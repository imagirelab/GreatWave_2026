# -*- coding: utf-8 -*-
"""図5：見た目の手がかり（番号30・31 の証拠の静止画から切り出すだけ）。
使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds26/diag_cues.py → Docs/Evidence/Design/26/diag_f5_visual_cues.png"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ds26_paths as DP  # noqa: E402
REPO, OUT = DP.REPO, DP.outdir(DP.EVID)
E = os.path.join(REPO, "Docs", "Evidence", "ArtFirst")
F = lambda s, b=False: ImageFont.truetype("C:/Windows/Fonts/YuGoth%s.ttc" % ("B" if b else "M"), s)
p30 = Image.open(os.path.join(E, "30", "af30_painting_formation.png")).convert("RGB")
s30 = Image.open(os.path.join(E, "30", "af30_seat_formation_waveonly.png")).convert("RGB")
p31 = Image.open(os.path.join(E, "31", "af31_painting_white.png")).convert("RGB")
def g30(im, r, c):
    return im.crop((c * 640, r * 360, c * 640 + 640, r * 360 + 360))
def g31(r, c):
    x0, y0, w, h = 42, 48, 612, 344
    return p31.crop((x0 + c * w, y0 + r * h, x0 + c * w + w, y0 + r * h + h))
tiles = [
    (g30(p30, 0, 0), "30 原画視点 2.0 s：平らな海に K* の色区（白・水色・藍）が縞で押し縮められて見える"),
    (g31(0, 2), "31 原画視点 7.0 s：前面はまだ 63°（鉛直の前、砕けていない）なのに頂が白い（白の割合 36%）"),
    (g30(p30, 1, 0), "30 原画視点 9.0 s：唇の下面（藍濃）が前を向き、角のような唇"),
    (g30(p30, 1, 2), "30 原画視点 10.5 s：唇先の速さ 2〜3 m/s（頂はほぼ止まったまま）"),
    (g30(s30, 0, 0), "30 座席 2.0 s：縞模様の平らな板が海の上にある"),
    (g30(s30, 1, 1), "30 座席 10.0 s"),
    (g30(s30, 2, 0), "30 座席 11.0 s：唇の奥に白と藍濃の櫛の歯（28修正01 の限界 1）"),
    (g30(s30, 2, 2), "30 座席 12.0 s（t*）：唇先は座席から水平 5.1 m・仰角 64°、真上には来ない（番号30 の記録）"),
]
# 座席と原画視点の 10→12 s の画素の変化
def changed(a, b):
    A = np.asarray(a, np.int16); B = np.asarray(b, np.int16)
    d = np.abs(A - B).max(-1) > 24
    return float(d.mean())
ch_seat = changed(g30(s30, 1, 1), g30(s30, 2, 2)); ch_seat_early = changed(g30(s30, 0, 2), g30(s30, 1, 0))
ch_p = changed(g30(p30, 1, 1), g30(p30, 2, 2)); ch_p_early = changed(g30(p30, 0, 2), g30(p30, 1, 0))
tw, th = 560, 315
W = 4 * tw + 5 * 16; H = 70 + 2 * (th + 70) + 90
img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
d.text((16, 14), "図5　見た目の手がかり（番号30・31 の証拠の静止画を切り出しただけ。Unity の実描画）", fill=(0, 0, 0), font=F(26, True))
for i, (im, cap) in enumerate(tiles):
    r, c = divmod(i, 4)
    x = 16 + c * (tw + 16); y = 70 + r * (th + 70)
    img.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
    # 折り返し
    words = cap; lines = []
    while words:
        n = len(words)
        while d.textlength(words[:n], font=F(16)) > tw and n > 1:
            n -= 1
        lines.append(words[:n]); words = words[n:]
    for k, s in enumerate(lines[:2]):
        d.text((x, y + th + 4 + k * 22), s, fill=(0, 0, 0), font=F(16))
note = ("画素の変化（色の差 > 24/255 の画素の割合）：座席 10.0→12.0 s %.1f%%（8.0→9.0 s は %.1f%%）、原画視点 10.0→12.0 s %.1f%%（8.0→9.0 s は %.1f%%）"
        % (ch_seat * 100, ch_seat_early * 100, ch_p * 100, ch_p_early * 100))
d.text((16, H - 70), "上段：色（UV に焼いた終態の配色）が形成の前から水面に貼り付いている。下段：座席 v1 から見た形成（主役波・空・海だけ）。", fill=(0, 0, 0), font=F(18))
img.save(os.path.join(OUT, "diag_f5_visual_cues.png"))
print(note)
