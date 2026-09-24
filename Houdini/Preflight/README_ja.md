# Houdiniの新規検証準備

**16はMCP接続と一時箱のUI表示・削除・復元を確認、短い変形クリップ・保存・書き出しは未検証。17〜20は未実行。** 期限切れ・未更新という利用者の申告とは別に、実行中のSteam版22.0.429がMCP経由でUI有効・Indie分類を返した。接続不可という一律の扱いを訂正した。UI実演後の変更済みフラグとUndo履歴6件は残っている。

- [最新：MCP接続・互換性の調整・実行環境の応答](Evidence/16_mcp_connection_ja.md)
- [初期のライセンス調査・Steam版と通常版の区別](Evidence/16_license_connection_ja.md)
- [通常版21.0/20.5の起動試行記録](Evidence/16_houdini_preflight_ja.md)
- [試行JSON](Evidence/16_houdini_preflight.json)／[最新の状態JSON](Evidence/16_license_connection.json)
- [最小プローブ起動補助](Scripts/Run_Houdini_Probe.ps1)／[新規箱のcook・BGEO保存プローブ](Scripts/probe_houdini.py)

現在のSteamインストール先は `G:\SteamLibrary\steamapps\common\Houdini Indie`。MCP SDKの実通信と実行環境3値のPython問い合わせは確認したが、この会話のネイティブツールは未読込。互換性のない27件を設定で無効化し、再読込後の候補は180件。全機能の動作確認ではない。

既存の試行は独立した新規ステージングで通常版の実行ファイルに対して実施した。今回ここへ精選した記録・補助スクリプトをコピーし、追加実行はしていない。通常版21.0のクラッシュは原因未特定。通常版ローカルの期限切れApprentice記録も、Steamの権利確認の代用にはならない。

次の検証は、新規専用シーンで短い変形クリップ・保存・再読込を確かめる。以前の通常版向けプローブがSteam版にそのまま対応すると仮定しない。アカウント同期・購入・更新・認証変更は実施していない。UI実演では既存ジオメトリ・プラグインを編集せず、作成した一時物だけを削除した。

補助スクリプトの作業先はこの `Preflight/` 以下。新しい試行名を使い、Logs/Preferences/ExportsはGit対象外とした。Evidenceには判定に必要な数値と分類だけを残し、認証情報や診断全文を公開しない。
