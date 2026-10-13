# -*- coding: utf-8 -*-
"""FLIP44：途中保存の置き場所（2026-10-12、2 回目の確かめ check/check_fixes_ja.md の G2 の直し。record_ja.md §3.2。
3 回目の確かめ check/check_fixes2_ja.md の H1・H7 の直しは record_ja.md §3.3）。py -3.10。
風の計算が打ち切りの道を走ると 1 本 24〜34 個の途中保存（1 個 0.5〜0.7 GB）を作り、全部で 72〜100 GiB に届く（確かめ）。続きから走らせるのに
要る物と、計画が走らせ直しに使う物だけを残し、ほかは新しい物ができて確かめた後に消す。

  keep_policy(kind, ...)        g44_queue.py が作る計算の設定に足す決まり（cfg の ckpt_keep）。並びを通さない設定（runs/ready など）には入らないので、
                                そこでは前と同じに全部残る。
  after_launch(...)             g44_chain.py が起動の後に呼ぶ。
     - 帳面 rd/ckpt_ledger.json の made に、新しい途中保存と、それを作った chain の種類（origin）を書く。ckpt_keep のある chain（並び）は
       "queue"、ない chain（README §2 の 1 本ずつの道）は "single"（H7）。
     - 消してよいのは origin が "queue" の物だけ。"single" の物、origin のない古い帳面の物、帳面にない物（前からあった物）は、いつまでも消さない。
     - 残す物：(1) 決まりで守る物、(2) いちばん新しい物（続きから走らせる元）、(3) 確かめた始めの物（ある起動がそこから走り、新しいコマを進めた物。
       まだなければ 2 番目に新しい物）。
     - いちばん新しい物の大きさが、ほかの物の中央値の半分より小さい時は消さない（書きかけの見込み）。
     - 本当に消すのは cfg の out_root が runs（本番）で、ckpt_keep の dry が偽の時だけ。ほかの置き場所（試し）では「消すはずの物」を書くだけ。
     - 1 個ずつ消し、そのたびに帳面を書く。消せなかった物は prune_failed に理由を書いて次へ進む（3 回目の確かめ H6。H1 の直しで消す所を
       一つにまとめた時に入れた）。
  形の本番（SH。H1）：計算の間は 1 個も消さない（守る区間が全部のコマ）。並びは解析が巻き始め t_on を決めた後に prune_after_onset(...) を呼び、
     風の計算の始め（t_on − 3 s より前の最後の途中保存。計画 §4.1）・f_w・いちばん新しい物を残して、ほかの "queue" の物を消す。
     始めの途中保存が計画どおりにない時は 1 個も消さず、理由を返す。
  wind_start(...)               風の計算の始めのコマと、計画の始めが残っていない時の理由（消した時刻と理由・消せなかった・作っていない、など）。
  disk_plan(...)                並びの始めに、残りの段の置き場所の見込み（g44_hours の起動の真似から作る途中保存のコマを数え、上の決まりで残る数を出す）。
"""
import os, json, time, glob, math

REPO = r"G:/Unity/GreatWave_2026_Fresh"
R42 = REPO + "/Unity/Build/FLIP42/runs"
FPS = 24.0
LEDGER = "ckpt_ledger.json"
ALL_FRAMES = [0, 99999]     # 形の本番の守る区間（計算の間は全部守る。途中保存のファイル名は 4 桁のコマ）
WIND_LEAD_S = 3.0           # 風の計算の始め：t_on − 3 s より前の最後の途中保存（計画 §4.1。plan_numbers の wind.timing.ramp_start_before_onset_s）


# ------------------------------------------------------------------ 決まり
def frames_for(t):
    return int(math.floor(t * FPS + 1e-9)) + 1


