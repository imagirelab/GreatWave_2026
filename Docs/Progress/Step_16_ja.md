# 16：HoudiniからUnityへの2秒キャッシュ検証

日付：2026-09-24。**MCP接続・UI実演に続き、新規の固定トポロジー変形をHoudiniで書き出し、Unity EditorとWindows実行版で再生・数値照合した。PCの中間確認点として利用者の確認を待つ。17以降は未実行。** 流体・砕波・完成版の描画・HMDは未検証。M0とM1全体の完了ではない。

## 今回見るもの

- [Unityの2秒動画](../Evidence/M1/FixedTopology16/16_Unity_Cache.mp4)／[0秒](../Evidence/M1/FixedTopology16/16_Unity_Start.png)／[1秒](../Evidence/M1/FixedTopology16/16_Unity_Middle.png)／[2秒](../Evidence/M1/FixedTopology16/16_Unity_End.png)
- [Houdini実ビューポートの2秒動画](../../Houdini/FixedTopology16/Evidence/fixed_topology_16_houdini_preview.mp4)
- [Houdini検証結果](../../Houdini/FixedTopology16/Evidence/16_houdini_validation.json)／[Unity Editor数値](../Evidence/M1/FixedTopology16/16_unity_editor_validation.json)／[Windows実行版数値](../Evidence/M1/FixedTopology16/16_unity_runtime_validation.json)

青い面は8×8m、33×33点・2048三角形の検査用格子。Houdiniで解析式による上下変形を作り、点番号と接続を固定した。Unityは**実際のAlembicを読み、波形の式を再生成しない**。黄の1m立方体と位置・寸法が異なる4個のマーカーで、単位と座標の向きを調べた。マーカーは点法線による平滑な陰影で、完成モデルの美術表現ではない。

## 確認した条件

| 項目 | 実測・判定 |
| --- | --- |
| 制作側 | 実行中のSteam Houdini22.0.429、MCP経由、Indie分類 |
| 書出し | 0〜2秒・30Hzの61サンプル。各BGEOを再読込し位置・法線・接続を照合 |
| 元データ保存 | 所有ノードだけのCPIOを別の所有コンテナへ再読込し、61時刻の位置・接続を照合 |
| 表示側 | Unity6000.4.3f1、公式Alembic2.4.4、Built-in、Windows x64 Mono |
| 座標 | scale=1、swapHandedness=true、flipFaces=false。Houdini(x,y,z)→Unity(-x,y,z) |
| 実アーカイブ時刻 | 61個。1/24+k/30秒（k=0〜60）。Unityの相対時刻0〜2秒で読む |
| 位置・補間 | 全61サンプル＋中点60個。最大位置差3.40×10⁻⁷m未満、許容0.0001m |
| 法線・表裏 | 有限値・単位長、元法線と一致、格子の全点のY成分0.95458以上、格子の面法線との内積0.99917以上 |
| 接続・寸法 | 全時刻2048三角形。点順に依存しない照合と生の三角形数、8×8m、全5マーカーの中心・寸法・外向き法線を確認 |
| PCビルド | 成功、エラー0、警告3。自動起動・検査・描画・終了を確認 |

実アーカイブ時刻は参照JSONから推測していない。SideFXのabcinfo/abcechoによる実サンプル数に加え、Unity公式Importerがネイティブ時間サンプリングから作った61個のAnimationEvent時刻を読み、[実測値](../Evidence/M1/FixedTopology16/16_archive_sampling.json)を保存した。補間の期待値は隣接する実書出し位置の線形補間。

初回はHoudini側の頂点順が意図と逆で、法線が下向き・内向きだった。転送値の一致だけでは発見できず、Unityの片面描画で面が消えて発見した。[不採用画像と初期判定](../Evidence/M1/FixedTopology16/Rejected_Orientation/README_ja.md)を残し、Houdiniの新規ソースを直して全データを再生成した。Unityにも上向き・外向き・表裏の検査を追加した。両面材質で隠していない。

