# 22：実 FLIP 水槽の中間記録 — 進行波は未完成

最新の22修正02は、内槽長だけを6.000mへ変更した感度試験 `db52394211`。**鏡像ラベルは改善したが、361時刻の静水判定は再びFAIL。駆動・波動画はない。** 初期粒子などの派生変化を含むため、格子位相だけの因果とはしない。以下にt3と22修正01の履歴を残し、末尾に最新結果を追記する。

- [22修正01・t6の全時系列図](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_full_series.png)／[固定判定窓の拡大図](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_late_windows.png)
- [22修正01・361時刻CSV](../../Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_checkpoint6_gauges.csv)／[t6判定の原JSON](../../Houdini/Wave22/Evidence/Curated_Runs/3e5ff87a29/22_checkpoint_gate.json)

- [最新L6と旧槽の比較図](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_full_series.png)／[固定窓](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_late_windows.png)／[比較CSV](../../Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_gauges.csv)

**静水の駆動開始判定は不合格。造波段へ進めていない。** 新規水槽の接続、実時計、キャッシュ、静水の測点を確認したが、手順22が求める非砕波の伝播・複数の峰の到来・伝播動画は未完成である。シミュレーションの実行失敗と、正常に実行できた試料が物理上の開始条件を満たさないことを区別する。

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
