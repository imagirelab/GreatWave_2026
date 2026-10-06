# -*- coding: utf-8 -*-
"""組み込みの準備：Unity の独立の試作の場面（F37Proto.unity）で描いた PNG を、確かめ用の動画にまとめる。
並び（3 × 2）：上＝原画カメラ、下＝座席。左＝方法 A（240 × 400 の固定の網目、コマの間を補間、試作の再生器）、
中＝方法 B（コマごとの網目、補間なし）、右＝方法 A を作品の keypose の書式にして作品の再生器（DS30SheetPlayer＋PL29UkiyoeHero）で描いたもの（t* まで）。
札：計算の名前・誘導なし・計算の時刻。P1sweep は「断面の計算を並べた試験の面（3D の流体の計算ではない）」と書く。
使い方：py -3.10 integ_video.py <seq>
出力：Unity/Build/FLIP37/integration_prep/video/<seq>_unity_check.mp4 と <seq>_unity_sheet.png（数コマの並べ図）
"""
import os, sys, glob, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C

FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = r"C:/Windows/Fonts/meiryo.ttc"
LABEL = {
    "R05": "P2 R05：3D の流体の計算（粒子 1 m、まっすぐの岩棚＋レンズ、入力 29 m）・誘導なし。この組は巻く手前まで（前の面 −82°）",
    "P1sweep": "P1 の断面の計算（粒子 0.25 m、誘導なし）を峰に沿って時刻をずらして並べた試験の面。3D の流体の計算ではない",
    "R18": "P2 R18：3D の流体の計算（粒子 1 m、交わる二つの列＋レンズ＋低い棚、入力 39 m）・誘導なし。巻き波（z=0 で空洞が閉じる 10.67 s）。t* 10.375 s",
}


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def main():
    seq = sys.argv[1]
    rd = C.OUT + "/unity_render/" + seq
    od = C.OUT + "/video"
    os.makedirs(od, exist_ok=True)
    tmp = od + "/_frames_" + seq
    os.makedirs(tmp, exist_ok=True)
    idx = json.load(open(C.OUT + "/pkg/%s/sheet/index.json" % seq, encoding="utf8"))
    t0 = idx["frames"][0]["t"]
    fps = 24.0
    names = sorted(glob.glob(rd + "/sheet_painting/f_*.png"))
    n = len(names)
    f1, f2, f3 = font(20), font(17), font(15)
    picks = []
    for i in range(n):
        tiles = []
        for cam in ("painting", "seat"):
            row = []
            for m in ("sheet", "frames", "keypose"):
                pth = rd + "/%s_%s/f_%04d.png" % (m, cam, i)
                if os.path.exists(pth):
                    im = Image.open(pth).convert("RGB")
                else:
                    im = Image.new("RGB", row[0].size, (235, 235, 235))
                    ImageDraw.Draw(im).text((20, row[0].size[1] // 2), "t* の後は keypose の包みに入れていない", fill=(80, 80, 80), font=f2)
                row.append(im)
            tiles.append(row)
        w, h = tiles[0][0].size
        top = 64
        canvas = Image.new("RGB", (3 * w, 2 * h + top), (255, 255, 255))
        dr = ImageDraw.Draw(canvas)
        t = t0 + i / fps
        dr.text((10, 6), LABEL[seq], fill=(0, 0, 0), font=f2)
        dr.text((10, 34), "計算の時刻 t = %.2f s（物理だけ・誘導なし）。材質は AS05 の平らな色（試作の白の印・帯の属性。白の区域は仮）" % t, fill=(0, 0, 0), font=f3)
        for r, cam in enumerate(("painting", "seat")):
            for c, m in enumerate(("sheet", "frames", "keypose")):
                canvas.paste(tiles[r][c], (c * w, top + r * h))
                lab = {"sheet": "方法 A：240×400 の固定の網目（コマの間を補間）", "frames": "方法 B：コマごとの流体の網目（補間なし）",
                       "keypose": "方法 A → keypose の包み・作品の再生器（属性は t* の 1 回）"}[m] + \
                      ("・原画カメラ" if cam == "painting" else "・座席（seat_v1）")
                bb = dr.textbbox((c * w + 10, top + r * h + 8), lab, font=f3)
                dr.rectangle([bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3], fill=(255, 255, 255))
                dr.text((c * w + 10, top + r * h + 8), lab, fill=(0, 0, 0), font=f3)
        canvas.save(tmp + "/c_%04d.png" % i)
        if i in (0, n // 3, 2 * n // 3, n - 1):
            picks.append(canvas.resize((canvas.width // 3, canvas.height // 3)))
    out = od + "/%s_unity_check.mp4" % seq
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", tmp + "/c_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", out], check=True)
    sheet = Image.new("RGB", (picks[0].width * 2, picks[0].height * 2), (255, 255, 255))
    for k, p in enumerate(picks):
        sheet.paste(p, ((k % 2) * p.width, (k // 2) * p.height))
    sheet.save(od + "/%s_unity_sheet.png" % seq)
    for f in glob.glob(tmp + "/c_*.png"):
        os.remove(f)
    os.rmdir(tmp)
    print("wrote", out, n, "frames", C.sha256(out))


if __name__ == "__main__":
    main()
