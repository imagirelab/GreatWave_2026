# -*- coding: utf-8 -*-
"""FLIP55 C2H HERO (Unity): the stitched C2H surface (f55_stitch.py) played in the FLIP3D player as the hero, Q86 design (py -3.10 -B; numpy,
scipy, PIL, ffmpeg; Unity batch only in `unity` / `views3 unity`). 2026-10-19 written new (Claude, workflow subagent) for the user's Q90:
  把 0.25 m 局部加密继续算到第 2、3 组，并和外面的水面拼接，做成主角。
  OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral
No existing file is edited: flip52b3h/h52b3_hero.py (seat table, touchdown, column, crest_track, move_path rules, stay rule), flip53/pv53.py
(PVRun, scan_period, conv_at, cameras), flip50g2/f3d50_video_loop.py (compose_cont_exact) and flip3d/f3d_unity.ps1 /
FLIP3DBatch.BuildSceneAndCapture are used unchanged (imported or called). Writes: Unity/Build/FLIP55/hero_C2H/ (json, cameras, unity backups,
views3 frames), Unity/Build/FLIP3D/clip_C2H_stitch_f1153_3001_r24_seatA_ds/ (GW45LIST1 manifest that STREAMS the stitched records + bed.f32),
Unity/Build/FLIP3D/capture_C2H_stitch_..._ds/ (Unity frames), the views3 clip / capture (clip_C2H_stitch_views3_*, capture_C2H_stitch_views3_*),
Unity/Build/FLIP3D/video/FLIP3D_C2H_stitch_* (mp4 + sheets). The DFG-2B-E / DFG-2B-V hero files are never written (guard).

Design [chosen unless tagged]:
  seat      A (Unity seat_x 284, seat_z -20, eye 1.5 m, look (263.74, 6.04, 1.67), FOV 55; the Q86 seat) with the clearance rule of h52b3_hero
            (>= 1.0 m on every frame 1153-3001: nest hf at the seat point, the STITCHED mesh at the eye point and the stitched mesh column
            through the eye); heave = mean of C2H's hf over the boat footprint x +-4 m, lateral +-1.5 m (the player / f3d50_export rule; the
            seat lies inside the nest region). `--seat auto` (default): A if it passes, else B (305, -32, eye 1.75; the h52b3 fallback) if B
            passes, else A with the failure on every output.
  print     pv53 option D of C2H's OWN group-2 most print-like instant: pv53.PVRun(C2H, judge = the PARENT's g52/judge_DFG.json) ->
            scan_period (score3 on C2H's centre section r2) -> conv_at (e51 Hc on C2H's hf) -> pv53.cameras; the nest's own judge-like tracker
            is NOT used (it mis-tracked Hc 3.2 m vs ~7.2 m in group 1 [measured]); the print eye is raised by pv53's rule (0.8 m) against the
            STITCHED scene's water (parent hf at the camera, which lies outside the nest box) when needed.
  move      Q86: -f3dmoves f<group-2 best frame> -f3dmovesec 6 -f3dhold 2 -f3dstay S -f3dback 6; S = 2.5 s kept iff the crest leaves the
            print frame within 0.5 s of DFG-2B-E's under the same rule (h52b3_hero.crest_track / STAY_RULE), else 2.5 + the difference rounded
            to 0.25 s; no white-out; VR adds -f3dnocrestalign.
  captures  cseat / cprint / cmove 1920x1080 24 fps, 48-125 s (h52b3_hero.capture_args layout); capcheck as h52b3 (record order, the
            schedule, camera clearance on the stitched mesh, white-out); captioned mp4s; 3-view 2x2 video (front = pv53's front camera of
            group 2, top = views3's top camera, print view = the hero cprint, the print); contact sheet.
  labels    every manifest note, caption line, sheet header and json carries LABEL (above), the display-stitch line and the C2H identity line.

usage (py -3.10 -B; each prints ONE json line last; --simulate = the C2 stand-in (group 1, its 3rd-frame records, _scratch/stitch_sim)):
  f55_c2h_hero.py pv53 [--simulate]           pv53 per group on C2H with the parent's judge + the group-2 print pose -> pv53_C2H.json
  f55_c2h_hero.py cues [--simulate]           onset (the parent's judge, r2 lip) / touchdown (C2H's r2, h52b3 rule) per group
  f55_c2h_hero.py seatcheck [--seat auto|A|B] [--simulate]   stitched-surface clearance every frame + print-camera clearance
  f55_c2h_hero.py stay [--simulate]           the crest-leaves-frame rule (C2H vs DFG-2B-E) -> the stay seconds
  f55_c2h_hero.py movepath [--simulate]       camera clearance on the move (composite hf: nest inside the seam, parent outside)
  f55_c2h_hero.py clip [--simulate]           cameras JSON + the GW45LIST1 clip of the stitched records (needs stitch verify ok)
  f55_c2h_hero.py unity [--dry]               memory check, backup, f3d_unity.ps1 (cseat, cprint, cmove), restore
  f55_c2h_hero.py capcheck                    the capture checks
  f55_c2h_hero.py video [--dry]               captioned mp4s (compose_cont_exact + the label lines)
  f55_c2h_hero.py views3 clip|unity|compose [--dry]   the 3-view 2x2 video (+ single views, still sheet)
  f55_c2h_hero.py sheet                       contact sheet (seat / print view at each group's print-like instant + pv53 report)
  f55_c2h_hero.py status | selftest
Tags: [measured] records / captures, [computed] derived, [chosen] seat, poses, rules.
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys, json, time, csv, io, shutil, hashlib, subprocess, contextlib, ctypes, math, glob, importlib.util

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
for _p in (TOOLS + "/flip50g2", TOOLS + "/flip3d", TOOLS + "/flip52b3h", TOOLS + "/flip53", TOOLS + "/flip52b3", HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                                                         # noqa: E402

TOOL = "Tools/GWWaveGen/flip55/f55_c2h_hero.py"
HM_PATH = TOOLS + "/flip52b3h/h52b3_hero.py"
B55 = REPO + "/Unity/Build/FLIP55"
B52B3 = REPO + "/Unity/Build/FLIP52B3"
HERO_DIR = B55 + "/hero_C2H"
SIM_HERO = B55 + "/_scratch/sim_c2h_hero"
OUT3D = REPO + "/Unity/Build/FLIP3D"
VID = OUT3D + "/video"
RID_C2H = "F55NH_D19B_x180y60_dp0p25_c1056_t125"
RD_C2H = B55 + "/runs/" + RID_C2H
RD_C2 = B55 + "/runs/F55N_D19B_x180y60_dp0p25_c1056"
STITCH_OUT = B55 + "/stitch/C2H"
STITCH_SIM = B55 + "/_scratch/stitch_sim"
PARENT_RUN = B52B3 + "/hero/runs/DFGBVr_D19B_xf272p25_in5c0p6_tp3_dp0p5_c1152_t125_long"       # every-frame hf / surf 1153-3001
JUDGE52 = B52B3 + "/runs/DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5/g52/judge_DFG.json"             # the parent's judge (pv53 groups f / x_pk)
JUDGEV = B52B3 + "/runs/DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5/g52b3/judge_DFGB4.json"          # the parent's judge (onsets)
TEMPLATE_CLIP = OUT3D + "/clip_DFGBVr_f1153_3001_r24_seatA_ds"                                  # full-tank bed / tank fields of the parent hero
PV53_JSON_C2H = REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (RID_C2H, RID_C2H)
PRINT_IMG = REPO + "/Docs/References/Met_JP1847.jpg"
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
UNITY_METHOD = "GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture"
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FPS = 24.0
F0, F1 = 1153, 3001
STILL = 0.0759846568107605
COMMIT_MIN_GB = 8.0                                                     # the project rule before any Unity batch
CLEAR_MIN = 1.0
NEAR = 2.0
MOVE_BASE = dict(move=6.0, hold=2.0, back=6.0)                          # Q86 [chosen]; stay from `stay`
TOP_POS, TOP_LOOK, TOP_FOV = [252.0, 200.0, -7.0], [252.0, 0.0, 0.0], 35.5      # = views3's top camera [chosen there]
LABEL = "OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral"
LABEL_JA = "規則の外の 0.25 m の入れ子（同一性の試しで頂の高さ +5.9 %、容差 ±2 %、Q89/Q90）。親 DFG-2B-V は有効。エネルギーは DM1A のスペクトル"
PARENT_EN = ("parent DFG-2B-V (DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5): VALID by the frozen DFGB4 rule; energy: sum a^2 = DM1A's 1.336 m^2 "
             "(spectral), in-tank power 0.23 x DM1A")
NOSHAPE_EN = "no shapes between frames"
SHORT = "C2Hstitch"
CLIP_NAME = "clip_C2H_stitch_f%d_%d_r24_seat%%s_ds" % (F0, F1)
CAP_NAME = "capture_C2H_stitch_f%d_%d_r24_seat%%s_ds" % (F0, F1)
V3_CLIP = OUT3D + "/clip_C2H_stitch_views3_f%d_%d_r24" % (F0, F1)
V3_CAP = OUT3D + "/capture_C2H_stitch_views3_f%d_%d_r24" % (F0, F1)
V3_FR = HERO_DIR + "/views3_frames"
PROTECT = (B52B3 + "/", REPO + "/Unity/Build/FLIP52B/", OUT3D + "/clip_DFGB", OUT3D + "/capture_DFGB", VID + "/FLIP3D_DFGB")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def guard(p):
    q = os.path.abspath(p).replace("\\", "/")
    for pre in PROTECT:
        if q.lower().startswith(pre.lower()):
            raise SystemExit("refused: %s belongs to another hero / run (read only)" % q)
    if not (q.lower().startswith(B55.lower() + "/") or q.lower().startswith(OUT3D.lower() + "/")):
        raise SystemExit("refused: %s outside Unity/Build/FLIP55 and Unity/Build/FLIP3D" % q)
    os.makedirs(os.path.dirname(q), exist_ok=True)
    return q


def jdump(o, p):
    guard(p)
    tmp = p + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def t_of(f):
    return (int(f) - 1) / FPS


def final(d):
    d = clean(dict([("label", LABEL)] + [(k, v) for k, v in d.items() if k != "label"]))
    print(json.dumps(d, ensure_ascii=False, default=str), flush=True)
    return 0 if d.get("ok") else 1


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


_HM = None


def hm():
    """h52b3_hero imported unchanged (its rules / readers); nothing of it writes here."""
    global _HM
    if _HM is None:
        spec = importlib.util.spec_from_file_location("h52b3_hero", HM_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _HM = m
    return _HM


def stitch_mod():
    import f55_stitch as S
    return S


# ====================================================================== context (real or the C2 stand-in)
class Ctx:
    def __init__(self, o):
        self.sim = "simulate" in o
        self.rd = RD_C2 if self.sim else RD_C2H
        self.stitch = STITCH_SIM if self.sim else STITCH_OUT
        self.out = SIM_HERO if self.sim else HERO_DIR
        self.f0, self.f1 = (1321, 1360) if self.sim else (F0, F1)
        self.cfg = jload(self.rd + "/cfg.json") or {}
        self.groups = (1,) if self.sim else (1, 2, 3)
        self.print_group = 1 if self.sim else 2

    def j(self, name):
        return self.out + "/%s.json" % name

    def seat(self):
        s = jload(self.j("seat_choice")) or {}
        return dict(hm().SEATS[s.get("seat", "A")])

    def clip(self, seat=None):
        s = seat or self.seat()["name"]
        return (SIM_HERO + "/" + CLIP_NAME % s) if self.sim else (OUT3D + "/" + CLIP_NAME % s)

    def cap(self, seat=None):
        s = seat or self.seat()["name"]
        return OUT3D + "/" + CAP_NAME % s


def identity_line():
    j = jload(RD_C2H + "/f55/identity_C2.json") or {}
    return j.get("summary") or "C2H vs C2 on group 1: not compared yet"


def stitch_line(ctx):
    S = stitch_mod()
    v = jload(ctx.stitch + "/stitch_verify.json") or {}
    r = v.get("seam_rms_m") or {}
    return ("DISPLAY STITCH: nest 0.25 m inside x %g-%g m, lateral 0-%g m; DFG-2B-V 0.5 m outside; seam blend %g m + zipper; seam mismatch rms "
            "median %s m, max %s m, max |dz| %s m [measured]" % (S.SEAM["x_s"], S.SEAM["x_e"], S.SEAM["y_s"], S.SEAM["blend_m"],
                                                                None if r.get("median") is None else round(r["median"], 3),
                                                                None if r.get("max") is None else round(r["max"], 3),
                                                                None if v.get("seam_max_abs_m") is None else round(v["seam_max_abs_m"], 3)))


def flags_line(ctx):
    """the failures the design promises to print on every output (review 2026-10-19): seat clearance, the print-pose Hc sanity."""
    out = []
    sc = jload(ctx.j("seat_choice")) or {}
    if sc and not sc.get("ok"):
        out.append("SEAT %s FAILS the 1 m clearance rule on the stitched surface (%s)" % (sc.get("seat"), rel(ctx.j("seatcheck"))))
    pj = jload(ctx.j("pv53_C2H")) or {}
    hs = pj.get("hc_sanity") or {}
    if hs and not hs.get("ok"):
        out.append("PRINT POSE scaled by the nest's Hc %.2f m vs the parent's judged %.2f m (ratio %.2f outside %s)" % (
            hs.get("Hc_nest_conv_print") or 0.0, hs.get("Hc_parent_judged") or 0.0, hs.get("ratio") or 0.0, hs.get("band")))
    return " | ".join(out)


def honesty(ctx):
    fl = flags_line(ctx)
    return [LABEL, PARENT_EN, stitch_line(ctx), identity_line() + " | " + NOSHAPE_EN + ((" | " + fl) if fl else "")]


# ====================================================================== readers
class HFComp:
    """the stitched scene's water height: C2H's hf inside the nest region (seam rectangle), the parent's every-frame hf outside."""

    def __init__(self, ctx):
        import f3d_common as C
        self.C = C
        self.Hn = C.Rec("hf", ctx.rd)
        self.Hp = C.Rec("hf", PARENT_RUN)
        self.xn, self.zn = C.axes_hf(self.Hn.meta)
        self.xp, self.zp = C.axes_hf(self.Hp.meta)
        self.seam = stitch_mod().SEAM

    @staticmethod
    def _bil(e, xs, zs, x, z):
        x = np.atleast_1d(np.asarray(x, float)); z = np.abs(np.atleast_1d(np.asarray(z, float)))
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2); j = np.clip(np.searchsorted(zs, z) - 1, 0, len(zs) - 2)
        u = np.clip((x - xs[i]) / (xs[i + 1] - xs[i]), 0, 1); v = np.clip((z - zs[j]) / (zs[j + 1] - zs[j]), 0, 1)
        q00, q01, q10, q11 = e[j, i], e[j, i + 1], e[j + 1, i], e[j + 1, i + 1]
        return (1 - v) * ((1 - u) * q00 + u * q01) + v * ((1 - u) * q10 + u * q11)

    def inside(self, x, z):
        s = self.seam
        x = np.atleast_1d(np.asarray(x, float)); z = np.abs(np.atleast_1d(np.asarray(z, float)))
        return (x >= s["x_s"]) & (x <= s["x_e"]) & (z <= s["y_s"])

    def h(self, f, x, z):
        x = np.atleast_1d(np.asarray(x, float)); z = np.atleast_1d(np.asarray(z, float))
        ins = self.inside(x, z)
        out = np.full(len(x), np.nan)
        if ins.any() and f in self.Hn.where:
            out[ins] = self._bil(self.Hn.get(f).astype(np.float64), self.xn, self.zn, x[ins], z[ins])
        if (~ins).any() and f in self.Hp.where:
            out[~ins] = self._bil(self.Hp.get(f).astype(np.float64), self.xp, self.zp, x[~ins], z[~ins])
        return out

    def hmax_near(self, f, x, z, half=NEAR, n=9):
        g = np.linspace(-half, half, n)
        X, Z = np.meshgrid(x + g, abs(z) + g)
        v = self.h(f, X.ravel(), Z.ravel())
        return float(np.nanmax(v)) if np.isfinite(v).any() else None


