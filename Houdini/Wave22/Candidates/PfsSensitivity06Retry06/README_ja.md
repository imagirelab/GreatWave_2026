# 22修正06・Retry06：k360旧.5面化の再現候補

**未実行。** rootによる候補審査と明示RUNまでHoudini/MCPを呼ばない。今回の実装は、原04 `22e7801642` の保存粒子を使い、**k360・voxel scale .5の面を一回だけ**再現する候補である。.25、k474/k496、142面拡張、新しいsolver、波検出、動画採録は実装の実行対象に含めない。成功しても22の波伝播完成にはならない。


## Replay05の実保留と唯一の修正

前回 `pfsreplay06_55fa260d7f` は入力のFile/Null署名が意味上完全一致し、Auto窓1は0.0048919秒でManualへ復帰した。11設定とOut表示旗まで記録したが、Manual中の `definition06` でHDA sectionの文字列をUTF-8へ符号化する際に `UnicodeEncodeError` が発生した。Auto窓2は未開始でmeshは存在せず、PFS配対FAILと取り違えない。6.9606698秒で停止し、UI18/所有cleanupは全て成立、完了不明なし。

[前回原記録の読取照合](Evidence/22_previous_run_review.json)にraw SHA、入力・例外位置・復元・資源を結ぶ。元Runも前freezeも書き換えない。

