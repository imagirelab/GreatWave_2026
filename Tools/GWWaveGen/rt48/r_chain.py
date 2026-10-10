# -*- coding: utf-8 -*-
"""RT48（計画 Unity/Build/RT48/plan/plan_ja.md §2.2）：R3 の計算し直し（R3e）を、1 回 30 分以内の起動に区切って最後まで続ける。
Tools/GWWaveGen/flip42/g_chain2.py（変えていない）を写して直した。変えたのは次の所で、間隔の選び方と起動の区切り方は g_chain2.py と同じ：
  1. 出力先：Unity/Build/RT48/rerun/<run_id>/。起動するのは rt48/r_run.py（g_run.py の写しに粒子の書き出しを足した物）。
  2. Houdini の一時フォルダー：Unity/Build/RT48/tmp_houdini（g_chain2.py の 18 行目は FLIP42/tmp_houdini に固定している）。
  3. 待ち方：R4d の chain（コマンドの行に g_chain2.py と cfg_R4d_b.json を含む python）が終わり、かつ hython が 120 s 続けて
     動いていない時に始める（g_chain2.py は「hython が動いていない」だけを見るので、R4d の起動と起動の間の数秒に割り込む恐れがある）。
     起動の前ごとに、hython が動いていないのを待つのは g_chain2.py と同じ。
  4. hython を「通常より下」の優先度で起動する（BELOW_NORMAL_PRIORITY_CLASS）。g_unthrottle.py が動いていれば同じ設定をする。
  5. 間隔を選ぶ時の 1 コマの秒に、粒子の書き出しの秒（hf の wall_exp）を足す。
  6. 始める前の確かめ：G: の空き 60 GB 以上、場面の SHA-256 が R3 と同じ、途中保存 v.3318.sim を R3 から写して SHA-256 が同じ。
  7. 終わった後、--after を付けた時は rt48/r_after.py を起動する（C1 (b)・細かい面・焼き）。
py -3.10 r_chain.py <cfg.json> [--after]
止める：Unity/Build/RT48/rerun/<run_id>/STOP を置くと、今の起動の後で止まる（待っている間に置けば始めない）。
記録：Unity/Build/RT48/rerun/<run_id>/chain_state.json（今の状態）と、標準出力（起動した側でファイルへ）。"""
import sys, json, os, glob, subprocess, time, hashlib, shutil
import numpy as np

R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/rerun"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
RUN = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/rt48/r_run.py"
AFTER = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/rt48/r_after.py"
TMP = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/tmp_houdini"
HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc"
HIP_SHA_R3 = "e17c9aad315aef24fb671ebdef4cafae670b457d2d996f122e9e4aba2f50a922"
R3CK = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3/ckpt"
BELOW_NORMAL = 0x00004000
cfg = json.load(open(sys.argv[1], encoding="utf8"))
DO_AFTER = "--after" in sys.argv[2:]
rid = cfg["run_id"]; rd = os.path.join(R, rid)
os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
os.makedirs(TMP, exist_ok=True)
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
WL = float(cfg.get("wall_limit_s", 1740))
base_sp = int(cfg.get("ckpt_every", 240))
sp_list = sorted(set(int(v) for v in cfg.get("ckpt_list", [base_sp])), reverse=True)
lock_until = int(cfg.get("ckpt_lock_until", 0))
f_first = int(cfg.get("f_start", 1))
f_end = int(cfg["f_end"])
nper = float(cfg.get("ckpt_per_launch", 1))
ck_from = cfg.get("ckpt_from")   # 例 {"src": R3CK + "/v.3318.sim"}
STATE = os.path.join(rd, "chain_state.json")


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def state(**kw):
    s = {}
    if os.path.exists(STATE):
        try:
            s = json.load(open(STATE, encoding="utf8"))
        except Exception:
            s = {}
    s.update(kw)
    s["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(s, open(STATE, "w", encoding="utf8"), indent=1, ensure_ascii=False)


def procs():
    """(名前, コマンドの行) の一覧（PowerShell の Win32_Process）"""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|hython|py.exe' } | "
          "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.Name + '|' + $_.CommandLine }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf8", errors="ignore").stdout
    r = []
    for line in out.splitlines():
        p = line.split("|", 2)
        if len(p) == 3:
            r.append((int(p[0]) if p[0].strip().isdigit() else -1, p[1].lower(), p[2]))
    return r


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