def heave_of(ctx, seat, frames):
    import f3d_common as C
    HF = C.Rec("hf", ctx.rd)
    xs, zs = C.axes_hf(HF.meta)
    return hm().heave_series(HF, xs, zs, seat, frames), HF, xs, zs


def stitched(ctx, f):
    return hm().surf_points(ctx.stitch + "/surf/s_%05d.gw45s" % f)


# ====================================================================== pv53 on C2H (the parent's judge periods)
def cmd_pv53(o):
    ctx = Ctx(o)
    t0 = time.time()
    import pv53 as PV
    log = lambda *a: None
    with contextlib.redirect_stdout(io.StringIO()):
        R = PV.PVRun(ctx.rd, judge=JUDGE52)
    per = []
    for p in R.periods:
        if p["n"] not in ctx.groups:
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            sp = R.scan_period(p, log)
        if sp.get("best"):
            sp["best"]["_n"] = p["n"]
            sp["conv_print"] = R.conv_at(sp["best"]["frame"], sp["best"]["x_c"])
        per.append(sp)
    g = [p for p in per if p.get("n") == ctx.print_group and p.get("best")]
    if not g:
        return final(dict(ok=False, step="pv53", why="no print-like instant for group %d" % ctx.print_group, periods=[p.get("n") for p in per]))
    best, conv = g[0]["best"], g[0].get("conv_print") or {}
    fb = int(best["frame"])
    clip_frames = [f for f in range(fb + int(PV.CLIP_S[0] * FPS), fb + int(PV.CLIP_S[1] * FPS) + 1) if f in R.hfset][::3]
    cam = PV.cameras(R, best, conv, clip_frames)
    # the print camera lies outside the nest box (lateral ~75 m): pv53's clearance rule against the STITCHED scene (parent hf there)
    notes = list(cam.get("notes") or [])
    try:
        HC = HFComp(ctx)
        hs = [HC.hmax_near(f, cam["print_pos"][0], cam["print_pos"][2]) for f in clip_frames]
        hs = [h for h in hs if h is not None]
        hmax = max(hs) if hs else None
        if hmax is not None and cam["print_pos"][1] - R.eta0 < hmax + PV.CLEAR_M:
            notes.append("print eye raised %.2f m against the stitched scene (parent hf within %.1f m of the eye)" % (hmax + PV.CLEAR_M - (cam["print_pos"][1] - R.eta0), PV.CLEAR_M))
            cam["print_pos"][1] = R.eta0 + hmax + PV.CLEAR_M
        cam["hf_near_print_cam_stitched"] = hmax
    except Exception as e:
        notes.append("stitched clearance at the print camera not checked: %r" % e)
    # Hc sanity (review 2026-10-19): pv53.cameras scales option D by the nest's conv_at Hc; the nest's judge-like tracker once read 3.2 m
    # for ~7.2 m, so the Hc used here is compared with the PARENT's judged Hc of the same group (report + flag on every output, no stop)
    hc_band = [0.75, 1.25]                                                 # [chosen]: C2 group 1 gave 7.57 / 8.05 = 0.94 [measured]
    try:
        jg = {int(g["n"]): g for g in (jload(JUDGE52) or {}).get("groups") or []}
        hp = float((jg.get(ctx.print_group) or {}).get("Hc") or float("nan"))
        hn = float(cam.get("Hc_used") or float("nan"))
        ratio = hn / hp if (math.isfinite(hn) and math.isfinite(hp) and hp > 0) else None
        hc_sanity = dict(Hc_nest_conv_print=hn, Hc_parent_judged=hp, ratio=ratio, band=hc_band, ok=bool(ratio is not None and hc_band[0] <= ratio <= hc_band[1]),
                         rule="the nest's conv_at Hc at the print-like instant / the parent's judge_DFG.json Hc of the same group within %s [chosen]" % hc_band)
    except Exception as e:
        hc_sanity = dict(ok=False, why="not checked: %r" % e, band=hc_band)
    if not hc_sanity.get("ok"):
        notes.append("Hc sanity FAILED: the print pose scale uses the nest's Hc %s vs the parent's judged %s (see hc_sanity)" % (
            hc_sanity.get("Hc_nest_conv_print"), hc_sanity.get("Hc_parent_judged")))
    cam["notes"] = notes
    rows = []
    for p in per:
        b = p.get("best") or {}
        rows.append(dict(n=p["n"], f_max=p.get("f_max"), x_max=p.get("x_max"), window_frames=p.get("window_frames"),
                         best={k: b.get(k) for k in ("frame", "t", "score3", "lip", "hood", "x_c", "eta_c", "chord", "foot") if k in b},
                         conv_print={k: (p.get("conv_print") or {}).get(k) for k in ("Hc", "x_pk", "y_pk", "frame", "t", "miss")}))
    res = dict(date=now(), tool=TOOL, step="pv53", run=rel(ctx.rd), judge=rel(JUDGE52), eta0=R.eta0, eta0_source=R.eta0_src, groups=rows,
               print_group=ctx.print_group, print_frame=fb, print_pose=dict(pos=cam["print_pos"], look=cam["print_look"], fov_v=cam["print_fov_v"],
                                                                           Hc_used=cam["Hc_used"], x_c=cam["x_c"], scale=cam["scale"], notes=notes),
               front_pose=dict(pos=cam["front_pos"], look=cam["front_look"], fov_v=cam["front_fov_v"]), cameras=cam, hc_sanity=hc_sanity,
               pv53_tool_sha256=sha(TOOLS + "/flip53/pv53.py"),
               rule=("pv53.PVRun(<run>, judge = the parent's g52/judge_DFG.json) -> scan_period (score3 on the run's centre section r2, every frame "
                     "of [t_max - 1.5, t_max + 3] s) -> conv_at (e51 Hc on the run's hf) -> pv53.cameras (option D scaled by Hc / 7.16 m); the nest's own "
                     "judge-like tracker is not used [chosen]"),
               label=LABEL, simulate=ctx.sim, seconds=round(time.time() - t0, 1), tags="[measured] r2 / hf -> [computed] poses; rule [chosen]")
    jdump(res, ctx.j("pv53_C2H"))
    return final(dict(ok=True, step="pv53", out=rel(ctx.j("pv53_C2H")), groups=[(r["n"], r["best"].get("frame"), r["best"].get("score3"),
                                                                                  r["conv_print"].get("Hc")) for r in rows],
                      print_frame=fb, print_pose=res["print_pose"], hc_sanity=hc_sanity, simulate=ctx.sim))


