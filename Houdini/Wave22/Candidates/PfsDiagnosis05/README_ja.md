# 22修正05 事前計画：既存PFSとsolver場の定義差を読む

**現在は30配対の実BGEO読戻しを完了した。** [実結果・3図・原JSON・再現方法](Evidence/Result_22e7801642/README_ja.md)を参照する。元中央測点90配対・5850断面のquery整合を確認したが、元04のPFS唯一鎖なしを保持し、22完成とはしない。以下は実行前に固定して審査した計画の保存説明である。最初の1配対を読んで原値・pattern・所要時間を独立審査した後、別放行で残29組を実行した。

唯一の基線は[22修正04 Run22e7801642](../WaveStart04/Evidence/Result_22e7801642/README_ja.md)、公開commit `d3be3eb205f6e3ff91c215806bb85df84976cac6`。旧試作や別solver計算は使わない。既存BGEOを `hou.Geometry.loadFromFile` へ読むだけで、ノード作成・DOP/SOP cook・シーン走査・UI時刻変更・HIP操作は行わない。

## 固定する入力と観測

| 項目 | 事前定義 |
| --- | --- |
| 時刻 | k468..526の偶数30時刻、t7.8..8.766667秒、30Hz |
| 入力 | 同時刻のmeshとpilot、60 BGEO合計153,892,203bytes、最大1組5,140,587bytes |
| 原中央測点 | G1=2.242796379968867、G2=2.9903951732918226、G3=3.7379939666147783m、z=0 |
| 周辺配置 | 各Gのx差−.12..+.12mを.02m刻み13点、z=−.12/−.06/0/.06/.12mの5列 |
| 件数 | 195縦線/時刻、5850断面、原中央配対90件 |
| 主断面 | z=0のx方向、および各G中央xのz方向。全近傍行を保存 |

当初検討した8.5秒終端を**実行前に**8.766667秒まで延ばした。G3 PFS谷8.266667とsolver谷8.366667の既定±.375秒prominence右側と平滑の追加標本を含めるためである。G1の早い谷の左側は周辺読戻し区間に含まれない。検出自体は[元04の全時系列と凍結関数](../WaveStart04/Evidence/Result_22e7801642/Executed_Source/startup_response.py)だけを使用し、短い新区間で再判定しない。

これは短槽pilotの.75/1/1.25λの診断である。手順21のfull用2/2.2/2.55λの自由伝播測点とは異なり、22完成や23精度試験を代替しない。

原既定first-hitに命中がある一方、主strict rayが空なら `strict_default_coverage=false` として両観測を保存し、容差/範囲による定義差の再審査まで次組を保留する。両rayが空の場合の整合フラグは形状存在の証明ではない。

全体queryと面限定queryは逆方向も照合し、各incidenceの高さが主strictのいずれかの高さから1µm以内にあることを確認する。逆方向は共有辺の同高別面を許し、primitive一致を要求しない。主strictが取り逃した独立高さは、incidenceのindex・高さ・最小誤差を残して保留する。

## 観測の定義と数値的な曖昧さ

1. 原04のsolverは元と同じ上下bracket、121標本、25回二分で原測点水位を再現する。PFSも元と同じy=.4から下向きの**既定引数native first-hit**を別に再現する。許容差はsolver1×10⁻⁸m、PFS1×10⁻⁶m。元定義の配対失敗は結果を保存して次組を停止する。これは数値再現性であり物理精度ではない。
2. 追加rayはy=.4→−.7m。主query tolerance=1µm/前進2µm、感度queryは10µm/前進20µm。各最大64命中で、primitive0は有効、−1だけをmissとする。前進幅は同じ面を再報告しないためで、これ以下の近接層を排除できない。HOM float32と辺/頂点の影響があるため、二設定とも保存し良い結果だけを選ばない。
3. .04m幅のXZ索引を一度作り、bboxは最大query toleranceの±10µmを含める。候補面ごとに `pattern=str(primitive number)` でnative交点を読む。全face ID/vertex ID/位置/normalを**未統合のまま**保存し、共有辺や同じ高さの断層を勝手に削除しない。主queryの各primitive IDと高さが面限定incidenceにもあるかを1µm許容で照合する。不一致時も両側の原交点・最小高さ誤差をJSONへ保存し、`strict_incidence_consistency_passed=false`で次組を保留する。native反復の高さ件数と面別incidence数は別物である。
4. 元polygonを三角扇へ変換しない。命中面の頂点/Newell平面逸脱を記録し、quadだけは二対角線による高さ差も補助観測する。`two_diagonals_determinate`は二分割の高さが各々定まるという観測だけで、投影凸性は未検査、幾何の妥当性も認定しない。凹面/退化/多値は未確定、nativeを置換しない。0.1mmと1mm差は数値/応答スケールの**記述フラグ**であり物理合否・減幅原因の判定ではない。
5. 場は名前/型/実bounds/transform/voxelとisSDF metadataを保存する。y=−.5999から−.12mは約.03m、−.12から元04と同じ上端min(.25,field_hi−.01)までは.0025m以下で照会する。field外/非有限は停止。wet→dryとdry→wet、零接触・零台地を分け、複数/曖昧な交差を単一自由面へ置き換えない。`single_wet_to_dry_local=false`なら`height_m=null`とし、後処理図もこのフラグが真の行だけを単値で描く。原交差一覧は残す。細かい照会は元約.06m格子の解像度向上ではない。有限標本でより薄い層や全領域の連通を証明しない。

