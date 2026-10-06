# -*- coding: utf-8 -*-
"""組み込みの準備の図（cv2 だけ。matplotlib は無い）。
1. sections_<seq>.png：いくつかの時刻・行の、流体の切り口（灰）と方法 A の 400 列（10 列ごとの点）と目印（色）。
2. metrics_<seq>.png：当てはまり・飛び・跳びの時間の変化。
使い方：py -3.10 integ_figs.py <seq> [sections|metrics|all]
"""
import os, sys, json, glob
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C
from integ_convert import SEQS

FONT = cv2.FONT_HERSHEY_SIMPLEX
KCOL = [(120, 120, 120), (0, 140, 255), (0, 0, 220), (200, 0, 200), (220, 120, 0), (0, 160, 0), (90, 90, 90), (60, 60, 60)]


def panel(curves, G_row, kn_cols, title, W=640, H=300, xr=None, yr=(-14, 26)):
    img = np.full((H, W, 3), 250, np.uint8)
    if xr is None:
        xr = (G_row[:, 0].min() - 3, G_row[:, 0].max() + 3)
    sx = (W - 20) / (xr[1] - xr[0]); sy = (H - 40) / (yr[1] - yr[0])
    sc = min(sx, sy)
    def tp(p):
        return np.stack([10 + (p[:, 0] - xr[0]) * sc, H - 10 - (p[:, 1] - yr[0]) * sc], 1).astype(np.int32)
    cv2.line(img, tuple(tp(np.array([[xr[0], 0.0]]))[0]), tuple(tp(np.array([[xr[1], 0.0]]))[0]), (210, 210, 210), 1)
    for c in curves:
        cv2.polylines(img, [tp(c)], False, (160, 160, 160), 3, cv2.LINE_AA)
    cv2.polylines(img, [tp(G_row)], False, (40, 40, 40), 1, cv2.LINE_AA)
    for j in range(0, C.NU, 10):
        cv2.circle(img, tuple(tp(G_row[j:j + 1])[0]), 2, (40, 40, 40), -1, cv2.LINE_AA)
    for k, j in enumerate(C.KNOTS_J):
        cv2.circle(img, tuple(tp(G_row[j:j + 1])[0]), 5, KCOL[k], -1, cv2.LINE_AA)
    cv2.putText(img, title, (8, 18), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def sections(seq, times=None, rows_c=None):
    cfg = SEQS[seq]
    od = C.OUT + "/" + seq
    zrows = cfg["zc"] + np.linspace(cfg["c"][0], cfg["c"][1], C.NV)
    fs = sorted(glob.glob(od + "/sheet_sim_*.npy"))
    fr = [int(os.path.basename(f)[10:14]) for f in fs]
    ts = np.array([(f - 1) / 24.0 for f in fr])
    if times is None:
        times = np.linspace(ts[0], ts[-1], 5)
    if rows_c is None:
        rows_c = [cfg["c"][0] * 0.7, 0.0, cfg["c"][1] * 0.7]
    tiles = []
    for t in times:
        i = int(np.argmin(np.abs(ts - t)))
        G = np.load(fs[i])
        d = np.load(cfg["mesh_dir"] + "/mesh_%04d.npz" % fr[i])
        P = d["P"].astype(float); tri = d["tri"].astype(np.int64)
        row_tiles = []
        for c in rows_c:
            r = int(np.argmin(np.abs(zrows - (cfg["zc"] + c))))
            ch = C.slice_mesh_z(P, tri, zrows[r])
            curves = [cc for cc, _ in ch]
            Gr = G[r, :, :2]
            xt = Gr[90, 0]
            row_tiles.append(panel(curves, Gr, None, "%s t=%.2fs row c=%+.0fm" % (seq, ts[i], c), xr=(xt - 80, xt + 75)))
        tiles.append(np.concatenate(row_tiles, 1))
    img = np.concatenate(tiles, 0)
    leg = np.full((30, img.shape[1], 3), 255, np.uint8)
    names = ["B j0", "back foot j18", "top j90", "lip tip j200", "tube corner j314", "face bottom j379", "E0 j394", "E j399"]
    x = 8
    for k, n in enumerate(names):
        cv2.circle(leg, (x + 5, 15), 5, KCOL[k], -1, cv2.LINE_AA)
        cv2.putText(leg, n, (x + 14, 20), FONT, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        x += 14 + 9 * len(n) + 12
    img = np.concatenate([leg, img], 0)
    cv2.imwrite(od + "/sections_%s.png" % seq, img)
    print("wrote", od + "/sections_%s.png" % seq)


def plot_series(img, x0, y0, w, h, xs, series, title, ylab, ymax=None):
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (200, 200, 200), 1)
    cv2.putText(img, title, (x0 + 4, y0 - 6), FONT, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    allv = np.concatenate([np.asarray(s[1], float) for s in series])
    allv = allv[np.isfinite(allv)]
    top = ymax if ymax else (allv.max() * 1.1 if len(allv) else 1)
    xa, xb = min(xs[0] for xs in [s[0] for s in series]), max(xs[-1] for xs in [s[0] for s in series])
    for (xx, yy, col, name) in series:
        xx = np.asarray(xx, float); yy = np.clip(np.asarray(yy, float), 0, top)
        pts = np.stack([x0 + (xx - xa) / max(xb - xa, 1e-6) * w, y0 + h - yy / top * h], 1).astype(np.int32)
        cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
    cv2.putText(img, "%.2f %s" % (top, ylab), (x0 + 4, y0 + 14), FONT, 0.4, (90, 90, 90), 1, cv2.LINE_AA)
    cv2.putText(img, "t %.2f..%.2f s" % (xa, xb), (x0 + w - 130, y0 + h + 14), FONT, 0.4, (90, 90, 90), 1, cv2.LINE_AA)
    yl = y0 + 18
    for (_, _, col, name) in series:
        cv2.putText(img, name, (x0 + w - 230, yl), FONT, 0.4, col, 1, cv2.LINE_AA); yl += 14


def metrics(seq):
    od = C.OUT + "/" + seq
    m = json.load(open(od + "/metrics.json", encoding="utf8"))["metrics"]
    img = np.full((760, 1300, 3), 255, np.uint8)
    f = m["fit_fluid_to_sheet"]
    plot_series(img, 40, 40, 580, 300, None, [([x["t"] for x in f], [x["p95"] for x in f], (200, 0, 0), "fluid->sheet p95"),
                                              ([x["t"] for x in f], [x["p99"] for x in f], (0, 0, 200), "fluid->sheet p99"),
                                              ([x["t"] for x in m["fit_sheet_mid_to_fluid"]], [x["p99"] for x in m["fit_sheet_mid_to_fluid"]], (0, 150, 0), "sheet mid->fluid p99")],
                "fit error (m)", "m", ymax=None)
    a = m["A_d2"]; s = m["A_step"]
    plot_series(img, 680, 40, 580, 300, None, [([x["t"] for x in a], [x["p99"] for x in a], (0, 0, 200), "A |d2P| p99"),
                                               ([x["t"] for x in a], [x["max"] for x in a], (200, 0, 0), "A |d2P| max"),
                                               ([x["t"] for x in s], [x["p99"] for x in s], (0, 150, 0), "A step p99")],
                "sheet (A) frame-to-frame (m)", "m")
    b = m["B_jump"]
    plot_series(img, 40, 420, 580, 300, None, [([x["t"] for x in b], [x["p95"] for x in b], (200, 0, 0), "B jump p95"),
                                               ([x["t"] for x in b], [x["p99"] for x in b], (0, 0, 200), "B jump p99"),
                                               ([x["t"] for x in s], [x["p95"] for x in s], (0, 150, 0), "A step p95")],
                "surface jump between data frames when not interpolated (m)", "m")
    c = m["B_components"]
    plot_series(img, 680, 420, 580, 300, None, [([x["t"] for x in c], [x["n"] for x in c], (200, 0, 0), "B pieces"),
                                                ([x["t"] for x in c], [x["small_lt50"] for x in c], (0, 0, 200), "B pieces <50 tris")],
                "per-frame mesh (B) separate pieces", "")
    cv2.imwrite(od + "/metrics_%s.png" % seq, img)
    print("wrote", od + "/metrics_%s.png" % seq)


if __name__ == "__main__":
    seq = sys.argv[1]
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    if what in ("sections", "all"):
        sections(seq)
    if what in ("metrics", "all"):
        metrics(seq)
