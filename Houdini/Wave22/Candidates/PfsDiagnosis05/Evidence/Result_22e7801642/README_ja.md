# 22修正05：既存PFSとsolver符号場の局所読戻し

**実BGEOの読戻し診断を完了した。新規solver計算・ノード作成・UI変更はない。** 元04のPFS唯一鎖なしという判定を保持し、番号22の波の完成・非砕波・精度は未認定である。

唯一の入力は修正04 Run `22e7801642`、公開commit `d3be3eb205f6e3ff91c215806bb85df84976cac6`。k468〜526の偶数30時刻（7.8〜8.766667秒）についてmesh/pilot計60 BGEO、153,892,203bytesをSHA照合して読んだ。G1/G2/G3は短槽pilotのx=.75/1/1.25λであり、手順21のfull用2/2.2/2.55λとは別である。

## 実測図と読戻し範囲

- [原中央水位と定義差](22_profile05_centers.png)：左は04の原時系列、青帯の30時刻を再読込。右は同時刻PFS−solver差であり、水位補正ではない。
- [G1〜G3の実局所断面](22_profile05_sections.png)：元04の既知G3谷候補k496/k502を選んだx/z断面。新たな合否用の時刻選別ではない。
- [G3の元prominence採否](22_profile05_G3_prominence.png)：04の全時間窓・凍結関数を再評価し、左右の値を別記。
- [5850行の断面CSV](22_profile05_sections.csv)／[数値摘要](22_profile05_summary.json)。図は実キャッシュの測定値を描いたもので、Houdiniビューポートの新しい画像ではない。

各Gのx±.12mを.02m刻み、z=−.12/−.06/0/.06/.12mとし、195縦線×30時刻=5850断面を事前登録した。元中央測点のsolver121点/25回二分とPFS既定first-hitを再現し、90配対すべて元値との差0mだった。近傍solver列は上限min(.25,field_hi−.01)まで照会した有限区間の補間符号交差で、根許容1µm。原中央の25回二分値と同じ精度とは記さない。`surface`はVolumeで、isSDF metadata=falseを保持する。

| 読戻し検査 | 実結果 |
| --- | --- |
| 主/感度/native既定交点 | 各列の高さ差0m。主1µm・前進2µm、感度10µm・前進20µm |
| 主ray / 感度ray / 面限定incidence | 各11,700命中。primitive/高さの双方向照合は全一致 |
| 符号場の縦線 | 848,250個のφ標本が有限。5850列で単一wet→dry、零台地・接線零点なし |
| meshの上側交点 | −15.1943〜−3.6363mm、normal Y=.994801〜1 |
| meshの下側交点 | −613.3791〜−606.3722mm、normal Y=−.999999〜−.997287 |

上下二つのmesh交点を二層の自由水面とは呼ばない。既定first-hitは上側と一致し、下側は表示面の底側である。有限の線・時刻・数値許容の範囲では、首命中の取り違え、二設定間の容差差、標本で見える複数交差は、今回のG3不採用を説明する証拠にならなかった。未標本化の薄い層や全3D/連続時間の交差を完全に排除したとはしない。

## G3の不採用理由と限界

元04の556時刻・baseline・q・平滑・候補・唯一鎖を変更せず、status/onset/featuresを含む元結果全体が再計算で一致した。以下は平滑後の**谷候補**であり、rawの最小標本時刻とは別である。

| 元G3候補 | 時刻 | raw振幅（元μから） | 左prominence | 右prominence | 元q=1mmでの採否 |
| --- | ---: | ---: | ---: | ---: | --- |
| solver符号場 | 8.366667s | 3.618661mm | 1.507968mm | 3.396022mm | 採用 |
| PFS表示面 | 8.266667s | 1.991066mm | 0.827461mm | 1.542008mm | 左側だけ不足、不採用 |

PFSの左右支持は切れていない。左側の基準標本はt7.9、平滑高さ−11.989295mm、候補平滑高さ−12.816757mmだった。したがってraw振幅がqを超えていても、左側の回復幅が元規則を満たさない。rawの最小標本はPFS t8.3、solver t8.333333であり、表の平滑候補時刻と混同しない。PFS5点の時間幅は4/30秒、solverは4/60秒で異なる。05の短い近傍窓に元中央の閾値や認定を移植していない。

