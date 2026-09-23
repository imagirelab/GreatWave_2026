"""great_wave の単独テスト（test_shape / test_motion / test_mesh / run_all）に共通する補助処理。

このモジュールの役割
--------------------
* コマンドライン: 各テストが受け付ける引数（add_common_args）
* シーンの準備: .blend を開く、または構築スクリプトを実行し、波のオブジェクトを特定する（setup_context）
* しきい値: make_check() が各検査について両階層（'spec' と 'user_relaxed_5pct'）の
  合否を含む JSON 用レコードを作る。限界値の出典は tests/thresholds.json だけである。
* 設定: TEST_SETTINGS はノイズ下限や解像度など、テスト側の測定設定であり、しきい値ではない。
  params.json の 'test_settings' または --set key=value で変更できる。未知の名前はエラーとする。
  判定に影響する設定と測定パラメータは tests/thresholds.json の 'interpretations' にも記録する。
  settings_audit() は有効値を照合し、差があれば判定結果に ' (NON-DEFAULT SETTINGS)' を付ける。
* 判定: PASS / FAIL / INVALID / INCOMPLETE / ERROR。条件により
  ' (NON-OFFICIAL INPUTS)' と ' (NON-DEFAULT SETTINGS)' が続く。summarize() を参照。
  inputs_audit() は --contour / --H / --water-z / --fps をプロジェクトの値と照合する。
* 異常終了対策: parse_args_guarded() は引数エラー時に --out-dir の古い出力を退避し、
  ERROR（終了コード 2）を書き出す。guarded_main() は実行先の古い出力を退避し、RUNNING 印を置く。
  未処理の例外、およびテスト本体が実行中に生じた SystemExit（構築スクリプト内の
  sys.exit(0) / gw.bootstrap.finish(True) など）は ERROR の metrics.json と終了コード 2 に変える。
* 有効性: evaluation_state_report()。テストはビューポートの依存グラフを測るため、
  対象モディファイアの show_viewport と show_render（または levels と render_levels）が異なると INVALID。
* 出力: 各階層の概要、metrics.json、summary.md、ログ、警告行。
* メッシュ取得: 一フレームの評価済みメッシュの頂点位置・位相・UV 配列。

構築スクリプトの約束（--build-script）
----------------------------------------
    --build-script <file.py> [--build-func <name>] [--build-arg key=value ...]
ファイルをモジュールとして読み込むため、`if __name__ == "__main__"` 節は実行しない。
空の初期シーン（または --blend で開いたシーン）で `func(scene, **build_args)` を呼ぶ。
`func` は --build-func の指定値。未指定なら build_for_tests、build、build_object の順に存在する関数を選ぶ。
関数は `scene` 内に波オブジェクトを作り、そのオブジェクト、先頭要素がオブジェクトのタプル、
または None を返せる。None の場合は --object で名前を指定する。
--build-arg の値は可能なら JSON として読み解く。

環境変数は読み書きせず、許可されたルート以外へは書き込まない。
"""
import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
import traceback

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gw import bootstrap, draw, frame as gw_frame, imgio, paths, plot, silhouette  # noqa: E402,F401
from gw import profile_metrics as pm  # noqa: E402

log = bootstrap.log
TIERS = paths.TIER_NAMES
RESULT_SCHEMA = "gw.test_result.v1"

# ------------------------------------------------------------------------------------ 測定設定
TEST_SETTINGS = {
    "shape_res_scale": {"value": 1.0, "comment": "test_shape のマスク解像度倍率。1.0 は原画と同じ 3859×2594 px。"},
    "motion_res_scale": {"value": 0.25, "comment": "test_motion のマスク解像度倍率。境界の交差位置を正確に求めるため、精度はこの値に依存しない（docs/measurement_definitions.md 第 7 節）。"},
    "mesh_res_scale": {"value": 0.5, "comment": "test_mesh が見える波頭先端を特定する際に使う CAM_print 輪郭のマスク解像度倍率（G3）。"},
    "monotonic_noise_floor_H": {"value": 1e-4, "comment": "解釈値。フレーム間の h / o の減少がこの値未満なら測定ノイズとして 0 と判定する（H 単位。画像高の 0.0066 %、H=11 m では 1.1 mm）。測定ノイズの記録値は h で 5e-6 H、o と x_c で 1.5e-4 H。元の値も判定値と並べて必ず報告する。"},
    "monotonic_noise_floor_deg": {"value": 0.2, "comment": "解釈値。phi に対する同様の許容値。記録された測定誤差は各フレームで 0.07 度以下、差分で 0.14 度以下。"},
    "static_disp_eps_H": {"value": 1e-6, "comment": "解釈値。輪郭変位がこの値以下なら「動いていない」と数える（H 単位。H=11 m では 0.011 mm）。停止検出と M5 の停止後検査に用いる。"},
    "disp_z_min_H": {"value": 0.01, "comment": "この高さより下の輪郭標本（静水面に沿う区間）は輪郭変位の計算から除く。pm.measure_sequence の既定値。"},
    "jump_floor_frac_of_vmax": {"value": 0.05, "comment": "解釈値（M6）。急変比の分母となる隣接変位を、最大フレーム変位のこの比率未満にはしない。そうしないと静止からの開始や停止時に x/0 がすべて急変と判定される。"},
    "hold_frames": {"value": None, "comment": "解釈値（M5 の「停止後は形状が変わらない」）。None なら宣言された最終フレームより後にシーンが持つ全フレーム（final+1～scene.frame_end）を評価・判定する。2026-09-20 までは 3 フレームだけだったため、3 フレーム静止した後にずれる姿勢が合格していた。数値（--hold-frames N または --set）を指定すると、最終フレーム後の N フレームだけを評価し、標準設定との差として判定に印を付ける。0 の場合、この検査は NOT_MEASURABLE。"},
    "min_hold_s": {"value": 1.0, "comment": "解釈値（M5）。宣言された最終フレームの後に、少なくともこの秒数だけシーンが最終姿勢を保持する必要がある（30 fps なら 30 フレーム）。短い保持中に動きが見えなくても M5.post_stop_max_disp_H は判定せず、判定結果は INCOMPLETE とする。短い保持中に動けば失敗。ステップ 3 の生成処理は scene.frame_end >= 最終フレーム + 1 秒を満たし、--final-frame または scene['gw_final_frame'] で最終フレームを宣言する必要がある。"},
    "m6_backlog_half_window": {"value": 2, "comment": "報告専用の解釈値。作業一覧の定義 4「隣接フレーム間の変位は、停止への移行を除き、周辺フレームの中央値の 3 倍を超えない」に対し、組 k の前後それぞれこの数のフレーム組の変位で中央値を取る（k 自身は除外、端では数を減らす）。1 ではなく 2 としたのは、単一フレームの異常値が往復の二つの大きな変位を生み、前後 1 組ずつの中央値では二値の平均となって最初の急変が隠れるため（比 2）。"},
    "m6_backlog_exclude_window_s": {"value": None, "comment": "報告専用。「停止への移行を除く」の解釈値。後側フレームが停止フレームのこの秒数以内に入る組と、停止後の全組を M6_backlog から除く。None は thresholds.json の M5 減速窓（M5.decel_window_s=1 秒）を意味する。"},
    "backlog_hold_s": {"value": 10.0, "comment": "報告専用。作業一覧の定義 5「静止姿勢を 10 秒保持し、輪郭の移動は画像高の 0.2 % 以下」に対し、最終フレーム後に評価する保持の長さ。scene.frame_end を超えるフレームは Blender がアニメーションを外挿した状態で評価する。"},
    "backlog_hold_step_frames": {"value": 30, "comment": "保持中は n フレームごとと最終フレームを標本化する。各標本を最終姿勢の輪郭と比較するため、ゆっくりしたずれも標本化で見落とさない。"},
    "backlog_hold_reference_pct_h": {"value": 0.2, "comment": "報告専用。作業一覧の定義（docs/backlog_crosscheck.md 項目 3）から引用した参考値。プロジェクトの判定しきい値ではなく、tests/thresholds.json にも項目はない。測定変位と並べて報告するだけで、判定には使わない。"},
    "contact_sheet_step": {"value": 15, "comment": "仕様第 9 節のステップ 3。15 フレームごとに画像を 1 枚作る。"},
    "g3_n_sections": {"value": 9, "comment": "縁の厚さを測るために使う Y=一定の断面平面の数。"},
    "g3_y_percentiles": {"value": [10.0, 90.0], "comment": "断面を配置する、crest_rim 頂点の Y 座標のパーセンタイル範囲。"},
    "g3_tip_match_pct_h": {"value": 1.0, "comment": "解釈値。各断面の波頭先端が CAM_print から見える先端のこの距離以内（画像高に対する %）なら、その断面の縁を判定する。先細りの端の断面は報告のみ。"},
    "g3_normal_window_pct_H": {"value": 0.4, "comment": "縁の点における接線と内向き法線を求める対称弦の半長（断面に沿う、H に対する %）。"},
    "g3_exclude_pct_H": {"value": 0.5, "comment": "内接円の計算では、縁の点からこの弧長距離（H に対する %）より近い曲線点を使わない。比 0/0 が不安定なため。"},
    "g3_probe_offsets_pct_H": {"value": [-0.2, -0.1, 0.0, 0.1, 0.2], "comment": "内接円の直径は、縁の点をこれらの弧長（H に対する %）だけずらして求めた値の中央値とする。"},
    "g4_eps_rel_H": {"value": 1e-6, "comment": "三角形同士の交差検査の幾何学的許容値（H に対する比）。頂点と相手三角形の平面の距離がこれ未満なら接触とし、これより短い交差線分は無視する。"},
    "g4_min_plane_angle_deg": {"value": 0.1, "comment": "平面同士の角度がこの値未満の三角形組は、交差ではなく同一平面・接触として分類する。"},
    "g5_n_frames": {"value": 5, "comment": "再構築間で頂点位置をビット単位で比較するフレーム数。最初から最終フレームまで等間隔に選ぶ。"},
    "dup_vertex_eps_rel_H": {"value": 1e-6, "comment": "解釈値（test_mesh の有効性）。二つの頂点間の距離がこの H 比未満なら同じ位置とみなす（H=11 m では 0.011 mm）。同位置でも、長さゼロに潰れたメッシュ辺の連鎖でつながらない頂点は未溶接の重複（第二の面、溶接されていない継ぎ目）とする。先細りで潰れた行の同位置頂点はそのような辺でつながるため数えない。"},
    "dup_max_share_pct": {"value": 0.1, "comment": "解釈値（test_mesh の有効性）。検査フレームの頂点に占める未溶接の重複頂点の最大比率、および三角形に占める重複三角形の最大比率（退化しておらず、三頂点の位置が別の三角形と同じもの）。超えれば INVALID。2026-09-20 の測定では、正常な fixture（clip と lift_clip）と正式輪郭の掃引形状は、先細りの潰れた行に最大 9,003 の一致頂点があっても全検査フレームで 0/0。一方、複製面は 100 % / 65～99 %。0.1 % は 25,251 頂点のうち 25 に相当し、攻撃例より 3 桁小さい。波頂線に沿う一本の未溶接継ぎ目（1/443=0.23 %）も超える。"},
    "coincident_tri_pairs_max_share_pct": {"value": 0.5, "comment": "解釈値（test_mesh の有効性）。一つの G4 フレームで同位置・同一平面・接触する三角形組（共有頂点がなく、BVH 上で重なるが適切な交差でも退化でもないため G4 が無視する組）の最大数を、メッシュの三角形数に対する % で表す。超えれば INVALID。2026-09-20 の測定では正常 fixture の平坦な初フレームで 49,504 三角形中 6 組=0.012 %、その他は 0、正式輪郭の掃引形状も 0。複製面は 99,008 三角形中各フレーム 4,212～6,138 組=4.3～6.2 %（合計 15,048 組）。0.5 % は正常例の最大値の約 40 倍、攻撃例の最小値の約 1/8。"},
    "s7_report_max_ranges": {"value": 10, "comment": "各区間で一覧に出す失敗区間の最大数。"},
    "motion_frame_step": {"value": 1, "comment": "test_motion が評価するフレーム間隔（--frame-step）。1 以外では M5/M6 の合否判定に意味がなくなるため、許容値の変更と同様に判定結果へ NON-DEFAULT SETTINGS を付ける。"},
    "in_s7_false_max_share_pct": {"value": 35.0, "comment": "解釈値（有効性）。基礎輪郭で in_S7=false のため S7 から除外してよい区間の最大比率（輪郭区間の弧長に対する %、またはモデルの当該区間の標本数に対する %）。超えると S7 が区間を十分に覆わず、実行は INVALID。2026-09-20 の測定では正式基礎輪郭の内側円弧が 20.8 %、波背と波頭は 0 %、合成 fixture の内側円弧は 27.5 %。比率は T.<segment>.in_s7_false_share_pct / T.<segment>.model_samples_not_counted_share_pct に必ず記録する。"},
    "armpit_min_sagitta_pct_h": {"value": 0.5, "comment": "報告専用（S7 の裏面と腹部の分割）。脇は、波頭先端と最深点の間の内側円弧上で、先端と最深点を結ぶ直線から胴体側に最も離れた点とする。その距離がこの値（画像高に対する %）未満なら明確な脇がないため、分割結果を報告しない。"},
}

