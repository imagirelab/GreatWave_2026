# -*- coding: utf-8 -*-
"""FLIP51 plan E: the compare video of one run (py -3.10 -B; numpy, PIL, ffmpeg). 2026-10-17 written new (Claude). Reads the run records
(hf every frame, r2) and its x51_ana result (screen_E.json / screen_E05.json / judge_E05.json); writes only <run>/video (FLIP51) or --out
(the session scratchpad, for a test on a FLIP50 run).

Panels (all heights above the run's still level eta0; nothing is vertically stretched):
  front 3D   the 3x3-median top surface seen from the shore side, camera eye about the summit height, looking back along -x at the summit
             (the picture's near-frontal view). Colour = height. Black = the TARGET silhouette read from the user's picture (frozen e51 read
             values: full width 3.0 / 2.0 / 1.0 / 0.6 Hc at 20 / 50 / 80 / 95 % of Hc), drawn at this frame's summit and scaled by its Hc.
  crest c(y) c(y)/Hc against (y - y_pk)/Hc at 1:1 (the e51 crest line: max over x_pk - 30 .. x_pk + 10 m); black = the target read values,
             grey = the target ranges (e51 TARGET, [guess] read from the picture).
  top view   x 130-310 m, |y| <= 90 m, 1:1, mirrored at y = 0; + = summit, o = N1 neighbour (highest other peak), circle = the 4 Hc exclusion.
  section    centre section r2 (y 0.5 m) around the summit, 1:1; black = the print's crest outline (g47_video.print_phys, scaled to the section
             crest; the old 2D print ruler, shown for reference).
  table      per period: t, Hc, W50/W80/W95, K, S2, N1, core miss (frozen e51 ruler) and the gates.
A thick RED frame and a 3 s hold mark the most converged instant (the period summit with the smallest core miss); orange = the other
period summits. Normal speed 3x (0.25 s of simulation per frame at 12 fps), 0.5x slow motion from 1.5 s before to 1 s after the red instant.
usage: py -3.10 -B x51_video.py <run_dir> [--res=<screen json>] [--out=<dir>] [--t0=35] [--t1=75]
"""
import os, sys, json, math, time, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from PIL import Image, ImageDraw, ImageFont   # noqa: E402
import x51_common as XC               # noqa: E402
import x51_ana as XA                  # noqa: E402
import e51_metrics as EM              # noqa: E402

FONT = "C:/Windows/Fonts/meiryo.ttc"
W_IMG, H_IMG = 1600, 1040
FPS_OUT = 12
STEP_S = 0.25
SLOW = (-1.5, 1.0)
HOLD_S = 3.0
RED = (220, 0, 0); ORANGE = (240, 140, 0); BLACK = (0, 0, 0); GREY = (150, 150, 150); TXT = (20, 20, 20); SUB = (70, 70, 70)
STOPS = np.array([-4.0, -1.5, 0.0, 1.5, 3.5, 6.0, 9.0])
COLS = np.array([[25, 45, 110], [60, 110, 180], [185, 205, 225], [120, 190, 220], [235, 240, 245], [255, 190, 120], [230, 60, 40]], float)
TGT_F = (0.2, 0.5, 0.8, 0.95, 1.0)
_FC = {}


def fnt(sz):
    if sz not in _FC:
        try:
            _FC[sz] = ImageFont.truetype(FONT, sz)
        except Exception:
            _FC[sz] = ImageFont.load_default()
    return _FC[sz]


def colour(z):
    z = np.asarray(z, float)
    return np.stack([np.interp(z, STOPS, COLS[:, k]) for k in range(3)], -1)


def target_w(f, which="read"):
    T = EM.TARGET
    tab = {0.2: "W20", 0.5: "W50", 0.8: "W80", 0.95: "W95"}
    if f >= 1.0:
        return 0.0
    k = tab[f]
    return T[k]["read"] if which == "read" else T[k][which]


