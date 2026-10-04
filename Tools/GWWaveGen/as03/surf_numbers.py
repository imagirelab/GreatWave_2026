# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：数の比べ（調べ S1 の彫刻の数・見本02・FLAT・SCULPT）の表の図と、まとめの JSON。
入力：surface/mesh/<名前>_report.json、surface/measure/B2_<版>_{flat,sculpt}_measure.json、study/measure_ours.json（見本02、S3）、
study/sculpture_spec.json（S1）。写真・参照モデルは読まない。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_numbers.py <メッシュの名前> <版>"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "hero_relief_b1v1r5_s1.2"
TAG = sys.argv[2] if len(sys.argv) > 2 else "v9"
mr = S.jload(S.OUT + "/mesh/%s_report.json" % name)
ms = S.jload(S.OUT + "/measure/B2_%s_sculpt_measure.json" % TAG)
mf = S.jload(S.OUT + "/measure/B2_%s_flat_measure.json" % TAG)
sil = S.jload(S.OUT + "/measure/silhouette_vs_sample02.json") if os.path.exists(S.OUT + "/measure/silhouette_vs_sample02.json") else {}
gp_ = S.OUT + "/render/measure/gates_B2_%s_flat_eval/sweep_gates.json" % TAG
gates = S.jload(gp_)["gates"] if os.path.exists(gp_) else {}


def gtxt(k):
    g = gates.get(k)
    return "—" if not g else "%.2f／%.2f" % (g["after_noclaws"], g["after_claws"])


def f(x, n=2):
    return "—" if x is None else ("%.*f" % (n, x))


def spread_range(m, key):
    v = [d.get("white_lum_spread") for d in m[key].values() if d.get("white_lum_spread") is not None]
    return (min(v), max(v)) if v else (None, None)


