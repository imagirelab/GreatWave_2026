# 22：実 FLIP 水槽の中間記録 — 進行波は未完成

最新の22修正04は、新所有DOP `22e7801642` で同L6・SOP doreseeding=0を再計算し、**t6静水再PASS後に同じDOPでt9.25まで実活塞を駆動した。solver場は有序谷候補1鎖、PFS表示面は唯一鎖なし。** 短い始動応答の中間成果であり、非砕波・無反射・理論精度・22完成ではない。以前のFAILと未駆動対照を履歴として保持する。

- [22修正01・t6の全時系列図](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_full_series.png)／[固定判定窓の拡大図](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_late_windows.png)
- [22修正01・361時刻CSV](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_checkpoint6_gauges.csv)／[t6判定の原JSON](../../Houdini/Wave22/Evidence/Curated_Runs/3e5ff87a29/22_checkpoint_gate.json)

- [22修正02・L6と旧槽の比較図](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_full_series.png)／[固定窓](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_late_windows.png)／[比較CSV](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_gauges.csv)

**以下の初回記録では静水の駆動開始判定が不合格だった。修正03は静水PASSのみ、修正04の実始動は末尾に別記する。** 手順22が求める非砕波の伝播・複数の峰の到来は未完成である。シミュレーションの実行失敗と、正常に実行できた試料が物理上の開始条件を満たさないことを区別する。

- [実Houdini静止画：0秒](../../Houdini/Wave22/Evidence/Still_0652da0179/22_Perspective_000.png)／[3秒](../../Houdini/Wave22/Evidence/Still_0652da0179/22_Perspective_180.png)
- [181時刻の未補正 SDF と表示mesh](../../Houdini/Wave22/Evidence/Preroll_0652da0179/22_preroll_sdf_mesh.png)／[CSV](../../Houdini/Wave22/Evidence/Preroll_0652da0179/22_preroll_gauges.csv)
- [4つの静水対照](../../Houdini/Wave22/Evidence/Static_Comparison/22_static_comparison.png)／[条件・手順・一次資料](../../Houdini/Wave22/README_ja.md)
- [駆動開始判定の全数値](../../Houdini/Wave22/Evidence/Curated_Runs/0652da0179/22_preroll_stability.json)／[原時系列](../../Houdini/Wave22/Evidence/Curated_Runs/0652da0179/22_pilot_samples.json)／[出典索引](../../Houdini/Wave22/Evidence/22_provenance.json)

画像は同じ実BGEOをHoudiniへ読み戻して撮影した1280×720の静止画で、青色の表示属性だけを加えた。再シミュレーション、理論式からの水面生成、画像加工はしていない。静水を進行波の完成映像に見せる動画は作っていない。Unity波映像・HMDは今回未検証。

## 固定条件と実施範囲

[21の基準](Step_21_ja.md)は波高.060 m、周期1.500 s、水深.600 m、g=9.81 m/s²、ρ=1000 kg/m³の淡水相当条件。今回の短槽は長さ2λ=5.980790 m、幅.600 m、底y=−.600 m、初期水面y=0。短槽の診断測点は x=.75/1/1.25λ、z=0で、本試験用の3測点とは別である。

現在のSteam Houdini22.0.429 / Indie / 24 fpsをmetadataのみで再確認した。新規所有FLIPのAPIC、実DOP刻み1/120秒、補間OFF、サブステップ保持から60 Hzで採録した。全体FPSを変えていない。底・側面・閉端・ピストンは厚い実衝突形状で、collision velocityを実fieldから照合。解析境界流・Waterline・Narrow Bandは無効。閉端の吸収帯は未実装で、長時間に延長しても無反射とは扱えない。

dp=.04 m / Grid Scale=2の初期試行は、solver SDFの初期過渡が大きかった。静水対照と比較し、Grid Scale=1.5、1.25、さらにdp=.03 m / Grid Scale=1.5を別ケースで検査した。細粒化は単調に改善せず、初期粒子配置・数も変わるため圧力格子だけの因果や解像度収束は未証明。[比較数値](../../Houdini/Wave22/Evidence/Static_Comparison/22_static_comparison.json)を保持した。

## 3秒の静水待機：事前判定 FAIL

主記録 `0652da0179` は dp=.04 m、Grid Scale=1.5、実solver voxel=.06 m、表示mesh voxel=.02 m。作成時からピストン開始を絶対t=3秒に固定し、t=0〜3秒の181標本でピストンの解析変位・解析速度とも0だった。判定窓は事前に (1.5,2.25] と (2.25,3] 秒へ固定し、それぞれ45標本。平均を差し引いた水位や後から選び直した窓は使っていない。

| 診断位置 | 前窓 平均 / RMS | 後窓 平均 / RMS | 窓間平均差 | 傾き×.75秒：前 / 後 |
| --- | --- | --- | --- | --- |
| x=2.242796 m | −5.842 / .892 mm | −3.088 / 1.538 mm | +2.753 mm | −2.496 / −2.428 mm |
| x=2.990395 m | −3.495 / 1.878 mm | −1.544 / .463 mm | +1.952 mm | **+6.302** / −1.568 mm |
| x=3.737994 m | −3.180 / .561 mm | −2.959 / .324 mm | +.221 mm | +.277 / +1.081 mm |

窓間平均差・平均まわりRMS・傾き×.75秒の絶対値の上限は3 mm、SDF代理量の窓間変化は1%以下。平均水位そのものを3 mm以内と判定したものではない。唯一の超過は中央測点の前窓の傾き+6.302 mmであり、駆動開始条件を通していない。これは今回の診断条件であり、一般的な波浪精度基準ではない。別担当が原181標本から独立再計算し、同じ不合格を確認した。数値差の最大は1.31×10⁻¹⁸ m。

負SDFセルの代理量は窓平均2.343653→2.343370 m³、変化−.0121%。固体やhaloを除外しておらず、水量保存の証拠ではない。粒子速度RMSの窓平均は6.949→5.066 mm/s、総粒子数は初期53,500→末尾51,430。reseedingがあるため粒子数を質量と解釈しない。cook中央値2.088秒、最大2.570秒、DOP記録メモリ最大805.28 MB、空き物理RAM最小33.75 GB。メモリ上限768 MiBと自動ディスク退避OFFを保持し、プログラム・資源・局所交差・壁外粒子のガードは通過した。

