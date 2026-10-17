# -*- coding: utf-8 -*-
"""FLIP51 X2B': the X2 view package transferred to X2B' (py -3.10 -B; numpy, scipy, PIL, ffmpeg, Unity batch). 2026-10-17 written new (Claude).
Reuses READ ONLY the X2 view tools of Unity/Build/FLIP51/_scratch/x2view/ (imported by path under new module names, their module constants set
IN MEMORY to the X2B run; the files are not edited): x2_section.py (centre-section print ruler scan and panels), cam_x2.py (Field, clearance,
visibility, projection, the print / front camera rules), compose_x2.py (band captions). f3d51_export_e51.py (unchanged) writes the long clips;
FLIP3DBatch.BuildSceneAndCapture (unchanged C#) renders them through Tools/GWWaveGen/flip3d/f3d_unity.ps1 (unity.lock: one Unity at a time).

Steps (each guarded; a failed step is recorded in view_X2B.json and the next one still runs where it can):
  section  every r2 frame 841-1801 (35-75 s): every centre-line crest (x 150-340 m, height >= 1 m, prominence >= 0.5 m) measured with the D ruler
           (x2_section.scan, unchanged code; the water outside the crest's own troughs cleared as for X2). Per e51 period (screen_E05.json scan
           summits): at_summit / track_best / any_best (x2_section.analyse rules, re-written here only to survive a period without a centre-row
           crest: then the plain g49 call at the e51 summit is used and flagged). Panels (1:1, print outline cn scaled to eta_c at the crest):
           the most print-like instant of pv53 (if its json exists) and the converged summit (the judge's red instant).
  cams     the X2 camera rules (cam_x2.py docstring) transferred to X2B's CONVERGED summit (the judge's red-instant period, its centre-row crest at
           that frame): print view = the option-D print pose relative to the crest at the DM1A metres-per-pixel (camera +5.12 m, lateral 75 m, eye
           0.576 z_s raised in 0.25 m steps until clear over 35-75 s, look (x_s + 0.5, 0.789 z_s), vertical FOV 23.5 deg); front view = d 30-90 m
           shoreward, y_off 10 / 0 / 20 m, eye at the summit height raised until clear, the candidate nearest d 50 / y_off 10 with the face and
           the near crest line >= 95 % visible at every period summit.
  export   f3d51_export_e51.py long (print and front): clips of 35-75 s with the run's surf records (24/s when r5 is every frame), print record =
           the red period's e51 summit, double-sided water (display only).
  unity    FLIP3DBatch -f3dcap cstills,cprint 1920x1080 (as X2), stills at every judged period summit -1 s / 0 / +1 s and at pv53's most
           print-like frame. Side effect (as every FLIP3D capture): Assets/GreatWave/FLIP3D Scenes / Materials are re-saved; nothing is committed
           or reverted here.
  compose  stills with caption bands, a period sheet, real-time mp4 per view (2 s hold at the converged summit) and print | front side by side.
Writes only: <run>/x2b/view/ (json, section, cams, stills, mp4 copies), Unity/Build/FLIP3D/{clip,capture}_X2B_* and Unity/Build/FLIP3D/video/.
usage: py -3.10 -B x51b_view.py all <run_dir> [--steps=section,cams,export,unity,compose] [--no-unity]
Tags: [measured] records, ruler values; [computed] cameras, snapping; [chosen] camera rules (copied from cam_x2.py). The user judges the look.
"""
import os, sys, json, math, time, glob, re, csv, shutil, subprocess, importlib.util

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
import x51b_common as XB              # noqa: E402

TOOL = "Tools/GWWaveGen/flip51/x51b_view.py"
REPO = XB.REPO
X2V = XB.X2VIEW
B3 = REPO + "/Unity/Build/FLIP3D"
VID = B3 + "/video"
EXPORT = REPO + "/Tools/GWWaveGen/flip51/f3d51_export_e51.py"
UNITY_PS1 = REPO + "/Tools/GWWaveGen/flip3d/f3d_unity.ps1"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FPS = 24.0
F0, F1 = 841, 1801
HOLD_S = 2.0
TITLE = "X2B'（S51X2B：X2 の向きの組 34 成分・T 7 s・a_sum 6.33 m、焦点 x 275.25 m、横の帯は x 210.25 m まで作る・1:10 の斜面・粒子 0.5 m）"
STEPS = ("section", "cams", "export", "unity", "compose")


def t_of(f):
    return (f - 1) / FPS


def load_ro(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


VDIR_OVERRIDE = None                  # --out=<dir under Unity/Build/FLIP51/_scratch> for tests on another run (e.g. X2)


def vdir(rd):
    return VDIR_OVERRIDE or (rd + "/x2b/view")


def jl(p):
    return XB.jload(p)


def judge_of(rd):
    return jl(rd + "/e51/judge_E05.json") or {}


def screen_of(rd):
    return jl(rd + "/e51/screen_E05.json") or {}


def pv53_of(rd):
    rid = os.path.basename(rd)
    return jl(REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (rid, rid)) or {}


def red_of(rd):
    return judge_of(rd).get("red_instant") or screen_of(rd).get("red_instant") or {}


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    return o


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)


