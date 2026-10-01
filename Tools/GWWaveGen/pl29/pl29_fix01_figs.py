# -*- coding: utf-8 -*-
"""仕上げ29 修正の回の図（1920×1080）。前（投影の焼き込み p28）・作る部（p29d）・修正の回（p29g）を、同じ視点・同じ時刻で並べる。

  fig_pl29c_painting_compare.png：原画視点 t* の比べ（原画の色区の地図｜投影｜作る部｜修正の回）と、白・淡い水色と藍の一致の地図（作る部・修正の回）と数。
  fig_pl29c_claws.png  ：立体の爪の切り抜き（原画視点・座席・真上・回り台 0°・30°・330°、t*、作品のまま）。上：作る部、下：修正の回。爪の分かれる割合（pl29_claw_sep.py）。
  fig_pl29c_lip.png    ：唇の先の拡大（原画視点・爪なし、t 12 s と 10.5 s）。投影｜作る部｜修正の回。切れ切れの暗い線の数（pl29_lip_dashes.py）。
  fig_pl29c_stretch.png：座席から波の方向 t*（爪なし）の溝の比べ（作る部｜修正の回）と、面の座標の伸び縮みの数（pl29_stretch.py）。
数は各 JSON から読むだけ（ここでは測らない）。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_fix01_figs.py --p28 <before/p28> --p29d <after/p29d> --p29g <fix01/p29g> --clawsep <dir> --lip <json> --stretch <json>
        --measure <p29g/measure/metrics_build.json> --build-metrics Docs/Evidence/Polish/29/metrics_build.json --out <dir>
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
FR = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
LABELS = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels.png")


def f(sz, b=False):
    return ImageFont.truetype(FB if b else FR, sz)


def lab(d, x, y, t, sz=14):
    w = d.textlength(t, font=f(sz, True)) + 10
    d.rectangle([x, y, x + w, y + sz + 8], fill=(20, 20, 20))
    d.text((x + 5, y + 2), t, fill=(255, 255, 255), font=f(sz, True))


def header(im, title, sub):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 62], fill=(28, 36, 52))
    d.text((14, 4), title, fill=(255, 255, 255), font=f(23, True))
    d.text((14, 38), sub, fill=(205, 212, 225), font=f(14))
    return d


def ids(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    c = np.zeros(r.shape, int)
    c[(r > 200) & (g < 50) & (b < 50)] = 1
    c[(r < 50) & (g > 200) & (b < 50)] = 2
    c[(r < 50) & (g < 50) & (b > 200)] = 3
    c[(r > 200) & (g > 200) & (b < 50)] = 4
    return c


def painting(a, out):
    L = np.array(Image.open(LABELS).convert("L"))
    pal = {0: (249, 232, 196), 1: (248, 243, 223), 2: (198, 215, 203), 3: (44, 105, 147), 4: (35, 64, 97), 5: (71, 80, 95), 9: (249, 232, 196)}
    C = np.zeros(L.shape + (3,), np.uint8)
    for k, v in pal.items():
        C[L == k] = v
    box = (130, 60, 1170, 860)
    tiles = [("原画の色区（美術優先28 の地図）", Image.fromarray(C)),
             ("前｜投影の焼き込み", Image.open(os.path.join(a.p28, "views", "painting_t120_asis.png"))),
             ("作る部 p29d", Image.open(os.path.join(a.p29d, "views", "painting_t120_asis.png"))),
             ("修正の回 p29g", Image.open(os.path.join(a.p29g, "views", "painting_t120_asis.png")))]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "仕上げ29 修正の回（Q28）｜原画視点 t*：原画の色区｜投影｜作る部｜修正の回（作品のまま、爪・飛沫・線あり）",
               "修正の回は面の座標（t* の弧長）・高さ・面の向き・T_white だけで色を決める（房・泡の粒・縁の泡の点・爪の陰の段と縁の線）。原画カメラからの投影は使わない。Unity の PC 描画（HMD ではない）。")
    tw = 474
    th = int(tw * (box[3] - box[1]) / (box[2] - box[0]))
    for k, (t, img) in enumerate(tiles):
        x, y = 4 + k * (tw + 5), 66
        im.paste(img.convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (x, y))
        lab(d, x, y, t)
    y2 = 66 + th + 8
    res = {}
    for k, (nm, root) in enumerate([("作る部 p29d", a.p29d), ("修正の回 p29g", a.p29g)]):
        Cc = ids(os.path.join(root, "diag", "painting_t120_id_claws1.png"))
        m = (L >= 1) & (L <= 4) & (Cc >= 1)
        W1 = np.isin(Cc, [1, 2]); W2 = np.isin(L, [1, 2])
        o = np.full(L.shape + (3,), 238, np.uint8)
        o[m & (W1 == W2)] = (150, 190, 150); o[m & W2 & ~W1] = (210, 70, 60); o[m & ~W2 & W1] = (60, 90, 210)
        o[(L >= 1) & (L <= 4) & ~m] = (200, 200, 200)
        x = 4 + (k + 2) * (tw + 5)
        im.paste(Image.fromarray(o).crop(box).resize((tw, th), Image.NEAREST), (x, y2))
        lab(d, x, y2, nm + "｜白と藍の一致（緑 一致・赤 原画は白・青 原画は藍）", 12)
    bm = json.load(open(a.build_metrics, encoding="utf-8"))["paintingMatch"]["後"]
    fm = json.load(open(a.measure, encoding="utf-8"))["paintingMatch"]["after_claws1"]
    pm = json.load(open(a.build_metrics, encoding="utf-8"))["paintingMatch"]["前"]
    rows = [("", "投影（前）", "作る部", "修正の回", "原画"),
            ("白と藍の一致", "%.3f" % pm["白と藍の一致"], "%.3f" % bm["白と藍の一致"], "%.3f" % fm["白と藍の一致"], "—"),
            ("色区の一致", "%.3f" % pm["色区の一致"], "%.3f" % bm["色区の一致"], "%.3f" % fm["色区の一致"], "—")]
    for n in ["白", "淡い水色", "藍中", "藍濃"]:
        rows.append(("面積 " + n, "%.3f" % pm[n]["render"], "%.3f" % bm[n]["render"], "%.3f" % fm[n]["render"], "%.3f" % fm[n]["painting"]))
    for n in ["白", "淡い水色", "藍中", "藍濃"]:
        rows.append(("IoU " + n, "%.2f" % pm[n]["iou"], "%.2f" % bm[n]["iou"], "%.2f" % fm[n]["iou"], "—"))
    d.text((14, y2 + 2), "原画視点 t* の色区（爪あり、ID の画像で数える）", fill=(20, 20, 20), font=f(16, True))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            d.text((14 + [0, 150, 270, 370, 480][j], y2 + 30 + i * 24), v, fill=(20, 20, 20), font=f(14, i == 0 or j == 0))
    d.text((14, y2 + 30 + len(rows) * 24 + 8), "色区の項目 73〜270 は投影をやめたので動く（新しい読みとして記録。投影に戻して追わない）。", fill=(60, 60, 60), font=f(13))
    d.text((14, y2 + 30 + len(rows) * 24 + 30), "輪郭の関門 78・130・131・132・72 は作る部・P28R2rec と同じ値（形は変えていない）。", fill=(60, 60, 60), font=f(13))
    im.save(out)
    return {"build": bm, "fix": fm, "projection": pm}


def hero_mask(p):
    al = np.array(Image.open(p).convert("RGBA"))[..., 3].astype(int)
    return np.abs(al - 128) <= 2


def densest(diag0, diag1, w=620, h=380):
    """爪が主役波を隠す画素（pl29_claw_sep.py と同じ取り方）がいちばん多い w×h の窓。"""
    m = hero_mask(diag0) & ~hero_mask(diag1)
    ii = np.cumsum(np.cumsum(m.astype(np.int64), 0), 1)
    H, W = m.shape
    best = (-1, 0, 0)
    for y0 in range(0, H - h + 1, 20):
        for x0 in range(0, W - w + 1, 20):
            y1, x1 = y0 + h - 1, x0 + w - 1
            s = ii[y1, x1] - (ii[y0 - 1, x1] if y0 else 0) - (ii[y1, x0 - 1] if x0 else 0) + (ii[y0 - 1, x0 - 1] if x0 and y0 else 0)
            if s > best[0]:
                best = (int(s), x0, y0)
    return (best[1], best[2], best[1] + w, best[2] + h)


def claw_crops(a, out):
    cs_d = json.load(open(os.path.join(a.clawsep, "claw_sep_p29d.json"), encoding="utf-8"))
    cs_g = json.load(open(os.path.join(a.clawsep, "claw_sep_p29g.json"), encoding="utf-8"))
    dg = os.path.join(a.p29g, "diag")
    items = [("painting", "views/painting_t120_asis.png", densest(dg + "/painting_t120_hero_claws0.png", dg + "/painting_t120_hero_claws1.png"), "原画視点"),
             ("seat", "views/seat_t120_asis.png", densest(dg + "/seat_t120_hero_claws0.png", dg + "/seat_t120_hero_claws1.png"), "座席"),
             ("top", "views/top_t120_asis.png", densest(dg + "/top_t120_hero_claws0.png", dg + "/top_t120_hero_claws1.png"), "真上"),
             ("tt0", "tt/t120_az000_claws.png", densest(dg + "/tt_t120_az000_hero_claws0.png", dg + "/tt_t120_az000_hero_claws1.png"), "回り台 0°"),
             ("tt30", "tt/t120_az030_claws.png", densest(dg + "/tt_t120_az030_hero_claws0.png", dg + "/tt_t120_az030_hero_claws1.png"), "回り台 30°"),
             ("tt330", "tt/t120_az330_claws.png", densest(dg + "/tt_t120_az330_hero_claws0.png", dg + "/tt_t120_az330_hero_claws1.png"), "回り台 330°")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "仕上げ29 修正の回（Q28）｜立体の爪（t*、作品のまま）｜上：作る部 p29d（設計34 の白・淡い水色、原画視点では縁の線なし）　下：修正の回 p29g",
               "修正の回：爪の帯の輪の向き（sin φ）で白（上面）・淡い水色（側面）・藍中（下面）の段（PL29 Claw Shade）と、設計38 の縁の線をどの視点でも描く。爪の形・数・位置（設計33）は変えていない（仕上げ32・33）。")
    tw, th = 316, 194
    for k, (key, rel, box, name) in enumerate(items):
        x = 4 + k * (tw + 4)
        for si, (root, nm) in enumerate([(a.p29d, "作る部"), (a.p29g, "修正の回")]):
            y = 70 + si * (th + 30)
            p = os.path.join(root, rel)
            if os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (x, y))
            lab(d, x, y, nm + "｜" + name, 12)
    # 数の表
    y0 = 70 + 2 * (th + 30) + 10
    d.text((14, y0), "爪の分かれる割合（作品のままの色の画像で、爪の片の縁の 2 画素以内に暗い画素（縁の線・藍）がある縁の割合が 0.6 以上の片の割合。pl29_claw_sep.py。4 時刻の合計）",
           fill=(20, 20, 20), font=f(15, True))
    names = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"), ("side_right", "右の側面"),
             ("back65", "後ろ 65°"), ("top", "真上"), ("turntable", "回り台（12 方位 × 4 時刻）")]
    d.text((14, y0 + 30), "視点", font=f(14, True), fill=(20, 20, 20))
    d.text((300, y0 + 30), "作る部：読める片／片（割合）", font=f(14, True), fill=(20, 20, 20))
    d.text((700, y0 + 30), "修正の回：読める片／片（割合）", font=f(14, True), fill=(20, 20, 20))
    d.text((1120, y0 + 30), "爪の画素（主役波を隠す、4 時刻の合計）", font=f(14, True), fill=(20, 20, 20))
    for i, (k, nm) in enumerate(names):
        bd, bg = cs_d["byView"][k], cs_g["byView"][k]
        yy = y0 + 56 + i * 24
        d.text((14, yy), nm, font=f(14), fill=(20, 20, 20))
        d.text((300, yy), "%d／%d（%s）" % (bd["readable"], bd["pieces"], "—" if bd["readableFrac"] is None else "%.2f" % bd["readableFrac"]), font=f(14), fill=(20, 20, 20))
        d.text((700, yy), "%d／%d（%s）" % (bg["readable"], bg["pieces"], "—" if bg["readableFrac"] is None else "%.2f" % bg["readableFrac"]), font=f(14), fill=(20, 20, 20))
        d.text((1120, yy), "%d" % bg["clawPx"], font=f(14), fill=(20, 20, 20))
    d.text((14, y0 + 56 + len(names) * 24 + 6), "側面・後ろ・真上では爪がほとんど見えない（片 0〜4、画素 0〜1,714）。爪の大きさ・数・K*′ への結び付け直しは仕上げ32・33 の造形の仕事（限界として記録）。",
           font=f(14, True), fill=(150, 30, 30))
    im.save(out)
    return {"build": cs_d["byView"], "fix": cs_g["byView"]}


def lip(a, out):
    L = json.load(open(a.lip, encoding="utf-8"))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "仕上げ29 修正の回（Q28）｜唇の先の梯子（原画視点・爪なし）｜左から 投影｜作る部 p29d｜修正の回 p29g",
               "修正の回：唇の先のまわりの前の白の終わりを管の天井へ（c −5〜5 で F 2.5〜2.55）、房の切れ込みは画面で 1〜2.5 画素を切ると消し、縁の線は面が視線にほぼ平行な所で薄める。")
    boxes = {"t120": (880, 300, 1140, 500), "t105": (600, 300, 860, 480)}
    tw, th = 630, 470
    for r, ts in enumerate(["t120", "t105"]):
        for k, (nm, root) in enumerate([("p28", a.p28), ("p29d", a.p29d), ("p29g", a.p29g)]):
            p = os.path.join(root, "views", "painting_%s_clawfree.png" % ts)
            x, y = 4 + k * (tw + 4), 66 + r * (th + 4)
            if os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").crop(boxes[ts]).resize((tw, th), Image.NEAREST), (x, y))
            v = L["renders"][nm].get(ts, {})
            lab(d, x, y, "%s｜t %s s｜切れ切れの暗い線 %d 片・%d 画素" % ({"p28": "投影", "p29d": "作る部", "p29g": "修正の回"}[nm], "12" if ts == "t120" else "10.5",
                                                             v.get("smallDarkPieces", -1), v.get("smallDarkPx", -1)), 13)
    im.save(out)
    return L["renders"]


def stretch(a, out):
    S = json.load(open(a.stretch, encoding="utf-8"))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "仕上げ29 修正の回（Q28）｜面の座標の伸び縮み：座席から波の方向 t*（爪なし）｜左：作る部 p29d　右：修正の回 p29g",
               "作る部は溝・点・舌を UV2 の s（前の K* の σ）と行の c の上に置いた。修正の回は t* の面の弧長（行ごとの sa・列ごとの ca）と、行の間隔の倍率 kc で本数を 2 倍ずつ変える溝。")
    for k, root in enumerate([a.p29d, a.p29g]):
        p = os.path.join(root, "views", "seat_toward_wave_t120_clawfree.png")
        if os.path.exists(p):
            im.paste(Image.open(p).convert("RGB").resize((954, 536), Image.LANCZOS), (4 + k * 958, 66))
        lab(d, 4 + k * 958, 66, ["作る部 p29d", "修正の回 p29g"][k])
    b, o, oc, af = S["before_uv2"], S["after_grooves_octave"], S["after_grooves_octave_c5_15"], S["area_factor_p5_p50_p95"]
    rows = ["溝の 3 次元の間隔の倍率（λ = 0.95 m の何倍か。三角形の面積の重み。列 j_B〜j_E）",
            "　作る部（UV2 の行の c）：p5 %.2f・p50 %.2f・p95 %.2f。2 倍を超える面積 %.1f%%。c 5〜15 m（右の管）の p50 %.2f、2 倍を超える %.1f%%" % (
                b["groove_spacing_factor_p5_p50_p95"][0], b["groove_spacing_factor_p5_p50_p95"][1], b["groove_spacing_factor_p5_p50_p95"][2],
                100 * b["groove_spacing_area_frac_gt2"], b["c5_15_groove_spacing_factor_p50"], 100 * b["c5_15_area_frac_gt2"]),
            "　　（作る部の評審の読み：p50 1.21・p95 2.73、c 5〜15 m の中央値 2.39、2 倍を超える 68%、異方性 p95 6.7。数える範囲と重みが違う）",
            "　修正の回（行の c の上、kc で本数を 2 倍ずつ）：基の間隔 p5 %.2f・p50 %.2f・p95 %.2f、間の溝を足した実効 p5 %.2f・p50 %.2f・p95 %.2f（c 5〜15 m の実効 p50 %.2f）" % (
                tuple(o["groove_base_spacing_factor_p5_p50_p95"]) + tuple(o["groove_effective_spacing_factor_p5_p50_p95"]) + (oc["groove_effective_spacing_factor_p5_p50_p95"][1],)),
            "点・房・泡の粒の座標の面積の倍率（3 次元の面積／座標の面積）：作る部 (s, c) p5 %.2f・p50 %.2f・p95 %.2f → 修正の回 (sa, ca) p5 %.2f・p50 %.2f・p95 %.2f" % (
                tuple(af["before_uv2_s_c"]) + tuple(af["after_sa_ca"])),
            "残る所：(sa, ca) は列ごとに積むので、管の中（F ≈ 2.5）で座標が斜めにずれ（溝を ca に置くと向きのずれ p95 49°）、点・粒は楕円に伸びる（異方性 p95 %.1f）。溝は ca を使わない。" % S["after_arc"]["anisotropy_p50_p95"][1]]
    for i, t in enumerate(rows):
        d.text((14, 620 + i * 34), t, fill=(150, 30, 30) if t.startswith("残る") else (20, 20, 20), font=f(15, i == 0))
    im.save(out)
    return {"before": b, "after_grooves": o, "after_grooves_c5_15": oc, "area": af}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p28", required=True)
    ap.add_argument("--p29d", required=True)
    ap.add_argument("--p29g", required=True)
    ap.add_argument("--clawsep", required=True)
    ap.add_argument("--lip", required=True)
    ap.add_argument("--stretch", required=True)
    ap.add_argument("--measure", required=True)
    ap.add_argument("--build-metrics", dest="build_metrics", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    r = {"painting": painting(a, os.path.join(a.out, "fig_pl29c_painting_compare.png")),
         "claws": claw_crops(a, os.path.join(a.out, "fig_pl29c_claws.png")),
         "lip": lip(a, os.path.join(a.out, "fig_pl29c_lip.png")),
         "stretch": stretch(a, os.path.join(a.out, "fig_pl29c_stretch.png"))}
    with open(os.path.join(a.out, "fix01_fig_numbers.json"), "w", encoding="utf-8") as fo:
        json.dump(r, fo, ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
