# 第1段階記録：背の左端の由来フラグを訂正（2026-09-20）

> この文書は当時の中国語記録を日本語で整理したものです。元の全文は変更前のコミット 0b0178eb9ea6b99ff685d608d557e49068066bb8 で確認できます。数値と判断は当時の記録であり、現在の成果を再検証した結果ではありません。

背の x約0～338 px は、原画で直接見える墨線の追跡ではなかった。可視の白い浪体の縁を外側へ8.84 px移して**構築**した区間が traced と誤表示されていたため、offset_from_visible_edge へ訂正した。指状尺度の claw_root_bridge にも、実際には爪根だけでなく円盤処理で変えた部分を含むという説明上の問題があった。大形ファイルの注記にも小さな不一致があった。

変更は点の位置を変えず、由来フラグ、保留事項、説明文、図の線種を直すものだった。target/base_contour.json、target/base_contour_finger_scale.json、変体など計10個のJSONについて、3段×px/H座標の**60配列すべてが変更前後でビット単位で同一**だった。in_S7、指状尺度からの偏差、地標座標も同じ。比較結果は results/step1_prepare/contour_flags/hashes_compare.json と json_key_diff.json に保存した。

指状尺度の背は traced 880点から traced 689点＋構築由来191点に、大形の背は traced 739点＋正則化区間129点から traced 631点＋構築由来108点＋正則化区間129点に変わった。大形では最初の83点は正則化区間に属するため、新フラグよりそれを優先した。ユーザーの確認が必要な back_left_variant を pending_user_confirmation に加えた。

再構築は tools/run_blender.ps1 に src/contour/build_base_contour.py、続いて src/contour/build_large_form.py を渡す。当時、後半3回の実行では対象JSON 10件のSHA-256が同じだった。読み込み確認は results/step1_prepare/contour_flags/loader_check.json、形状試験の再実行は同フォルダの runs/shape_official_large_form にある。由来表示の修正は、左端の**形状解釈が正しいと確認されたことを意味しない**。
