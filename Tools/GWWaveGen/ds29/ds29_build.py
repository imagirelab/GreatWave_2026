# -*- coding: utf-8 -*-
"""設計29：表示用サーフェスの keypose パッケージ（設計27 の DS27 の書式）と t* の網を、密度ごとに書き出す。

使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/ds29/ds29_build.py [--only full_240x400,half_120x200] [--out Unity/Build/Design/29]
        [--variant NAME:ROWS:COLS:tube=arc_tstar]   （比べるための追加の組。区間の張り方を上書きできる）
出力（Git 対象外）：Unity/Build/Design/29/<名前>/
    ds27_keypose.json・ds27_pos_rgba16.bin・ds27_twhite_r32f.bin   設計27 の書式（rows・cols は json に書く。決定的）
    ds29_uv3_f32.bin     頂点ごとの焼き込み用 UV（UV3、float32 × 2、頂点の添字 = 行 × cols + 列）
    ds29_map.npz         表示の網の媒介変数（rho・kappa0・k_seg・区間の張り方）。関門の検査器が読む
    tstar/kstar_a45.gwb・.obj・_meta.json   t* の表示用の網（K* の面の上。AF26KStarMesh と Blender の検査が読む書式）
    ds29_build_log.json  時間などの記録（決定的でない値はここだけ）
節点：源（設計28 の既定のパッケージ）の節点をそのまま使い、arc_tau の区間がある網は、各区間の内側の 2 点で Hermite と
正確な表示の網の差が 2.5 mm を超えたら中点を足す（最大 3 回）。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds29_surface as S  # noqa: E402
from ds27_package import hermite_weights  # noqa: E402

REPO = S.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "29")
CODE_FILES = ["ds29_surface.py", "ds29_build.py", "ds29_params.json"]


def code_sha():
    return {f: S.sha256_file(os.path.join(HERE, f)) for f in CODE_FILES}


class Cache:
    def __init__(self, src, log):
        self.src, self.log, self.d, self.n = src, log, {}, 0

    def __call__(self, tau):
        k = round(float(tau), 9)
        if k not in self.d:
            self.d[k] = self.src.local(k)
            self.n += 1
        return self.d[k]


def herm(knots, layers, tau):
    idx, w = hermite_weights(knots, float(tau))
    out = np.zeros(layers.shape[1:])
    for q in range(4):
        if w[q] != 0.0:
            out += w[q] * layers[idx[q]]
    return out


def build_layers(d, knots, X, P, log):
    """節点の表示の網。arc_tau があれば節点を足す。戻り (knots, layers (L, nv, nu, 3), rounds)。"""
    kn = list(np.round(np.asarray(knots, np.float64), 9))
    lay = {t: d.eval(X(t), t) for t in kn}
    rounds = []
    if d.has_tau:
        KP = P["knots"]
        tol, m = float(KP["adaptive_tol_m"]), int(KP["adaptive_check_per_interval"])
        to_check = set(range(len(kn) - 1))
        for rnd in range(int(KP["adaptive_max_rounds"])):
            kk = np.array(kn)
            Ls = np.stack([lay[t] for t in kn])
            add, worst, t0 = [], 0.0, time.time()
            for i in sorted(to_check):
                lo, hi = kk[i], kk[i + 1]
                emax = 0.0
                for j in range(1, m + 1):
                    t = lo + (hi - lo) * j / (m + 1)
                    e = float(np.linalg.norm(herm(kk, Ls, t) - d.eval(X(t), t), axis=-1).max())
                    emax = max(emax, e)
                worst = max(worst, emax)
                if emax > tol:
                    add.append(round(0.5 * (lo + hi), 9))
            rounds.append(dict(round=rnd, knots=len(kn), intervals_checked=len(to_check), worst_err_m=worst, added=len(add)))
            log("  %s 節点 %d 回目：%d 層、%d 区間、差の最大 %.2f mm、追加 %d（%.0f s）" % (d.name, rnd, len(kn), len(to_check), worst * 1000, len(add), time.time() - t0))
            if not add:
                break
            for t in add:
                lay[t] = d.eval(X(t), t)
            kn = sorted(set(kn) | set(add))
            idx = [kn.index(t) for t in add]
            to_check = set()
            for k in idx:
                for i in range(k - 2, k + 2):
                    if 0 <= i < len(kn) - 1:
                        to_check.add(i)
    return np.array(kn), np.stack([lay[t] for t in kn]), rounds


def export(d, src, knots, layers, outdir, log):
    os.makedirs(os.path.join(outdir, "tstar"), exist_ok=True)
    P = src.P
    L = len(knots)
    nv, nu = d.nv, d.nu
    lo, size, q = S.quantize(layers)
    pos = np.concatenate([q, np.full(q.shape[:-1] + (1,), 65535, "<u2")], -1)
    ppos = os.path.join(outdir, "ds27_pos_rgba16.bin")
    pos.tofile(ppos)
    deq = lo + q.astype(np.float64) / 65535.0 * size
    qerr = float(np.linalg.norm(deq - layers, axis=-1).max())
    T = d.twhite().astype("<f4")
    ptw = os.path.join(outdir, "ds27_twhite_r32f.bin")
    T.tofile(ptw)
    uv3 = d.attr(src.uv3).astype("<f4")
    puv3 = os.path.join(outdir, "ds29_uv3_f32.bin")
    uv3.tofile(puv3)
    Tf = T.astype(np.float64)
    white_now = Tf < 1e8
    pk = src.pkg
    n = nv * nu
    gpu_b = L * n * int(P["gpu"]["bytes_per_vertex_layer"])
    # t* の網（K* の面の上。源の生成器の τ = 0 は K* と 1e-14 m で同じなので、K* のワールドの位置から直接求める）
    Xt = d.eval(src.K.X, 0.0)
    uv = d.attr(src.uv)
    uv2 = d.attr(src.uv2)
    pg = os.path.join(outdir, "tstar", "kstar_a45.gwb")
    S.write_gwb(pg, nu, nv, uv, uv2, d.tris, Xt)
    po = os.path.join(outdir, "tstar", "kstar_a45.obj")
    S.write_obj(po, Xt, uv, d.tris, ["設計29 表示用サーフェス %s の t*（K* の面の上に張り直した網）、Unity のワールド座標（m）" % d.name,
                                       "vertex index = row * %d + column; rows = %d, cols = %d; vt = UV0（K* の UV0 を媒介変数で補間）" % (nu, nu, nv)])
    with open(os.path.join(src.K.dir, "kstar_a45_meta.json"), encoding="utf-8") as f:
        km = S.json.load(f)
    meta = {"schema": "GreatWave.DS29.tstar_meta/1", "number": "設計29", "key": "a45", "display": d.name,
            "nu": nu, "nv": nv, "vertex_count": n, "triangle_count": int(len(d.tris)),
            "frame": km["frame"], "rows": {"main_row_display": d.region()["main_row"], "peak_row_display": d.region()["peak_row"]},
            "format_ja": km["format_ja"] + "（設計29：nu・nv は表示の網の値）",
            "uv_layout_ja": "UV0・UV2 は K* の値を t* の媒介変数 (ρ, κ) の点で源の三角形の重心座標で補間したもの。UV3（焼き込み用）は ../ds29_uv3_f32.bin（頂点ごと）。",
            "source_kstar_sha256": src.g.K.sha, "files": {"gwb": "kstar_a45.gwb", "obj": "kstar_a45.obj"},
            "gwb_sha256": S.sha256_file(pg), "obj_sha256": S.sha256_file(po)}
    S.dump_json(os.path.join(outdir, "tstar", "kstar_a45_meta.json"), meta)
    reg = d.region()
    np.savez(os.path.join(outdir, "ds29_map.npz"), rho=d.rho, kappa0=d.kappa0, kap_src0=d.kap_src0, k_seg=d.k_seg, n_seg=d.n_seg,
             L=src.L, tau_cols=d.tau_cols, modes=np.array([d.modes[nm] for nm in S.SEGMENTS]), curled=reg["curled"],
             k_root=reg["k_root"], k_rim=reg["k_rim"], k_ja=reg["k_ja"], main_row=reg["main_row"], peak_row=reg["peak_row"])
    rec = {
        "schema": "GreatWave.DS27.keypose/1", "number": "設計29", "version": pk["version"], "variant": "display_" + d.name,
        "layers": int(L), "rows": int(nv), "cols": int(nu),
        "bbox_min": [float(v) for v in lo], "bbox_size": [float(v) for v in size],
        "knot_tau": [float(v) for v in knots], "t_star_layer": int(L - 1),
        "frame": pk["frame"],
        "pos_file": "ds27_pos_rgba16.bin", "pos_sha256": S.sha256_file(ppos), "pos_bytes": int(os.path.getsize(ppos)),
        "pos_format_ja": pk["pos_format_ja"],
        "twhite_file": "ds27_twhite_r32f.bin", "twhite_sha256": S.sha256_file(ptw), "twhite_bytes": int(os.path.getsize(ptw)),
        "twhite_format_ja": pk["twhite_format_ja"] + "（設計29：源の T_white を t* の媒介変数で補間。寄与する源の頂点の重みの半分以上が 1e9 なら 1e9）",
        "twhite_never": float(P["twhite_never"]),
        "twhite_summary": {"min_tau": float(round(Tf[white_now].min(), 4)), "max_tau": float(round(Tf[white_now].max(), 4)),
                           "vertices_white_before_tstar": int((Tf <= 0).sum()), "vertices_never": int((~white_now).sum())},
        "interpolation_ja": pk["interpolation_ja"],
        "quantization_max_err_m": qerr,
        "tstar": {"layer": int(L - 1), "note_ja": "最後の層（τ = 0）は K*（26修正01）の面の上の点（表示の網の頂点。量子化の差だけ）。"},
        "switches": pk["switches"],
        "generator": {"code": "Tools/GWWaveGen/ds29/ds29_surface.py", "code_sha256": code_sha(),
                      "source_package": S.rel(src.pkg_dir), "source_pos_sha256": pk["pos_sha256"], "source_keypose_json_sha256": src.pkg_json_sha,
                      "source_generator": pk["generator"]["code"], "source_generator_code_sha256": pk["generator"]["code_sha256"],
                      "kstar_sha256": pk["generator"]["kstar_sha256"]},
        "sea_model": pk["sea_model"],
        "display_surface": dict(d.describe(), uv3_file="ds29_uv3_f32.bin", uv3_sha256=S.sha256_file(puv3),
                                uv3_source=S.rel(src.uv3_path), uv3_source_sha256=src.uv3_sha,
                                tstar_mesh="tstar/kstar_a45.gwb", tstar_mesh_sha256=meta["gwb_sha256"],
                                region=dict(k_root=reg["k_root"], k_rim=reg["k_rim"], k_ja=reg["k_ja"], main_row=reg["main_row"], peak_row=reg["peak_row"],
                                            curled_rows=[int(np.nonzero(reg["curled"])[0][0]), int(np.nonzero(reg["curled"])[0][-1])]),
                                note_ja="表示の頂点は源（設計28 の既定）の面の上の点。唇（lip）は t* の弧長で一様な固定の媒介変数（物質の点の重み付きの平均＝放出の後は重力だけ）、"
                                        "管の天井（tube）はその時刻の源の弧長で一様（滑る）。UV3 は頂点ごと（ds29_uv3_f32.bin）で、AF28NprWave の列・行の表では表せない。"),
        "gpu_estimate": {"position_structured_buffer_mib": round(gpu_b / 2 ** 20, 2), "twhite_mib": round(n * 4 / 2 ** 20, 3),
                         "texture2darray_rgba64_mib": round(L * n * 8 / 2 ** 20, 2), "budget_mib": int(P["gpu"]["budget_mib"]),
                         "note_ja": P["gpu"]["note_ja"]},
    }
    S.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    log("  %s：%d 層、位置 %.1f MiB（GPU %.1f MiB）、量子化の差の最大 %.2f mm" % (d.name, L, rec["pos_bytes"] / 2 ** 20, gpu_b / 2 ** 20, qerr * 1000))
    return rec


def parse_variant(s):
    name, rows, cols, *rest = s.split(":")
    modes = {}
    for it in rest:
        k, v = it.split("=")
        modes[k] = v
    return dict(name=name, rows=int(rows), cols=int(cols), modes=modes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--only", default="")
    ap.add_argument("--variant", action="append", default=[])
    a = ap.parse_args()
    t_all = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    P = S.load_params()
    src = S.Source(P)
    log("源：%s（%d 層、T_white がパッケージと同じ：%s）%.0f s" % (S.rel(src.pkg_dir), len(src.knots), src.twhite_matches_package, time.time() - t_all))
    specs = [dict(name=x["name"], rows=x["rows"], cols=x["cols"], modes={}) for x in P["densities"]]
    only = [s for s in a.only.split(",") if s]
    if only:
        specs = [s for s in specs if s["name"] in only]
    specs += [parse_variant(v) for v in a.variant]
    X = Cache(src, log)
    # 源の再現：生成器の節点の値と設計28 のパッケージ（量子化）の差
    pk = src.pkg
    Q = np.fromfile(os.path.join(src.pkg_dir, "ds27_pos_rgba16.bin"), "<u2").reshape(len(src.knots), src.nv, src.nu, 4)
    lo, sz = np.array(pk["bbox_min"]), np.array(pk["bbox_size"])
    rep = 0.0
    for l, t in enumerate(src.knots):
        rep = max(rep, float(np.linalg.norm(lo + Q[l, ..., :3] / 65535.0 * sz - X(t), axis=-1).max()))
    del Q
    log("源の再現：生成器の節点と設計28 のパッケージの差の最大 %.3f mm（量子化 %.3f mm）" % (rep * 1000, pk["quantization_max_err_m"] * 1000))
    out = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), python=platform.python_version(),
               numpy=np.__version__, machine=platform.platform(), command="py -3.10 -B Tools/GWWaveGen/ds29/ds29_build.py " + " ".join(sys.argv[1:]),
               code_sha256=code_sha(), source_repro_max_m=rep, displays={})
    for sp in specs:
        t0 = time.time()
        modes = dict(P["segments"]["mode"])
        modes.update(sp["modes"])
        d = S.Display(src, sp["rows"], sp["cols"], name=sp["name"], modes=modes)
        kn, lay, rounds = build_layers(d, src.knots, X, P, log)
        rec = export(d, src, kn, lay, os.path.join(a.out, sp["name"]), log)
        out["displays"][sp["name"]] = dict(layers=rec["layers"], rows=d.nv, cols=d.nu, pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"],
                                           keypose_json_sha256=S.sha256_file(os.path.join(a.out, sp["name"], "ds27_keypose.json")),
                                           uv3_sha256=rec["display_surface"]["uv3_sha256"], tstar_gwb_sha256=rec["display_surface"]["tstar_mesh_sha256"],
                                           gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"], adaptive_rounds=rounds,
                                           describe=d.describe(), seconds=round(time.time() - t0, 1))
        del lay
    out["generator_evals"] = X.n
    out["seconds_total"] = round(time.time() - t_all, 1)
    out["log"] = logs
    S.dump_json(os.path.join(a.out, "ds29_build_log%s.json" % ("_" + "_".join(s["name"] for s in specs) if (only or a.variant) else "")), out)
    print("DONE %.0f s" % (time.time() - t_all))


if __name__ == "__main__":
    main()
