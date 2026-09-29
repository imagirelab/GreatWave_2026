# -*- coding: utf-8 -*-
"""設計29修正01：設計28修正01 の新しい動き（試行F_final、K*′）の表示用サーフェスを、設計29 と同じ検査器で、精度の層つきの復号で測る。

設計29 §3 の規則のとおり、原版 = そのパッケージ自身の K*′ の格子（240 × 400）。検査器は設計29 のもの（ds29_qa.py・ds29_blender_qa.py・
ds29_review_checks.py・ds29_review_blender.py）をファイルを変えずに使い、ds29r01_common.setup() で K* を K*′ に、復号を 16 bit ＋ 精度の層に
差し替える（--decode hi で設計27〜29 の再生器と同じ 16 bit だけの読みも測れる。量子化の影響の比べ）。

サブコマンド（リポジトリの根で。出力の既定は Git 対象外の Unity/Build/Design/29R01/measure/）
  qa      静止の網の読み（設計29 §3・美術優先26 と同じ）：τ −3〜0 s の 0.1 s ごと＋段階の 6 コマ（設計29 と同じ τ）＝ 36 コマの
          位相・折れ返り・断面の自己交差・唇先の厚さ（≥ 0.3 m）と、Blender の座席 v1 の射線 5 万本 × コマ（穴・開いた背面・切断端）・
          BVH の 3 次元の自己交差（頂点を共有する組を除き、両方の面 ≥ 5 mm）。あわせて 30 Hz の通し（面の反転・二階差分・辺）。
          py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py qa [--decode fine|hi] [--package 名前=<包み>] [--out …]
  strict  厳しい読み（設計29 のレビュー対応）：30 Hz の全コマ（τ −12〜0 s、361 コマ）で、頂点を 1 つ共有する組の貫通・折れ返り
          （ds29_review_checks.py mesh）と、BVH の自己交差（ds29_review_checks.py blender）。
          py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py strict [--decode fine|hi] [--only mesh|blender]
共通：--kstar <K* のフォルダー>（既定 Unity/Build/Design/28R01F/kstar_final）。
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds29r01_common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["qa", "strict"])
    ap.add_argument("--decode", default="fine", choices=["fine", "hi"])
    ap.add_argument("--kstar", default=C.DEFAULT_KSTAR)
    ap.add_argument("--package", default="F_final=" + C.DEFAULT_PACKAGE)
    ap.add_argument("--ref", default=None, help="qa：波頭の欠落を比べる基準の包み（軽量版を測る時に原版を渡す）")
    ap.add_argument("--only", default="", help="strict：mesh か blender だけ")
    ap.add_argument("--no-blender", action="store_true", help="qa：Blender（射線・BVH）を回さない")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    Q = C.setup(a.kstar, a.decode)
    name, pkg = a.package.split("=", 1)
    tag = "%s_%s" % (name, a.decode)
    t0 = time.time()
    if a.cmd == "qa":
        out = a.out or os.path.join(C.OUT_ROOT, "measure", "qa_%s" % tag)
        argv = [Q.__file__, "--package", "%s=%s" % (tag, os.path.join(C.REPO, pkg)), "--out", out,
                "--summary-name", "ds29r01_qa_%s" % tag,
                "--title", "設計29修正01：表示用サーフェスの検査（ds29_qa、K*′、復号 %s）" % a.decode]
        if a.ref:
            argv += ["--ref", os.path.join(C.REPO, a.ref)]
        if not a.no_blender:
            argv += ["--blender"]
        sys.argv = argv
        print("[ds29r01] qa %s（K* = %s、復号 %s）" % (tag, C.STATE["kstar_src"], a.decode), flush=True)
        Q.main()
    else:
        import ds29_review_checks as R
        out = a.out or os.path.join(C.OUT_ROOT, "measure", "strict")
        for cmd in ("mesh", "blender"):
            if a.only and a.only != cmd:
                continue
            # 追う面は設計29 の行 185 の面（K* の番号）。K*′ では意味のない面なので、唇の近くの面を追う（記録のみ）
            sys.argv = [R.__file__, cmd, "--package", "%s=%s" % (tag, pkg), "--out", out, "--face", "183,200,1"]
            print("[ds29r01] strict %s %s（K* = %s、復号 %s）" % (cmd, tag, C.STATE["kstar_src"], a.decode), flush=True)
            R.main()
    print("[ds29r01] %s %s 終わり %.0f s" % (a.cmd, tag, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
