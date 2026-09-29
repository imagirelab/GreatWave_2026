# -*- coding: utf-8 -*-
"""設計28修正01 試行C：生成器（ds28r01c_model.py）から keypose パッケージを書き出す（設計27・28・試行B と同じ書式）。

パッケージの書式・ファイル名は設計27 と同じ（ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin）なので、設計27 の Unity の
再生器と関門の検査器（ds27_gates.py・ds28_gates_extra.py）、試行A の独立の検査器（ds28r01_overlap.py）がそのまま読む。

使い方（リポジトリの根で。1 回 約 25〜30 分。変種ごとに別のプロセスで並べて走らせてよい）：
    py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_generate.py --variant C1            # → Unity/Build/Design/28R01C/C1/art_on
    任意：--name <名前> --out <フォルダー> --no-check --no-sea --overrides <json>
出力（Git 対象外）：<out>/<名前>/ に ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin（決定的）、ds27_sea.npz、ds27_checks.json、
ds28r01c_generate_log.json（時間・唇先の運び・巻き下がり・放出の表などの記録）。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # 行列積の和の順を固定し、同じバイトを保つ
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
DSB = os.path.abspath(os.path.join(HERE, "..", "ds28r01b"))
for p in (HERE, DSB, DS28, DS27):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402
import ds28_generate as G28  # noqa: E402
import ds28r01b_generate as GB  # noqa: E402
import ds28r01c_model as MC  # noqa: E402

REPO = MC.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28R01C")
C_FILES = ["ds28r01c_model.py", "ds28r01c_generate.py", "ds28r01c_params.json"]
LAUNCH_C = GB.LAUNCH_C


def code_sha():
    out = GB.code_sha()
    for f in C_FILES:
        out["ds28r01c/%s" % f] = MD.sha256_file(os.path.join(HERE, f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="C1", choices=list(MC.VARIANTS))
    ap.add_argument("--version", default="art_on", choices=["art_on"])
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    ap.add_argument("--overrides", default="", help="ds28r01c_params.json への上書き（JSON。記録に残る）")
    a = ap.parse_args()
    t0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    name = a.name or os.path.join(a.variant, a.version)
    ov = json.loads(a.overrides) if a.overrides else None
    log("設計28修正01 試行C 生成：変種 %s（試行B の V80 ＋ ds_lip_curl_with_extension）、版 %s、上書き %s → %s" % (a.variant, a.version, ov or "なし", name))
    g = MC.Generator(a.version, curl_variant=a.variant, log=log, c_overrides=ov)
    log("生成器の準備 %.0f s（%s）" % (time.time() - t0, g.variant))
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(a.out, name)
    rec, deq = G28.export_package(g, B, outdir, log)
    rec["number"] = "設計28修正01 試行C"
    rec["generator"]["code"] = ("Tools/GWWaveGen/ds28r01c/ds28r01c_model.py（試行B の V80 ＋ ds_lip_curl_with_extension。変種 %s、%s）"
                                % (a.variant, g.variant))
    rec["generator"]["code_sha256"] = code_sha()
    rec["tstar"]["note_ja"] = "最後の層（τ = 0）は、入れた版では K*（26修正01）そのもの（量子化の差だけ）。"
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    vr = dict(dir=G27.rel(outdir), version=a.version, curl_variant=a.variant, variant=g.variant, overrides=ov,
              curl_params=g.VC, curl_common=g.RC["lip_curl_with_extension"],
              switches=dict(g.sw, ds_crest_tower=g.crest_tower, ds_undercut_kstar=g.undercut_kstar, ds_lip_carry=g.lip_carry,
                            ds_claws_follow_lip=g.claws_follow, ds_lip_curl_with_extension=g.curl_on),
              layers=rec["layers"], pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"],
              keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"])
    try:
        rows = sorted(set(int(np.argmin(np.abs(g.K.c - c))) for c in LAUNCH_C) & set(g.lip.keys()))
        vr["lip_launch"] = g.launch_table(rows)
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
                  command="py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28r01c_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
