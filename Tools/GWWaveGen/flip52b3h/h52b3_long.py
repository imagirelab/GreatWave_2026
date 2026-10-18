# -*- coding: utf-8 -*-
"""FLIP52B3 DFG-2B-V HERO RE-RECORD (prepared 2026-10-18 by a Claude subagent; the user has NOT said to switch the hero): the every-frame
re-record of the judged VALID run DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5 from its checkpoint v.1152 (47.958 s) to 125 s, for the Unity
FLIP3D player (py -3.10 -B; numpy + scipy in compare, no Houdini here). Adapted from flip52bh/h52b_long.py (DFG-2B-E hero, committed,
NOT edited): paths -> Build/FLIP52B3, the precheck -> flip52b3/g52b3_pcfg.py with the long_* replacements, the chain -> flip52b3/
g52b3_chain.py, the still offset -> DFGBV's run_c*.json, no G52B_SEA (the DFG-2B-V sea is built into g52b3_common), no 'known' module
difference (every runtime module must equal the DFGBV chain-start hashes).

What it is (and is not): the SAME physics recomputed from the judged run's own checkpoint with records written every frame (r4 SDF and the
surface r5; hf, r2, r3 were already every frame). Every frame 1153-3001 exists in the judged run, so the overlap is compared bit for bit
(hf / r2 / r3 / volcorr on 1849 frames, surf bytes and r4 SDF on the 339 common frames) and the compare is STRICT: the overlap must be
COMPLETE (a partial or empty overlap fails; g49_restart.compare alone counts only the common frames).
DFG-2B-V is judged VALID (all gates pass; G4 side 0.398 <= 0.40, tight; G2f phases -0.06 / 0.29 / 0.23 rad; G6 passes under its window
RE-REGISTERED before the run [t_fn - 6.9, t_fn - 0.9] s: group 1 converged at t_fn - 4.21 s, which the ORIGINAL window [t_fn - 4, t_fn + 2]
would have failed). Co-equal (frozen DFGB4 rule): NOT progress; verdict VALID_DFGB2_LIKE_HERO_CANDIDATE (replaces the invalid DFG-2B-E hero
only after the user says so). Energy (Q84): sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A. Every cfg / label says so.

No existing file is edited. Read only, imported unchanged: flip52b3/g52b3_common.py (constants), flip52b3/g52b3_pcfg.py (precheck),
flip52b3/g52b3_chain.py (only its gate() is read and run alone, dry), flip49/g49_restart.py (seed / compare with its module global GC replaced
in memory by a shim whose B49 is Build/FLIP52B3: src = Build/FLIP52B3/runs/<src>, dst = <out_root>/<run_id>, the 'under Build/...' guard),
flip50g2/g50g2_cont.py (cost / still_offset helpers). The source run folder is read only. Writes: Unity/Build/FLIP52B3/hero/cfg/<run_id>.json
(cfg; never runs/ready) and, through seed / the chain / compare, only the NEW run folder Unity/Build/FLIP52B3/hero/runs/<run_id>/ (all of
Unity/Build is git-ignored). The accepted DFG-2B-E hero (Unity/Build/FLIP52B/hero, clip_DFGB2Er_*) is never touched.

  py -3.10 -B h52b3_long.py cfg       [--t_from=48] [--t_end=125] [--ckpt=auto|<k>] [--max_hours=auto|<h>] [--dry] [--out=<cfg folder>]
  py -3.10 -B h52b3_long.py selfcheck <cfg>
  py -3.10 -B h52b3_long.py gate      <cfg>        (g52b3_chain.py's own gate() run alone + selfcheck; nothing launched, no folder made)
  py -3.10 -B h52b3_long.py seed      <cfg>        (g49_restart.seed: v.1152, volcorr ref.json / vd_01152 / vd_01153 / state rows f <= 1152)
  chain:  py -3.10 Tools/GWWaveGen/flip52b3/g52b3_chain.py <cfg>   (unchanged; printed by `cfg`)
  py -3.10 -B h52b3_long.py compare   <cfg>        (g49_restart.compare -> restart_compare.json + hero_compare_summary.json; rc 0 only if
                                                    complete and bit-identical)
Tags: [measured] run records, [computed] derived here, [guess], [chosen].
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys, json, copy, glob, time, ast, math, types, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
T52B3, T50G2, T49, T46 = (REPO + "/Tools/GWWaveGen/" + s for s in ("flip52b3", "flip50g2", "flip49", "flip46"))
for _p in (T52B3, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _p in (T50G2, T49, T46):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                  # noqa: E402
import g52b3_common as GC           # noqa: E402  read only
import g52b3_pcfg as PCF            # noqa: E402  read only (precheck)
import g50g2_cont as G2             # noqa: E402  read only (cost, still_offset)

B52B3 = GC.B52B3
SRC_RUN = "DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"
SRC_DIR = B52B3 + "/runs/" + SRC_RUN
HERO = B52B3 + "/hero"
CFG_DIR = HERO + "/cfg"
OUT_ROOT = HERO + "/runs"
CHAIN = T52B3 + "/g52b3_chain.py"
JUDGE = SRC_DIR + "/g52b3/judge_DFGB4.json"
COEQ = SRC_DIR + "/g52b3/coequal_DFGB4.json"
T_FROM_S, T_END_S = 48.0, 125.0      # [chosen] = the DFG-2B-E hero window (Q86): every frame of 48-125 s exists in the judged run -> fully comparable
CKPT_EVERY = 48                      # [chosen] as the DFG-2B-E / DM1A heroes (one checkpoint ~0.20 GB; a relaunch redoes <= 47 frames)
CKPT_LIST = [48, 24]
WALL_S = 1740.0                      # launches <= 29 min (g52b3_chain)
MAX_BACK_S = 10.0                    # [chosen] the checkpoint may lie at most 10 s before t_from
MH_FACTOR, MH_ADD = 1.2, 0.25        # [chosen] max_hours = measured estimate x 1.2 + 0.25 h, rounded up to 0.25 h (the h50 / h52b rule)
DISK_MARGIN_GB = 20.0                # [chosen] free space after the run >= the chain's stop line 25 GB + 20 GB
SUFFIX = "_long"
STILL_OFFSET_EXPECT = 0.0759846568107605   # [measured] every run_c*.json of DFGBV (online in c00001, then restored)
POP_TOP = ("hip_sha256", "module_shas_at_chain_start", "precheck")
ALLOWED_TOP = {"run_id", "out_root", "f_start", "f_first", "f_end", "t_end_s", "still_offset_m", "ckpt_every", "ckpt_list", "wall_limit_s",
               "max_hours", "pstats_frames", "note", "restart", "precheck"}
ALLOWED_REMOVED = set(POP_TOP)
ALLOWED_PATHS = {"records.r4.every", "records.r5.every", "records.windows"}
ALLOWED_CASE = {"judged", "role", "restart_of", "restart_ckpt_frame", "windows_source", "hero"}
PHYS_KEYS = ("stage", "kind", "layout", "parms", "box", "bed", "sf", "dir", "wave", "drift", "solver", "gauges", "level_regions", "dir_check",
             "level_guard_m", "level_box", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "analysis", "disk_stop_free_gb")
# the keys of g52b3_pcfg.SAME_AS_DFGBE_KEYS a re-record changes on purpose (the restart window, its checkpoints and time budget)
RESTART_KEYS = ("f_start", "f_first", "ckpt_list", "pstats_frames", "max_hours", "wall_limit_s", "ckpt_every")
REPLACEABLE = dict(
    records_as_designed="g52b3_pcfg's records rule of the JUDGED DFG-2B-V run (r4 / r5 every 3rd frame in the three group windows); this cfg is "
                        "the hero re-record whose records are every frame on purpose (long_records_every_frame)",
    records_equal_DFGBE="the judged run's records equal DFG-2B-E's judged layout; the re-record differs exactly in r4.every / r5.every / windows "
                        "(long_records_equal_source_except_every_frame)",
    blocks_equal_DFGBE="the judged run's f_start / f_first / ckpt_list / pstats_frames equal DFG-2B-E's; a re-record from checkpoint 1152 changes "
                       "exactly those restart keys (long_blocks_equal_DFGBE_except_restart_keys checks every other block)",
    max_hours_equal_DFGBE="max_hours of a JUDGED run = DFG-2B-E's 3.0 h; the hero re-record's max_hours is the measured cost x 1.2 + 0.25 h "
                          "(long_measured_est_le_max_hours): a named difference (hero re-record, not a judged run)",
    time_within_max_hours="g52b3_pcfg's time model of a judged run (DFG-2B-E rate, surface every 3rd frame in windows) underestimates every-frame "
                          "surface writing (2.96 s per frame [measured on DFGBV]); replaced by the source's own measured cost "
                          "(long_measured_est_le_max_hours)")
NAME = "DFG-2B-V"
VALID_EN = ("DFG-2B-V (DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5): VALID, all gates pass (G4 side 0.398 <= 0.40, tight; G2f phases -0.06 / 0.29 / "
            "0.23 rad); G6 passes under its window RE-REGISTERED before the run [t_fn - 6.9, t_fn - 0.9] s: group 1 converged at t_fn - 4.21 s, "
            "which the ORIGINAL window [t_fn - 4, t_fn + 2] would have failed")
PROGRESS_EN = ("NOT progress (co-equal, frozen DFGB4 rule); VALID_DFGB2_LIKE_HERO_CANDIDATE: replaces the invalid DFG-2B-E hero only after "
               "the user says so")
ENERGY_EN = "energy: sum a^2 = DM1A's 1.336 m^2 (equal spectral energy, Q84), in-tank power 0.23 x DM1A (AM-DFGB1b)"
PLAN_DEV_EN = ("named deviation: re-recorded BEFORE the user's yes - the frozen plan_DFGB4_frozen.json (records.layout_choice, criteria.decision.after) "
               "put this every-frame re-record after the user's yes ('nothing is started automatically'); started because Houdini was idle (Q81: "
               "keep work moving on the recommendation); the hero is NOT switched")


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=float)


def jload(p):
    try:
        return json.load(open(p, encoding="utf8"))
    except Exception:
        return None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


def ckpt_frames(rd):
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def chain_segment(ls):
    """the last chain start..end segment of a chain.log (g52b3_chain writes '... chunk <f0> ... stopped None ...' for the launch that reached f_end)."""
    if not ls:
        return dict(state="absent", max_hours_stop=False, last="")
    ends = [i for i, l in enumerate(ls) if " chain end " in l]
    starts = [i for i, l in enumerate(ls) if " chain start " in l]
    gates = [i for i, l in enumerate(ls) if "gate failed" in l]
    if gates and gates[-1] > max(ends + starts + [-1]):
        return dict(state="gate_failed", max_hours_stop=False, last=ls[-1])
    if not ends or (starts and starts[-1] > ends[-1]):
        return dict(state="running", max_hours_stop=False, last=ls[-1])
    seg = ls[(starts[-1] if starts else 0):]
    done = any(" stopped None " in (l + " ") for l in seg if " chunk " in l)
    mh = any("max_hours exceeded" in l for l in seg)
    return dict(state="complete" if done else "incomplete", max_hours_stop=bool(mh and not done), last=ls[-1])


def frames_done(rd):
    best = 0
    for p in glob.glob(os.path.join(rd, "run_c*.json")):
        try:
            best = max(best, int((jload(p) or {}).get("f_end_done") or 0))
        except Exception:
            pass
    return best


def paths_diff(a, b, pre=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            p = (pre + "." + k) if pre else k
            if k not in a:
                out.append(("added", p))
            elif k not in b:
                out.append(("removed", p))
            else:
                out += paths_diff(a[k], b[k], p)
        return out
    return [] if canon(a) == canon(b) else [("changed", pre)]


def getp(d, p):
    for k in p.split("."):
        if not isinstance(d, dict) or k not in d:
            return "<absent>"
        d = d[k]
    return d


def allowed(kind, p):
    top = p.split(".")[0]
    if top in ALLOWED_TOP:
        return True
    if kind == "removed" and p in ALLOWED_REMOVED:
        return True
    if p in ALLOWED_PATHS:
        return True
    if top == "case" and len(p.split(".")) >= 2 and p.split(".")[1] in ALLOWED_CASE:
        return True
    return False


def source_diff(c0, c):
    d = paths_diff(c0, c)
    bad = ["%s %s" % (k, p) for k, p in d if not allowed(k, p)]
    return dict(ok=not bad, changed=["%s %s" % (k, p) for k, p in d if not p.startswith("precheck")], unexpected=bad,
                rule="every key of the source cfg.json is canonical-JSON equal except ALLOWED_TOP / ALLOWED_PATHS / the case labels "
                     "(judged, role, restart_of, restart_ckpt_frame, windows_source, hero) / removed chain-written keys (hip_sha256, "
                     "module_shas_at_chain_start, precheck)")


def diff_table(c0, c):
    """old -> new of every changed path (the printed cfg diff; long values cut)."""
    rows = []
    for k, p in paths_diff(c0, c):
        if p.startswith("precheck"):
            continue
        a, b = getp(c0, p), getp(c, p)
        sa, sb = json.dumps(a, ensure_ascii=False, default=float), json.dumps(b, ensure_ascii=False, default=float)
        rows.append(dict(kind=k, path=p, old=sa if len(sa) <= 160 else sa[:157] + "...", new=sb if len(sb) <= 160 else sb[:157] + "..."))
    return rows


def disk_est(rd0, n_frames, n_launches):
    """bytes per frame of the source's own records [measured] x frames [computed]; npz blocks of overlapping launches kept twice (<= 47 frames
    per relaunch); checkpoints every 48 frames at the mean size of the source's last 5."""
    per = {}
    for kind in ("hf", "r2", "r3", "r4"):
        nb, nf = 0, 0
        for p in glob.glob(os.path.join(rd0, "%s_c*_b*.npz" % kind)):
            try:
                with np.load(p, allow_pickle=True) as d:
                    nf += len(d["frames"])
                nb += os.path.getsize(p)
            except Exception:
                pass
        per[kind] = nb / nf if nf else 0.0
    sf = sorted(glob.glob(os.path.join(rd0, "surf", "s_*.gw45s")))[-100:]
    per["surf"] = float(np.mean([os.path.getsize(p) for p in sf])) if sf else 2.5e6
    cks = sorted(glob.glob(os.path.join(rd0, "ckpt", "v.*.sim")))[-5:]
    ck_b = float(np.mean([os.path.getsize(p) for p in cks])) if cks else 2.1e8
    n_ck = int(math.ceil(n_frames / float(CKPT_EVERY))) + 1
    redo = max(0, n_launches - 1) * (CKPT_EVERY - 1)
    rec = sum(per.values()) * n_frames + (per["hf"] + per["r2"] + per["r3"] + per["r4"]) * redo
    tot = rec + ck_b * n_ck
    return dict(bytes_per_frame={k: round(v) for k, v in per.items()}, ckpt_bytes=round(ck_b), n_ckpt=n_ck, redo_frames=redo,
                records_gb=round(rec / 1e9, 2), ckpt_gb=round(ck_b * n_ck / 1e9, 2), total_gb=round(tot / 1e9, 2),
                tag="[measured] source bytes per frame / checkpoint size x [computed] frames; surf files of a redone frame are overwritten")


