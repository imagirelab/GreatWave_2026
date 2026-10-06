# -*- coding: utf-8 -*-
"""P1 の図と動画（PIL・numpy・cv2 だけ。py -3.10）。
使い方:
  py -3.10 p1_figs.py strip <run_dir> <out.png> [n=8]
      巻く前後のコマの並び（粒子の断面。色＝速さ）。砕けの始まり（B>0.85）から空洞が閉じた 0.5 秒後まで。
  py -3.10 p1_figs.py compare <run_dir> <out.png> [scale_to_20=1]
      比べの表：原画の読み A（横から見た断面、頂 20 m）と、流体のいちばん近いコマの水の形の重ね図と、値の表（R9 は参考）。
  py -3.10 p1_figs.py movie <run_dir> <out.mp4> [t0] [t1]
      断面の動画（波に付いて動く窓。24 コマ/秒の計算の 2 コマごと＝12 コマ/秒を 2 回ずつ出して実時間）。
  py -3.10 p1_figs.py table <out.png> <analysis.json> ...
      探索の表の図。
"""
import sys, os, json, glob, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_analyze as A

FONT = "C:/Windows/Fonts/meiryo.ttc"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
PT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1/painting/painting_section.json"
# R9（見本06）の主の断面の値（Unity/Build/Polish/flip_proposal/C_shape_keep.md の M1・M4・M5・M6。参考だけ）
R9 = {"crest_m": 20.27, "lip_reach_m": 12.0, "lip_drop_m": 8.7, "overhang_main_row_m": 18.5, "overhang_p50_region1_m": 10.4,
      "back_slope_25_75_p50_deg": 63.0, "covered_air_LW_p50": 1.27, "tube_inscribed_r_max_m": 8.9}


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def speed_rgb(sp, vmax=25.0):
    a = np.clip(sp / vmax, 0, 1)[:, None]
    lo = np.array([30, 60, 150], float); mid = np.array([90, 170, 230], float); hi = np.array([255, 250, 235], float)
    c = np.where(a < 0.5, lo + (mid - lo) * (a / 0.5), mid + (hi - mid) * ((a - 0.5) / 0.5))
    return c.astype(np.uint8)


def paint_water(arr, x, y, box, xr, yr, P, col=(200, 222, 242)):
    """断面の水の形（粒子の升目から作った水の範囲。深い所の水を埋めたもの）を薄い青で塗る。"""
    x0, y0, x1, y1 = box
    cnt = A.raster(x, y, xr[0] - 5, xr[1] + 5)
    water, closed = A.water_mask(cnt)
    ny, nx = water.shape
    H_, W_ = y1 - y0, x1 - x0
    # 画素の中心 → 升目
    gx = xr[0] + (np.arange(W_) + 0.5) / W_ * (xr[1] - xr[0])
    gy = yr[1] - (np.arange(H_) + 0.5) / H_ * (yr[1] - yr[0])
    ix = ((gx - (xr[0] - 5)) / A.DX).astype(int); iy = ((gy - A.YMIN) / A.DX).astype(int)
    okx = (ix >= 0) & (ix < nx); oky = (iy >= 0) & (iy < ny)
    sub = np.zeros((H_, W_), bool)
    sub[np.ix_(oky, okx)] = water[np.ix_(iy[oky], ix[okx])]
    # 升目より深い所（y < A.YMIN）は、海底より上なら水
    h0, hr, xs0, n = P["h0"], P["hr"], P["xs0"], P["slope_n"]
    yb = np.minimum(-h0 + np.maximum(0, gx - xs0) / n, -hr)
    deep = (gy[:, None] < A.YMIN + 0.5) & (gy[:, None] > yb[None, :])
    m = sub | deep
    reg = arr[y0:y1, x0:x1]
    reg[m] = col


def draw_particles(arr, x, y, sp, box, xr, yr, bg=(245, 245, 240), P=None):
    x0, y0, x1, y1 = box
    arr[y0:y1, x0:x1] = bg
    if P is not None:
        paint_water(arr, x, y, box, xr, yr, P)
    px = (x0 + (x - xr[0]) / (xr[1] - xr[0]) * (x1 - x0)).astype(int)
    py = (y1 - (y - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)).astype(int)
    m = (px >= x0) & (px < x1) & (py >= y0) & (py < y1)
    col = speed_rgb(sp[m])
    o = np.argsort(sp[m])
    arr[py[m][o], px[m][o]] = col[o]


