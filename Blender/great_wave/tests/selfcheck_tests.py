"""S／M／G 検査の自己確認。故障注入で検出能力を検証する。

合成波とその解析輪郭を無改変で構築し、次に意図した欠陥を加える。
無改変は PASS、欠陥を加えた場合は事前に指定した項目が失敗する必要がある。

  blender --background --factory-startup --python-exit-code 1 --python tests/selfcheck_tests.py -- [--cases a,b,...] [--quick]
直接起動では --python-exit-code 1 が必須。--cases の未知の名前はエラー、終了コード2。

期待値は初回実行より前に定義した。exact は失敗集合の完全一致、analytic は断面折線の独立判定との一致、
at_least は必須失敗項目の包含を求める。

2026-09-20の監査後に追加した HARDEN_CASES の期待値も初回実行前に記録した。
原版の控えは results/step1_prepare/harden_tests/expectations_before_first_run/ にある。
harden は正式輪郭への故障注入、subprocess は別のBlenderプロセスで終了コードや結果ファイルを検証する。
元の期待値、許容差、閾値は変更していない。

このファイルは単独試験用の構築スクリプトとしても使える。
  --build-script tests/selfcheck_tests.py --build-func build_case --build-arg case=hem_lift_2pctH
  --build-script tests/selfcheck_tests.py --build-func build_attack_case --build-arg attack=wide_low:5:1.9

出力：results/<YYYYMMDD_HHMMSS>_selfcheck/ に selfcheck_report.json、selfcheck_table.md と
各事例・各試験の数値・画像を保存する。
"""
import argparse
import math
import os
import subprocess
import sys
import traceback

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "fixtures")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common_test as ct  # noqa: E402
from common_test import bootstrap, paths, pm, log  # noqa: E402
import make_synthetic_wave as msw  # noqa: E402

PCT = 100.0 / 66.0 / 100.0            # 画像高さ 1 % を H 単位に換算
N_SHORT, N_LONG = 31, 121             # 形状・網目は短い系列、動作は長い系列を使う
JUMP_FRAME = 40

# ------------------------------------------------------------------------------------ 検査事例
# tests は実行対象。期待値は spec 階層を基準とし、relaxed は user_relaxed_5pct 階層の値
# （None なら spec と同じ）。しきい値のない報告専用値は失敗集合と別に検査する。
# expect_W の factor=k は、波頂の鉛直線 X=0 を中心に X を k 倍する操作。断面幅、前後の距離、
# 張り出し o、空洞深さは、網目・シルエット経由でも単一断面でも (k-1)×100 % ± W_TOL_PCT となる。
# 面積は 0 超、(k-1)×100 % 未満だけ増える。波頂より左側が画面端で切られるため。
# k=1 なら全値が ±W_TOL_PCT 内。expect_report は旧定義に沿う動作の報告専用値。
W_KEYS_EXACT = ("z75.width_full_H", "z75.front_from_crest_H", "z75.back_from_crest_H", "z50.back_from_crest_H", "o_H", "cavity_depth_H")
W_KEY_AREA = "area_above_still_water_H2"
W_TOL_PCT = 0.3                       # 百分率点。測定誤差は画像高さの 0.016 %、o の 0.07 %

CASES = [
    {"name": "baseline", "n_frames": N_LONG, "defect": "欠陥なし（無改変の合成波、121フレーム）",
     # 無改変の系列：動作が滑らかなので d(k) は隣接値の中央値の 3 倍以下。
     # シェイプキーは最終姿勢を保つので、10 秒の保持中に動かない。
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.0},
                         "expect_verdict": {"spec": "PASS", "user_relaxed_5pct": "PASS"}},
               "motion": {"mode": "exact", "must_fail": [],
                          "expect_report": {"M6.backlog_jump_ratio": ("<=", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}},
               "mesh": {"mode": "exact", "must_fail": []}}},
    # 最終フレームだけ、弧長の 6 % を標準偏差とする滑らかな変位で波頂の X を画像高さの 3 % 移す。
    # Z は不変。S7 の法線偏差は波頂付近で約 0.8 % 以下なので、1 %／2 % の範囲に収まる。
    # 20260920_064705 の実測：+3 % 例の S1.dx は網目経由 2.43 %、単一断面 3.08 %。
    # clip の先細りが最深点 X=0.0178 H で X を制限し、移動した波頂 X=0.045 H より左にある。
    # 終端行の合成シルエットは頂部を左に広げる。単一断面の予測はこの合成を含まない。
    # 後から追加した -3 % 例では波頂を制限線から遠ざける。
    {"name": "crest_shift_x_3pct", "n_frames": N_SHORT, "defect": "波頂をX方向へ画面高の+3％だけ滑らかに局所移動",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dx_pct_h"], "relaxed": []}}},
    {"name": "crest_shift_x_minus3pct", "n_frames": N_SHORT, "defect": "波頂をX方向へ画面高の−3％だけ滑らかに局所移動",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dx_pct_h"], "relaxed": []}}},
    # 波頂を標準偏差 6 % のガウス変位で画像高さの 3 % 持ち上げる。S1.dz と S3 は +3 %。
    # 波背・頭部の 5 % 超の標本が 2 % 超ずれるため、S7 の p95 も失敗する予測。
    {"name": "crest_raise_z_3pct", "n_frames": N_SHORT, "defect": "波頂を画面高の+3％だけ滑らかに持ち上げる",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dz_pct_h", "S3.height_err_pct_h"], "relaxed": []}}},
    # 全フレームで波頂の鉛直線を中心に X を拡大。5 % 拡大時の波背法線偏差は約 0.5～1.2 %、
    # 平均約 0.8 % と見積もるため、S7 の失敗は予想しない。厳密な期待値は解析的予測による。
    {"name": "widen_x_5pct", "n_frames": N_SHORT, "defect": "波頂の鉛直線を基準に断面をX方向へ5％拡大",
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.05}}}},
    # 2026-09-20 に報告専用の幅指標を追加。20260920_065550 の 1.08 倍実測では
    # S7 波背平均が 1.19 % > 1 %。5 % 階層は失敗しないが、W は +8 % を示すはず。
    {"name": "widen_x_8pct", "n_frames": N_SHORT, "defect": "波頂の鉛直線を基準に断面をX方向へ8％拡大",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S7.back.mean_dev_pct_h"], "relaxed": [], "expect_W": {"factor": 1.08}}}},
    {"name": "widen_x_10pct", "n_frames": N_SHORT, "defect": "波頂の鉛直線を基準に断面をX方向へ10％拡大",
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.10}}}},
    # 最終フレームの波背 47 度の直線部に、最大高 1.2 %、半幅 3 標本（画面高 2.3 %）の山形折れを置く。
    # 接線は約 27／55／27 度回り S8 が失敗。最大傾斜の後に約 27 度緩んで再び急になるので S4 も失敗。
    # 高さは 2 % 未満で局所的なため、S7 は失敗しない予測。
    {"name": "back_kink", "n_frames": N_SHORT, "defect": "背に高さ1.2％・幅4.6％の折れを挿入",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S8.max_tangent_diff_deg", "S4.flattens_towards_crest"], "relaxed": None}}},
    # 全 121 フレームのうち 40 のみ全網目を X に +0.3 H 動かし、41 で戻す。Z は不変で h・theta は同じ。
    # 39→40 と 40→41 の跳躍は各約 0.3 H、周辺は数 1e-3 H。前後 2 対の中央値でも比は 3 を大幅に超える。
    {"name": "frame_jump", "n_frames": N_LONG, "defect": "フレーム%dだけ波全体をX方向へ0.3 H移動" % JUMP_FRAME,
     "tests": {"motion": {"mode": "exact", "must_fail": ["M6.jump_ratio"], "relaxed": None,
                          "expect_report": {"M6.backlog_jump_ratio": (">", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}}}},
    # 動作を t=0.9 で打ち切り、巻き込み中の移動状態から突然停止する。
    # 打ち切りは旧 M6 の除外窓内にあるため比は 3 以下。以後シェイプキーは姿勢を保持する。
    {"name": "abrupt_stop", "n_frames": N_LONG, "defect": "運動の90％でアニメーションを切り、動いている途中で停止",
     "tests": {"motion": {"mode": "exact", "must_fail": ["M5.stop_speed_ratio"], "relaxed": None,
                          "expect_report": {"M6.backlog_jump_ratio": ("<=", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}}}},
    # 全フレームの境界頂点を 0.02 H 持ち上げる。前面は持ち上げた終端列より前で水面に達するため、
    # CAM_print の輪郭指標には影響せず、G2 のみ失敗する予測。
    {"name": "hem_lift_2pctH", "n_frames": N_SHORT, "defect": "全フレームで網目境界の裾を波高の2％持ち上げる",
     "tests": {"mesh": {"mode": "exact", "must_fail": ["G2.hem_step_pct_H"], "relaxed": None}}},
    # 最終フレームで頭部上面の窪みを下面まで押し抜く。位置と深さは輪郭への射線検査で求め、
    # 深さは測定した頭部厚 +0.08 H。位相・裾・縁は不変で G4 のみ失敗する予測。
    # 初案の F2 中点・深さ固定 0.25 H は根元が実際には貫通せず、G4 は正しく 0 と報告した。
    # 期待値を変えず、故障注入の方を修正した。
    {"name": "self_fold", "n_frames": N_SHORT, "defect": "終幕で波頭上面を下面に貫通させる",
     "tests": {"mesh": {"mode": "exact", "must_fail": ["G4.n_self_intersections"], "relaxed": None}}},
    # 2026-09-20 追加。モデルは無改変、目標 JSON の頭部と内側弧の接合点だけを頭部上面に沿って
    # 40 標本（80 px＝画面高 3.1 %）戻す。輪郭形状自体は不変。
    # 検出された最右端の先端は JSON 接合点と 3.1 % 異なり、許容 0.2 % を超えるので INVALID を期待。
    # S5／S7 の失敗は異なる区間同士の比較に由来する副作用。
    {"name": "target_joint_shifted", "n_frames": N_SHORT, "contour_mod": "tip_joint_shift_40",
     "defect": "目標JSONの波頭／内側の弧の接合点を波頭上で3.1％移動（モデルは無改変）",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["VALIDITY"],
                         "expect_verdict": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}}}},
    # テスト用形状自身の失敗例（docs/measurement_definitions.md 第1.1節）
    {"name": "taper_zscale", "n_frames": N_SHORT, "taper": "zscale", "defect": "両端の断面が空洞を塞ぐ（taper = zscale）",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["S2.dist_pct_h", "S5.pos_pct_h", "S5.dir_deg", "S6.body_rightmost_left_pct",
                                                           "S7.head.mean_dev_pct_h", "S7.inner_arc.mean_dev_pct_h"]}}},
    {"name": "taper_none", "n_frames": N_SHORT, "taper": "none", "defect": "単純押し出しでは薄片の投影面積がない（taper = none）",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["VALIDITY"],
                         "expect_verdict": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}}}},
]
WIDEN_SWEEP = [1.02, 1.05, 1.08, 1.10, 1.12, 1.15, 1.20]

