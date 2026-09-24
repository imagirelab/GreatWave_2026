# 06：新規Unity基準シーン

日付：2026-09-24／結果：新規プロジェクト作成・コンパイル・シーン保存を確認。

`Unity/` をUnity 6000.4.3f1の `-createProject` で新規作成した。Built-inはM0用の暫定選択。Windows x64、Mono、Direct3D 11、Linear、1280×720のウィンドウ表示を固定した。大波の描画方式の採用判断ではない。

`M0BaselineBuilder.Create` を新規実装し、平面、1m箱、方位の軸、カメラ、光源を生成した。基準シーンは `Unity/Assets/GreatWave/Scenes/Tests/M0_DesktopPreflight.unity`。Unityで箱のRenderer.boundsを取得し、各軸1.000mであることを記録した。

- [実測JSON](../Evidence/M0/06_baseline.json)
- 実行ログ：`Unity/Logs/create-project.log`、`Unity/Logs/06-baseline.log`（ローカル・Git対象外）
- 新規作成と生成処理の両方が終了コード0で終了。`error CS`・例外・Shader errorなし。
- 初期ライセンス接続で一時的なエラー表示があったが、その後権利情報を解決し処理完了。認証情報を含みうる元ログは公開しない。

再現：Unityを閉じ、Editorへ `-batchmode -nographics -projectPath <repo>/Unity -executeMethod GreatWave.Editor.M0BaselineBuilder.Create -quit -logFile <path>` を渡す。この操作は基準シーンを06の状態へ再生成するため、後続の船を含むシーンが必要な場合は後続工程も順番に実行する。

今回は画面の見栄え・PC実行ビルド・HMDを検証していない。実出力画像は10でPCビルドから保存する。
