# -*- coding: utf-8 -*-
"""FLIP45：時間・主メモリー・置き場所の見込みを、煙の試しで測った 3D の値で出し直す（py -3.10、numpy だけ。計画 plan_ja.md §7・§10.1）。
FLIP44 の g44_hours.py（変えていない）の考えを写して新しく書いた。計画の見込み（plan_numbers.json の runs）は FLIP42 の 2D の記録からの推定だった。
ここでは次の【測った】値で置き換える（どれも粒子 0.5 m 以上の小さな箱か粗い計算の値で、3D の本番の崩れの後は測っていない）：
  - 1 粒子 1 コマの µs（3D、波あり）：S2a（粒子 0.5 m、±30°・±45° の組）の r6 の中央値と p95。ほかの粒子は S2b（2D の板、x 252 m）の
    µs(dp) ÷ µs(0.5) の比で移す。
  - 粒子の数：水の体積 ÷ dp³ × 増え（S2a の最大 ÷ 始め）。上の端は FLIP42 R3 の 1.744 倍（plan の 111.6 個/m³）との大きい方。
  - 崩れの後の重さ：FLIP42 の R2・R4d の 1.35〜3.12 倍（3D では測っていない。計画 §7.1 のまま）。粒子 181/1024 m の小刻みの増え 1.196 倍も同じ。
  - 記録を書く秒（R1〜R4 を読む・書く）：S10・S2a の起動の秒 − 計算のコマの秒 − 面の秒、を格子の数に比べて移す。
  - 面を作る秒（R5）：S6 の 1 コマの秒を、面を作る粒子の数に比べて移す。
  - 起動ごとの秒（場面を読む・途中保存を読む）：S5・S2a の chain の記録。
  - 主メモリー：S1 の 4 つの粒子と S2a の主メモリーの最大を、粒子の数の一次の式に合わせる。
  - 途中保存 1 個の大きさ：S5・S2a の v.*.sim の大きさ ÷ 粒子の数。
使い方：py -3.10 g45_hours.py   → Unity/Build/FLIP45/hours/hours45.json と hours45_ja.md
"""
import os, sys, json, glob, math, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

SM = GC.B45 + "/smoke"
OUTD = GC.B45 + "/hours"
FPS = 24.0


def r6(rd):
    out = []
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz"))):
        d = np.load(p)
        for i in range(len(d["frames"])):
            out.append({k: float(d[k][i]) for k in ("t", "wall", "npts", "ss_n", "rss", "surf_s") if k in d.files})
    return out


def recs(rd):
    return [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]


