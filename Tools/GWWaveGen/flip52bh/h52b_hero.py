# -*- coding: utf-8 -*-
"""FLIP52B DFG-2B-E HERO (user Q85 2026-10-18 "DFG-2B 的效果更好"): after the every-frame re-record (h52b_long.py) - re-score, breaker cues,
seat clearance on every frame, the continuous Unity clip (designed seat + print cameras, water_double_sided), the Unity captures, capture
checks, captioned videos and a contact sheet (py -3.10 -B; numpy, scipy, PIL, ffmpeg; Unity batch only in `unity`). 2026-10-18 written new
(Claude subagent). No existing file is edited: f3d50_export.main_long, pv53.PVRun, f3d50_video_loop.compose_cont_exact and
FLIP3DBatch.BuildSceneAndCapture (through flip3d/f3d_unity.ps1) run unchanged; their outputs are patched afterwards (the h50_long /
pv53 make_clip / hero_video_relabel precedents). Run folders are read only.
Writes only: Unity/Build/FLIP52B/hero/ (json, cameras, unity backups, sheet), Unity/Build/FLIP3D/clip_<id>/ (GW45LIST1 manifest that STREAMS
the re-record's own surf files, no copy: that surf folder must stay), Unity/Build/FLIP3D/capture_<id>/ (Unity frames),
Unity/Build/FLIP3D/video/ (mp4 + sheets). All of Unity/Build is git-ignored.

Honesty (every manifest, caption line and sheet): DFG-2B-E is formally INVALID (G2f inlet 5.6 s phase 0.514 rad > 0.35; G6 group 1 peak
58.958 s, 0.042 s before 59.0 s); energy: sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A; physics only, 0.5 m Houdini FLIP; frames
1153-3001 re-recorded from checkpoint 1152 and bit-identical to the judged run (or the measured difference); no shapes between frames.

Hero design [chosen, the design step]: seat A (Unity seat_x 284, seat_z -20, eye 1.5 m, look (263.74, 6.04, 1.67), FOV 55); fallback seat B
(305, -32, 1.75, look (281.61, 3.65, -13.3)) if seat A comes within 1.0 m of the water on any frame; ONE visible move to group 2's most
print-like instant, frame 2149 (89.5 s): -f3dmoves f2149 -f3dmovesec 6 -f3dhold 2 -f3dstay 2.5 -f3dback 6 (no white-out); print pose = group 2's
own pv53 option-D pose (270.373, 4.001, -71.375) -> (265.995, 5.476, 0), FOV 23.5. VR also needs -f3dnocrestalign (crestAlign would shift
every pose by about -13 m); FLIP3DExperience would by default pick group 3, so f2149 is passed explicitly.

  py -3.10 -B h52b_hero.py rescore   <cfg> [--run <dir>] [--frames a-b,...]   pv53's D ruler on the re-record's r2, frames best +-12 per group
  py -3.10 -B h52b_hero.py cues      <cfg> [--run <dir>]                      onset (judge r2 lip) / touchdown (r2 enclosed cavity) per group
  py -3.10 -B h52b_hero.py seatcheck <cfg> [--run <dir>] [--seat A|B]          hf + surface meshes on every frame of the play range
  py -3.10 -B h52b_hero.py framing   <cfg>                                    print pose vs crest / lip of groups 1-3 (half-widths)
  py -3.10 -B h52b_hero.py cams      <cfg> [--seat A|B]                       cameras JSON (cameras_DM1A_seatA.json layout)
  py -3.10 -B h52b_hero.py export    <cfg> [--seat A|B] [--dry]               continuous clip (f3d50_export long) + manifest patch
  py -3.10 -B h52b_hero.py unity     <cfg> [--seat A|B] [--jobs cstills,cseat,cprint,cmove] [--dry]   memory check, backup, Unity, restore
  py -3.10 -B h52b_hero.py capcheck  <cfg> [--seat A|B]                       record order, schedule, camera clearance, white-out
  py -3.10 -B h52b_hero.py video     <cfg> [--seat A|B] [--dry]               captioned mp4s (every frame says INVALID + energy)
  py -3.10 -B h52b_hero.py sheet     <cfg> [--seat A|B]                       contact sheet: seat / print stills + the pv53 print-outline report
Tags: [measured] records / captures, [computed] derived here, [chosen] seat, poses, move seconds, rules.
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
if not (os.environ.get("G52B_SEA") or "").strip():
    os.environ["G52B_SEA"] = "E"
import sys, json, time, csv, io, glob, shutil, hashlib, subprocess, contextlib, ctypes, math, struct

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
for _p in (TOOLS + "/flip50g2", TOOLS + "/flip3d"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                       # noqa: E402

TOOL = "Tools/GWWaveGen/flip52bh/h52b_hero.py"
B52B = REPO + "/Unity/Build/FLIP52B"
SRC_RUN = "DFGB2E_D19B_xf272p25_dp0p5"
SRC_DIR = B52B + "/runs/" + SRC_RUN
HERO = B52B + "/hero"
OUT3D = REPO + "/Unity/Build/FLIP3D"
VID = OUT3D + "/video"
PV53_DIR = REPO + "/Unity/Build/FLIP53/pv53/" + SRC_RUN
PV53_JSON = PV53_DIR + "/pv53_%s.json" % SRC_RUN
PV53_PNG = PV53_DIR + "/pv53_%s.png" % SRC_RUN
JUDGE52 = SRC_DIR + "/g52/judge_DFG.json"          # the pv53 alias of the judge (groups f / x_pk)
JUDGE52B = SRC_DIR + "/g52b/judge_DFGB.json"
SEATS_FINALS = HERO + "/seats/dfgb2e_seats_finals.json"
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
UNITY_METHOD = "GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture"
FPS = 24.0
COMMIT_MIN_GB = 8.0                                 # [chosen] free commit memory before any Unity batch (pagefile: one 0.5 m sim at a time)
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]

SEATS = {   # [chosen] dfgb2e_seats_finals.json candidates rank 1 (A) / rank 4 (B); FOV 55 = the DM1A hero precedent (the lip needs only +-9.3 / 6.3 deg)
    "A": dict(name="A", cls="A_front_quarter_close", x=284.0, z=-20.0, eye=1.5, look=[263.74, 6.04, 1.67], fov_v=55.0),
    "B": dict(name="B", cls="B_calm_clear_view", x=305.0, z=-32.0, eye=1.75, look=[281.61, 3.65, -13.3], fov_v=55.0),
}
PRINT = dict(group=2, pos=[270.3725239459851, 4.000681399583817, -71.37486248981337],      # [computed] group 2's own pv53 option-D pose
             look=[265.99486571327657, 5.475761891039959, 0.0], fov_v=23.5,                  # (DM1A composition scaled by Hc 6.814 / 7.160)
             rule="pv53 option D (Unity/Build/FLIP50/_scratch/cameras/cameras_DM1A.json composition) scaled by group 2's Hc at its print instant")
MOVE = dict(frame=2149, move=6.0, hold=2.0, stay=2.5, back=6.0)   # [chosen] one visible move to group 2 (the DM1A 6 s precedent); stay 6 -> 2.5 s on 10/18 after the 8/s preview: the crest leaves the print frame about 2.5 s after arrival [measured]
GROUP_BEST = {1: 1470, 2: 2149, 3: 2824}                          # [measured] pv53 periods[*].best.frame of the judged run
RESCORE_HALF = 12                                                  # [chosen] best +-12 frames (2137-2161, 2812-2836 in the design)
CAVITY = dict(dx_back=10.0, dx_fwd=40.0, min_cells=3, z_min=-1.0, bed_pad=0.75, max_s=4.0, td_pad_frames=12)   # [chosen] touchdown rule on r2
CLEAR_MIN = 1.0                                                    # [chosen] the seat rule: eye >= 1.0 m above the water on every frame
FOOT = (4.0, 1.5)                                                  # the player's heave footprint (f3d50_export FOOT)
NEAR = 2.0                                                         # +-2 m neighbours of the seat (reported)
ASPECT = 16.0 / 9.0
INVALID_EN = ("DFG-2B-E (DFGB2E_D19B_xf272p25_dp0p5), formally INVALID: G2f inlet 5.6 s phase 0.514 rad > 0.35, "
              "G6 group 1 peak 58.958 s, 0.042 s before 59.0 s")
ENERGY_EN = "energy: sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A"
NOSHAPE_EN = "no shapes between frames"


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def t_of(f):
    return (int(f) - 1) / FPS


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def emit(o):
    print(json.dumps(o, ensure_ascii=False, default=float))


# ====================================================================== the hero cfg, folders and names
class Hero:
    def __init__(self, cfgp, run=None, seat="A"):
        self.cfgp = cfgp
        self.cfg = jload(cfgp)
        if not self.cfg or (self.cfg.get("restart") or {}).get("src_run") != SRC_RUN:
            raise SystemExit("%s is not a DFG-2B-E hero re-record cfg" % cfgp)
        self.rid = self.cfg["run_id"]
        self.short = self.rid.split("_")[0]                                  # DFGB2Er
        self.rd = (run or (self.cfg["out_root"].rstrip("/") + "/" + self.rid)).replace("\\", "/").rstrip("/")
        self.is_source = os.path.normcase(os.path.abspath(self.rd)) == os.path.normcase(os.path.abspath(SRC_DIR))
        self.f0, self.f1 = int(self.cfg["f_start"]), int(self.cfg["f_end"])
        if seat not in SEATS:
            raise SystemExit("seat %s unknown (A or B)" % seat)
        self.seat = dict(SEATS[seat])
        tag = "%s_f%d_%d_r24_seat%s_ds" % (self.short, self.f0, self.f1, seat)
        self.clip_name = "clip_" + tag
        self.cap_name = "capture_" + tag
        self.clip = OUT3D + "/" + self.clip_name
        self.cap = OUT3D + "/" + self.cap_name
        # outputs of a check run on the JUDGED run itself (a stand-in before the re-record exists) go to hero/check_on_source/
        self.hj = lambda name: HERO + ("/check_on_source" if self.is_source else "") + "/%s_%s.json" % (name, self.rid)

    def compare(self):
        if self.is_source:                    # a check on the judged run itself: its own records and judgement (nothing to compare)
            return True, dict(source_itself=True)
        s = jload(self.rd + "/hero_compare_summary.json") or {}
        rc = jload(self.rd + "/restart_compare.json") or {}
        ident = bool(s.get("all_bit_identical_in_overlap") is True and rc.get("all_bit_identical") is True and s.get("every_frame_surf_complete"))
        return ident, s

    def physics_line(self):
        ident, s = self.compare()
        if self.is_source:
            return "physics only, 0.5 m Houdini FLIP; the judged run's own records (not re-recorded; a check run)"
        if ident:
            return ("physics only, 0.5 m Houdini FLIP; frames %d-%d re-recorded from checkpoint %d and bit-identical to the judged run "
                    "(hf/r2/r3 %s, volcorr %s, surf %s)" % (self.f0, self.f1, self.f0 - 1, s.get("hf_eta"), s.get("volcorr_equal"), s.get("r5_bytes_equal")))
        if not s:
            return ("physics only, 0.5 m Houdini FLIP; frames %d-%d re-recorded from checkpoint %d; compare with the judged run NOT done"
                    % (self.f0, self.f1, self.f0 - 1))
        return ("physics only, 0.5 m Houdini FLIP; frames %d-%d re-recorded from checkpoint %d and NOT bit-identical to the judged run "
                "(hf %s, r2 %s, volcorr %s, surf %s; see restart_compare.json)" % (self.f0, self.f1, self.f0 - 1, s.get("hf_eta"), s.get("r2_sdf"),
                                                                                  s.get("volcorr_equal"), s.get("r5_bytes_equal")))

    def invalid_line(self):
        return ((self.cfg.get("case") or {}).get("hero") or {}).get("invalid") or INVALID_EN

    def honesty(self):
        return [self.invalid_line(), ENERGY_EN, self.physics_line(), NOSHAPE_EN]


def hero_from_args(a):
    if not a or a[0].startswith("--"):
        raise SystemExit("give the hero cfg path")
    return Hero(a[0], run=opt(a, "--run"), seat=opt(a, "--seat", "A"))


# ====================================================================== readers
def rec(kind, rd):
    import f3d_common as C
    return C.Rec(kind, rd)


SURF_HEAD = struct.Struct("<8sIIdiIIffffffff")


def surf_points(path):
    """GW45SRF1 -> (P [x, up, lateral] float64, tri int64, t, frame) (positions and triangles only)."""
    b = open(path, "rb").read()
    magic, ver, hb, t, fr, nv, nt, x0, y0, z0, x1, y1, z1, off, _ = SURF_HEAD.unpack_from(b, 0)
    if magic != b"GW45SRF1":
        raise ValueError("not GW45SRF1: %s" % path)
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(nv, 3); o += nv * 6
    o += nv * 4 + nv * 6
    T = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3).astype(np.int64)
    lo = np.array([x0, y0, z0]); hi = np.array([x1, y1, z1])
    return q.astype(np.float64) / 65535.0 * (hi - lo) + lo, T, float(t), int(fr)


def column(P, T, x, lat):
    """heights (up) of every mesh crossing of the vertical line through (x, lat) (the DM1A cap_clearance rule)."""
    A, B, Cc = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    xs = np.stack([A[:, 0], B[:, 0], Cc[:, 0]], 1); zs = np.stack([A[:, 2], B[:, 2], Cc[:, 2]], 1)
    m = (xs.min(1) <= x) & (xs.max(1) >= x) & (zs.min(1) <= lat) & (zs.max(1) >= lat)
    A, B, Cc = A[m], B[m], Cc[m]
    if len(A) == 0:
        return np.zeros(0)
    v0 = np.stack([Cc[:, 0] - A[:, 0], Cc[:, 2] - A[:, 2]], 1); v1 = np.stack([B[:, 0] - A[:, 0], B[:, 2] - A[:, 2]], 1)
    v2 = np.stack([x - A[:, 0], lat - A[:, 2]], 1)
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d02 = (v0 * v2).sum(1); d12 = (v1 * v2).sum(1)
    den = d00 * d11 - d01 * d01
    ok = np.abs(den) > 1e-12
    u = np.where(ok, (d11 * d02 - d01 * d12) / np.where(ok, den, 1), -1); v = np.where(ok, (d00 * d12 - d01 * d02) / np.where(ok, den, 1), -1)
    ins = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
    y = A[:, 1] + u * (Cc[:, 1] - A[:, 1]) + v * (B[:, 1] - A[:, 1])
    return np.sort(y[ins])


def ranges(pairs):
    """consecutive frames grouped: [first, last, t_first, t_last, min value]."""
    out = []
    for f, v in sorted(pairs):
        if out and f <= out[-1][1] + 1:
            out[-1][1] = f; out[-1][2] = min(out[-1][2], v)
        else:
            out.append([f, f, v])
    return [[a, b, round(t_of(a), 3), round(t_of(b), 3), m] for a, b, m in out]


def pv53_best():
    """[measured] the judged run's pv53 per-group best frames and ruler (periods[*].best)."""
    P = jload(PV53_JSON) or {}
    ser = P.get("series") or {}
    out = {}
    for p in P.get("periods") or []:
        b = p.get("best") or {}
        rows = p.get("series") or ser.get(str(p["n"])) or []
        out[int(p["n"])] = dict(k=int(p["n"]), frame=int(b["frame"]), t=float(b["t"]), score3=float(b["score3"]), lip=b.get("lip"), hood=b.get("hood"),
                                x_c=b.get("x_c"), eta_c=b.get("eta_c"), scan_window=p.get("window_frames"), f_max=p.get("f_max"), x_max=p.get("x_max"),
                                series={int(r["frame"]): r.get("score3") for r in rows if r.get("frame") is not None})
    return out


