# -*- coding: utf-8 -*-
"""FLIP39 E：座席の目から見た 4 つの瞬間を計算ごとに並べた図（sheet_seat_moments.png）。py -3.10 e_seat_sheet.py <run_id>=<label> ...
瞬間：(1) 乗る目の終わりの 6 秒前、(2) 仰角が初めて 10° を越えた時、(3) 仰角が初めて 30° を越えた時、(4) 乗る目の終わりの 0.4 秒前（唇が頭上・前の面が目の前）。
図は短い動画のために描いた座席の目の粘土の図（render/clip_seat、3 コマおき）から、時刻のいちばん近いものを使う。"""
import sys, os, json, glob
import numpy as np
from PIL import Image
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_plot import Sheet

E = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
pairs = [a.split("=", 1) for a in sys.argv[1:]]
W, H = 400, 225
sh = Sheet(4 * W + 20, 60 + len(pairs) * (H + 50), "座席の目（船は水面に上下だけ乗る、目は水面＋1.83 m、沖を向いて 15° 見上げ、縦の画角 90°）から見た 4 つの瞬間")
for i, (rid, label) in enumerate(pairs):
    rd = os.path.join(E, rid)
    se = json.load(open(os.path.join(rd, "seat_e.json"), encoding="utf8"))
    rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8")); toff = float(rj["parms"].get("t_off", 0.0))
    b = se["best_seat"]; r = b["ride"]; s = r["series"]
    tt = np.array(s["t_group"]); al = np.array(s["alpha"])
    tend = r["end_t_group"] if r.get("end_t_group") else float(tt[-1])
    def first(th):
        k = np.where(al >= th)[0]
        return float(tt[k[0]]) if k.size else None
    moments = [("終わりの 6 秒前", tend - 6.0), ("仰角 10° を越えた", first(10)), ("仰角 30° を越えた", first(30)), ("終わりの 0.4 秒前", tend - 0.4)]
    fs = {int(os.path.basename(f)[1:5]): f for f in glob.glob(os.path.join(rd, "render", "clip_seat", "f*.png"))}
    frs = np.array(sorted(fs))
    y0 = 60 + i * (H + 50)
    sh.text((6, y0), "%s　座席 x %.0f m　終わり %.2f s（%s）　仰角の最大 %.0f°　唇が頭上 %s" % (
        label, b["x_seat"], tend, r.get("end_why"), r["alpha_max"], "はい" if r.get("lip_overhead") else "いいえ"), 14, bold=True)
    for j, (nm, tg) in enumerate(moments):
        if tg is None or not len(frs):
            continue
        f = int(frs[np.argmin(np.abs((frs - 1) / 24.0 + toff - tg))])
        im = Image.open(fs[f]).resize((W, H))
        sh.im.paste(im, (j * W + 5, y0 + 22))
        a_ = float(np.interp(tg, tt, al))
        sh.text((j * W + 10, y0 + 24), "%s  %.2f s  仰角 %.0f°" % (nm, (f - 1) / 24.0 + toff, a_), 13, col=(120, 30, 0))
out = os.path.join(E, "sheet_seat_moments.png")
sh.save(out); print(out)
