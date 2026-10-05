#!/usr/bin/env bash
# 仕上げ36：原画視点の評価器と形の関門（仕上げ33修正01 の r01_run_eval.sh の最初の 2 段を写し、出力を Build/Polish/36/<run> の下にしたもの）。
# pl28u_regress（t28_white＝爪なし・t28_claws＝爪あり の形の関門と色区の項目）と、評価器 23 の 4 組（線あり・なし × 爪あり・なし）。重い numpy の処理は 1 つずつ。
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
R=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/36/${1:-r_after}
date
py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene $R --kstar rec > $R/regress.log 2>&1; echo regress $?
for c in line line_noclaws noline noline_noclaws; do
  py -3.10 -B Tools/PaintingTruth/evaluate.py --render $R/full/painting_t120_off.png --ids $R/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $R/eval23/off_$c --name off_$c > $R/eval23_off_$c.log 2>&1; echo eval $c $?
done
date
