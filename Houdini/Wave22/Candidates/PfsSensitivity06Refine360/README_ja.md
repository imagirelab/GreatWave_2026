# 22修正06・Refine360：保存粒子から作る新.25面の単一感度候補

**未実行。rootの別途RUNまでHoudini/MCPへ接続しない。** 原04 run `22e7801642` のk360（絶対6秒/frame145/FPS24）保存粒子だけを使い、PFSの `voxelsize` を `.5 → .25` に変更する。新solver、他frame、142面拡張、波検出、q計算は行わない。単一静水時刻の面化感度であり、22完成や物理収束の証明ではない。

## 旧面を再現した三つの先行結果

旧`.5`のk360/k474/k496は独立した実runでordered P・有向indices・primitive型/closed・3測点native・保存再読が完全一致した。各UI18復元も成立し、完了不明なし。新旧BGEOファイルbytesは異なるため、ファイル同一や未検査属性の一致とは書かない。

| k | 実run | 点/面 |
|---:|---|---:|
| 360 | `pfsreplay06_af76bc8ec2` | 38,926 / 38,924 |
| 474 | `pfsreplay06_ac6451419c` | 39,078 / 39,076 |
| 496 | `pfsreplay06_b13cd6bcb8` | 38,912 / 38,910 |

[計画](Source/refine_plan.json)は三runの原JSON/execution/mesh/freeze SHAを固定する。[保護一覧](Evidence/22_prior_attempts_manifest.json)の **180ファイル、6,188,888 bytes** は変更しない。今回も実行前に集合・bytes/SHAを照合する。凍結READMEは実行前の保存版なので、将来の結果は別の公開先からリンクし、ここへResultを追加しない。

唯一の物理入力は原 `pilot_360.bgeo.sc`（4,313,913 bytes、SHA `26f4e93c8f108958359d1faf06f5fc498fdf43182cf1be9fe87e794d5d89688f`）。53,806粒子とVolume保持5点を含む全幾何をFileへ渡し、保持点を勝手に除去しない。旧 `mesh_360.bgeo.sc`（873,004 bytes、SHA `6cdddb10ebb93b51124d8f95bd83fedc1e0d7e71114558fc89ba18f8b5a804cd`）を形状比較と旧195断面の入力にする。05の公開断面にはk360が無いため、今回旧面も同じreaderで読む。

## 変更可能な設定と不変条件

PFS3.0の11明示設定は、`particlesep=.04`、`surfmethod=particlefluid`、**`voxelsize=.25`**、adaptivity/dilate/smooth/erode/final smooth/closed container/closed ends/flattenは全0。指定から期待するvoxel寸法は.01mだが、出力Volumeの実寸を測ったとは書かない。

成功k360のDirect入力署名と今回のDirect/File/Null署名を比較する。許す違いはdetail属性一覧の一意nameによる列挙順だけ。他の属性値・粒子ID/P/v/pscale・全field voxel/格点・配列順等は厳密一致。全評価PFS parmは `voxelsize` だけの差、HDA定義の全原binary sectionとlibrary SHA、Convert全評価parmは完全一致を要求する。実評価の派生parmに他の差が出ても黙認せずHOLDする。

旧/新meshの点数・面数・P・有向接続の一致は要求しない。新mesh保存前後の一致は要求する。旧3点nativeは成功k360の原測定と完全一致しなければならない。新3点は有限/存在を確認し、元の絶対水位、新−旧、旧−solver、新−solverを記録する。固定約10mmの補正や波形選択はしない。

## 更新と読戻しを分離する三段階

1. **面化RPC**：現在のPID/22.0.429/Indie/UI/FPS24を確認し、UI18を保存する。Manualで所有subnet/geoを非表示にし、frame145へ置く。Auto窓1はFile→Nullのcook/freezeだけ、finally Manual。完全入力署名が一致した後だけPFS→Convert→Outを作る。HDA/全parmの配対をManualで済ませてからAuto窓2で原04と同じOutだけをforce cook/freezeする。finally Manualへ戻し、新meshを保存・SHA取得してからnativeを読む。
2. **UI18を復元して所有ノードを削除**する。完了が明らかで復元合格した場合だけ、別の読取専用RPCで旧meshの195断面を採る。既存 `hou.Geometry.loadFromFile` だけを使い、ノード・HIP・frame・update modeへ書き込まない。
3. 旧195が有効なら、さらに別の読取専用RPCで新meshの同じ195断面を採る。旧FAIL/不明なら新へ進まない。各RPCはローカル原JSONへ全行と入力SHAを書き、ACKはJSON/source SHAと保存状態だけを返す。MCPの浮動小数点転送値で判定しない。読取前後のframe/FPS/update modeとHIP未保存変更flagも一致を要求する。

