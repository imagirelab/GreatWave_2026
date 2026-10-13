# -*- coding: utf-8 -*-
"""FLIP45：形の量（計画 plan_ja.md §6.4 の 11 の量。STUDY52 と同じ定義）を、y = 0 の断面の記録（R2）から測る（py -3.10、numpy・scikit-image）。
2026-10-12 FLIP44 の g44_shape.py（変えていない）を写した（計画 §6.4「g44_shape.py を写す」）。変えたのは次の所だけ：
  - FLIP45 の記録の置き場所（Unity/Build/FLIP45/<runs|smoke>/<id>/）と断面のファイルの名前（r2_c*_b*.npz、中身の形は FLIP44 の sec と同じ）。
  - FLIP45 の計算は造波板が x = 0（x_p = 0）。巻き波の長さの目安 Lc は FLIP45 の計算では λ 72.03 m（FLIP42 の R3・R4d は 135.4633 m のまま）。
  - S7 の結果の置き場所（Unity/Build/FLIP45/smoke/S7）。measure_mask・runs・flip_mask の中身は変えていない。
以下は g44_shape.py の説明のまま：
FLIP44：形の量（計画 plan_ja.md §3.3 (b) の 11 の量ほか）を、断面の記録から STUDY52 と同じ定義で測る（py -3.10、numpy・scikit-image）。
`measure_mask` と `runs` は STUDY52 の `Unity/Build/STUDY52/tools/s52_shape.py` をそのまま写した（中身は 1 文字も変えていない）。
`flip_mask` も同じ写しで、海底の扱いだけを足した：礁の上では窓の下の端（静かな水面の 12 m 下）が礁の上の面に近いので、
海底の中（y < 海底）を水として扱う（底につながる水を選ぶ所が礁で切れないように）。平らな海底（水深 42 m）では窓の中に海底がないので、
FLIP42 の R3・R4d では元と同じ値になる（煙の試し S7 で確かめる）。
使い方：
  py -3.10 g44_shape.py --s7                 → R3・R4d の 3 コマを測り、STUDY52 の shape_measures.json と比べる（煙の試し S7）
  py -3.10 g44_shape.py <run_id> [runs|smoke] <frame> [<frame> ...]   → FLIP44 の計算のコマを測って表示
読む物：FLIP42 は Unity/Build/FLIP42/runs/<id>/（cfg.json・ana.json・sec_*.npz）、FLIP44 は Unity/Build/FLIP44/<runs|smoke>/<id>/（cfg.json・ana.json・sec_*.npz）。
"""
import sys, json, math, os, glob
import numpy as np
from skimage import measure

REPO = r"G:/Unity/GreatWave_2026_Fresh"
RUNS42 = REPO + "/Unity/Build/FLIP42/runs"
B44 = REPO + "/Unity/Build/FLIP44"
B45 = REPO + "/Unity/Build/FLIP45"
LC45 = 72.028
SHAPE52 = REPO + "/Unity/Build/STUDY52/shape_measures.json"
FPS = 24.0
FINE = 0.05


# ------------------------------------------------------------------ 記録（STUDY52 の s52_common と同じ決まり。置き場所だけを引数にした）
def run_dir(rid, root=None):
    if root is None or root == "flip42":
        return os.path.join(RUNS42, rid)
    if root.startswith("flip44:"):
        return os.path.join(B44, root.split(":", 1)[1], rid)
    return os.path.join(B45, root, rid)      # 〔FLIP45〕runs・smoke


def run_info(rid, root=None):
    rd = run_dir(rid, root)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    ana = json.load(open(os.path.join(rd, "ana.json"), encoding="utf8"))
    p = cfg["parms"]
    return dict(x_p=p.get("x_p", 0.0), dp=p["dp"], vox=2 * p["dp"], off=ana["still_level_offset_m"], onset=ana.get("onset"), touch=ana.get("touchdown"),
                parms=p, rd=rd)


