# -*- coding: utf-8 -*-
"""FLIP44：本番の計算を計画 plan_ja.md §7 の並びで続けて走らせる（py -3.10）。指導教員の合意の後だけ使う。
並び：PR1 → PR2 →（§3.3 (a) の決まりで選ぶ → 人が見て続ける言葉を打つまで待つ。両方外れたら PR3 → もう一度待つ）→ SH → B35S → B45S → RP → 表。
  - 起動は --agreed "<合意の日時と場所>" がない限りしない（合意の前に本番を走らせないため）。合意の記録は runs/AGREED.txt に足す。
  - 各計算は g44_chain.py（30 分以下の起動を途中保存でつなぐ、G: の空きの見張り、止める決まり）。
  - 計算の後に g44_analyze.py（下見・形の本番・風）・g44_repeat.py（繰り返し）・g44_wind_check.py（風）を走らせる。
  - 選びの後で止まる（2026-10-12 確かめ F5 の直し。計画 §7 の「選び 1 時間」）：runs/SELECT_RESULT_ja.md に選びの結果を書き、
    runs/QUEUE_PAUSE.txt に続ける言葉を書いて終わる（終わりのコード 3）。続ける言葉：
      py -3.10 g44_queue.py --agreed "<同じ合意>" --confirm-select <PR1|PR2|PR3>
    （<...> は SELECT_RESULT_ja.md の choice と同じでないと受け付けない。違う物を選ぶのは計画の外なので止めて伺う）。
    PR3 を走らせた時は、その結果を runs/PR3_RESULT_ja.md に書いてもう一度止まる。続ける言葉は --confirm-pr3。
    確かめがない限り、--from SH・--only SH でも形の本番は始めない。
  - 止めて伺う所（runs/QUEUE_STOP.txt に理由と続ける言葉を書いて終わる。終わりのコード 2）：PR3 も (a) を外れた時、繰り返しの 1 回目が外れた時、
    G: の空きが 25 GB より少ない時、下見・形の本番・繰り返しの計算が途中で止まった時（打ち切りの時間・途中保存が作れない・hython が落ちた・
    水面の見張り。g44_chain.py が書く STOPPED_*.txt の理由をそのまま写す）、形の本番に巻き始めか着水がない時。
  - 風の計算（B35S・B45S）は、途中で止まっても、解析が止まっても、runs/QUEUE_REPORT.txt に理由を書いて次の段へ進む（後の段は風の計算を使わない。
    確かめ F2 の直し）。残りの差の表には、主な巻き波の巻き始めと着水が取れた風の計算だけを入れ、入れなかった物と理由を報告に書く。
  - 風なし（B0）は走らせない：煙の試し S4 で、風の道具を入れて q = 0 にした計算が、入れない計算とビット単位で同じだった（smoke_results.json の S4）。
  - はがれのない流れの形（B35N・B45N）は入れない（S6 の道具ができてから足す。計画 §4.1・§7。g44_cfg.py も wind=N を拒む）。
  2026-10-12 の 2 回目の確かめ（check/check_fixes_ja.md）の後に足した所（record_ja.md §3.2）：
  - G1：前の段の結果が要る段（SELECT・PR3・SH・B35S・B45S・RP・TABLE）は、始めにその状態を確かめ、なければ traceback でなく
    QUEUE_STOP.txt に平文の理由と続ける言葉を書いて止まる。RP と TABLE も確かめた選びが要る（SH・PR3 は前と同じく、確かめがなければ待つ）。
    思わない誤りも QUEUE_STOP.txt に書いて止まる（詳しい記録は queue_log.txt）。
  - G2：並びが作る計算の設定に途中保存の残し方（ckpt_keep。g44_ckpt.py）を足す。並びの始めに、残りの段の置き場所の見込みを
    runs/DISK_PLAN_ja.md に書き、空き − 止まる線より大きければ始めずに止まる（--disk-ok で見込みを越えても走らせる。止まる線の見張りは残る）。
  - G3：下見 3 本目の入口（p_plan_numbers.py --aim3）の終わりのコードとファイルを確かめる。--dry-run でも、凍結した道具と同じ計算で
    試しの置き場所（<root>/plan_pr3）に入口を書き（x44_aim3_dry.py）、下見 3 本目の道を最後まで通す。
  - G4：下見 1・2 の解析が止まっても次の段へ進み、選びの所で理由を書いて待つ（続ける言葉は --from SELECT。解析だけやり直す）。
  - G5：解析が「主な頂は記録の始めですでに巻いていた」と書いた時は、報告に写す。
  - G8：RP は、この起動より新しい止まりのファイルだけで「1 回目が外れた」と読む。runs/RP に前の試みの途中保存があれば、--resume-rp が
    ない限り続きから走らせない（前の試みが 1 回目の外れで止まっていた時は --resume-rp でも走らせない）。
  - 夜の間に PC が眠らないように、並びが動いている間だけ SetThreadExecutionState を頼む（g44_chain.py も同じ）。電源の設定は変えない。
  2026-10-12 の 3 回目の確かめ（check/check_fixes2_ja.md）の後に足した所（record_ja.md §3.3）：
  - H1：形の本番の途中保存は、計算の間は 1 個も消さない。解析が巻き始め t_on を決めた後に g44_ckpt.prune_after_onset で、風の計算の始め
    （t_on − 3 s より前の最後の途中保存。計画 §4.1）・f_w・いちばん新しい物を残して消し、QUEUE_REPORT.txt に 1 行書く。始めの途中保存が
    計画どおりにない時と、巻き始めが主な頂の道の最初のコマで読まれた時は、1 個も消さずに理由を書く。
    風の計算の段は g44_ckpt.wind_start で始めを選び、計画の始めがない時は理由（いつ・なぜ消したか、作っていない、など）を報告に書く。
  - H7：消すのは、帳面の made の origin が queue の物（並びの chain が作った物）だけ（g44_ckpt・g44_chain）。
使い方：py -3.10 g44_queue.py --agreed "2026-10-13 18:00 Discord" [--from <段の名前>] [--only <段の名前>] [--confirm-select <PR1|PR2|PR3>] [--confirm-pr3]
        [--resume-rp] [--disk-ok]
  段の名前：PR1 PR2 SELECT PR3 SH B35S B45S RP TABLE
  試しの時だけ：--root <FLIP44 の下の置き場所>（既定 runs）、--dry-run（計算と解析を走らせず、走らせる物を書くだけ。選びと、下見 3 本目の入口は走らせる）
"""
import sys, os, json, subprocess, time, glob, shutil, traceback, ctypes

TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44"
B44 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
ROOT = "runs"
RUNS = B44 + "/runs"
DRY = False
PY = [sys.executable]
sys.path.insert(0, TOOLS)
import g44_cfg as C
import g44_ckpt as K

STAGES = ["PR1", "PR2", "SELECT", "PR3", "SH", "B35S", "B45S", "RP", "TABLE"]
HEAVY = ("PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP")
EXIT_STOP, EXIT_PAUSE = 2, 3
AGREED = ""
ARGS = []


def setup(root, dry=False):
    global ROOT, RUNS, DRY
    ROOT = root; RUNS = os.path.join(B44, root).replace("\\", "/"); DRY = dry
    os.makedirs(RUNS, exist_ok=True)
    # 下見 3 本目の入口の置き場所：本番は凍結した計画の plan/（p_plan_numbers.py --aim3 が書く）。dry-run は試しの置き場所（G3）
    C.PR3_DIR = (RUNS + "/plan_pr3") if dry else C.PLAN_DIR


def sprint(msg):
    """標準出力が cp932 の時（Git Bash やファイルへ流した時）も止まらない表示（G7 と同じ）。"""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, "replace").decode(enc, "replace"), flush=True)


def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    sprint(msg)
    open(os.path.join(RUNS, "queue_log.txt"), "a", encoding="utf8").write(msg + "\n")


def cmd_line(extra):
    return 'py -3.10 Tools/GWWaveGen/flip44/g44_queue.py --agreed "%s" %s%s' % (AGREED, extra, (" --root " + ROOT) if ROOT != "runs" else "")


def stop(why):
    open(os.path.join(RUNS, "QUEUE_STOP.txt"), "a", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + why + "\n")
    log("STOP", why)
    sys.exit(EXIT_STOP)


def pause(why, cont):
    txt = "%s %s\n  続ける言葉：%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), why, cont)
    open(os.path.join(RUNS, "QUEUE_PAUSE.txt"), "a", encoding="utf8").write(txt)
    log("PAUSE", why, "| 続ける言葉：", cont)
    sys.exit(EXIT_PAUSE)


