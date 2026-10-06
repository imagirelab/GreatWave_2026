# -*- coding: utf-8 -*-
"""P2 の一覧の図（py -3.10）。各計算の sheet.png の左の原画視点のシルエットの重ね（960×540）と、
左前の斜めの粘土（clay_fXXXX_leftfront315.png）を、計算ごとに 1 行に並べる。
使い方: py -3.10 p2_overview.py <out.png> <run_id> ...
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont

P2 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2"


def font(sz):
    for p in ("C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main(out, rids):
    tw, th = 640, 360
    rows = []
    for rid in rids:
        rd = os.path.join(P2, rid)
        try:
            an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
        except Exception:
            continue
        b = an.get("best") or {}; a = an.get("at_best") or {}
        sh = Image.open(os.path.join(rd, "sheet.png")).crop((0, 40, 960, 580)).resize((tw, th), Image.LANCZOS)
        cl = os.path.join(rd, "clay_f%04d_leftfront315.png" % b.get("frame", 0))
        cp = os.path.join(rd, "clay_f%04d_painting.png" % b.get("frame", 0))
        im2 = Image.open(cl).convert("RGB").resize((tw, th), Image.LANCZOS) if os.path.isfile(cl) else Image.new("RGB", (tw, th), (230, 230, 230))
        im3 = Image.open(cp).convert("RGB").resize((tw, th), Image.LANCZOS) if os.path.isfile(cp) else Image.new("RGB", (tw, th), (230, 230, 230))
        od = (b.get("outline_dist") or {})
        secs = an.get("sections", {})
        nplunge = sum(1 for v in secs.values() if v.get("plunging"))
        nvert = sum(1 for v in secs.values() if (v.get("events") or {}).get("face_past_vertical"))
        sw = a.get("side_swell_m") or {}
        txt = "%s  t=%.2f s  ψ=%s° 倍率 %s  IoU %.3f  輪郭の距離 平均 %.0f px  Hc %.1f m  山 %s 個  手前 46 m の頂 %s m  垂直を過ぎた切り口 %d/%d・巻いた %d" % (
            rid, b.get("t", float("nan")), b.get("psi_deg"), b.get("scale"), b.get("iou", float("nan")), od.get("mean_px", float("nan")),
            a.get("Hc_m", float("nan")), a.get("n_peaks_prom08"),
            "%.1f" % sw["near_dz-46"] if sw.get("near_dz-46") is not None else "—", nvert, len(secs), nplunge)
        rows.append((txt, sh, im3, im2))
    W = tw * 3; H = len(rows) * (th + 30) + 40
    S = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((8, 8), "P2 粗い 3D の岩棚の探索：左＝原画カメラのシルエット（橙）と原画の大波の輪郭（青）、中＝原画カメラの粘土、右＝左前の斜めの粘土。どれも物理だけ（誘導なし）",
           fill=(0, 0, 0), font=font(18))
    y = 40
    for txt, a, b2, c in rows:
        d.text((8, y + 4), txt, fill=(0, 0, 0), font=font(16))
        S.paste(a, (0, y + 28)); S.paste(b2, (tw, y + 28)); S.paste(c, (2 * tw, y + 28))
        y += th + 30
    S.save(out)
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
