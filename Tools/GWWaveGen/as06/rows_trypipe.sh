#!/usr/bin/env bash
# 美術の見本06 の段の行：試しの設計で、静止のメッシュまで作り（rows_pipeline.sh）、帯の座標 w の伸び（G1）を数える。
# 使い方：bash Tools/GWWaveGen/as06/rows_trypipe.sh <名前>   設計は Unity/Build/Polish/sample06/rows/try/<名前>.json
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
R=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/rows
N=$1
py -3.10 -c "
import json; d=json.load(open('$R/try/$N.json',encoding='utf-8')); d['write_candidate']=True
json.dump(d,open('$R/try/${N}_w.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
bash Tools/GWWaveGen/as06/rows_pipeline.sh $R/try/${N}_pipe $R/try/${N}_w.json > $R/try/${N}_pipe.txt 2>&1
grep -v "^Mon" $R/try/${N}_pipe.txt | tr '\n' ' '; echo
py -3.10 -B Tools/GWWaveGen/as06/rows_stretch.py $R/try/${N}_pipe/mesh/hero_smooth_as06r.json
