# -*- coding: utf-8 -*-
# 確かめの役（2026-10-13）：P1c の 112〜142 s（k6・k7・数えられていない巻き・k8）の確かめの動画を記録の生の断面から描く。使い方：py -3.10 -B x47_pchk_video.py <一時の置き場所> 2690 3400
# 読むだけ（書くのは c7 の動画だけ、Unity/Build/FLIP47/videos の中）。
# checker video: P1c 110-145 s, whole-domain section + crest-following zoom; marks counted events (k6, k7, k8) and the
# uncounted plunging breaker at 128-131 s; print outline overlaid on k8 at its closest frame 3360. Reads raw records only.
import sys, os, json, glob, math, subprocess, shutil
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
sys.dont_write_bytecode = True
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
import g47_video as GV                     # read only: print outline in eta_c units (same transform as the run videos)
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Unity/Build/STUDY52/tools")
import s52_shape as S52
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/"
RUN = "runs/P1c_S2beach_H12_vcx_dp0p25"
OUTV = B + "videos/CHECK_P1c_k6-k8_missed_breaker_and_spike.mp4"
TMP = sys.argv[1]
if len(sys.argv) > 4: OUTV = sys.argv[4]
F0, F1 = int(sys.argv[2]), int(sys.argv[3])
FF = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
rd = B + RUN; name = os.path.basename(RUN)
cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
ana = json.load(open(B + "runs/PERIODIC_compare/periodic_ana_%s.json" % name, encoding="utf8"))
off = float(ana["still_offset_m"]); bed = np.array(cfg["bed"], float)
best = {}
for p in glob.glob(rd + "/sec_c*_b*.npz"):
    f0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
    d = np.load(p); m = json.loads(str(d["meta"]))
    if m["ny"] != 78: continue
    for i, f in enumerate(d["frames"]):
        f = int(f)
        if f not in best or best[f][0] <= f0: best[f] = (f0, p, i, m)
cache = {}
def get(f):
    f0, p, i, m = best[f]
    if p not in cache:
        cache.clear(); cache[p] = np.load(p)["sdf"]
    S = cache[p][i].astype(np.float32)
    xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); ys = m["y0"] + m["dy"] * np.arange(S.shape[0]) - off
    return S, xs, ys
def bed_y(x): return np.interp(x, bed[:, 0], -bed[:, 1])
FONT = "C:/Windows/Fonts/YuGothM.ttc"; FONTB = "C:/Windows/Fonts/YuGothB.ttc"
fn = lambda s, b=False: ImageFont.truetype(FONTB if b else FONT, s)
F14, F16, F18, F20, F26, F34 = fn(14), fn(16), fn(18), fn(20, True), fn(26, True), fn(34, True)
BG = (247, 247, 244); WAT = (38, 86, 128); SAND = (196, 178, 140); RED = (200, 40, 40); ORA = (230, 120, 0); GRN = (30, 140, 60)
W, H = 1920, 1080
# events (reported) and the uncounted breaker found by the checker
EV = [(e["k"], e["on_frame"], e["x_b"], (e.get("touchdown") or {}).get("frame"), (e.get("best3") or {}).get("frame")) for e in ana["events"] if e.get("on_frame")]
MISSED = dict(f0=3060, f1=3160, x0=623.0, x1=676.0, note="数えられていない巻き（g47_video の k_all 19、0.6T の決まりで落ちた）")
PR = GV.print_ref()["cn"]          # [outer, inner] in eta_c units, crest at (0, 1)
K8_BEST = dict(f=3360, eta=9.28, xc=620.1)

def render_field(S, xs, ys, x0, x1, y0, y1, w, h):
    XX = x0 + (np.arange(w) + 0.5) * (x1 - x0) / w; YY = y1 - (np.arange(h) + 0.5) * (y1 - y0) / h
    fx = (XX - xs[0]) / (xs[1] - xs[0]); fy = (YY - ys[0]) / (ys[1] - ys[0])
    ix = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2); wx = np.clip(fx - ix, 0, 1)
    iy = np.clip(np.floor(fy).astype(int), 0, len(ys) - 2); wy = np.clip(fy - iy, 0, 1)
    A = S[iy][:, ix] * (1 - wx) + S[iy][:, ix + 1] * wx; Bq = S[iy + 1][:, ix] * (1 - wx) + S[iy + 1][:, ix + 1] * wx
    F = A * (1 - wy)[:, None] + Bq * wy[:, None]
    by = bed_y(XX)
    arr = np.empty((h, w, 3), np.uint8); arr[:] = (255, 255, 255)
    arr[F < 0] = WAT
    arr[YY[:, None] < by[None, :]] = SAND
    sw = np.abs(YY - 0.0).argmin()
    arr[sw, ::6] = (150, 150, 150)
    return Image.fromarray(arr), XX, YY

