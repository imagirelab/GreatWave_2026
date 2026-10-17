# -*- coding: utf-8 -*-
"""FLIP50 option D: the HERO long every-frame re-record (AM-D23) - cfg, self-check, dry launch gate, compare and Unity export
(py -3.10 -B; numpy (+ scipy in compare/export), no Houdini). 2026-10-17 written new (Claude, orchestrator workflow step).

No file of flip46-flip50, flip50g, flip50g2, flip50dg2, the hips, build_check*.json, the frozen plans, the ready cfgs or the amendments
already written is edited. Everything reuses the unchanged code read only (the flip50g2 precedent):
  - cfg      the DA3r --full analogue (flip49 g49_pcfg preset DA3r --full: DA3 v.1152 -> 138 s, ckpt 48) built here from the run's own
             cfg.json: the latest checkpoint v.<k> at or before 48.0 s (DM1A: v.1152 = 47.958 s) -> 138.0 s, NEW run folder
             runs/<short>r_<rest>_c<k>_t138_long, r5 and r4 every frame (hf, r2, r3 already every frame), ckpt_every 48 / ckpt_list [48, 24],
             launches <= 29 min (wall_limit_s 1740), max_hours = measured cost x 1.2 + 0.25 h (auto_hero also resumes on max_hours up to 3
             times), still offset copied from the run's launch records. Helpers of flip50g2/g50g2_cont.py are used read only (tools_for =
             g50_pcfg for D19B runs, the in-memory groove patch g50g_pcfg + accept_rr for DG1; still_offset; cost = the DA3r rule).
             A source that ran 0-92 s only (DM1A, DF1A, DG1 without its DD3) is EXTENDED beyond its end: those frames are new computation
             of the same settings (the DD3 '+48 s' precedent); only the frames up to the source end can be compared bit for bit.
  - selfcheck regenerates the cfg from the source and requires (1) the same cfg as the file (precheck aside) and (2) the source cfg.json
             equal in every key except the time/output keys listed in ALLOWED_* (canonical JSON, so 'byte-equal' per key).
  - gate     dry launch gate, nothing launched, no run folder made: D19B = the unchanged `gate()` of flip50/g50_chain.py executed alone
             (as flip50g/g50g_chain.py --dry does); DG1 = `py -3.10 -B flip50g2/g50g2_cont.py chain <cfg> --dry` (the flip50g chain path,
             groove hip; the id 'DG1r_..._long' is accepted by g50g2_cont.accept_rr because cfg.restart.src_run is the DG1 main run).
  - seed     = flip50g2/g50g2_cont.py seed (g49_restart.seed with Build/FLIP50 in memory; the source folder is read only).
  - chain    D19B: py -3.10 flip50/g50_chain.py <cfg> (unchanged); DG1: py -3.10 flip50g2/g50g2_cont.py chain <cfg>. Printed by `cfg`.
  - compare  = flip50g2/g50g2_cont.py compare (g49_restart.compare) + <run>/hero_compare_summary.json (overlap with the source, frames
             beyond its end, every-frame records complete).
  - export   flip50g2/f3d50_export.py long on the re-record (24 records/s, GW45LIST1 streaming the run's own surf files). The re-record has no
             analysis; when compare says all_bit_identical, the SOURCE run's pana/best_frames.json (same frame numbers, identical records
             in the overlap) gives the judged breakers and the print record (in memory; the manifest names the source file).

  py -3.10 -B h50_long.py cfg       --run=<DM1A|DG1|DF1A|run id> [--t_from=48] [--t_end=138] [--ckpt=auto|<k>] [--max_hours=auto|<h>]
                                    [--dry] [--out=<cfg folder>]      (default folder Unity/Build/FLIP50/_scratch/hero/cfg; never runs/ready)
  py -3.10 -B h50_long.py selfcheck <cfg>
  py -3.10 -B h50_long.py gate      <cfg>
  py -3.10 -B h50_long.py compare   <cfg>
  py -3.10 -B h50_long.py export    <cfg> [f3d50_export long options, e.g. --print-k 3 --play 60,138]
Tags: 【測定】 measured (run records), 【計算】 computed, 【推測】 guess, 【選び】 chosen.
"""
import os, sys, json, copy, glob, time, ast, subprocess, math, io, contextlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
T50, T50G, T50G2, T49, T46 = (REPO + "/Tools/GWWaveGen/" + s for s in ("flip50", "flip50g", "flip50g2", "flip49", "flip46"))
for _p in (HERE, T50G2, T50G, T50, T49, T46):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                  # noqa: E402
import g50_common as GC50           # noqa: E402  read only
import g50g2_cont as G2             # noqa: E402  read only (helpers; its module constants are not changed here)
import h50_hero as HR               # noqa: E402

