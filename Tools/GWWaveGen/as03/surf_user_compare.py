# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：利用者だけに見せる比べの図（彫刻の写真を含む。リポジトリと成果物へ入れない。Build の下の user_only だけに置く）。
写真は、調べ S3 が利用者だけの図のために残した一時の縮めた写し（study/ref_tmp/ref01・02・03・11・12、Exif なし）を読むだけで、新しい写しは作らない。
使った写しの名前と SHA-256 を surface/user_only/surf_user_compare_log.json に書く。写真を面へ写すことはしない（見るためだけ）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_user_compare.py [版 v11]"""
import hashlib
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "v11"
REF = S.S03 + "/study/ref_tmp"
R = S.OUT + "/render"
OD = S.OUT + "/user_only"
cols = [("ref11.png", "正面图", 45, "45°（正面）"), ("ref02.png", "左45", 0, "0°（原画の向き）"), ("ref03.png", "左图", 315, "315°（左の側面）"),
        ("ref01.png", "右图", 180, "180°"), ("ref12.png", "背图", 225, "225°（背）")]
W, H = 1920, 1080
im = Image.new("RGB", (W, H), (24, 26, 30))
d = ImageDraw.Draw(im)
fb = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 24)
fr = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)   # 写真の名前（中国語の字）も出せる字体
d.text((24, 14), "利用者だけに見せる比べ（彫刻の写真を含む。リポジトリと成果物へ入れない）：参照の彫刻の写真｜B2 FLAT｜B2 SCULPT（冠なし、波頭の回り台）",
       font=fb, fill=(255, 120, 110))
tw, th = 330, 248
used = []
for j, (fn, nm, az, lab) in enumerate(cols):
    x = 24 + 140 + j * (tw + 12)
    d.text((x, 56), "写真「%s」｜方位 %s" % (nm, lab), font=fr, fill=(255, 196, 92))
    p = REF + "/" + fn
    if os.path.exists(p):
        ph = Image.open(p).convert("RGB")
        w0, h0 = ph.size
        # 4:3 の写真を 4:3 の枠へ
        im.paste(ph.resize((tw, th), Image.LANCZOS), (x, 84))
        used.append({"file": p, "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "src_name": nm})
    for i, m in enumerate(("flat", "sculpt")):
        q = R + "/B2_%s_%s/crest/t120_az%03d_clawfree.png" % (TAG, m, az)
        if os.path.exists(q):
            c = Image.open(q).convert("RGB")
            # 16:9 の描画の中ほどを 4:3 で切る
            cw = int(c.size[1] * 4 / 3)
            x0 = (c.size[0] - cw) // 2
            im.paste(c.crop((x0, 0, x0 + cw, c.size[1])).resize((tw, th), Image.LANCZOS), (x, 84 + (i + 1) * (th + 12)))
for i, lab in enumerate(["彫刻の写真", "B2 FLAT", "B2 SCULPT"]):
    d.text((24, 84 + i * (th + 12) + th // 2 - 10), lab, font=fr, fill=(255, 196, 92))
d.text((24, H - 62), "冠の指（B1）はまだ入れていない。白の境は B1 の白の印 v2。B2 は面の彫り（稜と溝）と陰・艶だけ。写真は調べ S3 が残した一時の縮めた写し（G:/research/reality scan/北斋参考 の 5 枚、Exif なし）。",
       font=fr, fill=(200, 200, 200))
d.text((24, H - 36), "この図は Build の下の user_only だけに置く。写真を面へ写していない。PC オフスクリーン描画（HMD 実機ではない）。", font=fr, fill=(200, 200, 200))
os.makedirs(OD, exist_ok=True)
outp = OD + "/surf_ref_compare_USERONLY.png"
im.save(outp)
S.jdump(OD + "/surf_user_compare_log.json", {"noteJa": "写真の一時の写し（調べ S3 が残した物）を読んだだけ。新しい写しは作っていない。この図は利用者だけ（リポジトリと成果物へ入れない）。",
                                              "used": used, "output": outp, "output_sha256": hashlib.sha256(open(outp, "rb").read()).hexdigest(),
                                              "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
print(outp)
