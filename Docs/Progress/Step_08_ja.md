# 08：OpenXR設定の保存と再読込

日付：2026-09-24／結果：PC向け設定と再読込の検査は合格。HMD実機は保留。

新規プロジェクトでInput System 1.19.0、XR Core Utils 2.5.3、XR Management 4.5.2、OpenXR 1.16.1、XR Legacy Input Helpers 3.0.1を導入し、manifestとlockへ固定した。元はこのUnity Editorの公式同梱版であり、旧プロジェクトからコピーしていない。

StandaloneにOpenXR loaderと設定アセットを保存。XROrigin、Camera Floor Offset、Camera、TrackedPoseDriverを作り、中心眼の位置・回転・追跡状態をInput Systemへ割り当てた。自動XR初期化はオフ、TrackedPoseDriverもPCの通常起動ではオフ。機器がないPCで無条件にVRを起動しない。

設定生成後にEditorを終了し、別のEditor起動で `M0XRSetup.Validate` を実行した。loader、設定、Origin、入力binding、起動条件の保持を確認した。

- [再読込後の実測JSON](../Evidence/M0/08_xr_configuration.json)
- Project Validation：エラー0、警告3。機器未定によりinteraction profile未選択。残る2件は任意の新しい入力Control型への移行案内。
- HMDの機種決定後、使用するprofileを選択し、実入力・両眼・頭部追跡を検証する。警告を無視して機器対応済みとしない。
- グローバルなOpenXR runtime登録は変更していない。Mock Runtimeで実機試験を代用していない。
- 元ログ：`Unity/Logs/08-xr-configure.log`、`08-xr-reload.log`。双方で処理完了・終了コード0。

公式資料：[Unity OpenXR](https://docs.unity3d.com/6000.4/Documentation/Manual/com.unity.xr.openxr.html)、[OpenXR入力](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/input.html)、[XR手動起動](https://docs.unity3d.com/Packages/com.unity.xr.management@4.5/manual/EndUser.html)。
