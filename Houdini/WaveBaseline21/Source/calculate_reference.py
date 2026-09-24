"""21の有限水深線形波を計算する。Houdini/Unityの起動や流体計算は行わない。"""
import csv
import hashlib
import json
import math
import platform
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

BASE = Path(__file__).resolve().parents[1]
EVIDENCE = BASE / "Evidence"
EVIDENCE.mkdir(exist_ok=True)
CONFIG = BASE / "Source/conditions.json"
cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
p = cfg["physics"]
tank = cfg["full_tank_candidate"]
a, T, h, g = p["wave_height_m"] / 2, p["period_s"], p["depth_m"], p["gravity_m_s2"]
omega = 2 * math.pi / T

# 単調な色散式の正根を二分法で解き、浅水/深水近似を使わない。
lo, hi = 0.0, 1.0
while g * hi * math.tanh(hi * h) < omega**2:
    hi *= 2
for _ in range(100):
    mid = (lo + hi) / 2
    if g * mid * math.tanh(mid * h) < omega**2:
        lo = mid
    else:
        hi = mid
k = (lo + hi) / 2
lam, c = 2 * math.pi / k, omega / k
cg = c * 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h))
length = tank["length_wavelengths"] * lam
gauges = np.array(tank["gauge_x_wavelengths"]) * lam
ramp_time = tank["ramp_duration_periods"] * T
inlet = np.array(tank["inlet_zone_wavelengths"]) * lam
absorber = np.array(tank["absorber_zone_wavelengths"]) * lam
pilot = cfg["pilot_candidate"]


def eta(x, t):
    return a * np.cos(k * np.asarray(x) - omega * np.asarray(t) + p["phase_at_origin_rad"])


def velocity(x, y, t):
    theta = k * np.asarray(x) - omega * np.asarray(t) + p["phase_at_origin_rad"]
    u = a * omega * np.cosh(k * (np.asarray(y) + h)) / math.sinh(k * h) * np.cos(theta)
    v = a * omega * np.sinh(k * (np.asarray(y) + h)) / math.sinh(k * h) * np.sin(theta)
    return u, v


def ramp(t):
    return 0.5 * (1 - np.cos(math.pi * np.clip(np.asarray(t) / ramp_time, 0, 1)))


