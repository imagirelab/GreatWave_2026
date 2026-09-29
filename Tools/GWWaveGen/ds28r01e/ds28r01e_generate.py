# -*- coding: utf-8 -*-
"""設計28修正01 試行E：生成器（ds28r01e_model.py）から keypose パッケージを書き出す（設計27 の書式に、後方互換の精度の層を足す）。

パッケージ（E3。後方互換の追加）：
  ds27_pos_rgba16.bin   設計27 と同じ（RGBA16 UNORM、全体の外接箱、刻み = bbox_size/65535 ≈ 1.7 mm、A = 65535）。古い再生器はこれだけを読む。
  ds27_pos_lo_rgba8.bin 追加（新）。RGBA8 UNORM（TextureFormat.RGBA32）、層 × 行 × 列 × 4 バイト。16 bit の丸めの残り
                        e = u − q（u = (位置 − bbox_min)/bbox_size·65535、q = round(u)、e ∈ [−0.5, 0.5]）を
                        lo = round((e + 0.5)·255)（0〜255）で持つ。A = 255。
                        新しい再生器の復号：位置 = bbox_min + (q + lo/255 − 0.5)/65535·bbox_size（刻み ≈ 6.6 µm、最大誤差 ≈ 3.3 µm）。
  ds27_keypose.json     設計27 の欄はそのまま（quantization_max_err_m も 16 bit だけの値。原画の関門と古い再生器の読み）。
                        足した欄：extensions ["pos_lo_rgba8/1"]、pos_lo_file・pos_lo_sha256・pos_lo_bytes・pos_lo_format_ja、
                        pos_precision{hi_step_mm, fine_step_mm, max_err_hi_m, max_err_fine_m}、gpu_estimate の fine の見積もり。
  Unity の再生器（Design27/29 の DS27KeyposePlayer・DS29KeyposePlayer）は変えない（古い書式のまま読める＝後方互換）。精度の層を
  読むのは 29修正01 の作業（記録：29修正01 への申し送り）。
その他は試行D の ds28r01d_generate.py と同じ（K* は --kstar、決定的、ds27_sea.npz、ds27_checks.json、ds28r01e_generate_log.json）。
ds27_checks.json の Hermite の再生の差は精度の層を足した位置（新しい再生器）で測り、16 bit だけの読み（古い再生器）との差の最大も記録する。

使い方（リポジトリの根で。1 回 約 25〜30 分）：
    py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_generate.py [--kstar Unity/Build/Design/28R01D/kstar_foot] [--name E/art_on]
        [--out Unity/Build/Design/28R01E] [--overrides <json>] [--off curl_lead,...] [--no-check] [--no-sea]
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # 行列積の和の順を固定し、同じバイトを保つ
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import functools  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c", "ds28r01d"):
    p = os.path.abspath(os.path.join(HERE, "..", sub))
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402
import ds28_generate as G28  # noqa: E402
import ds28r01d_generate as GD  # noqa: E402
import ds28r01e_model as ME  # noqa: E402

REPO = ME.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28R01E")
E_FILES = ["ds28r01e_model.py", "ds28r01e_generate.py", "ds28r01e_params.json", "ds28r01e_timewarp.py"]
LO_NAME = "ds27_pos_lo_rgba8.bin"


def code_sha():
    out = GD.code_sha()
    for f in E_FILES:
        out["ds28r01e/%s" % f] = MD.sha256_file(os.path.join(HERE, f))
    return out


def export_lo(rec, B, outdir, log):
    """16 bit の丸めの残りを RGBA8 で書き、細かい復号の位置（float64）を返す。rec（ds27_keypose.json の中身）に欄を足す。"""
    Xs = B.Xk
    lo = np.asarray(rec["bbox_min"], np.float64)
    size = np.asarray(rec["bbox_size"], np.float64)
    u = (Xs - lo) / size * 65535.0
    q = np.clip(np.round(u), 0, 65535)
    e = u - q
    ql = np.clip(np.round((e + 0.5) * 255.0), 0, 255).astype(np.uint8)
    L, nv, nu = Xs.shape[:3]
    buf = np.concatenate([ql, np.full((L, nv, nu, 1), 255, np.uint8)], -1)
    p = os.path.join(outdir, LO_NAME)
    buf.tofile(p)
    deq_hi = lo + q / 65535.0 * size
    deq_fine = lo + (q + ql.astype(np.float64) / 255.0 - 0.5) / 65535.0 * size
    e_hi = float(np.linalg.norm(deq_hi - Xs, axis=-1).max())
    e_fine = float(np.linalg.norm(deq_fine - Xs, axis=-1).max())
    rec["extensions"] = ["pos_lo_rgba8/1"]
    rec["pos_lo_file"] = LO_NAME
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
        LO_NAME, rec["pos_precision"]["fine_step_mm"], rec["pos_precision"]["hi_step_mm"], e_fine * 1000, e_hi * 1000))
    return deq_hi, deq_fine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kstar", default=None)
    ap.add_argument("--version", default="art_on", choices=["art_on"])
    ap.add_argument("--name", default="E/art_on")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--overrides", default="", help="ds28r01e_params.json への上書き（JSON。記録に残る）")
    ap.add_argument("--off", default="", help="切る名前（, 区切り。P20 の比べ用）")
    ap.add_argument("--nr-cache", default=None, help="（開発用）num_no_rebound_after_apex の格子の置き場。記録に残る")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    ov = json.loads(a.overrides) if a.overrides else None
    off = [s for s in a.off.split(",") if s]
    outd = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    log("設計28修正01 試行E 生成：K* %s、上書き %s、切り %s → %s" % (a.kstar or "既定", ov or "なし", off or "なし", a.name))
    kdir = a.kstar or ME.load_e()[0]["kstar"]["dir_default"]
    g = ME.Generator(a.version, kstar_dir=kdir, log=log, e_overrides=ov, off=off, no_rebound_cache=a.nr_cache)
    log("生成器の準備 %.0f s（%s）" % (time.time() - t0, g.variant))
    G27.stage_metrics = functools.partial(G27.stage_metrics, jE=int(g.jE))
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(outd, a.name)
    rec, deq16 = G28.export_package(g, B, outdir, log)
    deq_hi, deq_fine = export_lo(rec, B, outdir, log)
    assert float(np.abs(deq_hi - deq16).max()) < 1e-9
    rec["number"] = "設計28修正01 試行E"
    rec["generator"]["code"] = "Tools/GWWaveGen/ds28r01e/ds28r01e_model.py（試行D ＋ E1〜E6 の直し。%s）" % g.variant
    rec["generator"]["code_sha256"] = code_sha()
    rec["generator"]["summary"] = {k: (v if not isinstance(v, float) else G27.fnum(v, 6)) for k, v in g.summary().items()}
    rec["kstar"] = dict(dir=g.K.src["dir"], sha256=g.K.sha, landmarks=g.K.landmarks, landmarks_source=g.K.src["landmarks_source"],
                        trough_min_m=float(g.K.T_trough.min()),
                        note_ja="K* はフォルダーで渡した（ds28r01d_kstar.py）。平らな縁の y < 0 は谷として分けて動かし、t* では谷を含む K* そのもの")
    rec["tstar"]["note_ja"] = "最後の層（τ = 0）は、K*（%s。谷を含む）そのもの（量子化の差だけ）。" % g.K.src["dir"]
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    X0 = B.Xk[-1] + g.origin(0.0)[None, None, :]
    dK = np.linalg.norm(X0 - g.K.X, axis=-1)
    dG = np.linalg.norm(X0 - g.K.Xgwb, axis=-1)
    vr = dict(dir=G27.rel(outdir), version=a.version, variant=g.variant, overrides=ov, off=off, nr_cache=a.nr_cache,
              kstar=rec["kstar"], e_params=g.RE, e_on=g.e_on, d_params=g.RD, d_on=g.d_on, layers=rec["layers"], pos_sha256=rec["pos_sha256"],
              pos_lo_sha256=rec["pos_lo_sha256"], twhite_sha256=rec["twhite_sha256"],
              keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), pos_lo_mib=G27.fnum(rec["pos_lo_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"],
              quantization_max_err_m=rec["quantization_max_err_m"], pos_precision=rec["pos_precision"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"],
              tstar_vs_kstar_float_m=dict(max_vs_rows=float(dK.max()), max_vs_gwb=float(dG.max())),
              no_rebound=getattr(g, "_nr_stats", None), T_row_range=[float(g.T_row.min()), float(g.T_row.max())])
    try:
        rows = sorted(set(int(np.argmin(np.abs(g.K.c - c))) for c in GD.LAUNCH_C) & set(g.lip.keys()))
        vr["lip_launch"] = g.launch_table(rows)
    except Exception as e:  # 記録だけ
        vr["lip_launch_error"] = repr(e)
    if not a.no_sea:
        ps = G27.export_sea(g, B, outdir)
        vr["sea_npz"] = dict(path=G27.rel(ps), sha256=MD.sha256_file(ps))
    if not a.no_check:
        chk = G27.run_checks(g, B, deq_fine, log)
        # 16 bit だけの読み（古い再生器）：同じコマの Hermite の差 |H_hi − H_fine| の最大（誤差 ≤ 新しい読みの誤差 + これ）
        kn = B.knots
        n = int(np.floor(-g.tau_min * 30.0 + 1e-9))
        worst = 0.0
        for k in range(n + 1):
            t = round(-(n - k) / 30.0, 9)
            worst = max(worst, float(np.linalg.norm(B.herm(t, kn, deq_hi) - B.herm(t, kn, deq_fine), axis=-1).max()))
        chk["hermite_playback_err_m"]["note_ja"] = "量子化した節点（16 bit ＋ 精度の層、新しい再生器）の Hermite と解析の生成器の差（全頂点の最大）。30 Hz のコマと節点の間の中点"
        chk["hermite_playback_err_m"]["hi_only_minus_fine_max_m"] = worst
        chk["hermite_playback_err_m"]["hi_only_bound_m"] = float(chk["hermite_playback_err_m"]["max"]) + worst
        G27.dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
        vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
        vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
    vr["seconds"] = round(time.time() - t0, 1)
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28r01e_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
