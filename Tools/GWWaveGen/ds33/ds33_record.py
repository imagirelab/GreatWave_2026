# -*- coding: utf-8 -*-
"""設計33 の記録：証拠（Docs/Evidence/Design/33/）を作り、metrics.json と run.json を書く。

値は次の出力から読む（どれも Git 対象外）。
  - 爪の部：Unity/Build/Design/33/claws/（metrics.json・run.json・ds33_claw_checks.json・ds33_claws_indep_check.json・
    ds33_contour_tstar.json・ds33_visibility_tstar.json・ds33_claw_layout.json・図と動画）
  - 独立の測定器（harness）の部：Unity/Build/Design/33/harness/（claws_run/harness_metrics.json・harness_run.json、
    selftest/harness_selftest.json・図）
  - 進行役の独立の検査：リポジトリの外のコード。コードと出力の写しは Unity/Build/Design/33/indep_check/（chk_geom.json・chk_growth.json）
この道具で新しく数えるのは、t* の帯の形（隣り合う輪の向きの差・接線まわりのねじれ・中心線の折れ・内側の縁が折れ返る所）と、
C072 の断面の向きのコマごとの変化だけ（Unity/Build/Design/33/record/ds33_record_counts.json にも書く）。
あわせて、帯の近くからの形の図（限界の記録。numpy の描画で、Unity ではない）を描く。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds33/ds33_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = REPO + "/Tools/GWWaveGen/ds33"
B33 = REPO + "/Unity/Build/Design/33"
CL = B33 + "/claws"
HN = B33 + "/harness"
HNR = HN + "/claws_run"
HNS = HN + "/selftest"
IND = B33 + "/indep_check"
REC = B33 + "/record"
EV = REPO + "/Docs/Evidence/Design/33"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
MP4_LIMIT = 5 * 1024 * 1024
F_STAR = 360

sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds32")
from ds32_claw_figs import put, label  # noqa: E402  （日本語の文字を描くだけ）


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(o, p):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
        f.write("\n")


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, im):
    ok, buf = cv2.imencode(".png", im, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    assert ok
    buf.tofile(p)


def fit1080(im, bg=255):
    """1920×1080 の枠に収める（縮尺だけ変える。余白は白、上寄せ・左右の中央）。"""
    h, w = im.shape[:2]
    s = min(1920 / w, 1080 / h, 1.0)
    if s < 1:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
    out = np.full((1080, 1920, 3), bg, np.uint8)
    h, w = im.shape[:2]
    x0 = (1920 - w) // 2
    out[:h, x0:x0 + w] = im
    return out, round(s, 4)


def r3(x):
    return None if x is None else round(float(x), 3)


# ---------------------------------------------------------------- t* の帯の形（記録のみ）
def ang_deg(a, b):
    na = np.linalg.norm(a, axis=-1)
    nb = np.linalg.norm(b, axis=-1)
    c = (a * b).sum(-1) / np.maximum(na * nb, 1e-12)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def band_shape(P, c):
    """1 本の爪の帯の形。P は 1 コマの全頂点（m）、c は layout の爪。
    輪 j の幅の軸 B_j = 輪の頂点 0 − 頂点 4（φ 0° と 180°）、輪の中心 C_j = 8 頂点の平均。
      width_axis_deg：隣り合う輪の B の向きの差（接線まわりのねじれと、面の中の曲がりの両方を含む）
      twist_deg：隣り合う輪の B を、2 つの輪の中心を結ぶ向きに垂直な面へ写してからの向きの差（接線まわりのねじれ）
      turn_deg：中心線の隣り合う 2 区間の向きの差（中心線の折れ）
      fold：折れの所の曲率の半径（2 区間の長さの平均 / 折れの角 rad）が、その輪の幅の半分より小さい所（帯の内側の縁が折れ返る）"""
    o, st = c["vert_offset"], c["stations"]
    R = P[o + 1:o + 1 + 8 * st].reshape(st, 8, 3).astype(np.float64)
    C = R.mean(1)
    B = R[:, 0] - R[:, 4]
    width_axis = ang_deg(B[:-1], B[1:])
    T = C[1:] - C[:-1]
    Ln = np.linalg.norm(T, axis=1)
    Tu = T / np.maximum(Ln, 1e-12)[:, None]
    a = B[:-1] - Tu * (B[:-1] * Tu).sum(1, keepdims=True)
    b = B[1:] - Tu * (B[1:] * Tu).sum(1, keepdims=True)
    twist = ang_deg(a, b)
    turn = ang_deg(T[:-1], T[1:])
    lmean = 0.5 * (Ln[:-1] + Ln[1:])
    radius = lmean / np.maximum(np.radians(turn), 1e-9)
    half_w = 0.5 * np.linalg.norm(B[1:-1], axis=1)
    fold = radius < half_w
    return {"width_axis_deg": width_axis, "twist_deg": twist, "turn_deg": turn, "fold": fold}


def shape_counts(X, lay):
    P = np.asarray(X[F_STAR], np.float64)
    per = []
    for c in lay["claws"]:
        s = band_shape(P, c)
        per.append({"id": c["id"], "type": c["type"],
                    "width_axis_max_deg": round(float(s["width_axis_deg"].max()), 1),
                    "twist_max_deg": round(float(s["twist_deg"].max()), 1),
                    "turn_max_deg": round(float(s["turn_deg"].max()), 1),
                    "fold_joints": int(s["fold"].sum())})

    def cnt(key, thr):
        return int(sum(1 for p in per if p[key] > thr))

    def top(key, n=8):
        return [[p["id"], p["type"], p[key]] for p in sorted(per, key=lambda p: -p[key])[:n]]

    out = {
        "frame": F_STAR,
        "rule_ja": "t*（コマ 360）の帯の形。輪 j の幅の軸 B_j＝輪の頂点 0 − 頂点 4（φ 0° と 180°）、輪の中心 C_j＝8 頂点の平均。"
                   "width_axis：隣り合う輪の B の向きの差（接線まわりのねじれと面の中の曲がりの両方を含む）。"
                   "twist：隣り合う輪の B を、2 つの輪の中心を結ぶ向きに垂直な面へ写してからの向きの差（接線まわりのねじれ）。"
                   "turn：中心線の隣り合う 2 区間の向きの差（中心線の折れ）。"
                   "fold：折れの所の曲率の半径（2 区間の長さの平均 / 折れの角 rad）が輪の幅の半分より小さい所（帯の内側の縁が折れ返る）。記録のみ",
        "width_axis_deg": {"over_45": cnt("width_axis_max_deg", 45), "over_30": cnt("width_axis_max_deg", 30), "top": top("width_axis_max_deg")},
        "twist_deg": {"over_45": cnt("twist_max_deg", 45), "over_30": cnt("twist_max_deg", 30), "top": top("twist_max_deg")},
        "turn_deg": {"over_45": cnt("turn_max_deg", 45), "over_30": cnt("turn_max_deg", 30), "top": top("turn_max_deg")},
        "fold": {"claws_with_fold": int(sum(1 for p in per if p["fold_joints"] > 0)),
                 "joints_total": int(sum(p["fold_joints"] for p in per)),
                 "top": [[p["id"], p["type"], p["fold_joints"]] for p in sorted(per, key=lambda p: -p["fold_joints"])[:10] if p["fold_joints"] > 0]},
        "per_claw": per,
    }
    return out


def c072_series(X, lay, skel):
    c = [x for x in lay["claws"] if x["id"] == "C072"][0]
    rows = []
    for f in range(194, 226):
        vis = bool(skel[f, c["index"], 34] > 0.5)
        if not vis:
            rows.append([f, round(f / 30, 3), False, None, None])
            continue
        s = band_shape(np.asarray(X[f], np.float64), c)
        rows.append([f, round(f / 30, 3), True, round(float(s["twist_deg"].max()), 1), int(np.argmax(s["twist_deg"]))])
    return {"rule_ja": "C072 のコマごとの接線まわりのねじれの最大（隣り合う輪。band_shape の twist）と、その輪の組の番号 j（輪 j と j+1）",
            "columns": ["frame", "t_s", "visible", "twist_max_deg", "ring_pair_j"], "rows": rows}


def jumps_px(X, lay, jumps):
    """進行役の検査の段（chk_growth.json の jumps）を、固定の PaintingCam v1（t* の原画視点）の表示の画素で読む。
    段の前のコマの根元に対する形を、段のコマの根元へ平行に移して投影し、段のコマの形との差（頂点の最大）を取る。"""
    sys.path.insert(0, REPO + "/Tools/PaintingTruth")
    import truthlib as TL  # noqa: E402
    spec = TL.load_spec()
    cl = {c["id"]: c for c in lay["claws"]}
    rows = []
    for (cid, f, d_m, med_m, len_m) in jumps:
        c = cl[cid]
        o, n = c["vert_offset"], c["vert_count"]
        V1 = np.asarray(X[f, o:o + n], np.float64)
        V0 = np.asarray(X[f - 1, o:o + n], np.float64)
        V0s = V0 - V0[0] + V1[0]
        x1, y1 = TL.project_world(spec, V1)[:2]
        x0, y0 = TL.project_world(spec, V0s)[:2]
        dpx = float(np.hypot(x1 - x0, y1 - y0).max())
        size = float(np.hypot(x1 - x1[0], y1 - y1[0]).max())
        rows.append([cid, int(f), round(dpx, 2), round(size, 1), round(float(x1[0]), 1), round(float(y1[0]), 1)])
    return {"rule_ja": "固定の PaintingCam v1（t* の原画視点）で読んだ段の大きさ。段の前のコマの根元に対する形を段のコマの根元へ平行に移し、"
                       "段のコマの形との差の最大（表示の px）と、そのコマの爪の大きさ（根元から最も遠い頂点まで、px）。"
                       "動画の左の視点は波の枠と一緒に動くので、この読みは目安",
            "columns": ["id", "frame", "jump_px", "claw_size_px", "root_x_px", "root_y_px"], "rows": rows}


# ---------------------------------------------------------------- 限界の図（帯を近くから）
FW = np.array([-2.5, 6.7, 66.0])
FW = FW / np.linalg.norm(FW)
UPW = np.array([0.0, 1.0, 0.0])


def draw_claw(X, T, A, c, f, W=480, H=540, top=40):
    """1 本の爪の帯を、決まった向き（進行役の独立の検査の近くからの図と同じ向き）から透視で描く（画家の方法）。"""
    P = np.asarray(X[f], np.float64)
    sel = np.where(A[:, 0] == c["index"])[0]
    tv = T[sel]
    pts = P[c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
    ctr = pts.mean(0)
    pos = ctr - FW * 20.0
    rt = np.cross(UPW, FW)
    rt /= np.linalg.norm(rt)
    up = np.cross(FW, rt)
    d = P - pos
    z = d @ FW
    sx = (d @ rt) / z
    sy = -(d @ up) / z
    xs, ys = sx[tv], sy[tv]
    lo = np.array([xs.min(), ys.min()])
    hi = np.array([xs.max(), ys.max()])
    span = max(hi - lo) * 1.12 + 1e-12
    s = min(W, H - top) / span
    cx, cy = (lo + hi) / 2
    img = np.full((H, W, 3), 236, np.uint8)
    order = np.argsort(-z[tv].mean(1))
    cols = {0: (250, 250, 250), 1: (212, 200, 168), 2: (244, 244, 244)}
    for k in order:
        q = np.stack([(xs[k] - cx) * s + W / 2, (ys[k] - cy) * s + top + (H - top) / 2], 1)
        q = np.round(q * 16).astype(np.int32)
        cv2.fillPoly(img, [q], cols[int(A[sel[k], 1])], cv2.LINE_AA, 4)
        cv2.polylines(img, [q], True, (120, 120, 120), 1, cv2.LINE_AA, 4)
    return img


def limit_figure(X, T, A, lay, sc, jp):
    cl = {c["id"]: c for c in lay["claws"]}
    top_ids = [t[0] for t in sc["width_axis_deg"]["top"][:4]]
    per = {p["id"]: p for p in sc["per_claw"]}
    panels = []
    for f in (216, 217, 218, 219):
        im = draw_claw(X, T, A, cl["C072"], f)
        im = label(im, (8, 8), "C072  コマ %d（t %.2f s）" % (f, f / 30), size=18, col=(255, 255, 255))
        panels.append(im)
    for i in top_ids:
        im = draw_claw(X, T, A, cl[i], F_STAR)
        p = per[i]
        im = label(im, (8, 8), "%s（%s） t*  向きの差 %.0f°・折れ %.0f°" % (i, p["type"], p["width_axis_max_deg"], p["turn_max_deg"]),
                   size=17, col=(255, 255, 255))
        panels.append(im)
    fig = np.concatenate([np.concatenate(panels[:4], 1), np.concatenate(panels[4:], 1)], 0)
    big = max(jp["rows"], key=lambda r: r[2])
    for x in (480, 960, 1440):
        cv2.line(fig, (x, 0), (x, 1079), (160, 160, 160), 1)
    cv2.line(fig, (0, 540), (1919, 540), (160, 160, 160), 1)
    fig = put(fig, ["設計33 の限界（記録のみ）：上＝C072 の輪の断面が 1 コマで回る所（コマ 217 → 218）。下＝t* で隣り合う輪の向きの差が大きい 4 本",
                    "爪 1 本の帯を決まった向きから近くで描いた numpy の描画（Unity ではない）。白＝上面、淡い水色＝縁の側面と下面。"
                    "固定の原画視点で読むと段は最大 %.1f px（%s、爪の大きさ %.1f px）" % (big[2], big[0], big[3])],
              size=17, xy=(12, 1020))
    return fig, top_ids


# ---------------------------------------------------------------- main
def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    cm = jload(CL + "/metrics.json")
    cr = jload(CL + "/run.json")
    cc = jload(CL + "/ds33_claw_checks.json")
    ci = jload(CL + "/ds33_claws_indep_check.json")
    ct = jload(CL + "/ds33_contour_tstar.json")
    cv = jload(CL + "/ds33_visibility_tstar.json")
    lay = jload(CL + "/ds33_claw_layout.json")
    hm = jload(HNR + "/harness_metrics.json")
    hr = jload(HNR + "/harness_run.json")
    hs = jload(HNS + "/harness_selftest.json")
    og = jload(IND + "/chk_geom.json")
    ow = jload(IND + "/chk_growth.json")

    frames_sha = sha(CL + "/ds33_claw_frames_f32.bin")
    assert frames_sha == lay["files"]["frames"]["sha256"] == ci["inputs"]["frames_sha256"] == \
        hr["provider"]["files"]["frames"]["sha256"], "爪の部の出力が測定の後に変わった"

    NF, NV, NT = lay["frames"], lay["vertices"], lay["triangles"]
    X = np.memmap(CL + "/ds33_claw_frames_f32.bin", np.float32, "r", shape=(NF, NV, 3))
    T = np.fromfile(CL + "/ds33_claw_tris_i32.bin", np.int32).reshape(NT, 3)
    A = np.fromfile(CL + "/ds33_claw_tri_attr_u16.bin", np.uint16).reshape(NT, 2)
    skel = np.fromfile(CL + "/ds33_claw_skel_f32.bin", np.float32).reshape(NF, len(lay["claws"]), 36)

    # ---- 記録の時に数えるもの ----
    sc = shape_counts(X, lay)
    rc = {"schema": "GreatWave.DS33.record_counts/1",
          "note_ja": "記録の時に数えたもの（ds33_record.py）。爪の部の出力 ds33_claw_frames_f32.bin（SHA-256 %s）から。記録のみで、合否は出さない" % frames_sha,
          "band_shape_tstar": sc, "c072_twist_series": c072_series(X, lay, skel),
          "jumps_px_paintcam": jumps_px(X, lay, ow["jumps"])}
    arc = skel[F_STAR, :, 35]
    ia = int(np.argmax(arc))
    rc["arc_length_tstar_m"] = {"rule_ja": "骨格の表 ds33_claw_skel_f32.bin の欄 35（帯の弧長 m）の t*（コマ 360）の値",
                                "max": round(float(arc.max()), 3), "max_id": lay["claws"][ia]["id"],
                                "median": round(float(np.median(arc)), 3), "min": round(float(arc.min()), 3)}
    rc["root_class_dark"] = [[p["id"], p["root_class"], p["dist_to_white_vertex_m"]] for p in cc["web_join"]["per_claw"]
                             if p["root_class"] not in ("白", "淡い水色")]
    fig_lim, lim_ids = limit_figure(X, T, A, lay, sc, rc["jumps_px_paintcam"])
    rc["limit_figure_claws"] = {"top_row": ["C072 コマ 216〜219"], "bottom_row_tstar": lim_ids}
    jdump(rc, REC + "/ds33_record_counts.json")

    # ---- 証拠：画像（1920×1080） ----
    pngs = {}

    def put_png(name, im, src_path, how):
        assert im.shape[:2] == (1080, 1920), name
        imwrite(EV + "/" + name, im)
        pngs[name] = {"source": rel(src_path) if src_path else None, "source_sha256": sha(src_path) if src_path else None, "how_ja": how}

    same = ["fig_ds33_tstar_overlay.png", "fig_ds33_tstar_render.png",
            "fig_ds33_rows_upper.png", "fig_ds33_rows_middle.png", "fig_ds33_rows_boat.png", "fig_ds33_rows_bregion.png",
            "fig_ds33_rows_upper_render.png", "fig_ds33_rows_middle_render.png", "fig_ds33_rows_boat_render.png",
            "fig_ds33_rows_bregion_render.png", "fig_ds33_contour_tstar.png"]
    for f in same:
        p = CL + "/fig/" + f
        put_png(f, imread(p), p, "1920×1080 のまま")
    for f in ("fig_ds33_types.png", "fig_ds33_single_growth.png"):
        p = CL + "/fig/" + f
        im = imread(p)
        out, s = fit1080(im)
        put_png(f, out, p, "%d×%d を 1920×1080 の枠へ（縮尺 %.3f）" % (im.shape[1], im.shape[0], s))
    # 成長の静止画は 3 段 × 2 組（1 段 540 px）。2 段と 1 段に分ける
    p = CL + "/fig/fig_ds33_growth_stills.png"
    im = imread(p)
    assert im.shape[:2] == (1620, 1920), im.shape
    put_png("fig_ds33_growth_stills_1.png", im[:1080], p, "1920×1620 の上の 2 段（t 7.0・8.5・9.5・10.3 s）")
    out, _ = fit1080(im[1080:])
    put_png("fig_ds33_growth_stills_2.png", out, p, "1920×1620 の下の 1 段（t 11.0・12.0 s）を 1920×1080 の枠の上へ")
    # 独立の測定器の輪郭の図：下の英語の凡例の 2 行を、日本語の説明の帯で覆う（図の中身は同じ）
    p = HNR + "/fig_ds33h_outline_132_72.png"
    im = imread(p)
    im[1010:1080] = 20
    o = hm["outline"]
    im = put(im, ["独立の測定器（numpy、Unity ではない）：主役波のシート＋爪を PaintingCam v1 で被覆にし、評価器で測った。水色＝原画の輪郭、描画の縁の差：緑 ≤ 2 px・黄 ≤ 4 px・赤 > 4 px",
                  "細部込み 132 最大 %.3f px（シートだけ %.3f）・72 p95 %.3f px（シートだけ %.3f）。71・fuji_ridge・sky の印は評価器のほかの項目で、この番号の関門ではない" % (
                      o["with_claws"]["132"]["max_px"], o["sheet_only_same_method"]["132"]["max_px"],
                      o["with_claws"]["72"]["p95_px"], o["sheet_only_same_method"]["72"]["p95_px"])],
             size=17, xy=(12, 1016))
    put_png("fig_ds33h_outline_132_72.png", im, p, "1920×1080。下の英語の凡例の 2 行を日本語の説明の帯で覆った")
    imwrite(REC + "/fig_ds33_limit_band_folds.png", fig_lim)
    put_png("fig_ds33_limit_band_folds.png", fig_lim, None, "この道具で描いた（爪の部の頂点のコマの表から）")

    # ---- 証拠：動画（5 MB 以下へ符号化し直す） ----
    src_mp4 = CL + "/fig/ds33_claws_growth_30fps.mp4"
    dst_mp4 = EV + "/ds33_claws_growth_30fps.mp4"
    crf_used = None
    for crf in (24, 26, 28, 30, 32):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src_mp4, "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst_mp4], check=True)
        if os.path.getsize(dst_mp4) <= MP4_LIMIT:
            crf_used = crf
            break
    assert crf_used is not None
    probe = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-count_frames", "-show_entries",
                            "stream=width,height,nb_read_frames,r_frame_rate", "-of", "json", dst_mp4],
                           capture_output=True, text=True, check=True)
    st = json.loads(probe.stdout)["streams"][0]
    video = {"file": "ds33_claws_growth_30fps.mp4", "source": rel(src_mp4), "source_sha256": sha(src_mp4),
             "source_bytes": os.path.getsize(src_mp4),
             "reencode_ja": "libx264 -preset slow -crf %d（元は %d バイトで 5 MB を超えるので符号化し直した。大きさ・コマ数は同じ）" % (
                 crf_used, os.path.getsize(src_mp4)),
             "width": st["width"], "height": st["height"], "frames": int(st["nb_read_frames"]), "fps": st["r_frame_rate"],
             "bytes": os.path.getsize(dst_mp4),
             "content_ja": "t 5.5〜14 s。左＝原画視点の拡大、右上＝波頭を斜め横から、右下＝唇の船側の爪の近く。視点は波の枠と一緒に動き、t* で原画視点と一致する。numpy の描画（Unity ではない）"}

    # ---- 証拠：JSON の写し ----
    copied = {}
    for src, dst in ((CL + "/metrics.json", "ds33_claws_part_metrics.json"),
                     (CL + "/ds33_claw_checks.json", "ds33_claw_checks.json"),
                     (CL + "/ds33_claws_indep_check.json", "ds33_claws_indep_check.json"),
                     (CL + "/ds33_contour_tstar.json", "ds33_contour_tstar.json"),
                     (CL + "/ds33_visibility_tstar.json", "ds33_visibility_tstar.json"),
                     (CL + "/ds33_claw_layout.json", "ds33_claw_layout.json"),
                     (HNR + "/harness_metrics.json", "ds33_harness_metrics.json"),
                     (HNS + "/harness_selftest.json", "ds33_harness_selftest.json"),
                     (IND + "/chk_geom.json", "ds33_indep_chk_geom.json"),
                     (IND + "/chk_growth.json", "ds33_indep_chk_growth.json"),
                     (REC + "/ds33_record_counts.json", "ds33_record_counts.json")):
        shutil.copyfile(src, EV + "/" + dst)
        copied[dst] = {"source": rel(src), "sha256": sha(src)}

    # ---- metrics.json ----
    acc = cm["acceptance"]
    hv = hm["verdicts"]
    hp = hm["painting"]
    tp = ow["tstar_projection"]
    sc_w, sc_t, sc_n, sc_f = sc["width_axis_deg"], sc["twist_deg"], sc["turn_deg"], sc["fold"]
    metrics = {
        "schema": "GreatWave.DS33.metrics/1",
        "number": "設計33",
        "title_ja": "波頭の帯と 3〜5 種類の爪の試作",
        "generated_utc": now,
        "evidence_kind_ja": "numpy の生成器・検査と、numpy の z バッファの描画（仮の NPR）。独立の測定器（harness）と進行役の独立の検査も numpy。"
                            "Unity の描画ではない。HMD 実機の結果ではない。利用者は確かめていない",
        "acceptance": {
            "ja": "計画 §2.2 の設計33 の最小の受入（Q26：この番号は最小の受入だけを満たす。修正は 1 回まで）",
            "overlay_position_orientation": {
                "rule_ja": "原画視点で一覧の爪の位置・向きの対応が見て取れる（重ね図。爪ごとの 4 px は記録のみ）",
                "figures": ["fig_ds33_tstar_overlay.png", "fig_ds33_rows_upper.png", "fig_ds33_rows_middle.png", "fig_ds33_rows_boat.png",
                            "fig_ds33_rows_bregion.png"],
                "claws_part": {"skeleton_vs_list_hausdorff_px": acc["overlay_position_orientation"]["record_only_4px"],
                               "root_px_max": cc["reprojection_tstar_record_only"]["root_px_max"],
                               "tip_px_max": cc["reprojection_tstar_record_only"]["tip_px_max"]},
                "harness": {"rendered": hp["rendered"], "nearest_is_self": hp["nearest_is_self"], "root_err_px": hp["root_err_px"],
                            "tip_err_px": hp["tip_err_px"], "angle_err_deg": hp["angle_err_deg"],
                            "centerline_mean_px": hp["centerline_mean_px"], "flagged": hp["flagged"]},
                "orchestrator": {"root_err_px_median_max": tp["root_err_px"], "tip_err_px_median_max": tp["tip_err_px"],
                                 "dir_err_deg_median_max": tp["dir_err_deg"], "centerline_hd_px_median_p95_max": tp["hd_px"],
                                 "hd_le_4px": tp["hd_le4"], "worst": tp["worst"][:2]},
                "verdict": "合格（目視・進行役の判断。3 つの読みで根元 ≤ 0.148 px、先端 ≤ 1.98 px、向き ≤ 7.2°。利用者は未確認）"},
            "105": {"rule_ja": "根元から水面までの距離 ≤ 1 mm（全コマ）",
                    "claws_part_m": acc["105"]["value_m"], "claws_part_indep_m": acc["105"]["indep_m"],
                    "harness_m": hv["105_root_to_surface_le_1mm"]["value_m"],
                    "orchestrator_visible_m": og["105_root_to_surface_m"]["visible_frames"]["max"],
                    "orchestrator_all_frames_m": og["105_root_to_surface_m"]["all_frames"]["max"],
                    "verdict": "合格（numpy）"},
            "137": {"rule_ja": "根元の滑り 0（許容 1 mm は float32 の丸め）",
                    "claws_part_m": acc["137"]["value_m"], "claws_part_cells": acc["137"]["value_cells"],
                    "claws_part_indep_m": acc["137"]["indep_m"], "harness_m": hv["137_root_slip_0"]["value_m"],
                    "harness_cells": hv["137_root_slip_0"]["value_cells"],
                    "orchestrator_visible_m": og["137_root_slip"]["m_visible"]["max"],
                    "orchestrator_all_frames_m": og["137_root_slip"]["m_vs_fixed_rc_all"]["max"],
                    "orchestrator_cells_visible": og["137_root_slip"]["cells_visible"]["max"],
                    "verdict": "合格（numpy）"},
            "139": {"rule_ja": "成長の途中の欠落 0（使える水準）",
                    "claws_part": acc["139"]["generator"], "claws_part_indep": acc["139"]["indep"],
                    "harness": {k: hv["139_no_missing_mid_growth"][k] for k in ("gaps", "zero_area", "nonfinite", "count", "missing_vs_ds32_bound")},
                    "orchestrator": {"gaps": ow["139_gaps"], "birth_vs_tau_birth_bad": ow["birth_vs_tau_birth_bad"],
                                     "birth_time_s": ow["birth_time_s"], "area_change_after_tstar_max_rel": ow["area_change_after_tstar_max_rel"]},
                    "verdict": "合格（numpy）"},
            "vertices": {"rule_ja": "1 本あたり ≤ 600 頂点",
                         "per_claw_max": acc["vertices"]["per_claw_max"], "per_type_instance_max": acc["vertices"]["per_type_instance_max"],
                         "total": cc["vertices"]["total"], "triangles": cc["vertices"]["triangles"],
                         "harness_max": hv["vertex_budget_le_600"]["max"], "orchestrator": og["vertex_budget"],
                         "verdict": "合格"},
            "all_pass": True,
        },
        "backlog": {
            "ja": "計画 §2.2 の設計33：95〜98・101・103〜105・122〜129・136〜139・200（使える水準、精度は仕上げ32・33）。項目の中身は美術優先の作業計画の 33・35 の受入の書き方による",
            "items": {
                "105": {"value_m": hv["105_root_to_surface_le_1mm"]["value_m"], "verdict": "合格（numpy）"},
                "137": {"value_m": hv["137_root_slip_0"]["value_m"], "verdict": "合格（numpy）"},
                "139": {"value": "途切れ 0・面積 0 のコマ 0・NaN 0、148 本（150 ± 15）", "verdict": "合格（numpy、使える水準）"},
                "95〜98": {"value_ja": "船側の列 45 本を生成（型と一覧のパラメータから）", "verdict": "記録のみ"},
                "101・103・104": {"value_ja": "t* の先端 ≤ 1.98 px（3 つの読み）。爪ごとの縁の Hausdorff（測定器）p95 ≤ 4 px が 94／148、最大 ≤ 4 px が 61／148",
                                  "verdict": "記録のみ（精度は仕上げ33）"},
                "122・127・128": {"value_ja": "根元 ≤ 0.148 px、先端 ≤ 1.98 px（t*、一覧から作ったので作りによる一致）", "verdict": "記録のみ"},
                "123〜126": {"value_ja": "代表の R6（C075）・R8（C106）・R10（C092）も型から生成。骨格と一覧の中心線の対称 Hausdorff は C092 3.918 px・C075 2.314 px（爪の部）。"
                                         "進行役の読み（輪の中心の折れ線）では C075 5.02 px", "verdict": "記録のみ（仕上げ32・33）"},
                "129": {"value_ja": "爪の瞬間移動 0（爪の部）、先端の突出 0（爪の部の独立の検査）。群の置き換えは作っていない", "verdict": "記録のみ"},
                "136": {"value_ja": "支でない爪は根元の T_white の最初のコマで見え始める（進行役の検査）。支は主爪が届くまで待つので、T_white より最大 %.2f s 遅い（測定器）。t* で全部伸び切る"
                                    % hv["136_birth_record"]["birth_minus_twhite_abs_max_s"], "verdict": "記録のみ"},
                "138": {"value_ja": "根元の近くの向きの、根元の局所の座標系での変化は 30%% 成長の後で最大 %.1f°（粗い読み）" % hv["138_root_angle_record"]["change_after30pct_max_deg"],
                        "verdict": "記録のみ"},
                "200": {"value_ja": "根元の色区は白 114・淡い水色 32・藍濃 2。ΔE00 は測っていない（描画は仮の NPR）", "verdict": "記録のみ（段階7）"},
                "99（SHOULD）": {"value_ja": "側面の厚みの比 0.18（支）・0.20（T1・T2）・0.25（T4）。計画は 15〜25%", "verdict": "記録のみ（範囲の内）"},
            },
        },
        "design": {k: cm["design"][k] for k in ("types", "claws", "rows", "segments", "joint_how", "hanging", "skeleton_vs_user100", "band",
                                                 "growth", "root_binding_ja", "web_join", "b_region_q16", "teleport")},
        "regression": {
            "ja": "計画 §2.0 の回帰。Unity の原画視点の描画は変えていない（Unity/Assets/GreatWave/Design33 はない）。爪をシートに載せた時の値を numpy の 2 つの読みで測った",
            "claws_part_unity_like": {"no_claws": cm["record_only"]["contour_tstar"]["no_claws"],
                                      "claws": cm["record_only"]["contour_tstar"]["claws"],
                                      "unity_29r01_30": cm["record_only"]["contour_tstar"]["unity_reference"]["unity_29r01_30"],
                                      "delta_claws_minus_no_claws": ct["delta_claws_minus_no_claws"]},
            "harness_28r01_reading": {"values": hv["regression_78_130_131_132lf_72lf"]["values"],
                                      "raw_132_72": hv["132_72_raw_vs_28r01"], "verdict": hv["regression_78_130_131_132lf_72lf"]["verdict"]},
            "harness_unity_like_reading": hv["scene_reading_unity_like"],
            "colour_items_ja": "色の項目（73・77・79・118・120・133・134・263・265〜267・270）は、Unity の原画視点を変えていないので 29修正01・設計30 のまま",
            "verdict": "後退なし（numpy の 2 つの読み）",
        },
        "record_only": {
            "visibility_tstar": cm["record_only"]["visibility_tstar"],
            "arc_length_drop": cm["record_only"]["arc_length_drop"],
            "harness_per_claw_4px": hv["per_claw_4px_record"],
            "harness_region_iou": hp["region_iou"],
            "harness_hidden_by_sheet_frac": hp["hidden_by_sheet_frac"],
            "harness_c073_flag": hp["flagged"],
            "136": hv["136_birth_record"], "138": hv["138_root_angle_record"],
            "harness_length_decrease_claws": len(hm["tracks"]["claws_with_length_decrease"]),
            "band_shape_tstar": {k: sc[k] for k in ("width_axis_deg", "twist_deg", "turn_deg", "fold")},
            "c072_twist_series": rc["c072_twist_series"],
        },
        "extra_checks": {
            "ja": "計画の最小の受入の外の検査（測定器と進行役の追加の読み）",
            "harness_139b": hv["139b_geometry_continuity"],
            "orchestrator_area_drop_gt10pct": ow["area_drop_gt10pct"], "orchestrator_jumps": ow["jumps"],
            "orchestrator_jumps_columns_ja": "爪、コマ、根元に対する頂点の 1 コマの動きの最大 m、前後のコマの中央値 m、根元から先端までの距離 m",
            "jumps_px_paintcam": rc["jumps_px_paintcam"],
            "orchestrator_thickness_ratio": ow["thickness_ratio"], "orchestrator_root_to_ring0": og["root_to_ring0"],
            "verdict": "C072 だけ 139b 不合格（計画の 139 は合格）。修正の回は使っていないので、限界として記録（仕上げ33・設計34 の近くの見え方）",
        },
        "revisions": {"count": 0,
                      "ja": "受入のための修正は 0 回（Q26 の 1 回は使っていない）。受入の評価より前の開発中の調整 4 つ（幅の先細りを緩める、節が潰れる当てはめの当て直し、"
                            "関節の置き方、輪を面に沿わせる）は数えない。進行役の独立の検査は pass = true・必須の指摘 0 で、修正の回を開かなかった"},
        "independent": {
            "harness": {"files": {"ds33_harness.py": hr["tool_sha256"], "frames_sha256": hr["provider"]["files"]["frames"]["sha256"]},
                        "selftest": {"injected": hs["defects"]["injected"], "all_found": hs["defects"]["all_found"],
                                     "other_claws_flagged_tracks": hs["defects"]["other_claws_flagged_tracks"]},
                        "elapsed_s": hm["elapsed_s"]},
            "orchestrator_ja": "進行役の独立の検査（ファイルの時刻で 00:51〜00:57）。コードはリポジトリの外で、コードと出力の写しは Unity/Build/Design/33/indep_check/。"
                               "判定は pass = true、必須の指摘 0。動画の 256 コマを取り出して見た",
            "orchestrator_files": {f: sha(IND + "/" + f) for f in sorted(os.listdir(IND)) if f.endswith((".py", ".json"))},
            "claws_part_indep": {"file": "ds33_claws_indep_check.json", "all_pass": all(ci[k]["pass_"] for k in ("item105", "item137", "item139", "growth_order", "vertices"))},
        },
        "discrepancies_ja": [
            "105 の最大：爪の部 1.65e-6 m（見えるコマ）、爪の部の独立の検査 1.71e-6 m、測定器 2e-6 m（6 桁に丸めた値）、進行役 1.65e-6 m（見えるコマ）・3.79e-6 m（見えないコマを含む全コマ、C115 のコマ 93）。どれも ≤ 1 mm",
            "137 の最大：爪の部 2.0e-6 m、独立の検査 2.7e-6 m、測定器 6e-6 m（最初に見えたコマの値からの動き）、進行役 2.1e-6 m（見えるコマ）・7.3e-6 m（全コマ）。読みの違い",
            "『ねじれ』の数：進行役の独立の検査の報告は、t* で隣り合う輪の間のねじれが 45° を超える爪を 13 本とした。記録の時に数え直すと、それは隣り合う輪の幅の軸の向きの差（面の中の曲がりを含む）"
            "で 45° 超 %d 本・30° 超 %d 本。接線まわりのねじれだけなら 45° 超 %d 本（%s）。形がつぶれて見える主な原因は、中心線の折れ（45° 超 %d 本、最大 %s %.1f°）で帯の内側の縁が折れ返ること（%d 本）"
            % (sc_w["over_45"], sc_w["over_30"], sc_t["over_45"], ",".join(t[0] for t in sc_t["top"] if t[2] > 45),
               sc_n["over_45"], sc_n["top"][0][0], sc_n["top"][0][2], sc_f["claws_with_fold"]),
            "136 の遅れ：測定器は成長の始まりが T_white より最大 1.41 s 遅いとする（支）。進行役の検査は支でない爪の誕生が tau_birth（根元の 2×2 のセルの T_white の最小、差 ≤ 5e-5 s）の最初のコマとする。どちらも設計どおり",
            "C075 の中心線の差：爪の部（関節を通る曲線）2.314 px、進行役（輪の中心の折れ線）5.02 px。爪ごとの 4 px は記録のみ",
            "原画視点の対応の自動の旗：測定器は C073（シートが手前の割合 0.517 > 0.5）を挙げた。爪の部の見える割合（別の定義）では C073 は 1.0、最小は C095 の 0.613",
            "作業の指示の記録では開始 23:06。ファイルの時刻では Tools/GWWaveGen/ds33 の作成 23:16:26、Unity/Build/Design/33 の作成 23:18:22",
            "爪の部の t* の描画の図（fig_ds33_tstar_render.png）の見出しはコマ 420。t ≥ 12 s は t* の保持なので形はコマ 360 と同じ（測定器の保持の間の面積の変化 0）",
            "爪の部の成長の時刻の限界の文（0.69〜2.68 s）は、根元の T_white から t* までの長さ。進行役の検査の誕生の時刻は t 6.07〜10.17 s",
            "爪の部の報告の『空へ出る爪 22 本 → 15 本』の 22 は、設計32 の修正01 の前の値。修正01 の後の ds32_ids.json では、根元の深さの面の上の先端は 21 本（Design_32_ja.md 第 5 節の 18）。設計33 の空へ出る爪は 15 本（design.hanging）",
            "爪の部の報告の 3 次元の弧長の最大 4.05 m は、骨格の表（skel の欄 35）の t* の値では %.3f m（%s）" % (rc["arc_length_tstar_m"]["max"], rc["arc_length_tstar_m"]["max_id"]),
        ],
        "decision": [
            "Q26 の 1 回の修正の回を開かない：独立の検査が pass = true・必須の指摘 0。C072 の断面の回り（測定器の追加の 139b）と帯の折れ返りは、原画視点では 2.2 px 以下で見えず、計画の最小の受入の外。近くの見え方（設計34・仕上げ33）の限界として記録した",
            "回帰の規則：Unity の原画視点を変えていないので評価器は回していない。爪をシートに載せた値を numpy の 2 つの読み（爪の部と測定器）で測り、後退なしを確かめた",
            "崩壊での消失は作らない（Q11）。動画は成長 → 曲がり → t* の保持",
            "損切りの形（3 段の標準曲線）をはじめから既定にした（見え方の否決はまだない）",
            "T3・T5 は型の試作の図だけ（一覧に当てはまる爪がない／右側の爪がシートに結び付いていない）",
        ],
        "handoffs": {
            "設計34": "頂点のコマの表（ds33_claw_frames_f32.bin）を主役波と同じコマ番号で結合メッシュへ差し替える。ds32 の履歴の根元（双線形）は描画の三角形から最大 9.2 mm 離れるので、根元は ds33 のメッシュ（描画と同じ三角形の上）を使う。"
                    "座席からの見え方（唇から空へ出る爪の隠れ、面に沿う爪の隠れ、帯の折れ返りと C072 の断面の回り）、船の後ろの遮蔽、Mock の両眼。HMD は保留",
            "仕上げ32": "爪ごとの輪郭の合わせ（帯の見かけの幅が領域の 0.72〜0.81 倍）、支の判定の規則、代表の形",
            "仕上げ33": "帯の断面の向きを輪の間とコマの間で続ける（平行移動の座標系）、中心線の急な折れの所の幅、成長の時刻、132・72 の爪のこぶ（細部込みで 4 px に届かない）",
            "段階7": "根元の白の円の角ばり、爪の色と線（200 の ΔE00）",
            "右側の爪": "T5 の生成（右側の爪 C129〜C153 のシートへの結び付けから）。ブラッシュアップの最後",
        },
        "time": {"limit_h": 8,
                 "ja": "Q26 の日程で 8 時間（計画 §2.6 の Q26 の表、10/1 の設計33）。作業の指示の記録では 9/29 23:06 開始。ファイルの時刻で Tools/GWWaveGen/ds33 の作成 23:16:26 〜 "
                       "爪の部の記録 00:31:38（claws/run.json）、測定器の最後の出力 00:47:13（harness/README_interface.txt）、進行役の独立の検査 00:51〜00:57、記録 01:00 から。"
                       "23:06〜00:57 は約 1 時間 51 分で、8 時間の上限の内。1 回の計算は長くて爪の部の動画 約 40 分（README_interface.txt の見積もり）"
                       "で、30 分の上限を超える（numpy の描画。Unity・Houdini の計算ではない）"},
        "hmd_ja": "HMD（PS VR2）の項目は保留（導入は利用者の手）。Mock の両眼と PC の確認は設計34",
    }
    jdump(metrics, EV + "/metrics.json")

    # ---- run.json ----
    scripts = {rel(HERE + "/" + f): sha(HERE + "/" + f) for f in sorted(os.listdir(HERE)) if f.endswith(".py")}
    build = {}
    for d in (CL, CL + "/fig", HNR, HNS, IND, REC):
        for f in sorted(os.listdir(d)):
            p = d + "/" + f
            if os.path.isfile(p):
                build[rel(p)] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    ev = {f: {"sha256": sha(EV + "/" + f), "bytes": os.path.getsize(EV + "/" + f)} for f in sorted(os.listdir(EV)) if f != "run.json"}
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    run = {
        "schema": "GreatWave.DS33.run/1", "number": "設計33", "generated_utc": now,
        "machine": platform.platform(), "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
        "ffmpeg": ffv,
        "commands": cr["commands"] + [
            "py -3.10 -B Tools/GWWaveGen/ds33/ds33_harness.py --selftest（測定器の自己試験。約 5 分）",
            "py -3.10 -B Tools/GWWaveGen/ds33/ds33_harness_claws.py（測定器で爪の部の出力を測る。約 4 分）",
            "（進行役の独立の検査：リポジトリの外の numpy。コードと出力の写しは Unity/Build/Design/33/indep_check/）",
            "（記録）py -3.10 -B Tools/GWWaveGen/ds33/ds33_record.py",
        ],
        "scripts": scripts,
        "scripts_at_claws_run": cr["generators"],
        "harness_tool_at_run": hr["tool_sha256"],
        "inputs": cr["inputs"],
        "harness_inputs_sha256": {rel(k) if k.startswith(REPO) else k: v for k, v in hr["inputs_sha256"].items()},
        "claw_analysis_readme_ja": "爪形分析の README（Q8 の例外の 1 ファイル）は爪の部が数値（96 本の中央値と四分位）だけを写した。SHA-256 は inputs の claw_readme。"
                                   "爪形分析のフォルダーの画像・マスクは、どの部も開いていない",
        "frames_sha256": frames_sha,
        "build_outputs": build,
        "evidence": ev,
        "evidence_sources": {"png": pngs, "mp4": video, "json": copied},
        "not_in_repo_ja": "Unity/Build/Design/33/ の全部（爪の部の出力、測定器の出力、進行役の独立の検査の写し、記録の数え）は Git 対象外。"
                          "頂点のコマの表 ds33_claw_frames_f32.bin（126,562,704 バイト）は、生成器・入力・SHA-256 で再現する",
        "not_used_ja": "参照モデル、利用者の解算、写真のフォルダー、爪形分析のフォルダーの画像とマスク、禁止の場所、Unity、Blender、Houdini、git の操作",
    }
    jdump(run, EV + "/run.json")
    print("記録を書いた:", EV)
    print(json.dumps({"band_shape": {k: {kk: vv for kk, vv in sc[k].items() if kk != "top"} for k in ("width_axis_deg", "twist_deg", "turn_deg", "fold")},
                      "mp4": video["bytes"], "crf": crf_used, "pngs": len(pngs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
