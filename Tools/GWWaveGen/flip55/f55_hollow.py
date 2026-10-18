# -*- coding: utf-8 -*-
"""FLIP55: the 3D HOLLOW quantities (R0 ruler = pv53 ruler on the centre section r2) of a run, the DFG-2B-V baseline and the frozen reading
(py -3.10 -B; numpy, scipy, scikit-image). 2026-10-19 written new (Claude).
The measuring code is Unity/Build/FLIP54/r0/r0_hollow.py (frozen with its registered rule r0_rule_registered.json, sha checked) used UNCHANGED:
this tool only points its run table (r0_hollow.RUNS) and its mask folder (r0_hollow.HERE) at the run being measured, IN MEMORY of its own process.
Per pv53 group n (judge groups; window [f_max - 36, f_max + 72] frames = t_max - 1.5 .. + 3.0 s, crest track and ruler = pv53's):
  alive frames   r2 frames in the PRIMARY window [f_max - 36, f_max + 96] (t_max - 1.5 .. + 4.0 s = R0's extended window; the pv53 window
                 [f_max - 36, f_max + 72] cuts DFG-2B-V group 1's growing cavity: its R0 hollow instant sits at the window end, flag 'edge';
                 the pv53-window values are reported with the suffix _pv) whose section crest eta_c >= 0.6 x Hc_ref (pv53 crest floor AM-DFG2a; the 3D stand-in for R54's
                 'before touchdown': a collapsed crest does not count)
  air_max        max cavity air A_air / eta_c^2 over the alive frames (R0 column rule, = R54 air_max_pre's rule)            GAIN KEY
  hood_max       max hood_area over the alive frames (= R54 hood_max)                                                       GAIN KEY
  hood78         max hood_area over the alive frames with chord <= 78 deg (0 if none)                                       report
  chord_at_hood_max, lip_at_hood_max (lip_thick_mid / eta_c), lip_at_hood_max_m (x eta_c), eta_at_hood_max (m)              report
  hi_*           the R0 hollow instant (eligible: 50 <= chord <= 100 deg, lip >= 0.30, eta_c >= 0.6 Hc_ref; max air): air, air m^2,
                 lip, lip m, chord (None when no frame is eligible)                                                         report
  best_score3, best_lip   pv53's most print-like instant of the group                                                       report
Reading (f55_common.reading, frozen in the plan): RESOLUTION_MATTERS_3D iff air_max or hood_max grows >= +25 % against the baseline: group-1
stage -> group 1; full stage -> median over groups 1-3 >= +25 % AND >= 2 groups each >= +25 %. Baseline: DFG-2B-V (A375); the 0.5 m identity
nest C2ID (C2; DFG-2B-V beside it, report).
usage:
  py -3.10 -B f55_hollow.py baseline                       DFG-2B-V -> Unity/Build/FLIP55/plan/hollow_baseline_DFGBV.json (+ reproduction check
                                                           of the r2 series against r0_hollow.json's DFG2BV series)
  py -3.10 -B f55_hollow.py measure <run_dir> [--pv=<pv53 json>] [--groups=1|all]   -> <run>/f55/hollow_F55.json
  py -3.10 -B f55_hollow.py verdict <run_dir> --stage=g1|full [--base=<hollow json>] -> <run>/f55/reading_F55_<stage>.json
  py -3.10 -B f55_hollow.py selftest                       synthetic checks of the extraction and the reading; baseline file vs plan (no FLIP)
"""
import os, sys, json, math, io, contextlib, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
import f55_common as C               # noqa: E402

R0_RULE_SHA = "3fd82c862630c4536ee7f6a88ac31e7b86f58d391293bcb32b672eb5cb94e567"   # = r0_hollow.RULE_SHA (registered 2026-10-18 19:58:57)
CREST_FLOOR = 0.6
CHORD78 = 78.0