def write_json(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_csv(name, header, rows):
    with (EVIDENCE / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([format(float(v), ".17g") for v in row])


times = np.arange(round(tank["record_end_s"] * tank["output_sample_rate_hz"]) + 1) / tank["output_sample_rate_hz"]
xs = np.linspace(0, length, 601)
ys = np.linspace(-h, 0, 61)
write_csv("21_theory_gauges.csv", ["time_s", "steady_eta_g1_m", "steady_eta_g2_m", "steady_eta_g3_m", "inlet_ramp_factor"],
          ([t, *eta(gauges, t), ramp(t)] for t in times))
write_csv("21_theory_profile.csv", ["x_m", "steady_eta_t0_m", "steady_eta_t_quarter_period_m"],
          ([x, eta(x, 0), eta(x, T / 4)] for x in xs))
write_csv("21_theory_velocity.csv", ["y_m", "u_at_crest_m_s", "v_at_phase_pi_over_2_m_s"],
          ([y, velocity(0, y, 0)[0], velocity(lam / 4, y, 0)[1]] for y in ys))

derived = {
    "case_id": cfg["case_id"], "classification_ja": "解析式のみ。実波・FLIP未計算。",
    "amplitude_m": a, "omega_rad_s": omega, "k_rad_m": k, "wavelength_m": lam,
    "phase_speed_m_s": c, "group_speed_m_s": cg, "long_wave_speed_bound_m_s": math.sqrt(g * h),
    "kh": k * h, "ka": k * a, "a_over_h": a / h, "H_over_lambda": 2 * a / lam,
    "surface_u_amplitude_m_s": float(velocity(0, 0, 0)[0]), "surface_v_amplitude_m_s": a * omega,
    "tank_length_m": length, "tank_initial_water_volume_m3": length * tank["width_m"] * h,
    "inlet_zone_x_m": inlet.tolist(),
    "absorber_zone_x_m": absorber.tolist(),
    "gauge_x_m": gauges.tolist(), "adjacent_crest_delay_s": (np.diff(gauges) / c).tolist(),
    "first_to_last_crest_delay_s": float((gauges[-1] - gauges[0]) / c),
    "ramp_end_s": ramp_time,
    "ramp_plus_farthest_group_travel_s_heuristic": ramp_time + float(gauges[-1] / cg),
    "return_from_absorber_front_with_source_at_origin_s_heuristic": float((2 * absorber[0] - gauges[-1]) / math.sqrt(g * h)),
    "return_with_inlet_zone_extent_s_heuristic": float((2 * absorber[0] - gauges[-1] - inlet[1]) / math.sqrt(g * h)),
    "window_note_ja": "到達/反射時刻は長波や過渡・境界実装で変わる。9〜16.5sを無反射と保証しない。",
    "theory_csv_count": len(times), "theory_sample_rate_hz": tank["output_sample_rate_hz"],
    "theory_end_s": float(times[-1]),
    "particle_count_order_only": [
        {"particle_separation_m": dp, "full_volume_over_dp_cubed": length * tank["width_m"] * h / dp**3,
         "pilot_volume_over_dp_cubed": pilot["length_wavelengths"] * lam * pilot["width_m"] * h / dp**3,
         "H_over_dp": 2 * a / dp}
        for dp in [0.04, 0.03, 0.02]
    ]
}
write_json("21_derived_parameters.json", derived)

# 実装の符号・単位・境界・位相を独立した有限差分/標本fitで検算する。
check_times = np.linspace(0.11, 2 * T, 37)
check_x = np.linspace(0.13, 2 * lam, 37)
check_y = np.linspace(-h, 0, 37)
epsilon = 1e-5
bed_v = float(np.max(np.abs(velocity(check_x, -h, check_times)[1])))
surface_v = velocity(check_x, 0, check_times)[1]
eta_dt = (eta(check_x, check_times + epsilon) - eta(check_x, check_times - epsilon)) / (2 * epsilon)
ux = (velocity(check_x + epsilon, check_y, check_times)[0] - velocity(check_x - epsilon, check_y, check_times)[0]) / (2 * epsilon)
vy = (velocity(check_x, check_y + epsilon, check_times)[1] - velocity(check_x, check_y - epsilon, check_times)[1]) / (2 * epsilon)
period_error = float(np.max(np.abs(eta(check_x, check_times + T) - eta(check_x, check_times))))
wavelength_error = float(np.max(np.abs(eta(check_x + lam, check_times) - eta(check_x, check_times))))
following_error = float(np.max(np.abs(eta(check_x + c * 0.37, check_times + 0.37) - eta(check_x, check_times))))
fit_t = np.arange(600) / 60.0
design = np.column_stack([np.ones(len(fit_t)), np.cos(omega * fit_t), np.sin(omega * fit_t)])
fit = np.linalg.lstsq(design, eta(gauges[None, :], fit_t[:, None]), rcond=None)[0]
phases = np.unwrap(np.arctan2(fit[2], fit[1]))
delays = np.diff(phases) / omega
gauge_delay_error = float(np.max(np.abs(delays - np.diff(gauges) / c)))
reflection_matrix = np.column_stack([np.exp(1j * k * gauges), np.exp(-1j * k * gauges)])
incident_reflected = np.linalg.lstsq(reflection_matrix, fit[1] + 1j * fit[2], rcond=None)[0]
reflection_recovery = float(abs(incident_reflected[1]) / abs(incident_reflected[0]))
relative_dispersion = abs(g * k * math.tanh(k * h) - omega**2) / omega**2
checks = {
    "dispersion_relative_residual": {"value": relative_dispersion, "limit": 1e-12},
    "bed_normal_velocity_max_m_s": {"value": bed_v, "limit": 1e-12},
    "linear_surface_kinematic_fd_error_m_s": {"value": float(np.max(np.abs(surface_v - eta_dt))), "limit": 1e-8},
    "incompressibility_fd_error_s_inv": {"value": float(np.max(np.abs(ux + vy))), "limit": 1e-8},
    "period_repeat_error_m": {"value": period_error, "limit": 1e-12},
    "wavelength_repeat_error_m": {"value": wavelength_error, "limit": 1e-12},
    "positive_x_following_crest_error_m": {"value": following_error, "limit": 1e-12},
    "adjacent_fitted_gauge_delay_error_s": {"value": gauge_delay_error, "limit": 1e-12},
    "synthetic_incident_only_reflection_recovery": {"value": reflection_recovery, "limit": 1e-12}
}
for v in checks.values():
    v["passed"] = math.isfinite(v["value"]) and v["value"] <= v["limit"]
passed = all(v["passed"] for v in checks.values())
write_json("21_numeric_checks.json", {
    "classification_ja": "解析式コードの自己検査。FLIPの精度判定ではない。", "passed": passed,
    "checks": checks, "fitted_adjacent_delay_s": delays.tolist(),
    "gauge_reflection_matrix_condition_number": float(np.linalg.cond(reflection_matrix)),
    "phase_note_ja": "隣接.2λ/.35λで位相をunwrap。端間.55λをprincipal phaseのみで扱わない。"
})
if not passed:
    raise RuntimeError("21の解析式検算が不合格")

# 日本語フォントを明示し、実シミュレーションに見える図を作らない。
font_path = Path("C:/Windows/Fonts/meiryo.ttc")
if not font_path.exists():
    raise FileNotFoundError("日本語フォントが見つかりません。別環境ではfont_pathを明示してください。")
font = FontProperties(fname=str(font_path))
plt.rcParams.update({"font.family": font.get_name(), "font.size": 11, "axes.unicode_minus": False})
fig = plt.figure(figsize=(14, 10), layout="constrained", facecolor="#f8f5ed")
grid = fig.add_gridspec(3, 1, height_ratios=[1.1, 1, 1.2])
fig.suptitle("21  有限水深の単色波：解析式のみ・流体シミュレーション未実施", fontsize=18, fontweight="bold")
ax = fig.add_subplot(grid[0])
ax.axvspan(*tank["inlet_zone_wavelengths"], color="#f4c579", alpha=.6, label="入口強制帯（22候補）")
ax.axvspan(*tank["absorber_zone_wavelengths"], color="#bfd4b4", alpha=.7, label="出口減衰帯（未検証）")
ax.fill_between(xs / lam, -h, eta(xs, 0), color="#b9d6e3", alpha=.8)
ax.plot(xs / lam, eta(xs, 0), color="#164968", lw=2, label="定常理論の水面 t=0")
ax.axhline(-h, color="#555555", lw=2)
for i, gx in enumerate(gauges):
    ax.plot([gx / lam, gx / lam], [-.2, .16], "--", color="#b24b37")
    ax.text(gx / lam, .2, f"G{i+1}", ha="center", color="#a43427")
ax.set(xlim=(0, tank["length_wavelengths"]), ylim=(-h-.1, tank["top_y_m"]+.02), xlabel="X / λ（+Xへ進行）", ylabel="Y [m]", title="全槽候補の断面。定常理論は槽の初期状態ではなく、実初期条件は静水・速度0。")
ax.legend(loc="lower right", fontsize=9, ncol=3)
ax = fig.add_subplot(grid[1])
ax.plot(xs / lam, eta(xs, 0) * 100, label="t=0", lw=2, color="#164968")
ax.plot(xs / lam, eta(xs, T / 4) * 100, "--", label="t=T/4", color="#bd663d")
ax.set(xlim=(0, 3), ylim=(-a*125, a*125), xlabel="X / λ", ylabel="η [cm]", title=f"H={2*a*100:g} cm・T={T:g} s・h={h:g} m → λ={lam:.6f} m、位相速度={c:.6f} m/s（縦横比は非等倍）")
ax.legend(loc="upper right", ncol=2)
ax.grid(alpha=.25)
ax = fig.add_subplot(grid[2])
for i, gx in enumerate(gauges):
    ax.plot(times, eta(gx, times) * 100, label=f"G{i+1}: X/λ={gx/lam:g}", lw=1.7)
ax.set(xlim=(0, 4*T), ylim=(-a*125, a*125), xlabel="理論時刻 [s]", ylabel="定常η [cm]", title="理論波高計：入力立ち上げや伝播到達を表すCSVではない。実波高計は22で別採録。")
ax.legend(loc="upper right", ncol=3)
ax.grid(alpha=.25)
fig.savefig(EVIDENCE / "21_analytic_reference.png", dpi=140, metadata={"Description": "解析式のみ。Houdini/Unity出力ではない。"})
plt.close(fig)

files = [CONFIG, Path(__file__), BASE / "Source/requirements.lock.txt", BASE / "README_ja.md"]
files += sorted(p for p in EVIDENCE.iterdir() if p.name != "21_provenance.json")
write_json("21_provenance.json", {
    "case_id": cfg["case_id"], "classification_ja": "理論基準の計算。Houdini/Unity実行なし。",
    "python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__,
    "font": font_path.name, "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
    "files": [{"path": p.relative_to(BASE).as_posix(), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    "checks_passed": passed, "fluid_simulated": False, "hmd_verified": False
})
print(json.dumps({"checks_passed": passed, "k": k, "wavelength_m": lam, "phase_speed_m_s": c, "group_speed_m_s": cg, "gauge_x_m": gauges.tolist(), "csv_rows": len(times)}))
