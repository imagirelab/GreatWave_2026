# -*- coding: utf-8 -*-
"""FLIP53 pv53: the PRINT-VIEW package of one run (py -3.10 -B; numpy, scipy, scikit-image, PIL, ffmpeg, Unity batch). 2026-10-17 written new (Claude).

Why (user 2026-10-17 ~21:50): the analysis figures built from the screenshot metrics (front, top, centre section) were checked without
checking the most important thing, whether the run matches the ORIGINAL PRINT's view. From now on every run's evaluation shows, side by side
and as CO-EQUAL criteria:
  (1) the Unity PRINT-VIEW render at the run's most print-like instant (+ a front view of the same instant, + the print itself),
  (2) the centre section vs the Hokusai print outline with the print ruler (STUDY52 cn outline; score3 and its parts, hollow, lip, back 0.7-0.9
      eta_c, width07),
  (3) the convergence metrics (flip51/e51_metrics.py, frozen ruler; target read from the user's screenshot, used only through its frozen
      read values; the screenshot itself is never copied, embedded or uploaded).
New goals are constraints on top of the print match, never replacements.

Read only: the run folder (FLIP50 / FLIP51 / FLIP52 layouts), its judge file (FLIP51 e51/judge_*.json or screen_*.json, FLIP52
g52/judge_DFG.json or smoke_DFG.json, FLIP50 the e51 baseline Unity/Build/FLIP51/target/baseline.json), DM1A's pana/best_frames.json (the
reference), the option-D camera file Unity/Build/FLIP50/_scratch/cameras/cameras_DM1A.json, Docs/References/Met_JP1847.jpg (the print, public
domain). No file of flip3d, flip46-flip52 or flip50g2 is edited: their functions are imported (g50_ana -> g49_periodic_ana.Ctx49, g46 r2_mask,
STUDY52 measure_mask, d_shape_measure.pick, g47_video.score3 / print_phys, e51_metrics, f3d50_export.Run / main_long).
Writes only: Unity/Build/FLIP53/pv53/<run_id>/ (report png / json / stills / mp4), Unity/Build/FLIP3D/pv53_<run_id>_f<frame>/ (the clip:
GW45LIST1 manifest that STREAMS the run's own surf records, no copy) and Unity/Build/FLIP3D/pv53cap_<run_id>_f<frame>/ (the Unity frames).
All of Unity/Build is git-ignored.

Rules (written before any FLIP51 0.5 m run was measured with this code; tags: 【測定】 measured, 【計算】 derived, 【選び】 chosen):
  periods      FLIP51: the judge's periods (its 'max' instant f, summit x_pk); FLIP52: the judge's groups (f, x_pk) or the smoke's group
               summits; FLIP50: the e51 baseline per-breaker 'max' instants (fallback: pana/best_frames windows).
  print-like   per period, the centre section r2 (y 0.5 m) at EVERY frame in [t_max - 1.5 s, t_max + 3.0 s] is measured with the D ruler
  instant      (g46 r2_mask -> STUDY52 measure_mask -> d_shape_measure.pick, the code that made DM1A's pana/best_frames.json); the
               frame with the smallest score3 (g47_video.score3 = chord 0.1-0.5 eta_c + front foot 0.1 eta_c + hood area band misses;
               ties: smaller chord miss, then higher hood) is the period's most print-like instant 【選び】 (the window covers DM1A's
               onset .. touchdown + 0.5 s: its best frames are 0.96-1.58 s after its e51 'max' 【測定】). The crest guess per frame
               follows the top of the centre hf row (3-point median) from the 'max' summit, -1.0 .. +2.5 m per frame forward,
               -2.5 .. +1.0 m backward. The run's most print-like instant = the period with the smallest best score3 (ties: earlier).
               Crest floor (AM-DFG2a, registered before any 0.5 m DFG result): a frame is a candidate only if its section crest
               eta_c >= 0.6 x the period's Hc at the judge's 'max' instant (as e51 amendment_1 for tbest: a decayed / collapsed crest
               must not stand for the period; the 1.0 m DFG smoke's dispersing group otherwise picked a 0.98 m crest 3 s after a 3.6 m
               focus); if no frame passes, the smallest score3 overall is kept and flagged below_crest_floor.
               Check 2026-10-17 【測定】: on DM1A this rule finds the frozen best_frames.json frames and score3 of all four judged
               breakers exactly (1211 / 1512 / 1795 / 2083; 0.414 / 0.721 / 0.576 / 1.0). (Every 2nd frame missed 1512: not used.)
  ruler        reported at each best instant: score3 + parts, chord, foot, hood, hollow (hood_wall_x_rel; print 0.048, no band),
               lip (lip_thick_mid), gap, back 0.7-0.9 eta_c, width07, eta_c, x_c; the print's cn values and bands beside them.
  convergence  the judge's frozen numbers at its own instants (median core miss, Hc, W50/W80/W95, K, S2, N1, Nt) AND e51 hf_metrics +
               score_vs_target at the print-like instant (rows y > interior NaN: FLIP50/51 95 m, FLIP52 65 m; xwin x_c - 60 .. x_c + 35 m,
               the e51 D window around the section crest).
  verdict      print match 'ok' iff (a) the MEDIAN over the run's periods of the best-instant score3 <= DM1A's median best score3 (0.6485
               【測定】, its four judged breakers 0.414 / 0.721 / 0.576 / 1.0) + 0.30 = 0.9485, and (b) the median best-instant lip
               (lip_thick_mid) >= 0.20; otherwise 'worse than DM1A'. Reasons: 0.30 is about DM1A's own breaker-to-breaker scatter
               (IQR 0.255, max - median 0.35), so a run inside it cannot be told from DM1A by this ruler; lip 0.20 = 0.57 x the print's
               lip 0.35 (band 0.318-0.389), DM1A 0.335-0.346: it asks that a plunging lip exists, not that it matches 【選び】.
               The still at the rendered instant is shown so the USER judges the look (the numbers do not replace that).
               convergence line: the judge's median core miss vs DM1A (e51 'max' 4.86, 'best' 6.47 【測定】) and the run's own judge verdict.
               FLIP52 (AM-DFG2): progress = the frozen DFG-2 decision says NEW_BEST_SHAPE or TARGET_BAND AND print match ok.
  print view   option-D composition (cameras_DM1A.json, DM1A k2: camera 5.12 m shoreward of the crest, 75 m to the side, eye 0.576 Hc,
               look 0.52 m shoreward at 0.793 Hc, vertical FOV 23.5 deg) scaled by s = Hc / 7.16 m (Hc = e51 crest height of THIS run at the
               print-like instant; 7.16 m = DM1A k2's) so the crest fills the frame as in option D 【選び】. If hf at the camera (+-2 m,
               every frame of the clip) comes within 0.8 m of the eye, the eye is raised to clear it (reported). A sightline check at the
               print record reports any crest that hides part of the main crest (report only: in a crossing sea it is the physics).
  front view   from the shore side on the axis, looking back along -x at the crest: eye at Hc above still water, 6.3 Hc shoreward, look at
               (x_c, 0.5 Hc), vertical FOV 30 deg (+-3 Hc fit a 16:9 frame); the e51 / x51 'front' convention (the screenshot is near-frontal
               with the eye about at the summit) 【選び】. Static camera (heave 0).
  Unity        f3d50_export.main_long (unchanged) writes a GW45LIST1 clip of the run's surf records t_print - 2.5 .. + 1.5 s (record rate of
               the run: 8/s for every-3rd-frame records, 24/s for every-frame re-records); pv53 then sets the print_* fields to its own
               print-like record (nearest record, ties earlier), the cam_* poses above, heave 0, water_double_sided (display only, the
               DM1Ar seatA_ds precedent). FLIP3DBatch.BuildSceneAndCapture -f3dcap cprint,cseat (unchanged C#) through
               flip3d/f3d_unity.ps1 (unity.lock: one Unity at a time). Stills = the frame showing the print record; mp4 = 24 fps.
               No surf record within 0.25 s of the print-like instant -> no Unity view (the report says so; the 1.0 m DFG smoke has none).
               Targets: the run's most print-like instant, and also the print-like instant of the judge's most CONVERGED period
               (red_instant) when that is another period, so the print view of the wave that the convergence numbers praise is seen too.
               Side effect (as every FLIP3D capture): BuildSceneAndCapture re-saves Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity
               and the FLIP3D materials (new object ids, _GWCull); nothing is committed.
  outputs      Unity/Build/FLIP53/pv53/<run_id>/pv53_<run_id>.png (one report: (1) print view | the print | DM1A k4 reference |
               converged-period print view | front view; (2) section + print outline + ruler table; (3) convergence table; verdict lines),
               pv53_<run_id>.json (all numbers, per-frame score3 series), <run_id>_<target>_{printview,front}_f<record>.jpg and .mp4
               (24 fps real time) and <run_id>_<target>_print_front_half_speed.mp4 (side by side, 0.5x).
usage:
  py -3.10 -B pv53.py run <run_dir> [--no-unity] [--size 1280x720] [--lockwait 120] [--reuse-cap <capture dir>]
                                [--judge <judge json>] [--out <dir>]   (tests: another judge file / output folder)
  py -3.10 -B pv53.py scan <run_dir>          (periods + print-like instants + ruler, json to stdout; writes nothing)
  py -3.10 -B pv53.py ref                     (the DM1A reference numbers, json to stdout)
"""
import os, sys, json, math, time, glob, subprocess, hashlib, csv, shutil, io, contextlib

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
for _p in (TOOLS + "/flip50", TOOLS + "/flip51"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                       # noqa: E402
from scipy import ndimage as ndi         # noqa: E402
import g50_ana as GA50                   # noqa: E402  redirect_gc49 + Ctx50 (read only; nothing is written by importing it)
PA = GA50.PA
A46 = PA.A46
import g47_video as GV                   # noqa: E402  score3, print_ref, print_phys (read only)
import e51_metrics as EM                 # noqa: E402  frozen convergence ruler (read only)
from PIL import Image, ImageDraw, ImageFont   # noqa: E402

TOOL = "Tools/GWWaveGen/flip53/pv53.py"
FPS = 24.0
B50 = REPO + "/Unity/Build/FLIP50"
B51 = REPO + "/Unity/Build/FLIP51"
B52 = REPO + "/Unity/Build/FLIP52"
B53 = REPO + "/Unity/Build/FLIP53"
OUT3D = REPO + "/Unity/Build/FLIP3D"
DM1A = B50 + "/runs/DM1A_D19B_T12_th80_dp0p5"
CAMS_D = B50 + "/_scratch/cameras/cameras_DM1A.json"
PRINT_IMG = REPO + "/Docs/References/Met_JP1847.jpg"
DM1A_PRINT_STILL = OUT3D + "/capture_DM1Ar_k4_r24_seatA_ds/print"     # DM1A k4 (score3 0.576) in the option-D print view, sim frame 1795
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
FONT = "C:/Windows/Fonts/meiryo.ttc"

SCAN = dict(back_s=1.5, fwd_s=3.0, coarse=1, refine=2, fwd_step=(-1.0, 2.5), back_step=(-2.5, 1.0), crest_floor=0.6)
REF = dict(score3_median=0.6485, score3=[0.414, 0.721, 0.576, 1.0], tol=0.30, lip_min=0.20,
           e51_max_miss=4.8555, e51_best_miss=6.4673, note="DM1A pana/best_frames.json (frozen g49 rule) and FLIP51/target/baseline.json")
YMAX = {"FLIP50": 95.0, "FLIP51": 95.0, "FLIP52": 65.0}
CONV_KEYS = ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "miss", "x_pk", "y_pk")
PV = dict(dx_m=5.12, lateral_m=75.0, h_over_crest=0.576, look_dx_m=0.52, look_h=0.793, fov_v=23.5, Hc_ref=7.16)
FV = dict(dist_Hc=6.3, eye_Hc=1.0, look_h=0.5, fov_v=30.0, min_dist=25.0)
CLEAR_M = 0.8
CLIP_S = (-2.5, 1.5)


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def jdump(o, p):
    json.dump(clean(o), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def t_of(f):
    return (int(f) - 1) / FPS


def med(v):
    v = [x for x in v if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)]
    return float(np.median(v)) if v else None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


