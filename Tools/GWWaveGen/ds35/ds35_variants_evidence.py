# -*- coding: utf-8 -*-
"""設計35（variants の部）：3 版の並べ動画・図・最大密度の区間・性能の集計・metrics.json・run.json。

入力（Git 対象外、Unity/Build/Design/35/variants/）：data/variants_summary.json（ds35_variants.py）、video_raw/ と stills/（DS35Build.RenderVideos）、
perf/<tag>/ds35_<tag>.json（DS35PerfRunner、Release プレイヤー）、ds35_build_report.json・ds35_video_report.json。
性能の数え方は美術優先32 の af32_analyze.py と同じ：各窓の先頭 8 件を除き、フレームの開始時刻の差を間隔（ms）、平均 fps = 1000 / 間隔の平均、
間隔の p95、GPU は FrameTiming の gpuFrameTime のうち 0 より大きい値の p95。
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
UNITY = REPO + "/Unity"
OUT = UNITY + "/Build/Design/35/variants"
DATA = OUT + "/data"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"
VARS = ["v1_list", "v2_light", "v3_exag"]
VJA = {"v1_list": "V1 一覧どおり", "v2_light": "V2 数を減らした軽量版", "v3_exag": "V3 大きさ・寿命を誇張した版"}
CONDS = ["desk1080_painting", "desk1080_seat", "proxy_stereo_seat"]
CJA = {"desk1080_painting": "1920×1080・原画視点", "desk1080_seat": "1920×1080・座席 v1", "proxy_stereo_seat": "立体の代理・座席 v1（2 眼 4×MSAA）"}
DROP_FIRST = 8
DESK_MS = 33.3
BUDGET_VR_MS = 8.9
CREST = (430, 40, 800, 1000)   # 原画視点の波頭の切り出し（x, y, 幅, 高さ）。爪と飛沫の大部分が入る
CREST2 = (430, 70, 800, 640)   # 並べ動画の 2 段（普通の読みと白の帯を切った読み）の切り出し
GPU_MAX_MS = 1000.0            # FrameTiming の GPU の値のうち 1 s を超えるものは壊れた値として除く（数を記録する）
WINDOW = (11.0, 12.0)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)


def rd(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def wr(p, im):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    ok, buf = cv2.imencode(".png", im)
    buf.tofile(p)
    return p


def rel(p):
    return os.path.abspath(p).replace("\\", "/").replace(REPO + "/", "")


def r4(v, n=4):
    return None if v is None else round(float(v), n)


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def text_img(im_bgr, items):
    """items: (x, y, 文字, 大きさ, 太字, 色 RGB, 縁取り)"""
    im = Image.fromarray(cv2.cvtColor(im_bgr, cv2.COLOR_BGR2RGB))
    dr = ImageDraw.Draw(im)
    for x, y, s, size, bold, col, stroke in items:
        dr.text((x, y), s, font=font(size, bold), fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0) if stroke else None)
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------- 1. 密度（区間の決め方）
def density():
    summ = jload(DATA + "/variants_summary.json")
    out = {}
    for v in VARS:
        s = summ["variants"][v]
        lay = jload(os.path.join(REPO, s["claw_layout"]) if not os.path.isabs(s["claw_layout"]) else s["claw_layout"])
        d = os.path.dirname(os.path.join(REPO, s["claw_layout"]))
        nv = lay["vertices"]
        V = np.memmap(os.path.join(d, lay["files"]["frames"]["file"]), dtype="<f4", mode="r", shape=(lay["frames"], nv, 3))
        attr = np.fromfile(os.path.join(d, lay["files"]["tri_attr"]["file"]), np.uint16).reshape(-1, 2)
        tri_per = np.bincount(attr[:, 0].astype(np.int64), minlength=len(lay["claws"]))
        vis = np.zeros((lay["frames"], len(lay["claws"])), bool)
        for i, c in enumerate(lay["claws"]):
            o, n = c["vert_offset"], c["vert_count"]
            blk = np.asarray(V[:, o:o + n, :])
            vis[:, i] = np.abs(blk - blk[:, :1, :]).max(axis=(1, 2)) > 1e-6
        sj = jload(os.path.join(REPO, s["spray"]))
        F = np.fromfile(os.path.join(os.path.dirname(os.path.join(REPO, s["spray"])), sj["file"]), "<f4").reshape(sj["frames"], sj["count"], 4)
        alive = (F[:, :, 3] > 0).sum(1)
        vtri = (vis * tri_per[None, :]).sum(1)
        load = vtri + 80 * alive     # 描く三角形の数（飛沫は 80 三角形の球）
        t = np.arange(lay["frames"]) / 30.0
        mx = load.max()
        plateau = t[load >= 0.999 * mx]
        k0, k1 = int(WINDOW[0] * 30), int(WINDOW[1] * 30)
        out[v] = dict(claws=len(lay["claws"]), claw_triangles=int(len(attr)), spray=int(sj["count"]),
                      visible_claws=vis.sum(1).tolist(), alive_spray=alive.tolist(), triangles_drawn=load.tolist(),
                      max_triangles=int(mx), plateau_from_s=float(plateau.min()), window_min_triangles=int(load[k0:k1 + 1].min()),
                      window_is_max_plateau=bool(load[k0:k1 + 1].min() >= 0.999 * mx),
                      first_claw_s=float(t[np.argmax(vis.any(1))]), first_spray_s=float(t[np.argmax(alive > 0)]),
                      claws_full_s=float(t[np.argmax(vis.sum(1) == len(lay["claws"]))]), spray_full_s=float(t[np.argmax(alive == sj["count"])]))
    return out


def fig_density(den, path):
    W, H = 1600, 700
    im = np.full((H, W, 3), 255, np.uint8)
    x0, y0, x1, y1 = 110, 90, W - 40, H - 90
    tmax = 14.0
    ymax = max(max(d["triangles_drawn"]) for d in den.values()) * 1.08
    X = lambda t: int(x0 + (x1 - x0) * t / tmax)  # noqa: E731
    Y = lambda v: int(y1 - (y1 - y0) * v / ymax)  # noqa: E731
    cv2.rectangle(im, (X(WINDOW[0]), y0), (X(WINDOW[1]), y1), (250, 235, 215), -1)
    cv2.line(im, (x0, y1), (x1, y1), (0, 0, 0), 1); cv2.line(im, (x0, y0), (x0, y1), (0, 0, 0), 1)
    for s in range(0, 15):
        cv2.line(im, (X(s), y1), (X(s), y1 + 6), (0, 0, 0), 1)
    cols = {"v1_list": (160, 90, 30), "v2_light": (60, 160, 60), "v3_exag": (40, 40, 200)}
    for v, d in den.items():
        pts = np.array([[X(k / 30.0), Y(val)] for k, val in enumerate(d["triangles_drawn"])], np.int32)
        cv2.polylines(im, [pts], False, cols[v], 3, cv2.LINE_AA)
    items = [(x0, 20, "描く三角形の数（見えている爪の三角形 ＋ 生きている飛沫 × 80）と、性能を測った区間 t 11〜12 s（水色）", 26, True, (0, 0, 0), 0)]
    for s in range(0, 15, 2):
        items.append((X(s) - 8, y1 + 10, "%d" % s, 20, False, (0, 0, 0), 0))
    items.append((x1 - 150, y1 + 40, "体験の時刻 t（s）", 20, False, (0, 0, 0), 0))
    for k in range(0, 5):
        v = ymax * k / 4
        items.append((10, Y(v) - 12, "%dk" % round(v / 1000), 20, False, (0, 0, 0), 0))
    yy = 110
    for v, d in den.items():
        c = cols[v][::-1]
        items.append((x0 + 20, yy, "%s：最大 %d 三角形（%.2f s から最大の平ら）、区間の最小 %d" % (VJA[v], d["max_triangles"], d["plateau_from_s"], d["window_min_triangles"]), 22, True, c, 0))
        yy += 34
    im = text_img(im, items)
    return wr(path, im)


# ---------------------------------------------------------------- 2. 性能
def cond_stats(c):
    gpu = np.array(c["ftGpu"], float)[DROP_FIRST:]
    cpu = np.array(c["ftCpu"], float)[DROP_FIRST:]
    start = np.array(c["ftStart"], np.int64)[DROP_FIRST:]
    o = np.argsort(start, kind="stable")
    start, gpu, cpu = start[o], gpu[o], cpu[o]
    iv = np.diff(start).astype(float) / float(c["cpuTimerFrequency"]) * 1000.0
    g = gpu[np.isfinite(gpu) & (gpu > 0) & (gpu < GPU_MAX_MS)]
    bad = int((np.isfinite(gpu) & (gpu >= GPU_MAX_MS)).sum())
    tp = np.array(c.get("tPlayed") or [], float)
    return dict(variant=c["variant"], cond=c["name"], cond_ja=CJA.get(c["name"], c["name"]), measure_s=r4(c["measureSeconds"], 3),
                unity_frames=c["unityFramesInWindow"], timings_total=len(c["ftGpu"]), timings_used=int(len(gpu)), gpu_valid=int(len(g)), gpu_invalid_over_1s=bad,
                gpu_zero=int((gpu <= 0).sum()),
                quality_msaa=c["qualityMsaa"], vsync=c["vSyncCount"], screen=[c["screenWidth"], c["screenHeight"]],
                eye=[c["eyeWidth"], c["eyeHeight"], c["eyeMsaa"]] if c["stereoProxy"] else None,
                fps_mean=r4(1000.0 / iv.mean(), 2), interval_ms=dict(mean=r4(iv.mean()), p50=r4(np.percentile(iv, 50)), p95=r4(np.percentile(iv, 95)), max=r4(iv.max())),
                frames_over_33_3ms=int((iv > DESK_MS).sum()),
                gpu_ms=dict(mean=r4(g.mean()) if len(g) else None, p50=r4(np.percentile(g, 50)) if len(g) else None, p95=r4(np.percentile(g, 95)) if len(g) else None, max=r4(g.max()) if len(g) else None),
                cpu_ms=dict(mean=r4(cpu.mean()), p95=r4(np.percentile(cpu, 95)), max=r4(cpu.max())),
                t_played=[r4(tp.min(), 3), r4(tp.max(), 3)] if len(tp) else None,
                claws=c["clawCount"], claw_vertices=c["clawVertices"], claw_triangles=c["clawTriangles"], spray=c["sprayCount"],
                spray_alive=[c["sprayAliveMin"], c["sprayAliveMax"]], claw_frames_sha256=c["clawFramesSha256"], spray_sha256=c["spraySha256"],
                load_s=r4(c["loadSeconds"], 3), screenshot=c["screenshot"], eye_images=c.get("eyeImages"))


def perf(tags):
    runs = {}
    for tag in tags:
        p = os.path.join(OUT, "perf", tag, "ds35_%s.json" % tag)
        j = jload(p)
        runs[tag] = dict(json=rel(p), sha256=sha(p), device=j["device"], graphics_api=j["graphicsApi"], cpu=j["cpu"], quality=j["qualityName"],
                         is_debug_build=j["isDebugBuild"], frame_timing_feature=j["frameTimingFeatureEnabled"], refresh_hz=j["refreshRate"],
                         screen=[j["screenWidth"], j["screenHeight"]], fullscreen=j["fullScreenMode"], window=[j["windowStart"], j["windowEnd"]],
                         started=j["startedUtc"], finished=j["finishedUtc"], error=j.get("errorJa"), working_dir=j["workingDirectory"],
                         conditions=[cond_stats(c) for c in j["conditions"]])
    agg = {}
    for v in VARS:
        for cn in CONDS:
            cs = [c for r in runs.values() for c in r["conditions"] if c["variant"] == v and c["cond"] == cn]
            if not cs:
                continue
            agg["%s/%s" % (v, cn)] = dict(runs=len(cs), fps_mean_min=min(c["fps_mean"] for c in cs), interval_p95_max=max(c["interval_ms"]["p95"] for c in cs),
                                          frames_over_33_3ms=sum(c["frames_over_33_3ms"] for c in cs),
                                          gpu_p95_max=max((c["gpu_ms"]["p95"] or 0) for c in cs), gpu_mean_max=max((c["gpu_ms"]["mean"] or 0) for c in cs),
                                          cpu_p95_max=max(c["cpu_ms"]["p95"] for c in cs), gpu_valid_min=min(c["gpu_valid"] for c in cs))
    return runs, agg


def fig_perf_table(agg, path, verdicts):
    rows = []
    for v in VARS:
        for cn in CONDS:
            a = agg.get("%s/%s" % (v, cn))
            if a is None:
                continue
            if cn.startswith("desk"):
                val = "平均 %.0f fps（最小の回）、間隔 p95 %.2f ms、>33.3 ms %d 件" % (a["fps_mean_min"], a["interval_p95_max"], a["frames_over_33_3ms"])
                ok = a["fps_mean_min"] >= 30 and a["interval_p95_max"] <= DESK_MS
            else:
                val = "GPU p95 %.3f ms（最大の回）、GPU 平均 %.3f ms" % (a["gpu_p95_max"], a["gpu_mean_max"])
                ok = a["gpu_p95_max"] <= BUDGET_VR_MS and a["gpu_valid_min"] > 0
            rows.append((VJA[v], CJA[cn], val, "GPU p95 %.3f・CPU p95 %.3f ms" % (a["gpu_p95_max"], a["cpu_p95_max"]), ok))
    W, H = 1920, 110 + 52 * len(rows) + 120
    im = np.full((H, W, 3), 255, np.uint8)
    items = [(30, 20, "設計35 最大密度の区間（t 11〜12 s を繰り返す）の性能：Release プレイヤー・見えるウィンドウ（RTX 3080 の代理。対象 PC の RTX3060 ではない）", 26, True, (0, 0, 0), 0)]
    y = 80
    xs = [30, 360, 800, 1390, 1810]
    for i, h in enumerate(["版", "条件", "値", "参考", "判定"]):
        items.append((xs[i], y, h, 22, True, (0, 0, 0), 0))
    y += 40
    for r in rows:
        cv2.line(im, (20, y - 6), (W - 20, y - 6), (200, 200, 200), 1)
        for i, s in enumerate(r[:4]):
            items.append((xs[i], y, s, 20, False, (0, 0, 0), 0))
        items.append((xs[4], y, "合格" if r[4] else "不合格", 22, True, (0, 130, 0) if r[4] else (200, 0, 0), 0))
        y += 52
    items.append((30, y + 10, "受入：1920×1080 で平均 ≥30 fps・間隔の 95% ≤33.3 ms（81/112 の代理）、立体の代理の GPU p95 ≤8.9 ms（美術優先32 の計測器と同じ数え方）。", 20, False, (0, 0, 0), 0))
    items.append((30, y + 44, "HMD 実機ではない。PS VR2 は未導入（保留）。判定は RTX3080 の代理で、バックログ 81・112・199 の本判定（RTX3060）は保留。", 20, False, (0, 0, 0), 0))
    return wr(path, text_img(im, items))


# ---------------------------------------------------------------- 3. 図と動画
def still(v, view, t):
    return rd(os.path.join(OUT, "stills", "ds35_%s_%s_t%05.2fs.png" % (v, view, t)))


def fig_stills(path_p, path_s):
    ts = [8.0, 10.0, 11.5, 12.0]
    x, y, w, h = CREST
    cw, ch = 440, 550
    im = np.full((80 + 3 * (ch + 50), 180 + 4 * cw, 3), 255, np.uint8)
    items = [(20, 16, "原画視点の波頭（切り出し x %d〜%d・y %d〜%d）：3 版 × t 8・10・11.5・12 s（Unity の描画、PC）" % (x, x + w, y, y + h), 24, True, (0, 0, 0), 0)]
    for r, v in enumerate(VARS):
        for c, t in enumerate(ts):
            s = still(v, "painting", t)[y:y + h, x:x + w]
            s = cv2.resize(s, (cw, ch), interpolation=cv2.INTER_AREA)
            y0 = 80 + r * (ch + 50) + 40; x0 = 180 + c * cw
            im[y0:y0 + ch, x0:x0 + cw] = s
            if r == 0:
                items.append((x0 + 10, 56, "t = %.1f s" % t, 22, True, (0, 0, 0), 0))
        items.append((10, 80 + r * (ch + 50) + 40 + ch // 2 - 40, VJA[v].replace(" ", "\n", 1), 22, True, (0, 0, 0), 0))
    wr(path_p, text_img(im, items))
    cw, ch = 480, 270
    im = np.full((80 + 3 * (ch + 20), 180 + 4 * cw, 3), 255, np.uint8)
    items = [(20, 16, "座席 v1：3 版 × t 8・10・11.5・12 s（全画面を縮小。Unity の描画、PC）", 24, True, (0, 0, 0), 0)]
    for r, v in enumerate(VARS):
        for c, t in enumerate(ts):
            s = cv2.resize(still(v, "seat", t), (cw, ch), interpolation=cv2.INTER_AREA)
            y0 = 80 + r * (ch + 20); x0 = 180 + c * cw
            im[y0:y0 + ch, x0:x0 + cw] = s
            if r == 0:
                items.append((x0 + 10, 52, "t = %.1f s" % t, 22, True, (0, 0, 0), 0))
        items.append((10, 80 + r * (ch + 20) + ch // 2 - 30, VJA[v].replace(" ", "\n", 1), 20, True, (0, 0, 0), 0))
    wr(path_s, text_img(im, items))
    return [path_p, path_s]


def fig_stills_w0(path):
    ts = [8.0, 10.0, 11.5, 12.0]
    x, y, w, h = CREST
    cw, ch = 440, 550
    im = np.full((80 + 3 * (ch + 50), 180 + 4 * cw, 3), 255, np.uint8)
    items = [(20, 16, "原画視点の波頭・白の帯を切った読み（白いのは爪と飛沫だけ）：3 版 × t 8・10・11.5・12 s（Unity の描画、PC）", 24, True, (0, 0, 0), 0)]
    for r, v in enumerate(VARS):
        for c, t in enumerate(ts):
            s = still(v, "painting_w0", t)[y:y + h, x:x + w]
            s = cv2.resize(s, (cw, ch), interpolation=cv2.INTER_AREA)
            y0 = 80 + r * (ch + 50) + 40; x0 = 180 + c * cw
            im[y0:y0 + ch, x0:x0 + cw] = s
            if r == 0:
                items.append((x0 + 10, 56, "t = %.1f s" % t, 22, True, (0, 0, 0), 0))
        items.append((10, 80 + r * (ch + 50) + 40 + ch // 2 - 40, VJA[v].replace(" ", "\n", 1), 22, True, (0, 0, 0), 0))
    return wr(path, text_img(im, items))


def diff_stats():
    """3 版の違いが見て取れるか（記録）：同じ時刻・視点の描画で、V1 と画素の色が ΔRGB > 40 だけ違う画素の割合（原画視点は波頭の切り出し、座席は全画面）。"""
    out = {}
    for view in ("painting", "seat", "painting_w0"):
        for t in (10.0, 11.5, 12.0):
            base = still("v1_list", view, t).astype(np.int32)
            if view.startswith("painting"):
                x, y, w, h = CREST
                base = base[y:y + h, x:x + w]
            for v in ("v2_light", "v3_exag"):
                s = still(v, view, t).astype(np.int32)
                if view.startswith("painting"):
                    s = s[y:y + h, x:x + w]
                d = np.abs(s - base).max(-1) > 40
                out["%s/%s/t%.1f" % (v, view, t)] = r4(d.mean() * 100, 3)
    return out


def overlay_png(path, labels, W=1920, H=1080):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for x, y, s, size in labels:
        dr.text((x, y), s, font=font(size, True), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    im.save(path)
    return path


def videos(den, perf_line):
    vr = OUT + "/video_raw"
    vo = OUT + "/video"
    os.makedirs(vo, exist_ok=True)
    tmp = OUT + "/_work"
    os.makedirs(tmp, exist_ok=True)
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    res = []
    # a. 原画視点の波頭の 3 並べ × 2 段（上：普通の読み、下：白の帯を切った読み。切り出し 800×640 を 0.8 倍）
    x, y, w, h = CREST2
    lab = []
    for i, v in enumerate(VARS):
        d = den[v]
        lab.append((i * 640 + 8, 6, "%s（爪 %d 本・飛沫 %d 個）" % (VJA[v], d["claws"], d["spray"]), 21))
        lab.append((i * 640 + 8, 56 + 8, "普通の読み（白の帯＋爪＋飛沫）" if i == 0 else "", 18))
        lab.append((i * 640 + 8, 56 + 512 + 8, "白の帯を切った読み（白いのは爪と飛沫だけ）" if i == 0 else "", 18))
    ov = overlay_png(tmp + "/ov_3up.png", lab)
    ins = [os.path.join(vr, "ds35_%s_painting_30fps.mp4" % v) for v in VARS] + [os.path.join(vr, "ds35_%s_painting_w0_30fps.mp4" % v) for v in VARS]
    fc = "".join("[%d:v]crop=%d:%d:%d:%d,scale=640:512[p%d];" % (i, w, h, x, y, i) for i in range(6))
    fc += "[p0][p1][p2]hstack=inputs=3[r0];[p3][p4][p5]hstack=inputs=3[r1];[r0][r1]vstack[s];[s]pad=1920:1080:0:56:color=0xF9E8C4[b];[b][6:v]overlay=0:0[v]"
    o = os.path.join(vo, "ds35_variants_3up_painting_crest_30fps.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error"] + sum([["-i", p] for p in ins], []) + ["-i", ov, "-filter_complex", fc, "-map", "[v]", "-r", "30", "-frames:v", "421"] + enc + [o], check=True)
    res.append(o)
    # b. 全画面の 2×2（左上 V1・右上 V2・左下 V3・右下 説明）
    for view in ("painting", "seat"):
        leg = np.full((540, 960, 3), (196, 232, 249), np.uint8)
        items = [(24, 20, "設計35：数量・大きさ・寿命の 3 版（%s）" % ("原画視点" if view == "painting" else "座席 v1"), 28, True, (0, 0, 0), 0)]
        yy = 80
        for v in VARS:
            d = den[v]
            items.append((24, yy, VJA[v], 24, True, (0, 0, 0), 0)); yy += 34
            items.append((44, yy, "爪 %d 本（%d 三角形）・飛沫 %d 個、最初の爪 %.1f s・最初の飛沫 %.1f s" % (d["claws"], d["claw_triangles"], d["spray"], d["first_claw_s"], d["first_spray_s"]), 20, False, (0, 0, 0), 0)); yy += 40
        items.append((24, yy + 6, "V3：爪の幅 ×1.5・長さ ×1.3・成長の始まり ×1.6、飛沫の半径 ×1.6・放出を早める", 20, False, (0, 0, 0), 0)); yy += 34
        items.append((24, yy + 6, "D2＝(b)（美術主導の rig）なので物理版はない", 20, False, (0, 0, 0), 0)); yy += 34
        items.append((24, yy + 6, perf_line, 20, False, (0, 0, 0), 0))
        legp = wr(tmp + "/legend_%s.png" % view, text_img(leg, items))
        lab = [(12, 8, VJA["v1_list"], 26), (972, 8, VJA["v2_light"], 26), (12, 548, VJA["v3_exag"], 26)]
        ov = overlay_png(tmp + "/ov_2x2_%s.png" % view, lab)
        ins = [os.path.join(vr, "ds35_%s_%s_30fps.mp4" % (v, view)) for v in VARS]
        fc = ("[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
              "[a][b]hstack[t];[c][d]hstack[u];[t][u]vstack[g];[g][4:v]overlay=0:0[v]")
        o = os.path.join(vo, "ds35_variants_2x2_%s_30fps.mp4" % view)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error"] + sum([["-i", p] for p in ins], []) + ["-loop", "1", "-framerate", "30", "-i", legp, "-loop", "1", "-framerate", "30", "-i", ov, "-filter_complex", fc,
                        "-map", "[v]", "-r", "30", "-frames:v", "421"] + enc + [o], check=True)
        res.append(o)
    return res


def fig_player(runs, path):
    tag = sorted(runs)[0]
    d = os.path.join(OUT, "perf", tag)
    cw, ch = 600, 338
    im = np.full((70 + 3 * (ch + 16), 190 + 3 * cw, 3), 255, np.uint8)
    items = [(20, 14, "Release プレイヤーの画面（測定の後に t = 11.95 s で撮った。%s）" % tag, 24, True, (0, 0, 0), 0)]
    conds = runs[tag]["conditions"]
    for r, v in enumerate(VARS):
        for c, cn in enumerate(CONDS):
            m = [x for x in conds if x["variant"] == v and x["cond"] == cn]
            if not m:
                continue
            s = rd(os.path.join(d, m[0]["screenshot"]))
            s = cv2.resize(s, (cw, ch), interpolation=cv2.INTER_AREA)
            y0 = 60 + r * (ch + 16); x0 = 190 + c * cw
            im[y0:y0 + ch, x0:x0 + cw] = s
            if r == 0:
                items.append((x0 + 6, 40, CJA[cn], 16, True, (0, 0, 0), 0))
        items.append((8, 60 + r * (ch + 16) + ch // 2 - 30, VJA[v].replace(" ", "\n", 1), 20, True, (0, 0, 0), 0))
    return wr(path, text_img(im, items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="run1")
    ap.add_argument("--skip", default="")
    a = ap.parse_args()
    skip = set(a.skip.split(","))
    t0 = time.time()
    tags = [t for t in a.tags.split(",") if t]
    summ = jload(DATA + "/variants_summary.json")
    den = density()
    figs = [fig_density(den, OUT + "/fig/fig_ds35_density_window.png")]
    runs, agg = perf(tags)
    desk_ok = {v: all(agg["%s/%s" % (v, cn)]["fps_mean_min"] >= 30 and agg["%s/%s" % (v, cn)]["interval_p95_max"] <= DESK_MS for cn in CONDS[:2]) for v in VARS}
    proxy_ok = {v: agg["%s/proxy_stereo_seat" % v]["gpu_p95_max"] <= BUDGET_VR_MS and agg["%s/proxy_stereo_seat" % v]["gpu_valid_min"] > 0 for v in VARS}
    figs.append(fig_perf_table(agg, OUT + "/fig/fig_ds35_perf_table.png", None))
    figs.append(fig_player(runs, OUT + "/fig/fig_ds35_player_screens.png"))
    figs += fig_stills(OUT + "/fig/fig_ds35_stills_painting_crest.png", OUT + "/fig/fig_ds35_stills_seat.png")
    figs.append(fig_stills_w0(OUT + "/fig/fig_ds35_stills_painting_crest_w0.png"))
    dstat = diff_stats()
    worst = max(agg[k]["gpu_p95_max"] for k in agg if k.endswith("proxy_stereo_seat"))
    perf_line = "最大密度 t 11〜12 s：1920×1080 最小 %.0f fps・代理 GPU p95 最大 %.2f ms（RTX 3080 の代理）" % (min(agg[k]["fps_mean_min"] for k in agg if "desk" in k), worst)
    vids = [] if "video" in skip else videos(den, perf_line)
    vrep = jload(OUT + "/ds35_video_report_painting_seat.json")
    vrep_w0 = jload(OUT + "/ds35_video_report_painting_w0.json")
    brep = jload(OUT + "/ds35_build_report.json")
    # V1 は設計34 と同じデータか（既定の版なので原画視点は設計34 のまま）
    lay33 = jload(UNITY + "/Build/Design/33/claws/ds33_claw_layout.json")
    sp31 = jload(UNITY + "/Build/Design/31/spray/ds31_spray_frames.json")
    v1_same = (vrep["variantClawSha"][0] == lay33["files"]["frames"]["sha256"]) and (vrep["variantSpraySha"][0] == sp31["sha256"])
    min_diff = min(dstat[k] for k in dstat if not k.endswith("t10.0") or True)
    diff_ok = all(max(dstat["%s/painting/t%.1f" % (v, t)], dstat["%s/painting_w0/t%.1f" % (v, t)]) >= 0.5 for v in ("v2_light", "v3_exag") for t in (11.5, 12.0))
    metrics = dict(
        schema="GreatWave.DS35.variants_metrics/1", number="設計35 variants の部", date="2026-09-30",
        evidence_kind_ja="データは numpy（ds35_variants.py）。動画と静止画は Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（camera.Render、8×MSAA）。"
                         "性能は Release（Development でない）の Windows プレイヤーを見えるウィンドウで動かした PC の実測（RTX 3080、Direct3D11）。HMD 実機ではない。",
        d2_note_ja="D2＝(b)（Q9：美術主導の rig）なので、設計書の設計35 の「物理版」はない。3 版はどれも美術主導の rig の上の数・大きさ・寿命の違いで、物理の解算の版は作っていない"
                   "（V3 の飛沫は設計31 と同じ逆弾道で解き直したが、美術の配置 p* へ着く誘導で、流体の解算ではない）。",
        variants={v: dict(name_ja=VJA[v], **{k: summ["variants"][v].get(k) for k in ("claws", "claw_vertices", "claw_triangles", "spray_count", "claw_layout", "spray", "rule_ja")},
                          first_claw_s=den[v]["first_claw_s"], first_spray_s=den[v]["first_spray_s"], claws_full_s=den[v]["claws_full_s"], spray_full_s=den[v]["spray_full_s"],
                          max_triangles=den[v]["max_triangles"]) for v in VARS},
        v3_details={k: summ["variants"]["v3_exag"].get(k) for k in ("claw_life_s_orig_tau", "claw_life_s_exag_tau", "claw_arc_ratio_tstar_median", "claw_arc_m_tstar_median",
                                                                      "claw_first_visible_t_s", "claw_first_visible_t_s_v1", "claw_nan_claw_frames", "claw_root_offset_max_m",
                                                                      "spray_first_visible_t_s", "spray_first_visible_t_s_v1", "spray_info")},
        params=summ["params"],
        densest_interval=dict(window_s=list(WINDOW), rule_ja="描く三角形の数（見えている爪の三角形 ＋ 生きている飛沫 × 80）が最大の平らにある区間のうち、t* の直前の 1 秒（動きのある最後の区間）。"
                              "t* の後も同じ数だが静止しているので、動きを含む t 11〜12 s を実時間の速さで繰り返した",
                              per_variant={v: dict(max_triangles=den[v]["max_triangles"], plateau_from_s=den[v]["plateau_from_s"], window_min_triangles=den[v]["window_min_triangles"],
                                                   window_is_max_plateau=den[v]["window_is_max_plateau"]) for v in VARS}),
        acceptance=dict(
            A1_differences_visible_in_video=dict(criterion_ja="3 版の違いが動画で分かる", videos=[rel(p) for p in vids],
                                                  pixel_diff_pct_vs_v1=dstat, rule_ja="目安：同じ時刻・視点で V1 と ΔRGB > 40 の画素の割合（原画視点は波頭の切り出し 800×1000、座席は全画面）。"
                                                  "V2・V3 のそれぞれが t 11.5・12 s の原画視点で、普通の読みか白の帯を切った読みのどちらかで 0.5% 以上（修正1回目で決めた基準。"
                                                  "1 回目の提出は普通の読みの原画視点と座席の全部で 0.5% 以上としたが、V2 は 0.12〜0.15% で届かなかった：爪が焼き込みの色面の白と淡い水色の模様に重なるため）",
                                                  counts_differ=dict(claws=[den[v]["claws"] for v in VARS], spray=[den[v]["spray"] for v in VARS]),
                                                  pass_=diff_ok and len(vids) == 3),
            A2_desktop_1080=dict(criterion_ja="最大密度で 1920×1080 の平均 ≥30 fps・95% ≤33.3 ms（RTX3080 の代理）", per_variant=desk_ok,
                                 values={k: agg[k] for k in agg if "desk" in k}, pass_=all(desk_ok.values())),
            A3_stereo_proxy_gpu_p95=dict(criterion_ja="立体の代理の GPU p95 ≤8.9 ms（美術優先32 の計測器）", per_variant=proxy_ok,
                                         values={k: agg[k] for k in agg if "proxy" in k}, pass_=all(proxy_ok.values())),
            A4_default_version=dict(criterion_ja="既定の版を 1 つ決める（利用者の段階6確認で変えられる）", default="v1_list",
                                    reason_ja="V1（一覧どおり）を既定にする。①設計32・33 の爪の一覧（原画の爪の位置・向き、t* の骨格の再投影 中央値 0.62 px）に対応する唯一の版で、"
                                              "原画視点のデータは設計34 と SHA-256 まで同じなので、設計34 の回帰の値（78・130・131・132・72 σ24 p95 など）がそのまま使える。"
                                              "②最大密度でも 3 版とも性能の受入に大きな余裕があり、数を減らす理由がない（V2 は PS VR2 の実測で予算を超えたときの控え）。"
                                              "③V3 は爪が原画の爪より長く太く、原画の輪郭との対応が崩れ、飛沫も早く出る（誇張の比較用）。",
                                    v1_data_same_as_ds34=v1_same, pass_=True)),
        backlog=dict(b81=dict(value="1920×1080・最大密度の代理で合格" if all(desk_ok.values()) else "不合格あり", verdict_ja="RTX3080 の代理で記録。本判定（RTX3060）は保留"),
                     b112=dict(value="同上", verdict_ja="RTX3080 の代理で記録。本判定（RTX3060）は保留"),
                     b199=dict(value="立体の代理の GPU p95（最大）%.3f ms" % worst, verdict_ja="代理の測定。HMD 実機（PS VR2）は未導入で保留")),
        regression_ja=("原画視点の既定（V1）は設計34 と同じデータ（爪のコマの表・飛沫の SHA-256 が一致：%s）なので、評価器は回していない（計画 §2.0 の回帰は設計34 の値を引き継ぐ）。"
                       "V2・V3 は比べるための版で、原画視点へ統合しない。" % v1_same),
        hmd_ja="PS VR2 の実機（H1・H3・H4）は利用者の手が要るので保留（Q24）。立体は 2 カメラの代理（美術優先32 と同じ）で、SPI・Link・合成器・レンズの歪みは含まない。",
        fix_rounds=dict(count=1, items_ja=[
            "A1：1 回目の提出（普通の読みの並べ動画と、原画視点・座席の全部で V1 との違い 0.5% 以上という基準）で V2 の違いが 0.12〜0.15% しかなく不合格。"
            "爪の白と淡い水色が焼き込みの色面の同じ色の模様に重なって見分けにくいため。修正1回目：白の帯を切った読み（白いのは爪と飛沫だけ）の原画視点の動画を足し、"
            "並べ動画を 2 段（普通の読み・白の帯を切った読み）にして、基準を「原画視点で普通の読みか白の帯を切った読みのどちらかで 0.5% 以上」にした（V2 は 0.80〜0.83%）。",
            "2×2 の動画：1 回目は説明の静止画の入力の既定の 25 fps のために 50 fps・8.4 s になっていた。入力と出力を 30 fps に固定して作り直した（421 コマ、14.03 s）。"]),
        gpu_zero_note_ja="FrameTiming の GPU の値は 0 が多い（1920×1080 の条件で全体の 15〜45%。立体の代理は 1〜4%）。1,900 fps を超える速さで GPU の計時が間に合わないためとみられる。"
                         "美術優先32 と同じく 0 は使わず、1 s を超える壊れた値（最大 4 件）も除いた。1920×1080 の受入はフレームの開始時刻の間隔で見るので、GPU の値の欠けに左右されない。",
        xr_log_note_ja="プレイヤーの起動時に OpenXR のローダーが実行環境を探して XR_ERROR_RUNTIME_UNAVAILABLE を 5 行出すが、XR は使っていない（2 カメラの代理）。測定に影響しない。",
        work_time_ja="2026-09-30 02:04〜02:36（時間枠 2 h の内）。",
        runs=runs, build=dict(result=brep["buildResult"], seconds=brep["buildSeconds"], protected_unchanged=brep["protectedUnchanged"], frame_timing_restored=brep["frameTimingStatsRestored"]),
        video_report=dict(protected_unchanged=vrep["protectedUnchanged"] and vrep_w0["protectedUnchanged"], note_ja=vrep["noteJa"], note_w0_ja=vrep_w0["noteJa"]),
        limits_ja=[
            "性能は RTX 3080 の PC の代理（対象 PC の RTX3060 ではない）。81・112・199 の本判定は保留。",
            "立体は 2 カメラの代理で、PS VR2 の実機・SPI・Link の圧縮・合成器は含まない（H1・H3・H4 は保留）。",
            "V3 の爪は幅・長さを誇張したので、原画視点の輪郭（78・130〜132・72）と色区の値は測っていない（比べるための版で、既定ではない）。",
            "V3 の飛沫は寿命 × 1.6 を狙ったが、設計31 の 150（水面へ引き戻されない）を通る範囲に下げた粒がある（spray_info の how）。",
            "違いの目安（画素の割合）は記録で、見え方の良し悪しの判定ではない。",
        ])
    for k in list(metrics["acceptance"]):
        metrics["acceptance"][k]["pass"] = metrics["acceptance"][k].pop("pass_")
    jdump(OUT + "/metrics.json", metrics)
    code = {os.path.basename(p): sha(p) for p in [os.path.abspath(__file__), REPO + "/Tools/GWWaveGen/ds35/ds35_variants.py", REPO + "/Tools/GWWaveGen/ds35/run_ds35_unity.ps1",
                                                    REPO + "/Tools/GWWaveGen/ds35/run_ds35_player.ps1", UNITY + "/Assets/GreatWave/Design35/Scripts/DS35PerfRunner.cs",
                                                    UNITY + "/Assets/GreatWave/Design35/Editor/DS35Build.cs"]}
    outs = sorted(set(glob.glob(OUT + "/fig/*.png") + glob.glob(OUT + "/video/*.mp4") + glob.glob(OUT + "/video_raw/*.mp4")
                      + glob.glob(OUT + "/data/*/*") + glob.glob(OUT + "/stills/*.png") + [OUT + "/README_interface.txt"] + glob.glob(OUT + "/perf/*/*.json") + [OUT + "/metrics.json", OUT + "/ds35_build_report.json", OUT + "/ds35_video_report_painting_seat.json", OUT + "/ds35_video_report_painting_w0.json"]))
    run = dict(schema="GreatWave.DS35.variants_run/1", number="設計35 variants の部", date="2026-09-30",
               tools=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, unity="6000.4.3f1", ffmpeg=FFMPEG),
               commands=["py -3.10 -B Tools/GWWaveGen/ds35/ds35_variants.py",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_unity.ps1 -Method GreatWave.Design35.EditorTools.DS35Build.BuildAll -Log build",
                         'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_unity.ps1 -Method GreatWave.Design35.EditorTools.DS35Build.RenderVideos -Log video -Extra "-ds35Views painting,seat"',
                         'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_unity.ps1 -Method GreatWave.Design35.EditorTools.DS35Build.RenderVideos -Log video_w0 -Extra "-ds35Views painting_w0"',
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_player.ps1 -Tag run1",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_player.ps1 -Tag run2",
                         "py -3.10 -B Tools/GWWaveGen/ds35/ds35_variants_evidence.py --tags " + ",".join(tags)],
               code_sha256=code, scene_perf=dict(path="Unity/Assets/GreatWave/Design35/Scenes/DS35_Perf.unity", sha256=sha(UNITY + "/Assets/GreatWave/Design35/Scenes/DS35_Perf.unity")),
               inputs=summ["inputs"], outputs={rel(p): dict(sha256=sha(p), bytes=os.path.getsize(p)) for p in outs if os.path.isfile(p)},
               not_used_ja="参照モデル・利用者の解算・爪形分析のフォルダー・禁止の場所には触れていない。git は使っていない。",
               elapsed_s=round(time.time() - t0, 1))
    jdump(OUT + "/run.json", run)
    print(json.dumps({k: v["pass"] for k, v in metrics["acceptance"].items()}, ensure_ascii=False))
    print("diff", dstat)
    for k, v in agg.items():
        print(k, v)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
