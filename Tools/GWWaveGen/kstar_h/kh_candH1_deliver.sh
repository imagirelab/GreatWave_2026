#!/usr/bin/env bash
# 候補 H1 の納品（設計28修正01 K*′、Houdini）：設計の json → Houdini のシーン → 格子（GWW0）→ 評価・描画・記録。
# usage: bash kh_candH1_deliver.sh <design.json>
# 出力：Houdini/Design28R01/kstar_h.hiplc、Unity/Build/Q20H/candH1/（git 対象外）
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8
KH=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar_h
Q=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20H
OUT=$Q/candH1
HY="G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
HIP=G:/Unity/GreatWave_2026_Fresh/Houdini/Design28R01/kstar_h.hiplc
KROWS="G:/Unity/GreatWave_2026_Fresh/Unity/Build/ArtFirst/26修正01/kstar/kstar_a45_rows.npz"
A4ROWS=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20L3/candA4/kstarA4_a45_rows.npz
DESIGN=$1
mkdir -p "$OUT"
cp "$DESIGN" "$KH/candH1_design.json"
# 1 Houdini scene (network + CTRL ramps from the design) and its check (cook, CTRL round trip, Houdini vs numpy, OpenGL painting view)
timeout 1500 "$HY" "$KH/kh_design_scene.py" --design "$KH/candH1_design.json" --out "$HIP" --verify "$OUT/kstar_h_verify.json" > "$OUT/log_scene.txt" 2>&1
# 2 Houdini -> grid (the bridge slices /obj/kstar_h_design/OUT on the 240 row planes; col attribute keeps the landmarks)
timeout 1500 "$HY" "$KH/kh_bridge.py" h2g --hip "$HIP" --sop /obj/kstar_h_design/OUT --out "$OUT/kstarH1_a45" > "$OUT/log_bridge.txt" 2>&1
# 3 evaluation (+ 9 standard views, user-failure views, turntables) against K* and the round-3 winner A4
timeout 1790 py -3.10 "$KH/kh_eval.py" --out "$OUT/eval" --turntable "H1=$OUT/kstarH1_a45.gwb" "A4=$A4ROWS" "Kstar=$KROWS" > "$OUT/log_eval.txt" 2>&1
# 4 difference record (reference model: someone else's sculpture) and credit
py -3.10 "$KH/kh_diff_record.py" "$OUT/eval" H1 "$OUT/candH1_difference_record.json" >> "$OUT/log_eval.txt" 2>&1
echo "done: $HIP  $OUT"
