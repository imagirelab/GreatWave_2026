"""順序付きの波断面に対する測定指標（NumPy のみ）。幾何は H 正規化座標（X_H, Z_H）を用いる。
最終姿勢の波頂は (0, 1)、静水面・谷の高さは Z_H=0、+X は船側。角度は度で示し、
方向角は atan2(dZ, dX) とする（0 は +X、正は上向き）。

断面は画像左端→波頂→波頭先端→波頭の下面→内側円弧→谷→右端の水面の順に並ぶ。
gw.silhouette.extract_profile の profile['H'] と、gw.base_contour.v1 の三つの区間を
つないだ基礎輪郭は同じ順序を持つため、モデルと原画に同じ定義を適用できる。
詳細と解釈上の決定は docs/measurement_definitions.md を参照する。

主な定義
--------
波頂：Z の最大点。平坦部でも位置を安定させるため、最大値から extremum_tol_pct_h
以内の連続標本を取り、複数の高さでの交差弦の中点を sqrt(高さ差) に対して直線近似し、
高さ差 0 へ外挿する。平坦な頂部なら中央、左右で曲率が異なる丸い頂部なら真の極値に
相当する。補正量は区間幅の 25 % 以下とする。

波頭先端：既定の tip_rule=max_reversal。波頂から静水面への最初の接点までの前面区間で、
T が D より前にあり、X(T)-X(D) の戻りが最大になる組を選ぶ。T が先端、D が内側の
最深点となる。これにより途中のうねりや泡の房、右端の水面区間を先端と誤認しない。
戻りが tip_min_reversal_pct_h（0.3 %）を超えた場合だけ張り出しとする。
旧規則 first_reversal は波頂後で最初の局所 X 最大を取り、単一先端では同じ結果だが
房のある波頭では途中で止まる。旧点は overhang_onset として報告する。
head_lobes は波頂から最深点までの 1 % 以上の右→左への戻りを数える。

内側の最深点：先端から谷の終端までの X 最小点。垂直な壁ではその中央を用いる。
基礎輪郭：JSON の波頂・先端の接合点で区間を維持し、同じ折れ線上での自動検出とも
照合する。差が segmentation_check_tol_pct_h（0.2 %）を超える場合、test_shape は
区間分割の不一致として INVALID とする。
谷の終端：波頂の後（張り出す場合は最深点の後）で、初めて Z が静水面の許容範囲に
入る標本。なければ波頂以降の最低点。区間は back、head、inner_arc、trough_run、
そして head と inner_arc を合わせた front とする。

h と x_c：静水面からの波頂高と波頂の X。theta：前面の最大傾斜角。
進行方向（波頂→谷）を +X から時計回りに測り、20 度は緩い斜面、90 度は垂直、
90 度超は張り出し、180 度は水平な天井。theta_window_pct_h の弦を接線とし、
結果は 0～180 度に制限する。theta_raw は 180 度超も残す。
o=max(0, X_tip-X_crest) で、先端がない場合は 0。
phi：先端から phi_skip_H～phi_skip_H+phi_len_H 手前の波頭表側の弦の方向。
負値は下向き。モデルと基礎輪郭の S5 と M4 に同じ定義を使う。
crest_to_tip は波頂から先端への直線方向で、phi と並べる報告専用値。

W：しきい値を持たない形状の大きさの報告。width_levels_H の絶対高さで波背・前面の
水平交点、幅、波頂の鉛直線からの距離を求め、張り出し o、空洞深さ、輪郭と静水面の
間の面積も示す。S4 は波背の左端、最大、波頂前の傾斜角を示す。
S8 は隣接する標本の接線差を複数位相で評価する。左端→先端と先端→谷端の区間に加え、
先端をまたぐ弦も評価する。2026-09-20 以降は既定で先端付近を除外しない
（s8_tip_exclusion_pct_h=0）。正値にすると旧来の除外を明示的に復活させるが、
薄い縁の合成 fixture に限る。旧定義の最大値、先端付近の回転、折れ線自身の頂点角を
閉じた窓で測る値も報告する。頂点窓は短い窓や先端をまたぐ窓にも分ける。
S7 は区間ごとにモデル→基礎輪郭と逆方向の最近距離を測り、平均と 95 パーセンタイルを
画像高に対する % で報告する。隣接区間へ余白を入れ、基礎輪郭の in_S7=false は除く。
符号付き平均はモデルが標的の胴体の外側なら正とする。

trough_level_H は波の前方にあるモデル自身の最低水位。最深点（張り出さない場合は波頂）
から断面右端までの最低 Z を取る。静水面から trough_tol_pct_h（0.3 %）以内なら
reached_still_water=true。S3 は座標系の Z=0 と、このモデル自身の谷底の両方を報告・判定する。
shape は各断面自身の波頂高 h の 0.25 / 0.5 / 0.75 で形を記述する報告専用指標。
各長さを h で割り、o/h、空洞深さ/h、0.5 h での幅/h を示すため、広く低い形の差も
相殺されにくい。
"""
import json
import math

import numpy as np

from . import frame as gw_frame, paths

__all__ = [
    "DEFAULT_PARAMS", "get_params", "Curve", "measure_profile", "measure_sequence", "s8_smoothness", "s7_deviation",
    "position_checks", "load_base_contour", "base_contour_polyline", "measure_base_contour",
    "contour_displacement", "point_polyline_distance", "pct_h_to_H", "H_to_pct_h",
    "detect_landmarks", "segmentation_check", "width_metrics", "compare_width_metrics", "count_x_reversals",
    "shape_descriptors", "compare_shape_descriptors", "signed_point_polyline_distance", "vertex_window_turns",
    "non_default_params", "S8_SPACING_DEFAULT_PCT_H", "SHAPE_LABEL",
]

DEFAULT_PARAMS = {
    "z_still_H": {"value": 0.0, "comment": "静水面・谷レベルの H 単位の高さ（仕様第 4 節では Z=0）。"},
    "extremum_tol_pct_h": {"value": 0.1, "comment": "波頂・先端・最深点は、極値座標からこの距離（画像高に対する %）以内の連続標本区間の中心で定める。平坦な頂部と垂直な壁でも位置を安定させる。"},
    "tip_rule": {"value": "max_reversal", "comment": "波頭先端の検出方法。モデル断面で用い、基礎輪郭では整合性の確認に用いる。max_reversal は前面区間（波頂から Z<=z_still+trough_tol の最初の標本まで）で X(T)-X(D) が最大の、T が D より前にある組を選ぶ。T は波頭全体の最右点、D は内側円弧の最深点。途中の細かなうねりや房で波頭が途中終了せず、右の水面に沿う区間も選ばれない。first_reversal は旧規則で、波頂後で初めて X が局所最大となり、tip_min_reversal_pct_h 以上戻る点を選ぶ。先端が一つの波頭では同じ結果だが房のある波頭では最初の房で止まり、指状部分尺度の基礎輪郭では JSON の先端から画像高の 16 % 離れていた。旧規則の点は overhang_onset として常に報告する。"},
    "tip_min_reversal_pct_h": {"value": 0.3, "comment": "前面区間で X の最大の戻りがこの値を超えた場合に張り出し（波頭先端と内側円弧）があるとする。それ以下は張り出しなし（o=0）。旧規則と同じ値なので、動きの張り出し開始フレームは変わらない。"},
    "head_lobe_reversal_pct_h": {"value": 1.0, "comment": "診断専用で先端位置を変えない。波頂と最深点の間で X がこの値以上右から左へ戻る回数を波頭の房として数える（head_lobes.n_lobes）。1 は先端が一つの波頭で max_reversal と first_reversal が一致する。1 より大きい場合は房のある波頭。"},
    "segmentation_check_tol_pct_h": {"value": 0.2, "comment": "measure_base_contour で、JSON の接合点から得た波頂・先端・最深点と、同じ折れ線上で検出した特徴点の許容距離。超えると標的とモデルの区間分割が一致せず、test_shape は INVALID とする（2026-09-20 の進行管理者の作業）。"},
    "width_levels_H": {"value": [0.25, 0.5, 0.75], "comment": "報告専用。水平断面幅を報告する絶対高さ Z（H 単位）。標的とモデルで同じ原画の行を指す。しきい値なし、ユーザーの判断待ち。"},
    "trough_tol_pct_h": {"value": 0.3, "comment": "内側円弧・前面が静水面からこの距離以内に初めて入る位置を終端とする。"},
    "theta_window_pct_h": {"value": 2.0, "comment": "前面傾斜角 theta の接線として用いる弦の長さ。"},
    "theta_step_pct_h": {"value": 0.25, "comment": "弧長方向に theta を評価する間隔。"},
    "phi_skip_H": {"value": 0.02, "comment": "phi の計測で波頭先端直前から除く弧長。丸い縁に相当し、仕様第 7 節の縁半径は H の 1.5 % 以下。"},
    "phi_len_H": {"value": 0.06, "comment": "phi に用いる波頭表側の窓の長さ。「先端前の最後の数 % H」に相当する。"},
    "phi_min_len_H": {"value": 0.02, "comment": "波頭が短く、この長さ以上の窓を取れない場合は phi を報告しない。"},
    "s4_left_window_pct_h": {"value": 5.0, "comment": "S4 の「左端付近」。画像左端からこの弧長までの弦で測る。"},
    "s4_tangent_window_pct_h": {"value": 2.0, "comment": "波背の傾斜曲線の接線として用いる弦の長さ。"},
    "s4_before_crest_window_pct_h": {"value": [3.0, 8.0], "comment": "S4 の「波頂直前」。波頂からこの二つの弧長距離だけ手前の波背上の弦で測る。"},
    "s4_monotone_tol_deg": {"value": 2.0, "comment": "「波頂へ向けて傾斜が徐々に減る」ための許容角度。"},
    "s4_crest_zone_pct_h": {"value": 6.0, "comment": "「頂部は丸く角がない」を調べる、波頂からの弧長範囲。この範囲内の S8 の曲がり角を使う。"},
    "s8_n_phases": {"value": 4, "comment": "折れが標本間に隠れないよう、S8 をこの数の標本位相（間隔を位相数で割ったずらし）で評価する。"},
    "s8_tip_exclusion_pct_h": {"value": 0.0, "comment": "0 なら除外なし。波頭先端をまたぐ接合点も含めて仕様を文字通り判定し、尖った先端を失敗とする。2026-09-20 までは 2.0 で、薄い縁を想定した進行管理者の解釈だった。正式な大形状標的は先端で一標本当たり約 10 度しか曲がらず、仕様 S8 に例外もない。0 より大きい値は旧動作を復活させ、先端からこの弧長未満の接合点を判定から除く。明示的な個別上書きとして、薄い縁の合成 fixture でのみ使用する。"},
    "s8_tip_report_zone_pct_h": {"value": 2.0, "comment": "報告専用。s8_tip_exclusion_pct_h=0 のとき、先端付近の補助値の対象とする弧長半幅。max_tip_zone_excluded_deg は旧定義の S8、tip_turn_deg はこの範囲をまたぐ曲がり角、頂点窓の値も範囲内外に分ける。除外幅が 0 より大きければその値を範囲とする。"},
    "s8_limit_deg": {"value": 15.0, "comment": "thresholds.json の S8.max_tangent_diff_deg の複製値。S4 の「角がない」の真偽値にのみ使う。"},
    "s7_sample_spacing_pct_h": {"value": 0.25, "comment": "S7 の距離を測る標本間隔。S8 の間隔より細かい。"},
    "s7_segment_margin_pct_h": {"value": 3.0, "comment": "わずかな波頂・先端の分割位置差で偽の偏差が出ないよう、比較相手の区間を隣接区間へこの弧長だけ延長する。"},
    "shape_levels_frac_h": {"value": [0.25, 0.5, 0.75], "comment": "報告専用。各輪郭自身の波頂高 h に対する断面高さの比率（metrics['shape']）。形が広く低いとき相対高さでは差が相殺されず、絶対高さ width_levels_H では相殺され得る。しきい値なし。"},
    "s8_vertex_short_windows_pct_h": {"value": [0.5, 0.25], "comment": "報告専用。S8 の頂点窓の曲がり角を追加で調べる短い窓（画像高に対する %）。滑らかな曲線では窓が短くなるほど角度も小さくなるが、折れは局所曲率に逆らっていても角度を保つ。例：20 度の折れが 1 % 当たり 9 度の曲率と逆向きなら、1 % 窓では 11 度でも 0.25 % 窓では 18 度となる。"},
}

