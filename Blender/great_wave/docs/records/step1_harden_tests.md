# 第1段階記録：試験枠組みの強化（2026-09-20）

> この文書は当時の中国語記録を日本語で整理したものです。元の全文は変更前のコミット 0b0178eb9ea6b99ff685d608d557e49068066bb8 で確認できます。数値と判断は当時の記録であり、現在の成果を再検証した結果ではありません。

対象は tests/common_test.py、test_shape.py、test_motion.py、test_mesh.py、run_all.py、selfcheck_tests.py、thresholds.json の解釈設定と docs/tests_readme.md。元の35検査項目の閾値、比較方法、二段階、基準輪郭、カメラは変更していない。元の17組の自己検証の期待値と許容差も維持した。

## 修正した枠組み上の欠陥

検査0件の誤ったPASSを INCOMPLETE に変更。例外時は ERROR、終了コード2、旧結果を stale_ 名へ移し、未完了のRUNNING印を区別する。NaN／無限大の頂点、輪郭から離れた成分、静水面に届かない終幕などは INVALID とした。--set により判定に影響する設定を変更すると NON-DEFAULT SETTINGS を表示して終了コードを0にしない。--only・--skip・--cases の誤字は ERROR にする。S3は静水面基準に加え、モデル自身の谷基準でも判定した。当時、この二重判定の採用は利用者確認待ちだった。

当時の自己検証は元の17組＋新規21組＝**38組、不一致0**。測定層の自己検証は**88項目、失敗0**。正式輪郭を lift_clip で掃引して全分解能で再実行すると、旧実行と共通の55形状項目・7網目項目の数値と二段階判定はビット単位で同一だった。全体の形状結論は S4.flattens_towards_crest のため FAIL、網目結論は **G3＝14.84％ H（上限3％ H）** のため FAILのままだった。

## 残る見落とし

横幅+5％・高さ−1.9％の複合変形は判定項目を通り、報告専用の自身波高で規格化した量だけが約+8.1％と示した。S8の標本位相の間の17°折れは判定値13.96°になり、報告専用の窓角では16.61°だった。--object で指定されない物体は検査できず、名前を注意として列挙するだけである。これらは当時の試験の限界で、PASSだけから視覚的・研究的な正確さを保証できない。

証拠は results/step1_prepare/harden_tests/final_runs_stdout.txt、同フォルダの試験結果、results/20260920_110019_selfcheck/、docs/records/step1_proof.md にある。再実行は tools/run_blender.ps1 に tests/selfcheck_tests.py、test_shape.py、test_mesh.py などを渡す。
