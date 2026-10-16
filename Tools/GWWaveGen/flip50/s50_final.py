# -*- coding: utf-8 -*-
"""FLIP50 option D: numbers for the chosen main (T 12 s) and fallback (T 10 s) configurations and the plan draft.
numpy only (py -3.10 -I). 2026-10-15, Claude. Writes screen/s50_final.json and plan_D_draft.json (a DRAFT: not frozen, no run started).
Reads: screen/s50_linear*.json, screen/u50_*.json (made by s50_linear.py and u50_dir.py), Unity/Build/FLIP49/plan/plan_A_frozen.json
(read only, criteria copied unchanged), Unity/Build/FLIP49/runs/runs.jsonl (DA1 launch 1 rate, read only).
"""
import os, sys, json, math, time, hashlib
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g50_dirfield as DF
import s50_linear as S

REPO = r"G:/Unity/GreatWave_2026_Fresh"
PLAN_A = REPO + "/Unity/Build/FLIP49/plan/plan_A_frozen.json"
RUNS49 = REPO + "/Unity/Build/FLIP49/runs/runs.jsonl"
OUT = os.path.join(HERE, "screen")

BED = dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")
LAYOUT = dict(Lx=412.0, W=140.0, side_band=45.0, x_gen=180.25, x_sw=210.25, inlet=(0.0, 100.0), wall_taper=20.0,
              zb=-21.0, z_top=17.0, beach_top_x=410.25, shoreline_x=350.25)
CONFIGS = {
    "DM1_T12": dict(T=12.0, thm=80.0, n=30, weight="uniform", delta=-20.0, hb_target=11.0, u3="u50_F12_main.json", t_end=92.0, ramp=24.0),
    "DF1_T10": dict(T=10.0, thm=80.0, n=30, weight="uniform", delta=-20.0, hb_target=11.0, u3="u50_F10_fallback.json", t_end=86.0, ramp=20.0),
}
COEF = (0.486, 0.575)          # s per million particles per frame, FLIP48 measured
GROWTH = (1.16, 1.30)          # particle growth used by plan A
HEAVY_S = 1.8                  # s per heavy-record frame (FLIP49)


