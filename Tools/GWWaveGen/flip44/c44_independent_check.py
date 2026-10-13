# -*- coding: utf-8 -*-
"""FLIP44 の用意の、作っていない者による確かめ（py -3.10、numpy だけ。流体の計算はしない。Houdini も使わない）。
p_plan_numbers.py・g44_cfg.py は読まず（呼ばず）、検討（PeriodicBigWave_Study_ja.md §3.2）と FLIP42 R3 の設定（cfg.json）から、
入口の表と線形の見積もりを別の作り方で出し直し、runs/ready の設定と plan_numbers.json の値と比べる。
  - 分散の関係は 2 分法（作った側はニュートン法）。
  - 礁の上の位相 ∫k dx は、斜面を 0.01 m 刻みのシンプソン則で積む（作った側は 0.5 m 刻みの台形）。
  - 線形の水面は複素の振幅の和で、時間 0.02 s 刻み（作った側は 0.05 s）。
出力：Unity/Build/FLIP44/check/c44_independent.json
"""
import json, math, os, hashlib
import numpy as np

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUT = ROOT + "/Unity/Build/FLIP44/check/c44_independent.json"
G = 9.80665
H0 = 42.0
# 検討 §3.2 の礁（造波板からの距離）
FOOT, EDGE, TOP_END, BACK, HT = 320.0, 470.0, 530.0, 680.0, 12.0


def depth(x):
    x = np.asarray(x, float)
    h = np.full(x.shape, H0)
    m = (x > FOOT) & (x < EDGE); h[m] = H0 - (H0 - HT) * (x[m] - FOOT) / (EDGE - FOOT)
    m = (x >= EDGE) & (x <= TOP_END); h[m] = HT
    m = (x > TOP_END) & (x < BACK); h[m] = HT + (H0 - HT) * (x[m] - TOP_END) / (BACK - TOP_END)
    return h


