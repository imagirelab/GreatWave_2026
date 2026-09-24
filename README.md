# GreatWave_2026

『神奈川沖浪裏』をHoudini・Blender・UnityでリアルタイムVR作品にする制作記録です。旧試作を参照せず、番号ごとに新規検証してコミットします。

利用者の続行指示により、18で同じ実FLIP試料のAlembicとFluid VATをUnityのPC実行版で比較しました。両方式とも全49時刻の転送検査に合格しました。**18の中間成果で確認を待ちます。M0のHMD・物理操作、19の密度/HMD試験、20の採用決定は未完了です。** 進行役は指示とレビュー、実装担当のGPT-6は制作とコミットを担当します。

## 18の2方式比較を見る

- [Alembic／Fluid VATの左右比較・2秒動画](Docs/Evidence/M1/Playback18/18_Comparison_2s.mp4)
- [初期2球](Docs/Evidence/M1/Playback18/18_Comparison_000.png)／[結合](Docs/Evidence/M1/Playback18/18_Comparison_003.png)／[分離](Docs/Evidence/M1/Playback18/18_Comparison_024.png)／[2秒末端](Docs/Evidence/M1/Playback18/18_Comparison_048.png)
- [数値・性能・容量・再現方法・制限](Docs/Progress/Step_18_ja.md)／[Houdini出力と専用デコーダーの出典](Houdini/PlaybackComparison18/README_ja.md)

実Windowsビルドの同じ視点によるオフスクリーン描画です。元の三角化面との位置差は両方式0m、法線角差はVATで最大約0.028°でした。これは小さな技術試料の転送検査で、北斎の砕波・物理精度・HMDの合格ではありません。CPU負荷、容量、未測定のGPU時間/総メモリを区別し、採用方式は決めていません。

