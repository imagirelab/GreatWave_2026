# 第19号：Built-inの変形・深度・影の準備

新規シェーダー4ファイルを19専用シーンへ統合した。18のソース・証拠は変更していない。単独コンパイル28経路の記録と、[Windows実描画の色・深度・影検査](../../Docs/Progress/Step_19_ja.md)を区別して保存する。

## 配置と呼出契約

次の4ファイルを `Unity/Assets/GreatWave/Shaders/Sampling19/` へ同じ位置関係で配置する。

- `Sampling19VAT.shader`：`GreatWave/Sampling19/VAT HDR Shadow`
- `Sampling19Reference.shader`：`GreatWave/Sampling19/Reference Shadow`
- `Sampling19Surface.cginc`：両シェーダーの頂点処理・照明・ShadowCaster の共通実装
- `Sampling19DepthView.shader`：`Hidden/GreatWave/Sampling19/Depth View`

VAT のみ、既存の `../Playback18/Playback18VAT.cginc` を読み取り依存にする。複製・修正はしない。出典とライセンスは18の記録を継承する。依存ファイルの実 SHA-256 は `Evidence/19_shader_compile.json` に保存した。統合先はこの依存を含むソース集合を記録すること。

`Playback18VAT.Bind(material, data, frameIndex)` と `SetFrame` はシェーダー名を検査・変更しないため、新しい19号材質にも使える。既存の `_Vat*` 名・HDRデータ・整数フレームを維持する。フレームはカメラ描画の前に設定し、色・深度・影の間で変更しない。`_Color` と `_Ambient` を設定する。`_LightDirection` は19号では使わず、Unity の実際の主指向性ライトを参照する。

照明は主指向性ライト1灯の Lambert 項と `_Ambient` の固定環境項だけを使う。VATと通常メッシュに同じ計算を適用する。追加ライト、ライトマップ、GI、透過水、屈折、DepthNormals、MotionVectors、物理コライダーの変形は今回の実装範囲ではない。影の描画が成立しても、水の光学・浮世絵表現の完成を意味しない。

両シェーダーは `Cull Back`、不透明、ZWrite有効。VATの色と ShadowCaster は同じ `Sampling19Deform` から位置・法線を得る。ShadowCaster はその後 Unity の影バイアスを適用する。GPU変形前のCPU境界で消えないよう、主担当は18で実証した全時刻境界を継承し、Renderer の影設定とライト/QualitySettings の実値を保存する。動的バッチングでローカル頂点の意味が変わらないよう `DisableBatching=True` を指定した。

## 深度の表示と数値読戻し

透視カメラで `depthTextureMode = DepthTextureMode.Depth` を指定する。まずMSAA無しで確認する。同じカメラの`OnRenderImage`内で色RTを `Graphics.Blit` のsourceに渡し、モード別の独立材質で3つの専用RTへ出力する。Camera.Render復帰後は専用RTだけを読み、カメラ依存のglobalを後読みしない。最初の後読み方式はNaNで不採用になった。`_CameraDepthTexture` は直近のカメラ依存であり、後から二眼分をまとめて読む方法では片眼を取り違える可能性がある。

`_DepthMode` は Integer のため `Material.SetInteger` で設定する。

| 値 | 出力 |
|---|---|
| 0 | `_DepthRange.x/y` の眼奥行き範囲を近白・遠黒に表示 |
| 1 | 眼奥行きメートルをRGBへ出力。ARGBFloat・linearのRTで読む |
| 2 | 生の深度値をRGBへ出力。反転Zを含むAPI依存値 |

眼奥行きはカメラ空間の前方向距離であり、カメラからのユークリッド距離ではない。空の背景は far plane 付近になる。`LinearEyeDepth` を使う透視投影専用の準備であり、正投影、MSAA、HMDでの上下・array sliceは未検証。色画像と深度画像の同じ画素が同じ向きで対応することを実画像で検査する。

## 必要な統合検証

1. Unityで全3シェーダーの取込エラーと実ビルド結果を確認する。単独コンパイル結果だけで合格にしない。
2. 18の対応するABCとVATを同じ離散時刻、変換、カメラ、材質色、ライト条件で比較する。変形の異なる複数時刻で色の輪郭、眼奥行き、影の移動を記録する。元の静的FBXの影が残る状態を見逃さない。
3. 床へ落ちる影をライトの影ON/OFFで確認し、VATが別物体の影を受けることも遮蔽物ON/OFFで確認する。自己遮蔽だけで受影の検証を代用しない。
4. 深度は境界画素のラスタライズ差を別扱いとし、内側の共通画素について誤差統計を保存する。完全に消えた形状を共通画素だけの比較で通さないよう、可視マスクの被覆率・輪郭・前景画素数も確認する。影バイアスがあるため色と影の全画素完全一致を要求しない。
5. PC上の左右カメラには同じフレームを設定する。これは二視点の整合試験であり、OpenXRの実際の両眼配送や頭部追跡を実証しない。

