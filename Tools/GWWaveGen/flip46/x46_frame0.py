# -*- coding: utf-8 -*-
"""FLIP46：0 コマ目の確かめ（FLIP37 の誤り：深い格子の流速が 0 から始まった）を、厳密な孤立波の点の値と比べる（py -3.10。統合の役、2026-10-12）。
解の表（0.25 m の npz）を通さず、g46_solitary.get_wave() の点の値（等角写像を Newton 法で逆に解く）と比べる。
読む物：<run>/run.json の info.init_check（g46_run.py。格子の流速を確かめの点で sample した値、cfg の init_check_dx・init_check_y）と
        <run>/init_fFFFFF.npz（cfg の init_dump。確かめの x のまわり ±1.5 格子の粒子の位置と流速、格子の流速の縦の線）。
比べ方：
  - 格子：確かめの点 (x, z, 横) の vel 場の値と、その点の厳密な値（時刻 t、頂は x0 + c t）。
  - 粒子：確かめの点のまわりの箱（各向き ±dp）の粒子の流速の平均と、同じ粒子の位置の厳密な値の平均（粒子の置き場所の偏りを除く）。
           1 粒子ずつの差の RMS も。
  - 縦の線：確かめの x・横ごとに、海底 + 1 格子から水面 − 1 格子までの格子の u・w と厳密な値の差の RMS と最大。
  - 1 コマ目の粒子の全部（書き出した物から最大 20000 個）：初めに置いた流速と厳密な値の差の RMS と最大。
1 コマ目は t = 0 の置いたままの状態（圧力の段の前）。2 コマ目からは 1 段の後で、尾根の上では海底に沿う流れ（解は平らな海底の解）が足される。
使い方：py -3.10 x46_frame0.py <run_dir> [--dx=-15,0,15] [--y=-2,-8.5,-15] [--frames=1,2,3]  → <run_dir>/frame0_check.json と表
"""
import sys, os, json, glob, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC
import g46_solitary as S


