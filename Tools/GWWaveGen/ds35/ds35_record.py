# -*- coding: utf-8 -*-
"""設計35 の記録：証拠（Docs/Evidence/Design/35/）を作り、metrics.json と run.json を書く。

値は次の出力から読む（どれも Git 対象外）。
  - variants の部：Unity/Build/Design/35/variants/（metrics.json・run.json・data/variants_summary.json・
    ds35_build_report.json・ds35_video_report_*.json・perf/run{1,2}/ds35_run{1,2}.json・図と動画）
  - 進行役の独立の検査：リポジトリの外のコード。コードと、記録の時に回し直した出力の写しは Unity/Build/Design/35/indep_check/
この道具で新しく数えるのは、次の数え直しだけ（Unity/Build/Design/35/record/ds35_record_counts.json にも書く）。
  - 性能：プレイヤーの生の計時（ftStart・ftGpu）から、美術優先32 の数え方（先頭 8 件を除く）で fps・間隔 p95・GPU p95 を数え直す
  - データ：3 版の爪と飛沫の数、最初に見える時刻、V2 が V1 の部分集合であること、V3 の爪の広がりの比、飛沫の見えている時間の比
  - 動画：3 版の元の動画（video_raw）をコマごとに比べ、V1 と ΔRGB > 40 の画素の割合の時間の変化と、最初に 50 画素以上違うコマ
  - 作業の時刻（ファイルの時刻）
図は 1920×1080 の枠に収め、余白に日本語の説明を入れる。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds35/ds35_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Design"
B35 = B + "/35"
VAR = B35 + "/variants"
IND = B35 + "/indep_check"
REC = B35 + "/record"
EV = REPO + "/Docs/Evidence/Design/35"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
FONT = "C:/Windows/Fonts/meiryo.ttc"
MP4_LIMIT = 5 * 1024 * 1024
W, H = 1920, 1080
NF = 421
KSTAR = 360
VARS = ["v1_list", "v2_light", "v3_exag"]
VIEWS = ["painting", "painting_w0", "seat"]
CREST = (430, 40, 800, 1000)    # variants の部の違いの目安の切り出し（x, y, 幅, 高さ）
CREST2 = (430, 70, 800, 640)    # 並べ動画の 2 段の切り出し
DIFF_T = 40
FIRST_PX = 50
CLAW_FRAMES_SHA_DS33 = "6e7629889a47efc0172d40c28364b59eadef48e419d0dad5c279e3fa3d7f7565"
SPRAY_SHA_DS31 = "9db0a42811aa2c72f1cefbf8b80386f2e919a8b80fe65f7e91dd6a60c9b25c5f"
CODE_PATHS = {
    "ds35_variants_evidence.py": "Tools/GWWaveGen/ds35/ds35_variants_evidence.py",
    "ds35_variants.py": "Tools/GWWaveGen/ds35/ds35_variants.py",
    "run_ds35_unity.ps1": "Tools/GWWaveGen/ds35/run_ds35_unity.ps1",
    "run_ds35_player.ps1": "Tools/GWWaveGen/ds35/run_ds35_player.ps1",
    "DS35PerfRunner.cs": "Unity/Assets/GreatWave/Design35/Scripts/DS35PerfRunner.cs",
    "DS35Build.cs": "Unity/Assets/GreatWave/Design35/Editor/DS35Build.cs",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def jdump(p, d):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def imread(p):
    im = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit("画像を読めない: " + p)
    return im


def imwrite(p, im):
    ok, buf = cv2.imencode(".png", im)
    if not ok:
        raise SystemExit("PNG を書けない: " + p)
    buf.tofile(p)


def text_lines(img, lines, x, y, size=24, col=(20, 20, 20), gap=8):
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, size)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=(col[2], col[1], col[0]))
        y += size + gap
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def fit(img, box_w, box_h):
    s = min(box_w / img.shape[1], box_h / img.shape[0], 1.0)
    if s < 1.0:
        img = cv2.resize(img, (int(round(img.shape[1] * s)), int(round(img.shape[0] * s))), interpolation=cv2.INTER_AREA)
    return img, s


def fig_single(src, dst, caption):
    """1 枚の図を 1920×1080 に収め、下の余白に日本語の説明を入れる。"""
    im = imread(src)
    ch = 20 + len(caption) * 34
    small, s = fit(im, W, H - ch)
    cv = np.full((H, W, 3), 245, np.uint8)
    x0 = (W - small.shape[1]) // 2
    cv[0:small.shape[0], x0:x0 + small.shape[1]] = small
    cv = text_lines(cv, caption, 24, small.shape[0] + 12, size=24)
    imwrite(dst, cv)
    return {"src": rel(src), "src_sha256": sha(src), "scale": round(s, 4), "dst": rel(dst)}


def ftime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")


def ctime(p):
    return datetime.datetime.fromtimestamp(os.path.getctime(p)).strftime("%Y-%m-%d %H:%M:%S")


def probe(p):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,nb_frames,r_frame_rate,codec_name", "-of", "json", p],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


# ---------------------------------------------------------------- 性能の数え直し
def recount_perf():
    per = {}
    meta = {}
    for tag in ("run1", "run2"):
        d = jload(VAR + "/perf/%s/ds35_%s.json" % (tag, tag))
        ext = jload(VAR + "/perf/%s/ds35_%s_external.json" % (tag, tag))
        meta[tag] = {"device": d["device"], "graphicsApi": d["graphicsApi"], "cpu": d["cpu"], "qualityName": d["qualityName"],
                     "isDebugBuild": d["isDebugBuild"], "frameTimingFeatureEnabled": d["frameTimingFeatureEnabled"],
                     "fullScreenMode": d["fullScreenMode"], "screen": [d["screenWidth"], d["screenHeight"]],
                     "window_s": [d["windowStart"], d["windowEnd"]], "startedUtc": d["startedUtc"], "finishedUtc": d["finishedUtc"],
                     "exitCode": ext["exitCode"], "killedByTimeout": ext["killedByTimeout"], "exeSha256": ext["exeSha256"]}
        for c in d["conditions"]:
            st = np.array(c["ftStart"], dtype=np.int64)
            gpu = np.array(c["ftGpu"], dtype=float)
            o = np.argsort(st, kind="stable")
            st, gpu = st[o][8:], gpu[o][8:]
            iv = np.diff(st).astype(float) / float(c["cpuTimerFrequency"]) * 1000.0
            g = gpu[(gpu > 0) & (gpu < 1000.0)]
            tp = np.array(c["tPlayed"], dtype=float)
            k = c["variant"] + "/" + c["name"]
            per.setdefault(k, []).append({
                "tag": tag, "fps_mean": round(1000.0 / float(iv.mean()), 2), "interval_p95_ms": round(float(np.percentile(iv, 95)), 4),
                "interval_max_ms": round(float(iv.max()), 3), "frames_over_33_3ms": int((iv > 33.3).sum()), "frames": int(iv.size + 1),
                "gpu_p95_ms": round(float(np.percentile(g, 95)), 4), "gpu_zero": int((gpu == 0).sum()), "gpu_over_1s": int((gpu >= 1000.0).sum()),
                "gpu_zero_pct": round(100.0 * float((gpu == 0).mean()), 1),
                "t_played_s": [round(float(tp.min()), 4), round(float(tp.max()), 4)],
                "claws": c["clawCount"], "claw_triangles": c["clawTriangles"], "spray": c["sprayCount"],
                "spray_alive": [c["sprayAliveMin"], c["sprayAliveMax"]], "quality_msaa": c["qualityMsaa"], "vsync": c["vSyncCount"],
                "eye": [c["eyeWidth"], c["eyeHeight"], c["eyeMsaa"]], "stereo_proxy": c["stereoProxy"],
                "claw_frames_sha256": c["clawFramesSha256"], "spray_sha256": c["spraySha256"]})
    table = {}
    for k, rs in per.items():
        table[k] = {"fps_mean_min": min(r["fps_mean"] for r in rs), "interval_p95_max_ms": max(r["interval_p95_ms"] for r in rs),
                    "interval_max_ms": max(r["interval_max_ms"] for r in rs), "frames_over_33_3ms": sum(r["frames_over_33_3ms"] for r in rs),
                    "gpu_p95_max_ms": max(r["gpu_p95_ms"] for r in rs), "gpu_zero_pct": [r["gpu_zero_pct"] for r in rs],
                    "gpu_over_1s": sum(r["gpu_over_1s"] for r in rs),
                    "t_played_s": [min(r["t_played_s"][0] for r in rs), max(r["t_played_s"][1] for r in rs)],
                    "claws": rs[0]["claws"], "claw_triangles": rs[0]["claw_triangles"], "spray": rs[0]["spray"],
                    "spray_alive_min": min(r["spray_alive"][0] for r in rs), "eye": rs[0]["eye"], "quality_msaa": rs[0]["quality_msaa"],
                    "vsync": rs[0]["vsync"], "claw_frames_sha256": rs[0]["claw_frames_sha256"], "spray_sha256": rs[0]["spray_sha256"]}
    return {"rule_ja": "各条件で ftStart を並べて先頭 8 件を除き、開始時刻の差を間隔（ms）。平均 fps＝1000／間隔の平均。GPU は 0 より大きく 1 s 未満の値の p95。"
                       "2 回（run1・run2）のうち fps は小さい方、p95 は大きい方",
            "runs": meta, "per_run": per, "table": table}


# ---------------------------------------------------------------- データの数え直し
def recount_data():
    L1 = jload(B + "/33/claws/ds33_claw_layout.json")
    L2 = jload(VAR + "/data/v2_light/claw_layout.json")
    L3 = jload(VAR + "/data/v3_exag/claw_layout.json")
    files = {"v1_list": (B + "/33/claws/ds33_claw_frames_f32.bin", B + "/31/spray/ds31_spray_frames.bin", L1, 186),
             "v2_light": (VAR + "/data/v2_light/claw_frames_f32.bin", VAR + "/data/v2_light/spray_frames.bin", L2, 93),
             "v3_exag": (VAR + "/data/v3_exag/claw_frames_f32.bin", VAR + "/data/v3_exag/spray_frames.bin", L3, 186)}
    out = {"sha256": {}, "per_variant": {}}
    fr, sp, ext = {}, {}, {}
    for v, (cf, sf, L, ns) in files.items():
        out["sha256"][v] = {"claw_frames": sha(cf), "spray_frames": sha(sf)}
        f = np.fromfile(cf, dtype="<f4").reshape(NF, L["vertices"], 3)
        s = np.fromfile(sf, dtype="<f4").reshape(NF, ns, 4)
        E = np.zeros((NF, len(L["claws"])), np.float32)
        for i, c in enumerate(L["claws"]):
            p = f[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
            E[:, i] = np.nanmax(np.linalg.norm(p - p[:, :1], axis=2), axis=1)
        vis = E > 1e-3
        alive = s[:, :, 3] > 0
        fr[v], sp[v], ext[v] = f, s, E
        cfirst = int(np.argmax(vis.any(axis=1)))
        call = int(np.argmax(vis.all(axis=1))) if vis.all(axis=1).any() else -1
        sfirst = int(np.argmax(alive.any(axis=1)))
        sfull = int(np.argmax(alive.sum(axis=1) == alive.sum(axis=1).max()))
        out["per_variant"][v] = {
            "claws": len(L["claws"]), "claw_vertices": L["vertices"], "claw_triangles": L["triangles"], "spray": ns,
            "claw_first_visible_frame": cfirst, "claw_first_visible_s": round(cfirst / 30.0, 3),
            "claw_all_visible_frame": call, "claw_all_visible_s": round(call / 30.0, 3),
            "spray_first_frame": sfirst, "spray_first_s": round(sfirst / 30.0, 3),
            "spray_full_frame": sfull, "spray_full_s": round(sfull / 30.0, 3), "spray_alive_max": int(alive.sum(axis=1).max()),
            "claw_nan_frames": int(np.isnan(f).any(axis=(1, 2)).sum()),
            "claw_extent_tstar_median_m": round(float(np.median(E[KSTAR])), 4),
            "spray_radius_tstar_m": [round(float(s[KSTAR, :, 3].min()), 4), round(float(s[KSTAR, :, 3].max()), 4)]}
    # V2 は V1 の部分集合か
    f1, f2 = fr["v1_list"], fr["v2_light"]
    mx = 0.0
    for c in L2["claws"]:
        s1 = L1["claws"][c["src_index"]]
        if s1["id"] != c["id"] or s1["vert_count"] != c["vert_count"]:
            raise SystemExit("V2 の爪の並びが V1 と合わない: " + c["id"])
        a = f2[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
        b = f1[:, s1["vert_offset"]:s1["vert_offset"] + s1["vert_count"]]
        mx = max(mx, float(np.nanmax(np.abs(a - b))))
    s1, s2, s3 = sp["v1_list"], sp["v2_light"], sp["v3_exag"]
    cols = []
    for j in range(s2.shape[1]):
        d = np.abs(s1 - s2[:, j:j + 1]).max(axis=(0, 2))
        cols.append((int(np.argmin(d)), float(d.min())))
    rad1 = s1[KSTAR, :, 3]
    top = set(np.argsort(-rad1)[:s2.shape[1]].tolist())
    out["v2_subset"] = {"claws_max_abs_diff_m": mx, "claw_ids": len(L2["claws"]),
                        "spray_columns_exact_in_v1": int(sum(1 for c in cols if c[1] == 0.0)),
                        "spray_is_largest_radius_at_tstar": set(c[0] for c in cols) == top}
    # V3 の爪の広がりの比（t*）と、根元（各爪の最初の頂点）の V1 からの距離
    r = ext["v3_exag"][KSTAR] / np.maximum(ext["v1_list"][KSTAR], 1e-6)
    f3 = fr["v3_exag"]
    root_all, root_vis = [], []
    for i, (c1, c3) in enumerate(zip(L1["claws"], L3["claws"])):
        if c1["id"] != c3["id"]:
            raise SystemExit("V3 の爪の並びが V1 と合わない: " + c3["id"])
        d = np.linalg.norm(f3[:, c3["vert_offset"]].astype(np.float64) - f1[:, c1["vert_offset"]].astype(np.float64), axis=1)
        root_all.append(float(np.nanmax(d)))
        vis = (ext["v1_list"][:, i] > 1e-3) & (ext["v3_exag"][:, i] > 1e-3)
        if vis.any():
            root_vis.append(float(np.nanmax(d[vis])))
    out["v3_claws"] = {"extent_ratio_tstar": {"median": round(float(np.median(r)), 4), "p10": round(float(np.percentile(r, 10)), 4),
                                              "p90": round(float(np.percentile(r, 90)), 4)},
                       "root_vertex_offset_vs_v1_max_m_all_frames": round(max(root_all), 5),
                       "root_vertex_offset_vs_v1_max_m_both_visible": round(max(root_vis), 5),
                       "note_ja": "広がり＝各爪の頂点の、根元の点（各爪の最初の頂点。ds33_claw_anim の頂点の並び）からの距離の最大。"
                                  "根元の点の V1 との距離は、全コマと、両方の版で爪が見えているコマで数えた"}
    # V3 の飛沫：見えている時間（コマ数）の比
    a1, a3 = s1[:, :, 3] > 0, s3[:, :, 3] > 0
    tot1, tot3 = a1.sum(axis=0), a3.sum(axis=0)
    pre1, pre3 = a1[:KSTAR + 1].sum(axis=0), a3[:KSTAR + 1].sum(axis=0)
    rr = s3[KSTAR, :, 3] / np.maximum(s1[KSTAR, :, 3], 1e-9)
    out["v3_spray"] = {
        "visible_to_tstar_ratio": {"median": round(float(np.median(pre3 / pre1)), 4), "mean": round(float((pre3 / pre1).mean()), 4),
                                   "longer": int((pre3 > pre1).sum()), "same": int((pre3 == pre1).sum()), "shorter": int((pre3 < pre1).sum())},
        "visible_all_frames_ratio": {"median": round(float(np.median(tot3 / tot1)), 4), "mean": round(float((tot3 / tot1).mean()), 4)},
        "visible_to_tstar_s_v1": [round(float(np.min(pre1)) / 30, 3), round(float(np.median(pre1)) / 30, 3), round(float(np.max(pre1)) / 30, 3)],
        "visible_to_tstar_s_v3": [round(float(np.min(pre3)) / 30, 3), round(float(np.median(pre3)) / 30, 3), round(float(np.max(pre3)) / 30, 3)],
        "radius_ratio_tstar": [round(float(rr.min()), 4), round(float(np.median(rr)), 4), round(float(rr.max()), 4)],
        "position_tstar_max_diff_vs_v1_m": float(np.abs(s3[KSTAR, :, :3] - s1[KSTAR, :, :3]).max()),
        "note_ja": "見えている＝半径 > 0 のコマ。t* まで＝コマ 0〜360。全コマ（0〜420）は t* の後の保持 60 コマを含む"}
    return out


# ---------------------------------------------------------------- 動画の数え直し
def recount_video():
    res = {}
    for w in VIEWS:
        caps = {v: cv2.VideoCapture(VAR + "/video_raw/ds35_%s_%s_30fps.mp4" % (v, w)) for v in VARS}
        cur = {v: {"full_pct": [], "full_px": [], "crest_pct": [], "crest2_pct": []} for v in VARS[1:]}
        n = 0
        while True:
            fr = {}
            for v, c in caps.items():
                ok, im = c.read()
                if not ok:
                    fr = None
                    break
                fr[v] = im.astype(np.int16)
            if fr is None:
                break
            for v in VARS[1:]:
                d = np.abs(fr[v] - fr["v1_list"]).max(axis=2) > DIFF_T
                x, y, ww, hh = CREST
                x2, y2, w2, h2 = CREST2
                cur[v]["full_pct"].append(round(100.0 * float(d.mean()), 4))
                cur[v]["full_px"].append(int(d.sum()))
                cur[v]["crest_pct"].append(round(100.0 * float(d[y:y + hh, x:x + ww].mean()), 4))
                cur[v]["crest2_pct"].append(round(100.0 * float(d[y2:y2 + h2, x2:x2 + w2].mean()), 4))
            n += 1
        for c in caps.values():
            c.release()
        out = {"frames": n}
        for v in VARS[1:]:
            px = np.array(cur[v]["full_px"])
            first = int(np.argmax(px >= FIRST_PX)) if (px >= FIRST_PX).any() else -1
            out[v] = {"first_frame_ge50px": first, "first_s_ge50px": round(first / 30.0, 3),
                      "at_t11p5": {"full_pct": cur[v]["full_pct"][345], "crest_pct": cur[v]["crest_pct"][345], "crest2_pct": cur[v]["crest2_pct"][345]},
                      "at_t12": {"full_pct": cur[v]["full_pct"][KSTAR], "crest_pct": cur[v]["crest_pct"][KSTAR], "crest2_pct": cur[v]["crest2_pct"][KSTAR]},
                      "curve_full_pct": cur[v]["full_pct"], "curve_crest_pct": cur[v]["crest_pct"]}
        res[w] = out
    return {"rule_ja": "3 版の元の動画（Unity の描画、H.264）をコマごとに比べ、V1 と ΔRGB > 40 の画素の割合。full＝全画面、crest＝variants の部の切り出し "
                       "(x 430, y 40, 800×1000)、crest2＝並べ動画の切り出し (x 430, y 70, 800×640)。最初に全画面で 50 画素以上違うコマも数える",
            "views": res}


def fig_diff_curve(vid, dat, dst):
    """V1 との違いの割合の時間の変化（動画から）と、データで爪・飛沫が出る時刻。"""
    fig = np.full((H, W, 3), 255, np.uint8)
    x0, x1 = 120, 1860
    panels = [("painting_w0", "原画視点・白の帯を切った読み（波頭の切り出し 800×1000）", "curve_crest_pct"),
              ("painting", "原画視点・普通の読み（波頭の切り出し 800×1000）", "curve_crest_pct"),
              ("seat", "座席 v1・普通の読み（全画面）", "curve_full_pct")]
    ph, top0, gap = 240, 110, 70
    col = {"v2_light": (60, 160, 60), "v3_exag": (40, 40, 210)}
    lines = []
    for i, (w, title, key) in enumerate(panels):
        y0 = top0 + i * (ph + gap)
        ymax = max(max(vid["views"][w][v][key]) for v in VARS[1:])
        ymax = max(0.5, float(np.ceil(ymax * 2) / 2))
        cv2.rectangle(fig, (x0, y0), (x1, y0 + ph), (180, 180, 180), 1)
        for t in range(0, 15):
            xx = int(x0 + (x1 - x0) * t / 14.0)
            cv2.line(fig, (xx, y0 + ph), (xx, y0 + ph + 6), (120, 120, 120), 1)
        for tv, cc in [(dat["per_variant"]["v1_list"]["claw_first_visible_s"], (0, 140, 255)),
                       (dat["per_variant"]["v3_exag"]["claw_first_visible_s"], (40, 40, 210)),
                       (dat["per_variant"]["v1_list"]["spray_first_s"], (0, 140, 255)),
                       (dat["per_variant"]["v3_exag"]["spray_first_s"], (40, 40, 210))]:
            xx = int(x0 + (x1 - x0) * tv / 14.0)
            for yy in range(y0, y0 + ph, 8):
                cv2.line(fig, (xx, yy), (xx, min(yy + 4, y0 + ph)), cc, 1)
        for v in VARS[1:]:
            c = np.array(vid["views"][w][v][key])
            pts = np.array([[int(x0 + (x1 - x0) * k / 30.0 / 14.0), int(y0 + ph - ph * min(c[k], ymax) / ymax)] for k in range(len(c))], np.int32)
            cv2.polylines(fig, [pts], False, col[v], 2, cv2.LINE_AA)
            fk = vid["views"][w][v]["first_frame_ge50px"]
            if fk >= 0:
                cv2.circle(fig, (int(x0 + (x1 - x0) * fk / 30.0 / 14.0), y0 + ph), 7, col[v], 2, cv2.LINE_AA)
        lines.append((y0, title, ymax))
    v1c, v3c = dat["per_variant"]["v1_list"]["claw_first_visible_s"], dat["per_variant"]["v3_exag"]["claw_first_visible_s"]
    cap = ["縦軸：V1 と ΔRGB > 40 の画素の割合（%）。緑＝V2、赤＝V3。丸＝全画面で初めて 50 画素以上違うコマ。点線（橙＝V1、赤＝V3）＝データで最初の爪と最初の飛沫が出る時刻。",
           "V3 の爪はデータでは %.2f s から出る（V1 %.2f s）が、動画で V1 と違って見えるのは丸の時刻から（記録の時に Unity の元の動画から数えた）。" % (v3c, v1c)]
    fig = text_lines(fig, ["設計35：3 版の V1 との違いの時間の変化（Unity の元の動画、記録の数え直し）"], 20, 12, size=28)
    for (y0, title, ymax) in lines:
        fig = text_lines(fig, [title + "　縦軸の上端 %.1f %%" % ymax], x0, y0 - 30, size=21)
        for t in range(0, 15, 2):
            xx = int(x0 + (x1 - x0) * t / 14.0)
            fig = text_lines(fig, ["%d s" % t], xx - 12, y0 + ph + 6, size=16)
    fig = text_lines(fig, cap, 20, H - 16 - len(cap) * 30, size=21)
    imwrite(dst, fig)
    return {"src": "record (video_raw)", "dst": rel(dst)}


def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    m = jload(VAR + "/metrics.json")
    r = jload(VAR + "/run.json")
    summ = jload(VAR + "/data/variants_summary.json")
    brep = jload(VAR + "/ds35_build_report.json")
    vrep = jload(VAR + "/ds35_video_report_painting_seat.json")
    vrep0 = jload(VAR + "/ds35_video_report_painting_w0.json")

    # 作り手の記録と、いまのコード・場面が同じか（違えば止まる）
    code_now = {k: sha(REPO + "/" + p) for k, p in CODE_PATHS.items()}
    diff = [k for k in code_now if code_now[k] != r["code_sha256"][k]]
    if diff:
        raise SystemExit("variants の部の run.json とコードの SHA-256 が違う: " + ", ".join(diff))
    if sha(REPO + "/" + r["scene_perf"]["path"]) != r["scene_perf"]["sha256"]:
        raise SystemExit("場面 DS35_Perf.unity が run.json と違う")

    perf = recount_perf()
    dat = recount_data()
    if dat["sha256"]["v1_list"]["claw_frames"] != CLAW_FRAMES_SHA_DS33 or dat["sha256"]["v1_list"]["spray_frames"] != SPRAY_SHA_DS31:
        raise SystemExit("V1 のデータが設計33・31 と違う")
    vid = recount_video()
    # プレイヤー・動画が使ったデータと、いまのデータの SHA-256
    sha_ok = {
        "player": all(perf["table"]["%s/%s" % (v, c)]["claw_frames_sha256"] == dat["sha256"][v]["claw_frames"] and
                      perf["table"]["%s/%s" % (v, c)]["spray_sha256"] == dat["sha256"][v]["spray_frames"]
                      for v in VARS for c in ("desk1080_painting", "desk1080_seat", "proxy_stereo_seat")),
        "video_painting_seat": all(vrep["variantClawSha"][i] == dat["sha256"][v]["claw_frames"] and vrep["variantSpraySha"][i] == dat["sha256"][v]["spray_frames"]
                                   for i, v in enumerate(VARS)),
        "video_painting_w0": all(vrep0["variantClawSha"][i] == dat["sha256"][v]["claw_frames"] and vrep0["variantSpraySha"][i] == dat["sha256"][v]["spray_frames"]
                                 for i, v in enumerate(VARS)),
        "player_exe_now": sha(VAR + "/player/DS35Perf.exe"),
    }
    ind_outs = sorted(x for x in os.listdir(IND) if x.endswith("_out.txt")) if os.path.isdir(IND) else []
    counts = {
        "schema": "GreatWave.DS35.record_counts/1",
        "perf": perf, "data": dat, "video": vid, "sha_consistency": sha_ok,
        "file_times": {
            "build35_created": ctime(B35), "variants_created": ctime(VAR), "tools_ds35_created": ctime(REPO + "/Tools/GWWaveGen/ds35"),
            "ds35_variants_py_created": ctime(REPO + "/Tools/GWWaveGen/ds35/ds35_variants.py"),
            "assets_design35_created": ctime(REPO + "/Unity/Assets/GreatWave/Design35"),
            "first_data_v2": ftime(VAR + "/data/v2_light/claw_layout.json"),
            "v3_claws_written": ftime(VAR + "/data/v3_exag/claw_frames_f32.bin"),
            "v3_spray_first_log": ftime(VAR + "/logs/ds35_variants_exag.log"),
            "v3_spray_regenerated": ftime(VAR + "/data/v3_exag/spray_frames.bin"),
            "build_report": ftime(VAR + "/ds35_build_report.json"),
            "video_report_painting_seat": ftime(VAR + "/ds35_video_report_painting_seat.json"),
            "perf_run1": [perf["runs"]["run1"]["startedUtc"], perf["runs"]["run1"]["finishedUtc"]],
            "perf_run2": [perf["runs"]["run2"]["startedUtc"], perf["runs"]["run2"]["finishedUtc"]],
            "ds35Build_cs_modified": ftime(REPO + "/Unity/Assets/GreatWave/Design35/Editor/DS35Build.cs"),
            "video_report_painting_w0": ftime(VAR + "/ds35_video_report_painting_w0.json"),
            "readme_created": ctime(VAR + "/README_interface.txt"), "readme_modified": ftime(VAR + "/README_interface.txt"),
            "variants_metrics": ftime(VAR + "/metrics.json"), "variants_run": ftime(VAR + "/run.json"),
            "evidence_py_modified": ftime(REPO + "/Tools/GWWaveGen/ds35/ds35_variants_evidence.py"),
            "indep_check_scripts": {x: ftime(IND + "/" + x) for x in sorted(os.listdir(IND)) if x.endswith(".py") or x.endswith(".png")} if os.path.isdir(IND) else {},
            "indep_check_rerun_outputs": {x: ftime(IND + "/" + x) for x in ind_outs},
            "record_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    jdump(REC + "/ds35_record_counts.json", counts)

    # ------------------------------------------------------------ 図
    figs = []
    F = VAR + "/fig/"
    figs.append(fig_single(F + "fig_ds35_stills_painting_crest_w0.png", EV + "/fig_ds35_stills_painting_crest_w0.png",
                           ["原画視点の波頭・白の帯を切った読み（主役波の白を白の前の色で塗るので、白いのは爪と飛沫だけ）。Unity の PC 描画。",
                            "行＝V1 一覧どおり／V2 数を減らした軽量版／V3 大きさ・寿命を誇張した版。列＝t 8・10・11.5・12 s（12 s＝t*）。",
                            "V2 は爪 74 本・飛沫 93 個（V1 の部分集合）。V3 は爪が太く長く、飛沫が大きい。修正1回目で足した読み。"]))
    figs.append(fig_single(F + "fig_ds35_stills_painting_crest.png", EV + "/fig_ds35_stills_painting_crest.png",
                           ["原画視点の波頭・普通の読み（利用者が見る画面）。行と列は上の図と同じ。",
                            "V2 と V1 の違いは、ほとんどが波の根元の前の飛沫の点の数（爪の白と淡い水色は焼き込みの色面の同じ色の模様に重なる）。"]))
    figs.append(fig_single(F + "fig_ds35_stills_seat.png", EV + "/fig_ds35_stills_seat.png",
                           ["座席 v1・普通の読み。行＝V1／V2／V3、列＝t 8・10・11.5・12 s。Unity の PC 描画。"]))
    figs.append(fig_single(F + "fig_ds35_density_window.png", EV + "/fig_ds35_density_window.png",
                           ["描く三角形の数（見えている爪の三角形＋生きている飛沫 × 80）。水色＝性能を測った区間 t 11〜12 s。",
                            "3 版とも 10.57〜10.63 s から最大の平ら（V1・V3 62,912、V2 31,264）で、区間は最大の平らの上にある。"]))
    figs.append(fig_single(F + "fig_ds35_perf_table.png", EV + "/fig_ds35_perf_table.png",
                           ["性能の表（Release プレイヤー、見えるウィンドウ、RTX 3080、Direct3D11、Ultra・4×MSAA・垂直同期なし、run1・run2 の 2 回）。",
                            "RTX3060（対象 PC）の実測ではない。PS VR2 の実機ではない（保留）。"]))
    figs.append(fig_single(F + "fig_ds35_player_screens.png", EV + "/fig_ds35_player_screens.png",
                           ["Release プレイヤーの画面（測定の後に t 11.95 s で撮った、run1）。列＝1920×1080 原画視点／1920×1080 座席 v1／立体の代理の L・R（2064×2208 を縮小）。"]))
    figs.append(fig_single(IND + "/ic35_zoom_normal_t12.png", EV + "/fig_ds35_indep_v2_normal_t12.png",
                           ["進行役の独立の検査：動画から取り出した原画視点・普通の読みの t 12 s（切り出し y 60〜700・x 380〜1180 を 0.8 倍）。",
                            "上＝V1／V2／V3。下＝V1 と ΔRGB > 40 の画素を赤で示した V2（中）と V3（右）。",
                            "V2 の違いは、ほとんどが根元の前の飛沫の点（爪の所の違いはわずか）。V3 は爪の縁と大きい飛沫が違う。"]))
    figs.append(fig_diff_curve(vid, dat, EV + "/fig_ds35_diff_curve.png"))

    # ------------------------------------------------------------ 動画
    vids = []
    for name in ("ds35_variants_3up_painting_crest_30fps.mp4", "ds35_variants_2x2_painting_30fps.mp4", "ds35_variants_2x2_seat_30fps.mp4"):
        src = VAR + "/video/" + name
        dst = EV + "/" + name
        if os.path.getsize(src) > MP4_LIMIT:
            raise SystemExit("動画が 5 MB を超える: " + src)
        shutil.copyfile(src, dst)
        pr = probe(dst)
        vids.append({"src": rel(src), "dst": rel(dst), "bytes": os.path.getsize(dst), "sha256": sha(dst),
                     "width": pr["width"], "height": pr["height"], "frames": int(pr["nb_frames"]), "fps": pr["r_frame_rate"]})
    raw = {}
    for v in VARS:
        for w in VIEWS:
            p = VAR + "/video_raw/ds35_%s_%s_30fps.mp4" % (v, w)
            pr = probe(p)
            raw[rel(p)] = {"bytes": os.path.getsize(p), "sha256": sha(p), "width": pr["width"], "height": pr["height"],
                           "frames": int(pr["nb_frames"]), "fps": pr["r_frame_rate"]}

    # ------------------------------------------------------------ JSON の写し
    json_out = {}
    for src, name in [(VAR + "/metrics.json", "ds35_variants_metrics.json"), (VAR + "/data/variants_summary.json", "ds35_variants_summary.json"),
                      (VAR + "/ds35_build_report.json", "ds35_build_report.json")]:
        jdump(EV + "/" + name, jload(src))
        json_out[name] = {"src": rel(src), "src_sha256": sha(src)}
    vr = {"painting_seat": {k: v for k, v in vrep.items() if k != "videos"}, "painting_w0": {k: v for k, v in vrep0.items() if k != "videos"},
          "videos": [{k: x[k] for k in ("variant", "view", "sha256", "frames", "fps", "seconds")} for x in vrep["videos"] + vrep0["videos"]]}
    jdump(EV + "/ds35_video_reports.json", vr)
    json_out["ds35_video_reports.json"] = {"src": [rel(VAR + "/ds35_video_report_painting_seat.json"), rel(VAR + "/ds35_video_report_painting_w0.json")],
                                           "src_sha256": [sha(VAR + "/ds35_video_report_painting_seat.json"), sha(VAR + "/ds35_video_report_painting_w0.json")],
                                           "note_ja": "動画ごとの静止画の一覧と絶対パスを除いた"}
    perf_small = {"rule_ja": perf["rule_ja"], "runs": perf["runs"], "table": perf["table"],
                  "per_run": {k: [{kk: vv for kk, vv in x.items() if kk not in ("claw_frames_sha256", "spray_sha256")} for x in v] for k, v in perf["per_run"].items()}}
    jdump(EV + "/ds35_perf_recount.json", perf_small)
    json_out["ds35_perf_recount.json"] = {"src": [rel(VAR + "/perf/run1/ds35_run1.json"), rel(VAR + "/perf/run2/ds35_run2.json")],
                                          "src_sha256": [sha(VAR + "/perf/run1/ds35_run1.json"), sha(VAR + "/perf/run2/ds35_run2.json")],
                                          "note_ja": "生の計時の JSON（各 18 MB 前後）から記録の時に数え直した表"}
    counts_small = {k: v for k, v in counts.items() if k not in ("perf", "video")}
    counts_small["video"] = {"rule_ja": vid["rule_ja"],
                             "views": {w: {"frames": vid["views"][w]["frames"],
                                           **{v: {kk: vv for kk, vv in vid["views"][w][v].items() if not kk.startswith("curve")} for v in VARS[1:]}}
                                       for w in VIEWS},
                             "curves_every_15_frames": {w: {v: {"crest_pct": vid["views"][w][v]["curve_crest_pct"][::15],
                                                                "full_pct": vid["views"][w][v]["curve_full_pct"][::15]} for v in VARS[1:]} for w in VIEWS}}
    jdump(EV + "/ds35_record_counts.json", counts_small)
    json_out["ds35_record_counts.json"] = {"src": rel(REC + "/ds35_record_counts.json"), "note_ja": "性能の表は ds35_perf_recount.json。動画の曲線は 15 コマおき（全コマは Git 対象外の元）"}
    for x in ind_outs:
        name = "ds35_indep_" + x[len("ic35_"):]
        shutil.copyfile(IND + "/" + x, EV + "/" + name)
        json_out[name] = {"src": rel(IND + "/" + x), "src_sha256": sha(IND + "/" + x)}

    # ------------------------------------------------------------ metrics.json
    A = m["acceptance"]
    pt = perf["table"]
    vv = vid["views"]
    metrics = {
        "schema": "GreatWave.DS35.metrics/1",
        "number": "設計35",
        "title_ja": "数量・大きさ・寿命を変えて比較する",
        "generated_local": counts["file_times"]["record_run"],
        "evidence_kind_ja": "データは numpy。動画と静止画は Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（RTX 3080）。性能は Release の Windows プレイヤーを"
                            "見えるウィンドウで動かした PC の実測（RTX 3080、Direct3D11）で、対象 PC（RTX3060）の実測でも HMD 実機でもない。"
                            "進行役の独立の検査は、variants の部のコードを使わない numpy/OpenCV。記録の数え直しはこの道具。利用者は確かめていない。",
        "d2_note_ja": m["d2_note_ja"],
        "variants": m["variants"],
        "acceptance": {
            "ja": "計画 §2.2 の設計35 の最小の受入（Q26：最小の受入だけ。修正は 1 回まで）",
            "A1_differences_visible_in_video": {
                "variants_part": {"pixel_diff_pct_vs_v1_stills": A["A1_differences_visible_in_video"]["pixel_diff_pct_vs_v1"],
                                  "rule_ja": A["A1_differences_visible_in_video"]["rule_ja"], "counts": A["A1_differences_visible_in_video"]["counts_differ"]},
                "record_recount_video": {w: {v: {"first_s_ge50px": vv[w][v]["first_s_ge50px"], "t11p5": vv[w][v]["at_t11p5"], "t12": vv[w][v]["at_t12"]}
                                             for v in VARS[1:]} for w in VIEWS},
                "independent_ja": "独立の検査（ds35_indep_a1_diff_out.txt・ds35_indep_a1_curve_out.txt、記録の時に回し直した出力）",
                "verdict": "合格（白の帯を切った読みの段で。普通の読みの V2 は小さい。限界 2）",
            },
            "A2_desktop_1080_mean_ge30fps_p95_le33_3ms": {
                "variants_part": A["A2_desktop_1080"]["values"],
                "record_recount": {k: {"fps_mean_min": pt[k]["fps_mean_min"], "interval_p95_max_ms": pt[k]["interval_p95_max_ms"],
                                       "frames_over_33_3ms": pt[k]["frames_over_33_3ms"], "interval_max_ms": pt[k]["interval_max_ms"]}
                                   for k in pt if "desk1080" in k},
                "verdict": "合格（RTX 3080 の代理）",
            },
            "A3_stereo_proxy_gpu_p95_le8_9ms": {
                "variants_part": A["A3_stereo_proxy_gpu_p95"]["values"],
                "record_recount": {k: {"gpu_p95_max_ms": pt[k]["gpu_p95_max_ms"], "gpu_zero_pct": pt[k]["gpu_zero_pct"],
                                       "interval_p95_max_ms": pt[k]["interval_p95_max_ms"], "eye": pt[k]["eye"]} for k in pt if "proxy" in k},
                "verdict": "合格（2 カメラの代理。SPI・PS VR2 ではない）",
            },
            "A4_one_default_version": {"default": A["A4_default_version"]["default"], "reason_ja": A["A4_default_version"]["reason_ja"],
                                       "v1_data_same_as_ds34": A["A4_default_version"]["v1_data_same_as_ds34"],
                                       "verdict": "合格（進行役の決定、Q24。利用者の段階6確認で変えられる）"},
            "HMD_H1_H3_H4": {"verdict": "保留", "ja": m["hmd_ja"]},
            "all_pass": True,
        },
        "backlog": {"ja": "計画 §2.2 の設計35：81・112・199（代理の測定。判定は RTX3060 の実測がないので保留）", "items": m["backlog"]},
        "regression": {"ja": m["regression_ja"], "ds34_open_decision_ja": "設計34 の色区 133・134（と 267）の読みの決定は、設計34 の記録のとおり（爪の層を除いた読みを採り、爪を入れた読みの不合格は限界）。この番号では変えていない"},
        "densest_interval": m["densest_interval"],
        "v3": {"part": m["v3_details"], "record_recount_claws": dat["v3_claws"], "record_recount_spray": dat["v3_spray"]},
        "record_recount_data": dat["per_variant"],
        "v2_subset": dat["v2_subset"],
        "sha_consistency": sha_ok,
        "fix_rounds": m["fix_rounds"],
        "gpu_zero_note_ja": m["gpu_zero_note_ja"],
        "limits_part_ja": m["limits_ja"],
        "time": {"limit_ja": "Q26 の日程（計画 §2.6）で 2 時間。範囲は最小の受入だけで、修正は 1 回まで",
                 "part_record_ja": m["work_time_ja"], "file_times": counts["file_times"]},
    }
    jdump(EV + "/metrics.json", metrics)

    # ------------------------------------------------------------ run.json
    ev_files = sorted(os.listdir(EV))
    run = {
        "schema": "GreatWave.DS35.run/1",
        "number": "設計35",
        "tools": {"unity": r["tools"]["unity"], "device": perf["runs"]["run1"]["device"], "graphics_api": perf["runs"]["run1"]["graphicsApi"],
                  "cpu": perf["runs"]["run1"]["cpu"], "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": Image.__version__, "ffprobe": FFPROBE},
        "commands_variants_part": r["commands"],
        "commands_record": ["py -3.10 -B Tools/GWWaveGen/ds35/ds35_record.py"],
        "independent_check_ja": "進行役の独立の検査はリポジトリの外のコード。コードの写しと、記録の時に回し直した出力は Git 対象外の Unity/Build/Design/35/indep_check/（ic35_*.py・ic35_*_out.txt）",
        "scene_perf": r["scene_perf"],
        "build_report": {k: brep[k] for k in ("utc", "scene34Sha256Before", "scene34Sha256After", "scenePerfSha256", "buildResult", "buildOptions",
                                              "frameTimingStatsBefore", "frameTimingStatsRestored", "protectedUnchanged", "keepMaterials")},
        "player_exe_sha256": sha_ok["player_exe_now"],
        "player_exe_sha256_at_runs": {t: perf["runs"][t]["exeSha256"] for t in ("run1", "run2")},
        "inputs": r["inputs"],
        "code_sha256": dict({CODE_PATHS[k]: v for k, v in r["code_sha256"].items()},
                            **{"Tools/GWWaveGen/ds35/ds35_record.py": sha(REPO + "/Tools/GWWaveGen/ds35/ds35_record.py")}),
        "variants_data_sha256": dat["sha256"],
        "variants_part_outputs_sha256": {k: v for k, v in r["outputs"].items() if "/fig/" in k or "/video/" in k or k.endswith(".json")},
        "variants_part_run_json_sha256": sha(VAR + "/run.json"),
        "video_raw": raw,
        "figures": figs,
        "videos": vids,
        "json_copies": json_out,
        "evidence_sha256": {f: sha(EV + "/" + f) for f in ev_files if f != "run.json"},
    }
    jdump(EV + "/run.json", run)

    # ------------------------------------------------------------ 確かめ
    bad = []
    for f in os.listdir(EV):
        p = EV + "/" + f
        if f.endswith(".png") and imread(p).shape[:2] != (H, W):
            bad.append(f + " の大きさ")
        if f.endswith(".mp4") and os.path.getsize(p) > MP4_LIMIT:
            bad.append(f + " が 5 MB を超える")
    if bad:
        raise SystemExit("証拠の確かめで不合格: " + "; ".join(bad))
    print("DS35_RECORD_DONE evidence files", len(os.listdir(EV)))
    print(json.dumps({w: {v: (vv[w][v]["first_s_ge50px"], vv[w][v]["at_t11p5"], vv[w][v]["at_t12"]) for v in VARS[1:]} for w in VIEWS}, ensure_ascii=False))
    print(json.dumps({"v3_claws": dat["v3_claws"], "v3_spray": dat["v3_spray"], "v2": dat["v2_subset"], "sha": sha_ok}, ensure_ascii=False))
    print(json.dumps({k: {kk: pt[k][kk] for kk in ("fps_mean_min", "interval_p95_max_ms", "gpu_p95_max_ms", "frames_over_33_3ms", "gpu_zero_pct", "t_played_s", "spray_alive_min")} for k in pt}, ensure_ascii=False))
    print(json.dumps(dat["per_variant"], ensure_ascii=False))


if __name__ == "__main__":
    main()
