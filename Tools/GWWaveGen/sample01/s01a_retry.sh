#!/usr/bin/env bash
# 美術の見本01・見本 A：s01a_run_render.sh を、描画が終わり（S01A_RENDER_DONE）かつメモリ不足の描画の板（D3D_OOM）が 0 になるまで、4 回まで繰り返す。
# 2026-10-02 夜、ほかの処理でパソコンの確保できるメモリ（コミット）が尽きかけ、Unity の描画の板の作成や配列の確保が時々失敗したため。引数は s01a_run_render.sh と同じ。
cd G:/Unity/GreatWave_2026_Fresh
for i in 1 2 3 4; do
  out=$(bash Tools/GWWaveGen/sample01/s01a_run_render.sh "$@" 2>&1)
  echo "$out" | grep -E "S01A_RENDER_DONE|D3D_OOM|S01A_UNITY" | tr '\n' ' '; echo
  if echo "$out" | grep -q "S01A_RENDER_DONE" && echo "$out" | grep -q "D3D_OOM=0"; then exit 0; fi
  sleep 30
done
exit 1
