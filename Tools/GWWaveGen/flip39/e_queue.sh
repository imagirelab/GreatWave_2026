#!/bin/bash
# FLIP39 E：3D の計算を一つずつ順に流す（前の鎖の終わりを待つ）。
E="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
T="G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
until grep -q "chain end" "$E/E2_dir20_reef/chain.log" 2>/dev/null; do sleep 15; done
cd "$T"
py -3.10 e_post.py E2_dir20_reef --clip > "$E/_post_E2.log" 2>&1 &
CFG3=$(py -3.10 e_cfg.py E3_dir20_lens 16.47 slab=0 sigma=20 mound=1 lead=55)
mkdir -p "$E/E3_dir20_lens"
py -3.10 e_chain.py "$CFG3" --wait > "$E/E3_dir20_lens/chain.log" 2>&1
py -3.10 e_post.py E3_dir20_lens --clip > "$E/_post_E3.log" 2>&1 &
if [ -f "$E/_queue_E2w_go" ]; then
  CFGW=$(py -3.10 e_cfg.py E2w_dir40_reef 16.2 slab=0 sigma=40)
  mkdir -p "$E/E2w_dir40_reef"
  py -3.10 e_chain.py "$CFGW" --wait > "$E/E2w_dir40_reef/chain.log" 2>&1
  py -3.10 e_post.py E2w_dir40_reef --clip > "$E/_post_E2w.log" 2>&1
fi
echo queue-done