# ====================================================================== rescore (pv53's D ruler on the re-record's centre section)
def cmd_rescore(a):
    H = hero_from_args(a)
    sys.path.insert(0, TOOLS + "/flip53")
    import pv53 as PV                                                     # read only (its PVRun / track / measure)
    want = None
    if opt(a, "--frames"):
        want = set()
        for part in opt(a, "--frames").split(","):
            lo, _, hi = part.partition("-")
            want |= set(range(int(lo), int(hi or lo) + 1))
    ident, cs = H.compare()
    src_best = pv53_best()
    with contextlib.redirect_stdout(io.StringIO()):
        R = PV.PVRun(H.rd, judge=JUDGE52)                                  # periods from the JUDGED run's own judge (same frame numbers)
    groups = []
    for p in R.periods:
        n = int(p["n"])
        sb = src_best.get(n) or {}
        fb = int(sb.get("frame") or GROUP_BEST.get(n))
        f_lo = p["f_max"] - int(round(PV.SCAN["back_s"] * FPS)); f_hi = p["f_max"] + int(round(PV.SCAN["fwd_s"] * FPS))
        trk = R.track(p["f_max"], p["x_max"], f_lo, f_hi)                 # the pv53 crest track from the judge's summit
        frames = [f for f in range(fb - RESCORE_HALF, fb + RESCORE_HALF + 1) if f in trk and f in R.r2set and (want is None or f in want)]
        rows = [R.measure(f, trk[f]) for f in frames]
        ok = [r for r in rows if r.get("score3") is not None]
        key = lambda r: (r["score3"], r.get("chord_miss") or 0.0, -(r.get("hood_height_m") or 0.0), r["frame"])
        best = min(ok, key=key) if ok else None
        same = [r["frame"] for r in ok if sb.get("series", {}).get(r["frame"]) is not None and abs(float(sb["series"][r["frame"]]) - float(r["score3"])) < 1e-9]
        groups.append(dict(n=n, frames=[frames[0], frames[-1]] if frames else None, n_measured=len(rows),
                           best=None if best is None else {k: best.get(k) for k in ("frame", "t", "score3", "lip", "hood", "x_c", "eta_c", "chord", "foot")},
                           source_best={k: sb.get(k) for k in ("frame", "score3", "lip", "hood", "x_c", "eta_c")},
                           best_frame_same_as_source=bool(best is not None and best["frame"] == sb.get("frame")),
                           score3_equal_to_source_frames=len(same), score3_compared=len([r for r in ok if sb.get("series", {}).get(r["frame"]) is not None]),
                           series=[(r["frame"], r.get("score3"), r.get("lip")) for r in rows]))
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " rescore", run=rel(H.rd), judge=rel(JUDGE52), source_pv53=rel(PV53_JSON),
               bit_identical=ident, label=("re-record bit-identical to the judged run: the pv53 numbers hold" if ident else
                                           "NOT bit-identical (or not compared): these are the re-record's OWN numbers, labelled 'not bit-identical'"),
               rule="pv53.PVRun.measure (g46 r2_mask -> STUDY52 measure_mask -> d_shape_measure.pick -> g47_video.score3) on frames best +-%d of each "
                    "group, crest track pv53.track from the judge's summit; best = smallest score3 (pv53 tie rule) [measured]" % RESCORE_HALF,
               groups=groups, tags="[measured] r2 ruler")
    if want is None:
        jdump(res, H.hj("rescore"))
    emit(dict(rescore=[(g["n"], (g["best"] or {}).get("frame"), (g["best"] or {}).get("score3"), g["best_frame_same_as_source"],
                        "%d/%d" % (g["score3_equal_to_source_frames"], g["score3_compared"])) for g in groups], bit_identical=ident,
              out=H.hj("rescore") if want is None else "(frames subset: not written)"))
    return 0