## 水面の定義差と底方向の追加検査

t0のsolver SDFはほぼ0 mだが、同じ粒子の表示meshは既に約−12〜−13 mmにある。初期のSDFの大きな変化を、そのまま実水体が沈下した量とは呼べない。g=0対照でも初期ジャンプが発生するため、初期SDFと粒子再構成の定義差が関与する。ただし通常重力下で残る全振動の原因は確定していない。

既存のゲージ `valid` は−.48 mから上の局所交差を確認したものだった。独立監査で床付近の連結が未証明と分かったため、**同じ181個の実BGEO**を追加読戻しした。中央z=0の3縦線について、床上.1 mmから局所自由面下.1 mmまで各21点、合計11,403点を約29.64〜29.99 mm間隔で照会し、全点が実field bounds内・有限・負だった。543プロファイルで乾いた切断を検出しなかったという限定結果で、3D全域、連続時間、サブ格子空隙、真の底接触、水量保存は証明しない。[全phiと条件](../../Houdini/Wave22/Evidence/Curated_Runs/0652da0179/22_bottom_connection.json)を保存した。

同時刻30HzのPFS表示面も別観測として比較した。中央測点の前窓の傾き×.75秒は、同じ30Hz標本のSDFで+6.439 mm、PFSで+3.959 mm。表示面も変わるのでSDFだけのノイズとは断定できない。元の60Hz SDF判定をPFSで置き換えていない。[対照の全数値](../../Houdini/Wave22/Evidence/Preroll_0652da0179/22_preroll_mesh_comparison.json)を参照する。

## 初期化と短い単一変更の診断

新規所有ノードを別に作り、実初期化設定を読み取った。Initial Surface=1、Waterline=0、Narrow Band=0、Apply Particle Separation=0、Surface Extrapolation=.5、FLIP Object Input Type=`Particle Field`、Radius Scale=1.2、Smooth Surface=1、Update Surface=`advect`。reseedingのbirth/deathは.5/1.5、表面oversamplingは1.5。sourceのActivateはt=0で1、1/120・1/60秒で0だった。第4入力は未接続。[実値](../../Houdini/Wave22/Evidence/Curated_Runs/3fbad0c17a/22_initialization_schema.json)を保存し、Initial Surfaceだけが二重初期化を起こしたとは断定しない。

二つの新規9標本対照は、t0の粒子53,500点のP/IDが主記録と完全一致することを先に確認した。

- **reseedingだけOFF**：初期のSDFジャンプは残った。t=.1333秒の基準との差は約.046/.007 mmで、初期ジャンプをreseedingだけでは説明できない。
- **重力だけ0**：第1標本でSDFが−4.077/−.702 mmへ変わり、以後.1333秒まで不変。粒子速度RMSは全0、表示meshの変化はG1で約.00474 mm、G2で0。初期再構成の診断であり、重力0の流体を作品や物理合格に使わない。

[対照の原数値・ID追加削除](../../Houdini/Wave22/Evidence/Short_Controls/22_short_control_comparison.json)と実行当時のSourceを保存した。初期配置を固定した短い切り分けであり、長時間の収束・収支試験ではない。

## 保存・復元・再現と次の条件

[Curated_Runs](../../Houdini/Wave22/Evidence/Curated_Runs)には、図表で使用した実条件、原時系列、UI復元摘要、実行当時のSourceをSHA別に保存した。clone後に[駆動/停止対照](../../Houdini/Wave22/Source/analyze_pilot.py)、[静水比較](../../Houdini/Wave22/Source/compare_static_cases.py)、[窓診断](../../Houdini/Wave22/Source/analyze_preroll.py)、[SDF/mesh比較](../../Houdini/Wave22/Source/compare_preroll_surfaces.py)、[短対照比較](../../Houdini/Wave22/Source/compare_short_controls.py)を再計算できる。[公開データだけを別ディレクトリへ複製した再計算検査](../../Houdini/Wave22/Evidence/22_analysis_reproduction.json)では、Runsフォルダー無しで5スクリプトを実行し、9出力のSHAが一致した。Pythonとmatplotlib等は[21の固定依存](../../Houdini/WaveBaseline21/Source/requirements.lock.txt)を参照。フォントはWindowsのMeiryoでSHAを記録した。

全BGEOとrawログは本機 `G:\Unity\GreatWave_2026_Fresh\Houdini\Wave22\Runs` に保持し、通常Gitには含めない。原時系列のcache SHAと公開実行摘要を対応付けた。全試行で既存HIPの保存・読込・クリアや全体FPS変更は行わず、所有ノード削除と18項目UI復元を確認。dirtyフラグと増えたUndo履歴は保持した。初回2試行は更新モード/cookの実装不備で不採用とし、個人パスを含むraw tracebackは公開せず、[失敗種別と段階](../../Houdini/Wave22/Evidence/22_run_ledger.json)を残した。

初回の中間成果では手順22を完了にしなかった。当時の次案だった、物理条件を変えず待機を延長して固定窓を判定する試験は、下記のt6ケースで実施し、再びFAILとなった。無条件な長時間計算や基準の緩和は行わない。実進行波、非砕波の確認、23の理論誤差、24の収束、25の収支・反射、HMDは未検証として保持する。


## 22修正01：6秒待機でも固定条件FAIL

新規ケース `3e5ff87a29` は、作成前にUIを保存してframe=1へ移し、開始時刻をt6に固定した。t0の53,500粒子のP/IDはt3主ケースと完全一致した。0〜3秒の三点SDF、代理量、粒子数と91回のPFS測点・点面数も一致したが、旧t3終端には衝突速度の微量差があり、全物理状態やBGEOのbytesが同一とは記さない。

開始判定は取得前に(4.5,5.25]と(5.25,6]の各45標本へ固定した。元と同じ3mm/1%の基準である。全361標本を保存し、判定FAIL後はk361以後を評価せず、同じ所有DOPを削除してUIを復元した。

