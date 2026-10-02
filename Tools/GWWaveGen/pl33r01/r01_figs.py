# -*- coding: utf-8 -*-
"""仕上げ33修正01：爪の拡大の並べ図（仕上げ33｜変種 SWEEP｜修正の回 1 の後）を、同じ視点・同じ時刻の Unity の PC 描画から切り出して作る（記録）。

出力：--out/fig_pl33r01_claws_views.png（行：原画視点 t* の頂と唇・b区域、座席 t*、後ろ 65° t*、左の側面 t*）
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/r01_figs.py [--out …]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_sheets as S  # noqa: E402

B = REPO + "/Unity/Build/Polish"
COLS = [("仕上げ33（修正の回 2）", B + "/33/fix02/r_fix02"), ("変種 SWEEP（評審の前）", B + "/33r01/sweep/r_final"),
        ("仕上げ33修正01（修正の回 1 の後）", B + "/33r01/fix01/r_fix01")]
ROWS = [("原画視点 t*：頂と唇", "painting_t120", (700, 110, 1200, 310)),
        ("原画視点 t*：b区域", "painting_t120", (380, 360, 880, 560)),
        ("座席 t*", "seat_t120", (420, 80, 1420, 480)),
        ("後ろ 65° t*", "back65_t120", (640, 140, 1260, 388)),
        ("左の側面 t*", "side_left_t120", (560, 330, 1260, 610))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=B + "/33r01/fix01/evidence")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    W, H = 1920, 1080
    im = Image.new("RGB", (W, H), (238, 238, 238))
    d = ImageDraw.Draw(im)
    S.head(d, "仕上げ33修正01 爪の拡大｜列：仕上げ33・変種 SWEEP・修正の回 1 の後（同じ視点・同じ時刻・作品のまま）",
           "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。行ごとに同じ切り出し。原画カメラからの投影の色は使っていない。")
    cw = (W - 8 - 2 * 6) // 3
    ch = (H - 66 - 8) // len(ROWS) - 4
    for r, (rn, v, box) in enumerate(ROWS):
        for c, (cn, run) in enumerate(COLS):
            x, y = 4 + c * (cw + 6), 66 + r * (ch + 4)
            p = os.path.join(run, "views", v + "_asis.png")
            if os.path.exists(p):
                t = S.fit(Image.open(p).convert("RGB").crop(box), (cw, ch))
                im.paste(t, (x + (cw - t.size[0]) // 2, y))
            S.label(d, x + 4, y + 3, "%s｜%s" % (cn, rn), 13)
    p = os.path.join(a.out, "fig_pl33r01_claws_views.png")
    im.save(p)
    print(p, os.path.getsize(p))


if __name__ == "__main__":
    main()