# ====================================================================== cues (onset / touchdown on the centre section r2, every frame)
def touchdown(R2, meta, f_on, x_on, bed_of, oy, f_last):
    """first frame >= onset (<= onset + max_s) whose centre section r2 (lateral 0.5 m) holds an ENCLOSED air pocket near the crest: the
    plunging lip has reached the water in front (the g46 'cavity' idea on the 1 m r2 grid) [chosen rule]. Air = sdf >= 0 above the bed;
    a pocket = a 4-connected air region inside x on - dx_back .. on + dx_fwd, z >= z_min, not touching the window's top / sides, >= min_cells."""
    from scipy import ndimage as ndi
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(int(meta["nx"]))
    zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(int(meta["ny"])) - oy          # plan z (Houdini up = plan + o)
    ix = np.where((xs >= x_on - CAVITY["dx_back"]) & (xs <= x_on + CAVITY["dx_fwd"]))[0]
    iz = np.where(zs >= CAVITY["z_min"])[0]
    bed = bed_of(xs[ix])                                                                # [len(ix)]
    for f in range(f_on, min(f_last, f_on + int(round(CAVITY["max_s"] * FPS))) + 1):
        if f not in R2.where:
            continue
        S = R2.get(f)[np.ix_(iz, ix)]
        air = (S >= 0.0) & (zs[iz][:, None] >= bed[None, :] + CAVITY["bed_pad"])
        lab, n = ndi.label(air)
        if n == 0:
            continue
        open_ = set(np.unique(np.concatenate([lab[-1, :], lab[:, 0], lab[:, -1]]))) - {0}
        for c in range(1, n + 1):
            if c in open_:
                continue
            cells = np.argwhere(lab == c)
            if len(cells) >= CAVITY["min_cells"]:
                zc = float(zs[iz][cells[:, 0]].mean()); xc = float(xs[ix][cells[:, 1]].mean())
                return dict(frame=int(f), t=t_of(f), cells=int(len(cells)), x=round(xc, 2), z=round(zc, 2), dt_after_onset=round((f - f_on) / FPS, 3))
    return None


def cmd_cues(a):
    H = hero_from_args(a)
    sys.path.insert(0, TOOLS + "/flip52b")
    import g52b_common as GC                                               # bed functions (read only)
    J = jload(JUDGE52B) or {}
    spec = GC.bed_spec(H.cfg)
    oy = float(H.cfg["parms"].get("oy", 0.5))
    bed_of = lambda x: np.asarray(GC.bed_z(np.asarray(x, float), np.full(np.shape(x), 0.5), **spec), float)
    R2 = rec("r2", H.rd)
    ident, _ = H.compare()
    best = pv53_best()
    out = []
    for g in J.get("groups") or []:
        n = int(g["n"]); on = g.get("onset") or {}
        if not on.get("frame"):
            continue
        f_on, x_on = int(on["frame"]), float(on["x"])
        td = touchdown(R2, R2.meta, f_on, x_on, bed_of, oy, H.f1)
        b = best.get(n) or {}
        w1 = (td["frame"] + CAVITY["td_pad_frames"]) if td else (f_on + 60)
        out.append(dict(k=n, onset=dict(frame=f_on, t=t_of(f_on), x=x_on, source="judge_DFGB.json groups[%d].onset (r2 lip, every frame) [measured]" % (n - 1)),
                        touchdown=td, win_first=f_on, win_last=int(min(w1, H.f1)),
                        win_rule=("onset .. touchdown + 0.5 s" if td else "onset .. onset + 2.5 s (no enclosed pocket found: the g49 fallback)"),
                        best_frame=b.get("frame"), best_inside=bool(b.get("frame") and f_on <= b["frame"] <= w1), pv53_scan_window=b.get("scan_window")))
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " cues", run=rel(H.rd), bit_identical=ident, rule=touchdown.__doc__.strip(),
               cavity=CAVITY, cues=out, note="FLIP3DExperience cues = breaker_onset (win_first), breaker_best (frame), breaker_touchdown (win_last). "
                                             "The pv53 window_frames are scan windows, not cues.", tags="[measured] r2 records; rule [chosen]")
    jdump(res, H.hj("cues"))
    emit(dict(cues=[(c["k"], c["win_first"], (c["touchdown"] or {}).get("frame"), c["win_last"], c["best_frame"], c["best_inside"]) for c in out],
              out=H.hj("cues")))
    return 0 if out else 1


