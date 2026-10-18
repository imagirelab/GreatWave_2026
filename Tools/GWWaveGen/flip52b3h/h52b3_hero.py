# -*- coding: utf-8 -*-
"""FLIP52B3 DFG-2B-V HERO (prepared 2026-10-18 by a Claude subagent; the user has NOT said to switch the hero - the accepted hero stays
DFG-2B-E until the user says so): after the every-frame re-record (h52b3_long.py) - re-score, breaker cues, lips, seat clearance on every
frame, seat view (facing the lip, distance), print framing of all 3 groups, the print-stay measurement, the continuous Unity clip (seat A +
the print move, water_double_sided), the Unity captures, capture checks, captioned videos and a contact sheet (py -3.10 -B; numpy, scipy,
PIL, ffmpeg; Unity batch only in `unity`). Adapted from flip52bh/h52b_hero.py (DFG-2B-E hero, committed, NOT edited). No existing file is
edited: f3d50_export.main_long, pv53.PVRun, f3d50_video_loop.compose_cont_exact and FLIP3DBatch.BuildSceneAndCapture (through
flip3d/f3d_unity.ps1) run unchanged; their outputs are patched afterwards (the h52b_hero precedent). Run folders are read only.
Writes only: Unity/Build/FLIP52B3/hero/ (json, cameras, unity backups, sheet copy), Unity/Build/FLIP3D/clip_DFGBVr_*/ (GW45LIST1 manifest
that STREAMS the re-record's own surf files, no copy: that surf folder must stay), Unity/Build/FLIP3D/capture_DFGBVr_*/ (Unity frames),
Unity/Build/FLIP3D/video/FLIP3D_DFGBVr_* (mp4 + sheets). The accepted DFG-2B-E hero (Unity/Build/FLIP52B/hero, clip_DFGB2Er_*,
capture_DFGB2Er_*, FLIP3D_DFGB2Er_*) is never written: every output path is checked against those names (guard_out).

Honesty (every manifest, caption line and sheet): DFG-2B-V is VALID (all gates pass; G4 side 0.398 <= 0.40, tight; G2f phases -0.06 /
0.29 / 0.23 rad; G6 passes under its window RE-REGISTERED before the run [t_fn - 6.9, t_fn - 0.9] s - group 1 converged at t_fn - 4.21 s,
which the ORIGINAL window [t_fn - 4, t_fn + 2] would have failed); co-equal (frozen DFGB4 rule): NOT progress, VALID_DFGB2_LIKE_HERO_CANDIDATE
(replaces the invalid DFG-2B-E hero only after the user says so); energy: sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A; physics
only, 0.5 m Houdini FLIP; frames 1153-3001 re-recorded from checkpoint 1152 and bit-identical to the judged run (or the measured
difference); no shapes between frames.

Hero design [chosen]: the Q86 design of DFG-2B-E carried over: seat A (Unity seat_x 284, seat_z -20, eye 1.5 m, look (263.74, 6.04, 1.67),
FOV 55); fallback seat B (305, -32, 1.75, look (281.61, 3.65, -13.3)) if seat A comes within 1.0 m of the water on any frame; ONE visible
move to DFG-2B-V's group 2 most print-like instant, frame 2156 (89.79 s): -f3dmoves f2156 -f3dmovesec 6 -f3dhold 2 -f3dstay 2.5
-f3dback 6 (no white-out; the stay 2.5 s is kept because the crest leaves the print frame within +-0.5 s of DFG-2B-E's under the same rule:
`stay`); print pose = DFG-2B-V group 2's own pv53 option-D pose (273.165, 3.874, -69.068) -> (268.929, 5.301, 0), FOV 23.5. VR also needs
-f3dnocrestalign; FLIP3DExperience would by default pick group 3, so f2156 is passed explicitly.

  py -3.10 -B h52b3_hero.py rescore   <cfg|source> [--frames a-b,...]   pv53's D ruler on the run's r2, frames best +-12 per group
  py -3.10 -B h52b3_hero.py cues      <cfg|source>                      onset (judge r2 lip) / touchdown (r2 enclosed cavity) per group
  py -3.10 -B h52b3_hero.py lips      <cfg|source>                      the overturning lip (r4 SDF) at each group's print record
  py -3.10 -B h52b3_hero.py seatcheck <cfg|source> [--seat A|B]          hf + surface meshes on every frame of the play range
  py -3.10 -B h52b3_hero.py seatview  <cfg|source> [--seat A|B]          facing the lip, distance, line of sight at each print instant
  py -3.10 -B h52b3_hero.py framing   <cfg|source>                      the group-2 print pose vs crest / lip of groups 1-3
  py -3.10 -B h52b3_hero.py stay      <cfg|source>                      when the crest leaves the print frame (DFG-2B-V vs DFG-2B-E)
  py -3.10 -B h52b3_hero.py movepath  <cfg|source> [--seat A|B]          hf clearance of the camera on the move seat -> print -> seat (V vs E)
  py -3.10 -B h52b3_hero.py cams      <cfg> [--seat A|B]                 cameras JSON
  py -3.10 -B h52b3_hero.py export    <cfg> [--seat A|B] [--dry]         continuous clip (f3d50_export long) + manifest patch
  py -3.10 -B h52b3_hero.py unity     <cfg> [--seat A|B] [--jobs cseat,cprint,cmove] [--dry]   memory check, backup, Unity, restore
  py -3.10 -B h52b3_hero.py capcheck  <cfg> [--seat A|B]                 record order, schedule, camera clearance, white-out
  py -3.10 -B h52b3_hero.py video     <cfg> [--seat A|B] [--dry]         captioned mp4s (every frame says VALID + G6 note + not progress + energy)
  py -3.10 -B h52b3_hero.py sheet     <cfg> [--seat A|B]                 contact sheet: seat / print stills + the pv53 print-outline report
  'source' = a check on the judged DFGBV run itself before the re-record exists (hf / r2 every frame, r4 / surf every 3rd frame in the
  group windows); its outputs go to Unity/Build/FLIP52B3/hero/check_on_source/.
Tags: [measured] records / captures, [computed] derived here, [chosen] seat, poses, move seconds, rules.
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys, json, time, csv, io, shutil, hashlib, subprocess, contextlib, ctypes, math, struct

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

TOOL = "Tools/GWWaveGen/flip52b3h/h52b3_hero.py"
B52B3 = REPO + "/Unity/Build/FLIP52B3"
SRC_RUN = "DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"
SRC_DIR = B52B3 + "/runs/" + SRC_RUN
HERO = B52B3 + "/hero"
HERO_RID = "DFGBVr_D19B_xf272p25_in5c0p6_tp3_dp0p5_c1152_t125_long"
OUT3D = REPO + "/Unity/Build/FLIP3D"
VID = OUT3D + "/video"
PV53_DIR = REPO + "/Unity/Build/FLIP53/pv53/" + SRC_RUN
PV53_JSON = PV53_DIR + "/pv53_%s.json" % SRC_RUN
PV53_PNG = PV53_DIR + "/pv53_%s.png" % SRC_RUN
JUDGE52 = SRC_DIR + "/g52/judge_DFG.json"          # the pv53 alias of the judge (groups f / x_pk)
JUDGEV = SRC_DIR + "/g52b3/judge_DFGB4.json"
COEQ = SRC_DIR + "/g52b3/coequal_DFGB4.json"
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
UNITY_METHOD = "GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture"
FPS = 24.0
STILL = 0.0759846568107605                         # [measured] DFGBV run_c*.json still_offset (= pv53 eta0)
COMMIT_MIN_GB = 8.0                                 # [chosen] free commit memory before any Unity batch (pagefile: one 0.5 m sim at a time)
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]
# ---- the accepted DFG-2B-E hero: read only (the stay reference) and never written (guard_out)
E_RUN = REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5"
E_PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json"
E_PRINT = dict(pos=[270.3725239459851, 4.000681399583817, -71.37486248981337], look=[265.99486571327657, 5.475761891039959, 0.0], fov_v=23.5)
E_MOVE = dict(frame=2149, move=6.0, hold=2.0, stay=2.5, back=6.0)   # [chosen] the accepted DFG-2B-E hero (Q86)
E_PROTECTED = (REPO + "/Unity/Build/FLIP52B/", OUT3D + "/clip_DFGB2Er_", OUT3D + "/capture_DFGB2Er_", VID + "/FLIP3D_DFGB2Er_")

SEATS = {   # [chosen] = the DFG-2B-E hero seats (Q86 "座位 A 的距离可以"); FOV 55 = the DM1A hero precedent
    "A": dict(name="A", cls="A_front_quarter_close", x=284.0, z=-20.0, eye=1.5, look=[263.74, 6.04, 1.67], fov_v=55.0),
    "B": dict(name="B", cls="B_calm_clear_view", x=305.0, z=-32.0, eye=1.75, look=[281.61, 3.65, -13.3], fov_v=55.0),
}
PRINT = dict(group=2, pos=[273.16506241700955, 3.873849971294403, -69.06829712396033],     # [computed] DFG-2B-V group 2's own pv53 option-D pose
             look=[268.92887352673995, 5.301261445189582, 0.0], fov_v=23.5,                 # (pv53 unity.converged.cameras: DM1A composition x Hc 6.594 / 7.160)
             rule="pv53 option D (Unity/Build/FLIP50/_scratch/cameras/cameras_DM1A.json composition) scaled by DFG-2B-V group 2's Hc at its "
                  "print instant (pv53_DFGBV...json unity.converged.cameras: print_pos / print_look / print_fov_v)")
MOVE = dict(frame=2156, move=6.0, hold=2.0, stay=2.5, back=6.0)   # [chosen] the Q86 move / hold / stay / back carried over to group 2's most print-like frame
GROUP_BEST = {1: 1477, 2: 2156, 3: 2836}                          # [measured] pv53 periods[*].best.frame of the judged DFGBV run
RESCORE_HALF = 12                                                  # [chosen] best +-12 frames
CAVITY = dict(dx_back=10.0, dx_fwd=40.0, min_cells=3, z_min=-1.0, bed_pad=0.75, max_s=4.0, td_pad_frames=12)   # [chosen] touchdown rule on r2
CLEAR_MIN = 1.0                                                    # [chosen] the seat rule: eye >= 1.0 m above the water on every frame
FOOT = (4.0, 1.5)                                                  # the player's heave footprint (f3d50_export FOOT)
NEAR = 2.0                                                         # +-2 m neighbours of the seat (reported)
ASPECT = 16.0 / 9.0
VIEW_RULE = dict(phi_max_deg=80.0, dist_m=[20.0, 60.0], ndc_max=1.0)   # [chosen] = dfgb2e_seats.py (front <= 80 deg, 20-60 m) + the lip in the seat frame
STAY_RULE = dict(lat_row_m=0.5, back_m=1.0, fwd_m=4.0, max_s=8.0, low_m=1.0, ndc_edge=1.0, tol_s=0.5, keep_s=2.5, step_s=0.25)  # [chosen] before measuring
VALID_EN = ("DFG-2B-V (DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5): VALID, all gates pass (G4 side 0.398 <= 0.40, tight; G2f phases -0.06 / 0.29 / "
            "0.23 rad); G6 passes under its window RE-REGISTERED before the run [t_fn - 6.9, t_fn - 0.9] s: group 1 converged at t_fn - 4.21 s, "
            "which the ORIGINAL window [t_fn - 4, t_fn + 2] would have failed")
PROGRESS_EN = ("NOT progress (co-equal, frozen DFGB4 rule); VALID_DFGB2_LIKE_HERO_CANDIDATE: replaces the invalid DFG-2B-E hero only after "
               "the user says so")
ENERGY_EN = "energy: sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A"
NOSHAPE_EN = "no shapes between frames"
PLAN_DEV_EN = ("named deviation: re-recorded BEFORE the user's yes - the frozen plan_DFGB4_frozen.json (records.layout_choice, criteria.decision.after) "
               "put this every-frame re-record after the user's yes ('nothing is started automatically'); started because Houdini was idle (Q81: "
               "keep work moving on the recommendation); the hero is NOT switched")
PLAN_DEV_JA = ("毎コマの計算し直しは、凍らせた計画（plan_DFGB4_frozen.json の records.layout_choice と criteria.decision.after）では利用者の「はい」の後の段"
               "（自動では始めない）だったが、Houdini が空いていたので先に行った（Q81：勧めの道で仕事を止めない）。名前を付けた逸れ。主役は替えていない")


def wrap_px(text, fnt, width):
    """[computed] split text at spaces so that each piece fits width px in font fnt (a single longer word stays whole)."""
    out, cur = [], ""
    for w in str(text).split(" "):
        t = (cur + " " + w) if cur else w
        if cur and fnt.getlength(t) > width:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out or [""]


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def guard_out(p):
    """every write goes to a DFG-2B-V place; the accepted DFG-2B-E hero files are never written."""
    q = os.path.abspath(p).replace("\\", "/")
    for pre in E_PROTECTED:
        if q.lower().startswith(pre.lower()):
            raise SystemExit("refused: %s belongs to the accepted DFG-2B-E hero (read only)" % q)
    return p


def jdump(o, p):
    guard_out(p)
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
def source_cfg():
    """the stand-in cfg of a check on the judged DFGBV run itself (before the re-record exists): the source cfg with the hero window."""
    c0 = jload(SRC_DIR + "/cfg.json")
    if not c0:
        raise SystemExit("%s/cfg.json is missing" % SRC_DIR)
    c = dict(c0)
    c.update(run_id=HERO_RID, out_root=HERO + "/runs", f_start=1153, f_end=3001, still_offset_m=STILL, restart=dict(src_run=SRC_RUN, src_dir=SRC_DIR),
             _source_stand_in=True)
    return c


class Hero:
    def __init__(self, cfgp, run=None, seat="A"):
        if cfgp == "source":
            self.cfgp = "source"
            self.cfg = source_cfg()
            run = SRC_DIR
        else:
            self.cfgp = cfgp
            self.cfg = jload(cfgp)
        if not self.cfg or (self.cfg.get("restart") or {}).get("src_run") != SRC_RUN:
            raise SystemExit("%s is not a DFG-2B-V hero re-record cfg" % cfgp)
        self.rid = self.cfg["run_id"]
        self.short = self.rid.split("_")[0]                                  # DFGBVr
        self.rd = (run or (self.cfg["out_root"].rstrip("/") + "/" + self.rid)).replace("\\", "/").rstrip("/")
        self.is_source = os.path.normcase(os.path.abspath(self.rd)) == os.path.normcase(os.path.abspath(SRC_DIR))
        self.f0, self.f1 = int(self.cfg["f_start"]), int(self.cfg["f_end"])
        if seat not in SEATS:
            raise SystemExit("seat %s unknown (A or B)" % seat)
        self.seat = dict(SEATS[seat])
        tag = "%s_f%d_%d_r24_seat%s_ds" % (self.short, self.f0, self.f1, seat)
        self.clip_name = "clip_" + tag
        self.cap_name = "capture_" + tag
        self.clip = guard_out(OUT3D + "/" + self.clip_name)
        self.cap = guard_out(OUT3D + "/" + self.cap_name)
        # outputs of a check run on the JUDGED run itself (a stand-in before the re-record exists) go to hero/check_on_source/
        self.hj = lambda name: HERO + ("/check_on_source" if self.is_source else "") + "/%s_%s.json" % (name, self.rid)

    def compare(self):
        if self.is_source:                    # a check on the judged run itself: its own records and judgement (nothing to compare)
            return True, dict(source_itself=True)
        s = jload(self.rd + "/hero_compare_summary.json") or {}
        rc = jload(self.rd + "/restart_compare.json") or {}
        ident = bool(s.get("ok") is True and s.get("all_bit_identical_in_overlap") is True and rc.get("all_bit_identical") is True
                     and s.get("every_frame_surf_complete"))
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

    def valid_line(self):
        return ((self.cfg.get("case") or {}).get("hero") or {}).get("valid") or VALID_EN

    def progress_line(self):
        return ((self.cfg.get("case") or {}).get("hero") or {}).get("progress") or PROGRESS_EN

    def honesty(self):
        return [self.valid_line(), self.progress_line(), ENERGY_EN, self.physics_line(), NOSHAPE_EN]


def hero_from_args(a):
    if not a or a[0].startswith("--"):
        raise SystemExit("give the hero cfg path (or 'source')")
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


def pv53_best(path=PV53_JSON):
    """[measured] a run's pv53 per-group best frames and ruler (periods[*].best)."""
    P = jload(path) or {}
    ser = P.get("series") or {}
    out = {}
    for p in P.get("periods") or []:
        b = p.get("best") or {}
        rows = p.get("series") or ser.get(str(p["n"])) or []
        out[int(p["n"])] = dict(k=int(p["n"]), frame=int(b["frame"]), t=float(b["t"]), score3=float(b["score3"]), lip=b.get("lip"), hood=b.get("hood"),
                                x_c=b.get("x_c"), eta_c=b.get("eta_c"), scan_window=p.get("window_frames"), f_max=p.get("f_max"), x_max=p.get("x_max"),
                                Hc_print=(p.get("conv_print") or {}).get("Hc"),
                                series={int(r["frame"]): r.get("score3") for r in rows if r.get("frame") is not None})
    return out


