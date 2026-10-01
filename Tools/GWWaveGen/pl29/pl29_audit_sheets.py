# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の前の点検（AUDIT）の図（1920×1080 PNG）を作る。

入力：PL29Audit.cs の出力（<before>/views・tt）と pl29_audit_measure.py の出力（<before>/audit/audit_metrics.json・components.json・maps_*.npz）。
出力（<out>）：
  fig_pl29a_before_tNNN.png   時刻ごと：上 2 段＝7 視点の作品のまま（爪・飛沫・線）、下 2 段＝同じ視点の診断の重ね（爪なし）と凡例
  fig_pl29a_turntable_tNNN.png 時刻ごと：回り台 12 方位（上 2 段＝爪あり、下 2 段＝診断の重ね）
  fig_pl29a_crops_<kind>.png   壊れ方ごとの切り抜き（大きい順。視点・時刻を散らす）
  fig_pl29a_counts.png         視点ごとの数の表
画像はどれも Unity の PC 描画（HMD 実機ではない）。参照モデルや写真は使わない。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_sheets.py --before <dir> --out <dir>
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
TOP = 74
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TIMES = ["t060", "t090", "t105", "t120"]
VJ = {"painting": "原画視点", "seat": "座席", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面", "side_right": "右の側面",
      "back65": "後ろ 65°", "top": "真上", "tt": "回り台"}