def pv(ctx):
    j = jload(ctx.j("pv53_C2H"))
    if not j:
        raise SystemExit("no %s: run `pv53` first" % rel(ctx.j("pv53_C2H")))
    return j


# ====================================================================== cues
def cmd_cues(o):
    ctx = Ctx(o)
    H = hm()
    import g52b3_common as GC
    J = jload(JUDGEV) or {}
    spec = GC.bed_spec(ctx.cfg)
    oy = float(ctx.cfg["parms"].get("oy", 0.5))
    bed_of = lambda x: np.asarray(GC.bed_z(np.asarray(x, float), np.full(np.shape(x), 0.5), **spec), float)
    import f3d_common as C
    R2 = C.Rec("r2", ctx.rd)
    P = pv(ctx)
    best = {int(g["n"]): g["best"] for g in P["groups"]}
    out = []
    for g in J.get("groups") or []:
        n = int(g["n"]); on = g.get("onset") or {}
        if n not in ctx.groups or not on.get("frame"):
            continue
        f_on, x_on = int(on["frame"]), float(on["x"])
        td = H.touchdown(R2, R2.meta, f_on, x_on, bed_of, oy, ctx.f1 if not ctx.sim else 1657)
        b = best.get(n) or {}
        w1 = (td["frame"] + H.CAVITY["td_pad_frames"]) if td else (f_on + 60)
        out.append(dict(k=n, onset=dict(frame=f_on, t=t_of(f_on), x=x_on, source="the parent's judge_DFGB4.json groups[%d].onset (r2 lip) [measured]" % (n - 1)),
                        touchdown=td, win_first=f_on, win_last=int(min(w1, 3001)), best_frame=b.get("frame"),
                        best_inside=bool(b.get("frame") and f_on <= b["frame"] <= w1),
                        win_rule=("onset .. touchdown (C2H's r2, h52b3_hero.touchdown) + 0.5 s" if td else "onset .. onset + 2.5 s (no enclosed pocket)")))
    res = dict(date=now(), tool=TOOL, step="cues", run=rel(ctx.rd), cues=out, cavity=H.CAVITY, label=LABEL, simulate=ctx.sim,
               note="onsets borrowed from the parent's judge (the nest has no valid judge; its tracker mis-tracked Hc); touchdown measured on C2H's r2",
               tags="[measured] r2; rule [chosen]")
    jdump(res, ctx.j("cues"))
    return final(dict(ok=bool(out), step="cues", cues=[(c["k"], c["win_first"], (c["touchdown"] or {}).get("frame"), c["win_last"], c["best_frame"])
                                                       for c in out], simulate=ctx.sim))


# ====================================================================== seat clearance on the stitched surface
def seat_check(ctx, seat, P, frames_mesh=None):
    H = hm()
    frames = list(range(ctx.f0, ctx.f1 + 1))
    hv, HF, xs, zs = heave_of(ctx, seat, [f for f in frames])
    eye = STILL + seat["eye"] + hv
    lat = abs(seat["z"])
    HC = HFComp(ctx)
    pt = np.array([eye[i] - float(HC.h(f, seat["x"], lat)[0]) for i, f in enumerate(frames)])
    nb = np.array([eye[i] - (HC.hmax_near(f, seat["x"], lat) or -1e9) for i, f in enumerate(frames)])
    mrows = []
    sf = frames_mesh or [f for f in frames if os.path.exists(ctx.stitch + "/surf/s_%05d.gw45s" % f)]
    fi = {f: i for i, f in enumerate(frames)}
    for f in sf:
        Pm, T, _, _ = stitched(ctx, f)
        m = (np.abs(Pm[:, 0] - seat["x"]) <= H.FOOT[0]) & (np.abs(np.abs(Pm[:, 2]) - lat) <= H.FOOT[1])
        me = (np.abs(Pm[:, 0] - seat["x"]) <= 0.5) & (np.abs(np.abs(Pm[:, 2]) - lat) <= 0.5)
        col = H.column(Pm, T, seat["x"], lat)
        e_ = eye[fi[f]]
        mrows.append((f, e_ - (float(Pm[m, 1].max()) if m.any() else -1e9), e_ - (float(col.max()) if len(col) else -1e9),
                      int((col > e_).sum()) if len(col) else 0, e_ - (float(Pm[me, 1].max()) if me.any() else -1e9)))
    mf = np.array([r[1] for r in mrows] or [np.inf]); mc = np.array([r[2] for r in mrows] or [np.inf]); mev = np.array([r[4] for r in mrows] or [np.inf])
    # the print camera: stitched hf +-2 m and the stitched mesh column, during hold + stay
    pp = P["print_pose"]["pos"]
    mvf = int(P["print_frame"])
    stay_s = float((jload(ctx.j("stay")) or {}).get("stay_s") or 2.5)
    hold_frames = [f for f in frames if mvf <= f <= mvf + int(round(stay_s * FPS))]
    pc = [pp[1] - (HC.hmax_near(f, pp[0], pp[2]) or -1e9) for f in hold_frames]
    pcol = []
    for f in hold_frames:
        if os.path.exists(ctx.stitch + "/surf/s_%05d.gw45s" % f):
            Pm, T, _, _ = stitched(ctx, f)
            col = H.column(Pm, T, pp[0], abs(pp[2]))
            pcol.append(pp[1] - (float(col.max()) if len(col) else -1e9))
    rate = np.abs(np.diff(hv)) * FPS if len(hv) > 1 else np.zeros(1)
    res = dict(seat=seat, frames=[frames[0], frames[-1]], n_meshes=len(mrows), meshes_expected=len(frames),
               model="eye(t) = still 0.076 + eye + heave(t); heave = mean of C2H's hf over x +-%g m, lateral +-%g m (player rule)" % H.FOOT,
               hf_point_min_m=float(pt.min()), hf_point_min_frame=frames[int(pt.argmin())], hf_near2m_min_m=float(nb.min()),
               mesh_eye_min_m=float(mev.min()), mesh_eye_min_frame=(mrows[int(mev.argmin())][0] if mrows else None),
               mesh_column_min_m=float(mc.min()), mesh_column_min_frame=(mrows[int(mc.argmin())][0] if mrows else None),
               mesh_footprint_min_m=float(mf.min()), mesh_footprint_min_frame=(mrows[int(mf.argmin())][0] if mrows else None),
               mesh_frames_column_above_eye=[r[0] for r in mrows if r[3] > 0][:50],
               hf_point_lt1=H.ranges([(frames[i], round(float(v), 3)) for i, v in enumerate(pt) if v < CLEAR_MIN]),
               mesh_eye_lt1=H.ranges([(r[0], round(float(r[4]), 3)) for r in mrows if r[4] < CLEAR_MIN]),
               heave_range_m=[float(hv.min()), float(hv.max())], heave_rate_max_mps=float(rate.max()),
               print_cam_hf2m_hold_stay_min_m=float(min(pc)) if pc else None, print_cam_mesh_column_hold_stay_min_m=float(min(pcol)) if pcol else None,
               print_pose=P["print_pose"], print_frame=mvf)
    res["ok"] = bool(len(mrows) == len(frames) and res["hf_point_min_m"] >= CLEAR_MIN and res["mesh_eye_min_m"] >= CLEAR_MIN
                     and res["mesh_column_min_m"] >= CLEAR_MIN) if not ctx.sim else bool(res["hf_point_min_m"] >= CLEAR_MIN
                                                                                       and res["mesh_eye_min_m"] >= CLEAR_MIN and res["mesh_column_min_m"] >= CLEAR_MIN)
    return res, hv