def hf_bilinear(E, x, lat):
    """bilinear hf at plan x and lateral |lat| (cell centres at k + 0.5); NaN cells propagate."""
    x = np.asarray(x, float); z = np.abs(np.asarray(lat, float))
    fi = np.clip(x - 0.5, 0, E.shape[1] - 1.000001); fj = np.clip(z - 0.5, 0, E.shape[0] - 1.000001)
    i0 = np.floor(fi).astype(int); j0 = np.floor(fj).astype(int)
    u = fi - i0; v = fj - j0
    return (E[j0, i0] * (1 - u) * (1 - v) + E[j0, i0 + 1] * u * (1 - v) + E[j0 + 1, i0] * (1 - u) * v + E[j0 + 1, i0 + 1] * u * v)


def sdf_at(S, m, P):
    """trilinear r4 SDF (S[lat, up, x]) at points P (x, up, lateral; |lateral| mirrored); outside the box -> NaN."""
    fx = (P[:, 0] - m["x0"]) / m["dx"]; fy = (P[:, 1] - m["y0"]) / m["dy"]; fz = np.maximum((np.abs(P[:, 2]) - m["z0"]) / m["dz"], 0.0)
    ok = (fx >= 0) & (fx <= m["nx"] - 1) & (fy >= 0) & (fy <= m["ny"] - 1) & (fz <= m["nz"] - 1)
    out = np.full(len(P), np.nan)
    if ok.any():
        x, y, z = fx[ok], fy[ok], fz[ok]
        i0 = np.minimum(np.floor(x).astype(int), m["nx"] - 2); j0 = np.minimum(np.floor(y).astype(int), m["ny"] - 2)
        k0 = np.minimum(np.floor(z).astype(int), m["nz"] - 2)
        u, v, w = x - i0, y - j0, z - k0
        acc = 0.0
        for dk, wk in ((0, 1 - w), (1, w)):
            for dj, wj in ((0, 1 - v), (1, v)):
                for di, wi in ((0, 1 - u), (1, u)):
                    acc = acc + S[k0 + dk, j0 + dj, i0 + di] * wk * wj * wi
        out[ok] = acc
    return out


