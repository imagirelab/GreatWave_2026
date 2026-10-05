# -*- coding: utf-8 -*-
"""設計28修正01（Q13）：唇の伸び出しと頂の上昇の重なり（T1）と、爪の育ち方（T2）を、パッケージで測る検査器。

README
======
パッケージ（設計27 の書式。ds27_gates.Package と同じ Hermite・量子化で読む）を τ −5.0〜0 s の 60 Hz で読み、次を測る。

T1（重なり）：主断面（行 159）と峰の行（行 192）で
  - 頂の高さ H(τ)（ds27_gates.row_metrics の本体の頂）、Hf = t* の H、張り出し Lo（定義 A：内壁の 0.3H を最後に下へ横切る点から、
    0.3H より上の前の部分の a の最大まで）。唇先の頂からの前への距離 (a_tip − a_頂)/H も記録（内壁が動かない「唇先の前進」の読み）。
  - 伸び出しの始まり τ_e：Lo ≥ 0.05H を満たし、その後 t* まで満たし続ける最初の時刻。
  - 判定：H(τ_e)/Hf ≤ 0.75、H(t*) − H(τ_e) ≥ 0.25 Hf、τ_e から t* まで H が単調（戻り ≤ 0.05 m）、
    t* の前に H ≥ 0.95 Hf が 0.5 s を超えて続かない（頭打ちなし）、H の最大が t* から 0.2 s 以内。
T2（爪）：巻きの行（133 行）の唇の列（K* の頂の列 jt〜rim）で
  - 行の間の爪（指）：唇の前の部分（K* の唇先の 60 列前〜rim）の、頂からの相対の断面座標 (a − a_頂, y − H) を波峰線方向に σ 1.0 m の
    ガウスでならした値からのずれ（高域）の RMS（頂の列が行ごとに跳ぶ K* の頂の近くの列は、本体と唇の役が行で入れ替わるので含めない）。
  - 行の中の鉤：列の方向に 5 列のガウス（ds_claws を切った標的と同じ）でならした値からのずれの RMS。
  - それぞれ t* の値で割った割合 C(τ)。唇の伸び出しの進み E(τ)：巻きの行ごとに (Lo − 0.05H)/(Lo(t*) − 0.05H) を 0〜1 に切り、行の中央値。
  - 判定：C が伸び出しの始まり（主断面と峰の行の早い方）から単調（戻り ≤ 0.02）、始まりの C ≤ 0.35（伸び出しの前に埋まっていない）、
    C が E より 0.2 を超えて遅れない（E − C ≤ 0.2：伸び出しの後に遅れて埋まらない）。記録：|C − E| の最大、C・E が 0.25・0.5・0.75 に届く τ。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_q13.py --package Unity/Build/Design/28R01/art_on --out Unity/Build/Design/28R01/q13/art_on.json
numpy だけ。Unity の描画ではない。
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402

fnum = DG.fnum
rel = DG.rel
HZ = 60
TIP_COLS = 60     # 行の間の爪を測る列：唇先の 60 列前（放出の前の帯で約 1.2 m、t* の K* で唇の前の約 4〜6 m）から rim まで
TH = dict(T1_H_at_start_max=0.75, T1_rise_after_start_min=0.25, T1_mono_m=0.05, T1_plateau_frac=0.95, T1_plateau_s=0.5,
          T1_max_near_tstar_s=0.2, T1_Lo_start=0.05, T2_mono=0.02, T2_lag=0.2, T2_start_max=0.35, claw_sigma_c_m=1.0)


def gauss_rows(c, sg):
    W = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sg) ** 2)
    return W


def claw_setup(ks):
    rows = ks.curled_idx
    q = ks.cq
    mask = np.zeros((len(rows), ks.nu), bool)
    for i, r in enumerate(rows):
        mask[i, max(q[r]["jtip"] - TIP_COLS, q[r]["jt"] + 6):q[r]["rim"] + 1] = True
    W = gauss_rows(ks.c[rows], TH["claw_sigma_c_m"])
    g = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
    g /= g.sum()
    return dict(rows=rows, mask=mask, W=W, g=g)


def claw_fields(ks, A, Y, C, ca, H):
    """行の間の爪（高域）と行の中の鉤（列の平滑からのずれ）の場（ベクトル、m）。断面の座標は行ごとの頂（a、H）からの相対（頂の線の曲がりを除く）。"""
    rows, mask, W, g = C["rows"], C["mask"], C["W"], C["g"]
    a = A[rows] - ca[rows][:, None]
    y = Y[rows] - H[rows][:, None]
    m = mask.astype(float)
    den = W @ m
    sa = (W @ (a * m)) / np.maximum(den, 1e-12)
    sy = (W @ (y * m)) / np.maximum(den, 1e-12)
    ok = mask & (den > 1e-9)
    cross = np.concatenate([(a - sa)[ok], (y - sy)[ok]])
    hk = []
    for i, r in enumerate(rows):
        q = ks.cq[r]
        j0, j1 = q["jt"], q["rim"] + 1
        pa = a[i, j0:j1]
        py = y[i, j0:j1]
        if len(pa) < 14:
            continue
        cxa = np.convolve(np.pad(pa, 6, mode="edge"), g, mode="valid")
        cxy = np.convolve(np.pad(py, 6, mode="edge"), g, mode="valid")
        hk.append(np.concatenate([(pa - cxa)[3:-3], (py - cxy)[3:-3]]))
    return cross, np.concatenate(hk)


def claw_series(F):
    """場の列 F (nt, n) から、RMS と、t* の場への射影の割合 <F(τ), F(0)>/<F(0), F(0)>（t* の爪の模様がどれだけ出ているか。
    放出の前の帯の並びの行ごとの違いのような、t* の模様と相関しない高域は 0 に近く数える）。"""
    F = np.asarray(F)
    rms = np.sqrt((F ** 2).mean(1))
    f0 = F[-1]
    proj = (F @ f0) / max(float(f0 @ f0), 1e-12)
    return rms, proj


def measure(package, t_start=-5.0, log=print):
    ks = DG.KStar()
    pk = DG.Package(package, ks)
    t0 = max(float(pk.knots[0]), t_start)
    K = int(np.floor(-t0 * HZ + 1e-6))
    taus = -np.arange(K, -1, -1) / HZ
    mr, pr = ks.main_row, ks.peak_row
    rows = ks.curled_idx
    C = claw_setup(ks)
    S = {k: np.full((len(taus), ks.nv), np.nan) for k in ("H", "Lo", "ca", "theta", "phi", "tipa", "tipy")}
    Fc, Fh = [], []
    tipc = np.where(ks.tip_col >= 0, ks.tip_col, 0)
    rr = np.arange(ks.nv)
    tt = time.time()
    for k, tau in enumerate(taus):
        Xl = pk.local(float(tau)) + ks.O
        A, Y, _ = ks.section(Xl)
        rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
        for key in ("H", "Lo", "ca", "theta", "phi"):
            S[key][k] = rm[key]
        S["tipa"][k] = A[rr, tipc]
        S["tipy"][k] = Y[rr, tipc]
        fc, fh = claw_fields(ks, A, Y, C, rm["ca"], rm["H"])
        Fc.append(fc)
        Fh.append(fh)
        if k % 60 == 0:
            log("  [q13] τ %.2f（%.0f s）" % (tau, time.time() - tt))
    cross_rms, cross = claw_series(Fc)
    hook_rms, hook = claw_series(Fh)
    S["claw_rms"] = (cross_rms, hook_rms)
    return ks, pk, taus, S, cross, hook


def t1_row(taus, H, Lo):
    Hf = float(H[-1])
    lo = Lo / np.maximum(H, 1e-9)
    ok = np.nan_to_num(lo, nan=0.0) >= TH["T1_Lo_start"]
    # t* まで満たし続ける最初の時刻
    if not ok[-1]:
        ke = None
    else:
        bad = np.nonzero(~ok)[0]
        ke = int(bad[-1] + 1) if len(bad) else 0
    res = dict(Hf_m=fnum(Hf, 3))
    if ke is None:
        res.update(ext_start_tau=None, pass_=False)
        return res
    te = float(taus[ke])
    He = float(H[ke])
    seg = H[ke:]
    dd = float((np.maximum.accumulate(seg) - seg).max())
    hi = H >= TH["T1_plateau_frac"] * Hf
    # t* の直前から遡って H ≥ 0.95 Hf が続く長さ（t* を含む連続区間）と、t* の前のどこかで続いた最長
    run = 0.0
    best = 0.0
    for k in range(len(taus)):
        run = run + (1.0 / HZ) if hi[k] else 0.0
        best = max(best, run)
    kmax = int(np.argmax(H))
    t_max = float(taus[kmax])
    c1 = He / Hf <= TH["T1_H_at_start_max"]
    c2 = (Hf - He) / Hf >= TH["T1_rise_after_start_min"]
    c3 = dd <= TH["T1_mono_m"]
    c4 = best <= TH["T1_plateau_s"]
    c5 = -t_max <= TH["T1_max_near_tstar_s"] + 1e-9
    # 読みの補助：Lo が 0.1H に届く時刻、そのときの H/Hf
    k10 = np.nonzero(np.nan_to_num(lo, nan=0.0) >= 0.1)[0]
    k10 = int(k10[0]) if len(k10) else None
    res.update(ext_start_tau=fnum(te, 3), H_at_start_over_Hf=fnum(He / Hf, 3), rise_after_start_over_Hf=fnum((Hf - He) / Hf, 3),
               H_drawdown_after_start_m=fnum(dd, 4), plateau_ge_0p95_longest_s=fnum(best, 3), H_max_tau=fnum(t_max, 3),
               Lo_0p1_tau=(fnum(float(taus[k10]), 3) if k10 is not None else None),
               H_at_Lo_0p1_over_Hf=(fnum(float(H[k10] / Hf), 3) if k10 is not None else None),
               checks=dict(H_at_start=bool(c1), rise_after_start=bool(c2), monotone=bool(c3), no_plateau=bool(c4), max_near_tstar=bool(c5)),
               pass_=bool(c1 and c2 and c3 and c4 and c5))
    return res


def ext_progress(ks, taus, S):
    rows = ks.curled_idx
    H = S["H"][:, rows]
    Lo = np.nan_to_num(S["Lo"][:, rows], nan=0.0)
    lo = Lo / np.maximum(H, 1e-9)
    lof = lo[-1]
    E = np.clip((lo - TH["T1_Lo_start"]) / np.maximum(lof - TH["T1_Lo_start"], 1e-6), 0.0, 1.0)
    return np.median(E, axis=1)


def tip_progress(ks, taus, S):
    """唇先の頂からの前への距離 (a_tip − a_頂) の進み：行の較正の噴流の始まり（ds26 の T_row）から t* まで 0〜1、行の中央値（記録）。"""
    cond, _ = DG.load_conditions()
    rows = ks.curled_idx
    pr = ks.peak_row
    out = []
    for r in rows:
        Tr = max(abs(cond["tau0"]) - abs(ks.c[r] - ks.c[pr]) / cond["peel"], cond["floor"])
        ta = S["tipa"][:, r] - S["ca"][:, r]
        t0v = float(np.interp(-Tr, taus, ta))
        out.append(np.clip((ta - t0v) / max(ta[-1] - t0v, 1e-6), 0.0, 1.0))
    return np.median(np.array(out), axis=0)


def first_ge(taus, v, x):
    k = np.nonzero(v >= x)[0]
    return fnum(float(taus[k[0]]), 3) if len(k) else None


def evaluate(ks, taus, S, cross, hook):
    mr, pr = ks.main_row, ks.peak_row
    out = dict(thresholds=TH)
    t1 = {}
    for r, nm in ((mr, "main"), (pr, "peak")):
        t1[nm] = t1_row(taus, S["H"][:, r], S["Lo"][:, r])
        t1[nm]["row"] = int(r)
    out["T1"] = dict(pass_=bool(t1["main"].get("pass_") and t1["peak"].get("pass_")), rows=t1)
    E = ext_progress(ks, taus, S)
    Cc = cross / max(cross[-1], 1e-9)
    Ch = hook / max(hook[-1], 1e-9)
    te = t1["peak"].get("ext_start_tau")
    te_main = t1["main"].get("ext_start_tau")
    t_from = min(v for v in (te, te_main) if v is not None) if (te is not None or te_main is not None) else -2.5
    m = taus >= t_from - 1e-9
    res2 = {}
    ok2 = True
    for nm, Cv in (("cross_row_claws", Cc), ("in_row_hooks", Ch)):
        seg = Cv[m]
        dd = float((np.maximum.accumulate(seg) - seg).max()) if len(seg) else None
        lag = float(np.max(np.abs(Cv[m] - E[m]))) if m.any() else None
        lag_behind = float(np.max(E[m] - Cv[m])) if m.any() else None
        c0_ = float(np.interp(t_from, taus, Cv))
        okk = (dd is not None and dd <= TH["T2_mono"] and lag_behind is not None and lag_behind <= TH["T2_lag"]
               and c0_ <= TH["T2_start_max"])
        rms_ = S["claw_rms"][0 if nm.startswith("cross") else 1]
        res2[nm] = dict(amp_tstar_rms_m=fnum(float(rms_[-1]), 4), rms_at_ext_start_m=fnum(float(np.interp(t_from, taus, rms_)), 4),
                        frac_at_ext_start=fnum(float(np.interp(t_from, taus, Cv)), 3), drawdown_after_start=fnum(dd, 4),
                        max_abs_C_minus_E=fnum(lag, 3), max_E_minus_C=fnum(lag_behind, 3), tau_C_0p5=first_ge(taus, Cv, 0.5),
                        tau_C_0p25=first_ge(taus, Cv, 0.25), tau_C_0p75=first_ge(taus, Cv, 0.75), pass_=bool(okk))
        ok2 &= okk
    Et = tip_progress(ks, taus, S)
    res2["ext_progress"] = dict(tau_E_0p25=first_ge(taus, E, 0.25), tau_E_0p5=first_ge(taus, E, 0.5), tau_E_0p75=first_ge(taus, E, 0.75),
                                from_tau=fnum(t_from, 3),
                                tip_ahead_record=dict(tau_0p25=first_ge(taus, Et, 0.25), tau_0p5=first_ge(taus, Et, 0.5), tau_0p75=first_ge(taus, Et, 0.75)))
    out["_Et"] = Et
    out["T2"] = dict(pass_=bool(ok2), detail=res2)
    return out, E, Cc, Ch


def run(package, out, log=print):
    t0 = time.time()
    ks, pk, taus, S, cross, hook = measure(package, log=log)
    res, E, Cc, Ch = evaluate(ks, taus, S, cross, hook)
    Et = res.pop("_Et")
    mr, pr = ks.main_row, ks.peak_row
    ser = dict(taus=[fnum(v, 4) for v in taus], E_median=[fnum(v, 4) for v in E], E_tip_median=[fnum(v, 4) for v in Et], claw_cross_frac=[fnum(v, 4) for v in Cc],
               hook_frac=[fnum(v, 4) for v in Ch], claw_cross_rms_m=[fnum(v, 4) for v in S["claw_rms"][0]], hook_rms_m=[fnum(v, 4) for v in S["claw_rms"][1]])
    for r, nm in ((mr, "main"), (pr, "peak")):
        for key in ("H", "Lo", "ca", "theta", "phi", "tipa", "tipy"):
            ser["%s_%s" % (key, nm)] = [fnum(v, 4) for v in S[key][:, r]]
    rep = dict(schema="GreatWave.DS28R01.q13/1", number="設計28修正01", tool=rel(os.path.abspath(__file__)), package=dict(dir=rel(pk.dir), pos_sha256=pk.pos_sha, layers=pk.L),
               readings_ja=[
                   "H：ds27_gates.row_metrics の本体の頂（巻きの行は K* の頂の列 jt より前の列を含まない）。Hf は t* の H。",
                   "伸び出しの始まり τ_e：Lo（定義 A）≥ 0.05H を満たし、その後 t* まで満たし続ける最初の時刻（60 Hz）。",
                   "頭打ち：H ≥ 0.95 Hf が続いた最長の時間（t* を含む）。",
                   "爪：行の間の爪は唇の前の部分（K* の唇先の 60 列前〜rim）の頂からの相対座標を波峰線方向に σ 1.0 m でならした値からのずれ、行の中の鉤は唇（K* の jt〜rim）を列の方向に 5 列のガウスでならした値からのずれ（端の 3 列を除く）。割合 C は t* の場への射影 <F(τ), F(0)>/|F(0)|²（t* の爪の模様がどれだけ出ているか）。RMS も記録。",
                   "伸び出しの進み E：巻きの行ごとに (Lo/H − 0.05)/(Lo/H(t*) − 0.05) を 0〜1 に切った値の行の中央値。",
               ], results=res, series=ser, runtime_s=round(time.time() - t0, 1))
    for g in (res["T1"], res["T2"]):
        g["pass"] = g.pop("pass_")
    for v in res["T1"]["rows"].values():
        v["pass"] = v.pop("pass_", None)
    for v in res["T2"]["detail"].values():
        if "pass_" in v:
            v["pass"] = v.pop("pass_")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=lambda o: fnum(o) if hasattr(o, "dtype") else str(o))
    log("[q13] T1 %s（主断面 %s・峰の行 %s）、T2 %s → %s（%.0f s）" % (
        res["T1"]["pass"], res["T1"]["rows"]["main"].get("ext_start_tau"), res["T1"]["rows"]["peak"].get("ext_start_tau"), res["T2"]["pass"], out, rep["runtime_s"]))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a.package, a.out)


if __name__ == "__main__":
    main()
