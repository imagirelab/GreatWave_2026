# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：rows_build.py（変えない）の写し。足したこと（どれも design に書いた時だけ働き、無ければ R8 と同じ）：
  A. 段の体の下の面を前へ傾ける（塊 LB2 の r2.profile の脛・足の考えを移した）：profile または prof_knots の lean_on > 0 の行で、
     足 Fo = (a_foot + shin_fwd_m, shin_y_m)、前の谷 Tr = (a_foot + foot_fwd_m, foot_y_m)（a は c の向きにならした段の体の面の線から、y は絶対の高さ）。
     引っ込みの底 R3 より 1 m 以上低くする。元の海へつなぐ所 a_join もこの足から決める。
  B. 唇の頭の太さ・唇の出・引っ込みは design の prof_knots（tip_thick_m・lip_m・ucut_m・r1_drop_m など）でそのまま変えられる（コードは元のまま）。
以下は元の説明。
美術の見本06 の段の行（B-ROWS、Q34）：主役波 K*′ AS04F の左の部分（行 c −24〜−8.2 m）を、① から左下へ下りる二つの段
（② b区域・③ 最左側の小区域）にし、それぞれの段に「体」を持たせる。
py -3.10 -B Tools/GWWaveGen/as06/rows_build.py <out_prefix> <design.json>

見本05 の形 B（Tools/GWWaveGen/as05/fx5_B_build.py。変えない）の写しから作った。変えた所：
  1. 段の窓を見本04 の地図の計画の幅へ広げた（② c −15〜−8、③ c −21〜−14、それぞれ約 6〜7 m）。窓の重みで縁の頂を二つの曲線の間で
     切り替える代わりに、縁の頂 E(c)（a・y）と断面の値（溝の深さ・唇・引っ込み・足）を、c の節点の表（design の E_knots・prof_knots）から
     PCHIP でなめらかに決める。行の間で断面の値が跳ばないので、段の脇が切り口・板・角にならない。
  2. 船・手前の海の射線の禁止域（仕上げ28 の protect_grids）による制約を外した（Q34「船可以挪」：造型の間は船を避けない）。
     段の唇の下の面は、見本05 では元の巻きの内の面へ戻していた（禁止域のため）。ここでは、唇の先の下から後ろへ引っ込み（前の縁の下の凹み）、
     そこから段の体の面（藍）が下へ降りて前の谷へ着き、海へつながる。① の巻きの筒は、② の段の右の端（c −10.4〜−8.2 m）で閉じる。
  3. 段の縁の頂 E は、原画の層の頂の線（shapeB_common.READ_CREST）の射線の上の点から節点を取った（rows_knots.py が射線の上の点を出す）。
     窓の端では E を下げ（段どうし・段と ① の間の切れ目）、左の端では前への出を戻して ③ の体を丸く終える。
