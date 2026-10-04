# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：選んだ彫刻の写真の縮めた一時の写しと、拡大の切り出しを作る（測るため。読み取りのみ）。
写しは Git 対象外の Unity/Build/Polish/sample03/study/ref_tmp/s1/pick/ にだけ置き、名前と SHA-256 を ref_tmp/s1/s1_ref_tmp_log.json に残す（調べの後に消す）。
Exif は写さない（PIL で画素だけを保存する）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_photo_pick.py pick  <id> <相対パス> [長辺]
       py -3.10 -B Tools/GWWaveGen/as03/s1_photo_pick.py crop  <id> <相対パス> x0 y0 x1 y1 [長辺]   （0..1 の割合）
"""
import os
import sys
import json
import time
import hashlib
from PIL import Image

SRC = "G:/research/reality scan/北斋参考"
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study/ref_tmp/s1/pick"
LOG = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study/ref_tmp/s1/s1_ref_tmp_log.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def log_add(ev):
    d = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {"source_folder": SRC, "events": []}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    d["events"].append(ev)
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    mode, pid, rel = sys.argv[1], sys.argv[2], sys.argv[3]
    src = os.path.join(SRC, rel)
    im = Image.open(src).convert("RGB")
    W, H = im.size
    if mode == "crop":
        x0, y0, x1, y1 = [float(v) for v in sys.argv[4:8]]
        box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
        im = im.crop(box)
        ls = int(sys.argv[8]) if len(sys.argv) > 8 else 1600
        name = "%s_crop.png" % pid
    else:
        box = (0, 0, W, H)
        ls = int(sys.argv[4]) if len(sys.argv) > 4 else 1600
        name = "%s.png" % pid
    r = min(1.0, ls / max(im.size))
    if r < 1.0:
        im = im.resize((int(round(im.width * r)), int(round(im.height * r))), Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, name)
    im.save(fp)
    log_add({"event": "tmp_copy", "id": pid, "source_rel": rel, "source_sha256": sha(src), "source_size": [W, H],
             "box_px": list(box), "scale": r, "tmp": os.path.relpath(fp, os.path.dirname(LOG)).replace("\\", "/"),
             "tmp_sha256": sha(fp), "tmp_size": list(im.size), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(fp, im.size, "scale %.4f" % r)


if __name__ == "__main__":
    main()
