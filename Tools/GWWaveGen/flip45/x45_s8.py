# -*- coding: utf-8 -*-
"""FLIP45 煙の試し S8：3D の量の道具（g45_crest3d.py・g45_analyze.py の読み）の確かめ（py -3.10。Houdini は使わない。計画 §10.2）。
判定（走らせる前に決めた。計画 §10.2 の S8）：
  (1) 壁ありの線形の場（巻かない。F45 の y = 0 の頂が最も高い時刻）を R1 の形（格子 0.5 m の中心）にした合成の記録で、ℓ（z = Ac/2 の
      等高線の幅）が numpy の直接の値（0.05 m の細かい格子で、同じ決まり）と格子 1 個（0.5 m）以内。
  (2) 巻き始めと着水のコマが FLIP42 の読みと同じ：FLIP42 の R3 の本物の断面の記録（3690〜3760 コマ）を g45_crest3d で読み、巻き始め 3714・
      着水 3745（STUDY52 の shape_measures.json と FLIP42 の ana.json）と同じコマ。
  (3) 崩れ落ちる前の面（唇の先は静かな水面より下へ下がるが、覆いかぶさりがない）の合成の断面を「前へ巻く」と読まない（見直し M10）。
      くらべに、唇が覆いかぶさる合成の断面は「前へ巻く」と読む。
  (4) 軸の外で巻く合成の場（y = 20 m の所だけ前の面が 90° を越える 3D の SDF）で、軸の外の巻き始めの y・x・コマが合成の値と同じ（見直し M7）。
  ほかに、(5) GCI の手順（g45_resolution.gci3）が f = 1 + h² で次数 2・外挿 1 を返すか、(6) 繰り返しの判定（g45_repeat.judge）が
  合成の出来事で場合 1・2・3 を返すかも見る（記録だけ）。
出力：Unity/Build/FLIP45/smoke/S8/s8.json
"""
import sys, os, json, math, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_crest3d as C3
import g45_inlet_table as IT

OUT = GC.B45 + "/smoke/S8"
os.makedirs(OUT, exist_ok=True)
res = {}

# ---------------------------------------------------------------- (1) ℓ
c = IT.CASES["F45"]
P, Q = IT.modes(c)
ts = np.round(np.arange(44.0, 60.0, 0.1) / 0.1) * 0.1
x_line = np.arange(190.0, 240.0, 0.5)
ms = IT.mode_series(P, Q, x_line, ts)
eta0 = IT.combine_y(ms, [0.0])["eta"][0]                  # (t, x)
it, ix = np.unravel_index(np.argmax(eta0), eta0.shape)
t_pk = float(ts[it]); x_pk = float(x_line[ix]); A_pk = float(eta0[it, ix])
# 記録の形：x の格子の中心 0.25 + 0.5 i、横の中心 0.25 + 0.5 j（粒子 0.25 m の L1 と同じ）
xs_r = np.arange(150.25, 300.0, 0.5); ys_r = np.arange(0.25, 108.0, 0.5)
msr = IT.mode_series(P, Q, xs_r, [t_pk])
Er = IT.combine_y(msr, ys_r)["eta"][:, 0, :]               # (y, x)
cw = C3.crest_width(Er, xs_r, ys_r, x_pk, 0.5 * A_pk)
# 細かい直接の値：x 0.05 m ごと、各 x で y を 0.05 m ごとにたどり、η > Ac/2 が y = 0 から続く最大の y（線形の補間）
xs_f = np.arange(x_pk - 30.0, x_pk + 30.0, 0.05); ys_f = np.arange(0.0, 108.0, 0.05)
msf = IT.mode_series(P, Q, xs_f, [t_pk])
Ef = IT.combine_y(msf, ys_f)["eta"][:, 0, :]
best = 0.0
lev = 0.5 * A_pk
for i in range(len(xs_f)):
    col = Ef[:, i]
    if col[0] <= lev:
        continue
    j = int(np.argmax(col <= lev)) if (col <= lev).any() else len(col) - 1
    yh = ys_f[j - 1] + (col[j - 1] - lev) / (col[j - 1] - col[j]) * (ys_f[j] - ys_f[j - 1]) if j > 0 else 0.0
    best = max(best, yh)
direct = 2 * best
res["1_ell"] = dict(t=t_pk, x_crest=x_pk, Ac=A_pk, level=lev, ell_tool=cw["width"], ell_direct=direct, diff=cw["width"] - direct,
                    tol=0.5, passed=bool(abs(cw["width"] - direct) <= 0.5))

