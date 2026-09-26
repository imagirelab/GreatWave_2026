# -*- coding: utf-8 -*-
"""番号32：GPU 計時の修正・立体の代理・Mock の両眼・性能の初回測定の集計。

入力（Git 対象外）：Unity/Build/ArtFirst/32/ の af32_build_report.json、af32_spi_compile.json、runs/<tag>/ の
  af32_<tag>.json（Release プレイヤーが FrameTimingManager で取った生の値）と af32_<tag>_external.json（Windows の GPU カウンターと nvidia-smi）。
出力：Docs/Evidence/ArtFirst/32/ の metrics.json・run.json・PNG（1920×1080）。

使い方（リポジトリ根で）：
  py -3.10 Tools/Perf32/af32_analyze.py
"""
import datetime
import hashlib
import json
import math
import os
import platform
import sys

import cv2
import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "32")
RUNS = os.path.join(BUILD, "runs")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "32")
PERF_TAGS = ["run1", "run2", "run3"]      # 正式な測定（見えるウィンドウ、各条件 15 秒）
HIDDEN_TAGS = ["hidden1"]                 # 診断：-WindowStyle Hidden（番号20 の条件の再現）
MOCK_TAGS = ["mock1", "mock2"]            # OpenXR Mock Runtime
PRETEST_TAGS = ["test1", "mocktest1"]     # 作る途中の試し（集計に使わない。記録だけ）
DROP_FIRST = 8                            # FrameTiming は数フレーム遅れるので各窓の先頭 8 件を除く（番号20 と同じ）
LINE_RGB = (71, 80, 95)                   # AF28_Outline.mat の _LineColor (0.2784, 0.3137, 0.3725) × 255
LINE_TOL = 10.0                           # 線の画素とみなす RGB 距離（Mock の眼のテクスチャは MSAA なし）
BUDGET_VR_MS = 8.9                        # 作業計画 4.0：Quest 3＋Link、90 Hz の p95 予算
FRAME_90HZ_MS = 1000.0 / 90.0
DESK_MS = 33.3                            # バックログ 81/112
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"
COND_JA = {
    "desk1080_painting": "1920×1080・原画視点",
    "desk1080_seat_right": "1920×1080・右船の座席",
    "desk1080_seat_right_vsync": "1920×1080・右船の座席・垂直同期",
    "proxy_stereo_seat_right": "立体の代理 2×(2064×2208, 4×MSAA)・右船の座席",
}


def r4(v, n=4):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        return str(v)
    return round(v, n)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else None


def parse_utc(s):
    # 例 2026-09-26T04:57:51.9456628Z（7 桁の小数を 6 桁に丸める）
    s = s.rstrip("Z")
    if "." in s:
        a, b = s.split(".")
        s = a + "." + (b + "000000")[:6]
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc).timestamp()


# ---------------------------------------------------------------------------------------------- 外部カウンター
def ext_series(ext):
    """外部の標本を (時刻 s, 3D エンジンの Running Time 秒, 専用メモリ MiB, nvidia-smi MiB) の列にする。"""
    rows = []
    for s in ext["samples"]:
        c = s.get("counters") or {}
        rt = [v for k, v in c.items() if "running time" in k.lower()]
        ded = [v for k, v in c.items() if "dedicated usage" in k.lower()]
        smi = (s.get("smi") or {}).get("memUsedMiB")
        rows.append((parse_utc(s["utc"]), sum(rt) * 1e-7 if rt else None, sum(ded) / 1048576.0 if ded else None, smi))
    return rows


EXT_LAG_S = 1.0      # 標本の時刻は Get-Counter を呼ぶ前に取った。値は約 1 秒後（呼び出しの終わり）のもの（run1 で、眼の RT を作った時刻より前の時刻の標本に専用メモリの増加が出たことから）
EXT_MARGIN_S = 0.5   # 窓の両端から除く余白


def ext_window(rows, t0, t1):
    """窓 [t0, t1] の中の標本から、GPU の使用率（Running Time の増分 ÷ 経過）と専用メモリの最大を出す。"""
    inside = [(r[0] + EXT_LAG_S,) + tuple(r[1:]) for r in rows if r[1] is not None]
    inside = [r for r in inside if t0 + EXT_MARGIN_S <= r[0] <= t1 - EXT_MARGIN_S]
    out = {"n_samples": len(inside)}
    if len(inside) >= 2:
        dt = inside[-1][0] - inside[0][0]
        drt = inside[-1][1] - inside[0][1]
        out["gpu_busy_fraction"] = r4(drt / dt) if dt > 0 else None
    ded = [r[2] for r in inside if r[2] is not None]
    smi = [r[3] for r in inside if r[3] is not None]
    out["dedicated_mib_max"] = r4(max(ded), 1) if ded else None
    out["nvidia_smi_used_mib_max"] = r4(max(smi), 0) if smi else None
    return out