S8_SPACING_DEFAULT_PCT_H = 1.0
"""params.json に S8_sample_spacing_pct がない場合の S8 標本間隔。
仕様第 5 節 S8 と第 10 節の仮定 4 に従い、初期値を画像高の 1 % とする。"""

_PARAMS_META_KEYS = ("comment", "provenance", "unit", "_doc", "_comment")     # params.json['measure_params'] の値に添えてよいメタデータ。
_DERIVED_KEYS = ("s8_spacing_pct_h", "non_default_params")                    # 平坦な結果辞書には含むが DEFAULT_PARAMS には含めない。


def _param_entry(name):
    """params.json の指定項目の値を返す。項目が存在しない場合だけ None とする。ファイルの欠落、不正な JSON、読み取り失敗は例外とし、壊れた設定を暗黙に補わない。"""
    try:
        return paths.param(name)
    except KeyError:
        return None


def _same_value(a, b):
    try:
        if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
            return list(a) == list(b)
        if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
            return a == b
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def get_params(overrides=None):
    """DEFAULT_PARAMS の平坦な {name: value} に、params.json の measure_params と overrides を順に重ねる。S8 の標本間隔は params.json の S8_sample_spacing_pct から取り、項目がなければ S8_SPACING_DEFAULT_PCT_H を使う。
項目がない場合だけを捕捉し、ファイル不正、辞書以外の measure_params、数値でない S8 間隔、未知の名前は例外とする。誤記を黙って既定値で測らないため。
結果の non_default_params は既定値と異なる設定の value、default、source を記録する。空ならすべて文書化された既定値で測定したことを示す。テストは空でない場合に印を付ける。"""
    p = {k: (list(v["value"]) if isinstance(v["value"], list) else v["value"]) for k, v in DEFAULT_PARAMS.items()}
    from_json = {}
    raw = _param_entry("S8_sample_spacing_pct")
    p["s8_spacing_pct_h"] = S8_SPACING_DEFAULT_PCT_H if raw is None else float(raw)
    from_json["s8_spacing_pct_h"] = p["s8_spacing_pct_h"]
    extra = _param_entry("measure_params")
    if extra is not None:
        if not isinstance(extra, dict):
            raise TypeError("params.json['measure_params'] must be an object {name: value | {value: ..}}, got %s" % type(extra).__name__)
        for k, v in extra.items():
            if k in _PARAMS_META_KEYS:
                continue
            if k not in DEFAULT_PARAMS:
                raise ValueError("params.json['measure_params'] has an unknown measure parameter %r (known: %s)"
                                 % (k, ", ".join(sorted(DEFAULT_PARAMS))))
            p[k] = v["value"] if isinstance(v, dict) and "value" in v else v
            from_json[k] = p[k]
    if overrides:
        for k, v in overrides.items():
            if k == "non_default_params":
                continue                                  # 以前の get_params() が返した平坦な辞書も上書き値として有効。
            if k not in DEFAULT_PARAMS and k not in _DERIVED_KEYS:
                raise ValueError("unknown measure parameter %r in overrides (known: %s)"
                                 % (k, ", ".join(sorted(list(DEFAULT_PARAMS) + ["s8_spacing_pct_h"]))))
            p[k] = v
    nd = {}
    for k in sorted(p):
        default = S8_SPACING_DEFAULT_PCT_H if k == "s8_spacing_pct_h" else DEFAULT_PARAMS[k]["value"]
        if not _same_value(p[k], default):
            src = "params.json" if (k in from_json and _same_value(from_json[k], p[k])) else "override"
            nd[k] = {"value": p[k], "default": default, "source": src}
    p["non_default_params"] = nd
    return p


def non_default_params(params=None):
    """DEFAULT_PARAMS と異なる測定設定の value、default、source を返す。params は上書き値、または get_params() の平坦な結果を指定できる。"""
    return get_params(params)["non_default_params"]


def _frame_h():
    # 壊れた params.json はここでも例外とする。以前の 100/66 への暗黙の代替は行わない。
    return gw_frame.get_frame().frame_h


def pct_h_to_H(d_pct):
    """画像高に対する % で示した長さを H 単位へ変換する。"""
    return np.asarray(d_pct, dtype=np.float64) / 100.0 * _frame_h()


def H_to_pct_h(d_H):
    """H 単位の長さを画像高に対する % へ変換する。"""
    return np.asarray(d_H, dtype=np.float64) / _frame_h() * 100.0


def wrap_deg(a):
    """角度を (-180, 180] の範囲へ正規化する。"""
    a = (np.asarray(a, dtype=np.float64) + 180.0) % 360.0 - 180.0
    return np.where(a == -180.0, 180.0, a)


# ====================================================================== 弧長を持つ曲線
class Curve:
    """弧長で位置を指定できる折れ線。pts は (N, 2)。連続する重複点は除く。"""

    def __init__(self, pts):
        p = np.asarray(pts, dtype=np.float64)
        if p.ndim != 2 or p.shape[1] != 2 or p.shape[0] < 2:
            raise ValueError("a curve needs at least 2 points of shape (N, 2)")
        if not np.isfinite(p).all():
            raise ValueError("curve contains non-finite values")
        seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
        keep = np.concatenate([[True], seg > 0])
        self.index_map = np.nonzero(keep)[0]          # 元の配列の添字。
        p = p[keep]
        if p.shape[0] < 2:
            raise ValueError("curve has zero length")
        self.pts = p
        self.s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))])
        self.length = float(self.s[-1])

    def at(self, s):
        s = np.clip(np.asarray(s, dtype=np.float64), 0.0, self.length)
        return np.stack([np.interp(s, self.s, self.pts[:, 0]), np.interp(s, self.s, self.pts[:, 1])], axis=-1)

    def chord_deg(self, s0, s1):
        a, b = self.at(s0), self.at(s1)
        return np.degrees(np.arctan2(b[..., 1] - a[..., 1], b[..., 0] - a[..., 0]))

    def tangent_deg(self, s, window, lo=0.0, hi=None):
        """s-window/2 から s+window/2 までの弦の方向。両端を [lo, hi] に収める。"""
        hi = self.length if hi is None else hi
        s = np.asarray(s, dtype=np.float64)
        return self.chord_deg(np.clip(s - 0.5 * window, lo, hi), np.clip(s + 0.5 * window, lo, hi))

    def index_at(self, s):
        return int(np.clip(np.searchsorted(self.s, s), 0, len(self.s) - 1))

    def sub(self, s0, s1, spacing):
        """[s0, s1] の両端を含め、spacing 間隔で点を標本化する。"""
        s0, s1 = float(max(0.0, s0)), float(min(self.length, s1))
        if s1 <= s0:
            return self.at(np.array([s0]))
        n = max(2, int(math.ceil((s1 - s0) / spacing)) + 1)
        return self.at(np.linspace(s0, s1, n))

    def slice_pts(self, s0, s1):
        """[s0, s1] にある元の頂点と、正確な両端点を返す。"""
        s0, s1 = float(max(0.0, s0)), float(min(self.length, s1))
        inner = (self.s > s0) & (self.s < s1)
        return np.concatenate([self.at(np.array([s0])), self.pts[inner], self.at(np.array([s1]))], axis=0)


def _run_mid(values, s, i_ext, tol, sign, lo, hi):
    """[lo, hi] 内の極値添字 i_ext を含み、sign×values が極値から tol 以内にある連続区間を求める。区間中央の弧長と両端添字を返す。"""
    v = sign * values
    thr = v[i_ext] - tol
    a = i_ext
    while a > lo and v[a - 1] >= thr:
        a -= 1
    b = i_ext
    while b < hi and v[b + 1] >= thr:
        b += 1
    if b == a:
        return float(s[a]), a, b
    # 極値から少し下の複数の高さ tau で、極値の左右の交点を結ぶ弦の中点 m(tau) を求める。
    # 平坦部や左右対称の頂部では m は一定。左右の曲率が異なる場合は
    # m(tau)=s0+c√tau なので、√tau に対する直線を tau=0 へ外挿すると真の極値 s0 を得る。
    # 平坦部のノイズで位置が大きく動かないよう、補正量は連続区間幅の 25 % 以下とする。
    vmax = v[i_ext]
    mids, roots = [], []
    for frac in (0.4, 0.55, 0.7, 0.85, 1.0):
        level = vmax - frac * tol
        k = i_ext
        while k > lo and v[k - 1] >= level:
            k -= 1
        if k == lo:
            continue
        sl = s[k - 1] + (level - v[k - 1]) / (v[k] - v[k - 1]) * (s[k] - s[k - 1])
        k = i_ext
        while k < hi and v[k + 1] >= level:
            k += 1
        if k == hi:
            continue
        sr = s[k + 1] + (level - v[k + 1]) / (v[k] - v[k + 1]) * (s[k] - s[k + 1])
        mids.append(0.5 * (sl + sr))
        roots.append(math.sqrt(frac * tol))
    if len(mids) >= 3:
        c1, c0 = np.polyfit(np.asarray(roots), np.asarray(mids), 1)
        m_full = mids[-1]
        cap = 0.25 * (s[b] - s[a])
        est = m_full + min(max(c0 - m_full, -cap), cap)
        return float(min(max(est, s[a]), s[b])), a, b
    # 探索範囲の端で連続区間が切れた場合は、代わりに弧長の重み付き重心を用いる。
    ss = s[a:b + 1]
    ds = np.gradient(ss)
    wgt = np.maximum(v[a:b + 1] - thr, 0.0) ** 2 * ds
    if wgt.sum() <= 0:
        return 0.5 * (s[a] + s[b]), a, b
    return float((wgt * ss).sum() / wgt.sum()), a, b


# ====================================================================== 波頭先端の検出
def _front_stretch_end(z, i_c, z_lim):
    """前面区間の終端添字。波頂以降で Z<=z_lim を初めて満たす標本（静水面への最初の接点）を選ぶ。なければ波頂以降の最低標本。波頂自身は選ばない。"""
    below = np.nonzero(z[i_c:] <= z_lim)[0]
    i_f = int(i_c + below[0]) if below.size else int(i_c + np.argmin(z[i_c:]))
    return i_f if i_f > i_c else len(z) - 1