30/60Hzの密度試験と、本シェーダーによる18の24Hz VATの影・深度試験を区別する。24Hzの既存VATを60Hzで繰り返して描画しても、新しい60Hzの流体標本を作ったことにはならない。

## 単独検査で確認した範囲

独立制作時の`validate_compile.py` は `E:/6000.4.3f1/Editor/Data/Resources/CGIncludes` の実ファイルを読み、Windows `d3dcompiler_47.dll` の D3DCompile を使う。Unityを起動しない。Built-inの旧 sampler 宣言に合わせてバックワード互換オプションを指定する。

Forward無影/画面空間影、ShadowCaster、Depthの各vertex/fragmentについて、通常条件と `STEREO_INSTANCING_ON` 条件の計28経路がコンパイル成功、警告0。ソース、依存include、コンパイル対象のハッシュはJSONにある。これはUnityのShaderLab取込・variant選択・描画資源・実VAT画像を検査しておらず、DXCや他APIの全経路の保証でもない。

SPI用のinstance/eye index初期化と、深度texture array用のUnityマクロを用意した。現時点ではHMDが無いので、実眼への配送、追跡、遅延、再投影、快適性、HMDでの性能は保留する。

## 公式資料からの第19号の判定条件

- [DOP Network](https://www.sidefx.com/docs/houdini/nodes/obj/dopnet.html)：計算刻みをフレーム時間以外にも設定できる。表示補間は計算済み前後状態の近似、補間無効時は近い計算状態になる。したがって60Hzの採取時刻を1/120秒の実計算境界へ揃え、substep cacheと時刻を確認する。これは今回の検証方針であり、実測結果は主担当が保存する。
- [DopSimulation](https://www.sidefx.com/docs/houdini/hom/hou/DopSimulation.html) と [SopNode](https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html)：`geometryAtFrame` は指定フレームでのcookを要求する。DOPのメソッドはcurrent frameのデータを暗黙に使うため、時刻を計測するコンテキストの一致が必要。
- [SOP FLIP Solver](https://www.sidefx.com/docs/houdini/nodes/sop/flipsolver.html)：Global/Min/Max Substepsは計算刻みの設定であり、保存頻度とは別。新しい密な1本の計算から偶数標本を30Hzへ使うことで、計算条件を共通にした密度比較になる。
- [File Cache](https://www.sidefx.com/docs/houdini/nodes/sop/filecache.html)：範囲・増分に小数を使える。小数時刻の保存名は整数フレームへの丸めや上書きを防ぐ必要がある。連番indexと秒時刻の対応を別途保存する。
- [Built-inの深度](https://docs.unity3d.com/6000.0/Documentation/Manual/SL-CameraDepthTexture.html)：通常のZ書込みとCameraDepthTextureは同義ではなく、後者はShadowCaster経路を使用する。今回のデコード共有はこの差に対応する。DepthNormalsへの対応までは主張しない。
- [影を受ける処理](https://docs.unity3d.com/6000.0/Documentation/Manual/built-in-shader-examples-receive-shadows.html) と [影を落とす処理](https://docs.unity3d.com/6000.0/Documentation/Manual/built-in-shader-examples-shadow-casting.html)：ForwardBase/AutoLightと、頂点変形を反映するShadowCasterを用いる。既存の静的ShadowCasterをそのまま借用する方法はVATに適用しない。
- [Single-pass instancing](https://docs.unity3d.com/6000.0/Documentation/Manual/SinglePassInstancing.html)：目のindexを正しく引き継ぐマクロが必要。コンパイル準備だけでは両眼実機確認にならない。
- [OpenXR 1.16のMock Environment](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/mock-environment.html)：低水準試験用で、対話的な物理XR機器の代替ではない。
- [OpenXR 1.16の設定](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/project-configuration.html)：depth submissionはruntimeと対応拡張に依存する。PCのCameraDepthTextureの一致は、HMDへのdepth submission成功とは別の判定である。

## 最終PC描画結果

Unity6000.4.3f1／Windows Mono／D3D11の同じビルドで、18の24Hz ABC/VATについて0・1・2秒×人工左右2視点を採録した。OnRenderImageのcallback、生深度/眼奥行きfinite、ABC/VAT深度差0m、流体本体を非表示にした床への落影を確認した。初回の描画後global読出しはNaNで棄却した。

別のShadowOnly cubeによる流体への受影は0秒の両視点で確認。流体mask内の暗化は左5,707／右5,735画素、ABC/VAT各々同数、ON/OFF深度差0m。全受影画素の色一致までは主張しない。1・2秒で同じ受影試験は未実施。実画像・全報告・保持事項は[Step19](../../Docs/Progress/Step_19_ja.md)を参照。