def r4d_chain_alive():
    import re
    me = os.getpid()
    for pid, name, cmd in procs():
        if pid != me and re.search(r"g_chain2\.py\s+\S*cfg_R4d", cmd):
            return True
    return False


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def ckpts():
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def tail_cost(f0):
    """前の起動の hf の記録から（1 コマの秒＋書き出しの秒の 75 % 点、最初のコマの秒＝読み込み込み）。"""
    p = os.path.join(rd, "hf_c%04d.npz" % f0)
    if not os.path.exists(p):
        return None, None
    d = np.load(p)
    w = d["wall"]
    if "wall_exp" in d.files and len(d["wall_exp"]) == len(w):
        w = w + np.maximum(d["wall_exp"], 0)
    if len(w) < 3:
        return None, None
    return float(np.percentile(w[1:][-48:], 75)), float(w[0])


# ---------------------------------------------------------------- 待つ
log("queued", rid, "pid", os.getpid())
state(phase="waiting_r4d", pid=os.getpid(), queued=time.strftime("%Y-%m-%d %H:%M:%S"))
free_since = None
while True:
    if os.path.exists(os.path.join(rd, "STOP")):
        log("STOP found while waiting"); state(phase="stopped_while_waiting"); sys.exit(0)
    alive = r4d_chain_alive()
    hy = hython_running()
    if alive or hy:
        free_since = None
    elif free_since is None:
        free_since = time.time()
    if free_since is not None and time.time() - free_since >= 120:
        break
    time.sleep(10 if free_since is not None else 60)
log("R4d chain ended and no hython for 120 s")
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))

# ---------------------------------------------------------------- 始める前の確かめ
free_gb = shutil.disk_usage("G:/").free / 2**30
hip_sha = sha(HIP)
pre = {"free_gb": round(free_gb, 1), "hip_sha256": hip_sha, "hip_same_as_r3": hip_sha == HIP_SHA_R3}
if ck_from:
    src = ck_from["src"]; dst = os.path.join(rd, "ckpt", os.path.basename(src))
    if not os.path.exists(dst):
        shutil.copyfile(src, dst + ".tmp"); os.replace(dst + ".tmp", dst)
    s1, s2 = sha(src), sha(dst)
    pre.update(ckpt_src=src, ckpt_src_sha256=s1, ckpt_copy_sha256=s2, ckpt_same=(s1 == s2))
log("pre-checks", json.dumps(pre))
state(phase="pre_checks", pre=pre)
if free_gb < 60 or not pre["hip_same_as_r3"] or (ck_from and not pre["ckpt_same"]):
    log("pre-checks failed; stop"); state(phase="pre_checks_failed"); sys.exit(2)

# ---------------------------------------------------------------- 計算（g_chain2.py と同じ）
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
    c.pop("ckpt_from", None)
    c["wall_limit_s"] = min(WL, max(60.0, max_h * 3600 - (time.time() - T0)))
    while hython_running():
        time.sleep(5)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    state(phase="running", f0=f0, ckpt_every=sp)
    with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + " ckpt_every %d\n" % sp); lg.flush()
        subprocess.run([HY, RUN, json.dumps(c)], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL,
                       creationflags=BELOW_NORMAL)
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        log("no run record for chunk", f0, "(crash?)"); state(phase="crash", f0=f0); break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    log(rid, "chunk", f0, "ckpt_every", sp, "done to", done, "stopped", r["stopped"], "wall", r["wall_total_s"],
        "s/frame", r["wall_per_frame_median_s"], "sub", r.get("substeps_min_max"), "pts", r.get("particles_max"), "rss", r.get("rss_peak_gb"),
        "pexp", json.dumps(r.get("pexp", {}).get("states")))
    state(phase="ran", last_chunk=f0, done_to=done, stopped=r["stopped"])
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
st = json.load(open(STATE, encoding="utf8"))
finished = st.get("done_to", 0) >= f_end
state(phase="chain_end", finished=finished, elapsed_h=round((time.time() - T0) / 3600, 3))
if DO_AFTER and finished:
    log("start after:", AFTER)
    with open(os.path.join(R, "after_stdout.txt"), "a", encoding="utf8", errors="ignore") as fh:
        rc_ = subprocess.run([sys.executable, AFTER, rd], stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=BELOW_NORMAL).returncode
    log("after exit", rc_)
    state(phase="after_end", after_exit=rc_)