# ---------------------------------------------------------------------------------------------- 条件ごとの集計
def cond_stats(c, ext_rows, idle_smi):
    gpu = np.array(c["ftGpu"], dtype=float)[DROP_FIRST:]
    cpu = np.array(c["ftCpu"], dtype=float)[DROP_FIRST:]
    start = np.array(c["ftStart"], dtype=np.int64)[DROP_FIRST:]
    order = np.argsort(start, kind="stable")
    start = start[order]
    gpu, cpu = gpu[order], cpu[order]
    freq = float(c["cpuTimerFrequency"])
    iv = np.diff(start).astype(float) / freq * 1000.0      # フレーム開始の間隔（ms）＝提示のループの周期
    valid = np.isfinite(gpu) & (gpu > 0)
    g = gpu[valid]
    dt = np.array(c["dt"], dtype=float) * 1000.0
    s = {
        "name": c["name"], "name_ja": COND_JA.get(c["name"], c["name"]), "note_ja": c["noteJa"],
        "screen": [c["screenWidth"], c["screenHeight"]], "vsync_count": c["vSyncCount"], "quality_msaa": c["qualityMsaa"],
        "eye": [c["eyeWidth"], c["eyeHeight"], c["eyeMsaa"]] if c["stereoProxy"] else None,
        "frame_timing_enabled": c["frameTimingEnabled"], "vsyncs_per_second": c["vsyncsPerSecond"],
        "window_utc": [c["startUtc"], c["endUtc"]], "measure_s": r4(c["measureSeconds"], 3), "unity_frames": c["unityFramesInWindow"],
        "timings_total": int(len(c["ftGpu"])), "timings_used": int(len(gpu)), "dropped_first": DROP_FIRST,
        "gpu_valid": int(valid.sum()), "gpu_zero": int((gpu == 0).sum()), "gpu_valid_fraction": r4(valid.mean() if len(gpu) else 0),
        "gpu_ms": {"mean": r4(g.mean()) if len(g) else None, "p50": r4(pct(g, 50)), "p95": r4(pct(g, 95)), "p99": r4(pct(g, 99)), "max": r4(g.max()) if len(g) else None},
        "cpu_ms": {"mean": r4(cpu.mean()) if len(cpu) else None, "p95": r4(pct(cpu, 95)), "max": r4(cpu.max()) if len(cpu) else None},
        "interval_ms": {"mean": r4(iv.mean()) if len(iv) else None, "p50": r4(pct(iv, 50)), "p95": r4(pct(iv, 95)), "p99": r4(pct(iv, 99)), "max": r4(iv.max()) if len(iv) else None},
        "fps_mean": r4(1000.0 / iv.mean(), 2) if len(iv) else None,
        "fps_unity_frames": r4(c["unityFramesInWindow"] / c["measureSeconds"], 2),
        "dt_ms_mean": r4(dt.mean()) if len(dt) else None,
        "frames_over_33_3ms": int((iv > DESK_MS).sum()),
        "frames_over_33_3ms_fraction": r4((iv > DESK_MS).mean() if len(iv) else 0, 6),
    }
    if c["vSyncCount"] > 0 and c["vsyncsPerSecond"] > 0:
        per = 1000.0 / c["vsyncsPerSecond"]
        s["vsync_period_ms"] = r4(per)
        s["missed_vsync_frames"] = int((iv > 1.5 * per).sum())
        s["missed_vsync_fraction"] = r4((iv > 1.5 * per).mean() if len(iv) else 0, 6)
        s["gpu_ms_note_ja"] = "垂直同期ありでは、FrameTiming の GPU 時間が提示の待ちを含む（間隔とほぼ同じになる）。GPU の負荷は垂直同期なしの条件で読む。"
    if c["stereoProxy"]:
        s["gpu_over_8_9ms"] = int((g > BUDGET_VR_MS).sum())
        s["gpu_over_11_1ms"] = int((g > FRAME_90HZ_MS).sum())
    rec = np.array(c.get("recGpu") or [], dtype=float)
    if len(rec):
        rv = rec[rec > 0] / 1e6
        s["profiler_recorder_gpu"] = {"name": c.get("recGpuName"), "unit": c.get("recGpuUnit"), "valid": int(len(rv)), "total": int(len(rec)),
                                      "mean_ms": r4(rv.mean()) if len(rv) else None, "p95_ms": r4(pct(rv, 95))}
    mem = dict(zip(c.get("memNames") or [], c.get("memValues") or []))
    s["unity_memory_recorders_bytes_at_end"] = {k: (None if (isinstance(v, float) and math.isnan(v)) else int(v)) for k, v in mem.items()}
    w = ext_window(ext_rows, parse_utc(c["startUtc"]), parse_utc(c["endUtc"]))
    if w.get("gpu_busy_fraction") is not None and s["interval_ms"]["mean"]:
        w["gpu_ms_per_frame_from_busy"] = r4(w["gpu_busy_fraction"] * s["interval_ms"]["mean"])
    if w.get("nvidia_smi_used_mib_max") is not None and idle_smi is not None:
        w["nvidia_smi_delta_vs_idle_mib"] = r4(w["nvidia_smi_used_mib_max"] - idle_smi, 0)
    s["external"] = w
    return s


def load_run(tag):
    d = os.path.join(RUNS, tag)
    j = load(os.path.join(d, "af32_" + tag + ".json"))
    e = load(os.path.join(d, "af32_" + tag + "_external.json"))
    rows = ext_series(e)
    idle = [x["smi"]["memUsedMiB"] for x in e["idle"] if x.get("smi")]
    idle_smi = float(np.median(idle)) if idle else None
    return j, e, rows, idle_smi


# ---------------------------------------------------------------------------------------------- Mock の両眼
def t_range(P, axis):
    """Unity の射影行列（列優先 16）から、眼の視野の正接の範囲を出す。ndc = P_aa·t − P_a2。"""
    if axis == "x":
        a, b = P[0], P[8]
    else:
        a, b = P[5], P[9]
    return ((-1 + b) / a, (1 + b) / a), a, b