# ====================================================================== the run
class PVRun:
    def __init__(self, rd, judge=None):
        self.judge_override = judge
        self.rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
        self.id = os.path.basename(self.rd)
        self.cfg = jload(self.rd + "/cfg.json") or {}
        s = self.rd + "/"
        self.fam = "FLIP52" if ("/FLIP52/" in s or str((self.cfg.get("dir") or {}).get("set") or "").startswith("DFG")) else (
            "FLIP51" if "/FLIP51/" in s else "FLIP50")
        self.ymax = YMAX[self.fam]
        with contextlib.redirect_stdout(io.StringIO()):
            self.cx = PA.Ctx49(self.rd, {})          # Ctx50 (the D tools' context: bed, still offset, r2 / hf readers, Lc)
        self.eta0 = float(self.cx.off)
        self.eta0_src = str(self.cx.off_src)
        self.r2set = set(int(f) for f in self.cx.R2.frames)
        self.hfset = set(int(f) for f in self.cx.R1.frames)
        self.judge = None
        self.periods, self.summary = self.load_periods()

    def _rows_from(self, J, fam, path):
        """periods / groups of a FLIP51 judge (periods), a FLIP52 judge (groups) or a FLIP52 smoke (smoke_groups)."""
        self.judge = J
        rows = []
        gx = lambda g: float(g["x_pk"] if g.get("x_pk") is not None else ((g.get("scan") or {}).get("x") or g.get("x")))
        if fam == "FLIP51":
            for p in J.get("periods") or []:
                if p.get("f") is None or p.get("complete") is False:
                    continue
                rows.append(dict(n=int(p["n"]), f_max=int(p["f"]), x_max=gx(p), y_max=float(p.get("y_pk") or 0.0),
                                 conv={k: p.get(k) for k in CONV_KEYS}, window=p.get("window")))
            j5 = J.get("judgement_05") if isinstance(J.get("judgement_05"), dict) else {}
            summ = dict(source=rel(path), valid=J.get("valid"), failed=J.get("failed_gates"), outcomes=j5.get("outcomes"),
                        median={k: (J.get("median") or {}).get(k) for k in CONV_KEYS}, core_miss_median=J.get("core_miss_median"),
                        red_instant=J.get("red_instant"))
        elif "groups" in J:
            for g in J.get("groups") or []:
                if not g.get("complete") or g.get("f") is None:
                    continue
                rows.append(dict(n=int(g["n"]), f_max=int(g["f"]), x_max=gx(g), y_max=float(g.get("y_pk") or 0.0),
                                 conv={k: g.get(k) for k in CONV_KEYS}, window=g.get("window")))
            d = J.get("decision") or {}
            summ = dict(source=rel(path), valid=J.get("valid"), failed=J.get("failed_gates"), outcomes=d.get("outcomes"), bar=d.get("bar"),
                        next=d.get("next"), follow_up=d.get("follow_up"), median={k: (J.get("median") or {}).get(k) for k in CONV_KEYS},
                        core_miss_median=J.get("core_miss_median"), red_instant=J.get("red_instant"), eligibility=J.get("eligibility"))
        else:
            for g in (J.get("smoke_groups") or {}).get("rows") or []:
                if g.get("t") is None:
                    continue
                f = int(round(float(g["t"]) * FPS)) + 1
                rows.append(dict(n=int(g["n"]), f_max=f, x_max=float(g["x"]), y_max=float(g.get("y") or 0.0),
                                 conv=dict(Hc=g.get("Hc"), x_pk=g.get("x"), y_pk=g.get("y")), window=None))
            summ = dict(source=rel(path), valid=J.get("smoke_pass"), failed=J.get("failed"), outcomes=[J.get("verdict")], median={},
                        note="smoke (1.0 m): a pipeline check, never shape-judged (plan smoke_1p0.role)")
        if not rows:
            raise SystemExit("no complete period / group in the judge %s" % path)
        return rows, summ

    # ---------------------------------------------------------------- periods from the run's own judge
    def load_periods(self):
        rows, summ = [], dict(source=None)
        if self.judge_override:                       # tests / re-runs: the judge file given on the command line (format from its keys)
            J = jload(self.judge_override) or {}
            fam = "FLIP52" if ("groups" in J or "smoke_groups" in J) else "FLIP51"
            return self._rows_from(J, fam, self.judge_override)
        if self.fam == "FLIP51":
            js = sorted(glob.glob(self.rd + "/e51/judge_*.json")) or sorted(glob.glob(self.rd + "/e51/screen_*.json"))
            if not js:
                raise SystemExit("no e51/judge_*.json or screen_*.json in %s (the run is not judged yet)" % self.rd)
            return self._rows_from(jload(js[-1]) or {}, "FLIP51", js[-1])
        elif self.fam == "FLIP52":
            p = self.rd + "/g52/judge_DFG.json"
            if not os.path.exists(p):
                p = self.rd + "/g52/smoke_DFG.json"
            if not os.path.exists(p):
                raise SystemExit("no g52/judge_DFG.json or smoke_DFG.json in %s (the run is not judged yet)" % self.rd)
            return self._rows_from(jload(p) or {}, "FLIP52", p)
        else:
            base = jload(B51 + "/target/baseline.json") or {}
            short = self.id.split("_")[0]
            br = ((base.get("runs") or {}).get(short) or {}).get("per_breaker") or []
            for b in br:
                m = b.get("max") or {}
                if m.get("frame") is None:
                    continue
                rows.append(dict(n=int(b["k"]), f_max=int(m["frame"]), x_max=float(m.get("x_pk") or b.get("on_x")), y_max=float(m.get("y_pk") or 0.0),
                                 conv=dict(Hc=m.get("Hc"), W50=m.get("W50"), W80=m.get("W80"), W95=m.get("W95"), K=m.get("K"), S2=m.get("S2"),
                                           miss=m.get("target_miss"), x_pk=m.get("x_pk"), y_pk=m.get("y_pk")), window=None))
            if rows:
                tm = [r for r in (base.get("table_median_judged") or []) if r.get("run") == short and r.get("instant") == "max"]
                summ = dict(source="Unity/Build/FLIP51/target/baseline.json (e51 'max' instants)", valid=True, failed=[], outcomes=None,
                            median={k: (tm[0] if tm else {}).get("target_miss" if k == "miss" else k) for k in CONV_KEYS}, core_miss_median=(tm[0] if tm else {}).get("target_miss"))
            else:
                bf = jload(self.rd + "/pana/best_frames.json") or {}
                for b in bf.get("per_breaker") or []:
                    w0, w1 = b["window_frames"]
                    rows.append(dict(n=int(b["k"]), f_max=int(w0), x_max=float(b.get("x_c") or b.get("xc")), y_max=0.0, conv={}, window=None))
                summ = dict(source=rel(self.rd + "/pana/best_frames.json"), valid=None, failed=None, outcomes=None, median={})
        if not rows:
            raise SystemExit("no complete period / group / breaker in the judge of %s" % self.rd)
        return rows, summ

    # ---------------------------------------------------------------- centre hf row and the crest track
    def centre_row(self, f):
        e, m, t = self.cx.R1.get(f)
        xs = float(m["x0"]) + float(m["dx"]) * np.arange(int(m["res"][0]))
        row = np.asarray(e[0], float) - self.eta0
        row = ndi.median_filter(np.where(np.isfinite(row), row, -99.0), size=3, mode="nearest")
        return xs, row

    def track(self, f0, x0, f_lo, f_hi):
        out = {}
        for direction, rng, step in ((1, range(f0, f_hi + 1), SCAN["fwd_step"]), (-1, range(f0, f_lo - 1, -1), SCAN["back_step"])):
            xg = x0
            for i, f in enumerate(rng):
                if f not in self.hfset:
                    break
                xs, row = self.centre_row(f)
                lo, hi = (-3.0, 3.0) if i == 0 else step
                sel = np.where((xs >= xg + lo) & (xs <= xg + hi))[0]
                if not len(sel):
                    break
                xg = float(xs[sel[int(np.argmax(row[sel]))]])
                out[f] = xg
        return out

    # ---------------------------------------------------------------- the D ruler on the centre section
    def measure(self, f, xg, keep_mask=False):
        try:
            M, X, Z, t = A46.r2_mask(self.cx, f, xg)
            mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=self.cx.Lc))
            row = A46.DS.pick(mm)
            s3, parts = GV.score3(row)
        except Exception as ex:
            return dict(frame=int(f), t=t_of(f), xg=xg, error=repr(ex)[:200])
        g = lambda k: (float(row[k]) if isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool) and math.isfinite(float(row[k])) else None)
        r = dict(frame=int(f), t=float(t), xg=float(xg), score3=s3, parts={k: v for k, v in (parts or {}).items()},
                 chord=g("face_chord_deg_01_05"), foot=g("front_x01_rel"), hood=g("hood_area"), hollow=g("hood_wall_x_rel"),
                 lip=g("lip_thick_mid"), gap=g("gap_max"), back=g("back_angle_07_09_deg"), w07=g("width07_silhouette"),
                 eta_c=g("eta_c"), x_c=g("x_c"), hood_height_m=(float(mm["hood_height_m"]) if mm.get("hood_height_m") is not None else None),
                 chord_miss=(parts or {}).get("face_chord_deg_01_05"))
        if keep_mask:
            r["_mask"] = (M, X, Z)
        return r

    def scan_period(self, p, log=print):
        f0 = p["f_max"]
        f_lo = f0 - int(round(SCAN["back_s"] * FPS)); f_hi = f0 + int(round(SCAN["fwd_s"] * FPS))
        trk = self.track(f0, p["x_max"], f_lo, f_hi)
        frames = [f for f in range(f_lo, f_hi + 1) if f in self.r2set and f in trk]
        rows = {}
        for f in frames[::SCAN["coarse"]]:
            rows[f] = self.measure(f, trk[f])
        key = lambda r: (r["score3"], r.get("chord_miss") or 0.0, -(r.get("hood_height_m") or 0.0), r["frame"])
        ok = [r for r in rows.values() if r.get("score3") is not None]
        if ok:
            b = min(ok, key=key)
            for f in range(b["frame"] - SCAN["refine"], b["frame"] + SCAN["refine"] + 1):
                if f in trk and f in self.r2set and f not in rows:
                    rows[f] = self.measure(f, trk[f])
            ok = [r for r in rows.values() if r.get("score3") is not None]
        # crest floor (2026-10-17, AM-DFG2a): only frames whose section crest eta_c >= 0.6 x the period's Hc at the judge's 'max' instant
        # (else the largest eta_c measured in the window) are candidates; a decayed crest of the dispersing group must not stand for it
        hc_ref = (p.get("conv") or {}).get("Hc")
        if not isinstance(hc_ref, (int, float)) or not hc_ref:
            hc_ref = max([r.get("eta_c") or 0.0 for r in ok] or [0.0])
        floor = SCAN["crest_floor"] * float(hc_ref)
        elig = [r for r in ok if (r.get("eta_c") or 0.0) >= floor - 1e-9]
        best = min(elig, key=key) if elig else (min(ok, key=key) if ok else None)
        if best is not None:
            best["below_crest_floor"] = not bool(elig)
        log("  period %s: f_max %d (t %.2f, x %.1f), %d frames measured, best %s" % (
            p["n"], f0, t_of(f0), p["x_max"], len(rows), ("f %d t %.3f score3 %.3f lip %s" % (best["frame"], best["t"], best["score3"], _g(best.get("lip"))) if best else "none")))
        return dict(n=p["n"], f_max=f0, t_max=t_of(f0), x_max=p["x_max"], window_frames=[f_lo, f_hi], n_measured=len(rows),
                    crest_floor_m=floor, crest_floor_ref_Hc=hc_ref, n_eligible=len(elig),
                    n_errors=sum(1 for r in rows.values() if "error" in r), best=best,
                    series=[dict((k, r.get(k)) for k in ("frame", "t", "score3", "lip", "chord", "foot", "hood", "eta_c", "x_c", "error")) for r in sorted(rows.values(), key=lambda r: r["frame"])],
                    conv_judge=p.get("conv") or {})

    # ---------------------------------------------------------------- e51 at the print-like instant
    def conv_at(self, f, x_c):
        a, meta = EM.load_frame(self.rd, "hf", f, "eta")
        if a is None:
            return dict(error="no hf frame %d" % f)
        yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(a.shape[0])
        b = a.copy()
        b[yh > self.ymax + 1e-9, :] = np.nan
        xwin = (x_c - 60.0, x_c + 35.0)
        m = EM.hf_metrics(b, meta, self.eta0, xwin=xwin)
        if not m or "W50" not in m:
            return dict(error="no crest metrics", xwin=list(xwin))
        miss, per = EM.score_vs_target(m)
        o = {k: m.get(k) for k in ("Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "K", "S1", "S2", "taper", "ring_max", "Lx50", "A50")}
        o.update(miss=miss, miss_per=per, xwin=list(xwin), ymax=self.ymax, frame=int(f), t=t_of(f))
        return o


def _g(v, f="%.2f"):
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else (f % v)


# ====================================================================== reference and verdict
def reference():
    bf = jload(DM1A + "/pana/best_frames.json") or {}
    s3 = [b.get("score3") for b in bf.get("per_breaker") or []]
    lips = [((b.get("ruler") or {}).get("lip")) for b in bf.get("per_breaker") or []]
    live = med(s3)
    base = jload(B51 + "/target/baseline.json") or {}
    tm = {r["instant"]: r for r in (base.get("table_median_judged") or []) if r.get("run") == "DM1A"}
    return dict(run="DM1A_D19B_T12_th80_dp0p5", score3_per_breaker=s3, score3_median_live=live, score3_median_frozen=REF["score3_median"],
                same=bool(live is not None and abs(live - REF["score3_median"]) < 1e-6), lip_per_breaker=lips, lip_median=med(lips),
                tol=REF["tol"], lip_min=REF["lip_min"], bar_score3=REF["score3_median"] + REF["tol"],
                e51_max=dict((k, (tm.get("max") or {}).get(k)) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "target_miss")),
                e51_best=dict((k, (tm.get("best") or {}).get(k)) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "target_miss")),
                print_cn=dict((k, GV.print_ref()["cnv"].get(k)) for k in ("face_chord_deg_01_05", "front_x01_rel", "hood_area", "hood_wall_x_rel",
                                                                          "lip_thick_mid", "gap_max", "back_angle_07_09_deg", "width07_silhouette")),
                bands=dict((k, v.get("band")) for k, v in (GV.print_ref()["bands"] or {}).items()), extra=GV.print_ref()["extra"],
                source="DM1A pana/best_frames.json (frozen g49 rule) + FLIP51/target/baseline.json table_median_judged")