B50 = GC50.B50
HERO_DIR = B50 + "/_scratch/hero"
CFG_DIR = HERO_DIR + "/cfg"
CKPT_EVERY = 48                     # 【選び】 as DA3r --full (one checkpoint about 0.21 GB; a relaunch redoes <= 47 frames)
CKPT_LIST = [48, 24]                # 【選び】 the chain may drop to 24 if a launch cannot reach the next 48
WALL_S = 1740.0                     # launches <= 29 min (g50_chain)
MAX_BACK_S = 10.0                   # 【選び】 the checkpoint may lie at most 10 s before t_from (more = more warm-up frames)
MH_FACTOR, MH_ADD = 1.2, 0.25       # 【選び】 max_hours = measured estimate x 1.2 + 0.25 h, rounded up to 0.25 h
DISK_MARGIN_GB = 20.0               # 【選び】 free space after the run must stay >= the chain's stop line 25 GB + this margin
SUFFIX = "_long"
POP_TOP = ("hip_sha256", "module_shas_at_chain_start", "precheck", "f_resume_est", "dg1_chain")
POP_CASE = ("continuation_of", "rerun_of", "windows_source", "heavy_rule", "follow_up", "dd3_wrapper")
ALLOWED_TOP = {"run_id", "out_root", "f_start", "f_first", "f_end", "t_end_s", "still_offset_m", "ckpt_on", "ckpt_every", "ckpt_list",
               "wall_limit_s", "max_hours", "pstats_frames", "note", "restart", "precheck"}
ALLOWED_REMOVED = set(POP_TOP)
ALLOWED_PATHS = {"records.r4.every", "records.r5.every", "records.windows"}
ALLOWED_CASE = {"queue_id", "judged", "label", "restart_of", "restart_ckpt_frame", "windows_source", "why", "hero"} | set(POP_CASE)
REPLACEABLE = dict(wall_le_limit="g50_pcfg's plan-D budget of a JUDGED 3D run (LIMIT_D_H 3.0 h by the FLIP48/DA1 coefficient model over all "
                                 "frames); this cfg is an unjudged re-record whose budget is its own measured cost "
                                 "(long_measured_est_le_max_hours) and whose chain auto_hero resumes on max_hours up to 3 times")


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=float)


def jload(p):
    try:
        return json.load(open(p, encoding="utf8"))
    except Exception:
        return None


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


def src_dir(run):
    run = HR.IDS.get(run, run)
    return G2.run_dir(run)


def ckpt_frames(rd):
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))


def chain_segment(ls):
    """the last chain start..end segment of a chain.log (the same rule as flip50dg2/g50dg2_rules.chain_segment; copied, not imported)."""
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
    done = any("stopped None" in l for l in seg)
    mh = any("max_hours exceeded" in l for l in seg)
    return dict(state="complete" if done else "incomplete", max_hours_stop=bool(mh and not done), last=ls[-1])


