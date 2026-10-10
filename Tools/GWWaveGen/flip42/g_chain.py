# -*- coding: utf-8 -*-
"""FLIP42：計算 1 本を、1 回 30 分以内の起動に区切って最後まで続ける（途中保存から再開）。FLIP41 の v_chain.py と同じ形。
py -3.10 g_chain.py <cfg.json>   重い計算は一度に一つ（動いている hython の終わりを待つ）。
止める：runs/<run_id>/STOP を置くと、今の起動の後で止まる。
max_hours（cfg に書けば）：始めからの経過がこれを越えたら、次の起動をしないで止める（見込みの 2 倍で止める決まりのため）。"""
import sys, json, os, glob, subprocess, time
R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
RUN = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/g_run.py"
cfg = json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]; rd = os.path.join(R, rid)
os.makedirs(rd, exist_ok=True)
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
T0 = time.time()
max_h = float(cfg.get("max_hours", 1e9))


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


f0 = 1
for _ in range(60):
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        if os.path.exists(os.path.join(rd, "STOP")):
            print("STOP found", flush=True); break
        if (time.time() - T0) / 3600 > max_h:
            print("max_hours exceeded (%.2f h > %.2f h); stop" % ((time.time() - T0) / 3600, max_h), flush=True); break
        c = dict(cfg, f_start=f0)
        c["wall_limit_s"] = min(float(cfg.get("wall_limit_s", 1740)), max(60.0, max_h * 3600 - (time.time() - T0)))
        while hython_running():
            time.sleep(5)
        env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini",
                   TEMP=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini", TMP=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini")
        with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n"); lg.flush()
            subprocess.run([HY, RUN, json.dumps(c)], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    if not os.path.exists(rc):
        print("no run record for chunk", f0, "(crash?)", flush=True)
        break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    print(time.strftime("%H:%M:%S"), rid, "chunk", f0, "done to", done, "stopped", r["stopped"], "wall", r["wall_total_s"],
          "s/frame", r["wall_per_frame_median_s"], "sub", r.get("substeps_min_max"), flush=True)
    if done >= int(cfg["f_end"]) or not (r["stopped"] or "").startswith("wall_limit"):
        break
    ck = sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))
    ck = [k for k in ck if k <= done]
    if not ck:
        print("no checkpoint"); break
    f0 = ck[-1] + 1
print("chain end", rid, "elapsed_h %.3f" % ((time.time() - T0) / 3600), flush=True)
