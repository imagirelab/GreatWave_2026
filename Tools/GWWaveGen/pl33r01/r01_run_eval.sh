#!/usr/bin/env bash
# 仕上げ33修正01 修正の回 1：採る状態の評価器・関門・数（記録の部で Unity/Build/Polish/33r01/fix01/run_eval.sh を写したもの。2 行目のこの説明のほかは同じ。変種の sweep/run_final.sh の eval・measure を写し、出力を fix01 の下にしたもの）。重い numpy の処理は 1 つずつ。
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
S=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/fix01
SW=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/sweep
T=Tools/GWWaveGen/pl33r01
R=$S/r_fix01
mkdir -p $S/measure
date
py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene $R --kstar rec > $R/regress.log 2>&1; echo regress $?
for c in line line_noclaws noline noline_noclaws; do
  py -3.10 -B Tools/PaintingTruth/evaluate.py --render $R/full/painting_t120_off.png --ids $R/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $R/eval23/off_$c --name off_$c > $R/eval23_off_$c.log 2>&1; echo eval $c $?
done
py -3.10 -B $T/sweep_gates.py --after-run $R --out $S/measure > $S/logs/final_gates.txt 2>&1; echo gates $?
py -3.10 -B $T/sweep_gates.py --before-run $SW/r_final --after-run $R --out $S/measure/vs_sweep > $S/logs/final_gates_vs_sweep.txt 2>&1; echo gates_vs_sweep $?
py -3.10 -B $T/sweep_measure.py --after-run $R --after-claws $S/claws --out $S/measure > $S/logs/final_measure.txt 2>&1; echo measure $?
py -3.10 -B $T/sweep_overlay.py --after-run $R --after-claws $S/claws --out $S/measure > $S/logs/final_overlay.txt 2>&1; echo overlay $?
py -3.10 -B Tools/GWWaveGen/pl33/pl33f_measure.py --fix-run $R --fix-claws $S/claws --build-run Unity/Build/Polish/33/fix02/r_fix02 --build-claws Unity/Build/Polish/33/fix02/claws --out $S/measure/pl33f_measure_fix01.json > $S/logs/final_pl33f_measure.txt 2>&1; echo pl33f_measure $?
py -3.10 -B $T/r01_quick.py --run $R --claws $S/claws --out $S/measure/r01_quick.json > $S/logs/final_quick.txt 2>&1; echo quick $?
py -3.10 -B $T/r01_quick.py --geo-only --claws $SW/claws --out $S/measure/r01_quick_geo_sweep.json > $S/logs/final_quick_sweep.txt 2>&1; echo quick_sweep $?
py -3.10 -B $T/r01_quick.py --geo-only --claws Unity/Build/Polish/33/fix02/claws --out $S/measure/r01_quick_geo_pl33.json > $S/logs/final_quick_pl33.txt 2>&1; echo quick_pl33 $?
py -3.10 -B $T/r01_measure.py --claws Unity/Build/Polish/33/fix02/claws --claws $SW/claws --claws $S/claws --out $S/measure/r01_measure.json > $S/logs/final_r01_measure.txt 2>&1; echo r01_measure $?
date
