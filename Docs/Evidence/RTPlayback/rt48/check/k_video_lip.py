# -*- coding: utf-8 -*-
"""6e. 横からの動画の 155.0〜155.983 s（巻き始めの後、最初の接触の前）で、絵の水の塗りの境の線を取り、自分の唇の読み方
（届く距離・厚み）を当てて、同じコマの自分の R3 の線の値と比べる。出力：out/k_video_lip.json"""
import numpy as np
from skimage import measure
from k_lib import *
import k_video as kv
from k_video_events import xc, yc, c0, c1, r0_, r1_, sx, sy, x470, row_y0

rows = jload(OUT + "/k_r3.json")["rows"]; my = MyFrames()
out = []
for n, a in kv.read_frames(RT + "/video/rt48_side_coarse.mp4"):
    t = T0 + n / 60.0
    if t < 155.0:
        continue
    if t >= 156.0 - 1e-9:
        break
    sub = a[r0_:r1_, c0:c1].astype(float)
    sky = np.array([212.0, 224.0, 230.0]); wat = np.array([28.0, 77.0, 95.0]); dv = wat - sky
    tt = np.clip(((sub - sky) @ dv) / (dv @ dv), 0, 1)
    cs = measure.find_contours(tt, 0.5)
    k, w, ip = kv.state(t); f = F0 + k
    cx = rows[f - F0]["crest_x"]
    best = None
    for c in cs:
        P = np.column_stack([x470 / -sx * -1 * 0 + (c0 + c[:, 1] + 0.5 - x470) / sx, (row_y0 - (r0_ + c[:, 0] + 0.5)) / sy])
        if P[:, 0].min() < cx - 25 and P[:, 0].max() > cx + 10 and P[:, 1].max() > 5:
            best = P; break
    if best is None:
        continue
    if best[0, 0] > best[-1, 0]:
        best = best[::-1]
    ic = crest_index(best, cx, half=10.0)
    lv = lip(best, ic)
    lr = rows[f - F0]["lip"]
    out.append(dict(n=n, t=t, frame=f, interp=ip, img=None if lv is None else dict(reach=lv["reach"], thick=lv["thick"], tip=lv["tip"]),
                    r3=None if lr is None else dict(reach=lr["reach"], thick=lr["thick"], tip=lr["tip"])))
for r in out[::3] + out[-2:]:
    print(r["n"], round(r["t"], 3), r["frame"], r["interp"], r["img"] and {k: (np.round(v, 3).tolist() if not isinstance(v, float) else round(v, 3)) for k, v in r["img"].items()},
          r["r3"] and {k: (np.round(v, 3).tolist() if not isinstance(v, float) else round(v, 3)) for k, v in r["r3"].items()})
ok = [r for r in out if r["img"] and r["r3"] and not r["interp"]]
res = dict(n=len(out), n_both=len(ok), max_d_reach=max(abs(r["img"]["reach"] - r["r3"]["reach"]) for r in ok) if ok else None,
           max_d_thick=max(abs(r["img"]["thick"] - r["r3"]["thick"]) for r in ok) if ok else None,
           max_d_tip=max(float(np.hypot(r["img"]["tip"][0] - r["r3"]["tip"][0], r["img"]["tip"][1] - r["r3"]["tip"][1])) for r in ok) if ok else None,
           at_3744=[r for r in out if r["frame"] == 3744], rows=out)
print({k: v for k, v in res.items() if k not in ("rows",)})
jsave(OUT + "/k_video_lip.json", res)
