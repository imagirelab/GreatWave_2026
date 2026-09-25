# 22修正06：同じ粒子キャッシュに対する面化解像度の感度試験案

**未実行・審査候補。現在は公開JSON、既存ファイルのSHA、純関数・mockだけを確認した。Houdini/MCPへ接続しておらず、新しい面も流体計算も作っていない。stage・commit・pushは行わない。**

唯一の物理入力は[04のrun 22e7801642](../WaveStart04/Evidence/Result_22e7801642/README_ja.md)が保存した `pilot_*.bgeo.sc` である。[05の局所断面診断](../PfsDiagnosis05/Evidence/Result_22e7801642/README_ja.md)では、中央first-hitの誤選択や1/10µm容差の差は検出されなかった。一方、PFSとsolver符号場の高さ差は時空間で一定でなく、原G3 PFS谷候補は左側prominence 0.827461 mmがq=1 mmを満たさなかった。これだけで減幅の原因を確定できない。

06は原粒子を面化する `particlefluidsurface::3.0` の `voxelsize` だけを `.5→.25` に変える候補である。`particlesep=.04m` と全ての他の明示設定・既定値を揃え、原位相・時間窓・detectorを変えない。固定10mmオフセットは加えない。SOPの値はVoxel Scaleであり絶対長ではない。期待する面化セル長は `.02→.01m` だが、圧力格子や粒子分解能は変わらない。ポリゴン出力のため内部VDBの実セル長は本先導で測定済みと記さず、現物parm・定義と期待積を区別する。

## 固定入力と唯一の変更

| 項目 | 固定内容 |
|---|---|
| 元記録 | 04 run `22e7801642`、commit `d3be3eb205f6e3ff91c215806bb85df84976cac6` |
| 直前の公開点 | 05 commit `76fabdf8ce09ee7b4ad3f531e61cdda8dba51116` |
| 物理状態 | 既存BGEOのみ。L=6m、dp=.04m、APIC等の流体設定を再評価・変更しない |
| 入力構成 | File→Null→PFS→Convert(poly)→Null。元と同じ粒子・field・保持点を含む全geometry |
| PFS固定 | `surfmethod=particlefluid`, adaptivity/dilate/smooth/erode/final-smooth/closed-container/closed-ends/flatten全0 |
| 唯一の変更 | `voxelsize .5→.25`。全評価parmの他の差や定義SHA差があればHOLD |
| 時刻 | 元04 JSONのabsolute global frame（理論値 `1+(k/60)*24`）、FPS24。Manualで所有SOPだけcook |
| 中央測点 | x=2.242796380 / 2.990395173 / 3.737993967m、z=0。21のfull測点とは別の短槽pilot |
| 近傍断面 | 各中央x±.12mを.02m間隔、z=−.12/−.06/0/.06/.12m。195縦線/面 |

元ソースが記録したのは明示parmであり、全HDA既定値を歴史的に固定した証拠ではない。現HDAの全評価parm・library/sections SHAを保存し、まず旧出力の厳密再現でこの不確かさを検査する。入力の実粒子ID/P/v/pscale、全点P、Volume値/transform/voxelを直接BGEOとFile SOPで照合する。保持点は粒子数から除外するが、入力geometryから削除しない。

## 3フレーム先導の反証可能な順序

| k / 時刻 | 事前に選んだ理由 | 元pilot / 元mesh bytes |
|---|---|---:|
| 360 / 6.000000s | 駆動開始境界・静水後端 | 4,313,913 / 873,004 |
| 474 / 7.900000s | 原G3候補の左側参考時刻 | 4,269,688 / 870,685 |
| 496 / 8.266667s | 原G3 PFSの未採用谷候補の時刻 | 4,258,982 / 860,227 |

先導6入力の合計は15,446,499 bytes。ファイルSHA/bytesは[計画JSON](Source/pfs06_plan.json)に固定した。`k474`の1個のraw値は5点平滑の左参考値ではなく、`k496`が新面でも谷になるとは仮定しない。

