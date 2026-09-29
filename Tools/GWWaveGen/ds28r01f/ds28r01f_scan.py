# -*- coding: utf-8 -*-
"""設計28修正01 試行F：パッケージ（Unity の再生器と同じ Hermite、精度の層つき）を 60 Hz で走査する検査器（M1〜M3）。生成器のコードは読まない。

読むもの：パッケージのフォルダー（ds27_keypose.json・ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin）、K* のフォルダー（目印と t* の比べ）、
時間曲線（画面の時刻との対応）。関門の検査器 ds27_gates.py の Package・KStar・row_metrics・row_areas と、試行E の検査器の FinePackage を使う。
  M1 物理の時刻 τ −8〜0 の 60 Hz の全こま（481）：行ごとの断面の自己交差（全列、ds28r01f_selfx.section_selfx_rows ＝ gw_wavegen.self_intersections
     と同じ定義）と、網の局所の自己交差（ds28r01f_selfx.local_selfx ＝ gw_wavegen_v1.local_self_intersections と同じ定義）。t* の K*′ そのものに
     ある局所の自己交差の近く（±2 行・列）は「K*′ から受け継いだもの」として別に数える。
  M2 t* と K*′ の差（行の断面から作ったワールドと、.gwb の float32 と）。本体の水（行ごとの符号付きの断面積 × 行の間隔の和、設計27 の読み）
     と主断面の断面積の 60 Hz の時系列、最後の 2 s の跳び（1 こまの変化の最大と、それより前の最大との比）と、最後の 2 s の最小からの戻り。
     最後の 1 s の各頂点の軌跡（波の枠）：正味の変位 D = X(0) − X(−1) の向きの、行き過ぎて戻る量（overshoot）と、逆向きに動いた道のりの和（retro）。
  M3 行ごとの頂の角 θc（ds27_gates.row_metrics、E の検査器と同じ定義）：唇ができる前（Lo < 0.05H）で H ≥ 0.3 H(t*) のこまの最小（主断面・峰の行と、
     巻きのある全行）、画面の最後の 3 s（t 9〜12）の θc の時系列と、t* の値より下へ尖った量。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_scan.py --package <パッケージ> --kstar <K* のフォルダー> --out <json> [--warp <時間曲線>] [--workers 12]
"""
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GW, "..", ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d", "ds28r01e"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def r3(x, n=3):
    return None if x is None else round(float(x), n)


_W = {}


def _open(pkg, kdir):
    import ds28r01d_gates as DGW
    import ds28r01e_review as RE
    DG = DGW.DG
    d = DGW.patch_kstar(kdir)
    ks = DG.KStar(d)
    pk = RE.FinePackage(absrepo(pkg), ks, fine=True)
    return DG, ks, pk


def _winit(pkg, kdir):
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    DG, ks, pk = _open(pkg, kdir)
    _W.update(DG=DG, ks=ks, pk=pk)


def _frame(tau):
    import ds28r01f_selfx as SX
    DG, ks, pk = _W["DG"], _W["ks"], _W["pk"]
    X = np.asarray(pk.local(float(tau)), float)
    A = X @ ks.t
    Y = X[..., 1]
    rows = SX.section_selfx_rows(A, Y)
    loc = sorted(SX.local_selfx(X))
    an, ap = DG.row_areas(A, Y)
    rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
    jc = int(ks.j_corner)
    tr = [(float(-min(Y[r, jc:].min(), 0.0)), float(Y[r].max())) for r in _trough_rows(ks)]
    return dict(tau=float(tau), rows=rows, local=loc, A_net=an, A_pos=ap, theta=rm["theta"], Lo=rm["Lo"], H=rm["H"], trough=tr)


TROUGH_C = (-15.0, -7.5, 0.0, 3.85, 8.0)


