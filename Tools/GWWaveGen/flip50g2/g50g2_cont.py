# -*- coding: utf-8 -*-
"""FLIP50 after DG1 (option D): the DD3-style +48 s continuation cfg and the every-frame surface re-record for the Unity player
(py -3.10 -B; numpy only, no Houdini). 2026-10-17 written new (Claude).

No file of flip46-flip50, flip50g, the hips, build_check*.json, dg1_frozen.json, plan_D_frozen.json, the tables or the ready cfgs is edited.
Everything reuses the unchanged code in memory (the flip50g precedent):
  - DD3 cfg  = flip50/g50_pcfg.preset('DD3', run=<run>) exactly (same run_id, resumes from the run's last checkpoint, +48 s, records windows
               extended, max_hours 2.0); for a groove run (cfg bed.groove, DG1) it is called through flip50g/g50g_pcfg (in-memory groove patch)
               and its precheck is g50g_pcfg.precheck_g. Only max_hours may be raised (--max_hours, default 2.6 h [chosen]: DM1A measured
               5.75-6.49 s/frame incl. the every-3rd-frame surface in 76-92 s -> 1152 frames 1.84-2.08 h + launch reloads, so the preset's
               2.0 h would stop once near the end). Physics keys are asserted equal to the run's cfg.json. The cfg is written to
               Unity/Build/FLIP50/_scratch/post_dg1/cfg/ (never runs/ready).
  - rr cfg   = the DA3r analogue (flip49 g49_pcfg preset DA3r, g49_restart.py): the same physics from checkpoint v.<k> of the run into a NEW run
               folder runs/<short>r_..._c<k>_t<t>, r5 and r4 every frame (hf, r2, r3 were already every frame), still offset copied from the
               run's launch records, ckpt_every 24. Extra checks as DA3r: physics keys = every launch cfg of the run, hip sha = the run's,
               runtime module shas = the run's, checkpoint full size, volcorr state ready, records every frame, measured cost <= max_hours.
  - seed / compare = flip49/g49_restart.py seed / compare run unchanged with its module global GC replaced in memory by a shim whose B49 is
               Build/FLIP50 (so src = Build/FLIP50/runs/<run>, dst = Build/FLIP50/runs/<rr id>; the same copy list: ckpt v.<k>.sim,
               volcorr/ref.json, state.jsonl rows f <= k, vd_<k>.txt, vd_<k+1>.txt; the run folder is read only).
  - chain    = for a groove run: flip50g/g50g_chain.py's main() in memory with two changes: g50g_common.cfg_groove_ok also accepts a re-record
               id of DG1 whose cfg.restart.src_run is the DG1 main run (every other groove/hip/frozen/untouched/order item unchanged), and
               each launch is flip50g2/g50g2_run.py (the same accept, then the unchanged flip50g/g50g_run.py). For a D19B run (DM1A, DF1A)
               the unchanged flip50/g50_chain.py takes the rr cfg directly.

  py -3.10 -B g50g2_cont.py backup  --run=<run>                     copy cfg.json + pana/ to _scratch/post_dg1/backup_<run>_<t_end>/ (+ sha list)
  py -3.10 -B g50g2_cont.py dd3     --run=<run> [--max_hours=2.6] [--dry]
  py -3.10 -B g50g2_cont.py rr      --run=<run> --ckpt=<k> --t_end=<s> [--tau=<frame>] [--max_hours=<h>] [--dry]
  py -3.10 -B g50g2_cont.py seed    <rr cfg>
  py -3.10    g50g2_cont.py chain   <rr cfg> [--dry]                (groove runs; D19B runs: py -3.10 flip50/g50_chain.py <rr cfg>)
  py -3.10 -B g50g2_cont.py compare <rr cfg>
Tags: 【測定】 measured (run records), 【計算】 computed, 【選び】 chosen.
"""
import os, sys, json, copy, glob, time, hashlib, shutil, types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
T50, T50G, T49, T46 = (REPO + "/Tools/GWWaveGen/" + s for s in ("flip50", "flip50g", "flip49", "flip46"))
for _p in (HERE, T50G, T50, T49, T46):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                  # noqa: E402
import g50_common as GC50           # noqa: E402  read only

