"""Metrics on an ordered wave profile (numpy only).  All geometry in H-normalised units
(X_H, Z_H): crest of the final pose = (0, 1), still water / trough level Z_H = 0,
+X = boat side.  Angles in degrees; direction angle = atan2(dZ, dX) (0 = +X, + = up).

The profile is ordered:  left frame edge -> crest -> head tip -> underside of the head ->
inner arc -> trough (-> along the water to the right frame edge).  This is what
gw.silhouette.extract_profile returns in profile['H'], and what a base contour
(schema 'gw.base_contour.v1') gives when its three segments are concatenated, so the SAME
definitions are applied to the model and to the painting's base contour.

Definitions (details + which ones are interpretations: docs/measurement_definitions.md)
-----------------------------------------------------------------------------------------
crest          highest point: Z = max Z.  Its position ALONG the contour is made robust for flat
               tops ('robust extremum'): inside the contiguous run of samples within
               `extremum_tol_pct_h` of the maximum, the mid-points of the level-set chords at
               0.4 .. 1.0 x tol are fitted with a line in sqrt(level) and extrapolated to level
               0 (exact for a round top whose curvature differs on both sides, = the plateau
               centre for a flat top); the correction is capped at 25 % of the run width.
head tip       rule 'max_reversal' (default, `tip_rule`): on the FRONT STRETCH = crest .. first touch
               of the still water, take the pair (T before D) with the largest horizontal come-back
               X(T) - X(D) (the 'maximum drawdown' of X along the path).  T = head tip, D = inner
               deepest.  T is then the right-most point of the whole stretch crest .. D and D the
               left-most point of T .. trough, however many ripples / lobes lie in between, and
               the run along the water to the right frame edge (X only increases there) can never
               be picked.  An overhang exists when that come-back exceeds `tip_min_reversal_pct_h`
               (0.3 %); otherwise no tip.  On a single-nosed head this is exactly the legacy rule
               'first_reversal' (first local X maximum after the crest followed by a reversal of
               `tip_min_reversal_pct_h`), which is still evaluated and reported as the landmark
               'overhang_onset'.  X = that maximum, position along the contour = robust extremum.
               `head_lobes` counts the right->left reversals >= `head_lobe_reversal_pct_h` (1 %)
               between crest and deepest point (1 = single-nosed head).
inner deepest  left-most point of the path between the head tip and the trough end
               (X = that minimum, position along the contour = robust extremum; on a vertical
               wall this is the middle of the wall).
base contour   measure_base_contour keeps the json joints (crest, head tip) but ALSO runs the
               detection on the same polyline: 'segmentation_check' = distance json <-> detected
               for crest / tip / deepest; above `segmentation_check_tol_pct_h` (0.2 %) target and
               model are not segmented the same way (test_shape: run INVALID).
trough end     first sample after the crest (after the deepest point when overhanging) with
               Z <= z_still + trough_tol; if there is none, the lowest sample after the crest.
segments       back = start..crest, head = crest..tip, inner_arc = tip..trough end,
               trough_run = rest; front = crest..trough end (= head + inner_arc).
h, x_c         crest height above still water, crest X.
theta          steepest inclination of the front face.  Travel direction (crest -> trough) is
               measured clockwise from +X: 20 = gentle slope, 90 = vertical, > 90 = overhanging,
               180 = horizontal roof.  Tangent = chord over `theta_window_pct_h`.  theta =
               clip(max, 0, 180); theta_raw keeps values > 180 (roof rising towards the body).
o              max(0, X_tip - X_crest); 0 without a tip.
phi            pointing direction of the head tip: direction of the chord of the TOP-side
               contour from `phi_skip_H + phi_len_H` to `phi_skip_H` of arc length before the
               tip (= arc-length mean of the tangent over that window).  Negative = downward.
               THE direction of S5 and M4, for the model AND the base contour.
crest_to_tip   direction of the straight line crest -> head tip (report only, next to phi).
W (report)     report-only size metrics (NO thresholds): at the levels `width_levels_H` the
               horizontal section through the contour (x_back = left-most crossing of the back, or
               the left frame edge when the back is clipped there; x_inner = left-most crossing of
               the front = end of the main body where the section is overhung; x_front = right-most
               crossing of the front), widths, distances from the crest plumb line, plus o, cavity
               depth and the area between the contour [left edge .. trough end] and Z = z_still.
S4             back slopes: left end (chord over the first `s4_left_window_pct_h`), max of the
               tangent along the back, mean slope in the window before the crest.
S8             tangent change between neighbouring samples spaced S8_sample_spacing_pct
               (chord directions between consecutive samples, several phases), evaluated on
               [start, tip] and [tip, trough end] AND ACROSS THE TIP: junctions placed on the tip and
               at every phase offset within one spacing on both sides of it (their chords span the
               tip).  Since 2026-09-20 (second hardening) NOTHING is excluded by default
               (`s8_tip_exclusion_pct_h` = 0 = the spec's literal S8; it was 2 % while the target was
               expected to have a thin rim): a pointed head tip fails S8.  A value > 0 restores the
               old exclusion (junctions closer than that to the tip are not judged; fixture-only use).
               The old 'tip zone excluded' maximum is still REPORTED (`max_tip_zone_excluded_deg`,
               zone = `s8_tip_report_zone_pct_h` = 2 %), as is the turn across that zone (`tip_turn_deg`).
               REPORT ONLY next to it (blind spots of the judged number, 2026-09-20 hardening):
               `max_vertex_window_turn_deg` = net turning of the POLYLINE ITSELF (sum of the exterior
               angles of its own vertices, no chords) over every closed window of one S8 spacing that
               starts or ends on a vertex, nothing excluded; `vertex_window_turn` splits it per
               segment / tip zone / across the tip and repeats it for shorter windows; and
               `max_unexcluded_deg` now contains ONE junction placed exactly on the head tip.
S7             per segment, distance of model samples to the base-contour polyline of the same
               segment (extended by `s7_segment_margin_pct_h` into its neighbours) and the
               symmetric direction; mean / 95th percentile in % of image height; base points
               with in_S7 == false are not counted.  REPORT ONLY next to it: the SIGNED mean of the
               same distances (positive = the model contour lies OUTSIDE the target body).
trough level   `trough_level_H` = lowest Z of the profile between the inner-arc deepest point (the
               crest when there is no overhang) and the end of the profile (right frame edge) = the
               MODEL'S OWN water level in front of the wave.  `reached_still_water` = that level is
               within `trough_tol_pct_h` (0.3 % of image height) of `z_still_H`.  position_checks
               reports S3 from Z = 0 (judged, as before) AND from this level ('S3_from_model_trough').
shape (report) descriptors that do not cancel when a shape is wider AND lower: sections at 0.25 / 0.5 /
               0.75 of the contour's OWN crest height h (not at absolute Z), every length divided by
               h, o / h, cavity_depth / h, aspect ratio = full width at 0.5 h divided by h.
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
    "z_still_H": {"value": 0.0, "comment": "still-water / trough level in H units (spec section 4: Z = 0)"},
    "extremum_tol_pct_h": {"value": 0.1, "comment": "crest / tip / deepest point = mid-point of the run of samples within this distance (in % of image height) of the extreme coordinate; makes flat tops and vertical walls well defined"},
    "tip_rule": {"value": "max_reversal", "comment": "how the head tip is DETECTED (model profiles; base contour: consistency check). 'max_reversal' = on the front stretch [crest, first sample with Z <= z_still + trough_tol] take the pair (T before D) with the largest come-back X(T) - X(D); T = head tip = right-most point of the whole overhanging head (crest .. deepest point), D = inner-arc deepest point. Ripples and lobes of any size between crest and D cannot truncate the head, and the run along the water to the right frame edge cannot be picked (X never comes back there). 'first_reversal' = legacy rule (first local X maximum after the crest that is followed by a reversal of tip_min_reversal_pct_h): identical on single-nosed heads, stops at the first lobe on a lobed head (was 16 % of image height away from the json tip on the finger-scale base contour). The legacy point is always reported as landmark 'overhang_onset'."},
    "tip_min_reversal_pct_h": {"value": 0.3, "comment": "an overhang (head tip, inner arc) exists when the largest come-back of X on the front stretch exceeds this; smaller come-backs count as a non-overhanging profile (o = 0). Unchanged from the legacy rule, so the overhang ONSET frame of a motion is the same as before."},
    "head_lobe_reversal_pct_h": {"value": 1.0, "comment": "DIAGNOSTIC only (never moves the tip): right->left reversals of X of at least this size between the crest and the deepest point are counted as head lobes (head_lobes.n_lobes). 1 = single-nosed head, where 'max_reversal' and 'first_reversal' give the same tip; > 1 = lobed head (finger-scale contour)."},
    "segmentation_check_tol_pct_h": {"value": 0.2, "comment": "measure_base_contour: largest allowed distance between the landmarks that follow from the json joints (crest, head tip, deepest point) and the landmarks DETECTED on the same polyline; above it the target and the model are not segmented in the same way and test_shape marks the run INVALID (orchestrator task, 2026-09-20)"},
    "width_levels_H": {"value": [0.25, 0.5, 0.75], "comment": "REPORT ONLY (no threshold, pending user decision): heights Z (H units, absolute: the same painting rows for target and model) at which the horizontal section widths are reported"},
    "trough_tol_pct_h": {"value": 0.3, "comment": "the inner arc / front face ends where Z first gets within this distance of the still-water level"},
    "theta_window_pct_h": {"value": 2.0, "comment": "chord length used as tangent for theta (front-face inclination)"},
    "theta_step_pct_h": {"value": 0.25, "comment": "arc-length step at which theta is evaluated"},
    "phi_skip_H": {"value": 0.02, "comment": "arc length before the tip that is skipped for phi (the rounded rim cap; rim radius <= 1.5 % H by spec section 7)"},
    "phi_len_H": {"value": 0.06, "comment": "length of the top-side window used for phi ('the last few % H before the tip')"},
    "phi_min_len_H": {"value": 0.02, "comment": "phi is not reported when the head is too short for a window of at least this length"},
    "s4_left_window_pct_h": {"value": 5.0, "comment": "S4 'near the left end': chord over this arc length from the left frame edge"},
    "s4_tangent_window_pct_h": {"value": 2.0, "comment": "chord length used as tangent for the slope curve of the back"},
    "s4_before_crest_window_pct_h": {"value": [3.0, 8.0], "comment": "S4 'before the crest': chord of the back between these arc-length distances before the crest"},
    "s4_monotone_tol_deg": {"value": 2.0, "comment": "tolerance for 'slope decreases gradually towards the crest'"},
    "s4_crest_zone_pct_h": {"value": 6.0, "comment": "'top is round, no corner': S8 turn angles within this arc-length distance of the crest"},
    "s8_n_phases": {"value": 4, "comment": "S8 is evaluated for this many sample phases (offsets of spacing / n) so a kink cannot hide between samples"},
    "s8_tip_exclusion_pct_h": {"value": 0.0, "comment": "0 = NOTHING is excluded: S8 is judged in the spec's literal form, also ACROSS the head tip (junctions on the tip and at every phase offset within one spacing of it), so a pointed tip fails. WAS 2.0 until 2026-09-20 (orchestrator interpretation made when the target was expected to have a thin rim: 'a rim thinner than 3 % H turns ~180 deg within ~3 % of image height'); the official large-form target turns only about 10 deg per sample across its tip and the spec's S8 text has no exemption. A value > 0 restores the old behaviour (junctions closer than this arc length to the tip are not judged) - used ONLY by the thin-rimmed synthetic test fixture, as an explicit per-case override that is reported as a non-default parameter."},
    "s8_tip_report_zone_pct_h": {"value": 2.0, "comment": "REPORT ONLY: half width (arc length) of the zone around the head tip that the report-only numbers refer to when s8_tip_exclusion_pct_h = 0: max_tip_zone_excluded_deg (= the judged S8 of the definition used until 2026-09-20), tip_turn_deg (turn across the zone) and the 'outside / tip zone' split of the vertex-window turning. When s8_tip_exclusion_pct_h > 0 that value is the zone."},
    "s8_limit_deg": {"value": 15.0, "comment": "copy of thresholds.json S8.max_tangent_diff_deg, only used for the boolean S4 'no corner' flag"},
    "s7_sample_spacing_pct_h": {"value": 0.25, "comment": "spacing of the samples whose distance is measured for S7 (denser than the S8 spacing)"},
    "s7_segment_margin_pct_h": {"value": 3.0, "comment": "a segment is compared with the same segment of the other contour extended by this arc length into its neighbours, so a slightly different crest / tip split does not create fake deviation"},
    "shape_levels_frac_h": {"value": [0.25, 0.5, 0.75], "comment": "REPORT ONLY (no threshold): fractions of the contour's OWN crest height h at which the sections of the shape descriptors are taken (metrics['shape']); relative levels do not cancel when a shape is wider AND lower, absolute levels (width_levels_H) do"},
    "s8_vertex_short_windows_pct_h": {"value": [0.5, 0.25], "comment": "REPORT ONLY: additional, SHORTER windows (% of image height) for the vertex-window turning of S8. On a smooth curve the turning shrinks with the window; a kink keeps its angle, also when it goes against the local curvature (20 deg against 9 deg / 1 % reads 11 deg over 1 % but 18 deg over 0.25 %)"},
}

S8_SPACING_DEFAULT_PCT_H = 1.0
"""S8 sample spacing when params.json has no 'S8_sample_spacing_pct' entry (spec section 5 S8 / section 10
assumption 4: initial value 1 % of image height)."""

_PARAMS_META_KEYS = ("comment", "provenance", "unit", "_doc", "_comment")     # allowed next to the values in params.json['measure_params']
_DERIVED_KEYS = ("s8_spacing_pct_h", "non_default_params")                    # part of the flat dict, not of DEFAULT_PARAMS


def _param_entry(name):
    """Value of a params.json entry, or None when THE ENTRY IS ABSENT (KeyError).  Everything else - params.json
    missing, malformed json, unreadable file - raises: a broken parameter file must never be measured around."""
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
    """Flat {name: value} of DEFAULT_PARAMS, overridden by params.json['measure_params'] (if the
    project adds such an entry) and then by `overrides`.  S8 spacing comes from params.json
    ('S8_sample_spacing_pct'; S8_SPACING_DEFAULT_PCT_H when that entry is absent).

    Only the case 'the entry does not exist' is caught.  A missing or MALFORMED params.json, a
    'measure_params' entry that is not a dict, a non-numeric S8 spacing and an UNKNOWN parameter
    name (a typo would otherwise silently measure with the default) all raise.

    The result also carries 'non_default_params': {name: {'value', 'default', 'source'}} for every
    measure parameter whose value differs from DEFAULT_PARAMS (S8 spacing: from
    S8_SPACING_DEFAULT_PCT_H); source = 'params.json' | 'override'.  Empty dict = everything is
    measured with the documented defaults.  Tests should flag a non-empty dict."""
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
                continue                                  # a flat dict from an earlier get_params() is a valid override
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
    """{name: {'value', 'default', 'source'}} of every measure parameter that differs from DEFAULT_PARAMS
    (see get_params).  `params`: overrides or a flat dict from get_params()."""
    return get_params(params)["non_default_params"]


def _frame_h():
    # no fallback: a broken params.json must raise here too (it used to be replaced silently by 100 / 66)
    return gw_frame.get_frame().frame_h


def pct_h_to_H(d_pct):
    """length in % of image height -> H units."""
    return np.asarray(d_pct, dtype=np.float64) / 100.0 * _frame_h()


def H_to_pct_h(d_H):
    """length in H units -> % of image height."""
    return np.asarray(d_H, dtype=np.float64) / _frame_h() * 100.0


def wrap_deg(a):
    """wrap to (-180, 180]."""
    a = (np.asarray(a, dtype=np.float64) + 180.0) % 360.0 - 180.0
    return np.where(a == -180.0, 180.0, a)


# ====================================================================== Curve
class Curve:
    """Polyline with arc-length parameter.  pts (N, 2); consecutive duplicates are dropped."""

    def __init__(self, pts):
        p = np.asarray(pts, dtype=np.float64)
        if p.ndim != 2 or p.shape[1] != 2 or p.shape[0] < 2:
            raise ValueError("a curve needs at least 2 points of shape (N, 2)")
        if not np.isfinite(p).all():
            raise ValueError("curve contains non-finite values")
        seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
        keep = np.concatenate([[True], seg > 0])
        self.index_map = np.nonzero(keep)[0]          # index into the original array
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
        """direction of the chord from s - window/2 to s + window/2, both clipped to [lo, hi]."""
        hi = self.length if hi is None else hi
        s = np.asarray(s, dtype=np.float64)
        return self.chord_deg(np.clip(s - 0.5 * window, lo, hi), np.clip(s + 0.5 * window, lo, hi))

    def index_at(self, s):
        return int(np.clip(np.searchsorted(self.s, s), 0, len(self.s) - 1))

    def sub(self, s0, s1, spacing):
        """points sampled every `spacing` on [s0, s1] (both ends included)."""
        s0, s1 = float(max(0.0, s0)), float(min(self.length, s1))
        if s1 <= s0:
            return self.at(np.array([s0]))
        n = max(2, int(math.ceil((s1 - s0) / spacing)) + 1)
        return self.at(np.linspace(s0, s1, n))

    def slice_pts(self, s0, s1):
        """original vertices inside [s0, s1] plus exact end points."""
        s0, s1 = float(max(0.0, s0)), float(min(self.length, s1))
        inner = (self.s > s0) & (self.s < s1)
        return np.concatenate([self.at(np.array([s0])), self.pts[inner], self.at(np.array([s1]))], axis=0)


def _run_mid(values, s, i_ext, tol, sign, lo, hi):
    """Contiguous run around index i_ext (within [lo, hi]) where sign*values >= sign*values[i_ext] - tol.
    -> (s_mid, i_a, i_b)"""
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
    # Level-set bisectors: for several levels tau below the extreme value, take the mid-point
    # m(tau) of the chord between the two crossings next to the extremum.  A flat plateau or a
    # symmetric top gives a constant m; for an extremum whose curvature differs on both sides
    # m(tau) = s0 + c * sqrt(tau), so a straight-line fit in sqrt(tau) extrapolated to tau = 0
    # returns the true extreme point s0.  The correction is capped at 25 % of the run width so
    # that noise on a plateau cannot move the point far from the plateau centre.
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
    # run clipped by the end of the search range: weighted arc-length centroid instead
    ss = s[a:b + 1]
    ds = np.gradient(ss)
    wgt = np.maximum(v[a:b + 1] - thr, 0.0) ** 2 * ds
    if wgt.sum() <= 0:
        return 0.5 * (s[a] + s[b]), a, b
    return float((wgt * ss).sum() / wgt.sum()), a, b


# ====================================================================== head-tip detection
def _front_stretch_end(z, i_c, z_lim):
    """Index where the front stretch ends: first sample at / after the crest with Z <= z_lim (first touch of
    the still water); without one the lowest sample after the crest; never the crest itself."""
    below = np.nonzero(z[i_c:] <= z_lim)[0]
    i_f = int(i_c + below[0]) if below.size else int(i_c + np.argmin(z[i_c:]))
    return i_f if i_f > i_c else len(z) - 1


def _tip_first_reversal(x, i_c, rev):
    """LEGACY rule: first local maximum of X after the crest that is followed by a come-back > rev.
    -> index or None."""
    xm, im = x[i_c], i_c
    for i in range(i_c + 1, len(x)):
        if x[i] > xm:
            xm, im = x[i], i
        elif x[i] < xm - rev:
            return im if im > i_c else None
    return None


def _tip_max_reversal(x, i_c, i_f, rev):
    """Rule 'max_reversal': the pair (T before D) on [i_c, i_f] with the largest come-back x[T] - x[D]
    (maximum drawdown of X).  -> (i_T, i_D, come-back) or (None, None, come-back) when it is <= rev.
    By construction T is the right-most sample of [i_c, D] and D the left-most sample of [T, i_f]."""
    xf = x[i_c:i_f + 1]
    dd = np.maximum.accumulate(xf) - xf
    j = int(np.argmax(dd))
    if not dd[j] > rev:
        return None, None, float(dd[j])
    i_t = i_c + int(np.argmax(xf[:j + 1]))
    if i_t <= i_c:                                     # the crest itself is the right-most point: no head
        return None, None, float(dd[j])
    return i_t, i_c + j, float(dd[j])


def count_x_reversals(x, rev):
    """Number of right->left reversals of X of at least `rev` along the samples x (hysteresis count).
    A single-nosed head between crest and deepest point has exactly 1."""
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


# ====================================================================== main measurement
def measure_profile(pts_H, params=None, crest_index=None, tip_index=None):
    """All single-frame quantities of an ordered profile (H units).

    pts_H : (N, 2) ordered profile (see module doc).
    crest_index / tip_index : optional explicit indices into pts_H (used for a base contour
        whose segmentation is given); otherwise they are detected (head tip: params['tip_rule']).
    -> dict (json-ready apart from numpy floats being python floats):
       ok, notes[], overhanging, tip_source ('detected:<rule>' | 'given'),
       landmarks {crest, crest_argmax, crest_plateau, head_tip, inner_deepest, trough_end, theta_point, body_rightmost,
                  overhang_onset (legacy first-reversal tip, None without overhang)},
           each {'H': [X, Z], 's': arc length, 'index': nearest sample index}
       segments {back, head, inner_arc, trough_run, front}: [i0, i1] sample index ranges (inclusive) or None
       h, x_c, theta, theta_raw, o, cavity_depth, phi {deg, window_s, p0, p1} | None, crest_to_tip_deg | None
       head_lobes {n_lobes, n_reversals_min, onset_to_tip_pct_h, max_comeback_pct_h, ...}
       S4 {...}, S8 {...}, W {...} (report-only widths / area, see width_metrics), length_H,
       shape {...} (report-only descriptors relative to the own crest height, see shape_descriptors),
       trough_level_H (lowest Z between the deepest point - crest without overhang - and the end of the profile; landmark
       'trough_lowest'), reached_still_water (bool: trough_level_H <= z_still + trough_tol_pct_h), trough_level_above_still_pct_h,
       h_from_model_trough (crest Z - trough_level_H), trough_run_median_H (the pre-hardening 'trough_level_H'),
       non_default_params {name: {value, default, source}} (empty = every measure parameter has its documented default)
    """
    P = get_params(params)
    C = Curve(pts_H)
    x, z, s = C.pts[:, 0], C.pts[:, 1], C.s
    n = len(s)
    tol = float(pct_h_to_H(P["extremum_tol_pct_h"]))
    z_still = float(P["z_still_H"])
    notes = []

    def lm(point, s_val):
        return {"H": [float(point[0]), float(point[1])], "s": float(s_val), "index": int(C.index_map[C.index_at(s_val)])}

    # ---- crest
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

    # ---- head tip (module doc: 'head tip'; DEFAULT_PARAMS['tip_rule'])
    rev = float(pct_h_to_H(P["tip_min_reversal_pct_h"]))
    ttol = float(pct_h_to_H(P["trough_tol_pct_h"]))
    rule = str(P.get("tip_rule", "max_reversal"))
    if rule not in ("max_reversal", "first_reversal"):
        raise ValueError("unknown tip_rule %r (known: 'max_reversal', 'first_reversal')" % rule)
    i_front = _front_stretch_end(z, i_c, z_still + ttol)
    i_onset = _tip_first_reversal(x, i_c, rev)                  # legacy tip = where the overhang is first seen
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

    # ---- trough end / deepest point
    i_d = None
    if overhanging:
        s_t, ta, tb = _run_mid(x, s, i_t, tol, +1.0, i_c, n - 1) if tip_index is None else (s[i_t], i_t, i_t)
        tip_pt = C.at(s_t)
        if tip_index is None:
            tip_pt[0] = x[i_t]
        # provisional trough end after the tip
        below = np.nonzero(z[i_t:] <= z_still + ttol)[0]
        i_e = int(i_t + below[0]) if below.size else int(i_t + np.argmin(z[i_t:]))
        if i_e <= i_t:
            i_e = n - 1
        i_d = int(i_t + np.argmin(x[i_t:i_e + 1]))
        s_d, da, db = _run_mid(x, s, i_d, tol, -1.0, i_t, i_e)
        deep_pt = C.at(s_d)
        deep_pt[0] = x[i_d]
        # trough end must come after the deepest point
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

    # ---- the model's OWN water level in front of the wave: lowest Z between the inner-arc deepest point (the crest
    # when there is no overhang) and the end of the profile (= right frame edge for a complete silhouette profile).
    # A sea that stands higher than Z = z_still in front of the wave (raised floor) shows up HERE; h / S3 measured
    # from z_still cannot see it.  (Before 2026-09-20 this key was the median of the water run, None when the
    # front never came within trough_tol of z_still; that number is kept as 'trough_run_median_H'.)
    i_from = i_d if overhanging else i_c
    i_low = int(i_from + np.argmin(z[i_from:]))
    trough_level = float(z[i_low])
    reached_still_water = bool(trough_level <= z_still + ttol)
    landmarks["trough_lowest"] = lm(C.pts[i_low], s[i_low])
    trough_run_median = float(np.median(z[i_e:])) if i_e < n - 1 and reached_trough else (float(z[i_e]) if reached_trough else None)

    # ---- theta
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

    # ---- o, cavity depth, body right-most
    if overhanging:
        o = float(max(0.0, landmarks["head_tip"]["H"][0] - landmarks["crest"]["H"][0]))
        cavity = float(landmarks["head_tip"]["H"][0] - landmarks["inner_deepest"]["H"][0])
        i_br = int(i_c + np.argmax(x[i_c:i_d + 1]))
        landmarks["body_rightmost"] = lm(C.pts[i_br], s[i_br])
    else:
        o, cavity = 0.0, 0.0
        landmarks["body_rightmost"] = None

    # ---- overhang onset (legacy tip), lobes of the head, crest -> tip direction (all report only)
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

    # ---- S4 back slopes
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

    # ---- report-only widths / area (absolute levels) and shape descriptors (levels relative to the own crest height)
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
    """Landmarks DETECTED on an ordered polyline with the library's own rules (crest = robust Z maximum,
    head tip / deepest point = params['tip_rule'], trough end).  For contour builders: a base contour whose
    json joints are put on these points is segmented exactly like every model profile, so that
    measure_base_contour(...)['segmentation_check'] is consistent by construction.
    -> {overhanging, crest, head_tip, inner_deepest, trough_end, overhang_onset (each {'H', 's', 'index'} | None),
        head_lobes, tip_rule}"""
    m = measure_profile(pts_H, params)
    out = {k: m["landmarks"].get(k) for k in ("crest", "head_tip", "inner_deepest", "trough_end", "overhang_onset")}
    out.update({"overhanging": m["overhanging"], "head_lobes": m["head_lobes"], "tip_rule": m["params"]["tip_rule"]})
    return out


# ====================================================================== report-only widths / area
WIDTH_LABEL = "report only - pending user decision"


def _level_tag(level):
    return "z%02d" % int(round(100.0 * float(level)))


def _level_crossings(x, z, s, level, k0, k1):
    """Crossings of the polyline samples k0 .. k1 (inclusive) with the horizontal line Z = level, in path order.
    -> (X (m,), s (m,), going_down (m,) bool)"""
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
    """Horizontal section of a measured profile at Z = level (module doc 'W'): one record."""
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
    """Report-only shape descriptors of one measured profile (see shape_descriptors)."""
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
    """REPORT-ONLY shape descriptors that do NOT cancel when a shape is wider AND lower (no thresholds).

    The W sections are taken at ABSOLUTE heights (the same painting rows for model and target): on a model that is 5 % wider
    and 1.9 % lower the row Z = 0.75 H cuts the body higher up, and the width there reads -5 % instead of +5 %
    (results/step1_prepare/verify_tests, attack wide_low:5:1.9).  Here every contour is cut at fractions of ITS OWN crest
    height and every length is divided by that height, so a pure 'k times wider, m times lower' reads k / m in every entry.
    -> {'h_H', 'sections': {'h25' | 'h50' | 'h75': W-section record + frac_of_h + width_full_over_h, width_body_over_h,
        front_from_crest_over_h, inner_from_crest_over_h, back_from_crest_over_h, cavity_gap_over_h},
        'o_over_h', 'cavity_depth_over_h', 'aspect_ratio' (= width_full at 0.5 h / h), 'aspect_ratio_back_clipped',
        'aspect_ratio_h75', 'aspect_ratio_h75_back_clipped'}.   The same dict is part of every measure_profile result (key 'shape')."""
    m = metrics or measure_profile(pts_H, params)
    return m["shape"]


def compare_shape_descriptors(model_shape, target_shape):
    """Rows 'model vs target' of the shape descriptors (each contour relative to ITS OWN h).  diff = model - target,
    diff_pct_of_target in % of |target|.  comparable = False when the two sections are not of the same kind (back clipped at
    the frame edge on one side only / overhung on one side only) or when the back is clipped on both sides for a width that
    starts at the back (the frame edge does not scale with the body)."""
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
    """Report-only size metrics of one measured profile (see width_metrics)."""
    x, z, s = C.pts[:, 0], C.pts[:, 1], C.s
    z_still = float(P["z_still_H"])
    sections = {}
    for level in [float(v) for v in P["width_levels_H"]]:
        sections[_level_tag(level)] = _section_record(C, level, i_c, s_t, i_e, x_c)
    # area between the contour [left end .. trough end] and the still-water level (shoelace; the cavity is outside)
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
    """REPORT-ONLY size metrics of an ordered profile (no thresholds; pending user decision).

    -> {'sections': {'z25' | 'z50' | 'z75': {x_back_H, back_clipped_at_frame_edge, x_inner_H, x_front_H, overhung,
        width_full_H (= x_front - x_back), width_body_H (= x_inner - x_back, only where the section is overhung),
        cavity_gap_H, front_from_crest_H, inner_from_crest_H, back_from_crest_H, ...}},
        'o_H', 'cavity_depth_H', 'area_above_still_water_H2', ...}
    The same dict is part of every measure_profile result (key 'W')."""
    m = metrics or measure_profile(pts_H, params)
    return m["W"]


_W_SECTION_KEYS = ("width_full_H", "width_body_H", "front_from_crest_H", "inner_from_crest_H", "back_from_crest_H", "cavity_gap_H")


def compare_width_metrics(model_W, target_W):
    """Rows 'model vs target' of the report-only size metrics.  diff = model - target; diff_pct_of_target in % of
    |target| (None when the target is ~0); diff_pct_h = the same difference in % of image height (lengths only).
    comparable = False when the two sections are not of the same kind (back clipped / overhung differ)."""
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
    """Net turning of the POLYLINE ITSELF over closed arc-length windows of length `window` inside [lo, hi].

    turning of a window [a, b] = sum of the signed exterior angles (deg, + = counter-clockwise) of the polyline's OWN
    vertices with a <= s <= b: no chords, no sampling phase, so a kink on a vertex is read with its full angle wherever
    it sits, and a turn of more than 180 deg (a thin rim) is not wrapped.  Windows: one that STARTS and one that ENDS on
    every interior vertex (clipped to [lo, hi]); the turning of a sliding closed window changes only at those positions,
    so their maximum is the maximum over all positions.  If hi - lo < window there is one window [lo, hi].
    -> (a (m,), b (m,), turn_deg (m,))"""
    if not isinstance(C, Curve):
        C = Curve(C)
    lo, hi, w = float(max(0.0, lo)), float(min(C.length, hi)), float(window)
    if C.pts.shape[0] < 3 or hi <= lo or w <= 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    d = np.degrees(np.arctan2(np.diff(C.pts[:, 1]), np.diff(C.pts[:, 0])))
    ext = wrap_deg(np.diff(d))                                   # exterior angle at the interior vertices 1 .. n-2
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
    """Half width (% of image height, arc length) of the zone around the head tip that the REPORT-ONLY S8 numbers refer to:
    the exclusion zone when one is set (s8_tip_exclusion_pct_h > 0), otherwise s8_tip_report_zone_pct_h (2 % = the zone that
    was excluded from the verdict until 2026-09-20)."""
    excl = float(P["s8_tip_exclusion_pct_h"])
    return excl if excl > 0.0 else float(P.get("s8_tip_report_zone_pct_h", 2.0))


def _vertex_window_report(C, s_crest, s_tip, s_end, P):
    """REPORT-ONLY companion of the judged S8 (see vertex_window_turns).  Windows of one S8 spacing on [0, s_end]:
    max_deg (nothing excluded), per_segment (windows whose centre is OUTSIDE the tip exclusion zone, by centre),
    max_outside_tip_exclusion_deg (the number to compare with the judged S8), tip_zone_deg (centre inside the exclusion
    zone), across_tip_deg (windows that contain the head tip), max_at; 'short_windows': the same maxima for the shorter
    windows of `s8_vertex_short_windows_pct_h`."""
    excl = float(pct_h_to_H(_s8_tip_zone_pct_h(P)))           # report zone (= the exclusion zone when one is set)

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
    """Tangent change between neighbouring samples (spec S8).

    C : Curve or (N, 2) points.  s_tip None = non-overhanging.  Stretches: [0, s_tip] and
    [s_tip, s_end] (or [0, s_end]).  For every phase the stretch is sampled every `spacing`;
    tangent_j = direction of the chord sample j -> j+1; junction value = |tangent_j - tangent_j-1|
    located at sample j.  ACROSS THE TIP (2026-09-20, second hardening): additional junctions at s_tip + spacing * k /
    n_phases, k = -(n_phases - 1) .. (n_phases - 1) (k = 0 = exactly on the tip); their two chords span the tip, so the
    junction density across the tip equals that inside the stretches.  `s8_tip_exclusion_pct_h` = 0 (default): EVERY
    junction is judged (the spec's literal S8; a pointed tip fails).  > 0: junctions closer than that to the tip are not
    judged (the pre-2026-09-20 definition with 2 %; then none of the across-tip junctions is judged).
    -> dict: max_tangent_diff_deg (judged), max_at {H, s, segment, across_tip}, per_segment {back, head,
       inner_arc | front}, tip_turn_deg, max_unexcluded_deg, spacing_pct_h, n_junctions, n_judged,
       across_tip {n_junctions, n_judged, max_deg, max_at_s}
       REPORT ONLY:
       max_tip_zone_excluded_deg        max |turn| of the within-stretch junctions farther than the report zone
                                        (tip_report_zone_pct_h) from the tip = the JUDGED S8 of the definition used
                                        until 2026-09-20 (equals max_tangent_diff_deg when that exclusion is set)
       tip_junction_deg                 signed turn of the ONE junction placed exactly on the head tip
       max_unexcluded_deg               max |turn| over the within-stretch junctions and that tip junction
       max_unexcluded_without_tip_junction_deg   the value this key had before the tip junction was added
       tip_turn_deg                     clockwise turn across the report zone around the tip
       max_vertex_window_turn_deg       max |net turning of the polyline itself| over closed windows of one spacing
                                        that start or end on a vertex; nothing excluded (see vertex_window_turns)
       vertex_window_turn               {window_pct_h, n_windows, max_deg, max_at, per_segment {back, head, inner_arc | front}
                                        (window centre outside the tip exclusion zone), max_outside_tip_exclusion_deg,
                                        tip_zone_deg, across_tip_deg, short_windows [same keys for shorter windows]}
    """
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

    # ONE extra junction placed exactly on the head tip (chord tip - spacing -> tip against chord tip -> tip + spacing).
    # The two stretches above are sampled separately, so without it NO junction ever looks across the tip and a pointed
    # tip (a 40 deg corner read 10.3 deg 'unexcluded') is invisible even in the unexcluded maximum.  Report only: it is
    # not part of _junction_s / the judged value.
    tip_junction = None
    if s_tip is not None:
        a0, a1 = max(0.0, s_tip - sp), min(float(s_end), s_tip + sp)
        if s_tip - a0 > 1e-12 and a1 - s_tip > 1e-12:
            tip_junction = float(wrap_deg(C.chord_deg(s_tip, a1) - C.chord_deg(a0, s_tip)))
    unexcl_old = float(np.max(np.abs(jd))) if jd.size else None
    unexcl = unexcl_old if tip_junction is None else max(abs(tip_junction), unexcl_old or 0.0)
    # junctions ACROSS the tip at every phase offset (k = 0 is the tip junction above, with its own end clamping); both
    # chords must lie inside [0, s_end].  Kept apart from _junction_s / _junction_diff: S4 'top is round' reads those.
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
        out["tip_turn_deg"] = float((d_before - d_after) % 360.0)      # clockwise turn across the report zone around the tip
    return out


# ====================================================================== distances / S7
def point_polyline_distance(points, poly, chunk=512):
    """Distance of each point to a polyline.  -> (dist (n,), index of the nearest polyline edge (n,))"""
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
    """point_polyline_distance plus the SIDE of the polyline each point lies on.

    Every ordered contour of this project is walked with the wave BODY ON THE RIGHT-HAND SIDE (left frame edge -> crest ->
    tip -> underside -> inner arc -> trough; Z up), so the LEFT of the travel direction is the air.
    -> (dist (n,), index of the nearest edge (n,), signed (n,)):  signed = +dist when the point is on the left = OUTSIDE the
       body of `poly`, -dist when it is inside, 0 on the polyline.
    The side is the sign of cross(tangent, point - nearest point); where the nearest point is a polyline VERTEX the tangent
    is the mean of the unit tangents of the two edges that meet there."""
    Pp = np.asarray(points, dtype=np.float64)
    Q = np.asarray(poly, dtype=np.float64)
    dist, idx = point_polyline_distance(Pp, Q, chunk)
    if Q.shape[0] < 2 or Pp.shape[0] == 0:
        return dist, idx, np.zeros(Pp.shape[0])
    AB = Q[1:] - Q[:-1]
    L = np.hypot(AB[:, 0], AB[:, 1])
    U = AB / np.where(L > 0, L, 1.0)[:, None]                     # unit tangents of the edges
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
    """Read a 'gw.base_contour.v1' json (default: target/base_contour.json)."""
    path = path or paths.BASE_CONTOUR_JSON
    with open(path, "r", encoding="utf-8") as fh:
        bc = json.load(fh)
    if bc.get("schema") != "gw.base_contour.v1":
        raise ValueError("unexpected base contour schema %r in %s" % (bc.get("schema"), path))
    return bc


def base_contour_polyline(bc):
    """Concatenate the three segments (shared end points are not duplicated).
    -> dict: pts_H (N, 2), seg_id (N,) 0 back / 1 head / 2 inner_arc, in_S7 (N,) bool,
       crest_index, tip_index, names"""
    names = ["back", "head", "inner_arc"]
    by = {sg["name"]: sg for sg in bc["segments"]}
    pts, sid, flag, bounds = [], [], [], []
    for k, nm in enumerate(names):
        sg = by[nm]
        p = np.asarray(sg["points_H"], dtype=np.float64)
        f = np.asarray(sg.get("in_S7", [True] * len(p)), dtype=bool)
        n_prev = sum(len(q) for q in pts)
        if pts and np.allclose(pts[-1][-1], p[0], atol=1e-9):
            p, f = p[1:], f[1:]                  # shared joint: keep the copy of the previous segment
            bounds.append(n_prev - 1)
        else:
            bounds.append(n_prev)                # first point of this segment is the joint
        pts.append(p)
        sid.append(np.full(len(p), k))
        flag.append(f)
    P = np.concatenate(pts)
    return {"pts_H": P, "seg_id": np.concatenate(sid), "in_S7": np.concatenate(flag),
            "crest_index": int(bounds[1]), "tip_index": int(bounds[2]), "names": names}


def segmentation_check(poly, json_metrics, params=None, bc=None):
    """Are the json joints of a base contour where the library's DETECTION puts crest / head tip / deepest point
    on the very same polyline?  (The model profile is always segmented by detection; S5 / S7 compare like with
    like only when both agree.)

    poly : base_contour_polyline(bc);  json_metrics : measure_profile(..., crest_index, tip_index) of it.
    -> {tol_pct_h, consistent (bool), max_dist_pct_h, worst, items {crest | head_tip | inner_deepest:
        {json_H, detected_H, dist_pct_h, ds_pct_h}}, detected_overhanging, detected_head_lobes, detected_onset_H,
        json_landmarks_block {key: dist_pct_h}  (information: the json's own 'landmarks' entries vs the detection)}"""
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
    """measure_profile on a base contour.  With use_json_segmentation the crest / head tip are
    the segment joints of the json (orchestrator convention); otherwise they are re-detected.
    check_detection (json segmentation only): the detection is ALSO run on the same polyline and the result
    gets the key 'segmentation_check' (see segmentation_check); test_shape marks a run INVALID when it is
    not consistent."""
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
    """Signed normal deviation, already oriented so that + = the MODEL is outside the TARGET body.  % of image height."""
    d = H_to_pct_h(np.asarray(signed_H, dtype=np.float64))
    if d.size == 0:
        return {"signed_mean_pct_h": None, "signed_median_pct_h": None, "signed_p05_pct_h": None, "signed_p95_pct_h": None,
                "frac_model_outside": None}
    return {"signed_mean_pct_h": float(d.mean()), "signed_median_pct_h": float(np.median(d)),
            "signed_p05_pct_h": float(np.percentile(d, 5)), "signed_p95_pct_h": float(np.percentile(d, 95)),
            "frac_model_outside": float((d > 0).mean())}


def s7_deviation(model_pts_H, base, model_metrics=None, params=None):
    """Contour-to-contour deviation per segment (spec S7).

    model_pts_H   : ordered model profile (H units).
    base          : base contour dict (load_base_contour) or the result of base_contour_polyline.
    model_metrics : measure_profile(model_pts_H) if already computed.
    -> {segment: {model_to_base {n, mean, p95, max}, base_to_model {...}, mean_dev_pct_h, p95_dev_pct_h,
                  worst_point {H, dev_pct_h, direction}}, ..., 'n_base_excluded': ..}
       mean_dev_pct_h / p95_dev_pct_h = the worse of the two directions (judged values).
       REPORT ONLY, same samples: signed_mean_dev_pct_h (= model_to_base['signed_mean_pct_h'], the base_to_model value when
       the model has no counted sample) and, in both direction dicts, signed_mean / median / p05 / p95 _pct_h and
       frac_model_outside.  SIGN: positive = the model contour lies OUTSIDE the target body (in the air / in the cavity: the
       model is fatter there), negative = inside (thinner); see signed_point_polyline_distance.  A wider AND lower body
       moves the back out and down at the same time: the unsigned numbers stay small, the signed one tells which way.
    """
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
    # base segment arc-length ranges
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
        # model -> base
        mp = Cm.sub(m_rng[0], m_rng[1], sp)
        lo, hi = max(0.0, b_rng[nm][0] - margin), min(Cb.length, b_rng[nm][1] + margin)
        ia, ib = Cb.index_at(lo), Cb.index_at(hi)
        ia = max(0, ia - 1)
        target = Cb.pts[ia:ib + 1]
        d, e, sg = signed_point_polyline_distance(mp, target)
        counted = edge_ok[np.clip(ia + e, 0, len(edge_ok) - 1)]
        st_mb = _stats(d[counted])
        st_mb["n_skipped_not_in_S7"] = int((~counted).sum())
        st_mb.update(_signed_stats(sg[counted]))                 # + = model sample outside the target body
        # base -> model
        sel = (b_seg == k) & b_flag
        bp = Cb.pts[sel]
        if bp.shape[0] > 1:
            # thin the base points to about the same spacing
            keep = np.concatenate([[True], np.diff(np.floor(Cb.s[sel] / sp)) > 0])
            bp = bp[keep]
        lo_m, hi_m = max(0.0, m_rng[0] - margin), min(Cm.length, m_rng[1] + margin)
        tm = Cm.slice_pts(lo_m, hi_m)
        d2, _e2, sg2 = signed_point_polyline_distance(bp, tm) if bp.shape[0] else (np.zeros(0), None, np.zeros(0))
        st_bm = _stats(d2)
        st_bm.update(_signed_stats(-sg2))                        # target point INSIDE the model body = model outside the target
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
    """Symmetric contour displacement between two frames (for M5 / M6): nearest distance of
    samples of A to polyline B and vice versa.  z_min_H: ignore samples below this height
    (e.g. 0.01 to skip the run along the still water).  -> {max_H, p95_H, mean_H}"""
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
    """Per-frame motion quantities (spec 6.2) for a list of ordered profiles (one per frame).

    -> dict of equally long lists: h, x_c, theta, theta_raw, o, cavity_depth, phi_deg (None without
       a head), overhanging, tip_H / crest_H / deepest_H ([X, Z] or None), and the contour
       displacement to the PREVIOUS frame disp_max_H / disp_p95_H / disp_mean_H (None for the
       first frame; samples below disp_z_min_H, i.e. the run along the still water, are ignored).
       'metrics' holds the full measure_profile dict of every frame.
    """
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


# ====================================================================== position checks S1 S2 S3 S5 S6
def position_checks(metrics, base=None, base_metrics=None, frame_obj=None):
    """Position differences for S1, S2, S3, S5 and the S6 outer-boundary check.

    metrics : measure_profile(model).  base : base contour json dict (optional; needed for S5 and
    for the 'vs base contour' variants).  All differences are model minus target, in % of image
    height (horizontal ones too).  Nothing is judged here; use paths.check_threshold on the values.
    """
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
    # S3 measured the way the spec words it ('height from the TROUGH to the crest'): crest Z minus the model's own water
    # level in front of the wave (metrics['trough_level_H']).  Identical to S3 when the water in front of the wave is at
    # z_still; 3 % smaller when the sea stands 3 % higher there (raised floor), which S3 from Z = 0 cannot see.
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
                         # report only: direction of the straight line crest -> head tip, same for both contours
                         "model_crest_to_tip_deg": metrics.get("crest_to_tip_deg"), "base_crest_to_tip_deg": bm.get("crest_to_tip_deg"),
                         "crest_to_tip_diff_deg": None if (metrics.get("crest_to_tip_deg") is None or bm.get("crest_to_tip_deg") is None)
                         else float(wrap_deg(metrics["crest_to_tip_deg"] - bm["crest_to_tip_deg"]))}
        else:
            out["S5"] = None
    return out
