# 22修正06・Replay474：k474旧.5面の単一再現候補

**本候補は未実行。rootの明示RUNまでHoudini/MCPを呼ばない。** 原04 run `22e7801642` の保存粒子から、k474（7.9秒）の旧voxel scale `.5` 面を一回だけ再現する。k360成功は別時刻の証拠であり、k474の結果を先取りしない。k496、`.25`、142面拡張、新solver、detector、動画は今回の対象に含めない。

## 固定する出典と変更範囲

[前k360成功の読取要約](Evidence/22_k360_success_review.json)は、Retry06 run `pfsreplay06_af76bc8ec2` の原JSON/mesh/UI記録にSHAで結ぶ。原04とordered P・有向indices・primitive型/closed・3点nativeが完全一致し、保存後再読も合格した。ただしBGEOファイルのSHAは異なり、未検査のmesh属性まで同じとは主張しない。外部DOP状態は監視していない。

今回は成功したRetry06の対象だけをk360からk474へ変更する。`replay_support06.py` と `replay_window06.py` はbyte同一。runnerと再現関数の差分は[計画](Source/replay_plan.json)の `target_source_changes` に列挙し、離線試験で置換以外の差を拒否する。PFSの11設定、入力署名の規則、厳密mesh/native配対、二窓の順序、資源上限、UI18復元は変更しない。

[保護一覧](Evidence/22_prior_attempts_manifest.json)は前7候補・前6Runの **133ファイル、3,694,829 bytes** を固定する。原HOLDや成功の記録は上書きしない。実行入口は全file集合・bytes/SHA、自身のfreeze/検査/出典、原04公開資料7件、今回の2キャッシュを再照合してからMCPをimportする。

| 固定入力 | bytes | 役割 |
|---|---:|---|
| `pilot_474.bgeo.sc` | 4,269,688 | 唯一の物理入力。53,833粒子＋Volume保持5点＝53,838点/5 primitive |
| `mesh_474.bgeo.sc` | 870,685 | 原04の比較面。39,078点/39,076面 |

合計5,140,373 bytes。SHAは計画の `record` に保存した。3測点は原短槽のx=.75/1/1.25λ、z=0であり、21の本試験測点ではない。原04 native高さはそれぞれ −0.013093209266662575、−0.009756213426589944、−0.01198158264160154 m。

FPS24を維持し、原04の式 `1+(474/60)*24` により絶対frame **190.60000000000002** を要求する。元JSON表記190.6との差2.842170943040401e−14 frameは `frame_contract` に明記する。frame確認は既定06と同じ1e−8 frame未満であり、meshの数値配対を緩めるものではない。

## 二つの更新窓と判定

実行時に現在のPID、UI、Indie、Houdini 22.0.429、FPS24を再取得する。UI18を保存し、Manualへ移して所有subnet/geoを非表示とする。既存HIPの保存・読込・clear、FPS変更はしない。

1. Manualで原粒子と原meshをDirect読み込みする。所有File→Nullだけを作り、入力なしのliteralパス、load設定、Directの全署名を記録する。
2. 同じmain-thread RPCの **Auto窓1** でFile/Nullをcookしてfreezeし、`finally` でManualへ戻る。cookCount/errors/warningsを記録する。
3. ManualでDirect/File/Nullの全入力署名を比較する。許す差は `attribute_inventory.detail` の一意nameによる列挙順だけ。他の型・値・配列順・属性値SHA・粒子/field全voxel/格点・group等は厳密一致。入力不一致、空入力、警告、cookCount増加なしはHOLDとし、PFSを作成しない。
4. 入力PASS後にだけPFS3.0→Convert poly→Outを作る。所有Outのdisplay/renderだけtrue、geo/ownerは非表示のまま。全評価parm、HDAの全section原bytes SHAとライブラリSHAを保存する。
5. **Auto窓2** は原04と同じくOutだけ `cook(force=True)`、Outをfreezeする。PFS/Convert/Outの前後cookCountを読み、`finally` でManualへ戻る。個別PFS/Convertの強制cookは追加しない。
6. 新meshを新Runへ保存・hash取得してから、ordered P、有向face indices、primitive型/closed、有限値、保存再読を比較する。3点nativeは原04と同じy=.4から下向きの既定first-hitで、新旧primitive/position/normal/uvw完全一致を要求する。原記録高さとの対応は既定の1µm以内。点や面の並替え、固定高さ補正、許容差拡大をしない。

PFS設定は `particlesep=.04`、`surfmethod=particlefluid`、`voxelsize=.5`、`adaptivity=0`、dilate/smooth/erode/final smooth=0、closed container/ends/flatten=0。`.02m`は指定からの期待voxel寸法であり、出力fieldを測った値ではない。入力fieldは署名で比較するが、solver縦線、05の195断面、strict/incidence、波形検出は追加しない。

## 停止・記録と限界

- 可用RAM≥8GiB、private増加<12GiB、G空き≥10GiBをManualの節目で読む。前k360は計9.3924秒、Auto窓約.00881/1.17956秒だったが、k474の実費用を保証しない。
- 各Auto窓<30秒、診断RPC<90秒、client待機180秒。処理が戻った時点で判定する協調上限であり、HOMを強制killしない。
- mesh≤16MiB、原JSON≤16MiB、今回の全出力≤64MiB。原ファイル上書き禁止。得たmeshはnative検査前に保存し、失敗を追跡できるようにする。
- 入力FAILは面化前HOLD。mesh/native FAILは生成済みmesh・段階・例外型を保存してHOLD。PASSでも他時刻や`.25`へ進まない。
- 完了不明・通信timeout・JSON解析不能・完了状態欠落なら追加RPC、retry、kill、並行cleanupを行わない。完了が明らかな時だけUI18 guardで所有ノードを削除し、元frame/mode/viewport等を復元する。

Auto切替には無関係ネットワークの潜在的自動cookリスクがある。短いmain-thread窓、非表示の所有object、UI復元で抑えるが、外部DOP内部状態を観測せず全無影響とは書かない。原04とRetry06は記録上同じPID53912/22.0.429/Indie/FPS24だった。今回も現在値を再確認する。

成功しても単一時刻で保存粒子から旧面を再現できた証拠に留まる。全時刻再現、細粒化の効果、原因の特定、22の連続非砕波伝播、本試験波高計、23の物理精度は未検証である。

## 離線検査・実行入口

既定の検査は証拠を書き換えず、Houdiniにも接続しない。mockは両窓の例外復元・入力FAIL時の第二窓禁止・署名/mesh差の拒否・HDA原bytes・独立namespaceを検査するが、実HOMの代用ではない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Replay474/Source/check_replay06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Replay474/Source/run_replay06.py
```

rootの明示RUN後だけ使う入口は次の一つ。他frameや`.25`を選ぶ引数は無い。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Replay474/Source/run_replay06.py --execute-reviewed-k474-old-half-replay
```

[離線検査](Evidence/22_replay_offline_checks.json)と[freeze](Evidence/22_replay_candidate_freeze.json)を審査する。新Runは `Houdini/Wave22/Runs/pfsreplay06_<token>` に実行源・進捗JSON・最終JSON・mesh・execution/UIを保存する。ACKは原JSON/source SHAだけとし、数値はローカル原JSONから読む。stage/commit/pushは行っていない。

手順の公式根拠は、既存候補でも参照した [Manualでのforce cookに関するSideFXスタッフ回答](https://www.sidefx.com/forum/topic/76888/)、[SopNode](https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html)、[HDASectionのbinaryContents](https://www.sidefx.com/docs/houdini/hom/hou/HDASection.html)。今回の実HOM検証は未実行である。
