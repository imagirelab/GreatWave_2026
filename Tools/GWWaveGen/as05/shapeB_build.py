# -*- coding: utf-8 -*-
"""美術の見本05 の形づくり・やり方 B：主役波 K*′ AS04F の左の部分（行 c −24〜−8 m）を、① から左下へ下りる二つの段（② b区域・③ 最左側の小区域）にする。
py -3.10 -B Tools/GWWaveGen/as05/shapeB_build.py <out_prefix> <design.json>

各行の断面の列 jA..jK（背の頂の列 82〜105 より前 〜 巻きの内の面）を、次の制御点を通る一本のなめらかな線（弦長の PCHIP）で作り直す：
  P_A（列 jA、見本04 のまま）→ 踏み面 → 溝 G（縁の頂より g m 低い）→ 縁の頂 E → 唇の先 T（E より lip m 前）→ 先の下 B →
  引っ込み U1・U2（唇の先より後ろ・下）→ 巻きの内の面の列 jK（見本04 のまま）。
縁の頂 E は、段の窓の中では原画の層の頂の線（READ_CREST）の射線の上の点（原画のカメラから dist m）、段の窓の外（② と ③ の間の湾・③ の左の端）
では背の頂のすぐ前の短い鼻（見本04 の出っ張りの直しと同じ「唇を短くした肩」）。窓の重み s(c) で二つの間をなめらかにつなぐので、
② と ③ の間は縁が途切れる湾になる。行 c ≥ −8 m（K-top）と、右の端の窓（c_keep_blend）より右は見本04 の行のまま。
行の c・格子 400 × 240・目印の列・境の輪は変えない。参照モデル・写真は読まない。原画のカメラは縁の置き場と測りにだけ使う（色は写さない）。
"""
import json
import os
import sys
import time

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeB_common as B  # noqa: E402


def win(c, c0, c1, b0, b1):
    """c0..c1 で 1、外へ b0・b1 m で 0 へ（smoothstep）。"""
    return B.ss((c - (c0 - b0)) / max(b0, 1e-6)) * B.ss(((c1 + b1) - c) / max(b1, 1e-6))


def step_targets(c, design):
    """行ごとの縁の頂 E の (a, y) と、段の重み s(c)、層の番号（2・3、0 は湾）。"""
    nE = len(c)
    Ea = np.full(nE, np.nan); Ey = np.full(nE, np.nan); s = np.zeros(nE); lay = np.zeros(nE, int)
    curves = {}
    for key, L in (("r3", 3), ("r2", 2)):
        st = design["steps"][key]
        q, xs, ys = B.crest_curve(key, st["dist_m"], n=400, dy_px=st.get("dy_px", 0.0))
        o = np.argsort(q[:, 2])
        qc, qa, qy = q[o, 2], q[o, 0], q[o, 1]
        curves[key] = {"c": qc, "a": qa, "y": qy}
        c0, c1 = st["c_window"]
        w = win(c, c0, c1, st["blend"][0], st["blend"][1])
        # 窓の端の外へは、曲線の端の値を延ばす
        ea = np.interp(c, qc, qa); ey = np.interp(c, qc, qy) + st.get("dy_m", 0.0)
        # 縁の高さを、窓の端で下げる（峰の突出を c の向きにも作る。end_drop m を窓の端で）
        drop = st.get("end_drop_m", 0.0) * (1.0 - win(c, c0 + st.get("drop_in", 0.8), c1 - st.get("drop_in", 0.8), 1.0, 1.0))
        ey = ey - drop
        if st.get("y_min_H0") is not None:
            ey = np.maximum(ey, st["y_min_H0"] * B.H0)
        take = w > s
        Ea[take] = ea[take]; Ey[take] = ey[take]; lay[take & (w > 0.05)] = L
        s = np.maximum(s, w)
    return Ea, Ey, s, lay, curves


