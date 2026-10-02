#!/usr/bin/env bash
# 仕上げ33修正01 修正の回 1：場面の写し・Play モードの確かめ・Release のビルド・プレイヤーの負荷（記録の部で Unity/Build/Polish/33r01/fix01/run_unity_steps.sh を写したもの。2 行目のこの説明のほかは同じ。変種の sweep/run_unity_steps.sh を写し、
# 場面を Polish33R01/Scenes/PL33R01_*.unity、出力を Build/Polish/33r01/{setup,release} と fix01 の下にしたもの）。Unity は 1 つずつ（unity.lock）。
# 引数：段（setup|playmode|release|players|all）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
S=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/fix01
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r01/r01_run_unity.ps1"
PL="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r01/r01_run_player.ps1"
EXE33=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33/release/player/GreatWave50.exe
st=${1:-all}
date
if [ $st = setup ] || [ $st = all ]; then
  $U -Method GreatWave.Polish33R01.EditorTools.PL33R01Setup.BuildScenes -Log setup -Extra "-pl33r01Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/setup" 2>&1 | grep -E "R01_UNITY"
  grep -E "PL33R01_SETUP_DONE|error CS|Exception" $S/logs/unity_r01_setup.log | head -5
fi
if [ $st = playmode ] || [ $st = all ]; then
  for sc in Release:400 SinglePlayback:120; do
    n=${sc%%:*}; lim=${sc##*:}
    $U -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_$n -Extra "-pl29Scene Assets/GreatWave/Polish33R01/Scenes/PL33R01_$n.unity -pl29Out $S/playmode_$n -pl29Limit $lim" 2>&1 | grep -E "R01_UNITY"
    grep -E "PL29_PLAYMODE|PLAYMODE_DONE|error CS" $S/logs/unity_r01_playmode_$n.log | head -3
  done
fi
if [ $st = release ] || [ $st = all ]; then
  $U -Method GreatWave.Polish33R01.EditorTools.PL33R01ReleaseBuild.BuildAll -Log release_build 2>&1 | grep -E "R01_UNITY"
  grep -E "PL33R01_RELEASE_BUILD_DONE|error CS|Exception" $S/logs/unity_r01_release_build.log | head -3
fi
if [ $st = players ] || [ $st = all ]; then
  $PL -Tag pl33_1 -Exe $EXE33
  $PL -Tag r01_1
  $PL -Tag pl33_2 -Exe $EXE33
  $PL -Tag r01_2
  py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_perf.py --runs G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/release/runs --tags pl33_1,r01_1,pl33_2,r01_2 --out $S/measure/r01_perf.json
fi
date
