# -*- coding: utf-8 -*-
"""FLIP44：計算 1 本を、1 回 30 分以内の起動に区切って最後まで続ける（途中保存から再開）。
FLIP42 の g_chain2.py（変えていない）を写して直した。同じにした所：
  途中保存の間隔を起動ごとに選び直す（cfg の ckpt_list から、前の起動の終わりの 1 コマの秒で 30 分に収まる最大のもの）。
  ckpt_lock_until（コマ）までは ckpt_every のまま（形の本番の f_w の途中保存を必ず作るため。計画 §4.1）。
  始めのコマは、途中保存のフォルダーの最後の途中保存の次のコマ。新しい途中保存を作らずに終わったら、間隔を一段小さくして起動し直す。
  ほかの hython が動いていたら、終わるまで待つ（重い計算は一度に一つ）。runs/<run_id>/STOP を置くと、今の起動の後で止まる。
  max_hours（cfg）：この chain の始めからの経過がこれを越えたら、次の起動をしないで止める（計画 §3.2：見込みの上の端の 2 倍）。
足した所（計画 §3.2・§3.3・§4.1・N8）：
  - 起動の前に G: の空きを見て、25 GB より少なければ止めて利用者に伺う（STOP_DISK.txt を書く。g44_run.py も起動の始めに見る）。
  - from_ckpt（風の計算）：形の本番の途中保存 v.<コマ>.sim を、この計算の ckpt に写してから始める（元は消さない）。
  - stop_check：起動の後に、記録から止める決まりを見る（g44_analyze.stop_main_touchdown：主な巻き波の着水 + 2 Tc、
    g44_repeat.stop_first_group：繰り返しの 1 回目が §3.3 (a) を外れたら 1 回目の着水 + 2 Tc）。
  - 止まり方の記録（2026-10-12 確かめ F2 の直し）：f_end の前に終わった時は、理由を 1 つのファイルに平文で書く。
    STOPPED_MAX_HOURS.txt（打ち切りの時間）・STOPPED_NO_CKPT.txt（途中保存が作れない）・STOPPED_CRASH.txt（起動の記録がない）。
    STOPPED_BY_RULE.txt・STOP_DISK.txt・STOP は前と同じ。g44_queue.py はこれを読んで、報告して先へ進むか、理由を書いて止まる。
  - from_ckpt に root（FLIP44 の下の置き場所）があれば、元の途中保存をそこから写す（煙の試し用。なければこの計算と同じ置き場所）。
  - 2026-10-12（2 回目の確かめ check/check_fixes_ja.md の後。record_ja.md §3.2）：
    G2：起動の後に g44_ckpt.after_launch を呼ぶ。cfg に ckpt_keep（g44_queue.py が足す）があれば、続きから走らせるのに要る物と計画が
        走らせ直しに使う物だけを残し、この chain が作ったほかの途中保存を消す（本番の置き場所 runs の時だけ。ほかは消すはずの物を書くだけ）。
        作った物・消した物は rd/ckpt_ledger.json。風の計算の元の途中保存は、この計算にそれより新しい途中保存がない時だけ写す。
    G6：g44_run.py が設定を拒んだ時（stopped "refused: ..."）は STOPPED_REFUSED.txt に理由を書いて止まる。
  - 2026-10-12 06:4x（3 回目の確かめ check/check_fixes2_ja.md の H7。record_ja.md §3.3）：帳面の made に、作った chain の種類（origin）を書く。
    ckpt_keep のある chain（並び）は "queue"、ない chain（README §2 の 1 本ずつの道）は "single"。並びが消すのは "queue" の物だけ。
    風の計算の元の途中保存の写しも同じ（並びの chain の写しだけが、その計算が進んだ後で消える）。
    夜の間に PC が眠らないように、この chain が動いている間だけ SetThreadExecutionState（ES_CONTINUOUS | ES_SYSTEM_REQUIRED）を頼む
    （画面は消えてよい。chain が終わると Windows が元に戻す。電源の設定は変えない）。
py -3.10 g44_chain.py <cfg.json>
"""
import sys, json, os, glob, subprocess, time, shutil, importlib, ctypes
import numpy as np

