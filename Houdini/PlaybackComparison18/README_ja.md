# 18：同じ実FLIP面をAlembicとFluid VATへ渡す

17の採用クリップ `GreatWave17_FLIP_02` の49個のsurface BGEOを読み、流体を再計算せず、実際のAlembicとSideFX Labs Dynamic Remeshing VATを出力した。結果・画像・負荷の判定は [18の記録](../../Docs/Progress/Step_18_ja.md) にまとめる。19の密度/HMD試験と20の方式採用は行わない。

## 入力と比較の基準

- 24Hz、元frame1〜49、相対時刻0〜2秒。元BGEOは [17の全時刻索引](../VariableTopology17/Evidence/17_cache_index.json) のSHAで49件照合した。
- 元面の各ポリゴンを頂点0からfan三角化し、点P/Nを保った同一SOPを両形式へ渡した。Fuse・削減・FLIP再計算なし。
- 元には非平面quadがある。先頭3点の平面から最大約0.04647m離れ、投影が凹の面も1件ある。このため今回の誤差基準は**共通の三角化後の面**であり、非平面quad内部の唯一の曲面を復元したとは言わない。[三角化監査](Evidence/18_triangulation_audit.json)。
- 1unit=1m、Houdini Y-upからUnity `(-x,y,z)` へ。法線・有向接続も照合する。別時刻の頂点番号が同じとは仮定しない。
- 元の面化体積膨張と終盤の領域外流出は保持した。今回の転送誤差とは区別し、物理精度・質量保存は合格対象にしない。

## 実出力と実装

Steam Houdini22.0.429の既存GUIへ真のMCPクライアントで接続した。所有コンテナーとROPだけを作り、最後にUIと所有物18項目、一時HDA登録の解除を確認した。HIP保存・読込・全シーン走査・FPS・ライセンス・既存プラグインの変更は行わない。Undoと変更済みフラグは消去しない。[出力・復元要約](Evidence/18_export_summary.json)。

| 項目 | 条件 |
| --- | --- |
| Alembic | 実49サンプル、Changing Topology、archive 1/24〜49/24秒。Unityの相対指定は0〜2秒、補間OFF、SwapHandedness ON、Scale1 |
| VAT | Labs3.1 Dynamic Remeshing、mesh+lookupとanimationの2pass、49時刻、HDR float32 position/quaternion/lookup、UVなし、法線をquatから復号 |
| 公式版 | [SideFXLabs](https://github.com/sideeffects/SideFXLabs/tree/791ecfd07735bb8229fb679f08c000b8489b7a6c) の固定SHA。VATと3依存HDAだけを一時登録 |
| Unity | 6000.4.3f1、Built-in、Alembic2.4.4、Windows x64 Mono |
| デコーダー | 公式URP用DynamicRemeshing graphのHDR経路を新規Built-in shader/computeへ移植。公式Unity全パイプライン対応の主張ではない |
| 画像読込 | linear、RGBAFloat、Point、Repeat、no mip、no compression、最大8192、Standalone明示指定 |
| FBX読込 | scale1、圧縮/頂点最適化/weld OFF、UV保持、N/T import、readable |

lookupは2048×6174、position/rotationは1024×1066。符号化boundsの小数部はレイアウト情報を兼ねるため、実形状boundsに置き換えない。CPU/GPUの整数境界丸めを、最大2e-5かつ実lookup画素の1/8未満の範囲だけ補正する。元のmetadataは変更せず、raw/used値と境界9事例の結果を残した。共通デコードを実FBXのUVと実EXRで全49時刻照合する。

公式graphとライセンスは `ThirdParty/DecoderReference/`、4個のpacked HDAとライセンスは `ThirdParty/SideFXLabs/`。重複するVCS展開フォルダーはGitに含めない。[取得SHA一覧](Evidence/18_labs_download.json)。

## 保存場所

- Gitで共有する実ABC・VAT FBX/3EXR・可逆gzip参照：[Unity入力](../../Unity/Assets/GreatWave/Art/Playback18/)。各ファイルは100MB未満。EXRなどをさらに劣化圧縮していない。
- 元の非圧縮参照と書出し原本：本機 `G:\Unity\GreatWave_2026_Fresh\Houdini\PlaybackComparison18\Exports\`。Gitには重複掲載しない。
- 所有ノードだけの保存物：[Source/playback18_owned.cpio](Source/playback18_owned.cpio)。HIP全体ではなく、既存セッションの保存/再読込を検証したものでもない。絶対パスは今回のPC用。
- Gitには17の全BGEOはない。18の配布済みABC/VAT再生には不要。Houdiniから完全に再書出しするには、17の生成元で全49surfaceを用意し、索引SHAを一致させる。

## 再現

既存のMCP接続を利用するPCでは、`Source/probe_connection.py` で現在のPID/版/ライセンス応答を再実測する。歴史的PID53912を無条件で再利用しない。runnerは最新接続記録をguardへ渡し、24fpsを確認する。新規所有物の出力先を準備してから実行する。

```powershell
$python = 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
& $python Houdini/PlaybackComparison18/Source/probe_connection.py
# 同梱packed HDAを再取得する場合のみ：
& $python Houdini/PlaybackComparison18/Source/fetch_labs.py
& $python Houdini/PlaybackComparison18/Source/run_export.py
& $python Houdini/PlaybackComparison18/Source/integrate_alembic.py
& $python Houdini/PlaybackComparison18/Source/integrate_vat.py
```

Unity側の再生成、ビルド、実描画は [18の記録](../../Docs/Progress/Step_18_ja.md) を参照。両形式は同じ比較sceneで、2秒の一回再生を行う。

## 失敗を隠さない記録

初回VATはf2の既定式が240まで残り、欠落cache/空画像が生じたため不採用。式を解除して1〜49をassertし、正式 `VAT_Final` へ分けた。修正pass1は144.51秒、pass2は130.34秒。旧Houdini側ブリッジの120秒応答期限を超えた際は、計算を重複実行せず同tokenの完了JSONと出力を確認してから復元した。通信上の失敗と計算完了は別記する。

最初のUnity検査では、検査側の面積閾値が正しい極細三角形をpaddingと誤分類した。全頂点が厳密に同じ位置へ潰れた三角形だけを除外するよう修正し、全参照面の有向接続を再検査した。元キャッシュ・公式出力・誤差許容値を変更して合格させていない。

一次資料：[VAT3.1](https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.1.html)、[Unity Alembicの読込条件](https://github.com/Unity-Technologies/com.unity.formats.alembic/blob/main/com.unity.formats.alembic/Documentation~/import-options-scene.md)。
