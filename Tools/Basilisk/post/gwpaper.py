# -*- coding: utf-8 -*-
"""Feddersen ら 2024（J. Fluid Mech. 1000, A48）と比べるための、巻きの量を Basilisk の窓のコマから測る。

論文の本文（§3.3〜3.4）はこの計算機から読めなかった（出版社と著者のページへの接続が止められている）。
定義は、本作の記録（Docs/Research の調べ）と 2026-10-13 の雲の計算の指令の言葉から組み立てた【推測】。

- 水：f の双一次の補間 > 0.5。海底の固体は水として埋め、底につながる水だけを残す。長さは h0 = 1。
- 覆いかぶさった列：同じ x の縦の列に、水の続き（run）が 2 つ以上ある列（水面が x について多価）。
- 唇の下の空洞（巻きの空洞）A_O：覆いかぶさった列で、いちばん上の水の続きと、その下の水の続きの間の空気の面積。
  着水の前は、唇の先の真下で縦に閉じた形になる。
- 噴流の面積 A_J：覆いかぶさった列の、いちばん上の水の続きの面積。唇が前の水に触れた後は、触れた所より先に
  垂れ下がる唇も足す（触れた所の列の厚みは両側から補間）。空洞 A_O には入れない。
- 着水：唇の先の真下の縦の隙間が 0.015 h0 以下になった最初のコマ（本作の E1a の計画の決め方）、
  または、空洞が閉じた空気の泡になった最初のコマ（早い方）。
- 空洞の向き θ_O と縦横の比 W/L：空洞の画素の 2 次のモーメントの主軸の角度を θ_O とし、
  空洞の縁を −θ_O だけ回してから、軸のそろった楕円を最小二乗で当てはめる（Longuet-Higgins 1982 に倣った指令の読み）。
- 噴流の幅：着水のコマで、空洞の後ろの端（壁）から唇の先までの中ほどの x で、上の水の続きの中の、
  空気までの最短の距離の最大 × 2（噴流の軸に直角の厚み）。
"""
import os, sys, json, math
import numpy as np
from scipy import ndimage
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gwread as G  # noqa: E402

DM = 0.0025          # 測る格子の間隔（h0）。19 m の h0 で 0.0475 m
GAP_TD = 0.015       # 着水とみなす隙間（h0）


