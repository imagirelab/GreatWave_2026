# -*- coding: utf-8 -*-
"""P3 の原画カメラのシルエット（記録だけ。合否には使わない）（py -3.10）。
置き方は R18 のいちばん原画に近い瞬間のまま固定（ψ 30°、倍率 1.1、頂 (566, 18.13, 0) を原画の頂の画素へ）。
- R18：R18 の粗い網目（水槽全体、頂の近く x 406〜656 m）
- P3：P3 の細かい網目（箱の中）＋ 箱の外は R18 の粗い網目（ctx）
使い方: py -3.10 p3_paint.py <run_dir> <f1,f2,...>  → <run_dir>/paint_fit.json
"""
import sys, os, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p2_common as C  # noqa: E402
import p3_figs as F  # noqa: E402

SC = 0.5


def sil(cam, best, layers):
    Ps, Ts, n = [], [], 0
    for P, tri in layers:
        keep = (P[:, 0] > best["anchor"][0] - 160) & (P[:, 0] < best["anchor"][0] + 90)
        tk = tri[keep[tri].all(1)]
        Ps.append(P); Ts.append(tk + n); n += len(P)
    P = np.concatenate(Ps); tri = np.concatenate(Ts)
    U, O = C.place(P, best["anchor"], best["psi_deg"], best["scale"], cam)
    return C.raster_mask(cam, U, tri)


def main(rd, frames, own=False):
    best = F.best_place()
    cam = C.painting_cam(SC)
    pm, outer, inner = C.painting_mask(SC)
    win = C.window_mask(SC)
    out = []
    for f in frames:
        row = {"frame": f, "t": (f - 1) / 24.0}
        mp, g = F.r18_mesh_near(f)
        d = np.load(mp)
        cases = {"R18": [(d["P"].astype(np.float64), d["tri"].astype(np.int64))]}
        fm = os.path.join(rd, "mesh", "mesh_%04d.npz" % f)
        if os.path.isfile(fm):
            a = np.load(fm); b = np.load(F.ctx_mesh(rd, f))
            cases["P3"] = [(a["P"].astype(np.float64), a["tri"].astype(np.int64)), (b["P"].astype(np.float64), b["tri"].astype(np.int64))]
        row["r18_frame"] = g
        for k, L in cases.items():
            m = sil(cam, best, L) & win
            inter = (m & pm).sum(); uni = (m | (pm & win)).sum()
            row[k] = {"iou": float(inter / max(uni, 1)), "recall_painting_covered": float(inter / max((pm & win).sum(), 1)),
                      "outside_covered": float((m & ~pm).sum() / max((win & ~pm).sum(), 1)),
                      "outline_dist": C.outline_distance(m, outer, inner, SC)}
        print(f, "t=%.2f" % row["t"], {k: (round(row[k]["iou"], 3), round(row[k]["outline_dist"]["mean_px"], 1) if row[k]["outline_dist"] else None) for k in cases})
        out.append(row)
    json.dump({"placement": best, "rows": out, "note": "記録だけ。置き方は %s のまま固定。P3 は箱の外を R18 で埋めた" % ("P3 自身の place_p3.json" if own else "R18 の best")},
              open(os.path.join(rd, "paint_fit_own.json" if own else "paint_fit.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    own = "--own" in sys.argv
    if own:
        sys.argv.remove("--own")
        F.OWN["rd"] = sys.argv[1]
    main(sys.argv[1], [int(v) for v in sys.argv[2].split(",")], own)