def verdict(R, per, ref):
    bests = [p["best"] for p in per if p.get("best")]
    s3m = med([b["score3"] for b in bests])
    lipm = med([b.get("lip") or 0.0 for b in bests])
    bar = ref["bar_score3"]
    ok_a = bool(s3m is not None and s3m <= bar + 1e-9)
    ok_b = bool(lipm is not None and lipm >= ref["lip_min"] - 1e-9)
    pm = "ok" if (ok_a and ok_b) else "worse than DM1A"
    why = "median best score3 %s %s %.4f (DM1A median %.4f + %.2f); median best lip %s %s %.2f" % (
        _g(s3m, "%.3f"), "<=" if ok_a else ">", bar, ref["score3_median_frozen"], ref["tol"], _g(lipm, "%.3f"), ">=" if ok_b else "<", ref["lip_min"])
    S = R.summary
    cm = S.get("core_miss_median")
    if cm is None:
        cm = (S.get("median") or {}).get("miss")
    conv = "median core miss %s (%s; DM1A e51 'max' %.2f / 'best' %.2f); judge: valid %s%s%s" % (
        _g(cm), (S.get("source") or "-").split("/")[-1], REF["e51_max_miss"], REF["e51_best_miss"], S.get("valid"),
        (" failed %s" % S.get("failed")) if S.get("failed") else "", (" outcomes %s" % S.get("outcomes")) if S.get("outcomes") else "")
    o = dict(print_match=pm, print_match_line="print match: %s (%s)" % (pm, why), median_best_score3=s3m, median_best_lip=lipm,
             cond_a_score3=ok_a, cond_b_lip=ok_b, convergence_line="convergence: " + conv, core_miss_median=cm)
    if R.fam == "FLIP52" and (R.summary.get("source") or "").endswith("judge_DFG.json"):
        outs = S.get("outcomes") or []
        conv_ok = bool(any(x in ("NEW_BEST_SHAPE", "TARGET_BAND") for x in outs))
        o["progress_AM_DFG2"] = bool(conv_ok and pm == "ok")
        o["progress_line"] = "progress (AM-DFG2): %s (convergence %s by the frozen decision %s; print match %s)" % (
            "YES" if o["progress_AM_DFG2"] else "NO", "improves" if conv_ok else "does not improve", outs, pm)
    return o


