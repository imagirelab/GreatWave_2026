# -*- coding: utf-8 -*-
"""P2 の途中保存からの続き（部分 B）を、元の計算（部分 A）の出力に合わせて一本にする（py -3.10）。
使い方: py -3.10 p2_merge.py <run_id_A> <run_id_B> [note]
- 部分 A：P2/<run_id_A>（途中で止まった計算。hf.npz・crest.npy は 96 コマごとに書かれている）
- 部分 B：P2/<run_id_B>（run_p2.py を f_start = 途中保存のコマ + 1、ckpt_dir = A の ckpt で走らせたもの）
A の hf.npz と crest.npy のうち B の始まりより前のコマと、B の全部をつなぐ。sec・mesh は B の分を A のフォルダーへ写す
（同じコマは B で上書き。途中保存からの続きは止めずに計算したものと同じになる：P0 の確かめ）。
A の run.json を新しく書き、Unity/Build/FLIP37/runs.jsonl に 1 行足す。
"""
import sys, os, json, glob, shutil, time
import numpy as np

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
P2 = ROOT + "/P2"
ra, rb = sys.argv[1], sys.argv[2]
note = sys.argv[3] if len(sys.argv) > 3 else ""
A, B = os.path.join(P2, ra), os.path.join(P2, rb)
rbj = json.load(open(os.path.join(B, "run.json"), encoding="utf8"))
fb0 = int(rbj["f_start"])
ha, hb = np.load(os.path.join(A, "hf.npz")), np.load(os.path.join(B, "hf.npz"))
ka = ha["frames"] < fb0
assert ha["frames"][ka].max() == fb0 - 1, ("A の hf.npz が B の始まりの前のコマまでない", ha["frames"].max(), fb0)
ga, gb = json.loads(str(ha["grid"])), json.loads(str(hb["grid"]))
out = {}
for k in ("eta", "seg", "frames", "t", "wall", "npts", "lvl"):
    out[k] = np.concatenate([ha[k][ka], hb[k]])
np.savez_compressed(os.path.join(A, "hf.npz"), grid=json.dumps(gb), **out)
ca, cb = np.load(os.path.join(A, "crest.npy")), np.load(os.path.join(B, "crest.npy"))
np.save(os.path.join(A, "crest.npy"), np.concatenate([ca[ca[:, 0] < fb0], cb]))
nf = 0
for sub in ("sec", "mesh"):
    for f in glob.glob(os.path.join(B, sub, "**", "*.npz"), recursive=True):
        dst = os.path.join(A, os.path.relpath(f, B))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(f, dst); nf += 1
wa = ha["wall"][ka]
rec = dict(rbj)
rec.update({
    "run_id": ra, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "f_start": 1,
    "particles_first": int(ha["npts"][0]), "particles_max": int(max(ha["npts"][ka].max(), hb["npts"].max())),
    "wall_total_s": round(float(wa.sum()) + float(rbj["wall_total_s"]), 1),
    "wall_per_frame_median_s": round(float(np.median(np.concatenate([wa[1:], hb["wall"][1:]]))), 3),
    "level_start_m": float(ha["lvl"][0]), "level_min_m": float(min(ha["lvl"][ka].min(), hb["lvl"].min())),
    "parts": [{"run_id": ra, "frames": [1, fb0 - 1], "wall_sim_s": round(float(wa.sum()), 1),
               "wall_per_frame_median_s": round(float(np.median(wa[1:])), 3), "concurrent_with": None},
              {"run_id": rb, "frames": [fb0, int(rbj["f_end_done"])], "wall_total_s": rbj["wall_total_s"],
               "wall_per_frame_median_s": rbj["wall_per_frame_median_s"], "concurrent_with": rbj.get("concurrent_with")}],
    "merged_note": note, "merged_files": nf,
})
json.dump(rec, open(os.path.join(A, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps({"stage": "P2", "run_id": ra + "_merged", "date": rec["date"], "parms": rec["parms"],
                         "f_start": 1, "f_end_done": rec["f_end_done"], "particles_max": rec["particles_max"],
                         "wall_total_s": rec["wall_total_s"], "rss_peak_gb": rec.get("rss_peak_gb"), "stopped": rec.get("stopped"),
                         "parts": rec["parts"], "note": note}, ensure_ascii=False, default=str) + "\n")
print("merged", ra, "frames", int(out["frames"][0]), "-", int(out["frames"][-1]), "files", nf)