def mock_eyes(tag, j):
    m = j["mock"]
    d = os.path.join(RUNS, tag)
    L = np.asarray(Image.open(os.path.join(d, m["commandBufferImages"][0])).convert("RGB"))[::-1].copy()   # D3D の行の向きを直して上を上にする
    R = np.asarray(Image.open(os.path.join(d, m["commandBufferImages"][1])).convert("RGB"))[::-1].copy()
    H, W = L.shape[:2]
    (lx, ax_l, bx_l), (rx, ax_r, bx_r) = t_range(m["projLeft"], "x"), t_range(m["projRight"], "x")
    (ly, ay_l, by_l), (ry, ay_r, by_r) = t_range(m["projLeft"], "y"), t_range(m["projRight"], "y")
    tx = (max(lx[0], rx[0]), min(lx[1], rx[1]))
    ty = (max(ly[0], ry[0]), min(ly[1], ry[1]))

    def crop_box(ax, bx, ay, by):
        x0 = ((ax * tx[0] - bx) + 1) / 2 * W
        x1 = ((ax * tx[1] - bx) + 1) / 2 * W
        y0 = (1 - (ay * ty[1] - by)) / 2 * H     # 上端（正接が大きい側）
        y1 = (1 - (ay * ty[0] - by)) / 2 * H
        return [int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))]

    bl, br = crop_box(ax_l, bx_l, ay_l, by_l), crop_box(ax_r, bx_r, ay_r, by_r)
    cl = L[bl[1]:bl[3], bl[0]:bl[2]]
    cr = R[br[1]:br[3], br[0]:br[2]]
    h, w = min(cl.shape[0], cr.shape[0]), min(cl.shape[1], cr.shape[1])
    cl = cv2.resize(cl, (w, h), interpolation=cv2.INTER_NEAREST)
    cr = cv2.resize(cr, (w, h), interpolation=cv2.INTER_NEAREST)
    unmasked = (cl.sum(2) > 0) & (cr.sum(2) > 0)          # 両眼とも見えない域（Mock の隠し領域＝黒）を除く

    def line(img):
        return np.sqrt(((img.astype(float) - np.array(LINE_RGB)) ** 2).sum(2)) <= LINE_TOL

    ll, lr = line(cl) & unmasked, line(cr) & unmasked
    nl, nr = int(ll.sum()), int(lr.sum())
    diff = abs(nl - nr) / max(nl, nr) * 100 if max(nl, nr) > 0 else None
    full_l = int(line(L).sum())
    full_r = int(line(R).sum())
    # 色区（NPR v1 の調色板）の画素も両眼で数える（主役波が両眼に出ているかの確認）
    pal = {"white": (248, 243, 223), "mizuiro": (198, 215, 203), "ai_mid": (44, 105, 147), "ai_dark": (35, 64, 97)}
    pal_counts = {k: [int(((np.sqrt(((img.astype(float) - np.array(v)) ** 2).sum(2)) <= 6) & unmasked).sum()) for img in (cl, cr)] for k, v in pal.items()}
    mad = float(np.abs(cl.astype(float) - cr.astype(float))[unmasked].mean())
    return {
        "runtime": [m["runtimeName"], m["runtimeVersion"], m["runtimeApiVersion"]], "plugin": m["pluginVersion"],
        "loader": m["activeLoader"], "xr_enabled": m["xrEnabled"], "device_active": m["deviceActive"], "stereo_mode": m["stereoRenderingMode"],
        "eye_texture": [m["eyeTextureWidth"], m["eyeTextureHeight"], m["eyeTextureMsaa"], m["eyeTextureDimension"], m["eyeTextureVolumeDepth"]],
        "texture_layout": m["displayTextureLayout"], "render_passes": m["renderPasses"],
        "ipd_m_from_view": r4(abs(m["viewLeft"][12] - m["viewRight"][12]), 5),
        "tan_x_left": [r4(x) for x in lx], "tan_x_right": [r4(x) for x in rx], "tan_common_x": [r4(x) for x in tx], "tan_common_y": [r4(x) for x in ty],
        "crop_left_px": bl, "crop_right_px": br, "compared_size_px": [w, h], "unmasked_px": int(unmasked.sum()),
        "line_px_left": nl, "line_px_right": nr, "line_px_diff_percent": r4(diff, 3),
        "line_px_full_image": [full_l, full_r], "palette_px_common": pal_counts, "mean_abs_diff_rgb_common": r4(mad, 3),
        "_images": (L, R, bl, br, ll, lr),
    }