def volcorr_rows(vdir):
    rows = set()
    p = os.path.join(vdir, "state.jsonl")
    if os.path.exists(p):
        for ln in open(p, encoding="utf8"):
            try:
                rows.add(int(json.loads(ln)["f"]))
            except Exception:
                pass
    return rows


def judge_texts():
    """the VALID line from the source's own judge (g52b3/judge_DFGB4.json) and co-equal verdict [measured]; the fixed text if unreadable."""
    J = jload(JUDGE) or {}
    Q = jload(COEQ) or {}
    out = dict(valid_text=VALID_EN, progress_text=PROGRESS_EN, valid=J.get("valid"), failed=J.get("failed_gates"),
               progress=Q.get("progress"), hero_cls=(Q.get("hero_candidate") or {}).get("cls"),
               source="Unity/Build/FLIP52B3/runs/%s/g52b3/judge_DFGB4.json + coequal_DFGB4.json" % SRC_RUN)
    try:
        pn = J["G2f"]["per_n"]
        g4 = J["G4"]
        g1 = [g for g in J["groups"] if int(g["n"]) == 1][0]
        dt = float(g1["conv"]["t"]) - float(g1["t_fn"])
        if not (-6.9 <= dt <= -0.9 and dt < -4.0):
            raise ValueError("group 1 conv - t_fn = %.3f s: not the measured 'inside the re-registered window, outside the original' case" % dt)
        out["valid_text"] = ("DFG-2B-V (%s): VALID, all gates pass (G4 side %.3f <= %.2f, tight; G2f phases %.2f / %.2f / %.2f rad); G6 passes under "
                             "its window RE-REGISTERED before the run [t_fn - 6.9, t_fn - 0.9] s: group 1 converged at t_fn - %.2f s, which the "
                             "ORIGINAL window [t_fn - 4, t_fn + 2] would have failed"
                             % (SRC_RUN, float(g4["kA_side_max"]), float(g4["kA_max"]), float(pn["n3"]["phase_err_rad"]),
                                float(pn["n4"]["phase_err_rad"]), float(pn["n5"]["phase_err_rad"]), -dt))
        out["g1_conv_minus_tfn_s"] = round(dt, 3)
    except Exception as e:
        out["valid_text_error"] = repr(e)[:200]
    return out