def snap_at(rd, frame):
    return np.load(os.path.join(rd, "snap_%04d.npz" % frame))


def bed_poly(P, xr):
    h0, hr, xs0, n = P["h0"], P["hr"], P["xs0"], P["slope_n"]
    xs = np.linspace(xr[0], xr[1], 200)
    yb = np.minimum(-h0 + np.maximum(0, xs - xs0) / n, -hr)
    return xs, yb


def strip(rd, out, n=8):
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    tl = an["timeline"]; ev = an["events"]
    A.set_dx(run["parms"])
    tb = ev["breaking_onset_B085"]["t"] if ev["breaking_onset_B085"] else tl[len(tl) // 2]["t"] - 1.0
    tc = ev["tube_closed_or_nearly"]["t"] + 0.5 if ev["tube_closed_or_nearly"] else (ev["face_past_vertical"]["t"] + 2.0 if ev["face_past_vertical"] else tb + 3.0)
    tb -= 0.5
    ts = np.linspace(tb, min(tc, tl[-1]["t"]), n)
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 255, 255)); arr = np.array(img)
    cols = 4; rows = int(math.ceil(n / cols)); pw = W // cols - 20; ph = (H - 140) // rows - 50
    labels = []
    t_ov = ev["face_past_vertical"]["t"] if ev["face_past_vertical"] else None
    for k, tv in enumerate(ts):
        q = min(tl, key=lambda q: abs(q["t"] - tv))
        d = snap_at(rd, q["frame"])
        xc = q["crest"][0]
        xr = (xc - 30, xc + 35); yr = (-12, 26)
        bx = 10 + (k % cols) * (pw + 20); by = 110 + (k // cols) * (ph + 50)
        sp = np.hypot(d["vx"], d["vy"])
        draw_particles(arr, d["x"], d["y"], sp, (bx, by, bx + pw, by + ph), xr, yr, P=run["parms"])
        labels.append((bx, by, q, xr, yr))
    img = Image.fromarray(arr); dr = ImageDraw.Draw(img)
    P = run["parms"]
    zh = float(np.load(os.path.join(rd, "snap_%04d.npz" % tl[0]["frame"]))["zhalf"])
    dr.text((10, 10), "%s　巻く前後の断面（粒子、色＝速さ 0〜25 m/s、切り口 |z|<%.2f m、薄い青＝水の範囲）" % (an["run_id"], zh), fill=(0, 0, 0), font=font(26))
    if float(P.get("wave_mode", 0)) > 0.5:
        sub = "孤立波 高さ %.1f m・沖の水深 %.0f m・坂 1:%.0f（坂は %.0f m の高さまで続く）・粒子 %.2f m。物理だけ（誘導なし）。B＝頂の水の速さ/頂の進む速さ" % (P["Hs"], P["h0"], P["slope_n"], -P["hr"], P["dp"])
    else:
        sub = "T %.0f s・入力 H %.0f m・斜面 1:%.0f・岩棚 %.0f m・粒子 %.2f m。物理だけ（誘導なし）。B＝頂の水の速さ/頂の進む速さ" % (P["T"], P["H"], P["slope_n"], P["hr"], P["dp"])
    dr.text((10, 50), sub, fill=(0, 0, 0), font=font(18))
    for (bx, by, q, xr, yr) in labels:
        dr.rectangle([bx, by, bx + pw, by + ph], outline=(0, 0, 0))
        y0px = by + ph - (0 - yr[0]) / (yr[1] - yr[0]) * ph
        dr.line([(bx, y0px), (bx + pw, y0px)], fill=(180, 180, 180))
        xsb, ysb = bed_poly(P, xr)
        pts = [(bx + (u - xr[0]) / (xr[1] - xr[0]) * pw, by + ph - (v - yr[0]) / (yr[1] - yr[0]) * ph) for u, v in zip(xsb, ysb)]
        pts = [(u, min(max(v, by), by + ph)) for u, v in pts]
        dr.line(pts, fill=(120, 90, 60), width=2)
        rel = (" 張り出しから %+.2f s" % (q["t"] - t_ov)) if t_ov is not None else ""
        dr.text((bx + 4, by - 26), "t=%.2f s%s  x=%.0f m  頂 %.1f m  B=%.2f" % (q["t"], rel, q["crest"][0], q["crest"][1], q.get("B", float("nan"))), fill=(0, 0, 0), font=font(15))
        for yy in (0, 10, 20):
            py = by + ph - (yy - yr[0]) / (yr[1] - yr[0]) * ph
            dr.text((bx + 2, py - 16), "%d m" % yy, fill=(120, 120, 120), font=font(12))
    img.save(out)


def contour_of(rd, frame, xc_guess):
    A.set_dx(json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))["parms"])
    d = snap_at(rd, frame)
    x0 = xc_guess - 80
    cnt = A.raster(d["x"], d["y"], x0, xc_guess + 80)
    water, closed = A.water_mask(cnt)
    body = A.main_component(water) | closed * 0
    import cv2
    cs, _ = cv2.findContours(body.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    res = []
    for c in cs:
        c = c[:, 0, :].astype(float)
        X = x0 + (c[:, 0] + 0.5) * A.DX; Y = A.YMIN + (c[:, 1] + 0.5) * A.DX
        res.append(np.stack([X, Y], -1))
    return res, d


def compare(rd, out, scale20=True):
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    pt = json.load(open(PT, encoding="utf8"))
    RA = pt["readings"]["A_side"]; RB = pt["readings"]["B_sample06_plane"]
    bf = an["best_frame_vs_painting"]["A_side"]
    if not bf:
        print("no overturned frame"); return
    q = [q for q in an["timeline"] if q["frame"] == bf["frame"]][0]
    cs, d = contour_of(rd, q["frame"], q["crest"][0])
    xc, yc = q["crest"]
    s = 20.0 / yc if scale20 else 1.0
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 255, 255)); dr = ImageDraw.Draw(img)
    dr.text((20, 12), "断面の比べ：原画（読み A、頂 20 m）と %s の t=%.2f s（張り出しから %+.2f s）" % (an["run_id"], q["t"], bf["since_overturn_s"] or 0), fill=(0, 0, 0), font=font(26))
    dr.text((20, 52), "流体は頂を横 0 にそろえ、%s。原画の線＝青、流体の水の形の縁＝橙、R9 は値だけ（参考）。" % ("高さ・横を一様に %.3f 倍して頂を 20 m にした" % s if scale20 else "倍率なし"), fill=(0, 0, 0), font=font(18))
    sc = 12.0; ox, oy = 570, 700
    def Pp(x, y):
        return (ox + x * sc, oy - y * sc)
    for yy in range(-10, 31, 5):
        dr.line([Pp(-40, yy), Pp(40, yy)], fill=(235, 235, 235))
        dr.text((Pp(-40, yy)[0] + 2, Pp(-40, yy)[1] - 18), "%d m" % yy, fill=(120, 120, 120), font=font(14))
    dr.line([Pp(-38, 0), Pp(38, 0)], fill=(150, 150, 150), width=2)
    # 流体の粒子（薄く）
    arr = np.array(img)
    m = (np.abs(d["x"] - xc) < 40)
    X = (d["x"][m] - xc) * s; Y = d["y"][m] * s
    px = (ox + X * sc).astype(int); py = (oy - Y * sc).astype(int)
    k = (px > 0) & (px < 1150) & (py > 90) & (py < H)
    arr[py[k], px[k]] = (200, 215, 235)
    img = Image.fromarray(arr); dr = ImageDraw.Draw(img)
    for c in cs:
        # 窓の縁（左右の端・下の端）の線は描かない
        ok = (np.abs(c[:, 0] - xc) < 40) & (c[:, 1] > A.YMIN + 1.0) & (c[:, 0] > xc - 79.0) & (c[:, 0] < xc + 79.0)
        seg = []
        for (u, v), o in zip(c, ok):
            if o:
                seg.append(Pp((u - xc) * s, v * s))
            elif len(seg) > 2:
                dr.line(seg, fill=(230, 120, 20), width=2); seg = []
            else:
                seg = []
        if len(seg) > 2:
            dr.line(seg, fill=(230, 120, 20), width=2)
    for key, colr in (("_outline_outer_xy", (20, 50, 170)), ("_outline_inner_xy", (20, 50, 170))):
        dr.line([Pp(*p) for p in RA[key]], fill=colr, width=4)
    # 表
    rows = [("値", "原画 読み A（主）", "原画 読み B（参考）", "流体（このコマ）", "R9（参考）")]
    def f(v, nd=2):
        return "—" if v is None else ("%.*f" % (nd, v))
    rows += [
        ("頂の高さ Hc (m)", "20.0（そろえた）", "20.0（そろえた）", "%.1f（そろえる前 %.1f）" % (yc * s, yc), "20.27"),
        ("唇の届き / Hc", f(RA["reach_over_Hc"]), f(RB["reach_over_Hc"]), f(q.get("reach_over_Hc")), f(R9["lip_reach_m"] / R9["crest_m"])),
        ("唇の落ち / Hc", f(RA["drop_over_Hc"]), f(RB["drop_over_Hc"]), f(q.get("drop_over_Hc")), f(R9["lip_drop_m"] / R9["crest_m"])),
        ("唇のかぶり / Hc", f(RA["overhang_over_Hc"]), f(RB["overhang_over_Hc"]), f(q.get("overhang_over_Hc")), "%s（主の行）" % f(R9["overhang_main_row_m"] / R9["crest_m"])),
        ("空洞の幅/高さ", f(RA["tube_aspect_w_over_h"]), f(RB["tube_aspect_w_over_h"]), f(q.get("tube_aspect_w_over_h")), "—"),
        ("前の面の弦 (°)", f(RA["front_face_chord_angle_deg"], 0), f(RB["front_face_chord_angle_deg"], 0), f(q.get("front_face_chord_angle_deg"), 0), "—"),
        ("前の面の凹み / Hc", f(RA["front_face_concavity_over_Hc"], 3), f(RB["front_face_concavity_over_Hc"], 3),
         f((q.get("front_face_concavity_m") or 0) / yc, 3) if q.get("front_face_concavity_m") is not None else "—", "—"),
        ("背：頂→0.75Hc の横 / Hc", f(-RA["back"]["x_at_0.75Hc"] / 20.0), "（読めない）", f((q.get("back_dx_to_075Hc_m") or float("nan")) / yc), "—"),
        ("背：頂→0.75Hc の傾き (°)", f(math.degrees(math.atan2(5.0, -RA["back"]["x_at_0.75Hc"])), 0), "—", f(q.get("back_slope_crest_to_075Hc_deg"), 0), "—"),
        ("背の傾き 0.25–0.75Hc (°)", "（画面で切れる）", "—", f(q.get("back_slope_25_75_deg"), 0), "63（p50）"),
        ("前の谷 (m)", "（隠れて見えない）", "—", f(q.get("trough_ahead_m"), 1), "−5.7"),
        ("空洞の内接円の半径 (m)", "—", "—", f(q.get("tube_inscribed_r_m"), 1), "最大 8.9"),
    ]
    tx, ty = 1090, 120
    cw = [225, 140, 140, 190, 100]
    for i, r in enumerate(rows):
        x = tx
        for j, c in enumerate(r):
            dr.text((x, ty + i * 34), str(c), fill=(0, 0, 0) if i else (60, 60, 60), font=font(15 if i else 14))
            x += cw[j]
    dr.text((tx, ty + len(rows) * 34 + 20), "比べのコマ：張り出しのあるコマ（空洞が閉じた 1 秒後まで）のうち、\n届き・落ち・かぶり（/Hc）の差の 2 乗和が最小のコマ（読み A に対して）。\n形の値の定義は p1_analyze.py の頭の説明。原画の輪郭の読み方は painting_section.json。", fill=(60, 60, 60), font=font(14))
    img.save(out)