# ====================================================================== cameras
def option_d():
    c = jload(CAMS_D) or {}
    cr = (c.get("print") or {}).get("crest_relative") or {}
    pu = (c.get("print") or {}).get("unity") or {}
    still = float(c.get("still_offset_m") or 0.076)
    try:
        hc = (float(pu["printPos"][1]) - still) / float(cr["h_over_crest"])
        xc = float(pu["printPos"][0]) - float(cr["dx_m"])
        d = dict(dx_m=float(cr["dx_m"]), lateral_m=float(cr["lateral_m"]), h_over_crest=float(cr["h_over_crest"]),
                 look_dx_m=float(pu["printLookAt"][0]) - xc, look_h=(float(pu["printLookAt"][1]) - still) / hc, fov_v=float(pu["printFovV"]),
                 Hc_ref=hc, source=rel(CAMS_D), source_sha256=sha(CAMS_D))
    except Exception as ex:
        d = dict(PV, source="constants (camera file unreadable: %s)" % repr(ex)[:80])
    return d


def hf_max_near(R, frames, x, y_abs, half=2.0):
    """max over the frames of (hf - eta0) within +-half m of (x, |y|); None if outside the record."""
    best = None
    for f in frames:
        a, meta = EM.load_frame(R.rd, "hf", f, "eta")
        if a is None:
            continue
        xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(a.shape[1])
        ys = float(meta["z0"]) + float(meta["dz"]) * np.arange(a.shape[0])
        sx = (xs >= x - half) & (xs <= x + half); sy = (ys >= y_abs - half) & (ys <= y_abs + half)
        if not sx.any() or not sy.any():
            return None
        v = a[np.ix_(sy, sx)]
        v = v[np.isfinite(v)]
        if len(v):
            h = float(v.max()) - R.eta0
            best = h if best is None else max(best, h)
    return best


def sightline(R, f, cam, look, x_c, n=240):
    """report only: along camera -> look (Unity x, y, z), the largest water height above the line before reaching 10 m of the crest."""
    a, meta = EM.load_frame(R.rd, "hf", f, "eta")
    if a is None:
        return None
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(a.shape[1])
    ys = float(meta["z0"]) + float(meta["dz"]) * np.arange(a.shape[0])
    worst = (-1e9, None)
    blocked = 0; total = 0
    for u in np.linspace(0.02, 1.0, n):
        p = np.array(cam) + u * (np.array(look) - np.array(cam))
        if math.hypot(p[0] - x_c, p[2]) < 10.0:
            break
        ix = int(np.clip(round((p[0] - xs[0]) / float(meta["dx"])), 0, len(xs) - 1))
        iy = int(np.clip(round((abs(p[2]) - ys[0]) / float(meta["dz"])), 0, len(ys) - 1))
        if abs(abs(p[2]) - ys[iy]) > 1.0 or abs(p[0] - xs[ix]) > 1.0:
            continue
        h = a[iy, ix]
        if not np.isfinite(h):
            continue
        total += 1
        ex = float(h) - p[1]
        if ex > 0:
            blocked += 1
        if ex > worst[0]:
            worst = (ex, [float(p[0]), float(p[1]), float(p[2])])
    return dict(samples=total, blocked_samples=blocked, max_water_above_line_m=worst[0] if worst[1] else None, at=worst[1],
                note="report only: water between the camera and the main crest (in a crossing sea, crests in front of the main wave are physics)")