# ====================================================================== cfg
def build(o):
    rd0 = SRC_DIR
    c0 = jload(rd0 + "/cfg.json")
    if not c0:
        raise SystemExit("%s/cfg.json is missing or unreadable" % rd0)
    if c0.get("run_id") != SRC_RUN or (c0.get("dir") or {}).get("set") != GC.SET or c0.get("kind") != "3d":
        raise SystemExit("the hero re-record continues DFG-2B-V (%s, set %s) only, not %s" % (SRC_RUN, GC.SET, c0.get("run_id")))
    if c0.get("restart"):
        raise SystemExit("%s is itself a re-record" % c0.get("run_id"))
    t_from = float(o.get("t_from", T_FROM_S))
    t_end = float(o.get("t_end", T_END_S))
    f_want = int(GC.frames_for(0.0, t_from))
    f_end = int(GC.frames_for(0.0, t_end))
    cks = ckpt_frames(rd0)
    if str(o.get("ckpt", "auto")) == "auto":
        le = [v for v in cks if v <= f_want - 1]
        if not le:
            raise SystemExit("no checkpoint at or before frame %d (%.3f s) in %s/ckpt" % (f_want - 1, t_from, rd0))
        k = le[-1]                                        # [chosen] the latest checkpoint at or before t_from (fewest warm-up frames)
    else:
        k = int(o["ckpt"])
    f_from = k + 1
    t_from_k = (f_from - 1) / 24.0
    T = float(c0["sf"]["T"])                              # 7 s (the descriptor's middle harmonic; g52b3_run NT = round(sf.T x 24) = 168)
    nT = int(round(T * 24))
    short = c0["run_id"].split("_")[0]
    rest = "_".join(c0["run_id"].split("_")[1:])
    rid = "%sr_%s_c%04d_t%s%s" % (short, rest, k, GC.tag(t_end), SUFFIX)
    off, off_src = G2.still_offset(rd0, f_from)
    src_f_end = int(c0["f_end"])
    src_done = frames_done(rd0)
    wl = c0.get("wall_limit_s", 1740)
    wl = wl if float(wl) <= WALL_S else 1740
    est = G2.cost(rd0, k, f_end, every_frame_surf=True, wall_limit=float(wl), sp=CKPT_EVERY)
    if str(o.get("max_hours", "auto")) == "auto":
        th = est.get("total_h")
        mh = math.ceil(((float(th) if th is not None else 3.5) * MH_FACTOR + MH_ADD) * 4.0) / 4.0
    else:
        mh = float(o["max_hours"])
    jt = judge_texts()
    c = copy.deepcopy(c0)
    for k_ in POP_TOP:
        c.pop(k_, None)
    c.update(run_id=rid, out_root=OUT_ROOT, f_start=f_from, f_first=f_from, f_end=f_end, t_end_s=t_end, still_offset_m=off,
             ckpt_every=CKPT_EVERY, ckpt_list=list(CKPT_LIST), wall_limit_s=wl, max_hours=mh, pstats_frames=[f_from, f_end])
    c["records"]["r4"]["every"] = 1
    c["records"]["r5"]["every"] = 1
    c["records"]["windows"] = [[t_from_k, t_end]]
    cs = c["case"]
    beyond = [max(src_done, k) + 1, f_end] if f_end > src_done else None
    cs.update(judged=False,
              role=("hero every-frame RE-RECORD of the judged VALID DFG-2B-V run (prepared 2026-10-18; NOT judged, same physics; the hero "
                    "switches from DFG-2B-E only on the user's word)"),
              restart_of=c0["run_id"], restart_ckpt_frame=k,
              windows_source="every frame %d-%d (r4, r5; hf, r2, r3 as before)" % (f_from, f_end),
              hero=dict(q="Q81 (keep work moving on the recommendation) / Q85 / Q86 (seat A, the DFG-2B-E hero design)", name=NAME,
                        switch="NOT switched: the accepted hero stays DFG-2B-E (Unity/Build/FLIP52B/hero, clip_DFGB2Er_*) until the user says so",
                        plan_deviation=PLAN_DEV_EN,
                        valid=jt["valid_text"], progress=jt["progress_text"], judge_source=jt["source"], energy=ENERGY_EN,
                        physics="physics only, 0.5 m Houdini FLIP; frames %d-%d recomputed from checkpoint v.%04d of %s with the same settings; "
                                "no shapes between frames" % (f_from, f_end, k, c0["run_id"]),
                        tool="Tools/GWWaveGen/flip52b3h/h52b3_long.py cfg",
                        args=dict(t_from=t_from, t_end=t_end, ckpt=str(o.get("ckpt", "auto")), max_hours=str(o.get("max_hours", "auto"))),
                        source_f_end=src_f_end, source_frames_done=src_done, source_t_end_s=float(c0["t_end_s"]),
                        compared_frames=[f_from, min(f_end, src_done)], beyond_source_frames=beyond,
                        max_hours_note="max_hours %.2f h > the plan's 3.0 h cap for JUDGED runs: named difference (hero re-record, not a judged run)" % mh))
    ck_src = os.path.join(rd0, "ckpt", "v.%04d.sim" % k).replace("\\", "/")
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=k, ckpt_t_s=(k - 1) / 24.0, ckpt_file=ck_src,
                        ckpt_bytes=os.path.getsize(ck_src) if os.path.exists(ck_src) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip52b3h/h52b3_long.py seed <cfg> (g49_restart.seed, Build/FLIP52B3 in memory)",
                        compare="py -3.10 -B Tools/GWWaveGen/flip52b3h/h52b3_long.py compare <cfg>")
    c["note"] = ("%s hero every-frame re-record (flip52b3h, 2026-10-18; NOT judged; NOT yet the hero: the switch from DFG-2B-E happens only on the "
                 "user's word): from checkpoint v.%04d (%.3f s) of %s with the same settings, %.3f-%g s (frames %d-%d), surface (r5) and r4 every "
                 "frame, new folder %s/%s; shape not changed (physics only). %s. %s. %s. %s"
                 % (short, k, (k - 1) / 24.0, c0["run_id"], t_from_k, t_end, f_from, f_end, OUT_ROOT.replace(REPO + "/", ""), rid,
                    jt["valid_text"], jt["progress_text"], ENERGY_EN, PLAN_DEV_EN))
    # ---------------------------------------------------------------- precheck: g52b3_pcfg's own + the long_* checks
    pc = PCF.precheck(c)
    ck = pc["checks"]
    for nm, why in REPLACEABLE.items():
        if nm in ck:
            pc.setdefault("replaced", {})[nm] = dict(value=ck[nm], why=why, plan_time=pc.get("time"))
            ck.pop(nm)
    others = [os.path.getsize(p) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim"))]
    J = jload(JUDGE) or {}
    Q = jload(COEQ) or {}
    ck["long_source_is_DFGBV"] = bool(c0["run_id"] == SRC_RUN == GC.run_id("main") and (c0.get("dir") or {}).get("set") == GC.SET
                                      and (c0.get("case") or {}).get("plan_frozen") == GC.PLAN_REL)
    ck["long_source_judged_valid"] = bool(J.get("valid") is True and not J.get("failed_gates") and (J.get("run_complete") or {}).get("ok") is True
                                          and (Q.get("hero_candidate") or {}).get("cls") == "VALID_DFGB2_LIKE_HERO_CANDIDATE")
    ck["long_ckpt_exists_full_size"] = bool(k in cks and others and os.path.getsize(ck_src) >= 0.5 * float(np.median(others)))
    ck["long_ckpt_near_t_from"] = bool(k <= f_want - 1 and (f_want - 1 - k) <= MAX_BACK_S * 24)
    seg = chain_segment(open(rd0 + "/chain.log", encoding="utf8", errors="replace").read().splitlines() if os.path.exists(rd0 + "/chain.log") else [])
    ck["long_source_chain_complete"] = bool(seg["state"] == "complete" and src_done >= src_f_end)
    launch_cfgs = sorted(glob.glob(os.path.join(rd0, "cfg_c*.json")))
    same = [all(canon((jload(p) or {}).get(kk)) == canon(c.get(kk)) for kk in PHYS_KEYS) for p in [rd0 + "/cfg.json"] + launch_cfgs]
    ck["long_physics_same_as_run_all_launches"] = bool(same and all(same))
    ck["long_hip_same_as_run"] = bool(os.path.exists(GC.HIP) and GC.sha256_file(GC.HIP) == c0.get("hip_sha256"))
    m_now = GC.module_shas()
    m_run = c0.get("module_shas_at_chain_start") or {}
    mdiff = {kk: [m_run.get(kk), m_now.get(kk)] for kk in sorted(set(m_run) | set(m_now)) if m_now.get(kk) != m_run.get(kk)}
    ck["long_runtime_modules_same_as_source_chain"] = bool(m_run and not mdiff)
    try:
        ref = jload(PCF.DFGBE_READY) or {}
        bk = [kk for kk in PCF.SAME_AS_DFGBE_KEYS if kk not in RESTART_KEYS and canon(ref.get(kk)) != canon(c.get(kk))]
        ck["long_blocks_equal_DFGBE_except_restart_keys"] = bool(ref and not bk)
        pc.setdefault("long_detail", {})["blocks_diff_vs_DFGBE_except_restart_keys"] = bk
    except Exception as e:
        ck["long_blocks_equal_DFGBE_except_restart_keys"] = False
        pc.setdefault("long_detail", {})["blocks_error"] = repr(e)[:200]
    rec0 = copy.deepcopy(c0["records"])
    rec1 = copy.deepcopy(c["records"])
    for d_ in (rec0, rec1):
        d_.get("r4", {}).pop("every", None); d_.get("r5", {}).pop("every", None); d_.pop("windows", None)
    ck["long_records_equal_source_except_every_frame"] = bool(canon(rec0) == canon(rec1))
    dst = os.path.join(OUT_ROOT, rid).replace("\\", "/")
    launched = sorted(glob.glob(os.path.join(dst, "run_c*.json"))) + ([dst + "/chain.log"] if os.path.exists(dst + "/chain.log") else [])
    if not launched:
        ck["long_new_folder"] = bool(rid != c0["run_id"] and not os.path.exists(os.path.join(dst, "run.json")))
    else:                       # adopt / resume: the folder already holds THIS cfg's chain (cfg.json = this cfg + the chain-written keys)
        rc_ = jload(dst + "/cfg.json") or {}
        strip = lambda d: {k_: v_ for k_, v_ in d.items() if k_ not in ("precheck", "hip_sha256", "module_shas_at_chain_start")}
        ck["long_existing_run_is_this_cfg"] = bool(rid != c0["run_id"] and canon(strip(rc_)) == canon(strip(c)))
    wins = c["records"]["windows"]
    heavy = sum(1 for f in range(f_from, f_end + 1) if any(a - 1e-9 <= (f - 1) / 24.0 <= b + 1e-9 for a, b in wins))
    ck["long_records_every_frame"] = bool(int(c["records"]["r5"]["every"]) == 1 and int(c["records"]["r4"]["every"]) == 1
                                          and heavy == f_end - f_from + 1 and c["records"].get("r2") and c["records"].get("r3_z") == c0["records"].get("r3_z"))
    ck["long_still_offset_from_run"] = bool(off is not None and float(off) == STILL_OFFSET_EXPECT)
    vdir = os.path.join(rd0, "volcorr")
    rows = volcorr_rows(vdir)
    ck["long_volcorr_state_ready"] = bool(os.path.exists(os.path.join(vdir, "ref.json")) and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % k))
                                          and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % f_from)) and all(f_ in rows for f_ in range(k - nT + 1, k + 1)))
    ck["long_one_launch_le_29min"] = bool(float(c["wall_limit_s"]) <= WALL_S)
    ck["long_ckpt_every_48"] = bool(int(c["ckpt_every"]) == CKPT_EVERY and list(c["ckpt_list"]) == CKPT_LIST)
    ck["long_measured_est_le_max_hours"] = bool(est.get("total_h") is not None and est["total_h"] <= mh)
    dk = disk_est(rd0, f_end - f_from + 1, int(est.get("n_launches") or 9))
    free = float(GC.free_gb())
    stop_line = float(c.get("disk_stop_free_gb", 25.0))
    ck["long_disk_ok"] = bool(free - dk["total_gb"] >= stop_line + DISK_MARGIN_GB)
    ck["long_out_root_hero_FLIP52B3"] = bool(c["out_root"] == OUT_ROOT and (OUT_ROOT + "/").startswith(B52B3 + "/hero/")
                                             and "/FLIP52B/" not in OUT_ROOT)
    sd = source_diff(c0, c)
    ck["long_selfcheck_vs_source"] = bool(sd["ok"])
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(kk for kk, v in ck.items() if not v)
    pc["long"] = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), cost_measured=est, disk=dk, free_gb_now=round(free, 1), stop_line_gb=stop_line,
                      max_hours_rule="measured estimate x %g + %g h, rounded up to 0.25 h [chosen]" % (MH_FACTOR, MH_ADD),
                      hip=GC.HIP, physics_keys=list(PHYS_KEYS), launch_cfgs_compared=[os.path.basename(p) for p in launch_cfgs],
                      runtime_modules_compared=len(m_run), runtime_modules_changed_since_source=mdiff,
                      runtime_modules_note="every module hash recorded at the DFGBV chain start must equal today's (no named exception)",
                      nT_frames=nT, nT_rule="g52b3_run NT = round(sf.T x 24) with sf.T %g s" % T,
                      source_chain=dict(seg, last=seg["last"][:200]), source_diff=sd, judge=jt)
    c["precheck"] = pc
    return c, c0