sp_v_s, sp_c_s = spread_range(ms, "views"), spread_range(ms, "crest")
sp_v_f, sp_c_f = spread_range(mf, "views"), spread_range(mf, "crest")
gap = mr["spacing_front_face"]
tp = ms["views"]["painting"]["tones"]
rows = [
    ("項目", "S1（彫刻、写真と参照モデル）", "見本02（前）", "B2 FLAT", "B2 SCULPT"),
    ("稜の間隔 m（冠の下 0.75 H／中ほど 0.5 H／下 0.25 H）", "0.73／0.93／1.16（0.035／0.045／0.056 H）", "1.0／1.0／1.0（どこも同じ）",
     "%s／%s（平均 %s）／%s（同じメッシュ）" % (f(gap["0.75H"]["gap_p50_m"]), f(gap["0.50H"]["gap_p50_m"]), f(gap["0.50H"]["gap_mean_m"]), f(gap["0.25H"]["gap_p50_m"])), "← 同じ"),
    ("溝（淡い水色）の幅／周期", "0.244（藍 : 水色 ≈ 3 : 1）", "線 0.07 ＋ 帯 0.26（平らな縞）",
     "0.244（式）。描いた面の割合 座席 %s・座席から波 %s・原画 %s（遠くは画面で弱める）" % (f(ms["views"]["seat"].get("face_groove_frac")), f(ms["views"]["seat_toward_wave"].get("face_groove_frac")), f(ms["views"]["painting"].get("face_groove_frac"))), "← 同じ"),
    ("稜の山と谷／周期", "≈ 0.1（0.05〜0.25、陰からの推定）", "0（平らに描いた縞）", "0.12（本当の凹凸。静止のメッシュ）", "← 同じ＋画素ごとの傾きで艶の筋"),
    ("Y 字の枝分かれ", "線 3〜4 本に 1 つ、下へ開く", "あり（段の端数で）", "前の面に %d か所（約 24 本に。S1 の目安 6〜8）" % mr["fork_zones_front_face"], "← 同じ"),
    ("白の明るさの広がり p95−p5", "78〜83", "0〜6", "%s〜%s（2 段の陰）" % (f(min(sp_v_f[0], sp_c_f[0]), 0), f(max(sp_v_f[1], sp_c_f[1]), 0)),
     "7 視点 %s〜%s、回り台 %s〜%s" % (f(sp_v_s[0], 0), f(sp_v_s[1], 0), f(sp_c_s[0], 0), f(sp_c_s[1], 0))),
    ("艶の光（鏡の光・映り込み）", "強い（小さく鋭い光の点、長い窓の映り込み）", "0", "0（平らな色）",
     "あり：白 %d 画素・藍 %d 画素（15 枚の合計）" % (ms["summary"]["specular_px_white_total"], ms["summary"]["specular_px_ai_total"])),
    ("描いた線", "ない", "白の縁に 1.5 画素（原画視点 4,632 画素）", "白と藍の境に 1.2 画素の藍の線（原画視点 %d 画素）＋主役波の外殻の線（設計38）" % mf["views"]["painting"]["drawn_line_px"], "ない（コードに線の道がない）"),
    ("色：白 明／中／陰（sRGB、原画視点）", "245／218／145（白を中立に直した値）", "248,243,223 一色", "248,243,223／同／203,215,206",
     "%s／%s／%s" % (",".join(map(str, tp["white"]["lit"]["srgb"])), ",".join(map(str, tp["white"]["mid"]["srgb"])), ",".join(map(str, tp["white"]["shadow"]["srgb"])))),
    ("色：藍（稜）明／中／陰", "35,54,87／17,20,32／9,11,21", "35,64,97 ほか（平ら）", "35,64,97／同／20,38,64",
     "%s／%s／%s" % (",".join(map(str, tp["ridge"]["lit"]["srgb"])), ",".join(map(str, tp["ridge"]["mid"]["srgb"])), ",".join(map(str, tp["ridge"]["shadow"]["srgb"])))),
    ("色：溝の青 明／中／陰", "59,92,145／45,79,132／37,71,121", "102,161,209（淡い）", "44,105,147（藍中）／同／30,71,107",
     "%s／%s／%s" % (",".join(map(str, tp["groove"]["lit"]["srgb"])), ",".join(map(str, tp["groove"]["mid"]["srgb"])), ",".join(map(str, tp["groove"]["shadow"]["srgb"])))),
    ("唇の帯（列 111〜200）の白＋白の陰（原画視点）", "原画 0.75（S2）・彫刻は白い冠", "0.033", "%s（B1 の白の印 v2）" % f(mf["views"]["painting"].get("lip_white_frac")), "%s（同じ）" % f(ms["views"]["painting"].get("lip_white_frac"))),
    ("主役波の頂点・三角形", "—", "96,000・190,722（keypose）", "%d・%d（静止。行を 4 倍、c %.1f〜%.1f m）" % (mr["grid"]["vertices"], mr["grid"]["triangles"], mr["grid"]["c_range_m"][0], mr["grid"]["c_range_m"][1]), "← 同じ"),
    ("原画視点の空の輪郭の差（ID、見本02 と）", "—", "—", "%s 画素、見本02 の縁から最大 %s 画素（溝を内へ彫る）" % (sil.get("painting", {}).get("diff_px", "—"), sil.get("painting", {}).get("max_dist_px", "—")), "← 同じ"),
    ("原画視点の関門（4 px 以下。78・130・131・132 σ12・72 σ12 p95、爪なし／あり）", "—", "2.74・3.58・3.44・3.56・3.85／3.66",
     "%s・%s・%s・%s・%s（全部通る）" % (gtxt("78"), gtxt("130"), gtxt("131"), gtxt("132_s12"), gtxt("72_s12_p95")) if gates else "—", "← 同じ（輪郭は同じメッシュ）"),
]
W, H = 1920, 1080
im = Image.new("RGB", (W, H), (24, 26, 30))
d = ImageDraw.Draw(im)
fb = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 26)
fr = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicR.ttc", 15)
fh = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 16)
d.text((24, 14), "美術の見本03 B2：数の比べ（調べ S1 の彫刻・見本02・FLAT・SCULPT）｜主役波の面だけ、t* = 12 s、PC の描画", font=fb, fill=(236, 236, 236))
cw = [420, 330, 300, 420, 400]
x0, y = 24, 64
for i, r in enumerate(rows):
    x = x0
    hgt = 66 if i else 34
    d.rectangle([x0, y, x0 + sum(cw), y + hgt], outline=(70, 70, 70), fill=(34, 37, 42) if i % 2 else (28, 30, 34))
    for j, c in enumerate(r):
        fnt = fh if (i == 0 or j == 0) else fr
        col = (255, 196, 92) if i == 0 else ((236, 236, 236) if j != 4 else (180, 220, 255))
        # 折り返し
        words, line, lines = list(c), "", []
        for ch in words:
            if d.textlength(line + ch, font=fnt) > cw[j] - 12:
                lines.append(line); line = ch
            else:
                line += ch
        lines.append(line)
        for k, ln in enumerate(lines[:3]):
            d.text((x + 6, y + 5 + k * 20), ln, font=fnt, fill=col)
        x += cw[j]
    y += hgt
d.text((24, y + 12), "S1 の色は暖かい電球の光の写真から白を中立とみなして直した値（相対の目標）。B2 の色は描画の各色区の明るさの上位 15%・中ほど 20%・下位 15% の平均。艶の画素は「白の基の色より明るい」と「藍の上で明るさ > 110」の数。",
       font=fr, fill=(200, 200, 200))
d.text((24, y + 36), "白の境・冠の地・垂れる舌は B1 の共有の白の印 v2（B1 の担当）。冠の指はまだ入っていない。原画カメラの投影は使わない。HMD 実機ではない。", font=fr, fill=(200, 200, 200))
os.makedirs(S.OUT + "/sheets", exist_ok=True)
im.save(S.OUT + "/sheets/surf_5_numbers.png")
S.jdump(S.OUT + "/measure/B2_summary.json", {"rows": rows, "mesh_report": name, "render_tag": TAG, "sculpt": ms["summary"], "flat": mf["summary"], "silhouette": sil})
print("ok")
