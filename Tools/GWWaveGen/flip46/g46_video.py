# -*- coding: utf-8 -*-
"""FLIP46：尾根の上の孤立波の計算の動画と確かめの図（py -3.10 -B、numpy・scipy・scikit-image・PIL・ffmpeg）。
2026-10-12 解析と図の道具の役が書いた。FLIP45 の g45_video.py（変えていない）の描き方を読み込んで使い、尾根の海底と拡大の帯を足した。
読む物は g46_analyze.Ctx（記録・海底の式・静かな水面のずれ）と、あれば g46_analyze.py の ana.json（巻き始め・着水のコマ）。

作る物（--only=video,zoom,mesh,boat で選ぶ。既定は全部）：
  video  <名前>_4view.mp4（24 コマ/s、実時間）。1 コマに 4 つの図：
           上    横から（y = 0 の断面 r2。縦横同じ縮尺、高さは静かな水面から、10 m の目盛り、尾根の真ん中の海底を砂の色で、
                 GG06 の崩れる点 x 273.5 m に赤い印）
           中左  上から（一番上の水面 hf − 静かな水面のずれ。y = 0 で写して全幅。海底の等深線 2・4・8・12 m）
           中右  y = 0 の断面の拡大（崩れる点のまわり。g45 の V1 の断面の拡大と同じ描き方）
           下    斜め上から（g45_video.oblique：hf を横 6 m ごとに奥へずらして重ねる）
  zoom   <名前>_section_zoom.png：y = 0 の断面の拡大を 6 つの時刻で（1 m = 10 px。巻き始め・図 9 の時刻・着水のまわり）
  mesh   <名前>_mesh_fNNNNN.png（g45_video.mesh_view。面の記録の全部）と <名前>_meshzoom_fNNNNN.png（崩れる点のまわりを切った拡大）
  boat   <名前>_boat_fNNNNN_DddD_hH.png：低い船の目（静かな水面 + h m、崩れる点の前 D m、y = 0、−x を向く）からの透視の図。
         numpy の z バッファ（view_diag.py の描き方を写し、三角形をまとめて塗るように直した）。角度の物差しは原画と同じ
         （FLIP45 diag/view の富士の物差し、横 75.8 px/°。赤線は原画の頂の仰角 16.9°）。面の記録がなければ hf を三角形にして描く。
使い方: py -3.10 -B g46_video.py <記録の置き場所> [--out=<置き場所>] [--ana=<ana.json>] [--only=video,zoom,mesh,boat]
        [--t0=<s>] [--t1=<s>] [--label=...] [--still=<s>] [--zoomgrid=t1,t2,...] [--frames=f1,f2,...] [--boat_d=30] [--boat_h=2]
        [--boat_ride] [--boat_follow] [--boat_hfov=<度>] [--boat_video]
  --boat_ride：目の高さをその場の水面 + h に。--boat_follow：目をそのコマの頂の前 D m に（既定は崩れる点の前に止める）
出力の置き場所の既定：記録が Unity/Build/FLIP46 の中なら <記録>/video、外なら Unity/Build/FLIP46/smoke/test_<名前>/video。
"""
import sys, os, json, math, subprocess, time
sys.dont_write_bytecode = True
import numpy as np
from scipy.ndimage import map_coordinates
from skimage import measure
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_analyze as A46          # noqa: E402  Ctx・default_out・guard_out（FLIP45 の道具の置き場所も sys.path に入る）
import g45_video as V45             # noqa: E402  font・cmap・oblique・mesh_view・encode
import g45_export_unity as EU       # noqa: E402
import g45_common as GC45           # noqa: E402  FFMPEG

W, H = 1920, 1080
BG = V45.BG; WATER = V45.WATER; LINE = V45.LINE; TXT = V45.TXT; SUB = V45.SUB; RED = V45.RED
SAND = (196, 178, 140); SAND_EDGE = (150, 132, 96); BLUE_MARK = (30, 110, 200)
VIEW_NUMBERS = A46.REPO + "/Unity/Build/FLIP45/diag/view/view_numbers.json"
font = V45.font


# ======================================================================== 記録
class Data:
    def __init__(self, rd, opt):
        self.cx = A46.Ctx(rd, opt)
        self.rd = self.cx.rd
        self.name = os.path.basename(self.rd.rstrip("/"))
        self.R1, self.R2 = self.cx.R1, self.cx.R2
        self.off = self.cx.off
        self.cfg = self.cx.cfg
        ap = opt.get("ana") or os.path.join(A46.default_out(self.rd), "ana.json")
        self.ana = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
        self.ana_path = ap if self.ana else None
        s2 = set(self.R2.frames)
        self.frames = [f for f in self.R1.frames if f in s2] or self.R1.frames
        self.ridge = self.cx.kind == "ridge"
        on = self.ana.get("onset") or {}
        self.xB = on.get("xc") or (A46.GG06["table1"][0.25]["x"] * self.cx.h0 if self.ridge else 0.5 * (self.cx.x_min + self.cx.x_max))
        self.tB = on.get("t")

    def t(self, f):
        return self.R1.get(f)[2]

    def frame_at(self, t):
        return min(self.frames, key=lambda q: abs(self.t(q) - t))


