# -*- coding: utf-8 -*-
"""FLIP52B DFG-2B-E HERO (user Q85 2026-10-18 "DFG-2B 的效果更好"): the every-frame re-record of the judged run
DFGB2E_D19B_xf272p25_dp0p5 from its checkpoint v.1152 (47.958 s) to 125 s, for the Unity FLIP3D player (py -3.10 -B; numpy + scipy in
compare, no Houdini here). 2026-10-18 written new (Claude subagent). The FLIP52B analogue of flip50h/h50_long.py (which is FLIP50-bound:
B50 paths, g50_pcfg precheck, the FLIP50 hip, float(dir.T) - the FLIP52B dir.T is the list [9.33, 7, 5.6]).

What it is (and is not): the SAME physics recomputed from the judged run's own checkpoint with records written every frame (r4 SDF and the
surface r5; hf, r2, r3 were already every frame). Nothing new is computed for the hero window: every frame 1153-3001 exists in the judged
run, and the overlap is compared bit for bit (hf / r2 / r3 / volcorr on 1849 frames, surf bytes and r4 SDF on the 339 common frames).
DFG-2B-E is formally INVALID by two marginal gates (G2f inlet 5.6 s phase 0.514 rad > 0.35; G6 group 1 peak 58.958 s, 0.042 s before
t_fn - 4 = 59.0 s); energy (Q84): spectral sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A (AM-DFGB1b). Every cfg / label says so.

No existing file is edited. Read only, imported unchanged: flip52b/g52b_common.py (constants; G52B_SEA=E is set in this process when unset,
as auto_DFGB.py --sea=E does for its tools), flip52b/g52b_pcfg.py (precheck), flip52b/g52b_chain.py (only its gate() is read and run alone,
dry), flip49/g49_restart.py (seed / compare with its module global GC replaced in memory by a shim whose B49 is Build/FLIP52B: src =
Build/FLIP52B/runs/<src>, dst = <out_root>/<run_id>, the 'under Build/...' guard), flip50g2/g50g2_cont.py (cost / still_offset helpers).
The source run folder is read only. Writes: Unity/Build/FLIP52B/hero/cfg/<run_id>.json (cfg; never runs/ready), and through seed / the
chain / compare only the NEW run folder Unity/Build/FLIP52B/hero/runs/<run_id>/ (all of Unity/Build is git-ignored).

  py -3.10 -B h52b_long.py cfg       [--t_from=48] [--t_end=125] [--ckpt=auto|<k>] [--max_hours=auto|<h>] [--dry] [--out=<cfg folder>]
  py -3.10 -B h52b_long.py selfcheck <cfg>
  py -3.10 -B h52b_long.py gate      <cfg>        (g52b_chain.py's own gate() run alone + selfcheck; nothing launched, no folder made)
  py -3.10 -B h52b_long.py seed      <cfg>        (g49_restart.seed: v.1152, volcorr ref.json / vd_01152 / vd_01153 / state rows f <= 1152)
  chain:  set G52B_SEA=E and run  py -3.10 Tools/GWWaveGen/flip52b/g52b_chain.py <cfg>   (unchanged; printed by `cfg`)
  py -3.10 -B h52b_long.py compare   <cfg>        (g49_restart.compare -> restart_compare.json + hero_compare_summary.json)
Tags: [measured] run records, [computed] derived here, [guess], [chosen].
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
_SEA = os.environ.get("G52B_SEA")
if _SEA is None or not _SEA.strip():
    os.environ["G52B_SEA"] = "E"            # the energy-matched DFG-2B-E sea (AM-DFGB1); without it the precheck reads the frozen DFG-2B sea
elif _SEA.strip().upper() != "E":
    raise SystemExit("G52B_SEA=%r: the hero re-record is DFG-2B-E only (G52B_SEA=E)" % _SEA)
import sys, json, copy, glob, time, ast, math, types, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
T52B, T50G2, T49, T46 = (REPO + "/Tools/GWWaveGen/" + s for s in ("flip52b", "flip50g2", "flip49", "flip46"))
for _p in (T52B, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _p in (T50G2, T49, T46):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                  # noqa: E402
import g52b_common as GC            # noqa: E402  read only
import g52b_pcfg as PCF             # noqa: E402  read only (precheck)
import g50g2_cont as G2             # noqa: E402  read only (cost, still_offset)

B52B = GC.B52B
SRC_RUN = "DFGB2E_D19B_xf272p25_dp0p5"
SRC_DIR = B52B + "/runs/" + SRC_RUN
HERO = B52B + "/hero"
CFG_DIR = HERO + "/cfg"
OUT_ROOT = HERO + "/runs"
CHAIN = T52B + "/g52b_chain.py"
T_FROM_S, T_END_S = 48.0, 125.0      # [chosen] window A (design): every frame of 48-125 s exists in the judged run -> fully comparable
CKPT_EVERY = 48                      # [chosen] as the DM1A hero (one checkpoint ~0.20 GB; a relaunch redoes <= 47 frames)
CKPT_LIST = [48, 24]
WALL_S = 1740.0                      # launches <= 29 min (g52b_chain)
MAX_BACK_S = 10.0                    # [chosen] the checkpoint may lie at most 10 s before t_from
MH_FACTOR, MH_ADD = 1.2, 0.25        # [chosen] max_hours = measured estimate x 1.2 + 0.25 h, rounded up to 0.25 h (the h50 rule)
DISK_MARGIN_GB = 20.0                # [chosen] free space after the run >= the chain's stop line 25 GB + 20 GB
SUFFIX = "_long"
STILL_OFFSET_EXPECT = 0.07598474621772766   # [measured] every run_c*.json of the source (online in c00001, then restored)
POP_TOP = ("hip_sha256", "module_shas_at_chain_start", "precheck")
ALLOWED_TOP = {"run_id", "out_root", "f_start", "f_first", "f_end", "t_end_s", "still_offset_m", "ckpt_every", "ckpt_list", "wall_limit_s",
               "max_hours", "pstats_frames", "note", "restart", "precheck"}
ALLOWED_REMOVED = set(POP_TOP)
ALLOWED_PATHS = {"records.r4.every", "records.r5.every", "records.windows"}
ALLOWED_CASE = {"judged", "role", "restart_of", "restart_ckpt_frame", "windows_source", "hero"}
PHYS_KEYS = ("stage", "kind", "layout", "parms", "box", "bed", "sf", "dir", "wave", "drift", "solver", "gauges", "level_regions", "dir_check",
             "level_guard_m", "level_box", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "analysis", "disk_stop_free_gb")
RUNTIME_PREFIX = ("flip52b/", "flip52/", "flip50/", "flip51/")
# the two runtime modules that changed after the source chain ended (05:42; mtime 05:48:53; commit 6f17704 05:51; the earlier versions
# are not in git) [measured]. By reading g52b_run they only supply constants the cfg overrides + the bed functions of g50_common
# [computed]; only the bit-identical compare can prove the records unchanged. Any OTHER module difference fails the precheck.
KNOWN_MODULE_DIFF = {"flip52b/g52b_common.py": ("0d8226f8", "1689765261d68e6b"), "flip52/g52_common.py": ("9ff92875", "f36bbce861f0804c")}
REPLACEABLE = dict(
    records_as_designed="g52b_pcfg's records rule of a JUDGED DFG-2B run (r4 / r5 every 3rd frame in the three group windows); this cfg is the "
                        "hero re-record whose records are every frame on purpose (long_records_every_frame)",
    time_within_max_hours="g52b_pcfg's time model of a judged run (plan E X2 rates 1.954 / 3.00 s per frame) underestimates every-frame "
                          "surface writing (2.91 s per frame [measured]); replaced by the source's own measured cost (long_measured_est_le_max_hours). "
                          "max_hours 4.0 h > the plan's 3.0 h cap of JUDGED runs: a named difference (this is a hero re-record, not a judged run)")
INVALID_EN = ("DFG-2B-E (DFGB2E_D19B_xf272p25_dp0p5), formally INVALID: G2f inlet 5.6 s phase 0.514 rad > 0.35, "
              "G6 group 1 peak 58.958 s, 0.042 s before 59.0 s")
ENERGY_EN = "energy: sum a^2 = DM1A's 1.336 m^2 (equal spectral energy, Q84), in-tank power 0.23 x DM1A (AM-DFGB1b)"


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
    """the last chain start..end segment of a chain.log (g52b_chain writes '... chunk <f0> ... stopped None ...' for the launch that reached f_end)."""
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
    """the INVALID line from the source's own judge (g52b/judge_DFGB.json) [measured]; falls back to the fixed text if unreadable."""
    J = jload(SRC_DIR + "/g52b/judge_DFGB.json") or {}
    try:
        n5 = J["G2f"]["per_n"]["n5"]
        g6 = J["gates"]["G6"]["failing"][0]
        lim = float(J["G2f"]["phase_max_rad"])
        t_lo = float(g6["t_fn"]) - 4.0
        txt = ("DFG-2B-E (%s), formally INVALID: G2f inlet 5.6 s phase %.3f rad > %.2f, G6 group %d peak %.3f s, %.3f s before %.1f s"
               % (SRC_RUN, float(n5["phase_err_rad"]), lim, int(g6["n"]), float(g6["t"]), t_lo - float(g6["t"]), t_lo))
        return dict(invalid=txt, valid=J.get("valid"), failed=J.get("failed_gates"), source="Unity/Build/FLIP52B/runs/%s/g52b/judge_DFGB.json" % SRC_RUN)
    except Exception:
        return dict(invalid=INVALID_EN, valid=False, failed=["G2f", "G6"], source="(fixed text: judge unreadable)")


