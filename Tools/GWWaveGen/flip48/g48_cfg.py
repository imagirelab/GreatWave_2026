# -*- coding: utf-8 -*-
"""FLIP48：孤立波の表と計算の設定（cfg.json）を作り、走らせる前の確かめ（numpy だけ、1 分以内）をする（py -3.10 -B）。
2026-10-15 新しく書いた。FLIP46 の g46_cfg.py（Tools/GWWaveGen/flip46、変えていない。今 main session が書き換えている所なので読み込まない）の
base()・parms_for() の形を写し、FLIP48 の分を足した（棚 shelf_h、cfg の bed・solitary、凍らせた目標 plan_frozen.json）。
計画：Docs/Progress/FLIP48_3D_Peak_Setup_ja.md。

  py -3.10 -B g48_cfg.py ready          A 0.3 の表、runs/ready/ の R0・R1・R2a・R2b、smoke/ready/ の SMOKE48、plan/plan_frozen.json（なければ）、
                                         plan/precheck.json（確かめ）を書く
  py -3.10 -B g48_cfg.py check          確かめだけ（plan/precheck.json と画面）
  py -3.10 -B g48_cfg.py r2 a|b|c|d     R2 の決まり（計画 §5）で選んだ 1 本の設定（c・d は A 0.25・0.4 の表も作る。c は 6 m の板も）
  py -3.10 -B g48_cfg.py one --kind 3d|strip [--k 0.35] [--A 0.3] [--W 85] [--t_end 18.5] [--tag 名前]   1 本（R0 の決まりで R1 を A 0.4 にする時など）
出す物：Unity/Build/FLIP48/solitary/tanaka_a*_x107.npz、runs/ready/*.json、smoke/ready/*.json、plan/plan_frozen.json（＋ .sha256）、plan/precheck.json

2026-10-15 R3 の試し（plan/campaign_R3_judge.json の queue G0 → R3 → R4 → R5。凍らせた物 plan/plan_R3_frozen.json）のために足した：
  py -3.10 -B g48_cfg.py one ... [--wave nwave --beta 0.12 --dk 1.6] [--kend 1.0 --xk1 240 --xk2 296] [--ch 55,4,25,150,40] [--zfloor -25]
                                 [--ledge 11.2,2.8,4] [--t_end 17.5] [--queue R3]
        谷のある波（g48_nwave.py の表。無ければ作る）・先細り・溝・箱の底・段を選べる。3D は走らせる前の確かめ（粒子 > 5.3 M か
        時間の見込み > 27 分なら書かずに止める）を cfg の precheck に書く。
  py -3.10 -B g48_cfg.py r3 g0a|g0b|g0c|smoke|r3|r3l [--beta 0.12] [--A 0.3] [--k 0.35] [--prefix R4] [--tag 名前]
        判定の queue の決まった形（G0a・G0b：板＋谷、G0c：段の板、smoke：新しい海底の SMOKE48、r3：先細り＋溝＋谷、r3l：先細り＋溝＋段）。
        R4・R5 は r3 に --prefix R4 と 1 つだけ変えた値（--beta 0.18、--A 0.35、--k 0.5）。
  py -3.10 -B g48_cfg.py freeze_r3       plan/plan_R3_frozen.json（＋ .sha256）を書く（あれば書かない。P1〜P5・H は plan_frozen.json の写し）
  check は、既定の海底が R0・R1・R2b の cfg と 1 bit も違わないこと（前の式の写しと比べる）と、既定の箱が g46_common.box と同じことを確かめ、
  違えば止める（assert）。
"""
import os, sys, json, math, time, argparse, glob

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                 # noqa: E402
trapz = getattr(np, "trapezoid", None) or np.trapz
import g48_common as GC            # noqa: E402
import g46_common as G46           # noqa: E402  比べ（棚 0 で同じ式か）だけ

FLOOR_PAD = 2                      # FLIP46 と同じ（海底を全部 SDF に）
INIT_DX = [-32.0, -15.0, 0.0, 15.0, 32.0]          # 初めのコマの確かめ：頂 x 107 m のまわり（x 75〜139 m。どれも尾根の始まり 143 m の前の平らな所）
INIT_Y = [-1.0, -2.0, -4.25, -8.5, -12.75, -15.0, -15.3]
T_END = 18.5                       # 計算の終わり（s）。巻き始めの見込み 13〜15.5 s ＋ 着水まで
PLAN_DOC = "Docs/Progress/FLIP48_3D_Peak_Setup_ja.md"

# ------------------------------------------------------------------ 凍らせた目標（走らせる前に plan/plan_frozen.json に書き、後で変えない）
TARGETS48 = dict(
    name="FLIP48 A-frame peak (centre-concentrated narrow plunging crest)",
    hc_def="Hc = 真ん中（y 0.5 m の行）の頂の静かな水面からの高さ（巻き始めのコマ）",
    width_def="巻いた全幅 = y = 0 から続く thmax ≥ 90° の行の数 × 格子 × 2（g46_analyze.rows_summary。r4 の各 y の断面）",
    P1=dict(x_max_m=330.0, t_max_s=17.5, text="真ん中（y 0.5 m）が x ≤ 330 m・t ≤ 17.5 s で縦の接線に届く"),
    P2=dict(width_over_hc_max=2.0, text="巻き始めの巻いた全幅 ≤ 2.0 Hc"),
    P3=dict(width_over_hc_max_overturn=2.5, width_over_hc_touchdown=3.0, text="最も巻いたコマで ≤ 2.5 Hc、真ん中の唇の着水で ≤ 3.0 Hc。剥がれ角 atan(c/v) を書く"),
    P4a=dict(side_band_m=[70.0, 84.0], x_side_max_m=340.0, ratio_min=1.5, ratio_clear=2.0,
             text="巻き始めの c(0) / 横の端 |y| 70〜84 m（x ≤ 340 m）の頂の平均 ≥ 1.5（≥ 2.0 ははっきり集まった）"),
    P4b=dict(ratio_4hc_min=1.3, text="巻き始めの c(0)/c(|y| = 4 Hc) ≥ 1.3、かつ真ん中の着水の前に |y| ≥ 4 Hc の行が巻かない"),
    P5=dict(chord_min_deg=55.0, chord_good_deg=[60.5, 78.0], lip_min=0.2, hood_min=0.10, print=dict(chord_deg=64.3, lip=0.35, hood=0.186),
            text="真ん中の断面（巻き始め〜着水）：前の面の弦 0.1〜0.5 η_c ≥ 55°（良い = 原画の帯 60.5〜78°）、唇 ÷ η_c ≥ 0.2、覆い ÷ η_c² ≥ 0.10"),
    H=dict(bed_leak_frac_max=1e-4, volume_drift_max=0.01, init_check_rel_max=0.06, still_offset_max_m=0.1, wall_max_min=30.0, mp4=True,
           text="海底より下の粒子 < 1e-4、水の量のずれ < 1 %、2 コマ目の確かめ 6 % 以内、静かな水面のずれ < 0.1 m、1 本 30 分以内、mp4 がある"),
    overall="P1〜P5 を全部満たせば目標どおり。一部だけなら一部と書く。数は AI の読み（自己評価）で、見た目の良し悪しは利用者が決める",
)
R0_RULE = dict(
    S1=dict(x_max_m=330.0, t_max_s=17.5, text="y 0.5 m の行の最初の縦の接線が x ≤ 330 m・t ≤ 17.5 s"),
    S2=dict(chord_min_deg=55.0, text="巻き始め〜着水のどこかのコマで前の面の弦（0.1〜0.5 η_c）≥ 55°"),
    S3=dict(lip_min=0.2, hood_min=0.10, text="唇 ÷ η_c ≥ 0.2 かつ覆い ÷ η_c² ≥ 0.10"),
    H="R1 と同じ（海底より下の粒子・初めのコマ・静かな水面のずれ・水の量・mp4）",
    rule="S1 が外れるか、弦が 45° に届かなければ、R1 を A 0.4 にする（表 tanaka_a0p4_x107.npz、1:10 での S0 0.24【計算】）。ほかは同じ",
)
R2_RULE = dict(
    order="(a)→(b)→(c)→(d) の順に当てはめ、最初に当たった 1 つだけを変える",
    a=dict(when="P1 が外れ（x 330 m までに真ん中が巻かない）", change="k 0.25（GG06 の値。尾根を広く）", expect="P1 が満たされる"),
    b=dict(when="P1 は満たし、P2・P3・P4b のどれかが外れ（巻きが広い・横が高い）", change="k 0.5（尾根を細く）",
           expect="巻き始めの幅 ÷ Hc と c(4Hc)/c(0) がどちらも下がる"),
    c=dict(when="P1〜P3・P4b は満たし、P4a が外れ（横の端が低くない）", change="A 0.25（k 0.35）。先に 6 m の板を A 0.25 で走らせ（約 4 分）、巻かなければ止めて報告",
           expect="c0/c_far が上がる"),
    d=dict(when="全部満たす、または P5 だけ外れ", change="A 0.4（k 0.35）、t_end 17.5 s", expect="P2〜P4 を保ったまま Hc が上がる"),
    negative="変えた値で、決まりが言う向きに量が動かなければ、それ以上合わせ込まず、負の結果として報告する",
)
K_RULE = dict(
    rule="主の会話の g46_analyze が P05_k0p5_W136 で真ん中の巻き始めを x ≤ 300 m・弦 ≥ 55° と読めば R1 を k 0.5、そうでなければ k 0.35",
    evidence=dict(source="Unity/Build/FLIP46/runs/P05_k0p5_W136/RESULT_ja.md（g46_analyze.py、2026-10-15 02:48）【測定】",
                  onset_x_m=300.5, onset_t_s=12.0, chord_onset_deg=21.0, chord_max_overturn_deg=52.3, overturned_full_m_onset=2.0),
    decision="k 0.35（巻き始め x 300.5 m > 300 m、弦 21〜52° < 55°）",
)


def sol_table(A, x0=GC.X0_CREST, force=False):
    """Tanaka の厳密な孤立波（g46_solitary、FLIP46 の解き手をそのまま）の表を Build/FLIP48/solitary に書く。返り値 (パス, 情報)。"""
    import g46_solitary as S
    p = GC.sol_path(A, x0)
    if os.path.exists(p) and not force:
        d = np.load(p)
        return p, dict(made="exists", F=float(d["F"]), c=float(d["c"]), a_over_h=float(d["a_over_h"]), x0=float(d["x0"]))
    t0 = time.time()
    wv = S.get_wave(A, x0=x0, use_cache=False, write_cache=False)
    os.makedirs(GC.SOL_DIR, exist_ok=True)
    wv.write_grid(p, np.arange(0.0, GC.LX + 1e-4, 0.25), np.arange(-GC.H0, 7.2501, 0.25))
    return p, dict(made="new", F=float(wv.F), c=float(wv.c), a_over_h=float(wv.a_over_h), x0=float(x0), s=round(time.time() - t0, 1))


def parms_for(dp, W, Lx=GC.LX, k=GC.RIDGE_K, smoke=False, wave_on=1.0, floor_pad=FLOOR_PAD, side_pad=0, zb=GC.Z_BOTTOM, bed_extra=None, **over):
    """CTRL の値と箱。zb：箱の底（既定 −17 m。溝のある R3 は −25 m、g48_common.box48）。bed_extra：R3 の先細り・溝・段（あれば CTRL の
    ridge_kend・ch_*・ledge_* を足す。無ければ前と同じ parms）。"""
    GC.check_dp(dp, smoke=smoke)
    b = GC.box48(dp, Lx=Lx, W=W, zb=zb, floor_pad=floor_pad, side_pad=side_pad)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             ridge_on=1.0, ridge_x0=GC.RIDGE_X0, ridge_k=float(k), ridge_s=GC.RIDGE_S, shelf_h=GC.SHELF_H,
             bed_gap=0.5, floor_pad=float(floor_pad), side_pad=float(side_pad), wave_on=float(wave_on),
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=b["W"],
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5)
    if bed_extra:
        p.update(GC.bed_parms(dict(GC.BED_EXTRA_DEFAULTS, **bed_extra)))
    p.update(over)
    return p, b