行 c ≥ −8.2 m（K-top を含む）と背の頂の列（< jA）は見本04 の行のまま。行の c・格子 240 × 400・唇の先の列 200 は変えない。
参照モデル・写真は読まない。原画のカメラは縁の置き場の節点を作る時（rows_knots.py）と測りにだけ使う（色は写さない）。
"""
import json
import os
import sys
import time

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import shapeB_common as B  # noqa: E402


def knot_fn(kn, c):
    k = np.asarray(kn, float)
    if len(k) == 1:
        return np.full(len(c), k[0, 1])
    return PchipInterpolator(k[:, 0], k[:, 1], extrapolate=False)(np.clip(c, k[0, 0], k[-1, 0]))


def pchip_curve(P, n=6000):
    P = np.asarray(P, float)
    d = np.r_[0, np.cumsum(np.sqrt(np.hypot(*np.diff(P, axis=0).T)))]    # 求心（弦長の平方根）
    t = np.linspace(0, d[-1], n)
    return np.c_[PchipInterpolator(d, P[:, 0])(t), PchipInterpolator(d, P[:, 1])(t)]


def arclen(P):
    return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]


def tier_row(a, y, E, p):
    """1 行の列 jA..399 を作り直す。E = 段の縁の頂 (a, y)。p = この行の断面の値（節点の表から。_a_face・_a_join は c の向きにならした値）。
    外の面：P_A（列 jA、元のまま）→ 踏み面 → 溝 G2・G1 → 縁の頂 E → 唇の先 T（列 200）。
    内の面：T → 唇の下 Bt → 引っ込み R1（前の縁の下）→ 段の体の面 R2・R3（c の向きにならした面の線 a_face）→ 足 Fo → 前の谷 Tr
    → 元の海（列 jS 以後は元の点のまま。手前の海のメッシュとの重なりを変えない）。"""
    jA = p["jA"]
    PA = np.array([a[jA], y[jA]])
    Ee = np.array(E, float)
    g = p["groove_m"]
    w1, w2 = p["groove_w1_m"], p["groove_w2_m"]
    room = max(Ee[0] - PA[0] - 0.8, 0.4)
    k = min(1.0, room / w2)
    G1 = Ee + np.array([-w1 * k, -g]); G2 = Ee + np.array([-w2 * k, -g * p["groove_back_frac"]])
    T = Ee + np.array([p["lip_m"], -p["tip_drop_m"]])
    Bt = T + np.array([-0.45, -p["tip_thick_m"]])
    af = min(p["_a_face"], T[0] - p["face_min_back_m"])        # 段の体の面の a（唇の先より face_min_back m 以上後ろ）
    ue = T[0] - af                                            # この行の引っ込みの深さ
    hb = p["recess_h_m"]
    yR3 = max(T[1] - hb, p["recess_min_y_m"])
    R1 = np.array([T[0] - min(ue, p["ucut_m"]) - p["r1_back_m"], T[1] - p["r1_drop_m"]])
    R2 = np.array([af - p["r2_back_m"], 0.5 * (R1[1] + yR3)])
    R3 = np.array([af - p["r3_back_m"], yR3])
    # 足の a は、面の線よりさらに c の向きにならした線（foot_sigma_m）から。段と段の間の谷で足が行ごとに大きく動き、帯の座標 w が伸びるのを防ぐ
    Fo = np.array([max(p.get("_a_foot", af) + p["toe_fwd_m"], R3[0] + 0.3), max(yR3 - p["toe_drop_m"], p["toe_min_y_m"])])
    Tr = np.array([Fo[0] + p["trough_fwd_m"], p["trough_y_m"]])
    lw = float(p.get("lean_on", 0.0))
    if lw > 0:                                   # 直しの回 A：下の面を前へ傾ける（lean_on は 0〜1 の重みで、元の足と混ぜる）
        af_ = p.get("_a_foot", af)
        Fo_l = np.array([max(af_ + p["shin_fwd_m"], R3[0] + 0.5), min(p["shin_y_m"], yR3 - 1.0)])
        Tr_l = np.array([max(af_ + p["foot_fwd_m"], Fo_l[0] + 1.0), p["foot_y_m"]])
        Fo = (1 - lw) * Fo + lw * Fo_l
        Tr = (1 - lw) * Tr + lw * Tr_l
    # 元の海へのつなぎ：列 300 以後で、a ≥ _a_join、かつ y > −0.9、かつそこから先の a が増える最初の列
    # （元の行の海は列 390 ごろから先の数列が長い区間：列 396 で a ≈ 22 m。足が前へ出た行はそこへつなぐ）
    jj = np.arange(300, 398)
    inc = np.r_[np.diff(a[300:399]) > 0]
    ok = (a[jj] >= max(p["_a_join"], Tr[0] + 1.0)) & (y[jj] > -0.9) & inc[:len(jj)]
    jS = int(jj[np.argmax(ok)]) if ok.any() else 397
    if p.get("join_col", 0) >= 300:               # 決めた行で同じ列へつなぐ（300 より小さい値は自動）（列の対応が行ごとに跳ばないよう。帯の座標 w の伸び）
        jS = int(p["join_col"])
    PS = np.array([a[jS], y[jS]])
    pre = [np.array([a[jA - 6], y[jA - 6]]), np.array([a[jA - 3], y[jA - 3]]), PA]
    Rr = PA + np.array([p["riser_frac"] * (G2[0] - PA[0]), p["riser_yfrac"] * (G2[1] - PA[1])])
    mid = [Rr, G2, G1, Ee, T, Bt, R1, R2, R3, Fo, Tr]
    post = [PS] + [np.array([a[j_], y[j_]]) for j_ in sorted(set([min(jS + 1, 399), min(jS + 2, 399)])) if j_ > jS]
    C = pchip_curve(pre + mid + post, 8000)
    sC = arclen(C)
    near = lambda Q: int(np.argmin(np.hypot(C[:, 0] - Q[0], C[:, 1] - Q[1])))
    iA, iT, iS = near(PA), near(T), near(PS)
    na = a.copy(); ny = y.copy()
    jt = 200
    sold = arclen(np.c_[a[jA:jt + 1], y[jA:jt + 1]]); fo = sold / sold[-1]
    fr = p["col_mix_old"] * fo + (1 - p["col_mix_old"]) * np.linspace(0, 1, jt - jA + 1)
    t = sC[iA] + fr * (sC[iT] - sC[iA])
    na[jA:jt + 1] = np.interp(t, sC, C[:, 0]); ny[jA:jt + 1] = np.interp(t, sC, C[:, 1])
    # 唇の先 → 列 jS（元の海の点）を列 200..jS へ。列 jS より先は元のまま
    Q = C[iT:iS + 1]
    sQ = arclen(Q)
    n2 = jS - jt + 1
    t2 = np.linspace(0, 1, n2) ** p["col_pow_in"] * sQ[-1]
    na[jt:jS + 1] = np.interp(t2, sQ, Q[:, 0]); ny[jt:jS + 1] = np.interp(t2, sQ, Q[:, 1])
    na[jS] = a[jS]; ny[jS] = y[jS]
    pts = {"E": Ee, "G1": G1, "T": T, "R1": R1, "R2": R2, "R3": R3, "Fo": Fo, "Tr": Tr, "jS": np.array([jS, 0.0])}
    return na, ny, {k_: [round(float(v[0]), 2), round(float(v[1]), 2)] for k_, v in pts.items()}


DEFAULT_PROFILE = {"lean_on": 0.0, "shin_fwd_m": 2.6, "shin_y_m": 2.0, "foot_fwd_m": 6.0, "foot_y_m": -0.8, "jA": 106, "groove_m": 1.1, "groove_w1_m": 2.6, "groove_w2_m": 3.6, "groove_back_frac": 0.8,
                   "riser_frac": 0.45, "riser_yfrac": 0.62, "lip_m": 0.9, "tip_drop_m": 0.3, "tip_thick_m": 0.9,
                   "ucut_m": 2.3, "recess_h_m": 5.5, "recess_min_y_m": 1.6, "r1_back_m": 0.15, "r1_drop_m": 1.75, "r2_back_m": 0.5,
                   "r3_back_m": 0.25, "toe_fwd_m": 1.2, "toe_drop_m": 1.6, "toe_min_y_m": 0.4, "trough_fwd_m": 1.6, "trough_y_m": -1.7,
                   "join_fwd_m": 3.5, "col_mix_old": 0.3, "col_pow_in": 1.0, "face_min_back_m": 0.6, "face_sigma_m": 1.2}


def build(design):
    c, A, Y = B.load_rows(B.ROWS04F if not design.get("base_rows") else design["base_rows"])
    A0, Y0 = A.copy(), Y.copy()
    lo, hi = design["c_range"]
    kb0, kb1 = design["c_keep_blend"]        # 右の端：kb0 まで作り直し全部、kb1 で見本04 のまま
    wl = design["c_left_blend"]
    wkeep = B.ss((kb1 - c) / max(kb1 - kb0, 1e-6)) * B.ss((c - wl[0]) / max(wl[1] - wl[0], 1e-6))
    wkeep[(c < wl[0]) | (c > kb1)] = 0.0
    EK = np.array(design["E_knots"], float)
    Ea = knot_fn(EK[:, [0, 1]], c); Ey = knot_fn(EK[:, [0, 2]], c) * B.H0
    prof = dict(DEFAULT_PROFILE); prof.update(design.get("profile", {}))
    PK = {k_: knot_fn(v, c) for k_, v in design.get("prof_knots", {}).items()}
    lay = np.zeros(len(c), int)
    for L_, (c0, c1) in ((2, design["layer_c"]["2"]), (3, design["layer_c"]["3"])):
        lay[(c >= c0) & (c <= c1)] = L_
    # 段の体の面の線 a_face(c)：唇の先 − 引っ込みの深さを、c の向きに face_sigma_m でならす（段と段の間の切れ目で面が縦の溝にならないよう）
    def pk(name):
        return PK[name] if name in PK else np.full(len(c), float(prof[name]))
    Ta = Ea + pk("lip_m")
    raw = Ta - pk("ucut_m")
    cg = np.arange(lo - 3.0, kb1 + 3.0001, 0.1)
    rg = np.interp(cg, c, raw)
    a_face = np.interp(c, cg, gaussian_filter1d(rg, prof["face_sigma_m"] / 0.1, mode="nearest"))
    a_foot = np.interp(c, cg, gaussian_filter1d(rg, prof.get("foot_sigma_m", prof["face_sigma_m"]) / 0.1, mode="nearest"))
    tr_a = np.maximum(a_foot, a_face) + pk("toe_fwd_m") + pk("trough_fwd_m")
    if "lean_on" in PK or prof.get("lean_on", 0) > 0:      # 直しの回 A：前へ出した足の前の谷から海へつなぐ
        lw_ = pk("lean_on")
        tr_a = (1 - lw_) * tr_a + lw_ * np.maximum(tr_a, a_foot + pk("foot_fwd_m"))
    a_join = np.interp(c, cg, gaussian_filter1d(np.interp(cg, c, tr_a), 1.0 / 0.1, mode="nearest")) + pk("join_fwd_m")
    info = []
    dA = np.zeros_like(A); dY = np.zeros_like(Y)
    for i in np.nonzero(wkeep > 1e-3)[0]:
        pr = dict(prof)
        for k_, v in PK.items():
            pr[k_] = float(v[i])
        pr["_a_face"] = float(a_face[i]); pr["_a_join"] = float(a_join[i]); pr["_a_foot"] = float(a_foot[i])
        na, ny, inf = tier_row(A[i], Y[i], (Ea[i], Ey[i]), pr)
        dA[i] = (na - A[i]) * wkeep[i]; dY[i] = (ny - Y[i]) * wkeep[i]
        info.append({"row": int(i), "c": round(float(c[i]), 2), "w": round(float(wkeep[i]), 3), "layer": int(lay[i]), **inf})
    sig = design.get("sigma_rows", 0.0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    # 場所を限ったならし（design の local_smooth：c の窓・列の窓の中だけ、行の向きに σ 行でならす。fx5_B_build.py と同じ。
    # ③ の左の端と ② ③ の間の谷で、行の間の断面の変わり方を緩め、帯の座標 w の伸び（G1）を消す）
    for ls in design.get("local_smooth", []):
        dAs = gaussian_filter1d(dA, ls["sigma"], axis=0, mode="nearest"); dYs = gaussian_filter1d(dY, ls["sigma"], axis=0, mode="nearest")
        c0_, c1_, bl_ = ls["c"][0], ls["c"][1], ls["blend"]
        wc = (B.ss((c - (c0_ - bl_)) / bl_) * B.ss(((c1_ + bl_) - c) / bl_))[:, None]
        J_ = np.arange(A.shape[1])[None, :]
        wj = B.ss((J_ - (ls["cols"][0] - 8)) / 8.0) * B.ss(((ls["cols"][1] + 8) - J_) / 8.0)
        W_ = wc * wj
        dA = dA + W_ * (dAs - dA); dY = dY + W_ * (dYs - dY)
    # K-top：c ≥ kb1 の行と、背の頂の列（< jA）は動かさない
    dA[c >= kb1] = 0; dY[c >= kb1] = 0
    dA[:, :prof["jA"]] = 0; dY[:, :prof["jA"]] = 0
    A = A + dA; Y = Y + dY
    for AA, Ax in ((A, A0), (Y, Y0)):
        AA[0] = Ax[0]; AA[-1] = Ax[-1]; AA[:, 0] = Ax[:, 0]; AA[:, -1] = Ax[:, -1]
    # 段の縁の白を付ける行（rows_mesh.py が s ≥ 0.75 の行に付ける）：design の white_c（無ければ層の行）。左の端の丸い終わりには白を付けない（S9）
    s = np.where(lay > 0, 1.0, 0.0) * (wkeep > 0.5)
    if design.get("white_c"):
        s = np.zeros(len(c))
        for k_, (c0, c1) in design["white_c"].items():
            s[(c >= c0) & (c <= c1) & (wkeep > 0.5)] = 1.0
    return c, A, Y, {"rows": info, "s": s.tolist(), "layer": lay.tolist(), "wkeep": wkeep.tolist(),
                     "E": {"a": B.rnd(Ea, 3), "y": B.rnd(Ey, 3)}}


def main():
    pre, dpath = sys.argv[1], sys.argv[2]
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    c, A, Y, log = build(design)
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    if design.get("write_candidate"):
        prov = {"route": "美術の見本06 直しの回 Tools/GWWaveGen/as06/fix6_build.py（rows_build.py の写し。numpy、行の断面の作り直し：② と ③ の段に体、下の面を前へ傾ける）",
                "base": "K*′ AS04F (%s, sha256 %s)" % (B.ROWS04F.replace(B.REPO + "/", ""), B.sha(B.ROWS04F)),
                "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False,
                "boat_nearsea_keepout_used": False}
        B.SC.K.write_candidate(pre, c, A, Y, prov)
    else:
        np.savez(pre + "_rows.npz", c=c, A=A, Y=Y)
    B.jdump(pre + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("ROWS_BUILD_DONE", pre, round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