# ====================================================================== cfg
def build(o):
    rd0 = SRC_DIR
    c0 = jload(rd0 + "/cfg.json")
    if not c0:
        raise SystemExit("%s/cfg.json is missing or unreadable" % rd0)
    if c0.get("run_id") != SRC_RUN or (c0.get("dir") or {}).get("set") != "DFG2BE" or c0.get("kind") != "3d":
        raise SystemExit("the hero re-record continues DFG-2B-E (%s, set DFG2BE) only, not %s" % (SRC_RUN, c0.get("run_id")))
    if c0.get("restart"):
        raise SystemExit("%s is itself a re-record" % c0.get("run_id"))
    if GC.SEA != "E":
        raise SystemExit("g52b_common.SEA is %r, not 'E'" % GC.SEA)
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
    T = float(c0["sf"]["T"])                              # 7 s (the descriptor's middle harmonic; g52b_run NT = round(sf.T x 24) = 168)
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
              role="hero every-frame RE-RECORD of the judged DFG-2B-E run (user Q85, 2026-10-18; not judged, same physics)",
              restart_of=c0["run_id"], restart_ckpt_frame=k,
              windows_source="every frame %d-%d (r4, r5; hf, r2, r3 as before)" % (f_from, f_end),
              hero=dict(q="Q85", user_words="DFG-2B 的效果更好", decision="Docs/Workflow/Production_Workflow_ja.md Q85",
                        invalid=jt["invalid"], invalid_source=jt["source"], energy=ENERGY_EN,
                        physics="physics only, 0.5 m Houdini FLIP; frames %d-%d recomputed from checkpoint v.%04d of %s with the same settings; "
                                "no shapes between frames" % (f_from, f_end, k, c0["run_id"]),
                        tool="Tools/GWWaveGen/flip52bh/h52b_long.py cfg",
                        args=dict(t_from=t_from, t_end=t_end, ckpt=str(o.get("ckpt", "auto")), max_hours=str(o.get("max_hours", "auto"))),
                        source_f_end=src_f_end, source_frames_done=src_done, source_t_end_s=float(c0["t_end_s"]),
                        compared_frames=[f_from, min(f_end, src_done)], beyond_source_frames=beyond,
                        max_hours_note="max_hours %.2f h > the plan's 3.0 h cap for JUDGED runs: named difference (hero re-record, not a judged run)" % mh))
    ck_src = os.path.join(rd0, "ckpt", "v.%04d.sim" % k).replace("\\", "/")
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=k, ckpt_t_s=(k - 1) / 24.0, ckpt_file=ck_src,
                        ckpt_bytes=os.path.getsize(ck_src) if os.path.exists(ck_src) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip52bh/h52b_long.py seed <cfg> (g49_restart.seed, Build/FLIP52B in memory)",
                        compare="py -3.10 -B Tools/GWWaveGen/flip52bh/h52b_long.py compare <cfg>")
    c["note"] = ("%s hero every-frame re-record (flip52bh, Q85, 2026-10-18; NOT judged): from checkpoint v.%04d (%.3f s) of %s with the same "
                 "settings, %.3f-%g s (frames %d-%d), surface (r5) and r4 every frame, new folder %s/%s; shape not changed (physics only). %s. %s"
                 % (short, k, (k - 1) / 24.0, c0["run_id"], t_from_k, t_end, f_from, f_end, OUT_ROOT.replace(REPO + "/", ""), rid, jt["invalid"], ENERGY_EN))
    # ---------------------------------------------------------------- precheck: g52b_pcfg's own + the long_* checks
    pc = PCF.precheck(c)
    ck = pc["checks"]
    for nm, why in REPLACEABLE.items():
        if nm in ck:
            pc.setdefault("replaced", {})[nm] = dict(value=ck[nm], why=why, plan_time=pc.get("time"))
            ck.pop(nm)
    others = [os.path.getsize(p) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim"))]
    ck["long_source_is_DFGB2E"] = bool(c0["run_id"] == SRC_RUN and (c0.get("dir") or {}).get("set") == "DFG2BE"
                                       and (c0.get("case") or {}).get("amendment") == "AM-DFGB1" and GC.SEA == "E")
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
    mkeys = [kk for kk in m_run if kk.startswith(RUNTIME_PREFIX)]
    mdiff = {kk: [m_run.get(kk), m_now.get(kk)] for kk in mkeys if m_now.get(kk) != m_run.get(kk)}
    known_ok = all(kk in KNOWN_MODULE_DIFF and str(v[0] or "").startswith(KNOWN_MODULE_DIFF[kk][0]) and v[1] == KNOWN_MODULE_DIFF[kk][1]
                   for kk, v in mdiff.items())
    ck["long_runtime_modules_same_except_named_two"] = bool(mkeys and known_ok)
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
    ck["long_out_root_hero"] = bool(c["out_root"] == OUT_ROOT and (OUT_ROOT + "/").startswith(B52B + "/hero/"))
    sd = source_diff(c0, c)
    ck["long_selfcheck_vs_source"] = bool(sd["ok"])
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(kk for kk, v in ck.items() if not v)
    pc["long"] = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), cost_measured=est, disk=dk, free_gb_now=round(free, 1), stop_line_gb=stop_line,
                      max_hours_rule="measured estimate x %g + %g h, rounded up to 0.25 h [chosen]" % (MH_FACTOR, MH_ADD),
                      hip=GC.HIP, physics_keys=list(PHYS_KEYS), launch_cfgs_compared=[os.path.basename(p) for p in launch_cfgs],
                      runtime_modules_compared=len(mkeys), runtime_modules_changed_since_source=mdiff,
                      runtime_modules_note="changed after the source chain ended; only the named two may differ, and only the bit-identical "
                                           "compare after the run proves the records unchanged",
                      nT_frames=nT, nT_rule="g52b_run NT = round(sf.T x 24) with sf.T %g s (dir.T is a list for FLIP52B)" % T,
                      source_chain=dict(seg, last=seg["last"][:200]), source_diff=sd, sea_env=os.environ.get("G52B_SEA"))
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
                          chain="set G52B_SEA=E && " + " ".join(launch_cmd(p))),
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
    """g52b_chain.py's own gate() executed alone (its top level is not run: it would create the run folder and launch)."""
    src = open(CHAIN, encoding="utf8").read()
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gate"]
    if len(fn) != 1:
        return ["flip52b/g52b_chain.py has no unique gate()"]
    ns = dict(cfg=c, GC=GC, os=os, json=json)
    exec(compile(ast.Module(body=fn, type_ignores=[]), CHAIN + " [gate only, read by flip52bh]", "exec"), ns)
    return ns["gate"]()


