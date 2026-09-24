# 20：PC制作経路の暫定採用と再検査条件

**PCで次の制作を進める組合せはBuilt-in＋Alembicを形状基準として継続する。Fluid VATはCPU更新の軽い候補として保持する。GPU専用時間・HMD・主役波が未検証のため、最終VR形式は採用済みにしない。** 利用者の最新指示に従い、代理の番号別レビューを経て独立した後続作業へ継続する。未所持HMDの条件を合格へ書き換えない。

- [20専用WindowsのAlembic近景動画](../Evidence/M1/Decision20/20_abc_2s.mp4)／[Fluid VAT近景動画](../Evidence/M1/Decision20/20_vat_2s.mp4)
- [Alembic 1秒](../Evidence/M1/Decision20/20_abc_024.png)／[VAT 1秒](../Evidence/M1/Decision20/20_vat_024.png)
- [人工左視点ABC](../Evidence/M1/Decision20/20_abc_stereo_024_0.png)／[VAT](../Evidence/M1/Decision20/20_vat_stereo_024_0.png)
- [測定値全要約](../Evidence/M1/Decision20/20_measurement_summary.json)／[出典](../Evidence/M1/Decision20/20_provenance.json)／[01〜20の検証状態と再検査一覧](Verification_Status_ja.md)

## 比較対象と判断

比較入力は18で採用した同じ24Hz・49時刻・0〜2秒の実FLIPで、再計算・面削減・デコード精度変更なし。19の新しい60Hz ABCと古い24Hz VATを競わせていない。描画は19の同じ色・CameraDepthTexture・ShadowCaster・不透明Lambert shaderを使う。小さな2球からの結合/崩壊であり、北斎の主役巻き波、白波の尖端、船からの実VR体験ではない。

| 対象 | 今回の判断 | 根拠・残る改修 |
| --- | --- | --- |
| PCの形状/物理検証 | Built-in＋Alembic2.4.4を暫定継続 | 元面と同じ幾何を参照しやすく、18/19の転送検査済み。CPU頂点更新/I/Oの予算は主役波で再測定 |
| 主役波のGPU再生候補 | Labs3.1 Dynamic Remeshing VAT＋専用Built-in HDR decoderを保持 | 18で全49面一致、19で同24Hzの深度/影を確認。CPU更新値だけではGPU全体の高速性を言えず、最終採用は保留 |
| Android単体Alembic | 現経路では採用しない | 公式desktop対象。PCに接続するHMDとは別条件 |
| URP/HDRP | 比較未実施・却下しない | 現時点はBuilt-inの検証基盤を維持。公式URP VAT graphの存在だけで現Unity/XR互換を仮定しない |
| 動的topology頂点の単純補間 | 採用しない | 毎時刻の対応頂点が同じではない。実新サンプルと表面としての差を検査する |
| HDR→half/圧縮・lookup縮小 | 今回は変更しない | 容量削減は全時刻P/N/接続/表裏/bounds/深度/影の再検証を伴う |
| 最終NPR/透明水/白波 | 未採用 | 現shaderは比較用の不透明照明で、浮世絵的な最終美術ではない |
| 操船/浮力照会 | 別契約が必要 | VATのGPU描画だけではCPUの水面/速度/接触照会を満たさない |

