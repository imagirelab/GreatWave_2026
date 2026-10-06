# -*- coding: utf-8 -*-
"""P3 の主役の範囲の計算を、30 分以内の区切り（A, B, C, ...）で途中保存から続けて最後まで走らせる（py -3.10）。
重い計算は一度に一つだけ（区切りは順に走る）。
使い方: py -3.10 p3_chain.py '<run_p3.py へ渡す JSON（run_id, parms, f_end, ckpt_every など）>' または <その JSON のファイル> [最初の区切りの文字 A] [最初のコマ]
- 区切りが「chunk_end」「wall_limit」で止まったら、最後の途中保存のコマ + 1 から次の区切りを始める。
- 止まった理由が free_fall / error のとき、または同じコマから 2 回進まなかったときは、そこでやめる。
各区切りの記録は run_p3.py が runs.jsonl と <run_id>/run_<part>.json に書く。
"""
import sys, os, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3"
HYTHON = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/tmp")

ARG = sys.argv[1]


def load_base():
    """引数が JSON のファイルなら、区切りごとに読み直す（途中で網目の間隔などを変えられるように）。"""
    if os.path.isfile(ARG):
        return json.load(open(ARG, encoding="utf8"))
    return json.loads(ARG)


base = load_base()
part = sys.argv[2] if len(sys.argv) > 2 else "A"
F0 = int(base["parms"].get("F0", 72))
f_start = int(sys.argv[3]) if len(sys.argv) > 3 else F0
f_end = int(base["f_end"])
rid = base["run_id"]
out = os.path.join(P3, rid)
os.makedirs(os.path.join(out, "logs"), exist_ok=True)
stuck = 0
while True:
    base = load_base()
    J = dict(base, part=part, f_start=f_start, ckpt_on=1)
    J.setdefault("ckpt_dir", os.path.join(out, "ckpt").replace("\\", "/"))
    log = os.path.join(out, "logs", "part_%s.log" % part)
    print(time.strftime("%H:%M:%S"), "start part", part, "f_start", f_start, "->", f_end, "log", log, flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf8") as fh:
        rc = subprocess.call([HYTHON, os.path.join(HERE, "run_p3.py"), json.dumps(J)], stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=out)
    rj = os.path.join(out, "run_%s.json" % part)
    if not os.path.isfile(rj):
        print(time.strftime("%H:%M:%S"), "part", part, "no run json, rc", rc, flush=True)
        break
    r = json.load(open(rj, encoding="utf8"))
    st = r.get("stopped")
    print(time.strftime("%H:%M:%S"), "part", part, "done f", r.get("f_end_done"), "stopped", st, "wall %.0f s" % (time.time() - t0),
          "per frame", r.get("wall_per_frame_median_s"), "pts max", r.get("particles_max"), "rss peak", r.get("rss_peak_gb"), flush=True)
    if st is None:
        print("finished", rid, flush=True)
        break
    if not (st.startswith("chunk_end") or st.startswith("wall_limit")):
        print("stop:", st, flush=True)
        break
    lc = r.get("last_ckpt_frame")
    if lc is None or lc + 1 <= f_start:
        stuck += 1
        if stuck >= 2 or lc is None:
            print("stop: no progress past a checkpoint", flush=True)
            break
    nxt = lc + 1
    f_start = nxt
    part = chr(ord(part) + 1)
