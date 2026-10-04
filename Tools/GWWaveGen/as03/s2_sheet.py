# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S2：原画の波頭の解剖の図（painting_zones.png、1920×1080）。
原画 DP130155（メトロポリタン美術館の公開の画像）の切り出しの上に、我々の線引き（冠の領域・藍の面・面の上の縁と舌・白い点・空の縁）と、
見本02 の 83 本の爪の役割（置いた 3D の爪の背骨を原画のカメラで写した線）を描く。利用者のマスクの画素・彫刻の写真は使わない。
右は凡例と主な数、下は行ごとの巻きの向きの色の並び（頂の列 90 からの m）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s2_sheet.py
"""
import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402

U = CC.U
ST = REPO + "/Unity/Build/Polish/sample03/study"
TMP = ST + "/tmp"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
CLAWD = REPO + "/Unity/Build/Polish/sample02/fix01/assemble/claws/mesh"
FONT = r"C:\Windows\Fonts\YuGothM.ttc"
FONTB = r"C:\Windows\Fonts\YuGothB.ttc"
A = U.A_DISP
OFFX = 156.66152659984573
X0, Y0, X1, Y1 = 80, 170, 2330, 1560          # 原画の切り出し（原画の画素）
PW, PH = 1400, 865
S = min(PW / (X1 - X0), PH / (Y1 - Y0))
COL = dict(crest_top=(255, 140, 0), lip=(220, 30, 60), b_crest=(20, 160, 60), face=(30, 90, 200), flecks=(240, 200, 0),
           CREST_CROWN=(220, 0, 160), FACE_INTERIOR=(0, 170, 230), NEAR_SEA=(120, 120, 120), sil=(0, 0, 0))
CLS_COL = [(235, 222, 195), (255, 255, 255), (190, 215, 205), (95, 85, 80), (60, 120, 180), (25, 45, 85)]


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def tp(p):
    """原画の画素 → 図の画素（左の枠）。"""
    p = np.asarray(p, np.float64)
    return np.stack([(p[..., 0] - X0) * S + 10, (p[..., 1] - Y0) * S + 60], -1)


def main():
    pc = json.load(open(ST + "/painting_crest.json", encoding="utf-8"))
    cr = json.load(open(ST + "/claw_roles.json", encoding="utf-8"))
    z = np.load(TMP + "/s2_zones.npz")
    cl = np.load(TMP + "/s2_classes.npz")["cls"]
    mp = np.load(TMP + "/s2_map.npz")
    im = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)
    crop = im[Y0:Y1, X0:X1]
    crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    crop = (crop.astype(np.float32) * 0.62 + 255 * 0.38).astype(np.uint8)        # 線引きが読めるよう薄く
    cw, ch = int((X1 - X0) * S), int((Y1 - Y0) * S)
    base = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_AREA).astype(np.float32)
    # 領域の塗り（薄く）と縁
    def zfill(mask, col, a):
        m = cv2.resize(mask[Y0:Y1, X0:X1].astype(np.uint8), (cw, ch), interpolation=cv2.INTER_NEAREST) > 0
        base[m] = base[m] * (1 - a) + np.array(col, np.float32) * a
        return m
    edges = []
    for g in ("b_crest", "crest_top", "lip"):
        k = "z_" + g
        if k in z.files:
            m = zfill(z[k], COL[g], 0.22)
            edges.append((m, COL[g], 3))
    mface = cv2.resize(z["face"][Y0:Y1, X0:X1].astype(np.uint8), (cw, ch), interpolation=cv2.INTER_NEAREST) > 0
    edges.append((mface, COL["face"], 2))
    canvas = np.full((1080, 1920, 3), 255, np.uint8)
    canvas[60:60 + ch, 10:10 + cw] = np.clip(base, 0, 255).astype(np.uint8)
    for m, col, wdt in edges:
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cs = [c for c in cs if cv2.contourArea(c) > 80]
        cv2.drawContours(canvas[60:60 + ch, 10:10 + cw], cs, -1, col, wdt, lineType=cv2.LINE_AA)
    # 空の縁（主役波の縁）
    sil = np.load(TMP + "/s2_sil.npy")
    q = tp(sil).astype(np.int32)
    cv2.polylines(canvas, [q], False, COL["sil"], 2, lineType=cv2.LINE_AA)
    for key, mk in (("summit_painting_px", "頂"), ("lip_tip_painting_px", "唇の先")):
        p = tp(np.array(pc["silhouette"][key], float))
        cv2.drawMarker(canvas, tuple(int(v) for v in p), (0, 0, 0), cv2.MARKER_DIAMOND, 18, 3)
    # 藍の面の上の縁・舌・藍の頭
    ed = np.load(TMP + "/s2_face_edges.npy", allow_pickle=True)
    sub_c = canvas[60:60 + ch, 10:10 + cw]
    for e in ed:
        e = np.asarray(e, float)
        if len(e) < 2:
            continue
        q = tp(e) - [10, 60]
        cv2.polylines(sub_c, [q.astype(np.int32)], False, (0, 200, 255), 2, lineType=cv2.LINE_AA)
    for key in ("tongues_main", "tongues_b"):
        for t in pc[key].get("tongues", []):
            p = tp(np.array([t["x"], t["y"]], float))
            cv2.drawMarker(canvas, tuple(int(v) for v in p), (255, 255, 255), cv2.MARKER_TRIANGLE_DOWN, 16, 5)
            cv2.drawMarker(canvas, tuple(int(v) for v in p), (0, 120, 255), cv2.MARKER_TRIANGLE_DOWN, 14, 2)
        for t in pc[key].get("heads", []):
            p = tp(np.array([t["x"], t["y"]], float))
            cv2.drawMarker(canvas, tuple(int(v) for v in p), (20, 30, 120), cv2.MARKER_TRIANGLE_UP, 12, 2)
    # 白い点
    fl = cv2.resize(z["flecks"][Y0:Y1, X0:X1].astype(np.uint8), (cw, ch), interpolation=cv2.INTER_NEAREST)
    ys, xs = np.nonzero(fl)
    canvas[60 + ys, 10 + xs] = COL["flecks"]
    # 測りの線（行＝巻きの向き、列＝頂に並ぶ向き）
    r = mp["r"]; c = mp["c"]; hm = mp["surf"] == 1
    sub = (slice(Y0, Y1), slice(X0, X1))
    for r0 in (105, 115, 125, 135, 145):
        m = hm[sub] & (np.abs(r[sub] - r0) < 0.25) & (c[sub] >= 85) & (c[sub] <= 205)
        m = cv2.resize(m.astype(np.uint8), (cw, ch), interpolation=cv2.INTER_AREA) > 0
        yy, xx = np.nonzero(m)
        canvas[60 + yy, 10 + xx] = (90, 90, 90)
    for c0 in (150, 170, 190):
        m = hm[sub] & (np.abs(c[sub] - c0) < 0.25) & (r[sub] >= 95) & (r[sub] <= 160)
        m = cv2.resize(m.astype(np.uint8), (cw, ch), interpolation=cv2.INTER_AREA) > 0
        yy, xx = np.nonzero(m)
        canvas[60 + yy, 10 + xx] = (150, 60, 150)
    # 見本02 の爪（置いた 3D の爪の背骨）と役割
    lay = json.load(open(CLAWD + "/ds33_claw_layout.json", encoding="utf-8"))
    V = np.fromfile(CLAWD + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3).astype(np.float64)
    lid = {k["user_id"]: k for k in lay["claws"]}
    cam = CC.painting_cam()
    pil = Image.fromarray(canvas)
    dr = ImageDraw.Draw(pil)
    f12 = font(13)
    for k in cr["claws"]:
        L = lid[k["id"]]
        o, st = L["vert_offset"], L["stations"]
        spine = np.vstack([V[o], V[o + 1:o + 1 + st * 8].reshape(st, 8, 3).mean(1), V[o + 1 + st * 8]])
        qd, _ = cam.project(spine)
        qp = np.stack([(qd[:, 0] + 0.5 - OFFX) / A - 0.5, (qd[:, 1] + 0.5) / A - 0.5], 1)
        f = tp(qp)
        if not ((f[:, 0] > 10) & (f[:, 0] < 10 + cw) & (f[:, 1] > 60) & (f[:, 1] < 60 + ch)).any():
            continue
        col = COL[k["role"]]
        dr.line([tuple(p) for p in f], fill=col, width=3)
        x, y = f[0]
        if k["role"] == "CREST_CROWN":
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col, outline=(0, 0, 0))
        elif k["role"] == "FACE_INTERIOR":
            dr.rectangle([x - 5, y - 5, x + 5, y + 5], fill=col, outline=(0, 0, 0))
            if k.get("face_top_fringe"):
                dr.rectangle([x - 8, y - 8, x + 8, y + 8], outline=(0, 0, 0), width=2)
        else:
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col)
        dr.text((x + 6, y - 15), k["id"][-3:], fill=(0, 0, 0), font=f12, stroke_width=2, stroke_fill=(255, 255, 255))
    # 見出し
    fb = font(26, True); f18 = font(18); f16 = font(16); f15 = font(15)
    dr.text((12, 12), "S2：原画の波頭の解剖（我々の線引き）と、見本02 の 83 本の爪の役割", fill=(0, 0, 0), font=fb)
    dr.text((14, 60 + ch + 6), "原画 DP130155（メトロポリタン美術館の公開の画像）の切り出し x %d〜%d・y %d〜%d（原画の画素）を薄くした上に描いた。利用者のマスク・彫刻の写真は使っていない。" % (X0, X1, Y0, Y1),
            fill=(60, 60, 60), font=f15)
    # 凡例と数（右）
    xr = 1430
    y = 60
    def leg(col, txt, kind="box"):
        nonlocal y
        if kind == "box":
            dr.rectangle([xr, y + 3, xr + 22, y + 19], fill=col)
        elif kind == "line":
            dr.line([xr, y + 11, xr + 22, y + 11], fill=col, width=4)
        elif kind == "dot":
            dr.ellipse([xr + 5, y + 5, xr + 17, y + 17], fill=col, outline=(0, 0, 0))
        elif kind == "sq":
            dr.rectangle([xr + 5, y + 5, xr + 17, y + 17], fill=col, outline=(0, 0, 0))
        dr.text((xr + 30, y), txt, fill=(0, 0, 0), font=f16)
        y += 24
    dr.text((xr, y), "凡例（我々の線引き）", fill=(0, 0, 0), font=font(19, True)); y += 28
    leg(COL["crest_top"], "頂の冠（上側の爪の領域）")
    leg(COL["lip"], "唇の泡の塊（途中・船側の爪の領域）")
    leg(COL["b_crest"], "b区域の第二の頂の冠")
    leg(COL["face"], "藍の面（線を除き白い点を含む）", "line")
    leg((0, 200, 255), "藍の面の上の縁（▼舌 ▲藍の頭）", "line")
    leg(COL["flecks"], "白い点（藍の面の中の小さな白）")
    leg((0, 0, 0), "空に接する主役波の縁（◇頂・唇の先）", "line")
    leg((90, 90, 90), "測りの線：行 105〜145（巻きの向き）", "line")
    leg((150, 60, 150), "測りの線：列 150・170・190（頂に並ぶ向き）", "line")
    leg(COL["CREST_CROWN"], "爪：冠の縁 CREST_CROWN（指の先へ）", "dot")
    leg(COL["FACE_INTERIOR"], "爪：面の内 FACE_INTERIOR（□太枠＝面の上の縁）", "sq")
    y += 6
    a = pc["along_curl_main"]["summary"]; ac = pc["face_bands_horizontal_main"]["summary"]; fm = pc["flecks_main"]["stats"]
    tm = pc["tongues_main"]; sl = pc["silhouette"]; g = pc["painting_claws"]["groups"]
    cnt = cr["counts"]
    lines = [
        ("主な数（AS02C の面の上の m）", True),
        ("冠の帯の深さ（最初の爪の線〜藍の面）p50 %.1f m（p10 %.1f・p90 %.1f）" % (a["crown_depth_m"]["p50"], a["crown_depth_m"]["p10"], a["crown_depth_m"]["p90"]), False),
        ("冠の中の水色 p50 %.0f%%・白 p50 %.0f%%" % (100 * a["crown_mizuiro_frac"]["p50"], 100 * a["crown_white_frac"]["p50"]), False),
        ("頂の上側の爪 %d 本：頂に並ぶ向き %.1f m に %.1f 本/m、長さ p50 %.2f m" % (g["crest_top"]["count"], g["crest_top"]["ca_span_m"], g["crest_top"]["per_m_along_crest"], g["crest_top"]["length_root_to_tip_m"]["p50"]), False),
        ("唇の爪 %d 本：唇の縁（見え）%.1f m に %.1f 本/m・%.1f 本/m²、長さ p50 %.2f m" % (g["lip"]["count"], g["lip"].get("lip_silhouette_screen_m", 0), g["lip"].get("per_m_of_lip_silhouette_screen", 0), g["lip"].get("per_m2_of_zone", 0), g["lip"]["length_root_to_tip_m"]["p50"]), False),
        ("b区域の爪 %d 本：%.1f m に %.1f 本/m、長さ p50 %.2f m" % (g["b_crest"]["count"], g["b_crest"]["ca_span_m"], g["b_crest"]["per_m_along_crest"], g["b_crest"]["length_root_to_tip_m"]["p50"]), False),
        ("面の藍中の帯：横の線ごと p50 %.0f 本（面の幅 p50 %.1f m）、幅 p50 %.2f m、間隔 p50 %.2f m" % (ac["n_ai_mid_bands"]["p50"], ac["face_width_m_chord"]["p50"], ac["ai_mid_width_m"]["p50"], ac["ai_mid_spacing_m"]["p50"]), False),
        ("藍濃の幅 p50 %.2f m（p90 %.2f m）" % (ac["ai_dark_width_m"]["p50"], ac["ai_dark_width_m"]["p90"]), False),
        ("舌 %d・藍の頭 %d、舌の深さ p50 %s m、頭の間隔 p50 %s m" % (tm.get("n_tongues", 0), tm.get("n_indigo_heads", 0),
                                                         (tm.get("tongue_depth_m_along_s") or {}).get("p50"), (tm.get("head_spacing_m") or {}).get("p50")), False),
        ("白い点 %d 個・%.1f 個/m²、径 p50 %.2f m、面の上の縁から p50 %.1f m 下" % (fm["count"], fm["per_m2"], fm["eq_diam_m"]["p50"], pc["flecks_main"]["depth_below_face_top_m"]["p50"]), False),
        ("縁の見えの長さ：頂→唇の先 %.1f m、唇の下 %.1f m" % (sl["summit_to_lip_tip_screen_m"], sl.get("lip_tip_to_underside_screen_m") or 0), False),
        ("爪の役割：冠 %d・面の内 %d・近い海 %d" % (cnt.get("CREST_CROWN", 0), cnt.get("FACE_INTERIOR", 0), cnt.get("NEAR_SEA", 0)), True),
    ]
    def wrap(txt, fnt, width):
        out_, cur = [], ""
        for ch_ in txt:
            if dr.textlength(cur + ch_, font=fnt) > width:
                out_.append(cur)
                cur = "　" + ch_
            else:
                cur += ch_
        if cur:
            out_.append(cur)
        return out_
    for txt, b in lines:
        fnt = font(17, True) if b else font(14)
        for ln in wrap(txt, fnt, 1915 - xr):
            dr.text((xr, y), ln, fill=(0, 0, 0), font=fnt)
            y += 25 if b else 19
    # 下：行ごとの巻きの向きの色の並び（頂の列 90 からの m）
    yb = y + 6
    dr.text((xr, yb), "行ごとの色の並び（横＝頂の列 90 からの s、0〜16 m）", fill=(0, 0, 0), font=font(14, True))
    yb += 20
    xx0 = xr
    for kk, nm in [(1, "白"), (2, "水色"), (3, "線"), (4, "藍中"), (5, "藍濃"), (0, "空")]:
        dr.rectangle([xx0, yb + 2, xx0 + 14, yb + 14], fill=CLS_COL[kk], outline=(0, 0, 0))
        dr.text((xx0 + 18, yb - 1), nm, fill=(0, 0, 0), font=font(13))
        xx0 += 70
    yb += 20
    cls = cl
    s_map = None
    att = np.fromfile(REPO + "/Unity/Build/Polish/sample02/fix01/assemble/attr/pl29/pl29_hero_attr_f32.bin", np.float32).reshape(240, 400, 12)
    rows = list(range(150, 99, -5))
    bw = 430
    hh = max(6, min(14, (1070 - yb) // max(len(rows), 1) - 2))
    ys_, xs_ = np.nonzero(hm & (c >= 85) & (c <= 205) & (np.arange(hm.shape[1])[None, :] >= 1000) & (np.arange(hm.shape[0])[:, None] <= 1350))
    rr = r[ys_, xs_]
    sv = U.bilin(att[..., 4].astype(np.float64)[..., None], rr.astype(np.float64), c[ys_, xs_].astype(np.float64))[:, 0]
    for i, r0 in enumerate(rows):
        sel = np.abs(rr - r0) < 0.5
        if sel.sum() < 30:
            continue
        s90 = float(att[r0, 90, 4])
        d = sv[sel] - s90
        k = cls[ys_[sel], xs_[sel]]
        strip = np.full((hh, bw, 3), 245, np.uint8)
        bins = np.clip((d / 16.0 * bw).astype(int), 0, bw - 1)
        for kk in range(6):
            mm = k == kk
            if mm.any():
                strip[:, np.unique(bins[mm])] = CLS_COL[kk]
        # 多数決で塗り直し
        cnts = np.zeros((6, bw))
        for kk in range(6):
            cnts[kk] = np.bincount(bins[k == kk], minlength=bw)
        has = cnts.sum(0) > 0
        strip[:, has] = np.array(CLS_COL)[np.argmax(cnts[:, has], 0)]
        pil.paste(Image.fromarray(strip), (xr + 40, yb))
        dr.text((xr, yb - 3), "r%d" % r0, fill=(0, 0, 0), font=font(12))
        yb += hh + 2
    for mtr in range(0, 17, 4):
        xx = xr + 40 + int(mtr / 16.0 * bw)
        dr.line([xx, yb, xx, yb + 4], fill=(0, 0, 0), width=1)
        dr.text((xx - 6, yb + 4), "%d" % mtr, fill=(0, 0, 0), font=font(11))
    notes = ["役割の決め方：置いた 3D の爪の背骨を原画のカメラで写し、空の縁から 12 px 以内か、周り 30 px の白・水色 ≥ 45%（藍の面 ≤ 35%）なら冠の縁 CREST_CROWN、"
             "周りの藍の面 ≥ 45% なら面の内 FACE_INTERIOR、根元が近い海なら NEAR_SEA（近い海の 10 本の多くはこの切り出しの外）。",
             "太枠の □ は面の内のうち、藍の面の上の縁から 0.8 m 以内の爪（白の泡の垂れの先の鉤）。冠に回すか、面の鉤のままにするかは利用者が選べる。",
             "数は t* の主役波 K*′ AS02C の面の上の m（原画の画素を原画のカメラの射線で面の点へ結んだ）。原画の色は面へ写していない（Q28）。"]
    yn = 60 + ch + 30
    for n_ in notes:
        for ln in wrap(n_, font(14), 1880):
            dr.text((14, yn), ln, fill=(40, 40, 40), font=font(14))
            yn += 19
    pil.save(ST + "/painting_zones.png")
    print("saved", pil.size)


if __name__ == "__main__":
    main()
