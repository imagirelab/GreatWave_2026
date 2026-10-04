# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：比べの図（前 = 見本03 の形 AS02C、今 = 新しい形 AS04）。py -3.10 -B shape_sheets.py
  1. shape_1_painting.png：原画視点（原画｜AS02C｜AS04、どちらも材質 AS04 Flat Smooth の Unity の描画）と、粘土の原画視点（利用者の区域の線つき）
  2. shape_2_clay_views.png：粘土（Blender の Workbench）：原画視点・座席・左右の側面（v3・v4）・後ろ 65°・真上・利用者の失敗の視点（前｜今）
  3. shape_3_turntable.png：粘土の回り台 12 方位（Blender、前｜今）と、材質つきの回り台（Unity、前｜今）
  4. shape_4_layers.png：三つの層（numpy の粘土、① 赤・② 緑・③ 青で薄く色づけ）と、数の図（頂の高さ H(c)、帯の幅、唇の前の縁）
  5. shape_5_material_views.png：材質つきの 7 視点（Unity、前｜今）
原画の画像は比べの図にだけ使う（面へは写さない）。
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402

SH = S.OUT
MAT = S.REPO + "/Unity/Build/Polish/sample04/mat"
FONT = "C:/Windows/Fonts/msgothic.ttc"
F = {k: ImageFont.truetype(FONT, k) for k in (18, 22, 24, 26, 30, 36)}
BG = (250, 248, 242)
INK = (25, 25, 30)
BEFORE = SH + "/render/before_AS02C"
AFTER = SH + "/render/A4"


def im(p, w=None, h=None, box=None):
    a = Image.open(p).convert("RGB")
    if box:
        a = a.crop(box)
    if w and h:
        a = a.resize((w, h), Image.LANCZOS)
    elif w:
        a = a.resize((w, int(a.height * w / a.width)), Image.LANCZOS)
    return a


def label(img, xy, text, f=22, fill=INK, bg=(255, 255, 255)):
    d = ImageDraw.Draw(img)
    x, y = xy
    tb = d.textbbox((x, y), text, font=F[f])
    d.rectangle([tb[0] - 4, tb[1] - 3, tb[2] + 4, tb[3] + 3], fill=bg)
    d.text((x, y), text, font=F[f], fill=fill)


def header(W, title, sub, h=110):
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((20, 14), title, font=F[36], fill=INK)
    y = 62
    for line in sub:
        d.text((22, y), line, font=F[18], fill=(70, 70, 70)); y += 24
    return img


def stack(parts, W):
    H = sum(p.height for p in parts)
    out = Image.new("RGB", (W, H), BG)
    y = 0
    for p in parts:
        out.paste(p, (0, y)); y += p.height
    return out


