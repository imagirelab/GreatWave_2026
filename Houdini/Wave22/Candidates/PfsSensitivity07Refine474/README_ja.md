# 22修正07：k474・新.25面の単一感度候補

**実行前に固定する計画。現時点ではHoudini/MCP未実行。** 利用者の最新の継続指示に基づき、rootが候補・離線結果を独立審査し、明示RUNを出した後だけ実行する。06の当時の確認待ち文言は履歴として変更しない。本候補はk474だけであり、他時刻・142面拡張・新solver・波検出を開始しない。

[修正06の実結果](../../Evidence/Revision06/README_ja.md)で旧`.5`のk360/k474/k496再現と新`.25`のk360を確認した。今回は**動いている試料のt7.9一面**を対象とするが、新たな時間発展を計算するものではない。面化差や局所queryが通っても、22の非砕波連続伝播/full測点/媒体、23精度、25収支/反射、主役波・HMDの合格へ拡張しない。

## 固定する入力と設定

唯一の物理入力は修正04 Run `22e7801642` の `pilot_474.bgeo.sc`。旧試作を参照しない。[計画JSON](Source/refine_plan.json)で原SHA、全条件、成功した旧`.5`の原記録、05の原195断面を固定する。

| 対象 | 固定値 |
| --- | --- |
| sample / 時刻 | k474 / 絶対7.9秒 |
| global frame / FPS | `1+0.4*474` = 190.60000000000002 / 24 |
| pilot | 4,269,688 bytes、SHA `48177e8fa0343a87a75c4f60ebdb0153adbdd793c252aca7a2a07da65565c40a` |
| 入力全幾何 | 53,838点、5 Volume、実粒子53,833。Volume保持点も含む原幾何を渡す |
| 原`.5` mesh | 870,685 bytes、SHA `116cf67f5decdf35a0a73503c17fed32d93b6972748fc3dadb5052e65e8277c3` |
| 原mesh点 / 面 | 39,078 / 39,076 |
| PFS / Convert | `particlefluidsurface::3.0` / Convert `poly` |
| 変更 | 実評価166 PFS parmのうち `voxelsize` **.5→.25だけ** |

原04式 `1+(474/60)*24` は今回式と同じ倍精度値。原保存JSONのframe190.6およびHOM戻り値の丸めを分け、frame誤差は1e−8未満で照合する。全体FPSは変更しない。

Particle Separation=.04m、surfmethod=`particlefluid`、adaptivity/dilate/smooth/erode/final smooth/closed container/closed ends/flattenは全0を維持する。HDA libraryと全sectionの原binary bytes、Convert全評価parm、全PFS parm集合を成功したk474旧`.5`と照合する。メニューはint-indexとstring-tokenを区別する。定義や派生parmに追加差があればHOLDし、黙認しない。

