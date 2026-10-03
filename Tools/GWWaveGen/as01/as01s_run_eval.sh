#!/usr/bin/env bash
# 美術の見本01（Q29）組み立て：見本 A・B（爪あり）の原画視点の評価器 23（線あり・なし × 爪あり・なし）と形の関門（pl28u_regress → sweep_gates）。
# 前（採用）＝ 仕上げ33修正01 の描画 Build/Polish/33r01/fix01/r_fix01、CP1・26修正01 は sweep_gates.py の表の値。重い numpy の処理は 1 つずつ。
# 入力：as01s_run_render.sh <A|B> <A|B> views,tt,full,t28 の出力。出力：Build/Polish/sample01/assemble/<A|B>/eval23・pl28u_regress.json、assemble/measure/
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
AS=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/assemble
mkdir -p $AS/measure $AS/logs
date
for S in ${SAMPLES:-A B}; do   # 改善の回 1：SAMPLES="A1 B1"
  R=$AS/$S
  py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene $R --kstar rec > $AS/logs/regress_$S.log 2>&1; echo regress $S $?
  for c in line line_noclaws noline noline_noclaws; do
    py -3.10 -B Tools/PaintingTruth/evaluate.py --render $R/full/painting_t120_off.png --ids $R/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $R/eval23/off_$c --name off_$c > $AS/logs/eval23_${S}_$c.log 2>&1; echo eval $S $c $?
  done
  py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --after-run $R --out $AS/measure/gates_$S > $AS/logs/gates_$S.txt 2>&1; echo gates $S $?
done
date
