# 22修正02：内槽長6.000mの事前登録計画・保存版

**これは実行前に固定した計画の保存版。固定当時は未実行だったが、その後の許可された実Run db52394211は361標本で静水FAILとなり、駆動せず終了した。** [22修正02の実測結果](../../Docs/Progress/Step_22_ja.md)を参照する。以下の条件・予算・順序は事前登録の記録であり、実行当時Source/plan JSONは変更しない。

## 変更と保持する条件

| 項目 | 事前登録 |
| --- | --- |
| 唯一変更する設計入力 | 内槽長L：5.980790346583645mから6.000m、約+0.3212% |
| その派生変更 | domainの長さ/中心、初期水、底/側壁の長さ/中心、右端壁位置。初期粒子P/ID・格子境界も変わり得る |
| 固定するλと測点 | λ=2.9903951732918226m。x=2.242796379968867 / 2.9903951732918226 / 3.7379939666147783m、z=0 |
| 固定物理・離散条件 | dp=.04m、Grid Scale1.5、g9.81m/s²、ρ1000kg/m³、dt1/120s、APIC、seed2101、reseeding、source_once、閉端・底・側壁とParticle衝突、圧力適応OFF |
| 時間・表示 | 全体FPS24を保持、solver採録60Hz、PFS表示mesh30Hz。板の開始絶対時刻t6、3秒ramp、片振幅.02480741527m |
| 初期粒子の保護 | 新t0でP/v有限、ID一意、空でない、内槽から20mmを超えた点なしを確認。旧53,500粒子P/IDとの一致assertは適用しない |
| 許可条件 | 原(4.5,5.25]・(5.25,6]の各45標本。窓間平均差、平均まわりRMS、傾き×.75sの各上限3mm。負SDF代理量の窓平均変化1%以内 |

これは形状・初期化・格子を含む長さの感度試験であり、圧力格子の位相だけの因果試験とは呼ばない。粒子数と負SDFセル代理量は実水量・質量保存の証明ではない。元のL、旧t3/t6の標本・出典・図表は上書きしない。

## 最初の格子・壁観測

承認後の接続では現PID・版・UI・Indie分類・FPSを再取得する。UI保存後にManual→frame1を確認し、登録済み所有ノードだけを作る。各RPCは独立namespaceへ必要定義を渡し、数値はHoudini保存JSONとsource SHAを照合して元精度で読む。

1. 指定した新規repo内の旧t6 `Runs/3e5ff87a29/Cache/pilot_001.bgeo.sc` を公開samplesのSHAで確認し、承認後のHOMでpressure/surfaceだけを読む。旧ファイルにcollision場はないため旧collision比較を作らない。
2. 新t0とt1/60は通常標本として保存したBGEOをSHA照合して読戻す。同時刻のparticlesへ再度force-cookしない。間のt1/120だけ同じDOPを前進評価してcook(force=False)し、実simulation.time/dtを保存する。resetや補間は行わない。
3. 各時刻のpressure/surface/collision surfaceの名前・型・bounds・resolution・transformと、`indexToPos((0,0,0))` の実cell中心、単位index差の3軸を記録する。bounds minをcell中心へ代用しない。t0の小さなpressure場が両壁へ未展開なら鏡像ラベル適用外とし、1/60の拡張pressureで両壁への包含を確認する。
4. x方向のcell中心をx_c、実間隔をΔxとして、q0=(0−x_c)/Δx、qL=(L−x_c)/Δx、Eg=|q0+qL−round(q0+qL)|を計算する。Eg≤.001cellは**数値上の鏡像互換ラベルだけ**である。改善・悪化は早期停止や造波許可の条件にしない。
5. collision SDFをd=−.12..+.12m（.03m刻み）、y=−.45/−.30/−.15m、z=−.15/0/.15mで81対採取する。φ(d,y,z)とφ(L−d,y,z)の値、差の最大値/RMS、実Δxを残す。両壁の9縦横位置ずつ、計18根についてd=±.06mの固体側負/槽内側正を確認し、二分区間幅≤1e−5mまで求める。範囲外・非有限・符号欠損は停止する。
6. 静止velocity VDBのactive領域が空の場合、isEmpty/activeVoxelCountを記録し、transform/voxelと背景速度だけを調べる。空fieldのbounds・cell中心・Egは評価しない。非空VDBはactiveVoxelBoundingBoxとresolutionを区別して記録する。

