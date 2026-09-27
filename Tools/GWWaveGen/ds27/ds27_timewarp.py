# -*- coding: utf-8 -*-
"""設計27 の層7：世界全体の時間曲線 τ(t)（設計26 §3.2。Q11 で D31 は既定を採用、代案も描いて比べる）。

- 既定（default、D31 の (a)）：t 7.936 s まで実時間 → 1 s の smoothstep で 0.5 倍へ（終わりは唇先が最初に頂点に着く
  τ −1.432 s）→ 0.5 倍の一定のスロー → 0.4 s の smoothstep で止めて t* = 12.0 s → 12〜14 s は τ = 0 で保持。
  τ(0) = −10.118 s。保持の後（14 s 以後）は設計47 で決める（Q11 で崩壊と再開は作らない）。
- 代案（alt、D31 の (b)）：実時間のまま t* で瞬間に止めて 12〜14 s 保持。τ(t) = t − 12（t 0 s で τ −12 s。設計26 の代案のとおり）。
  設計27修正の1回目で生成器の範囲を τ −12 s まで広げた（初回は τ ≥ −10.125 s で、t 0〜1.882 s が最初の姿のまま止まっていた）。
表：{"t": [...], "tau": [...]}（t 0〜14 s を 240 Hz、3361 点。解析式の値）。Unity と関門の検査は線形補間で読む。
使い方：py -3.10 Tools/GWWaveGen/ds27/ds27_timewarp.py（Tools/GWWaveGen/ds27/timewarp_default.json・timewarp_alt.json を書く）。
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T_STAR = 12.0
T_END = 14.0
HZ = 240


def params_from_conditions(cond):
    d = cond["time_warp"]["default"]
    return dict(t1=float(d["real_time_until_t_s"]), d1=float(d["ramp_to_r0_s"]), r0=float(d["r0"]), tf=float(d["freeze_ramp_s"]),
                hold=float(d["hold_s"]))


def tau_default(t, t1=7.936, d1=1.0, r0=0.5, tf=0.4):
    """既定の τ(t)（解析式）。r(t) を区間ごとに積分。∫0^x S = x³ − x⁴/2。"""
    t = np.asarray(t, np.float64)
    ta = t1 + d1                     # スローの始まり
    tb = T_STAR - tf                 # 止めるための 0.4 s の始まり
    # t* から逆に積む
    I_freeze = r0 * tf * (1.0 - 0.5)                     # ∫ r0 (1 − S) = r0 tf (1 − (1 − 1/2)) = r0 tf / 2
    I_const = r0 * (tb - ta)
    I_ramp = d1 * (1.0 - (1.0 - r0) * 0.5)               # ∫ (1 − (1 − r0) S) = d1 (1 − (1 − r0)/2)
    tau_b = -I_freeze
    tau_a = tau_b - I_const
    tau_1 = tau_a - I_ramp

    def iS(x):
        x = np.clip(x, 0.0, 1.0)
        return x ** 3 - x ** 4 / 2
    out = np.empty_like(t)
    m = t < t1
    out[m] = tau_1 - (t1 - t[m])
    m = (t >= t1) & (t < ta)
    x = (t[m] - t1) / d1
    out[m] = tau_1 + d1 * (x - (1 - r0) * iS(x))
    m = (t >= ta) & (t < tb)
    out[m] = tau_a + r0 * (t[m] - ta)
    m = (t >= tb) & (t < T_STAR)
    x = (t[m] - tb) / tf
    out[m] = tau_b + r0 * tf * (x - iS(x))
    out[t >= T_STAR] = 0.0
    return out


def rate_default(t, t1=7.936, d1=1.0, r0=0.5, tf=0.4):
    t = np.asarray(t, np.float64)
    S = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    r = np.ones_like(t)
    m = (t >= t1) & (t < t1 + d1)
    r[m] = 1 - (1 - r0) * S((t[m] - t1) / d1)
    r[(t >= t1 + d1) & (t < T_STAR - tf)] = r0
    m = (t >= T_STAR - tf) & (t < T_STAR)
    r[m] = r0 * (1 - S((t[m] - (T_STAR - tf)) / tf))
    r[t >= T_STAR] = 0.0
    return r


def tau_alt(t, tau_start=None):
    t = np.asarray(t, np.float64)
    tt = t - T_STAR if tau_start is None else np.maximum(t - T_STAR, tau_start)
    return np.where(t < T_STAR, tt, 0.0)


def tables(cond=None):
    kw = params_from_conditions(cond) if cond else dict(t1=7.936, d1=1.0, r0=0.5, tf=0.4, hold=2.0)
    hold = kw.pop("hold", 2.0)
    t = np.round(np.arange(0, int(round(T_END * HZ)) + 1) / HZ, 9)
    tau_d = tau_default(t, **kw)
    tau0 = float(tau_d[0])
    tau_a = tau_alt(t)
    info = dict(t1=kw["t1"], d1=kw["d1"], r0=kw["r0"], tf=kw["tf"], hold_s=hold, tau_at_t0_default=tau0,
                apex_t=kw["t1"] + kw["d1"], freeze_start_t=T_STAR - kw["tf"], apparent_g_mps2=9.81 * kw["r0"] ** 2)
    return t, tau_d, tau_a, info


def write_tables(outdir=HERE, cond=None):
    t, tau_d, tau_a, info = tables(cond)
    res = {}
    for name, tau, note in (("default", tau_d, "D31 (a) 既定（Q11 で採用）：実時間 → 1 s で 0.5 倍 → 0.5 倍 → 0.4 s で止め、t* = 12 s で 2 s 保持"),
                            ("alt", tau_a, "D31 (b) 代案（比べるために描く）：実時間のまま t* で瞬間に止め、2 s 保持（τ = t − 12、t 0 s で τ −12 s）")):
        J = {"schema": "GreatWave.DS27.timewarp/1", "id": name, "note_ja": note, "t_star_s": T_STAR, "hz": HZ, "params": info,
             "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
        p = os.path.join(outdir, "timewarp_%s.json" % name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        res[name] = p
    return res, info


if __name__ == "__main__":
    import sys
    sys.path.insert(0, HERE)
    from ds27_model import load_json, REPO
    cond = load_json(os.path.join(REPO, "Docs", "Evidence", "Design", "26", "ds26_conditions.json"))
    r, info = write_tables(HERE, cond)
    print(json.dumps(dict(files=r, info=info), ensure_ascii=False))
