# -*- coding: utf-8 -*-
"""FLIP45：計画 plan_ja.md §2 の並びを走らせる（py -3.10）。FLIP44 の g44_queue.py（変えていない）の考えを写して新しく書いた。
二つの入口：
  下見（合意の前。利用者の Q57 の B）：--preview。V1 を走らせて解析し、runs/V1_RESULT_ja.md に関門（§6.9 の (a)〜(d)）・窓の前提（§6.8）・
    時間の出し直し・平均の水面の読みを書いて止まる（人の確かめを待つ。終わりのコード 3）。V2・V1h・V4（粒子 0.5 m）は、利用者が合意の前に
    走らせてよいと言った時だけ（--user-ok-05 "<利用者の言葉と日時>"。計画 §12 の 2）。
  本番（指導教員の合意の後だけ）：--agreed "<合意の日時と場所>"。並び A か B（runs/SEQ_DECISION.json）で
    [V2（V1 が §6.8 の前提を満たし、まだの時だけ。その後で止まる）] → [V3（V1 の巻き始めの時刻が ±5 % の外の時だけ。記録だけ）] →
    M1 → [止まる：人の確かめ] → M1h → V1h → V4 → RPT05 → X60 →（最初の報告）→ M1c → F40 → X45 →（並び A だけ）M1f。
  --agreed も --preview もない時は何も走らせない。凍結した計画の SHA-256 が違う時・入口の利得の記録がない時も走らせない。
V1 の後の段（V2・V1h・V4・V3 と、M1 から後の全部）の守り（2026-10-12 12:53〜12:58 に直した。別の者の確かめ check_ja.md の F2・F6・F7）：
  - V1 が終わっていて、関門 (a)（見張りと止まりなく走りきった）・(b)（N3 の振幅の比 0.90〜1.10）・(d)（焦点の近くの頂 5.1 m 以上）が
    全部入っていること。(b) が外れたら、計画 §6.9 のとおり「帯の作りを調べ、作りの誤りだけを直して V1 を走らせ直す」と書いて止まる
    （走らせ直しは --preview --rerun-v1 "<直した所と record_ja.md の節>"。前の V1 は V1_try<n>_<日時> へ移す。消さない）。
    (d) が外れたら、記録を調べて伺うと書いて止まる。(c)（1 コマの秒と本番の時間の出し直し）は V1_RESULT_ja.md に書き、人の確かめで見る。
  - その V1 を人が見た確かめ（--confirm v1）があること。--confirm v1 は V1 が終わった後だけ受け、どの V1 を見たかを一緒に覚える
    （V1 を走らせ直すと、前の確かめは使えない）。--confirm v2・m1 も、その計算が終わった後だけ受ける。
止まって人の確かめを待つ所（計画 §10.1）：V1 の後、V2 の後、M1 の後。続ける言葉は runs/QUEUE_PAUSE.txt に書く。
途中保存の片付け（計画 §7.3）：--ckpt-prune-ok "<利用者の言葉と日時>" がある時だけ、g45_chain.py が計算ごとに 4 個を残して古い物を消す。
  ない時は全部残し、G: の空きが 25 GB を切ったら止まる（N7）。
止めて伺う所（runs/QUEUE_STOP.txt に理由と続ける言葉。終わりのコード 2）：計算が途中で止まった（打ち切りの時間・途中保存が作れない・hython が落ちた・
  水面の見張り）、G: の空き、解析が止まった、V1 の関門 (a)・(b)・(d) が外れた、受けられない --confirm。
使い方：
  py -3.10 g45_queue.py --preview [--confirm v1] [--user-ok-05 "..."] [--rerun-v1 "..."] [--dry-run] [--root runs]
  py -3.10 g45_queue.py --agreed "2026-10-13 18:00 Discord" [--confirm v1] [--confirm v2] [--confirm m1] [--from <段>] [--only <段>]
                        [--ckpt-prune-ok "..."] [--dry-run]
  段：V2 V3 M1 M1h V1h V4 RPT05 X60 M1c F40 X45 M1f
--dry-run は設定を書いて、走らせる物を queue_log.txt に書くだけ（hython も表も作らない）。dry-run は毎回新しい --root の名前で打つ
  （前の dry-run の状態 QUEUE_STATE.json が残っていると、済んだ段を飛ばす）。V1 の後の道の試しは x45_qdry.py（状態を仮に置いて打つ）。
"""
import sys, os, json, time, subprocess, argparse, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_cfg as C
import g45_ckpt as K