def movie(rd, out, t0=None, t1=None):
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    P = run["parms"]
    tl = an["timeline"]
    A.set_dx(P)
    t0 = tl[0]["t"] if t0 is None else float(t0)
    t1 = tl[-1]["t"] if t1 is None else float(t1)
    fr = [q for q in tl if t0 <= q["t"] <= t1]
    tmp = os.path.join(rd, "_movie"); os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(os.path.join(tmp, "*.png")):
        os.remove(f)
    W, H = 1280, 720
    ev = an["events"]
    # 窓は頂に付いて動くが、ゆっくり（頂の x を ±1 秒でならす）
    tt = np.array([q["t"] for q in tl]); xx = np.array([q["crest"][0] for q in tl])
    for k, q in enumerate(fr):
        sel = np.abs(tt - q["t"]) <= 1.0
        xm = float(np.mean(xx[sel]))
        xr = (xm - 70, xm + 50); yr = (-30, 30)
        d = snap_at(rd, q["frame"])
        arr = np.full((H, W, 3), 255, np.uint8)
        box = (0, 60, W, H - 40)
        draw_particles(arr, d["x"], d["y"], np.hypot(d["vx"], d["vy"]), box, xr, yr, P=P)
        img = Image.fromarray(arr); dr = ImageDraw.Draw(img)
        xsb, ysb = bed_poly(P, xr)
        bx0, by0, bx1, by1 = box
        pts = [(bx0 + (u - xr[0]) / (xr[1] - xr[0]) * (bx1 - bx0), by1 - (v - yr[0]) / (yr[1] - yr[0]) * (by1 - by0)) for u, v in zip(xsb, ysb)]
        dr.polygon(pts + [(bx1, by1), (bx0, by1)], fill=(150, 120, 90))
        y0px = by1 - (0 - yr[0]) / (yr[1] - yr[0]) * (by1 - by0)
        dr.line([(0, y0px), (W, y0px)], fill=(190, 190, 190))
        dr.text((10, 8), "%s　t=%.2f s　頂 x=%.0f m・高さ %.1f m　B=%.2f" % (an["run_id"], q["t"], q["crest"][0], q["crest"][1], q.get("B", float("nan"))), fill=(0, 0, 0), font=font(22))
        tag = []
        if ev["breaking_onset_B085"] and q["t"] >= ev["breaking_onset_B085"]["t"]:
            tag.append("B>0.85")
        if ev["face_past_vertical"] and q["t"] >= ev["face_past_vertical"]["t"]:
            tag.append("前の面が垂直を過ぎた")
        if ev["tube_closed_or_nearly"] and q["t"] >= ev["tube_closed_or_nearly"]["t"]:
            tag.append("空洞が閉じた")
        dr.text((10, 36), "物理だけ（誘導なし）。粒子の断面、色＝速さ 0〜25 m/s。茶＝海底（見えない岩棚）。" + ("　" + "・".join(tag) if tag else ""), fill=(40, 40, 40), font=font(16))
        # 時間の帯
        frac = (q["t"] - t0) / max(t1 - t0, 1e-6)
        dr.rectangle([10, H - 28, W - 10, H - 12], outline=(0, 0, 0))
        dr.rectangle([10, H - 28, 10 + frac * (W - 20), H - 12], fill=(80, 120, 200))
        for key, colr in (("breaking_onset_B085", (220, 160, 0)), ("face_past_vertical", (220, 60, 20)), ("tube_closed_or_nearly", (150, 0, 150))):
            if ev[key]:
                fx = 10 + (ev[key]["t"] - t0) / max(t1 - t0, 1e-6) * (W - 20)
                dr.line([(fx, H - 32), (fx, H - 8)], fill=colr, width=3)
        img.save(os.path.join(tmp, "m_%05d.png" % k))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "m_%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", "24", out], check=True)
    print("movie", out, len(fr), "frames")