# ====================================================================== seat clearance on every frame
def heave_series(HF, xs, zs, seat, frames):
    ix = (xs >= seat["x"] - FOOT[0]) & (xs <= seat["x"] + FOOT[0])
    iz = (zs >= abs(seat["z"]) - FOOT[1]) & (zs <= abs(seat["z"]) + FOOT[1])
    return np.array([float(np.nanmean(HF.get(f)[iz][:, ix])) for f in frames])


def bilinear(e, xs, zs, x, z):
    i = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)); j = int(np.clip(np.searchsorted(zs, z) - 1, 0, len(zs) - 2))
    u = (x - xs[i]) / (xs[i + 1] - xs[i]); v = (z - zs[j]) / (zs[j + 1] - zs[j])
    q = e[j:j + 2, i:i + 2].astype(np.float64)
    return float((1 - v) * ((1 - u) * q[0, 0] + u * q[0, 1]) + v * ((1 - u) * q[1, 0] + u * q[1, 1]))


def cmd_seatcheck(a):
    H = hero_from_args(a)
    import f3d_common as C
    seat = H.seat
    HF = rec("hf", H.rd)
    xs, zs = C.axes_hf(HF.meta)
    off = float(H.cfg.get("still_offset_m") or 0.07598474621772766)
    frames = [f for f in range(H.f0, H.f1 + 1) if f in HF.where]
    miss_hf = (H.f1 - H.f0 + 1) - len(frames)
    hv = heave_series(HF, xs, zs, seat, frames)
    eye = off + seat["eye"] + hv
    lat = abs(seat["z"])
    pt, nb = [], []
    jx = (xs >= seat["x"] - NEAR) & (xs <= seat["x"] + NEAR); jz = (zs >= lat - NEAR) & (zs <= lat + NEAR)
    for i, f in enumerate(frames):
        e = HF.get(f)
        pt.append(eye[i] - bilinear(e, xs, zs, seat["x"], lat))
        nb.append(eye[i] - float(np.nanmax(e[jz][:, jx])))
    pt, nb = np.array(pt), np.array(nb)
    # surface meshes: the boat footprint (x +-4 m, lateral +-1.5 m) top vertex and the column at the eye
    sf = [f for f in range(H.f0, H.f1 + 1) if os.path.exists(H.rd + "/surf/s_%05d.gw45s" % f)]
    lim = opt(a, "--max-meshes")
    if lim:
        sf = sf[:int(lim)]
    fi = {f: i for i, f in enumerate(frames)}
    mrows = []
    for f in sf:
        P, T, t, fr = surf_points(H.rd + "/surf/s_%05d.gw45s" % f)
        if f not in fi:
            continue
        m = (np.abs(P[:, 0] - seat["x"]) <= FOOT[0]) & (np.abs(np.abs(P[:, 2]) - lat) <= FOOT[1])
        me = (np.abs(P[:, 0] - seat["x"]) <= 0.5) & (np.abs(np.abs(P[:, 2]) - lat) <= 0.5)
        top = float(P[m, 1].max()) if m.any() else None
        tope = float(P[me, 1].max()) if me.any() else None
        col = column(P, T, seat["x"], lat)
        mrows.append((f, eye[fi[f]] - (top if top is not None else -1e9), eye[fi[f]] - (float(col.max()) if len(col) else -1e9),
                      int((col > eye[fi[f]]).sum()) if len(col) else 0, eye[fi[f]] - (tope if tope is not None else -1e9)))
    mf = np.array([r[1] for r in mrows]) if mrows else np.array([np.inf])
    mc = np.array([r[2] for r in mrows]) if mrows else np.array([np.inf])
    mev = np.array([r[4] for r in mrows]) if mrows else np.array([np.inf])
    # the print camera (fixed): hf +-2 m and the mesh column, over the play range and during hold + stay
    pp = PRINT["pos"]
    kx = (xs >= pp[0] - NEAR) & (xs <= pp[0] + NEAR); kz = (zs >= abs(pp[2]) - NEAR) & (zs <= abs(pp[2]) + NEAR)
    pc = np.array([pp[1] - float(np.nanmax(HF.get(f)[kz][:, kx])) for f in frames])
    stay = [i for i, f in enumerate(frames) if MOVE["frame"] <= f <= MOVE["frame"] + int(MOVE["stay"] * FPS)]
    rate = np.abs(np.diff(hv)) * FPS if len(hv) > 1 else np.zeros(1)
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " seatcheck", run=rel(H.rd), seat=seat, still_offset_m=off,
               frames=[frames[0], frames[-1]], n_hf_frames=len(frames), hf_frames_missing=miss_hf, n_meshes=len(mrows),
               meshes_expected=H.f1 - H.f0 + 1, model="eye(t) = still_offset + seat_eye_m + heave(t), heave = nanmean hf over x +-%g m, lateral +-%g m "
                                                     "(the FLIP3D player / f3d50_export rule)" % FOOT,
               hf_point_min_m=float(pt.min()), hf_point_min_frame=frames[int(pt.argmin())],
               hf_near2m_min_m=float(nb.min()), hf_near2m_min_frame=frames[int(nb.argmin())],
               mesh_eye_min_m=float(mev.min()), mesh_eye_min_frame=(mrows[int(mev.argmin())][0] if mrows else None),
               mesh_eye_rule="top vertex within x +-0.5 m, lateral +-0.5 m of the eye point (the dfgb2e_seats.py 'mesh_min_m' rule)",
               mesh_footprint_min_m=float(mf.min()), mesh_footprint_min_frame=(mrows[int(mf.argmin())][0] if mrows else None),
               mesh_footprint_rule="top vertex anywhere in the boat footprint x +-%g m, lateral +-%g m (report: water inside the boat's own box, "
                                   "not at the eye)" % FOOT,
               mesh_column_min_m=float(mc.min()), mesh_column_min_frame=(mrows[int(mc.argmin())][0] if mrows else None),
               mesh_frames_column_above_eye=[r[0] for r in mrows if r[3] > 0][:50],
               hf_point_lt1=ranges([(frames[i], round(float(v), 3)) for i, v in enumerate(pt) if v < CLEAR_MIN]),
               mesh_eye_lt1=ranges([(r[0], round(float(r[4]), 3)) for r in mrows if r[4] < CLEAR_MIN]),
               mesh_footprint_lt1=ranges([(r[0], round(float(r[1]), 3)) for r in mrows if r[1] < CLEAR_MIN]),
               heave_range_m=[float(hv.min()), float(hv.max())], heave_swing_m=float(hv.max() - hv.min()), heave_rate_max_mps=float(rate.max()),
               print_cam_hf2m_min_m=float(pc.min()), print_cam_hf2m_min_frame=frames[int(pc.argmin())],
               print_cam_hold_stay_min_m=float(pc[stay].min()) if stay else None,
               expected_design=dict(hf_point=">= 1.38", near2m=">= 0.78", mesh=">= 1.40", heave="-1.56 .. +2.33 m, 3.1 m/s", print_stay=">= 2.57"),
               tags="[measured] hf / surf records; footprint, eye model [chosen as the player]")
    res["ok"] = bool(len(frames) == H.f1 - H.f0 + 1 and res["hf_point_min_m"] >= CLEAR_MIN and res["mesh_eye_min_m"] >= CLEAR_MIN
                     and res["mesh_column_min_m"] >= CLEAR_MIN)
    res["ok_rule"] = ("every frame %d-%d: hf at the seat point, the surface mesh at the eye point (+-0.5 m) and the mesh column through the eye all "
                      ">= %.1f m below the eye [chosen = the seat search rule]; the boat-footprint and +-2 m numbers are reported" % (H.f0, H.f1, CLEAR_MIN))
    res["footprint_below_1m"] = bool(res["mesh_footprint_min_m"] < CLEAR_MIN)
    if not lim:
        jdump(res, H.hj("seatcheck_seat%s" % seat["name"]))
    emit({k: res[k] for k in ("seat", "n_hf_frames", "n_meshes", "hf_point_min_m", "hf_point_min_frame", "hf_near2m_min_m", "mesh_eye_min_m", "mesh_footprint_min_m",
                              "mesh_footprint_min_frame", "mesh_column_min_m", "heave_range_m", "heave_rate_max_mps", "print_cam_hold_stay_min_m",
                              "print_cam_hf2m_min_m", "ok")})
    return 0 if res["ok"] else 3


