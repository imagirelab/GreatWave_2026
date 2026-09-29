# -*- coding: utf-8 -*-
"""設計37 第「流れに沿う線」部の図（py -3.10）。ds37_flow_eval.py の関数を使う。

fig_ds37_formation_bands.png：原画視点の形成（t 4・6・8・9・10・12 s、白の時間場あり）に、t* で藍中に見える縞の面の点（縞ごとの色の点）を
  同じ面の点のまま各時刻の頂点で投影して重ねた図（見えている点だけ）。縞が面とともに動くことを見る。
fig_ds37_sway_triptych.png：座席から波の方向（t 9 s）と座席（t*）の目の左右 −0.1・0・+0.1 m の拡大（同じ所）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds37/ds37_figs.py
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds37_flow_eval as E  # noqa: E402


def band_points():
    """ds37_flow_eval.eval_177 と同じ帯（美術優先31 の藍中の帯 25 本）の t* の面の点。"""
    hs = E.SHEETS['hero']
    uv3 = np.fromfile(E.REP['heroUv3Path'], np.float32).reshape(hs['rows'], hs['cols'], 2)
    raw = np.fromfile(E.REP['heroSdfPath'], np.uint8).reshape(4096, 4096, 4)
    cls = raw.argmax(-1).astype(np.uint8)
    _, lab = cv2.connectedComponents((cls == 2).astype(np.uint8), connectivity=8)
    truth = json.load(open(E.COL_DIR + '/colour_truth.json', encoding='utf-8'))
    polys = {r['id']: r for r in json.load(open(E.COL_DIR + '/colour_polylines.json', encoding='utf-8'))['regions']}
    fr = E.one('flowk', view='painting', t=12.0)
    sid, col, row = E.load_coord(fr['coord'])
    L = E.labels(E.imread_rgb(fr['colourWhiteOn']))
    out = []
    for bd in truth['stripes']['ai_mid_bands']:
        pm = E._poly_mask(polys[bd['region']]) & (sid == 1) & (L == 2)
        if not pm.any():
            continue
        c, r = col[pm].astype(np.float64), row[pm].astype(np.float64)
        _, comp = E._texel_class_comp(uv3, cls, lab, c, r)
        ids, cnt = np.unique(comp[comp > 0], return_counts=True)
        keep = [int(i) for i, n in zip(ids, cnt) if n >= 0.1 * len(comp)]
        sel = np.isin(comp, keep)
        out.append((bd['region'], c[sel], r[sel]))
    return out


def main():
    bands = band_points()
    rng = np.random.default_rng(37)
    cols = [tuple(int(v) for v in rng.integers(60, 255, 3)) for _ in bands]
    tiles = []
    for t in (4.0, 6.0, 8.0, 9.0, 10.0, 12.0):
        fr = E.one('flowk', view='painting', t=t)
        im = E.imread_rgb(fr['colourWhiteOn'])
        vis = (0.6 * im + 0.4 * 255).astype(np.uint8)
        s2, c2, r2 = E.load_coord(fr['coord'])
        for (b, cb, rb), cc in zip(bands, cols):
            idx = np.arange(len(cb))[:: max(1, len(cb) // 400)]
            X = E.surf_point(E.verts('hero', t), cb[idx], rb[idx])
            p, _ = E.project(X, fr)
            xi, yi = np.rint(p[:, 0]).astype(int), np.rint(p[:, 1]).astype(int)
            ok = (xi >= 0) & (xi < E.W) & (yi >= 0) & (yi < E.H)
            xi, yi, cq, rq = xi[ok], yi[ok], cb[idx][ok], rb[idx][ok]
            v = (s2[yi, xi] == 1) & (np.abs(c2[yi, xi] - cq) < 0.75) & (np.abs(r2[yi, xi] - rq) < 0.75)
            for x, y in zip(xi[v], yi[v]):
                cv2.circle(vis, (int(x), int(y)), 2, cc, -1)
        crop = vis[100:820, 0:1280]
        crop = cv2.resize(crop, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.putText(crop, 't {:.0f} s'.format(t), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
        tiles.append(crop)
    fig = np.concatenate([np.concatenate(tiles[:3], 1), np.concatenate(tiles[3:], 1)], 0)
    fig = cv2.copyMakeBorder(fig, 0, 1080 - fig.shape[0], 0, 1920 - fig.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(fig, 'painting view, wave and sea only (crop x 0-1280, y 100-820): dots = surface points of the 25 ai_mid stripes at t* (one colour per stripe), '
                'moved with the surface vertices; only points visible at that time', (10, 1060), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(E.FIG + '/fig_ds37_formation_bands.png', fig[:, :, ::-1])

    rows = []
    for view, t, box in (('seat_toward_wave', 9.0, (560, 300, 1200, 660)), ('seat', 12.0, (0, 250, 900, 700))):
        x0, y0, x1, y1 = box
        tri = []
        for dx in (-0.1, 0.0, 0.1):
            fr = E.one('sway', view=view, t=t, dx=dx)
            im = E.imread_rgb(fr['colourWhiteOn'])[y0:y1, x0:x1]
            im = cv2.resize(im, (640, int(640 * (y1 - y0) / (x1 - x0))), interpolation=cv2.INTER_AREA)
            cv2.putText(im, '{} t {:.0f} s eye {:+.1f} m'.format(view, t, dx), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
            tri.append(im)
        hh = max(x.shape[0] for x in tri)
        tri = [cv2.copyMakeBorder(x, 0, hh - x.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for x in tri]
        rows.append(np.concatenate(tri, 1))
    fig = np.concatenate(rows, 0)
    fig = cv2.copyMakeBorder(fig, 0, max(0, 1080 - fig.shape[0]), 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))[:1080]
    fig = cv2.resize(fig, (1920, 1080 * 1920 // fig.shape[1]) if fig.shape[1] != 1920 else (1920, fig.shape[0]))
    cv2.imwrite(E.FIG + '/fig_ds37_sway_triptych.png', fig[:, :, ::-1])
    print('figs done')


if __name__ == '__main__':
    main()
