# 07：BlenderからUnityへの単位・軸

日付：2026-09-24／結果：新規Blender制作、保存・FBX往復、Unity実インポートの数値検査を完了。描画確認は10、HMDは保留。

別担当のGPT-6が空のBlenderシーンに1m箱と非対称の5目印を新規生成した。旧試作は参照していない。制作元・生成手順・Blender測定を [校正データ](../../Blender/Calibration/README.md) に保存した。Unity用FBXはその出力をコピーしたもので、blendはUnity外へ置いて自動変換への依存を避けた。

実際のUnityインポート後、モデルの根を位置0・回転0・拡大率1に置き、各メッシュのワールド頂点から境界と中心、法線を測定した。Transform.positionだけで位置を判定していない。

| Blenderの基準 | Unityで固定した対応 | 実測 |
| --- | --- | --- |
| +X、2m | -X、2m | (-2, 0, 0) |
| +Y、3m | -Z、3m | (0, 約0, -3) |
| +Z、4m | +Y、4m | (0, 4, 約0) |
| 1m箱 | X/Y/Zすべて1m、底面Y=0 | 誤差±0.001m以内 |
| 非対称点(1,2,3) | (-1,3,-2) | 誤差±0.001m以内 |
| 軸の三重積 | +24から-24へ座標系の向きが変換 | 約-23.999996 m³ |

FBXは-Z forward / Y upで書き出し、UnityはglobalScale=1、useFileScale=true、bakeAxisConversion=falseを固定した。この受け渡しではBlenderの前方-YがUnityの+Zへ向く。右手系から左手系への変換を含み、単純にBlenderとUnityの同名軸を同一視しない。以後はこの対応を明示して制作する。

検査では上方向、軸の長さと直交、負X目印、非対称点、箱の底面、全ピボット、期待する符号、三重積、外向き法線をそれぞれ判定した。画像を見ずに法線の見た目まで合格としたわけではない。

- [Unity実測と判定JSON](../Evidence/M0/07_unity_import.json)
- `M0CalibrationVerifier.ImportAndMeasure` を実行して再測定できる。
- 計測後、表示用のモデルだけを(-5, 0.15, 8)mへ移動した。実測JSONは原点に置いた条件。
- 元ログ：`Unity/Logs/07-calibration.log`（Git対象外）。画像は10のPC実行版から保存する。