# ======================================================================== 横からの断面（r2）
def section(im, dr, D, f, box, xr0, xr1, z0, z1, title, tick=50.0, marks=True, scale_label=True):
    """box = (px0, py0, px1)。縦横同じ縮尺で、高さは静かな水面から。海底は砂の色。返り値 描いた高さ（px）。"""
    px0, py0, px1 = box
    s = (px1 - px0) / (xr1 - xr0)
    ph = int(round((z1 - z0) * s))
    xs = xr0 + (np.arange(px1 - px0) + 0.5) / s
    zs = z1 - (np.arange(ph) + 0.5) / s
    a = np.empty((ph, px1 - px0, 3), np.uint8); a[:] = BG
    if f in D.R2.b:
        S, m, t = D.R2.get(f)
        gx = (xs - m["x0"]) / m["dx"]; gz = (zs + D.off - m["y0"]) / m["dy"]
        GX, GZ = np.meshgrid(gx, gz)
        v = map_coordinates(S.astype(np.float32), [GZ.ravel(), GX.ravel()], order=1, mode="nearest").reshape(GZ.shape)
        a[v < 0] = WATER
    zb = D.cx.bed_z(xs, float(D.R2.get(f)[1].get("z", 0.0)) if f in D.R2.b else 0.0) - D.off
    bedm = zs[:, None] < zb[None, :]
    a[bedm] = SAND
    a[:, (xs < D.cx.x_min) | (xs > D.cx.x_max)] = (225, 225, 220)
    im.paste(Image.fromarray(a), (px0, py0))
    X = lambda xr: px0 + (xr - xr0) * s
    Y = lambda z: py0 + (z1 - z) * s
    pts = [(X(x), Y(min(max(z, z0), z1))) for x, z in zip(xs[::4], zb[::4])]
    if len(pts) > 1:
        dr.line(pts, fill=SAND_EDGE, width=1)
    for xx in np.arange(px0, px1, 14):
        dr.line([(xx, Y(0)), (min(xx + 7, px1), Y(0))], fill=LINE, width=1)
    for gx in np.arange(math.ceil(xr0 / tick) * tick, xr1 + 1e-6, tick):
        dr.line([(X(gx), Y(z0)), (X(gx), Y(z0) + 6)], fill=SUB, width=1)
        dr.text((X(gx) - 14, Y(z0) + 7), "%d" % gx, fill=SUB, font=font(15))
    bx = px0 + 14
    dr.line([(bx, Y(0)), (bx, Y(10))], fill=RED, width=4)
    if scale_label:
        dr.text((bx + 9, Y(10) - 4), "10 m", fill=RED, font=font(17, True))
    if marks and D.ridge:
        xg = A46.GG06["table1"][0.25]["x"] * D.cx.h0
        if xr0 <= xg <= xr1:
            dr.polygon([(X(xg), Y(z0) - 2), (X(xg) - 6, Y(z0) - 12), (X(xg) + 6, Y(z0) - 12)], fill=RED)
            dr.text((X(xg) + 8, Y(z0) - 26), "GG06 の崩れる点", fill=RED, font=font(14))
    if marks and D.ana.get("onset"):
        xo = D.ana["onset"]["xc"]
        if xr0 <= xo <= xr1:
            dr.polygon([(X(xo), py0 + 2), (X(xo) - 6, py0 + 12), (X(xo) + 6, py0 + 12)], fill=BLUE_MARK)
    dr.rectangle([px0, py0, px1, py0 + ph], outline=(120, 120, 120))
    if title:
        dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    return ph


# ======================================================================== 上から（hf）
def plan_view(im, dr, D, f, box, title, lo, hi):
    px0, py0, px1, py1 = box
    e, m, t = D.R1.get(f)
    E = e - D.off
    full = np.concatenate([E[::-1], E], 0)
    img = Image.fromarray(V45.cmap(full[::-1], lo, hi))
    Lx_ = m["dx"] * m["res"][0]; Wf = 2 * m["dz"] * m["res"][2]
    sc = min((px1 - px0) / Lx_, (py1 - py0) / Wf)
    px1 = px0 + int(round(Lx_ * sc)); py1 = py0 + max(2, int(round(Wf * sc)))
    img = img.resize((px1 - px0, py1 - py0), Image.NEAREST)
    im.paste(img, (px0, py0))
    xs = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs = m["z0"] + m["dz"] * np.arange(m["res"][2])
    if D.ridge:                                      # 海底の等深線（y = 0 で写して全幅）
        zz = np.concatenate([-zs[::-1], zs])
        dep = -D.cx.bed_z(xs[None, :], zz[:, None])
        for lev in (2.0, 4.0, 8.0, 12.0, 16.0):
            for c in measure.find_contours(dep, lev):
                pts = [(px0 + (0.5 + q[1]) * m["dx"] * sc, py1 - (0.5 + q[0]) * m["dz"] * sc) for q in c[::2]]
                if len(pts) > 1:
                    dr.line(pts, fill=(70, 70, 60), width=1)
                    j = len(pts) // 2 if lev != 16.0 else 0
                    dr.text((pts[j][0] + 2, pts[j][1] - 8), "%g m" % lev, fill=(50, 50, 40), font=font(11))
    dr.rectangle([px0, py0, px1, py1], outline=(120, 120, 120))
    dr.text((px0, py0 - 26), title, fill=TXT, font=font(18, True))
    s = (px1 - px0) / Lx_
    dr.line([(px0 + 10, py1 - 12), (px0 + 10 + 10 * s, py1 - 12)], fill=RED, width=4)
    dr.text((px0 + 14 + 10 * s, py1 - 26), "10 m", fill=RED, font=font(15, True))
    ymid = (py0 + py1) / 2
    for xx in np.arange(px0, px1, 12):
        dr.line([(xx, ymid), (min(xx + 6, px1), ymid)], fill=(240, 240, 240), width=1)
    # 色の目盛り
    bw = 160; bx0 = px1 - bw - 44; by0 = py0 - 18
    ramp = V45.cmap(np.linspace(lo, hi, bw)[None, :].repeat(8, 0), lo, hi)
    im.paste(Image.fromarray(ramp), (bx0, by0))
    dr.text((bx0 - 52, by0 - 4), "%+g m" % lo, fill=SUB, font=font(12))
    dr.text((bx0 + bw + 4, by0 - 4), "%+g m" % hi, fill=SUB, font=font(12))
    return py1


