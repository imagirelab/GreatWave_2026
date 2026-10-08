# -*- coding: utf-8 -*-
"""FLIP41 確かめ：解析の結果（runs/*/ana.json）を表にまとめ、plan_ja.md §5 の判定の幅と比べる。細かさの収束（GCI）と、T2 の風の効きも出す。
py -3.10 v_summary.py → verify/summary.json、verify/summary_tables.md（record_ja.md に写す表）、verify/t2_summary.json"""
import sys, os, json, glob, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
from v_lin import props, G

V = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify"


def load_all():
    A = {}
    for p in sorted(glob.glob(os.path.join(V, "runs", "*", "ana.json"))):
        a = json.load(open(p, encoding="utf8"))
        A[a["run_id"]] = a
    return A


def yes(b):
    return "入った" if b else "入らない"


def gci(phis, hs):
    """Celik ら（2008）。phis・hs は細かい順（h1 < h2 < h3）。"""
    f1, f2, f3 = phis; h1, h2, h3 = hs
    r21, r32 = h2 / h1, h3 / h2
    e21, e32 = f2 - f1, f3 - f2
    out = dict(phi=phis, h=hs, r21=r21, r32=r32, e21=e21, e32=e32)
    if abs(e21) < 1e-12 or abs(e32) < 1e-12:
        out["note"] = "差が 0 で次数を出せない"
        return out
    s = np.sign(e32 / e21)
    p = abs(math.log(abs(e32 / e21))) / math.log(r21)
    for _ in range(50):
        q = math.log((r21 ** p - s) / (r32 ** p - s))
        p = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
    ea21 = abs((f1 - f2) / f1)
    ext = (r21 ** p * f1 - f2) / (r21 ** p - 1)
    out.update(p=p, monotone=bool(s > 0), phi_ext=ext, ea21=ea21, gci_fine=1.25 * ea21 / (r21 ** p - 1))
    # 3 段で単調でない（振動する）時は、Celik らの手順の次数は意味を持たない。細かい 2 段だけで、次数 2 を仮定した目安も出す
    out["two_level_p2"] = dict(phi_ext=f1 + (f1 - f2) / (r21 ** 2 - 1), gci_fine=1.25 * ea21 / (r21 ** 2 - 1))
    out["two_level_p1"] = dict(phi_ext=f1 + (f1 - f2) / (r21 - 1), gci_fine=1.25 * ea21 / (r21 - 1))
    return out