def kdisp(f, h):
    """ω² = g k tanh(k h) を 2 分法で解く（f・h は同じ形に広げる）。"""
    f, h = np.broadcast_arrays(np.asarray(f, float), np.asarray(h, float))
    om2 = (2 * np.pi * f) ** 2
    lo = np.full(f.shape, 1e-9); hi = np.full(f.shape, 10.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        g = G * mid * np.tanh(mid * h) - om2
        hi = np.where(g > 0, mid, hi); lo = np.where(g > 0, lo, mid)
    return 0.5 * (lo + hi)


def cgroup(f, h):
    k = kdisp(f, h); om = 2 * np.pi * np.asarray(f, float)
    return om / k * 0.5 * (1 + 2 * k * h / np.sinh(2 * k * h))


def Phi(fs, x_end, step=0.01):
    """∫_0^x_end k_i(h(x)) dx（シンプソン則）。"""
    n = int(round(x_end / step)); n += n % 2
    xs = np.linspace(0.0, x_end, n + 1)
    K = kdisp(np.asarray(fs)[:, None], depth(xs)[None, :])
    w = np.ones(n + 1); w[1:-1:2] = 4; w[2:-1:2] = 2
    return (K * w[None, :]).sum(1) * (x_end / n) / 3.0


def wrap(a):
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi


def load(p):
    return json.load(open(p, encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


res = {}
# ------------------------------------------------------------------ 凍結の SHA-256
fz = load(ROOT + "/Unity/Build/FLIP44/plan/plan_frozen.json")
res["frozen_sha_ok"] = {e["path"]: sha(ROOT + "/" + e["path"]) == e["sha256"] for e in fz["frozen"]}

# ------------------------------------------------------------------ R3 の入口を FLIP42 の式から作り直す
r3 = load(ROOT + "/Unity/Build/FLIP42/runs/R3/cfg.json")["parms"]
N = int(r3["ncomp"]); fc, dff, S = r3["fc"], r3["dff"], r3["S"]
fa, fb = fc * (1 - dff / 2), fc * (1 + dff / 2)
f32 = fa + (fb - fa) * np.arange(N) / (N - 1)
k32 = kdisp(f32, H0)
a32 = S / k32.sum()
xb, tb = r3["x_b"], r3["t_b"]
Tc = 1 / fc; Lc = 2 * np.pi / kdisp(fc, H0)
res["tank"] = dict(Tc=Tc, Lc=float(Lc), x_p_cfg=r3["x_p"], Lc_minus_x_p=float(Lc - r3["x_p"]))
ready = ROOT + "/Unity/Build/FLIP44/runs/ready/"
cfg = {n: load(ready + n + ".json") for n in ("PR1", "PR2", "RP_reef500", "RP_flat592")}
pn = load(ROOT + "/Unity/Build/FLIP44/plan/plan_numbers.json")
i1 = cfg["PR1"]["inlet"]
phi_r3 = -k32 * xb + 2 * np.pi * f32 * tb       # FLIP42: cos(k(x−x_p−x_b) − ω(t−t_b)) = cos(k(x−x_p) − ωt + φ)
res["PR1_vs_R3"] = dict(
    n=len(i1["freqs_Hz"]),
    max_df_Hz=float(np.max(np.abs(np.array(i1["freqs_Hz"]) - f32))),
    amp_mine=float(a32), max_damp_m=float(np.max(np.abs(np.array(i1["amps_m"]) - a32))),
    max_dk=float(np.max(np.abs(np.array(i1["k"]) - k32))),
    max_dphase_rad=float(np.max(np.abs(wrap(np.array(i1["phases_rad"]) - phi_r3)))),
    sum_a=float(a32 * N), S_sum_ak=float((a32 * k32).sum()))

# ------------------------------------------------------------------ 位相が狙いの所と時刻で 0 にそろうか（表の値をそのまま使う）
def aim_residual(inl, kind):
    f = np.array(inl["freqs_Hz"]); ph = np.array(inl["phases_rad"])
    xa, ta = inl["aim_x_from_paddle"], inl["aim_t_s"]
    th = (kdisp(f, H0) * xa if kind == "flat" else Phi(f, xa)) - 2 * np.pi * f * ta + ph
    return float(np.max(np.abs(wrap(th))))


res["aim_phase_residual_rad"] = {n: aim_residual(cfg[n]["inlet"], k) for n, k in
                                 (("PR1", "flat"), ("PR2", "reef"), ("RP_reef500", "reef"), ("RP_flat592", "flat"))}
# 礁の上の位相の積分の、作った側（0.5 m 台形）との差の大きさ
res["Phi500_step_sensitivity_rad"] = float(np.max(np.abs(Phi(f32, 500.0, 0.01) - Phi(f32, 500.0, 0.5))))

# ------------------------------------------------------------------ 繰り返しの入口
P = cfg["RP_reef500"]["inlet"]["rep_P"]
band = fb - fa
f8 = np.arange(6, 14) / P
res["RP"] = dict(P=P, P_from_7_over_band=7 / band, max_df_Hz=float(np.max(np.abs(np.array(cfg["RP_reef500"]["inlet"]["freqs_Hz"]) - f8))),
                 amp=cfg["RP_reef500"]["inlet"]["amps_m"][0], amp_from_sum=a32 * N / 8,
                 S_sum_ak=float((cfg["RP_reef500"]["inlet"]["amps_m"][0] * kdisp(f8, H0)).sum()),
                 f_end_reef=cfg["RP_reef500"]["f_end"], f_end_flat=cfg["RP_flat592"]["f_end"])
for n in ("RP_reef500", "RP_flat592"):
    inl = cfg[n]["inlet"]
    f = np.array(inl["freqs_Hz"]); a = np.array(inl["amps_m"]); ph = np.array(inl["phases_rad"])
    t = np.arange(0.0, P, 0.01)
    env = np.abs((a[None, :] * np.exp(1j * (ph[None, :] - 2 * np.pi * f[None, :] * t[:, None]))).sum(1))
    eta = (a[None, :] * np.cos(ph[None, :] - 2 * np.pi * f[None, :] * t[:, None])).sum(1)
    # 1 Tc の移動平均のエネルギー（円で回す）
    w = int(round(Tc / 0.01)); e2 = np.convolve(np.r_[eta[-w:], eta, eta[:w]] ** 2, np.ones(w) / w, "same")[w:-w]
    res["RP"][n] = dict(envelope_min_t_mod_P=float(t[np.argmin(env)]), envelope_min_over_max=float(env.min() / env.max()),
                        energy1Tc_min_t_mod_P=float(t[np.argmin(e2)]),
                        aim_t=inl["aim_t_s"], t_end_expected=inl["aim_t_s"] + 3 * P + 2 * Tc,
                        f_end_expected=int(math.floor((inl["aim_t_s"] + 3 * P + 2 * Tc) * 24 + 1e-9)) + 1,
                        f_end_cfg=cfg[n]["f_end"],
                        periodic_3P_maxdiff=float(np.max(np.abs(eta - (a[None, :] * np.cos(ph[None, :] - 2 * np.pi * f[None, :] * (t[:, None] + 3 * P))).sum(1)))))


# ------------------------------------------------------------------ 線形の見積もり（ゆっくり変わる海底：位相 ∫k dx、振幅 √(cg0/cg)）
def linear_field(inl, period, xs, dt=0.02):
    f = np.array(inl["freqs_Hz"]); a = np.array(inl["amps_m"]); ph = np.array(inl["phases_rad"])
    t = np.arange(0.0, period, dt)
    out = []
    # 位相の積分を x の列にそって 1 回で（0.01 m シンプソンを区間ごとに足す）
    Ph = np.zeros((len(f), len(xs)))
    for j in range(1, len(xs)):
        x0, x1 = xs[j - 1], xs[j]
        n = 20
        xx = np.linspace(x0, x1, n + 1)
        K = kdisp(f[:, None], depth(xx)[None, :])
        w = np.ones(n + 1); w[1:-1:2] = 4; w[2:-1:2] = 2
        Ph[:, j] = Ph[:, j - 1] + (K * w).sum(1) * (x1 - x0) / n / 3
    A = np.sqrt(cgroup(f, H0)[:, None] / cgroup(f[:, None], depth(xs)[None, :]))
    C = a[:, None] * A * np.exp(1j * (Ph + ph[:, None]))       # (成分, x)
    E = np.exp(-1j * 2 * np.pi * f[:, None] * t[None, :])        # (成分, t)
    for j in range(len(xs)):
        eta = np.real(C[:, j] @ E)
        # 山（時間の局所の最大）
        ii = np.where((eta[1:-1] > eta[:-2]) & (eta[1:-1] >= eta[2:]))[0] + 1
        pk = np.sort(eta[ii])[::-1]
        jm = int(np.argmax(eta))
        out.append((float(xs[j]), float(pk[0]), float(pk[1] / pk[0]) if len(pk) > 1 else None, float(t[jm])))
    return out


def summarize(rows):
    x = np.array([r[0] for r in rows]); m = np.array([r[1] for r in rows]); s = np.array([r[2] for r in rows]); tm = np.array([r[3] for r in rows])
    top = (x >= 470) & (x <= 530)
    g = int(np.argmax(m))
    return dict(paddle=float(m[0]), global_max=[float(x[g]), float(m[g]), float(tm[g])],
                reef_top=[float(m[top].min()), float(m[top].max())], second=[float(s[top].min()), float(s[top].max())])


xs = np.arange(0.0, 930.0 + 1e-9, 1.0)
lin = {}
for n, per in (("PR1", 403.7431634893572), ("PR2", 403.7431634893572), ("RP_reef500", P), ("RP_flat592", P)):
    lin[n] = summarize(linear_field(cfg[n]["inlet"], per, xs))
res["linear_mine"] = lin
key = {"PR1": "PR1_R3_flat592", "PR2": "PR2_reef_aim500", "RP_reef500": "RP_reef500", "RP_flat592": "RP_flat592"}
res["linear_plan"] = {n: dict(paddle=pn["programs"][key[n]]["paddle"]["max_crest_m"], global_max=pn["programs"][key[n]]["global_max"],
                              reef_top=pn["programs"][key[n]]["reef_top_470_530"]) for n in key}


# ------------------------------------------------------------------ PR2 の狙いの時刻（造波板の所のエネルギーの重心を R3 とそろえる）
def paddle_centroid(inl, period=403.7431634893572, dt=0.01):
    f = np.array(inl["freqs_Hz"]); a = np.array(inl["amps_m"]); ph = np.array(inl["phases_rad"])
    t = np.arange(0.0, period, dt)
    env2 = np.abs((a[None, :] * np.exp(1j * (ph[None, :] - 2 * np.pi * f[None, :] * t[:, None]))).sum(1)) ** 2
    eta2 = (a[None, :] * np.cos(ph[None, :] - 2 * np.pi * f[None, :] * t[:, None])).sum(1) ** 2
    return float((t * env2).sum() / env2.sum()), float((t * eta2).sum() / eta2.sum())


res["paddle_centroid"] = {n: paddle_centroid(cfg[n]["inlet"]) for n in ("PR1", "PR2")}

# ------------------------------------------------------------------ 設定の 2 進の割り切れと水槽
chk = {}
for n, c in cfg.items():
    p = c["parms"]; vox = p["dp"] * p["gridscale"]
    chk[n] = dict(dp=p["dp"], dp_binary_exact=(p["dp"] * 2 ** 10) == int(p["dp"] * 2 ** 10), vox=vox,
                  Lx_over_vox=p["Lx"] / vox, Lz_over_vox=p["Lz"] / vox, narrowband=c["solver"]["donarrowband"],
                  reef=[p["reef_on"], p["rf_foot"], p["rf_top_end"], p["rf_h_top"], p["rf_slope_n"]],
                  reef_edge=p["rf_foot"] + (p["h0"] - p["rf_h_top"]) * p["rf_slope_n"],
                  reef_back=p["rf_top_end"] + (p["h0"] - p["rf_h_top"]) * p["rf_slope_n"],
                  absorber_from_paddle=p["xa0"] - p["x_p"], wind_on=p["wind_on"], amp_gain=p["amp_gain"],
                  sec=c["sec"], f_end=c["f_end"], max_hours=c.get("max_hours"), wall_limit_s=c["wall_limit_s"], stop=c.get("stop_check"))
res["cfg"] = chk
# 風の q
res["wind_q"] = {U: 0.5 * 1.2 * (U + 12.0) ** 2 for U in (35.0, 45.0)}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
