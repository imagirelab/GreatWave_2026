# 22修正06 再候補01：k360旧面の前処理診断

**本再候補は未実行。Houdini/MCPへの再接続、stage、commit、pushは行っていない。rootの別審査が必要である。** 初回の[実行前保存版](../PfsSensitivity06/README_ja.md)・[凍結SHA](../PfsSensitivity06/Evidence/22_pfs06_candidate_freeze.json)と原Runsは変更しない。本候補を将来実行する場合も **k360/t6の旧`.5`を1回だけ** とし、k474/496、候補`.25`、142枚拡張は自動開始しない。

## 初回で実際に分かったこと

初回tokenは `pfs06_da9e62c8df`。Houdini 22.0.429 Indie、PID53912、UI有効/FPS24を再確認し、Manualでframe145へ到達した後にAssertionErrorでHOLDした。資源保護は通過したが、input signatureはまだ記録されず、PFS output cookの計時・mesh出力・厳密旧面parityは未実施だった。`.25`の比較結果は存在しない。

| 原記録 | SHA256 |
|---|---|
| replay_360.json / 1,105 bytes | `5f492b54f383ceca50adfe1dbf90b398d489e8be4d6d3207d24a39584922798d` |
| execution.json / 6,877 bytes | `51cdc764819b71345c54189fb4c5229be13bf68c7f3b3b7b5ccfee88000050c4` |
| initial_resource.json / 185 bytes | `4ce0dc055ae938324d9279287686470e9c7ee6c1d4ebf57ea1d071ab899860f9` |

stage処理0.665092秒。観測した可用RAMは36,136,148,992 bytes、privateは6,716,923,904 bytes、開始privateは6,695,813,120 bytes。G空きは909,575,118,848 bytes。これらは面化費用の実測ではなく前処理時点のプロセス/OS値である。

UI18項目は全復元、所有物削除・一時session削除も成功。frame1/FPS24/AutoUpdate、undo702、dirty=trueの元状態を保持し、HIPの保存・読込・clearは行わなかった。RPC完了不明ではない。無messageの断言だったため、File入力tuple、型/parm読戻し、signatureのいずれが原因かは**まだ未確定**。幾何parity失敗や物理失敗と読み替えない。

## 対処するAPI仮定と診断記録

- File SOPの `inputs()` は未接続connectorの `None` 占位を返し得る。tupleの真偽で拒否せず、全slotがNoneかつ `inputConnections()` が空であることを確認する。slot一覧と接続数を断言前に残す。実接続は引き続き禁止する。
- Menu評価は整数indexまたは文字列tokenを区別し、menuItemsと対応させる。requested/raw/effective、各Python型、template型、menuItemsを断言前に記録する。要求値の不一致はHOLDのまま、要求値や物理parmを合わせ直さない。
- direct BGEOとFile SOPのsignatureは別phaseにする。実粒子/保持点数、必須属性の有無/型、重複ID数・最初のID、最初の非有限粒子またはfield voxel位置を保存してから判定する。
- 各重要操作の前に `phase`、時刻、部分観測を新Runsのprogress JSONへ保存する。例外ではsource識別子・関数・行番号を保存し、元ユーザーディレクトリを含むtraceback文字列を公開しない。
- 生成できた面はnative query前に別BGEOへ保存・hash・容量・内容読戻しを確認する。reader途中例外では生成BGEOとstage失敗JSONまでであり、195 profile行が部分保存される保証はない。

原File接続の実値やConvertのMenu返却型は、本候補のmockが実現可能性を試しただけで、初回の根因を特定する実測ではない。

## 不変の科学条件と停止条件

唯一の入力は04 `22e7801642` の保存pilot BGEO。PFS `particlesep=.04 / voxelsize=.5 / surfmethod=particlefluid`、filter等の全設定、Convert(poly)、k360の元絶対frame145、FPS24は原計画と同じである。新solver/DOPは作らず、粒子やfieldを変えない。元P/有向indices/native三測点の厳密配対が通らなければその場でHOLD。点番号並替え・許容差拡大・固定水位補正は行わない。

3フレーム全体の物理/面化契約、近傍195断面、旧`.5`全成功前は`.25`禁止、q公式/142フレームの完全性は[計画JSON](Source/pfs06_plan.json)に保持している。ただし本runnerは最初の1stageしか実行しない。成功は「k360の前処理/旧面再現の観測」に限り、残りの先導/面化感度/波精度/22完成とは別である。

可用RAM≥8GiB、private増分<12GiB、1cook<30秒、1RPC協調90秒/client待機180秒、面≤16MiB、G空きの元条件を維持する。native cook中の強制中断は保証しない。エラーが戻れば保存と所有/UI復元を行う。返却を解析できない、または明確な実行完了状態がなければ不明として追加RPC・再試行・kill・並行cleanupを行わない。

## 離線審査用

[純関数](Source/sensitivity_core.py)、[所有面化候補](Source/remesh_pilot06.py)、[1回限定runner](Source/run_pilot06.py)、[離線検査](Source/check_pilot06.py)、[検査報告](Evidence/22_pfs06_offline_checks.json)、[凍結候補SHA](Evidence/22_pfs06_candidate_freeze.json)。

Freshルートでの次の2コマンドはHoudiniへ接続しない。既定checkは証拠を変更しない。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry01/Source/check_pilot06.py
& 'G:\AI\TaskEnvironments\greatwave_wave_analysis\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry01/Source/run_pilot06.py
```

実行候補は次の1回だけで、**まだ放行されていない**。

```powershell
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' -X utf8 -B Houdini/Wave22/Candidates/PfsSensitivity06Retry01/Source/run_pilot06.py --execute-reviewed-single-replay
```

未実測の原因を断定せず、同じ条件の配対と元結果の再現を先に確認する。資料：[SideFX Node.inputs](https://www.sidefx.com/docs/houdini/hom/hou/Node.html)、[Parm.eval](https://www.sidefx.com/docs/houdini/hom/hou/Parm.html)、[PFS](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)。実schemaと返却値の証拠は次の許可された観測に依存する。