def frames_done(rd):
    best = 0
    for p in glob.glob(os.path.join(rd, "run_c*.json")):
        r = jload(p) or {}
        try:
            best = max(best, int(r.get("f_end_done") or 0))
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
                rule="every key of the source cfg.json is canonical-JSON equal except ALLOWED_TOP / ALLOWED_PATHS / case labels / removed "
                     "chain-written keys (hip_sha256, module_shas_at_chain_start, precheck, f_resume_est, dg1_chain)")


def disk_est(rd0, n_frames, n_launches):
    """bytes per frame of the source's own records 【測定】 x frames 【計算】; npz blocks of overlapping launches are kept twice (<= 47 frames
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
                tag="【測定】 source bytes per frame / checkpoint size x 【計算】 frames; surf files of a redone frame are overwritten")


# ====================================================================== cfg
def build(o):
    run = o["run"]
    rd0 = src_dir(run)
    c0 = jload(rd0 + "/cfg.json")
    if not c0:
        raise SystemExit("%s/cfg.json is missing or unreadable" % rd0)
    if c0.get("layout") != "D" or c0.get("kind") != "3d":
        raise SystemExit("the hero long re-record continues a FLIP50 option-D 3D run only (%s)" % c0.get("run_id"))
    if c0.get("restart"):
        raise SystemExit("%s is itself a re-record; give the main run" % c0.get("run_id"))
    PC, pre, GG = G2.tools_for(c0)
    t_from = float(o.get("t_from", HR.T_FROM_S))
    t_end = float(o.get("t_end", HR.T_END_S))
    f_want = int(GC50.frames_for(0.0, t_from))
    f_end = int(GC50.frames_for(0.0, t_end))
    cks = ckpt_frames(rd0)
    if str(o.get("ckpt", "auto")) == "auto":
        le = [v for v in cks if v <= f_want - 1]
        if not le:
            raise SystemExit("no checkpoint at or before frame %d (%.3f s) in %s/ckpt (have %s)" % (f_want - 1, t_from, rd0, cks[-5:]))
        k = le[-1]                                        # 【選び】 the latest checkpoint at or before t_from (fewest warm-up frames)
    else:
        k = int(o["ckpt"])
    f_from = k + 1
    t_from_k = (f_from - 1) / 24.0
    T = float((c0.get("dir") or c0.get("sf") or {}).get("T", 12.0))
    short = c0["run_id"].split("_")[0]
    rest = "_".join(c0["run_id"].split("_")[1:])
    rid = "%sr_%s_c%04d_t%s%s" % (short, rest, k, G2.tag(t_end), SUFFIX)
    off, off_src = G2.still_offset(rd0, f_from)
    src_f_end = int(c0["f_end"])
    src_done = frames_done(rd0)
    est = G2.cost(rd0, k, f_end, every_frame_surf=True, wall_limit=min(float(c0.get("wall_limit_s", WALL_S)), WALL_S), sp=CKPT_EVERY)
    if str(o.get("max_hours", "auto")) == "auto":
        th = est.get("total_h")
        mh = math.ceil(((float(th) if th is not None else 6.0) * MH_FACTOR + MH_ADD) * 4.0) / 4.0
    else:
        mh = float(o["max_hours"])
    c = copy.deepcopy(c0)
    for k_ in POP_TOP:
        c.pop(k_, None)
    wl = c0.get("wall_limit_s", 1740)
    wl = wl if float(wl) <= WALL_S else 1740       # the source's own value (type kept) unless above 29 min
    c.update(run_id=rid, out_root="runs", f_start=f_from, f_first=f_from, f_end=f_end, t_end_s=t_end, still_offset_m=off,
             ckpt_on=1, ckpt_every=CKPT_EVERY, ckpt_list=list(CKPT_LIST), wall_limit_s=wl, max_hours=mh, pstats_frames=[f_from, f_end])
    c["records"]["r4"]["every"] = 1
    c["records"]["r5"]["every"] = 1
    c["records"]["windows"] = [[t_from_k, t_end]]
    cs = c["case"]
    for k_ in POP_CASE:
        cs.pop(k_, None)
    beyond = [max(src_done, k) + 1, f_end] if f_end > src_done else None
    cs.update(queue_id=short + "r", judged=False,
              label="hero long re-record of %s for the Unity player (AM-D23): same physics, every-frame surface records %.3f-%g s" % (c0["run_id"], t_from_k, t_end),
              restart_of=c0["run_id"], restart_ckpt_frame=k,
              windows_source="every frame %d-%d (r4, r5; hf, r2, r3 as before)" % (f_from, f_end),
              why="FLIP50 r5 exists only every 3rd frame (8 records/s) from 44 s; the FLIP3D player then holds each record 3 video frames "
                  "(Docs/Progress/FLIP3D_Playback_ja.md 5, 8); continuous playback of 7-8 breakers (DA3r --full precedent)",
              hero=dict(am=HR.AM_ID, rule="Unity/Build/FLIP50/plan/hero_rule.json", tool="Tools/GWWaveGen/flip50h/h50_long.py cfg",
                        args=dict(run=c0["run_id"], t_from=t_from, t_end=t_end, ckpt=str(o.get("ckpt", "auto")), max_hours=str(o.get("max_hours", "auto"))),
                        source_f_end=src_f_end, source_frames_done=src_done, source_t_end_s=float(c0["t_end_s"]),
                        compared_frames=[f_from, min(f_end, src_done)], beyond_source_frames=beyond,
                        beyond_source_note=(None if beyond is None else
                                            "frames %d-%d (%.3f-%g s) lie after the source's end: new computation of the same settings (DD3 '+48 s' "
                                            "precedent; closed-tank drift after ~100 s is expected), not comparable with the source" %
                                            (beyond[0], beyond[1], (beyond[0] - 1) / 24.0, t_end))))
    ck_src = os.path.join(rd0, "ckpt", "v.%04d.sim" % k).replace("\\", "/")
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=k, ckpt_t_s=(k - 1) / 24.0, ckpt_file=ck_src,
                        ckpt_bytes=os.path.getsize(ck_src) if os.path.exists(ck_src) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip50g2/g50g2_cont.py seed <cfg> (g49_restart.seed, Build/FLIP50 in memory)",
                        compare="py -3.10 -B Tools/GWWaveGen/flip50h/h50_long.py compare <cfg>")
    c["note"] = ("%s hero long re-record (flip50h, AM-D23, 2026-10-17; not judged): from checkpoint v.%04d (%.3f s) of %s with the same settings, "
                 "%.3f-%g s (frames %d-%d), surface (r5) and r4 every frame, new folder runs/%s; shape not changed (physics only)%s"
                 % (short, k, (k - 1) / 24.0, c0["run_id"], t_from_k, t_end, f_from, f_end, rid,
                    "" if beyond is None else "; frames %d-%d continue past the source end %d" % (beyond[0], beyond[1], src_done)))
    pc = pre(c)
    ck = pc["checks"]
    for nm, why in REPLACEABLE.items():
        if nm in ck and ck[nm] is False:
            pc.setdefault("replaced", {})[nm] = dict(value=False, why=why, plan_time=pc.get("time"))
            ck.pop(nm)
    others = [os.path.getsize(p) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim"))]
    ck["long_ckpt_exists_full_size"] = bool(k in cks and others and os.path.getsize(ck_src) >= 0.5 * float(np.median(others)))
    ck["long_ckpt_near_t_from"] = bool(k <= f_want - 1 and (f_want - 1 - k) <= MAX_BACK_S * 24)
    seg = chain_segment(open(rd0 + "/chain.log", encoding="utf8", errors="replace").read().splitlines() if os.path.exists(rd0 + "/chain.log") else [])
    ck["long_source_chain_complete"] = bool(seg["state"] == "complete" and src_done >= src_f_end)
    launch_cfgs = sorted(glob.glob(os.path.join(rd0, "cfg_c*.json")))
    same = [all(canon((jload(p) or {}).get(kk)) == canon(c.get(kk)) for kk in G2.PHYS_KEYS) for p in [rd0 + "/cfg.json"] + launch_cfgs]
    ck["long_physics_same_as_run_all_launches"] = bool(same and all(same))
    hip = GC50.HIP if GG is None else GG.HIP_G
    ck["long_hip_same_as_run"] = bool(os.path.exists(hip) and G2.sha(hip) == c0.get("hip_sha256"))
    m_now = GC50.module_shas() if GG is None else GG.module_shas_g()
    m_run = c0.get("module_shas_at_chain_start") or {}
    mkeys = [kk for kk in m_run if kk.startswith(G2.RUNTIME_PREFIX)]
    ck["long_runtime_modules_same_as_run"] = bool(mkeys and all(m_now.get(kk) == m_run.get(kk) for kk in mkeys))
    dst = os.path.join(B50, "runs", rid)
    launched = sorted(glob.glob(os.path.join(dst, "run_c*.json"))) + ([dst + "/chain.log"] if os.path.exists(dst + "/chain.log") else [])
    if not launched:
        ck["long_new_folder"] = bool(rid != c0["run_id"] and rid not in HR.IDS.values())
    else:                       # adopt / resume: the folder already holds THIS cfg's chain (cfg.json = this cfg + the chain-written keys)
        rc_ = jload(dst + "/cfg.json") or {}
        strip = lambda d: {k_: v_ for k_, v_ in d.items() if k_ not in ("precheck", "hip_sha256", "module_shas_at_chain_start", "dg1_chain")}
        ck["long_existing_run_is_this_cfg"] = bool(rid != c0["run_id"] and canon(strip(rc_)) == canon(strip(c)))
    ck["long_records_every_frame"] = bool(int(c["records"]["r5"]["every"]) == 1 and int(c["records"]["r4"]["every"]) == 1
                                          and PC.heavy_frames(c, f_from) == f_end - f_from + 1)
    ck["long_still_offset_from_run"] = bool(off is not None)
    vdir = os.path.join(rd0, "volcorr")
    rows = set()
    if os.path.exists(os.path.join(vdir, "state.jsonl")):
        for ln in open(os.path.join(vdir, "state.jsonl"), encoding="utf8"):
            try:
                rows.add(int(json.loads(ln)["f"]))
            except Exception:
                pass
    nT = int(round(T * 24))
    ck["long_volcorr_state_ready"] = bool(os.path.exists(os.path.join(vdir, "ref.json")) and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % k))
                                          and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % f_from)) and all(f_ in rows for f_ in range(k - nT + 1, k + 1)))
    ck["long_one_launch_le_29min"] = bool(float(c["wall_limit_s"]) <= WALL_S)
    ck["long_ckpt_every_48"] = bool(int(c["ckpt_every"]) == CKPT_EVERY)
    ck["long_window_ge_6_periods"] = bool(t_end - t_from_k >= 6.0 * T - 1e-9)
    ck["long_measured_est_le_max_hours"] = bool(est.get("total_h") is not None and est["total_h"] <= mh)
    dk = disk_est(rd0, f_end - f_from + 1, int(est.get("n_launches") or 12))
    free = float(GC50.free_gb())
    stop_line = float(c.get("disk_stop_free_gb", 25.0))
    ck["long_disk_ok"] = bool(free - dk["total_gb"] >= stop_line + DISK_MARGIN_GB)
    sd = source_diff(c0, c)
    ck["long_selfcheck_vs_source"] = bool(sd["ok"])
    if GG is not None:
        ck["long_id_accepted_by_groove_chain"] = bool(GG.cfg_groove_ok(c) == [])
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(kk for kk, v in ck.items() if not v)
    pc["long"] = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), cost_measured=est, disk=dk, free_gb_now=round(free, 1), stop_line_gb=stop_line,
                      max_hours_rule="measured estimate x %g + %g h, rounded up to 0.25 h 【選び】; auto_hero resumes on max_hours up to 3 times" % (MH_FACTOR, MH_ADD),
                      hip=hip, physics_keys=list(G2.PHYS_KEYS), launch_cfgs_compared=[os.path.basename(p) for p in launch_cfgs],
                      runtime_modules_compared=len(mkeys), source_chain=dict(seg, last=seg["last"][:200]), source_diff=sd)
    c["precheck"] = pc
    return c, c0, rd0, GG


def launch_cmd(c, cfgp):
    if (c.get("bed") or {}).get("groove"):
        return ["py", "-3.10", T50G2 + "/g50g2_cont.py", "chain", cfgp]
    return ["py", "-3.10", T50 + "/g50_chain.py", cfgp]


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


def cmd_cfg(o):
    c, c0, rd0, GG = build(o)
    pc = c["precheck"]
    folder = o.get("out", CFG_DIR)
    dry = "dry" in o
    p = folder.rstrip("/") + "/" + c["run_id"] + ".json"
    how = "not written: %s" % ("dry" if dry else "precheck not ok")
    if not dry and pc["ok"]:
        p, how = write_cfg(c, folder)
    dst = os.path.join(B50, "runs", c["run_id"])
    seg = chain_segment(open(dst + "/chain.log", encoding="utf8", errors="replace").read().splitlines() if os.path.exists(dst + "/chain.log") else [])
    L = pc["long"]
    print(json.dumps(dict(cfg=p, how=how, written=bool(not dry and pc["ok"]), run_id=c["run_id"], source=c0["run_id"], groove=GG is not None,
                          run_state=dict(seg, last=seg["last"][:200], frames_done=frames_done(dst) if os.path.isdir(dst) else 0),
                          frames=[c["f_start"], c["f_end"]], t=[(c["f_start"] - 1) / 24.0, c["t_end_s"]], ckpt=c["restart"]["ckpt_frame"],
                          beyond_source_frames=c["case"]["hero"]["beyond_source_frames"], still_offset=[c["still_offset_m"], c["restart"]["still_offset_source"]],
                          max_hours=c["max_hours"], precheck_ok=pc["ok"], reason=pc["reason"], replaced=list((pc.get("replaced") or {}).keys()),
                          selfcheck_vs_source=dict(ok=L["source_diff"]["ok"], unexpected=L["source_diff"]["unexpected"]),
                          est=dict((k, L["cost_measured"].get(k)) for k in ("frames", "frames_extrapolated", "s_per_frame_mean", "n_launches", "total_h", "missing")),
                          disk=dict((k, L["disk"][k]) for k in ("records_gb", "ckpt_gb", "total_gb")), free_gb_now=L["free_gb_now"],
                          chain=" ".join(launch_cmd(c, p))),
                     ensure_ascii=False, indent=1, default=float))
    return 0 if pc["ok"] else 2


def cmd_selfcheck(cfgp, quiet=False):
    """regenerate from the source with the cfg's own args: same cfg (precheck aside) + source diff only in the allowed keys."""
    c = jload(cfgp)
    if not c or not ((c.get("case") or {}).get("hero") or {}).get("args"):
        raise SystemExit("%s is not a hero long cfg" % cfgp)
    a = dict(c["case"]["hero"]["args"])
    c2, c0, rd0, GG = build(a)
    same = canon({k: v for k, v in c.items() if k != "precheck"}) == canon({k: v for k, v in c2.items() if k != "precheck"})
    diff = [] if same else ["%s %s" % x for x in paths_diff({k: v for k, v in c.items() if k != "precheck"},
                                                             {k: v for k, v in c2.items() if k != "precheck"})][:30]
    sd = source_diff(c0, c)
    r = dict(cfg=cfgp, regenerated_equal=bool(same), regenerated_diff=diff, source_diff_ok=sd["ok"], source_unexpected=sd["unexpected"],
             source_changed=sd["changed"], ok=bool(same and sd["ok"]))
    if not quiet:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return r