def _tip_first_reversal(x, i_c, rev):
    """旧規則。波頂の後で X が最初に局所最大となり、続いて rev を超えて戻る位置の添字を返す。なければ None。"""
    xm, im = x[i_c], i_c
    for i in range(i_c + 1, len(x)):
        if x[i] > xm:
            xm, im = x[i], i
        elif x[i] < xm - rev:
            return im if im > i_c else None
    return None


def _tip_max_reversal(x, i_c, i_f, rev):
    """max_reversal 規則。[i_c, i_f] で T が D より前にあり、X(T)-X(D) の戻りが最大になる組を求める。戻りが rev 以下なら添字は None。T は [i_c, D] の最右標本、D は [T, i_f] の最左標本となる。"""
    xf = x[i_c:i_f + 1]
    dd = np.maximum.accumulate(xf) - xf
    j = int(np.argmax(dd))
    if not dd[j] > rev:
        return None, None, float(dd[j])
    i_t = i_c + int(np.argmax(xf[:j + 1]))
    if i_t <= i_c:                                     # 波頂自身が最右点なら波頭は存在しない。
        return None, None, float(dd[j])
    return i_t, i_c + j, float(dd[j])


def count_x_reversals(x, rev):
    """標本列 x に沿う X の右から左への rev 以上の戻り回数（ヒステリシス付き）。波頂と最深点の間に先端が一つだけなら 1。"""
    x = np.asarray(x, dtype=np.float64)
    if x.size < 2:
        return 0
    n, right, ext = 0, True, x[0]
    for v in x:
        if right:
            if v > ext:
                ext = v
            elif v < ext - rev:
                n, right, ext = n + 1, False, v
        else:
            if v < ext:
                ext = v
            elif v > ext + rev:
                right, ext = True, v
    return int(n)


# ====================================================================== 主測定
def measure_profile(pts_H, params=None, crest_index=None, tip_index=None):
    """順序付き断面の一フレーム分の量を H 単位で測る。pts_H は (N, 2) の断面。crest_index と tip_index を指定すると基礎輪郭の区間接合点として使い、未指定なら自動検出する。
結果は ok、notes、overhanging、tip_source、特徴点 landmarks、区間 segments、h、x_c、theta、theta_raw、o、cavity_depth、phi、crest_to_tip_deg、head_lobes、S4、S8、W、shape、length_H を含む。trough_level_H はモデル前面の最低水位、reached_still_water は静水面への到達、h_from_model_trough は自身の谷底からの高さ。trough_run_median_H は強化前の旧指標。non_default_params は既定値と異なる測定設定を示す。数値・キーの詳細はモジュール冒頭を参照。"""
    P = get_params(params)
    C = Curve(pts_H)
    x, z, s = C.pts[:, 0], C.pts[:, 1], C.s
    n = len(s)
    tol = float(pct_h_to_H(P["extremum_tol_pct_h"]))
    z_still = float(P["z_still_H"])
    notes = []

    def lm(point, s_val):
        return {"H": [float(point[0]), float(point[1])], "s": float(s_val), "index": int(C.index_map[C.index_at(s_val)])}

    # ---- 波頂
    if crest_index is not None:
        i_c = int(np.searchsorted(C.index_map, crest_index))
        i_c = min(max(i_c, 0), n - 1)
        s_c, ia, ib = s[i_c], i_c, i_c
        crest_pt = C.pts[i_c].copy()
        i_max = i_c
    else:
        i_max = int(np.argmax(z))
        s_c, ia, ib = _run_mid(z, s, i_max, tol, +1.0, 0, n - 1)
        crest_pt = C.at(s_c)
        crest_pt[1] = z[i_max]
        i_c = C.index_at(s_c)
    landmarks = {"crest": lm(crest_pt, s_c), "crest_argmax": lm(C.pts[i_max], s[i_max]),
                 "crest_plateau": {"x_min_H": float(min(x[ia], x[ib])), "x_max_H": float(max(x[ia], x[ib])),
                                   "width_pct_h": float(H_to_pct_h(abs(x[ib] - x[ia]))), "tol_pct_h": P["extremum_tol_pct_h"]}}

    # ---- 波頭先端（冒頭の定義および DEFAULT_PARAMS['tip_rule'] を参照）
    rev = float(pct_h_to_H(P["tip_min_reversal_pct_h"]))
    ttol = float(pct_h_to_H(P["trough_tol_pct_h"]))
    rule = str(P.get("tip_rule", "max_reversal"))
    if rule not in ("max_reversal", "first_reversal"):
        raise ValueError("unknown tip_rule %r (known: 'max_reversal', 'first_reversal')" % rule)
    i_front = _front_stretch_end(z, i_c, z_still + ttol)
    i_onset = _tip_first_reversal(x, i_c, rev)                  # 旧規則の先端は、張り出しが初めて見える位置。
    i_tm, _i_dm, comeback = _tip_max_reversal(x, i_c, i_front, rev)
    i_t = None
    if tip_index is not None:
        i_t = int(np.searchsorted(C.index_map, tip_index))
        i_t = min(max(i_t, i_c), n - 1)
        tip_source = "given"
    else:
        i_t = i_tm if rule == "max_reversal" else i_onset
        tip_source = "detected:" + rule
    overhanging = i_t is not None and i_t > i_c

    # ---- 谷の終端・最深点
    i_d = None
    if overhanging:
        s_t, ta, tb = _run_mid(x, s, i_t, tol, +1.0, i_c, n - 1) if tip_index is None else (s[i_t], i_t, i_t)
        tip_pt = C.at(s_t)
        if tip_index is None:
            tip_pt[0] = x[i_t]
        # 先端より後にある仮の谷の終端。
        below = np.nonzero(z[i_t:] <= z_still + ttol)[0]
        i_e = int(i_t + below[0]) if below.size else int(i_t + np.argmin(z[i_t:]))
        if i_e <= i_t:
            i_e = n - 1
        i_d = int(i_t + np.argmin(x[i_t:i_e + 1]))
        s_d, da, db = _run_mid(x, s, i_d, tol, -1.0, i_t, i_e)
        deep_pt = C.at(s_d)
        deep_pt[0] = x[i_d]
        # 谷の終端は最深点より後に置く。
        below = np.nonzero(z[i_d:] <= z_still + ttol)[0]
        i_e = int(i_d + below[0]) if below.size else int(i_d + np.argmin(z[i_d:]))
        landmarks["head_tip"] = lm(tip_pt, s_t)
        landmarks["inner_deepest"] = lm(deep_pt, s_d)
        landmarks["inner_deepest"]["run_z_range_H"] = [float(min(z[da], z[db])), float(max(z[da], z[db]))]
    else:
        s_t = None
        below = np.nonzero(z[i_c:] <= z_still + ttol)[0]
        i_e = int(i_c + below[0]) if below.size else int(i_c + np.argmin(z[i_c:]))
        landmarks["head_tip"] = None
        landmarks["inner_deepest"] = None
        notes.append("no overhang: no head tip / inner arc (o = 0)")
    if i_e <= i_c:
        i_e = n - 1
        notes.append("front face has no samples after the crest")
    s_e = s[i_e]
    reached_trough = bool(z[i_e] <= z_still + ttol)
    if not reached_trough:
        notes.append("front face does not reach the still-water level inside the profile")
    landmarks["trough_end"] = lm(C.pts[i_e], s_e)
    landmarks["trough_end"]["reached_still_water"] = reached_trough

    om = C.index_map
    segments = {"back": [int(om[0]), int(om[i_c])],
                "head": [int(om[i_c]), int(om[i_t])] if overhanging else None,
                "inner_arc": [int(om[i_t]), int(om[i_e])] if overhanging else None,
                "trough_run": [int(om[i_e]), int(om[n - 1])] if i_e < n - 1 else None,
                "front": [int(om[i_c]), int(om[i_e])]}
    seg_s = {"back": [0.0, float(s_c)], "head": [float(s_c), float(s_t)] if overhanging else None,
             "inner_arc": [float(s_t), float(s_e)] if overhanging else None,
             "trough_run": [float(s_e), C.length] if i_e < n - 1 else None, "front": [float(s_c), float(s_e)]}

    # ---- 波の前面にあるモデル自身の水位。内側円弧の最深点（張り出さない場合は波頂）から
    # 断面の終端までの最低 Z を取る。完全なシルエットなら終端は画像右端。
    # 前面の海が z_still より高い場合はここに現れるが、z_still 基準の h / S3 では見えない。
    # 2026-09-20 より前は水面区間の中央値をこのキーに入れていた。旧値は
    # trough_run_median_H として保持する。
    i_from = i_d if overhanging else i_c
    i_low = int(i_from + np.argmin(z[i_from:]))
    trough_level = float(z[i_low])
    reached_still_water = bool(trough_level <= z_still + ttol)
    landmarks["trough_lowest"] = lm(C.pts[i_low], s[i_low])
    trough_run_median = float(np.median(z[i_e:])) if i_e < n - 1 and reached_trough else (float(z[i_e]) if reached_trough else None)

    # ---- 前面傾斜角 theta
    w_th = float(pct_h_to_H(P["theta_window_pct_h"]))
    step = float(pct_h_to_H(P["theta_step_pct_h"]))
    L_front = s_e - s_c
    if L_front > w_th:
        ss = np.arange(s_c + 0.5 * w_th, s_e - 0.5 * w_th + 1e-12, step)
        if ss.size == 0:
            ss = np.array([0.5 * (s_c + s_e)])
        dirs = C.tangent_deg(ss, w_th, s_c, s_e)
    else:
        ss = np.array([0.5 * (s_c + s_e)])
        dirs = np.atleast_1d(C.chord_deg(s_c, s_e))
        notes.append("front face shorter than the theta window; theta = chord of the whole front")
    th_raw_all = np.where(dirs > 90.0, 360.0 - dirs, -dirs)
    k = int(np.argmax(th_raw_all))
    theta_raw = float(th_raw_all[k])
    theta = float(min(max(theta_raw, 0.0), 180.0))
    landmarks["theta_point"] = lm(C.at(ss[k]), ss[k])

    # ---- 張り出し o、空洞深さ、胴体の最右点
    if overhanging:
        o = float(max(0.0, landmarks["head_tip"]["H"][0] - landmarks["crest"]["H"][0]))
        cavity = float(landmarks["head_tip"]["H"][0] - landmarks["inner_deepest"]["H"][0])
        i_br = int(i_c + np.argmax(x[i_c:i_d + 1]))
        landmarks["body_rightmost"] = lm(C.pts[i_br], s[i_br])
    else:
        o, cavity = 0.0, 0.0
        landmarks["body_rightmost"] = None

    # ---- 張り出し開始（旧先端）、波頭の房、波頂→先端の方向。いずれも報告専用。
    landmarks["overhang_onset"] = None if i_onset is None else lm(C.pts[i_onset], s[i_onset])
    lobe_rev = float(pct_h_to_H(P["head_lobe_reversal_pct_h"]))
    i_lobe_end = i_d if overhanging else i_front
    head_lobes = {"lobe_reversal_pct_h": float(P["head_lobe_reversal_pct_h"]),
                  "n_lobes": count_x_reversals(x[i_c:i_lobe_end + 1], lobe_rev),
                  "n_reversals_min": count_x_reversals(x[i_c:i_lobe_end + 1], rev),
                  "max_comeback_pct_h": float(H_to_pct_h(comeback)),
                  "detected_tip_index": None if i_tm is None else int(C.index_map[i_tm]),
                  "onset_to_tip_pct_h": None}
    crest_to_tip = None
    if overhanging:
        tp, cp = landmarks["head_tip"]["H"], landmarks["crest"]["H"]
        crest_to_tip = float(math.degrees(math.atan2(tp[1] - cp[1], tp[0] - cp[0])))
        if i_onset is not None:
            head_lobes["onset_to_tip_pct_h"] = float(H_to_pct_h(math.hypot(x[i_onset] - tp[0], z[i_onset] - tp[1])))
        if head_lobes["n_lobes"] > 1:
            notes.append("lobed head: %d right->left reversals >= %.3g %% of image height between crest and deepest point; "
                         "legacy first-reversal tip is %.2f %% of image height away from the head tip"
                         % (head_lobes["n_lobes"], P["head_lobe_reversal_pct_h"], head_lobes["onset_to_tip_pct_h"] or 0.0))

    # ---- phi
    phi = None
    if overhanging:
        skip, ln, mn = float(P["phi_skip_H"]), float(P["phi_len_H"]), float(P["phi_min_len_H"])
        s1 = max(s_c, s_t - skip)
        s0 = max(s_c, s_t - skip - ln)
        if s1 - s0 >= mn:
            p0, p1 = C.at(s0), C.at(s1)
            phi = {"deg": float(C.chord_deg(s0, s1)), "window_s": [float(s0), float(s1)],
                   "p0_H": [float(p0[0]), float(p0[1])], "p1_H": [float(p1[0]), float(p1[1])],
                   "window_len_H": float(s1 - s0), "truncated": bool(s1 - s0 < ln - 1e-9)}
        else:
            notes.append("head too short for the phi window (%.4f H < %.4f H)" % (s1 - s0, mn))

    # ---- S4 の波背の傾斜
    S4 = _back_slopes(C, s_c, P)

    # ---- S8
    S8 = s8_smoothness(C, s_c, s_t if overhanging else None, s_e, P)
    zone = float(pct_h_to_H(P["s4_crest_zone_pct_h"]))
    js = np.asarray(S8["_junction_s"])
    jd = np.asarray(S8["_junction_diff"])
    near = np.abs(js - s_c) <= zone
    crest_turn = float(np.max(np.abs(jd[near]))) if near.any() else None
    S4["crest_max_turn_deg"] = crest_turn
    S4["top_is_round_no_corner"] = None if crest_turn is None else bool(crest_turn < P["s8_limit_deg"])

    # ---- 報告専用の幅・面積（絶対高さ）と、輪郭自身の波頂高に対する形状記述子。
    h_val = float(landmarks["crest"]["H"][1] - z_still)
    W = _width_metrics(C, i_c, s_c, s_t if overhanging else None, i_e, float(landmarks["crest"]["H"][0]), o, cavity, P)
    shape = _shape_descriptors(C, i_c, s_t if overhanging else None, i_e, float(landmarks["crest"]["H"][0]), h_val, o, cavity, P)
    if not reached_still_water:
        notes.append("the lowest point of the profile in front of the wave is %.3f %% of image height above z_still: the model's own "
                     "water level is raised (trough_level_H = %.5f H); h and S3 are measured from z_still, see 'S3_from_model_trough'"
                     % (float(H_to_pct_h(trough_level - z_still)), trough_level))

    return {
        "ok": True, "notes": notes, "overhanging": bool(overhanging), "tip_source": tip_source,
        "landmarks": landmarks, "segments": segments, "segments_s": seg_s,
        "h": h_val, "x_c": float(landmarks["crest"]["H"][0]),
        "theta": theta, "theta_raw": theta_raw, "o": o, "cavity_depth": cavity, "phi": phi,
        "phi_deg": None if phi is None else phi["deg"], "crest_to_tip_deg": crest_to_tip, "head_lobes": head_lobes,
        "W": W, "shape": shape,
        "S4": S4, "S8": {k2: v for k2, v in S8.items() if not k2.startswith("_")},
        "trough_level_H": trough_level, "reached_still_water": reached_still_water,
        "trough_level_above_still_pct_h": float(H_to_pct_h(trough_level - z_still)),
        "h_from_model_trough": float(landmarks["crest"]["H"][1] - trough_level),
        "trough_run_median_H": trough_run_median, "reached_still_water_tol_pct_h": float(P["trough_tol_pct_h"]),
        "length_H": C.length, "n_points": int(n),
        "non_default_params": P["non_default_params"],
        "params": {k2: P[k2] for k2 in sorted(P)},
    }