# ====================================================================== print framing (pinhole, Unity LookRotation, 16:9)
def project(pos, look, fov_v, P):
    pos, look, P = (np.asarray(v, float) for v in (pos, look, P))
    fw = look - pos; fw /= np.linalg.norm(fw)
    up0 = np.array([0.0, 1.0, 0.0])
    rt = np.cross(up0, fw); rt /= np.linalg.norm(rt)
    up = np.cross(fw, rt)
    d = P - pos
    z = float(d @ fw)
    tv = math.tan(math.radians(fov_v) / 2.0); th = tv * ASPECT
    return [round(float(d @ rt) / z / th, 4), round(float(d @ up) / z / tv, 4)]


def cmd_framing(a):
    H = hero_from_args(a)
    best = pv53_best()
    fin = jload(SEATS_FINALS) or {}
    lips = {int(L["n"]): L for L in fin.get("lips") or []}
    off = float(H.cfg.get("still_offset_m") or 0.07598474621772766)
    rows = []
    for n, b in sorted(best.items()):
        crest = [b["x_c"], b["eta_c"] + off, 0.0]
        tip = (lips.get(n) or {}).get("axis_tip")
        lipP = [tip[0], tip[1] + off, 0.0] if tip else None
        rows.append(dict(k=n, frame=b["frame"], crest_unity=crest, crest_ndc=project(PRINT["pos"], PRINT["look"], PRINT["fov_v"], crest),
                         lip_unity=lipP, lip_ndc=project(PRINT["pos"], PRINT["look"], PRINT["fov_v"], lipP) if lipP else None))
    g2 = [r for r in rows if r["k"] == PRINT["group"]]
    ok = bool(g2 and abs(g2[0]["crest_ndc"][0]) <= 0.15 and abs(g2[0]["crest_ndc"][1]) <= 0.15 and (g2[0]["lip_ndc"] is None or
                                                                                                  (abs(g2[0]["lip_ndc"][0]) <= 0.15 and abs(g2[0]["lip_ndc"][1]) <= 0.15)))
    pp = [p for p in fin.get("print_poses") or [] if int(p.get("n", 0)) == PRINT["group"]]
    pose_same = bool(pp and max(abs(pp[0]["printPos"][i] - PRINT["pos"][i]) for i in range(3)) < 0.01
                     and max(abs(pp[0]["printLookAt"][i] - PRINT["look"][i]) for i in range(3)) < 0.01)
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " framing", pose=PRINT, aspect="16:9", rows=rows, ok_group2_within_0p15=ok,
               pose_matches_seats_finals=pose_same, rule="(horizontal, vertical) offset from the image centre in half-widths / half-heights; crest = "
                                                         "pv53 best (x_c, eta_c + still offset, lateral 0); lip = the r4 axis tip of dfgb2e_seats_finals.json",
               design_expected="group 2 crest -0.019 / +0.08, lip +0.020 / +0.002; groups 1 and 3 within 0.14", tags="[computed] from [measured] crest / lip")
    jdump(res, H.hj("framing"))
    emit(dict(framing=[(r["k"], r["crest_ndc"], r["lip_ndc"]) for r in rows], ok=ok, pose_matches_seats_finals=pose_same))
    return 0 if ok else 3


# ====================================================================== cameras JSON + export
def cams_json(H):
    s = H.seat
    p = HERO + "/cameras_%s_seat%s.json" % (SRC_RUN.split("_")[0], s["name"])
    yaw = math.degrees(math.atan2(s["look"][0] - s["x"], s["look"][2] - s["z"]))
    d = dict(run_id=SRC_RUN, date=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " cams", source=rel(SEATS_FINALS),
             conventions=dict(unity="FLIP3DPlayer: Unity (x, y, z) = (plan x, plan z, plan y); seat SeatBase = (seat_x, still_offset + seat_eye_m, seat_z), "
                                    "eye = SeatBase + up x heave(t); seat rotation LookRotation(seatLookAt - SeatBase), fixed. Print: printPos / printLookAt / printFovV."),
             seat=dict(plan=dict(x=s["x"], y=s["z"], lateral_abs=abs(s["z"]), eye_above_heave_m=s["eye"], cls=s["cls"]),
                       unity=dict(manifest=dict(seat_x=s["x"], seat_z=s["z"], seat_eye_m=s["eye"]), seatLookAt=s["look"], seatFovV=s["fov_v"], yaw_deg=round(yaw, 2))),
             print=dict(group=PRINT["group"], rule=PRINT["rule"], unity=dict(printPos=PRINT["pos"], printLookAt=PRINT["look"], printFovV=PRINT["fov_v"])),
             move=MOVE, tags="[chosen] seat, FOV, move; [computed] print pose")
    jdump(d, p)
    return p


