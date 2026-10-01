# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：前後の図（1920×1080）と回り台の並べ動画を作る（py -3.10、PIL・ffmpeg）。
入力は Unity/Build/Polish/28r01/shoulder/final/renders（rays_bl.py の粘土、土台 P28R2rec と候補 P28R01SH の同じ視点）と
trials_renders（試した案）。出力は Unity/Build/Polish/28r01/shoulder/final/sheets。
usage: py -3.10 r01_shoulder_fig.py <shoulder_dir>
"""
import os
import sys
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
BASE, CAND = "P28R2rec", "P28R01SH"


def font(sz):
    for p in (r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


F16, F20, F26 = font(16), font(20), font(26)


def tile(path, w, h, label=None, f=F16):
    im = Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)
    if label:
        d = ImageDraw.Draw(im)
        tw = d.textlength(label, font=f)
        d.rectangle([0, 0, tw + 10, f.size + 8], fill=(0, 0, 0))
        d.text((5, 3), label, fill=(255, 230, 0), font=f)
    return im


def text_panel(w, h, lines, f=F20, title=None):
    im = Image.new("RGB", (w, h), (250, 250, 247))
    d = ImageDraw.Draw(im)
    y = 10
    if title:
        d.text((12, y), title, fill=(0, 0, 0), font=F26); y += 40
    for ln in lines:
        d.text((12, y), ln, fill=(20, 20, 20), font=f); y += f.size + 8
    return im


def main():
    sd = sys.argv[1]
    R = os.path.join(sd, "final", "renders")
    T = os.path.join(sd, "trials_renders")
    out = os.path.join(sd, "final", "sheets")
    os.makedirs(out, exist_ok=True)
    rp = lambda lab, v: os.path.join(R, "%s__%s.png" % (lab, v))

    # (a) 後ろの 3 視点＋拡大
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    for k, v in enumerate(["b65_back65_clay", "b90_back_straight", "b115_back_minus_c"]):
        W.paste(tile(rp(BASE, v), 640, 360, "%s（土台）| %s" % (BASE, v)), (0, 360 * k))
        W.paste(tile(rp(CAND, v), 640, 360, "%s（SHOULDER）| %s" % (CAND, v)), (640, 360 * k))
    W.paste(tile(rp(BASE, "b65z_back65_zoom"), 640, 360, "%s | b65z 拡大" % BASE), (1280, 0))
    W.paste(tile(rp(CAND, "b65z_back65_zoom"), 640, 360, "%s | b65z 拡大" % CAND), (1280, 360))
    W.paste(text_panel(640, 360, [
        "原画の頂はそのまま。輪郭の縁より奥の背の殻だけを",
        "c 方向に少しずつ後ろへ伸ばした（k 0 → 2.0、c −8 → +12）。",
        "原画視点の z バッファーと外殻線は土台と画素まで同じ。",
        "目で見て：ドーム（中ほどの丸い頭巾の頂）は消えていない。",
        "後ろ 65° で奥の端の縦の壁が長い斜面に変わっただけ。",
        "真後ろでは同じ丸い山の輪郭に、左下の裾の暗い凹みが増えた。",
        "真上からは奥の端が後ろへ長く引かれた鰭になる（Q21 の否）。",
    ], F16, title="仕上げ28修正01 SHOULDER：後ろから"), (1280, 720))
    W.save(os.path.join(out, "fig_r01sh_back_views.png"))

    # (b) 9 視点＋利用者の失敗の視点（土台｜候補）
    std = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
           "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
    usr = ["u10_foot_zoom", "u11_v9zoom_crest_bulge", "u12a_v5_back_three_quarter", "u13_v8zoom_b_region", "b65z_back65_zoom"]
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    for k, v in enumerate(std + usr):
        r, cpair = divmod(k, 3)
        x = cpair * 640; y = r * 180
        W.paste(tile(rp(BASE, v), 320, 180, "土台 %s" % v.split("_")[0], F16), (x, y))
        W.paste(tile(rp(CAND, v), 320, 180, "SH %s" % v.split("_")[0], F16), (x + 320, y))
    W.paste(text_panel(640, 180, ["9 視点（v1〜v9）と Q21 の失敗の視点（u10〜u13）、b65z。",
                                  "各組の左＝土台 P28R2rec、右＝SHOULDER P28R01SH。",
                                  "原画視点 v1 は画素まで同じ（z バッファーで確かめた）。"], F16), (1280, 900))
    W.save(os.path.join(out, "fig_r01sh_9views.png"))

    # (c) 回り台（12 コマ）と真上・横
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    fr = ["f_%04d.png" % f for f in range(0, 240, 20)]
    for k, f in enumerate(fr):
        col = k % 6; rr = (k // 6) * 2
        W.paste(tile(os.path.join(R, "turntable_%s" % BASE, f), 320, 180, "土台 %s" % f[2:6], F16), (col * 320, rr * 180))
        W.paste(tile(os.path.join(R, "turntable_%s" % CAND, f), 320, 180, "SH %s" % f[2:6], F16), (col * 320, (rr + 1) * 180))
    for k, (lab, v) in enumerate([(BASE, "v6_top_down"), (CAND, "v6_top_down"), (BASE, "v3_side_along_crest_cam_side"), (CAND, "v3_side_along_crest_cam_side")]):
        W.paste(tile(rp(lab, v), 480, 360, "%s | %s" % (lab, v.split("_")[0] + " " + ("真上" if "v6" in v else "波峰に沿った横"))), (k * 480, 720))
    W.save(os.path.join(out, "fig_r01sh_turntable_top_side.png"))

    # (d) 試した案（後ろ 65°・真後ろ・真上）：6 列 × 2 組（各組 3 行）、320×180
    labs = ["S1", "S2", "S3", "S5", "S7", "S8", "S9", "S10", "S11"]
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    cols = [(BASE, R)] + [(l, T) for l in labs] + [(CAND, R)]
    for k, (lab, d) in enumerate(cols):
        grp, col = divmod(k, 6)
        for r, v in enumerate(["b65_back65_clay", "b90_back_straight", "v6_top_down"]):
            p = os.path.join(d, "%s__%s.png" % (lab, v))
            nm = "S12＝候補 " + lab if lab == CAND else lab
            W.paste(tile(p, 320, 180, nm if r == 0 else None, F16), (col * 320, grp * 540 + r * 180))
    W.paste(text_panel(320, 540, ["試した案（S1〜S12）", "行：後ろ 65°・真後ろ・真上", "左上が土台 P28R2rec。",
                                  "どれも原画視点は土台と", "画素まで同じ。", "中ほどの丸い頂（ドーム）は", "どの案でも残る。",
                                  "S8〜S12：奥の端が長い斜面", "（後ろ 65°）になるが、", "真上で後ろへ引かれた鰭。",
                                  "各案の中身と数値は", "final/trials_table.json"], F16), (5 * 320, 540))
    W.save(os.path.join(out, "fig_r01sh_trials.png"))

    # (e) 回り台の並べ動画（土台｜候補、1920×540、5 MB 以下）
    a = os.path.join(R, "turntable_%s.mp4" % BASE); b = os.path.join(R, "turntable_%s.mp4" % CAND)
    mp4 = os.path.join(out, "r01sh_turntable_P28R2rec_vs_P28R01SH.mp4")
    flt = ("[0:v]scale=960:540,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='P28R2rec (base)':x=10:y=10:fontsize=26:fontcolor=yellow:box=1:boxcolor=black[a];"
           "[1:v]scale=960:540,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='P28R01SH (SHOULDER)':x=10:y=10:fontsize=26:fontcolor=yellow:box=1:boxcolor=black[b];"
           "[a][b]hstack=inputs=2[v]")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", a, "-i", b, "-filter_complex", flt, "-map", "[v]", "-c:v", "libx264", "-crf", "26",
           "-preset", "slow", "-pix_fmt", "yuv420p", mp4]
    subprocess.run(cmd, check=True)
    print("mp4", mp4, os.path.getsize(mp4))
    for f in sorted(os.listdir(out)):
        print(f, os.path.getsize(os.path.join(out, f)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