def cmd_gate(cfgp, quiet=False):
    c = jload(cfgp)
    rid = c["run_id"]
    bad = list(chain_gate(c))
    sc = cmd_selfcheck(cfgp, quiet=True)
    if not sc["ok"]:
        bad.append("selfcheck failed: regenerated_equal %s, unexpected %s" % (sc["regenerated_equal"], sc["source_unexpected"][:5]))
    if os.environ.get("G52B_SEA") != "E":
        bad.append("G52B_SEA is not E in this process")
    dst = os.path.join(B52B, c.get("out_root", "runs"), rid).replace("\\", "/")
    ran = sorted(glob.glob(os.path.join(dst, "run_c*.json")))
    st = "fresh" if not os.path.exists(dst) else ("resume (%d launch records)" % len(ran) if ran else "seeded or empty folder")
    r = dict(cfg=cfgp, run_id=rid, path="flip52b/g52b_chain.py (unchanged)", run_dir=dst, gate_ok=not bad, reasons=bad, dst_state=st,
             chain="set G52B_SEA=E && " + " ".join(launch_cmd(cfgp)))
    if not quiet:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if not bad else 1


# ====================================================================== seed / compare (g49_restart unchanged, Build/FLIP52B in memory)
def restart_module():
    import g49_restart as RS
    RS.GC = types.SimpleNamespace(B49=B52B)        # dirs() reads only GC.B49 (src, dst, 'under Build/...' check)
    return RS