def measured():
    M = {}
    # 3D の波（S2a）
    us, grow, rss, ck = [], [], [], []
    for rid in ("S2a_th30_x228", "S2a_th45_x228"):
        rd = os.path.join(SM, rid)
        R = [r for r in r6(rd) if r["npts"] > 0]
        if not R:
            continue
        w = np.array([r["wall"] for r in R[1:]]); n = np.array([r["npts"] for r in R[1:]])
        us += list(w / n * 1e6)
        grow.append(max(n) / R[0]["npts"])
        rss += [(max(n), max(r["rss"] for r in R))]
        for p in glob.glob(os.path.join(rd, "ckpt", "v.*.sim")):
            fr = int(os.path.basename(p)[2:6])
            nn = [r["npts"] for r in R if abs(r["t"] - (fr - 1) / FPS) < 1e-6]
            if nn:
                ck.append(os.path.getsize(p) / nn[0])
    if us:
        M["us3d_wave_05"] = dict(median=float(np.median(us)), p95=float(np.percentile(us, 95)), n=len(us), src="S2a（粒子 0.5 m、波あり）")
        M["growth_3d_05"] = dict(max=float(max(grow)), values=grow)
        M["ckpt_B_per_particle"] = dict(median=float(np.median(ck)) if ck else None, n=len(ck))
    # 2D の板（S2b、x 252 m）の粒子による比
    rat = {}
    for dp in GC.PLAN_DP:
        rd = os.path.join(SM, "S2b_dp%s_x252" % repr(dp).replace(".", "p"))
        R = [r for r in r6(rd) if r["npts"] > 0]
        if R:
            rat[repr(dp)] = float(np.median([r["wall"] / r["npts"] * 1e6 for r in R[1:]]))
    if "0.5" in rat:
        M["us_ratio_vs_05_2d"] = {k: v / rat["0.5"] for k, v in rat.items()}
        M["us_2d_slab"] = rat
    # 静かな水（S1）：主メモリーの式
    pts = []
    for dp in GC.PLAN_DP:
        rd = os.path.join(SM, "S1_dp%s" % repr(dp).replace(".", "p"))
        R = [r for r in r6(rd) if r["npts"] > 0]
        if R:
            pts.append((max(r["npts"] for r in R), max(r["rss"] for r in R)))
    pts += rss
    if len(pts) >= 2:
        A = np.array(pts)
        c = np.polyfit(A[:, 0] / 1e6, A[:, 1], 1)
        M["rss_fit_GiB"] = dict(per_Mparticle=float(c[0]), base=float(c[1]), points=[[float(a), float(b)] for a, b in pts])
    # S10（粒子 1.0 m の L1・F45 の通し）：記録と面の秒、時間とともに
    rd = os.path.join(SM, "S10b_dp1p0")
    R = r6(rd); RC = recs(rd)
    if R and RC:
        cook = sum(r["wall"] for r in R); surf = sum(r.get("surf_s", 0.0) for r in R)
        launch = sum(rr.get("wall_total_s", 0.0) for rr in RC)
        g = RC[0]["grid"]["res"]
        cells = g[0] * g[1] * g[2]
        M["record_s_per_frame_per_Mcell"] = dict(value=(launch - cook - surf) / len(R) / (cells / 1e6), cells=cells, frames=len(R), src="S10")
        sv = [r.get("surf_s", 0.0) for r in R if r.get("surf_s", 0.0) > 0]
        M["S10"] = dict(s_per_frame_median=float(np.median([r["wall"] for r in R[1:]])), particles_max=max(r["npts"] for r in R),
                        surf_s_median=float(np.median(sv)) if sv else None, launches=len(RC))
    # 面（S6）
    s6 = {}
    for p in glob.glob(os.path.join(SM, "S6", "s6_*.json")):
        d = json.load(open(p, encoding="utf8"))
        s6[d["run"]] = d
    if s6:
        per = []
        for d in s6.values():
            for nm in ("layer", "whole"):
                per.append(dict(run=d["run"], kind=nm, us_per_particle=d[nm]["surface_s"] / max(d[nm]["particles_used"], 1) * 1e6, layer_m=d["layer_m"]))
        M["surf_us_per_particle"] = per
    # 起動ごとの秒（chain：起動の秒 − コマの秒の和）
    boots = []
    for rid in ("S5_chain", "S9_from_ckpt", "S2a_th30_x228", "S2a_th45_x228", "S10b_dp1p0"):
        rd = os.path.join(SM, rid)
        for rr in recs(rd):
            if rr.get("wall_launch_s") and rr.get("wall_total_s") is not None:
                boots.append(dict(run=rid, f_start=rr["f_start"], boot_s=rr["wall_launch_s"] - rr["wall_total_s"], first_frame_s=rr.get("wall_first_frame_s")))
    M["boots"] = boots
    return M