def cmd_seatcheck(o):
    ctx = Ctx(o)
    t0 = time.time()
    P = pv(ctx)
    want = o.get("seat", "auto")
    order = ["A", "B"] if want == "auto" else [want]
    tried = {}
    chosen = None
    for s in order:
        r, _ = seat_check(ctx, dict(hm().SEATS[s]), P)
        tried[s] = r
        if r["ok"]:
            chosen = s
            break
    if chosen is None:
        chosen = order[0]
    rule = ("every frame %d-%d: C2H hf at the seat point (composite: nest inside the seam), the STITCHED mesh at the eye point (+-0.5 m) and the "
            "stitched mesh column through the eye all >= %.1f m below the eye (h52b3_hero rule) [chosen]; seat auto: A, else B, else A flagged"
            % (ctx.f0, ctx.f1, CLEAR_MIN))
    res = dict(date=now(), tool=TOOL, step="seatcheck", run=rel(ctx.rd), stitch=rel(ctx.stitch), want=want, seat=chosen, tried=tried, rule=rule,
               ok=bool(tried[chosen]["ok"]), flag=None if tried[chosen]["ok"] else "seat %s fails the clearance rule (see tried)" % chosen,
               honesty_en=honesty(ctx), simulate=ctx.sim, seconds=round(time.time() - t0, 1),
               tags="[measured] hf / stitched surf -> [computed] clearances; rule [chosen]")
    jdump(res, ctx.j("seatcheck"))
    jdump(dict(seat=chosen, ok=res["ok"], date=now(), source=rel(ctx.j("seatcheck")), label=LABEL), ctx.j("seat_choice"))
    r = tried[chosen]
    return final(dict(ok=res["ok"], step="seatcheck", seat=chosen, hf_point_min_m=r["hf_point_min_m"], mesh_eye_min_m=r["mesh_eye_min_m"],
                      mesh_column_min_m=r["mesh_column_min_m"], mesh_footprint_min_m=r["mesh_footprint_min_m"], heave_range_m=r["heave_range_m"],
                      print_cam=[r["print_cam_hf2m_hold_stay_min_m"], r["print_cam_mesh_column_hold_stay_min_m"]], flag=res["flag"], simulate=ctx.sim))


# ====================================================================== stay (crest leaves the print frame) and move path
def cmd_stay(o):
    ctx = Ctx(o)
    H = hm()
    P = pv(ctx)
    pose = dict(pos=P["print_pose"]["pos"], look=P["print_pose"]["look"], fov_v=P["print_pose"]["fov_v"])
    g = [x for x in P["groups"] if x["n"] == ctx.print_group][0]
    v = H.crest_track(ctx.rd, int(P["print_frame"]), float(g["best"]["x_c"]), pose)
    be = H.pv53_best(H.E_PV53).get(2) or {}
    e = H.crest_track(H.E_RUN, H.E_MOVE["frame"], float(be["x_c"]), H.E_PRINT)
    dv = (v["leave"] or {}).get("after_arrival_s"); de = (e["leave"] or {}).get("after_arrival_s")
    R = H.STAY_RULE
    delta = None if (dv is None or de is None) else round(dv - de, 4)
    keep = bool(delta is not None and abs(delta) <= R["tol_s"])
    stay = R["keep_s"] if (keep or delta is None) else round(round((R["keep_s"] + delta) / R["step_s"]) * R["step_s"], 2)
    stay = max(R["step_s"], min(stay, R["max_s"]))
    res = dict(date=now(), tool=TOOL, step="stay", run=rel(ctx.rd), rule=dict(R, text=H.crest_track.__doc__.strip() + " Decision: 2.5 s kept if C2H's "
                                                                                 "leave delay differs from DFG-2B-E's (same rule) by <= 0.5 s; else 2.5 + "
                                                                                 "the difference rounded to 0.25 s (h52b3_hero rule); no leave found -> 2.5 s"),
               c2h=dict(v, pose=pose, print_frame=P["print_frame"]), dfgb2e_reference=dict(e, pose=H.E_PRINT, move=H.E_MOVE),
               leave_after_arrival_s=dict(C2H=dv, DFG2BE=de, difference_s=delta), keep_2p5=keep, stay_s=stay, label=LABEL, simulate=ctx.sim,
               tags="[measured] hf -> [computed] crest track; rule [chosen]")
    jdump(res, ctx.j("stay"))
    return final(dict(ok=True, step="stay", stay_s=stay, keep_2p5=keep, leave=dict(C2H=dv, DFG2BE=de, difference_s=delta), simulate=ctx.sim))


def move_sched(ctx):
    P = pv(ctx)
    st = jload(ctx.j("stay")) or {}
    return dict(frame=int(P["print_frame"]), move=MOVE_BASE["move"], hold=MOVE_BASE["hold"], stay=float(st.get("stay_s") or 2.5), back=MOVE_BASE["back"])


def cmd_movepath(o):
    ctx = Ctx(o)
    H = hm()
    P = pv(ctx)
    mv = move_sched(ctx)
    seat = ctx.seat()
    HC = HFComp(ctx)
    f_arr = mv["frame"]
    fr = [f for f in range(f_arr - int(round(mv["move"] * FPS)), f_arr + int(round((mv["stay"] + mv["back"]) * FPS)) + 1)
          if f in HC.Hn.where and f in HC.Hp.where]
    hv, _, _, _ = heave_of(ctx, seat, fr)
    Pp = np.array(P["print_pose"]["pos"], float)
    rows = []
    for k, f in enumerate(fr):
        c = (f - f_arr) / FPS
        bl = H.smooth01((c + mv["move"]) / mv["move"]) if c < 0 else (1.0 if c <= mv["stay"] else 1.0 - H.smooth01((c - mv["stay"]) / mv["back"]))
        eye = np.array([seat["x"], STILL + seat["eye"] + hv[k], seat["z"]])
        Q = eye * (1 - bl) + Pp * bl
        w = float(HC.h(f, Q[0], Q[2])[0])
        nm = HC.hmax_near(f, Q[0], Q[2], half=1.5, n=3)
        rows.append((f, round(c, 4), round(bl, 4), round(float(Q[1] - w), 3) if np.isfinite(w) else None, round(float(Q[1] - (nm if nm is not None else -30.0)), 3)))
    cl = [r for r in rows if r[3] is not None]
    worst = min(cl, key=lambda r: r[3]) if cl else None
    e = H.move_path(H.E_RUN, H.SEATS["A"], H.E_PRINT, H.E_MOVE, 0.07598474621772766)
    ok = bool(worst is not None and e["min_clear_m"] is not None and worst[3] >= min(CLEAR_MIN, e["min_clear_m"] - 0.25)) if not ctx.sim else bool(worst)
    res = dict(date=now(), tool=TOOL, step="movepath", run=rel(ctx.rd), move=mv, seat=seat, pose=P["print_pose"], n=len(rows),
               min_clear_m=worst[3] if worst else None, min_clear_at=worst[:3] if worst else None, every_12th=rows[::12],
               dfgb2e_reference=dict(min_clear_m=e["min_clear_m"], min_clear_at=e["min_clear_at"]), ok=ok,
               ok_rule="C2H's smallest hf clearance on the move path >= min(1.0 m, DFG-2B-E's - 0.25 m) (h52b3_hero rule); hf = composite (nest inside "
                       "the seam, parent outside)", label=LABEL, simulate=ctx.sim, tags="[measured] hf -> [computed] path; rule [chosen]")
    jdump(res, ctx.j("movepath"))
    return final(dict(ok=ok, step="movepath", min_clear_m=res["min_clear_m"], at=res["min_clear_at"], dfgb2e=e["min_clear_m"], move=mv, simulate=ctx.sim))


# ====================================================================== cameras + clip
def cams_json(ctx):
    seat = ctx.seat()
    P = pv(ctx)
    mv = move_sched(ctx)
    p = ctx.out + "/cameras_C2H_seat%s.json" % seat["name"]
    yaw = math.degrees(math.atan2(seat["look"][0] - seat["x"], seat["look"][2] - seat["z"]))
    d = dict(run_id=RID_C2H, date=now(), tool=TOOL, label=LABEL,
             source="seat = the Q86 seat table of h52b3_hero (read only); print = %s (C2H group %d)" % (rel(ctx.j("pv53_C2H")), ctx.print_group),
             seat=dict(plan=dict(x=seat["x"], y=seat["z"], lateral_abs=abs(seat["z"]), eye_above_heave_m=seat["eye"], cls=seat["cls"]),
                       unity=dict(manifest=dict(seat_x=seat["x"], seat_z=seat["z"], seat_eye_m=seat["eye"]), seatLookAt=seat["look"], seatFovV=seat["fov_v"],
                                  yaw_deg=round(yaw, 2))),
             print=dict(group=ctx.print_group, frame=P["print_frame"], rule=P["rule"], unity=dict(printPos=P["print_pose"]["pos"],
                                                                                                printLookAt=P["print_pose"]["look"], printFovV=P["print_pose"]["fov_v"]),
                        notes=P["print_pose"].get("notes")),
             front=P["front_pose"], move=mv, honesty_en=honesty(ctx), tags="[chosen] seat, FOV, move; [computed] print pose")
    jdump(d, p)
    return p


