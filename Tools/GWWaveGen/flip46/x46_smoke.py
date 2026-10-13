# -*- coding: utf-8 -*-
"""FLIP46：煙の試しを 1 回の起動で走らせる（py -3.10）。ほかの hython が動いていれば待つ（重い計算は一度に一つ）。
hython の優先度は「通常より下」・電力の抑えなし（g46_run.py が自分に頼む）。1 本は 10 分より短い物だけ（cfg の wall_limit_s 560 s）。
使い方：py -3.10 x46_smoke.py <cfg.json> [<cfg.json> ...]   （例：Unity/Build/FLIP46/smoke/ready/SA_dp1p0.json）
出力：Unity/Build/FLIP46/smoke/<run_id>/、smoke/driver_log.txt
"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC

SM = GC.B46 + "/smoke"
TMP = GC.B46 + "/tmp_houdini"
os.makedirs(SM, exist_ok=True); os.makedirs(TMP, exist_ok=True)
GC.unthrottle_self()


def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    open(SM + "/driver_log.txt", "a", encoding="utf8").write(msg + "\n")


def single(cfg):
    rd = os.path.join(GC.B46, cfg.get("out_root", "smoke"), cfg["run_id"])
    os.makedirs(rd, exist_ok=True)
    p = os.path.join(rd, "cfg.json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    GC.wait_no_hython(log=log)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    t0 = time.time()
    with open(os.path.join(rd, "log_c%05d.txt" % int(cfg["f_start"])), "w", encoding="utf8", errors="ignore") as lg:
        subprocess.run([GC.HY, GC.TOOLS + "/g46_run.py", p], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL,
                       timeout=600)
    r = os.path.join(rd, "run_c%05d.json" % int(cfg["f_start"]))
    rec = json.load(open(r, encoding="utf8")) if os.path.exists(r) else {}
    log(cfg["run_id"], "done %.0f s" % (time.time() - t0), "f_end_done", rec.get("f_end_done"), "stopped", rec.get("stopped"),
        "s/frame", rec.get("wall_per_frame_median_s"), "pts", rec.get("particles_max"), "rss", rec.get("rss_peak_gb"))


if __name__ == "__main__":
    for it in sys.argv[1:]:
        c = json.load(open(it, encoding="utf8"))
        log("start", c["run_id"], "f_end", c["f_end"])
        try:
            single(c)
        except Exception as e:
            log("ERROR", c["run_id"], repr(e)[:400])
