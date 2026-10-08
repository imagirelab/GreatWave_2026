# -*- coding: utf-8 -*-
"""FLIP41 確かめ：計算 1 本を、1 回 30 分以内の起動に区切って最後まで続ける（途中保存から再開）。FLIP39 の e_chain.py と同じ形。
py -3.10 v_chain.py '<cfg JSON>'   重い計算は一度に一つ（動いている hython の終わりを待つ）。"""
import sys, json, os, glob, subprocess, time
R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify/runs"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
RUN = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41/v_run.py"
cfg = json.loads(sys.argv[1]) if not os.path.exists(sys.argv[1]) else json.load(open(sys.argv[1], encoding="utf8"))
rid = cfg["run_id"]; rd = os.path.join(R, rid)
os.makedirs(rd, exist_ok=True)
json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


f0 = 1
for _ in range(12):
    rc = os.path.join(rd, "run_c%04d.json" % f0)
    if not os.path.exists(rc):
        c = dict(cfg, f_start=f0)
        while hython_running():
            time.sleep(5)
        env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/tmp_houdini")
        with open(os.path.join(rd, "log_c%04d.txt" % f0), "w", encoding="utf8", errors="ignore") as lg:
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n"); lg.flush()
            subprocess.run([HY, RUN, json.dumps(c)], stdout=lg, stderr=subprocess.STDOUT, env=env)
            lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    if not os.path.exists(rc):
        print("no run record for chunk", f0, "(crash?)", flush=True)
        break
    r = json.load(open(rc, encoding="utf8"))
    done = int(r["f_end_done"] or 0)
    print(time.strftime("%H:%M:%S"), rid, "chunk", f0, "done to", done, "stopped", r["stopped"], "wall", r["wall_total_s"], flush=True)
    if done >= int(cfg["f_end"]) or not (r["stopped"] or "").startswith("wall_limit"):
        break
    ck = sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))
    ck = [k for k in ck if k <= done]
    if not ck:
        print("no checkpoint"); break
    f0 = ck[-1] + 1
print("chain end", rid, flush=True)
