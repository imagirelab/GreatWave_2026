# -*- coding: utf-8 -*-
"""見本04 の調べ M：描画の確かめ用の縮めた一覧（作業用。比べの図は mat_sheets.py）。使い方：mat_contact.py <描画のフォルダー> <出力.png> [names…]"""
import sys
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
names = sys.argv[3:] or ["painting", "seat", "seat_toward_wave", "back65", "side_left", "side_right", "top"]
ims = [Image.open(src + "/views/%s_t120_claws.png" % n).convert("RGB").resize((960, 540)) for n in names]
cols = 2
rows = (len(ims) + 1) // 2
W = Image.new("RGB", (960 * cols, 540 * rows), (255, 255, 255))
for i, m in enumerate(ims):
    W.paste(m, ((i % cols) * 960, (i // cols) * 540))
W.save(out)