def make(run_id, kind, A, k, W, t_end=T_END, dp=0.5, out_root="runs", note="", case_extra=None, bed_extra=None, wave=None, zb=None):
    """1 本の設定。kind：'3d'（半幅 W）・'strip'（板）・'smoke'（粒子 1.0 m の短い試し）。
    R3 の選び（既定は無しで、無しなら前と同じ cfg）：bed_extra（k_end・xk1・xk2・ch_*・s1・dL・s2）、wave（dict(kind='nwave', beta, dk)）、zb（箱の底）。"""
    smoke = kind == "smoke"
    bed_extra = dict(bed_extra or {})
    zb_ = GC.Z_BOTTOM if zb is None else float(zb)
    p, b = parms_for(dp, W, k=k, smoke=smoke, zb=zb_, bed_extra=bed_extra)
    nw = wave is not None and wave.get("kind") == "nwave"
    if nw:
        import g48_nwave as NW
        sp, ni = NW.make(A, float(wave["beta"]), float(wave.get("dk", GC.DK_R3)), wave.get("ks"))
        _, si = sol_table(A)
        dnw = np.load(sp)
        wave_rec = dict(kind="nwave", beta=float(dnw["beta"]), dk=float(dnw["dk"]), k_s=float(dnw["k_s"]), d_m=float(dnw["d"]), a_m=float(dnw["a_m"]),
                        trough_amp_m=float(dnw["beta"]) * float(dnw["a_m"]), c0_trough_mps=float(dnw["c0_trough"]), crest_combined_m=float(dnw["eta"].max()),
                        eta_min_m=float(dnw["eta"].min()), npz_sha256=GC.sha256_file(sp)[:16], steady=False,
                        note_ja="谷のある波（g48_nwave.py）：Tanaka の頂 ＋ 線形の長い波の谷 −β a sech²(k_s(x − x0 − d))。定常な解ではない（頂は c、谷は c0 で進む。"
                                "重なりと尾根の始まり・溝の入り口との重なりで初めに揺れが出る。測っていない）。長いうねりの一つの山という仮定",
                        tags=dict(beta="選び", dk="選び", k_s="選び（A 0.3 の GN の κ、固定）", trough="選んだ形", crest="計算（Tanaka の厳密な解）"))
        sol_kind = "Tanaka1986_exact_a%g_x%g+trough_b%g_dk%g" % (A, GC.X0_CREST, float(wave["beta"]), float(dnw["dk"]))
    else:
        sp, si = sol_table(A)
        wave_rec = None
        sol_kind = "Tanaka1986_exact_a%g_x%g" % (A, GC.X0_CREST)
    spec = dict(GC.BED_EXTRA_DEFAULTS, k=float(k), x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H)
    spec.update(bed_extra)
    vox = b["vox"]
    f_end = GC.frames_for(0.0, t_end)
    if bed_extra:
        bed = dict(kind=GC.bed_kind(spec), h0=GC.H0, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, k=float(k), h_sh=GC.SHELF_H, on=True,
                   k_end=spec["k_end"], xk1=spec["xk1"], xk2=spec["xk2"], ch_y0=spec["ch_y0"], ch_w=spec["ch_w"], ch_h=spec["ch_h"],
                   ch_x0=spec["ch_x0"], ch_lx=spec["ch_lx"], s1=spec["s1"], dL=spec["dL"], s2=spec["s2"],
                   formula=GC.bed_formula(spec), shelf_x_axis_m=GC.shelf_x(spec, 0.0), box_floor_zb_m=b["z_bottom"],
                   max_depth_m=float(-GC.bed_z(np.arange(0.0, b["Lx"], 0.5)[None, :], np.arange(0.0, b["W"], 0.5)[:, None], **spec).min()))
        # 2026-10-15 見直し：溝（25 m）を箱の底 −17 m のまま作ると、−17 m より下に粒子が置かれず溝が空のまま走る（one で --zfloor を忘れた時）。止める
        if bed["max_depth_m"] > -float(b["z_bottom"]) + 1e-6:
            raise SystemExit("海底の最も深い所 %.3f m が箱の底 zb %.1f m より下（--zfloor を下げる。溝の R3 は −25）" % (bed["max_depth_m"], b["z_bottom"]))
    else:
        bed = dict(kind="ridge_shelf", h0=GC.H0, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, k=float(k), h_sh=GC.SHELF_H, on=True,
                   formula="z_b = -max(h_sh, h0 - max(x - x_toe, 0)/s * sech^2(k*y/h0))", shelf_x_axis_m=GC.SHORE_X)
    c = dict(
        run_id=run_id, out_root=out_root, stage="FLIP48", kind=("smoke" if smoke else ("preview" if dp >= 0.5 else "main")),
        case=dict(name="FLIP48_%s_k%g_A%g_W%g" % (bed["kind"], k, A, b["W"]), plan=PLAN_DOC, targets=TARGETS48, r0_rule=R0_RULE, r2_rule=R2_RULE,
                  k_rule=K_RULE, **(case_extra or {})),
        f_start=1, f_first=1, f_end=int(f_end), parms=p, box=b,
        solitary_npz=sp, solitary_kind=sol_kind,
        solitary=dict(H0_nd=float(A), x0_nd=GC.X0_CREST / GC.H0, c_nd=float(si["F"]), c_mps=float(si["c"])),
        bed=bed,
        solver=dict(veltransfer="flip", donarrowband=0),
        records=dict(r2=True, r3_z=b["W"] - 0.5 * vox, block=120, r4_block=24, preg_every=24,
                     r4=dict(x=[200.0, b["Lx"]], z1=b["W"], y0=-10.0, y1=16.0, clip_vox=6.0, t0=11.0),
                     r5=dict(t0=10.0, every=1)),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0,
        max_hours=1.5, level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=[300.0, 355.0], n1_window=[0.5, 1.0], shore_x=GC.SHORE_X,
        fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)], init_check_frames=[1, 2, 3], init_check_dx=list(INIT_DX),
        init_check_y=list(INIT_Y), init_dump=True, stop_touchdown=None, note=note)
    if smoke:
        c["ckpt_on"] = 0; c["max_hours"] = 0.25; c["wall_limit_s"] = 560
        c["records"]["r4"] = None; c["records"]["r5"] = dict(t0=0.0, every=24)
        c["n1_x"] = [300.0, 355.0]
    if kind == "strip":
        c["max_hours"] = 0.5
    if wave_rec:
        c["wave"] = wave_rec
    return c


def write(c, sub="runs/ready"):
    p = os.path.join(GC.B48, sub, c["run_id"] + ".json").replace("\\", "/")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return p


def tag(v):
    return ("%g" % v).replace(".", "p")


def R0(A=0.3):
    return make("R0_strip_RS_A%s" % tag(A), "strip", A, 0.0, GC.W_STRIP,
                note="FLIP48 R0：準 2D の板（半幅 6 m、k 0 で横に一様）。1:10 で棚 1.7 m に上る断面に Tanaka の孤立波 H0/h0 %g。R1 の 2D の基準 Hc_2D と場面の煙の試し" % A)


def R3d(k, A, W=GC.W_MAIN, t_end=T_END, prefix="R1"):
    return make("%s_RS_k%s_A%s_W%g" % (prefix, tag(k), tag(A), W), "3d", A, k, W, t_end=t_end,
                note="FLIP48 %s：尾根 k %g・真ん中 1:10・棚 1.7 m、Tanaka の孤立波 H0/h0 %g（まっすぐな頂）、半幅 %g m、粒子 0.5 m、FLIP の受け渡し、0〜%g s" % (prefix, k, A, W, t_end))


def SMOKE(k=GC.RIDGE_K, A=0.3):
    return make("SMOKE48_k%s_dp1p0" % tag(k), "smoke", A, k, GC.W_MAIN, t_end=3.0, dp=1.0, out_root="smoke",
                note="FLIP48 煙の試し：粒子 1.0 m・0〜3 s。場面・初めの波・尾根の斜面の漏れ・初めのコマの確かめだけ（巻きは見ない）")


def r2_cfgs(which):
    if which == "a":
        return [R3d(0.25, 0.3, prefix="R2a")]
    if which == "b":
        return [R3d(0.5, 0.3, prefix="R2b")]
    if which == "c":
        s = make("R2c_strip_RS_A0p25", "strip", 0.25, 0.0, GC.W_STRIP, note="FLIP48 R2(c) の前の板：A 0.25 で巻くか（巻かなければ止めて報告）")
        return [s, R3d(0.35, 0.25, prefix="R2c")]
    if which == "d":
        return [R3d(0.35, 0.4, t_end=17.5, prefix="R2d")]
    raise SystemExit("R2 は a・b・c・d")


# ------------------------------------------------------------------ R3 の試し（plan/campaign_R3_judge.json の queue）
JUDGE_R3 = GC.B48 + "/plan/campaign_R3_judge.json"
PLAN_R3 = GC.B48 + "/plan/plan_R3_frozen.json"
T_END_R3 = 17.5                    # G0〜R5 の計算の終わり（s）【選び：判定の queue】
LIMIT_PARTICLES = 5.3e6            # 3D を始めない粒子の数（判定の stop_rule の precheck）
LIMIT_WALL_MIN = 27.0              # 3D を始めない時間の見込み（分。H の上限 30 分）
COST_RUNS48 = ("R1_RS_k0p35_A0p3_W85", "R2b_RS_k0p5_A0p3_W85")   # 粒子 0.5 m の FLIP48 の 3D の 2 本【測定】


def case_r3(queue_id):
    return dict(campaign="R3", queue_id=queue_id, plan_r3=PLAN_R3, judge=JUDGE_R3,
                note_ja="判定（P1〜P5・H）は plan_frozen.json の写し、G0 の門と決まりは plan_R3_frozen.json（g48_peak_metrics.py が読む）")


