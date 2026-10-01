# -*- coding: utf-8 -*-
"""仕上げ28：F7-1（波頭の模様の 1 コマだけの跳び）を、段階7確認と同じ数え方（pl28_s7_video.analyse。M1・M1b・M2・M3）で数える包み。

段階7確認の台本は mp4 だけを読む。この包みは次の 3 つを同じ関数で数えられるようにする（数え方の中身は変えない）：
  video   ：mp4（段階7確認と同じ）
  pngseq  ：Unity が書いた無圧縮の PNG の連番（DS29Render の静止画。同じ τ の並び）。動画の圧縮を通さない。
  reenc   ：同じ PNG の連番を、Unity の動画と同じ ffmpeg の引数（libx264 -preset medium -crf 18 -pix_fmt yuv420p、DS29Render.EncodeVideo）
            で mp4 にしてから数える（圧縮だけを足す）。
PNG の連番は 421 コマに満たないので、段階7確認の窓 t2_12 の代わりに全体の窓（all）と、次の関心の窓を書く：
  --win a,b（コマの番号。連番の中の位置ではなく、動画のコマの番号 i = t·30 で書く。--first に連番の最初のコマの番号）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind pngseq --src <PNG のフォルダー> --glob "ds29_painting_f*.png" --first 264 --name F_final_png --out <json>
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind reenc  --src <同じ> --glob ... --first 264 --name F_final_reenc --out <json>
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind video  --src <mp4> --name ds29r01_painting --out <json> [--trim 264,351]
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import pl28_s7_video as S7  # noqa: E402

FF = S7.FF
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]   # DS29Render.EncodeVideo と同じ


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def png_frames(files):
    def gen(_path, w=1920, h=1080):
        for f in files:
            a = np.asarray(Image.open(f).convert("RGB"))
            assert a.shape == (h, w, 3), (f, a.shape)
            yield a
    return gen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["video", "pngseq", "reenc"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--glob", default="*.png")
    ap.add_argument("--first", type=int, default=0, help="連番の最初のコマの、動画のコマの番号（t·30）")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trim", default="", help="video：数えるコマの範囲 a,b（動画のコマの番号）。切り出してから数える")
    ap.add_argument("--win", action="append", default=[], help="関心の窓 a,b（動画のコマの番号）")
    a = ap.parse_args()
    out = absrepo(a.out)
    od = os.path.dirname(out)
    os.makedirs(od, exist_ok=True)
    S7.OUT = od
    src = absrepo(a.src)
    info = dict(kind=a.kind, name=a.name, s7_code_sha256=sha256_file(os.path.join(HERE, "pl28_s7_video.py")),
                count_code_sha256=sha256_file(os.path.abspath(__file__)))
    first = a.first
    if a.kind == "video":
        path = src
        info["src"] = os.path.relpath(src, REPO).replace("\\", "/")
        info["src_sha256"] = sha256_file(src)
        if a.trim:
            lo, hi = [int(x) for x in a.trim.split(",")]
            tmp = os.path.join(od, "_trim_%s.mp4" % a.name)
            # 無圧縮の中間を作らず、コマを選んで rgb24 で渡す（再圧縮しない）
            frames_all = list(S7.frames(src))
            sel = frames_all[lo:hi + 1]
            S7.frames = (lambda seq: (lambda _p, w=1920, h=1080: iter(seq)))(sel)
            first = lo
            path = tmp
            open(tmp, "wb").close()
        res = S7.analyse(a.name, path)
    else:
        files = sorted(glob.glob(os.path.join(src, a.glob)))
        if not files:
            raise SystemExit("PNG がありません：%s/%s" % (src, a.glob))
        info["src"] = os.path.relpath(src, REPO).replace("\\", "/")
        info["png_count"] = len(files)
        info["png_first_last"] = [os.path.basename(files[0]), os.path.basename(files[-1])]
        h = hashlib.sha256()
        for f in files:
            h.update(sha256_file(f).encode())
        info["png_list_sha256"] = h.hexdigest()
        if a.kind == "pngseq":
            S7.frames = png_frames(files)
            S7.sha256 = lambda p: info["png_list_sha256"]
            res = S7.analyse(a.name, src)
        else:
            mp4 = os.path.join(od, "reenc_%s.mp4" % a.name)
            p = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", "30", "-i", "-"]
                                 + ENC + [mp4], stdin=subprocess.PIPE)
            for f in files:
                p.stdin.write(np.asarray(Image.open(f).convert("RGB"), np.uint8).tobytes())
            p.stdin.close()
            p.wait()
            info["reenc_mp4"] = os.path.relpath(mp4, REPO).replace("\\", "/")
            info["reenc_args"] = " ".join(ENC)
            res = S7.analyse(a.name, mp4)
    # 関心の窓（動画のコマの番号 → 連番の中の位置）
    per = np.load(os.path.join(od, "per_frame_" + a.name + ".npz"))
    fb, fl = per["fb_px"], per["fl_px"]
    n = len(fb)
    wins = {}
    for w in (a.win or []):
        lo, hi = [int(x) for x in w.split(",")]
        i0, i1 = max(1, lo - first), min(n - 2, hi - first)
        if i1 < i0:
            continue
        s = slice(i0, i1 + 1)
        wins["%d_%d" % (lo, hi)] = dict(frames=[lo, hi], M1b_sum_px=int(fb[s].sum()), M1b_max_px=int(fb[s].max()),
                                         M1b_argmax_frame=int(first + i0 + int(fb[s].argmax())), M1_sum_px=int(fl[s].sum()),
                                         M1b_frames_over_50px=int((fb[s] > 50).sum()))
    res["windows_video_frames"] = wins
    res["first_video_frame"] = first
    res["info"] = info
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(name=a.name, windows=wins, all=res.get("all", {}).get("M1b_fill_flicker") if isinstance(res.get("all"), dict) else None),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
