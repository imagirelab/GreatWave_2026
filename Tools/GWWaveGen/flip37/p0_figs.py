# -*- coding: utf-8 -*-
"""P0 の図（PIL だけで描く。1920×1080 の PNG）。py -3.10 で実行する。
使い方:
  py -3.10 p0_figs.py still <out.png> '<run_dir>|<見出し>' ['<run_dir>|<見出し>' ...]
      静かな水：水面 η(x, t) の時空間図（色 ±vmax m）と、粒子の縦断面（最後のスナップ）を run ごとに 1 段ずつ。
  py -3.10 p0_figs.py wave <out.png> <analysis.json> <run_dir>[,<run_dir2>] <見出し>
      小さな波：η(x) のいくつかの時刻の線と、窓ごとの進む波の高さ・反射率。
"""
import sys, os, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/meiryo.ttc"
W, H = 1920, 1080


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def diverging(v, vmax):
    """-vmax 青 → 0 白 → +vmax 赤。NaN は灰色。"""
    a = np.clip(v / vmax, -1, 1)
    r = np.where(a > 0, 1.0, 1.0 + a)
    g = 1.0 - np.abs(a)
    b = np.where(a < 0, 1.0, 1.0 - a)
    rgb = (np.stack([r, g, b], -1) * 255).astype(np.uint8)
    rgb[np.isnan(v)] = (128, 128, 128)
    return rgb


def panel_spacetime(img, d, box, x, t, eta, vmax, title):
    x0, y0, x1, y1 = box
    rgb = diverging(eta[::-1], vmax)  # 上が後の時刻
    im = Image.fromarray(rgb).resize((x1 - x0, y1 - y0), Image.NEAREST)
    img.paste(im, (x0, y0))
    d.rectangle(box, outline=(0, 0, 0))
    d.text((x0, y0 - 30), title, fill=(0, 0, 0), font=font(20))
    for xv in range(0, int(x.max()) + 1, 100):
        px = x0 + (xv - x[0]) / (x[-1] - x[0]) * (x1 - x0)
        d.line([(px, y1), (px, y1 + 6)], fill=(0, 0, 0))
        d.text((px - 12, y1 + 8), str(xv), fill=(0, 0, 0), font=font(14))
    for tv in range(0, int(t.max()) + 1, 2):
        py = y1 - (tv - t[0]) / max(t[-1] - t[0], 1e-9) * (y1 - y0)
        d.text((x0 - 40, py - 8), "%ds" % tv, fill=(0, 0, 0), font=font(14))