# ====================================================================== section (x2_section.py, read only)
def section_module(rd, od):
    S2 = load_ro("x2_section_for_x2b", X2V + "/x2_section.py")
    S2.RD = rd
    S2.OUT = od
    S2.F0, S2.F1 = F0, F1
    return S2


def analyse(S2, rd, od, log=print):
    """x2_section.analyse rules with guards (a period without a centre-row crest at its e51 frame uses the plain g49 call there)."""
    S = S2.X2()
    sc = json.load(open(od + "/scan_rows.json", encoding="utf8"))
    rows = [r for r in sc["rows"] if r.get("score3") is not None]
    byf = {}
    for r in rows:
        byf.setdefault(r["frame"], []).append(r)
    scr, jud = screen_of(rd), judge_of(rd)
    jp = {int(p["n"]): p for p in (jud.get("periods") or []) if p.get("f") is not None and p.get("complete") is not False}
    res = []
    for p in scr.get("periods") or []:
        if not p.get("complete") or p.get("f") is None:
            continue
        n, f0, x_pk = int(p["n"]), int(p["f"]), float(p["x_pk"])
        w0, w1 = int(round(p["window"][0] * FPS)) + 1, int(round(p["window"][1] * FPS)) + 1
        cands = byf.get(f0, [])
        at = min(cands, key=lambda r: abs(r["crest_hf"]["x"] - x_pk)) if cands else None
        flag = None
        if at is None:
            try:
                at = {k: v for k, v in S.measure(f0, x_pk).items() if k != "_mask"}
                at["crest_hf"] = dict(x=x_pk, eta=None)
                flag = "no centre-row crest found by the scan at the e51 frame: the plain g49 call at the e51 summit"
            except Exception as ex:
                at = None
                flag = "no ruler at the e51 summit: %s" % repr(ex)[:160]
        trk = {f0: at} if at else {}
        for d, rng in ((-1, range(f0 - 1, w0 - 1, -1)), (1, range(f0 + 1, w1 + 1))):
            x = at["crest_hf"]["x"] if at else x_pk
            for f in rng:
                c = [r for r in byf.get(f, []) if -1.0 <= (r["crest_hf"]["x"] - x) * d <= 4.0]
                if not c:
                    break
                r = min(c, key=lambda r: abs(r["crest_hf"]["x"] - x))
                trk[f] = r
                x = r["crest_hf"]["x"]
        tr = [r for r in trk.values() if r]
        tb = min(tr, key=lambda r: (r["score3"], r["frame"])) if tr else None
        win = [r for f in range(w0, w1 + 1) for r in byf.get(f, [])]
        ab = min(win, key=lambda r: (r["score3"], r["frame"])) if win else None
        J = jp.get(n) or {}
        jr = None
        if J and int(J["f"]) != f0:
            jc = byf.get(int(J["f"]), [])
            jr = min(jc, key=lambda r: abs(r["crest_hf"]["x"] - float(J["x_pk"]))) if jc else None
        for q in (at, tb, ab, jr):
            if q:
                S2.add_depth(q)
        res.append(dict(n=n, e51=dict(n=n, frame=f0, t=float(p["t"]), x_pk=x_pk, Hc=float(p["Hc"]), miss=p.get("miss"), window=p["window"],
                                      judge_frame=int(J["f"]) if J else None, judge_x_pk=float(J["x_pk"]) if J else None, judge_Hc=J.get("Hc"),
                                      judge_instant=J.get("instant")),
                        at_summit=at, at_summit_flag=flag, track=dict(frames=[min(trk), max(trk)] if trk else None, n=len(tr),
                                                                      lip_max=max([(r.get("lip") or 0.0) for r in tr] or [0.0]),
                                                                      hood_max=max([(r.get("hood") or 0.0) for r in tr] or [0.0]),
                                                                      chord_max=max([(r.get("chord") or 0.0) for r in tr] or [0.0])),
                        track_best=tb, any_best=ab, judge_instant_row=jr, window_frames=[w0, w1],
                        window_any_lip_max=max([(r.get("lip") or 0.0) for r in win] or [0.0])))
    lips = [r for r in rows if (r.get("lip") or 0.0) > 0.0 or (r.get("hood") or 0.0) > 0.0]
    lip_x = [r["x_c"] for r in lips if r.get("x_c") is not None]
    sea = [r for r in rows if (S2.depth(r.get("x_c")) or -1) > 0.0]
    summ = dict(n_rows=len(rows), n_frames=len(byf), n_rows_with_lip_or_hood=len(lips), lip_or_hood_x_range=[min(lip_x), max(lip_x)] if lip_x else None,
                lip_or_hood_eta_c_max=max((r["eta_c"] or 0.0) for r in lips) if lips else None,
                best_overall=S2.add_depth(min(rows, key=lambda r: (r["score3"], r["frame"]))) if rows else None,
                best_overall_seaward_of_shoreline=S2.add_depth(min(sea, key=lambda r: (r["score3"], r["frame"]))) if sea else None,
                best_overall_eta_ge_4=min([r for r in rows if (r.get("eta_c") or 0) >= 4.0], key=lambda r: (r["score3"], r["frame"]), default=None),
                red_instant_screen=scr.get("red_instant"), red_instant_judge=jud.get("red_instant"))
    import g47_video as GV
    o = dict(run=rd, off=S.off, periods=res, summary=summ, print=dict(print_cn=GV.print_ref()["cnv"], print_bands=GV.print_ref()["bands"]),
             tool=TOOL + " (x2_section.py rules, read only)", date=time.strftime("%Y-%m-%d %H:%M:%S"))
    jdump(o, od + "/x2b_section.json")
    return o


