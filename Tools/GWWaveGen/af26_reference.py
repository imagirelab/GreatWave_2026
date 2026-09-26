# -*- coding: utf-8 -*-
"""番号26：参照モデル（Q5、wave_repair_zbrush2.obj）と K* の比較（記録のみ。合否には数えない）。

参照モデルは読むだけで、リポジトリにも成果物にも形状を入れない。ここで使うのは、SHA-256 を照合してから作った
Git 対象外の一時キャッシュ（頂点・面の npz。--cache で渡す）と、作業計画 9.4 の整列（解B）の 4×4 だけ。
出力は比較図（画像）と数値だけにする。

使い方（リポジトリ根で）:
    py -3.10 Tools/GWWaveGen/af26_reference.py --cache <refcache.npz> --align <align_B_upright.json> --out-dir <DIR> --tmp-dir <TMPDIR>
出力:
    DIR/26_ref_painting_overlay.png   原画視点の重ね図（原画 50%、真値の包絡輪郭、参照モデル（解B）と K* 3 案のシルエット）
    DIR/26_ref_sections.png           波峰線に直交する断面の比較（H で正規化、4 断面）
    DIR/26_ref_compare.json           比率の表、断面の位置、選んだ面の条件
    TMPDIR/ref_selected_world.npy     偏差の統計に使う参照モデルの頂点（Unity ワールド座標、一時ファイル）
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402

KEYS = ["a30", "a45", "a60"]
COLORS = {"a30": (230, 120, 20), "a45": (40, 120, 230), "a60": (40, 170, 70), "ref": (200, 30, 30), "truth": (0, 200, 220)}
FONT = r"C:\Windows\Fonts\YuGothM.ttc"
SEA_REF_WORLD_Y = 1.1982310754126466   # 解B でのモデル自身の海面（上向き面の世界 y の中央値、作業計画 9.4）


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def plane_segments(W, tris, p0, n):
    """三角形と平面 (x − p0)·n = 0 の交線分（k, 2, 3）。"""
    s = (W - p0) @ n
    st = s[tris]
    sg = np.sign(st)
    cross = ~((sg[:, 0] == sg[:, 1]) & (sg[:, 1] == sg[:, 2]))
    Tt = tris[cross]
    ss = st[cross]
    P = W[Tt]
    pts = []
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        si, sj = ss[:, i], ss[:, j]
        e = (si * sj) < 0
        t = np.where(e, si / np.where(e, si - sj, 1.0), 0.0)
        pts.append((P[:, i] + t[:, None] * (P[:, j] - P[:, i]), e))
    cnt = sum(e.astype(int) for _, e in pts)
    ok = cnt == 2
    seg = []
    for k in np.nonzero(ok)[0]:
        q = [p[0][k] for p in pts if p[1][k]]
        seg.append(q)
    return np.array(seg)


REF_SHA256 = "ab4124f9720d6e27d80e2ae063916292898c87606a64441043f6a64de3d53d40"


def build_cache(obj_path, tmp_dir):
    """参照モデルの OBJ の SHA-256 を照合してから、頂点・四角形（三角形は 4 点目を重ねる）を一時キャッシュ（npz）にする。
    一時キャッシュは Git 対象外の作業フォルダーに置き、番号26の終了時に消す。キャッシュの SHA-256 は記録する。"""
    import hashlib
    h = hashlib.sha256()
    with open(obj_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    sha = h.hexdigest()
    if sha != REF_SHA256:
        raise SystemExit("参照モデルの SHA-256 が一致しないので使わない: " + sha)
    V, F = [], []
    with open(obj_path, "r") as f:
        for line in f:
            if line.startswith("v "):
                V.append(line[2:].split()[:3])
            elif line.startswith("f "):
                idx = [int(t.split("/")[0]) for t in line[2:].split()]
                if len(idx) == 3:
                    idx.append(idx[2])
                F.append(idx[:4])
    V = np.array(V, np.float64)
    F = np.array(F, np.int64) - 1
    out = os.path.join(tmp_dir, "refcache.npz")
    np.savez(out, V=V, F=F)
    info = {"source": obj_path, "source_sha256": sha, "cache": out, "cache_sha256": T.sha256_file(out), "vertices": int(len(V)), "faces": int(len(F))}
    T.save_json(os.path.join(tmp_dir, "refcache_info.json"), info)
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default="G:/research/model/wave_repair_zbrush2.obj")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--align", required=True)
    ap.add_argument("--kstar-dir", default=os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar"))
    ap.add_argument("--render-dir", default=os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "render"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tmp-dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.tmp_dir, exist_ok=True)
    cache_info = None
    if a.cache is None:
        a.cache, cache_info = build_cache(a.obj, a.tmp_dir)
    d = np.load(a.cache)
    V, F = d["V"], d["F"]
    al = T.load_json(a.align)
    M = np.array(al["obj_to_unity_4x4"])
    s = float(al["params"]["scale"])
    W = (np.c_[V, np.ones(len(V))] @ M.T)[:, :3]
    tris = np.vstack([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])]
    rx = M[:3, 0] / s          # OBJ +x の世界方向（参照モデルの波の前は −x）
    rz = M[:3, 2] / s          # OBJ +z の世界方向（参照モデルの波峰線のおおよその向き）
    spec = T.load_spec()
    cam = G0.PaintingCam(spec)

    # ---- 参照モデルの頂（波峰線に沿った最高点）と、断面の位置
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
    H_ref = peak_y - SEA_REF_WORLD_Y
    metas = {k: T.load_json(os.path.join(a.kstar_dir, "kstar_%s_meta.json" % k)) for k in KEYS}
    rows = {k: np.load(os.path.join(a.kstar_dir, "kstar_%s_rows.npz" % k)) for k in KEYS}
    offsets = [0.0, -0.3, -0.6, 0.15]      # H を単位とした波峰線方向のずれ（負が手前の肩）
    panels = []
    for off in offsets:
        p0 = W.mean(0) + (z_peak + off * H_ref) * rz
        seg = plane_segments(W, tris, p0, rz)
        segs_ref = None
        if len(seg):
            aa = -((seg - p0) @ rx)            # 唇の向きを + にする
            yy = seg[..., 1] - SEA_REF_WORLD_Y
            top = np.unravel_index(np.argmax(yy), yy.shape)
            segs_ref = np.stack([(aa - aa[top]) / H_ref, yy / H_ref], -1)
        ks = {}
        for k in KEYS:
            c = rows[k]["c"]
            A, Y = rows[k]["A"], rows[k]["Y"]
            H0 = float(Y[metas[k]["rows"]["main_row"]].max())
            v = int(np.argmin(np.abs(c - off * H0)))
            jt = int(np.argmax(Y[v]))
            ks[k] = {"row": v, "c_m": float(c[v]), "poly": np.stack([(A[v] - A[v, jt]) / H0, Y[v] / H0], -1)}
        panels.append({"offset_H": off, "ref": segs_ref, "kstar": ks})

    # ---- 断面の図（1920×1080、2×2）
    img = Image.new("RGB", (1920, 1080), (250, 248, 242))
    dr = ImageDraw.Draw(img)
    f_s, f_m = font(20), font(26)
    xr, yr = (-1.1, 0.9), (-0.08, 1.12)
    for pi, pn in enumerate(panels):
        ox, oy = 60 + (pi % 2) * 930, 70 + (pi // 2) * 500
        w, h = 870, 440
        def tp(x, y):
            return (ox + (x - xr[0]) / (xr[1] - xr[0]) * w, oy + h - (y - yr[0]) / (yr[1] - yr[0]) * h)
        dr.rectangle([ox, oy, ox + w, oy + h], outline=(160, 160, 160))
        for gx in np.arange(-1.0, 0.91, 0.25):
            dr.line([tp(gx, yr[0]), tp(gx, yr[1])], fill=(225, 225, 225))
        for gy in np.arange(0.0, 1.11, 0.25):
            dr.line([tp(xr[0], gy), tp(xr[1], gy)], fill=(225, 225, 225))
            dr.text(tp(xr[0], gy), "%.2f" % gy, font=f_s, fill=(120, 120, 120))
        dr.line([tp(xr[0], 0), tp(xr[1], 0)], fill=(90, 110, 150), width=2)
        if pn["ref"] is not None:
            for sg in pn["ref"]:
                if np.all((sg[:, 0] > xr[0]) & (sg[:, 0] < xr[1]) & (sg[:, 1] > yr[0]) & (sg[:, 1] < yr[1])):
                    dr.line([tp(*sg[0]), tp(*sg[1])], fill=COLORS["ref"], width=2)
        for k in KEYS:
            P = pn["kstar"][k]["poly"]
            P = P[(P[:, 0] > xr[0]) & (P[:, 0] < xr[1])]
            dr.line([tp(*q) for q in P], fill=COLORS[k], width=3)
        title = "波頂からの距離 %+.2fH（K*: " % pn["offset_H"] + ", ".join("%s c=%.1f m" % (k, pn["kstar"][k]["c_m"]) for k in KEYS) + "）"
        dr.text((ox + 6, oy - 30), title, font=f_s, fill=(30, 30, 30))
    dr.text((60, 12), "番号26 断面の比較（波峰線に直交、H で正規化、記録のみ）  赤：参照モデル（Q5、解B で置いた世界座標、波峰線は OBJ z）  橙：K* 30°  青：K* 45°  緑：K* 60°  横は頂から唇の向きへ",
            font=f_s, fill=(20, 20, 20))
    img.save(os.path.join(a.out_dir, "26_ref_sections.png"))

    # ---- 原画視点の重ね図
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
    draw_iso(1.0 - sky, COLORS["truth"], 2)
    draw_iso(ref_cov, COLORS["ref"], 2)
    for k in KEYS:
        idp = os.path.join(a.render_dir, k, "26_%s_painting_ids.png" % k)
        ids = T.imread_rgb(idp)
        skyk = np.all(ids == np.array([0, 0, 255], np.uint8), axis=-1).astype(np.float32).reshape(1080, 2, 1920, 2).mean((1, 3))
        draw_iso(1.0 - skyk, COLORS[k], 1)
    out[:, :157] //= 3
    out[:, 1763:] //= 3
    pim = Image.fromarray(out)
    dr = ImageDraw.Draw(pim)
    dr.text((170, 1012), "番号26 原画視点（PaintingCam v1）：原画 50%、水色＝真値の包絡輪郭、赤＝参照モデル（Q5、解B）、橙／青／緑＝K* 30°／45°／60°（Unity の ID 画像）。記録のみ", font=f_s, fill=(255, 255, 255))
    dr.text((170, 1040), "K* の輪郭は真値から 1〜3 px 内側にあり、この縮尺では水色の線に重なって見えにくい（下端の緑などは前景の旧うねり・海面との境）", font=f_s, fill=(255, 255, 255))
    pim.save(os.path.join(a.out_dir, "26_ref_painting_overlay.png"))

    # ---- 偏差の統計に使う頂点：モデル自身の海面より 0.25H 以上高い所（海の塊・船の浮彫・前景の小波をおおむね除く。爪は除けていない）
    y_min = SEA_REF_WORLD_Y + 0.25 * H_ref
    sel = W[:, 1] >= y_min
    Wsel = W[sel]
    rng = np.random.default_rng(26)
    if len(Wsel) > 200000:
        Wsel = Wsel[rng.choice(len(Wsel), 200000, replace=False)]
    np.save(os.path.join(a.tmp_dir, "ref_selected_world.npy"), Wsel.astype(np.float32))

    # ---- 比率の表（参照モデルの中央部は作業計画 9.3 の値、K* は gw_wavegen_v1 の主断面）
    table = {}
    for k in KEYS:
        r = metas[k]["reference_ratios_self_check_record_only"]["main_row"]
        cl = metas[k]["crest_line"]
        table[k] = {"H_m": r["H_m"], "wall_over_H": r["wall_over_H"], "overhang_over_H": r["overhang_over_H"],
                    "lip_vertical_thickness_0p75m_behind_tip_m": r["lip_vertical_thickness_0p75m_behind_tip_m"],
                    "lip_thickness_min_over_lip_rows_m": metas[k]["reference_ratios_self_check_record_only"]["lip_vertical_thickness_min_over_lip_rows_m"],
                    "crest_above_half_peak_length_over_H": cl["above_half_peak_length_over_H"]}
    comp = {
        "note_ja": "記録のみ。合否は 68〜72・78・130〜132 などの項目だけで決める。参照モデルは読むだけで、形状は成果物に入れていない。",
        "reference": {"align": "解B（作業計画 9.4）", "scale_m_per_unit": s, "peak_world_y_m": float(peak_y), "sea_world_y_m": SEA_REF_WORLD_Y,
                      "H_ref_m": float(H_ref), "crest_dir_world_obj_z": rz.tolist(), "front_dir_world_obj_minus_x": (-rx).tolist(),
                      "central_ranges_plan_9_3": {"wall_over_H": [0.21, 0.31], "overhang_over_H": [0.37, 0.61], "lip_vertical_thickness_over_H": [0.02, 0.08],
                                                   "crest_above_half_peak_length_over_H": 1.2},
                      "deviation_vertex_selection_ja": "モデル自身の海面（世界 y %.2f m）より 0.25H（%.2f m）以上高い頂点（%d 点から最大 20 万点を無作為に抽出）。海の塊・船の浮彫・前景の小波はおおむね除かれるが、爪（唇の縁の指状の突起と波頂の背面のとげ）は除けていない" % (SEA_REF_WORLD_Y, y_min, int(sel.sum()))},
        "kstar_main_row_ratios": table,
        "section_offsets_H": offsets,
        "temp_cache": cache_info,
        "section_rows": {k: [p["kstar"][k]["row"] for p in panels] for k in KEYS},
    }
    T.save_json(os.path.join(a.out_dir, "26_ref_compare.json"), comp)
    print("REF_DONE", H_ref, peak_y, int(sel.sum()))


if __name__ == "__main__":
    main()
