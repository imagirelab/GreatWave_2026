# -*- coding: utf-8 -*-
"""FLIP52 'DFG-2' plan freezer (py -3.10 -B). 2026-10-17 written new (Claude).
Reads the numpy design screens Unity/Build/FLIP52/screens/dfg52_screen.json and dfg52_sponge.json (written by dfg52_screen.py), recomputes
the chosen component list, the cost model and the frozen gates, and writes Unity/Build/FLIP52/plan/plan_DFG_frozen.json + .sha256
(refuses to overwrite an existing frozen plan unless --force; a change after freezing goes into Unity/Build/FLIP52/plan/amendments.jsonl).
Nothing in flip45-flip51 is edited; no Houdini is started; nothing is committed.
usage: py -3.10 -B dfg52_plan.py freeze [--force] | show
"""
import os, sys, json, math, time, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                       # noqa: E402
import dfg52_screen as S                 # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
B52 = REPO + "/Unity/Build/FLIP52"
PLAN = B52 + "/plan/plan_DFG_frozen.json"
SCREEN = B52 + "/screens/dfg52_screen.json"
SPONGE = B52 + "/screens/dfg52_sponge.json"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
CHOSEN = "P28_345_eq_hyb60s28"
FPS = 24.0


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def r4(v, n=4):
    return float(round(float(v), n))


def row(rows, name):
    return [r for r in rows if r["name"] == name][0]