def sha16(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def count_particles(Lx, W, dp, zb, bed_gap=0.5):
    """same rule as g49_common.count_particles (columns at (i+1/2)dp, layers zb+(k+1/2)dp, bed + bed_gap*dp <= layer < 0), laterally straight bed."""
    xs = (np.arange(int(round(Lx / dp))) + 0.5) * dp
    bed = -DF.bed_h(xs, BED)
    k_lo = np.ceil((bed + bed_gap * dp - zb) / dp - 0.5 - 1e-9)
    k_hi = np.ceil((0.0 - zb) / dp - 0.5 - 1e-9)
    per_col = np.maximum(k_hi - np.maximum(k_lo, 0), 0)
    n = int(per_col.sum()) * int(round(W / dp))
    return n, n * dp ** 3


def da1_rate():
    """DA1 launch 1 (read only): frames done and wall time -> s per frame, s per million particles per frame (no heavy records yet)."""
    for line in open(RUNS49, encoding="utf-8"):
        r = json.loads(line)
        if r.get("run_id") == "DA1_SC37_T12H7p5_dp0p5" and r.get("f_start") == 1:
            spf = r["wall_total_s"] / r["f_end_done"]
            n0 = 4981609; nmax = r["particles_max"]
            return dict(frames=r["f_end_done"], wall_s=r["wall_total_s"], s_per_frame=spf, particles_start=n0, particles_max=nmax,
                        s_per_Mp_frame_lo=spf / (nmax / 1e6), s_per_Mp_frame_hi=spf / (n0 / 1e6),
                        note="launch 1 only (frames 1-940, before the heavy-record windows), measured while the numpy screens also used the CPU")
    return None


def windows(onsets, T, t_end):
    return [[round(t - 3.0, 2), round(min(t + 4.0, t_end), 2)] for t in onsets]


def main():
    cal = S.calib_gamma(); gb = cal["gamma_b"]
    out = dict(tool="Tools/GWWaveGen/flip50/s50_final.py", date=time.strftime("%Y-%m-%d %H:%M:%S"), bed=BED, layout=LAYOUT, calibration=cal, configs={})
    n05, V = count_particles(LAYOUT["Lx"], LAYOUT["W"], 0.5, LAYOUT["zb"])
    n10, _ = count_particles(LAYOUT["Lx"], LAYOUT["W"] + 2.0, 1.0, LAYOUT["zb"])
    da1 = da1_rate()
    out["particles"] = dict(dp0p5=n05, water_m3=V, dp1p0=n10, tag="computed (g49_common.count_particles rule)")
    out["da1_rate"] = da1
    for name, c in CONFIGS.items():
        r = S.screen_one(c["T"], c["thm"], n=c["n"], weight=c["weight"], delta=c["delta"], gamma_b=gb, spec=BED, hb_target=c["hb_target"],
                         apertures=((140.0, 45.0), (150.0, 50.0), (120.0, 35.0)), gen_offsets=(20.0, 0.0))
        th, w = DF.components(c["thm"], c["n"], c["weight"])
        om = 2 * math.pi / c["T"]; k0 = float(DF.kdisp(om, BED["h0"]))
        comps = [dict(theta_deg=round(float(t), 4), a_m=round(float(a), 5), ky=round(float(k0 * math.sin(math.radians(t))), 6)) for t, a in zip(th, r["a_sum"] * w)]
        u3 = json.load(open(os.path.join(OUT, c["u3"]), encoding="utf-8"))
        an = u3["analysis"]
        per = [p for p in an["periods"] if p["p"] >= 4]
        onsets = [p["t_onset_proxy"] for p in per if p["t_onset_proxy"] and p["t_onset_proxy"] >= 45.0 - 3.0]
        onsets = [t for t in onsets if t >= 45.0]
        t_end = c["t_end"]
        frames = int(round(t_end * 24)) + 1
        wins = windows(onsets, c["T"], t_end)
        heavy = sum(int(round((b - a) * 24 / 2)) + 1 for a, b in wins)
        lo = COEF[0] * n05 / 1e6 * GROWTH[0] * frames / 3600.0
        hi = COEF[1] * n05 / 1e6 * GROWTH[1] * frames / 3600.0
        rec = heavy * HEAVY_S / 3600.0
        da = None
        if da1:
            da = [da1["s_per_Mp_frame_lo"] * n05 / 1e6 * GROWTH[0] * frames / 3600.0 + rec, da1["s_per_Mp_frame_hi"] * n05 / 1e6 * GROWTH[1] * frames / 3600.0 + rec]
        L0 = 2 * math.pi / k0
        out["configs"][name] = dict(
            wave=dict(T=c["T"], omega=om, k_h0=k0, L_h0=L0, theta_max_deg=c["thm"], n_components=c["n"], weight=c["weight"],
                      a_sum_m=r["a_sum"], a_component_m=r["a_comp_max"], components=comps, h_gen=BED["h0"],
                      focus=dict(x_f=r["x_f"], y_f=0.0, t_f=0.0, rule="all component phases 0 at (x_f, 0) at t = t_f + nT (crest at the focus every period)"),
                      ramp_s=c["ramp"], ramp="half cosine 0.5(1 - cos(pi t / ramp)), t < ramp",
                      amplitude_rule="a_sum so that the linear centre-row 2|A|/h first reaches gamma_b = %.3f at h_b,target %.1f m (gamma_b from FLIP47 P1c)" % (gb, c["hb_target"])),
            linear=dict(x_b0=r["x_b0"], h_b0=r["h_b0"], Hc_est=r["Hc_est"], widths_over_Hc=r["widths_over_Hc"], widths_m=r["widths_m"], P4a_lin=r["P4a_lin"],
                        P4b_lin=r["P4b_lin"], w90_m=r["w90_m"], fwhm_excess_m=r["fwhm_excess_m"], steep=r["steep"], aperture=r["aperture"], dt_rows=r["dt_rows"],
                        gauges=r["gauges"]),
            u3=dict(file="screen/" + c["u3"], sha16=sha16(os.path.join(OUT, c["u3"])), generation=an["generation"], flat_axis=an["flat_axis"],
                    periods=[dict(p=p["p"], t=p["t_onset_proxy"], x_b=p["x_b"], h_b=p["h_b"], c0=p["c0"], c_side=p["c_side"], P4a=p["P4a"], P4b=p["P4b"],
                                  w90=p["w90"], fwhm=p["fwhm_excess"], widths_over_c0=p["widths_over_c0"]) for p in an["periods"]],
                    periodicity=an.get("periodicity"), levels=an["levels"], mean_currents=an.get("mean_currents")),
            time=dict(t_end_s=t_end, frames=frames, judged_onsets_screen=onsets, windows=wins, heavy_frames_every2=heavy,
                      solve_h=[lo, hi], records_h=rec, total_h=[lo + rec, hi + rec], total_h_DA1_rate=da,
                      launches="%d-%d of <= 29 min" % (math.ceil((lo + rec) * 3600 / 1740), math.ceil((hi + rec) * 3600 / 1740))))
    json.dump(out, open(os.path.join(OUT, "s50_final.json"), "w", encoding="utf-8"), indent=1, default=float)
    for name, c in out["configs"].items():
        print(name, "a_sum %.3f a_j %.3f x_f %.2f L0 %.1f | lin x_b %.1f widths/Hc %s P4b %.2f R2d %.2f R3d %.2f ap %s | time %s DA1rate %s" % (
            c["wave"]["a_sum_m"], c["wave"]["a_component_m"], c["wave"]["focus"]["x_f"], c["wave"]["L_h0"], c["linear"]["x_b0"],
            {k: round(v, 2) for k, v in c["linear"]["widths_over_Hc"].items()}, c["linear"]["P4b_lin"], c["linear"]["steep"]["R2d_max"],
            c["linear"]["steep"]["R3d_max"], c["linear"]["aperture"], [round(v, 2) for v in c["time"]["total_h"]],
            [round(v, 2) for v in (c["time"]["total_h_DA1_rate"] or [])]))
        print("   windows", c["time"]["windows"], "heavy", c["time"]["heavy_frames_every2"], c["time"]["launches"])
    print("particles dp0.5 %d (water %.0f m3), dp1.0 %d" % (n05, V, n10))
    print("DA1", json.dumps(da1))


if __name__ == "__main__":
    main()
