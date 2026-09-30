# -*- coding: utf-8 -*-
"""設計28修正01 試行F：生成器（ds28r01f_model.py）から keypose パッケージを書き出す（試行E と同じ書式：設計27 の 3 ファイル ＋ 精度の層）。

E の生成（ds28r01e_generate.py、1 回 2,585 s）は 1 つのプロセスで、準備（num_no_rebound_after_apex の 120 Hz の格子）・節点の適応・検査を
順に行っていた。F は生成器を複数のプロセス（既定 14）に持たせ、評価を分けて行う（M5：≤ 30 分）。集める順は時刻の順なので、プロセスの
数によらず同じバイト（決定的。numpy は 1 スレッド）。

流れ：
  1. 各プロセスが生成器を作る（num_no_rebound_after_apex の格子は後で読む）。主のプロセスも 1 つ作る（書き出し・海の標本）。
  2. num_no_rebound_after_apex の格子（120 Hz、τ −3.9〜0、F の層の前）を分けて計算し、ファイルにして全部のプロセスで読む。
  3. num_bridge_tangles の走査（120 Hz、局所の自己交差は 60 Hz、τ −8〜0）：E のまま（F の層なし）と、num_tstar_exact・num_sheet_clearance
     を入れた形の両方で、断面の自己交差と網の局所の自己交差を数える。F で残った所（K*′ から受け継いだものを除く）を行ごとの区間にし、
     端の位置と速さ（±1/240 s の中心差分）を取って bridge.npz に書き、240 Hz で確かめる（残れば区間を広げる）。
  4. 節点（G27.Builder と同じ規則、評価だけ分ける）→ パッケージ（設計27 の書式 ＋ 精度の層。ds28r01e_generate.export_lo）→ 海の標本。
  5. 検査（G27.run_checks と同じ中身、評価だけ分ける）、F の層の大きさ（P20：層を 1 つずつ切った形との頂点の差の最大）。
使い方（リポジトリの根で。1 回 約 15〜25 分）：
    py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_generate.py --kstar <K*′ のフォルダー> --name F_R2/art_on
        [--out Unity/Build/Design/28R01F] [--workers 14] [--overrides <json>] [--off bridge,...] [--no-check] [--no-sea]
出力：<out>/<name>/：ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin・ds27_keypose.json・ds27_twhite_r32f.bin（決定的）、ds27_sea.npz、
      ds27_checks.json、ds28r01f_generate_log.json（時間・走査・P20）、_work/（nr_cache.npz・bridge.npz・scan_prebridge.json）。
"""
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"   # 行列積の和の順を固定し、同じバイトを保つ（子のプロセスにも渡る）
os.environ["OMP_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import datetime  # noqa: E402
import functools  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c", "ds28r01d", "ds28r01e"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

F_FILES = ["ds28r01f_model.py", "ds28r01f_generate.py", "ds28r01f_params.json", "ds28r01f_clearance.py", "ds28r01f_selfx.py"]
LO_NAME = "ds27_pos_lo_rgba8.bin"

# ================================================================ 子のプロセス
_G = None
_STAGE = {}


def _winit(kdir, overrides, off):
    global _G
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    import ds28r01f_model as MF
    _G = MF.Generator(kstar_dir=kdir, f_overrides=overrides or None, off=off, defer_no_rebound=True)


def _ensure(stage):
    """stage = dict(nr=格子のファイル, bridge=橋渡しのファイル or None, gw=窓のファイル or None, raw=(A, Y, taus) の npy or None,
    layers=dict or None)。"""
    g = _G
    dl = tuple(stage.get("delip") or ())
    if dl != _STAGE.get("delip", ()):
        g.apply_delip(dl)
        _STAGE["delip"] = dl
    nrp = stage.get("nr")
    if nrp and nrp != _STAGE.get("nr_loaded"):
        g.load_no_rebound(nrp)
        _STAGE["nr_loaded"] = nrp
    w = stage.get("gw")
    if w != _STAGE.get("gw"):
        g.set_guard_window(w)
        _STAGE["gw"] = w
    rw = stage.get("raw")
    if rw and _STAGE.get("raw_paths") != rw:
        _STAGE["raw"] = (np.load(rw[0], mmap_mode="r"), np.load(rw[1], mmap_mode="r"), np.load(rw[2]))
        _STAGE["raw_paths"] = rw
    b = stage.get("bridge")
    if b != _STAGE.get("bridge"):
        if b:
            g.set_bridge(b)
        else:
            g._bridge = None
            g._bridge_sha = None
        _STAGE["bridge"] = b
    if stage.get("layers") is not None:
        g.set_layers(**{k: v for k, v in stage["layers"].items()})
    else:
        g.set_layers(**g.f_on)


def _t_nr(tau):
    return _G.nr_grid_row(tau)


def _t_nr2(args):
    """num_no_rebound_after_apex の格子の 1 こま（small_lip_body の差し替えの後で作り直す。読み込んだ格子は外して計算）。"""
    tau, stage = args
    _ensure(dict(stage, nr=None))
    g = _G
    ready = g._nr_ready
    g._nr_ready = False
    try:
        return g.nr_grid_row(tau)
    finally:
        g._nr_ready = ready


def _t_knot(args):
    tau, stage = args
    _ensure(stage)
    X, A, Y, d = _G.local(float(tau), info=True)
    return X, np.asarray(d["Ac"], float).copy()


def _t_x(args):
    tau, stage = args
    _ensure(stage)
    return _G.local(float(tau))


def _t_xay(args):
    tau, stage = args
    _ensure(stage)
    X, A, Y, d = _G.local(float(tau), info=True)
    return X, A, Y


def _t_scan(args):
    """走査の 1 こま：E のまま（F の層なし）と F（橋渡しの前、または stage の層）の、断面の自己交差の行と網の局所の自己交差。"""
    tau, stage, do_local, do_raw_local = args
    import ds28r01f_selfx as SX
    _ensure(stage)
    g = _G
    t = float(min(tau, 0.0))
    f = g._f_ready
    g._f_ready = False
    try:
        A0, Y0, _ = g.section_y(t)
    finally:
        g._f_ready = f
    raw_rows = SX.section_selfx_rows(A0, Y0)
    L = dict(g.f_layers)
    A1, Y1 = g.f_apply(t, A0, Y0, L)
    sc = dict(g._sc_last)
    rows = {r: SX.section_hits_row(A1[r], Y1[r]) for r in SX.section_selfx_rows(A1, Y1)}
    out = dict(tau=tau, raw_rows=raw_rows, rows=rows, sc_max_push_m=sc["max_push_m"], sc_rows=sc["rows"])
    if do_local:
        out["local"] = sorted(SX.local_selfx(g.to_local(A1, Y1)))
    if do_raw_local:
        out["raw_local"] = sorted(SX.local_selfx(g.to_local(A0, Y0)))
    return out


def _t_pass1(args):
    """走査の 1 回目（E のまま、F の層なし）：断面 (A, Y) と、断面の自己交差の行、網の局所の自己交差（do_local の時）。"""
    tau, stage, do_local = args
    import ds28r01f_selfx as SX
    _ensure(stage)
    g = _G
    f = g._f_ready
    g._f_ready = False
    try:
        A, Y, _ = g.section_y(float(min(tau, 0.0)))
    finally:
        g._f_ready = f
    out = dict(tau=tau, rows=SX.section_selfx_rows(A, Y))
    if do_local:
        out["local"] = sorted(SX.local_selfx(g.to_local(A, Y)))
    return out, A, Y


def _t_pass2(args):
    """走査の 2 回目：1 回目の断面（ファイル）に F の層（stage の layers）を掛けて、断面の自己交差の行と網の局所の自己交差。"""
    k, stage, do_local = args
    import ds28r01f_selfx as SX
    _ensure(stage)
    g = _G
    Araw, Yraw, taus = _STAGE["raw"]
    tau = float(taus[k])
    A, Y = g.f_apply(tau, np.array(Araw[k], float), np.array(Yraw[k], float), dict(g.f_layers))
    sc = dict(g._sc_last)
    out = dict(tau=tau, rows=SX.section_selfx_rows(A, Y), sc_max_push_m=sc["max_push_m"], sc_rows=sc["rows"])
    if do_local:
        out["local"] = sorted(SX.local_selfx(g.to_local(A, Y)))
    return out


def _t_gridstate(args):
    """1 回目の断面のこま k に F の層を掛けた、指定の行の (A, Y)。"""
    k, stage, rows = args
    _ensure(stage)
    g = _G
    Araw, Yraw, taus = _STAGE["raw"]
    A, Y = g.f_apply(float(taus[k]), np.array(Araw[k], float), np.array(Yraw[k], float), dict(g.f_layers))
    r = np.asarray(rows, int)
    return A[r].copy(), Y[r].copy()


def _t_rowstate(args):
    tau, stage, rows = args
    _ensure(stage)
    A, Y, _ = _G.section_y(float(min(tau, 0.0)))
    r = np.asarray(rows, int)
    return A[r].copy(), Y[r].copy()


def _t_p20(args):
    """F の層ごとの大きさ：全部を入れた形と、その層だけを切った形の頂点の差（局所座標）の最大と場所。E のまま（全部を切った形）との差も。"""
    tau, stage = args
    _ensure(stage)
    g = _G
    t = float(min(tau, 0.0))
    f = g._f_ready
    g._f_ready = False
    try:
        A0, Y0, _ = g.section_y(t)
    finally:
        g._f_ready = f
    on = dict(g.f_layers)
    Xon = g.to_local(*g.f_apply(t, A0, Y0, on))
    out = {}
    k0s = dict(getattr(g, "_tail_kappa0", {}))
    k0s.update(getattr(g, "_delip_kappa0", {}))
    if k0s:
        # tail_lip_body・small_lip_body：唇の強さを E の値へ戻した形（F の層なし）と、κ = 0 の形（F の層なし）の差（格子は同じ）
        X0 = g.to_local(A0, Y0)
        for r, kv in k0s.items():
            g.kappa[r] = kv
        g._f_ready = False
        try:
            A1, Y1, _ = g.section_y(t)
        finally:
            g._f_ready = f
            for r in k0s:
                g.kappa[r] = 0.0
        d = np.linalg.norm(X0 - g.to_local(A1, Y1), axis=-1)
        k = int(np.argmax(d))
        out["lip_body"] = (float(d.max()), int(k // d.shape[1]), int(k % d.shape[1]))
    if on.get("back_no_undercut", False) or "back_no_undercut" in g.f_on and g.f_on["back_no_undercut"]:
        # ds_back_no_undercut：_back の差し替えの δ < 0 の重みの広げ方だけを切った形（F の層なし）との差。水の釣り合いの山 ΔL の当てはめ
        # （__init__ の中）は入れた版のまま（近似。記録）
        X0 = g.to_local(A0, Y0)
        g.f_off = tuple(g.f_off) + ("back_no_undercut",)
        g._f_ready = False
        try:
            A1, Y1, _ = g.section_y(t)
        finally:
            g._f_ready = f
            g.f_off = tuple(x for x in g.f_off if x != "back_no_undercut")
        d = np.linalg.norm(X0 - g.to_local(A1, Y1), axis=-1)
        k = int(np.argmax(d))
        out["back_no_undercut"] = (float(d.max()), int(k // d.shape[1]), int(k % d.shape[1]))
    if getattr(g, "_bal_ks_on", False):
        # num_balance_swell_calm（仕上げ27）：海の釣り合いの κ_s だけを切った形（F の層なし）との差。F の層（f_apply）ではなく海の中の値なので、ここで測る
        X0 = g.to_local(A0, Y0)
        g._bal_ks_on = False
        g._f_ready = False
        try:
            A1, Y1, _ = g.section_y(t)
        finally:
            g._f_ready = f
            g._bal_ks_on = True
        d = np.linalg.norm(X0 - g.to_local(A1, Y1), axis=-1)
        k = int(np.argmax(d))
        out["balance_swell_calm"] = (float(d.max()), int(k // d.shape[1]), int(k % d.shape[1]))
    for nm in list(on) + ["all"]:
        if nm in ("tail_lip_body", "small_lip_body", "back_no_undercut", "back_width_retarget", "anchor_retarget", "far_hook_early",
                  "balance_swell_calm", "sea_sample_range") or (nm != "all" and not on[nm]):
            continue
        L = {k: (False if (nm == "all" or k == nm) else v) for k, v in on.items()}
        Xo = g.to_local(*g.f_apply(t, A0, Y0, L))
        d = np.linalg.norm(Xon - Xo, axis=-1)
        k = int(np.argmax(d))
        out[nm] = (float(d.max()), int(k // d.shape[1]), int(k % d.shape[1]))
    return tau, out


# ================================================================ 主のプロセス
def export_sea_range(g, B, outdir, a_min, a_max, step=1.0, hz=10.0):
    """num_sea_sample_range（仕上げ27）：設計27 の export_sea（ds27_generate.py。地面の a −330〜130 m）と同じ中身・同じ式・同じ書式で、
    a の範囲だけを a_min〜a_max にする（関門 P2・P3 の 225 m の窓が、τ −12 s の頂の後ろでも標本に収まるように）。"""
    a = np.arange(a_min, a_max + 1e-9, step)
    kn = B.knots
    Ak = np.stack([B.Ac[round(float(t), 9)] for t in kn])            # (L, nv)
    n = int(np.floor(-kn[0] * hz + 1e-9))
    ts = np.array([-(n - k) / hz for k in range(n + 1)])
    eta = np.zeros((len(ts), g.K.nv, len(a)), np.float32)
    Ac = np.zeros((len(ts), g.K.nv), np.float32)
    for k, t in enumerate(ts):
        ac = np.array([np.interp(t, kn, Ak[:, r]) for r in range(g.K.nv)])
        Ac[k] = ac
        eta[k] = g.sea_outside(float(t), ac, a).astype(np.float32)
    p = os.path.join(outdir, "ds27_sea.npz")
    np.savez(p, tau=ts, a=a, eta=eta, Ac=Ac, c=g.K.c, knot_tau=kn, Ac_knots=Ak.astype(np.float32))
    return p


def rel(p):
    try:
        return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")
    except ValueError:
        return p


class PBuilder:
    """G27.Builder と同じ規則の節点の適応（評価だけ子のプロセスへ分ける）。knots・Xk・Ac・rounds・n_eval・herm は同じ。"""

    def __init__(self, g, pool, stage, log):
        import ds27_generate as G27
        self.G27 = G27
        self.g = g
        self.pool = pool
        self.stage = stage
        self.log = log
        self.cache = {}
        self.Ac = {}
        self.n_eval = 0

    def herm(self, tau, knots, Xk):
        return self.G27.Builder.herm(self, tau, knots, Xk)

    def _fill(self, taus):
        need = [t for t in taus if t not in self.cache]
        for t, (X, Ac) in zip(need, self.pool.imap(_t_knot, [(t, self.stage) for t in need], chunksize=2)):
            self.cache[t] = X
            self.Ac[t] = Ac
            self.n_eval += 1

    def build_knots(self):
        P = self.g.P["knots"]
        tmin = self.g.tau_min
        a = np.arange(tmin, P["coarse_until_tau_s"] - 1e-9, P["coarse_step_s"])
        nfine = int(round(-P["coarse_until_tau_s"] / P["fine_step_s"]))
        b = np.linspace(P["coarse_until_tau_s"], 0.0, nfine + 1)
        knots = sorted(set(np.round(np.concatenate([a, b]), 9).tolist()))
        tol = float(P["adaptive_tol_m"])
        m = int(P["adaptive_check_per_interval"])
        rounds = []
        to_check = set(range(len(knots) - 1))
        for rnd in range(int(P["adaptive_max_rounds"])):
            t0 = time.time()
            self._fill(knots)
            kn = np.array(knots)
            Xk = [self.cache[t] for t in knots]
            jobs = []
            for i in sorted(to_check):
                lo, hi = kn[i], kn[i + 1]
                for j in range(1, m + 1):
                    jobs.append((i, lo + (hi - lo) * j / (m + 1)))
            emax = {}
            for (i, t), Xg in zip(jobs, self.pool.imap(_t_x, [(t, self.stage) for _, t in jobs], chunksize=4)):
                self.n_eval += 1
                e = float(np.linalg.norm(self.herm(t, kn, Xk) - Xg, axis=-1).max())
                emax[i] = max(emax.get(i, 0.0), e)
            add = [round(0.5 * (kn[i] + kn[i + 1]), 9) for i in sorted(emax) if emax[i] > tol]
            worst = max(emax.values()) if emax else 0.0
            rounds.append(dict(round=rnd, knots=len(knots), intervals_checked=len(to_check), worst_err_m=worst, added=len(add),
                               seconds=round(time.time() - t0, 1)))
            self.log("  節点 %d 回目：%d 層、%d 区間を検査、差の最大 %.2f mm、追加 %d（%.0f s）" % (rnd, len(knots), len(to_check), worst * 1000, len(add),
                                                                           time.time() - t0))
            if not add:
                break
            knots = sorted(set(knots) | set(add))
            idx = [knots.index(t) for t in add]
            to_check = set()
            for k in idx:
                for i in range(k - 2, k + 2):
                    if 0 <= i < len(knots) - 1:
                        to_check.add(i)
        self._fill(knots)
        self.knots = np.array(knots)
        self.Xk = np.stack([self.cache[t] for t in knots])
        self.Ac = {t: self.Ac[t] for t in knots}
        self.rounds = rounds
        self.cache = {}
        return self.knots


def run_checks_parallel(g, B, deq, log, pool, stage, hz=30.0, si_every=2):
    """G27.run_checks と同じ中身（評価だけ子のプロセス。MeshStats は主のプロセスで順に）。"""
    import ds27_generate as G27
    from ds27_checks import MeshStats
    kn = B.knots
    n = int(np.floor(-g.tau_min * hz + 1e-9))
    taus = [round(-(n - k) / hz, 9) for k in range(n + 1)]
    MS = MeshStats(g, hz)
    herr = []
    stage_m = {"main": [], "peak": []}
    rows_st = {"main": g.K.main_row, "peak": int(np.argmin(np.abs(g.K.c - g.c_pk_on)))}
    t0 = time.time()
    for i, (t, (X, A, Y)) in enumerate(zip(taus, pool.imap(_t_xay, [(t, stage) for t in taus], chunksize=2))):
        MS.add(t, X, A, Y, si=(i % si_every == 0))
        if i % 15 == 0 or i == len(taus) - 1:
            MS.normals_check(X)
        e = np.linalg.norm(B.herm(t, kn, deq) - X, axis=-1)
        herr.append((t, float(e.max()), float(np.percentile(e, 99))))
        for key, r in rows_st.items():
            mm = G27.stage_metrics(A, Y, r)
            mm["tau"] = t
            mm["H_over_Hr"] = mm["H"] / g.H[r]
            stage_m[key].append(mm)
    mid = []
    tm = [0.5 * (kn[i] + kn[i + 1]) for i in range(len(kn) - 1)]
    for t, X in zip(tm, pool.imap(_t_x, [(t, stage) for t in tm], chunksize=4)):
        e = np.linalg.norm(B.herm(t, kn, deq) - X, axis=-1)
        mid.append((t, float(e.max()), float(np.percentile(e, 99))))
    log("  検査：%d コマ（30 Hz）＋ 中点 %d（%.0f s）" % (len(taus), len(mid), time.time() - t0))
    allh = herr + mid
    worst = max(allh, key=lambda x: x[1])
    res = MS.result()
    Xw0 = deq[-1] + g.origin(0.0)[None, None, :]
    dK = np.linalg.norm(Xw0 - g.K.X, axis=-1)
    dKg = np.linalg.norm(Xw0 - g.K.Xgwb, axis=-1)
    fnum = G27.fnum
    res_st = {}
    for key, S in stage_m.items():
        tt = np.array([s["tau"] for s in S])

        def first(cond):
            k = np.nonzero(cond)[0]
            return fnum(tt[k[0]], 3) if len(k) else None
        Hh = np.array([s.get("H_over_Hr", 0) for s in S])
        thc = np.array([s.get("theta_c", 180) for s in S])
        phi = np.array([s.get("phi", 0) for s in S])
        phib = np.array([s.get("phi_band", 0) for s in S])
        Lo = np.array([s.get("Lo_over_H", 0) for s in S])
        dH = np.gradient(Hh, tt)
        res_st[key] = dict(row=rows_st[key], c_m=fnum(g.K.c[rows_st[key]], 2),
                           a_first_tau=first((Hh >= 0.5) & (thc >= 140) & (phi <= 35) & (Lo <= 1e-3)),
                           b_first_tau=first((phi >= 45) & (thc <= 130) & (Hh >= 0.65) & (Lo <= 1e-3)),
                           c_first_tau=first((phib >= 90) & (Hh >= 0.8) & (Lo < 0.05)),
                           d_first_tau=first((Lo >= 0.1) & (Hh >= 0.9) & (dH > 0)),
                           series_every_0p1s=[dict(tau=fnum(s["tau"], 3), H_over_Hr=fnum(s.get("H_over_Hr"), 3), theta_c=fnum(s.get("theta_c"), 1),
                                                   phi=fnum(s.get("phi"), 1), phi_band=fnum(s.get("phi_band"), 1), Lo_over_H=fnum(s.get("Lo_over_H"), 3))
                                              for s in S[::3]])
    return dict(hz=hz, frames=len(taus), tau_range=[taus[0], taus[-1]],
                hermite_playback_err_m=dict(max=worst[1], max_at_tau=fnum(worst[0], 4), p99_of_frame_p99=fnum(np.percentile([h[2] for h in allh], 99), 6),
                                            max_30hz=max(h[1] for h in herr), max_midpoints=max(h[1] for h in mid),
                                            note_ja="量子化した節点の Hermite と解析の生成器の差（全頂点の最大）。30 Hz のコマと節点の間の中点"),
                tstar_vs_kstar_world_max_m=float(dK.max()), tstar_vs_kstar_gwb_float32_max_m=float(dKg.max()),
                mesh_and_continuity=res, stage_estimate=res_st)


def inherited_set(local0, pad=2):
    """K*′（t*）そのものの網の局所の自己交差の頂点の近く（±pad 行・列）。動きが作ったものと分けるため。"""
    s = set()
    for r, c in local0:
        for dr in range(-pad, pad + 1):
            for dc in range(-pad, pad + 1):
                s.add((r + dr, c + dc))
    return s


def intervals_from_flags(times, merge_gap, margin, t_lo, t_hi):
    """フラグの立った時刻の並びから、近いものをつないだ区間（前後に margin）。"""
    if not times:
        return []
    ts = sorted(times)
    out = [[ts[0], ts[0]]]
    for t in ts[1:]:
        if t - out[-1][1] <= merge_gap + 1e-9:
            out[-1][1] = t
        else:
            out.append([t, t])
    res = []
    for a, b in out:
        a2, b2 = max(a - margin, t_lo), min(b + margin, t_hi)
        if res and a2 <= res[-1][1] + 1e-9:
            res[-1][1] = max(res[-1][1], b2)
        else:
            res.append([a2, b2])
    return res


def make_bridge(pool, stage, row_ivs, taus, path, log):
    """行ごとの区間（120 Hz の格子の番号 [k0, k1]）の端の位置と速さ（中心差分、t* の端は片側）を、1 回目の断面に F の層を掛けて取り、
    bridge.npz に書く。"""
    h = float(taus[1] - taus[0])
    n = len(taus) - 1
    need = {}
    for r, ivs in row_ivs.items():
        for k0, k1 in ivs:
            for k in (k0 - 1, k0, k0 + 1, k1 - 1, k1, k1 + 1):
                if 0 <= k <= n:
                    need.setdefault(k, set()).add(r)
    ks = sorted(need)
    st = {}
    for k, (A, Y) in zip(ks, pool.imap(_t_gridstate, [(k, stage, sorted(need[k])) for k in ks], chunksize=1)):
        for j, r in enumerate(sorted(need[k])):
            st[(k, r)] = (A[j], Y[j])
    rec = {x: [] for x in ("rows", "t0", "t1", "A0", "Y0", "VA0", "VY0", "A1", "Y1", "VA1", "VY1")}
    for r in sorted(row_ivs):
        for k0, k1 in row_ivs[r]:
            def pv(k):
                P = st[(k, r)]
                if k + 1 <= n:
                    Pp, Pm = st[(k + 1, r)], st[(k - 1, r)]
                    V = ((Pp[0] - Pm[0]) / (2 * h), (Pp[1] - Pm[1]) / (2 * h))
                else:
                    Pm = st[(k - 1, r)]
                    V = ((P[0] - Pm[0]) / h, (P[1] - Pm[1]) / h)
                return P, V
            (Pa, Va), (Pb, Vb) = pv(k0), pv(k1)
            for key, v in (("rows", r), ("t0", float(taus[k0])), ("t1", float(taus[k1])), ("A0", Pa[0]), ("Y0", Pa[1]), ("VA0", Va[0]), ("VY0", Va[1]),
                           ("A1", Pb[0]), ("Y1", Pb[1]), ("VA1", Vb[0]), ("VY1", Vb[1])):
                rec[key].append(v)
    np.savez(path, **{k: np.array(v) for k, v in rec.items()})
    log("  橋渡しの区間：%d 行、%d 区間 → %s" % (len(row_ivs), len(rec["rows"]), rel(path)))


def group_windows(flags, n, merge, margin, pad, nv, lo=1):
    """橋渡しの区間：フラグの行を ±pad の行へ広げ、つながった行の組（行の差 ≤ 1）ごとに、組の中の区間を合わせて同じ区間にする
    （隣の行が違う動きをして網の局所の自己交差を作らないように）。戻り {行: [[k0, k1], ...]}。"""
    fl2 = {}
    for r, ks in flags.items():
        for dr in range(-pad, pad + 1):
            if 0 <= r + dr < nv:
                fl2.setdefault(r + dr, set()).update(ks)
    w = row_windows(fl2, n, merge, margin, lo=lo)
    rows = sorted(w)
    groups = []
    for r in rows:
        if groups and r - groups[-1][-1] <= 1:
            groups[-1].append(r)
        else:
            groups.append([r])
    out = {}
    for gr in groups:
        ivs = sorted(iv for r in gr for iv in w[r])
        merged = []
        for iv in ivs:
            if merged and iv[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], iv[1])
            else:
                merged.append(list(iv))
        for r in gr:
            out[r] = [list(iv) for iv in merged]
    return out


def row_windows(flags, n, merge, margin, lo=1):
    """行ごとのフラグの格子の番号の集合 → 区間 [k0, k1] のリスト（近いものをつなぎ、前後に margin こま。k0 ≥ lo、k1 ≤ n）。"""
    out = {}
    for r, ks in flags.items():
        ks = sorted(ks)
        iv = [[ks[0], ks[0]]]
        for k in ks[1:]:
            if k - iv[-1][1] <= merge:
                iv[-1][1] = k
            else:
                iv.append([k, k])
        res = []
        for a_, b_ in iv:
            a2, b2 = max(a_ - margin, lo), min(b_ + margin, n)
            if res and a2 <= res[-1][1]:
                res[-1][1] = max(res[-1][1], b2)
            else:
                res.append([a2, b2])
        out[r] = res
    return out


def code_sha(MD):
    import ds28r01e_generate as GE
    out = GE.code_sha()
    for f in F_FILES:
        out["ds28r01f/%s" % f] = MD.sha256_file(os.path.join(HERE, f))
    return out


def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--name", default="F/art_on")
    ap.add_argument("--out", default="Unity/Build/Design/28R01F")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--overrides", default="", help="ds28r01f_params.json への上書き（JSON。記録に残る）")
    ap.add_argument("--off", default="", help="切る名前（F の層・E・D の名前。, 区切り）")
    ap.add_argument("--keep-raw", action="store_true", help="走査の 1 回目の断面のファイル（_work/raw_A.npy・raw_Y.npy）を残す")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    a = ap.parse_args()
    t_all = time.time()
    import ds28r01f_proc
    thr = ds28r01f_proc.opt_out()
    import ds27_generate as G27
    import ds27_model as MD
    import ds28_generate as G28
    import ds28r01d_generate as GD
    import ds28r01e_generate as GE
    import ds28r01f_model as MF
    import ds28r01f_selfx as SX
    REPO = MF.REPO
    logs = []
    timing = {}

    def log(s):
        print(s, flush=True)
        logs.append(s)

    def lap(k, t0):
        timing[k] = round(time.time() - t0, 1)
    ov = json.loads(a.overrides) if a.overrides else None
    off = [s for s in a.off.split(",") if s]
    RF = MD.load_json(MF.PARAMS_F)
    if ov:
        MF.M8.deep_merge(RF, ov)
    nw = a.workers or int(RF["parallel"]["workers"])
    kdir = a.kstar if os.path.isabs(a.kstar) else os.path.join(REPO, a.kstar)
    outd = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    outdir = os.path.join(outd, a.name)
    work = os.path.join(outdir, "_work")
    os.makedirs(work, exist_ok=True)
    log("設計28修正01 試行F 生成：K*′ %s、上書き %s、切り %s、プロセス %d → %s（電力の抑制を切る：%s）" % (rel(kdir), ov or "なし", off or "なし", nw, rel(outdir), thr))
    ctx = mp.get_context("spawn")
    t0 = time.time()
    pool = ctx.Pool(nw, initializer=_winit, initargs=(kdir, ov, off))
    g = MF.Generator(kstar_dir=kdir, f_overrides=ov, off=off, defer_no_rebound=True, log=None)
    lap("build_main", t0)
    log("主のプロセスの生成器 %.0f s（%s）" % (time.time() - t0, g.variant))
    # ---- 2. num_no_rebound_after_apex の格子
    t0 = time.time()
    nr_path = os.path.join(work, "nr_cache.npz")
    if g.d_on.get("no_rebound", False) or g._nr_deferred:
        taus = g.nr_grid_taus()
        Yg = np.stack(list(pool.imap(_t_nr, [float(t) for t in taus], chunksize=4)))
        np.savez(nr_path, Y=Yg.astype(np.float64), taus=taus)
        g.enable_no_rebound(nr_path)
        stage = dict(nr=nr_path, bridge=None, layers=None)
    else:
        stage = dict(nr=None, bridge=None, layers=None)
    lap("no_rebound_grid", t0)
    log("num_no_rebound_after_apex の格子 %.0f s（%s）" % (time.time() - t0, g._nr_stats if hasattr(g, "_nr_stats") else "切り"))
    G27.stage_metrics = functools.partial(G27.stage_metrics, jE=int(g.jE))
    # ---- 3. 走査と窓と橋渡し
    BR = RF["bridge"]
    GWp = RF["sheet_clearance"]
    scan_rec = {}
    bridge_path = None
    hz = float(BR["scan_hz"])
    lstep = int(round(hz / float(BR["scan_local_hz"])))
    n = int(round(-float(BR["scan_tau_start"]) * hz))
    taus = np.array([round(-(n - k) / hz, 9) for k in range(n + 1)])
    t0 = time.time()
    pA = os.path.join(work, "raw_A.npy")
    pY = os.path.join(work, "raw_Y.npy")
    pT = os.path.join(work, "raw_taus.npy")
    RA = np.lib.format.open_memmap(pA, mode="w+", dtype=np.float64, shape=(n + 1, g.K.nv, g.K.nu))
    RY = np.lib.format.open_memmap(pY, mode="w+", dtype=np.float64, shape=(n + 1, g.K.nv, g.K.nu))
    np.save(pT, taus)
    def pass1(stage_):
        st1 = dict(stage_, layers=dict(tstar_exact=False, sheet_clearance=False, bridge=False))
        out = []
        for k, (o, A_, Y_) in enumerate(pool.imap(_t_pass1, [(float(t), st1, (k % lstep == 0) or k == n) for k, t in enumerate(taus)], chunksize=2)):
            RA[k] = A_
            RY[k] = Y_
            out.append(o)
        return out
    res1 = pass1(stage)
    lap("scan_pass1", t0)
    # ---- small_lip_body：K*′ の高さが row_min_H（8 m）に届かない唇の行で、E のままの断面が自己交差する行 ±pad の唇の強さを 0 にし、
    # num_no_rebound_after_apex の格子を作り直して 1 回目をやり直す
    SL = RF["small_lip_body"]
    HK = g.K.Y_full.max(1)
    small = sorted({int(r) for o in res1 for r in o["rows"] if HK[int(r)] < float(RF["sheet_clearance"]["row_min_H_m"]) and int(r) in g.lip
                    and float(g.kappa[int(r)]) > 0.0})
    scan_rec["small_lip_body"] = dict(flagged_rows=small)
    if g.f_on["small_lip_body"] and small:
        t1 = time.time()
        pad = int(SL["row_pad"])
        dl = sorted({r + dr for r in small for dr in range(-pad, pad + 1) if (r + dr) in g.lip and float(g.kappa[r + dr]) > 0.0})
        g.apply_delip(dl)
        stage = dict(stage, delip=tuple(dl))
        nr2 = os.path.join(work, "nr_cache_small_lip.npz")
        ntaus = g.nr_grid_taus()
        Yg = np.stack(list(pool.imap(_t_nr2, [(float(t), stage) for t in ntaus], chunksize=4)))
        np.savez(nr2, Y=Yg.astype(np.float64), taus=ntaus)
        g.load_no_rebound(nr2)
        stage = dict(stage, nr=nr2)
        res1 = pass1(stage)
        scan_rec["small_lip_body"].update(rows=dl, kappa0={str(r): round(v, 4) for r, v in g._delip_kappa0.items()}, seconds=round(time.time() - t1, 1))
        log("small_lip_body：行 %s の唇の強さを 0 に（F のこまごとの層の前で断面が自己交差した小さい行 %s ±%d）、格子を作り直して 1 回目をやり直した（%.0f s）" % (
            dl, small, pad, time.time() - t1))
        lap("small_lip_body", t1)
    RA.flush()
    RY.flush()
    del RA, RY
    inh = inherited_set(res1[-1].get("local", []))
    raw_sec = [(k, o) for k, o in enumerate(res1) if o["rows"]]
    raw_loc = [(k, [v for v in map(tuple, o["local"]) if v not in inh]) for k, o in enumerate(res1) if "local" in o]
    raw_loc = [(k, v) for k, v in raw_loc if v]
    scan_rec["e_raw"] = dict(hz=hz, local_hz=hz / lstep, frames=len(res1), tau_range=[float(taus[0]), 0.0],
                             kstar_local_selfx_at_tstar=len(res1[-1].get("local", [])),
                             kstar_local_selfx_rows=sorted({int(v[0]) for v in res1[-1].get("local", [])}),
                             section_frames=len(raw_sec), section_rows=sorted({int(r) for _, o in raw_sec for r in o["rows"]}),
                             section_tau_range=[float(taus[raw_sec[0][0]]), float(taus[raw_sec[-1][0]])] if raw_sec else None,
                             local_motion_frames=len(raw_loc), local_motion_rows=sorted({int(v[0]) for _, vs in raw_loc for v in vs}))
    log("走査 1 回目（F のこまごとの層の前、120 Hz、%d こま、%.0f s）：断面の自己交差 %d こま（行 %s）、動きが作った局所の自己交差 %d こま（行 %s）、K*′ から %d 頂点" % (
        len(res1), time.time() - t0, len(raw_sec), scan_rec["e_raw"]["section_rows"], len(raw_loc), scan_rec["e_raw"]["local_motion_rows"],
        scan_rec["e_raw"]["kstar_local_selfx_at_tstar"]))
    # ---- num_sheet_clearance の窓（E のままでもつれる行 ±row_pad、時刻の区間 ± margin、前後 ramp）
    if g.f_on["sheet_clearance"]:
        flags = {}
        for k, o in raw_sec:
            for r in o["rows"]:
                flags.setdefault(int(r), set()).add(k)
        for k, vs in raw_loc:
            for v in vs:
                flags.setdefault(int(v[0]), set()).add(k)
        pad = int(GWp.get("window_row_pad", 2))
        fl2 = {}
        for r, ks in flags.items():
            for dr in range(-pad, pad + 1):
                if 0 <= r + dr < g.K.nv:
                    fl2.setdefault(r + dr, set()).update(ks)
        wins = row_windows(fl2, n, int(round(float(GWp.get("window_merge_s", 0.5)) * hz)), int(round(float(GWp.get("window_margin_s", 0.25)) * hz)), lo=0)
        ramp = float(GWp.get("window_ramp_s", 0.3))
        rows_, a_, b_, rp_ = [], [], [], []
        for r in sorted(wins):
            for k0, k1 in wins[r]:
                rows_.append(r)
                a_.append(float(taus[k0]))
                b_.append(float(taus[k1]))
                rp_.append(ramp)
        gw_path = os.path.join(work, "guard_window.npz")
        np.savez(gw_path, rows=np.array(rows_, int), t0=np.array(a_), t1=np.array(b_), ramp=np.array(rp_))
        g.set_guard_window(gw_path)
        stage = dict(stage, gw=gw_path)
        scan_rec["guard_window"] = dict(rows=sorted(wins), windows={str(r): [[float(taus[k0]), float(taus[k1])] for k0, k1 in v] for r, v in wins.items()},
                                        ramp_s=ramp, row_pad=pad)
        log("  num_sheet_clearance の窓：%d 行（例 %s）" % (len(wins), {r: [[round(float(taus[k0]), 3), round(float(taus[k1]), 3)] for k0, k1 in v]
                                                           for r, v in list(sorted(wins.items()))[:3]}))
    # ---- 2 回目（F の層、橋渡しの前）
    t0 = time.time()
    rawp = (pA, pY, pT)
    st2 = dict(stage, raw=rawp, layers=dict(g.f_on, bridge=False))
    res2 = list(pool.imap(_t_pass2, [(k, st2, (k % lstep == 0) or k == n) for k in range(n + 1)], chunksize=4))
    lap("scan_pass2", t0)
    f_sec = [(k, o) for k, o in enumerate(res2) if o["rows"]]
    f_loc = [(k, [v for v in map(tuple, o["local"]) if v not in inh]) for k, o in enumerate(res2) if "local" in o]
    f_loc = [(k, v) for k, v in f_loc if v]
    kmax = max(range(len(res2)), key=lambda k: res2[k]["sc_max_push_m"])
    scan_rec["f_before_bridge"] = dict(section_frames=len(f_sec), section_rows=sorted({int(r) for _, o in f_sec for r in o["rows"]}),
                                       section_tau=[float(taus[k]) for k, _ in f_sec][:200],
                                       local_motion_frames=len(f_loc), local_motion_rows=sorted({int(v[0]) for _, vs in f_loc for v in vs}),
                                       sheet_clearance_max_push_m=float(res2[kmax]["sc_max_push_m"]), sheet_clearance_max_push_tau=float(taus[kmax]),
                                       sheet_clearance_push_by_tau={("%+.3f" % taus[k]): round(res2[k]["sc_max_push_m"], 4) for k in range(0, n + 1, 12)})
    log("走査 2 回目（F、橋渡しの前、%.0f s）：断面の自己交差 %d こま（行 %s）、動きが作った局所の自己交差 %d こま（行 %s）、押した量の最大 %.3f m（τ %.3f）" % (
        time.time() - t0, len(f_sec), scan_rec["f_before_bridge"]["section_rows"], len(f_loc), scan_rec["f_before_bridge"]["local_motion_rows"],
        res2[kmax]["sc_max_push_m"], taus[kmax]))
    # ---- 橋渡し
    t0 = time.time()
    if g.f_on["bridge"] and (f_sec or f_loc):
        flags = {}
        for k, o in f_sec:
            for r in o["rows"]:
                flags.setdefault(int(r), set()).add(k)
        for k, vs in f_loc:
            for v in vs:
                for dr in (-1, 0, 1):
                    if 0 <= int(v[0]) + dr < g.K.nv:
                        flags.setdefault(int(v[0]) + dr, set()).add(k)
        mg = int(round(float(BR["margin_s"]) * hz))
        gr = int(round(float(BR["grow_s"]) * hz))
        mgap = int(round(float(BR["merge_gap_s"]) * hz))
        padb = int(BR.get("row_pad", 2))
        hist = []
        for it in range(int(BR["max_grow"]) + 1):
            t1 = time.time()
            row_ivs = group_windows(flags, n, mgap, mg, padb, g.K.nv, lo=1)
            # 繰り返しごとに別のファイル（子のプロセスはファイルの名前で読み直しを決めるので、同じ名前に上書きすると古い区間のまま）
            bridge_it = os.path.join(work, "bridge_it%d.npz" % it)
            make_bridge(pool, st2, row_ivs, taus, bridge_it, log)
            st_b = dict(st2, bridge=bridge_it, layers=None)
            vk = set()
            for r, ivs in row_ivs.items():
                for k0, k1 in ivs:
                    vk.update(range(max(k0 - 2, 0), min(k1 + 2, n) + 1))
            vk = sorted(vk)
            # 確かめは 1 回目の断面のファイル（120 Hz の格子）に F の層（橋渡しを含む）を掛けて行う（生成器の評価をしない）。局所の自己交差も全部のこまで
            vres = list(pool.imap(_t_pass2, [(k, st_b, True) for k in vk], chunksize=2))
            bad = {}
            for kk, rr in zip(vk, vres):
                for r in rr["rows"]:
                    bad.setdefault(int(r), set()).add(kk)
                for v in rr.get("local", []):
                    if tuple(v) not in inh:
                        bad.setdefault(int(v[0]), set()).add(kk)
            nbad = len({k for ks in bad.values() for k in ks})
            hist.append(dict(iteration=it, rows=sorted(row_ivs), intervals={str(r): [[float(taus[a_]), float(taus[b_])] for a_, b_ in v] for r, v in row_ivs.items()},
                             verify_frames_120hz=len(vk), remaining_rows=sorted(bad), remaining_frames=nbad, file=rel(bridge_it),
                             seconds=round(time.time() - t1, 1)))
            log("  橋渡し %d 回目：%d 行、確かめ %d こま（120 Hz の格子）、残り %s（%.0f s）" % (it, len(row_ivs), len(vk), sorted(bad), time.time() - t1))
            if not bad or it == int(BR["max_grow"]):
                break
            for r, ks in bad.items():
                f_ = flags.setdefault(r, set())
                f_.update(ks)
                f_.update({max(min(ks) - gr, 1), min(max(ks) + gr, n)})
        # 残りのこまが最も少ない繰り返しの区間を使う（同じなら早い方）。子のプロセスが読み直すよう、まだ使っていない名前 bridge.npz に写す
        best = min(range(len(hist)), key=lambda i: (hist[i]["remaining_frames"], i))
        bridge_path = os.path.join(work, "bridge.npz")
        shutil.copyfile(os.path.join(work, "bridge_it%d.npz" % best), bridge_path)
        scan_rec["bridge"] = hist
        scan_rec["bridge_chosen_iteration"] = best
        log("  橋渡し：%d 回目の区間を使う（残り %d こま）" % (best, hist[best]["remaining_frames"]))
        g.set_bridge(bridge_path)
        stage = dict(stage, bridge=bridge_path)
        # 橋渡しの後の全部のこまの確かめ（120 Hz の格子、局所は 30 Hz）：残りを記録
        t1 = time.time()
        st_b = dict(st2, bridge=bridge_path, layers=None)
        res3 = list(pool.imap(_t_pass2, [(k, st_b, (k % lstep == 0) or k == n) for k in range(n + 1)], chunksize=4))
        s3 = [(k, o) for k, o in enumerate(res3) if o["rows"]]
        l3 = [(k, [v for v in map(tuple, o["local"]) if v not in inh]) for k, o in enumerate(res3) if "local" in o]
        l3 = [(k, v) for k, v in l3 if v]
        scan_rec["f_after_bridge"] = dict(section_frames=len(s3), section_rows=sorted({int(r) for _, o in s3 for r in o["rows"]}),
                                          local_motion_frames=len(l3), local_motion_rows=sorted({int(v[0]) for _, vs in l3 for v in vs}),
                                          seconds=round(time.time() - t1, 1))
        log("走査 3 回目（橋渡しの後、%.0f s）：断面の自己交差 %d こま、動きが作った局所の自己交差 %d こま（30 Hz）" % (time.time() - t1, len(s3), len(l3)))
    for pth in (pA, pY):
        try:
            os.remove(pth)
        except OSError:
            pass
    lap("bridge", t0)
    # ---- 4. 節点・パッケージ
    t0 = time.time()
    B = PBuilder(g, pool, stage, log)
    B.build_knots()
    lap("knots", t0)
    t0 = time.time()
    rec, deq16 = G28.export_package(g, B, outdir, log)
    deq_hi, deq_fine = GE.export_lo(rec, B, outdir, log)
    assert float(np.abs(deq_hi - deq16).max()) < 1e-9
    rec["number"] = "設計28修正01 試行F"
    rec["generator"]["code"] = "Tools/GWWaveGen/ds28r01f/ds28r01f_model.py（試行E ＋ num_tstar_exact・num_sheet_clearance・num_bridge_tangles。%s）" % g.variant
    rec["generator"]["code_sha256"] = code_sha(MD)
    rec["generator"]["summary"] = {k: (v if not isinstance(v, float) else G27.fnum(v, 6)) for k, v in g.summary().items()}
    rec["kstar"] = dict(dir=g.K.src["dir"], sha256=g.K.sha, landmarks=g.K.landmarks, landmarks_source=g.K.src["landmarks_source"], j_tip=int(g.j_tip),
                        trough_min_m=float(g.K.T_trough.min()),
                        note_ja="K*′ はフォルダーで渡した（ds28r01d_kstar.py）。t* は K*′（谷を含む）そのもの（num_tstar_exact）")
    rec["tstar"]["note_ja"] = "最後の層（τ = 0）は、K*′（%s。谷を含む）そのもの（量子化の差だけ）。" % g.K.src["dir"]
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    X0 = B.Xk[-1] + g.origin(0.0)[None, None, :]
    dK = np.linalg.norm(X0 - g.K.X, axis=-1)
    dG = np.linalg.norm(X0 - g.K.Xgwb, axis=-1)
    lap("export", t0)
    vr = dict(dir=rel(outdir), variant=g.variant, overrides=ov, off=off, kstar=rec["kstar"], f_params=g.RF, f_on=g.f_on, e_on=g.e_on, d_on=g.d_on,
              layers=rec["layers"], pos_sha256=rec["pos_sha256"], pos_lo_sha256=rec["pos_lo_sha256"], twhite_sha256=rec["twhite_sha256"],
              keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), pos_lo_mib=G27.fnum(rec["pos_lo_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"],
              quantization_max_err_m=rec["quantization_max_err_m"], pos_precision=rec["pos_precision"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"],
              tstar_vs_kstar_float_m=dict(max_vs_rows=float(dK.max()), max_vs_gwb=float(dG.max())),
              no_rebound=getattr(g, "_nr_stats", None), T_row_range=[float(g.T_row.min()), float(g.T_row.max())], scan=scan_rec,
              workers=nw, power_throttling_opt_out=list(thr), bridge_file=rel(bridge_path) if bridge_path else None,
              bridge_sha256=MD.sha256_file(bridge_path) if bridge_path else None)
    try:
        t0 = time.time()
        rows = sorted(set(int(np.argmin(np.abs(g.K.c - c))) for c in GD.LAUNCH_C) & set(g.lip.keys()))
        vr["lip_launch"] = g.launch_table(rows)
        lap("lip_launch", t0)
    except Exception as e:  # 記録だけ
        vr["lip_launch_error"] = repr(e)
    if not a.no_sea:
        t0 = time.time()
        if g.f_on.get("sea_sample_range"):
            SR = RF["sea_sample_range"]
            ps = export_sea_range(g, B, outdir, float(SR["a_min_m"]), float(SR["a_max_m"]), float(SR.get("step_m", 1.0)))
        else:
            ps = G27.export_sea(g, B, outdir)
        vr["sea_npz"] = dict(path=rel(ps), sha256=MD.sha256_file(ps),
                             a_range=[float(RF["sea_sample_range"]["a_min_m"]), float(RF["sea_sample_range"]["a_max_m"])]
                             if g.f_on.get("sea_sample_range") else [-330.0, 130.0])
        lap("sea", t0)
    if not a.no_check:
        t0 = time.time()
        chk = run_checks_parallel(g, B, deq_fine, log, pool, stage)
        kn = B.knots
        nn = int(np.floor(-g.tau_min * 30.0 + 1e-9))
        worst = 0.0
        for k in range(nn + 1):
            t = round(-(nn - k) / 30.0, 9)
            worst = max(worst, float(np.linalg.norm(B.herm(t, kn, deq_hi) - B.herm(t, kn, deq_fine), axis=-1).max()))
        chk["hermite_playback_err_m"]["note_ja"] = "量子化した節点（16 bit ＋ 精度の層、新しい再生器）の Hermite と解析の生成器の差（全頂点の最大）。30 Hz のコマと節点の間の中点"
        chk["hermite_playback_err_m"]["hi_only_minus_fine_max_m"] = worst
        chk["hermite_playback_err_m"]["hi_only_bound_m"] = float(chk["hermite_playback_err_m"]["max"]) + worst
        G27.dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
        vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
        vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
        lap("checks", t0)
    # ---- 5. F の層の大きさ（P20）
    t0 = time.time()
    ptaus = [round(float(t), 9) for t in np.concatenate([np.arange(-9.5, -3.0 + 1e-9, 0.25), np.arange(-2.95, 1e-9, 0.05)])]
    p20 = {}
    for tau, o in pool.imap(_t_p20, [(t, stage) for t in ptaus], chunksize=2):
        for nm, (m, r, c) in o.items():
            e = p20.setdefault(nm, dict(max_vertex_diff_m=0.0, per_tau={}))
            e["per_tau"]["%+.2f" % tau] = round(m, 4)
            if m > e["max_vertex_diff_m"]:
                e.update(max_vertex_diff_m=m, at=dict(tau=tau, row=r, col=c, c_m=float(g.K.c[r])))
    names = dict(back_no_undercut="ds_back_no_undercut（近似：ΔL の当てはめは入れた版）", lip_body="num_tail_lip_body＋num_small_lip_body（κ = 0 の行）",
                 balance_swell_calm="num_balance_swell_calm（仕上げ27。海の釣り合いの κ_s だけを切った形との差）",
                 tstar_exact="num_tstar_exact", sheet_clearance="num_sheet_clearance", bridge="num_bridge_tangles",
                 all="F の層（t*・隙間・橋渡し）の全部（E のまま（κ の差し替えの後）との差）")
    vr["p20"] = {names.get(k, k): v for k, v in p20.items()}
    G27.dump_json(os.path.join(outdir, "p20_f_layers.json"), dict(note_ja="F の層ごとの大きさ（P20）：全部を入れた形と、その層だけを切った形の頂点の差（局所座標）の最大。τ −9.5〜−3 は 0.25 s、−2.95〜0 は 0.05 s",
                                                                  kstar=rec["kstar"]["dir"], layers=vr["p20"]))
    lap("p20_f", t0)
    pool.close()
    pool.join()
    # 走査の 1 回目の断面のファイル（raw_A・raw_Y、約 1.5 GB）は、子のプロセスが終わった後に消す（F_R1・F_R2 では子のプロセスが
    # ファイルを掴んだまま残り、手で消した。--keep-raw で残す）
    if not a.keep_raw:
        import gc
        gc.collect()
        for pth in (pA, pY):
            try:
                os.remove(pth)
                logs.append("消した：%s" % rel(pth))
            except OSError as e:
                logs.append("消せなかった：%s（%s）" % (rel(pth), e))
    vr["timing_s"] = timing
    vr["seconds"] = round(time.time() - t_all, 1)
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(MD), result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28r01f_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t_all))


REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

if __name__ == "__main__":
    main()
