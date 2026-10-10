# -*- coding: utf-8 -*-
"""2. Unity が書き出した点（Editor・プレイヤー、RT48Decode.hlsl を計算シェーダーで走らせた物）を、
(a) 焼いた点から自分で作った表示の点と、(b) 自分で取った R3 の線と、(c) R3 の符号付き距離の場そのものと比べる。
出力：out/k_playback_<editor|player>.json"""
import sys, time
import numpy as np
from k_lib import *

which = sys.argv[1] if len(sys.argv) > 1 else "editor"
t0 = time.time()
D = RT + f"/verify/coarse/unity_{which}"
ix = jload(D + "/index.json")
cur = np.fromfile(D + "/" + ix["curvesFile"], dtype="<f4")
pairs, man = load_pairs()
N = 8192
TAPER = np.array([100.0, 200.0, 825.0, 925.0])
man_taper = man["x_fade"]["ranges_x_rel"]
assert np.allclose([man_taper[0][0], man_taper[0][1], man_taper[1][0], man_taper[1][1]], TAPER)
assert np.allclose(np.array(ix["taperStored"]) + X0B, TAPER)


def ulp32(v):
    return np.spacing(np.abs(v).astype(np.float32)).astype(np.float64)


def expected(p, alpha, seat):
    A = pairs[p, 0].astype(np.float64); B = pairs[p, 1].astype(np.float64)
    P = A + (B - A) * alpha
    X = P[:, 0] + X0B - seat
    Y = P[:, 1] * taper_w(P[:, 0] + X0B)
    D2 = np.column_stack([X, Y])
    i0 = np.r_[0, np.arange(N - 1)]; i1 = np.r_[np.arange(1, N), N - 1]
    t = D2[i1] - D2[i0]
    L = np.hypot(t[:, 0], t[:, 1])
    n = np.column_stack([-t[:, 1], t[:, 0]]) / np.where(L > 0, L, 1)[:, None]
    return D2, n


# ---- (a) Unity の点 と 焼いた点から作った表示の点
grp = {}
for c in ix["curves"]:
    o = c["offsetFloats"]
    U = cur[o:o + 4 * N].reshape(N, 4).astype(np.float64)
    E, nE = expected(c["pair"], c["alpha"], c["seatX"])
    dp = np.abs(U[:, :2] - E)
    tol = np.maximum(1e-4, 4 * np.maximum(ulp32(U[:, 0]), ulp32(U[:, 1])))[:, None]
    cosang = np.clip((U[:, 2] * nE[:, 0] + U[:, 3] * nE[:, 1]) / np.maximum(np.hypot(U[:, 2], U[:, 3]), 1e-30), -1, 1)
    ang = np.degrees(np.arccos(cosang))
    g = grp.setdefault(c["group"], dict(n=0, max_pos=0.0, n_over_tol=0, max_norm_deg=0.0, pairs=set(), alphas=set()))
    g["n"] += 1; g["max_pos"] = max(g["max_pos"], float(dp.max())); g["n_over_tol"] += int((dp > tol).sum())
    g["max_norm_deg"] = max(g["max_norm_deg"], float(np.nanmax(ang))); g["pairs"].add(c["pair"]); g["alphas"].add(round(c["alpha"], 6))
for g in grp.values():
    g["n_pairs"] = len(g["pairs"]); g["n_alphas"] = len(g["alphas"]); del g["pairs"]; g["alphas"] = sorted(g["alphas"])[:5]
print("A", grp, f"{time.time()-t0:.1f}s")