def report(msg):
    open(os.path.join(RUNS, "QUEUE_REPORT.txt"), "a", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    log("REPORT", msg)


def run(cmd):
    """計算・解析など（--dry-run では走らせない）。"""
    log("run", " ".join(cmd))
    if DRY:
        return 0
    r = subprocess.run(cmd, cwd=TOOLS)
    return r.returncode


def run_now(cmd):
    """記録を読むだけの短い道具（--dry-run でも走らせる）。出力を queue_log.txt に写し、(終わりのコード, 最後の行) を返す。"""
    log("run", " ".join(cmd))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, cwd=TOOLS, capture_output=True, env=env)
    out = (r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")).strip()
    if out:
        open(os.path.join(RUNS, "queue_log.txt"), "a", encoding="utf8").write(out[-6000:] + "\n")
    lines = [l for l in out.splitlines() if l.strip()]
    return r.returncode, (lines[-1][:400] if lines else "")


def keep_awake():
    try:
        f = ctypes.windll.kernel32.SetThreadExecutionState
        f.argtypes = [ctypes.c_uint]; f.restype = ctypes.c_uint
        return bool(f(0x80000000 | 0x00000001))      # ES_CONTINUOUS | ES_SYSTEM_REQUIRED（この処理が終わると元に戻る）
    except Exception:
        return False


def _newer(p, t0):
    return os.path.exists(p) and os.path.getmtime(p) >= t0 - 1.0


def chain_result(rid, f_end, t0=0.0):
    """g44_chain.py の後の状態。返り値 (状態, 進んだコマ, 理由の文)。状態：done（f_end まで）・rule（止める決まり）・online（計算の中の着水の読み）・
    cut（打ち切りの時間）・nockpt（途中保存が作れない）・crash・refused（g44_run.py が設定を拒んだ）・disk・stopfile（利用者の STOP）・
    short（ほかの理由で f_end の前に終わった）。STOPPED_*.txt は t0（この chain を始めた時刻）より新しい物だけを読む（前の試みの古いファイルで誤らないため）。"""
    rd = os.path.join(RUNS, rid)
    recs = sorted(glob.glob(os.path.join(rd, "run_c*.json")))
    txt = lambda n: open(os.path.join(rd, n), encoding="utf8").read().strip()
    if _newer(os.path.join(rd, "STOP_DISK.txt"), t0):
        return "disk", None, txt("STOP_DISK.txt")
    if not recs:
        return "crash", 0, txt("STOPPED_CRASH.txt") if _newer(os.path.join(rd, "STOPPED_CRASH.txt"), t0) else "起動の記録 run_c*.json がない"
    last = json.load(open(recs[-1], encoding="utf8"))
    done = int(last.get("f_end_done") or 0)
    st = last.get("stopped") or ""
    if _newer(os.path.join(rd, "STOPPED_BY_RULE.txt"), t0):
        return "rule", done, txt("STOPPED_BY_RULE.txt")
    if st.startswith("touchdown_online"):
        return "online", done, st
    if done >= f_end:
        return "done", done, "%d コマまで走った" % done
    for n, s in (("STOPPED_MAX_HOURS.txt", "cut"), ("STOPPED_NO_CKPT.txt", "nockpt"), ("STOPPED_CRASH.txt", "crash"), ("STOPPED_REFUSED.txt", "refused")):
        if _newer(os.path.join(rd, n), t0):
            return s, done, txt(n)
    if os.path.exists(os.path.join(rd, "STOP")):
        return "stopfile", done, "利用者の STOP のファイルで止まった"
    return "short", done, "%d コマ目で止まった（最後の起動の記録：%s）" % (done, st or "理由の記録なし")


def chain(cfg):
    rid = cfg["run_id"]
    os.makedirs(os.path.join(RUNS, rid), exist_ok=True)
    p = os.path.join(RUNS, rid, "cfg_queue.json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if DRY:
        log("dry-run: g44_chain.py", p, "（max_hours %.2f h、f_end %d、ckpt_keep %s）" % (
            cfg.get("max_hours", 0), cfg["f_end"], (cfg.get("ckpt_keep") or {}).get("mode")))
        return "dry", None, "dry-run"
    t0 = time.time()
    run(PY + [TOOLS + "/g44_chain.py", p])
    return chain_result(rid, int(cfg["f_end"]), t0)


def chain_or_stop(cfg, stage, cont=None):
    """下見・形の本番・繰り返し：後の段がこの計算を使うので、途中で止まったら理由を書いて止まる。"""
    state_, done, why = chain(cfg)
    if state_ in ("done", "rule", "online", "dry"):
        return state_
    stop("%s：計算が最後まで進まなかった（%s）。%s。原因を見てから、%s で途中保存の続きから走らせ直す" % (
        cfg["run_id"], state_, why, cmd_line(cont or ("--from " + stage))))


def make_cfg(kind, rid, kw, stage):
    """g44_cfg.kind_cfg。設定を作れない時（拒み・足りない入口）は traceback でなく理由を書いて止まる（G1）。"""
    try:
        return dict(C.kind_cfg(kind, rid, dict(kw)), out_root=ROOT)
    except SystemExit as e:
        stop("%s：計算の設定を作れなかった（%s）" % (stage, e))
    except Exception as e:
        stop("%s：計算の設定を作れなかった（%s）" % (stage, repr(e)[:300]))


def analyze_soft(rid):
    """解析。返り値 (ana, None) か (None, 理由の文)。--dry-run では、ある ana.json を読むだけ。"""
    p = os.path.join(RUNS, rid, "ana.json")
    if DRY:
        log("dry-run: g44_analyze.py", rid, ROOT)
        return (json.load(open(p, encoding="utf8")), None) if os.path.exists(p) else (None, "dry-run：%s/%s/ana.json がない" % (ROOT, rid))
    t0 = time.time()
    rc, last = run_now(PY + [TOOLS + "/g44_analyze.py", rid, ROOT])
    if rc != 0:
        return None, "g44_analyze.py の終わりのコード %d：%s" % (rc, last)
    if not _newer(p, t0):
        return None, "g44_analyze.py は終わったが %s/%s/ana.json が新しくない" % (ROOT, rid)
    return json.load(open(p, encoding="utf8")), None


def state():
    p = os.path.join(RUNS, "queue_state.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def save_state(s):
    json.dump(s, open(os.path.join(RUNS, "queue_state.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


# ------------------------------------------------------------------ 前の段の状態の確かめ（G1）
def need_select(S, stage):
    """確かめた選びがなければ止まる（SH・PR3 は前と同じく待つ）。返り値は select。"""
    sel = S.get("select") or {}
    if not sel.get("choice"):
        stop("%s：選びの結果（%s/queue_state.json の select）がない。先に下見を走らせて選ぶ（下見が終わっていれば選びから）：%s" % (
            stage, ROOT, cmd_line("--from SELECT")))
    cont = cmd_line("--confirm-select %s" % sel["choice"])
    if not sel.get("confirmed"):
        why = "%s：選びの結果（choice %s、%s/SELECT_RESULT_ja.md）がまだ確かめられていないので始めない" % (stage, sel["choice"], ROOT)
        if stage in ("PR3", "SH"):
            pause(why, cont)
        stop(why + "。見てから：" + cont)
    if stage != "PR3" and sel["choice"] == "PR3" and not sel.get("pr3_confirmed"):
        why = "%s：下見 3 本目の結果（%s/PR3_RESULT_ja.md）がまだ確かめられていないので始めない" % (stage, ROOT)
        if stage == "SH":
            pause(why, cmd_line("--confirm-pr3"))
        stop(why + "。見てから：" + cmd_line("--confirm-pr3"))
    return sel


def need_sh(S, stage):
    sh = S.get("SH") or {}
    if not (sh.get("onset") or {}).get("t") or not (sh.get("touchdown") or {}).get("t") or sh.get("still") is None:
        stop("%s：形の本番の結果（%s/queue_state.json の SH：主な巻き波の巻き始め・着水・静かな水面）がない。先に形の本番を走らせて読む：%s" % (
            stage, ROOT, cmd_line("--from SH")))
    return sh


# ------------------------------------------------------------------ 置き場所の見込み（G2）
def disk_check(todo, S, disk_ok):
    heavy = [s for s in todo if s in HEAVY]
    if not heavy:
        return
    sel = S.get("select") or {}; sh = S.get("SH") or {}
    stg = [s for s in heavy if s != "PR3" or sel.get("choice") in (None, "PR3")]
    p = os.path.join(RUNS, "DISK_PLAN_ja.md")
    stop_gb = float(C.plan()["criteria"]["disk_stop_free_GB"])
    free = shutil.disk_usage("G:/").free / 2**30
    try:
        d = K.disk_plan(stg, choice=sel.get("choice"), sh_onset=(sh.get("onset") or {}).get("t"), sh_td=(sh.get("touchdown") or {}).get("t"))
    except Exception as e:
        open(p, "w", encoding="utf8").write("# 置き場所の見込み（%s）\n\n- 見込みを出せなかった（%s）。止まる線（%.0f GiB）の見張りは残る。空き %.1f GiB\n" % (
            time.strftime("%Y-%m-%d %H:%M"), repr(e)[:300], stop_gb, free))
        log("disk plan failed", repr(e)[:300])
        return
    open(p, "w", encoding="utf8").write(K.plan_md(d, free, stop_gb, ROOT))
    log("disk plan: need %.1f GiB (keep %.1f + peak %.1f), without pruning %.1f GiB, free %.1f GiB, stop line %.0f GiB -> %s" % (
        d["total_need_gb"], d["total_keep_gb"], d["peak_extra_gb"], d["total_all_gb"], free, stop_gb, p))
    if d["total_need_gb"] > free - stop_gb:
        if disk_ok:
            report("置き場所の見込み %.1f GiB が、空き %.1f GiB − 止まる線 %.0f GiB を越えるが、--disk-ok で始めた（止まる線の見張りは残る）" % (
                d["total_need_gb"], free, stop_gb))
        else:
            stop("置き場所の見込み %.1f GiB（%s）が、G: の空き %.1f GiB − 止まる線 %.0f GiB を越える。G: を空けてから同じ言葉で走らせる。"
                 "見込みを越えても走らせるなら、言葉に --disk-ok を足す（止まる線で止まる見張りは残る）" % (d["total_need_gb"], p, free, stop_gb))


# ------------------------------------------------------------------ 選びの結果（人が見る物）
def _fmt_on(o):
    if not o:
        return "なし"
    return "%.2f s・造波板から %.1f m・η_c %.2f m・H %.2f m" % (o["t"], o["xc_rel"], o["eta_c"], o["H"] if o.get("H") is not None else float("nan"))


def write_select_result(sel):
    L = ["# 選びの結果（計画 §3.3 (a)。g44_queue.py が書いた。%s）" % time.strftime("%Y-%m-%d %H:%M"), "",
         "- 決まり：%s" % sel.get("rule_ja", ""), "- 道具の選び（choice）：**%s**" % sel["choice"]]
    if sel["choice"] == "PR3":
        L.append("- 下見 3 本目の狙い：%s m（%s）" % (sel.get("PR3_aim_m"), sel.get("PR3_command", sel.get("note_ja", ""))))
    L += ["", "| 下見 | 入った | 1 場所 | 2 前へ巻く | 3 一つだけ | 主な巻き波の巻き始め | 着水 | 除いた頂（主な巻き波の崩れの一部） | 除かなかったほかの巻き始め |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for k in ("PR1", "PR2"):
        a = sel.get(k) or {}
        ap = os.path.join(RUNS, k, "ana.json")
        ana = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
        td = ana.get("touchdown")
        oth = a.get("other_onsets") or []
        piece = ["%.1f s・%.0f m（%d コマ目に %.0f m で生まれた）" % (o["t"], o["xc_rel"], o["born_frame"], o["born_x_rel"]) for o in oth if o.get("piece_of_main")]
        rest = ["%.1f s・%.0f m" % (o["t"], o["xc_rel"]) for o in oth if not o.get("piece_of_main")]
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            k, a.get("pass_"), a.get("c1_onset_in_window"), a.get("c2_plunges_forward"), a.get("c3_one_plunger"), _fmt_on(ana.get("onset")),
            ("%.2f s（%s）" % (td["t"], td["by"])) if td else "なし", "、".join(piece) or "なし", "、".join(rest) or "なし"))
    L += ["", "## 続ける前に見ること（計画 §7 の選び 1 時間。確かめ F5）",
          "- 主な巻き波が、崩れた水の跳ね上がりではなく、群の中で最も高い頂か（`%s/<下見>/ana.json` の main の path）。" % ROOT,
          "- 除いた頂（計画の読み方 13）が、主な巻き波の崩れの一部で、群のほかの波ではないか。",
          "- 断面の絵：`py -3.10 Tools/GWWaveGen/flip44/g44_video.py <下見> Unity/Build/FLIP44/report/video --root=%s --only=crest`" % ROOT,
          "", "## 続ける言葉", "", "```", cmd_line("--confirm-select %s" % sel["choice"]), "```",
          "", "- choice と違う下見を選ぶのは計画の外なので、この言葉では受け付けない。止めて伺う。"]
    p = os.path.join(RUNS, "SELECT_RESULT_ja.md").replace("\\", "/")
    open(p, "w", encoding="utf8").write("\n".join(L) + "\n")
    return p


def write_pr3_result(an):
    a = an.get("selection_a") or {}
    L = ["# 下見 3 本目の結果（g44_queue.py が書いた。%s）" % time.strftime("%Y-%m-%d %H:%M"), "",
         "- (a) に入った：%s（1 場所 %s・2 前へ巻く %s・3 一つだけ %s）" % (a.get("pass_"), a.get("c1_onset_in_window"), a.get("c2_plunges_forward"), a.get("c3_one_plunger")),
         "- 主な巻き波の巻き始め：%s" % _fmt_on(an.get("onset")),
         "- 除いた頂：%s" % ("、".join("%.1f s・%.0f m" % (o["t"], o["xc_rel"]) for o in a.get("other_onsets") or [] if o.get("piece_of_main")) or "なし"),
         "", "## 続ける言葉", "", "```", cmd_line("--confirm-pr3"), "```"]
    p = os.path.join(RUNS, "PR3_RESULT_ja.md").replace("\\", "/")
    open(p, "w", encoding="utf8").write("\n".join(L) + "\n")
    return p


# ------------------------------------------------------------------ 段ごと
def stage_pr(st, S):
    S.pop("select", None); S.setdefault("ana_fail", {}).pop(st, None); save_state(S)        # 下見を走らせ直したら、前の選びは使わない
    cfg = make_cfg(st, st, {}, st)
    cfg["ckpt_keep"] = K.keep_policy("PR")
    chain_or_stop(cfg, st)
    an, why = analyze_soft(st)
    if an is None:       # G4：解析が止まっても下見 2 へ進み、選びの所で待つ
        S["ana_fail"][st] = why; S[st] = None; save_state(S)
        report("%s：解析が止まった（%s）。計算は終わっているので次の段へ進み、選びの所で止めて伺う" % (st, why))
        return
    S[st] = an.get("selection_a"); save_state(S)


def stage_select(S):
    bad = []
    for k in ("PR1", "PR2"):
        rdk = os.path.join(RUNS, k)
        ap = os.path.join(rdk, "ana.json")
        failed = (S.get("ana_fail") or {}).get(k)
        if failed or not os.path.exists(ap):
            if not os.path.exists(ap) and not glob.glob(os.path.join(rdk, "hf_c*.npz")):
                stop("選び：下見 %s の記録（%s/%s）がない。先に下見を走らせる：%s" % (k, ROOT, k, cmd_line("--from " + k)))
            an, why = analyze_soft(k)
            if an is None:
                bad.append("%s（%s）" % (k, why)); continue
            S.setdefault("ana_fail", {}).pop(k, None); S[k] = an.get("selection_a"); save_state(S)
            if failed:
                report("%s：解析をやり直して通った（前の理由：%s）" % (k, failed))
    if bad:
        pause("下見の解析が止まったので選べない：%s。記録か解析の道具を見て直してから、選びからやり直す（下見の計算は走らせ直さない。確かめ G4）" % "；".join(bad),
              cmd_line("--from SELECT"))
    rc, last = run_now(PY + [TOOLS + "/g44_analyze.py", "--select", "PR1", "PR2", ROOT, ROOT])     # 選びは記録を読むだけなので、--dry-run でも走らせる
    if rc != 0:
        stop("選び（g44_analyze.py --select）が止まった（コード %d：%s）" % (rc, last))
    sel = json.load(open(os.path.join(RUNS, "select.json"), encoding="utf8"))
    S["select"] = dict(choice=sel["choice"], PR3_aim_m=sel.get("PR3_aim_m"), confirmed=False, written_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    save_state(S)
    if sel["choice"] == "PR3" and sel.get("PR3_aim_m") is None:
        stop("下見 1・2 がどちらも外れ、下見 2 に巻き始めがないので狙いを直せない（計画 §3.3 (a)）")
    p = write_select_result(sel)
    pause("選びの結果（choice %s）を %s に書いた。人が見て確かめるまで先へ進まない（計画 §7 の選び 1 時間）" % (sel["choice"], p),
          cmd_line("--confirm-select %s" % sel["choice"]))


def stage_pr3(S):
    sel = need_select(S, "PR3")
    if sel.get("choice") != "PR3":
        return
    x = sel.get("PR3_aim_m")
    if x is None:
        stop("PR3：下見 3 本目の狙い（select の PR3_aim_m）がない。止めて伺う")
    aim_p = os.path.join(C.PR3_DIR, "pr3_aim%.0f.json" % float(x)).replace("\\", "/")
    if DRY:      # G3：凍結した道具と同じ計算を、試しの置き場所へ書く
        rc, last = run_now(PY + [TOOLS + "/x44_aim3_dry.py", "%g" % float(x), C.PR3_DIR])
    else:
        rc, last = run_now(PY + [TOOLS + "/p_plan_numbers.py", "--aim3", "%g" % float(x)])
    if rc != 0:
        stop("PR3：下見 3 本目の入口を作る道具（p_plan_numbers.py --aim3 %g）が止まった（コード %d：%s）。queue_log.txt を見てから、%s" % (
            float(x), rc, last, cmd_line("--from PR3")))
    try:
        a3 = json.load(open(aim_p, encoding="utf-8"))
        assert a3.get("freqs_Hz") and a3.get("amps_m") and a3.get("repeat_same_aim"), "入口の表か繰り返しの入口がない"
    except Exception as e:
        stop("PR3：下見 3 本目の入口 %s を読めない（%s）。%s" % (aim_p, repr(e)[:200], cmd_line("--from PR3")))
    log("PR3 inlet", aim_p, a3.get("name"))
    cfg = make_cfg("PR3", "PR3", {"aim": x}, "PR3")
    cfg["ckpt_keep"] = K.keep_policy("PR")
    chain_or_stop(cfg, "PR3")
    an, why = analyze_soft("PR3")
    if an is None:
        stop("PR3：下見 3 本目の解析が止まった（%s）。記録か解析の道具を見て直してから、%s（計算は途中保存の続きから。終わっていれば解析だけ）" % (
            why, cmd_line("--from PR3")))
    S["PR3"] = an.get("selection_a"); save_state(S)
    if not (an.get("selection_a") or {}).get("pass_"):
        stop("下見 3 本目も §3.3 (a) を外れた。礁の形や入口の振幅を変えるのは新しい選択なので、止めて伺う")
    p = write_pr3_result(an)
    pause("下見 3 本目の結果を %s に書いた。人が見て確かめるまで形の本番を始めない" % p, cmd_line("--confirm-pr3"))


def stage_sh(S):
    sel = need_select(S, "SH")
    ch = sel["choice"]
    ap = os.path.join(RUNS, ch, "ana.json")
    if not os.path.exists(ap):
        stop("SH：選んだ下見 %s の解析（%s/%s/ana.json）がない。%s" % (ch, ROOT, ch, cmd_line("--from SELECT")))
    pre = json.load(open(ap, encoding="utf8"))
    if not (pre.get("onset") or {}).get("t"):
        stop("SH：選んだ下見 %s の解析に主な巻き波の巻き始めがない（f_w を決められない）。止めて伺う" % ch)
    kw = {"prog": ch, "onset_pre": pre["onset"]["t"]}
    if ch == "PR3":
        kw["aim"] = sel["PR3_aim_m"]
    cfg = make_cfg("SH", "SH", kw, "SH")
    cfg["ckpt_keep"] = K.keep_policy("SH", onset_pre=pre["onset"]["t"], f_w=cfg["case"]["f_w"], Tc=C.plan()["tank"]["Tc"])
    chain_or_stop(cfg, "SH")
    an, why = analyze_soft("SH")
    if DRY and an is None:
        log("dry-run: 形の本番の記録がないので、ここで終わる")
        return "end"
    if an is None:
        stop("SH：形の本番の解析が止まった（%s）。記録か解析の道具を見て直してから、%s" % (why, cmd_line("--from SH")))
    S["SH"] = dict(onset=an.get("onset"), touchdown=an.get("touchdown"), still=an.get("still_level_offset_m")); save_state(S)
    if not an.get("onset") or not an.get("touchdown"):
        stop("形の本番に主な巻き波の巻き始めか着水がない。風の計算の始めが決まらないので止めて伺う（形の本番の途中保存は 1 個も消していない）")
    if an.get("onset_at_path_start"):
        report("SH：%s" % an["onset_at_path_start"])
        report("SH：巻き始めが主な頂の道の最初のコマで読まれた（本当の巻き始めはもっと早いかもしれない）ので、形の本番の途中保存は 1 個も消さずに"
               "全部残した（%s/SH/ckpt）。消すかは利用者が決める" % ROOT)
        S["SH"]["ckpt"] = dict(pruned="none", why="onset_at_path_start"); save_state(S)
        return
    # H1：巻き始めが決まったので、風の計算の始め・f_w・いちばん新しい物を残して消す（本番の置き場所で dry-run でない時だけ本当に消す）
    real = bool(ROOT == "runs" and not DRY and not (cfg.get("ckpt_keep") or {}).get("dry"))
    try:
        pr = K.prune_after_onset(os.path.join(RUNS, "SH"), an["onset"]["t"], f_w=cfg["case"].get("f_w"), real=real, log=log)
    except Exception as e:      # 片付けは先の段に要らないので、誤りでも止まらない（消した所までは帳面にある）
        open(os.path.join(RUNS, "queue_log.txt"), "a", encoding="utf8").write(traceback.format_exc() + chr(10))
        S["SH"]["ckpt"] = dict(error=repr(e)[:300]); save_state(S)
        report("SH：途中保存の片付け（g44_ckpt.prune_after_onset）で思わない誤りが出た（%s）。片付けをやめて先へ進む。消した物は %s/SH/ckpt_ledger.json の pruned にある"
               % (repr(e)[:200], ROOT))
        return
    S["SH"]["ckpt"] = dict(start=pr["start"], want=pr["want"], f_w=pr["f_w"], deleted=pr["deleted"], would=pr["would"], failed=pr["failed"], real=real)
    save_state(S)
    report("SH：" + pr["report_ja"])


def wind_stage(st, S):
    sel = need_select(S, st)
    sh = need_sh(S, st)
    ch = sel["choice"]
    t_on = sh["onset"]["t"]
    w = K.wind_start(os.path.join(RUNS, "SH"), t_on)      # H1：計画の始めがない時は、その理由（いつ・なぜ消したか等）も返る
    if w["start"] is None:
        report("%s：形の本番に、巻き始めの 3 s 前（%.2f s）より前の途中保存がないので走らせなかった。%s" % (st, w["t_lim"], w["why_ja"]))
        S.setdefault("wind", {})[st] = dict(state="not_run", complete=False, why=w["why_ja"]); save_state(S); return
    if w["start"] != w["want"]:
        report("%s：%s" % (st, w["why_ja"]))
    kw = {"wind": "S", "U10": float(st[1:3]), "sh": "SH", "prog": ch, "t_on": t_on, "t_td": sh["touchdown"]["t"], "ckpt_frame": w["start"],
          "still_offset": sh["still"], "out_root": ROOT}
    if ch == "PR3":
        kw["aim"] = sel["PR3_aim_m"]
    cfg = make_cfg("B", st, kw, st)
    cfg["ckpt_keep"] = K.keep_policy("B")
    state_, done, why = chain(cfg)
    wind_after(st, S, state_, done, why)


def wind_after(st, S, state_, done, why):
    """風の計算の後：止まり方を報告し、解析・風の判定を走らせ、表に入れられるか（complete）を決める。どの場合も先へ進む
    （置き場所が足りない時と、利用者の STOP の時だけ止まる）。"""
    if state_ in ("disk", "stopfile"):
        stop("%s：%s。%s" % (st, why, "置き場所を空けてから" if state_ == "disk" else "STOP を外してから") + "、" + cmd_line("--from " + st))
    S.setdefault("wind", {})[st] = r = dict(state=state_, done=done, why=why, complete=False)
    save_state(S)
    if state_ not in ("online", "done", "dry"):
        report("%s：計算が着水の 0.5 s 後にも形の本番の着水 + 2 Tc にも届かずに終わった（%s：%s）。記録を読めるだけ読み、次の段へ進む" % (st, state_, why))
    an, awhy = analyze_soft(st)
    if an is None:
        report("%s：解析が止まった（%s）。風の判定と残りの差の表には入れない。次の段へ進む" % (st, awhy))
        save_state(S); return
    if not an.get("onset") or not an.get("touchdown"):
        report("%s：記録の中に主な巻き波の巻き始めか着水がない（%s）。風の判定 W1〜W5 と表には入れない" % (st, "；".join(an.get("notes_ja", []))))
        save_state(S); return
    if an.get("onset_at_path_start"):
        report("%s：%s" % (st, an["onset_at_path_start"]))
    rc = run(PY + [TOOLS + "/g44_wind_check.py", st, "SH", ROOT])
    if rc != 0:
        report("%s：風の判定（g44_wind_check.py）が止まった（コード %d）。表には入れない" % (st, rc))
        save_state(S); return
    r["complete"] = True
    if state_ == "done":
        report("%s：計算の中の読みは着水を見つけず、形の本番の着水 + 2 Tc まで走った（打ち切りの道。解析の着水 %.2f s・%s）" % (
            st, an["touchdown"]["t"], an["touchdown"]["by"]))
    elif state_ not in ("online", "dry"):
        report("%s：途中で止まったが、記録の中に巻き始めと着水があるので判定に使う（着水 %.2f s）" % (st, an["touchdown"]["t"]))
    save_state(S)


def stage_rp(S):
    sel = need_select(S, "RP")
    rp = os.path.join(RUNS, "RP")
    old_ck = K.ckpt_frames(rp) if os.path.isdir(rp) else []
    old_recs = glob.glob(os.path.join(rp, "run_c*.json"))
    if old_ck or old_recs:      # G8：前の試みの途中保存
        rule_f = os.path.join(rp, "STOPPED_BY_RULE.txt")
        if os.path.exists(rule_f):
            stop("RP：%s/RP に、前の試みが 1 回目の外れで止まった記録（STOPPED_BY_RULE.txt、%s）と途中保存・起動の記録がある。同じ所で走らせると"
                 "古い途中保存の続きになり、古い止まりのファイルでまた止まる。狙いを直した繰り返しは、進行役が作る別の名前の設定で走らせる（計画 §3.3 (c)）。"
                 "--resume-rp でもここは走らせない" % (ROOT, time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(rule_f)))))
        if "--resume-rp" not in ARGS:
            stop("RP：%s/RP に前の試みの途中保存（%d 個、最後 %s コマ）か起動の記録（%d 個）がある。続きから走らせるなら：%s 。"
                 "最初から走らせるなら、利用者が %s/RP を別の名前へ動かしてから：%s" % (
                     ROOT, len(old_ck), old_ck[-1] if old_ck else "なし", len(old_recs), cmd_line("--from RP --resume-rp"), ROOT, cmd_line("--from RP")))
        log("RP: 前の試みの途中保存の続きから走らせる（--resume-rp）", old_ck[-1:] if old_ck else None)
    ch = sel["choice"]
    aim = {"PR1": "flat", "PR2": "reef"}.get(ch, "pr3:%g" % float(sel.get("PR3_aim_m") or 0))
    cfg = make_cfg("RP", "RP", {"aim": aim}, "RP")
    cfg["ckpt_keep"] = K.keep_policy("RP")
    st_ = chain_or_stop(cfg, "RP", cont="--from RP --resume-rp")
    if st_ == "rule":      # G8：この chain より新しい STOPPED_BY_RULE.txt だけ（chain_result が時刻を見る）
        stop("繰り返しの 1 回目が §3.3 (a) を外れた。(a) と同じ式で狙いを 1 回だけ直して最初から走らせ直す（計画 §3.3 (c)）。直す入口の表は進行役が作る")
    if run(PY + [TOOLS + "/g44_repeat.py", "RP", ROOT]) != 0:
        report("RP：繰り返しの判定（g44_repeat.py）が止まった。表の段へは進む")


def stage_table(S):
    sel = need_select(S, "TABLE")
    need_sh(S, "TABLE")
    if not os.path.exists(os.path.join(RUNS, "SH", "ana.json")):
        stop("TABLE：形の本番の解析（%s/SH/ana.json）がない。%s" % (ROOT, cmd_line("--from SH")))
    W = S.get("wind", {})
    ok = [k for k in ("B35S", "B45S") if (W.get(k) or {}).get("complete")]
    for k in ("B35S", "B45S"):
        if k not in ok:
            report("表：%s は入れない（%s）" % (k, json.dumps(W.get(k) or {"state": "not_run"}, ensure_ascii=False)[:300]))
    args = ["--wind"] + ["%s=%s" % (k, k) for k in ok] if ok else []
    rc = run(PY + [TOOLS + "/g44_ctable.py", "SH"] + args + ["--root", ROOT] + (["--pr2"] if sel["choice"] != "PR1" else []))
    if rc != 0:
        report("表：g44_ctable.py が止まった（コード %d）。queue_log.txt の上の出力を見る" % rc)


def main():
    global AGREED, ARGS
    a = sys.argv[1:]
    ARGS = a
    if "--agreed" not in a:
        sprint("指導教員の合意の記録（--agreed \"日時と場所\"）がないので走らせない。"); sys.exit(1)
    AGREED = a[a.index("--agreed") + 1]
    for flag in ("--from", "--only", "--confirm-select"):
        if flag in a and (a.index(flag) + 1 >= len(a) or a[a.index(flag) + 1] not in (STAGES if flag != "--confirm-select" else ("PR1", "PR2", "PR3"))):
            sprint("%s の後の名前が分からない（%s）。段の名前：%s" % (flag, a[a.index(flag) + 1] if a.index(flag) + 1 < len(a) else "なし", " ".join(STAGES)))
            sys.exit(1)
    setup(a[a.index("--root") + 1] if "--root" in a else "runs", "--dry-run" in a)
    open(os.path.join(RUNS, "AGREED.txt"), "a", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + "合意：" + AGREED + "\n")
    S = state()
    frm = a[a.index("--from") + 1] if "--from" in a else None
    only = a[a.index("--only") + 1] if "--only" in a else None
    if "--confirm-select" in a:
        x = a[a.index("--confirm-select") + 1]
        sel = S.get("select")
        if not sel:
            sprint("選びの結果（queue_state.json の select）がない。先に SELECT の段を走らせる。"); sys.exit(1)
        if x != sel["choice"]:
            sprint("選びの結果は %s で、%s ではない。choice と違う下見を選ぶのは計画の外なので受け付けない（止めて伺う）。" % (sel["choice"], x)); sys.exit(1)
        sel.update(confirmed=True, confirmed_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        save_state(S)
        open(os.path.join(RUNS, "SELECT_CONFIRMED.txt"), "a", encoding="utf8").write(
            "%s 選びの結果 %s を人が確かめた（--confirm-select %s）\n" % (sel["confirmed_at"], x, x))
        log("select confirmed", x)
        frm = frm or "PR3"
    if "--confirm-pr3" in a:
        sel = S.get("select") or {}
        if sel.get("choice") != "PR3" or not (S.get("PR3") or {}).get("pass_"):
            sprint("下見 3 本目を走らせて (a) に入った記録がないので、--confirm-pr3 は受け付けない。"); sys.exit(1)
        sel.update(pr3_confirmed=True, pr3_confirmed_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        save_state(S)
        open(os.path.join(RUNS, "SELECT_CONFIRMED.txt"), "a", encoding="utf8").write("%s 下見 3 本目の結果を人が確かめた（--confirm-pr3）\n" % sel["pr3_confirmed_at"])
        log("PR3 confirmed")
        frm = frm or "SH"
    frm = frm or "PR1"
    todo = [s for s in STAGES[STAGES.index(frm):] if only is None or s == only]
    log("queue start", " ".join(todo), "| awake_request", keep_awake(), "| dry" if DRY else "")
    st = None
    try:
        disk_check(todo, S, "--disk-ok" in a)
        for st in todo:
            log("stage", st)
            if st in ("PR1", "PR2"):
                stage_pr(st, S)
            elif st == "SELECT":
                stage_select(S)
            elif st == "PR3":
                stage_pr3(S)
            elif st == "SH":
                if stage_sh(S) == "end":
                    break
            elif st in ("B35S", "B45S"):
                wind_stage(st, S)
            elif st == "RP":
                stage_rp(S)
            elif st == "TABLE":
                stage_table(S)
    except Exception as e:      # G1：思わない誤りも traceback で終わらず、理由を書いて止まる
        open(os.path.join(RUNS, "queue_log.txt"), "a", encoding="utf8").write(traceback.format_exc() + "\n")
        stop("%s の段で思わない誤りが出た（%s）。詳しくは %s/queue_log.txt。原因を見てから %s" % (st, repr(e)[:300], ROOT, cmd_line("--from %s" % (st or frm))))
    log("queue end")


if __name__ == "__main__":
    main()