# ---------------------------------------------------------------- (2) FLIP42 R3 の断面
rd42 = GC.REPO + "/Unity/Build/FLIP42/runs/R3"
off42 = json.load(open(rd42 + "/ana.json", encoding="utf8"))["still_level_offset_m"]
best_f = {}
for p in glob.glob(rd42 + "/sec_c*_b*.npz"):
    c0 = int(os.path.basename(p)[5:9]); d = np.load(p)
    for i, f in enumerate(d["frames"]):
        f = int(f)
        if 3690 <= f <= 3760 and (f not in best_f or best_f[f][0] < c0):
            best_f[f] = (c0, p, i)
rows = {}
meta42 = None
cache = {}
for f in sorted(best_f):
    c0, p, i = best_f[f]
    if p not in cache:
        d = np.load(p); cache = {p: (d["sdf"], json.loads(str(d["meta"])))}
    S, meta42 = cache[p]
    cr, _ = C3.frame_crests(S[i], meta42, off42, 0.5, 135.46329754326246, z_bed=-42.0)
    rows[f] = cr
tracks = C3.track_crests(rows, meta42["dx"])
main = max((tr for tr in tracks if len(tr) >= 3), key=lambda tr: max(r["eta"] for _, r in tr))
f_on = next((f for f, r in main if np.isfinite(r["thmax"]) and r["thmax"] >= 90.0), None)
f_td = None
for f, r in main:
    if f_on is not None and f >= f_on:
        c0, p, i = best_f[f]
        S = np.load(p)["sdf"][i].astype(np.float32)
        xs = meta42["x0"] + meta42["dx"] * np.arange(S.shape[1]); ys = meta42["y0"] + meta42["dy"] * np.arange(S.shape[0]) - off42
        pr = C3.plunge_rule(r, S, xs, ys, off42, 0.5, 135.46329754326246)
        if pr["plunge"]:
            f_td = f; td_by = "cavity" if pr["a_cavity"] else "tip+overhang"
            break
res["2_R3"] = dict(onset=f_on, touchdown=f_td, ref_onset=3714, ref_touchdown=3745, passed=bool(f_on == 3714 and f_td == 3745))


# ---------------------------------------------------------------- (3) 崩れ落ちる前の面と、覆いかぶさる唇（合成の断面）
def section_from_mask(M, dx=0.5):
    """水の格子 M[縦, x] → 符号つきの距離のおおよそ（格子の中心の値。水の中で負）。"""
    from scipy import ndimage
    din = ndimage.distance_transform_edt(M) * dx
    dout = ndimage.distance_transform_edt(~M) * dx
    return (dout - din + np.where(M, 0.5 * dx, -0.5 * dx)).astype(np.float32)


dx = 0.5
xs = np.arange(100.0, 260.0, dx) + 0.25; ys = np.arange(-20.0, 16.0, dx) + 0.25
X, Y = np.meshgrid(xs, ys)
meta = dict(x0=float(xs[0]), dx=dx, y0=float(ys[0]), dy=dx)
# 崩れ落ちる面：頂 x 180、高さ 6 m、前の面は 2 m の幅で鉛直より少し寝た壁が静かな水面の 1 m 下まで、その前は水面 −1 m（覆いかぶさりなし）
surf = np.where(X < 180.0, 6.0 * np.exp(-((X - 180.0) / 25.0) ** 2), np.where(X < 182.0, 6.0 - 7.0 * (X - 180.0) / 2.0, -1.0))
M1 = Y < surf
cr1, _ = C3.frame_crests(section_from_mask(M1), meta, 0.0, 1.0, GC.L0)
c1 = max(cr1, key=lambda r: r["eta"])
pr1 = C3.plunge_rule(c1, section_from_mask(M1), xs, ys, 0.0, 1.0, GC.L0)
# 覆いかぶさる唇：同じ頂から前へ厚さ 1.5 m の唇が x 182〜192 に張り出し、先が静かな水面の 0.5 m 下まで垂れる。下の前の面は x 182 で −1 m へ
M2 = (Y < np.where(X < 180.0, 6.0 * np.exp(-((X - 180.0) / 25.0) ** 2), np.where(X < 182.0, 6.0, -1.0)))
lip_top = 6.0 - 0.65 * (X - 182.0)
lip = (X >= 182.0) & (X <= 192.0) & (Y <= lip_top) & (Y >= lip_top - 1.5)
M2 = M2 | lip
cr2, _ = C3.frame_crests(section_from_mask(M2), meta, 0.0, 1.0, GC.L0)
c2 = max(cr2, key=lambda r: r["eta"])
pr2 = C3.plunge_rule(c2, section_from_mask(M2), xs, ys, 0.0, 1.0, GC.L0)
res["3_collapse_vs_plunge"] = dict(collapse=pr1, plunge=pr2, passed=bool((not pr1["plunge"]) and pr2["plunge"]))

