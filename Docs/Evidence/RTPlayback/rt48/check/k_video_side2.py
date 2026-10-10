# -*- coding: utf-8 -*-
"""6c. 横からの動画の 2 コマおき：
(1) 水の塗りの食い違いのうち、自分の R3 の線から 1.5 画素（0.12 m）より離れた画素の数。船・印・字のある x 545〜583 m は別に数える。
(2) 時刻のずれ：頂が窓の中にある時（頂 ±20 m が x 470〜620 m に入る）、絵の一番上の水の高さ（列ごと）と、自分の R3 の
    コマ k−2〜k+2 の一番上の水面の高さの差の二乗平均で、最も合うコマ（見せているはずのコマとの差 dk）。
出力：out/k_video_side2.json"""
import numpy as np
from scipy import ndimage
from k_lib import *
import k_video as kv
from k_video_events import raster, xc, yc, c0, c1, r0_, r1_, sx, sy, x470, row_y0

my = MyFrames(); rows = jload(OUT + "/k_r3.json")["rows"]
BOATZ = (545.0, 583.0)
static_excl = None
out = []


def top_profile(mask):
    has = mask.any(0)
    i0 = mask.argmax(0)
    return np.where(has, yc[i0] + 0.5 / sy, np.nan)       # 一番上の水の画素の上の縁


def r3_top(f, xs):
    P = my.main_of(f)
    Ls = [np.vstack([L["pts"], L["pts"][:1]]) for L in my.loops_of(f, -1)]
    y = np.full(len(xs), np.nan)
    for j, x in enumerate(xs):
        c = list(crossings_y(P, x))
        for Q in Ls:
            c += list(crossings_y(Q, x))
        if c:
            y[j] = max(c)
    return y


for n, a in kv.read_frames(RT + "/video/rt48_side_coarse.mp4"):
    sub = a[r0_:r1_, c0:c1].astype(float)
    sky = np.array([212.0, 224.0, 230.0]); wat = np.array([28.0, 77.0, 95.0]); dv = wat - sky
    tt = ((sub - sky) @ dv) / (dv @ dv)
    resid = np.linalg.norm(sub - sky - tt[..., None] * dv, axis=2)
    isw = (tt > 0.5) & (resid < 45)
    other = (resid >= 45) | ndimage.binary_dilation((sub.min(2) > 225) | (resid >= 60), iterations=2)
    rd = int(np.floor(row_y0)) - r0_
    other[rd - 2:rd + 2, :] = True
    if static_excl is None:
        lab0, nl0 = ndimage.label(isw & ~other)
        big = np.argmax(np.bincount(lab0.ravel())[1:]) + 1
        static_excl = np.zeros(isw.shape, bool)
        for li in range(1, nl0 + 1):
            if li != big:
                ys_, xs_ = np.where(lab0 == li)
                static_excl[max(0, ys_.min() - 4):ys_.max() + 5, max(0, xs_.min() - 4):xs_.max() + 5] = True
    other |= static_excl
    if n % 2:
        continue
    t = T0 + n / 60.0
    C, loops, f, ib = kv.displayed_curves(t)
    m = raster(C, loops)
    mis = (isw != m) & ~other
    rr, cc = np.where(mis)
    if len(rr):
        pts = np.column_stack([cc + c0 + 0.5, rr + r0_ + 0.5])
        cpx = [np.column_stack([x470 + sx * P[:, 0], row_y0 - sy * P[:, 1]]) for P in [C] + [np.vstack([L["pts"], L["pts"][:1]]) for L in loops]]
        d, _ = SegTree(cpx).dist(pts)
        xpt = xc[cc]
        inz = (xpt >= BOATZ[0]) & (xpt <= BOATZ[1])
        far = d > 1.5
        r = dict(n=n, t=t, frame=f, interp=ib, n_mis=int(len(rr)), n_far_out=int((far & ~inz).sum()), dmax_out=float(d[~inz].max()) if (~inz).any() else 0.0,
                 n_far_boatzone=int((far & inz).sum()),
                 far_out_xy=[(float(xpt[i]), float(yc[rr[i]])) for i in np.where(far & ~inz)[0][:5]])
    else:
        r = dict(n=n, t=t, frame=f, interp=ib, n_mis=0, n_far_out=0, dmax_out=0.0, n_far_boatzone=0, far_out_xy=[])
    cx = rows[f - F0]["crest_x"]
    if cx - 20 >= xc[0] and cx + 20 <= xc[-1] and not ib:
        w = np.where((xc >= cx - 20) & (xc <= cx + 20))[0]
        yv = top_profile(isw & ~other)[w]
        rms = {}
        for dk in (-2, -1, 0, 1, 2):
            if F0 <= f + dk <= F1:
                yr = r3_top(f + dk, xc[w])
                ok = np.isfinite(yv) & np.isfinite(yr)
                rms[dk] = float(np.sqrt(np.mean((yv[ok] - yr[ok]) ** 2)))
        r["rms"] = rms; r["best_dk"] = min(rms, key=rms.get)
        r["crest_img"] = float(np.nanmax(yv)); r["crest_r3"] = float(np.nanmax(r3_top(f, xc[w])))
    out.append(r)
    if n % 120 == 0:
        print(n, round(t, 3), f, ib, r["n_far_out"], round(r["dmax_out"], 2), r["n_far_boatzone"], r.get("best_dk"), r.get("rms"))
tim = [r for r in out if "best_dk" in r]
res = dict(n=len(out), far_out_max=max(r["n_far_out"] for r in out), far_out_frames=sum(1 for r in out if r["n_far_out"] > 0),
           dmax_out_px=max(r["dmax_out"] for r in out), worst=max(out, key=lambda r: r["n_far_out"]),
           far_boatzone_max=max(r["n_far_boatzone"] for r in out),
           timing_n=len(tim), timing_best=dict((str(k), sum(1 for r in tim if r["best_dk"] == k)) for k in (-2, -1, 0, 1, 2)),
           timing_first_t=tim[0]["t"] if tim else None,
           crest_diff=dict(max_abs=max(abs(r["crest_img"] - r["crest_r3"]) for r in tim), median=float(np.median([r["crest_img"] - r["crest_r3"] for r in tim]))),
           rows=out)
print({k: v for k, v in res.items() if k != "rows"})
jsave(OUT + "/k_video_side2.json", res)
