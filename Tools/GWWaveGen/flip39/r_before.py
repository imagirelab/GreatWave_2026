# -*- coding: utf-8 -*-
"""FLIP39 R：図の「前」＝FLIP37 P3（H25_R18_mg、粒子 0.25 m）を、D1 の座席（seat_v1 を P3 の置き方の逆で計算の座標へ写した目）から描く（py -3.10 → Blender）。
- 固定の目：D1 の目 (552.19, 1.666, −9.45)（作品の 1.83 m を置き方の倍率 1.1 で割った高さ）。目が水に入る直前（t 8.08 s）。
- 乗る目：D1 の seat_raw.json の eye_ride_y。乗る目の仰角が最大（68°）の時（t 9.04 s）。
P3 の網目の水面のずれは 0.46 m（FLIP37 P2 の 3D の 0.44〜0.48 m の中ほど。推定）を引く。箱の外は高さ 0 の平らな面（P3 の外の R18 は描かない）。
カメラは R の座席の目と同じ（沖＝−x を向き、縦の画角 90°）。見上げる角は R と同じ決め方（頂の仰角の 0.55 倍、10°〜42°）。
"""
import sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from r_render import run_blender
P3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3/H25_R18_mg/mesh"
D1 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D1/seat_raw.json"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/render/before"
os.makedirs(OUT, exist_ok=True)
S = json.load(open(D1, encoding="utf8"))["seat"]
ex, ey, ez = S["eye_sim"]
fr = {int(q["frame"]): q for q in S["frames"]}
items = []
info = {}
# 乗る目の仰角が初めて 40° を越えたコマ（R の図と同じ決め方）
t40 = min((q["t"] for q in S["frames"] if q.get("view_ride") and q["view_ride"]["alpha_max"] >= 40.0), default=8.5)
# 乗る目の終わり（D1：9.2 s に船が頂の上に出る）の 0.4 秒前（R の止めた画と同じ決め方）
for lab, t, mode in (("fixed", 8.0833, "fixed"), ("ride40", t40, "ride"), ("ride", 9.0417, "ride"), ("ride_m04", 8.80, "ride")):
    f = int(round(t * 24)) + 1
    q = fr.get(f) or fr[min(fr, key=lambda k: abs(k - f))]
    if mode == "fixed":
        eye = ey; al = q["view"]["alpha_max"]
    else:
        eye = q["eye_ride_y"] + 1.83 / 1.1; al = q["view_ride"]["alpha_max"]
    p = np.radians(np.clip(0.55 * al, 10, 42))
    cam = dict(pos=[ex, eye, ez], look=[ex - 100 * np.cos(p), eye + 100 * np.sin(p), ez], vfov=90.0, near=0.2, out=os.path.join(OUT, "p3_%s_f%04d.png" % (lab, f)))
    items.append(dict(frame=f, fine=os.path.join(P3, "mesh_%04d.npz" % f), fine_off=0.46, mirror=False, flip=True, boat=[ex - 1.0, eye - 1.83 / 1.1, ez], cams=[cam]))
    info[lab] = dict(frame=f, t=(f - 1) / 24.0, eye=[ex, eye, ez], alpha=al, pitch_deg=float(np.degrees(p)), out=cam["out"])
job = dict(res=[1280, 720], plane_hole=[304.0, 636.0, -66.0, 66.0], items=items)
run_blender(job, os.path.join(OUT, "job.json"))
json.dump(info, open(os.path.join(OUT, "before_info.json"), "w", encoding="utf8"), indent=1, default=float)
print(json.dumps(info, default=float))
