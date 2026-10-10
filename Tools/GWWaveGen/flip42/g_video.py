# -*- coding: utf-8 -*-
"""FLIP42：横から見た動画（縦横同じ縮尺、実物の大きさ、10 m の目盛り、静かな水面の線、時刻）。計画 §6。
FLIP39 の ft_side_video.py と FLIP40 の f_video.py を元にした（PIL で描き、ffmpeg へ直接流す。コマの画像は残さない）。
使い方: py -3.10 g_video.py <run_id> <out_dir> [--crest_x=<造波板からの m>] [--crest_t=<s>] [--label=...]
  広い窓：造波板から 150〜750 m、t_b − 6 Tc（114.5 s）から終わりまで。300 m ずつ 2 段。
  頂の周りの窓：頂の位置 ±1 Lc（上の段）と ±0.4 Lc（下の段、同じ時刻の拡大）。頂の時刻 − 4 Tc から終わりまで。
  頂の位置と時刻は、巻き始めがあればその時刻と場所、なければ ana.json の N2 の時刻（最も険しくなった時刻）。
水の塗り方：断面の記録のある所と時刻（造波板から 321〜863 m、138.2 s から）は板の真ん中の水面の場（0 より小さい所が水）、
  それ以外は板の真ん中の一番上の水面の高さより下。高さは静かな水面（ana.json の still_level_offset_m）から。
出力: <out_dir>/<run_id>_wide.mp4・_wide_half.mp4・_crest.mp4・_crest_half.mp4
"""
import sys, os, json, math, subprocess
import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A

FF = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
W, H = 1920, 1080
BG = (247, 247, 244); WATER = (38, 86, 128); LINE = (150, 150, 150); TXT = (25, 25, 25); SUB = (95, 95, 92); LIN = (220, 120, 30)

# 印の字。既定は 10/10 に出した版（R2/video/R3_*.mp4、R2/R2_side_finest.mp4）と同じ。
# 字だけを直した _v2 は g_relabel_v2.py がこの辞書を差し替えて描く（描き方・窓・数は変えない）。
LAB = {"dk_x": "D&K の着水 584.5 m",      # 場所の印（D&K の表 3.1 の x_ob を 70 倍）
       "dk_t": "D&K の着水の時刻",        # 時間の帯の印（同じ表の t_ob を 70 倍）
       "touch_t": "着水"}                 # 時間の帯の印（この計算の「着水」の決まりを満たした時）


class Data:
    def __init__(self, rid):
        self.rid = rid
        self.P = A.plan(); self.C = A.comps_full(self.P)
        self.ana = json.load(open(os.path.join(A.ROOT, rid, "ana.json"), encoding="utf8"))
        self.cfg = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))
        self.D = A.load_hf(rid)
        self.S = A.load_sec(rid)
        self.off = self.ana["still_level_offset_m"]
        self.xp = self.cfg["parms"]["x_p"]
        self.mid = self.D["eta"].shape[1] // 2
        self.fidx = {int(f): i for i, f in enumerate(self.D["frames"])}
        self.sidx = {int(f): i for i, f in enumerate(self.S["frames"])} if self.S else {}

    def water_mask(self, f, xr_px, y_px):
        """xr_px（造波板からの m、列）と y_px（静かな水面からの m、行）の格子で、水なら True。"""
        i = self.fidx[f]
        eta = self.D["eta"][i, self.mid, :] - self.off
        xs = xr_px + self.xp
        et = np.interp(xs, self.D["x"], np.nan_to_num(eta, nan=-99.0))
        m = y_px[:, None] < et[None, :]
        j = self.sidx.get(f)
        if j is not None:
            me = self.S["meta"]
            gx = (xs - me["x0"]) / me["dx"]
            inside = (gx >= 0) & (gx <= me["nx"] - 1)
            if inside.any():
                gy = (y_px + self.off - me["y0"]) / me["dy"]
                GX, GY = np.meshgrid(gx[inside], gy)
                v = map_coordinates(self.S["sdf"][j].astype(np.float32), [GY.ravel(), GX.ravel()], order=1, mode="nearest").reshape(GY.shape)
                m[:, inside] = v < 0
        return m


def font(sz, b=False):
    return ImageFont.truetype(FONTB if b else FONT, sz)


