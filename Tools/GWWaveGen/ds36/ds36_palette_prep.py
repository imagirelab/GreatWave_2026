# -*- coding: utf-8 -*-
"""設計36 第「調色板」部：Unity へ渡す調色板のデータを作る（numpy/OpenCV、py -3.10）。

作るもの（Git 対象外の Unity/Build/Design/36/palette/prep/）：
  1) 爪の投影の表：主役波の焼き込みと同じ原画の色区の符号付き距離（設計29修正01 の paint_sdf_rgba16f.bin、高解像度原画の格子）を、
     表示フレームの 2 倍（3840×2160）へ写した RGBA8（1 チャンネル 1 色区、8 段／表示 px、±16 px、下の行から）。爪の頂点には Unity で
     t* の原画視点の画面の位置を UV として付け、この表を引く（t* の原画視点で爪が主役波と同じ原画の色区の色になる。美術優先28 の投影と同じ考え）。
  2) 爪ごとの影の色（一覧の色区）：設計32 の爪の領域（計画 §6 の仮の定義 D25：藍の輪郭線の内側、白＋影。領域は (x0, y0, M) で原点は
     inventory の params.crop）の中の原画の色区（mw_colour_labels_hi.png）の割合と、白でない色区（淡い水色・藍中・藍濃）で最も多いもの
     ＝「一覧の色区の影の色」。t* で原画のカメラに背を向ける爪の縁の側面と下面に使う。
  3) 周りの海（near・far）の 4 段：t* の高さ y* と、近くの最も高い所 Hloc（格子の上の最大値の広がり）で割った相対の高さ h から
     白（h ≥ 0.45、白の時間場のある頂点）・淡い水色（0.30〜）・藍中（0.14〜）・藍濃（それ未満と谷・平らな海）の段を決める。
     さらに谷（y* < −0.5 m）のまわりの海の高さの面に、谷の印のぼかしから作ったなめらかな藍中の 1 段を置く（谷を読ませる段）。
     頂点ごとの UV3（u = 0.05 + 0.9·s、v = 0.5）と、u に沿った 4 色区の符号付き距離の表（256×256、行はどれも同じ）を書く。
     DS30SheetPlayer の既存の読み込み（sdfPath・uv3File）でそのまま読める形。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds36/ds36_palette_prep.py
"""
import hashlib
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "36", "palette", "prep")
LABELS = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels.png")
LABELS_HI = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels_hi.png")
REGIONS = os.path.join(REPO, "Unity", "Build", "Design", "32", "list+ids", "_regions.npy")
INVENTORY = os.path.join(REPO, "Unity", "Build", "Design", "32", "list+ids", "ds32_claw_inventory.json")
LAYOUT = os.path.join(REPO, "Unity", "Build", "Design", "33", "claws", "ds33_claw_layout.json")
PAINT_SDF = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "bake_kp", "bake_input", "paint_sdf_rgba16f.bin")
PAINT_META = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "bake_kp", "bake_input", "af28_bake_meta.json")
SEA = os.path.join(REPO, "Unity", "Build", "Design", "30", "sea")

LEVELS = 8.0            # 符号付き距離の 1 px あたりの段（±127.5/8 ≈ ±16 px）
# 周りの海の段（相対の高さ h の境）。白は白の時間場（第A部の T_white）のある頂点だけ
SEA_BOUNDS = {"white": 0.45, "mizuiro": 0.30, "ai_mid": 0.14}
SEA_HLOC_MIN = (0.8, 2.0)   # Hloc がこの範囲で 0 → 1 に効く（平らな海のうねりは段を作らない）
SEA_KERNEL = {"near": (9, 41), "far": (5, 11)}  # 最大値の広がり（行, 列）
TROUGH_Y = -0.5            # 谷の底（t* の y、m）
RIM_SIGMA = (1.2, 10.0)    # 谷の印のぼかし（行, 列の格子の幅。行 約 2.1 m、列 約 0.22 m → 約 2.5 m, 2.2 m）
RIM_GAIN = 2.5             # ぼかしの値の倍率（谷の縁から約 1 σ で藍中の境を切る）
RIM_S = 0.26               # 縁の値の上限（藍中の段の中、淡い水色の境 0.30 より下）
RIM_Y_MAX = 0.3            # 縁は海の高さまで（m）
RIM_ROW_MIN = 3            # 主役波との継ぎ目の側の行は段にしない
RAMP_N = 256
RAMP_SCALE = 400.0          # s の単位 → 段


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def imread(p, flag=cv2.IMREAD_UNCHANGED):
    return cv2.imdecode(np.fromfile(p, np.uint8), flag)


