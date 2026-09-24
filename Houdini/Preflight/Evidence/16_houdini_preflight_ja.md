# 16 — Houdini の起動・ライセンス・書き出し事前検証

検証日: 2026-09-24。状態: **16 は実行を試みたが停止中。17–20 は依存条件が未成立のため未実行。**

**最新の申告と訂正は [16の追記](16_license_connection_ja.md) を参照。利用者のSteamの2年間の利用権は期限切れ・未更新。以下は通常版21.0/20.5の起動履歴であり、Steam版の権利や動作を検証した結果ではない。再開条件は最新追記を優先する。**

新規の検証用フォルダーだけで実施した。旧試作のコード、モデル、キャッシュ、過去コミットは参照していない。Unity の工程 11–15 は、この検証とは独立して進められる。HMD は未所持で、VR の表示・装着・追跡・快適性は未検証である。

## 結果

Houdini 21.0.729 はユーザースクリプトの実行確認に至る前に、終了コード 139 と `Fatal error: Segmentation fault` を出した。通常起動、ユーザー設定とパッケージをプロセス内で分離した起動、分離した hbatch の計 3 回とも同じ分類だった。**この結果はライセンス拒否を証明しない。クラッシュの原因は未特定。**

別途インストール済みの Houdini 20.5.278 を分離して起動すると、終了コード 3 と次の明示的なライセンスエラーで終了した。

```text
No licenses could be found to run this application.
    Please check for a valid license server host
```

ローカルのライセンスサービス 2 種は実行中だったが、ローカルサーバーへの読み取り専用の一覧問い合わせは 0 件だった。これは問い合わせ先で確認できた状態であり、利用者が別サーバーやアカウントに持つライセンスの有無を断定するものではない。ライセンスの購入・追加・認証・サーバー設定変更は行っていない。

## 起動試行の記録

すべて非表示・30 秒上限の別プロセスで実行し、タイムアウトは発生していない。

| 試行 | 実行ファイル | 分離 | 終了 | プロセス計測秒 | スクリプト実行確認 | 観測結果 |
|---|---|---|---:|---:|---|---|
| hython21_default | 21.0.729 hython | なし | 139 | 未記録 | なし | Segmentation fault |
| hython21_isolated | 21.0.729 hython | あり | 139 | 未記録 | なし | Segmentation fault |
| hbatch21_isolated | 21.0.729 hbatch | あり | 139 | 1.367 | なし | Segmentation fault |
| hython205_isolated | 20.5.278 hython | あり | 3 | 4.997 | なし | 明示的ライセンスエラー |

先頭 2 回は専用ストップウォッチを導入する前の試行なので、プロセス所要時間を補完していない。全試行でユーザー側の完了マーカーはなく、ジオメトリ検証 JSON も生成されなかった。21 系のクラッシュログはネイティブ初期化中のスタックを示す。掲載値は実測・観測結果であり、後から成功値を与えていない。

## インストールと Labs

- Houdini 21: `C:\Program Files\Side Effects Software\Houdini 21.0.729\bin\hython.exe` / `hbatch.exe`
- Houdini 20.5: `C:\Program Files\Side Effects Software\Houdini 20.5.278\bin\hython.exe`
- Labs マニフェスト: `C:\Program Files\Side Effects Software\sidefx_packages\SideFXLabs20.5.json`
- Labs 宣言バージョン: `20.5.363`
- Labs 有効条件: `houdini_version >= '20.5' and houdini_version < '20.6'`

このマニフェストは 21.0 を対象外とする。Labs のフォルダーが存在することは確認できたが、Houdini 内での正常ロードや VAT ノードの実行は確認できていない。分離試行ではパッケージ処理を無効化したため、Labs の動作試験を兼ねていない。

## できていないことと工程の扱い

`Exports` は空である。単純な箱の cook / BGEO 保存さえ確認できていないため、次の項目はすべて **未実行** とする。

- 2–3 秒の固定トポロジーアニメーションの生成
- 微小な FLIP の計算とフレームごとの再メッシュ
- Alembic、FBX、VAT の書き出し可否・品質・座標系の実測
- Unity での各サンプルの再生、負荷、補間、見た目の比較

16 は「試行済み・停止中」であり、成功または完成とはしない。17–20 は依存するサンプルが存在しないため未実行とし、再生形式の採用判断を行わない。静的モデルや数式による変形を、Houdini の流体サンプルの代替証拠として扱わない。

再開条件は、実際に利用可能なライセンス条件の確認と、使用する Houdini の正常起動である。その後に新規の箱の cook、短い固定トポロジー、短い FLIP、書き出し、Unity の順で検証する。ライセンス上の制限を回避する別経路は試していない。

## 再現方法

同梱の `Scripts/Run_Houdini_Probe.ps1` は、実行ファイル・引数・試行名を受け取り、非表示起動、30 秒上限、終了コードとマーカーの記録を行う。上限を超えた場合は、この試行で起動したプロセス ID だけを停止する。作成する Logs / Evidence / Exports はスクリプトの親フォルダー内に限る。プロセス限定の環境変数を使い、ユーザーの Houdini 設定やグローバル環境変数を書き換えない。

以下は通常版21.0を使った補助スクリプトの呼出形式を残す歴史的な例で、次の推奨対象を意味しない。リポジトリのルートからの相対配置へ記述だけを更新した。Steam版への対応は未検証であり、今回この例を追加実行していない:

```powershell
$stage = Join-Path (Get-Location) 'Houdini\Preflight'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$stage\Scripts\Run_Houdini_Probe.ps1" -Executable 'C:\Program Files\Side Effects Software\Houdini 21.0.729\bin\hython.exe' -Arguments ('"' + "$stage\Scripts\probe_houdini.py" + '"') -AttemptName 'hython21_recheck_01' -IsolatePackages
```

履歴を残すため、再試行時は新しい `AttemptName` を使う。正常起動した場合に限り `probe_houdini.py` が新規シーンに 1 m の箱を作り、cook 結果とライセンス分類、BGEO 保存を記録する。この最小プローブは、FLIP や外部形式の書き出しが成功したことを示すものではない。パッケージ分離の解除と Labs の検証は別の後続試行とする。

記録後の保守修正として、空出力の判定を bool に統一し、出力先フォルダーの自動作成、試行名の制約、Python 冒頭の開始マーカーを追加した。これらの修正後に Houdini を追加起動していない。既存の試行結果を成功として再解釈していない。

## 公式資料

- [Houdini 環境変数](https://www.sidefx.com/docs/houdini/ref/env.html): `HOUDINI_USER_PREF_DIR`、`HOUDINI_NO_ENV_FILE`、`HOUDINI_PACKAGE_SKIP` などの分離設定。設定は今回のプロセス内だけに適用。
- [SideFX 製品比較](https://www.sidefx.com/products/compare/) / [Apprentice の制限](https://www.sidefx.com/faq/question/apprentice-restrictions/): 実行ファイルの存在だけでは、使用可能なライセンスや形式の許可範囲を決められない。
- [Labs VAT 3.1](https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.1.html): 固定トポロジーと Dynamic Remeshing は異なる扱い。流体の動的再メッシュはメッシュ・ルックアップとアニメーションテクスチャの段階があるため、固定トポロジーだけで検証完了とはできない。このリンクは現行公式資料であり、ローカル Labs 20.5 に当該ノードが正常ロードされたという証拠ではない。
