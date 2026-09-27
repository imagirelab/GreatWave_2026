# -*- coding: utf-8 -*-
"""設計27：単発砕波の生成器（ds27_model.py）から DS27 keypose パッケージ（入れた版・切った版）と時間曲線の表を書き出す。

使い方（リポジトリの根で。run_ds27.ps1 が同じことをする）:
    py -3.10 -B Tools/GWWaveGen/ds27/ds27_generate.py [--versions art_on,art_off] [--out Unity/Build/Design/27] [--no-check]
出力：
    Tools/GWWaveGen/ds27/timewarp_default.json・timewarp_alt.json（層7。コミットする小さな表）
    Unity/Build/Design/27/<版>/ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin（パッケージ。Git 対象外）
    Unity/Build/Design/27/<版>/ds27_sea.npz（任意。シートの外の解析式の海を行の断面に沿って標本化したもの＝検査器の --sea と
        設計30 の照合用。キー tau（10 Hz）・a（地面）・eta[時刻, 240, a]・Ac[時刻, 240]・knot_tau・Ac_knots[節点, 240]）
    Unity/Build/Design/27/<版>/ds27_checks.json（自前の簡単な検査）、Unity/Build/Design/27/ds27_generate_log_<版>.json（時間などの記録）
パッケージの 3 ファイルは決定的（同じ入力で同じバイト）。時刻や所要時間は ds27_generate_log_<版>.json にだけ書く。1 回の計算を 30 分以内にするため、版ごとに分けて走らせてよい（run_ds27.ps1 は版ごとに 1 回ずつ呼ぶ）。
節点：τ −10.125〜−3.0 s は 0.25 s、−3.0〜0 s は 1/30 s。各区間の 6 点で Hermite と解析の差が 2.5 mm を超えたら中点を足す（最大 6 回）。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # 行列積の和の順を固定し、同じバイトを保つ
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds27_model as MD  # noqa: E402
import ds27_timewarp as TW  # noqa: E402
from ds27_checks import MeshStats, stage_metrics  # noqa: E402
from ds27_package import hermite_weights  # noqa: E402

REPO = MD.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "27")
CODE_FILES = ["ds27_model.py", "ds27_timewarp.py", "ds27_generate.py", "ds27_package.py", "ds27_checks.py", "ds27_params.json"]


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def fnum(x, n=6):
    return None if x is None else float(round(float(x), n))


def dump_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


class Builder:
    def __init__(self, gen, log):
        self.g = gen
        self.log = log
        self.cache = {}
        self.Ac = {}
        self.n_eval = 0

    def X(self, tau):
        k = round(float(tau), 9)
        if k not in self.cache:
            X, A, Y, d = self.g.local(k, info=True)
            self.cache[k] = X
            self.Ac[k] = d["Ac"].copy()
            self.n_eval += 1
        return self.cache[k]

    def gen_only(self, tau):
        self.n_eval += 1
        return self.g.local(float(tau))

    def herm(self, tau, knots, Xk):
        idx, w = hermite_weights(knots, tau)
        out = np.zeros_like(Xk[0])
        for q in range(4):
            if w[q] != 0.0:
                out += w[q] * Xk[idx[q]]
        return out

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
            kn = np.array(knots)
            Xk = [self.X(t) for t in knots]
            add = []
            worst = 0.0
            t0 = time.time()
            for i in sorted(to_check):
                lo, hi = kn[i], kn[i + 1]
                emax = 0.0
                for j in range(1, m + 1):
                    t = lo + (hi - lo) * j / (m + 1)
                    e = float(np.linalg.norm(self.herm(t, kn, Xk) - self.gen_only(t), axis=-1).max())
                    emax = max(emax, e)
                worst = max(worst, emax)
                if emax > tol:
                    add.append(round(0.5 * (lo + hi), 9))
            rounds.append(dict(round=rnd, knots=len(knots), intervals_checked=len(to_check), worst_err_m=worst, added=len(add), seconds=round(time.time() - t0, 1)))
            self.log("  節点 %d 回目：%d 層、%d 区間を検査、差の最大 %.2f mm、追加 %d（%.0f s）" % (rnd, len(knots), len(to_check), worst * 1000, len(add), time.time() - t0))
            if not add:
                break
            knots = sorted(set(knots) | set(add))
            idx = [knots.index(t) for t in add]
            to_check = set()
            for k in idx:
                for i in range(k - 2, k + 2):
                    if 0 <= i < len(knots) - 1:
                        to_check.add(i)
        self.knots = np.array(knots)
        self.Xk = np.stack([self.X(t) for t in knots])
        self.rounds = rounds
        return self.knots


def export_package(g, B, outdir, log):
    os.makedirs(outdir, exist_ok=True)
    kn = B.knots
    Xs = B.Xk
    L = len(kn)
    nv, nu = g.K.nv, g.K.nu
    lo = Xs.reshape(-1, 3).min(0) - 0.01
    hi = Xs.reshape(-1, 3).max(0) + 0.01
    lo = np.floor(lo * 1000) / 1000
    hi = np.ceil(hi * 1000) / 1000
    size = hi - lo
    q = np.clip(np.round((Xs - lo) / size * 65535.0), 0, 65535).astype("<u2")
    pos = np.concatenate([q, np.full(q.shape[:-1] + (1,), 65535, "<u2")], -1)
    ppos = os.path.join(outdir, "ds27_pos_rgba16.bin")
    pos.tofile(ppos)
    deq = lo + q.astype(np.float64) / 65535.0 * size
    qerr = float(np.linalg.norm(deq - Xs, axis=-1).max())
    T = g.twhite()
    ptw = os.path.join(outdir, "ds27_twhite_r32f.bin")
    T.astype("<f4").tofile(ptw)
    # 波の枠の原点（480 Hz、最後 = 0）
    hz = int(g.P["knots"]["frame_hz"])
    n0 = int(round(-g.tau_min * hz))
    ftau = [round(-(n0 - k) / hz, 9) for k in range(n0 + 1)]
    forg = [[round(float(v), 7) for v in g.origin(t)] for t in ftau]
    code_sha = {f: MD.sha256_file(os.path.join(HERE, f)) for f in CODE_FILES}
    Tf = T.astype(np.float64)
    white_now = Tf < 1e8
    rec = {
        "schema": "GreatWave.DS27.keypose/1", "number": "設計27", "version": g.version,
        "layers": int(L), "rows": int(nv), "cols": int(nu),
        "bbox_min": [float(v) for v in lo], "bbox_size": [float(v) for v in size],
        "knot_tau": [float(v) for v in kn], "t_star_layer": int(L - 1),
        "frame": {"tau": ftau, "origin": forg, "hz": hz,
                  "note_ja": "波の枠の原点 O(τ)（ワールド、m）。O(τ) = O_K − X(τ)·t（O_K は K* の断面の原点、t は進行方向、X は峰の行の頂が t* までに進む残りの距離：c0 = 20 m/s、噴流の始まり τ −2.4 s から t* まで 0.8 c0 へ線形に減速）。間は線形補間、範囲の外は端の標本。"},
        "pos_file": "ds27_pos_rgba16.bin", "pos_sha256": MD.sha256_file(ppos), "pos_bytes": int(os.path.getsize(ppos)),
        "pos_format_ja": "RGBA16 UNORM（TextureFormat.RGBA64）、層 × 行 × 列 × 4、リトルエンディアン。xyz = (位置 − bbox_min)/bbox_size·65535、A = 65535。位置は波の枠の局所座標（ワールド − O(τ)、軸はワールド）。",
        "twhite_file": "ds27_twhite_r32f.bin", "twhite_sha256": MD.sha256_file(ptw), "twhite_bytes": int(os.path.getsize(ptw)),
        "twhite_format_ja": "R32F（TextureFormat.RFloat）、行 × 列。T_white は τ の秒（t* = 0）。τ ≥ T_white で白（終態の色区が白のテクセルだけ）。+1e9 = t* まで白にならない。",
        "twhite_never": 1.0e9,
        "twhite_summary": {"min_tau": fnum(Tf[white_now].min(), 4), "max_tau": fnum(Tf[white_now].max(), 4),
                           "vertices_white_before_tstar": int((Tf <= 0).sum()), "vertices_never": int((~white_now).sum())},
        "interpolation_ja": "節点 i と i+1 の間の τ の 3 次 Hermite。傾き m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})（両端は片側）。節点が等間隔なら一様の Catmull-Rom と同じ。範囲の外は端の層。",
        "quantization_max_err_m": qerr,
        "tstar": {"layer": int(L - 1), "note_ja": "最後の層（τ = 0）は、入れた版では K*（26修正01）そのもの（量子化の差だけ）。切った版は K* ではない（P14）。"},
        "switches": g.sw,
        "generator": {"code": "Tools/GWWaveGen/ds27/ds27_model.py", "code_sha256": code_sha, "params_sha256": g.params_sha,
                      "conditions": rel(os.path.join(REPO, g.P["inputs"]["conditions"])), "conditions_sha256": g.cond_sha,
                      "kstar_sha256": g.K.sha, "adaptive_rounds": [{k: v for k, v in r.items() if k != "seconds"} for r in B.rounds],
                      "summary": {k: (v if not isinstance(v, float) else fnum(v, 6)) for k, v in g.summary().items()}},
        "sea_model": g.sea_model_record(),
        "gpu_estimate": {"layer_mib": fnum(nv * nu * 8 / 2 ** 20, 4), "texture2darray_mib": fnum(L * nv * nu * 8 / 2 ** 20, 2),
                         "texture2darray_readable_mib": fnum(2 * L * nv * nu * 8 / 2 ** 20, 2), "twhite_mib": fnum(nv * nu * 4 / 2 ** 20, 3),
                         "budget_mib": 512,
                         "note_ja": "RGBA64 の Texture2DArray（層 × 400 × 240 × 8 バイト）。読み取り可能のままなら CPU の写しで 2 倍（見積もり、Unity の実測は設計29）。法線はパッケージに入れない（再生側で三角形から作る）。"},
    }
    dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    log("  パッケージ：%d 層、位置 %.1f MiB、量子化の差の最大 %.2f mm" % (L, rec["pos_bytes"] / 2 ** 20, qerr * 1000))
    return rec, deq


def export_sea(g, B, outdir, hz=10.0):
    """シートの外の解析式の海を、行の断面に沿った地面の a（−330〜130 m、1 m）で、10 Hz（最後 = t*）に標本化する。
    A_c,r は節点の値を τ で線形に補間する。Ac_knots は節点ごとの表（設計30 の周りの海が読む）。"""
    a = np.arange(-330.0, 130.0 + 1e-9, 1.0)
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


def run_checks(g, B, deq, log, hz=30.0, si_every=2):
    """30 Hz（物理の時刻）の連続性と網の形、Hermite の再生の差（量子化した節点）、段階の目安。"""
    kn = B.knots
    n = int(np.floor(-g.tau_min * hz + 1e-9))
    taus = [round(-(n - k) / hz, 9) for k in range(n + 1)]
    MS = MeshStats(g, hz)
    herr = []
    stage = {"main": [], "peak": []}
    rows_st = {"main": g.K.main_row, "peak": int(np.argmin(np.abs(g.K.c - g.c_pk_on)))}
    t0 = time.time()
    for i, t in enumerate(taus):
        X, A, Y, d = g.local(t, info=True)
        MS.add(t, X, A, Y, si=(i % si_every == 0))
        if i % 15 == 0 or i == len(taus) - 1:
            MS.normals_check(X)
        Hq = B.herm(t, kn, deq)
        herr.append((t, float(np.linalg.norm(Hq - X, axis=-1).max()), float(np.percentile(np.linalg.norm(Hq - X, axis=-1), 99))))
        for key, r in rows_st.items():
            m = stage_metrics(A, Y, r)
            m["tau"] = t
            m["H_over_Hr"] = m["H"] / g.H[r]
            stage[key].append(m)
    # 区間の中点（節点の間）
    mid = []
    for i in range(len(kn) - 1):
        t = 0.5 * (kn[i] + kn[i + 1])
        X = g.local(t)
        e = np.linalg.norm(B.herm(t, kn, deq) - X, axis=-1)
        mid.append((t, float(e.max()), float(np.percentile(e, 99))))
    log("  検査：%d コマ（30 Hz）＋ 中点 %d（%.0f s）" % (len(taus), len(mid), time.time() - t0))
    allh = herr + mid
    worst = max(allh, key=lambda x: x[1])
    res = MS.result()
    # t* の姿（入れた版は K*）
    Xw0 = deq[-1] + g.origin(0.0)[None, None, :]
    dK = np.linalg.norm(Xw0 - g.K.X, axis=-1)
    dKg = np.linalg.norm(Xw0 - g.K.Xgwb, axis=-1)
    step = B.g.P["knots"]
    quant_step = None
    res_st = {}
    for key, S in stage.items():
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
    out = dict(hz=hz, frames=len(taus), tau_range=[taus[0], taus[-1]],
               hermite_playback_err_m=dict(max=worst[1], max_at_tau=fnum(worst[0], 4), p99_of_frame_p99=fnum(np.percentile([h[2] for h in allh], 99), 6),
                                           max_30hz=max(h[1] for h in herr), max_midpoints=max(h[1] for h in mid),
                                           note_ja="量子化した節点の Hermite と解析の生成器の差（全頂点の最大）。30 Hz のコマと節点の間の中点"),
               tstar_vs_kstar_world_max_m=float(dK.max()), tstar_vs_kstar_gwb_float32_max_m=float(dKg.max()),
               mesh_and_continuity=res, stage_estimate=res_st)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="art_on,art_off")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    ap.add_argument("--no-tables", action="store_true", help="時間曲線の表を書かない（決定性の確認の 2 回目）")
    a = ap.parse_args()
    t_all = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    cond = MD.load_json(os.path.join(REPO, "Docs", "Evidence", "Design", "26", "ds26_conditions.json"))
    if a.no_tables:
        files, info = {}, TW.tables(cond)[3]
    else:
        files, info = TW.write_tables(HERE, cond)
    log("時間曲線：%s（τ(0) = %.4f s）" % (", ".join(rel(p) for p in files.values()), info["tau_at_t0_default"]))
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds27/ds27_generate.py " + " ".join(sys.argv[1:]),
                  timewarp={k: dict(path=rel(p), sha256=MD.sha256_file(p)) for k, p in files.items()}, timewarp_info=info, versions={})
    for ver in [v.strip() for v in a.versions.split(",") if v.strip()]:
        t0 = time.time()
        log("版 %s" % ver)
        g = MD.Generator(ver)
        B = Builder(g, log)
        B.build_knots()
        outdir = os.path.join(a.out, ver)
        rec, deq = export_package(g, B, outdir, log)
        vr = dict(dir=rel(outdir), layers=rec["layers"], pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"],
                  keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
                  pos_mib=fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
                  knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"])
        if not a.no_sea:
            ps = export_sea(g, B, outdir)
            vr["sea_npz"] = dict(path=rel(ps), sha256=MD.sha256_file(ps))
        if not a.no_check:
            chk = run_checks(g, B, deq, log)
            dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
            vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
            vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
        vr["seconds"] = round(time.time() - t0, 1)
        runlog["versions"][ver] = vr
        log("版 %s：%.0f s" % (ver, time.time() - t0))
    runlog["seconds_total"] = round(time.time() - t_all, 1)
    runlog["log"] = logs
    dump_json(os.path.join(a.out, "ds27_generate_log_%s.json" % "_".join(runlog["versions"].keys())), runlog)
    print("DONE %.0f s" % (time.time() - t_all))


if __name__ == "__main__":
    main()