# ======================================================================== 1 コマの 4 つの図
def zoom_window(D):
    if D.ridge:
        x1 = min(D.xB + 25.0, D.cx.x_max); return x1 - 70.0, x1
    return D.xB - 45.0, D.xB + 25.0


def render(D, f, head, sub):
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
    cx = D.cx
    t = D.t(f)
    dr.text((40, 14), head, fill=TXT, font=font(22, True))
    dr.text((40, 46), sub, fill=SUB, font=font(16))
    dr.text((W - 330, 14), "t = %6.2f s" % t, fill=TXT, font=font(26, True))
    if D.ridge:
        dr.text((W - 330, 50), "t' = %.3f（GG06 の巻き始め 7.890）" % cx.tprime(t), fill=SUB, font=font(15))
    zlo = -cx.h0 if D.ridge else max(-cx.h0, -20.0)
    ph = section(im, dr, D, f, (60, 110, W - 60), cx.x_min, cx.x_max, zlo, 16.0, "横から（y = 0 の断面。砂の色は尾根の真ん中の海底）" if D.ridge else "横から（y = 0 の断面）")
    yb = 110 + ph + 64
    lo, hi = (-4.0, 12.0) if D.ridge else (-8.0, 8.0)
    plan_view(im, dr, D, f, (60, yb, 920, yb + 400), "上から（高さ %+g〜%+g m、y = 0 で写して全幅%s）" % (lo, hi, "。線は海底の等深線" if D.ridge else ""), lo, hi)
    xz0, xz1 = zoom_window(D)
    zz0 = max(zlo, -8.0)
    section(im, dr, D, f, (980, yb, W - 60), xz0, xz1, zz0, 16.0, "y = 0 の断面の拡大（x %.0f〜%.0f m）" % (xz0, xz1), tick=10.0)
    yo = 760
    P = cx.P
    if D.ridge:
        ymax = cx.y_max; xlo = A46.GG06["xs"] * cx.h0 - 20.0; xhi = cx.x_max
    else:
        ymax = float(P.get("sd0", cx.y_max)) if float(P.get("sd_on", 1.0)) > 0.5 else cx.y_max
        xlo = float(P.get("in1", cx.x_min)); xhi = float(P.get("ex0", cx.x_max))
    V45.oblique(im, dr, D, f, (60, yo + 30, W - 60, H - 10), "斜め上から（y = 0〜%g m を 6 m ごと、x %.0f〜%.0f m）" % (ymax, xlo, xhi), ymax=ymax, x_lo=xlo, x_hi=xhi)
    return im


def heads(D, opt):
    cx = D.cx
    coarse = "（粗い）" if cx.dp > 0.25 + 1e-9 else ""
    if D.ridge:
        head = "FLIP46 %s：GG06 の尾根 k %g の上の孤立波 H0/h0 %.2g、粒子 %.4g m（格子 %.4g m）%s。力は重力だけ。%s" % (
            D.name, cx.k, cx.H0 / cx.h0, cx.dp, cx.vox, coarse, opt.get("label", ""))
        sub = "縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。x は上流の壁から（m）。半分の幅を解き、y = 0 は対称の面、y = %g m は壁" % (D.off, cx.y_max)
    else:
        head = "%s %s：粒子 %.4g m（格子 %.4g m）%s。g46_video の試し（尾根ではない）%s" % (cx.stage or "", D.name, cx.dp, cx.vox, coarse, opt.get("label", ""))
        sub = "縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。半分の幅を解き、y = 0 は対称の面" % D.off
    return head, sub


def make_video(D, out, opt):
    head, sub = heads(D, opt)
    t0 = float(opt.get("t0", -1e9)); t1 = float(opt.get("t1", 1e9))
    frs = [f for f in D.frames if t0 - 1e-9 <= D.t(f) <= t1 + 1e-9]
    path = os.path.join(out, "%s_4view.mp4" % D.name)
    p = V45.encode(path)
    for f in frs:
        p.stdin.write(np.asarray(render(D, f, head, sub)).tobytes())
    p.stdin.close(); p.wait()
    return path, len(frs)