BASE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44"
RUN = TOOLS + "/g44_run.py"
TMP = BASE + "/tmp_houdini"
sys.path.insert(0, TOOLS)
cfg = json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]
R = os.path.join(BASE, cfg.get("out_root", "runs"))
rd = os.path.join(R, rid)
os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
os.makedirs(TMP, exist_ok=True)
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))
WL = float(cfg.get("wall_limit_s", 1740))
base_sp = int(cfg.get("ckpt_every", 240))
sp_list = sorted(set(int(v) for v in cfg.get("ckpt_list", [base_sp])), reverse=True)
lock_until = int(cfg.get("ckpt_lock_until", 0))
f_first = int(cfg.get("f_start", 1))
f_end = int(cfg["f_end"])
nper = float(cfg.get("ckpt_per_launch", 1))
disk_stop = float(cfg.get("disk_stop_free_gb", 25.0))
import g44_ckpt as K


def keep_awake():
    """この処理が動いている間だけ、Windows が眠らないように頼む（終わると元に戻る）。返り値は頼めたか。"""
    try:
        f = ctypes.windll.kernel32.SetThreadExecutionState
        f.argtypes = [ctypes.c_uint]; f.restype = ctypes.c_uint
        return bool(f(0x80000000 | 0x00000001))
    except Exception:
        return False


