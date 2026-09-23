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

- [改訂試作：斜めから見る動き（MP4）](Blender/great_wave/deliverables/localized_wave_volume.mp4)
- [改訂試作：原画方向から見る動き（MP4）](Blender/great_wave/deliverables/localized_wave_print.mp4)
- [アニメーションを内蔵した Blender ファイル](Blender/great_wave/deliverables/localized_wave_animated.blend)

改訂試作は局所的な高峰、非対称の肩、独立した分岐白波と小滴を検討するものです。動画は 30 fps、11.5 秒で、立上りから最終姿勢での静止までを収録しています。**参考映像と同等の完成品質に達したという判定ではありません。** 残る問題は[改訂記録](Blender/great_wave/docs/milestones/2026-09-24_localized_wave_rebuild.md)に記載しています。

旧版の動画も[成果物一覧](Blender/great_wave/deliverables/README.md)から比較できます。Houdini の流体シミュレーション、Unity でのリアルタイム表示、HMD での動作は、この Blender 試作では検証していません。

## Unity の既存試作

- 使用エディター: Unity 6000.4.3f1
- Unity Hub ではリポジトリの **`Unity/`** をプロジェクトとして開く。
- 現在の主要シーン: `Unity/Assets/Scenes/Showcase_01.unity`
- ビルド対象のシーンはまだ `Unity/ProjectSettings/EditorBuildSettings.asset` に登録されていない。

`Unity/Assets/`、`Unity/Packages/`、`Unity/ProjectSettings/` と Unity の `.meta` ファイルを管理する。`Unity/Packages/com.coplaydev.unity-mcp/` のローカルソースも含める。パッケージ参照の整合性は今後確認する。

Unity が再生成するキャッシュ、実行結果、個人の作業記録、スクリーンショット群、復旧シーンはリポジトリに含めない。

現在の Unity 内容は既存試作の保存であり、波浪の物理的妥当性や HMD 上での動作を検証した完成版を意味しない。