# ====================================================================== 3D (painter's algorithm, PIL polygons)
class Cam:
    def __init__(self, eye, look, box, fov_deg=58.0):
        self.C = np.asarray(eye, float)
        f = np.asarray(look, float) - self.C
        self.f = f / np.linalg.norm(f)
        up = np.array([0.0, 0.0, 1.0])
        r = np.cross(self.f, up); self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.box = box
        self.foc = 0.5 * (box[2] - box[0]) / math.tan(math.radians(0.5 * fov_deg))

    def proj(self, P):
        d = np.asarray(P, float) - self.C
        zf = d @ self.f
        zf = np.where(zf > 0.5, zf, np.nan)
        cx = 0.5 * (self.box[0] + self.box[2]); cy = 0.5 * (self.box[1] + self.box[3])
        return cx + self.foc * (d @ self.r) / zf, cy - self.foc * (d @ self.u) / zf, zf


def render3d(img, e_full, xs, ys, cam, x_lo, x_hi, y_lim):
    bx = cam.box
    sub = Image.new("RGB", (bx[2] - bx[0], bx[3] - bx[1]), (236, 240, 244))
    dr = ImageDraw.Draw(sub)
    sx = (xs >= x_lo) & (xs <= x_hi); sy = np.abs(ys) <= y_lim
    X = xs[sx]; Y = ys[sy]; Z = e_full[np.ix_(sy, sx)]
    XX, YY = np.meshgrid(X, Y)
    P = np.stack([XX, YY, np.nan_to_num(Z, nan=-50.0)], -1)
    u, v, dz = cam.proj(P.reshape(-1, 3))
    u = u.reshape(XX.shape); v = v.reshape(XX.shape); dz = dz.reshape(XX.shape)
    ny, nx = Z.shape
    # per-cell colour and Lambert shading
    gz_y, gz_x = np.gradient(np.nan_to_num(Z, nan=0.0), Y, X)
    nrm = np.stack([-gz_x, -gz_y, np.ones_like(gz_x)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    L = np.array([0.45, 0.25, 0.86]); L /= np.linalg.norm(L)
    shade = np.clip(0.45 + 0.55 * (nrm @ L), 0.25, 1.0)
    col = colour(np.nan_to_num(Z, nan=-9.0)) * shade[..., None]
    cells = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            zz = Z[j:j + 2, i:i + 2]
            if not np.isfinite(zz).all():
                continue
            d = dz[j, i] + dz[j + 1, i + 1]
            if not np.isfinite(d):
                continue
            cells.append((d, j, i))
    cells.sort(reverse=True)
    for _, j, i in cells:
        poly = [(u[j, i] - bx[0], v[j, i] - bx[1]), (u[j, i + 1] - bx[0], v[j, i + 1] - bx[1]), (u[j + 1, i + 1] - bx[0], v[j + 1, i + 1] - bx[1]),
                (u[j + 1, i] - bx[0], v[j + 1, i] - bx[1])]
        c = tuple(int(q) for q in col[j, i])
        dr.polygon(poly, fill=c)
    return sub


def paste3d(img, sub, cam):
    img.paste(sub, (cam.box[0], cam.box[1]))
    dr = ImageDraw.Draw(img)
    dr.rectangle(cam.box, outline=(120, 120, 120))
    return dr


def silhouette_3d(sub, cam, x_pk, y_pk, Hc):
    dr = ImageDraw.Draw(sub)
    bx = cam.box
    for ysgn in ((1.0,) if abs(y_pk) <= 2.0 else (1.0, -1.0)):          # on the axis (within one 1.0 m hf cell): one silhouette
        yc = ysgn * y_pk
        left = [(x_pk, yc - 0.5 * target_w(f) * Hc, f * Hc) for f in TGT_F]
        right = [(x_pk, yc + 0.5 * target_w(f) * Hc, f * Hc) for f in TGT_F[::-1]]
        pts = np.array(left + right, float)
        u, v, _ = cam.proj(pts)
        if np.isfinite(u).all():
            dr.line(list(zip(u - bx[0], v - bx[1])), fill=BLACK, width=3)


# ====================================================================== the other panels
def crest_panel(dr, box, e_full, xs, ys, x_pk, y_pk, Hc, red):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=(255, 255, 255), outline=(150, 150, 150))
    span = 3.5
    s = (x1 - x0) / (2 * span)
    zlo, zhi = -0.15, 1.25
    if (y1 - y0) < (zhi - zlo) * s:
        s = (y1 - y0) / (zhi - zlo)
    cx = 0.5 * (x0 + x1)
    yb = y0 + (zhi - zlo) * s
    U = lambda q: cx + q * s
    V = lambda z: yb - (z - zlo) * s
    # target band and read values
    for which, colr in (("hi", (215, 215, 215)), ("lo", (255, 255, 255))):
        pts = [(U(-0.5 * target_w(f, which if f < 1 else "read")), V(f)) for f in TGT_F] + \
              [(U(0.5 * target_w(f, which if f < 1 else "read")), V(f)) for f in TGT_F[::-1]]
        dr.polygon(pts, fill=colr)
    dr.line([(U(-0.5 * target_w(f)), V(f)) for f in TGT_F] + [(U(0.5 * target_w(f)), V(f)) for f in TGT_F[::-1]], fill=BLACK, width=3)
    dr.line([(x0, V(0.0)), (x1, V(0.0))], fill=GREY)
    for k in range(-3, 4):
        dr.line([(U(k), V(0) - 3), (U(k), V(0) + 3)], fill=GREY)
        dr.text((U(k) - 8, V(zlo) - 16), "%+d" % k if k else "0", fill=SUB, font=fnt(11))
    if Hc and Hc > 0.5:
        cw = (xs >= x_pk - 30.0) & (xs <= x_pk + 10.0)
        c = np.nanmax(np.where(cw[None, :], e_full, -np.inf), axis=1)
        q = (ys - (y_pk if True else 0.0)) / Hc
        ok = np.isfinite(c) & (np.abs(q) <= span)
        pts = [(U(a), V(min(max(b / Hc, zlo), zhi))) for a, b in zip(q[ok], c[ok])]
        if len(pts) > 1:
            dr.line(pts, fill=(30, 80, 200) if not red else RED, width=3)
    dr.text((x0 + 6, y0 + 4), "頂の線 c(y)/Hc（横 (y − y_pk)/Hc、縦横同じ）　黒＝原画の読み・灰＝その幅　青＝このコマ", fill=TXT, font=fnt(13))


def top_panel(img, dr, box, e_full, xs, ys, m, frame_m):
    x0, y0, x1, y1 = box
    xa, xb, ya = 130.0, 310.0, 90.0
    s = min((x1 - x0) / (xb - xa), (y1 - y0) / (2 * ya))
    sx = (xs >= xa) & (xs <= xb); sy = np.abs(ys) <= ya
    sub = e_full[np.ix_(sy, sx)]
    rgb = colour(np.nan_to_num(sub, nan=-9.0))
    rgb[~np.isfinite(sub)] = (225, 210, 180)
    im = Image.fromarray(rgb[::-1].astype(np.uint8)).resize((int(round((xb - xa) * s)), int(round(2 * ya * s))), Image.NEAREST)
    img.paste(im, (x0, y0))
    X = lambda x: x0 + (x - xa) * s
    Y = lambda y: y0 + (ya - y) * s
    dr.rectangle([x0, y0, x0 + im.size[0], y0 + im.size[1]], outline=(120, 120, 120))
    for xv, lab in ((XC.GC50.X_TOE, "斜面の足"), (XC.X_F, "焦点"), (300.0, "x 300")):
        dr.line([(X(xv), y0), (X(xv), y0 + im.size[1])], fill=(90, 90, 90))
        dr.text((X(xv) + 2, y0 + 2), lab, fill=(40, 40, 40), font=fnt(11))
    if frame_m:
        xp, yp, Hc = frame_m["x"], frame_m["y"], frame_m["Hc"]
        for yy in ((yp, -yp) if abs(yp) >= 1 else (yp,)):
            dr.line([(X(xp) - 7, Y(yy)), (X(xp) + 7, Y(yy))], fill=BLACK, width=2)
            dr.line([(X(xp), Y(yy) - 7), (X(xp), Y(yy) + 7)], fill=BLACK, width=2)
            r = 4.0 * Hc * s
            dr.ellipse([X(xp) - r, Y(yy) - r, X(xp) + r, Y(yy) + r], outline=(60, 60, 60))
    if m and m.get("N1_detail") and (m["N1_detail"] or {}).get("at"):
        ax, ay = m["N1_detail"]["at"]
        if not (xa <= ax <= xb and abs(ay) <= ya):      # outside the drawn window: say where instead of drawing off the panel
            dr.text((x0 + 4, y0 + im.size[1] - 18), "N1 %.2f at x %.0f m, y %.0f m (outside this view)" % (m["N1"], ax, ay), fill=(200, 0, 160), font=fnt(12))
            ax = None
    if m and m.get("N1_detail") and (m["N1_detail"] or {}).get("at") and ax is not None:
        dr.ellipse([X(ax) - 8, Y(ay) - 8, X(ax) + 8, Y(ay) + 8], outline=(200, 0, 160), width=3)
        dr.text((X(ax) + 10, Y(ay) - 8), "N1 %.2f" % m["N1"], fill=(200, 0, 160), font=fnt(12))
    dr.text((x0, y0 + im.size[1] + 4), "上から（x 130〜310 m・|y| ≤ 90 m、縦横同じ、y = 0 で写して両側）　＋＝頂、円＝4 Hc、紫＝いちばん高いほかの山（N1）",
            fill=SUB, font=fnt(12))
    return im.size


def section_panel(dr, box, rd, f, eta0, x_pk, print_phys):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=(255, 255, 255), outline=(150, 150, 150))
    s_, meta = EM.load_frame(rd, "r2", f, "sdf")
    if s_ is None:
        return
    xa, xb, za, zb = x_pk - 45.0, x_pk + 20.0, -6.0, 12.0
    s = min((x1 - x0) / (xb - xa), (y1 - y0 - 18) / (zb - za))
    X = lambda x: x0 + (x - xa) * s
    Z = lambda z: y1 - (z - za) * s
    nz, nx = s_.shape
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nz) - eta0
    sel = (xs >= xa) & (xs <= xb)
    dxp = max(1, int(math.ceil(float(meta["dx"]) * s))); dzp = max(1, int(math.ceil(float(meta["dy"]) * s)))
    top = np.full(nx, np.nan)
    for i in np.where(sel)[0]:
        col = s_[:, i] < 0
        for k in np.where(col & (zs >= za) & (zs <= zb))[0]:
            dr.rectangle([max(X(xs[i]) - 0.5 * dxp, x0 + 1), max(Z(zs[k]) - 0.5 * dzp, y0 + 18), min(X(xs[i]) + 0.5 * dxp, x1 - 1),
                          min(Z(zs[k]) + 0.5 * dzp, y1 - 1)], fill=(70, 120, 200))
        if col.any():
            top[i] = zs[np.where(col)[0].max()]
    dr.line([(X(xa), Z(0.0)), (X(xb), Z(0.0))], fill=GREY)
    if print_phys is not None and np.isfinite(top[sel]).any():
        i = int(np.nanargmax(np.where(sel, top, np.nan)))
        Hs = float(top[i])
        if Hs > 1.0:
            for q in print_phys(float(xs[i]), Hs):
                dr.line([(X(a), Z(b)) for a, b in q], fill=BLACK, width=2)
    dr.text((x0 + 6, y0 + 3), "真ん中の断面（y 0.5 m、縦横同じ）　黒＝原画の頂の輪郭（2D の物差し）", fill=TXT, font=fnt(12))


