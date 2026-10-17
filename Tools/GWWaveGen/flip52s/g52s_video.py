# -*- coding: utf-8 -*-
"""FLIP52S plan DFG-S: the compare video of one run (py -3.10 -B; numpy, PIL, ffmpeg). 2026-10-18 written new (Claude) by adapting
flip52b/g52b_video.py (not edited) to the DFG-S run (DFG-2's tank with the 1:3 step). Reads the run records (hf every frame, r2), its g52s_ana
result (g52s/judge_DFGS.json or pcheck_DFGS.json) and, when present, pv53's json and the co-equal verdict; writes only <run>/video (FLIP52S)
or --out (the session scratchpad, for tests). The 3D renderer, the crest-line panel and the section panel are flip51/x51_video.py's (imported
READ ONLY). The Unity print view itself is pv53's (its stills / mp4 are listed in the table panel).

Panels (heights above the run's still level eta0; nothing is vertically stretched):
  print pose (hf proxy)  the 3x3-median top surface seen from the option-D print pose of pv53 (camera 5.12 s m shoreward of the crest, 75 s m to the
                         side, eye 0.576 Hc, look 0.52 s m shoreward at 0.793 Hc, vertical FOV 23.5 deg, s = Hc / 7.16 m) at the red instant's crest;
                         the hf top surface cannot show an overhang: it is a proxy, the Unity print view (pv53) is the criterion
  front 3D               from the downstream side looking back along -x (the screenshot's near-frontal view); black = the target silhouette
  section                centre section r2 (y 0.5 m) around the crest, 1:1; black = the print's crest outline (g47_video.print_phys); the step's
                         toe 108 m / edge 150 m are named in the header
  crest c(y)             e51 crest line c(y)/Hc vs the target read values
  table                  per group: the converged crest, the onset (x, depth), Hc, W50/W80/W95, K, S2, N1, Nt, miss; the print ruler at pv53's
                         best instants (score3, lip, back, width07); the pre-break back / width07 of the judge; the three co-equal criteria
RED thick frame + 3 s hold = the most PRINT-LIKE instant (pv53's, else the judge's most converged instant); ORANGE = the groups' 'max' instants.
usage: py -3.10 -B g52s_video.py <run_dir> [--out=<dir>] [--t0=<s>] [--t1=<s>] [--res=<judge json> (tests)]
"""
import os, sys, json, math, time, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from PIL import Image, ImageDraw      # noqa: E402
import g52s_common as GC              # noqa: E402
import g52s_ana as GA                 # noqa: E402
import e51_metrics as EM              # noqa: E402  read only
import x51_video as XV                # noqa: E402  read only

W_IMG, H_IMG = 1600, 1040
FPS_OUT = 12
STEP_S = 0.25
SLOW = (-1.5, 1.5)
HOLD_S = 3.0
PV = dict(dx_m=5.12, lateral_m=75.0, h_over_crest=0.576, look_dx_m=0.52, look_h=0.793, fov_v=23.5, Hc_ref=7.16)   # = pv53 option-D pose
RED = XV.RED; ORANGE = XV.ORANGE; TXT = XV.TXT; SUB = XV.SUB