# ---- (b)(c) 再生した形（各コマ：その組の割合 0、最後のコマは最後の組の割合 1）と R3
my = MyFrames()
rec = R3Rec()
src = {(c["pair"], round(c["alpha"], 6)): c for c in ix["curves"] if c["group"] == "src556"}
rows = []
worst = dict(d=0.0)
for f in range(F0, F1 + 1):
    p = f - F0
    c = src[(p, 0.0)] if p < 570 else src[(569, 1.0)]
    o = c["offsetFloats"]
    U = cur[o:o + 4 * N].reshape(N, 4)[:, :2].astype(np.float64)
    U[:, 0] += c["seatX"]                         # Unity の X → 造波板からの距離
    R = my.main_of(f)
    core = (U[:, 0] >= 200.0) & (U[:, 0] <= 825.0)
    tr = SegTree([R])
    d1, uns1 = tr.dist(U[core])
    Rd = densify(R, 0.01); Rd = Rd[(Rd[:, 0] >= 200.0) & (Rd[:, 0] <= 825.0)]
    tu = SegTree([U])
    d2, uns2 = tu.dist(Rd)
    # 場そのもの：断面の範囲の Unity の点の、双一次の符号付き距離の大きさ（線を取らない比べ）
    S, xs, ys = rec.section(f)
    insec = (U[:, 0] >= xs[0]) & (U[:, 0] <= xs[-1]) & core
    sdf = np.abs(bilinear(S, xs, ys, U[insec]))
    # hf の帯（x 200 m〜断面の左の端）：高さの差
    eh, xh = rec.height(f)
    inhf = core & (U[:, 0] < xs[0])
    dyh = np.abs(U[inhf, 1] - np.interp(U[inhf, 0], xh, eh))
    # 両端の下ろしの帯：表示の高さと計算の高さの差（計算にない形の大きさ）
    tz = ~core
    ytrue = np.interp(U[tz, 0], xh, eh)
    dtaper = np.abs(U[tz, 1] - ytrue)
    r = dict(frame=f, d_u2r=float(d1.max()), d_r2u=float(d2.max()), unsure=uns1 + uns2, sdf_max=float(sdf.max()), sdf_p99=float(np.percentile(sdf, 99)),
             hf_dy_max=float(dyh.max()) if len(dyh) else 0.0, taper_dy_max=float(dtaper.max()), taper_true_absmax=float(np.abs(ytrue).max()),
             x_first=float(U[0, 0]), x_last=float(U[-1, 0]))
    r["two_way"] = max(r["d_u2r"], r["d_r2u"])
    if r["two_way"] > worst["d"]:
        worst = dict(d=r["two_way"], frame=f)
    rows.append(r)
tw = np.array([r["two_way"] for r in rows])
summ = dict(n_frames=len(rows), max_two_way=float(tw.max()), worst_frame=worst["frame"], median=float(np.median(tw)), n_over_002=int((tw > 0.02).sum()),
            max_u2r=max(r["d_u2r"] for r in rows), max_r2u=max(r["d_r2u"] for r in rows), unsure_total=sum(r["unsure"] for r in rows),
            max_before_onset=float(tw[: 3714 - F0].max()),
            sdf_max=max(r["sdf_max"] for r in rows), sdf_p99_max=max(r["sdf_p99"] for r in rows), hf_dy_max=max(r["hf_dy_max"] for r in rows),
            taper_dy_max=max(r["taper_dy_max"] for r in rows), taper_true_absmax=max(r["taper_true_absmax"] for r in rows),
            x_first_range=(min(r["x_first"] for r in rows), max(r["x_first"] for r in rows)), x_last_range=(min(r["x_last"] for r in rows), max(r["x_last"] for r in rows)))
print("B", summ, f"{time.time()-t0:.1f}s")

# ---- 目印：各コマの頂（自分のたどり）、巻き始め・唇（自分の読み方を Unity の線に当てる）
kr = jload(OUT + "/k_r3.json")
crest_rows = []
xprev = 261.53670245673754
onsetU = None; lipU = {}
for f in range(F0, F1 + 1):
    p = f - F0
    c = src[(p, 0.0)] if p < 570 else src[(569, 1.0)]
    o = c["offsetFloats"]
    U = cur[o:o + 4 * N].reshape(N, 4)[:, :2].astype(np.float64); U[:, 0] += c["seatX"]
    ic = crest_index(U, xprev); xprev = U[ic, 0]
    rr = kr["rows"][p]
    crest_rows.append((f, U[ic, 0] - rr["crest_x"], U[ic, 1] - rr["crest_y"]))
    ang, xv = front_overturn(U, ic)
    if onsetU is None and ang >= 90.0:
        onsetU = dict(frame=f, x_vertical=xv, crest=(float(U[ic, 0]), float(U[ic, 1])))
    if 3714 <= f <= 3744:
        lu = lip(U, ic)
        lr = rr["lip"]
        if lu is not None and lr is not None:
            lipU[f] = dict(reach_u=lu["reach"], reach_r=lr["reach"], thick_u=lu["thick"], thick_r=lr["thick"],
                           tip_d=float(np.hypot(lu["tip"][0] - lr["tip"][0], lu["tip"][1] - lr["tip"][1])))
