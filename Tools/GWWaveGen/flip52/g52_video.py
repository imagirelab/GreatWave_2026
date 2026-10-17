# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: the compare video of one run (py -3.10 -B; numpy, PIL, ffmpeg). 2026-10-17 written new (Claude). Reads the run records
(hf every frame, r2) and its g52_ana result (judge_DFG.json or smoke_DFG.json); writes only <run>/video (FLIP52) or --out (the session
scratchpad, for tests). The 3D renderer, the crest-line panel and the section panel are flip51/x51_video.py's (imported READ ONLY).

Panels (all heights above the run's still level eta0; nothing is vertically stretched):
  front 3D   the 3x3-median top surface seen from the downstream side (+x), camera eye about the summit height, looking back along -x at the
             summit (the picture's near-frontal view). Colour = height. Black = the TARGET silhouette read from the user's picture (frozen e51
             read values: full width 3.0 / 2.0 / 1.0 / 0.6 Hc at 20 / 50 / 80 / 95 % of Hc), drawn at this frame's summit and scaled by its Hc.
  crest c(y) c(y)/Hc against (y - y_pk)/Hc at 1:1 (e51 crest line); black = the target read values, grey = the target ranges [guess].
  top view   x 50-210 m, |y| <= 65 m (the interior), 1:1, mirrored at y = 0; + = summit, circle = 4 Hc, magenta = the N1 neighbour.
  section    centre section r2 (y 0.5 m) around the summit, 1:1; black = the print's crest outline (g47_video.print_phys, the old 2D ruler).
  table      per group: t, Hc, W50/W80/W95, K, S2, N1, Nt, core miss (frozen e51 ruler), the gates and the frozen decision.
A thick RED frame and a 3 s hold mark the most converged instant (the group summit with the smallest core miss); orange = the other group
summits. Normal speed 3x (0.25 s of simulation per frame at 12 fps), 0.5x slow motion from 1.5 s before to 1 s after the red instant.
For a smoke (no groups judged) the red instant is the group-1 summit of the smoke check and the video says PIPELINE CHECK ONLY.
usage: py -3.10 -B g52_video.py <run_dir> [--res=<judge or smoke json>] [--out=<dir>] [--t0=30] [--t1=<record end>]
"""
import os, sys, json, math, time, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from PIL import Image, ImageDraw      # noqa: E402
import g52_common as GC               # noqa: E402
import g52_ana as GA                  # noqa: E402
if GC.TOOLS51 not in sys.path:
    sys.path.append(GC.TOOLS51)
import e51_metrics as EM              # noqa: E402  read only
import x51_video as XV                # noqa: E402  read only (Cam, render3d, paste3d, silhouette_3d, crest_panel, section_panel, colour, fnt)

W_IMG, H_IMG = 1600, 1040
FPS_OUT = 12
STEP_S = 0.25
SLOW = (-1.5, 1.0)
HOLD_S = 3.0
RED = XV.RED; ORANGE = XV.ORANGE; BLACK = XV.BLACK; GREY = XV.GREY; TXT = XV.TXT; SUB = XV.SUB


def _n(v, f="%.2f"):
    return (f % v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None and np.isfinite(v) else "-"


def top_panel(img, dr, box, e_full, xs, ys, m, frame_m):
    x0, y0, x1, y1 = box
    xa, xb, ya = 50.0, 210.0, GC.INTERIOR_Y
    s = min((x1 - x0) / (xb - xa), (y1 - y0) / (2 * ya))
    sx = (xs >= xa) & (xs <= xb); sy = np.abs(ys) <= ya
    sub = e_full[np.ix_(sy, sx)]
    rgb = XV.colour(np.nan_to_num(sub, nan=-9.0))
    rgb[~np.isfinite(sub)] = (225, 210, 180)
    im = Image.fromarray(rgb[::-1].astype(np.uint8)).resize((int(round((xb - xa) * s)), int(round(2 * ya * s))), Image.NEAREST)
    img.paste(im, (x0, y0))
    X = lambda x: x0 + (x - xa) * s
    Y = lambda y: y0 + (ya - y) * s
    dr.rectangle([x0, y0, x0 + im.size[0], y0 + im.size[1]], outline=(120, 120, 120))
    for xv, lab in ((60.0, "x 60 (c_in)"), (GC.X_F, "focus x 150"), (190.0, "x 190")):
        dr.line([(X(xv), y0), (X(xv), y0 + im.size[1])], fill=(90, 90, 90))
        dr.text((X(xv) + 2, y0 + 2), lab, fill=(40, 40, 40), font=XV.fnt(11))
    if frame_m:
        xp, yp, Hc = frame_m["x"], frame_m["y"], frame_m["Hc"]
        for yy in ((yp, -yp) if abs(yp) >= 1 else (yp,)):
            dr.line([(X(xp) - 7, Y(yy)), (X(xp) + 7, Y(yy))], fill=BLACK, width=2)
            dr.line([(X(xp), Y(yy) - 7), (X(xp), Y(yy) + 7)], fill=BLACK, width=2)
            r = 4.0 * Hc * s
            dr.ellipse([X(xp) - r, Y(yy) - r, X(xp) + r, Y(yy) + r], outline=(60, 60, 60))
    if m and (m.get("N1_detail") or {}).get("at"):
        ax, ay = m["N1_detail"]["at"]
        if xa <= ax <= xb and abs(ay) <= ya:
            dr.ellipse([X(ax) - 8, Y(ay) - 8, X(ax) + 8, Y(ay) + 8], outline=(200, 0, 160), width=3)
            dr.text((X(ax) + 10, Y(ay) - 8), "N1 %.2f" % m["N1"], fill=(200, 0, 160), font=XV.fnt(12))
    dr.text((x0, y0 + im.size[1] + 4), "上から（x 50〜210 m・|y| ≤ 65 m、縦横同じ、y = 0 で写して両側）　＋＝頂、円＝4 Hc、紫＝いちばん高いほかの山（N1）",
            fill=SUB, font=XV.fnt(12))


def table_panel(dr, box, res, t_now, red_n):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=(255, 255, 255), outline=(150, 150, 150))
    dr.text((x0 + 6, y0 + 4), "組ごとの頂（凍らせた e51 の物差し）。目標 W50 1.5〜2.6・W80 0.8〜1.25・W95 0.4〜0.85・K 2〜4.5・S2 0.05〜0.35",
            fill=TXT, font=XV.fnt(10))
    hdr = ["n", "t s", "Hc m", "x m", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "miss"]
    cw = [26, 58, 54, 46, 50, 50, 50, 46, 46, 46, 46, 52]
    yy = y0 + 24; xx = x0 + 8
    for h, w in zip(hdr, cw):
        dr.text((xx, yy), h, fill=SUB, font=XV.fnt(12)); xx += w
    for r in res.get("groups") or []:
        if not r.get("complete"):
            continue
        yy += 18
        colr = RED if r["n"] == red_n else (TXT if abs(r["t"] - t_now) > 0.6 else ORANGE)
        vals = ["%d" % r["n"], _n(r["t"]), _n(r["Hc"]), _n(r["x_pk"], "%.0f"), _n(r.get("W50")), _n(r.get("W80")), _n(r.get("W95")), _n(r.get("K")),
                _n(r.get("S2")), _n(r.get("N1")), _n(r.get("Nt")), _n(r.get("miss"))]
        xx = x0 + 8
        for v, w in zip(vals, cw):
            dr.text((xx, yy), v, fill=colr, font=XV.fnt(12)); xx += w
    md = res.get("median") or {}
    yy += 22
    dr.text((x0 + 8, yy), "中央値：Hc %s m・W50 %s・W80 %s・W95 %s・K %s・S2 %s・N1 %s・Nt %s・miss %s" % tuple(
        _n(md.get(k)) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "miss")), fill=TXT, font=XV.fnt(12))
    g = res.get("gates") or {k: res.get(k) for k in ("run_complete", "G1", "G2f", "G4", "G5")}
    gl = []
    for k in ("G1", "G2f", "G3P", "G4", "G5", "G6"):
        if k in g:
            gl.append("%s %s" % (k, "○" if (g.get(k) or {}).get("ok") else "×"))
    el = res.get("eligibility") or {}
    for k in ("E1", "E1t", "E2", "E3"):
        if k in el:
            gl.append("%s %s" % (k, "○" if (el.get(k) or {}).get("ok") else "×"))
    yy += 18
    dr.text((x0 + 8, yy), "門：" + "・".join(gl), fill=TXT, font=XV.fnt(12))
    d = res.get("decision") or {}
    if d:
        yy += 18
        dr.text((x0 + 8, yy), "凍らせた決まり：%s（bar %s）%s" % ("・".join(d.get("outcomes") or []), _n(d.get("bar")),
                                                        ("　次：%s" % d["follow_up"]) if d.get("follow_up") else ""), fill=TXT, font=XV.fnt(12))
    dr.text((x0 + 8, yy + 18), "数は【測定】、目標の幅は原画からの読み【推測】", fill=SUB, font=XV.fnt(11))


def make(rd, res_path=None, out_dir=None, t0=30.0, t1=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    rid = os.path.basename(rd)
    if res_path is None:
        for nm in ("judge_DFG.json", "smoke_DFG.json"):
            p = os.path.join(rd, "g52", nm)
            if os.path.exists(p):
                res_path = p; break
    res = json.load(open(res_path, encoding="utf8"))
    smoke = res.get("kind") == "1p0"
    eta0 = float(res["eta0"])
    cfg = GA.load_cfg(rd)
    H = GA.Blocks(rd, "hf", "eta")
    allf = H.frames()
    t1 = float(t1) if t1 is not None else (max(allf) - 1) / GA.FPS
    frames = [f for f in allf if t0 - 1e-9 <= (f - 1) / GA.FPS <= t1 + 1e-9]
    if smoke:
        sg = [r for r in ((res.get("smoke_groups") or {}).get("rows") or []) if r.get("t") is not None]
        red = dict(n=1, frame=int(round(sg[0]["t"] * GA.FPS)) + 1, t=sg[0]["t"], x=sg[0]["x"], y=sg[0]["y"], Hc=sg[0]["Hc"]) if sg else {}
        per = {int(round(r["t"] * GA.FPS)) + 1: dict(n=r["n"], t=r["t"], x_pk=r["x"]) for r in sg}
    else:
        red = res.get("red_instant") or {}
        per = {int(r["f"]): r for r in (res.get("groups") or []) if r.get("complete") and r.get("f")}
    red_f = red.get("frame"); red_t = red.get("t"); red_n = red.get("n")
    try:
        sys.path.insert(0, GC.REPO + "/Tools/GWWaveGen/flip47")
        import g47_video as GV47
        pp = GV47.print_phys
    except Exception:
        pp = None
    plan = []
    t = t0
    while t <= t1 + 1e-9:
        if red_t is not None and red_t + SLOW[0] - 1e-9 <= t < red_t + SLOW[1]:
            for f in frames:
                tf = (f - 1) / GA.FPS
                if red_t + SLOW[0] - 1e-9 <= tf <= red_t + SLOW[1] + 1e-9:
                    plan.append((f, "slow"))
                    if f == red_f:
                        plan.extend([(f, "hold")] * int(round(HOLD_S * FPS_OUT)))
            t = red_t + SLOW[1] + STEP_S
            continue
        f = min(frames, key=lambda q: abs((q - 1) / GA.FPS - t))
        near = [q for q in per if abs((q - 1) / GA.FPS - t) < 0.5 * STEP_S - 1e-9 and q in set(frames)]
        if near:
            f = near[0]                          # a group summit inside this step is shown (orange frame), not skipped
        plan.append((f, "fast"))
        t += STEP_S
    xc = float(red.get("x") or (res.get("median") or {}).get("x_pk") or GC.X_F)
    Hm = float((res.get("median") or {}).get("Hc") or red.get("Hc") or 6.0)
    box3 = (40, 112, 940, 532)
    cam = XV.Cam(eye=(xc + 75.0, 0.0, 0.9 * Hm + 1.0), look=(xc - 10.0, 0.0, 0.4 * Hm), box=box3, fov_deg=48.0)
    od = GC.guard_out(out_dir or os.path.join(rd, "video"), allow_scratch=True)
    path = os.path.join(od, "%s_DFG_compare.mp4" % rid).replace("\\", "/")
    proc = subprocess.Popen([GC.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W_IMG, H_IMG),
                             "-r", str(FPS_OUT), "-i", "-", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
    dr_ = cfg.get("dir") or {}
    t_start = time.time()
    cache = {}
    n_out = 0
    dp = float((cfg.get("parms") or {}).get("dp", res.get("dp") or 0.5))
    for f, state in plan:
        if f not in cache:
            cache.clear()
            a, meta = H.get(f)
            b = GA.masked(a, meta, GC.INTERIOR_Y)
            e_half = EM.median3(b) - eta0
            e_full, ys = EM.mirror_y(e_half, meta)
            xs = EM.xs_of(meta, e_full.shape[1])
            sel = (xs >= GC.FOCAL_X[0]) & (xs <= GC.FOCAL_X[1])
            v = np.where(sel[None, :], e_full, np.nan)
            fm = None
            if np.isfinite(v).any():
                iy, ix = np.unravel_index(int(np.nanargmax(v)), v.shape)
                fm = dict(Hc=float(v[iy, ix]), x=float(xs[ix]), y=float(ys[iy]))
            img = Image.new("RGB", (W_IMG, H_IMG), (250, 250, 247))
            dr = ImageDraw.Draw(img)
            tnow = (f - 1) / GA.FPS
            dr.text((40, 6), "FLIP52 DFG-2 %s　t = %.2f s　粒子 %g m%s" % (rid, tnow, dp, "（下見：管の確かめだけ、形は判定しない）" if smoke else ""),
                    fill=TXT, font=XV.fnt(19))
            dr.text((40, 34), "選んだ物【選び】：周期 P 28 s の 3 つの周波数（T 9.33・7・5.6 s、等しい重み）・X2 の方向 34 本・振幅の和 %s m（%s）" % (
                _n(dr_.get("a_sum"), "%.3f"), "DM1A と同じ、大きくしていない" if abs(float(dr_.get("a_sum") or 0) - GC.A_SUM) < 1e-6 else "大きくした枝"),
                    fill=SUB, font=XV.fnt(13))
            dr.text((40, 51), "　・焦点 (150, 0) と時刻 44 + 28m s・平らな水深 20 m。計算した物：進み・分散・集まり・崩れ。力は重力だけ", fill=SUB, font=XV.fnt(13))
            dr.text((40, 69), "赤い太枠＋3 s 止め＝いちばん収束した瞬間（組の頂の中で凍らせた目標の外れ miss が最小）・橙＝ほかの組の頂。高さは静かな水面 %.2f m から" % eta0,
                    fill=RED, font=XV.fnt(13))
            dr.text((40, 89), "前から見た 3D（下流の側から、目の高さは頂ほど、色＝高さ、縦横同じ）　黒＝原画の読みの形（幅 3.0/2.0/1.0/0.6 Hc を 20/50/80/95 % で、このコマの頂と Hc に）",
                    fill=SUB, font=XV.fnt(12))
            sub3 = XV.render3d(img, e_full, xs, ys, cam, xc - 75.0, xc + 32.0, GC.INTERIOR_Y)
            if fm and fm["Hc"] > 0.5:
                XV.silhouette_3d(sub3, cam, fm["x"], abs(fm["y"]), fm["Hc"])
            XV.paste3d(img, sub3, cam)
            is_red = (f == red_f)
            is_sum = f in per
            XV.crest_panel(dr, (960, 112, 1580, 290), e_full, xs, ys, fm["x"] if fm else xc, fm["y"] if fm else 0.0, fm["Hc"] if fm else None, is_red)
            top_panel(img, dr, (40, 560, 520, 960), e_full, xs, ys, per.get(f) if not smoke else None, fm)
            for k_, (z_, c_) in enumerate(zip(XV.STOPS, XV.COLS)):
                dr.rectangle((1030, 570 + 24 * k_, 1050, 588 + 24 * k_), fill=tuple(int(q) for q in c_))
                dr.text((1056, 570 + 24 * k_), "%+g m" % z_, fill=SUB, font=XV.fnt(12))
            dr.text((1030, 570 + 24 * len(XV.STOPS)), "色＝静かな水面からの高さ", fill=SUB, font=XV.fnt(12))
            XV.section_panel(dr, (560, 560, 1000, 790), rd, f, eta0, fm["x"] if fm else xc, pp)
            table_panel(dr, (960, 300, 1580, 540), res, tnow, red_n)
            gr = res.get("gains_report") or {}
            e3 = (res.get("eligibility") or {}).get("E3") or {}
            lines = ["高さの元（Q39）：Hc の中央値 %s m は、x 60 m の線でいちばん高い来た頂 %s m の %s 倍（集まりの利得）" % (
                         _n((res.get("median") or {}).get("Hc")), _n(e3.get("c_in60_median")), _n(e3.get("gain"))),
                     "1 つの成分の振幅の最大 %s m の %s 倍、1 つの周波数の振幅 %s m の %s 倍、線形の設計の頂 6.331 m の %s 倍" % (
                         _n(gr.get("a_max_component"), "%.4f"), _n(gr.get("Hc_over_max_component"), "%.1f"),
                         _n((gr.get("amp_per_freq") or [None])[0], "%.3f"), _n(gr.get("Hc_over_amp_per_freq")), _n(gr.get("Hc_over_linear_design_crest"))),
                     "周期：組の頂の間 %s s（G3P、P = 28 s）" % ("・".join("%.2f" % v for v in ((res.get("gates") or {}).get("G3P") or {}).get("spacings_s", [])) or "-")]
            g2 = (res.get("G2f") or {}).get("per_n") or {}
            if g2:
                lines.append("入口の振幅（G2f、x 60 m）：" + "・".join("n %s R %s 位相 %s rad" % (k[1:], _n(v.get("R")), _n(v.get("phase_err_rad"))) for k, v in g2.items()))
            yy = 800
            for ln in lines:
                dr.text((560, yy), ln, fill=TXT, font=XV.fnt(13)); yy += 20
            tb0, tb1 = 40, 1560
            ytb = 1008
            U = lambda tt: tb0 + (tb1 - tb0) * (tt - t0) / max(t1 - t0, 1e-6)
            dr.rectangle([tb0, ytb, tb1, ytb + 8], fill=(225, 225, 222))
            dr.rectangle([tb0, ytb, U(tnow), ytb + 8], fill=(60, 80, 110))
            for ff, r in per.items():
                dr.line([(U(r["t"]), ytb - 6), (U(r["t"]), ytb + 14)], fill=RED if r["n"] == red_n else ORANGE, width=3)
            for tf_ in GC.FOCI:
                if t0 <= tf_ <= t1:
                    dr.text((U(tf_) - 10, ytb - 20), "t_f %g" % tf_, fill=SUB, font=XV.fnt(11))
            dr.text((tb0, ytb + 12), "%.0f s" % t0, fill=SUB, font=XV.fnt(11)); dr.text((tb1 - 30, ytb + 12), "%.0f s" % t1, fill=SUB, font=XV.fnt(11))
            if is_red or is_sum:
                colr = RED if is_red else ORANGE
                wd = 7 if is_red else 3
                for bb in (box3, (960, 112, 1580, 290)):
                    dr.rectangle([bb[0] - 5, bb[1] - 5, bb[2] + 5, bb[3] + 5], outline=colr, width=wd)
            cache[f] = np.asarray(img, np.uint8).tobytes()
        proc.stdin.write(cache[f]); n_out += 1
    proc.stdin.close(); proc.wait()
    meta_out = dict(path=path, frames_out=n_out, fps=FPS_OUT, step_s=STEP_S, slow=SLOW, hold_s=HOLD_S, red_instant=red, t_range=[t0, t1],
                    camera=dict(eye=list(cam.C), forward=list(cam.f)), ok=bool(proc.returncode == 0 and os.path.exists(path)),
                    cpu_s=round(time.time() - t_start, 1), result=res_path, smoke=smoke)
    GC.jdump(meta_out, path.replace(".mp4", ".json"))
    return meta_out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    m = make(a[0], res_path=opt.get("res"), out_dir=opt.get("out"), t0=float(opt.get("t0", 30.0)), t1=opt.get("t1"))
    print(json.dumps(GC.clean(m), ensure_ascii=False))


if __name__ == "__main__":
    main()