def panel_particles(img, d, box, sx, sy, xr, yr, title):
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=(0, 0, 0), fill=(250, 250, 250))
    px = x0 + (sx - xr[0]) / (xr[1] - xr[0]) * (x1 - x0)
    py = y1 - (sy - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
    m = (px >= x0) & (px < x1) & (py >= y0) & (py < y1)
    arr = np.array(img)
    arr[py[m].astype(int), px[m].astype(int)] = (20, 60, 160)
    img.paste(Image.fromarray(arr))
    d = ImageDraw.Draw(img)
    for yv in (-60, -40, -26, -20, 0):
        if yr[0] <= yv <= yr[1]:
            p = y1 - (yv - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
            d.text((x0 - 40, p - 8), "%d" % yv, fill=(0, 0, 0), font=font(14))
    d.text((x0, y0 - 30), title, fill=(0, 0, 0), font=font(20))
    return d


def still(out, specs):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    n = len(specs)
    vmax = float(os.environ.get("P0_VMAX", "0.3"))
    head = os.environ.get("P0_HEAD", "P0 T1 静かな水 10 秒")
    d.text((40, 10), "%s：左＝水面の高さ η(x,t)（色 ±%.1f m、赤＝高い）、右＝粒子の縦断面（z≈0、最後のスナップ）" % (head, vmax), fill=(0, 0, 0), font=font(24))
    rowh = (H - 80) // n
    for i, sp in enumerate(specs):
        rd, title = sp.split("|", 1)
        e = np.load(os.path.join(rd, "eta.npz"))
        y0 = 80 + i * rowh + 30
        panel_spacetime(img, d, (60, y0, 960, y0 + rowh - 70), e["x"], e["t"], e["eta"], vmax, title + "：η(x,t)")
        snaps = sorted(glob.glob(os.path.join(rd, "snap_*.npz")))
        s = np.load(snaps[-1])
        d = panel_particles(img, d, (1040, y0, 1880, y0 + rowh - 70), s["x"], s["y"], (0, float(e["x"].max())), (-63, 4),
                            title + "：粒子 %s（全体 %d 個）" % (os.path.basename(snaps[-1])[5:9], int(s["n"])))
    img.save(out)


def wave(out, ana_path, rds, title):
    A = json.load(open(ana_path, encoding="utf8"))
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 10), title, fill=(0, 0, 0), font=font(24))
    xs = None; ts = []; es = []
    for rd in rds:
        e = np.load(os.path.join(rd, "eta.npz"))
        xs = e["x"]
        keep = np.ones(len(e["frames"]), bool) if not ts else e["t"] > max(np.concatenate(ts))
        ts.append(e["t"][keep]); es.append(e["eta"][keep])
    t = np.concatenate(ts); eta = np.concatenate(es)
    # 上：η(x) を 6 つの時刻で
    box = (100, 80, 1860, 500)
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=(0, 0, 0))
    yr = (-3.0, 3.0)
    cols = [(30, 30, 30), (200, 40, 40), (40, 120, 200), (40, 160, 60), (160, 60, 160), (220, 140, 20)]
    for j, tv in enumerate(np.linspace(0, t.max(), 6)):
        i = int(np.argmin(np.abs(t - tv)))
        px = x0 + (xs - xs[0]) / (xs[-1] - xs[0]) * (x1 - x0)
        py = y1 - (np.nan_to_num(eta[i]) - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
        d.line(list(zip(px, py)), fill=cols[j], width=2)
        d.text((x1 - 160, y0 + 10 + 22 * j), "t = %.1f s" % t[i], fill=cols[j], font=font(18))
    for xv in range(0, int(xs.max()) + 1, 100):
        p = x0 + (xv - xs[0]) / (xs[-1] - xs[0]) * (x1 - x0)
        d.text((p - 12, y1 + 6), str(xv), fill=(0, 0, 0), font=font(14))
    for yv in (-3, -1.5, 0, 1.5, 3):
        p = y1 - (yv - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
        d.text((x0 - 50, p - 8), "%.1f" % yv, fill=(0, 0, 0), font=font(14))
    d.text((x0, y0 - 26 + 0), "水面 η(x)（m）", fill=(0, 0, 0), font=font(18))
    # 下：窓ごとの H_incident と Kr
    box = (100, 580, 1860, 1000)
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=(0, 0, 0))
    Wn = A["windows"]
    Hmax = 4.0
    for w in Wn:
        p0 = x0 + (w["x0"] - xs[0]) / (xs[-1] - xs[0]) * (x1 - x0)
        p1 = x0 + (w["x1"] - xs[0]) / (xs[-1] - xs[0]) * (x1 - x0)
        pc = (p0 + p1) / 2
        ph = y1 - w["H_incident"] / Hmax * (y1 - y0)
        pk = y1 - min(w["Kr"], 1.0) * (y1 - y0)
        d.ellipse([pc - 6, ph - 6, pc + 6, ph + 6], fill=(40, 120, 200))
        d.rectangle([pc - 5, pk - 5, pc + 5, pk + 5], fill=(200, 40, 40))
        d.text((pc - 30, ph - 30), "%.2f m" % w["H_incident"], fill=(40, 120, 200), font=font(14))
        d.text((pc - 20, pk + 8), "%.0f%%" % (100 * w["Kr"]), fill=(200, 40, 40), font=font(14))
    for xv in range(0, int(xs.max()) + 1, 100):
        p = x0 + (xv - xs[0]) / (xs[-1] - xs[0]) * (x1 - x0)
        d.text((p - 12, y1 + 6), str(xv), fill=(0, 0, 0), font=font(14))
    p = y1 - 3.0 / Hmax * (y1 - y0)
    d.line([(x0, p), (x1, p)], fill=(150, 150, 220))
    d.text((x0 + 4, p - 20), "H = 3 m（入力）", fill=(100, 100, 200), font=font(14))
    p = y1 - 0.10 * (y1 - y0)
    d.line([(x0, p), (x1, p)], fill=(230, 150, 150))
    d.text((x0 + 4, p - 20), "反射率 10 %", fill=(200, 100, 100), font=font(14))
    hl = A.get("height_loss_2L", {})
    d.text((x0, y0 - 26), "窓ごと：青丸＝進む波の高さ（m、目盛 0〜4）、赤四角＝反射率（目盛 0〜100 %%）。時間窓 %.1f〜%.1f s。最初と最後の窓（中心の間 %.2f 波長）の間の減り %.1f %%" % (
        A["t_window"][0], A["t_window"][1], hl.get("distance_over_L", 0), 100 * hl.get("loss_frac", 0)), fill=(0, 0, 0), font=font(18))
    img.save(out)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "still":
        still(sys.argv[2], sys.argv[3:])
    elif mode == "wave":
        wave(sys.argv[2], sys.argv[3], sys.argv[4].split(","), sys.argv[5])
