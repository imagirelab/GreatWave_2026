# 19：実60Hz FLIPとPC描画の引継ぎ

利用者の18確認・続行指示を受けて、新しい60Hzの実FLIPを作成した。成果と制限は [Step19](../../Docs/Progress/Step_19_ja.md)。19はPC部分の中間確認で停止し、HMDと20の方式採用は未実施。

## 実データの場所

- Git掲載の入力：[`Unity/Assets/GreatWave/Art/Sampling19`](../../Unity/Assets/GreatWave/Art/Sampling19)。4本の実Alembicと可逆gzipの参照。参照名は`reference60.bytes`だがgzipとして読む。
- 本機の全キャッシュ：`G:\Unity\GreatWave_2026_Fresh\Houdini\Sampling19\Cache`。121時刻×粒子/面の242BGEO、124,142,322bytes。Git対象外。
- 元書出しと未圧縮参照：同`Exports/`。Git対象外で、掲載入力と同bytesか可逆展開一致を確認した。
- `Source/fluid19_owned.cpio`は新規所有ノードだけの保存。現在開いているHIPの保存でも、.hiplc再起動検証でもない。
- [全時刻索引](Evidence/19_cache_index.json)、[書出しmanifest](Evidence/19_alembic_exports.json)、[Unityコピーの一致](Evidence/19_unity_integration.json)、[要約とUI復元](Evidence/19_source_summary.json)。

## 計算と時刻契約

Steam Houdini22.0.429・Indie・UIあり。PID53912はこの実行時の値で、将来の起動へ固定して使わない。[接続記録](Evidence/19_connection.json)。global24fpsを変えず、所有DOPだけ1/120秒・補間OFF・substep cache ONに設定した。要求k/60秒でglobal frame `1+24*k/60`へ合わせて実cookし、同じ評価コンテキストのsimulation time/timestepを採録。`geometryAtFrame`を呼んだだけで新計算と見なしていない。

全121時刻のDOP時刻誤差は最大2.22e-16秒。粒子Pと面P/topologyが各時刻で変わり、P/N/vをBGEOから再読込した。30Hzは同計算の偶数61時刻なので、流体の計算条件は同じ。独立した物理の真値、全時刻の質量保存、北斎の砕波を意味しない。粒子数は1305→570、後半のdomain流出と面化誤差を含む。

単位m・Y-up、UnityはX反転。面のfan三角化は両出力/参照へ同じ処理を用い、元キャッシュを変更しない。native Alembic時刻は物理相対秒+1/24。60Hzの3segmentは40/80の境界を重複し、Unityは相対秒をsegment開始から評価する。[全184格納サンプルの独立読戻し](Evidence/19_alembic_independent_readback.json)もP/N/有向triangle一致、30Hz共通時刻と境界が一致した。

## 再現手順

まず上記Git入力からUnityを作るだけならHoudini操作は不要。[Step19のPC手順](../../Docs/Progress/Step_19_ja.md)を使う。

Houdiniから再生成する場合は、現在のMCP接続を先に確認する。以下は本機の既存環境用。出力先が同じなので、既存正式結果を保持したい場合は`Sampling19/`を別の新しい作業先へ複製して実行する。過去のPIDや古い`19_connection.json`をそのまま使わない。

```powershell
$python19='G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
& $python19 ./Houdini/Sampling19/Source/probe_connection.py
& $python19 ./Houdini/Sampling19/Source/run_sampling.py
# pilotの実時刻・dt・非重複・UI復元を確認してから全体へ。
& $python19 ./Houdini/Sampling19/Source/run_sampling.py --full
& $python19 ./Houdini/Sampling19/Source/run_exports.py
& $python19 ./Houdini/Sampling19/Source/integrate_unity.py
```

`run_sampling.py` / `run_exports.py`は真のMCPクライアントから`execute_python`を呼び、再測定したPIDをガードする。既存HIPの全ノード/形状を走査せず、新規所有コンテナだけを生成・計算・書出す。既存DOP reset、HIP保存/読込/clear、global FPS変更は行わない。所有nodeのinstanceだけを編集可能にし、HDA定義は変更しない。

`finally`で所有ノードを削除し、選択・pane・frame・view・FPS等18項目を復元した。Undo履歴は消さず、変更済みフラグtrueを保持。最後の書出しではUndo442→474を記録した。過去実行の詳細logはローカル、公開要約にそれらのhash・実行ソースhash・復元条件を保存。CPIOは所有ノードの記録であり、今回はCPIO再読込/再計算やHIP保存再起動を別途実行していない。

## 解析・描画の区別

- [30Hz保持差の独立幾何解析](Analysis_ja.md)：60 odd時刻を面への距離で比較。頂点番号補間なし。標本距離でありHMD知覚や波頭尖端合格ではない。
- [19の新shader](Shader_ja.md)：18の正式24Hz VAT/ABCを読み取り再利用し、色・CameraDepthTexture・床への落影・別物体からの受影をWindows上で検査する。新30/60Hz VATは作っていない。
- [`19_shader_compile.json`](Evidence/19_shader_compile.json)：単独コンパイル28経路の当時の出典。実Unity検査はStep19の別報告。

HMD機器、XR両眼配送/追跡/SPI/再投影、runtimeへのdepth submission、HMD性能、主役波の尖端/爪形状、方式採用20は保留。