def panels(S2, rd, od, o, log=print):
    S = S2.X2()
    out = {}
    pv = pv53_of(rd)
    mp = pv.get("most_print_like") or {}
    if mp.get("frame") is not None:
        r = dict(frame=int(mp["frame"]), x_guess=float(mp["x_c"]), clear=None)
        try:
            im, m = S2.panel(S, r, "原画に最も近い瞬間（pv53、周期 n%s の頂の線）" % mp.get("n"), 940, 470)
            p = od + "/section_print_like_f%d.png" % r["frame"]
            im.save(p); out["section_print_like"] = p; out["section_print_like_ruler"] = m
        except Exception as ex:
            out["section_print_like_error"] = repr(ex)[:200]
    red = red_of(rd)
    if red.get("frame") is not None:
        f = int(red["frame"])
        jp = {int(p["n"]): p for p in (judge_of(rd).get("periods") or []) if p.get("f") is not None}
        x_pk = float((jp.get(int(red["n"])) or {}).get("x_pk") or 0.0)
        sc = json.load(open(od + "/scan_rows.json", encoding="utf8"))
        c = [q for q in sc["rows"] if q.get("frame") == f and q.get("score3") is not None]
        if c:
            q = min(c, key=lambda q: abs(q["crest_hf"]["x"] - x_pk))
            r = dict(frame=f, x_guess=float(q["crest_hf"]["x"]), clear=q.get("clear"))
        else:
            r = dict(frame=f, x_guess=x_pk, clear=None)
        try:
            im, m = S2.panel(S, r, "最も集まった瞬間（e51 の赤い瞬間、周期 n%s、コマ %d）" % (red.get("n"), f), 940, 470)
            p = od + "/section_converged_f%d.png" % f
            im.save(p); out["section_converged"] = p; out["section_converged_ruler"] = m
        except Exception as ex:
            out["section_converged_error"] = repr(ex)[:200]
    return out


def step_section(rd, log=print):
    od = vdir(rd) + "/section"
    os.makedirs(od, exist_ok=True)
    S2 = section_module(rd, od)
    if not os.path.exists(od + "/scan_rows.json") or os.path.getmtime(od + "/scan_rows.json") < os.path.getmtime(rd + "/e51/judge_E05.json"):
        S2.scan()
    o = analyse(S2, rd, od, log)
    pn = panels(S2, rd, od, o, log)
    s = o["summary"]
    log("  section: %d periods, rows %d, lip/hood x range %s, best overall score3 %s at x %s" % (
        len(o["periods"]), s["n_rows"], s["lip_or_hood_x_range"], (s.get("best_overall") or {}).get("score3"), (s.get("best_overall") or {}).get("x_c")))
    return dict(ok=True, json=od + "/x2b_section.json", summary=s, panels=pn,
                at_summit=[dict(n=p["n"], frame=(p["at_summit"] or {}).get("frame"), score3=(p["at_summit"] or {}).get("score3"),
                                lip=(p["at_summit"] or {}).get("lip"), flag=p["at_summit_flag"]) for p in o["periods"]])


# ====================================================================== cameras (cam_x2.py rules, read only)
def surf_frames(rd):
    out = []
    for p in glob.glob(rd + "/surf/s_*.gw45s"):
        m = re.search(r"s_(\d+)\.gw45s$", p.replace("\\", "/"))
        if m:
            out.append(int(m.group(1)))
    return sorted(f for f in out if F0 <= f <= F1)


