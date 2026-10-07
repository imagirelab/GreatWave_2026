# -*- coding: utf-8 -*-
"""FLIP39 E：1 本の計算を、1 回 30 分以内の起動に区切って最後まで続ける（途中保存から再開）。py -3.10 e_chain.py '<cfg JSON>' [--wait]
--wait：今動いている hython の終わりを待ってから、その結果から続ける（最初の起動を別に始めた時）。重い計算は一度に一つ。"""
import sys, json, os, glob, subprocess, time
E = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
cfg = json.loads(sys.argv[1]); rid = cfg["run_id"]; rd = os.path.join(E, rid)
def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()
if "--wait" in sys.argv:
    while hython_running():
        time.sleep(10)
f0 = 1
for _ in range(8):
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        c = dict(cfg, f_start=f0)
        while hython_running():
            time.sleep(5)
        env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/tmp_houdini")
        with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + chr(10)); lg.flush()
            subprocess.run([r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe",
                            r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39/e_run.py", json.dumps(c)], stdout=lg, stderr=subprocess.STDOUT, env=env)
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + chr(10))
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    print(time.strftime("%H:%M:%S"), rid, "chunk", f0, "done to", done, "stopped", r["stopped"], flush=True)
    if done >= int(cfg["f_end"]) or not (r["stopped"] or "").startswith("wall_limit"):
        break
    ck = sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "e.*.sim")))
    ck = [k for k in ck if k <= done]
    if not ck:
        print("no checkpoint"); break
    f0 = ck[-1] + 1
print("chain end", rid)
