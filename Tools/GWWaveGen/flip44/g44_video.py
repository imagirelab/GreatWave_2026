# -*- coding: utf-8 -*-
"""FLIP44：横から見た動画（縦横同じ縮尺、実物の大きさ、10 m の目盛り、静かな水面の線、海底（礁）、時刻）。計画 §2・§5。
FLIP42 の g_video.py（変えていない）を写して直した。同じにした所：PIL で描いて ffmpeg へ直接流す（コマの画像は残さない）、
  水の塗り方（断面の記録のある所と時刻は板の真ん中の水面の場、ほかは一番上の水面の高さより下）、高さは静かな水面から、10 m の目盛り。
変えた所：海底（礁）を灰色で塗る。広い窓は断面の記録の範囲を 2 段に分ける。印は礁の前の足・上の縁・上の後ろの縁・後ろの足と、
  入口の狙いの場所。頂の周りの窓は ana.json の主な巻き波の巻き始め（なければ使わない）。線形の重ね合わせの線は描かない（礁の上では線形の式が違うため）。
使い方: py -3.10 g44_video.py <run_id> <out_dir> [--root=runs|smoke] [--only=wide|crest] [--t0=<s>] [--t1=<s>] [--crest_t=<s> --crest_x=<造波板から m>] [--label=...]
出力: <out_dir>/<run_id>_wide.mp4・_crest.mp4（24 コマ/s、実時間）
"""
import sys, os, json, math, subprocess
import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_analyze as A

FF = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
W, H = 1920, 1080
BG = (247, 247, 244); WATER = (38, 86, 128); BED = (150, 140, 120); LINE = (150, 150, 150); TXT = (25, 25, 25); SUB = (95, 95, 92)


class Data:
    def __init__(self, rid, root):
        self.rid = rid
        rd = A.run_dir(rid, root)
        self.cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        ap = os.path.join(rd, "ana.json")
        self.ana = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
        self.D = A.load_hf(rd)
        self.SR = A.SecReader(rd)
        self.xp = self.cfg["parms"]["x_p"]
        # ana.json の値（計画 N1。風の計算は形の本番の値）。なければ同じ決まりで出す。以前は既定の値の式が先に評価され、
        # 途中保存から始めた計算では still_level が止まった（2026-10-12 確かめ F1 の直し）
        self.off = self.ana["still_level_offset_m"] if "still_level_offset_m" in self.ana else A.still_offset(self.cfg, self.D, root)[0]
        self.mid = self.D["eta"].shape[1] // 2
        self.fidx = {int(f): i for i, f in enumerate(self.D["frames"])}

    def water_mask(self, f, xr_px, y_px):
        i = self.fidx[f]
        eta = self.D["eta"][i, self.mid, :] - self.off
        xs = xr_px + self.xp
        et = np.interp(xs, self.D["x"], np.nan_to_num(eta, nan=-99.0))
        m = y_px[:, None] < et[None, :]
        if f in self.SR.best:
            me = self.SR.meta
            gx = (xs - me["x0"]) / me["dx"]
            inside = (gx >= 0) & (gx <= me["nx"] - 1)
            if inside.any():
                gy = (y_px + self.off - me["y0"]) / me["dy"]
                GX, GY = np.meshgrid(gx[inside], gy)
                v = map_coordinates(self.SR.get(f), [GY.ravel(), GX.ravel()], order=1, mode="nearest").reshape(GY.shape)
                m[:, inside] = v < 0
        bed = A.bed_y(self.cfg["parms"], xs) - self.off
        return m, y_px[:, None] < bed[None, :]


def font(sz, b=False):
    return ImageFont.truetype(FONTB if b else FONT, sz)


