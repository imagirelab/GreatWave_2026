# 22：実 FLIP 水槽の中間成果（進行波は未完成）

> **2026-09-25：22は損切りで中止した（未完成・合否判定なし）。** 理由・保持する結果・費用は[Step_22の中止記録](../../Docs/Progress/Step_22_ja.md#22中止損切り2026-09-25)にある。22修正08の候補 [`Candidates/PfsSensitivity08Refine496`](Candidates/PfsSensitivity08Refine496/README_ja.md) は、実行前に凍結した計画として1バイトも変えずに保存した。候補READMEの「実行前・未実行」は凍結時点の記述である。その後、一時停止の前にk496の実行が1回行われ、原結果は本機の `Runs/pfsrefine08_9ed90958b4` にある（実行済み・未審査・未公開・本機保存）。以下は中止前の記録で、当時のまま残す。

現在は22修正07で、独立審査後に04保存粒子のk474（t7.9）一面をPFS `.25` にし、旧新各195断面の数値整合を確認した。[実測図・原JSON・再現・限界](Evidence/Revision07/README_ja.md)を公開する。新solver/時間波形/物理精度の合格ではなく、22未完成を保持する。最新の継続指示に従い根担当・独立担当が各実行を審査し、今回まだk496の新面化や連続列は実行していない。[修正06のt6診断・再現/失敗履歴](Evidence/Revision06/README_ja.md)は当時の証拠を変更せず保持する。

修正05の30時刻・5850断面では、[交点の再現性とG3候補の左prominence不足](Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/README_ja.md)を記録した。元PFS唯一鎖なし・減幅の単一原因未確定は今回も変更していない。

修正04は新所有DOPのL6/SOP doreseeding=0をt6まで再計算し、元静水判定PASS後に同一DOPをt9.25まで実駆動した。**短い始動応答は観測したが、非砕波・理論精度・22完成は未認定。** [実結果・媒体](Candidates/WaveStart04/Evidence/Result_22e7801642/README_ja.md)を参照する。以下の初期化FAILや未駆動対照は履歴として保持する。手順17・19の二球試料を波の証拠へ流用していない。

目標と理論値は [手順21の条件](../WaveBaseline21/README_ja.md) に固定した。H=.060 m、T=1.500 s、h=.600 m、g=9.81 m/s²、ρ=1000 kg/m³ の淡水相当基準である。初期の短槽は長さ2λ=5.980790 m、最新の感度試験は6.000m、いずれも幅.600 m。診断ゲージは .75λ と1.25λ、静水待機ケースでは1λを補助追加する。本試験用ゲージや理論値を、この短槽の結果で置き換えない。

## 実装と保護

現在の接続先は `Evidence/22_connection.json` に再測定した Steam Houdini 22.0.429、Indie、24 fps。専用の標準MCPクライアントから新規所有ノードだけを作成する。既存HIPの内容を走査せず、保存・読み込み・クリア・全体FPS変更を行わない。各実行の最後に所有ノードを削除し、18項目のUI復元を確認する。dirtyとundo履歴を消して見かけ上復元したとはしない。

初期水を一度だけ投入し、底・側面・閉端・移動ピストンを厚さ.24 mの閉じた衝突形状で構成する。FLIP Collide の第3出力を Solver の第3入力へ渡し、実際の collision velocity field を測る。任意の `v` 属性を指定しただけで速度転送が成立したとは扱わない。上面は開放、WaterlineとNarrow Bandは無効、速度移送は実パラメータのAPIC。解析的な境界流は接続していない。**吸収帯は未実装であり、閉端反射を含み得る。**

所有したDOPだけを1/120秒刻み、補間無効、サブステップ保持に設定し、実 `simulation.time()` と採録秒を照合する。60 Hzの各時刻は全体24 fpsの整数フレーム表示ではなく、対応する小数フレームで評価する。DOPメモリ上限768 MiB、ディスクへの自動退避は無効。実キャッシュはこのフォルダーの `Runs/<ID>/Cache` に保存し、再描画時はファイルを読み、再シミュレーションしない。

## 水面計測と既知の限界

波高計は実ソルバーの `surface` Volume を名前・型・bounds・transformで確認してから、湿側の負値と乾側の正値の間を二分する。範囲外・空field・交差無し・複数の湿→乾交差は無効とし、0 mや前の値へ補完しない。表示用 Particle Fluid Surface の縦線交差は別列で記録する。表示meshのdilate、erode、smooth、flatten、閉端処理は無効だが、粒子からの面化と実ソルバーSDFは同一ではない。

残存粒子が物理壁の外20 mmを超えない検査は、削除済み粒子や水量保存を証明しない。粒子数も質量ではない。負SDFセル数×voxel体積は未クリップの代理量で、固体やhalo、量子化を含み得る。手順25の収支には、固体を除いた物理領域内の部分湿体積と境界流束が別途必要である。

最初の dp=.04 m、Grid Scale=2（solver/collision voxel=.08 m）では、ピストン移動が約.064 mmの間にsolver SDF のゼロ交差が13〜21 mm下がった。駆動ON/OFFの同時刻差は0.5秒まで最大.0183 mmと.00042 mmであり、初期過渡が支配的だった。1.5秒試行では表示meshとsolver SDFの差が最大13.09 mm、目標振幅30 mmの約44%に達した。静水対照の t=0 では solver SDF はほぼ0 mだが表示meshは既に約−12〜−13 mmで、最初の1/60秒ではSDFだけが大きく変わる一方、mesh変化は約.1 mmだった。この初期ジャンプには、初期SDFと粒子再構成による定義の差が含まれる可能性があり、全てを実水体の沈下と解釈しない。別所有ノードの実初期化設定、初期P/ID一致のreseeding OFF・g=0対照を実施した。g=0でも最初のSDFジャンプが残り、初期再構成の定義差を支持するが、全振動の単一原因は未確定。水面を定数で持ち上げたり静水曲線を差し引いて理論一致と認定したりしない。

### 0.5秒の静水対照

以下は実ゲージの未補正値である。Grid Scaleを変えると初期粒子数・配置も変わったため、圧力voxelだけの因果比較や手順24の収束検証にはならない。計算時間は保存等を含む各標本の記録であり、MCP通信全体の時間ではない。

| dp / Grid Scale | 実solver voxel | 初期→末尾粒子 | G1/G2 最大絶対水位 | 末尾 G1/G2 | cook中央値 |
| --- | --- | --- | --- | --- | --- |
| .04 m / 2 | .08 m | 41,511→41,162 | 23.882 / 28.365 mm | −14.909 / −17.840 mm | 1.904 s |
| .04 m / 1.5 | .06 m | 53,500→52,936 | 5.999 / 3.683 mm | −3.401 / −3.683 mm | 2.187 s |
| .04 m / 1.25 | .05 m | 47,299→46,255 | 4.662 / 7.617 mm | −4.662 / −3.993 mm | 2.164 s |
| .03 m / 1.5 | .045 m | 117,731→117,441 | 9.398 / 5.740 mm | −8.194 / −4.184 mm | 4.092 s |

[実データ比較図](Evidence/Static_Comparison/22_static_comparison.png) と [数値・元標本SHA](Evidence/Static_Comparison/22_static_comparison.json) を保存した。細粒化は単調な改善を示さず、無制限に解像度を上げる方針は採らない。dp=.04 m / Grid Scale=1.5 を、精度合格ではなく次の診断用候補とした。

## 静水待機ケース

新規ケースの作成時から、ピストン開始を絶対DOP時刻3秒に固定する。0〜3秒は板を動かさず、途中でパラメータを変更して計算をリセットしない。波の時刻は τ=t−3秒とし、正確な絶対時刻も保存する。3秒以後は2T=3秒の立上げを使うが、診断ゲートを通らなければ駆動段へ進めない。

事前固定した後半窓は (1.5,2.25] 秒と (2.25,3.0] 秒、それぞれ45標本。全ゲージで窓間平均差≤3 mm、平均まわりRMS≤3 mm、線形傾き×.75秒の絶対値≤3 mm、SDF代理量の窓間変化≤1%を診断する。これらは今回の運用上の条件であり、初期水深や収支の精度合格ではない。平均まわりRMSを計算しても、元の水位系列から平均を差し引かない。

1.5秒は健康と費用の中間確認である。最初の窓は既知の初期過渡を含むため、その傾きの不合格だけで静水待機の延長を禁じない。駆動前の判定は上記後半窓で行う。solver SDFは60 Hz、表示meshは30 Hzで保存する。meshを保存しない時刻は未測定を `null` で示す。

## 再現と保存物

`Source/run_pilot.py` は新規所有物を作成し、失敗時も復元を試みる。接続先の現PIDを `Source/probe_connection.py` で再取得し、記録と実応答が一致することが前提。[公開時系列と実行当時Source](Evidence/Curated_Runs)、[出典索引](Evidence/22_provenance.json)、[3秒の実Houdini静止画](Evidence/Still_0652da0179/22_Perspective_180.png)を保存した。`Runs` の全BGEOとraw画像・ログはローカルに保持する。公開図表はCurated_Runsだけから再計算できる。

解析だけを再現する `Source/compare_static_cases.py` と `Source/analyze_preroll.py` は、保存済み実データを読み、所有したEvidenceへ図表を書き出す。Houdiniを操作せず、水面のシミュレーション値を生成しない。

## 一次資料

- [SideFX FLIP Collide](https://www.sidefx.com/docs/houdini/nodes/sop/flipcollide.html)：変形衝突形状の速度計算、Velocity Substeps、衝突型。
- [SideFX SOP衝突](https://www.sidefx.com/docs/houdini/fluid/sopcollisions.html)：衝突surface/velocityの接続。
- [SideFX FLIP Solver](https://www.sidefx.com/docs/houdini/nodes/sop/flipsolver.html)：Containerとの粒子間隔整合、無外力計算による初期体積保持の確認方針。
- [SideFX FLIP Container](https://www.sidefx.com/docs/houdini/nodes/sop/flipcontainer.html)：境界は実壁と同一ではなく、領域外では粒子が削除される。
- [SideFX volumesample](https://www.sidefx.com/docs/houdini/expressions/volumesample.html)：範囲外等の0を有効な水面と取り違えない。
- [Lee & Hong 2020, 式21–22](https://www.mdpi.com/2077-1312/8/3/159/xml)：小振幅ピストン造波の H/S 開始値。今回の片振幅約.0248074 mは候補であり、実FLIP波高を保証しない。

## 今回の到達点と再現

[22の中間進捗](../../Docs/Progress/Step_22_ja.md)に、3秒の不合格表、独立再計算、底方向SDF追加検査、初期化schema、二つの単一変更診断をまとめた。中央測点の前窓の傾き×.75秒は6.302mmで3mmを超え、駆動段へは入っていない。プログラム失敗ではなく、事前登録した開始条件の不合格である。

底方向の読戻しは3本の縦線・181時刻、約3cm以下のSDF標本で乾いた切断を検出しなかった。全3D、連続時間、サブ格子の気泡、真の底接触・水量保存の合格ではない。PFSの最初のray hitも主水柱への連結証明ではない。実Initial Surface=1、Waterline=0、Particle Field初期化、Radius Scale1.2、Smooth Surface1、Update Surface advect、partsep0、extrapdist.5とsource初回だけのActivateを別所有ノードで確認した。

図表のみの再計算は、Wave22を含むリポジトリを取得後、解析環境のPythonで次を実行する。公開原データは書き換えないが、解析結果JSON/図は再生成する。

```powershell
python Houdini/Wave22/Source/analyze_pilot.py 6bb19ca887 e1db8acb19
python Houdini/Wave22/Source/compare_static_cases.py
python Houdini/Wave22/Source/analyze_preroll.py 0652da0179 --end 3
python Houdini/Wave22/Source/compare_preroll_surfaces.py
python Houdini/Wave22/Source/compare_short_controls.py
```

Houdiniを新規計算する場合は、既存MCP接続先を `probe_connection.py` で再測定してから、専用MCP Python環境で次の条件を使う。現PIDを歴史値のまま使用しない。現行スクリプトは診断項目が追加されており、実行当時のexact sourceは各execution_summaryとExecuted_Sourceで識別する。同じ入力からのbit単位の再現を未検査で約束しない。

```powershell
python Houdini/Wave22/Source/run_pilot.py --grid-scale 1.5 --particle-separation .04 --piston-start 3 --mesh-stride 2 --three-gauges --samples 181 --batch-size 6
```

このコマンドはt3で終了し、駆動段へ自動続行しない。再実行は新しいRun IDへ保存する。現在の中間結果を波の合格として上書きしない。

実行当時Sourceのうち末尾空行を含む4ファイルは `.py.gz` へ無損失圧縮し、元SHAと保存物SHAをexecution_summaryに分けて記録した。展開後は当時のbytesと一致する。現在のSourceはLF・単一末尾改行で公開する。


## 22修正01：t6の実行結果

新Run `3e5ff87a29` は361時刻で停止した。固定窓(4.5,5.25]、(5.25,6]のG3傾きが+5.624/−4.552mmで3mm上限を超え、開始判定FAIL。平均差・平均まわりRMS・SDF代理量変化は通過したが、表示PFSにも残動がある。板の解析変位/速度は0、k360の実collision vxだけ9.889719e−7m/s、他は0。駆動許可なし、波動画なし、UI18項目と所有ノード削除は合格。

[実全時系列図](Evidence/Checkpoint6_Result_3e5ff87a29/22_static_full_series.png)、[後半拡大](Evidence/Checkpoint6_Result_3e5ff87a29/22_static_late_windows.png)、[公開Curated原データ](Evidence/Curated_Runs/3e5ff87a29)、[実行値・資源・出典](Evidence/Checkpoint6_Result_3e5ff87a29/22_checkpoint6_summary.json)を参照。542BGEO計1.662GBは本機Runsに保持し、[hash一覧](Evidence/Checkpoint6_Result_3e5ff87a29/22_cache_manifest.json)だけをGitへ保存した。t3の底方向検査をt6へ拡張したとは記さない。

新runnerはHoudini保存JSONのSHAと実行ソースSHAを照合して精値を読み、MCP返却floatを判定に使わない。初回の丸めによる拒否は[短い記録](Evidence/Checkpoint6_Planned/22_rejected_transport_attempt.json)へ分離した。[事前計画](Checkpoint6_Plan_ja.md)は実行前の条件として保持する。23項目の模擬実行を通してから再実行したが、実静水は合格しなかった。

公開ファイルだけで新しい図・CSV・統計を再計算する場合：

```powershell
python Houdini/Wave22/Source/summarize_checkpoint6.py --curated-only
```

このモードはHoudiniへ接続せず、ローカルBGEOの再検証も行わない。原JSONと保存manifestから再計算する。通常モードは本機Runsの542BGEOのSHAを再検査してから公開候補を作る。


## 22修正02：L6の実結果

内槽長6.000mのRun `db52394211` は新しい初期粒子53,794個で始まり、格子/壁の予備観測と0.5秒健康点を通過した。pressure鏡像Egは旧.320057881cell→新.000103315cellとなったが、静水のG3傾きは+6.430/−4.033mmで3mm上限を超え、再びFAIL。前窓の絶対値は増え、後窓は減り、全体の改善や格子だけの因果は主張しない。同30HzのPFSも+5.609/−3.359mmと変化した。元60Hz判定はそのまま保持する。

[旧槽との原水位比較](Evidence/Length6_Result_db52394211/22_length6_full_series.png)／[固定窓](Evidence/Length6_Result_db52394211/22_length6_late_windows.png)／[361時刻CSV](Evidence/Length6_Result_db52394211/22_length6_gauges.csv)／[元JSONと実設定・復元](Evidence/Curated_Runs/db52394211)／[出典](Evidence/Length6_Result_db52394211/22_result_provenance.json)。548個の実BGEOはローカルRunsに残し、全SHAをmanifestへ保存した。UI18復元合格、造波許可なし、動画なし。詳細数値と限界は[Step22の修正02](../../Docs/Progress/Step_22_ja.md)に記載した。

公開データだけの再計算：`python Houdini/Wave22/Source/summarize_length6.py --curated-only`。これは実BGEO/Houdiniを再評価せず、公開JSONの図・CSV・摘要を作る。


## 22修正03：SOP doreseeding OFFの固定6秒診断

同じL6初態をID別P/v/pscale・全surface/pressureで厳密配対し、SOP doreseedingだけ1→0とした。Run4250d4451fは元の静水判定PASS、六時刻×7128点の粗い被覆警報0、UI18復元PASS。PASSでも固定6秒で終了し、造波・波動画はない。内部DOPはonlysourceseeding=1/reseed=1であり、「内部Reseed ParticlesもOFF」「出生なし」とは記さない。

[実ON/OFF図・CSV・全原記録](Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/README_ja.md)／[事前計画と手順](Candidates/Reseeding03/README_ja.md)／[独立再計算方法と限界](../../Docs/Progress/Step_22_ja.md)。548 BGEOは本機Runs、ON/OFFの全深水原JSONはgzipで公開した。符号場/支持の検査は無空洞・収支・物理精度・波伝播の証明ではない。22は引き続き中間成果である。