| 診断位置 | 前窓 平均 / 平均まわりRMS | 後窓 平均 / 平均まわりRMS | 窓間平均差 | 傾き×.75秒：前 / 後 |
| --- | --- | --- | --- | --- |
| G1 x=2.242796m | −1.729 / .782mm | −2.992 / .302mm | −1.263mm | −2.606 / −.041mm |
| G2 x=2.990395m | −.947 / .666mm | −3.765 / .620mm | −2.818mm | +.293 / −2.093mm |
| G3 x=3.737994m | −3.632 / 1.627mm | −3.871 / 1.368mm | −.238mm | **+5.624 / −4.552mm** |

不合格はG3の前後窓の傾き2項目である。平均差・RMSは全て通過した。負SDF代理量の平均は2.340826→2.336871m³（−.168966%）で1%以内だが、固体・halo・量子化を含むため水量保存とは言えない。速度RMSの窓平均は4.378→6.682mm/s。粒子数は前窓51,308→51,239、後窓51,238→51,253で、reseedingがあり質量ではない。独立再計算でも同じFAILを確認した。

同時刻30Hzで比較したG3のPFS表示面も傾き×.75秒が前+4.428mm、後−2.642mmと変化した。SDFだけの読み取りノイズと断定できない。表示面を元の60Hz判定に置き換えず、残動の原因や単一の振動モードも未確定とする。

ピストンの解析変位・解析速度は361時刻で0。ただし実collision velocityのvxはk360だけ9.889719×10⁻⁷m/sで、それ以外は0だった。現1×10⁻⁴m/sの一致性許容内であり、造波の証拠にはしない。実collision速度が常に厳密0だったとは記さない。

資源・手順は正常で、時計誤差最大8.88×10⁻¹⁶秒、壁外20mm超の残存粒子数0、cook中央値2.204秒/最大3.053秒、DOP最大767.975MiB、プロセス私有コミット最大8.266GiB、空きRAM最小31.336GiB。361個のsolver/粒子BGEOと181個のPFS BGEO、計542ファイル1,662,166,359bytesのSHAを読戻し照合した。全cacheはローカルRunsに残し、Gitには軽量な原時系列とmanifestを保存する。

18項目UI復元・所有物削除は全て合格、HIP保存/読込なし、全体FPS24を保持した。dirtyはtrueのまま、Undoは554→558で履歴を消していない。[条件・原361標本・trace・初期一致・復元摘要](../../Houdini/Wave22/Evidence/Curated_Runs/3e5ff87a29)、[全判定・資源と表示面統計](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_checkpoint6_summary.json)、[542cacheのSHA](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_cache_manifest.json)、[新結果の出典](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_result_provenance.json)を対応付けた。

全6秒の底方向読戻しは今回未実施で、以前の181時刻/543縦線の限定結果を6秒へ拡張しない。新しい図は実SDF/PFS時系列からのグラフで、Houdiniの追加ビューポート画像や動画ではない。進行波・非砕波・理論精度・HMDは引き続き未検証である。

最初の準備試行 `9e0d1dff0c` は、MCP返却値が槽長を5.98079へ丸め、元の5.980790346583645との条件照合が拒否された。採録0・駆動なし・UI18復元合格で、物理FAILではない。[短い拒否記録](../../Houdini/Wave22/Evidence/Checkpoint6_Planned/22_rejected_transport_attempt.json)を残した。修正版はHoudini保存JSONと実行ソースのSHAを両端で照合し、元の精度のJSONから静水判定する。23項目の模擬実行後に新Runを開始し、物理の閾値は緩めていない。

公開データだけの図・CSV再計算は、同じPython/フォント環境で以下を使う。実行時のBGEO照合はローカル完全版で済ませており、公開データだけのモードはBGEOを再検証したとは言わない。

```powershell
python Houdini/Wave22/Source/summarize_checkpoint6.py --curated-only
```

[Runsを含まない隔離コピーでの復算記録](../../Houdini/Wave22/Evidence/Checkpoint6_Planned/22_result_reproduction.json)では、2図・CSV・数値摘要・cache manifestの5出力のSHAが一致した。出典索引自体はこの検査記録と最終文書を含めて最後に更新する。

次のケースはこのFAILを保持したまま原因を診断し、変更量・固定窓・停止条件を別途事前定義する。無条件に待機を延長せず、3mm基準を緩めない。


## 22修正02：内槽長6.000mでも静水の開始条件FAIL

設計入力はLだけを5.980790346583645→6.000m（+0.3212%）へ変えた。λと三点の絶対x、dp=.04m、Grid Scale1.5、g9.81m/s²、dt1/120s、source once、APIC、seed・reseeding・衝突は保持した。Lに伴って水域・端壁位置と格子との対応、初期粒子が変わり、粒子は旧53,500→新53,794。新初態のP/v有限・ID一意・内槽20mm保護は合格したが、旧P/ID完全一致を要求する対照ではない。[保存した事前計画](../../Houdini/Wave22/Length6_Plan_ja.md)と[実条件・初態・格子・健康点・原361標本](../../Houdini/Wave22/Evidence/Curated_Runs/db52394211)を対応付けた。

t0とt1/60の格子は保存済みBGEOを読み、同時刻のforce再cookを避けた。間のt1/120だけ同じDOPを前進して実時計を確認した。旧t1/60 BGEOのpressure/surface Egは0.320057881cell、新しい拡張場は0.000103315cellで、事前の.001cell鏡像ラベルを満たした。t0の小pressure場は両壁未包含で適用外。新collisionは各時刻81対・18本の壁根を検査し、3時刻合計243対・54根が有効だった。対の最大差は3.446×10⁻⁷m。空のvel VDBは背景速度だけを扱い、boundsやEgを解釈しなかった。旧cacheにcollision場はなく、旧collisionとの比較は未実施である。

0.5秒の31標本健康点は通過したが、これは静水合格ではない。元と同じ(4.5,5.25]と(5.25,6]、各45点で以下を得た。

| 新L6診断点 | 前窓 平均 / 平均まわりRMS | 後窓 平均 / 平均まわりRMS | 窓間平均差 | 傾き×.75秒：前 / 後 |
| --- | --- | --- | --- | --- |
| G1 | −1.504 / .706mm | −2.360 / .352mm | −.856mm | −2.411 / +.926mm |
| G2 | −.482 / .483mm | −2.373 / .773mm | −1.891mm | +.666 / −2.639mm |
| G3 | −3.032 / 1.925mm | −3.306 / 1.238mm | −.274mm | **+6.430 / −4.033mm** |