def sdf_channels(lab_filled, classes=(1, 2, 3, 4)):
    """色区ごとの符号付き距離（内側が正、px）→ RGBA8。"""
    out = np.zeros(lab_filled.shape + (4,), np.uint8)
    for ch, k in enumerate(classes):
        m = (lab_filled == k).astype(np.uint8)
        if m.sum() == 0:
            out[..., ch] = 0
            continue
        din = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        dout = cv2.distanceTransform(1 - m, cv2.DIST_L2, 5)
        sd = np.where(m > 0, din - 0.5, -(dout - 0.5))
        out[..., ch] = np.clip(np.round(sd * LEVELS + 127.5), 0, 255).astype(np.uint8)
    return out


def paint_sdf_display2x():
    """主役波の焼き込みと同じ原画の色区の符号付き距離（設計29修正01 の paint_sdf_rgba16f.bin、高解像度原画の格子 3859×2594、行は下から、
    値は表示の px、空・主浪の外は最も近い色区で埋めてある）を、表示フレームの 2 倍（3840×2160）へ写す（双線形）。"""
    meta = json.load(open(PAINT_META, encoding="utf-8"))
    pw, ph, sc, ox = meta["paintW"], meta["paintH"], meta["scale"], meta["offsetX"]
    a = np.fromfile(PAINT_SDF, np.float16).reshape(ph, pw, 4).astype(np.float32)
    H2, W2 = 2 * 1080, 2 * 1920
    Y, X = np.mgrid[0:H2, 0:W2].astype(np.float32)
    xd = (X + 0.5) / 2 - 0.5; yd = (Y + 0.5) / 2 - 0.5
    xr = (xd + 0.5 - ox) / sc - 0.5
    yr = (ph - 1) - ((yd + 0.5) / sc - 0.5)          # 格子は下の行から
    out = np.stack([cv2.remap(a[..., k], xr, yr, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) for k in range(4)], -1)
    return out, meta