def manifest_patch(H, man, cams_path, cues, export_j):
    ident, cs = H.compare()
    s = H.seat
    man.update(cam_seat_look_at=[float(v) for v in s["look"]], cam_seat_fov_v=float(s["fov_v"]), cam_print_pos=[float(v) for v in PRINT["pos"]],
               cam_print_look_at=[float(v) for v in PRINT["look"]], cam_print_fov_v=float(PRINT["fov_v"]), cam_source_file=rel(cams_path),
               cam_source_sha256=sha(cams_path), cam_source_run=SRC_RUN,
               cam_note_ja=("座席（seat_x %.0f・seat_z %.0f・目 %.2f m と heave）と、座席の見る点・画角・原画の視点は %s の値【選び】。原画の視点は"
                            "群 2 の pv53 の方案 D の構図（Hc で拡大）【計算】" % (s["x"], s["z"], s["eye"], rel(cams_path))))
    man["water_double_sided"] = True
    man["water_double_sided_ja"] = ("表示だけ：FLIP3D のプレイヤーは水を両面で描く（面の記録の穴の向こうの水の裏の面を、法線を裏返して表と同じ式で塗る）。"
                                    "記録・計算・形は変えない。穴を埋めたのではない")
    man["half_width_ja"] = ("面の記録は横 0〜97.5 m（cfg の crop_z1 = 95 m まで）。95〜140 m は横の緩和の帯で記録しない。壁ではないので並べない："
                            "-f3dtiles 0 で見る（外は計算にない平らな海）。y = 0 は計算の対称の面（写して全幅を描く）")
    man["unity_notes_ja"] = ("座席・原画の視点の値は manifest の cam_* を使う。視点の動きは -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g"
                             "（群 2 の原画に最も近い瞬間 %.3f s に着く。白い画面は使わない）。VR では -f3dnocrestalign も付ける（crestAlign は姿勢を約 −13 m ずらす）。"
                             "FLIP3DExperience の既定は群 3 を選ぶので f%d を明示する" % (MOVE["frame"], MOVE["move"], MOVE["hold"], MOVE["stay"], MOVE["back"],
                                                                                      t_of(MOVE["frame"]), MOVE["frame"]))
    man["breakers_source"] = (("judged run %s: pv53 best frames / score3 / ruler (%s) and judge onset (%s); cue touchdown measured on the "
                               "re-record's r2 (%s). Borrowed because the re-record is bit-identical to the judged run (%s)" %
                               (SRC_RUN, rel(PV53_JSON), rel(JUDGE52B), rel(H.hj("cues")), rel(H.rd + "/restart_compare.json"))) if ident else
                              ("NOT bit-identical (or not compared): the re-record's OWN r2 ruler numbers (%s, labelled 'not bit-identical') and "
                               "touchdown (%s)" % (rel(H.hj("rescore")), rel(H.hj("cues")))))
    man["hero"] = dict(q="Q85", user_words="DFG-2B 的效果更好", run=rel(H.rd), source_run=SRC_RUN, bit_identical=ident, compare=cs,
                       honesty_en=H.honesty(), seat=s, print=PRINT, move=MOVE, cues=cues, tool=TOOL,
                       vr_command_hint=("FLIP3D player: -f3ddata %s -f3dtiles 0 -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g "
                                        "-f3dnocrestalign" % (H.clip, MOVE["frame"], MOVE["move"], MOVE["hold"], MOVE["stay"], MOVE["back"])),
                       export=dict((k, export_j.get(k)) for k in ("out", "records", "record_fps", "t", "play", "bytes", "print", "breakers", "heave")))
    man["notes_en"] = H.honesty()
    return man


def cmd_export(a):
    H = hero_from_args(a)
    import f3d50_export as FX
    ident, cs = H.compare()
    cues = (jload(H.hj("cues")) or {}).get("cues")
    if not cues:
        raise SystemExit("no cues (%s): run `cues` first" % H.hj("cues"))
    if ident:
        nums = {n: dict(frame=b["frame"], score3=b["score3"], lip=b["lip"], hood=b["hood"], x_c=b["x_c"], eta_c=b["eta_c"], t=b["t"])
                for n, b in pv53_best().items()}
        nums_src = "pv53 of the judged run (borrowed: bit-identical)"
    else:
        rs = jload(H.hj("rescore")) or {}
        nums = {int(g["n"]): dict(g["best"], t=t_of(g["best"]["frame"])) for g in rs.get("groups") or [] if g.get("best")}
        nums_src = "the re-record's own rescore (NOT bit-identical)"
        if not nums:
            raise SystemExit("not bit-identical and no rescore: run `rescore` first")
    per = []
    for c in cues:
        b = nums.get(int(c["k"]))
        if not b:
            continue
        per.append(dict(k=int(c["k"]), frame=int(b["frame"]), t=float(b["t"]), score3=float(b["score3"]), window_frames=[int(c["win_first"]), int(c["win_last"])],
                        ruler=dict(hood=b.get("hood"), lip=b.get("lip")), x_c=b.get("x_c"), eta_c=b.get("eta_c")))
    bf = dict(per_breaker=per, source=nums_src)
    cams_path = cams_json(H)
    orig = FX.Run.__init__

    def init(self, name):
        orig(self, name)
        if self.bf is None:
            self.bf = bf
    FX.Run.__init__ = init
    s = H.seat
    fs, ts = float(opt(a, "--from-s", t_of(H.f0))), float(opt(a, "--to-s", t_of(H.f1)))     # (--from-s / --to-s: tests on a part only)
    args = ["--run", H.rd, "--from-s", "%.6f" % fs, "--to-s", "%.6f" % ts, "--seat", "%g,%g" % (s["x"], s["z"]), "--eye", "%g" % s["eye"],
            "--print-k", str(PRINT["group"]), "--name", H.clip_name]
    dry = "--dry" in a
    if dry:
        args.append("--dry")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        FX.main_long(args)
    txt = buf.getvalue()
    j = json.loads(txt[txt.index("{"):]) if "{" in txt else {}
    if dry:
        emit(dict(dry=j, cams=cams_path, bit_identical=ident, breakers=per))
        return 0
    mp = H.clip + "/manifest.json"
    man = manifest_patch(H, jload(mp), cams_path, cues, j)
    json.dump(man, open(mp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    he = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " export", clip=rel(H.clip), args=args, export=j, breakers=per,
              numbers_source=nums_src, bit_identical=ident, honesty_en=H.honesty())
    jdump(he, H.clip + "/hero_export.json")
    emit(dict(out=H.clip, records=j.get("records"), record_fps=j.get("record_fps"), t=j.get("t"), print=(j.get("print") or {}).get("print_record_frame"),
              breakers=j.get("breakers"), heave=j.get("heave"), bit_identical=ident, water_double_sided=man.get("water_double_sided")))
    return 0 if j.get("out") else 4


# ====================================================================== Unity (memory check, backup / restore of the tracked scene + materials)
class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def commit_free_gb():
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9, m.ullTotalPageFile / 1e9


def capture_args(H, jobs):
    return ("-f3dcap %s -f3dsize 1920x1080 -f3dfps 24 -f3dtiles 0 -f3dsha -f3ddata %s -f3dfrom %.4f -f3dto %.4f -f3dmoves f%d -f3dmovesec %g "
            "-f3dhold %g -f3dstay %g -f3dback %g -f3dout %s" % (jobs, H.clip, t_of(H.f0), t_of(H.f1) + 1.0 / FPS, MOVE["frame"], MOVE["move"],
                                                               MOVE["hold"], MOVE["stay"], MOVE["back"], H.cap))


def cmd_unity(a):
    H = hero_from_args(a)
    jobs = opt(a, "--jobs", "cstills,cseat,cprint,cmove")
    extra = capture_args(H, jobs)
    log = "hero2b_%s_seat%s" % (H.short, H.seat["name"])
    free, total = commit_free_gb()
    plan = dict(method=UNITY_METHOD, extra=extra, log=log, commit_free_gb=round(free, 2), commit_limit_gb=round(total, 2), need_gb=COMMIT_MIN_GB)
    if "--dry" in a:
        emit(dict(dry=plan)); return 0
    if not os.path.exists(H.clip + "/manifest.json"):
        raise SystemExit("no clip %s: run `export` first" % H.clip)
    if free < COMMIT_MIN_GB:
        emit(dict(unity="skipped: commit free %.2f GB < %.1f GB" % (free, COMMIT_MIN_GB), **plan)); return 5
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = HERO + "/_unity_backup/" + stamp
    os.makedirs(bdir, exist_ok=True)
    before = {}
    for r in TRACKED:
        src = REPO + "/" + r
        dst = bdir + "/" + r.replace("/", "__")
        shutil.copyfile(src, dst)
        before[r] = sha(src)
        assert sha(dst) == before[r]
    t0 = time.time()
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UNITY_PS1, "-Method", UNITY_METHOD, "-Log", log, "-Extra", extra,
           "-TimeoutMinutes", "90", "-LockWaitMinutes", "40"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    finally:
        restored = {}
        for rr in TRACKED:
            dst = REPO + "/" + rr
            shutil.copyfile(bdir + "/" + rr.replace("/", "__"), dst)
            restored[rr] = sha(dst) == before[rr]
    line = [l for l in out.splitlines() if l.startswith("FLIP3D_UNITY ")]
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " unity", rc=rc, seconds=round(time.time() - t0, 1), unity_line=line[-1] if line else None,
               settings_changed=(line[-1].split("settings_changed=")[1].split(" ")[0] if line and "settings_changed=" in line[-1] else None),
               restored_pre_batch_state=restored, all_restored=all(restored.values()), backup=rel(bdir), tail=out[-1500:], **plan)
    jdump(res, H.hj("unity_seat%s" % H.seat["name"]))
    emit({k: res[k] for k in ("rc", "seconds", "unity_line", "settings_changed", "all_restored", "backup")})
    return 0 if (rc == 0 and res["all_restored"]) else 6


