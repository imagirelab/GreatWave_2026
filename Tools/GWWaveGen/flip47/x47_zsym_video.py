# -*- coding: utf-8 -*-
"""FLIP47：板の層の差の試しの動画（py -3.10 -B。numpy・scipy・PIL・skimage と ffmpeg）。2026-10-13 板の層の差を調べる役（Claude）。
g47_video.py（動画の役）がまだない時の、簡単な横の断面 + 頂を追う拡大の動画。1 本か 2 本の計算を上下・左右に並べる。
  上：領域の全部の横の断面（縦横同じ尺、10 m の物差し、海底は茶、水は板の真ん中に近い層 z −0.25 m）
  下：頂を追う拡大（縦横同じ尺、10 m の物差し）。水の塗りは板の全部の層の平均の場、線は層ごと（青 −z の壁の側 → 赤 +z の壁の側）。
      2D なら層の線は重なる。各計算の最も近いコマ（主の層で score3 最小）では原画の輪郭（黒、η_c と頂にそろえた）を重ね、1.5 s 止める。
使い方：py -3.10 -B x47_zsym_video.py --out <mp4> --t0 8 <run_id>[=<見出し>] [<run_id>[=<見出し>]]
"""
import os, sys, json, glob, argparse, subprocess, math
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC

B47 = GC.B47
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"      # flip45 g45_common.FFMPEG と同じ
FONT = "C:/Windows/Fonts/YuGothM.ttc"; FONTB = "C:/Windows/Fonts/YuGothB.ttc"
W, H = 1280, 720
SKY = (246, 248, 252); WATER = (120, 170, 225); WATER2 = (168, 200, 236); BED = (150, 115, 80); TXT = (25, 25, 25); SUB = (90, 90, 90)


def font(sz, b=False):
    return ImageFont.truetype(FONTB if b else FONT, sz)


class Run:
    def __init__(self, rid, label):
        self.rid = rid; self.label = label
        rd = B47 + "/runs/" + rid
        self.cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
        self.bed = GC.bed_points(self.cfg["bed"])
        fr, S, SZ, T, ME = [], [], [], [], []
        for p in sorted(glob.glob(rd + "/sec_c*_b*.npz")):
            d = np.load(p)
            m = json.loads(str(d["meta"]))
            if "sdfz" in d.files:
                SZ.append(d["sdfz"])
            else:                                            # 層ごとの記録のない計算（E1a など）は板の真ん中に近い層だけ
                SZ.append(d["sdf"][:, None]); m["allz_z"] = [m.get("z", -0.25)]
            fr.append(d["frames"]); T.append(d["t"]); ME.append(m)
        shp = [z.shape[1:] for z in SZ]
        main = max(set(shp), key=shp.count)                 # 1 コマ目（初めの VDB の格子）は形が違うので外す
        keep = [k for k in range(len(SZ)) if SZ[k].shape[1:] == main]
        fr = [fr[k] for k in keep]; SZ = [SZ[k] for k in keep]; T = [T[k] for k in keep]; self.meta = ME[keep[-1]]
        self.frames = np.concatenate(fr); self.t = np.concatenate(T); self.sdfz = np.concatenate(SZ)
        _, ui = np.unique(self.frames, return_index=True)
        self.frames = self.frames[ui]; self.t = self.t[ui]; self.sdfz = self.sdfz[ui]
        m = self.meta
        self.xs = m["x0"] + m["dx"] * np.arange(m["nx"]); self.ys = m["y0"] + m["dy"] * np.arange(m["ny"])
        self.zs = m.get("allz_z")
        self.imain = int(np.argmin(np.abs(np.array(self.zs) + 0.25)))
        self.nz = self.sdfz.shape[1]
        # 頂を追う窓の真ん中：4 層の平均の場の一番上の水面の最大の x を、時刻でならす
        cxs = []
        for i in range(len(self.frames)):
            a = self.sdfz[i].astype(np.float32).mean(0)
            wet = a < 0
            jt = np.where(wet.any(0), wet.shape[0] - 1 - np.argmax(wet[::-1], 0), 0)
            cxs.append(self.xs[int(np.argmax(jt))])
        cxs = np.array(cxs, float)
        cxs = np.maximum.accumulate(cxs)
        self.cx = ndi.uniform_filter1d(cxs, 13, mode="nearest")
        # 最も近いコマ（x47_zsym ana の主の層、無ければ g47_scan ana の主）と、その x_c・η_c
        self.best = None
        zj = rd + "/zsym/zsym.json"
        if os.path.exists(zj):
            o = json.load(open(zj, encoding="utf8"))
            b = o.get("main_best3") or {}
            if b.get("frame"):
                a = json.load(open(rd + "/zsym/z%d/g47_ana.json" % o["main_layer"], encoding="utf8"))
                w = next((x for x in a.get("fine") or [] if x["frame"] == b["frame"]), None)
                if w:
                    self.best = dict(frame=b["frame"], x_c=w["xc"], eta_c=w["eta"], score3=b.get("score3"))
            self.onset = (o.get("main_onset") or {}).get("frame")
            self.td = (o.get("main_touchdown") or {}).get("frame")
        else:
            self.onset = self.td = None

    def bed_y(self, x):
        return GC.bed_y(np.asarray(x, float), self.bed)