def sec_frame(rd, frame):
    best = None
    pats = glob.glob(os.path.join(rd, "sec_c*_b*.npz")) + glob.glob(os.path.join(rd, "r2_c*_b*.npz"))   # 〔FLIP45〕r2 も読む
    for p in pats:
        b = os.path.basename(p); f0 = int(b.split("_c")[1].split("_")[0])
        d = np.load(p)
        fr = list(map(int, d["frames"]))
        if frame in fr and frame >= f0 and (best is None or best[0] < f0):
            best = (f0, p, fr.index(frame))
    if best is None:
        return None
    d = np.load(best[1])
    meta = json.loads(str(d["meta"]))
    return d["sdf"][best[2]].astype(np.float32), meta, best[1]


def bed_z(parms, xs_scene):
    """海底の高さ（場面の y）。g44_tanklib.bedy と同じ式。FLIP42 の計算（reef_on なし）は平ら。"""
    h0 = float(parms["h0"])
    if float(parms.get("reef_on", 0.0)) < 0.5:
        return np.full(np.shape(xs_scene), -h0)
    xr = np.asarray(xs_scene) - float(parms["x_p"])
    n = float(parms["rf_slope_n"]); ht = float(parms["rf_h_top"])
    df = h0 - (xr - float(parms["rf_foot"])) / n
    db = ht + (xr - float(parms["rf_top_end"])) / n
    return -np.minimum(h0, np.maximum(ht, np.maximum(df, db)))


