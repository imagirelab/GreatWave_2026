# -*- coding: utf-8 -*-
"""FLIP47：周期の波の実験の設計の下見の動画（流体の計算ではない）。py -3.10 -B g47_periodic_preview.py
2026-10-13 周期の波の設計の役（Claude）。読む物：Unity/Build/FLIP47/periodic_design.json（g47_periodic.py spec が書く）、
g47_sfwave（流れ関数の解）、g47_scan.print_lines（原画の輪郭。読むだけ）。書く物：Unity/Build/FLIP47/videos/periodic_design_preview.mp4 と .json。

並び（1920×1080、24 コマ/s、30 s）：
  上 2 段：P1（S2）の水槽の全部。1 段目は縦横同じ縮尺（10 m の目盛り）、2 段目は縦 4 倍（読みやすさのため。印を付ける）。
           入口の帯（青）・吸う帯（灰）・海底・静かな水面。波は流れ関数の解（19 m の平らの上だけ厳密）を x 144〜570 m に、実時間で 2 周期。
           570 m より先は描かない（計算で決まる所）。予測の印：定常の波で運べない水深の所（h_SF）と、Goda の崩れの所の幅。
  左下：頂の形を η_c で割って重ねる（原画、流れ関数の 19 m・定常の限りの手前、GN の孤立波）。後ろの角と 0.7 η_c の幅。
  右下：4 本の計算の表（海底・波・崩れの予測・費用）と、P3 の組の包絡。
"""
import os, sys, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g47_sfwave as SF
import g47_common as GC

B47 = GC.B47
VID = B47 + "/videos"
W, H, FPS = 1920, 1080, 24
FONT = "C:/Windows/Fonts/YuGothM.ttc"; FONTB = "C:/Windows/Fonts/YuGothB.ttc"
TXT = (25, 25, 25); SUB = (95, 95, 92)
WATER = (120, 170, 215); BED = (205, 185, 140); ZONE = (60, 110, 200); SPONGE = (150, 150, 150)
_fc = {}


def font(sz, b=False):
    k = (sz, b)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONTB if b else FONT, sz)
    return _fc[k]


def ffmpeg_path():
    p = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45/g45_common.py"
    try:
        for line in open(p, encoding="utf8"):
            if line.startswith("FFMPEG"):
                return line.split("=", 1)[1].strip().strip("r").strip('"')
    except Exception:
        pass
    return r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


