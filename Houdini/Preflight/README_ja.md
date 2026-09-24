# Houdiniの新規検証準備

**16は試行済み・停止中。17〜20は未実行。** 利用者はSteamで購入した2年間の利用権が期限切れで、更新していないと確認した。

- [最新のライセンス状態・Steam版と通常版の区別](Evidence/16_license_connection_ja.md)
- [通常版21.0/20.5の起動試行記録](Evidence/16_houdini_preflight_ja.md)
- [試行JSON](Evidence/16_houdini_preflight.json)／[最新の状態JSON](Evidence/16_license_connection.json)
- [最小プローブ起動補助](Scripts/Run_Houdini_Probe.ps1)／[新規箱のcook・BGEO保存プローブ](Scripts/probe_houdini.py)

現在のSteamインストール先は `G:\SteamLibrary\steamapps\common\Houdini Indie`、実行ファイルの製品バージョン22.0.429。これはファイルの存在・版の確認だけで、起動・Python・cook・書き出し・接続の成功ではない。

既存の試行は独立した新規ステージングで通常版の実行ファイルに対して実施した。今回ここへ精選した記録・補助スクリプトをコピーし、追加実行はしていない。通常版21.0のクラッシュは原因未特定。通常版ローカルの期限切れApprentice記録も、Steamの権利確認の代用にはならない。

有効な適切な利用権を用意できた後、使用する配布版の通常起動を確認し、その実行環境に合わせて最小の新規cook試験を組む。今回のスクリプトがSteam版にそのまま対応すると仮定しない。アカウント同期・購入・更新・認証変更は実施していない。

補助スクリプトの作業先はこの `Preflight/` 以下。新しい試行名を使い、Logs/Preferences/ExportsはGit対象外とした。Evidenceには判定に必要な数値と分類だけを残し、認証情報や診断全文を公開しない。
