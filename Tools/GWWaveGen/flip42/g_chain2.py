# -*- coding: utf-8 -*-
"""FLIP42：計算 1 本を、1 回 30 分以内の起動に区切って最後まで続ける（途中保存から再開）。g_chain.py（R1・R1b で使った。変えていない）を写して直した。
直した所（R2 の段、2026-10-09）：
  1. 途中保存の間隔を起動ごとに選び直せるようにした。1 コマの秒が大きくなる所（崩れの後、細かい計算）で、30 分の起動の中に次の途中保存へ
     届かないと計算が進まなくなるため。間隔は cfg の ckpt_list（大きい順）から、前の起動の終わりの 1 コマの秒で 30 分に収まる最大のものを選ぶ。
     ckpt_lock_until（コマ）までは ckpt_every のまま（R3 の 3318 コマ目の途中保存を必ず作るため）。
  2. 始めのコマは、途中保存のフォルダーの最後の途中保存の次のコマ（f_start より前なら f_start）。続きから再開できる。R5' は R3 の途中保存を写して置く。
  3. 起動が新しい途中保存を作らずに終わったら、間隔を一段小さくして同じコマから起動し直す（いちばん小さくても進まなければ止める）。
py -3.10 g_chain2.py <cfg.json>   重い計算は一度に一つ（動いている hython の終わりを待つ）。
止める：runs/<run_id>/STOP を置くと、今の起動の後で止まる。
max_hours（cfg）：この chain の始めからの経過がこれを越えたら、次の起動をしないで止める。"""
import sys, json, os, glob, subprocess, time
import numpy as np

R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
RUN = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/g_run.py"
TMP = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini"
cfg = json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]; rd = os.path.join(R, rid)
os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))
WL = float(cfg.get("wall_limit_s", 1740))
base_sp = int(cfg.get("ckpt_every", 240))
sp_list = sorted(set(int(v) for v in cfg.get("ckpt_list", [base_sp])), reverse=True)
lock_until = int(cfg.get("ckpt_lock_until", 0))
f_first = int(cfg.get("f_start", 1))
f_end = int(cfg["f_end"])
nper = float(cfg.get("ckpt_per_launch", 1))   # 1 回の起動で作りたい途中保存の数（多いほど、途中保存の後に捨てる計算が減る）


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


def ckpts():
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def tail_cost(f0):
    """前の起動の hf の記録から（1 コマの秒の 75 % 点、最初のコマの秒＝読み込み込み）。"""
    p = os.path.join(rd, "hf_c%04d.npz" % f0)
    if not os.path.exists(p):
        return None, None
    w = np.load(p)["wall"]
    if len(w) < 3:
        return None, None
    return float(np.percentile(w[1:][-48:], 75)), float(w[0])


while hython_running():   # 動いている起動が終わってから、最後の途中保存を見て始めのコマを決める
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
        log("max_hours exceeded (%.2f h > %.2f h); stop" % ((time.time() - T0) / 3600, max_h)); break
    # 間隔を選ぶ
    if f0 <= lock_until:
        sp = base_sp
    else:
        sp = base_sp if base_sp in sp_list else sp_list[0]   # 前の起動の記録がない時は ckpt_every
        s_est, load = tail_cost(prev_f0) if prev_f0 is not None else (None, None)
        if s_est is not None:
            ok = [v for v in sp_list if load + 1.5 * nper * v * s_est <= 0.92 * WL]
            sp = ok[0] if ok else sp_list[-1]
        if force_idx is not None:
            sp = min(sp, sp_list[min(force_idx, len(sp_list) - 1)])
    c = dict(cfg, f_start=f0, ckpt_every=sp)
    c["wall_limit_s"] = min(WL, max(60.0, max_h * 3600 - (time.time() - T0)))
    while hython_running():
        time.sleep(5)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + " ckpt_every %d\n" % sp); lg.flush()
        subprocess.run([HY, RUN, json.dumps(c)], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        log("no run record for chunk", f0, "(crash?)"); break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    log(rid, "chunk", f0, "ckpt_every", sp, "done to", done, "stopped", r["stopped"], "wall", r["wall_total_s"],
        "s/frame", r["wall_per_frame_median_s"], "sub", r.get("substeps_min_max"), "pts", r.get("particles_max"), "rss", r.get("rss_peak_gb"))
    if done >= f_end or not (r["stopped"] or "").startswith("wall_limit"):
        break
    ck = [k for k in ckpts() if k <= done]
    prev_f0 = f0
    if not ck or ck[-1] + 1 <= f0:
        idx = sp_list.index(sp) if sp in sp_list else 0
        if idx + 1 >= len(sp_list) or f0 <= lock_until:
            log("no new checkpoint at the smallest spacing (or inside the lock); stop"); break
        force_idx = idx + 1
        log("no new checkpoint; retry from", f0, "with spacing", sp_list[force_idx])
        continue
    force_idx = None
    f0 = ck[-1] + 1
log("chain end", rid, "elapsed_h %.3f" % ((time.time() - T0) / 3600))
