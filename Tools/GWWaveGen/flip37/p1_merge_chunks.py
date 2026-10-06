# -*- coding: utf-8 -*-
"""P1：途中保存で区切って走らせた計算（<id>_A, <id>_B, ...）を 1 つのフォルダー <id> にまとめる（py -3.10）。
使い方: py -3.10 p1_merge_chunks.py <id> <chunk_id> <chunk_id> ...
snap_*.npz は複製し、eta.npz と crest.npy はつなぎ、run.json は最初の区切りの条件に、区切りごとの時間などを chunks として足す。"""
import sys, os, json, shutil, glob
import numpy as np
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1"
out = os.path.join(ROOT, sys.argv[1]); os.makedirs(out, exist_ok=True)
chunks = sys.argv[2:]
etas, cr, recs = [], [], []
for c in chunks:
    d = os.path.join(ROOT, c)
    for f in glob.glob(os.path.join(d, "snap_*.npz")):
        shutil.copy2(f, out)
    e = np.load(os.path.join(d, "eta.npz")); etas.append({k: e[k] for k in e.files})
    cr.append(np.load(os.path.join(d, "crest.npy")))
    recs.append(json.load(open(os.path.join(d, "run.json"), encoding="utf8")))
E = {k: (np.concatenate([x[k] for x in etas]) if k != "x" else etas[0]["x"]) for k in etas[0]}
np.savez_compressed(os.path.join(out, "eta.npz"), **E)
np.save(os.path.join(out, "crest.npy"), np.concatenate(cr))
r = dict(recs[0]); r["run_id"] = sys.argv[1]
r["f_end_done"] = recs[-1]["f_end_done"]
r["wall_total_s"] = round(sum(x["wall_total_s"] for x in recs), 1)
r["particles_max"] = max(x["particles_max"] for x in recs)
r["rss_peak_gb"] = max(x["rss_peak_gb"] for x in recs)
r["wall_per_frame_median_s"] = float(np.median(E["wall"][1:]))
r["stopped"] = [x["stopped"] for x in recs]
r["chunks"] = [{k: x[k] for k in ("run_id", "f_start", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped", "ckpt_files", "ckpt_gb", "hip_sha256")} for x in recs]
json.dump(r, open(os.path.join(out, "run.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=str)
print("merged", out, len(glob.glob(os.path.join(out, "snap_*.npz"))), "snaps", r["wall_total_s"], "s")