def step_cams(rd, log=print):
    od = vdir(rd) + "/cams"
    os.makedirs(od, exist_ok=True)
    C = load_ro("cam_x2_for_x2b", X2V + "/cam_x2.py")
    C.RD = rd
    C.OUT = od
    F = C.Field()
    jud = judge_of(rd)
    eta0 = float(jud["eta0"])
    recs = np.array(surf_frames(rd))
    if len(recs) < 2:
        raise RuntimeError("no surface records in frames %d-%d" % (F0, F1))
    per = []
    for p in jud.get("periods") or []:
        if p.get("f") is None or p.get("complete") is False:
            continue
        q = dict(n=int(p["n"]), frame=int(p["f"]), t=float(p["t"]), x_pk=float(p["x_pk"]), Hc=float(p["Hc"]))
        i = int(np.argmin(np.abs(recs - q["frame"]) * 2 + (recs > q["frame"])))
        q["record"] = int(recs[i])
        k = F.fi[q["record"]]
        q["x_s"], q["z_s"] = C.crest_row(F, k, q["x_pk"] - 8.0, q["x_pk"] + 8.0)
        per.append(q)
    red = red_of(rd)
    s0 = [q for q in per if q["n"] == int(red.get("n", -1))]
    s0 = s0[0] if s0 else max(per, key=lambda q: q["Hc"])
    x_s, z_s = s0["x_s"], s0["z_s"]
    Hc = z_s - eta0
    D = C.D_PRINT
    pos0 = [x_s + D["dx"], -D["lateral"], D["h_over"] * z_s]
    look = [x_s + D["look_dx"], 0.0, D["look_over"] * z_s]
    tries, z = [], pos0[2]
    while True:
        c = F.clearance(pos0[0], pos0[1], z)
        tries.append(dict(eye_z=round(z, 3), **c))
        if c["eye_min"] >= C.CLEAR_MIN and c["near_min"] >= C.NEAR_MIN:
            break
        z += 0.25
        if z > 20:
            raise RuntimeError("print view: no clear eye below 20 m")
    pos = [pos0[0], pos0[1], z]
    pvis = {}
    for q in per:
        k = F.fi[q["record"]]
        e = F.E[k, 0]
        sel = np.where((F.xs >= q["x_s"] - 25.0) & (F.xs <= q["x_s"] + 10.0) & np.isfinite(e))[0]
        pts = [(float(F.xs[i]), 0.5, float(e[i])) for i in sel]
        upper = [w for w in pts if w[2] >= 0.5 * q["z_s"]]
        v_all = F.visible(k, pos, pts); v_up = F.visible(k, pos, upper) if upper else np.array([])
        vc = F.visible(k, pos, [(q["x_s"], 0.5, q["z_s"])])[0]
        pj = C.project(pos, look, D["fov"], 16 / 9, [(q["x_s"], 0.0, q["z_s"]), (q["x_s"], 0.0, eta0)])
        pvis[q["n"]] = dict(record=q["record"], x_s=q["x_s"], z_s=q["z_s"], crest_visible=bool(vc), profile_visible=float(v_all.mean()) if len(v_all) else None,
                            upper_half_visible=float(v_up.mean()) if len(v_up) else None,
                            crest_in_frame=dict(right=pj[0][0], up=pj[0][1], dist=pj[0][2]), crest_foot_in_frame=dict(right=pj[1][0], up=pj[1][1]))
    print_cam = dict(unity=dict(printPos=[round(pos[0], 3), round(pos[2], 3), round(pos[1], 3)], printLookAt=[round(look[0], 3), round(look[2], 3), 0.0],
                                printFovV=D["fov"]),
                     plan=dict(pos=pos, look=look), rule=D, transferred_eye_z=round(pos0[2], 3), eye_raised_m=round(pos[2] - pos0[2], 3),
                     clearance_steps=tries, clearance=tries[-1], visibility=pvis,
                     distance_to_summit_m=float(math.dist((pos[0], pos[1], pos[2]), (x_s, 0.0, z_s))))
    cands = []
    for yoff in (10.0, 0.0, 20.0):
        for d in range(30, 95, 5):
            ex, ey = x_s + d, -yoff
            z = z_s
            while True:
                c = F.clearance(ex, ey, z)
                if c["eye_min"] >= C.CLEAR_MIN and c["near_min"] >= C.NEAR_MIN:
                    break
                z += 0.25
                if z > 30:
                    break
            eye = [ex, ey, z]
            lk = [x_s, 0.0, 0.5 * z_s]
            dist = math.dist((ex, ey), (x_s, 0.0))
            hfov = 2 * math.degrees(math.atan(4.0 * Hc / dist))
            vfov = 2 * math.degrees(math.atan(math.tan(math.radians(hfov) / 2) * 9 / 16))
            vis = {}
            for q in per:
                k = F.fi[q["record"]]
                e = F.E[k, 0]
                sel = np.where((F.xs >= q["x_s"] - 0.5) & (F.xs <= q["x_s"] + 15.0) & np.isfinite(e))[0]
                face = [(float(F.xs[i]), 0.5, float(e[i])) for i in sel if e[i] >= 0.3 * q["z_s"]]
                cl = C.crest_line(F, k, q["x_s"], q["z_s"], 2.0 * Hc)
                v1 = F.visible(k, eye, face) if face else np.array([])
                v2 = F.visible(k, eye, [(a, -b, c_) for a, b, c_ in cl]) if cl else np.array([])
                vis[q["n"]] = dict(face=float(v1.mean()) if len(v1) else None, crest_line=float(v2.mean()) if len(v2) else None)
            ok = all((v["face"] or 0) >= 0.95 and (v["crest_line"] or 0) >= 0.95 for v in vis.values())
            cands.append(dict(d=d, y_off=yoff, eye=eye, eye_over_summit=round(z - z_s, 3), look=lk, fov_v=round(vfov, 2), fov_h=round(hfov, 2), clear=c,
                              vis=vis, ok=ok))
    okc = [c for c in cands if c["ok"] and c["clear"]["eye_min"] >= C.CLEAR_MIN]
    pref = {10.0: 0, 0.0: 1, 20.0: 2}
    pool = okc or [c for c in cands if c["clear"]["eye_min"] >= C.CLEAR_MIN]          # none fully visible: the nearest clear candidate (flagged)
    ch = min(pool, key=lambda c: (abs(c["d"] - 50) + 25 * pref[c["y_off"]], c["eye"][2])) if pool else None
    front = None
    if ch:
        front = dict(unity=dict(printPos=[round(ch["eye"][0], 3), round(ch["eye"][2], 3), round(ch["eye"][1], 3)],
                                printLookAt=[round(ch["look"][0], 3), round(ch["look"][2], 3), 0.0], printFovV=ch["fov_v"]),
                     plan=dict(pos=ch["eye"], look=ch["look"]), chosen=ch, all_visible=bool(okc),
                     rule="cam_x2.py (b) FRONT VIEW rule, anchored at X2B's converged summit")
    res = dict(run_id=os.path.basename(rd), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " (cam_x2.py rules, read only)", eta0=eta0, periods=per,
               summit=dict(n=s0["n"], record=s0["record"], x=x_s, z_raw=z_s, Hc=Hc, e51_frame=s0["frame"], e51_x_pk=s0["x_pk"], e51_Hc=s0["Hc"],
                           source="judge_E05.json red instant (the most converged period)"),
               summit_n6=dict(record=s0["record"], x=x_s, z_raw=z_s, Hc=Hc, note="key kept for the X2 tools; it is the converged summit n%d" % s0["n"]),
               print=print_cam, front=front, front_candidates=cands,
               clearance_rule=dict(window_frames=[F0, F1], eye_min=C.CLEAR_MIN, near_min=C.NEAR_MIN, near_r=C.NEAR_R))
    p = od + "/cameras_X2B.json"
    jdump(res, p)
    log("  cams: summit n%d record %d x %.1f z %.2f (Hc %.2f); print %s eye raised %.2f m; front %s" % (
        s0["n"], s0["record"], x_s, z_s, Hc, print_cam["unity"], print_cam["eye_raised_m"], (front or {}).get("unity")))
    return dict(ok=bool(front), json=p, summit=res["summit"], print=print_cam["unity"], front=(front or {}).get("unity"),
                front_all_visible=(front or {}).get("all_visible"))