def cmd_seed(cfgp):
    c = jload(cfgp)
    if (c.get("restart") or {}).get("src_run") != SRC_RUN or not str(c.get("out_root", "")).startswith(OUT_ROOT):
        raise SystemExit("not a DFG-2B-E hero re-record cfg")
    rd = os.path.join(OUT_ROOT, c["run_id"])
    if os.path.exists(rd + "/chain.log") or glob.glob(rd + "/run_c*.json"):
        print(json.dumps(dict(seed="skipped: the folder already holds this cfg's chain", run_dir=rd)))
        return 0
    rec = restart_module().seed(cfgp)
    ok = all(v.get("dst_sha256") in (v.get("src_sha256"), v.get("src_sha256_of_rows")) for v in rec["files"].values())
    print(json.dumps(dict(seed="ok" if ok else "sha mismatch", run_dir=rd, files={k: {kk: v.get(kk) for kk in ("bytes", "rows", "frames")}
                                                                                    for k, v in rec["files"].items()}), ensure_ascii=False))
    return 0 if ok else 1


def cmd_compare(cfgp):
    c = jload(cfgp)
    rid = c["run_id"]
    dst = os.path.join(OUT_ROOT, rid).replace("\\", "/")
    rc = restart_module().compare(cfgp)
    h = (c.get("case") or {}).get("hero") or {}
    f0, f1 = int(c["f_start"]), int(c["f_end"])
    have = set(int(os.path.basename(p)[2:7]) for p in glob.glob(os.path.join(dst, "surf", "s_*.gw45s")))
    miss = [f for f in range(f0, f1 + 1) if f not in have]
    eq = lambda kind, key: [((rc.get(kind) or {}).get(key) or {}).get("n_bit_equal"), ((rc.get(kind) or {}).get(key) or {}).get("n_frames")]
    s = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip52bh/h52b_long.py compare (g49_restart.compare, Build/FLIP52B in memory)",
             run_id=rid, source=c["restart"]["src_run"], all_bit_identical_in_overlap=rc.get("all_bit_identical"), overlap_frames=h.get("compared_frames"),
             hf_eta=eq("hf", "eta"), r2_sdf=eq("r2", "sdf"), r2_u=eq("r2", "u"), r2_w=eq("r2", "w"), r3_sdf=eq("r3", "sdf"), r3_u=eq("r3", "u"),
             r3_v=eq("r3", "v"), r3_w=eq("r3", "w"), r4_sdf=eq("r4", "sdf"),
             r5_bytes_equal=[(rc.get("r5") or {}).get("n_bytes_equal"), (rc.get("r5") or {}).get("n_common")],
             volcorr_equal=[(rc.get("volcorr") or {}).get("n_equal"), (rc.get("volcorr") or {}).get("n_common")],
             beyond_source_frames=h.get("beyond_source_frames"), every_frame_surf_complete=not miss, surf_missing_first=miss[:20],
             n_surf=len([f for f in range(f0, f1 + 1) if f in have]), n_expected=f1 - f0 + 1,
             if_not_identical="look first at the two runtime modules that changed after the source chain (g52b_common 0d8226f8 -> 16897652, "
                              "g52_common 9ff92875 -> f36bbce8); the pv53 group numbers are then NOT borrowed (h52b_hero.py rescore labels "
                              "its own numbers 'not bit-identical')",
             tags="[measured] record-to-record comparison")
    # 2026-10-18 review (Claude subagent): g49_restart.compare counts only the COMMON frames (an empty or partial overlap is vacuously
    # 'identical'), so the overlap must also be complete: every frame of the compared range for hf / r2 / r3 (all keys) / volcorr, and every
    # source r4 / surf frame of the range (339 for 48-125 s) [measured counts]. all_bit_identical_in_overlap is the strict value; the raw
    # g49 value is kept as all_bit_identical_g49.
    n_ov = int(min(f1, int((h.get("compared_frames") or [f0, f1])[1])) - f0 + 1)
    src_dir = c["restart"].get("src_dir") or SRC_DIR
    n_src_surf = len([p for p in glob.glob(os.path.join(src_dir, "surf", "s_*.gw45s")) if f0 <= int(os.path.basename(p)[2:7]) <= f1])
    n_src_r4 = int((rc.get("r4") or {}).get("n_src") or 0)
    s["expected"] = dict(hf_r2_r3_frames=n_ov, volcorr_rows=n_ov, surf_common=n_src_surf, r4_common=n_src_r4,
                         rule="every frame of the overlap for hf / r2 / r3 / volcorr; every source r4 / surf frame of the range")
    s["counts_as_expected"] = bool(n_ov > 0 and n_src_surf > 0 and n_src_r4 > 0
                                   and all(s[k] == [n_ov, n_ov] for k in ("hf_eta", "r2_sdf", "r2_u", "r2_w", "r3_sdf", "r3_u", "r3_v", "r3_w", "volcorr_equal"))
                                   and s["r5_bytes_equal"] == [n_src_surf, n_src_surf] and s["r4_sdf"] == [n_src_r4, n_src_r4])
    s["all_bit_identical_g49"] = rc.get("all_bit_identical")
    s["all_bit_identical_in_overlap"] = bool(rc.get("all_bit_identical") is True and s["counts_as_expected"])
    json.dump(s, open(dst + "/hero_compare_summary.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(json.dumps(s, ensure_ascii=False))
    return 0 if (s["all_bit_identical_in_overlap"] and not miss) else 3


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
    else:
        print(__doc__); sys.exit(1)