def pchip_curve(P, n=2000):
    P = np.asarray(P, float)
    d = np.r_[0, np.cumsum(np.sqrt(np.hypot(*np.diff(P, axis=0).T)))]    # 求心（弦長の平方根）
    t = np.linspace(0, d[-1], n)
    return np.c_[PchipInterpolator(d, P[:, 0])(t), PchipInterpolator(d, P[:, 1])(t)]


def arclen(P):
    return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]


def step_row(a, y, E, s, p, crest_a, crest_y):
    """1 行の列 jA..jK を作り直す。E = 段の縁の頂 (a, y)（s = 1 の時）、s = 段の重み。s = 0 なら背の頂のすぐ前の短い鼻。
    外の面（P_A → 溝 → 縁の頂 → 唇の先 T）を列 jA..200 へ、唇の先の下から後ろへ返って元の唇の下・内の面（列 jU、元の点）へつなぎ、
    元の線を列 jK まで使う部分を列 200..jK へ並べる（列 200 = 唇の先の目印を保つ）。元の唇の下より下へ新しい面を出さない（船・手前の海の禁止域）。"""
    jA, jK = p["jA"], p["jK"]
    PA = np.array([a[jA], y[jA]])
    N = np.array([max(crest_a + p["nose_ahead_m"], PA[0] + 0.6), min(crest_y - p["nose_drop_m"], p.get("_nose_cap_y", 1e9))])
    Es = np.array(E) if E is not None and np.all(np.isfinite(E)) else N
    Ee = N + s * (Es - N)
    g = s * p.get("_groove_row", p["groove_m"])
    lip = p["lip_nose_m"] + s * (p["lip_m"] - p["lip_nose_m"])
    th = p["tip_thick_nose_m"] + s * (p["tip_thick_m"] - p["tip_thick_nose_m"])
    ub = p["under_back_nose_m"] + s * (p["under_back_m"] - p["under_back_nose_m"])
    # 溝：縁の頂の後ろに、幅のある U の形の底（G1・G2）。踏み面の始まり P_A との間が狭い時は幅を縮める
    room = max(Ee[0] - PA[0] - 0.6, 0.4)
    w1, w2 = p.get("groove_w1_m", 1.6), p.get("groove_w2_m", 2.7)
    k = min(1.0, room / w2)
    # 溝の底は、元の唇の下の面（船・手前の海の禁止域の上の端）より min_thick m 上にとどめる（段の板を薄くしすぎない・禁止域へ出さない）
    jj_ = np.arange(200, jK)
    PT = p.get("_protect_top")          # (a の格子, その a での禁止域（元の塗りの外）の一番上の y)：無ければ元の唇の下で
    def under_y(aq):
        if PT is not None:
            return float(np.interp(aq, PT[0], PT[1]))
        m_ = np.abs(a[jj_] - aq) < 0.35
        return float(y[jj_][m_].max()) if m_.any() else -1e9
    yu = max(under_y(Ee[0] - w1 * k), under_y(Ee[0] - w2 * k))
    g = float(np.clip(min(g, Ee[1] - (yu + p.get("floor_min_thick_m", 0.45))), 0.0, None)) if s > 0 else g
    G1 = Ee + np.array([-w1 * k, -g]); G2 = Ee + np.array([-w2 * k, -g * p.get("groove_back_frac", 0.85)])
    G = G1
    if PT is not None and p.get("lip_clear_m") is not None:
        need = max(float(np.interp(q, PT[0], PT[1])) for q in np.linspace(Ee[0] - 0.6, Ee[0] + lip, 6)) + p["tip_drop_m"] + th + p["lip_clear_m"]
        if Ee[1] < need:
            Ee = np.array([Ee[0], need])
            G1 = Ee + np.array([-w1 * k, -g]); G2 = Ee + np.array([-w2 * k, -g * p.get("groove_back_frac", 0.85)])
    T = Ee + np.array([lip, -p["tip_drop_m"]])
    Bt = T + np.array([-0.45, -th])
    # 段の面（face_m を与えた時、② の段）：唇の先の下から後ろへ巻き込み（U1）、そこから下へ段の藍の面（U2）を下ろして内の面へつなぐ。
    # 段が「棚の板」ではなく、頂・唇・その下の面を持つ小さな波に読めるように。船・手前の海の禁止域の上の端より下へは出さない（見張り）
    face = []
    jy = Bt[1] - p.get("join_drop_m", 0.2)
    if s > 0.3 and p.get("face_m"):
        fb1, fd1, fb2, fd2 = p["face_m"]
        U1 = Bt + np.array([-fb1 * s, -fd1 * s]); U2 = U1 + np.array([-fb2 * s, -fd2 * s])
        if PT is not None:
            # 段の面の下の端は、船・手前の海の射線の禁止域の上の端より 0.4 m 上にとどめる（見張りの押し上げで面が段々にならないように）
            U1[1] = max(U1[1], float(np.interp(U1[0], PT[0], PT[1])) + 0.4)
            U2[1] = max(U2[1], float(np.interp(U2[0], PT[0], PT[1])) + 0.4, )
            U2[1] = min(U2[1], U1[1] - 0.3)
        face = [U1, U2]
        jy = min(jy, U2[1] - 0.3)
    # 元の線の上のつなぎの点：列 205 以上で、a ≤ Bt_a − ub かつ y ≤ jy の最初の列
    jj = np.arange(205, jK - 8)
    ok = (a[jj] <= (face[-1][0] if face else Bt[0] - ub)) & (y[jj] <= jy)
    jU = int(jj[np.argmax(ok)]) if ok.any() else jK - 8
    PU = np.array([a[jU], y[jU]])
    pre = [np.array([a[jA - 6], y[jA - 6]]), np.array([a[jA - 3], y[jA - 3]]), PA]
    # 踏み面（P_A → 溝の後ろの縁 G2）の途中の点：まっすぐな崖にしないよう、P_A から前へ riser_frac の所を通す
    Rr = PA + np.array([p.get("riser_frac", 0.5) * (G2[0] - PA[0]), 0.62 * (G2[1] - PA[1])])
    mid = ([Rr, G2, G1] if g > 0.05 else []) + [Ee, T, Bt] + face
    post = [PU, np.array([a[jU + 3], y[jU + 3]]), np.array([a[jU + 6], y[jU + 6]])]
    C = pchip_curve(pre + mid + post, 6000)
    sC = arclen(C)
    near = lambda Q: int(np.argmin(np.hypot(C[:, 0] - Q[0], C[:, 1] - Q[1])))
    iA, iT, iU = near(PA), near(T), near(PU)
    # 外の面 jA..200
    na = a.copy(); ny = y.copy()
    jt = 200
    sold = arclen(np.c_[a[jA:jt + 1], y[jA:jt + 1]]); fo = sold / sold[-1]
    fr = p["col_mix_old"] * fo + (1 - p["col_mix_old"]) * np.linspace(0, 1, jt - jA + 1)
    t = sC[iA] + fr * (sC[iT] - sC[iA])
    na[jA:jt + 1] = np.interp(t, sC, C[:, 0]); ny[jA:jt + 1] = np.interp(t, sC, C[:, 1])
    # 唇の先 → つなぎ → 元の線（列 jU..jK）を列 200..jK へ
    Q = np.r_[C[iT:iU + 1], np.c_[a[jU + 1:jK + 1], y[jU + 1:jK + 1]]]
    sQ = arclen(Q)
    sold2 = arclen(np.c_[a[jt:jK + 1], y[jt:jK + 1]]); fo2 = sold2 / sold2[-1]
    fr2 = p["col_mix_old"] * fo2 + (1 - p["col_mix_old"]) * np.linspace(0, 1, jK - jt + 1)
    t2 = fr2 * sQ[-1]
    na[jt:jK + 1] = np.interp(t2, sQ, Q[:, 0]); ny[jt:jK + 1] = np.interp(t2, sQ, Q[:, 1])
    return na, ny, {"E": Ee.tolist(), "G": G1.tolist() if g > 0.05 else None, "T": T.tolist(), "jU": [float(jU), 0.0], "g": [g, 0.0]}