def cmd_clip(o):
    ctx = Ctx(o)
    t0 = time.time()
    S = stitch_mod()
    v = jload(ctx.stitch + "/stitch_verify.json") or {}
    if not ctx.sim and not v.get("ok"):
        return final(dict(ok=False, step="clip", why="stitch verify not ok (%s)" % rel(ctx.stitch + "/stitch_verify.json")))
    seat = ctx.seat()
    P = pv(ctx)
    cues = (jload(ctx.j("cues")) or {}).get("cues") or []
    mv = move_sched(ctx)
    cams = cams_json(ctx)
    out = ctx.clip()
    guard(out + "/manifest.json")
    rec = [f for f in range(ctx.f0, ctx.f1 + 1) if os.path.exists(ctx.stitch + "/surf/s_%05d.gw45s" % f)]
    if not ctx.sim and rec != list(range(F0, F1 + 1)):
        return final(dict(ok=False, step="clip", why="stitched records missing (%d of %d)" % (len(rec), F1 - F0 + 1)))
    info = {}
    for f in rec:
        b = open(ctx.stitch + "/surf/s_%05d.gw45s" % f, "rb").read()
        magic, ver, hb, t, fr, nv, nt = __import__("struct").unpack_from("<8sIIdiII", b, 0)
        if fr != f or abs(t - t_of(f)) > 1e-6:
            return final(dict(ok=False, step="clip", why="record head frame/time differs from the name at %d" % f))
        info[f] = dict(bytes=len(b), sha=hashlib.sha256(b).hexdigest(), nv=nv, nt=nt, t=t)
    man = jload(TEMPLATE_CLIP + "/manifest.json")
    shutil.copyfile(TEMPLATE_CLIP + "/bed.f32", out + "/bed.f32")
    hv, HF, xs, zs = heave_of(ctx, seat, list(range(rec[0], rec[-1] + 1)))
    best = {int(g["n"]): g["best"] for g in P["groups"]}
    cue = {int(c["k"]): c for c in cues}
    brk = []
    for n in sorted(best):
        b = best[n]
        c = cue.get(n) or {}
        if not b.get("frame") or not (rec[0] <= b["frame"] <= rec[-1]):
            continue
        brk.append(dict(k=n, frame=int(b["frame"]), t=t_of(b["frame"]), score3=float(b["score3"]), win_first=int(c.get("win_first") or b["frame"]),
                        win_last=int(c.get("win_last") or b["frame"]), hood=float(b.get("hood") or 0.0), lip=float(b.get("lip") or 0.0),
                        frame_bestframes=int(b["frame"]), t_bestframes=t_of(b["frame"]), record_offset_frames=0, xc_bestframes=float(b.get("x_c") or 0.0),
                        eta_c_bestframes=float(b.get("eta_c") or 0.0)))
    pf = int(P["print_frame"])
    e = HF.get(pf)
    i = int(np.nanargmax(e[0]))
    pb = best.get(ctx.print_group) or {}
    sd = ctx.stitch + "/surf"
    man.update(format="GW45LIST1", version=1, clip_kind="continuous", clip_file="", clip_bytes=int(sum(info[f]["bytes"] for f in rec)), clip_sha256="",
               frames=len(rec), t_first=info[rec[0]]["t"], t_last=info[rec[-1]]["t"], frame_first=rec[0], frame_last=rec[-1],
               loop_seconds=len(rec) / FPS, loop_start_s=info[rec[0]]["t"], loop_end_s=info[rec[0]]["t"] + len(rec) / FPS,
               play_from_s=t_of(rec[0]), play_to_s=round(t_of(rec[-1]) + 1.0 / FPS, 3),
               vert_max=int(max(info[f]["nv"] for f in rec)), tri_max=int(max(info[f]["nt"] for f in rec)),
               vert_min=int(min(info[f]["nv"] for f in rec)), tri_min=int(min(info[f]["nt"] for f in rec)),
               source_frames=rec, source_bytes=[info[f]["bytes"] for f in rec], source_sha256=[info[f]["sha"] for f in rec],
               source_list_sha256=hashlib.sha256("".join(info[f]["sha"] for f in rec).encode("ascii")).hexdigest(),
               stream_dir=sd, stream_dir_rel=os.path.relpath(sd, out).replace("\\", "/"), stream_pattern="s_{0:D5}.gw45s", repeat=1,
               breakers=brk, breakers_source=("C2H's own pv53 print-like instants (score3 on its centre section r2, the PARENT's judge periods: %s) and "
                                              "cues (onset = the parent's judge, touchdown = C2H's r2: %s)" % (rel(ctx.j("pv53_C2H")), rel(ctx.j("cues")))),
               breaker_k=ctx.print_group, print_record_frame=pf, print_record_t=t_of(pf), print_record_index=rec.index(pf) if pf in rec else 0,
               print_bestframes_frame=pf, print_bestframes_t=t_of(pf), print_score3=float(pb.get("score3") or 0.0), print_crest_x=float(xs[i]),
               print_crest_eta=float(e[0, i]), record_fps=FPS, sim_fps=FPS, record_step_frames=1, still_offset_m=STILL,
               bed_sha256=sha(out + "/bed.f32"),
               seat_x=seat["x"], seat_z=seat["z"], seat_eye_m=seat["eye"], heave_fps=FPS, heave=[round(float(x), 4) for x in hv],
               heave_min_m=float(hv.min()), heave_max_m=float(hv.max()), heave_source=rel(ctx.rd) + " hf (the seat lies inside the nest region)",
               source_run=rel(ctx.rd), run_id=SHORT + "_" + RID_C2H,
               cam_seat_look_at=[float(x) for x in seat["look"]], cam_seat_fov_v=float(seat["fov_v"]), cam_print_pos=[float(x) for x in P["print_pose"]["pos"]],
               cam_print_look_at=[float(x) for x in P["print_pose"]["look"]], cam_print_fov_v=float(P["print_pose"]["fov_v"]), cam_source_file=rel(cams),
               cam_source_sha256=sha(cams), cam_source_run=RID_C2H,
               cam_note_ja=("座席は Q86 の座席 %s（seat_x %.0f・seat_z %.0f・目 %.2f m と heave）【選び】。原画の視点は C2H の %d 組目の pv53 の方案 D（Hc で拡大、親の判定の組）【計算】（%s）"
                            % (seat["name"], seat["x"], seat["z"], seat["eye"], ctx.print_group, rel(cams))),
               water_double_sided=True,
               water_double_sided_ja="表示だけ：水を両面で描く（記録・計算・形は変えない。穴を埋めたのではない）",
               created=now(), tool=TOOL,
               playback_ja="面の記録は 24 個/s（毎コマ、つないだ面）。Unity は記録の範囲を続けて 1 回、実時間の時計で、その時刻以前の最後の記録を見せる。コマの間の形は作らない（GW45LIST1）",
               unity_notes_ja=("座席・原画の視点の値は manifest の cam_* を使う。視点の動きは -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g"
                               "（C2H の %d 組目の原画に最も近い瞬間 %.3f s に着く。白い画面は使わない）。VR では -f3dnocrestalign も付ける"
                               % (mv["frame"], mv["move"], mv["hold"], mv["stay"], mv["back"], ctx.print_group, t_of(mv["frame"]))),
               hero_status_ja=("主役（Q90）：0.25 m の入れ子 C2H（親 DFG-2B-V、決まりの上は有効）の面を入れ子の箱の中に、外は親の毎コマの面（0.5 m）を置き、継ぎ目で表示だけつないだ。"
                               + LABEL_JA + "。エネルギー：a² の和は DM1A と同じ（スペクトル）、水槽の中の力は DM1A の 0.23 倍"),
               stitch=dict(tool=rel(S.__file__), tool_sha256=sha(S.__file__), seam=S.SEAM, rule=S.STITCH_RULE, parent_run=rel(PARENT_RUN), nest_run=rel(ctx.rd),
                           verify=rel(ctx.stitch + "/stitch_verify.json"), verify_sha256=sha(ctx.stitch + "/stitch_verify.json"),
                           seam_rms_m=v.get("seam_rms_m"), seam_max_abs_m=v.get("seam_max_abs_m"),
                           open_visible_seam_len_max_m=v.get("open_visible_seam_len_max_m"), display=S.DISPLAY_EN),
               hero=dict(name="C2H (0.25 m nest of DFG-2B-V, stitched)", switched=True, switch_rule="Q90 (the user's words): %s" % "把 0.25 m 局部加密继续算到第 2、3 组，并和外面的水面拼接，做成主角。",
                         label=LABEL, run=rel(ctx.rd), seat=seat, print=dict(P["print_pose"], group=ctx.print_group, frame=pf), move=mv, cues=cues,
                         identity=identity_line(), tool=TOOL,
                         vr_command_hint=("FLIP3D player: -f3ddata %s -f3dtiles 0 -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g -f3dnocrestalign"
                                          % (out, mv["frame"], mv["move"], mv["hold"], mv["stay"], mv["back"]))),
               notes_en=honesty(ctx), label=LABEL, label_ja=LABEL_JA)
    jdump(man, out + "/manifest.json")
    ck = dict(records=len(rec), heave=[float(hv.min()), float(hv.max())], vert_max=man["vert_max"], tri_max=man["tri_max"], print=pf, breakers=[(b["k"], b["frame"]) for b in brk],
              bed_same_as_template=bool(sha(out + "/bed.f32") == man.get("bed_sha256")), stream_dir_ok=os.path.isdir(sd), label=LABEL, date=now(),
              seconds=round(time.time() - t0, 1))
    jdump(ck, out + "/check.json")
    return final(dict(ok=True, step="clip", clip=rel(out), records=len(rec), vert_max=man["vert_max"], tri_max=man["tri_max"], print_frame=pf,
                      move=mv, heave=ck["heave"], simulate=ctx.sim))


# ====================================================================== Unity
def commit_free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9


def capture_args(clip, cap, mv, jobs="cseat,cprint,cmove"):
    return ("-f3dcap %s -f3dsize 1920x1080 -f3dfps 24 -f3dtiles 0 -f3dsha -f3ddata %s -f3dfrom %.4f -f3dto %.4f -f3dmoves f%d -f3dmovesec %g "
            "-f3dhold %g -f3dstay %g -f3dback %g -f3dout %s" % (jobs, clip, t_of(F0), t_of(F1) + 1.0 / FPS, mv["frame"], mv["move"], mv["hold"],
                                                               mv["stay"], mv["back"], cap))


def git_status():
    return subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-uno"], capture_output=True, text=True, encoding="utf8").stdout


def unity_batch(extra, log, bdir_root, timeout_min=90, lockwait=40):
    free = commit_free_gb()
    if free < COMMIT_MIN_GB:
        return dict(rc=None, skipped="commit free %.2f GB < %.1f GB" % (free, COMMIT_MIN_GB), ok=False)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = bdir_root + "/_unity_backup/" + stamp
    before = {}
    for r in TRACKED:
        dst = guard(bdir + "/" + r.replace("/", "__"))
        shutil.copyfile(REPO + "/" + r, dst)
        before[r] = sha(REPO + "/" + r)
        if sha(dst) != before[r]:
            raise SystemExit("backup copy differs: %s" % r)
    st0 = git_status()
    jdump(dict(files=before, git_status_uno=st0, date=now()), bdir + "/pre_batch.json")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UNITY_PS1, "-Method", UNITY_METHOD, "-Log", log, "-Extra", extra,
           "-TimeoutMinutes", str(timeout_min), "-LockWaitMinutes", str(lockwait)]
    t0 = time.time()
    out, rc = "", -1
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO)
        out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
    finally:
        restored = {}
        for rr in TRACKED:
            dst = REPO + "/" + rr
            if not os.path.exists(dst) or sha(dst) != before[rr]:
                shutil.copyfile(bdir + "/" + rr.replace("/", "__"), dst)
            restored[rr] = sha(dst) == before[rr]
    line = [l for l in out.splitlines() if l.startswith("FLIP3D_UNITY ")]
    return dict(rc=rc, seconds=round(time.time() - t0, 1), unity_line=line[-1] if line else None, all_restored=all(restored.values()),
                git_status_same=st0 == git_status(), backup=rel(bdir), tail=out[-1500:], commit_free_gb_before=round(free, 2),
                lock_released=not os.path.exists(REPO + "/Unity/Build/unity.lock"), ok=bool(rc == 0 and all(restored.values())), extra=extra, log=log)