# ------------------------------------------------------------------------------------ 強化検査事例（2026-09-20）
# 期待値は各事例の初回実行前に、仕様 great_wave_blender_prompt.md、解析式、
# 測定記録 docs/records/step1_harden_measure.md から設定した。故障注入の原型は
# results/step1_prepare/verify_tests/scripts/attack_common.py にあり、必要部分を下へ移植した。
# 正式基準輪郭は自己比較でも S4.flattens_towards_crest に失敗する既知の性質がある
# （docs/records/step1_proof.md）。INHERITED はその継承失敗で、注入した欠陥の証拠ではない。
# verdict_base は階層別判定、must_fail／must_not_fail は仕様階層の検査 ID、
# failing_equals は厳密な失敗集合、values は実測値の比較、diff_pct は目標値からの差の範囲。
# validity_note_contains は有効性注記、vs_clean は無改変例との差、suffix は接尾辞の有無。
INHERITED = ["S4.flattens_towards_crest"]
HARDEN_CASES = [
    # 証明記録の無改変実行を再現。継承失敗のみで、分離成分や除外三角形はなく、前面は Z=0 に達する。
    # 正式輪郭の谷は Z=0 なので、モデルの谷から測る S3 は Z=0 から測る S3 と同じ。
    {"name": "official_clean", "kind": "harden", "test": "shape", "attack": "none",
     "defect": "欠陥なし。正式基準輪郭を lift_clip で掃引（故障注入の対照）",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "failing_equals": INHERITED, "suffix": False,
                "values": {"T.n_removed_islands": ("==", 0), "T.n_nonfinite_vertices": ("==", 0), "T.n_dropped_triangles": ("==", 0),
                           "T.reached_still_water": ("==", 1), "S3.from_model_trough.height_err_pct_h": ("between", -0.2, 0.2),
                           "S3.height_err_pct_h": ("between", -0.2, 0.2)},
                "diff_pct": {"W.own_h.aspect_ratio_h75": (-0.5, 0.5), "W.own_h.o_over_h": (-0.5, 0.5), "W.own_h.cavity_depth_over_h": (-0.5, 0.5)}}},
    # 当初の指摘「幅が広く、高さが足りない」を再現。X を 1.05 倍、波頂を画像高さの 1.9 % 下げる。
    # S1.dz／S3 は約 -1.87 %、頭部先端の移動も 1.9 % で、各 2 % の許容内。
    # 波背では拡幅と降下の法線方向が逆なので、判定対象の S7 も 1 %／2 % 内に収まる。
    # この見逃しには未指定の新しきい値が必要。報告専用の長さ／自己高さは解析式
    # 1.05／(1 - 1.9×0.0151515／1.0006) = 1.0811、約 +8.1 % を示す（特徴点雑音を見込む）。
    # 符号付き S7 は波背と頭部上面で負、空洞屋根と波腹で正。大きさは約 0.2～1.5 %。
    {"name": "wide_low_5_1p9", "kind": "harden", "test": "shape", "attack": "wide_low:5:1.9",
     "defect": "幅+5％かつ高さ−1.9％（縦横比+8％）。以前に指摘された問題",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "must_fail": INHERITED, "must_not_fail": ["VALIDITY"], "suffix": False,
                "values": {"S3.height_err_pct_h": ("between", -2.0, -1.7), "S3.from_model_trough.height_err_pct_h": ("between", -2.0, -1.7),
                           "S7.back.signed_mean_dev_pct_h": ("between", -1.5, -0.2), "S7.head.signed_mean_dev_pct_h": ("between", -1.5, -0.2),
                           "S7.inner_arc.signed_mean_dev_pct_h": ("between", 0.2, 1.5)},
                "diff_pct": {"W.own_h.aspect_ratio_h75": (7.0, 9.2), "W.own_h.o_over_h": (7.0, 9.4), "W.own_h.cavity_depth_over_h": (7.0, 9.2),
                             "W.own_h.h75.width_full_over_h": (7.0, 9.2)},
                "document": ["S7.back.mean_dev_pct_h", "S7.back.p95_dev_pct_h", "S7.head.mean_dev_pct_h", "S7.head.p95_dev_pct_h", "S5.pos_pct_h",
                             "S1.dz_pct_h", "W.z75.width_full_H"]}},
    # 第二物体 Floor で前方水面を Z=0 より画像高さの 3 % 高くする。谷から波頂の高さは
    # 仕様の 66 % に対し 63 %（許容 2 点）。前面が静水面に達しないため INVALID。
    # S3.from_model_trough は約 -2.97 % で仕様階層に失敗し、5 % 階層には合格。
    # Z=0 起点の S3 は +0.03 % 程度のまま。
    {"name": "floor_raised_3pct", "kind": "harden", "test": "shape", "attack": "none", "floor_pct": 3.0, "objects": "SweptAttack,Floor",
     "defect": "波の前方の海面を画面高の3％上げる（谷から波頂まで63％、指定は66％）",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY", "S3.from_model_trough.height_err_pct_h"],
                "must_not_fail": ["S3.height_err_pct_h"], "suffix": False, "validity_note_contains": ["前面が静水面へ届かない"],
                "values": {"S3.from_model_trough.height_err_pct_h": ("between", -3.15, -2.8), "S3.height_err_pct_h": ("between", -0.2, 0.2),
                           "T.reached_still_water": ("==", 0)}}},
    # 空洞入口に 0.13 H×0.15 H の分離四角形を置く。仕様第5節注2の空洞閉塞に当たるが、
    # 輪郭追跡は分離成分を除き、各 S 値は無改変例と同じになる。
    # INVALID とし、成分の範囲 X=0.17..0.30 H、Z=0.22..0.37 H を示す必要がある。
    {"name": "island_in_cavity", "kind": "harden", "test": "shape", "attack": "none", "island": 1, "objects": "SweptAttack,Island",
     "defect": "空洞内の離れた物体（輪郭追跡時に除かれる）",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["離れたシルエット成分", "X 0.17", "Z 0.22"],
                "values": {"T.n_removed_islands": ("==", 1)}}},
    # 最終シェイプキーの頂点一つを NaN にする。Blender は値を伝播し、ライブラリはその三角形を除く。
    # 指標は無改変例とビット単位で同じでも、shape・mesh とも INVALID が必要。
    {"name": "nan_vertex", "kind": "harden", "test": "shape", "attack": "none", "nan_vertex": 1,
     "defect": "終幕に NaN 頂点を1個挿入",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["有限でない幾何"],
                "values": {"T.n_nonfinite_vertices": ("==", 1), "T.n_dropped_triangles": (">=", 1)}}},
    {"name": "nan_vertex_mesh", "kind": "harden", "test": "mesh", "attack": "none", "nan_vertex": 1, "mesh_skip": ("G5",),
     "defect": "終幕に NaN 頂点を1個挿入。G5を省いても INVALID とする",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["有限でない幾何"], "values": {"T.n_frames_nonfinite_geometry": (">=", 1)}}},
    # 既知の限界。同じ分離物体を --object に含めないと、検査できず各 S 値と判定は無改変例と同じ。
    # ただし T.n_untested_mesh_objects=1 と物体名を報告し、読み手に未検査を知らせる。
    {"name": "island_not_listed", "kind": "harden", "test": "shape", "attack": "none", "island": 1,
     "defect": "--object に含めない空洞内の物体（既知の限界：報告のみ）",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "failing_equals": INHERITED, "suffix": False,
                "validity_note_contains": ["検査対象外: Island"], "values": {"T.n_untested_mesh_objects": ("==", 1), "T.n_removed_islands": ("==", 0)}}},
    # 波背の 17 度の折れを S8 の標本位相の間に置く。標本間隔 1 % の接線差は 15 度未満が仕様だが、
    # 弦による平滑化で 17×0.875=14.9 度となり、判定対象の S8 は失敗しない予測。
    # これは標本定義の既知の盲点。仕様の判定定義は変えない。報告専用の頂点窓転角は
    # 15.5 度以上、無改変例より 2.5 度以上大きいはず。
    {"name": "back_kink_17_worst", "kind": "harden", "test": "shape", "attack": "back_kink:17:worst",
     "defect": "S8の標本位相の間に17°の背の折れを置く",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "must_fail": INHERITED, "must_not_fail": ["VALIDITY"], "suffix": False,
                "values": {"S8.max_tangent_diff_deg": ("between", 12.0, 15.0), "S8.back.vertex_window_turn_deg": (">=", 15.5)},
                "vs_clean": {"S8.back.vertex_window_turn_deg": (">=", 2.5)},
                "document": ["S8.max_tangent_diff_deg", "S8.max_vertex_window_turn_deg", "S8.back.vertex_window_turn_deg", "S7.back.p95_dev_pct_h"]}},
    # 同じ二欠陥を motion 検査に通す。正式輪郭の 2 フレーム掃引と保持 3 フレームでは M 指標に意味がない。
    # 最終の NaN 頂点と全フレームの分離物体はいずれも INVALID とし、T.n_frames_* に数える。
    {"name": "nan_vertex_motion", "kind": "harden", "test": "motion", "attack": "none", "nan_vertex": 1, "extra_args": ["--backlog-hold-s", "0"],
     "defect": "終幕に NaN 頂点を1個挿入（運動検査）",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["有限でない幾何"], "values": {"T.n_frames_nonfinite_geometry": (">=", 1), "T.n_frames_with_islands": ("==", 0)}}},
    {"name": "island_motion", "kind": "harden", "test": "motion", "attack": "none", "island": 1, "objects": "SweptAttack,Island", "extra_args": ["--backlog-hold-s", "0"],
     "defect": "全フレームで波の前方に離れた物体を置く（運動検査）",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["離れたシルエット成分"], "values": {"T.n_frames_with_islands": (">=", 2), "T.n_frames_nonfinite_geometry": ("==", 0)}}},
    # 設定の抜け道。--set jump_floor_frac_of_vmax=1.0 で 0.3 H の跳躍が M6 を通過した。
    # 現在は両階層の判定に接尾辞を付け、変更源を記録し、終了コード 1 にする。
    # 元の判定が PASS になること自体がこの抜け道の再現。
    {"name": "settings_backdoor_frame_jump", "kind": "harden", "test": "motion", "fixture_case": "frame_jump", "n_frames": N_LONG,
     "extra_args": ["--set", "jump_floor_frac_of_vmax=1.0"],
     "defect": "--set jump_floor_frac_of_vmax=1.0 で0.3 Hの突跳を隠す",
     "expect": {"verdict_base": {"spec": "PASS", "user_relaxed_5pct": "PASS"}, "suffix": True, "exit_code_spec": 1,
                "non_default_names": ["jump_floor_frac_of_vmax"], "must_not_fail": ["M6.jump_ratio"]}},
    # --hold-frames 0 では停止後の不変性を測れず、NOT_MEASURABLE による FAIL が必要。
    # 標準設定との差には接尾辞を付ける。31 フレームの短い系列では M6 も失敗する既知の性質がある。
    {"name": "no_hold_frames", "kind": "harden", "test": "motion", "fixture_case": "baseline", "n_frames": N_SHORT, "extra_args": ["--hold-frames", "0"],
     "defect": "停止後の保持フレームなしで運動検査を実行",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "suffix": True, "exit_code_spec": 1,
                "not_measurable": ["M5.post_stop_max_disp_H"], "non_default_names": ["hold_frames"]}},
    # ---- Python 単体事例。初回の期待値写しの後に追加した。
    # PASS は判定済み検査が一つ以上あり、必要な全検査も判定済みの場合のみ。
    # 未判定は INCOMPLETE、NOT_MEASURABLE は失敗、有効性喪失は INVALID、例外は ERROR（終了 2）。
    # 判定に関わる設定変更は接尾辞と終了コード 1。表は unit_verdict_vocabulary() にある。
    {"name": "unit_verdict_vocabulary", "kind": "unit", "func": "unit_verdict_vocabulary", "defect": "手作成の検査一覧による総合判定と終了コードの確認",
     "expect": {}},
    # 未知の --set 名は ValueError。既定値は thresholds.json の interpretations と一致する。
    # 判定に関わる変更は出典付きで列挙し、報告専用値の変更は別に記録して判定には印を付けない。
    {"name": "unit_settings_audit", "kind": "unit", "func": "unit_settings_audit", "defect": "検査設定の取得と変更記録の確認", "expect": {}},
    # params.json は編集せず、事例の実行中だけ gw.paths.param を差し替える。
    # 判定関連値は出典「params.json test_settings」で列挙する。未知名・型違いは例外、項目の欠落は許容。
    {"name": "unit_settings_from_params_json", "kind": "unit", "func": "unit_settings_from_params_json",
     "defect": "params.json の test_settings を模擬し、既知名・未知名・型違いを確認", "expect": {}},
    # ---- 個別 Blender プロセスで終了コードとファイルを検証
    # G 検査を全部省けば判定済み 0 件で INCOMPLETE、終了コード 1。
    {"name": "zero_checks_mesh_skip_all", "kind": "subprocess", "script": "test_mesh.py", "defect": "全G検査を省き、判定項目を0件にする",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--skip", "G1,G2,G3,G4,G5"],
     "expect": {"exit_code": 1, "verdict_base": {"spec": "INCOMPLETE", "user_relaxed_5pct": "INCOMPLETE"}, "n_judged": 0, "running_marker": False}},
    # --only の誤記で対象が 0 件でも PASS にしない。
    {"name": "run_all_only_typo", "kind": "subprocess", "script": "run_all.py", "defect": "run_all --only shpae（指定名の誤記）",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--only", "shpae"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "ValueError", "running_marker": False}},
    {"name": "mesh_skip_unknown_name", "kind": "subprocess", "script": "test_mesh.py", "defect": "test_mesh --skip G9（未知の名前）",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--skip", "G9"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "ValueError", "running_marker": False}},
    # run_all の一検査で例外（--contour のファイル欠落）が起きても他の検査は続行。
    # shape と総合は ERROR、終了 2、RUNNING 印なし。shape 自身の metrics.json を残す。
    {"name": "run_all_subtest_crash", "kind": "subprocess", "script": "run_all.py", "defect": "形状検査が例外終了しても、他の検査を続行する",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--contour", "does_not_exist.json", "--skip", "G5"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "running_marker": False,
                "sub_test_verdict_base": {"shape": "ERROR"}, "sub_tests_present": ["shape", "motion", "mesh"]}},
    # 古い PASS が残る出力先で構築スクリプトを例外終了させる。終了 2、metrics.json はトレース付き ERROR。
    # 古いファイルは stale_* に改名し、RUNNING 印は残さない。
    # Blender の --python-exit-code 1 の有無で試し、guarded_main の終了値が同じことを確かめる。
    {"name": "crashing_build_script", "kind": "subprocess", "script": "test_shape.py", "defect": "構築スクリプトが例外終了し、結果フォルダに古いPASSが残る",
     "argv": ["--build-script", "{this}", "--build-func", "build_crash"], "seed_stale_pass": True,
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "RuntimeError",
                "error_message_contains": "意図的な例外", "running_marker": False, "stale_files": ["metrics.json", "summary.md"]}},
    {"name": "crashing_build_script_no_exit_code_flag", "kind": "subprocess", "script": "test_shape.py", "python_exit_code_flag": False,
     "defect": "同じ事例を --python-exit-code 1 なしで起動",
     "argv": ["--build-script", "{this}", "--build-func", "build_crash"], "seed_stale_pass": True,
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "RuntimeError",
                "error_message_contains": "意図的な例外", "running_marker": False, "stale_files": ["metrics.json", "summary.md"]}},
]


