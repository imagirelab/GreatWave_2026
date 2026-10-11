# -*- coding: utf-8 -*-
"""RT48：船の外の試しの視点の連番（Unity Editor の RT48OutsideCapture が書いた PNG）に字を足して、実時間の動画にする（py -3.10、PIL・ffmpeg）。
使い方:
  py -3.10 v_outside.py <連番のフォルダー（capture.json のある所）> <出力.mp4> [crf（既定 20）]
字：上に「Unity の描画・船の外の試しの視点（体験では見えない所）」と時刻、下に字 1・2・3・4、K から先は 6、最初の接触から 7、いまのコマ（補間の有無）。
絵そのもの（Unity が描いた画素）は変えず、字の帯を重ねるだけ。"""
import sys, os, json, time, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONT_B = "C:/Windows/Fonts/YuGothB.ttc"
VIEW_JA = {"endon": "端から（掃いた面の端の 70 m 外から頂の向きに見る。手前の縁が断面。カメラは頂に付いて x の向きに動く）",
           "oblique": "斜めから（止めたカメラ：座席の 8 m 前・頂の向きに 50 m 離れ・高さ 7 m）",
           "high": "斜め上から（止めたカメラ：座席の 20 m 後ろ・頂の向きに 40 m 離れ・高さ 15 m で頂より上）"}


def wrap(s, n):
    out, line = [], ""
    for ch in s:
        line += ch
        if len(line) >= n and ch in "、。）":
            out.append(line); line = "　"
    if line.strip():
        out.append(line)
    return out


def main(d, out, crf="20"):
    cap = json.load(open(os.path.join(d, "capture.json"), encoding="utf-8-sig"))
    idx = json.load(open(os.path.join(BUILD, "data", "manifest.json"), encoding="utf8"))
    src = cap["source"]
    man = json.load(open(os.path.join(BUILD, "data", src, "manifest.json"), encoding="utf8"))
    C = idx["captions"]
    K = man["playback"]["K"]
    tc = man["events"]["first_contact_t"]
    f_b = ImageFont.truetype(FONT_B, 26)
    f_s = ImageFont.truetype(FONT, 20)
    W, H = cap["width"], cap["height"]
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "%g" % cap["fps"],
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    T0 = time.time()
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for r in cap["rows"]:
        im = Image.open(os.path.join(d, "frame_%05d.png" % r["i"])).convert("RGB")
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        head = "Unity の描画（Editor）・船の外の試しの視点（体験の座席からは見えない所）"
        view = VIEW_JA.get(cap["view"], cap["view"])
        c2 = (idx.get("checks") or {}).get("C2")
        ref = []
        if src == "fine" and c2 is not None and not c2.get("pass_all"):
            ref = ["参考：細かい面の確かめ C2 の %s が外れたため、計画の決まりでは報告の元は粗い元のまま" % "・".join("(%s)" % q for q in "abcde" if c2.get(q) is False)]
        lines = ref + wrap("1 " + C["1"], 120) + ["2 " + C["2"], "3 " + C["3_" + src], "4 巻き始め %.1f s・唇が前の面に付く %.1f s　　5 %s" % (
            man["events"]["onset_t"], tc, C["5"])]
        if K is not None and r["frame"] >= K:
            lines.append("6 " + C["6"])
        if r["t"] >= tc - 1e-9:
            lines += wrap("7 " + C["7"], 110)
        lines.append("いま：%s　船（座席 %d m）：上下 %+.2f m・縦揺れ %+.2f°" % (r["label"], cap["seatX"], r["heave"], r["pitchDeg"]))
        dr.rectangle((0, 0, W, 78), fill=(0, 0, 0, 140))
        dr.text((20, 8), head, font=f_b, fill=(250, 250, 250))
        dr.text((20, 44), view, font=f_s, fill=(235, 235, 235))
        dr.text((W - 20, 8), "計算の時刻 %.3f s" % r["t"], font=f_b, fill=(250, 250, 250), anchor="ra")
        lh = 27
        y0 = H - 14 - lh * len(lines)
        dr.rectangle((0, y0 - 10, W, H), fill=(0, 0, 0, 140))
        for k, ln in enumerate(lines):
            dr.text((20, y0 + k * lh), ln, font=f_s, fill=(245, 245, 245))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        pr.stdin.write(np.asarray(im).tobytes())
        if r["i"] % 120 == 0:
            print("frame", r["i"], "/", cap["frames"], round(time.time() - T0, 1), "s", flush=True)
    pr.stdin.close()
    rc = pr.wait()
    info = dict(file=out, src_dir=d, view=cap["view"], source=src, frames=cap["frames"], fps=cap["fps"], t_first=cap["from"], t_last=cap["rows"][-1]["t"],
                ffmpeg_rc=rc, crf=str(crf), seconds=round(time.time() - T0, 1), note="Unity Editor の画素に字の帯を重ねただけ")
    json.dump(info, open(out + ".json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:4]))
