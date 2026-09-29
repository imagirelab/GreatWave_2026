# -*- coding: utf-8 -*-
"""設計36 の記録：証拠（Docs/Evidence/Design/36/）を作り、metrics.json と run.json を書く。

値は次の出力から読む（どれも Git 対象外）。
  - 調色板の部：Unity/Build/Design/36/palette/（ds36_palette_metrics.json・ds36_colour_chart.csv・ds36_claw_shadow_per_claw.json・
    unity/ds36_render_report.json・unity/ds30_tstar_regress.json・unity/tstar_sym_t28_*/tstar_sym.json・fig/・unity/video/）
  - 進行役の独立の検査：Unity/Build/Design/36/indep_check/（ic36_claws.json・ic36_flicker.json・eval/・frames/）
この道具で新しく数えるのは、次の数え直しだけ（Unity/Build/Design/36/record/ds36_record_counts.json にも書く）。
  - 回帰の表の照合：調色板の部と独立の検査の ds30_tstar_regress.json の数値の葉が同じか
  - 藍濃の 1 段：t* の原画視点で (34,63,96) と (35,64,97) の画素と、その境（4 近傍）の画素。設計34 の同じ画像と比べる
  - 1 コマだけの色の跳び：設計36・設計34・設計30 の動画で、A→B→A の色区の跳び（3×3 で 4 画素以上まとまったもの）
  - 作業の時刻（ファイルの時刻）
図は 1920×1080 の枠に収め、余白に日本語の説明を入れる。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds36/ds36_record.py
"""
import csv
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess

import PIL
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Design"
B36 = B + "/36"
PAL = B36 + "/palette"
IND = B36 + "/indep_check"
REC = B36 + "/record"
EV = REPO + "/Docs/Evidence/Design/36"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
FONT = "C:/Windows/Fonts/meiryo.ttc"
MP4_LIMIT = 5 * 1024 * 1024
W, H = 1920, 1080

CODE_PATHS = [
    "Tools/GWWaveGen/ds36/ds36_palette_prep.py",
    "Tools/GWWaveGen/ds36/ds36_palette_eval.py",
    "Tools/GWWaveGen/ds36/run_ds36_unity.ps1",
    "Tools/GWWaveGen/ds36/ds36_record.py",
    "Unity/Assets/GreatWave/Design36/Editor/DS36Render.cs",
    "Unity/Assets/GreatWave/Design36/Scripts/DS36ClawPalette.cs",
    "Unity/Assets/GreatWave/Design36/Scripts/DS36SeaPalette.cs",
    "Unity/Assets/GreatWave/Design36/Shaders/DS36_Claw_Palette.shader",
    "Unity/Assets/GreatWave/Design36/Shaders/DS36_Claw_TDepth.shader",
    "Unity/Assets/GreatWave/Design36/Scenes/DS36_Palette.unity",
]
# 調色板（主役波の材質の値）と、美術優先27 の平塗りの藍濃（AF27_Flat_ai_dark.mat の _Color 0.13333334, 0.24705882, 0.3764706）
PALETTE = [("白", (248, 243, 223)), ("淡い水色", (198, 215, 203)), ("藍中", (44, 105, 147)), ("藍濃", (35, 64, 97)), ("藍の線", (71, 80, 95))]
AI_DARK = (35, 64, 97)
AI_DARK_AF27 = (34, 63, 96)


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


def fig_img(im, dst, caption, src_desc):
    """画像を 1920×1080 に収め、下の余白に日本語の説明を入れる。"""
    ch = 20 + len(caption) * 34
    small, s = fit(im, W, H - ch)
    cv = np.full((H, W, 3), 245, np.uint8)
    x0 = (W - small.shape[1]) // 2
    cv[0:small.shape[0], x0:x0 + small.shape[1]] = small
    cv = text_lines(cv, caption, 24, small.shape[0] + 12, size=24)
    imwrite(dst, cv)
    return {"src": src_desc, "scale": round(s, 4), "dst": rel(dst), "sha256": sha(dst)}


def fig_single(src, dst, caption, crop=None):
    im = imread(src)
    if crop is not None:
        y0, y1 = crop
        im = im[y0:y1]
    d = fig_img(im, dst, caption, rel(src) + ("" if crop is None else " [行 %d:%d]" % crop))
    d["src_sha256"] = sha(src)
    return d


def ftime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")


def ctime(p):
    return datetime.datetime.fromtimestamp(os.path.getctime(p)).strftime("%Y-%m-%d %H:%M:%S")


def probe(p):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,nb_frames,r_frame_rate,codec_name", "-of", "json", p],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


# ---------------------------------------------------------------- 回帰の表の照合
def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, p + "[%d]" % i)
    elif isinstance(o, bool) or o is None:
        yield p, o
    elif isinstance(o, (int, float)):
        yield p, float(o)