def print_outline():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import g47_scan as SC
    PL, _ = SC.print_lines()
    return PL


def sample(S, xs, ys, X, Y):
    fx = (X - xs[0]) / (xs[1] - xs[0]); fy = (Y - ys[0]) / (ys[1] - ys[0])
    FY, FX = np.meshgrid(fy, fx, indexing="ij")
    return ndi.map_coordinates(S.astype(np.float32), [FY, FX], order=1, mode="nearest")


def draw_side(dr, img, R, i, box, x0, x1, y0, y1, title):
    bx0, by0, bw, bh = box
    sc = bw / (x1 - x0)
    X = x0 + (np.arange(bw) + 0.5) / sc
    Y = y1 - (np.arange(bh) + 0.5) / sc
    S = sample(R.sdfz[i, R.imain], R.xs, R.ys, X, Y)
    rgb = np.empty((bh, bw, 3), np.uint8); rgb[:] = SKY
    rgb[S < 0] = WATER
    bedy = R.bed_y(X)
    rgb[(Y[:, None] < bedy[None, :] + 0.6) & (S < 0.6)] = WATER      # 海底のすぐ上の粒子を置かない薄い所（bed_gap）は水で塗る
    rgb[Y[:, None] < bedy[None, :]] = BED
    img.paste(Image.fromarray(rgb), (bx0, by0))
    dr.rectangle([bx0, by0, bx0 + bw, by0 + bh], outline=(150, 150, 150))
    # 10 m の物差し
    xb = bx0 + 12; yb = by0 + bh - 10
    dr.line([xb, yb, xb + 10 * sc, yb], fill=(0, 0, 0), width=3)
    dr.text((xb + 10 * sc + 6, yb - 10), "10 m", fill=TXT, font=font(12, True))
    # 窓の場所
    return sc