# 判定を変えない TEST_SETTINGS の項目（報告専用の量、出力形式）。それ以外の項目は必ず
# tests/thresholds.json の interpretations.test_settings に登録し、実行ごとに settings_audit で検査する。
REPORT_ONLY_SETTINGS = ("m6_backlog_half_window", "m6_backlog_exclude_window_s", "backlog_hold_s", "backlog_hold_step_frames",
                        "backlog_hold_reference_pct_h", "contact_sheet_step", "s7_report_max_ranges", "armpit_min_sagitta_pct_h")
# 報告専用の量にしか影響しない測定パラメータ。その他は interpretations.measure_params に登録する。
REPORT_ONLY_MEASURE_PARAMS = ("head_lobe_reversal_pct_h", "width_levels_H", "shape_levels_frac_h", "s8_vertex_short_windows_pct_h",
                              "s8_tip_report_zone_pct_h")
_SETTINGS_META_KEYS = ("comment", "provenance", "unit", "_doc", "_comment")
NON_DEFAULT_SUFFIX = " (NON-DEFAULT SETTINGS)"
NON_OFFICIAL_SUFFIX = " (NON-OFFICIAL INPUTS)"       # NON_DEFAULT_SUFFIX より前に付ける。固定の判定文字列を保つ。
EXIT_CODE_ERROR = 2
# 各テストの判定を変え得るシーン入力。輪郭を読むのは test_shape、fps を使うのは test_motion のみ。
RELEVANT_INPUTS = {"shape": ("contour", "H", "water_z"), "motion": ("H", "water_z", "fps"), "mesh": ("H", "water_z"),
                   "all": ("contour", "H", "water_z", "fps")}


class BuildScriptExit(RuntimeError):
    """構築スクリプトの読み込み中または実行中に sys.exit() / gw.bootstrap.finish() が呼ばれた。"""


def get_settings(overrides=None, with_sources=False):
    """平坦な {name: value} を返す。TEST_SETTINGS に params.json の任意の test_settings と --set を重ねる。

    params.json に項目がない場合だけを捕捉する。ファイル不正、test_settings がオブジェクトでない場合、
    params.json や --set に未知の設定名がある場合は例外とする。誤記で既定値を黙って使わないため。
    with_sources は設定値と設定元を返す。"""
    s = {k: (list(v["value"]) if isinstance(v["value"], list) else v["value"]) for k, v in TEST_SETTINGS.items()}
    src = {}
    try:
        extra = paths.param("test_settings")
    except KeyError:
        extra = None
    if extra is not None:
        if not isinstance(extra, dict):
            raise TypeError("params.json['test_settings'] はオブジェクト {name: value | {value: ..}} である必要があります。実際: %s" % type(extra).__name__)
        for k, v in extra.items():
            if k in _SETTINGS_META_KEYS:
                continue
            if k not in TEST_SETTINGS:
                raise ValueError("params.json['test_settings'] に未知のテスト設定 %r があります（既知: %s）" % (k, ", ".join(sorted(TEST_SETTINGS))))
            s[k] = v["value"] if isinstance(v, dict) and "value" in v else v
            src[k] = "params.json test_settings"
    for k, v in (overrides or {}).items():
        if k not in TEST_SETTINGS:
            raise ValueError("--set に未知のテスト設定 %r があります（既知: %s）" % (k, ", ".join(sorted(TEST_SETTINGS))))
        s[k] = v
        src[k] = "--set"
    return (s, src) if with_sources else s


def _same(a, b):
    try:
        if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
            return [float(v) for v in a] == [float(v) for v in b]
        if a is None or b is None or isinstance(a, (bool, str)) or isinstance(b, (bool, str)):
            return a == b
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def settings_audit(settings, sources=None, measure_params=None, effective=None):
    """判定に影響する許容値を tests/thresholds.json の interpretations と照合する。

    settings は get_settings() の結果、sources は with_sources=True の設定元。
    measure_params は pm.get_params() の結果で、None ならここで取得する。
    effective は --res-scale / --hold-frames / --frame-step などで直接置き換えた実効値と出典。
    結果の non_default は標準値からの差、unlisted はしきい値ファイルに未登録の判定関連設定、
    report_only_non_default は判定を変えない報告専用の変更を示す。
    この処理はしきい値を変更しない。使用値を記録・照合し、許容値の変更を見逃さないためにある。
    実際に --set jump_floor_frac_of_vmax=1.0 は 0.3 H の急変を M6 に通していた。"""
    sources = dict(sources or {})
    block = paths.load_thresholds().get("interpretations") or {}
    f_set, f_mp, f_lib = block.get("test_settings") or {}, block.get("measure_params") or {}, block.get("library_constants") or {}
    eff = {k: (v, None) for k, v in settings.items()}
    for k, (v, where) in (effective or {}).items():
        eff[k] = (v, where)
    non_default, unlisted, report_only = [], [], []
    for k in sorted(eff):
        v, where = eff[k]
        default = TEST_SETTINGS[k]["value"] if k in TEST_SETTINGS else None
        if k in REPORT_ONLY_SETTINGS:
            if not _same(v, default):
                report_only.append({"group": "test_settings", "name": k, "effective": v, "default": default, "source": where or sources.get(k, "?")})
            continue
        if k not in f_set:
            unlisted.append({"group": "test_settings", "name": k, "effective": v, "file_value": None,
                             "source": "thresholds.json の interpretations.test_settings に未登録"})
        elif not _same(v, f_set[k].get("value")):
            origin = where or sources.get(k) or ("common_test.TEST_SETTINGS の既定値が thresholds.json と異なる" if _same(v, default) else "?")
            non_default.append({"group": "test_settings", "name": k, "effective": v, "file_value": f_set[k].get("value"), "source": origin})
    P = measure_params if measure_params is not None else pm.get_params()
    nd_lib = P.get("non_default_params") or {}
    for k in sorted(P):
        if k in ("non_default_params",):
            continue
        v = P[k]
        if k == "s8_spacing_pct_h":
            continue                      # 独立した検査 S8.sample_spacing_pct_h（thresholds.json の等号判定）で評価する。
        src = (nd_lib.get(k) or {}).get("source")
        if k in REPORT_ONLY_MEASURE_PARAMS:
            if k in nd_lib:
                report_only.append({"group": "measure_params", "name": k, "effective": v, "default": nd_lib[k].get("default"), "source": src})
            continue
        if k not in f_mp:
            unlisted.append({"group": "measure_params", "name": k, "effective": v, "file_value": None,
                             "source": "thresholds.json の interpretations.measure_params に未登録"})
        elif not _same(v, f_mp[k].get("value")):
            non_default.append({"group": "measure_params", "name": k, "effective": v, "file_value": f_mp[k].get("value"),
                                "source": src or "profile_metrics.DEFAULT_PARAMS の既定値が thresholds.json と異なる"})
    for k, entry in sorted(f_lib.items()):
        mod_name, attr = k.split(".", 1)
        v = getattr({"silhouette": silhouette, "profile_metrics": pm}.get(mod_name), attr, None)
        if not _same(v, entry.get("value")):
            non_default.append({"group": "library_constants", "name": k, "effective": v, "file_value": entry.get("value"),
                                "source": "gw ライブラリの定数が thresholds.json と異なる"})
    return {"ok": not non_default and not unlisted, "non_default": non_default, "unlisted": unlisted,
            "report_only_non_default": report_only,
            "reference": "tests/thresholds.json の interpretations（進行管理者の解釈、ユーザーの確認待ち）"}