1. **旧`.5`を3フレームすべて先に生成する。** 原meshの全P配列、各面の順序付き点indices、primitive型/closedフラグを厳密比較する。点や面の並替えによる救済はしない。三測点のnative first-hit（元と同じy=.4、下向き、既定引数）のprimitive/位置/法線/uvwも直接旧meshと厳密比較し、元公開測点値にも1µm以内で対応する。新保存BGEOのbytesそのものは一致を求めず、内容と独立SHAを記録する。
2. どれか1フレームでも旧`.5`配対が不成立なら、生成済み面と観測JSONを保存してHOLD。残りや`.25`を作らない。原入力から再現できない状態でvoxel変更の効果とは結論しない。
3. 3フレームがすべて合えば同じ順の`.25`を3フレーム生成する。同じ実HDAと全parmを記録し、評価値の差はvoxelsizeだけであることを確認する。異なる時刻や源に差替えない。
4. `.25`の高さ差は結果そのものであり、1mm未満であることなどを新たな合格条件にしない。原中央parity用フィールドを借りた `center_mesh_error_m` は候補−原`.5`の差であり、候補の `center_parity_passed=false` だけでは失敗ではない。原solver符号場値の読戻しは引き続き厳密に合わせる。
5. 有限/field内/保存読戻し/資源/query整合を判定する。旧と交点数が変わる、上面normalが反転する、符号場が曖昧になる場合は形状審査HOLDとする。これは面化結果の観測で、solver失敗と同義ではない。

3フレームではq・prominence・onset・唯一鎖を計算しない。高さ、候補−原面差、面数、交点/断面と実費用のみを返す。6面×195=1,170断面を上限とする。

## 交点と無効データ

05で検査済みの[純関数](../PfsDiagnosis05/Source/profile_core.py)と[HOM reader](../PfsDiagnosis05/Source/read_profile05.py)をSHA固定で参照する。原native first-hitと、1µm tolerance / 2µm advance・10µm tolerance / 20µm advanceの多交点を別々に保存する。primitive番号0は有効、−1のみmiss。rayはy=.4から−.7、最大64個の異なる高さ。XZ候補を最大tolerance分拡張し、面限定queryの未統合face/頂点/法線を残す。

主query→同primitive/高さ、逆方向は各面の高さ→主queryを照合する。同じ面のdefault first-hitとstrict先頭の高さ差>1µmまたは法線方向の不一致も保留する。共有辺のprimitive番号は異なってよいが、default自体のprimitive/高さを面限定queryで裏付ける。共有辺の別primitiveを誤って「別水面」にしないが、別の重なった面を勝手に融合しない。主・感度queryの個数差/高さ差>1µmやquery同士の不一致は原値を保存してHOLD。上下二交点は表示水塊の上面/下底であり、二層の自由水面とは呼ばない。

符号場の局所縦線は底−.5999mから `min(.25,field_hi−.01)`。非有限・範囲外は停止、零台地/接触/複数交差は曖昧として単値図に使わない。欠測を0、前値、旧PFS、solver高さで補わない。native読戻しの前に生成BGEOを保存してSHA/容量/内容読戻しを確認する。05 reader中途の例外では生成済みBGEOとstage失敗JSONを残せるだけで、195断面の途中までの行が保存される保証はない。表面の一価性・全域連通・水量や無空洞の証明にはしない。

## 別審査が必要な142フレーム拡張

**現在のrunnerには拡張実行入口がない。** 先導が通った後もrootが結果/費用/コードを再審査する。拡張の固定範囲は偶数k272..554の142枚、先導3枚の`.25`を含む。残139枚は索引順で作る。結果を見て時刻や終点を選び直さない。

全556行の原solver時刻・測点ηを保持し、k<272および新PFSを持たない行のmesh_sampledはfalse。detector専用の派生入力では旧mesh SHA/点面数を消し、新しい高さに旧面の出典を誤結合しない。原JSONは不変で、新面manifestと派生入力SHAは拡張時に別々に記録する。新面から(4.5,5.25]の22標本、(5.25,6]の23標本を測り、`q=max(.001m,3*max(RMS1,RMS2),max|η−μ2|)`を**その観測自身の**値で計算する。原`.5`のq=1mmを候補へ強制移植しない。床が1mmの同じ公式を使い、固定10mmの補正をしない。