def detect_landmarks(pts_H, params=None):
    """ライブラリの規則で順序付き折れ線の特徴点を検出する。波頂は頑健な Z 最大、波頭先端と最深点は tip_rule、谷の終端も求める。輪郭生成側は JSON の接合点をここへ置くことで、モデル側と同じ分割を保てる。"""
    m = measure_profile(pts_H, params)
    out = {k: m["landmarks"].get(k) for k in ("crest", "head_tip", "inner_deepest", "trough_end", "overhang_onset")}
    out.update({"overhanging": m["overhanging"], "head_lobes": m["head_lobes"], "tip_rule": m["params"]["tip_rule"]})
    return out


# ====================================================================== 報告専用の幅と面積
WIDTH_LABEL = "report only - pending user decision"


def _level_tag(level):
    return "z%02d" % int(round(100.0 * float(level)))


def _level_crossings(x, z, s, level, k0, k1):
    """折れ線の標本 k0～k1 と水平線 Z=level の交点を経路順に求める。X、弧長 s、下向きに横切るかを返す。"""
    if k1 <= k0:
        return np.zeros(0), np.zeros(0), np.zeros(0, bool)
    zz = z[k0:k1 + 1] - float(level)
    above = zz >= 0.0
    k = np.nonzero(above[:-1] != above[1:])[0]
    if k.size == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0, bool)
    a, b = zz[k], zz[k + 1]
    t = a / (a - b)
    kk = k0 + k
    return x[kk] + t * (x[kk + 1] - x[kk]), s[kk] + t * (s[kk + 1] - s[kk]), above[k]


def _section_record(C, level, i_c, s_t, i_e, x_c):
    """測定済み断面を Z=level で水平に切った一件分の記録（冒頭の W）。"""
    x, z, s = C.pts[:, 0], C.pts[:, 1], C.s
    level = float(level)
    rec = {"level_H": level, "measurable": False, "note": None, "x_back_H": None, "back_clipped_at_frame_edge": None,
           "x_inner_H": None, "x_front_H": None, "overhung": None, "inner_on_segment": None,
           "n_back_crossings": 0, "n_front_crossings": 0, "width_full_H": None, "width_body_H": None,
           "cavity_gap_H": None, "front_from_crest_H": None, "inner_from_crest_H": None, "back_from_crest_H": None}
    xb, _sb, _db = _level_crossings(x, z, s, level, 0, i_c)
    xf, sf, _df = _level_crossings(x, z, s, level, i_c, i_e)
    rec["n_back_crossings"], rec["n_front_crossings"] = int(xb.size), int(xf.size)
    if z[i_c] <= level:
        rec["note"] = "level is not below the crest"
        return rec
    if xf.size == 0:
        rec["note"] = "the front face does not come down to this level inside the profile"
        return rec
    clipped = bool(z[0] >= level)
    if not clipped and xb.size == 0:
        rec["note"] = "the back does not cross this level"
        return rec
    rec["measurable"] = True
    rec["back_clipped_at_frame_edge"] = clipped
    x_back = float(x[0]) if clipped else float(xb.min())
    order = np.argsort(xf)
    x_front = float(xf[order[-1]])
    rec.update({"x_back_H": x_back, "x_front_H": x_front, "width_full_H": x_front - x_back,
                "front_from_crest_H": x_front - x_c, "back_from_crest_H": None if clipped else x_c - x_back,
                "overhung": bool(xf.size >= 3)})
    if clipped:
        rec["note"] = "the back is outside the frame at this level: x_back = left end of the contour (frame edge), widths are measured from there"
    if xf.size >= 3:
        x_inner = float(xf[order[0]])
        rec.update({"x_inner_H": x_inner, "width_body_H": x_inner - x_back, "inner_from_crest_H": x_inner - x_c,
                    "cavity_gap_H": float(xf[order[1]]) - x_inner,
                    "inner_on_segment": "inner_arc" if (s_t is not None and sf[order[0]] >= s_t) else "head"})
    return rec


SHAPE_LABEL = "report only - shape descriptors relative to the contour's own crest height h (no thresholds)"
_SHAPE_SECTION_KEYS = ("width_full", "width_body", "front_from_crest", "inner_from_crest", "back_from_crest", "cavity_gap")


def _frac_tag(frac):
    return "h%02d" % int(round(100.0 * float(frac)))


def _shape_descriptors(C, i_c, s_t, i_e, x_c, h, o, cavity, P):
    """測定済みの一断面について、報告専用の形状記述子を求める。shape_descriptors を参照。"""
    z_still = float(P["z_still_H"])
    ok = bool(h > 1e-9)
    out = {"report_only": True, "label": SHAPE_LABEL, "h_H": float(h), "levels_frac_h": [float(v) for v in P["shape_levels_frac_h"]],
           "sections": {}, "o_over_h": (float(o) / h) if ok else None, "cavity_depth_over_h": (float(cavity) / h) if ok else None,
           "aspect_ratio": None, "aspect_ratio_back_clipped": None, "aspect_ratio_h75": None, "aspect_ratio_h75_back_clipped": None,
           "definition": "sections at z_still + f * h for f in levels_frac_h (h = the contour's OWN crest height above z_still); every "
                         "'*_over_h' value is the length of the same name (W sections) divided by h; aspect_ratio = width_full at 0.5 h / h "
                         "(aspect_ratio_h75: at 0.75 h, where the painting's back is still inside the frame); '*_back_clipped' = the back is "
                         "outside the frame at that level, so the width is measured from the left frame edge and does NOT scale with the body"}
    if not ok:
        return out

    def section(frac):
        rec = _section_record(C, z_still + float(frac) * h, i_c, s_t, i_e, x_c)
        rec["frac_of_h"] = float(frac)
        for k in _SHAPE_SECTION_KEYS:
            v = rec.get(k + "_H")
            rec[k + "_over_h"] = None if v is None else float(v) / h
        return rec

    for frac in out["levels_frac_h"]:
        out["sections"][_frac_tag(frac)] = section(frac)
    for frac, key in ((0.5, "aspect_ratio"), (0.75, "aspect_ratio_h75")):
        rec = out["sections"].get(_frac_tag(frac)) or section(frac)
        out[key] = rec["width_full_over_h"]
        out[key + "_back_clipped"] = rec["back_clipped_at_frame_edge"]
    return out


def shape_descriptors(pts_H, metrics=None, params=None):
    """幅が広く高さが低い形の差も相殺しない、しきい値のない報告専用の形状記述子。W は標的とモデルを同じ絶対高さで切るため、幅を 5 % 広げ高さを 1.9 % 下げた例では Z=0.75 H の幅が逆に -5 % と読まれた。ここでは各輪郭自身の波頂高 h の比率で切り、長さも h で割る。幅 k 倍・高さ m 倍なら各値は k/m となる。
結果は h_H、h25/h50/h75 の各 sections（水平幅、波頂からの距離、空洞の間隔を h で割ったもの）、o_over_h、cavity_depth_over_h、各種 aspect_ratio を含む。measure_profile の shape キーにも同じ辞書を入れる。"""
    m = metrics or measure_profile(pts_H, params)
    return m["shape"]