def keep_policy(kind, onset_pre=None, f_w=None, Tc=None):
    """kind：PR・SH・B・RP。SH は計算の間は全部守り、巻き始めが決まった後に prune_after_onset で消す（H1）。Tc は前の版との互換のために残した（使わない）。"""
    pol = dict(mode="latest", protect_frames=[], protect_ranges=[], dry=False, kind=kind,
               why_ja="続きから走らせる元（いちばん新しい物）と、確かめた始めの物だけを残す（2026-10-12 G2）")
    if kind == "SH":
        pol["protect_frames"] = [int(f_w)] if f_w is not None else []
        pol["protect_ranges"] = [list(ALL_FRAMES)]
        pol["after_onset"] = dict(f_w=(int(f_w) if f_w is not None else None), lead_s=WIND_LEAD_S,
                                  onset_pre=(float(onset_pre) if onset_pre is not None else None))
        pol["why_ja"] = ("形の本番は、計算の間は途中保存を 1 個も消さない（守る区間が全部のコマ）。解析が巻き始め t_on を決めた後に、並びが"
                         "風の計算の始め（t_on − 3 s より前の最後の途中保存。計画 §4.1）・f_w（%s コマ）・いちばん新しい物を残して、ほかを消す"
                         "（2026-10-12 3 回目の確かめ H1 の直し。前の「下見の巻き始め − 3 s の前後 1 Tc」は、形の本番が下見より約 3 s 以上早く巻くと"
                         "風の計算の始めを消した）" % f_w)
    return pol


def protected(frames, pol):
    pf = set(int(v) for v in pol.get("protect_frames", []))
    out = set()
    for k in frames:
        if k in pf or any(int(a) <= k <= int(b) for a, b in pol.get("protect_ranges", [])):
            out.add(k)
    return out


# ------------------------------------------------------------------ 帳面（chain が作った途中保存）
def ckpt_path(rd, k):
    return os.path.join(rd, "ckpt", "v.%04d.sim" % int(k))


def ckpt_frames(rd):
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def load_ledger(rd):
    p = os.path.join(rd, LEDGER)
    if os.path.exists(p):
        L = json.load(open(p, encoding="utf8"))
    else:
        L = {}
    for k in ("made", "pruned", "would_prune", "prune_failed"):
        L.setdefault(k, {})
    L.setdefault("verified", [])
    return L


def save_ledger(rd, L):
    json.dump(L, open(os.path.join(rd, LEDGER), "w", encoding="utf8"), ensure_ascii=False, indent=1)


def note_made(rd, L, frames, how, launch_f0=None, origin="single"):
    """origin：並び（ckpt_keep のある chain）なら "queue"、ほかは "single"。すでに帳面にあるコマは書き換えない（初めに作った chain の種類が残る）。"""
    for k in frames:
        if str(k) not in L["made"] and os.path.exists(ckpt_path(rd, k)):
            L["made"][str(k)] = dict(bytes=os.path.getsize(ckpt_path(rd, k)), time=time.strftime("%Y-%m-%d %H:%M:%S"), how=how, launch=launch_f0,
                                     origin=origin)


def queue_made(L, k):
    """並びの chain（ckpt_keep あり）が作った物か。origin のない古い帳面の物は、並びが作ったと分からないので偽（消さない）。"""
    return (L["made"].get(str(int(k))) or {}).get("origin") == "queue"


def _prune(rd, L, cand, sz, real, newest, why, res):
    """cand を 1 個ずつ消す（real）か、消すはずの物として帳面に書く。消すたびに帳面を書く。消せなかった物は prune_failed に書いて次へ（H6）。"""
    for k in cand:
        rec = dict(bytes=sz.get(k), time=time.strftime("%Y-%m-%d %H:%M:%S"), newest=newest, why=why)
        if not real:
            L["would_prune"].setdefault(str(k), rec)
            res["would"].append(k)
            continue
        try:
            os.remove(ckpt_path(rd, k))
        except Exception as e:
            L["prune_failed"][str(k)] = dict(rec, error=repr(e)[:200])
            res["failed"].append(k)
            save_ledger(rd, L)
            continue
        L["pruned"][str(k)] = rec
        L["prune_failed"].pop(str(k), None)
        res["deleted"].append(k)
        save_ledger(rd, L)


def _sizes(rd, now):
    return {k: os.path.getsize(ckpt_path(rd, k)) for k in now}


