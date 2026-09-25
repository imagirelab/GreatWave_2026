# GreatWave_2026

『神奈川沖浪裏』をHoudini・Blender・UnityでリアルタイムVR作品にする制作記録です。旧試作を参照せず、番号ごとに新規検証してコミットします。

利用者の最新指示により、代理が各番号を制作・独立レビューして最終作品へ継続します。**20では同じ24Hz小試料のPCロード・メモリ・CPU費用を測り、Built-in＋Alembicを制作の形状基準として暫定継続します。VATは候補を保持。GPU時間・HMD・主役波が未検証のため、最終VR形式は未採用です。** 進行役は指示とレビュー、実装担当のGPT-6は制作とコミットを担当します。

## 22の実水槽・中間結果を見る

最新の22修正06は、保存粒子から旧PFS `.5` の3時刻を厳密再現した後、t6の一面だけ `.25` へ細分化しました。旧新各195断面の読戻しは成立し、中央の高さ差は+0.0483/+0.0726/−0.1481mm。**単一静水時刻の面化感度であり、波形・物理精度・番号22完成は未判定です。** 新しい流体計算や他frameへの拡張は行っていません。

- [修正06・中央の原水位と面化差](Houdini/Wave22/Evidence/Revision06/22_refine06_centers.png)／[195位置の実差](Houdini/Wave22/Evidence/Revision06/22_refine06_spatial_difference.png)／[失敗履歴・原JSON・再現・限界](Houdini/Wave22/Evidence/Revision06/README_ja.md)

修正05は、同じ04の既存BGEOを30時刻・5850断面で読み、G3 PFS候補の元の左prominence不足を確認しました。減幅の単一原因は未確定、元のPFS唯一鎖なしを保持します。

- [原水位と差](Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_centers.png)／[実cacheの局所断面](Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_sections.png)／[G3候補の採否](Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_G3_prominence.png)／[05の数値・原JSON・再現](Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/README_ja.md)

修正04は新所有DOPで静水判定を再PASSし、同じDOPのままt6〜9.25の実活塞始動を観測しました。solver場の有序谷候補1鎖とPFS唯一鎖なしを分け、非砕波・理論精度は未認定です。

- [実Houdini PFS動画・97枚/30fps](Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Media/22_startup_PFS.mp4)／[固定8秒静止画](Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Media/22_Perspective_480.png)／[原水位の実測図](Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/22_startup_full_series.png)／[数値・出典・限界](Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/README_ja.md)

- [ON/OFFの実時系列図](Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_reseeding_full_series.png)／[固定窓の図](Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/22_reseeding_late_windows.png)／[数値・原JSON・再現](Houdini/Wave22/Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f/README_ja.md)

- [修正02・L6と旧槽の実SDF/PFS比較](Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_full_series.png)／[固定窓](Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_late_windows.png)／[比較CSV](Houdini/Wave22/Evidence/Length6_Result_db52394211/22_length6_gauges.csv)

以前のt3、旧槽t6、reseeding ONのL6 t6は静水判定FAILで、履歴を保持しています。修正03のOFF静水対照は未駆動で終了し、修正04では新規計算・再判定の後だけ始動しました。小さい変位の視口動画だけで大波や物理精度を認定しません。

- [未補正の水位と表示面の比較](Houdini/Wave22/Evidence/Preroll_0652da0179/22_preroll_sdf_mesh.png)／[実Houdini静止画・3秒](Houdini/Wave22/Evidence/Still_0652da0179/22_Perspective_180.png)
- [22の不合格理由・独立レビュー・残る条件](Docs/Progress/Step_22_ja.md)／[181時刻CSV](Houdini/Wave22/Evidence/Preroll_0652da0179/22_preroll_gauges.csv)／[再現方法](Houdini/Wave22/README_ja.md)

- [22修正01・旧槽t6の未補正SDF/PFS図](Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_full_series.png)／[判定窓の拡大](Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_static_late_windows.png)／[361時刻CSV](Houdini/Wave22/Evidence/Checkpoint6_Result_3e5ff87a29/22_checkpoint6_gauges.csv)

## 21の小振幅波の基準を見る

- [固定条件と22〜25の測定計画](Docs/Progress/Step_21_ja.md)
- [解析式のみの波形図](Houdini/WaveBaseline21/Evidence/21_analytic_reference.png)／[境界・波高計・再現方法](Houdini/WaveBaseline21/README_ja.md)

波高6cm・周期1.5秒・水深60cmの単色波を基準に、理論波長2.990395mと位相速度1.993597m/sを計算しました。これは解析式の条件固定で、実FLIPやUnityの波映像ではありません。22は小さな境界/時計pilotから進め、実測した水面・伝播・反射を理論と照合します。

## 20のPC測定と暫定判断を見る

- [Alembicの近景・2秒動画](Docs/Evidence/M1/Decision20/20_abc_2s.mp4)／[Fluid VATの同視点動画](Docs/Evidence/M1/Decision20/20_vat_2s.mp4)
- [Alembic 1秒](Docs/Evidence/M1/Decision20/20_abc_024.png)／[VAT 1秒](Docs/Evidence/M1/Decision20/20_vat_024.png)
- [3回ずつの実測表・採用条件・再現方法](Docs/Progress/Step_20_ja.md)／[01〜22の検証状態と残る条件](Docs/Progress/Verification_Status_ja.md)