# ------------------------------------------------------------------ 水の格子を作る（s52_shape.flip_mask の写し＋海底）
def flip_mask(rid, frame, info):
    S, meta, src = sec_frame(info["rd"], frame)
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"]) - info["x_p"]
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - info["off"]
    water = S < 0
    jt = np.where(water.any(1))[0].max()
    xc0 = xs[np.where(water[jt])[0]].mean()
    X = np.arange(xc0 - 105.0, xc0 + 105.0, FINE)
    Z = np.arange(-12.0, ys[jt] + 1.5, FINE)
    fx = (X - xs[0]) / meta["dx"]; fz = (Z - ys[0]) / meta["dy"]
    ix = np.clip(np.floor(fx).astype(int), 0, meta["nx"] - 2); wx = fx - ix
    iz = np.clip(np.floor(fz).astype(int), 0, meta["ny"] - 2); wz = fz - iz
    A = S[iz][:, ix] * (1 - wx)[None, :] + S[iz][:, ix + 1] * wx[None, :]
    B = S[iz + 1][:, ix] * (1 - wx)[None, :] + S[iz + 1][:, ix + 1] * wx[None, :]
    F = A * (1 - wz)[:, None] + B * wz[:, None]
    M = F < 0
    # 〔FLIP44 で足した〕海底の中を水として扱う（平らな 42 m では窓の中に海底がなく、何も変わらない）
    bz = bed_z(info["parms"], X + info["x_p"]) - info["off"]
    M = M | (Z[:, None] < bz[None, :])
    lab = measure.label(M, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        k = np.bincount(keep).argmax()
        M = lab == k
    return M, X, Z, os.path.basename(src)


# ------------------------------------------------------------------ 量（s52_shape.py の写し。変えていない）
def runs(b):
    if not b.any():
        return []
    d = np.diff(np.concatenate([[0], b.astype(np.int8), [0]]))
    s = np.where(d == 1)[0]; e = np.where(d == -1)[0] - 1
    return list(zip(s, e))


def measure_mask(M, X, Z, zmin_valid=None, xmin_valid=None, flip_extra=None):
    """M[行=z（下から）, 列=x]。X・Z は列・行の座標（Z は静かな水面から、上が正）。"""
    dx = float(X[1] - X[0]); dz = float(Z[1] - Z[0])
    rows = np.where(M.any(1))[0]
    jt = rows.max()
    eta = float(Z[jt] + 0.5 * dz)
    xc = float(X[np.where(M[jt])[0]].mean())
    out = dict(eta_c=eta, x_c=xc)

    def row_info(z):
        j = int(round((z - Z[0]) / dz))
        j = min(max(j, 0), len(Z) - 1)
        rr = [r for r in runs(M[j]) if X[r[1]] > xc - 3.0 * eta]
        return rr

    def xb(z):
        rr = row_info(z)
        return float(X[rr[0][0]] - 0.5 * dx) if rr else float("nan")

    def xf(z):
        rr = row_info(z)
        return float(X[rr[0][1]] + 0.5 * dx) if rr else float("nan")

    def xE(z):
        rr = [r for r in row_info(z) if X[r[0]] < xc + 2.0 * eta]
        return float(X[rr[-1][1]] + 0.5 * dx) if rr else float("nan")

    def has_hood(z):
        rr = [r for r in row_info(z) if X[r[0]] < xc + 2.0 * eta]
        return len(rr) >= 2

    # ---- 体（背・幅・前の足）
    out["back_x07_rel"] = (xb(0.7 * eta) - xc) / eta
    out["back_x09_rel"] = (xb(0.9 * eta) - xc) / eta
    out["back_angle_07_09_deg"] = math.degrees(math.atan2(0.2 * eta, xb(0.9 * eta) - xb(0.7 * eta)))
    out["width07_silhouette"] = (xE(0.7 * eta) - xb(0.7 * eta)) / eta
    out["front_x01_rel"] = (xf(0.1 * eta) - xc) / eta           # 前の面が 0.1 η_c を通る所の、頂からの距離
    out["front_x05_rel"] = (xf(0.5 * eta) - xc) / eta
    out["eta_over_front01"] = 1.0 / out["front_x01_rel"] if out["front_x01_rel"] > 0 else float("inf")
    # ---- 前の面（本体の右端 x_f）：0.1〜0.5 η_c の弦の角度と凹み
    z1, z2 = 0.1 * eta, 0.5 * eta
    xa, xb_ = xf(z2), xf(z1)
    out["face_chord_deg_01_05"] = math.degrees(math.atan2(z2 - z1, xb_ - xa))
    zz = np.arange(z1, z2, dz)
    pts = np.array([[xf(z), z] for z in zz])
    ch = np.array([xb_ - xa, z1 - z2]); chn = ch / np.linalg.norm(ch)
    rel = pts - np.array([xa, z2])
    # 弦より後ろ（水の側）を正：弦の向き（右下）の右手の法線 (−chn_y, chn_x)… の逆
    nrm = np.array([chn[1], -chn[0]])        # 右下向きの弦に対し、左下（後ろ・下）を向く法線
    dev = rel @ nrm
    out["face_concavity_01_05"] = float(dev.max()) / eta if len(dev) else float("nan")
    out["face_convexity_01_05"] = float(-dev.min()) / eta if len(dev) else float("nan")
    # ---- 立った前の輪郭の割合（0.1〜1.0 η_c）
    zs = np.arange(0.1 * eta, eta - 0.5 * dz, dz)
    xe = np.array([xE(z) for z in zs])
    w = max(1, int(round(0.02 * eta / dz)))
    s = np.full_like(xe, np.nan)
    s[w:-w] = -(xe[2 * w:] - xe[:-2 * w]) / (zs[2 * w:] - zs[:-2 * w])
    ang = np.degrees(np.arctan2(1.0, s))
    hood = np.array([has_hood(z) for z in zs])
    ok = ~np.isnan(ang)
    for th in (45, 60):
        st = ((ang >= th) | hood) & ok
        out["steep%d_frac" % th] = float(st.sum()) / max(ok.sum(), 1)
    # ---- 覆いかぶさった列
    cols = []
    j_lo = int(np.searchsorted(Z, 0.2 * eta))
    for i in range(len(X)):
        if X[i] < xc - 0.5 * eta or X[i] > xc + 1.5 * eta:
            continue
        rr = runs(M[:, i])
        if len(rr) >= 2:
            top = rr[-1]; below = rr[-2]
            if top[0] > j_lo and Z[top[0]] > Z[below[1]]:
                # 4 つ目：唇の下の空気の縦の長さ（上の続きの下の端 − その下の水の上の端）
                cols.append((i, float(Z[top[1]] + 0.5 * dz), float(Z[top[0]] - 0.5 * dz), float(Z[top[0]] - Z[below[1]] - dz), False))
        elif len(rr) == 1 and rr[0][0] > j_lo:
            # 原画だけ：唇の下の、前の面の下の端より前は描かれていない（水面は下の端より下）ので、下は空気として数える。
            # 空気の縦の長さは「見える所の下の端（zmin_valid）まで」の下限
            top = rr[0]
            zlow = zmin_valid if zmin_valid is not None else float(Z[0])
            cols.append((i, float(Z[top[1]] + 0.5 * dz), float(Z[top[0]] - 0.5 * dz), float(Z[top[0]] - 0.5 * dz) - zlow, True))
    if cols:
        # 頂にいちばん近い一続きの組
        idx = [c[0] for c in cols]
        groups, g = [], [cols[0]]
        for c in cols[1:]:
            if c[0] == g[-1][0] + 1:
                g.append(c)
            else:
                groups.append(g); g = [c]
        groups.append(g)
        g = min(groups, key=lambda gg: abs(X[gg[0][0]] - xc))
        xw = float(X[g[0][0]] - 0.5 * dx); xt = float(X[g[-1][0]] + 0.5 * dx)
        tops = np.array([c[1] for c in g]); bots = np.array([c[2] for c in g])
        R = xt - xw
        th = tops - bots
        imid = int(round(0.5 * (len(g) - 1)))
        gaps = np.array([c[3] for c in g])
        out.update(dict(
            gap_under_tip=float(gaps[-1]) / eta, gap_under_tip_is_lower_bound=bool(g[-1][4]),
            gap_max=float(gaps.max()) / eta, gap_max_is_lower_bound=bool(g[int(np.argmax(gaps))][4]),
            hood=True,
            hood_wall_x_rel=(xw - xc) / eta, hood_tip_x_rel=(xt - xc) / eta,
            reach=R / eta,
            hood_height=(tops.max() - bots.min()) / eta,
            hood_low_z=float(bots.min()) / eta,
            tip_z=float(0.5 * (tops[-1] + bots[-1])) / eta,
            lip_thick_mid=float(th[imid]) / eta,
            lip_thick_mid_m=float(th[imid]),
            hood_area=float(th.sum() * dx) / eta ** 2,
            reach_m=R, hood_height_m=float(tops.max() - bots.min()), hood_area_m2=float(th.sum() * dx)))
    else:
        out.update(dict(hood=False, reach=0.0, hood_height=0.0, lip_thick_mid=0.0, hood_area=0.0, reach_m=0.0, hood_height_m=0.0, hood_area_m2=0.0))
    # ---- 上の面の高さ（谷・H）：FLIP だけ
    if flip_extra:
        Lc = flip_extra["Lc"]
        top = np.array([Z[np.where(M[:, i])[0].max()] + 0.5 * dz if M[:, i].any() else np.nan for i in range(len(X))])
        mf = (X > xc) & (X <= xc + 0.75 * Lc); mr = (X < xc) & (X >= xc - 0.75 * Lc)
        jf = np.where(mf)[0][np.nanargmin(top[mf])]; jr = np.where(mr)[0][np.nanargmin(top[mr])]
        out.update(dict(trough_front=float(top[jf]) / eta, trough_front_x_rel=float(X[jf] - xc) / eta,
                        trough_rear=float(top[jr]) / eta, trough_rear_x_rel=float(X[jr] - xc) / eta,
                        H_front_over_eta=(eta - float(top[jf])) / eta, H_rear_over_eta=(eta - float(top[jr])) / eta,
                        H_front_m=eta - float(top[jf]), H_rear_m=eta - float(top[jr])))
        # 前の面が静かな水面を切る所
        out["front_x00_rel"] = (xf(0.02 * eta) - xc) / eta
    return out


# ------------------------------------------------------------------ FLIP44 で足した所：コマの選び（STUDY52 の main と同じ決まり）
LC = 135.4633


def series(rid, root, f_from, f_to, Lc=None):
    LC = Lc or (LC45 if (root not in (None, "flip42") and not str(root).startswith("flip44:")) else 135.4633)
    info = run_info(rid, root)
    rows = []
    for fr in range(f_from, f_to + 1):
        M, X, Z, src = flip_mask(rid, fr, info)
        m = measure_mask(M, X, Z, flip_extra=dict(Lc=LC))
        rows.append(dict(frame=fr, t=(fr - 1) / FPS, x_c_from_paddle=m["x_c"], eta_c=m["eta_c"], hood_height=m["hood_height"],
                         hood_height_m=m["hood_height_m"], reach_m=m["reach_m"], hood_area_m2=m["hood_area_m2"], lip_thick_mid_m=m.get("lip_thick_mid_m", 0.0)))
    return info, rows


def measure_three(rid, root=None, f_on=None, f_td=None, Lc=None):
    """巻き始め・いちばん巻いた（巻き始めから着水までで覆いかぶさった高さが最大）・着水の 3 コマを測る（STUDY52 と同じ選び）。"""
    LC = Lc or (LC45 if (root not in (None, "flip42") and not str(root).startswith("flip44:")) else 135.4633)
    info = run_info(rid, root)
    f_on = f_on or info["onset"]["frame"]; f_td = f_td or info["touch"]["frame"]
    _, rows = series(rid, root, f_on, f_td, Lc=LC)
    f_max = max(rows, key=lambda r: r["hood_height_m"])["frame"]
    out = {}
    for name, fr in {"onset": f_on, "max_overturn": f_max, "contact": f_td}.items():
        M, X, Z, src = flip_mask(rid, fr, info)
        m = measure_mask(M, X, Z, flip_extra=dict(Lc=LC))
        m.update(frame=fr, t=(fr - 1) / FPS, x_c_from_paddle=m["x_c"], src=src, dp=info["dp"])
        out[name] = m
    return out


def s7():
    ref = json.load(open(SHAPE52, encoding="utf8"))["flip"]
    res = {"note_ja": "煙の試し S7（FLIP45）：g45_shape.py（g44_shape.py の写し）で R3・R4d を測り、STUDY52 の shape_measures.json と比べる。判定：数の量の全部で差 1e-9 以内",
           "runs": {}}
    worst = 0.0; nkeys = 0; bad = []
    for rid in ("R3", "R4d"):
        r0 = ref[rid]
        got = measure_three(rid, None, r0["onset"]["frame"], r0["contact"]["frame"])
        res["runs"][rid] = {}
        for nm in ("onset", "max_overturn", "contact"):
            a, b = r0[nm], got[nm]
            diffs = {}
            for k, v in a.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    if k not in ("src",) and b.get(k) != v:
                        bad.append((rid, nm, k, v, b.get(k)))
                    continue
                w = b.get(k)
                if w is None:
                    bad.append((rid, nm, k, v, None)); continue
                d = abs(float(w) - float(v)) if (math.isfinite(v) and math.isfinite(w)) else (0.0 if (str(v) == str(w)) else float("inf"))
                diffs[k] = d; worst = max(worst, d); nkeys += 1
            res["runs"][rid][nm] = dict(frame=b["frame"], frame_ref=a["frame"], max_abs_diff=max(diffs.values()) if diffs else None, n=len(diffs))
    res["n_compared"] = nkeys; res["max_abs_diff"] = worst; res["mismatch_nonnumeric"] = [list(map(str, x)) for x in bad]
    res["pass"] = bool(worst <= 1e-9 and not bad)
    return res


if __name__ == "__main__":
    if sys.argv[1] == "--s7":
        r = s7()
        os.makedirs(B45 + "/smoke/S7", exist_ok=True)
        json.dump(r, open(B45 + "/smoke/S7/s7.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
        print(json.dumps({k: r[k] for k in ("n_compared", "max_abs_diff", "mismatch_nonnumeric", "pass")}, ensure_ascii=False))
        for rid, d in r["runs"].items():
            print(rid, d)
    else:
        rid, root = sys.argv[1], sys.argv[2]
        info = run_info(rid, root)
        for f in map(int, sys.argv[3:]):
            M, X, Z, src = flip_mask(rid, f, info)
            m = measure_mask(M, X, Z, flip_extra=dict(Lc=LC))
            print(f, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()})
