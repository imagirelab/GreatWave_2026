# -*- coding: utf-8 -*-
"""設計28修正01：生成器（ds28r01_model.py）から keypose パッケージを書き出す（設計28 の ds28_generate.py・ds28_physoff.py と同じ書式）。

パッケージの書式・ファイル名は設計27 と同じ（ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin）なので、設計27 の Unity の
再生器（Unity/Assets/GreatWave/Design27/）と関門の検査器（ds27_gates.py・ds28_gates_extra.py）がそのまま読む。

使い方（リポジトリの根で。1 回 約 12〜14 分）：
    py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_generate.py --version art_on            # 設計28修正01 の既定（15 個の誘導をすべて入れる）
    py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_generate.py --version art_off           # 15 個すべて切る（設計28 の切った版＝物理だけと同じ動き）
    任意：--name <名前> --out <フォルダー>（既定 Unity/Build/Design/28R01）--no-check --no-sea --rise-overlap 0|1 --switches ds_claws=0,...
出力（Git 対象外）：Unity/Build/Design/28R01/<名前>/ に ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin（決定的：同じ入力で同じバイト）、
ds27_sea.npz、ds27_checks.json、ds28r01_generate_log.json（時間・唇先の打ち出しの表などの記録）。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # 行列積の和の順を固定し、同じバイトを保つ
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
for p in (HERE, DS28, DS27):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402
import ds28_generate as G28  # noqa: E402
import ds28_physoff as PO  # noqa: E402
import ds28r01_model as MR  # noqa: E402

REPO = MR.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
R01_FILES = ["ds28r01_model.py", "ds28r01_generate.py", "ds28r01_params.json"]


def code_sha():
    out = PO.code_sha()
    for f in R01_FILES:
        out["ds28r01/%s" % f] = MD.sha256_file(os.path.join(HERE, f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="art_on", choices=["art_on", "art_off"])
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    ap.add_argument("--rise-overlap", default="", help="0|1：ds_rise_overlap だけを版の既定から変える")
    ap.add_argument("--switches", default="", help="設計28 の 12 個の切り替えの上書き（例 ds_claws=0）")
    a = ap.parse_args()
    t0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    name = a.name or a.version
    sw = G28.parse_switches(a.switches)
    ro = None if a.rise_overlap == "" else bool(int(a.rise_overlap))
    log("設計28修正01 生成：版 %s、ds_rise_overlap %s、切り替えの上書き %s → %s" % (a.version, "版の既定" if ro is None else ro, sw or "なし", name))
    g = MR.Generator(a.version, log=log, switches=sw or None, rise_overlap=ro)
    log("生成器の準備 %.0f s（%s）" % (time.time() - t0, g.variant))
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(a.out, name)
    rec, deq = G28.export_package(g, B, outdir, log)
    rec["number"] = "設計28修正01"
    rec["generator"]["code"] = ("Tools/GWWaveGen/ds28r01/ds28r01_model.py（ds28_physoff.Generator＋ds_rise_overlap。版 %s、%s）" % (a.version, g.variant))
    rec["generator"]["code_sha256"] = code_sha()
    rec["tstar"]["note_ja"] = ("最後の層（τ = 0）は、入れた版では K*（26修正01）そのもの（量子化の差だけ）。切った版（物理の頂の高さ）は K* ではない（P14）。"
                               if a.version == "art_on" else "切った版（物理の頂の高さ）。最後の層（τ = 0）は K* ではない（P14）。")
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    tw = {k: dict(path=G27.rel(p), sha256=MD.sha256_file(p)) for k, p in (("default", os.path.join(HERE, "timewarp_default.json")),
                                                                        ("alt", os.path.join(DS27, "timewarp_alt.json"))) if os.path.isfile(p)}
    vr = dict(dir=G27.rel(outdir), version=a.version, variant=g.variant,
              switches=dict(g.sw, ds_crest_tower=g.crest_tower, ds_undercut_kstar=g.undercut_kstar, ds_rise_overlap=g.rise_overlap),
              layers=rec["layers"], pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"],
              keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"])
    try:
        vr["lip_launch"] = g.launch_table([int(g.K.main_row), 192])
    except Exception as e:  # 記録だけ（パッケージには影響しない）
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
                  command="py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), timewarp=tw, result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28r01_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
