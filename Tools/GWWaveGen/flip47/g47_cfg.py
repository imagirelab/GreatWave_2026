# -*- coding: utf-8 -*-
"""FLIP47：計算の設定（cfg.json）を作る（py -3.10。numpy だけ）。FLIP46 の g46_cfg.py の考えを写して新しく書いた。
計画：BigWave_Recipes_ja.md §5.1 E1a（Feddersen・Hanson・Mostert・Fincham 2024、JFM 1000 A48 を h0 19 m に）。
  領域 full ：x 0〜1130 m（平ら 0〜570 m、勾配 0.0693 で 742.45 m まで、水深 7.049 m の棚が 1130 m の壁まで）。GN の孤立波 a0/h0 0.6 の頂 x0 285 m。
  領域 short：x 380〜893 m（20〜47 h0）、頂 x0 475 m（25 h0）。崩れる位置と Hb が粒子 0.25 m で full と 5% 以内で合えば、細かい段は short で回す。
  海底は折れ線の点の並び（cfg の bed。[x, 水深]）。同じ並びを short にも使う（箱で切るだけ）。
終わりの時刻：頂の走る時間の目安（g47_common.travel_estimate、Green の式で上の目安）で崩れ（x 790 m ≈ 41.5 h0）の時刻を出し、
  着水まで +2 s、着水の後 +2 s、余り +3 s。計算の中の着水の読み（stop_touchdown、after_s 2 s）がそれより先に止める。
  目安：full 30.6 s で崩れ → 38 s（913 コマ）、short 19.6 s → 27 s（649 コマ）。着水の読みは目安の 8 s 前から（t_from）。
  確かめ（2026-10-12、E1a_full_dp0p5、粒子 0.5 m）：前の面が縦 約 26.6 s（x 約 760 m）、着水（閉じた空気の穴）28.33 s（コマ 681、頂 x 789.5 m = 41.6 h0）、
  計算の中の読みで 30.33 s（コマ 729）に止まった。目安は崩れを約 4 s 遅く見ていた（Green の式の振幅が大きすぎる側）が、止め方は読みに任せるので足りる。
使い方：
  py -3.10 g47_cfg.py ready                       runs/ready/E1a_{full,short}_dp0p5.json・_dp0p25.json と smoke/ready/SA_still_dp0p5.json・SB_gn_dp0p5.json
  py -3.10 g47_cfg.py one --domain full --dp 0.125 [--kind exact] [--name X] [--out_root runs]   1 本だけ（runs/ready/<name>.json）
"""
import os, sys, json, math, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC
import g47_solitary_npz as SN

X_BREAK_GUESS = 41.5 * GC.H0          # 788.5 m（論文の風の 8 本の 40.9〜42.2 h0 の真ん中あたり）
TOUCH_LAG_S = 2.0                     # 崩れ（縦の面）から着水までの目安
AFTER_S = 2.0                         # 着水の後に走らせる時間
MARGIN_S = 3.0

TARGETS = dict(
    source="Feddersen, Hanson, Mostert & Fincham 2024, J. Fluid Mech. 1000, A48（§2.1.2 の式 (2.4)(2.5)、§3.3・§3.4、図 5〜7）。"
           "BigWave_Recipes_ja.md §5.1",
    Hb_over_h0=0.64, xbp_over_h0=[40.9, 42.2], jet_width_over_Hb=0.08, jet_width_over_h0=0.05,
    AJ_over_Hb2=0.219, AO_over_Hb2=0.352, cavity_W_over_L=0.300, jet_angle_deg=29.0, tol=0.05,
    touchdown_rule_ja="噴流のいちばん低い所と、その下の水面の縦の隙間が 0.015 h0（0.285 m）以下になる最初のコマ。格子がこれより粗い段では、最初に触れたコマ",
    differences_ja="論文の DNS は 2 相（空気あり）・表面張力（Bo 4000）・粘り（Re 4×10⁴）。私たちは水だけ・重力だけ・実物の大きさ（h0 19 m）の FLIP"
                   "（空気・表面張力・粘りなし）。噴流の太さと着水の形はこの違いで変わりうる（重力だけの実物の大きさでは細い見込みもある）")


