# Houdini — 波浪シミュレーション

教員の指定に従い、波の流体シミュレーションとサーフェス化をこの作業区分で進めます。最終的には Unity でリアルタイム再生できる表現へ変換します。

物理的な条件と北斎の構図に対する美学的な評価は分けて記録します。

## 現在の確認範囲

### 最新：参照水体からの自由発展と白波

[reference_release](reference_release/README.md) に、参照の巻いた水体と高さに応じた非零の初期速度から進めたFLIP試験を収録しています。主波は96フレーム・24 fpsです。

- 単色表示：[側面（4秒）](reference_release/previews/自由発展01_側面.mp4) ／ [斜視（4秒）](reference_release/previews/自由発展01_斜視.mp4)
- 白波と色面表示：[斜視（1秒）](reference_release/previews/自由発展01_白波と色面_斜視.mp4) ／ [側面（1秒）](reference_release/previews/自由発展01_白波と色面_側面.mp4)

白波は主波の体積場から第2～24フレームを別に生成・計算・後処理しました。動画の第1フレームには白波がありません。**主波の形成と保持は未達です。** 第1・6フレームのC形は第12フレーム（開始から約0.46秒）には保持されず、第17フレーム以降は側壁の影響を受ける可能性もあります。初期断面でも開口の縮小と唇の厚みの増加が生じています。[表示と断面の記録](../Blender/great_wave/docs/milestones/2026-09-24_reference_release.md)を参照してください。

この試行は低い浪からの形成を示しません。初期速度0の対照A0は未実行です。誘導条件Bの解析速度場はNumPyで符号・発散・境界・速度上界を確認しましたが、FLIPへの適用は未実施です。

### 方向を持つ波群の集束

[focused_packet](focused_packet/README.md) に、有限水深の速度分布で初期化した21成分の波群を収録しています。名義の合計振幅0.6mの1条件を72フレーム計算しました。[側面動画](focused_packet/previews/集束波_側面.mp4)と[斜視動画](focused_packet/previews/集束波_斜視.mp4)は各3秒です。急な前面と短い突出は見えますが、参考の深い開口と高い局所峰は未達です。[表示の記録](../Blender/great_wave/docs/milestones/2026-09-24_focused_packet.md)を参照してください。

### 新しいFLIP波槽と比較動画

[wave_tank](wave_tank/README.md) に、初期波包から自由発展させる小規模なFLIPシーンを2条件保存しました。各72フレーム・24 fpsで計算し、表面Alembicを公式Blender MCPから読み込んでいます。

- [試作02：全槽の側面](wave_tank/previews/試作02_側面.mp4)
- [試作02：波頭の拡大](wave_tank/previews/試作02_側面拡大.mp4)
- [試作02：斜視](wave_tank/previews/試作02_斜視.mp4)
- [旧キャッシュの直接表示](wave_tank/previews/旧キャッシュ_側面.mp4)

**2条件とも、参考模型の深い開口と大きい巻下げは未達です。** 計算条件、圧力が働かない構成を除外した対照、粒子の追跡、表面の読込み検査を記録しています。画面による判定は[試行記録](../Blender/great_wave/docs/milestones/2026-09-24_fluid_trials.md)にまとめています。UnityとHMDではまだ確認していません。

### 既存の FLIP シーン

ローカルに保存されていた `wave_flip_2_bak4.hiplc` を、Steam 版 Houdini Indie 22.0.429 の手動更新モードで読み込み、FLIP Solver、FLIP Object、Ocean Spectrum、圧縮・表面キャッシュなどのノードを確認しました。元ファイルは変更していません。

読み込み時に埋め込みスクリプトから `Missing /obj/grid_object1` という警告が出ました。読み込み完了後には同パスが存在しますが、原因は未解決です。旧シーンのシミュレーションや書き出しは実行していません。このバックアップと、以前に得られた `1.abc` の生成元が同一であることも未確認です。旧 FLIP シーンは、このリポジトリにはまだ収録していません。

### 小規模な Alembic 入出力

[tests/interop_probe](tests/interop_probe/README.md) に、小型の制作元シーン、実際の Alembic、照合結果と再現用スクリプトを収録しました。正弦変形する 81 点のメッシュを 3 フレーム書き出し、Houdini で再読込した座標が元データと一致することを確認しています。

**このテストは FLIP 流体シミュレーションではありません。Unity の再生、HMD の動作・性能、波の物理精度は未検証です。**

## 次の確認

次は低い初期水体を共通にした無誘導条件と有限時間の誘導条件を比べ、形成から解放後までを確認します。誘導の仕事、粒子数と体積の指標も記録する計画です。[実装済みの解析場と未実行のFLIP試験](reference_release/README.md)を区別して進めます。既存の[集束波群の記録](focused_packet/README.md)も比較用に残します。白波の長時間の挙動、UnityとHMDでの再生は未検証です。

シミュレーションキャッシュと大容量の書き出し結果は原則として Git に含めません。`results/` はローカルの検証出力用です。今回の小型 Alembic は、入出力の実測結果として制作元と一緒に `tests/interop_probe/` に収録しています。