cr = np.array(crest_rows)
pre = cr[cr[:, 0] <= 3745]
land = dict(crest_dx_max_all=float(np.abs(cr[:, 1]).max()), crest_dy_max_all=float(np.abs(cr[:, 2]).max()),
            crest_dx_max_to_contact=float(np.abs(pre[:, 1]).max()), crest_dy_max_to_contact=float(np.abs(pre[:, 2]).max()),
            crest_at_3714=crest_rows[3714 - F0][1:], crest_at_3745=crest_rows[3745 - F0][1:],
            onset_unity=onsetU, onset_mine=kr["onset"], lip=lipU,
            lip_3744=lipU.get(3744))
print("C", {k: v for k, v in land.items() if k != "lip"}, f"{time.time()-t0:.1f}s")

# ---- 閉じた線（loops.bin：焼きの水の塊と囲んだ空気）と、自分の R3 の閉じた線
lb = np.fromfile(RT + "/data/coarse/loops.bin", dtype="<f4").reshape(-1, 2).astype(np.float64)
lrows = []
for e in man["loops_index"]:
    f = e["frame"]
    mine = my.loops_of(f)
    # 焼きの loops は x の範囲 100〜925 m の全部か？ 自分の閉じた線は断面の範囲の全部（静かな水面から 25 m 下より上）
    baked = [dict(pts=lb[int(a):int(a) + int(n)] + np.array([X0B, 0.0]), phase=int(ph), area=float(ar)) for a, n, ph, ar in e["loops"]]
    nb = {ph: sum(1 for L in baked if L["phase"] == ph) for ph in (-1, 1, 0)}
    nm = {ph: sum(1 for L in mine if L["phase"] == ph) for ph in (-1, 1)}
    hd = 0.0
    for L in baked:
        if not mine:
            hd = float("inf"); break
        best = min(max(SegTree([np.vstack([M["pts"], M["pts"][:1]])]).dist(L["pts"])[0].max(),
                       SegTree([np.vstack([L["pts"], L["pts"][:1]])]).dist(M["pts"])[0].max()) for M in mine)
        hd = max(hd, best)
    lrows.append(dict(frame=f, baked=nb, mine=nm, hausdorff_max=hd, area_baked=sorted(round(L["area"], 4) for L in baked),
                      area_mine=sorted(round(L["area"], 4) for L in mine)))
diff_count = [r for r in lrows if r["baked"][-1] != r["mine"][-1] or r["baked"][1] != r["mine"][1]]
loops = dict(n_frames=len(lrows), frames_with_loops=sum(1 for r in lrows if sum(r["baked"].values())),
             n_frames_count_differs=len(diff_count), differs=diff_count[:15],
             hausdorff_max=max(r["hausdorff_max"] for r in lrows), baked_unknown_phase=sum(r["baked"][0] for r in lrows))
print("D", {k: v for k, v in loops.items() if k != "differs"}, [ (r["frame"], r["baked"], r["mine"]) for r in diff_count[:10]], f"{time.time()-t0:.1f}s")

jsave(OUT + f"/k_playback_{which}.json", dict(which=which, A_decode=grp, B_shape=summ, C_landmarks=land, D_loops=loops, rows=rows, seconds=time.time() - t0))
print(f"done {time.time()-t0:.1f}s")