B50 = GC50.B50
POST = B50 + "/_scratch/post_dg1"
CFG_DIR = POST + "/cfg"
RR_CKPT_EVERY = 24                  # 【選び】 as DA3r (a relaunch redoes <= 23 frames)
RR_MAX_H = 1.6                      # 【選び】 cap of one re-record chain (expected 0.8-1.0 h for ~330-400 frames)
DD3_MAX_H = 2.6                     # 【選び】 see the module doc
PHYS_KEYS = ("kind", "layout", "parms", "sf", "dir", "wave", "drift", "solver", "box", "bed", "gauges", "level_regions", "level_box",
             "level_guard_m", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "analysis", "hip", "build_check")
RUNTIME_PREFIX = ("flip50/", "flip49/", "flip48/", "flip47/", "flip46/", "flip50g/")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def run_dir(name):
    if "/" in name or "\\" in name:
        return name.replace("\\", "/").rstrip("/")
    return B50 + "/runs/" + name


def is_groove(c):
    return bool((c.get("bed") or {}).get("groove"))


def tools_for(c):
    """(PC, precheck) for the run: g50_pcfg unpatched for D19B runs; under the groove patch (g50g_pcfg) for DG1."""
    if is_groove(c):
        import g50g_common as GG
        accept_rr(GG)
        import g50g_pcfg as GGP            # patches g48/g49/g50_common in memory and imports g50_pcfg on the patched module
        return GGP.PC, GGP.precheck_g, GG
    import g50_pcfg as PC
    return PC, PC.precheck, None


def accept_rr(GG):
    """in memory only: g50g_common.cfg_groove_ok also accepts a re-record of the DG1 main run (cfg.restart.src_run == RUN_MAIN and run_id
    'DG1r_' + ...). Every other item of the check is the unchanged original."""
    if getattr(GG, "_g2_accept", False):
        return
    orig = GG.cfg_groove_ok

    def cfg_groove_ok(cfg):
        bad = orig(cfg)
        rid = cfg.get("run_id") or ""
        rs = cfg.get("restart") or {}
        if rid.startswith("DG1r_") and rs.get("src_run") == GG.RUN_MAIN:
            bad = [b for b in bad if not b.startswith("run_id %s is neither" % rid)]
        return bad
    cfg_groove_ok.__doc__ = "flip50g2 in-memory wrapper of g50g_common.cfg_groove_ok (+ DG1 re-record ids)"
    GG.cfg_groove_ok = cfg_groove_ok
    GG._g2_accept = True


def tag(t):
    return GC50.tag(t) if hasattr(GC50, "tag") else ("%g" % t).replace(".", "p")


def write(c, name, dry):
    p = CFG_DIR + "/" + name
    if dry:
        return p + " (dry: not written)"
    os.makedirs(CFG_DIR, exist_ok=True)
    if os.path.exists(p):
        old = json.load(open(p, encoding="utf8"))
        if {k: v for k, v in old.items() if k != "precheck"} != {k: v for k, v in c.items() if k != "precheck"}:
            raise SystemExit("%s exists with other content; remove it by hand if it is really to be replaced" % p)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    return p


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    return pos, o


# ====================================================================== backup (before the extended run is re-analysed)
def backup(o):
    rd = run_dir(o["run"])
    c = json.load(open(rd + "/cfg.json", encoding="utf8"))
    dst = POST + "/backup_%s_t%s" % (c["run_id"], tag(float(c["t_end_s"])))
    if os.path.exists(dst):
        raise SystemExit("%s exists" % dst)
    os.makedirs(dst)
    files = [rd + "/cfg.json"] + sorted(glob.glob(rd + "/pana/**/*", recursive=True))
    rec = {}
    for p in files:
        if os.path.isdir(p):
            continue
        rel = os.path.relpath(p, rd).replace("\\", "/")
        q = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copyfile(p, q)
        rec[rel] = sha(q)
        assert rec[rel] == sha(p)
    json.dump(dict(src=rd, time=time.strftime("%Y-%m-%d %H:%M:%S"), files=rec), open(dst + "/backup.json", "w", encoding="utf8"), indent=1)
    print("backup", dst, len(rec), "files")


