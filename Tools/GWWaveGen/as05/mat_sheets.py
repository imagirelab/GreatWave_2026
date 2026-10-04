# -*- coding: utf-8 -*-
"""美術の見本05 の材質 AS05（Q33、T5・T6）の前後の並べ図。前 = 見本04 の最後（AS04F、Unity/Build/Polish/sample04/assemble/render/FX1）、
後 = AS05（Unity/Build/Polish/sample05/mat/render/AS05）。形は同じ（主役波 K*′ AS04F ＋ wave4、爪 35 本）。

  py -3.10 -B Tools/GWWaveGen/as05/mat_sheets.py [--after <描画のフォルダー>] [--tag AS05]
出力：Unity/Build/Polish/sample05/mat/sheets/（1920 幅の PNG）。白の印の変わり目の図は numpy の z バッファ（Unity の描画ではない）。
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402

BG = (246, 244, 238)
INK = (30, 34, 40)


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def im(p):
    return Image.open(p).convert("RGB")


def label(img, text, sz=None, pad=8):
    d = ImageDraw.Draw(img)
    sz = max(sz or 0, img.width // 28, 22)   # 並べて縮めても読める大きさ（幅 1920 の画で 68 画素）
    pad = max(pad, sz // 4)
    f = font(sz, True)
    w = d.textlength(text, font=f)
    d.rectangle([0, 0, w + 2 * pad, sz + 2 * pad], fill=(255, 255, 255))
    d.text((pad, pad - 2), text, fill=INK, font=f)
    return img


def title_bar(text, sub=None, W=1920):
    h = 64 if sub is None else 100
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((20, 12), text, fill=INK, font=font(34, True))
    if sub:
        d.text((22, 60), sub, fill=(70, 74, 80), font=font(22))
    return img


def stack(imgs, W=1920):
    H = sum(i.height for i in imgs)
    out = Image.new("RGB", (W, H), BG)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height
    return out


def row(imgs, W=1920, gap=8):
    n = len(imgs)
    w = (W - gap * (n - 1)) // n
    hs = [int(i.height * w / i.width) for i in imgs]
    h = max(hs)
    out = Image.new("RGB", (W, h), BG)
    x = 0
    for i, hh in zip(imgs, hs):
        out.paste(i.resize((w, hh), Image.LANCZOS), (x, 0))
        x += w + gap
    return out


def painting_disp():
    import s5_targets as T
    return Image.fromarray(T.painting_disp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", default=M.MAT + "/render/AS05")
    ap.add_argument("--before", default=M.RENDER04F)
    ap.add_argument("--tag", default="AS05")
    ap.add_argument("--measure-before", default=M.MAT + "/measure/before_AS04F.json")
    ap.add_argument("--measure-after", default=M.MAT + "/measure/after_AS05.json")
    ap.add_argument("--edge-mesh", default=M.MAT + "/mesh/union_as05.json")
    g = ap.parse_args()
    out = M.MAT + "/sheets"
    os.makedirs(out, exist_ok=True)
    mb = M.jl(g.measure_before) if os.path.isfile(g.measure_before) else {}
    ma = M.jl(g.measure_after) if os.path.isfile(g.measure_after) else {}

    def k5(m):
        return m.get("K_T5_T6_study_rule", {}).get("T5_small_white_blobs_on_hero_indigo")

    def k6(m):
        return (m.get("T6_surface_edge", {}).get("painting") or {}).get("pale_share")

    B, A = g.before, g.after
    P = painting_disp()
    # ---- 1 原画視点
    s1 = [title_bar("見本05 の材質 AS05：原画視点（前 = 見本04 AS04F、後 = AS05。形は同じ）",
                    "T5 波の本体の白い粒を外した（原画視点の粒の数 %s → %s）。T6 唇の下の内の縁に白・水色を置かない（縁の帯の白・水色の割合 %s → %s）" % (k5(mb), k5(ma), k6(mb), k6(ma)))]
    s1.append(row([label(P.copy(), "原画"), label(im(B + "/views/painting_t120_claws.png"), "見本04（AS04F）"), label(im(A + "/views/painting_t120_claws.png"), "見本05 材質（AS05）")]))
    x0, y0, x1, y1 = 690, 270, 1000, 760
    crop = lambda p: p.crop((x0, y0, x1, y1))
    s1.append(title_bar("利用者の切り出し（Q33）の所の拡大：x %d〜%d、y %d〜%d（赤い枠 = 切り出し x 736〜891、y 300〜721）" % (x0, x1, y0, y1)))
    cs = []
    for name, img in (("原画", P), ("見本04", im(B + "/views/painting_t120_claws.png")), ("見本05 材質", im(A + "/views/painting_t120_claws.png"))):
        c = crop(img)
        d = ImageDraw.Draw(c)
        d.rectangle([736 - x0, 300 - y0, 891 - x0, 721 - y0], outline=(220, 40, 30), width=2)
        cs.append(label(c, name))
    s1.append(row(cs))
    stack(s1).save(out + "/as05m_1_painting.png")
    # ---- 2 7 視点
    s2 = [title_bar("見本05 の材質 AS05：7 視点（左 = 見本04 AS04F、右 = AS05。爪あり）",
                    "粒の数（爪なしの描画、主役波の藍に囲まれた 2〜400 画素の白・水色の塊）：" + "、".join(
                        "%s %s→%s" % (v, (mb.get("T5_views", {}).get(v) or {}).get("small_white_blobs_on_hero_indigo"),
                                      (ma.get("T5_views", {}).get(v) or {}).get("small_white_blobs_on_hero_indigo")) for v in M.VIEWS7))]
    ja = {"painting": "原画視点", "seat": "座席", "seat_toward_wave": "座席から波", "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
    for v in M.VIEWS7:
        s2.append(row([label(im(B + "/views/%s_t120_claws.png" % v), "%s：見本04" % ja[v]), label(im(A + "/views/%s_t120_claws.png" % v), "%s：見本05 材質" % ja[v])]))
    stack(s2).save(out + "/as05m_2_views.png")
    # ---- 3 波頭の回り台
    s3 = [title_bar("見本05 の材質 AS05：波頭の回り台 8 方位（上 2 段 = 見本04 AS04F、下 2 段 = AS05。爪あり）")]
    azs = ["%03d" % a for a in range(0, 360, 45)]
    for src, nm in ((B, "見本04"), (A, "見本05 材質")):
        for half in (azs[:4], azs[4:]):
            s3.append(row([label(im(src + "/crest/t120_az%s_claws.png" % a), "%s %s°" % (nm, int(a)), 22) for a in half]))
    stack(s3).save(out + "/as05m_3_crest.png")
    # ---- 4 T6 の面の上の変わり目（numpy）と座席の縁
    ch0, tri, _ = M.read_static(M.UNION04F)
    ch1, _, _ = M.read_static(g.edge_mesh)
    w0 = ch0["uv5"][:, 2]
    w1 = ch1["uv5"][:, 2]
    tris, lab, th = M.scene(ch0, tri, M.N_HERO04F, claws=None)
    tiles = []
    for v, nm in (("painting", "原画視点"), ("seat", "座席"), ("side_right", "右の側面"), ("tt60", "回り台 60°")):
        cm, idb, D, L = M.raster(v, tris, lab)
        hero = L == 1
        tv = th[np.clip(idb - 1, 0, len(th) - 1)]
        img = np.full(L.shape + (3,), 235, np.uint8)
        img[L == 6] = (150, 160, 175)
        img[L == 5] = (90, 110, 190)
        a0 = w0[tv].mean(-1)
        a1 = w1[tv].mean(-1)
        img[hero & (a1 > 0)] = (250, 245, 225)
        img[hero & (a1 <= 0)] = (35, 60, 100)
        img[hero & (a0 > 0) & (a1 <= 0)] = (230, 60, 40)
        tiles.append(label(Image.fromarray(img), "%s：白 → 藍にした所（赤）" % nm, 22))
    rep = M.jl(os.path.splitext(g.edge_mesh)[0] + "_edge_report.json")
    r0 = rep["results"][0]
    s4 = [title_bar("T6：面の上で白の印 whiteSD を書き換えた所（numpy の z バッファ、Unity の描画ではない）",
                    "規則の行 c %s〜%s m（下の端は同じ稜の白の終わり c %s m まで延長）、白 → 藍の頂点 %s・面積 %s m²。唇の鉤（浪尖）の白は変えない" % (
                        r0.get("c_m", ["?", "?"])[0], r0.get("c_m", ["?", "?"])[1], (r0.get("extend_end") or {}).get("c_m"),
                        r0.get("white_vertices_to_indigo"), r0.get("white_area_to_indigo_m2")))]
    s4.append(row(tiles[:2]))
    s4.append(row(tiles[2:]))
    sx0, sy0, sx1, sy1 = 960, 500, 1320, 1080
    s4.append(title_bar("座席から見た右の脇の稜（x %d〜%d、y %d〜%d）：左 = 見本04、右 = AS05" % (sx0, sx1, sy0, sy1)))
    s4.append(row([label(im(B + "/views/seat_t120_claws.png").crop((sx0, sy0, sx1, sy1)), "見本04"),
                   label(im(A + "/views/seat_t120_claws.png").crop((sx0, sy0, sx1, sy1)), "見本05 材質")]))
    stack(s4).save(out + "/as05m_4_t6_surface.png")
    # ---- 5 粒（座席から波）
    s5 = [title_bar("T5：座席から波（爪なし）。左 = 見本04（粒 %s）、右 = AS05（粒 %s。残りは画の端の切れ端と遠い海の点）" % (
        (mb.get("T5_views", {}).get("seat_toward_wave") or {}).get("small_white_blobs_on_hero_indigo"),
        (ma.get("T5_views", {}).get("seat_toward_wave") or {}).get("small_white_blobs_on_hero_indigo")))]
    s5.append(row([label(im(B + "/views/seat_toward_wave_t120_clawfree.png"), "見本04"), label(im(A + "/views/seat_toward_wave_t120_clawfree.png"), "見本05 材質")]))
    s5.append(row([label(im(B + "/views/seat_t120_clawfree.png"), "座席：見本04"), label(im(A + "/views/seat_t120_clawfree.png"), "座席：見本05 材質")]))
    stack(s5).save(out + "/as05m_5_t5_grain.png")
    print(json.dumps({"sheets": sorted(os.listdir(out))}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