def _same_file(a, b):
    """二つのパスが同じファイルを示すか、解決済みパスで比較する。表記の違いは比較しない。"""
    ra, rb = os.path.normcase(os.path.realpath(str(a))), os.path.normcase(os.path.realpath(str(b)))
    if ra == rb:
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def inputs_audit(test_name, contour_path, H, water_z, fps, sources=None):
    """シーンを記述する入力がプロジェクトの正式値か照合する。

    --contour は解決済みパスで target/base_contour.json、H は params.json の WAVE_HEIGHT_M、
    静水面は 0（仕様第 4 節）、fps は params.json の fps と一致する必要がある。
    各テストの判定に影響する入力だけ比較する。自己検証は意図的に合成輪郭を使うため、
    差は実行エラーではないが、正式な受入検査でもない。判定に固定の接尾辞を付け終了コードを非ゼロにする。
    --final-frame / --frame-start / --phase-frames はシーンの記述であり、正式値とは比較せず、
    summary.scene_description に表示する。"""
    sources = dict(sources or {})
    rel = RELEVANT_INPUTS.get(test_name, RELEVANT_INPUTS["all"])
    items = []
    if "contour" in rel and contour_path is not None and not _same_file(contour_path, paths.BASE_CONTOUR_JSON):
        items.append({"name": "contour", "effective": paths.norm(contour_path), "official": paths.norm(paths.BASE_CONTOUR_JSON),
                      "source": sources.get("contour", "--contour")})
    if "H" in rel and H is not None:
        off = float(paths.param("WAVE_HEIGHT_M"))
        if float(H) != off:
            items.append({"name": "H_m", "effective": float(H), "official": off, "source": sources.get("H", "--H")})
    if "water_z" in rel and water_z is not None and float(water_z) != 0.0:
        items.append({"name": "water_z_m", "effective": float(water_z), "official": 0.0, "source": sources.get("water_z", "--water-z")})
    if "fps" in rel and fps is not None:
        off = float(paths.param("fps"))
        if float(fps) != off:
            items.append({"name": "fps", "effective": float(fps), "official": off, "source": sources.get("fps", "--fps")})
    return {"ok": not items, "non_official": items, "relevant": list(rel),
            "reference": "target/base_contour.json（解決済みパス）、params.json の WAVE_HEIGHT_M と fps、静水面 0（仕様第 4 節）"}


INTERPRETATION_NOTES = {
    "tiers": "すべての検査を tests/thresholds.json の二つの階層で判定する。spec は great_wave_blender_prompt.md の値、user_relaxed_5pct はユーザーの「5 %」発言を作業用に解釈した値で、ユーザーの確認待ち。",
    "S1": "ユーザーの確認待ちの解釈。波頂 X は最大画素ではなく profile_metrics の頑健な極値（許容値は画像高の 0.1 %）とする。仕様目標（38.2 % / 8.7 %）で判定し、基礎輪郭の波頂との差は情報としてのみ報告する。",
    "S2": "仕様目標（39.5 % / 46.3 %）とのユークリッド距離で判定する。dx、dz、基礎輪郭の最深点との差も報告する。",
    "S3": "画像高に対する百分率の差として 66.0 を中心に判定する（仕様階層は 64～68）。相対的な読み方（66±1.32）も元の数値から判定できる。2026-09-20 の強化で加えた、ユーザーの確認待ちの解釈。同じしきい値を使い、S3.height_err_pct_h は座標系の Z=0 から波頂まで、S3.from_model_trough.height_err_pct_h はモデル自身の谷底（最深点から輪郭右端までの最低 Z、profile_metrics の S3_from_model_trough）から波頂までを判定する。両方を表示し、悪い方が総合判定に反映される。理由：仕様は「谷から波頂までの高さ」と書く。波の前の海面を 3 % 持ち上げた例では、Z=0 からの値は +0.03 で合格しても、モデル自身の谷からは -2.97 になる。",
    "verdicts": "PASS は有効性を満たし、判定済み検査に失敗・測定不能がなく、対象 ID（S1～S8 / M1～M6 / G1～G5）の tests/thresholds.json 上の全検査を少なくとも一回判定した状態。INCOMPLETE は失敗がないが必要な検査に未判定がある状態（スキップや検査ゼロを含む）。FAIL は判定済み検査の失敗または NOT_MEASURABLE。INVALID は有効性条件を満たさず数値を信用できない状態。ERROR はスクリプト例外で、metrics.json にトレースバックを記録し終了コード 2。判定に影響する設定が tests/thresholds.json の interpretations と異なると、固定の接尾辞「 (NON-DEFAULT SETTINGS)」を付ける。正式な輪郭・H・水面・fps 以外の入力には「 (NON-OFFICIAL INPUTS)」を前に付け、各テストが使う入力だけ比較する。テスト本体の SystemExit は ERROR とし、終了コード 0 にはしない。終了コード 0 は接尾辞のない厳密な PASS のみ。",
    "validity": "ユーザーの確認待ちの解釈。有効性を失い INVALID となる条件。既存の「輪郭が不完全、未充填の穴、水面上 0 px、標的とモデルの区間分割不一致」に加え、2026-09-20 に次を強化した。(1) 検査フレームに非有限の頂点、またはそれによって落ちた三角形がある。(2) 斑点限界（全解像度で 25 px）より大きい独立シルエット成分を除去した。空洞内の障害物などを見逃さないため、境界枠も示す。(3) 前面が静水面に達しない（reached_still_water=false、許容値は画像高の 0.3 %）。この場合、S3 はモデルの届かない Z=0 までを測る。(4) in_S7=false により区間の 35 % 超が S7 から除外される。第二の強化では、(5) テストはビューポートの依存グラフを測るため、対象オブジェクト・モディファイアの表示状態や細分化段数がレンダー時と異なる場合は INVALID。test_shape、test_motion、test_mesh に適用し、対象名を記録する。(6) test_mesh では未溶接の重複頂点・重複三角形が 0.1 % を超える、または同位置・同一平面・接触三角形組が三角形数の 0.5 % を超えると INVALID。重なった第二の面が G1～G5 をすり抜けるのを防ぐ。",
    "report_only_shape": "報告専用で判定しない値。W.own_h.* は各輪郭自身の波頂高 h に対する形状記述子（0.25 / 0.5 / 0.75 h の断面、o/h、空洞深さ/h、縦横比）。胴体が広く低い場合も差が相殺されない。S7.<segment>.signed_* は法線方向の符号付き偏差（+ はモデルが標的の胴体外側）。S7.underside / S7.belly は内側円弧を脇（波頭先端と最深点を結ぶ直線から胴体側へ最も離れた点）で分割したもの。S1.crest_inside_painted_plateau / S1.height_on_x0_plumb_* は原画の波頂が約 4～5 % 幅の平坦部であるための補助値。S8.max_vertex_window_turn_deg は閉じた 1 % 窓で折れ線自身の頂点の曲がり角を報告する。正式な基礎輪郭自身がそこでは 19 度なので、15 度の判定はしない。すべてユーザーの判断待ち。",
    "S4": "三つの角度は報告専用であり、形状の判定は S7 に委ねる。「左端付近／中間／波頂の直前」の窓と、三つの真偽検査の許容値は profile_metrics の解釈（docs/measurement_definitions.md 第 3.1 節）で、ユーザーの確認待ち。",
    "S5": "目標は基礎輪郭の波頭先端（爪を除いた波頭の最右点）。向きは双方の輪郭に同じ profile_metrics の phi（先端から弧長 2～8 % H 手前の波頭表側の弦）を適用する。これを S5 と M4 の向きとするのはユーザーの確認待ちの解釈。波頂から先端への直線方向も両輪郭で S5.crest_to_tip_* として報告するが判定には使わない。",
    "S6": "外側の上限のみ。波頂と最深点の間の波胴体の最右点は 59.2 % より左でなければならない。前面の裾はここでいう「胴体」に含めないという解釈。",
    "S7": "区間ごとにモデル→基礎輪郭と基礎輪郭→モデルの両方向の最近距離を求め、各方向を別々に情報として表示し、悪い方を判定する。比較時は隣接区間へ 3 % の余白を入れる。基礎輪郭の in_S7=false（補完・遮蔽）点は数えない。作業一覧の定義にも両方向の要求がある。profile_metrics の解釈で、ユーザーの確認待ち。",
    "segmentation": "波頭先端は張り出した波頭全体の最右点。前面区間（波頂から静水面との最初の接点）で X の戻りが最大となる「先端→最深点」の組を選ぶ（profile_metrics の tip_rule=max_reversal、画像高の 0.3 % の戻りから張り出しとする）。モデルは常にこの検出で分割し、基礎輪郭は JSON の接合点で分割する。同じ検出を基礎輪郭にも適用する（T.seg_*）。JSON の接合点（波頂、先端）、またはそこから定まる最深点が検出結果から画像高の 0.2 % を超えて離れると、標的とモデルの分割が一致しないため FAIL ではなく INVALID とする。",
    "W": "しきい値のない報告専用項目で、ユーザーの判断待ち。Z=0.25 / 0.5 / 0.75 H の水平断面幅（x_back は波背の最左交点、画面外なら画像左端、x_inner は張り出し部分の前面の最左交点、x_front は前面の最右交点）、波頂の鉛直線からの距離、張り出し o、空洞深さ、輪郭と Z=0 の間の面積を、モデルと基礎輪郭について % 差とともに示す。理由：胴体の幅が 5～8 % 過大でも仕様階層の全検査を通過し得る（docs/records/step1_tests.md）。",
    "S8": "2026-09-20 以降は仕様を文字通り適用。標本間隔 1 %、4 位相で隣接標本の接線差を 15 度未満とし、波頭先端の除外区間は設けない（s8_tip_exclusion_pct_h=0）。残る解釈は、左端→先端と先端→谷端を区間内で別々に標本化し、先端そのものと両側の一間隔以内の全位相に追加接合点を置いて、その弦が先端をまたぐようにすること。2026-09-20 以前は先端から弧長 2 % 以内の接合点を判定から除いた。薄い縁を想定した進行管理者の解釈だったが、正式な大形状標的の先端は一標本当たり約 10 度しか回転せず、仕様に除外規定もないため、38 度の尖った先端が通過していた。旧指標は S8.max_tip_zone_excluded_deg として、tip_turn_deg、max_unexcluded_deg、tip_junction_deg と並べて報告だけを続ける。薄い縁を持つ合成 fixture（厚さ 2.5 % H、先端の回転は標本当たり約 67 度）は文字通りの S8 に合格できないため、その自己検証例だけで --measure-param を使って s8_tip_exclusion_pct_h=2 を明示し、標準設定との差として記録する。",
    "phases": "ユーザーの確認待ちの解釈。段階の境界はデータから検出する。張り出し段階は、先端が存在し o>0 の状態が以後続く最初のフレームから。巻き込み段階は phi(t) が最大のフレームから。動きの終わりは宣言された最終フレーム以前で輪郭が最後に動いたフレーム。--phase-frames A,B または params.json の motion_phase_frames は検出した A/B を置き換える。",
    "M2": "h は最初のフレームから張り出し前の最終フレームまで減少してはならない。theta_start は初フレーム、theta_end は張り出していない最後のフレームの theta とする。緩やかな傾斜から一気に張り出す場合も失敗するため。ノイズ下限未満の減少は 0 と判定する解釈で、元の値も報告する。",
    "M3": "張り出し段階では o が減少してはならない。h_drop=(段階開始時の h − 段階内の最小 h)/段階開始時の h。tip_crosses_crest_plumb は段階末で o>0、かつ段階内で波頭先端が -X へ後退していないことを示す。",
    "M4": "最初の巻き込みフレームから停止フレームまで phi は増加してはならない。ノイズ下限未満の増加は 0 と判定する。",
    "M5": "フレームの輪郭速度は前フレームとの pm.contour_displacement（両方向の最近点距離の最大、静水面に沿う区間は除外）とする。停止フレームは宣言された最終フレーム以前で最後に動いたフレーム。stop_speed_ratio はその速度／アニメーション全体の最大速度。「最後の一秒で緩やかに減速」には thresholds.json 上の数値しきい値がないため、窓内の速度 decel_* を報告するだけで判定しない。2026-09-20 の強化後、post_stop は最終フレーム後の全保持フレームについて、フレーム間および最終輪郭との比較（遅いずれの検出）の最大変位を取り、static_disp_eps_H の下限を適用する。シーンには min_hold_s=1 秒（30 fps で 30 フレーム）以上の保持が必要。短い保持で動きがなくても検査は NOT_JUDGED、総合は INCOMPLETE。短い保持中の動きは FAIL。以前の 3 フレーム外挿では、3 フレーム後のずれを見逃していた。--hold-frames N は最終後ちょうど N フレームを評価し、標準設定との差として記録する。N=0 は NOT_MEASURABLE で失敗扱い。最終フレームは --final-frame、次に scene['gw_final_frame']、最後に scene.frame_end の順に決める。",
    "M6": "ユーザーの確認待ちの解釈。フレーム組 k の急変比は d(k)/max(min(d(k−1),d(k+1)), floor)。floor は最大変位の 5 %。したがって変位は両隣の 3 倍未満でなければならず、ほぼ静止した隣接値を分母として使わない。これを仕様本文の判定用の読み方とし、作業一覧の別の読み方 M6_backlog は並べて報告する。",
    "M6_backlog": "報告専用でユーザーの判断待ち。docs/backlog_crosscheck.md 項目 2 の作業一覧は「停止への移行を除き、隣接フレームの中央値の 3 倍を超えない」とし、仕様本文は「隣接フレームの変位の 3 倍未満」とする。ratio(k)=d(k)/median(k の前後それぞれ m6_backlog_half_window=2 組の d) とし、下限値を置かない。停止前の最後の m6_backlog_exclude_window_s（M5 の減速窓、1 秒）内と停止後の組を除く。残った組の最大比を M6.backlog_jump_ratio として参考倍率 3 と並べる。",
    "hold_backlog": "報告専用でユーザーの判断待ち。docs/backlog_crosscheck.md 項目 3 の作業一覧は「静止姿勢を 10 秒保持し、輪郭移動を画像高の 0.2 % 以下」とするが、仕様 M5 は停止後に形状が変わらないとだけ記す。最終フレーム後の保持（backlog_hold_s=10 秒、30 fps で 300 フレーム。scene.frame_end を超えた分は Blender が外挿する）を backlog_hold_step_frames ごとに標本化し、最終輪郭と比較する。最大変位を M5.backlog_hold_max_disp_pct_h として参考値 0.2 % と並べる。判定には使わないが、2026-09-20 以降、参考値を超えると summary.md と GW RESULT 行に警告を出す。",
    "inputs": "正式でない入力の扱い（2026-09-20）。--contour の解決済みパスが target/base_contour.json でない、または H・静水面・fps が params.json の WAVE_HEIGHT_M・0・fps と異なる場合、判定に固定の接尾辞「 (NON-OFFICIAL INPUTS)」を付け、終了コードを非ゼロにする。各テストが使う入力だけ比較する。shape は輪郭・H・水面、motion は H・水面・fps（--fps がなければシーンの fps も）、mesh は H・水面。--final-frame、--frame-start、--phase-frames はシーンの記述なので summary.scene_description に出力し、差の印は付けない。",
    "evaluation_state": "テストはビューポートの依存グラフ（bpy.context.evaluated_depsgraph_get()）を評価し、show_viewport とビューポート細分化段数を用いる。gw.silhouette.viewport_render_mismatches() がビューポートとレンダーの状態が異なるモディファイアを列挙し、一件でもあれば INVALID（T.n_viewport_render_mismatches）。「Is Viewport」で分岐するノード群、評価モードを読むドライバ・ハンドラ、シーンの simplify 設定は検出できない。",
    "mesh_duplicates": "ユーザーの確認待ちの解釈（2026-09-20、test_mesh の有効性）。最終フレームと各 G4 フレームで、頂点位置を dup_vertex_eps_rel_H=1e-6 H の許容値で群分けする。同位置の頂点がすべて長さゼロの辺でつながらない群は、未溶接の重複（第二の面、未溶接の継ぎ目）を含み、T.n_duplicate_vertices に記録する。三頂点の位置が別の三角形と一致する非退化三角形は T.n_duplicate_triangles。同位置・同一平面・接触する三角形組（G4 が無視する BVH 上の重複組）は T.max_coincident_triangle_pairs。dup_max_share_pct=0.1 % または coincident_tri_pairs_max_share_pct=三角形数の 0.5 % を超えると INVALID。許容値より離れ、元の面にも触れない第二の面は検出できない。",
    "G1": "各フレームの評価済みメッシュで、頂点・辺・面・ループの数、面の辺数、ループ→頂点の添字、UV レイヤー名と UV 座標をハッシュ化し、初フレームと比較する。",
    "G2": "Hem は評価済みメッシュの境界辺（面がちょうど一枚だけ使う辺）の頂点。測定値は全フレームでの max |Z_world−water_z| を H に対する % で示す。",
    "G3": "ユーザーの確認待ちの解釈。縁の厚さは、断面（Y=一定）に内接し縁の点で接する最大円の直径。縁の点は両頂点が crest_rim 頂点グループに属するメッシュ辺と断面の交点。丸い縁では丸みの直径 2r となる。最終フレームで、断面の波頭先端が CAM_print に見える波頭先端と一致する断面を判定し、その最大値を採用する。",
    "G4": "mathutils BVHTree.overlap(tree, tree) で候補組を求める。頂点を共有する組は除く。両三角形の頂点が相手の平面の両側に厳密にあり、平面が平行でなく、交差線分が許容値より長い場合だけ自己交差とする。同位置・接触・退化した組は別に報告し、判定しないという解釈。",
    "G5": "構築スクリプトをこの処理内でシーンを初期化して再実行し、さらに新しい Blender プロセスでも実行する。複数フレームで、評価済み頂点位置の float32 バイト列とワールド変換行列をビット単位で比較する。",
}