def draw_zoom(dr, img, R, i, box, xc, PL, show_print, nlay_label=True):
    bx0, by0, bw, bh = box
    sc = 12.0                       # px / m
    xw = bw / sc; x0 = xc - 0.62 * xw; x1 = x0 + xw
    yb0 = -7.0; yt = yb0 + bh / sc
    X = x0 + (np.arange(bw) + 0.5) / sc
    Y = yt - (np.arange(bh) + 0.5) / sc
    Sm = sample(R.sdfz[i].astype(np.float32).mean(0), R.xs, R.ys, X, Y)
    rgb = np.empty((bh, bw, 3), np.uint8); rgb[:] = SKY
    rgb[Sm < 0] = WATER2
    bedy = R.bed_y(X)
    rgb[(Y[:, None] < bedy[None, :] + 0.6) & (Sm < 0.6)] = WATER2
    rgb[Y[:, None] < bedy[None, :]] = BED
    img.paste(Image.fromarray(rgb), (bx0, by0))
    # 層ごとの水面の線（記録の格子 0.5 m の等高線）
    ix = np.where((R.xs >= x0 - 1) & (R.xs <= x1 + 1))[0]; iy = np.where((R.ys >= yb0 - 1) & (R.ys <= yt + 1))[0]
    cols = [tuple(int(c) for c in (np.array([30, 80, 220]) * (1 - s) + np.array([210, 30, 30]) * s)) for s in np.linspace(0, 1, R.nz)]
    tr = lambda x, y: (bx0 + (x - x0) * sc, by0 + (yt - y) * sc)
    if len(ix) > 2 and len(iy) > 2:
        for k in range(R.nz):
            S = R.sdfz[i, k][np.ix_(iy, ix)].astype(np.float32)
            bb = R.bed_y(R.xs[ix])
            S[R.ys[iy][:, None] < bb[None, :] + 0.25] = -1.0       # 海底の中は水として線を引かない
            for c in measure.find_contours(S, 0.0):
                P = [tr(R.xs[ix[0]] + q[1] * 0.5, R.ys[iy[0]] + q[0] * 0.5) for q in c]
                P = [p for p in P if bx0 <= p[0] <= bx0 + bw and by0 <= p[1] <= by0 + bh]
                if len(P) > 1:
                    dr.line(P, fill=cols[k], width=2)
    # 静かな水面
    yy = tr(0, 0.0)[1]
    dr.line([bx0, yy, bx0 + bw, yy], fill=(110, 110, 110), width=1)
    if show_print and R.best:
        for L in PL:
            P = [tr(R.best["x_c"] + q[0] * R.best["eta_c"], q[1] * R.best["eta_c"]) for q in L]
            P = [p for p in P if bx0 - 2 <= p[0] <= bx0 + bw + 2 and by0 - 2 <= p[1] <= by0 + bh + 2]
            if len(P) > 1:
                dr.line(P, fill=(0, 0, 0), width=3)
    dr.rectangle([bx0, by0, bx0 + bw, by0 + bh], outline=(150, 150, 150))
    xb = bx0 + 14; ybb = by0 + bh - 14
    dr.line([xb, ybb, xb + 10 * sc, ybb], fill=(0, 0, 0), width=4)
    dr.text((xb + 10 * sc + 8, ybb - 11), "10 m", fill=TXT, font=font(14, True))
    return x0, x1, cols


