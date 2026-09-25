# 22修正08：k496・新.25面の単一感度候補

**実行前の凍結候補。Houdini/MCP未実行。** 基線commitは`3c30afac96772a586ff3f24a0ccd6230542f3f3f`。root・独立担当の審査と明示した単回RUNが出るまで接続しない。今回の準備では既存候補・原Run・進捗文書を変更せず、stage/commit/pushもしない。

[修正07の実結果](../../Evidence/Revision07/README_ja.md)で確認した二つの短いAuto窓と旧新195断面読戻しを技術的な基礎とする。ただし今回の入力・旧成功面・05原断面は**k496だけを新たに固定**する。新solver・駆動・detector/q/唯一鎖・142面拡張は実行しない。元のG3谷候補時刻に当たっても、一面の結果から元の不採用や伝播判定を変更しない。

## 固定入力と一つの変更

唯一の物理入力は修正04 Run `22e7801642` の保存`pilot_496.bgeo.sc`。旧試作は参照しない。[計画JSON](Source/refine_plan.json)が原cache、成功k496旧`.5`、公開05断面と全設定をSHAで結ぶ。

| 項目 | 固定値 |
| --- | --- |
| sample / 絶対時刻 | k496 / 496÷60 = 8.266666666666667秒 |
| 要求global frame / FPS | `1+0.4*496` = 199.4 / 24 |
| pilot | 4,258,982bytes、SHA `6d14a40ab3d1839c478822fd32536612cc47e84ffef45c818013389337ac7a31` |
| 入力全幾何 | 53,853点、5 Volume、保持点5を除く実粒子53,848 |
| 原旧`.5` mesh | 860,227bytes、SHA `afb4a747b92f6f74472012a3249cd6db1ae9f79e04d1d1abdcb7da3c460def19` |
| 原旧面点 / 面 | 38,912 / 38,910 |
| PFS / Convert | `particlefluidsurface::3.0` / `poly` |
| 変更する実評価パラメータ | 166項のうちvoxelsize **.5→.25だけ** |

原04式`1+(496/60)*24`の倍精度値は199.40000000000003であり、今回式との差は2.842170943040401e−14 frame。原JSONと旧成功HOM実測は199.4。式同士のbit一致とは書かず、差を保存して固定許容1e−8 frame未満で照合する。FPS全体を変更しない。

