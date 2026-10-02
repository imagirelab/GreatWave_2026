#!/usr/bin/env bash
# 仕上げ33修正02 修正の回 2：採る状態の評価器・関門・数（pl33r01/r01_run_eval.sh を写し、出力を Build/Polish/33r02 の下、前を仕上げ33修正01（33r01/fix01）にしたもの）。
# 重い numpy の処理は 1 つずつ。
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
S=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r02
F1=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/fix01
T1=Tools/GWWaveGen/pl33r01
T=Tools/GWWaveGen/pl33r02
R=$S/r_final
mkdir -p $S/measure $S/logs
date
py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene $R --kstar rec > $R/regress.log 2>&1; echo regress $?
for c in line line_noclaws noline noline_noclaws; do
  py -3.10 -B Tools/PaintingTruth/evaluate.py --render $R/full/painting_t120_off.png --ids $R/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $R/eval23/off_$c --name off_$c > $R/eval23_off_$c.log 2>&1; echo eval $c $?
done
py -3.10 -B $T1/sweep_gates.py --before-run $F1/r_fix01 --after-run $R --out $S/measure > $S/logs/final_gates.txt 2>&1; echo gates $?
py -3.10 -B $T1/sweep_measure.py --before-run $F1/r_fix01 --before-claws $F1/claws --after-run $R --after-claws $S/claws --out $S/measure > $S/logs/final_measure.txt 2>&1; echo measure $?
py -3.10 -B $T1/sweep_overlay.py --after-run $R --after-claws $S/claws --out $S/measure > $S/logs/final_overlay.txt 2>&1; echo overlay $?
py -3.10 -B Tools/GWWaveGen/pl33/pl33f_measure.py --fix-run $R --fix-claws $S/claws --build-run $F1/r_fix01 --build-claws $F1/claws --out $S/measure/pl33f_measure_r02.json > $S/logs/final_pl33f_measure.txt 2>&1; echo pl33f_measure $?
py -3.10 -B $T1/r01_quick.py --run $R --claws $S/claws --out $S/measure/r01_quick_r02.json > $S/logs/final_quick.txt 2>&1; echo quick $?
py -3.10 -B $T1/r01_measure.py --claws Unity/Build/Polish/33/fix02/claws --claws $F1/claws --claws $S/claws --out $S/measure/r01_measure.json > $S/logs/final_r01_measure.txt 2>&1; echo r01_measure $?
py -3.10 -B $T/r02_seatfan.py --claws $F1/claws --run $F1/r_fix01 --name before_r01 --claws $S/claws --run $R --name after_r02 --out $S/measure/r02_seatfan.json > $S/logs/final_seatfan.txt 2>&1; echo seatfan $?
py -3.10 -B $T/r02_quick.py --run $F1/r_fix01 --claws $F1/claws --out $S/measure/r02_quick_before_r01.json > $S/logs/final_r02quick_before.txt 2>&1; echo r02quick_before $?
py -3.10 -B $T/r02_quick.py --run $R --claws $S/claws --out $S/measure/r02_quick_after.json > $S/logs/final_r02quick_after.txt 2>&1; echo r02quick_after $?
date