EXIT_STOP, EXIT_PAUSE = 2, 3
ap = argparse.ArgumentParser()
ap.add_argument("--preview", action="store_true"); ap.add_argument("--agreed", default=None)
ap.add_argument("--user-ok-05", default=None); ap.add_argument("--confirm", action="append", default=[])
ap.add_argument("--rerun-v1", default=None)
ap.add_argument("--from", dest="frm", default=None); ap.add_argument("--only", default=None)
ap.add_argument("--ckpt-prune-ok", default=None); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--root", default="runs")
A = ap.parse_args()
RUNS = os.path.join(GC.B45, A.root).replace("\\", "/")
os.makedirs(RUNS, exist_ok=True)
STATE = os.path.join(RUNS, "QUEUE_STATE.json")
D_GATE = 0.8 * 6.317                   # 計画 §6.9 (d)：壁ありの線形の最大の 0.8 倍（5.1 m）


def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode(), flush=True)
    open(os.path.join(RUNS, "queue_log.txt"), "a", encoding="utf8").write(msg + "\n")


def stop(why):
    open(os.path.join(RUNS, "QUEUE_STOP.txt"), "a", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + why + "\n")
    log("STOP", why); sys.exit(EXIT_STOP)


def pause(why, cont):
    open(os.path.join(RUNS, "QUEUE_PAUSE.txt"), "a", encoding="utf8").write("%s %s\n  続ける言葉：%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), why, cont))
    log("PAUSE", why, "| 続ける言葉：", cont); sys.exit(EXIT_PAUSE)


def state():
    return json.load(open(STATE, encoding="utf8")) if os.path.exists(STATE) else {}


def save_state(s):
    json.dump(s, open(STATE, "w", encoding="utf8"), ensure_ascii=False, indent=1)


def cmd(extra, mode=None):
    """続ける言葉。mode：preview か agreed（既定は今の入口）。"""
    base = 'py -3.10 Tools/GWWaveGen/flip45/g45_queue.py '
    mode = mode or ("agreed" if A.agreed else "preview")
    base += ('--agreed "%s" ' % (A.agreed or "<指導教員の合意の日時と場所>")) if mode == "agreed" else "--preview "
    if A.user_ok_05 and mode == "preview":
        base += '--user-ok-05 "%s" ' % A.user_ok_05
    if A.ckpt_prune_ok:
        base += '--ckpt-prune-ok "%s" ' % A.ckpt_prune_ok
    return (base + extra).strip() + ((" --root " + A.root) if A.root != "runs" else "") + (" --dry-run" if A.dry_run else "")


SEQ_A = ["M1", "M1h", "V1h", "V4", "RPT05", "X60", "M1c", "F40", "X45", "M1f"]
NAME = {"A": dict(V2="V2", V3="V3", M1="M1_L2", M1h="M1h_L2", V1h="V1h", V4="V4", RPT05="RPT05", X60="X60_L2x", M1c="M1c_L2", F40="F40_L1",
                  X45="X45_L2w", M1f="M1f_L2"),
        "B": dict(V2="V2", V3="V3", M1="M1_L1", M1h="M1h_L1", V1h="V1h", V4="V4", RPT05="RPT05", X60="X60_L1x", M1c="M1c_L1", F40="F40_L1",
                  X45="X45_L1w", M1f=None)}


# ------------------------------------------------------------------ 守り
if not A.preview and not A.agreed:
    print("走らせない：--preview（合意の前の下見 V1）か --agreed \"<指導教員の合意の日時と場所>\"（本番）が要る（計画 §11・Q49・Q56）")
    sys.exit(EXIT_STOP)
ok, bad = GC.frozen_ok()
if not ok:
    stop("凍結した計画のファイルの SHA-256 が plan_frozen.json と違う（%s）。計画を変えたなら走らせる前に伺う" % bad)
if not os.path.exists(GC.GAIN_FILE):
    stop("入口の利得の記録 %s がない（煙の試し S2b・S2a の後に決める。計画 §4.1）" % GC.GAIN_FILE)
if A.rerun_v1 and (A.agreed or not A.preview):
    stop("--rerun-v1 は --preview と一緒に使う（V1 の走らせ直しは下見の道）")
if A.agreed:
    open(os.path.join(RUNS, "AGREED.txt"), "a", encoding="utf8").write("%s 合意の記録（--agreed）：%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), A.agreed))
GC.keep_awake()
S = state()


def m1_done(s):
    return [n for n in ("M1_L1", "M1_L2") if s.get(n + "_done")]


# 人の確かめ：その計算が終わった後だけ受け、どの計算を見たか（終わった時刻）を一緒に覚える（check_ja.md の F7）
for c in A.confirm:
    c = c.lower()
    if c == "v1":
        if not S.get("V1_done"):
            stop("--confirm v1 は受けない：V1 がまだ終わっていない（この置き場所 %s に V1 の結果がない）。先に --preview で V1 を走らせる" % A.root)
        S.setdefault("confirmed", {})["v1"] = dict(at=time.strftime("%Y-%m-%d %H:%M:%S"), of_V1_done=S["V1_done"])
    elif c == "v2":
        if not S.get("V2_done"):
            stop("--confirm v2 は受けない：V2 がまだ終わっていない")
        S.setdefault("confirmed", {})["v2"] = dict(at=time.strftime("%Y-%m-%d %H:%M:%S"), of_V2_done=S["V2_done"])
    elif c == "m1":
        if not m1_done(S):
            stop("--confirm m1 は受けない：M1 がまだ終わっていない")
        S.setdefault("confirmed", {})["m1"] = dict(at=time.strftime("%Y-%m-%d %H:%M:%S"), of=m1_done(S))
    else:
        stop("--confirm %s は知らない（v1・v2・m1 だけ）" % c)
save_state(S)


def v1_confirmed(s):
    c = (s.get("confirmed") or {}).get("v1")
    return isinstance(c, dict) and s.get("V1_done") is not None and c.get("of_V1_done") == s.get("V1_done")


def v1_gate_problem(s):
    """V1 の後の段を始めてよいか（計画 §6.9 の (a)・(b)・(d)）。返り値 None（よい）か、止める理由の文。"""
    if not s.get("V1_done") or not s.get("V1_gate"):
        return "V1 がまだ終わっていない（V1 の後の段は V1 の関門の後。計画 §6.9）。先に `%s` で V1 を走らせる" % cmd("", "preview")
    g = s["V1_gate"]
    if not g.get("a"):
        return ("V1 の関門 (a)（見張りと止まりなく走りきる）が外れた（%s）。V1 の後の段を始めない。記録を見て伺う（計画 §6.9）"
                % g.get("stops"))
    if not g.get("b"):
        return ("V1 の関門 (b)（N3 の振幅の比 0.90〜1.10）が外れた（最小 %s・最大 %s）。V1 の後の段（M1 から後を含む）を始めない。計画 §6.9 のとおり："
                "帯の作り（VEX、表、壁のなだらかさ、利得の入れ方）が煙の試しと同じかを調べ、作りの誤りだけを直して V1 を走らせ直す。"
                "利得は V1 の値から決め直さない。直した所を record_ja.md に書く。走らせ直す言葉：`%s`"
                % (g.get("n3_min"), g.get("n3_max"), cmd('--rerun-v1 "<直した所と record_ja.md の節>"', "preview")))
    if not g.get("d"):
        return ("V1 の関門 (d)（焦点の近くの y = 0 の頂が 5.1 m 以上）が外れた（%s m）。V1 の後の段（M1 から後を含む）を始めない。"
                "記録を調べて伺う（計画 §6.9）" % g.get("focus_eta"))
    return None


def run_stage(name, overrides=None):
    """計算 1 本：設定を作り（表も）、g45_chain.py で走らせ、止まり方を読み、解析する。返り値 (状態, ana)。"""
    try:
        cfg = C.make(name, root=A.root, overrides=overrides)
    except SystemExit as e:
        stop("%s：設定を作れなかった（%s）" % (name, e))
    cfg["ckpt_keep"] = K.keep_policy("main", allowed_by_user=A.ckpt_prune_ok)
    cfg["n1_x_min"] = 100.0 if cfg["parms"]["x0"] == 0.0 else cfg["parms"]["x0"]
    rd = os.path.join(RUNS, name)
    os.makedirs(rd, exist_ok=True)
    if not A.dry_run:
        cfg = C.table_for(cfg)                     # 表は走らせる時だけ作る（dry-run は作らない）
    p = os.path.join(rd, "cfg_queue.json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    log("stage", name, "f_end", cfg["f_end"], "max_hours", cfg["max_hours"], "table", (cfg["table"].get("sha256") or "（dry-run：作らない）")[:12],
        "ramp", cfg["table"].get("ramp"), "in_gain", cfg["parms"].get("in_gain"), "ckpt_prune", bool(A.ckpt_prune_ok))
    if A.dry_run:
        log("dry-run: g45_chain.py", p)
        return "dry", None
    t0 = time.time()
    subprocess.run([sys.executable, GC.TOOLS + "/g45_chain.py", p], cwd=GC.TOOLS)
    newer = lambda n: os.path.exists(os.path.join(rd, n)) and os.path.getmtime(os.path.join(rd, n)) >= t0 - 1
    for n, st in (("STOP_DISK.txt", "disk"), ("STOPPED_CRASH.txt", "crash"), ("STOPPED_NO_CKPT.txt", "nockpt"), ("STOPPED_GUARD.txt", "guard"),
                  ("STOPPED_MAX_HOURS.txt", "cut")):
        if newer(n):
            stop("%s：計算が最後まで進まなかった（%s：%s）。原因を見てから %s で続きから走らせる" % (
                name, st, open(os.path.join(rd, n), encoding="utf8").read().strip(),
                cmd("" if name == "V1" else "--only " + name, "preview" if name == "V1" else None)))
    try:
        import g45_analyze as GA
        ana = GA.analyze(name, A.root)
    except Exception as e:
        stop("%s：解析が止まった（%s）。記録を見る" % (name, repr(e)[:300]))
    return ("online" if newer("STOPPED_ONLINE.txt") else "done"), ana


def v1_report(ana):
    """§6.9 の関門 (a)〜(d)、§6.8 の前提、V3 の条件、平均の水面の読み。runs/V1_RESULT_ja.md。返り値は状態に入れる関門の dict。"""
    plan = GC.load_plan()
    n3 = ana.get("N3_summary") or {}
    fc = ana.get("focus_crest_max") or {}
    a = not ana.get("N2_guard")
    b = bool(n3.get("within_preview_090_110"))
    d = bool((fc.get("eta") if fc.get("eta") is not None else -1e9) >= D_GATE)
    pre = ana.get("layout_precondition_6_8") or {}
    on = ana.get("onset")
    tb = plan["criteria"]["reproduction"]["bands"]["F45"]["tBP_s"]
    t_on = on.get("t") if on else None
    v3 = bool(t_on is not None and not (tb[0] <= t_on <= tb[1]))
    v3_why = ("巻き始め %.2f s が %.2f〜%.2f s の%s" % (t_on, tb[0], tb[1], "外：合意の後、M1 の前に V3（立ち上げの感度、記録だけ）を走らせる" if v3 else "中：V3 は走らせない")
              if t_on is not None else "巻き始めがないので、V3 の条件（巻き始めの時刻が ±5 % の外）は決まらない：V3 は走らせない（record_ja.md の読み方 R28）")
    cost = ana.get("cost") or {}
    ml = ana.get("mean_level_series") or {}
    sr = ana.get("second_reading_mean_level") or {}
    g = dict(a=a, b=b, d=d, pre=bool(pre.get("amp_within_3pct") and pre.get("phase_within_010")),
             n3_min=n3.get("ratio_min"), n3_max=n3.get("ratio_max"), focus_eta=fc.get("eta"), stops=ana.get("stops"),
             tBP=t_on, v3_needed=v3, v3_why_ja=v3_why)
    nxt = []
    if a and b and d:
        nxt.append("関門 (a)・(b)・(d) は入った。人が V1（この文書・動画・ana.json）を見た後：`%s`（V1 の確かめ）。"
                   "本番は指導教員の合意の後に `%s`" % (cmd("--confirm v1", "preview"), cmd("", "agreed")))
    if not b:
        nxt.append("関門 (b) が外れた。計画 §6.9：帯の作り（VEX、表、壁のなだらかさ、利得の入れ方）が煙の試しと同じかを調べ、作りの誤りだけを直して "
                   "V1 を走らせ直す。利得は V1 の値から決め直さない。直した所を record_ja.md に書く。走らせ直す言葉：`%s`"
                   % cmd('--rerun-v1 "<直した所と record_ja.md の節>"', "preview"))
    if not d:
        nxt.append("関門 (d) が外れた。M1 を始めずに記録を調べて伺う（計画 §6.9）")
    if not a:
        nxt.append("関門 (a) が外れた。記録を見て伺う")
    lf = ml.get("liquid_volume_change") or {}
    r3 = lambda v: round(v, 3) if isinstance(v, float) else v
    pc = ml.get("particle_count_change") or {}
    lines = ["# V1 の結果（粗い下見、粒子 0.5 m。再現の判定には使わない）", "",
             "- 解析：`Unity/Build/FLIP45/%s/V1/ana.json`（%s）。立ち上げ %s" % (A.root, ana.get("date"), ana.get("ramp")),
             "- (a) 見張りと止まりなく走りきった：%s（%s）" % ("入った" if a else "外れた", ana.get("stops")),
             "- (b) N3 の振幅の比 0.90〜1.10：%s（最小 %s・最大 %s）" % ("入った" if b else "外れた", r3(n3.get("ratio_min")), r3(n3.get("ratio_max"))),
             "- (c) 1 コマの秒（全部の記録の中央値）：%s s、粒子の最大 %s、主メモリーの最大 %s GiB、起動 %s 回・%s 時間。"
             "本番の時間は崩れの前の中央値と崩れの後の倍で出し直して利用者に伝える（計画 §6.9 (c)・§7.1）" % (
                 r3(cost.get("s_per_frame_median")), cost.get("particles_max"), cost.get("rss_peak_gb"), cost.get("launches"),
                 None if cost.get("wall_total_h") is None else round(cost["wall_total_h"], 2)),
             "- (d) 焦点の近く（x 150〜300 m）の y = 0 の頂が壁ありの線形の最大の 0.8 倍（5.1 m）以上：%s（%s）" % ("入った" if d else "外れた", json.dumps(fc, ensure_ascii=False)),
             "- N10（伝わる間の減り、粗い）：%s" % r3((ana.get("N10") or {}).get("ratio_x130_over_x40")),
             "- §6.8 の前提（x 130 m の振幅 ±3 %%・位相 ±0.10 rad）：振幅 %s・位相 %s → %s" % (
                 pre.get("amp_within_3pct"), pre.get("phase_within_010"),
                 "V2 を走らせて窓を比べる" if g["pre"] else "V2 を走らせず並び B"),
             "- 巻き始め（粗い）：%s" % json.dumps(on, ensure_ascii=False, default=float)[:600],
             "- V3 の条件（計画 §2）：%s" % v3_why,
             "", "## 平均の水面（記録。判定にしない。record_ja.md §8 の 2・check_ja.md §3.2）", "",
             "- Ac の二つ目の読み（%s の前の 1 周期 %s s の内側の箱の周期の平均の水面から）：N1 から %s m、二つ目 %s m、偏り %s m（割合 %s）。"
             "H1 は頂と後ろの谷が同じだけ動くので変わらない（%s m）" % (
                 sr.get("kind"), sr.get("window"), r3(sr.get("Ac_N1_m")), r3(sr.get("Ac_second_m")), r3(sr.get("Ac_bias_m")), r3(sr.get("Ac_bias_rel")),
                 r3(sr.get("H1_N1_m"))),
             "- 箱の全部の周期の平均の水面の上がり：最後の周期 %s m、最大 %s m、最大の 90 %% に届いた周期 %s s" % (
                 ml.get("rise_whole_box_last_period_m"), ml.get("rise_whole_box_max_period_m"), ml.get("rise_reaches_90pct_in_period")),
             "- 出所の読み：%s（前線の速さ %s m/s）" % (ml.get("origin_hint_ja"), (ml.get("rise_front") or {}).get("speed_m_s")),
             "- 水の体積の変わり（R6、所の面積で割った高さ m。箱の全部・入口の帯・内側・横の帯・出口の帯）：%s。粒子の数の変わりの割合：%s" % (
                 json.dumps(lf.get("dV_as_level_m"), ensure_ascii=False), json.dumps(pc.get("dN_over_N"), ensure_ascii=False)),
             "- 毎コマの値：`Unity/Build/FLIP45/%s/V1/mean_level_series.npz`、周期ごとの値：ana.json の mean_level_series.per_period" % A.root,
             "", "## 次", ""] + ["- " + x for x in nxt] + [""]
    open(os.path.join(RUNS, "V1_RESULT_ja.md"), "w", encoding="utf8").write("\n".join(lines))
    return g


def rerun_v1():
    """関門が外れた V1 を、帯の作りを直した後に走らせ直す用意：前の V1 の置き場所と結果を V1_try<n>_<日時> へ移し（消さない）、状態を戻す。"""
    if not S.get("V1_done"):
        stop("--rerun-v1：V1 がまだ終わっていないので、走らせ直す物がない（--preview だけで V1 を走らせる）")
    g = S.get("V1_gate") or {}
    if g.get("a") and g.get("b") and g.get("d"):
        stop("--rerun-v1 は受けない：V1 の関門 (a)・(b)・(d) は全部入っている。結果を見て入口・帯を直して走らせ直すことは計画 §6.1・§6.9 にない")
    n = len(S.get("V1_history", [])) + 1
    tag = "V1_try%d_%s" % (n, time.strftime("%Y%m%d_%H%M"))
    moved = {}
    for src, dst in (("V1", tag), ("V1_RESULT_ja.md", tag + "_RESULT_ja.md")):
        ps, pd = os.path.join(RUNS, src), os.path.join(RUNS, dst)
        if os.path.exists(ps):
            os.rename(ps, pd); moved[src] = dst
    if os.path.exists(os.path.join(RUNS, "SEQ_DECISION.json")) and not S.get("V2_done"):
        os.rename(os.path.join(RUNS, "SEQ_DECISION.json"), os.path.join(RUNS, tag + "_SEQ_DECISION.json")); moved["SEQ_DECISION.json"] = tag + "_SEQ_DECISION.json"
    S.setdefault("V1_history", []).append(dict(at=time.strftime("%Y-%m-%d %H:%M:%S"), why=A.rerun_v1, V1_done=S.get("V1_done"), V1_gate=g,
                                                confirmed=(S.get("confirmed") or {}).get("v1"), moved=moved))
    for k in ("V1_done", "V1_gate", "seq"):
        S.pop(k, None)
    (S.get("confirmed") or {}).pop("v1", None)
    save_state(S)
    open(os.path.join(RUNS, "V1_RERUN_LOG.txt"), "a", encoding="utf8").write("%s V1 を走らせ直す（%s）。前の V1 は %s へ移した（消していない）\n" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), A.rerun_v1, json.dumps(moved, ensure_ascii=False)))
    log("rerun V1:", A.rerun_v1, "moved", moved)


