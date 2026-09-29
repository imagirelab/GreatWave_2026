# -*- coding: utf-8 -*-
"""設計28修正01 試行D：生成の後の検査を並べて走らせる（関門（既定の時間曲線・代案・Q13 の段階の表）・独立の検査器・目標の検査器・P20）。

生成（ds28r01d_generate.py）は先に済ませておく。関門は ds28r01d_gates.py（試行A の包み ds28r01_gates.py と独立の検査器
ds28r01_overlap.py を、変えずに、--kstar の K* で走らせる）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_pipeline.py [--tag D] [--kstar Unity/Build/Design/28R01D/kstar_foot]
      [--root Unity/Build/Design/28R01D] [--skip-p20] [--skip-review]
出力：<根>/<tag>/gates/{default,alt,default_q13}.json・overlap/overlap_default.json、<根>/review/review_<tag>.json、<根>/p20/*.json、ログは <根>/logs/。
"""
import argparse
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
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
    ap.add_argument("--tag", default="D")
    ap.add_argument("--kstar", default="Unity/Build/Design/28R01D/kstar_foot")
    ap.add_argument("--root", default="Unity/Build/Design/28R01D")
    ap.add_argument("--warp", default="%s/ds28r01d/timewarp_default_D.json" % T)
    ap.add_argument("--carry-sigma", default="-3.7")
    ap.add_argument("--skip-p20", action="store_true")
    ap.add_argument("--skip-review", action="store_true")
    ap.add_argument("--skip-gates", action="store_true")
    a = ap.parse_args()
    root = a.root.replace("\\", "/")
    B = os.path.join(REPO, root)
    logd = os.path.join(B, "logs")
    os.makedirs(logd, exist_ok=True)
    tag = a.tag
    pk = "%s/%s/art_on" % (root, tag)
    sea = pk + "/ds27_sea.npz"
    twa = "%s/ds27/timewarp_alt.json" % T
    jobs = []
    if not a.skip_gates:
        for sub in ("gates", "overlap"):
            os.makedirs(os.path.join(B, tag, sub), exist_ok=True)
        g = PY + ["%s/ds28r01d/ds28r01d_gates.py" % T, "--kstar", a.kstar, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("gates_%s_default" % tag, g + ["--timewarp", a.warp, "--out", "%s/%s/gates/default.json" % (root, tag), "--table", "design26"]))
        jobs.append(("gates_%s_alt" % tag, g + ["--timewarp", twa, "--out", "%s/%s/gates/alt.json" % (root, tag), "--table", "design26"]))
        jobs.append(("gates_%s_default_q13" % tag, g + ["--timewarp", a.warp, "--out", "%s/%s/gates/default_q13.json" % (root, tag), "--table", "q13"]))
        jobs.append(("overlap_%s" % tag, PY + ["%s/ds28r01d/ds28r01d_gates.py" % T, "--kstar", a.kstar, "--tool", "overlap", "--",
                                              "--package", pk, "--tw-default", a.warp, "--tw-alt", twa,
                                              "--out", "%s/%s/overlap/overlap_default.json" % (root, tag),
                                              "--label", "設計28修正01 試行D %s 既定（art_on）" % tag]))
    if not a.skip_review:
        jobs.append(("review_%s" % tag, PY + ["%s/ds28r01d/ds28r01d_review.py" % T, "--tags", "C1,%s" % tag,
                                             "--tag-spec", "%s=%s|%s|%s|%s" % (tag, pk, a.warp, a.kstar, a.carry_sigma),
                                             "--out", "%s/review/review_%s.json" % (root, tag)]))
    if not a.skip_p20:
        for nm in ("lean_pace", "row_timing", "near_trough", "row_smooth", "back_hold", "kstar_foot_rebake", "timewarp"):
            jobs.append(("p20_%s" % nm, PY + ["%s/ds28r01d/ds28r01d_p20.py" % T, "--name", nm, "--kstar", a.kstar,
                                               "--out", "%s/p20/%s.json" % (root, nm)]))
    bad = run_parallel(jobs, logd)
    if bad:
        raise SystemExit("失敗：%s" % bad)


if __name__ == "__main__":
    main()
