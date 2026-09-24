# 19：新しい時間標本とPC深度・影

**PC範囲の中間成果。HMDがないため19全体は未完了で、20の方式採用へ進まない。** 利用者が18を確認して続行を指示した後、新しい実FLIPを計算した。北斎の巻き波や爪状の白波ではなく、2球が結合・崩壊する小さな技術試料である。

- [30/60Hzの近景比較・2秒動画](../Evidence/M1/Sampling19/19_Sampling_2s.mp4)
- [0.25秒](../Evidence/M1/Sampling19/19_Sampling_015.png)／[0.75秒](../Evidence/M1/Sampling19/19_Sampling_045.png)／[1.017秒](../Evidence/M1/Sampling19/19_Sampling_061.png)／[終端2秒](../Evidence/M1/Sampling19/19_Sampling_120.png)
- [固定カメラ対照0.75秒](../Evidence/M1/Sampling19/19_fixed_045.png)／[1.383秒](../Evidence/M1/Sampling19/19_fixed_083.png)／[1.85秒](../Evidence/M1/Sampling19/19_fixed_111.png)
- [18のABC/VAT：色](../Evidence/M1/Sampling19/19_color_000_L.png)／[実深度](../Evidence/M1/Sampling19/19_depth_000_L.png)／[床への落影](../Evidence/M1/Sampling19/19_shadow_024_L.png)
- [Houdini元計算・再現](../../Houdini/Sampling19/README_ja.md)／[出典一覧](../Evidence/M1/Sampling19/19_provenance.json)

## 時間標本の作り方と確認

既存HIPを保存・読込・消去せず、新規所有SOP FLIPとその内部DOPだけを計算した。Steam Houdini22.0.429・Indie分類・既存24fpsを開始時に再確認。Global FPSは24のまま、所有DOPの刻みを1/120秒、表示補間OFF、substep cache ON、time scale1に固定した。要求時刻k/60にglobal frameを1+24k/60へ合わせて実cookし、同じ評価コンテキストのDOP時刻を測った。9点pilot後に121点へ拡張した。[設定](../../Houdini/Sampling19/Evidence/19_solver_conditions.json)、[pilot](../../Houdini/Sampling19/Evidence/19_clock_pilot.json)、[全121点](../../Houdini/Sampling19/Evidence/19_cache_index.json)。

| 項目 | 実測・条件 |
| --- | --- |
| 長さ・標本 | 0〜2秒、60Hzは121時刻、30Hzは同masterの偶数61時刻 |
| 実DOP時刻 | 最大誤差2.22×10⁻¹⁶秒、刻み全件1/120秒 |
| 新規性 | 位置・接続hashはそれぞれ121種類。24Hz既存面の複製や頂点補間ではない |
| 元キャッシュ | 粒子＋面242BGEO、124,142,322bytes。P/N/v再読込・ID一意・有限値確認 |
| 計算条件 | 粒子間隔0.08m、domain12×4×12m、密度1000kg/m³、重力9.80665m/s²、seed19、reseeding有効 |
| 面化 | Average Position、voxel0.06m、adaptivity0、dilate/erode/smoothなし |
| 実計算ログ | solver error/warning0、採取cook合計109.14秒、DOP報告memory最大653,982,226bytes |

30Hzの出力は独立した粗い物理計算ではなく、同じ60Hz計算の偶数形状を抽出したもの。これにより保存・保持頻度だけを比べる。1/120秒はDOP設定であり、全内部圧力計算の誤差保証ではない。

Alembicは可変トポロジー、X反転・scale1・補間OFF。native時刻には1/24秒の書出しオフセットがあり、Unityでは各archiveのMediaStartTimeを基準に相対秒を与える。60HzはGitHubの単一ファイル上限を避け0–40、40–80、80–120の3本に分割し、境界40/80だけ重複する。実再生では一方だけを選ぶ。30Hzは61点の1本。

[独立ABC読戻し](../../Houdini/Sampling19/Evidence/19_alembic_independent_readback.json)は全184格納サンプルのfloat32 P/N/有向triangle接続を元参照と一致確認した。30Hz共通時刻・60Hz境界のhashも一致。Unity EditorとWindows実行版は通常182時刻に加え前segmentの終端2点も照合し、全件合格、位置/法線差0。通常再生の182件では可視meshのboundsも囲い込みを検査した。追加した旧segment終端2件はP/N/有向接続の照合のみで、報告内のboundsEncloseImportedVertices=falseは未設定の初期値を残している。この2件のbounds合格とは読まない。[実行版全件](../Evidence/M1/Sampling19/19_runtime_validation.json)。

## 保持による形状差

60Hzの奇数60時刻と、30Hzが保持する直前偶数形状を比較した。跨時刻の頂点番号は対応させず、各方向256個の面積比例標本から相手の全三角形への距離を求めた。±XYZの外周5%帯も最大16点ずつ別集計した。[解析詳細](../../Houdini/Sampling19/Analysis_ja.md)。

- 各時刻の標本距離p95の最大：0.08434m（1.85秒）。
- 全標本の最大：1.06213m（1.383秒）。該当点はz=-6.499mで、粒子domain±6mの外縁側にある。流出・面の消失を含み、波頭の段差や知覚閾値ではない。
- 全点bounds端の最大変化：0.18038m。同一時刻の30/60Hz共通形状は一致。