本機の実行一式は `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Playback18\`。`GreatWave18.exe`を起動し、1でAlembic、2でVAT、Spaceで停止・再開、Rで先頭、Qで終了。配布にはフォルダー全体が必要です。

## 17の小さな流体試料を見る

- [Houdini実ビューポートの2秒動画](Houdini/VariableTopology17/Evidence/17_FLIP_Surface_2s.mp4)
- [粒子と表面の同時刻比較・全数値・限界](Docs/Progress/Step_17_ja.md)
- [生成元・キャッシュ・再現方法](Houdini/VariableTopology17/README_ja.md)

2球からの結合と、その後の分離を実FLIPの粒子ID・連結成分で確認しました。0〜2秒の49時刻はすべて異なる表面トポロジーです。後半は領域外への流出があり、面化体積も大きく増えるため、質量保存・海洋物理精度の合格ではありません。利用者の続行指示を受け、同じ試料を上記18の形式比較へ渡しました。

## M1の静止構図を見る

- [修正01：20秒の自動カメラ動画](Docs/Evidence/M1/Revision01/M1_Revision01_Walkthrough.mp4)
- [原画比較](Docs/Evidence/M1/Revision01/M1_Comparison.png)／[船上](Docs/Evidence/M1/Revision01/M1_Boat.png)／[側面](Docs/Evidence/M1/Revision01/M1_Side.png)／[背面](Docs/Evidence/M1/Revision01/M1_Rear.png)／[候補範囲図](Docs/Evidence/M1/Revision01/M1_Region.png)
- [修正前後・結果・再現方法](Docs/Progress/Step_15_Revision01_ja.md)／[修正前の15を保存した記録](Docs/Progress/Step_15_ja.md)

![M1の構図修正01・Unity実描画](Docs/Evidence/M1/Revision01/M1_Comparison.png)

波・船・富士・白波は新しく作った3Dの形状模型です。画像はUnity実行ビルドのオフスクリーン描画で、流体シミュレーション、完成版の浮世絵レンダリング、HMD映像ではありません。波と船は静止しています。動画の24fpsは再生用の値で、実時間性能の測定ではありません。

本機の実行ファイル：`G:\Unity\GreatWave_2026_Fresh\Unity\Builds\M1_Revision01\GreatWaveM1Revision01.exe`。移す場合は `M1_Revision01/` 一式が必要です。1〜5で視点を切替、右ドラッグ・矢印で見回し、Rで戻す、Spaceで停止、Qで終了します。通常のウィンドウと物理キー・マウス操作は利用者確認待ち。 [ビルド](Tools/Build_M1_Revision01.ps1)／[画像・動画の再取得](Tools/Capture_M1_Revision01.ps1)。

## 16のHoudini→Unity受け渡しを見る

- [Unityの2秒動画](Docs/Evidence/M1/FixedTopology16/16_Unity_Cache.mp4)／[静止画](Docs/Evidence/M1/FixedTopology16/16_Unity_Middle.png)
- [Houdini実ビューポートの2秒動画](Houdini/FixedTopology16/Evidence/fixed_topology_16_houdini_preview.mp4)
- [結果・数値・起動方法・保留項目](Docs/Progress/Step_16_ja.md)

実行中のSteam Houdini22.0.429へMCPで接続し、新規の変形格子をAlembicへ書き出しました。Unity EditorとWindows実行版で61時刻と60個の補間点を照合しました。解析式の検査用形状で、流体ではありません。通常起動は2秒で停止し、Rで再生、Spaceで停止・再開、Qで終了。本機の実行ファイルは `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\FixedTopology16\GreatWave16.exe`。移す場合はフォルダー全体が必要です。

既存HIPを保存・読み直さず、所有ノードだけのCPIOを保存・再読込しました。UIと所有ノードの復元を確認し、変更済みフラグとUndo履歴は保持しています。.hiplcの再起動・再読込、HMD、物理キー操作は未検証。17の新規FLIP試料と18の形式比較は上記の別記録へ進み、19〜20は未実行です。

## M0の基礎検証記録

- [20秒の確認動画](Docs/Evidence/M0/M0_Desktop_Walkthrough.mp4)
- [着座視点](Docs/Evidence/M0/M0_Seated.png)／[静止船全体](Docs/Evidence/M0/M0_Boat_Exterior.png)／[1m・軸の校正モデル](Docs/Evidence/M0/M0_Calibration.png)
- [結果・操作・再現方法・保留項目](Docs/Progress/Step_10_ja.md)

M0の画像・動画は新規Windows実行版の実シーンを、Unityでオフスクリーン描画した自動カメラ記録です。通常ウィンドウの手動操作やHMDの録画ではありません。平面と箱形の静止船を使った当時の基礎検証を保存しています。

本機の実行ファイルは `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\M0\GreatWaveM0.exe`。右ドラッグ・矢印で見回し、Rで戻る、Spaceで停止・再開、Qで終了します。通常画面での物理キー・マウス操作は利用者の確認待ちです。実行一式はGit対象外で、[ビルド](Tools/Build_M0.ps1)と[証拠の再取得](Tools/Capture_M0.ps1)の手順を保存しています。

## 制作設計

- [制作依頼のプロンプト（原文）](Docs/Design/Original_Request_ja.md)
- [制作設計書：12段階・60ステップ](Docs/Design/GreatWave_VR_Production_Design_ja.md)

設計書には、Houdiniによる波浪の計算とサーフェス化、白波の別計算とモデルアニメーション、Blenderによる船などの制作、Unityでの浮世絵表現・HMD体験・操船を記載しています。各ステップの成果物と確認事項、各段階の合格条件、物理・美術・性能の評価方法をまとめています。

- [制作手順・役割・確認条件](Docs/Workflow/Production_Workflow_ja.md)
- [番号ごとの進捗](Docs/Progress/README.md)

## フォルダー構成

| フォルダー | 用途 |
| --- | --- |
| `Houdini/` | 波浪の流体シミュレーションとサーフェス化 |
| `Blender/` | 船などの静的モデルの制作 |
| `Whitewater/` | 白波の別計算とアニメーション |
| `Unity/` | リアルタイム表示、HMD体験、船の操作の統合 |
| `Docs/` | 設計と各段階の確認記録 |

完成点ごとに実際の結果を保存し、確認後に次の工程へ進みます。HMD実機の必須試験は保留一覧に残しています。