def cmd_unity(o):
    ctx = Ctx(o)
    seat = ctx.seat()
    mv = move_sched(ctx)
    clip, cap = ctx.clip(), ctx.cap()
    extra = capture_args(clip, cap, mv, o.get("jobs", "cseat,cprint,cmove"))
    log = "heroC2H_%s_seat%s" % (SHORT, seat["name"])
    if "dry" in o or ctx.sim:
        return final(dict(ok=True, step="unity", dry=True, method=UNITY_METHOD, extra=extra, log=log, commit_free_gb=round(commit_free_gb(), 2),
                          need_gb=COMMIT_MIN_GB, unity_lock=os.path.exists(REPO + "/Unity/Build/unity.lock"), clip_exists=os.path.exists(clip + "/manifest.json")))
    if not os.path.exists(clip + "/manifest.json"):
        return final(dict(ok=False, step="unity", why="no clip %s: run `clip` first" % rel(clip)))
    res = unity_batch(extra, log, HERO_DIR)
    res.update(date=now(), tool=TOOL, step="unity", label=LABEL)
    jdump(res, ctx.j("unity_seat%s" % seat["name"]))
    return final(dict({k: res.get(k) for k in ("ok", "rc", "seconds", "unity_line", "all_restored", "git_status_same", "skipped", "lock_released")}, step="unity"))


def cmd_capcheck(o):
    ctx = Ctx(o)
    H = hm()
    seat = ctx.seat()
    mv = move_sched(ctx)
    clip, cap = ctx.clip(), ctx.cap()
    man = jload(clip + "/manifest.json") or {}
    sd = man.get("stream_dir") or (ctx.stitch + "/surf")
    ff = int(man.get("frame_first") or F0)
    out, memo = {}, {}

    def surf(f):
        if f not in memo:
            memo.clear()
            memo[f] = H.surf_points(sd + "/s_%05d.gw45s" % f)
        return memo[f]
    from PIL import Image
    for mode in ("cseat", "cprint", "cmove"):
        d = cap + "/" + mode
        if not os.path.exists(d + "/frames.csv"):
            out[mode] = dict(missing=True); continue
        rows = list(csv.DictReader(open(d + "/frames.csv", encoding="utf8")))
        cj = jload(d + "/capture.json") or {}
        recs = np.array([int(r["record"]) for r in rows]); sf = np.array([int(r["sim_frame"]) for r in rows])
        st = np.array([float(r["sim_t"]) for r in rows]); fr = np.array([int(r["frozen"]) for r in rows]); bl = np.array([float(r["blend"]) for r in rows])
        pos = np.array([[float(r["cx"]), float(r["cy"]), float(r["cz"])] for r in rows])
        dd = np.diff(recs)
        oo = dict(frames=len(rows), sim_frame_eq_first_plus_record=bool((sf == ff + recs).all()), back_steps=int((dd < 0).sum()),
                  skipped_records=int((dd > 1).sum()), frozen_frames=int(fr.sum()), schedule=cj.get("schedule"), moves=cj.get("moves"),
                  streaming=cj.get("streaming"), water_double_sided=cj.get("waterDoubleSided"))
        sel = range(len(rows)) if mode != "cmove" else np.where(bl > 0)[0]
        cl, mk = [], {}
        for i in sel:
            key = (int(sf[i]), round(pos[i, 0], 3), round(pos[i, 1], 3), round(pos[i, 2], 3))
            if key not in mk:
                P_, T_, _, _ = surf(int(sf[i]))
                ys = H.column(P_, T_, pos[i, 0], abs(pos[i, 2]))
                mk[key] = pos[i, 1] - float(ys.max()) if len(ys) else np.inf
            cl.append(mk[key])
        cl = np.array(cl) if cl else np.array([np.inf])
        idx = list(sel)
        oo.update(cam_col_clearance_min_m=float(cl.min()) if np.isfinite(cl.min()) else None,
                  cam_col_clearance_min_sim_frame=int(sf[idx[int(cl.argmin())]]) if idx else None,
                  frames_col_clear_lt1=H.ranges([(int(sf[idx[k]]), round(float(v), 3)) for k, v in enumerate(cl) if v < CLEAR_MIN]))
        if mode == "cmove":
            one = np.where(bl >= 0.99995)[0]
            if len(one):
                oo["arrive"] = dict(sim_frame=int(sf[one[0]]), sim_t=float(st[one[0]]), record=int(recs[one[0]]), frozen=int(fr[one[0]]))
            oo["arrive_ok"] = bool((oo.get("arrive") or {}).get("sim_frame") == mv["frame"])
            oo["max_cam_step_m"] = float(np.linalg.norm(np.diff(pos, axis=0), axis=1).max()) if len(pos) > 1 else 0.0
        lum, white = [], []
        for i in range(len(rows)):
            im = Image.open(d + "/frame_%05d.jpg" % i)
            im.draft("L", (240, 135))
            q = np.asarray(im.convert("L"), np.float32)
            lum.append(q.mean()); white.append((q > 240).mean())
        oo.update(lum_min_max=[float(min(lum)), float(max(lum))], white_frac_max=float(max(white)), white_out=bool(max(white) > 0.5))
        out[mode] = oo
    m = out.get("cmove") or {}
    out["ok"] = bool(all((out.get(k) or {}).get("sim_frame_eq_first_plus_record") for k in ("cseat", "cprint", "cmove"))
                     and all((out.get(k) or {}).get("skipped_records", 1) == 0 and (out.get(k) or {}).get("back_steps", 1) == 0 for k in ("cseat", "cprint", "cmove"))
                     and m.get("frozen_frames") == int(mv["hold"] * FPS) and m.get("arrive_ok") is True
                     and not any((out.get(k) or {}).get("white_out") for k in ("cseat", "cprint", "cmove"))
                     and ((out.get("cseat") or {}).get("cam_col_clearance_min_m") or 0) >= CLEAR_MIN)
    out.update(honesty_en=honesty(ctx), date=now(), tool=TOOL, step="capcheck", move=mv, seat=seat, label=LABEL)
    jdump(out, ctx.j("capcheck_seat%s" % seat["name"]))
    jdump(out, cap + "/hero_capcheck.json")
    return final(dict(ok=out["ok"], step="capcheck", **{k: {kk: (out.get(k) or {}).get(kk) for kk in ("frames", "skipped_records", "frozen_frames",
                                                                                                       "cam_col_clearance_min_m", "white_frac_max", "arrive")}
                                                         for k in ("cseat", "cprint", "cmove")}))


# ====================================================================== videos (unchanged compose_cont_exact + in-memory caption lines)
def cmd_video(o):
    ctx = Ctx(o)
    seat = ctx.seat()
    import f3d50_video_loop as FL
    V, V5 = FL.V, FL.V5
    V5.RUN_TEXT = dict(V5.RUN_TEXT)
    V5.RUN_TEXT[SHORT] = ("%s：0.25 m の入れ子 C2H（親 DFG-2B-V）を 2・3 組目まで計算し、外の水面（DFG-2B-V 0.5 m）と表示だけつないだ主役（Q90）。規則の外の試算"
                          % SHORT)
    L = honesty(ctx)
    V.HEROV_L4, V.HEROV_L5, V.HEROV_L6, V.HEROV_L7 = L
    band_old = "        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))\n"
    band_new = "        dr.rectangle([0, 0, W, 222], fill=(0, 0, 0, 150))\n"
    l3_old = "        dr.text((18, 74), line3, font=_fit(line3, 19, W - 36), fill=(225, 225, 225))\n"
    l3_new = l3_old + "".join("        dr.text((18, %d), HEROV_L%d, font=_fit(HEROV_L%d, 19, W - 36), fill=(255, 200, 140))\n" % (102 + 28 * i, 4 + i, 4 + i)
                              for i in range(4))
    FL.FIT_LINES = tuple(FL.FIT_LINES) + ((band_old, band_new), (l3_old, l3_new))
    cap_name = os.path.basename(ctx.cap())
    names = [n for n in ("cseat", "cprint", "cmove") if os.path.exists(ctx.cap() + "/" + n + "/frames.csv")]
    if "dry" in o or ctx.sim or not names:
        import inspect
        s = inspect.getsource(V.compose_cont)
        if s.count(FL.OLD_MOVE) != 1:
            return final(dict(ok=False, step="video", why="move caption not found once"))
        s = s.replace(FL.OLD_MOVE, FL.NEW_MOVE)
        for old, new in FL.FIT_LINES:
            if s.count(old) != 1:
                return final(dict(ok=False, step="video", why="caption line not found exactly once: " + old[:60]))
            s = s.replace(old, new)
        for old in (V5.OLD_TITLE, V5.OLD_LINE2, V5.OLD_LINE3):
            if s.count(old) != 1:
                return final(dict(ok=False, step="video", why="f3d50_video caption not found once: " + old[:40]))
        compile(s, "patched compose_cont", "exec")
        return final(dict(ok=True, step="video", dry=True, lines=L, captures_present=names,
                          videos_would_be=[VID + "/FLIP3D_%s_%s.mp4" % (cap_name[len("capture_"):], n) for n in ("cseat", "cprint", "cmove")]))
    for n in names:
        guard(VID + "/FLIP3D_%s_%s.mp4" % (cap_name[len("capture_"):], n))
    fn = FL.compose_cont_exact(cap_name, names)
    res = [fn(nm, cap_name) for nm in names]
    r = dict(date=now(), tool=TOOL, step="video", videos=res, lines=L, label=LABEL)
    jdump(r, ctx.j("video_seat%s" % seat["name"]))
    return final(dict(ok=True, step="video", videos=[(x["name"], x["mp4"], x["frames"], x["bytes"]) for x in res]))