独立再計算でも同じFAILを確認した（判定数値の最大差5.4×10⁻²⁰m）。窓間平均差・平均まわりRMSは全点3mm以内だが、G3の両傾きは3mmを超えた。旧Lの同項目は+5.624/−4.552mmで、新Lは前窓の絶対値が増え、後窓は減った。**一方が改善し一方が悪化しており、全体の改善や単一原因の特定とは言えない。** 負SDF代理量は2.351914→2.350315m³、−.067962%で1%以内。これは水量収支ではない。粒子速度RMSの窓平均は3.691→5.182mm/s、粒子数は前51,670→51,617・後51,617→51,636であり質量ではない。

同一30Hz時刻に揃えたG3の比較も保存した（前22点/後23点）。この統計は元60Hzの判定を置き換えない。

| G3 傾き×.75秒 | 前窓 | 後窓 |
| --- | ---: | ---: |
| 新L6 SDF・30Hzに限定 | +6.572mm | −4.030mm |
| 新L6 PFS表示面・30Hz | +5.609mm | −3.359mm |
| 旧L PFS表示面・30Hz | +4.428mm | −2.642mm |

新SDF/PFSの同時刻相関は.9941/.9896で、表示面にも同方向の変化がある。SDFの読み取りだけのノイズで説明できたとは言わず、初期化・圧力・粒子・衝突等の単独原因も断定しない。表示面とSDFの絶対水位には差が残り、どちらも補正していない。

解析板変位/速度は361時刻全0。実collision vxはk360だけ9.889719×10⁻⁷m/s、他は0で、既存1×10⁻⁴m/s一致性許容内だった。これは造波証拠ではない。gate FAIL後は駆動許可もk361以後もなく、所有ノードを削除した。18項目UI復元全PASS、dirtyはtrueのまま、Undo558→562を保持、HIP保存/読込なし。実時計差最大8.88×10⁻¹⁶s、cook中央値2.225s/最大3.060s、DOP最大767.995MiB、私有コミット最大8.323GiB、空きRAM最小30.459GiBだった。

361solver/粒子、181PFS、6格子/衝突BGEOの**548ファイル1,682,590,892bytes**を全件SHA照合し、[manifest](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_cache_manifest.json)を公開した。BGEO本体はローカルRunsに保持する。[数値と原ソースの対応](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_summary.json)、[今回の出典](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_result_provenance.json)、実行当時Sourceを保存した。

今回の図は実SDF/PFSの原時系列から作ったグラフで、追加のHoudini/Unityビューポート画像や動画ではない。全6秒の底連通・非砕波・伝播・理論精度・収支・HMDは未検証。22の完成点にせず、次の原因診断は別計画とする。公開時系列だけの再計算は次で行う。元のBGEO読戻し検査をこの公開モードで再実施したとは言わない。

```powershell
python Houdini/Wave22/Source/summarize_length6.py --curated-only
```

[Runsのない隔離コピーでの再計算記録](../../Houdini/Wave22/Evidence/Length6_Planned/22_result_reproduction.json)では、2図・CSV・数値摘要・cache manifestの5出力が同一SHAとなった。原時系列・条件・実行当時Sourceを変更せず検査した。


## 22修正03：同一初態のSOP doreseeding OFF対照は静水診断PASS

配対基線は公開済みL6 `db52394211` だけとした。水槽、λ、三点の絶対位置、dp=.04m、Grid Scale1.5、g9.81m/s²、dt1/120s、APIC、source once、seed2101、衝突、板の開始t6を固定し、設計パラメータはSOP `doreseeding` 1→0だけ変更した。t0の53,794粒子についてID順P/v/pscale、surface/pressureの格点・transform・全体素値を厳密配対し、一致後だけsample1へ進んだ。t0/1⁄120/1⁄60の場観測順も基線と同じである。[事前計画と実行手順](../../Houdini/Wave22/Candidates/Reseeding03/README_ja.md)、[初態配対の原記録](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/Original/off_initial_strict_pair.json)を残す。