def main():
    A = load_all()
    rows_b1, rows_w, rows_iso, rows_b2, rows_t1, rows_amp = [], [], [], [], [], []
    for rid, a in A.items():
        if "error" in a:
            continue
        cs = a["case"]
        if cs["kind"] == "B1":
            r = dict(run_id=rid, T=cs["T"], h=cs["h"], kh=cs["kh"], dp=cs["dp"], wm=cs["wm"], H=cs["H"], a_vox=cs["a_over_vox"], L_vox=cs["L_over_vox"],
                     c_err=a["c_err"], c_spread=a["c_err_spread"], decay_3L=a["decay_3L"], R=a["R"], a_exit_ratio=a["a_exit_ratio"],
                     dphase_exit=a["dphase_exit"], a2_ratio=a["a2_mean"] / max(a["a2_stokes"], 1e-9), wall_s=a.get("wall_total_s"),
                     band_vox=cs.get("band_vox", 4), minsub=cs.get("minsub", 1), vt=cs.get("vt", "apic"), nb=cs.get("nb", 1), P0=cs.get("P0", 0.0), tau=cs.get("tau", 0.0))
            r["ok_c"] = abs(r["c_err"]) <= 0.01
            r["ok_decay"] = r["decay_3L"] <= 0.05
            r["ok_exit"] = abs(r["a_exit_ratio"] - 1) <= 0.05 and (r["dphase_exit"] is None or abs(r["dphase_exit"]) <= 0.1)
            if "_T2" in rid:
                continue
            r["HL"] = cs["HL"]
            if r["band_vox"] != 4 or r["minsub"] != 1 or r["vt"] != "apic" or r["nb"] != 1:
                rows_iso.append(r)
            elif cs["wm"] == "piston":
                rows_w.append(r)
            elif abs(cs["HL"] - 0.01) > 1e-4:
                rows_amp.append(r)
            else:
                rows_b1.append(r)
        elif cs["kind"] == "B2":
            for mode, src in (("場所ごとの窓", a.get("perx")), ("同じ窓", a)):
                if not src:
                    continue
                top = [x for x in src["rows"] if abs(x["h"] - cs["h1"]) < 1e-6]
                slope = [x for x in src["rows"] if cs["h1"] + 1e-6 < x["h"] < cs["h0"] - 1e-6]
                ks_top = float(np.mean([x["Ks_num"] for x in top[:4]])) if top else float("nan")
                ks_lin = top[0]["Ks_lin"] if top else float("nan")
                ce = [x["c_err"] for x in slope + top[:4]]
                r = dict(run_id=rid, mode=mode, T=cs["T"], dp=cs["dp"], nb=cs.get("nb", 1), c_err_max=float(max([abs(v) for v in ce] or [float("nan")])),
                         c_err_min_s=float(min(ce)) if ce else float("nan"), c_err_max_s=float(max(ce)) if ce else float("nan"),
                         t_num=src["slope_time_num"], t_lin=src["slope_time_lin"], t_const=src["slope_time_const"],
                         t_err=src["slope_time_err"], Ks_top_num=ks_top, Ks_top_lin=ks_lin, Ks_err=ks_top / ks_lin - 1,
                         a_off_ratio=src["a_off_ratio"], R_off=src["R_off"], c_err_off=src["c_err_off"], wall_s=a.get("wall_total_s"))
                r["ok_c"] = r["c_err_max"] <= 0.02; r["ok_t"] = abs(r["t_err"]) <= 0.5; r["ok_ks"] = abs(r["Ks_err"]) <= 0.03
                rows_b2.append(r)
        elif cs["kind"] == "T1":
            r = dict(run_id=rid, dp=cs["dp"], p0u=cs["p0u"], p0c=cs["p0c"], lam=cs["lam"], ratio=a["ratio"], cos_amp=a["cos_amp"], expect=a["expect"],
                     sd_win=a["sd_time_window"], sd_still=a["sd_time_still"], resid=a["resid_rms"])
            r["ok_ratio"] = abs(r["ratio"] - 1) <= 0.10 and r["cos_amp"] * r["expect"] > 0
            r["ok_still"] = r["sd_win"] <= 2 * r["sd_still"]
            rows_t1.append(r)
    # 細かさの収束（粒子 1・0.5・0.25 m がそろった組）
    conv = []
    groups = {}
    for r in rows_b1 + rows_amp:
        groups.setdefault((r["T"], r["h"], round(r["HL"], 3)), {})[r["dp"]] = r
    for key, g in sorted(groups.items()):
        for lv in ((0.125, 0.25, 0.5), (0.25, 0.5, 1.0)):
            if all(d in g for d in lv):
                phis = [1 + g[d]["c_err"] for d in lv]
                gg = gci(phis, list(lv))
                gd = gci([g[d]["decay_3L"] for d in lv], list(lv))
                conv.append(dict(T=key[0], h=key[1], HL=key[2], levels=list(lv), speed=gg, decay=gd))
    # T2：風あり ÷ 風なし
    t2 = None
    base = [rid for rid in A if rid.endswith("_T2N") and "error" not in A[rid]]
    if base:
        N = A[base[0]]
        cs = N["case"]
        cv = N["_curve"]; x = np.array(cv["x"])
        AN = np.array([c[0] + 1j * c[1] for c in cv["A1"]])
        xm0, xm1 = cv["sel"]
        sel = (x >= xm0) & (x <= xm1)
        p = props(cs["T"], cs["h"])
        runs = []
        for tag, label in (("_T2M", "Miles 型 β=34"), ("_T2J", "Jeffreys 型 S=0.5"), ("_T2MT", "Miles 型 + 接線の応力")):
            rid = base[0].replace("_T2N", tag)
            if rid not in A or "error" in A[rid]:
                continue
            W = A[rid]; cw = W["case"]
            AW = np.array([c[0] + 1j * c[1] for c in W["_curve"]["A1"]])
            ratio = np.abs(AW) / np.abs(AN)
            # 進む波の合わせ（ana.json の α）から：振幅の空間の増え方 = αN − αW、エネルギーの成長率 γ = 2 cg (αN − αW)
            dal = N["alpha"] - W["alpha"]
            gam = 2 * p["cg"] * dal
            gam_sd = 2 * p["cg"] * math.hypot(N["alpha_sd"], W["alpha_sd"])
            P0 = cw["P0"]
            gam_th = P0 * p["k"] * p["om"] / (1000.0 * G)
            us = math.sqrt(cw["tau"] / 1.2) if cw["tau"] > 0 else 1.3796738745080301
            plant = [f * (us / p["c"]) ** 2 * p["om"] for f in (0.02, 0.04, 0.06)]
            th_ratio = np.exp(gam_th / (2 * p["cg"]) * (x - xm0))
            runs.append(dict(run_id=rid, label=label, P0=P0, tau=cw["tau"], gamma=gam, gamma_sd=gam_sd, gamma_theory=gam_th,
                             ratio_to_theory=gam / gam_th if gam_th > 0 else None, plant=plant,
                             ok_impl=bool(abs(gam / gam_th - 1) <= 0.25) if (gam_th > 0 and cw["tau"] == 0) else None,
                             ok_plant=bool(plant[0] <= gam <= plant[2]) if "Miles" in label else None,
                             decay_nowind_per_L=1 - math.exp(-N["alpha"] * cs["L"]), growth_wind_per_L=math.exp(gam_th / (2 * p["cg"]) * cs["L"]) - 1,
                             ratio=[float(v) for v in ratio[sel]], ratio_theory=[float(v) for v in th_ratio[sel]], c_err=W["c_err"]))
        t2 = dict(base=base[0], x=[float(v) for v in x[sel]], x_meas=[xm0, xm1], cg=p["cg"], k=p["k"], om=p["om"], runs=runs,
                  alpha_nowind=N["alpha"], alpha_nowind_sd=N["alpha_sd"])
        json.dump(t2, open(os.path.join(V, "t2_summary.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    out = dict(B1=rows_b1, AMP=rows_amp, W=rows_w, ISO=rows_iso, B2=rows_b2, T1=rows_t1, convergence=conv,
               T2=None if t2 is None else [{k: v for k, v in r.items() if k not in ("ratio", "ratio_theory")} for r in t2["runs"]])
    json.dump(out, open(os.path.join(V, "summary.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    # 表（Markdown）
    L = []
    def pct(v, d=2):
        return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else ("%+.*f %%" % (d, 100 * v))
    L.append("### B1 平らな底（緩和の帯）\n")
    L.append("速さの誤差は線形の分散の式との差。括弧の中は、測る区間を 1 波長の窓に分けた時の最小〜最大。Stokes 3 次は、振幅による速さの増え（Fenton 1985）。\n")
    L.append("| 計算 | 周期 | 水深 | kh | 粒子 | 高さ | 振幅/格子 | 波長/格子 | 速さの誤差（場所の幅） | Stokes 3 次 | 1 % に | 3 波長の減り | 5 % に | 帯の出口の高さ比・位相 | 出口の判定 | 跳ね返り | 計算の時間 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in sorted(rows_b1 + rows_amp, key=lambda r: (r["T"], -r["h"], -r["dp"], r["HL"])):
        a = json.load(open(os.path.join(V, "runs", r["run_id"], "ana.json"), encoding="utf8"))
        lo, hi = a.get("c_err_local_min"), a.get("c_err_local_max")
        L.append("| %s | %g s | %g m | %.2f | %g m | %.2f m | %.2f | %.0f | %s（%s〜%s） | %s | %s | %.1f %% | %s | %.3f・%+.3f rad | %s | %.1f %% | %.0f 分 |" % (
            r["run_id"], r["T"], r["h"], r["kh"], r["dp"], r["H"], r["a_vox"], r["L_vox"], pct(r["c_err"]), pct(lo, 1), pct(hi, 1), pct(a["stokes3_dc"]), yes(r["ok_c"]),
            100 * r["decay_3L"], yes(r["ok_decay"]), r["a_exit_ratio"], r["dphase_exit"] if r["dphase_exit"] is not None else float("nan"), yes(r["ok_exit"]),
            100 * r["R"], (r["wall_s"] or 0) / 60))
    if rows_w:
        L.append("\n### W ピストン板\n")
        L.append("| 計算 | 周期 | 水深 | 粒子 | 速さの誤差 | 3 波長の減り | 板から 1.5 波長の高さ ÷ 目標 | 判定（±5 %） | 跳ね返り |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in sorted(rows_w, key=lambda r: (r["T"], -r["dp"])):
            L.append("| %s | %g s | %g m | %g m | %s | %.1f %% | %.3f | %s | %.1f %% |" % (r["run_id"], r["T"], r["h"], r["dp"], pct(r["c_err"]), 100 * r["decay_3L"],
                                                                            r["a_exit_ratio"], yes(abs(r["a_exit_ratio"] - 1) <= 0.05), 100 * r["R"]))
    if rows_iso:
        L.append("\n### 一つずつ変えた計算（原因を分ける）\n")
        L.append("| 計算 | 粒子・H/L | 変えた所 | 速さの誤差 | 3 波長の減り | 帯の出口の高さ比 | 計算の時間 |")
        L.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in rows_iso:
            ch = []
            if r["band_vox"] != 4: ch.append("粒子の帯 %d 格子" % r["band_vox"])
            if r["nb"] != 1: ch.append("帯を使わない（全体に粒子）")
            if r["minsub"] != 1: ch.append("最小の小刻み %d" % r["minsub"])
            if r["vt"] != "apic": ch.append("受け渡し %s" % r["vt"].upper())
            L.append("| %s | %g m・%.2f | %s | %s | %.1f %% | %.3f | %.0f 分 |" % (r["run_id"], r["dp"], r["HL"], "、".join(ch), pct(r["c_err"]), 100 * r["decay_3L"], r["a_exit_ratio"], (r["wall_s"] or 0) / 60))
    if conv:
        L.append("\n### 細かさの収束（Celik ら 2008、粒子の間隔の比 2 の 3 段）\n")
        L.append("| 組 | 粒子（細かい順） | 速さの比 c/c線形 | 観測された次数 | 単調か | 外挿した値（3 段） | 細かい側の GCI（3 段） | 細かい 2 段で次数 2・次数 1 を仮定した外挿（GCI） | 減り | 減りの外挿 |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for c in conv:
            s = c["speed"]; d = c["decay"]
            q2 = s.get("two_level_p2", {}); q1 = s.get("two_level_p1", {})
            L.append("| 周期 %g s・水深 %g m・H/L %.2f | %s m | %s | %s | %s | %s | %s | %s・%s | %s | %s |" % (
                c["T"], c["h"], c.get("HL", 0.01), "・".join("%g" % v for v in c["levels"]), "・".join("%.4f" % v for v in s["phi"]), ("%.2f" % s["p"]) if "p" in s else "—", ("はい" if s.get("monotone") else "いいえ（振動）") if "p" in s else "—",
                ("%.4f" % s["phi_ext"]) if ("phi_ext" in s and s.get("monotone")) else "—", ("%.2f %%" % (100 * s["gci_fine"])) if ("gci_fine" in s and s.get("monotone")) else "—",
                ("%.4f（%.2f %%）" % (q2["phi_ext"], 100 * q2["gci_fine"])) if q2 else "—", ("%.4f（%.2f %%）" % (q1["phi_ext"], 100 * q1["gci_fine"])) if q1 else "—",
                "・".join("%.1f %%" % (100 * v) for v in d["phi"]), ("%.1f %%" % (100 * d["phi_ext"])) if ("phi_ext" in d and d.get("monotone") and 0 <= d["phi_ext"] <= 1) else "—（漸近の範囲でない）"))
    if rows_b2:
        L.append("\n### B2 ゆるい斜面（40 → 12 m、1:20）\n")
        L.append("「場所ごとの窓」は、その場所に波の先頭（群速度）が着いて 3 周期の後からの 5 周期で測った値（造波の帯の近くで後の時刻に育つ乱れを避ける）。「同じ窓」は計画のとおり、全部の場所で同じ時刻の窓。\n")
        L.append("| 計算 | 窓 | 周期 | 粒子 | 斜面と浅い所の速さの誤差（最小〜最大） | ±2 % に | 斜面を上る位相の時間（FLIP・線形・40 m のまま） | 差 | ±0.5 s に | 浅い所の高さ ÷ 沖の高さ（FLIP・線形 Ks） | ±3 % に | 沖の速さの誤差 | 沖の高さ ÷ 目標 | 沖の跳ね返り |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in sorted(rows_b2, key=lambda r: (r["T"], -r["dp"], r["nb"], r["mode"])):
            L.append("| %s | %s | %g s | %g m%s | %s〜%s | %s | %.2f・%.2f・%.2f s | %+.2f s | %s | %.3f・%.3f | %s | %s | %.3f | %.2f |" % (
                r["run_id"], r["mode"], r["T"], r["dp"], "（帯なし）" if r["nb"] == 0 else "", pct(r["c_err_min_s"], 1), pct(r["c_err_max_s"], 1), yes(r["ok_c"]),
                r["t_num"], r["t_lin"], r["t_const"], r["t_err"], yes(r["ok_t"]), r["Ks_top_num"], r["Ks_top_lin"], yes(r["ok_ks"]), pct(r["c_err_off"]), r["a_off_ratio"], r["R_off"]))
    if rows_t1:
        L.append("\n### T1 水面の圧力の場\n")
        L.append("| 計算 | 粒子 | 圧力（一様・cos・波長） | cos の振幅（FLIP・式） | 比 | ±10 % に | 窓の中の揺れ ÷ 静かな水の揺れ | 2 倍以内に |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in rows_t1:
            L.append("| %s | %g m | %g・%g Pa・%g m | %.3f・%.3f m | %.3f | %s | %.2f | %s |" % (
                r["run_id"], r["dp"], r["p0u"], r["p0c"], r["lam"], r["cos_amp"], r["expect"], r["ratio"], yes(r["ok_ratio"]), r["sd_win"] / r["sd_still"], yes(r["ok_still"])))
    if t2:
        L.append("\n### T2 風の圧力による波の育ち（周期 5 s・水深 25 m、U10 30 m/s）\n")
        L.append("| 計算 | P0 | τ | 測ったエネルギーの成長率 γ（±1σ） | 入れた圧力の式 P0kω/(ρg) | 比 | ±25 % に | Plant の幅（0.02〜0.06） | Plant の幅に |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in t2["runs"]:
            L.append("| %s | %.1f Pa | %.2f Pa | %.2e（%.1e）/s | %.2e /s | %s | %s | %.1e〜%.1e /s | %s |" % (
                r["run_id"], r["P0"], r["tau"], r["gamma"], r["gamma_sd"], r["gamma_theory"], ("%.2f" % r["ratio_to_theory"]) if r["ratio_to_theory"] else "—",
                yes(r["ok_impl"]) if r["ok_impl"] is not None else "—", r["plant"][0], r["plant"][2], yes(r["ok_plant"]) if r["ok_plant"] is not None else "—"))
    open(os.path.join(V, "summary_tables.md"), "w", encoding="utf8").write("\n".join(L) + "\n")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf8", "replace"))


if __name__ == "__main__":
    main()
