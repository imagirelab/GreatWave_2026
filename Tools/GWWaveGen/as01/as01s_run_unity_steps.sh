#!/usr/bin/env bash
# 美術の見本01（Q29）組み立て：場面の写し（AS01SampleSetup）と Play モードの確かめ（仕上げ29 の PL29PlayModeCheck を写しの場面で）。
# 仕上げ33修正01 の r01_run_unity_steps.sh の setup・playmode の段を写したもの。Unity は 1 つずつ（unity.lock）。
# 引数：段（setup|playmode|all）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
AS=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/assemble
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as01/as01s_run_unity.ps1"
st=${1:-all}
date
if [ $st = setup ] || [ $st = all ]; then
  $U -Method GreatWave.ArtSample01.EditorTools.AS01SampleSetup.BuildScenes -Log setup -Extra "-as01Out $AS/setup" 2>&1 | grep -E "AS01S_UNITY"
  grep -E "AS01S_SETUP_DONE|error CS|Exception" $AS/logs/unity_as01s_setup.log | head -5
fi
if [ $st = playmode ] || [ $st = all ]; then
  for sc in A_SinglePlayback:120 B_SinglePlayback:120 A_Release:400 B_Release:400; do
    n=${sc%%:*}; lim=${sc##*:}
    $U -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_$n -Extra "-pl29Scene Assets/GreatWave/ArtSample01/Scenes/AS01_Sample$n.unity -pl29Out $AS/playmode_$n -pl29Limit $lim" 2>&1 | grep -E "AS01S_UNITY"
    grep -E "PL29_PLAYMODE|PLAYMODE_DONE|AS01_DESIGN_LOADED|error CS" $AS/logs/unity_as01s_playmode_$n.log | head -4
  done
fi
date