主窓は元[6,9.25]、30Hz PFSは98標本/末9.233333、solverは60Hz/末9.25のまま。5点対称平均、完全±.375s支持、同符号open lag(2/60,.75)s、全候補の一意鎖という原関数/設定を変えない。60Hzと30Hzの5点窓の時間幅は異なる。欠落フレーム・無効測点は全体をHOLDし、途中までの列で再判定しない。候補の鎖が現れても短窓の**面化感度**に限り、物理分解能・精度改善/収束・減幅の唯一原因を証明しない。

142入力のpilotは609,012,664 bytes、対応原meshは123,414,638 bytes（公開manifest合計）。未読込み面の計算費用・出力容量は未測定である。

## 資源・停止・UI

| 項目 | 事前固定した値と動作 |
|---|---|
| メモリ | GlobalMemoryStatusExで可用RAM≥8GiB。GetProcessMemoryInfoで初期privateからの増分<12GiB。privateはVRAMではない |
| cook時間 | 1面<30s。直近30面の中央値<15s、残り時間の推定<90分。先導では6cook以下 |
| 1 RPC / 待機 | 協調予算90s、client待機180s、先導累積540s。native cook中に強制監視・中断できる保証はない |
| 面ファイル | 新面1枚≤16MiB。142枚＋補助64MiB=2,449,473,536 bytesを予約 |
| G空き | 開始≥15,636,365,312 bytes（予約2倍＋10GiB）、実行中≥10GiB |
| 補助容量 | 64MiB内に旧`.5`三面・JSON・凍結実行元を含む。新`.25`は別枠 |
| 操作 | metadata再確認→UI18保存→Manual→同じabsolute frame→所有SOPだけcook→finally所有物削除/元UI復元 |
| 未許可 | FPS変更、既存HIP保存/読込/clear、旧DOP再cook、新solver、元BGEO上書き、先導中flipbook |

各cookの前後と読戻しの節目で資源を保存する。native cookの途中peak privateを連続計測したとは記さない。時間超過は戻ってから停止・保存・復元し、次RPCを開始しない。RPC完了不明なら追加cleanup・再要求・killを行わずrootへ報告する。HOM/API不一致、資源不足、missing/hash違い、警告/エラーも停止する。

RAMや時間が必ず8倍、面数が必ず4倍になるとは仮定しない。3フレームで実費用を測ってから拡張予算を判断する。判定値や幾何を見て予算を緩めて継続しない。

## 審査用ファイルと再検査

- [機械可読の固定候補](Source/pfs06_plan.json)
- [順序・配対・予算・応答入力の純関数](Source/sensitivity_core.py)
- [所有面化のHOM候補](Source/remesh_pilot06.py)
- [3フレームだけのrunner候補](Source/run_pilot06.py)
- [離線検査](Source/check_pilot06.py)／[検査報告](Evidence/22_pfs06_offline_checks.json)
- [審査候補のSHA一覧](Evidence/22_pfs06_candidate_freeze.json)

Freshルートから次を実行してもHoudiniへ接続しない。既定checkは報告を変更せず一致を検証する。証拠更新は明示の `--update-evidence` のみ。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06/Source/check_pilot06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06/Source/run_pilot06.py
```

実面化はrootの別放行後だけ、次の候補コマンドを使う。**現在は未許可。** 先導が成功しても拡張は自動開始しない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06/Source/run_pilot06.py --execute-reviewed-three-frame-pilot
```

実結果が得られたら、原高さ・差・断面の可読な静止図と全条件/源SHAを06の証拠にする。3フレーム先導では動画や波検出を捏造しない。元04動画を参照する場合は新面化の描画映像と区別する。[21のfull測点](../../../WaveBaseline21/README_ja.md)による非砕波連続伝播と実媒体は22の残件、理論精度は23、収束は24、収支/反射定量は25、HMDは未検証のままである。

公式出典：[PFSのVoxel ScaleとParticle Separation](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)、[Geometryの交点と読戻し](https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html)、[SOP cook](https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html)。公式PFSページの見出しは2.0であり、実際の3.0 node schemaは許可後に照合する。Final Smooth等の一般説明を、このrunで無効なfilterが原因だった証拠に置き換えない。
