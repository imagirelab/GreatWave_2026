# -*- coding: utf-8 -*-
"""P2g：P2 の後処理（p2_post.py → p2_figs）が誘導ありの計算の図にも書く「物理だけ（誘導なし）」の札を、正しい札に書き直す（py -3.10）。
使い方: py -3.10 p2g_relabel.py <run_dir> <札>
sheet.png（下の行）と strip.png（上の行）の札の行を白で消して書き直す。p2_figs.py は P2 の道具なので変えない。
"""
import sys, os, json
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2_figs import font  # noqa: E402

rd, label = sys.argv[1], sys.argv[2]
an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
b = an["best"]; od = b.get("outline_dist") or {}
p = os.path.join(rd, "sheet.png")
if os.path.isfile(p):
    im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
    d.rectangle([0, 580, 975, 604], fill=(255, 255, 255))
    d.text((8, 584), "IoU %.3f（窓の中）・輪郭の距離 平均 %.0f px・中央 %.0f px（1920 表示）。記録だけ。%s" % (
        b["iou"], od.get("mean_px", float("nan")), od.get("median_px", float("nan")), label), fill=(0, 0, 0), font=font(14))
    im.save(p); print("relabelled", p)
p = os.path.join(rd, "strip.png")
if os.path.isfile(p):
    im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 29], fill=(255, 255, 255))
    d.text((8, 6), "%s：いちばん原画に近い瞬間（t=%.2f s）の前後。上＝左前の斜め、下＝原画カメラ（ψ=%d°・倍率 %.1f）。%s" % (
        an["run_id"], b["t"], b["psi_deg"], b["scale"], label), fill=(0, 0, 0), font=font(15))
    im.save(p); print("relabelled", p)