def recount_regress_match():
    a = dict(leaves(jload(PAL + "/unity/ds30_tstar_regress.json")))
    b = dict(leaves(jload(IND + "/eval/ds30_tstar_regress.json")))
    keys = sorted(set(a) | set(b))
    nums = [k for k in keys if isinstance(a.get(k), float) or isinstance(b.get(k), float)]
    same = [k for k in nums if a.get(k) == b.get(k)]
    diff = [k for k in nums if a.get(k) != b.get(k) and not k.endswith("ids_sha256")]
    return {"numeric_leaves": len(nums), "equal": len(same), "different": diff,
            "builder": rel(PAL + "/unity/ds30_tstar_regress.json"), "builder_sha256": sha(PAL + "/unity/ds30_tstar_regress.json"),
            "indep": rel(IND + "/eval/ds30_tstar_regress.json"), "indep_sha256": sha(IND + "/eval/ds30_tstar_regress.json")}


# ---------------------------------------------------------------- 藍濃の 1 段
def step_counts(im_bgr):
    rgb = im_bgr[:, :, ::-1].astype(np.int32)
    a = (rgb == np.array(AI_DARK_AF27)).all(-1)
    b = (rgb == np.array(AI_DARK)).all(-1)
    ba = np.zeros_like(a)
    bb = np.zeros_like(b)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        ba |= a & np.roll(np.roll(b, dy, 0), dx, 1)
        bb |= b & np.roll(np.roll(a, dy, 0), dx, 1)
    return a, b, ba, bb


def recount_step():
    p36 = PAL + "/unity/t28_claws/t28/render/af28r01_painting.png"
    p34 = B + "/34/unity3/main/t28_claws/t28/render/af28r01_painting.png"
    preg = PAL + "/unity/chart/ds36_region_painting_t12.00s.png"
    out = {"definition_ja": "t* の原画視点（1920×1080、爪あり）で、(34,63,96) と (35,64,97) にちょうど等しい画素と、4 近傍で互いに接する画素（両側の合計）。",
           "inputs": {}}
    res = {}
    for tag, p in (("ds36", p36), ("ds34", p34)):
        im = imread(p)
        a, b, ba, bb = step_counts(im)
        res[tag] = {"px_34_63_96": int(a.sum()), "px_35_64_97": int(b.sum()), "boundary_px_34_side": int(ba.sum()),
                    "boundary_px_35_side": int(bb.sum()), "boundary_px_both": int(ba.sum() + bb.sum())}
        out["inputs"][tag] = {"path": rel(p), "sha256": sha(p)}
    # 設計36 の領域の画像（主役波 赤・near 緑・far 青・爪 マゼンタ・飛沫 シアン・ほか）で、どちらの色がどの領域にあるか
    reg = imread(preg)[:, :, ::-1].astype(np.int32)
    out["inputs"]["ds36_region"] = {"path": rel(preg), "sha256": sha(preg)}
    names = {(255, 0, 0): "hero", (0, 255, 0): "near", (0, 0, 255): "far", (255, 0, 255): "claws", (0, 255, 255): "spray"}
    im = imread(p36)
    a, b, ba, bb = step_counts(im)
    by = {}
    for nm, m in (("px_34_63_96", a), ("px_35_64_97", b)):
        cols, cnt = np.unique(reg[m].reshape(-1, 3), axis=0, return_counts=True)
        d = {}
        for c, n in zip(cols, cnt):
            d[names.get(tuple(int(x) for x in c), "other")] = d.get(names.get(tuple(int(x) for x in c), "other"), 0) + int(n)
        by[nm] = d
    res["ds36_by_region"] = by
    out.update(res)
    # 図：左＝描画、右＝(35,64,97) を水色、(34,63,96) を橙、境を赤
    vis = (im.astype(np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    vis[b] = (230, 190, 120)
    vis[a] = (40, 150, 245)
    edge = cv2.dilate((ba | bb).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    vis[edge] = (0, 0, 220)
    pair = np.hstack([cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA), cv2.resize(vis, (960, 540), interpolation=cv2.INTER_AREA)])
    return out, pair


def recount_other_diff():
    """t* の原画視点（爪あり）で、設計34 と設計36 の描画が違う画素のうち、主役波・海・爪・飛沫の領域の外のもの（船・富士・空などが変わっていないか）。"""
    p36 = PAL + "/unity/t28_claws/t28/render/af28r01_painting.png"
    p34 = B + "/34/unity3/main/t28_claws/t28/render/af28r01_painting.png"
    preg = PAL + "/unity/chart/ds36_region_painting_t12.00s.png"
    a = imread(p36).astype(np.int32)
    b = imread(p34).astype(np.int32)
    reg = imread(preg)[:, :, ::-1].astype(np.int32)
    named = np.zeros(reg.shape[:2], bool)
    for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255)):
        named |= (reg == np.array(c)).all(-1)
    diff = (a != b).any(-1)
    outside = diff & ~named
    dist = cv2.distanceTransform((~named).astype(np.uint8), cv2.DIST_L2, 5)
    d = dist[outside]
    return {"definition_ja": "t* の原画視点（爪あり、1920×1080）で、設計34 と設計36 の描画の RGB が違う画素のうち、設計36 の領域の画像で主役波・near・far・爪・飛沫でない画素と、"
                             "そこから最も近い領域の画素までの距離（px、ユークリッド）。",
            "diff_px": int(diff.sum()), "outside_named_px": int(outside.sum()),
            "outside_within_2px": int((d <= 2.0).sum()), "outside_within_3px": int((d <= 3.0).sum()),
            "outside_max_dist_px": round(float(d.max()), 3) if d.size else 0.0,
            "inputs": {"ds36": {"path": rel(p36), "sha256": sha(p36)}, "ds34": {"path": rel(p34), "sha256": sha(p34)},
                       "region": {"path": rel(preg), "sha256": sha(preg)}}}