def table_panel(dr, box, res, t_now, red_n):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=(255, 255, 255), outline=(150, 150, 150))
    dr.text((x0 + 6, y0 + 4), "周期ごとの頂（凍らせた e51 の物差し）。目標 W50 1.5〜2.6・W80 0.8〜1.25・W95 0.4〜0.85・K 2〜4.5・S2 0.05〜0.35",
            fill=TXT, font=fnt(10))
    hdr = ["n", "t s", "Hc m", "x m", "W50", "W80", "W95", "K", "S2", "N1", "miss"]
    cw = [30, 62, 58, 54, 54, 54, 54, 50, 50, 50, 56]
    yy = y0 + 24
    xx = x0 + 8
    for h, w in zip(hdr, cw):
        dr.text((xx, yy), h, fill=SUB, font=fnt(12)); xx += w
    for r in res.get("periods") or []:
        if not r.get("complete") or r.get("W50") is None:
            continue
        yy += 18
        colr = RED if r["n"] == red_n else (TXT if abs(r["t"] - t_now) > 0.6 else ORANGE)
        vals = ["%d" % r["n"], "%.2f" % r["t"], "%.2f" % r["Hc"], "%.0f" % r["x_pk"], "%.2f" % r["W50"], "%.2f" % r["W80"], "%.2f" % r["W95"],
                "%.2f" % r["K"], "%.2f" % r["S2"], "%.2f" % (r.get("N1") or 0.0), "%.2f" % r["miss"]]
        xx = x0 + 8
        for v, w in zip(vals, cw):
            dr.text((xx, yy), v, fill=colr, font=fnt(12)); xx += w
    md = res.get("median") or {}
    yy += 22
    dr.text((x0 + 8, yy), "中央値：Hc %s m・W50 %s・W80 %s・W95 %s・K %s・S2 %s・N1 %s・miss %s" % tuple(
        ("%.2f" % md[k]) if md.get(k) is not None else "-" for k in ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "miss")), fill=TXT, font=fnt(12))
    g = res.get("gates") or {}
    gl = []
    for k, lab in (("G2_inlet_amplitude", "G2"), ("G3_recurrence", "G3"), ("G4_no_band_breaking", "G4"), ("G5_volume", "G5"), ("G6_focus_where_designed", "G6")):
        gl.append("%s %s" % (lab, "○" if (g.get(k) or {}).get("ok") else "×"))
    el = res.get("eligibility") or {}
    gl.append("E1 %s" % ("○" if (el.get("E1_isolation") or {}).get("ok") else "×"))
    gl.append("E3 %s（%s 倍）" % ("○" if (el.get("E3_focusing_gain") or {}).get("ok") else "×",
                                 "%.2f" % el["E3_focusing_gain"]["Hc_over_incoming"] if (el.get("E3_focusing_gain") or {}).get("Hc_over_incoming") else "-"))
    yy += 18
    dr.text((x0 + 8, yy), "門：" + "・".join(gl), fill=TXT, font=fnt(12))
    dr.text((x0 + 8, yy + 18), "数は【測定】、目標の幅は原画からの読み【推測】", fill=SUB, font=fnt(11))


