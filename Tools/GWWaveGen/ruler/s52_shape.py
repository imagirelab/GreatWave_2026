# -*- coding: utf-8 -*-
"""STUDY52 (A)：形の量を、FLIP42 の断面（R3・R4d）と原画の輪郭から同じ定義で読む（py -3.10、numpy・PIL・scikit-image）。

量の定義は shape_ja.md §2 のとおり（測る前に書いた）。どれも水の領域（水＝真の 2 値の格子）から読む：
  頂     ：水のいちばん高い所。η_c ＝ 静かな水面からの高さ。長さはどれも η_c で割る。
  横の列 ：高さ z ごとに、水の続き（run）を左から並べる。最初の続き＝本体（左端＝背 x_b、右端＝前の面 x_f）。
           本体より前にある続き＝覆いかぶさり（下に空気がある水）。いちばん前の続きの右端＝前の輪郭 x_E。
  縦の列 ：x ごとに上から水の続きを見る。上の続きの下に空気があり、その下にまた水がある列＝覆いかぶさった列。
出力：STUDY52/shape_measures.json（量）、STUDY52/work/s52_frames.json（「いちばん巻いたコマ」を選んだ値の並び）。
"""
import sys, json, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 元は STUDY52/tools の絶対パス
import numpy as np
from PIL import Image, ImageDraw
from skimage import measure
import s52_common as C

PRINT_JSON = C.REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
Y_HORIZON = 1885.0          # 原画（3859×2594 の画素）で、富士の足もとの海と空の境。±15 px の読み（§3.1）
STRETCH = 1.3               # Cartwright & Nakamura 2009：画面の縦が約 30 % 伸びている → 縦を 1/1.3 にして戻す
FINE = 0.05                 # FLIP の水の格子を細かくする間隔（m）。等高線と同じ一次の補間


