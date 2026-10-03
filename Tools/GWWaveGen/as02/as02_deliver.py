# -*- coding: utf-8 -*-
"""美術の見本02（Q30）を利用者へ渡す：リポジトリへ入れてよい図（1920×1080）を作り、Docs/Evidence/ArtSample02/ へ写す。

  as02_1_painting_view.png   原画視点（修正の回 1 の s2_painting.png。原画に、利用者のマスクの縁を我々が線で描いたもの。マスクの画像そのものは入れない）
  as02_2_claws_closeup.png   新しく作る：爪 8 本の近く（原画＋縁の線｜Unity の原画視点＋縁の線｜置いた 3D の爪を原画カメラから＋縁の線｜作り直した爪 3/4｜置いた爪 3/4）
                             選び方は決まり：マスクの面積の大きい順に 6 本＋C3（重なり 0.85）に届かない 2 本。利用者のマスクの塗りと claw_mid の描画は入れない
  as02_3_back_clay.png       背の粘土（s3b）
  as02_4_back_chart.png      背は一つの山か（s3d と同じ図を描き直す。図の中の「見本02（水色）」を、線の本当の色の「緑の点線」に直した）
  as02_5_views.png           座席・側面・真上（s4a）
  as02_6_turntable.png       回り台 12 方位（s4b）
利用者のマスク（G:/research/爪形分析、読み取りのみ。D14・D23）は縁の線を描くためだけに読み、画像・マスクはリポジトリへ写さない。
原画は Docs/References/Met_JP1847_DP130155.jpg（メトロポリタン美術館の公開の画像）。彫刻の写真・参照モデルは使わない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_deliver.py
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_asm_sheets as SH  # noqa: E402
import as02_claws100 as A  # noqa: E402
import as02_gallery as G  # noqa: E402

S2 = REPO + "/Unity/Build/Polish/sample02"
FIX = S2 + "/fix01"
DELIV_FIX = FIX + "/delivery"
NOW = FIX + "/assemble/render/AS02C_A"
MESH = FIX + "/assemble/claws/mesh"
OUT_B = S2 + "/deliver"                      # Git 対象外の写し
OUT_E = REPO + "/Docs/Evidence/ArtSample02"   # リポジトリへ入れる図
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
S_DISP = 0.4163454124903624                  # as02_sheets.painting_disp と同じ（原画の画素 → 表示の画素）
OX_DISP = 156.66152659984573
GREEN = (0, 170, 0)
NOTE = "t* = 12 s の静止。Unity の PC 描画（HMD 実機ではない）と numpy の下見の描画。緑の線は、利用者が爪形分析で切り出した爪のマスクの縁を、我々が線で描いたもの。"

COPIES = [
    ("as02_1_painting_view.png", DELIV_FIX + "/s2_painting.png"),
    ("as02_3_back_clay.png", DELIV_FIX + "/s3b_back_clay_back65_behind.png"),
    ("as02_5_views.png", DELIV_FIX + "/s4a_views.png"),
    ("as02_6_turntable.png", DELIV_FIX + "/s4b_turntable.png"),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def disp_to_ref(xy):
    xy = np.asarray(xy, np.float64)
    o = np.array([S_DISP * 0.5 - 0.5 + OX_DISP, S_DISP * 0.5 - 0.5])
    return (xy - o) / S_DISP


def window(pts, aspect, pad=0.28, min_h=26.0):
    """表示の画素の枠（x0, y0, w, h）。点の外接に余白を足し、幅:高さ = aspect にそろえる。"""
    lo, hi = pts.min(0), pts.max(0)
    c = 0.5 * (lo + hi)
    w, h = (hi - lo) * (1 + 2 * pad)
    h = max(h, w / aspect, min_h)
    w = h * aspect
    return c[0] - w / 2, c[1] - h / 2, w, h


def crop_scaled(img, win, out_w, out_h, src_scale=1.0):
    """img（src_scale 倍の表示の画素）から窓 win を out_w×out_h へ（双三次）。"""
    x0, y0, w, h = win
    sx = out_w / (w * src_scale)
    sy = out_h / (h * src_scale)
    Mx = np.array([[sx, 0, -x0 * src_scale * sx + 0.5 * sx - 0.5], [0, sy, -y0 * src_scale * sy + 0.5 * sy - 0.5]], np.float64)
    return cv2.warpAffine(img, Mx, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def to_tile(pts, win, out_w, out_h):
    x0, y0, w, h = win
    return np.stack([(pts[:, 0] - x0) * out_w / w, (pts[:, 1] - y0) * out_h / h], -1)


def draw_outline(img, pts_tile, th=2):
    p = np.round(pts_tile * 8).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [p], True, GREEN, th, cv2.LINE_AA, shift=3)
    return img


def render_screen(V, F, col, q, z, cam_pos, win, out_w, out_h, light=(-0.6, 0.6, -0.5)):
    """原画カメラの画面の座標 q（表示の画素）のまま、窓 win を out_w×out_h へ描く（z バッファ、頂点の法線の陰、輪郭の藍の線）。"""
    x0, y0, w, h = win
    x = (q[:, 0] - x0) * out_w / w
    y = (q[:, 1] - y0) * out_h / h
    vn = G.vnormals(V, F)
    vd = V - cam_pos
    vd /= np.linalg.norm(vd, axis=1, keepdims=True)
    vns = np.where((np.sum(vn * vd, 1) > 0)[:, None], -vn, vn)
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    lam = 0.66 + 0.40 * np.clip(vns @ (-L), 0, 1) + 0.06 * np.clip(-np.sum(vns * vd, 1), 0, 1)
    vc = np.clip(col * lam[:, None], 0, 255)
    img = np.full((out_h, out_w, 3), 255.0)
    zb = np.full((out_h, out_w), np.inf)
    sil = np.zeros((out_h, out_w), bool)
    for tri in F:
        xs, ys = x[tri], y[tri]
        a0, a1 = int(max(np.floor(xs.min()), 0)), int(min(np.ceil(xs.max()), out_w - 1))
        b0, b1 = int(max(np.floor(ys.min()), 0)), int(min(np.ceil(ys.max()), out_h - 1))
        if a1 < a0 or b1 < b0:
            continue
        gx, gy = np.meshgrid(np.arange(a0, a1 + 1), np.arange(b0, b1 + 1))
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-12:
            continue
        w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
        w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        zz = w0 * z[tri[0]] + w1 * z[tri[1]] + w2 * z[tri[2]]
        sub = zb[b0:b1 + 1, a0:a1 + 1]
        upd = m & (zz < sub)
        if not upd.any():
            continue
        cc = w0[..., None] * vc[tri[0]] + w1[..., None] * vc[tri[1]] + w2[..., None] * vc[tri[2]]
        sub[upd] = zz[upd]
        img[b0:b1 + 1, a0:a1 + 1][upd] = cc[upd]
        sil[b0:b1 + 1, a0:a1 + 1] |= upd
    out = img.astype(np.uint8)
    e = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((2, 2), np.uint8)) > 0
    out[e] = G.LINE
    return out


def ortho34(V, F, col, cam, ref_V, size_w, size_h):
    """原画の向きから 55° 回した 3/4 の正射影（as02_gallery と同じ向き）。"""
    ctr = 0.5 * (ref_V.min(0) + ref_V.max(0))
    vd = A.unit(ctr - cam.pos)
    up = A.unit(cam.u - (cam.u @ vd) * vd)
    side = np.cross(up, vd)
    R = math.radians(55.0)
    v34 = math.cos(R) * vd + math.sin(R) * side
    s34 = np.cross(up, v34)
    c = 0.5 * (V.min(0) + V.max(0))
    ext = max(np.ptp((V - c) @ s34), np.ptp((V - c) @ up), 1e-6)
    S = max(size_w, size_h)
    im = G.render(V, F, col, v34, up, S, c, 0.80 * min(size_w, size_h) / ext)
    y0, x0 = (S - size_h) // 2, (S - size_w) // 2
    return im[y0:y0 + size_h, x0:x0 + size_w]


def pick(rep):
    pl = [c for c in rep["claws"] if c.get("placed")]
    big = [c["user_id"] for c in sorted(pl, key=lambda c: -c["area_mask_px"])[:6]]
    low = [c["user_id"] for c in pl if c["iou_painting"] < 0.85 or c["iou_face"] < 0.85]
    return big + [u for u in low if u not in big]


def claws_sheet(path):
    rep = json.load(open(MESH + "/as02_claws_report.json", encoding="utf-8"))
    rmap = {c["user_id"]: c for c in rep["claws"]}
    E = {e["uid"]: e for e in np.load(MESH + "/as02_entries.npy", allow_pickle=True)}
    users, _, _ = A.load_user()
    um = {u["uid"]: u for u in users}
    cam = A.CC.painting_cam()
    paint = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)
    unity = cv2.imread(NOW + "/views/painting_t120_claws.png")
    sel = pick(rep)
    sh = SH.Sheet("爪の近く（8 本）：原画｜Unity の原画視点｜置いた 3D の爪（原画カメラから）｜作り直した爪 3/4｜置いた爪 3/4", NOTE)
    TW, TH, GAP = 178, 196, 6
    bx = [16, 976]
    heads = ["原画＋縁の線", "Unity 原画視点（今）", "3D の爪・原画の向き", "作り直した爪 3/4", "置いた爪 3/4"]
    for x in bx:
        for k, s in enumerate(heads):
            sh.text(x + k * (TW + GAP) + 2, 70, s, 14, bold=True)
    used = []
    for i, uid in enumerate(sel):
        col_i, row = i % 2, i // 2
        x = bx[col_i]
        y = 96 + row * (TH + 34)
        e, r, u = E[uid], rmap[uid], um[uid]
        V = e["V"].astype(np.float64)
        F = e["T"][e["kind"] != 2]
        colv = G.claw_colors(e["n"])
        m = A.imread_u(u["dir"] + "/fill_mask.png", cv2.IMREAD_GRAYSCALE) > 127
        C = A.mask_contour(m)                       # 切り抜きの画素
        Mx = A.disp_affine(u["A"])
        Cd = C @ Mx[:, :2].T + Mx[:, 2]             # 表示の画素
        q, z = cam.project(V)
        win = window(np.vstack([Cd, q]), TW / TH)
        # 1 原画（原画の画素の細かさで切り出す）
        ref_win = (*disp_to_ref([win[0], win[1]]), win[2] / S_DISP, win[3] / S_DISP)
        t1 = crop_scaled(paint, ref_win, TW, TH)
        draw_outline(t1, to_tile(Cd, win, TW, TH))
        # 2 Unity の原画視点（1920×1080 の描画を拡大）
        t2 = crop_scaled(unity, win, TW, TH)
        draw_outline(t2, to_tile(Cd, win, TW, TH))
        # 3 置いた 3D の爪を原画カメラの画面のまま（numpy）
        t3 = render_screen(V, F, colv, q, z, cam.pos, win, TW, TH)
        draw_outline(t3, to_tile(Cd, win, TW, TH))
        # 4 作り直した爪（置く前、Vcan）3/4　5 置いた爪 3/4
        Vc = e["Vcan"].astype(np.float64)
        t4 = ortho34(Vc, F, colv, cam, Vc, TW, TH)
        t5 = ortho34(V, F, colv, cam, Vc, TW, TH)
        lab = "%s　IoU 原画視点 %.2f・面 %.2f　長さ %.2f m　根元と面の法線 %.0f°" % (
            uid, r["iou_painting"], r["iou_face"], r["length_3d_m"], r["root_dir_vs_normal_deg"])
        low = r["iou_painting"] < 0.85 or r["iou_face"] < 0.85
        sh.text(x, y, lab + ("　C3 に届かない" if low else ""), 14, col=(170, 30, 30) if low else (40, 40, 40), bold=low)
        for k, t in enumerate([t1, t2, t3, t4, t5]):
            sh.im.paste(SH.to_pil(t), (x + k * (TW + GAP), y + 22))
        used.append(dict(uid=uid, window_disp_px=[round(float(v), 2) for v in win], iou_painting=r["iou_painting"], iou_face=r["iou_face"],
                         length_3d_m=r["length_3d_m"], root_dir_vs_normal_deg=r["root_dir_vs_normal_deg"]))
    s = rep["summary"]
    sh.text(16, 1022, "選び方：マスクの面積の大きい順に 6 本（%s）＋ C3（重なり 0.85）に届かない 2 本。83 本の全部は Git 対象外の一覧（Build/Polish/sample02/fix01/delivery/s1_claw_gallery_p1〜p7）。"
            % "・".join(sel[:6]), 14)
    sh.text(16, 1044, "1・2 の枠は同じ。2 は 1920×1080 の描画の拡大でぼける。3/4 は原画の向きから 55° 回した正射影。置き方は案 A（原画の射線の上で奥行きだけ動かす）なので、置いた爪は横から見ると薄く伸びる。原画視点の IoU p50 %.3f。"
            % s["iou_painting"]["p50"], 14)
    sh.save(path)
    return used


def main():
    os.makedirs(OUT_B, exist_ok=True)
    os.makedirs(OUT_E, exist_ok=True)
    used = claws_sheet(OUT_B + "/as02_2_claws_closeup.png")
    files = {}
    for name, src in COPIES:
        shutil.copyfile(src, OUT_B + "/" + name)
        files[name] = dict(source=os.path.relpath(src, REPO).replace("\\", "/"), source_sha256=sha(src))
    files["as02_2_claws_closeup.png"] = dict(source="Tools/GWWaveGen/as02/as02_deliver.py（新しく作った）", claws=used)
    meas = FIX + "/back/final/measure.json"
    subprocess.run([sys.executable, "-B", REPO + "/Tools/GWWaveGen/as02/as02_fix01_back_chart.py", meas, OUT_B + "/as02_4_back_chart.png"], check=True)
    files["as02_4_back_chart.png"] = dict(source="Tools/GWWaveGen/as02/as02_fix01_back_chart.py で描き直し（説明の色の名前だけ直した）",
                                          measure=os.path.relpath(meas, REPO).replace("\\", "/"), measure_sha256=sha(meas))
    for name in sorted(files):
        p = OUT_B + "/" + name
        im = cv2.imread(p)
        assert im.shape[:2] == (1080, 1920), (name, im.shape)
        shutil.copyfile(p, OUT_E + "/" + name)
        files[name]["sha256"] = sha(OUT_E + "/" + name)
        files[name]["size"] = [im.shape[1], im.shape[0]]
    json.dump(files, open(OUT_B + "/deliver_sheets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(files, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