def run_v2_and_pause():
    st, ana = run_stage("V2")
    import g45_resolution as GR
    dec = GR.window_decision(A.root)
    S["V2_done"] = time.strftime("%Y-%m-%d %H:%M:%S"); S["seq"] = dec["sequence"]; save_state(S)
    pause("V2 が終わった（窓の決め：並び %s）。runs/SEQ_DECISION.json を人が見る" % dec["sequence"], cmd("--confirm v2"))


def seq_b_without_v2():
    S["seq"] = "B"; save_state(S)
    json.dump(dict(sequence="B", why_ja="V1 が §6.8 の前提を満たさなかったので V2 を走らせず並び B"), open(os.path.join(RUNS, "SEQ_DECISION.json"), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)


try:
    if A.preview and not A.agreed:
        if A.rerun_v1:
            rerun_v1()
        if not S.get("V1_done"):
            st, ana = run_stage("V1")
            if st == "dry":
                pause("dry-run：V1 の設定を書いた（走らせていないので V1 の結果はなく、--confirm v1 はまだ受けない）", "（dry-run の終わり）")
            g = v1_report(ana)
            S["V1_done"] = time.strftime("%Y-%m-%d %H:%M:%S"); S["V1_gate"] = g; save_state(S)
            why = v1_gate_problem(S)
            if why:
                stop("V1 が終わった。runs/V1_RESULT_ja.md を人が見る。" + why)
            pause("V1 が終わった。runs/V1_RESULT_ja.md を人が見る（§6.9）", cmd("--confirm v1"))
        why = v1_gate_problem(S)
        if why:
            stop(why)
        if not v1_confirmed(S):
            pause("V1 の結果（runs/V1_RESULT_ja.md）を人が見た確かめがまだ", cmd("--confirm v1"))
        if not A.user_ok_05:
            pause("V1 の確かめの後。V2・V1h・V4 を合意の前に走らせるには利用者の許しが要る（計画 §12 の 2）",
                  cmd('--user-ok-05 "<利用者の言葉と日時>"', "preview"))
        if S["V1_gate"].get("pre") and not S.get("V2_done"):
            run_v2_and_pause()
        if not S["V1_gate"].get("pre") and not S.get("seq"):
            seq_b_without_v2()
        if S.get("V2_done") and "v2" not in (S.get("confirmed") or {}):
            pause("V2 の結果（runs/SEQ_DECISION.json）を人が見た確かめがまだ", cmd("--confirm v2"))
        for nm in ("V1h", "V4"):
            if not S.get(nm + "_done"):
                run_stage(nm); S[nm + "_done"] = time.strftime("%Y-%m-%d %H:%M:%S"); save_state(S)
        log("preview stages done（合意の後は --agreed で本番）")
        sys.exit(0)
    # ---------------------------------------------------------------- 本番（合意の後）
    why = v1_gate_problem(S)                      # V1 の関門 (a)・(b)・(d)（dry-run でも見る）
    if why:
        stop(why)
    if not v1_confirmed(S):
        pause("V1 の結果（runs/V1_RESULT_ja.md）を人が見た確かめ（--confirm v1）がないので、V1 の後の段（M1 から後を含む）を始めない（計画 §6.9・§10.1）",
              cmd("--confirm v1"))
    seq = S.get("seq")
    if seq is None:
        if os.path.exists(os.path.join(RUNS, "SEQ_DECISION.json")):
            seq = json.load(open(os.path.join(RUNS, "SEQ_DECISION.json"), encoding="utf8"))["sequence"]
        elif not S["V1_gate"].get("pre"):
            seq_b_without_v2(); seq = "B"
        elif not S.get("V2_done"):
            run_v2_and_pause()                     # 計画 §2：V2 は合意の後の最初（V1 が前提を満たした時だけ）。終わったら止まる
        else:
            stop("並び A・B がまだ決まっていない（V2 の後の SEQ_DECISION.json がない。計画 §6.8）")
    if S.get("V2_done") and "v2" not in (S.get("confirmed") or {}):
        pause("V2 の結果（runs/SEQ_DECISION.json）を人が見た確かめがまだ", cmd("--confirm v2"))
    order = [s for s in SEQ_A if NAME[seq][s]]
    if S["V1_gate"].get("v3_needed") and not S.get("V3_done"):
        order = ["V3"] + order                      # 計画 §2：V1 の巻き始めの時刻が ±5 % の外の時だけ、M1 の前（記録だけ）
    if A.frm:
        if A.frm not in order:
            stop("--from %s は並び %s のこの時の段にない（%s）" % (A.frm, seq, " ".join(order)))
        order = order[order.index(A.frm):]
    if A.only:
        if A.only not in NAME[seq] or not NAME[seq][A.only] or A.only == "V2":
            stop("--only %s は使えない（並び %s の段：%s。V2 は並びが決まる前に自分で走る）" % (A.only, seq, " ".join(k for k in NAME[seq] if NAME[seq][k] and k != "V2")))
        order = [A.only]
    for st_name in order:
        name = NAME[seq][st_name]
        if S.get(name + "_done") and not A.only:
            continue
        if st_name == "M1h" and "m1" not in (S.get("confirmed") or {}):
            pause("M1 の後の人の確かめ（計画 §8：1 時間）。M1 の解析 runs/%s/ana.json を見る" % NAME[seq]["M1"], cmd("--confirm m1"))
        over = None
        if st_name == "M1h" and A.dry_run:
            over = dict(from_ckpt=dict(run=NAME[seq]["M1"], frame=None, why="dry-run：M1 の解析の後に決まる"))
        elif st_name == "M1h":
            m1 = json.load(open(os.path.join(RUNS, NAME[seq]["M1"], "ana.json"), encoding="utf8"))
            if not m1.get("onset"):
                stop("M1 に巻き始めがないので M1h の始めが決まらない（計画 §2）")
            k, why = K.start_for_m1h(os.path.join(RUNS, NAME[seq]["M1"]), m1["onset"]["t"], m1["t_off"])
            if k is None:
                stop("M1h の始めの途中保存がない（%s）" % why)
            from_ck = dict(run=NAME[seq]["M1"], frame=int(k), why=why)
            over = dict(from_ckpt=from_ck, f_start=int(k) + 1)
        st, ana = run_stage(name, overrides=over)
        S[name + "_done"] = time.strftime("%Y-%m-%d %H:%M:%S"); save_state(S)
        if st_name == "M1":
            pause("M1 が終わった。解析 runs/%s/ana.json と動画を人が見る（計画 §8）" % name, cmd("--confirm m1"))
        if st_name == "X60":
            log("最初の報告に入れる計算が終わった（計画 §8）")
    log("queue end")
except SystemExit:
    raise
except Exception as e:
    stop("思わない誤り：%s\n%s" % (repr(e)[:300], traceback.format_exc()[-1500:]))