def water_grid(fr, dm=DM, back=2.5, front=3.0, ylow=-0.45, pad=0.08):
    """窓のコマから、頂の周りの細かい水の 2 値 W[y, x] を作る（底につながる水だけ）。"""
    f, cs = fr["f"], fr["cs"]
    X0, Y0 = G.coords(fr)
    dx = fr["dx"]
    wet = (f > 0.5) | (cs < 0.5)
    lab = measure.label(wet, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        wet = lab == np.bincount(keep).argmax()
    wet_fluid = wet & (cs > 0.5)
    rows = np.where(wet_fluid.any(1))[0]
    jt = rows.max()
    xc0 = X0[np.where(wet_fluid[jt])[0]].mean()
    ytop = Y0[jt]
    X = np.arange(max(xc0 - back, X0[0]), min(xc0 + front, X0[-1]), dm)
    pad = max(pad, 2.0 * dx)       # 粗い段（9 段など）で頂が切れないように
    Y = np.arange(max(ylow, Y0[0]), min(ytop + pad, Y0[-1] + 0.5 * dx), dm)
    gi = (X - X0[0]) / dx
    gj = (Y - Y0[0]) / dx
    JJ, II = np.meshgrid(gj, gi, indexing="ij")
    F = ndimage.map_coordinates(f, [JJ, II], order=1, mode="nearest")
    CS = ndimage.map_coordinates(cs, [JJ, II], order=1, mode="nearest")
    solid = CS < 0.5
    W = (F > 0.5) | solid
    lab = measure.label(W, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        W = lab == np.bincount(keep).argmax()
    return W, X, Y, solid


def column_runs(W):
    """各列の水の続き：戻り値は列ごとの [(j0, j1), ...]（下から上、j1 を含む）。"""
    ny, nx = W.shape
    P = np.zeros((ny + 2, nx), np.int8)
    P[1:-1] = W
    d = np.diff(P, axis=0)
    s_j, s_i = np.nonzero(d == 1)
    e_j, e_i = np.nonzero(d == -1)
    o = np.lexsort((s_j, s_i)); s_j, s_i = s_j[o], s_i[o]
    o = np.lexsort((e_j, e_i)); e_j, e_i = e_j[o], e_i[o]
    runs = [[] for _ in range(nx)]
    for a, b, i in zip(s_j, e_j - 1, s_i):
        runs[i].append((int(a), int(b)))
    return runs


def ellipse_fit_axis(xy):
    """軸のそろった楕円 A x² + C y² + D x + E y = 1 を最小二乗で当てはめ、半径 (a, b) と中心を返す。"""
    x, y = xy[:, 0], xy[:, 1]
    M = np.stack([x * x, y * y, x, y], 1)
    sol, *_ = np.linalg.lstsq(M, np.ones_like(x), rcond=None)
    A, C, D, E = sol
    if A <= 0 or C <= 0:
        return None
    x0 = -D / (2 * A); y0 = -E / (2 * C)
    R = 1 + A * x0 * x0 + C * y0 * y0
    if R <= 0:
        return None
    return math.sqrt(R / A), math.sqrt(R / C), x0, y0


def analyze_frame(fr, dm=DM, detail=False):
    W, X, Y, solid = water_grid(fr, dm=dm)
    ny, nx = W.shape
    rows = np.where((W & ~solid).any(1))[0]
    jt = rows.max()
    eta = float(Y[jt] + 0.5 * dm)
    xc = float(X[np.where(W[jt] & ~solid[jt])[0]].mean())
    out = dict(t=fr["t"], eta_c=eta, x_c=xc)
    runs = column_runs(W)
    # 前の面の最も急な角度（覆いかぶさる前の、上の面 z(x) から）
    top = np.array([Y[r[-1][1]] if r else np.nan for r in runs])
    k = max(1, int(round(0.01 / dm)))
    s = (top[:-2 * k] - top[2 * k:]) / (2 * k * dm)
    sel = (X[k:-k] > xc) & (X[k:-k] < xc + 1.5)
    out["front_slope_max_deg"] = float(np.degrees(np.arctan(np.nanmax(s[sel])))) if sel.any() else float("nan")
    ov = [i for i in range(nx) if len(runs[i]) >= 2 and xc - 1.0 < X[i] < xc + 2.0 and runs[i][-1][0] > 0]
    # 頂につながる一続きの組だけ（遠くの別の覆いかぶさりを除く）
    if ov:
        groups, g = [], [ov[0]]
        for i in ov[1:]:
            if i == g[-1] + 1:
                g.append(i)
            else:
                groups.append(g); g = [i]
        groups.append(g)
        k0 = min(range(len(groups)), key=lambda q: min(abs(X[groups[q][0]] - xc), abs(X[groups[q][-1]] - xc)))
        ov = groups[k0]
        # 唇が前の水に触れた後、触れた所より先に垂れ下がる唇も同じ噴流として数える（空洞には入れない）：
        # すぐ前（JOIN 以内）にあり、上の面がつながっている組を足す。間の列（触れた所）の厚みは両側から補間する
        JOIN = 0.06
        ext, contact = [], []
        last = ov[-1]
        for g2 in groups[k0 + 1:]:
            if (g2[0] - last) * dm > JOIN:
                break
            if abs(Y[runs[g2[0]][-1][1]] - Y[runs[last][-1][1]]) > 0.05:
                break
            contact += list(range(last + 1, g2[0]))
            ext += g2
            last = g2[-1]
    else:
        ext, contact = [], []
    out["n_ov"] = len(ov)
    if len(ov) < 2:
        out.update(overturned=False)
        return (out, None) if detail else out
    gaps, thick, cav_pix, jet_pix = [], [], [], []
    for i in ov:
        up = runs[i][-1]; lo = runs[i][-2]
        gaps.append((up[0] - lo[1] - 1) * dm)
        thick.append((up[1] - up[0] + 1) * dm)
        cav_pix.append((i, lo[1] + 1, up[0] - 1))
        jet_pix.append((i, up[0], up[1]))
    gaps = np.array(gaps); thick = np.array(thick)
    # 触れた所より先の唇
    thick_ext = [(runs[i][-1][1] - runs[i][-1][0] + 1) * dm for i in ext]
    for i in ext:
        up = runs[i][-1]
        jet_pix.append((i, up[0], up[1]))
    if contact:
        t_a = thick[-1]; t_b = thick_ext[0]
        thick_contact = [t_a + (t_b - t_a) * (q + 1) / (len(contact) + 1) for q in range(len(contact))]
    else:
        thick_contact = []
    i_cav = ov[-1]; i_wall = ov[0]
    i_tip = ext[-1] if ext else ov[-1]
    out.update(overturned=True,
               x_wall=float(X[i_wall] - 0.5 * dm), x_cav_front=float(X[i_cav] + 0.5 * dm), x_tip=float(X[i_tip] + 0.5 * dm),
               y_tip=float(Y[runs[i_tip][-1][0]] - 0.5 * dm),
               gap_tip=float(gaps[-1]), gap_min=float(gaps.min()), n_ext=len(ext), n_contact=len(contact),
               A_O=float(gaps.sum() * dm),
               A_J=float((thick.sum() + sum(thick_ext) + sum(thick_contact)) * dm))
    # 閉じた空気の泡（空洞が閉じたか）
    air = ~W
    lab = measure.label(air, connectivity=1)
    top_lab = set(np.unique(lab[-1])) | set(np.unique(lab[:, 0])) | set(np.unique(lab[:, -1]))
    pockets = []
    for r in measure.regionprops(lab):
        if r.label in top_lab or r.area * dm * dm < 1e-4:
            continue
        cy, cx = r.centroid
        if xc - 1.0 < X[0] + cx * dm < xc + 2.0:
            pockets.append(dict(area=float(r.area * dm * dm), x=float(X[0] + cx * dm), y=float(Y[0] + cy * dm)))
    out["pockets"] = pockets
    out["closed"] = bool(pockets)
    if not detail:
        return out
    # 空洞の画素
    C = np.zeros_like(W)
    for i, j0, j1 in cav_pix:
        if j1 >= j0:
            C[j0:j1 + 1, i] = True
    J = np.zeros_like(W)
    for i, j0, j1 in jet_pix:
        J[j0:j1 + 1, i] = True
    return out, dict(W=W, X=X, Y=Y, C=C, J=J, solid=solid, ov=ov)


def cavity_shape(det):
    """空洞の向き θ_O（度、x 軸から反時計回りを正、−90〜90）、楕円の W/L、モーメントの縦横の比。"""
    C, X, Y = det["C"], det["X"], det["Y"]
    lab = measure.label(C, connectivity=1)
    if lab.max() == 0:
        return None
    big = np.bincount(lab.ravel())[1:].argmax() + 1
    Cm = lab == big
    jj, ii = np.nonzero(Cm)
    px = X[ii]; py = Y[jj]
    mx, my = px.mean(), py.mean()
    cov = np.cov(np.stack([px - mx, py - my]))
    w, v = np.linalg.eigh(cov)
    vmaj = v[:, 1]
    th = math.degrees(math.atan2(vmaj[1], vmaj[0]))
    if th > 90: th -= 180
    if th <= -90: th += 180
    cont = measure.find_contours(np.pad(Cm.astype(float), 1), 0.5)
    cont = max(cont, key=len) - 1.0
    bx = X[0] + cont[:, 1] * (X[1] - X[0]); by = Y[0] + cont[:, 0] * (Y[1] - Y[0])
    c, s_ = math.cos(math.radians(-th)), math.sin(math.radians(-th))
    rx = c * (bx - mx) - s_ * (by - my); ry = s_ * (bx - mx) + c * (by - my)
    fit = ellipse_fit_axis(np.stack([rx, ry], 1))
    res = dict(theta_O_deg=th, aspect_moment=float(math.sqrt(w[0] / w[1])), area_main=float(Cm.sum() * (X[1] - X[0]) ** 2),
               boundary=np.stack([bx, by], 1))
    if fit:
        a, b, x0, y0 = fit
        L, Wd = 2 * max(a, b), 2 * min(a, b)
        res.update(L=L, W=Wd, W_over_L=Wd / L, ellipse=dict(a=a, b=b, x0=x0, y0=y0, theta=th, cx=mx, cy=my),
                   major_along_theta=bool(a >= b))
    return res


def jet_width(det, out):
    """唇の先から壁までの中ほどの x で、噴流（上の水の続き）の中の空気までの距離の最大 × 2。"""
    W, X, Y, J = det["W"], det["X"], det["Y"], det["J"]
    dm = X[1] - X[0]
    D = ndimage.distance_transform_edt(W) * dm
    xm = 0.5 * (out["x_wall"] + out["x_tip"])
    i = int(np.clip(round((xm - X[0]) / dm), 0, len(X) - 1))
    cols = np.where(J.any(0))[0]
    if not len(cols):
        return float("nan"), xm
    i = int(cols[np.argmin(abs(cols - i))])   # 触れた所の列に当たった時は、いちばん近い噴流の列
    xm = float(X[i])
    col = J[:, i]
    return float(2 * D[col, i].max()), xm


def analyze_run(run, stride=1, verbose=False):
    files = G.frames(run, "win")[::stride]
    seq = []
    for p in files:
        fr = G.read_frame(p)
        try:
            o = analyze_frame(fr)
        except Exception as e:
            o = dict(t=fr["t"], error=repr(e))
        o["file"] = os.path.basename(p)
        seq.append(o)
        if verbose:
            print(o["t"], o.get("eta_c"), o.get("n_ov"), o.get("gap_tip"), o.get("closed"))
    return seq


def summarize(run, seq):
    """時刻の列から、崩れ・着水の時刻と、着水のコマの量をまとめる。"""
    ok = [o for o in seq if "error" not in o]
    pre = ok
    i_ov = next((k for k, o in enumerate(ok) if o.get("overturned")), None)
    res = dict(run=run)
    if i_ov is None:
        res["note"] = "覆いかぶさりが出なかった"
        return res
    o_ov = ok[i_ov]
    # 着水：隙間 ≤ GAP_TD か、空洞が閉じた最初のコマ
    i_td = next((k for k in range(i_ov, len(ok)) if ok[k].get("overturned") and
                 (ok[k].get("gap_tip", 9) <= GAP_TD or ok[k].get("closed"))), None)
    hmax = max(o["eta_c"] for o in ok[:(i_td + 1 if i_td is not None else len(ok))])
    # 前の面が鉛直になった時刻（覆いかぶさる前のコマの最も急な角度から内そう）
    t_vert = o_ov["t"]
    if i_ov > 0:
        a0, a1 = ok[i_ov - 1].get("front_slope_max_deg", np.nan), 90.0
        t0, t1 = ok[i_ov - 1]["t"], o_ov["t"]
        if np.isfinite(a0) and a0 < 90:
            t_vert = t0 + (t1 - t0) * 1.0  # 覆いかぶさりを見つけたコマを鉛直の時刻とする（内そうはしない）
    res.update(t_overturn=o_ov["t"], x_c_overturn=o_ov["x_c"], eta_c_overturn=o_ov["eta_c"],
               x_vertical=o_ov.get("x_wall"), eta_c_max=hmax, t_vertical=t_vert)
    if i_td is None:
        res["note"] = "着水が窓の時刻の中に見つからなかった"
        return res
    o_td = ok[i_td]
    fr = G.read_frame(os.path.join(run, o_td["file"]))
    o2, det = analyze_frame(fr, detail=True)
    shp = cavity_shape(det)
    jw, xm = jet_width(det, o2)
    res.update(t_touchdown=o_td["t"], td_by=("closed" if o_td.get("closed") else "gap"),
               x_c_touchdown=o2["x_c"], eta_c_touchdown=o2["eta_c"], x_tip_touchdown=o2["x_tip"],
               A_O=o2["A_O"], A_J=o2["A_J"], jet_width=jw, jet_width_x=xm, gap_tip=o2["gap_tip"])
    if shp:
        res.update({k: v for k, v in shp.items() if k not in ("boundary", "ellipse")})
        res["ellipse"] = shp.get("ellipse")
    # 高さの候補で割った値
    for nm, H in (("Htd", o2["eta_c"]), ("Hov", o_ov["eta_c"]), ("Hmax", hmax)):
        res["A_O_over_%s2" % nm] = o2["A_O"] / H ** 2
        res["A_J_over_%s2" % nm] = o2["A_J"] / H ** 2
        res["jet_width_over_%s" % nm] = jw / H
    res["frame_touchdown"] = o_td["file"]
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="窓のコマから巻きの量を測る")
    ap.add_argument("run")
    ap.add_argument("--out", default=None)
    ap.add_argument("--stride", type=int, default=1)
    a = ap.parse_args()
    seq = analyze_run(a.run, a.stride)
    res = summarize(a.run, seq)
    print(json.dumps({k: v for k, v in res.items()}, ensure_ascii=False, indent=1, default=float))
    if a.out:
        json.dump(dict(summary=res, frames=seq), open(a.out, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
