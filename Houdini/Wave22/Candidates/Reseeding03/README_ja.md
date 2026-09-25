# 22修正03：SOP再シーディング切替の配対診断

**OFFの実計算4250d4451fは361標本で正常終了し、元の静水判定PASS・深水被覆警報0・UI18復元PASSとなった。造波はしていない。** [実結果と図・CSV・原JSON](Evidence/OFF_Result_4250d4451f/README_ja.md)が現在状態である。以下の設計表とSource内planは実行前に固定した記録で、JSONの未実行表現は当時の状態を示す。旧L6データ・実行元は変更していない。

## 仮説と変更の境界

[SideFX DOP FLIP Solver公式資料](https://www.sidefx.com/docs/houdini/nodes/dop/flipsolver.html#reseeding)は、再シードが遅い流体の表面ノイズに影響し得る一方、近壁などの空気ポケットを防ぐ役割もあると説明する。これは今回の原因が再シードだと示した結果ではない。SOP `doreseeding=0` を適用する際には、新しく所有する内部DOPの実設定も記録し、公式のOnly Source Seedingと同義であると未確認のまま断言しない。現在はAPICであり、FLIP向けの粒子半径/格子比からAPICを欠解析と断定することも避ける。

| 項目 | 固定する条件 |
| --- | --- |
| 唯一の物理パラメーター変更 | 同じL6の `doreseeding` を1→0 |
| 水槽と測点 | L=6.000m、幅/水深=.600m、λ=2.9903951732918226m。x=2.242796379968867 / 2.9903951732918226 / 3.7379939666147783m、z=0 |
| 計算・初期化 | dp=.04m、Grid Scale1.5、g9.81m/s²、ρ1000kg/m³、dt1/120s、APIC、seed2101、source_once、Waterline/Narrow Band OFF、同じ衝突と閉端 |
| 時計・保存 | 全体FPS24を変更せず、0〜6秒の361標本、solver SDF60Hz、PFS30Hz。初回source・初期水・表示面設定を変えない |
| 板と終点 | 元と同じ開始t6/3秒rampを保持するが、必ずt6で診断終了。解析変位/速度は採録中0。静水PASSでも駆動許可を出さない |
| 静水判定 | (4.5,5.25]と(5.25,6]各45点。窓間平均差・平均まわりRMS・傾き×.75秒は3mm、負SDF代理量の窓平均変化は1%という元の規則 |

初態は基線の53,794粒子を元BGEOから取り出し、ID順のP・v・pscaleを元精度で比較する。surface/pressureのtransform・解像度・中心・間隔と全初期voxel値も厳密比較する。同seed/同数だけでは配対成立にしない。差があれば「初態とreseedの複合変更」として停止し、源を調整して一致へ誘導しない。基線pscaleは約.048mで、以下の.08mは別に事前設定した観測半径である。

## 基線の保存BGEO：6時刻の読戻し結果

[実読戻し摘要](Evidence/22_baseline_readback_summary.json)では全42,768点が場内・有限・負SDF・粒子支持ありで、粗い被覆警報は0だった。6原JSONのSHAを確認し、総読戻し13.9316秒、17,109,916bytes。UIのframe/FPS/dirty/更新modeは各前後で同じ。これは無空洞の合格ではない。

時刻は0、.5、3、4.5、5.25、6秒（k=0/30/180/270/315/360）に固定する。入力は `Houdini/Wave22/Runs/db52394211/Cache/pilot_*.bgeo.sc` の指定6ファイルだけであり、[公開原標本](../../Evidence/Curated_Runs/db52394211/22_pilot_samples.json)のSHAに結合する。既存HIP内容、過去DOP、他のgeometryは読まず、保存cacheを新しいメモリー上の `hou.Geometry` へ読み込む。ノード作成・cook・setFrame・HIP保存/読込を行わない。

固定した99×8×9=**7,128点**を、各ファイルで次の順に観測する。

1. x=.06:.06:5.94m、y=−.54:.06:−.12m、z=−.24:.06:.24mを整数cmから作る。点順と座標のSHAを保存する。
2. 名前surface・密Volume型・実bounds/transform/解像度を確認する。各点は厳密にfield内であることを先に検査し、外側のsample戻り値0を水面へ読み替えない。field外または非有限は無効観測である。
3. 全primitiveの参照点を実粒子から除く。Volume保持点を粒子支持に加えない。非空・有限位置・ID一意・元標本との実粒子数一致を確認する。
4. 各ファイルで一度だけ空間hashを作り、半径r=.08m以内の粒子個数と全粒子への最近距離を求める。通常は27近傍cellだけを検査し、支持0の場合はcell距離下界で探索を広げる。全点×全粒子行列は作らない。
5. 各点の座標・φ・最近距離・半径内個数を**全行保存**し、負SDF/支持あり、負SDF/支持0、非負SDF/支持あり、非負SDF/支持0、無効fieldを分けて計数する。分布と警報点indexも併記する。壁隣接点の支持球は壁に切られるため、低い非ゼロ個数を一律警報にしない。

分布の `median` は `sorted[N//2]` による**上側中央値**で、偶数Nの中央2値の平均ではない。p95はnearest-rank。OFFにも実行済みの同じ計算法を使い、原読戻しSourceとJSONを作り直さない。

実MCPはローカルJSONを書いた後のJSON SHAとSource SHAだけを返す。呼出側はその元JSONをSHA照合して読むため、7,128行の返却切断やfloat丸めを判定へ混ぜない。6ファイルは順次処理し、処理ごとのGeometryを解放する。単体観測予算90秒、client timeout180秒。読み込み等の単一APIが停止しない場合も強制killせず、RPC完了不明として追加要求を送らない。

## 被覆警報と正式OFFの停止規則

基線の6時刻を先に確認し、警報があれば座標/時刻/φ/距離/個数/SHAを提示してからOFF実行の判断を受ける。ONとOFFの同点・同時刻を比較し、共有警報・ONだけ・OFFだけを分ける。基線にもある警報をOFFの新しい欠陥として数えない。

OFFの6チェック点で単一のφ≥0または支持0があっても、**coverage_alertを保持して原安全制限内で固定t6まで継続**する。これは孤立した補間/境界警報で結果を打ち切らないためであり、物理合格ではない。場外/非有限、初態配対不成立、元の求解器・漏粒・時計・資源保護の違反は早期停止する。.5秒は健康点であり静水合格ではない。

警報がある場合も、元静水gateの実数が減った/判定がPASSだったという限定した結果は記録できる。ただし物理改善・無空洞・採用とは主張しない。警報がなくても、支持1粒子以上を充填・圧力解像・質量保存・連結性・波精度の証明にしない。近表面、6cm間隔より薄い空隙、時刻間の現象は未検査であり、42,768点時刻は互いに強く依存する。1seed×1runを独立反復の統計と扱わない。

## 費用と実行前検査

[合成検査と費用記録](Evidence/22_reseeding03_offline_checks.json)は、乱数96点のhash探索対全距離走査、半径境界、空/非有限、field外をsampleしないこと、符号/支持交差分類、初態差、独立RPC namespace、JSON ACK、元L6のFAIL、途中警報を保持した361点制御を検査する。明示的な合成54,000粒子・7,128照会の探索部分は約1.24秒だった。これは実BGEO decode、HOM照会、通信、JSON保存を含まず、実読戻しの速度保証ではない。

公開manifestによればt0の指定BGEOは1,058,043bytes、6ファイル合計22,034,153bytes。初回にt0の1ファイルだけを読み、3.1251秒・2,855,674bytesを報告した後、別許可で残り5件を読んだ。以下はその手順の記録であり、既定コマンドは今も計画表示だけである。

```powershell
python Houdini/Wave22/Candidates/Reseeding03/Source/check_deepwater_logic.py
python Houdini/Wave22/Candidates/Reseeding03/Source/run_baseline_readback.py
```

以下は実施済み基線t0読戻しのコマンドである。再実行を自動許可するものではない。実行時の現PID53912/H22.0.429/Indie/UI/FPS24をmetadataで確認した。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 Houdini/Wave22/Candidates/Reseeding03/Source/run_baseline_readback.py --execute-reviewed-readback --samples 0
```

基線L6の361標本cook合計は694.264秒、中央値2.225秒/最大3.060秒だった。OFFの費用へ直接保証しない。将来OFF runの予約は361×8MiB＋観測JSON64MiB=3,095,396,352bytes、開始時G空きはその2倍+10GiB=16,928,210,944bytes以上。空きRAM≥8GiB、私有commit増分≤12GiB、DOP768MiBの実上限1.05倍、G空き≥10GiB、単標本≤30秒、直近30標本中央値≤6秒、残予測≤90分を維持する。Cへのdisk spillは無効を読み返す。数値計測と読戻し費用は別に記録する。

## OFF runner候補と実行前判定

[OFF用固定計画](Source/reseeding_off_plan.json)と[runner](Source/run_reseeding_off.py)を準備した。[33項目の離線検査](Evidence/22_off_runner_checks.json)では、作成条件の差分白リスト、基線の原FAIL、t0厳密配対前のsample1拒否、元JSON SHA不一致、別RPC namespace、元判定の両側一致、coverage警報を保持した361点終端を確認した。先行の深水観測39検査とは別であり、OFF実計算の合格ではない。

生成器・元gate・UI guard・格子観測のSourceは、22修正02で実行したbytesをそのまま新Runへ複製する。実物理差はrunner定数 `RESEEDING=False` のみ。作成結果はcase名と実行時メモリ値を除いて同一を要求し、solver_parameters内でdoreseedingだけを1→0として照合する。所有内部schemaを採録し、SOP設定と公式DOP設定の関係を結果で確認する。

snapshot→Manual→frame1の後に新所有ノードを作り、t0保存cacheの厳密配対が両側で通るまでsample1を許可しない。基線と同じt0→1/120→1/60の格子観測順序も保持する。以後は各標本で同一DOP ID、元の時計・有限・漏粒・局所水面・solver warning/error・資源条件、disk spill無効を確認する。深水観測は保存済みBGEOの読み取りだけで、同時刻のsolverを再cookしない。

元のt6 gateをhostとHoudiniの双方で、同じ361標本JSON/条件SHAへ結合して再計算する。PASSでもdrive_authorizedは常にfalse。FAILも結果として保存し、通常終了/既知失敗は所有IDで削除して18項目UI復元を検査する。RPC終了が不明なら追加要求や並行cleanup、GUI killは行わず復旧要否を報告する。

以下は独立審査と進行役の明示放行後に実行したコマンドである。再実行は自動許可しない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 Houdini/Wave22/Candidates/Reseeding03/Source/run_reseeding_off.py --execute-reviewed-off-plan
```

基線の548 BGEOは1,682,590,892bytes、6深水JSONは約17.11MB、solver cook合計694.264秒だった。これらはON基線の実費用であり、OFFの速度/サイズを保証しない。新観測の費用は各標本cookと別に残す。OFFの実t0厳密配対、静水判定、六時刻被覆、UI復元の結果は上記結果に保存した。内部Only Source Seeding=1/Reseed Particles=1であり、全内部reseedをOFFと表現しない。

内部設定は凍結ONの `22_initialization_schema.json` と所有ルート名を除いて比較し、差分を保存する。OFFのseed関連パラメータは所有ノードだけを補足採録する。旧ONに未収録の項目は配対未確認とし、SOPのOFFを公式のOnly Source Seedingと同義とは断定しない。

図の再計算環境はPython3.13.2、Matplotlib3.11.2、Windows Meiryo。依存は[21と同じlock](../../../WaveBaseline21/Source/requirements.lock.txt)を使い、フォントSHAと版は各再計算manifestに記録した。配布JSON/gzipだけを用いる手順は結果READMEとStep22に記載する。