# ====================================================================== DD3 (+48 s continuation of the same run)
def dd3(o):
    rd = run_dir(o["run"])
    c0 = json.load(open(rd + "/cfg.json", encoding="utf8"))
    PC, pre, GG = tools_for(c0)
    c = PC.preset("DD3", {"run": rd})
    if GG is not None:
        c["precheck"] = pre(c)
    mh = float(o.get("max_hours", DD3_MAX_H))
    c["max_hours"] = mh
    same = {k: c.get(k) == c0.get(k) for k in PHYS_KEYS if k in c0 or k in c}
    if not all(same.values()):
        raise SystemExit("DD3 cfg physics keys differ from the run's cfg.json: %s" % [k for k, v in same.items() if not v])
    # measured rate of the run's last launches (for the time estimate only)
    est = cost(rd, int(c["f_resume_est"]) - 1, int(c["f_end"]), every_frame_surf=False, wall_limit=float(c.get("wall_limit_s", 1740)), sp=int(c.get("ckpt_every", 48)))
    c["case"]["dd3_wrapper"] = dict(tool="Tools/GWWaveGen/flip50g2/g50g2_cont.py dd3", preset="flip50/g50_pcfg.preset('DD3') unchanged" + (
        " under the in-memory groove patch (flip50g/g50g_pcfg), precheck g50g_pcfg.precheck_g" if GG else ""),
        base_cfg=rd.replace(REPO + "/", "") + "/cfg.json", base_cfg_sha16=sha(rd + "/cfg.json")[:16], physics_keys_equal=sorted(same),
        max_hours_preset=2.0, max_hours=mh, max_hours_why="budget only [chosen]: measured rate x 1152 frames (est %s h) + launch reloads" % est.get("total_h"),
        est=est)
    name = "%s__DD3_t%s.json" % (c["run_id"], tag(float(c["t_end_s"])))
    p = write(c, name, "dry" in o)
    pc = c["precheck"]
    print(json.dumps(dict(cfg=p, run_id=c["run_id"], f_resume_est=c["f_resume_est"], f_end=c["f_end"], t_end_s=c["t_end_s"], windows=c["records"]["windows"],
                          max_hours=mh, precheck_ok=pc.get("ok"), reason=pc.get("reason"), time=pc.get("time"), est_measured=est,
                          launch=("py -3.10 %s/g50g_chain.py %s" % (T50G, p)) if GG else ("py -3.10 %s/g50_chain.py %s" % (T50, p))),
                     ensure_ascii=False, indent=1, default=float))


