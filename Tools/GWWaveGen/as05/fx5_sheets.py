# -*- coding: utf-8 -*-
"""美術の見本05 の直しの回 fix1（Q33）：見本04（前）・形 A の直す前（A5）と直し（A9）・形 B の直す前（B6）と直し（B10）の Unity の描画を並べた図（見出しは日本語）。
asm5_sheets.py（変えない）の写しで、列を 5 つにし、置き場を直しの回のものにした。
py -3.10 -B Tools/GWWaveGen/as05/fx5_sheets.py [rules]
出力：Unity/Build/Polish/sample05/fix1/assemble/sheets/fx5_*.png（以下の名前の asm5_ を fx5_ に読み替える）
  asm5_1_painting.png        原画視点（爪あり）：原画・見本04・形 A・形 B と、利用者の切り出し（内の縁）・③ の区域の拡大
  asm5_2_painting_clawfree.png 原画視点（爪なし）：白い粒（T5）を見る
  asm5_3_views_claws.png     7 視点（爪あり）  asm5_4_views_clawfree.png 7 視点（爪なし）
  asm5_5_crest_claws.png     波頭の回り台 8 方位（爪あり） asm5_6_crest_clawfree.png（爪なし）
  asm5_7_tt_claws.png        回り台 12 方位（爪あり）  asm5_8_tt_noclaws.png（爪なし）
  asm5_9_rules.png           規則の表（rules_check_A.json・rules_check_B.json）
  asm5_10_t5_left.png        T5 の数え方で残る小さな塊の拡大（何が残っているか）
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402
import s5_targets as T  # noqa: E402

P = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish"
R04 = P + "/sample04/assemble/render/FX1"
R04NC = P + "/sample05/assemble/render/S04_ttnc"
RA0 = P + "/sample05/assemble/render/A5"
RB0 = P + "/sample05/assemble/render/B6"
RA = P + "/sample05/fix1/assemble/render/A9"
RB = P + "/sample05/fix1/assemble/render/B10"
OUT = P + "/sample05/fix1/assemble/sheets"
INK = (24, 30, 40)
BG = (246, 244, 238)
COLS = [("見本04（FX1）", R04), ("形 A 直す前（A5）", RA0), ("形 A 直し（A9）", RA), ("形 B 直す前（B6）", RB0), ("形 B 直し（B10）", RB)]
NC = len(COLS)
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波"), ("side_left", "左の横"), ("side_right", "右の横"),
         ("back65", "後ろ 65°"), ("top", "真上")]


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def im(p, w=None):
    x = Image.open(p).convert("RGB")
    if w:
        x = x.resize((w, int(round(x.height * w / x.width))), Image.LANCZOS)
    return x


def label(img, text, sz=22):
    img = img.copy()
    d = ImageDraw.Draw(img)
    f = font(sz, True)
    w = d.textlength(text, font=f)
    d.rectangle([0, 0, w + 16, sz + 12], fill=(255, 255, 255))
    d.text((8, 4), text, fill=INK, font=f)
    return img


def title(text, sub=None, W=1920):
    h = 96 if sub else 64
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((20, 12), text, fill=INK, font=font(32, True))
    if sub:
        d.text((22, 58), sub, fill=(70, 74, 80), font=font(20))
    return img


def grid(cells, ncol, cw, gap=6):
    rows = [cells[i:i + ncol] for i in range(0, len(cells), ncol)]
    ch = max(c.height for c in cells)
    W = ncol * cw + (ncol + 1) * gap
    out = Image.new("RGB", (W, len(rows) * (ch + gap) + gap), BG)
    for r, rr in enumerate(rows):
        for k, c in enumerate(rr):
            out.paste(c, (gap + k * (cw + gap), gap + r * (ch + gap)))
    return out


def vstack(parts):
    W = max(p.width for p in parts)
    out = Image.new("RGB", (W, sum(p.height for p in parts)), BG)
    y = 0
    for p in parts:
        out.paste(p, (0, y)); y += p.height
    return out


def save(img, name):
    os.makedirs(OUT, exist_ok=True)
    img.save(OUT + "/" + name, optimize=True)
    print("書いた", OUT + "/" + name, img.size)


def painting_sheet():
    cw = 940
    pd = Image.fromarray(T.painting_disp())
    cells = [label(pd.resize((cw, 529), Image.LANCZOS), "原画（同じ表示の画素へ）")]
    cw = 630
    cells = [label(pd.resize((cw, 354), Image.LANCZOS), "原画（同じ表示の画素へ）")]
    for nm, r in COLS:
        cells.append(label(im(r + "/views/painting_t120_claws.png", cw), nm))
    top = grid(cells, 3, cw)
    # 拡大：利用者の切り出し（内の縁）と ③ の区域
    x0, y0, x1, y1 = M.T6_CROP
    crops = []
    srcs = [("原画", pd)] + [(nm.split("（")[0], Image.open(r + "/views/painting_t120_claws.png").convert("RGB")) for nm, r in COLS]
    for nm, s in srcs:
        c = s.crop((x0 - 20, y0 - 10, x1 + 40, y1 + 10))
        c = c.resize((int(c.width * 1.6), int(c.height * 1.6)), Image.LANCZOS)
        crops.append(label(c, nm + "：内の縁（T6）", 18))
    r3 = np.round(np.asarray(M.A.ref_to_px(np.array([[0, 1110], [630, 1849]], float)))).astype(int)
    rx0, ry0 = max(r3[0, 0], 0), max(r3[0, 1] - 20, 0)
    rx1, ry1 = r3[1, 0] + 20, min(r3[1, 1] + 10, 1079)
    crops3 = []
    for nm, s in srcs:
        c = s.crop((rx0, ry0, rx1, ry1))
        sc = 470.0 / c.width
        c = c.resize((470, int(c.height * sc)), Image.LANCZOS)
        crops3.append(label(c, nm + "：③ の区域", 18))
    mid = grid(crops, 6, max(c.width for c in crops))
    low = grid(crops3, 6, 470)
    save(vstack([title("美術の見本05 の直しの回（Q33）：原画視点（爪あり、t*）", "上：原画・見本04・形 A 直す前／直し・形 B 直す前／直し。中：利用者の切り出し（唇の下の内の縁、ここに白を置かない）。下：③（最も左の小さな区域）", W=3000),
                 top, mid, low]), "fx5_1_painting.png")


def rows_sheet(name, ttl, sub, items, cw=480):
    cw = 480
    parts = [title(ttl, sub, W=NC * cw + (NC + 1) * 6)]
    hdr = Image.new("RGB", (NC * cw + (NC + 1) * 6, 34), BG)
    d = ImageDraw.Draw(hdr)
    for k, (nm, _) in enumerate(COLS):
        d.text((6 + k * (cw + 6) + 4, 6), nm, fill=INK, font=font(20, True))
    parts.append(hdr)
    for lab, paths in items:
        cells = []
        for p in paths:
            if p and os.path.isfile(p):
                cells.append(im(p, cw))
            else:
                cells.append(Image.new("RGB", (cw, int(cw * 9 / 16)), (200, 200, 200)))
        cells[0] = label(cells[0], lab, 20)
        parts.append(grid(cells, NC, cw))
    save(vstack(parts), name)


def main():
    painting_sheet()
    rows_sheet("fx5_2_painting_clawfree.png", "原画視点（爪なし）：三つの層の形・白い粒（T5）", "左から見本04・形 A 直す前／直し・形 B 直す前／直し",
               [("原画視点・爪なし", [r + "/views/painting_t120_clawfree.png" for _, r in COLS])], cw=630)
    for tag, nm, ttl in (("claws", "fx5_3_views_claws.png", "7 視点（爪あり、t*）"), ("clawfree", "fx5_4_views_clawfree.png", "7 視点（爪なし、t*）")):
        rows_sheet(nm, ttl, "左から見本04・形 A 直す前／直し・形 B 直す前／直し。PC のオフスクリーン描画（HMD 実機ではない）",
                   [(ja, [r + "/views/%s_t120_%s.png" % (v, tag) for _, r in COLS]) for v, ja in VIEWS])
    for tag, nm, ttl in (("claws", "fx5_5_crest_claws.png", "波頭の回り台 8 方位（爪あり）"), ("clawfree", "fx5_6_crest_clawfree.png", "波頭の回り台 8 方位（爪なし）")):
        rows_sheet(nm, ttl, "方位 0 = 原画の側、反時計回り。左から見本04・形 A 直す前／直し・形 B 直す前／直し",
                   [("方位 %d°" % a, [r + "/crest/t120_az%03d_%s.png" % (a, tag) for _, r in COLS]) for a in range(0, 360, 45)])
    rows_sheet("fx5_7_tt_claws.png", "回り台 12 方位（爪あり）", "方位 0 = 原画の側。左から見本04・形 A 直す前／直し・形 B 直す前／直し",
               [("方位 %d°" % a, [r + "/tt/t120_az%03d_claws.png" % a for _, r in COLS]) for a in range(0, 360, 30)])
    rows_sheet("fx5_8_tt_noclaws.png", "回り台 12 方位（爪なし）", "方位 0 = 原画の側。左から見本04・形 A 直す前／直し・形 B 直す前／直し",
               [("方位 %d°" % a, [R04NC + "/tt/t120_az%03d_noclaws.png" % a, RA0 + "/tt/t120_az%03d_noclaws.png" % a, RA + "/tt/t120_az%03d_noclaws.png" % a,
                                  RB0 + "/tt/t120_az%03d_noclaws.png" % a, RB + "/tt/t120_az%03d_noclaws.png" % a])
                for a in range(0, 360, 30)])
    rules_sheet()


def t5_sheet():
    """形 A・B の描画（爪なし）に残る白・水色の小さな塊（T5 の数え方で波の本体の上）を、1 つずつ拡大して並べる（何が残っているかを見るため）。"""
    cells = []
    for v, r in (("A9", RA), ("B10", RB)):
        found = []
        for part in ("v", "ct"):
            p = P + "/sample05/fix1/assemble/measure/t5t6_%s_%s.json" % (v, part)
            if not os.path.isfile(p):
                continue
            pv = json.load(open(p, encoding="utf-8"))["T5"]["per_view"]
            for name, d in pv.items():
                for x, y, a in d.get("body_first", []):
                    found.append((a, name, x, y))
        found.sort(key=lambda q: -q[0])
        for a, name, x, y in found[:24]:
            if name.startswith("crest"):
                ip = r + "/crest/t120_az%03d_clawfree.png" % int(name[5:])
            elif name.startswith("tt"):
                ip = r + "/tt/t120_az%03d_noclaws.png" % int(name[2:])
            else:
                ip = r + "/views/%s_t120_clawfree.png" % name
            s = Image.open(ip).convert("RGB")
            c = s.crop((x - 40, y - 28, x + 40, y + 28)).resize((320, 224), Image.NEAREST)
            d2 = ImageDraw.Draw(c)
            d2.ellipse([160 - 26, 112 - 26, 160 + 26, 112 + 26], outline=(220, 30, 30), width=2)
            cells.append(label(c, "形 %s・%s（%d 画素）" % (v[0], name, a), 15))
    if not cells:
        return
    save(vstack([title("白い粒（T5）の数え方で波の本体の上に残る小さな塊（大きい順に各形 24 まで）",
                       "直しの回の形 A（A9）・形 B（B10）の爪なしの描画。1 つずつ 4 倍に拡大（赤い丸が塊の中心）"),
                 grid(cells, 6, 320)]), "fx5_10_t5_left.png")


def rules_sheet():
    rc = {}
    for v in ("A", "B"):
        for sfx, tag in (("_before_fix", "前"), ("", "後")):
            p = P + "/sample05/rules_check_%s%s.json" % (v, sfx)
            if os.path.isfile(p):
                rc[v + tag] = json.load(open(p, encoding="utf-8"))
    if not rc:
        return
    names = [("G1", "G1 投影なし・帯の伸び"), ("G2", "G2 輪郭の関門"), ("S4", "S4 背は一つの山"), ("S8", "S8 出っ張りなし"),
             ("S9", "S9 左の白は低い・④ は wave4"), ("S10", "S10 峰に沿う長さ"), ("S11", "S11 三つの層"), ("T5", "T5 白い粒なし"),
             ("T6", "T6 内の縁に白なし"), ("C2", "C2 爪の形"), ("C3", "C3 爪の影"), ("K-top", "いちばん高い峰のまま"), ("K-boat", "一艘目の船が隠れない")]
    cols = [("A前", "形 A 直す前（A5）"), ("A後", "形 A 直し（A9）"), ("B前", "形 B 直す前（B6）"), ("B後", "形 B 直し（B10）")]
    W = 2900
    rowsH = 46
    img = Image.new("RGB", (W, 120 + rowsH * (len(names) + 1) + 40), BG)
    d = ImageDraw.Draw(img)
    d.text((20, 14), "美術の見本05 の直しの回（Q33）：測る規則（形 A・形 B の直す前と直し）", fill=INK, font=font(32, True))
    d.text((22, 60), "合 = 測れる規則を通る。美術が届いたかは利用者が決める（Q29・Q30）", fill=(70, 74, 80), font=font(20))
    y = 110
    d.text((20, y), "規則", fill=INK, font=font(22, True))
    for k, (_, ja) in enumerate(cols):
        d.text((330 + k * 640, y), ja, fill=INK, font=font(22, True))
    y += rowsH
    for key, ja in names:
        d.text((20, y), ja, fill=INK, font=font(20))
        for k, (v, _) in enumerate(cols):
            r = rc.get(v, {}).get("rules", {}).get(key, {})
            vd = r.get("verdict")
            txt = {"pass": "合", "fail": "否"}.get(vd, str(vd))
            col = (40, 120, 60) if vd == "pass" else (180, 50, 40)
            d.text((330 + k * 640, y), txt + "  " + brief(key, r), fill=col, font=font(15))
        y += rowsH
    save(img, "fx5_9_rules.png")


def brief(key, r):
    try:
        if key == "G2":
            return " ".join("%s %.2f" % (k, v["claws"]) for k, v in r["gates"].items())
        if key == "S11":
            a = r["asked_by_orchestrator"]
            bad = [i for g in a.values() for i, ok in g.items() if not ok]
            return "must %s、否：%s" % (r["must_pass"], "・".join(r.get("must_fail_ids", bad)) if r.get("must_fail_ids", bad) else "なし")
        if key == "G1":
            return "コード・記録 %s、帯の伸び %s（%d 三角形）" % (
                "合" if r["code_and_record_checks_pass"] else "否", "合" if r["surface_stretch_not_worse"] else "否",
                r["surface_stretch_where"]["this_mesh"]["patterned_tri_w_outside"])
        if key == "T5":
            return "原画視点 船の縁を除き %s、全 32 視点 %s（見本04 %s）" % (
                r["painting_body_blobs_excluding_boat_edges"], r["all_views_total"], r["sample04_all_views_total"])
        if key == "T6":
            return "切り出しの白・水色 %s" % (r["painting_crop_pale_share"],)
        if key == "S10":
            d = r["vs_sample04_AS04F_union"]["diff_m"]
            lo = [r["ratio_vs_sample03"][k]["union"] for k in ("0.1", "0.2", "0.3", "0.4", "0.5")]
            return "高い帯の差 %.2f m、低い帯 見本03 の %.2f〜%.2f 倍" % (max(abs(d[k]) for k in ("0.6", "0.7", "0.8", "0.9")), min(lo), max(lo))
        if key == "K-boat":
            return "船の画素の比 %s" % r.get("ratio")
        if key == "C3":
            return "IoU p10・p50・min %s" % r.get("iou_painting_p10_p50_min_sample02")
    except Exception:  # noqa
        return ""
    return ""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        t5_sheet()
        rules_sheet()
    else:
        main()