def los_free(A, T, E, S, m, step=0.25, skip_end=0.6, start=0.3):
    """is the segment eye A -> target T free of water? (the cam50_choose.los_batch rule: r4 SDF < 0 inside its box, else below the hf upper
    surface; the last skip_end m before the target are not tested)."""
    A = np.asarray(A, float); T = np.asarray(T, float)
    L = float(np.linalg.norm(T - A)); U = (T - A) / L
    s = np.arange(start, max(start, L - skip_end), step)
    P = A[None, :] + s[:, None] * U[None, :]
    keep = (P[:, 0] > 0.5) & (P[:, 0] < 345.0)
    P = P[keep]
    if not len(P):
        return True
    sv = sdf_at(S, m, P) if S is not None else np.full(len(P), np.nan)
    h = hf_bilinear(E, P[:, 0], P[:, 2])
    wet = np.where(np.isfinite(sv), sv < 0.0, P[:, 1] < np.nan_to_num(h, nan=-30.0))
    return bool(not wet.any())


def project(pos, look, fov_v, P):
    """(horizontal, vertical) offset of point P from the image centre in half-widths / half-heights (pinhole, Unity LookRotation, 16:9)."""
    pos, look, P = (np.asarray(v, float) for v in (pos, look, P))
    fw = look - pos; fw /= np.linalg.norm(fw)
    up0 = np.array([0.0, 1.0, 0.0])
    rt = np.cross(up0, fw); rt /= np.linalg.norm(rt)
    up = np.cross(fw, rt)
    d = P - pos
    z = float(d @ fw)
    tv = math.tan(math.radians(fov_v) / 2.0); th = tv * ASPECT
    return [round(float(d @ rt) / z / th, 4), round(float(d @ up) / z / tv, 4)]


# ====================================================================== rescore (pv53's D ruler on the run's centre section)
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
               bit_identical=ident, label=("re-record bit-identical to the judged run (or the judged run itself): the pv53 numbers hold" if ident else
                                           "NOT bit-identical (or not compared): these are the re-record's OWN numbers, labelled 'not bit-identical'"),
               rule="pv53.PVRun.measure (g46 r2_mask -> STUDY52 measure_mask -> d_shape_measure.pick -> g47_video.score3) on frames best +-%d of each "
                    "group, crest track pv53.track from the judge's summit; best = smallest score3 (pv53 tie rule) [measured]" % RESCORE_HALF,
               groups=groups, honesty_en=H.honesty(), tags="[measured] r2 ruler")
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
    sys.path.insert(0, TOOLS + "/flip52b3")
    import g52b3_common as GC                                              # bed functions (read only)
    J = jload(JUDGEV) or {}
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
        out.append(dict(k=n, onset=dict(frame=f_on, t=t_of(f_on), x=x_on, source="judge_DFGB4.json groups[%d].onset (r2 lip, every frame) [measured]" % (n - 1)),
                        touchdown=td, win_first=f_on, win_last=int(min(w1, H.f1)),
                        win_rule=("onset .. touchdown + 0.5 s" if td else "onset .. onset + 2.5 s (no enclosed pocket found: the g49 fallback)"),
                        best_frame=b.get("frame"), best_inside=bool(b.get("frame") and f_on <= b["frame"] <= w1), pv53_scan_window=b.get("scan_window")))
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " cues", run=rel(H.rd), bit_identical=ident, rule=touchdown.__doc__.strip(),
               cavity=CAVITY, cues=out, note="FLIP3DExperience cues = breaker_onset (win_first), breaker_best (frame), breaker_touchdown (win_last). "
                                             "The pv53 window_frames are scan windows, not cues.", honesty_en=H.honesty(), tags="[measured] r2 records; rule [chosen]")
    jdump(res, H.hj("cues"))
    emit(dict(cues=[(c["k"], c["win_first"], (c["touchdown"] or {}).get("frame"), c["win_last"], c["best_frame"], c["best_inside"]) for c in out],
              out=H.hj("cues")))
    return 0 if out else 1


# ====================================================================== lips (r4 SDF at each group's print record)
def lip_rows(S, xs4, up4, lat4, jmax=40):
    """per lateral row of the r4 SDF: the overturning tip = the upper of >= 2 liquid runs in a column (the dfgb2e_seats.py rule) and the air
    cells between the runs (the pocket)."""
    Lq = S < 0
    rows, pocket = [], []
    for j in range(min(jmax, S.shape[0])):
        tip = None
        for ci in range(S.shape[2]):
            idx = np.where(Lq[j, :, ci])[0]
            if len(idx) < 2:
                continue
            runs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
            if len(runs) < 2:
                continue
            top = runs[-1]
            tip = (float(xs4[ci]), float(0.5 * (up4[top[0]] + up4[top[-1]])), float(up4[top[0]]))
            for vj in range(runs[0][-1] + 1, runs[1][0]):
                pocket.append((float(xs4[ci]), float(up4[vj]), float(lat4[j])))
        if tip is not None:
            rows.append(dict(lat=float(lat4[j]), x_tip=tip[0], z_tip=tip[1], z_under=tip[2]))
    return rows, np.array(pocket).reshape(-1, 3)


def compute_lips(rd, best=None):
    R4 = rec("r4", rd)
    m4 = R4.meta
    xs4 = m4["x0"] + m4["dx"] * np.arange(m4["nx"]); up4 = m4["y0"] + m4["dy"] * np.arange(m4["ny"]); lat4 = m4["z0"] + m4["dz"] * np.arange(m4["nz"])
    best = best or pv53_best()
    have = np.array(sorted(R4.where))
    out = []
    for n, b in sorted(best.items()):
        fb = int(b["frame"])
        rec_ = int(have[int(np.argmin(np.abs(have - fb) * 2 + (have > fb)))])     # nearest r4 record, ties to the earlier (pv53 nearest_record)
        rows_all, pocket = lip_rows(R4.get(rec_), xs4, up4, lat4)
        rows = []
        for r in rows_all:                       # main lip = rows contiguous from the axis, tip within 10 m of the axis tip (drops swash spots)
            if (not rows and r["lat"] < 1.0) or (rows and r["lat"] - rows[-1]["lat"] <= 2.0 and abs(r["x_tip"] - rows[0]["x_tip"]) <= 10.0):
                rows.append(r)
            elif rows:
                break
        pocket = pocket[np.abs(pocket[:, 2]) <= (rows[-1]["lat"] + 1.0)] if (len(pocket) and rows) else pocket
        ax = rows[0] if rows else None
        out.append(dict(n=n, best_frame=fb, rec=rec_, rec_offset_frames=rec_ - fb, axis_tip=[ax["x_tip"], ax["z_tip"], 0.0] if ax else None,
                        rows=rows, rows_lat_max=max(r["lat"] for r in rows) if rows else None, pocket_cells=int(len(pocket)),
                        pocket=[[round(float(v), 2) for v in q] for q in pocket[:200]],
                        rows_dropped=[r for r in rows_all if r not in rows][:10]))
    return out