# ---------------------------------------------------------------- 1 コマだけの色の跳び
PAL4 =np.array([c for _, c in PALETTE[:4]], np.int32)


def cls(fr):
    f = fr[:, :, ::-1].astype(np.int32)
    d = ((f[:, :, None, :] - PAL4[None, None]) ** 2).sum(-1)
    k = d.argmin(-1).astype(np.int8)
    k[d.min(-1) > 12 ** 2] = -1
    return k


def flicker(path):
    cap = cv2.VideoCapture(path)
    prev2 = prev1 = None
    n = 0
    per = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        k = cls(cv2.resize(fr, (960, 540), interpolation=cv2.INTER_AREA))
        if prev2 is not None:
            tog = (prev2 >= 0) & (prev1 >= 0) & (k >= 0) & (prev2 == k) & (prev1 != k)
            cnt = cv2.filter2D(tog.astype(np.uint8), -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT)
            per.append((n - 1, int((tog & (cnt >= 4)).sum())))
        prev2, prev1 = prev1, k
        n += 1
    arr = np.array(per)
    win = arr[(arr[:, 0] >= 318) & (arr[:, 0] <= 341)]
    return {"path": rel(path), "sha256": sha(path), "frames": n,
            "cluster_px_max": int(arr[:, 1].max()), "cluster_px_max_frame": int(arr[np.argmax(arr[:, 1]), 0]),
            "frames_gt50": int((arr[:, 1] > 50).sum()),
            "window_318_341_max": int(win[:, 1].max()), "window_318_341_max_frame": int(win[np.argmax(win[:, 1]), 0]),
            "after_frame_362_max": int(arr[arr[:, 0] >= 362][:, 1].max())}


def flicker_regions(frame=330):
    """設計36 の動画のコマ 330（t 11.0 s）の跳びを、同じ時刻の領域の画像（chart/ds36_region_*_t11.00s.png）で領域ごとに分ける。"""
    names = {(255, 0, 0): "hero", (0, 255, 0): "near", (0, 0, 255): "far", (255, 0, 255): "claws", (0, 255, 255): "spray"}
    out = {"frame": frame, "note_ja": "前後のコマ 329・331 と比べたコマ 330 の跳び（上と同じ読み）。領域の画像を 960×540 へ最近傍で縮めて分けた。"}
    for v in ("painting", "seat", "seat_toward_wave"):
        rp = PAL + "/unity/chart/ds36_region_%s_t11.00s.png" % v
        reg = cv2.resize(imread(rp), (960, 540), interpolation=cv2.INTER_NEAREST)[:, :, ::-1]
        cap = cv2.VideoCapture(PAL + "/unity/video/ds36_palette_%s_30fps.mp4" % v)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame - 1)
        ks = [cls(cv2.resize(cap.read()[1], (960, 540), interpolation=cv2.INTER_AREA)) for _ in range(3)]
        tog = (ks[0] >= 0) & (ks[1] >= 0) & (ks[2] >= 0) & (ks[0] == ks[2]) & (ks[1] != ks[2])
        cnt = cv2.filter2D(tog.astype(np.uint8), -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT)
        big = tog & (cnt >= 4)
        d = {}
        for y, x in zip(*np.nonzero(big)):
            nm = names.get(tuple(int(c) for c in reg[y, x]), "other")
            d[nm] = d.get(nm, 0) + 1
        out[v] = {"total": int(big.sum()), "by_region": d, "region_image": rel(rp), "region_sha256": sha(rp)}
    return out