# ------------------------------------------------------------------------------------ JSON 補助処理
def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (str, int, bool)) or o is None:
        return o
    return str(o)


def _parse_value(text):
    try:
        return json.loads(text)
    except Exception:
        return text


def parse_kv_list(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError("key=value 形式が必要です。実際: %r" % it)
        k, v = it.split("=", 1)
        out[k.strip()] = _parse_value(v.strip())
    return out


# ------------------------------------------------------------------------------------ コマンドライン
def add_common_args(ap):
    g = ap.add_argument_group("シーン")
    g.add_argument("--object", default=None, help="波メッシュのオブジェクト名。コンマ区切りで複数指定すると一つのシルエットを作る。最初のオブジェクトを G 系検査で調べる。既定値は構築関数の返り値、またはシーン唯一のメッシュ。")
    g.add_argument("--blend", default=None, help="開く .blend ファイル。Blender の --python より前に渡す方法も可。")
    g.add_argument("--build-script", default=None, help="シーン内に波を構築する Python ファイル。common_test.py の構築スクリプトの約束を参照。")
    g.add_argument("--build-func", default=None, help="呼び出す構築関数。既定値は build_for_tests、build、build_object のうち最初に存在するもの。")
    g.add_argument("--build-arg", action="append", default=[], metavar="KEY=VALUE", help="構築関数のキーワード引数。複数回指定でき、値は可能なら JSON として読み解く。")
    g.add_argument("--contour", default=None, help="基礎輪郭の JSON。既定値は target/base_contour.json。")
    g.add_argument("--frame-start", type=int, default=None, help="開始フレーム。既定値は scene.frame_start。")
    g.add_argument("--final-frame", type=int, default=None, help="最終姿勢のフレーム。既定値は scene.frame_end。")
    g.add_argument("--fps", type=float, default=None, help="一秒当たりのフレーム数。既定値はシーンのレンダー設定。")
    g.add_argument("--H", type=float, default=None, help="波高（m）。既定値は params.json の WAVE_HEIGHT_M。")
    g.add_argument("--water-z", type=float, default=0.0, help="静水面のワールド Z 座標。既定値は 0。")
    g.add_argument("--res-scale", type=float, default=None, help="マスク解像度倍率。既定値はテストごとに異なる。TEST_SETTINGS を参照。")
    o = ap.add_argument_group("出力")
    o.add_argument("--out-dir", default=None, help="結果ディレクトリ。既定値は results/<YYYYMMDD_HHMMSS>_<test>/。")
    o.add_argument("--tag", default=None, help="既定の結果ディレクトリ名の末尾に追加する文字列。")
    o.add_argument("--exit-tier", default="spec", choices=list(TIERS) + ["none"], help="終了コードを決める判定階層。両階層の結果は常に報告する。")
    o.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="TEST_SETTINGS の項目を上書きする。複数回指定できる。")
    o.add_argument("--measure-param", action="append", default=[], metavar="KEY=VALUE",
                   help="gw.profile_metrics.DEFAULT_PARAMS の測定パラメータを上書きする。複数回指定でき、未知の名前はエラー。判定に影響する変更には ' (NON-DEFAULT SETTINGS)' が付く。薄い縁の合成 fixture の自己検証だけで s8_tip_exclusion_pct_h=2 を用いる。")
    o.add_argument("--background-image", default="auto", choices=["auto", "painting", "white"], help="重ね画像の背景。auto は輪郭 JSON に画像名があれば原画、なければ白を使う。")
    return ap


