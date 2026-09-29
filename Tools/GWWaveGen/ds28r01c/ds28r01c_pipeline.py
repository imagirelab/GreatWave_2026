# -*- coding: utf-8 -*-
"""設計28修正01 試行C：生成の後の検査を並べて走らせる（時間曲線 → 関門（既定・代案・V80 の表・Q13 の段階の表）と試行A の独立の検査器）。

生成（ds28r01c_generate.py）は先に済ませておく。関門の包み（試行A の ds28r01_gates.py：ds27_gates.py＋ds28_gates_extra.py を変えずに
import する）と、生成器から独立の検査器（試行A の ds28r01_overlap.py）はどちらも読むだけで使う（試行B の ds28r01b_pipeline.py と同じ並び）。
比べのための時間曲線（規則のまま 0.7 倍）も作る（<根>/warps/）。「V80 の表」は試行B の timewarp_default_V80.json をそのまま使う。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_pipeline.py [--variants C1,C2] [--skip-q13] [--root <出力の根>]
出力：<根>/<変種>/gates/{default,alt,v80warp,default_q13}.json・overlap/overlap_default.json、ログは <根>/logs/。
"""
import argparse
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = ["py", "-3.10", "-B"]
T = "Tools/GWWaveGen"
V80_WARP = "%s/ds28r01b/timewarp_default_V80.json" % T


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
    ap.add_argument("--variants", default="C1,C2")
    ap.add_argument("--skip-q13", action="store_true")
    ap.add_argument("--root", default="Unity/Build/Design/28R01C")
    ap.add_argument("--tw-only", action="store_true")
    a = ap.parse_args()
    vs = a.variants.split(",")
    root = a.root.replace("\\", "/")
    B = os.path.join(REPO, root)
    logd = os.path.join(B, "logs")
    os.makedirs(logd, exist_ok=True)
    os.makedirs(os.path.join(B, "warps"), exist_ok=True)
    tw = []
    default_root = root.rstrip("/") == "Unity/Build/Design/28R01C"

    def twd_path(v):
        # 既定の根（最終の版）は Tools/GWWaveGen/ds28r01c/timewarp_default_<変種>.json、修正の途中の根は <根>/warps/
        return "%s/ds28r01c/timewarp_default_%s.json" % (T, v) if default_root else "%s/warps/timewarp_default_%s.json" % (root, v)
    for v in vs:
        pk = "%s/%s/art_on" % (root, v)
        tw.append(("tw_%s" % v, PY + ["%s/ds28r01c/ds28r01c_timewarp.py" % T, "--variant", v, "--package", pk, "--out", twd_path(v)]))
        tw.append(("tw_r07_%s" % v, PY + ["%s/ds28r01c/ds28r01c_timewarp.py" % T, "--variant", v, "--package", pk, "--r0", "0.7",
                                          "--out", "%s/warps/tw_r07_%s.json" % (root, v)]))
    if not os.path.isfile(os.path.join(B, "warps", "tw_r07_V80.json")):
        tw.append(("tw_r07_V80", PY + ["%s/ds28r01c/ds28r01c_timewarp.py" % T, "--package", "Unity/Build/Design/28R01B/V80/art_on", "--tag", "V80",
                                       "--r0", "0.7", "--out", "%s/warps/tw_r07_V80.json" % root]))
    bad = run_parallel(tw, logd)
    if bad:
        raise SystemExit("時間曲線で失敗：%s" % bad)
    if a.tw_only:
        return
    jobs = []
    for v in vs:
        pk = "%s/%s/art_on" % (root, v)
        sea = pk + "/ds27_sea.npz"
        twd = twd_path(v)
        twa = "%s/ds27/timewarp_alt.json" % T
        os.makedirs(os.path.join(B, v, "gates"), exist_ok=True)
        os.makedirs(os.path.join(B, v, "overlap"), exist_ok=True)
        g = PY + ["%s/ds28r01/ds28r01_gates.py" % T, "--package", pk, "--sea", sea]
        jobs.append(("gates_%s_default" % v, g + ["--timewarp", twd, "--out", "%s/%s/gates/default.json" % (root, v), "--table", "design26"]))
        jobs.append(("gates_%s_alt" % v, g + ["--timewarp", twa, "--out", "%s/%s/gates/alt.json" % (root, v), "--table", "design26"]))
        jobs.append(("gates_%s_v80warp" % v, g + ["--timewarp", V80_WARP, "--out", "%s/%s/gates/v80warp.json" % (root, v), "--table", "design26"]))
        if not a.skip_q13:
            jobs.append(("gates_%s_default_q13" % v, g + ["--timewarp", twd, "--out", "%s/%s/gates/default_q13.json" % (root, v), "--table", "q13"]))
        jobs.append(("overlap_%s" % v, PY + ["%s/ds28r01/ds28r01_overlap.py" % T, "--package", pk, "--tw-default", twd, "--tw-alt", twa,
                                             "--out", "%s/%s/overlap/overlap_default.json" % (root, v),
                                             "--label", "設計28修正01 試行C %s 既定（art_on）" % v]))
    bad = run_parallel(jobs, logd)
    if bad:
        raise SystemExit("失敗：%s" % bad)


if __name__ == "__main__":
    main()
