# 22修正06・Decision04：File/Null署名の離線判読

これは実行済み Retry03 の原JSONを別の比較規則で読む候補であり、Houdiniを新たに実行した結果ではない。元の `passed=false` / HOLD と `equals_direct=false` を保持する。既存の候補・Run・原キャッシュは変更しない。PFS面化の再現、細かいvoxelの採用、22の波伝播完成はいずれも未確認である。

## 入力と保護

唯一の対象は `file06_22b8368396` の k360 診断である。

| 原記録 | bytes | SHA-256 |
|---|---:|---|
| file_probe_360.json | 100,667 | `2821647739c1e0f0f836350ca4920337e35a9ae780a924ce8bff5601e23c9910` |
| execution.json | 5,857 | `88305d8f7698cb3d2d204e8fe4417b07db98610018761e9130aecf24f9120d3a` |

[入力計画](Source/decision_plan.json)に原04粒子BGEO・Retry03 freezeも固定する。[保護一覧](Evidence/22_prior_attempts_manifest.json)は前4候補と前4Runの**80ファイル・2,110,939 bytes**を対象にし、全ファイル集合、bytes、SHAを入口と判読後に照合する。実行元6ファイル、結合source、plan、ACK、原JSON、UI復元ACKを結び付ける。原Runにはローカルパスを含むため、この候補はまだ公開用抜粋ではない。Gitへの追加・コミットは行っていない。

## 許す差を一箇所に限定

比較用の深い複製の `attribute_inventory.detail` だけを、一意な `name` をキーとする辞書へ変換する。元の10属性が全て存在し、名前・型・size・arrayが一致することが必要で、重名、欠落、追加は拒否する。全 `attribute_value_sha256` は名前ごとに厳密一致を要求する。

他の署名の全キーと値、数値型、point/primitive/vertex属性の列挙順、粒子ID/P/v/pscale、全点P、5つのfieldの全voxel SHA・transform・resolution、方向付きindices、groupは正規化しない。辞書のキー順はJSONの意味に含めないが、それ以外の配列順は保持する。一般的な許容誤差を追加しない。

原比較で各Auto観測とDirectの差は**16葉**で、4観測とも同じdetail一覧順の差だった。4つのAuto署名は互いに原順のまま完全一致していた。判読JSONは各組の全16差と元の順序を保存する。同じ差を4回比較した記録であり、64個の独立した幾何差があるという意味ではない。

## 実測に基づく新しい解釈

| 読戻し段階 | 点 / primitive | cookCount | 状態 |
|---|---:|---|---|
| Direct BGEO読込 | 53,811 / 5 | 対象外 | 53,806粒子と5つのVolume保持点 |
| Manual・File/Null | 各 0 / 0 | 各 0→0 | 強制cook後もneedsToCook=true |
| AutoUpdate・File/Null | 各 53,811 / 5 | 各 0→1→2 | geometry取得が0→1、明示cookが1→2 |

AutoUpdateの実窓は **0.06260849995305762秒**、診断全体は **11.380468299961649秒**。4つのAuto観測は `RECORDED_SIGNATURES_EQUIVALENT_EXCEPT_DETAIL_ENUMERATION` と新たに判読する。これは保存した署名の範囲での意味の同一性であり、元の実行が事前の順序付き比較に失敗した事実を取り消さない。

全ノード観測のerrors/warningsは空。Auto窓と同じRPC内でManualへ戻し、その後に署名計算とJSON保存を行った。UI18項目、所有ノード削除、session除去、HIP保存/読込なし、undo不変、通信完了不明なしを原記録に結び付けて再照合する。

他DOPへの直接呼出しは記録上ないが、他ネットワークの状態自体を監視した試験ではない。内部private属性や全intrinsicは今回の署名に含まれず、証明範囲を拡張しない。これだけでは live solver入力をFile入力に替えたPFS出力の再現性は分からない。

## 再照合と反例試験

以下は標準ライブラリだけを使う離線処理であり、Houdini/MCP、ネットワーク、別プロセスを呼ばない。既定では保存済みJSONと再計算結果をbytesで照合し、証拠を書き換えない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Decision04/Source/check_decision06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Decision04/Source/adjudicate_file06.py
```

証拠生成時だけ `check_decision06.py --update-evidence` と `adjudicate_file06.py --write-evidence` を使用した。生成後のfreezeには全source・本書・入力保護一覧・判読・試験結果を含める。

- [判読JSON](Evidence/22_file_signature_adjudication.json)：原HOLD、各16葉差、4署名の新解釈、cook/UI/出典。
- [離線反例結果](Evidence/22_decision_offline_checks.json)：detail順序以外の変更拒否、入力dict/原ファイル不変、Houdiniなし。
- [候補freeze](Evidence/22_decision_candidate_freeze.json)：審査対象のbytes/SHA。

## 次の段階は未実行

この判読が独立審査を通った後に、別候補の **k360・旧voxel .5だけ**のPFS parityを準備する。実行にはさらにrootの明示放行が必要である。

次候補では同じmain-thread RPC内の短いAuto窓を二つに分ける案とする。第1窓はFile/Nullのcook・freezeだけを行い、Manualで完全な入力署名を判定する。入力PASS後だけ第2窓でPFS/Convert/Outをcook・freezeし、Manualで原04のordered P、方向付き面indices、型/closed、3測点native first-hitを厳密比較する。所有outのdisplay/renderを記録し、geo/ownerは隠す。両窓は例外時もManual復帰を保証する設計とし、不明RPC時の追加cleanupは禁止を維持する。現時点ではそのHoudini実行コードも走らせていない。

04とRetry03は同じPID53912 / Houdini 22.0.429 / Indie / FPS24の記録で、バージョン変更が原因だったと推測しない。未取得の全既定パラメータやlive solver→File入力の差は、今後の面化parityで確認すべき残存事項である。
