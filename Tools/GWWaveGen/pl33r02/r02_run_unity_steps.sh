#!/usr/bin/env bash
# 仕上げ33修正02 修正の回 2：場面の写し・Play モードの確かめ・Release のビルド・プレイヤーの負荷（pl33r01/r01_run_unity_steps.sh を写し、
# 場面を Polish33R02/Scenes/PL33R02_*.unity、出力を Build/Polish/33r02/{setup,release,playmode_*}、前の exe を仕上げ33修正01 にしたもの）。Unity は 1 つずつ（unity.lock）。
# 引数：段（setup|playmode|release|players|all）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
S=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r02
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r02/r02_run_unity.ps1"
PL="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r02/r02_run_player.ps1"
EXE01=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/release/player/GreatWave50.exe
st=${1:-all}
date
if [ $st = setup ] || [ $st = all ]; then
  $U -Method GreatWave.Polish33R02.EditorTools.PL33R02Setup.BuildScenes -Log setup -Extra "-pl33r02Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r02/setup" 2>&1 | grep -E "R02_UNITY"
  grep -E "PL33R02_SETUP_DONE|error CS|Exception" $S/logs/unity_r02_setup.log | head -5
fi
if [ $st = playmode ] || [ $st = all ]; then
  for sc in Release:400 SinglePlayback:120; do
    n=${sc%%:*}; lim=${sc##*:}
    $U -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_$n -Extra "-pl29Scene Assets/GreatWave/Polish33R02/Scenes/PL33R02_$n.unity -pl29Out $S/playmode_$n -pl29Limit $lim" 2>&1 | grep -E "R02_UNITY"
    grep -E "PL29_PLAYMODE|PLAYMODE_DONE|error CS" $S/logs/unity_r02_playmode_$n.log | head -3
  done
fi
if [ $st = release ] || [ $st = all ]; then
  $U -Method GreatWave.Polish33R02.EditorTools.PL33R02ReleaseBuild.BuildAll -Log release_build 2>&1 | grep -E "R02_UNITY"
  grep -E "PL33R02_RELEASE_BUILD_DONE|error CS|Exception" $S/logs/unity_r02_release_build.log | head -3
fi
if [ $st = players ] || [ $st = all ]; then
  $PL -Tag r01_1 -Exe $EXE01
  $PL -Tag r02_1
  $PL -Tag r01_2 -Exe $EXE01
  $PL -Tag r02_2
  py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_perf.py --runs G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r02/release/runs --tags r01_1,r02_1,r01_2,r02_2 --out $S/measure/r02_perf.json
fi
date