def cmd_lips(a):
    H = hero_from_args(a)
    L = compute_lips(H.rd)
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " lips", run=rel(H.rd), lips=L,
               rule="r4 SDF at the record nearest each group's pv53 best frame (ties earlier): per lateral row the upper of >= 2 liquid runs in an x "
                    "column = the overturned lip; the main lip = rows contiguous from the axis with the tip within 10 m of the axis tip (dfgb2e_seats.py "
                    "rule); coordinates (x, up, lateral) in the record frame [measured r4 -> computed]", honesty_en=H.honesty())
    jdump(res, H.hj("lips"))
    emit(dict(lips=[(l["n"], l["best_frame"], l["rec"], l["axis_tip"], l["rows_lat_max"], l["pocket_cells"]) for l in L], out=H.hj("lips")))
    return 0 if all(l["axis_tip"] for l in L) else 3


def lips_of(H):
    j = jload(H.hj("lips"))
    return {int(l["n"]): l for l in (j or {}).get("lips") or []} if j else {int(l["n"]): l for l in compute_lips(H.rd)}


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
    off = float(H.cfg.get("still_offset_m") or STILL)
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
        if f not in fi:
            continue
        P, T, t, fr = surf_points(H.rd + "/surf/s_%05d.gw45s" % f)
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
               print_cam_hold_stay_min_m=float(pc[stay].min()) if stay else None, print_pose=PRINT, move=MOVE,
               dfgb2e_hero_seatA_for_reference=dict(hf_point=1.382, near2m=0.784, mesh_eye=1.398, heave=[-1.559, 2.325], rate=3.13,
                                                    source="Unity/Build/FLIP52B/hero/seats/dfgb2e_seats_finals.json rank 1 (DFG-2B-E, 3rd-frame meshes)"),
               honesty_en=H.honesty(), tags="[measured] hf / surf records; footprint, eye model [chosen as the player]")
    res["ok"] = bool(len(frames) == H.f1 - H.f0 + 1 and res["hf_point_min_m"] >= CLEAR_MIN and res["mesh_eye_min_m"] >= CLEAR_MIN
                     and res["mesh_column_min_m"] >= CLEAR_MIN)
    res["ok_rule"] = ("every frame %d-%d: hf at the seat point, the surface mesh at the eye point (+-0.5 m) and the mesh column through the eye all "
                      ">= %.1f m below the eye [chosen = the seat search rule]; the boat-footprint and +-2 m numbers are reported" % (H.f0, H.f1, CLEAR_MIN))
    res["meshes_note"] = ("%d of %d frames have a surface mesh (%s)" % (len(mrows), H.f1 - H.f0 + 1, "the judged run: every 3rd frame in the group "
                                                                         "windows only" if H.is_source else "every frame"))
    res["footprint_below_1m"] = bool(res["mesh_footprint_min_m"] < CLEAR_MIN)
    if not lim:
        jdump(res, H.hj("seatcheck_seat%s" % seat["name"]))
    emit({k: res[k] for k in ("seat", "n_hf_frames", "n_meshes", "hf_point_min_m", "hf_point_min_frame", "hf_near2m_min_m", "mesh_eye_min_m", "mesh_footprint_min_m",
                              "mesh_footprint_min_frame", "mesh_column_min_m", "heave_range_m", "heave_rate_max_mps", "print_cam_hold_stay_min_m",
                              "print_cam_hf2m_min_m", "ok")})
    return 0 if res["ok"] else 3


# ====================================================================== seat view: facing the lip, distance, line of sight
def cmd_seatview(a):
    H = hero_from_args(a)
    import f3d_common as C
    s = H.seat
    HF = rec("hf", H.rd)
    R4 = rec("r4", H.rd)
    xs, zs = C.axes_hf(HF.meta)
    off = float(H.cfg.get("still_offset_m") or STILL)
    L = lips_of(H)
    best = pv53_best()
    base = np.array([s["x"], off + s["eye"], s["z"]])
    fwd = np.array(s["look"]) - base                                    # the seat rotation is fixed (LookRotation(seatLookAt - SeatBase)); the eye heaves
    hfov_half = math.degrees(math.atan(math.tan(math.radians(s["fov_v"]) / 2) * ASPECT))
    rows = []
    for n in sorted(L):
        l = L[n]; b = best.get(n) or {}
        f = int(l["rec"])
        hv = float(heave_series(HF, xs, zs, s, [f])[0])
        eye = base + np.array([0.0, hv, 0.0])
        tip = np.array(l["axis_tip"]) if l.get("axis_tip") else None
        crest = np.array([b["x_c"], off + b["eta_c"], 0.0]) if b else None
        sub = {}
        for nm, P in (("lip_axis_tip", tip), ("crest", crest)):
            if P is None:
                continue
            nd = project(eye, eye + fwd, s["fov_v"], P)
            sub[nm] = dict(point=[round(float(v), 3) for v in P], ndc=nd, in_frame=bool(abs(nd[0]) <= VIEW_RULE["ndc_max"] and abs(nd[1]) <= VIEW_RULE["ndc_max"]),
                           h_deg=round(float(nd[0]) * hfov_half, 2), dist_3d_m=round(float(np.linalg.norm(P - eye)), 2))
        phi = math.degrees(math.atan2(abs(s["z"]), s["x"] - tip[0])) if tip is not None else None
        los = None
        if tip is not None and f in R4.where:
            E = HF.get(f); S = R4.get(f)
            tips = [[r["x_tip"], r["z_tip"], sg * r["lat"]] for r in l["rows"] for sg in (-1.0, 1.0)]
            vis = [los_free(eye, t_, E, S, R4.meta) for t_ in tips]
            pk = np.array(l.get("pocket") or [], float).reshape(-1, 3)
            if len(pk) > 60:
                pk = pk[np.random.default_rng(0).choice(len(pk), 60, replace=False)]
            hol = [los_free(eye, [q[0], q[1], -q[2]], E, S, R4.meta, skip_end=0.3) for q in pk]
            los = dict(axis_tip_visible=bool(los_free(eye, tip, E, S, R4.meta)), lip_rows_visible_frac=round(float(np.mean(vis)), 3) if vis else None,
                       rows=len(tips), hollow_near_visible_frac=round(float(np.mean(hol)), 3) if hol else None, hollow_points=len(hol))
            los["vis"] = round(float(np.mean([float(los["axis_tip_visible"]), los["lip_rows_visible_frac"] or 0.0]
                                             + ([los["hollow_near_visible_frac"]] if hol else []))), 3)
        d = sub.get("lip_axis_tip", {}).get("dist_3d_m")
        rows.append(dict(n=n, best_frame=l["best_frame"], rec=f, t_rec=round(t_of(f), 4), heave=round(hv, 3), eye=[round(float(v), 3) for v in eye],
                         front_angle_deg=None if phi is None else round(phi, 1), dist_3d_lip_m=d, view=sub, line_of_sight=los,
                         ok=bool(phi is not None and phi <= VIEW_RULE["phi_max_deg"] and d is not None and VIEW_RULE["dist_m"][0] <= d <= VIEW_RULE["dist_m"][1]
                                 and sub["lip_axis_tip"]["in_frame"] and sub.get("crest", {}).get("in_frame", True))))
    vs = [r["line_of_sight"]["vis"] for r in rows if r.get("line_of_sight")]
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " seatview", run=rel(H.rd), seat=s, still_offset_m=off, rows=rows,
               ok=bool(rows and all(r["ok"] for r in rows)), rule=VIEW_RULE, vis_score=round(float(np.mean(vs)), 3) if vs else None,
               rule_text=("at each group's print record (the r4 record nearest its pv53 best frame): front angle phi = atan2(|seat lateral|, seat x - lip "
                          "tip x) <= 80 deg (0 = straight in front of the falling lip), 3D distance heaved eye -> axis lip tip 20-60 m, the lip tip and "
                          "the crest inside the fixed seat frame (FOV %g, 16:9) [chosen = the dfgb2e_seats.py rules]. Line of sight (r4 SDF / hf, the "
                          "cam50_choose.los_batch rule) is REPORTED as in the DFG-2B-E seat search (tip, lip rows both sides, <= 60 pocket points; "
                          "vis = their mean): no threshold there either (DFG-2B-E seat A: tip hidden in all 3 groups, vis_score 0.639)" % s["fov_v"]),
               dfgb2e_hero_seatA_for_reference=dict(front_angle_deg=[44.3, 48.8, 52.2], dist_3d_m=[29.1, 27.04, 25.78], tip_visible=[False, False, False],
                                                    lip_rows_visible=[1.0, 0.75, 1.0], vis_score=0.639,
                                                    source="Unity/Build/FLIP52B/hero/seats/dfgb2e_seats_finals.json candidates[0] (read only)"),
               honesty_en=H.honesty(), tags="[measured] hf / r4 / pv53 -> [computed] angles, distances, visibility; rules [chosen]")
    jdump(res, H.hj("seatview_seat%s" % s["name"]))
    emit(dict(seatview=[(r["n"], r["rec"], r["front_angle_deg"], r["dist_3d_lip_m"], (r["view"].get("lip_axis_tip") or {}).get("ndc"),
                         (r["line_of_sight"] or {}).get("axis_tip_visible"), (r["line_of_sight"] or {}).get("lip_rows_visible_frac"),
                         (r["line_of_sight"] or {}).get("hollow_near_visible_frac"), r["ok"]) for r in rows],
              ok=res["ok"], vis_score=res["vis_score"], out=H.hj("seatview_seat%s" % s["name"])))
    return 0 if res["ok"] else 3


