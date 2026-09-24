# 17：変動トポロジーの実FLIP試料

[制作結果・画像・限界](../../Docs/Progress/Step_17_ja.md)を先に読む。小さな流体の結合と分離を含む技術試料で、北斎の波や質量保存の検証ではない。

## 保存場所

- `Source/generate_fluid.py`：公式SOPによる新規FLIP生成・全時刻保存・再読込確認。
- `Source/run_fluid17.py`：MCP SDKの段階実行とfinally復元。`Source/ui_guard.py`は今回の新規16基盤から継承し、24Hz用に適応した。
- `Source/fluid17_owned.cpio`：所有コンテナーだけの設定。完全なHIPや再計算済みのDOPメモリーではない。
- `Source/validate_cached.py`／`inspect_cache.py`：実BGEOの連結成分、ID継承、表裏・法線・体積を再測定。
- `Source/capture_cached17.py`：新規の表示用ノードで実キャッシュを再読込し、粒子位置の球記号と表面を同じ画角で撮影。
- `Source/finalize_evidence.py`：ハッシュ照合、選択キャッシュ保存、実画像の動画化、全デコード、出典更新。
- `Evidence/17_summary.json`：技術試料の判定、未検証項目、全98キャッシュのSHA。
- `Evidence/SelectedCache/`：6時刻×粒子/表面の実BGEO。全キャッシュは `Cache/` にあり、Git対象外。
- `LocalRejected/Attempt01/`：小領域の不採用試行。元キャッシュ・ソースをローカルに保持。公開要約は `Evidence/17_rejected_initial.json`。

## 本機での再現

現在の前提はSteam Houdini22.0.429の既存MCP、127.0.0.1:8100、24fps。接続先には未保存の利用者シーンがあるため、別HIPを保存・読込せず、一意な所有ノードだけを作成して削除する。PID53912は今回の値で、将来の固定値として信用しない。

使用Python：`G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe`。このPythonで次の順に各スクリプトを実行する。Houdini UIへの作業中は別の操作を同時に行わない。

1. `Source/probe_connection.py`：PID・版・UI・分類・FPSを再実測する。別の実行環境や24fps以外なら、自動的に設定を変更せず条件を見直す。
2. `Source/run_fluid17.py --probe`：最初の2時刻だけでソルバー・保存・復元を確かめる。
3. `Source/run_fluid17.py`：0〜2秒の49時刻を生成。約50MBのCacheを作り直すため、以前の試料を残す場合は先に別の自分の保存先へ退避する。
4. `Source/inspect_cache.py`：実キャッシュの数値を更新。Volume保持点を除外した実粒子だけを測る。
5. `Source/capture_cached17.py --preview`：粒子と面が描画されていることを視覚確認。その後 `Source/capture_cached17.py` で正式画像・動画用フレームを取得する。表示用球半径0.025mは粒子径の物理モデルではない。
6. `Source/finalize_evidence.py --simulation run_実際のID.json --capture capture_実際のID.json`：それぞれ今回成功したEvidence内のレポートを指定して出典と動画を更新する。名前を過去の実行から流用しない。

今回の実行は `run_f5ed693b99.json`、正式撮影は `capture_40b91a1b50.json`。公開用の複製は `17_simulation_run.json` と `17_capture_run.json`。MCP応答内の説明文字列には文字化けがあるため、日本語の説明は本資料と17_summaryのローカル生成文を使う。数値や真偽値は原応答のまま保存している。

## データの読み方

単位m、Houdini Y-up、相対秒t=(frame-1)/24。各時刻の粒子/場と表面は同じ実計算に由来する。元場の保持点5個を実粒子へ加算しない。`17_cache_index` の旧命名 `particle_count` は生点数、`17_validation.samples.particle_count` が実粒子数。

連結の閾値は粒子距離0.16m、有意群12粒子、系譜共有8ID、面体積0.005m³。これらはこの粗い技術試料の判定値で、普遍的な流体の分裂条件ではない。49時刻でトポロジーは変わるため、16の固定XZ対応や全法線Y正を再利用しない。

生フレーム、全キャッシュ、初期失敗の記録はローカル保持。Git版には生成スクリプト、所有CPIO、選択キャッシュ、全キャッシュのSHA、数値、正式画像・動画を含めた。CPIOの読込による再計算一致やHIP再起動試験は実施していない。18のAlembic/VAT比較とHMDは未実行。