def sheet1(ev):
    W = 2400
    box = (150, 0, 1250, 800)
    w = 780; h = int(800 * w / 1100)
    # 原画を表示の画素の箱へ合わせて切る（表示 x = A_DISP·(x+0.5) − 0.5 + OFFX）
    p = Image.open(S.REPO + "/Docs/References/Met_JP1847_DP130155.jpg").convert("RGB")
    r0 = S.disp_to_ref(np.array([[box[0], box[1]], [box[2], box[3]]], float))
    pc = p.crop(tuple(int(round(v)) for v in (r0[0, 0], r0[0, 1], r0[1, 0], r0[1, 1]))).resize((w, h), Image.LANCZOS)
    a = im(BEFORE + "/views/painting_t120_claws.png", w, h, box)
    b = im(AFTER + "/views/painting_t120_claws.png", w, h, box)
    row1 = Image.new("RGB", (W, h + 40), BG)
    for k, (t, x) in enumerate(((pc, "原画（DP130155、比べの図だけに使う）"), (a, "見本03 の形 AS02C（材質は調べ M の AS04 Flat Smooth）"), (b, "新しい形 AS04（同じ材質・同じ視点）"))):
        row1.paste(t, (20 + k * (w + 10), 36)); ImageDraw.Draw(row1).text((24 + k * (w + 10), 6), x, font=F[22], fill=INK)
    # 粘土（numpy、層の色）＋区域の線
    def clay_poly(lab):
        c = Image.open(SH + "/clay/np_layers/%s__painting.png" % lab).convert("RGB")
        d = ImageDraw.Draw(c)
        polys = [(S.ref_to_disp(np.array(S.REG1, float)), (220, 40, 40)), (S.ref_to_disp(np.array(S.REG2, float)), (30, 150, 30)),
                 (S.ref_to_disp(np.array(S.REG3, float)), (20, 140, 190)), (S.ref_to_disp(np.array(S.REG4, float)), (230, 170, 0)),
                 (np.array(S.BULGE_DISP, float), (255, 120, 0))]
        sc = c.width / 1920.0
        for P, col in polys:
            pts = [tuple(v) for v in (P * sc)]
            d.line(pts + [pts[0]], fill=col, width=3)
        return c.crop(tuple(int(v * sc) for v in box)).resize((w, h), Image.LANCZOS)
    row2 = Image.new("RGB", (W, h + 40), BG)
    ImageDraw.Draw(row2).text((24, 6), "粘土の下見（numpy）：① 赤・② 緑・③ 青で層を薄く色づけ。線 = 区域（赤 ①・緑 ②・青 ③・黄 ④・橙 = 利用者の黄色の線の出っ張りの所）", font=F[22], fill=INK)
    row2.paste(clay_poly("AS02C"), (20 + (w + 10), 36)); row2.paste(clay_poly("AS04"), (20 + 2 * (w + 10), 36))
    s8 = ev["S8_bulge"]; g = ev["G2_outline_split"]["AS04"]
    t = [
        "S8 出っ張り（利用者の黄色の線の中の原画の射線 %d 本の、最初に当たる面の、内の面からの距離）：" % s8["AS04"]["rays"],
        "  AS02C：内の面に当たる割合 %.2f、距離 p50 %.2f m・p95 %.2f m（唇の外の面が 1〜3 m 手前に出る）" % (s8["AS02C"]["first_hit_inner_face_share"], s8["AS02C"]["dev_from_inner_face_m"]["p50"], s8["AS02C"]["dev_from_inner_face_m"]["p95"]),
        "  AS04 ：内の面に当たる割合 %.2f、距離 p95 %.2f m（目標 ≤ 0.15 m）。参考：調べ S の円からの距離 p95 %.2f → %.2f m" % (
            s8["AS04"]["first_hit_inner_face_share"], s8["AS04"]["dev_from_inner_face_m"]["p95"], s8["AS02C"]["dev_from_circle_s4_m"]["p95"], s8["AS04"]["dev_from_circle_s4_m"]["p95"]),
        "原画視点の関門（Unity の描画、4 px 以下）：130 %.4f・131 %.4f・132 σ12 %.4f・72 σ12 p95 %.4f（見本03 の形と同じか良い）。" % tuple(GATES[k] for k in ("130", "131", "132_s12", "72_s12_p95")),
        "  78 は主役波だけでは %.2f px：④（x < 360）を主役波が作らないため（S9）。x ≥ 360 は %.2f px（AS02C と同じ）。別の青い波 wave4 と重ねると x < 360 も %.2f px。" % (
            GATES["78"], g["78_x_ge_360（主役波）"]["max"], UNION["outline78_union"]["x_lt_360"]["max"]),
    ]
    foot = Image.new("RGB", (W, 30 + 26 * len(t)), BG)
    d = ImageDraw.Draw(foot)
    for k, line in enumerate(t):
        d.text((24, 10 + 26 * k), line, font=F[22], fill=INK)
    hd = header(W, "美術の見本04 の形 1：原画視点（前 = 見本03 の形 AS02C、今 = AS04）",
                ["唇の左の面の帯（S8）は、唇を短くして（頂の前の短い鼻）内の面の弧が頂のすぐ下まで続く形にした。左の白は楔の下の縁まで下げ、④ の輪郭は別の青い波が作る（S9）。",
                 "粘土の下見は numpy の z バッファ（Unity の描画ではない）。材質つきの描画は Unity 6000.4.3f1 の PC オフスクリーン（HMD ではない）。"])
    return stack([hd, row1, row2, foot], W)