_GP = {}


def protect_top(i, a, y):
    """行 i の、元の塗りの外にある船・手前の海の射線の禁止域の、a ごとの一番上の y（格子の上の端）。禁止域の無い a は −1e9。"""
    import r2_common as R
    if "G" not in _GP:
        zp = np.load(B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
        _GP["G"] = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    bad = _GP["G"][i] & ~R.section_fill(a, y)
    ag = R.GA0 + np.arange(R.NA) * R.GRES
    yg = R.GY0 + np.arange(R.NY) * R.GRES
    has = bad.any(0)
    top = np.full(R.NA, -1e9)
    top[has] = yg[R.NY - 1 - np.argmax(bad[::-1, has], axis=0)] + R.GRES
    # 隣の a へ 0.25 m 広げる（線の補間の間で禁止域へ入らないよう）
    from scipy.ndimage import maximum_filter1d
    top = maximum_filter1d(top, 5)
    return (ag, top)


def protect_guard(c, A, Y, dA, dY, p, step=0.06, max_lift=3.0):
    """作り直した行の唇の下・内の面（列 200..jK）の点のうち、元の行の塗りの外で、船・手前の海の射線の禁止域（仕上げ28 の protect_grids）に
    入る点を、入らなくなるまで上へ押す（列の向きに少しならす）。原画視点で船と手前の海を新しく隠さない（K-boat）。"""
    import r2_common as R
    if not _GP:
        zp = np.load(B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
        _GP["G"] = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    Gp = _GP["G"]
    lifted = {}
    j0, j1 = 200, p["jK"]
    L2 = np.zeros_like(dY)
    rows_ = np.nonzero(np.abs(dA).max(1) + np.abs(dY).max(1) > 1e-6)[0]
    for i in rows_:
        f0 = R.section_fill(A[i], Y[i])
        bad = Gp[i] & ~f0
        an = A[i] + dA[i]; yn = Y[i] + dY[i]
        lift = np.zeros(len(an))
        for j in range(j0 + 3, j1 + 1):
            if abs(dA[i, j]) + abs(dY[i, j]) < 0.05:
                continue
            for _ in range(int(max_lift / step)):
                hit = False
                for t in (0.0, 0.5):            # 点と、次の点との中ほど（線分が禁止域の格子を横切らないように）
                    jn = min(j + 1, j1)
                    aq = an[j] + t * (an[jn] - an[j]); yq = yn[j] + lift[j] + t * (yn[jn] + lift[jn] - yn[j] - lift[j])
                    ia = int(round((aq - R.GA0) / R.GRES)); iy = int(round((yq - R.GY0) / R.GRES))
                    if 0 <= ia < R.NA and 0 <= iy < R.NY and bad[iy, ia]:
                        hit = True
                if hit:
                    lift[j] += step
                else:
                    break
        L2[i] = lift
    # 押し上げの量を行・列の向きに広げてなめらかにする（格子ごとの押し上げの段々を面に残さない）
    from scipy.ndimage import maximum_filter, gaussian_filter
    Ls = gaussian_filter(maximum_filter(L2, size=(5, 15)), (1.5, 5.0))
    Ls[:, :j0 + 3] = 0.0
    for i in rows_:
        an = A[i] + dA[i]; yn = Y[i] + dY[i]
        lift = np.maximum(L2[i], Ls[i])
        if lift.max() > 0:
            import r2_build as B2
            k_ = 1.0
            while k_ > 0.05 and B2.seg_selfx(an, yn + k_ * lift, 0, None) > B2.seg_selfx(A[i], Y[i], 0, None):
                k_ *= 0.8
            if k_ <= 0.05:
                k_ = 0.0
            dY[i] = dY[i] + k_ * lift
            lifted[round(float(c[i]), 2)] = [round(float(lift.max()), 2), round(k_, 2)]
    return dY, lifted


def build(design):
    c, A, Y = B.load_rows()
    A0, Y0 = A.copy(), Y.copy()
    Ea, Ey, s, lay, curves = step_targets(c, design)
    p = design["profile"]
    lo, hi = design["c_range"]
    kb0, kb1 = design["c_keep_blend"]        # 右の端：kb0 で作り直し全部、kb1 で見本04 のまま
    wl = design.get("c_left_blend", [lo - 1.0, lo])
    wkeep = B.ss((kb1 - c) / max(kb1 - kb0, 1e-6)) * B.ss((c - wl[0]) / max(wl[1] - wl[0], 1e-6))
    info = []
    dA = np.zeros_like(A); dY = np.zeros_like(Y)
    for i in np.nonzero(wkeep > 1e-3)[0]:
        jc = B.J_B + int(np.argmax(Y[i, B.J_B:106]))
        pr = dict(p)
        key = {3: "r3", 2: "r2"}.get(int(lay[i]))
        if key and "groove_m" in design["steps"][key]:
            pr["_groove_row"] = design["steps"][key]["groove_m"]
        if key:
            pr.update(design["steps"][key].get("profile", {}))
        if design.get("floor_by_protect", True):
            pr["_protect_top"] = protect_top(i, A[i], Y[i])
        if design.get("nose_cap"):
            kc = np.array(design["nose_cap"], float)
            if kc[0, 0] <= c[i] <= kc[-1, 0]:
                pr["_nose_cap_y"] = float(np.interp(c[i], kc[:, 0], kc[:, 1])) * B.H0
        na, ny, inf = step_row(A[i], Y[i], (Ea[i], Ey[i]), s[i], pr, A[i, jc], Y[i, jc])
        dA[i] = (na - A[i]) * wkeep[i]; dY[i] = (ny - Y[i]) * wkeep[i]
        info.append({"row": int(i), "c": round(float(c[i]), 2), "w": round(float(wkeep[i]), 3), "s": round(float(s[i]), 3), "layer": int(lay[i]),
                     **{k: (B.rnd(v, 2) if v is not None else None) for k, v in inf.items()}})
    sig = design.get("sigma_rows", 0.0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    if design.get("protect_guard", True):
        dY, ginfo = protect_guard(c, A, Y, dA, dY, p)
        info.append({"protect_guard": ginfo})
    # K-top：c ≥ −8 の行と、背の頂の列（≤ jA）は動かさない
    dA[c >= B.C_KTOP] = 0; dY[c >= B.C_KTOP] = 0
    dA[:, :p["jA"]] = 0; dY[:, :p["jA"]] = 0
    A = A + dA; Y = Y + dY
    for AA, Ax in ((A, A0), (Y, Y0)):
        AA[0] = Ax[0]; AA[-1] = Ax[-1]; AA[:, 0] = Ax[:, 0]; AA[:, -1] = Ax[:, -1]
    return c, A, Y, {"rows": info, "s": s.tolist(), "layer": lay.tolist(), "wkeep": wkeep.tolist(),
                     "curves": {k: {kk: B.rnd(vv[::20], 3) for kk, vv in v.items()} for k, v in curves.items()}}


def main():
    pre, dpath = sys.argv[1], sys.argv[2]
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    c, A, Y, log = build(design)
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    if design.get("write_candidate"):
        prov = {"route": "美術の見本05 やり方 B Tools/GWWaveGen/as05/shapeB_build.py（numpy、行の断面の作り直し：② と ③ の段）",
                "base": "K*′ AS04F (%s, sha256 %s)" % (B.ROWS04F.replace(B.REPO + "/", ""), B.sha(B.ROWS04F)),
                "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
        B.SC.K.write_candidate(pre, c, A, Y, prov)
    else:
        np.savez(pre + "_rows.npz", c=c, A=A, Y=Y)
    B.jdump(pre + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("SHAPEB_BUILD_DONE", pre, round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
