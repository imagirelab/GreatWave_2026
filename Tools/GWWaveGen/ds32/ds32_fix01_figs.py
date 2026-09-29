# -*- coding: utf-8 -*-
"""設計32 修正01 の前後図（人が見るため。測定には使わない）。
前＝修正01 の前の初回の出力（Unity/Build/Design/32/list+ids_prefix01/、2026-09-29 20:21 の出力の写し）、後＝修正01 の出力（list+ids/）。
  fig_ds32_fix01_truncated.png：口の規則で短く切りすぎた爪（独立の検査の指摘 2 の 12 本と、同じ見張りで直った爪）の前後
  fig_ds32_fix01_c105_c110.png：C105・C107・C110 の所（指摘 1）の前後
  fig_ds32_fix01_c163_c169.png：C163・C169（指摘 3）の前後
  fig_ds32_fix01_flags.png：修正01 の検査で「根元の先で指が続く」と出た爪と、他の爪の中心線を含む領域の組（記録のみ、仕上げ32）
"""
import json
import os

import cv2
import numpy as np

from ds32_claw_figs import put, label

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/32/list+ids"
PRE = REPO + "/Unity/Build/Design/32/list+ids_prefix01"
FIG = OUT + "/fig"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
INV29 = REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"


def tile(img, claws_by_id, ids, ctx_ids, title, W=620, H=420, pad=18, focus=None):
    pts = []
    for i in (focus or ids):
        c = claws_by_id.get(i)
        if c is None:
            continue
        pts += list(c["region_polygon_ref"]) + [c["tip_ref"], c["root_ref"]]
    pts = np.array(pts, np.float64)
    x0, y0 = pts.min(0) - pad
    x1, y1 = pts.max(0) + pad
    s = min(W / (x1 - x0), H / (y1 - y0))
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    x0, x1 = cx - 0.5 * W / s, cx + 0.5 * W / s
    y0, y1 = cy - 0.5 * H / s, cy + 0.5 * H / s
    A = np.array([[s, 0, -x0 * s], [0, s, -y0 * s]], np.float64)
    canvas = cv2.warpAffine(img, A, (W, H), flags=cv2.INTER_CUBIC, borderValue=(245, 245, 245))
    M = lambda P: (np.asarray(P, np.float64) - [x0, y0]) * s
    for i in ctx_ids:
        c = claws_by_id.get(i)
        if c is None or i in ids:
            continue
        cv2.polylines(canvas, [np.round(M(c["region_polygon_ref"])).astype(np.int32)], True, (170, 170, 170), 1, cv2.LINE_AA)
    for i in ids:
        c = claws_by_id.get(i)
        if c is None:
            continue
        col = (255, 200, 0) if c["origin"].startswith("ds32") else (40, 40, 230)
        cv2.polylines(canvas, [np.round(M(c["region_polygon_ref"])).astype(np.int32)], True, col, 2, cv2.LINE_AA)
        cv2.polylines(canvas, [np.round(M(c["centerline_ref"])).astype(np.int32)], False, (0, 230, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, tuple(np.round(M(c["root_ref"])).astype(int)), 6, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(np.round(M(c["root_ref"])).astype(int)), 6, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(np.round(M(c["tip_ref"])).astype(int)), 4, col, -1, cv2.LINE_AA)
        canvas = label(canvas, M(c["tip_ref"]) + [6, -6], "%s %.0fpx" % (i, c["length_ref_px"]), 15)
    canvas = put(canvas, title if isinstance(title, list) else [title], 15, (6, 4))
    return canvas


def grid(tiles, cols, gap=8):
    H, W = tiles[0].shape[:2]
    rows = []
    for k in range(0, len(tiles), cols):
        r = tiles[k:k + cols]
        r = r + [np.full((H, W, 3), 255, np.uint8)] * (cols - len(r))
        row = r[0]
        for t in r[1:]:
            row = np.concatenate([row, np.full((H, gap, 3), 255, np.uint8), t], 1)
        rows.append(row)
    out = rows[0]
    for r in rows[1:]:
        out = np.concatenate([out, np.full((gap, out.shape[1], 3), 255, np.uint8), r], 0)
    return out


def main():
    os.makedirs(FIG, exist_ok=True)
    img = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)
    pre = {c["id"]: c for c in json.load(open(PRE + "/ds32_claw_inventory.json", encoding="utf-8"))["claws"]}
    inv = json.load(open(OUT + "/ds32_claw_inventory.json", encoding="utf-8"))
    new = {c["id"]: c for c in inv["claws"]}
    chk = json.load(open(OUT + "/ds32_claw_list_checks.json", encoding="utf-8"))["fix01"]
    legend = ("左＝修正01 の前（初回）　右＝修正01 の後　赤＝領域（藍の輪郭線の内側）・黒丸＝根元・黄＝中心線・数字＝中心線の長さ　"
              "灰＝周りの爪の領域　水色＝加えた爪")

    # 1. 短く切りすぎた爪
    changed = [i for i, c in new.items() if c["zone"] == "main" and i in pre
               and (pre[i]["status"] != c["status"] or pre[i]["root_ref"] != c["root_ref"]) and c["status"] in ("root_kept_guard", "mouth_exit")]
    named12 = ["C074", "C075", "C078", "C080", "C081", "C082", "C087", "C092", "C093", "C098", "C106"]
    order = [i for i in named12 if i in changed] + sorted(i for i in changed if i not in named12)
    tiles = []
    for i in order:
        c = new[i]
        g = c.get("short_guard_fix01") or {}
        af = c.get("length_ref_px_af29")
        ctx = [j for j in new if new[j]["zone"] == "main"]
        tiles.append(tile(img, pre, [i], ctx, "前 %s：%s（美術優先29 の %.0f px → %.0f px）" % (i, pre[i]["status"], af or float("nan"), pre[i]["length_ref_px"]),
                          focus=[i]))
        why = {"root_kept_guard": "口と認めず美術優先29 の根元", "mouth_exit": "両側の線が終わる所を口"}[c["status"]]
        tiles.append(tile(img, new, [i], ctx, "後 %s：%s（%.0f px）　最初の候補は %.2f 倍" % (i, why, c["length_ref_px"], g.get("first_cut_over_old", float("nan"))),
                          focus=[i] + ([i] if i not in pre else [])))
    sheet = grid(tiles, 4)
    sheet = put(np.concatenate([np.full((44, sheet.shape[1], 3), 255, np.uint8), sheet], 0),
                ["修正01（独立の検査の指摘 2）：口の規則が先端の鉤のすぐ上や曲がり目を口と読んで短く切った爪 %d 本（指摘の 12 本のうち C107 は C105 に統合）。" % len(order)
                 + "元の長さの 0.5 倍未満に縮む候補は、両側の線が終わる所だけを口と認める", legend], 15, (8, 4))
    cv2.imwrite(FIG + "/fig_ds32_fix01_truncated.png", sheet)

    # 2. C105・C107・C110
    ctx = [j for j in new if new[j]["zone"] == "main"]
    t1 = tile(img, pre, ["C105", "C107", "C110"], ctx, "前：C105（口なし・美術優先29 の根元）が C110 の指と C107 を呑み込む", 900, 640, 14)
    t2 = tile(img, new, ["C105", "C110"], ctx, "後：C105 は房だけ（根元＝房の左の口の中央）、C107 は C105 に統合、C110 は変えない", 900, 640, 14,
              focus=["C105", "C110"])
    sheet = grid([t1, t2], 2, 12)
    cv2.imwrite(FIG + "/fig_ds32_fix01_c105_c110.png", put(np.concatenate([np.full((44, sheet.shape[1], 3), 255, np.uint8), sheet], 0),
                                                            ["修正01（独立の検査の指摘 1）：名指しの所 110 の C105・C107・C110", legend], 15, (8, 4)))

    # 3. C163・C169
    t1 = tile(img, pre, ["C163", "C169"], ctx, "前：C169（利用者の claw071 から）は C163（claw060 から）と同じ指で、根元と先端が逆", 900, 640, 14)
    t2 = tile(img, new, ["C163"], ctx, "後：C169 は重複として消した（ID は欠番、対応表に理由）。C163 は変えない", 900, 640, 14,
              focus=["C163"])
    sheet = grid([t1, t2], 2, 12)
    cv2.imwrite(FIG + "/fig_ds32_fix01_c163_c169.png", put(np.concatenate([np.full((44, sheet.shape[1], 3), 255, np.uint8), sheet], 0),
                                                            ["修正01（独立の検査の指摘 3）：加えた爪どうしの重複", legend], 15, (8, 4)))

    # 4. 修正01 の検査で出た爪（記録のみ）
    fl = [x["id"] for x in chk["continues_past_root_ge_0.6"]]
    pairs = [(x["region_of"], x["centerline_of"]) for x in chk["containment_pairs_ge_0_5"]]
    tiles = []
    for i in fl:
        c = new[i]
        tiles.append(tile(img, new, [i], ctx, "%s（%s）：根元の先 20 px の断面の %.0f%% で両側が藍に閉じる" %
                          (i, c["status"], 100 * c["fix01_continues_past_root"]["fraction"]), focus=[i]))
    for a, b in pairs:
        tiles.append(tile(img, new, [a, b], ctx, "%s の領域が %s の中心線を含む" % (a, b)))
    if tiles:
        sheet = grid(tiles, 4)
        cv2.imwrite(FIG + "/fig_ds32_fix01_flags.png", put(np.concatenate([np.full((44, sheet.shape[1], 3), 255, np.uint8), sheet], 0),
                                                           ["修正01 の検査で出た爪（記録のみ。仕上げ32 で確かめる）。修正01 の後だけを描く。根元の先で体の中の線に当たるだけの誤検出を含む",
                                                            legend.split("　", 1)[1]], 15, (8, 4)))
    print("fix01 figs", len(order))


if __name__ == "__main__":
    main()
