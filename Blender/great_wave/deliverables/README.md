# 大波の試作動画と Blender ファイル

## 現在の比較試作：利用者の参照模型を底稿にした前進波

**[波を追跡する視点](reference_actor_volume.mp4) ｜ [固定した視点](reference_actor_fixed.mp4)**

各450フレーム、30 fps、15秒。形成、前進、前側の唇の巻き下げ、低い波への移行を確認します。追跡視点は波と同速で移動する比較カメラで、固定した船上視点ではありません。

- [アニメーション内蔵の Blender ファイル](reference_actor_animated.blend)
- [高峰の比較画像](reference_actor_volume.png)
- [船上の高さからの比較画像](reference_actor_boat.png)
- [前側が巻き下がる比較画像](reference_actor_curl.png)

基礎造形は利用者提供の `wave_repair_zbrush2.obj` の派生です。新規に造形した作品とは扱いません。**完成品質には達していません。** 着水衝突や流体物理は未検証です。[出典・方法・確認範囲・課題](../docs/milestones/2026-09-24_reference_actor.md)を参照してください。

## 改訂試作：局所的な高峰と分岐白波

**[斜めから見る動画](localized_wave_volume.mp4) ｜ [原画方向から見る動画](localized_wave_print.mp4)**

動画は各345フレーム、30 fps、11.5秒です。約9.5秒で最終姿勢になり、その後2秒静止します。白波は独立した厚みのあるメッシュ、小滴は別のメッシュです。原画の画像投射は使っていません。

- [アニメーション内蔵の Blender ファイル](localized_wave_animated.blend)：外部 PC2 キャッシュは不要。1～345フレームのタイムラインで確認できます。
- [斜め視点の静止画](localized_wave_volume.png)
- [原画方向の静止画](localized_wave_print.png)

**この段階は未承認の造形試作です。** 白波の片状の重なり、広く均一な白い波冠、参考映像のような連続した波の通過などに改善が必要です。流体の物理的妥当性、Unity と HMD の動作は未検証です。[制作方法・確認結果・残る問題](../docs/milestones/2026-09-24_localized_wave_rebuild.md)を参照してください。

## 旧版との比較

- [旧版：原画視点の動画](great_wave_motion_print_reference.mp4)：原画の単一視点投射を使用。小舟も波面に映り込みます。
- [旧版：斜め視点の動画](great_wave_motion_3d.mp4)：幅方向へ同じ断面を展開した試作。波頭が梁状に見える問題があります。
- [旧版：原画視点の静止シーン](great_wave_final_print.blend)
- [旧版：斜め視点の静止シーン](great_wave_final_3d.blend)

旧版の動画は各173フレーム、15 fps、約11.53秒です。旧版の2つの `.blend` は第285フレームの静止メッシュで、動画のアニメーションは内蔵していません。旧版の点キャッシュを変更する場合は `src/gwave/build_great_wave.py` から再生成します。