def brief(r):
    L, N = r["lin"], r["nl2"]
    keep = ("Hc", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50", "kpHc", "W50_m", "miss")
    return dict(lin={k: L.get(k) for k in keep} | dict(N1=L["N1"]["N1"]), nl2={k: N.get(k) for k in keep} | dict(N1=N["N1"]["N1"], t_s=N["t"]),
                Nt_lin=r4(r["Nt_lin"], 3), Nt_nl2=r4(r["Nt_nl2"], 3), focus_point_secondary_lin=r4(r["focus_point_secondary_lin"], 3),
                c_in_line_lin_m=r4(r["c_in_line_lin"], 3), c_in_line_nl2_m=r4(r["c_in_line_nl2"], 3), gain_over_c_in_nl2=r4(r["gain_over_c_in_nl2"], 3),
                gain_over_incoming_r15L=r4(r["gain_over_incoming_r15L"], 3), gain_over_max_component=r4(r["gain_over_max_component"], 2),
                a_max_comp_m=r4(r["a_max_comp"], 5), sum_a2_over_DM1A=r4(r["sum_a2_over_DM1A"], 3), a_sum_m=r4(r["a_sum"], 5),
                realization=r.get("realization"), bands_kp_crest_nl2=dict(inlet=r4(r["bands"]["kp_crest_inlet_nl2"], 3), side=r4(r["bands"]["kp_crest_side_nl2"], 3)),
                aperture=r4(r["rays"]["aperture"], 4), t_full_s=r4(r["rays"]["t_full_s"], 2), ncomp=r["ncomp"], cpu_s=r["cpu_s"])


def cost(L):
    """[computed from measured rates] particle count and wall time of the 0.5 m run and the 1.0 m smoke."""
    vol = L["Lx"] * L["W"] * L["h"]
    seed = 5383840 / 678965.0          # particles per m^3 at dp 0.5, frame 1 of S51X2 dp 0.5 (D19B volume 678,965 m^3) [measured]
    n0 = vol * seed
    grow = (1.05, 1.16)                # V1 6.26 -> 6.60 M (1.05), DM1A ~9.2 / 7.93 per m^3 (1.16) [measured]
    t_end = 105.0
    nf = int(round(t_end * FPS)) + 1
    f_pre = int(round(25.0 * FPS))
    pre_rate = 0.378                   # s per Mp per frame, V1 launch 1 (frames 1-737, 1743 s, 6.26 M, incl. launch overhead) [measured]
    dev_rate = (0.62, 0.74)            # V1 launches 2-4 (4.58-4.81 s/frame at 6.45-6.60 M) = 0.70-0.74 incl. r5 EVERY frame; minus r5 0.4-0.8 s -> 0.62 [measured/derived]
    heavy = 3 * int(10.0 * FPS / 3)    # r5 every 3rd frame in [t_fn - 6, t_fn + 4] for 3 groups
    r5_s = 2.4                         # s per heavy frame (g50_common.R5_S_PER_FRAME) [measured]
    n_launch = 6
    relaunch_s = 60.0 + 24 * 3.5       # restart + half a checkpoint interval (48 frames) re-simulated [guess]
    lo = (f_pre * pre_rate * n0 * 1.0 + (nf - f_pre) * dev_rate[0] * n0 * grow[0]) / 1e6 + heavy * r5_s + (n_launch - 1) * relaunch_s
    hi = (f_pre * pre_rate * n0 * grow[0] + (nf - f_pre) * dev_rate[1] * n0 * grow[1]) / 1e6 + heavy * r5_s + (n_launch - 1) * relaunch_s
    sm_n0 = vol * 1.0                  # dp 1.0: 1 particle per m^3 seeding
    sm_t = 90.0
    sm_nf = int(round(sm_t * FPS)) + 1
    smoke_rate = 581.8 / 1201 / 0.853673   # SMOKE50DA: s per frame per million particles (substeps 1) [measured, x51_pcfg.SMOKE_RATE]
    sm = [smoke_rate * sm_n0 * 1.1 / 1e6 * sm_nf / 3600.0, smoke_rate * sm_n0 * 1.3 / 1e6 * sm_nf / 3600.0 * 1.6]
    return dict(
        water_volume_m3=vol, seed_per_m3_dp0p5=r4(seed, 3),
        particles_dp0p5_M=dict(initial=r4(n0 / 1e6, 2), peak=[r4(n0 * grow[0] / 1e6, 2), r4(n0 * grow[1] / 1e6, 2)], limit=7.0,
                               tag="computed from the measured seeding density x the measured growth"),
        run_dp0p5=dict(t_end_s=t_end, frames=nf, heavy_r5_frames=heavy, est_h=[r4(lo / 3600, 2), r4(hi / 3600, 2)], max_hours=3.3, ckpt_every=48,
                       wall_limit_s=1740, launches_expected=n_launch,
                       rule="frames < 25 s at 0.378 s/Mp/frame (V1 launch 1), later frames at 0.62-0.74 s/Mp/frame (V1 launches 2-4), r5 2.4 s/heavy frame, "
                            "5 relaunches x 144 s [measured rates, guessed relaunch overhead]",
                       rss_GB="5.5-7.5 (V1 6.6 M particles: 7.5-8.1 GB) [measured scale]", disk_GB="4-6 (V1 6.0 GB with r5 every frame) [measured scale]"),
        smoke_dp1p0=dict(t_end_s=sm_t, frames=sm_nf, particles_M=r4(sm_n0 / 1e6, 2), est_h=[r4(sm[0], 2), r4(sm[1], 2)], max_hours=0.75,
                         rule="SMOKE50DA measured 0.567 s per Mp per frame x growth 1.1-1.3 x substeps up to 1.6 (as plan E screens)"),
        numpy_screens_cpu_s="each case 1-10 s, the full screen 43 + 61 + 48 s (limit 120 s each) [measured]",
    )


def build():
    scr = json.load(open(SCREEN, encoding="utf-8"))
    spg = json.load(open(SPONGE, encoding="utf-8"))
    rows = scr["rows"]
    L = dict(scr["layout"])
    ch = row(rows, CHOSEN)
    c = S.components(28.0, (3, 4, 5), "eq", ("hyb", 60.0, 28.0, 85.0, 17), S.A_SUM_DM1A, L["h"])
    th, wd = S.dirset(("hyb", 60.0, 28.0, 85.0, 17))
    om, wf = S.freqset(28.0, (3, 4, 5), "eq")
    t_f1 = 44.0
    P = 28.0
    plan = dict(
        status="FROZEN", plan="DFG-2", campaign="FLIP52-DFG2",
        title="FLIP52 plan DFG-2: periodic three-frequency directional group (P 28 s; T 9.33 / 7 / 5.6 s; the plan E X2 direction set) "
              "focusing on a flat 20 m bed, one 0.5 m run of three groups, a 1.0 m smoke as a pipeline check only",
        tools=dict(screen="Tools/GWWaveGen/flip52/dfg52_screen.py", freezer="Tools/GWWaveGen/flip52/dfg52_plan.py"),
        trigger=dict(
            source="campaign E judge rank 3 (FLIP51 plan_E_frozen ranking_summary; mechanism 'deep focused groups'); plan E decision 19:28 'nothing "
                   "promotable ... DFG-2 multi-frequency engineering next day'; round E2 (AM-E1, X2 then X1 at 0.5 m) running 19:30-~00:00",
            user_2026_10_17_1710="the big wave is not converged enough; converge the shape toward the screenshot as far as pure physics allows; "
                                 "decide self-checkable steps without asking",
            target_image="Unity/Build/FLIP50/_scratch/target/user_target_20261017.jpg (git-ignored; read only; never copied, uploaded or committed); "
                         "used only through the frozen e51 read values"),
        physics_rules=dict(
            forces="gravity, the flat bed and the incoming waves only; no force toward a shape; no wind, no current (the return current only "
                   "cancels the target's own mean mass flux)",
            Q39="a_sum = 6.331240 m = the DM1A input sum, NOT enlarged; the input variance sum a^2 is 0.354 x DM1A's; gains are reported over the "
                "largest incoming crest, each frequency and each component",
            Q52="periodic recurrence: f_n = n / P makes the whole sea P-periodic, so ONE focused group recurs at the same spot every P = 28.0 s",
            Q54_honesty="chosen at the inlet: P, the three frequencies and their equal weights, the 34 directions and Gaussian weights, a_sum, "
                        "the focus point (150, 0) and time t = 44 + 28 m s; computed by FLIP: propagation, dispersion, focusing, the crest's growth, "
                        "breaking, any jet / plume"),
        sea=dict(
            P_s=P, harmonics_n=[3, 4, 5], T_s=[r4(P / 3, 6), 7.0, 5.6], f_Hz=[r4(n / P, 6) for n in (3, 4, 5)], omega_rad_s=[r4(v, 6) for v in om],
            freq_weights=[r4(v, 6) for v in wf], freq_weight_rule="equal [chosen: screen round 1-2: equal weights give the lowest temporal isolation "
                                                                   "Nt (0.42 vs JONSWAP 0.79) at the same width]",
            amp_per_freq_m=[r4(S.A_SUM_DM1A * v, 6) for v in wf],
            directions_deg=[r4(v, 6) for v in th], dir_weights=[r4(v, 6) for v in wd],
            direction_rule="+-linspace(2, 85, 17) deg, w ~ exp(-(|th| - 60)^2 / (2 x 28^2)), normalised over the 34 directions = the plan E X2 set "
                           "(c51_sweepD.gauss_lobes(60, 28, n=17, cap=85)); the SAME set for each frequency [chosen]",
            n_components=int(len(th) * 3), a_nj_rule="a_nj = a_sum x wf_n x wd_j (sum = a_sum)",
            a_max_component_m=r4(c["a"].max(), 6), sum_a2_m2=r4(np.sum(c["a"] ** 2), 6), sum_a2_DM1A_m2=r4(S.SUMA2_DM1A, 6),
            a_sum_m=r4(S.A_SUM_DM1A, 9), a_sum_rule="= DM1A input sum [chosen]; not enlarged",
            a_sum_energy_match_m=r4(ch["a_sum_energy_match"], 3),
            a_sum_energy_match_note="the a_sum that would give the same input variance as DM1A (sum a^2 = 1.33616 m^2) is 10.64 m; it is NOT used "
                                    "(it would be a 1.68x larger focal sum); branch B2 below stays far below it",
            focus=dict(x_m=L["x_f"], y_m=0.0, t_f_s=t_f1, times_s=[t_f1, t_f1 + P, t_f1 + 2 * P],
                       rule="every component has phase 0 at (x_f, 0) at t = 44 + 28 m s [chosen]; t_f1 = t_full 40.1 s + 3.9 s margin (ramp-spectrum "
                            "smear and half a period of the 5.6 s wave) [computed + chosen]"),
            ramp_s=L["ramp_s"], ramp_rule="half cosine 14 s = 2 Tp (D rule) = 1.5 T of the 9.33 s wave [chosen]",
            k_n=ch["k_n"], kh_n=ch["kh_n"], L_n_m=ch["L_n"], kp=r4(ch["kp"], 6), Lp_m=r4(ch["Lp"], 3), kph=r4(ch["kph"], 4), kp_asum=r4(ch["kp_asum"], 4),
            steep_per_freq_kA_at_focus=ch["steep_per_freq_kA"],
            depth_reason="h 20 m flat [chosen]: kh 1.14 / 1.75 / 2.60 (intermediate to deep: focus-limited, not depth-limited breaking: linear "
                         "Hc/h 0.32, 2nd-order 0.38); the FLIP45 V1 calibration depth (T 7.004 s, h 20 m, dp 0.5); the DFG51 screen found W50/Hc "
                         "within 4.5 % for kh 1.19-3.29, so deeper water would only add particles [computed]",
            why_this_set=dict(
                summary="screen rounds 1-2 at a_sum = DM1A (16 sets, flat 20 m): the X2 direction set with three equal harmonics of P 28 s gives "
                        "the best isolation (N1 0.02, Nt 0.42), the lowest band steepness (side kp*crest 0.29 at 2nd order) and a large focusing "
                        "gain (Hc / largest incoming crest 3.69), at a linear core miss 2.35 (0.22 above the narrowest isolated sets hyb65s25 / "
                        "hyb60s20 / cross60s20 at 2.13, whose side bands reach 0.32-0.33). It is also the plan E X2 set now running at 0.5 m as a "
                        "monochromatic T 7 sea, so X2(0.5 m) is the same-direction control for the frequency band [computed]",
                vs_monochromatic_same_bed=dict(M7_hyb60s28=brief(row(rows, "M7_hyb60s28")),
                                               note="the frequency band lowers N1 0.37 -> 0.02, Nt 0.69 -> 0.42 and the linear miss 2.68 -> 2.35 [computed]"),
                rejected=dict(
                    JONSWAP_weights="Nt 0.77-0.80: the 7 s component dominates, a crest of 0.78 of the focus passes it 7 s before/after [computed]",
                    uniform_80="lin miss 2.97 (wider) [computed]",
                    cross50s12="N1 0.31, Nt 0.70, gain 2.58, lin miss 2.45 [computed]",
                    cross60s15="narrowest (lin miss 2.00) but ring 0.79 and side band 0.36 (G4 limit 0.40) [computed]",
                    P21_234="lin miss 2.11 and 11 % less wall time, but its 5.25 s component (L 43 m) is the most damped at dp 0.5 and its 10.5 s "
                            "component (kh 0.99) reflects most at the sponge [computed + guess]")),
            components_table_note="the exact per-component list is (dir weights) x (freq weights) x a_sum; the flip52 table writer must reproduce "
                                  "sea.directions_deg / dir_weights / freq_weights bit for bit (precheck)"),
        tank=dict(
            kind="half tank, symmetry plane y = 0, flat bed", h0_m=L["h"], Lx_m=L["Lx"], W_m=L["W"], z_bed_m=-L["h"], z_top_m=20.0,
            z_top_reason="2nd-order crest 7.6 m + a jet J 1.6 (12 m) + spray [guess]; air cells cost little",
            water_volume_m3=L["Lx"] * L["W"] * L["h"],
            bed_rule="flat z = -20 m through the g50 bed path (k 0, toe beyond the box) so the bed / volume code is unchanged",
            solver=dict(dp=[1.0, 0.5], gridscale=2.0, cfl=1.0, pcfl=0.75, minsub=1, maxsub=8, veltransfer="flip"),
            bands=dict(
                inlet=dict(x_m=[0.0, L["x_in"]], xg_end=L["x_in"], relax_g=1.0, wall_taper_m=L["wall_taper"], in_gain=1.0,
                           reason="0.45 / 0.69 / 1.03 L of the 9.33 / 7 / 5.6 s waves (FLIP45 V1 used 36 m = 0.5 L at T 7); taper = band/4 (FLIP45 rule)"),
                side=dict(y_m=[L["sd0"], L["W"]], sd0=L["sd0"], sd_gen=L["sd_gen"], sd_sw=L["sd_sw"], sd_sigma=L["sd_sigma"], sd_pow=L["sd_pow"],
                          sd_taper_m=L["sd_taper"], sd_gain=1.0,
                          reason="generating (relaxing to the linear target, which contains the outgoing waves) up to x 180 m = 30 m past the focus, "
                                 "blend to absorbing 180-210 m: a 30 m absorbing band would reflect 0.20-0.45 of the 7-9.33 s waves at 10-40 deg "
                                 "incidence for any sigma (Peric 1D: best sigma 4.5, CR 0.45) [computed]; every incoming ray starts in a "
                                 "generating band (aperture 1.000) [computed]"),
                exit_sponge=dict(abs_on=1, xa0=L["xa0"], length_m=L["Lx"] - L["xa0"], abs_sigma=L["abs_sigma"], abs_pow=L["abs_pow"],
                                 reflection=spg["chosen_exit"],
                                 reason="80 m, sigma 1.0 = min-max of the Peric 1D reflection over T 9.33/7/5.6 s and incidence 0-50 deg (rays below 49 deg "
                                        "reach x 210 m inside |y| < 70 m): CR <= 0.115 (9.33 s normal), <= 0.085 (7 s), <= 0.051 (5.6 s) [computed]; "
                                        "first use of abs_on in a g50-type chain (g50 VEX bands50 already contains it)"),
                ret_on=1, dir_on=1, volume=dict(stage="A (AM-D18)", vol_x_m=[60.0, 205.0])),
            sea_into_tank="table (N-layer complex amplitudes, see implementation) over x 0-214 m, y 0-100 m, 1 m; VEX loops over the three layers",
            interior=dict(x_m=[L["x_in"] + 10.0, L["xa0"] - 5.0], y_abs_max_m=L["sd0"] - 5.0, focal_window_x_m=[90.0, 190.0], focal_window_y_abs_m=60.0),
        ),
        records=dict(
            hf="top-surface height field (1 m) every frame (all metrics, gauges, N1, Nt, c_in, G4)",
            r2="vertical section y 0.5 m every frame (face/back/concavity report; G4 lip)",
            r3="vertical section y 40 m every frame (report)",
            r4="per-y sections x 90-190 m, y 0-65 m, every 3rd frame in [t_fn - 6, t_fn + 4] s (3D crest / curl report)",
            r5="surface meshes every 3rd frame in [t_fn - 6, t_fn + 4] s, 0.5 m only (mp4 for the user)",
            gauges="read from hf: x 60 m, y 0.5 / 15 / 30 / 45 / 60 m (G2f); focus (150, 0.5) and x 190-200 m, y 0.5 / 30 m (report)",
            checkpoints="every 48 frames (resume after the 1740 s launch limit)",
            t_end_s=dict(dp0p5=105.0, dp1p0=90.0)),
        screens=dict(
            tool="Tools/GWWaveGen/flip52/dfg52_screen.py (linear + Sharma-Dean 2nd order, frozen e51 metrics; imports flip51 e51_metrics and "
                 "dfg51_screen read only)", out="Unity/Build/FLIP52/screens/dfg52_screen.json, dfg52_sponge.json",
            rounds="1: 8 sets (P 28 / 21, JONSWAP / equal / mid weights, crossing / hybrid / uniform); 2: 8 more around the hybrid; 3: realization "
                   "models and the two branches (all written before any FLIP52 run exists)",
            all_rows={r["name"]: dict(lin_miss=r["lin"]["miss"], nl2_miss=r["nl2"]["miss"], lin_W50=r["lin"]["W50"], N1=r["nl2"]["N1"]["N1"],
                                      Nt=r4(r["Nt_nl2"], 3), gain=r4(r["gain_over_c_in_nl2"], 3), side_kp_crest=r4(r["bands"]["kp_crest_side_nl2"], 3),
                                      a_sum=r4(r["a_sum"], 4), realization=r.get("realization")) for r in rows},
            chosen=brief(ch), realization_mid=brief(row(rows, "DFG2_real_mid")), realization_low=brief(row(rows, "DFG2_real_low")),
            tags="all [computed]; the realization factors (0.95, 0.88, 0.80) / (0.92, 0.83, 0.68) for n = 3/4/5 are [guess]: FLIP45 r0(dp 0.5) = 0.883 "
                 "inlet realization at T 7 [measured] x propagation damping 3.7-5.5 % per wavelength at L 72 m (V1 N10, S2b as reported) scaled "
                 "by (dx/L)^1 (mid) or ^2 (low)"),
        expected=dict(
            basis="central = the linear screen with the FLIP 0.5 m lateral calibration (V1: W ratios 1.0-1.2 x linear; Hc 0.97-1.10 x the linear "
                  "sum with its own in_gain 1.13, ~0.97 without) and the per-frequency realization models; optimistic = the 2nd-order screen "
                  "(needs FLIP to realise the 2nd-order narrowing, which V1 did not) [computed + guess]",
            Hc_m=dict(central=6.0, range=[5.0, 7.0], optimistic=7.62, jet_ratio_bar=1.30, linear_design_crest=r4(S.A_SUM_DM1A, 4)),
            W50=dict(central=[4.6, 5.5], realization_mid_lin=row(rows, "DFG2_real_mid")["lin"]["W50"], optimistic=[3.0, 3.7], target=[1.5, 2.6]),
            W80=dict(central=[2.7, 3.3], optimistic=[1.8, 2.2], target=[0.8, 1.25]),
            W95=dict(central=[1.35, 1.6], optimistic=[0.86, 1.06], target=[0.4, 0.85]),
            K=dict(central=2.26, target=[2.0, 4.5], note="inside the range in every screen"),
            S2=dict(central=[0.60, 0.70], optimistic=[0.25, 0.43], target=[0.05, 0.35]),
            ring_max=dict(central=[0.74, 0.83], optimistic=[0.55, 0.67]),
            core_miss=dict(central=[2.35, 3.05], central_point=2.8, optimistic=[0.51, 1.33], pessimistic=3.3,
                           compare="DF1A 0.5 m 3.3 [measured]; X2 1.0 m 3.46, X1 1.0 m 2.78 (both G6-invalid) [measured]; X2 / X1 0.5 m pending tonight"),
            N1=dict(central=[0.0, 0.3], screen=0.02, note="the deterministic focused group leaves the surroundings low at the focal instant; FLIP "
                                                           "noise, reflections and band crests may raise it (D single-focus runs 0.17-0.51) [guess]"),
            Nt=dict(central=[0.40, 0.55], screen_lin=0.42, screen_nl2=0.39, focus_point_secondary=0.37,
                    note="the next crest at the focus point 7 s before/after is ~0.37 of the focal crest (1/3 by construction plus bound waves)"),
            gains=dict(Hc_over_c_in_line=[3.0, 3.7], screen=3.69, Hc_over_incoming_r15L=3.30, Hc_over_max_component=[53, 80],
                       Hc_over_amp_per_freq=[2.4, 3.6], E3_min=1.8),
            Lx50=dict(central=[4.3, 6.0], A50=[0.69, 0.77], note="the crest is a ridge along x (crossing lobes: small k_x); weak target 0.8-2.0 / "
                                                                  "0.8-2.5 not met; the frontal picture cannot see it"),
            face=dict(note="crossing fronts are gentle (k_x small): a vertical spout is more likely than a forward curl (as plan E watch items)"),
            band_steepness=dict(inlet_kp_crest_nl2=0.16, side_kp_crest_nl2=0.29, G4_max=0.40),
            recurrence="one focused group at (150, 0) every 28.0 s; between groups the largest crest anywhere in the interior is 0.39-0.42 of it [computed]",
            probabilities_guess=dict(valid=0.65, miss_le_2p8_given_valid=0.45, target_band_le_0p5=0.08, N1_le_0p65_given_valid=0.9,
                                     breaks_at_focus=0.6, tag="[guess]")),
        gates=dict(
            A_validity=dict(
                G1=dict(rule="numpy table check (per layer and total): focus vs an independent sum < 1e-3, phase 0 at the focus at t_f, symmetry, "
                             "continuity per layer < 5e-3 (flat), interpolation < 2 %, vertical profile per layer (own k_n) < 1e-4, zero period-mean "
                             "mass flux per layer with ret_on (< 1e-6 relative), P-periodicity of the target at the gauges; build_check52 all_ok "
                             "(VEX dir_probe vs the numpy mirror <= 1e-5 relative over 3 layers, band/sponge probe, flat bed, saved scene still "
                             "with bands off); cfg precheck ok (table = this plan's set bit for bit)"),
                G2f=dict(rule="inlet amplitude PER FREQUENCY: complex harmonic fit (mean + cos/sin at w3, w4, w5 + the 2nd-order harmonics n 6-10 "
                              "as nuisance terms) of the 3x3-median hf - eta0 at x 60 m, y 0.5/15/30/45/60 m over t 32-88 s (2 P): "
                              "R_n = sum|A_n fit| / sum|A_n linear|, phase error = arg(sum A_n fit conj(A_n linear))",
                         range_0p5={"n3": [0.85, 1.12], "n4": [0.85, 1.12], "n5": [0.80, 1.12]}, phase_max_rad_0p5=0.35,
                         range_1p0={"n3": [0.70, 1.15], "n4": [0.70, 1.15], "n5": [0.60, 1.15]}, phase_max_rad_1p0=0.60,
                         reason="FLIP45 r0(dp 0.5) = 0.883 at T 7 and plan E 0.5 m crest range 0.90-1.12 [measured / frozen]; 5.6 s lower by the "
                                "damping ~ (dx/L)^1-2 [guess]; 0.35 rad = 0.39 s at 7 s (focus time) [computed]; 1.0 m: plan E screens read "
                                "0.72-0.87 at T 7 [measured]"),
                G3P=dict(rule="recurrence every P: the three group summits ('max' instants) spaced 28.0 +- 1.5 s, summit x spread <= 20 m, "
                              "Hc max/min <= 1.25", reason="the forcing is exactly P-periodic; +-1.5 s and 20 m allow breaking jitter (plan E: "
                                                           "20 m; D runs 11.3-12.6 s at T 12) [chosen]"),
                G4=dict(rule="no band breaking: kp x (3x3-median hf - eta0) <= 0.40 over t 30-105 s in the inlet band (x <= 50 m, all y) and the "
                             "generating side band (y >= 70 m, x <= 180 m); no overturning lip on r2 at x < 60 m", kA_max=0.40,
                        predicted="0.16 / 0.29 (2nd order) [computed]"),
                G5=dict(rule="max |V/V0 - 1| of the whole-tank column volume after 1.5 s <= 2 % (stage A, AM-D18)", max=0.02),
                G6=dict(rule="focus where / when designed: each group's 'max' summit at x 110-170 m (x_f - 40 / + 20), |y| <= 10 m, "
                             "t in [t_fn - 3, t_fn + 2] s, Hc >= 4.1 m (0.68 x central 6.0)",
                        reason="V1 peaked 30 m (0.42 L) upstream of its linear focus [measured]; 0.68 = plan E floor rule"),
                also="run complete (f_end reached), 3 groups",
                failure_class="pipeline = run incomplete, G1, G2f (fix and rerun once, same setup name); physics = G3P, G4, G5, G6 (ends this setup)"),
            B_eligibility=dict(
                E1=dict(rule="isolation N1 (plan E definition: highest local max of the 15 m max-filtered mirrored 3x3-median hf - eta0 at the "
                             "'max' instant, x 60-205 m, |y| <= 65 m, r <= 100 m, outside r < 4 Hc of the summit and of its mirror, / Hc), "
                             "median over the groups <= 0.65", max=0.65, reason="plan E E1 (calibrated on DA3/DM1A/DF1A/DG1)"),
                E1t=dict(rule="temporal isolation Nt: largest Hc_scan (interior) in [t_fn - 14, t_fn + 14) at |t - t_max| >= 3.5 s / Hc, "
                              "median over the groups <= 0.75", max=0.75,
                         reason="screen 0.39-0.43; a monochromatic hot spot is 1.0 by construction and the same-bed X2 monochromatic set 0.65-0.69 "
                                "[computed]: >= 0.75 means the group does not stand out in time"),
                E2=dict(rule="median Hc >= 5.0 m", min=5.0, reason="plan E 0.5 m value"),
                E3=dict(rule="focusing gain: median Hc / median largest crest on the line x 60 m (|y| <= 65 m) in the group window >= 1.8", min=1.8,
                        reason="plan E E3 (DM1A c0/c_in 1.97)"),
                reports="Hc / 6.331 m (jet ratio), Hc / max a_nj (0.0947 m), Hc / per-frequency amplitude (2.110 m), W(f), taper, S1, ring, "
                        "Lx50, A50, face/concavity/overhang/back (r2), onsets (g50 events), per-frequency focal amplitudes (harmonic fit, report)"),
            analysis=dict(
                eta0="the run's online still offset (info.still_offset_online)",
                instants="per group n = 1-3 (t_fn 44 / 72 / 100 s): 'max' = largest Hc of the 3x3-median hf - eta0 over x 90-190 m, |y| <= 60 m "
                         "in [t_fn - 6, t_fn + 4] s; if a g50 overturning onset falls in that window, the e51 'max' of that onset instead (plan E D rule)",
                metrics="e51 hf_metrics (frozen ruler sha 91a2f041..., xwin 90-190 m, rows y > 65 m NaN) and score_vs_target over the core "
                        "(W50, W80, W95, K, S2); medians over the three groups",
                tool="to be written: Tools/GWWaveGen/flip52/g52_ana.py (imports e51_metrics and x51_ana.n1_isolation logic read only)"),
        ),
        smoke_1p0=dict(
            role="PIPELINE CHECK ONLY: not shape-judged (1.0 m damps the 5.6 s and 7 s components: plan E 1.0 m screens read Hc 0.58-0.67 of the "
                 "linear design crest, 21-47 m upstream of the design focus [measured])",
            run_id="S52DFG2_flat20_P28_dp1p0", t_end_s=90.0,
            pass_rule="run complete; G1; G2f at the 1.0 m ranges; G4; G5; a summit in each of the groups 1-2 within x 90-190 m and +-4 s of t_fn, "
                      "spaced 28 +- 2 s; the exit sponge works (the mean level and the per-frequency field at x 190-200 m show no growing standing "
                      "pattern: report)",
            on_fail="pipeline cause -> fix, smoke once more; the 0.5 m run starts only after a passing smoke"),
        decision_after_first_0p5=dict(
            frozen_before_any_FLIP52_run=True,
            bar="NEW_BEST bar = min(2.8, best valid 0.5 m median core miss - 0.5) where 'best valid 0.5 m' is the lowest of DF1A 3.3 and the "
                "plan E round-E2 X2 / X1 results that pass plan E's D_judgement validity",
            steps=[
                "1 validity (A): pipeline failure -> fix and rerun once; physics failure -> report numbers to the user, DFG-2 stops; next = user's "
                "choice (Froude-scaled best set, or stop)",
                "2 eligibility (B): E1 N1 <= 0.65, E1t Nt <= 0.75, E2 Hc >= 5.0 m, E3 gain >= 1.8",
                "3 outcomes (valid and eligible): NEW_BEST_SHAPE if median miss <= bar (mp4, shown to the user with gains over the incoming crest, "
                "each frequency and each component; becomes the shape reference); TARGET_BAND if miss <= 0.5; JET_REGIME_SEEN if Hc / 6.331 m >= 1.30 "
                "in >= 2 groups (refine within DFG-2: lobe angle)",
                "4 one follow-up run at most before reporting, chosen in this order: "
                "B2 STEEPER if valid and NO overturning onset at the focus in >= 2 of 3 groups (r2/r4 lip within x 90-190 m, [t_fn - 4, t_fn + 3]) "
                "-> the same set at a_sum 7.10 m (kp a_sum 0.62; x1.12 the DM1A sum; sum a^2 = 0.45 x DM1A, still 0.67 of the energy-matched "
                "sum 10.64 m) tagged 'a_sum enlarged x1.12, justified by an input variance below DM1A'; screen lin miss 1.85, nl2 0.20, "
                "realization-mid 2.51; "
                "B1 NARROWER if valid, eligible, breaking, miss > bar and N1 <= 0.40 -> lobes 65 deg / sigma 25 (one change; screen lin miss 2.13, "
                "realization-mid 2.76, N1 0.02-0.04, side band 0.32); "
                "NO_GAIN otherwise (miss > 2.8 with breaking and N1 > 0.40, or E1t fails) -> stop DFG-2 and report honestly",
                "5 numbers stay frozen; any change is an amendment (Unity/Build/FLIP52/plan/amendments.jsonl) registered before the next run"],
            branch_screens=dict(B2=brief(row(rows, "DFG2_k62")), B2_realization_mid=brief(row(rows, "DFG2_k62_real_mid")),
                                B1_realization_mid=brief(row(rows, "DFG2n_hyb65s25_real_mid")))),
        cost=cost(L),
        order=["implement the flip52 code below and its numpy checks (no Houdini)",
               "build the hip ONLY when no hython runs (after round E2 ends, ~00:00 or later): build_command",
               "1.0 m smoke (pipeline only)", "0.5 m run (one simulation at a time)", "g52_ana + mp4 + decision (decision_after_first_0p5)"],
        implementation=dict(
            status="NOT written yet (this freeze writes only the screen and the plan); all new files under Tools/GWWaveGen/flip52 and Houdini/FLIP52; "
                   "flip45-flip51 modules imported read only, never edited",
            files=dict(
                g52_common="constants of this plan (tank, bands, sea, paths Build/FLIP52, Houdini/FLIP52/g52_tank.hiplc, CTRL node /obj/G52_SETUP/CTRL)",
                g52_table="N-layer table writer: per layer n the complex surface fields er_n, ei_n, ur_n, ui_n, vr_n, vi_n and kk_n (own k_n), "
                          "shared hh, the summed return current mx, my = -sum_n Re(A_n conj(Q_n)) / (2 h^2) (cross-frequency terms vanish over P), "
                          "npz info with omega_n, P, t_f, the set; numpy mirror dirwave_np (eta_t = sum_n g(er_n c_n + ei_n s_n); Wheeler "
                          "stretching with the total eta_t; U = sum_n g(ur_n c_n + ui_n s_n) cosh(k_n(z' + h))/cosh(k_n h) + ret_on g^2 mx); "
                          "checks = G1",
                g52_tanklib="VEX: the g50 head (read only) with dirwave replaced by a fixed loop over d_nlayer <= 4 layers (field names er0..er3 ...), "
                            "bands50 unchanged (abs_on exit sponge used), node paths G52_",
                g52_build_tank="hython builder adapted from g50_build_tank (flat bed, Lx 290, W 100, zb -20, top +20) -> Houdini/FLIP52/g52_tank.hiplc "
                               "+ Unity/Build/FLIP52/_logs/build_check52.json (dir_probe over 3 layers vs g52_table.dirwave_np)",
                x52_build="py -3.10 launcher: writes the table, waits for no hython, runs hython g52_build_tank.py",
                g52_run_chain="copies of g50_run / g50_chain with HIP = Houdini/FLIP52/g52_tank.hiplc and the FLIP52 build_check / plan sha gates",
                g52_pcfg="cfgs S52DFG2_flat20_P28_dp1p0 (smoke) and DFG2_flat20_P28_dp0p5 (run) + precheck (table = plan set, cost, records)",
                g52_ana="per-group analysis, gates, eligibility, decision (this plan)", g52_video="mp4 per run (user rule: video per experiment)"),
            build_command=('py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52/x52_build.py   '
                           '(runs "%s" G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52/g52_build_tank.py after waiting for no hython; '
                           'writes Houdini/FLIP52/g52_tank.hiplc and Unity/Build/FLIP52/_logs/build_check52.json)' % HY),
            build_now=False, build_rule="NOT run in this step: round E2 (X2, X1 at dp 0.5) is using hython until ~00:00",
            engineering_h="5-9 h (campaign E judge) [guess]"),
        honesty=dict(
            chosen_at_inlet="P 28 s, n 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 6.331240 m (= DM1A), "
                            "focus (150, 0) at t = 44 + 28 m s, the flat 20 m bed and the band / sponge layout",
            computed_by_FLIP="propagation, dispersion, focusing, the crest's growth, breaking, any jet / plume",
            gains_reported="Hc / largest crest on the line x 60 m (E3), Hc / the r >= 1.5 L incoming crest, Hc / each frequency's amplitude, Hc / max a_nj, "
                           "Hc / linear design crest",
            input_energy="the DFG-2 input variance is 0.354 x DM1A's: the height comes from focusing 102 small components (max 0.095 m), not "
                         "from a bigger sea",
            not_done="no input enlargement in the first run, no force toward a shape, no wind or current; the target picture only through e51; "
                     "nothing committed; README / Docs not edited; no Houdini started; no file of the running round E2 touched"),
        risks=[
            "2nd-order narrowing (the only route into the target band) did not appear in FLIP at 0.5 m in V1 [measured]: central miss 2.35-3.05",
            "the 5.6 s component (L 48 m) loses 11-23 % on its 100-120 m path at dp 0.5 [guess from (dx/L)^1-2 scaling]: Hc and the width "
            "benefit shrink (realization-low: lin miss 3.32)",
            "new N-layer table + VEX loop + the first abs_on sponge in a g50-type chain: G1 / G2f / smoke catch them; reflections 5-12 % per "
            "frequency (Peric 1D) [computed] are P-periodic and so part of the steady pattern",
            "the side band blend 180-210 m reflects more than the generating part [computed 1D]; N1 / Nt may rise above the screen values",
            "crossing fronts are gentle: a vertical spout rather than a forward curl; the crest is a ridge along x (A50 0.7)",
            "no breaking at a_sum = DM1A is possible (crossing seas break later): branch B2 is frozen for it",
            "the e51 windows are in absolute metres (crest window 0.56 L at 72 m), as for plan E"],
        metrics_ruler=dict(e51="Tools/GWWaveGen/flip51/e51_metrics.py", e51_sha256=sha(REPO + "/Tools/GWWaveGen/flip51/e51_metrics.py"),
                           target_frozen="Unity/Build/FLIP51/target/target_frozen.json",
                           target_frozen_sha256=sha(REPO + "/Unity/Build/FLIP51/target/target_frozen.json"),
                           baseline="Unity/Build/FLIP51/target/baseline.json", baseline_sha256=sha(REPO + "/Unity/Build/FLIP51/target/baseline.json")),
        code_sha256={"Tools/GWWaveGen/flip52/dfg52_screen.py": sha(HERE + "/dfg52_screen.py"),
                     "Tools/GWWaveGen/flip52/dfg52_plan.py": sha(HERE + "/dfg52_plan.py"),
                     "Tools/GWWaveGen/flip51/dfg51_screen.py (read only)": sha(REPO + "/Tools/GWWaveGen/flip51/dfg51_screen.py")},
        inputs_sha256={"Unity/Build/FLIP52/screens/dfg52_screen.json": sha(SCREEN), "Unity/Build/FLIP52/screens/dfg52_sponge.json": sha(SPONGE),
                       "Unity/Build/FLIP51/plan/plan_E_frozen.json (read only)": sha(REPO + "/Unity/Build/FLIP51/plan/plan_E_frozen.json")},
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return plan


def freeze(force=False):
    if os.path.exists(PLAN) and not force:
        raise SystemExit("%s exists (frozen); use an amendment instead" % PLAN)
    p = build()
    os.makedirs(os.path.dirname(PLAN), exist_ok=True)
    with open(PLAN, "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=1, ensure_ascii=False, default=float)
    h = sha(PLAN)
    with open(PLAN + ".sha256", "w", encoding="utf-8") as fh:
        fh.write("%s  %s\n" % (h, os.path.basename(PLAN)))
    print("frozen", PLAN, h)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "freeze":
        freeze("--force" in a)
    elif a and a[0] == "show":
        print(json.dumps(build(), indent=1, ensure_ascii=False, default=float)[:6000])
    else:
        print(__doc__)