def cameras(R, best, conv, frames_clip):
    od = option_d()
    Hc = conv.get("Hc") if isinstance(conv.get("Hc"), (int, float)) else None
    Hc = float(Hc if Hc else best["eta_c"])
    x_c = float(best["x_c"])
    s = Hc / od["Hc_ref"]
    e0 = R.eta0
    pp = [x_c + od["dx_m"] * s, e0 + od["h_over_crest"] * Hc, -od["lateral_m"] * s]
    pl = [x_c + od["look_dx_m"] * s, e0 + od["look_h"] * Hc, 0.0]
    notes = []
    h = hf_max_near(R, frames_clip, pp[0], abs(pp[2]))
    if h is not None and pp[1] - e0 < h + CLEAR_M:
        notes.append("print eye raised %.2f m (water within %.1f m of the eye at the camera)" % (h + CLEAR_M - (pp[1] - e0), CLEAR_M))
        pp[1] = e0 + h + CLEAR_M
    D = max(FV["min_dist"], FV["dist_Hc"] * Hc)
    fp = [x_c + D, e0 + FV["eye_Hc"] * Hc, 0.0]
    fl = [x_c, e0 + FV["look_h"] * Hc, 0.0]
    h2 = hf_max_near(R, frames_clip, fp[0], 0.5)
    if h2 is not None and fp[1] - e0 < h2 + CLEAR_M:
        notes.append("front eye raised %.2f m" % (h2 + CLEAR_M - (fp[1] - e0)))
        fp[1] = e0 + h2 + CLEAR_M
    try:
        bz = float(R.cx.bed_z(np.array([fp[0]]), 0.0)[0])
        if fp[1] < bz + 1.0:
            notes.append("front camera above the bed: raised to bed + 1 m")
            fp[1] = bz + 1.0
    except Exception:
        pass
    return dict(option_d=od, scale=s, Hc_used=Hc, x_c=x_c, print_pos=pp, print_look=pl, print_fov_v=od["fov_v"],
                front_pos=fp, front_look=fl, front_fov_v=FV["fov_v"], front_rule=dict(FV), clearance_m=CLEAR_M,
                hf_near_print_cam=h, hf_near_front_cam=h2, notes=notes)


# ====================================================================== Unity
def nearest_record(surf, f):
    rs = np.array(sorted(surf))
    if not len(rs):
        return None
    i = int(np.argmin(np.abs(rs - f) * 2 + (rs > f)))
    return int(rs[i])


def make_clip(R, best, conv, log=print):
    sys.path.insert(0, TOOLS + "/flip50g2")
    import f3d50_export as FX                  # unchanged (its own imports: f3d_common, g50_common read only)
    run = FX.Run(R.rd)
    surf = sorted(run.surf)
    fb = int(best["frame"])
    pr = nearest_record(surf, fb)
    if pr is None or abs(pr - fb) > 6:
        return None, dict(ok=False, why="no surface record within 0.25 s of the print-like frame %d (records %s .. %s, n %d)" % (
            fb, surf[0] if surf else None, surf[-1] if surf else None, len(surf)))
    fs, ts = t_of(pr) + CLIP_S[0], t_of(pr) + CLIP_S[1]
    rec = [f for f in surf if int(round(fs * FPS)) + 1 <= f <= int(round(ts * FPS)) + 1]
    d = np.diff(rec) if len(rec) > 1 else np.array([])
    if len(rec) < 2 or not np.all(d == d[0]):           # shrink to the evenly spaced run of records around pr
        step = int(np.median(np.diff(surf))) if len(surf) > 1 else 3
        rec = [pr]
        while rec[0] - step in surf and rec[0] - step >= int(round(fs * FPS)) + 1:
            rec.insert(0, rec[0] - step)
        while rec[-1] + step in surf and rec[-1] + step <= int(round(ts * FPS)) + 1:
            rec.append(rec[-1] + step)
        if len(rec) < 2:
            return None, dict(ok=False, why="fewer than 2 evenly spaced surface records around frame %d" % pr)
    frames_clip = list(range(rec[0], rec[-1] + 1))
    cam = cameras(R, best, conv, [f for f in frames_clip if f in R.hfset][::3])
    name = "pv53_%s_f%d" % (R.id, pr)
    out = OUT3D + "/" + name
    seat_eye_guess = cam["front_pos"][1] - R.eta0
    args = ["--run", R.rd, "--from-s", "%.6f" % (t_of(rec[0]) - 1e-4), "--to-s", "%.6f" % (t_of(rec[-1]) + 1e-4),
            "--seat", "%.3f,%.3f" % (cam["front_pos"][0], 0.0), "--eye", "%.3f" % seat_eye_guess, "--name", name]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        FX.main_long(args)
    mp = out + "/manifest.json"
    man = jload(mp)
    if not man:
        return None, dict(ok=False, why="f3d50_export.main_long wrote no manifest", stdout=buf.getvalue()[-800:])
    sf = man["source_frames"]
    if pr not in sf:
        return None, dict(ok=False, why="print record %d not in the clip %s..%s" % (pr, sf[0], sf[-1]))
    still = float(man["still_offset_m"])
    man.update(print_record_frame=pr, print_record_t=t_of(pr), print_record_index=sf.index(pr), print_bestframes_frame=fb,
               print_bestframes_t=t_of(fb), print_score3=float(best["score3"]), print_crest_x=float(best["x_c"]),
               print_crest_eta=float(R.eta0 + (cam["Hc_used"])), breaker_k=int(best.get("_n") or 0),
               breakers=[dict(k=int(best.get("_n") or 0), frame=pr, t=t_of(pr), score3=float(best["score3"]), win_first=sf[0], win_last=sf[-1],
                              hood=float(best.get("hood") or 0.0), lip=float(best.get("lip") or 0.0), frame_bestframes=fb, t_bestframes=t_of(fb),
                              record_offset_frames=pr - fb, xc_bestframes=float(best["x_c"]), eta_c_bestframes=float(best.get("eta_c") or 0.0))],
               breakers_source="pv53 print-like instant (score3 minimum on r2, %s)" % TOOL,
               heave=[0.0] * len(man.get("heave") or [0.0, 0.0]), heave_min_m=0.0, heave_max_m=0.0,
               heave_note="pv53: the front view is a static camera (heave 0); the seat fields hold the FRONT view, not a boat seat",
               seat_x=float(cam["front_pos"][0]), seat_z=0.0, seat_eye_m=float(cam["front_pos"][1] - still),
               cam_seat_look_at=[float(v) for v in cam["front_look"]], cam_seat_fov_v=float(cam["front_fov_v"]),
               cam_print_pos=[float(v) for v in cam["print_pos"]], cam_print_look_at=[float(v) for v in cam["print_look"]],
               cam_print_fov_v=float(cam["print_fov_v"]),
               cam_source_file=cam["option_d"].get("source"), cam_source_run="DM1A_D19B_T12_th80_dp0p5 (option-D print pose, scaled)",
               cam_note_ja=("pv53：原画の視点＝option D の構図（cameras_DM1A.json の k2 に対する位置）を、この計算の原画に最も近い瞬間の頂（x %.1f m、Hc %.2f m）"
                            "に合わせ Hc / %.2f m で縮めた物【選び】。座席の欄は正面（岸の側から −x を見る、目は頂の高さ）" % (cam["x_c"], cam["Hc_used"], cam["option_d"]["Hc_ref"])),
               water_double_sided=True, water_double_sided_ja="表示だけ：水を両面で描く（DM1Ar seatA_ds と同じ。記録・形は変えない）",
               pv53=dict(tool=TOOL, run=R.rd, print_like_frame=fb, print_record=pr, cameras=cam, date=time.strftime("%Y-%m-%d %H:%M:%S")))
    jdump(man, mp)
    return out, dict(ok=True, clip=out, print_record=pr, print_like_frame=fb, record_offset_frames=pr - fb, records=len(sf),
                     record_fps=man.get("record_fps"), frames=[sf[0], sf[-1]], cameras=cam)