# ======================================================================== 断面の拡大を並べた図
def key_times(D):
    on = D.ana.get("onset") or {}; td = D.ana.get("touchdown") or {}
    cx = D.cx
    t_last = D.t(D.frames[-1]); t_first = D.t(D.frames[0])
    if on:
        ts = [on["t"] - 0.75, on["t"]]
        if td:
            ts += [0.5 * (on["t"] + td["t"]), td["t"] - 0.25, td["t"], td["t"] + 0.3]
        else:
            ts += [on["t"] + 0.5, on["t"] + 1.0, on["t"] + 1.5, on["t"] + 2.0]
    elif D.ridge:
        ts = [cx.t_of_tprime(v) for v in (6.5, 7.5, 7.89, 8.5, 9.142, 9.5)]
    else:
        ts = list(np.linspace(t_first + 0.67 * (t_last - t_first), t_last, 6))
    return [min(max(v, t_first), t_last) for v in ts]


def zoom_grid(D, out, times):
    cx = D.cx
    xz0, xz1 = zoom_window(D)
    zlo = max(-cx.h0 if D.ridge else -20.0, -8.0); zhi = 16.0 if D.ridge else 10.0
    pw = int(round((xz1 - xz0) * 10)); ph = int(round((zhi - zlo) * 10))
    ncol = 3; nrow = int(math.ceil(len(times) / ncol))
    Wd = 40 + ncol * (pw + 20); Hd = 70 + nrow * (ph + 50)
    im = Image.new("RGB", (Wd, Hd), BG); dr = ImageDraw.Draw(im)
    coarse = "粗い：" if cx.dp > 0.25 + 1e-9 else ""
    dr.text((20, 12), "FLIP46 %s（%s粒子 %.4g m・格子 %.4g m）y = 0 の断面の拡大。縦横同じ縮尺（1 m = 10 px）。点線は静かな水面、砂の色は海底。力は重力だけ" % (
        D.name, coarse, cx.dp, cx.vox), fill=TXT, font=font(19, True))
    for i, tq in enumerate(times):
        f = D.frame_at(tq)
        r, c = divmod(i, ncol)
        px0 = 20 + c * (pw + 20); py0 = 60 + r * (ph + 50)
        section(im, dr, D, f, (px0, py0, px0 + pw), xz0, xz1, zlo, zhi, None, tick=10.0, scale_label=(i == 0))
        lab = "t = %.2f s" % D.t(f)
        if D.ridge:
            lab += "（t' %.3f）" % cx.tprime(D.t(f))
        dr.text((px0 + pw - 9 * len(lab) - 40, py0 + 4), lab, fill=RED, font=font(17, True))
    p = os.path.join(out, "%s_section_zoom.png" % D.name)
    im.save(p)
    return p


# ======================================================================== 面の記録（斜め上から）
def mesh_still(D, out, f, crop=True):
    d, fm = A46.mesh_frame(D.cx, f)
    if d is None:
        return None
    src = os.path.join(D.rd, "surf", "s_%05d.gw45s" % fm)
    head, _ = heads(D, {})
    p_full = V45.mesh_view(src, os.path.join(out, "%s_mesh_f%05d.png" % (D.name, fm)), head + "（コマ %d）" % fm)
    res = [p_full]
    if crop:
        res.append(mesh_view_crop(D, d, fm, os.path.join(out, "%s_meshzoom_f%05d.png" % (D.name, fm))))
    return res


def mesh_view_crop(D, d, fm, out_png, az_deg=-35.0, el_deg=18.0, size=(1920, 1080), ylat=45.0):
    """g45_video.mesh_view と同じ描き方で、崩れる点のまわり（x xB − 60〜xB + 40 m、横 ±ylat m）だけを切って大きく描く。"""
    P = d["P"].copy(); P[:, 1] -= D.off
    N = d["N"]; tri = d["tri"].astype(np.int64)
    x0, x1 = D.xB - 60.0, D.xB + 40.0
    cen = P[tri].mean(1)
    tri = tri[(cen[:, 0] >= x0) & (cen[:, 0] <= x1) & (cen[:, 2] <= ylat)]
    if not len(tri):
        return None
    P2 = np.concatenate([P, P * np.array([1, 1, -1])]); N2 = np.concatenate([N, N * np.array([1, 1, -1])])
    tri2 = np.concatenate([tri, tri[:, ::-1] + len(P)])
    az, el = math.radians(az_deg), math.radians(el_deg)
    X = P2[:, 0] - D.xB; Z = P2[:, 2]; Y = P2[:, 1]
    xr = X * math.cos(az) - Z * math.sin(az); zr = X * math.sin(az) + Z * math.cos(az)
    sx = xr; sy = -(Y * math.cos(el) - zr * math.sin(el)); depth = zr * math.cos(el) + Y * math.sin(el)
    used = np.unique(tri2)
    W_, H_ = size
    sc = 0.92 * min(W_ / np.ptp(sx[used]), (H_ - 130) / np.ptp(sy[used]))
    u = (sx - sx[used].min()) * sc + 0.04 * W_; v = (sy - sy[used].min()) * sc + 100
    L = np.array([-0.75, 0.45, -0.5]); L = L / np.linalg.norm(L)
    nf = N2[tri2].mean(1); nf = nf / np.maximum(np.linalg.norm(nf, axis=1, keepdims=True), 1e-9)
    lam = np.clip(nf @ L, 0, 1)
    hgt = np.clip((P2[tri2, 1].mean(1) + 4.0) / 16.0, 0, 1)
    order = np.argsort(-depth[tri2].mean(1))
    im = Image.new("RGB", (W_, H_), BG); dr = ImageDraw.Draw(im)
    for i in order:
        a, b, c = tri2[i]
        g = 0.15 + 0.85 * lam[i]
        col = (int(20 + 90 * g + 80 * hgt[i]), int(55 + 120 * g + 60 * hgt[i]), int(95 + 130 * g + 20 * hgt[i]))
        dr.polygon([(u[a], v[a]), (u[b], v[b]), (u[c], v[c])], fill=col)
    head, _ = heads(D, {})
    dr.text((40, 14), head, fill=TXT, font=font(22, True))
    dr.text((40, 46), "面の記録（GW45SRF1）の x %.0f〜%.0f m・横 ±%g m を y = 0 で写して描いた確かめの図。縦横同じ縮尺。t = %.2f s（コマ %d）%s" % (
        x0, x1, ylat, d["t"], fm, "、t' %.3f" % D.cx.tprime(d["t"]) if D.ridge else ""), fill=SUB, font=font(16))
    dr.line([(60, H_ - 40), (60 + 10 * sc, H_ - 40)], fill=RED, width=4)
    dr.text((66 + 10 * sc, H_ - 54), "10 m（画面の横の向き、おおよそ）", fill=RED, font=font(16, True))
    im.save(out_png)
    return out_png