# ====================================================================== print framing (pinhole, Unity LookRotation, 16:9)
def pv53_group2_pose():
    """[measured] the pv53 option-D pose of DFG-2B-V's group 2 (unity.converged = the red instant's group, print_like_frame 2156)."""
    P = jload(PV53_JSON) or {}
    u = ((P.get("unity") or {}).get("converged") or {})
    cam = u.get("cameras") or {}
    return dict(frame=u.get("print_like_frame"), pos=cam.get("print_pos"), look=cam.get("print_look"), fov_v=cam.get("print_fov_v"),
                Hc=cam.get("Hc_used"), x_c=cam.get("x_c"))


def cmd_framing(a):
    H = hero_from_args(a)
    best = pv53_best()
    L = lips_of(H)
    off = float(H.cfg.get("still_offset_m") or STILL)
    rows = []
    for n, b in sorted(best.items()):
        crest = [b["x_c"], b["eta_c"] + off, 0.0]
        tip = (L.get(n) or {}).get("axis_tip")
        rows.append(dict(k=n, frame=b["frame"], lip_rec=(L.get(n) or {}).get("rec"), crest_unity=crest, crest_ndc=project(PRINT["pos"], PRINT["look"], PRINT["fov_v"], crest),
                         lip_unity=tip, lip_ndc=project(PRINT["pos"], PRINT["look"], PRINT["fov_v"], tip) if tip else None))
    within = lambda r, lim: bool(abs(r["crest_ndc"][0]) <= lim and abs(r["crest_ndc"][1]) <= lim and (r["lip_ndc"] is None or
                                                                                                      (abs(r["lip_ndc"][0]) <= lim and abs(r["lip_ndc"][1]) <= lim)))
    g2 = [r for r in rows if r["k"] == PRINT["group"]]
    ok = bool(g2 and within(g2[0], 0.15))
    all3 = bool(len(rows) == 3 and all(within(r, 0.30) for r in rows))
    pv = pv53_group2_pose()
    pose_same = bool(pv["frame"] == MOVE["frame"] and pv["pos"] and max(abs(pv["pos"][i] - PRINT["pos"][i]) for i in range(3)) < 1e-6
                     and max(abs(pv["look"][i] - PRINT["look"][i]) for i in range(3)) < 1e-6 and float(pv["fov_v"]) == PRINT["fov_v"])
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " framing", pose=PRINT, aspect="16:9", rows=rows, ok_group2_within_0p15=ok,
               ok_all_groups_within_0p30=all3, pose_matches_pv53_group2=pose_same, pv53_group2_pose=pv,
               rule="(horizontal, vertical) offset from the image centre in half-widths / half-heights; crest = pv53 best (x_c, eta_c + still offset, "
                    "lateral 0); lip = the r4 axis tip (lips); group 2 within 0.15 (the DFG-2B-E design rule), every group within 0.30 in the single "
                    "group-2 pose [chosen]", honesty_en=H.honesty(), tags="[computed] from [measured] crest / lip")
    jdump(res, H.hj("framing"))
    emit(dict(framing=[(r["k"], r["crest_ndc"], r["lip_ndc"]) for r in rows], ok=ok, all_groups_within_0p30=all3, pose_matches_pv53_group2=pose_same))
    return 0 if (ok and pose_same) else 3


# ====================================================================== the print stay: when does the crest leave the print frame?
def crest_track(rd, f_arr, x0, pose):
    """[computed] the crest after the arrival on hf (every frame, the centre row lateral 0.5 m): each frame the highest hf point within
    [x_prev - back_m, x_prev + fwd_m] (continuity, forward-biased: the crest runs shoreward), from the pv53 best crest x at the arrival frame;
    projected into the fixed print pose. Leaves = the first frame whose crest is outside the image (|h| or |v| > 1) or lower than low_m above
    still (the crest has gone) [rule chosen before measuring]."""
    import f3d_common as C
    HF = rec("hf", rd)
    xs, zs = C.axes_hf(HF.meta)
    j = int(np.argmin(np.abs(zs - STAY_RULE["lat_row_m"])))
    rows, x = [], float(x0)
    leave, reach = None, None
    for f in range(f_arr, f_arr + int(STAY_RULE["max_s"] * FPS) + 1):
        if f not in HF.where:
            break
        e = HF.get(f)[j].astype(np.float64)
        m = (xs >= x - STAY_RULE["back_m"]) & (xs <= x + STAY_RULE["fwd_m"]) & np.isfinite(e)
        if not m.any():
            leave = leave or dict(frame=f, why="no water in the track window"); break
        i = np.where(m)[0][int(np.argmax(e[m]))]
        x, eta = float(xs[i]), float(e[i])
        nd = project(pose["pos"], pose["look"], pose["fov_v"], [x, eta, 0.0])
        rows.append((f, round(x, 2), round(eta, 3), nd[0], nd[1]))
        if reach is None and abs(nd[0]) >= 0.75:
            reach = dict(frame=f, after_arrival_s=round((f - f_arr) / FPS, 4), ndc=nd)
        if leave is None:
            out = abs(nd[0]) > STAY_RULE["ndc_edge"] or abs(nd[1]) > STAY_RULE["ndc_edge"]
            low = eta - STILL < STAY_RULE["low_m"]
            if out or low:
                leave = dict(frame=f, why="outside the image (h %.3f, v %.3f)" % (nd[0], nd[1]) if out else "crest lower than %.1f m above still (%.2f m)"
                             % (STAY_RULE["low_m"], eta - STILL))
    if leave:
        leave.update(t=round(t_of(leave["frame"]), 4), after_arrival_s=round((leave["frame"] - f_arr) / FPS, 4))
    return dict(arrival=dict(frame=f_arr, t=round(t_of(f_arr), 4), x0=x0), leave=leave, track_every_6th=rows[::6], n=len(rows),
                ndc_at_arrival=rows[0][3:] if rows else None,
                reach_0p75_half_width=reach, reach_note=("report only (added after the first measurement): the crest reaches 0.75 of the half-width "
                                                         "toward the image edge; on DFG-2B-E this is 2.54 s, about the 2.5 s stay chosen by eye on its preview"),
                at_stay_end=[r for r in rows if r[0] == f_arr + int(round(MOVE["stay"] * FPS))][:1])