def main():
    D = json.load(open(B47 + "/periodic_design.json", encoding="utf8"))
    sfd = D["design_wave"]["sf"]
    s = dict(k=sfd["k"], c=sfd["c"], h=sfd["h"], Ubar=sfd["Ubar"], B=np.array(sfd["B"]), E=np.array(sfd["E"]), H=sfd["H"], T=sfd["T"],
             L=2 * math.pi / sfd["k"])
    P1 = D["runs"]["P1_S2_sf14"]
    bed = P1["bed"]; x0, x1 = P1["box"]["x0"], P1["box"]["x1"]; xg = P1["parms"]["xg_end"]; xa0 = P1["parms"]["xa0"]
    xp = P1["parms"]["x_p"]
    pred = D["predictions"]["breaking"]["S2"]
    h_sf = [b for b in pred if b["method"] == "h_SF"][0]
    gd = [b for b in pred if b["method"].startswith("goda")]
    xb_lo = min(b["x_b"] for b in gd); xb_hi = max(b["x_b"] for b in gd)
    # 頂の形（η_c で割る）
    import g47_scan as S
    PL, pr = S.print_lines()
    s19 = SF.solve(19.0, s["T"], s["H"], N=40)
    trk = D["predictions"]["shoal_track_design"][-1]
    sL = SF.solve(trk["h"], s["T"], trk["H"], N=40)
    pm19 = SF.profile_measures(s19); pmL = SF.profile_measures(sL)
    C, kap = GC.gn_params(0.6 * 19.0, 19.0)
    a = 0.6 * 19.0
    gx07 = math.acosh(1 / math.sqrt(0.7)) / kap; gx09 = math.acosh(1 / math.sqrt(0.9)) / kap
    gn_back = math.degrees(math.atan2(0.2 * a, gx07 - gx09)); gn_w = 2 * gx07 / a

    out = VID + "/periodic_design_preview.mp4"
    os.makedirs(VID, exist_ok=True)
    proc = subprocess.Popen([ffmpeg_path(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    # 固定の部分（下の 2 つの枠）を先に描く
    base = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(base)
    dr.text((24, 10), "FLIP47 周期の波の実験の設計の下見（流体の計算ではない）", fill=TXT, font=font(26, True))
    dr.text((24, 46), "波は流れ関数の解（Fenton の方法、重力だけの定常の周期の波。19 m の平らの上だけ厳密）。570 m より先の形は計算で決まるので描かない。"
                      "印の崩れの所は推定（Goda 2010・1970 の崩れの指数と、定常の波で運べなくなる水深）", fill=SUB, font=font(16))
    # 左下：頂の形
    ox, oy, pw, ph = 30, 640, 900, 420
    dr.rectangle([ox, oy, ox + pw, oy + ph], outline=(170, 170, 170))
    dr.text((ox + 8, oy + 6), "頂の形を η_c で割って重ねる（右が進む向き、縦横同じ倍率）", fill=TXT, font=font(17, True))
    XL, XR, ZB, ZT = -2.6, 1.6, -0.45, 1.08
    PX = min((pw - 40) / (XR - XL), (ph - 90) / (ZT - ZB))
    gx0, gy0 = ox + 20, oy + 40
    tr = lambda xq, zq: (gx0 + (xq - XL) * PX, gy0 + (ZT - zq) * PX)
    for zv in (0.0, 0.7, 0.9, 1.0):
        dr.line([tr(XL, zv), tr(XR, zv)], fill=(120, 120, 120) if zv == 0 else (225, 225, 225), width=1)
        dr.text((gx0 - 18, tr(XL, zv)[1] - 8), "%g" % zv, fill=SUB, font=font(11))

    def prof(sv):
        X = np.linspace(-sv["L"] / 2, sv["L"] / 2, 3001)
        e = SF.eta(sv, X)
        ec = e.max()
        return X / ec, e / ec
    for sv, col, wd, lab in ((s19, (90, 140, 230), 2, "流れ関数 19 m（H 11 m、限りの 0.83 倍）"), (sL, (20, 60, 200), 4, "流れ関数 %.2f m（限りの 0.95 倍）" % trk["h"])):
        Xn, En = prof(sv)
        m = (Xn >= XL) & (Xn <= XR)
        dr.line([tr(a_, b_) for a_, b_ in zip(Xn[m], En[m])], fill=col, width=wd)
    xs = np.linspace(XL, XR, 800)
    eg = 1.0 / np.cosh(kap * xs * a) ** 2
    dr.line([tr(a_, b_) for a_, b_ in zip(xs, eg)], fill=(230, 130, 30), width=3)
    for arr in PL:
        dr.line([tr(a_, b_) for a_, b_ in arr], fill=(0, 0, 0), width=3)
    ly = oy + ph - 112
    rows = [((0, 0, 0), "原画（縦の伸びを戻した形）：後ろの角 %.0f°、0.7 η_c の幅 %.2f η_c【測った：STUDY52】" % (pr["print"]["cn"]["back_angle_07_09_deg"], pr["print"]["cn"]["width07_silhouette"])),
            ((20, 60, 200), "流れ関数の定常の限りの手前（水深 %.2f m）：%.0f°・%.2f【計算】" % (trk["h"], pmL["back_angle_07_09_deg"], pmL["width07_over_eta_c"])),
            ((90, 140, 230), "流れ関数 19 m の入れる波：%.0f°・%.2f【計算】" % (pm19["back_angle_07_09_deg"], pm19["width07_over_eta_c"])),
            ((230, 130, 30), "孤立波 a0/h0 0.6（S2 の入れた波）：%.0f°・%.2f【計算】。S2 の崩れ（最も近いコマ）は 8°・3.05【測った】" % (gn_back, gn_w))]
    for i, (col, t_) in enumerate(rows):
        dr.line([ox + 12, ly + 12 + 26 * i, ox + 44, ly + 12 + 26 * i], fill=col, width=4)
        dr.text((ox + 52, ly + 2 + 26 * i), t_, fill=TXT, font=font(14))
    # 右下：表
    tx0, ty0 = 960, 640
    dr.rectangle([tx0, ty0, W - 30, H - 20], outline=(170, 170, 170))
    dr.text((tx0 + 10, ty0 + 6), "1 回目の計算（粒子 0.25 m。崩れの予測は推定）", fill=TXT, font=font(17, True))
    br = D["predictions"]["breaking"]
    R = D["runs"]

    def pr_line(key):
        b = [q for q in br[key] if q["method"].startswith("goda") and q.get("broke")]
        return "x %.0f〜%.0f m・水深 %.1f〜%.1f m・η_c %.1f〜%.1f m" % (min(q["x_b"] for q in b), max(q["x_b"] for q in b), min(q["h_b"] for q in b),
                                                                   max(q["h_b"] for q in b), min(q["eta_c_b"] for q in b), max(q["eta_c_b"] for q in b))
    lines = [("P1", "S2（1:10→1.9 m）・規則波 T 14 s・H19 11 m", pr_line("S2"), R["P1_S2_sf14"]),
             ("P2", "S5（1:7→3.8 m）・同じ規則波", pr_line("S5"), R["P2_S5_sf14"]),
             ("P3", "S2・組（84 s ごとに 2 波＋上り下り、28 s 静か）", "P1 と同じ所（組の 1・2 番）", R["P3_S2_sets14"]),
             ("R4", "予備 1 本：a 岩棚の段（13→3.8 m）か b T 16 s", "a：段まで崩れない（Goda）", R["R4a_slab_sf14"])]
    yy = ty0 + 38
    for tag, w_, p_, rr in lines:
        c_ = rr["cost_estimate"]["hours"]
        dr.text((tx0 + 12, yy), tag, fill=TXT, font=font(18, True))
        dr.text((tx0 + 60, yy), w_, fill=TXT, font=font(15))
        dr.text((tx0 + 60, yy + 21), "崩れの予測 " + p_, fill=SUB, font=font(14))
        dr.text((tx0 + 60, yy + 40), "%.0f s・%d コマ・%.1f〜%.1f 時間【推定】" % (rr["t_end_s"], rr["f_end"], c_[0], c_[1]), fill=SUB, font=font(14))
        yy += 70
    # 組の包絡（小さく）
    ex0, ey0, ew, eh = tx0 + 12, yy + 4, 560, 60
    tt = np.linspace(0, 2 * 84.0, 600)
    sys.path.insert(0, HERE)
    import g47_periodic as GP
    Ee = GP.set_envelope(tt, 84.0, 14.0, 28.0, 14.0)
    dr.line([(ex0 + t_ / tt[-1] * ew, ey0 + eh - E_ * eh) for t_, E_ in zip(tt, Ee)], fill=ZONE, width=2)
    dr.text((ex0 + ew + 8, ey0 + 10), "P3 の組の包絡（2 組分、168 s）", fill=SUB, font=font(13))

    # 上 2 段の座標
    top = [dict(y0=92, ex=1.0, lab="縦横同じ縮尺"), dict(y0=262, ex=4.0, lab="縦 4 倍（読みやすさのため）")]
    XLm, XRm = x0 - 4, x1 + 4
    sx = (W - 80) / (XRm - XLm)
    xs_m = np.arange(x0, x1 + 0.01, 0.5)
    bedy = -np.interp(xs_m, [p[0] for p in bed], [p[1] for p in bed])
    nfr = int(2 * s["T"] * FPS)
    for fi in range(nfr + 3 * FPS):
        t = min(fi, nfr) / FPS
        img = base.copy(); d2 = ImageDraw.Draw(img)
        for pnl in top:
            ex = pnl["ex"]; y0 = pnl["y0"]
            ymid = y0 + 22 + 14 * sx * ex
            X = lambda xv: 40 + (xv - XLm) * sx
            Y = lambda yv: ymid - yv * sx * ex
            # 帯と吸う帯
            d2.rectangle([X(x0), Y(14), X(xg), Y(-19)], fill=(225, 233, 250))
            d2.rectangle([X(xa0), Y(14), X(x1), Y(-19)], fill=(232, 232, 232))
            # 水（静かな水面の下）と波
            m_ = xs_m <= 570.0
            e = np.where(m_, SF.eta(s, xs_m - xp, t), 0.0)
            # 帯の中は始めのなだらかさなし（下見は満ちた後の様子）。壁の近くのなだらかさだけ掛ける
            e = e * np.clip((xs_m - x0) / 30.0, 0, 1) ** 2 * (3 - 2 * np.clip((xs_m - x0) / 30.0, 0, 1))
            poly = [(X(x_), Y(max(e_, b_))) for x_, e_, b_ in zip(xs_m, e, bedy)] + [(X(x_), Y(b_)) for x_, b_ in zip(xs_m[::-1], bedy[::-1])]
            d2.polygon(poly, fill=WATER)
            mk = xs_m >= 570.0
            d2.polygon([(X(x_), Y(max(0.0, b_))) for x_, b_ in zip(xs_m[mk], bedy[mk])] + [(X(x_), Y(b_)) for x_, b_ in zip(xs_m[mk][::-1], bedy[mk][::-1])],
                       fill=(200, 222, 240))
            for yy_ in np.arange(-19.0, 15.0, 2.0):
                d2.line([X(570.0), Y(yy_), X(570.0), Y(yy_ + 1.0)], fill=(80, 80, 80), width=1)
            d2.polygon([(X(x_), Y(b_)) for x_, b_ in zip(xs_m, bedy)] + [(X(x1), Y(-20)), (X(x0), Y(-20))], fill=BED)
            for xx in np.arange(x0, x1, 8.0):
                d2.line([X(xx), Y(0), X(min(xx + 4, x1)), Y(0)], fill=(60, 60, 60), width=1)
            # 予測の印
            d2.line([X(h_sf["x_b"]), Y(15), X(h_sf["x_b"]), Y(-19)], fill=(200, 120, 0), width=2)
            d2.rectangle([X(xb_lo), Y(15), X(xb_hi), Y(-19)], outline=(200, 40, 40), width=2)
            d2.text((X(x0) + 4, Y(14) - 2), "入口の帯 144〜432 m", fill=ZONE, font=font(13))
            d2.text((X(xa0) + 4, Y(14) - 2), "吸う帯 790〜900 m", fill=(90, 90, 90), font=font(13))
            if ex > 1:
                d2.text((X(570) + 4, Y(-12)), "ここから先の波は計算で決まる（描かない）", fill=SUB, font=font(13))
                d2.text((X(h_sf["x_b"]) - 230, Y(17) - 4), "定常の波で運べない所 x %.0f（推定）" % h_sf["x_b"], fill=(200, 120, 0), font=font(13))
                d2.text((X(xb_hi) + 6, Y(16) - 4), "崩れの予測 x %.0f〜%.0f（Goda、推定）" % (xb_lo, xb_hi), fill=(200, 40, 40), font=font(13))
            # 目盛り
            d2.line([X(x0 + 10), Y(-19) + 14, X(x0 + 60), Y(-19) + 14], fill=TXT, width=3)
            d2.text((X(x0 + 10), Y(-19) + 18), "50 m", fill=TXT, font=font(12))
            d2.line([X(x1 - 30), Y(0), X(x1 - 30), Y(10)], fill=TXT, width=3)
            d2.text((X(x1 - 30) - 44, Y(10) - 2), "10 m", fill=TXT, font=font(12))
            d2.text((40, y0 - 4), "P1：S2 の海底・規則波 T 14 s・H 11 m（19 m の所）／%s" % pnl["lab"], fill=TXT, font=font(15, True))
        d2.text((W - 420, 8), "t = %5.2f s（実時間、2 周期）" % t, fill=TXT, font=font(18, True))
        
        proc.stdin.write(img.tobytes())
    proc.stdin.close(); rc = proc.wait()
    meta = dict(file=out, frames=nfr + 3 * FPS, fps=FPS, rc=rc, note_ja="設計の下見。流体の計算ではない。波は流れ関数の解（19 m の平らの上だけ）。印の崩れの所は推定",
                source="Unity/Build/FLIP47/periodic_design.json")
    json.dump(meta, open(VID + "/periodic_design_preview.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(meta)


if __name__ == "__main__":
    main()