# ======================================================================== 船の目（透視、z バッファ）
SKY_T = np.array([249, 232, 196], float) / 255; SKY_B = np.array([200, 196, 182], float) / 255
DEEP = np.array([0.06, 0.20, 0.33]); SHAL = np.array([0.22, 0.45, 0.55])
LDIR = np.array([0.35, 0.55, 0.76]); LDIR = LDIR / np.linalg.norm(LDIR)


def print_ruler():
    """原画の角度の物差し（FLIP45 diag/view の view_numbers.json。読むだけ）。返り値 (横 px/°, 頂の仰角°, 地平線の行, 幅, 高さ)。"""
    try:
        a = json.load(open(VIEW_NUMBERS, encoding="utf8"))["A_print"]
        return float(a["s_h_px_per_deg"]), float(a["crest_elev_deg_linear"]), float(a["horizon_row_ref_px"])
    except Exception:
        return 75.78, 16.88, 1885.0


def tri_grid(nx, ny):
    """nx × ny の点の格子（行が y）の三角形。"""
    j, i = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    a = (j * nx + i).ravel()
    return np.concatenate([np.stack([a, a + 1, a + nx], 1), np.stack([a + 1, a + nx + 1, a + nx], 1)])


def hf_patch(D, f, inset=None):
    """一番上の水面（hf）を y = 0 で写した三角形（世界の座標 (x, 横, 上)）。inset = (x0, x1, 横の最大) の中の三角形は除く（面の記録で描く）。"""
    e, m, t = D.R1.get(f)
    e = np.nan_to_num(e - D.off, nan=0.0)
    xs = m["x0"] + m["dx"] * np.arange(e.shape[1]); ys = m["z0"] + m["dz"] * np.arange(e.shape[0])
    ys2 = np.concatenate([-ys[::-1], ys]); e2 = np.concatenate([e[::-1], e])
    X, Y = np.meshgrid(xs, ys2)
    P = np.stack([X.ravel(), Y.ravel(), e2.ravel()], 1)
    T = tri_grid(len(xs), len(ys2))
    if inset is not None:
        c = P[T].mean(1)
        T = T[~((c[:, 0] > inset[0]) & (c[:, 0] < inset[1]) & (np.abs(c[:, 1]) < inset[2]))]
    return P, T, (xs[0] - 0.5 * m["dx"], xs[-1] + 0.5 * m["dx"], ys[-1] + 0.5 * m["dz"])


def far_plane(cam, fwd, R=3000.0):
    rs = np.geomspace(1.0, R, 90)
    ang = np.radians(np.linspace(-100, 100, 121)) + math.atan2(fwd[1], fwd[0])
    RR, AA = np.meshgrid(rs, ang, indexing="ij")
    P = np.stack([cam[0] + RR.ravel() * np.cos(AA.ravel()), cam[1] + RR.ravel() * np.sin(AA.ravel()), np.zeros(RR.size)], 1)
    return P, tri_grid(len(ang), len(rs))


def shade(P, T, cam):
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n = np.cross(b - a, c - a); n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cen = (a + b + c) / 3; v = cam - cen; dist = np.linalg.norm(v, axis=1); v = v / np.maximum(dist[:, None], 1e-9)
    n = np.where((np.sum(n * v, 1) < 0)[:, None], -n, n)
    lam = np.clip(n @ LDIR, 0, 1)
    cosv = np.clip(np.sum(n * v, 1), 0, 1); F = 0.02 + 0.98 * (1 - cosv) ** 5
    h = np.clip((cen[:, 2] + 2.0) / 12.0, 0, 1)[:, None]
    base = DEEP * (1 - h) + SHAL * h
    col = base * (0.35 + 0.65 * lam[:, None]) * (1 - F[:, None]) + SKY_B * F[:, None]
    fog = np.clip(dist / 2500.0, 0, 1)[:, None] ** 0.7
    return col * (1 - fog) + SKY_B * fog


