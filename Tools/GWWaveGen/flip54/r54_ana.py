# -*- coding: utf-8 -*-
"""FLIP54 R54: compare the K54 strips K0 / K4 at dp 0.5 m (K54's records and analyses, read only) with their R54 reruns at dp 0.25 m and
read the result by the rule frozen in Unity/Build/FLIP54/r54/plan/plan_R54_frozen.json (py -3.10 -B; numpy, scipy, scikit-image, PIL, ffmpeg).
2026-10-18 written new (Claude, FLIP54 builder R). Every number comes from the UNCHANGED K54 analysis g54_ana.py (`measure`: the pv53 ruler
on every frame of the judged breakers k2-k4, medians over the judged breakers; its sha256 must equal the one recorded in the K54 analyses).
The dp-0.5 analyses are the K54 files themselves (sha256 registered in the plan); the dp-0.25 analyses are written by `g54_ana.py measure`
into <R54 run>/k54/k54_ana.json. This file only tabulates, applies r54_common.reading() with the plan's thresholds, and draws.

Quantities (medians over the judged k2-k4; registered): hood_max, hood78, air_max_pre (cavity air), hollow_air (report), lip at the first lip
and at the max-hood frame (in eta_c and in metres = lip x eta_c of that frame), chord_at_hood_max, foot_at_hood_max, foot_at_hood14,
best_score3, h_b, eta_at_hood_max; health: realized H at the gauges, Kr, stage-A volume, judged count.

usage:
  py -3.10 -B r54_ana.py verdict --map=<json {"K0@0p5": run, "K4@0p5": run, "K0@0p25": run, "K4@0p25": run, "ana": {key: k54_ana.json}}>
                                 [--out=<dir under FLIP54>] [--plan=<plan json>] [--no-video]
        -> <out | r54/verdict>/verdict_R54.json, R54_sheet.png, R54_sections.mp4 (prints a summary JSON line)
"""
import os, sys, json, math, glob, time, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np            # noqa: E402
import r54_common as RC       # noqa: E402
import g54_common as C        # noqa: E402
import g54_ana as GA          # noqa: E402  (read only, never edited)

KEYS = ("K0@0p5", "K0@0p25", "K4@0p5", "K4@0p25")
QK = ("hood_max", "hood78", "air_max_pre", "hollow_air", "first_lip_lip", "first_lip_lip_m", "lip_at_hood_max", "lip_at_hood_max_m",
      "chord_at_hood_max", "foot_at_hood_max", "foot_at_hood14", "best_score3", "h_b", "eta_at_hood_max")
QLAB = dict(hood_max="hood max (pre-touchdown)", hood78="hood at chord<=78", air_max_pre="cavity air max", hollow_air="hollow-instant air (report)",
            first_lip_lip="lip at first lip / eta_c", first_lip_lip_m="lip at first lip (m)", lip_at_hood_max="lip at max hood / eta_c",
            lip_at_hood_max_m="lip at max hood (m)", chord_at_hood_max="chord at max hood (deg)", foot_at_hood_max="foot at max hood",
            foot_at_hood14="foot at first hood>=0.14", best_score3="best score3 (lower = closer)", h_b="h_b (m)", eta_at_hood_max="eta_c at max hood (m)")


def lip_m(at):
    if not at or at.get("lip") is None or at.get("eta_c") is None:
        return None
    return float(at["lip"]) * float(at["eta_c"])


