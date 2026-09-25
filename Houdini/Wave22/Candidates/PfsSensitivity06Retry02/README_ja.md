# 22修正06 再候補02：File→Null の更新mode診断

**未実行の審査候補。Houdini/MCPには接続していない。rootの静的審査・明示的な実行承認までは実行しない。** 対象は04 `22e7801642` の `pilot_360.bgeo.sc` だけ。PFSを作らず、新しい面・solver・波を計算しない。旧2 Runと2つの凍結版は変更しない。

## 読み取りだけで分かったこと

初回 `pfs06_da9e62c8df` は無messageのAssertionError。再候補01 `pfs06_4e658eee02` は `FILE_INPUT_SIGNATURE` でHOLDした。この名称の対象は **Null出力** であり、File本体が空だったとまでは実測していない。直接BGEOは53,811点（53,806粒子＋5 Volume保持点）、ID0〜53805が一意、P/v/pscaleと5場の値は有限だった。File inputsは空tuple、PFS/ConvertのMenuは整数0でtokenも指定通りだった。したがって今回の観測は、当初疑ったNone入力slotや文字列Menuの不適合を示していない。初回の未記録原因は確定できない。

再候補01の結果は0.693306秒、生成meshなし、UI18全復元、RPC完了不明なし。

| 不変の原記録 | SHA256 |
|---|---|
| 初回 replay_360.json | `5f492b54f383ceca50adfe1dbf90b398d489e8be4d6d3207d24a39584922798d` |
| 再候補01 replay_360.json | `49fa9614d683afafc73a1a691f8a86e85d8712a41f0fddc849e5c67d5fcecdb8` |
| 再候補01 execution.json | `35ccc97dac64380619d7f1160ace53091f6172812fd2350a4f218cf9c8cfa0f6` |

04の撮影[実装](../WaveStart04/Postprocess/capture_start04.py)はFile→Cd、AutoUpdate、所有物の表示ONだった。06はManual、所有物非表示であり、従来記録だけでは両要因を分離できない。

[SideFX staffの説明](https://www.sidefx.com/forum/topic/76888/)は、Manualでは強制要求でもノードがcookを拒み、同一main-thread呼出しの中で一時的にManualを解除する方法を示している。これは今回の空Nullと整合する有力な説明だが、実Fileの設定/警告を未採録のまま唯一原因と断言しない。

## 固定する1回の観測

1. 実PID/version22.0.429/Indie/UI/FPS24を再確認し、既存UI18を保存。所有subnetを直後にsessionId付き登録し、Manual/非表示でgeo→File→Nullだけを作る。絶対frame145（04 k360）へ置く。File入力なし、literal原BGEOのSHA/bytesを必須とする。
2. 直接 `Geometry.loadFromFile` の署名を先に保存する。粒子ID/P/v/pscale、全点P、全5 Volumeのtransform/resolution/voxel全値、公開属性の型/値、公開群所属と有向接続を比較対象にする。未知属性型・非有限値は理由を残してHOLD。
3. Fileの初期schema、file原値/未展開値/求値、filemode・Load・Missing等を含む実scalar設定とmenu token/labelを保存する。変更はliteral `file` だけ。無入力Fileは公式の読盤経路であり、Write/自動cache書出しへの入力接続は作らない。Read/All Geometryへの後付け再調整も行わない。
4. **Manual前測**としてFileとNullを個別に観測。geometry getter前後、明示cook前後にcookCount・needsToCook（秒）・errors/warnings・表示/bypass/lock旗を採る。点/primitive/属性と署名を別記する。`geometry()` 自体もcookし得るため、明示cookだけの効果と混同しない。
5. main threadであることを確認し、同じRPC内の `try/finally` で短くAutoUpdateへ切替。File/Nullを個別cook/凍結読戻しし、**finallyでManualへ復帰**する。この窓ではyield、待機、別RPC、UI描画、flipbook、他ノードへの探索やDOP APIを呼ばない。重い全属性/全voxel署名とJSON出力はManualに戻ってから行う。
6. AutoUpdate読戻しのFileとNullが直接原BGEOの定義済み全署名に厳密一致し、警告/エラーがなければ、このFile読戻し診断だけをPASSとする。空/不一致/例外は原観測を保持してHOLD。結果に応じてPFSや別時刻へ自動移行しない。
7. 完了が明確なRPCに限り、所有ノード削除と元frame/update modeを含むUI18復元を行う。HIP保存/読込/clear、FPS変更は行わない。

一般の全Houdini状態を比較するものではない。署名は公開属性/群と記載した幾何量で、未列挙の内部private属性や全intrinsicの同一性までは保証しない。isSDF metadataも観測として保存する。

## 安全と限界

AutoUpdateはグローバル設定である。staffが示す同一main-threadの短い切替を使い、UIイベント更新を挟まない。表示旗をOFFのままにし、他のネットワークやDOPには直接アクセスしない。ただし既存DOPの内部状態を全監視しないので、UI18復元だけで無関係な全計算状態の不変を証明したとは記さない。切替の時間・main-thread確認・同RPC内Manual復帰を実記録する。

可用RAM≥8GiB、private増分<12GiB、G空き≥10GiB、1RPC協調予算90秒、client待機180秒、JSON≤16MiB。native処理中の即時停止/連続peak監視は保証しない。RPC完了不明なら再送・kill・並行cleanupを行わずrootへ報告する。実出力は新しい無衝突Runs tokenへ保存し、原BGEOや前回Runを上書きしない。

## 審査資料と入口

[計画JSON](Source/file_probe_plan.json)、[読戻し本体](Source/probe_file06.py)、[runner](Source/run_file_probe06.py)、[離線検査](Source/check_file_probe06.py)、[検査報告](Evidence/22_file_probe_offline_checks.json)、[凍結一覧](Evidence/22_file_probe_candidate_freeze.json)。

以下はFreshルートからの離線確認。既定checkは報告を更新せず、既定runnerは表示だけ。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry02/Source/check_file_probe06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry02/Source/run_file_probe06.py
```

次は**審査後だけ**使用する1回限定の入口であり、まだ実行していない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry02/Source/run_file_probe06.py --execute-reviewed-file-only-diagnostic
```

公式API：[File](https://www.sidefx.com/docs/houdini/nodes/sop/file.html)、[SopNode.geometry](https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html)、[OpNode cook/needsToCook/cookCount](https://www.sidefx.com/docs/houdini/hom/hou/OpNode.html)、[Parm menu](https://www.sidefx.com/docs/houdini/hom/hou/Parm.html)。