def after_launch(rd, cfg, launch_f0, done, before, first_wall=None, med_wall=None, log=print):
    """起動の後：新しい途中保存を帳面に書き（origin つき）、決まり（cfg の ckpt_keep）があれば、残す物の外で、並びの chain が作った物を消す。
    返り値 dict(new, kept, deleted, would, failed, why, origin)。"""
    L = load_ledger(rd)
    now = ckpt_frames(rd)
    new = [k for k in now if k not in set(before)]
    pol = cfg.get("ckpt_keep")
    origin = "queue" if pol else "single"
    note_made(rd, L, new, "launch", launch_f0, origin=origin)
    res = dict(new=new, kept=now, deleted=[], would=[], failed=[], why=None, origin=origin)
    if not pol:
        res["why"] = "決まりなし（並びの外の chain。全部残す。帳面には origin single と書くので、並びが後で同じフォルダーで続けても消さない）"
        save_ledger(rd, L)
        return res
    if pol.get("mode") != "latest":
        res["why"] = "知らない決まり %s（消さない）" % pol.get("mode")
        save_ledger(rd, L)
        return res
    if not now:
        res["why"] = "途中保存なし"
        save_ledger(rd, L)
        return res
    start = int(launch_f0) - 1
    ok_start = bool(start in now and done is not None and int(done) >= int(launch_f0) + 1
                    and (first_wall is None or med_wall is None or first_wall <= max(120.0, 10.0 * med_wall)))
    if ok_start and start not in L["verified"]:
        L["verified"].append(start)
    newest = now[-1]
    sz = _sizes(rd, now)
    others = sorted(sz[k] for k in now if k != newest)
    if others and sz[newest] < 0.5 * others[len(others) // 2]:
        res["why"] = "いちばん新しい途中保存 %d の大きさ %d が、ほかの中央値 %d の半分より小さい（書きかけの見込み）ので消さない" % (newest, sz[newest], others[len(others) // 2])
        log(res["why"]); save_ledger(rd, L)
        return res
    keep = protected(now, pol) | {newest}
    ver = [v for v in L["verified"] if v in now and v != newest]
    if ver:
        keep.add(max(ver))
    elif len(now) >= 2:
        keep.add(now[-2])
    cand = [k for k in now if k not in keep and queue_made(L, k)]
    real = bool(cfg.get("out_root", "runs") == "runs" and not pol.get("dry"))
    if pol.get("after_onset"):
        res["why"] = "形の本番：解析が巻き始めを決めるまで消さない（H1）"
    _prune(rd, L, cand, sz, real, newest, "起動 %d の後（いちばん新しい物 %d、決まり %s）" % (int(launch_f0), newest, pol.get("kind")), res)
    res["kept"] = sorted(set(now) - set(res["deleted"])) if real else now
    L["last"] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), launch_f0=int(launch_f0), done=done, newest=newest, start_verified=ok_start,
                     keep=sorted(keep & set(now)), deleted=res["deleted"], would_prune=res["would"], failed=res["failed"], real=real)
    save_ledger(rd, L)
    log("ckpt_keep: newest %d, keep %s, %s %s%s" % (newest, sorted(keep & set(now)), "deleted" if real else "would delete (test root or dry)", cand,
                                                  (" failed %s" % res["failed"]) if res["failed"] else ""))
    return res


# ------------------------------------------------------------------ 形の本番：巻き始めが決まった後（H1）
def wind_start(rd, t_on, lead_s=WIND_LEAD_S, L=None, now=None):
    """風の計算の始め。返り値 dict(t_lim, start, want, why_ja)：
    start ＝ 残っている途中保存のうち t_on − lead_s より前の最後のコマ（並びが使う物）、want ＝ 帳面と残っている物から分かる計画の始め
    （作った物の中で同じ条件の最後。計画 §4.1）。start が want と違う時・ない時は why_ja に理由を書く。"""
    L = L if L is not None else load_ledger(rd)
    now = now if now is not None else ckpt_frames(rd)
    t_lim = float(t_on) - float(lead_s)
    ok = lambda k: (int(k) - 1) / FPS < t_lim
    have = [k for k in now if ok(k)]
    known = set(now) | set(int(k) for k in L["made"]) | set(int(k) for k in L["pruned"])
    want_c = sorted(k for k in known if ok(k))
    start = have[-1] if have else None
    want = want_c[-1] if want_c else None
    why = None
    if want is None:
        why = "形の本番は t_on − %g s（%.2f s）より前の途中保存を作っていない（フォルダーにも帳面にもない）" % (lead_s, t_lim)
    elif start != want:
        p = L["pruned"].get(str(want))
        if p:
            why = "計画の始め %d コマ（%.2f s）は %s に消してあった（%s）" % (want, (want - 1) / FPS, p.get("time"),
                                                                 p.get("why") or "前の版の決まり：守る区間の外")
        else:
            why = ("計画の始め %d コマ（%.2f s）は帳面の made にあるがファイルがない（消した記録はない。並びの外で動かされたか消された見込み）"
                   % (want, (want - 1) / FPS))
        if start is not None:
            why += ("。残っている物のうち t_on − %g s より前の最後の %d コマ（%.2f s）から始める（途中保存から続けた計算は元とビット単位で同じなので、"
                    "結果は同じで、計算が %.1f s 分延びる）" % (lead_s, start, (start - 1) / FPS, (want - start) / FPS))
        else:
            why += "。t_on − %g s より前に残っている途中保存はない。風の計算を走らせるには形の本番を走らせ直す" % lead_s
    return dict(t_lim=t_lim, start=start, want=want, why_ja=why)


def prune_after_onset(rd, t_on, f_w=None, real=False, log=print, lead_s=WIND_LEAD_S):
    """形の本番の解析が巻き始め t_on を決めた後に、並び（g44_queue.stage_sh）が呼ぶ。
    残す：風の計算の始め（t_on − lead_s より前の最後の途中保存。計画 §4.1）、f_w（計画が必ず作る物）、いちばん新しい物（続きから走らせる元。
    それが書きかけの見込みなら 1 つ前も）。ほかの、並びの chain が作った物（origin queue）を消す（real でなければ消すはずの物を書くだけ）。
    始めの途中保存がない時と、計画の始めが残っていない時は 1 個も消さず、理由を返す。返り値 dict(start, want, kept, deleted, would, failed, why_ja, report_ja)。"""
    L = load_ledger(rd)
    now = ckpt_frames(rd)
    w = wind_start(rd, t_on, lead_s, L=L, now=now)
    res = dict(t_on=float(t_on), t_lim=w["t_lim"], start=w["start"], want=w["want"], f_w=f_w, kept=list(now), deleted=[], would=[], failed=[],
               why_ja=w["why_ja"], real=bool(real), pruned_none=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if w["start"] is None or w["start"] != w["want"]:
        res["report_ja"] = ("形の本番：風の計算の始めの途中保存が計画どおりにないので、途中保存は 1 個も消さなかった（%s）" % w["why_ja"])
        L["after_onset"] = dict(time=stamp, t_on=float(t_on), t_lim=w["t_lim"], start=w["start"], want=w["want"], keep=list(now), deleted=[], would=[],
                                failed=[], real=bool(real), why_ja=res["report_ja"])
        save_ledger(rd, L)
        log(res["report_ja"])
        return res
    newest = now[-1]
    sz = _sizes(rd, now)
    keep = {w["start"], newest}
    if f_w is not None and int(f_w) in now:
        keep.add(int(f_w))
    others = sorted(sz[k] for k in now if k != newest)
    if len(now) >= 2 and others and sz[newest] < 0.5 * others[len(others) // 2]:
        keep.add(now[-2])
    cand = [k for k in now if k not in keep and queue_made(L, k)]
    not_queue = [k for k in now if k not in keep and not queue_made(L, k)]
    _prune(rd, L, cand, sz, real, newest, "形の本番の巻き始め %.2f s が決まった後（風の計算の始め %d コマ・f_w %s・いちばん新しい %d を残す）" % (
        float(t_on), w["start"], f_w, newest), res)
    res["pruned_none"] = not (res["deleted"] or res["would"])
    res["kept"] = sorted(set(now) - set(res["deleted"])) if real else list(now)
    gone = res["deleted"] if real else res["would"]
    gib = sum(sz[k] for k in gone) / 2**30
    res["report_ja"] = ("形の本番の途中保存：巻き始め %.2f s が決まったので、風の計算の始め %d コマ（%.2f s。t_on − %g s より前の最後）・f_w %s・"
                        "いちばん新しい %d を残し、並びが作ったほかの %d 個（%.1f GiB）を%s。並びの外で作った物・帳面にない物 %d 個は残した%s" % (
                            float(t_on), w["start"], (w["start"] - 1) / FPS, lead_s, f_w, newest, len(gone), gib,
                            "消した" if real else "消すはずの物として帳面に書いた（試しの置き場所か dry。消していない）", len(not_queue),
                            ("。消せなかった物 %s（帳面の prune_failed）" % res["failed"]) if res["failed"] else ""))
    L["after_onset"] = dict(time=stamp, t_on=float(t_on), t_lim=w["t_lim"], start=w["start"], want=w["want"], f_w=f_w, newest=newest,
                            keep=sorted(keep & set(now)), deleted=res["deleted"], would=res["would"], failed=res["failed"], real=bool(real),
                            why_ja=res["report_ja"])
    save_ledger(rd, L)
    log(res["report_ja"])
    return res


def pruned_before(rd, t_limit):
    """帳面で消した物のうち、時刻 t_limit より前で最も遅いコマ（前の版からの互換。並びは wind_start を使う）。"""
    L = load_ledger(rd)
    ks = [int(k) for k in L["pruned"] if (int(k) - 1) / FPS < t_limit]
    return max(ks) if ks else None


# ------------------------------------------------------------------ 置き場所の見込み
def _replay(trace, pol, start=None, t_on=None):
    """起動の真似（g44_hours.simulate の trace）の上で after_launch と同じ決まりを当てる。形の本番（after_onset）は、終わりに
    prune_after_onset と同じ残し方（t_on − 3 s より前の最後・f_w・いちばん新しい物）を当てる。返り値：作る数、終わりに残る数、いちばん多い時の数。"""
    now = [start] if start is not None else []
    made = set(now); peak = len(now); verified = []
    for L in trace:
        new = [k for k in L["cks"] if k not in now]
        made |= set(new)
        now = sorted(set(now) | set(new))
        peak = max(peak, len(now))
        if pol is None or not now:
            continue
        s = L["f0"] - 1
        if s in now and L["done"] >= L["f0"] + 1 and s not in verified:
            verified.append(s)
        newest = now[-1]
        keep = protected(now, pol) | {newest}
        ver = [v for v in verified if v in now and v != newest]
        if ver:
            keep.add(max(ver))
        elif len(now) >= 2:
            keep.add(now[-2])
        now = sorted(keep & set(now))
    ao = (pol or {}).get("after_onset")
    if ao and t_on is not None and now:
        lim = float(t_on) - float(ao.get("lead_s", WIND_LEAD_S))
        b = [k for k in now if (k - 1) / FPS < lim]
        if b:
            keep = {b[-1], now[-1]} | ({ao["f_w"]} if ao.get("f_w") in now else set())
            now = sorted(keep & set(now))
    return dict(made=len(made), end=len(now), peak=peak)


def ckpt_bytes():
    """1 個の大きさの上の見込み：FLIP42 の最大（0.34375 m の計算は R2、0.25 m は R3。礁で粒子が減る分は入れない）。"""
    out = {}
    for dp, rid, fb in ((0.34375, "R2", 0.351e9), (0.25, "R3", 0.684e9)):
        fs = glob.glob(os.path.join(R42, rid, "ckpt", "v.*.sim"))
        out[dp] = max(os.path.getsize(p) for p in fs) if fs else fb
    return out


def rec_bytes_per_frame():
    """途中保存の外の記録（一番上の水面・断面）の 1 コマの大きさ：FLIP42 の記録から。風の計算は圧力の断面の分を足す。"""
    out = {}
    for dp, rid in ((0.34375, "R2"), (0.25, "R3")):
        rd = os.path.join(R42, rid)
        tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(rd, "*.npz")))
        n = 4560
        try:
            n = max(int(json.load(open(p, encoding="utf8")).get("f_end_done") or 0) for p in glob.glob(os.path.join(rd, "run_c*.json")))
        except Exception:
            pass
        out[dp] = tot / max(n, 1)
    out["psec"] = 0.25e6       # 粒子 0.25 m・600 m の断面の圧力と水面の写し（S9_v2 の 35 KB/コマを格子 4 倍・長さ 1.5 倍、余り 1.2 倍）
    return out


def disk_plan(stages, choice=None, sh_onset=None, sh_td=None, loads=(1.0, 1.33), onsets=(140.0, 145.0, 150.0, 155.0, 160.0, 165.0)):
    """残りの段の置き場所の見込み（GiB = 2³⁰ バイト。g44_chain の止まる線と同じ単位）。返り値 dict(rows, total_keep_gb, total_all_gb, peak_extra_gb)。
    各段は、機械の重さ loads と巻き始め onsets の組の中の最大の数で数える（形の本番の結果があれば、その巻き始めだけ）。
    形の本番は計算の間は消さないので、途中でいちばん多い数は作る数と同じ（H1 の直しの置き場所の値段）。"""
    import g44_hours as H
    P = H.plan(); Tc = P["tank"]["Tc"]; runs = P["runs"]
    CB = ckpt_bytes(); RB = rec_bytes_per_frame()
    aims = {"PR1": P["programs"]["PR1_R3_flat592"]["aim_t_s"], "PR2": P["programs"]["PR2_reef_aim500"]["aim_t_s"]}
    ons = [float(sh_onset)] if sh_onset is not None else list(onsets)
    rows = []
    for st in stages:
        if st not in ("PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP"):
            continue
        cand = []
        for load in loads:
            for o in ons:
                tr = []
                t_on = None
                if st in ("PR1", "PR2", "PR3"):
                    r = H.est_PR(o, aims.get(st, aims["PR2"]), 1.0, load, Tc, max_h=2 * runs["PR1"]["hours"]["hi"], trace=tr)
                    pol = keep_policy("PR"); dp = 0.34375; start = None; f_first = 1
                elif st == "SH":
                    pre = aims["PR1"] if choice in (None, "PR1") else aims["PR2"]
                    r = H.est_SH(o, pre, 1.0, load, Tc, max_h=2 * runs["SH"]["hours"]["hi"], trace=tr)
                    pol = keep_policy("SH", onset_pre=o, f_w=r["f_w"], Tc=Tc); dp = 0.25; start = None; f_first = 1; t_on = o
                elif st in ("B35S", "B45S"):
                    r = H.est_B(o, 1.0, load, Tc, "cap", t_td=sh_td, trace=tr)
                    pol = keep_policy("B"); dp = 0.25; start = r["ckpt_frame"]; f_first = r["ckpt_frame"] + 1
                else:
                    aim = "flat" if choice == "PR1" else "reef"
                    r = H.est_RP(aim, 1.0, load, P, max_h=2 * runs["RP"]["hours"]["hi"], trace=tr)
                    if choice is None:
                        tr2 = []
                        r2 = H.est_RP("flat", 1.0, load, P, max_h=2 * runs["RP"]["hours"]["hi"], trace=tr2)
                        if r2["last_frame"] > r["last_frame"]:
                            r, tr = r2, tr2
                    pol = keep_policy("RP"); dp = 0.34375; start = None; f_first = 1
                k = _replay(tr, pol, start, t_on=t_on)
                a = _replay(tr, None, start)
                frames = int(r["last_frame"]) - f_first + 1
                recb = frames * RB[dp] * 1.5 + (frames * RB["psec"] if st.startswith("B") else 0.0)
                cand.append(dict(stage=st, load=load, onset=o, ckpt_gb=CB[dp] / 2**30, made=a["made"], end=k["end"], peak=k["peak"], frames=frames,
                                 records_gb=recb / 2**30, keep_gb=(k["end"] * CB[dp] + recb) / 2**30, all_gb=(a["made"] * CB[dp] + recb) / 2**30,
                                 peak_extra_gb=(k["peak"] - k["end"]) * CB[dp] / 2**30))
        best = dict(max(cand, key=lambda r: r["keep_gb"] + r["peak_extra_gb"]))
        best["all_gb_max"] = max(r["all_gb"] for r in cand)
        best["made_max"] = max(r["made"] for r in cand)
        rows.append(best)
    total_keep = sum(r["keep_gb"] for r in rows)
    peak_extra = max([r["peak_extra_gb"] for r in rows] or [0.0])
    total_all = sum(r["all_gb_max"] for r in rows)
    return dict(rows=rows, total_keep_gb=total_keep, peak_extra_gb=peak_extra, total_need_gb=total_keep + peak_extra, total_all_gb=total_all,
                basis_ja="途中保存 1 個は FLIP42 の最大（%.3f GiB・%.3f GiB）、記録は FLIP42 の 1 コマの大きさの 1.5 倍（風は圧力の断面を足す）。"
                         "数は g44_hours の起動の真似（機械の重さ %s、巻き始め %s s）の最大。消す決まり（g44_ckpt.after_launch と、形の本番の "
                         "prune_after_onset）を同じ真似に当てた。形の本番は計算の間は消さないので、途中でいちばん多い数は作る数と同じ" % (
                             CB[0.34375] / 2**30, CB[0.25] / 2**30, "・".join("%g" % v for v in loads), "・".join("%g" % v for v in ons)))


def plan_md(dp_, free_gb, stop_gb, root):
    """disk_plan の結果を、人が読む表にする。"""
    L = ["# 置き場所の見込み（g44_queue.py が並びの始めに書いた。%s）" % time.strftime("%Y-%m-%d %H:%M"), "",
         "- G: の空き：%.1f GiB。止まる線（計画 N8、g44_chain・g44_run と同じ GiB で見る）：%.0f GiB。使える分：%.1f GiB" % (free_gb, stop_gb, free_gb - stop_gb),
         "- 見込み（消す決まりあり）：%.1f GiB（終わりに残る %.1f GiB ＋ 計算の途中でいちばん多い時の上乗せ %.1f GiB）" % (
             dp_["total_need_gb"], dp_["total_keep_gb"], dp_["peak_extra_gb"]),
         "- 消さない時（前の作り。確かめ G2 の見込みと同じ形）：%.1f GiB" % dp_["total_all_gb"],
         "- 余り：%.1f GiB" % (free_gb - stop_gb - dp_["total_need_gb"]), "- 出し方：%s" % dp_["basis_ja"], "",
         "| 段 | 途中保存 1 個（GiB） | 作る数（消さない時） | 終わりに残る数 | 途中でいちばん多い数 | 記録（GiB） | 残る分（GiB） | 消さない時（GiB） |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in dp_["rows"]:
        L.append("| %s | %.3f | %d | %d | %d | %.2f | %.2f | %.2f |" % (r["stage"], r["ckpt_gb"], r["made_max"], r["end"], r["peak"], r["records_gb"],
                                                                     r["keep_gb"], r["all_gb_max"]))
    L += ["", "- 消すのは、この並びの chain が本番の置き場所（runs）に作った途中保存（帳面の made の origin が queue）だけ。1 本ずつの道（README §2）で"
              "作った物と、帳面にない物は消さない。消した物は `%s/<計算>/ckpt_ledger.json` の pruned に残る。" % root,
          "- 形の本番は、計算の間は途中保存を 1 個も消さない。解析が巻き始め t_on を決めた後に、風の計算の始め（t_on − 3 s より前の最後。計画 §4.1）・"
          "f_w・いちばん新しい物を残して消す。始めの途中保存が計画どおりにない時は 1 個も消さず、理由を QUEUE_REPORT.txt に書く。",
          "- 止まる線はそのまま：G: の空きが %.0f GiB を切ると、計算は次の起動をせずに止まる（STOP_DISK.txt）。" % stop_gb]
    return "\n".join(L) + "\n"