# ------------------------------------------------------------------ 水の格子を作る
def flip_mask(rid, frame, info):
    S, meta, src = C.sec_frame(rid, frame)
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"]) - info["x_p"]
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - info["off"]
    # 頂のおおよその位置（粗い格子）
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
    # 底につながる水だけ（飛んだ滴を除く）
    lab = measure.label(M, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        k = np.bincount(keep).argmax()
        M = lab == k
    return M, X, Z, os.path.basename(src)


def print_outline():
    d = json.load(open(PRINT_JSON, encoding="utf8"))
    S = {s["id"]: np.array(s["points_ref"], float) for s in d["segments"]}
    outer = np.concatenate([S["78"], S["130"][1:], S["131"][1:], S["132"][1:]])
    inner = S["72"]
    return outer, inner, d


def print_mask(step=2):
    """原画の輪郭で囲んだ水（外の輪郭＋内の輪郭。前の面の下の端からは真下へ、左の端までを水として閉じる）。
    閉じた所（前の面の下の端より下、左の端より下）は形の量に使わない（§3.1）。"""
    outer, inner, d = print_outline()
    W, H = d["reference_size"]
    foot = inner[-1]
    poly = np.concatenate([outer, inner[1:], [[foot[0], Y_HORIZON + 300.0], [outer[0][0], Y_HORIZON + 300.0]]])
    img = Image.new("L", (W // step, H // step), 0)
    ImageDraw.Draw(img).polygon([(float(p[0]) / step, float(p[1]) / step) for p in poly], fill=1)
    M = np.asarray(img).astype(bool)[::-1]            # 行 0 を下に
    xpx = (np.arange(W // step) + 0.5) * step
    ypx = ((np.arange(H // step) + 0.5) * step)[::-1]
    return M, xpx, ypx, outer, inner


# ------------------------------------------------------------------ 量
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


# ------------------------------------------------------------------ 本体
def flip_series(rid):
    info = C.run_info(rid)
    f_on = info["onset"]["frame"]; f_td = info["touch"]["frame"]
    rows = []
    for fr in range(f_on, f_td + 25):
        M, X, Z, src = flip_mask(rid, fr, info)
        m = measure_mask(M, X, Z, flip_extra=dict(Lc=135.4633))
        rows.append(dict(frame=fr, t=(fr - 1) / C.FPS, x_c_from_paddle=m["x_c"], eta_c=m["eta_c"],
                         hood_height=m["hood_height"], hood_height_m=m["hood_height_m"], reach_m=m["reach_m"],
                         hood_area_m2=m["hood_area_m2"], lip_thick_mid_m=m.get("lip_thick_mid_m", 0.0)))
    return info, rows


def main():
    res = {"note_ja": "STUDY52 の形の量。長さ・高さは η_c（静かな水面から頂まで）で割った値。角度は度。定義は shape_ja.md §2。",
           "print": {}, "flip": {}}
    # ---- 原画
    M, xpx, ypx, outer, inner = print_mask(step=2)
    Hd = Y_HORIZON - outer[:, 1].min()
    variants = {
        "drawn": dict(sw=Y_HORIZON, sy=1.0, note="描かれたまま。静かな水面＝水平線（y=1885 px）"),
        "cn": dict(sw=Y_HORIZON, sy=1.0 / STRETCH, note="C&N の縦 30 % の伸びを戻した（縦を 1/1.3）。静かな水面＝水平線"),
        "cn_swl_low": dict(sw=Y_HORIZON + 0.1 * Hd, sy=1.0 / STRETCH, note="感度：静かな水面を水平線より 0.1 η_c（描いた高さ）下に置いた（目が水面から η_c の 1 割上）"),
        "cn_swl_high": dict(sw=Y_HORIZON - 0.1 * Hd, sy=1.0 / STRETCH, note="感度：静かな水面を水平線より 0.1 η_c 上に置いた（目が谷の中）"),
    }
    for k, v in variants.items():
        Zc = (v["sw"] - ypx) * v["sy"]
        m = measure_mask(M, xpx, Zc, zmin_valid=(v["sw"] - inner[-1][1]) * v["sy"])
        foot_z = (v["sw"] - inner[-1][1]) * v["sy"] / m["eta_c"]
        left_z = (v["sw"] - outer[0][1]) * v["sy"] / m["eta_c"]
        dip_z = (v["sw"] - outer[:200, 1].max()) * v["sy"] / m["eta_c"]
        for kk in [kk for kk in m if kk.endswith("_m") or kk.endswith("_m2")]:
            m.pop(kk)          # 原画では m の値はない（画素なので落とす）
        m.update(note_ja=v["note"], eta_c_px=m["eta_c"], visible_front_foot_z=foot_z, back_left_edge_z=left_z, back_lowest_visible_z=dip_z)
        m["eta_c_unit"] = "px（原画 3859×2594 の画素。縦の伸びを戻した読みでは縦を 1/1.3 にした画素）"
        res["print"][k] = m
    res["print_source"] = dict(outline="Tools/PaintingTruth/targets/main_wave_outline_envelope.json（区間 78・130・131・132 が外の輪郭、72 が唇の先から内の壁を通って前の面の下の端まで）",
                               image="Docs/References/Met_JP1847_DP130155.jpg（3859×2594）", horizon_px=Y_HORIZON, stretch=STRETCH,
                               mask_step_px=2)
    # ---- FLIP42
    frames_log = {}
    for rid in ("R3", "R4d"):
        info, rows = flip_series(rid)
        frames_log[rid] = rows
        f_on = info["onset"]["frame"]; f_td = info["touch"]["frame"]
        pre = [r for r in rows if r["frame"] <= f_td]
        f_max = max(pre, key=lambda r: r["hood_height_m"])["frame"]
        sel = {"onset": f_on, "max_overturn": f_max, "contact": f_td}
        res["flip"][rid] = {}
        for name, fr in sel.items():
            Mf, X, Z, src = flip_mask(rid, fr, info)
            m = measure_mask(Mf, X, Z, flip_extra=dict(Lc=135.4633))
            m.update(frame=fr, t=(fr - 1) / C.FPS, x_c_from_paddle=m["x_c"], src=src, dp=info["dp"])
            res["flip"][rid][name] = m
            np.savez_compressed(C.OUT + "/work/mask_%s_%s.npz" % (rid, name), M=Mf, X=X, Z=Z)
    json.dump(res, open(C.OUT + "/shape_measures.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(frames_log, open(C.OUT + "/work/s52_frames.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 表示
    keys = ["eta_c", "front_x01_rel", "eta_over_front01", "front_x05_rel", "back_x07_rel", "back_angle_07_09_deg", "width07_silhouette",
            "face_chord_deg_01_05", "face_concavity_01_05", "face_convexity_01_05", "steep45_frac", "steep60_frac",
            "hood_height", "reach", "lip_thick_mid", "hood_area", "tip_z", "hood_low_z", "hood_wall_x_rel", "gap_under_tip", "gap_max", "visible_front_foot_z", "back_left_edge_z", "back_lowest_visible_z",
            "trough_front", "trough_rear", "H_front_over_eta", "H_rear_over_eta", "front_x00_rel", "trough_front_x_rel"]
    cols = [("P:" + k, res["print"][k]) for k in res["print"]] + [("%s:%s" % (r, n), res["flip"][r][n]) for r in res["flip"] for n in res["flip"][r]]
    print("%-24s" % "", " ".join("%13s" % c[0][:13] for c in cols))
    for k in keys:
        print("%-24s" % k, " ".join("%13s" % (("%.3f" % c[1][k]) if isinstance(c[1].get(k), (int, float)) else "-") for c in cols))
    for rid in res["flip"]:
        print(rid, {n: (v["frame"], round(v["t"], 3), round(v["x_c"], 1)) for n, v in res["flip"][rid].items()})


if __name__ == "__main__":
    main()