# ====================================================================== export (f3d51_export_e51.py, unchanged)
CAP_TAG = "X2B"                       # --cap-tag (tests only: read another run's existing clips / captures, e.g. X2)
MAX_FRAMES = None                     # --max-frames (tests only: compose only the first N frames)


def clip_name(rd, view):
    fr = surf_frames(rd)
    step = (fr[1] - fr[0]) if len(fr) > 1 else 3
    return "clip_%s_f%d_%d_r%d_%s_ds" % (CAP_TAG, F0, F1, round(FPS / step), view)


def vid_dir():
    return (VDIR_OVERRIDE + "/video") if VDIR_OVERRIDE else VID


def step_export(rd, log=print):
    out = {}
    sec = vdir(rd) + "/section/x2b_section.json"
    cams = vdir(rd) + "/cams/cameras_X2B.json"
    red_n = int(red_of(rd).get("n"))
    scr_n = [int(p["n"]) for p in screen_of(rd).get("periods") or [] if p.get("complete") and p.get("f") is not None]
    pk = red_n if red_n in scr_n else (scr_n[0] if scr_n else red_n)
    for view in ("print", "front"):
        name = clip_name(rd, view)
        cmd = ["py", "-3.10", "-B", EXPORT, "long", "--run", rd, "--section", sec, "--cams", cams, "--view", view, "--print-k", str(pk),
               "--water-double-sided", "--name", name, "--from-s", "35", "--to-s", "75"]
        t0 = time.time()
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        clip = B3 + "/" + name
        ok = r.returncode == 0 and os.path.exists(clip + "/manifest.json")
        if ok:
            mp = clip + "/manifest.json"
            man = json.load(open(mp, encoding="utf8"))
            man["e51_note_ja"] = ("X2B' の計算には pana/best_frames.json はない（x51b_ana.py が x51_ana.py の決まりで e51 を読む）。f3d51_export_e51.py が e51 の"
                                  "周期の頂（screen_E05.json の scan の頂）を best_frames の代わりに渡した（メモリの中だけ）。最も集まった瞬間は judge_E05.json の"
                                  "赤い瞬間 n%d のコマ %s（%s）。この注は x51b_view.py が書き直した（f3d51_export_e51.py の既定の文は X2 のもの）" % (
                                      red_n, red_of(rd).get("frame"), TOOL))
            man["x2b_view"] = dict(tool=TOOL, print_k=pk, red_instant=red_of(rd))
            json.dump(man, open(mp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        out[view] = dict(ok=ok, clip=clip, rc=r.returncode, seconds=round(time.time() - t0, 1), tail=(r.stdout or "")[-400:] + (r.stderr or "")[-600:])
        log("  export %s: rc %s ok %s %s" % (view, r.returncode, ok, clip))
    out["ok"] = all(v.get("ok") for k, v in out.items() if isinstance(v, dict))
    return out


# ====================================================================== Unity (FLIP3DBatch through f3d_unity.ps1)
def moves(rd):
    fr = set()
    avail = set(surf_frames(rd))
    for p in judge_of(rd).get("periods") or []:
        if p.get("f") is None:
            continue
        for d in (-24, 0, 24):
            f = int(p["f"]) + d
            if f in avail:
                fr.add(f)
    mp = pv53_of(rd).get("most_print_like") or {}
    if mp.get("frame") and int(mp["frame"]) in avail:
        fr.add(int(mp["frame"]))
    r = red_of(rd).get("frame")
    if r and int(r) in avail:
        fr.add(int(r))
    return sorted(fr)


def step_unity(rd, log=print):
    out = {}
    fr = moves(rd)
    sf = surf_frames(rd)
    t_to = t_of(sf[-1]) + ((sf[1] - sf[0]) / FPS if len(sf) > 1 else 1.0 / 8)
    for view in ("print", "front"):
        clip = B3 + "/" + clip_name(rd, view)
        cap = clip.replace("/clip_", "/capture_")
        extra = ("-f3dcap cstills,cprint -f3dsize 1920x1080 -f3dtiles 0 -f3dsha -f3ddata %s -f3dfrom 35 -f3dto %.4f -f3dmoves %s -f3dhold 0 -f3dout %s"
                 % (clip, t_to, ";".join("f%d" % f for f in fr), cap))
        ps = "& '%s' -Method 'GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture' -Log 'X2B_%s_cap' -Extra '%s' -LockWaitMinutes 120 -TimeoutMinutes 45" % (
            UNITY_PS1, view, extra)
        t0 = time.time()
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        txt = (r.stdout or "") + (r.stderr or "")
        ok = r.returncode == 0 and os.path.exists(cap + "/cprint/frames.csv")
        out[view] = dict(ok=ok, rc=r.returncode, capture=cap, seconds=round(time.time() - t0, 1), moves=fr, tail=txt[-800:])
        log("  unity %s: rc %s ok %s %.0f s" % (view, r.returncode, ok, time.time() - t0))
    out["ok"] = all(v.get("ok") for k, v in out.items() if isinstance(v, dict))
    out["side_effect"] = "FLIP3DBatch.BuildSceneAndCapture re-saves Assets/GreatWave/FLIP3D Scenes / Materials (as every FLIP3D capture); not reverted, not committed"
    return out


# ====================================================================== compose (stills, sheet, mp4)
def step_compose(rd, log=print):
    from PIL import Image, ImageDraw
    CX = load_ro("compose_x2_for_x2b", X2V + "/compose_x2.py")
    od = vdir(rd) + "/stills"
    os.makedirs(od, exist_ok=True)
    os.makedirs(vid_dir(), exist_ok=True)
    jud = judge_of(rd)
    red = red_of(rd)
    cams = jl(vdir(rd) + "/cams/cameras_X2B.json") or {}
    per = {int(p["n"]): p for p in jud.get("periods") or [] if p.get("f") is not None}
    out = dict(stills={}, mp4={})
    vt = {"print": "原画の視点（方案 D の原画の視点を X2B' の最も集まった頂へ移した：DM1A の原画の視点と同じ m/画素）",
          "front": "正面の視点（頂から岸側、目の高さ＝頂の高さ、沖の頂の前の面を見る：利用者の 10/17 の画面に近い向き）"}
    for view in ("print", "front"):
        cap = (B3 + "/" + clip_name(rd, view)).replace("/clip_", "/capture_")
        cd = cap + "/cstills"
        try:
            rows = {r["name"]: r for r in csv.DictReader(open(cd + "/cstills.csv", encoding="utf8"))}
            f = int(red["frame"]) if red.get("frame") else None
            key = "f%d_arrive" % f if f else None
            if f and key not in rows:                 # the red frame is not a capture still: the nearest one (ties earlier)
                av = sorted(int(k[1:].split("_")[0]) for k in rows if re.match(r"^f\d+_arrive$", k))
                if av:
                    f = min(av, key=lambda q: (abs(q - f), q))
                    key = "f%d_arrive" % f
            if key in rows and os.path.exists(cd + "/%s.png" % key):
                im = CX.band(Image.open(cd + "/%s.png" % key), [TITLE, vt[view], "最も集まった瞬間 n%s：e51 の赤い瞬間 コマ %d（t %.3f s、Hc %.2f m、miss %.2f）" % (
                    red.get("n"), f, t_of(f), float(red.get("Hc") or 0), float(red.get("miss") or 0))], red=True)
                p = od + "/X2B_%s_f%d.png" % (view, f)
                im.save(p)
                out["stills"]["%s_conv" % view] = p
            # period sheet: rows = periods, columns = -1 s / summit / +1 s
            tw, th = 480, 270
            ns = sorted(per)
            S = Image.new("RGB", (tw * 3, 60 + (th + 28) * len(ns)), (255, 255, 255))
            d = ImageDraw.Draw(S)
            d.text((8, 6), TITLE, font=CX.fit(d, TITLE, 18, tw * 3 - 16), fill=(0, 0, 0))
            d.text((8, 32), vt[view], font=CX.fit(d, vt[view], 14, tw * 3 - 16), fill=(60, 60, 60))
            for i, n in enumerate(ns):
                for j, dt in enumerate((-24, 0, 24)):
                    f = int(per[n]["f"]) + dt
                    pp = cd + "/f%d_arrive.png" % f
                    x0, y0 = j * tw, 60 + i * (th + 28)
                    d.text((x0 + 4, y0 + 2), "n%d %s：コマ %d（t %.2f s）%s" % (n, ("−1 s", "頂", "+1 s")[j], f, t_of(f),
                                                                           ("・Hc %.2f m・x %.1f m" % (per[n]["Hc"], per[n]["x_pk"])) if dt == 0 else ""),
                           font=CX.F(13), fill=(20, 20, 20))
                    if os.path.exists(pp):
                        S.paste(Image.open(pp).convert("RGB").resize((tw, th), Image.LANCZOS), (x0, y0 + 24))
                    if dt == 0 and n == int(red.get("n", -1)):
                        d.rectangle([x0, y0 + 24, x0 + tw - 1, y0 + 24 + th - 1], outline=(230, 0, 0), width=5)
            p2 = od + "/X2B_%s_sheet.jpg" % view
            S.save(p2, quality=90)
            out["stills"]["%s_sheet" % view] = p2
        except Exception as ex:
            out["stills"]["%s_error" % view] = repr(ex)[:300]
        # video
        try:
            cdp = cap + "/cprint"
            fr = list(csv.DictReader(open(cdp + "/frames.csv", encoding="utf8")))
            if MAX_FRAMES:
                fr = fr[:MAX_FRAMES]
            tmp = vid_dir() + "/_frames_X2B_%s" % view
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)
            summ = {int(p["f"]): n for n, p in per.items()}
            t0, t1 = 35.0, 75.0
            k = 0
            lines = [TITLE, vt[view], "面の記録を実時間（24 フレーム/s）で 35〜75 s を 1 回。赤い枠＝その周期の判定の瞬間（e51）。最も集まった瞬間で %.0f s 止め" % HOLD_S]
            for i, r in enumerate(fr):
                sfm, st = int(r["sim_frame"]), float(r["sim_t"])
                n = summ.get(sfm)
                bot = "計算の時刻 %.3f s（コマ %d）" % (st, sfm)
                if n:
                    bot += "　n%d（Hc %.2f m、x %.1f m、miss %s）%s" % (n, per[n]["Hc"], per[n]["x_pk"], ("%.2f" % per[n]["miss"]) if per[n].get("miss") is not None else "-",
                                                               "　★ 最も集まった瞬間" if n == int(red.get("n", -1)) else "")
                im = CX.band(Image.open(cdp + "/frame_%05d.jpg" % i), lines, bottom=bot, red=bool(n))
                dr = ImageDraw.Draw(im)
                W, H = im.size
                x0, x1, y = 300, W - 40, H - 62
                X = lambda t: x0 + (t - t0) / (t1 - t0) * (x1 - x0)
                dr.line([(x0, y), (x1, y)], fill=(200, 200, 200), width=2)
                for nn, p in per.items():
                    tt = t_of(int(p["f"]))
                    dr.line([(X(tt), y - 8), (X(tt), y + 8)], fill=(255, 80, 80) if nn == int(red.get("n", -1)) else (255, 210, 60), width=3)
                    dr.text((X(tt) - 10, y - 22), "n%d" % nn, font=CX.F(13), fill=(255, 210, 60))
                dr.ellipse([X(st) - 6, y - 6, X(st) + 6, y + 6], fill=(255, 255, 255))
                last = (i + 1 >= len(fr) or int(fr[i + 1]["sim_frame"]) != sfm)
                reps = 1 + (int(round(HOLD_S * FPS)) if (n is not None and n == int(red.get("n", -1)) and last) else 0)
                for _ in range(reps):
                    im.save(tmp + "/f_%05d.jpg" % k, quality=90); k += 1
            mp4 = vid_dir() + "/FLIP3D_X2B_%s_ds_35_75s.mp4" % view
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", tmp + "/f_%05d.jpg", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-crf", "20", "-preset", "medium", "-movflags", "+faststart", mp4], check=True)
            shutil.rmtree(tmp, ignore_errors=True)
            out["mp4"][view] = mp4
        except Exception as ex:
            out["mp4"]["%s_error" % view] = repr(ex)[:300]
    if out["mp4"].get("print") and out["mp4"].get("front"):
        sbs = vid_dir() + "/FLIP3D_X2B_print_front_35_75s.mp4"
        r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", out["mp4"]["print"], "-i", out["mp4"]["front"], "-filter_complex",
                            "[0:v]scale=960:540[a];[1:v]scale=960:540[b];[a][b]hstack=inputs=2[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-crf", "20", "-preset", "medium", "-movflags", "+faststart", sbs], capture_output=True, text=True)
        if r.returncode == 0:
            out["mp4"]["side_by_side"] = sbs
    vd = vdir(rd) + "/video"
    os.makedirs(vd, exist_ok=True)
    for k, v in list(out["mp4"].items()):
        if isinstance(v, str) and v.endswith(".mp4") and os.path.exists(v) and os.path.dirname(v) != vd:
            shutil.copyfile(v, vd + "/" + os.path.basename(v))
    out["ok"] = bool(out["stills"].get("print_conv") and out["mp4"].get("print"))
    log("  compose: stills %s mp4 %s" % (sorted(out["stills"]), sorted(out["mp4"])))
    return out