def write_cfg(c, folder):
    """new file only. An existing file equal apart from its precheck is KEPT as it is (a chain may have been started with it: never
    rewritten); a different one stops."""
    p = folder.rstrip("/") + "/" + c["run_id"] + ".json"
    if os.path.exists(p):
        old = jload(p) or {}
        if canon({k: v for k, v in old.items() if k != "precheck"}) != canon({k: v for k, v in c.items() if k != "precheck"}):
            raise SystemExit("%s exists with other content; remove it by hand if it is really to be replaced" % p)
        if (old.get("precheck") or {}).get("ok") is not True:
            raise SystemExit("%s exists (same content) but its own precheck is not ok; look before replacing it" % p)
        return p, "kept (existing file, same content apart from the precheck; not rewritten)"
    os.makedirs(folder, exist_ok=True)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    return p, "written"


def launch_cmd(cfgp):
    return ["py", "-3.10", CHAIN, cfgp]


def cmd_cfg(o):
    c, c0 = build(o)
    pc = c["precheck"]
    folder = o.get("out", CFG_DIR)
    dry = "dry" in o
    p = folder.rstrip("/") + "/" + c["run_id"] + ".json"
    how = "not written: %s" % ("dry" if dry else "precheck not ok")
    if not dry and pc["ok"]:
        p, how = write_cfg(c, folder)
    dst = OUT_ROOT + "/" + c["run_id"]
    seg = chain_segment(open(dst + "/chain.log", encoding="utf8", errors="replace").read().splitlines() if os.path.exists(dst + "/chain.log") else [])
    L = pc["long"]
    print(json.dumps(dict(cfg=p, how=how, written=bool(not dry and pc["ok"]), run_id=c["run_id"], source=c0["run_id"], run_dir=dst,
                          run_state=dict(seg, last=seg["last"][:200], frames_done=frames_done(dst) if os.path.isdir(dst) else 0),
                          frames=[c["f_start"], c["f_end"]], t=[(c["f_start"] - 1) / 24.0, c["t_end_s"]], ckpt=c["restart"]["ckpt_frame"],
                          ckpt_bytes=c["restart"]["ckpt_bytes"], still_offset=[c["still_offset_m"], c["restart"]["still_offset_source"]],
                          max_hours=c["max_hours"], precheck_ok=pc["ok"], reason=pc["reason"], replaced=list((pc.get("replaced") or {}).keys()),
                          checks=pc["checks"], runtime_modules_changed=L["runtime_modules_changed_since_source"],
                          selfcheck_vs_source=dict(ok=L["source_diff"]["ok"], unexpected=L["source_diff"]["unexpected"]),
                          diff_vs_source=diff_table(c0, c),
                          est=dict((k, L["cost_measured"].get(k)) for k in ("frames", "frames_extrapolated", "s_solve_tail_median", "s_surf", "s_other",
                                                                             "s_per_frame_mean", "n_launches", "total_h", "missing")),
                          disk=dict((k, L["disk"][k]) for k in ("records_gb", "ckpt_gb", "total_gb", "redo_frames")), free_gb_now=L["free_gb_now"],
                          valid=c["case"]["hero"]["valid"], progress=c["case"]["hero"]["progress"], energy=ENERGY_EN,
                          chain=" ".join(launch_cmd(p))),
                     ensure_ascii=False, indent=1, default=float))
    return 0 if pc["ok"] else 2


