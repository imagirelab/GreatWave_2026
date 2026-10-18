# -*- coding: utf-8 -*-
"""FLIP52B3 (DFG-2B round 3) shared helpers for the three-run comparison DFG-2B-E / DFG-S-E140 / DFGB3 (py -3.10 -B; numpy, scipy).
2026-10-18 written new (Claude). Nothing of FLIP52B / FLIP52B2 / FLIP52S2 is edited: run folders, cfgs, judges and frozen tools are READ ONLY.
Imports READ ONLY: flip51/e51_metrics (frozen ruler: median3, hf_metrics, section_metrics, score_vs_target), flip52/g52_ana (Blocks, lip test).
Writes only under Unity/Build/FLIP52B3/ (diag/, _scratch/).
Bed per run from its own cfg parms (the FLIP48/49 ridge formula with k 0: laterally uniform):
  R(x) = max(x - x0, 0) / s up to R = h0 - pg_hL, then (h0 - pg_hL) + (x - x_L) / pg_s2 (pg_s2 > 0); h = max(shelf_h, h0 - R) (shelf_h 0: to the shore).
Tags: [measured] [computed] [calibrated] [guess] [chosen] [literature].
"""
import os, sys, json, math

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = os.environ.get("B3_THREADS", "2")
REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in (REPO + "/Tools/GWWaveGen/flip50", REPO + "/Tools/GWWaveGen/flip51", REPO + "/Tools/GWWaveGen/flip52"):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                      # noqa: E402
import e51_metrics as EM                # noqa: E402  read only (frozen ruler)
import g52_ana as GA52                  # noqa: E402  read only

OUT = REPO + "/Unity/Build/FLIP52B3/diag"
SCR = REPO + "/Unity/Build/FLIP52B3/_scratch"
FPS = 24.0
G = 9.81
T_M = 7.0                                # T_m01 of the three equal layers (mean frequency 4 / 28 s) [computed]
T_RANGE = (5.6, 9.333333)

RUNS = {
    "B2E": dict(name="DFG-2B-E", rd=REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5", judge="g52b/judge_DFGB.json",
                coeq="g52b/coequal_DFGB.json", pv="DFGB2E_D19B_xf272p25_dp0p5", ymax=95.0),
    "S2E": dict(name="DFG-S-E140", rd=REPO + "/Unity/Build/FLIP52S2/runs/DFGS2E_step3h6_xf145_W140_dp0p5", judge="g52s2/judge_DFGS2.json",
                coeq="g52s2/coequal_DFGS2.json", pv="DFGS2E_step3h6_xf145_W140_dp0p5", ymax=65.0),
    "B3": dict(name="DFGB3", rd=REPO + "/Unity/Build/FLIP52B2/runs/DFGB3_D19Bs3h6_xf272p25_dp0p5", judge="g52b2/judge_DFGB3.json",
               coeq="g52b2/coequal_DFGB3.json", pv="DFGB3_D19Bs3h6_xf272p25_dp0p5", ymax=95.0),
}


def jload(p):
    with open(p, encoding="utf8") as fh:
        return json.load(fh)


def jdump(o, p):
    def cl(v):
        if isinstance(v, dict):
            return {str(k): cl(w) for k, w in v.items()}
        if isinstance(v, (list, tuple)):
            return [cl(w) for w in v]
        if isinstance(v, (np.floating, float)):
            return None if not np.isfinite(v) else round(float(v), 6)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, np.ndarray):
            return cl(v.tolist())
        return v
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf8") as fh:
        json.dump(cl(o), fh, ensure_ascii=False, indent=1)


class Bed:
    def __init__(self, parms):
        p = parms
        self.h0 = float(p["h0"]); self.x0 = float(p["ridge_x0"]); self.s = float(p["ridge_s"])
        self.hs = float(p["shelf_h"]); self.hL = float(p.get("pg_hL", 0.0)); self.s2 = float(p.get("pg_s2", 0.0))

    def h(self, x):
        x = np.asarray(x, float)
        R = np.maximum(x - self.x0, 0.0) / self.s
        if self.s2 > 0 and self.hL > 0:
            RL = self.h0 - self.hL; xL = self.x0 + RL * self.s
            R = np.where(x > xL, RL + (x - xL) / self.s2, R)
        return np.maximum(self.hs, self.h0 - R)

    def slope(self, x, half=0.5):
        """bed slope tan(beta) = -dh/dx averaged over x +- half [computed]."""
        return float((self.h(x - half) - self.h(x + half)) / (2 * half))


def run_ctx(key):
    r = dict(RUNS[key]); rd = r["rd"]
    r["cfg"] = jload(rd + "/cfg.json"); r["bed"] = Bed(r["cfg"]["parms"])
    r["J"] = jload(rd + "/" + r["judge"])
    r["PV"] = jload(REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (r["pv"], r["pv"]))
    r["eta0"] = float(r["J"]["eta0"])
    return r


def kdisp(om, h):
    """linear dispersion om^2 = g k tanh(k h) (Newton) [computed]."""
    k = om * om / G / max(math.tanh(om * math.sqrt(max(h, 1e-6) / G)), 1e-6) ** 0.5
    for _ in range(50):
        f = G * k * math.tanh(k * h) - om * om
        d = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / d
    return k


def cg_c(T, h):
    om = 2 * math.pi / T; k = kdisp(om, h); c = om / k
    n = 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h))
    return c, n * c, k


def L0(T):
    return G * T * T / (2 * math.pi)


def iribarren(slope, H, T=T_M):
    return slope / math.sqrt(max(H, 1e-6) / L0(T))