# ------------------------------------------------------------------------------------ 実行コンテキスト
class Ctx:
    """テストに必要なシーン、オブジェクト、フレーム範囲、H、結果ディレクトリ、設定。"""

    def __init__(self):
        self.args = None
        self.test_name = None
        self.scene = None
        self.objs = []
        self.obj = None
        self.H = None
        self.F = None
        self.water_z = 0.0
        self.run_dir = None
        self.settings = None
        self.settings_sources = {}     # 上書きされた設定の出典
        self.builder = None            # callable(scene) -> object、または None
        self.source = {}
        self.frame_start = None
        self.final_frame = None
        self.fps = None
        self.contour_path = None
        self.background = "auto"
        self.untested_mesh_objects = []   # 検査対象のシルエットに含まれないメッシュ（報告専用）
        self.measure_overrides = {}       # --measure-param key=value
        self.measure_params = None        # この実行で有効な pm.get_params(measure_overrides) の測定設定
        self.input_sources = {}           # 各シーン入力値の出典
        self.scene_frame_end = None       # 準備時の scene.frame_end（test_motion の保持区間）

    def describe(self):
        return {
            "object": [o.name for o in self.objs], "source": self.source, "H_m": self.H, "water_z_m": self.water_z,
            "frame_start": self.frame_start, "final_frame": self.final_frame, "fps": self.fps,
            "scene_frame_end": self.scene_frame_end, "input_sources": dict(self.input_sources),
            "contour": None if self.contour_path is None else paths.norm(self.contour_path),
            "contour_is_official_target": None if self.contour_path is None else bool(_same_file(self.contour_path, paths.BASE_CONTOUR_JSON)),
            "contour_sha1": file_sha1(self.contour_path), "untested_mesh_objects": list(self.untested_mesh_objects),
            "blender": bootstrap.blender_version(), "numpy": np.__version__,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "thresholds_file": paths.norm(paths.THRESHOLDS_JSON),
            "settings": self.settings, "settings_sources": self.settings_sources,
            "measure_param_overrides": dict(self.measure_overrides),
            "evaluation": "ビューポートの依存グラフ（bpy.context.evaluated_depsgraph_get()）。解釈メモ evaluation_state を参照。",
            "command_line": bootstrap.script_args(),
        }

    def audit(self, effective=None, measure_params=None):
        """このコンテキストの settings_audit()。effective はコマンドラインで直接置き換えた設定。
        測定パラメータには --measure-param による上書きも含む。"""
        mp = measure_params if measure_params is not None else self.measure_params
        return settings_audit(self.settings, self.settings_sources, mp, effective)

    def inputs(self, test_name=None):
        """指定テストの入力を inputs_audit() で検査する。未指定ならこのコンテキストのテスト。"""
        return inputs_audit(test_name or self.test_name, self.contour_path, self.H, self.water_z, self.fps, self.input_sources)

    def scene_description(self, **extra):
        """正式値との比較対象ではないシーンの記述情報。判定結果の欄にも表示する。"""
        d = {"frame_start": self.frame_start, "frame_start_source": self.input_sources.get("frame_start"),
             "final_frame": self.final_frame, "final_frame_source": self.input_sources.get("final_frame"),
             "scene_frame_end": self.scene_frame_end, "fps": self.fps, "fps_source": self.input_sources.get("fps"),
             "H_m": self.H, "water_z_m": self.water_z, "objects": [o.name for o in self.objs]}
        d.update(extra)
        return d


def file_sha1(path):
    """ファイルの SHA-1。読めない場合は None。結果と標的ファイルの厳密な対応付けに用いる。"""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except (OSError, TypeError):
        return None


def untested_objects_report(ctx):
    """報告専用。構築スクリプトや .blend には検査対象より多くのメッシュがあり得る。
    シルエットに入るのは構築関数が返すオブジェクト、または --object で挙げたものだけ。
    別オブジェクトとして空洞内に置かれた物体は検査から見えない。
    T.n_untested_mesh_objects の記録と、必要なら注意文を返す。"""
    names = list(ctx.untested_mesh_objects)
    rec = report_value("T", "n_untested_mesh_objects", len(names), "count",
                       note="シーン内で検査対象のシルエットに含まれないメッシュ%s。波の一部か判別できないため、この数だけでは判定しない"
                            % ("" if not names else ": " + ", ".join(names[:10])))
    note = None if not names else ("注意（この項目だけでは判定しない）：シーン内に検査対象外: %s（計 %d 個）があります。シルエットに含めたオブジェクトは %s だけです。波の一部なら --object a,b で追加してください。"
                                   % (", ".join(names[:10]), len(names), ", ".join(o.name for o in ctx.objs)))
    return rec, note


def resolve_path(p):
    """入力ファイルの絶対パス。絶対指定、作業ディレクトリ基準、プロジェクトルート基準の順に探す。
    その他の代替先は使わず、存在しない場合は後続処理で例外とする。"""
    if p is None:
        return None
    p = str(p)
    if os.path.isabs(p) or os.path.exists(p):
        return paths.norm(p)
    cand = os.path.join(paths.PROJECT_ROOT, p)
    return paths.norm(cand) if os.path.exists(cand) else paths.norm(p)