def compare_shape_descriptors(model_shape, target_shape):
    """各輪郭自身の h で正規化した形状記述子をモデルと標的で比較する。diff はモデル−標的、diff_pct_of_target は標的の絶対値に対する %。片方だけで波背が画面端で切れる、張り出しの有無が異なる、または両方の波背が切れていて画像端に依存する幅では comparable=false とする。"""
    rows = []

    def row(name, mv, tv, frac=None, comparable=True, note=None):
        d = None if (mv is None or tv is None) else float(mv - tv)
        rel = None if (d is None or abs(tv) < 1e-9) else 100.0 * d / abs(tv)
        rows.append({"name": name, "frac_of_h": frac, "unit": "1 (length / own h)", "model": mv, "target": tv, "diff": d,
                     "diff_pct_of_target": rel, "comparable": bool(comparable and d is not None), "note": note})

    row("h_H", model_shape.get("h_H"), target_shape.get("h_H"), note="crest height above z_still (H units), for reference")
    rows[-1]["unit"] = "H"
    for tag in sorted(set(model_shape.get("sections", {})) | set(target_shape.get("sections", {}))):
        ms, ts = model_shape["sections"].get(tag), target_shape["sections"].get(tag)
        if ms is None or ts is None:
            continue
        both = bool(ms["measurable"] and ts["measurable"])
        same = both and ms["back_clipped_at_frame_edge"] == ts["back_clipped_at_frame_edge"] and ms["overhung"] == ts["overhung"]
        clipped = both and bool(ms["back_clipped_at_frame_edge"] or ts["back_clipped_at_frame_edge"])
        note = []
        if not both:
            note.append("not measurable (model: %s; target: %s)" % (ms.get("note"), ts.get("note")))
        else:
            if clipped:
                note.append("back outside the frame (model %s, target %s): widths start at the left frame edge, which does not scale with the body"
                            % (ms["back_clipped_at_frame_edge"], ts["back_clipped_at_frame_edge"]))
            if ms["overhung"] != ts["overhung"]:
                note.append("section overhung: model %s, target %s" % (ms["overhung"], ts["overhung"]))
        for k in _SHAPE_SECTION_KEYS:
            from_back = k in ("width_full", "width_body", "back_from_crest")
            row("%s.%s_over_h" % (tag, k), ms.get(k + "_over_h"), ts.get(k + "_over_h"), frac=ms.get("frac_of_h"),
                comparable=same and not (from_back and clipped), note="; ".join(note) or None)
    row("o_over_h", model_shape.get("o_over_h"), target_shape.get("o_over_h"))
    row("cavity_depth_over_h", model_shape.get("cavity_depth_over_h"), target_shape.get("cavity_depth_over_h"))
    for key in ("aspect_ratio", "aspect_ratio_h75"):
        cm, ctg = model_shape.get(key + "_back_clipped"), target_shape.get(key + "_back_clipped")
        row(key, model_shape.get(key), target_shape.get(key), frac=0.5 if key == "aspect_ratio" else 0.75,
            comparable=not (cm or ctg),
            note=None if not (cm or ctg) else "back outside the frame at this level (model %s, target %s): the width starts at the left frame edge" % (cm, ctg))
    return rows


def _width_metrics(C, i_c, s_c, s_t, i_e, x_c, o, cavity, P):
    """測定済みの一断面について、報告専用の大きさの指標を求める。width_metrics を参照。"""
    x, z, s = C.pts[:, 0], C.pts[:, 1], C.s
    z_still = float(P["z_still_H"])
    sections = {}
    for level in [float(v) for v in P["width_levels_H"]]:
        sections[_level_tag(level)] = _section_record(C, level, i_c, s_t, i_e, x_c)
    # 輪郭の左端～谷の終端と静水面の間の面積。靴紐公式を用い、空洞は外側とする。
    p = C.slice_pts(0.0, float(s[i_e]))
    px_, pz_ = p[:, 0], np.maximum(p[:, 1], z_still)
    qx = np.concatenate([px_, [px_[-1], px_[0]]])
    qz = np.concatenate([pz_, [z_still, z_still]])
    area = 0.5 * abs(float(np.sum(qx * np.roll(qz, -1) - np.roll(qx, -1) * qz)))
    return {"report_only": True, "label": WIDTH_LABEL, "levels_H": [float(v) for v in P["width_levels_H"]],
            "sections": sections, "o_H": float(o), "cavity_depth_H": float(cavity),
            "area_above_still_water_H2": area, "x_crest_H": float(x_c), "x_left_end_H": float(x[0]),
            "area_definition": "area enclosed by the contour from its left end (left frame edge) to the trough end, the vertical "
                               "at the left end and Z = z_still; the cavity under the head is outside"}


def width_metrics(pts_H, metrics=None, params=None):
    """順序付き断面のしきい値のない大きさの指標。ユーザーの判断待ち。z25/z50/z75 の各高さで、波背・内側・前面の X、画面端で切れているか、張り出しの有無、全幅・胴体幅・空洞の間隔・波頂からの距離を記録する。o_H、cavity_depth_H、静水面より上の面積も含む。measure_profile の W キーにも同じ辞書を入れる。"""
    m = metrics or measure_profile(pts_H, params)
    return m["W"]


_W_SECTION_KEYS = ("width_full_H", "width_body_H", "front_from_crest_H", "inner_from_crest_H", "back_from_crest_H", "cavity_gap_H")


def compare_width_metrics(model_W, target_W):
    """報告専用の大きさをモデルと標的で比較する。diff はモデル−標的、diff_pct_of_target は標的の絶対値に対する %（標的がほぼ 0 なら None）、diff_pct_h は長さの差を画像高に対する % で示す。波背の切れ方や張り出しの有無が異なる断面は comparable=false。"""
    rows = []

    def row(name, mv, tv, unit, level=None, comparable=True, note=None):
        d = None if (mv is None or tv is None) else float(mv - tv)
        rel = None if (d is None or abs(tv) < 1e-9) else 100.0 * d / abs(tv)
        rows.append({"name": name, "level_H": level, "unit": unit, "model": mv, "target": tv, "diff": d,
                     "diff_pct_of_target": rel, "diff_pct_h": None if (d is None or unit != "H") else float(H_to_pct_h(d)),
                     "comparable": bool(comparable and d is not None), "note": note})

    for tag in sorted(set(model_W.get("sections", {})) | set(target_W.get("sections", {}))):
        ms, ts = model_W["sections"].get(tag), target_W["sections"].get(tag)
        if ms is None or ts is None:
            continue
        same = (ms["measurable"] and ts["measurable"] and ms["back_clipped_at_frame_edge"] == ts["back_clipped_at_frame_edge"]
                and ms["overhung"] == ts["overhung"])
        note = []
        if ms["measurable"] and ts["measurable"]:
            if ms["back_clipped_at_frame_edge"] or ts["back_clipped_at_frame_edge"]:
                note.append("back outside the frame (model %s, target %s): widths from the left frame edge"
                            % (ms["back_clipped_at_frame_edge"], ts["back_clipped_at_frame_edge"]))
            if ms["overhung"] != ts["overhung"]:
                note.append("section overhung: model %s, target %s" % (ms["overhung"], ts["overhung"]))
        else:
            note.append("not measurable (model: %s; target: %s)" % (ms.get("note"), ts.get("note")))
        for k in _W_SECTION_KEYS:
            row("%s.%s" % (tag, k), ms.get(k), ts.get(k), "H", level=ms["level_H"], comparable=same, note="; ".join(note) or None)
    row("o_H", model_W.get("o_H"), target_W.get("o_H"), "H")
    row("cavity_depth_H", model_W.get("cavity_depth_H"), target_W.get("cavity_depth_H"), "H")
    row("area_above_still_water_H2", model_W.get("area_above_still_water_H2"), target_W.get("area_above_still_water_H2"), "H^2")
    return rows