def table(out, files):
    rows = []
    for fpath in files:
        a = json.load(open(fpath, encoding="utf8"))
        rows.append(a)
    W = 1920; H = 140 + 40 * len(rows)
    img = Image.new("RGB", (W, H), (255, 255, 255)); dr = ImageDraw.Draw(img)
    hdr = ["計算", "T", "入力H", "足元H", "1:n", "岩棚", "B最大", "B>0.85 t/x", "垂直を過ぎた t/x", "閉じた t", "頂(張出前)", "巻き波", "届き/Hc", "落ち/Hc", "かぶり/Hc", "時間"]
    cw = [250, 50, 70, 80, 50, 60, 70, 150, 160, 90, 110, 80, 90, 90, 100, 90]
    x = 10
    for j, h in enumerate(hdr):
        dr.text((x, 20), h, fill=(0, 0, 0), font=font(16)); x += cw[j]
    for i, a in enumerate(rows):
        ev = a["events"]; P = a["parms"]
        bf = a["best_frame_vs_painting"]["A_side"]
        q = [q for q in a["timeline"] if bf and q["frame"] == bf["frame"]]
        q = q[0] if q else {}
        def g(e, k):
            return ("%.1f/%.0f" % (e["t"], e["x"])) if e else "—"
        sol = P.get("wave_mode", 0) > 0.5
        vals = [a["run_id"], "—" if sol else "%.0f" % P.get("T", 0), "%.0f" % P.get("H", 0) if not sol else "孤%.0f" % P.get("Hs", 0),
                "%.1f" % a["toe_gauge"].get("H_toe_m", float("nan")) if "H_toe_m" in a.get("toe_gauge", {}) else "—",
                "%.0f" % P.get("slope_n", 0), ("沖%.0f" % P.get("h0", 0)) if sol else "%.0f" % P.get("hr", 0), "%.2f" % (a["events"]["B_max"] or 0),
                g(ev["breaking_onset_B085"], 0), g(ev["face_past_vertical"], 0),
                ("%.1f" % ev["tube_closed_or_nearly"]["t"]) if ev["tube_closed_or_nearly"] else "—",
                "%.1f" % (ev["crest_max_before_overturn_m"] or 0), "はい" if a["plunging"] else "いいえ",
                "%.2f" % q["reach_over_Hc"] if "reach_over_Hc" in q else "—", "%.2f" % q["drop_over_Hc"] if "drop_over_Hc" in q else "—",
                "%.2f" % q["overhang_over_Hc"] if "overhang_over_Hc" in q else "—", "%.0f s" % (a["wall_total_s"] or 0)]
        x = 10
        for j, v in enumerate(vals):
            dr.text((x, 60 + i * 40), str(v), fill=(0, 0, 0), font=font(15)); x += cw[j]
    img.save(out)