# ====================================================================== gate (dry: nothing launched, no run folder made)
def gate_d19b(c):
    src = open(T50 + "/g50_chain.py", encoding="utf8").read()
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gate"]
    if len(fn) != 1:
        return ["flip50/g50_chain.py has no unique gate()"]
    ns = dict(cfg=c, GC=GC50, os=os, json=json)
    exec(compile(ast.Module(body=fn, type_ignores=[]), T50 + "/g50_chain.py [gate only, read by flip50h]", "exec"), ns)
    return ns["gate"]()


def cmd_gate(cfgp):
    c = jload(cfgp)
    rid = c["run_id"]
    bad = []
    groove = bool((c.get("bed") or {}).get("groove"))
    if groove:
        r = subprocess.run([sys.executable, "-B", T50G2 + "/g50g2_cont.py", "chain", cfgp, "--dry"], capture_output=True, text=True, encoding="utf8",
                           errors="replace", cwd=REPO)
        s = r.stdout or ""
        try:
            g = json.loads(s[s.find("{"):])
            bad += list(g.get("reasons") or [])
            if not g.get("gate_ok") and not bad:
                bad.append("g50g_chain dry gate not ok")
        except Exception:
            bad.append("g50g2_cont chain --dry gave no JSON (rc %s): %s %s" % (r.returncode, s[-400:], (r.stderr or "")[-400:]))
    else:
        bad += gate_d19b(c)
    sc = cmd_selfcheck(cfgp, quiet=True)
    if not sc["ok"]:
        bad.append("selfcheck failed: regenerated_equal %s, unexpected %s" % (sc["regenerated_equal"], sc["source_unexpected"][:5]))
    dst = os.path.join(B50, c.get("out_root", "runs"), rid)
    ran = sorted(glob.glob(os.path.join(dst, "run_c*.json")))
    st = "fresh" if not os.path.exists(dst) else ("resume (%d launch records)" % len(ran) if ran else "seeded or empty folder")
    print(json.dumps(dict(cfg=cfgp, run_id=rid, groove=groove, path="flip50g chain (g50g2_cont chain, groove hip)" if groove else "flip50/g50_chain.py",
                          gate_ok=not bad, reasons=bad, dst_state=st), ensure_ascii=False, indent=1))
    return 0 if not bad else 1