Particle Separation=.04m、surfmethod=`particlefluid`、adaptivity/dilate/smooth/erode/final smooth/closed container/closed ends/flatten全0を維持する。HDA libraryと全sectionのbinary bytes、Convert全評価値、PFS全評価166項の集合を旧k496成功記録と照合し、voxel以外の相違はHOLD。[SideFX Voxel Scale](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)の乗数の意味から指定表示面voxelは.02→.01mとなるが、**FLIP solverの粒距・圧力格子の細分化ではない**。公式ページ題名と実3.0を混同せず、[binaryContents](https://www.sidefx.com/docs/houdini/hom/hou/HDASection.html)で実HDAを調べる。

旧`.5`の成功原Runは`pfsreplay06_b13cd6bcb8`。原結果JSONのSHAは`2dfc69416695a778c60ea8f326f72487a32b60c1075a8620d69096604bcd4f34`。原04に対するordered P・有向面indices・型/closed・native3点・保存再読の一致が既に確認されているが、今回も旧面指紋とnativeを再確認する。再保存BGEO全bytesの一致を仮定しない。

## 実行を許す順序

1. 既定runnerはscope表示だけ。明示入口でも全凍結集合/bytes/SHA、基線commit、元cache、05 gzip/展開SHA、開始G空きを接続前に検査する。metadataは現在のPID/version22.0.429/Indie/UI/FPS24を再確認し、旧PIDを流用しない。
2. UI18を保存し、Manualのまま非表示所有subnet/geoとFile→Nullだけを作る。絶対frameを固定し、同じmain-thread RPCのAuto窓1でFile/Nullをcook/freeze、finally Manualに戻す。Direct/File/Null全幾何署名は旧成功k496と同一を要求する。一意nameによるdetail一覧順だけを許し、ID/P/v/pscale、全属性値、field格点/全voxel等は厳密一致。不一致ならPFSを作らない。
3. 入力PASS後にだけPFS→Convert→Outを作る。owner/geoは非表示、out display/render=true。全定義/設定の比較後、Auto窓2で原04同様Outだけをforce cook/freezeし、finally Manual。PFS/Convert/OutのcookCount・errors/warningsは観測する。
4. 新面はnative query前にBGEO保存し、容量/SHAと保存再読のP/有向面/型/closed/有限性を確認する。旧native3点は原成功と厳密一致、新native3点は有限・存在を要求する。旧/新の生高さとsolverとの差を保存し、固定10mm補正はしない。新旧meshのP/接続一致は要求しない。
5. 所有ノード削除とUI18復元PASSの後だけ、別の只読RPCで旧195断面を採り公開05と厳密照合する。旧FAILなら停止。旧PASS後に別RPCで新195断面を採る。`hou.Geometry.loadFromFile`だけでノード/時刻/HIPを変更しない。

二窓helperの原ラベル`OLD_HALF_PFS`は履歴識別子として残す。設定の根拠は今回scopeと実評価`.25`である。Auto窓に伴う無関係networkの潜在的cookリスクは残り、外部DOPを直接呼ばなくても全外部状態の無影響を認定しない。HIP保存/読込/clear、undo消去は禁止。dirtyはUI18復元に含めず前後の実値を報告する。読戻しRPCではframe/FPS/mode/dirtyの前後一致を要求する。

## 原05配対・二つのsolver定義・195断面

公開05 `profiles_496.json.gz`は428,189bytes、SHA `db5eded39edf86ba520620e35031bb37e532295f800f957465e6db472d29c2ea`。展開3,680,857bytes、SHA `c79705783bc27a1355ca931149f4be4edb85e24ee2da42cea8ad205a675e8374`。reader二本は05/07とbyte同一。

旧再読は科学15項目の型を含む全値一致を要求する。全profiles/field/幾何指紋/元SHA/近傍差/中央判定を含み、**その内部のmeaning_jaも厳密比較**する。指定した最上位時間・資源・説明・UI/source/plan metadataだけ比較外とする。投影2,173,739bytes、SHA `72de5801d21eaef364975382960b64f45317db6954044b3c6457b54c29022892`。新面には旧profileの全値一致を要求しない。

| 測点 | 原04・121標本/25二分の水位 m | 05局所断面の水位 m | 原`.5` native m |
| --- | ---: | ---: | ---: |
| G1 | +.001284524680028517 | +.0012844848632812512 | −.008780008554458596 |
| G2 | −.003211513270562148 | −.003211364746093739 | −.009167498350143410 |
| G3 | −.0041132123782449525 | −.004113464355468740 | −.012830650806426980 |

二つのsolver値は別定義で保存し、互いに置換しない。原04定義への誤差≤1e−8m、旧面中央への誤差≤1µmを維持する。旧05全断面の再現は、これとは別に全値厳密一致を求める。

G1〜G3×X近傍13（±.12m/.02m刻み）×Z近傍5（±.12m/.06m刻み）＝各195位置。長さ195・一意な順序付き座標・同じfield値を要求する。主tolerance1µm/前進2µm、感度10µm/20µm、ray y=.4→−.7、最大64交点を固定する。primitive0も有効。欠落、非有限、曖昧なfield交差、主/感度/面限定queryの不一致、上下交点数の旧新差、上側法線Y反転はHOLD。

同じ面のdefault/strict高さは1µm以内かつ法線方向整合を要求し、default原primitiveは同面のincidenceで裏付ける。共有辺を考慮してdefault/strict ID同一は必須にせず、旧新面のprimitive IDや法線ベクトル自体の同一も求めない。新center_parity_passed=falseが旧面との差だけなら診断値で、全旧中心はtrueを要求する。下底交点を第2自由面と呼ばない。isSDF metadata=falseのsurfaceを符号場として読み、全域連通・未標本化薄層・時刻間状態・非砕波を証明しない。

## 資源・HOLD・保存

| 固定保護 | 門 |
| --- | --- |
| G開始 / 実行中空き | ≥15,636,365,312bytes / ≥10GiB |
| 可用RAM / private起点比 | ≥8GiB / <12GiB |
| Auto窓 / 各業務RPC / client待機 | <30秒 / 90秒協調 / 180秒 |
| 新mesh / 各profile / 主JSON | 各≤16MiB |
| 全Run / profile記帳予約 | ≤64MiB / 64KiB |

07 k474の実測は面化RPC20.837554秒/Auto2=8.096435秒、旧新profile2.959956/10.814633秒、新mesh3,497,363bytes。k496新`.25`の費用は未測定で、前回値を上限保証や方式性能比較にはしない。最大3業務RPCの公称270秒も強制中断保証ではない。

RAM/時間は各縦線前にも検査するが、HOM単一呼出しを強制中断しない。private/G空きはManual節目とprofile前後の観測で連続ピーク/VRAMではない。完全profileのserialize後に単体/総残量を検査してから書き、容量HOLDは小摘要を残す。摘要の余裕も無ければ書込なしACKをexecutionへ保存する。途中例外でpartial195の保存は保証せず、生成済みBGEO・完了JSON・失敗段階を保持する。

HOLD時に閾値や時刻を変更しない。通信完了不明は後続RPC/retry/kill/並行cleanupを禁止し、面化不明なら自動UI復元の追要求もしない。只読profile不明時はUI18が先に済んでいるが、次の読戻しを始めない。これらは物理solverの不合格判定とは別の実行/数値診断保留である。

## 凍結と入口

[旧資料manifest](Evidence/22_prior_attempts_manifest.json)は333ファイル/32,172,303bytesを保護する。全先行候補・Run・Revision06/07・現況文書の集合とbytesを変更しない。新結果は将来の別`Evidence/Revision08/`に整理し、凍結候補の中へ追記しない。

[離線報告](Evidence/22_refine_offline_checks.json)は偽通信による入力/面/profile HOLD、非有限、UI復元失敗、原JSON/SHA、資源不足、完了不明後の呼出し禁止、二窓finally Manual、195queryと旧05厳密配対を検査する。08専用の誤k474/原二分値置換/実166項追加変更/登録資源値変更も拒否する。結合RPC sourceをローカルmodule禁止と隔離`python -I`で検査する。mockはHOM実成功を保証しない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity08Refine496/Source/check_refine08.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity08Refine496/Source/run_refine08.py
```

既定checkは証拠を更新せず、runnerは表示だけ。[freeze](Evidence/22_refine_candidate_freeze.json)を審査した後に、rootの明示した単回RUNでのみ次を使う。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity08Refine496/Source/run_refine08.py --execute-reviewed-k496-quarter-mesh
```

実結果が得られた場合は原JSON/旧新195断面/SHA、未補正の高さ差の図・CSV、資源/UI/dirtyを公開候補へ結ぶ。**22完成ではない。** 21のfull測点2/2.2/2.55λと短槽pilot .75/1/1.25λを区別し、非砕波連続伝播/実媒体、23理論精度、25収支/反射、主役波・HMDをこの単一面で合格にしない。