def recount_flicker():
    vids = {
        "ds36_painting": PAL + "/unity/video/ds36_palette_painting_30fps.mp4",
        "ds36_seat": PAL + "/unity/video/ds36_palette_seat_30fps.mp4",
        "ds36_seat_toward_wave": PAL + "/unity/video/ds36_palette_seat_toward_wave_30fps.mp4",
        "ds34_all_painting": B + "/34/unity3/video_run/video/ds34_all_painting_30fps.mp4",
        "ds34_all_seat": B + "/34/unity3/video_run/video/ds34_all_seat_30fps.mp4",
        "ds30_painting": B + "/30/unity/single_fix1/video/ds30_painting_30fps.mp4",
        "ds30_seat": B + "/30/unity/single_fix1/video/ds30_seat_30fps.mp4",
        "ds30_seat_toward_wave": B + "/30/unity/single_fix1/video/ds30_seat_toward_wave_30fps.mp4",
    }
    out = {"definition_ja": "960×540 に縮めたコマを調色板の 4 色（白・淡い水色・藍中・藍濃。距離 12 以内）へ分け、コマ n−1 と n+1 が同じ色区でコマ n だけ違う画素のうち、"
                            "3×3 の中に 4 画素以上まとまったもの（ic36_flicker.py と同じ読み）。コマ番号は 0 から（t = n/30 s）。"}
    for k, p in vids.items():
        out[k] = flicker(p)
        print("flicker", k, out[k]["cluster_px_max"], out[k]["window_318_341_max"], flush=True)
    out["ds36_frame330_by_region"] = flicker_regions(330)
    print("flicker regions", json.dumps(out["ds36_frame330_by_region"], ensure_ascii=False)[:400], flush=True)
    return out


