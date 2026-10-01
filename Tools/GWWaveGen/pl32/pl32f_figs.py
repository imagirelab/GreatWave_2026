# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1 の図（1920×1080）。原画はリポジトリの Docs/References/Met_JP1847_DP130155.jpg の切り抜き。Unity の図は PL32Render の
PC オフスクリーン描画（HMD ではない）。前＝仕上げ31（r_before）、作る部＝仕上げ32 の作る部（r_after）、修正01＝この回（fix01/r_fix01）。

  fig_pl32f_spots.png    審査で指摘された所：座席 t* の左端・座席から波の方向 t* の左上・座席 t* の b区域の稜・原画視点 t 10.5 s と t* の b区域
  fig_pl32f_bregion.png  b区域の爪（［利用者の言葉］Q16・Q21）：原画｜作る部｜修正01｜修正01 の爪なし と数（線の成分・水色の版の割合・閉じた輪）
  fig_pl32f_reps.png     代表10形と船側中央の爪 C095：原画（一覧の領域）｜作る部｜修正01 の原画視点 t* と、爪の帯の投影の数（95・97・123〜126）
  fig_pl32f_list.png     一覧の直し：利用者の 100 本から加えた爪（主浪の左下・手前の波）、根元を延ばした爪、帯にしなかった爪（根元が白の範囲の外）
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32f_figs.py --out Docs/Evidence/Polish/32
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
import pl32_figs as F  # noqa: E402
from pl30_sheets import font, label, head, fit  # noqa: E402

B = REPO + "/Unity/Build/Polish/32"
RUNS = [("前（仕上げ31）", B + "/r_before"), ("作る部（仕上げ32）", B + "/r_after"), ("修正01", B + "/fix01/r_fix01")]
INVF = B + "/fix01/list/ds32_claw_inventory.json"


def crop(path, box, sc):
    im = cv2.imread(path)
    x0, y0, x1, y1 = box
    return cv2.resize(im[y0:y1, x0:x1], None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST if sc >= 2 else cv2.INTER_AREA)


def fig_spots(out):
    rows = [("座席 t*（左端：藍の上の白い棒・くねった白・稜の線の箱）", "views/seat_t120_asis.png", (0, 520, 700, 1080)),
            ("座席から波の方向 t*（左上：白い斜めの棒と鉤）", "views/seat_toward_wave_t120_asis.png", (0, 0, 800, 400)),
            ("原画視点 t 10.5 s（b区域：伸びる途中の爪の閉じた輪＝米粒）", "views/painting_t105_asis.png", (220, 380, 560, 580)),
            ("原画視点 t*（b区域）", "views/painting_t120_asis.png", (220, 380, 560, 580))]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32 修正01｜審査で指摘された所（同じ視点・同じ時刻・作品のまま）：左 前（仕上げ31）｜中 作る部（仕上げ32）｜右 修正01",
         "Unity の PC オフスクリーン描画（HMD ではない）。座席・座席から波の方向の左の 2 段は審査の切り抜きと同じ所。原画視点は b区域を拡大。")
    tw = 632
    y = 64
    for name, rel, box in rows:
        x0, y0, x1, y1 = box
        th = int(round(tw * (y1 - y0) / float(x1 - x0)))
        th = min(th, 226)
        for k, (lab, root) in enumerate(RUNS):
            t = fit(F.pil(cv2.imread(os.path.join(root, rel))[y0:y1, x0:x1]), (tw, th))
            im.paste(t, (4 + k * (tw + 4), y + 22))
            label(d, 4 + k * (tw + 4) + 4, y + 26, lab, 13)
        d.text((8, y + 2), name, fill=(30, 30, 30), font=font(15))
        y += th + 26
        if y > 1000:
            break
    p = os.path.join(out, "fig_pl32f_spots.png"); im.save(p); return p