[SideFX公式のVoxel Scale説明](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)はParticle Separationの乗数を意味する。指定から期待する表示面voxelは.04×.25=.01m。**FLIP solverの粒距や圧力格子を細分化する試験ではない。** 公式ページ題名は2.0だが、実行時は本機3.0のHDA/166項目を検査する。[HDA binaryContents](https://www.sidefx.com/docs/houdini/hom/hou/HDASection.html)を用い、文字列化で原bytesを損なわない。

## 進行を許す順序

1. 開始前に全凍結ファイル集合・bytes/SHA、元cache、公開05 gzipと展開SHA、G空きを検査する。metadataで現在のPID・22.0.429・Indie・UI・FPS24を確認する。過去PIDは現在値として流用しない。
2. UI18を保存し、Manualで非表示の所有subnet/geoを作る。frameを固定する。第1Auto窓はFile→Nullだけをcook/freezeし、必ずManualへ戻す。Direct/File/Nullの全幾何署名を成功k474と比べ、許す差は一意nameで対応させたdetail属性一覧の列挙順だけ。全属性値/ID/P/v/pscale/field格点・全voxelは厳密一致。入力不一致ならPFSを作成・cookしない。
3. 入力PASS後だけPFS→Convert→Outを作り、HDA/全評価parmを照合する。第2Auto窓は原04と同じOutだけforce cook/freezeし、finally Manual。新meshを**native照会より前**に保存し、bytes/SHA、P/有向面indices/primitive型/closed/有限の保存再読一致を記録する。旧面を再保存する必要も、新旧meshのP・接続一致を要求する必要もない。
4. 元旧面fingerprint・native3点は成功k474と厳密一致、新3点は有限/存在を確認する。旧・新・solverの原水位と新−旧を保存する。固定10mmの補正はしない。所有ノード削除とUI18復元が明らかに通るまで断面RPCを始めない。
5. 次の読取専用RPCで原`.5`の195断面を読み、公開05 k474と後述の厳密配対を行う。FAILなら新読戻しを開始しない。旧PASS後にだけ、別RPCで新`.25`の同じ195断面を読む。`hou.Geometry.loadFromFile`だけでノード/時刻/HIPを書き換えない。

06とbyte同一のAuto helperには第2窓名`OLD_HALF_PFS`が残る。これは履歴識別子であり、実scopeと要求/実評価`.25`を設定の根拠にする。owner/geoは非表示、outはdisplay/render=true。全体Auto窓には無関係networkの潜在的cookリスクがある。外部DOPへ直接呼び出さないが、その内部状態は監視せず全無影響とは認定しない。

HIP保存/読込/clear、undo履歴削除、新solverは禁止。UI18にdirty flagの復元は含まれない。06では所有物作成・削除後にdirty false→trueとなったため、今回も前後の実値を報告する。読取専用RPCはframe/FPS/update mode/dirtyの前後一致を要求する。

## 05原断面と390断面の検査

公開05の `profiles_474.json.gz` は427,646 bytes、展開3,681,460 bytes。圧縮SHA `f1d3b0f8e7978e3c3ab799c25558123d03cc1f1a02e3d3f7aa6a7b41d58aef24`、原SHA `9293fc5ab1f3d5995d11f9a08170793fb31fb3959e8a75c74acad83c56e38dde`。読戻しreader二本は公開05とbyte同一である。

旧面の比較は15項目を抽出し、型も含めた全値一致を要求する。195行`profiles`全体、場/格点、P指紋、原cache SHA、近傍差、中央判定を含む。最上位の時間・資源・説明・UI/source/plan metadataだけ比較外とする。**行内の補足文字列も15項目に含まれ、除外していない。** 投影2,174,342 bytes、SHA `2841b0f5d79b7f9e0d0d5896cd8885f458619ea4c543ae9fbe4ed5efcd157344`。この旧対05の一致と、新対旧の形状判定を混同しない。

solver観測は二つの定義を保存し、互いに置換しない。

| 測点 | 元04・121標本/25二分の水位 m | 05局所断面の水位 m | 原`.5` native m |
| --- | ---: | ---: | ---: |
| G1 | −.004264756841695326 | −.004264831542968740 | −.013093209266662575 |
| G2 | −.003595844023928607 | −.003595886230468739 | −.009756213426589944 |
| G3 | −.002307101953183235 | −.002306823730468739 | −.011981582641601540 |

原04の中央測点値への照合誤差≤1e−8m、旧面中央への誤差≤1µmを保持する。公開05旧面の再読は上表を含め全値厳密一致であり、これより強い別の再現条件である。

3測点×x近傍13点（±.12m、.02m刻み）×z近傍5点（±.12m、.06m刻み）=各195位置。旧新とも長さ195、一意な座標順、同じsolver field値を確認する。主tolerance1µm/前進2µm、感度10µm/20µm、ray y=.4→−.7、最大64交点を固定する。primitive0は有効。

- 同一面のdefault/strict first高さ差>1µm、法線向き差、面限定queryと双方向不一致、二容差の交点数/高さ差はquery HOLD。共有辺ではprimitive番号同一を必須にせず、各面の原primitiveを同じ面の限定queryで裏付ける。
- 場のwet→dryが単一でない、零平台/接線で曖昧、欠落交点、旧新の上下交点数変化、上側法線Y方向反転は形状HOLD。下底交点を第2自由面と呼ばない。旧新primitive ID・法線ベクトル自体の同一は要求しない。
- 新`center_parity_passed=false`は旧面からの差だけなら許容する。全旧中心はtrueを要求する。差を消す高さ補正やq=1mm/検出規則の変更はしない。detector/唯一鎖はこの一面から判定しない。
- `surface` Volumeは原metadata isSDF=falseの符号場として扱う。小さい照会刻み/細かい表示mesh、quad二分割の数値感度は物理精度・投影凸性・減幅の単一原因の証明ではない。

## 予算・HOLD・原記録

| 保護 | 固定値 |
| --- | --- |
| G開始空き / 実行中空き | ≥15,636,365,312 bytes / ≥10GiB |
| 可用RAM / private起点比 | ≥8GiB / <12GiB |
| Auto窓 / 各業務RPC / client待機 | <30秒 / 90秒協調 / 180秒 |
| 新mesh / 各profile / 主JSON | 各≤16MiB |
| Run総出力 / profile記帳予約 | ≤64MiB / 64KiB |

06のk360新`.25`は面化RPC17.635秒、Auto2=7.250秒、旧/新195読戻し2.271/10.993秒、新mesh3,494,161bytesだった。k474の費用は未測定で、前回の値は今回の上限保証でも性能比較でもない。3業務RPCの公称270秒はHOM強制中断保証ではない。全て呼出しが戻った後の協調停止であり、時間中のkillはしない。

開始G門はRun作成/MCP接続前と面化最初の健康点で確認する。実行中はManual節目・各読戻し前後、reader内で各縦線前のRAM/時間を確認する。private/ディスクの連続ピーク監視ではなく、process値をVRAMと呼ばない。

面の容量/finite/HDA/入力/query等のFAILは保存してHOLDし、閾値を緩めない。完全profileはserialize後・書込前に単体/総残量を検査する。容量超過なら原bytes/SHAだけの小摘要、摘要も置けなければ書込なしACKをexecutionへ残す。途中例外は部分195行の保存を保証しないが、生成BGEO・完成JSON・失敗段階を保持する。NaNを0や前値に置換しない。

通信完了不明時は後続RPC/retry/kill/並行cleanup禁止。面化不明なら自動UI復元も追要求しない。断面不明ならUI18は既に完了しているが新読戻しへ進まない。HOLDを流体solver失敗や物理不合格へ読み替えない。

## 凍結・離線検査・入口

[保護manifest](Evidence/22_prior_attempts_manifest.json)は旧候補/原Run/Revision06/関連文書の266ファイル、19,042,592bytesを固定する。ディレクトリ集合も比較するため、凍結候補へResultを追加しない。今回の結果は将来の別 `Evidence/Revision07/` へ整理する。今回新Runは`pfsrefine07_<token>`、元cache/旧Runを上書きしない。

既定checkは実HOM/MCPなし、既存証拠を変更しない。偽通信によるUI失敗・非有限・old/new HOLD・完了不明・容量不足に加え、誤時刻/FPS/原cache/gzip改ざん/05全断面差/開始G不足を注入して停止を確認する。mockは実HOMの保証ではない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity07Refine474/Source/check_refine07.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity07Refine474/Source/run_refine07.py
```

[離線報告](Evidence/22_refine_offline_checks.json)と[freeze](Evidence/22_refine_candidate_freeze.json)をrootへ渡す。既定runnerは固定scopeを表示するだけで接続しない。明示RUN後だけ次を使用する。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity07Refine474/Source/run_refine07.py --execute-reviewed-k474-quarter-mesh
```

実結果が得られた後に原JSON/SHA、旧新195剖面、原高さと差の科学図、資源/UI/dirty/不明通信の記録を別公開先へ対応させる。現在はstage/commit/pushを行わない。