これは有限個の表面標本の距離で、厳密Hausdorff距離でも物理的真値に対する誤差でもない。動画は60Hz形状のboundsに同じカメラを追従させ、左右でカメラ条件を共通にした近景。形状差とカメラ運動を分けるため固定姿勢の対照3枚も保存した。動画は0〜119の120枚で2秒、2秒終端120は別静止画に残す。記録60fpsは実時間性能ではない。

主役波の尖端段差、白波の爪、海洋物理精度、HMDの滑らかさは未検証。90Hz追加の判断にも本物のcrest形状と実機が必要で、今回の小試料だけで不要と決めない。

## 深度・影は別の24Hz試料で検査

新規30/60Hz試験はAlembicを使う。VATの深度・影は18で正式に書き出した同一49時刻/24HzのABCとVATを、19専用shaderで比較した。30/60Hz VATを作った、または検証したとは記さない。

新shaderは色とShadowCasterで同じVATデコードを共有する。Built-in・Direct3D11、実Directional light1灯、hard shadow、bias0.01、normal bias0、shadow distance45m、MSAAなし。設定は19実行時だけに適用し、既存ProjectSettingsは変更しない。IPD64mm相当の左右2カメラ、0/1/2秒の6条件で、同じ眼姿勢・透視45°・640×480・near0.05/far60mを両形式へ使った。時刻に応じて既知寸法の遮蔽物も移す。

初回はCamera.Render後にカメラ依存の深度/投影定数を読んだためNaNとなり不採用。閾値を緩めず、描画中のOnRenderImageで生深度・眼奥行き・表示用の3専用RTへ保存し、描画後はそれらだけを読んだ。[不採用記録](../../Houdini/Sampling19/Evidence/19_rejected_depth_capture.json)。

正式6条件ではcallback実行、生深度finite、眼奥行きfinite、流体による深度画素の変化を確認。ABC/VATの眼奥行き差は最大0m。流体本体をShadowOnlyにして床への影を描き、非表示時との差と両形式の差を比較した。[実記録](../Evidence/M1/Sampling19/19_runtime_capture_report.json)。

別物体から流体表面への受影は**0秒の人工左右2視点のみ**で別途確認した。光線上流のcubeをShadowOnlyにし、rendererの有効/無効で影だけを切り替えた。流体なし床深度との差から流体maskを作り、その内側で暗くなる画素は左5,707／右5,735。ABC/VATとも同数で、影ON/OFFの深度差は0mだった。これは画素数の一致であり、受影画像の全画素一致を主張しない。[左の実対照](../Evidence/M1/Sampling19/19_receive_000_L.png)／[右](../Evidence/M1/Sampling19/19_receive_000_R.png)。1/2秒のreceiverTested=falseは未実施を示し、当該2時刻の受影合格には使わない。

人工左右カメラはOpenXRの実眼配送・頭部追跡・SPI・再投影・depth submissionの代替ではない。SPI条件の単独コンパイル28経路はコード準備だけ。HMD、通常ウィンドウの物理キー操作、GPU専用時間・実機フレーム時間は保留。

## 容量と再現

| 保存物 | 実ファイルbytes | 方針 |
| --- | ---: | --- |
| 60Hz ABC 0–40 | 7,210,212 | Git掲載 |
| 60Hz ABC 40–80 | 59,700,708 | Git掲載 |
| 60Hz ABC 80–120 | 84,002,676 | Git掲載 |
| 30Hz ABC 0–120 | 74,501,988 | Git掲載 |
| 参照gzip | 70,637,077 | Git掲載。可逆展開後126,970,116bytes |
| 全242BGEO | 124,142,322 | 本機のみ、SHA/生成元は掲載 |

60Hz3本の書出し計179.80秒、30Hz87.91秒。分割境界重複とROP起動回数が異なるので、容量や時間を一般的効率の比とは呼ばない。18のVATテクスチャは既存入力を共有し複製しない。

本機の実行一式：`G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Sampling19\`。`GreatWave19.exe`起動後、1で30Hz、2で60Hz、Space停止・再開、R先頭、Q終了。2秒で停止する。移動・配布はフォルダー全体が必要。

```powershell
& 'E:\6000.4.3f1\Editor\Unity.exe' -batchmode -projectPath 'G:\Unity\GreatWave_2026_Fresh\Unity' -executeMethod GreatWave.Editor.Sampling19Builder.CreateAndValidate -quit -logFile 'G:\Unity\GreatWave_2026_Fresh\Unity\Logs\19-editor.log'
./Tools/Build_Sampling19.ps1
./Tools/Capture_Sampling19.ps1
```

最終ビルドは480,035,659bytes、errors0/warnings3、build前後ソース差0。実行一式・生121PNG・ローカル重複出力はGit対象外。新規ABC・参照・選択画像/動画・ソース・数値・hashを掲載する。provenanceはbuild前後の全ソース、payload、媒体、実行log、Houdini元計算を結ぶ。M0由来のOpenXR native起動前探査にはruntime未導入メッセージがあり、ログ全体無警告とは言わない。

元2球の物理精度・体積保存は合格にしていない。粒子数は1305→570へ減り、後半の流出と面化の形状誤差を含む。60Hzへ増やすだけではこの問題は解決しない。既存15修正/16/17/18の成果を保存したまま、19のPC中間確認で停止する。
