# -*- coding: utf-8 -*-
"""FLIP49 campaign B (PER49-B, 2026-10-16): raise the incoming crest's q (= H / Hmax at the 17 m approach) by two crossing swells over the
unchanged DA3 spur, preceded by two 2D axis strips that test only the breaking stage (py -3.10 -B, numpy only for the plan/presets part).

Why (user 2026-10-16 after DA3): "the 3D wave is still not close enough to the print"; the two biggest gaps chosen by the user are
  (1) the wave body is too long and too gentle (the print is a tall steep 'mountain') and (2) the wave is not tall enough (ours 6-7.5 m;
  the print is estimated at 10-12 m from the boats, Cartwright & Nakamura 2009).
Supervisor rules kept: gravity + natural conditions only, no shaping forces, height from real physics (Q39), periodic recurrence (Q52),
  numbers with reasons and tags. User rule Q73: rounds by frozen rules, video + numbers each round, stop and ask when the same direction does
  not improve for 2 rounds.

Written new by the campaign-B implementation step (Claude). g49_pcfg.py dispatches here (cfg BS0|BS1|BX1, freezeB, precheck of plan-B cfgs);
every other g49_pcfg preset writes byte-identical cfgs (checked by Unity/Build/FLIP49/campaignB/prep/p_identity.py). Read only here:
plan_A_frozen.json, plan_frozen.json, diag_B/out/d1_summary.json (DA3 reference medians), the FLIP49 tank and run tools.

usage (through g49_pcfg.py):
  py -3.10 -B g49_pcfg.py freezeB [--force=1 --reason=...]   write plan/plan_B_frozen.json (+ .sha256); refuses to overwrite once a plan-B run exists
  py -3.10 -B g49_pcfg.py cfg BS0|BS1                         2D axis strips S0 (DA3 wave) and S1 (stand-in, H 10.7 m) -> strips/ready/
  py -3.10 -B g49_planB.py ana <strip run dir>                plan-B per-breaker numbers (after g49_periodic_ana.py all), S0 baseline / G1 gate
Round 2 (added 2026-10-16 after the user's Q77; plan/plan_B2_frozen.json; BS0/BS1/BX1 and plan B are unchanged):
  py -3.10 -B g49_pcfg.py freezeB2 [--force=1 --reason=...]  write plan/plan_B2_frozen.json (+ .sha256); refuses to overwrite once a plan-B2 run exists
  py -3.10 -B g49_pcfg.py cfg BS2|BS3                         steep-ledge axis strips S2 (= S0 with the ledge bed) and S3 (= S1 stand-in with the ledge bed)
  py -3.10 -B g49_planB.py ana2 <strip run dir>               plan-B2 numbers (after g49_periodic_ana.py all): gate G2 (S2 vs S0), S3 vs S1 report-only
Tags: [measured] FLIP records, [computed] formulas/screens, [literature], [guess], [chosen].
"""
import os, sys, json, time, math, glob, copy

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np            # noqa: E402
import g49_common as GC       # noqa: E402

PLAN_B_REL = "Unity/Build/FLIP49/plan/plan_B_frozen.json"
PLAN_B = GC.REPO + "/" + PLAN_B_REL
OUT_B = GC.B49 + "/campaignB"
REGISTRY = OUT_B + "/registry.jsonl"          # S0 baseline, S0-DA3 offset, X1 expectation: appended BEFORE the next run is read
D1_SUMMARY = GC.B49 + "/diag_B/out/d1_summary.json"
T_END_STRIP = 120.0
JUDGE_T = (45.0, 80.0)                         # 2D set-up artefact: only onsets 45-80 s (k2-k4) are judged [chosen, plan B]
H_S0 = 7.5                                     # DA3 wave [chosen in plan A]
H_S1 = 10.7                                    # stand-in: peak H of a +-29.9 deg pair of 5.35 m trains on the axis at 17 m [computed, linear]
H_T = 5.35                                     # each train of X1 [chosen: q17 about 0.92]
H_T_MAX = 5.5                                  # input cap per train [chosen]
THETA_DEG = 29.9                               # half crossing angle [chosen: 60 deg crossing (D30/Q11), 29.9 so that W fits L/(2 sin theta)]
W_X1 = 143.0                                   # half tank of X1 [computed: L_lin(17 m, 12 s)/(2 sin 29.9 deg)]
Q_SF_MAX_B = 0.95                              # plan-B precheck: H/Hmax of the Fenton table (S1 is 0.918 by design; plan A/PER49 keep 0.9)
STRIP_S_PER_MPF = 758.0 / (315612 * 2881) * 1e6   # s per million particles per frame: S1_axis_PG12s_stC (758 s, 315,612 max particles, 2881 frames) [measured]
EXPECT_PARTICLES_B = {("BS0", 0.5): None, ("BS1", 0.5): None}   # filled from count_particles at prep (see precheck: recorded, not asserted)

# print reference (STUDY52 ruler, 'cn' values and bands, as quoted in the plan-B brief) [measured on the print]
PRINT_REF = dict(back_deg_07_09=31.3, back_band=[29.0, 38.0], width07=1.32, width07_band=[1.02, 1.42], lip=0.35, hollow_ahead_eta_c=[0.04, 0.11],
                 front_foot=0.25, chord_deg=64.3, hood=0.186)


# ====================================================================== beds
def _pc():
    import g49_pcfg as PC
    return PC


def spec_B_axis():
    """S0/S1 strip bed: the DA3 bed (SC37, ch_y0 30 m) on its ridge axis y = 0, extruded laterally (k 0: sech^2(0) = 1 at every y) and without
    the side-channel term (ch_h 0). At y = 0 the DA3 channel weight is 0.5(1 + tanh((0 - 30)/4)) = 3.1e-7, so the 3D axis profile and this
    strip differ by < 1e-5 m [computed, checked in precheck_B]. Profile: flat 17 m to x 180.25, 1:10 to the 1.7 m shelf at x 333.25,
    reef top to x_back 353.25, 1:2 down to the 6 m lagoon (x 361.85), exit band 362-442."""
    sp = dict(_pc().spec_A3())
    sp = GC.pg_axis(sp)
    sp.update(ch_h=0.0)
    return sp


def is_spec_B_axis(spec):
    ref = spec_B_axis()
    for k, v in ref.items():
        w = spec.get(k)
        if v is None or w is None:
            if not (v is None and w is None):
                return False
        elif isinstance(v, bool) or isinstance(w, bool):
            if bool(v) != bool(w):
                return False
        elif abs(float(v) - float(w)) > 1e-12:
            return False
    return bool(GC.is_spur_drop(spec))


def axis_bed_checks(spec):
    """numpy checks of the strip bed (seconds)."""
    ok, o = {}, {}
    sp3 = _pc().spec_A3()
    xs = np.arange(0.0, 442.0, 0.05)
    z_ax = GC.bed_z(xs, np.zeros_like(xs), **spec)
    z_da3 = GC.bed_z(xs, np.zeros_like(xs), **sp3)
    d = float(np.abs(z_ax - z_da3).max())
    o["strip_vs_DA3_axis_max_abs_m"] = d
    ok["B_bed_equals_DA3_axis_lt_1e-5m"] = bool(d < 1e-5)
    ys = np.arange(0.0, 6.0001, 0.5)
    Z = GC.bed_z(xs[None, :], ys[:, None], **spec)
    ok["B_bed_uniform_across_strip"] = bool(np.abs(Z - Z[0:1, :]).max() == 0.0)

    def dep(x):
        return float(-GC.bed_z(np.array([x]), np.array([0.0]), **spec)[0])
    lm = dict(x180=dep(180.0), x180p25=dep(180.25), x256p75=dep(256.75), x333p25=dep(333.25), x353p25=dep(353.25), x361p85=dep(361.85), x362=dep(362.0), x440=dep(440.0))
    o["depth_landmarks_m"] = lm
    ok["B_bed_landmarks"] = bool(abs(lm["x180"] - 17.0) < 1e-9 and abs(lm["x256p75"] - 9.35) < 1e-6 and abs(lm["x333p25"] - 1.7) < 1e-6
                                 and abs(lm["x353p25"] - 1.7) < 1e-6 and abs(lm["x362"] - 6.0) < 1e-6 and abs(lm["x440"] - 6.0) < 1e-6)
    o["edge_x_m"] = GC.edge_x(spec)
    o["tags"] = dict(all="computed (numpy, g49_common.bed_z)")
    return o, ok


# ====================================================================== presets
def make_strip(qid, H, opt):
    PC = _pc()
    sp = spec_B_axis()
    stage = opt.get("stage", "C")
    if stage not in ("C", "A"):
        raise SystemExit("plan B strips use stage C (DA3's drift fix) or stage A (AM-B2: the S0 health fix)")
    if stage == "A" and not amendment("AM-B2"):
        raise SystemExit("stage A for the plan-B strips needs amendment AM-B2 in plan/amendments.jsonl")
    g = float(opt["in_gain"]) if opt.get("in_gain") else None
    if g is not None and not amendment("AM-B3"):
        raise SystemExit("an in_gain other than plan/in_gain.json for the plan-B strips needs amendment AM-B3 (S0 inlet fix) in plan/amendments.jsonl")
    rid = {"BS0": "BS0_axDA3_T12H7p5", "BS1": "BS1_axDA3_T12H10p7_standin"}[qid] + ("" if stage == "C" else "_st%s" % stage) + ("" if g is None else "_g%s" % GC.tag(g))
    lab = {"BS0": "2D control strip on the DA3 ridge axis with the DA3 wave (T 12 s, H 7.5 m, q 0.64)",
           "BS1": "STAND-IN strip (tests only the breaking stage; never shown or reported as the wave): T 12 s, H 10.7 m (q 0.92) = the axis peak of a "
                  "+-29.9 deg pair of 5.35 m trains at 17 m"}[qid]
    rec = dict(r2=True, r3_z=None, block=120, preg_every=24,
               r4=dict(x=[225.0, 362.0], z1=GC.W_STRIP, y0=-10.0, y1=16.0, clip_vox=6.0, t0=24.0),
               r5=dict(t0=24.0, every=2), windows=None)
    c = PC.make(rid, "axis_strip", 0.5, GC.W_STRIP, sp, T_END_STRIP, stage=stage, in_gain=g, H=H, layout="A", records=rec,
                case_extra=dict(queue_id={"BS0": "S0", "BS1": "S1"}[qid], label=lab, judged_onset_window_s=list(JUDGE_T), standin=(qid == "BS1")),
                note="FLIP49 campaign B %s: %s. Strip half width 6 m, particle 0.5 m, 120 s, stage C, box 442 m x zb -25 m, inlet band 0-100 m, "
                     "exit band 362-442 m (sigma 1.41) - the DA3 band/sponge/drift fix. Bed = DA3 axis (flat 17 m to 180.25, 1:10 to the 1.7 m shelf at "
                     "333.25, reef top to 353.25, 1:2 to the 6 m lagoon). Judged: onsets 45-80 s only (2D set-up artefact)." % ({"BS0": "S0", "BS1": "S1"}[qid], lab))
    c["case"].update(plan_frozen=PLAN_B_REL, plan="Unity/Build/FLIP49/plan/plan_B_frozen.json (queue, frozen_criteria, gate_G1, stop_rule, honesty)",
                     campaign="PER49-B")
    c["analysis"]["plan_frozen"] = PLAN_B_REL
    if stage == "A":
        c["case"]["amendment"] = "AM-B2 (Unity/Build/FLIP49/plan/amendments.jsonl): S0 stage C failed the volume health (4.75 % > 1 %); fix = drift stage A"
    if g is not None:
        c["case"]["amendment"] = c["case"].get("amendment", "") + " | AM-B3: in_gain %g (S0 inlet fix, 7.5/H_meas)" % g
        c["wave"]["in_gain_source"] = "AM-B3 (plan/amendments.jsonl): 7.5/H_meas of the stage-A S0"
    c["precheck"] = precheck_B(c)
    return c


def amendment(aid):
    p = GC.PLAN_DIR + "/amendments.jsonl"
    if not os.path.exists(p):
        return None
    for l in open(p, encoding="utf8"):
        if l.strip():
            e = json.loads(l)
            if e.get("id") == aid and e.get("plan") == PLAN_B_REL:
                return e
    return None


