# 03：ソフトと書き出し条件

日付：2026-09-24／結果：インストールと版の調査を完了。起動・実際の制作出力は後続番号で検証する。

| ソフト | 読み取り専用で確認した状態 | 今回の採用・保留 |
| --- | --- | --- |
| Unity | `E:\6000.4.3f1\Editor\Unity.exe`、6000.4.3f1（39d1a88d4dd1） | 新規M0に採用。ライセンスとコンパイル・ビルドは06〜10の実行で確認 |
| Unity Windows出力 | WindowsStandalone・win64開発用Monoのフォルダーあり。対応するIL2CPP開発用フォルダーなし | Windows x64・Monoを使用する計画 |
| Blender | `G:\SteamLibrary\steamapps\common\Blender\blender.exe`、`--version`実行結果5.2.2 LTS | 07で新しい1m検証モデルを作成し、保存とFBX出力を実証 |
| Houdini | `C:\Program Files\Side Effects Software\Houdini 21.0.729\bin` | インストール確認のみ。M0では起動・流体計算不要 |
| Houdiniライセンス | サービスは応答。既定とlocalhostの読取専用summaryではlicense件数0 | 利用可能なライセンス種別とFLIP・Alembic・VAT出力は未確認 |
| SideFX Labs | 導入版・エクスポーター版の有効性は未確認 | M1の開始条件として後日検証 |
| ffmpeg | `G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe`、版情報の実行に成功 | Unity実出力のレビュー用動画の符号化に使用 |

環境調査担当の読み取り専用結果に基づく。購入・再インストール・ライセンス変更は行っていない。Houdiniが存在することを流体制作可能の証拠にしない。ライセンスの不足は将来の16以降で解決が必要だが、今回のPC画面検証を妨げない。

## 06〜10で固定する候補

インストールされたUnity Editorの公式同梱パッケージに、Input System 1.19.0、XR Core Utils 2.5.3、XR Management 4.5.2、OpenXR 1.16.1、XR Legacy Input Helpers 3.0.1がある。08ではこの組合せを候補とし、実際の解決結果をmanifest・lockと検証記録で固定する。現時点では導入・コンパイル済みとはしない。

公式資料：[Unity 6000.4 OpenXR](https://docs.unity3d.com/6000.4/Documentation/Manual/com.unity.xr.openxr.html)、[Unity 6000.4.0f1リリース情報](https://unity.com/releases/editor/whats-new/6000.4.0f1)。新規M0の描画方式は単位・静止船を確かめる暫定選択とし、流体再生方式との組合せはM1で判断する。