def cmd_selfcheck(cfgp, quiet=False):
    """regenerate from the source with the cfg's own args: same cfg (precheck aside) + source diff only in the allowed keys."""
    c = jload(cfgp)
    if not c or not ((c.get("case") or {}).get("hero") or {}).get("args"):
        raise SystemExit("%s is not a hero long cfg" % cfgp)
    a = dict(c["case"]["hero"]["args"])
    c2, c0 = build(a)
    strip = lambda d: {k: v for k, v in d.items() if k != "precheck"}
    same = canon(strip(c)) == canon(strip(c2))
    diff = [] if same else ["%s %s" % x for x in paths_diff(strip(c), strip(c2))][:30]
    sd = source_diff(c0, c)
    r = dict(cfg=cfgp, regenerated_equal=bool(same), regenerated_diff=diff, source_diff_ok=sd["ok"], source_unexpected=sd["unexpected"],
             source_changed=sd["changed"], ok=bool(same and sd["ok"]))
    if not quiet:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return r


# ====================================================================== gate (dry: nothing launched, no run folder made)
def chain_gate(c):
    """g52b3_chain.py's own gate() executed alone (its top level is not run: it would create the run folder and launch)."""
    src = open(CHAIN, encoding="utf8").read()
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gate"]
    if len(fn) != 1:
        return ["flip52b3/g52b3_chain.py has no unique gate()"]
    ns = dict(cfg=c, GC=GC, os=os, json=json)
    exec(compile(ast.Module(body=fn, type_ignores=[]), CHAIN + " [gate only, read by flip52b3h]", "exec"), ns)
    return ns["gate"]()


