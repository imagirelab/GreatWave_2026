# -*- coding: utf-8 -*-
"""FLIP49 方案 A（PER49-A）：走らせる前に決まりを凍らせる（plan/plan_A_frozen.json ＋ .sha256。py -3.10 -B、numpy だけ）。
2026-10-15 新しく書いた（方案 A を実装する役、Claude）。g49_pcfg.py freezeA から呼ぶ。plan_frozen.json（PER49、PG12s）は読むだけで変えない。

方案 A：FLIP49 の周期のうねり（Fenton の流れ関数の波 T 12 s・H 7.5 m、入口の帯 0〜100 m、段 C）を、FLIP48 で真ん中に集まった海底（C3・R4 の
spur_channel：1:10 の軸、先細り k 0.35 → 1.0、横の 25 m の溝、棚 1.7 m）を +37.25 m ずらした海底 SC37 に入れる。決まり（P1〜P5 の閾は FLIP48 の
plan_frozen.json の targets と同じ。x の上限だけ並びに合わせて動かす）、繰り返しの判定（PERIODIC）、止める決まり、下見の見込み（登録）、正直に書く所を
ここで凍らせる。結果を見た後に閾を緩めない。

使い方：py -3.10 -B g49_pcfg.py freezeA [--force=1 --reason=…]
  あれば書かない。--force=1 は方案 A の FLIP の記録（layout A の cfg がある記録の run_c*.json）が無い間だけ。criteria・decision_rules・runs が
  変わる凍らせ直しは止める（design・honesty の直しだけ --reason つきで許す）。
"""
import os, sys, json, time, glob, math

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np            # noqa: E402
import g49_common as GC       # noqa: E402

PLAN_A_REL = "Unity/Build/FLIP49/plan/plan_A_frozen.json"
PLAN_A = GC.REPO + "/" + PLAN_A_REL
SCREEN_A = GC.B49 + "/screen_A"
SCREEN_FILES = ("eval_A_T12H7p5_A_T12H6p5_A_T12H6p0.json", "eval_A_T12H7p5_noch_A_T12H7p5_tapUp.json", "eval_A_T16H7p0.json",
                "sa_run.py", "sa_eval.py", "u3_A_T12H7p5.json")


def _screen():
    """下見（U3、screen_A）の登録する数を json から読む（設計の文の数と同じことを確かめる）。"""
    p = os.path.join(SCREEN_A, SCREEN_FILES[0])
    d = json.load(open(p, encoding="utf8"))["A_T12H7p5"]
    bf = d["break_frames"]
    reg = dict(source=os.path.relpath(p, GC.REPO).replace("\\", "/"), sha256_16=GC.sha256_file(p)[:16],
               periods=[b["p"] for b in bf], t_s=[round(b["t"], 3) for b in bf], x_break_m=[b["x_b"] for b in bf], h_break_m=[round(b["h_b"], 2) for b in bf],
               c0_m=[round(b["c0"], 2) for b in bf], c_side_m=[round(b["c_side"], 2) for b in bf], centre_over_side=[round(b["r_side"], 2) for b in bf],
               r4=[round(b["r4"], 2) for b in bf], fwhm_m=[round(b["half_w"], 1) for b in bf],
               reef_level_m=[round(b["reef_lev"], 2) for b in bf], incoming=d.get("incoming"))
    c0 = np.array(reg["c0_m"])
    reg["c0_cv"] = float(c0.std() / c0.mean())
    out = dict(A_T12H7p5=reg)
    try:
        d2 = json.load(open(os.path.join(SCREEN_A, SCREEN_FILES[1]), encoding="utf8"))
        out["no_channel"] = dict(centre_over_side=[round(b["r_side"], 2) for b in d2["A_T12H7p5_noch"]["break_frames"]],
                                 r4=[round(b["r4"], 2) for b in d2["A_T12H7p5_noch"]["break_frames"]])
        out["taper_upstream"] = dict(x_break_m=[b["x_b"] for b in d2["A_T12H7p5_tapUp"]["break_frames"]],
                                     centre_over_side=[round(b["r_side"], 2) for b in d2["A_T12H7p5_tapUp"]["break_frames"]])
    except Exception as e:      # 補いの数（無くても登録の主の数は上）
        out["sensitivity_error"] = repr(e)[:160]
    out["files_sha256_16"] = {nm: (GC.sha256_file(os.path.join(SCREEN_A, nm))[:16] if os.path.exists(os.path.join(SCREEN_A, nm)) else None) for nm in SCREEN_FILES}
    return out