# ====================================================================== capture checks
def cmd_capcheck(a):
    H = hero_from_args(a)
    man = jload(H.clip + "/manifest.json") or {}
    sd = man.get("stream_dir") or (H.rd + "/surf")
    ff = int(man.get("frame_first") or H.f0)
    out = {}
    memo = {}

    def surf(f):
        if f not in memo:
            memo.clear()
            memo[f] = surf_points(sd + "/s_%05d.gw45s" % f)
        return memo[f]
    from PIL import Image
    for mode in ("cseat", "cprint", "cmove"):
        d = H.cap + "/" + mode
        if not os.path.exists(d + "/frames.csv"):
            out[mode] = dict(missing=True); continue
        rows = list(csv.DictReader(open(d + "/frames.csv", encoding="utf8")))
        if opt(a, "--limit"):                                                  # tests only: the first N captured frames
            rows = rows[:int(opt(a, "--limit"))]
        cj = jload(d + "/capture.json") or {}
        recs = np.array([int(r["record"]) for r in rows]); sf = np.array([int(r["sim_frame"]) for r in rows])
        st = np.array([float(r["sim_t"]) for r in rows]); fr = np.array([int(r["frozen"]) for r in rows]); bl = np.array([float(r["blend"]) for r in rows])
        pos = np.array([[float(r["cx"]), float(r["cy"]), float(r["cz"])] for r in rows]); fov = np.array([float(r["fov"]) for r in rows])
        dd = np.diff(recs)
        u, c = np.unique(recs, return_counts=True)
        o = dict(frames=len(rows), seconds=len(rows) / FPS, first=[int(recs[0]), int(sf[0])], last=[int(recs[-1]), int(sf[-1])],
                 sim_frame_eq_first_plus_record=bool((sf == ff + recs).all()), steps=sorted(set(dd.tolist())), back_steps=int((dd < 0).sum()),
                 skipped_records=int((dd > 1).sum()), frozen_frames=int(fr.sum()), frozen_records=sorted(set(recs[fr == 1].tolist())),
                 records_shown_more_than_once=[(int(x), int(y)) for x, y in zip(u, c) if y > 1][:10], records_unique=int(len(u)),
                 shown_eq_wanted=bool(all(int(r["record"]) == int(r["wanted"]) for r in rows)), schedule=cj.get("schedule"), moves=cj.get("moves"),
                 streaming=cj.get("streaming"), water_double_sided=cj.get("waterDoubleSided"))
        sel = range(len(rows)) if mode != "cmove" else np.where(bl > 0)[0]
        cl, nr, above = [], [], []
        mk = {}
        for i in sel:
            key = (int(sf[i]), round(pos[i, 0], 3), round(pos[i, 1], 3), round(pos[i, 2], 3))
            if key not in mk:
                P, T, _, _ = surf(int(sf[i]))
                ys = column(P, T, pos[i, 0], abs(pos[i, 2]))
                dist = float(np.sqrt(((P - np.array([pos[i, 0], pos[i, 1], abs(pos[i, 2])])) ** 2).sum(1)).min())
                mk[key] = (pos[i, 1] - float(ys.max()) if len(ys) else np.inf, dist, int((ys > pos[i, 1]).sum()) if len(ys) else 0)
            a_, b_, c_ = mk[key]
            cl.append(a_); nr.append(b_); above.append((int(sf[i]), c_))
        cl = np.array(cl) if cl else np.array([np.inf]); nr = np.array(nr) if nr else np.array([np.inf])
        idx = list(sel)
        fin = lambda v: float(v) if np.isfinite(v) else None
        o.update(cam_col_clearance_min_m=fin(cl.min()), cam_col_clearance_min_sim_frame=int(sf[idx[int(cl.argmin())]]) if idx else None,
                 cam_nearest_vertex_min_m=fin(nr.min()), frames_mesh_above_cam=[f for f, n in above if n > 0][:50],
                 frames_col_clear_lt1=ranges([(int(sf[idx[k]]), round(float(v), 3)) for k, v in enumerate(cl) if v < CLEAR_MIN]))
        if mode == "cmove":
            mv = np.where(bl > 0)[0]; one = np.where(bl >= 0.99995)[0]
            if len(mv):
                o["move_start_sim_t"] = float(st[mv[0]]); o["move_end_sim_t"] = float(st[mv[-1]])
                o["blend_first_pos_s"] = float(rows[mv[0]]["s"])
            if len(one):
                o["arrive"] = dict(sim_frame=int(sf[one[0]]), sim_t=float(st[one[0]]), record=int(recs[one[0]]), frozen=int(fr[one[0]]))
                o["leave_sim_t"] = float(st[one[-1]])
            o["max_cam_step_m"] = float(np.linalg.norm(np.diff(pos, axis=0), axis=1).max())
            o["max_fov_step_deg"] = float(np.abs(np.diff(fov)).max())
            o["expected"] = "move 83.5 -> arrive 89.5 (frame %d), hold 2 s (48 frames), stay to 95.5, back 95.5-101.5, end 125.0" % MOVE["frame"]
        lum, white = [], []
        for i in range(len(rows)):
            im = Image.open(d + "/frame_%05d.jpg" % i)
            im.draft("L", (240, 135))
            q = np.asarray(im.convert("L"), np.float32)
            lum.append(q.mean()); white.append((q > 240).mean())
        lum, white = np.array(lum), np.array(white)
        o.update(lum_min_max=[float(lum.min()), float(lum.max())], white_frac_max=float(white.max()), max_lum_jump=float(np.abs(np.diff(lum)).max()),
                 white_out=bool(white.max() > 0.5))
        out[mode] = o
    log = OUT3D + "/logs/unity_hero2b_%s_seat%s.log" % (H.short, H.seat["name"])
    lt = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    out["unity_log"] = dict(file=rel(log), cseq=[l.strip()[:400] for l in lt.splitlines() if "FLIP3D_CSEQ" in l][:6],
                            stream=[l.strip()[:300] for l in lt.splitlines() if "FLIP3D_STREAM_STATS" in l][-2:],
                            exceptions=len([l for l in lt.splitlines() if "Exception" in l]))
    m = out.get("cmove") or {}
    out["ok"] = bool(all((out.get(k) or {}).get("sim_frame_eq_first_plus_record") for k in ("cseat", "cprint", "cmove"))
                     and all((out.get(k) or {}).get("skipped_records", 1) == 0 and (out.get(k) or {}).get("back_steps", 1) == 0 for k in ("cseat", "cprint", "cmove"))
                     and m.get("frozen_frames") == int(MOVE["hold"] * FPS) and not any((out.get(k) or {}).get("white_out") for k in ("cseat", "cprint", "cmove"))
                     and ((out.get("cseat") or {}).get("cam_col_clearance_min_m") or 0) >= CLEAR_MIN)
    out["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    jdump(out, H.cap + "/hero_capcheck.json")
    jdump(out, H.hj("capcheck_seat%s" % H.seat["name"]))
    emit(dict(ok=out["ok"], **{k: {kk: (out.get(k) or {}).get(kk) for kk in ("frames", "sim_frame_eq_first_plus_record", "skipped_records", "frozen_frames",
                                                                             "cam_col_clearance_min_m", "white_frac_max", "move_start_sim_t", "arrive", "leave_sim_t")}
                                for k in ("cseat", "cprint", "cmove")}))
    return 0 if out["ok"] else 7


# ====================================================================== videos (unchanged compose_cont_exact + in-memory caption lines)
def cmd_video(a):
    H = hero_from_args(a)
    import f3d50_video_loop as FL                                            # unchanged
    V, V5 = FL.V, FL.V5
    ident, _ = H.compare()
    V5.RUN_TEXT = dict(V5.RUN_TEXT)
    V5.RUN_TEXT[H.short] = ("%s：DFG-2B-E（多くの周波数の組、総エネルギー = DM1A）を 48 s の途中保存から同じ物理で計算し直し、面を毎コマ、粒子 0.5 m"
                            % H.short)
    l4 = H.invalid_line() + " | " + ENERGY_EN
    l5 = H.physics_line() + " | " + NOSHAPE_EN
    V.HERO2B_L4, V.HERO2B_L5 = l4, l5                                        # in memory: copied into the exec namespace by V5.patched
    band_old = "        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))\n"
    band_new = "        dr.rectangle([0, 0, W, 166], fill=(0, 0, 0, 150))\n"
    l3_old = "        dr.text((18, 74), line3, font=_fit(line3, 19, W - 36), fill=(225, 225, 225))\n"
    l3_new = l3_old + ("        dr.text((18, 102), HERO2B_L4, font=_fit(HERO2B_L4, 19, W - 36), fill=(255, 200, 140))\n"
                       "        dr.text((18, 130), HERO2B_L5, font=_fit(HERO2B_L5, 19, W - 36), fill=(255, 200, 140))\n")
    FL.FIT_LINES = tuple(FL.FIT_LINES) + ((band_old, band_new), (l3_old, l3_new))     # each must occur exactly once (checked by FL)
    names = [n for n in ("cseat", "cprint", "cmove") if os.path.exists(H.cap + "/" + n + "/frames.csv")] or ["cseat", "cprint", "cmove"]
    if "--dry" in a:
        if not os.path.exists(H.cap + "/" + names[0] + "/capture.json"):
            # caption patch check only: compile the patched compose_cont on f3d_video's source (no capture needed)
            import inspect
            s = inspect.getsource(V.compose_cont)
            if s.count(FL.OLD_MOVE) != 1:
                raise SystemExit("move caption not found once")
            s = s.replace(FL.OLD_MOVE, FL.NEW_MOVE)
            for old, new in FL.FIT_LINES:
                if s.count(old) != 1:
                    raise SystemExit("caption line not found exactly once: " + old[:60])
                s = s.replace(old, new)
            for old in (V5.OLD_TITLE, V5.OLD_LINE2, V5.OLD_LINE3):
                if s.count(old) != 1:
                    raise SystemExit("f3d50_video caption not found once: " + old[:40])
            compile(s, "patched compose_cont", "exec")
            emit(dict(dry="caption patch compiles (every replacement found exactly once)", line4=l4, line5=l5, bit_identical=ident)); return 0
    os.makedirs(VID, exist_ok=True)
    fn = FL.compose_cont_exact(H.cap_name, names)
    res = [fn(nm, H.cap_name) for nm in names]
    r = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " video", videos=res, line4=l4, line5=l5, bit_identical=ident)
    jdump(r, H.hj("video_seat%s" % H.seat["name"]))
    emit(dict(videos=[(x["name"], x["mp4"], x["frames"], x["bytes"]) for x in res]))
    return 0