SOP/internal DOPの記録済み57項目は所有ルート名を除いて比較し、差はSOP `doreseeding` のみだった。追加読取りではOFF内部に `onlysourceseeding=1`、`reseed=1`、`reseedsinglepass=1` を確認した。**内部のReseed Particlesを0にした試験ではない。** 旧ONの先頭2項目は未収録なので、旧内部値を推定で補わない。[実schema差](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/Original/off_initialization_schema_comparison.json)と[追加実値](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/Original/off_reseed_internal_detail.json)を分けた。[SideFX公式資料](https://www.sidefx.com/docs/houdini/nodes/dop/flipsolver.html#reseeding)はこの診断の仮説の根拠であり、今回のSOP切替と全内部機構の同義性を代用証明しない。

Run `4250d4451f` は0〜6秒の361標本で正常終了した。窓は(4.5,5.25]と(5.25,6]各45点、窓間平均差・平均まわりRMS・傾き×.75秒の上限3mm、負符号場voxel代理量変化1%を一切緩めていない。

| OFF診断点 | 前窓 平均 / 平均まわりRMS | 後窓 平均 / 平均まわりRMS | 窓間平均差 | 傾き×.75秒：前 / 後 |
| --- | --- | --- | --- | --- |
| G1 | −.631 / .049mm | −.877 / .166mm | −.246mm | −.112 / −.535mm |
| G2 | −.333 / .081mm | −.558 / .235mm | −.225mm | −.154 / +.356mm |
| G3 | −.707 / .177mm | −.803 / .200mm | −.096mm | +.079 / +.680mm |

独立した原361標本の再計算でも、全項目が元の静水判定条件を通過した。ON基線のG3傾きは+6.430/−4.033mmだった。OFFの負voxel代理量の窓平均は2.361437→2.361471m³、+0.001422863%。粒子速度RMSの窓平均は1.539→1.561mm/sである。**この1 seed・1組の静水診断では残動の数値が減少したが、一般物理精度、質量保存、波の成立や方式採用を確認したとはしない。** 判定PASSでも事前計画通りk360で終了し、駆動許可を出していない。

同30HzのG3ではsolver符号場の傾き×.75秒が+.107/+.679mm、PFS表示面は−.078/+.312mm。元60Hzの判定を表示面で置き換えていない。PFSは約−10.8mm、solver測点は約−.7〜−.8mmで、両者の絶対水位差が依然ある。図は未補正値であり、この差を引いて水深・体積を合わせていない。

[全時系列図](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_reseeding_full_series.png)／[固定窓の拡大図](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_reseeding_late_windows.png)／[ON/OFF 361時刻CSV](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_on_off_gauges.csv)／[全判定・資源・粒子・PFS統計](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_reseeding_comparison.json)。これは実測グラフであり、追加のHoudini/Unity動画ではない。

深水は両条件とも0/.5/3/4.5/5.25/6秒の固定6時刻、各7128点を、保存したBGEOから読み取った。x=.06:.06:5.94m、y=−.54:.06:−.12m、z=−.24:.06:.24m、半径.08m内の実粒子支持を計算し、Volume保持点を除外した。両条件の42,768点ずつが場内・有限・負φかつ支持ありで、共有/ONのみ/OFFのみの警報は全0。OFFの最近粒子距離最大.038723m、支持個数26〜88。中央値は `sorted[N//2]` の上側中央値、p95はnearest-rankであり、通常の中央2値の平均とは区別する。

surfaceは名前付きVolumeとして採録したが `isSDF` metadataはfalseだったため、ここでは**保存solver surfaceの符号場**の実値として扱う。負φ・支持ありは、全域・連続時刻・近表面・薄い空隙・圧力の解像や無空洞の証明ではない。壁近傍では支持球が固体で切られ、低い非ゼロ個数だけで空洞認定しない。観測点は相関しており42,768個の独立統計試行ではない。

IDの観測はONが出生498/消失2656件・53,794→51,636粒子、OFFが出生12/消失0件・53,794→53,806粒子。これを全てreseedイベントや質量と同一視しない。解析板変位/速度は全時刻0、実collision vxは両条件ともk360だけ9.889719×10⁻⁷m/sで、造波の証拠ではない。開始境界t6のk360では原フラグ `piston_started=true` となるが、解析運動は0のまま、k361以後は採録していない。全標本の開始フラグがfalseだったとは記さない。

実OFFのcook合計696.930秒、最大2.899秒、DOP cache最大765.441MiB、私有commit最大8.364GiB、空きRAM最小30.735GiB。solver error/warningなし。361solver＋181PFS＋6予備場の548 BGEO、1,720,726,649bytesを全件読んでSHA照合した。[cache manifest](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_cache_manifest.json)のみ公開し、本体は本機Runsに保持する。18項目UI復元・所有物削除は全PASS、dirty true維持、Undo562→566、HIP保存/読込なし、FPS24維持。

[原JSON/gzip](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/Original)と[原bytes/保存bytesのSHA一覧](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_original_manifest.json)を公開する。ON/OFF 12深水JSONは34,219,926bytesをmtime=0のgzipで2,426,124bytesへ無損失圧縮し、全行のphi・最近距離・支持数を残した。条件・時系列・trace・実行当時Source・UI摘要も対応付けた。実行前のplan JSONと凍結Sourceは当時のまま保存し、未実行という文言は計画固定時の状態を表す。Houdini原JSONの一部説明文字列に文字化けがあるが、原bytesを変更せず保持した。数値・時刻・SHAの解釈はこの日本語本文と再計算記録で示す。

```powershell
python Houdini/Wave22/Candidates/Reseeding03/Postprocess/summarize_reseeding03.py --evidence Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f
```

[Runsを含めない隔離復算](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_isolated_reproduction.json)で図2枚・CSV・統計・READMEと再計算manifestのSHA一致を確認した。この公開再現はローカルBGEO再検証ではない。[最終出典](../../Houdini/Wave22/Candidates/Reseeding03/Evidence/22_revision03_provenance.json)に原入力・実行元・解析元・文書を結ぶ。次の造波試験は別途事前条件・停止条件を審査し、本診断だけで22完了や23精度試験開始を宣言しない。

## 22修正04：静水再判定後、同じDOPで実活塞を始動

Run `22e7801642` は新規所有DOPでt0から再計算した。基線は修正03のOFF `4250d4451f`。L6、λ、三点の絶対位置、dp=.04m、Grid Scale1.5、g9.81m/s²、dt1/120s、APIC、source once、衝突、seed、SOP doreseeding=0、板start6/ramp3/片振幅.02480741527mを固定した。t0のID別P/v/pscale・surface/pressure全voxelと格点を厳密配対し、取得したSOP/内部DOP設定も一致した。清理済み旧DOPや再生キャッシュを新しい計算の代用にしていない。[事前計画の保存版](../../Houdini/Wave22/Candidates/WaveStart04/README_ja.md)と51項目の実行前模擬検査を残した。

原45+45標本の静水判定は再PASS。G3の傾き×.75秒は+.078941585/+.680174425mm、負voxel代理量の窓変化+.001422863%で、修正03の値を再現した。361行のt6入力を独立保存し、その原JSON/条件/policy/gate SHAを両側で検査した。実RPC順序は0始まりevent383の再判定→384の同DOP許可→385のk361採録である。[公開実行摘要](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_execution_summary.json)は元execution SHAと順序IDを残す。許可時のパラメータ変更/resetなし、以後も同じDOPで事前固定のk555/t9.25まで前進した。

応答規則は今回の静水二窓からμ=後窓平均、σ=二窓RMSの最大、E=二窓全標本の最大|η−μ|、q=max(1mm,3σ,E)を決める。元水位は補正せず、同符号5標本の持続超過を60Hz onsetとする。PFSは同じ時間幅の3標本/30Hzで別評価する。5点平滑は極値候補検出だけに使い、raw振幅と左右prominenceを要求し、同符号・順序を保つ全候補鎖から唯一の鎖だけを採る。理論に近いピークを選ばない。詳細と端/plateau処理は凍結した関数に記録した。

| 実観測時刻 s | G1 | G2 | G3 |
| --- | ---: | ---: | ---: |
| solver符号場・最初の持続超過 | 7.366667 | 7.583333 | 7.816667 |
| solver符号場・唯一鎖の谷候補 | 7.800000 | 8.000000 | 8.366667 |
| PFS表示面・最初の持続超過 | 7.466667 | 7.666667 | 7.866667 |

solver場は有序の谷候補を1鎖観測した。隣接遅れ.200/.366667秒をそのまま記録し、理論.375秒との精度試験へ読み替えない。**PFSは応答超過あり・唯一の有効鎖なし**で、solverの判定を表示面へ流用しない。両者の絶対高さの約10mm差は保持し、固定オフセットで水深を合わせていない。[全原水位図](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_startup_full_series.png)／[候補検出図](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_startup_response.png)／[556時刻CSV](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_startup_gauges.csv)を公開した。独立監査でも原関数の再評価と数値が一致した。

`surface` VolumeのisSDF metadata=false、格子予備検査のphysical_pass=falseを保つ。ここでの測点はsolver surface符号場の観測であり、正確な距離場・物理認証を意味しない。六時刻×7128点は**全て始動前t<=6**、42,768点が場内・有限・負φかつ半径.08m内の実粒子支持あり。上側中央値/nearest-rank p95の定義は同じで、駆動中の全域連通・無空洞・漏れ・非砕波へ拡張しない。駆動中は三点の局所交差、PFS、solver/時計/有限/ID/壁外20mm/資源保護に限られる。

実collision vxと解析活塞速度の最大差2.301124×10⁻⁵m/sは既定1×10⁻⁴m/s保護内だった。k360では開始フラグtrueだが解析変位/速度0、実collision vxは9.889719×10⁻⁷m/s。粒子は53,794→54,037、観測ID出生243/消失0であり、質量や全reseed回数ではない。内部onlysourceseeding=1/reseed=1/reseedsinglepass=1も保持した。

556solver/粒子＋278PFS＋6予備場の**840 BGEO/2,640,361,537bytes**を全件SHA照合した。[原JSON/gzip・実行元・全cache manifest](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/README_ja.md)を公開し、BGEO本体は本機Runsに保持する。cook合計1075.137秒/最大2.835秒、581RPC合計1432.576秒。DOP cache最大805,210,137bytes、private commit最大9,054,294,016bytes、空きRAM最小33,594,212,352bytes。18項目UI復元/所有物削除PASS、完了不明RPCなし、HIP保存/読込/clearなし、FPS24維持を独立照合した。

### 実PFS媒体と残る範囲

計算後に新所有File SOPへliteral BGEOだけを読み、原P/有向indicesと配対した。固定UI frame1/FPS24の単一フレーム撮影で、FlipbookのinitializeSimulations(False)/useMotionBlur(False)を明示した。既存DOPへ接続せず、[7枚の原静止画と撮影report](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Media)を保存した。固定時刻はFront t6/7/8/9/9.233333、斜視t8/9.233333である。

[実視口動画](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Media/22_startup_PFS.mp4)は固定Frontのk360..552を2刻みで採った97枚、H264/1280×720/30fps/3.233333秒、全復号エラー0。日本語字幕のみ追加、形状加工・空間倍率変更・時刻補間なし。再生末区間はk552/t9.2を保持し、PFS終端k554/t9.233333は別静止画、solver終端t9.25のPFSはない。[媒体manifest](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Media/22_media_manifest.json)で元BGEO→PNG→動画のSHAと時刻を追える。全槽6mの画角では起伏が微小であるため、動画と実測曲線を併読する。主役大波の証拠と呼ばない。撮影後もUI18とgrid/color復元は全PASSだった。

G3閉端帰還は対象λでt10.144秒、長波上限速度√ghではt9.405秒が目安。停止9.25はこれより早いが、広帯域ramp・初期残動・圧力応答を排除せず無反射は保証しない。ramp完成包絡のG3到来目安11.664秒より前に終了しており、定常5周期や23の精度試験ではない。**結果は短窓の始動応答に限り、22完成・非砕波・主役波・HMDは未認定。**

公開資料からの再計算：

```powershell
python Houdini/Wave22/Candidates/WaveStart04/Postprocess/summarize_start04.py --input Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642
```

[Runsなし隔離復算](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_isolated_reproduction.json)でCSV・2図・数値摘要と再計算manifestのbytes一致を検証する。これはBGEO再検証やGUI再撮影ではない。[修正04の最終出典](../../Houdini/Wave22/Candidates/WaveStart04/Evidence/22_revision04_provenance.json)が原データ・凍結実行元・後処理・媒体・今回文書を結ぶ。

## 22修正05：既存cacheのPFS局所差を診断

唯一の基線は04 Run `22e7801642`。既存mesh/pilotを `hou.Geometry.loadFromFile` だけで読み、新規solver計算・ノード作成・DOP/SOP cook・UI変更を行っていない。最初のk468を実測審査してから、原JSON SHA・plan/readerを束ねた別許可で残29組を読んだ。[固定計画・68項目の離線検査](../../Houdini/Wave22/Candidates/PfsDiagnosis05/README_ja.md)を保持する。

時刻は7.8〜8.766667秒の30Hz30配対、各Gのx±.12m/.02m刻みとz=−.12/−.06/0/.06/.12mの計195列、全5850断面。60 BGEO/153,892,203bytesの原SHAを照合した。中央90配対の原04 solver121点/25二分・PFS既定first-hitは、原値との差0mだった。主rayはtolerance1µm/前進2µm、感度rayは10µm/20µm。面別patternを含む各11,700交点の双方向primitive/高さ対応が一致し、既定/主/感度queryの高さ差は全0だった。

各列の二交点は上側表示面と底側表示面で、二層の自由水面ではない。上側normal Yは正、下側は負。solverの848,250個のφ標本は有限、5850列で単一wet→dry、零台地・接線零点なし。観測範囲では首命中の取り違え、二容差間の差、標本で見える複数交差はG3不採用を説明する証拠にならなかった。ただし、有限の線・時間・数値許容で未標本化の薄層や全3Dの問題を完全に排除してはいない。`surface` VolumeのisSDF metadata=falseも保持する。

| 元04 G3谷候補 | 時刻 | raw振幅 | 左prominence | 右prominence | 元q=1mm |
| --- | ---: | ---: | ---: | ---: | --- |
| solver符号場 | 8.366667s | 3.618661mm | 1.507968mm | 3.396022mm | 採用 |
| PFS表示面 | 8.266667s | 1.991066mm | 0.827461mm | 1.542008mm | 左だけ不足、不採用 |

元04全時系列・凍結detectorのstatus/onset/featuresを含む結果全体を再現し、原q/候補/唯一鎖は変更しなかった。PFS候補の左右支持は切れていない。rawの最小標本時刻（PFS8.3、solver8.333333）と平滑候補時刻を区別する。二つの候補の.100秒差を波速や物理位相誤差に換算せず、5点の時間幅がPFS4/30秒・solver4/60秒で異なることを残した。近傍断面に中央閾値を移植していない。

[未補正の中央時系列・差](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_centers.png)／[実cacheのx/z断面](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_sections.png)／[G3元候補の左右prominence](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_G3_prominence.png)を公開した。これは実測値の図で、新しい視口画像や想像流体ではない。新動画は作らず、同じ04の実PFS動画を参照する。

G3中央のPFS−原solver差は−9.896538〜−8.300951mmで、固定10mmではない。k496のx断面幅はPFS5.119145mm/符号場2.056885mm、z断面幅は4.205793/2.603760mm。PFSの空間変化が一律に小さいとは言えない。quad対角線補助差は最大.213745mm、投影凸性は未検査で、元nativeを置換していない。PFS3.0の明示smooth類は全0であり、Final Smoothや空間再構成を単一原因と認定しない。定数水位補正も行わない。

原JSON30本110,422,809bytesを12,839,583bytesへ無損失gzip化し、全交点・面頂点・φ・誤差を公開した。[5850行CSV・原gzip・出典](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/README_ja.md)で元/保存SHAを結ぶ。BGEO本体は本機Runsに保持。読戻し合計69.735298秒、最大2.427344秒/組、空きRAM最小36,150,370,304bytes、UI4項目前後一致、完了不明RPCなし。UI変更がないため18項目復元をしたとは記さない。

```powershell
python Houdini/Wave22/Candidates/PfsDiagnosis05/Postprocess/summarize_profile05.py --input Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642
```

[RunsもBGEOもない隔離入力からの復算](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_isolated_reproduction.json)では、コピーした原gzip/04資料だけで3図・CSV・摘要・解析manifestの6出力が同一bytesとなった。これは新HOM読戻しや物理再計算ではない。[修正05最終出典](../../Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/22_revision05_provenance.json)に資料・解析・文書を結ぶ。**PFS唯一鎖なし・減幅の単一原因未確定・22未完成を保持する。** 22の非砕波連続伝播/full測点/媒体と、23の理論精度、25の反射/収支は別の後続検証である。

## 22修正06：旧PFSの再現とt6一面の細分化感度

唯一の物理入力は04 Run `22e7801642` の既存pilot BGEO。新solverや板運動は計算せず、PFS3.0のvoxelsize `.5→.25` だけを変える事前試験を行った。粒距.04mなので指定面化voxelは.02→.01mに相当するが、solver格子の収束試験ではない。**新`.25`はk360/t6一面だけ。波形・q・唯一鎖を再判定せず、次frameは利用者確認後の別審査とする。**

初回/Retry01は入力前assert/Manualの空FileでHOLD、Retry02は`needsToCook(time=...)`のTypeError、Retry03はdetail属性一覧順の差で原HOLD、Replay05はHDA文字列符号化で停止した。原記録を保持し、別のDecision04は一意nameによる一覧順だけの正規化で全署名が一致すると判読した。HDAは公式binaryContentsの原bytesをSHA化し、失敗箇所を別候補で修正した。[全9Runの原JSON・10候補・順序](../../Houdini/Wave22/Evidence/Revision06/README_ja.md)を公開する。5つのHOLDを流体の物理不合格や成功へ読み替えない。

短いAuto更新窓でFile/Nullをfreeze→Manualで全入力署名を判定し、PASS後だけ別Auto窓でOutをforce cookする。旧`.5`のk360/k474/k496は、原04面のordered P・有向面indices・型/closed・3点native・保存再読が厳密一致した。再保存BGEOのfile SHAは異なるので、未検査属性を含む全bytes一致とは記さない。

Refine360 Run `pfsrefine06_c208ac35e3` は新しいSteam Houdini PID26892/22.0.429/Indie/FPS24で実行。成功k360の入力署名・HDA/Convertと照合し、実評価166 PFS parmの差はvoxelsizeだけだった。原JSONの窓名`OLD_HALF_PFS`は同一helperからの履歴ラベルであり、実要求/評価値は`.25`。ラベルを原記録から消していない。

| 中央点 | 原solver符号場 mm | 旧`.5` PFS mm | 新`.25` PFS mm | 新−旧 mm |
| --- | ---: | ---: | ---: | ---: |
| G1 | −0.988379 | −10.810441 | −10.762161 | +0.048280 |
| G2 | −0.609264 | −7.603443 | −7.530844 | +0.072598 |
| G3 | −0.417516 | −10.671026 | −10.819083 | −0.148058 |

原絶対高さを保ち、固定10mm補正はしない。新面159,932点/159,930面、3,494,161bytesは保存再読一致。旧38,926点/38,924面との形状同一を要求せず、同じ新面のdefault/主/感度/面限定query整合を検査した。UI18復元後に旧新各195位置を別RPCで採り、同じ座標/field・中央solver誤差0・各列上下2交点を確認した。新`center_parity_passed=false`は旧面との差という予告した診断値で、旧面の同フラグはtrueである。

[中央の未補正水位と差の実測図](../../Houdini/Wave22/Evidence/Revision06/22_refine06_centers.png)／[195位置の実差](../../Houdini/Wave22/Evidence/Revision06/22_refine06_spatial_difference.png)／[原値CSV](../../Houdini/Wave22/Evidence/Revision06/22_refine06_profiles.csv)。全195位置の新−旧は−.493705〜+.678122mm、平均+.089239mm、RMS.223545mm。これは局所位置の分布で測定不確かさや独立反復ではない。下底交点を第2自由面と呼ばず、fieldのisSDF metadata=false、全域/時刻間状態未検証を保持する。細分化で旧solverとの差が解消した、波が正しくなったとは判定しない。

面化RPC17.634901秒、2番目Auto窓7.250425秒、旧/新profile2.270634/10.993487秒。観測private増分最大331,362,304bytes、空きRAM最小34,102,996,992bytes。節目観測で連続privateピークやVRAMではなく、旧PIDの`.5`との性能比較もしない。UI18/owned削除はPASS、通信不明なし。一方HIP dirtyはfalse→trueであり、完全に元状態へ戻したとは記さない。HIP保存/読込/clear/undo消去なし。後続只読profileはframe/FPS/mode/dirtyの前後一致を確認した。

28原JSON8,252,599bytesを990,124bytesの無損失gzipで公開し、[元/保存SHA](../../Houdini/Wave22/Evidence/Revision06/22_original_manifest.json)、[本機BGEO manifest](../../Houdini/Wave22/Evidence/Revision06/22_cache_manifest.json)、凍結Sourceを結ぶ。BGEO本体は本機保持。新視口動画は作らず、今回の科学図と04実動画を別資料にする。

```powershell
python -B Houdini/Wave22/Evidence/Revision06/Source/summarize_revision06.py --input Houdini/Wave22/Evidence/Revision06
```

[Runs/候補/BGEOなし隔離復算](../../Houdini/Wave22/Evidence/Revision06/22_isolated_reproduction.json)で2図・2CSV・摘要・解析manifestの6出力が同一bytesだった。これは公開測定値の復算で、Houdini再実行ではない。[修正06最終出典](../../Houdini/Wave22/Evidence/Revision06/22_revision06_provenance.json)を保存する。**22は中間成果のまま。非砕波連続伝播・full測点・媒体、23精度・25収支/反射、主役波・HMDは別の未完了項目である。**

## 22修正07：k474一面のPFS細分化感度

最新の継続指示に基づき、修正06の原候補/Run/証拠を保持したまま、根担当と独立担当の事前審査後にk474（t7.9）一面だけを実行した。[新しい凍結候補と171項目の離線記録](../../Houdini/Wave22/Candidates/PfsSensitivity07Refine474/README_ja.md)を保存する。唯一の物理入力は修正04 Run `22e7801642` の保存pilotで、新solver・板運動を再計算していない。

Run `pfsrefine07_f2bf190159` はSteam Houdini 22.0.429/Indie/PID26892/FPS24、絶対frame190.6で実行した。Direct/File/Nullの全署名を照合し、許した差は一意属性名によるdetail一覧順だけ。旧k474成功RunとHDA binary/library・Convert評価値が一致し、実評価166 PFSパラメータの差はvoxelsize `.5→.25` だけだった。粒距.04mに対する表示面voxel指定.02→.01mであり、solver格子の細分化ではない。

| 中央点 | 原04 solver符号場 mm | 旧`.5` PFS mm | 新`.25` PFS mm | 新−旧 mm |
| --- | ---: | ---: | ---: | ---: |
| G1 | −4.264757 | −13.093209 | −13.017213 | +0.075996 |
| G2 | −3.595844 | −9.756213 | −9.752607 | +0.003606 |
| G3 | −2.307102 | −11.981583 | −12.140518 | −0.158936 |

原04中央測点値は121標本/25回二分、05局所断面の中央field値は別定義で−4.264832/−3.595886/−2.306824mm。両方を[中央CSV](../../Houdini/Wave22/Evidence/Revision07/22_refine07_centers.csv)へ保持し、置換や固定10mm補正はしない。旧面の原nativeとsolver原観測の再読誤差は0m。新面160,642点/160,640面・3,497,363bytesは、保存再読のordered P/有向面/型/closedが一致した。

UI復元後に旧新各195位置を別只読RPCで採り、旧側は05公開195断面の指定15項目と完全一致した。座標順・重複なし・同一field・中央solver誤差0・局所単一wet→dryを確認。各面のdefault/主/感度/面限定queryの上下2交点を調べ、面ごとのprimitive根拠と高さ/法線方向が整合した。旧新primitive IDの同一や下底が第2自由面だとは記さない。新`center_parity_passed=false`は旧面に対する差の診断値であり、旧側はtrueである。

[中央原値の実測図](../../Houdini/Wave22/Evidence/Revision07/22_refine07_centers.png)／[195位置の差](../../Houdini/Wave22/Evidence/Revision07/22_refine07_spatial_difference.png)／[195行CSV](../../Houdini/Wave22/Evidence/Revision07/22_refine07_profiles.csv)。全位置の新−旧は−.584275〜+.628144mm、平均+.091844mm、RMS.229214mm。これは近傍位置の分布で独立反復・不確かさではない。単一面から谷候補の採否・伝播・唯一鎖・物理精度を判断しない。isSDF metadata=falseのsolver符号場という制限も保持する。

面化RPC20.837554秒、Auto窓2=8.096435秒、旧/新profile2.959956/10.814633秒。可用RAM最小27,957,891,072bytes、観測private増分228,343,808bytes。節目観測でVRAMや連続ピークではない。UI18/所有ノード削除PASS、通信不明なし、dirtyはtrue→true、undo0→0。HIP保存/読込/clearなし。継承した原窓ラベル`OLD_HALF_PFS`を改変せず、実voxelsize=.25を根拠とする。

[結果README・原記録・再現](../../Houdini/Wave22/Evidence/Revision07/README_ja.md)に5原JSONと2基線JSON、実行前文書6本を無損失gzipで保存した。[原/保存SHA](../../Houdini/Wave22/Evidence/Revision07/22_original_manifest.json)、[本機保持3 BGEO](../../Houdini/Wave22/Evidence/Revision07/22_cache_manifest.json)、[最終出典](../../Houdini/Wave22/Evidence/Revision07/22_revision07_provenance.json)を結ぶ。候補は元bytesの通常Gitファイルで、現況文書更新前の内容もcommit352e1baから別保存した。

[Runs/候補/BGEOなし隔離復算](../../Houdini/Wave22/Evidence/Revision07/22_isolated_reproduction.json)は公開gzipから6出力をbyte同一再現した。新視口動画は作らず、今回の実測グラフと04の実PFS動画を区別する。**22は未完成。k496新面や連続列、q/鎖の再判定は今回未実行。非砕波連続伝播/full測点/媒体、23精度・25収支/反射、主役波・HMDは別の未完了項目を維持する。**
