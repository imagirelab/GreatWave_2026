# -*- coding: utf-8 -*-
"""FLIP45：途中保存の帳面と残し方（py -3.10）。FLIP44 の g44_ckpt.py（変えていない）の考えを写して新しく書いた（計画 plan_ja.md §7.3）。

  - 帳面 runs/<計算>/ckpt_ledger.json に、作った途中保存（コマ・大きさ・時刻・作った起動）を書く。
  - 古い途中保存を消すのは削除に当たる。進行役は利用者の許しなしに消さない（計画 §7.3・§11）。cfg の ckpt_keep に
    allowed_by_user（利用者の許しの言葉と日時。g45_queue.py の --ckpt-prune-ok が入れる）がない時は、1 個も消さず、
    「許しがあれば消す物」を would_prune に書くだけ。許しがあり、置き場所が runs（本番）の時だけ本当に消す。
  - 許しがある時に残す物（計画 §7.3）：いちばん新しい 2 個と、M1h の始めに使う 2 個（巻き始めの 7 s 前より前の最後の 2 個）。
    M1（と巻き始めを使う計算）は、計算の中で巻き始めを見つけるまで、時刻 30 s より後の物を消さない（見直し L3。plan_numbers の ckpt_rule）。
    巻き始めが分かる前は、30 s より前の物だけが消す候補。
  - いちばん新しい物の大きさが、ほかの物の中央値の半分より小さい時は消さない（書きかけの見込み。FLIP44 と同じ）。
  disk_plan(...)：残りの計算の置き場所の見込み（全部残す・4 個残す）。
"""
import os, json, time, glob, math

FPS = 24.0
LEDGER = "ckpt_ledger.json"


def ckpt_path(rd, k):
    return os.path.join(rd, "ckpt", "v.%04d.sim" % int(k))


def ckpt_frames(rd):
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def t_of(k, t_off):
    return t_off + (int(k) - 1) / FPS


def load_ledger(rd):
    p = os.path.join(rd, LEDGER)
    L = json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}
    for k in ("made", "pruned", "would_prune", "prune_failed"):
        L.setdefault(k, {})
    return L


def save_ledger(rd, L):
    json.dump(L, open(os.path.join(rd, LEDGER), "w", encoding="utf8"), ensure_ascii=False, indent=1)


def keep_policy(kind="main", onset_known=False, t_onset=None, keep_all_from_s=30.0, allowed_by_user=None):
    """g45_queue.py が cfg に足す決まり。allowed_by_user が None なら消さない（would_prune だけ）。"""
    return dict(mode="keep4", kind=kind, keep_all_from_s=float(keep_all_from_s), t_onset=t_onset, onset_known=bool(onset_known),
                allowed_by_user=allowed_by_user,
                why_ja="いちばん新しい 2 個と、M1h の始めに使う 2 個（巻き始めの 7 s 前より前の最後の 2 個）を残す。巻き始めが分かるまで "
                       "%.0f s より後の物は消さない。利用者の許しがない間は 1 個も消さない（計画 §7.3）" % keep_all_from_s)


def keep_set(frames, pol, t_off):
    """残す物の集合と、理由。"""
    if not frames:
        return set(), "途中保存なし"
    keep = set(frames[-2:])
    t_on = pol.get("t_onset")
    if t_on is None:
        keep |= {k for k in frames if t_of(k, t_off) > float(pol.get("keep_all_from_s", 30.0)) - 1e-9}
        return keep, "巻き始めがまだ分からないので、%.0f s より後の物は全部残す" % float(pol.get("keep_all_from_s", 30.0))
    pre = [k for k in frames if t_of(k, t_off) < float(t_on) - 7.0]
    keep |= set(pre[-2:])
    return keep, "巻き始め %.2f s の 7 s 前より前の最後の 2 個 %s と、いちばん新しい 2 個" % (float(t_on), pre[-2:])