公式根拠：[Unity Alembic 2.4](https://docs.unity3d.com/Packages/com.unity.formats.alembic@2.4/manual/index.html)、[SideFX VAT3.1](https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.1.html)、[OpenXR設定](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/project-configuration.html)。本機はUnity6000.4.3f1／Alembic2.4.4へ固定して検査した。

## 独立ロードと同じ測定条件

同一Windows x64 Mono開発buildにboot・ABC専用・VAT専用の3sceneを用意した。bootは流体入力0、ABC sceneはABC1個、VAT sceneはFBX＋3EXRのみを参照する。[静的依存検査](../Evidence/M1/Decision20/20_scene_isolation.json)。実行時もロード前の流体Texture0、ABCロード後0、VATロード後3を確認し、相手の非表示assetを同時常駐させない。

新しいプロセスをABC→VAT→VAT→ABC→ABC→VATの順で6回起動し、形式ごとに3回測定した。OS/GPU cacheは消去していないため**新プロセス初回ロード**であり、物理ディスクのcold-start試験ではない。各形式で表示経路の順序を同じにした。

RTX3080／Core i7-12700K／D3D11、vSync0・targetFrameRate無制限・MSAAなし。実Directional light・hard shadow・深度生成、影距離45m。設定は20実行時に適用し、過去sceneのproject設定は変更しない。

- 広景固定カメラ：位置(14,12,-18)m、注視(0,0.6,0)m。初期流体は1,113／921,600画素（約0.12%）なので初期の塗り負荷は小さい。
- 近景固定窓：位置(4,3,-5)m、同注視。後半は画角外の流体もあり、主役波全体や船上視点の代用ではない。
- 両視距でmono1カメラと人工2カメラを測定。2カメラは平行姿勢・IPD64mm、各1280×720であり、同じ総画素数の比較ではない。OpenXRの実眼配送/SPIではない。
- 各経路98回warm-up後、49時刻を20回反復して980回計時。反復は負荷の測定であり、物理的に継ぎ目が成立した作品のループとは呼ばない。
- CPU更新、Camera.RenderのCPU呼出し、loop間隔、FrameTimingのCPU/GPUを分ける。計測中にPNG/readback/幾何検査は行わない。49回ごとのメモリ照会と配列記録の共通overheadはloop/FrameTiming CPUに入り得る。

初回可視化は最初の描画呼出しと同期readbackを別計時。初期球を499画素おきの色数で判定した旧候補は6色で不合格だった。実画像で球を確認し、全画素の液体固有青領域を計測する基準へ修正した。[不採用記録](../Evidence/M1/Decision20/20_rejected_initial_run.json)。100画素以上と実PNGを確認する判定で、黒画像や床だけを色数で通すものではない。

## 実測値

正式採録は `Capture_20260925_045354` の6プロセスだけ。以下は[最終要約JSON](../Evidence/M1/Decision20/20_measurement_summary.json)から取り出した**3回の中央値（最小〜最大）**で、旧候補の測定を混ぜていない。時間はms、メモリはMiB（1,048,576bytes）。

| 新プロセスでの初回処理 | Alembic | Fluid VAT |
| --- | ---: | ---: |
| 専用scene読込 | 19.6692（19.6014〜19.8911） | 153.1106（147.2697〜166.4145） |
| 流体初期化 | 0.9874（0.8771〜1.0015） | 2.3091（2.2734〜2.3602） |
| 最初の描画CPU呼出し | 2.7890（2.7831〜3.0166） | 2.9348（2.9316〜2.9798） |
| 最初の同期readback | 11.3771（10.0991〜12.0471） | 9.9610（9.7529〜12.6847） |
| 初回可視化後のprivate commit | 546.01（545.37〜550.44） | 817.30（811.69〜847.44） |
| 同private commitの空基盤からの増分 | 95.33（94.80〜98.19） | 364.91（359.14〜395.43） |
| 初回可視化後のworking set | 268.65（268.63〜270.49） | 308.01（302.62〜338.00） |

次表は各runの980回のうち、先頭8回を除いた972件の**FrameTiming CPU p95**を、さらに3runの中央値（範囲）として示す。全体frameのCPU値であり、流体更新だけやGPU時間ではない。

| 同じ固定視点の測定経路 | Alembic CPU p95 ms | Fluid VAT CPU p95 ms |
| --- | ---: | ---: |
| 広景・単眼 | 5.5857（5.5016〜5.7942） | 0.3098（0.2982〜1.5547） |
| 広景・人工2視点 | 5.6886（5.6579〜5.7011） | 0.4115（0.3881〜0.7739） |
| 近景窓・単眼 | 5.6221（5.5833〜5.6298） | 0.2918（0.2778〜0.2943） |
| 近景窓・人工2視点 | 5.9056（5.6967〜6.2513） | 0.7454（0.7419〜0.7609） |

直接計時した近景単眼の更新CPU p50は、run中央値でABC 2.8224ms、VAT 0.0014ms。ABCはCPUメッシュの読み込み/更新、VATは主にフレームuniformの変更なので、仕事の移動先を含むGPU費用まで同じ比率で軽くなったとは言えない。描画CPU・loop間隔・p99・各runの値は要約JSONと元runに保存した。人工2視点は実HMDの性能値ではない。

**GPU有効値は全24条件で各0件。** 各条件の取得対象972件はすべて0値、欠測timestampは0件だった。追加の通常PlayerLoop診断もABC/VAT各482件すべて0値で、有効GPU時間は得られなかった。0msとして集計せず、GPU計測は未解決として残す。

この24Hz小試料・非表示起動のoffscreen測定では、VATのCPU費用は低い一方、初回読込と私有commit増分は大きかった。GPU時間・主役波・HMDが欠けるため、CPU値のみでVATを最終採用せず、PCの形状基準としてAlembicを暫定継続する判断とした。

## GPUとメモリの解釈

20 buildだけ `enableFrameTimingStats=true` を設定し、build後finallyで元falseへ戻した。build前・実compiled・復元後の3manifestと実compiled PlayerSettingsを保存し、project復元差0を確認した。Development Playerは設定と別に機能が有効になる場合があるため、18のGPU欠測原因をこの設定だけと断定しない。

FrameTimingは約4frame遅れるので測定先頭8回を集計から除外し、一意timestamp・finite/正値・ゼロ・欠測を分けた。終了側の未取得値を推測で補っていない。rawの`cpuSample`は直接CPU計時の対象で、同rowのFrameTiming値をそのsample固有GPU負荷として扱わない。FrameTimingのGPU値が有効でもUnityアプリ全frameであり、VAT shaderだけの時間ではない。[公式FrameTiming](https://docs.unity3d.com/6000.0/Documentation/Manual/frame-timing-manager.html)。

さらに有効Camera・targetTexture=nullの通常PlayerLoopで別の診断を行った。非表示で起動したWindows processの画面target要求であり、実displayのpresentやHMDを実証しない。offscreen6-runへ混ぜない。両形式とも `IsFeatureEnabled=true` だったがGPU有効値は0件。[ABC診断](../Evidence/M1/Decision20/20_present_probe_abc.json)／[VAT診断](../Evidence/M1/Decision20/20_present_probe_vat.json)。

メモリはWin32 `GetProcessMemoryInfo(PROCESS_MEMORY_COUNTERS_EX)`。working setは実常駐、private bytesはプロセスの私有commitでVRAMではない。`peakWorkingSetSinceProcess`はbaseline以前や初回readbackも含むプロセス生涯peak。private peakは49回ごとの標本最大で、連続全時刻の最大を保証しない。Unity allocated/reserved/managedの値も別に保存した。

## 容量と成果物

元ABCは61,097,540bytes。VATはFBX＋3EXRで72,389,894bytes、mat別4,059bytes。3Textureの非圧縮texel合計237,240,320bytes（226.25MiB）とディスク容量を混同しない。これにmesh、CPU/driverコピー等が加わり、GPU総使用量は今回未計測。20は同じassetを参照し、容量のための再圧縮や精度低下を行わない。

共通buildの**実配布一式は270ファイル合計470,512,131bytes**。Unity BuildReportの409,414,591bytesとは区別する。差61,097,540bytesはABC本体サイズと同じだが、報告側の除外原因は断定しない。両形式を含むため方式別配布パッケージ差とは扱わない。Gitには新入力を複製せず、20専用コード/scene、測定、画像・動画、出典を保存する。

媒体は最終20 buildの計測外に、同じ元面boundsから得る規定の近景カメラで描いた。両形式で同じ時刻・軌跡を使う。動画は0〜47の48枚を24fps・2秒へ符号化し、終端48は別静止画。動画fpsは性能値ではなく、媒体のカメラは性能の固定広景/近景窓とは区別する。

0/1/2秒×mono/人工左右の9組を独立に画像比較し、注記を除いた流体の青領域maskは全組で一致した。これは代表9組の視覚/輪郭検査で、20の全時刻・全画素一致を主張するものではない。全49時刻のP/N/有向接続の根拠は18の転送検査を参照する。

## 再現と後続gate

本機の測定用実行一式は `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Decision20\`。最終体験アプリではなく自動検査用。以下は新しい出力フォルダーへ保存し、古いrunを削除しない。

```powershell
& 'E:\6000.4.3f1\Editor\Unity.exe' -batchmode -projectPath 'G:\Unity\GreatWave_2026_Fresh\Unity' -executeMethod GreatWave.Editor.Decision20Builder.Create -quit -logFile 'G:\Unity\GreatWave_2026_Fresh\Unity\Logs\20-editor.log'
./Tools/Build_Decision20.ps1
./Tools/Run_Decision20.ps1
```

Houdiniの再起動/再計算は不要。18入力と19shaderはそのまま、20だけの新規sceneで測る。最終provenanceはproject/compiled版とbuild一式、6runと別診断のlog、実PNG/動画、入力SHAを結ぶ。ログにはM0由来のOpenXR runtime未導入探査が残り、全ログ無警告とは言わない。

HMD・対象platform・実両眼/SPI/追跡/再投影・最大負荷予算・主役波の尖端/白波・最終NPR・操船queryが揃うまで最終VR採用とM1 gateは保留。代理の逐項検査という最新指示により、21〜25の独立した小振幅波・理論比較・収支確認などは継続できる。2球試料の面体積膨張/後半流出を波の物理基準に使わない。
