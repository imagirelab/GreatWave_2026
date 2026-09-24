# 11：厚みを持つ静止の大波

日付：2026-09-24。結果：新規Blender形状の作成・FBX出力・Unityでの寸法確認と初期描画を完了。流体計算はしていない。

[生成手順](../../Blender/M1_Composition/generate_wave.py) は空シーンから閉じた波形を作る。断面の弧に厚みを与え、奥行きに沿って高さ・張り出し・位置を変えている。同じ断面を単に押し出した板ではない。頂点4,066、面4,064、非多様体辺0。閉領域の体積は形状検査の数値であり、海水の体積収支の実証ではない。

制作元：`Blender/M1_Composition/M1_Wave_Static.blend`、出力：`wave_static.fbx`。この形状は、今回選んだMetの原画を観察して作った静止の構図模型で、物理的に正しい巻き波という主張はしない。

Unityの新しい `M1_StaticComposition.unity` に読み込み、実境界は約35.44×21.65×20.00m。Blenderの期待する軸変換後の境界と±0.001m以内で一致した。材質は名前に対応する藍・青の単純な色面で、完成版の浮世絵シェーダーではない。

- [Blender形状検査](../../Blender/M1_Composition/11_blender_geometry.json)
- [Unity実測](../Evidence/M1/11_unity_geometry.json)
- [初期のUnity実描画](../Evidence/M1/11_wave_early.png)

画像はUnity Editorのカメラから1280×720でオフスクリーン描画した。まだ船・富士・白波を配置していない。M0のシーンと証拠は変更していない。視点の最終評価は12〜14で行う。