def domain(name):
    if name == "full":
        return dict(x0=0.0, x1=GC.X_END_FULL, crest=GC.X0_CREST)
    if name == "short":
        return dict(x0=GC.SHORT_X[0], x1=GC.SHORT_X[1], crest=GC.X0_CREST_SHORT)
    raise SystemExit("知らない領域 %s" % name)


def sol_npz(kind, dom, a_over_h=GC.A_OVER_H):
    p = SN.default_path(kind, a_over_h, GC.H0, dom["crest"], 0.25)
    if not os.path.exists(p):
        SN.build(kind, a_over_h, GC.H0, dom["crest"], dom["x0"], dom["x1"], out=p)
    return p


def timing(dom, a_over_h=GC.A_OVER_H):
    tb = GC.travel_estimate(GC.BED_E1A, dom["crest"], X_BREAK_GUESS, a_over_h * GC.H0)
    t_end = math.ceil(tb + TOUCH_LAG_S + AFTER_S + MARGIN_S)
    return tb, float(t_end)


def base(run_id, dp, dom_name, out_root="runs", wave_on=1.0, kind="gn", t_end=None, note="", floor_pad=2, a_over_h=GC.A_OVER_H):
    GC.check_dp(dp)
    dom = domain(dom_name)
    b = GC.box(dp, dom["x0"], dom["x1"], GC.BED_E1A, floor_pad=floor_pad)
    tb, te = timing(dom, a_over_h)
    t_end = te if t_end is None else float(t_end)
    f_end = GC.frames_for(t_end)
    parms = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], Lz=b["Lz"], y_floor=b["y_floor"], Hy=b["Hy"], h0=GC.H0,
                 hmax=b["hmax"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0, ox=b["ox"], oy=b["oy"], oz=b["oz"],
                 bed_gap=0.5, floor_pad=float(floor_pad), wave_on=float(wave_on), relax_on=0.0, abs_on=0.0, xa0=1e9)
    on = wave_on > 0.5
    sp = sol_npz(kind, dom, a_over_h) if on else None
    C, _ = GC.gn_params(a_over_h * GC.H0, GC.H0)
    return dict(
        run_id=run_id, out_root=out_root, stage="FLIP47", kind="E1a", domain=dom_name,
        case=dict(name="E1a_Feddersen2024_%s" % dom_name, plan="Docs/Research/BigWave_Recipes_ja.md §5.1", targets=TARGETS,
                  t_break_estimate_s=round(tb, 2), x_break_guess_m=X_BREAK_GUESS,
                  timing_note_ja="t_end = 崩れの目安 %.1f s + 着水まで %.0f s + 着水の後 %.0f s + 余り %.0f s。計算の中の着水の読みが先に止める"
                                 % (tb, TOUCH_LAG_S, AFTER_S, MARGIN_S)),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=t_end, parms=parms, box=b, bed=GC.BED_E1A,
        solitary_npz=sp, solitary=dict(kind=kind if on else "none", a_over_h=a_over_h, h0=GC.H0, x0=dom["crest"], c_gn=C),
        solver=dict(veltransfer="apic", donarrowband=0),
        sec=dict(x0=b["x0"], x1=b["x1"], t0=0.0, block=120),
        stop_touchdown=(dict(after_s=AFTER_S, tip_wait_s=AFTER_S, tip_on=True, t_from=max(0.0, tb - 8.0), Lc=60.0) if on else None),
        n1_x=([dom["crest"] + 180.0, b["x1"] - 20.0] if on else [b["x0"], b["x1"]]), n1_window=[0.5, 1.5],
        init_check_frames=[1, 2, 3], init_check_dx=[-20.0, 0.0, 20.0], init_check_y=[-2.0, -9.5, -17.0],
        pstats_frames=[1, 2, int(f_end)], fieldbox_frames=[2], leak_every=24,
        ckpt_on=1, ckpt_every=120, ckpt_list=[240, 120, 48, 24], wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0,
        max_hours=4.0, wait_hython_max_s=1800, note=note)


