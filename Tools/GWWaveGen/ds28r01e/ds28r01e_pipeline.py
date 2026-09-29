# -*- coding: utf-8 -*-
"""設計28修正01 試行E：生成の後の検査を並べて走らせる（関門（既定の時間曲線・代案・Q13 の段階の表）・独立の検査器・目標の検査器・P20）。

生成（ds28r01e_generate.py）は先に済ませておく。関門は試行D の包み ds28r01d_gates.py（試行A の ds28r01_gates.py と独立の検査器
ds28r01_overlap.py を、変えずに、--kstar の K* で走らせる。16 bit の読み＝古い再生器と同じ）。目標の検査器は ds28r01e_review.py
（C1・D・E を並べる。精度の層があれば足して読む）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_pipeline.py [--tag E] [--kstar Unity/Build/Design/28R01D/kstar_foot]
      [--root Unity/Build/Design/28R01E] [--skip-p20] [--skip-review] [--skip-gates]
出力：<根>/<tag>/gates/{default,alt,default_q13}.json（16 bit の読み）・{default,alt}_fine.json（精度の層の読み、記録）・overlap/overlap_default.json、<根>/review/review_<tag>.json、<根>/p20/*.json、ログは <根>/logs/。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "ds28r01d")))
import ds28r01d_pipeline as PD  # noqa: E402

REPO = PD.REPO
PY = PD.PY
T = "Tools/GWWaveGen"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="E")
    ap.add_argument("--kstar", default="Unity/Build/Design/28R01D/kstar_foot")
    ap.add_argument("--root", default="Unity/Build/Design/28R01E")
    ap.add_argument("--warp", default="%s/ds28r01e/timewarp_default_E.json" % T)
    ap.add_argument("--carry-sigma", default="-3.85")
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
        gf = PY + ["%s/ds28r01e/ds28r01e_gates.py" % T, "--kstar", a.kstar, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("gates_%s_default_fine" % tag, gf + ["--timewarp", a.warp, "--out", "%s/%s/gates/default_fine.json" % (root, tag), "--table", "design26"]))
        jobs.append(("gates_%s_alt_fine" % tag, gf + ["--timewarp", twa, "--out", "%s/%s/gates/alt_fine.json" % (root, tag), "--table", "design26"]))
        gs = PY + ["%s/ds28r01e/ds28r01e_gates.py" % T, "--stop-max", "1.3", "--kstar", a.kstar, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("gates_%s_default_fine_stop" % tag, gs + ["--timewarp", a.warp, "--out", "%s/%s/gates/default_fine_stop13.json" % (root, tag), "--table", "design26"]))
        jobs.append(("overlap_%s" % tag, PY + ["%s/ds28r01d/ds28r01d_gates.py" % T, "--kstar", a.kstar, "--tool", "overlap", "--",
                                              "--package", pk, "--tw-default", a.warp, "--tw-alt", twa,
                                              "--out", "%s/%s/overlap/overlap_default.json" % (root, tag),
                                              "--label", "設計28修正01 試行E %s 既定（art_on）" % tag]))
    if not a.skip_review:
        jobs.append(("review_%s" % tag, PY + ["%s/ds28r01e/ds28r01e_review.py" % T, "--tags", "C1,D,%s" % tag,
                                             "--tag-spec", "%s=%s|%s|%s|%s" % (tag, pk, a.warp, a.kstar, a.carry_sigma),
                                             "--out", "%s/review/review_%s.json" % (root, tag)]))
    if not a.skip_p20:
        for nm in ("lean_with_height", "tower_peak_off", "curl_lead", "back_hold_water", "timewarp"):
            jobs.append(("p20_%s" % nm, PY + ["%s/ds28r01e/ds28r01e_p20.py" % T, "--name", nm, "--kstar", a.kstar,
                                               "--out", "%s/p20/%s.json" % (root, nm)]))
    bad = PD.run_parallel(jobs, logd)
    if bad:
        raise SystemExit("失敗：%s" % bad)


if __name__ == "__main__":
    main()