def claw_part():
    lab = imread(LABELS)
    # 爪の投影の表：主役波の焼き込みと同じ原画の色区（設計36 の最初の版は mw_colour_labels.png を埋めた表で、主役波の焼き込みの原画の色区と
    # 0.4% の画素で違い、爪の縁に余計な色の境ができて色区の項目を悪くした。同じ出典にそろえる）
    sd, meta = paint_sdf_display2x()
    H, W = sd.shape[:2]
    rgba = np.clip(np.round(sd * LEVELS + 127.5), 0, 255).astype(np.uint8)
    raw = np.ascontiguousarray(rgba[::-1])       # Texture2D.LoadRawTextureData は下の行から
    p_raw = os.path.join(OUT, "ds36_claw_label_sdf_3840x2160_rgba8.bin")
    raw.tofile(p_raw)
    filled = (sd.argmax(-1) + 1).astype(np.uint8)
    p_fill = os.path.join(OUT, "ds36_labels_filled_display2x.png")
    cv2.imencode(".png", filled)[1].tofile(p_fill)
    lab_ok = (lab >= 1) & (lab <= 4)
    agree_disp = float((filled[1::2, 1::2][lab_ok] == lab[lab_ok]).mean())

    # 爪ごとの一覧の色区（設計32 の領域、高解像度の原画の画素）
    labhi = imread(LABELS_HI)
    regs = np.load(REGIONS, allow_pickle=True)
    inv = json.load(open(INVENTORY, encoding="utf-8"))
    lay = json.load(open(LAYOUT, encoding="utf-8"))
    ids = [c["id"] for c in lay["claws"]]
    CROP = inv["params"]["crop"]      # [x0, y0, x1, y1]（設計32 の切り出し。領域の局所座標の原点）
    reg = {str(r[0]): r[1] for r in regs}
    per = []
    names = {1: "white", 2: "mizuiro", 3: "ai_mid", 4: "ai_dark"}
    for cid in ids:
        rec = {"id": cid}
        if cid not in reg:
            rec.update({"n_px": 0, "shadow_class": 1, "shadow_name": "mizuiro", "note_ja": "領域なし（既定の淡い水色）"})
            per.append(rec)
            continue
        # 設計32 の領域は (x0, y0, M)、原点は切り出し（inventory の params.crop）の左上。高解像度原画の座標（ref）へ戻す
        x0, y0, m = reg[cid]
        x0 += CROP[0]; y0 += CROP[1]
        m = m.astype(bool)
        sub = labhi[y0:y0 + m.shape[0], x0:x0 + m.shape[1]][m]
        cnt = {names[k]: int((sub == k).sum()) for k in (1, 2, 3, 4)}
        cnt["line"] = int((sub == 5).sum()); cnt["other"] = int(len(sub) - sum(cnt.values()))
        tot4 = max(1, sum(cnt[names[k]] for k in (1, 2, 3, 4)))
        frac = {k: cnt[k] / tot4 for k in names.values()}
        sh = [(cnt[names[k]], k) for k in (2, 3, 4)]
        best = max(sh)
        sc = best[1] if best[0] > 0 else 2
        rec.update({"n_px": int(len(sub)), "counts": cnt, "fractions_4": {k: round(v, 4) for k, v in frac.items()},
                    "shadow_label": sc, "shadow_class": sc - 1, "shadow_name": names[sc],
                    "shadow_px": int(best[0]), "region_ref_x0y0": [int(x0), int(y0)], "region_shape": [int(m.shape[0]), int(m.shape[1])]})
        per.append(rec)
    claws = {"schema": "GreatWave.DS36.claw_palette/1",
             "note_ja": "shadow_class は爪の面の色区の番号（0 白、1 淡い水色、2 藍中、3 藍濃）。一覧の色区＝設計32 の爪の領域の中の原画の色区（mw_colour_labels_hi.png）で、"
                        "白でない色区のうち最も画素の多いもの。領域に白でない画素がなければ淡い水色。",
             "sources": {"labels": [os.path.relpath(LABELS, REPO), sha256(LABELS)], "labels_hi": [os.path.relpath(LABELS_HI, REPO), sha256(LABELS_HI)],
                         "regions": [os.path.relpath(REGIONS, REPO), sha256(REGIONS)], "inventory": [os.path.relpath(INVENTORY, REPO), sha256(INVENTORY)],
                         "layout": [os.path.relpath(LAYOUT, REPO), sha256(LAYOUT)]},
             "label_sdf": {"file": os.path.basename(p_raw), "width": W, "height": H, "levels_per_px": LEVELS, "rows": "bottom_up", "sha256": sha256(p_raw),
                           "frame_ja": "表示フレーム（1920×1080）の 2 倍の格子。ビューポートの (0,0)〜(1,1) が表の全体",
                           "source": [os.path.relpath(PAINT_SDF, REPO), sha256(PAINT_SDF)], "source_meta": [os.path.relpath(PAINT_META, REPO), sha256(PAINT_META)],
                           "agree_with_mw_colour_labels_display": round(agree_disp, 5),
                           "channels_ja": "R 白、G 淡い水色、B 藍中、A 藍濃。値 = 符号付き距離（表示の px、内側が正）× 8 + 127.5"},
             "crop_ref": CROP, "claws": per}
    json.dump(claws, open(os.path.join(OUT, "ds36_claw_palette.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {}
    for r in per:
        by[r["shadow_name"]] = by.get(r["shadow_name"], 0) + 1
    return {"claws": len(per), "shadow_class_counts": by, "label_sdf_sha256": claws["label_sdf"]["sha256"]}


def tstar_world(pkg):
    d = json.load(open(os.path.join(pkg, "ds27_keypose.json"), encoding="utf-8"))
    R, C, L = d["rows"], d["cols"], d["layers"]
    n = R * C
    lay = d["t_star_layer"]
    hi = np.memmap(os.path.join(pkg, d["pos_file"]), np.uint16, "r", shape=(L, n, 4))[lay].astype(np.float64)
    lo = np.memmap(os.path.join(pkg, d["pos_lo_file"]), np.uint8, "r", shape=(L, n, 4))[lay].astype(np.float64)
    bmin = np.array(d["bbox_min"]); bsz = np.array(d["bbox_size"])
    pos = bmin + (hi[:, :3] + lo[:, :3] / 255.0 - 0.5) / 65535.0 * bsz
    ft = np.array(d["frame"]["tau"]); fo = np.array(d["frame"]["origin"])
    o = fo[np.argmin(np.abs(ft - d["knot_tau"][lay]))]
    w = pos + o
    tw = np.fromfile(os.path.join(pkg, d["twhite_file"]), np.float32)
    return d, w.reshape(R, C, 3), tw.reshape(R, C)


def sea_part():
    res = {}
    bnd = SEA_BOUNDS
    lo_hi = {3: (-1e9, bnd["ai_mid"]), 2: (bnd["ai_mid"], bnd["mizuiro"]), 1: (bnd["mizuiro"], bnd["white"]), 0: (bnd["white"], 1e9)}
    # u に沿った表：s = (u − 0.05)/0.9
    u = (np.arange(RAMP_N) + 0.5) / RAMP_N
    s = (u - 0.05) / 0.9
    ramp = np.zeros((RAMP_N, 4), np.uint8)
    for k, (a, b) in lo_hi.items():
        mg = np.minimum(s - a, b - s)
        ramp[:, k] = np.clip(np.round(mg * RAMP_SCALE + 127.5), 0, 255)
    tex = np.ascontiguousarray(np.repeat(ramp[None, :, :], RAMP_N, axis=0))
    p_ramp = os.path.join(OUT, "ds36_sea_ramp_256_rgba8.bin")
    tex.tofile(p_ramp)
    res["ramp"] = {"file": p_ramp, "size": RAMP_N, "sha256": sha256(p_ramp), "scale_per_s": RAMP_SCALE, "bounds_h": bnd}
    for name in ("near", "far"):
        pkg = os.path.join(SEA, name)
        d, w, tw = tstar_world(pkg)
        y = w[..., 1].astype(np.float32)
        kr, kc = SEA_KERNEL[name]
        # 列は一周する（最後の列は最初の列の写し）ので、列の方向は巻いて広げる
        pad = kc
        yp = np.concatenate([y[:, -pad - 1:-1], y, y[:, 1:pad + 1]], axis=1)
        hl = cv2.dilate(yp, np.ones((2 * kr + 1, 2 * kc + 1), np.uint8), borderType=cv2.BORDER_REPLICATE)[:, pad:-pad]
        wgt = np.clip((hl - SEA_HLOC_MIN[0]) / (SEA_HLOC_MIN[1] - SEA_HLOC_MIN[0]), 0, 1)
        wgt = wgt * wgt * (3 - 2 * wgt)
        h = np.where(hl > 1e-3, y / np.maximum(hl, 1e-3), 0.0) * wgt
        h = np.clip(h, 0.0, 1.0)
        white_ok = tw < 1e8
        # 白の時間場のない頂点は白の段へ入れない（淡い水色の上限で止める）
        s_v = np.where(white_ok, h, np.minimum(h, bnd["white"] - 0.02))
        # 谷を読ませる段（設計36、段階5確認 §6.1 の 2）：谷（t* の y < TROUGH_Y）の底は藍濃のまま、谷のまわりの海の高さの面（y < RIM_Y_MAX）に
        # 谷の印のぼかし（行 σ RIM_SIGMA[0]・列 σ RIM_SIGMA[1] の格子の幅、列は一周）から作ったなめらかな値 s = RIM_S·clip(RIM_GAIN·ぼかし) を置き、
        # 藍中の 1 段（s ≥ 藍中の境）にする。値がなめらかなので、段の境は三角形の中の等値線になり、頂点ごとのぎざぎざが出ない。
        # 主役波との継ぎ目（行 0 の側、行 < RIM_ROW_MIN）には段を置かない（色の段が継ぎ目に沿って見えないように）
        trough = (y < TROUGH_Y).astype(np.float32)
        rim = np.zeros(y.shape, bool)
        if name == "near" and trough.any():
            sr, sc = RIM_SIGMA
            pc = int(4 * sc) + 1
            tp = np.concatenate([trough[:, -pc - 1:-1], trough, trough[:, 1:pc + 1]], axis=1)
            bl = cv2.GaussianBlur(tp, (0, 0), sigmaX=sc, sigmaY=sr, borderType=cv2.BORDER_REPLICATE)[:, pc:-pc]
            val = RIM_S * np.clip(RIM_GAIN * bl, 0.0, 1.0)
            ok = (trough == 0) & (y < RIM_Y_MAX) & (s_v < bnd["ai_mid"])
            ok[:RIM_ROW_MIN] = False
            s_v = np.where(ok, np.maximum(s_v, val), s_v)
            rim = ok & (val >= bnd["ai_mid"])
        uv3 = np.stack([0.05 + 0.9 * s_v, np.full_like(s_v, 0.5)], -1).astype(np.float32)
        p_uv = os.path.join(OUT, "ds36_sea_uv3_%s_f32.bin" % name)
        np.ascontiguousarray(uv3.reshape(-1, 2)).tofile(p_uv)
        cls = np.full(y.shape, 3, np.int8)
        cls[s_v >= bnd["ai_mid"]] = 2
        cls[s_v >= bnd["mizuiro"]] = 1
        cls[s_v >= bnd["white"]] = 0
        cnt = {nm: int((cls == k).sum()) for k, nm in enumerate(["white", "mizuiro", "ai_mid", "ai_dark"])}
        trough = y < -0.5
        res[name] = {"uv3_file": p_uv, "uv3_sha256": sha256(p_uv), "rows": int(y.shape[0]), "cols": int(y.shape[1]),
                     "y_tstar_min": float(y.min()), "y_tstar_max": float(y.max()), "vertex_class_counts": cnt,
                     "trough_vertices_y_lt_-0.5": int(trough.sum()), "trough_class_counts": {nm: int(((cls == k) & trough).sum()) for k, nm in enumerate(["white", "mizuiro", "ai_mid", "ai_dark"])},
                     "white_time_field_vertices": int(white_ok.sum()), "kernel_rows_cols": [kr, kc],
                     "trough_rim_vertices_ai_mid": int(rim.sum()),
                     "grid_spacing_m_median": {"rows": float(np.median(np.linalg.norm(np.diff(w, axis=0), axis=-1))), "cols": float(np.median(np.linalg.norm(np.diff(w, axis=1), axis=-1)))},
                     "package": [os.path.relpath(os.path.join(pkg, "ds27_keypose.json"), REPO), sha256(os.path.join(pkg, "ds27_keypose.json"))]}
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {"schema": "GreatWave.DS36.palette_prep/1", "claw": claw_part(), "sea": sea_part(),
           "code_sha256": sha256(os.path.abspath(__file__)),
           "params": {"levels": LEVELS, "sea_bounds": SEA_BOUNDS, "sea_hloc_min": SEA_HLOC_MIN, "sea_kernel": SEA_KERNEL, "ramp_n": RAMP_N, "ramp_scale": RAMP_SCALE,
                      "trough_y": TROUGH_Y, "rim_sigma": RIM_SIGMA, "rim_gain": RIM_GAIN, "rim_s": RIM_S, "rim_y_max": RIM_Y_MAX, "rim_row_min": RIM_ROW_MIN}}
    json.dump(rep, open(os.path.join(OUT, "ds36_palette_prep.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
