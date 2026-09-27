# -*- coding: utf-8 -*-
"""設計28：単発砕波の生成器（ds28_model.py）から keypose パッケージを書き出す（設計27 の ds27_generate.py を写して直したもの）。

パッケージの書式・ファイル名は設計27 と同じ（ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin）なので、設計27 の Unity の
再生器（Unity/Assets/GreatWave/Design27/）と関門の検査器（ds27_gates.py）がそのまま読む。時間曲線の表は設計27 の
Tools/GWWaveGen/ds27/timewarp_default.json・timewarp_alt.json をそのまま使う（ここでは書かない）。

使い方（リポジトリの根で。run_ds28.ps1 が同じことをする）：
    py -3.10 -B Tools/GWWaveGen/ds28/ds28_generate.py --version art_on [--out Unity/Build/Design/28] [--name art_on]
        [--switches ds_approach_kstar=0,ds_tube_shape=0] [--no-check] [--no-sea]
出力：Unity/Build/Design/28/<name>/（Git 対象外。name の既定は版の名前）：ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin
    （決定的：同じ入力で同じバイト）、ds27_sea.npz（任意）、ds27_checks.json、ds28_generate_log.json（時間などの記録）。
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
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds28_model as M8  # noqa: E402
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402

REPO = M8.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28")
CODE_FILES = [("ds28", "ds28_model.py"), ("ds28", "ds28_generate.py"), ("ds28", "ds28_params.json"),
              ("ds27", "ds27_model.py"), ("ds27", "ds27_generate.py"), ("ds27", "ds27_package.py"), ("ds27", "ds27_checks.py"),
              ("ds27", "ds27_params.json"), ("ds27", "timewarp_default.json"), ("ds27", "timewarp_alt.json")]
rel = G27.rel
fnum = G27.fnum
dump_json = G27.dump_json


def code_sha():
    out = {}
    for d, f in CODE_FILES:
        p = os.path.join(HERE if d == "ds28" else DS27, f)
        out["%s/%s" % (d, f)] = MD.sha256_file(p)
    return out


def export_package(g, B, outdir, log):
    """設計27 の export_package と同じ書式。記録の欄（number・generator）だけ設計28 に直す。"""
    rec, deq = G27.export_package(g, B, outdir, log)
    rec["number"] = "設計28"
    rec["variant"] = g.variant
    rec["generator"]["code"] = "Tools/GWWaveGen/ds28/ds28_model.py"
    rec["generator"]["code_sha256"] = code_sha()
    rec["generator"]["base_params_sha256"] = g.base_sha
    rec["generator"]["summary"] = {k: (v if not isinstance(v, float) else fnum(v, 6)) for k, v in g.summary().items()}
    rec["tstar"]["note_ja"] = ("最後の層（τ = 0）は、ds_lip_target_kstar・ds_approach_kstar・ds_tube_shape が入った版では K*（26修正01）そのもの"
                               "（量子化の差だけ）。切った版は K* ではない（P14）。")
    dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    return rec, deq


def parse_switches(s):
    out = {}
    for item in [x.strip() for x in (s or "").split(",") if x.strip()]:
        k, v = item.split("=")
        out[k.strip()] = bool(int(v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="art_on", choices=["art_on", "art_off"])
    ap.add_argument("--switches", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    sw = parse_switches(a.switches)
    name = a.name or a.version
    log("設計28 生成：版 %s、切り替えの上書き %s → %s" % (a.version, sw or "なし", name))
    g = M8.Generator(a.version, switches=sw or None, log=log)
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(a.out, name)
    rec, deq = export_package(g, B, outdir, log)
    tw = {k: dict(path=rel(os.path.join(DS27, "timewarp_%s.json" % k)), sha256=MD.sha256_file(os.path.join(DS27, "timewarp_%s.json" % k)))
          for k in ("default", "alt")}
    vr = dict(dir=rel(outdir), version=a.version, variant=g.variant, switches=g.sw, layers=rec["layers"], pos_sha256=rec["pos_sha256"],
              twhite_sha256=rec["twhite_sha256"], keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"])
    if not a.no_sea:
        ps = G27.export_sea(g, B, outdir)
        vr["sea_npz"] = dict(path=rel(ps), sha256=MD.sha256_file(ps))
    if not a.no_check:
        chk = G27.run_checks(g, B, deq, log)
        dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
        vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
        vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
    vr["seconds"] = round(time.time() - t0, 1)
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds28/ds28_generate.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), timewarp=tw, result=vr, log=logs)
    dump_json(os.path.join(outdir, "ds28_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
