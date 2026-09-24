# 22：実 FLIP 水槽の中間記録 — 進行波は未完成

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

主記録 `0652da0179` は dp=.04 m、Grid Scale=1.5、実solver voxel=.06 m、表示mesh voxel=.02 m。作成時からピストン開始を絶対t=3秒に固定し、t=0〜3秒の181標本で実変位・速度とも0だった。判定窓は事前に (1.5,2.25] と (2.25,3] 秒へ固定し、それぞれ45標本。平均を差し引いた水位や後から選び直した窓は使っていない。

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

この中間成果では手順22を完了にしない。次は物理条件を変えず待機を延長する新規ケースを事前定義し、後半の固定窓を通した場合だけ同じDOPで駆動へ進む案を審査する。無条件な長時間計算や基準の緩和は行わない。実進行波、非砕波の確認、23の理論誤差、24の収束、25の収支・反射、HMDは未検証として保持する。
