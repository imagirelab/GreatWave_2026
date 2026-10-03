#!/usr/bin/env bash
# 美術の見本02（Q30-2）組み立て（as02_run_eval.sh の写し。描画と記録の場所を Build/Polish/sample02/assemble へ替えただけ）：原画視点の評価器 23（線あり・なし × 爪あり・なし）と形の関門（pl28u_regress → sweep_gates）。
# 見本01 の as01s_run_eval.sh の写し（出力を Build/Polish/sample02/claws/render/<名前>/eval23・measure へ）。重い numpy の処理は 1 つずつ。
# 前（BEFORE）は見本01 の回 2（B2。A2 と空の被覆が画素で同じなので関門の値は共通、見本01 の記録の第 6 節）。
# 引数：描画のフォルダー名（render/ の下）を空白で区切って（既定 A_final B_ref_final）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
RB=${RB:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/assemble/render}   # 修正の回 1 は RB・LG で置き場を変える
LG=${LG:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/assemble/logs}
mkdir -p $RB/measure $LG
date
for S in ${@:-AS02B_A}; do
  R=$RB/$S
  py -3.10 -B Tools/GWWaveGen/as02/as02_gates.py --scene $R --kstar rec > $LG/regress_$S.log 2>&1; echo regress $S $?   # pl28u_regress.py の形の関門の部分だけ（267 の None で止まらないように）
  for c in line line_noclaws noline noline_noclaws; do
    py -3.10 -B Tools/PaintingTruth/evaluate.py --render $R/full/painting_t120_off.png --ids $R/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $R/eval23/off_$c --name off_$c > $LG/eval23_${S}_$c.log 2>&1; echo eval $S $c $?
  done
  py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run ${BEFORE:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/assemble/B2} --after-run $R --out $RB/measure/gates_$S > $LG/gates_$S.txt 2>&1; echo gates $S $?
done
date