# ====================================================================== cost from the run's own launches (DA3r rule)
def cost(rd0, k, f_end, every_frame_surf=True, wall_limit=1740.0, sp=RR_CKPT_EVERY, launch_extra_s=2.0):
    """measured per-frame solve time of the run (r6 wall; a frame in 2 launches: the later) + surface time (median of surf_s, every frame
    for a re-record, every 3rd frame otherwise) + other per-frame overhead; frames past the run's end use the last 200 frames' median.
    Launch cuts as g50_chain / g50_run (stop after the frame that passes wall_limit; next launch from the last multiple of sp)."""
    sim, surf, other = {}, [], []
    for p in sorted(glob.glob(os.path.join(rd0, "r6_c*.npz"))):
        c_ = int(os.path.basename(p)[4:9])
        rp = os.path.join(rd0, "run_c%05d.json" % c_)
        if not os.path.exists(rp):
            continue
        r = json.load(open(rp, encoding="utf8"))
        d = np.load(p)
        fr, w, s = d["frames"], d["wall"], d["surf_s"]
        for f_, w_ in zip(fr, w):
            sim[int(f_)] = float(w_)
        surf += [float(v) for v in s if v > 0]
        other.append((float(r["wall_total_s"]) - float(w.sum()) - float(s.sum())) / max(len(fr), 1))
    if not sim or not surf:
        return dict(missing="no r6 / run records in %s" % rd0)
    last = sorted(sim)[-200:]
    tail = float(np.median([sim[f_] for f_ in last]))
    s_surf = float(np.median(surf[-200:]))
    s_other = float(np.median(other))
    need = list(range(k + 1, f_end + 1))
    cst = {f_: sim.get(f_, tail) + (s_surf if (every_frame_surf or (f_ - 1) % 3 == 0) else 0.0) + s_other for f_ in need}
    n_extrap = sum(1 for f_ in need if f_ not in sim)
    launches, f0 = [], k + 1
    for _ in range(40):
        t, f_ = launch_extra_s, f0
        while f_ <= f_end:
            t += cst[f_]
            if t > wall_limit:
                break
            f_ += 1
        done = min(f_, f_end)
        launches.append(dict(f_start=f0, f_done=done, est_s=round(t, 1)))
        if done >= f_end:
            break
        ck = (done // sp) * sp
        if ck + 1 <= f0:
            return dict(missing="spacing %d too coarse for one launch" % sp, launches=launches)
        f0 = ck + 1
    tot = sum(L_["est_s"] for L_ in launches)
    return dict(frames=len(need), frames_extrapolated=n_extrap, s_solve_tail_median=tail, s_surf=s_surf, s_other=s_other,
                s_per_frame_mean=float(np.mean(list(cst.values()))), n_launches=len(launches), launches=launches, total_h=round(tot / 3600.0, 3),
                tag="【測定】 run r6/run_c records x 【計算】 launch cuts; frames past the run end use the last 200 frames' median")


# ====================================================================== rr (every-frame re-record from a checkpoint)
def still_offset(rd0, f_from):
    best = None
    for p in sorted(glob.glob(os.path.join(rd0, "run_c*.json"))):
        r = json.load(open(p, encoding="utf8"))
        so = (r.get("still_offset") or {})
        if so.get("value") is not None and int(r.get("f_start") or 0) <= f_from:
            best = (float(so["value"]), "%s (%s)" % (os.path.basename(p), so.get("source")))
    return best if best else (None, "no still_offset in the run's run_c*.json")


def rr(o):
    rd0 = run_dir(o["run"])
    c0 = json.load(open(rd0 + "/cfg.json", encoding="utf8"))
    PC, pre, GG = tools_for(c0)
    L = int(round(float((c0.get("dir") or c0.get("sf") or {}).get("T", 12.0)) * 24))      # one wave period (frames)
    if o.get("ckpt", "auto") == "auto" or o.get("t_end", "auto") == "auto":
        if not o.get("tau"):
            raise SystemExit("--ckpt=auto / --t_end=auto need --tau=<loop start frame> (from f3d50_export.py loop --dry)")
        tau = int(o["tau"])
        cks = sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim")))
        if o.get("ckpt", "auto") == "auto":
            le = [v for v in cks if v <= tau - 1]
            if not le:
                raise SystemExit("no checkpoint <= tau - 1 = %d in %s/ckpt" % (tau - 1, rd0))
            o["ckpt"] = str(le[-1])                   # 【選び】 the latest checkpoint before the window (fewest warm-up frames)
        if o.get("t_end", "auto") == "auto":          # 【選び】 window + the seam frame tau + L + 1 s margin, inside the run
            o["t_end"] = "%g" % min(float(c0["t_end_s"]), round((tau + L + 24 - 1) / 24.0 * 4) / 4.0)
    k = int(o["ckpt"])
    t_end = float(o["t_end"])
    f_from, f_end = k + 1, int(GC50.frames_for(0.0, t_end))
    t_from = (f_from - 1) / 24.0
    short = c0["run_id"].split("_")[0]
    rest = "_".join(c0["run_id"].split("_")[1:])
    rid = "%sr_%s_c%04d_t%s" % (short, rest, k, tag(t_end))
    off, off_src = still_offset(rd0, f_from)
    c = copy.deepcopy(c0)
    for k_ in ("hip_sha256", "module_shas_at_chain_start", "precheck", "f_resume_est", "dg1_chain"):
        c.pop(k_, None)
    mh = float(o.get("max_hours", RR_MAX_H))
    c.update(run_id=rid, out_root="runs", f_start=f_from, f_first=f_from, f_end=f_end, t_end_s=t_end, still_offset_m=off,
             ckpt_on=1, ckpt_every=RR_CKPT_EVERY, ckpt_list=[RR_CKPT_EVERY, RR_CKPT_EVERY // 2], wall_limit_s=min(float(c0.get("wall_limit_s", 1740)), 1740.0),
             max_hours=mh, pstats_frames=[f_from, f_end])
    c["records"]["r4"]["every"] = 1
    c["records"]["r5"]["every"] = 1
    c["records"]["windows"] = [[t_from, t_end]]
    cs = c["case"]
    for k_ in ("continuation_of", "rerun_of", "windows_source", "heavy_rule", "follow_up", "dd3_wrapper"):
        cs.pop(k_, None)
    cs.update(queue_id=short + "r", judged=False, label="re-record of %s for the Unity player: same physics, every-frame surface records" % c0["run_id"],
              restart_of=c0["run_id"], restart_ckpt_frame=k, windows_source="every frame %d-%d (r4, r5; hf, r2, r3 as before)" % (f_from, f_end),
              why="FLIP50 r5 exists only every 3rd frame (8 records/s); the FLIP3D player then holds each record 3 video frames "
                  "(Docs/Progress/FLIP3D_Playback_ja.md 5, 8); DA3r precedent (flip49 g49_restart.py)")
    if o.get("tau"):
        cs["loop_tau_frame"] = int(o["tau"])
    ck_src = os.path.join(rd0, "ckpt", "v.%04d.sim" % k).replace("\\", "/")
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=k, ckpt_t_s=(k - 1) / 24.0, ckpt_file=ck_src,
                        ckpt_bytes=os.path.getsize(ck_src) if os.path.exists(ck_src) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip50g2/g50g2_cont.py seed <cfg> (g49_restart.seed, Build/FLIP50 in memory)",
                        compare="py -3.10 -B Tools/GWWaveGen/flip50g2/g50g2_cont.py compare <cfg>")
    c["note"] = ("%s re-record (flip50g2, 2026-10-17; not judged): from checkpoint v.%04d (%.3f s) of %s with the same settings, %.3f-%g s (frames %d-%d), "
                 "surface (r5) and r4 every frame, new folder runs/%s; shape not changed (physics only)" % (short, k, (k - 1) / 24.0, c0["run_id"],
                                                                                                         t_from, t_end, f_from, f_end, rid))
    pc = pre(c)
    ck = pc["checks"]
    others = [os.path.getsize(p) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim"))]
    ck["rr_ckpt_exists_full_size"] = bool(os.path.exists(ck_src) and others and os.path.getsize(ck_src) >= 0.5 * float(np.median(others)))
    if o.get("tau"):
        ck["rr_ckpt_le_tau_minus_1"] = bool(k <= int(o["tau"]) - 1)
        ck["rr_t_end_covers_loop_and_seam"] = bool(f_end >= int(o["tau"]) + L)
    launch_cfgs = sorted(glob.glob(os.path.join(rd0, "cfg_c*.json")))
    same = []
    for p in [os.path.join(rd0, "cfg.json")] + launch_cfgs:
        q = json.load(open(p, encoding="utf8"))
        same.append(all(q.get(kk) == c.get(kk) for kk in PHYS_KEYS))
    ck["rr_physics_same_as_run_all_launches"] = bool(same and all(same))
    hip = GC50.HIP if GG is None else GG.HIP_G
    ck["rr_hip_same_as_run"] = bool(os.path.exists(hip) and sha(hip) == c0.get("hip_sha256"))
    m_now = GC50.module_shas() if GG is None else GG.module_shas_g()
    m_run = c0.get("module_shas_at_chain_start") or {}
    keys = [kk for kk in m_run if kk.startswith(RUNTIME_PREFIX)]
    ck["rr_runtime_modules_same_as_run"] = bool(keys and all(m_now.get(kk) == m_run.get(kk) for kk in keys))
    ck["rr_new_folder"] = bool(rid != c0["run_id"] and not os.path.exists(os.path.join(B50, "runs", rid, "run.json")))
    ck["rr_records_every_frame"] = bool(int(c["records"]["r5"]["every"]) == 1 and int(c["records"]["r4"]["every"]) == 1)
    ck["rr_still_offset_from_run"] = bool(off is not None)
    vdir = os.path.join(rd0, "volcorr")
    rows = set()
    if os.path.exists(os.path.join(vdir, "state.jsonl")):
        for ln in open(os.path.join(vdir, "state.jsonl"), encoding="utf8"):
            try:
                rows.add(int(json.loads(ln)["f"]))
            except Exception:
                pass
    nT = int(round(float((c0.get("dir") or c0.get("sf") or {}).get("T", 12.0)) * 24))
    ck["rr_volcorr_state_ready"] = bool(os.path.exists(os.path.join(vdir, "ref.json")) and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % k))
                                        and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % f_from)) and all(f_ in rows for f_ in range(k - nT + 1, k + 1)))
    est = cost(rd0, k, f_end, every_frame_surf=True, wall_limit=float(c["wall_limit_s"]), sp=RR_CKPT_EVERY)
    ck["rr_measured_est_le_max_hours"] = bool(est.get("total_h") is not None and est["total_h"] <= mh)
    pc["rr"] = dict(cost_measured=est, hip=hip, physics_keys=list(PHYS_KEYS), launch_cfgs_compared=[os.path.basename(p) for p in launch_cfgs],
                    runtime_modules_compared=len(keys))
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(kk for kk, v in ck.items() if not v)
    c["precheck"] = pc
    p = write(c, rid + ".json", "dry" in o or not pc["ok"])
    print(json.dumps(dict(cfg=p, run_id=rid, frames=[f_from, f_end], t=[t_from, t_end], still_offset=[off, off_src], precheck_ok=pc["ok"], reason=pc["reason"],
                          est=est, chain=("py -3.10 %s/g50g2_cont.py chain %s" % (HERE, p)) if GG else ("py -3.10 %s/g50_chain.py %s" % (T50, p))),
                     ensure_ascii=False, indent=1, default=float))