def pair_grid(pairs, cell_w, title, sub, W=2400, labels=("前：見本03 の形 AS02C", "今：AS04")):
    rows = []
    for name, pa, pb in pairs:
        a = im(pa, cell_w); b = im(pb, cell_w)
        h = max(a.height, b.height)
        r = Image.new("RGB", (W, h + 34), BG)
        ImageDraw.Draw(r).text((24, 4), name, font=F[22], fill=INK)
        r.paste(a, (20, 32)); r.paste(b, (40 + cell_w, 32))
        rows.append(r)
    top = Image.new("RGB", (W, 34), BG)
    d = ImageDraw.Draw(top)
    d.text((24, 4), labels[0], font=F[26], fill=INK); d.text((44 + cell_w, 4), labels[1], font=F[26], fill=INK)
    return stack([header(W, title, sub), top] + rows, W)


def sheet2():
    V = SH + "/clay/views"
    names = [("v1_painting", "原画視点"), ("v2_seat", "座席（右の船）"), ("v3_side_along_crest_cam_side", "側面（原画のカメラの側、峰に沿って）"),
             ("v4_true_side_perp_crest_front", "真横（峰に直角、前から）"), ("b65_back65_clay", "後ろ 65°"), ("v6_top_down", "真上"),
             ("v8_user7_az290_el5", "利用者の視点 7（方位 290°・仰角 5°）"), ("v9_user8_az030_el25", "利用者の視点 8（方位 30°・仰角 25°）"), ("b115_back_minus_c", "後ろ（−c 側）")]
    pairs = [(n2, V + "/AS02C__%s.png" % n, V + "/AS04__%s.png" % n) for n, n2 in names]
    return pair_grid(pairs, 1170, "美術の見本04 の形 2：粘土の視点（Blender 5.2 Workbench、前｜今）",
                     ["形だけを見るための粘土（色・模様なし）。視点は設計28 からの粘土の標準の視点（kstar_p28/rays_views.json）。海は格子の縁につないだ輪と 5 m の格子。"])


def sheet2b():
    V = SH + "/clay/np_plain"
    names = [("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left_fit", "左の側面（寄り）"), ("side_right_fit", "右の側面（寄り）"),
             ("back65_fit", "後ろ 65°（寄り）"), ("top_fit", "真上（寄り）")]
    pairs = [(n2, V + "/AS02C__%s.png" % n, V + "/AS04__%s.png" % n) for n, n2 in names]
    return pair_grid(pairs, 1170, "美術の見本04 の形 2b：粘土の視点（numpy、Unity の描画と同じ向きの視点、前｜今）",
                     ["Unity の描画（見本03 の VIEWS）と同じ向き。側面・後ろ・真上は主役波に合わせて寄せた。灰色 = 主役波、青灰 = 主役波の格子の海の帯。"])