def cmd_stay(a):
    H = hero_from_args(a)
    bv = pv53_best().get(2) or {}
    be = pv53_best(E_PV53).get(2) or {}
    v = crest_track(H.rd, MOVE["frame"], float(bv["x_c"]), PRINT)
    e = crest_track(E_RUN, E_MOVE["frame"], float(be["x_c"]), E_PRINT)
    dv = (v["leave"] or {}).get("after_arrival_s")
    de = (e["leave"] or {}).get("after_arrival_s")
    delta = None if (dv is None or de is None) else round(dv - de, 4)
    keep = bool(delta is not None and abs(delta) <= STAY_RULE["tol_s"])
    stay = STAY_RULE["keep_s"] if keep else (None if delta is None else round(round((STAY_RULE["keep_s"] + delta) / STAY_RULE["step_s"]) * STAY_RULE["step_s"], 2))
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " stay", run=rel(H.rd), reference_run=rel(E_RUN),
               rule=dict(STAY_RULE, text=crest_track.__doc__.strip() + " Decision: the Q86 stay 2.5 s (chosen on the DFG-2B-E preview: 'the crest "
                                                                      "leaves the print frame about 2.5 s after arrival') is KEPT if DFG-2B-V's leave delay "
                                                                      "differs from DFG-2B-E's (same rule) by <= 0.5 s; else stay = 2.5 + the difference, "
                                                                      "rounded to 0.25 s"),
               dfgb2v=dict(v, pose=PRINT, pv53_best_frame=bv.get("frame"), pv53_x_c=bv.get("x_c")),
               dfgb2e_reference=dict(e, pose=E_PRINT, pv53_best_frame=be.get("frame"), pv53_x_c=be.get("x_c"), move=E_MOVE),
               leave_after_arrival_s=dict(DFG2BV=dv, DFG2BE=de, difference_s=delta, DFG2BV_minus_2p5=None if dv is None else round(dv - STAY_RULE["keep_s"], 4)),
               keep_2p5=keep, stay_s=stay, stay_in_tool=MOVE["stay"], tool_matches=bool(stay is not None and abs(stay - MOVE["stay"]) < 1e-9),
               honesty_en=H.honesty(), tags="[measured] hf (every frame) -> [computed] crest track / projection; rule and tolerance [chosen]")
    jdump(res, H.hj("stay"))
    emit(dict(stay=dict(DFG2BV=v["leave"], DFG2BE=e["leave"], difference_s=delta, keep_2p5=keep, stay_s=stay, tool_matches=res["tool_matches"],
                        reach_0p75=[(v["reach_0p75_half_width"] or {}).get("after_arrival_s"), (e["reach_0p75_half_width"] or {}).get("after_arrival_s")],
                        at_2p5s_V_E=[v["at_stay_end"], e["at_stay_end"]]), out=H.hj("stay")))
    return 0 if res["tool_matches"] else 3


# ====================================================================== the move path: seat -> print pose -> seat (the player's blend)
def smooth01(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def move_path(rd, seat, pose, mv, off):
    """[computed] the camera on the player's move (FLIP3DPlayer: position Lerp(eye, printPos, S-curve), the eye heaving): sim seconds c from the
    arrival (the 2 s hold freezes the clock at the arrival frame with the camera at the print pose, so it adds no new position); blend =
    s((c + move)/move) before, 1 during the stay, 1 - s((c - stay)/back) after (dfgb2e_seats.py blend_at). Clearance = camera height minus hf
    (bilinear) under it; near = minus the highest hf within +-1.5 m (9 points)."""
    import f3d_common as C
    HF = rec("hf", rd)
    xs, zs = C.axes_hf(HF.meta)
    f_arr = int(mv["frame"])
    fr = [f for f in range(f_arr - int(round(mv["move"] * FPS)), f_arr + int(round((mv["stay"] + mv["back"]) * FPS)) + 1) if f in HF.where]
    P = np.array(pose["pos"], float)
    hv = heave_series(HF, xs, zs, seat, fr)
    rows = []
    for k, f in enumerate(fr):
        c = (f - f_arr) / FPS
        bl = smooth01((c + mv["move"]) / mv["move"]) if c < 0 else (1.0 if c <= mv["stay"] else 1.0 - smooth01((c - mv["stay"]) / mv["back"]))
        eye = np.array([seat["x"], off + seat["eye"] + hv[k], seat["z"]])
        Q = eye * (1 - bl) + P * bl
        E = HF.get(f).astype(np.float64)
        w = float(hf_bilinear(E, Q[0], Q[2]))
        nm = max(float(np.nan_to_num(hf_bilinear(E, Q[0] + dx, Q[2] + dz), nan=-30.0)) for dx in (-1.5, 0.0, 1.5) for dz in (-1.5, 0.0, 1.5))
        rows.append((f, round(c, 4), round(bl, 4), round(float(Q[1] - w), 3) if np.isfinite(w) else None, round(float(Q[1] - nm), 3)))
    moving = [r for r in rows if 0.0 < r[2] < 1.0]
    cl = [r for r in rows if r[3] is not None]
    worst = min(cl, key=lambda r: r[3]) if cl else None
    worst_n = min(rows, key=lambda r: r[4]) if rows else None
    worst_mv = min([r for r in moving if r[3] is not None], key=lambda r: r[3]) if moving else None
    return dict(frames=[fr[0], fr[-1]] if fr else None, n=len(rows), arrival=f_arr, move=mv, pose=pose, seat={k: seat[k] for k in ("x", "z", "eye")},
                min_clear_m=worst[3] if worst else None, min_clear_at=worst[:3] if worst else None,
                min_near_m=worst_n[4] if worst_n else None, min_near_at=worst_n[:3] if worst_n else None,
                min_clear_while_moving_m=worst_mv[3] if worst_mv else None, min_clear_while_moving_at=worst_mv[:3] if worst_mv else None,
                every_12th=rows[::12])


def cmd_movepath(a):
    H = hero_from_args(a)
    off = float(H.cfg.get("still_offset_m") or STILL)
    v = move_path(H.rd, H.seat, PRINT, MOVE, off)
    e = move_path(E_RUN, SEATS["A"], E_PRINT, E_MOVE, 0.07598474621772766)
    ok = bool(v["min_clear_m"] is not None and e["min_clear_m"] is not None and v["min_clear_m"] >= min(CLEAR_MIN, e["min_clear_m"] - 0.25))
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " movepath", run=rel(H.rd), rule=move_path.__doc__.strip(),
               dfgb2v=v, dfgb2e_reference=dict(e, run=rel(E_RUN), note="the accepted DFG-2B-E hero design (Q86), same rule"),
               ok=ok, ok_rule="DFG-2B-V's smallest hf clearance on the move path >= min(1.0 m, DFG-2B-E's - 0.25 m) [chosen: not worse than the "
                              "accepted design by more than 0.25 m]; report: the DFG-2B-E hero capture measured 0.26 m on its mesh column (capcheck)",
               honesty_en=H.honesty(), tags="[measured] hf -> [computed] path, clearances; rule [chosen]")
    jdump(res, H.hj("movepath_seat%s" % H.seat["name"]))
    emit(dict(movepath=dict(DFG2BV=[v["min_clear_m"], v["min_clear_at"], v["min_near_m"], v["min_clear_while_moving_m"]],
                            DFG2BE=[e["min_clear_m"], e["min_clear_at"], e["min_near_m"], e["min_clear_while_moving_m"]]), ok=ok,
              out=H.hj("movepath_seat%s" % H.seat["name"])))
    return 0 if ok else 3


# ====================================================================== cameras JSON + export
def cams_json(H):
    s = H.seat
    p = HERO + "/cameras_%s_seat%s.json" % (SRC_RUN.split("_")[0], s["name"])
    yaw = math.degrees(math.atan2(s["look"][0] - s["x"], s["look"][2] - s["z"]))
    d = dict(run_id=SRC_RUN, date=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " cams",
             source="seat = the DFG-2B-E hero seat (Q86, Unity/Build/FLIP52B/hero/seats/dfgb2e_seats_finals.json, read only); print = %s" % rel(PV53_JSON),
             conventions=dict(unity="FLIP3DPlayer: Unity (x, y, z) = (plan x, plan z, plan y); seat SeatBase = (seat_x, still_offset + seat_eye_m, seat_z), "
                                    "eye = SeatBase + up x heave(t); seat rotation LookRotation(seatLookAt - SeatBase), fixed. Print: printPos / printLookAt / printFovV."),
             seat=dict(plan=dict(x=s["x"], y=s["z"], lateral_abs=abs(s["z"]), eye_above_heave_m=s["eye"], cls=s["cls"]),
                       unity=dict(manifest=dict(seat_x=s["x"], seat_z=s["z"], seat_eye_m=s["eye"]), seatLookAt=s["look"], seatFovV=s["fov_v"], yaw_deg=round(yaw, 2))),
             print=dict(group=PRINT["group"], rule=PRINT["rule"], unity=dict(printPos=PRINT["pos"], printLookAt=PRINT["look"], printFovV=PRINT["fov_v"])),
             move=MOVE, honesty_en=H.honesty(), tags="[chosen] seat, FOV, move; [computed] print pose")
    jdump(d, p)
    return p