# ---------------------------------------------------------------- (4) 軸の外で巻く合成の場（3D の SDF、コマ 3 つ）
zs4 = np.arange(0.25, 72.0, 0.5)
# 静かな水面より上で前へ張り出す唇（先の縦の面が鉛直、その下は後ろへ戻る下の面）：前の面の弦が 90° を越える
M3 = (Y < np.where(X < 180.0, 6.0 * np.exp(-((X - 180.0) / 25.0) ** 2), np.where(X < 182.0, 6.0, -1.0)))
lip_top3 = 6.0 - 0.25 * (X - 182.0)
M3 = M3 | ((X >= 182.0) & (X <= 190.0) & (Y <= lip_top3) & (Y >= lip_top3 - 1.5))
frames = []
for k, tilt in enumerate((0.0, 0.5, 1.0)):          # コマ 0：どこも巻かない、コマ 1：y 18〜22 m だけ唇、コマ 2：同じ
    vol = []
    for z in zs4:
        if tilt > 0 and 18.0 <= z <= 22.0:
            vol.append(section_from_mask(M3))
        else:
            vol.append(section_from_mask(Y < np.where(X < 180.0, 6.0 * np.exp(-((X - 180.0) / 25.0) ** 2), np.where(X < 186.0, 6.0 - (X - 180.0), 0.0))))
    frames.append(np.array(vol))
meta4 = dict(x0=float(xs[0]), dx=dx, z0=0.25, dz=0.5, y0=float(ys[0]), dy=dx)
first = None
for k, V in enumerate(frames):
    rows4 = C3.overturn_span(V, meta4, 0.0, 1.0, GC.L0)
    over = [r for r in rows4 if np.isfinite(r[1]) and r[1] >= 90.0]
    if over and first is None:
        y, th, x, e = min(over, key=lambda r: r[0])
        first = dict(frame=k, y=y, x=x, n=len(over), ys=[r[0] for r in over])
res["4_offaxis"] = dict(first=first, expect=dict(frame=1, y_min=18.0, y_max=22.0),
                        passed=bool(first is not None and first["frame"] == 1 and 17.9 <= first["y"] <= 22.1 and all(17.9 <= v <= 22.1 for v in first["ys"])))

# ---------------------------------------------------------------- (5) GCI・(6) 繰り返し（記録だけ）
import g45_resolution as GR
g = GR.gci3(1 + 0.25 ** 2, 1 + 0.34375 ** 2, 1 + 0.5 ** 2, 0.25, 0.34375, 0.5)
res["5_gci"] = dict(g, expect=dict(p=2.0, f_ext=1.0), passed=bool(abs(g.get("p", 0) - 2.0) < 1e-6 and abs(g.get("f_ext", 0) - 1.0) < 1e-9))
import g45_repeat as RP
T = GC.T
ev1 = [dict(t=48.0, xc=211.0, eta_c=7.0, H=10.0)] + [dict(t=58.0 + 0.1 + n * T, xc=212.0, eta_c=7.1, H=10.1) for n in range(9)]
ev2 = [dict(t=48.0, xc=211.0, eta_c=7.0, H=10.0)] + [dict(t=58.0 + n * T, xc=212.0 + 5.0 * (n % 2), eta_c=7.1, H=10.1) for n in range(9)]
ev3 = [dict(t=48.0, xc=211.0, eta_c=7.0, H=10.0)] + [dict(t=58.0 + n * T, xc=212.0, eta_c=7.1, H=10.1) for n in range(0, 9, 2)]
res["6_repeat"] = dict(case1=RP.judge(ev1)["case"], case2=RP.judge(ev2)["case"], case3=RP.judge(ev3)["case"])
res["6_repeat"]["passed"] = res["6_repeat"] == dict(case1=1, case2=2, case3=3, passed=None) or (res["6_repeat"]["case1"], res["6_repeat"]["case2"], res["6_repeat"]["case3"]) == (1, 2, 3)
res["pass_S8"] = bool(res["1_ell"]["passed"] and res["2_R3"]["passed"] and res["3_collapse_vs_plunge"]["passed"] and res["4_offaxis"]["passed"])
json.dump(res, open(OUT + "/s8.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
print(json.dumps(res, ensure_ascii=False, indent=1, default=float)[:4000])