def after_launch(rd, cfg, launch_f0, done, before, log=print):
    """起動の後：新しい途中保存を帳面に書き、決まりがあれば残す物の外を消す（許しがある時だけ）か、消すはずの物として書く。"""
    L = load_ledger(rd)
    now = ckpt_frames(rd)
    new = [k for k in now if k not in set(before)]
    for k in new:
        if str(k) not in L["made"]:
            L["made"][str(k)] = dict(bytes=os.path.getsize(ckpt_path(rd, k)), time=time.strftime("%Y-%m-%d %H:%M:%S"), launch=int(launch_f0))
    pol = cfg.get("ckpt_keep")
    res = dict(new=new, kept=now, deleted=[], would=[], failed=[], why=None)
    if not pol:
        res["why"] = "決まりなし（全部残す）"
        save_ledger(rd, L); return res
    t_off = float(cfg["parms"]["t_off"])
    keep, why = keep_set(now, pol, t_off)
    sz = {k: os.path.getsize(ckpt_path(rd, k)) for k in now}
    others = sorted(sz[k] for k in now if k != now[-1])
    if others and sz[now[-1]] < 0.5 * others[len(others) // 2]:
        res["why"] = "いちばん新しい物が書きかけの見込み（消さない）"
        save_ledger(rd, L); return res
    cand = [k for k in now if k not in keep]
    real = bool(pol.get("allowed_by_user")) and cfg.get("out_root", "runs") == "runs"
    for k in cand:
        rec = dict(bytes=sz[k], time=time.strftime("%Y-%m-%d %H:%M:%S"), why=why)
        if not real:
            L["would_prune"].setdefault(str(k), rec); res["would"].append(k); continue
        try:
            os.remove(ckpt_path(rd, k))
            L["pruned"][str(k)] = dict(rec, allowed_by_user=pol["allowed_by_user"]); res["deleted"].append(k)
        except Exception as e:
            L["prune_failed"][str(k)] = dict(rec, error=repr(e)[:200]); res["failed"].append(k)
        save_ledger(rd, L)
    res["why"] = why + ("" if real else "（利用者の許しがない・試しの置き場所なので消していない。消すはずの物は would_prune）")
    L["last"] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), launch_f0=int(launch_f0), done=done, keep=sorted(keep), real=real,
                     deleted=res["deleted"], would=res["would"])
    save_ledger(rd, L)
    log("ckpt_keep: keep %s, %s %s" % (sorted(keep), "deleted" if real else "would delete", cand))
    return res


def start_for_m1h(rd, t_onset, t_off):
    """M1h の始め：巻き始めの 7 s 前より前の最後の途中保存（計画 §2）。返り値 (コマ, 理由)。"""
    now = ckpt_frames(rd)
    pre = [k for k in now if t_of(k, t_off) < float(t_onset) - 7.0]
    if not pre:
        return None, "巻き始め %.2f s の 7 s 前より前の途中保存がない" % float(t_onset)
    return pre[-1], "巻き始め %.2f s の 7 s 前（%.2f s）より前の最後の途中保存 %d（%.2f s）" % (t_onset, t_onset - 7.0, pre[-1], t_of(pre[-1], t_off))


def disk_plan(runs, ckpt_gb_key="ckpt_GB"):
    """plan_numbers の runs の行の並び（V1 など）から、全部残す・4 個残すの置き場所の見込み（GB）。"""
    tot_all = [0.0, 0.0]; tot4 = 0.0; rec = 0.0
    for r in runs:
        tot_all[0] += float(r["ckpt_keep_all_GB"]["lo"] if isinstance(r["ckpt_keep_all_GB"], dict) else r["ckpt_keep_all_GB"][0])
        tot_all[1] += float(r["ckpt_keep_all_GB"]["hi"] if isinstance(r["ckpt_keep_all_GB"], dict) else r["ckpt_keep_all_GB"][1])
        tot4 += float(r["ckpt_keep4_GB"])
        rec += float(r["records_GB"])
    return dict(keep_all_GB=tot_all, keep4_GB=tot4, records_GB=rec)
