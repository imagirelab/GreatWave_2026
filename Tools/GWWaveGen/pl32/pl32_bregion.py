# -*- coding: utf-8 -*-
"""仕上げ32：b区域（Q16・Q21、大波の背の左肩の第二の波頭）の爪を原画から数え直す（numpy・OpenCV。Unity の描画ではない）。

設計32 の一覧の b区域の爪は、利用者の爪 100 本のうち b区域にあった 14 本（と上側の C172）からだけ作った（Design_32 §2.2「b区域の爪を全部数えたわけではない」）。
美術優先29 の骨格化の道具（af29_claw_inventory.process_zone：白の骨格 → ストローク → 端点を持つストローク＝爪）を、主浪の範囲の外にある b区域の帯に当て、
爪の候補を全部取り出す。帯は Q16 の調べの帯（Tools/GWWaveGen/kstar3/candA4_band_targets.json、原画視点の表示 px）を上へ 25 px・下へ 40 px 広げ、
左右の端を延ばし、主浪の範囲（af29 の main）を除いたもの。

出力（Git 対象外）：Unity/Build/Polish/32/list/pl32_bregion_candidates.json（原画 DP130155 の画素の根元・先端・中心線・長さ・幅）と、確認の図。
"""
import json
import os
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
sys.path.insert(0, REPO + "/Tools/PaintingTruth/claws29")
import truthlib as T  # noqa: E402
import af29_claw_inventory as AF  # noqa: E402

BAND = REPO + "/Tools/GWWaveGen/kstar3/candA4_band_targets.json"
OUT = REPO + "/Unity/Build/Polish/32/list"
A_DISP, X_OFF = 0.416345, 156.66153
PAD_TOP_D, PAD_BOT_D = 25.0, 40.0
X_LEFT_D, X_RIGHT_D = 165.0, 780.0


def d2r(q):
    q = np.asarray(q, np.float64)
    return np.stack([(q[..., 0] + 0.5 - X_OFF) / A_DISP - 0.5, (q[..., 1] + 0.5) / A_DISP - 0.5], -1)


def r2d(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + X_OFF, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


def zone_polygon_ref(prm):
    b = json.load(open(BAND, encoding="utf-8"))
    top = np.array(b["top_smooth"]); bot = np.array(b["bottom_smooth"])
    xs = np.arange(X_LEFT_D, X_RIGHT_D + 1e-6, 10.0)
    # 帯の外は端の 3 点の傾きで延ばす
    def ext(curve, x):
        cx, cy = curve[:, 0], curve[:, 1]
        y = np.interp(x, cx, cy)
        lo, hi = x < cx[0], x > cx[-1]
        sl0 = (cy[3] - cy[0]) / (cx[3] - cx[0]); sl1 = (cy[-1] - cy[-4]) / (cx[-1] - cx[-4])
        y = np.where(lo, cy[0] + sl0 * (x - cx[0]), y)
        y = np.where(hi, cy[-1] + sl1 * (x - cx[-1]), y)
        return y
    yt = ext(top, xs) - PAD_TOP_D
    yb = ext(bot, xs) + PAD_BOT_D
    poly_d = np.concatenate([np.stack([xs, yt], 1), np.stack([xs[::-1], yb[::-1]], 1)], 0)
    return d2r(poly_d), poly_d


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    spec = T.load_spec()
    man = T.load_manual()
    prm = T.load_json(AF.PARAMS_PATH)
    ex = spec["extraction"]
    polys = man["polygons_ref"]
    ref_rgb = T.imread_rgb(T.repo_abs(spec["reference"]["path"]))
    lab_ref = T.srgb8_to_lab(ref_rgb).astype(np.float32)
    fills = [polys["sky_fill_cartouche"]["points"], polys["sky_fill_signature"]["points"]]
    barriers = list(man.get("barriers_ref", {}).values())
    sky_ref = T.segment_sky(lab_ref, ex["sky"], fills, barriers)
    ochre_ref = T.ochre_mask(lab_ref, sky_ref, ex["ochre"])
    pal = T.load_json(AF.PALETTE_JSON)
    centres = np.array([pal["classes_lloyd_centers_lab"][k] for k in AF.CLASS_NAMES], np.float32)
    print("paint %.1fs" % (time.time() - t0), flush=True)
    zpoly, zpoly_d = zone_polygon_ref(prm)
    main_zone = np.array(prm["zones"][0]["points"], np.float64)
    zm = T.poly_mask(sky_ref.shape, zpoly.tolist()) & ~T.poly_mask(sky_ref.shape, main_zone.tolist())
    # 範囲の多角形（主浪を除いた後の外周）
    cs, _ = cv2.findContours(zm.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cmax = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float64)
    zd = dict(id="bregion", name_ja="b区域（大波の背の左肩の第二の波頭。Q16・Q21）", points=cmax.tolist(), rows="b区域",
              mask_classes=["white"], body_open_radius_ref_px=45)
    Z = AF.process_zone(zd, prm, ref_rgb, lab_ref, sky_ref, ochre_ref, centres)
    print("zone %.1fs claws %d excluded %d" % (time.time() - t0, len(Z["claws"]), len(Z["excluded"])), flush=True)
    cands = []
    for i, c in enumerate(Z["claws"]):
        C = np.asarray(c["C"], np.float64) + Z["off"]           # 根元 → 先端（原画 px）
        L = float(np.hypot(*np.diff(C, axis=0).T).sum())
        DT = Z["DT"]
        q = np.clip(np.round(np.asarray(c["C"])).astype(int), 0, [DT.shape[1] - 1, DT.shape[0] - 1])
        hw = DT[q[:, 1], q[:, 0]]
        cands.append(dict(k=i, root_ref=C[0].round(1).tolist(), tip_ref=C[-1].round(1).tolist(), centerline_ref=C.round(1).tolist(),
                          length_ref_px=round(L, 1), halfwidth_median_ref_px=round(float(np.median(hw)), 2), kind=c["kind"],
                          root_in_body=c["root_in_body"], root_by_width_jump=c["root_by_width_jump"]))
    out = dict(schema="GreatWave.Polish32.bregion_candidates/1", zone_ref=cmax.round(1).tolist(), zone_display=r2d(cmax).round(2).tolist(),
               band_source=BAND.replace(REPO + "/", ""), pad_display_px=[PAD_TOP_D, PAD_BOT_D], x_display=[X_LEFT_D, X_RIGHT_D],
               stats=Z["stats"], excluded=Z["excluded"], candidates=cands, elapsed_s=round(time.time() - t0, 1))
    json.dump(out, open(OUT + "/pl32_bregion_candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o))
    # 確認の図（原画の b区域を 1:1 で、候補の中心線と根元・先端）
    x0, y0 = np.floor(cmax.min(0)).astype(int) - 20
    x1, y1 = np.ceil(cmax.max(0)).astype(int) + 20
    x0, y0 = max(0, x0), max(0, y0)
    img = cv2.cvtColor(ref_rgb[y0:y1, x0:x1].copy(), cv2.COLOR_RGB2BGR)
    cv2.polylines(img, [np.round(cmax - [x0, y0]).astype(np.int32)], True, (0, 160, 255), 2)
    for c in cands:
        P = np.round(np.asarray(c["centerline_ref"]) - [x0, y0]).astype(np.int32)
        cv2.polylines(img, [P], False, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.circle(img, tuple(P[0]), 4, (0, 0, 0), -1)
        cv2.circle(img, tuple(P[-1]), 3, (0, 200, 0), -1)
    cv2.imwrite(OUT + "/fig_bregion_candidates.png", img)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