def run_unity(clip, cap, size, lockwait, log=print):
    log_name = "pv53_" + os.path.basename(clip)
    extra = "-f3dcap cprint,cseat -f3ddata %s -f3dout %s -f3dsize %s -f3dfps 24 -f3dtiles 0" % (clip, cap, size)
    ps = "& '%s' -Method 'GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture' -Log '%s' -Extra '%s' -LockWaitMinutes %d -TimeoutMinutes 30" % (
        UNITY_PS1, log_name, extra, int(lockwait))
    t0 = time.time()
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    log("  unity rc %s %.0f s | %s" % (p.returncode, time.time() - t0, out.strip().splitlines()[-1][:300] if out.strip() else ""))
    return dict(rc=p.returncode, seconds=round(time.time() - t0, 1), tail=out[-1500:], log=OUT3D + "/logs/unity_" + log_name + ".log")


def ffmpeg():
    return GV.FF


def pick_frame(capview, record_frame):
    p = capview + "/frames.csv"
    if not os.path.exists(p):
        return None, None
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    hit = [r for r in rows if int(r["sim_frame"]) == int(record_frame)]
    if not hit:
        return None, rows
    i = int(hit[0]["i"])
    return capview + "/frame_%05d.jpg" % i, rows


def make_videos(cap, od, rid, pr, log=print):
    res = {}
    ff = ffmpeg()
    for view in ("cprint", "cseat"):
        d = cap + "/" + view
        still, rows = pick_frame(d, pr)
        if still and os.path.exists(still):
            dst = od + "/%s_%s_f%d.jpg" % (rid, "printview" if view == "cprint" else "front", pr)
            shutil.copyfile(still, dst)
            res[view + "_still"] = dst
        if rows:
            mp = od + "/%s_%s.mp4" % (rid, "printview" if view == "cprint" else "front")
            p = subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "24", "-i", d + "/frame_%05d.jpg", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                "-crf", "20", mp], capture_output=True, text=True)
            res[view + "_mp4"] = mp if p.returncode == 0 else None
            res[view + "_frames"] = len(rows)
    if os.path.exists(cap + "/cprint/frames.csv") and os.path.exists(cap + "/cseat/frames.csv"):
        mp = od + "/%s_print_front_half_speed.mp4" % rid
        p = subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "12", "-i", cap + "/cprint/frame_%05d.jpg", "-framerate", "12", "-i",
                            cap + "/cseat/frame_%05d.jpg", "-filter_complex", "[0:v]scale=960:-2[a];[1:v]scale=960:-2[b];[a][b]hstack=inputs=2",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp], capture_output=True, text=True)
        res["side_by_side_half_speed_mp4"] = mp if p.returncode == 0 else None
    log("  videos: %s" % {k: (os.path.basename(v) if isinstance(v, str) else v) for k, v in res.items()})
    return res


# ====================================================================== the report image
_FC = {}


def fnt(sz, bold=False):
    k = (sz, bold)
    if k not in _FC:
        try:
            _FC[k] = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc" if bold else FONT, sz)
        except Exception:
            _FC[k] = ImageFont.load_default()
    return _FC[k]


BG = (247, 247, 244); TXT = (20, 20, 20); SUB = (90, 90, 90); RED = (200, 30, 30); GREEN = (25, 130, 55); BLUE = (30, 70, 190)
WATER = (60, 110, 160); SAND = (196, 178, 140)