def manifest_patch(H, man, cams_path, cues, export_j):
    ident, cs = H.compare()
    s = H.seat
    man.update(cam_seat_look_at=[float(v) for v in s["look"]], cam_seat_fov_v=float(s["fov_v"]), cam_print_pos=[float(v) for v in PRINT["pos"]],
               cam_print_look_at=[float(v) for v in PRINT["look"]], cam_print_fov_v=float(PRINT["fov_v"]), cam_source_file=rel(cams_path),
               cam_source_sha256=sha(cams_path), cam_source_run=SRC_RUN,
               cam_note_ja=("座席（seat_x %.0f・seat_z %.0f・目 %.2f m と heave）と、座席の見る点・画角は DFG-2B-E の主役と同じ座席 A（Q86）【選び】。原画の視点は"
                            "DFG-2B-V の群 2 の pv53 の方案 D の構図（Hc で拡大）【計算】（%s）" % (s["x"], s["z"], s["eye"], rel(cams_path))))
    man["water_double_sided"] = True
    man["water_double_sided_ja"] = ("表示だけ：FLIP3D のプレイヤーは水を両面で描く（面の記録の穴の向こうの水の裏の面を、法線を裏返して表と同じ式で塗る）。"
                                    "記録・計算・形は変えない。穴を埋めたのではない")
    man["half_width_ja"] = ("面の記録は横 0〜97.5 m（cfg の crop_z1 = 95 m まで）。95〜140 m は横の緩和の帯で記録しない。壁ではないので並べない："
                            "-f3dtiles 0 で見る（外は計算にない平らな海）。y = 0 は計算の対称の面（写して全幅を描く）")
    man["unity_notes_ja"] = ("座席・原画の視点の値は manifest の cam_* を使う。視点の動きは -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g"
                             "（DFG-2B-V の群 2 の原画に最も近い瞬間 %.3f s に着く。白い画面は使わない）。VR では -f3dnocrestalign も付ける（crestAlign は姿勢を約 −13 m ずらす）。"
                             "FLIP3DExperience の既定は群 3 を選ぶので f%d を明示する" % (MOVE["frame"], MOVE["move"], MOVE["hold"], MOVE["stay"], MOVE["back"],
                                                                                      t_of(MOVE["frame"]), MOVE["frame"]))
    man["hero_status_ja"] = ("DFG-2B-V は判定で有効（全部の門を通る。G6 は計算の前に登録し直した窓 [t_fn − 6.9, t_fn − 0.9] s で通る：群 1 の収束は t_fn − 4.21 s で、"
                             "元の窓 [t_fn − 4, t_fn + 2] なら落ちていた）。凍らせた DFGB4 の決まりの比べでは前進ではない。主役の候補（VALID_DFGB2_LIKE_HERO_CANDIDATE）："
                             "主役は利用者が言うまで DFG-2B-E のまま。エネルギー：a² の和は DM1A と同じ 1.336 m²、水槽の中の力は DM1A の 0.23 倍。" + PLAN_DEV_JA)
    man["breakers_source"] = (("judged run %s: pv53 best frames / score3 / ruler (%s) and judge onset (%s); cue touchdown measured on the "
                               "re-record's r2 (%s). Borrowed because the re-record is bit-identical to the judged run (%s)" %
                               (SRC_RUN, rel(PV53_JSON), rel(JUDGEV), rel(H.hj("cues")), rel(H.rd + "/restart_compare.json"))) if ident else
                              ("NOT bit-identical (or not compared): the re-record's OWN r2 ruler numbers (%s, labelled 'not bit-identical') and "
                               "touchdown (%s)" % (rel(H.hj("rescore")), rel(H.hj("cues")))))
    man["hero"] = dict(name="DFG-2B-V", switched=False, switch_rule="the accepted hero stays DFG-2B-E until the user says so", plan_deviation=PLAN_DEV_EN,
                       run=rel(H.rd), source_run=SRC_RUN, bit_identical=ident, compare=cs,
                       honesty_en=H.honesty(), seat=s, print=PRINT, move=MOVE, cues=cues, tool=TOOL,
                       vr_command_hint=("FLIP3D player: -f3ddata %s -f3dtiles 0 -f3dmoves f%d -f3dmovesec %g -f3dhold %g -f3dstay %g -f3dback %g "
                                        "-f3dnocrestalign" % (H.clip, MOVE["frame"], MOVE["move"], MOVE["hold"], MOVE["stay"], MOVE["back"])),
                       export=dict((k, export_j.get(k)) for k in ("out", "records", "record_fps", "t", "play", "bytes", "print", "breakers", "heave")))
    man["notes_en"] = H.honesty()
    return man