def fin(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def r0():
    sys.path.insert(0, C.R0_DIR)
    import r0_hollow as R0            # noqa: E402  frozen
    if C.sha(R0.RULE) != R0_RULE_SHA or R0.RULE_SHA != R0_RULE_SHA:
        raise SystemExit("R0 rule file changed after registration: %s" % C.sha(R0.RULE))
    return R0


# ------------------------------------------------------------------ quantities of one R0 group
def _window_q(ser, hc):
    alive = [r for r in ser if fin(r.get("eta_c")) and fin(hc) and r["eta_c"] >= CREST_FLOOR * hc - 1e-9]
    q = dict(n_frames=len(ser), n_alive=len(alive))
    airs = [r for r in alive if fin(r.get("air"))]
    hoods = [r for r in alive if fin(r.get("hood"))]
    q["air_max"] = max(r["air"] for r in airs) if airs else None
    q["air_max_frame"] = max(airs, key=lambda r: (r["air"], -r["frame"]))["frame"] if airs else None
    if hoods:
        hm = max(hoods, key=lambda r: (r["hood"], -r["frame"]))
        q.update(hood_max=hm["hood"], hood_max_frame=hm["frame"], chord_at_hood_max=hm.get("chord"), lip_at_hood_max=hm.get("lip"),
                 lip_at_hood_max_m=(hm["lip"] * hm["eta_c"]) if fin(hm.get("lip")) else None, eta_at_hood_max=hm.get("eta_c"))
        h78 = [r["hood"] for r in hoods if fin(r.get("chord")) and r["chord"] <= CHORD78]
        q["hood78"] = max(h78) if h78 else 0.0
    else:
        q.update(hood_max=None, hood_max_frame=None, chord_at_hood_max=None, lip_at_hood_max=None, lip_at_hood_max_m=None, eta_at_hood_max=None,
                 hood78=None)
    return q


def quantities(g):
    """primary window = R0's extended window [f_max - 36, f_max + 96] (t_max - 1.5 .. + 4.0 s; R0's own 'edge' extension), because the pv53
    window [f_max - 36, f_max + 72] cuts DFG-2B-V group 1's still-growing cavity (R0 hollow instant f 1483 at the window end 1484, flag 'edge'
    [measured, r0_hollow.json]); the pv53-window values are reported beside them with the suffix _pv."""
    hc = g.get("Hc_ref")
    f_max = g.get("f_max")
    f_hi_pv = (g.get("window") or [None, 10 ** 9])[1]
    f_hi_ext = (f_max + 96) if f_max is not None else 10 ** 9
    ser_all = [r for r in (g.get("series") or []) if not r.get("error") and r.get("frame") is not None]
    ext = _window_q([r for r in ser_all if r["frame"] <= f_hi_ext], hc)
    pvw = _window_q([r for r in ser_all if r["frame"] <= f_hi_pv], hc)
    q = dict(n=g.get("n"), f_max=f_max, Hc_ref=hc, window_primary=[f_max - 36 if f_max is not None else None, f_hi_ext], window_pv=[f_max - 36 if f_max is not None else None, f_hi_pv])
    q.update(ext)
    q.update({k + "_pv": v for k, v in pvw.items()})
    hi = g.get("hollow_instant") or None
    q.update(hi_frame=hi.get("frame") if hi else None, hi_air=hi.get("air") if hi else None, hi_air_m2=hi.get("air_m2") if hi else None,
             hi_lip=hi.get("lip") if hi else None, hi_lip_m=(hi["lip"] * hi["eta_c"]) if (hi and fin(hi.get("lip"))) else None,
             hi_chord=hi.get("chord") if hi else None, hi_eta_c=hi.get("eta_c") if hi else None, hi_edge=bool(g.get("edge")))
    pk = g.get("pv53_pick") or {}
    q.update(best_frame=pk.get("frame"), best_score3=pk.get("score3"), best_lip=pk.get("lip"))
    return q


def measure_run(rd, pv=None, groups="all", out_dir=None, tag=None, r4=None):
    R0 = r0()
    rd = os.path.abspath(rd).replace("\\", "/")
    rid = os.path.basename(rd)
    pv = pv or (C.REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (rid, rid))
    if not os.path.exists(pv):
        raise SystemExit("no pv53 json %s (run pv53 first)" % pv)
    out_dir = out_dir or (rd + "/f55")
    od = C.guard_out(out_dir)
    tag = tag or ("F55_" + rid)
    R0.RUNS[tag] = dict(r2=rd, r4=r4 or rd, pv53=pv)
    R0.HERE = od                                        # the masks npz goes to the output folder (never into FLIP54/r0)
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        res = R0.run_one(tag, log=lambda *a: None)
    gs = [g for g in res["groups"] if groups == "all" or int(g["n"]) in [int(v) for v in str(groups).split(",")]]
    out = dict(run_id=rid, run_dir=C.rel(rd), pv53=C.rel(pv), r4_source=C.rel(r4 or rd), tool=C.rel(os.path.abspath(__file__)),
               tool_sha256=C.sha(os.path.abspath(__file__)), r0_tool_sha256=C.sha(C.R0_TOOL), r0_rule_sha256=R0_RULE_SHA, pv53_sha256=C.sha(C.PV53),
               eta0=res.get("eta0"), groups={int(g["n"]): quantities(g) for g in gs}, r0_groups=gs, seconds=round(time.time() - t0, 1),
               date=time.strftime("%Y-%m-%d %H:%M:%S"),
               tags=dict(numbers="measured (FLIP records + the frozen R0 / pv53 ruler)", alive_rule="registered (FLIP55 plan)"))
    return out


# ------------------------------------------------------------------ the DFG-2B-V baseline
def baseline():
    out = measure_run(C.DFGBV_RUN, pv=C.DFGBV_PV53, groups="all", out_dir=C.SCRATCH + "/baseline_DFGBV", tag="F55BASE_DFGBV", r4=C.DFGBV_RUN)
    # reproduction: the r2-derived series must equal r0_hollow.json's DFG2BV series (same r2 source, same ruler; r4 differs only in the
    # side projections, which are report only and not used here)
    ref = (C.jload(C.R0_JSON).get("runs") or {}).get("DFG2BV") or {}
    rep = {}
    for g in out["r0_groups"]:
        rg = [x for x in ref.get("groups", []) if x["n"] == g["n"]]
        if not rg:
            rep[g["n"]] = False; continue
        a = {r["frame"]: r for r in g["series"]}
        b = {r["frame"]: r for r in rg[0]["series"]}
        keys = ("score3", "chord", "lip", "hood", "air", "eta_c", "x_c")
        same = bool(set(a) == set(b) and all((a[f].get(k) == b[f].get(k)) or (fin(a[f].get(k)) and fin(b[f].get(k)) and abs(a[f][k] - b[f][k]) < 1e-9)
                                             for f in a for k in keys))
        rep[g["n"]] = same
    out["reproduces_r0_hollow_json_DFG2BV"] = rep
    out["reproduction_ok"] = bool(rep and all(rep.values()))
    out.pop("r0_groups", None)
    C.jdump(out, C.BASELINE)
    return out


# ------------------------------------------------------------------ reading
def base_groups(base_path=None):
    b = C.jload(base_path or C.BASELINE)
    return {int(k): v for k, v in b["groups"].items()}, b


def verdict(rd, stage, base_path=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    m = C.jload(rd + "/f55/hollow_F55.json")
    new = {int(k): v for k, v in m["groups"].items()}
    base, bj = base_groups(base_path)
    groups = (1,) if stage == "g1" else (1, 2, 3)
    pl = C.jtry(C.PLAN) or {}
    bsha = C.sha(base_path or C.BASELINE)
    frozen_b = ((pl.get("hollow") or {}).get("baseline_file_sha256"))
    r = C.reading(new, base, groups)
    r.update(stage=stage, run=C.rel(rd), baseline=C.rel(base_path or C.BASELINE), baseline_sha256=bsha,
             baseline_as_frozen=bool(base_path is not None or bsha == frozen_b), plan_sha_ok=C.plan_sha_ok(),
             ruler_ok=bool(m.get("r0_tool_sha256") == ((pl.get("code_sha256_frozen_used") or {}).get("Unity/Build/FLIP54/r0/r0_hollow.py"))
                           and m.get("pv53_sha256") == ((pl.get("code_sha256_frozen_used") or {}).get("Tools/GWWaveGen/flip53/pv53.py"))),
             date=time.strftime("%Y-%m-%d %H:%M:%S"),
             tags=dict(verdict="decided by the frozen FLIP55 reading rule from measured quantities; AI self-assessment, the user judges the look"))
    if not r["plan_sha_ok"] or not r["baseline_as_frozen"] or not r["ruler_ok"]:
        r["verdict_by_rule"] = r["verdict"]
        r["verdict"] = "NO_READING_" + ("PLAN" if not r["plan_sha_ok"] else ("BASELINE" if not r["baseline_as_frozen"] else "RULER")) + "_CHANGED"
    C.jdump(r, rd + "/f55/reading_F55_%s.json" % stage)
    return r


# ------------------------------------------------------------------ selftest (no FLIP records)
def selftest():
    ok = {}
    ser = [dict(frame=100 + i, eta_c=6.0 - 0.05 * i, air=0.1 + 0.02 * i, hood=0.05 * i, chord=120.0 - 6 * i, lip=0.3) for i in range(12)]
    ser.append(dict(frame=200, eta_c=1.0, air=9.0, hood=9.0, chord=50.0, lip=0.3))        # collapsed crest: ignored
    ser.append(dict(frame=300, eta_c=6.0, air=9.0, hood=9.0, chord=50.0, lip=0.3))        # outside the window: ignored
    g = dict(n=1, f_max=136, Hc_ref=8.0, window=[100, 208], series=ser, hollow_instant=dict(frame=105, air=0.2, air_m2=7.0, lip=0.31, chord=90.0, eta_c=5.75),
             pv53_pick=dict(frame=104, score3=0.9, lip=0.3))
    q = quantities(g)
    ok["alive_floor"] = q["n_alive"] == 12 and q["n_alive_pv"] == 12
    ok["air_max"] = abs(q["air_max"] - (0.1 + 0.02 * 11)) < 1e-12
    ok["hood_max"] = abs(q["hood_max"] - 0.55) < 1e-12 and q["hood_max_frame"] == 111
    ok["hood78"] = abs(q["hood78"] - 0.55) < 1e-12           # chord 120 - 66 = 54 <= 78
    ok["lip_m"] = abs(q["lip_at_hood_max_m"] - 0.3 * (6.0 - 0.55)) < 1e-12
    ok["hi"] = abs(q["hi_lip_m"] - 0.31 * 5.75) < 1e-12 and q["best_score3"] == 0.9
    b = {1: dict(air_max=0.30, hood_max=0.27), 2: dict(air_max=0.33, hood_max=0.28), 3: dict(air_max=0.32, hood_max=0.28)}
    r = C.reading({1: dict(air_max=0.40, hood_max=0.28)}, b, (1,))
    ok["g1_air_hit"] = r["verdict"] == "RESOLUTION_MATTERS_3D" and r["gain_quantities"] == ["air_max"]
    r = C.reading({1: dict(air_max=0.36, hood_max=0.30)}, b, (1,))
    ok["g1_not_shown"] = r["verdict"] == "NOT_SHOWN"
    r = C.reading({1: dict(air_max=0.375, hood_max=0.2)}, b, (1,))
    ok["g1_exact_bar"] = r["verdict"] == "RESOLUTION_MATTERS_3D"            # +25 % exactly counts (>=)
    r = C.reading({1: dict(air_max=0.5, hood_max=0.3), 2: dict(air_max=0.5, hood_max=0.3), 3: dict(air_max=0.3, hood_max=0.3)}, b, (1, 2, 3))
    ok["full_two_of_three"] = r["verdict"] == "RESOLUTION_MATTERS_3D"
    r = C.reading({1: dict(air_max=0.9, hood_max=0.3), 2: dict(air_max=0.33, hood_max=0.3), 3: dict(air_max=0.32, hood_max=0.3)}, b, (1, 2, 3))
    ok["full_one_group_not_enough"] = r["verdict"] == "NOT_SHOWN"
    r = C.reading({1: dict(air_max=None, hood_max=0.3)}, b, (1,))
    ok["incomplete"] = r["verdict"] == "INCOMPLETE"
    if os.path.exists(C.PLAN) and os.path.exists(C.BASELINE):
        pl = C.jload(C.PLAN)
        ok["baseline_file_as_frozen"] = bool((pl.get("hollow") or {}).get("baseline_file_sha256") == C.sha(C.BASELINE))
    ok["r0_rule_registered"] = bool(C.sha(C.R0_RULE) == R0_RULE_SHA)
    res = dict(ok=bool(all(ok.values())), checks=ok)
    print(json.dumps(res, ensure_ascii=False))
    return res["ok"]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "selftest":
        sys.exit(0 if selftest() else 1)
    if a[0] == "baseline":
        b = baseline()
        print(json.dumps(C.clean(dict(ok=b["reproduction_ok"], file=C.BASELINE, sha256=C.sha(C.BASELINE), reproduces=b["reproduces_r0_hollow_json_DFG2BV"],
                                      groups={k: {kk: v.get(kk) for kk in ("air_max", "hood_max", "hood78", "chord_at_hood_max", "lip_at_hood_max_m",
                                                                         "hi_air", "hi_lip_m", "best_score3", "n_alive")} for k, v in b["groups"].items()},
                                      seconds=b["seconds"])), ensure_ascii=False))
    elif a[0] == "measure" and len(a) >= 2:
        m = measure_run(a[1], pv=opt.get("pv"), groups=opt.get("groups", "all"))
        m.pop("r0_groups", None)
        p = os.path.abspath(a[1]).replace("\\", "/") + "/f55/hollow_F55.json"
        C.jdump(m, p)
        print(json.dumps(C.clean(dict(ok=True, file=p, groups={k: {kk: v.get(kk) for kk in ("air_max", "hood_max", "hood78", "chord_at_hood_max",
                                                                                            "lip_at_hood_max_m", "hi_air", "best_score3", "n_alive")}
                                                              for k, v in m["groups"].items()}, seconds=m["seconds"])), ensure_ascii=False))
    elif a[0] == "verdict" and len(a) >= 2:
        r = verdict(a[1], opt.get("stage", "g1"), opt.get("base"))
        print(json.dumps(C.clean(dict(verdict=r["verdict"], gain_quantities=r.get("gain_quantities"), text=r.get("text"),
                                      gains={k: dict(median=v["median"], per_group=v["per_group"]) for k, v in (r.get("gains") or {}).items()},
                                      stage=r["stage"], file=os.path.abspath(a[1]).replace("\\", "/") + "/f55/reading_F55_%s.json" % r["stage"])),
                         ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