def cmd_gate(cfgp, quiet=False):
    c = jload(cfgp)
    rid = c["run_id"]
    bad = list(chain_gate(c))
    sc = cmd_selfcheck(cfgp, quiet=True)
    if not sc["ok"]:
        bad.append("selfcheck failed: regenerated_equal %s, unexpected %s" % (sc["regenerated_equal"], sc["source_unexpected"][:5]))
    if (c.get("restart") or {}).get("src_run") != SRC_RUN or c.get("out_root") != OUT_ROOT:
        bad.append("not a DFG-2B-V hero re-record cfg under %s" % OUT_ROOT)
    dst = os.path.join(B52B3, c.get("out_root", "runs"), rid).replace("\\", "/")
    ran = sorted(glob.glob(os.path.join(dst, "run_c*.json")))
    st = "fresh" if not os.path.exists(dst) else ("resume (%d launch records)" % len(ran) if ran else "seeded or empty folder")
    r = dict(cfg=cfgp, run_id=rid, path="flip52b3/g52b3_chain.py (unchanged)", run_dir=dst, gate_ok=not bad, reasons=bad, dst_state=st,
             chain=" ".join(launch_cmd(cfgp)))
    if not quiet:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if not bad else 1


# ====================================================================== seed / compare (g49_restart unchanged, Build/FLIP52B3 in memory)
def restart_module():
    import g49_restart as RS
    RS.GC = types.SimpleNamespace(B49=B52B3)       # dirs() reads only GC.B49 (src, dst, 'under Build/...' check)
    return RS