def quantities(a):
    """the registered quantities of one analysis (medians over its judged breakers, >= 2 values needed)."""
    m = a.get("medians") or {}
    rows = a.get("breakers") or []
    q = {k: m.get(k) for k in ("hood_max", "hood78", "air_max_pre", "hollow_air", "first_lip_lip", "chord_at_hood_max", "foot_at_hood_max",
                               "foot_at_hood14", "best_score3", "h_b", "eta_at_hood_max")}
    q["first_lip_lip_m"] = GA.med([lip_m(r.get("first_lip")) for r in rows])
    q["lip_at_hood_max"] = GA.med([(r.get("hood_max_at") or {}).get("lip") for r in rows])
    q["lip_at_hood_max_m"] = GA.med([lip_m(r.get("hood_max_at")) for r in rows])
    per = {}
    for k, f in (("hood_max", lambda r: r.get("hood_max")), ("air_max_pre", lambda r: r.get("air_max_pre")), ("hood78", lambda r: r.get("hood78")),
                 ("best_score3", lambda r: (r.get("best_score3") or {}).get("score3")), ("h_b", lambda r: r.get("h_b")),
                 ("chord_at_hood_max", lambda r: r.get("chord_at_hood_max")), ("lip_at_hood_max_m", lambda r: lip_m(r.get("hood_max_at")))):
        per[k] = [[int(r["k"]), (None if f(r) is None else round(float(f(r)), 4))] for r in rows]
    h = a.get("health") or {}
    inl = a.get("inlet") or {}
    return q, per, dict(n_judged=h.get("n_judged"), n_judged_ok=h.get("n_judged_ok"), Kr=h.get("Kr"), volume_max_rel=h.get("volume_max_rel"),
                        H_realized_m=inl.get("H_realized_m"), H_input_m=a.get("H"), judged_k=a.get("judged_k"))


def run_records(rd):
    recs = [C.jload(p) or {} for p in sorted(glob.glob(rd + "/run_c*.json"))]
    return dict(launches=len(recs), f_end_done=max([int(r.get("f_end_done") or 0) for r in recs] or [0]),
                wall_total_s=round(sum(float(r.get("wall_total_s") or 0.0) for r in recs), 1),
                particles_max=max([int(r.get("particles_max") or 0) for r in recs] or [0]),
                rss_peak_gb=max([float(r.get("rss_peak_gb") or 0.0) for r in recs] or [0.0]),
                substeps=[min([(r.get("substeps_min_max") or [99, 0])[0] for r in recs] or [None]),
                          max([(r.get("substeps_min_max") or [99, 0])[1] for r in recs] or [None])])


# ====================================================================== sheet and video
def mask_outline(R, at, half=30.0):
    """(x - x_c, z) points of the water outline of the r2 mask at the frame `at` (pv53 r2_mask raster)."""
    from scipy import ndimage as ndi
    M, X, Z, t = GA.A46.r2_mask(R.cx, int(at["frame"]), float(at.get("xg") or at["x_c"]))
    xc = float(at["x_c"])
    edge = M & ~ndi.binary_erosion(M, iterations=1)
    iz, ix = np.nonzero(edge)
    xr = X[ix] - xc
    sel = (xr >= -half - 15) & (xr <= half)
    return xr[sel], Z[iz][sel]


def overlay_panel(im, items, box, title):
    """dp 0.5 (red) and dp 0.25 (blue) outlines of one arm at their own max-hood frames, both shifted to x_c = 0."""
    from PIL import ImageDraw
    dr = ImageDraw.Draw(im)
    x0, y0, w, h = box
    dr.rectangle([x0, y0, x0 + w, y0 + h], fill=(255, 255, 255), outline=(150, 150, 150))
    dr.text((x0 + 6, y0 + 4), title, fill=GA.TXT, font=GA.fnt(15, True))
    XL, XR, ZB, ZT = -42.0, 22.0, -9.0, 12.0
    s = min((w - 50) / (XR - XL), (h - 60) / (ZT - ZB))
    px0, py0 = x0 + 40, y0 + 28
    tr = lambda x, z: (px0 + (x - XL) * s, py0 + (ZT - z) * s)
    dr.line([tr(XL, 0.0), tr(XR, 0.0)], fill=(170, 170, 170), width=1)
    dr.line([tr(0.0, ZB), tr(0.0, ZT)], fill=(220, 220, 220), width=1)
    for zz in range(-5, int(ZT) + 1, 5):
        dr.text((px0 - 30, py0 + (ZT - zz) * s - 8), "%d" % zz, fill=GA.SUB, font=GA.fnt(11))
    yy = y0 + h - 26
    for j, (lab, col, R, at) in enumerate(items):
        if not at:
            continue
        try:
            xr, zz = mask_outline(R, at)
        except Exception as ex:
            dr.text((x0 + 10, yy), "%s outline error %s" % (lab, repr(ex)[:60]), fill=GA.RED, font=GA.fnt(12))
            continue
        r_ = 1.6 if j == 0 else 0.6                    # dp 0.5 drawn first and thicker, so it stays visible under dp 0.25
        for x, z in zip(xr, zz):
            if XL <= x <= XR and ZB <= z <= ZT:
                p = tr(x, z)
                dr.rectangle([p[0] - r_, p[1] - r_, p[0] + r_, p[1] + r_], fill=col)
    dr.text((x0 + 8, yy), "red = dp 0.5 m, blue = dp 0.25 m; each at its own max-hood frame, shifted to x_c = 0 (m, centre section)", fill=GA.SUB,
            font=GA.fnt(12))


