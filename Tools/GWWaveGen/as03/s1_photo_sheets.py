# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：彫刻の写真（G:/research/reality scan/北斋参考、Q16 の例外。読み取りのみ）を選ぶための一時の一覧図を作る。
写真とそこから作った画像はリポジトリへ入れない。出力は Git 対象外の Unity/Build/Polish/sample03/study/ref_tmp/s1/sheets/ だけ（調べの後に消す）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_photo_sheets.py [サブフォルダーの名前 ...]
"""
import os
import sys
import json
import hashlib
from PIL import Image, ImageDraw

SRC = "G:/research/reality scan/北斋参考"
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study/ref_tmp/s1/sheets"
TW = 240


def files_in(sub):
    d = os.path.join(SRC, sub) if sub else SRC
    fs = [f for f in os.listdir(d) if f.lower().endswith(".jpg")]

    def key(f):
        b = os.path.splitext(f)[0]
        t = b.rsplit("_", 1)
        try:
            return (t[0], int(t[1]))
        except Exception:
            return (b, 0)
    return [os.path.join(d, f) for f in sorted(fs, key=key)]


def sheet(paths, name, cols=8):
    thumbs = []
    for p in paths:
        im = Image.open(p)
        im.draft("RGB", (im.width // 8, im.height // 8))
        im = im.convert("RGB")
        r = TW / im.width
        im = im.resize((TW, int(round(im.height * r))))
        thumbs.append((os.path.basename(p), im))
    th = max(t[1].height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    S = Image.new("RGB", (cols * TW, rows * (th + 14)), (40, 40, 40))
    dr = ImageDraw.Draw(S)
    for i, (nm, im) in enumerate(thumbs):
        x = (i % cols) * TW
        y = (i // cols) * (th + 14)
        S.paste(im, (x, y + 14))
        dr.text((x + 2, y + 1), str(i), fill=(255, 255, 0))
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, name)
    S.save(fp, quality=85)
    import time
    LOG = os.path.join(os.path.dirname(OUT), "s1_ref_tmp_log.json")
    d = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {"source_folder": SRC, "events": []}
    h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
    d["events"].append({"event": "tmp_contact_sheet", "tmp": os.path.relpath(fp, os.path.dirname(LOG)).replace("\\", "/"),
                        "tmp_sha256": h, "sources": [os.path.basename(p) for p in paths],
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return fp, [t[0] for t in thumbs], thumbs[0][1].size


if __name__ == "__main__":
    subs = sys.argv[1:] or [""]
    index = {}
    for sub in subs:
        ps = files_in(sub)
        tag = (sub.replace("/", "_") or "top")
        for k in range(0, len(ps), 64):
            fp, names, sz = sheet(ps[k:k + 64], "sheet_%s_%03d.jpg" % (tag, k))
            index[os.path.basename(fp)] = {"folder": sub, "names": names}
            print(fp, len(names))
    jf = os.path.join(OUT, "sheet_index_%s.json" % (subs[0].replace("/", "_") or "top"))
    json.dump(index, open(jf, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