# ====================================================================== the video
def make(rd, res_path=None, out_dir=None, t0=35.0, t1=75.0):
    rd = os.path.abspath(rd).replace("\\", "/")
    rid = os.path.basename(rd)
    if res_path is None:
        for nm in ("judge_E05.json", "screen_E05.json", "screen_E.json"):
            p = os.path.join(rd, "e51", nm)
            if os.path.exists(p):
                res_path = p; break
    res = json.load(open(res_path, encoding="utf8"))
    eta0 = float(res["eta0"])
    cfg = XA.load_cfg(rd)
    case = res.get("case")
    H = XA.HF(rd)
    frames = [f for f in H.frames() if t0 - 1e-9 <= (f - 1) / XA.FPS <= t1 + 1e-9]
    red = res.get("red_instant") or {}
    red_f = red.get("frame"); red_t = red.get("t"); red_n = red.get("n")
    per = {int(r["f"]): r for r in (res.get("periods") or []) if r.get("complete") and r.get("f")}
    try:
        sys.path.insert(0, XC.REPO + "/Tools/GWWaveGen/flip47")
        import g47_video as GV47
        pp = GV47.print_phys
    except Exception:
        pp = None
    # output frame plan
    plan = []
    t = t0
    while t <= t1 + 1e-9:
        if red_t is not None and red_t + SLOW[0] - 1e-9 <= t < red_t + SLOW[1]:
            t = red_t + SLOW[0]
            for f in frames:
                tf = (f - 1) / XA.FPS
                if red_t + SLOW[0] - 1e-9 <= tf <= red_t + SLOW[1] + 1e-9:
                    plan.append((f, "slow"))
                    if f == red_f:
                        plan.extend([(f, "hold")] * int(round(HOLD_S * FPS_OUT)))
            t = red_t + SLOW[1] + STEP_S
            continue
        f = min(frames, key=lambda q: abs((q - 1) / XA.FPS - t))
        plan.append((f, "fast"))
        t += STEP_S
    # camera: static, centred on the red summit (or the median summit)
    xc = float(red.get("x") or (res.get("median") or {}).get("x_pk") or XC.X_F)
    if red_f in per:
        xc = float(per[red_f]["x_pk"])
    Hm = float((res.get("median") or {}).get("Hc") or 6.0)
    box3 = (40, 112, 940, 532)
    cam = Cam(eye=(xc + 75.0, 0.0, 0.9 * Hm + 1.0), look=(xc - 10.0, 0.0, 0.4 * Hm), box=box3, fov_deg=48.0)
    od = XC.guard_out(out_dir or os.path.join(rd, "video"), allow_scratch=True)
    path = os.path.join(od, "%s_E_compare.mp4" % rid).replace("\\", "/")
    proc = subprocess.Popen([XC.GC50.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W_IMG, H_IMG),
                             "-r", str(FPS_OUT), "-i", "-", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
    th, w = XC.components(case) if case in XC.CASES else (None, None)
    t_start = time.time()
    cache = {}
    n_out = 0
    for f, state in plan:
        if f not in cache:
            cache.clear()
            a, meta = H.get(f)
            b = XA.masked_interior(a, meta)
            e_half = EM.median3(b) - eta0
            e_full, ys = EM.mirror_y(e_half, meta)
            xs = EM.xs_of(meta, e_full.shape[1])
            sel = (xs >= XA.SCAN["xr"][0]) & (xs <= XA.SCAN["xr"][1])
            v = np.where(sel[None, :], e_full, np.nan)
            fm = None
            if np.isfinite(v).any():
                iy, ix = np.unravel_index(int(np.nanargmax(v)), v.shape)
                fm = dict(Hc=float(v[iy, ix]), x=float(xs[ix]), y=float(ys[iy]))
            img = Image.new("RGB", (W_IMG, H_IMG), (250, 250, 247))
            dr = ImageDraw.Draw(img)
            tnow = (f - 1) / XA.FPS
            dp = float((cfg.get("parms") or {}).get("dp", res.get("dp") or 1.0))
            dr.text((40, 6), "FLIP51 方案 E %s（%s）　t = %.2f s　粒子 %g m%s" % (
                rid, {"U7": "一様 ±80°", "X2": "交差 ±60° σ28°", "X1": "交差 ±45〜75°"}.get(case, case), tnow, dp,
                "（粗い下見：形は凍らせた数で比べる）" if dp == 1.0 else ""), fill=TXT, font=fnt(19))
            dr.text((40, 36), "選んだ物【選び】：周期 T 7 s・方向と重み・振幅の和 6.33 m（DM1A と同じ、大きくしていない）・焦点 (220.25, 0) と時刻 t = 7n s、海底 D19B。"
                              "計算した物：浅くなる・屈折・集まり・崩れ。力は重力だけ", fill=SUB, font=fnt(14))
            dr.text((40, 58), "赤い太枠＋3 s 止め＝いちばん収束した瞬間（周期の頂の中で凍らせた目標の外れ miss が最小）・橙＝ほかの周期の頂。高さは静かな水面 %.2f m から" % eta0,
                    fill=RED, font=fnt(14))
            dr.text((40, 80), "前から見た 3D（浜の側から、目の高さは頂ほど、色＝高さ、縦横同じ）　黒＝原画の読みの形（幅 3.0/2.0/1.0/0.6 Hc を 20/50/80/95 % で、このコマの頂と Hc に合わせた）",
                    fill=SUB, font=fnt(13))
            sub3 = render3d(img, e_full, xs, ys, cam, xc - 75.0, xc + 32.0, 75.0)
            if fm and fm["Hc"] > 0.5:
                silhouette_3d(sub3, cam, fm["x"], abs(fm["y"]), fm["Hc"])
            paste3d(img, sub3, cam)
            is_red = (f == red_f)
            is_sum = f in per
            crest_panel(dr, (960, 112, 1580, 290), e_full, xs, ys, fm["x"] if fm else xc, fm["y"] if fm else 0.0, fm["Hc"] if fm else None, is_red)
            mrow = per.get(f)
            top_panel(img, dr, (40, 560, 520, 960), e_full, xs, ys, mrow, fm)
            # colour scale
            for k_, (z_, c_) in enumerate(zip(STOPS, COLS)):
                dr.rectangle((1030, 570 + 24 * k_, 1050, 588 + 24 * k_), fill=tuple(int(q) for q in c_))
                dr.text((1056, 570 + 24 * k_), "%+g m" % z_, fill=SUB, font=fnt(12))
            dr.text((1030, 570 + 24 * len(STOPS)), "色＝静かな水面からの高さ", fill=SUB, font=fnt(12))
            section_panel(dr, (560, 560, 1000, 790), rd, f, eta0, fm["x"] if fm else xc, pp)
            table_panel(dr, (960, 300, 1580, 540), res, tnow, red_n)
            # gains and honesty box
            el = res.get("eligibility") or {}
            gr = el.get("gains_report") or {}
            e3 = el.get("E3_focusing_gain") or {}
            lines = ["高さの元（Q39）：Hc の中央値 %s m は、x 110 m の線でいちばん高い来た頂 %s m の %s 倍（集まりの利得）" % (
                         _n((res.get("median") or {}).get("Hc")), _n(e3.get("c_in110_median")), _n(e3.get("Hc_over_incoming"))),
                     "1 つの成分の振幅の最大 %s m の %s 倍、線形の設計の頂 %s m の %s 倍" % (
                         _n(gr.get("a_j_max"), "%.3f"), _n(gr.get("Hc_over_a_j_max"), "%.1f"), _n(gr.get("design_crest_xf")), _n(gr.get("Hc_over_linear_design_crest"))),
                     "周期：頂は %s s ごと（G3）" % ("・".join("%.2f" % v for v in (res.get("gates") or {}).get("G3_recurrence", {}).get("spacings_s", [])) or "-")]
            if th is not None:
                lines.append("方向（h0 で）：%d 成分 %.0f〜%.0f°・重みの最大 %.3f" % (len(th), float(np.min(np.abs(th))), float(np.max(np.abs(th))), float(np.max(w))))
            yy = 800
            for ln in lines:
                dr.text((560, yy), ln, fill=TXT, font=fnt(13)); yy += 20
            # time bar
            tb0, tb1 = 40, 1560
            ytb = 1008
            U = lambda tt: tb0 + (tb1 - tb0) * (tt - t0) / max(t1 - t0, 1e-6)
            dr.rectangle([tb0, ytb, tb1, ytb + 8], fill=(225, 225, 222))
            dr.rectangle([tb0, ytb, U(tnow), ytb + 8], fill=(60, 80, 110))
            for r in res.get("periods") or []:
                if r.get("complete") and r.get("t") is not None:
                    dr.line([(U(r["t"]), ytb - 6), (U(r["t"]), ytb + 14)], fill=RED if r["n"] == red_n else ORANGE, width=3)
            dr.text((tb0, ytb + 12), "%.0f s" % t0, fill=SUB, font=fnt(11)); dr.text((tb1 - 30, ytb + 12), "%.0f s" % t1, fill=SUB, font=fnt(11))
            if is_red or is_sum:
                colr = RED if is_red else ORANGE
                wd = 7 if is_red else 3
                for bb in (box3, (960, 112, 1580, 290)):
                    dr.rectangle([bb[0] - 5, bb[1] - 5, bb[2] + 5, bb[3] + 5], outline=colr, width=wd)
            cache[f] = np.asarray(img, np.uint8).tobytes()
        buf = cache[f]
        if state == "hold" and n_out == 0:
            pass
        proc.stdin.write(buf); n_out += 1
    proc.stdin.close(); proc.wait()
    meta_out = dict(path=path, frames_out=n_out, fps=FPS_OUT, step_s=STEP_S, slow=SLOW, hold_s=HOLD_S, red_instant=red, t_range=[t0, t1],
                    camera=dict(eye=list(cam.C), forward=list(cam.f)), ok=bool(proc.returncode == 0 and os.path.exists(path)),
                    cpu_s=round(time.time() - t_start, 1), result=res_path)
    XC.jdump(meta_out, path.replace(".mp4", ".json"))
    return meta_out


def _n(v, f="%.2f"):
    return (f % v) if isinstance(v, (int, float)) and v is not None and np.isfinite(v) else "-"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    m = make(a[0], res_path=opt.get("res"), out_dir=opt.get("out"), t0=float(opt.get("t0", 35.0)), t1=float(opt.get("t1", 75.0)))
    print(json.dumps(XC.clean(m), ensure_ascii=False))


if __name__ == "__main__":
    main()