def raster(P, T, col, cam, yaw_deg, Wi, Hi, fx, fy, cx, cy, ss=2, chunk_samples=2_000_000):
    """三角形を z バッファで塗る（view_diag.py の raster と同じ投影。小さい三角形は大きさの段ごとにまとめて塗る）。"""
    W2, H2 = Wi * ss, Hi * ss; fx2, fy2, cx2, cy2 = fx * ss, fy * ss, cx * ss, cy * ss
    ps = math.radians(yaw_deg); fw = np.array([math.cos(ps), math.sin(ps), 0.0]); rt = np.array([math.sin(ps), -math.cos(ps), 0.0])
    d = P - cam; Zc = d @ fw; Xc = d @ rt; Yc = d[:, 2]
    good = Zc > 0.3
    Zs = np.where(good, Zc, 1.0)
    u = cx2 + fx2 * Xc / Zs; v = cy2 - fy2 * Yc / Zs; iz = np.where(good, 1.0 / Zs, 0.0)
    keep = good[T].all(1)
    T = T[keep]; col = col[keep]
    U = u[T]; V = v[T]; IZ = iz[T]
    x0 = np.floor(U.min(1)).astype(np.int64); x1 = np.ceil(U.max(1)).astype(np.int64)
    y0 = np.floor(V.min(1)).astype(np.int64); y1 = np.ceil(V.max(1)).astype(np.int64)
    vis = (x1 >= 0) & (x0 < W2) & (y1 >= 0) & (y0 < H2)
    xa = np.clip(x0, 0, W2 - 1); xb = np.clip(x1, 0, W2 - 1); ya = np.clip(y0, 0, H2 - 1); yb = np.clip(y1, 0, H2 - 1)
    bw = xb - xa + 1; bh = yb - ya + 1; size = np.maximum(bw, bh)
    den = (V[:, 1] - V[:, 2]) * (U[:, 0] - U[:, 2]) + (U[:, 2] - U[:, 1]) * (V[:, 0] - V[:, 2])
    vis &= np.abs(den) > 1e-12
    zbuf = np.zeros(H2 * W2, np.float64); cid = -np.ones(H2 * W2, np.int64)

    def resolve(pix, z, tid):
        o = np.lexsort((-z, pix))
        pix, z, tid = pix[o], z[o], tid[o]
        first = np.r_[True, pix[1:] != pix[:-1]]
        pix, z, tid = pix[first], z[first], tid[first]
        upd = z > zbuf[pix]
        zbuf[pix[upd]] = z[upd]; cid[pix[upd]] = tid[upd]

    done = np.zeros(len(T), bool)
    for Bsz in (2, 4, 8, 16, 32, 64):
        sel = np.nonzero(vis & ~done & (size <= Bsz))[0]
        done[sel] = True
        if not len(sel):
            continue
        oy, ox = np.divmod(np.arange(Bsz * Bsz), Bsz)
        step = max(1, chunk_samples // (Bsz * Bsz))
        for c0 in range(0, len(sel), step):
            k = sel[c0:c0 + step]
            gx = xa[k][:, None] + ox[None, :]; gy = ya[k][:, None] + oy[None, :]
            inb = (ox[None, :] < bw[k][:, None]) & (oy[None, :] < bh[k][:, None])
            px = gx + 0.5; py = gy + 0.5
            ax, bx_, cx_ = U[k, 0][:, None], U[k, 1][:, None], U[k, 2][:, None]
            ay, by, cy_ = V[k, 0][:, None], V[k, 1][:, None], V[k, 2][:, None]
            dd = den[k][:, None]
            w0 = ((by - cy_) * (px - cx_) + (cx_ - bx_) * (py - cy_)) / dd
            w1 = ((cy_ - ay) * (px - cx_) + (ax - cx_) * (py - cy_)) / dd
            w2 = 1.0 - w0 - w1
            ins = inb & (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not ins.any():
                continue
            z = w0 * IZ[k, 0][:, None] + w1 * IZ[k, 1][:, None] + w2 * IZ[k, 2][:, None]
            pix = (gy * W2 + gx)[ins]
            resolve(pix, z[ins], np.broadcast_to(k[:, None], ins.shape)[ins])
    for k in np.nonzero(vis & ~done)[0]:                       # 大きい三角形は 1 つずつ
        gxs = np.arange(xa[k], xb[k] + 1); gys = np.arange(ya[k], yb[k] + 1)
        gx, gy = np.meshgrid(gxs, gys)
        px = gx + 0.5; py = gy + 0.5
        (ax, bx_, cx_), (ay, by, cy_) = U[k], V[k]
        w0 = ((by - cy_) * (px - cx_) + (cx_ - bx_) * (py - cy_)) / den[k]
        w1 = ((cy_ - ay) * (px - cx_) + (ax - cx_) * (py - cy_)) / den[k]
        w2 = 1.0 - w0 - w1
        ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if ins.any():
            z = w0 * IZ[k, 0] + w1 * IZ[k, 1] + w2 * IZ[k, 2]
            resolve((gy * W2 + gx)[ins], z[ins], np.full(int(ins.sum()), k))
    rows = (np.arange(H2)[:, None] + 0.5)
    tsky = np.clip((cy2 - rows) / (0.9 * max(cy2, 1.0)), 0, 1)
    sky = SKY_B * (1 - tsky[..., None]) + SKY_T * tsky[..., None]
    sky = np.broadcast_to(sky, (H2, W2, 3)).reshape(-1, 3)
    out = np.where((cid >= 0)[:, None], col[np.maximum(cid, 0)], sky).reshape(H2, W2, 3)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).resize((Wi, Hi), Image.LANCZOS)


def boat_scene(D, f, cam, yaw):
    """面の記録（あれば、y = 0 で写す）＋その外の hf＋箱の外の平らな水。"""
    d, fm = A46.mesh_frame(D.cx, f)
    fw = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
    parts = []
    if d is not None:
        P = d["P"].copy(); P[:, 1] -= D.off
        V = np.stack([P[:, 0], P[:, 2], P[:, 1]], 1)
        T = d["tri"].astype(np.int64)
        Pm = np.concatenate([V, V * np.array([1, -1, 1])]); Tm = np.concatenate([T, T[:, ::-1] + len(V)])
        parts.append((Pm, Tm))
        lo, hi = d["lo"], d["hi"]
        inset = (lo[0] + 1.0, hi[0] - 1.0, hi[2] - 1.0)
    else:
        inset = None
    Ph, Th, (hx0, hx1, hy1) = hf_patch(D, f, inset)
    parts.append((Ph, Th))
    Pf, Tf = far_plane(cam, fw)
    cen = Pf[Tf].mean(1)
    Tf = Tf[~((cen[:, 0] > hx0 + 0.5) & (cen[:, 0] < hx1 - 0.5) & (np.abs(cen[:, 1]) < hy1 - 0.5))]
    parts.append((Pf, Tf))
    Ps, Ts, n0 = [], [], 0
    for Pp, Tp in parts:
        Ps.append(Pp); Ts.append(Tp + n0); n0 += len(Pp)
    P = np.concatenate(Ps); T = np.concatenate(Ts)
    return P, T, shade(P, T, cam), (fm if d is not None else None)


def boat_view(D, f, opt, out=None, Wi=1286, Hi=865):
    s_h, alpha_print, y_hor = print_ruler()
    Dd = float(opt.get("boat_d", 30.0)); hh = float(opt.get("boat_h", 2.0))
    e, m, t = D.R1.get(f)
    xs = m["x0"] + m["dx"] * np.arange(e.shape[1])
    xref = D.xB
    if "boat_follow" in opt:                 # 目をそのコマの真ん中の頂（hf の y = 0 の行の最も高い所、崩れる点 ± 40 m）の前に置く
        sel = np.where(np.abs(xs - D.xB) <= 40.0)[0]
        xref = float(xs[sel][int(np.nanargmax(e[0, sel]))])
    xcam = min(xref + Dd, D.cx.x_max - 0.5)
    eta_cam = float(e[0, int(np.argmin(np.abs(xs - xcam)))] - D.off)
    zcam = (eta_cam + hh) if "boat_ride" in opt else hh
    cam = np.array([xcam, 0.0, zcam])
    if "boat_hfov" in opt:
        fx = (Wi / 2.0) / math.tan(math.radians(float(opt["boat_hfov"])) / 2.0)
    else:
        fx = s_h * 180.0 / math.pi / 3.0                       # 原画（3859 px 幅）を 1/3 にした画面で、原画と同じ角度の物差し
    cy = (y_hor + 0.5) / 3.0 - 0.5 if Hi == 865 else 0.73 * Hi
    P, T, col, fm = boat_scene(D, f, cam, 180.0)
    im = raster(P, T, col, cam, 180.0, Wi, Hi, fx, fx, Wi / 2.0, cy)
    # 見かけの仰角（前にある面の点の最大）
    used = np.zeros(len(P), bool); used[np.unique(T)] = True          # 描いた三角形の点だけ（面の記録の下に隠した hf の点は除く）
    dv = P - cam
    ahead = -dv[:, 0]; ok = (ahead > 0.5) & used
    r = np.hypot(dv[ok, 0], dv[ok, 1]); el = np.degrees(np.arctan2(dv[ok, 2], r))
    i = int(np.argmax(el)); a_max = float(el[i]); top = P[ok][i]
    dr = ImageDraw.Draw(im)
    rowa = lambda a: cy - fx * math.tan(math.radians(a))
    for a in (5, 10, 15, 20, 25, 30):
        y = rowa(a)
        if 0 < y < Hi:
            for x in range(0, Wi, 14):
                dr.line([(x, y), (x + 6, y)], fill=(120, 120, 120), width=1)
            dr.text((Wi - 44, y - 16), "%d°" % a, fill=(90, 90, 90), font=font(13))
    y = rowa(alpha_print)
    dr.line([(0, y), (Wi, y)], fill=(200, 30, 30), width=2)
    lab = "原画の頂の仰角 %.1f°（富士の物差し、FLIP45 diag/view）" % alpha_print
    bb = dr.textbbox((8, y - 21), lab, font=font(15, True))
    dr.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill=(248, 246, 240))
    dr.text((8, y - 21), lab, fill=(200, 30, 30), font=font(15, True))
    dr.line([(0, cy), (Wi, cy)], fill=(150, 140, 120), width=1)
    lines = ["t = %.2f s（コマ %d%s）。目は x %.1f m・y 0・高さ %.2f m（%s）。%s x %.1f m の前 %g m から −x を向く。%s" % (
        t, f, "、t' %.3f" % D.cx.tprime(t) if D.ridge else "", xcam, zcam, "その場の水面 + %g m" % hh if "boat_ride" in opt else "静かな水面 + %g m" % hh,
        "このコマの頂" if "boat_follow" in opt else "崩れる点", xref, Dd, "面の記録 + hf" if fm else "hf だけ（面の記録なし）"),
             "見かけの頂の仰角 %.1f°（点 x %.1f・y %.1f・高さ %.2f m）。目の所の水面 %.2f m。灰の点線は 5° ごと。縦横同じ（伸ばしていない）%s" % (
                 a_max, top[0], top[1], top[2], eta_cam, "。目が水の中" if zcam < eta_cam else "")]
    hh_ = 30 + 20 * len(lines)
    outim = Image.new("RGB", (Wi, Hi + hh_), (248, 246, 240)); outim.paste(im, (0, hh_)); d2 = ImageDraw.Draw(outim)
    d2.text((10, 4), "FLIP46 %s：低い船の目から（正面）D = %g m" % (D.name, Dd), fill=(20, 20, 20), font=font(17, True))
    for k, s in enumerate(lines):
        d2.text((10, 28 + 20 * k), s, fill=(60, 60, 60), font=font(14))
    if out:
        p = os.path.join(out, "%s_boat_f%05d_D%03d_h%s.png" % (D.name, f, int(round(Dd)), ("%g" % hh).replace(".", "p")))
        outim.save(p)
        return p, dict(frame=f, t=t, elev_max_deg=a_max, top=[float(v) for v in top], cam=[float(v) for v in cam], eta_cam=eta_cam)
    return outim, dict(frame=f, t=t, elev_max_deg=a_max)


