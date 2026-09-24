# GreatWave_2026

『神奈川沖浪裏』をHoudini・Blender・UnityでリアルタイムVR作品にする制作記録です。旧試作を参照せず、番号ごとに新規検証してコミットします。

現在は01〜10のPC中間成果を保存し、**利用者の確認待ちで停止しています。M0はHMD未所持のため未完了です。** 11以降には進んでいません。進行役は指示とレビュー、実装担当のGPT-6は制作とコミットを担当しました。

## PC中間成果を見る

- [20秒の確認動画](Docs/Evidence/M0/M0_Desktop_Walkthrough.mp4)
- [着座視点](Docs/Evidence/M0/M0_Seated.png)／[静止船全体](Docs/Evidence/M0/M0_Boat_Exterior.png)／[1m・軸の校正モデル](Docs/Evidence/M0/M0_Calibration.png)
- [結果・操作・再現方法・保留項目](Docs/Progress/Step_10_ja.md)

![M0の着座視点](Docs/Evidence/M0/M0_Seated.png)

画像・動画は新規Windows実行版の実シーンを、Unityでオフスクリーン描画した自動カメラ記録です。通常ウィンドウの手動操作やHMDの録画ではありません。平面と箱形の静止船で基礎を検証し、波・白波・浮力・操船は未実装です。

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