原高さ・近傍x/z差と傾斜・同じ列の時間差を保存する。最も近い高さの枝へ追跡補間しない。原solver場とPFSの約10mm差を固定補正しない。後処理ではこれらの**実cache読戻し値から断面図または時空間図を最低1枚**作り、原高さと差・条件・SHAを併記する。新規運動の動画は作らず、必要なら04の実動画へ明記した参照を置く。

## 元の1mm判定を保持する

04のq、raw振幅、5点対称平滑、±.375秒prominence、唯一鎖規則を変えない。公開原時系列のオフライン再評価で元判定の一致を検査する。PFSの5点は4/30秒、solverの5点は4/60秒を覆い、平滑時間幅が違う。prominence差だけを空間再構成に帰属させない。近傍位置には静水基準窓を新しく読んでいないため、中央q/応答認定を移植しない。

既知のG3 PFS谷はraw振幅約1.9911mmがqを超える一方、左右prominence約.8275mmがq=1mm未満である。solver谷の約1.508mmとは区別する。この数値を通すように閾値・窓・水位を調整しない。

[凍結生成源](../WaveStart04/Evidence/Result_22e7801642/Executed_Source/generate_wave_l6.py)はPFS3.0/particlefluid/voxelScale.5（.02m想定）/adaptivity0を設定し、dodilate/dosmooth/doerode/dofinalsmoothを全て0としている。全既定値の実dumpではないが、明示Final Smoothを原因とする証拠はない。[SideFX資料](https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html)の平滑・平均位置再構成の説明は仮説の参考に留め、今回の原因認定には使わない。[Geometry.intersectの契約](https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html)に従いnativeの定義差も観測する。

## 費用・停止・許可境界

1組の協調処理上限90秒、MCP待機180秒、完了済み読戻し時間合計900秒を上限とする。次組の90秒余地がない場合は開始しない。空きRAM8GiB未満、非有限/field外、元cache SHA不一致、異常HOM、上限64hit超過は停止し、実行エラーを保存する。この場合、未完了の部分断面JSONは保存されないことがある。完了した中央配対・主query/面限定queryの不一致は原JSONを保存して次組を保留する。各原JSONの上限16MiB。原JSONはHoudini側で新規保存し、MCPは原JSON SHAとsource SHAだけ返す。root側はその元bytesを読む。

既定の実行引数はk468の1組だけを許可し、複数組や別時刻はMCP接続前に拒否する。残29組には独立の `--execute-reviewed-continuation` と、審査済み首組の原JSON path/SHAを要する。首組の入力・plan・reader SHA、中央配対、主query/面限定query整合、UI不変が全て一致しない場合は追加しない。フラグはrootの明示放行を置き換えない。計画固定時は追加組未許可であり、今回は首組の実結果審査後に別放行を得た。

単独`loadFromFile`を強制中断する仕組みではなく、完了不明RPCでは再要求・並行清理・killを行わず報告する。各RPCは必要import/定義を全て含み、前回namespaceに依存しない。UIのframe/FPS/dirty/updateModeを前後照合する。ノードもUI変更もないため18項目復元を行ったとは記さない。

合成39,000面の索引と195本の解析φの費用は[離線検査](Evidence/22_profile05_offline_checks.json)に記録する。**これはBGEO読み込みやHOM交点の実費用ではない。** 最初の1組k468の結果後だけ、残29組の実行予算を確定する。場や交点の曖昧さを観測しても物理・非砕波・22完成を認定しない。05の前に06の条件は変更しない。

```powershell
# 公開JSONと合成データのみ。Houdini/MCPは呼ばない。
# 既定の検査は保存証拠を変更しない。計測時間は今回のstdoutへ出す。
python Houdini/Wave22/Candidates/PfsDiagnosis05/Source/check_profile05.py
python Houdini/Wave22/Candidates/PfsDiagnosis05/Source/run_profile05.py

# rootの明示放行後だけ。最初1組以外は未許可。
G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe -X utf8 Houdini/Wave22/Candidates/PfsDiagnosis05/Source/run_profile05.py --samples 468 --execute-reviewed-profile-readback
```

[計画JSONと入力SHA](Source/profile05_plan.json)／[純関数](Source/profile_core.py)／[読戻し定義](Source/read_profile05.py)／[実行源](Source/run_profile05.py)。計画JSONの未実行文言は固定時点を表し、実行した六源のbytesを維持する。68項目の合成/既存公開JSON検査と、別途実施した実BGEO読戻し結果を区別する。

離線検査の保存報告は、生成時の合成所要時間を保持する。通常の再検査は検査一覧・源SHA・費用の固定項目を照合し、再測定時間をstdoutに出すだけで原報告を上書きしない。実装改稿後に証拠を更新するときだけ `check_profile05.py --update-evidence` を明示し、その後の通常検査でbytes不変を確認して再凍結する。