def estimate(M, plan):
    out = []
    cm = plan["cost_model"]
    # 上の端は p95 の 1.3 倍：S2a の波（振幅 2 m）より高い焦点の頂（6〜7 m）では水が速く、小刻みが増える分を測っていないため【推定】
    us_lo = M["us3d_wave_05"]["median"]; us_hi = M["us3d_wave_05"]["p95"] * 1.3
    g_lo = M["growth_3d_05"]["max"]; g_hi = max(g_lo, cm["rho_particles_per_m3_at_025"] / 64.0)
    ratio = M.get("us_ratio_vs_05_2d", {})
    rec_c = (M.get("record_s_per_frame_per_Mcell") or {}).get("value", 0.0)
    surf = [q for q in M.get("surf_us_per_particle", []) if q["kind"] == "layer"]
    surf_us = max(q["us_per_particle"] for q in surf) if surf else cm["surf_us_per_particle"]
    s_by = {("S2a" in q["run"]): q["us_per_particle"] for q in surf}           # True：粒子 0.5 m（S2a）、False：粒子 0.25 m（S6b）

    def surf_us_dp(dp):
        """面を作る 1 粒子の µs（薄い層 2.5 m）：粒子 0.5 m は S2a、0.25 m 以下は S6b、間は線形に補う。"""
        if True not in s_by or False not in s_by:
            return surf_us
        a, b = s_by[True], s_by[False]
        return float(np.interp(dp, [0.25, 0.5], [b, a]))
    boot = [b["boot_s"] + (b["first_frame_s"] or 0.0) for b in M.get("boots", []) if b["f_start"] > 1]
    boot_s = float(np.median(boot)) if boot else 60.0
    # 起動ごとの秒は、小さな試しの値（S5・S9 の途中保存 0.3 GB で約 3.5 s）に、hython の立ち上げと表の読み込みの 10 s と、途中保存の読み込み
    # （計画の 0.154 GB/s。FLIP44 の 0.54 GB を 3.5 s）を足す【推定】
    boot_fn = lambda ck_gb: 10.0 + ck_gb / 0.154
    rfit = M.get("rss_fit_GiB")
    ckb = (M.get("ckpt_B_per_particle") or {}).get("median") or cm["ckpt_B_per_particle"]
    for r in plan["runs"]:
        if r["kind"] in ("infeasible",):
            continue
        dp = float(r["dp"]); d = r["dims"]
        vol = d["Lx"] * d["Ly"] * 20.0
        n_lo = g_lo * vol / dp ** 3; n_hi = g_hi * vol / dp ** 3
        k = ratio.get(repr(dp), 1.0)
        cfl = 2.0 if r["name"].startswith(("M1h", "V1h")) else 1.0
        fine = cm["fine_factor"] if dp < 0.2 else 1.0
        s_lo = us_lo * k * n_lo * 1e-6 * cfl
        s_hi = us_hi * k * n_hi * 1e-6 * cfl * fine
        t0 = r["t0_s"]; t_on = cm["onset_lo_s"].get(r["case"], 48.2)
        t_end_lo, t_end_hi, t_cap = r["t_end_lo_s"], r["t_end_hi_s"], r["t_cap_s"]
        t_surf0 = 40.0 if r["name"].startswith("RPT") else cm["t_surf0_s"]
        cells = d["cells"][0] * d["cells"][1] * d["cells"][2]
        rec_s = rec_c * cells / 1e6
        crop_area = (d["Lx"] - 72.0) * (d["Ly"] - 36.0)
        su = surf_us_dp(dp)
        surf_s_lo = su * 1e-6 * g_lo * crop_area * 2.5 / dp ** 3      # 薄い層 2.5 m（S6 で決めた）
        surf_s_hi = su * 1e-6 * g_hi * crop_area * 2.5 / dp ** 3 * 1.3

        boot_s = boot_fn(ckb * n_hi / 1e9)

        def hours(t_end, s_pre, post_m, surf_s, chain):
            if r["name"].startswith("RPT"):
                pre = (min(t_on, t_end) - t0) * FPS; post = max(0.0, t_end - t_on) * FPS
            else:
                pre = max(0.0, min(t_on, t_end) - t0) * FPS; post = max(0.0, t_end - max(t_on, t0)) * FPS
            fr = pre + post
            sf = max(0.0, t_end - max(t_surf0, t0)) * FPS
            sec = (pre * s_pre + post * s_pre * post_m + sf * surf_s + fr * rec_s) * chain
            launches = max(1, math.ceil(sec / 1740.0))
            return (sec + launches * boot_s) / 3600.0, launches
        h_lo, l_lo = hours(t_end_lo, s_lo, cm["m_post_lo"], surf_s_lo, cm["chain"][0])
        h_hi, l_hi = hours(t_end_hi, s_hi, cm["m_post_hi"], surf_s_hi, cm["chain"][1])
        h_cap, _ = hours(t_cap, s_hi, cm["m_post_hi"], surf_s_hi, cm["chain"][1])
        mem = (rfit["base"] + rfit["per_Mparticle"] * n_hi / 1e6) if rfit else None
        tab_gb = 13 * 4 * (min(d["Lx"], 281.0) + 1) * (d["Ly"] + 1) * ((t_cap - t0) / 0.1 + 1) / 1e9   # 入口の表（13 の場、float32）
        mem_lo = 4.5 + 0.30 * n_lo / 1e6 + tab_gb                       # S1 の粒子 0.25・0.177 m の間の傾き 0.30 GiB/百万粒子 + 土台 4.5 GiB（DOP の覚え 3 GB を含む）
        out.append(dict(name=r["name"], case=r["case"], layout=r["layout"], dp=dp, particles_M=[round(n_lo / 1e6, 2), round(n_hi / 1e6, 2)],
                        s_per_frame_pre=[round(s_lo, 2), round(s_hi, 2)], surf_s=[round(surf_s_lo, 2), round(surf_s_hi, 2)], record_s=round(rec_s, 2),
                        hours=[round(h_lo, 2), round(h_hi, 2)], hours_cap_hi=round(h_cap, 2), launches=[l_lo, l_hi],
                        rss_GiB=[round(mem_lo, 1), round(mem + tab_gb, 1) if mem else None], table_GB=round(tab_gb, 2), boot_s=round(boot_s, 1),
                        rss_GiB_hi=round(mem + tab_gb, 1) if mem else None, ckpt_GB_one=round(ckb * n_hi / 1e9, 2),
                        plan_hours=[r["hours"]["lo"], r["hours"]["hi"]], plan_particles_M=r["particles_M"], plan_mem_GB=r["mem_GB"]))
    return out, dict(us_lo=us_lo, us_hi=us_hi, growth=[g_lo, g_hi], surf_us=surf_us, boot_s=boot_s, rec_s_per_Mcell=rec_c, ckpt_B_per_particle=ckb)