def boat_video(D, out, opt):
    t0 = float(opt.get("t0", -1e9)); t1 = float(opt.get("t1", 1e9))
    frs = [f for f in D.frames if t0 - 1e-9 <= D.t(f) <= t1 + 1e-9]
    Wi, Hi = 1286, 865
    im0, _ = boat_view(D, frs[0], opt, None, Wi, Hi)
    w_, h_ = im0.size
    w_ -= w_ % 2; h_ -= h_ % 2
    path = os.path.join(out, "%s_boat.mp4" % D.name)
    p = subprocess.Popen([GC45.FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w_, h_), "-r", "24", "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
    for f in frs:
        im, _ = boat_view(D, f, opt, None, Wi, Hi)
        p.stdin.write(np.asarray(im)[:h_, :w_].tobytes())
    p.stdin.close(); p.wait()
    return path, len(frs)


# ======================================================================== 本体
def key_frames(D, opt):
    if opt.get("frames"):
        return [int(v) for v in opt["frames"].split(",")]
    out = []
    on = D.ana.get("onset"); td = D.ana.get("touchdown")
    sh = (D.ana.get("shape") or {}).get("frames") or {}
    if on:
        out.append(int(on["frame"]))
    if sh.get("max_overturn"):
        out.append(int(sh["max_overturn"]))
    f9 = ((D.ana.get("short_crest") or {}).get("gg06_fig9_time") or {}).get("frame")
    if f9 and D.ridge and f9 in D.R1.b:
        out.append(int(f9))
    if td:
        out.append(int(td["frame"]))
    if not out:
        out = [D.frame_at(t) for t in key_times(D)[1::2]]
    return sorted(set(out))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    rd = sys.argv[1]
    opt = A46.parse_opt(sys.argv[2:])
    D = Data(rd, opt)
    out = A46.guard_out(opt.get("out") or (A46.default_out(rd) + "/video"))
    only = set((opt.get("only") or "video,zoom,mesh,boat").split(","))
    t_start = time.time()
    res = dict(run_dir=D.rd, out=out, ana=D.ana_path, xB=D.xB, still_offset=D.off)
    if "still" in opt:
        f = D.frame_at(float(opt["still"]))
        head, sub = heads(D, opt)
        p = os.path.join(out, "%s_4view_f%05d.png" % (D.name, f))
        render(D, f, head, sub).save(p)
        res["still"] = p
        print(json.dumps(res, ensure_ascii=False, indent=1)); return
    if "zoom" in only:
        times = [float(v) for v in opt["zoomgrid"].split(",")] if opt.get("zoomgrid") not in (None, "1") else key_times(D)
        res["zoom"] = zoom_grid(D, out, times)
        print("zoom", res["zoom"], round(time.time() - t_start, 1), "s"); sys.stdout.flush()
    kf = key_frames(D, opt)
    res["key_frames"] = kf
    if "mesh" in only:
        res["mesh"] = []
        for f in kf:
            r_ = mesh_still(D, out, f)
            res["mesh"].append(r_ if r_ else "コマ %d の面の記録なし" % f)
        print("mesh", res["mesh"], round(time.time() - t_start, 1), "s"); sys.stdout.flush()
    if "boat" in only:
        res["boat"] = []
        for f in kf:
            t1_ = time.time()
            p, info = boat_view(D, f, opt, out)
            info["s"] = round(time.time() - t1_, 1)
            res["boat"].append(dict(png=p, **info))
            print("boat", p, info); sys.stdout.flush()
        if "boat_video" in opt:
            res["boat_video"] = boat_video(D, out, opt)
    if "video" in only:
        t1_ = time.time()
        p, n = make_video(D, out, opt)
        res["video"] = dict(path=p, frames=n, s=round(time.time() - t1_, 1))
        print("video", res["video"]); sys.stdout.flush()
    res["elapsed_s"] = round(time.time() - t_start, 1)
    json.dump(A46._clean(res), open(os.path.join(out, "%s_video_log.json" % D.name), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(A46._clean(res), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
