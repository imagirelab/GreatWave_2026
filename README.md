# GreatWave_2026

『神奈川沖浪裏』の没入型3D/VR表現に向けた動的波浪と浮世絵表現の研究制作。

## フォルダー構成

| フォルダー | 役割 | 現状 |
| --- | --- | --- |
| `Unity/` | リアルタイム表示、浮世絵表現、HMD 体験、船の操作を統合する | 既存の試作を収録 |
| `Houdini/` | 波浪の流体シミュレーションとサーフェス化 | 波槽・集束波群に加え、参照形状からの自由発展を96フレーム計算。目標の形成と開口の保持は未達。Unity読込みは未検証 |
| `Blender/` | 大波の造形・アニメーション研究と、船などの静的モデルの制作 | 大波の試作と検証を収録。船のモデルは未制作 |
| `Whitewater/` | 白波を主波面とは別モデルとしてアニメーション化する | Blenderによる造形試作あり。Houdiniで別計算した白波の短い確認は `Houdini/reference_release/` に収録 |
| `Docs/` | 教員の要求、Rider AI による設計、段階ごとの検証記録 | 要求を記録。Rider AI による設計は未実施 |

## 大波の試作動画

### 最新：参照水体の自由発展と別計算の白波

- 主波の単色表示：[固定側面（4秒）](Houdini/reference_release/previews/自由発展01_側面.mp4) ／ [固定斜視（4秒）](Houdini/reference_release/previews/自由発展01_斜視.mp4)
- 白波と色面表示：[固定斜視（1秒）](Houdini/reference_release/previews/自由発展01_白波と色面_斜視.mp4) ／ [固定側面（1秒）](Houdini/reference_release/previews/自由発展01_白波と色面_側面.mp4)

参照の巻いた水体と高さに応じた非零の初期速度から、主波を96フレーム・24 fpsでFLIP計算しました。白波は第2～24フレームを別に生成・計算・後処理し、主波の第1～24フレームに重ねています。第1フレームには白波がありません。

**目標未達の崩壊診断です。** C形は第1・6フレームで読めますが、第12フレーム（開始から約0.46秒）には保持できていません。初期断面も参照より開口が22～31%狭く、唇の鉛直厚さが21～41%増しています。第17フレーム以降は側壁の影響にも注意が必要です。[計算条件と制限](Houdini/reference_release/README.md)、[画面と断面による判定](Blender/great_wave/docs/milestones/2026-09-24_reference_release.md)に記録します。

低い浪からの形成は未確認です。初期速度0の対照A0は未実行で、誘導条件Bは解析速度場をNumPyで確認した段階です。誘導を加えたFLIPはまだ実行していません。

### Houdiniの流体計算：形状確認

- [集束波群の試験：固定斜視（3秒）](Houdini/focused_packet/previews/集束波_斜視.mp4) ／ [固定側面（3秒）](Houdini/focused_packet/previews/集束波_側面.mp4)
- [試作02：全槽の固定側面（3秒）](Houdini/wave_tank/previews/試作02_側面.mp4)
- [試作02：波頭の固定拡大（3秒）](Houdini/wave_tank/previews/試作02_側面拡大.mp4)
- [試作02：固定斜視（3秒）](Houdini/wave_tank/previews/試作02_斜視.mp4)
- [以前のHoudiniキャッシュ：直接表示による比較（約2.29秒）](Houdini/wave_tank/previews/旧キャッシュ_側面.mp4)

新しい2条件では実際のFLIP流体を計算しましたが、**参照模型のような深い開口と大きな巻下げには達していません。** 単色表示で波の形を確認する段階です。[画面による判定](Blender/great_wave/docs/milestones/2026-09-24_fluid_trials.md)、[計算条件と再現手順](Houdini/wave_tank/README.md)に結果と限界を記録しています。

続く集束波群の条件でも目標の造形は未達です。初期場の不整合を含めて、[追加試行の記録](Blender/great_wave/docs/milestones/2026-09-24_focused_packet.md)に説明しています。

### Blenderの造形・アニメーション比較

- [参照模型を底稿にした前進と巻き下げ：追跡視点（MP4）](Blender/great_wave/deliverables/reference_actor_volume.mp4)
- [同じ運動を固定視点で確認する動画（MP4）](Blender/great_wave/deliverables/reference_actor_fixed.mp4)
- [アニメーションを内蔵した Blender ファイル](Blender/great_wave/deliverables/reference_actor_animated.blend)

現在の比較試作は、利用者提供の3D参考模型を簡略化し、水体と白波を分離して動かしたものです。基礎造形を新たに自作したものではありません。動画は 30 fps、15 秒で、形成、前進、前側の巻き下げ、低波への移行を収録しています。**参考映像と同等の完成品質に達したという判定ではありません。** 制作方法、出典、検証範囲と課題は[改訂記録](Blender/great_wave/docs/milestones/2026-09-24_reference_actor.md)に記載しています。

旧版の動画も[成果物一覧](Blender/great_wave/deliverables/README.md)から比較できます。Houdini の流体シミュレーション、Unity でのリアルタイム表示、HMD での動作は、この Blender 試作では検証していません。

## Unity の既存試作

- 使用エディター: Unity 6000.4.3f1
- Unity Hub ではリポジトリの **`Unity/`** をプロジェクトとして開く。
- 現在の主要シーン: `Unity/Assets/Scenes/Showcase_01.unity`
- ビルド対象のシーンはまだ `Unity/ProjectSettings/EditorBuildSettings.asset` に登録されていない。

`Unity/Assets/`、`Unity/Packages/`、`Unity/ProjectSettings/` と Unity の `.meta` ファイルを管理する。`Unity/Packages/com.coplaydev.unity-mcp/` のローカルソースも含める。パッケージ参照の整合性は今後確認する。

Unity が再生成するキャッシュ、実行結果、個人の作業記録、スクリーンショット群、復旧シーンはリポジトリに含めない。

現在の Unity 内容は既存試作の保存であり、波浪の物理的妥当性や HMD 上での動作を検証した完成版を意味しない。