def load_builder(script_path, func_name=None, build_args=None):
    """構築関数と、その出典情報を返す。"""
    script_path = paths.require_file(resolve_path(script_path))
    mod_name = "gw_builder_" + hashlib.sha1(script_path.encode("utf-8")).hexdigest()[:10]
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        d = os.path.dirname(script_path)
        if d not in sys.path:
            sys.path.insert(0, d)
        spec = importlib.util.spec_from_file_location(mod_name, script_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except SystemExit as exc:                  # module-level sys.exit() / bootstrap.finish() of the build script
            sys.modules.pop(mod_name, None)
            raise BuildScriptExit("構築スクリプトの読み込み中に sys.exit(%r) が呼ばれました（%s）。モジュール直下のコードは処理を終了させてはなりません。何も構築・検査していません"
                                  % (exc.code, script_path)) from exc
    names = [func_name] if func_name else ["build_for_tests", "build", "build_object"]
    func = None
    for nm in names:
        if hasattr(mod, nm):
            func, func_name = getattr(mod, nm), nm
            break
    if func is None:
        raise AttributeError("構築スクリプト %s に候補関数 %s がありません" % (script_path, names))
    kwargs = dict(build_args or {})

    def _build(scene):
        # このプロジェクトの単独スクリプトは sys.exit(0) / gw.bootstrap.finish(True, ..) で終わることがある。
        # 構築関数がそれを行うと検査前に終了コード 0 となるため、ここで SystemExit を捕捉し、
        # 原因を示す通常の例外へ変える。guarded_main が ERROR（終了コード 2）として記録する。
        try:
            ret = func(scene, **kwargs)
        except SystemExit as exc:
            raise BuildScriptExit("構築スクリプト %s の %s() 内で sys.exit(%r) が呼ばれました。構築関数は処理を終了せず、オブジェクトまたは None を返す必要があります（gw.bootstrap.finish() は sys.exit を呼ぶ）。検査は実行されていません"
                                  % (script_path, func_name, exc.code)) from exc
        if isinstance(ret, (tuple, list)):
            ret = ret[0] if ret else None
        return ret

    return _build, {"build_script": script_path, "build_func": func_name, "build_args": kwargs}


def _mesh_objects(scene):
    return [o for o in scene.objects if o.type == "MESH"]


def resolve_objects(scene, names, built=None):
    if names:
        objs = []
        for nm in [n.strip() for n in names.split(",") if n.strip()]:
            ob = scene.objects.get(nm)
            if ob is None:
                raise KeyError("オブジェクト %r がシーンにありません（メッシュ: %s）"
                               % (nm, ", ".join(o.name for o in _mesh_objects(scene)) or "none"))
            objs.append(ob)
        return objs
    if built is not None and hasattr(built, "name"):
        return [built]
    meshes = _mesh_objects(scene)
    if len(meshes) == 1:
        return meshes
    raise KeyError("--object の指定が必要です。シーンには %d 個のメッシュがあります（%s）"
                   % (len(meshes), ", ".join(o.name for o in meshes)))


def run_dir_from_args(args, test_name):
    """一回の実行結果のディレクトリ。--out-dir、なければ日時とテスト名から作成する。"""
    if getattr(args, "out_dir", None):
        return paths.ensure_dir(args.out_dir)
    name = test_name if not getattr(args, "tag", None) else "%s_%s" % (test_name, args.tag)
    return paths.results_run_dir(name)


def setup_context(args, test_name, run_dir=None):
    """共通引数に従ってシーンを開くか構築し、Ctx を返す。
    run_dir は guarded_main() が用意した結果先。None ならここで引数から求める。"""
    import bpy
    ctx = Ctx()
    ctx.args = args
    ctx.test_name = test_name
    if run_dir is None:
        run_dir = run_dir_from_args(args, test_name)
    ctx.run_dir = paths.ensure_dir(run_dir)
    ctx.settings, ctx.settings_sources = get_settings(parse_kv_list(getattr(args, "set", [])), with_sources=True)
    ctx.measure_overrides = parse_kv_list(getattr(args, "measure_param", []) or [])
    ctx.measure_params = pm.get_params(ctx.measure_overrides or None)          # 未知の名前は構築前のここで例外となる。
    ctx.water_z = float(args.water_z)
    ctx.background = getattr(args, "background_image", "auto")
    src = {"blend": None, "build_script": None}
    if args.blend:
        blend = paths.require_file(resolve_path(args.blend))
        if paths.norm(bpy.data.filepath or "") != blend:
            bpy.ops.wm.open_mainfile(filepath=blend)
        src["blend"] = blend
    elif bpy.data.filepath:
        src["blend"] = paths.norm(bpy.data.filepath)
    built = None
    if args.build_script:
        ctx.builder, binfo = load_builder(args.build_script, args.build_func, parse_kv_list(args.build_arg))
        src.update(binfo)
        if not src["blend"]:
            bootstrap.reset_scene()
        with bootstrap.Timer("build script %s" % os.path.basename(binfo["build_script"])):
            built = ctx.builder(bpy.context.scene)
    ctx.scene = bpy.context.scene
    ctx.source = src
    ctx.objs = resolve_objects(ctx.scene, args.object, built)
    ctx.obj = ctx.objs[0]
    ctx.untested_mesh_objects = [o.name for o in _mesh_objects(ctx.scene) if o.name not in [t.name for t in ctx.objs]]
    ctx.H = float(args.H) if args.H is not None else float(paths.param("WAVE_HEIGHT_M"))
    ctx.F = gw_frame.Frame.from_params(wave_height_m=ctx.H)
    ctx.frame_start = int(args.frame_start) if args.frame_start is not None else int(ctx.scene.frame_start)
    # 最終フレームは --final-frame、次に構築関数が宣言した scene['gw_final_frame']、最後に scene.frame_end。
    # 最終姿勢を保持するシーンは frame_end が最終フレームより後なので、最終フレームの宣言が必要。
    declared = ctx.scene.get("gw_final_frame") if hasattr(ctx.scene, "get") else None
    if args.final_frame is not None:
        ctx.final_frame, src_ff = int(args.final_frame), "--final-frame"
    elif declared is not None:
        ctx.final_frame, src_ff = int(declared), "scene['gw_final_frame']（構築関数または .blend による宣言）"
    else:
        ctx.final_frame, src_ff = int(ctx.scene.frame_end), "scene.frame_end（その後の保持フレームなし）"
    ctx.scene_frame_end = int(ctx.scene.frame_end)
    ctx.fps = float(args.fps) if args.fps is not None else float(ctx.scene.render.fps) / float(ctx.scene.render.fps_base)
    ctx.contour_path = resolve_path(args.contour) if args.contour else paths.BASE_CONTOUR_JSON
    ctx.input_sources = {"H": "--H" if args.H is not None else "params.json WAVE_HEIGHT_M", "water_z": "--water-z",
                         "fps": "--fps" if args.fps is not None else "シーンのレンダー fps（--fps 未指定）",
                         "contour": "--contour" if args.contour else "既定の target/base_contour.json",
                         "frame_start": "--frame-start" if args.frame_start is not None else "scene.frame_start", "final_frame": src_ff}
    log("[%s] オブジェクト=%s H=%.3f m フレーム %d..%d（最終フレームの出典 %s、scene.frame_end %d）fps=%.3g 結果先=%s"
        % (test_name, ",".join(o.name for o in ctx.objs), ctx.H, ctx.frame_start, ctx.final_frame, src_ff, ctx.scene_frame_end, ctx.fps, ctx.run_dir))
    return ctx


def evaluation_state_report(ctx):
    """有効性（2026-09-20 の第二の強化）。テストはビューポートの依存グラフを評価する。
    対象オブジェクトのモディファイアや表示状態がレンダー時と異なれば、レンダーやレンダーモードの
    Alembic 書き出しは測定とは別の形状を出す。レンダー専用の Displace で H の 10 % ずらしても、
    以前の検査値は正常例と同じだった。T.n_viewport_render_mismatches、注意文、有効性を返す。"""
    items = silhouette.viewport_render_mismatches(list(ctx.objs))
    rec = report_value("T", "n_viewport_render_mismatches", len(items), "count",
                       note="ビューポートとレンダーの状態が異なるモディファイア・オブジェクト。テストはビューポートの依存グラフを評価する。0 件を超えると INVALID%s"
                            % ("" if not items else "：" + "; ".join("%s / %s" % (d["object"], d["modifier"] or "オブジェクトの表示フラグ") for d in items[:10])))
    notes = []
    if items:
        notes.append("ビューポートとレンダーの状態が異なります。テスト対象の %d 件のモディファイアまたは表示フラグが両モードで一致しません：%s。"
                     "レンダーやレンダーモードの Alembic 書き出しでは測定時と別の形状になるため、この実行値を納品メッシュの評価には使えません。"
                     % (len(items), "; ".join("オブジェクト '%s' の %s：%s（ビューポート %s、レンダー %s）"
                                              % (d["object"], ("モディファイア '%s' [%s]" % (d["modifier"], d["type"])) if d["modifier"] else "オブジェクト本体",
                                                 d["what"], d["viewport"], d["render"]) for d in items[:10])))
    return rec, notes, not items


def rebuild_scene(ctx):
    """シーンを初期化して構築関数を再実行する（G5）。オブジェクト一覧を返す。"""
    import bpy
    if ctx.builder is None:
        raise RuntimeError("構築スクリプトが指定されていません")
    if ctx.source.get("blend"):
        bpy.ops.wm.open_mainfile(filepath=ctx.source["blend"])
    else:
        bootstrap.reset_scene()
    built = ctx.builder(bpy.context.scene)
    ctx.scene = bpy.context.scene
    ctx.objs = resolve_objects(ctx.scene, ctx.args.object, built)
    ctx.obj = ctx.objs[0]
    return ctx.objs


# ------------------------------------------------------------------------------------ 検査
def _status(tier_res, info_only, not_judged=False):
    if info_only:
        return "INFO"
    if tier_res["limit"] is None:
        return "REPORT"
    if not_judged:
        return "NOT_JUDGED"
    if tier_res["pass"] is None:
        return "NOT_MEASURABLE"
    return "PASS" if tier_res["pass"] else "FAIL"


def make_check(test, check, measured, sub=None, target=None, difference=None, where=None, note=None,
               raw=None, info_only=False, label=None, not_judged=False):
    """検査一件分の記録。限界値と比較条件は tests/thresholds.json だけから取得する。

    measured は数値・真偽値・None。None は測定不能で NOT_MEASURABLE（失敗扱い）。
    not_judged=True はシーンに必要な情報がない場合（例：M5 の保持が 1 秒未満）。両階層で
    NOT_JUDGED とし、他の失敗がなければ総合は INCOMPLETE。理由を note に書く。
    sub は S7 の区間名など。target は比較対象、difference は測定値と目標値の差。
    where は測定位置、raw はノイズ下限処理前の値。info_only は情報用で判定には含めない。"""
    m = None if measured is None else (float(int(measured)) if isinstance(measured, (bool, np.bool_)) else float(measured))
    if m is not None and not math.isfinite(m):
        m = None
    res = paths.check_threshold(test, check, m)
    entry = paths.load_thresholds()[test]["checks"][check]
    rid = "%s.%s" % (test, check) if sub is None else "%s.%s.%s" % (test, sub, check)
    rec = {"id": rid, "test": test, "sub": sub, "check": check, "label": label or entry.get("comment"),
           "measured": m, "raw": raw, "target": target, "difference": difference, "unit": res["unit"], "op": res["op"],
           "provenance": res["provenance"], "info_only": bool(info_only), "tiers": {}, "where": where, "note": note}
    for t in TIERS:
        tr = dict(res["tiers"][t])
        tr["status"] = _status(tr, info_only, not_judged)
        if tr["status"] == "NOT_JUDGED":
            tr["pass"] = None
        rec["tiers"][t] = tr
    return rec


def report_value(test, name, value, unit=None, note=None, where=None, sub=None, target=None, difference=None, label=None):
    """thresholds.json に項目がない報告専用の量。判定しない。"""
    rid = "%s.%s" % (test, name) if sub is None else "%s.%s.%s" % (test, sub, name)
    v = value
    if isinstance(v, (bool, np.bool_)):
        v = bool(v)
    elif v is not None and not isinstance(v, (str, list, dict)):
        v = float(v)
        if not math.isfinite(v):
            v = None
    rec = {"id": rid, "test": test, "sub": sub, "check": name, "label": label, "measured": v, "raw": None,
           "target": target, "difference": difference, "unit": unit, "op": "report", "provenance": None, "info_only": True,
           "tiers": {t: {"limit": None, "pass": None, "margin": None, "status": "REPORT"} for t in TIERS},
           "where": where, "note": note}
    return rec


EXPECTED_IDS = {"shape": ["S%d" % i for i in range(1, 9)], "motion": ["M%d" % i for i in range(1, 7)],
                "mesh": ["G%d" % i for i in range(1, 6)]}
EXPECTED_IDS["all"] = EXPECTED_IDS["shape"] + EXPECTED_IDS["motion"] + EXPECTED_IDS["mesh"]
JUDGED_STATES = ("PASS", "FAIL", "NOT_MEASURABLE")


def expected_checks(test_ids):
    """指定テスト ID の下で、thresholds.json に限界値を持つ検査名の一覧。"""
    T = paths.load_thresholds()
    out = []
    for tid in test_ids or []:
        for name, entry in T[tid]["checks"].items():
            if entry.get("value") is not None:
                out.append("%s.%s" % (tid, name))
    return out


def validate_names(given, allowed, what):
    """--only / --skip / --cases の名前を検証する。未知の名前は ERROR。
    誤記で検査ゼロとなった実行を PASS と誤認しないため。正規表記の名前一覧を返す。"""
    canon = {str(a).lower(): a for a in allowed}
    out, bad = [], []
    for g in given:
        g = str(g).strip()
        if not g:
            continue
        if g.lower() in canon:
            out.append(canon[g.lower()])
        else:
            bad.append(g)
    if bad:
        raise ValueError("%s に未知の名前 %s が指定されました（使用可能: %s）" % (what, ", ".join(repr(b) for b in bad), ", ".join(str(a) for a in allowed)))
    return out


def summarize(checks, validity_ok=True, validity_notes=None, skipped=None, expected=None, audit=None, errors=None,
              inputs=None, warnings=None, scene_description=None):
    """階層ごとの判定結果を作る。固定の値は PASS / FAIL / INVALID / INCOMPLETE / ERROR。

    INVALID は有効性条件を満たさず数値を信用できない状態。FAIL は有効だが検査の失敗や
    NOT_MEASURABLE がある状態。INCOMPLETE は失敗がないが必要な検査が未判定、または
    判定済み検査がゼロの状態。PASS は有効で必要な全検査を判定し失敗がない状態。
    ERROR は run_all の個別テストに例外がある状態。判定に影響する設定が標準値と異なれば
    固定の接尾辞 ' (NON-DEFAULT SETTINGS)' が付く。正式でない入力には
    ' (NON-OFFICIAL INPUTS)' が付く。終了コード 0 は厳密な PASS のみ。"""
    out = {"validity_ok": bool(validity_ok), "validity_notes": list(validity_notes or []), "skipped": list(skipped or []),
           "expected_ids": list(expected or []), "errors": list(errors or [])}
    flagged = bool(audit and (audit.get("non_default") or audit.get("unlisted")))
    out["non_default_settings"] = [] if not audit else list(audit.get("non_default") or []) + list(audit.get("unlisted") or [])
    out["report_only_non_default_settings"] = [] if not audit else list(audit.get("report_only_non_default") or [])
    exp = expected_checks(expected)
    for t in TIERS:
        failed = [c["id"] for c in checks if c["tiers"][t]["status"] == "FAIL"]
        nm = [c["id"] for c in checks if c["tiers"][t]["status"] == "NOT_MEASURABLE"]
        passed = [c["id"] for c in checks if c["tiers"][t]["status"] == "PASS"]
        judged = set("%s.%s" % (c["test"], c["check"]) for c in checks if c["tiers"][t]["status"] in JUDGED_STATES)
        missing = [e for e in exp if e not in judged]
        if errors:
            base = "ERROR"
        elif not validity_ok:
            base = "INVALID"
        elif failed or nm:
            base = "FAIL"
        elif not judged or missing:
            base = "INCOMPLETE"
        else:
            base = "PASS"
        out[t] = {"verdict": base + (NON_DEFAULT_SUFFIX if flagged else ""), "verdict_base": base, "n_pass": len(passed), "n_fail": len(failed),
                  "n_not_measurable": len(nm), "n_judged": len(passed) + len(failed) + len(nm), "failed": failed, "not_measurable": nm,
                  "expected_not_judged": missing}
    return out


def failing_ids(result, tier="spec", include_not_measurable=True):
    s = result["summary"][tier]
    ids = list(s["failed"]) + (list(s["not_measurable"]) if include_not_measurable else [])
    if not result["summary"]["validity_ok"]:
        ids.append("VALIDITY")
    return sorted(set(ids))


def _fmt(v, nd=4):
    if v is None:
        return "該当なし"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return ("%." + str(nd) + "g") % v
    if isinstance(v, dict):
        return json.dumps(jsonable(v), ensure_ascii=True)
    return str(v)


def _where_text(w):
    if not w:
        return ""
    parts = []
    for k in ("segment", "frame", "frames"):
        if w.get(k) is not None:
            parts.append("%s=%s" % (k, w[k]))
    if w.get("s_pct_h") is not None:
        parts.append("s=%.1f%%" % w["s_pct_h"])
    if w.get("s_range_pct_h") is not None:
        parts.append("s=%.1f..%.1f%%" % tuple(w["s_range_pct_h"]))
    if w.get("px") is not None:
        parts.append("px=(%.0f,%.0f)" % tuple(w["px"]))
    if w.get("world_m") is not None:
        parts.append("xyz=(%.2f,%.2f,%.2f)m" % tuple(w["world_m"]))
    if w.get("n_ranges"):
        parts.append("%d 区間" % w["n_ranges"])
    return " ".join(parts)


def log_checks(checks, title):
    log("---- %s" % title)
    for c in checks:
        st = " ".join("%s:%s" % (t, c["tiers"][t]["status"]) for t in TIERS)
        lim = "/".join(_fmt(c["tiers"][t]["limit"]) for t in TIERS)
        extra = ""
        if c.get("target") is not None and not isinstance(c["target"], dict):
            extra += " 目標=%s" % _fmt(c["target"])
        if c.get("raw") is not None:
            extra += " 元値=%s" % _fmt(c["raw"])
        wt = _where_text(c.get("where"))
        tsc = c.get("target_self_check")
        if tsc and tsc["spec"] in ("FAIL", "NOT_MEASURABLE"):
            extra += " 目標輪郭の自己照合=%s(%s)" % (_fmt(tsc["measured"]), tsc["spec"])
        log("%-34s 実測=%-11s %s 限界値(%s)=%s [%s]%s%s" % (c["id"], _fmt(c["measured"]), st, c["op"], lim, c["unit"] or "",
                                                          extra, (" @ " + wt) if wt else ""))


def summary_markdown(result):
    """一回のテスト結果を Markdown 表にまとめ、metrics.json の隣に書く。"""
    L = ["# %s  (%s)" % (result["test"], result["context"].get("created", "")), ""]
    s = result["summary"]
    L.append("- 判定: " + ", ".join("`%s` = **%s**" % (t, s[t]["verdict"]) for t in TIERS))
    L.append("- 有効性: %s %s" % ("OK" if s["validity_ok"] else "**NOT OK**", "; ".join(s["validity_notes"])))
    if s.get("skipped"):
        L.append("- 判定対象外: " + ", ".join(s["skipped"]))
    miss = s.get(TIERS[0], {}).get("expected_not_judged") or []
    if miss:
        L.append("- **判定すべき項目が未判定（失敗がなければ INCOMPLETE）**: " + ", ".join(miss))
    if s.get(TIERS[0], {}).get("n_judged") == 0:
        L.append("- **判定済み項目がありません**: 判定項目がゼロの実行は PASS としません")
    for d in s.get("non_default_settings") or []:
        L.append("- **標準設定から変更** `%s.%s` = %s（tests/thresholds.json の解釈値: %s、設定元: %s）"
                 % (d["group"], d["name"], _fmt(d["effective"]), _fmt(d["file_value"]), d["source"]))
    for d in s.get("report_only_non_default_settings") or []:
        L.append("- 報告専用の値のみに影響する設定変更: `%s.%s` = %s（標準値: %s、設定元: %s）"
                 % (d["group"], d["name"], _fmt(d["effective"]), _fmt(d.get("default")), d["source"]))
    if result.get("error"):
        L += ["", "## エラー", "", "`%s: %s`" % (result["error"]["type"], result["error"]["message"]), "", "```", result["error"]["traceback"].rstrip(), "```"]
    if result.get("test") == "all":
        for e in s.get("errors") or []:
            L.append("- **個別テストのエラー** %s" % e)
    L += ["", "| 指標 ID | 実測値 | 目標値 | 差 | 単位 | 比較演算子 | 仕様の限界値 | 仕様判定 | 5% の限界値 | 5% 判定 | 位置・備考 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in result["checks"]:
        ts, tr = c["tiers"][TIERS[0]], c["tiers"][TIERS[1]]
        note = _where_text(c.get("where"))
        if c.get("raw") is not None:
            note = ("元値=%s " % _fmt(c["raw"])) + note
        tsc = c.get("target_self_check")
        if tsc and tsc["spec"] in ("FAIL", "NOT_MEASURABLE"):
            note = ("**目標輪郭の自己照合: %s (%s)** " % (_fmt(tsc["measured"]), tsc["spec"])) + note
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["id"], _fmt(c["measured"]), _fmt(c["target"]), _fmt(c["difference"]), c["unit"] or "", c["op"],
            _fmt(ts["limit"]), ts["status"], _fmt(tr["limit"]), tr["status"], note.replace("|", "/")))
    L.append("")
    return "\n".join(L)


