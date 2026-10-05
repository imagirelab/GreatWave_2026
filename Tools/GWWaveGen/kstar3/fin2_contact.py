# -*- coding: utf-8 -*-
"""Q20 final loop 2: contact sheet of the 12 turntable stills.  usage: py -3.10 fin2_contact.py stills_dir out.png title"""
import sys, os, glob
from PIL import Image, ImageDraw, ImageFont
d, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
fs = sorted(glob.glob(os.path.join(d, "f_*.png")))
ims = [Image.open(f).convert("RGB") for f in fs]
w = 480; h = int(ims[0].size[1] * w / ims[0].size[0])
cols = 4; rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w + (cols - 1) * 6, 40 + rows * (h + 24)), (250, 250, 248))
dr = ImageDraw.Draw(sheet); f = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 18); f2 = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 14)
dr.text((8, 8), title, fill=(20, 20, 20), font=f)
for k, (fn, im) in enumerate(zip(fs, ims)):
    x = (k % cols) * (w + 6); y = 40 + (k // cols) * (h + 24)
    dr.text((x + 4, y + 2), "frame %s (%d deg from the painting camera azimuth)" % (os.path.basename(fn)[2:6], int(int(os.path.basename(fn)[2:6]) * 360 / 240)), fill=(40, 40, 40), font=f2)
    sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y + 22))
sheet.save(out); print(out, sheet.size)