def cmd_seed(cfgp):
    c = jload(cfgp)
    if (c.get("restart") or {}).get("src_run") != SRC_RUN or not str(c.get("out_root", "")).startswith(OUT_ROOT):
        raise SystemExit("not a DFG-2B-V hero re-record cfg")
    rd = os.path.join(OUT_ROOT, c["run_id"])
    if os.path.exists(rd + "/chain.log") or glob.glob(rd + "/run_c*.json"):
        print(json.dumps(dict(seed="skipped: the folder already holds this cfg's chain", run_dir=rd)))
        return 0
    rec = restart_module().seed(cfgp)
    ok = all(v.get("dst_sha256") in (v.get("src_sha256"), v.get("src_sha256_of_rows")) for v in rec["files"].values())
    print(json.dumps(dict(seed="ok" if ok else "sha mismatch", run_dir=rd, files={k: {kk: v.get(kk) for kk in ("bytes", "rows", "frames")}
                                                                                    for k, v in rec["files"].items()}), ensure_ascii=False))
    return 0 if ok else 1


def strict_summary(c, rc, dst):
    """[computed] the STRICT verdict on g49_restart.compare's output: g49 counts only the COMMON frames (an empty or partial overlap would be
    vacuously 'identical'), so every count must also be COMPLETE: every frame of the compared range for hf / r2 / r3 (all keys) / volcorr, every
    source r4 / surf frame of the range (339 for 48-125 s), the re-record's chain complete to f_end, and every frame's surface present."""
    h = (c.get("case") or {}).get("hero") or {}
    f0, f1 = int(c["f_start"]), int(c["f_end"])
    have = set(int(os.path.basename(p)[2:7]) for p in glob.glob(os.path.join(dst, "surf", "s_*.gw45s")))
    miss = [f for f in range(f0, f1 + 1) if f not in have]
    eq = lambda kind, key: [((rc.get(kind) or {}).get(key) or {}).get("n_bit_equal"), ((rc.get(kind) or {}).get(key) or {}).get("n_frames")]
    s = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip52b3h/h52b3_long.py compare (g49_restart.compare, Build/FLIP52B3 in memory; strict)",
             run_id=c["run_id"], source=c["restart"]["src_run"], overlap_frames=h.get("compared_frames"),
             hf_eta=eq("hf", "eta"), r2_sdf=eq("r2", "sdf"), r2_u=eq("r2", "u"), r2_w=eq("r2", "w"), r3_sdf=eq("r3", "sdf"), r3_u=eq("r3", "u"),
             r3_v=eq("r3", "v"), r3_w=eq("r3", "w"), r4_sdf=eq("r4", "sdf"),
             r5_bytes_equal=[(rc.get("r5") or {}).get("n_bytes_equal"), (rc.get("r5") or {}).get("n_common")],
             volcorr_equal=[(rc.get("volcorr") or {}).get("n_equal"), (rc.get("volcorr") or {}).get("n_common")],
             beyond_source_frames=h.get("beyond_source_frames"), every_frame_surf_complete=not miss, surf_missing_first=miss[:20],
             n_surf=len([f for f in range(f0, f1 + 1) if f in have]), n_expected=f1 - f0 + 1,
             frames_done=frames_done(dst), chain=chain_segment(open(dst + "/chain.log", encoding="utf8", errors="replace").read().splitlines()
                                                                if os.path.exists(dst + "/chain.log") else [])["state"],
             if_not_identical=("look first at the runtime module hashes (cfg.json module_shas_at_chain_start vs the source's) and the hip sha; the "
                               "pv53 group numbers are then NOT borrowed and nothing is exported (auto_heroV stops)"),
             tags="[measured] record-to-record comparison")
    n_ov = int(min(f1, int((h.get("compared_frames") or [f0, f1])[1])) - f0 + 1)
    src_dir = c["restart"].get("src_dir") or SRC_DIR
    n_src_surf = len([p for p in glob.glob(os.path.join(src_dir, "surf", "s_*.gw45s")) if f0 <= int(os.path.basename(p)[2:7]) <= f1])
    n_src_r4 = int((rc.get("r4") or {}).get("n_src") or 0)
    s["expected"] = dict(hf_r2_r3_frames=n_ov, volcorr_rows=n_ov, surf_common=n_src_surf, r4_common=n_src_r4,
                         rule="every frame of the overlap for hf / r2 / r3 / volcorr; every source r4 / surf frame of the range")
    s["counts_as_expected"] = bool(n_ov > 0 and n_src_surf > 0 and n_src_r4 > 0
                                   and all(s[k] == [n_ov, n_ov] for k in ("hf_eta", "r2_sdf", "r2_u", "r2_w", "r3_sdf", "r3_u", "r3_v", "r3_w", "volcorr_equal"))
                                   and s["r5_bytes_equal"] == [n_src_surf, n_src_surf] and s["r4_sdf"] == [n_src_r4, n_src_r4])
    s["run_complete"] = bool(s["frames_done"] >= f1 and s["chain"] == "complete")
    s["all_bit_identical_g49"] = rc.get("all_bit_identical")
    s["all_bit_identical_in_overlap"] = bool(rc.get("all_bit_identical") is True and s["counts_as_expected"])
    s["ok"] = bool(s["all_bit_identical_in_overlap"] and s["every_frame_surf_complete"] and s["run_complete"])
    return s


