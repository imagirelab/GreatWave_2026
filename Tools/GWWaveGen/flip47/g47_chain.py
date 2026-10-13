# -*- coding: utf-8 -*-
"""FLIP47：計算 1 本を、1 回 29 分（wall_limit_s 1740 s）以内の起動に区切って最後まで続ける（途中保存から再開。py -3.10）。
FLIP46 の g46_chain.py（変えていない）を写して直した。変えた所：置き場所（Build/FLIP47）、走らせる道具（g47_run.py）、途中保存は消さない
（2D の計算は途中保存が小さい：粒子 0.25 m で 1 個 約 0.1〜0.3 GB の見込み。帳面と消す決まりは持ち込まない）、ほかの hython を待つのは
60 秒ごと・cfg の wait_hython_max_s（既定 1800 s）まで（越えたら STOPPED_BUSY.txt を書いて止める）。
同じ所（FLIP46 の説明のまま）：
  途中保存の間隔を起動ごとに選び直す（cfg の ckpt_list から、前の起動の終わりの 1 コマの秒で 30 分に収まる最大のもの）。
  始めのコマは、途中保存のフォルダーの最後の途中保存の次のコマ。新しい途中保存を作らずに終わったら、間隔を一段小さくして起動し直す。
  runs/<run_id>/STOP を置くと、今の起動の後で止まる。max_hours（cfg）を越えたら次の起動をしない。G: の空きが 25 GB より少なければ止める。
  止まり方を平文のファイルに書く：STOPPED_MAX_HOURS.txt・STOPPED_NO_CKPT.txt・STOPPED_CRASH.txt・STOPPED_ONLINE.txt・STOPPED_GUARD.txt・STOPPED_BUSY.txt。
  この chain が動いている間だけ SetThreadExecutionState を頼む（電源の設定は変えない）。
py -3.10 g47_chain.py <cfg.json>
"""
import sys, json, os, glob, subprocess, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC

RUN = GC.TOOLS + "/g47_run.py"
TMP = GC.B47 + "/tmp_houdini"
cfg = json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]
R = os.path.join(GC.B47, cfg.get("out_root", "runs"))
rd = os.path.join(R, rid)
os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
os.makedirs(TMP, exist_ok=True)
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))
WL = float(cfg.get("wall_limit_s", 1740))
WAITMAX = float(cfg.get("wait_hython_max_s", 1800))
base_sp = int(cfg.get("ckpt_every", 120))
sp_list = sorted(set(int(v) for v in cfg.get("ckpt_list", [base_sp])), reverse=True)
f_first = int(cfg.get("f_start", 1))
f_end = int(cfg["f_end"])
disk_stop = float(cfg.get("disk_stop_free_gb", 25.0))
PRIO = GC.unthrottle_self()


def stop_note(name, text):
    open(os.path.join(rd, name), "w", encoding="utf8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")


def log(*a):
    msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode(), flush=True)
    with open(os.path.join(rd, "chain.log"), "a", encoding="utf8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


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


def wait_or_stop():
    if GC.wait_no_hython(poll=60, max_wait_s=WAITMAX, log=log) is None:
        stop_note("STOPPED_BUSY.txt", "ほかの hython が %.0f 秒より長く動いていたので始めなかった（重い計算は一度に一つ）" % WAITMAX)
        log("stop: another hython kept running"); sys.exit(2)


log("chain start", rid, "awake_request", GC.keep_awake(), "free_gb %.1f" % GC.free_gb(), "stop_line_gb %.0f" % disk_stop, "priority", PRIO)
_sol = cfg.get("solitary_npz")
if float(cfg.get("parms", {}).get("wave_on", 1.0)) > 0.5:
    if not _sol or not os.path.exists(_sol):
        stop_note("STOPPED_CRASH.txt", "孤立波の npz %s がないので始めなかった" % _sol)
        log("no solitary npz", _sol); sys.exit(1)
    cfg["solitary_sha256"] = GC.sha256_file(_sol)
    log("solitary", _sol, cfg["solitary_sha256"][:12])
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)

wait_or_stop()
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
    free = GC.free_gb()
    if free < disk_stop:
        open(os.path.join(rd, "STOP_DISK.txt"), "w", encoding="utf8").write(
            "%s G: の空き %.1f GB が %.0f GB より少ないので止めた。消すかは利用者が決める。\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), free, disk_stop))
        log("disk free %.1f GB < %.0f GB; stop" % (free, disk_stop)); break
    sp = base_sp if base_sp in sp_list else sp_list[0]
    s_est, load = tail_cost(prev_f0) if prev_f0 is not None else (None, None)
    if s_est is not None:
        ok = [v for v in sp_list if load + 1.5 * v * s_est <= 0.92 * WL]
        sp = ok[0] if ok else sp_list[-1]
    if force_idx is not None:
        sp = min(sp, sp_list[min(force_idx, len(sp_list) - 1)])
    c = dict(cfg, f_start=f0, ckpt_every=sp)
    c.setdefault("f_first", f_first)
    c["wall_limit_s"] = min(WL, max(60.0, max_h * 3600 - (time.time() - T0)))
    wait_or_stop()
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    cpath = os.path.join(rd, "cfg_c%04d.json" % f0)
    json.dump(c, open(cpath, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + " ckpt_every %d\n" % sp); lg.flush()
        subprocess.run([GC.HY, RUN, cpath], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
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
    st = r["stopped"] or ""
    if st.startswith("touchdown_online"):
        stop_note("STOPPED_ONLINE.txt", "計算の中の着水の読みで止めた（%s）。cfg の stop_touchdown の止め方どおり" % st)
        break
    if st.startswith(("free_fall", "no water", "error", "disk")):
        stop_note("STOPPED_GUARD.txt", "見張りで止まった（%s）" % st)
        break
    if done >= f_end or not st.startswith("wall_limit"):
        break
    ck = [k for k in ckpts() if k <= done]
    prev_f0 = f0
    if not ck or ck[-1] + 1 <= f0:
        idx = sp_list.index(sp) if sp in sp_list else 0
        if idx + 1 >= len(sp_list):
            log("no new checkpoint at the smallest spacing; stop")
            stop_note("STOPPED_NO_CKPT.txt", "%d コマ目からの起動で新しい途中保存ができなかった（間隔 %d、いちばん小さい間隔）。1 回の起動 %.0f s の中で次の途中保存に届かない"
                      % (f0, sp, WL))
            break
        force_idx = idx + 1
        log("no new checkpoint; retry from", f0, "with spacing", sp_list[force_idx])
        continue
    force_idx = None
    f0 = ck[-1] + 1
log("chain end", rid, "elapsed_h %.3f" % ((time.time() - T0) / 3600))