def preset_B(name, opt):
    if name == "BS0":
        return [make_strip("BS0", H_S0, opt)]
    if name == "BS1":
        return [make_strip("BS1", H_S1, opt)]
    if name == "BX1":
        raise SystemExit("BX1 (coarse 3D, two crossing trains through the FLIP50 directional inlet) is built only after gate G1 passes "
                         "(plan_B_frozen.json gate_G1). Run S0 and S1 and `g49_planB.py ana` first")
    if name in ("BS2", "BS3"):                 # round 2 (plan_B2_frozen.json, Q77): the steep-ledge strips
        return [make_strip_B2(name, opt)]
    raise SystemExit("plan B presets: BS0, BS1 (BX1 after G1); plan B2: BS2, BS3")


def precheck_B(c):
    """pre-run checks of a plan-B cfg. Strips: layout A checks of g49_pcfg.precheck_A (minus the SC37 identity, replaced by the axis-bed checks),
    Fenton table checks with the plan-B limit H/Hmax <= 0.95, inlet gain from plan/in_gain.json, plan-B naming, cost from the S1 strip rate."""
    PC = _pc()
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's rule)", wall="computed from the measured S1_axis_PG12s_stC rate"))
    ck = out["checks"]
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), float(P["dp"]), zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V))
    a = PC.precheck_A(c, P, spec, n)
    ckA = a.pop("checks_A")
    ckA.pop("A_bed_is_SC37", None)            # the strip is the DA3 axis (checked below), not SC37
    ckA.pop("A_layout_named", None)           # plan A naming (analysis.plan_frozen = plan A); replaced by the plan-B naming checks below
    ckA.pop("A_plan_frozen_named", None)
    ck.update(ckA)
    ck["B_layout_A"] = bool(c.get("layout") == "A")
    out["A"] = a.get("A")
    if c["kind"] == "axis_strip":
        ck["B_bed_is_DA3_axis_spec"] = bool(is_spec_B_axis(spec))
        o_b, k_b = axis_bed_checks(spec)
        ck.update(k_b)
        out["bed_B"] = o_b
        ck["B_strip_W6_dp0p5"] = bool(float(P["W"]) == GC.W_STRIP and float(P["dp"]) == 0.5)
        nf = int(c["f_end"])
        est = STRIP_S_PER_MPF * n * 1.45 / 1e6 * nf / 3600.0       # growth up to x1.45 (S1 strips x1.41-1.47) [measured]
        out.update(frames=nf, wall_est_h=est, wall_rate_src="S1_axis_PG12s_stC: 758 s for 2881 frames at 315,612 max particles [measured]")
        ck["B_strip_one_launch"] = bool(est * 3600.0 <= 0.9 * float(c.get("wall_limit_s", 1740)))
    sf = c.get("sf")
    if sf:
        ck["sf_depth_is_h0_17"] = bool(abs(float(sf["h"]) - float(P["h0"])) < 1e-9 and abs(float(sf["h"]) - 17.0) < 1e-9)
        ck["sf_terms"] = bool(len(sf["E"]) == len(sf["B"]) + 1 and len(sf["B"]) == GC.SF_N)
        ck["sf_below_0p95_Hmax_planB"] = bool(float(sf["H_over_Hmax"]) <= Q_SF_MAX_B)
        H_design = {"S0": H_S0, "S1": H_S1}.get((c.get("case") or {}).get("queue_id"))
        if H_design is not None:
            ck["sf_H_is_design"] = bool(abs(float(sf["H"]) - H_design) < 1e-9)
        out["sf_q"] = float(sf["H_over_Hmax"]); out["sf_Hmax_fit_m"] = float(sf["Hmax_fit"]); out["sf_eta_crest_m"] = float(sf["eta_crest"])
    gx_ = [float(v) for v in (c.get("gauges") or {}).get("x", GC.GAUGE_X)]
    ck["band_layout"] = bool(float(P["xg_end"]) < min(gx_) and (float(P["vol_x0"]) >= float(P["xg_end"]) or float(P["vol_x1"]) >= float(P["Lx"]) - 1e-9)
                             and (float(P["vol_x1"]) <= float(P["xa0"]) or float(P["vol_x0"]) <= 0.0) and max(gx_) <= float(P["vol_x1"]))
    ck["bed_above_box_floor"] = bool(c["bed"].get("max_depth_m", 17.0) <= -float(P["zb"]) + 1e-6)
    src_g = str((c.get("wave") or {}).get("in_gain_source"))
    ck["in_gain_set"] = bool("plan/in_gain.json" in src_g or ("AM-B3" in src_g and amendment("AM-B3") is not None))
    st = (c.get("drift") or {}).get("stage")
    if st == "C":
        ck["stage_C_as_DA3"] = bool(float(P["duabs_on"]) == 1.0 and float(P["volcorr_on"]) == 0.0)
    else:
        ck["stage_A_by_AM_B2"] = bool(st == "A" and amendment("AM-B2") is not None and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0
                                      and float(P["hold_on"]) == 0.0 and abs(float(P["vol_x0"]) - 110.0) < 1e-9 and abs(float(P["vol_x1"]) - 357.0) < 1e-9)
    ck["B_plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == PLAN_B_REL and (c.get("analysis") or {}).get("plan_frozen") == PLAN_B_REL)
    if (c.get("case") or {}).get("queue_id") == "S1":
        ck["B_S1_labelled_standin"] = bool((c.get("case") or {}).get("standin") is True and "STAND-IN" in str((c.get("case") or {}).get("label")))
    ck["B_plan_frozen_exists"] = bool(os.path.exists(PLAN_B) and os.path.exists(PLAN_B + ".sha256"))
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "fails: " + ", ".join(k for k, v in ck.items() if not v)
    return out


# ====================================================================== linear numbers used by the plan (computed here, recorded in the plan)
def k_lin(T, h):
    om = 2 * math.pi / T
    k = max(om * om / GC.G, om / math.sqrt(GC.G * h))
    for _ in range(100):
        th = math.tanh(k * h)
        dk = (GC.G * k * th - om * om) / (GC.G * th + GC.G * k * h * (1 - th * th))
        k -= dk
        if abs(dk) < 1e-14 * k:
            break
    return k


def linear_numbers():
    T = 12.0; h = 17.0
    k = k_lin(T, h); L = 2 * math.pi / k
    th = math.radians(THETA_DEG)
    W_fit = L / (2 * math.sin(th))
    lam_x = L / math.cos(th)
    E_ratio = 2 * H_T ** 2 / H_S0 ** 2
    F_ratio = 2 * H_T ** 2 * math.cos(th) / H_S0 ** 2
    E_ratio55 = 2 * H_T_MAX ** 2 / H_S0 ** 2
    F_ratio55 = 2 * H_T_MAX ** 2 * math.cos(th) / H_S0 ** 2
    _, tb = GC.sf_solve(h, T, H_S1, GC.SF_N)
    _, tb0 = GC.sf_solve(h, T, H_S0, GC.SF_N)
    _, tbt = GC.sf_solve(h, T, H_T, GC.SF_N)
    return dict(T_s=T, h_m=h, L_lin_m=L, k_lin=k, theta_deg=THETA_DEG, W_fit_m=W_fit, W_chosen_m=W_X1, lambda_x_m=lam_x,
                energy_ratio_vs_DA3=E_ratio, onshore_flux_ratio_vs_DA3=F_ratio, energy_ratio_Ht5p5=E_ratio55, onshore_flux_ratio_Ht5p5=F_ratio55,
                axis_peak_H_linear_m=2 * H_T, Hmax_fit_17m_T12_m=float(tb["Hmax_fit"]), q_S0=float(tb0["H_over_Hmax"]), q_S1=float(tb["H_over_Hmax"]),
                fenton_crest_S0_m=float(tb0["eta_crest"]), fenton_crest_S1_m=float(tb["eta_crest"]), fenton_crest_train_m=float(tbt["eta_crest"]),
                tags=dict(all="computed (linear dispersion; Fenton stream function g47_sfwave N 40 for crests and Hmax)"))


def da3_reference():
    """DA3 medians over k2-k9 from diag_B/out/d1_summary.json [measured, D1]."""
    rows = [r for r in json.load(open(D1_SUMMARY, encoding="utf8")) if r["run"] == "DA3"]

    def med(k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return float(np.median(v)) if v else None
    return dict(source="Unity/Build/FLIP49/diag_B/out/d1_summary.json", sha256_16=GC.sha256_file(D1_SUMMARY)[:16], n=len(rows), ks=[r["k"] for r in rows],
                back_on_deg=med("back_on"), back_best_deg=med("back_best"), back_pre_max_deg=med("back_pre_max"), back_inc_deg=med("inc_back"),
                width07_best=med("w07_best"), width07_on=med("w07_on"), Hc_m=med("Hc"), h_b_m=med("h_b"), H_front_m=med("Hf"), H_rear_m=med("Hr"),
                gain_c0_over_cin=med("gain"),
                brief_quoted=dict(back_on=8.2, back_best=8.15, width07_best=3.58, Hc=6.46,
                                  note="the brief quoted 8.15 deg for the best-frame back; the median recomputed from d1_summary.json is used (tag measured)"),
                tag="measured (FLIP DA3 + STUDY52 ruler, diag_B d1_measure/d1_summary)")


# ====================================================================== the frozen plan
def plan_B():
    PC = _pc()
    pA = json.load(open(GC.REPO + "/Unity/Build/FLIP49/plan/plan_A_frozen.json", encoding="utf8"))
    cA = pA["criteria"]
    lin = linear_numbers()
    ref = da3_reference()
    s0 = preset_B("BS0", {})[0]; s1 = preset_B("BS1", {})[0]
    crit = dict(
        source="P1-P5, PERIODIC, health and best-frame rule copied unchanged from plan_A_frozen.json (SHA %s...); nothing loosened. "
               "Plan-B additions below (added_targets, gains, verdict_wording, input_cap, compute)." % GC.sha256_file(GC.REPO + "/Unity/Build/FLIP49/plan/plan_A_frozen.json")[:16],
        targets48=cA["targets48"],
        definitions=dict(cA["definitions"], judged_breaker_3d="centre (y 0.5 m row) onset t >= 45 s (unchanged)",
                         judged_breaker_strip="centre onset 45 s <= t <= 80 s (k2-k4 by the event rule); later onsets report-only with the offshore mean level shown "
                                              "(2D set-up artefact: water that crosses the reef cannot return sideways in a strip, FLIP49 S1)",
                         Hc="centre crest above the still level at onset (ana.json onset.eta_c; unchanged)",
                         back_angle="centre section, STUDY52 ruler (s52_shape.measure_mask back_angle_07_09_deg on the g46 r2 mask): angle of the rear face between "
                                    "0.7 and 0.9 eta_c. Reported at: the incoming crest (median of the hf-track back_deg_07_09 while the crest is over depth >= 16.5 m), "
                                    "the pre-onset maximum (ruler frames onset - 3 s .. onset), onset (ruler frame nearest onset) and the score3 best frame",
                         width07="width07_silhouette of the STUDY52 ruler at the score3 best frame (onset reported), in eta_c",
                         lip="P5 lip: lip_thick_mid / eta_c, maximum over the shape window (onset to touchdown), as P5",
                         h_b="still-water depth under the centre crest at onset (ana.json onset.hB)",
                         crest_to_trough="H_front = crest - front trough, H_rear = crest - rear trough, on the y 0.5 m top surface at onset (diag_B d1_measure.profile_stats rule)",
                         realized_q="measured mean H of the centre gauges x 128 and 160 m (y 0.5 m) / Hmax(17 m, 12 s) = %.3f m (Fenton fit)" % lin["Hmax_fit_17m_T12_m"],
                         breaking_x_lt_180="an onset by the frozen event rule (g46 centre_events: thmax >= 90 deg, crest >= 1 m) at x < 180 m, scanned over x 5-180 m "
                                           "in the judged periods"),
        per_breaker=cA["per_breaker"],
        periodic_A=cA["periodic_A"],
        report_only=cA["report_only"],
        health=dict(cA["health"], wall_max_h_per_coarse_3d_run=4.5,
                    wall_rule="<= 4.5 h per coarse 3D run for X1/X2 (raised before launch from the frozen 2.5 h - 3.0 h in AM-A3/A5 - because the wall-fit forces W 143), "
                              "launched in chunks of <= 29 min",
                    strip_health_S0="measured inlet H at x 110-160 m (centre gauges) within 5 % of 7.5 m; no breaking at x < 180 m; volume drift < 1 % (stage C interior "
                                    "period mean). Any failure: fix the preset and rerun S0 (not a round)",
                    strip_health_S1="volume drift < 1 % and no bed leak; inlet H and realized q reported (breaking at x < 180 m is handled by G1 (a))"),
        best_frame_rule=cA["best_frame_rule"],
        layout_moves_X1=dict(
            P4a_side_band="|y| 128-142 m, x <= 357 (the 14 m next to the far wall; at W 85 it was |y| 70-84, the same rule; both in the 25 m channel). "
                          "Compares the centre with the far-wall crossing peak of the same wave (the stricter choice)",
            crest_window="xc0 +- lambda_x/2, lambda_x = L/cos(theta) = %.1f m (was L/2 = 74.3 m), so the far-wall crest of the same pattern lies inside" % lin["lambda_x_m"],
            node_line="|y| 70-84 m is a node line of the crossing pattern: reported, never judged",
            strips="P2-P4 do not apply in the 2D strips; P1, P5 and the new items do"),
        added_targets=dict(back_best_deg_min=25.0, width07_best_max=1.6, Hc_min_m=9.0,
                           rule="judged on the median over judged breakers, never on best frames alone; onset and pre-onset maximum back reported alongside"),
        gains_reported=["Hc / axis incoming crest at x 160 m", "Hc / each train's Fenton crest (%.2f m)" % lin["fenton_crest_train_m"],
                        "Hc / DA3's measured incoming crest (4.75 m)", "crest-to-front-trough H / axis incoming H at x 160 m",
                        "crest-to-front-trough and crest-to-rear-trough heights (Cartwright & Nakamura comparison)", "measured realized q at 17 m"],
        verdict_wording=dict(full_print_shape="PERIODIC + P1-P5 on >= 3 consecutive breakers + all three added targets on their medians",
                             periodic_narrow_peak="PERIODIC + P1-P4", partial="otherwise, breaker by breaker",
                             self_assessment="all scores are AI self-assessment; the user judges print-likeness"),
        input_cap=dict(H_t_max_m=H_T_MAX, onshore_energy_flux="<= DA3's", total_energy_max_rel=0.076,
                       values_computed=dict(H_t5p35=dict(E=lin["energy_ratio_vs_DA3"], F=lin["onshore_flux_ratio_vs_DA3"]),
                                            H_t5p5=dict(E=lin["energy_ratio_Ht5p5"], F=lin["onshore_flux_ratio_Ht5p5"]))),
        compute=dict(wall_cap_h_X1_X2=4.5, launch_max_min=29, one_simulation_at_a_time=True),
        deliverables="each round: g49_video2 compare mp4 (red frame at the best frame, print outline) plus tagged numbers, sent without waiting (Q73)",
        print_reference=PRINT_REF,
        DA3_reference=ref,
    )
    gate = dict(
        name="G1", frozen=True, judged_on="k2-k4 medians (onsets 45-80 s) of S1 against S0",
        a="if breaking starts at x < 180 m (in the band or on the flat) in >= 2 judged periods: X1 uses H_t 5.0 m (q17 about 0.86) instead of 5.35 m, and the shape gate "
          "(b) is read on the S1 breakers that reach the slope; if fewer than 2 reach the slope, stop and ask",
        b_pass=dict(all_of=["back at onset S1 - S0 >= +5 deg", "h_b S1 - S0 >= +1.5 m (a deeper break: the height mechanism)",
                            "lip >= 0.2 eta_c on >= 2 of k2-k4 (plunging, not spilling)"],
                    then="build and run X1; before launching X1 register its expected back = S1's value minus the S0-DA3 offset"),
        c_fail="anything in (b) missing: FLIP does not confirm that a near-limiting incoming crest steepens the back and deepens the break on this axis. Do not port the "
               "inlet and do not run X1. Stop and ask the user, listing: an S1 strip at 0.25 m particles (resolution check), a steep-ledge axis strip (1:10 from 17 to "
               "13 m, then 1:3), X1 for height only, or keeping DA3",
        s0_baseline="S0 medians over k2-k4 recorded as the 2D baseline and the 2D-to-3D offset (S0 minus DA3's medians: onset back, best-frame back, best-frame width07, Hc) "
                    "appended to campaignB/registry.jsonl before S1 is read")
    stop = dict(
        q73=dict(direction="raise the incoming crest's q at the 17 m approach by crossing swells", rounds=["S1 vs S0", "X1 vs DA3", "X2 vs X1"],
                 improvement_any=["median best-frame back angle >= +3 deg", "median best-frame width07 <= -0.3 eta_c", "median Hc >= +0.7 m"],
                 nothing_worse_than=dict(back_deg=-2.0, width07=0.2, Hc_m=-0.5, note="ruler noise at 0.5 m particles"),
                 rule="two consecutive rounds without improvement means stop",
                 single_round_stop=["G1 fails", "X1 does not improve on DA3"]),
        hard_stops=["a vertical jet instead of a forward lip on >= 2 judged breakers", "main gaps improved but P4a < 1.5 on >= 2 judged breakers (verdict partial, show the user)",
                    "fewer than 2 S1 breakers reach the slope", "the FLIP50 two-component inlet cannot pass its T0 checks and smoke within about one working day",
                    "a health failure that cannot be diagnosed"],
        campaign_end="after X2 or after 4 runs, whichever first: stop and show all videos and numbers",
        always=["never exceed the input cap (H_t <= 5.5 m, onshore energy flux <= DA3's)", "never change two things in one run", "never loosen a frozen threshold after seeing a result"],
        height_definition="open (Hc vs crest-to-trough); goes to the user with the first report; does not block S0/S1")
    queue = [
        dict(id="S0", preset="BS0", run_id=s0["run_id"], what="2D control strip on the DA3 ridge axis, DA3 Fenton wave T 12 s H 7.5 m (q %.2f), particle 0.5 m, 120 s, stage C" % lin["q_S0"],
             est_minutes=45,
             expected="[computed/guess] ~12 s recurrence; onset x 255-276 m, h_b 7.4-9.5 m, Hc 5.4-7.0 m, crest-to-front-trough 8.5-10.5 m; back at onset 9-16 deg, best frame 8-16 deg; "
                      "width07 2.0-3.0 eta_c; lip 0.3-0.5",
             decision_after="health first (strip_health_S0); otherwise no gate: register the S0 baseline and the S0-DA3 offset, then go straight to S1"),
        dict(id="S1", preset="BS1", run_id=s1["run_id"], what="as S0 with one change: Fenton T 12 s, H 10.7 m (q %.3f). STAND-IN testing only the breaking stage" % lin["q_S1"],
             est_minutes=15,
             expected="[computed/guess] intact on the flat; onset x 245-255 m, h_b 9.7-10.9 m, Hc 7.8-9.3 m; back at the incoming crest 21-23 deg, pre-onset max 22-28, onset 17-25, "
                      "best frame 15-23 deg; width07 at onset 1.7-2.4; plunging with lip >= 0.2 likely but not certain",
             decision_after="gate G1"),
        dict(id="X1", what="coarse 3D: DA3/SC37y30 bed unchanged for |y| <= 85 m, its 25 m side channel continued to a far wall at y = %.0f m; two linear regular trains T 12 s, "
                           "+-%.1f deg, H_t from G1 (5.35 m default) through the FLIP50 directional inlet (2 components, no side band) in the FLIP49 band; stage C, exit sponge, "
                           "particle 0.5 m, 92 s, ~9.8 M particles, ~4.2 h in 9-10 launches of <= 29 min, ~13 GB peak. Before X1 (not runs): T0 checks (numpy target = VEX target, "
                           "no flow through the walls at y 0/143, zero net mass flux) and a <= 10 min smoke at 1.0 m (axis H = 2 H_t +- 6 %% at x 110-160 m, far-wall H within 10 %% "
                           "of the axis)" % (W_X1, THETA_DEG),
             est_minutes=255,
             expected="[computed with the DA3-calibrated break model (f 0.3) + guess] breaks every 12 s at onset x ~227-245 m, h_b 10.8-12.3 m; Hc 9.2 m (8.4-10.6); crest-to-trough "
                      "at onset ~13-14 m; gain over the axis incoming crest at x 160 m 1.3-1.6, over each train's Fenton crest 2.5-2.9, over DA3's incoming crest 1.8-2.1; back at "
                      "onset and best frame 18-25 deg; width07 1.7-2.4; c0/c_side vs the far-wall band 1.3-1.7; curl width 1.6-2.2 Hc. Likely verdict: partial",
             decision_after=["(1) health failure (volume, leak, reef-top set-up > 3 m): diagnose first",
                             "(2) upward vertical jet instead of a forward lip at the centre on >= 2 judged breakers (P5 lip < 0.2 with a rising jet): no X2, stop and ask",
                             "(3) breaking at x < 180 m in >= 2 judged periods: X2 = H_t - 0.35 m",
                             "(4) everything passes (PERIODIC + P1-P5 on >= 3 consecutive breakers + medians back >= 25 deg, width07 <= 1.6, Hc >= 9 m): X2 = +48 s continuation to 140 s, then stop and report",
                             "(5) no Q73 improvement over DA3: stop and ask",
                             "(6) improved over DA3 but P4a < 1.5 (far-wall band) on >= 2 judged breakers: verdict partial, stop and show the user",
                             "(7) improved, P4a passes, but back < 25, width07 > 1.6 or Hc < 9 m: if the measured axis H at x 160 m < 0.95 x design, X2 = inlet gain calibration to the "
                             "design value (not an enlargement); otherwise X2 = H_t 5.5 m (q17 0.94), the last step the input cap allows (+3 % per train; total energy +7.6 % over DA3; onshore flux -7 %)"]),
        dict(id="X2", what="the one change chosen by X1's frozen rule (+48 s continuation, H_t - 0.35 m, inlet gain calibration, or H_t 5.5 m); everything else identical; "
                           "never two changes, never H_t > 5.5 m", est_minutes=255,
             expected="continuation: same breaker to 140 s within +-10 m and +-10 % Hc; H_t 5.0: Hc ~8.3 m (7.5-9.5), back 16-22 deg, h_b ~10.3 m; H_t 5.5: Hc ~9.7 m (8.9-11.2), "
                      "onset back 20-27 deg, width07 1.6-2.2 [computed/guess]",
             decision_after="campaign end whatever the outcome: show all four runs (mp4 + numbers), verdict in plan A's wording, Q73 test X2 vs X1, ask the height-definition question"),
    ]
    honesty = dict(
        height_sources_X1=["(a) linear superposition of two smaller swells (each 5.35 m < DA3's 7.5 m) adds to ~2 H_t = 10.7 m on the axis; a property of the chosen sea, already at "
                           "the inlet; not seabed focusing. Energy +%.1f %%, onshore flux %.1f %% vs DA3 [computed, linear]" % (100 * (lin["energy_ratio_vs_DA3"] - 1), 100 * (lin["onshore_flux_ratio_vs_DA3"] - 1)),
                           "(b) shoaling + refraction over the unchanged spur: x1.1-1.3 [computed]; FLIP measures Hc / axis incoming crest at x 160 m",
                           "(c) a deeper break: a near-limiting crest breaks at h_b ~11-12 m instead of 8-8.5 m, Hc ~0.8 h_b [measured rule from D1 + Goda]"],
        natural_basis="crossing seas are the accepted linear explanation of field rogue waves (Draupner; McAllister et al. 2019 needed 60-120 deg) [literature]; 60 deg is the "
                      "angle the user chose earlier (D30/Q11); in Q39 the supervisor asked about two waves gathering at one point",
        idealisations=["two swells exactly phase-locked at the same period for 92-140 s (in nature the lattice drifts and recurrence follows the beat)",
                       "the walled half tank stands for an infinite row of spurs %.0f m apart, with crossing peaks over the channels at y = %.0f m" % (2 * W_X1, W_X1)],
        standin="S1 is a single 10.7 m long-crested wave = an enlarged input; used only to test the breaking stage, labelled stand-in, never shown or reported as the wave",
        height_definition="open: C&N's 10-12 m is crest-to-trough; measured that way DA3 is already 10.0-11.7 m [measured, D1]; Hc >= 9 m kept as given; both reported",
        expectations=["every X1/X2 number is computed screening or a guess; no campaign-B FLIP run existed at freeze",
                      "break model (f 0.3, Hc ~0.8 h_b) calibrated on DA3 and P1c only: Hc +-1.2 m",
                      "U3 overpredicts crests ~1.2-1.3x and its crest shapes contradict FLIP; shape predictions rest on the steady-Fenton q rule and the P1c analogue",
                      "most likely outcome partial; Hc near 9 m roughly even odds; back closes about half the gap (10 -> 18-25 deg); back >= 25 deg at the best frame not expected "
                      "(every FLIP best-frame back so far <= onset/pre-onset values; P1c inlet q ~0.82: 6-17 deg) [measured]; width07 <= 1.6 unlikely; P4a vs far wall 1.3-1.7",
                      "resolution: at 0.5 m particles the 0.7-0.9 eta_c band spans 2-3 cells; FLIP reads the incoming crest ~2 deg flatter than Fenton; 0.25 m is outside this queue",
                      "linear inlet: no bound second-order terms; free harmonics may shift Hc by ~+-0.7 m; the gauge crest share is reported",
                      "the FLIP50 directional inlet has never been run"],
        chosen=["crossing as the mechanism", "T 12 s", "delta theta 60 deg (+-%.1f)" % THETA_DEG, "H_t 5.35 m (q17 ~0.92; 5.0 or 5.5 only by frozen rules)",
                "W %.0f m (forced by the wall fit)" % W_X1, "the DA3 bed unchanged", "the stand-in wave H 10.7 m", "strip judged window 45-80 s", "side band and window layout moves",
                "the 4.5 h cap", "all gate thresholds", "strip bed without the side-channel term (ch_h 0; < 1e-5 m from the DA3 axis)",
                "plan-B precheck limit H/Hmax <= 0.95 for the Fenton table (S1 0.918; PER49/plan A keep 0.9)"],
        computed_by_FLIP="break location, time, height, shape, narrowness, recurrence and all gains",
        not_queued=["focused sets: no height gain in this tank (linear 0.93-1.09; U3 -8 % to 0 %)", "steeper swell: +1.3 deg at T 10; T 8 not a realistic regular sea",
                    "seabed lens moved offshore: transfer lengths 229-429 m exceed the tank", "opposing current: q only +0.05-0.10 and new boundaries"],
        tags="screening numbers are computed, not FLIP")
    P = dict(
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_pcfg.py freezeB (g49_planB.py)", canonical_path=PLAN_B_REL, campaign="PER49-B",
        parent_plans=dict(plan_A=dict(path="Unity/Build/FLIP49/plan/plan_A_frozen.json", sha256=GC.sha256_file(GC.REPO + "/Unity/Build/FLIP49/plan/plan_A_frozen.json")),
                          plan_PER49=dict(path="Unity/Build/FLIP49/plan/plan_frozen.json", sha256=GC.sha256_file(GC.PLAN_FROZEN)), note="read only, not edited"),
        user_20261016=dict(request="等一下我觉得现在最主要的问题是3D模拟依然不够贴近原画",
                           gaps_chosen=["(1) the wave body is too long and too gentle (the print is a tall steep 'mountain')",
                                        "(2) the wave is not tall enough (ours 6-7.5 m; the print ~10-12 m from the boats, Cartwright & Nakamura 2009)"]),
        supervisor_rules=["only gravity + natural conditions (seabed, incoming waves, realistic wind/current with a real cause and realistic size); no forces toward a shape",
                          "the wave must become tall by real physics, not by enlarging the input or exaggeration (Q39)", "periodic recurrence (Q52)",
                          "numbers with reasons and tags; chosen vs computed stated"],
        user_rule_Q73="rounds by frozen rules, video + numbers each round, stop and ask if the same direction does not improve for 2 rounds",
        design=dict(linear_numbers=lin, strip_bed=dict(spec=GC.bed_record(spec_B_axis()), formula=GC.bed_formula(spec_B_axis())),
                    strips=dict(S0=dict(run_id=s0["run_id"], particles_model=s0["precheck"]["particles_model"], sf_q=s0["precheck"].get("sf_q")),
                                S1=dict(run_id=s1["run_id"], particles_model=s1["precheck"]["particles_model"], sf_q=s1["precheck"].get("sf_q"),
                                        fenton_crest_m=s1["precheck"].get("sf_eta_crest_m"))),
                    same_as_DA3="inlet band 0-100 m (u relaxed toward the Fenton target, in_gain 1.0 from plan/in_gain.json), exit band 362-442 m sigma 1.41, stage C drift fix, "
                                "box 442 m x zb -25 m, particle 0.5 m, gauges x 110/128/160 m"),
        frozen_criteria=crit, gate_G1=gate, stop_rule=stop, queue=queue, honesty=honesty,
        ranking_reasons=dict(P3_crossing=7, P2_steeper_swell=2.5, P1_focused_sets=2, note="scores and reasons from the campaign-B design step (computed/guess)"),
        implementation=dict(tools=["Tools/GWWaveGen/flip49/g49_planB.py", "Tools/GWWaveGen/flip49/g49_pcfg.py", "Tools/GWWaveGen/flip49/g49_periodic_ana.py",
                                   "Tools/GWWaveGen/flip49/g49_video2.py", "Tools/GWWaveGen/flip49/g49_chain.py", "Tools/GWWaveGen/flip49/g49_run.py"],
                            module_sha256_16=dict(GC.module_shas(), **{"flip49/g49_planB.py": GC.sha256_file(os.path.abspath(__file__))[:16],
                                                                       "flip49/g49_video2.py": GC.sha256_file(os.path.join(_HERE, "g49_video2.py"))[:16]}),
                            hip=GC.HIP.replace(GC.REPO + "/", ""), hip_sha256=GC.sha256_file(GC.HIP),
                            analysis="g49_periodic_ana.py all (unchanged) + g49_planB.py ana (plan-B items, S0 baseline, G1)"),
    )
    return P


def freeze_B(force=False, reason=None):
    os.makedirs(os.path.dirname(PLAN_B), exist_ok=True)
    if os.path.exists(PLAN_B) and not force:
        return PLAN_B, "exists (not changed)"
    if os.path.exists(PLAN_B) and force:
        runs = [p for p in glob.glob(os.path.join(GC.B49, "*", "*", "cfg.json"))
                if (json.load(open(p, encoding="utf8")).get("case") or {}).get("plan_frozen") == PLAN_B_REL
                and glob.glob(os.path.join(os.path.dirname(p), "run_c*.json"))]
        if runs:
            raise SystemExit("a plan-B run exists (%s); the plan is not refrozen" % runs[0])
        if not reason:
            raise SystemExit("refreezing before any run needs --reason")
    d = plan_B()
    if os.path.exists(PLAN_B) and force:
        old = json.load(open(PLAN_B, encoding="utf8"))
        d["refrozen_history"] = list(old.get("refrozen_history") or []) + [dict(frozen_at=old.get("frozen_at"), sha256=GC.sha256_file(PLAN_B), reason=reason)]
    s = json.dumps(d, indent=1, ensure_ascii=False)
    open(PLAN_B, "w", encoding="utf8", newline="\n").write(s)
    h = GC.sha256_file(PLAN_B)
    open(PLAN_B + ".sha256", "w", newline="\n").write(h + "  plan_B_frozen.json\n")
    return PLAN_B, "new %s" % h[:16]


# ====================================================================== round 2: plan B2 (2026-10-16, user Q77) - the steep-ledge axis strips S2/S3
# Q77 (user, 2026-10-16, AskUserQuestion): (a) height is compared crest-to-trough (Cartwright & Nakamura's 10-12 m): the plan-B height target
# Hc >= 9 m becomes crest-to-front-trough >= 10 m (Hc reported); (b) round 2 = the frozen option 'a steep-ledge axis strip (1:10 from 17 to
# 13 m, then 1:3)'; focus on the back angle and width07. S2 = S0 with only the bed changed, S3 = S1 (stand-in) with only the bed changed.
# Everything above (plan B, BS0/BS1/BX1, precheck_B) is unchanged; plan_B_frozen.json is read, never edited.
PLAN_B2_REL = "Unity/Build/FLIP49/plan/plan_B2_frozen.json"
PLAN_B2 = GC.REPO + "/" + PLAN_B2_REL
LEDGE_HL = 13.0                    # ledge foot: 1:10 from 17 m down to 13 m [chosen: the user's Q77 option]
LEDGE_S2 = 3.0                     # ledge face 1:3 down to the shelf [chosen: the user's Q77 option]
LEDGE_SHELF_LEN = 20.0             # shelf (reef top) length at 1.7 m, then 1:2 to the 6 m lagoon = S0's reef-top element [chosen: same as S0]
SCREEN_B2_DIR = OUT_B + "/screen_B2/out"
B2_QID = {"BS2": "S2", "BS3": "S3"}
B2_RID = {"BS2": "BS2_axLedge13s3_T12H7p5", "BS3": "BS3_axLedge13s3_T12H10p7_standin"}
B2_PARENT = {"S2": "BS0", "S3": "BS1"}
B2_BASE_ANA = {"S2": GC.B49 + "/strips/BS0_axDA3_T12H7p5/pana/planB_ana.json",              # round-1 medians the S2/S3 numbers are read against
               "S3": GC.B49 + "/strips/BS1_axDA3_T12H10p7_standin/pana/planB_ana.json"}
B2_ALLOWED_DIFF = dict(top={"run_id", "case", "note", "bed", "parms", "precheck", "analysis", "shore_x"},
                       parms={"pg_hL", "pg_s2", "lag_xb"},
                       bed={"pg_hL", "pg_s2", "x_back", "kind", "formula", "x_edge_axis_m", "x_foot_axis_m"},
                       analysis={"plan_frozen"})


def ledge_geometry():
    """x of the ledge landmarks on the strip axis [computed from the chosen numbers]."""
    sp = spec_B_axis()
    x_foot = sp["x_toe"] + (sp["h0"] - LEDGE_HL) * sp["s"]
    x_top = x_foot + (LEDGE_HL - sp["shelf_h"]) * LEDGE_S2
    x_back = x_top + LEDGE_SHELF_LEN
    x_lag = x_back + (sp["h_lag"] - sp["shelf_h"]) * sp["s_back"]
    r = lambda v: round(float(v), 6)
    return dict(x_toe_m=r(sp["x_toe"]), x_foot_13m=r(x_foot), x_top_1p7m=r(x_top), x_back_m=r(x_back), x_lagoon_6m=r(x_lag),
                lagoon_len_to_exit_band_m=r(GC.LAYOUTS["A"]["ex_x0"] - x_lag), face_len_m=r(x_top - x_foot), exit_band_m=[GC.LAYOUTS["A"]["ex_x0"], 442.0],
                S0_landmarks=dict(x_shelf_1p7m=333.25, x_back_m=353.25, x_lagoon_6m=361.85, lagoon_len_to_exit_band_m=0.15),
                tag="computed")


def spec_B2_ledge():
    """S2/S3 strip bed: spec_B_axis (S0/S1) with the axis rise replaced by the two-slope rise that the scene already has (pg_hL, pg_s2: the
    PG12s path of g49_common.bed_z and the VEX bedgrad_pg): flat 17 m to x 180.25, 1:10 to 13 m at x 220.25, 1:3 to the 1.7 m shelf at
    x 254.15, shelf 20 m to x_back 274.15, 1:2 to the 6 m lagoon at x 282.75, 6 m to the exit band 362-442 m (as S0)."""
    sp = spec_B_axis()
    sp.update(pg_hL=LEDGE_HL, pg_s2=LEDGE_S2, x_back=ledge_geometry()["x_back_m"])
    return sp


def _same_spec(spec, ref):
    for k, v in ref.items():
        w = spec.get(k)
        if v is None or w is None:
            if not (v is None and w is None):
                return False
        elif isinstance(v, bool) or isinstance(w, bool):
            if bool(v) != bool(w):
                return False
        elif abs(float(v) - float(w)) > 1e-12:
            return False
    return True


def ledge_bed_checks(spec):
    """numpy checks of the S2/S3 bed (seconds)."""
    ok, o = {}, {}
    g = ledge_geometry()
    s0 = spec_B_axis()
    xs = np.arange(0.0, 442.0, 0.05)
    z = GC.bed_z(xs, np.zeros_like(xs), **spec)
    z0 = GC.bed_z(xs, np.zeros_like(xs), **s0)
    up = xs <= g["x_foot_13m"] + 1e-9
    d_up = float(np.abs(z[up] - z0[up]).max())
    o["upstream_of_foot_vs_S0_max_abs_m"] = d_up
    ok["B2_bed_upstream_of_foot_equals_S0"] = bool(d_up < 1e-9)
    ys = np.arange(0.0, 6.0001, 0.5)
    Z = GC.bed_z(xs[None, :], ys[:, None], **spec)
    ok["B2_bed_uniform_across_strip"] = bool(np.abs(Z - Z[0:1, :]).max() == 0.0)

    def dep(x):
        return float(-GC.bed_z(np.array([x]), np.array([0.0]), **spec)[0])
    xf, xt, xb, xl = g["x_foot_13m"], g["x_top_1p7m"], g["x_back_m"], g["x_lagoon_6m"]
    lm = dict(x180=dep(180.0), x_foot=dep(xf), x_mid_face=dep(0.5 * (xf + xt)), x_top=dep(xt), x_back=dep(xb), x_lagoon=dep(xl), x362=dep(362.0), x440=dep(440.0))
    o["depth_landmarks_m"] = lm
    ok["B2_bed_landmarks"] = bool(abs(lm["x180"] - 17.0) < 1e-9 and abs(lm["x_foot"] - 13.0) < 1e-6 and abs(lm["x_mid_face"] - 7.35) < 1e-6
                                  and abs(lm["x_top"] - 1.7) < 1e-6 and abs(lm["x_back"] - 1.7) < 1e-6 and abs(lm["x_lagoon"] - 6.0) < 1e-6
                                  and abs(lm["x362"] - 6.0) < 1e-6 and abs(lm["x440"] - 6.0) < 1e-6)
    sl = (dep(xf + 1.0) - dep(xt - 1.0)) / ((xt - 1.0) - (xf + 1.0))
    o["face_slope"] = sl
    ok["B2_face_is_1_to_3"] = bool(abs(sl - 1.0 / LEDGE_S2) < 1e-9)
    sl10 = (dep(181.0) - dep(219.0)) / 38.0
    ok["B2_approach_is_1_to_10"] = bool(abs(sl10 - 0.1) < 1e-9)
    e = GC.edge_x(spec)
    o["edge_x_m"] = e                                   # rule: first x with depth <= shelf + 0.05 m (0.15 m before the top on a 1:3 face)
    ok["B2_edge_at_ledge_top"] = bool(abs(e - (xt - 0.05 * LEDGE_S2)) < 0.06)
    o["foot_x_m"] = GC.foot_x(spec)
    ok["B2_foot_x"] = bool(o["foot_x_m"] is not None and abs(o["foot_x_m"] - xf) < 1e-9)
    ok["B2_bed_depth_range"] = bool(abs(float(-z.min()) - 17.0) < 1e-9 and abs(float(-z.max()) - 1.7) < 1e-9)
    o["tags"] = dict(all="computed (numpy, g49_common.bed_z)")
    return o, ok


def make_strip_B2(name, opt):
    PC = _pc()
    if opt.get("stage", "C") != "C" or opt.get("in_gain"):
        raise SystemExit("plan B2 strips are S0/S1 with one change (the bed): stage C and in_gain from plan/in_gain.json only")
    qid = B2_QID[name]
    H = {"S2": H_S0, "S3": H_S1}[qid]
    g = ledge_geometry()
    sp = spec_B2_ledge()
    rid = B2_RID[name]
    lab = {"S2": "2D steep-ledge strip on the DA3 ridge axis (1:10 17 -> 13 m, then 1:3 to the 1.7 m shelf) with the DA3 wave (T 12 s, H 7.5 m, q 0.64)",
           "S3": "STAND-IN strip (tests only the breaking stage; never shown or reported as the wave): T 12 s, H 10.7 m on the steep-ledge axis bed "
                 "(= S1 with the ledge bed)"}[qid]
    rec = dict(r2=True, r3_z=None, block=120, preg_every=24,
               r4=dict(x=[225.0, 362.0], z1=GC.W_STRIP, y0=-10.0, y1=16.0, clip_vox=6.0, t0=24.0),
               r5=dict(t0=24.0, every=2), windows=None)                       # identical to S0/S1 (records are not a change)
    c = PC.make(rid, "axis_strip", 0.5, GC.W_STRIP, sp, T_END_STRIP, stage="C", in_gain=None, H=H, layout="A", records=rec,
                case_extra=dict(queue_id=qid, label=lab, judged_onset_window_s=list(JUDGE_T), standin=(qid == "S3"), round="B2",
                                parent_queue_id={"S2": "S0", "S3": "S1"}[qid], parent_run_id={"S2": "BS0_axDA3_T12H7p5", "S3": "BS1_axDA3_T12H10p7_standin"}[qid],
                                one_change="bed only: the axis rise 1:10 to the 1.7 m shelf at x 333.25 (S0/S1) -> 1:10 to 13 m at x %.2f, 1:3 to the 1.7 m "
                                           "shelf at x %.2f, shelf 20 m, 1:2 to the 6 m lagoon at x %.2f (pg_hL 13, pg_s2 3, x_back %.2f)" % (
                                               g["x_foot_13m"], g["x_top_1p7m"], g["x_lagoon_6m"], g["x_back_m"])),
                note="FLIP49 campaign B round 2 %s: %s. Strip half width 6 m, particle 0.5 m, 120 s, stage C, box 442 m x zb -25 m, inlet band 0-100 m, "
                     "exit band 362-442 m (sigma 1.41) - as S0/S1. Bed = steep ledge on the DA3 axis (flat 17 m to 180.25, 1:10 to 13 m at %.2f, 1:3 to the "
                     "1.7 m shelf at %.2f, shelf to %.2f, 1:2 to the 6 m lagoon at %.2f, 6 m to the exit band). Judged: onsets 45-80 s only (2D set-up "
                     "artefact)." % (qid, lab, g["x_foot_13m"], g["x_top_1p7m"], g["x_back_m"], g["x_lagoon_6m"]))
    c["case"].update(plan_frozen=PLAN_B2_REL, plan="Unity/Build/FLIP49/plan/plan_B2_frozen.json (queue, frozen_criteria, gate_G2, stop_rule, honesty)",
                     campaign="PER49-B")
    c["analysis"]["plan_frozen"] = PLAN_B2_REL
    c["precheck"] = precheck_B2(c)
    return c


def one_change_vs_parent(c):
    """S2 vs S0 (S3 vs S1): every cfg item equal except the bed, its CTRL numbers (pg_hL, pg_s2, lag_xb), the derived particle-label x
    (shore_x = the ledge top; records only) and names/labels/precheck."""
    qid = (c.get("case") or {}).get("queue_id")
    p = preset_B(B2_PARENT[qid], {})[0]

    def dk(a, b):
        return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    top = dk(c, p)
    parms = dk(c["parms"], p["parms"])
    bed = dk(c["bed"], p["bed"])
    an = dk(c.get("analysis") or {}, p.get("analysis") or {})
    ok = bool(set(top) <= B2_ALLOWED_DIFF["top"] and set(parms) <= B2_ALLOWED_DIFF["parms"] and set(bed) <= B2_ALLOWED_DIFF["bed"]
              and set(an) <= B2_ALLOWED_DIFF["analysis"])
    return dict(parent=p["run_id"], parent_particles_model=p["precheck"].get("particles_model"), top_level_differing=top, parms_differing={k: [p["parms"].get(k), c["parms"].get(k)] for k in parms},
                bed_differing=bed, analysis_differing=an, shore_x=[p.get("shore_x"), c.get("shore_x")], ok=ok,
                rule="only the bed may differ (plus names, labels, precheck and the records-only particle label x shore_x)")


def precheck_B2(c):
    """pre-run checks of a plan-B2 cfg: the plan-B strip checks (layout A, Fenton table, inlet gain, stage C, one launch), with the DA3-axis bed
    and plan-B naming checks replaced by the ledge-bed checks, the plan-B2 naming and the one-change check against S0/S1."""
    out = precheck_B(c)
    ck = out["checks"]
    for k in ("B_bed_is_DA3_axis_spec", "B_bed_equals_DA3_axis_lt_1e-5m", "B_bed_landmarks", "B_plan_named", "B_plan_frozen_exists", "B_S1_labelled_standin"):
        ck.pop(k, None)
    out.pop("bed_B", None)
    out["replaced_plan_B_checks"] = "DA3-axis bed and plan-B naming checks -> ledge bed, plan-B2 naming and one-change checks (plan B2)"
    spec = GC.bed_spec(c)
    ck["B2_bed_is_ledge_spec"] = bool(_same_spec(spec, spec_B2_ledge()))
    o2, k2 = ledge_bed_checks(spec)
    ck.update(k2)
    out["bed_B2"] = o2
    qid = (c.get("case") or {}).get("queue_id")
    sf = c.get("sf")
    if sf:
        ck["sf_H_is_design"] = bool(abs(float(sf["H"]) - {"S2": H_S0, "S3": H_S1}[qid]) < 1e-9)
    ck["B2_plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == PLAN_B2_REL and (c.get("analysis") or {}).get("plan_frozen") == PLAN_B2_REL)
    if qid == "S3":
        ck["B2_S3_labelled_standin"] = bool((c.get("case") or {}).get("standin") is True and "STAND-IN" in str((c.get("case") or {}).get("label")))
    oc = one_change_vs_parent(c)
    out["one_change"] = oc
    ck["B2_one_change_vs_parent"] = oc["ok"]
    ck["B2_parent_analysis_exists"] = bool(os.path.exists(B2_BASE_ANA[qid]))
    ck["B2_plan_frozen_exists"] = bool(os.path.exists(PLAN_B2) and os.path.exists(PLAN_B2 + ".sha256"))
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "fails: " + ", ".join(k for k, v in ck.items() if not v)
    return out


def _medk(rows, ks, key):
    v = [r.get(key) for r in rows if r.get("k") in ks and r.get(key) is not None]
    return float(np.median(v)) if v else None


def round1_numbers():
    """round-1 medians (k2-k4) of S0/S1 from their planB_ana.json and the DA3 reference of plan B [measured]."""
    out = {}
    for q, p in B2_BASE_ANA.items():
        a = json.load(open(p, encoding="utf8"))
        m = a["medians_judged"]
        out[{"S2": "S0", "S3": "S1"}[q]] = dict(run_id=a["run_id"], source=p.replace(GC.REPO + "/", ""), sha256=GC.sha256_file(p), judged_k=a["judged_k"],
                                                inlet_H_m=a["inlet"]["H_mean_110_160_m"], realized_q=a["inlet"]["realized_q"],
                                                n_lip_ge_0p2=sum(1 for r in a["rows"] if r.get("judged") and (r.get("lip_max") or 0) >= 0.2),
                                                **{k: m.get(k) for k in ("x_on", "h_b", "Hc", "H_front", "H_rear", "back_inc", "back_pre_max", "back_on",
                                                                         "back_best", "w07_on", "w07_best", "lip_max")},
                                                volume_stageC_max_rel=a["health"]["volume_corrected_max_rel"],
                                                flat_level_period_means=a["inlet"].get("levels_flat_period_means"))
    pb = json.load(open(PLAN_B, encoding="utf8"))
    out["DA3"] = dict(pb["frozen_criteria"]["DA3_reference"], note="plan_B_frozen.json frozen_criteria.DA3_reference (d1_summary.json medians k2-k9)")
    out["tags"] = "measured (FLIP + STUDY52 ruler through g49_planB_ana.measure / diag_B d1_measure)"
    return out


def transfer_2d_to_3d(r1=None):
    """round-1 2D -> 3D transfer on the same bed and wave (S0 strip -> DA3 centre section): ratio and offset per item [computed from measured]."""
    r1 = r1 or round1_numbers()
    s0, d = r1["S0"], r1["DA3"]
    pairs = dict(back_on=("back_on", "back_on_deg"), back_best=("back_best", "back_best_deg"), w07_on=("w07_on", "width07_on"),
                 w07_best=("w07_best", "width07_best"), H_front=("H_front", "H_front_m"), Hc=("Hc", "Hc_m"))
    out = {}
    for k, (a, b) in pairs.items():
        out[k] = dict(S0_2d=s0[a], DA3_3d=d[b], ratio=d[b] / s0[a], offset=d[b] - s0[a])
    out["tag"] = "computed from measured medians (one bed, one 2D/3D pair: an assumption when carried to the ledge bed)"
    return out


def g2_thresholds(tf=None):
    """gate G2 thresholds. Two transfer models from round 1 (3D = ratio x 2D, 3D = 2D + offset); a 3D ledge run is worth building only if
    BOTH models predict a Q73 improvement over DA3 (best-frame back >= +3 deg) without width07 or height getting worse."""
    tf = tf or transfer_2d_to_3d()
    s0on, s0b = tf["back_on"]["S0_2d"], tf["back_best"]["S0_2d"]
    d_on, d_b = tf["back_on"]["DA3_3d"], tf["back_best"]["DA3_3d"]
    th = dict(back_on_min_deg=24.0, d_back_on_min_deg=8.0, d_back_best_min_deg=5.0, lip_min=0.2, n_lip_min=2, n_judged_min=2,
              n_on_ledge_min=2, x_ledge_foot_m=ledge_geometry()["x_foot_13m"], periods_breaking_x_lt_180_max=1)
    wr = (tf["w07_best"]["DA3_3d"] + 0.2) / tf["w07_best"]["ratio"]
    wo = tf["w07_best"]["S0_2d"] + 0.2
    th["w07_best_max"] = math.floor(min(wr, wo) * 100.0) / 100.0
    hr = 10.0 / tf["H_front"]["ratio"]
    ho = 10.0 - tf["H_front"]["offset"]
    th["H_front_min_m"] = math.ceil(max(hr, ho) * 20.0) / 20.0
    pred = dict(
        back_on_at_threshold=dict(ratio=tf["back_on"]["ratio"] * max(24.0, s0on + 8.0), offset=max(24.0, s0on + 8.0) + tf["back_on"]["offset"], DA3=d_on),
        back_best_at_threshold=dict(ratio=tf["back_best"]["ratio"] * (s0b + 5.0), offset=s0b + 5.0 + tf["back_best"]["offset"], DA3=d_b, Q73_needs=d_b + 3.0),
        w07_best_at_threshold=dict(ratio=tf["w07_best"]["ratio"] * th["w07_best_max"], offset=th["w07_best_max"] + tf["w07_best"]["offset"],
                                   DA3=tf["w07_best"]["DA3_3d"], Q73_not_worse_max=tf["w07_best"]["DA3_3d"] + 0.2),
        H_front_at_threshold=dict(ratio=tf["H_front"]["ratio"] * th["H_front_min_m"], offset=th["H_front_min_m"] + tf["H_front"]["offset"], Q77_needs=10.0))
    why = dict(
        back_on="2D onset back >= 24 deg AND S2 - S0 >= +8 deg (with S0 15.9 deg the two coincide). Round 1 lost about half the back from 2D to 3D "
                "(ratio %.3f, offset %+.1f deg). At the threshold the ratio model gives 3D onset back %.1f deg (DA3 %.1f + %.1f) and the offset model %.1f deg; "
                "both clear Q73's +3 deg plus ~1-2 deg ruler noise at 0.5 m particles" % (
                    tf["back_on"]["ratio"], tf["back_on"]["offset"], pred["back_on_at_threshold"]["ratio"], d_on, pred["back_on_at_threshold"]["ratio"] - d_on,
                    pred["back_on_at_threshold"]["offset"]),
        back_best="best-frame back S2 - S0 >= +5 deg: Q73 judges the best frame; ratio model 3D %.1f deg = DA3 %.1f + %.1f (the Q73 +3 deg), offset model %.1f deg" % (
            pred["back_best_at_threshold"]["ratio"], d_b, pred["back_best_at_threshold"]["ratio"] - d_b, pred["back_best_at_threshold"]["offset"]),
        w07_best="best-frame width07 S2 <= %.2f: 3D adds width (ratio %.3f, offset %+.2f); at the threshold both models keep 3D within DA3 %.2f + 0.2 "
                 "(Q73 'nothing worse')" % (th["w07_best_max"], tf["w07_best"]["ratio"], tf["w07_best"]["offset"], tf["w07_best"]["DA3_3d"]),
        lip="lip >= 0.2 eta_c on >= 2 judged breakers: plunging, not spilling (as G1)",
        H_front="crest-to-front-trough at onset S2 >= %.2f m: the user's Q77 height (>= 10 m in the wave) carried to the strip with round 1's 2D -> 3D height "
                "gain (ratio %.3f, offset %+.2f m); at the threshold both models give >= 10.0 m in 3D. Hc is reported only" % (
                    th["H_front_min_m"], tf["H_front"]["ratio"], tf["H_front"]["offset"]),
        prerequisites="health (inlet H within 5 %% of 7.5 m, no bed leak); >= 2 judged breakers; >= 2 judged onsets at x >= %.2f m (on or after the ledge foot); "
                      "breaking at x < 180 m in <= 1 judged period" % th["x_ledge_foot_m"])
    return th, pred, why


def screen_B2_summary():
    """the cheap screen (no new simulation): existing 2D records with abrupt/steep beds measured with the round-1 code
    (Unity/Build/FLIP49/campaignB/screen_B2/s2_screen.py -> out/*_s2.json; P1c from diag_B/out/d1_summary.json) [measured]."""
    def load(rid):
        p = (SCREEN_B2_DIR + "/" + rid + "_s2.json").replace("\\", "/")
        return json.load(open(p, encoding="utf8")), p

    keys = ("x_on", "h_b", "Hc", "H_front", "back_inc", "back_pre_max", "back_on", "back_best", "w07_on", "w07_best", "lip_max")
    out = dict(tool="Unity/Build/FLIP49/campaignB/screen_B2/s2_screen.py (g49_planB_ana.measure for FLIP49 strips; diag_B/d1_measure for FLIP47/48)", records={})
    for rid, what in (("S1_axis_PG12s_stC", "PG12s axis strip, stage C (the closest analogue): DA3 wave T 12 s H 7.5 m, flat 17 m to x 180.25, 1:10 to 12 m "
                                            "at x 230.25, 1:2.5 to the 1.7 m reef at x 256, reef 20 m, 1:2 to the 6 m lagoon; box 360 m x zb -17 m, exit band from "
                                            "x 290 m (older layout); 0.5 m particles"),
                      ("S1_axis_PG12s", "as above, drift stage A (judged window has k2, k3 only)"),
                      ("S1_axis_PG12s_stB", "as above, drift stage B (judged window has k2 only)"),
                      ("BS0_axDA3_T12H7p5", "S0 re-measured by the screen harness (control: reproduces its planB_ana.json medians exactly)")):
        o, p = load(rid)
        m = o["medians_judged"]
        jr = [r for r in o["rows"] if r["k"] in o["judged_k"]]
        out["records"][rid] = dict(what=what, source=p.replace(GC.REPO + "/", ""), sha256_16=GC.sha256_file(p)[:16], judged_k=o["judged_k"],
                                   medians_judged={k: m.get(k) for k in keys},
                                   n_lip_ge_0p2=sum(1 for r in jr if (r.get("lip_max") or 0) >= 0.2),
                                   eta_incoming_m=[round(r["eta_inc"], 2) if r.get("eta_inc") is not None else None for r in jr],
                                   ranges_judged={k: [min(r[k] for r in jr if r.get(k) is not None), max(r[k] for r in jr if r.get(k) is not None)]
                                                  for k in ("back_on", "back_best", "w07_on", "w07_best", "Hc", "H_front", "h_b", "x_on")})
    s0 = out["records"]["BS0_axDA3_T12H7p5"]["medians_judged"]
    pg = out["records"]["S1_axis_PG12s_stC"]["medians_judged"]
    out["PG12s_stC_minus_S0"] = {k: (pg[k] - s0[k]) if (pg.get(k) is not None and s0.get(k) is not None) else None for k in keys}
    d1 = [r for r in json.load(open(GC.B49 + "/diag_B/out/d1_summary.json", encoding="utf8")) if r["run"] == "P1c"]
    per = {"P1c (1:10 to the beach, T 14 s H 12 m, h 19 m, 0.25 m particles; D1 values)": dict(rows=d1, k=(2, 3, 4), src="Unity/Build/FLIP49/diag_B/out/d1_summary.json")}
    for rid, lab in (("P2c_S5beach_H12_vcx_dp0p25", "P2c (1:7 to the beach, same wave as P1c)"), ("P1b_S2_H12_lvl_dp0p25", "P1b (1:10 to a 1.9 m flat, same wave)")):
        o, p = load(rid)
        per[lab] = dict(rows=o["rows"], k=(2, 3, 4), src=p.replace(GC.REPO + "/", ""))
    f47 = {}
    for lab, d in per.items():
        f47[lab] = dict(source=d["src"], k=list(d["k"]), back_on=_medk(d["rows"], d["k"], "back_on"), back_best=_medk(d["rows"], d["k"], "back_best"),
                        back_pre_max=_medk(d["rows"], d["k"], "back_pre_max"), w07_best=_medk(d["rows"], d["k"], "w07_best"),
                        w07_on=_medk(d["rows"], d["k"], "w07_on"),
                        back_on_each=[round(r["back_on"], 1) if r.get("back_on") is not None else None for r in d["rows"] if r["k"] in d["k"]])
    out["FLIP47_periodic_k2_k4"] = f47
    f48 = {}
    for rid, lab in (("R0_strip_RS_A0p3", "R0: 1:10 to the 1.7 m shelf"), ("G0c_strip_ledge_A0p3", "G0c: 1:11.2 with a 1:4 ledge of 2.8 m"),
                     ("G0a_strip_nw_A0p3_b0p12", "G0a: N-wave (trough ahead) on 1:10")):
        o, p = load(rid)
        r = o["rows"][0]
        f48[lab] = dict(source=p.replace(GC.REPO + "/", ""), back_on=r.get("back_on"), back_pre_max=r.get("back_pre_max"), w07_on=r.get("w07_on"), Hc=r.get("Hc"))
    out["FLIP48_single_wave_strips"] = f48
    out["FLIP47_solitary_beds"] = ("FLIP47 doc section 4 (Docs/Progress/FLIP47_2D_Seabed_ja.md): six beds incl. S2 1:10 to 1.9 m, S5 1:7 ledge to 3.8 m, "
                                   "S6 two steps 11.4 -> 2.9 m; back 3-14 deg and width07 1.9-5.3 on all six (a solitary wave has no trough) [measured, quoted]")
    out["reading"] = [
        "the closest analogue (PG12s axis strip: same DA3 wave, same measure code, 1:2.5 face from 12 m) breaks ON the face at h_b %.1f m with a LOWER crest "
        "than it arrives with (incoming crest about 4.6 m -> Hc %.1f m at onset); judged medians: back onset %.1f deg (S0 %.1f), best %.1f (S0 %.1f), width07 best "
        "%.2f (S0 %.2f), crest-to-front-trough %.1f m (S0 %.1f) [measured]" % (pg["h_b"], pg["Hc"], pg["back_on"], s0["back_on"], pg["back_best"], s0["back_best"],
                                                                             pg["w07_best"], s0["w07_best"], pg["H_front"], s0["H_front"]),
        "steeper planar slopes change the 2D back by a few degrees only: P2c (1:7) vs P1c (1:10), same periodic wave: onset %+.1f deg, best %+.1f deg, width07 best "
        "%+.2f; the single-wave 1:4 ledge (G0c) vs 1:10 (R0): onset %+.1f deg [measured]" % (
            f47["P2c (1:7 to the beach, same wave as P1c)"]["back_on"] - f47["P1c (1:10 to the beach, T 14 s H 12 m, h 19 m, 0.25 m particles; D1 values)"]["back_on"],
            f47["P2c (1:7 to the beach, same wave as P1c)"]["back_best"] - f47["P1c (1:10 to the beach, T 14 s H 12 m, h 19 m, 0.25 m particles; D1 values)"]["back_best"],
            f47["P2c (1:7 to the beach, same wave as P1c)"]["w07_best"] - f47["P1c (1:10 to the beach, T 14 s H 12 m, h 19 m, 0.25 m particles; D1 values)"]["w07_best"],
            f48["G0c: 1:11.2 with a 1:4 ledge of 2.8 m"]["back_on"] - f48["R0: 1:10 to the 1.7 m shelf"]["back_on"]),
        "no existing 2D record with an abrupt or steep bed reaches a back of 25 deg at onset on its median; none gains +8 deg over its gentle-bed partner [measured]",
        "prediction for S2 [computed from the analogue; guess-level for the transfer from 12 m/1:2.5 to 13 m/1:3]: the steep ledge lowers and widens the breaker "
        "instead of steepening its back; G2 expected to FAIL; Q73 expected: no improvement over S0"]
    out["tags"] = "measured (FLIP + STUDY52 ruler), AI self-assessment; the user judges print-likeness"
    return out


def plan_B2():
    PC = _pc()
    pb = json.load(open(PLAN_B, encoding="utf8"))
    r1 = round1_numbers()
    tf = transfer_2d_to_3d(r1)
    th, pred, why = g2_thresholds(tf)
    scr = screen_B2_summary()
    g = ledge_geometry()
    lin = linear_numbers()
    s2 = preset_B("BS2", {})[0]; s3 = preset_B("BS3", {})[0]
    om = 2 * math.pi / 12.0

    def cg(h):
        k = k_lin(12.0, h)
        return om / k * 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h)), 2 * math.pi / k
    Ks13 = math.sqrt(cg(17.0)[0] / cg(13.0)[0])
    _, tb13 = GC.sf_solve(13.0, 12.0, 1.0, GC.SF_N)
    L0 = GC.G * 144.0 / (2 * math.pi)
    Ks17 = math.sqrt((GC.G * 12.0 / (4 * math.pi)) / cg(17.0)[0])
    xi = lambda H17, s: (1.0 / s) / math.sqrt((H17 / Ks17) / L0)
    phys = dict(T_s=12.0, L_lin_17m=cg(17.0)[1], L_lin_13m=cg(13.0)[1], Ks_17_to_13_linear=Ks13, Hmax_fit_13m=float(tb13["Hmax_fit"]),
                q13_S0_linear=r1["S0"]["inlet_H_m"] * Ks13 / float(tb13["Hmax_fit"]), q13_S1_linear=r1["S1"]["inlet_H_m"] * Ks13 / float(tb13["Hmax_fit"]),
                iribarren_xi0=dict(S0_wave=dict(slope_1_10=xi(r1["S0"]["inlet_H_m"], 10.0), slope_1_3=xi(r1["S0"]["inlet_H_m"], 3.0), slope_1_2p5=xi(r1["S0"]["inlet_H_m"], 2.5)),
                                   S1_wave=dict(slope_1_10=xi(r1["S1"]["inlet_H_m"], 10.0), slope_1_3=xi(r1["S1"]["inlet_H_m"], 3.0))),
                note="linear shoaling and the Fenton Hmax fit (g47_sfwave) [computed]; the measured S1 wave stayed intact below 13 m although its linear q13 > 1 "
                     "(unsteady shoaling; the FLIP wave also decays along the flat), so q13 is only indicative. Iribarren xi0 0.5-3.3 = plunging "
                     "(Battjes 1974) [literature]: the 1:3 face is in the plunging range for both waves")
    crit = copy.deepcopy(pb["frozen_criteria"])
    crit["source"] = ("plan_B_frozen.json (SHA %s...) frozen_criteria copied; changed only: added_targets (Q77: Hc >= 9 m -> crest-to-front-trough >= 10 m, "
                      "Hc reported), definitions.judged_breaker_strip_B2, health.strip_health_S2/S3 (added), gains_reported (Q77 order). Every P1-P5/PERIODIC/"
                      "health threshold unchanged (g49_periodic_ana reads them as before)" % GC.sha256_file(PLAN_B)[:16])
    crit["added_targets"] = dict(back_best_deg_min=25.0, width07_best_max=1.6, H_front_min_m=10.0, Hc="reported only (Q77)",
                                 rule="judged on the median over judged breakers, never on best frames alone; in 3D runs. Onset and pre-onset maximum back reported "
                                      "alongside. The strips are read through gate G2 (2D -> 3D transfer), not against these 3D targets",
                                 replaced=dict(Hc_min_m=9.0, by="H_front_min_m 10.0", why="user Q77 (a), 2026-10-16"))
    crit["definitions"]["judged_breaker_strip_B2"] = ("as judged_breaker_strip: centre onset 45 s <= t <= 80 s; the same event rule; the event origin rule uses "
                                                      "the step foot of the bed (g49_periodic_ana: x_foot = 220.25 m for the ledge, x_toe + 50 = 230.25 m for S0)")
    crit["health"]["strip_health_S2"] = ("pass/fail: measured inlet H at x 110-160 m (centre gauges) within 5 %% of 7.5 m; no bed leak (frac < 1e-4); the Houdini "
                                         "run completes. Reported, not pass/fail (AM-B3: no 2D reef/lagoon strip of this axis can meet the 1 %% interior rule; S0 "
                                         "itself fails it): volume drift (stage C) and the 'flat' (x 110-160 m) period-mean level. Comparability flags (frozen): "
                                         "|S2 - S0| interior volume > 2 points, or |S2 - S0| flat period-mean level > 0.5 m in the judged periods, or ledge "
                                         "reflection Kr > 0.20 -> 'comparison weakened' printed beside G2. Health failure: diagnose, fix the preset, rerun (not a round)")
    crit["health"]["strip_health_S3"] = "as strip_health_S2 with 10.7 m for the inlet design (S1 arrived 9.43 m = -12 %: reported, as S1); bed leak and completion pass/fail"
    crit["gains_reported"] = ["crest-to-front-trough H at onset (the Q77 height) and crest-to-rear-trough H", "Hc (reported only, Q77)",
                              "Hc / incoming crest over depth >= 16.5 m", "measured realized q at 17 m", "ledge reflection Kr at the gauges"]
    gate = dict(
        name="G2", frozen=True, decides="whether a coarse 3D ledge run DL1 is worth building",
        judged_on="S2 vs S0 medians over judged breakers (onsets 45-80 s), STUDY52 ruler through g49_planB_ana.measure (the round-1 code); S0 = "
                  "BS0_axDA3_T12H7p5 planB_ana.json (SHA %s...)" % r1["S0"]["sha256"][:16],
        thresholds=th, predicted_3d_at_thresholds=pred, why=why,
        transfer_2d_to_3d=tf,
        pass_="all of: back onset S2 >= %.1f deg AND S2 - S0 >= +%.1f deg; best-frame back S2 - S0 >= +%.1f deg; best-frame width07 S2 <= %.2f; lip >= %.1f on >= %d "
              "judged breakers; crest-to-front-trough S2 >= %.2f m; prerequisites" % (th["back_on_min_deg"], th["d_back_on_min_deg"], th["d_back_best_min_deg"],
                                                                                       th["w07_best_max"], th["lip_min"], th["n_lip_min"], th["H_front_min_m"]),
        then_pass="freeze DL1 in an amendment BEFORE building it (exact 3D bed numbers, particles/wall from precheck, and the registered expected numbers: "
                  "S2's medians carried through both transfer models), then build and run DL1",
        then_fail="do not build DL1. Stop and ask the user, listing which G2 items passed and the options: S2 at 0.25 m particles (is the low ledge crest a "
                  "resolution effect?), the ledge with a 6 m terrace instead of the 1.7 m shelf (one change), keep DA3, or another direction",
        S3_role="S3 vs S1 is reported with the same items (the ledge at the stand-in's q 0.80); it never passes or fails G2 (stand-in, as S1)",
        prediction_from_screen="FAIL expected (see screen_B2)")
    stop = dict(
        q73=dict(direction="steepen the back / narrow the body by breaking on a steep ledge (Q77 b; a new direction)",
                 rounds=["S2 vs S0 (2D)", "DL1 vs DA3 (3D, only after G2 PASS)"],
                 improvement_any=["median best-frame back angle >= +3 deg", "median best-frame width07 <= -0.3"],
                 nothing_worse_than=dict(back_deg=-2.0, width07=0.2, H_front_m=-0.5,
                                         note="ruler noise at 0.5 m particles; height compared crest-to-front-trough (Q77), Hc reported"),
                 height_only="a height gain alone is not an improvement in this direction (Q77: DA3 already reaches crest-to-trough 10.5-11.4 m; focus back/width07)",
                 rule="two rounds in this direction without improvement means stop and ask",
                 single_round_stop=["G2 fails (no frozen next round in this direction)", "DL1 does not improve on DA3"]),
        order="S2, then S3 (S3 runs whatever G2 says, unless S2 hits a hard stop), then G2. One Houdini simulation at a time; each launch <= 29 min",
        hard_stops=["a health failure that cannot be diagnosed", "fewer than 2 judged S2 breakers reach the ledge foot (x >= 220.25 m)",
                    "breaking at x < 180 m in >= 2 judged S2 periods"],
        campaign_end_round2="after G2 FAIL (stop and ask) or after DL1 (show all videos and numbers, Q73 test DL1 vs DA3, then ask)",
        always=["never change two things in one run", "never loosen a frozen threshold after seeing a result", "every run ships a g49_video2 compare mp4 and the strip "
                "analysis (g49_planB.py ana2)"])
    med = scr["records"]["S1_axis_PG12s_stC"]["medians_judged"]
    queue = [
        dict(id="S2", preset="BS2", run_id=s2["run_id"], parent="S0 (BS0_axDA3_T12H7p5)", what="S0 with one change, the bed: the DA3 axis rise 1:10 to the 1.7 m shelf -> "
             "1:10 to 13 m at x %.2f then 1:3 to the 1.7 m shelf at x %.2f (shelf 20 m, 1:2 to the 6 m lagoon at x %.2f, 6 m to the exit band). DA3 wave T 12 s "
             "H 7.5 m, particle 0.5 m, 120 s, stage C, layout A" % (g["x_foot_13m"], g["x_top_1p7m"], g["x_lagoon_6m"]),
             particles_model=s2["precheck"]["particles_model"], wall_est_h=s2["precheck"].get("wall_est_h"), est_minutes=20,
             est_note="S0 took 0.29 h for 120 s (measured); S2's water is about the same (particles_model vs S0's in design.strips)",
             expected=dict(source="screen analogue S1_axis_PG12s_stC (k2-k4 medians) [measured] carried to the 13 m / 1:3 ledge [guess]",
                           onset_x_m=[226.0, 242.0], h_b_m=[6.5, 9.5], Hc_m=[2.5, 4.5], H_front_m=[3.0, 5.5], back_incoming_deg=[9.0, 11.5],
                           back_pre_max_deg=[11.0, 15.0], back_onset_deg=[7.0, 12.5], back_best_deg=[6.0, 12.5], width07_onset=[4.0, 8.5], width07_best=[1.8, 8.7],
                           lip="0.4-0.6 on >= 2 of 3 (plunging)", reflection_Kr=[0.08, 0.18],
                           analogue_medians=med, S2_minus_S0_expected=dict(back_onset_deg=[-9.0, -3.5], back_best_deg=[-8.0, -1.0], width07_best=[-0.8, 6.0],
                                                                            H_front_m=[-5.5, -3.0], Hc_m=[-3.5, -1.5]),
                           G2="FAIL expected (back, width07 and crest-to-front-trough items)", Q73="no improvement expected"),
             decision_after="health first (strip_health_S2); then S3; G2 is applied after S2's analysis and registered in campaignB/registry.jsonl before S3 is read"),
        dict(id="S3", preset="BS3", run_id=s3["run_id"], parent="S1 (BS1_axDA3_T12H10p7_standin)", what="S1 (STAND-IN, Fenton T 12 s H 10.7 m) with the same one change "
             "(the ledge bed). Report-only, never shown or reported as the wave", particles_model=s3["precheck"]["particles_model"], wall_est_h=s3["precheck"].get("wall_est_h"),
             est_minutes=20,
             expected=dict(source="[guess] no analogue with this wave on a step; scaled from the PG12s analogue (Hc ~0.4 h_b on the face)",
                           onset_x_m=[221.0, 236.0], h_b_m=[8.5, 12.5], Hc_m=[3.5, 6.5], H_front_m=[4.5, 8.5], back_onset_deg=[8.0, 14.0], back_best_deg=[7.0, 14.0],
                           width07_best=[2.5, 6.5], lip="likely >= 0.2", breaking_x_lt_180="none expected (S1 had none)",
                           S3_minus_S1_expected=dict(back_onset_deg=[-7.0, -1.0], Hc_m=[-4.0, -1.0])),
             decision_after="report S3 vs S1 (ledge effect at q 0.80); then apply the G2 decision"),
        dict(id="DL1", what="ONLY after G2 PASS (frozen first in an amendment): coarse 3D = the DA3 bed (SC37y30: spur k 0.35 -> 1.0 taper at x 277.25-333.25, 25 m side "
             "channel at y 30 m) with the axis rise replaced by the same ledge (pg_hL 13, pg_s2 3; the 1:3 continues off the axis through the existing formula) and the "
             "reef tongue starting at the ledge top (x_back %.2f); everything else as DA3 (wave, inlet, box 442 x 85 m, stage C, particle 0.5 m, 92 s, <= 4.5 h in "
             "launches <= 29 min). Expected numbers registered before launch from S2 through both transfer models" % g["x_back_m"],
             decision_after="Q73 test DL1 vs DA3; show; stop and ask (round-2 end)"),
    ]
    honesty = dict(
        screen_prediction=("the cheap screen predicts that S2 FAILS G2 and does not improve on S0: the closest existing analogue (PG12s axis strip, 1:2.5 from 12 m, "
                           "same wave and code) broke on the face with a lower crest and a gentler back than S0. S2 differs from it by the ledge foot (13 vs 12 m), "
                           "the face (1:3 vs 1:2.5) and the layout (box 442 m/zb -25 m/exit band 362 m vs 360 m/-17 m/290 m). S2 still runs because the user chose this "
                           "direction (Q77) and it costs about 0.3 h; it confirms the analogue on the exact bed and the layout of S0"),
        volume_rule=("the plan-B 1 %% interior volume rule is reported, not pass/fail, for the 2D strips (AM-B3: S0 fails it with either drift stage because the "
                     "closed 2D lagoon stores ~4 %% of the interior water). This is a choice of this plan [chosen], made before any S2/S3 run; the user has not "
                     "ruled on it. 2D strips are compared only with each other, and G2 only decides whether to build a 3D run, where the 1 %% rule applies again"),
        transfer_model=("G2 carries 2D numbers to 3D with round 1's single S0 -> DA3 pair (1:10 axis bed). A ledge may feed water sideways differently, so the "
                        "transfer is an assumption [guess]; requiring both the ratio and the offset model to pass is the conservative choice"),
        resolution=("at 0.5 m particles the 0.7-0.9 eta_c band is ~2-3 cells tall for Hc 6 m but only ~1 cell for Hc 3 m: if the ledge crest is low, its back angle "
                    "is noisier (the PG12s analogue's best-frame backs span 1.6-46.5 deg)"),
        layout_differences=("S2's lagoon is 6 m deep and %.0f m long before the exit band (S0: the drop ends 0.15 m before the band) - forced by keeping x_toe, the "
                            "box and the exit band; the shelf, its 20 m length, the 1:2 drop and the 6 m depth are S0's own elements" % g["lagoon_len_to_exit_band_m"]),
        reflection="the 1:3 face reflects more (PG12s analogue Kr 0.13 vs S0 0.04 [measured]); the inlet gauges then see a partly standing wave; reported",
        standin="S3 is the 10.7 m single long-crested stand-in = an enlarged input; it tests only the breaking stage, is labelled STAND-IN and is never shown "
                "or reported as the wave",
        height="Q77: the height target is crest-to-front-trough >= 10 m (DA3 10.5-11.4 m at onset already); Hc is reported only",
        chosen=["the ledge numbers 13 m and 1:3 (the user's Q77 option)", "the 1.7 m shelf, its 20 m length, the 1:2 drop to 6 m (S0's elements)",
                "stage C and in_gain 1.0 (as S0/S1)", "the judged window 45-80 s (as round 1)", "all G2 thresholds (from round-1 transfer and Q73)",
                "volume rule reported for 2D strips", "S3 runs whatever G2 says", "the Q73 improvement items limited to back and width07 in this direction"],
        computed_by_FLIP="break location, time, height, shape, narrowness and recurrence",
        site="the ledge is a chosen bed shape, not a measured place (Q63/10-13: shape first, no site)",
        skip_option=("because the screen already predicts the outcome, skipping S2/S3 and asking the user straight away is a defensible alternative; it is "
                     "the user's or the main session's call and is not taken in this plan (the frozen queue runs S2 then S3)"),
        screen_waves=("the FLIP47 records (P1b, P1c, P2c) use another wave (T 14 s, H 12 m at 19 m) and 0.25 m particles, and the FLIP48 strips are single waves "
                      "without a trough: they show the size of slope effects, not S2's numbers; only the PG12s strips share S0's wave, particle size and code"),
        self_assessment="every shape number is AI self-assessment through the STUDY52 ruler; the user judges print-likeness")
    P = dict(
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_pcfg.py freezeB2 (g49_planB.py plan_B2)", canonical_path=PLAN_B2_REL,
        campaign="PER49-B", round="B2",
        parent_plan=dict(path=PLAN_B_REL, sha256=GC.sha256_file(PLAN_B), note="read only, not edited; round-1 results and amendments AM-B1..B5 belong to it"),
        parent_plans_upstream=pb.get("parent_plans"),
        user_decisions_Q77=dict(
            date="2026-10-16", route="Claude Code main conversation, AskUserQuestion after round 1 (S0/S1, G1 provisional FAIL)",
            answers_quoted=["「浪不够高」用哪种高度来比？ → 浪顶到浪谷 (Recommended)", "方案 B 第 2 轮走哪个方向？ → 急陡台阶 2D 板 (Recommended)"],
            a_height="height compared crest-to-trough like Cartwright & Nakamura (2009) 10-12 m: the plan-B target Hc >= 9 m is replaced by crest-to-front-trough "
                     ">= 10 m (DA3 reaches 10.5-11.4 m at onset); Hc is still reported",
            b_direction="round 2 = the frozen option 'a steep-ledge axis strip (1:10 from 17 to 13 m, then 1:3)': S2 (DA3 wave) and S3 (stand-in), one change each; "
                        "focus on the back angle and width07; a 3D ledge run only through a gate that allows for the ~2x back loss from 2D to 3D",
            recorded_in="Docs/Workflow/Production_Workflow_ja.md Q77 (main session)"),
        supervisor_rules=pb.get("supervisor_rules"), user_rule_Q73=pb.get("user_rule_Q73"),
        round1_results=r1, screen_B2=scr,
        design=dict(ledge=g, strip_bed=dict(spec=GC.bed_record(spec_B2_ledge()), formula=GC.bed_formula(spec_B2_ledge())),
                    bed_choice=dict(
                        shelf_depth="1.7 m = S0's shelf and the screen analogue's reef (the comparison with S0 changes only the rise; the analogue's numbers transfer)",
                        shelf_length="20 m = S0's reef top and the analogue's reef",
                        behind="1:2 drop to 6 m and 6 m to the exit band 362-442 m = S0's drop and band depth; the 6 m lagoon becomes ~%.0f m long (forced)" % g["lagoon_len_to_exit_band_m"],
                        not_chosen=["a 6 m terrace instead of the shelf (no shallow reef, no closed pool; but then two elements differ from S0 and the analogue does "
                                    "not apply) - kept as the first variant to offer if G2 fails",
                                    "a long 1.7 m shelf to x 353.25 so that everything behind matches S0 (a closed shallow pool in 2D, FLIP47 P1b)",
                                    "a 13 m terrace before the face so that the face top sits at S0's x 333.25 (adds a second bed change)"],
                        formula_path="g49_common.bed_z / VEX bedgrad_pg two-slope rise (pg_hL, pg_s2), already used and checked for PG12s; no scene change"),
                    strips=dict(S0_parent_particles_model=s2["precheck"]["one_change"].get("parent_particles_model"),
                                S2=dict(run_id=s2["run_id"], particles_model=s2["precheck"]["particles_model"], sf_q=s2["precheck"].get("sf_q"),
                                        one_change=s2["precheck"]["one_change"]),
                                S3=dict(run_id=s3["run_id"], particles_model=s3["precheck"]["particles_model"], sf_q=s3["precheck"].get("sf_q"),
                                        one_change=s3["precheck"]["one_change"])),
                    physics=phys, linear_numbers_plan_B=lin,
                    same_as_S0_S1="inlet band 0-100 m (in_gain 1.0 from plan/in_gain.json), exit band 362-442 m sigma 1.41, stage C, box 442 m x zb -25 m, half width "
                                  "6 m, particle 0.5 m, 120 s, gauges x 110/128/160 m, records, level regions"),
        frozen_criteria=crit, gate_G2=gate, stop_rule=stop, queue=queue, honesty=honesty,
        implementation=dict(tools=["Tools/GWWaveGen/flip49/g49_planB.py", "Tools/GWWaveGen/flip49/g49_planB2_ana.py", "Tools/GWWaveGen/flip49/g49_planB_ana.py",
                                   "Tools/GWWaveGen/flip49/g49_pcfg.py", "Tools/GWWaveGen/flip49/g49_periodic_ana.py", "Tools/GWWaveGen/flip49/g49_video2.py",
                                   "Tools/GWWaveGen/flip49/g49_chain.py"],
                            commands=["py -3.10 -B g49_pcfg.py cfg BS2   (then BS3)", "py -3.10 -B g49_chain.py <cfg> (launches <= 29 min)",
                                      "py -3.10 -B g49_periodic_ana.py all <run>", "py -3.10 -B g49_planB.py ana2 <run>", "py -3.10 -B g49_video2.py compare <run>"],
                            module_sha256_16=dict(GC.module_shas(), **{"flip49/g49_planB.py": GC.sha256_file(os.path.abspath(__file__))[:16],
                                                                       "flip49/g49_planB_ana.py": GC.sha256_file(os.path.join(_HERE, "g49_planB_ana.py"))[:16],
                                                                       "flip49/g49_planB2_ana.py": GC.sha256_file(os.path.join(_HERE, "g49_planB2_ana.py"))[:16],
                                                                       "flip49/g49_video2.py": GC.sha256_file(os.path.join(_HERE, "g49_video2.py"))[:16]}),
                            hip=GC.HIP.replace(GC.REPO + "/", ""), hip_sha256=GC.sha256_file(GC.HIP),
                            screen_tool_sha256_16=GC.sha256_file(OUT_B + "/screen_B2/s2_screen.py")[:16]),
    )
    return P


def freeze_B2(force=False, reason=None):
    os.makedirs(os.path.dirname(PLAN_B2), exist_ok=True)
    if os.path.exists(PLAN_B2) and not force:
        return PLAN_B2, "exists (not changed)"
    if os.path.exists(PLAN_B2) and force:
        runs = [p for p in glob.glob(os.path.join(GC.B49, "*", "*", "cfg.json"))
                if (json.load(open(p, encoding="utf8")).get("case") or {}).get("plan_frozen") == PLAN_B2_REL
                and glob.glob(os.path.join(os.path.dirname(p), "run_c*.json"))]
        if runs:
            raise SystemExit("a plan-B2 run exists (%s); the plan is not refrozen" % runs[0])
        if not reason:
            raise SystemExit("refreezing before any run needs --reason")
    d = plan_B2()
    if os.path.exists(PLAN_B2) and force:
        old = json.load(open(PLAN_B2, encoding="utf8"))
        d["refrozen_history"] = list(old.get("refrozen_history") or []) + [dict(frozen_at=old.get("frozen_at"), sha256=GC.sha256_file(PLAN_B2), reason=reason)]
    s = json.dumps(d, indent=1, ensure_ascii=False)
    open(PLAN_B2, "w", encoding="utf8", newline="\n").write(s)
    h = GC.sha256_file(PLAN_B2)
    open(PLAN_B2 + ".sha256", "w", newline="\n").write(h + "  plan_B2_frozen.json\n")
    return PLAN_B2, "new %s" % h[:16]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "ana":
        import g49_planB_ana as AB
        AB.main(a[1:])
    elif a[0] == "ana2":
        import g49_planB2_ana as AB2
        AB2.main(a[1:])
    elif a[0] == "lin":
        print(json.dumps(linear_numbers(), indent=1))
    else:
        print(__doc__); sys.exit(1)