def panel(im, dr, data, f, box, xr0, xr1, y0, y1, title, marks=()):
    px0, py0, px1 = box
    s = (px1 - px0) / (xr1 - xr0)
    ph = int(round((y1 - y0) * s))
    xr_px = xr0 + (np.arange(px1 - px0) + 0.5) / s
    y_px = y1 - (np.arange(ph) + 0.5) / s
    m, bed = data.water_mask(f, xr_px, y_px)
    a = np.empty((ph, px1 - px0, 3), np.uint8); a[:] = BG; a[m] = WATER; a[bed] = BED
    im.paste(Image.fromarray(a), (px0, py0))
    X = lambda xr: px0 + (xr - xr0) * s
    Y = lambda y: py0 + (y1 - y) * s
    for xx in np.arange(px0, px1, 14):
        dr.line([(xx, Y(0)), (min(xx + 7, px1), Y(0))], fill=LINE, width=1)
    step = 50 if (xr1 - xr0) > 150 else 10
    for gx in np.arange(math.ceil(xr0 / step) * step, xr1 + 1e-6, step):
        dr.line([(X(gx), Y(y0)), (X(gx), Y(y0) + 6)], fill=SUB, width=1)
        dr.text((X(gx) - 14, Y(y0) + 7), "%d" % gx, fill=SUB, font=font(15))
    bx = px0 + 14
    dr.line([(bx, Y(0)), (bx, Y(10))], fill=(200, 40, 40), width=4)
    for yy in (0, 10):
        dr.line([(bx - 6, Y(yy)), (bx + 6, Y(yy))], fill=(200, 40, 40), width=2)
    dr.text((bx + 9, Y(10) - 4), "10 m", fill=(200, 40, 40), font=font(17, True))
    for q, (xm, lab) in enumerate(marks):
        if xr0 <= xm <= xr1:
            dr.line([(X(xm), Y(y1)), (X(xm), Y(y1) + 10 + 18 * (q % 3))], fill=(200, 40, 40), width=2)
            dr.text((X(xm) + 4, Y(y1) + 1 + 18 * (q % 3)), lab, fill=(200, 40, 40), font=font(14))
    dr.rectangle([px0, py0, px1, py0 + ph], outline=(120, 120, 120))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    return ph


def encode(path, fps_in):
    return subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(fps_in), "-i", "-",
                             "-vf", "fps=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)