# ====================================================================== contact sheet
def cmd_sheet(a):
    H = hero_from_args(a)
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", s)
    J = jload(JUDGE52B) or {}
    conv = {int(g["n"]): int(g["conv"]["f"]) for g in J.get("groups") or [] if (g.get("conv") or {}).get("f")}
    best = pv53_best()
    frames = []
    for n in (1, 2, 3):
        frames += [conv.get(n), (best.get(n) or {}).get("frame")]
    frames = [f for f in frames if f]
    idx = {}
    for mode in ("cseat", "cprint"):
        p = H.cap + "/" + mode + "/frames.csv"
        if not os.path.exists(p):
            raise SystemExit("no capture %s: run `unity` first" % p)
        idx[mode] = {int(r["sim_frame"]): r for r in csv.DictReader(open(p, encoding="utf8"))}
    CW, CH, COLS = 640, 360, 6
    lines = ["DFG-2B-E hero (Q85): seat %s (top) and the print view (bottom) at each group's converged peak and most print-like instant" % H.seat["name"]] + H.honesty()
    TOP = 16 + 44 * len(lines)
    pv = Image.open(PV53_PNG).convert("RGB") if os.path.exists(PV53_PNG) else None
    pvh = int(pv.height * (CW * COLS) / pv.width) if pv else 0
    S = Image.new("RGB", (CW * COLS, TOP + 2 * CH + pvh + (44 if pv else 0)), (0, 0, 0))
    dr = ImageDraw.Draw(S)
    for i, l in enumerate(lines):
        dr.text((14, 8 + 44 * i), l, font=font(30 if i else 36), fill=(255, 255, 255) if i == 0 else (255, 200, 140))
    for j, f in enumerate(frames[:COLS]):
        for m, (mode, name) in enumerate((("cseat", "seat %s" % H.seat["name"]), ("cprint", "print view"))):
            r = idx[mode].get(f)
            x, y = j * CW, TOP + m * CH
            if r is None:
                dr.text((x + 10, y + 10), "frame %d not captured" % f, font=font(18), fill=(255, 120, 120)); continue
            im = Image.open(H.cap + "/" + mode + "/frame_%05d.jpg" % int(r["i"])).convert("RGB").resize((CW, CH), Image.LANCZOS)
            S.paste(im, (x, y))
            n = [k for k, v in conv.items() if v == f]
            kind = ("group %d converged peak" % n[0]) if n else ("group %d most print-like (score3 %.3f)" % (
                [k for k, b in best.items() if b["frame"] == f][0], [b["score3"] for b in best.values() if b["frame"] == f][0]))
            d2 = ImageDraw.Draw(S)
            d2.rectangle([x, y, x + CW, y + 52], fill=(0, 0, 0))
            d2.text((x + 6, y + 2), "%s  %.3f s (frame %d)" % (name, t_of(f), f), font=font(20), fill=(255, 230, 120) if m == 0 else (160, 220, 255))
            d2.text((x + 6, y + 26), kind, font=font(18), fill=(255, 230, 120) if m == 0 else (160, 220, 255))
    if pv:
        y = TOP + 2 * CH
        dr.text((14, y + 6), "pv53 of the judged run: print view | the print | section vs the print outline + ruler (the print view is always checked)",
                font=font(28), fill=(200, 255, 200))
        S.paste(pv.resize((CW * COLS, pvh), Image.LANCZOS), (0, y + 44))
    os.makedirs(VID, exist_ok=True)
    out = VID + "/FLIP3D_%s_sheet_seat_print.jpg" % H.clip_name[5:]
    S.save(out, quality=90)
    shutil.copyfile(out, HERO + "/" + os.path.basename(out))
    emit(dict(sheet=out, frames=frames, size=S.size))
    return 0


CMDS = dict(rescore=cmd_rescore, cues=cmd_cues, seatcheck=cmd_seatcheck, framing=cmd_framing, cams=lambda a: emit(dict(cams=cams_json(hero_from_args(a)))) or 0,
            export=cmd_export, unity=cmd_unity, capcheck=cmd_capcheck, video=cmd_video, sheet=cmd_sheet)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] not in CMDS:
        print(__doc__); sys.exit(1)
    sys.exit(CMDS[a[0]](a[1:]))