def cmd_export(a):
    H = hero_from_args(a)
    if H.is_source:
        raise SystemExit("export needs the every-frame re-record (the judged run's surf records are every 3rd frame in windows only)")
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
    guard_out(mp)
    json.dump(man, open(mp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    he = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " export", clip=rel(H.clip), args=args, export=j, breakers=per,
              numbers_source=nums_src, bit_identical=ident, honesty_en=H.honesty())
    jdump(he, H.clip + "/hero_export.json")
    pr = (j.get("print") or {}).get("print_record_frame")
    emit(dict(out=H.clip, records=j.get("records"), record_fps=j.get("record_fps"), t=j.get("t"), print=pr,
              print_is_move_frame=bool(pr == MOVE["frame"]), breakers=j.get("breakers"), heave=j.get("heave"), bit_identical=ident,
              water_double_sided=man.get("water_double_sided")))
    return 0 if (j.get("out") and pr == MOVE["frame"]) else 4


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


def git_tracked_status():
    p = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-uno"], capture_output=True, text=True, encoding="utf8")
    return p.stdout


def cmd_unity(a):
    H = hero_from_args(a)
    jobs = opt(a, "--jobs", "cseat,cprint,cmove")
    extra = capture_args(H, jobs)
    log = "heroV_%s_seat%s" % (H.short, H.seat["name"])
    free, total = commit_free_gb()
    plan = dict(method=UNITY_METHOD, extra=extra, log=log, commit_free_gb=round(free, 2), commit_limit_gb=round(total, 2), need_gb=COMMIT_MIN_GB,
                unity_lock_exists=os.path.exists(REPO + "/Unity/Build/unity.lock"))
    if "--dry" in a:
        emit(dict(dry=plan)); return 0
    if H.is_source:
        raise SystemExit("unity needs the re-record's clip")
    if not os.path.exists(H.clip + "/manifest.json"):
        raise SystemExit("no clip %s: run `export` first" % H.clip)
    if free < COMMIT_MIN_GB:
        emit(dict(unity="skipped: commit free %.2f GB < %.1f GB" % (free, COMMIT_MIN_GB), **plan)); return 5
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = HERO + "/_unity_backup/" + stamp
    os.makedirs(bdir, exist_ok=True)
    before = {}
    for r in TRACKED:                                   # the PRE-BATCH working-tree state (not HEAD): restored byte for byte afterwards
        src = REPO + "/" + r
        dst = bdir + "/" + r.replace("/", "__")
        shutil.copyfile(src, dst)
        before[r] = sha(src)
        if sha(dst) != before[r]:
            raise SystemExit("backup copy differs: %s" % r)
    st0 = git_tracked_status()
    jdump(dict(files=before, git_status_uno=st0, date=time.strftime("%Y-%m-%d %H:%M:%S")), bdir + "/pre_batch.json")
    t0 = time.time()
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UNITY_PS1, "-Method", UNITY_METHOD, "-Log", log, "-Extra", extra,
           "-TimeoutMinutes", "90", "-LockWaitMinutes", "40"]
    out, rc = "", -1
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    finally:
        restored = {}
        for rr in TRACKED:
            dst = REPO + "/" + rr
            if not os.path.exists(dst) or sha(dst) != before[rr]:
                shutil.copyfile(bdir + "/" + rr.replace("/", "__"), dst)
            restored[rr] = sha(dst) == before[rr]
    st1 = git_tracked_status()
    line = [l for l in out.splitlines() if l.startswith("FLIP3D_UNITY ")]
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " unity", rc=rc, seconds=round(time.time() - t0, 1), unity_line=line[-1] if line else None,
               settings_changed=(line[-1].split("settings_changed=")[1].split(" ")[0] if line and "settings_changed=" in line[-1] else None),
               restored_pre_batch_state=restored, all_restored=all(restored.values()), git_status_same=st0 == st1, backup=rel(bdir), tail=out[-1500:],
               lock_released=not os.path.exists(REPO + "/Unity/Build/unity.lock"), **plan)
    jdump(res, H.hj("unity_seat%s" % H.seat["name"]))
    emit({k: res[k] for k in ("rc", "seconds", "unity_line", "settings_changed", "all_restored", "git_status_same", "backup", "lock_released")})
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
            ta = t_of(MOVE["frame"])
            o["expected"] = ("move %.2f -> arrive %.2f (frame %d), hold %g s (%d frames), stay to %.2f, back %.2f-%.2f, end %.1f"
                             % (ta - MOVE["move"], ta, MOVE["frame"], MOVE["hold"], int(MOVE["hold"] * FPS), ta + MOVE["stay"], ta + MOVE["stay"],
                                ta + MOVE["stay"] + MOVE["back"], t_of(H.f1)))
            o["arrive_ok"] = bool((o.get("arrive") or {}).get("sim_frame") == MOVE["frame"])
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
    log = OUT3D + "/logs/unity_heroV_%s_seat%s.log" % (H.short, H.seat["name"])
    lt = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    out["unity_log"] = dict(file=rel(log), cseq=[l.strip()[:400] for l in lt.splitlines() if "FLIP3D_CSEQ" in l][:6],
                            stream=[l.strip()[:300] for l in lt.splitlines() if "FLIP3D_STREAM_STATS" in l][-2:],
                            exceptions=len([l for l in lt.splitlines() if "Exception" in l]))
    m = out.get("cmove") or {}
    out["ok"] = bool(all((out.get(k) or {}).get("sim_frame_eq_first_plus_record") for k in ("cseat", "cprint", "cmove"))
                     and all((out.get(k) or {}).get("skipped_records", 1) == 0 and (out.get(k) or {}).get("back_steps", 1) == 0 for k in ("cseat", "cprint", "cmove"))
                     and m.get("frozen_frames") == int(MOVE["hold"] * FPS) and m.get("arrive_ok") is True
                     and not any((out.get(k) or {}).get("white_out") for k in ("cseat", "cprint", "cmove"))
                     and ((out.get("cseat") or {}).get("cam_col_clearance_min_m") or 0) >= CLEAR_MIN)
    out["honesty_en"] = H.honesty()
    out["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    jdump(out, H.cap + "/hero_capcheck.json")
    jdump(out, H.hj("capcheck_seat%s" % H.seat["name"]))
    emit(dict(ok=out["ok"], **{k: {kk: (out.get(k) or {}).get(kk) for kk in ("frames", "sim_frame_eq_first_plus_record", "skipped_records", "frozen_frames",
                                                                             "cam_col_clearance_min_m", "white_frac_max", "move_start_sim_t", "arrive", "leave_sim_t")}
                                for k in ("cseat", "cprint", "cmove")}))
    return 0 if out["ok"] else 7


# ====================================================================== videos (unchanged compose_cont_exact + in-memory caption lines)
def caption_lines(H):
    """the four honesty lines drawn under the three caption lines of every video frame."""
    return [H.valid_line(), H.progress_line(), ENERGY_EN + " | " + NOSHAPE_EN, H.physics_line()]


def cmd_video(a):
    H = hero_from_args(a)
    import f3d50_video_loop as FL                                            # unchanged
    V, V5 = FL.V, FL.V5
    ident, _ = H.compare()
    V5.RUN_TEXT = dict(V5.RUN_TEXT)
    # review 2026-10-18: 'a² の和 = DM1A' (not '総エネルギー': the in-tank power is 0.23 x DM1A) and short enough that the fitted title is not
    # clipped at the 12 px floor in cprint / cmove (the longer text measured 1938 / 1968 px > 1884 px)
    V5.RUN_TEXT[H.short] = ("%s：DFG-2B-V（DFG-2B-E の海に入口 n5 の位相の較正と横の帯 3 %% の弱め。a² の和 = DM1A）を 48 s の途中保存から同じ物理で計算し直し、"
                            "面を毎コマ、粒子 0.5 m。主役の候補（主役は利用者が言うまで DFG-2B-E）" % H.short)
    L = caption_lines(H)
    V.HEROV_L4, V.HEROV_L5, V.HEROV_L6, V.HEROV_L7 = L                      # in memory: copied into the exec namespace by V5.patched
    band_old = "        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))\n"
    band_new = "        dr.rectangle([0, 0, W, 222], fill=(0, 0, 0, 150))\n"
    l3_old = "        dr.text((18, 74), line3, font=_fit(line3, 19, W - 36), fill=(225, 225, 225))\n"
    l3_new = l3_old + "".join("        dr.text((18, %d), HEROV_L%d, font=_fit(HEROV_L%d, 19, W - 36), fill=(255, 200, 140))\n" % (102 + 28 * i, 4 + i, 4 + i)
                              for i in range(4))
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
            emit(dict(dry="caption patch compiles (every replacement found exactly once)", lines=L, bit_identical=ident,
                      videos_would_be=[VID + "/FLIP3D_%s_%s.mp4" % (H.clip_name[5:], n) for n in names])); return 0
    for n in names:
        guard_out(VID + "/FLIP3D_%s_%s.mp4" % (H.clip_name[5:], n))
    os.makedirs(VID, exist_ok=True)
    fn = FL.compose_cont_exact(H.cap_name, names)
    res = [fn(nm, H.cap_name) for nm in names]
    r = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " video", videos=res, lines=L, bit_identical=ident)
    jdump(r, H.hj("video_seat%s" % H.seat["name"]))
    emit(dict(videos=[(x["name"], x["mp4"], x["frames"], x["bytes"]) for x in res]))
    return 0


# ====================================================================== contact sheet
def cmd_sheet(a):
    H = hero_from_args(a)
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", s)
    J = jload(JUDGEV) or {}
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
        idx[mode] = {}
        for r in csv.DictReader(open(p, encoding="utf8")):
            idx[mode].setdefault(int(r["sim_frame"]), r)
    CW, CH, COLS = 640, 360, 6
    lines = ["DFG-2B-V hero candidate: seat %s (top) and the print view (bottom) at each group's converged peak and most print-like instant "
             "(NOT the hero until the user says so)" % H.seat["name"]] + H.honesty() + [PLAN_DEV_EN]
    # review 2026-10-18: wrap every header line to the sheet width (the VALID line measured 4975 px at 30 px > 3826 px: its G6 note was cut)
    rows_h = []
    for i, l in enumerate(lines):
        fnt = font(30 if i else 34)
        for j, piece in enumerate(wrap_px(l, fnt, CW * COLS - 28 - 40)):
            rows_h.append((("    " if j else "") + piece, fnt, (255, 255, 255) if i == 0 else (255, 200, 140)))
    TOP = 16 + 44 * len(rows_h)
    pv = Image.open(PV53_PNG).convert("RGB") if os.path.exists(PV53_PNG) else None
    pvh = int(pv.height * (CW * COLS) / pv.width) if pv else 0
    S = Image.new("RGB", (CW * COLS, TOP + 2 * CH + pvh + (44 if pv else 0)), (0, 0, 0))
    dr = ImageDraw.Draw(S)
    for i, (l, fnt, col) in enumerate(rows_h):
        dr.text((14, 8 + 44 * i), l, font=fnt, fill=col)
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
        dr.text((14, y + 6), "pv53 of the judged DFG-2B-V run: print view | the print | section vs the print outline + ruler (the print view is always checked)",
                font=font(28), fill=(200, 255, 200))
        S.paste(pv.resize((CW * COLS, pvh), Image.LANCZOS), (0, y + 44))
    os.makedirs(VID, exist_ok=True)
    out = guard_out(VID + "/FLIP3D_%s_sheet_seat_print.jpg" % H.clip_name[5:])
    S.save(out, quality=90)
    shutil.copyfile(out, guard_out(HERO + "/" + os.path.basename(out)))
    emit(dict(sheet=out, frames=frames, size=S.size))
    return 0


CMDS = dict(rescore=cmd_rescore, cues=cmd_cues, lips=cmd_lips, seatcheck=cmd_seatcheck, seatview=cmd_seatview, framing=cmd_framing, stay=cmd_stay,
            movepath=cmd_movepath,
            cams=lambda a: emit(dict(cams=cams_json(hero_from_args(a)))) or 0,
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