このAlembicの定数マーカーは、実頂点が正しくても描画用境界が大きさ0になった。読み込んだ実頂点から RecalculateBounds し、描画前の境界を更新している。位置の加工や波形の再生成ではない。検査JSONに更新前後の境界を残した。

## 映像・起動・再現

Unity画像は実行ビルドの実Alembicを Camera.Render → RenderTexture → ReadPixels で描画したもの。通常の表示窓の録画ではない。61枚取得し、動画には先頭60枚を使う。1280×720、H.264、30fps、2.000秒、全デコードを確認。30fpsは記録・再生の設定で、性能測定ではない。

通常起動は一回再生して2秒で停止する。Spaceで停止・再開、Rで先頭から再生、Qで終了。物理キーの手動操作は利用者確認待ち。起動時のOpenXRネイティブ探査は XR_ERROR_RUNTIME_UNAVAILABLE を残すが、PCキャッシュ検査は成功した。ログ全体が無エラー、VR表示が成功した、とは扱わない。

本機の実行ファイルは `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\FixedTopology16\GreatWave16.exe`。別PCへ移すには **FixedTopology16フォルダー全体** が必要。実AlembicもStreamingAssetsへ含まれる。

1. Unity6000.4.3f1で Unity/ を開く。シーンは Assets/GreatWave/Scenes/Tests/M1_FixedTopology16.unity。
2. シーン再生成・全座標検査はUnityの `-executeMethod GreatWave.Editor.FixedTopology16Builder.CreateAndValidate`。M0・M1静止構図を上書きしない。
3. [Build_FixedTopology16.ps1](../../Tools/Build_FixedTopology16.ps1) でWindowsビルドを作る。
4. [Capture_FixedTopology16.ps1](../../Tools/Capture_FixedTopology16.ps1) で実行版の照合・画像・動画・出典を再取得する。制作ソースとビルド時の一覧・ハッシュが異なれば停止する。

[出典](../Evidence/M1/FixedTopology16/16_provenance.json) にGit開始点＋未コミット変更の有無、Unityソース一覧、ビルド一式、画像・動画のハッシュを記録した。ビルド開始HEADだけを完成物の版とはしない。

最終Alembic SHA256：`78e11da3be5640924df7d9399dd2701d396c7e87172f89d6be7860ecff4ecd5c`。参照JSON：`c530edbb87c0197e45645c435c1e97979c1ca2072d3cb661018ffad0ddc66a84`。[Unityの実データ](../../Unity/Assets/GreatWave/Art/FixedTopology16/) に一組だけ保存。61個のBGEOと重複キャッシュはローカルのみ。[Houdiniソースと再現時のPIDガード](../../Houdini/FixedTopology16/README_ja.md) を参照。

## 保留と元シーンの状態

別のSteam GUI起動は失敗したため、既存の確認済み接続へ一意な新規所有コンテナだけを作った。既存形状を参照せず、HIPの保存・読込・クリア、グローバルFPS変更をしていない。終了後の18項目のUI・所有ノード復元は成功した。以前の箱実演時のUndo6件はその時点の記録で、今回の最終記録は42件。元の履歴を保持し、dirtyは今回の前後ともtrue。

**.hiplcを保存して再起動・再読込する試験、CPIO再読込後の法線照合、変動トポロジー・FLIP・FBX/VAT比較、ループ速度連続性、手動操作、HMDは未実施。** CPIOを完全なHIP保存の証拠にはしない。ここで確認を待ち、17以降へ進まない。

MCPの接続条件・未対応27ツールの除外・ネイティブツール再読込未確認・期限切れ申告と実行中Indie分類の区別は [接続時点の記録](../../Houdini/Preflight/Evidence/16_mcp_connection_ja.md) に残す。ライセンス購入・更新・認証変更は行っていない。