def cost48():
    """FLIP48 の R1・R2b（粒子 0.5 m、445 コマ）の記録から：初めの粒子 ÷ 数え方の粒子、粒子の増え（最大 ÷ 初め）、
    1 コマ・粒子 100 万あたりの秒（最大の粒子で割る。面の秒も込み）【測定から計算】。格子の数（箱の cells）も並べる。"""
    rows = []
    for rid in COST_RUNS48:
        rd = os.path.join(GC.B48, "runs", rid)
        rs = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        if not rs:
            continue
        P = cfg["parms"]
        n_model, V = count_particles(GC.bed_spec(cfg), float(P["Lx"]), float(P["W"]), float(P["dp"]), eta_from_npz(cfg["solitary_npz"]),
                                     zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
        n0 = int(rs[0]["particles_first"]); n1 = int(max(r["particles_max"] for r in rs)); nf = int(cfg["f_end"])
        wall = sum(float(r.get("wall_launch_s") or r.get("wall_total_s") or 0.0) for r in rs)
        cells = int(np.prod(cfg["box"]["cells"]))
        rows.append(dict(run=rid, particles_model=n_model, particles_first=n0, particles_max=n1, frames=nf, wall_s=wall, cells=cells,
                         ratio_first_over_model=n0 / n_model, growth_max_over_first=n1 / n0, s_per_Mpart_frame=wall / (n1 / 1e6 * nf)))
    if not rows:
        raise SystemExit("時間の見込みの元の記録（%s）がない" % ", ".join(COST_RUNS48))
    return dict(rows=rows, ratio_first=float(np.mean([r["ratio_first_over_model"] for r in rows])),
                growth_max=float(max(r["growth_max_over_first"] for r in rows)),
                coef_lo=float(min(r["s_per_Mpart_frame"] for r in rows)), coef_hi=float(max(r["s_per_Mpart_frame"] for r in rows)),
                cells_ref=int(rows[0]["cells"]),
                note_ja="時間 = 最大の粒子（100 万）× コマの数 × 秒の係数（R1・R2b の小さい方〜大きい方）。面（t ≥ 10 s）の秒も込みで割ったので、"
                        "コマが少ない計算（421 コマ）では少し多めに出る。格子の数の増え（箱の底 −25 m で +22 %）の分は測っていない：上限の見込みとして"
                        "時間 × 格子の比も並べる")


def precheck(c, cm=None):
    """走らせる前の確かめ（判定の stop_rule）：粒子の数と時間の見込み。3D（横 > 12 m、粒子 0.5 m）は 粒子の最大の見込み > 5.3 M か
    時間の見込み（大きい方の係数）> 27 分なら ok = False（g48_cfg.py one・r3 は書かずに止め、g48_chain.py も始めない）。"""
    cm = cm or cost48()
    P = c["parms"]
    spec = GC.bed_spec(c)
    n, V = count_particles(spec, float(P["Lx"]), float(P["W"]), float(P["dp"]), eta_from_npz(c["solitary_npz"]), zb=float(P["zb"]),
                           bed_gap=float(P["bed_gap"]))
    first = n * cm["ratio_first"]; mx = first * cm["growth_max"]
    nf = int(c["f_end"]); cells = int(np.prod(c["box"]["cells"]))
    out = dict(particles_model=int(n), water_m3=float(V), particles_first_est=int(first), particles_max_est=int(mx), frames=nf, cells=cells,
               cells_ratio_vs_R1=cells / cm["cells_ref"], limits=dict(particles_max=LIMIT_PARTICLES, wall_min=LIMIT_WALL_MIN),
               cost_rows=[{k: r[k] for k in ("run", "particles_first", "particles_max", "frames", "wall_s", "s_per_Mpart_frame")} for r in cm["rows"]],
               tags=dict(particles_model="計算（初めの粒子の置き方を numpy で数えた）", ratio_growth="測定（R1・R2b）", wall="計算（測定の係数から）"))
    three_d = float(P["W"]) > 12.0 and c.get("kind") != "smoke"
    if abs(float(P["dp"]) - 0.5) < 1e-9:
        out["wall_min_est_lo"] = mx / 1e6 * nf * cm["coef_lo"] / 60.0
        out["wall_min_est_hi"] = mx / 1e6 * nf * cm["coef_hi"] / 60.0
        out["wall_min_upper_cells"] = out["wall_min_est_hi"] * max(1.0, out["cells_ratio_vs_R1"])
        out["wall_note_ja"] = "wall_min_est_hi で決める。wall_min_upper_cells は格子の数の増えが時間を全部比例で増やした時の上限（測っていない）"
    else:
        out["wall_note_ja"] = "粒子 %g m は係数（粒子 0.5 m）の外なので時間は見込まない" % float(P["dp"])
    if three_d:
        out["ok"] = bool(mx <= LIMIT_PARTICLES and out.get("wall_min_est_hi", 0.0) <= LIMIT_WALL_MIN)
        out["reason"] = None if out["ok"] else "粒子の最大の見込み %.2f M（上限 %.1f M）・時間の見込み %.1f 分（上限 %.0f 分）" % (
            mx / 1e6, LIMIT_PARTICLES / 1e6, out.get("wall_min_est_hi", float("nan")), LIMIT_WALL_MIN)
    else:
        out["ok"] = True
        out["reason"] = None
    out["scope"] = "3D（判定の上限で止める）" if three_d else "板・煙の試し（上限を当てない。数だけ）"
    return out


def r3_cfg(name, beta=GC.BETA_R3, A=GC.A0, k=GC.RIDGE_K, prefix=None, tag_=None, dk=GC.DK_R3):
    """判定の queue の決まった形の cfg（書かない）。name：g0a・g0b・g0c・smoke・smoke_r3l・r3・r3l。"""
    nwv = dict(kind="nwave", beta=float(beta), dk=float(dk))
    spur = dict(GC.TAPER_R3, **GC.CHANNEL_R3)
    if name in ("g0a", "g0b"):
        q = "G0a" if name == "g0a" else "G0b"
        rid = tag_ or "%s_strip_nw_A%s_b%s" % (q, tag(A), tag(beta))
        return make(rid, "strip", A, 0.0, GC.W_STRIP, t_end=T_END_R3, wave=nwv, case_extra=case_r3(q),
                    note="FLIP48 %s（R3 の試しの 2D の門）：準 2D の板（半幅 6 m、k 0）、R の断面（1:10 で棚 1.7 m、x 296 m）。Tanaka H0/h0 %g の頂 ＋ 前の谷 β %g"
                         "（d = %g/k_s）。谷は定常な解ではない。粒子 0.5 m・FLIP の受け渡し・0〜%g s" % (q, A, beta, dk, T_END_R3))
    if name == "g0c":
        rid = tag_ or "G0c_strip_ledge_A%s" % tag(A)
        return make(rid, "strip", A, 0.0, GC.W_STRIP, t_end=T_END_R3, bed_extra=dict(GC.LEDGE_G0C), case_extra=case_r3("G0c"),
                    note="FLIP48 G0c（谷が 2D で負の時だけ）：段の板（k 0、1:11.2 で水深 4.5 m の x 283.0 m、1:4 の段 2.8 m で棚 1.7 m の x 294.2 m）、"
                         "まっすぐな Tanaka H0/h0 %g（谷なし）。粒子 0.5 m・0〜%g s" % (A, T_END_R3))
    if name in ("smoke", "smoke_r3l"):
        led = name == "smoke_r3l"
        rid = tag_ or ("SMOKE48_R3L_TSCL_dp1p0" if led else "SMOKE48_R3_TSC_b%s_dp1p0" % tag(beta))
        be = dict(spur, **(GC.LEDGE_G0C if led else {}))
        return make(rid, "smoke", A, k, GC.W_MAIN, t_end=3.0, dp=1.0, out_root="smoke", bed_extra=be, wave=(None if led else nwv), zb=GC.ZB_DEEP,
                    case_extra=case_r3("SMOKE48_R3L" if led else "SMOKE48_R3"),
                    note="FLIP48 煙の試し（新しい海底の最初の 3D の前に 1 回）：粒子 1.0 m・0〜3 s。先細り＋溝%s、箱の底 −25 m。場面・初めの波・"
                         "斜面と溝の壁の漏れ・初めのコマの確かめだけ（巻きは見ない）" % ("＋段（R3L）" if led else "、谷 β %g" % beta))
    if name in ("r3", "r3l"):
        led = name == "r3l"
        pre = prefix or ("R3L" if led else "R3")
        be = dict(spur, **(GC.LEDGE_G0C if led else {}))
        if led:
            rid = tag_ or "%s_TSCL_k%s_A%s_W85" % (pre, tag(k), tag(A))
        else:
            rid = tag_ or "%s_TSC_k%s_A%s_b%s_W85" % (pre, tag(k), tag(A), tag(beta))
        return make(rid, "3d", A, k, GC.W_MAIN, t_end=T_END_R3, bed_extra=be, wave=(None if led else nwv), zb=GC.ZB_DEEP, case_extra=case_r3(pre),
                    note="FLIP48 %s：尾根 k %g → 1.0（x 240〜296 m の先細り）・真ん中 1:10%s・棚 1.7 m、横の遠くの溝（|y| ≳ 55 m を 25 m、x 150〜190 m）、"
                         "箱の底 −25 m。%s。半幅 85 m、粒子 0.5 m、FLIP の受け渡し、0〜%g s" % (
                             pre, k, "（＋段 1:11.2 → 1:4 → 棚）" if led else "",
                             "まっすぐな Tanaka H0/h0 %g（谷なし）" % A if led else "Tanaka H0/h0 %g の頂 ＋ 前の谷 β %g（d = %g/k_s、定常な解ではない）" % (A, beta, dk),
                             T_END_R3))
    raise SystemExit("r3 は g0a・g0b・g0c・smoke・smoke_r3l・r3・r3l")


def write_checked(c, sub=None):
    """precheck を cfg に書き、3D で ok でなければ書かずに止める。"""
    c["precheck"] = precheck(c)
    if not c["precheck"]["ok"]:
        raise SystemExit("走らせる前の確かめで止めた（cfg は書かない）：%s" % c["precheck"]["reason"])
    return write(c, sub or ("smoke/ready" if c["kind"] == "smoke" else "runs/ready"))


def freeze(force=False):
    p = GC.B48 + "/plan/plan_frozen.json"
    if os.path.exists(p) and not force:
        return p, "exists（変えない）"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    d = dict(frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip48/g48_cfg.py", plan=PLAN_DOC,
             runs=["R0_strip_RS_A0p3（約 4 分）", "R1_RS_k0p35_A0p3_W85（約 20 分）", "R2：R2_RULE で 1 本（約 20 分）"],
             targets=TARGETS48, r0_rule=R0_RULE, r2_rule=R2_RULE, k_rule=K_RULE,
             bed=dict(formula="z_b = -max(1.7, 17 - max(x-143,0)/10 * sech^2(k*y/17))", k_R1=0.35, shelf_x_axis_m=GC.SHORE_X),
             wave=dict(kind="Tanaka 1986 exact solitary, straight crest uniform in y", A=0.3, x0_m=GC.X0_CREST),
             honesty_ja="選んだ物：振幅 0.3 h0 と尾根（盛り上がりの出る所＝尾根の軸と、横の高さ 5.1〜5.6 m を決める）。計算した物：真ん中の伸び、崩れ方、巻きの形と幅、剥がれ、唇")
    json.dump(d, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(p + ".sha256", "w").write(GC.sha256_file(p) + "  plan_frozen.json\n")
    return p, "new"


def _ref_run(rid):
    """凍らせる時の基準の値（R0・R1・R2b の記録から。測定）：peak.json の判定の量と g48_supp の補いの読み。"""
    import g48_supp as GS
    rd = os.path.join(GC.B48, "runs", rid)
    pk = json.load(open(os.path.join(rd, "peak.json"), encoding="utf8"))
    sp = GS.supp(rd)
    sp.pop("chords", None)
    sd = dict(sp.get("shelf_depth") or {}); sd.pop("series_every6", None)
    on = pk.get("onset") or {}
    lo = (pk.get("lateral_key") or {}).get("onset") or {}
    sw = pk.get("shape_window") or {}
    h = pk.get("health") or {}
    return dict(run=rid, source="runs/%s/peak.json・ana.json（g48_peak_metrics・g48_analyze）＋ g48_supp.supp【測定】" % rid,
                onset=dict(frame=on.get("frame"), t=on.get("t"), xc=on.get("xc"), Hc_m=on.get("eta_c")),
                shape_window=dict(chord_max_deg=sw.get("chord_max"), lip_max=sw.get("lip_max"), area_max=sw.get("hood_max"), frames=sw.get("frames")),
                P4=dict(ratio_side_P4a=lo.get("ratio_side"), ratio_4Hc_P4b=lo.get("ratio_4Hc"), c0_m=lo.get("c0")),
                still_offset_m=h.get("still_offset_m"), judge=pk.get("judge"),
                onset_apron=(sp.get("onset_apron") or {}).get("apron"), frozen_chord_max=sp.get("frozen_chord_max"),
                frames_chord_ge55=sp.get("frames_chord_ge55"), chord_local_max_deg=sp.get("chord_local_max_deg"),
                body_face=sp.get("body_face"), body_chord_swl_median_deg=(sp.get("body_face") or {}).get("chord_swl_median_deg"),
                print_ruler={k: v for k, v in (sp.get("print_ruler") or {}).items() if k != "rule_ja"}, shelf_depth=sd)


def freeze_r3(force=False):
    """plan/plan_R3_frozen.json（＋ .sha256）を G0 の前に書く。P1〜P5・H は plan_frozen.json の targets をそのまま写す（plan_frozen.json は変えない）。
    ほかは判定 campaign_R3_judge.json の queue（G0・R3・R4・R5）の決まり・門・幅・止める決まりの写しと、門を読むための決まり（g48_supp.DEFS）、
    R0・R1・R2b の基準の値【測定】。あれば書かない（結果を見た後に変えないため。--force は使わないこと）。"""
    import g48_supp as GS
    import g48_nwave as NW
    p = PLAN_R3
    if os.path.exists(p) and not force:
        return p, "exists（変えない）"
    pf_path = GC.B48 + "/plan/plan_frozen.json"
    pf = json.load(open(pf_path, encoding="utf8"))
    jd = json.load(open(JUDGE_R3, encoding="utf8"))
    Q = {e["id"].split(" ")[0].split("_")[0]: e for e in jd["queue"]}
    for k_ in ("G0", "R3", "R4", "R5"):
        if k_ not in Q:
            raise SystemExit("判定の queue に %s が無い" % k_)
    refs = {nm: _ref_run(rid) for nm, rid in (("R0", "R0_strip_RS_A0p3"), ("R1", "R1_RS_k0p35_A0p3_W85"), ("R2b", "R2b_RS_k0p5_A0p3_W85"))}
    pn, _ = NW.make()
    nwc = NW.nwave_checks(pn)
    base = dict(GC.BED_EXTRA_DEFAULTS, k=GC.RIDGE_K, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H)
    sp3 = dict(base, **GC.TAPER_R3, **GC.CHANNEL_R3)
    spL = dict(base, k=0.0, **GC.LEDGE_G0C)
    sp3L = dict(sp3, **GC.LEDGE_G0C)
    r0 = refs["R0"]
    cmd = "py -3.10 -B G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48/"
    d = dict(
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip48/g48_cfg.py freeze_r3", plan=PLAN_DOC,
        campaign="FLIP48 R3: tapered reef spur + far deep side channels + Tanaka crest with a leading trough (queue G0 -> R3 -> R4 -> R5)",
        rule_ja="G0 の計算の前に書いた。結果を見た後にこの file は変えない（plan_frozen.json も変えない）。P1〜P5・H は plan_frozen.json の targets の写しで、"
                "判定（g48_peak_metrics.judge）はそれだけを使う。G0 の門と決まり、R3〜R5 の決まり・幅・止める決まりは判定 campaign_R3_judge.json の写し。"
                "門を読むための決まり（definitions）は D1 の読み方を写し、閾値の分かれ目を【選び】と書いた",
        sources=dict(plan_frozen=dict(path=pf_path, sha256=GC.sha256_file(pf_path)), judge=dict(path=JUDGE_R3, sha256=GC.sha256_file(JUDGE_R3)),
                     chosen_proposal=jd["ranking"][0]["title"], chosen_score=jd["ranking"][0]["score"]),
        targets=pf["targets"],
        targets_note="plan_frozen.json の targets をそのまま写した（P1〜P5・H と Hc・幅の決まり）。変えていない",
        definitions=dict(
            GS.DEFS,
            onset_Hc="g48_analyze（g46_analyze）の onset：真ん中 y 0.5 m の行の最初の縦の接線のコマ、xc・t・η_c（= Hc）。targets.hc_def と同じ",
            lip_area_chord="唇・巻いた面積・凍らせた弦は g48_peak_metrics の shape_window（ana.json の形の量のコマ＝巻き始め〜着水、なければ + 2 s の最大）。"
                           "P5 と同じ量。判定の「R0 0.43 / 0.25」の唇 0.43 は最も巻いたコマの値（shape_window の最大は 0.533）。どちらも門の 0.25 を越える",
            apron="g48_supp.apron_level ÷ η_c（巻き始めのコマ。D1 の lvl_1p5_3eta と同じ）",
            chord_01_on_face="凍らせた弦 ≥ 55° のコマのどれかで、そのコマの apron ≤ %g（0.1 η_c の点が前の水の層の上ではない）" % GS.ON_FACE_APRON_MAX,
            jet_tip_flag="|x05 − hood_tip| ≤ %g η_c（凍らせた弦の最大のコマと、弦 ≥ 55° の各コマで書く）" % GS.JET_TIP_TOL,
            body_chord="巻き始め〜噴き出しの落ち始め（reach ≥ %g η_c かつ hood_low_z < %g η_c の最初のコマ）の前の、静かな水面から測った弦の中央値。"
                       "G0c の「R0 + 10°」は R0 の同じ量（下の reference_R0）に 10° を足した値" % (GS.JET_FALL_REACH_MIN, GS.JET_FALL_HOOD_LOW),
            foot_cavity_hood="ana.json の形の表の最も巻いたコマの front_x01_rel・gap_max・reach（原画 0.2541・0.5406・0.5925）",
            min_shelf_depth="g48_supp.min_shelf_depth（t ≥ 2 s〜巻き始めのコマ、真ん中の行、頂より前、静かな時の水深 ≤ 1.7 m の所の水深の最小）",
            c0_over_H0="c0（巻き始めの真ん中の頂、x 150〜Lx − 15 m）÷ H0 = A h0（谷を足す前の Tanaka の頂 5.10 m）",
            out_of_channel_ratio="c0 ÷ |y| 35〜48 m の頂の平均（x ≤ 340 m）。P4a の横の帯 70〜84 m は溝の中",
            beta_scaling="一つの β の測った最小の水深を別の β へ：h_sh − (h_sh − d_min)·β'/β【選び：線形】"),
        geometry=dict(
            R_series_axis="z_b = -max(1.7, 17 - max(x-143,0)/10 * sech^2(k*y/17)); shelf edge on the axis x 296 m",
            R3_spur_channel=dict(spec=sp3, formula=GC.bed_formula(sp3), shelf_x_axis=GC.shelf_x(sp3, 0.0), box_zb_m=GC.ZB_DEEP, floor_pad_cells=FLOOR_PAD,
                                 z_top_m=GC.Z_TOP),
            G0c_ledge_strip=dict(spec=spL, formula=GC.bed_formula(spL), shelf_x_axis=GC.shelf_x(spL, 0.0), ledge_top_x=GC.RIDGE_X0 + (GC.H0 - GC.SHELF_H - GC.LEDGE_G0C["dL"]) * GC.LEDGE_G0C["s1"]),
            R3L=dict(spec=sp3L, formula=GC.bed_formula(sp3L), shelf_x_axis=GC.shelf_x(sp3L, 0.0)),
            R4h_taper_start_k=0.5,
            tags=dict(taper="chosen", channel="chosen", ledge="chosen", box="computed (floor -25 m + 2 cells; top +17 m)")),
        wave=dict(
            nwave=dict(formula="eta = eta_Tanaka(A) - beta*a*sech^2(k_s*(x - x0 - d)); u += c0*eta_t/(h0+eta); w += -(z+h0)*du_t/dx",
                       A=GC.A0, x0_m=GC.X0_CREST, k_s=GC.KS_R3, dk=GC.DK_R3, d_m=GC.DK_R3 / GC.KS_R3, c0_mps=GC.C0_LIN,
                       k_s_rule="k_s は A 0.3 の GN の κ（0.024472 /m、判定の 0.02447）に固定し、β・A を変えても変えない【選び：1 本で 1 つだけ変える】",
                       table_b0p12=dict(npz=pn, sha256=GC.sha256_file(pn), crest_combined_m=nwc["crest_combined_m"], crest_tanaka_m=nwc["crest_tanaka_m"],
                                        eta_min_m=nwc["trough"]["eta_min_m"], x_eta_min_m=nwc["trough"]["x_eta_min_m"],
                                        trough_amp_m=nwc["trough"]["trough_amp_m"], volume_trough_m2=nwc["trough"]["volume_trough_m2"],
                                        green_upper_bound_on_shelf_m=nwc["trough"]["green_upper_bound_on_shelf_m"]),
                       steady=False, generate_other_beta=cmd + "g48_nwave.py --beta 0.09（0.06・0.15・0.18 も同じ）",
                       generate_A0p35=cmd + "g48_nwave.py --A 0.35 --beta <β>"),
            tanaka_straight="Tanaka 1986 exact solitary H0/h0 0.3, straight crest uniform in y (G0c, R3L)"),
        G0=dict(
            id=Q["G0"]["id"], bed=Q["G0"]["bed"], wave=Q["G0"]["wave"], domain=Q["G0"]["domain"], est_minutes=Q["G0"]["est_minutes"],
            expected=Q["G0"]["expected"], code_changes=Q["G0"]["code_changes"], decision_after=Q["G0"]["decision_after"],
            gate=dict(H=dict(bed_leak_frac_max=pf["targets"]["H"]["bed_leak_frac_max"], init_check_rel_max=pf["targets"]["H"]["init_check_rel_max"],
                             still_offset_max_m=pf["targets"]["H"]["still_offset_max_m"], volume_drift_max=pf["targets"]["H"]["volume_drift_max"]),
                      onset_x_m=[273.0, 305.0], onset_t_max_s=13.5, apron_onset_max=0.03, lip_min=0.25, area_min=0.12,
                      frozen_chord_min_deg=55.0, chord_01_point_on_face=True, shelf_depth_ahead_min_m=0.5,
                      text="Pass needs all: H (bed leak < 1e-4, frame-2 check <= 6%, still offset < 0.1 m, volume drift < 1%); 2D onset x 273-305 m and t <= 13.5 s; "
                           "onset apron <= 0.03; lip >= 0.25 and curled area >= 0.12; frozen chord >= 55 deg in some frame onset..touchdown with the 0.1 eta_c point "
                           "on the body or jet face; minimum water depth on the shelf ahead of the crest >= 0.5 m"),
            g0c_positive=dict(onset_x_max_m=302.0, body_chord_gain_deg=10.0, foot_max=1.0, frozen_chord_min_deg=55.0, lip_min=0.25, area_min=0.12,
                              text="onset <= 302 m and (body chord >= R0 + 10 deg or foot <= 1.0 eta_c) and frozen chord >= 55 with lip >= 0.25 and area >= 0.12"),
            decision_rules=[
                dict(order=1, when="any G0 H item fails", then="fix the tooling and rerun the same strip"),
                dict(order=2, when="G0a gate passes", then="R3 with beta 0.12"),
                dict(order=3, when="G0a fails only on onset < 273 m, or only on lip < 0.25 / area < 0.12 (failing items within {onset x < 273, lip, area})",
                     then="G0b at beta 0.09; if it passes, R3 with beta 0.09"),
                dict(order=4, when="G0a fails on apron > 0.03 but apron <= 0.068 - 0.02 = 0.048 and onset >= 280 m, and the measured minimum shelf depth "
                                   "scaled to beta 0.15 stays >= 0.5 m", then="G0b at beta 0.15; if it passes, R3 with beta 0.15"),
                dict(order=5, when="otherwise, or G0b fails (trough negative in 2D)", then="G0c (ledge strip, straight Tanaka 0.3); if positive (g0c_positive), R3L"),
                dict(order=6, when="G0c negative", then="stop; run no 3D; report that neither face lever gave a print-like 2D centre section at A 0.3")],
            decision_rules_note="decision_after の写しを順に並べた読み（order 3・4 の言い換えは decision_after の文が正）",
            reference_R0=dict(r0["onset"], apron=r0["onset_apron"], lip_max=r0["shape_window"]["lip_max"], area_max=r0["shape_window"]["area_max"],
                              chord_max_deg=r0["shape_window"]["chord_max_deg"], body_chord_swl_median_deg=r0["body_chord_swl_median_deg"],
                              body_face=r0["body_face"], foot=(r0["print_ruler"] or {}).get("foot"), cavity=(r0["print_ruler"] or {}).get("cavity"),
                              hood=(r0["print_ruler"] or {}).get("hood"), still_offset_m=r0["still_offset_m"], min_shelf_depth_m=(r0["shelf_depth"] or {}).get("min_depth_m"),
                              jet_tip_at_chord_max=(r0["frozen_chord_max"] or {}).get("jet_tip"),
                              judge_quoted="body chord 24-33 (still water) / 35-43 deg (local datum) for frames 325-341 (D1); this code: median over 325-345",
                              tag="measured"),
            configs=dict(G0a=cmd + "g48_cfg.py r3 g0a", G0b_0p09=cmd + "g48_cfg.py r3 g0b --beta 0.09", G0b_0p15=cmd + "g48_cfg.py r3 g0b --beta 0.15",
                         G0c=cmd + "g48_cfg.py r3 g0c")),
        R3=dict(
            id=Q["R3"]["id"], bed=Q["R3"]["bed"], wave=Q["R3"]["wave"], domain=Q["R3"]["domain"], est_minutes=Q["R3"]["est_minutes"],
            expected=Q["R3"]["expected"], code_changes=Q["R3"]["code_changes"], decision_after=Q["R3"]["decision_after"],
            decision_numbers=dict(P4a_failed_extrapolation_below=1.6, P4b_failed_extrapolation_below=1.25, apron_layer_threshold=0.08,
                                  onset_beta_up_above_x_m=330.0, onset_beta_down_below_x_m=270.0, beta_step=0.06, beta_bounds=[0.06, 0.18],
                                  h_rerun_allowed_in_campaign=1, r3l_A_step_to=0.35, taper_start_k_case_h=0.5),
            configs=dict(smoke=cmd + "g48_cfg.py r3 smoke --beta <β>", R3=cmd + "g48_cfg.py r3 r3 --beta <β>", smoke_R3L=cmd + "g48_cfg.py r3 smoke_r3l",
                         R3L=cmd + "g48_cfg.py r3 r3l",
                         one_equivalent=cmd + "g48_cfg.py one --kind 3d --kend 1.0 --xk1 240 --xk2 296 --ch 55,4,25,150,40 --zfloor -25 --wave nwave "
                                              "--beta <β> --dk 1.6 --t_end 17.5 --queue R3")),
        R4=dict(
            id=Q["R4"]["id"], bed=Q["R4"]["bed"], wave=Q["R4"]["wave"], domain=Q["R4"]["domain"], est_minutes=Q["R4"]["est_minutes"],
            expected=Q["R4"]["expected"], code_changes=Q["R4"]["code_changes"], decision_after=Q["R4"]["decision_after"],
            required_moves=dict(beta_up=dict(onset_apron_falls_by_at_least=0.02), beta_down=dict(P4b_rises_by_at_least=0.03),
                                A0p35=dict(chord_up_deg=10.0, or_lip_up=0.05, or_area_up=0.03), taper_start_k0p5=dict(max_overturn_width_falls_by_Hc=0.3)),
            configs=dict(beta_up=cmd + "g48_cfg.py r3 r3 --prefix R4 --beta <β + 0.06>", beta_down=cmd + "g48_cfg.py r3 r3 --prefix R4 --beta <β − 0.06>",
                         A0p35=cmd + "g48_cfg.py r3 r3 --prefix R4 --A 0.35 --beta <β>（R3L なら r3l --prefix R4 --A 0.35）",
                         taper_k0p5=cmd + "g48_cfg.py r3 r3 --prefix R4 --k 0.5 --beta <β>")),
        R5=dict(
            id=Q["R5"]["id"], bed=Q["R5"]["bed"], wave=Q["R5"]["wave"], domain=Q["R5"]["domain"], est_minutes=Q["R5"]["est_minutes"],
            expected=Q["R5"]["expected"], code_changes=Q["R5"]["code_changes"], decision_after=Q["R5"]["decision_after"],
            configs=dict(midpoint=cmd + "g48_cfg.py r3 r3 --prefix R5 --beta <中点、例 0.15 か 0.09>")),
        bounds=dict(beta=[0.06, 0.18], beta_step=0.06, beta_up_needs_scaled_min_shelf_depth_m=0.5, A=[0.30, 0.35],
                    geometry_not_tuned_after_R3=True, one_knob_per_run=True,
                    no_new_elements="no lens, arc crest, crossing seas, periodic inlet or resolution change; only the predeclared G0c/R3L ledge fallback"),
        prechecks=dict(particles_max=LIMIT_PARTICLES, wall_min_est_max=LIMIT_WALL_MIN, H_wall_limit_min=30.0, tool="g48_cfg.precheck（g48_chain.py も ok でなければ始めない）"),
        budget=dict(queue_entries_max=4, g0_strips_max=3, three_d_runs_max=3, smoke_per_new_bed=1, one_sim_at_a_time=True),
        stop_rule=jd["stop_rule"], honesty=jd["honesty"],
        references_measured={nm: v for nm, v in refs.items()},
        known_before_G0=[
            "R0 の静かな水面のずれは 0.125 m で、H の 0.1 m を越えている（R0 の PEAK_ja.md の H_still_offset いいえ）【測定】。G0 の板は R0 と同じ箱なので、"
            "同じ読みなら G0 の H の静かな水面のずれも外れうる（決まり 1：道具を直して同じ板をもう一度）。R1・R2b は 0.089・0.085 m",
            "谷のある波の表（β 0.12）で、足した後の頂は %.3f m（Tanaka の 5.100 m から谷の裾で %.3f m 下がる）、水面の最小は %.3f m（x %.1f m）。"
            "谷の 0.61 m は谷だけの深さで、頂の裾と重なるので水面はそこまで下がらない【計算】" % (
                nwc["crest_combined_m"], nwc["crest_change_m"], nwc["trough"]["eta_min_m"], nwc["trough"]["x_eta_min_m"]),
            "溝の tanh の壁の裾で、溝の外の帯 |y| 35〜48 m も最大 %.2f m 深くなる【計算】" % checks_r3_band_extra(sp3),
            "R3 の粒子の見込みは最大 %s M、時間は %s 分（格子の数の増えを全部入れた上限 %s 分）【計算、R1・R2b の測定の係数から】" % ("{R3_particles}", "{R3_wall}", "{R3_wall_cells}")],
    )
    pc = precheck(r3_cfg("r3"))
    d["known_before_G0"][-1] = d["known_before_G0"][-1].replace("{R3_particles}", "%.2f" % (pc["particles_max_est"] / 1e6)).replace(
        "{R3_wall}", "%.1f〜%.1f" % (pc["wall_min_est_lo"], pc["wall_min_est_hi"])).replace("{R3_wall_cells}", "%.1f" % pc["wall_min_upper_cells"])
    d["precheck_R3_b0p12"] = pc
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    open(p + ".sha256", "w").write(GC.sha256_file(p) + "  plan_R3_frozen.json\n")
    # 写しが本当に同じか（plan_frozen.json の targets と、書いた file の targets）
    back = json.load(open(p, encoding="utf8"))
    if back["targets"] != pf["targets"]:
        raise SystemExit("plan_R3_frozen.json の targets が plan_frozen.json と違う")
    return p, "new"


def checks_r3_band_extra(sp):
    xs = np.arange(0.0, 360.0, 0.25); ys = np.arange(35.0, 48.0001, 0.25)
    X, Y = np.meshgrid(xs, ys)
    return float(np.max(-GC.bed_z(X, Y, **sp) + GC.bed_z(X, Y, **dict(sp, ch_h=0.0))))


# ------------------------------------------------------------------ 確かめ（numpy）
def count_particles(spec, Lx, W, dp, eta_fn, zb=GC.Z_BOTTOM, bed_gap=0.5):
    """場面の init_particles と同じ決まりで初めの粒子の数を数える：列 (ix+0.5)dp・(iz+0.5)dp、段 y = zb + (k+0.5)dp、
    海底 + bed_gap·dp ≤ y < η(x)。返り値 (数, 水の体積 m³ = 数 × dp³)。"""
    xs = (np.arange(int(round(Lx / dp))) + 0.5) * dp
    ys = (np.arange(int(round(W / dp))) + 0.5) * dp
    e = eta_fn(xs)
    n = 0
    for j0 in range(0, len(ys), 64):
        yy = ys[j0:j0 + 64]
        bed = GC.bed_z(xs[None, :], yy[:, None], **spec) if spec else np.full((len(yy), len(xs)), zb)
        ylo = bed + bed_gap * dp
        k_lo = np.ceil((ylo - zb) / dp - 0.5 - 1e-9)          # 最初の段 k：zb + (k+0.5)dp ≥ ylo
        k_hi = np.ceil((e[None, :] - zb) / dp - 0.5 - 1e-9)    # 段 k < k_hi：zb + (k+0.5)dp < e
        n += int(np.maximum(k_hi - np.maximum(k_lo, 0), 0).sum())
    return n, n * dp ** 3


def eta_from_npz(p):
    d = np.load(p)
    x = np.asarray(d["x"], float); e = np.asarray(d["eta"], float)
    if "h0" in d.files and abs(float(d["h0"]) - 1.0) < 1e-9:      # 無次元の表
        x = x * GC.H0; e = e * GC.H0
    return lambda xq: np.interp(np.clip(xq, x[0], x[-1]), x, e)


def table_checks(p):
    """表の確かめ：x の範囲、η(0)・η(143)・η(360)、裾、体積、流量 Q(x) = ∫u dz と c η（形を変えない波は Q = c η）、発散 ∂u/∂x + ∂w/∂z。"""
    d = np.load(p)
    x = d["x"]; z = d["z"]; eta = d["eta"]; u = d["u_ext"]; w = d["w_ext"]; c = float(d["c"]); x0 = float(d["x0"]); a = float(eta.max())
    out = dict(npz=p, sha256=GC.sha256_file(p)[:16], x_range=[float(x[0]), float(x[-1])], z_range=[float(z[0]), float(z[-1])],
               F=float(d["F"]), c=c, crest_m=a, x_crest=float(x[np.argmax(eta)]), eta_x0wall=float(eta[0]),
               eta_toe=float(np.interp(GC.RIDGE_X0, x, eta)), eta_end=float(eta[-1]))
    ahead = x > x0
    for frac in (0.1, 0.01, 0.001):
        xi = x[ahead][eta[ahead] < frac * a]
        out["tail_%g_ahead_m" % frac] = float(xi[0] - x0) if len(xi) else None
    out["volume_per_m_crest_m2"] = float(trapz(eta, x))
    out["volume_beyond_toe_frac"] = float(trapz(np.where(x > GC.RIDGE_X0, eta, 0.0), x) / trapz(eta, x))
    # 流量：水面までの積分（最後の区間は水面で切る）
    Q = np.zeros(len(x))
    for i in range(len(x)):
        zi = z[z < eta[i]]
        ui = u[:len(zi), i]
        q = trapz(ui, zi) if len(zi) > 1 else 0.0
        ue = np.interp(eta[i], z, u[:, i])
        q += 0.5 * (ui[-1] + ue) * (eta[i] - zi[-1])
        q += 0.5 * (u[0, i] + u[0, i]) * (zi[0] + GC.H0)          # 海底 −17 m から最初の段まで（z[0] = −17 なら 0）
        Q[i] = q
    big = eta > 0.05 * a
    rel = np.abs(Q[big] - c * eta[big]) / (c * a)
    out["flux_rel_err_max"] = float(rel.max()); out["flux_rel_err_rms"] = float(np.sqrt(np.mean(rel ** 2)))
    # 発散（水の中だけ、海底と水面から 0.5 m 離れた所）
    dx = x[1] - x[0]; dz = z[1] - z[0]
    du = np.gradient(u, dx, axis=1); dw = np.gradient(w, dz, axis=0)
    Z = z[:, None] * np.ones((1, len(x)))
    inside = (Z < eta[None, :] - 0.5) & (Z > -GC.H0 + 0.5) & big[None, :]
    out["div_rel_rms"] = float(np.sqrt(np.mean((du + dw)[inside] ** 2)) / max(np.sqrt(np.mean(du[inside] ** 2)), 1e-12))
    out["u_max"] = float(np.nanmax(d["u"])); out["u_crest_bed"] = float(u[0, np.argmax(eta)])
    out["lateral_velocity"] = "0（まっすぐな頂。VEX の sol_vel は横 0 を返す。曲がった頂は使わない）"
    return out


def crude_timing(A, spec_axis, x0=GC.X0_CREST, c0=None, zB_hB=2.6, dx=0.25):
    """真ん中の断面の頂の着く時刻の粗い見込み：c = √(g(h + a))、a は Green の法則 a = A h0 (h0/h)^(1/4)、a/h が zB_hB に着いた所を崩れる所とする
    （GG06 の 3D zB/hB 2.57【文献】を目安）。浅い水の近似で、分散も非線形の速さの補いも無い。順番の見込みだけ。"""
    x = x0; t = 0.0
    a0 = A * GC.H0
    while x < GC.LX:
        h = float(-GC.bed_z(x, 0.0, **spec_axis))
        a = a0 * (GC.H0 / h) ** 0.25
        if a / h >= zB_hB:
            return dict(x_b=x, t_b=t, h_b=h, a_b=a, rule="a/h ≥ %g" % zB_hB)
        t += dx / math.sqrt(GC.G * (h + a)); x += dx
    return dict(x_b=None, t_b=t, note="棚の上でも a/h が届かない（Green の法則の上限 a = %.2f m）" % (a0 * (GC.H0 / GC.SHELF_H) ** 0.25))


def cost_model():
    """FLIP46 の 3 本（粒子 0.5 m）の記録から、1 コマの計算の秒と面の秒を「粒子 100 万あたり」で合わせる（最小二乗）。【測定から計算】"""
    rows = []
    for rid in ("P05_FLIP", "P05_k1p0_W102", "P05_k0p5_W136"):
        rd = os.path.join(GC.B46_REAL, "runs", rid)
        rs = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        if not rs:
            continue
        n0 = rs[0]["particles_first"]; n1 = max(r["particles_max"] for r in rs); nf = int(cfg["f_end"])
        t5 = float(cfg["records"]["r5"]["t0"]); nsurf = nf - int(round(t5 * 24))
        rows.append(dict(run=rid, n0=n0, n1=n1, frames=nf, surf_frames=nsurf, wall=sum(r["wall_total_s"] for r in rs),
                         sim_med=rs[0]["wall_per_frame_median_s"], surf_med=rs[0]["surf_per_frame_median_s"]))
    A_ = np.array([[0.5 * (r["n0"] + r["n1"]) / 1e6 * r["frames"], 0.5 * (r["n0"] + r["n1"]) / 1e6 * r["surf_frames"]] for r in rows])
    y = np.array([r["wall"] for r in rows])
    coef, *_ = np.linalg.lstsq(A_, y, rcond=None)
    pred = A_ @ coef
    return dict(sim_s_per_Mframe=float(coef[0]), surf_s_per_Mframe=float(coef[1]), rows=rows, fit_rel_err=[float(v) for v in pred / y - 1],
                growth=[r["n1"] / r["n0"] - 1 for r in rows])


# ------------------------------------------------------------------ R3 の確かめ（numpy）
def _bed_z_ref(x, y_lat=0.0, k=GC.RIDGE_K, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H):
    """R0・R1・R2b を走らせた時の g48_common.bed_z の写し（2026-10-15 R3 の前。比べるためだけ。変えない）。"""
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    if not on:
        return np.full(np.broadcast(x, y).shape, -float(h0))
    sh = 1.0 / np.cosh(k * y / h0)
    dep = h0 - np.maximum(x - x_toe, 0.0) * sh * sh / s
    if shelf_h is not None and shelf_h > 0:
        dep = np.maximum(dep, shelf_h)
    return -dep


def _bed_grad_ref(x, y_lat=0.0, k=GC.RIDGE_K, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H):
    """R0・R1・R2b を走らせた時の g48_common.bed_grad の写し（比べるためだけ。変えない）。"""
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    x, y = np.broadcast_arrays(x, y)
    gx = np.zeros(x.shape); gy = np.zeros(x.shape)
    if not on:
        return gx, gy
    a = k * y / h0
    sh = 1.0 / np.cosh(a)
    dep = h0 - np.maximum(x - x_toe, 0.0) * sh * sh / s
    m = x > x_toe
    if shelf_h is not None and shelf_h > 0:
        m &= dep > shelf_h
    gx = np.where(m, sh * sh / s, 0.0)
    gy = np.where(m, (x - x_toe) / s * (-2.0 * sh * sh * np.tanh(a) * k / h0), 0.0)
    return gx, gy


def checks_r3():
    """R3 の試しの道具の確かめ（1 分以内）。既定の海底と箱が前と 1 bit も違わない（違えば止める）、新しい海底の形の数、谷の表、粒子と時間の見込み。"""
    out = {}
    rng = np.random.default_rng(4803)
    X = np.concatenate([rng.uniform(-20.0, 420.0, 300000), np.arange(0.0, 360.0001, 0.25)])
    Y = np.concatenate([rng.uniform(-100.0, 120.0, 300000), np.zeros(1441)])
    ex = {}
    for rid in ("R0_strip_RS_A0p3", "R1_RS_k0p35_A0p3_W85", "R2b_RS_k0p5_A0p3_W85"):
        p = os.path.join(GC.B48, "runs", rid, "cfg.json")
        if not os.path.exists(p):
            ex[rid] = dict(missing=p); continue
        cfg = json.load(open(p, encoding="utf8"))
        b = cfg["bed"]
        ref = dict(k=float(b["k"]), x_toe=float(b["x_toe"]), s=float(b["s"]), h0=float(b["h0"]), on=bool(b["on"]), shelf_h=float(b["h_sh"]))
        r = {}
        for src, sp in (("cfg_bed", GC.bed_spec(cfg)), ("cfg_parms_ctrl", GC.bed_spec(parms=cfg["parms"]))):
            z0 = _bed_z_ref(X, Y, **ref); z1 = GC.bed_z(X, Y, **sp)
            g0 = _bed_grad_ref(X, Y, **ref); g1 = GC.bed_grad(X, Y, **sp)
            r[src] = dict(z_max_abs_diff=float(np.abs(z1 - z0).max()), gx_max_abs_diff=float(np.abs(g1[0] - g0[0]).max()),
                          gy_max_abs_diff=float(np.abs(g1[1] - g0[1]).max()), bit_equal=bool(np.array_equal(z0, z1) and np.array_equal(g0[0], g1[0])
                                                                                                 and np.array_equal(g0[1], g1[1])),
                          kind=GC.bed_kind(sp))
        bx = cfg["box"]
        b48 = GC.box48(float(cfg["parms"]["dp"]), Lx=GC.LX, W=float(cfg["parms"]["W"]), zb=float(cfg["parms"]["zb"]), floor_pad=int(cfg["parms"]["floor_pad"]))
        r["box48_equals_cfg_box"] = bool(all(b48[k_] == bx[k_] for k_ in bx))
        ex[rid] = r
    out["bed_defaults_exact"] = ex
    ok_exact = all(v.get("cfg_bed", {}).get("bit_equal") and v.get("cfg_parms_ctrl", {}).get("bit_equal") and v.get("box48_equals_cfg_box")
                   for v in ex.values() if "missing" not in v) and not any("missing" in v for v in ex.values())
    out["box48_default_equals_g46_box"] = {"%g_%g" % (dp, W): bool(GC.box48(dp, Lx=GC.LX, W=W, floor_pad=FLOOR_PAD) == GC.box(dp, Lx=GC.LX, W=W, floor_pad=FLOOR_PAD))
                                           for dp, W in ((0.5, GC.W_MAIN), (0.5, GC.W_STRIP), (1.0, GC.W_MAIN))}
    # 既定が前と違えば、ここで止める（R0〜R2b と比べられなくなるため）
    assert ok_exact, "既定の海底か箱が R0・R1・R2b の cfg と違う：%s" % json.dumps(ex, ensure_ascii=False)
    assert all(out["box48_default_equals_g46_box"].values()), "box48 の既定が g46_common.box と違う"
    # 新しい海底の形
    base = dict(GC.BED_EXTRA_DEFAULTS, k=GC.RIDGE_K, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H)
    beds = {"R1_ref": dict(base), "R3_spur_channel": dict(base, **GC.TAPER_R3, **GC.CHANNEL_R3),
            "G0c_ledge_strip": dict(base, k=0.0, **GC.LEDGE_G0C), "R3L": dict(base, **GC.TAPER_R3, **GC.CHANNEL_R3, **GC.LEDGE_G0C),
            "R4h_k0p5_start": dict(base, k=0.5, **GC.TAPER_R3, **GC.CHANNEL_R3)}
    xs = np.arange(0.0, 360.0, 0.25); ys = np.arange(0.0, 85.0001, 0.25)
    Xs, Ys = np.meshgrid(xs, ys)
    shp = {}
    for nm, sp in beds.items():
        z = GC.bed_z(Xs, Ys, **sp)
        gx, gy = GC.bed_grad(Xs, Ys, **sp)
        sl = np.degrees(np.arctan(np.hypot(gx, gy)))
        chm = (Ys >= sp["ch_y0"] - 3 * sp["ch_w"]) & (Ys <= sp["ch_y0"] + 3 * sp["ch_w"]) if sp["ch_h"] > 0 else np.zeros_like(Xs, bool)
        r = dict(kind=GC.bed_kind(sp), formula=GC.bed_formula(sp), shelf_x_axis=GC.shelf_x(sp, 0.0), max_depth_m=float(-z.min()), min_depth_m=float(-z.max()),
                 max_slope_deg=float(sl.max()), max_slope_outside_channel_wall_deg=float(sl[~chm].max()),
                 max_slope_channel_wall_deg=float(sl[chm].max()) if chm.any() else None,
                 axis_depth_at={str(x_): float(-GC.bed_z(x_, 0.0, **sp)) for x_ in (143.0, 200.0, 240.0, 283.0, 290.0, 294.2, 296.0, 300.0)},
                 axis_max_abs_diff_vs_R1_m=float(np.abs(GC.bed_z(xs, 0.0, **sp) - GC.bed_z(xs, 0.0, **beds["R1_ref"])).max()),
                 depth_y_at_x={str(int(x_)): {str(int(y_)): round(float(-GC.bed_z(x_, y_, **sp)), 3) for y_ in (0, 10, 20, 35, 48, 55, 70, 84)}
                               for x_ in (200.0, 260.0, 296.0, 320.0, 340.0)},
                 out_of_channel_band_35_48_max_extra_depth_vs_no_channel_m=float(np.max(-GC.bed_z(Xs, Ys, **sp)[(Ys >= 35) & (Ys <= 48)]
                                                                                       + GC.bed_z(Xs, Ys, **dict(sp, ch_h=0.0))[(Ys >= 35) & (Ys <= 48)])))
        shp[nm] = r
    out["bed_shapes"] = shp
    out["bed_shapes_note_ja"] = "判定の書き：尾根の脇の斜面 44.5° まで、溝の壁 55.6° まで【計算、D4】。ここの値は 0.25 m の格子の勾配の最大"
    # 谷のある波の表（β 0.12）
    import g48_nwave as NW
    pn, ni = NW.make()
    out["nwave_b0p12"] = dict(made=ni, **{k: v for k, v in NW.nwave_checks(pn).items() if k != "table_checks"})
    # 粒子と時間の見込み（cfg を作って確かめるだけ。書かない）
    cm = cost48()
    out["cost48"] = cm
    est = {}
    for nm, args in (("G0a_b0p12", ("g0a",)), ("G0c", ("g0c",)), ("R3_b0p12", ("r3",)), ("R3_b0p18", ("r3", 0.18)), ("R3_b0p06", ("r3", 0.06)),
                     ("R3L", ("r3l",)), ("R4h_k0p5", ("r3", GC.BETA_R3, GC.A0, 0.5)), ("SMOKE48_R3", ("smoke",))):
        c = r3_cfg(*args)
        est[nm] = dict(run_id=c["run_id"], **precheck(c, cm))
    if os.path.exists(GC.sol_path(0.35)):
        c = r3_cfg("r3", GC.BETA_R3, 0.35)
        est["R4_A0p35"] = dict(run_id=c["run_id"], **precheck(c, cm))
    else:
        est["R4_A0p35"] = dict(note_ja="Tanaka の A 0.35 の表がまだ無いので見込まない（R4 で A 0.35 を選んだ時に g48_cfg.py r3 r3 --A 0.35 が作る）")
    out["estimates_r3"] = est
    # 凍らせた目標（P1〜P5・H）が plan_frozen.json と同じか
    pf = json.load(open(GC.B48 + "/plan/plan_frozen.json", encoding="utf8"))
    out["targets_equal_plan_frozen"] = bool(json.loads(json.dumps(TARGETS48, ensure_ascii=False)) == pf["targets"])
    out["ok"] = dict(bed_defaults_exact=bool(ok_exact), box48_default=all(out["box48_default_equals_g46_box"].values()),
                     r3_bed_above_box_floor=shp["R3_spur_channel"]["max_depth_m"] <= -GC.ZB_DEEP + 1e-9,
                     r3l_bed_above_box_floor=shp["R3L"]["max_depth_m"] <= -GC.ZB_DEEP + 1e-9,
                     r3_axis_unchanged=shp["R3_spur_channel"]["axis_max_abs_diff_vs_R1_m"] < 1e-6,
                     ledge_axis_4p5_at_283=abs(shp["G0c_ledge_strip"]["axis_depth_at"]["283.0"] - 4.5) < 1e-9
                     and abs(shp["G0c_ledge_strip"]["shelf_x_axis"] - 294.2) < 0.011,
                     nwave_table=out["nwave_b0p12"]["all_ok"], targets_equal_plan_frozen=out["targets_equal_plan_frozen"],
                     r3_precheck=est["R3_b0p12"]["ok"], r3l_precheck=est["R3L"]["ok"])
    out["all_ok"] = bool(all(out["ok"].values()))
    return out


def checks(write_json=True):
    t_start = time.time()
    out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="g48_cfg.py check")
    # (1) 箱が 2 進で割り切れる
    out["boxes"] = {}
    for nm, dp, W in (("R1", 0.5, GC.W_MAIN), ("R0", 0.5, GC.W_STRIP), ("SMOKE", 1.0, GC.W_MAIN)):
        b = GC.box(dp, Lx=GC.LX, W=W, floor_pad=FLOOR_PAD)
        out["boxes"][nm] = dict(Lx=b["Lx"], W=b["W"], cells=b["cells"], o=[b["ox"], b["oy"], b["oz"]], ok=True)
    # (2) 海底の式
    rng = np.random.default_rng(48)
    X = rng.uniform(0, 400, 20000); Y = rng.uniform(0, 120, 20000)
    sp = dict(k=0.35, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S, h0=GC.H0, on=True, shelf_h=GC.SHELF_H)
    bc = dict(even_in_y=float(np.abs(GC.bed_z(X, Y, **sp) - GC.bed_z(X, -Y, **sp)).max()),
              same_as_g46_when_shelf0=float(np.abs(GC.bed_z(X, Y, **dict(sp, shelf_h=0.0)) - G46.bed_z(X, Y, k=0.35, x_toe=GC.RIDGE_X0, s=GC.RIDGE_S)).max()),
              strip_k0_uniform=float(np.abs(GC.bed_z(X, Y, **dict(sp, k=0.0)) - GC.bed_z(X, 0.0, **dict(sp, k=0.0))).max()),
              axis_shelf_x=GC.shelf_x(sp, 0.0), axis_depth_at=dict((str(x_), float(-GC.bed_z(x_, 0.0, **sp))) for x_ in (143.0, 200.0, 250.0, 280.0, 295.0, 296.0, 300.0, 360.0)))
    # 勾配の確かめ（数値の差と比べる）
    h = 1e-4
    Xg = rng.uniform(150, 350, 4000); Yg = rng.uniform(0.5, 85, 4000)
    gx, gy = GC.bed_grad(Xg, Yg, **sp)
    ngx = (GC.bed_z(Xg + h, Yg, **sp) - GC.bed_z(Xg - h, Yg, **sp)) / (2 * h); ngy = (GC.bed_z(Xg, Yg + h, **sp) - GC.bed_z(Xg, Yg - h, **sp)) / (2 * h)
    kink = np.abs(-GC.bed_z(Xg, Yg, **sp) - GC.SHELF_H) < 1e-3
    bc["grad_max_err"] = float(max(np.abs(gx - ngx)[~kink].max(), np.abs(gy - ngy)[~kink].max()))
    out["bed_formula"] = bc
    # (3) 尾根の形の数：棚の幅・横の水深・斜面の角
    shape = {}
    yy = np.arange(0.0, 90.0001, 0.05)
    for k in (0.0, 0.25, 0.35, 0.5):
        s_ = dict(sp, k=k)
        r = dict(shelf_x_axis=GC.shelf_x(s_, 0.0))
        for x_ in (280.0, 296.0, 300.0, 310.0, 330.0, 350.0):
            dep = -GC.bed_z(x_, yy, **s_)
            row = {}
            for lev in (1.7, 3.4, 5.0):
                m = dep <= lev + 1e-9
                row["half_width_h<=%g" % lev] = float(yy[np.argmin(m)] if not m.all() else yy[-1]) if m[0] else 0.0
            row.update({"depth_y%d" % yv: float(-GC.bed_z(x_, float(yv), **s_)) for yv in (20, 32, 40, 70, 84)})
            r["x%d" % int(x_)] = row
        Xs, Ys = np.meshgrid(np.arange(143.0, 360.0, 0.5), np.arange(0.0, 85.0, 0.25))
        gx_, gy_ = GC.bed_grad(Xs, Ys, **s_)
        r["max_slope_deg"] = float(np.degrees(np.arctan(np.sqrt(gx_ ** 2 + gy_ ** 2).max())))
        dside = -GC.bed_z(np.arange(143.0, 340.0001, 1.0)[None, :], np.arange(70.0, 84.0001, 1.0)[:, None], **s_)
        r["side_band_70_84_x<=340_depth_min"] = float(dside.min())
        shape["k%g" % k] = r
    out["bed_shape"] = shape
    # (4) 孤立波の表（A 0.3）
    p03, si = sol_table(0.3)
    out["table_A0.3"] = dict(si, **table_checks(p03))
    # 横の高さの見込み（Green の法則、横の端の水深で）【計算】
    dmin = shape["k0.35"]["side_band_70_84_x<=340_depth_min"]
    out["side_crest_green_m"] = [0.3 * GC.H0 * (GC.H0 / d) ** 0.25 for d in (GC.H0, dmin)]
    out["crude_timing_axis"] = {"A0.3": crude_timing(0.3, sp), "A0.4": crude_timing(0.4, sp), "A0.25": crude_timing(0.25, sp)}
    # (5) 粒子の数と時間（FLIP46 の 3 本で数え方を合わせる）
    cal = []
    p06 = G46.SOL_TANAKA
    if os.path.exists(p06):
        e06 = eta_from_npz(p06)
        for rid, k, W in (("P05_FLIP", 0.25, 68.0), ("P05_k1p0_W102", 1.0, 102.0), ("P05_k0p5_W136", 0.5, 136.0)):
            n, V = count_particles(dict(k=k, x_toe=G46.RIDGE_X0, s=G46.RIDGE_S, h0=GC.H0, on=True, shelf_h=0.0), G46.LX_PLAN, W, 0.5, e06)
            rj = os.path.join(GC.B46_REAL, "runs", rid, "run_c00001.json")
            meas = json.load(open(rj, encoding="utf8"))["particles_first"] if os.path.exists(rj) else None
            cal.append(dict(run=rid, model=n, measured_first=meas, ratio=(meas / n) if meas else None))
    out["particle_count_calibration"] = cal
    ratio = float(np.mean([c["ratio"] for c in cal if c["ratio"]])) if cal else 1.0
    cm = cost_model()
    out["cost_model"] = cm
    growth = float(np.mean(cm["growth"]))
    e03 = eta_from_npz(p03)
    est = {}
    for nm, k, W, t_end, t5 in (("R0", 0.0, GC.W_STRIP, T_END, 10.0), ("R1", 0.35, GC.W_MAIN, T_END, 10.0), ("R2a", 0.25, GC.W_MAIN, T_END, 10.0),
                                ("R2b", 0.5, GC.W_MAIN, T_END, 10.0), ("R2d_A0.4", 0.35, GC.W_MAIN, 17.5, 10.0)):
        ef = e03
        if nm == "R2d_A0.4":
            p04 = GC.sol_path(0.4)
            ef = eta_from_npz(p04) if os.path.exists(p04) else (lambda xq, _e=e03: _e(xq) * 4.0 / 3.0)
        n, V = count_particles(dict(sp, k=k), GC.LX, W, 0.5, ef)
        nf = GC.frames_for(0, t_end); ns = nf - int(round(t5 * 24))
        nbar = n * ratio * (1 + 0.5 * growth) / 1e6
        wall = cm["sim_s_per_Mframe"] * nbar * nf + cm["surf_s_per_Mframe"] * nbar * ns
        est[nm] = dict(particles_model=n, particles_first_est=int(n * ratio), particles_max_est=int(n * ratio * (1 + growth)), water_m3=V,
                       frames=nf, surf_frames=ns, wall_min_est=wall / 60.0)
    out["estimates"] = est
    out["ok"] = dict(
        bed_even=bc["even_in_y"] < 1e-9, bed_same_g46=bc["same_as_g46_when_shelf0"] < 1e-9, strip_uniform=bc["strip_k0_uniform"] < 1e-9,
        shelf_axis_296=abs(bc["axis_shelf_x"] - 296.0) < 1e-6, grad=bc["grad_max_err"] < 1e-5,
        # 計画の「横の端 |y| 70〜84 m の水深 14.5〜15.5 m」は x ≤ 340 m では言い過ぎ（y 70 m・x 340 m で 13.0 m【計算】）。
        # 目的は「横の頂が Green の法則で 5.6 m を越えない（砕けない）」なので、それを確かめる
        side_green_le_5p6=max(out["side_crest_green_m"]) <= 5.6,
        table_covers_0_360=out["table_A0.3"]["x_range"][0] <= 0.0 and out["table_A0.3"]["x_range"][1] >= GC.LX,
        flux=out["table_A0.3"]["flux_rel_err_max"] < 0.01,
        particles_le_5M=est["R1"]["particles_max_est"] <= 5.0e6, wall_le_25min=est["R1"]["wall_min_est"] <= 25.0)
    # R3 の試しの道具（既定の海底・箱が前と同じことを assert で確かめる）
    out["r3"] = checks_r3()
    out["ok"]["r3_tools"] = out["r3"]["all_ok"]
    out["all_ok"] = bool(all(out["ok"].values()))
    out["elapsed_s"] = round(time.time() - t_start, 1)
    if write_json:
        p = GC.B48 + "/plan/precheck.json"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(out, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
        out["path"] = p
    return out


def summary(o):
    t = o["table_A0.3"]; e = o["estimates"]
    L = ["all_ok %s  %s" % (o["all_ok"], o["ok"]),
         "table A0.3: F %.5f c %.3f crest %.3f m at x %.2f; eta(0) %.4f eta(143) %.3f eta(360) %.2e; tail 10/1/0.1%% ahead %s/%s/%s m; "
         "beyond-toe volume %.1f%%; flux err max %.2e rms %.2e; div rel rms %.2e" % (
             t["F"], t["c"], t["crest_m"], t["x_crest"], t["eta_x0wall"], t["eta_toe"], t["eta_end"], t["tail_0.1_ahead_m"], t["tail_0.01_ahead_m"],
             t["tail_0.001_ahead_m"], 100 * t["volume_beyond_toe_frac"], t["flux_rel_err_max"], t["flux_rel_err_rms"], t["div_rel_rms"]),
         "side crest (Green) flat/at min side depth: %s" % ["%.2f" % v for v in o["side_crest_green_m"]],
         "crude timing: %s" % {k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in o["crude_timing_axis"].items()},
         "particle calibration: %s" % [(c["run"], c["model"], c["measured_first"], round(c["ratio"], 4) if c["ratio"] else None) for c in o["particle_count_calibration"]],
         "cost model: sim %.3f s/Mframe, surf %.3f s/Mframe, fit err %s, growth %s" % (
             o["cost_model"]["sim_s_per_Mframe"], o["cost_model"]["surf_s_per_Mframe"], ["%+.3f" % v for v in o["cost_model"]["fit_rel_err"]],
             ["%.3f" % v for v in o["cost_model"]["growth"]])]
    for k, v in e.items():
        L.append("  %s: particles first %.2f M max %.2f M, water %.0f m3, frames %d, wall %.1f min" % (
            k, v["particles_first_est"] / 1e6, v["particles_max_est"] / 1e6, v["water_m3"], v["frames"], v["wall_min_est"]))
    for k, v in o["bed_shape"].items():
        L.append("  bed %s: shelf x %.1f, max slope %.1f deg, side depth min %.2f, x296 %s, x300 y32/y40 %.2f/%.2f" % (
            k, v["shelf_x_axis"], v["max_slope_deg"], v["side_band_70_84_x<=340_depth_min"],
            {kk: round(vv, 1) for kk, vv in v["x296"].items() if kk.startswith("half")}, v["x300"]["depth_y32"], v["x300"]["depth_y40"]))
    if o.get("r3"):
        L.append(summary_r3(o["r3"]))
    return "\n".join(L)


def summary_r3(r):
    L = ["R3 tools all_ok %s  %s" % (r["all_ok"], r["ok"])]
    for rid, v in r["bed_defaults_exact"].items():
        L.append("  default bed vs %s: %s" % (rid, {k: (vv.get("bit_equal") if isinstance(vv, dict) else vv) for k, vv in v.items()}))
    for nm, v in r["bed_shapes"].items():
        L.append("  bed %s (%s): shelf x %.2f, depth %.2f-%.2f m, max slope %.1f deg (outside channel wall %.1f, channel wall %s), axis diff vs R1 %.1e m, "
                 "extra depth in |y| 35-48 %.3f m" % (nm, v["kind"], v["shelf_x_axis"], v["min_depth_m"], v["max_depth_m"], v["max_slope_deg"],
                                                       v["max_slope_outside_channel_wall_deg"], None if v["max_slope_channel_wall_deg"] is None else round(v["max_slope_channel_wall_deg"], 1),
                                                       v["axis_max_abs_diff_vs_R1_m"], v["out_of_channel_band_35_48_max_extra_depth_vs_no_channel_m"]))
    nw = r["nwave_b0p12"]
    L.append("  nwave b0.12: ok %s, crest %.3f m (Tanaka %.3f), eta min %.3f m at x %.1f, trough amp %.3f m, Green bound on shelf %.3f m" % (
        nw["all_ok"], nw["crest_combined_m"], nw["crest_tanaka_m"], nw["trough"]["eta_min_m"], nw["trough"]["x_eta_min_m"], nw["trough"]["trough_amp_m"],
        nw["trough"]["green_upper_bound_on_shelf_m"]))
    cm = r["cost48"]
    L.append("  cost48: ratio first/model %.4f, growth max %.4f, s per Mpart-frame %.4f-%.4f, rows %s" % (
        cm["ratio_first"], cm["growth_max"], cm["coef_lo"], cm["coef_hi"], [(x["run"], x["particles_model"], x["particles_first"], x["particles_max"]) for x in cm["rows"]]))
    for nm, v in r["estimates_r3"].items():
        if "particles_max_est" not in v:
            L.append("  %s: %s" % (nm, v.get("note_ja"))); continue
        L.append("  %s %s: particles model %.3f M, first %.3f M, max %.3f M, frames %d, cells x%.3f, wall %s-%s min (cells upper %s), ok %s" % (
            nm, v["run_id"], v["particles_model"] / 1e6, v["particles_first_est"] / 1e6, v["particles_max_est"] / 1e6, v["frames"], v["cells_ratio_vs_R1"],
            None if "wall_min_est_lo" not in v else round(v["wall_min_est_lo"], 1), None if "wall_min_est_hi" not in v else round(v["wall_min_est_hi"], 1),
            None if "wall_min_upper_cells" not in v else round(v["wall_min_upper_cells"], 1), v["ok"]))
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ready", "check", "r2", "one", "freeze", "r3", "freeze_r3"])
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--kind", choices=["3d", "strip", "smoke"], default="3d")
    ap.add_argument("--k", type=float, default=GC.RIDGE_K)
    ap.add_argument("--A", type=float, default=0.3)
    ap.add_argument("--W", type=float, default=None)
    ap.add_argument("--t_end", type=float, default=None, help="既定 18.5 s（r3 は 17.5 s）")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--force", action="store_true", help="freeze：plan_frozen.json を書き直す（凍らせた目標を変える時だけ。理由を記録に書くこと）")
    # R3 の試し（one の選び。既定は無し）
    ap.add_argument("--wave", choices=["tanaka", "nwave"], default="tanaka", help="nwave：Tanaka の頂 ＋ 前の谷（g48_nwave.py）")
    ap.add_argument("--beta", type=float, default=GC.BETA_R3, help="谷の深さ β（谷 = β × 頂。計画の範囲 0.06〜0.18）")
    ap.add_argument("--dk", type=float, default=GC.DK_R3, help="谷の中心 d = dk/k_s（既定 1.6 → 65.4 m）")
    ap.add_argument("--kend", type=float, default=None, help="尾根の先細りの終わりの k（R3 は 1.0）")
    ap.add_argument("--xk1", type=float, default=GC.TAPER_R3["xk1"])
    ap.add_argument("--xk2", type=float, default=GC.TAPER_R3["xk2"])
    ap.add_argument("--ch", default=None, help="溝 y0,w,h,x0,lx（R3 は 55,4,25,150,40）")
    ap.add_argument("--zfloor", type=float, default=None, help="箱の底 zb（m。溝のある R3 は −25）")
    ap.add_argument("--ledge", default=None, help="段 s1,dL,s2（G0c・R3L は 11.2,2.8,4）")
    ap.add_argument("--queue", default=None, help="判定の queue の名前（G0a・R3 など。cfg の case に書く）")
    ap.add_argument("--prefix", default=None, help="r3：run_id の頭（R4・R5 など）")
    a = ap.parse_args()
    t_end_arg = a.t_end
    paths = []
    if a.what == "ready":
        for c in (R0(), R3d(GC.RIDGE_K, 0.3), R3d(0.25, 0.3, prefix="R2a"), R3d(0.5, 0.3, prefix="R2b")):
            paths.append(write(c))
        paths.append(write(SMOKE(), "smoke/ready"))
        fp, st = freeze()
        print("plan_frozen", fp, st)
        o = checks()
        print(summary(o))
    elif a.what == "check":
        o = checks()
        print(summary(o))
    elif a.what == "freeze":
        print(freeze(force=a.force))
    elif a.what == "r2":
        for c in r2_cfgs(a.name):
            paths.append(write(c))
    elif a.what == "r3":
        c = r3_cfg(a.name, beta=a.beta, A=a.A, k=a.k, prefix=a.prefix, tag_=a.tag, dk=a.dk)
        paths.append(write_checked(c))
    elif a.what == "freeze_r3":
        print(freeze_r3(force=a.force))
    else:
        W = a.W if a.W is not None else (GC.W_STRIP if a.kind == "strip" else GC.W_MAIN)
        k = 0.0 if a.kind == "strip" else a.k
        t_end = t_end_arg if t_end_arg is not None else T_END
        be = {}
        if a.kend is not None:
            be.update(k_end=float(a.kend), xk1=float(a.xk1), xk2=float(a.xk2))
        if a.ch:
            v = [float(s) for s in a.ch.split(",")]
            if len(v) != 5:
                raise SystemExit("--ch は y0,w,h,x0,lx の 5 つ")
            be.update(ch_y0=v[0], ch_w=v[1], ch_h=v[2], ch_x0=v[3], ch_lx=v[4])
        if a.ledge:
            v = [float(s) for s in a.ledge.split(",")]
            if len(v) != 3:
                raise SystemExit("--ledge は s1,dL,s2 の 3 つ")
            be.update(s1=v[0], dL=v[1], s2=v[2])
        wv = dict(kind="nwave", beta=float(a.beta), dk=float(a.dk)) if a.wave == "nwave" else None
        sfx = ""
        if a.kend is not None:
            sfx += "_tap%s" % tag(a.kend)
        if a.ch:
            sfx += "_ch%s" % tag(be["ch_h"])
        if a.ledge:
            sfx += "_ldg"
        if wv:
            sfx += "_b%s" % tag(a.beta)
        if a.zfloor is not None:
            sfx += "_zb%s" % tag(-a.zfloor)
        rid = a.tag or ("%s_RS_k%s_A%s_W%g%s" % (a.queue or ("R0" if a.kind == "strip" else "R1"), tag(k), tag(a.A), W, sfx))
        c = make(rid, a.kind, a.A, k, W, t_end=t_end,
                 dp=(1.0 if a.kind == "smoke" else 0.5), out_root=("smoke" if a.kind == "smoke" else "runs"),
                 note="FLIP48 %s：k %g・A %g・半幅 %g m・0〜%g s%s（g48_cfg.py one）" % (a.kind, k, a.A, W, t_end, (" " + sfx) if sfx else ""),
                 bed_extra=be or None, wave=wv, zb=a.zfloor, case_extra=(case_r3(a.queue) if a.queue else None))
        paths.append(write_checked(c, "smoke/ready" if a.kind == "smoke" else "runs/ready"))
    for p in paths:
        c = json.load(open(p, encoding="utf8"))
        print(p, "f_end", c["f_end"], "box", c["box"]["Lx"], c["box"]["W"], c["box"]["cells"], "zb", c["parms"]["zb"], "k", c["parms"]["ridge_k"],
              "A", c["solitary"]["H0_nd"], "F", round(c["solitary"]["c_nd"], 5), "sol", os.path.basename(c["solitary_npz"]), "bed", c["bed"]["kind"])
        pc = c.get("precheck")
        if pc:
            print("  precheck ok %s: particles max %.3f M, wall %s min (cells upper %s)" % (
                pc["ok"], pc["particles_max_est"] / 1e6, None if "wall_min_est_hi" not in pc else round(pc["wall_min_est_hi"], 1),
                None if "wall_min_upper_cells" not in pc else round(pc["wall_min_upper_cells"], 1)))
