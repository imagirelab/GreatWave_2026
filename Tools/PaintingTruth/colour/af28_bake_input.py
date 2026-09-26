# -*- coding: utf-8 -*-
"""番号28 第B部：投影ベイクの入力（原画側の符号付き距離と有効域、調色板、線幅、K* の列の範囲）を作る。

使い方（リポジトリの根で実行。py -3.10、numpy・OpenCV だけ）:
    py -3.10 Tools/PaintingTruth/colour/af28_bake_input.py [--build Unity/Build/ArtFirst/28]

入力：
    Unity/Build/ArtFirst/28/partA/stage_a.npz   第A部の中間物（mw_region = 線を両側の色へ吸収した高解像度の色区の地図）。
                                                 SHA-256 を第A部の partA_run.json の記録と照合する。無ければ colour_truth.py を先に実行する。
    Tools/PaintingTruth/colour/colour_truth.json 調色板（palette_display_median）
    Tools/PaintingTruth/targets/line_width_profile.json 原画の輪郭線の幅（外殻線 v0 の角幅）
    Tools/PaintingTruth/painting_truth.json      PaintingCam v1 と表示フレーム
    Unity/Build/ArtFirst/26/kstar/kstar_aXX_meta.json 番号26 の K*（唇先端・内壁の下端の列）
出力（Git 対象外の build フォルダー）：
    bake_input/paint_sdf_rgba16f.bin   高解像度原画の格子（3859×2594、下の行から）の RGBAHalf。4 色区の符号付き距離（表示 px、±15.9 で切る）
    bake_input/paint_valid_r8.bin      同じ格子の R8。255 = 主浪の色区、128 = 主浪から 6 表示 px 以内の空（ここまで有効）、64 = 遠い空、0 = 主浪の外（原画の遮蔽物）
    bake_input/af28_bake_meta.json     Unity が読む平らな JSON（寸法・写像・調色板の 8bit sRGB・線の角幅・K* ごとの列の範囲と SHA-256）
    bake_input/af28_bake_input_record.json 入出力の SHA-256 と記録（線の色の中央値など）
座標：高解像度 px は原画の画素（画素中心が整数）。表示 px は 1920×1080。写像は番号23 v0.2 と同じ。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PT))
sys.path.insert(0, PT)
import truthlib as T  # noqa: E402

PARAMS_REL = "Tools/PaintingTruth/colour/af28_params.json"
STAGE_REL = "Unity/Build/ArtFirst/28/partA/stage_a.npz"
PARTA_RUN_REL = "Docs/Evidence/ArtFirst/28/partA_run.json"
CT_REL = "Tools/PaintingTruth/colour/colour_truth.json"
LW_REL = "Tools/PaintingTruth/targets/line_width_profile.json"
SPEC_REL = "Tools/PaintingTruth/painting_truth.json"
KSTAR_DIR_REL = "Unity/Build/ArtFirst/26/kstar"
CLASSES = ["white", "mizuiro", "ai_mid", "ai_dark"]
CLS_VAL = {"white": 1, "mizuiro": 2, "ai_mid": 3, "ai_dark": 4}
SKY, OUTSIDE = 9, 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def nearest_class_fill(label, holes):
    """holes の画素を、holes でない最も近い画素の値で埋める（Voronoi。第A部の nearest_label_fill と同じ）。"""
    src = (~holes).astype(np.uint8)
    _, idx = cv2.distanceTransformWithLabels(1 - src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(src)
    lut = np.zeros(len(ys) + 1, label.dtype)
    lut[1:] = label[ys, xs]
    out = label.copy()
    out[holes] = lut[idx[holes]]
    return out


def signed_distance(mask):
    """mask（True が内側）の符号付き距離（画素、正が内側）。境界は画素の縁（±0.5）に置く。"""
    m = mask.astype(np.uint8)
    d_in = cv2.distanceTransform(m, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    d_out = cv2.distanceTransform(1 - m, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return np.where(mask, d_in - 0.5, -(d_out - 0.5)).astype(np.float32)


def read_gwb(path):
    """番号26 の .gwb（GWW0 書式）から格子の大きさ、UV0、頂点位置を読む。"""
    with open(path, "rb") as f:
        b = f.read()
    hdr = np.frombuffer(b[:32], np.int32)
    nu, nv, ntri = int(hdr[2]), int(hdr[3]), int(hdr[7])
    n = nu * nv
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2)
    o += n * 8 + n * 8 + ntri * 12
    Pw = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    if o + n * 12 != len(b):
        raise SystemExit(".gwb の容量が合いません: " + path)
    return nu, nv, uv, Pw


def fr_hi_to_disp(mask_hi, s, ox, ss=3):
    """高解像度の 0/1 → 表示フレームの被覆率（第A部の Frame.hi_to_disp_cov と同じ式）。"""
    a = 1.0 / (ss * s)
    bx = (0.5 / ss - ox) / s - 0.5
    by = (0.5 / ss) / s - 0.5
    M = np.array([[a, 0, bx], [0, a, by]], np.float64)
    up = cv2.warpAffine(mask_hi.astype(np.float32), M, (1920 * ss, 1080 * ss), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return up.reshape(1080, ss, 1920, ss).mean(axis=(1, 3))


def uv_warp(spec, nu, nv, Pw, main_band, W_, N):
    """焼き込み用の UV（UV3）の列ごとの u′・行ごとの v′（0〜1、単調）。

    原画視点で、前を向き（空気の側がカメラを向く）、画面内で、主浪（とその 6 px の帯）の上にある四角形について、
    列の間隔（行の間隔）の画面上の長さを全行（全列）で最大にとり、1 テクセルあたり target_px_per_texel 以下になる長さを要求とする。
    世界の長さ offscreen_world_m_per_texel に 1 テクセルを下限にし、合計が N になるように比例配分する。
    """
    x, y, z, _, _ = T.project_world(spec, Pw)
    G = Pw.reshape(nv, nu, 3)
    X = x.reshape(nv, nu)
    Y = y.reshape(nv, nu)
    Z = z.reshape(nv, nu)
    pos = np.array(spec["painting_cam"]["position"], np.float64)
    du = G[:-1, 1:] - G[:-1, :-1]
    dv = G[1:, :-1] - G[:-1, :-1]
    nrm = np.cross(du, dv)
    nrm *= np.sign(np.median(nrm[:, :5, 1]))          # 平らな海の表（+Y）に向きをそろえる
    front = (nrm * (G[:-1, :-1] - pos)).sum(-1) < 0
    cx = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
    cy = 0.25 * (Y[:-1, :-1] + Y[1:, :-1] + Y[:-1, 1:] + Y[1:, 1:])
    on = (Z[:-1, :-1] > 0.2) & (Z[1:, 1:] > 0.2) & (cx >= 0) & (cx <= 1919) & (cy >= 0) & (cy <= 1079)
    q = np.clip(np.round(np.stack([cx, cy], -1)).astype(int), 0, [1919, 1079])
    inmain = main_band[q[..., 1], q[..., 0]] & on
    vis = front & inmain
    su = np.hypot(X[:-1, 1:] - X[:-1, :-1], Y[:-1, 1:] - Y[:-1, :-1])
    sv = np.hypot(X[1:, :-1] - X[:-1, :-1], Y[1:, :-1] - Y[:-1, :-1])
    need_u = np.where(vis, su, 0).max(0)
    need_v = np.where(vis, sv, 0).max(1)
    wu = np.linalg.norm(G[:, 1:] - G[:, :-1], axis=-1).max(0)
    wv = np.linalg.norm(G[1:] - G[:-1], axis=-1).max(1)
    tpx = float(W_["target_px_per_texel"])
    wmin = float(W_["offscreen_world_m_per_texel"])
    au = np.maximum(np.maximum(need_u / tpx, wu / wmin), 1e-3)
    av = np.maximum(np.maximum(need_v / tpx, wv / wmin), 1e-3)
    uw = np.concatenate([[0.0], np.cumsum(au)]) / au.sum()
    vw = np.concatenate([[0.0], np.cumsum(av)]) / av.sum()
    ru = need_u / (au / au.sum() * N)
    rv = need_v / (av / av.sum() * N)
    rec = {"sum_alloc_u_texels_before_scaling": round(float(au.sum()), 1), "sum_alloc_v_texels_before_scaling": round(float(av.sum()), 1),
           "achieved_px_per_texel_u_max": round(float(ru.max()), 3), "achieved_px_per_texel_v_max": round(float(rv.max()), 3),
           "achieved_px_per_texel_u_p99": round(float(np.percentile(ru[need_u > 0], 99)), 3) if (need_u > 0).any() else None,
           "achieved_px_per_texel_v_p99": round(float(np.percentile(rv[need_v > 0], 99)), 3) if (need_v > 0).any() else None,
           "sum_need_u_px": round(float(need_u.sum()), 1), "sum_need_v_px": round(float(need_v.sum()), 1),
           "n_quads_counted": int(vis.sum()),
           "ja": "achieved_px_per_texel＝要求の長さ（画面 px）÷ 配分したテクセル数。列（行）ごとの最大をとった値で、1 以下が目標"}
    return uw, vw, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="Unity/Build/ArtFirst/28")
    a = ap.parse_args()
    t0 = time.time()
    P = json.load(open(os.path.join(REPO, PARAMS_REL), encoding="utf-8"))
    spec = json.load(open(os.path.join(REPO, SPEC_REL), encoding="utf-8"))
    out_dir = os.path.join(REPO, a.build, "bake_input")
    os.makedirs(out_dir, exist_ok=True)

    stage = os.path.join(REPO, STAGE_REL)
    if not os.path.exists(stage):
        raise SystemExit("第A部の中間物がありません。先に colour_truth.py を実行してください: " + STAGE_REL)
    parta = json.load(open(os.path.join(REPO, PARTA_RUN_REL), encoding="utf-8"))
    want = None
    for k, v in parta.items():
        if isinstance(v, dict) and STAGE_REL in v:
            want = v[STAGE_REL]
    got = sha256(stage)
    if want is not None and want != got:
        raise SystemExit("第A部の中間物の SHA-256 が記録と違います: %s（記録 %s）" % (got, want))
    z = np.load(stage, allow_pickle=True)
    reg = z["mw_region"]
    layer = z["mw_layer"]
    Hh, Wh = reg.shape
    s = float(spec["display_frame"]["scale"])
    ox = float(spec["display_frame"]["offset_x"])

    # ---- 色区の地図（主浪）と、空・外側を最も近い色区で埋めた地図（符号付き距離を輪郭の外まで連続にする）
    is_cls = np.isin(reg, [1, 2, 3, 4])
    ext = nearest_class_fill(reg, ~is_cls)
    sdf = np.zeros((Hh, Wh, 4), np.float32)
    clamp = float(P["sdf_clamp_display_px"])
    for k, n in enumerate(CLASSES):
        d = signed_distance(ext == CLS_VAL[n]) * s          # 高解像度 px → 表示 px
        sdf[..., k] = np.clip(d, -clamp, clamp)
    # 同じ画素で正の色区がちょうど 1 つであることを確かめる（分割になっているか）
    npos = (sdf > 0).sum(-1)
    partition_ok = int((npos != 1).sum())

    # ---- 有効域
    band_hi = float(P["paint_valid_sky_band_display_px"]) / s
    d_main = cv2.distanceTransform((~is_cls).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    valid = np.zeros((Hh, Wh), np.uint8)          # 0 = 主浪の外（前景の波・船・右の海など、原画の遮蔽物）
    valid[reg == SKY] = 64                          # 主浪から遠い空（K* がはみ出した所）
    valid[(reg == SKY) & (d_main <= band_hi)] = 128  # 主浪から 6 表示 px 以内の空（有効。最も近い色区の値を使う）
    valid[is_cls] = 255                             # 主浪の色区（有効）

    # ---- 書き出し（Unity の LoadRawTextureData は下の行から）
    f_sdf = os.path.join(out_dir, "paint_sdf_rgba16f.bin")
    sdf[::-1].astype("<f2").tofile(f_sdf)
    f_val = os.path.join(out_dir, "paint_valid_r8.bin")
    np.ascontiguousarray(valid[::-1]).tofile(f_val)

    # ---- 調色板（第A部の表示フレームの中央値 → 8bit sRGB）
    ct = json.load(open(os.path.join(REPO, CT_REL), encoding="utf-8"))
    pal = {}
    for n in CLASSES:
        lab = np.array(ct["palette_display_median"][n]["lab_median"], np.float64)
        rgb8, de = T.lab_to_srgb8_best(lab)
        pal[n] = {"lab": [float(v) for v in lab], "srgb8": [int(v) for v in rgb8[0]] if rgb8.ndim > 1 else [int(v) for v in rgb8],
                  "dE00_rounding": round(float(de), 4)}

    # ---- 原画の輪郭線：線幅（外殻線 v0 の角幅）と色（記録）
    lw = json.load(open(os.path.join(REPO, LW_REL), encoding="utf-8"))
    widths = []
    for sg in lw["segments"]:
        if sg["id"] in ("78", "130", "131"):
            w = np.asarray(sg["width_ref_px"], np.float64)
            r = np.asarray(sg["reason"])
            widths.append(w[(r == 0) & np.isfinite(w)] * s)
    widths = np.concatenate(widths)
    w_px = float(np.median(widths))
    fov = float(spec["painting_cam"]["vertical_fov_deg"])
    px_angle = 2.0 * np.tan(np.radians(fov) / 2.0) / float(spec["display_frame"]["height"])
    line_angle = w_px * px_angle
    # 線の色：外周（空に接する線）の高解像度の線画素のうち、L* が下位 20% の画素（線の芯。縁は空との混色）の Lab 中央値
    ref = T.imread_rgb(T.repo_abs(spec["reference"]["path"]))
    sky = reg == SKY
    near_sky = cv2.dilate(sky.astype(np.uint8), T.disk(3)) > 0
    line_px = (layer == 5) & near_sky
    lab_line = T.srgb8_to_lab(ref[line_px].reshape(-1, 1, 3)).reshape(-1, 3)
    core = lab_line[lab_line[:, 0] <= np.percentile(lab_line[:, 0], 20)]
    line_lab = np.median(core, 0)
    line_rgb8, line_de = T.lab_to_srgb8_best(line_lab)
    line_rgb8 = [int(v) for v in np.asarray(line_rgb8).reshape(-1)[:3]]

    # ---- K*（番号26）の列の範囲と、焼き込み用の UV（UV3）の引き伸ばし
    main_disp = fr_hi_to_disp(is_cls, s, ox) >= 0.5
    band_px = int(round(float(P["uv_warp"]["main_wave_band_display_px"])))
    main_band = cv2.dilate(main_disp.astype(np.uint8), T.disk(band_px)) > 0
    kst = {}
    for key in P["keys"]:
        meta_p = os.path.join(REPO, KSTAR_DIR_REL, "kstar_%s_meta.json" % key)
        gwb_p = os.path.join(REPO, KSTAR_DIR_REL, "kstar_%s.gwb" % key)
        m = json.load(open(meta_p, encoding="utf-8"))
        idx = m["profile"]["index"]
        nu, nv, uv, Pw = read_gwb(gwb_p)
        gsha = sha256(gwb_p)
        if gsha != m["files"]["gwb_sha256"]:
            raise SystemExit("K* の .gwb の SHA-256 が meta と違います: " + key)
        uw, vw, wrec = uv_warp(spec, nu, nv, Pw, main_band, P["uv_warp"], int(P["uv_texture_size"]))
        kst[key] = {"gwb": KSTAR_DIR_REL + "/kstar_%s.gwb" % key, "gwb_sha256": gsha, "meta": KSTAR_DIR_REL + "/kstar_%s_meta.json" % key,
                    "meta_sha256": sha256(meta_p), "nu": nu, "nv": nv,
                    "j_top": int(idx["j_top"]), "j_tip": int(idx["j_tip"]), "j_corner": int(idx["j_corner"]), "j_facebot": int(idx["j_facebot"]),
                    "u3_top": float(uw[idx["j_top"]]), "u3_tip": float(uw[idx["j_tip"]]), "u3_corner": float(uw[idx["j_corner"]]),
                    "u3_facebot": float(uw[idx["j_facebot"]]), "uv3_warp": wrec, "uWarp": uw, "vWarp": vw}

    # ---- Unity が読む平らな JSON（JsonUtility 用）
    unity_meta = {
        "paintW": Wh, "paintH": Hh, "scale": s, "offsetX": ox,
        "sdfFile": "paint_sdf_rgba16f.bin", "validFile": "paint_valid_r8.bin",
        "texSize": int(P["uv_texture_size"]), "sdfClamp": clamp, "encodeLevels": float(P["sdf_encode_levels_per_px"]),
        "depthW": int(P["depth_rt"][0]), "depthH": int(P["depth_rt"][1]),
        "depthTolM": float(P["depth_tolerance_m"]), "depthTolRel": float(P["depth_tolerance_rel"]),
        "seaHeightM": float(P["sea_height_m"]),
        "scoredX0": float(spec["display_frame"]["scored_columns"][0]), "scoredX1": float(spec["display_frame"]["scored_columns"][1]),
        "white": pal["white"]["srgb8"], "mizuiro": pal["mizuiro"]["srgb8"], "aiMid": pal["ai_mid"]["srgb8"], "aiDark": pal["ai_dark"]["srgb8"],
        "lineColor": line_rgb8, "lineAngleRad": line_angle, "lineMinM": float(P["line"]["min_width_m"]), "lineMaxM": float(P["line"]["max_width_m"]),
        "keys": list(P["keys"]),
        "kstar": [{"key": k, "gwb": kst[k]["gwb"], "gwbSha256": kst[k]["gwb_sha256"], "nu": kst[k]["nu"], "nv": kst[k]["nv"],
                   "uTip": kst[k]["u3_tip"], "uFacebot": kst[k]["u3_facebot"], "uTop": kst[k]["u3_top"], "uCorner": kst[k]["u3_corner"],
                   "uWarp": [round(float(v), 7) for v in kst[k]["uWarp"]], "vWarp": [round(float(v), 7) for v in kst[k]["vWarp"]]} for k in P["keys"]],
    }
    f_meta = os.path.join(out_dir, "af28_bake_meta.json")
    with open(f_meta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(unity_meta, f, ensure_ascii=False, indent=1)
        f.write("\n")

    rec = {
        "schema": "GreatWave.AF28.bake_input_record/1",
        "command": "py -3.10 Tools/PaintingTruth/colour/af28_bake_input.py --build " + a.build.replace("\\", "/"),
        "inputs_sha256": {r_: sha256(os.path.join(REPO, r_)) for r_ in [PARAMS_REL, STAGE_REL, CT_REL, LW_REL, SPEC_REL,
                                                                        "Tools/PaintingTruth/colour/af28_bake_input.py", "Tools/PaintingTruth/truthlib.py"]},
        "stage_a_sha256_recorded_partA": want,
        "outputs_sha256": {rel(f_sdf): sha256(f_sdf), rel(f_val): sha256(f_val), rel(f_meta): sha256(f_meta)},
        "paint_grid": [Wh, Hh],
        "partition_violations_px": partition_ok,
        "partition_ja": "空・主浪の外を最も近い色区で埋めた地図の上で、4 つの符号付き距離のうち正がちょうど 1 つでない画素の数（0 が期待値。±0.5 の境界の置き方で境界上の画素がどちらにも入らないことがある）。",
        "valid_px": {"main_wave": int((valid == 255).sum()), "sky_band": int((valid == 128).sum()), "sky_far": int((valid == 64).sum()), "outside_occluder": int((valid == 0).sum())},
        "palette": pal,
        "line": {"width_display_px_median_78_130_131": round(w_px, 4), "n_points": int(len(widths)), "px_angle_rad": px_angle,
                 "line_angle_rad": line_angle, "line_lab_core_median_outer": [round(float(v), 3) for v in line_lab],
                 "line_lab_all_median_outer": [round(float(v), 3) for v in np.median(lab_line, 0)],
                 "line_colour_ja": "外周の線（空から 3 高解像度 px 以内の線画素）のうち L* が下位 20% の画素の中央値。縁の画素は空との混色なので除いた。",
                 "line_srgb8": line_rgb8, "line_rgb_dE00_rounding": round(float(line_de), 4), "n_line_px_hi": int(line_px.sum())},
        "kstar": {k: {kk: vv for kk, vv in v.items() if kk not in ("uWarp", "vWarp")} for k, v in kst.items()},
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, "af28_bake_input_record.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("AF28_BAKE_INPUT_DONE", round(time.time() - t0, 1), "s partition_violations", partition_ok, "line_px", round(w_px, 3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
