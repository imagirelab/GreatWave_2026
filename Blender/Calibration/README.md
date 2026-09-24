# ステップ 07：長さ・軸・鏡映の校正データ

本データは既存の試作を参照せず、Blender 5.2.2 LTS で新規生成した最小の検証用形状です。完成作品の船や波ではありません。

## ファイル

- `generate_calibration.py`：再生成・保存・再読込・数値検証を行うスクリプト。
- `Calibration.blend`：メートル単位の制作元。メッシュ 6 個、カメラ・ライト・アニメーションなし。
- `calibration.fbx`：Unity に渡す形状。
- `validation_blender.json`：ソフトウェアの版、単位、書出設定、元形状と再読込形状の寸法、検証結果、ファイル SHA-256。

## 基準寸法

以下は Blender の右手座標系（Z 上方向）の値です。座標と寸法の単位はすべて m です。

| オブジェクト | 形状の中心 X, Y, Z | 寸法 X, Y, Z | 目的 |
|---|---|---|---|
| Calibration_Cube_1m | 0, 0, 0.5 | 1, 1, 1 | 一辺 1 m、底面 Z = 0 |
| Axis_PosX_2m | 2, 0, 0 | 0.20, 0.10, 0.10 | 正 X、赤 |
| Axis_PosY_3m | 0, 3, 0 | 0.10, 0.30, 0.10 | 正 Y、緑 |
| Axis_PosZ_4m | 0, 0, 4 | 0.10, 0.10, 0.40 | 正 Z、青 |
| Axis_NegX_1p5m | -1.5, 0, 0 | 0.15, 0.15, 0.15 | 負 X、橙 |
| Handedness_P123 | 1, 2, 3 | 0.12, 0.20, 0.28 | 非対称な鏡映判定点、紫 |

位置・回転・スケールをメッシュへ適用しています。すべてのオブジェクトの Transform は位置 0、回転 0、スケール 1 です。上表の「中心」は形状の境界の中心であり、Transform.position ではありません。

正 X / 正 Y / 正 Z の中心ベクトルの順序付き三重積は、Blender 側では +24 m³ です。距離・名前・三軸の長さを変えてあるため、軸の取り違えや鏡映を数値で判定できます。

## 再生成

Blender のバックグラウンド実行で、次の引数を渡してください。スクリプトと同じフォルダーに出力し、同名の生成物を更新します。

```text
blender --background --factory-startup --python generate_calibration.py
```

この PC の実行ファイルは `G:\SteamLibrary\steamapps\common\Blender\blender.exe` です。検証に成功したときのみ `CALIBRATION_BLENDER_PASS` を出力します。

処理は (1) 空シーンに生成、(2) 元形状検査、(3) blend と FBX 保存、(4) blend 再読込、(5) 空シーンへの FBX 再読込、(6) 名前・面数・頂点数・寸法・中心・全ワールド頂点・三重積の検査、の順です。許容誤差は 0.00001 m です。

## 書出設定と Unity 側の確認

Blender 単位は Metric、Unit Scale は 1、Length は Meters。FBX は `global_scale=1`、`apply_unit_scale=True`、`apply_scale_options=FBX_SCALE_UNITS`、`axis_forward=-Z`、`axis_up=Y`、`use_space_transform=True`、`bake_space_transform=False` を明示しています。全フラグは JSON に保存しています。アニメーションと外部テクスチャはありません。

Unity では FBX の実インポート後に、まず **インポートルートを位置 0・回転 0・スケール 1** にして、名前で各メッシュを特定し、実際のワールド頂点または Renderer.bounds を測ってください。

1. 一辺 1 m の立方体が X/Y/Z いずれも 1 m であること。
2. 3 個の軸マーカーが直交し、原点からの距離が順に 2 m / 3 m / 4 m であること。
3. 負 X のマーカーが正 X の反対側の 1.5 m にあること。
4. 正軸マーカーから実測した基底を用い、Handedness_P123 の中心が `0.5 × Axis_PosX_2m + (2/3) × Axis_PosY_3m + 0.75 × Axis_PosZ_4m` と一致すること。
5. 実測した Blender→Unity の軸・符号の対応と、Unity ModelImporter の設定を記録すること。FBX の宣言だけで Unity の軸対応を決めつけないこと。
6. 上向き、立方体の底面、外向き法線・裏面の描画も静止画で確認すること。

本フォルダーの検証は **Blender の保存・FBX 往復のみ** です。Unity での寸法・座標変換、HMD 表示は未検証です。Unity のインポート結果とその画像は、担当工程で別の証跡として残します。
