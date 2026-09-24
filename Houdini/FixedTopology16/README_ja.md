# 手順16: 固定トポロジーの Houdini → Unity 転送標本

## この資料が示す範囲

これは **解析式で動かす転送検証用メッシュ** であり、FLIP、海洋物理、砕波の検証ではない。新しく作った 33×33 点の面を三角形化し、点番号と接続を固定して上下に変形した。既存の試作のノード、コード、形状、画像は参照していない。

Houdini 側では 61 個の実サンプル、BGEO の再読込、Alembic の書出し、所有ノードだけの CPIO 再読込を確認した。**Unity の最終判定は Unity 側の実測レポートを参照する。** この資料だけで手順16全体、HMD、物理的な波の検証完了とはしない。

## 実行環境と安全な作業範囲

実行中の Steam Houdini 22.0.429 は MCP を通して `licenseCategoryType.Indie` と確認できた。別 GUI を起動する試行は失敗し、診断再試行は起動後約2秒で終了コード3、標準出力・標準エラーに説明なし、8101 ポート未開通だった。コード3は製品ライセンスの取得・確認失敗を示すが、原因の内訳や Steam 契約の状態をこの終了値だけから断定しない。

そこで、確認済みの PID 53912 / MCP 8100 に一意な所有サブネットだけを作った。既存 HIP の保存・読込・クリア、既存形状の取得、全シーン走査、ライセンス設定変更は行っていない。現在の 24fps は変えず、時刻 t に対して `frame=1+24t` で評価した。Alembic ROP の入力は所有 OUT への相対パスだけ、Initialize Simulation OPs はオフ、外部 ROP 入力はなし、`ignore_inputs=True`。

作業後、所有ノード削除と界面・時刻・FPS・カメラ・選択など18項目の復元確認が通った。変更前後とも dirty は true。undo は元の記録を保持したまま増えた。各実行レポートに開始・終了件数を記録した。undo の消去はしていない。

## データ契約

- 基準: メートル、Houdini Y-up。Unity は `scaleFactor=1`, `swapHandedness=true` により **(x,y,z) → (-x,y,z)**。
- 面: `kinematic_grid`、1089点、2048三角形、XZ は固定で一意。8m×8m、最大変位0.2m。
- サンプル: t=0～2秒、30Hz、両端を含む61個。現在の24fpsのフレーム番号は1～49、刻み0.8。
- 参照 JSON の `positions`、`normals`、`center`、`size` は `{x,y,z}`。`triangles` は Houdini の実三角形の点番号を平坦化した配列。
- 初回は点法線が内側を向いている欠陥が Unity の片面描画で判明した。元の試作を参照せず、新規ソースの三角形順序を反転して修正した。修正版は61個すべてで水面の全点 N.y > 0.9、全マーカー角点の N・(P-中心) > 0 を確認。法線は Houdini Normal SOP が計算した点法線。61 BGEO ファイルすべて再読込し、位置・法線・接続を元の評価結果と照合。
- 初期/終端の位置差は最大約1.19e-7m。ただし速度連続性などのループ品質試験ではなく、Unity側はまず一回再生として検証する。
- Alembic 内は面と下記5マーカーを別名の polymesh として記録。すべて頂点位置と法線の記録数61を `abcecho` で確認。

| 名前 | Houdini 中心(m) | 寸法(m) | 識別色 |
| --- | --- | --- | --- |
| unit_cube_1m | (-5, 0.5, -5) | (1, 1, 1) | 黄 |
| axis_x_positive | (5, 0.5, 0) | (0.35, 1, 0.35) | 赤 |
| axis_y_positive | (0, 2, 0) | (0.35, 0.7, 0.35) | 緑 |
| axis_z_positive | (0, 0.5, 5) | (0.35, 1, 0.35) | 青 |
| asym_p123 | (1, 2, 3) | (0.3, 0.5, 0.7) | 紫 |

### Alembic 時刻は参照時刻と異なる

Houdini の archive 読返し範囲は約 `[0.04166667, 2.041667]` 秒だった。`abcinfo` は動的時間サンプリングに61個、開始 `1/24` 秒と報告する。したがって参照時刻0秒は archive の1/24秒に対応する。Unity側でメディア開始時刻を考慮する必要がある。個々の実タイムスタンプの厳密な値は Unity のネイティブ Alembic 読取レポートで確認する。参照JSONの61個だけをもって archive の61個が証明されたとは扱っていない。