# ====================================================================== views3 (front / top / print view / print)
V3_W, V3_H = 1920, 1080
V3_HEAD, V3_FOOT, V3_GAP = 96, 58, 6
V3_PH = (V3_H - V3_HEAD - V3_FOOT - V3_GAP) // 2
V3_PW = int(round(V3_PH * 16 / 9))
V3_X0 = (V3_W - 2 * V3_PW - V3_GAP) // 2
V3_POS = dict(front=(V3_X0, V3_HEAD), top=(V3_X0 + V3_PW + V3_GAP, V3_HEAD), printview=(V3_X0, V3_HEAD + V3_PH + V3_GAP),
              print=(V3_X0 + V3_PW + V3_GAP, V3_HEAD + V3_PH + V3_GAP))
V3_LABEL = dict(front="① 正面视角（岸侧看向来浪，静止相机，pv53 的正面相机）", top="② 上方视角（俯视；右＝岸；显示对比度×2.5）",
                printview="③ 原画视角（Unity 渲染，主役的 cprint）", print="④ 原画（北斋《神奈川冲浪里》，Met JP1847）")
V3_TOPK, V3_TOPLM = 2.5, 77.0                                  # = views3 [chosen there]
_F = {}


def fnt(sz, b=False):
    from PIL import ImageFont
    k = (sz, b)
    if k not in _F:
        name = "C:/Windows/Fonts/msyhbd.ttc" if b and os.path.exists("C:/Windows/Fonts/msyhbd.ttc") else "C:/Windows/Fonts/msyh.ttc"
        try:
            _F[k] = ImageFont.truetype(name, sz)
        except Exception:
            _F[k] = ImageFont.load_default()
    return _F[k]


def v3_views(ctx):
    return dict(front=V3_CAP + "/cseat", top=V3_CAP + "/cprint", printview=ctx.cap() + "/cprint")


def v3_marks(ctx):
    P = pv(ctx)
    return [(g["n"], g["best"]["frame"], g["best"]["score3"]) for g in P["groups"] if g.get("best") and g["best"].get("frame")]


def cmd_views3(o, sub):
    ctx = Ctx(o)
    if sub == "clip":
        src = ctx.clip()
        man = jload(src + "/manifest.json")
        if not man:
            return final(dict(ok=False, step="views3 clip", why="no hero clip %s" % rel(src)))
        P = pv(ctx)
        fc = P["front_pose"]
        m = dict(man)
        n_heave = len(m.get("heave") or [0.0, 0.0])
        m.update(seat_x=float(fc["pos"][0]), seat_z=0.0, seat_eye_m=float(fc["pos"][1] - STILL), cam_seat_look_at=[float(v) for v in fc["look"]],
                 cam_seat_fov_v=float(fc["fov_v"]), heave=[0.0] * n_heave, heave_min_m=0.0, heave_max_m=0.0,
                 heave_note="views3: static cameras (heave 0); the seat fields hold the FRONT view, the print fields hold the TOP view",
                 cam_print_pos=TOP_POS, cam_print_look_at=TOP_LOOK, cam_print_fov_v=TOP_FOV,
                 stream_dir_rel=os.path.relpath(m["stream_dir"], V3_CLIP).replace("\\", "/"),
                 views3=dict(tool=TOOL, source_clip=rel(src), date=now(), label=LABEL,
                             job_cseat="FRONT (pv53 front camera of C2H group %d: %s -> %s, fov_v %s)" % (ctx.print_group, fc["pos"], fc["look"], fc["fov_v"]),
                             job_cprint="TOP %s -> %s, fov_v %s (NOT the print view)" % (TOP_POS, TOP_LOOK, TOP_FOV),
                             print_view="the hero capture %s/cprint" % rel(ctx.cap())))
        if "dry" in o or ctx.sim:
            return final(dict(ok=True, step="views3 clip", dry=True, would_write=rel(V3_CLIP), front=fc, top=[TOP_POS, TOP_LOOK, TOP_FOV]))
        jdump(m, V3_CLIP + "/manifest.json")
        shutil.copyfile(src + "/bed.f32", guard(V3_CLIP + "/bed.f32"))
        return final(dict(ok=bool(sha(V3_CLIP + "/bed.f32") == m["bed_sha256"]), step="views3 clip", clip=rel(V3_CLIP)))
    if sub == "unity":
        mv = move_sched(ctx)
        extra = capture_args(V3_CLIP, V3_CAP, mv, "cseat,cprint")
        if "dry" in o or ctx.sim:
            return final(dict(ok=True, step="views3 unity", dry=True, extra=extra))
        if not os.path.exists(V3_CLIP + "/manifest.json"):
            return final(dict(ok=False, step="views3 unity", why="no views3 clip: run `views3 clip` first"))
        res = unity_batch(extra, "views3_%s" % SHORT, HERO_DIR, timeout_min=60, lockwait=40)
        res.update(date=now(), tool=TOOL, step="views3 unity", label=LABEL)
        jdump(res, ctx.j("views3_unity"))
        return final(dict({k: res.get(k) for k in ("ok", "rc", "seconds", "unity_line", "all_restored", "skipped")}, step="views3 unity"))
    if sub == "compose":
        return v3_compose(ctx, o)
    return final(dict(ok=False, step="views3", why="views3 clip|unity|compose"))


def v3_rows(path):
    r = list(csv.DictReader(open(path + "/frames.csv", encoding="utf-8")))
    return {int(x["sim_frame"]): (path + "/frame_%05d.jpg" % int(x["i"]), float(x["sim_t"])) for x in r}


_V3 = {}