# ====================================================================== all
def run_all(rd, steps=STEPS, log=print):
    rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
    os.makedirs(vdir(rd), exist_ok=True)
    vp = vdir(rd) + "/view_X2B.json"
    V = jl(vp) or {}
    V.update(run_id=os.path.basename(rd), tool=TOOL, tool_sha256=XB.sha256_file(os.path.abspath(__file__)), date=time.strftime("%Y-%m-%d %H:%M:%S"),
             reused_read_only={k: XB.sha256_file(v) for k, v in XB.view_files().items()})
    V.setdefault("steps", {})
    fn = dict(section=step_section, cams=step_cams, export=step_export, unity=step_unity, compose=step_compose)
    for s in STEPS:
        if s not in steps:
            continue
        t0 = time.time()
        log("x51b_view %s ..." % s)
        try:
            r = fn[s](rd, log)
        except Exception as ex:
            import traceback
            r = dict(ok=False, error=repr(ex)[:400], trace=traceback.format_exc()[-1500:])
            log("  %s FAILED: %s" % (s, repr(ex)[:300]))
        r["seconds"] = round(time.time() - t0, 1)
        V["steps"][s] = r
        jdump(V, vp)
    st = V["steps"]
    sec = (st.get("section") or {}).get("panels") or {}
    comp = st.get("compose") or {}
    V["stills"] = dict(print_conv=(comp.get("stills") or {}).get("print_conv"), front_conv=(comp.get("stills") or {}).get("front_conv"),
                       print_sheet=(comp.get("stills") or {}).get("print_sheet"), front_sheet=(comp.get("stills") or {}).get("front_sheet"),
                       section_print_like=sec.get("section_print_like"), section_converged=sec.get("section_converged"))
    V["mp4"] = comp.get("mp4")
    V["ok"] = {s: bool((st.get(s) or {}).get("ok")) for s in STEPS if s in st}
    jdump(V, vp)
    return V


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if len(a) < 2 or a[0] != "all":
        print(__doc__); sys.exit(1)
    steps = tuple(s for s in opt.get("steps", ",".join(STEPS)).split(",") if s in STEPS)
    if opt.get("out"):
        o = os.path.abspath(opt["out"]).replace("\\", "/")
        if not o.lower().startswith((XB.B51 + "/_scratch/").lower()):
            raise SystemExit("--out must be under Unity/Build/FLIP51/_scratch (tests)")
        global VDIR_OVERRIDE, CAP_TAG, MAX_FRAMES
        VDIR_OVERRIDE = o
        CAP_TAG = opt.get("cap-tag", CAP_TAG)
        MAX_FRAMES = int(opt["max-frames"]) if opt.get("max-frames") else None
    if "no-unity" in opt:
        steps = tuple(s for s in steps if s not in ("unity",))
    V = run_all(a[1], steps)
    print(json.dumps(clean(dict(ok=V.get("ok"), stills=V.get("stills"), mp4=V.get("mp4"), json=vdir(os.path.abspath(a[1]).replace("\\", "/").rstrip("/")) + "/view_X2B.json")),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