# ---------------------------------------------------------------- 色票の図
def chart_rows():
    rows = []
    with open(PAL + "/ds36_colour_chart.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def fig_colour_chart(rows, dst, pal_L):
    cv = np.full((H, W, 3), 245, np.uint8)
    sw_w, sw_h, x = 330, 110, 40
    labels = []
    for (nm, c), L in zip(PALETTE, pal_L):
        cv2.rectangle(cv, (x, 30), (x + sw_w, 30 + sw_h), (c[2], c[1], c[0]), -1)
        labels.append((x, ["%s #%02X%02X%02X" % (nm, c[0], c[1], c[2]), "sRGB (%d,%d,%d)  L* %.1f" % (c[0], c[1], c[2], L)]))
        x += sw_w + 40
    for lx, t in labels:
        cv = text_lines(cv, t, lx, 30 + sw_h + 6, size=20, gap=4)
    pick = [("painting", "12.0", ["hero", "sea_near", "sea_far", "claws", "spray"]), ("seat", "12.0", ["hero", "claws", "spray"]),
            ("seat_low", "12.0", ["hero", "sea_near", "claws"]), ("seat_toward_wave", "10.0", ["hero", "sea_near", "claws"])]
    vname = {"painting": "原画視点", "seat": "座席 v1", "seat_low": "座席の低い視点", "seat_toward_wave": "座席から波の方向"}
    rname = {"hero": "主役波", "sea_near": "周りの海 near", "sea_far": "周りの海 far", "claws": "爪", "spray": "飛沫"}
    heads = ["視点・時刻", "領域", "画面の割合 %", "白 %", "淡い水色 %", "藍中 %", "藍濃 %", "線 %", "調色板の外 %", "平均 L*"]
    xs = [40, 400, 640, 820, 940, 1100, 1220, 1340, 1450, 1640]
    idx = {(r["view"], "%.1f" % float(r["t"]), r["region"]): r for r in rows}
    used = []
    y = 222
    for x0, h in zip(xs, heads):
        cv = text_lines(cv, [h], x0, y, size=21)
    cv2.line(cv, (40, y + 32), (1780, y + 32), (120, 120, 120), 1)
    y += 40
    for v, t, regs in pick:
        for rg in regs:
            r = idx.get((v, t, rg))
            if r is None:
                continue
            used.append((v, t, rg))
            vals = [float(r[k]) for k in ("frame_share_pct", "share_white_pct", "share_mizuiro_pct", "share_ai_mid_pct",
                                          "share_ai_dark_pct", "share_line_pct", "share_off_palette_pct", "mean_L")]
            cells = ["%s t %s s" % (vname[v], t.rstrip("0").rstrip(".")), rname[rg], "%.2f" % vals[0]] + ["%.1f" % q for q in vals[1:]]
            for x0, cell in zip(xs, cells):
                cv = text_lines(cv, [cell], x0, y, size=21)
            y += 31
    cv = text_lines(cv, [], 40, y)
    cv = text_lines(cv, ["色票の表（ds36_colour_chart.csv の抜粋。割合は領域の画素に対する %、平均 L* は描画の画素の CIELAB の L* の平均）。Unity の PC 描画。",
                         "領域は Unity の平塗りの領域の画像（主役波・near・far・爪・飛沫）で分けた。調色板の外はアンチエイリアスの縁・線・空との混ざり。",
                         "t 4〜12 s × 4 視点の全 122 行は ds36_colour_chart.csv。線（藍の線）の色は設計38 で使う。"], 40, 900, size=21, gap=8)
    imwrite(dst, cv)
    return {"src": rel(PAL + "/ds36_colour_chart.csv"), "src_sha256": sha(PAL + "/ds36_colour_chart.csv"), "rows": ["/".join(u) for u in used],
            "dst": rel(dst), "sha256": sha(dst)}


# ---------------------------------------------------------------- main
def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    m = jload(PAL + "/ds36_palette_metrics.json")
    rr = jload(PAL + "/unity/ds36_render_report.json")

    # 調色板の部の出力と、いまのコード・場面・動画が同じか（違えば止まる）
    checks = {
        "eval_code": sha(REPO + "/Tools/GWWaveGen/ds36/ds36_palette_eval.py") == m["code_sha256"],
        "scene": sha(REPO + "/Unity/Assets/GreatWave/Design36/Scenes/DS36_Palette.unity") == rr["scene36Sha256"],
        "claw_palette": sha(PAL + "/prep/ds36_claw_palette.json") == rr["clawPaletteSha256"],
        "videos": all(sha(v["path"]) == v["sha256"] for v in rr["videos"]),
        "protectedUnchanged": bool(rr["protectedUnchanged"]) and rr["changedFiles"] == [],
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise SystemExit("調色板の部の出力といまのファイルが違う: " + ", ".join(bad))

    counts = {"schema": "GreatWave.DS36.record_counts/1", "consistency": checks}
    counts["regress_match"] = recount_regress_match()
    step, step_pair = recount_step()
    counts["ai_dark_step_tstar"] = step
    counts["other_region_diff_vs_ds34_tstar"] = recount_other_diff()
    print("other diff", counts["other_region_diff_vs_ds34_tstar"]["outside_named_px"], counts["other_region_diff_vs_ds34_tstar"]["outside_max_dist_px"], flush=True)
    counts["flicker"] = recount_flicker()
    counts["file_times"] = {
        "build36_created": ctime(B36), "palette_created": ctime(PAL), "started_txt": ctime(PAL + "/_started.txt"),
        "tools_ds36_created": ctime(REPO + "/Tools/GWWaveGen/ds36"), "assets_design36_created": ctime(REPO + "/Unity/Assets/GreatWave/Design36"),
        "tdepth_shader_meta_created": ctime(REPO + "/Unity/Assets/GreatWave/Design36/Shaders/DS36_Claw_TDepth.shader.meta"),
        "unity_r1_facing_created": ctime(PAL + "/unity_r1_facing"),
        "render_report": ftime(PAL + "/unity/ds36_render_report.json"),
        "regress_json": ftime(PAL + "/unity/ds30_tstar_regress.json"),
        "palette_metrics": ftime(PAL + "/ds36_palette_metrics.json"),
        "started_txt_modified": ftime(PAL + "/_started.txt"),
        "readme_modified": ftime(PAL + "/README_interface.txt"),
        "indep_check_created": ctime(IND),
        "indep_check_files": {x: ftime(IND + "/" + x) for x in sorted(os.listdir(IND)) if os.path.isfile(IND + "/" + x)},
        "indep_frames_last": max(ftime(IND + "/frames/" + x) for x in os.listdir(IND + "/frames")),
        "record_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    jdump(REC + "/ds36_record_counts.json", counts)

    # ------------------------------------------------------------ 図
    figs = []
    F = PAL + "/fig/"
    figs.append(fig_single(F + "fig_ds36_before_after.png", EV + "/fig_ds36_before_after_painting.png",
                           ["左＝設計34（前）、右＝設計36。上＝原画視点 t 12 s（t*）、下＝座席から波の方向 t 10 s。Unity の PC 描画（HMD ではない）。",
                            "周りの海（手前の小波・右の高い波を含む）：設計30 の仮の 2 色（白と藍濃）を、t* の相対の高さの 4 段（白・淡い水色・藍中・藍濃）に替えた。",
                            "主役波は設計29修正01 の焼き込みのまま。爪は t* の原画視点へ投影した原画の色区で塗る（原画視点では焼き込みと同じ色になる）。"], crop=(0, 1080)))
    figs.append(fig_single(F + "fig_ds36_before_after.png", EV + "/fig_ds36_before_after_low.png",
                           ["左＝設計34（前）、右＝設計36。上＝座席の低い視点 t 12 s（t*）、下＝原画視点 t 8 s（形成の途中）。Unity の PC 描画。",
                            "座席の低い視点の t* では、谷の縁の藍中の段はほとんど見えない（周りの海 near の画素の藍中 1.9%）。谷は藍濃の平らな面のまま（限界 1）。",
                            "t 8 s の右の高い波は、t* の高さで決めた帯（白・淡い水色・藍中）が頂点について動く（今の高さでは決めない。限界 2）。"], crop=(1080, 2160)))
    figs.append(fig_single(F + "fig_ds36_claw_shadow_tstar.png", EV + "/fig_ds36_claw_shadow_tstar.png",
                           ["爪の内側の影の色の受入（B）。t* の原画視点の波頭。左＝原画の色区、中＝描画の色区 ID（爪あり）、",
                            "右＝爪の画素：緑＝原画が影（白でない）で描画の色区が原画と同じ、赤＝違う、灰＝原画が白。",
                            "影の画素の一致 1,657／1,763（0.9399）。影が 20 px 以上の 25 本は、描画の影の最多の色区＝一覧の色区が 25／25。"]))
    figs.append(fig_colour_chart(chart_rows(), EV + "/fig_ds36_colour_chart.png", [p["value_L"] for p in m["palette"]]))
    figs.append(fig_single(F + "fig_ds36_formation_frames.png", EV + "/fig_ds36_formation_frames.png",
                           ["形成の途中の調色板。行＝原画視点／座席の低い視点／座席から波の方向、列＝t 4・6・8・10・12 s。Unity の PC 描画。",
                            "主役波・周りの海・爪・飛沫は、どのコマも同じ 4 色（白・淡い水色・藍中・藍濃）と藍の線。",
                            "海の帯は t* の高さで頂点ごとに決めたので、形成の間は頂点について動く（右の高い波の t 4〜8 s。限界 2、仕上げ30）。"]))
    step_fig = fig_img(step_pair, EV + "/fig_ds36_aidark_step_tstar.png",
                       ["藍濃の 1 段（記録の数え直し）。原画視点 t 12 s（t*）、爪あり。左＝描画、右＝(35,64,97)（主役波・周りの海の藍濃）を水色、",
                        "(34,63,96)（美術優先27 の平塗りの藍濃 AF27_Flat_ai_dark を使う物）を橙、互いに接する画素を赤で示した。",
                        "境の画素（両側）は 設計36 %d・設計34 %d。1 段（RGB で 1）なので目では見えないが、段はまだ残る（限界 6）。" % (
                            step["ds36"]["boundary_px_both"], step["ds34"]["boundary_px_both"])],
                       rel(PAL + "/unity/t28_claws/t28/render/af28r01_painting.png"))
    figs.append(step_fig)
    fl = counts["flicker"]
    fr = fl["ds36_frame330_by_region"]
    figs.append(fig_single(IND + "/frames/flicker_painting_328.png", EV + "/fig_ds36_indep_flicker_painting_f328.png",
                           ["進行役の独立の検査：原画視点の動画のコマ 328（t ≈ 10.93 s）。左＝コマ、右＝前後のコマと色区が違う 1 コマだけの跳びを赤。",
                            "ほとんどが主役波の白と淡い水色の模様の跳び（設計36 の前からある）。コマ 318〜341 の最大：設計36 %d・設計34 %d・設計30 %d 画素（960×540、記録の数え直し）。" % (
                                fl["ds36_painting"]["window_318_341_max"], fl["ds34_all_painting"]["window_318_341_max"], fl["ds30_painting"]["window_318_341_max"]),
                            "コマ 330 の領域ごと：主役波 %d・爪 %d 画素。爪の跳びは、爪に原画の模様を投影したことで加わった分。t* の後（コマ 362 から）は 0。" % (
                                fr["painting"]["by_region"].get("hero", 0), fr["painting"]["by_region"].get("claws", 0))]))
    figs.append(fig_single(IND + "/frames/flicker_seat_toward_wave_328.png", EV + "/fig_ds36_indep_flicker_seat_toward_wave_f328.png",
                           ["進行役の独立の検査：座席から波の方向の動画のコマ 328（t ≈ 10.93 s）。左＝コマ、右＝1 コマだけの跳びを赤。",
                            "主役波の模様の跳びに加え、手前の小波の裾の鋸歯と、右の波の淡い水色と藍中の段の境が跳ぶ（設計36 で海を 4 段にして加わった）。",
                            "コマ 330 の領域ごと：主役波 %d・周りの海 near %d・爪 %d 画素。全コマの最大：設計36 %d・設計30 %d 画素（960×540、記録の数え直し。限界 5）。" % (
                                fr["seat_toward_wave"]["by_region"].get("hero", 0), fr["seat_toward_wave"]["by_region"].get("near", 0),
                                fr["seat_toward_wave"]["by_region"].get("claws", 0),
                                fl["ds36_seat_toward_wave"]["cluster_px_max"], fl["ds30_seat_toward_wave"]["cluster_px_max"])]))
    figs.append(fig_single(IND + "/frames/stw_345.png", EV + "/fig_ds36_indep_foot_streaks_f345.png",
                           ["進行役の独立の検査：座席から波の方向の動画のコマ 345（t 11.5 s）。主役波の前面の足の縦の筋が見える（設計28 から渡された描画の傷）。",
                            "設計36 では直していない。設計38（外殻線と色の境）か仕上げ28 へ渡す（限界 7）。下の手前の小波の裾の藍中の段の境は、形の鋸歯（段階5 の S5-2・S5-3）。"]))

    # ------------------------------------------------------------ 動画
    vids = []
    for v in rr["videos"]:
        src = v["path"].replace("\\", "/")
        dst = EV + "/" + os.path.basename(src)
        if os.path.getsize(src) > MP4_LIMIT:
            raise SystemExit("動画が 5 MB を超える: " + src)
        shutil.copyfile(src, dst)
        pr = probe(dst)
        vids.append({"view": v["view"], "src": rel(src), "dst": rel(dst), "bytes": os.path.getsize(dst), "sha256": sha(dst),
                     "width": pr["width"], "height": pr["height"], "frames": int(pr["nb_frames"]), "fps": pr["r_frame_rate"]})

    # ------------------------------------------------------------ JSON・表の写し
    copies = [
        (PAL + "/ds36_palette_metrics.json", "ds36_palette_metrics.json"),
        (PAL + "/ds36_colour_chart.csv", "ds36_colour_chart.csv"),
        (PAL + "/ds36_claw_shadow_per_claw.json", "ds36_claw_shadow_per_claw.json"),
        (PAL + "/unity/ds36_render_report.json", "ds36_render_report.json"),
        (PAL + "/unity/ds30_tstar_regress.json", "ds36_tstar_regress.json"),
        (PAL + "/unity/tstar_sym_t28_claws/tstar_sym.json", "ds36_tstar_sym_claws.json"),
        (PAL + "/unity/tstar_sym_t28_white/tstar_sym.json", "ds36_tstar_sym_no_claws.json"),
        (PAL + "/prep/ds36_palette_prep.json", "ds36_palette_prep.json"),
        (IND + "/ic36_claws.json", "ds36_indep_claws.json"),
        (IND + "/ic36_flicker.json", "ds36_indep_flicker.json"),
        (REC + "/ds36_record_counts.json", "ds36_record_counts.json"),
    ]
    copied = []
    for src, name in copies:
        shutil.copyfile(src, EV + "/" + name)
        copied.append({"src": rel(src), "dst": rel(EV + "/" + name), "bytes": os.path.getsize(src), "sha256": sha(src)})

    # ------------------------------------------------------------ metrics.json
    reg = m["regression"]["sets"]
    ref = m["regression"]["reference"]
    acc = m["claw_shadow_acceptance"]
    ic = jload(IND + "/ic36_claws.json")
    metrics = {
        "schema": "GreatWave.Design36.metrics/1",
        "number": "設計36：限定色と少数の陰影段階（色票、面積・明度）",
        "evidence_kind_ja": "Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と numpy/OpenCV。HMD 実機ではない（PS VR2 は保留）。",
        "palette": m["palette"],
        "acceptance": {
            "claw_shadow_colour_matches_list": {
                "A_hidden_faces_list_class": acc["A_hidden_faces_list_class_match"],
                "B_painting_tstar": acc["B_painting_tstar"],
                "criterion_ja": acc["criterion_ja"],
                "indep": {"list_class_rederived": ic["list_class_rederived"], "B_painting_tstar_claw_px": ic["B_painting_tstar_claw_px"],
                          "whole_region_agreement_vs_painting": ic["whole_region_agreement_vs_painting"], "claw_mask_check": ic["claw_mask_check"],
                          "hidden_faces": ic["hidden_faces"]},
                "pass": acc["pass"],
            },
            "no_regression_265_266_267": {
                s: {"265_dE00": reg[s]["265_dE00"], "266_ai_mid_bands_sym": reg[s]["266_ai_mid_bands_sym"],
                    "266_mizuiro_bands_sym": reg[s]["266_mizuiro_bands_sym"], "267_white_bands_sym": reg[s]["267_white_bands_sym"],
                    "267_white_bands_strict": reg[s]["267_white_bands_strict"], "vs_29r01": reg[s]["no_regression_265_266_267_vs_29r01"]}
                for s in ("t28_claws", "t28_white")},
            "reference_29r01": ref["29R01"], "reference_ds34_claws": ref["DS34_claws"],
            "pass": all(all(reg[s]["no_regression_265_266_267_vs_29r01"].values()) for s in ("t28_claws", "t28_white")),
        },
        "record_only_200_root_white": m["root_white_200"],
        "regression_plan_2_0": {s: reg[s]["plan_2_0"] for s in ("t28_claws", "t28_white")},
        "regression_sym_rows_diff_vs_29r01_worst_px": {s: reg[s]["sym_worst_diff_vs_29r01_px"] for s in ("t28_claws", "t28_white")},
        "regression_verdicts_sym": {s: reg[s]["verdicts_sym"] for s in ("t28_claws", "t28_white")},
        "regress_json_match_builder_vs_indep": {k: counts["regress_match"][k] for k in ("numeric_leaves", "equal", "different")},
        "stage6_condition_4_2_1": {"ds34_claws": {"133": ref["DS34_claws"]["verdicts_sym"]["133"], "134": ref["DS34_claws"]["verdicts_sym"]["134"],
                                                  "267_white_bands_sym": ref["DS34_claws"]["267_white_bands_sym"]},
                                   "ds36_claws": {"133": reg["t28_claws"]["verdicts_sym"]["133"], "134": reg["t28_claws"]["verdicts_sym"]["134"],
                                                  "267_white_bands_sym": reg["t28_claws"]["267_white_bands_sym"]}},
        "claw_colours_by_view": m["claw_colours_by_view"],
        "trough_record": m["trough_record"],
        "sea": {"params": m["sea_params"], "prep": m["sea_prep"]},
        "face_check": m["face_check"],
        "ai_dark_step_tstar": step,
        "other_region_diff_vs_ds34_tstar": counts["other_region_diff_vs_ds34_tstar"],
        "flicker": counts["flicker"],
        "backlog": {"200": "記録のみ（上の record_only_200_root_white）", "265": "回帰なし", "266": "回帰なし", "267": "回帰なし（両側の読みの白の帯 0）",
                    "121": "触っていない（仕上げ36）", "175": "不合格のまま（29修正01 と同じ値。仕上げ36）"},
        "hmd": "保留（PS VR2 の導入は利用者の手。Q24）。Mock の両眼はこの番号では描いていない。",
        "fix_rounds": {"used": 1, "limit_q26": 1,
                       "round1_ja": "t* の向きで見える面を決めた版（unity_r1_facing/）で 133 が両側の読みで 8.259 px の不合格 → t* の爪の奥行きの表で見える面を決める版で合格"},
        "time": {"box_q26_h": 2, "build_start": "2026-09-30 03:30:55", "build_end": "2026-09-30 04:32:09",
                 "file_times": counts["file_times"]},
    }
    jdump(EV + "/metrics.json", metrics)

    # ------------------------------------------------------------ run.json
    run = {
        "schema": "GreatWave.Design36.run/1",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/ds36/ds36_palette_prep.py",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds36/run_ds36_unity.ps1 -Method GreatWave.Design36.EditorTools.DS36Render.Render -Log run5 -Extra \"-ds36Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/36/palette/unity\"",
            "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/36/palette/unity --sets t28_claws,t28_white",
            "py -3.10 -B Tools/GWWaveGen/ds36/ds36_palette_eval.py",
            "py -3.10 -B Tools/GWWaveGen/ds36/ds36_record.py",
        ],
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                        "pillow": PIL.__version__, "unity": rr["unity"], "device": rr["device"], "graphicsApi": rr["graphicsApi"],
                        "os": platform.platform()},
        "code_sha256": {p: sha(REPO + "/" + p) for p in CODE_PATHS},
        "scene": {"path": "Unity/Assets/GreatWave/Design36/Scenes/DS36_Palette.unity", "sha256": rr["scene36Sha256"]},
        "inputs_sha256": dict(m["inputs_sha256"], **{
            "Unity/Build/Design/36/palette/prep/ds36_claw_label_sdf_3840x2160_rgba8.bin": sha(PAL + "/prep/ds36_claw_label_sdf_3840x2160_rgba8.bin"),
            "Unity/Build/Design/36/palette/prep/ds36_sea_ramp_256_rgba8.bin": sha(PAL + "/prep/ds36_sea_ramp_256_rgba8.bin"),
            "Unity/Build/Design/36/palette/prep/ds36_sea_uv3_near_f32.bin": sha(PAL + "/prep/ds36_sea_uv3_near_f32.bin"),
            "Unity/Build/Design/36/palette/prep/ds36_sea_uv3_far_f32.bin": sha(PAL + "/prep/ds36_sea_uv3_far_f32.bin"),
        }),
        "sea_packages": {k: m["sea_prep"][k]["package"] for k in ("near", "far")},
        "protected_files": rr["protectedFiles"], "protectedUnchanged": rr["protectedUnchanged"],
        "render_seconds_total": rr["secondsTotal"],
        "figures": figs, "videos": vids, "copies": copied,
        "not_used_ja": "参照モデル・利用者の解算・写真のフォルダー・Blender・Houdini は使っていない。爪形分析のフォルダーは、作る部も検査もこの記録も開いていない"
                       "（コミットの一覧の点検で、ファイルの大きさと SHA-256 を読み取りのみで照合しただけ）。",
        "record_run": counts["file_times"]["record_run"],
    }
    jdump(EV + "/run.json", run)
    print("DS36_RECORD_DONE figs=%d vids=%d copies=%d" % (len(figs), len(vids), len(copied)))


if __name__ == "__main__":
    main()
