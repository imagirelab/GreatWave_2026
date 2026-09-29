# -*- coding: utf-8 -*-
"""設計28修正01 試行B：生成の後の検査を並べて走らせる（時間曲線 → 関門（既定・代案、設計26 の段階の表と試行A の表）→ 独立の検査器）。

生成（ds28r01b_generate.py）は先に済ませておく。関門の包み（試行A の ds28r01_gates.py：ds27_gates.py＋ds28_gates_extra.py を変えずに
import する）と、生成器から独立の検査器（試行A の ds28r01_overlap.py、レビューで確かめられたもの）はどちらも読むだけで使う。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01b/ds28r01b_pipeline.py [--variants V80,V75,V70] [--skip-q13]
出力：Unity/Build/Design/28R01B/<変種>/gates/{default,alt,default_q13}.json・overlap/overlap_default.json、ログは logs/。
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Design", "28R01B")
PY = ["py", "-3.10", "-B"]
T = "Tools/GWWaveGen"


def run_parallel(jobs, log_dir):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    procs = []
    for name, cmd in jobs:
        lf = open(os.path.join(log_dir, name + ".log"), "w", encoding="utf-8")
        procs.append((name, subprocess.Popen(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, env=env), lf, time.time()))
    bad = []
    for name, p, lf, t0 in procs:
        rc = p.wait()
        lf.close()
        print("%-28s rc %d  %.0f s" % (name, rc, time.time() - t0), flush=True)
        if rc != 0:
            bad.append(name)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="V80,V75,V70")
    ap.add_argument("--skip-q13", action="store_true")
    a = ap.parse_args()
    vs = a.variants.split(",")
    logd = os.path.join(B, "logs")
    os.makedirs(logd, exist_ok=True)
    bad = run_parallel([("tw_%s" % v, PY + ["%s/ds28r01b/ds28r01b_timewarp.py" % T, "--variant", v]) for v in vs], logd)
    if bad:
        raise SystemExit("時間曲線で失敗：%s" % bad)
    jobs = []
    for v in vs:
        pk = "Unity/Build/Design/28R01B/%s/art_on" % v
        sea = pk + "/ds27_sea.npz"
        twd = "%s/ds28r01b/timewarp_default_%s.json" % (T, v)
        twa = "%s/ds27/timewarp_alt.json" % T
        os.makedirs(os.path.join(B, v, "gates"), exist_ok=True)
        os.makedirs(os.path.join(B, v, "overlap"), exist_ok=True)
        g = PY + ["%s/ds28r01/ds28r01_gates.py" % T, "--package", pk, "--sea", sea]
        jobs.append(("gates_%s_default" % v, g + ["--timewarp", twd, "--out", "Unity/Build/Design/28R01B/%s/gates/default.json" % v, "--table", "design26"]))
        jobs.append(("gates_%s_alt" % v, g + ["--timewarp", twa, "--out", "Unity/Build/Design/28R01B/%s/gates/alt.json" % v, "--table", "design26"]))
        if not a.skip_q13:
            jobs.append(("gates_%s_default_q13" % v, g + ["--timewarp", twd, "--out", "Unity/Build/Design/28R01B/%s/gates/default_q13.json" % v, "--table", "q13"]))
        jobs.append(("overlap_%s" % v, PY + ["%s/ds28r01/ds28r01_overlap.py" % T, "--package", pk, "--tw-default", twd, "--tw-alt", twa,
                                             "--out", "Unity/Build/Design/28R01B/%s/overlap/overlap_default.json" % v,
                                             "--label", "設計28修正01 試行B %s 既定（art_on）" % v]))
    bad = run_parallel(jobs, logd)
    if bad:
        raise SystemExit("失敗：%s" % bad)


if __name__ == "__main__":
    main()