def vec_err_pct(du, dw, ue, we):
    den = float(np.hypot(ue, we))
    return 100.0 * float(np.hypot(du, dw)) / den if den > 1e-9 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--dx", default="-15,0,15")
    ap.add_argument("--y", default="-2,-8.5,-15")
    ap.add_argument("--frames", default="1,2,3")
    a = ap.parse_args()
    rd = a.run_dir
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    P = run["parms"]
    dp = float(P["dp"]); vox = dp * float(P["gridscale"])
    want_dx = [float(v) for v in a.dx.split(",")]
    want_y = [float(v) for v in a.y.split(",")]
    want_f = [int(v) for v in a.frames.split(",")]
    sol = (run.get("info") or {}).get("solitary") or {}
    npz = sol.get("npz") or ""
    kind = cfg.get("solitary_kind")
    wave = S.get_wave()
    out = dict(run_id=run["run_id"], dp=dp, vox=vox, solitary_npz=npz, solitary_kind=kind, exact=dict(F=wave.F, c=wave.c, x0=wave.x0, h0=wave.h0),
               note_ja="1 コマ目＝t 0 の置いたまま。2 コマ目から 1 段の後（尾根の上は海底に沿う流れが足される）。誤差 % は (Δu, Δw) の長さ ÷ 厳密な流速の長さ",
               probes=[], columns=[], particles_all=[])
    if kind and "Tanaka" not in str(kind):
        out["warning"] = "この計算の初めの波は %s。厳密な解（Tanaka）との差は解の違いを含む" % kind
    rows = []
    for ic in (run.get("info") or {}).get("init_check", []):
        for r in ic["rows"]:
            rows.append(dict(r, frame=int(ic["frame"]), t=float(ic["t"])))
    dumps = {}
    for p in sorted(glob.glob(os.path.join(rd, "init_f*.npz"))):
        d = np.load(p)
        dumps[int(d["frame"])] = d
    # ------------------------------------------------ 確かめの点
    for f in want_f:
        for r in rows:
            if r["frame"] != f or not any(abs(r["dx"] - v) < 1e-6 for v in want_dx) or not any(abs(r["y"] - v) < 1e-6 for v in want_y):
                continue
            t = r["t"] - float(run.get("t_off") or 0.0)
            ue, we = wave.velocity(np.array([r["x"]]), np.array([r["y"]]), t=t)
            ue = float(ue[0]); we = float(we[0])
            row = dict(frame=f, t=t, dx=r["dx"], x=r["x"], y=r["y"], zl=r["zl"], bed=r.get("bed"), eta_exact=float(wave.eta(np.array([r["x"]]), t=t)[0]),
                       u_exact=ue, w_exact=we, u_table=r.get("u_ana"), w_table=r.get("w_ana"),
                       u_grid=r.get("u_grid"), w_grid=r.get("w_grid"), v_grid=r.get("v_grid"))
            if r.get("u_grid") is not None and np.isfinite(ue):
                row["grid_du"] = r["u_grid"] - ue; row["grid_dw"] = r["w_grid"] - we
                row["grid_err_pct"] = vec_err_pct(row["grid_du"], row["grid_dw"], ue, we)
                row["grid_u_err_pct"] = 100.0 * row["grid_du"] / ue if abs(ue) > 1e-9 else None
            d = dumps.get(f)
            if d is not None:
                Pp = d["P"].astype(np.float64); V = d["v"].astype(np.float64)
                m = (np.abs(Pp[:, 0] - r["x"]) < dp) & (np.abs(Pp[:, 1] - r["y"]) < dp) & (np.abs(Pp[:, 2] - r["zl"]) < dp)
                row["n_part"] = int(m.sum())
                if m.any():
                    ux, wx = wave.velocity(Pp[m, 0], Pp[m, 1], t=t, above="surface")
                    ok = np.isfinite(ux)
                    if ok.any():
                        up = V[m, 0][ok]; wp = V[m, 1][ok]
                        row["u_part"] = float(up.mean()); row["w_part"] = float(wp.mean())
                        row["u_exact_at_part"] = float(ux[ok].mean()); row["w_exact_at_part"] = float(wx[ok].mean())
                        row["part_du"] = row["u_part"] - row["u_exact_at_part"]; row["part_dw"] = row["w_part"] - row["w_exact_at_part"]
                        row["part_err_pct"] = vec_err_pct(row["part_du"], row["part_dw"], row["u_exact_at_part"], row["w_exact_at_part"])
                        row["part_rms_per_particle"] = float(np.sqrt(np.mean((up - ux[ok]) ** 2 + (wp - wx[ok]) ** 2)))
                        row["part_v_mean"] = float(V[m, 2][ok].mean())
            out["probes"].append(row)
    # ------------------------------------------------ 縦の線（格子）
    for f in want_f:
        d = dumps.get(f)
        if d is None:
            continue
        t = float(d["dt"])
        gy = d["grid_y"].astype(np.float64); gl = d["grid_vel"].astype(np.float64)
        for i, (dx_, xp) in enumerate(zip(d["probe_dx"], d["probe_x"])):
            for j, zl in enumerate(d["grid_zl"]):
                bed = float(GC.bed_z(xp, zl, k=float(P["ridge_k"]), x_toe=float(P["ridge_x0"]), s=float(P["ridge_s"]), h0=float(P["h0"]),
                                     on=float(P["ridge_on"]) > 0.5))
                eta = float(wave.eta(np.array([xp]), t=t)[0])
                m = (gy >= bed + vox) & (gy <= eta - vox)
                if m.sum() < 2:
                    continue
                ue, we = wave.velocity(np.full(m.sum(), xp), gy[m], t=t)
                du = gl[i, j, m, 0] - ue; dw = gl[i, j, m, 1] - we
                deep = gy[m] <= bed + 0.5 * (eta - bed)
                out["columns"].append(dict(frame=int(d["frame"]), t=t, dx=float(dx_), x=float(xp), zl=float(zl), bed=bed, eta_exact=eta,
                                           n=int(m.sum()), u_rms=float(np.sqrt(np.mean(du ** 2))), u_maxabs=float(np.max(np.abs(du))),
                                           w_rms=float(np.sqrt(np.mean(dw ** 2))), w_maxabs=float(np.max(np.abs(dw))),
                                           u_exact_range=[float(ue.min()), float(ue.max())],
                                           u_grid_min_deep=float(gl[i, j, m, 0][deep].min()) if deep.any() else None,
                                           v_grid_maxabs=float(np.nanmax(np.abs(gl[i, j, m, 2])))))
    # ------------------------------------------------ 1 コマ目の粒子の全部（書き出した物）
    for f in want_f:
        d = dumps.get(f)
        if d is None:
            continue
        t = float(d["dt"])
        Pp = d["P"].astype(np.float64); V = d["v"].astype(np.float64)
        rng = np.random.default_rng(46)
        idx = rng.choice(len(Pp), size=min(20000, len(Pp)), replace=False) if len(Pp) else np.zeros(0, int)
        ux, wx = wave.velocity(Pp[idx, 0], Pp[idx, 1], t=t, above="surface")
        ok = np.isfinite(ux)
        du = V[idx, 0][ok] - ux[ok]; dw = V[idx, 1][ok] - wx[ok]
        sp = np.hypot(ux[ok], wx[ok])
        out["particles_all"].append(dict(frame=int(d["frame"]), t=t, n_dumped=int(len(Pp)), n_checked=int(ok.sum()),
                                         rms_m_s=float(np.sqrt(np.mean(du ** 2 + dw ** 2))) if ok.any() else None,
                                         max_m_s=float(np.max(np.hypot(du, dw))) if ok.any() else None,
                                         rel_rms_pct=float(100 * np.sqrt(np.mean(du ** 2 + dw ** 2)) / np.sqrt(np.mean(sp ** 2))) if ok.any() else None,
                                         v_lateral_maxabs=float(np.max(np.abs(V[idx, 2]))) if len(idx) else None))
    json.dump(out, open(os.path.join(rd, "frame0_check.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


def fmt(v, n=3):
    return "-" if v is None else ("%.*f" % (n, v))


if __name__ == "__main__":
    o = main()
    print("run", o["run_id"], "dp", o["dp"], "wave", o["solitary_kind"], "exact c %.3f m/s" % o["exact"]["c"])
    print("frame  dx    y     lat | u_ex   u_grid  u_part(at-part ex) | w_ex   w_grid  w_part | grid err%  part err%  n")
    for r in o["probes"]:
        print("%3d %6.1f %6.2f %5.1f | %6.3f %6.3f %6.3f(%6.3f) | %6.3f %6.3f %6.3f | %6s %6s %3s" % (
            r["frame"], r["dx"], r["y"], r["zl"], r["u_exact"], r["u_grid"] or float("nan"), r.get("u_part", float("nan")),
            r.get("u_exact_at_part", float("nan")), r["w_exact"], r["w_grid"] or float("nan"), r.get("w_part", float("nan")),
            fmt(r.get("grid_err_pct"), 2), fmt(r.get("part_err_pct"), 2), r.get("n_part", 0)))
    for c in o["columns"]:
        print("column f%d dx %5.1f lat %4.1f bed %6.2f: n %3d  u rms %.4f max %.4f | w rms %.4f max %.4f | deep u_grid min %s" % (
            c["frame"], c["dx"], c["zl"], c["bed"], c["n"], c["u_rms"], c["u_maxabs"], c["w_rms"], c["w_maxabs"], fmt(c["u_grid_min_deep"])))
    for pa in o["particles_all"]:
        print("particles f%d: checked %d of %d, rms %.4f m/s (%.3f %%), max %.4f m/s" % (
            pa["frame"], pa["n_checked"], pa["n_dumped"], pa["rms_m_s"], pa["rel_rms_pct"], pa["max_m_s"]))
