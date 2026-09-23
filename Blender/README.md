# Blender — 大波のアニメーションと静的モデル

`great_wave/` には、画面内で最も大きな波のパラメーターによる造形、アニメーション、計測テストを収録しています。現行の波面は、曲線で制御した頂点数固定のモデルです。動きと原画視点での最終フレームの輪郭を検証するための試作であり、Houdini による流体シミュレーションではありません。独立した白波・波の先端部も Blender で試作しています。

[原画視点の動画](great_wave/deliverables/great_wave_motion_print_reference.mp4)と[斜め視点の動画](great_wave/deliverables/great_wave_motion_3d.mp4)を公開しています。直接開ける静止画用 `.blend` も `great_wave/deliverables/` にあります。生成したアニメーション用 `.blend`、PC2 キャッシュ、レンダリング結果は再生成可能なため、原則として Git に含めません。動画の再生条件、再生成方法、未解決の検証項目は [大波試作の説明](great_wave/README.md) を参照してください。

船、櫂などの静的モデルは、今後 `Blender/` 内の別ディレクトリで制作する予定です。現時点ではまだありません。