二つの候補の時刻差.100秒は、この観測定義と標本化の下での差である。直接、波速や物理的な位相誤差へ換算しない。

G3中央の同30Hz PFS−原solver差は−9.896538〜−8.300951mmで、固定10mmではない。定数オフセット自体ではprominenceは変わらず、今回は高さ補正を一切していない。k496のz=0・13点のx断面幅はPFS5.119145mm、符号場2.056885mm、中央xの5点z断面幅は4.205793/2.603760mmだった。PFSの空間変化が一律に小さくなるわけではなく、『PFSが全てを平滑化した』とは結論しない。

quad二対角線の補助高さ差は最大.213745mm、1017件が.1mm以上、1mm以上は0件だった。投影凸性は未検査で、これは元native面を変更しない数値感度観測に限る。PFS候補の不足幅.172539mmより最大値が大きい一方、場所・作用が異なり、原因とも無影響とも認定しない。固定sourceのPFS3.0/particlefluid、想定voxel.02m、adaptivity0、dodilate/dosmooth/doerode/dofinalsmooth全0も保持する。明示Final Smoothが原因とは言えない。

同じ登録列の隣接1/30秒差は5655件。最大|Δη|はPFS .729829mm、符号場1.311646mmだが最大値の位置は別である。比を減幅係数にせず、有限差分から数学的連続性、物理精度や非砕波を証明しない。**今回の診断は観測定義の切り分けであり、面再構成・格子・時間標本の単一因果を確定していない。**

## 実行・原bytes・再現

最初のk468だけを `profiles05_77a1b7dda9` で実読戻しし、原JSON SHAと中心/双方向query一致・UI/資源を独立審査した。その後、独立continuationフラグと審査済み首組SHAを必須にして残29組を `profiles05_894837442e` で順次読んだ。Steam Houdini22.0.429/Indie/PID53912、FPS24。frame/FPS/dirty/updateModeの4項目が毎組前後一致し、完了不明RPCなし。UI変更がないため、18項目の復元を実行したとは記さない。

全読戻し69.735298秒、各2.252064〜2.427344秒、RPC合計73.485528秒。空きRAM最小36,150,370,304bytes、最大原JSON3,681,820bytes。90秒/180秒待機/総900秒/8GiB/16MiBの事前保護内だった。これは既存BGEOの読込み・測定費用であり、solver計算や再生フレーム時間ではない。

[原JSONのgzip30本と実行記録](Original)は110,422,809bytesを12,839,583bytesへmtime=0 gzipで無損失圧縮した。展開SHAと保存SHAは[原記録manifest](22_profile05_original_manifest.json)で照合できる。[Executed_Source](Executed_Source)は実行した6ファイルの原bytes、[Baseline04](Baseline04)は凍結04の全時系列・検出関数など、[60 BGEO manifest](22_profile05_cache_manifest.json)は本体の原SHA/bytesを保持する。BGEO本体は本機Runsだけに残す。

```powershell
python Houdini/Wave22/Candidates/PfsDiagnosis05/Postprocess/summarize_profile05.py --input Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642
```

これは公開gzipからの図3枚・CSV・摘要再計算で、Houdini接続/BGEO再読込ではない。Python/描画依存は[requirements](../../Postprocess/requirements.lock.txt)、MeiryoのSHAは[解析manifest](22_profile05_analysis_manifest.json)に記録する。別font/描画版ではPNG bytes一致を保証しない。[隔離再計算記録](22_profile05_isolated_reproduction.json)と[最終出典](../22_revision05_provenance.json)を併読する。

新規運動や新動画は生成していない。[04の実PFS動画](../../../WaveStart04/Evidence/Result_22e7801642/Media/22_startup_PFS.mp4)は同じsolverの全槽表示であり、05の局所診断図とは出典を区別する。22には引き続き非砕波の連続伝播、full条件の実測点・媒体が必要である。理論精度は23、反射・収支は25の後続検証として分ける。
