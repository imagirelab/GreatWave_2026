# -*- coding: utf-8 -*-
"""FLIP45：煙の試しを走らせる（py -3.10。計画 plan_ja.md §10.2）。一度に一つ、ほかの hython が動いていれば待つ。
hython は g45_run.py（1 回の起動）か g45_chain.py（30 分を越える物）で走らせ、優先度は「通常より下」・電力の抑えなし（g45_run.py が自分に頼む）。
使い方：
  py -3.10 x45_smoke.py S1:0.5 S1:0.34375 S2b:0.25 S3:36 S3b:72 S2a:30 S2c:45 S5 S10:1.0 ...
  各項目は <種類>[:<値>]。S1・S2b・S10 の値は粒子、S3・S3b は帯の厚さ、S2a・S2c は角。
出力：Unity/Build/FLIP45/smoke/<id>/（cfg.json・記録）、smoke/driver_log.txt
"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_cfg as C

SM = GC.B45 + "/smoke"
TMP = GC.B45 + "/tmp_houdini"
os.makedirs(SM, exist_ok=True); os.makedirs(TMP, exist_ok=True)
GC.unthrottle_self()


def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    open(SM + "/driver_log.txt", "a", encoding="utf8").write(msg + "\n")


def cfg_of(item):
    kind, _, val = item.partition(":")
    if kind == "S1":
        return C.smoke("S1", dp=float(val or 0.5))
    if kind == "S2b":
        return C.smoke("S2b", dp=float(val or 0.5))
    if kind in ("S3", "S3b"):
        return C.smoke(kind, dp=0.5, band=float(val or 36))
    if kind in ("S2a", "S2c"):
        return C.smoke(kind, dp=0.5, theta=float(val))
    if kind == "S10":
        return C.smoke("S10", dp=float(val or 1.0))
    if kind == "S10b":                    # 2026-10-12：R2 の断面の情報の誤りを直した後の S10 の走らせ直し（別の置き場所）
        return C.smoke("S10", dp=float(val or 1.0), tag="S10b_dp%s" % repr(float(val or 1.0)).replace(".", "p"))
    if kind == "S5":
        return C.smoke("S5", dp=0.5)
    if kind == "S6b":
        return C.smoke("S6b", dp=float(val or 0.25))
    raise SystemExit("知らない項目 %s" % item)


def single(cfg):
    rd = os.path.join(SM, cfg["run_id"])
    os.makedirs(rd, exist_ok=True)
    cfg = C.table_for(cfg)
    p = os.path.join(rd, "cfg.json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    GC.wait_no_hython(log=log)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    t0 = time.time()
    with open(os.path.join(rd, "log_c%05d.txt" % int(cfg["f_start"])), "w", encoding="utf8", errors="ignore") as lg:
        subprocess.run([GC.HY, GC.TOOLS + "/g45_run.py", p], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    r = os.path.join(rd, "run_c%05d.json" % int(cfg["f_start"]))
    rec = json.load(open(r, encoding="utf8")) if os.path.exists(r) else {}
    log(cfg["run_id"], "done %.0f s" % (time.time() - t0), "f_end_done", rec.get("f_end_done"), "stopped", rec.get("stopped"),
        "s/frame", rec.get("wall_per_frame_median_s"), "pts", rec.get("particles_max"), "rss", rec.get("rss_peak_gb"))


def chained(cfg):
    rd = os.path.join(SM, cfg["run_id"])
    os.makedirs(rd, exist_ok=True)
    cfg = C.table_for(cfg)
    p = os.path.join(rd, "cfg_in.json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    t0 = time.time()
    subprocess.run([sys.executable, GC.TOOLS + "/g45_chain.py", p], stdin=subprocess.DEVNULL)
    log(cfg["run_id"], "chain done %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    for it in sys.argv[1:]:
        c = cfg_of(it)
        log("start", it, c["run_id"], "f_end", c["f_end"])
        try:
            if it.startswith(("S2a", "S2c", "S10")):          # S10b も
                chained(c)
            else:
                single(c)
        except Exception as e:
            log("ERROR", it, repr(e)[:400])
