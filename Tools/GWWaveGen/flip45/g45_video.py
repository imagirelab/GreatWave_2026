# -*- coding: utf-8 -*-
"""FLIP45：3D の計算の動画（py -3.10、PIL・numpy・ffmpeg。計画 plan_ja.md §6.9・§10.1）。FLIP44 の g44_video.py（変えていない）の描き方を写して 3D に直した。
1 コマに 3 つの図：
  上：横から（y = 0 の断面、記録 R2 の水面の場。縦横同じ縮尺、高さは静かな水面から、10 m の目盛り）。
  左下：平面の高さの図（記録 R1 の一番上の水面の高さ − 静かな水面のずれ。y = 0 で写して全幅で描く。色は −8〜+8 m）。
  右下：斜め上から（R1 の y = 0〜(横の帯の内の縁) の断面を 6 m ごとに奥へずらして重ねた図。縦は 2 倍に伸ばさず、x・高さは同じ縮尺、10 m の目盛り）。
PIL で描いて ffmpeg へ直接流す（コマの画像は残さない）。粒子 0.5 m の計算には「粗い」と書く。
使い方: py -3.10 g45_video.py <run_id> <out_dir> [--root=runs|smoke] [--t0=<s>] [--t1=<s>] [--label=...] [--still=<s>]（1 枚の PNG だけ）
出力: <out_dir>/<run_id>_3view.mp4（24 コマ/s、実時間）
"""
import sys, os, json, math, subprocess
import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_analyze as GA

FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
W, H = 1920, 1080
BG = (247, 247, 244); WATER = (38, 86, 128); LINE = (150, 150, 150); TXT = (25, 25, 25); SUB = (95, 95, 92); RED = (200, 40, 40)


def font(sz, b=False):
    return ImageFont.truetype(FONTB if b else FONT, sz)


def cmap(v, lo=-8.0, hi=8.0):
    """高さ → 色（低い所は濃い青、0 は薄い灰、高い所は白から黄）。"""
    t = np.clip((v - lo) / (hi - lo), 0, 1)
    c0 = np.array([20, 50, 110]); c1 = np.array([225, 230, 235]); c2 = np.array([250, 210, 60])
    out = np.where(t[..., None] < 0.5, c0 + (c1 - c0) * (t[..., None] / 0.5), c1 + (c2 - c1) * ((t[..., None] - 0.5) / 0.5))
    return np.nan_to_num(out, nan=200).astype(np.uint8)


class Data:
    def __init__(self, rid, root):
        self.rd = GA.run_dir(rid, root)
        self.cfg = json.load(open(os.path.join(self.rd, "cfg.json"), encoding="utf8"))
        ap = os.path.join(self.rd, "ana.json")
        self.ana = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
        self.R1 = GA.Reader(self.rd, "hf", "eta"); self.R2 = GA.Reader(self.rd, "r2", "sdf")
        if "still_level_offset_m" in self.ana:
            self.off = self.ana["still_level_offset_m"]
        else:
            self.off = GA.still_offset(self.rd, self.cfg, GA.records(self.rd), self.R1)[0]
        self.frames = [f for f in self.R1.frames if f in set(self.R2.frames)] or self.R1.frames


def side(im, dr, data, f, box, xr0, xr1, y0, y1, title):
    px0, py0, px1 = box
    s = (px1 - px0) / (xr1 - xr0)
    ph = int(round((y1 - y0) * s))
    xs = xr0 + (np.arange(px1 - px0) + 0.5) / s
    ys = y1 - (np.arange(ph) + 0.5) / s
    a = np.empty((ph, px1 - px0, 3), np.uint8); a[:] = BG
    if f in data.R2.b:
        S, m, t = data.R2.get(f)
        gx = (xs - m["x0"]) / m["dx"]; gy = (ys + data.off - m["y0"]) / m["dy"]
        GX, GY = np.meshgrid(gx, gy)
        v = map_coordinates(S.astype(np.float32), [GY.ravel(), GX.ravel()], order=1, mode="nearest").reshape(GY.shape)
        a[v < 0] = WATER
    im.paste(Image.fromarray(a), (px0, py0))
    X = lambda xr: px0 + (xr - xr0) * s
    Y = lambda y: py0 + (y1 - y) * s
    for xx in np.arange(px0, px1, 14):
        dr.line([(xx, Y(0)), (min(xx + 7, px1), Y(0))], fill=LINE, width=1)
    for gx in np.arange(math.ceil(xr0 / 50) * 50, xr1 + 1e-6, 50):
        dr.line([(X(gx), Y(y0)), (X(gx), Y(y0) + 6)], fill=SUB, width=1)
        dr.text((X(gx) - 14, Y(y0) + 7), "%d" % gx, fill=SUB, font=font(15))
    bx = px0 + 14
    dr.line([(bx, Y(0)), (bx, Y(10))], fill=RED, width=4)
    dr.text((bx + 9, Y(10) - 4), "10 m", fill=RED, font=font(17, True))
    dr.rectangle([px0, py0, px1, py0 + ph], outline=(120, 120, 120))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    return ph


