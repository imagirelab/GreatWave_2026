# -*- coding: utf-8 -*-
"""FLIP45：計算の設定（cfg.json）を作る（py -3.10。numpy だけ）。
FLIP44 の g44_cfg.py（変えていない）の考えを写して新しく書いた（計画 plan_ja.md §2・§3・§5・§10.1）。
設定は plan_numbers.json（凍結）・入口の利得の記録（Unity/Build/FLIP45/gain/gain45.json。煙の試しの後に決めた物）・V2 の決め（並び A・B）
だけから作る。2 進で割り切れない粒子は拒む（g45_common.check_dp）。利得の記録がない時は本番と下見の設定を作らない（計画 §4.1：
利得は V1 の前に決めて record_ja.md に書く）。
  make(name, ...)        plan_numbers.json の runs の 1 本（V1・V2・V1h・V4・M1_L2・M1_L1・M1h_*・RPT05・X60_*・M1c_*・F40_L1・X45_*・M1f_L2 など）
  smoke(kind, ...)       煙の試し（S1・S2b・S2a・S2c・S3・S3b・S5・S6・S10）
  table_for(cfg)         入口の表（npz）を計算の置き場所に作る（作ってあれば SHA-256 を確かめて使う）
立ち上げの形（2026-10-12 12:45 に足した。別の者の確かめ check_ja.md の F1）：cfg の table.ramp に "tanh"（tanh(t/T)。計画 §4.1、全部の計算）か
"tanh_s"（0.5{1 + tanh(2t/T − 3)}。計画 §2 の V3 だけ）を書き、table_for が g45_inlet_table.build に渡す。解析（g45_analyze.py）も同じ値で線形の目標を作る。
使い方：py -3.10 g45_cfg.py <name> [--out <cfg.json>] [--root runs|smoke]   （設定を書いて表を作るだけ。計算は走らせない）
"""
import os, sys, json, math, copy, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

T = GC.T
LAMBDA = GC.L0
# 立ち上げの形を既定（tanh）から替える計算（計画 §2 の表の V3 の行：「立ち上げを 0.5{1 + tanh(2t/T − 3)} にした V1」）。ほかは全部 tanh
RAMP_BY_RUN = {"V3": "tanh_s"}


def parms_for(layout, dp, t_off, **over):
    """CTRL の値（Houdini の座標：x・上 y・横 z）。layout は plan の layouts の形（x・y・inlet・exit・side・side_gen・side_sw・crop_x・crop_y）。"""
    b = GC.box(layout, dp)
    band_in = b["inlet"][1] - b["inlet"][0]
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=GC.Z_BOTTOM, Hz=b["Hz"], h0=GC.D, k0=GC.K0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"],
             maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=float(t_off),
             in_on=1.0, in0=b["inlet"][0], in1=b["inlet"][1], in_tgt=1.0,
             sd_on=1.0, sd0=b["side"][0], sd1=b["W"], sd_gen=b["side_gen"], sd_sw=b["side_sw"],
             ex0=b["exit"][0], ex1=b["x1"], ex_mode=0.0, relax_g=1.0, dt0=1.0 / 24.0, abs_sigma=GC.SIGMA_ABS, abs_pow=2.0,
             wall_taper_m=0.25 * band_in, amp_gain=1.0, tab_on=1.0, in_gain=1.0, sd_gain=1.0,
             surf_layer_m=0.0, mirror_m=1.0, surf_vox_scale=1.0,
             crop_x0=float(layout.get("crop_x", [b["inlet"][1], b["exit"][0]])[0]),
             crop_x1=float(layout.get("crop_x", [b["inlet"][1], b["exit"][0]])[1]),
             crop_z1=float(layout.get("crop_y", [0.0, b["side"][0]])[1]), surf_ycut=-12.0, surf_keep_vox=1.0)
    p.update(over)
    return p, b


def band_gains(dp, gain_file):
    """入口の利得の記録の方法が inlet_band_scalar（入口の帯だけに 1/r0(dp) を掛ける）なら CTRL の in_gain・sd_gain を返す。ほかは空。"""
    if not gain_file or not os.path.exists(gain_file):
        return {}
    g = json.load(open(gain_file, encoding="utf-8"))
    if g.get("method") != "inlet_band_scalar":
        return {}
    return dict(in_gain=float(g["in_gain"][repr(float(dp))]), sd_gain=float(g.get("sd_gain", 1.0)))