def sheet(anas, runs, D, path):
    from PIL import Image, ImageDraw
    import textwrap
    pw, ph = 700, 330
    W = 2 * pw + 30
    im = Image.new("RGB", (W, 2400), (247, 247, 244))
    dr = ImageDraw.Draw(im)
    dr.text((14, 10), "R54 2D resolution check (K54 K0 / K4 at dp 0.5 vs 0.25 m): %s" % D["verdict"], fill=GA.TXT, font=GA.fnt(22, True))
    yy = 44
    paras = [D["reading"].get("text", ""),
             "rule (frozen %s): resolution matters if cavity air or hood max grows >= +%d %% at dp 0.25 in BOTH arms (same quantity), or the K4-vs-K0 "
             "order of hood max / cavity air / hood<=78 / best score3 flips (tie band %d %%); report only otherwise" % (
                 D.get("plan_frozen_at") or "?", round(D["thresholds"]["gain"] * 100), round(D["thresholds"]["tie"] * 100)),
             "medians over the judged breakers k2-k4 (unchanged g54_ana ruler); 2D strips (half width 6 m), not the 3D wave [measured]; the user judges"]
    for ln in [w for p in paras for w in textwrap.wrap(p, 170)]:
        dr.text((14, yy), ln, fill=GA.SUB, font=GA.fnt(14))
        yy += 20
    yy += 6
    hdr = ["quantity", "K0 dp0.5", "K0 dp0.25", "K0 change", "K4 dp0.5", "K4 dp0.25", "K4 change"]
    xs = [14, 300, 420, 540, 680, 800, 920]
    for x, t_ in zip(xs, hdr):
        dr.text((x, yy), t_, fill=GA.TXT, font=GA.fnt(13, True))
    yy += 18
    T = D["table"]
    for k in QK:
        row = T.get(k) or {}
        vals = [QLAB.get(k, k)]
        for arm in ("K0", "K4"):
            r = row.get(arm) or {}
            f = "%.1f" if k.startswith("chord") else ("%.2f" if k in ("h_b", "eta_at_hood_max", "first_lip_lip_m", "lip_at_hood_max_m") else "%.3f")
            ch = r.get("rel")
            vals += [GA.fmt(r.get("dp0p5"), f), GA.fmt(r.get("dp0p25"), f), "-" if ch is None else "%+.0f %%" % (100 * ch)]
        for i, (x, t_) in enumerate(zip(xs, vals)):
            col = GA.TXT
            if k in D["thresholds"]["gain_keys"] and i in (3, 6) and t_ != "-":
                col = GA.GREEN if float(t_.split()[0]) >= 100 * D["thresholds"]["gain"] - 1e-9 else GA.TXT
            dr.text((x, yy), t_, fill=col, font=GA.fnt(13))
        yy += 17
    od = D["reading"].get("ordering") or {}
    if od:
        yy += 4
        s = "K4-vs-K0 order (+1 K4 larger, -1 smaller, 0 tie): " + "; ".join("%s %+d -> %+d%s" % (k, v["order_dp0p5"], v["order_dp0p25"],
                                                                                                      " FLIP" if v["flip"] else "") for k, v in od.items())
        for ln in textwrap.wrap(s, 170):
            dr.text((14, yy), ln, fill=GA.TXT, font=GA.fnt(13)); yy += 18
    hl = D.get("health") or {}
    s = "health: " + "; ".join("%s judged %s H_realized %s m Kr %s vol %s" % (k, (v or {}).get("n_judged"), GA.fmt((v or {}).get("H_realized_m")),
                                                                              GA.fmt((v or {}).get("Kr"), "%.3f"), GA.fmt((v or {}).get("volume_max_rel"), "%.4f"))
                               for k, v in hl.items())
    for ln in textwrap.wrap(s, 170):
        dr.text((14, yy), ln, fill=GA.SUB, font=GA.fnt(12)); yy += 17
    y0 = yy + 10
    Rs = {}
    for i, key in enumerate(KEYS):
        a = anas.get(key)
        px, py = 14 + (i % 2) * (pw + 2), y0 + (i // 2) * (ph + 14)
        if a is None:
            continue
        br = GA.median_breaker(a)
        at = (br or {}).get("hood_max_at")
        R = GA.Run(runs[key])
        Rs[key] = (R, at)
        lines = ["k%s  t %s s  x_c %s m  eta_c %s m  hood %s  air %s" % (br["k"] if br else "-", GA.fmt((at or {}).get("t")), GA.fmt((at or {}).get("x_c"), "%.1f"),
                                                                         GA.fmt((at or {}).get("eta_c")), GA.fmt((at or {}).get("hood"), "%.3f"),
                                                                         GA.fmt((at or {}).get("air"), "%.3f")),
                 "lip %s eta_c (%s m)  chord %s deg  foot %s  score3 %s" % (GA.fmt((at or {}).get("lip"), "%.3f"), GA.fmt(lip_m(at)),
                                                                           GA.fmt((at or {}).get("chord"), "%.1f"), GA.fmt((at or {}).get("foot")),
                                                                           GA.fmt((at or {}).get("score3"), "%.3f")),
                 os.path.basename(runs[key])]
        GA.draw_panel(im, R, a, br, at, (px, py, pw - 14, ph), "%s  (median breaker by hood max, at its max-hood frame)" % key.replace("@0p", " dp 0."), lines)
    yo = y0 + 2 * (ph + 14)
    for j, arm in enumerate(("K0", "K4")):
        items = [("dp 0.5", (210, 40, 40)) + Rs.get(arm + "@0p5", (None, None)), ("dp 0.25", (30, 70, 200)) + Rs.get(arm + "@0p25", (None, None))]
        items = [(lab, col, R, at) for (lab, col, R, at) in items if R is not None]
        overlay_panel(im, items, (14 + j * (pw + 2), yo, pw - 14, ph), "%s: outlines dp 0.5 vs 0.25 at max hood" % arm)
    im = im.crop((0, 0, W, yo + ph + 16))
    RC.guard_out(os.path.dirname(path))
    im.save(path)
    return path


def video(anas, runs, path, slow=2, size=(560, 220)):
    """centre sections of the median breaker of each run (2 x 2: rows K0 / K4, columns dp 0.5 / 0.25), aligned at each run's first lip, 0.5x."""
    from PIL import Image, ImageDraw
    cols = 2
    W, Hh = cols * size[0], 2 * (size[1] + 26) + 40
    W += W % 2; Hh += Hh % 2
    prep = []
    for key in KEYS:
        a = anas.get(key)
        if a is None:
            prep.append((key, None, {}, None, None, {}, 6.0)); continue
        br = GA.median_breaker(a) or {}
        fl = (br.get("first_lip") or {}).get("frame") or br.get("on_f")
        R = GA.Run(runs[key])
        trk = R.track(int(br.get("on_f") or fl or 1), float(br.get("on_x") or 250.0), int(fl) - 40, int(fl) + 64) if fl else {}
        ec = (br.get("hood_max_at") or {}).get("eta_c") or (br.get("crest_ref_m") or 6.0)
        prep.append((key, a, br, fl, R, trk, ec))
    RC.guard_out(os.path.dirname(path))
    cmd = [C.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, Hh), "-r", "24", "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for d in range(-36, 61):
        im = Image.new("RGB", (W, Hh), (247, 247, 244))
        dr = ImageDraw.Draw(im)
        dr.text((10, 8), "R54: K54 K0 / K4 at dp 0.5 (left) and 0.25 m (right), aligned at each first lip  t_rel %+.2f s  (0.5x; 2D strips)" % (d / GA.FPS),
                fill=GA.TXT, font=GA.fnt(15, True))
        for i, (key, a, br, fl, R, trk, ec) in enumerate(prep):
            px, py = (i % cols) * size[0], 40 + (i // cols) * (size[1] + 26)
            dr.text((px + 6, py), "%s  k%s" % (key.replace("@0p", " dp 0."), br.get("k", "-")), fill=GA.TXT, font=GA.fnt(14, True))
            if not fl:
                continue
            f = int(fl) + d
            xg = trk.get(f)
            if xg is None or f not in R.r2set:
                continue
            try:
                sim, geo = GA.section_rgb(R, f, xg, xg, float(ec), size[0] - 10, size[1] - 10)
                im.paste(sim, (px + 5, py + 22))
            except Exception:
                pass
        b = im.tobytes()
        for _ in range(slow):
            pr.stdin.write(b)
            n += 1
    pr.stdin.close()
    pr.wait()
    return path, n


# ====================================================================== verdict
def verdict(mp, out_dir=None, plan_path=None, do_video=True):
    plan_path = plan_path or RC.PLAN
    plan = C.jload(plan_path) or {}
    sp = plan_path + ".sha256"
    plan_ok = bool(plan and os.path.exists(sp) and open(sp, encoding="utf8").read().split()[0] == C.sha256_file(plan_path))
    rr = plan.get("reading_rule") or {}
    th = dict(gain=float(rr.get("gain", RC.GAIN)), tie=float(rr.get("tie", RC.TIE)), gain_keys=list(rr.get("gain_keys") or RC.GAIN_KEYS),
              order_keys=list(rr.get("order_keys") or RC.ORDER_KEYS))
    anas, paths, notes = {}, {}, {}
    over = mp.get("ana") or {}
    for key in KEYS:
        rd = mp.get(key)
        if not rd:
            continue
        if key in over:
            a, p = C.jload(over[key]), over[key]
            if a is None:
                notes[key] = "analysis %s missing" % over[key]; continue
        elif key.endswith("@0p5"):
            p = rd.rstrip("/") + "/k54/" + GA.ANA_NAME
            a = C.jload(p)
            if a is None:
                notes[key] = "K54 analysis %s missing (never re-measured here)" % p; continue
        else:
            a, p = GA.load_or_measure(rd)
        anas[key], paths[key] = a, p
    # the K54 references must be the registered files; the ruler must be the K54 one
    refs = (plan.get("references") or {}).get("arms") or {}
    ref_ok = {}
    for arm in RC.ARMS:
        key = arm + "@0p5"
        want = (refs.get(arm) or {}).get("analysis_sha256")
        got = RC.sha(paths[key]) if key in paths else None
        ref_ok[arm] = bool(want and got == want) if key not in over else "stand-in (simulate)"
    ga_sha = C.sha256_file(HERE + "/g54_ana.py")[:16]
    ruler_ok = {k: ((a.get("module_shas") or {}).get("flip54/g54_ana.py") == ga_sha) for k, a in anas.items()}
    q, per, health = {}, {}, {}
    for key, a in anas.items():
        arm, dpt = key.split("@")
        qq, pp, hh = quantities(a)
        health[key] = hh
        per[key] = pp
        q[(arm, dpt)] = qq if hh.get("n_judged_ok") else None
    rd_ = RC.reading(q, th["gain"], th["tie"], tuple(th["gain_keys"]), tuple(th["order_keys"]))
    if not plan_ok:
        rd_ = dict(rd_, verdict="PLAN_SHA_FAILED", text="the frozen plan's sha256 does not hold: no reading (%s)" % plan_path)
    elif any(v is False for v in ref_ok.values()):
        rd_ = dict(rd_, verdict="REFERENCE_CHANGED", text="a K54 dp-0.5 analysis differs from the registered sha256: no reading")
    elif not all(ruler_ok.values()):
        rd_ = dict(rd_, verdict="RULER_CHANGED", text="an analysis was made with a g54_ana.py other than the current one: no reading")
    table = {}
    for k in QK:
        table[k] = {}
        for arm in RC.ARMS:
            a5 = (q.get((arm, "0p5")) or {}).get(k) if q.get((arm, "0p5")) else ((quantities(anas[arm + "@0p5"])[0].get(k)) if arm + "@0p5" in anas else None)
            a25 = (q.get((arm, "0p25")) or {}).get(k) if q.get((arm, "0p25")) else ((quantities(anas[arm + "@0p25"])[0].get(k)) if arm + "@0p25" in anas else None)
            table[k][arm] = dict(dp0p5=a5, dp0p25=a25, rel=RC.rel(a25, a5), diff=(None if (a5 is None or a25 is None) else float(a25) - float(a5)))
    hb_shift = {arm: table["h_b"][arm]["diff"] for arm in RC.ARMS}
    D = dict(verdict=rd_["verdict"], reading=rd_, thresholds=th, table=table, per_breaker=per, health=health,
             report=dict(h_b_shift_m=hb_shift,
                         h_b_note="report: a break-depth shift > 1 m means the dp-0.25 wave breaks elsewhere on the bed, so a hollow change mixes "
                                  "resolution and breaking position",
                         per_breaker_note="the per-breaker values (k2-k4) show the scatter a median change sits in",
                         H_realized_shift_m={arm: (None if not (health.get(arm + "@0p5") and health.get(arm + "@0p25") and health[arm + "@0p5"].get("H_realized_m")
                                                               is not None and health[arm + "@0p25"].get("H_realized_m") is not None)
                                                   else health[arm + "@0p25"]["H_realized_m"] - health[arm + "@0p5"]["H_realized_m"]) for arm in RC.ARMS}),
             runs={k: (v.replace(C.REPO + "/", "") if v else None) for k, v in mp.items() if k in KEYS},
             run_records={k: run_records(mp[k]) for k in KEYS if mp.get(k) and os.path.isdir(mp[k])},
             analyses={k: v.replace(C.REPO + "/", "") for k, v in paths.items()}, notes=notes,
             plan=plan_path.replace(C.REPO + "/", ""), plan_sha256=RC.sha(plan_path), plan_sha_ok=plan_ok, plan_frozen_at=plan.get("frozen_at"),
             references_ok=ref_ok, ruler_g54_ana_sha16=ga_sha, ruler_ok=ruler_ok,
             r54_tool_shas={t: (C.sha256_file(HERE + "/" + t)[:16] if os.path.exists(HERE + "/" + t) else None) for t in RC.R54_TOOLS},
             date=time.strftime("%Y-%m-%d %H:%M:%S"),
             tags=dict(verdict="decided by the frozen rule (plan R54 reading_rule) from measured medians; AI self-assessment, the user judges the look",
                       numbers="measured (FLIP records + the pv53 ruler of g54_ana.py)"))
    od = RC.guard_out(out_dir or RC.VERDICT_DIR)
    try:
        D["sheet"] = sheet(anas, mp, D, od + "/R54_sheet.png")
    except Exception as ex:
        import traceback
        D["sheet_error"] = repr(ex)[:300] + " | " + traceback.format_exc()[-600:]
    if do_video:
        try:
            p, n = video(anas, mp, od + "/R54_sections.mp4")
            D["video"] = p; D["video_frames"] = n
        except Exception as ex:
            D["video_error"] = repr(ex)[:300]
    C.jdump(D, od + "/verdict_R54.json")
    return D, od + "/verdict_R54.json"


def main(argv):
    pos, opt = GA.parse(argv[1:])
    if not pos or pos[0] != "verdict" or not opt.get("map"):
        print(__doc__); return 2
    mp = json.load(open(opt["map"], encoding="utf8"))
    D, p = verdict(mp, opt.get("out"), opt.get("plan"), do_video=not opt.get("no-video"))
    print(json.dumps(C.clean(dict(verdict_json=p, verdict=D["verdict"], text=D["reading"].get("text"), gains=D["reading"].get("gains"),
                                  flips=D["reading"].get("flips"), references_ok=D["references_ok"], ruler_ok=D["ruler_ok"], plan_sha_ok=D["plan_sha_ok"],
                                  sheet=D.get("sheet"), video=D.get("video"),
                                  errors=[D.get(k) for k in ("sheet_error", "video_error") if D.get(k)])), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