def fig_bregion(out, meas):
    D = F.paint_disp()
    box = (160, 380, 800, 620)
    sc = 1.45
    cr = lambda a: cv2.resize(a[box[1]:box[3], box[0]:box[2]], None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)  # noqa: E731
    tiles = [(cr(D), "原画（DP130155）"),
             (cr(cv2.imread(B + "/r_after/views/painting_t120_asis.png")), "作る部（仕上げ32）t*"),
             (cr(cv2.imread(B + "/fix01/r_fix01/views/painting_t120_asis.png")), "修正01 t*"),
             (cr(cv2.imread(B + "/fix01/r_fix01/views/painting_t120_clawfree.png")), "修正01 の爪なし（主役波の材質だけ）"),
             (cr(cv2.imread(B + "/r_after/views/painting_t105_asis.png")), "作る部 t 10.5 s"),
             (cr(cv2.imread(B + "/fix01/r_fix01/views/painting_t105_asis.png")), "修正01 t 10.5 s")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32 修正01｜b区域の爪（［利用者の言葉］Q16・Q21：房として読めるか）",
         "表示の x 160〜800・y 380〜620。修正01：根元が白の範囲の外の爪を帯にせず、縁の線を根元で開き、根元の円を水色の版の雲にし、帯の幅を一覧の領域に合わせた。")
    tw, th = 632, 237
    for k, (a, t) in enumerate(tiles):
        x, y = 4 + (k % 3) * (tw + 4), 66 + (k // 3) * (th + 30)
        im.paste(fit(F.pil(a), (tw, th)), (x, y + 22))
        label(d, x + 4, y + 26, t, 14)
    bl, mz, rg = meas["bregion_lines_tstar"], meas["bregion_mizuiro_fraction_tstar"], meas["bregion_closed_rings"]
    txt = ["b区域の帯の中（作る部の数え方）：白い地の上の暗い線の成分 原画 %d・前 %d・作る部 %d・修正01 %d（線の画素 原画 %d・作る部 %d・修正01 %d）。"
           % (bl["painting"]["components"], bl["before"]["components"], bl["build"]["components"], bl["fix01"]["components"],
              bl["painting"]["dark_line_px"], bl["build"]["dark_line_px"], bl["fix01"]["dark_line_px"]),
           "白い地の上の水色の版の割合：原画 %.3f・前 %.3f・作る部 %.3f・修正01 %.3f（根元の水色の雲、pl32f_tuft_base）。"
           % (mz["painting"], mz["before"], mz["build"], mz["fix01"]),
           "閉じた輪（爪の差の暗い画素の成分のうち、中に閉じた所を囲むもの）：t 10.5 s 作る部 %d → 修正01 %d、t* 作る部 %d → 修正01 %d（記録のみ）。"
           % (rg["build_t105"], rg["fix01_t105"], rg["build_t120"], rg["fix01_t120"]),
           "読み：爪は根元が泡の胴へ開いた鉤（c・u・J の形）になり、付け根に水色の版の雲がつく。原画の藍の窓（房と房の間の藍）と 3 つの房の形は主役波の形と材質（仕上げ28・29）で、",
           "この回では変えていない。房としての読みは一部（記録 第2節）。"]
    y = 66 + 2 * (th + 30) + 30
    for ln in txt:
        d.text((14, y), ln, fill=(40, 48, 64), font=font(16)); y += 26
    p = os.path.join(out, "fig_pl32f_bregion.png"); im.save(p); return p


def fig_reps(out, m_fix, m_build):
    D = F.paint_disp()
    rb = cv2.imread(B + "/r_after/views/painting_t120_asis.png")
    ra = cv2.imread(B + "/fix01/r_fix01/views/painting_t120_asis.png")
    new = F.load_inv(INVF)
    ids = F.REPS + ["C095"]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32 修正01｜代表10形（R1〜R10）と船側中央の爪 C095：原画｜作る部｜修正01 の原画視点 t*（赤＝一覧の領域）",
         "数は爪の帯の投影（主役波の面の隠れを数えない。pl32_measure_claws.py）：輪郭＝影の外周と領域の外周の左右の対称 Hausdorff（≤4 px）、幅＝影の幅／領域の幅。")
    cw = 60
    for k, cid in enumerate(ids):
        c = new[cid]
        q = F.r2d(np.asarray(c["centerline_ref"]))
        cx, cy = (q.min(0) + q.max(0)) / 2
        x0, y0 = int(cx - cw / 2), int(cy - cw / 2)
        sc = 2.6
        tiles = []
        for src in (D, rb, ra):
            C = src[max(0, y0):y0 + cw, max(0, x0):x0 + cw].copy()
            C = cv2.resize(C, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
            Q = np.round((F.r2d(np.asarray(c["region_polygon_ref"])) - [x0, y0]) * sc).astype(np.int32)
            cv2.polylines(C, [Q], True, (0, 0, 230), 1, cv2.LINE_AA)
            tiles.append(C)
        cell = np.concatenate(tiles, 1)
        col, row = k % 3, k // 3
        x, y = 4 + col * 638, 66 + row * 252
        im.paste(fit(F.pil(cell), (630, 156)), (x, y + 22))
        v = m_fix["after"]["per_claw"][cid]; vb = m_build["after"]["per_claw"].get(cid, {})
        t = "%s %s｜輪郭 左 %s・右 %s px（作る部 %s・%s）｜幅 %.2f（%.2f）｜先 %.1f°（%.1f°）" % (
            F.REPL.get(cid, "船側中央"), cid, v["outline_left_px"], v["outline_right_px"], vb.get("outline_left_px"), vb.get("outline_right_px"),
            v["width_ratio"], vb.get("width_ratio", float("nan")), v["tip_dir_deg"], vb.get("tip_dir_deg", float("nan")))
        if cid == "C095":
            t += "｜根元 %.2f・先 %.2f px" % (v["root_width_px"], v["tip_width_px"])
        d.text((x + 2, y + 2), t, fill=(30, 30, 30), font=font(12))
    p = os.path.join(out, "fig_pl32f_reps.png"); im.save(p); return p


def fig_list(out):
    D = F.paint_disp()
    inv = json.load(open(INVF, encoding="utf-8"))
    chk = json.load(open(B + "/fix01/list/pl32_claw_list_checks.json", encoding="utf-8"))
    rig = json.load(open(B + "/fix01/claws/ds33_claw_rig.json", encoding="utf-8"))
    dropped = {r["id"] for r in rig["dropped_white_root"]}
    ext = {e["id"]: e for e in chk["fix01"]["root_extend"]}
    byid = {c["id"]: c for c in inv["claws"]}
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32 修正01｜一覧の直し（原画 DP130155、表示の px）",
         "緑：利用者の 100 本から加えた主浪の爪（主浪の左下）／青：手前の波の爪（一覧だけ）／橙：根元を延ばした爪（細線＝前の根元）／赤：帯にしなかった爪（根元が白の範囲の外）／灰：そのほか。")
    for k, (box, name) in enumerate([((150, 60, 1150, 640), "主浪と b区域"), ((150, 600, 1150, 1080), "手前の波（画の下側）")]):
        x0, y0, x1, y1 = box
        C = D[y0:y1, x0:x1].copy()
        sc = 0.94
        C = cv2.resize(C, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        for c in inv["claws"]:
            if c["zone"] == "right":
                continue
            cl = (F.r2d(np.asarray(c["centerline_ref"])) - [x0, y0]) * sc
            if c.get("origin") == "pl32f_user100":
                col = (200, 120, 0) if c["zone"] == "front" else (40, 170, 40)
            elif c["id"] in ext and ext[c["id"]]["decision"] == "延ばした":
                col = (0, 140, 255)
            elif c["id"] in dropped:
                col = (30, 30, 220)
            else:
                col = (130, 130, 130)
            cv2.polylines(C, [np.round(cl).astype(np.int32)], False, col, 2, cv2.LINE_AA)
            if c["id"] in ext and ext[c["id"]]["decision"] == "延ばした" and c.get("root_ref_pl32"):
                r0 = (F.r2d(np.asarray(c["root_ref_pl32"])) - [x0, y0]) * sc
                cv2.circle(C, tuple(np.round(r0).astype(int)), 3, (0, 0, 0), 1)
            if c.get("origin") == "pl32f_user100" or (c["id"] in ext and ext[c["id"]]["decision"] == "延ばした"):
                cv2.putText(C, c["id"], tuple(np.round(cl[-1]).astype(int) + [3, 0]), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1)
        x = 4 + k * 958
        im.paste(fit(F.pil(C), (950, 560)), (x, 70))
        label(d, x + 4, 74, name, 14)
    ad = chk["fix01"]["user100_additions"]
    n_add = sum(1 for a in ad if a["decision"] == "加える")
    txt = ["利用者の 100 本：加えた %d 本（主浪の左下 4・手前の波 11）、既存の爪に対応 %d 本、まとめた %d 本、加えない %d 本（回転つきの位置合わせでも NCC < 0.70 の 4 本と、通れる画素でつなげない手前の波の 2 本）。"
           % (n_add, sum(1 for a in ad if a["decision"].startswith("対応")), sum(1 for a in ad if a["decision"] == "まとめる"),
              sum(1 for a in ad if a["decision"].startswith("加えない"))),
           "根元の先で指が続く疑い：作る部 18 → 修正01 11（延ばした %d 本。残る 11 のうち 8 本は目で見て誤検出、1 本は名指しの長さ、2 本は断面が根元の直ぐ先で開く）。"
           % sum(1 for e in ext.values() if e["decision"] == "延ばした"),
           "帯にしなかった爪 %d 本は一覧に残す（根元のセルの 4 頂点のうち白の範囲は 0〜1。原画では白い泡、立体の材質では藍の所）。" % len(dropped)]
    y = 640
    for ln in txt:
        d.text((14, y), ln, fill=(40, 48, 64), font=font(16)); y += 26
    p = os.path.join(out, "fig_pl32f_list.png"); im.save(p); return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=REPO + "/Docs/Evidence/Polish/32")
    a = ap.parse_args()
    meas = json.load(open(B + "/fix01/measure/pl32f_measure.json", encoding="utf-8"))
    m_fix = json.load(open(B + "/fix01/measure/pl32_measure_claws.json", encoding="utf-8"))
    m_build = json.load(open(B + "/measure/pl32_measure_claws.json", encoding="utf-8"))
    for f in (fig_spots(a.out), fig_bregion(a.out, meas), fig_reps(a.out, m_fix, m_build), fig_list(a.out)):
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