今回変える実行関数は `definition06` のsection bytes取得だけである。SideFX 22.0の[公式HDASection](https://www.sidefx.com/docs/houdini/hom/hou/HDASection.html)に従い、`binaryContents()` が返すPython3の原 `bytes` をそのままSHA-256へ渡す。引数なしの既定NoCompressionを用い、文字decode/encode、置換、surrogateescape、section省略を行わない。bytes以外は拒否する。section名で整列した全SHAとHDAライブラリファイルSHAを従来どおり保存する。

実行runner、二窓の分岐と復帰、File/Null完全署名、mesh/三測点native配対、11設定、予算はReplay05から変更しない。helper内の他の関数も完全同一である。離線試験では全256byte値・NUL・非UTF-8・圧縮データ風bytes・空sectionを使い、`contents()`を呼ぶ実装なら失敗するmockで原bytes SHAを照合する。旧APIの文字列では実際と同じsurrogate符号化例外を再現する。

## 既存記録を保護する

Retry03 の原 `passed=false` / HOLD は変更しない。[Decision04](../PfsSensitivity06Decision04/README_ja.md)は入力署名のdetail属性一覧順だけを名前対応にした別の離線解釈であり、PFSの再現を証明していない。

[保護一覧](Evidence/22_prior_attempts_manifest.json)で前6候補・前5Runの**110ファイル、2,468,510 bytes**を集合・容量・SHAで固定する。実行入口は今回のfreeze、自身の全source、離線検査、Decision04、以前のファイル集合とbytes/SHAを確認した後にだけMCPをimportする。元04の基準資料7件と今回の二つのBGEOも照合する。

| 入力 | bytes | 役割 |
|---|---:|---|
| `pilot_360.bgeo.sc` | 4,313,913 | 唯一の物理入力。53,806粒子とVolume保持5点、計53,811点/5 Volume |
| `mesh_360.bgeo.sc` | 873,004 | 原04の比較面。38,926点/38,924面 |

SHAと原3測点の値は[固定計画](Source/replay_plan.json)に収録する。二ファイルは合計5,186,917 bytes。ファイル自体はG盤の既存Runにあり、読み取り専用とする。既存HIPの保存・読込・clear、FPS変更はしない。

## 同一RPC内の二つの短いAuto窓

実行時にPID、UI、Indie、Houdini 22.0.429、FPS24を新たに確認する。UI18を保存してManualへ置き、所有subnetとgeoは非表示にする。原04と同じ**絶対frame145、秒6.0**を使う。

1. Manualで原BGEOを `hou.Geometry.loadFromFile` し、Directの全署名を保存する。所有File→Nullだけを作り、Fileに入力が無いこと、literal絶対パス、load関連の実schema/evalを記録する。
2. **Auto窓1**ではFileとNullを明示cookし、geometryをfreezeする。前後cookCount/errors/warningsを記録する。main-thread内の `try/finally` で必ずManualへ戻し、待機・別RPC・UI描画・全属性hash・JSON出力を挟まない。
3. ManualでDirectとFile、DirectとNullを完全比較する。許す違いは**入力の `attribute_inventory.detail` の一意nameによる列挙順だけ**。他のキー・型・属性値SHA・配列順・粒子/場/点P/有向接続/groupは厳密一致を必要とする。空入力、警告、cookCount増加なしも保留する。ここが不成立なら**PFSノードを作らず第二窓へ入らない**。
4. 入力PASS後にだけManualでNull→PFS3.0→Convert poly→Outを作る。全11明示設定を原04から固定し、実Menu型/token、全評価parm、HDA定義SHAを記録する。所有Outのdisplay/renderをtrueにし、geo/ownerは非表示のまま記録する。
5. **Auto窓2**は原04と同じく **Outだけ `cook(force=True)`** を呼び、Out geometryをfreezeする。PFS/Convert/Outの実前後cookCount/errors/warningsを観測し、個別の強制cookは追加しない。`finally` でManualへ戻す。
6. Manualで新meshを新しいRunへ保存・SHA記録した後、元のordered P、有向面indices、primitive型/closedを厳密比較する。原04と同じ既定native first-hitをy=.4、下向き、中央3点で実行し、原meshと新meshのprimitive/position/normal/uvwを完全比較する。原記録の高さとも1µm以内で対応させる。点/面の並替え、voxel/フィルター変更、固定水位補正、許容差拡大はしない。

旧.5設定は `particlesep=.04`、`surfmethod=particlefluid`、`voxelsize=.5`、`adaptivity=0`、`dodilate/dosmooth/doerode/dofinalsmooth=0`、`closedcontainer/closedends/flattengeo=0`。期待voxel寸法は.02mだが、このmeshだけから出力Volumeの寸法を実測したとは書かない。

入力の全field値/格点は署名で対応させる。この一回ではsolver縦線の追加query、05の195断面、strict/incidenceの追加検査はしない。既定nativeの原04再現が目的であり、その幾何queryの一般的な正確性を新たに認定するものではない。

## 停止・復元・原記録

- RAM可用8GiB以上、private増加12GiB未満、G空き10GiB以上をManualの節目で読む。
- 各Auto窓30秒未満、全診断RPC90秒未満。client待機180秒。いずれも強制中断ではなく、処理が戻った時点で判定する協調上限である。
- 新mesh16MiB以下、原JSON16MiB以下、今回の全出力64MiB以下。元データの上書き禁止。得られたmeshはnative queryより前に保存する。cook時間超過時もfreeze取得済みならManual復帰後に保存を試み、保存失敗自体を記録する。
- Input FAILは面化前HOLD。旧mesh/native配対FAILは新meshと失敗段階を保持しHOLD。PASSでも他時刻/.25へ進まない。
- 例外では段階と例外型/位置をローカル原記録へ保存する。JSON解析不能、明確な実行状態がない応答、通信timeoutは完了不明とし、追加RPC・再要求・kill・並行cleanupを行わない。
- 完了が明らかな場合だけ元のUI18 guardで所有ノードを削除し、frame、更新mode、viewport、selection、カメラ等を復元する。HIP保存/読込なしとundo状態も照合する。

Autoへの全体更新切替は外部ネットワークの潜在的な自動cookリスクを持つ。既存DOPを直接参照せず、main-threadの短窓・非表示の所有object・UI復元で抑えるが、外部DOP内部状態は監視しておらず、全無影響を証明したとは記さない。

04とRetry03は記録上同じPID53912、22.0.429、Indie、FPS24だった。今回もmetadataは再取得する。主な未解決点はlive solver出力をFile入力へ替えた時の再現性と、原04が全既定parmを保存していなかった範囲であり、バージョン漂移が原因と決め付けない。

## 離線検査と実行入口

以下の二つはHoudini未接続で、既定では証拠を書き換えない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry06/Source/check_replay06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry06/Source/run_replay06.py
```

mockは入力不一致/例外時に第二窓が呼ばれないこと、両窓と各比較段階の例外でManualへ戻ること、型・属性・field・点・面差の拒否、独立RPC namespace、無引数needsToCook、Menu int/token、不明RPC分類を検査する。mockは実HOM動作の代用ではない。

rootの**明示RUN後だけ**使う入口は次の一つで、引数による別frame/.25選択肢はない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry06/Source/run_replay06.py --execute-reviewed-k360-old-half-replay
```

[離線試験](Evidence/22_replay_offline_checks.json)と[freeze](Evidence/22_replay_candidate_freeze.json)を審査対象とする。新Runは `Houdini/Wave22/Runs/pfsreplay06_<token>` に実行元、進捗JSON、最終JSON、mesh、execution/UIを保存する。原JSONとsource SHAだけをACKで受け、数値はローカル原JSONから読む。今回の候補はstage/commitしていない。

根拠となる既存説明は [SideFXのManual/force cookに関するスタッフ回答](https://www.sidefx.com/forum/topic/76888/)、[SopNode](https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html)、[Particle Fluid Surface](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)。本候補の実HOM検証は未実行である。