def cmd_compare(cfgp):
    c = jload(cfgp)
    if (c.get("restart") or {}).get("src_run") != SRC_RUN:
        raise SystemExit("not a DFG-2B-V hero re-record cfg")
    dst = os.path.join(OUT_ROOT, c["run_id"]).replace("\\", "/")
    rc = restart_module().compare(cfgp)
    s = strict_summary(c, rc, dst)
    json.dump(s, open(dst + "/hero_compare_summary.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(json.dumps(s, ensure_ascii=False))
    return 0 if s["ok"] else 3


def cmd_selftest_strict():
    """[computed] the strict rule on synthetic g49 outputs (no files read but the source's surf list): complete identical -> ok; a partial
    overlap (the re-record stopped at frame 2500) -> not ok although g49 says identical; an empty overlap -> not ok."""
    c = dict(run_id="x", f_start=1153, f_end=3001, restart=dict(src_run=SRC_RUN, src_dir=SRC_DIR),
             case=dict(hero=dict(compared_frames=[1153, 3001], beyond_source_frames=None)))

    def g49(n, n_src_r4=339, n_surf=339, ident=True):
        e = lambda m: dict(n_bit_equal=m, n_frames=m)
        return dict(all_bit_identical=ident, hf=dict(eta=e(n)), r2=dict(sdf=e(n), u=e(n), w=e(n)), r3=dict(sdf=e(n), u=e(n), v=e(n), w=e(n)),
                    r4=dict(n_src=n_src_r4, sdf=e(min(n_src_r4, n_surf))), r5=dict(n_bytes_equal=n_surf, n_common=n_surf), volcorr=dict(n_equal=n, n_common=n))
    res = {}
    for name, rc in (("complete", g49(1849)), ("partial_to_2500", g49(1348, n_surf=226)), ("empty", g49(0, n_surf=0)),
                     ("not_identical", g49(1849, ident=False))):
        s = strict_summary(c, rc, HERO + "/_no_such_run")
        res[name] = dict(counts_as_expected=s["counts_as_expected"], all_bit_identical_in_overlap=s["all_bit_identical_in_overlap"])
    res["ok"] = bool(res["complete"]["all_bit_identical_in_overlap"] and not res["partial_to_2500"]["all_bit_identical_in_overlap"]
                     and not res["empty"]["all_bit_identical_in_overlap"] and not res["not_identical"]["all_bit_identical_in_overlap"])
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    if not argv:
        print(__doc__); sys.exit(1)
    cmd = argv[0]
    pos, o = opts(argv[1:])
    if cmd == "cfg":
        sys.exit(cmd_cfg(o))
    elif cmd == "selfcheck":
        sys.exit(0 if cmd_selfcheck(pos[0])["ok"] else 1)
    elif cmd == "gate":
        sys.exit(cmd_gate(pos[0]))
    elif cmd == "seed":
        sys.exit(cmd_seed(pos[0]))
    elif cmd == "compare":
        sys.exit(cmd_compare(pos[0]))
    elif cmd == "selftest-strict":
        sys.exit(cmd_selftest_strict())
    else:
        print(__doc__); sys.exit(1)