def sheet3():
    W = 2400
    cw = 380
    parts = [header(W, "美術の見本04 の形 3：回り台 12 方位（前｜今）",
                    ["上：粘土（Blender、半径 72 m・仰角 16°、方位 0°〜330°）。下：材質 AS04 Flat Smooth の Unity の描画（見本03 の回り台のカメラ、爪あり）。"])]
    for lab, src, pat, title in (("AS02C", SH + "/clay/tt_AS02C", "f_%04d.png", "粘土・前（AS02C）"), ("AS04", SH + "/clay/tt_AS04", "f_%04d.png", "粘土・今（AS04）"),
                                 ("AS02C", BEFORE + "/tt", "t120_az%03d_claws.png", "材質・前（AS02C）"), ("AS04", AFTER + "/tt", "t120_az%03d_claws.png", "材質・今（AS04）")):
        r = Image.new("RGB", (W, 2 * int(cw * 9 / 16) + 40), BG)
        ImageDraw.Draw(r).text((24, 6), title, font=F[24], fill=INK)
        for k in range(12):
            p = src + "/" + (pat % (k if "f_" in pat else 30 * k))
            if not os.path.isfile(p):
                continue
            t = im(p, cw, int(cw * 9 / 16))
            x = 20 + (k % 6) * (cw + 8); y = 36 + (k // 6) * (int(cw * 9 / 16) + 2)
            r.paste(t, (x, y)); label(r, (x + 4, y + 4), "%d°" % (30 * k), 18)
        parts.append(r)
    return stack(parts, W)


def chart(w, h, series, xr, yr, title, xlab, ylab, refs=()):
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    L, R, T, B = 70, 20, 40, 50
    d.text((L, 8), title, font=F[22], fill=INK)

    def P(x, y):
        return (L + (x - xr[0]) / (xr[1] - xr[0]) * (w - L - R), h - B - (y - yr[0]) / (yr[1] - yr[0]) * (h - T - B))
    d.rectangle([L, T, w - R, h - B], outline=(150, 150, 150))
    for gx in np.linspace(xr[0], xr[1], 7):
        x, _ = P(gx, yr[0]); d.line([(x, T), (x, h - B)], fill=(230, 230, 230)); d.text((x - 14, h - B + 4), "%.0f" % gx, font=F[18], fill=(80, 80, 80))
    for gy in np.linspace(yr[0], yr[1], 6):
        _, y = P(xr[0], gy); d.line([(L, y), (w - R, y)], fill=(230, 230, 230)); d.text((6, y - 9), "%.1f" % gy, font=F[18], fill=(80, 80, 80))
    d.text((w // 2 - 60, h - 26), xlab, font=F[18], fill=(60, 60, 60)); d.text((L + 4, T + 2), ylab, font=F[18], fill=(60, 60, 60))
    ly = T + 24
    for name, xs, ys, col, wd in series:
        pts = [P(x, y) for x, y in zip(xs, ys) if np.isfinite(y)]
        if len(pts) > 1:
            d.line(pts, fill=col, width=wd)
        d.line([(w - R - 250, ly + 9), (w - R - 220, ly + 9)], fill=col, width=4); d.text((w - R - 212, ly), name, font=F[18], fill=INK); ly += 24
    for x0, x1, yv, col, txt in refs:
        a_, b_ = P(x0, yv), P(x1, yv); d.line([a_, b_], fill=col, width=2); d.text((a_[0], a_[1] - 22), txt, font=F[18], fill=col)
    return img


def sheet4(ev):
    W = 2400
    V = SH + "/clay/np_layers"
    names = [("top_fit", "真上（寄り）"), ("tt060", "回り台 60°"), ("tt300", "回り台 300°"), ("side_left_fit", "左の側面（寄り）")]
    rows = []
    for n, n2 in names:
        a = im(V + "/AS02C__%s.png" % n, 1170); b = im(V + "/AS04__%s.png" % n, 1170)
        r = Image.new("RGB", (W, a.height + 34), BG)
        ImageDraw.Draw(r).text((24, 4), n2 + "（左 = 前 AS02C、右 = 今 AS04）", font=F[22], fill=INK)
        r.paste(a, (20, 32)); r.paste(b, (40 + 1170, 32)); rows.append(r)
    # 数の図
    cb, Ab, Yb = S.load_rows()
    z = np.load(SH + "/final/cand/kstarAS04_a45_rows.npz"); c, A, Y = z["c"], z["A"], z["Y"]
    Hb = Yb[:, 18:201].max(1); Ha = Y[:, 18:201].max(1)
    ch1 = chart(1170, 420, [("前 AS02C", cb, Hb, (120, 120, 200), 3), ("今 AS04", c, Ha, (220, 90, 40), 3)], (-62, 16), (0, 21),
                "頂の高さ H(c)（行ごとの列 18〜200 の最大）", "c（m、波峰線の向き、− が原画視点の左）", "m")
    fe_b = ev["S11_layers"]["AS02C"]["front_edge_by_row"]; fe_a = ev["S11_layers"]["AS04"]["front_edge_by_row"]
    xb = [r["c"] for r in fe_b if r]; yb = [r["a"] for r in fe_b if r]; xa = [r["c"] for r in fe_a if r]; ya = [r["a"] for r in fe_a if r]
    ch2 = chart(1170, 420, [("前 AS02C", xb, yb, (120, 120, 200), 3), ("今 AS04", xa, ya, (220, 90, 40), 3)], (-30, 16), (-6, 16),
                "唇の前の縁（列 90〜300 で高さ ≥ 0.2 H0 の点の a の最大）", "c（m）", "a（m、+ が前）",
                refs=((-23, -17, 15, (40, 120, 200), "③"), (-15.5, -11.5, 15, (40, 150, 40), "②"), (-2, 8, 15, (210, 60, 60), "①")))
    be = ev["S10_band_extent"]
    keys = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
    refw = {"0.1": 32.5, "0.2": 30.5, "0.3": 30.5, "0.4": 30.0, "0.5": 27.0, "0.6": 23.5, "0.7": 18.0, "0.8": 10.5, "0.9": 5.0}
    bar = Image.new("RGB", (1170, 420), (255, 255, 255)); d = ImageDraw.Draw(bar)
    d.text((70, 8), "高さの帯ごとの c の幅（m）：前・今・参照モデルの数（調べ S-3、下限を含む）", font=F[22], fill=INK)
    for k, key in enumerate(keys):
        x0 = 80 + k * 120
        for j, (v, col) in enumerate(((be["AS02C"][key]["width_m"], (120, 120, 200)), (be["AS04"][key]["width_m"], (220, 90, 40)), (refw[key], (150, 150, 150)))):
            hh = v / 62.0 * 300
            d.rectangle([x0 + j * 32, 370 - hh, x0 + j * 32 + 28, 370], fill=col)
            d.text((x0 + j * 32 - 2, 370 - hh - 20), "%.0f" % v, font=F[18], fill=INK)
        d.text((x0 + 20, 378), key + " H", font=F[18], fill=INK)
    d.text((780, 40), "■ 前 AS02C", font=F[18], fill=(120, 120, 200)); d.text((780, 62), "■ 今 AS04", font=F[18], fill=(220, 90, 40)); d.text((780, 84), "■ 参照（数だけ）", font=F[18], fill=(150, 150, 150))
    L4 = ev["S11_layers"]["AS04"]; st = L4["steps"]
    txt = Image.new("RGB", (1170, 420), (255, 255, 255)); d = ImageDraw.Draw(txt)
    lines = ["三つの層（S11）の数（AS04、行ごとの唇の前の縁から）",
             "① 主の頂と唇（c −2〜+8）：前の縁 a %.1f m・原画のカメラから %.1f m・頂 %.2f H0" % (L4["r1"]["front_a_p50"], L4["r1"]["dist_to_painting_cam_p50_m"], L4["r1"]["crest_H_p50_over_H0"]),
             "② の房（c −15.5〜−11.5）：前の縁 a %.1f m・%.1f m・頂 %.2f H0" % (L4["r2"]["front_a_p50"], L4["r2"]["dist_to_painting_cam_p50_m"], L4["r2"]["crest_H_p50_over_H0"]),
             "③ 最左側の小さな房（c −23〜−17）：前の縁 a %.1f m・%.1f m・頂 %.2f H0" % (L4["r3"]["front_a_p50"], L4["r3"]["dist_to_painting_cam_p50_m"], L4["r3"]["crest_H_p50_over_H0"]),
             "① と ② の間の凹の所（c −10〜−6）の前の縁 a %.1f m（AS02C %.1f m）" % (L4["bay_c-10_-6"]["front_a_p50"], ev["S11_layers"]["AS02C"]["bay_c-10_-6"]["front_a_p50"]),
             "段：① の前の縁 − 凹 %.1f m、② − 凹 %.1f m" % (st["r1_front_minus_bay_m"], st["r2_front_minus_bay_m"]),
             "奥行き：② は ① より原画のカメラに %.1f m 近い、③ は ② より %.1f m 近い" % (st["r1_minus_r2_depth_m（② が ① よりカメラに近い）"], st["r2_minus_r3_depth_m（③ が ② よりカメラに近い）"]),
             "高さ：② の頂 − ③ の頂 = %.2f H0" % st["r2_crest_minus_r3_crest_over_H0"],
             "③ の前の縁は ② より %.1f m 後ろ（計画の「4〜5 m 前」は、原画視点の" % (-st["r3_front_minus_r2_front_m"]),
             "  船・手前の海の射線の禁止域にかかるので出していない）"]
    for k, line in enumerate(lines):
        d.text((20, 12 + 34 * k), line, font=F[22] if k else F[26], fill=INK)
    r1 = Image.new("RGB", (W, 440), BG); r1.paste(ch1, (20, 10)); r1.paste(ch2, (40 + 1170, 10))
    r2 = Image.new("RGB", (W, 440), BG); r2.paste(bar, (20, 10)); r2.paste(txt, (40 + 1170, 10))
    hd = header(W, "美術の見本04 の形 4：三つの層（S11）と、峰に沿う長さ（S10）・頂の高さ（S4）",
                ["粘土の下見（numpy）で、① 主の頂と唇（c −2〜+15）を赤、② の房（c −16〜−11）を緑、③ 最左側の小さな房（c −23〜−16）を青で薄く色づけ（列 90〜240：頂から唇の先・唇の下）。"])
    return stack([hd] + rows + [r1, r2], W)


def sheet5():
    names = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"), ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
    pairs = [(n2, BEFORE + "/views/%s_t120_claws.png" % n, AFTER + "/views/%s_t120_claws.png" % n) for n, n2 in names]
    return pair_grid(pairs, 1170, "美術の見本04 の形 5：材質つきの 7 視点（AS04 Flat Smooth、Unity、爪あり、前｜今）",
                     ["材質は調べ M の AS04 Flat Smooth（変えていない）。白の区域は見本03 の白の印 v2 を頂点の番号で引き継ぎ、境からの距離を新しい面で測り直した。低い行（頂 < 0.22 H0）は白にしない。"])


GATES = {}
UNION = {}


def main():
    ev = json.load(open(SH + "/final/eval_AS04.json", encoding="utf-8"))
    g = json.load(open(SH + "/render/measure/gates_A4/sweep_gates.json", encoding="utf-8"))
    GATES.update({k: v["after_claws"] for k, v in g["gates"].items()})
    UNION.update(json.load(open(SH + "/final/union_wave4_check.json", encoding="utf-8")))
    outs = {}
    for name, fn in (("shape_1_painting.png", lambda: sheet1(ev)), ("shape_2_clay_views.png", sheet2), ("shape_2b_clay_views_np.png", sheet2b),
                     ("shape_3_turntable.png", sheet3), ("shape_4_layers.png", lambda: sheet4(ev)), ("shape_5_material_views.png", sheet5)):
        img = fn()
        p = SH + "/" + name
        img.save(p)
        outs[name] = {"size": list(img.size), "sha256": S.sha(p)}
        print(name, img.size)
    S.jdump(SH + "/shape_sheets.json", outs)


if __name__ == "__main__":
    main()