def _back_slopes(C, s_c, P):
    w = float(pct_h_to_H(P["s4_tangent_window_pct_h"]))
    Lleft = float(pct_h_to_H(P["s4_left_window_pct_h"]))
    b0, b1 = (float(pct_h_to_H(v)) for v in P["s4_before_crest_window_pct_h"])
    out = {"left_end_deg": None, "mid_max_deg": None, "before_crest_deg": None, "mid_max_at": None,
           "mid_is_steepest": None, "flattens_towards_crest": None, "slope_curve": None}
    if s_c < max(Lleft, b1) + w:
        out["note"] = "back too short inside the frame for the S4 windows"
        if s_c > w:
            ss = np.arange(0.5 * w, s_c - 0.5 * w + 1e-12, float(pct_h_to_H(0.25)))
            sl = C.tangent_deg(ss, w, 0.0, s_c)
            k = int(np.argmax(sl))
            out["mid_max_deg"] = float(sl[k])
        return out
    out["left_end_deg"] = float(C.chord_deg(0.0, Lleft))
    out["before_crest_deg"] = float(C.chord_deg(s_c - b1, s_c - b0))
    ss = np.arange(0.5 * w, s_c - 0.5 * w + 1e-12, float(pct_h_to_H(0.25)))
    sl = C.tangent_deg(ss, w, 0.0, s_c)
    k = int(np.argmax(sl))
    p = C.at(ss[k])
    out["mid_max_deg"] = float(sl[k])
    out["mid_max_at"] = {"H": [float(p[0]), float(p[1])], "s": float(ss[k]), "frac_of_back": float(ss[k] / s_c)}
    out["mid_is_steepest"] = bool(Lleft <= ss[k] <= s_c - b1 and sl[k] > out["left_end_deg"]
                                  and sl[k] > out["before_crest_deg"])
    after = sl[k:]
    run_min = np.minimum.accumulate(after)
    rise = float(np.max(after - run_min)) if after.size else 0.0
    out["max_slope_increase_after_steepest_deg"] = rise
    out["flattens_towards_crest"] = bool(rise <= P["s4_monotone_tol_deg"])
    step = max(1, ss.size // 200)
    out["slope_curve"] = {"s_H": [float(v) for v in ss[::step]], "deg": [float(v) for v in sl[::step]]}
    return out


# ====================================================================== S8
def vertex_window_turns(C, lo, hi, window):
    """折れ線自身が [lo, hi] 内の弧長 `window` の閉じた窓で曲がる正味角度を求める。窓 [a,b] に含む元の頂点の符号付き外角を合計する（反時計回りが正）。弦や標本位相を使わないため、頂点上の折れはどこにあっても全角度を読み、薄い縁の 180 度超の回転も折り返さない。各内部頂点で始まる窓と終わる窓を調べれば全位置の最大値が得られる。範囲が window 未満なら [lo,hi] 一窓。窓の始点・終点・角度の配列を返す。"""
    if not isinstance(C, Curve):
        C = Curve(C)
    lo, hi, w = float(max(0.0, lo)), float(min(C.length, hi)), float(window)
    if C.pts.shape[0] < 3 or hi <= lo or w <= 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    d = np.degrees(np.arctan2(np.diff(C.pts[:, 1]), np.diff(C.pts[:, 0])))
    ext = wrap_deg(np.diff(d))                                   # 内部頂点 1～n-2 の外角。
    sv = C.s[1:-1]
    T = np.concatenate([[0.0], np.cumsum(ext)])                  # T[k] = sum(ext[:k])
    tol = 1e-12 * max(1.0, C.length)
    if hi - lo <= w:
        a = np.array([lo])
        b = np.array([hi])
    else:
        inside = sv[(sv >= lo - tol) & (sv <= hi + tol)]
        a = np.unique(np.clip(np.concatenate([inside, inside - w, [lo]]), lo, hi - w))
        b = a + w
    k_lo = np.searchsorted(sv, a - tol, side="left")
    k_hi = np.searchsorted(sv, b + tol, side="right")
    return a, b, T[k_hi] - T[k_lo]


def _s8_tip_zone_pct_h(P):
    """報告専用の S8 補助値が指す波頭先端周辺の弧長半幅（画像高に対する %）。除外設定が正ならその幅、なければ s8_tip_report_zone_pct_h（旧判定で使った 2 %）とする。"""
    excl = float(P["s8_tip_exclusion_pct_h"])
    return excl if excl > 0.0 else float(P.get("s8_tip_report_zone_pct_h", 2.0))


def _vertex_window_report(C, s_crest, s_tip, s_end, P):
    """判定用 S8 に並べる報告専用の頂点窓指標。全窓の最大値、先端除外範囲の外側・内側、各区間、先端をまたぐ窓の最大値と位置を記録する。s8_vertex_short_windows_pct_h の短い窓についても同じ指標を求める。"""
    excl = float(pct_h_to_H(_s8_tip_zone_pct_h(P)))           # 報告範囲。除外範囲を指定した場合はそれと一致する。

    def seg_of(sv):
        if sv <= s_crest:
            return "back"
        if s_tip is None:
            return "front"
        return "head" if sv <= s_tip else "inner_arc"

    def one(w_pct):
        a, b, t = vertex_window_turns(C, 0.0, s_end, float(pct_h_to_H(w_pct)))
        rep = {"window_pct_h": float(w_pct), "n_windows": int(a.size), "max_deg": None, "max_at": None, "per_segment": {},
               "max_outside_tip_exclusion_deg": None, "tip_zone_deg": None, "across_tip_deg": None}
        if a.size == 0:
            return rep
        mag, c = np.abs(t), 0.5 * (a + b)
        k = int(np.argmax(mag))
        p = C.at(c[k])
        rep["max_deg"] = float(mag[k])
        rep["max_at"] = {"H": [float(p[0]), float(p[1])], "s": float(c[k]), "segment": seg_of(c[k]), "window_s": [float(a[k]), float(b[k])],
                         "signed_turn_deg": float(t[k])}
        outside = np.ones(a.size, bool) if s_tip is None else (np.abs(c - s_tip) > excl)
        if outside.any():
            rep["max_outside_tip_exclusion_deg"] = float(mag[outside].max())
            if s_tip is None:
                groups = (("back", c <= s_crest), ("front", c > s_crest))
            else:
                groups = (("back", c <= s_crest), ("head", (c > s_crest) & (c <= s_tip)), ("inner_arc", c > s_tip))
            for nm, sel in groups:
                sel = sel & outside
                if sel.any():
                    rep["per_segment"][nm] = float(mag[sel].max())
        if s_tip is not None:
            if (~outside).any():
                rep["tip_zone_deg"] = float(mag[~outside].max())
            across = (a <= s_tip) & (b >= s_tip)
            if across.any():
                rep["across_tip_deg"] = float(mag[across].max())
        return rep

    out = one(float(P["s8_spacing_pct_h"]))
    out["report_only"] = True
    out["definition"] = ("net turning of the polyline itself (sum of the exterior angles of its own vertices) over every closed "
                         "arc-length window that starts or ends on a vertex; max_deg excludes nothing")
    out["short_windows"] = [one(float(w)) for w in (P.get("s8_vertex_short_windows_pct_h") or [])]
    return out


def s8_smoothness(C, s_crest, s_tip, s_end, params=None):
    """仕様 S8 の、隣接標本間の接線差を求める。C は Curve または (N,2) の点列。先端があれば [0,s_tip] と [s_tip,s_end] を別に標本化し、なければ全区間を使う。各位相で spacing 間隔の弦の方向を求め、接合点における隣接弦の角度差を測る。
2026-09-20 の強化では先端自身と両側の各位相にも接合点を置き、二つの弦で先端をまたぐ。既定の s8_tip_exclusion_pct_h=0 では全接合点を判定し、尖った先端は失敗する。正値を指定した場合だけ先端付近を判定から除く。
結果は判定用最大角、位置、区間別の値、標本間隔、接合点数と判定数、先端をまたぐ角度を含む。報告専用として旧定義での最大値 max_tip_zone_excluded_deg、先端上の角度 tip_junction_deg、先端区間の回転 tip_turn_deg、除外なしの最大値、折れ線自身の頂点窓での最大角と短い窓の詳細も含む。"""
    P = params if (params is not None and "s8_spacing_pct_h" in params) else get_params(params)
    if not isinstance(C, Curve):
        C = Curve(C)
    sp = float(pct_h_to_H(P["s8_spacing_pct_h"]))
    nph = max(1, int(P["s8_n_phases"]))
    excl = float(pct_h_to_H(P["s8_tip_exclusion_pct_h"]))
    stretches = [(0.0, s_tip), (s_tip, s_end)] if s_tip is not None else [(0.0, s_end)]
    js, jd = [], []
    for a, b in stretches:
        for ph in range(nph):
            start = a + sp * ph / nph
            m = int(math.floor((b - start) / sp + 1e-9))
            if m < 2:
                continue
            ss = start + sp * np.arange(m + 1)
            p = C.at(ss)
            d = np.degrees(np.arctan2(np.diff(p[:, 1]), np.diff(p[:, 0])))
            js.append(ss[1:-1])
            jd.append(wrap_deg(np.diff(d)))
    js = np.concatenate(js) if js else np.zeros(0)
    jd = np.concatenate(jd) if jd else np.zeros(0)
    no_exclusion = s_tip is None or excl <= 0.0
    judged = np.ones(js.size, bool) if no_exclusion else (np.abs(js - s_tip) > excl)
    zone = float(pct_h_to_H(_s8_tip_zone_pct_h(P)))
    legacy = np.ones(js.size, bool) if s_tip is None else (np.abs(js - s_tip) > zone)

    def seg_of(sv):
        if sv <= s_crest:
            return "back"
        if s_tip is None:
            return "front"
        return "head" if sv <= s_tip else "inner_arc"

    # 波頭先端の位置に接合点を一つ追加し、先端の前後の弦を比較する。
    # 上の二つの区間は別々に標本化されるため、これがないと先端をまたぐ接合点がない。
    # 実際、40 度の尖りが除外なしの旧最大値でも 10.3 度にしか見えなかった。
    # この単独の接合点は報告専用で、_junction_s や判定値には入れない。
    tip_junction = None
    if s_tip is not None:
        a0, a1 = max(0.0, s_tip - sp), min(float(s_end), s_tip + sp)
        if s_tip - a0 > 1e-12 and a1 - s_tip > 1e-12:
            tip_junction = float(wrap_deg(C.chord_deg(s_tip, a1) - C.chord_deg(a0, s_tip)))
    unexcl_old = float(np.max(np.abs(jd))) if jd.size else None
    unexcl = unexcl_old if tip_junction is None else max(abs(tip_junction), unexcl_old or 0.0)
    # 各位相ずらしで先端をまたぐ接合点を作る。k=0 は上記の先端そのものの点。
    # 両弦は [0,s_end] 内に置く。S4 の「頂部は丸い」は _junction_s / _junction_diff を
    # 参照するため、それらとは分けて保持する。
    ts, td = [], []
    if s_tip is not None:
        for k in range(-(nph - 1), nph):
            sj = s_tip + sp * k / nph
            if k == 0:
                if tip_junction is not None:
                    ts.append(float(s_tip))
                    td.append(tip_junction)
                continue
            if sj - sp < 0.0 or sj + sp > float(s_end):
                continue
            ts.append(float(sj))
            td.append(float(wrap_deg(C.chord_deg(sj, sj + sp) - C.chord_deg(sj - sp, sj))))
    ts, td = np.asarray(ts, dtype=np.float64), np.asarray(td, dtype=np.float64)
    t_judged = np.ones(ts.size, bool) if no_exclusion else (np.abs(ts - s_tip) > excl)

    out = {"spacing_pct_h": float(P["s8_spacing_pct_h"]), "n_phases": nph, "n_junctions": int(js.size) + int(ts.size),
           "n_judged": int(judged.sum()) + int(t_judged.sum()), "tip_exclusion_pct_h": float(P["s8_tip_exclusion_pct_h"]),
           "tip_report_zone_pct_h": float(_s8_tip_zone_pct_h(P)),
           "max_tangent_diff_deg": None, "max_at": None, "per_segment": {}, "tip_turn_deg": None,
           "max_unexcluded_deg": unexcl, "tip_junction_deg": tip_junction,
           "max_unexcluded_without_tip_junction_deg": unexcl_old,
           "max_tip_zone_excluded_deg": float(np.max(np.abs(jd[legacy]))) if legacy.any() else None,
           "across_tip": {"n_junctions": int(ts.size), "n_judged": int(t_judged.sum()),
                          "max_deg": float(np.max(np.abs(td))) if ts.size else None,
                          "max_at_s": float(ts[int(np.argmax(np.abs(td)))]) if ts.size else None},
           "_junction_s": js.tolist(), "_junction_diff": jd.tolist(), "_junction_judged": judged.tolist(),
           "_tip_junction_s": ts.tolist(), "_tip_junction_diff": td.tolist(), "_tip_junction_judged": t_judged.tolist()}
    vw = _vertex_window_report(C, s_crest, s_tip, float(s_end), P)
    out["max_vertex_window_turn_deg"] = vw["max_deg"]
    out["vertex_window_turn"] = vw
    all_s = np.concatenate([js[judged], ts[t_judged]])
    all_a = np.abs(np.concatenate([jd[judged], td[t_judged]]))
    all_x = np.concatenate([np.zeros(int(judged.sum()), bool), np.ones(int(t_judged.sum()), bool)])
    if all_s.size:
        k = int(np.argmax(all_a))
        sk = all_s[k]
        p = C.at(sk)
        out["max_tangent_diff_deg"] = float(all_a[k])
        out["max_at"] = {"H": [float(p[0]), float(p[1])], "s": float(sk), "segment": seg_of(sk), "across_tip": bool(all_x[k])}
        names = np.array([seg_of(v) for v in all_s])
        for nm in np.unique(names):
            out["per_segment"][str(nm)] = float(all_a[names == nm].max())
    if s_tip is not None:
        d_before = float(C.chord_deg(max(0.0, s_tip - zone - sp), max(0.0, s_tip - zone)))
        d_after = float(C.chord_deg(min(s_end, s_tip + zone), min(s_end, s_tip + zone + sp)))
        out["tip_turn_deg"] = float((d_before - d_after) % 360.0)      # 先端付近の報告範囲をまたぐ時計回りの角度変化。
    return out


# ====================================================================== 距離と S7
def point_polyline_distance(points, poly, chunk=512):
    """各点から折れ線までの距離と、最近傍の辺の添字を返す。"""
    P = np.asarray(points, dtype=np.float64)
    Q = np.asarray(poly, dtype=np.float64)
    if Q.shape[0] == 1:
        d = np.hypot(P[:, 0] - Q[0, 0], P[:, 1] - Q[0, 1])
        return d, np.zeros(P.shape[0], np.int64)
    A, B = Q[:-1], Q[1:]
    AB = B - A
    L2 = (AB ** 2).sum(axis=1)
    L2 = np.where(L2 > 0, L2, 1.0)
    dist = np.empty(P.shape[0])
    idx = np.empty(P.shape[0], np.int64)
    for i in range(0, P.shape[0], chunk):
        p = P[i:i + chunk, None, :]
        t = np.clip(((p - A[None]) * AB[None]).sum(axis=2) / L2[None], 0.0, 1.0)
        c = A[None] + t[:, :, None] * AB[None]
        d2 = ((p - c) ** 2).sum(axis=2)
        k = d2.argmin(axis=1)
        idx[i:i + chunk] = k
        dist[i:i + chunk] = np.sqrt(d2[np.arange(k.size), k])
    return dist, idx


def signed_point_polyline_distance(points, poly, chunk=512):
    """各点から折れ線までの距離に、その点が折れ線のどちら側にあるかを加える。このプロジェクトの輪郭は波の胴体を進行方向の右側に置いてたどるため、左側は空気側。符号付き距離は胴体外側で正、内側で負、線上で 0 とする。最近点が頂点なら、両側の単位接線の平均を接線とする。距離・最近傍辺添字・符号付き距離を返す。"""
    Pp = np.asarray(points, dtype=np.float64)
    Q = np.asarray(poly, dtype=np.float64)
    dist, idx = point_polyline_distance(Pp, Q, chunk)
    if Q.shape[0] < 2 or Pp.shape[0] == 0:
        return dist, idx, np.zeros(Pp.shape[0])
    AB = Q[1:] - Q[:-1]
    L = np.hypot(AB[:, 0], AB[:, 1])
    U = AB / np.where(L > 0, L, 1.0)[:, None]                     # 各辺の単位接線。
    A = Q[idx]
    t = np.clip(((Pp - A) * AB[idx]).sum(axis=1) / np.where(L[idx] > 0, L[idx] ** 2, 1.0), 0.0, 1.0)
    near = A + t[:, None] * AB[idx]
    r = Pp - near
    tang = U[idx].copy()
    at_start = (t <= 0.0) & (idx > 0)
    at_end = (t >= 1.0) & (idx < AB.shape[0] - 1)
    tang[at_start] = U[idx[at_start]] + U[idx[at_start] - 1]
    tang[at_end] = U[idx[at_end]] + U[idx[at_end] + 1]
    side = np.sign(tang[:, 0] * r[:, 1] - tang[:, 1] * r[:, 0])
    return dist, idx, side * dist


def load_base_contour(path=None):
    """gw.base_contour.v1 の JSON を読み込む。既定値は target/base_contour.json。"""
    path = path or paths.BASE_CONTOUR_JSON
    with open(path, "r", encoding="utf-8") as fh:
        bc = json.load(fh)
    if bc.get("schema") != "gw.base_contour.v1":
        raise ValueError("unexpected base contour schema %r in %s" % (bc.get("schema"), path))
    return bc


def base_contour_polyline(bc):
    """基礎輪郭の三つの区間を接続する。共有端点は重複させない。H 座標の点列、区間 ID（0 波背、1 波頭、2 内側円弧）、in_S7 フラグ、波頂・先端の添字、区間名を返す。"""
    names = ["back", "head", "inner_arc"]
    by = {sg["name"]: sg for sg in bc["segments"]}
    pts, sid, flag, bounds = [], [], [], []
    for k, nm in enumerate(names):
        sg = by[nm]
        p = np.asarray(sg["points_H"], dtype=np.float64)
        f = np.asarray(sg.get("in_S7", [True] * len(p)), dtype=bool)
        n_prev = sum(len(q) for q in pts)
        if pts and np.allclose(pts[-1][-1], p[0], atol=1e-9):
            p, f = p[1:], f[1:]                  # 共有接合点は前の区間の点を残す。
            bounds.append(n_prev - 1)
        else:
            bounds.append(n_prev)                # この区間の最初の点が接合点。
        pts.append(p)
        sid.append(np.full(len(p), k))
        flag.append(f)
    P = np.concatenate(pts)
    return {"pts_H": P, "seg_id": np.concatenate(sid), "in_S7": np.concatenate(flag),
            "crest_index": int(bounds[1]), "tip_index": int(bounds[2]), "names": names}


def segmentation_check(poly, json_metrics, params=None, bc=None):
    """同じ折れ線上で、基礎輪郭 JSON の接合点とライブラリが検出する波頂・先端・最深点が一致するか調べる。モデルは常に検出結果で分割されるため、S5/S7 を同じ区間として比べるには基礎輪郭も一致する必要がある。許容値、整合性、最大距離、各特徴点の JSON 座標と検出座標・差、張り出しと房の情報を返す。"""
    P = get_params(params)
    det = measure_profile(poly["pts_H"], P)
    tol = float(P["segmentation_check_tol_pct_h"])
    items, worst, missing = {}, None, []
    for key in ("crest", "head_tip", "inner_deepest"):
        a, b = json_metrics["landmarks"].get(key), det["landmarks"].get(key)
        if a is None or b is None:
            items[key] = {"json_H": None if a is None else a["H"], "detected_H": None if b is None else b["H"],
                          "dist_pct_h": None, "ds_pct_h": None}
            if (a is None) != (b is None):
                missing.append(key)
            continue
        d = float(H_to_pct_h(math.hypot(a["H"][0] - b["H"][0], a["H"][1] - b["H"][1])))
        items[key] = {"json_H": a["H"], "detected_H": b["H"], "dist_pct_h": d, "ds_pct_h": float(H_to_pct_h(b["s"] - a["s"]))}
        if worst is None or d > worst[1]:
            worst = (key, d)
    out = {"tol_pct_h": tol, "tip_rule": P["tip_rule"], "items": items,
           "max_dist_pct_h": None if worst is None else worst[1], "worst": None if worst is None else worst[0],
           "only_one_side_has": missing, "detected_overhanging": bool(det["overhanging"]),
           "json_overhanging": bool(json_metrics["overhanging"]), "detected_head_lobes": det["head_lobes"],
           "detected_onset_H": None if det["landmarks"].get("overhang_onset") is None else det["landmarks"]["overhang_onset"]["H"],
           "detected_phi_deg": det["phi_deg"], "json_phi_deg": json_metrics["phi_deg"]}
    out["consistent"] = bool(worst is not None and not missing and worst[1] <= tol
                             and det["overhanging"] == json_metrics["overhanging"])
    block = {}
    for key in ("crest", "head_tip", "inner_deepest"):
        jl = ((bc or {}).get("landmarks") or {}).get(key)
        b = det["landmarks"].get(key)
        if isinstance(jl, dict) and jl.get("H") is not None and b is not None:
            block[key] = float(H_to_pct_h(math.hypot(jl["H"][0] - b["H"][0], jl["H"][1] - b["H"][1])))
    out["json_landmarks_block"] = block
    return out


def measure_base_contour(bc, params=None, use_json_segmentation=True, check_detection=True):
    """基礎輪郭に measure_profile を適用する。use_json_segmentation では JSON の区間接合点を波頂・先端とし、そうでなければ再検出する。check_detection 指定時は同じ折れ線上で自動検出を追加し、不整合を記録する。"""
    poly = base_contour_polyline(bc)
    if not use_json_segmentation:
        return measure_profile(poly["pts_H"], params)
    m = measure_profile(poly["pts_H"], params, crest_index=poly["crest_index"], tip_index=poly["tip_index"])
    if check_detection:
        m["segmentation_check"] = segmentation_check(poly, m, params, bc)
    return m


def _stats(d_H):
    d = H_to_pct_h(np.asarray(d_H, dtype=np.float64))
    if d.size == 0:
        return {"n": 0, "mean_pct_h": None, "p95_pct_h": None, "max_pct_h": None}
    return {"n": int(d.size), "mean_pct_h": float(d.mean()), "p95_pct_h": float(np.percentile(d, 95)),
            "max_pct_h": float(d.max())}


def _signed_stats(signed_H):
    """モデルが標的の胴体外側にある場合を正とした、画像高に対する % の符号付き法線偏差。"""
    d = H_to_pct_h(np.asarray(signed_H, dtype=np.float64))
    if d.size == 0:
        return {"signed_mean_pct_h": None, "signed_median_pct_h": None, "signed_p05_pct_h": None, "signed_p95_pct_h": None,
                "frac_model_outside": None}
    return {"signed_mean_pct_h": float(d.mean()), "signed_median_pct_h": float(np.median(d)),
            "signed_p05_pct_h": float(np.percentile(d, 5)), "signed_p95_pct_h": float(np.percentile(d, 95)),
            "frac_model_outside": float((d > 0).mean())}


def s7_deviation(model_pts_H, base, model_metrics=None, params=None):
    """区間ごとのモデルと基礎輪郭の偏差（仕様 S7）。モデルの順序付き点列、基礎輪郭、任意の既計算 measure_profile を受け取る。モデル→基礎輪郭と基礎輪郭→モデルの両方向で標本数、平均、95 パーセンタイル、最大値を求め、各区間の判定値は悪い方を使う。基礎輪郭の in_S7=false 点は除く。
報告専用の符号付き平均・中央値・5/95 パーセンタイルと、モデルが胴体外側にある割合も返す。正は空気側・空洞側へ膨らむ方向、負は内側へ細くなる方向。幅が広く低い形では符号なしの偏差が小さくても、符号がずれの方向を示す。"""
    P = get_params(params)
    poly = base if "pts_H" in base else base_contour_polyline(base)
    mm = model_metrics or measure_profile(model_pts_H, P)
    Cm = Curve(model_pts_H)
    Cb = Curve(poly["pts_H"])
    b_idx = Cb.index_map
    b_seg = poly["seg_id"][b_idx]
    b_flag = poly["in_S7"][b_idx]
    sp = float(pct_h_to_H(P["s7_sample_spacing_pct_h"]))
    margin = float(pct_h_to_H(P["s7_segment_margin_pct_h"]))
    # 基礎輪郭の各区間の弧長範囲。
    i_cb = int(np.searchsorted(b_idx, poly["crest_index"]))
    i_tb = int(np.searchsorted(b_idx, poly["tip_index"]))
    b_rng = {"back": (0.0, Cb.s[i_cb]), "head": (Cb.s[i_cb], Cb.s[i_tb]), "inner_arc": (Cb.s[i_tb], Cb.length)}
    out = {"n_base_points": int(len(b_idx)), "n_base_excluded": int((~b_flag).sum()), "segments_missing": []}
    edge_ok = b_flag[:-1] & b_flag[1:]
    for k, nm in enumerate(poly["names"]):
        m_rng = mm["segments_s"].get(nm)
        if m_rng is None:
            out[nm] = None
            out["segments_missing"].append(nm)
            continue
        # モデルから基礎輪郭への距離。
        mp = Cm.sub(m_rng[0], m_rng[1], sp)
        lo, hi = max(0.0, b_rng[nm][0] - margin), min(Cb.length, b_rng[nm][1] + margin)
        ia, ib = Cb.index_at(lo), Cb.index_at(hi)
        ia = max(0, ia - 1)
        target = Cb.pts[ia:ib + 1]
        d, e, sg = signed_point_polyline_distance(mp, target)
        counted = edge_ok[np.clip(ia + e, 0, len(edge_ok) - 1)]
        st_mb = _stats(d[counted])
        st_mb["n_skipped_not_in_S7"] = int((~counted).sum())
        st_mb.update(_signed_stats(sg[counted]))                 # 正値はモデルの標本が標的の胴体外側にあることを示す。
        # 基礎輪郭からモデルへの距離。
        sel = (b_seg == k) & b_flag
        bp = Cb.pts[sel]
        if bp.shape[0] > 1:
            # 基礎輪郭の点をほぼ同じ間隔まで間引く。
            keep = np.concatenate([[True], np.diff(np.floor(Cb.s[sel] / sp)) > 0])
            bp = bp[keep]
        lo_m, hi_m = max(0.0, m_rng[0] - margin), min(Cm.length, m_rng[1] + margin)
        tm = Cm.slice_pts(lo_m, hi_m)
        d2, _e2, sg2 = signed_point_polyline_distance(bp, tm) if bp.shape[0] else (np.zeros(0), None, np.zeros(0))
        st_bm = _stats(d2)
        st_bm.update(_signed_stats(-sg2))                        # 標的の点がモデル胴体の内側にあれば、モデルが標的の外側へ膨らんでいる。
        means = [v for v in (st_mb["mean_pct_h"], st_bm["mean_pct_h"]) if v is not None]
        p95s = [v for v in (st_mb["p95_pct_h"], st_bm["p95_pct_h"]) if v is not None]
        worst = None
        cand = []
        if counted.any():
            j = int(np.argmax(np.where(counted, d, -1.0)))
            cand.append((float(d[j]), mp[j], "model_to_base"))
        if d2.size:
            j = int(np.argmax(d2))
            cand.append((float(d2[j]), bp[j], "base_to_model"))
        if cand:
            c = max(cand, key=lambda t: t[0])
            worst = {"H": [float(c[1][0]), float(c[1][1])], "dev_pct_h": float(H_to_pct_h(c[0])), "direction": c[2]}
        sgn = st_mb["signed_mean_pct_h"] if st_mb["signed_mean_pct_h"] is not None else st_bm["signed_mean_pct_h"]
        out[nm] = {"model_to_base": st_mb, "base_to_model": st_bm,
                   "mean_dev_pct_h": max(means) if means else None,
                   "p95_dev_pct_h": max(p95s) if p95s else None, "worst_point": worst,
                   "signed_mean_dev_pct_h": sgn,
                   "signed_definition": "report only; + = model outside the target body, - = inside; % of image height"}
    return out


def contour_displacement(pts_a_H, pts_b_H, spacing_pct_h=0.5, z_min_H=None):
    """M5/M6 用の、二フレーム間の対称な輪郭変位。A の標本から B の折れ線への最近距離と逆方向を測る。z_min_H より下の標本（静水面に沿う区間など）は無視し、最大・95 パーセンタイル・平均の H 単位の変位を返す。"""
    Ca, Cb = Curve(pts_a_H), Curve(pts_b_H)
    sp = float(pct_h_to_H(spacing_pct_h))
    pa, pb = Ca.sub(0.0, Ca.length, sp), Cb.sub(0.0, Cb.length, sp)
    if z_min_H is not None:
        pa_s, pb_s = pa[pa[:, 1] >= z_min_H], pb[pb[:, 1] >= z_min_H]
    else:
        pa_s, pb_s = pa, pb
    ds = []
    if pa_s.shape[0]:
        ds.append(point_polyline_distance(pa_s, Cb.pts)[0])
    if pb_s.shape[0]:
        ds.append(point_polyline_distance(pb_s, Ca.pts)[0])
    if not ds:
        return {"max_H": 0.0, "p95_H": 0.0, "mean_H": 0.0, "n": 0}
    d = np.concatenate(ds)
    return {"max_H": float(d.max()), "p95_H": float(np.percentile(d, 95)), "mean_H": float(d.mean()), "n": int(d.size)}


def measure_sequence(profiles_H, params=None, disp_z_min_H=0.01):
    """フレームごとの順序付き断面から、仕様 6.2 の動きの量を計算する。各フレームの h、x_c、theta、theta_raw、o、空洞深さ、phi、張り出し状態、波頂・先端・最深点の座標、前フレームとの輪郭変位の最大・95 パーセンタイル・平均を同長の一覧で返す。初フレームの変位は None。静水面に沿う低い標本は除く。各フレームの詳細な measure_profile 結果は metrics に入る。"""
    keys = ("h", "x_c", "theta", "theta_raw", "o", "cavity_depth", "phi_deg", "crest_to_tip_deg", "overhanging",
            "trough_level_H", "reached_still_water")
    out = {k: [] for k in keys}
    out.update({"crest_H": [], "tip_H": [], "deepest_H": [], "disp_max_H": [], "disp_p95_H": [],
                "disp_mean_H": [], "metrics": []})
    prev = None
    for pts in profiles_H:
        m = measure_profile(pts, params)
        for k in keys:
            out[k].append(m[k])
        lm = m["landmarks"]
        out["crest_H"].append(lm["crest"]["H"])
        out["tip_H"].append(None if lm["head_tip"] is None else lm["head_tip"]["H"])
        out["deepest_H"].append(None if lm["inner_deepest"] is None else lm["inner_deepest"]["H"])
        if prev is None:
            d = {"max_H": None, "p95_H": None, "mean_H": None}
        else:
            d = contour_displacement(prev, pts, z_min_H=disp_z_min_H)
        out["disp_max_H"].append(d["max_H"])
        out["disp_p95_H"].append(d["p95_H"])
        out["disp_mean_H"].append(d["mean_H"])
        out["metrics"].append(m)
        prev = pts
    return out


# ====================================================================== 位置検査 S1 S2 S3 S5 S6
def position_checks(metrics, base=None, base_metrics=None, frame_obj=None):
    """S1、S2、S3、S5 と S6 の外側限界について、モデルと目標の位置差を求める。metrics はモデルの measure_profile、base は必要に応じた基礎輪郭 JSON。差はすべてモデル−目標で、水平距離も画像高に対する % に換算する。ここでは判定せず、paths.check_threshold で判定する。"""
    F = frame_obj or gw_frame.get_frame()
    spec = {k: [float(v) for v in F.pct_to_H(*pct)] for k, pct in gw_frame.SPEC_LANDMARKS_PCT.items()}
    out = {}

    def diff(p, q):
        dx = float(F.H_to_pct_h(p[0] - q[0]))
        dz = float(F.H_to_pct_h(p[1] - q[1]))
        return {"dx_pct_h": dx, "dz_pct_h": dz, "dist_pct_h": float(math.hypot(dx, dz))}

    lmk = metrics["landmarks"]
    out["S1"] = {"target_spec_H": spec["S1_crest"], "model_H": lmk["crest"]["H"],
                 "vs_spec": diff(lmk["crest"]["H"], spec["S1_crest"]),
                 "model_plateau": lmk.get("crest_plateau")}
    out["S2"] = {"target_spec_H": spec["S2_inner_arc_deepest"],
                 "model_H": None if lmk["inner_deepest"] is None else lmk["inner_deepest"]["H"],
                 "vs_spec": None if lmk["inner_deepest"] is None else diff(lmk["inner_deepest"]["H"], spec["S2_inner_arc_deepest"])}
    h_pct = float(F.H_to_pct_h(metrics["h"]))
    tl = metrics.get("trough_level_H")
    h_mt = None if tl is None else float(F.H_to_pct_h(lmk["crest"]["H"][1] - tl))
    out["S3"] = {"height_pct_h": h_pct, "height_err_pct_h": h_pct - F.height_pct,
                 "trough_level_H": tl,
                 "height_from_measured_trough_pct_h": h_mt,
                 "height_err_from_model_trough_pct_h": None if h_mt is None else h_mt - F.height_pct,
                 "reached_still_water": metrics.get("reached_still_water")}
    # 仕様の「谷から波頂までの高さ」に沿う S3。波頂 Z から、波の前にあるモデル自身の
    # 水位 metrics['trough_level_H'] を引く。前面の水位が z_still なら従来の S3 と同じ。
    # 海面が 3 % 高い場合は 3 % 小さくなり、Z=0 基準の S3 では見えない差を示す。
    z_still = float((metrics.get("params") or {}).get("z_still_H", 0.0))
    out["S3_from_model_trough"] = {
        "height_pct_h": h_mt, "height_err_pct_h": None if h_mt is None else h_mt - F.height_pct,
        "trough_level_H": tl, "trough_level_above_still_pct_h": None if tl is None else float(F.H_to_pct_h(tl - z_still)),
        "reached_still_water": metrics.get("reached_still_water"),
        "reached_still_water_tol_pct_h": metrics.get("reached_still_water_tol_pct_h"),
        "trough_lowest_H": None if lmk.get("trough_lowest") is None else lmk["trough_lowest"]["H"],
        "diff_to_S3_pct_h": None if h_mt is None else h_mt - h_pct,
        "definition": "crest Z minus the lowest Z of the profile between the inner-arc deepest point (crest when there is no "
                      "overhang) and the right end of the profile; % of image height; error = that minus height_pct (66)"}
    br = lmk.get("body_rightmost")
    if br is not None:
        left_pct = float(F.H_to_pct(br["H"][0], br["H"][1])[0])
        out["S6"] = {"body_rightmost_H": br["H"], "body_rightmost_left_pct": left_pct,
                     "claw_rightmost_spec_H": spec["S6_claw_rightmost"],
                     "margin_pct_h": float(F.H_to_pct_h(spec["S6_claw_rightmost"][0] - br["H"][0]))}
    else:
        out["S6"] = None
    if base is not None:
        bm = base_metrics or measure_base_contour(base)
        bl = bm["landmarks"]
        out["S1"]["vs_base"] = diff(lmk["crest"]["H"], bl["crest"]["H"])
        if lmk["inner_deepest"] is not None and bl.get("inner_deepest") is not None:
            out["S2"]["vs_base"] = diff(lmk["inner_deepest"]["H"], bl["inner_deepest"]["H"])
        if lmk["head_tip"] is not None and bl.get("head_tip") is not None:
            d = diff(lmk["head_tip"]["H"], bl["head_tip"]["H"])
            out["S5"] = {"model_tip_H": lmk["head_tip"]["H"], "base_tip_H": bl["head_tip"]["H"],
                         "pos_pct_h": d["dist_pct_h"], "dx_pct_h": d["dx_pct_h"], "dz_pct_h": d["dz_pct_h"],
                         "model_phi_deg": metrics["phi_deg"], "base_phi_deg": bm["phi_deg"],
                         "dir_deg": None if (metrics["phi_deg"] is None or bm["phi_deg"] is None)
                         else float(wrap_deg(metrics["phi_deg"] - bm["phi_deg"])),
                         "dir_definition": "phi (top-side chord before the tip) for BOTH contours: the judged S5 direction",
                         # 報告専用。波頂→波頭先端の直線方向を両輪郭で同じように求める。
                         "model_crest_to_tip_deg": metrics.get("crest_to_tip_deg"), "base_crest_to_tip_deg": bm.get("crest_to_tip_deg"),
                         "crest_to_tip_diff_deg": None if (metrics.get("crest_to_tip_deg") is None or bm.get("crest_to_tip_deg") is None)
                         else float(wrap_deg(metrics["crest_to_tip_deg"] - bm["crest_to_tip_deg"]))}
        else:
            out["S5"] = None
    return out
