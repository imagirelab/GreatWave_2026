# -*- coding: utf-8 -*-
"""6b. 横からの動画の 150〜157 s の毎コマで、かぶさり（巻き始め）と囲んだ空気（最初の接触）が絵に初めて出る時刻を、
同じ決め方で自分の R3 の線を塗った絵と比べる（空気の塊は 8 方向につながりを見る：細い口が開いていれば囲まれていない）。
出力：out/k_video_events.json"""
import numpy as np
from scipy import ndimage
from k_lib import *
import k_video as kv

S8 = np.ones((3, 3), int)
box_left, box_top, box_right, box_bottom = 39, 195, 1880, 613
c0, c1, r0_, r1_ = box_left + 1, box_right, box_top + 1, box_bottom - 1
sx = 12.266176470588228; x470 = 40.536764705885616 - 470 * sx   # k_video の目盛りの読み（cal）から
sy = (box_bottom - box_top - 1) / 34.0; row_y0 = 441.5
xc = (np.arange(c0, c1) + 0.5 - x470) / sx
yc = (row_y0 - (np.arange(r0_, r1_) + 0.5)) / sy


def raster(C, loops):
    polys = [np.vstack([C, [C[-1, 0], -60.0], [C[0, 0], -60.0], C[:1]])] + [np.vstack([L["pts"], L["pts"][:1]]) for L in loops]
    m = np.zeros((len(yc), len(xc)), bool)
    for Pp in polys:
        x0, x1 = Pp[:-1, 0], Pp[1:, 0]; y0, y1 = Pp[:-1, 1], Pp[1:, 1]
        for j, xq in enumerate(xc):
            kk = np.where(((x0 <= xq) & (x1 > xq)) | ((x1 <= xq) & (x0 > xq)))[0]
            if len(kk):
                yy = y0[kk] + (xq - x0[kk]) * (y1[kk] - y0[kk]) / (x1[kk] - x0[kk])
                m[:, j] ^= ((yy[None, :] > yc[:, None]).sum(1) % 2 == 1)
    return m


def events(water, crest_x):
    water = water[yc > 1.0]          # 静かな水面から 1 m より上だけ（物差し・字・破線は下にある）
    win = np.where((xc >= crest_x - 30) & (xc <= crest_x + 30))[0]
    over = 0
    for j in win:
        col = water[:, j]
        if col.any():
            i0 = col.argmax(); i1 = len(col) - 1 - col[::-1].argmax()
            if (~col[i0:i1 + 1]).any():
                over += 1
    lab, nl = ndimage.label(~water, structure=S8)
    hole = 0.0
    for li, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys_, xs_ = sl
        if ys_.start == 0 or ys_.stop == water.shape[0] or xs_.start == 0 or xs_.stop == water.shape[1]:
            continue
        area = (lab[sl] == li).sum() / (sx * sy)
        xm = xc[(xs_.start + xs_.stop) // 2]
        if abs(xm - crest_x) <= 30:
            hole = max(hole, area)
    return over, hole


rows = jload(OUT + "/k_r3.json")["rows"]
out = []
for n, a in kv.read_frames(RT + "/video/rt48_side_coarse.mp4"):
    if n < 960:
        continue
    if n > 1080:
        break
    t = T0 + n / 60.0
    sub = a[r0_:r1_, c0:c1].astype(float)
    sky = np.array([212.0, 224.0, 230.0]); wat = np.array([28.0, 77.0, 95.0]); dv = wat - sky
    tt = ((sub - sky) @ dv) / (dv @ dv)
    resid = np.linalg.norm(sub - sky - tt[..., None] * dv, axis=2)
    isw = (tt > 0.5) & (resid < 45)
    rd = int(np.floor(row_y0)) - r0_
    isw[rd - 2:rd + 2, :] |= isw[rd - 3:rd - 2, :].repeat(4, 0)   # 破線の行は上の行で埋める（水の中の白い点線を水とみなす）
    C, loops, f, ib = kv.displayed_curves(t)
    cx = rows[f - F0]["crest_x"]
    ov, ho = events(isw, cx)
    m = raster(C, loops)
    ovr, hor = events(m, cx)
    out.append(dict(n=n, t=t, frame=f, interp=ib, over_video=ov, hole_video=ho, over_r3=ovr, hole_r3=hor))
fo = lambda key: next((dict(n=r["n"], t=r["t"], frame=r["frame"]) for r in out if r[key] >= (1 if key.startswith("over") else 0.25)), None)
res = dict(first_overhang_video=fo("over_video"), first_overhang_r3=fo("over_r3"), first_hole_video=fo("hole_video"), first_hole_r3=fo("hole_r3"),
           rows=out)
print({k: v for k, v in res.items() if k != "rows"})
jsave(OUT + "/k_video_events.json", res)