def paste_fit(im, path, box, label, sub=None, mirror=False):
    dr = ImageDraw.Draw(im)
    x0, y0, w, h = box
    dr.rectangle([x0, y0, x0 + w, y0 + h], fill=(225, 225, 222), outline=(150, 150, 150))
    if path and os.path.exists(path):
        src = Image.open(path).convert("RGB")
        if mirror:
            src = src.transpose(Image.FLIP_LEFT_RIGHT)
        sc = min(w / src.width, h / src.height)
        src = src.resize((max(1, int(src.width * sc)), max(1, int(src.height * sc))), Image.LANCZOS)
        im.paste(src, (x0 + (w - src.width) // 2, y0 + (h - src.height) // 2))
    else:
        msg = str(sub or "なし")
        f_ = fnt(14)
        lines_, cur = [], ""
        for ch in msg:
            if dr.textlength(cur + ch, font=f_) > w - 24:
                lines_.append(cur); cur = ch
            else:
                cur += ch
        lines_.append(cur)
        lines_ = lines_[:max(1, (h - 20) // 18)]
        for i, ln in enumerate(lines_):
            dr.text((x0 + 12, y0 + 10 + 18 * i), ln, fill=RED, font=f_)
    dr.text((x0, y0 - 24), label, fill=TXT, font=fnt(16, True))


def draw_section(im, R, best, box, ref):
    dr = ImageDraw.Draw(im)
    x0, y0, w, h = box
    dr.rectangle([x0, y0, x0 + w, y0 + h], fill=(255, 255, 255), outline=(150, 150, 150))
    dr.text((x0, y0 - 24), "② 真ん中の断面（r2、y 0.5 m）と原画の輪郭（黒、STUDY52 cn を η_c と頂の x に合わせた）1:1", fill=TXT, font=fnt(16, True))
    if not best:
        dr.text((x0 + 20, y0 + 40), "断面の物差しが読めなかった", fill=RED, font=fnt(16)); return
    r = R.measure(best["frame"], best["xg"], keep_mask=True)
    if "_mask" not in r:
        dr.text((x0 + 20, y0 + 40), "断面が読めなかった：%s" % r.get("error"), fill=RED, font=fnt(14)); return
    M, X, Z = r["_mask"]
    xc, ec = float(best["x_c"]), float(best["eta_c"])
    XL, XR = xc - 42.0, xc + 22.0
    ZB, ZT = -9.0, max(ec + 3.5, 10.0)
    s = min((w - 70) / (XR - XL), (h - 60) / (ZT - ZB))
    px0 = x0 + 50; py0 = y0 + 12
    Wp, Hp = int((XR - XL) * s), int((ZT - ZB) * s)
    gx = XL + (np.arange(Wp) + 0.5) / s
    gz = ZT - (np.arange(Hp) + 0.5) / s
    ix = np.clip(np.round((gx - X[0]) / (X[1] - X[0])).astype(int), 0, len(X) - 1)
    iz = np.clip(np.round((gz - Z[0]) / (Z[1] - Z[0])).astype(int), 0, len(Z) - 1)
    inside = ((gx >= X[0]) & (gx <= X[-1]))[None, :] & ((gz >= Z[0]) & (gz <= Z[-1]))[:, None]
    wat = M[iz][:, ix] & inside
    rgb = np.full((Hp, Wp, 3), 255, np.uint8)
    rgb[wat] = WATER
    try:
        bz = np.asarray(R.cx.bed_z(gx, 0.0), float) - R.eta0
        bed = gz[:, None] <= bz[None, :]
        rgb[bed] = SAND
    except Exception:
        pass
    im.paste(Image.fromarray(rgb), (px0, py0))
    tr = lambda P: [(px0 + (p[0] - XL) * s, py0 + (ZT - p[1]) * s) for p in P]
    yz = py0 + (ZT - 0.0) * s
    dr.line([(px0, yz), (px0 + Wp, yz)], fill=(120, 120, 120), width=1)
    for zz in range(int(math.ceil(ZB / 5.0)) * 5, int(ZT) + 1, 5):
        yy = py0 + (ZT - zz) * s
        dr.text((px0 - 34, yy - 8), "%d" % zz, fill=SUB, font=fnt(12))
    for xx in range(int(math.ceil(XL / 10.0)) * 10, int(XR) + 1, 10):
        u = px0 + (xx - XL) * s
        dr.line([(u, py0 + Hp), (u, py0 + Hp - 6)], fill=SUB)
        dr.text((u - 12, py0 + Hp + 2), "%d" % xx, fill=SUB, font=fnt(11))
    for q in GV.print_phys(xc, ec):
        P = [p for p in np.asarray(q) if XL <= p[0] <= XR and ZB <= p[1] <= ZT]
        if len(P) > 1:
            dr.line(tr(P), fill=(0, 0, 0), width=3)
    dr.text((px0 + 6, py0 + 4), "t %.3f s（コマ %d）  頂 x %.1f m・η_c %.2f m（静かな水面から）  score3 %.3f" % (best["t"], best["frame"], xc, ec, best["score3"]),
            fill=TXT, font=fnt(14, True))


def table(dr, x0, y0, cols, rows, widths, fs=13, head_fill=(230, 230, 226)):
    y = y0
    x = x0
    dr.rectangle([x0, y, x0 + sum(widths), y + fs + 9], fill=head_fill)
    for c, wd in zip(cols, widths):
        dr.text((x + 4, y + 2), str(c), fill=TXT, font=fnt(fs, True)); x += wd
    y += fs + 10
    for r in rows:
        x = x0
        col = None
        if isinstance(r, tuple) and len(r) == 2 and isinstance(r[1], tuple):
            r, col = r
        for i, (c, wd) in enumerate(zip(r, widths)):
            fc = TXT
            if col and i < len(col) and col[i]:
                fc = col[i]
            dr.text((x + 4, y + 1), str(c), fill=fc, font=fnt(fs))
            x += wd
        y += fs + 7
    return y


def inband(v, band):
    if v is None or band is None:
        return None
    lo, hi = band
    return bool((lo is None or v >= lo - 1e-9) and (hi is None or v <= hi + 1e-9))


def compose(R, per, best_p, conv_best, ref, V, unity, od):
    W, H = 1920, 1330
    im = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(im)
    dr.text((24, 12), "原画の視点の検査（pv53）  %s  [%s]  %s" % (R.id, R.fam, time.strftime("%Y-%m-%d %H:%M")), fill=TXT, font=fnt(24, True))
    pmc = GREEN if V["print_match"] == "ok" else RED
    dr.text((24, 50), V["print_match_line"], fill=pmc, font=fnt(17, True))
    dr.text((24, 76), V["convergence_line"][:230], fill=TXT, font=fnt(15))
    if V.get("progress_line"):
        dr.text((24, 98), V["progress_line"], fill=GREEN if V.get("progress_AM_DFG2") else RED, font=fnt(16, True))
    # ---- row A: print view | the print | DM1A reference + converged period | front
    b = best_p["best"] if best_p else None
    ya = 150
    U = unity or {}
    up = U.get("print_like") or {}
    uc = U.get("converged") or {}
    why = up.get("why") or U.get("why") or "Unity の絵なし"
    cap_pv = "① 原画の視点（Unity、option D の構図を Hc で縮めた）：原画に最も近い瞬間（周期 %s）" % (best_p["n"] if best_p else "-")
    paste_fit(im, up.get("cprint_still"), (24, ya, 860, 484), cap_pv, sub=why)
    paste_fit(im, PRINT_IMG, (900, ya, 480, 323), "原画（北斎、Met JP1847）")
    dm = DM1A_PRINT_STILL + "/frame_00036.jpg"
    paste_fit(im, dm if os.path.exists(dm) else None, (900, ya + 357, 235, 132), "DM1A k4 基準 (0.576)", sub="なし")
    if uc:
        paste_fit(im, uc.get("cprint_still"), (1145, ya + 357, 235, 132), "収束最良 周期 %s" % uc.get("period"), sub=uc.get("why") or "なし")
    paste_fit(im, up.get("cseat_still"), (1400, ya, 496, 279), "正面（岸の側から、目は頂の高さ）", sub=why)
    yb = ya + 494
    if up.get("ok"):
        c = up.get("cameras") or {}
        txt = ("原画の視点：位置 (%.1f, %.1f, %.1f) → 見る点 (%.1f, %.1f, 0)、縦の画角 %.1f°、縮め s = %.2f（Hc %.2f / %.2f m）。記録のコマ %d（原画に最も近いコマ %d との差 %+d コマ、記録 %g 個/s）" % (
            *c["print_pos"], c["print_look"][0], c["print_look"][1], c["print_fov_v"], c["scale"], c["Hc_used"], c["option_d"]["Hc_ref"],
            up["print_record"], up["print_like_frame"], up["record_offset_frames"], up.get("record_fps") or 0))
        dr.text((24, yb), txt, fill=SUB, font=fnt(12))
        nt = "; ".join(c.get("notes") or [])
        sl = (up.get("sightline") or {})
        if sl.get("max_water_above_line_m") is not None and sl["max_water_above_line_m"] > 0:
            nt = (nt + "; " if nt else "") + "手前の水が視線を %.1f m 越える所あり（%d/%d 点、報告だけ）" % (sl["max_water_above_line_m"], sl["blocked_samples"], sl["samples"])
        if nt:
            dr.text((24, yb + 17), "注：" + nt, fill=RED, font=fnt(12))
        dr.text((1400, ya + 285), "正面：位置 (%.1f, %.1f, 0) → (%.1f, %.1f, 0)、縦 %.0f°" % (c["front_pos"][0], c["front_pos"][1], c["front_look"][0], c["front_look"][1], c["front_fov_v"]),
                fill=SUB, font=fnt(13))
        if uc.get("ok"):
            cc = uc.get("cameras") or {}
            dr.text((1400, ya + 305), "最も収束した周期 %s：記録 %d、頂 x %.1f m、Hc %.2f m" % (uc.get("period"), uc["print_record"], cc.get("x_c", 0), cc.get("Hc_used", 0)),
                    fill=SUB, font=fnt(13))
    # ---- row B left: the section
    draw_section(im, R, b, (24, 700, 860, 330), ref)
    # ruler table under the section
    rows = []
    bands = ref["bands"]; cn = ref["print_cn"]; ex = ref["extra"]
    spec = [("score3（弦・足・覆いの外れ）", "score3", "%.3f", "0（帯の中）", None),
            ("前の面の弦 0.1〜0.5 η_c", "chord", "%.1f°", "%.1f°（%.1f〜%.1f）" % (cn["face_chord_deg_01_05"], *bands["face_chord_deg_01_05"]), bands["face_chord_deg_01_05"]),
            ("前の足 0.1 η_c", "foot", "%.3f", "%.3f（%.2f〜%.2f）" % (cn["front_x01_rel"], *bands["front_x01_rel"]), bands["front_x01_rel"]),
            ("覆いの面積", "hood", "%.3f", "%.3f（%.3f〜%.3f）" % (cn["hood_area"], *bands["hood_area"]), bands["hood_area"]),
            ("空洞の壁 hollow", "hollow", "%.3f", "%.3f（帯なし）" % cn["hood_wall_x_rel"], None),
            ("唇の厚み lip", "lip", "%.3f", "%.3f（%.2f〜%.2f）" % (cn["lip_thick_mid"], *bands["lip_thick_mid"]), bands["lip_thick_mid"]),
            ("後ろの角 0.7〜0.9 η_c", "back", "%.1f°", "%.1f°（%.0f〜%.0f）" % (cn["back_angle_07_09_deg"], *ex["back_angle_07_09_deg"]), ex["back_angle_07_09_deg"]),
            ("0.7 η_c の幅", "w07", "%.2f", "%.2f（%.2f〜%.2f）" % (cn["width07_silhouette"], *ex["width07_silhouette"]), ex["width07_silhouette"])]
    pl = [p for p in per if p.get("best")]
    cols = ["原画の物差し（η_c で割る）"] + ["周期 %s" % p["n"] for p in pl] + ["原画 cn（帯）"]
    nper = max(1, len(pl))
    wcol = max(62, int(440 / nper))
    widths = [210] + [wcol] * len(pl) + [210]
    for lab, k, f, ptxt, band in spec:
        vals = [p["best"].get(k) for p in pl]
        colr = (None,) + tuple((GREEN if inband(v, band) else RED) if (band is not None and v is not None) else None for v in vals) + (SUB,)
        rows.append(([lab] + [_g(v, f) for v in vals] + [ptxt], colr))
    rows.append((["t（s）"] + ["%.2f" % p["best"]["t"] for p in pl] + ["DM1A score3 中央値 %.3f" % ref["score3_median_frozen"]], (None,)))
    table(dr, 24, 1040, cols, rows, widths, fs=12)
    # ---- row B right: convergence table
    xr = 910
    dr.text((xr, 676), "③ 収束の物差し（e51 凍結、目標＝利用者の画面の読み値。画面そのものは載せない）", fill=TXT, font=fnt(16, True))
    ck = [("Hc", "%.2f"), ("W50", "%.2f"), ("W80", "%.2f"), ("W95", "%.2f"), ("K", "%.2f"), ("S2", "%.2f"), ("N1", "%.2f"), ("Nt", "%.2f"), ("miss", "%.2f")]
    cols = ["周期", "瞬間"] + [k for k, _ in ck]
    widths = [56, 132] + [78] * len(ck)
    rows = []
    for p in per:
        cj = p.get("conv_judge") or {}
        rows.append([str(p["n"]), "判定 %.2f s" % p["t_max"]] + [_g(cj.get(k), f) for k, f in ck])
        cb = p.get("conv_print") or {}
        if cb and "error" not in cb:
            rows.append(["", "原画 %.2f s" % cb.get("t", 0)] + [_g(cb.get(k), f) for k, f in ck])
    S = R.summary
    mdn = S.get("median") or {}
    rows.append(["中央", "判定"] + [_g(mdn.get(k), f) for k, f in ck])
    e5m = ref["e51_max"]
    rows.append(["DM1A", "e51 max"] + [_g(e5m.get("target_miss" if k == "miss" else k), f) for k, f in ck])
    tgt = EM.TARGET
    rows.append(["目標", "範囲"] + [("%.2f〜%.2f" % (tgt[k]["lo"], tgt[k]["hi"]) if k in tgt and k in ("W50", "W80", "W95", "K", "S2") else "") for k, _ in ck])
    yy = table(dr, xr, 704, cols, rows, widths, fs=12)
    lines = ["判定の出どころ：%s（valid %s%s）" % (S.get("source"), S.get("valid"), ("、落ちた門 %s" % S.get("failed")) if S.get("failed") else ""),
             "「判定」行＝その計算の凍らせた判定の瞬間（e51 'max'）、「原画」行＝原画に最も近い瞬間の e51（x_c − 60〜+35 m、横 %g m まで）" % R.ymax,
             "miss＝W50・W80・W95・K・S2 の目標の帯からの外れの和（0 が帯の中）。数は【測定】記録から【計算】。原画らしさの最後の判断は利用者"]
    if S.get("note"):
        lines.insert(0, S["note"])
    for i, s_ in enumerate(lines):
        dr.text((xr, yy + 8 + 20 * i), s_[:120], fill=SUB, font=fnt(13))
    # footer
    dr.text((24, H - 26), "pv53（%s）：①②③ は同じ重みの基準。新しい目標は原画に合うことの上に重ねる条件で、置き換えではない。原画の視点の絵＝option D の構図（DM1A）を移した物【選び】" % TOOL,
            fill=SUB, font=fnt(12))
    p = od + "/pv53_%s.png" % R.id
    im.save(p)
    return p


# ====================================================================== main
def analyse(rd, log=print, judge=None):
    R = PVRun(rd, judge)
    log("pv53 %s [%s] eta0 %.4f (%s), %d periods from %s" % (R.id, R.fam, R.eta0, R.eta0_src[:40], len(R.periods), R.summary.get("source")))
    per = []
    for p in R.periods:
        sp = R.scan_period(p, log)
        if sp.get("best"):
            sp["best"]["_n"] = p["n"]
            sp["conv_print"] = R.conv_at(sp["best"]["frame"], sp["best"]["x_c"])
        per.append(sp)
    ok = [p for p in per if p.get("best")]
    best_p = min(ok, key=lambda p: (p["best"]["score3"], p["best"]["frame"])) if ok else None
    ref = reference()
    V = verdict(R, per, ref)
    return R, per, best_p, ref, V


def render_target(R, tp, a, od, tag, log=print):
    """one Unity clip + capture (print view and front view) at the period's print-like instant."""
    reuse = opt(a, "--reuse-cap") if tag == "print_like" else None
    try:
        clip, info = make_clip(R, dict(tp["best"], _n=tp["n"]), tp.get("conv_print") or {}, log)
    except (Exception, SystemExit) as ex:
        clip, info = None, dict(ok=False, why="no Unity clip: %s" % repr(ex)[:240])
    u = dict(info)
    if clip:
        pr = info["print_record"]
        cap = reuse or (OUT3D + "/pv53cap_%s_f%d" % (R.id, pr))
        try:
            u["sightline"] = sightline(R, pr, info["cameras"]["print_pos"], info["cameras"]["print_look"], info["cameras"]["x_c"])
        except Exception as ex:
            u["sightline"] = dict(error=repr(ex)[:200])
        if not reuse:
            u["unity_run"] = run_unity(clip, cap, opt(a, "--size", "1280x720"), int(opt(a, "--lockwait", "120")), log)
        u["capture"] = cap
        u.update(make_videos(cap, od, R.id + "_" + tag, pr, log))
        if not u.get("cprint_still"):
            u["ok"] = False
            u["why"] = "Unity の連番に原画の記録のコマがない（%s）" % ((u.get("unity_run") or {}).get("tail") or "")[-160:]
    log("  unity %s: %s" % (tag, {k: v for k, v in u.items() if k in ("ok", "why", "print_record", "clip")}))
    return u


def main_run(a, log=print):
    t0 = time.time()
    rd = a[0]
    R, per, best_p, ref, V = analyse(rd, log, opt(a, "--judge"))
    od = opt(a, "--out") or (B53 + "/pv53/" + R.id)
    os.makedirs(od, exist_ok=True)
    unity = None
    targets = []
    if best_p:
        targets.append(("print_like", best_p))
    red_n = (R.summary.get("red_instant") or {}).get("n")
    if red_n is not None:
        rp = [p for p in per if p["n"] == red_n and p.get("best")]
        if rp and (not best_p or rp[0]["n"] != best_p["n"]):
            targets.append(("converged", rp[0]))
    if targets and "--no-unity" not in a:
        unity = {}
        for tag, tp in targets:
            unity[tag] = render_target(R, tp, a, od, tag, log)
            unity[tag]["period"] = tp["n"]
        unity["ok"] = bool((unity.get("print_like") or {}).get("ok"))
        unity["why"] = (unity.get("print_like") or {}).get("why")
    elif "--no-unity" in a:
        unity = dict(ok=False, why="--no-unity")
    png = compose(R, per, best_p, (best_p or {}).get("conv_print"), ref, V, unity, od)
    out = dict(run_id=R.id, run_dir=R.rd, family=R.fam, tool=TOOL, tool_sha256=sha(os.path.abspath(__file__)), date=time.strftime("%Y-%m-%d %H:%M:%S"),
               eta0=R.eta0, eta0_source=R.eta0_src, judge=R.summary, scan_rule=SCAN, reference=ref, verdict=V,
               periods=[dict((k, v) for k, v in p.items() if k != "series") for p in per], series={str(p["n"]): p["series"] for p in per},
               most_print_like=dict(n=best_p["n"], frame=best_p["best"]["frame"], t=best_p["best"]["t"], score3=best_p["best"]["score3"],
                                    lip=best_p["best"].get("lip"), x_c=best_p["best"]["x_c"], eta_c=best_p["best"]["eta_c"]) if best_p else None,
               unity=unity, report_png=png, seconds=round(time.time() - t0, 1),
               tags="score3 / ruler / e51 numbers 【測定】 records -> 【計算】; windows, tolerance, cameras 【選び】")
    for p in out["periods"]:
        if p.get("best"):
            p["best"] = dict((k, v) for k, v in p["best"].items() if not k.startswith("_"))
    jp = od + "/pv53_%s.json" % R.id
    jdump(out, jp)
    log(json.dumps(clean(dict(run=R.id, print_match=V["print_match_line"], convergence=V["convergence_line"], progress=V.get("progress_line"),
                              most_print_like=out["most_print_like"], report=png, json=jp, unity_ok=(unity or {}).get("ok"),
                              seconds=out["seconds"])), ensure_ascii=False))
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "run" and len(a) > 1:
        main_run(a[1:])
    elif a[0] == "scan" and len(a) > 1:
        R, per, best_p, ref, V = analyse(a[1], log=lambda s: print(s, file=sys.stderr), judge=opt(a, "--judge"))
        print(json.dumps(clean(dict(run=R.id, verdict=V, periods=[dict((k, v) for k, v in p.items() if k != "series") for p in per])), ensure_ascii=False, default=str))
    elif a[0] == "ref":
        print(json.dumps(clean(reference()), ensure_ascii=False, indent=1))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
