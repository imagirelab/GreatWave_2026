# -*- coding: utf-8 -*-
"""FLIP41 確かめ：計算を一つずつ順に流す（重い計算は一度に一つ）。各計算の後に解析（v_analyze.py）も走らせる。
py -3.10 v_queue.py <queue.txt>
queue.txt：1 行 1 本。「kind key=value ...」（v_cfg.py と同じ書き方）。# で始まる行は飛ばす。
止める：verify/STOP_QUEUE というファイルを置くと、今の計算の後で止まる。解析が済んだ計算（ana.json がある）は飛ばす。
記録：verify/queue_log.txt に 1 本ごとに 1 行。"""
import sys, os, json, subprocess, time, shlex
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
import v_cfg
V = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify"
T = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41"
LOG = os.path.join(V, "queue_log.txt")


def log(s):
    with open(LOG, "a", encoding="utf8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")
    try:
        sys.stdout.buffer.write((s + chr(10)).encode("utf8", "replace")); sys.stdout.flush()
    except Exception:
        pass


def make(line):
    parts = shlex.split(line)
    kind = parts[0]
    kw = {}
    for s in parts[1:]:
        k, v = s.split("=", 1)
        try:
            kw[k] = float(v)
        except ValueError:
            kw[k] = v
    for k in ("band_vox", "minsub", "maxsub", "nb", "nwin"):
        if k in kw:
            kw[k] = int(kw[k])
    if "wind" in kw:
        kw["wind"] = bool(int(kw["wind"]))
    return dict(B1=v_cfg.b1, B2=v_cfg.b2, T1=v_cfg.t1)[kind](**kw)


lines = [l.strip() for l in open(sys.argv[1], encoding="utf8") if l.strip() and not l.strip().startswith("#")]
log("queue start %s (%d runs)" % (sys.argv[1], len(lines)))
for line in lines:
    if os.path.exists(os.path.join(V, "STOP_QUEUE")):
        log("STOP_QUEUE found; stop")
        break
    cfg = make(line)
    rid = cfg["run_id"]
    rd = os.path.join(V, "runs", rid)
    if os.path.exists(os.path.join(rd, "ana.json")):
        log("skip (done) " + rid)
        continue
    os.makedirs(rd, exist_ok=True)
    cp = os.path.join(rd, "cfg_in.json")
    json.dump(cfg, open(cp, "w", encoding="utf8"), ensure_ascii=False)
    t0 = time.time()
    log("run " + rid + " f_end " + str(cfg["f_end"]) + "  <" + line + ">")
    with open(os.path.join(rd, "chain.log"), "w", encoding="utf8") as lg:
        subprocess.run(["py", "-3.10", os.path.join(T, "v_chain.py"), cp], stdout=lg, stderr=subprocess.STDOUT)
    r = subprocess.run(["py", "-3.10", os.path.join(T, "v_analyze.py"), rid], capture_output=True, text=True, encoding="utf8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r.stdout.strip().splitlines() or [""])[0][:600]
    err = r.stderr.strip()[-400:]
    log("done %s wall %.0f s | %s %s" % (rid, time.time() - t0, out, ("ERR " + err) if err else ""))
log("queue end")