def seq_totals(est, plan):
    E = {e["name"]: e for e in est}
    out = {}
    for k, seq in plan["sequences"].items():
        names = seq if isinstance(seq, list) else seq.get("runs", [])
        lo = sum(E[n]["hours"][0] for n in names if n in E); hi = sum(E[n]["hours"][1] for n in names if n in E)
        cap = sum(E[n]["hours_cap_hi"] for n in names if n in E)
        out[k] = dict(runs=names, hours=[round(lo, 1), round(hi, 1)], hours_all_cap=round(cap, 1))
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    GC.unthrottle_self()
    plan = GC.load_plan()
    M = measured()
    est, used = estimate(M, plan)
    tot = seq_totals(est, plan)
    os.makedirs(OUTD, exist_ok=True)
    res = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), measured=M, used=used, runs=est, sequences=tot,
               note_ja="【推定】煙の試しで測った 3D の値（粒子 0.5 m 以上・崩れの前）から。崩れの後の重さと粒子 181/1024 m の増えは FLIP42 の 2D の値のまま")
    json.dump(res, open(OUTD + "/hours45.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    lines = ["# FLIP45 の時間の見込みの出し直し（%s、`g45_hours.py`）【推定】" % res["date"], "",
             "| 計算 | 粒子（百万） | 1 コマの秒（崩れの前） | 面の秒 | 時間（下〜上） | t_cap まで（上） | 主メモリー（GiB、下〜上） | 途中保存 1 個（GB） | 計画の見込み |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for e in est:
        lines.append("| %s | %s〜%s | %s〜%s | %s〜%s | %s〜%s | %s | %s | %s | %s〜%s 時間・%s 百万・%s GB |" % (
            e["name"], e["particles_M"][0], e["particles_M"][1], e["s_per_frame_pre"][0], e["s_per_frame_pre"][1], e["surf_s"][0], e["surf_s"][1],
            e["hours"][0], e["hours"][1], e["hours_cap_hi"], "%s〜%s" % (e["rss_GiB"][0], e["rss_GiB"][1]), e["ckpt_GB_one"], e["plan_hours"][0], e["plan_hours"][1],
            e["plan_particles_M"], e["plan_mem_GB"]))
    lines += ["", "並びの和：" + json.dumps(tot, ensure_ascii=False)]
    open(OUTD + "/hours45_ja.md", "w", encoding="utf8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
