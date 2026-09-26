# -*- coding: utf-8 -*-
"""番号26修正01：参照モデル（Q5、wave_repair_zbrush2.obj）と K* の比較の numpy 側（記録のみ。合否には数えない）。

番号26 の af26_reference.py（変更しない）の関数（SHA-256 を照合してから作る一時キャッシュ、平面と三角形の交線）を読み込んで使う。
参照モデルは読むだけで、リポジトリにも成果物にも形状を入れない。一時キャッシュは Git 対象外の作業フォルダーに置き、番号の終了時に消す。

使い方（リポジトリ根で）:
    py -3.10 Tools/GWWaveGen/af26r01_reference.py --align Docs/Evidence/ArtFirst/26/reference/align_B_upright.json --tmp-dir <TMP>
出力（Unity/Build/ArtFirst/26修正01/ref/）:
    26R01_ref_sections.png    波峰線に直交する 6 断面（H で正規化）：参照モデル（赤）、CP1 の K* 45°（灰）、26修正01 の K*（青）
    26R01_ref_painting.png    原画視点の重ね図（原画 50%、真値の包絡輪郭、参照モデル、26修正01 の K* の ID 輪郭）
    26R01_ref_compare.json    断面の位置、比率、一時キャッシュの SHA-256
    TMP/ref_selected_world.npy 偏差の統計に使う参照モデルの頂点（一時ファイル）
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402
import af26_reference as R26  # noqa: E402  番号26 の比較（変更しない）

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01")
K_NEW = os.path.join(BUILD, "kstar")
K_OLD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar")
COL = {"ref": (200, 30, 30), "cp1": (150, 150, 150), "r01": (30, 90, 220), "truth": (0, 200, 220)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default="G:/research/model/wave_repair_zbrush2.obj")
    ap.add_argument("--align", required=True)
    ap.add_argument("--tmp-dir", required=True)
    ap.add_argument("--out-dir", default=os.path.join(BUILD, "ref"))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.tmp_dir, exist_ok=True)
    cache, cache_info = R26.build_cache(a.obj, a.tmp_dir)   # SHA-256 を照合してから一時キャッシュを作る（違えば止まる）
    d = np.load(cache)
    V, F = d["V"], d["F"]
    al = T.load_json(a.align)
    M = np.array(al["obj_to_unity_4x4"])
    sc = float(al["params"]["scale"])
    W = (np.c_[V, np.ones(len(V))] @ M.T)[:, :3]
    tris = np.vstack([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])]
    rx = M[:3, 0] / sc
    rz = M[:3, 2] / sc
    spec = T.load_spec()
    cam = G0.PaintingCam(spec)
    zc = (W - W.mean(0)) @ rz
    bins = np.round(zc / 0.5).astype(int)
    peak_bin, peak_y = None, -1e9
    for b in np.unique(bins):
        m = bins == b
        if m.sum() < 200:
            continue
        y = W[m, 1].max()
        if y > peak_y:
            peak_y, peak_bin = y, b
    z_peak = peak_bin * 0.5
    H_ref = peak_y - R26.SEA_REF_WORLD_Y
    ks = {"cp1": (T.load_json(os.path.join(K_OLD, "kstar_a45_meta.json")), np.load(os.path.join(K_OLD, "kstar_a45_rows.npz"))),
          "r01": (T.load_json(os.path.join(K_NEW, "kstar_a45_meta.json")), np.load(os.path.join(K_NEW, "kstar_a45_rows.npz")))}
    offsets = [-0.9, -0.6, -0.3, 0.0, 0.15, 0.3]
    panels = []
    for off in offsets:
        p0 = W.mean(0) + (z_peak + off * H_ref) * rz
        seg = R26.plane_segments(W, tris, p0, rz)
        segs_ref = None
        if len(seg):
            aa = -((seg - p0) @ rx)
            yy = seg[..., 1] - R26.SEA_REF_WORLD_Y
            top = np.unravel_index(np.argmax(yy), yy.shape)
            segs_ref = np.stack([(aa - aa[top]) / H_ref, yy / H_ref], -1)
        kk = {}
        for k, (mt, rw) in ks.items():
            c = rw["c"]
            A, Y = rw["A"], rw["Y"]
            H0 = float(Y[mt["rows"]["main_row"]].max())
            v = int(np.argmin(np.abs(c - off * H0)))
            if Y[v].max() < 0.3:
                kk[k] = {"row": v, "c_m": float(c[v]), "poly": None}
                continue
            jt = int(mt["profile"]["index"]["j_top"])
            kk[k] = {"row": v, "c_m": float(c[v]), "poly": np.stack([(A[v] - A[v, jt]) / H0, Y[v] / H0], -1)}
        panels.append({"offset_H": off, "ref": segs_ref, "kstar": kk})
    img = Image.new("RGB", (1920, 1080), (250, 248, 242))
    dr = ImageDraw.Draw(img)
    f_s = R26.font(18)
    xr, yr = (-1.1, 0.9), (-0.08, 1.2)
    for pi, pn in enumerate(panels):
        ox, oy = 40 + (pi % 3) * 630, 80 + (pi // 3) * 500
        w, h = 590, 420

        def tp(x, y):
            return (ox + (x - xr[0]) / (xr[1] - xr[0]) * w, oy + h - (y - yr[0]) / (yr[1] - yr[0]) * h)
        dr.rectangle([ox, oy, ox + w, oy + h], outline=(160, 160, 160))
        for gy in np.arange(0.0, 1.11, 0.25):
            dr.line([tp(xr[0], gy), tp(xr[1], gy)], fill=(225, 225, 225))
            dr.text(tp(xr[0], gy), "%.2f" % gy, font=f_s, fill=(120, 120, 120))
        dr.line([tp(xr[0], 0), tp(xr[1], 0)], fill=(90, 110, 150), width=2)
        if pn["ref"] is not None:
            for sg in pn["ref"]:
                if np.all((sg[:, 0] > xr[0]) & (sg[:, 0] < xr[1]) & (sg[:, 1] > yr[0]) & (sg[:, 1] < yr[1])):
                    dr.line([tp(*sg[0]), tp(*sg[1])], fill=COL["ref"], width=2)
        for k in ("cp1", "r01"):
            P = pn["kstar"][k]["poly"]
            if P is None:
                continue
            P = P[(P[:, 0] > xr[0]) & (P[:, 0] < xr[1])]
            dr.line([tp(*q) for q in P], fill=COL[k], width=3 if k == "r01" else 2)
        dr.text((ox + 4, oy - 26), "波頂から %+.2fH（CP1 c=%.1f m、26修正01 c=%.1f m）" % (pn["offset_H"], pn["kstar"]["cp1"]["c_m"], pn["kstar"]["r01"]["c_m"]),
                font=f_s, fill=(30, 30, 30))
    dr.text((40, 14), "番号26修正01 断面の比較（波峰線に直交、H で正規化、記録のみ）  赤：参照モデル（Q5、解B で置いた世界座標、波峰線は OBJ z）  灰：CP1 の K* 45°（番号26）  青：26修正01 の K*",
            font=f_s, fill=(20, 20, 20))
    dr.text((40, 40), "横は頂から唇の向きへ。K* の行は波峰線方向の位置 c = ずれ×H（負が手前の肩）。参照モデルの形状は成果物に入れていない（断面の線を描いた図だけ）。", font=f_s, fill=(20, 20, 20))
    img.save(os.path.join(a.out_dir, "26R01_ref_sections.png"))

    # 原画視点の重ね図
    truth_disp = T.painting_display(spec, T.FrameMap(spec))[1]
    base = (truth_disp.astype(np.float32) * 0.5 + 255 * 0.25).astype(np.uint8)
    Pp = cam.project(W)
    ss = 2
    mask = np.zeros((1080 * ss, 1920 * ss), np.uint8)
    ok = Pp[:, 2] > 0.5
    ip = np.round(((Pp[:, :2] + 0.5) * ss - 0.5) * 16).astype(np.int32)
    tv = ok[tris].all(1)
    for tri in ip[tris[tv]]:
        cv2.fillConvexPoly(mask, tri, 255, lineType=cv2.LINE_8, shift=4)
    ref_cov = (mask > 0).astype(np.float32).reshape(1080, ss, 1920, ss).mean((1, 3))
    out = base.copy()

    def draw_iso(cov, col, th=2):
        m = (cov > 0.5).astype(np.uint8)
        cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(out, cs, -1, col, th, cv2.LINE_AA)
    reg = T.load_json(os.path.join(T.TARGET_DIR, "regions.json"))
    sky = T.load_cov_png(os.path.join(T.TARGET_DIR, reg["masks"]["sky_envelope"]))
    draw_iso(1.0 - sky, COL["truth"], 2)
    draw_iso(ref_cov, COL["ref"], 2)
    idp = os.path.join(BUILD, "render", "af26r01_painting_ids.png")
    if os.path.exists(idp):
        ids = T.imread_rgb(idp)
        skyk = np.all(ids == np.array([0, 0, 255], np.uint8), axis=-1).astype(np.float32).reshape(1080, 2, 1920, 2).mean((1, 3))
        draw_iso(1.0 - skyk, COL["r01"], 1)
    out[:, :157] //= 3
    out[:, 1763:] //= 3
    pim = Image.fromarray(out)
    dr = ImageDraw.Draw(pim)
    dr.text((170, 1012), "番号26修正01 原画視点（PaintingCam v1）：原画 50%、水色＝真値の包絡輪郭、赤＝参照モデル（Q5、解B）、青＝26修正01 の K*（Unity の ID 画像、船・前景を含む）。記録のみ",
            font=R26.font(20), fill=(255, 255, 255))
    pim.save(os.path.join(a.out_dir, "26R01_ref_painting.png"))

    y_min = R26.SEA_REF_WORLD_Y + 0.25 * H_ref
    sel = W[:, 1] >= y_min
    Wsel = W[sel]
    rng = np.random.default_rng(26)
    if len(Wsel) > 200000:
        Wsel = Wsel[rng.choice(len(Wsel), 200000, replace=False)]
    np.save(os.path.join(a.tmp_dir, "ref_selected_world.npy"), Wsel.astype(np.float32))
    comp = {"note_ja": "記録のみ。参照モデルは読むだけで、形状は成果物に入れていない。", "align": T.repo_rel(a.align), "H_ref_m": float(H_ref),
            "peak_world_y_m": float(peak_y), "section_offsets_H": offsets,
            "section_rows": {k: [p["kstar"][k]["row"] for p in panels] for k in ("cp1", "r01")},
            "section_c_m": {k: [p["kstar"][k]["c_m"] for p in panels] for k in ("cp1", "r01")},
            "deviation_vertex_selection_ja": "モデル自身の海面（世界 y %.2f m）より 0.25H（%.2f m）以上高い頂点から最大 20 万点（番号26 と同じ）" % (R26.SEA_REF_WORLD_Y, y_min),
            "temp_cache": cache_info}
    T.save_json(os.path.join(a.out_dir, "26R01_ref_compare.json"), comp)
    print("REF_DONE", H_ref, int(sel.sum()))


if __name__ == "__main__":
    main()