def main():
    rid, outd = sys.argv[1], sys.argv[2]
    opt = dict(q[2:].split("=", 1) for q in sys.argv[3:] if q.startswith("--"))
    root = opt.get("root", "runs")
    os.makedirs(outd, exist_ok=True)
    data = Data(rid, root)
    P = A.plan(); Lc = P["tank"]["Lc"]
    p = data.cfg["parms"]; dp = p["dp"]
    reef = float(p.get("reef_on", 0)) > 0.5
    q = float(p.get("wind_q", 0)) if float(p.get("wind_on", 0)) > 0.5 else 0.0
    head = "FLIP44 %s：入口 %s、粒子 %.4g m（格子 %.4g m）、%s。%s %s" % (
        rid, data.cfg["inlet"]["name"], dp, 2 * dp, "礁あり" if reef else "平らな海底（水深 42 m）",
        ("力は重力と風の圧力（q %.0f Pa）" % q) if q > 0 else "力は重力だけ", opt.get("label", ""))
    sub = "縦横同じ縮尺。高さは静かな水面から（点線）。位置は造波板からの距離（m）。濃い青＝水（板の真ん中の断面）、灰色＝海底。"
    marks = []
    if reef:
        n = p["rf_slope_n"]; d = p["h0"] - p["rf_h_top"]
        marks = [(p["rf_foot"], "礁の前の足"), (p["rf_foot"] + n * d, "礁の上の縁"), (p["rf_top_end"], "上の後ろの縁"), (p["rf_top_end"] + n * d, "礁の後ろの足")]
    if data.cfg["case"].get("aim_x_from_paddle") and not data.cfg["case"].get("reef_shift"):
        marks.append((data.cfg["case"]["aim_x_from_paddle"], "狙い %.0f m" % data.cfg["case"]["aim_x_from_paddle"]))
    on = data.ana.get("onset"); tou = data.ana.get("touchdown")
    if "crest_t" in opt:      # 頂の周りの窓の中心を指定する（主な巻き波の範囲 300〜800 m の外の試しのため）
        on = dict(t=float(opt["crest_t"]), xc_rel=float(opt["crest_x"])); tou = None
    frames_all = [int(f) for f in data.D["frames"]]
    t_end = (frames_all[-1] - 1) / 24.0
    sx0 = data.cfg["sec"]["x0"] - data.xp; sx1 = data.cfg["sec"]["x1"] - data.xp
    t0w = float(opt.get("t0", max(0.0, min(data.cfg["sec"]["t0"], t_end))))
    t1w = float(opt.get("t1", t_end))
    tmk = []
    if on:
        tmk.append((on["t"], "巻き始め"))
    if tou:
        tmk.append((tou["t"], "着水"))

    def tbar(dr, t, t0, t1):
        bx0, bx1, by = 60, W - 60, H - 46
        dr.rectangle([bx0, by, bx1, by + 8], fill=(225, 225, 222))
        dr.rectangle([bx0, by, bx0 + (bx1 - bx0) * (t - t0) / max(t1 - t0, 1e-6), by + 8], fill=(60, 80, 110))
        for k, (tm, lab) in enumerate(sorted(tmk)):
            if t0 <= tm <= t1:
                xx = bx0 + (bx1 - bx0) * (tm - t0) / (t1 - t0)
                dr.line([(xx, by - 4), (xx, by + 14 + 14 * (k % 2))], fill=(200, 40, 40), width=2)
                dr.text((xx + 3, by + 12 + 14 * (k % 2)), lab, fill=(200, 40, 40), font=font(13))
        dr.text((bx0, by - 22), "%.1f s" % t0, fill=SUB, font=font(14)); dr.text((bx1 - 50, by - 22), "%.1f s" % t1, fill=SUB, font=font(14))
    only = opt.get("only", "")
    if only != "crest":
        fw = [f for f in frames_all if t0w - 1e-9 <= (f - 1) / 24.0 <= t1w + 1e-9]
        pw = encode(os.path.join(outd, rid + "_wide.mp4"), 24)
        xm = 0.5 * (sx0 + sx1)
        for f in fw:
            t = (f - 1) / 24.0
            im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
            dr.text((40, 14), head, fill=TXT, font=font(21, True))
            dr.text((40, 48), sub, fill=SUB, font=font(16))
            dr.text((40, 76), "t = %.2f s　広い窓" % t, fill=TXT, font=font(22, True))
            h1 = panel(im, dr, data, f, (40, 150, W - 40), sx0, xm, -16, 22, "造波板から %.0f〜%.0f m" % (sx0, xm), marks=marks)
            panel(im, dr, data, f, (40, 150 + h1 + 80, W - 40), xm, sx1, -16, 22, "造波板から %.0f〜%.0f m" % (xm, sx1), marks=marks)
            tbar(dr, t, t0w, t1w)
            pw.stdin.write(im.tobytes())
        pw.stdin.close(); pw.wait()
        print("wide frames", len(fw))
    if only != "wide" and on:
        tc, xc = on["t"], on["xc_rel"]
        t0c = max(tc - 4 * P["tank"]["Tc"], t0w)
        fc = [f for f in frames_all if t0c - 1e-9 <= (f - 1) / 24.0 <= t1w + 1e-9]
        pc = encode(os.path.join(outd, rid + "_crest.mp4"), 24)
        for f in fc:
            t = (f - 1) / 24.0
            im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
            dr.text((40, 14), head, fill=TXT, font=font(21, True))
            dr.text((40, 48), sub, fill=SUB, font=font(16))
            dr.text((40, 76), "t = %.2f s（巻き始めから %+.2f s）　頂の周りの窓（中心 %.0f m）" % (t, t - tc, xc), fill=TXT, font=font(22, True))
            h1 = panel(im, dr, data, f, (40, 150, W - 40), xc - Lc, xc + Lc, -18, 20, "頂の位置 ±1 波長（±%.0f m）" % Lc, marks=marks)
            panel(im, dr, data, f, (40, 150 + h1 + 70, W - 40), xc - 0.4 * Lc, xc + 0.4 * Lc, -12, 16, "拡大：頂の位置 ±0.4 波長（±%.0f m）" % (0.4 * Lc), marks=marks)
            tbar(dr, t, t0c, t1w)
            pc.stdin.write(im.tobytes())
        pc.stdin.close(); pc.wait()
        print("crest frames", len(fc))
    print("saved", outd, rid)


if __name__ == "__main__":
    main()
