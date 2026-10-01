# -*- coding: utf-8 -*-
"""仕上げ28：ds28p の生成器（ds28p_model.Generator ＝ 試行F ＋ ds_upper_back_aspect・ds_far_hook_earlier）で包みを作る。

試行F の生成の台本（Tools/GWWaveGen/ds28r01f/ds28r01f_generate.py）をそのまま使い、子のプロセスの生成器を作る関数 _winit だけを
このファイルの _winit_p に差し替える（ファイルは変えない。spawn の子のプロセスもこの台本を __main__ として読み込むので、同じ差し替えが効く）。
引数は ds28r01f_generate.py と同じ（--kstar・--name・--out・--workers・--off …）。ds28p の値の入り切りと中身は、包みのフォルダーの
ds28p_generate_log.json に書く（試行F の生成の記録 ds28r01f_generate_log.json はそのまま）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28p/ds28p_generate.py --kstar Unity/Build/Polish/28/kstar_p28 --name G_p28a/art_on --out Unity/Build/Polish/28 --workers 5 [--p-off upper_back_aspect]
その後、検査の一式は ds28r01f_pipeline.py（pl28_pipeline_limited.py の包み）を --skip-generate で回す。
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DSF = os.path.abspath(os.path.join(HERE, "..", "ds28r01f"))
for _p in (DSF, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import ds28r01f_generate as GEN  # noqa: E402

P_FILES = ["ds28p_model.py", "ds28p_generate.py", "ds28p_params.json"]


def p_off():
    """--p-off で切る ds28p の名前（親のプロセスが環境変数 DS28P_OFF に書き、spawn の子のプロセスも同じ値を読む）。"""
    return tuple(n for n in os.environ.get("DS28P_OFF", "").split(",") if n)


def _winit_p(kdir, overrides, off):
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    import ds28p_model as MP
    GEN._G = MP.Generator(kstar_dir=kdir, f_overrides=overrides or None, off=tuple(off) + p_off(), defer_no_rebound=True)


GEN._winit = _winit_p

# ---- 省メモリの書き出し（--lean-export。仕上げ28 の回復、2026-10-01）
# この機械の確保の上限（commit）の残りが 1.5〜5 GB しかなく、G_p28rec の生成が 3 度、パッケージの書き出しの float64 の中間の配列
# （層 × 240 × 400 × 3、552 MiB ずつ）で MemoryError になった（精度の層 ds28r01e_generate.export_lo で 2 度、16 bit の層
# ds27_generate.export_package で 1 度）。この 2 つを、同じ式を層ごとに回す版に差し替える：
#   * ファイル（ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin・ds27_twhite_r32f.bin・ds27_keypose.json）のバイトと記録の値は元と同じ
#     （式は要素ごとで、ファイルは層の順に続けて書く。最大の値は層ごとの最大の最大）。
#   * 返す復号の位置（deq16・deq_fine、float64）は、<出力>/_work/ の .npy を写像した配列（ファイルが裏付け。確保の上限を使わない）。値は元と同じ。
#   * 呼ぶ側（ds28r01f_generate.main）の「deq_hi と deq16 が同じ」の確かめは、ここで層ごとに完全一致を確かめ、一致した時だけ deq16 そのものを
#     _SameAs の見え方で返す（引き算の中間の配列 1.1 GB を作らないため。一致しなければ別の配列を作り直して返す）。
# ds27_generate.py・ds28_generate.py・ds28r01e_generate.py・ds28r01f_generate.py は変えない。合成のデータで元の関数とバイト・値が同じことを確かめた。
import numpy as _np

_STASH = {}


class _SameAs(_np.ndarray):
    """deq16 そのものの見え方。deq16 との引き算だけを、層ごとの一致の確かめの結果（0）で返す。"""

    def __sub__(self, other):
        ref = _STASH.get("deq16")
        if (_STASH.get("same") and other is ref and self.shape == ref.shape
                and self.__array_interface__["data"][0] == _np.asarray(ref).__array_interface__["data"][0]):
            return _np.zeros((1,), _np.float64)
        return _np.ndarray.__sub__(_np.asarray(self), other)


def _memmap(outdir, name, shape):
    d = os.path.join(outdir, "_work")
    os.makedirs(d, exist_ok=True)
    return _np.lib.format.open_memmap(os.path.join(d, name), mode="w+", dtype=_np.float64, shape=shape)


def _export_package27_lean(g, B, outdir, log):
    """ds27_generate.export_package の写し。q・pos・deq・qerr だけを層ごとに計算する（ファイルと記録は同じ）。"""
    import ds27_generate as G27
    np = _np
    MD = G27.MD
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
    ppos = os.path.join(outdir, "ds27_pos_rgba16.bin")
    deq = _memmap(outdir, "deq16_f64.npy", Xs.shape)
    qerr = 0.0
    alpha = np.full((nv, nu, 1), 65535, "<u2")
    with open(ppos, "wb") as fo:
        for l in range(L):
            q = np.clip(np.round((Xs[l] - lo) / size * 65535.0), 0, 65535).astype("<u2")
            fo.write(np.concatenate([q, alpha], -1).tobytes())
            deq[l] = lo + q.astype(np.float64) / 65535.0 * size
            qerr = max(qerr, float(np.linalg.norm(deq[l] - Xs[l], axis=-1).max()))
    T = g.twhite()
    ptw = os.path.join(outdir, "ds27_twhite_r32f.bin")
    T.astype("<f4").tofile(ptw)
    hz = int(g.P["knots"]["frame_hz"])
    n0 = int(round(-g.tau_min * hz))
    ftau = [round(-(n0 - k) / hz, 9) for k in range(n0 + 1)]
    forg = [[round(float(v), 7) for v in g.origin(t)] for t in ftau]
    code_sha = {f: MD.sha256_file(os.path.join(G27.HERE, f)) for f in G27.CODE_FILES}
    Tf = T.astype(np.float64)
    white_now = Tf < 1e8
    fnum, rel, REPO = G27.fnum, G27.rel, G27.REPO
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
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    log("  パッケージ：%d 層、位置 %.1f MiB、量子化の差の最大 %.2f mm" % (L, rec["pos_bytes"] / 2 ** 20, qerr * 1000))
    _STASH["deq16"] = deq
    return rec, deq


def _export_lo_lean(rec, B, outdir, log):
    """ds28r01e_generate.export_lo の写し。層ごとに計算して書き、deq_fine はファイルが裏付けの配列で返す。"""
    np = _np
    import ds27_generate as G27
    import ds27_model as MD
    import ds28r01e_generate as GE
    Xs = B.Xk
    lo = np.asarray(rec["bbox_min"], np.float64)
    size = np.asarray(rec["bbox_size"], np.float64)
    L, nv, nu = Xs.shape[:3]
    deq16 = _STASH.get("deq16")
    deq_fine = _memmap(outdir, "deq_fine_f64.npy", Xs.shape)
    e_hi = 0.0
    e_fine = 0.0
    same = deq16 is not None and deq16.shape == Xs.shape
    p = os.path.join(outdir, GE.LO_NAME)
    alpha = np.full((nv, nu, 1), 255, np.uint8)
    with open(p, "wb") as fo:
        for l in range(L):
            u = (Xs[l] - lo) / size * 65535.0
            q = np.clip(np.round(u), 0, 65535)
            e = u - q
            ql = np.clip(np.round((e + 0.5) * 255.0), 0, 255).astype(np.uint8)
            fo.write(np.concatenate([ql, alpha], -1).tobytes())
            dh = lo + q / 65535.0 * size
            deq_fine[l] = lo + (q + ql.astype(np.float64) / 255.0 - 0.5) / 65535.0 * size
            e_hi = max(e_hi, float(np.linalg.norm(dh - Xs[l], axis=-1).max()))
            e_fine = max(e_fine, float(np.linalg.norm(deq_fine[l] - Xs[l], axis=-1).max()))
            if same and not np.array_equal(dh, deq16[l]):
                same = False
    _STASH["same"] = bool(same)
    if same:
        deq_hi = deq16.view(_SameAs)
    else:
        deq_hi = _memmap(outdir, "deq_hi_f64.npy", Xs.shape)
        for l in range(L):
            deq_hi[l] = lo + np.clip(np.round((Xs[l] - lo) / size * 65535.0), 0, 65535) / 65535.0 * size
    rec["extensions"] = ["pos_lo_rgba8/1"]
    rec["pos_lo_file"] = GE.LO_NAME
    rec["pos_lo_sha256"] = MD.sha256_file(p)
    rec["pos_lo_bytes"] = int(os.path.getsize(p))
    rec["pos_lo_format_ja"] = ("RGBA8 UNORM（TextureFormat.RGBA32）、層 × 行 × 列 × 4。16 bit の丸めの残り e = u − round(u)（u = (位置 − bbox_min)/bbox_size·65535）を "
                               "round((e + 0.5)·255) で持つ。A = 255。復号：位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size。"
                               "このファイルが無い・読まない再生器は ds27_pos_rgba16.bin だけで設計27 と同じに復号できる（後方互換）")
    rec["pos_precision"] = dict(hi_step_mm=float(size.max() / 65535 * 1000), fine_step_mm=float(size.max() / 65535 / 255 * 1000),
                                max_err_hi_m=e_hi, max_err_fine_m=e_fine)
    ge = rec["gpu_estimate"]
    ge["fine_extra_layer_mib"] = G27.fnum(nv * nu * 4 / 2 ** 20, 4)
    ge["fine_texture2darray_mib"] = G27.fnum(L * nv * nu * 12 / 2 ** 20, 2)
    ge["fine_texture2darray_readable_mib"] = G27.fnum(2 * L * nv * nu * 12 / 2 ** 20, 2)
    ge["fine_note_ja"] = "精度の層を読む再生器（29修正01）：RGBA64 ＋ RGBA32 の Texture2DArray（層 × 400 × 240 × 12 バイト）。読み取り可能のままなら 2 倍（見積もり）"
    log("  精度の層：%s、刻み %.4f mm（16 bit だけ %.3f mm）、量子化の差の最大 %.4f mm（16 bit だけ %.3f mm）" % (
        GE.LO_NAME, rec["pos_precision"]["fine_step_mm"], rec["pos_precision"]["hi_step_mm"], e_fine * 1000, e_hi * 1000))
    log("  ［省メモリの書き出し（--lean-export）：16 bit の復号は export_package と%s］" % ("同じ" if same else "違うので作り直した"))
    return deq_hi, deq_fine


def _install_lean_export():
    import ds27_generate as G27
    import ds28r01e_generate as GE
    G27.export_package = _export_package27_lean
    GE.export_lo = _export_lo_lean


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    t0 = time.time()
    lean = False
    if "--lean-export" in sys.argv:
        sys.argv.remove("--lean-export")
        lean = True
        _install_lean_export()
    if "--p-off" in sys.argv:
        k = sys.argv.index("--p-off")
        os.environ["DS28P_OFF"] = sys.argv[k + 1]
        del sys.argv[k:k + 2]
    log_only = False
    if "--log-only" in sys.argv:
        # 包みは書けたが、この記録（ds28p_generate_log.json）だけが書けなかった時に、包みを作り直さずに記録だけを書く（仕上げ28 の回復：
        # 書き出しの省メモリの版を足した時に sha256_file の定義を消し、G_p28rec の最後で止まった）。記録に log_only = true と書く
        sys.argv.remove("--log-only")
        log_only = True
    argv = sys.argv[1:]
    if not log_only:
        GEN.main()
    out = argv[argv.index("--out") + 1] if "--out" in argv else "Unity/Build/Design/28R01F"
    name = argv[argv.index("--name") + 1]
    kdir = argv[argv.index("--kstar") + 1]
    pkg = os.path.join(REPO, out, name) if not os.path.isabs(out) else os.path.join(out, name)
    import ds28p_model as MP
    g = MP.Generator(kstar_dir=kdir, off=p_off(), defer_no_rebound=True)
    rec = dict(schema="GreatWave.ds28p.generate_log/1", package=os.path.relpath(pkg, REPO).replace("\\", "/"), kstar=kdir,
               p_on=g.p_on, p_params={n: g.RP[n] for n in MP.P_NAMES}, p_info=g.p_info, p_base_shas=g.p_base_shas,
               files={f: sha256_file(os.path.join(HERE, f)) for f in P_FILES},
               p_off=list(p_off()), command="py -3.10 -B Tools/GWWaveGen/ds28p/ds28p_generate.py " + " ".join(argv) + ((" --p-off " + ",".join(p_off())) if p_off() else "") + (" --lean-export" if lean else ""), seconds=round(time.time() - t0, 1),
               lean_export=lean, log_only=log_only,
               note_ja="試行F の生成の記録（ds28r01f_generate_log.json）は、ds28r01f_generate.py がそのまま書いた（子のプロセスの生成器だけを ds28p に差し替えた）")
    with open(os.path.join(pkg, "ds28p_generate_log.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("ds28p", rec["p_on"], rec["p_info"]["far_hook_earlier_rows"][:3], "…", flush=True)


if __name__ == "__main__":
    main()