def write_result(ctx_or_dir, result):
    """実行先に metrics.json と summary.md を書き、metrics.json のパスを返す。"""
    run_dir = ctx_or_dir.run_dir if isinstance(ctx_or_dir, Ctx) else ctx_or_dir
    p = paths.write_json(os.path.join(run_dir, "metrics.json"), jsonable(result))
    md = paths.ensure_parent(os.path.join(run_dir, "summary.md"))
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(summary_markdown(result))
    return p


def exit_code(result, exit_tier="spec"):
    """指定階層が厳密に PASS のときだけ 0。いずれかが ERROR なら 2、それ以外は 1。
    --exit-tier none は結果の数値だけを求める指定で、ERROR 以外は 0。結果行に NONE と示す。"""
    s = result["summary"]
    if any(s[t].get("verdict_base", s[t]["verdict"]) == "ERROR" for t in TIERS):
        return EXIT_CODE_ERROR
    if exit_tier == "none":
        return 0
    return 0 if s[exit_tier]["verdict"] == "PASS" else 1


def finish(result, exit_tier="spec"):
    """判定をログに記録し、RUNNING 印を除き、exit_code() の終了コードで Blender を終える。"""
    s = result["summary"]
    line = " ".join("%s=%s" % (t, s[t]["verdict"]) for t in TIERS)
    for t in TIERS:
        if s[t]["failed"] or s[t]["not_measurable"]:
            log("[%s] %s 失敗: %s%s" % (result["test"], t, ", ".join(s[t]["failed"]) or "-",
                                          ("；測定不能: " + ", ".join(s[t]["not_measurable"])) if s[t]["not_measurable"] else ""))
    miss = s[TIERS[0]].get("expected_not_judged") or []
    if miss:
        log("[%s] 判定すべき項目が未判定: %s" % (result["test"], ", ".join(miss)))
    for d in s.get("non_default_settings") or []:
        log("[%s] 標準設定との差 %s.%s = %s（thresholds.json の解釈値: %s、出典: %s）"
            % (result["test"], d["group"], d["name"], _fmt(d["effective"]), _fmt(d["file_value"]), d["source"]))
    code = exit_code(result, exit_tier)
    word = "ERROR" if code == EXIT_CODE_ERROR else ("NONE" if exit_tier == "none" else ("PASS" if code == 0 else "FAIL"))
    if result.get("run_dir"):
        end_run(result["run_dir"])
    log("RESULT %s %s %s（終了判定階層: %s、終了コード %d）-> %s" % (word, result["test"], line, exit_tier, code, result.get("run_dir", "")))
    sys.stdout.flush()
    sys.exit(code)


# ------------------------------------------------------------------------------------ 実行先と異常終了対策
RUNNING_MARKER = "RUNNING"
_STALE_EXACT = ("metrics.json", "summary.md", "contact_sheet.png", "g2_hem.png", "g3_sections.png", "g4_intersections.png",
                "g5_subprocess.log", "g5_subprocess_vertices.npz", RUNNING_MARKER)
_STALE_PREFIX = ("overlay_", "crop_", "plot_")


