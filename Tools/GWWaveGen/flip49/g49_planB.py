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
    raise SystemExit("plan B presets: BS0, BS1 (BX1 after G1)")


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
    elif a[0] == "lin":
        print(json.dumps(linear_numbers(), indent=1))
    else:
        print(__doc__); sys.exit(1)
