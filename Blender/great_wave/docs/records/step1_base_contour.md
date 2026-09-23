# 第1段階記録：指状尺度の基準輪郭を決定（2026-09-20）

> この文書は当時の中国語記録を日本語で整理したものです。元の全文は変更前のコミット 0b0178eb9ea6b99ff685d608d557e49068066bb8 で確認できます。数値と判断は当時の記録であり、現在の成果を再検証した結果ではありません。

詳細な数値と判断箇所は docs/base_contour_report.md、再構築の根拠は src/contour/base_contour_params.json と results/step1_prepare/contour_final/metrics.json にある。

候補A（領域法）と候補B（輪郭追跡法）を比較し、可視部で差が画面高0.5％を超える4箇所と補完部1箇所を原画の拡大図で裁定した。可視部のA→B偏差（平均／95％／最大）は背0.010／0.022／0.127％、波頭0.169／0.963／1.128％、内側の弧0.070／0.299／0.901％。差の大きい箇所はすべてBを採った。背の左端は white_body_outline を暫定選択し、実線のない部分は可視縁を線幅8.84 pxだけ外側へ移して構築した。これは利用者確認待ちだった。

当時の出力は target/base_contour.json（その後 target/base_contour_finger_scale.json に移された）、target/base_contour_overlay.png、results/step1_prepare/contour_final/ の比較図・局所拡大図である。背／波頭／内側の弧の点数は880／594／1213。内側の弧の遮蔽補完部はS7から17.7％除外した。JSONの再生成を連続2回行い、当時のSHA-256は 85215972AF4CAC6D474E57FBB66145690A276611DC450345B385C2E5DF2A926B で一致した。

S1波頂は38.22／8.62％、S2最深点は39.56／46.92％、S5先端は(2226.5,785.1) px、S6爪を含む最右点は59.29／33.06％。谷の水位は遮蔽により**直接測定できず**、当時の Z＝0 を維持した。指状尺度の自身のS8は背23.0°、波頭86.3°、内側の弧66.7°で、15°制限を満たさない。S5の向きは定義により−45.8°、−36.8°、+5.4°と大きく異なった。この記録時点では大形尺度の作成、左端、S5の向き、谷水位が未決定だった。

再実行は tools/run_blender.ps1 に src/contour/build_base_contour.py を渡す。旧記録の G:/research/Wave Simulation パスは移転前のものである。候補の入力は target/candidates/a/ と target/candidates/b/、数値と図は results/step1_prepare/contour_final/。
