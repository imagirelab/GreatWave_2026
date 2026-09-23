# 大波本体の初期生成（第2・3段階、2026-09-20）

> この文書は当時の中国語記録を日本語で整理したものです。元の全文は変更前のコミット 0b0178eb9ea6b99ff685d608d557e49068066bb8 で確認できます。記載する数値と判断は当時の記録であり、現在の成果を再検証した結果ではありません。

第1段階の確認待ちの間に「動く波が見えない」と指摘されたため、暫定パラメータで大波を生成した記録である。未決定値は wave_params.json の PENDING 項目として残した。これは現在の最終版の合格報告ではない。

## 当時の実装

- src/gwave/profile_motion.py：終幕断面は大形輪郭（半径150 px）を基にし、画面外の背を水平3.0 H延長、端部接線を約14°とした。遮蔽された内側の弧はベジェ曲線で Z＝0 につなぎ、平らな谷を1.2 H設けた。曲率に応じて421点に再標本化した。
- 初期断面は高さ0.05 Hのガウス状のうねりとし、波頭部の初期弧長を終幕の25％とした。中間フレームは位置の直接補間ではなく、接線角と線分長の補間で構築し、背・前面、波頭上部、先端・下面の順に発達させた。
- 時間関数は単調な三次エルミート補間で、フレーム1、152、210、285を節点とした。両端の傾きを0とし、張り出し開始をフレーム152に合わせた。波頂の横移動は終点−2.0 H×(1−t/T)^1.8 を暫定値とした。
- 両翼は中央断面より発達の遅い形にし、端で静水面に収束させた。俯瞰では三日月形の波峰線になる。原画視点で空洞を隠さないため、翼の投影を中央断面の内側に抑えた。
- src/gwave/build_great_wave.py：421×201＝84,621頂点の固定トポロジー、断面弧長と波峰線方向のUV、波頭の縁に crest_rim 頂点群を設定。各フレームをPC2点キャッシュに書き出し、Mesh Cacheモディファイアで再生した。CAM_print、CAM_view34、CAM_front、CAM_boat、基準海面を配置した。
- src/gwave/render_previews.py は連続フレーム、原画重ね合わせ、MP4を出力。diagnose_motion.py と diagnose_steps.py は運動曲線と最大頂点変位を調べた。

## 当時の出力と再実行

- 当時の大容量ファイル：G:/research/Wave Simulation/great_wave.blend（2.6 MB）、G:/research/Wave Simulation/cache/great_wave.pc2（276 MB）。現在の保管先や存在は別途確認が必要。
- プレビュー：results/wave_build/preview/。運動診断：results/wave_build/diagnose/。
- 当時の再構築コマンド：G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1 に src/gwave/build_great_wave.py を渡す。動画は同スクリプトに src/gwave/render_previews.py、Blendパス、--video を渡して生成した。
- 原記録は「テスト結果は末尾参照」と書くが、記録本文に具体的な合否表はない。したがって、この文書から S1–S8／M1–M6／G1–G5 の合格は確認できない。
