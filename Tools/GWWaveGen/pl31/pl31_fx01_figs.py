# -*- coding: utf-8 -*-
"""仕上げ31 修正01 の図（1920×1080）：同じ視点・同じ時刻で、前（コミットした仕上げ30）・修正前（仕上げ31 の 1 回目）・修正01 の 3 段を並べる。
既にある Unity の描画（PL31Render）を切り抜いて並べるだけ（新しい描画はしない）。HMD ではない。

  fig_pl31_fx_white_t6.png     t 6 s・6.5 s の頂の白（回り台 90・120・150・270°）。修正前は頂の小さな白の横の 1 画素の点線
  fig_pl31_fx_white_tail.png   t 8.5〜9.5 s の尾の頂の白（回り台 0・240・300°、真上）。修正前は尾の頂の白い帯が 1〜2 画素の糸に細る
  fig_pl31_fx_claws.png        原画視点 t 6.5〜8 s の唇の爪の芽（設計33 の焼き込みの爪）。修正前は白くなる前の藍の面から爪が伸びる
  fig_pl31_fx_spray.png        原画視点 t 9.5〜11.5 s の唇の下の藍の壁と、座席から波の方向 t 10.5・12 s。修正前は管の中の子の粒が密
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_fx01_figs.py --before <前の描画（追加の時刻）> --r0 <修正前の描画> --after <修正01 の描画> --out Docs/Evidence/Polish/31
（各フォルダーは views/ と tt/ を持つ。時刻の画像は 1 つ目のフォルダーになければ --*-main の同じ名前を探す）
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, label, head  # noqa: E402

ROWS = (("before", "前｜仕上げ30"), ("r0", "修正前｜仕上げ31 1 回目"), ("after", "後｜仕上げ31 修正01"))


def find(roots, rel):
    for r in roots:
        if r and os.path.exists(os.path.join(r, rel)):
            return os.path.join(r, rel)
    return None


def white_centre(p, box):
    a = np.asarray(Image.open(p).convert("RGB"))[box[1]:box[3], box[0]:box[2]].astype(int)
    m = (a[..., 0] > 225) & (a[..., 1] > 220) & (a[..., 2] > 190)
    if m.sum() < 20:
        return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    ys, xs = np.nonzero(m)
    return (int(np.median(xs)) + box[0], int(np.median(ys)) + box[1])


def tile(p, centre, size, scale):
    w, h = size
    cw, ch = int(round(w / scale)), int(round(h / scale))
    if p is None:
        return Image.new("RGB", size, (200, 200, 200))
    im = Image.open(p).convert("RGB")
    x0 = int(np.clip(centre[0] - cw // 2, 0, im.width - cw)); y0 = int(np.clip(centre[1] - ch // 2, 0, im.height - ch))
    c = im.crop((x0, y0, x0 + cw, y0 + ch))
    return c.resize(size, Image.LANCZOS if scale < 1 else Image.NEAREST)


def grid(a, cols, title, sub, fname, size=(474, 300), scale=1.0, centre_from="after", search=(300, 80, 1620, 900)):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, title, sub)
    roots = dict(before=[a.before, a.before_main], r0=[a.r0, a.r0_main], after=[a.after, a.after_main])
    for ci, (rel, cname, fixed) in enumerate(cols):
        pc = find(roots[centre_from], rel)
        centre = fixed if fixed else (white_centre(pc, search) if pc else (960, 540))
        for ri, (key, rname) in enumerate(ROWS):
            x, y = 4 + ci * (size[0] + 4), 66 + ri * (size[1] + 4)
            im.paste(tile(find(roots[key], rel), centre, size, scale), (x, y))
            label(d, x + 3, y + 3, "%s｜%s" % (rname, cname), 12)
    p = os.path.join(a.out, fname)
    im.save(p)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True); ap.add_argument("--before-main", default=None)
    ap.add_argument("--r0", required=True); ap.add_argument("--r0-main", default=None)
    ap.add_argument("--after", required=True); ap.add_argument("--after-main", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fs = []
    fs.append(grid(a, [("tt/t060_az090_claws.png", "回り台 90° t 6 s", None), ("tt/t060_az120_claws.png", "回り台 120° t 6 s", None),
                       ("tt/t060_az150_claws.png", "回り台 150° t 6 s", None), ("tt/t060_az270_claws.png", "回り台 270° t 6 s", None)],
                   "仕上げ31 修正01｜t 6 s の頂の白（1:1 の切り抜き。作品のまま：爪・線・飛沫あり）",
                   "修正前（pl31_white_order の順位の重み）は頂の小さな白の横に、頂・唇の縁に沿う 1 画素の白い点線が出た。修正01（pl31_white_order patch：頂の最も高い所から面の上の距離の順）は頂の白い塊。",
                   "fig_pl31_fx_white_t6.png", search=(300, 80, 1620, 470)))
    fs.append(grid(a, [("tt/t090_az000_claws.png", "回り台 0° t 9 s", (900, 560)), ("tt/t090_az240_claws.png", "回り台 240° t 9 s", (1000, 560)),
                       ("tt/t095_az300_claws.png", "回り台 300° t 9.5 s", (960, 600)), ("views/top_t090_asis.png", "真上 t 9 s", (900, 540))],
                   "仕上げ31 修正01｜t 9〜9.5 s の尾の頂の白（切り抜きは 0.45 倍）",
                   "修正前は低い尾の行の頂だけが先に白くなり、尾の頂の白い帯が尾の端で 1〜2 画素の糸になった。修正01 は尾の行が頂の両側の帯の幅のまま白くなる（t 9.5 s ではまだ尾は藍で、t 10〜10.8 s に帯のまま白くなる）。",
                   "fig_pl31_fx_white_tail.png", scale=0.45))
    fs.append(grid(a, [("views/painting_t065_asis.png", "原画視点 t 6.5 s", (300, 500)), ("views/painting_t070_asis.png", "原画視点 t 7 s", (300, 470)),
                       ("views/painting_t075_asis.png", "原画視点 t 7.5 s", (320, 430)), ("views/painting_t080_asis.png", "原画視点 t 8 s", (360, 400))],
                   "仕上げ31 修正01｜原画視点 t 6.5〜8 s の唇の爪の芽（設計33 の焼き込みの爪、切り抜きは 0.8 倍）",
                   "修正前は爪の根元が白くなる前に爪が伸び始めた（白の範囲に根元がある 131 本のうち 32〜38 本、最大 +1.7 s）。修正01 は pl31_white_claw_pin で根元から 0.6 m を伸び始めの半コマ前までに白くした（0 本）。",
                   "fig_pl31_fx_claws.png", scale=0.8))
    fs.append(grid(a, [("views/painting_t095_asis.png", "原画視点 t 9.5 s", (420, 330)), ("views/painting_t110_asis.png", "原画視点 t 11 s", (560, 380)),
                       ("views/seat_toward_wave_t105_asis.png", "座席から波の方向 t 10.5 s", (900, 300)), ("views/seat_toward_wave_t120_asis.png", "座席から波の方向 t 12 s（t*）", (900, 300))],
                   "仕上げ31 修正01｜飛沫の子の粒（切り抜きは 0.6 倍）",
                   "修正前は子の 1,939 を原画視点 t* で主役波の陰（管の中）に置いたので、原画視点 t 9〜11.5 s に唇の下の藍の壁の前の密な粒、座席から波の方向に t 10.5 s〜t* の保持で一面の点が出た。修正01 は子を原画の点の中と白の上に狙って置く。",
                   "fig_pl31_fx_spray.png", scale=0.6))
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