## 保存したものと未実行項目

Gitで保存する実Alembicは [Unity側](../../Unity/Assets/GreatWave/Art/FixedTopology16/fixed_topology_16.abc)、完全な61サンプルの参照JSONは [同じフォルダー](../../Unity/Assets/GreatWave/Art/FixedTopology16/reference_samples.json) に一組だけ置いた。Unityで同じ数式を再生成するためのファイルではない。61個のBGEOと重複キャッシュはGit対象外。実行時のローカル保存先は `G:\Unity\GreatWave_2026_M1_Pipeline_Staging\FixedTopology16\CorrectedWinding\Cache`。`Source/fixed_topology_16.cpio` は所有サブネットだけのソース。

CPIO は別の所有サブネットへ読み直し、内部相対参照が読み直し先の OUT を指すこと、61個すべての位置と接続が一致することを確認した。CPIO 再読込後の法線比較は別項目として実行していない。**.hiplc の保存・再起動読込は未実行**。別セッションを使えず既存 HIP を変更しないため、CPIO と新規生成ソースで代替した事実を明示する。

## 実映像

`Evidence/fixed_topology_16_houdini_preview.mp4` は Houdini の実ビューポートを撮影した1280×720、30fps、60フレーム、正確に2秒の映像。61番目の終端サンプルは動画に含めない。背景の格子は Houdini の作業用グリッドで、最終作品の美術表現ではない。

初回データは法線が内向き、初回撮影は近すぎたため不採用。[Unityで発見した不採用画像・判定](../../Docs/Evidence/M1/FixedTopology16/Rejected_Orientation/README_ja.md)を保存した。その他の初回試行はローカル `G:\Unity\GreatWave_2026_M1_Pipeline_Staging\FixedTopology16` に残した。このフォルダーは修正版の成果物だけを採用する。CPIOだけを読み直し、所有形状の境界に合わせて取景を修正した。1枚を視覚確認してから60枚を撮り直した。撮り直し前後で ABC/参照JSON のハッシュは変わっていない。60枚すべて異なる画像ハッシュ、全動画デコード成功。静止画は0秒、0.5秒、1秒を保存した。

## 再現用コード

- `Source/generate_fixed_topology.py`: 新規形状、サンプリング、BGEO、Alembic、CPIO検証。
- `Source/run_owned_specimen.py`: 実 MCP stdio SDK から段階実行し、finally で UI を復元。
- `Source/ui_guard.py`: UI の最小スナップショットと所有ノードの削除・復元確認。
- `Source/recapture_owned_specimen.py`: 所有 CPIO のみから取景を修正して撮影。
- `Source/finalize_evidence.py`: 実ファイルの数値フレーム順整列、動画化、デコード検証。

PID・ポート・インストールパスは今回の接続を守るため固定している。PID53912のガードは履歴の条件であり、将来そのまま実行できるとは扱わない。再実行前に接続先のPID・ポート・出力先を新しい実測メタデータへ合わせ、ガードを維持し、既存シーンを読まず所有ノードだけを対象にする。生成スクリプトのフェーズを単独で実行せず、UIスナップショットとfinally復元を備えた入口を使用する。

`handoff_manifest.json` は実行時のステージング82ファイルのハッシュを保存した履歴で、すべてがGitにあるという意味ではない。取り込み時にこのREADMEのリンク・保存先を更新し、`Source/ui_guard.py` の説明docstringとコメント1行を日本語へ翻訳した。処理は変えていないが、実行時ソースと翻訳後のファイルが同一バイトだとは主張しない。現在の公開ファイルのハッシュは `repository_manifest.json`。実行時の元ファイルとハッシュはステージングとhandoff記録に保持した。

## 公式資料

- [SideFX: RopNode.render のフレーム範囲と ignore_inputs](https://www.sidefx.com/docs/houdini/hom/hou/RopNode.html)
- [SideFX: ビューポート境界への取景](https://www.sidefx.com/docs/houdini/hom/hou/GeometryViewport.html)
- [SideFX: コマンドラインと終了コード](https://www.sidefx.com/docs/houdini/ref/commandline.html)
- [SideFX 開発者: Steam 複数インスタンスとライセンス方式](https://steamcommunity.com/app/502570/discussions/0/3276824488729479766/)
