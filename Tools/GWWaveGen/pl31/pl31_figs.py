# -*- coding: utf-8 -*-
"""仕上げ31 の項目ごとの図（1920×1080。既にある描画と数を並べるだけ）。

  fig_pl31_white_onset.png  白の出現：numpy の割合の曲線（30 Hz、2% の線）と 135 の 10 区間の到着、Unity の色区 ID（白＝赤）の時刻ごとの前後
  fig_pl31_spray_tstar.png  原画視点 t* の飛沫：原画｜前｜後（目で照合した原画の点を緑の丸）と、151 の色
  fig_pl31_spray_3d.png     原画視点の外の飛沫（座席から波の方向・後ろ 65°・右の側面・回り台）の前後の拡大
  fig_pl31_f8.png           F8（固定配置と短い落下）の版と採った版の比べ（t 11・11.6・12 s）
  fig_pl31_dots_eye.png     原画の白い点の取り出しと目の照合（区域の 186、右上の空 15、船の近く 9、採らなかった 50）
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_figs.py --before Unity/Build/Polish/31/r_before2 --after Unity/Build/Polish/31/r_final2 --f8 Unity/Build/Polish/31/r_f8 --out Docs/Evidence/Polish/31
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, label, head, fit  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
B31 = REPO + "/Unity/Build/Polish/31"


def crop_fit(p, box, size):
    if not os.path.exists(p):
        return Image.new("RGB", size, (200, 200, 200))
    return fit(Image.open(p).convert("RGB").crop(box), size)


def plot_curves(W0, W1, size):
    """numpy の白の割合（表面の面積）の曲線と 1 コマの増分。matplotlib を使わず PIL で描く。"""
    w, h = size
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 60, 30, w - 20, h - 50
    d.rectangle([x0, y0, x1, y1], outline=(120, 120, 120))
    t = np.array(W1["series"]["t"])
    def X(tt): return x0 + (tt - 5.0) / 7.5 * (x1 - x0)
    def Y(f): return y1 - f * (y1 - y0)
    for tt in range(5, 13):
        d.line([X(tt), y1, X(tt), y1 + 5], fill=(80, 80, 80)); d.text((X(tt) - 6, y1 + 8), str(tt), fill=(40, 40, 40), font=font(13))
    for f in (0, 0.5, 1.0):
        d.text((x0 - 40, Y(f) - 8), "%.1f" % f, fill=(40, 40, 40), font=font(13))
    for W, col in ((W0, (150, 150, 150)), (W1, (200, 40, 40))):
        f = np.array(W["series"]["surface_fraction"])
        pts = [(X(tt), Y(v)) for tt, v in zip(t, f) if 5.0 <= tt <= 12.5]
        d.line(pts, fill=col, width=3)
        inc = np.diff(f)
        pts2 = [(X(tt), Y(min(v / 0.04, 1.0) * 0.35)) for tt, v in zip(t[1:], inc) if 5.0 <= tt <= 12.5]
        d.line(pts2, fill=tuple(int(c * 0.7) for c in col), width=1)
    d.line([X(5), Y(0.02 / 0.04 * 0.35), X(12.5), Y(0.02 / 0.04 * 0.35)], fill=(40, 120, 40), width=1)
    d.text((x0 + 8, y0 + 6), "白の割合（t* の面の上の面積、終態の白＝1）  灰：前（G_p28rec の T_white）  赤：後（修正01）", fill=(20, 20, 20), font=font(14, True))
    d.text((x0 + 8, y0 + 28), "下の細い線：30 Hz の 1 コマの増分（緑の線が 2%%）。前 最大 %.2f%%（2%% 超 %d コマ）、後 最大 %.2f%%（%d コマ）" % (
        100 * W0["surface_fraction_max_increment"], W0["surface_frames_over_2pct"], 100 * W1["surface_fraction_max_increment"], W1["surface_frames_over_2pct"]),
        fill=(20, 20, 20), font=font(13))
    d.text((x1 - 60, y1 + 26), "t（s）", fill=(40, 40, 40), font=font(13))
    return im


def plot_bins(N0, N1, size):
    w, h = size
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 60, 50, w - 20, h - 50
    d.rectangle([x0, y0, x1, y1], outline=(120, 120, 120))
    def X(i): return x0 + (i + 0.5) / 10 * (x1 - x0)
    def Y(tt): return y1 - (tt - 6.5) / 4.5 * (y1 - y0)
    for tt in (7, 8, 9, 10, 11):
        d.text((x0 - 30, Y(tt) - 8), str(tt), fill=(40, 40, 40), font=font(13)); d.line([x0, Y(tt), x0 + 5, Y(tt)], fill=(80, 80, 80))
    for N, col in ((N0, (150, 150, 150)), (N1, (200, 40, 40))):
        m = N["b135"]["front"]["bins_t_median"]
        d.line([(X(i), Y(v)) for i, v in enumerate(m)], fill=col, width=3)
        for i, v in enumerate(m):
            d.ellipse([X(i) - 4, Y(v) - 4, X(i) + 4, Y(v) + 4], fill=col)
    k = N1["b135"]["front"]["bins_key_median"]
    for i, v in enumerate(k):
        d.text((X(i) - 14, y1 + 8), "%.2f" % v, fill=(40, 40, 40), font=font(12))
    d.text((x0 + 8, 8), "135：前の白の 10 区間（流れの座標 F：頂 1 → 唇の先 2 → 下面）の到着の時刻の中央値", fill=(20, 20, 20), font=font(14, True))
    d.text((x0 + 8, 28), "灰：前 順位相関 %.2f　赤：後 %.2f（背の白は前後とも %.2f）" % (N0["b135"]["front"]["spearman_bins"], N1["b135"]["front"]["spearman_bins"],
                                                                N1["b135"]["back"]["spearman_bins"]), fill=(20, 20, 20), font=font(13))
    d.text((x1 - 140, y1 + 28), "F（区間の中央値）", fill=(40, 40, 40), font=font(12))
    return im


def fig_white(a, out):
    N0 = json.load(open(B31 + "/white_before/pl31_white_numpy.json", encoding="utf-8"))
    N1 = json.load(open(B31 + "/white/pl31_white_numpy.json", encoding="utf-8"))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ31 白の出現（102・135）｜上：numpy の数　下：Unity の色区 ID の白（赤）、同じ視点・同じ時刻の前と後",
         "前＝コミットした仕上げ30（G_p28rec の T_white：唇の先の近くから白くなり頂へ戻る）。後＝修正01 の pl31_white_order（頂の最も高い所から面の上の距離の順）＋ pl31_white_claw_pin（爪の根元は伸び始めまでに白）（1 コマ 2% 以下。pl31_white_rate_cap は掛からなかった）。Unity の PC 描画。")
    im.paste(plot_curves(N0["b102_before"], N1["b102_after"], (950, 330)), (6, 68))
    im.paste(plot_bins(N0, N1, (950, 330)), (962, 68))
    ts = [("t065", "6.5 s"), ("t070", "7 s"), ("t080", "8 s"), ("t090", "9 s"), ("t100", "10 s"), ("t110", "11 s")]
    views = [("side_left", (380, 300, 1540, 860), "左の側面"), ("painting", (0, 30, 1240, 820), "原画視点")]
    tw, th = 316, 160
    y = 404
    for v, box, vn in views:
        for si, (lab, root) in enumerate((("前", a.before), ("後", a.after))):
            for k, (t, tn) in enumerate(ts):
                x = 4 + k * (tw + 4)
                p = os.path.join(root, "white", "%s_%s_on.png" % (v, t))
                im.paste(crop_fit(p, box, (tw, th)), (x, y))
                label(d, x + 3, y + 3, "%s｜%s｜%s" % (lab, vn, tn), 12)
            y += th + 3
        y += 4
    p = os.path.join(out, "fig_pl31_white_onset.png"); im.save(p)
    return p


def fig_spray_tstar(a, out):
    spec = json.load(open(REPO + "/Tools/PaintingTruth/painting_truth.json", encoding="utf-8"))
    df = spec["display_frame"]; s = df["scale"]; o = df["offset_x"]
    ref = cv2.imread(os.path.join(REPO, spec["reference"]["path"]))
    disp = cv2.warpAffine(cv2.GaussianBlur(ref, (0, 0), 1.0), np.float32([[1 / s, 0, (0.5 - o) / s - 0.5], [0, 1 / s, 0.5 / s - 0.5]]), (1920, 1080),
                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    paint = Image.fromarray(disp[..., ::-1])
    dots = json.load(open(B31 + "/spray/pl31_spray_dots.json", encoding="utf-8"))["dots"]
    box = (760, 260, 1500, 780)
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    M = json.load(open(B31 + "/measure_fx01/pl31_measure.json", encoding="utf-8"))
    G = json.load(open(B31 + "/spray/pl31_spray_generate_log.json", encoding="utf-8"))
    head(d, "仕上げ31 原画視点 t* の飛沫（149〜152）｜左：原画　中：前（設計31 の 186 粒）　右：後（%s 粒のうち原画の点 210 と、ここで見える子）" % "{:,}".format(G["summary"]["total"]),
         "緑の丸＝目で照合して採った原画の白い点（区域 186・右上の空 15・船の近く 9）。子の {:,} 粒は原画視点の t* では原画の点の中（{}）か白の上（{}）に狙って置いた（描画で確かめて見えた子を除いた）。Unity の PC 描画。".format(G["summary"]["children"], G["children"]["rules"].get("inside_dot", 0), G["children"]["rules"].get("over_white", 0)))
    W, H = 632, 444
    for k, src in enumerate([("原画", paint), ("前", os.path.join(a.before, "full", "painting_t120_off.png")), ("後", os.path.join(a.after, "full", "painting_t120_off.png"))]):
        lab, p = src
        img = p if isinstance(p, Image.Image) else Image.open(p).convert("RGB")
        c = img.crop(box)
        sc = W / float(box[2] - box[0])
        c = c.resize((W, int(round((box[3] - box[1]) * sc))), Image.LANCZOS)
        dd = ImageDraw.Draw(c)
        if k != 1:
            for q in dots:
                x, y = (q["x_d"] - box[0]) * sc, (q["y_d"] - box[1]) * sc
                r = max(3, 0.5 * q["diam_display_px"] * sc + 3)
                dd.ellipse([x - r, y - r, x + r, y + r], outline=(0, 170, 0))
        im.paste(c, (4 + k * (W + 4), 68))
        label(d, 8 + k * (W + 4), 72, lab)
    sb, sa = M["spray"]["before"], M["spray"]["after"]
    cl = G["colour"]
    lines = [
        "数（原画視点 t*、飛沫あり − 飛沫なしの差）：前 塊 %d・画素 %d、原画の点の円の外の塊 %d　→　後 塊 %d・画素 %d、外の塊 %d（%d 画素）。空の上の方（行 0〜379）で飛沫が変える画素 前 %d → 後 %d" % (
            sb["components"], sb["spray_px"], sb["components_outside_dots"], sa["components"], sa["spray_px"], sa["components_outside_dots"], sa["px_outside_dots"],
            sb["sky_top_rows0_379_px"], sa["sky_top_rows0_379_px"]),
        "151 ΔE00（色の読み：原画の点の中心と粒の色）：前（白 1 色）中央値 %.2f・p90 %.2f・最大 %.1f・5 超 %d　→　後（限定色 2 段：白 %s、灰の白 %s、t* の高さ ≤ %.1f m）中央値 %.2f・p90 %.2f・最大 %.1f・5 超 %d" % (
            cl["de00_white_only"]["median"], cl["de00_white_only"]["p90"], cl["de00_white_only"]["max"], cl["de00_white_only"]["over5"], tuple(cl["white_srgb8"]),
            tuple(cl["grey_srgb8"]), cl["split_y_m"], cl["de00_two_tones"]["median"], cl["de00_two_tones"]["p90"], cl["de00_two_tones"]["max"], cl["de00_two_tones"]["over5"]),
        "151 ΔE00（描画の読み：Unity の画像の点の中心 3×3 と原画の点）：前 中央値 %.2f・p90 %.2f・最大 %.1f・5 超 %d　→　後 中央値 %.2f・p90 %.2f・最大 %.1f・5 超 %d" % (
            sb["de00_render_at_dots"]["median"], sb["de00_render_at_dots"]["p90"], sb["de00_render_at_dots"]["max"], sb["de00_render_at_dots"]["over5"],
            sa["de00_render_at_dots"]["median"], sa["de00_render_at_dots"]["p90"], sa["de00_render_at_dots"]["max"], sa["de00_render_at_dots"]["over5"]),
        "親 210：逆弾道 %d・F8 %d（150 で落とした 0）。放出点は全部が材質の白の範囲の頂点で、放出の時に白（%d／%d）。t* に主役波の前に来る原画の点 %d は、今の色がその画素で白なので残した" % (
            G["emit"]["ballistic"], G["emit"]["f8"], G["summary"]["emitters_white_before_emit"], G["summary"]["emitters_total"], G["place"]["over_hero"]),
    ]
    yy = 68 + int(round((box[3] - box[1]) * W / float(box[2] - box[0]))) + 12
    for ln in lines:
        d.text((10, yy), ln, fill=(20, 20, 20), font=font(15)); yy += 30
    # 白の範囲の放出点（t* の原画視点の白の上の点の拡大）
    p = os.path.join(out, "fig_pl31_spray_tstar.png"); im.save(p)
    return p


def fig_spray_3d(a, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ31 原画視点の外の飛沫｜各組の左：前（186 粒）　右：後（修正01）、同じ視点・同じ時刻の拡大（作品のまま）",
         "子の粒は t* の狙いの位置（原画の点の射線のまわりか、白い面の手前 0.3〜2 m）から逆弾道で放出点（Hash1 によらない白の範囲）を探した。どれも 150（主役波・近い海・遠い海の全部）を通った。Unity の PC 描画。")
    items = [("seat_toward_wave", "t105", (360, 0, 1560, 675), "座席から波の方向 t 10.5 s"), ("seat_toward_wave", "t120", (360, 0, 1560, 675), "座席から波の方向 t*"),
             ("back65", "t105", (480, 160, 1440, 700), "後ろ 65° t 10.5 s"), ("side_right", "t105", (500, 200, 1420, 717), "右の側面 t 10.5 s"),
             ("tt", "t105_az300", (400, 150, 1500, 770), "回り台 300° t 10.5 s"), ("tt", "t120_az060", (300, 150, 1400, 770), "回り台 60° t*")]
    tw, th = 474, 300
    for k, (v, t, box, nm) in enumerate(items):
        col, row = k % 2, k // 2
        for si, root in enumerate((a.before, a.after)):
            x = 4 + (2 * col + si) * (tw + 4)
            y = 68 + row * (th + 34)
            p = os.path.join(root, "tt", "%s_claws.png" % t) if v == "tt" else os.path.join(root, "views", "%s_%s_asis.png" % (v, t))
            im.paste(crop_fit(p, box, (tw, th)), (x, y))
            label(d, x + 4, y + 4, "%s｜%s" % ("前" if si == 0 else "後", nm), 13)
    p = os.path.join(out, "fig_pl31_spray_3d.png"); im.save(p)
    return p


def fig_f8(a, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ31 F8（t* 付近の固定配置と短い落下）の見え方｜上：F8 の版（原画の点 210 を全部 F8）　下：採った版（逆弾道 205・F8 5 と子）",
         "F8：t* の位置へ唇の水平の速さで運ばれながら 0.4 s（τ）落ちて着く。逆弾道で解けない点の予備。Unity の PC 描画。")
    cols = [("painting", "t110", (760, 260, 1500, 780), "原画視点 t 11 s"), ("painting", "t116", (760, 260, 1500, 780), "原画視点 t 11.6 s"),
            ("seat_toward_wave", "t116", (360, 0, 1560, 675), "座席から波の方向 t 11.6 s"), ("side_left", "t116", (560, 200, 1360, 650), "左の側面 t 11.6 s")]
    tw, th = 474, 470
    for k, (v, t, box, nm) in enumerate(cols):
        for si, root in enumerate((a.f8, a.after_f8times)):
            x, y = 4 + k * (tw + 4), 68 + si * (th + 4)
            im.paste(crop_fit(os.path.join(root, "views", "%s_%s_asis.png" % (v, t)), box, (tw, th)), (x, y))
            label(d, x + 4, y + 4, "%s｜%s" % ("F8 の版" if si == 0 else "採った版", nm), 13)
    p = os.path.join(out, "fig_pl31_f8.png"); im.save(p)
    return p


def fig_dots(out):
    spec = json.load(open(REPO + "/Tools/PaintingTruth/painting_truth.json", encoding="utf-8"))
    df = spec["display_frame"]; s = df["scale"]; o = df["offset_x"]
    ref = cv2.imread(os.path.join(REPO, spec["reference"]["path"]))
    disp = cv2.warpAffine(cv2.GaussianBlur(ref, (0, 0), 1.0), np.float32([[1 / s, 0, (0.5 - o) / s - 0.5], [0, 1 / s, 0.5 / s - 0.5]]), (1920, 1080),
                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    img = disp.copy()
    alld = json.load(open(B31 + "/_explore/dots_all.json"))
    acc = json.load(open(B31 + "/spray/pl31_spray_dots.json", encoding="utf-8"))["dots"]
    A = np.array([[q["x_d"], q["y_d"]] for q in acc])
    z = [790, 290, 1260, 770]
    cv2.rectangle(img, (z[0], z[1]), (z[2], z[3]), (60, 60, 200), 1)
    for q in alld:
        x, y = q["x_d"], q["y_d"]
        ok = (np.hypot(A[:, 0] - x, A[:, 1] - y) < 1.0).any()
        inz = z[0] <= x <= z[2] and z[1] <= y <= z[3]
        col = (0, 0, 230) if inz else ((0, 170, 0) if ok else (160, 160, 160))
        cv2.circle(img, (int(round(x)), int(round(y))), max(4, int(q["diam_display_px"]) + 2), col, 2 if ok or inz else 1)
    im = Image.fromarray(img[..., ::-1])
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 56], fill=(28, 36, 52))
    d.text((12, 4), "仕上げ31 原画の白い点の取り出しと目の照合｜赤：唇の前の区域 186（採る）　緑：区域の外で目で採った 24（右上の空 15・船の近く 9）　灰：採らなかった 50", fill=(255, 255, 255), font=font(20, True))
    d.text((12, 32), "灰の内訳：紙の地・雲の地 34、画面の端 8、題箋・落款の文字の縁 4、淡くて判断のつかないもの 4。左の波の上の空に白い点はなかった。照合は 1 人の目で 1 回（Tools/GWWaveGen/pl31/pl31_dots_eye.json）。", fill=(205, 212, 225), font=font(14))
    p = os.path.join(out, "fig_pl31_dots_eye.png"); im.save(p)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--f8", required=True)
    ap.add_argument("--after-f8times", required=True, help="採った版を F8 の版と同じ時刻で描いたフォルダー")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in (fig_white(a, a.out), fig_spray_tstar(a, a.out), fig_spray_3d(a, a.out), fig_f8(a, a.out), fig_dots(a.out)):
        print(f)


if __name__ == "__main__":
    main()
