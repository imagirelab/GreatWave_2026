# -*- coding: utf-8 -*-
"""設計32：爪の一覧の修正の図（人が見るため。測定には使わない）。
  fig_ds32_named_before_after.png：利用者が名指しした爪（83・84・85、109・中5・110、127 の下）の前（美術優先29）と後（設計32）。
  fig_ds32_rows_{upper,middle,boat,bregion}.png：列ごとの重ね図（緑の細線＝美術優先29 の白の多角形、赤＝設計32 の領域、黒点＝新しい根元、
      黄＝新しい中心線、水色＝加えた爪）。右側の爪は触らず「低優先・未修正」と書く。
  fig_ds32_user100.png：利用者の100本の位置合わせ（根元→先端の矢印。緑＝対応、水色＝加えた、灰＝対応なし）。
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/32/list+ids"
FIG = OUT + "/fig"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
INV29 = REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"


def font(sz):
    for p in ("C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def put(img, lines, size=22, xy=(12, 8), bg=(30, 30, 30)):
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    f = font(size)
    y = xy[1]
    for ln in lines:
        bb = d.textbbox((xy[0], y), ln, font=f)
        d.rectangle([bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2], fill=bg)
        d.text((xy[0], y), ln, font=f, fill=(255, 255, 255))
        y += size + 8
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def label(img, xy, text, size=16, col=(255, 255, 255)):
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    f = font(size)
    x, y = int(xy[0]), int(xy[1])
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=col)
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def view(img, x0, y0, x1, y1, W=1920, H=1080):
    s = min(W / (x1 - x0), H / (y1 - y0))
    crop = img[int(y0):int(y1), int(x0):int(x1)]
    big = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)
    canvas = np.full((H, W, 3), 245, np.uint8)
    canvas[:big.shape[0], :big.shape[1]] = big[:H, :W]
    return canvas, (lambda P: (np.asarray(P, np.float64) - [x0, y0]) * s), s


def draw_claw(img, M, c, old, lw=2, show_old=True, show_id=True):
    if show_old and old is not None:
        cv2.polylines(img, [np.round(M(old["outline_polygon_ref"])).astype(np.int32)], True, (60, 170, 60), 1, cv2.LINE_AA)
        cv2.circle(img, tuple(np.round(M(old["root_ref"])).astype(int)), 5, (60, 170, 60), 2, cv2.LINE_AA)
    col = (255, 200, 0) if c["origin"].startswith("ds32") else (40, 40, 230)
    if c.get("region_polygon_ref"):
        cv2.polylines(img, [np.round(M(c["region_polygon_ref"])).astype(np.int32)], True, col, lw, cv2.LINE_AA)
    cv2.polylines(img, [np.round(M(c["centerline_ref"])).astype(np.int32)], False, (0, 230, 255), 1, cv2.LINE_AA)
    cv2.circle(img, tuple(np.round(M(c["root_ref"])).astype(int)), 5, (0, 0, 0), -1, cv2.LINE_AA)
    cv2.circle(img, tuple(np.round(M(c["tip_ref"])).astype(int)), 3, col, -1, cv2.LINE_AA)
    return img


def main():
    os.makedirs(FIG, exist_ok=True)
    img = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)
    inv = json.load(open(OUT + "/ds32_claw_inventory.json", encoding="utf-8"))
    old = {c["id"]: c for c in json.load(open(INV29, encoding="utf-8"))["claws"]}
    corr = json.load(open(OUT + "/ds32_user100_correspondence.json", encoding="utf-8"))
    cl = {c["id"]: c for c in inv["claws"]}
    legend = "緑の細線＝美術優先29（白の指だけ）・緑の輪＝旧根元　赤＝設計32 の領域（藍の輪郭線の内側、影を含む）・黒点＝新しい根元（口の中央）・黄＝中心線　水色＝加えた爪"

    # 1. 名指しの前後
    below127 = [c["id"] for c in inv["claws"] if c.get("seed") == "127の下"]
    groups = [("83・84・85（影）", ["C083", "C084", "C085"]), ("109（中5）・110（起点）と C105・C107（修正01）", ["C109", "C110", "C105", "C107"]),
              ("127 の下（取りこぼし）", ["C127"] + below127)]
    tiles = []
    for title, ids in groups:
        pts = []
        for i in ids:
            c = cl.get(i)
            if c is not None:
                pts += list(c["region_polygon_ref"]) + [c["tip_ref"], c["root_ref"]]
            if i in old:
                pts += old[i]["outline_polygon_ref"]
        pts = np.array(pts)
        x0, y0 = pts.min(0) - 25
        x1, y1 = pts.max(0) + 25
        for mode in ("before", "after"):
            canvas, M, s = view(img, x0, y0, x1, y1, 940, 520)
            for i in ids:
                c = cl.get(i)
                if c is None:   # 修正01 で消した爪（統合・重複）：後の図には理由だけを書く
                    if mode == "after" and i in old:
                        rm = next((x for x in inv.get("removed_claws", []) if x["id"] == i), {})
                        canvas = label(canvas, M(old[i]["tip_ref"]) + [6, -6], "%s → %s に%s（修正01）" %
                                       (i, rm.get("merged_into") or rm.get("duplicate_of") or "?", rm.get("kind", "")), 18, (255, 160, 160))
                    continue
                if mode == "before":
                    if i in old:
                        o = old[i]
                        cv2.polylines(canvas, [np.round(M(o["outline_polygon_ref"])).astype(np.int32)], True, (60, 170, 60), 2, cv2.LINE_AA)
                        cv2.polylines(canvas, [np.round(M(o["centerline_ref"])).astype(np.int32)], False, (255, 255, 255), 1, cv2.LINE_AA)
                        cv2.circle(canvas, tuple(np.round(M(o["root_ref"])).astype(int)), 6, (60, 170, 60), -1, cv2.LINE_AA)
                        canvas = label(canvas, M(o["tip_ref"]) + [6, -6], i, 18)
                else:
                    draw_claw(canvas, M, c, None, 2, False)
                    canvas = label(canvas, M(c["tip_ref"]) + [6, -6], i + ("（加えた）" if c["origin"].startswith("ds32") else ""), 18,
                                   (255, 220, 120) if c["origin"].startswith("ds32") else (255, 255, 255))
            canvas = put(canvas, [("前：美術優先29　" if mode == "before" else "後：設計32　") + title], 20)
            tiles.append(canvas)
    rows_img = [np.concatenate([tiles[k], np.full((520, 40, 3), 255, np.uint8), tiles[k + 1]], 1) for k in range(0, len(tiles), 2)]
    sheet = np.concatenate([np.concatenate([r, np.full((12, r.shape[1], 3), 255, np.uint8)], 0) for r in rows_img], 0)
    sheet = put(np.concatenate([np.full((60, sheet.shape[1], 3), 255, np.uint8), sheet], 0), [legend], 17, (10, 14))
    cv2.imwrite(FIG + "/fig_ds32_named_before_after.png", sheet)

    # 2. 列ごとの重ね図
    def row_fig(name, sel, title):
        pts = np.concatenate([np.array(cl[i]["region_polygon_ref"] + [cl[i]["tip_ref"], cl[i]["root_ref"]]) for i in sel])
        x0, y0 = pts.min(0) - 30
        x1, y1 = pts.max(0) + 30
        canvas, M, s = view(img, x0, y0, x1, y1)
        for i in sel:
            draw_claw(canvas, M, cl[i], old.get(i), 2, True)
        for i in sel:
            c = cl[i]
            canvas = label(canvas, M(c["tip_ref"]) + [5, -5], i[1:], max(11, min(18, int(10 * s))),
                           (255, 220, 120) if c["origin"].startswith("ds32") else (255, 255, 255))
        sh = [cl[i]["shadow"]["included_new"] for i in sel if cl[i].get("shadow") and cl[i]["shadow"]["enclosed_px"] >= 20]
        canvas = put(canvas, [title + "（%d 本、うち加えた %d 本）　囲まれた影のうち領域に入る割合：最小 %.2f・中央値 %.2f" %
                              (len(sel), sum(1 for i in sel if cl[i]["origin"].startswith("ds32")), min(sh) if sh else float("nan"),
                               float(np.median(sh)) if sh else float("nan")), legend], 18)
        cv2.imwrite(FIG + "/fig_ds32_rows_%s.png" % name, canvas)

    by = {}
    for c in inv["claws"]:
        by.setdefault(c["row"], []).append(c["id"])
    row_fig("upper", [i for i in by.get("上側", []) if not cl[i]["b_region_q16"] or cl[i]["origin"] == "af29"], "上側の列")
    row_fig("middle", by.get("途中", []), "途中の列")
    row_fig("boat", by.get("船側", []), "船側の列")
    bsel = [c["id"] for c in inv["claws"] if c["b_region_q16"]]
    if bsel:
        row_fig("bregion", bsel, "b区域（Q16 の浪尖、左肩の第二の波頭）の爪")
    # 右側（触らない）
    rs = by.get("右側", [])
    if rs:
        pts = np.concatenate([np.array(cl[i]["region_polygon_ref"]) for i in rs])
        x0, y0 = pts.min(0) - 30
        x1, y1 = pts.max(0) + 30
        canvas, M, s = view(img, x0, y0, x1, y1)
        for i in rs:
            cv2.polylines(canvas, [np.round(M(cl[i]["region_polygon_ref"])).astype(np.int32)], True, (200, 60, 200), 2, cv2.LINE_AA)
        canvas = put(canvas, ["右側の爪（%d 本）：低優先・未修正（美術優先29 の読みB のまま。ブラッシュアップの最後）" % len(rs)], 20)
        cv2.imwrite(FIG + "/fig_ds32_rows_right_untouched.png", canvas)

    # 3. 利用者の100本
    canvas, M, s = view(img, 150, 150, 2750, 1700)
    for e in corr["claws"]:
        if not e.get("root_ref"):
            continue
        col = {"対応": (60, 190, 60), "追加": (255, 200, 0)}.get(e["status"], (150, 150, 150))
        a = M(e["root_ref"]); b = M(e["tip_ref"])
        cv2.arrowedLine(canvas, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), col, 2, cv2.LINE_AA, tipLength=0.3)
        canvas = label(canvas, b + [3, -3], e["user_id"][4:], 12, (255, 255, 255))
    sm = corr["summary"]
    canvas = put(canvas, ["利用者の爪100本を DP130155 へテンプレート照合で合わせた根元→先端（緑＝一覧と対応 %d、水色＝加えた %d、灰＝対応なし %d）"
                          % (sm["matched_existing"], sm["added_from_user"], sm["not_matched"]),
                          "画像・マスクは複製していない（読み取りのみ）。残差は ds32_user100_registration.json"], 18)
    cv2.imwrite(FIG + "/fig_ds32_user100.png", canvas)
    print("figs done")


if __name__ == "__main__":
    main()