TJ = {"t060": "t 6 s", "t090": "t 9 s", "t105": "t 10.5 s", "t120": "t 12 s（t*）"}
FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
FONTB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
C_STRETCH = (255, 140, 0)
C_BAND = (225, 0, 200)
C_FLAT = (0, 205, 235)
C_SEAM = (255, 0, 0)
C_CLAW = (40, 220, 40)
C_MELT = (255, 235, 0)


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def overlay(colour_path, maps):
    base = np.asarray(Image.open(colour_path).convert("RGB")).astype(np.float32)
    g = base.mean(axis=2, keepdims=True)
    out = np.where(maps["hero"][..., None], base, 0.35 * g + 0.65 * 235.0)
    def tint(mask, col, a):
        nonlocal out
        out = np.where(mask[..., None], (1 - a) * out + a * np.array(col, np.float32), out)
    stretch = maps["stretch"]
    tint(maps["band"], C_BAND, 0.55)
    tint(maps["flat"], C_FLAT, 0.55)
    tint(stretch, C_STRETCH, 0.75)
    o8 = np.clip(out, 0, 255).astype(np.uint8)
    # 平らな面の芯の輪郭（黄）、継ぎ目（赤）、爪が主役波を隠す所の輪郭（緑）と溶けた縁（黄）
    core = maps["core"].astype(np.uint8)
    cs, _ = cv2.findContours(core, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(o8, cs, -1, C_MELT, 3)
    seam = cv2.dilate(maps["seam"].astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    o8[seam] = C_SEAM
    over = maps["over"].astype(np.uint8)
    cs, _ = cv2.findContours(over, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(o8, cs, -1, C_CLAW, 2)
    return Image.fromarray(o8)


def legend(draw, x, y, w, h):
    f = font(19)
    items = [(None, "診断の色（主役波の色の出どころ。爪なし・線なし）"), ((255, 255, 255), "そのままの色＝原画カメラからの投影（直接）"),
             (C_STRETCH, "橙＝直接を斜めに読んだ引き伸ばし（異方性≥4）"), (C_BAND, "紫＝外挿の帯（行・列の色を写した所）"),
             (C_FLAT, "水色＝平らな塗り（見えない内側・海面の藍濃）"), (C_MELT, "黄の線＝平らな面の芯（色の境から 48 px 超）"),
             (C_SEAM, "赤＝継ぎ目（投影の境で色が切れる所）"), (C_CLAW, "緑の線＝立体の爪が主役波を隠す所")]
    yy = y + 6
    f = font(17)
    for col, txt in items:
        if col is not None:
            draw.rectangle([x + 10, yy + 4, x + 30, yy + 22], fill=col, outline=(80, 80, 80))
            draw.text((x + 38, yy), txt, fill=(20, 20, 20), font=f)
        else:
            draw.text((x + 10, yy), txt, fill=(20, 20, 20), font=font(18, True))
        yy += 29


def header(draw, text, sub):
    draw.rectangle([0, 0, W, TOP - 2], fill=(30, 40, 60))
    draw.text((16, 4), text, fill=(255, 255, 255), font=font(24, True))
    draw.text((16, 42), sub, fill=(210, 220, 235), font=font(16))


def tile_label(draw, x, y, txt):
    f = font(17, True)
    tw = draw.textlength(txt, font=f)
    draw.rectangle([x, y, x + tw + 12, y + 26], fill=(0, 0, 0))
    draw.text((x + 6, y + 2), txt, fill=(255, 255, 255), font=f)


def sheet_time(before, audit, t, m, outp):
    th = (H - TOP) // 4
    tw = th * 16 // 9
    im = Image.new("RGB", (W, H), (245, 245, 245))
    dr = ImageDraw.Draw(im)
    s = m["summaryByTime"][t]
    header(dr, f"仕上げ29 前の点検（今の採用：K*′ P28R2rec・G_p28rec・焼き込み bake_rec）｜{TJ[t]}｜上：作品のまま　下：投影の破れの診断",
           f"主役波の見える画素のうち 直接 {s['directFrac']*100:.1f}%・外挿の帯 {s['bandFrac']*100:.1f}%・平らな塗り {s['flatFillFrac']*100:.1f}%・引き伸ばし {s['stretchFracOfHero']*100:.1f}%"
           f"（7 視点＋回り台 12 方位）。Unity 6000.4.3f1 の PC 描画（HMD ではない）。")
    x0 = (W - 4 * tw) // 2
    for i, v in enumerate(VIEWS):
        r, c = divmod(i, 4)
        x, y = x0 + c * tw, TOP + r * th
        im.paste(Image.open(os.path.join(before, "views", f"{v}_{t}_asis.png")).convert("RGB").resize((tw - 4, th - 4), Image.LANCZOS), (x + 2, y + 2))
        tile_label(dr, x + 4, y + 4, VJ[v])
        mp = os.path.join(audit, f"maps_{v}_{t}.npz")
        y2 = TOP + (r + 2) * th
        if os.path.exists(mp):
            maps = dict(np.load(mp))
            ov = overlay(os.path.join(before, "views", f"{v}_{t}_clawfree.png"), maps)
            im.paste(ov.resize((tw - 4, th - 4), Image.LANCZOS), (x + 2, y2 + 2))
            rr = m["views"][f"{v}_{t}"]
            tile_label(dr, x + 4, y2 + 4, f"{VJ[v]}　直接 {rr['directFrac']*100:.0f}%・帯 {rr['bandFrac']*100:.0f}%・平 {rr['flatFillFrac']*100:.0f}%")
        else:
            dr.rectangle([x + 2, y2 + 2, x + tw - 2, y2 + th - 2], fill=(220, 220, 220))
            dr.text((x + 20, y2 + 100), f"{VJ[v]}：主役波が画面にない", fill=(60, 60, 60), font=font(20))
    # 凡例は右下の空き、右上の空きには視点ごとの数
    legend(dr, x0 + 3 * tw + 2, TOP + 3 * th + 2, tw - 4, th - 4)
    xx, yy = x0 + 3 * tw + 10, TOP + th + 8
    dr.text((xx, yy), "この時刻の数（7 視点）", fill=(20, 20, 20), font=font(18, True)); yy += 28
    for v in VIEWS:
        rr = m["views"][f"{v}_{t}"]
        if not rr["heroPx"]:
            dr.text((xx, yy), f"{VJ[v]}：主役波なし", fill=(60, 60, 60), font=font(15)); yy += 24; continue
        dr.text((xx, yy), f"{VJ[v]}：引伸 {rr['stretch']['stretchFracOfHero']*100:.0f}%・継ぎ目 {rr['seam']['seamSegments']}・平らな面 {rr['flat']['regions']}・帯 {rr['band']['bands']}・"
                 f"溶けた爪 {rr['claws']['clawPiecesMelted']}／{rr['claws']['clawPieces']}", fill=(30, 30, 30), font=font(15))
        yy += 24
    im.save(outp, optimize=True)


def sheet_tt(before, audit, t, m, outp, n=12):
    tw, th = 320, 180
    im = Image.new("RGB", (W, H), (245, 245, 245))
    dr = ImageDraw.Draw(im)
    s_parts = [m["tt"][f"{t}_az{int(round(k * 360 / n)):03d}"] for k in range(n)]
    hp = sum(r["heroPx"] for r in s_parts)
    dfr = sum(r["directFrac"] * r["heroPx"] for r in s_parts) / hp
    bfr = sum(r["bandFrac"] * r["heroPx"] for r in s_parts) / hp
    ffr = sum(r["flatFillFrac"] * r["heroPx"] for r in s_parts) / hp
    header(dr, f"仕上げ29 前の点検｜回り台 12 方位（30° ごと、原画視点の向きから）｜{TJ[t]}｜上 2 段：作品のまま（爪あり・飛沫なし）　下 2 段：診断",
           f"回り台の主役波の見える画素のうち 直接 {dfr*100:.1f}%・外挿の帯 {bfr*100:.1f}%・平らな塗り {ffr*100:.1f}%。中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°。周りの海は隠す。")
    for k in range(n):
        az = int(round(k * 360 / n))
        r, c = divmod(k, 6)
        x, y = c * tw, TOP + r * th
        im.paste(Image.open(os.path.join(before, "tt", f"{t}_az{az:03d}_claws.png")).convert("RGB").resize((tw - 2, th - 2), Image.LANCZOS), (x + 1, y + 1))
        tile_label(dr, x + 3, y + 3, f"az {az}°")
        maps = dict(np.load(os.path.join(audit, f"maps_tt_{t}_az{az:03d}.npz")))
        ov = overlay(os.path.join(before, "tt", f"{t}_az{az:03d}_claws.png"), maps)
        y2 = TOP + (r + 2) * th
        im.paste(ov.resize((tw - 2, th - 2), Image.LANCZOS), (x + 1, y2 + 1))
        rr = m["tt"][f"{t}_az{az:03d}"]
        tile_label(dr, x + 3, y2 + 3, f"az {az}° 直接 {rr['directFrac']*100:.0f}%・帯 {rr['bandFrac']*100:.0f}%")
    legend(dr, 0, TOP + 4 * th + 2, W, H - TOP - 4 * th)
    im.save(outp, optimize=True)


KIND_J = {"stretch": "引き伸ばし（直接の投影を斜めに読んだ所）", "seam": "継ぎ目（投影の境で色が切れる所）", "flat": "平らな面（特徴のない一色の壁）",
          "band": "外挿の帯（同じ行・列の色を写した帯）", "claw": "溶けた爪（立体の爪が焼き込みの白に溶ける）"}


def pick(comps, kind, n=15, per_view=3):
    cs = [c for c in comps if c["kind"] == kind]
    if kind == "claw":
        cs = [c for c in cs if c.get("melted") or c.get("meltedColour")]
    key = (lambda c: -c.get("extentPx", c["area"])) if kind == "flat" else (lambda c: -max(c["bbox"][2] - c["bbox"][0], c["bbox"][3] - c["bbox"][1]) * (1 if kind == "seam" else 0) - c["area"])
    cs.sort(key=key)
    out, cnt, seen = [], {}, set()
    for c in cs:
        k = c["view"]
        if cnt.get(k, 0) >= per_view:
            continue
        sig = (c["view"], c["t"], c["bbox"][0] // 120, c["bbox"][1] // 120)
        if sig in seen:
            continue
        seen.add(sig)
        cnt[k] = cnt.get(k, 0) + 1
        out.append(c)
        if len(out) >= n:
            break
    return out


def sheet_crops(before, audit, comps, kind, m, outp):
    sel = pick(comps, kind)
    tw, th, lh = 384, 284, 51
    im = Image.new("RGB", (W, H), (245, 245, 245))
    dr = ImageDraw.Draw(im)
    tot = len([c for c in comps if c["kind"] == kind and (kind != "claw" or c.get("melted") or c.get("meltedColour"))])
    header(dr, f"仕上げ29 前の点検｜切り抜き：{KIND_J[kind]}｜見つかった成分 {tot}（7 視点 × 4 時刻、回り台を除く）のうち大きい順 {len(sel)}",
           "左上の数字は成分の大きさ。赤い線が検出した範囲（爪は緑＝爪、黄＝溶けた縁）。切り抜きは作品のまま（爪・飛沫・線）の Unity の画像。")
    mkey = {"stretch": "stretch", "seam": "seam", "flat": "core", "band": "band", "claw": "over"}[kind]
    for i, c in enumerate(sel):
        r, col = divmod(i, 5)
        x, y = col * tw, TOP + r * (th + lh)
        bx0, by0, bx1, by1 = c["bbox"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        bw, bh = (bx1 - bx0) * 1.4 + 40, (by1 - by0) * 1.4 + 40
        asp = (tw - 4) / (th - 4)
        sw = max(bw, bh * asp, 240.0)
        sh = sw / asp
        if sw > W:
            sw = float(W); sh = sw / asp
        if sh > H:
            sh = float(H); sw = sh * asp
        lw = max(2, int(round(2 * sw / (tw - 4))))
        sx0 = int(np.clip(cx - sw / 2, 0, W - sw)); sy0 = int(np.clip(cy - sh / 2, 0, H - sh))
        sx1, sy1 = int(min(W, sx0 + sw)), int(min(H, sy0 + sh))
        src = np.asarray(Image.open(os.path.join(before, "views", f"{c['view']}_{c['t']}_asis.png")).convert("RGB")).copy()
        maps = dict(np.load(os.path.join(audit, f"maps_{c['view']}_{c['t']}.npz")))
        mk = maps[mkey].astype(np.uint8)
        if kind == "stretch":
            mk = cv2.dilate(mk, np.ones((7, 7), np.uint8))
        if kind == "seam":
            mk = cv2.dilate(mk, np.ones((5, 5), np.uint8))
        win = np.zeros_like(mk); win[by0:by1, bx0:bx1] = 1
        mk = mk & win
        cs, _ = cv2.findContours(mk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(src, cs, -1, C_CLAW if kind == "claw" else C_SEAM, lw)
        if kind == "claw":
            src[(maps["melted"] > 0) & (win > 0)] = C_MELT
        crop = Image.fromarray(src[sy0:sy1, sx0:sx1]).resize((tw - 4, th - 4), Image.LANCZOS)
        im.paste(crop, (x + 2, y + 2))
        val = c.get("extentPx", c["area"])
        tile_label(dr, x + 4, y + 4, f"{val:,} px")
        extra = ""
        if kind == "flat":
            extra = f"　{c.get('class')}・平らな塗り {100*(c.get('flatFillFrac') or 0):.0f}%・帯 {100*(c.get('bandFrac') or 0):.0f}%"
        if kind == "claw":
            mef = c.get("meltedEdgeFrac"); rcf = c.get("ringContrastFrac")
            extra = f"　同じ色区の縁 {100*(mef or 0):.0f}%・輪の対比 {100*(rcf or 0):.0f}%"
        dr.text((x + 6, y + th + 2), f"{VJ[c['view']]}　{TJ[c['t']]}", fill=(20, 20, 20), font=font(17, True))
        dr.text((x + 6, y + th + 24), f"枠 x{bx0}–{bx1} y{by0}–{by1}{extra}", fill=(60, 60, 60), font=font(14))
    im.save(outp, optimize=True)


def sheet_counts(m, outp):
    im = Image.new("RGB", (W, H), (250, 250, 250))
    dr = ImageDraw.Draw(im)
    header(dr, "仕上げ29 前の点検｜数の表（主役波の見える画素の割合と、壊れ方ごとの数。4 時刻の合計・画素で重み付け）",
           "直接＝原画カメラから見えた所の投影。帯＝外挿の帯。平＝平らな塗り（原画で見えない所の藍濃）。引伸＝直接のうち異方性 ≥ 4。芯＝色の境から 48 px より遠い所。爪＝爪が主役波を隠す成分（≥ 40 px）。")
    cols = ["視点", "画像", "主役波 px", "直接", "帯", "平", "引伸", "継ぎ目の成分（≥60px）", "帯の境 px", "平らな面（塗り由来）", "芯", "帯の成分", "爪", "溶けた爪 色区／色", "爪の縁の同じ色区"]
    rows = []
    for v in VIEWS + ["turntable"]:
        s = m["summaryByView"][v]
        bandedge = sum(m["views"][f"{v}_{t}"]["seam"]["bandEdgePx"] for t in TIMES if m["views"][f"{v}_{t}"]["heroPx"]) if v != "turntable" else sum(r["seam"]["bandEdgePx"] for r in m["tt"].values() if r["heroPx"])
        rows.append([VJ.get(v, "回り台（12 方位）"), s["images"], f"{s['heroPx']:,}", f"{s['directFrac']*100:.1f}%", f"{s['bandFrac']*100:.1f}%", f"{s['flatFillFrac']*100:.1f}%",
                     f"{s['stretchFracOfHero']*100:.1f}%", f"{s['seamSegments']}（{s['seamSegmentsLong']}）", f"{bandedge:,}", f"{s['flatRegions']}（{s['flatRegionsFromFill']}）",
                     f"{s['flatCoreFracOfHero']*100:.1f}%", s["bands"], s["clawPieces"], f"{s['clawPiecesMelted']}／{s['clawPiecesMeltedColour']}", f"{s['clawMeltedEdgeFrac']*100:.0f}%"])
    for lab, s in (("原画視点の外の計", m["summaryNonPainting"]),):
        rows.append([lab, s["images"], f"{s['heroPx']:,}", f"{s['directFrac']*100:.1f}%", f"{s['bandFrac']*100:.1f}%", f"{s['flatFillFrac']*100:.1f}%",
                     f"{s['stretchFracOfHero']*100:.1f}%", f"{s['seamSegments']}（{s['seamSegmentsLong']}）", "", f"{s['flatRegions']}（{s['flatRegionsFromFill']}）",
                     f"{s['flatCoreFracOfHero']*100:.1f}%", s["bands"], s["clawPieces"], f"{s['clawPiecesMelted']}／{s['clawPiecesMeltedColour']}", f"{s['clawMeltedEdgeFrac']*100:.0f}%"])
    widths = [190, 60, 130, 80, 80, 80, 80, 170, 110, 160, 80, 90, 60, 150, 140]
    x0, y0 = 20, TOP + 20
    f, fb = font(18), font(18, True)
    x = x0
    for c, wdt in zip(cols, widths):
        dr.rectangle([x, y0, x + wdt, y0 + 52], fill=(225, 230, 240), outline=(180, 180, 180))
        dr.multiline_text((x + 5, y0 + 4), c if len(c) < 9 else c[:8] + "\n" + c[8:], fill=(20, 20, 20), font=font(15, True))
        x += wdt
    y = y0 + 52
    for i, row in enumerate(rows):
        x = x0
        for c, wdt in zip(row, widths):
            dr.rectangle([x, y, x + wdt, y + 40], fill=(255, 255, 255) if i % 2 == 0 else (244, 246, 250), outline=(200, 200, 200))
            dr.text((x + 6, y + 8), str(c), fill=(20, 20, 20), font=fb if i == len(rows) - 1 else f)
            x += wdt
        y += 40
    uv = m["uvTexelCategoryFrac"]
    y += 20
    items = [f"{k} {v*100:.1f}%" for k, v in uv.items()]
    dr.text((x0, y), "焼き込みのテクセル（4096×4096、UV の空間。面積ではない）のカテゴリ：" + "、".join(items[:5]), fill=(20, 20, 20), font=font(17))
    y += 28
    dr.text((x0 + 40, y), "、".join(items[5:]), fill=(20, 20, 20), font=font(17))
    y += 34
    ic = m["identityCheckPaintingT120"]
    dr.text((x0, y), f"診断の読みの確かめ：原画視点 t* で、K* の原画カメラへの投影と画面の画素の差 中央値 {ic['medianPx']:.3f} px・p99 {ic['p99Px']:.3f} px（{ic['n']:,} 画素）。", fill=(20, 20, 20), font=font(17))
    y += 34
    th = m["thresholds"]
    dr.text((x0, y), f"閾値（進行役の判断）：引き伸ばし 異方性 ≥ {th['ANISO']}、同じ面 UV の差 ≤ {th['UVCONT']} テクセル、折り返し ≥ {th['FOLD']} px、芯 > {th['DFLAT']} px・平らな面 ≥ {th['FLATMIN']} px、帯の成分 ≥ {th['BANDMIN']} px、"
                     f"爪の成分 ≥ {th['CLAWMIN']} px（溶けた：同じ色区の縁 ≥ 80%（線なしの ID）／輪の対比 < {int(th['RINGFRAC']*100)}%（作品のまま、L1 ≥ {th['RING']}））。", fill=(20, 20, 20), font=font(15))
    y += 30
    dr.text((x0, y), "座席 t 6 s は主役波が画面の外（数に入れない）。継ぎ目の成分の括弧は長さ 60 px 以上、平らな面の括弧は平らな塗りか帯が半分以上のもの。", fill=(60, 60, 60), font=font(15))
    im.save(outp, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    audit = os.path.join(a.before, "audit")
    m = json.load(open(os.path.join(audit, "audit_metrics.json"), encoding="utf-8"))
    comps = json.load(open(os.path.join(audit, "components.json"), encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    for t in TIMES:
        sheet_time(a.before, audit, t, m, os.path.join(a.out, f"fig_pl29a_before_{t}.png"))
        sheet_tt(a.before, audit, t, m, os.path.join(a.out, f"fig_pl29a_turntable_{t}.png"))
    for kind in ("stretch", "seam", "flat", "band", "claw"):
        sheet_crops(a.before, audit, comps, kind, m, os.path.join(a.out, f"fig_pl29a_crops_{kind}.png"))
    sheet_counts(m, os.path.join(a.out, "fig_pl29a_counts.png"))
    print("done")


if __name__ == "__main__":
    main()