def _build_check():
    p = GC.B49 + "/_logs/build_check.json"
    if not os.path.exists(p):
        return None
    c = json.load(open(p, encoding="utf8"))
    return dict(all_ok=c.get("all_ok"), hip_sha256=c.get("hip_sha256"), date=c.get("date"),
                A_3d={k: (c.get("A_3d") or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_vex_numpy_lt_1mm", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac", "sdf_ok", "pg_path")},
                A_3d_particles_dp1={k: (c.get("A_3d_particles_dp1") or {}).get(k) for k in ("particles", "particles_model", "n_below_bed", "particles_ok")},
                relax_probe_A={k: (c.get("relax_probe_A") or {}).get(k) for k in ("ok", "v_max_abs_diff", "div_max_abs_diff", "xa0", "Lx")})


def plan_A():
    import g49_pcfg as PC
    tg48 = json.load(open(GC.REPO + "/Unity/Build/FLIP48/plan/plan_frozen.json", encoding="utf8"))["targets"]
    pf49 = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))
    s_, sfT = GC.sf_solve()
    LY = GC.LAYOUTS["A"]
    sp = GC.SPEC_A
    da1 = PC.preset("DA1", {})[0]
    smk = PC.preset("SMOKE_A", {})[0]
    pc = da1["precheck"]
    gain = json.load(open(GC.PLAN_DIR + "/in_gain.json", encoding="utf8")) if os.path.exists(GC.PLAN_DIR + "/in_gain.json") else None
    P = dict(
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_pcfg.py freezeA (g49_planA.py)", canonical_path=PLAN_A_REL,
        campaign="PER49-A", parent_plan=dict(path="Unity/Build/FLIP49/plan/plan_frozen.json", sha256=GC.sha256_file(GC.PLAN_FROZEN), note="read only, not edited"),
        supervisor_Q52=pf49.get("supervisor_Q52"),
        user_context_ja=[
            "Q71（2026-10-15）：周期的に大波を出す方法、比べの見える動画（原画に最も近い瞬間を赤い枠で）、集まりが見える動画",
            "Q72（2026-10-15）：利用者が貼った別の Claude の確かめの意見の 5 点（要約）：(1) 方案 A と方案 C（指導教員に「3D は先に細さか、先に断面の似方か」を伺う）は"
            "同時にする。細くする水の 91〜99 % が横から入り前の面を寝かせるので、この取捨は指導教員が先に決める。(2) 方案 A がだめな時の備えとして、"
            "入ってくる波の向きで集め、崩す所は横にまっすぐな急な斜面にする方案 D を置く。(3) Q70（原画に近づくまで続ける）と手順 6（同じ問題は 2 回まで）が"
            "食い違う：どちらで進めるかは利用者の答え待ち。(4) 粒子 0.25 m の本番の前に 29 分以内の主メモリーの試し。足りなければ 0.35 m。"
            "(5)「爪を削る」は新しい爪の計算を削る意味で、浮世絵の段では設計 32〜33 の爪を使い直す",
            "この計画は (1) の方案 A の部分だけを凍らせる。方案 C の問いは機械の時間を使わないので、この計画とは別に今伺う（進行役の仕事）。(3) は答えが来るまで、"
            "下の決まり（追いの計算は 2 本まで、そこで止めて見せる）で止まる"],
        design=dict(
            summary="FLIP49 periodic swell on the FLIP48 C3/R4 spur_channel bed shifted +37.25 m (SC37), half tank, dp 0.5, stage C, 92 s",
            domain=dict(Lx_m=LY["Lx"], W_m=GC.W_MAIN, z_m=[LY["zb"], GC.Z_TOP], box=dict(zb=LY["zb"], floor_pad=2, cells_dp0p5=[442, 85, 44]),
                        symmetry="half tank: symmetry plane y = 0 and wall y = 85 m (= a row of identical spurs 170 m apart; centre peak symmetric by construction)",
                        particle_m=0.5, grid_m=1.0, veltransfer="flip",
                        layout_m=dict(inlet_band=[0.0, GC.IN_X1], free_flat=[100.0, 180.25], gauges_x=list(GC.GAUGE_X), gauges_y=list(GC.GAUGE_Y), spur_toe=180.25,
                                      channel_ramp=[187.25, 227.25], axis_1_10=[180.25, 333.25], taper_k=[277.25, 333.25], reef_top=[333.25, 353.25],
                                      back_drop_1_2=[353.25, 361.85], exit_band=[LY["ex_x0"], LY["Lx"]], edge_axis=GC.edge_x(sp)),
                        particles_computed=dict(dp0p5=PC.EXPECT_PARTICLES_A[0.5], dp1p0_W86=PC.EXPECT_PARTICLES_A[1.0], water_m3=622701.1)),
            bed=dict(name="SC37", kind=GC.bed_kind(sp), spec=GC.bed_record(sp), formula=GC.bed_formula(sp), u3_spec=GC.SPEC_A_U3,
                     shift_m=GC.DX_A, source_run48=GC.C3_RUN48,
                     checks="x < x_back: heights bit-equal to FLIP48 C3 bed_z(x - 37.25) (g49_pcfg.py check A_bed_equals_C3_shifted); equal to u3_beds.depth (< 1e-9 m); "
                            "VEX = numpy in the hip build check A_3d",
                     geometry_computed=dict(tongue="the 1.7 m 'shelf' is a tongue at the spur tip: half-width 0 m at x 333 and 6.0 m at x 353",
                                            depth_x340_m={"y10": 5.5, "y20": 11.9, "y30": 15.2, "y55": 21.0, "y60+": 25.0}),
                     honesty="resembles a reef spur with deep side channels; not a measured site"),
            swell=dict(kind="Fenton stream function, zero mean mass flux", T_s=GC.T_WAVE, H_m=GC.H_WAVE, h0_m=GC.H0, N=GC.SF_N,
                       values_computed=dict(L_m=sfT["L"], c_mps=sfT["c"], eta_crest_m=sfT["eta_crest"], eta_trough_m=sfT["eta_trough"], ursell=sfT["ursell"],
                                            H_over_Hmax=sfT["H_over_Hmax"]),
                       in_gain=(gain or {}).get("in_gain"), in_gain_source="plan/in_gain.json (S0b, measured: H -2.1 %, c -0.8 %, Kr 1.4 %)",
                       why=["crest at the spur toe matches R4: theory 5.17 m vs R4 incoming 5.10 m (C3 5.95 m); screen 5.02-5.23 m at x 160",
                            "its own trough (-2.33 m = 0.45 of the crest) comes in front of every crest and replaces the added leading trough of R4/C3 (0.18 crest) without any added shape",
                            "it is the wave whose inlet was already calibrated (S0b) and for which the exit sigma 1.41 was derived",
                            "T 12 s gives 4 judged breakers within 92 s"],
                       rejected=["T12 H8.4 (crest 5.96 = C3): breaks even further offshore",
                                 "T12 H6.5/H6.0 (crest 4.34/3.94): break moved only +7/+12 m in the screen, still before the taper",
                                 "T16 H7.0: narrower crests in the screen (FWHM 16-18 m) but centre/side only 1.5-1.6; needs a new S0b strip, an exit band >= 120 m "
                                 "(a 70 m band reflects 22-36 % at T 16) and t_end ~100 s; kept as the one-change follow-up DA2"]),
            drainage=dict(text="no closed pool: the reef top is the narrow tip of the spur (tongue up to 6 m half-width, x 333.25-353.25), then a 1:2 drop to 6 m (to x 361.85) "
                               "merging with the 5-17 m flanks and the 25 m side channels, then the exit sponge",
                          return_path="set-up and onshore mass flux go sideways off the tongue into the flanks and the 25 m side channels (|y| > ~55 m, 30 m wide in the half tank) "
                                      "and back offshore along them; mass flux ~ gH^2/(8c) = 5.6 m2/s per m of crest, ~220 m3/s over a 40 m spur crest, return ~0.3 m/s [computed, estimate]",
                          screen_levels="period means, periods 4-7 [computed]: reef tip +1.0 to +1.25 m, back of reef top +0.8 to +1.1 m, lagoon -0.2 to -0.65 m, side/channel +-0.2 m; no growth",
                          trigger="reef-top set-up > 3 m: diagnose first (2D strips cannot drain sideways, so no 2D strip is used for drainage)"),
            exit_band=dict(x_m=[LY["ex_x0"], LY["Lx"]], length_m=LY["Lx"] - LY["ex_x0"], sigma=LY["ex_sigma"], w="1 - exp(-sigma chi^2 dt) on vel.x and vel.z toward 0",
                           theory=GC.EX_THEORY_A, why="lengthened from 70 m to 80 m because the unbroken swell runs down the 25 m channels (70 m: CR 0.145 at h 25 m)"),
            drift_fix=dict(stage="C", probe_m=list(GC.PROBE_C), formula=pf49["design"]["absorber_and_drift_fix"]["stage_C"]["formula"], volume_window_m=list(LY["vol_x"])),
            time_and_records=dict(t_end_s=PC.T_END_A, frames=da1["f_end"], judged_breakers_expected=4, light_records="r2/r3 every frame as FLIP49",
                                  heavy_records="r4 per-y sections over x %s and r5 surfaces in windows [t_s-3, t_s+4] s around the screen onsets %s s" % (LY["r4_x"], PC.ONSET_SCREEN_A),
                                  windows=da1["records"]["windows"], r4_every=da1["records"]["r4"].get("every"), r5_every=da1["records"]["r5"].get("every"),
                                  fallback=(da1.get("case") or {}).get("fallback"),
                                  note="D0's FLIP onsets matched its screen within about 1 s [measured]"),
            level_regions=[list(r) for r in LY["level_regions"]],
            cost=dict(coef_s_per_Mparticle_frame=[PC.COEF_LO, PC.COEF_HI], growth=[PC.GROWTH_LO, PC.GROWTH_HI_A], heavy_s_per_frame=PC.R5_S_PER_FRAME,
                      precheck={k: pc.get(k) for k in ("particles_model", "frames", "heavy_frames", "solve_h_lo", "solve_h_hi", "records_h", "total_h_lo", "total_h_hi", "launches_est")},
                      memory_estimate_gb="about 7-8 (C3: 6.77 GB at 4.91 M particles) [computed estimate]",
                      fifth_breaker="t_end 102 s would add ~0.3 h (upper 2.74-2.96 h): not chosen"),
            smoke=dict(cfg=smk["run_id"], what=smk["note"], judged=False),
            preview_dp1="not recommended: D0 showed dp 1.0 cannot judge focusing, and a full dp 1.0 run costs ~40 min"),
        criteria=dict(
            source="P1-P5 thresholds copied unchanged from Unity/Build/FLIP48/plan/plan_frozen.json (targets); health from FLIP49 plan_frozen.json; only x limits move with the layout; none loosened after results",
            targets48=tg48,
            definitions=dict(judged_breaker="centre (y 0.5 m row) onset t >= %g s" % GC.T_JUDGE, window_k="[t_on,k - 6, t_on,k + 6] s",
                             Hc="centre crest above the still level at onset (ana.json onset.eta_c)",
                             crest_profile="c(y) = per-row maximum of the 3-cell x-median of eta_top over x in [max(150, xc0 - L/2), min(357, xc0 + L/2)], xc0 = the centre-row "
                                           "crest x found over [150, 357] in the same frame, L = %.1f m (the swell wavelength). Keeps the side crest of the same wave and excludes the "
                                           "next incoming crest (~L behind) [chosen; g49_periodic_ana.crest_window]" % sfT["L"],
                             curl_width="2 x grid x number of contiguous rows from y = 0 with thmax >= 90 deg (g46_analyze.rows_summary on the r4 per-y sections); "
                                        "with r4 recorded every 2nd frame the curl series reads every available frame"),
            per_breaker=dict(
                P1=dict(x_max_m=LY["p1_x_max"], text="the y 0.5 m row reaches a vertical tangent inside window k at x <= 357 m (exit start 362 - 5)"),
                P2=dict(width_over_hc_max=tg48["P2"]["width_over_hc_max"], text="curl width at onset <= 2.0 Hc"),
                P3=dict(width_over_hc_max_overturn=tg48["P3"]["width_over_hc_max_overturn"], width_over_hc_touchdown=tg48["P3"]["width_over_hc_touchdown"],
                        text="<= 2.5 Hc at the most overturned frame and <= 3.0 Hc at centre touchdown; report atan(c/v)"),
                P4a=dict(side_band_m=list(LY["side_band"]), x_side_max_m=LY["p1_x_max"], ratio_min=tg48["P4a"]["ratio_min"], ratio_clear=tg48["P4a"]["ratio_clear"],
                         text="c(0) / mean crest of |y| 70-84 m (x <= 357 m) >= 1.5; >= 2.0 reported as 'clearly focused'. This band lies in the 25 m channel"),
                P4b=dict(ratio_4hc_min=tg48["P4b"]["ratio_4hc_min"], text="c(0)/c(|y| = 4 Hc) >= 1.3, and no row at |y| >= 4 Hc curls before centre touchdown"),
                P5=dict(chord_min_deg=tg48["P5"]["chord_min_deg"], chord_good_deg=tg48["P5"]["chord_good_deg"], lip_min=tg48["P5"]["lip_min"], hood_min=tg48["P5"]["hood_min"],
                        print=tg48["P5"]["print"], text="centre-section chord over 0.1-0.5 eta_c >= 55 deg (good 60.5-78), lip/eta_c >= 0.2, hood/eta_c^2 >= 0.10; "
                                                        "report per breaker and the medians, never best frames only")),
            periodic_A=dict(
                PERIODIC=dict(n_consecutive_min=3, each=dict(P4a_min=1.5, P3_overturn_width_over_hc_max=2.5), onset_x_within_m=10.0, Hc_cv_max=0.10,
                              text="at least 3 consecutive judged breakers, each with P4a >= 1.5 and P3 overturn width <= 2.5 Hc; their onset x within +-10 m of their median; Hc CV <= 10 %"),
                open_item="centre chord >= 55 deg, recorded separately (R4 15-19 deg, C3 36 deg); A is not designed to fix it",
                verdict_wording=dict(full="P1-P5 on >= 3 consecutive breakers + PERIODIC", periodic_narrow_peak="PERIODIC + P1-P4 on >= 3 consecutive breakers",
                                     partial="otherwise, breaker by breaker", never="'steady state'", self_assessment="all scores are AI self-assessment; the user judges print-likeness")),
            report_only=dict(text="judged in FLIP49 (PER2-PER5) and shown in A's table, but not part of A's verdict (stated openly)",
                             items=["intervals 11.4-12.6 s and phase std <= 0.05 T", "trend of x <= 10 m and of Hc <= 10 %", "inlet H within 5 % at x 110-160; band-core drift <= 0.3 m",
                                    "c0 / incoming crest at x 160 (R4: 1.88)", "c(y) profile and FWHM", "level regions axis_front, reef_top, lagoon, side (period means)"]),
            health=dict(bed_leak_frac_max=tg48["H"]["bed_leak_frac_max"], volume_drift_max=tg48["H"]["volume_drift_max"], still_offset_max_m=tg48["H"]["still_offset_max_m"],
                        volume_rule="stage C: period-mean interior volume over x 110-357 m", mp4=True, wall_max_h_per_coarse_3d_run=PC.LIMIT_3D_H,
                        wall_rule="<= 2.5 h per coarse 3D run, launched in chunks of <= 29 min (production rule: one Houdini calculation <= 30 min)",
                        still_offset_note="S0a still fails (FLIP surface ~0.1 m high, depth dependent): reported; the 25 m channel adds a depth range, measured at the run start",
                        diagnose_first=["reef-top set-up > 3 m (period mean of the reef_top region)", "breaking at x < 180 m", "volume or leak failure"]),
            best_frame_rule=dict(window="for each judged k: frames from centre onset to touchdown + 0.5 s (no touchdown: onset + 2.5 s)",
                                 score="score3 = sum of print-band misses of face chord (0.1-0.5 eta_c), front foot (0.1 eta_c) and hood area (g47_video.score3) on the centre section r2",
                                 tie="smaller chord miss, then higher hood", overall="minimum score3 over judged k", representative="breaker with the median score3",
                                 output="<run>/pana/best_frames.json (read by g49_video2.py)"),
            deliverables="per run: g49_video2 compare mp4 (per judged breaker: 3D front-oblique 1:1 colour = height with c(y) posts, c(y) graph, whole y 0.5 m section with the zoom "
                         "window, centre-section zoom with the print outline, normalized overlay with the green/red metric table, time bar; thick RED frame and 3 s hold at the "
                         "best frame, 0.25x slow motion from onset - 1 s to touchdown + 0.5 s); whole-run mp4 at 2x with the per-breaker table and gauge time series (Q66); "
                         "RESULT_ja.md with tagged numbers"),
        decision_rules=dict(
            after_T0A="any numpy, build or smoke check fails: fix the code; no DA1 until all pass",
            after_SMOKE_A="pipeline, record, resume or level-guard failure: fix and rerun SMOKE_A; never judged",
            after_DA1=["STOP RULE: P4a < 1.3 on all judged breakers -> option A is negative; option D next (directional focusing by the incoming wave + straight 1:10 break slope)",
                       "P4a >= 1.5 and P4b pass on >= 2 judged breakers, but P2/P3 width fails on >= 2 -> DA2 = T16 H7.0 (S0b-type T16 inlet strip first, exit band >= 120 m)",
                       "PERIODIC passes -> DA3 continuation (+48 s to 140 s) and a seamless 12 s loop; the chord stays the open item, no tuning in A",
                       "1.3 <= P4a < 1.5 on most judged breakers -> 'partial'; stop and show the user together with option D (Q72 default)",
                       "health failure (reef-top set-up > 3 m, breaking at x < 180 m, volume/leak) -> diagnose before anything else"],
            after_DA2=["moved the way the rule says: keep and re-evaluate", "moved the wrong way: revert, record a negative result"],
            limits=["one change per run", "at most 2 follow-up runs in A, then stop and show the user", "never loosen a frozen threshold after seeing results"]),
        registered_screen_predictions=dict(
            tag="computed, screening only (U3 depth-averaged Boussinesq/NSW, dx 2 m, no overturning). For comparison after the run, never for judging",
            numbers=_screen(),
            expected_FLIP="break 0-15 m shoreward of the model's eta/h = 1 crossing (about 255-280 m) [guess from FLIP47 P1c and PG12s]; Hc 9.7-11.0 m; P4a-like 2.2-3.2; r4 1.9-2.5",
            caveat="on PG12s the same model gave centre/side 1.7 where FLIP D0 (dp 1.0, not judged) measured 0.8-1.1, i.e. it overshot by 0.6-0.9"),
        honesty=dict(
            forces="only gravity, the seabed shape and the incoming regular waves act; nothing pulls water toward a shape; the inlet band relaxes horizontal velocity only (never the surface level)",
            chosen=["option A itself (C3/R4 bed shifted +37.25 m so FLIP49's inlet, gauges, x_p and calibrated in_gain apply unchanged)",
                    "20 m reef top, 1:2 drop to 6 m, 80 m exit band, Lx 442, W 85 half tank", "T 12 s and H 7.5 m; dp 0.5; t_end 92 s; judged t >= 45 s; drift stage C; record windows",
                    "the periodicity thresholds and the P1/P4a x limit 357 m", "the crest-profile window xc0 +- L/2", "the bed resembles a reef spur with deep side channels but is not a measured site"],
            computed=["stream-function wave properties, particle counts, the box", "run-time estimates (measured FLIP48 coefficients and D0 growth)", "sponge reflection (1D theory)",
                      "the U3 screen (ranks options, does not judge; its periodic focusing is not validated)"],
            measured=["FLIP48 R4/C3 results", "S0b inlet calibration", "D0 rates, growth and no-focus result"],
            guesses=["FLIP onset 0-15 m shoreward of the model's eta/h = 1 crossing", "part of D0's missing focus came from dp 1.0"],
            not_predicted="P2, P3 and P5 (curl width and section shape)",
            known_conflict="the screen says this swell breaks on the broad k 0.35 part of the spur (h ~9-10 m, before the taper), not at the narrow tip where C3 broke (h 2.45 m). "
                           "So A tests periodic breakers on a broad spur with deep channels. A high centre/side is partly a low side crest in the 25 m channel, so c0/c_in and P4b "
                           "are reported beside P4a",
            process_notes=["importing flip45/r45_gen_numbers for the reflection numbers (design step) rewrote the untracked Unity/Build/FLIP45/research/generation_numbers.json "
                           "(deterministic output of the unchanged script; only the time stamp changed)", "no flip45-48 tool file was edited"]),
        runs=[dict(id="SA", status="done", what="U3 screen of option A (screen_A)"),
              dict(id="T0A", what="code, numpy (g49_pcfg.py check) and hip build checks (x49_build.py, all_ok)"),
              dict(id="FREEZE_A", what="this file"),
              dict(id="SMOKE_A", what="3D smoke dp 1.0, t 0-8 s, 2 launches (wall_limit 80 s); never judged"),
              dict(id="DA1", what="main coarse periodic 3D run, dp 0.5, 92 s, chained launches of <= 29 min, est. %.2f-%.2f h" % (pc.get("total_h_lo", 0), pc.get("total_h_hi", 0))),
              dict(id="ANA_A", what="g49_periodic_ana all with the A limits (cfg analysis block): per-breaker P1-P5, PERIODIC verdict, report-only items, best_frames.json, RESULT_ja.md"),
              dict(id="VID_A", what="g49_video2.py compare + whole-run mp4"),
              dict(id="DA2", status="conditional", what="T16 H7.0 by the frozen rule (inlet strip first)"),
              dict(id="DA3", status="conditional", what="+48 s continuation to 140 s if PERIODIC passes; seamless 12 s loop"),
              dict(id="MEM025", status="later", what="<= 29 min memory test before any 0.25 m run (estimate RSS ~5.1 GB + 0.34 GB per M particles, ~23 GB at ~52 M) [computed estimate]")],
        implementation=dict(
            tools=["Tools/GWWaveGen/flip49/" + n for n in ("g49_common.py", "g49_tanklib.py", "g49_build_tank.py", "x49_build.py", "g49_run.py", "g49_chain.py", "g49_pcfg.py",
                                                         "g49_planA.py", "g49_periodic_ana.py", "g49_video2.py")],
            module_sha256_16=module_shas_A(), hip="Houdini/FLIP49/g49_tank.hiplc", build_check_at_freeze=_build_check(),
            cfg_dry=dict(DA1=dict(run_id=da1["run_id"], precheck_ok=pc.get("ok")), SMOKE_A=dict(run_id=smk["run_id"], precheck_ok=smk["precheck"].get("ok"))),
            read_only=["flip45-flip48 files", "plan_frozen.json (PER49)", "g48_video2.py (imported, not edited)"]),
    )
    return P