def plan_view(im, dr, data, f, box, title):
    px0, py0, px1, py1 = box
    e, m, t = data.R1.get(f)
    E = e - data.off
    full = np.concatenate([E[::-1], E], 0)                      # 横 −W..W（y = 0 で写す）
    img = Image.fromarray(cmap(full[::-1]))                     # 上が +y
    Lx_ = m["dx"] * m["res"][0]; Wf = 2 * m["dz"] * m["res"][2]
    sc = min((px1 - px0) / Lx_, (py1 - py0) / Wf)               # 縦横同じ縮尺
    px1 = px0 + int(round(Lx_ * sc)); py1 = py0 + max(2, int(round(Wf * sc)))
    img = img.resize((px1 - px0, py1 - py0), Image.NEAREST)
    im.paste(img, (px0, py0))
    dr.rectangle([px0, py0, px1, py1], outline=(120, 120, 120))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    Lx = m["dx"] * m["res"][0]
    s = (px1 - px0) / Lx
    dr.line([(px0 + 10, py1 - 12), (px0 + 10 + 10 * s, py1 - 12)], fill=RED, width=4)
    dr.text((px0 + 14 + 10 * s, py1 - 26), "10 m", fill=RED, font=font(15, True))
    ymid = (py0 + py1) / 2
    for xx in np.arange(px0, px1, 12):
        dr.line([(xx, ymid), (min(xx + 6, px1), ymid)], fill=(240, 240, 240), width=1)


