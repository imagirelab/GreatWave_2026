# 第1段階記録：輪郭マスクと断面測定ライブラリ（2026-09-20）

> この文書は当時の中国語記録を日本語で整理したものです。元の全文は変更前のコミット 0b0178eb9ea6b99ff685d608d557e49068066bb8 で確認できます。数値と判断は当時の記録であり、現在の成果を再検証した結果ではありません。

実装は src/gw/raster.py、src/gw/silhouette.py、src/gw/profile_metrics.py。定義は docs/measurement_definitions.md、再検証は tools/run_blender.ps1 に tests/selftest_measure.py を渡す。入力の合成波は tests/fixtures/make_synthetic_wave.py。出力と図は results/step1_prepare/measure/、自己検証の数値は selftest_measure_report.json にある。

raster.py は三角形の画素中心被覆、サブピクセル境界の交点、静水面下の充填、輪郭成分と穴の検出を実装した。silhouette.py は評価網目を CAM_print または任意の画角範囲へ正射影し、順序付き輪郭を抽出する。profile_metrics.py は波頂・先端・最深点、背・波頭・内側の弧の分段、S4・S7・S8、位置差、各フレームの h・x_c・θ・o・φと輪郭移動量を測る。基準輪郭とモデルを同じ定義で計測することを目的とした。

当時の初期実装の自己検証は52項目だった。後の先端規則修正で63項目、測定層の強化後は88項目・失敗0になったため、この文書の数値を現在の最終自己検証件数として扱わない。数値的な測定誤差、Cyclesとマスクの比較、速度の元表は変更前コミットと results/step1_prepare/measure/selftest_measure_report.json を参照する。

重要な限界は、開いた薄片網目を正面から見ると面積が消えること、静水面以下は輪郭として見えないこと、波頭先端や谷の分段が手描きの泡の小片に左右されること。これらを補う有効性検査と報告専用指標は後の docs/records/step1_libfix.md、step1_harden_measure.md、step1_harden_tests.md に記録した。