def module_shas_A():
    out = dict(GC.module_shas())
    for nm in ("g49_planA.py", "g49_video2.py", "g49_video.py", "x49_build.py"):
        p = os.path.join(GC.TOOLS, nm)
        out["flip49/" + nm] = GC.sha256_file(p)[:16] if os.path.exists(p) else None
    p = os.path.join(GC.TOOLS48, "g48_video2.py")
    out["flip48/g48_video2.py"] = GC.sha256_file(p)[:16] if os.path.exists(p) else None
    return out


def _a_runs_exist():
    hits = []
    for cp in glob.glob(os.path.join(GC.B49, "*", "*", "cfg.json")):
        try:
            c = json.load(open(cp, encoding="utf8"))
        except Exception:
            continue
        if c.get("layout") == "A" and glob.glob(os.path.join(os.path.dirname(cp), "run_c*.json")):
            hits.append(os.path.dirname(cp))
    return hits


def freeze_A(force=False, reason=None):
    p = PLAN_A
    if os.path.exists(p) and not force:
        return p, "exists（変えない）"
    d = plan_A()
    if os.path.exists(p) and force:
        hits = _a_runs_exist()
        if hits:
            raise SystemExit("方案 A の FLIP の記録があるので凍らせ直さない：%s" % hits[:3])
        old = json.load(open(p, encoding="utf8"))
        same = {k: json.dumps(old.get(k), sort_keys=True, ensure_ascii=False) == json.dumps(d.get(k), sort_keys=True, ensure_ascii=False)
                for k in ("criteria", "decision_rules", "runs", "design", "honesty")}
        changed = [k for k, v in same.items() if not v]
        if changed and (not reason or any(k not in ("design", "honesty") for k in changed)):
            raise SystemExit("凍らせ直しで決まりが変わる（%s）。design・honesty の直しだけ --reason=… で許す" % changed)
        hist = list(old.get("refrozen_history") or [])
        hist.append(dict(frozen_at=old.get("frozen_at"), sha256=GC.sha256_file(p), changes=changed, reason=reason))
        d["refrozen_history"] = hist
    os.makedirs(os.path.dirname(p), exist_ok=True)
    s = json.dumps(d, indent=1, ensure_ascii=False, default=float)
    open(p, "w", encoding="utf8", newline="\n").write(s)
    h = GC.sha256_file(p)
    open(p + ".sha256", "w", newline="\n").write(h + "  plan_A_frozen.json\n")
    return p, "new %s" % h[:16]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(plan_A(), ensure_ascii=False, indent=1, default=float)[:4000])
