# 22修正04：短槽の実活塞始動応答（中間結果）

新所有DOPの Run `22e7801642` は、同L6・SOP doreseeding=0の初態を厳密配対し、原t6静水判定を再び通過した。同じDOPのまま実活塞を動かし、事前固定t9.25で正常終了した。**solver場で有序の谷候補を一つ観測したが、PFS表示面は同じ検出規則の唯一鎖なし。番号22の完成、非砕波・無反射・理論精度の合格ではない。**

- [実測原水位・表示面の全時系列](22_startup_full_series.png)
- [事前規則の谷候補と閾値](22_startup_response.png)
- [556時刻の原CSV](22_startup_gauges.csv)／[数値摘要](22_startup_summary.json)
- [元入力と圧縮SHA](22_original_manifest.json)／[実行摘要・UI復元](22_execution_summary.json)
- [840 BGEOの全件読戻しSHA](22_cache_manifest.json)／[実行当時の凍結源](Executed_Source)
- [実PFS動画・97枚/30fps](Media/22_startup_PFS.mp4)／[固定8秒の斜視画像](Media/22_Perspective_480.png)／[最終PFS9.233333秒](Media/22_Front_554.png)／[媒体の出典](Media/22_media_manifest.json)

## 判定と観測

静水窓(4.5,5.25]・(5.25,6]の各45標本は、平均差/RMS/傾き×窓長3mmと代理量1%を全て通過した。G3傾きは+.078941585/+.680174425mm、代理窓平均の変化は+.001422863%。この値は水量保存を意味しない。
不変保存した361行のt6原JSONとconditions/policy/gate SHAを両側で確認した後だけ、同一DOP sessionId101009へ許可を出した。パラメータ変更・resetはない。

| 観測 | G1 | G2 | G3 |
|---|---:|---:|---:|
| solver符号場の最初の持続超過 s | 7.366667 | 7.583333 | 7.816667 |
| solver符号場の唯一鎖・谷候補 s | 7.800000 | 8.000000 | 8.366667 |
| PFS表示面の最初の持続超過 s | 7.466667 | 7.666667 | 7.866667 |

solver鎖の隣接遅れは.200/.366667秒。理論.375秒に合う候補へ置換せず、波速精度へ読み替えない。PFSには閾値超過があるが全条件を満たす三点鎖がなく、別観測として未確認を保持する。元60Hz solver水位と30Hz PFS水位には絶対高さの差が残り、10mmの固定差を引いていない。

`surface` Volumeの `isSDF` metadataはfalse、grid preflightの `physical_pass` もfalseである。名前付きsolver surface符号場の実観測であり、物理認証や全域の正しい距離場を意味しない。
6×7128の深水観測は**全てt<=6の静水段**で、全42,768点が場内・有限・負かつ半径.08m以内の実粒子支持ありだった。t>6の全領域被覆をこの結果で合格にしない。支持数のmedianは上側中央値、p95はnearest-rankで、無空洞・連通・水量の証明ではない。

## 実行と限界

556solver/粒子、278PFS、6予備場の840BGEO、2,640,361,537bytesを全件SHA照合した。PFS最終はk554/t9.233333、solver最終はk555/t9.25である。原キャッシュはローカル `Houdini/Wave22/Runs/22e7801642/Cache/` に保存し、Git公開はmanifestと原JSON/gzipで行う。
53,794→54,037粒子、ID出生243/消失0を観測した。SOP doreseeding=0でも内部 `onlysourceseeding=1/reseed=1/reseedsinglepass=1` であり、出生ゼロや質量収支とは解釈しない。
実collision vxと解析活塞速度の最大差2.301124×10⁻⁵m/sは元の1×10⁻⁴m/s保護内。全標本の時計・有限・ID・solver・移動壁外20mm・局所ゲージ・資源保護を通過したが、局所検査だけで全域無漏れや非砕波を宣言しない。

cook合計1075.137秒、最大2.835秒/標本。581回の順次RPC合計1432.576秒。DOP cache最大805,210,137bytes、private最大9,054,294,016bytes、空きRAM最小33,594,212,352bytes。
18項目UI復元/所有物削除PASS、完了不明RPCなし、HIP保存/読込/clearなし、FPS24維持。
G3の対象λの閉端帰還目安10.144秒、長波では9.405秒。停止9.25がこれより早くても、広帯域ramp・初期残動・圧力応答を排除せず無反射保証はない。ramp完成包絡は最遠点で11.664秒の目安であり、今回は定常状態や5周期を測っていない。

計算後に所有File SOPへliteral BGEOを読み、原P・有向indicesと照合して撮影した。UI時刻1/FPS24固定、initializeSimulationsとmotionBlurは明示OFF、既存DOPの再計算なし。静止画はFrontのt6/7/8/9/9.233333と斜視t8/9.233333の7枚で、原PNG bytesを保持した。別の固定Front採録97枚はk360..552（t6..9.2）を30fpsで再生し、長さ3.233333秒の最後はk552を保持する。最終PFS k554/t9.233333は別静止画、t9.25のPFS画像は存在しない。

MP4はH264/1280×720、全復号エラー0。日本語時刻字幕だけを追加し、時間補間・形状加工・空間倍率変更はない。全長6mの画角なので起伏は小さく、時系列図と併読する。主役の大波や美術完成の証拠ではない。両撮影のUI18項目とgrid/color復元は全PASS。媒体manifestはBGEO→PNG→MP4のSHA、各実時刻、ffmpeg版・設定を記録する。元97PNGは本機Captureに保持し、公開7PNGはpreflight原bytesの複製である。

## 公開資料からの再計算

```powershell
python Houdini/Wave22/Candidates/WaveStart04/Postprocess/summarize_start04.py --input Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642
```

Originalのgzipを展開して原SHA照合し、実行時に凍結した応答関数を再評価する。CSV・2図・数値摘要を生成する。公開再計算はBGEO再cook/再読戻しや実GUI撮影の代用ではない。
[事前計画の保存版](../../README_ja.md)・[源と出力の再計算manifest](22_reproduction_manifest.json)を参照する。

[Runsを含めない隔離復算](22_isolated_reproduction.json)はCSV・2図・数値摘要と再計算manifestのbytes一致を確認する。実媒体の再撮影やBGEO再検証とは別である。[今回の最終出典](../22_revision04_provenance.json)に公開文書・実行元・解析元・媒体を結ぶ。