def gain_record(required=True):
    if os.path.exists(GC.GAIN_FILE):
        return json.load(open(GC.GAIN_FILE, encoding="utf-8"))
    if required:
        raise SystemExit("入口の利得の記録 %s がない。煙の試し S2b・S2a の後に決めて書く（計画 §4.1）。本番と下見の設定は作らない" % GC.GAIN_FILE)
    return None


def run_dir(rid, root):
    return os.path.join(GC.B45, root, rid).replace("\\", "/")


def table_for(cfg, force=False):
    """cfg["table"] の spec から npz を作る（計算の置き場所の table.npz）。返り値 cfg（npz・sha を書き足した物）。"""
    import g45_inlet_table as IT
    tb = cfg["table"]
    rd = run_dir(cfg["run_id"], cfg.get("out_root", "runs"))
    os.makedirs(rd, exist_ok=True)
    npz = tb.get("npz") or os.path.join(rd, "table.npz").replace("\\", "/")
    spec = dict(target=tb["target"], x=tb["x_range"], y=tb["y_range"], t=tb["t_range"], dp=tb.get("dp"), gain=tb.get("gain_sha"))
    ramp = tb.get("ramp", "tanh")
    if ramp != "tanh":
        spec["ramp"] = ramp            # 既定の立ち上げの表の印は前と同じ形（作ってある煙の試しの表をそのまま使える）
    want = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    stamp = npz + ".spec.json"
    if os.path.exists(npz) and os.path.exists(stamp) and not force and open(stamp, encoding="utf-8").read() == want:
        pass
    else:
        gainrec = json.load(open(tb["gain_file"], encoding="utf-8")) if tb.get("gain_file") else None
        IT.build(tb["target"], tb["x_range"], tb["y_range"], tb["t_range"], dp=tb.get("dp"), gainrec=gainrec, out=npz, note=cfg["run_id"],
                 ramp_kind=ramp)
        open(stamp, "w", encoding="utf-8").write(want)
    tb["npz"] = npz
    tb["sha256"] = GC.sha256_file(npz)
    return cfg


def stop_rule(t_from):
    return dict(after_s=T, tip_wait_s=T, tip_on=True, t_from=float(t_from), Lc=LAMBDA, still_offset_m=None)


def records_for(layout, b, t_surf0, r4_t0=None, r3_z=33.0):
    vx = layout.get("vdb_x", [100.0, b["exit"][0]])
    return dict(r2=True, r3_z=r3_z, r4=dict(x=[float(vx[0]), float(vx[1])], z1=float(layout.get("crop_y", [0.0, b["side"][0]])[1]),
                                            y0=-12.0, y1=GC.Z_BOTTOM + b["Hz"], clip_vox=6.0, t0=float(r4_t0 if r4_t0 is not None else t_surf0)),
                r5=dict(t0=float(t_surf0), every=1), block=120, r4_block=24)


# ------------------------------------------------------------------ 本番・下見（plan_numbers.json の runs）
def make(name, root="runs", plan=None, gain_file=None, overrides=None):
    plan = plan or GC.load_plan()
    R = {r["name"]: r for r in plan["runs"]}
    if name not in R:
        raise SystemExit("plan_numbers.json の runs に %s がない" % name)
    r = R[name]
    if r["kind"] == "infeasible":
        raise SystemExit("%s は計画で走らせない（kind infeasible）" % name)
    dp = GC.check_dp(r["dp"])
    L = plan["layouts"][r["layout"]]
    gf = gain_file or GC.GAIN_FILE
    if not os.path.exists(gf):
        raise SystemExit("入口の利得の記録 %s がない。煙の試し S2b・S2a の後に決めて書く（計画 §4.1）。設定は作らない" % gf)
    t0 = float(r["t0_s"])
    over = {}
    if name.startswith(("M1h", "V1h")):
        over.update(cfl=0.5, pcfl=0.375)                 # CFL 半分（計画 §2）
    over.update(band_gains(dp, gf))
    over["surf_layer_m"] = 2.5        # 面（R5）は水面から 2.5 m の薄い層の粒子から作る（煙の試し S6 で、全体から作った面との差 p99 0.033 m・0.0000 m。読み方 R20）
    if dp < 0.2:
        over["surf_vox_scale"] = 0.25 / dp   # 粒子 181/1024 m の計算も、比べのため面の格子は 0.25 m（計画 §5）
    p, b = parms_for(L, dp, t0 if not name.startswith("M1h") else (-2.0 if r["layout"].startswith("L1") else 12.0), **over)
    t_cap = float(r["t_cap_s"])
    t_off = p["t_off"]
    f_end = GC.frames_for(t_off, t_cap)
    t_surf0 = 40.0 if name.startswith("RPT") else float(plan["cost_model"]["t_surf0_s"])
    onset_lo = plan["cost_model"]["onset_lo_s"].get(r["case"], 40.0)
    cfg = dict(run_id=name, out_root=root, stage="FLIP45", kind=r["kind"], case=dict(name=r["case"], layout=r["layout"], plan_run=r),
               f_start=1, f_first=1, f_end=f_end, parms=p, box=b, solver=dict(veltransfer="apic", donarrowband=0),
               table=dict(target=r["case"], x_range=[b["x0"], b["side_sw"] + 1.0], y_range=[0.0, b["W"]], t_range=[t_off, t_cap + 0.5],
                          dp=dp, gain_file=gf, gain_sha=GC.sha256_file(gf), ramp=RAMP_BY_RUN.get(name, "tanh")),
               records=records_for(L, b, t_surf0), ckpt_on=1, ckpt_every=240, ckpt_list=[240, 120, 96, 72, 48, 36, 24, 12],
               wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0, max_hours=float(r["max_hours"]),
               stop_touchdown=None if name.startswith("RPT") else stop_rule(max(t_off + 2.0, 0.8 * onset_lo - 7.0)),
               level_box=[max(b["x0"], b["inlet"][1]) + 4.0, b["exit"][0] - 4.0, 0.0, b["side"][0] - 2.0],
               fieldbox_frames=[2], pstats_frames=[2],
               note="FLIP45 %s：%s" % (name, r.get("what_ja", "")))
    if name.startswith("M1h"):
        cfg["from_ckpt"] = dict(run=name.replace("M1h", "M1"), rule="onset_minus_7s",
                                note_ja="M1 の途中保存（巻き始めの 7 s 前より前の最後の物）から。g45_queue.py が M1 の解析の後に frame を入れる")
        cfg["still_offset_from"] = name.replace("M1h", "M1")
    if overrides:
        cfg.update(overrides)
    return cfg