def oblique(im, dr, data, f, box, title, ymax, dy=6.0, x_lo=None, x_hi=None):
    px0, py0, px1, py1 = box
    e, m, t = data.R1.get(f)
    xs = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs = m["z0"] + m["dz"] * np.arange(m["res"][2])
    x_lo = xs[0] if x_lo is None else x_lo; x_hi = xs[-1] if x_hi is None else x_hi
    sel = (xs >= x_lo) & (xs <= x_hi)
    nlines = int(ymax // dy) + 1
    s = (px1 - px0) / ((x_hi - x_lo) + ymax * 0.6)              # x と高さは同じ縮尺（縦を伸ばさない）
    dep = max(0.2, (py1 - py0 - 90) / max(ymax * s, 1e-6))      # 奥へ 1 m で上へずらす割合（見る角だけ。高さの縮尺は変えない）
    base = py1 - 30
    for k in reversed(range(nlines)):
        y = k * dy
        iz = int(np.argmin(np.abs(zs - y)))
        prof = e[iz, sel] - data.off
        ox = px0 + y * 0.6 * s; oy = base - y * dep * s
        pts = [(ox + (x - x_lo) * s, oy - p * s) for x, p in zip(xs[sel], np.nan_to_num(prof, nan=0.0))]
        poly = pts + [(pts[-1][0], oy + 20 * s), (pts[0][0], oy + 20 * s)]
        shade = int(60 + 140 * (k / max(nlines - 1, 1)))
        dr.polygon(poly, fill=(30, 70 + shade // 3, 120 + shade // 2), outline=(230, 235, 240))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    dr.line([(px1 - 30, base), (px1 - 30, base - 10 * s)], fill=RED, width=4)
    dr.text((px1 - 80, base - 10 * s - 22), "10 m", fill=RED, font=font(15, True))


def mesh_view(path_gw45s, out_png, title="", az_deg=-35.0, el_deg=28.0, size=(1920, 1080)):
    """面の記録（R5 の GW45SRF1）を、横を y → −y に写して全幅にし、斜め上から陰をつけて描く（PIL の多角形を奥から順に。確かめの図）。
    縦横同じ縮尺。光は斜め上から。Unity の描き方ではない。"""
    import g45_export_unity as EU
    d = EU.read_frame_bytes(open(path_gw45s, "rb").read())
    P = d["P"]; N = d["N"]; tri = d["tri"].astype(np.int64)
    P2 = np.concatenate([P, P * np.array([1, 1, -1])]); N2 = np.concatenate([N, N * np.array([1, 1, -1])])
    tri2 = np.concatenate([tri, tri[:, ::-1] + len(P)])
    az, el = math.radians(az_deg), math.radians(el_deg)
    # 計画の座標（x 前、上、横）→ 見る向き：横（z）を奥行き、x を右へ
    X = P2[:, 0] - P2[:, 0].mean(); Z = P2[:, 2]; Y = P2[:, 1]
    xr = X * math.cos(az) - Z * math.sin(az); zr = X * math.sin(az) + Z * math.cos(az)
    sx = xr; sy = -(Y * math.cos(el) - zr * math.sin(el)); depth = zr * math.cos(el) + Y * math.sin(el)
    W_, H_ = size
    sc = 0.92 * min(W_ / (sx.max() - sx.min()), (H_ - 120) / (sy.max() - sy.min()))
    u = (sx - sx.min()) * sc + 0.04 * W_; v = (sy - sy.min()) * sc + 90
    L = np.array([-0.75, 0.45, -0.5]); L = L / np.linalg.norm(L)       # 横から低く当てる光（波の起伏が見えるように）
    nf = N2[tri2].mean(1); nf = nf / np.maximum(np.linalg.norm(nf, axis=1, keepdims=True), 1e-9)
    lam = np.clip(nf @ L, 0, 1)
    hgt = np.clip((P2[tri2, 1].mean(1) + 4.0) / 10.0, 0, 1)            # 高さ（−4〜+6 m）で頂を明るく
    order = np.argsort(-depth[tri2].mean(1))
    im = Image.new("RGB", (W_, H_), BG); dr = ImageDraw.Draw(im)
    for i in order:
        a, b, c = tri2[i]
        g = 0.15 + 0.85 * lam[i]
        col = (int(20 + 90 * g + 80 * hgt[i]), int(55 + 120 * g + 60 * hgt[i]), int(95 + 130 * g + 20 * hgt[i]))
        dr.polygon([(u[a], v[a]), (u[b], v[b]), (u[c], v[c])], fill=col)
    dr.text((40, 14), title, fill=TXT, font=font(22, True))
    dr.text((40, 46), "面の記録（R5、GW45SRF1）を y = 0 で写して全幅で描いた確かめの図。縦横同じ縮尺。t = %.2f s、三角形 %d（片側）" % (d["t"], d["nt"]), fill=SUB, font=font(16))
    # 10 m の目盛り（画面の左下、横向き）
    dr.line([(60, H_ - 40), (60 + 10 * sc, H_ - 40)], fill=RED, width=4)
    dr.text((66 + 10 * sc, H_ - 54), "10 m（画面の横の向き、おおよそ）", fill=RED, font=font(16, True))
    im.save(out_png)
    return out_png


def encode(path):
    return subprocess.Popen([GC.FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "24", "-i", "-",
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)


def render(data, f, head, sub):
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
    P = data.cfg["parms"]; x0 = P["x0"]; x1 = P["x0"] + P["Lx"]
    t = data.R1.get(f)[2]
    dr.text((40, 14), head, fill=TXT, font=font(22, True))
    dr.text((40, 46), sub, fill=SUB, font=font(16))
    dr.text((W - 260, 14), "t = %6.2f s" % t, fill=TXT, font=font(26, True))
    ph = side(im, dr, data, f, (60, 110, W - 60), x0, x1, -20.0, 16.0, "横から（y = 0 の断面）")
    yb = 110 + ph + 60
    plan_view(im, dr, data, f, (60, yb, 900, H - 40), "上から（高さ −8〜+8 m、y = 0 で写して全幅）")
    ymax = float(P["sd0"]) if float(P.get("sd_on", 1.0)) > 0.5 else float(P["W"])
    oblique(im, dr, data, f, (960, yb, W - 60, H - 20), "斜め上から（y = 0〜%g m を 6 m ごと）" % ymax, ymax=ymax, x_lo=P["in1"], x_hi=P["ex0"])
    return im


def main():
    rid, outd = sys.argv[1], sys.argv[2]
    opt = dict(q[2:].split("=", 1) for q in sys.argv[3:] if q.startswith("--"))
    root = opt.get("root", "runs")
    os.makedirs(outd, exist_ok=True)
    data = Data(rid, root)
    P = data.cfg["parms"]
    coarse = "（粗い）" if float(P["dp"]) > 0.25 + 1e-9 else ""
    tgt = data.cfg["table"]["target"]
    head = "FLIP45 %s：%s、粒子 %.4g m（格子 %.4g m）%s。力は重力だけ。%s" % (rid, tgt if isinstance(tgt, str) else tgt.get("kind"), P["dp"], 2 * P["dp"], coarse,
                                                                 opt.get("label", ""))
    sub = "縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。位置は造波板からの距離（m）。半分の幅を解き、y = 0 は対称の面" % data.off
    if "mesh" in opt:          # --mesh=<コマ>：面の記録を斜め上から描いた 1 枚
        fm = int(opt["mesh"])
        src = os.path.join(data.rd, "surf", "s_%05d.gw45s" % fm)
        print(mesh_view(src, os.path.join(outd, "%s_mesh_f%05d.png" % (rid, fm)), head))
        return
    if "still" in opt:
        ts = float(opt["still"])
        f = min(data.frames, key=lambda q: abs(data.R1.get(q)[2] - ts))
        render(data, f, head, sub).save(os.path.join(outd, "%s_t%06.2f.png" % (rid, ts)))
        return
    t0 = float(opt.get("t0", -1e9)); t1 = float(opt.get("t1", 1e9))
    frs = [f for f in data.frames if t0 - 1e-9 <= data.R1.get(f)[2] <= t1 + 1e-9]
    p = encode(os.path.join(outd, "%s_3view.mp4" % rid))
    for f in frs:
        p.stdin.write(np.asarray(render(data, f, head, sub)).tobytes())
    p.stdin.close(); p.wait()
    print("wrote", os.path.join(outd, "%s_3view.mp4" % rid), len(frs), "frames")


if __name__ == "__main__":
    main()