def stop_note(name, text):
    """止まった理由を平文で残す（g44_queue.py が読む）。"""
    open(os.path.join(rd, name), "w", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + chr(10))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
    with open(os.path.join(rd, "chain.log"), "a", encoding="utf8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


def ckpts():
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def tail_cost(f0):
    p = os.path.join(rd, "hf_c%04d.npz" % f0)
    if not os.path.exists(p):
        return None, None
    w = np.load(p)["wall"]
    if len(w) < 3:
        return None, None
    return float(np.percentile(w[1:][-48:], 75)), float(w[0])


log("chain start", rid, "awake_request", keep_awake(), "free_gb %.1f" % (shutil.disk_usage("G:/").free / 2**30), "stop_line_gb %.0f" % disk_stop,
    "ckpt_keep", json.dumps(cfg.get("ckpt_keep"), ensure_ascii=False)[:300])

# 風の計算：形の本番の途中保存を写す（この計算にそれより新しい途中保存がある時は写さない。前の起動の後で写しを消していても続きから走れる）
fc = cfg.get("from_ckpt")
if fc:
    src = os.path.join(BASE, fc.get("root", cfg.get("out_root", "runs")), fc["run"], "ckpt", "v.%04d.sim" % int(fc["frame"]))
    dst = os.path.join(rd, "ckpt", "v.%04d.sim" % int(fc["frame"]))
    if not os.path.exists(dst) and not [k for k in ckpts() if k >= int(fc["frame"])]:
        if not os.path.exists(src):
            log("from_ckpt missing", src)
            stop_note("STOPPED_CRASH.txt", "元の途中保存 %s がないので始められなかった" % src)
            sys.exit(1)
        shutil.copy2(src, dst)
        log("copied", src, "->", dst)
        _L = K.load_ledger(rd); K.note_made(rd, _L, [int(fc["frame"])], "copy from %s" % src, origin="queue" if cfg.get("ckpt_keep") else "single")
        K.save_ledger(rd, _L)

while hython_running():
    time.sleep(5)
ck = [k for k in ckpts() if k >= f_first - 1]
f0 = max(f_first, (ck[-1] + 1) if ck else f_first)
prev_f0 = None
force_idx = None
for it in range(400):
    if f0 > f_end:
        break
    if os.path.exists(os.path.join(rd, "STOP")):
        log("STOP found"); break
    if (time.time() - T0) / 3600 > max_h:
        log("max_hours exceeded (%.2f h > %.2f h); stop" % ((time.time() - T0) / 3600, max_h))
        stop_note("STOPPED_MAX_HOURS.txt", "打ち切りの時間 %.2f 時間（cfg の max_hours）を越えたので、次の起動をしなかった（最後の途中保存は %d コマ目、目標 %d コマ）。"
             "計算の誤りではなく、時間の上限で止めた" % (max_h, f0 - 1, f_end))
        break
    free = shutil.disk_usage("G:/").free / 2**30
    if free < disk_stop:
        open(os.path.join(rd, "STOP_DISK.txt"), "w", encoding="utf8").write(
            "%s G: の空き %.1f GB が %.0f GB より少ないので止めた（計画 N8）。消すかは利用者が決める。\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), free, disk_stop))
        log("disk free %.1f GB < %.0f GB; stop" % (free, disk_stop)); break
    if f0 <= lock_until:
        sp = base_sp
    else:
        sp = base_sp if base_sp in sp_list else sp_list[0]
        s_est, load = tail_cost(prev_f0) if prev_f0 is not None else (None, None)
        if s_est is not None:
            ok = [v for v in sp_list if load + 1.5 * nper * v * s_est <= 0.92 * WL]
            sp = ok[0] if ok else sp_list[-1]
        if force_idx is not None:
            sp = min(sp, sp_list[min(force_idx, len(sp_list) - 1)])
    c = dict(cfg, f_start=f0, ckpt_every=sp)
    c.setdefault("f_first", f_first)
    c["wall_limit_s"] = min(WL, max(60.0, max_h * 3600 - (time.time() - T0)))
    while hython_running():
        time.sleep(5)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    cpath = os.path.join(rd, "cfg_c%04d.json" % f0)
    json.dump(c, open(cpath, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    ck_before = ckpts()
    with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + " ckpt_every %d\n" % sp); lg.flush()
        subprocess.run([HY, RUN, cpath], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        log("no run record for chunk", f0, "(crash?)")
        stop_note("STOPPED_CRASH.txt", "%d コマ目からの起動の記録 run_c%04d.json がない（hython が落ちた見込み。log_c%04d.txt を見る）" % (f0, f0, f0))
        break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    log(rid, "chunk", f0, "ckpt_every", sp, "done to", done, "stopped", r["stopped"], "wall", r.get("wall_total_s"),
        "s/frame", r.get("wall_per_frame_median_s"), "sub", r.get("substeps_min_max"), "pts", r.get("particles_max"), "rss", r.get("rss_peak_gb"))
    if (r["stopped"] or "").startswith("refused"):
        stop_note("STOPPED_REFUSED.txt", "g44_run.py が設定を拒んだ（%s）。設定を直してから走らせる" % r["stopped"])
        break
    try:       # G2：途中保存の帳面と、残す物の外の物を消す（決まり ckpt_keep がある時だけ）
        _hf = os.path.join(rd, "hf_c%04d.npz" % f0)
        _w = np.load(_hf)["wall"] if os.path.exists(_hf) else np.array([])
        K.after_launch(rd, cfg, f0, done, ck_before, float(_w[0]) if len(_w) else None,
                       float(np.median(_w[1:])) if len(_w) > 1 else None, log=log)
    except Exception as e:
        log("ckpt_keep error", repr(e)[:300])
    sc = cfg.get("stop_check")
    if sc and done > 0:
        try:
            mod = importlib.import_module(sc["module"])
            stop, note = getattr(mod, sc["func"])(rid, cfg.get("out_root", "runs"), (done - 1) / 24.0, cfg, **sc.get("args", {}))
            log("stop_check", sc["func"], stop, note)
            if stop:
                open(os.path.join(rd, "STOPPED_BY_RULE.txt"), "w", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(note) + "\n")
                break
        except Exception as e:
            log("stop_check error", repr(e)[:300])
    if done >= f_end or not (r["stopped"] or "").startswith("wall_limit"):
        break
    ck = [k for k in ckpts() if k <= done]
    prev_f0 = f0
    if not ck or ck[-1] + 1 <= f0:
        idx = sp_list.index(sp) if sp in sp_list else 0
        if idx + 1 >= len(sp_list) or f0 <= lock_until:
            log("no new checkpoint at the smallest spacing (or inside the lock); stop")
            stop_note("STOPPED_NO_CKPT.txt", "%d コマ目からの起動で新しい途中保存ができなかった（間隔 %d、%s）。1 回の起動 %.0f s の中で次の途中保存に届かない"
                 % (f0, sp, "間隔を固定する区間（ckpt_lock_until %d）の中" % lock_until if f0 <= lock_until else "いちばん小さい間隔", WL))
            break
        force_idx = idx + 1
        log("no new checkpoint; retry from", f0, "with spacing", sp_list[force_idx])
        continue
    force_idx = None
    f0 = ck[-1] + 1
log("chain end", rid, "elapsed_h %.3f" % ((time.time() - T0) / 3600))
