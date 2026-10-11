# -*- coding: utf-8 -*-
"""RT48：Unity のプレイヤーが書いた連番（frame_00000.png …、capture.json）の上の端に、帯の字を 1〜2 行足して実時間の動画にする（py -3.10、PIL・ffmpeg）。
絵そのもの（Unity が描いた画素）は変えず、上の端に半透明の帯と字を重ねるだけ。参考の動画であることを絵の中に書くために使う。
使い方:
  py -3.10 v_banner.py <連番のフォルダー> <出力.mp4> <字の 1 行目> [<字の 2 行目>]"""
import sys, os, json, time, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT_B = "C:/Windows/Fonts/YuGothB.ttc"


def main(d, out, lines):
    cap = json.load(open(os.path.join(d, "capture.json"), encoding="utf-8-sig"))
    n, fps = int(cap["frames"]), float(cap["fps"])
    W, H = [int(v) for v in cap["size"].split("x")]
    f_b = ImageFont.truetype(FONT_B, 24)
    lh = 32
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    dr.rectangle((0, 0, W, 14 + lh * len(lines)), fill=(0, 0, 0, 150))
    for k, ln in enumerate(lines):
        dr.text((20, 8 + k * lh), ln, font=f_b, fill=(255, 236, 150))
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "%g" % fps,
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    T0 = time.time()
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        im = Image.open(os.path.join(d, "frame_%05d.png" % i)).convert("RGBA")
        im = Image.alpha_composite(im, ov).convert("RGB")
        pr.stdin.write(np.asarray(im).tobytes())
        if i % 240 == 0:
            print("frame", i, "/", n, round(time.time() - T0, 1), "s", flush=True)
    pr.stdin.close()
    rc = pr.wait()
    info = dict(file=out, src_dir=d, capture=cap, banner=lines, ffmpeg_rc=rc, seconds=round(time.time() - T0, 1),
                note="Unity のプレイヤーの画素の上の端に字の帯を重ねただけ（libx264、preset slow、crf 18、yuv420p）")
    json.dump(info, open(out + ".json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