20専用Windows版の6つの新プロセスで、同じ入力を広景/固定近景・単眼/人工2視点で測りました。新プロセス初回scene読込の中央値はABC 19.67ms、VAT 153.11ms。VATはCPU更新が軽い一方、初回メモリ増分が大きく、GPU時間は追加の通常カメラ診断でも取得できませんでした。映像は計測外の近景カメラによる実描画で、性能値やHMD映像ではありません。

測定用一式は `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Decision20\`。[ビルド](Tools/Build_Decision20.ps1)／[測定・媒体の再取得](Tools/Run_Decision20.ps1)。次の小振幅波の物理基準など独立した制作へ進み、HMDが必要な判定は保留一覧に残します。

## 19の時間標本・深度・影を見る

- [30/60Hzの近景比較・2秒動画](Docs/Evidence/M1/Sampling19/19_Sampling_2s.mp4)
- [近景0.75秒](Docs/Evidence/M1/Sampling19/19_Sampling_045.png)／[固定カメラ対照](Docs/Evidence/M1/Sampling19/19_fixed_083.png)／[2秒終端](Docs/Evidence/M1/Sampling19/19_Sampling_120.png)
- [18のABC/VAT実深度](Docs/Evidence/M1/Sampling19/19_depth_000_L.png)／[床への落影](Docs/Evidence/M1/Sampling19/19_shadow_024_L.png)／[VAT表面への受影対照](Docs/Evidence/M1/Sampling19/19_receive_000_L.png)
- [数値・限界・再現方法](Docs/Progress/Step_19_ja.md)／[Houdini元計算](Houdini/Sampling19/README_ja.md)

新しい60Hzの実121時刻から偶数61時刻を30Hzへ抽出し、同じ動きを比較しました。深度・影は18の正式24Hz VAT/ABCへ新shaderを適用した別試験です。小さな2球の技術試料であり、北斎の巻き波・波頭や白波の尖端・HMDの滑らかさを検証したとは扱いません。記録60fpsは性能値ではありません。

本機の実行一式は `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Sampling19\`。`GreatWave19.exe`を起動し、1で30Hz、2で60Hz、Space停止・再開、R先頭、Q終了。配布はフォルダー全体が必要です。物理キー操作は利用者確認待ち。

## 18の2方式比較を見る

- [Alembic／Fluid VATの左右比較・2秒動画](Docs/Evidence/M1/Playback18/18_Comparison_2s.mp4)
- [初期2球](Docs/Evidence/M1/Playback18/18_Comparison_000.png)／[結合](Docs/Evidence/M1/Playback18/18_Comparison_003.png)／[分離](Docs/Evidence/M1/Playback18/18_Comparison_024.png)／[2秒末端](Docs/Evidence/M1/Playback18/18_Comparison_048.png)
- [数値・性能・容量・再現方法・制限](Docs/Progress/Step_18_ja.md)／[Houdini出力と専用デコーダーの出典](Houdini/PlaybackComparison18/README_ja.md)

実Windowsビルドの同じ視点によるオフスクリーン描画です。元の三角化面との位置差は両方式0m、法線角差はVATで最大約0.028°でした。これは小さな技術試料の転送検査で、北斎の砕波・物理精度・HMDの合格ではありません。18当時は方式を採用せず、20で独立ロード・メモリを追加してPC制作経路を暫定判断しました。GPU時間と最終VR採用は引き続き保留です。

本機の実行一式は `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\Playback18\`。`GreatWave18.exe`を起動し、1でAlembic、2でVAT、Spaceで停止・再開、Rで先頭、Qで終了。配布にはフォルダー全体が必要です。

## 17の小さな流体試料を見る

- [Houdini実ビューポートの2秒動画](Houdini/VariableTopology17/Evidence/17_FLIP_Surface_2s.mp4)
- [粒子と表面の同時刻比較・全数値・限界](Docs/Progress/Step_17_ja.md)
- [生成元・キャッシュ・再現方法](Houdini/VariableTopology17/README_ja.md)

2球からの結合と、その後の分離を実FLIPの粒子ID・連結成分で確認しました。0〜2秒の49時刻はすべて異なる表面トポロジーです。後半は領域外への流出があり、面化体積も大きく増えるため、質量保存・海洋物理精度の合格ではありません。利用者の続行指示を受け、同じ試料を上記18の形式比較へ渡しました。

## M1の静止構図を見る

- [修正01：20秒の自動カメラ動画](Docs/Evidence/M1/Revision01/M1_Revision01_Walkthrough.mp4)
- [原画比較](Docs/Evidence/M1/Revision01/M1_Comparison.png)／[船上](Docs/Evidence/M1/Revision01/M1_Boat.png)／[側面](Docs/Evidence/M1/Revision01/M1_Side.png)／[背面](Docs/Evidence/M1/Revision01/M1_Rear.png)／[候補範囲図](Docs/Evidence/M1/Revision01/M1_Region.png)
- [修正前後・結果・再現方法](Docs/Progress/Step_15_Revision01_ja.md)／[修正前の15を保存した記録](Docs/Progress/Step_15_ja.md)

![M1の構図修正01・Unity実描画](Docs/Evidence/M1/Revision01/M1_Comparison.png)

波・船・富士・白波は新しく作った3Dの形状模型です。画像はUnity実行ビルドのオフスクリーン描画で、流体シミュレーション、完成版の浮世絵レンダリング、HMD映像ではありません。波と船は静止しています。動画の24fpsは再生用の値で、実時間性能の測定ではありません。

本機の実行ファイル：`G:\Unity\GreatWave_2026_Fresh\Unity\Builds\M1_Revision01\GreatWaveM1Revision01.exe`。移す場合は `M1_Revision01/` 一式が必要です。1〜5で視点を切替、右ドラッグ・矢印で見回し、Rで戻す、Spaceで停止、Qで終了します。通常のウィンドウと物理キー・マウス操作は利用者確認待ち。 [ビルド](Tools/Build_M1_Revision01.ps1)／[画像・動画の再取得](Tools/Capture_M1_Revision01.ps1)。

## 16のHoudini→Unity受け渡しを見る

- [Unityの2秒動画](Docs/Evidence/M1/FixedTopology16/16_Unity_Cache.mp4)／[静止画](Docs/Evidence/M1/FixedTopology16/16_Unity_Middle.png)
- [Houdini実ビューポートの2秒動画](Houdini/FixedTopology16/Evidence/fixed_topology_16_houdini_preview.mp4)
- [結果・数値・起動方法・保留項目](Docs/Progress/Step_16_ja.md)

実行中のSteam Houdini22.0.429へMCPで接続し、新規の変形格子をAlembicへ書き出しました。Unity EditorとWindows実行版で61時刻と60個の補間点を照合しました。解析式の検査用形状で、流体ではありません。通常起動は2秒で停止し、Rで再生、Spaceで停止・再開、Qで終了。本機の実行ファイルは `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\FixedTopology16\GreatWave16.exe`。移す場合はフォルダー全体が必要です。

既存HIPを保存・読み直さず、所有ノードだけのCPIOを保存・再読込しました。UIと所有ノードの復元を確認し、変更済みフラグとUndo履歴は保持しています。.hiplcの再起動・再読込、HMD、物理キー操作は未検証。17〜20の実流体・転送・時間密度・PC暫定判断は上記の独立記録へ進み、HMDと最終VR採用は保留しています。

## M0の基礎検証記録

- [20秒の確認動画](Docs/Evidence/M0/M0_Desktop_Walkthrough.mp4)
- [着座視点](Docs/Evidence/M0/M0_Seated.png)／[静止船全体](Docs/Evidence/M0/M0_Boat_Exterior.png)／[1m・軸の校正モデル](Docs/Evidence/M0/M0_Calibration.png)
- [結果・操作・再現方法・保留項目](Docs/Progress/Step_10_ja.md)

M0の画像・動画は新規Windows実行版の実シーンを、Unityでオフスクリーン描画した自動カメラ記録です。通常ウィンドウの手動操作やHMDの録画ではありません。平面と箱形の静止船を使った当時の基礎検証を保存しています。

本機の実行ファイルは `G:\Unity\GreatWave_2026_Fresh\Unity\Builds\M0\GreatWaveM0.exe`。右ドラッグ・矢印で見回し、Rで戻る、Spaceで停止・再開、Qで終了します。通常画面での物理キー・マウス操作は利用者の確認待ちです。実行一式はGit対象外で、[ビルド](Tools/Build_M0.ps1)と[証拠の再取得](Tools/Capture_M0.ps1)の手順を保存しています。

## 制作設計

- [制作依頼のプロンプト（原文）](Docs/Design/Original_Request_ja.md)
- [制作設計書：12段階・60ステップ](Docs/Design/GreatWave_VR_Production_Design_ja.md)

設計書には、Houdiniによる波浪の計算とサーフェス化、白波の別計算とモデルアニメーション、Blenderによる船などの制作、Unityでの浮世絵表現・HMD体験・操船を記載しています。各ステップの成果物と確認事項、各段階の合格条件、物理・美術・性能の評価方法をまとめています。

- [制作手順・役割・確認条件](Docs/Workflow/Production_Workflow_ja.md)
- [番号ごとの進捗](Docs/Progress/README.md)

## フォルダー構成

| フォルダー | 用途 |
| --- | --- |
| `Houdini/` | 波浪の流体シミュレーションとサーフェス化 |
| `Blender/` | 船などの静的モデルの制作 |
| `Whitewater/` | 白波の別計算とアニメーション |
| `Unity/` | リアルタイム表示、HMD体験、船の操作の統合 |
| `Docs/` | 設計と各段階の確認記録 |

完成点ごとに実際の結果を保存し、代理による番号別の独立確認後に次の工程へ進みます。利用者の毎回の返答を待つ条件は最新指示で解除されました。HMD実機の必須試験は保留一覧に残しています。