def panel(im, dr, data, f, box, xr0, xr1, y0, y1, title, lin=None, marks=()):
    """box = (px0, py0, px1)：左上と右の端。縦横同じ縮尺で高さを決める。"""
    px0, py0, px1 = box
    s = (px1 - px0) / (xr1 - xr0)
    ph = int(round((y1 - y0) * s))
    xr_px = xr0 + (np.arange(px1 - px0) + 0.5) / s
    y_px = y1 - (np.arange(ph) + 0.5) / s
    m = data.water_mask(f, xr_px, y_px)
    a = np.empty((ph, px1 - px0, 3), np.uint8); a[:] = BG; a[m] = WATER
    im.paste(Image.fromarray(a), (px0, py0))
    X = lambda xr: px0 + (xr - xr0) * s
    Y = lambda y: py0 + (y1 - y) * s
    # 静かな水面（点線）
    for xx in np.arange(px0, px1, 14):
        dr.line([(xx, Y(0)), (min(xx + 7, px1), Y(0))], fill=LINE, width=1)
    # x の目盛り
    step = 50 if (xr1 - xr0) > 150 else 10
    for gx in np.arange(math.ceil(xr0 / step) * step, xr1 + 1e-6, step):
        dr.line([(X(gx), Y(y0)), (X(gx), Y(y0) + 6)], fill=SUB, width=1)
        dr.text((X(gx) - 14, Y(y0) + 7), "%d" % gx, fill=SUB, font=font(15))
    # 10 m の目盛り（左の端）
    bx = px0 + 14
    dr.line([(bx, Y(0)), (bx, Y(10))], fill=(200, 40, 40), width=4)
    for yy in (0, 10):
        dr.line([(bx - 6, Y(yy)), (bx + 6, Y(yy))], fill=(200, 40, 40), width=2)
    dr.text((bx + 9, Y(10) - 4), "10 m", fill=(200, 40, 40), font=font(17, True))
    if lin is not None:
        pts = [(X(xx), Y(yy)) for xx, yy in zip(*lin) if xr0 <= xx <= xr1 and y0 <= yy <= y1]
        if len(pts) > 1:
            dr.line(pts, fill=LIN, width=1)
    for q, (xm, lab) in enumerate(marks):
        if xr0 <= xm <= xr1:
            dr.line([(X(xm), Y(y1)), (X(xm), Y(y1) + 10 + 18 * q)], fill=(200, 40, 40), width=2)
            dr.text((X(xm) + 4, Y(y1) + 1 + 18 * q), lab, fill=(200, 40, 40), font=font(14))
    dr.rectangle([px0, py0, px1, py0 + ph], outline=(120, 120, 120))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    return ph


def tlabel(data, t, tref, refname):
    return "t = %.2f s（%s %+.2f s）" % (t, refname, t - tref)


def encode(path, fps_in):
    return subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(fps_in), "-i", "-",
                             "-vf", "fps=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)