def render(runs, out, t0=8.0, hold_s=1.5, fps=24, noprint=False, note=""):
    PL = print_outline()
    if noprint:
        for R in runs:
            R.best = None
    R0 = runs[0]
    cfg = R0.cfg
    s = (cfg.get("case") or {}).get("targets_scan") or {}
    bed_ja = s.get("name_ja") or ("E1a（Feddersen ら 2024 の海底：勾配 0.0693 で水深 7.05 m の棚へ）" if cfg.get("kind") == "E1a" else "")
    head = "FLIP47 %s：%s｜GN の孤立波 a0/h0 %.1f・h0 19 m｜粒子 0.25 m（格子 0.5 m）｜重力だけ" % (
        cfg.get("scan_id", "E1a 短い領域"), bed_ja, (cfg.get("solitary") or {}).get("a_over_h", 0.6))
    n = len(runs)
    common = sorted(set.intersection(*[set(int(f) for f in R.frames) for R in runs]))
    common = [f for f in common if runs[0].t[list(runs[0].frames).index(f)] >= t0 - 1e-9]
    x0d, x1d = float(R0.xs[0] - 0.25), float(R0.xs[-1] + 0.25)
    y0d, y1d = -20.0, 16.0
    side_w = W - 40
    side_h = int(round((y1d - y0d) * side_w / (x1d - x0d)))
    zoom_w = (W - 40 - (n - 1) * 20) // n
    zoom_h = 330
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", out]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nfr = 0
    for f in common:
        holds = [1]
        is_best = [R.best is not None and R.best["frame"] == f for R in runs]
        if any(is_best):
            holds = [1] + [2] * int(hold_s * fps)
        for h in holds:
            img = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(img)
            i0 = list(R0.frames).index(f)
            t = float(R0.t[i0])
            fs_ = 16
            while fs_ > 11 and dr.textlength(head, font=font(fs_, True)) > W - 230:
                fs_ -= 1
            dr.text((20, 8), head, fill=TXT, font=font(fs_, True))
            dr.text((W - 190, 8), "t = %5.2f s" % t, fill=(180, 30, 30), font=font(20, True))
            y = 40
            for R in runs:
                i = list(R.frames).index(f)
                dr.text((20, y), "全体の横の断面（縦横同じ尺）：%s　海底：茶、水：板の層 z −0.25 m" % R.label, fill=SUB, font=font(13))
                sc = draw_side(dr, img, R, i, (20, y + 18, side_w, side_h), x0d, x1d, y0d, y1d, R.label)
                xc = float(R.cx[i])
                xa = 20 + (xc - 0.62 * zoom_w / 12.0 - x0d) * sc; xb_ = xa + zoom_w / 12.0 * sc
                dr.rectangle([xa, y + 18, xb_, y + 18 + side_h], outline=(200, 40, 40), width=2)
                y += side_h + 26
            y += 6
            for k, R in enumerate(runs):
                i = list(R.frames).index(f)
                bx = 20 + k * (zoom_w + 20)
                show = (h == 2 and is_best[k])
                ttl = "%s：頂を追う拡大（縦横同じ尺）" % R.label
                dr.text((bx, y), ttl, fill=TXT, font=font(14, True))
                x0z, x1z, cols = draw_zoom(dr, img, R, i, (bx, y + 22, zoom_w, zoom_h), float(R.cx[i]), PL, show)
                ly = y + 22 + zoom_h + 6
                dr.text((bx, ly), "線：板の層ごとの水面", fill=SUB, font=font(12))
                stp = min(64, (zoom_w - 140) // max(R.nz, 1))
                for kk in range(R.nz):
                    dr.line([bx + 130 + kk * stp, ly + 9, bx + 146 + kk * stp, ly + 9], fill=cols[kk], width=3)
                    dr.text((bx + 149 + kk * stp, ly), "%+.2f" % R.zs[kk], fill=cols[kk], font=font(11, True))
                nt = "塗り：層の平均の場"
                if R.onset and f >= R.onset:
                    nt += "　巻き始め コマ %d 以後" % R.onset
                if R.td and f >= R.td:
                    nt += "　着水 コマ %d 以後" % R.td
                dr.text((bx, ly + 18), nt, fill=SUB, font=font(12))
                if show:
                    dr.text((bx + 10, y + 28), "黒：原画の輪郭（最も近いコマ %d、score3 %.2f。η_c %.1f m と頂にそろえた）" % (
                        f, R.best["score3"] or 0, R.best["eta_c"]), fill=(0, 0, 0), font=font(13, True))
            if note:
                dr.text((20, H - 24), note, fill=(150, 30, 30), font=font(13, True))
            pr.stdin.write(np.asarray(img, np.uint8).tobytes())
            nfr += 1
    pr.stdin.close(); pr.wait()
    return out, nfr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--t0", type=float, default=8.0)
    ap.add_argument("--noprint", action="store_true", help="原画の輪郭を重ねない（形を原画と比べない試し）")
    ap.add_argument("--note", default="", help="下の端に書く 1 行")
    a = ap.parse_args()
    rs = []
    for s in a.runs:
        rid, _, lab = s.partition("=")
        rs.append(Run(rid, lab or rid))
    o, nf = render(rs, a.out, t0=a.t0, noprint=a.noprint, note=a.note)
    print("video", o, "frames", nf, "MB %.1f" % (os.path.getsize(o) / 1e6))
