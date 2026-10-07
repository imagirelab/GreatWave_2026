# -*- coding: utf-8 -*-
"""FLIP39 R：主役の範囲の計算（箱）と E3（粒子 1 m の粗い計算）を比べる（py -3.10、numpy）。流体の計算はしない。
使い方: py -3.10 r_compare.py <箱の run_dir> [--rows=-80,-118]
読むもの：箱の hf_*.npz（一番上の水面 η(z, x)、毎コマ、箱の格子の升）、E3 の hf_c*.npz（2 m の升）。
出すもの（<run_dir>/compare_E3.json）：
- 列ごと（z の ±2 m の帯）の頂の歩み：箱と E3 の頂の高さ・位置（箱の内側＝境界の帯 + 2 m を除く x の範囲で最も高い水面）。
- 箱の内側の水面の差の RMS（箱の水面を E3 の 2 m の升の節へ最も近い升で写して比べる）。
水面のずれ（粒子から水面を作る時のずれ）は引かずに比べる（どちらも生の値）。
"""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf

E3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/E3_dir20_lens"


def load_box(rd):
    fs = sorted(glob.glob(os.path.join(rd, "hf_*.npz")))
    E, S, F, T = [], [], [], []
    grid = None
    for f in fs:
        d = np.load(f, allow_pickle=True)
        if len(d["frames"]) == 0:
            continue
        E.append(d["eta"]); S.append(d["seg"]); F.append(d["frames"]); T.append(d["t"])
        grid = json.loads(str(d["grid"]))
    F = np.concatenate(F); E = np.concatenate(E); S = np.concatenate(S); T = np.concatenate(T)
    _, idx = np.unique(F[::-1], return_index=True)
    keep = np.sort(len(F) - 1 - idx)
    return dict(eta=E[keep].astype(np.float32), seg=S[keep], frames=F[keep], t=T[keep], grid=grid)


def main(rd, rows=(-80.0, -118.0)):
    B = load_box(rd)
    C = load_hf(E3)
    gb = B["grid"]; gc = C["grid"]
    xb = gb["x0"] + gb["dx"] * np.arange(B["eta"].shape[2]); zb = gb["z0"] + gb["dz"] * np.arange(B["eta"].shape[1])
    xc = gc["x0"] + gc["dx"] * np.arange(C["eta"].shape[2]); zc = gc["z0"] + gc["dz"] * np.arange(C["eta"].shape[1])
    wx0, wx1, wz0, wz1 = gb["window"]; pad = gb["pad"]
    rjs = sorted(glob.glob(os.path.join(rd, "run_*.json")))
    padz0 = float(json.load(open(rjs[0], encoding="utf8"))["parms"].get("padz0", pad)) if rjs else 0.0
    inx_b = (xb > wx0 + pad + 2) & (xb < wx1 - pad - 2)
    inx_c = (xc > wx0 + pad + 2) & (xc < wx1 - pad - 2)
    inz_c = (zc > wz0 + padz0 + 2 - 1e-6) & (zc < wz1 - pad - 2)
    # E3 の節に最も近い箱の升
    ixm = np.clip(np.round((xc - xb[0]) / gb["dx"]).astype(int), 0, len(xb) - 1)
    izm = np.clip(np.round((zc - zb[0]) / gb["dz"]).astype(int), 0, len(zb) - 1)
    cidx = {int(f): k for k, f in enumerate(C["frames"])}
    out = {"run_dir": rd, "rows": {}, "rms": []}
    for zr in rows:
        rb = (np.abs(zb - zr) <= 2.0); rc = (np.abs(zc - zr) <= 2.0)
        hist = []
        for k, f in enumerate(B["frames"]):
            f = int(f)
            if f not in cidx:
                continue
            eb = np.nanmax(B["eta"][k][rb][:, inx_b], axis=0); ec = np.nanmax(C["eta"][cidx[f]][rc][:, inx_c], axis=0)
            ib, ic = int(np.nanargmax(eb)), int(np.nanargmax(ec))
            hist.append([f, float(B["t"][k]), float(eb[ib]), float(xb[inx_b][ib]), float(ec[ic]), float(xc[inx_c][ic])])
        h = np.array(hist)
        out["rows"]["%g" % zr] = {"cols": ["frame", "t", "box_crest", "box_x", "E3_crest", "E3_x"], "hist": h.round(3).tolist(),
                                 "crest_max_box": float(h[:, 2].max()), "t_max_box": float(h[np.argmax(h[:, 2]), 1]), "x_max_box": float(h[np.argmax(h[:, 2]), 3]),
                                 "crest_max_E3": float(h[:, 4].max()), "t_max_E3": float(h[np.argmax(h[:, 4]), 1]), "x_max_E3": float(h[np.argmax(h[:, 4]), 5])}
    for k, f in enumerate(B["frames"]):
        f = int(f)
        if f not in cidx:
            continue
        eb = B["eta"][k][np.ix_(izm, ixm)][np.ix_(inz_c, inx_c)]; ec = C["eta"][cidx[f]][np.ix_(inz_c, inx_c)]
        d = eb - ec
        out["rms"].append([f, float(np.sqrt(np.nanmean(d ** 2))), float(np.nanmean(d)), float(np.nanmax(np.abs(d)))])
    json.dump(out, open(os.path.join(rd, "compare_E3.json"), "w", encoding="utf8"), indent=1)
    for zr, v in out["rows"].items():
        h = np.array(v["hist"])
        print("row z", zr, "box max %.2f m at t %.2f x %.0f | E3 max %.2f m at t %.2f x %.0f" % (
            v["crest_max_box"], v["t_max_box"], v["x_max_box"], v["crest_max_E3"], v["t_max_E3"], v["x_max_E3"]))
        for r in h[::24]:
            print("   f %d t %.2f  box %.2f @%.0f  E3 %.2f @%.0f" % tuple(r))
    r = np.array(out["rms"])
    for q in r[::24]:
        print("rms f %d  %.3f m  mean %.3f  max %.2f" % tuple(q))
    return out


if __name__ == "__main__":
    rows = (-80.0, -118.0)
    for a in sys.argv:
        if a.startswith("--rows="):
            rows = tuple(float(v) for v in a.split("=")[1].split(","))
    main(sys.argv[1], rows)