def v3_init(views, marks, lines, short_title):
    global _V3
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass
    from PIL import Image
    _V3 = dict(maps={v: v3_rows(p) for v, p in views.items()}, marks=marks, lines=lines, title=short_title)
    im = Image.open(PRINT_IMG).convert("RGB")
    strip = 44
    s = min(V3_PW / im.width, (V3_PH - strip) / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    bg = Image.new("RGB", (V3_PW, V3_PH), (12, 12, 12))
    bg.paste(im, ((V3_PW - im.width) // 2, strip + (V3_PH - strip - im.height) // 2))
    _V3["pp"] = bg


def v3_enh(im):
    from PIL import Image
    a = np.asarray(im).astype(np.float32)
    L = a @ np.array([0.299, 0.587, 0.114], np.float32) + 1e-3
    r = np.clip((V3_TOPLM + V3_TOPK * (L - V3_TOPLM)) / L, 0.3, 2.0)
    return Image.fromarray(np.clip(a * r[..., None], 0, 255).astype(np.uint8))


def v3_tag(dr, xy, text, sz=22):
    f = fnt(sz)
    x, y = xy
    b = dr.textbbox((x + 8, y + 4), text, font=f)
    dr.rectangle((x, y, b[2] + 8, b[3] + 6), fill=(0, 0, 0, 150))
    dr.text((x + 8, y + 4), text, font=f, fill=(255, 255, 255, 255))


def v3_near(f, win=12):
    for g, mf, s in _V3["marks"]:
        if abs(f - mf) <= win:
            return g, mf, s
    return None


def v3_frame(f):
    from PIL import Image, ImageDraw
    M = _V3["maps"]
    imgs = {}
    for v in ("front", "top", "printview"):
        im = Image.open(M[v][f][0]).convert("RGB")
        imgs[v] = v3_enh(im) if v == "top" else im
    can = Image.new("RGB", (V3_W, V3_H), (0, 0, 0))
    for v in ("front", "top", "printview"):
        can.paste(imgs[v].resize((V3_PW, V3_PH), Image.BILINEAR), V3_POS[v])
    can.paste(_V3["pp"], V3_POS["print"])
    ov = Image.new("RGBA", (V3_W, V3_H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for v in ("front", "top", "printview", "print"):
        v3_tag(dr, (V3_POS[v][0] + 6, V3_POS[v][1] + 6), V3_LABEL[v])
    nm = v3_near(f, 0)
    if nm:
        for v in ("front", "top", "printview"):
            x, y = V3_POS[v]
            dr.rectangle((x, y, x + V3_PW - 1, y + V3_PH - 1), outline=(255, 210, 0, 255), width=4)
    can.paste(ov, (0, 0), ov)
    dr = ImageDraw.Draw(can)
    dr.rectangle((0, 0, V3_W, V3_HEAD), fill=(0, 0, 0))
    dr.text((V3_X0, 4), "%s  模拟时间 %.2f s   帧 %d" % (_V3["title"], t_of(f) + 1e-9, f), font=fnt(28, True), fill=(255, 255, 255))
    sub = "★ 各浪群最像原画的瞬间（C2H 自身的 pv53）：" + "・".join("群%d 帧%d（%.2f s，score3 %.3f）" % (g, mf, t_of(mf), s) for g, mf, s in _V3["marks"])
    dr.text((V3_X0, 40), sub, font=fnt(16), fill=(200, 200, 200))
    dr.text((V3_X0, 64), _V3["lines"][0], font=fnt(17, True), fill=(255, 140, 120))
    tx0, tx1, ty = 1240, V3_W - V3_X0, 22
    dr.line((tx0, ty, tx1, ty), fill=(150, 150, 150), width=3)
    xf = lambda q: tx0 + (tx1 - tx0) * (q - F0) / (F1 - F0)
    for g, mf, s in _V3["marks"]:
        c = (255, 210, 0) if nm and nm[1] == mf else (200, 150, 0)
        dr.polygon([(xf(mf), ty + 4), (xf(mf) - 7, ty + 16), (xf(mf) + 7, ty + 16)], fill=c)
    dr.rectangle((xf(f) - 2, ty - 11, xf(f) + 2, ty + 11), fill=(255, 255, 255))
    y = V3_H - V3_FOOT + 4
    for ln in _V3["lines"][1:3]:
        dr.text((V3_X0, y), ln[:190], font=fnt(16), fill=(210, 210, 210))
        y += 24
    if len(_V3["lines"]) > 4 and _V3["lines"][4]:             # seat / print-pose failures (flags_line) on the print-view panel
        x, y = V3_POS["printview"]
        dr.text((x + 10, y + V3_PH - 30), _V3["lines"][4][:150], font=fnt(16, True), fill=(255, 90, 90))
    return can


def v3_work(args):
    f, fr_dir = args
    v3_frame(f).save(fr_dir + "/grid/f_%05d.jpg" % (f - F0), quality=92)
    return f


def v3_compose(ctx, o):
    t0 = time.time()
    views = v3_views(ctx)
    lines = honesty(ctx) + [flags_line(ctx)]
    marks = v3_marks(ctx)
    miss = {v: (not os.path.exists(p + "/frames.csv")) for v, p in views.items()}
    out_mp4 = VID + "/FLIP3D_C2H_stitch_views3_2x2_front_top_printview_print.mp4"
    if "dry" in o or ctx.sim or any(miss.values()):
        return final(dict(ok=not any(miss.values()) or "dry" in o or ctx.sim, step="views3 compose", dry=True, captures_missing=miss, would_write=rel(out_mp4),
                          marks=marks, layout=dict(W=V3_W, H=V3_H, PW=V3_PW, PH=V3_PH), lines=lines))
    maps = {v: v3_rows(p) for v, p in views.items()}
    frames = list(range(F0, F1 + 1))
    lack = {v: [f for f in frames if f not in maps[v]][:5] for v in maps}
    if any(lack.values()):
        return final(dict(ok=False, step="views3 compose", why="frames missing in a capture", lack=lack))
    fr_dir = guard(V3_FR + "/grid/x") and V3_FR
    os.makedirs(fr_dir + "/grid", exist_ok=True)
    from multiprocessing import Pool
    with Pool(int(o.get("workers", "6")), initializer=v3_init, initargs=(views, marks, lines, "C2H（0.25 m 入れ子＋DFG-2B-V 0.5 m、表示でつないだ主役）")) as p:
        for k, _ in enumerate(p.imap_unordered(v3_work, [(f, fr_dir) for f in frames], chunksize=8)):
            if k % 400 == 0:
                print(now(), "views3 frames", k, flush=True)
    guard(out_mp4)
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", fr_dir + "/grid/f_%05d.jpg", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "20", out_mp4], capture_output=True, text=True)
    # the still sheet at the marks
    from PIL import Image
    v3_init(views, marks, lines, "C2H")
    sheet = VID + "/FLIP3D_C2H_stitch_views3_sheet_%s.jpg" % "_".join("f%d" % mf for _, mf, _ in marks)
    ims = [v3_frame(mf).resize((960, 540), Image.LANCZOS) for _, mf, _ in marks]
    S = Image.new("RGB", (960 * max(1, len(ims)), 540), (0, 0, 0))
    for i, im in enumerate(ims):
        S.paste(im, (960 * i, 0))
    S.save(guard(sheet), quality=90)
    res = dict(date=now(), tool=TOOL, step="views3 compose", mp4=rel(out_mp4), mp4_ok=bool(r.returncode == 0 and os.path.exists(out_mp4)), sheet=rel(sheet),
               frames=len(frames), marks=marks, lines=lines, label=LABEL, seconds=round(time.time() - t0, 1), ffmpeg_err=r.stderr[-400:])
    jdump(res, ctx.j("views3_compose"))
    return final(dict(ok=res["mp4_ok"], step="views3 compose", mp4=res["mp4"], sheet=res["sheet"], seconds=res["seconds"]))


# ====================================================================== contact sheet
def cmd_sheet(o):
    ctx = Ctx(o)
    seat = ctx.seat()
    H = hm()
    from PIL import Image, ImageDraw
    P = pv(ctx)
    frames = [g["best"]["frame"] for g in P["groups"] if g.get("best") and g["best"].get("frame")]
    idx = {}
    for mode in ("cseat", "cprint"):
        p = ctx.cap() + "/" + mode + "/frames.csv"
        if not os.path.exists(p):
            return final(dict(ok=False, step="sheet", why="no capture %s: run `unity` first" % rel(p)))
        idx[mode] = {}
        for r in csv.DictReader(open(p, encoding="utf8")):
            idx[mode].setdefault(int(r["sim_frame"]), r)
    CW, CH, COLS = 640, 360, max(3, len(frames))
    lines = ["C2H hero (Q90): seat %s (top) and the print view (bottom) at each group's most print-like instant (C2H's own pv53)" % seat["name"]] + honesty(ctx)
    rows_h = []
    for i, l in enumerate(lines):
        f_ = fnt(30 if i else 34)
        for j, piece in enumerate(H.wrap_px(l, f_, CW * COLS - 68)):
            rows_h.append((("    " if j else "") + piece, f_, (255, 255, 255) if i == 0 else ((255, 140, 120) if i == 1 else (255, 200, 140))))
    TOP = 16 + 44 * len(rows_h)
    pvp = None
    pj = jload(PV53_JSON_C2H) or {}
    if pj.get("report_png") and os.path.exists(pj["report_png"]):
        pvp = Image.open(pj["report_png"]).convert("RGB")
    pvh = int(pvp.height * (CW * COLS) / pvp.width) if pvp else 0
    S = Image.new("RGB", (CW * COLS, TOP + 2 * CH + pvh + (44 if pvp else 0)), (0, 0, 0))
    dr = ImageDraw.Draw(S)
    for i, (l, f_, col) in enumerate(rows_h):
        dr.text((14, 8 + 44 * i), l, font=f_, fill=col)
    best = {g["best"]["frame"]: g for g in P["groups"] if g.get("best")}
    for j, f in enumerate(frames[:COLS]):
        for m, (mode, name) in enumerate((("cseat", "seat %s" % seat["name"]), ("cprint", "print view"))):
            r = idx[mode].get(f)
            x, y = j * CW, TOP + m * CH
            if r is None:
                dr.text((x + 10, y + 10), "frame %d not captured" % f, font=fnt(18), fill=(255, 120, 120)); continue
            im = Image.open(ctx.cap() + "/" + mode + "/frame_%05d.jpg" % int(r["i"])).convert("RGB").resize((CW, CH), Image.LANCZOS)
            S.paste(im, (x, y))
            g = best.get(f) or {}
            dr.rectangle([x, y, x + CW, y + 52], fill=(0, 0, 0))
            dr.text((x + 6, y + 2), "%s  %.3f s (frame %d)" % (name, t_of(f), f), font=fnt(20), fill=(255, 230, 120) if m == 0 else (160, 220, 255))
            dr.text((x + 6, y + 26), "group %s most print-like (score3 %.3f)" % (g.get("n"), (g.get("best") or {}).get("score3") or 0.0), font=fnt(18),
                    fill=(255, 230, 120) if m == 0 else (160, 220, 255))
    if pvp:
        y = TOP + 2 * CH
        dr.text((14, y + 6), "pv53 of C2H (nest records, the parent's judge periods): print view | the print | section vs the print outline + ruler",
                font=fnt(28), fill=(200, 255, 200))
        S.paste(pvp.resize((CW * COLS, pvh), Image.LANCZOS), (0, y + 44))
    out = guard(VID + "/FLIP3D_C2H_stitch_f%d_%d_r24_seat%s_ds_sheet_seat_print.jpg" % (F0, F1, seat["name"]))
    S.save(out, quality=90)
    shutil.copyfile(out, guard(HERO_DIR + "/" + os.path.basename(out)))
    return final(dict(ok=True, step="sheet", sheet=rel(out), frames=frames, size=S.size))


# ====================================================================== status / selftest
def cmd_status(o):
    ctx = Ctx(o)
    have = {k: os.path.exists(ctx.j(k)) for k in ("pv53_C2H", "cues", "seatcheck", "stay", "movepath")}
    return final(dict(ok=True, step="status", run=rel(ctx.rd), have=have, clip=os.path.exists(ctx.clip("A") + "/manifest.json"),
                      capture=os.path.exists(ctx.cap("A") + "/cmove/frames.csv"), views3=os.path.exists(V3_CAP + "/cseat/frames.csv"),
                      hm_sha256=sha(HM_PATH), tool_sha256=sha(os.path.abspath(__file__))))


def selftest(o):
    ck, info = {}, {}
    H = hm()
    ck["hm_seats"] = bool(H.SEATS["A"]["x"] == 284.0 and H.SEATS["A"]["z"] == -20.0 and H.SEATS["A"]["eye"] == 1.5)
    ck["template_clip"] = bool(os.path.exists(TEMPLATE_CLIP + "/manifest.json") and os.path.exists(TEMPLATE_CLIP + "/bed.f32"))
    ck["parent_judges"] = bool(os.path.exists(JUDGE52) and os.path.exists(JUDGEV))
    ck["parent_hf_every_frame"] = True
    import f3d_common as C
    Hp = C.Rec("hf", PARENT_RUN)
    ck["parent_hf_every_frame"] = bool(all(f in Hp.where for f in range(F0, F1 + 1)))
    ck["print_img"] = os.path.exists(PRINT_IMG)
    ck["ffmpeg"] = os.path.exists(FFMPEG)
    ck["unity_ps1"] = os.path.exists(UNITY_PS1)
    ck["no_space_in_paths"] = bool(" " not in OUT3D + "/" + CLIP_NAME % "A" and " " not in V3_CLIP)
    mv = dict(frame=2156, move=6.0, hold=2.0, stay=2.5, back=6.0)
    a = capture_args(OUT3D + "/" + CLIP_NAME % "A", OUT3D + "/" + CAP_NAME % "A", mv)
    ck["capture_args_like_hero"] = bool("-f3dcap cseat,cprint,cmove" in a and "-f3dfrom 48.0000" in a and "-f3dto 125.0417" in a and "-f3dmoves f2156" in a)
    info["capture_args_example"] = a
    try:
        protected = False
        guard(OUT3D + "/clip_DFGBVr_f1153_3001_r24_seatA_ds/manifest.json")
    except SystemExit:
        protected = True
    ck["guard_protects_dfgbv_hero"] = protected
    res = dict(ok=bool(all(ck.values())), step="selftest", checks=ck, info=info)
    return final(res)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    pos, o = opts(argv[1:])
    try:
        if cmd == "views3":
            return cmd_views3(o, pos[0] if pos else "")
        fn = dict(pv53=cmd_pv53, cues=cmd_cues, seatcheck=cmd_seatcheck, stay=cmd_stay, movepath=cmd_movepath, clip=cmd_clip, unity=cmd_unity,
                  capcheck=cmd_capcheck, video=cmd_video, sheet=cmd_sheet, status=cmd_status, selftest=selftest).get(cmd)
        if fn is None:
            print(__doc__)
            return 1
        return fn(o)
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            raise
        return final(dict(ok=False, step=cmd, why=str(e.code)[:600]))
    except Exception as e:
        import traceback
        return final(dict(ok=False, step=cmd, why="%s: %s" % (type(e).__name__, str(e)[:400]), traceback=traceback.format_exc()[-1500:]))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