# ---------------------------------------------------------------------------------------------- 図
def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def fit_text(dr, xy, text, maxw, size, bold, fill):
    s = size
    while s > 12 and dr.textlength(text, font=font(s, bold)) > maxw:
        s -= 1
    dr.text((xy[0], xy[1] + (size - s) // 2), text, font=font(s, bold), fill=fill)


def banner(im, lines, y=1080 - 40, size=22):
    dr = ImageDraw.Draw(im)
    h = (size + 10) * len(lines) + 10
    dr.rectangle([0, 1080 - h, 1920, 1080], fill=(20, 20, 24))
    for i, s in enumerate(lines):
        dr.text((20, 1080 - h + 8 + i * (size + 10)), s, font=font(size), fill=(240, 240, 240))
    return im


def save_png(im, path):
    im.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)


def fig_screens(run_dir, tag, j, path):
    """Release プレイヤーの見えるウィンドウから撮った 1920×1080 の画面（原画視点と右船の座席）を並べる。"""
    a = Image.open(os.path.join(run_dir, "af32_%s_desk1080_painting.png" % tag)).convert("RGB")
    b = Image.open(os.path.join(run_dir, "af32_%s_desk1080_seat_right.png" % tag)).convert("RGB")
    im = Image.new("RGB", (1920, 1080), (20, 20, 24))
    im.paste(a.resize((950, 534), Image.LANCZOS), (6, 120))
    im.paste(b.resize((950, 534), Image.LANCZOS), (964, 120))
    dr = ImageDraw.Draw(im)
    dr.text((20, 20), "番号32：Release プレイヤー（Development でない）の見えるウィンドウ 1920×1080 で測った画面（%s、各条件の測定の直後に撮影）" % tag, font=font(28, True), fill=(240, 240, 240))
    dr.text((20, 66), "主役波＝番号26 の K* 45°＋番号28 の NPR v1・外殻線 v0、背景＝番号27（CP1 の合成シーン AF_CP1 を複製）。静止した終態で、形成の動き（番号30）は入っていない。", font=font(20), fill=(210, 210, 210))
    dr.text((20, 666), "原画視点（PaintingCam v1）", font=font(22, True), fill=(240, 240, 240))
    dr.text((978, 666), "右船の座席（CP1 の候補 (a)＝D7 の決定。27修正01 の座席ではない）", font=font(22, True), fill=(240, 240, 240))
    lines = ["%s / %s / %s / 画面 %d×%d・%s / 品質 %s・MSAA 4 / FrameTiming %s" % (j["device"], j["graphicsApi"], j["cpu"].strip(), j["screenWidth"], j["screenHeight"], j["fullScreenMode"], j["qualityName"], "有効" if j["frameTimingFeatureEnabled"] else "無効"),
             "PC のデスクトップ表示の証拠で、HMD 実機ではない。性能の値は RTX3080 での代理測定（RTX3060 の対象 PC での合格ではない）。"]
    y = 710
    for s in lines:
        dr.text((20, y), s, font=font(20), fill=(220, 220, 220))
        y += 34
    save_png(im, path)


def fig_proxy(run_dir, tag, path):
    L = Image.open(os.path.join(run_dir, "af32_%s_proxy_stereo_seat_right_L.png" % tag)).convert("RGB")
    R = Image.open(os.path.join(run_dir, "af32_%s_proxy_stereo_seat_right_R.png" % tag)).convert("RGB")
    im = Image.new("RGB", (1920, 1080), (20, 20, 24))
    h = 900
    w = int(round(L.width * h / L.height))
    im.paste(L.resize((w, h), Image.LANCZOS), (960 - w - 6, 90))
    im.paste(R.resize((w, h), Image.LANCZOS), (966, 90))
    dr = ImageDraw.Draw(im)
    dr.text((20, 20), "番号32：立体の代理（左右の眼カメラ、各 2064×2208・4×MSAA の RT、IPD 64 mm・縦画角 96°、右船の座席）。Release プレイヤーの実描画（%s）" % tag, font=font(24, True), fill=(240, 240, 240))
    dr.text((20, 54), "SPI ではなく 2 台のカメラで描いた代理。Quest 3 の実 runtime・Link の圧縮・合成器・レンズの歪みは入っていない。左＝左眼、右＝右眼（縮小）。", font=font(18), fill=(210, 210, 210))
    save_png(im, path)


def fig_mock(res, tag, path):
    L, R, bl, br, ll, lr = res["_images"]
    im = Image.new("RGB", (1920, 1080), (20, 20, 24))
    h = 860
    w = int(round(L.shape[1] * h / L.shape[0]))
    sc = h / L.shape[0]
    xs = [960 - w - 10, 970]
    for k, (img, box, x0) in enumerate(((L, bl, xs[0]), (R, br, xs[1]))):
        im.paste(Image.fromarray(img).resize((w, h), Image.LANCZOS), (x0, 110))
        dr = ImageDraw.Draw(im)
        dr.rectangle([x0 + box[0] * sc, 110 + box[1] * sc, x0 + box[2] * sc, 110 + box[3] * sc], outline=(230, 40, 40), width=3)
    dr = ImageDraw.Draw(im)
    dr.text((20, 16), "番号32：OpenXR Mock Runtime（導入済み com.unity.xr.openxr 1.16.1 の同梱品）で、SPI の眼のテクスチャ配列の 2 枚を読み出した（%s）" % tag, font=font(24, True), fill=(240, 240, 240))
    dr.text((20, 52), "runtime：%s %s／%s／眼 %d×%d・MSAA %d・%s／IPD %.3f m（Mock の既定）。黒い縁は Mock の隠し領域。赤枠＝両眼に共通の視野（比較の範囲）。上下は D3D の行の向きを直して表示。" %
            (res["runtime"][0], res["runtime"][1], res["stereo_mode"], res["eye_texture"][0], res["eye_texture"][1], res["eye_texture"][2], res["eye_texture"][3], res["ipd_m_from_view"]), font=font(17), fill=(210, 210, 210))
    dr.text((20, 80), "外殻線の画素（RGB 71,80,95 から距離 ≤%g）：左眼 %d、右眼 %d、差 %.2f %%（受入 <10 %%）。HMD のレンズ越しの見え方ではない。" % (LINE_TOL, res["line_px_left"], res["line_px_right"], res["line_px_diff_percent"]), font=font(17), fill=(240, 220, 120))
    dr.text((xs[0], 980), "左眼（配列のスライス 0）", font=font(22, True), fill=(240, 240, 240))
    dr.text((xs[1], 980), "右眼（配列のスライス 1）", font=font(22, True), fill=(240, 240, 240))
    save_png(im, path)


def fig_table(path, rows, title, subtitle):
    COLORS = {"pass": (46, 125, 50), "fail": (183, 28, 28), "record": (97, 97, 97), "unstarted": (120, 120, 160), "unverified": (90, 60, 130), "pass-proxy": (0, 105, 120)}
    W_, H_ = 1920, 1080
    im = Image.new("RGB", (W_, H_), (250, 248, 242))
    dr = ImageDraw.Draw(im)
    dr.text((30, 18), title, font=font(28, True), fill=(20, 20, 20))
    dr.text((30, 58), subtitle, font=font(17), fill=(60, 60, 60))
    cols = [(30, "項目"), (290, "内容"), (760, "値"), (1270, "判定"), (1440, "備考")]
    y = 96
    fh = 19
    n_rows = len(rows) + len({r["group"] for r in rows})
    lh = max(26, min(40, (H_ - y - 20) // max(1, n_rows + 1)))
    for x, t in cols:
        dr.text((x, y), t, font=font(fh, True), fill=(20, 20, 20))
    y += lh
    dr.line([(24, y - 4), (W_ - 24, y - 4)], fill=(120, 120, 120), width=1)
    cur = None
    for r in rows:
        if r["group"] != cur:
            cur = r["group"]
            dr.rectangle([24, y - 2, W_ - 24, y + lh - 6], fill=(228, 224, 212))
            dr.text((30, y), cur, font=font(fh, True), fill=(30, 30, 30))
            y += lh
        fit_text(dr, (30, y), r["item"], 250, fh, False, (20, 20, 20))
        fit_text(dr, (290, y), r["name"], 460, fh, False, (20, 20, 20))
        fit_text(dr, (760, y), r["value"], 500, fh, False, (20, 20, 20))
        c = COLORS[r["verdict"]]
        dr.rounded_rectangle([1266, y - 1, 1266 + 165, y + lh - 9], radius=5, fill=c)
        fit_text(dr, (1274, y), r["verdict_ja"], 150, fh, True, (255, 255, 255))
        fit_text(dr, (1440, y), r["note"], W_ - 30 - 1440, fh - 2, False, (50, 50, 50))
        y += lh
    save_png(im, path)


# ---------------------------------------------------------------------------------------------- 本体
def med(vals):
    v = [x for x in vals if x is not None]
    return r4(float(np.median(v))) if v else None


def main():
    os.makedirs(EVID, exist_ok=True)
    build = load(os.path.join(BUILD, "af32_build_report.json"))
    spi = load(os.path.join(BUILD, "af32_spi_compile.json"))

    runs = {}
    raw_inputs = {}
    for tag in PERF_TAGS + HIDDEN_TAGS + MOCK_TAGS:
        j, e, rows, idle = load_run(tag)
        runs[tag] = (j, e, rows, idle)
        for fn in ("af32_%s.json" % tag, "af32_%s_external.json" % tag):
            raw_inputs["Unity/Build/ArtFirst/32/runs/%s/%s" % (tag, fn)] = sha(os.path.join(RUNS, tag, fn))

    # 条件ごと（3 回）
    per_run = {}
    for tag in PERF_TAGS + HIDDEN_TAGS:
        j, e, rows, idle = runs[tag]
        per_run[tag] = {
            "exit_code": e["exitCode"], "hidden_window": e["hiddenWindow"], "is_debug_build": j["isDebugBuild"],
            "frame_timing_feature_enabled": j["frameTimingFeatureEnabled"], "screen": [j["screenWidth"], j["screenHeight"]], "full_screen_mode": j["fullScreenMode"],
            "display_refresh_hz_unity": j["refreshRate"], "desktop_resolution": [j["currentResWidth"], j["currentResHeight"]],
            "window_handle_nonzero_samples": sum(1 for w in e["window"] if w["hwnd"] != 0), "window_samples": len(e["window"]),
            "idle_nvidia_smi_used_mib": idle, "data_sha256": dict(zip(j["dataFiles"], j["dataSha256"])),
            "unity_memory_after_load_bytes": {k: (None if (isinstance(v, float) and math.isnan(v)) else int(v)) for k, v in zip(j.get("memAfterLoadNames") or [], j.get("memAfterLoadValues") or [])},
            "conditions": {c["name"]: cond_stats(c, rows, idle) for c in j["conditions"]},
        }

    names = list(per_run[PERF_TAGS[0]]["conditions"].keys())
    agg = {}
    for n in names:
        cs = [per_run[t]["conditions"][n] for t in PERF_TAGS]
        agg[n] = {
            "name_ja": cs[0]["name_ja"],
            "gpu_valid_total": sum(c["gpu_valid"] for c in cs), "timings_used_total": sum(c["timings_used"] for c in cs),
            "gpu_ms_mean_median_of_runs": med([c["gpu_ms"]["mean"] for c in cs]), "gpu_ms_p95_median_of_runs": med([c["gpu_ms"]["p95"] for c in cs]),
            "gpu_ms_p95_max_of_runs": r4(max(c["gpu_ms"]["p95"] for c in cs)), "gpu_ms_max_of_runs": r4(max(c["gpu_ms"]["max"] for c in cs)),
            "cpu_ms_mean_median_of_runs": med([c["cpu_ms"]["mean"] for c in cs]), "cpu_ms_p95_median_of_runs": med([c["cpu_ms"]["p95"] for c in cs]),
            "fps_mean_min_of_runs": r4(min(c["fps_mean"] for c in cs), 2), "fps_mean_median_of_runs": med([c["fps_mean"] for c in cs]),
            "interval_ms_p95_max_of_runs": r4(max(c["interval_ms"]["p95"] for c in cs)),
            "frames_over_33_3ms_total": sum(c["frames_over_33_3ms"] for c in cs),
            "gpu_ms_per_frame_from_busy_median": med([c["external"].get("gpu_ms_per_frame_from_busy") for c in cs]),
            "dedicated_mib_max": r4(max((c["external"].get("dedicated_mib_max") or 0) for c in cs), 1),
            "per_run_gpu_ms_p95": [c["gpu_ms"]["p95"] for c in cs], "per_run_fps_mean": [c["fps_mean"] for c in cs],
        }
        if "missed_vsync_frames" in cs[0]:
            agg[n]["missed_vsync_frames_total"] = sum(c["missed_vsync_frames"] for c in cs)
            agg[n]["vsync_period_ms"] = cs[0]["vsync_period_ms"]
        if "gpu_over_8_9ms" in cs[0]:
            agg[n]["gpu_over_8_9ms_total"] = sum(c["gpu_over_8_9ms"] for c in cs)
            agg[n]["gpu_over_11_1ms_total"] = sum(c["gpu_over_11_1ms"] for c in cs)

    # Mock
    mock = {}
    for tag in MOCK_TAGS:
        j, e, rows, idle = runs[tag]
        res = mock_eyes(tag, j)
        m = j["mock"]
        w = ext_window(rows, parse_utc(m["spiStartUtc"]), parse_utc(m["spiEndUtc"]))
        frame_ms = m["spiSeconds"] / m["spiFrames"] * 1000.0
        if w.get("gpu_busy_fraction") is not None:
            w["gpu_ms_per_frame_from_busy"] = r4(w["gpu_busy_fraction"] * frame_ms)
        res["spi_window"] = {"eye": [m["spiEyeWidth"], m["spiEyeHeight"]], "scale": r4(m["spiScale"]), "frames": m["spiFrames"], "seconds": r4(m["spiSeconds"], 3),
                             "frame_interval_ms_mean": r4(frame_ms), "external": w,
                             "app_gpu_time_from_mock_nonzero": int(sum(1 for x in m["appGpuTimes"] if x > 0)), "app_gpu_time_samples": len(m["appGpuTimes"]),
                             "note_ja": "SPI の経路（Mock、眼 2064 幅、MSAA 1）の GPU 時間を、Windows の GPU Engine（3D）の Running Time の増分から割り出した値。FrameTiming の GPU は XR の経路で 0 になり使えなかった。"}
        ft = np.array(m["ftGpu"], dtype=float)
        res["frame_timing_under_xr"] = {"timings": int(len(ft)), "gpu_valid": int((ft > 0).sum()), "note_ja": "記録のみ。Mock の XR の経路では FrameTiming の GPU の有効値が %d 件。" % int((ft > 0).sum())}
        res["notes"] = m["notes"]
        mock[tag] = res
        if tag == MOCK_TAGS[0]:
            fig_mock(res, tag, os.path.join(EVID, "32_mock_eyes.png"))

    # 図
    fig_screens(os.path.join(RUNS, PERF_TAGS[0]), PERF_TAGS[0], runs[PERF_TAGS[0]][0], os.path.join(EVID, "32_desk_views.png"))
    fig_proxy(os.path.join(RUNS, PERF_TAGS[0]), PERF_TAGS[0], os.path.join(EVID, "32_proxy_stereo.png"))

    # ------------------------------------------------------------------ 判定
    gpu_valid_total = sum(agg[n]["gpu_valid_total"] for n in names)
    hid = per_run[HIDDEN_TAGS[0]]["conditions"]["desk1080_seat_right"]
    desk = [n for n in names if n.startswith("desk1080")]
    desk_ok = all(agg[n]["fps_mean_min_of_runs"] >= 30 and agg[n]["interval_ms_p95_max_of_runs"] <= DESK_MS for n in desk)
    px = agg["proxy_stereo_seat_right"]
    proxy_ok = px["gpu_ms_p95_max_of_runs"] <= BUDGET_VR_MS
    mock_diffs = [mock[t]["line_px_diff_percent"] for t in MOCK_TAGS]
    mock_ok = all(d is not None and d < 10 for d in mock_diffs)
    hero_shaders = [p for p in build["sceneShaders"] if p.endswith(".shader")]
    hero_names = []
    for s in spi["shaders"]:
        if s["path"] in hero_shaders:
            hero_names.append(s["shader"])
    stereo_by_shader = {}
    for p in spi["passes"]:
        if p["hasStage"] and p["stage"] == "Vertex" and p["keywords"].startswith("STEREO"):
            stereo_by_shader.setdefault(p["shader"], []).append(p["rtArrayIndexInOutput"])
    stereo_by_shader = {k: all(v) for k, v in stereo_by_shader.items()}
    hero_spi_ok = all(stereo_by_shader.get(n, False) for n in hero_names)
    af_render = [s["shader"] for s in spi["shaders"] if "/ArtFirst/" in s["shader"] and not s["shader"].startswith("Hidden/")]
    no_spi = sorted(k for k, v in stereo_by_shader.items() if not v)

    items = {
        "gpu_valid_samples": {"name_ja": "GPU の有効標本（FrameTimingManager、Release・見えるウィンドウ）", "criterion": "> 0（番号20 の L68 では 0 件）",
                              "value": {"valid": gpu_valid_total, "used_total": sum(agg[n]["timings_used_total"] for n in names),
                                        "by_condition": {n: [agg[n]["gpu_valid_total"], agg[n]["timings_used_total"]] for n in names},
                                        "hidden_window_diagnostic": {"tag": HIDDEN_TAGS[0], "valid": hid["gpu_valid"], "used": hid["timings_used"], "cpu_ms_mean": hid["cpu_ms"]["mean"],
                                                                     "fps_mean": hid["fps_mean"], "window_handle_nonzero_samples": per_run[HIDDEN_TAGS[0]]["window_handle_nonzero_samples"]}},
                              "verdict": "pass" if gpu_valid_total > 0 else "fail"},
        "81": {"name_ja": "前方の水面が上へ移る動き：1920×1080 で平均 ≥30 fps、95% ≤33.3 ms（RTX3080代測）", "criterion": "平均 ≥30 fps かつ 95% のフレーム ≤33.3 ms",
               "value": {n: {"fps_mean_min_of_runs": agg[n]["fps_mean_min_of_runs"], "interval_ms_p95_max_of_runs": agg[n]["interval_ms_p95_max_of_runs"], "frames_over_33_3ms_total": agg[n]["frames_over_33_3ms_total"]} for n in desk},
               "verdict_32": "pass-proxy" if desk_ok else "fail", "verdict": "unverified",
               "note_ja": "RTX3080代測。静止した終態 K* の画面で、形成の動き（番号30）は未実装。対象 PC（RTX3060）での合格ではないので、バックログの判定は未確認のまま。"},
        "112": {"name_ja": "延伸・下向きの動き：1920×1080 で平均 ≥30 fps、95% ≤33.3 ms（RTX3080代測）", "criterion": "同上",
                "value": "81 と同じ測定（静止した K*）", "verdict_32": "pass-proxy" if desk_ok else "fail", "verdict": "unverified",
                "note_ja": "81 と同じ理由で、バックログの判定は未確認のまま。"},
        "proxy_gpu_p95": {"name_ja": "立体の代理の GPU p95（2×2064×2208・4×MSAA）", "criterion": "≤8.9 ms（作業計画 4.0 の 90 Hz 予算）",
                          "value": {"gpu_ms_p95_per_run": px["per_run_gpu_ms_p95"], "gpu_ms_p95_max_of_runs": px["gpu_ms_p95_max_of_runs"], "gpu_ms_mean_median": px["gpu_ms_mean_median_of_runs"],
                                    "gpu_ms_max_of_runs": px["gpu_ms_max_of_runs"], "gpu_over_8_9ms_total": px["gpu_over_8_9ms_total"], "gpu_over_11_1ms_total": px["gpu_over_11_1ms_total"],
                                    "external_gpu_ms_per_frame_median": px["gpu_ms_per_frame_from_busy_median"]},
                          "verdict": "pass" if proxy_ok else "fail",
                          "note_ja": "2 台のカメラによる代理（SPI ではない）。Link の約 1 ms・合成器・HMD の runtime は含まない。HMD 実機の 90 Hz の判定は番号34。"},
        "spi_compile": {"name_ja": "自作シェーダーの SPI コンパイル", "criterion": "全シェーダー・全パスが STEREO_INSTANCING_ON でコンパイルでき、主役波の場面で使うシェーダーの頂点出力に SV_RenderTargetArrayIndex がある",
                        "value": {"shaders": len(spi["shaders"]), "stage_checks": sum(1 for p in spi["passes"] if p["hasStage"]), "all_compiled": spi["allCompiled"],
                                  "hero_scene_shaders": hero_names, "hero_scene_stereo_output": hero_spi_ok, "art_first_render_shaders": af_render,
                                  "without_stereo_output": no_spi},
                        "verdict": "pass" if (spi["allCompiled"] and hero_spi_ok) else "fail",
                        "note_ja": "SV_RenderTargetArrayIndex がないのは、Editor 専用の焼き込み（AF28 Bake）と番号18 の比較用（Playback18）のシェーダーで、主役波の場面・プレイヤーでは使わない（記録）。"},
        "mock_line_diff": {"name_ja": "Mock の両眼で外殻線の画素数の差", "criterion": "<10 %（両眼に共通の視野、隠し領域を除く）",
                           "value": {t: {"left": mock[t]["line_px_left"], "right": mock[t]["line_px_right"], "diff_percent": mock[t]["line_px_diff_percent"]} for t in MOCK_TAGS},
                           "verdict": "pass" if mock_ok else "fail",
                           "note_ja": "Mock Runtime の既定（眼 1512×1680、IPD 22 mm、左右で非対称の画角、MSAA 1）。HMD のレンズ越しの見え方ではなく、H3 の代わりにしない。"},
        "memory": {"name_ja": "GPU メモリの実測（プロセスの専用メモリ）", "criterion": "keypose ≤512 MiB（keypose がある場合）",
                   "value": {"dedicated_mib_max_desktop": max(agg[n]["dedicated_mib_max"] for n in desk), "dedicated_mib_max_proxy": px["dedicated_mib_max"],
                             "sdf_texture_bytes": runs[PERF_TAGS[0]][0]["sdfTextureBytes"], "wave_vertices": runs[PERF_TAGS[0]][0]["waveVertexCount"],
                             "keypose_estimate_mib_plan_format": r4(181 * 80000 * (8 + 4) / 1048576.0, 1),
                             "keypose_estimate_note_ja": "計画の書式（位置 RGBA64＝8 B、法線 RG16＝4 B、15 Hz で 181 層、8 万頂点）での見積りで、実測ではない（適応的に密にする層は含まない）。"},
                   "verdict": "unstarted",
                   "note_ja": "keypose は番号30 で作る（まだない）ので、≤512 MiB は未判定。今の主役波の資産（色区テクスチャ 64 MiB）を含むプロセスの専用メモリだけ実測した。"},
    }

    summary = {k: v["verdict"] for k, v in items.items()}
    metrics = {
        "schema": "GreatWave.AF32.metrics/1", "number": "32",
        "evidence_kind_ja": "Unity 6000.4.3f1 の Release（Development でない）Windows プレイヤーを見えるウィンドウで動かした PC の実測（RTX 3080・D3D11）と、OpenXR Mock Runtime の両眼の読み出し。HMD 実機の結果ではない。",
        "hero_assets_ja": "番号26 の K*（45°、kstar_a45.gwb）＋番号28 の NPR v1・外殻線 v0（af28_uvsdf_a45.bin、af28_uvwarp_a45.json）＋番号27 の背景。CP1（370297c）で使ったものと SHA-256 が同じ複製を Unity/Build/ArtFirst/32/data/ に固定して読んだ。",
        "seat_ja": "右船の座席＝CP1 の候補 (a)（AF_CP1.unity の「CP1 座席候補 右船カメラ」）。D7 の決定に対応するが、27修正01 で作り直す座席とは違う可能性がある。",
        "build": {k: build[k] for k in ("buildResult", "buildOptions", "totalSize", "frameTimingStatsBefore", "frameTimingStatsDuringBuild", "frameTimingStatsRestored", "srcSceneMatchesCommitted", "protectedUnchanged", "sceneShaders")},
        "items": items, "summary_verdicts": summary,
        "conditions_aggregate": agg, "runs": per_run,
        "mock": {t: {k: v for k, v in mock[t].items() if not k.startswith("_")} for t in MOCK_TAGS},
        "stop_loss": {"triggered": False, "note_ja": "1 日以内に有効な GPU 値が取れたので、Profiler の GPU モジュール・PresentMon には替えていない（PresentMon は導入していない）。"},
        "figures": ["32_desk_views.png", "32_proxy_stereo.png", "32_mock_eyes.png", "32_metrics_table.png"],
    }

    # 表
    rows = []
    g = "1. GPU 計時（Release・見えるウィンドウ）"
    rows.append({"group": g, "item": "有効標本", "name": "FrameTiming の GPU の有効値（3 回 × 4 条件）", "value": "%d / %d 件" % (gpu_valid_total, items["gpu_valid_samples"]["value"]["used_total"]), "verdict": "pass" if gpu_valid_total > 0 else "fail", "verdict_ja": "合格" if gpu_valid_total > 0 else "不合格", "note": "番号20 は全 24 条件で 0 件"})
    rows.append({"group": g, "item": "診断", "name": "-WindowStyle Hidden で起動（番号20 の条件）", "value": "%d / %d 件（CPU 平均 %.3f ms）" % (hid["gpu_valid"], hid["timings_used"], hid["cpu_ms"]["mean"]), "verdict": "record", "verdict_ja": "記録のみ", "note": "隠したウィンドウでは GPU の値が 0 になることを再現"})
    g = "2. 1920×1080（81/112、RTX3080代測、静止した K*）"
    for n in desk:
        a = agg[n]
        v = "平均 %.0f fps（最小の回）、間隔 p95 %.2f ms、>33.3 ms %d 件" % (a["fps_mean_min_of_runs"], a["interval_ms_p95_max_of_runs"], a["frames_over_33_3ms_total"])
        note = "GPU p95 %.3f ms・CPU p95 %.3f ms（3 回の中央値）" % (a["gpu_ms_p95_median_of_runs"], a["cpu_ms_p95_median_of_runs"])
        if "missed_vsync_frames_total" in a:
            note = "表示 %.0f Hz、周期の 1.5 倍を超えた間隔 %d 件（3 回の計）" % (1000.0 / a["vsync_period_ms"], a["missed_vsync_frames_total"])
        rows.append({"group": g, "item": "81/112", "name": a["name_ja"], "value": v, "verdict": "pass-proxy" if desk_ok else "fail", "verdict_ja": "合格（代測）" if desk_ok else "不合格", "note": note})
    rows.append({"group": g, "item": "81/112", "name": "バックログの判定", "value": "対象 PC（RTX3060）・形成の動きがまだない", "verdict": "unverified", "verdict_ja": "未確認", "note": "32 の受入は RTX3080代測の表記で満たす"})
    g = "3. 立体の代理・SPI・Mock"
    rows.append({"group": g, "item": "代理 GPU p95", "name": "2×(2064×2208、4×MSAA)、右船の座席", "value": "p95 %.3f ms（3 回の最大）、最大 %.3f ms" % (px["gpu_ms_p95_max_of_runs"], px["gpu_ms_max_of_runs"]), "verdict": "pass" if proxy_ok else "fail", "verdict_ja": "合格" if proxy_ok else "不合格", "note": "予算 ≤8.9 ms。2 カメラの代理で、Link・合成器は含まない"})
    rows.append({"group": g, "item": "SPI コンパイル", "name": "自作シェーダー %d 本・%d 段" % (len(spi["shaders"]), items["spi_compile"]["value"]["stage_checks"]), "value": "全部コンパイル可、主役波の場面の 4 本は眼の出力あり", "verdict": items["spi_compile"]["verdict"], "verdict_ja": "合格" if items["spi_compile"]["verdict"] == "pass" else "不合格", "note": "眼の出力なし %d 本（Editor 専用の焼き込み・番号18 の比較用。場面で使わない）" % len(no_spi)})
    for t in MOCK_TAGS:
        rows.append({"group": g, "item": "Mock 線の差", "name": "両眼の外殻線の画素数（%s）" % t, "value": "左 %d・右 %d、差 %.2f %%" % (mock[t]["line_px_left"], mock[t]["line_px_right"], mock[t]["line_px_diff_percent"]), "verdict": "pass" if mock[t]["line_px_diff_percent"] < 10 else "fail", "verdict_ja": "合格" if mock[t]["line_px_diff_percent"] < 10 else "不合格", "note": "共通の視野・隠し領域を除く。HMD 実機ではない"})
    sw = mock[MOCK_TAGS[0]]["spi_window"]
    rows.append({"group": g, "item": "SPI の GPU", "name": "Mock の SPI 経路（眼 %d×%d、MSAA 1）" % tuple(sw["eye"]), "value": "約 %s ms/フレーム（GPU の稼働率から）" % sw["external"].get("gpu_ms_per_frame_from_busy"), "verdict": "record", "verdict_ja": "記録のみ", "note": "外部カウンターからの推定。FrameTiming は XR で 0"})
    g = "4. メモリ"
    rows.append({"group": g, "item": "専用メモリ", "name": "プロセスの GPU 専用メモリ（Windows のカウンター）", "value": "画面 %.0f MiB・代理 %.0f MiB（最大）" % (items["memory"]["value"]["dedicated_mib_max_desktop"], px["dedicated_mib_max"]), "verdict": "record", "verdict_ja": "記録のみ", "note": "代理は眼の RT（4×MSAA）を含む"})
    rows.append({"group": g, "item": "keypose", "name": "keypose ≤512 MiB", "value": "keypose がまだない（見積り %.0f MiB）" % items["memory"]["value"]["keypose_estimate_mib_plan_format"], "verdict": "unstarted", "verdict_ja": "未着手", "note": "番号30 の後に測る"})
    fig_table(os.path.join(EVID, "32_metrics_table.png"), rows, "番号32：GPU 計時の修正・立体の代理・Mock の両眼・性能の初回測定（数値表）",
              "Release（Development でない）Windows プレイヤー、見えるウィンドウ、RTX 3080・D3D11、各条件 助走 3 秒＋測定 15 秒 × 3 回。PC の実測で HMD 実機ではない。81/112 は RTX3080代測。")

    with open(os.path.join(EVID, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # run.json
    ins = {
        "Unity/Assets/GreatWave/ArtFirst/Scripts/AF32PerfRunner.cs": None, "Unity/Assets/GreatWave/ArtFirst/Editor/AF32PerfBuild.cs": None,
        "Unity/Assets/GreatWave/Scenes/Tests/AF32_Perf.unity": None, "Unity/Assets/GreatWave/Scenes/Tests/AF_CP1.unity": None,
        "Tools/Perf32/af32_run_unity.ps1": None, "Tools/Perf32/af32_run_player.ps1": None, "Tools/Perf32/af32_analyze.py": None,
        "Unity/Build/ArtFirst/32/data/kstar_a45.gwb": None, "Unity/Build/ArtFirst/32/data/af28_uvsdf_a45.bin": None, "Unity/Build/ArtFirst/32/data/af28_uvwarp_a45.json": None,
        "Unity/Build/ArtFirst/32/player/AF32Perf.exe": None, "Unity/Build/ArtFirst/32/player/AF32Perf_Data/level0": None,
        "Unity/Build/ArtFirst/32/player/AF32Perf_Data/Managed/Assembly-CSharp.dll": None, "Unity/Build/ArtFirst/32/player/AF32Perf_Data/globalgamemanagers": None,
        "Unity/Build/ArtFirst/32/af32_build_report.json": None, "Unity/Build/ArtFirst/32/af32_spi_compile.json": None,
    }
    for k in ins:
        ins[k] = sha(os.path.join(REPO, k.replace("/", os.sep)))
    ins.update(raw_inputs)
    outs = {}
    for fn in sorted(os.listdir(EVID)):
        if fn in ("run.json",):
            continue
        outs["Docs/Evidence/ArtFirst/32/" + fn] = sha(os.path.join(EVID, fn))
    run = {
        "schema": "GreatWave.AF32.run/1", "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF32PerfBuild.BuildAll -Log build2",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag run1   （run2・run3 も同じ）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag hidden1 -Hidden -Conds desk1080_seat_right -Warm 3 -Measure 5",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag mock1 -Mode mock   （mock2 も同じ）",
            "py -3.10 Tools/Perf32/af32_analyze.py",
        ],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": PIL.__version__, "unity": runs[PERF_TAGS[0]][0]["unity"],
                  "device": runs[PERF_TAGS[0]][0]["device"], "graphics_api": runs[PERF_TAGS[0]][0]["graphicsApi"], "cpu": runs[PERF_TAGS[0]][0]["cpu"].strip(),
                  "os": runs[PERF_TAGS[0]][0]["os"], "gpu_driver": runs[PERF_TAGS[0]][0]["deviceVersion"], "openxr_package": "com.unity.xr.openxr 1.16.1（導入済み。Mock Runtime はその同梱品）",
                  "external_counters": "Windows の GPU Engine / GPU Process Memory カウンター（Get-Counter）、nvidia-smi（ドライバーに同梱）。新しい導入なし"},
        "pretests_not_used": {t: "Unity/Build/ArtFirst/32/runs/%s/（作る途中の試し。集計に使わない）" % t for t in PRETEST_TAGS},
        "inputs_sha256": ins, "outputs_sha256": outs,
        "not_committed_ja": "Unity/Build/ArtFirst/32/ の下（プレイヤー約 100 MB、生の計時 JSON、各条件の画面、ログ）は既存の /Unity/Build/ の規則で Git 対象外。SHA-256 は上に記録した。",
    }
    with open(os.path.join(EVID, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("AF32_ANALYZE", json.dumps(summary, ensure_ascii=False))
    for n in names:
        a = agg[n]
        print(n, "gpu p95 med", a["gpu_ms_p95_median_of_runs"], "max", a["gpu_ms_p95_max_of_runs"], "fps min", a["fps_mean_min_of_runs"], "iv p95 max", a["interval_ms_p95_max_of_runs"],
              "ext gpu/frame", a["gpu_ms_per_frame_from_busy_median"], "ded", a["dedicated_mib_max"], "valid", a["gpu_valid_total"], "/", a["timings_used_total"])
    for t in MOCK_TAGS:
        print(t, mock[t]["line_px_left"], mock[t]["line_px_right"], mock[t]["line_px_diff_percent"], mock[t]["spi_window"])


if __name__ == "__main__":
    sys.exit(main())
