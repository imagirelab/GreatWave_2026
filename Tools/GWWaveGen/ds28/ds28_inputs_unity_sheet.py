# -*- coding: utf-8 -*-
"""設計28：入力条件の変更の Unity の静止画（設計27 の再生器、run_ds27_unity.ps1 で描いたもの）を並べる。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_unity_sheet.py
入力（Git 対象外）：Unity/Build/Design/28/inputs/unity/<名前>/stills/、比べる基準に設計27 の入れた版の段階の静止画
  Unity/Build/Design/27/art_on_default_stages/stills/（設計27 の段階の τ で描いたもの）
出力：Unity/Build/Design/28/inputs/fig_ds28_inputs_unity_side.png・fig_ds28_inputs_unity_painting.png
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Design")
OUT = os.path.join(B, "28", "inputs")
FONT = "C:/Windows/Fonts/YuGothM.ttc"
SIDE_CROP = (240, 260, 1680, 1070)      # 設計27 の ds27_evidence.py と同じ（左の側面は画面の中ほどを 16:9 で切り出す）
ROWS = [("設計27 入れた版\n（t* = K*。段階は\n設計27 の τ）", os.path.join(B, "27", "art_on_default_stages", "stills")),
        ("物理だけ\nΔθ 60°・λp 195 m", os.path.join(OUT, "unity", "in_d60_l195", "stills")),
        ("物理だけ\nΔθ 0°・λp 195 m", os.path.join(OUT, "unity", "in_d0_l195", "stills")),
        ("物理だけ\nΔθ 120°・λp 195 m", os.path.join(OUT, "unity", "in_d120_l195", "stills"))]
COLS = ["a", "b", "c", "d", "apex", "tstar"]
NAMES = {"a": "a 丸い峰", "b": "b 尖った峰（塔）", "c": "c 鉛直の壁", "d": "d 先が前へ返る", "apex": "唇先の頂点ごろ", "tstar": "t*"}


def font(s):
    return ImageFont.truetype(FONT, s)


def sheet(view, path, crop=None, W=320, H=180):
    lab = 200
    img = Image.new("RGB", (lab + W * len(COLS), 50 + len(ROWS) * (H + 28) + 70), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, c in enumerate(COLS):
        d.text((lab + k * W + 6, 18), NAMES[c], fill=(0, 0, 0), font=font(16))
    y = 50
    for title, sd in ROWS:
        d.text((6, y + 4), title, fill=(0, 0, 0), font=font(15))
        for k, c in enumerate(COLS):
            f = glob.glob(os.path.join(sd, "ds27_%s_%s_tau*.png" % (view, c)))
            if not f:
                continue
            im = Image.open(f[0]).convert("RGB")
            if crop and im.size == (1920, 1080):
                im = im.crop(crop)
            img.paste(im.resize((W - 4, H), Image.LANCZOS), (lab + k * W, y))
            tau = os.path.basename(f[0]).split("_tau")[1][:-4]
            d.text((lab + k * W + 4, y + H + 3), "τ = %s s" % tau, fill=(0, 0, 0), font=font(13))
        y += H + 28
    notes = ["Unity 6000.4.3f1 の PC オフスクリーン描画（設計27 の再生器 DS27KeyposePlayer・場面 DS27_Formation を変えずに、設計28 のパッケージを読ませた）。HMD 実機ではない。",
             "物理だけ＝設計27 の生成器の切った版＋物理の頂の高さ、錨の K* への ease-in なし（ds28_inputs_model.InputGen）。段階の τ は設計26 §3.1 の表（峰の行）で、この 3 本で段階が成り立った時刻ではない。",
             "色は 28修正01 の UV の焼き込みのまま（設計36・38 の範囲）。パッケージの節点の適応は 1 回・1 区間 1 点の簡易版（設計27 の 2.5 mm の規則は確かめていない）。"]
    for i, t in enumerate(notes):
        d.text((6, y + 4 + 20 * i), t, fill=(0, 0, 0), font=font(13))
    img.save(path)
    return path


if __name__ == "__main__":
    print(sheet("side_left", os.path.join(OUT, "fig_ds28_inputs_unity_side.png"), SIDE_CROP))
    print(sheet("painting", os.path.join(OUT, "fig_ds28_inputs_unity_painting.png")))