新旧pressureのEgと新collisionの鏡像が良好でも、静水や進行波の合格ではない。本計画を固定した時点では実HOM互換性は未検証であり、模擬namespace検査だけを実Houdini検査へ読み替えなかった。その後の実観測は上記の結果に別記した。根拠：[H22 Volumeのcell中心/標本化](https://www.sidefx.com/docs/houdini/hom/hou/Volume.html)、[H22 VDBの疎なactive領域/中心](https://www.sidefx.com/docs/houdini/hom/hou/VDB.html)。

## 健康点と継続・停止

t0から順次採録し、t.5（k30・31標本）で時計・場・粒子・壁外点・資源の各保護が通ったことを保存する。これは初期化と費用の健康点だけで、3mmの静水合格や造波許可ではない。健全なら同じDOPをt6まで継続する。解析板変位・速度はt6まで0でなければ拒否し、実collision速度は既存の一致性許容で別検査する。

361標本の原JSONへ元と同じ純関数を適用し、**FAILなら保存・finally復元して終了、追加標本も駆動許可も0回**とする。全項目PASSの場合だけHoudini側でも同じ原JSON SHAとメモリー内標本を再照合・再判定し、同じDOPでt9.5（k570）まで続行する。Egの判定はこの許可経路に入れない。

9.5秒は3秒rampの初期応答であり、定常・無反射・5周期の精度窓ではない。L増分による閉端反射の時刻差は約16msにすぎず、前回の限定は解消しない。元3点の一次診断はt≤9.35、追加.5λの読戻し案は別の近場診断として扱う。波の実観測に至らなければ22完成にしない。

## 費用と復元

[JSON予算](Evidence/Length6_Planned/22_length6_budget.json)は公開された旧t6の361標本/542cache manifestから計算した。実平均4.604MB/時刻、最大5.134MB/時刻。旧と同じ平均なら新361標本は約1.662GB・692秒cook、571標本は約2.629GB・1,094秒cookである。通信時間・格子観測・新しい初期化・駆動後の非線形費用は別で、長さ比だけから精密な費用を予測しない。

raw予算は8MiB×571標本に初期格子/衝突保存64MiBを加え、4,857,004,032bytes。開始時Gドライブ空きは2倍+10GiBの20,451,426,304bytes以上を要求する。運用上限は空きRAM≥8GiB、所有基線からprivate commit増加≤12GiB、DOP768MiB（実測≤1.05倍）、G空き≥10GiB、単標本≤30秒、直近30標本中央値≤6秒、残りcook予測≤90分。自動disk spill/非対話disk cache/explicit cacheは無効を維持し、Cへ退避しない。

既存HIPの保存/読込/クリア、全scene走査、共有定義の変更はしない。通常終了と既知の失敗では所有物削除と18項目UI復元を検査する。完了不明のRPCは並行要求やGUI killで解決せず、復旧要否を記録して進行役へ報告する。dirty/Undoを消して元に戻ったように見せない。

## 実行前の検査とコマンド

[模擬検査](Evidence/Length6_Planned/22_length6_logic_checks.json)は公開t6のFAIL、合成一定値のPASS分岐、格子式、明示合成の壁・無効field、所有基線/許可/grid/sampleの独立namespaceを検査する。旧fixtureは変更せず、BGEO/Houdini/MCPは呼ばない。合成データは物理証拠ではない。

```powershell
python Houdini/Wave22/Source/check_length6_logic.py
python Houdini/Wave22/Source/prepare_length6_budget.py
```

通常起動は計画表示のみ。以下は固定時点で未実行だったコマンド。その後許可を受けて実行しt6 FAILで終了した履歴であり、自動的な再実行許可ではない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 Houdini/Wave22/Source/run_length6.py --execute-reviewed-plan
```

この案のSource/planはRunへ凍結しSHAを保存した。格子互換ラベルが得られても、22修正01に続いて静水の開始条件はFAILのままである。