# ------------------------------------------------------------------ 煙の試し
def smoke(kind, dp=0.5, root="smoke", tag=None, gain_file=None, **kw):
    """煙の試しの設定（計画 §10.2）。返り値 cfg（表は table_for で作る）。"""
    dp = GC.check_dp(dp, smoke=True)
    rid = tag or ("%s_dp%s" % (kind, repr(dp).replace(".", "p")))
    base = dict(run_id=rid, out_root=root, stage="FLIP45", kind="smoke", f_start=1, f_first=1, solver=dict(veltransfer="apic", donarrowband=0),
                ckpt_on=0, ckpt_every=240, wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0, fieldbox_frames=[2], pstats_frames=[2])
    if kind == "S1":          # 3D の静かな水：72 × 36 × 20 m、y = 0 の壁、24〜48 コマ（帯は目標 0 のまま動かす）
        L = dict(x=[0.0, 72.0], y=[0.0, 36.0], inlet=[0.0, 18.0], exit=[54.0, 72.0], side=[27.0, 36.0], side_gen=200.0, side_sw=230.0,
                 crop_x=[18.0, 54.0], crop_y=[0.0, 27.0], vdb_x=[18.0, 54.0])
        p, b = parms_for(L, dp, 0.0, amp_gain=0.0)
        nfr = int(kw.get("frames", 48))
        c = dict(base, parms=p, box=b, f_end=nfr, table=dict(target={"kind": "zero"}, x_range=[0.0, b["x1"]], y_range=[0.0, b["W"]],
                 t_range=[0.0, nfr / 24.0 + 0.5], dp=dp), records=dict(r2=True, r3_z=18.0, r4=None, r5=None),
                 fieldbox_frames=[2], pstats_frames=[2, nfr], level_box=[0.0, 72.0, 0.0, 36.0],
                 note="煙の試し S1：3D の静かな水（粒子 %s m）" % dp)
        return c
    if kind in ("S2b", "S3", "S3b"):     # 2D の板（横は格子 4 個、両側は閉じた壁）
        Ly = 4 * 2 * dp
        if kind == "S2b":
            # 計画の箱は x 0〜180 m（出口の帯 144〜180 m）。2026-10-12 の 1 回目で、出口の帯からの跳ね返りが x 56 m に 35 s ごろ戻り、粒子 0.177 m で
            # 2 点の差が 0.030（幅 0.02）になったので、出口の帯を 216〜252 m へ下げた箱（Lx 252）で測り直す（読み方・計画から変えた所 R13。幅は変えない）
            Lx2 = float(kw.get("Lx", 252.0))
            L = dict(x=[0.0, Lx2], y=[0.0, Ly], inlet=[0.0, 36.0], exit=[Lx2 - 36.0, Lx2], side=[1e3, 1e3], side_gen=200.0, side_sw=230.0)
            tgt = {"kind": "plane", "amp": 2.0, "dir": 1.0}
            t_end = 48.0
            over = {}
            rid = tag or ("S2b_dp%s" % repr(dp).replace(".", "p") + ("" if Lx2 == 180.0 else "_x%d" % int(Lx2)))
        elif kind == "S3":
            band = float(kw.get("band", 36.0))
            Lx = 108.0 + band + 36.0
            L = dict(x=[0.0, Lx], y=[0.0, Ly], inlet=[0.0, 36.0], exit=[Lx - band, Lx], side=[1e3, 1e3], side_gen=200.0, side_sw=230.0)
            tgt = {"kind": "plane", "amp": 1.0, "dir": 1.0}
            t_end = 80.0
            over = {}
            rid = tag or "S3_b%d" % int(band)
        else:                            # S3b：右の端の帯（36 m、FLIP42 の重み）で左へ進む波を起こし、左の目標 0 の起こす帯（band）へ送る
            band = float(kw.get("band", 36.0))
            Lx = band + 108.0 + 36.0
            L = dict(x=[0.0, Lx], y=[0.0, Ly], inlet=[0.0, band], exit=[Lx - 36.0, Lx], side=[1e3, 1e3], side_gen=200.0, side_sw=230.0)
            tgt = {"kind": "plane", "amp": 1.0, "dir": -1.0}
            t_end = 80.0
            over = dict(in_tgt=0.0, ex_mode=1.0)
            rid = tag or "S3b_b%d" % int(band)
        p, b = parms_for(L, dp, 0.0, sd_on=0.0, **over)
        p["sd0"] = b["W"] + 1.0; p["sd1"] = b["W"] + 2.0
        if kind == "S3b":
            p["wall_taper_m"] = 9.0
        f_end = GC.frames_for(0.0, t_end)
        gain = None
        c = dict(base, run_id=rid, parms=p, box=b, f_end=f_end,
                 table=dict(target=tgt, x_range=[0.0, b["x1"]], y_range=[0.0, b["W"]], t_range=[0.0, t_end + 0.5], dp=dp),
                 records=dict(r2=True, r3_z=None, r4=None, r5=None, block=240), level_box=[b["x0"] + 40.0, b["x1"] - 40.0, 0.0, b["W"]],
                 note="煙の試し %s（粒子 %s m）" % (kind, dp))
        return c
    if kind in ("S2a", "S2c"):           # 斜めの組 ±θ を入口の帯と横の帯で起こす（粒子 0.5 m）
        th = float(kw["theta"])
        # 計画の箱は x 0〜180 m（出口の帯 144〜180 m）。±30° の組は x の向きに 5.4 m/s で進み、出口の帯からの跳ね返りが x 108 m に 30 s ごろ戻って
        # 24〜45 s の窓に入る【計算】。S2b と同じく、出口の帯を 192〜228 m へ下げた箱（Lx 228）で測る（跳ね返りが x 108 m に戻るのは ±30° で 45.5 s、
        # ±45° で 54 s より後。読み方・計画から変えた所 R13。点・窓・幅は変えない）
        # S2c（利得の確かめ）は、x 108 m で波が落ち着いてから 3 T の窓（37〜58 s）が取れるよう、箱を 256 m（出口の帯 220〜256 m）、
        # 58.5 s まで走らせる（S2a の 1 回目で、x 108 m の振幅が 24〜45 s の窓の中でまだ育っていたため。読み方 R13・R15）
        Lx2 = float(kw.get("Lx", 228.0 if kind == "S2a" else 256.0))
        L = dict(x=[0.0, Lx2], y=[0.0, 108.0], inlet=[0.0, 36.0], exit=[Lx2 - 36.0, Lx2], side=[72.0, 108.0], side_gen=200.0, side_sw=230.0,
                 crop_x=[36.0, Lx2 - 36.0], crop_y=[0.0, 72.0], vdb_x=[36.0, Lx2 - 36.0])
        gf = (gain_file or GC.GAIN_FILE) if kind == "S2c" else None
        p, b = parms_for(L, dp, 0.0, **band_gains(dp, gf))
        t_end = float(kw.get("t_end", 45.5 if kind == "S2a" else 58.5))
        tb = dict(target={"kind": "pair", "amp": 1.0, "theta_deg": th}, x_range=[0.0, b["x1"]], y_range=[0.0, b["W"]], t_range=[0.0, t_end + 0.5], dp=dp)
        if kind == "S2c":
            tb.update(gain_file=gf, gain_sha=GC.sha256_file(gf))
        c = dict(base, run_id=tag or ("%s_th%d" % (kind, int(th)) + ("" if Lx2 == 180.0 else "_x%d" % int(Lx2))), parms=p, box=b,
                 f_end=GC.frames_for(0.0, t_end), table=tb,
                 ckpt_on=1, ckpt_every=480, records=dict(r2=True, r3_z=None, r4=None, r5=None, block=240),
                 level_box=[40.0, 140.0, 0.0, 70.0], note="煙の試し %s：±%g° の組（粒子 %s m）" % (kind, th, dp))
        return c
    if kind == "S6b":                    # 面の試しの材料：72 × 36 m の小さな箱、粒子 0.25 m、±30° の組（1 m）を 15 s
        L = dict(x=[0.0, 72.0], y=[0.0, 36.0], inlet=[0.0, 18.0], exit=[54.0, 72.0], side=[27.0, 36.0], side_gen=200.0, side_sw=230.0,
                 crop_x=[18.0, 54.0], crop_y=[0.0, 27.0], vdb_x=[18.0, 54.0])
        p, b = parms_for(L, dp, 0.0)
        t_end = float(kw.get("t_end", 15.0))
        c = dict(base, run_id=tag or "S6b_dp%s" % repr(dp).replace(".", "p"), parms=p, box=b, f_end=GC.frames_for(0.0, t_end),
                 table=dict(target={"kind": "pair", "amp": 1.0, "theta_deg": 30.0}, x_range=[0.0, b["x1"]], y_range=[0.0, b["W"]],
                            t_range=[0.0, t_end + 0.5], dp=dp),
                 ckpt_on=1, ckpt_every=120, records=dict(r2=True, r3_z=None, r4=None, r5=None, block=240), level_box=[20.0, 50.0, 0.0, 25.0],
                 note="煙の試し S6b：面の試しの材料（粒子 %s m の小さな箱に ±30° の組）" % dp)
        return c
    if kind == "S10":                    # 入口から焦点まで（粗い）：L1 の形・F45・粒子 1.0 m（煙の試しだけ）
        plan = GC.load_plan()
        L = plan["layouts"]["L1"]
        p, b = parms_for(L, dp, -2.0)
        t_end = float(kw.get("t_end", 56.0))
        gf = gain_file
        tb = dict(target="F45", x_range=[b["x0"], b["side_sw"] + 1.0], y_range=[0.0, b["W"]], t_range=[-2.0, t_end + 0.5], dp=dp)
        if gf:
            tb.update(gain_file=gf, gain_sha=GC.sha256_file(gf))
        c = dict(base, run_id=tag or "S10_dp%s" % repr(dp).replace(".", "p"), parms=p, box=b, f_end=GC.frames_for(-2.0, t_end), table=tb,
                 ckpt_on=1, ckpt_every=240, records=records_for(L, b, float(kw.get("t_surf0", 40.0)), r4_t0=40.0),
                 stop_touchdown=stop_rule(30.0), level_box=[40.0, 300.0, 0.0, 70.0],
                 note="煙の試し S10：F45 の入口から焦点まで（粒子 %s m、粗い。道具の通しの確かめで、結果ではない）" % dp)
        return c
    if kind == "S5":                     # 区切った起動：L1・粒子 0.5 m・120 コマ
        plan = GC.load_plan()
        L = plan["layouts"]["L1"]
        p, b = parms_for(L, dp, -2.0)
        gf = gain_file
        tb = dict(target="F45", x_range=[b["x0"], b["side_sw"] + 1.0], y_range=[0.0, b["W"]], t_range=[-2.0, 4.0], dp=dp)
        if gf:
            tb.update(gain_file=gf, gain_sha=GC.sha256_file(gf))
        c = dict(base, run_id=tag or "S5_single", parms=p, box=b, f_end=120, table=tb, ckpt_on=1, ckpt_every=12,
                 records=dict(r2=True, r3_z=33.0, r4=None, r5=None, block=120), level_box=[40.0, 300.0, 0.0, 70.0],
                 note="煙の試し S5：区切った起動（L1・粒子 0.5 m・120 コマ）")
        return c
    raise SystemExit("知らない煙の試し %s" % kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("--out"); ap.add_argument("--root", default="runs")
    ap.add_argument("--no-table", action="store_true")
    a = ap.parse_args()
    GC.unthrottle_self()
    cfg = make(a.name, root=a.root)
    if not a.no_table:
        cfg = table_for(cfg)
    out = a.out or os.path.join(run_dir(cfg["run_id"], a.root), "cfg_ready.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(cfg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