# ====================================================================== seed / compare (g49_restart unchanged, Build/FLIP50 in memory)
def restart_module():
    import g49_restart as RS
    RS.GC = types.SimpleNamespace(B49=B50)        # dirs() reads only GC.B49 (src, dst, 'under Build/...' check)
    return RS


def seed(cfgp):
    c = json.load(open(cfgp, encoding="utf8"))
    if (c.get("restart") or {}).get("src_dir", "").find("/FLIP50/") < 0:
        raise SystemExit("not a FLIP50 re-record cfg")
    restart_module().seed(cfgp)


def compare(cfgp):
    restart_module().compare(cfgp)


# ====================================================================== chain (groove runs: g50g_chain in memory, rr ids accepted)
def chain(cfgp, dry=False):
    c = json.load(open(cfgp, encoding="utf8"))
    if not is_groove(c):
        raise SystemExit("D19B run: use py -3.10 %s/g50_chain.py %s (unchanged; no id check there)" % (T50, cfgp))
    import g50g_common as GG
    accept_rr(GG)
    import g50g_chain as GCH
    i = [j for j, r in enumerate(GCH.REPL) if r[0] == 'RUN = GC.TOOLS + "/g50_run.py"']
    if len(i) != 1:
        raise SystemExit("g50g_chain.REPL has no unique RUN replacement")
    GCH.REPL[i[0]] = ('RUN = GC.TOOLS + "/g50_run.py"', 'RUN = %r' % (HERE + "/g50g2_run.py"), 1)
    sys.argv = [GCH.__file__, cfgp] + (["--dry"] if dry else [])
    GCH.main()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, o = opts(sys.argv[1:])
    if not pos:
        print(__doc__); sys.exit(1)
    if pos[0] == "backup":
        backup(o)
    elif pos[0] == "dd3":
        dd3(o)
    elif pos[0] == "rr":
        rr(o)
    elif pos[0] == "seed":
        seed(pos[1])
    elif pos[0] == "compare":
        compare(pos[1])
    elif pos[0] == "chain":
        chain(pos[1], dry="dry" in o)
    else:
        print(__doc__); sys.exit(1)