def top_surface(S, ys):
    Wm = S < 0
    has = Wm.any(0); jt = Wm.shape[0] - 1 - np.argmax(Wm[::-1], 0)
    return np.where(has, ys[jt], np.nan)

zc = None
os.makedirs(TMP, exist_ok=True)
seq = []
for f in range(F0, F1 + 1):
    seq.append(f)
    if f in (3089, K8_BEST["f"]):
        seq += [f] * 36                       # 1.5 s hold
n = 0
for f in seq:
    if f not in best: continue
    S, xs, ys = get(f)
    t = (f - 1) / 24.0
    img = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(img)
    dr.text((30, 14), "確かめの役の動画（FLIP47 P1c_S2beach_H12_vcx_dp0p25、記録の生の断面から描いた）", font=F26, fill=(20, 20, 20))
    dr.text((30, 54), "海底：水深 19 m の平ら（x < 570 m）→ 勾配 1:10 で浜（静かな水面の線 x 760 m）。波：流れ関数の規則波 T 14 s・入れる H 12 m。粒子 0.25 m（格子 0.5 m）。重力だけ・水だけ。板の層 z −0.25 m。", font=F16, fill=(60, 60, 60))
    dr.text((30, 78), "高さは静かな水面から（ずれ %.3f m を引いた）。縦横同じ縮尺。青＝水、砂色＝海底。数は【測った】（確かめの役が記録から）。" % off, font=F16, fill=(60, 60, 60))
    dr.text((1560, 10), "t = %.2f s" % t, font=F34, fill=(10, 10, 10))
    dr.text((1560, 56), "コマ %d" % f, font=F18, fill=(60, 60, 60))
    # ---- top panel: whole domain
    tx0, tx1, ty0, ty1 = 144.0, 900.0, -20.0, 16.0
    tw = 1860; th = int(tw * (ty1 - ty0) / (tx1 - tx0))
    timg, _, _ = render_field(S, xs, ys, tx0, tx1, ty0, ty1, tw, th)
    TY = 130
    dr.text((30, TY - 26), "領域の全部（x 144〜900 m）", font=F20, fill=(20, 20, 20))
    img.paste(timg, (30, TY))
    sx = lambda x: 30 + (x - tx0) / (tx1 - tx0) * tw
    sy = lambda y: TY + (ty1 - y) / (ty1 - ty0) * th
    for gx in range(200, 901, 100):
        dr.line([(sx(gx), TY + th), (sx(gx), TY + th + 6)], fill=(80, 80, 80)); dr.text((sx(gx) - 14, TY + th + 6), "%d" % gx, font=F14, fill=(60, 60, 60))
    dr.line([(sx(160), sy(0)), (sx(160), sy(10))], fill=RED, width=3); dr.text((sx(160) + 5, sy(10)), "10 m", font=F14, fill=RED)
    # markers: counted events near now, and the missed breaker
    for k, on, xb, td, b3 in EV:
        if on - 36 <= f <= (td or on + 48) + 24:
            dr.line([(sx(xb), TY - 4), (sx(xb), TY + th)], fill=RED, width=2)
            dr.text((sx(xb) + 3, TY + 2), "数えた k%d（巻き始め x_b %.0f m）" % (k, xb), font=F14, fill=RED)
    if MISSED["f0"] <= f <= MISSED["f1"] + 24:
        dr.rectangle([sx(MISSED["x0"]), TY + 2, sx(MISSED["x1"]), TY + th - 2], outline=ORA, width=3)
        dr.text((sx(MISSED["x0"]), TY + th + 22), "橙の枠：数えられていない大きな巻き（開いた覆い 最大 24.5 m・隙間 12 m）", font=F16, fill=ORA)
    # ---- zoom: follow the highest robust crest in x 590-720
    tp = top_surface(S, ys)
    tpm = ndi.median_filter(np.nan_to_num(tp, nan=-30), size=5)
    sel = (xs >= 590) & (xs <= 720)
    xi = xs[sel][np.argmax(tpm[sel])]
    zc = xi if zc is None else zc + 0.15 * (xi - zc)
    zw = 70.0; zx0 = zc - 0.55 * zw; zx1 = zx0 + zw; zy0, zy1 = -20.0, 18.0
    zwp = 1100; zhp = int(zwp * (zy1 - zy0) / zw)
    zimg, _, _ = render_field(S, xs, ys, zx0, zx1, zy0, zy1, zwp, zhp)
    ZY = TY + th + 60
    dr.text((30, ZY - 28), "拡大：砕け帯の一番高い頂を追う窓（幅 70 m、縦横同じ縮尺）", font=F20, fill=(20, 20, 20))
    img.paste(zimg, (30, ZY))
    zx = lambda x: 30 + (x - zx0) / zw * zwp
    zy = lambda y: ZY + (zy1 - y) / (zy1 - zy0) * zhp
    for gx in range(int(math.ceil(zx0 / 10) * 10), int(zx1) + 1, 10):
        dr.line([(zx(gx), ZY + zhp), (zx(gx), ZY + zhp + 6)], fill=(80, 80, 80)); dr.text((zx(gx) - 14, ZY + zhp + 6), "%d" % gx, font=F14, fill=(60, 60, 60))
    dr.line([(zx(zx0) + 20, zy(0)), (zx(zx0) + 20, zy(10))], fill=RED, width=4); dr.text((zx(zx0) + 26, zy(10) - 4), "10 m", font=F18, fill=RED)
    dr.line([(zx(zx0) + 40, zy(-18)), (zx(zx0 + 5) + 40, zy(-18))], fill=RED, width=4); dr.text((zx(zx0 + 5) + 46, zy(-18) - 12), "5 m", font=F18, fill=RED)
    if f == K8_BEST["f"]:
        for i, ln in enumerate(PR):
            pts = [(zx(K8_BEST["xc"] + K8_BEST["eta"] * p[0]), zy(K8_BEST["eta"] * p[1])) for p in ln]
            dr.line(pts, fill=(0, 0, 0), width=3)
        dr.text((40, ZY + 6), "黒＝原画の輪郭（伸びを戻した形）を η_c 9.28 m・頂 x 620.1 m に合わせた（k8 の原画に最も近いコマ 3360）", font=F16, fill=(0, 0, 0))
    # ---- right panel: what the checker found
    RX = 1160; RY = ZY
    lines = [
        ("確かめの役が見た事【測った】", F20, (20, 20, 20)),
        ("・k6（数えた、巻き始め 113.21 s）：頂 4.9 m の平らな頂の前の段。", F16, (40, 40, 40)),
        ("  0.9 s 後に前の面から細い縦の水の板（1〜2 格子）が 10 m 以上立つ。", F16, (40, 40, 40)),
        ("・k7（数えた、124.08 s、x 707 m、水深 5.3 m）：浅い所の小さな巻き。", F16, (40, 40, 40)),
        ("・128.5〜131.6 s、x 623〜676 m：大きな巻き（開いた覆い 24.5 m）", F16, ORA),
        ("  が数えられていない（k_all 19、k7 の 2.3 s 後なので落ちた）。", F16, ORA),
        ("・k8（139.21 s）の巻き始めの頂 12.43 m は、1〜2 格子の幅の", F16, (40, 40, 40)),
        ("  とがり（約 2.2 m）の高さ。2.5 m の中央値で 10.2 m。", F16, (40, 40, 40)),
        ("  本当の巻きは 139.7 s から。コマ 3360 は score3 0.00 を再現した。", F16, (40, 40, 40)),
        ("・赤の線＝数えた崩れの x_b（巻き始めの頂の x）。", F16, RED),
    ]
    yy = RY
    for s, ft, col in lines:
        dr.text((RX, yy), s, font=ft, fill=col); yy += 30 if ft is F20 else 24
    if f in (3089,) :
        dr.rectangle([RX - 6, yy + 6, RX + 740, yy + 40], fill=ORA); dr.text((RX, yy + 10), "止め：数えられていない巻き（コマ 3089）1.5 s", font=F18, fill=(255, 255, 255))
    if f == K8_BEST["f"]:
        dr.rectangle([RX - 6, yy + 6, RX + 740, yy + 40], fill=GRN); dr.text((RX, yy + 10), "止め：k8 の原画に最も近いコマ 3360（score3 0.00）1.5 s", font=F18, fill=(255, 255, 255))
    # timeline
    LY = H - 40
    dr.line([(30, LY), (W - 30, LY)], fill=(160, 160, 160), width=6)
    tl = lambda ff: 30 + (ff - F0) / (F1 - F0) * (W - 60)
    dr.line([(30, LY), (tl(f), LY)], fill=(40, 60, 90), width=6)
    for k, on, xb, td, b3 in EV:
        if F0 <= on <= F1:
            dr.line([(tl(on), LY - 12), (tl(on), LY + 6)], fill=RED, width=2); dr.text((tl(on) + 2, LY + 4), "k%d" % k, font=F14, fill=RED)
    dr.rectangle([tl(MISSED["f0"] + 16), LY - 10, tl(MISSED["f1"]), LY - 4], fill=ORA)
    dr.text((30, LY - 30), "t %.0f s" % ((F0 - 1) / 24), font=F14, fill=(60, 60, 60)); dr.text((W - 90, LY - 30), "t %.0f s" % ((F1 - 1) / 24), font=F14, fill=(60, 60, 60))
    img.save(os.path.join(TMP, "f%05d.png" % n)); n += 1
print("frames", n)
cmd = [FF, "-v", "error", "-y", "-framerate", "24", "-i", os.path.join(TMP, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", OUTV]
subprocess.run(cmd, check=True)
print(OUTV)