def _trough_rows(ks):
    return [int(np.argmin(np.abs(ks.c - c))) for c in TROUGH_C]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--warp", default="Tools/GWWaveGen/ds28r01e/timewarp_default_E.json")
    ap.add_argument("--label", default="")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--hz", type=float, default=60.0)
    ap.add_argument("--tau-start", type=float, default=-8.0)
    a = ap.parse_args()
    t_all = time.time()
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    DG, ks, pk = _open(a.package, a.kstar)
    hz = a.hz
    n = int(round(-a.tau_start * hz))
    taus = [round(-(n - k) / hz, 9) for k in range(n + 1)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(a.workers, initializer=_winit, initargs=(a.package, a.kstar)) as pool:
        F = list(pool.imap(_frame, taus, chunksize=2))
    # ---------------- M1
    inh = set()
    for r, c in F[-1]["local"]:
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                inh.add((r + dr, c + dc))
    sec_frames = [f for f in F if f["rows"]]
    mo = [(f["tau"], [v for v in map(tuple, f["local"]) if v not in inh]) for f in F]
    mo_frames = [(t, v) for t, v in mo if v]
    inh_frames = [f for f in F if any(tuple(v) in inh for v in f["local"])]
    m1 = dict(hz=hz, frames=len(F), tau_range=[taus[0], taus[-1]],
              section_selfx_frames=len(sec_frames), section_selfx_rows=sorted({int(r) for f in sec_frames for r in f["rows"]}),
              section_selfx_max_rows_in_frame=max([len(f["rows"]) for f in F] + [0]),
              section_selfx_samples=[dict(tau=r3(f["tau"], 4), rows=sorted(int(r) for r in f["rows"])[:12]) for f in sec_frames[:20]],
              local_selfx_motion_frames=len(mo_frames), local_selfx_motion_vertices_max=max([len(v) for _, v in mo] + [0]),
              local_selfx_motion_rows=sorted({int(v[0]) for _, vs in mo_frames for v in vs}),
              local_selfx_motion_samples=[dict(tau=r3(t, 4), n=len(v), first=[list(x) for x in v[:4]]) for t, v in mo_frames[:20]],
              local_selfx_kstar_inherited_at_tstar=len(F[-1]["local"]),
              local_selfx_kstar_inherited_rows=sorted({int(v[0]) for v in F[-1]["local"]}),
              local_selfx_kstar_inherited_frames=len(inh_frames),
              verdict_ja=("断面の自己交差 0 こま・動きが作った局所の自己交差 0 こま" if not sec_frames and not mo_frames else "残りあり"))
    # ---------------- M2
    O0 = pk.origin(0.0)
    X0 = np.asarray(pk.local(0.0), float) + O0[None, None, :]
    XK = ks.O[None, None, :] + ks.c[:, None, None] * ks.e[None, None, :] + ks.A[..., None] * ks.t[None, None, :] + ks.Y[..., None] * np.array([0, 1.0, 0])
    tstar = dict(max_vs_kstar_rows_m=float(np.linalg.norm(X0 - XK, axis=-1).max()), max_vs_gwb_float32_m=float(np.linalg.norm(X0 - ks.X, axis=-1).max()),
                 threshold_m=0.001)
    dc = np.gradient(ks.c)
    V = np.array([float(np.sum(f["A_net"] * dc)) for f in F])
    Vp = np.array([float(np.sum(f["A_pos"] * dc)) for f in F])
    mr = int(ks.main_row)
    Am = np.array([float(f["A_net"][mr]) for f in F])
    tt = np.array(taus)
    dV = np.abs(np.diff(V))
    last2 = tt[1:] > -2.0 + 1e-9
    pre = (tt[1:] > -4.0) & ~last2
    k2 = int(np.searchsorted(tt, -2.0 - 1e-9))
    vol = dict(definition_ja="本体の水 V = Σ 行（符号付きの断面積 A_net × 行の間隔 Δc）（設計27 の読み。シートの上だけ）。A_pos は y > 0 の部分",
               V_m3={("%+.2f" % t): r3(v, 1) for t, v in zip(tt[::10], V[::10])},
               A_main_m2={("%+.2f" % t): r3(v, 2) for t, v in zip(tt[::10], Am[::10])},
               V_at=dict(**{("%+.1f" % t): r3(float(np.interp(t, tt, V)), 1) for t in (-4, -3, -2, -1.5, -1, -0.5, 0)}),
               last2s_max_frame_step_m3=r3(dV[last2].max(), 2), before_max_frame_step_m3=r3(dV[pre].max(), 2),
               last2s_step_ratio=r3(dV[last2].max() / max(dV[pre].max(), 1e-9), 3),
               last2s_min_m3=r3(V[k2:].min(), 1), last2s_min_tau=r3(tt[k2:][int(np.argmin(V[k2:]))], 3),
               refill_after_min_frac=r3((V[-1] - V[k2:].min()) / max(V[k2:].min(), 1e-9), 4),
               last2s_change_frac=r3((V[-1] - V[k2]) / max(V[k2], 1e-9), 4),
               A_main_last2s_min_m2=r3(Am[k2:].min(), 2), A_main_refill_after_min_frac=r3((Am[-1] - Am[k2:].min()) / max(Am[k2:].min(), 1e-9), 4),
               Vpos_at={("%+.1f" % t): r3(float(np.interp(t, tt, Vp)), 1) for t in (-3, -2, -1, 0)})
    # 最後の 1 s の軌跡
    k1 = int(np.searchsorted(tt, -1.0 - 1e-9))
    P = np.stack([np.asarray(pk.local(float(t)), float) for t in tt[k1:]])     # (m, nv, nu, 3) 波の枠
    D = P[-1] - P[0]
    Dn = np.linalg.norm(D, axis=-1)
    u = D / np.maximum(Dn, 1e-12)[..., None]
    proj = ((P - P[0][None]) * u[None]).sum(-1)                                # (m, nv, nu)
    over = proj.max(0) - Dn
    retro = np.maximum(-np.diff(proj, axis=0), 0.0).sum(0)
    mv = Dn > 0.01
    ko = int(np.argmax(np.where(mv, over, -1)))
    kr = int(np.argmax(np.where(mv, retro, -1)))
    back = dict(window_tau=[-1.0, 0.0], hz=hz, vertices_moving_gt_1cm=int(mv.sum()),
                overshoot_max_m=r3(over[mv].max(), 4), overshoot_p99_m=r3(np.percentile(over[mv], 99), 4), overshoot_gt_1cm=int((over[mv] > 0.01).sum()),
                overshoot_max_at=dict(row=ko // ks.nu, col=ko % ks.nu, net_m=r3(Dn.ravel()[ko], 3)),
                retro_max_m=r3(retro[mv].max(), 4), retro_p99_m=r3(np.percentile(retro[mv], 99), 4), retro_gt_1cm=int((retro[mv] > 0.01).sum()),
                retro_max_at=dict(row=kr // ks.nu, col=kr % ks.nu, net_m=r3(Dn.ravel()[kr], 3)),
                definition_ja="波の枠。D = X(0) − X(−1)。overshoot = max_τ (X(τ) − X(−1))·D̂ − |D|（行き過ぎて戻る量）、retro = Σ max(0, −Δ(X·D̂))（正味の向きと逆に動いた道のり）。|D| > 1 cm の頂点")
    m2 = dict(tstar=tstar, volume=vol, backtrack_last1s=back)
    # ---------------- M3
    W = json.load(open(absrepo(a.warp), encoding="utf-8"))
    wt, wtau = np.asarray(W["t"], float), np.asarray(W["tau"], float)
    th = np.stack([f["theta"] for f in F])          # (frames, nv)
    Lo = np.stack([f["Lo"] for f in F])
    H = np.stack([f["H"] for f in F])
    Hf = H[-1]
    rows_c = [int(r) for r in ks.curled_idx]
    rc = {"main": mr, "peak": int(ks.peak_row), "c+3.85": int(np.argmin(np.abs(ks.c - 3.85)))}
    per = {}
    allmin = (999.0, None, None)
    for r in sorted(set(rows_c) | set(rc.values())):
        lo = np.nan_to_num(Lo[:, r] / np.maximum(H[:, r], 1e-9), nan=0.0)
        lip = np.nonzero(lo >= 0.05)[0]
        k_l = int(lip[0]) if len(lip) else len(tt)
        m = (np.arange(len(tt)) < k_l) & (H[:, r] >= 0.3 * Hf[r]) & np.isfinite(th[:, r])
        if not m.any():
            continue
        v = float(np.nanmin(th[m, r]))
        tmin = float(tt[m][int(np.nanargmin(th[m, r]))])
        per[r] = (v, tmin, float(tt[k_l]) if k_l < len(tt) else None)
        if v < allmin[0]:
            allmin = (v, r, tmin)
    t_of = lambda tau: float(np.interp(tau, wtau, wt))       # noqa: E731
    ts_last3 = np.arange(9.0, 12.0 + 1e-9, 0.25)
    tau_last3 = np.interp(ts_last3, wt, wtau)
    named = {}
    for nm, r in rc.items():
        if r in per:
            v, tm, tl = per[r]
        else:
            v, tm, tl = None, None, None
        ser = {("%.2f" % t): r3(float(np.interp(tq, tt, th[:, r])), 1) for t, tq in zip(ts_last3, tau_last3)}
        thf = float(th[-1, r])
        k9 = int(np.searchsorted(tt, float(np.interp(9.0, wt, wtau))))
        named[nm] = dict(row=r, c_m=r3(ks.c[r], 2), theta_c_min_before_lip_deg=r3(v, 1), at_tau=r3(tm, 3), at_t=r3(t_of(tm), 3) if tm is not None else None,
                         lip_tau=r3(tl, 3), theta_c_tstar_deg=r3(thf, 1), last3s_theta_c_min_deg=r3(np.nanmin(th[k9:, r]), 1),
                         last3s_sharpen_below_tstar_deg=r3(max(0.0, thf - float(np.nanmin(th[k9:, r]))), 1), theta_c_last3s=ser)
    vals = np.array([v[0] for v in per.values()])
    # ---------------- 前の谷が高さとともに深くなる（E から保つもの）
    trs = {}
    TRr = _trough_rows(ks)
    for i, r in enumerate(TRr):
        D = np.array([f["trough"][i][0] for f in F])
        Hh = np.array([f["trough"][i][1] for f in F])
        sub = slice(None, None, 6)
        rk = lambda x: np.argsort(np.argsort(x))      # noqa: E731
        sp = float(np.corrcoef(rk(Hh[sub]), rk(D[sub]))[0, 1]) if D[sub].std() > 1e-9 else None
        trs[str(r)] = dict(c_m=r3(ks.c[r], 2), D_tstar_m=r3(D[-1]), H_tstar_m=r3(Hh[-1]), D_over_H_tstar=r3(D[-1] / max(Hh[-1], 1e-9)),
                           spearman_H_D_10hz=r3(sp), D_at={("%+.1f" % t): r3(float(np.interp(t, tt, D))) for t in (-6, -4, -3, -2, -1, 0)},
                           D_max_before_tstar_m=r3(D[:-1].max()), D_monotone_drop_max_m=r3(float(np.max(np.maximum.accumulate(D) - D))))
    trough = dict(definition_ja="前の谷の深さ D = 列 j_corner〜399（前面の下と前の縁）の最低点の y の負の値（K*′ は谷が列 j_E より前にある）、H = 行の最高点。"
                                "E の検査器（ds28r01d_review.trough）は列 j_E より前を見るので、K*′ の谷を 0 と読む（記録）", rows=trs)
    m3 = dict(definition_ja="θc = ds27_gates.row_metrics の頂の角（頂から 0.1H 下の前後の点への弦のなす角）。唇ができる前 = Lo（定義 A）< 0.05H、かつ H ≥ 0.3 H(t*)",
              rows=named, curled_rows=len(per), curled_rows_min_deg=r3(allmin[0], 1), curled_rows_min_at=dict(row=allmin[1], tau=r3(allmin[2], 3),
                                                                                                            c_m=r3(ks.c[allmin[1]], 2) if allmin[1] is not None else None),
              curled_rows_below_125=int((vals < 125).sum()), curled_rows_below_125_list=sorted(int(r) for r, v in per.items() if v[0] < 125)[:40],
              threshold_deg=125)
    out = dict(label=a.label, package=a.package, kstar=a.kstar, warp=a.warp, pos_sha256=pk.pos_sha, fine=bool(pk.fine), m1=m1, m2=m2, m3=m3, trough=trough,
               seconds=round(time.time() - t_all, 1), definitions_ja=__doc__)
    op = absrepo(a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else float(o))
    print(json.dumps(dict(m1=m1["verdict_ja"], sec=m1["section_selfx_frames"], loc=m1["local_selfx_motion_frames"], tstar=tstar,
                          refill=vol["refill_after_min_frac"], over=back["overshoot_max_m"], retro=back["retro_max_m"], m3=m3["curled_rows_min_deg"],
                          s=out["seconds"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
