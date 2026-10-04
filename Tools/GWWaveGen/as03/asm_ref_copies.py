# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：利用者だけの比べの図（sculpture_vs_V1.png）に使う、参照の彫刻の写真の一時の縮めた写しを作る・消す。
写真のフォルダー（Q16 の例外、読み取りのみ）：G:/research/reality scan/北斋参考 の一番上の名前の付いた 5 枚だけ（正面・右45・左45・背・頂）。
写しは Git 対象外の Unity/Build/Polish/sample03/user_only/ref_asm/ に PNG（Exif なし）で置き、名前と SHA-256 を ref_asm_log.json に書く。
写しはリポジトリと成果物へ入れない。比べの図に使ったものだけを残し、ほかは消す（--clean で全部を消して記録する）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/asm_ref_copies.py make | clean
"""
import hashlib
import json
import os
import sys
import time

from PIL import Image, ImageOps

SRC = "G:/research/reality scan/北斋参考"
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/user_only/ref_asm"
LOG = OUT + "/ref_asm_log.json"
PICK = [("front", "正面图.jpg"), ("right45", "右45.jpg"), ("left45", "左45.jpg"), ("back", "背图.jpg"), ("top", "顶图、.jpg")]
W = 1200


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_log():
    if os.path.isfile(LOG):
        return json.load(open(LOG, encoding="utf-8"))
    return {"note_ja": "参照の彫刻の写真（Q16 のフォルダー、読み取りのみ）の一時の縮めた写し。Exif は写さない（PNG で保存）。リポジトリと成果物へ入れない。"
                       "利用者だけの比べの図 sculpture_vs_V1.png に使う。要らなくなったら消す（この記録に消した時刻を書く）。",
            "folder": SRC, "events": []}


def make():
    os.makedirs(OUT, exist_ok=True)
    log = load_log()
    for key, name in PICK:
        sp = SRC + "/" + name
        im = ImageOps.exif_transpose(Image.open(sp)).convert("RGB")
        w0, h0 = im.size
        im = im.resize((W, round(h0 * W / w0)), Image.LANCZOS)
        tp = OUT + "/" + key + ".png"
        im.save(tp, "PNG")
        log["events"].append({"event": "created", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "key": key, "src_name": name,
                              "src_sha256": sha(sp), "src_size": [w0, h0], "tmp": tp, "tmp_size": list(im.size), "tmp_sha256": sha(tp)})
        print(key, name, im.size)
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def clean(keep=()):
    log = load_log()
    for key, _name in PICK:
        tp = OUT + "/" + key + ".png"
        if key in keep or not os.path.isfile(tp):
            continue
        s = sha(tp)
        os.remove(tp)
        log["events"].append({"event": "deleted", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "key": key, "tmp": tp, "tmp_sha256": s})
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "make"
    if cmd == "make":
        make()
    elif cmd == "clean":
        clean(keep=tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ())