# ------------------------------------------------------------------------------------ 故障注入
def _arc_s(pts):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])))])


def perturb_profile(case, pts, ids, info, is_final):
    """H 単位の断面輪郭に故障を加え、点列と情報を返す。"""
    pts = pts.copy()
    info = dict(info)
    if case.startswith("widen_x_"):
        k = 1.0 + float(case.split("_")[2].replace("pct", "")) / 100.0
        pts[:, 0] *= k
        info["x_clip_target"] = info["x_clip_target"] * k
        return pts, info
    if case.startswith("widen_factor_"):
        k = float(case.split("_")[2])
        pts[:, 0] *= k
        info["x_clip_target"] = info["x_clip_target"] * k
        return pts, info
    if not is_final:
        return pts, info
    s = _arc_s(pts)
    i_c = int(np.argmax(pts[:, 1]))
    if case in ("crest_shift_x_3pct", "crest_shift_x_minus3pct"):
        sign = -1.0 if "minus" in case else 1.0
        pts[:, 0] += sign * 3.0 * PCT * np.exp(-0.5 * ((s - s[i_c]) / (6.0 * PCT)) ** 2)
    elif case == "crest_raise_z_3pct":
        w = np.exp(-0.5 * ((s - s[i_c]) / (6.0 * PCT)) ** 2)
        w[0] = w[-1] = 0.0
        pts[:, 1] += 3.0 * PCT * w
    elif case == "back_kink":
        idx = np.nonzero(ids == info["pieces"].index("B3"))[0]
        i0, hw = int(idx[len(idx) // 2]), 3
        t = pts[i0 + 1] - pts[i0 - 1]
        t /= math.hypot(t[0], t[1])
        nrm = np.array([-t[1], t[0]])                              # outward (up-left) normal of the back
        for i in range(i0 - hw, i0 + hw + 1):
            pts[i] += nrm * 1.2 * PCT * (1.0 - abs(i - i0) / float(hw))
    return pts, info


FOLD_MARGIN_H = 0.08


def _ray_thickness(pts, i, n_in, skip=5):
    """pts[i] から内向き法線 n_in に沿って後続の折線へ至る距離。
    交点がなければ None。表面の背後に別の面がなく、胴体内部が続く場合に当たる。"""
    best = None
    p = pts[i]
    for j in range(i + skip, len(pts) - 1):
        r, d2 = pts[j], pts[j + 1] - pts[j]
        den = n_in[0] * d2[1] - n_in[1] * d2[0]
        if abs(den) < 1e-15:
            continue
        t = ((r[0] - p[0]) * d2[1] - (r[1] - p[1]) * d2[0]) / den
        u = ((r[0] - p[0]) * n_in[1] - (r[1] - p[1]) * n_in[0]) / den
        if t > 1e-9 and 0.0 <= u <= 1.0 and (best is None or t < best):
            best = t
    return best


def fold_site(pts, ids, info):
    """self_fold を置く位置を、頭部上面 F2 のうち縁から最も遠く、内向き射線が
    0.10 H 内で下面に届く標本とする。初案の F2 中点・深さ 0.25 H は下面に届かず、
    G4 が正しく交差 0 と報告した（docs/records/step1_tests.md）。
    標本索引、内向き単位法線、測定した頭部厚を返す。"""
    idx = np.nonzero(ids == info["pieces"].index("F2"))[0]
    for iu in idx[2:-2]:
        t = pts[iu + 1] - pts[iu - 1]
        t = t / math.hypot(t[0], t[1])
        n_in = np.array([t[1], -t[0]])
        th = _ray_thickness(pts, int(iu), n_in)
        if th is not None and th <= 0.10:
            return int(iu), n_in, float(th)
    raise RuntimeError("self_fold: no top-side sample of the head has an underside within 0.10 H along its normal")


def make_wave_class(case):
    class PerturbedWave(msw.SyntheticWave):
        _case = case

        def _final(self):
            return msw.FRAME_START + self.n_frames - 1

        def profile(self, frame):
            t = msw.frame_to_t(frame, self.n_frames)
            if self._case == "abrupt_stop":
                t = 0.9 * t
            pts, ids, info = msw.profile_points(t)
            pts, info = perturb_profile(self._case, pts, ids, info, int(frame) == self._final())
            return pts, ids, info

        def vertices(self, frame):
            V = super().vertices(frame)
            H, n_u, n_v = self.H, self.n_u, self.n_v
            if self._case == "frame_jump" and int(frame) == JUMP_FRAME:
                V = V.copy()
                V[:, 0] += 0.3 * H
            elif self._case == "hem_lift_2pctH":
                G = V.reshape(n_v, n_u, 3).copy()
                border = np.zeros((n_v, n_u), bool)
                border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
                G[border, 2] += 0.02 * H
                V = G.reshape(-1, 3)
            elif self._case == "self_fold" and int(frame) == self._final():
                pts, _ids, _info = self.profile(frame)
                iu, n_in, thick = fold_site(pts, _ids, _info)
                wu = np.exp(-0.5 * ((np.arange(n_u) - iu) / 3.0) ** 2)
                wv = np.exp(-0.5 * ((np.arange(n_v) - n_v // 2) / 1.5) ** 2)
                amp = (thick + FOLD_MARGIN_H) * H * wv[:, None] * wu[None, :]
                G = V.reshape(n_v, n_u, 3).copy()
                G[:, :, 0] += amp * n_in[0]
                G[:, :, 2] += amp * n_in[1]
                V = G.reshape(-1, 3)
            return V

    return PerturbedWave


def build_case(scene, case="baseline", n_frames=N_SHORT, taper="clip", H=11.0):
    """common_test.py の構築規約に沿い、一欠陥を加えた合成テスト形状を作る。"""
    orig = msw.SyntheticWave
    msw.SyntheticWave = make_wave_class(case)
    try:
        obj, _sw = msw.build_object(scene, n_frames=int(n_frames), taper=taper, H=float(H), name="SyntheticWave")
    finally:
        msw.SyntheticWave = orig
    return obj


# ------------------------------------------------------------------------------------ hardening: attacks on the official contour
OFFICIAL_JSON = paths.BASE_CONTOUR_JSON


def _reintegrate(pts, i0, i1, delta):
    """辺 i0..i1-1 の接線を各 delta ラジアン回し、pts[i0] から積分し直して閉合誤差を線形に分散する。
    attack_common.py から移植した。"""
    seg = np.diff(pts[i0:i1 + 1], axis=0)
    ds = np.hypot(seg[:, 0], seg[:, 1])
    psi = np.arctan2(seg[:, 1], seg[:, 0]) + delta
    q = pts[i0] + np.concatenate([[[0.0, 0.0]], np.cumsum(np.stack([ds * np.cos(psi), ds * np.sin(psi)], axis=1), axis=0)])
    err = q[-1] - pts[i1]
    ss = np.concatenate([[0.0], np.cumsum(ds)])
    q -= err[None, :] * (ss / ss[-1])[:, None]
    return q, float(math.hypot(err[0], err[1]))


def apply_attack(pts, attack, x_left=None):
    """強化事例で用いる断面への故障注入。attack_common.py から同じ計算を移植した。
    指定は none、wide_low:<拡幅率>:<降下率>、back_kink:<角度>:worst。点列と情報を返す。"""
    pts = np.asarray(pts, dtype=np.float64).copy()
    info = {"attack": attack}
    name, *par = str(attack).split(":")
    if name == "none":
        return pts, info
    if x_left is None:
        x_left = ct.gw_frame.get_frame().x_left
    m = pm.measure_profile(pts)
    lm = m["landmarks"]
    s = _arc_s(pts)
    C = np.array(lm["crest"]["H"], dtype=np.float64)
    if name == "wide_low":
        k = 1.0 + float(par[0]) / 100.0
        pts[:, 0] = C[0] + k * (pts[:, 0] - C[0])
        pts[:, 1] *= 1.0 - float(par[1]) * PCT / C[1]
        info.update({"x_factor": k, "z_factor": 1.0 - float(par[1]) * PCT / C[1]})
    elif name == "back_kink":
        if par[1] != "worst":
            raise ValueError("移植済みなのは back_kink:<deg>:worst のみ")
        a = math.radians(float(par[0]))
        L, sp = 8.0 * PCT, 1.0 * PCT
        i0f = int(np.nonzero(pts[:, 0] >= x_left)[0][0])          # arc length along the contour AS SEEN (from the left frame edge)
        if i0f > 0:
            p0, p1 = pts[i0f - 1], pts[i0f]
            w = (x_left - p0[0]) / (p1[0] - p0[0])
            s_edge = s[i0f - 1] + w * (s[i0f] - s[i0f - 1])
        else:
            s_edge = 0.0
        ss = s - s_edge
        Cv = pm.Curve(pts)
        turn = np.abs(pm.wrap_deg(Cv.chord_deg(s, np.minimum(s + sp, Cv.length)) - Cv.chord_deg(np.maximum(s - sp, 0.0), s)))
        cand = np.nonzero((ss > L + 2 * PCT) & (s < lm["crest"]["s"] - L - 8.0 * PCT))[0]
        ok = cand[turn[cand] < 3.0]                                 # straight stretches of the back
        k = int(ok[np.argmin(np.abs(((ss[ok] / (sp / 4.0)) % 1.0) - 0.5))])      # exactly between two of the 4 phase grids
        i0, i1 = int(np.searchsorted(s, s[k] - L)), int(np.searchsorted(s, s[k] + L))
        sm = 0.5 * (s[i0:i1] + s[i0 + 1:i1 + 1])
        delta = np.where(sm < s[k], -0.5 * a * (sm - (s[k] - L)) / L, 0.5 * a * (1.0 - (sm - s[k]) / L))
        q, err = _reintegrate(pts, i0, i1, delta)
        moved = np.hypot(*(q - pts[i0:i1 + 1]).T)
        pts[i0:i1 + 1] = q
        info.update({"kink_vertex": k, "kink_H": [float(v) for v in pts[k]], "s_as_seen_pct_h": float(ss[k] / PCT),
                     "phase_offset_in_quarter_spacings": float((ss[k] / (sp / 4.0)) % 1.0),
                     "max_point_shift_pct_h": float(moved.max() / PCT), "closing_error_pct_h": err / PCT})
    else:
        raise ValueError("未知の故障注入 %r" % attack)
    return pts, info


def make_attack_wave_class(attack):
    class AttackWave(msw.SyntheticWave):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            if self._final_json_pts is None:
                raise ValueError("故障注入にはテスト用形状の profile-json モードが必要")
            self._final_json_pts, self.attack_info = apply_attack(self._final_json_pts, attack)
            pts, _ids, _info = self.profile(msw.FRAME_START)
            self.n_u = pts.shape[0]
            self.faces = msw.grid_faces(self.n_u, self.n_v)
            self.triangles = msw.grid_triangles(self.n_u, self.n_v)

    return AttackWave


def build_attack_case(scene, attack="none", island=0, floor_pct=0.0, nan_vertex=0, n_frames=2, H=11.0, taper="lift_clip"):
    """正式輪郭を lift_clip の先細りで掃引し、強化事例の故障を任意に加える。
    island=1 は空洞入口に X=0.17..0.30 H、Z=0.22..0.37 H の分離四角形 Island を追加。
    floor_pct=p は前方水面を p % 上げる Floor を追加。nan_vertex=1 は最終形状の中央行に NaN 頂点を置く。
    追加物体をシルエットへ含めるには --object SweptAttack,Island 等を指定する。"""
    import bpy
    orig = msw.SyntheticWave
    msw.SyntheticWave = make_attack_wave_class(str(attack))
    try:
        obj, sw_ = msw.build_object(scene, n_frames=int(n_frames), taper=taper, H=float(H), profile_json=OFFICIAL_JSON, name="SweptAttack")
    finally:
        msw.SyntheticWave = orig
    H = float(H)

    def quad(name, x0, x1, z0, z1):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)], [], [(0, 1, 2, 3)])
        me.update()
        scene.collection.objects.link(bpy.data.objects.new(name, me))

    if int(island):
        quad("Island", 0.17 * H, 0.30 * H, 0.22 * H, 0.37 * H)
    if float(floor_pct) > 0.0:
        quad("Floor", 0.10 * H, 1.6 * H, -0.02 * H, float(floor_pct) * PCT * H)
    if int(nan_vertex):
        idx = (sw_.n_v // 2) * sw_.n_u + sw_.n_u // 4
        kb = obj.data.shape_keys.key_blocks[-1]
        kb.data[idx].co = (float("nan"), float("nan"), float("nan"))
    return obj


def build_crash(scene, **_kw):
    """構築中に例外を送出する強化事例。"""
    raise RuntimeError("構築スクリプトの意図的な例外（自己検証事例 crashing_build_script）")


# ------------------------------------------------------------------------------------ analytic prediction (shape)
def analytic_contour(case, n_frames, F):
    """故障を加えた最終輪郭を CAM_print の見え方へ変換する。
    左端で切り、静水面に沿って右端まで延長する。網目・ラスター・Blender は使わない。"""
    sw = make_wave_class(case)(n_frames, "clip", 11.0)
    pts, _ids, _info = sw.profile(msw.FRAME_START + n_frames - 1)
    i0 = int(np.nonzero(pts[:, 0] >= F.x_left)[0][0])
    a, b = pts[i0 - 1], pts[i0]
    w = (F.x_left - a[0]) / (b[0] - a[0])
    first = a + w * (b - a)
    return np.concatenate([[first], pts[i0:], [[F.x_right, 0.0]]])


def predicted_failures(case, n_frames, F, S, bc):
    import test_shape
    J = test_shape.judge_profile(F, S, analytic_contour(case, n_frames, F), bc)
    summ = ct.summarize(J["checks"], True, [])
    return {t: sorted(summ[t]["failed"] + summ[t]["not_measurable"]) for t in ct.TIERS}, J


# ------------------------------------------------------------------------------------ driver
def modified_contour(case, root):
    """事例の目標 JSON を用意する。解析的な元輪郭または分段を意図的にずらした写しを出力先へ書く。
    tests/fixtures/synthetic_contour.json 自体は変更しない。"""
    mod = case.get("contour_mod")
    if not mod:
        return msw.SYNTHETIC_CONTOUR_JSON
    if not mod.startswith("tip_joint_shift_"):
        raise ValueError("未知の contour_mod %r" % mod)
    import copy
    n_pts = int(mod.rsplit("_", 1)[1])
    bc = copy.deepcopy(pm.load_base_contour(msw.SYNTHETIC_CONTOUR_JSON))
    by = {s["name"]: s for s in bc["segments"]}
    head, inner = by["head"], by["inner_arc"]
    for key in ("points_px", "points_H", "source", "in_S7"):
        if key in head:
            moved = head[key][-(n_pts + 1):]
            head[key] = head[key][:-n_pts]
            inner[key] = moved + inner[key][1:]
    bc["_comment"] = "SELFCHECK: synthetic_contour.json with the head / inner_arc joint moved %d samples back along the head" % n_pts
    return paths.write_json(os.path.join(root, case["name"], "target_%s.json" % mod), bc)


def _args_for(parser, case, out_dir, fps, contour=None):
    argv = ["--build-script", os.path.abspath(__file__), "--build-func", "build_case",
            "--build-arg", "case=%s" % case["name"],
            "--build-arg", "n_frames=%d" % case["n_frames"], "--build-arg", "taper=%s" % case.get("taper", "clip"),
            "--contour", contour or msw.SYNTHETIC_CONTOUR_JSON, "--out-dir", out_dir, "--fps", str(fps), "--exit-tier", "none"]
    return parser.parse_args(argv)


def backlog_ratio_with_half_window(res, half_window, eps):
    """完成した motion 結果の旧 M6 を別の隣接窓で再計算し、片側 2 対を標準とする理由を示す。"""
    import test_motion
    ser = res["series"]
    fr = np.asarray(ser["frame"])
    disp = np.array([np.nan if v is None else v for v in ser["disp_max_H"]], dtype=np.float64)
    i_final = int(np.nonzero(fr <= res["frames"]["final"])[0][-1])
    stop = res["phases"]["stop_frame"]
    i_stop = None if stop is None else int(np.nonzero(fr == stop)[0][0])
    n_excl = int(res["backlog_variants"]["M6_backlog"]["n_excluded_pairs_before_stop"])
    ratio, judged, _med = test_motion.backlog_jump_ratios(disp, i_final, i_stop, int(half_window), n_excl, eps)
    sel = np.isfinite(ratio) & judged
    return float(np.max(ratio[sel])) if sel.any() else None


def _key_numbers(result, ids):
    out = {}
    for c in result.get("checks", []):
        if c["id"] in ids:
            out[c["id"]] = c["measured"]
    return out


def numeric_gap(checks_pipeline, checks_section):
    """判定対象の数値について、処理全体と単一断面の予測との差の絶対値の最大を単位別に返す。
    失敗集合が同じでも数値が異なり得るため報告専用とする（crest_shift_x_3pct で確認）。"""
    b = {c["id"]: c for c in checks_section}
    worst = {}
    for c in checks_pipeline:
        o = b.get(c["id"])
        if o is None or c["info_only"] or c["measured"] is None or o["measured"] is None or c["unit"] == "bool":
            continue
        d = abs(c["measured"] - o["measured"])
        key = "deg" if c["unit"] == "deg" else "pct"
        if key not in worst or d > worst[key]["abs_diff"]:
            worst[key] = {"id": c["id"], "abs_diff": float(d), "pipeline": c["measured"], "section": o["measured"]}
    return worst


def check_width_exposure(factor, rows_pipeline, rows_section):
    """報告専用の寸法指標が factor 倍の拡幅を示すか調べ、真偽・各指標・問題点を返す。"""
    exp = (float(factor) - 1.0) * 100.0
    out, problems = {}, []
    for label, rows in (("pipeline", rows_pipeline), ("section", rows_section)):
        by = {r["name"]: r for r in rows or []}
        for k in W_KEYS_EXACT + (W_KEY_AREA,):
            r = by.get(k)
            v = None if r is None else r["diff_pct_of_target"]
            out.setdefault(k, {"expected_pct": exp if k != W_KEY_AREA else ("0 < x < %.3g" % exp if exp > 0 else "|x| <= %.3g" % W_TOL_PCT)})[label + "_pct"] = v
            if v is None or (r is not None and not r["comparable"]):
                problems.append("%s %s: not measurable / not comparable" % (label, k))
            elif k == W_KEY_AREA:
                if not ((0.0 < v < exp) if exp > 0 else abs(v) <= W_TOL_PCT):
                    problems.append("%s %s: %+.3f %% is not inside (0, %.3g)" % (label, k, v, exp))
            elif abs(v - exp) > W_TOL_PCT:
                problems.append("%s %s: %+.3f %% instead of %+.3f %% +- %.2g" % (label, k, v, exp, W_TOL_PCT))
    return not problems, out, problems


_REPORT_OPS = {"<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}


def check_report_values(expect, result):
    """-> (ok, {id: measured}, [problems]) for report-only values of a test result."""
    by = {c["id"]: c for c in result.get("checks", [])}
    vals, problems = {}, []
    for cid, (op, ref) in (expect or {}).items():
        v = by.get(cid, {}).get("measured")
        vals[cid] = v
        if v is None or not _REPORT_OPS[op](v, ref):
            problems.append("%s = %s, expected %s %s" % (cid, ct._fmt(v), op, ref))
    return not problems, vals, problems


_VALUE_OPS = {"<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "==": lambda a, b: a == b}


def check_harden_expectation(exp, res, clean=None):
    """検査結果を HARDEN_CASES の期待値と照合し、問題点と観測値を返す。"""
    problems, obs = [], {}
    summ = res["summary"]
    by = {c["id"]: c for c in res.get("checks", [])}
    got = {t: summ[t].get("verdict_base", summ[t]["verdict"]) for t in ct.TIERS}
    obs["verdict"] = {t: summ[t]["verdict"] for t in ct.TIERS}
    for t, word in (exp.get("verdict_base") or {}).items():
        if got[t] != word:
            problems.append("verdict %s = %s, expected %s" % (t, got[t], word))
    if "suffix" in exp:
        has = all(summ[t]["verdict"].endswith(ct.NON_DEFAULT_SUFFIX) for t in ct.TIERS)
        if has != bool(exp["suffix"]):
            problems.append("判定の接尾辞 '%s' の有無は %s、期待値は %s" % (ct.NON_DEFAULT_SUFFIX.strip(), has, exp["suffix"]))
    failing = ct.failing_ids(res, "spec")
    obs["failing_spec"] = failing
    for cid in exp.get("must_fail", []):
        if cid not in failing:
            problems.append("%s does not fail (spec tier)" % cid)
    for cid in exp.get("must_not_fail", []):
        if cid in failing:
            problems.append("%s fails (spec tier) but must not" % cid)
    if "failing_equals" in exp and sorted(exp["failing_equals"]) != failing:
        problems.append("失敗集合は %s、厳密な期待値は %s" % (failing, sorted(exp["failing_equals"])))
    for cid in exp.get("not_measurable", []):
        if cid not in summ["spec"]["not_measurable"]:
            problems.append("%s is not NOT_MEASURABLE" % cid)
    obs["values"] = {}
    for cid, spec_ in (exp.get("values") or {}).items():
        v = (by.get(cid) or {}).get("measured")
        obs["values"][cid] = v
        if v is None:
            problems.append("%s: no measured value" % cid)
        elif spec_[0] == "between":
            if not (spec_[1] <= v <= spec_[2]):
                problems.append("%s = %s, expected between %s and %s" % (cid, ct._fmt(v), spec_[1], spec_[2]))
        elif not _VALUE_OPS[spec_[0]](v, spec_[1]):
            problems.append("%s = %s, expected %s %s" % (cid, ct._fmt(v), spec_[0], spec_[1]))
    obs["diff_pct"] = {}
    for cid, (lo, hi) in (exp.get("diff_pct") or {}).items():
        d = ((by.get(cid) or {}).get("difference") or {}).get("pct_of_target")
        obs["diff_pct"][cid] = d
        if d is None or not (lo <= d <= hi):
            problems.append("%s differs from the base contour by %s %%, expected %s .. %s %%" % (cid, ct._fmt(d), lo, hi))
    obs["vs_clean"] = {}
    for cid, (op, delta) in (exp.get("vs_clean") or {}).items():
        v = (by.get(cid) or {}).get("measured")
        v0 = None if clean is None else ({c["id"]: c for c in clean.get("checks", [])}.get(cid) or {}).get("measured")
        obs["vs_clean"][cid] = None if (v is None or v0 is None) else v - v0
        if v is None or v0 is None:
            problems.append("%s: no value to compare with case official_clean (run it in the same self-check)" % cid)
        elif not _VALUE_OPS[op](v - v0, delta):
            problems.append("%s - clean = %s, expected %s %s" % (cid, ct._fmt(v - v0), op, delta))
    notes = " | ".join(summ.get("validity_notes") or [])
    for text in exp.get("validity_note_contains", []):
        if text not in notes:
            problems.append("有効性注記に %r がない" % text)
    if "non_default_names" in exp:
        names = [d["name"] for d in summ.get("non_default_settings") or []]
        obs["non_default_settings"] = summ.get("non_default_settings")
        for nm in exp["non_default_names"]:
            if nm not in names:
                problems.append("non-default setting %r is not listed (listed: %s)" % (nm, names))
    if "exit_code_spec" in exp:
        code = ct.exit_code(res, "spec")
        obs["exit_code_spec"] = code
        if code != exp["exit_code_spec"]:
            problems.append("--exit-tier spec の終了コードは %d、期待値は %d" % (code, exp["exit_code_spec"]))
    obs["document"] = {cid: (by.get(cid) or {}).get("measured") for cid in exp.get("document", [])}
    return problems, obs


def unit_verdict_vocabulary():
    """-> (problems, observed): summarize() / exit_code() on hand-made check lists of test_mesh (expected ids G1-G5)."""
    mk = ct.make_check
    full = [mk("G1", "n_topology_or_uv_changes", 0), mk("G2", "hem_step_pct_H", 0.0), mk("G3", "rim_thickness_pct_H", 1.0),
            mk("G4", "n_self_intersections", 0), mk("G4", "frame_step", 15), mk("G5", "rebuild_max_abs_diff_m", 0.0)]
    no_g5 = full[:-1]
    flagged = {"non_default": [{"group": "test_settings", "name": "jump_floor_frac_of_vmax", "effective": 1.0, "file_value": 0.05, "source": "--set"}], "unlisted": []}
    table = [  # 名称、検査、有効性、監査、エラー、両階層の期待判定、期待終了コード
        ("必要な全検査が判定済みで合格", full, True, None, None, "PASS", 0),
        ("検査が 0 件", [], True, None, None, "INCOMPLETE", 1),
        ("報告専用値だけ", [ct.report_value("G1", "max_vertex_step_H", 0.1)], True, None, None, "INCOMPLETE", 1),
        ("G5 は省略され未判定", no_g5, True, None, None, "INCOMPLETE", 1),
        ("G5 は測定不能", no_g5 + [mk("G5", "rebuild_max_abs_diff_m", None)], True, None, None, "FAIL", 1),
        ("G3 が失敗", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:], True, None, None, "FAIL", 1),
        ("G3 が失敗し G5 は未判定", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:-1], True, None, None, "FAIL", 1),
        ("数値は全て合格だが有効性を満たさない", full, False, None, None, "INVALID", 1),
        ("下位検査で例外", full, True, None, ["shape: RuntimeError: x"], "ERROR", 2),
        ("判定関連設定を変更し全検査は合格", full, True, flagged, None, "PASS" + ct.NON_DEFAULT_SUFFIX, 1),
        ("設定変更と検査失敗が重なる", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:], True, flagged, None, "FAIL" + ct.NON_DEFAULT_SUFFIX, 1),
    ]
    problems, obs = [], {}
    for name, checks, valid, audit, errors, word, code in table:
        summ = ct.summarize(checks, valid, [], expected=ct.EXPECTED_IDS["mesh"], audit=audit, errors=errors)
        got = [summ[t]["verdict"] for t in ct.TIERS]
        got_code = ct.exit_code({"summary": summ}, "spec")
        obs[name] = {"verdict": got, "exit_code": got_code}
        if got != [word] * len(ct.TIERS) or got_code != code:
            problems.append("%s: verdict %s exit code %d, expected %s / %d" % (name, got, got_code, word, code))
    try:
        ct.validate_names(["shape", "shpae"], ("shape", "motion", "mesh"), "--only")
        problems.append("validate_names accepted the unknown name 'shpae'")
    except ValueError:
        pass
    if ct.validate_names(["g5", " G1 ", ""], ("G1", "G2", "G3", "G4", "G5"), "--skip") != ["G5", "G1"]:
        problems.append("validate_names does not return the canonical spelling")
    return problems, {"values": {k: "%s / exit %d" % (v["verdict"][0], v["exit_code"]) for k, v in obs.items()}}


def unit_settings_audit():
    """-> (problems, observed): get_settings() strictness and settings_audit() against thresholds.json 'interpretations'."""
    problems, vals = [], {}
    try:
        ct.get_settings({"jump_floor": 1.0})
        problems.append("get_settings accepted the unknown name 'jump_floor'")
    except ValueError:
        vals["unknown --set name"] = "ValueError"
    S0, src0 = ct.get_settings(None, with_sources=True)
    a0 = ct.settings_audit(S0, src0)
    vals["defaults: non_default / unlisted"] = "%d / %d" % (len(a0["non_default"]), len(a0["unlisted"]))
    if not a0["ok"]:
        problems.append("コードの既定値が tests/thresholds.json の interpretations と異なる：%s" % (a0["non_default"] + a0["unlisted"]))
    S1, src1 = ct.get_settings({"jump_floor_frac_of_vmax": 1.0, "contact_sheet_step": 10}, with_sources=True)
    a1 = ct.settings_audit(S1, src1)
    names = [(d["name"], d["source"]) for d in a1["non_default"]]
    vals["--set jump_floor_frac_of_vmax=1.0"] = str(names)
    if names != [("jump_floor_frac_of_vmax", "--set")]:
        problems.append("--set jump_floor_frac_of_vmax=1.0 の監査結果が %s" % names)
    if [d["name"] for d in a1["report_only_non_default"]] != ["contact_sheet_step"]:
        problems.append("report-only setting contact_sheet_step is not listed separately: %s" % a1["report_only_non_default"])
    a2 = ct.settings_audit(S0, src0, measure_params=pm.get_params({"s8_tip_exclusion_pct_h": 3.0, "width_levels_H": [0.3, 0.6]}))
    vals["s8_tip_exclusion_pct_h=3 の上書き"] = str([(d["group"], d["name"]) for d in a2["non_default"]])
    if [(d["group"], d["name"]) for d in a2["non_default"]] != [("measure_params", "s8_tip_exclusion_pct_h")]:
        problems.append("測定パラメータの上書きの監査結果が %s" % a2["non_default"])
    if [d["name"] for d in a2["report_only_non_default"]] != ["width_levels_H"]:
        problems.append("report-only measure parameter width_levels_H is not listed separately: %s" % a2["report_only_non_default"])
    a3 = ct.settings_audit(S0, src0, effective={"hold_frames": (0, "--hold-frames"), "motion_frame_step": (2, "--frame-step")})
    got3 = sorted((d["name"], d["source"]) for d in a3["non_default"])
    vals["--hold-frames 0 --frame-step 2"] = str(got3)
    if got3 != [("hold_frames", "--hold-frames"), ("motion_frame_step", "--frame-step")]:
        problems.append("コマンド行の置換の監査結果が %s" % got3)
    return problems, {"values": vals}


def unit_settings_from_params_json():
    """-> (problems, observed): get_settings() with a simulated params.json entry 'test_settings'."""
    problems, vals = [], {}
    real = paths.param

    def fake(entry):
        def param(name, path=None):
            if name == "test_settings":
                if entry is KeyError:
                    raise KeyError(name)
                return entry
            return real(name, path)
        return param

    try:
        paths.param = fake({"monotonic_noise_floor_H": {"value": 0.01, "comment": "x"}, "comment": "simulated"})
        S1, src1 = ct.get_settings(None, with_sources=True)
        got = [(d["name"], d["effective"], d["source"]) for d in ct.settings_audit(S1, src1)["non_default"]]
        vals["test_settings.monotonic_noise_floor_H = 0.01"] = str(got)
        if got != [("monotonic_noise_floor_H", 0.01, "params.json test_settings")]:
            problems.append("params.json test_settings override is listed as %s" % got)
        for entry, exc_type in (({"monotonic_noise_floor": 0.01}, ValueError), ([1, 2], TypeError)):
            paths.param = fake(entry)
            try:
                ct.get_settings()
                problems.append("get_settings accepted params.json test_settings = %r" % (entry,))
            except exc_type:
                vals["test_settings = %r" % (entry,)] = exc_type.__name__
        paths.param = fake(KeyError)
        S0, src0 = ct.get_settings(None, with_sources=True)
        if src0 or not ct.settings_audit(S0, src0)["ok"]:
            problems.append("test_settings がない場合に清浄な既定値にならない")
        vals["項目なし"] = "既定値、監査済み"
    finally:
        paths.param = real
    return problems, {"values": vals}


def run_harden_inprocess(case, parser, runners, out_dir):
    """現在の Blender プロセスで強化事例を一件実行し、結果を返す。"""
    if case.get("fixture_case"):
        argv = ["--build-script", os.path.abspath(__file__), "--build-func", "build_case", "--build-arg", "case=%s" % case["fixture_case"],
                "--build-arg", "n_frames=%d" % case["n_frames"], "--contour", msw.SYNTHETIC_CONTOUR_JSON,
                "--fps", "30" if case["n_frames"] == N_LONG else "10"]
    else:
        argv = ["--build-script", os.path.abspath(__file__), "--build-func", "build_attack_case", "--build-arg", "attack=%s" % case.get("attack", "none"),
                "--build-arg", "island=%d" % int(case.get("island", 0)), "--build-arg", "floor_pct=%s" % float(case.get("floor_pct", 0.0)),
                "--build-arg", "nan_vertex=%d" % int(case.get("nan_vertex", 0))]
        if case.get("objects"):
            argv += ["--object", case["objects"]]
    argv += ["--out-dir", out_dir, "--exit-tier", "none"] + list(case.get("extra_args", []))
    args = parser.parse_args(argv)
    ct.begin_run(out_dir, case["test"])
    ctx = ct.setup_context(args, case["test"], run_dir=out_dir)
    res = runners[case["test"]](ctx) if case["test"] != "mesh" else runners["mesh_skip"](ctx, case.get("mesh_skip", ()))
    ct.end_run(out_dir)
    return res


def run_harden_subprocess(case, out_dir):
    """個別の Blender プロセスで強化事例を実行し、問題点と観測値を返す。"""
    import bpy
    exp = case["expect"]
    paths.ensure_dir(out_dir)
    if case.get("seed_stale_pass"):
        fake = {"schema": ct.RESULT_SCHEMA, "test": "shape", "SEEDED_BY_SELFCHECK": "架空の前回実行に残された古い結果",
                "summary": {t: {"verdict": "PASS"} for t in ct.TIERS}}
        paths.write_json(os.path.join(out_dir, "metrics.json"), fake)
        with open(paths.assert_writable(os.path.join(out_dir, "summary.md")), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# stale PASS seeded by selfcheck_tests.py\n")
    cmd = [bpy.app.binary_path, "--background", "--factory-startup"]
    if case.get("python_exit_code_flag", True):
        cmd += ["--python-exit-code", "1"]
    cmd += ["--python", os.path.join(_HERE, case["script"]), "--"]
    cmd += [a.replace("{fixture}", os.path.join(_HERE, "fixtures", "make_synthetic_wave.py")).replace("{this}", os.path.abspath(__file__)) for a in case["argv"]]
    cmd += ["--out-dir", out_dir]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    with open(paths.assert_writable(os.path.join(out_dir, "selfcheck_subprocess.log")), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# %s\n" % " ".join(cmd))
        fh.write(proc.stdout or "")
        fh.write("\n# exit code %s\n" % proc.returncode)
    problems, obs = [], {"exit_code": proc.returncode, "command": cmd}
    if proc.returncode != exp["exit_code"]:
        problems.append("終了コードは %s、期待値は %s" % (proc.returncode, exp["exit_code"]))
    mp = os.path.join(out_dir, "metrics.json")
    res = paths.read_json(mp) if os.path.isfile(mp) else None
    if res is None or res.get("SEEDED_BY_SELFCHECK"):
        problems.append("出力先に今回の metrics.json がない（%s）" % ("欠落" if res is None else "古いファイルが残っている"))
    else:
        got = {t: res["summary"][t].get("verdict_base", res["summary"][t]["verdict"]) for t in ct.TIERS}
        obs["verdict"] = {t: res["summary"][t]["verdict"] for t in ct.TIERS}
        for t, word in exp["verdict_base"].items():
            if got[t] != word:
                problems.append("verdict %s = %s, expected %s" % (t, got[t], word))
        if "n_judged" in exp and res["summary"]["spec"].get("n_judged") != exp["n_judged"]:
            problems.append("n_judged = %s, expected %s" % (res["summary"]["spec"].get("n_judged"), exp["n_judged"]))
        for t_name in exp.get("sub_tests_present", []):
            if t_name not in (res.get("tests") or {}):
                problems.append("sub-test %s has no result in the combined metrics.json" % t_name)
            elif ct.RUNNING_MARKER in os.listdir(os.path.join(out_dir, t_name)):
                problems.append("sub-test %s left its RUNNING marker behind" % t_name)
        for t_name, word in (exp.get("sub_test_verdict_base") or {}).items():
            got_t = ((res.get("tests") or {}).get(t_name) or {}).get("spec", {}).get("verdict_base")
            obs.setdefault("sub_test_verdicts", {})[t_name] = got_t
            if got_t != word:
                problems.append("sub-test %s verdict %s, expected %s" % (t_name, got_t, word))
        if "error_type" in exp:
            obs["error"] = {k: (res.get("error") or {}).get(k) for k in ("type", "message")}
            if (res.get("error") or {}).get("type") != exp["error_type"]:
                problems.append("エラー型は %s、期待値は %s" % ((res.get("error") or {}).get("type"), exp["error_type"]))
            if exp.get("error_message_contains") and exp["error_message_contains"] not in ((res.get("error") or {}).get("message") or ""):
                problems.append("エラーメッセージに %r がない" % exp["error_message_contains"])
            if "Traceback" not in ((res.get("error") or {}).get("traceback") or ""):
                problems.append("metrics.json has no traceback")
    files = sorted(os.listdir(out_dir))
    obs["files"] = files
    if exp.get("running_marker") is False and ct.RUNNING_MARKER in files:
        problems.append("the RUNNING marker is still in the run directory")
    for fn in exp.get("stale_files", []):
        hits = [f for f in files if f.startswith("stale_") and f.endswith("_" + fn)]
        if not hits:
            problems.append("古い %s が stale_*_%s に改名されなかった" % (fn, fn))
        elif fn == "metrics.json" and not paths.read_json(os.path.join(out_dir, hits[0])).get("SEEDED_BY_SELFCHECK"):
            problems.append("stale_*_metrics.json is not the seeded file")
    return problems, obs


def main():
    import test_mesh
    import test_motion
    import test_shape
    ap = argparse.ArgumentParser(description="合成波による大波検査の自己確認")
    ap.add_argument("--cases", default="", help="事例名をカンマ区切りで指定（既定：全事例）")
    ap.add_argument("--quick", action="store_true", help="G5の別プロセス再構築と幅拡大の走査を省く")
    own = bootstrap.parse_args(ap)
    parser = argparse.ArgumentParser()
    ct.add_common_args(parser)
    test_motion.add_args(parser)
    test_mesh.add_args(parser)
    runners = {"shape": lambda c: test_shape.run(c), "motion": lambda c: test_motion.run(c),
               "mesh": lambda c: test_mesh.run(c, skip=()), "mesh_skip": lambda c, sk: test_mesh.run(c, skip=sk)}
    try:
        wanted = ct.validate_names(own.cases.split(","), [c["name"] for c in CASES] + [c["name"] for c in HARDEN_CASES], "--cases")
    except ValueError as exc:                       # a typo must not select nothing and end as '0 mismatches'
        log("エラー：%s" % exc)
        log("結果：ERROR selfcheck_tests（終了コード %d）" % ct.EXIT_CODE_ERROR)
        sys.exit(ct.EXIT_CODE_ERROR)
    root = paths.results_run_dir("selfcheck")
    F = ct.gw_frame.get_frame()
    S = ct.get_settings()
    bc = pm.load_base_contour(msw.SYNTHETIC_CONTOUR_JSON)
    rows, all_ok = [], True
    for case in CASES:
        if wanted and case["name"] not in wanted:
            continue
        log("==== case %s: %s" % (case["name"], case["defect"]))
        fps = 30.0 if case["n_frames"] == N_LONG else 10.0
        first = True
        ctx = None
        for tname in ("shape", "motion", "mesh"):                  # mesh last: G5 resets the scene
            exp = case["tests"].get(tname)
            if exp is None:
                continue
            out_dir = os.path.join(root, case["name"], tname)
            args = _args_for(parser, case, out_dir, fps, modified_contour(case, root))
            if own.quick:
                args.g5_mode = "inprocess"
            ct.begin_run(out_dir, tname)
            try:
                if first or ctx is None:
                    ctx = ct.setup_context(args, tname, run_dir=out_dir)
                    first = False
                else:
                    ctx.args, ctx.test_name, ctx.run_dir = args, tname, paths.ensure_dir(out_dir)
                res = runners[tname](ctx)
            except Exception as exc:                # a crashing test is a MISMATCH of this pair, not the end of the self-check
                tb = traceback.format_exc()
                for ln in tb.rstrip().splitlines():
                    log("==== case %s / %s ERROR %s" % (case["name"], tname, ln))
                res = ct.error_result(tname, out_dir, exc, tb)
                ct.write_result(out_dir, res)
                ctx = None
            ct.end_run(out_dir)
            actual = {t: ct.failing_ids(res, t) for t in ct.TIERS}
            must = sorted(exp["must_fail"])
            must_rel = must if exp.get("relaxed", None) is None else sorted(exp["relaxed"])
            pred, gap = None, None
            if exp["mode"] == "analytic":
                pred, _J = predicted_failures(case["name"], case["n_frames"], F, S, bc)
                gap = numeric_gap(res.get("checks", []), _J["checks"])
                ok = set(must) <= set(actual["spec"]) and actual["spec"] == pred["spec"] and \
                    set(must_rel) <= set(actual["user_relaxed_5pct"]) and actual["user_relaxed_5pct"] == pred["user_relaxed_5pct"]
            elif exp["mode"] == "exact":
                ok = actual["spec"] == must and actual["user_relaxed_5pct"] == must_rel
            else:
                ok = set(must) <= set(actual["spec"])
            if res.get("error"):
                ok = False
            # ---- report-only numbers (no thresholds): do they show what they are meant to show?
            report_only = {}
            if exp.get("expect_W"):
                rows_pipe = ((res.get("measurements") or {}).get("W_compare") or {}).get("rows")
                ok_w, wvals, wprob = check_width_exposure(exp["expect_W"]["factor"], rows_pipe, None if pred is None else _J["w_rows"])
                report_only["W"] = {"factor": exp["expect_W"]["factor"], "ok": ok_w, "values": wvals, "problems": wprob}
                ok = ok and ok_w
            if exp.get("expect_report"):
                ok_r, rvals, rprob = check_report_values(exp["expect_report"], res)
                report_only["report"] = {"expected": {k: list(v) for k, v in exp["expect_report"].items()}, "ok": ok_r, "values": rvals, "problems": rprob}
                if "M6.backlog_jump_ratio" in exp["expect_report"]:          # information: the same run with ONE neighbour on each side
                    report_only["report"]["backlog_jump_ratio_with_half_window_1"] = backlog_ratio_with_half_window(res, 1, float(S["static_disp_eps_H"]))
                ok = ok and ok_r
            if exp.get("expect_verdict"):
                got = {t: res["summary"][t]["verdict"] for t in ct.TIERS}
                ok_v = all(got[t] == exp["expect_verdict"][t] for t in ct.TIERS)
                report_only["verdict"] = {"expected": exp["expect_verdict"], "values": got, "ok": ok_v,
                                          "problems": [] if ok_v else ["verdict %s, expected %s" % (got, exp["expect_verdict"])]}
                ok = ok and ok_v
            all_ok &= ok
            ids = set(must) | set(actual["spec"]) | set(actual["user_relaxed_5pct"])
            rows.append({"case": case["name"], "defect": case["defect"], "test": tname, "mode": exp["mode"],
                         "must_fail_spec": must, "must_fail_relaxed": must_rel, "predicted": pred, "actual": actual, "ok": bool(ok),
                         "numbers": _key_numbers(res, ids), "pipeline_vs_section_gap": gap, "validity_notes": res["summary"]["validity_notes"],
                         "verdicts": {t: res["summary"][t]["verdict"] for t in ct.TIERS}, "report_only": report_only,
                         "run_dir": paths.norm(out_dir)})
            log("==== case %s / %s: %s   spec failed = %s   (must fail %s%s)"
                % (case["name"], tname, "OK" if ok else "MISMATCH", actual["spec"] or "-", must or "-",
                   "" if pred is None else "; analytic prediction %s" % (pred["spec"] or "-")))
            for kind, ro in report_only.items():
                log("     report-only %s: %s %s" % (kind, "OK" if ro["ok"] else "MISMATCH", "; ".join(ro["problems"]) if ro["problems"] else
                                                   ", ".join("%s=%s" % (k, ct._fmt(v if not isinstance(v, dict) else v.get("pipeline_pct"))) for k, v in ro["values"].items())))
    # ---- hardening cases (expectations: HARDEN_CASES, written before their first run)
    clean_res = None
    for case in HARDEN_CASES:
        if wanted and case["name"] not in wanted:
            continue
        if own.quick and case["kind"] == "subprocess":
            continue
        log("==== hardening case %s: %s" % (case["name"], case["defect"]))
        out_dir = os.path.join(root, "harden_" + case["name"])
        obs, res = {}, None
        try:
            if case["kind"] == "subprocess":
                problems, obs = run_harden_subprocess(case, out_dir)
            elif case["kind"] == "unit":
                problems, obs = globals()[case["func"]]()
            else:
                res = run_harden_inprocess(case, parser, runners, out_dir)
                if case["name"] == "official_clean":
                    clean_res = res
                problems, obs = check_harden_expectation(case["expect"], res, clean_res)
        except Exception as exc:
            tb = traceback.format_exc()
            for ln in tb.rstrip().splitlines():
                log("==== hardening case %s ERROR %s" % (case["name"], ln))
            problems = ["事例で例外 %s：%s" % (type(exc).__name__, exc)]
        ok = not problems
        all_ok &= ok
        rows.append({"case": case["name"], "defect": case["defect"], "test": case.get("test") or case.get("script"), "mode": case["kind"],
                     "must_fail_spec": sorted(case["expect"].get("must_fail", [])), "must_fail_relaxed": [], "predicted": None,
                     "actual": {"spec": obs.get("failing_spec", []), "user_relaxed_5pct": [] if res is None else ct.failing_ids(res, "user_relaxed_5pct")},
                     "ok": bool(ok), "numbers": dict(obs.get("values") or {}, **(obs.get("document") or {})), "pipeline_vs_section_gap": None,
                     "validity_notes": [] if res is None else res["summary"]["validity_notes"],
                     "verdicts": obs.get("verdict"), "report_only": {}, "run_dir": paths.norm(out_dir),
                     "harden": {"expectation": case["expect"], "observed": obs, "problems": problems}})
        log("==== hardening case %s: %s   verdict %s%s" % (case["name"], "OK" if ok else "MISMATCH", obs.get("verdict"),
                                                          "" if ok else "   PROBLEMS: " + "; ".join(problems)))
    # ---- sensitivity of the shape tests to widening (analytic layer only; the user's complaint was 'too wide')
    sweep = []
    if not own.quick and not wanted:
        for k in WIDEN_SWEEP:
            pred, J = predicted_failures("widen_factor_%.4f" % k, N_SHORT, F, S, bc)
            s7 = J["s7"]
            wby = {r["name"]: r["diff_pct_of_target"] for r in J["w_rows"]}
            sweep.append({"factor": k, "failed_spec": pred["spec"], "failed_relaxed": pred["user_relaxed_5pct"],
                          "S7": {seg: {"mean": s7[seg]["mean_dev_pct_h"], "p95": s7[seg]["p95_dev_pct_h"]} for seg in ("back", "head", "inner_arc") if s7.get(seg)},
                          "S5_pos_pct_h": None if not J["pc"].get("S5") else J["pc"]["S5"]["pos_pct_h"],
                          "W_diff_pct": {kk: wby.get(kk) for kk in W_KEYS_EXACT + (W_KEY_AREA,)}})
            log("幅の拡大 x%.2f：仕様階層の失敗 = %s" % (k, pred["spec"] or "-"))
    if not rows:
        all_ok = False                                # a self-check that ran nothing is not a success
        log("エラー：事例が一つも実行されていない")
    report = {"schema": "gw.selfcheck.v1", "created": ct.now_stamp(), "all_ok": bool(all_ok), "rows": rows, "widen_sweep": sweep,
              "fixture": {"contour": paths.norm(msw.SYNTHETIC_CONTOUR_JSON), "frames_short": N_SHORT, "frames_long": N_LONG}}
    paths.write_json(os.path.join(root, "selfcheck_report.json"), ct.jsonable(report))
    write_table(root, rows, sweep, all_ok)
    log("自己確認の報告: %s" % root)
    bootstrap.finish(bool(all_ok), "selfcheck_tests: %d (case, test) pairs, %d mismatches"
                     % (len(rows), sum(1 for r in rows if not r["ok"])))


def write_table(root, rows, sweep, all_ok):
    L = ["# 検査の自己確認（%s） 全件一致 = %s" % (ct.now_stamp(), all_ok), "",
         "| 事例 | 故障内容 | 検査 | 方法 | 必須の失敗（原仕様） | 解析的予測（原仕様） | 実際の失敗（原仕様） | 実際の失敗（5％段階） | 主な数値 | 処理経路と単一断面の最大差 | 報告専用値 | 結果 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("harden"):
            continue
        nums = ", ".join("%s=%s" % (k, ct._fmt(v)) for k, v in sorted(r["numbers"].items()))
        g = r.get("pipeline_vs_section_gap")
        gtxt = "n/a" if not g else "; ".join("%s: %.4g (%s %.4g vs %.4g)" % (k, v["abs_diff"], v["id"], v["pipeline"], v["section"]) for k, v in sorted(g.items()))
        ro = []
        for kind, d in (r.get("report_only") or {}).items():
            if kind == "W":
                ro.append("W と基準輪郭の比較（x%.2f）: " % d["factor"] + ", ".join("%s %s %%" % (k, "該当なし" if v.get("pipeline_pct") is None else "%+.2f" % v["pipeline_pct"])
                                                                          for k, v in d["values"].items()) + (" → 一致" if d["ok"] else " → **不一致** " + "; ".join(d["problems"])))
            elif kind == "verdict":
                ro.append("判定 " + ", ".join("%s=%s（期待値 %s）" % (k, v, d["expected"][k]) for k, v in d["values"].items())
                          + (" → 一致" if d["ok"] else " → **不一致**"))
            else:
                ro.append(", ".join("%s=%s（期待値 %s %s）" % (k, ct._fmt(v), d["expected"][k][0], d["expected"][k][1]) for k, v in d["values"].items())
                          + ("" if d.get("backlog_jump_ratio_with_half_window_1") is None else
                             "; [参考] M6_backlog で両側1組ずつを使うと %s" % ct._fmt(d["backlog_jump_ratio_with_half_window_1"]))
                          + (" → 一致" if d["ok"] else " → **不一致**"))
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["case"], r["defect"], r["test"], r["mode"], ", ".join(r["must_fail_spec"]) or "-",
            "n/a" if r["predicted"] is None else (", ".join(r["predicted"]["spec"]) or "-"),
            ", ".join(r["actual"]["spec"]) or "-", ", ".join(r["actual"]["user_relaxed_5pct"]) or "-", nums or "-", gtxt,
            "<br>".join(ro) or "-", "一致" if r["ok"] else "**不一致**"))
    hard = [r for r in rows if r.get("harden")]
    if hard:
        L += ["", "## 強化事例（期待値は初回実行前に記録。tests/selfcheck_tests.py の HARDEN_CASES を参照）", "",
              "| 事例 | 故障内容 | 検査／スクリプト | 判定 | 失敗項目（原仕様） | 観測値 | 問題 | 結果 |", "|---|---|---|---|---|---|---|---|"]
        for r in hard:
            o = r["harden"]["observed"]
            vals = dict(o.get("values") or {})
            vals.update({k + " [基準比の差％]": v for k, v in (o.get("diff_pct") or {}).items()})
            vals.update({k + " [無改変との差]": v for k, v in (o.get("vs_clean") or {}).items()})
            vals.update({k + " [記録値]": v for k, v in (o.get("document") or {}).items()})
            if "exit_code" in o:
                vals["終了コード"] = o["exit_code"]
            if "exit_code_spec" in o:
                vals["終了コード（--exit-tier spec）"] = o["exit_code_spec"]
            if o.get("error"):
                vals["エラー"] = "%s: %s" % (o["error"].get("type"), o["error"].get("message"))
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r["case"], r["defect"], r["test"], "該当なし" if not o.get("verdict") else ", ".join("%s=%s" % kv for kv in o["verdict"].items()),
                ", ".join(o.get("failing_spec") or []) or "-", "; ".join("%s = %s" % (k, ct._fmt(v)) for k, v in vals.items()) or "-",
                "; ".join(r["harden"]["problems"]).replace("|", "/") or "-", "一致" if r["ok"] else "**不一致**"))
    if sweep:
        L += ["", "## 横幅拡大の走査（解析層）", "",
              "W列は報告専用の寸法値で閾値を持たない。差は基準輪郭の値に対する百分率。", "",
              "| X倍率 | 失敗（原仕様） | 失敗（5％段階） | S7 背の平均／95％値 | S7 波頭の平均／95％値 | S7 内側の弧の平均／95％値 | S5 位置 | W z75 幅 | W 張り出し | W 空洞深度 | W 面積 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in sweep:
            g = lambda seg: "n/a" if seg not in s["S7"] else "%.3f / %.3f" % (s["S7"][seg]["mean"], s["S7"][seg]["p95"])  # noqa: E731
            w = lambda kk: "n/a" if s.get("W_diff_pct", {}).get(kk) is None else "%+.2f %%" % s["W_diff_pct"][kk]  # noqa: E731
            L.append("| %.2f | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                s["factor"], ", ".join(s["failed_spec"]) or "-", ", ".join(s["failed_relaxed"]) or "-",
                g("back"), g("head"), g("inner_arc"), ct._fmt(s["S5_pos_pct_h"]),
                w("z75.width_full_H"), w("o_H"), w("cavity_depth_H"), w(W_KEY_AREA)))
    p = paths.ensure_parent(os.path.join(root, "selfcheck_table.md"))
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