def main():
    rid, outd = sys.argv[1], sys.argv[2]
    opt = dict(q[2:].split("=", 1) for q in sys.argv[3:] if q.startswith("--"))
    os.makedirs(outd, exist_ok=True)
    data = Data(rid)
    C = data.C; P = data.P
    Tc, Lc = C["Tc"], C["Lc"]
    on = data.ana.get("onset")
    n2 = (data.ana.get("N2_time") or {}).get("row")
    if "crest_t" in opt:
        tc, xc, refname = float(opt["crest_t"]), float(opt["crest_x"]), "指定の時刻から"
    elif on:
        tc, xc, refname = on["t"], on["xc_rel"], "巻き始めから"
    else:
        tc, xc, refname = n2["t"], n2["xc_rel"], "最も険しくなった時刻から"
    label = opt.get("label", "")
    t_end = P["tank"]["t_end"]
    dp = data.cfg["parms"]["dp"]; nbtxt = "粒子の帯 %.0f m" % (data.cfg["parms"]["band_vox"] * 2 * dp) if data.cfg["solver"]["donarrowband"] else "粒子の帯なし"
    head = "FLIP42 %s：Rapp & Melville の巻き波の組（S 0.352）を 70 倍、粒子 %.3g m（格子 %.3g m）、%s。力は重力だけ。%s" % (rid, dp, 2 * dp, nbtxt, label)
    sub = "縦横同じ縮尺。高さは静かな水面から（点線）。位置は造波板からの距離（m）。濃い青＝水（板の真ん中の断面）。"
    marks = [(C["xb"], "線形の焦点 592 m"), (P["full"]["xob_DK"], LAB["dk_x"])]
    tmk = [(P["full"]["tob_DK"], LAB["dk_t"]), (C["tb"], "線形の焦点の時刻")]
    if on:
        tmk.append((on["t"], "巻き始め"))
    tou = data.ana.get("touchdown")
    if tou:
        tmk.append((tou["t"], LAB["touch_t"]))
    only = opt.get("only", "")  # "crest" なら頂の周りの窓だけ、"wide" なら広い窓だけ（既定は両方）
    frames_all = [int(f) for f in data.D["frames"]]

    def tbar(dr, t, t0, t1):
        bx0, bx1, by = 60, W - 60, H - 46
        dr.rectangle([bx0, by, bx1, by + 8], fill=(225, 225, 222))
        dr.rectangle([bx0, by, bx0 + (bx1 - bx0) * (t - t0) / (t1 - t0), by + 8], fill=(60, 80, 110))
        for q, (tm, lab) in enumerate(sorted(tmk)):
            if t0 <= tm <= t1:
                xx = bx0 + (bx1 - bx0) * (tm - t0) / (t1 - t0)
                dr.line([(xx, by - 4), (xx, by + 14 + 14 * (q % 2))], fill=(200, 40, 40), width=2)
                dr.text((xx + 3, by + 12 + 14 * (q % 2)), lab, fill=(200, 40, 40), font=font(13))
        dr.text((bx0, by - 22), "%.1f s" % t0, fill=SUB, font=font(14)); dr.text((bx1 - 50, by - 22), "%.1f s" % t1, fill=SUB, font=font(14))

    # ---- 広い窓
    t0w = C["tb"] - 6 * Tc
    fw = [f for f in frames_all if (f - 1) / 24.0 >= t0w - 1e-9] if only != "crest" else []
    pw = [encode(os.path.join(outd, rid + "_wide.mp4"), 24), encode(os.path.join(outd, rid + "_wide_half.mp4"), 12)] if only != "crest" else []
    xl = np.arange(150, 751, 1.0)
    for f in fw:
        t = (f - 1) / 24.0
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        dr.text((40, 14), head, fill=TXT, font=font(21, True))
        dr.text((40, 48), sub + " 橙の細い線＝線形の重ね合わせ（参考）。", fill=SUB, font=font(16))
        dr.text((40, 76), tlabel(data, t, tc, refname) + "　広い窓（群が集まり、険しくなる所）", fill=TXT, font=font(22, True))
        el = A.eta_lin_xt(C, xl, [t])[:, 0]
        h1 = panel(im, dr, data, f, (40, 150, W - 40), 150, 450, -16, 22, "造波板から 150〜450 m", lin=(xl, el), marks=marks)
        panel(im, dr, data, f, (40, 150 + h1 + 80, W - 40), 450, 750, -16, 22, "造波板から 450〜750 m", lin=(xl, el), marks=marks)
        tbar(dr, t, t0w, t_end)
        b = im.tobytes()
        for p in pw:
            p.stdin.write(b)
    for p in pw:
        p.stdin.close(); p.wait()
    # ---- 頂の周りの窓
    t0c = max(tc - 4 * Tc, (data.S["frames"][0] - 1) / 24.0 if data.S else 0)
    fc = [f for f in frames_all if (f - 1) / 24.0 >= t0c - 1e-9] if only != "wide" else []
    pc = [encode(os.path.join(outd, rid + "_crest.mp4"), 24), encode(os.path.join(outd, rid + "_crest_half.mp4"), 12)] if only != "wide" else []
    for f in fc:
        t = (f - 1) / 24.0
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        dr.text((40, 14), head, fill=TXT, font=font(21, True))
        dr.text((40, 48), sub, fill=SUB, font=font(16))
        dr.text((40, 76), tlabel(data, t, tc, refname) + "　頂の周りの窓（中心 %.0f m）" % xc, fill=TXT, font=font(22, True))
        h1 = panel(im, dr, data, f, (40, 150, W - 40), xc - Lc, xc + Lc, -18, 20, "頂の位置 ±1 波長（±%.0f m）" % Lc, marks=marks)
        panel(im, dr, data, f, (40, 150 + h1 + 70, W - 40), xc - 0.4 * Lc, xc + 0.4 * Lc, -12, 16, "拡大：頂の位置 ±0.4 波長（±%.0f m）" % (0.4 * Lc), marks=marks)
        tbar(dr, t, t0c, t_end)
        b = im.tobytes()
        for p in pc:
            p.stdin.write(b)
    for p in pc:
        p.stdin.close(); p.wait()
    print("saved", outd, rid, "wide frames", len(fw), "crest frames", len(fc), "tc", tc, "xc", xc)


if __name__ == "__main__":
    main()