def begin_run(run_dir, test_name="?"):
    """古い結果を今回の結果と誤認しないよう、実行先を準備する。
    既存の出力や前回残った RUNNING 印を stale_<stamp>_<name> に改名してから、新しい RUNNING 印を書く。
    end_run() が印を除く。実行後も印が残れば処理が途中終了したことを示す。退避したファイル名を返す。"""
    run_dir = paths.ensure_dir(run_dir)
    stamp = paths.timestamp()
    renamed = []
    for fn in sorted(os.listdir(run_dir)):
        full = os.path.join(run_dir, fn)
        if not os.path.isfile(full) or fn.startswith("stale_"):
            continue
        if fn in _STALE_EXACT or (fn.startswith(_STALE_PREFIX) and fn.endswith(".png")):
            new, k = os.path.join(run_dir, "stale_%s_%s" % (stamp, fn)), 1
            while os.path.exists(new):
                new, k = os.path.join(run_dir, "stale_%s_%d_%s" % (stamp, k, fn)), k + 1
            os.replace(full, paths.assert_writable(new))
            renamed.append(os.path.basename(new))
    with open(paths.assert_writable(os.path.join(run_dir, RUNNING_MARKER)), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("テスト %s 開始 %s、プロセス ID %d\nこのファイルは ERROR で終わる場合も含め、実行終了時に削除されます。残っている場合は処理が途中で停止しています。"
                 "隣の metrics.json は完了した実行の結果ではありません。\n"
                 % (test_name, _dt.datetime.now().isoformat(timespec="seconds"), os.getpid()))
    if renamed:
        log("[%s] 結果先に古い出力がありました。%d 件を stale_%s_* へ改名しました" % (test_name, len(renamed), stamp))
    return renamed


def end_run(run_dir):
    p = os.path.join(run_dir, RUNNING_MARKER)
    if os.path.isfile(p):
        os.remove(paths.assert_writable(p))


def error_result(test_name, run_dir, exc, tb, context=None):
    """例外で終わった実行の結果。両階層とも ERROR とし、トレースバックを含める。"""
    summ = {"validity_ok": False, "validity_notes": ["ERROR: テストスクリプトで %s が発生しました: %s" % (type(exc).__name__, exc)], "skipped": [],
            "expected_ids": list(EXPECTED_IDS.get(test_name, [])), "errors": ["%s: %s" % (type(exc).__name__, exc)],
            "non_default_settings": [], "report_only_non_default_settings": []}
    for t in TIERS:
        summ[t] = {"verdict": "ERROR", "verdict_base": "ERROR", "n_pass": 0, "n_fail": 0, "n_not_measurable": 0, "n_judged": 0,
                   "failed": [], "not_measurable": [], "expected_not_judged": expected_checks(EXPECTED_IDS.get(test_name, []))}
    ctxd = dict(context or {})
    ctxd.setdefault("created", _dt.datetime.now().isoformat(timespec="seconds"))
    ctxd.setdefault("command_line", bootstrap.script_args())
    return {"schema": RESULT_SCHEMA, "test": test_name, "run_dir": run_dir, "context": ctxd, "checks": [], "summary": summ,
            "error": {"type": type(exc).__name__, "message": str(exc), "traceback": tb}, "outputs": {}}


def guarded_main(test_name, args, body):
    """各テスト main() の異常終了対策。結果先を準備し、本体を実行して終了処理へ進む。

    body(run_dir) はテストが書き出した結果を返す。引数不正、構築スクリプトの例外、テスト自体の
    不具合を含め、内部のあらゆる例外をログと metrics.json / summary.md の ERROR に記録し、
    終了コード 2 とする。前回の metrics.json を残したり、異常終了をコード 0 と誤認したりしない。
    実際、古い PASS が残る状態では、--python-exit-code 1 のない Blender が 0 を返していた。"""
    run_dir = None
    try:
        run_dir = run_dir_from_args(args, test_name)
        begin_run(run_dir, test_name)
        result = body(run_dir)
    except SystemExit:
        raise
    except BaseException as exc:                                       # noqa: BLE001 - 全例外を ERROR、終了コード 2 とする。
        tb = traceback.format_exc()
        for ln in tb.rstrip().splitlines():
            log("[%s] ERROR %s" % (test_name, ln))
        try:
            if run_dir is None:
                run_dir = paths.results_run_dir("%s_error" % test_name)
            write_result(run_dir, error_result(test_name, run_dir, exc, tb))
            end_run(run_dir)
        except Exception as exc2:                                      # ERROR 記録の失敗でも終了コードを隠さない。
            log("[%s] ERROR 結果の書き出し中に例外: %s: %s" % (test_name, type(exc2).__name__, exc2))
        log("RESULT ERROR %s %s（終了コード %d）-> %s" % (test_name, " ".join("%s=ERROR" % t for t in TIERS), EXIT_CODE_ERROR, run_dir))
        sys.stdout.flush()
        sys.exit(EXIT_CODE_ERROR)
    finish(result, getattr(args, "exit_tier", "spec"))


# ------------------------------------------------------------------------------------ 測定位置
def where_point(F, pH, segment=None, s_H=None, **extra):
    """H 単位で与えた点の位置情報。"""
    px = F.H_to_px(pH[0], pH[1])
    pct = F.H_to_pct(pH[0], pH[1])
    w = {"segment": segment, "H": [float(pH[0]), float(pH[1])], "px": [float(px[0]), float(px[1])],
         "left_top_pct": [float(pct[0]), float(pct[1])],
         "s_pct_h": None if s_H is None else float(pm.H_to_pct_h(s_H))}
    w.update(extra)
    return w


def ranges_above(values, limit, mask=None):
    """values > limit かつ mask が真である添字の連続区間。両端を含む。"""
    v = np.asarray(values, dtype=np.float64)
    hit = v > float(limit)
    if mask is not None:
        hit &= np.asarray(mask, dtype=bool)
    out, start = [], None
    for i, b in enumerate(hit):
        if b and start is None:
            start = i
        if (not b) and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(hit) - 1))
    return out


# ------------------------------------------------------------------------------------ 評価済みメッシュ
def eval_mesh_arrays(obj, depsgraph=None, topology=True, uv=False):
    """現在フレームの `obj` の評価済みメッシュ配列。

    co_local、matrix_world、co_world を返す。topology 指定時は三角形、面、ループ、辺の情報、
    uv 指定時は UV レイヤーも返す。非有限座標の頂点数と先頭 20 個の添字は常に含める。"""
    import bpy
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        out = {"co_local": co.reshape(n, 3).copy(), "n_vertices": n}
        if topology:
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            tri = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get("vertices", tri)
            tp = np.empty(nt, np.int32)
            me.loop_triangles.foreach_get("polygon_index", tp)
            tl = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get("loops", tl)
            nl = len(me.loops)
            lv = np.empty(nl, np.int32)
            me.loops.foreach_get("vertex_index", lv)
            npoly = len(me.polygons)
            ps = np.empty(npoly, np.int32)
            pt = np.empty(npoly, np.int32)
            me.polygons.foreach_get("loop_start", ps)
            me.polygons.foreach_get("loop_total", pt)
            ne = len(me.edges)
            ed = np.empty(ne * 2, np.int32)
            me.edges.foreach_get("vertices", ed)
            out.update({"tris": tri.reshape(nt, 3), "tri_poly": tp, "tri_loops": tl.reshape(nt, 3), "loop_vert": lv, "poly_start": ps,
                        "poly_total": pt, "edges": ed.reshape(ne, 2)})
        if uv:
            layers = {}
            for layer in me.uv_layers:
                a = np.empty(len(me.loops) * 2, np.float32)
                layer.uv.foreach_get("vector", a) if hasattr(layer, "uv") else layer.data.foreach_get("uv", a)
                layers[layer.name] = a.reshape(-1, 2)
            out["uv_layers"] = layers
    finally:
        ev.to_mesh_clear()
    M = np.array(ev.matrix_world, dtype=np.float64)
    out["matrix_world"] = M
    out["co_world"] = out["co_local"].astype(np.float64) @ M[:3, :3].T + M[:3, 3]
    bad = ~np.isfinite(out["co_world"]).all(axis=1)
    out["n_nonfinite_vertices"] = int(bad.sum())
    out["nonfinite_vertex_indices"] = [int(v) for v in np.nonzero(bad)[0][:20]]
    return out


def sha(*arrays):
    h = hashlib.sha1()
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def boundary_vertices(loop_vert, poly_start, poly_total, n_vertices):
    """境界辺（ちょうど一つの面に使われる辺）の頂点。頂点添字と境界辺数を返す。"""
    nl = loop_vert.shape[0]
    nxt = np.arange(nl, dtype=np.int64) + 1
    ends = (poly_start + poly_total - 1).astype(np.int64)
    nxt[ends] = poly_start
    a = loop_vert.astype(np.int64)
    b = loop_vert[nxt].astype(np.int64)
    key = np.minimum(a, b) * int(n_vertices) + np.maximum(a, b)
    uk, cnt = np.unique(key, return_counts=True)
    bk = uk[cnt == 1]
    v = np.unique(np.concatenate([bk // int(n_vertices), bk % int(n_vertices)]))
    return v.astype(np.int64), int(bk.size)


# ------------------------------------------------------------------------------------ 重ね画像の描画
SEG_COLORS = {"back": "red", "head": "orange", "inner_arc": "magenta", "trough_run": "cyan"}


def upsample_mask(mask, width, height):
    """真偽値マスクを最近傍補間で指定の高さ・幅に変換する。"""
    h, w = mask.shape
    if (h, w) == (height, width):
        return mask
    yi = np.minimum((np.arange(height) + 0.5) * h / float(height), h - 1).astype(np.int64)
    xi = np.minimum((np.arange(width) + 0.5) * w / float(width), w - 1).astype(np.int64)
    return mask[yi][:, xi]


def draw_view(base_rgb, box, scale, polylines=(), markers=(), title=None, legend=None):
    """原画サイズの `base_rgb` から拡大切り出し画像を作り、折れ線と印を描く。
    折れ線と印の位置は原画の全解像度の画素座標で指定する。"""
    x0, y0, x1, y1 = box
    view = draw.View(base_rgb, x0, y0, x1, y1, scale=scale, method="auto")
    img = view.img.copy()
    for pl in polylines:
        p = np.asarray(pl["px"], dtype=np.float64)
        if p.shape[0] < 2:
            continue
        v = view.to_view(p)
        m = 60.0
        inside = (v[:, 0] > -m) & (v[:, 0] < img.shape[1] + m) & (v[:, 1] > -m) & (v[:, 1] < img.shape[0] + m)
        keep = inside | np.roll(inside, 1) | np.roll(inside, -1)
        v = np.where(keep[:, None], v, np.nan)
        draw.polyline(img, v, pl.get("color", "red"), pl.get("width", 2.0), dash=pl.get("dash"))
    for mk in markers:
        c = view.to_view(np.asarray(mk["px"], dtype=np.float64))
        if not (-20 <= c[0] <= img.shape[1] + 20 and -20 <= c[1] <= img.shape[0] + 20):
            continue
        draw.marker(img, c, mk.get("kind", "+"), mk.get("size", 9), mk.get("color", "red"), 2.0, outline="white")
        if mk.get("label"):
            draw.label_point(img, c, mk["label"], mk.get("color", "red"), scale=2, offset=mk.get("offset", (12, -14)))
    if title:
        draw.text(img, 6, 6, title, "black", 2, bg="white", bg_alpha=0.85)
    legend = list(legend or [])
    yy = img.shape[0] - 6 - 24 * len(legend)           # 凡例は左下に配置する。波頂は上部にある。
    for text, col in legend:
        draw.text(img, 6, yy, text, col, 2, bg="white", bg_alpha=0.85)
        yy += 24
    return img


def now_stamp():
    return paths.timestamp()


class StopWatch:
    def __init__(self):
        self.t0 = time.perf_counter()

    def lap(self):
        t = time.perf_counter()
        d, self.t0 = t - self.t0, t
        return d