def _n(v, f="%.2f"):
    return (f % v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None and np.isfinite(v) else "-"


def jl(p):
    try:
        return json.load(open(p, encoding="utf8"))
    except Exception:
        return None


def print_cam(x_c, Hc, box):
    s = max(Hc, 1.0) / PV["Hc_ref"]
    w, h = box[2] - box[0], box[3] - box[1]
    fov_h = 2.0 * math.degrees(math.atan(math.tan(math.radians(0.5 * PV["fov_v"])) * w / float(h)))
    return XV.Cam(eye=(x_c + PV["dx_m"] * s, -PV["lateral_m"] * s, PV["h_over_crest"] * Hc), look=(x_c + PV["look_dx_m"] * s, 0.0, PV["look_h"] * Hc),
                  box=box, fov_deg=fov_h)


def table(dr, box, res, pv, co, tnow):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=(255, 255, 255), outline=(150, 150, 150))
    yy = y0 + 6
    hd = ["組", "収束 t / x / Hc", "崩れ t / x / h", "Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "miss", "score3", "lip", "back", "w07", "前 back/w07"]
    ws = [26, 132, 120, 46, 46, 46, 46, 42, 42, 42, 42, 46, 52, 40, 42, 42, 90]
    xx = x0 + 6
    for h_, w_ in zip(hd, ws):
        dr.text((xx, yy), h_, fill=SUB, font=XV.fnt(12)); xx += w_
    yy += 20
    pvp = {int(p["n"]): (p.get("best") or {}) for p in ((pv or {}).get("periods") or []) if p.get("n") is not None}
    for r in (res.get("groups") or []):
        if not r.get("complete"):
            dr.text((x0 + 6, yy), "%d  %s" % (r["n"], r.get("why")), fill=SUB, font=XV.fnt(12)); yy += 18; continue
        c = r["conv"]; o = r.get("onset") or {}
        b = pvp.get(int(r["n"]), {})
        vals = [str(r["n"]), "%.2f / %.0f / %.2f" % (c["t"], c["x"], c["Hc"]), ("%.2f / %.0f / %.1f" % (o["t"], o["x"], o.get("h") or 0.0)) if o else "-", _n(r.get("Hc")),
                _n(r.get("W50")), _n(r.get("W80")), _n(r.get("W95")), _n(r.get("K")), _n(r.get("S2")), _n(r.get("N1")), _n(r.get("Nt")), _n(r.get("miss")),
                _n(b.get("score3"), "%.3f"), _n(b.get("lip")), _n(b.get("back"), "%.1f"), _n(b.get("w07")),
                "%s / %s" % (_n(((r.get("prebreak_shape") or {}).get("shape") or {}).get("back_deg"), "%.0f"),
                             _n(((r.get("prebreak_shape") or {}).get("shape") or {}).get("w07")))]
        xx = x0 + 6
        for v, w_ in zip(vals, ws):
            dr.text((xx, yy), v, fill=TXT, font=XV.fnt(12)); xx += w_
        yy += 18
    pr = GA.COEQ["print_ref"]
    dr.text((x0 + 6, yy + 4), "原画：score3 0、lip %.2f、back %.1f°（%g〜%g）、width07 %.2f（%g〜%g）、chord %.1f°。DM1A の best score3 中央値 0.6485" % (
        pr["lip"], pr["back_deg_07_09"], pr["back_band"][0], pr["back_band"][1], pr["width07"], pr["width07_band"][0], pr["width07_band"][1], pr["chord_deg"]),
        fill=SUB, font=XV.fnt(12))
    yy += 26
    d = res.get("decision") or {}
    if co:
        c1 = co["criterion_1_print_view"]; c2 = co["criterion_2_print_ruler"]; c3 = co["criterion_3_convergence"]
        lines = ["(1) 原画の視点の Unity 画：%s" % ("あり（pv53）" if c1.get("ok") else "なし（%s）" % (c1.get("why") or "-")),
                 "(2) 原画の物差し：%s（score3 中央値 %s ≤ 0.9485、lip %s ≥ 0.20）" % (c2.get("print_match"), _n(c2.get("median_best_score3"), "%.3f"),
                                                                         _n(c2.get("median_best_lip"))),
                 "(3) 収束：%s（miss 中央値 %s、bar %s、valid %s）" % (c3.get("outcomes"), _n(c3.get("core_miss_median")), _n(c3.get("bar")), c3.get("valid")),
                 "判定（3 つは同格）：%s" % co.get("verdict")]
    else:
        lines = ["収束（凍らせた判定）：%s　bar %s　valid %s　失敗 %s" % (d.get("outcomes"), _n(d.get("bar")), res.get("valid", res.get("smoke_pass")),
                                                               res.get("failed_gates", res.get("failed"))),
                 "原画の視点・物差し：pv53 の結果がまだない（auto_DFGS が pv53 → coequal の後にこの動画を作る）"]
    lines.append("崩れの型：%s" % (d.get("physics_flags") or "-"))
    for ln in lines:
        dr.text((x0 + 6, yy), ln[:150], fill=TXT, font=XV.fnt(13)); yy += 19


def make(rd, out_dir=None, t0=None, t1=None, res_path=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    rid = os.path.basename(rd)
    res = (jl(res_path) if res_path else None) or jl(os.path.join(rd, "g52s", "judge_DFGS.json")) or jl(os.path.join(rd, "g52s", "pcheck_DFGS.json"))
    if not res:
        raise SystemExit("no g52s/judge_DFGS.json or pcheck_DFGS.json in %s" % rd)
    smoke = res.get("kind") == "pcheck"
    pv = jl(GA.PV53_OUT + "/%s/pv53_%s.json" % (rid, rid))
    co = jl(os.path.join(rd, "g52s", "coequal_DFGS.json"))
    eta0 = float(res["eta0"])
    cfg = GA.load_cfg(rd)
    fo = GA.foci(cfg)
    H = GA.Blocks(rd, "hf", "eta")
    allf = H.frames()
    t0 = float(t0) if t0 is not None else (0.0 if smoke else max(25.0, fo[0] - 12.0))
    t1 = float(t1) if t1 is not None else (max(allf) - 1) / GA.FPS
    frames = [f for f in allf if t0 - 1e-9 <= (f - 1) / GA.FPS <= t1 + 1e-9]
    per = {}
    if not smoke:
        for r in res.get("groups") or []:
            if r.get("complete"):
                per[int(r["f"])] = dict(n=r["n"], t=r["t"], x=r["x_pk"], Hc=r["Hc"])
    mpl = (pv or {}).get("most_print_like")
    if mpl and mpl.get("frame"):
        red = dict(frame=int(mpl["frame"]), t=float(mpl["t"]), x=float(mpl.get("x_c") or 0.0), Hc=float(mpl.get("eta_c") or 0.0), n=mpl.get("n"),
                   src="pv53 most print-like instant")
    else:
        ri = res.get("red_instant") or (dict(frame=min(per), **per[min(per)]) if per else {})
        red = dict(frame=ri.get("frame"), t=ri.get("t"), x=ri.get("x"), Hc=ri.get("Hc"), n=ri.get("n"), src="judge most converged instant")
    red_f = red.get("frame"); red_t = red.get("t")
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
            f = near[0]
        plan.append((f, "fast"))
        t += STEP_S
    xc = float(red.get("x") or GC.X_F)
    Hm = float(red.get("Hc") or (res.get("median") or {}).get("Hc") or 5.0)
    boxP = (30, 112, 790, 532); boxF = (810, 112, 1570, 392)
    camP = print_cam(xc, Hm, boxP)
    camF = XV.Cam(eye=(xc + 6.3 * Hm + 25.0, 0.0, Hm), look=(xc, 0.0, 0.5 * Hm), box=boxF, fov_deg=52.0)
    od = GC.guard_out(out_dir or os.path.join(rd, "video"), allow_scratch=True)
    path = os.path.join(od, "%s_DFGS_compare.mp4" % rid).replace("\\", "/")
    proc = subprocess.Popen([GC.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W_IMG, H_IMG),
                             "-r", str(FPS_OUT), "-i", "-", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
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
            sel = (xs >= GC.ONSET_X[0]) & (xs <= GC.ONSET_X[1])
            v = np.where(sel[None, :], e_full, np.nan)
            fm = None
            if np.isfinite(v).any():
                iy, ix = np.unravel_index(int(np.nanargmax(v)), v.shape)
                fm = dict(Hc=float(v[iy, ix]), x=float(xs[ix]), y=float(ys[iy]))
            img = Image.new("RGB", (W_IMG, H_IMG), (250, 250, 247))
            dr = ImageDraw.Draw(img)
            tnow = (f - 1) / GA.FPS
            dr.text((30, 6), "FLIP52S DFG-S %s　t = %.2f s　粒子 %g m%s" % (rid, tnow, dp, "（0.5 m 10 s の管の確かめだけ、形は判定しない）" if smoke else ""),
                    fill=TXT, font=XV.fnt(19))
            dr.text((30, 34), "選んだ物【選び】：DFG-2 と同じ海（P 28 s、T 9.33/7/5.6 s、X2 の方向 34 本、振幅の和 6.331 m = DM1A、大きくしていない）と水槽に"
                              "段（足 x %.0f m、1:%.0f、縁 x %.0f m、棚 %.0f m）、焦点 (%.0f, 0)（水深 %.1f m）・時刻 %s s" % (GC.X_TOE, GC.SLOPE_S, GC.X_EDGE, GC.H_TOP, GC.X_F,
                                                                                       GC.h_of(GC.X_F), " / ".join("%g" % q for q in fo)),
                    fill=SUB, font=XV.fnt(13))
            dr.text((30, 52), "計算した物：進み・分散・屈折・浅水変形・反射・集まり・崩れ。力は重力と海底だけ。赤い太枠＋3 s 止め＝%s、橙＝組の 'max'" % red.get("src"),
                    fill=RED, font=XV.fnt(13))
            dr.text((30, 72), "左：原画の視点（pv53 の option-D の構図、hf の上面なので巻きの下は描けない＝目安。本当の判定は Unity の画）　右：下流の側から前（収束の見方）",
                    fill=SUB, font=XV.fnt(12))
            e_print = e_full.copy()
            e_print[ys < camP.C[1] + 5.0, :] = np.nan       # only the water beyond the camera's side position (the painter's renderer has no near clip)
            subP = XV.render3d(img, e_print, xs, ys, camP, xc - 110.0, xc + 60.0, GC.INTERIOR_Y)
            XV.paste3d(img, subP, camP)
            subF = XV.render3d(img, e_full, xs, ys, camF, xc - 75.0, xc + 32.0, GC.INTERIOR_Y)
            if fm and fm["Hc"] > 0.5:
                XV.silhouette_3d(subF, camF, fm["x"], abs(fm["y"]), fm["Hc"])
            XV.paste3d(img, subF, camF)
            is_red = (f == red_f)
            is_sum = f in per
            XV.crest_panel(dr, (810, 400, 1570, 532), e_full, xs, ys, fm["x"] if fm else xc, fm["y"] if fm else 0.0, fm["Hc"] if fm else None, is_red)
            XV.section_panel(dr, (30, 548, 640, 800), rd, f, eta0, fm["x"] if fm else xc, pp)
            table(dr, (660, 548, 1570, 830), res, pv, co, tnow)
            tb0, tb1 = 30, 1570
            ytb = 1008
            U = lambda tt: tb0 + (tb1 - tb0) * (tt - t0) / max(t1 - t0, 1e-6)
            dr.rectangle([tb0, ytb, tb1, ytb + 8], fill=(225, 225, 222))
            dr.rectangle([tb0, ytb, U(tnow), ytb + 8], fill=(60, 80, 110))
            for ff, r in per.items():
                dr.line([(U(r["t"]), ytb - 6), (U(r["t"]), ytb + 14)], fill=ORANGE, width=3)
            if red_t is not None:
                dr.line([(U(red_t), ytb - 8), (U(red_t), ytb + 16)], fill=RED, width=4)
            for tf_ in fo:
                if t0 <= tf_ <= t1:
                    dr.text((U(tf_) - 10, ytb - 22), "t_f %g" % tf_, fill=SUB, font=XV.fnt(11))
            if is_red or is_sum:
                colr = RED if is_red else ORANGE
                wd = 7 if is_red else 3
                for bb in (boxP, boxF):
                    dr.rectangle([bb[0] - 5, bb[1] - 5, bb[2] + 5, bb[3] + 5], outline=colr, width=wd)
            cache[f] = np.asarray(img, np.uint8).tobytes()
        proc.stdin.write(cache[f]); n_out += 1
    proc.stdin.close(); proc.wait()
    meta_out = dict(path=path, frames_out=n_out, fps=FPS_OUT, step_s=STEP_S, slow=SLOW, hold_s=HOLD_S, red_instant=red, t_range=[t0, t1],
                    ok=bool(proc.returncode == 0 and os.path.exists(path)), cpu_s=round(time.time() - t_start, 1), smoke=smoke,
                    pv53=bool(pv), coequal=bool(co))
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
    m = make(a[0], out_dir=opt.get("out"), t0=opt.get("t0"), t1=opt.get("t1"), res_path=opt.get("res"))
    print(json.dumps(GC.clean(m), ensure_ascii=False))


if __name__ == "__main__":
    main()