def _main():
    cmd = sys.argv[1]
    if cmd == "strip":
        strip(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3], (sys.argv[4] != "0") if len(sys.argv) > 4 else True)
    elif cmd == "movie":
        movie(sys.argv[2], sys.argv[3], *(sys.argv[4:6]))
    elif cmd == "table":
        table(sys.argv[2], sys.argv[3:])
    elif cmd == "overview":
        overview(sys.argv[2], sys.argv[3:])


def overview(out, rids):
    """探索の全部の計算の、原画（読み A）にいちばん近いコマを 4×4 に並べる。"""
    W, H = 1920, 1200
    img = Image.new("RGB", (W, H), (255, 255, 255)); arr = np.array(img)
    cols = 4; pw = W // cols - 16; ph = (H - 130) // 4 - 44
    labs = []
    for k, rid in enumerate(rids):
        rd = os.path.join(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1", rid)
        an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
        run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
        A.set_dx(run["parms"])
        bf = an["best_frame_vs_painting"]["A_side"]
        if not bf:
            continue
        q = [q for q in an["timeline"] if q["frame"] == bf["frame"]][0]
        d = snap_at(rd, q["frame"])
        xc = q["crest"][0]
        xr = (xc - 30, xc + 35); yr = (-10, 26)
        bx = 8 + (k % cols) * (pw + 16); by = 125 + (k // cols) * (ph + 44)
        draw_particles(arr, d["x"], d["y"], np.hypot(d["vx"], d["vy"]), (bx, by, bx + pw, by + ph), xr, yr, P=run["parms"])
        labs.append((bx, by, rid, q, bf, run["parms"], an))
    img = Image.fromarray(arr); dr = ImageDraw.Draw(img)
    dr.text((10, 10), "P1 探索：16 の組み合わせの、原画（読み A）にいちばん近いコマ（どれも物理だけ、誘導なし）", fill=(0, 0, 0), font=font(26))
    dr.text((10, 46), "窓は頂の 30 m 後ろから 35 m 前、高さ −10〜26 m（縦横同じ縮尺）。灰色の線＝静かな水面。粒子の色＝速さ。S01 だけ粒子 0.35 m、ほかは 0.5 m", fill=(60, 60, 60), font=font(17))
    for (bx, by, rid, q, bf, P, an) in labs:
        dr.rectangle([bx, by, bx + pw, by + ph], outline=(0, 0, 0))
        y0px = by + ph - (0 - (-10)) / 36.0 * ph
        dr.line([(bx, y0px), (bx + pw, y0px)], fill=(150, 150, 150))
        dr.text((bx + 2, by - 40), "%s" % rid.replace("_d05", ""), fill=(0, 0, 0), font=font(15))
        dr.text((bx + 2, by - 20), "t=%.2f（張り出し%+.2f s） 頂 %.1f m 点数 %.3f" % (q["t"], bf["since_overturn_s"] or 0, q["crest"][1], bf["score_run"]), fill=(60, 60, 60), font=font(13))
    img.save(out)


if __name__ == "__main__":
    _main()