def make(name, dp, dom_name, kind="gn", out_root="runs", veltransfer="apic"):
    c = base(name, dp, dom_name, out_root=out_root, kind=kind,
             note="FLIP47 %s：E1a（Feddersen ら 2024）%s の領域、粒子 %g m（格子 %g m）、%s の孤立波 a0/h0 0.6" % (
                 name, dom_name, dp, 2 * dp, "GN" if kind == "gn" else "厳密な"))
    c["max_hours"] = {0.5: 1.0, 0.25: 3.0, 0.125: 8.0, 0.0625: 24.0}[float(dp)]
    if veltransfer != "apic":      # 2026-10-13 板の層の差を調べる役：推奨は flip（GC.VELTRANSFER_RECOMMENDED）。既定 apic は前と同じ
        c["solver"].update(GC.solver_for(veltransfer))
        c["note"] += "、速度の受け渡し %s" % veltransfer
    return c


def smoke(kind, dp=0.5):
    tag = repr(float(dp)).replace(".", "p")
    if kind == "SA":       # 海底の上の静かな水
        c = base("SA_still_dp%s" % tag, dp, "full", out_root="smoke", wave_on=0.0, t_end=3.0,
                 note="FLIP47 煙の試し SA：E1a の海底（平ら・勾配・棚）の上の静かな水（波なし）3 s。平均の水面の動き・自由落下・海底の中への漏れ")
    elif kind == "SB":     # GN の孤立波
        c = base("SB_gn_dp%s" % tag, dp, "full", out_root="smoke", wave_on=1.0, kind="gn", t_end=2.0,
                 note="FLIP47 煙の試し SB：GN の孤立波（頂 285 m）2 s。0 コマ目（コマ 1、t = 0）の格子の流速を GN の式と、頂と ±20 m の深さ −2・−9.5・−17 m で比べる")
        c["stop_touchdown"] = None
    else:
        raise SystemExit("知らない煙の試し %s" % kind)
    c["ckpt_on"] = 0
    c["max_hours"] = 0.25
    c["wall_limit_s"] = 560
    c["pstats_frames"] = [1, 2, c["f_end"]]
    c["leak_every"] = 12
    return c


def write(c, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(c, open(path, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return path


def ready():
    out = []
    for dom in ("full", "short"):
        for dp in (0.5, 0.25):
            nm = "E1a_%s_dp%s" % (dom, repr(dp).replace(".", "p"))
            out.append(write(make(nm, dp, dom), GC.B47 + "/runs/ready/%s.json" % nm))
    for k in ("SA", "SB"):
        c = smoke(k, 0.5)
        out.append(write(c, GC.B47 + "/smoke/ready/%s.json" % c["run_id"]))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ready", "one"])
    ap.add_argument("--domain", default="full", choices=["full", "short"])
    ap.add_argument("--dp", type=float, default=0.25)
    ap.add_argument("--kind", default="gn", choices=["gn", "exact"])
    ap.add_argument("--name", default=None)
    ap.add_argument("--out_root", default="runs")
    ap.add_argument("--veltransfer", choices=["apic", "flip"], default="apic", help="one：速度の受け渡し。既定 apic（前と同じ）、推奨 flip")
    a = ap.parse_args()
    if a.what == "ready":
        ps = ready()
    else:
        nm = a.name or "E1a_%s_dp%s%s%s" % (a.domain, repr(a.dp).replace(".", "p"), "" if a.kind == "gn" else "_" + a.kind,
                                          "" if a.veltransfer == "apic" else "_" + a.veltransfer)
        ps = [write(make(nm, a.dp, a.domain, kind=a.kind, out_root=a.out_root, veltransfer=a.veltransfer),
                    GC.B47 + "/%s/ready/%s.json" % (a.out_root, nm))]
    for p in ps:
        c = json.load(open(p, encoding="utf8"))
        b = c["box"]
        print(p, "f_end", c["f_end"], "t_end", c["t_end_s"], "t_break_est", c["case"]["t_break_estimate_s"], "box x", b["x0"], b["x1"],
              "y", b["y_floor"], b["y_top"], "Lz", b["Lz"], "o", b["ox"], b["oy"], b["oz"], "sol", os.path.basename(c["solitary_npz"] or "-"))
