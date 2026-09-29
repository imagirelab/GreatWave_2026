# -*- coding: utf-8 -*-
"""設計28修正01 試行D：生成器（ds28r01d_model.py）から keypose パッケージを書き出す（設計27・28・試行B・C と同じ書式）。

パッケージの書式・ファイル名は設計27 と同じ（ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin）なので、設計27 の Unity の
再生器と関門の検査器がそのまま読む。K* はフォルダーで渡す（--kstar。*.gwb・*_rows.npz・*_meta.json）。K*′ ができたら、そのフォルダーを
渡して同じコマンドで作り直す（コードは変えない）。関門は ds28r01d_gates.py に同じ --kstar を渡す。

使い方（リポジトリの根で。1 回 約 30〜40 分）：
    py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_generate.py [--kstar Unity/Build/Design/28R01D/kstar_foot] [--name D/art_on]
        [--out Unity/Build/Design/28R01D] [--overrides <json>] [--off near_trough,...] [--no-check] [--no-sea]
出力（Git 対象外）：<out>/<name>/ に ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin（決定的）、ds27_sea.npz、ds27_checks.json、
ds28r01d_generate_log.json（K* の場所と SHA-256・目印の列・名前の付いた値の記録・時間）。
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
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c"):
    p = os.path.abspath(os.path.join(HERE, "..", sub))
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402
import ds28_generate as G28  # noqa: E402
import ds28r01c_generate as GC  # noqa: E402
import ds28r01d_model as MDD  # noqa: E402

REPO = MDD.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28R01D")
D_FILES = ["ds28r01d_model.py", "ds28r01d_kstar.py", "ds28r01d_generate.py", "ds28r01d_params.json", "ds28r01d_timewarp.py"]
LAUNCH_C = GC.LAUNCH_C


def code_sha():
    out = GC.code_sha()
    for f in D_FILES:
        out["ds28r01d/%s" % f] = MD.sha256_file(os.path.join(HERE, f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kstar", default=None)
    ap.add_argument("--version", default="art_on", choices=["art_on"])
    ap.add_argument("--name", default="D/art_on")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--overrides", default="", help="ds28r01d_params.json への上書き（JSON。記録に残る）")
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
    log("設計28修正01 試行D 生成：K* %s、上書き %s、切り %s → %s" % (a.kstar or "既定", ov or "なし", off or "なし", a.name))
    g = MDD.Generator(a.version, kstar_dir=a.kstar, log=log, d_overrides=ov, off=off, no_rebound_cache=a.nr_cache)
    log("生成器の準備 %.0f s（%s）" % (time.time() - t0, g.variant))
    # 設計27 の自前の段階の目安（記録のみ）は前の足の列を 394 と決め打ちしているので、この K* の j_E を渡す（ファイルは変えない）
    G27.stage_metrics = functools.partial(G27.stage_metrics, jE=int(g.jE))
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(outd, a.name)
    rec, deq = G28.export_package(g, B, outdir, log)
    rec["number"] = "設計28修正01 試行D"
    rec["generator"]["code"] = "Tools/GWWaveGen/ds28r01d/ds28r01d_model.py（試行C の C1 ＋ Q16・Q17 の動きの直し。%s）" % g.variant
    rec["generator"]["code_sha256"] = code_sha()
    rec["kstar"] = dict(dir=g.K.src["dir"], sha256=g.K.sha, landmarks=g.K.landmarks, landmarks_source=g.K.src["landmarks_source"],
                        trough_min_m=float(g.K.T_trough.min()),
                        note_ja="K* はフォルダーで渡した（ds28r01d_kstar.py）。平らな縁の y < 0 は谷として分けて動かし、t* では谷を含む K* そのもの")
    rec["tstar"]["note_ja"] = "最後の層（τ = 0）は、K*（%s。谷を含む）そのもの（量子化の差だけ）。" % g.K.src["dir"]
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    X0 = B.Xk[-1] + g.origin(0.0)[None, None, :]
    dK = np.linalg.norm(X0 - g.K.X, axis=-1)
    dG = np.linalg.norm(X0 - g.K.Xgwb, axis=-1)
    vr = dict(dir=G27.rel(outdir), version=a.version, variant=g.variant, overrides=ov, off=off, nr_cache=a.nr_cache,
              kstar=rec["kstar"], d_params=g.RD, d_on=g.d_on, layers=rec["layers"], pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"],
              keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"],
              tstar_vs_kstar_float_m=dict(max_vs_rows=float(dK.max()), max_vs_gwb=float(dG.max())),
              no_rebound=getattr(g, "_nr_stats", None), T_row_range=[float(g.T_row.min()), float(g.T_row.max())])
    try:
        rows = sorted(set(int(np.argmin(np.abs(g.K.c - c))) for c in LAUNCH_C) & set(g.lip.keys()))
        vr["lip_launch"] = g.launch_table(rows)
    except Exception as e:  # 記録だけ
        vr["lip_launch_error"] = repr(e)
    if not a.no_sea:
        ps = G27.export_sea(g, B, outdir)
        vr["sea_npz"] = dict(path=G27.rel(ps), sha256=MD.sha256_file(ps))
    if not a.no_check:
        chk = G27.run_checks(g, B, deq, log)
        G27.dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
        vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
        vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
    vr["seconds"] = round(time.time() - t0, 1)
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28r01d_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
