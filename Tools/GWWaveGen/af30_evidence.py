# -*- coding: utf-8 -*-
"""番号30「形成の動き K0→K*」の証拠：シェーダーの補間の照合、座席からの項目（80・106・107・108・111・117）、図、metrics.json、run.json。

使い方（リポジトリの根で。af30_formation.py・Unity の AF30Formation.BuildAndRender・Blender の af30_blender.py・af30_tstar_eval.py の後）:
    py -3.10 Tools/GWWaveGen/af30_evidence.py
入力（Git 対象外の Unity/Build/ArtFirst/30/）：keypose/、af30_continuity.json、af30_render_report.json、af30_build_report.json、
    gpu_capture/*.bin、stills/*.png、video/*.mp4、blender/af30_blender_qa.json、af30_tstar_remeasure.json
出力：Docs/Evidence/ArtFirst/30/（図 1920×1080、MP4、metrics.json、run.json）
"""
import datetime
import glob
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402
import af30_formation as M  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "30")
FFMPEG = os.environ.get("GW_FFMPEG", r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe")
FFPROBE = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe")
W, H = 1920, 1080


def sha(p):
    return M.sha256_file(p)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def put(img, items, size=22):
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for fp in [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size)
                break
            except OSError:
                pass
    font = font or ImageFont.load_default()
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    for x, y, t, c in items:
        dr.text((x + 1, y + 1), t, fill=(0, 0, 0), font=font)
        dr.text((x, y), t, fill=tuple(int(v) for v in c), font=font)
    return np.array(im)


def rd(path):
    return T.imread_rgb(path)


def save(path, rgb):
    T.imwrite(path, rgb)
    return path


# ---------------------------------------------------------------- グラフ（cv2 で描く）
def chart(img, box, xs, series, xr, yr, title, xlabel="t (s)", ylabel="", hlines=(), vlines=(12.0,), yfmt="%.2f", legend_bottom=False):
    """box = (x0, y0, w, h)。series = [(ys, rgb, 名前)]。"""
    x0, y0, w, h = box
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (250, 250, 250), -1)
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (120, 120, 120), 1)
    px = lambda x: int(x0 + 60 + (x - xr[0]) / (xr[1] - xr[0]) * (w - 80))
    py = lambda y: int(y0 + h - 40 - (y - yr[0]) / (yr[1] - yr[0]) * (h - 80))
    for k in range(6):
        yv = yr[0] + k * (yr[1] - yr[0]) / 5
        cv2.line(img, (px(xr[0]), py(yv)), (px(xr[1]), py(yv)), (225, 225, 225), 1)
        cv2.putText(img, yfmt % yv, (x0 + 4, py(yv) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 60), 1, cv2.LINE_AA)
    for xv in np.arange(math.ceil(xr[0]), xr[1] + 1e-9, 2.0):
        cv2.putText(img, "%g" % xv, (px(xv) - 6, y0 + h - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 60), 1, cv2.LINE_AA)
    for xv in vlines:
        cv2.line(img, (px(xv), y0 + 30), (px(xv), y0 + h - 40), (180, 180, 180), 1)
    for yv, col in hlines:
        cv2.line(img, (px(xr[0]), py(yv)), (px(xr[1]), py(yv)), col, 2)
    for ys, col, _ in series:
        pts = np.array([[px(x), py(np.clip(y, yr[0] - 0.05 * (yr[1] - yr[0]), yr[1] + 0.05 * (yr[1] - yr[0])))] for x, y in zip(xs, ys) if np.isfinite(y)], np.int32)
        if len(pts) > 1:
            cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
    items = [(x0 + 8, y0 + 4, title, (20, 20, 20))]
    for i, (_, col, name) in enumerate(series):
        items.append((x0 + 70, (y0 + h - 70 - 22 * (len(series) - 1 - i)) if legend_bottom else (y0 + 30 + 22 * i), "— " + name, col))
    items.append((x0 + w // 2 - 20, y0 + h - 20, xlabel, (60, 60, 60)))
    return items


def draw_items(img, items, size=18):
    return put(img, [(x, y, t, c) for x, y, t, c in items], size)


# ---------------------------------------------------------------- 本体
def main():
    t0 = time.time()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    os.makedirs(EVID, exist_ok=True)
    rig_path = os.path.join(HERE, "af30_rig.json")
    F = M.Formation(rig_path, BUILD, log=lambda *a: None)
    R, ks = F.R, F.ks
    kp = T.load_json(os.path.join(BUILD, "keypose", "af30_keypose.json"))
    cont = T.load_json(os.path.join(BUILD, "af30_continuity.json"))
    rrep = T.load_json(os.path.join(BUILD, "af30_render_report.json"))
    brep = T.load_json(os.path.join(BUILD, "af30_build_report.json"))
    bqa = T.load_json(os.path.join(BUILD, "blender", "af30_blender_qa.json"))
    tst = T.load_json(os.path.join(BUILD, "af30_tstar_remeasure.json"))
    spec = T.load_spec()
    cam = G0.PaintingCam(spec)
    seat = F.seat
    eye = np.array(seat["seat"]["eye_world"], np.float64)

    # ---- keypose（量子化した値）を読み戻す
    nk, nv, nu = kp["layers"], kp["nv"], kp["nu"]
    q = np.fromfile(os.path.join(BUILD, "keypose", kp["position_file"]), "<u2").reshape(nk, nv, nu, 4)
    if sha(os.path.join(BUILD, "keypose", kp["position_file"])) != kp["position_sha256"]:
        raise SystemExit("keypose の位置のファイルが記録と違います")
    lo, size = np.array(kp["bbox_min"]), np.array(kp["bbox_size"])
    keys = lo + q[..., :3].astype(np.float64) / 65535.0 * size
    F.key_times = np.array(kp["key_times_s"])
    F.deq_keys = keys
    del q

    # ---- CPU の Catmull-Rom（量子化した key）と numpy の密なフレーム（120 Hz、0〜12 s）
    hz = 120.0
    ts_d = np.arange(0, int(round(12.0 * hz)) + 1) / hz
    cr_err = np.zeros(len(ts_d))
    cr_at = None
    for i, t in enumerate(ts_d):
        P = F.cr_eval(t)
        d = np.linalg.norm(P - F.X(t), axis=-1)
        cr_err[i] = d.max()
        if cr_at is None or cr_err[i] > cr_err[cr_at[0]]:
            cr_at = (i, [int(v) for v in np.unravel_index(d.argmax(), d.shape)])
    Pst = F.cr_eval(12.0)
    tstar_q_err = float(np.linalg.norm(Pst - ks.X, axis=-1).max())

    # ---- GPU（頂点シェーダーと同じ関数）の読み戻し
    gpu = []
    px_tstar = None
    for c in rrep["captures"]:
        t = float(c["t"])
        g = np.fromfile(c["path"], "<f4").reshape(nv, nu, 3).astype(np.float64)
        dense = F.X(t)
        cpu = F.cr_eval(t)
        e_dense = float(np.linalg.norm(g - dense, axis=-1).max())
        e_cpu = float(np.linalg.norm(g - cpu, axis=-1).max())
        rec = {"t": round(t, 4), "gpu_vs_numpy_dense_max_m": e_dense, "gpu_vs_cpu_catmullrom_max_m": e_cpu,
               "slices": c["slices"], "weights": [round(w, 6) for w in c["weights"]]}
        if abs(t - 12.0) < 1e-6:
            pg = cam.project(g.reshape(-1, 3))
            pk = cam.project(ks.X.reshape(-1, 3))
            vis = (pk[:, 2] > 0.5) & (pk[:, 0] > -50) & (pk[:, 0] < W + 50) & (pk[:, 1] > -50) & (pk[:, 1] < H + 50)
            px_tstar = float(np.linalg.norm(pg[vis, :2] - pk[vis, :2], axis=1).max())
            rec["tstar_px_vs_kstar_max"] = px_tstar
            rec["tstar_gpu_vs_kstar_max_m"] = float(np.linalg.norm(g - ks.X, axis=-1).max())
        gpu.append(rec)
    gpu_dense_max = max(r["gpu_vs_numpy_dense_max_m"] for r in gpu)
    gpu_cpu_max = max(r["gpu_vs_cpu_catmullrom_max_m"] for r in gpu)

    # ---- 再生される面（16 ビットに量子化した key の Catmull-Rom）の向きと、着色の法線（RG16 の八面体、頂点シェーダーと同じ式）。
    #      連続性の検査一式と Blender の検査は float64 の rig で測るので、ここで再生される側を記録する（下の座席の項目と同じ 30 Hz・0〜17 s）。
    def face_normals(X_):
        V_ = X_.reshape(-1, 3)
        return np.cross(V_[ks.tris[:, 1]] - V_[ks.tris[:, 0]], V_[ks.tris[:, 2]] - V_[ks.tris[:, 0]])

    def reversed_faces(fa_, fb_):
        ok_ = (np.linalg.norm(fa_, axis=1) > 1e-10) & (np.linalg.norm(fb_, axis=1) > 1e-10)
        return ok_ & ((fa_ * fb_).sum(1) < 0)

    npath = os.path.join(BUILD, "keypose", kp["normal_file"])
    if sha(npath) != kp["normal_sha256"]:
        raise SystemExit("keypose の法線のファイルが記録と違います")
    qn_all = np.fromfile(npath, "<u2").reshape(nk, nv, nu, 2)
    nrm_cache = {}

    def key_nrm(i_):
        if i_ not in nrm_cache:
            if len(nrm_cache) >= 8:
                nrm_cache.pop(next(iter(nrm_cache)))
            nrm_cache[i_] = M.octa_decode(qn_all[i_].astype(np.float64) / 65535.0 * 2.0 - 1.0)
        return nrm_cache[i_]

    def played_nrm(t_):
        idx_, w_ = M.cr_weights(F.key_times, t_)
        n_ = sum(w_[q_] * key_nrm(idx_[q_]) for q_ in range(4))
        return n_ / np.maximum(np.linalg.norm(n_, axis=-1, keepdims=True), 1e-20)

    fnK = face_normals(ks.X)
    VK = ks.X.reshape(-1, 3)
    eK_ = np.stack([np.linalg.norm(VK[ks.tris[:, 1]] - VK[ks.tris[:, 0]], axis=1), np.linalg.norm(VK[ks.tris[:, 2]] - VK[ks.tris[:, 1]], axis=1),
                    np.linalg.norm(VK[ks.tris[:, 0]] - VK[ks.tris[:, 2]], axis=1)], 1)
    hK = np.linalg.norm(fnK, axis=1) / np.maximum(eK_.max(1), 1e-20)   # 三角形の高さ（最長の辺に対する）
    thin = hK < 1.5e-3
    tri_row = ks.tris[:, 0] // nu
    rev_tstar = reversed_faces(face_normals(Pst), fnK)
    rev_rows, rev_cnt = np.unique(tri_row[rev_tstar], return_counts=True)
    pl = {"rev_vs_rig_face_frames": 0, "rev_vs_rig_max_per_frame": 0, "rev_vs_rig_frames": 0, "rev_vs_rig_formation_face_frames": 0,
          "flip_prev_face_frames": 0, "shading_dot_min": 1.0, "shading_dot_min_t": None}
    fnP_prev = None
    nsh_prev = None

    # ---- 座席からの項目（30 Hz、0〜17 s）
    hz2 = 30.0
    ts = np.arange(0, int(round(17.0 * hz2)) + 1) / hz2
    c_seat = float((eye - ks.O) @ ks.e)
    near_rows = np.nonzero(np.abs(ks.c - c_seat) <= 3.0)[0]
    lip_rows = np.nonzero(R.parab["valid"])[0]
    face_rows = np.nonzero(np.abs(ks.c - c_seat) <= 5.0)[0]
    centre_rows = face_rows
    left_rows = np.nonzero((ks.c < c_seat - 5.0) & (ks.c >= c_seat - 25.0))[0]
    right_rows = np.nonzero((ks.c > c_seat + 5.0) & (ks.c <= c_seat + 15.0))[0]
    # 座席の形成の向き（唇の方位）と、画面の中央・左・右の方位の帯
    fw = np.array(seat["view"]["target_world"]) - eye
    yaw0 = math.atan2(fw[0], fw[2])
    series = {k: [] for k in ("lip_elev_max", "lip_hdist_min", "near_tip_elev", "centre_elev_max", "left_elev_max", "right_elev_max",
                              "face_normal_up_deg", "face_normal_to_seat", "tip_dir_deg", "zenith70", "lip_within5m")}
    prev_face_n = None
    face_turn_max = 0.0
    tip_prev = None
    tip_jump_max = 0.0
    for t in ts:
        X, A, Y, _ = R.frame(t)
        d = X - eye
        hd = np.hypot(d[..., 0], d[..., 2])
        el = np.degrees(np.arctan2(d[..., 1], hd))
        az = np.degrees(np.arctan2(d[..., 0], d[..., 2])) - math.degrees(yaw0)
        az = (az + 180) % 360 - 180
        above = Y > 0.3
        lipm = np.zeros_like(Y, bool)
        lipm[np.ix_(lip_rows, np.arange(R.jT, R.jK + 1))] = True
        lm = lipm & above
        series["lip_elev_max"].append(float(el[lm].max()) if lm.any() else float("nan"))
        high = lm & (d[..., 1] > 3.0)
        series["lip_hdist_min"].append(float(hd[high].min()) if high.any() else float("nan"))
        series["lip_within5m"].append(int((high & (hd <= 5.0)).sum()))
        series["zenith70"].append(int((above & (el >= 70.0)).sum()))
        series["near_tip_elev"].append(float(el[near_rows, R.jP].max()))
        # 中央・左・右は行の組で決める（方位の帯で決めると、高い点が帯の境を横切るときに最大値が跳ぶため）。
        # 座席は唇の方位（左前）を向くので、手前の肩の行（c が小さい）が左、奥の行が右に見える。
        for key, rows_ in (("centre_elev_max", centre_rows), ("left_elev_max", left_rows), ("right_elev_max", right_rows)):
            m_ = above[rows_]
            series[key].append(float(el[rows_][m_].max()) if m_.any() else float("nan"))
        # 再生される面（量子化した key の Catmull-Rom）：同じ時刻の rig と向きが逆の面、前のフレームからの反転、着色の法線の連続
        fnP = face_normals(F.cr_eval(t))
        fnR = face_normals(X)
        rvm = reversed_faces(fnP, fnR)
        rv = int(rvm.sum())
        pl["rev_vs_rig_face_frames"] += rv
        if rv > pl["rev_vs_rig_max_per_frame"]:
            pl["rev_vs_rig_max_per_frame"], pl["rev_vs_rig_max_at_s"] = rv, round(float(t), 4)
        pl["rev_vs_rig_frames"] += int(rv > 0)
        if rv:
            V_ = X.reshape(-1, 3)
            tr_ = ks.tris[rvm]
            le_ = np.maximum.reduce([np.linalg.norm(V_[tr_[:, 1]] - V_[tr_[:, 0]], axis=1), np.linalg.norm(V_[tr_[:, 2]] - V_[tr_[:, 1]], axis=1),
                                     np.linalg.norm(V_[tr_[:, 0]] - V_[tr_[:, 2]], axis=1)])
            pl["rev_rig_height_max_m"] = max(pl.get("rev_rig_height_max_m", 0.0), float((np.linalg.norm(fnR[rvm], axis=1) / np.maximum(le_, 1e-20)).max()))
            pl.setdefault("rev_rows", set()).update(int(v) for v in np.unique(tri_row[rvm]))
        if t < 12.0 - 1e-9:
            pl["rev_vs_rig_formation_face_frames"] += rv
        if fnP_prev is not None:
            pl["flip_prev_face_frames"] += int(reversed_faces(fnP, fnP_prev).sum())
        fnP_prev = fnP
        nsh = played_nrm(t)
        if nsh_prev is not None:
            dm_ = float((nsh * nsh_prev).sum(-1).min())
            if dm_ < pl["shading_dot_min"]:
                pl["shading_dot_min"], pl["shading_dot_min_t"] = dm_, round(float(t), 4)
        nsh_prev = nsh
        # 107：船に面する水面（座席の近くの行の内壁の列）の法線
        n, _ = M.vertex_normals(X, ks.tris)
        n = n.reshape(nv, nu, 3)
        fn = n[np.ix_(face_rows, np.arange(R.jK, R.jF + 1))].reshape(-1, 3).mean(0)
        fn /= np.linalg.norm(fn)
        cen = X[np.ix_(face_rows, np.arange(R.jK, R.jF + 1))].reshape(-1, 3).mean(0)
        to_seat = eye - cen
        to_seat[1] = 0
        to_seat /= np.linalg.norm(to_seat)
        series["face_normal_up_deg"].append(float(np.degrees(np.arccos(np.clip(fn[1], -1, 1)))))
        series["face_normal_to_seat"].append(float(fn @ to_seat))
        if prev_face_n is not None:
            face_turn_max = max(face_turn_max, float(np.degrees(np.arccos(np.clip(fn @ prev_face_n, -1, 1)))))
        prev_face_n = fn
        # 111：座席の近くの行の唇先の向き（唇の上面の最後の 8 列の向き、水平からの角。負が下向き）
        v = np.stack([A[near_rows, R.jP] - A[near_rows, R.jP - 8], Y[near_rows, R.jP] - Y[near_rows, R.jP - 8]], -1)
        ang = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
        series["tip_dir_deg"].append(float(np.median(ang)))
        tp = X[near_rows, R.jP]
        if tip_prev is not None:
            tip_jump_max = max(tip_jump_max, float(np.linalg.norm(tp - tip_prev, axis=-1).max()))
        tip_prev = tp
    S = {k: np.array(v, np.float64) for k, v in series.items()}
    it0 = 0
    its = int(round(12.0 * hz2))
    lip_el = S["lip_elev_max"]
    lip_el_f = np.nan_to_num(lip_el, nan=-90.0)
    lip_drop = float(np.max(np.maximum(lip_el_f[:-1] - lip_el_f[1:], 0.0)))
    near_el = S["near_tip_elev"]
    tipdir = S["tip_dir_deg"]
    tipdir_step = float(np.max(np.abs(np.diff(tipdir))))
    cen = S["centre_elev_max"]
    cen_f = np.nan_to_num(cen, nan=-90.0)
    cen_drop = float(np.max(np.maximum(cen_f[:-1] - cen_f[1:], 0.0)))

    # ---- 図
    figs = {}
    def sheet(view, times, title, sub):
        out = np.full((H, W, 3), 30, np.uint8)
        tw, th = 640, 360
        items = []
        for i, t in enumerate(times):
            p = os.path.join(BUILD, "stills", "af30_%s_t%05.2f.png" % (view, t))
            im = cv2.resize(rd(p), (tw, th), interpolation=cv2.INTER_AREA)
            r_, c_ = divmod(i, 3)
            x, y = c_ * tw, r_ * th
            out[y:y + th, x:x + tw] = im
            items.append((x + 8, y + 6, "t = %.1f s" % t, (255, 255, 255)))
        items.append((8, H - 30, title + "　" + sub, (255, 240, 180)))
        return put(out, items, 20)
    tA = [2, 6, 8, 9, 10, 10.5, 11, 11.5, 12]
    figs["af30_painting_formation.png"] = sheet("painting", tA, "原画視点（PaintingCam v1）の形成（Unity、keypose の頂点補間、NPR は 28修正01 の焼き込み）",
                                                 "t* = 12.0 s が原画の姿。前景・右の仮置きは番号39・40 まで")
    figs["af30_seat_formation.png"] = sheet("seat_form", tA, "座席 v1（右船、唇の方位・仰角 30°、縦画角 80°）からの形成（場面全体）",
                                             "手前の白い三角・右の暗い斜面は仮置き（番号39・40）")
    figs["af30_seat_formation_waveonly.png"] = sheet("seat_form_waveonly", tA, "座席 v1 からの形成（主役波・空・海だけ。確認図）",
                                                      "船・富士・仮置きを描画の間だけ隠した")
    figs["af30_side_formation.png"] = sheet("side_left_waveonly", tA, "左の側面からの形成（Unity、主役波・空・海だけ。確認図）", "手前の肩から奥まで、波峰の全体がそろって立ち上がり巻いていく")
    figs["af30_back_formation.png"] = sheet("back", tA, "背面からの形成（Unity）", "足跡は船の側へ 4 m 動く（t* でずれ 0）")
    # 断面（numpy）
    sec = os.path.join(BUILD, "preview", "af30_sections_fig.png")
    M.preview_sections(F, sec)
    s_img = rd(sec)
    s_img[0:40] = 255
    rr_ = [ks.main_row, 146, 120, 100, 185, 200]
    s_img = put(s_img, [(10, 6, "断面の形成（numpy）。行 c：黒 %.1f（主断面）・青 %.1f・緑 %.1f・赤 %.1f（手前の肩）・紫 %.1f・黄 %.1f m（奥）。大きい赤い点は座席 v1、各行の小さい点は唇先"
                         % tuple(ks.c[r] for r in rr_), (0, 0, 0))], 20)
    figs["af30_sections.png"] = s_img

    # 座席の項目のグラフと唇先の軌跡
    img = np.full((H, W, 3), 255, np.uint8)
    items = []
    items += chart(img, (10, 10, 940, 340), ts, [(S["centre_elev_max"], (30, 30, 200), "中央：座席の近くの行 ±5 m の水面の最大仰角（80）"),
                                                 (S["left_elev_max"], (30, 150, 30), "左：手前の肩の行（座席 −25〜−5 m、106）"), (S["right_elev_max"], (150, 30, 150), "右：奥の行（座席 +5〜+15 m、106）"),
                                                 (S["lip_elev_max"], (200, 30, 30), "唇（巻きのある行）の最大仰角（108）。赤い横線 60°")],
                   (0, 17), (-10, 90), "座席 v1 から見た水面の仰角（度）", hlines=((60, (255, 150, 150)),), yfmt="%.0f")
    items += chart(img, (970, 10, 940, 340), ts, [(S["face_normal_up_deg"], (30, 30, 200), "内壁の法線と上向きの角（度、107）"),
                                                  (np.degrees(np.arccos(np.clip(S["face_normal_to_seat"], -1, 1))), (200, 30, 30), "内壁の法線と座席の方向の角（度）")],
                   (0, 17), (0, 180), "船に面する水面（座席の近くの行 ±5 m の内壁）の向き", yfmt="%.0f")
    items += chart(img, (10, 360, 940, 340), ts, [(tipdir, (200, 30, 30), "座席の近くの行の唇先の向き（度、負が下、111）")],
                   (0, 17), (-120, 60), "唇先の向き（唇の上面の最後の 8 列、断面内の水平からの角）", hlines=((0, (180, 180, 180)),), yfmt="%.0f")
    items += chart(img, (970, 360, 940, 340), ts, [(S["lip_hdist_min"], (200, 30, 30), "目より 3 m 高い唇の点までの水平距離の最小（m）")],
                   (0, 17), (0, 30), "唇と座席の水平距離（108 の真上の読み）", hlines=((5, (255, 150, 150)),), yfmt="%.0f")
    # 唇先の軌跡（主断面の行）
    x0, y0, w_, h_ = 10, 710, 1900, 360
    cv2.rectangle(img, (x0, y0), (x0 + w_, y0 + h_), (120, 120, 120), 1)
    tt = np.linspace(2, 12, 301)
    mr = ks.main_row
    tip = np.array([[R.frame_AY(t)[0][mr, R.jP], R.frame_AY(t)[1][mr, R.jP]] for t in tt])
    p = R.parab
    sa = float((eye - ks.O) @ ks.t)
    def PP(a, y):
        return (int(x0 + 700 + a * 45), int(y0 + h_ - 30 - y * 13))
    cv2.line(img, PP(-15, 0), PP(25, 0), (150, 150, 150), 1)
    aa = np.linspace(p["a_apex"][mr], ks.A[mr, R.jP], 50)
    par = p["y_apex"][mr] - p["G"][mr] * (aa - p["a_apex"][mr]) ** 2
    cv2.polylines(img, [np.array([PP(a, y) for a, y in zip(aa, par)], np.int32)], False, (255, 170, 170), 6, cv2.LINE_AA)
    cv2.polylines(img, [np.array([PP(a, y) for a, y in tip], np.int32)], False, (200, 30, 30), 2, cv2.LINE_AA)
    for tk in (4, 6, 8, 9, 10, 11, 12):
        a, y = R.frame_AY(tk)[0][mr, R.jP], R.frame_AY(tk)[1][mr, R.jP]
        cv2.circle(img, PP(a, y), 5, (0, 0, 0), -1)
        items.append((PP(a, y)[0] + 6, PP(a, y)[1] - 22, "%g s" % tk, (0, 0, 0)))
    Ks = np.stack([ks.A[mr], ks.Y[mr]], -1)
    cv2.polylines(img, [np.array([PP(a, y) for a, y in Ks], np.int32)], False, (120, 120, 200), 1, cv2.LINE_AA)
    cv2.circle(img, PP(sa, eye[1]), 7, (0, 0, 255), -1)
    items.append((x0 + 8, y0 + 4, "主断面の唇先の軌跡（赤）と重力の放物線 y = y_apex − G(a − a_apex)²（薄い赤、頂点 %.2f s、G %.3f /m）。青は K* の主断面、青い点は座席 v1" % (p["t_apex"][mr], p["G"][mr]), (20, 20, 20)))
    figs["af30_seat_metrics.png"] = draw_items(img, items, 18)

    # 連続性のグラフ
    pf = cont["per_frame"]
    tt2 = np.array([r_["t"] for r_ in pf])
    step = np.array([r_.get("step_max_m", np.nan) for r_ in pf])
    d2 = np.array([r_.get("second_diff_max_m", np.nan) for r_ in pf])
    nd = np.array([r_.get("normal_dot_min", np.nan) for r_ in pf])
    img = np.full((H, W, 3), 255, np.uint8)
    items = []
    lim = F.rig["continuity_limits"]
    items += chart(img, (10, 10, 940, 520), tt2, [(step, (30, 30, 200), "フレームごとの最大変位（m、30 Hz）")], (0, 17), (0, 0.7),
                   "位置の跳び：最大変位（上限 0.6 m）", hlines=((lim["max_step_m_30hz"], (255, 150, 150)),))
    items += chart(img, (970, 10, 940, 520), tt2, [(d2, (30, 30, 200), "二階差分の最大（m、30 Hz）")], (0, 17), (0, 0.025),
                   "二階差分（上限 0.0218 m ＝ 2 g）", hlines=((lim["max_second_difference_m_30hz"], (255, 150, 150)),), yfmt="%.3f")
    items += chart(img, (10, 545, 940, 520), tt2, [(nd, (30, 30, 200), "隣のフレームとの法線の内積の最小")], (0, 17), (0.9, 1.0),
                   "法線の連続（下限 0）", yfmt="%.3f", legend_bottom=True)
    items += chart(img, (970, 545, 940, 520), ts_d, [(cr_err * 100, (30, 30, 200), "CPU の Catmull-Rom（量子化した key）と密なフレームの差（cm、120 Hz）")] ,
                   (0, 17), (0, 2.5), "keypose の補間の差（上限 2 cm）", hlines=((2.0, (255, 150, 150)),))
    for r_ in gpu:
        cx = int(970 + 60 + r_["t"] / 17 * 860)
        cy = int(545 + 520 - 40 - r_["gpu_vs_numpy_dense_max_m"] * 100 / 2.5 * 440)
        cv2.circle(img, (cx, cy), 5, (200, 30, 30), -1)
    items.append((990, 545 + 56, "赤い点：GPU（頂点シェーダーと同じ関数）と密なフレームの差", (200, 30, 30)))
    figs["af30_continuity.png"] = draw_items(img, items, 18)

    # t* の比較（keypose の描画と 28修正01）
    a30 = rd(os.path.join(BUILD, "t28", "render", "af28r01_painting.png"))
    a28 = rd(os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "render", "af28r01_painting.png"))
    diff = np.abs(a30.astype(np.int16) - a28.astype(np.int16)).max(-1)
    ndiff = int((diff > 8).sum())
    img = np.full((H, W, 3), 30, np.uint8)
    img[0:540, 0:960] = cv2.resize(a30, (960, 540), interpolation=cv2.INTER_AREA)
    img[0:540, 960:1920] = cv2.resize(a28, (960, 540), interpolation=cv2.INTER_AREA)
    dimg = np.full((1080, 1920, 3), 255, np.uint8)
    dimg[diff > 8] = (220, 30, 30)
    img[540:1080, 0:960] = cv2.resize(dimg, (960, 540), interpolation=cv2.INTER_AREA)
    tb = [(980, 560, "t* の再測定（番号28修正01 と同じ評価の手順）", (255, 240, 180))]
    y = 600
    for r_ in tst["silhouettes_vs_26r01_28r01"]:
        if r_["item"] == "71":
            continue
        tb.append((980, y, "%s  30 %.2f px（p95 %.2f） 26修正01 %.2f（%.2f）" % (r_["item"], r_["af30_max_px"], r_["af30_p95_px"], r_["r26r01_max_px"], r_["r26r01_p95_px"]), (230, 230, 230)))
        y += 28
    for r_ in tst["boundaries_vs_28r01"]:
        if "record" in r_["measure"]:
            continue
        tb.append((980, y, "%s %s  30 %.2f px  28修正01 %.2f  差 %+.2f" % (r_["item"], r_["measure"].split("/")[-1], r_["af30_max_px"], r_["r28r01_max_px"], r_["diff_px"]), (230, 230, 230)))
        y += 28
    tb.append((980, y + 6, "差の最大 %.3f px（基準 ±0.5 px）" % tst["worst_abs_diff_px"], (255, 240, 180)))
    tb += [(8, 6, "t* = 12.0 s：keypose の頂点補間で描いた原画視点（番号30）", (255, 255, 255)), (968, 6, "番号28修正01（静止した K*、AF28 NPR v1）", (255, 255, 255)),
           (8, 546, "画素の差（RGB の差 >8）：%d px（1920×1080）" % ndiff, (0, 0, 0))]
    figs["af30_tstar.png"] = put(img, tb, 20)

    for name, im in figs.items():
        save(os.path.join(EVID, name), im)

    # ---- 動画（1920×1080・60 fps。5 MB 以下はそのまま証拠へ、それより大きいものは Build に残して 1280×720 の版を証拠へ）
    vids = {}
    for v in rrep["videos"]:
        src = v["path"]
        name = os.path.basename(src)
        info = subprocess.run([FFPROBE, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height,r_frame_rate,nb_read_frames,duration", "-of", "json", src], capture_output=True, text=True)
        st = json.loads(info.stdout)["streams"][0]
        size = os.path.getsize(src)
        if size <= 5 * 2 ** 20:
            dst = os.path.join(EVID, name)
            shutil.copy2(src, dst)
        else:
            dst = os.path.join(EVID, name.replace("_60fps.mp4", "_60fps_720p.mp4"))
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "medium", "-crf", "24",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst], check=True)
        vids[v["view"]] = {"build": rel(src), "build_sha256": v["sha256"], "bytes": size, "evidence": rel(dst), "evidence_sha256": sha(dst),
                           "evidence_bytes": os.path.getsize(dst), "width": st["width"], "height": st["height"], "fps": st["r_frame_rate"],
                           "frames_decoded": int(st["nb_read_frames"]), "duration_s": float(st["duration"])}

    # ---- 判定
    cl = cont["pass"]
    blender_frames = bqa["frames"]
    bl_all0 = all(fr_["nonmanifold_edges_gt2_faces"] == 0 and fr_["flipped_inconsistent_winding_edges"] == 0 and fr_["degenerate_faces_area_lt_1e-8"] == 0
                  and fr_["self_intersecting_face_pairs"] == 0 and fr_["boundary_edges"] == fr_["boundary_edges_expected_grid_perimeter"]
                  for fr_ in blender_frames.values())
    rays0 = all(fr_["rays"]["wave_back_open"] == 0 and fr_["rays"]["cut_end"] == 0 and fr_["rays"]["hole"] == 0 for fr_ in blender_frames.values())
    geom_ok = bool(cont["all_pass"] and bl_all0)
    interp_ok = bool(max(cr_err.max(), gpu_dense_max) <= 0.02)
    tstar_px_ok = bool(px_tstar is not None and px_tstar <= 1.0)
    items = {}
    common = {"shape_switch_missing_tear_jump_flip": {
        "index_constant": cont["index_sha256"] == rrep["indexSha256"] == kp["index_sha256"],
        "vertex_count": cont["vertex_count"], "step_max_m_30hz": round(cont["step_max_m"], 4), "step_limit_m": cont["step_limit_m"],
        "second_diff_max_m_30hz": round(cont["second_diff_max_m"], 5), "second_diff_limit_m": cont["second_diff_limit_m"],
        "normal_dot_min": round(cont["normal_dot_min"], 4), "face_flips": cont["face_flips"], "section_self_intersections": cont["section_self_intersections_total"],
        "edge_stretch_ratio_max": round(cont["edge_stretch_ratio_max"], 3), "blender_frames_all_zero": bl_all0, "blender_frames": len(blender_frames)}}
    items["80"] = {"name_ja": "船上の正面中央で、波の上側を上昇前から上昇後まで続けて見られる（形の切替・欠落 0）",
                   "value": {**common, "centre_band_elev_deg": {"t0": round(cen_f[0], 2), "t6": round(cen_f[int(6 * hz2)], 2), "t9": round(cen_f[int(9 * hz2)], 2), "tstar": round(cen_f[its], 2)},
                             "centre_band_max_drop_deg_per_frame": round(cen_drop, 3),
                             "ja": "座席 v1 から見た、座席の近くの行（波峰線方向 c が座席 ±5 m）の、海面より 0.3 m 高い水面の最大仰角（座席の形成の向き＝唇の方位の中央に見える）。原画視点と座席で同じ keypose・同じ時計（GWClock）の同じ上昇区間を描いた"},
                   "verdict": "pass" if (geom_ok and cen_drop < 1.0 and cen_f[its] > cen_f[int(2 * hz2)] + 20) else "fail"}
    items["106"] = {"name_ja": "船上の正面中央から左右まで、水面が同じ一面として上へ移る（裂け・位置跳び 0）",
                    "value": {**common, "left_elev_tstar": round(float(S["left_elev_max"][its]), 2), "right_elev_tstar": round(float(S["right_elev_max"][its]), 2),
                              "left_max_drop_deg_per_frame": round(float(np.max(np.maximum(np.nan_to_num(S["left_elev_max"], nan=-90)[:-1] - np.nan_to_num(S["left_elev_max"], nan=-90)[1:], 0))), 3),
                              "right_max_drop_deg_per_frame": round(float(np.max(np.maximum(np.nan_to_num(S["right_elev_max"], nan=-90)[:-1] - np.nan_to_num(S["right_elev_max"], nan=-90)[1:], 0))), 3),
                              "rows_ja": "左 = 手前の肩の行（c が座席 −25〜−5 m）、中央 = 座席 ±5 m、右 = 奥の行（座席 +5〜+15 m）の水面の最大仰角",
                              "ja": "固定位相の一枚の水面シート（添字は全フレーム同じ）。行の間の辺の伸びは K* と K0 の長い方の最大 %.2f 倍（裂けの目安 6 倍）" % cont["edge_stretch_ratio_max"]},
                    "verdict": "pass" if geom_ok else "fail"}
    items["107"] = {"name_ja": "船側の水面が上向きから船向きへ連続して変わる（面の反転・位置跳び 0）",
                    "value": {**common, "face_normal_up_deg": {"t0": round(S["face_normal_up_deg"][0], 2), "t8": round(S["face_normal_up_deg"][int(8 * hz2)], 2),
                                                               "tstar": round(S["face_normal_up_deg"][its], 2)},
                              "face_normal_dot_to_seat_tstar": round(S["face_normal_to_seat"][its], 3), "face_normal_turn_max_deg_per_frame": round(face_turn_max, 3),
                              "ja": "座席の近くの行（c が座席 ±5 m）の内壁（列 j_corner〜j_facebot）の平均の法線"},
                    "verdict": "pass" if (geom_ok and S["face_normal_up_deg"][0] < 1.0 and S["face_normal_to_seat"][its] > 0.3 and face_turn_max < 5.0) else "fail"}
    ok108_elev = bool(np.nanmax(lip_el) >= 60.0 and lip_drop < 1.0 and lip_el_f[int(2 * hz2)] < 20.0)
    items["108"] = {"name_ja": "船上から、前方の水面が船側へ延びて座席の上に入る過程を見られる",
                    "value": {"lip_elev_max_deg": {"t2": round(lip_el_f[int(2 * hz2)], 2), "t8": round(lip_el_f[int(8 * hz2)], 2), "t10": round(lip_el_f[int(10 * hz2)], 2),
                                                   "tstar": round(lip_el_f[its], 2), "max": round(float(np.nanmax(lip_el)), 2)},
                              "lip_elev_max_drop_deg_per_frame": round(lip_drop, 3),
                              "near_rows_tip_elev_deg_tstar": round(float(near_el[its]), 2),
                              "lip_horizontal_min_m_tstar": round(float(S["lip_hdist_min"][its]), 3),
                              "lip_points_within_5m_horizontal_max": int(S["lip_within5m"].max()),
                              "water_points_elev_ge_70deg_max": int(S["zenith70"].max()),
                              "blender_rays_elev_ge_60_hit_wave": {k: v["rays_elevation_ge_60deg"]["hit_wave"] for k, v in blender_frames.items()},
                              "lip_elev_max_over_all_frames_at_s": round(float(ts[int(np.nanargmax(lip_el))]), 4),
                              "kstar_static_lip_elev_deg": round(lip_el_f[its], 2),
                              "frames_before_tstar_above_kstar": int((lip_el_f[:its] > lip_el_f[its] + 1e-9).sum()),
                              "reading_ja": "読みは決めていない（保留、利用者の選択待ち）。作業計画の受入は「水面が座席の上方へ延びる」、バックログ 108 は「座席の上に入る」で、"
                                            "26修正01・27修正01 は t* の形がこれを満たさないとして、唇を座席の上方へ送ることを番号30 へ回した。ここでは 2 つの読みを測って記録する。"
                                            "(1) 仰角の読み（番号30 が置いた読みで、作業計画の既定値ではない）：座席は右船の座席 v1 に固定したまま、同じ水面（唇）の仰角が前方"
                                            "（t = 2 s で 20° 未満）から 60° 以上へ途切れずに（1 フレームで 1° 以上下がらない）上がる。60° 以上は静止した K*（t*）だけで満たしており、"
                                            "形成の途中で唇の仰角が K* を超える時刻はない（全区間の最大は t* = 12.0 s）。(2) 真上の読み：座席から水平 5 m 以内・仰角 70° 以上に水面が来る。満たさない。"},
                    "verdict": "保留（読みの選択待ち）",
                    "verdict_elevation_reading": "pass" if ok108_elev else "fail",
                    "verdict_overhead_reading": "pass" if (S["lip_within5m"].max() > 0 or S["zenith70"].max() > 0) else "fail"}
    ok111 = bool(tipdir[its] < -20 and tipdir_step < 3.0 and tip_jump_max < 0.6 and cl["tstar"])
    items["111"] = {"name_ja": "座席の上へ延びた水面の先が、下向きに曲がる過程を見られる（位置跳び・欠落 0）",
                    "value": {**common, "tip_dir_deg": {"t8": round(tipdir[int(8 * hz2)], 2), "t9": round(tipdir[int(9 * hz2)], 2), "t10": round(tipdir[int(10 * hz2)], 2),
                                                        "t11": round(tipdir[int(11 * hz2)], 2), "tstar": round(tipdir[its], 2), "max": round(float(tipdir.max()), 2)},
                              "tip_dir_step_max_deg_per_frame": round(tipdir_step, 3), "tip_jump_max_m_per_frame": round(tip_jump_max, 4),
                              "tstar_vs_kstar_max_m": cont["tstar_vs_kstar_max_m"],
                              "lip_parabola": {"main_row_t_apex_s": round(float(R.parab["t_apex"][ks.main_row]), 3), "main_row_G_per_m": round(float(R.parab["G"][ks.main_row]), 4),
                                               "main_row_deviation_m": round(cont["lip_parabola_deviation_main_row_m"], 4),
                                               "full_weight_rows_deviation_max_m": round(cont["lip_parabola_deviation_max_m_rows_full_weight"], 4)},
                              "ja": "座席の近くの行（c が座席 ±3 m）の唇先の向き（唇の上面の最後の 8 列、断面内の水平からの角の中央値。負が下向き）と唇先の位置の 1 フレームの移動"},
                    "verdict": "pass" if ok111 else "fail"}
    items["117"] = {"name_ja": "船上の近景で、前方から座席の上へ曲がる水面を一続きの面として見られる（減面なし、穴・切断 0）",
                    "value": {"same_mesh_all_views_and_frames": rrep["meshUnchanged"] and rrep["indexMatchesKeypose"], "vertex_count": rrep["vertexCount"],
                              "decimation": "なし（原画視点・座席・側面・背面とも同じ 96,000 頂点の同じ添字）", "contour_diff_px_vs_undecimated": 0.0,
                              "seat_rays_open_back_cut_hole": {k: [v["rays"]["wave_back_open"], v["rays"]["cut_end"], v["rays"]["hole"]] for k, v in blender_frames.items()}},
                    "verdict": "pass" if (rrep["meshUnchanged"] and rays0 and bl_all0) else "fail"}
    items["interp_shader_vs_numpy"] = {"name_ja": "シェーダーの補間と numpy の密なフレームの照合（t* ≤1 px、全区間 ≤2 cm）",
                                       "value": {"cpu_catmullrom_quantized_vs_dense_max_m_120hz": round(float(cr_err.max()), 5),
                                                 "cpu_worst_at_t_row_col": [round(float(ts_d[cr_at[0]]), 4)] + cr_at[1],
                                                 "gpu_vs_numpy_dense_max_m": round(gpu_dense_max, 5), "gpu_vs_cpu_catmullrom_max_m": gpu_cpu_max,
                                                 "gpu_capture_times": len(gpu), "tstar_px_max": px_tstar, "tstar_quantized_vs_kstar_max_m": tstar_q_err,
                                                 "keypose_quantization_max_m": kp["quantization_max_err_m"],
                                                 "ja": "GPU は頂点シェーダーと同じ関数（AF30KeyposeCore.cginc の AF30KeyposePosition）をコンピュートシェーダーで走らせて読み戻した値。t* の px は PaintingCam v1 で K* と比べた画面上の差（画面の周り 50 px までの頂点）"},
                                       "verdict": "pass" if (interp_ok and tstar_px_ok) else "fail"}
    items["tstar_remeasure"] = {"name_ja": "t* の再測定が 26修正01／28修正01 と ±0.5 px 以内", "value": {"worst_abs_diff_px": tst["worst_abs_diff_px"],
                                "silhouettes": tst["silhouettes_vs_26r01_28r01"], "boundaries": tst["boundaries_vs_28r01"],
                                "verdicts_af30": tst["summary_verdicts_af30"], "outline_interior_px": tst["outline_interior_px"]["af30"]["r01"]},
                                "verdict": "pass" if tst["pass"] else "fail"}
    items["continuity_suite"] = {"name_ja": "連続性の検査一式とガードレール（再生成のたび）", "value": {k: cont[k] for k in cont if k not in ("per_frame",)}, "verdict": "pass" if cont["all_pass"] else "fail"}
    items["blender_frames"] = {"name_ja": "途中のフレームのメッシュ検査（Blender、%d フレーム）" % len(blender_frames),
                               "value": {k: {kk: v[kk] for kk in ("nonmanifold_edges_gt2_faces", "boundary_edges", "flipped_inconsistent_winding_edges",
                                                                   "degenerate_faces_area_lt_1e-8", "self_intersecting_face_pairs", "flat_sea_faces_facing_down", "rays",
                                                                   "rays_elevation_ge_60deg")} for k, v in blender_frames.items()},
                               "verdict": "pass" if (bl_all0 and rays0) else "fail"}
    items["spi_compile"] = {"name_ja": "keypose の 2 シェーダーの SPI キーワードでのコンパイル（番号32 と同じ方法）", "value": {"allCompiled": rrep["spi"]["allCompiled"],
                            "allStereoOutput": rrep["spi"]["allStereoOutput"], "passes": len(rrep["spi"]["passes"])},
                            "verdict": "pass" if rrep["spi"]["allCompiled"] and rrep["spi"]["allStereoOutput"] else "fail"}
    items["keypose_memory"] = {"name_ja": "keypose の容量（計画 ≤512 MiB、判定は番号32 の手順で測る）",
                               "value": {"layers": nk, "position_bytes": kp["position_bytes"], "normal_bytes": kp["normal_bytes"],
                                         "files_total_MiB": round((kp["position_bytes"] + kp["normal_bytes"]) / 2 ** 20, 1),
                                         "unity_runtime_memory_size_MiB_record": round(rrep["textureMemoryBytes"] / 2 ** 20, 1)},
                               "verdict": "record-only"}
    items["played_keypose_faces"] = {"name_ja": "再生される面（16 ビットの keypose の Catmull-Rom）の向きと着色の法線（記録）",
                                     "value": {"hz": hz2, "frames": len(ts), "keypose_quantization_max_m": kp["quantization_max_err_m"],
                                               "tstar_played_vs_kstar_max_m": round(tstar_q_err, 6),
                                               "kstar_thin_faces_height_lt_1p5mm": int(thin.sum()),
                                               "kstar_thin_faces_rows_min_max": [int(tri_row[thin].min()), int(tri_row[thin].max())] if thin.any() else None,
                                               "tstar_faces_reversed_vs_kstar": int(rev_tstar.sum()),
                                               "tstar_reversed_faces_thin": int((rev_tstar & thin).sum()),
                                               "tstar_reversed_faces_height_max_mm": round(float(hK[rev_tstar].max()) * 1000, 3) if rev_tstar.any() else None,
                                               "tstar_reversed_faces_by_row": {str(int(r_)): int(c_) for r_, c_ in zip(rev_rows, rev_cnt)},
                                               "faces_reversed_vs_rig_face_frames": pl["rev_vs_rig_face_frames"],
                                               "faces_reversed_vs_rig_face_frames_before_tstar": pl["rev_vs_rig_formation_face_frames"],
                                               "faces_reversed_vs_rig_max_per_frame": pl["rev_vs_rig_max_per_frame"],
                                               "faces_reversed_vs_rig_max_at_s": pl.get("rev_vs_rig_max_at_s"),
                                               "faces_reversed_vs_rig_height_in_rig_max_mm": round(pl.get("rev_rig_height_max_m", 0.0) * 1000, 3),
                                               "faces_reversed_vs_rig_rows_min_max": [min(pl["rev_rows"]), max(pl["rev_rows"])] if pl.get("rev_rows") else None,
                                               "frames_with_reversed_faces": pl["rev_vs_rig_frames"],
                                               "faces_flipped_vs_previous_frame_face_frames": pl["flip_prev_face_frames"],
                                               "shading_normal_dot_min_adjacent_frames": round(pl["shading_dot_min"], 4), "shading_normal_dot_min_at_s": pl["shading_dot_min_t"],
                                               "ja": "連続性の検査一式（af30_continuity.json）と Blender の検査は float64 の rig で測る。実際に再生されるのは 16 ビットに量子化した key "
                                                     "（量子化の差 最大 約 1.2 mm）の Catmull-Rom なので、K* と形成の途中の細長い面（rig での高さが量子化の差と同じ mm の桁）の一部は、巻きの向きが rig と逆になる。"
                                                     "reversed_vs_rig は同じ時刻の rig との比較、flipped_vs_previous_frame は再生される面の前のフレームからの反転（連続性の検査一式の face_flips と同じ数え方）。"
                                                     "着色は頂点の法線（RG16 の八面体を同じ重みで補間して正規化）を使うので、その連続を隣のフレームとの内積で測る。"
                                                     "face-frames は 30 Hz の各フレームの面の数の和（t* の後の静止の区間を含む）。"},
                                     "verdict": "record-only"}
    M_ = {"schema": "GreatWave.AF30.metrics/1", "number": "30", "t_star_s": 12.0, "camera": spec["painting_cam"]["id"], "frame": [W, H],
          "evidence_kind_ja": "numpy の rig・連続性の検査、Blender 5.2.2 ヘッドレスのメッシュ検査、Unity 6000.4.3f1 Editor の batchmode による PC のオフスクリーン描画（RTX 3080、Direct3D11、Linear）。HMD 実機の結果ではない（HMD 未所持）。",
          "rig": {"path": rel(rig_path), "sha256": sha(rig_path)}, "kstar_gwb_sha256": ks.gwb_sha,
          "keys": {"layers": nk, "rate_hz": 15, "adaptive_added": nk - 181, "adaptive_rounds": kp["adaptive_rounds"]},
          "items": items, "videos": vids, "figures": sorted(figs.keys()),
          "summary_verdicts": {k: v["verdict"] for k, v in items.items()}}
    T.save_json(os.path.join(EVID, "metrics.json"), M_)

    # ---- run.json
    ins = ["Tools/GWWaveGen/af30_rig.json", "Tools/GWWaveGen/af30_formation.py", "Tools/GWWaveGen/af30_evidence.py", "Tools/GWWaveGen/af30_blender.py",
           "Tools/GWWaveGen/af30_tstar_eval.py", "Tools/GWWaveGen/run_af30.ps1", "Tools/GWWaveGen/run_af30_unity.ps1", "Tools/GWWaveGen/gw_wavegen.py",
           "Tools/GWContext/seat_v1.json", "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/colour/af28r01_evaluate.py", "Tools/PaintingTruth/colour/af28r01_params.json",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF30Formation.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF30KeyposeWave.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCore.cginc", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF30Keypose.cginc",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF30_NPR_Keypose.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF30_Outline_Keypose.shader",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCapture.compute", "Unity/Assets/GreatWave/ArtFirst/Materials/AF30_NPR_Keypose.mat",
           "Unity/Assets/GreatWave/ArtFirst/Materials/AF30_Outline_Keypose.mat", "Unity/Assets/GreatWave/Scenes/Tests/AF30_Formation.unity",
           "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45.gwb", "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45_rows.npz", "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45_meta.json",
           "Unity/Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin", "Unity/Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json"]
    build_files = []
    for d, _, fs in os.walk(BUILD):
        if os.sep + "t28" in d or os.sep + "frames" in d:
            continue
        for f_ in fs:
            if not f_.endswith(".log"):
                build_files.append(os.path.join(d, f_))
    import PIL
    run = {"schema": "GreatWave.AF30.run/1", "number": "30", "started_utc": started,
           "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af30.ps1",
                        "py -3.10 Tools/GWWaveGen/af30_formation.py --stage all",
                        "G:/SteamLibrary/steamapps/common/Blender/blender.exe --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af30_blender.py -- Unity/Build/ArtFirst/30/frames Unity/Build/ArtFirst/30/blender/af30_blender_qa.json 3.9544 1.8323 -15.0308 -2.1368 5.2525 -7.8754",
                        "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af30_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF30Formation.BuildAndRender -Log build_render",
                        "py -3.10 Tools/GWWaveGen/af30_tstar_eval.py", "py -3.10 Tools/GWWaveGen/af30_evidence.py"],
           "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": PIL.__version__,
                     "unity": rrep["unity"], "device": rrep["device"], "graphics_api": rrep["graphicsApi"], "color_space": rrep["colorSpace"],
                     "blender": bqa["blender"], "ffmpeg": FFMPEG, "os": platform.platform()},
           "unity_lock_ja": "Unity は Unity/Build/unity.lock を排他的に作ってから 1 プロセスだけ動かし、終わったら（失敗しても）消した（run_af30_unity.ps1）。",
           "timing_ja": "started_utc〜finished_utc と elapsed_evidence_s は、この証拠の段（af30_evidence.py）の実行だけの時刻。前の段（af30_formation.py・Blender・Unity・"
                        "af30_tstar_eval.py）の出力は、この実行で読んだものを not_committed_sha256 と unity_render_report の SHA-256 で固定する。",
           "inputs_sha256": {r_: sha(os.path.join(REPO, r_)) for r_ in ins if os.path.exists(os.path.join(REPO, r_))},
           "unity_build_report": {k: brep.get(k) for k in ("sceneSha256", "nprMatSha256", "outlineMatSha256", "protectedUnchanged", "protectedFiles", "changedFiles")},
           "unity_render_report": {k: rrep.get(k) for k in ("protectedUnchanged", "changedFiles", "passed", "totalSeconds", "indexSha256", "positionSha256", "normalSha256", "videos")},
           "outputs_sha256": {rel(os.path.join(EVID, f_)): sha(os.path.join(EVID, f_)) for f_ in sorted(os.listdir(EVID)) if f_ != "run.json"},
           "not_committed_sha256": {rel(p_): sha(p_) for p_ in sorted(build_files)},
           "not_committed_ja": "Unity/Build/ArtFirst/30/ は Git 対象外（/Unity/Build/）。keypose（位置 133 MB・法線 66 MB）、連続性の検査、GPU の読み戻し、静止画、動画、Blender の検査、t* の再測定（t28/、28修正01 の焼き込みをハードリンクで並べたもの）。同じコマンドで作り直せる。",
           "elapsed_evidence_s": round(time.time() - t0, 1)}
    T.save_json(os.path.join(EVID, "run.json"), run)
    print("AF30_EVIDENCE_DONE", M_["summary_verdicts"], round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
