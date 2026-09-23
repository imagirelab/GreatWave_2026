# GreatWave_2026

『神奈川沖浪裏』の没入型3D/VR表現に向けた動的波浪と浮世絵表現の研究制作。

## フォルダー構成

| フォルダー | 役割 | 現状 |
| --- | --- | --- |
| `Unity/` | リアルタイム表示、浮世絵表現、HMD 体験、船の操作を統合する | 既存の試作を収録 |
| `Houdini/` | 波浪の流体シミュレーションとサーフェス化 | 制作前 |
| `Blender/` | 大波の造形・アニメーション研究と、船などの静的モデルの制作 | 大波の試作と検証を収録。船のモデルは未制作 |
| `Whitewater/` | 白波を主波面とは別モデルとしてアニメーション化する | Blender による造形・アニメーションの試作を収録。物理的妥当性は未検証 |
| `Docs/` | 教員の要求、Rider AI による設計、段階ごとの検証記録 | 要求を記録。Rider AI による設計は未実施 |

## 大波の試作動画

- [原画視点の動画（MP4）](Blender/great_wave/deliverables/great_wave_motion_print_reference.mp4)：原画の色と模様を単一視点から投射した、形状・構図の比較用動画。
- [斜め視点の動画（MP4）](Blender/great_wave/deliverables/great_wave_motion_3d.mp4)：三次元形状、手続き型の材質、独立した白波を確認するための動画。

いずれも約 11.5 秒です。30 fps で作成した動きから 2 フレーム間隔で画像を取り出し、15 fps で再生しています。動画と直接開ける静止画用 `.blend` の説明、検証結果、残る問題は [Blender の大波試作](Blender/great_wave/README.md) を参照してください。Houdini の流体シミュレーション、Unity でのリアルタイム表示、HMD での動作はまだ検証していません。

## Unity の既存試作

- 使用エディター: Unity 6000.4.3f1
- Unity Hub ではリポジトリの **`Unity/`** をプロジェクトとして開く。
- 現在の主要シーン: `Unity/Assets/Scenes/Showcase_01.unity`
- ビルド対象のシーンはまだ `Unity/ProjectSettings/EditorBuildSettings.asset` に登録されていない。

`Unity/Assets/`、`Unity/Packages/`、`Unity/ProjectSettings/` と Unity の `.meta` ファイルを管理する。`Unity/Packages/com.coplaydev.unity-mcp/` のローカルソースも含める。パッケージ参照の整合性は今後確認する。

Unity が再生成するキャッシュ、実行結果、個人の作業記録、スクリーンショット群、復旧シーンはリポジトリに含めない。

現在の Unity 内容は既存試作の保存であり、波浪の物理的妥当性や HMD 上での動作を検証した完成版を意味しない。
