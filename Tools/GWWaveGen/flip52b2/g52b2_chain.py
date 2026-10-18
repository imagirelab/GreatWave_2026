# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-18 by flip52b2/g52b2_mkcopy.py from flip52/g52_chain.py (sha256 adc668759bf65cddf411c31e1fe8fa4861d2b8ee709a46f81e13894eb495d728, not edited) by exact, counted string replacements:
  - constants and paths from flip52b2/g52b2_common.py (Build/FLIP52B2, Houdini/FLIP52B2/g52b2_tank.hiplc) and flip52b2/g52b2_run.py; the start
    gate reads Unity/Build/FLIP52B2/_logs/build_check52b2.json; messages name x52b2_build.py and g52b2_pcfg.py.
Everything else is the FLIP52 / FLIP50 chain (flip46/g46_ckpt ledger; start gate: cfg precheck.ok, build check, frozen plan .sha256, table
sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting time is not counted against max_hours,
which counts from this chain's own start: a new chain on a max_hours stop resumes from the last checkpoint with a fresh budget).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b2/g52b2_chain.py <cfg.json>
"""
import sys, json, os, glob, subprocess, time, shutil
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g52b2_common as GC
import g46_ckpt as K

RUN = GC.TOOLS52B2 + "/g52b2_run.py"
TMP = GC.B52B2 + "/tmp_houdini"
cfg = json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]
R = os.path.join(GC.B52B2, cfg.get("out_root", "runs"))
rd = os.path.join(R, rid)
os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
os.makedirs(TMP, exist_ok=True)
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))
WL = float(cfg.get("wall_limit_s", 1740))
base_sp = int(cfg.get("ckpt_every", 240))
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
    return K.ckpt_frames(rd)


def tail_cost(f0):
    p = os.path.join(rd, "r6_c%05d.npz" % f0)
    if not os.path.exists(p):
        return None, None
    d = np.load(p)
    w = d["wall"] + (d["surf_s"] if "surf_s" in d.files else 0.0)
    if len(w) < 3:
        return None, None
    return float(np.percentile(w[1:][-48:], 75)), float(w[0])


def gate():
    """始める前の門。返り値：外れの理由の list（空なら始めてよい）。"""
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict):
        bad.append("cfg に precheck がない（g52b2_pcfg.py で書いた cfg だけ走らせる）")
    elif pc.get("ok") is not True:
        bad.append("precheck が ok でない：%s" % pc.get("reason"))
    ckp = GC.BUILD_CHECK
    if not os.path.exists(ckp):
        bad.append("場面の確かめ %s がない（py -3.10 x52b2_build.py）" % ckp)
    else:
        c = json.load(open(ckp, encoding="utf8"))
        if not c.get("all_ok"):
            bad.append("場面の確かめ build_check52b2.json の all_ok が偽")
        if not os.path.exists(GC.HIP):
            bad.append("場面 %s がない" % GC.HIP)
        elif c.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("場面の SHA-256 が確かめた時の値と違う（作り直した後に x52b2_build.py の確かめを通す）")
    dr = cfg.get("dir")
    if dr:
        if not os.path.exists(dr.get("npz") or ""):
            bad.append("directional table %s is missing (g52b2_pcfg.py cfg writes it)" % dr.get("npz"))
        elif GC.sha256_file(dr["npz"]) != dr.get("npz_sha256"):
            bad.append("directional table %s sha256 differs from the cfg" % dr["npz"])
    pf = (cfg.get("case") or {}).get("plan_frozen")
    if pf:
        p = pf if os.path.isabs(pf) else os.path.join(GC.REPO, pf)
        sp = p + ".sha256"
        if not (os.path.exists(p) and os.path.exists(sp)):
            bad.append("凍らせた計画 %s か .sha256 がない" % p)
        elif open(sp, encoding="utf8").read().split()[0] != GC.sha256_file(p):
            bad.append("凍らせた計画 %s の SHA-256 が .sha256 と違う（決まりが変わった）" % p)
    return bad


_bad = gate()
if _bad:
    stop_note("STOPPED_PRECHECK.txt", "始める前の門で止めた：" + " / ".join(_bad))
    log("gate failed; not started", _bad); sys.exit(1)
log("chain start", rid, "awake_request", GC.keep_awake(), "free_gb %.1f" % GC.free_gb(), "stop_line_gb %.0f" % disk_stop, "priority", PRIO)
cfg["hip_sha256"] = GC.sha256_file(GC.HIP)
cfg["module_shas_at_chain_start"] = GC.module_shas()
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)

T0 += GC.wait_no_hython(log=log)          # waiting is not run time (max_hours counts from the first launch)
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
    T0 += GC.wait_no_hython(log=log)      # waiting is not run time
    c["wall_limit_s"] = min(WL, max(60.0, max_h * 3600 - (time.time() - T0)))
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    cpath = os.path.join(rd, "cfg_c%05d.json" % f0)
    json.dump(c, open(cpath, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    ck_before = ckpts()
    with open(os.path.join(rd, "log_c%05d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + " ckpt_every %d\n" % sp); lg.flush()
        subprocess.run([GC.HY, RUN, cpath], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    rc = os.path.join(rd, "run_c%05d.json" % f0)
    if not os.path.exists(rc):
        log("no run record for chunk", f0, "(crash?)")
        stop_note("STOPPED_CRASH.txt", "%d コマ目からの起動の記録 run_c%05d.json がない（hython が落ちた見込み。log_c%05d.txt を見る）" % (f0, f0, f0))
        break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    log(rid, "chunk", f0, "ckpt_every", sp, "done to", done, "stopped", r["stopped"], "wall", r.get("wall_total_s"),
        "s/frame", r.get("wall_per_frame_median_s"), "surf", r.get("surf_per_frame_median_s"), "sub", r.get("substeps_min_max"),
        "pts", r.get("particles_max"), "rss", r.get("rss_peak_gb"))
    try:
        K.after_launch(rd, cfg, f0, done, ck_before, log=log)
    except Exception as e:
        log("ckpt_keep error", repr(e)[:300])
    st = r["stopped"] or ""
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
