# GreatWave_2026

『神奈川沖浪裏』の没入型3D/VR表現に向けた動的波浪と浮世絵表現の研究制作。

## フォルダー構成

| フォルダー | 役割 | 現状 |
| --- | --- | --- |
| `Unity/` | リアルタイム表示、浮世絵表現、HMD 体験、船の操作を統合する | 既存の試作を収録 |
| `Houdini/` | 波浪の流体シミュレーションとサーフェス化 | 制作前 |
| `Blender/` | 船などの静的モデルの制作 | 制作前 |
| `Whitewater/` | 白波を別計算・別モデルとしてアニメーション化する | 制作前、制作手段は未決定 |
| `Docs/` | 教員の要求、Rider AI による設計、段階ごとの検証記録 | 要求を記録、設計は未実施 |

## Unity の既存試作

- 使用エディター: Unity 6000.4.3f1
- Unity Hub ではリポジトリの **`Unity/`** をプロジェクトとして開く。
- 現在の主要シーン: `Unity/Assets/Scenes/Showcase_01.unity`
- ビルド対象のシーンはまだ `Unity/ProjectSettings/EditorBuildSettings.asset` に登録されていない。

`Unity/Assets/`、`Unity/Packages/`、`Unity/ProjectSettings/` と Unity の `.meta` ファイルを管理する。`Unity/Packages/com.coplaydev.unity-mcp/` のローカルソースも含める。パッケージ参照の整合性は今後確認する。

Unity が再生成するキャッシュ、実行結果、個人の作業記録、スクリーンショット群、復旧シーンはリポジトリに含めない。

現在の Unity 内容は既存試作の保存であり、波浪の物理的妥当性や HMD 上での動作を検証した完成版を意味しない。
