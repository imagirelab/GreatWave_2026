# -*- coding: utf-8 -*-
"""FLIP50 option D: builds plan_D_draft.json (DRAFT, not frozen; nothing is run). py -3.10 -I. 2026-10-15, Claude.
Criteria are copied unchanged from Unity/Build/FLIP49/plan/plan_A_frozen.json (read only); only the x limits move with the D layout.
Numbers come from screen/s50_final.json (s50_final.py), screen/s50_linear*.json (s50_linear.py) and screen/u50_*.json (u50_dir.py).
"""
import os, sys, json, copy, time, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:/Unity/GreatWave_2026_Fresh"
PLAN_A = REPO + "/Unity/Build/FLIP49/plan/plan_A_frozen.json"
SCR = os.path.join(HERE, "screen")


def sha(p, n=16):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:n]


def main():
    A = json.load(open(PLAN_A, encoding="utf-8"))
    F = json.load(open(os.path.join(SCR, "s50_final.json"), encoding="utf-8"))
    M = F["configs"]["DM1_T12"]; B = F["configs"]["DF1_T10"]
    X_P1 = 330.0          # h 2.0 m on the 1:10 beach, 20 m before the shoreline (FLIP48 targets48 P1 sat at the shelf edge, h ~2 m)
    X_SIDE = 330.0
    L_main = M["wave"]["L_h0"]; L_fb = B["wave"]["L_h0"]
    # main: 4th judged window extrapolated by one period from the screen (U3 ran to 90 s, 3 judged onsets)
    on_m = list(M["time"]["judged_onsets_screen"])
    while on_m[-1] + 12.0 + 6.0 <= M["time"]["t_end_s"]:
        on_m.append(round(on_m[-1] + 12.0, 2))
    win_m = [[round(t - 3.0, 2), round(t + 4.0, 2)] for t in on_m]
    crit = copy.deepcopy(A["criteria"])
    crit["source"] = ("P1-P5 thresholds, PERIODIC and health copied unchanged from Unity/Build/FLIP49/plan/plan_A_frozen.json (sha256 %s); "
                      "only the x limits and the crest window wavelength move with the D layout; none loosened" % sha(PLAN_A, 64))
    pb = crit["per_breaker"]
    pb["P1"]["x_max_m"] = X_P1
    pb["P1"]["text"] = "the y 0.5 m row reaches a vertical tangent inside window k at x <= 330 m (h >= 2.0 m on the 1:10 beach, 20 m before the shoreline x 350.25)"
    pb["P4a"]["x_side_max_m"] = X_SIDE
    pb["P4a"]["text"] = ("c(0) / mean crest of |y| 70-84 m (x <= 330 m) >= 1.5; >= 2.0 reported as 'clearly focused'. In D this band lies in the "
                         "shadow of the converging sea (screen c_side 0.03-1.6 m), so P4a passes almost by construction: P4b and c0/c_in carry the narrowing")
    crit["definitions"]["crest_profile"] = ("c(y) = per-row maximum of the 3-cell x-median of eta_top over x in [max(150, xc0 - L/2), min(330, xc0 + L/2)], "
                                            "xc0 = centre-row crest x found over [150, 330] in the same frame, L = %.1f m (T 12 s, linear, h 19 m; fallback "
                                            "T 10 s: %.1f m) [chosen; g49_periodic_ana.crest_window with cfg sf.L]" % (L_main, L_fb))
    crit["periodic_D"] = crit.pop("periodic_A")
    crit["periodic_D"]["open_item"] = "none: D is designed for P5 as well (straight 1:10 break slope); P2/P3 widths are the predicted weak point"
    crit["report_only"]["items"] = crit["report_only"]["items"] + [
        "generation: H / H_lin (linear directional target, s50_final gauges) at x 110/128/160, y 0.5/20/40/60/80 m, last 3 periods",
        "focus gain c0 / c_in, c_in = lateral mean (|y| <= 95 m) of the incident crest at x 128 m",
        "period-mean mass-transport velocity (rip cell): centre surf, |y| 20-40, |y| 60-84, offshore centre/side (as u50_dir)",
        "onset x and Hc against the registered linear and U3 predictions"]
    crit["health"]["diagnose_first"] = ["centre onset on the flat (x < 160.25 m) or at h_b > 14 m (offshore steepness breaking of the focused crest)",
                                        "swash set-up > 3 m (period mean of the swash region)",
                                        "generation at x 160 m, |y| <= 40 m outside 0.80-1.20 of the linear target (band failure)",
                                        "volume or leak failure"]
    crit["health"]["volume_rule"] = "stage C: period-mean interior volume over x 110-400 m (beach included)"
    plan = dict(
        status="DRAFT (not frozen). Prepared while DA1 runs; to be frozen by the orchestrator before T0D (sha256 + build check), as plan_A_frozen.json was",
        made_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50/g50_plan.py",
        campaign="PER50-D", parent_plan=dict(path="Unity/Build/FLIP49/plan/plan_A_frozen.json", sha256=sha(PLAN_A, 64), note="read only"),
        trigger="plan_A_frozen.json decision_rules.after_DA1 STOP RULE: P4a < 1.3 on all judged breakers -> option D; also the 'partial' branch shows D to the user",
        supervisor_Q52=A["supervisor_Q52"],
        idea=("narrowing from the INCOMING wave (a monochromatic directional sea whose components are phase-locked on one point) and breaking on a "
              "laterally straight 1:10 slope (FLIP47 S2/P1c section): focusing and breaking are separated (C3B rule) and no seabed feature feeds water "
              "sideways onto the axis (R4: 91-99 % of the water ahead of the centre came from the sides)"),
        physics_answers=dict(
            Q1_periodic=("all components share omega, so A(x,y) = sum A_j exp(i(Phi_j + ky_j y)) is time independent: the focus is a fixed hot spot and "
                         "a crest passes it once per period (eta = Re(A e^{-i omega (t - t_f)})). Screens: U3 onset intervals 11.25-12.62 s (T 12), "
                         "9.5-10.4 s (T 10) [computed]. Focus placed 20 m seaward of the linear break point (x_f 220.25 m, h 13 m; break target "
                         "h 11 m at x 240.25 m) because a slightly diverging crest (centre leading) delays the side rows [computed, s50_linear sweep]"),
            Q2_spread_period_amplitude=("lateral wavenumbers are bounded by k(h0) (k_y <= k(19 m) = 0.0421 rad/m at T 12, 0.0528 at T 10): the "
                                        "narrowest possible linear crest is set by the period, not by the bed. Theta_max 80 deg, 30 equal components, "
                                        "a_sum 6.33 m (T 12) / 6.50 m (T 10) give a focal crest of about 9.5 m at h_b 11 m (linear rule from P1c; U3 c0 "
                                        "9.5-10.4 m at T 12, 8.9-9.3 m at T 10) [computed]. Curl-width proxies: T 12 linear 1.6/3.0/4.3 Hc, U3 1.9-2.5/"
                                        "1.9-4.2/3.5-5.5 Hc; T 10 linear 1.2/2.3/3.2 Hc, U3 1.3-1.8/2.2-2.7/3.1-4.0 Hc (onset/overturn/touchdown proxies "
                                        "at +0.25/+0.75/+1.5 s; thresholds 2.0/2.5/3.0) [computed, proxies uncalibrated]. Half tank: W 85 cannot generate it "
                                        "(no side band: H 0.38-0.65 of target, no focus; 15 m band: 0.21-0.89, c0 5.2 m); W 120/35 m band works but the focus "
                                        "widens over periods (w90 26 -> 38 m); W 140-150 with 45-50 m bands holds w90 26 m and H/H_lin 0.85-1.09 [computed, U3]"),
            Q3_shoaling=("a y-uniform slope conserves k_y, so the lateral pattern is kept, not narrowed; refraction lowers the oblique components "
                         "(Kr = sqrt(cos th0 / cos th) < 1) and lengthens the focal zone in x. Linear widths at the break equal the flat-bottom "
                         "values within the proxy resolution; nonlinear (U3) widths are wider than linear and widen with time where the rip cell "
                         "develops (onshore mass transport ~0.5 m/s at the centre offshore of the break, up to -0.6 m/s rips at |y| 60-84 m) [computed]"),
            Q4_honesty=("a converging directional sea at a coastal point is real (refraction by offshore canyons/shoals acting as a lens, e.g. "
                        "Nazare; crossing swells), but here the converging field is imposed at the inlet and side bands as a coherent, monochromatic "
                        "+-80 deg fan whose phases are CHOSEN so that every crest focuses at (220.25 m, 0) at t = nT. Where and when the focus happens "
                        "is set by that choice; shoaling, refraction on the slope, nonlinear focusing, breaking, set-up and currents are computed. "
                        "A natural lens gives a caustic of finite coherence, not a perfect point focus")),
        design=dict(
            summary="half tank W 140 m (side band 45 m), h0 19 m flat to x 160.25 m, then a laterally straight 1:10 slope through the still level to a +6.2 m beach (x 412 m); directional monochromatic inflow T 12 s, +-80 deg, 30 components, focus (220.25, 0), dp 0.5, stage C, 92 s",
            domain=dict(Lx_m=412.0, W_m=140.0, z_m=[-21.0, 17.0], floor_pad_m=2.0, particle_m=0.5, grid_m=1.0, veltransfer="flip",
                        symmetry="half tank: symmetry plane y = 0; the side band (y 95-140 m) supplies the far field of the converging sea for x <= 180.25 m, so the model is an isolated focus (not a periodic row); beyond |y| 140 m nothing is computed",
                        layout_m=dict(inlet_band=[0.0, 100.0], free_flat=[100.0, 160.25], gauges_x=[110.0, 128.0, 160.0], gauges_y=[0.5, 20.0, 40.0, 60.0, 80.0],
                                      slope_toe=160.25, focus_x=220.25, break_target_x=240.25, shoreline=350.25, beach_top=[412.0, 6.175],
                                      side_band_y=[95.0, 140.0], side_generate_x=[0.0, 180.25], side_blend_x=[180.25, 210.25], side_absorb_x=[210.25, 412.0],
                                      P1_x_max=X_P1, interior_y=[0.0, 95.0]),
                        particles_computed=F["particles"]),
            bed=dict(name="D19B", kind="laterally straight 1:10 beach (FLIP47 S2/P1c depth and slope; the shelf replaced by the P1c beach)",
                     formula="z_b = -(19 - max(x - 160.25, 0)/10) (no floor: through the still level at x 350.25 to +6.175 m at x 412)",
                     spec_flip48_plain=dict(k=0.0, x_toe=160.25, s=10.0, h0=19.0, on=True, shelf_h=0.0),
                     why=["S2/P1c is the only 2D section that reached the print band (S2 chord 84-91 deg solitary; P1c 62.9-68 deg periodic)",
                          "a beach drains by swash and rip circulation; the U3 shelf+lagoon variant pumped water over the reef (centre mass transport 1.2-1.9 m/s), lowered the offshore level by 0.39 m and widened the focus (P3 proxy 5-9 Hc) [computed]",
                          "h0 19 m (not 17 m) keeps the focused crest on the flat at H/Hmax2D 0.84 (P1c 0.83, did not break offshore); at h0 17 m it is 1.00 [computed]"],
                     honesty="resembles a steep straight coast; not a measured site"),
            inflow=dict(kind="linear directional monochromatic sea (Airy components, WKB on the slope), complex-amplitude table",
                        main=M["wave"], fallback=B["wave"],
                        table=dict(tool="g50_dirfield.DirField(T, theta_j, w_j, a_sum, x, bed, x_f).complex_amp / complex_vel(depth_avg=False, z)",
                                   grid="x 0-212 m, y 0-140 m, 1 m; fields eta_re/im and U_l, V_l re/im at stretched levels z' = 0, -4, -8, -12, -16, -19 m (clipped at -h); one period is enough (time enters as Re(F e^{-i omega t}))",
                                   vex="target = R(t) E_wall(x) band_factor (F_re cos(omega t) + F_im sin(omega t)); levels interpolated in z' = h (z - eta)/(h + eta) as FLIP45; horizontal velocity only",
                                   gains="in_gain = sd_gain = 1.0 [chosen; FLIP49 100 m inlet band measured -2.1 % for T 12 s]; checked, not tuned, by SMOKE_D and DM1 generation report"),
                        drift="stage C as plan A: du_abs = -sqrt(g/h0)(mean_T(eta at x 100-110) - reading at 1.0-1.5 s) added to the inlet target u x walltaper"),
            bands=dict(inlet=dict(x=[0.0, 100.0], weight="relaxw(chi) = (e^{chi^3.5} - 1)/(e - 1), 1 - (1 - w)^(dt/dt0)", wall_taper_m=20.0,
                                  relaxes="vel.x and vel.z (horizontal) to the table target; never vel.y (vertical) nor the surface"),
                       side=dict(y=[95.0, 140.0], generate_x_max=180.25, blend_x=[180.25, 210.25], absorb="1 - exp(-sigma chi^2 dt), sigma 1.41 /s, target 0",
                                 rule="FLIP45 g45_tanklib bands(): weight max, target factors multiplied in the corner", reflection="not computed (only the U3 generation ratios)"),
                       exit="none (beach)"),
            time_and_records=dict(main=dict(t_end_s=92.0, frames=2209, ramp_s=24.0, judged_onsets_screen=on_m, windows=win_m, judged_expected=len(win_m)),
                                  fallback=dict(t_end_s=86.0, frames=2065, ramp_s=20.0, judged_onsets_screen=B["time"]["judged_onsets_screen"], windows=B["time"]["windows"]),
                                  light="r2/r3 every frame as FLIP49", heavy="r4 per-y sections x (200, 300) m, y 0-95 m and r5 surfaces in the windows, every 2nd frame",
                                  gauges="eta at x 110/128/160 m x y 0.5/20/40/60/80 m every frame"),
            level_regions=[["band_core", 20.0, 95.0, 0.0, 95.0], ["probe_c", 100.0, 110.0, 0.0, 95.0], ["flat", 110.0, 160.0, 0.0, 95.0],
                           ["window", 110.0, 400.0, 0.0, 95.0], ["break_front", 225.0, 255.0, 0.0, 10.0], ["inner_surf", 290.0, 330.0, 0.0, 10.0],
                           ["swash", 330.0, 360.0, 0.0, 10.0], ["side_surf", 290.0, 330.0, 60.0, 84.0], ["asym_centre", 110.0, 160.0, 0.0, 10.0],
                           ["asym_side", 110.0, 160.0, 75.0, 95.0]],
            cost=dict(particles_dp0p5=F["particles"]["dp0p5"], coef_s_per_Mparticle_frame=[0.486, 0.575], growth=[1.16, 1.3], heavy_s_per_frame=1.8,
                      main_total_h=[round(M["time"]["total_h"][0] + 85 * 1.8 / 3600, 2), round(M["time"]["total_h"][1] + 85 * 1.8 / 3600, 2)],
                      main_total_h_DA1_launch1_rate=[round(v + 85 * 1.8 / 3600, 2) for v in M["time"]["total_h_DA1_rate"]],
                      fallback_total_h=[round(v, 2) for v in B["time"]["total_h"]], fallback_total_h_DA1_launch1_rate=[round(v, 2) for v in B["time"]["total_h_DA1_rate"]],
                      launches="5-6 of <= 29 min (main)", DA1_rate=F["da1_rate"],
                      memory_estimate_gb="about 8 (C3 6.77 GB at 4.91 M; DA1 launch 1 RSS 6.03 GB at 5.68 M) [computed estimate]",
                      W150_option="W 150 m / 50 m band (U3 slightly better generation) adds ~7 % particles -> main upper 2.8 h: not chosen")),
        criteria=crit,
        decision_rules=dict(
            before_DM1=["T0D numpy + build checks (table = VEX probe, bed VEX = numpy, particle count, side band layout) all pass, else fix code",
                        "S2D (optional, recommended, ~2 x 10-13 min): 2D strips on the D19B axis with the FLIP49 Fenton inlet at h0 19 m, H = 0.83 Hmax2D (10.6 m at T 12, 9.9 m at T 10): chord/lip/hood per breaker; if T 12 spills (chord < 55 deg on >= 2 breakers) and T 10 does too, D is unlikely to give P5: show the user before DM1",
                        "SMOKE_D (dp 1.0, 0-36 s, 1 launch, never judged): pipeline, leak, the directional pattern at x 160 m (correlation with the linear target >= 0.9 over |y| <= 95 m)"],
            after_DM1=["health failure (onset on the flat or h_b > 14 m, swash set-up > 3 m, generation outside 0.80-1.20, volume/leak) -> diagnose first",
                       "PERIODIC + P1-P5 on >= 3 consecutive -> 'full'; DD3 continuation (+48 s) and a seamless 12 s loop",
                       "P5 passes (chord >= 55 deg, lip >= 0.2, hood >= 0.10) on >= 2 judged breakers but P2 or P3 width fails on >= 2 -> DF1 = T 10 s (one change: period; a_sum by the same linear rule; ramp 20 s; t_end 86 s)",
                       "P5 fails with chord < 55 deg on >= 2 judged breakers -> stop and show the user (the straight-slope section did not survive in 3D; T 10 s would spill more)",
                       "P4b < 1.3 on all judged breakers -> D negative (no narrowing); stop and show",
                       "otherwise 'partial', breaker by breaker; stop and show"],
            after_DF1=["moved the way the rule says (narrower, P5 kept): keep and re-evaluate", "P5 lost: revert to DM1 as the D result, record the negative"],
            limits=["one change per run", "at most 2 follow-up runs in D, then stop and show the user", "never loosen a frozen threshold after seeing results",
                    "one simulation at a time"]),
        registered_screen_predictions=dict(
            tag="computed, screening only; for comparison after the run, never for judging",
            linear=dict(main=M["linear"], fallback=B["linear"], tool="s50_linear.py (WKB, gamma_b 1.081 from P1c)"),
            u3=dict(main=M["u3"], fallback=B["u3"], tool="u50_dir.py (U3 depth-averaged Boussinesq/NSW, directional bands, no overturning)"),
            caveats=["on PG12s the U3 model overshot centre/side by 0.6-0.9 against FLIP D0 (plan A)",
                     "U3 at T 10 s needed +15 % amplitude to break at h 11 m (E10 cases); FLIP onset x is uncertain by about +-25 m",
                     "width proxies (+0.25/+0.75/+1.5 s after centre onset) are not calibrated against FLIP curl widths"],
            files={os.path.basename(p): sha(p) for p in sorted(os.path.join(SCR, f) for f in os.listdir(SCR) if f.endswith(".json"))}),
        honesty=dict(
            forces="only gravity, the bed and the incoming waves act; the inlet and side bands relax horizontal velocity only (never the surface, never the vertical velocity); nothing pulls water toward a shape",
            chosen=["option D itself; the converging directional sea (+-80 deg, 30 equal components) and its focus point (220.25 m, 0) and phase (t_f = 0)",
                    "T 12 s (main) / 10 s (fallback); a_sum by the linear P1c rule (h_b 11 m)", "h0 19 m, 1:10 beach, toe x 160.25 m",
                    "W 140 m with a 45 m side band generating to x 180.25 m", "dp 0.5, t_end 92 s, judged t >= 45 s, stage C, windows",
                    "P1/P4a x limit 330 m and the crest-window wavelength"],
            computed=["shoaling, refraction, nonlinear focusing, break location and time, section shape, curl width, set-up, rip circulation",
                      "particle counts and run-time estimates", "linear and U3 screens (rank only)"],
            measured=["FLIP47 P1c onsets (gamma_b calibration)", "FLIP48 rates", "DA1 launch-1 rate", "FLIP45 V1 crest width (directional focusing works in FLIP)"],
            guesses=["the 3D kinematic factor (<cos>) raising the breaking limit of a spread crest", "FLIP onset within +-25 m of x 240 m"],
            not_predicted="P5 (section shape) in 3D"),
        runs=[dict(id="SD", status="done", what="numpy screens s50_linear (sweep, refine, depth19), u50_dir (13 directional U3 runs, 67-114 s CPU each)"),
              dict(id="T0D", what="code + numpy + hip build checks for the new flip50 tank (directional table, side band, D19B bed)"),
              dict(id="FREEZE_D", what="freeze this file (sha256), after T0D"),
              dict(id="S2D", status="optional, recommended", what="2D strips T 12 / T 10 on the D19B axis (~10-13 min each)"),
              dict(id="SMOKE_D", what="3D smoke dp 1.0, 0-36 s, 1 launch, never judged"),
              dict(id="DM1", what="main coarse periodic 3D run, dp 0.5, T 12 s, 92 s, chained launches <= 29 min, est. 2.04-2.65 h (FLIP48 coef) / 1.42-1.77 h (DA1 launch-1 rate)"),
              dict(id="ANA_D", what="g49_periodic_ana with the D analysis block (side_band_m [70, 84], crest_x_min_m 150, p1_x_max_m 330, crest_window centre_half_L with sf.L 149.2) + D report-only items"),
              dict(id="VID_D", what="g49_video2 compare + whole-run mp4"),
              dict(id="DF1", status="conditional", what="T 10 s by the frozen rule, 86 s, est. 1.91-2.48 h"),
              dict(id="DD3", status="conditional", what="+48 s continuation if PERIODIC passes; seamless 12 s loop")],
        implementation=dict(
            new_files_flip50=["g50_dirfield.py (done: linear directional field, WKB, complex amplitudes, aperture)",
                              "g50_table.py (to write: complex-amplitude table npz/bgeo from g50_dirfield at the z' levels)",
                              "g50_tanklib.py (to write: FLIP49 tank VEX copied; relax_apply replaced by FLIP45-style inlet+side bands reading the complex table)",
                              "g50_build_tank.py / x50_build.py (to write: hip build + checks; bed through the FLIP48 plain path k 0, shelf_h 0)",
                              "g50_pcfg.py (to write: cfg, precheck for h0 19 m / W 140 / beach, freeze)",
                              "g50_run.py / g50_chain.py (thin wrappers over flip49 run/chain if their cfg keys suffice)"],
            reuse_read_only=["flip49 g49_run/g49_chain/g49_periodic_ana/g49_video2 (cfg analysis block)", "flip48 g48_common.bed_z plain path", "flip47 g47_sfwave (S2D strips at h0 19 m)", "flip45 g45_tanklib bands() logic (copied, not imported)"],
            estimate="about half a day of code + checks (as in the plan)"),
        risks=[
            "width is bounded by physics: k_y <= k(h0); predicted P2 borderline and P3 failing at T 12 (linear 1.6/3.0/4.3 Hc, U3 1.9-2.5/1.9-4.2/3.5-5.5 Hc); T 10 narrower but touchdown still > 3 Hc in U3",
            "offshore steepness breaking of the focused crest on the 19 m flat: H/Hmax2D 0.84-0.85 at the toe (P1c 0.83 did not break); at h0 17 m it would be 1.0",
            "breaker type: deep-water Iribarren xi0 0.44 (T 12), 0.36 (T 10) against 0.52 for P1c: closer to spilling; P5 unproven in 3D (S2D strips can check the 2D analogue)",
            "nonlinear focusing and the self-made rip cell (onshore mass transport at the centre, rips at the sides) widen and shift the focus over periods (U3 W120 w90 26 -> 38 m; W140 stable)",
            "side-band generation of the 60-80 deg components (45 m band = 0.30 L at T 12): U3 H/H_lin 0.85-0.88 at |y| 60-80 m; per-depth FLIP relaxation and dp 0.5 damping (FLIP49 -4.8 % per 50 m) untested for this field",
            "linear (Airy) target with Ursell ~25 at the band edge: spurious free harmonics (stationary in space, so periodicity is kept)",
            "P4a is almost automatic in D (shadowed |y| 70-84 m band); P4b, c0/c_in and the curl widths carry the narrowing claim",
            "break location calibration: U3 and linear disagree by up to 25-50 m for T 10 s; FLIP may break between x 230 and 265 m",
            "closed-tank drift after ~100 s (FLIP47 P1c); stage C fix; run ends at 92 s",
            "new code path: directional complex-table VEX, side band, h0 19 m, beach bed above the still level (FLIP48 plain path with shelf_h 0), zb -21 m",
            "cost: 2.04-2.65 h by the FLIP48 coefficient, inside the 2.5-3 h budget only with W 140 (not 150)"])
    p = os.path.join(HERE, "plan_D_draft.json")
    json.dump(plan, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print("wrote", p, sha(p, 64))


if __name__ == "__main__":
    main()