# ====================================================================== compare
def cmd_compare(cfgp):
    c = jload(cfgp)
    G2.compare(cfgp)                              # g49_restart.compare -> <dst>/restart_compare.json
    rid = c["run_id"]
    dst = os.path.join(B50, c.get("out_root", "runs"), rid)
    rc = jload(dst + "/restart_compare.json") or {}
    h = (c.get("case") or {}).get("hero") or {}
    f0, f1 = int(c["f_start"]), int(c["f_end"])
    have = set(int(os.path.basename(p)[2:7]) for p in glob.glob(os.path.join(dst, "surf", "s_*.gw45s")))
    miss = [f for f in range(f0, f1 + 1) if f not in have]
    s = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip50h/h50_long.py compare", run_id=rid, source=c["restart"]["src_run"],
             all_bit_identical_in_overlap=rc.get("all_bit_identical"), overlap_frames=h.get("compared_frames"),
             r5_bytes_equal=[(rc.get("r5") or {}).get("n_bytes_equal"), (rc.get("r5") or {}).get("n_common")],
             volcorr_equal=[(rc.get("volcorr") or {}).get("n_equal"), (rc.get("volcorr") or {}).get("n_common")],
             beyond_source_frames=h.get("beyond_source_frames"), every_frame_surf_complete=not miss, surf_missing_first=miss[:20],
             n_surf=len([f for f in have if f0 <= f <= f1]), n_expected=f1 - f0 + 1,
             tags="【測定】 record-to-record comparison (g49_restart.compare); frames beyond the source have nothing to compare with")
    json.dump(s, open(dst + "/hero_compare_summary.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0 if (rc.get("all_bit_identical") and not miss) else 3


# ====================================================================== export (f3d50_export long, source best_frames in memory)
def cmd_export(cfgp, extra):
    c = jload(cfgp)
    rid = c["run_id"]
    src = c["restart"]["src_dir"]
    dst = os.path.join(B50, c.get("out_root", "runs"), rid)
    rc = jload(dst + "/restart_compare.json") or {}
    ident = bool(rc.get("all_bit_identical"))
    bfp = src + "/pana/best_frames.json"
    import f3d50_export as FX
    orig = FX.Run.__init__
    used = {}

    def init(self, name):
        orig(self, name)
        if self.bf is None and self.id == rid and ident and os.path.exists(bfp):
            self.bf = json.load(open(bfp, encoding="utf8"))
            used["best_frames"] = bfp
    FX.Run.__init__ = init
    args = ["--run", rid] + list(extra)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        FX.main_long(args)
    out_s = buf.getvalue()
    i = out_s.find("{")
    j = json.loads(out_s[i:]) if i >= 0 else {}
    if "--dry" in extra:
        print(json.dumps(dict(dry=j, best_frames_from_source=used.get("best_frames"), compare_identical=ident), ensure_ascii=False, indent=1))
        return 0
    out = j.get("out")
    note = dict(tool="flip50h/h50_long.py export (f3d50_export.py long unchanged)", am=HR.AM_ID, source_run=c["restart"]["src_run"],
                best_frames_from_source=used.get("best_frames"), compare_all_bit_identical_in_overlap=ident,
                overlap_frames=(c["case"].get("hero") or {}).get("compared_frames"), beyond_source_frames=(c["case"].get("hero") or {}).get("beyond_source_frames"),
                why_ja=("この記録し直しには解析がない。元の計算と重なるコマは 1 bit も違わない（restart_compare.json）ので、元の計算の pana/best_frames.json の"
                        "判定（同じコマ番号）を崩れ・原画のコマに使った。元の終わりより後の崩れには判定がない") if used.get("best_frames") else
                       "判定（best_frames）なし：原画のコマは選ばれていない（compare が同一でない、または元の判定がない）")
    if out and os.path.exists(out + "/manifest.json"):
        man = jload(out + "/manifest.json")
        if used.get("best_frames"):
            man["breakers_source"] = bfp.replace(REPO + "/", "") + "（元の計算の判定。記録し直しは重なるコマで元と 1 bit も違わない：%s/restart_compare.json）" % dst.replace(REPO + "/", "")
        man["hero_long"] = note
        json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
        json.dump(dict(note, export=j), open(out + "/hero_export.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(j, hero=note), ensure_ascii=False, indent=1, default=float))
    return 0 if out else 4


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    if not argv:
        print(__doc__); sys.exit(1)
    cmd = argv[0]
    if cmd == "cfg":
        pos, o = opts(argv[1:])
        if "run" not in o:
            raise SystemExit("cfg needs --run=<DM1A|DG1|DF1A|run id>")
        sys.exit(cmd_cfg(o))
    elif cmd == "selfcheck":
        sys.exit(0 if cmd_selfcheck(argv[1])["ok"] else 1)
    elif cmd == "gate":
        sys.exit(cmd_gate(argv[1]))
    elif cmd == "compare":
        sys.exit(cmd_compare(argv[1]))
    elif cmd == "export":
        sys.exit(cmd_export(argv[1], argv[2:]))
    else:
        print(__doc__); sys.exit(1)