面化中の二つのAuto窓は実際に通った旧再現の実装を維持する。全体Auto更新には無関係なnetworkの潜在的cookリスクがあり、非表示の所有object/短いmain-thread窓で抑える。既存DOPへの直接呼出しは無いが、その内部状態は監視しておらず全無影響の証明ではない。

## 390断面の事前規則

readerは公開05の `profile_core.py` / `read_profile05.py` をbyte同一・SHA固定で使う。3測点×x近傍13点（±.12mを.02m刻み）×z近傍5点（±.12mを.06m刻み）＝各195点。旧・新配列の長さ195、座標順、重複なし、同じ入力fieldの照会値を確認する。

- 元04のy=.4から下向きdefault first-hitを保つ。primitive0も命中。厳密queryは1µm、感度queryは10µm、前進刻み等は05の凍結 `intersection` を再利用する。最大64の上下交点は原face/方向/頂点を保持し、下底交点を第2自由面とは呼ばない。
- 同じ面のdefault/strict first高さ差>1µm、法線向き不整合、primitive限定queryと双方向に不整合、二容差で交点数が違う/高さ差>1µmはquery審査HOLD。共有辺ではprimitive番号一致だけを要求せず、default原primitiveも面限定queryで裏付ける。
- fieldの単一wet→dry局所交差が無い、零平台/接線等で曖昧、交点欠落、旧新の上下交点数変更、上面法線Y方向反転は形状審査HOLD。全域トポロジー、3D空洞、連続時間の水面一価性は認定しない。
- 旧中心の `center_parity_passed` は必要。新中心の同フラグは旧meshとの差でfalseになり得るので、そのfalse自体は失敗としない。原solver中心値との差は両面とも≤1e−8m。近傍断面へ中心測点の波検出判定を継承しない。
- quad二分割は数値感度の補助であり、投影凸性/幾何妥当性を認定せず、減幅原因の証明にしない。

solverの `surface` は元runでVolume/isSDF metadata=falseだった符号場である。細かい照会刻みや細かいPFSがsolverの物理解像度を増やすものではない。

## 資源・失敗・保存

面化の各Auto窓<30秒、面化RPC<90秒、旧/新読戻しは各RPC90秒、client待機180秒。三つの業務RPCの公称合計は270秒だが、HOM呼出しを強制中断する時間保証ではない。完了してから超過を検知する協調停止である。新.25費用は未測定。旧05の実読戻しは約2.25–2.43秒/3.68MBだったが、新面の時間/容量を保証しない。

可用RAM≥8GiB、G空き≥10GiB、private増加<12GiB。面化のManual節目と各読戻し前後で観測する。reader内でも各縦線の前に可用RAM/時間を確認するが、private/ディスクは連続監視ではない。メモリはprocess値でVRAMではない。

新mesh≤16MiB、旧/新profile各≤16MiB、主JSON≤16MiB、Run全出力≤64MiB。profileはserialize後・書込前に一件の容量と実Run残容量を検査し、記帳用64KiBも残す。超過時は完全profileを保存せず、試みたbytes/SHAを小さなHOLD摘要へ残す。摘要の余裕すら無ければ書込なしACKをexecutionへ記録する。ログ等は連続容量監視ではないが、予算超過後に次RPCを開始しない。新meshはnative queryより前に保存し、新旧キャッシュを上書きしない。reader途中の例外では部分195行JSONの保存を保証しないため、既に完成したprofile、生成済みBGEO、段階・例外を残す。数値異常は0や前値で補完しない。面化結果の非有限観測はUI復元後の旧/新profile開始を禁止する。

通信完了不明なら追加RPC/retry/kill/並行cleanupをしない。面化RPCが不明ならUIの自動復元も追加要求しない。断面RPCが不明ならUI18は先に完了済みだが、それでも次の読戻しは行わない。HOLDは局所診断の判定であり、solver失敗や波物理の合否と混同しない。

## 離線検査と入口

既定checkは原証拠を変更しない。全体のMCPを偽物へ置換して、正常、面化HOLD/非有限、UI復元FAIL、旧/新断面HOLD、面化/読戻し完了不明を検査する。別の偽readerで書込前の一件/総容量HOLDとHIP変更flagも検査する。mockは実HOMの代用ではない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Refine360/Source/check_refine06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Refine360/Source/run_refine06.py
```

rootの明示RUN後だけの入口：

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Refine360/Source/run_refine06.py --execute-reviewed-k360-quarter-mesh
```

[離線結果](Evidence/22_refine_offline_checks.json)と[freeze](Evidence/22_refine_candidate_freeze.json)を審査する。結果は新Run `pfsrefine06_<token>` に保存する。公開整理は後日、保護対象外の `Houdini/Wave22/Publication/Revision06/` 等へ行い、原値と差の科学図を作る予定である。凍結候補README/Runは変更せず、現時点ではstage/commit/pushしない。
