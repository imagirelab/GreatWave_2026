"""Shared helpers of the stand-alone great_wave tests (test_shape / test_motion / test_mesh / run_all).

What lives here
---------------
* command line: the arguments every test understands (add_common_args)
* scene set-up : open a .blend and / or run a builder script, find the wave object (setup_context)
* thresholds   : make_check() -> one json-ready record per check with pass / fail for BOTH tiers
                 ('spec' and 'user_relaxed_5pct'); limits come ONLY from tests/thresholds.json
* settings     : TEST_SETTINGS = measurement settings of the TESTS (noise floors, resolutions ...).
                 They are NOT thresholds.  Optional override: params.json entry 'test_settings' or
                 --set key=value on the command line (unknown names raise).  Every setting / measure
                 parameter that can influence a verdict is ALSO written down in tests/thresholds.json
                 block 'interpretations'; settings_audit() compares the effective values with that
                 file and any difference puts ' (NON-DEFAULT SETTINGS)' behind the verdict.
* verdicts     : PASS | FAIL | INVALID | INCOMPLETE | ERROR (+ ' (NON-OFFICIAL INPUTS)' + ' (NON-DEFAULT SETTINGS)'),
                 see summarize(); inputs_audit(): --contour / --H / --water-z / --fps against the project's own values
* crash safety : parse_args_guarded(): an argparse error renames the stale outputs of --out-dir and writes an ERROR
                 result (exit 2);  guarded_main(): stale outputs of the run directory are renamed, a RUNNING marker is
                 written, an uncaught exception - AND a SystemExit raised while the test body is still running, e.g. a
                 build script that calls sys.exit(0) / gw.bootstrap.finish(True) - becomes metrics.json with verdict
                 ERROR + exit code 2
* validity     : evaluation_state_report(): the tests measure the VIEWPORT depsgraph; a modifier of a tested object with
                 show_viewport != show_render (or levels != render_levels) makes the run INVALID
* reporting    : summary per tier, metrics.json, summary.md, log lines, WARNING lines
* mesh access  : evaluated mesh arrays (positions, topology, UV) of one frame

Builder-script protocol (--build-script)
----------------------------------------
    --build-script <file.py> [--build-func <name>] [--build-arg key=value ...]
The file is imported as a module (its `if __name__ == "__main__"` block does NOT run) and
`func(scene, **build_args)` is called on an EMPTY factory scene (or on the opened --blend).
`func` = --build-func, otherwise the first that exists of: build_for_tests, build, build_object.
It must create the wave object in `scene` and may return the object, a tuple whose first item is the
object, or None (then --object names it).  --build-arg values are json-decoded when possible.

No environment variable is read or modified; nothing is written outside the allowed roots.
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

# ------------------------------------------------------------------------------------ settings
TEST_SETTINGS = {
    "shape_res_scale": {"value": 1.0, "comment": "mask resolution factor of test_shape (1.0 = 3859 x 2594, the painting's own grid)"},
    "motion_res_scale": {"value": 0.25, "comment": "mask resolution factor of test_motion; with exact crossings the accuracy does not depend on it (docs/measurement_definitions.md section 7)"},
    "mesh_res_scale": {"value": 0.5, "comment": "mask resolution factor of the CAM_print profile that test_mesh uses to locate the visible head tip (G3)"},
    "monotonic_noise_floor_H": {"value": 1e-4, "comment": "INTERPRETATION: a frame-to-frame decrease of h / o smaller than this (H units; = 0.0066 % of image height = 1.1 mm at H = 11 m) counts as measurement noise and is judged as 0. Documented noise of the measurement: 5e-6 H (h), 1.5e-4 H (o, x_c). The raw value is always reported next to the judged one."},
    "monotonic_noise_floor_deg": {"value": 0.2, "comment": "INTERPRETATION: same for phi (documented measurement error <= 0.07 deg per frame -> <= 0.14 deg per difference)"},
    "static_disp_eps_H": {"value": 1e-6, "comment": "INTERPRETATION: a contour displacement at or below this (H units; 0.011 mm at H = 11 m) counts as 'not moving' (stop detection, M5 post-stop)"},
    "disp_z_min_H": {"value": 0.01, "comment": "contour samples below this height (the run along the still water) are ignored in the contour displacement (pm.measure_sequence default)"},
    "jump_floor_frac_of_vmax": {"value": 0.05, "comment": "INTERPRETATION (M6): the neighbour displacement in the denominator of the jump ratio is never taken smaller than this fraction of the largest per-frame displacement; otherwise every start from rest / arrival at rest would be a 'jump' (x / 0)"},
    "hold_frames": {"value": None, "comment": "INTERPRETATION (M5 'the shape does not change after the stop'): None = EVERY frame the scene has after the declared final frame (final + 1 .. scene.frame_end) is evaluated and judged. WAS 3 until 2026-09-20 (three extrapolated frames): a pose that was held 3 frames and then drifted passed. A number (--hold-frames N / --set) evaluates exactly N frames after the final frame instead and is a NON-DEFAULT setting (verdict suffix); 0 = the check is NOT_MEASURABLE."},
    "min_hold_s": {"value": 1.0, "comment": "INTERPRETATION (M5): the scene must hold the final pose for at least this many seconds after the declared final frame (30 frames at 30 fps). With a shorter hold and no movement seen in it, M5.post_stop_max_disp_H is NOT judged (-> verdict INCOMPLETE, never PASS); movement inside a short hold still fails. Builders of step 3 must provide the hold: scene.frame_end >= final frame + 1 s, final frame declared with --final-frame or scene['gw_final_frame']."},
    "m6_backlog_half_window": {"value": 2, "comment": "REPORT ONLY, INTERPRETATION (backlog definition sheet item 4: 'displacement between adjacent frames must not exceed 3 x the MEDIAN of the neighbouring frames, excluding the transition to the stop'): the median is taken over the displacements of this many frame pairs BEFORE and this many AFTER pair k (k itself excluded; fewer at the ends of the animation). 2 (not 1) because a one-frame glitch makes TWO large displacements (out and back): with one neighbour on each side the median of 2 values is their mean and the second jump would hide the first (ratio 2)."},
    "m6_backlog_exclude_window_s": {"value": None, "comment": "REPORT ONLY, INTERPRETATION of 'excluding the transition to the stop': frame pairs whose later frame lies within this many seconds before the stop frame (and everything after it) are not used for M6_backlog. None = the M5 deceleration window of thresholds.json (M5.decel_window_s = 1 s)."},
    "backlog_hold_s": {"value": 10.0, "comment": "REPORT ONLY (backlog definition sheet item 5: 'the still pose is held 10 s with contour movement <= 0.2 % of image height'): length of the hold that is evaluated after the final frame; frames beyond scene.frame_end are evaluated as Blender extrapolates the animation"},
    "backlog_hold_step_frames": {"value": 30, "comment": "the hold is sampled every n-th frame (plus its last frame); every sample is compared with the FINAL frame's contour, so slow drift is not missed by the sampling"},
    "backlog_hold_reference_pct_h": {"value": 0.2, "comment": "REPORT ONLY reference value quoted from the backlog definition sheet (docs/backlog_crosscheck.md item 3). It is NOT a threshold of this project (tests/thresholds.json has no such entry); the measured movement is reported next to it and never enters a verdict."},
    "contact_sheet_step": {"value": 15, "comment": "spec section 9 step 3: one image every 15 frames"},
    "g3_n_sections": {"value": 9, "comment": "number of cross-sections (planes Y = const) used for the rim thickness"},
    "g3_y_percentiles": {"value": [10.0, 90.0], "comment": "the sections are spread between these percentiles of the Y coordinates of the crest_rim vertices"},
    "g3_tip_match_pct_h": {"value": 1.0, "comment": "INTERPRETATION: a section is JUDGED when its own head tip lies within this distance (% of image height) of the head tip seen by CAM_print, i.e. it forms the visible rim; tapered end sections are reported only"},
    "g3_normal_window_pct_H": {"value": 0.4, "comment": "half length (in % of H, along the section) of the symmetric chord that gives the tangent / inward normal at the rim point"},
    "g3_exclude_pct_H": {"value": 0.5, "comment": "curve points closer than this (arc length, % of H) to the rim point are not used for the inscribed circle (their ratio 0/0 is ill-conditioned)"},
    "g3_probe_offsets_pct_H": {"value": [-0.2, -0.1, 0.0, 0.1, 0.2], "comment": "the inscribed-circle diameter is the median over rim points shifted by these arc lengths (% of H)"},
    "g4_eps_rel_H": {"value": 1e-6, "comment": "geometric tolerance of the triangle-triangle test as a fraction of H: vertices closer than this to the other triangle's plane count as touching, intersection segments shorter than this are ignored"},
    "g4_min_plane_angle_deg": {"value": 0.1, "comment": "triangle pairs whose planes are closer to parallel than this are classified 'coplanar / touching', not as a crossing"},
    "g5_n_frames": {"value": 5, "comment": "number of frames (evenly spread from the first to the final frame) whose vertex positions are compared bit-exactly between rebuilds"},
    "dup_vertex_eps_rel_H": {"value": 1e-6, "comment": "INTERPRETATION (validity of test_mesh): two vertices closer than this fraction of H (0.011 mm at H = 11 m) have the same position. Vertices that share a position but are NOT joined by a chain of collapsed (zero-length) mesh edges are UNWELDED DUPLICATES (a second sheet, an unwelded seam); coincident vertices of a collapsed taper row are joined by such edges and do not count."},
    "dup_max_share_pct": {"value": 0.1, "comment": "INTERPRETATION (validity of test_mesh): largest share of unwelded duplicate vertices (% of the vertices) and of duplicated triangles (% of the triangles: non-degenerate triangles whose three corner POSITIONS equal those of another triangle) on any checked frame; above it the run is INVALID. Measured 2026-09-20: clean fixture (clip and lift_clip), swept official contour: 0 / 0 on every checked frame although up to 9,003 vertices coincide in collapsed taper rows; the sceptic's duplicated sheet: 100 % / 65 - 99 %. 0.1 % = 25 of 25,251 vertices: three orders of magnitude below the attack, and a single unwelded seam along the crest line (1 / 443 = 0.23 %) is already above it."},
    "coincident_tri_pairs_max_share_pct": {"value": 0.5, "comment": "INTERPRETATION (validity of test_mesh): largest number of COINCIDENT / COPLANAR / TOUCHING triangle pairs of one G4 frame (BVH-overlapping pairs without a shared vertex that do not cross properly and are not degenerate = the pairs G4 ignores), in % of the triangle count of the mesh; above it the run is INVALID. Measured 2026-09-20: clean fixture 6 pairs of 49,504 triangles = 0.012 % on its flat first frame and 0 elsewhere, swept official contour 0; duplicated sheet 4,212 .. 6,138 pairs of 99,008 triangles = 4.3 .. 6.2 % per frame (15,048 in total). 0.5 % lies a factor 40 above the clean maximum and a factor 8 below the smallest attack frame."},
    "s7_report_max_ranges": {"value": 10, "comment": "at most this many failing stretches are listed per segment"},
    "motion_frame_step": {"value": 1, "comment": "test_motion evaluates every n-th frame (--frame-step). Anything but 1 makes M5 / M6 meaningless for acceptance, so it is treated like a changed tolerance (verdict suffix NON-DEFAULT SETTINGS)"},
    "in_s7_false_max_share_pct": {"value": 35.0, "comment": "INTERPRETATION (validity): largest share (% of the segment's arc length on the base contour / % of the model's samples of the segment) that may be excluded from S7 because the base contour is flagged in_S7 = false there. Above it the S7 verdict of that segment covers too little of the segment and the run is INVALID. Measured shares 2026-09-20: official base contour inner arc 20.8 %, back / head 0 %; synthetic fixture inner arc 27.5 %. The shares are always reported as T.<segment>.in_s7_false_share_pct / T.<segment>.model_samples_not_counted_share_pct."},
    "armpit_min_sagitta_pct_h": {"value": 0.5, "comment": "REPORT ONLY (S7 split underside / belly): the armpit = point of the inner arc between head tip and deepest point that is farthest from the straight line tip -> deepest, on the body side; when that distance is below this value (% of image height) the inner arc has no distinct armpit and the split is not reported"},
}

# TEST_SETTINGS entries that cannot change a verdict (report-only quantities, output formatting).  Every OTHER entry must
# be listed in tests/thresholds.json 'interpretations' -> 'test_settings' (checked by settings_audit on every run).
REPORT_ONLY_SETTINGS = ("m6_backlog_half_window", "m6_backlog_exclude_window_s", "backlog_hold_s", "backlog_hold_step_frames",
                        "backlog_hold_reference_pct_h", "contact_sheet_step", "s7_report_max_ranges", "armpit_min_sagitta_pct_h")
# measure parameters (gw.profile_metrics.DEFAULT_PARAMS) that only feed report-only quantities; all others must be listed
# in 'interpretations' -> 'measure_params'
REPORT_ONLY_MEASURE_PARAMS = ("head_lobe_reversal_pct_h", "width_levels_H", "shape_levels_frac_h", "s8_vertex_short_windows_pct_h",
                              "s8_tip_report_zone_pct_h")
_SETTINGS_META_KEYS = ("comment", "provenance", "unit", "_doc", "_comment")
NON_DEFAULT_SUFFIX = " (NON-DEFAULT SETTINGS)"
NON_OFFICIAL_SUFFIX = " (NON-OFFICIAL INPUTS)"       # always BEFORE NON_DEFAULT_SUFFIX: '<word> (NON-OFFICIAL INPUTS) (NON-DEFAULT SETTINGS)'
EXIT_CODE_ERROR = 2
# which of the scene-describing inputs can change a verdict of which test (inputs_audit): the contour is only read by
# test_shape, the frame rate only by test_motion (1 s windows of M5, phase lengths)
RELEVANT_INPUTS = {"shape": ("contour", "H", "water_z"), "motion": ("H", "water_z", "fps"), "mesh": ("H", "water_z"),
                   "all": ("contour", "H", "water_z", "fps")}


class BuildScriptExit(RuntimeError):
    """The build script (its import or its build function) called sys.exit() / gw.bootstrap.finish()."""


def get_settings(overrides=None, with_sources=False):
    """Flat {name: value}: TEST_SETTINGS <- params.json['test_settings'] (optional) <- overrides (--set).

    Only 'the params.json entry does not exist' is caught.  A malformed params.json, a 'test_settings' entry that is
    not an object and an UNKNOWN setting name (in params.json or in --set; a typo would otherwise silently keep the
    default, or silently do nothing) all raise.  with_sources -> (settings, {name: 'params.json test_settings' | '--set'})."""
    s = {k: (list(v["value"]) if isinstance(v["value"], list) else v["value"]) for k, v in TEST_SETTINGS.items()}
    src = {}
    try:
        extra = paths.param("test_settings")
    except KeyError:
        extra = None
    if extra is not None:
        if not isinstance(extra, dict):
            raise TypeError("params.json['test_settings'] must be an object {name: value | {value: ..}}, got %s" % type(extra).__name__)
        for k, v in extra.items():
            if k in _SETTINGS_META_KEYS:
                continue
            if k not in TEST_SETTINGS:
                raise ValueError("params.json['test_settings'] has an unknown test setting %r (known: %s)" % (k, ", ".join(sorted(TEST_SETTINGS))))
            s[k] = v["value"] if isinstance(v, dict) and "value" in v else v
            src[k] = "params.json test_settings"
    for k, v in (overrides or {}).items():
        if k not in TEST_SETTINGS:
            raise ValueError("unknown test setting %r in --set (known: %s)" % (k, ", ".join(sorted(TEST_SETTINGS))))
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
    """Compare every tolerance that can influence a verdict with tests/thresholds.json block 'interpretations'.

    settings       : flat dict of get_settings();  sources: second return value of get_settings(with_sources=True)
    measure_params : flat dict of pm.get_params() (None = read it now)
    effective      : {setting name: (value actually used by this run, where it came from)} for settings that the command
                     line can replace directly (--res-scale, --hold-frames, --frame-step)
    -> {'non_default': [ {group, name, effective, file_value, source} ... ]   -> verdict suffix + non-zero exit code
        'unlisted'   : [ ... ]  verdict-relevant names that thresholds.json does not list (treated like non_default)
        'report_only_non_default': [ ... ]  changed settings that cannot influence a verdict (listed, no suffix)
        'ok': bool}
    Nothing here changes a threshold; the block only DOCUMENTS the values the code uses, so that a changed tolerance
    cannot go unnoticed (the sceptic's '--set jump_floor_frac_of_vmax=1.0' made a 0.3 H frame jump pass M6)."""
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
                             "source": "not listed in thresholds.json interpretations.test_settings"})
        elif not _same(v, f_set[k].get("value")):
            origin = where or sources.get(k) or ("code default of common_test.TEST_SETTINGS differs from thresholds.json" if _same(v, default) else "?")
            non_default.append({"group": "test_settings", "name": k, "effective": v, "file_value": f_set[k].get("value"), "source": origin})
    P = measure_params if measure_params is not None else pm.get_params()
    nd_lib = P.get("non_default_params") or {}
    for k in sorted(P):
        if k in ("non_default_params",):
            continue
        v = P[k]
        if k == "s8_spacing_pct_h":
            continue                      # judged by its own check S8.sample_spacing_pct_h (thresholds.json, op eq)
        src = (nd_lib.get(k) or {}).get("source")
        if k in REPORT_ONLY_MEASURE_PARAMS:
            if k in nd_lib:
                report_only.append({"group": "measure_params", "name": k, "effective": v, "default": nd_lib[k].get("default"), "source": src})
            continue
        if k not in f_mp:
            unlisted.append({"group": "measure_params", "name": k, "effective": v, "file_value": None,
                             "source": "not listed in thresholds.json interpretations.measure_params"})
        elif not _same(v, f_mp[k].get("value")):
            non_default.append({"group": "measure_params", "name": k, "effective": v, "file_value": f_mp[k].get("value"),
                                "source": src or "code default of profile_metrics.DEFAULT_PARAMS differs from thresholds.json"})
    for k, entry in sorted(f_lib.items()):
        mod_name, attr = k.split(".", 1)
        v = getattr({"silhouette": silhouette, "profile_metrics": pm}.get(mod_name), attr, None)
        if not _same(v, entry.get("value")):
            non_default.append({"group": "library_constants", "name": k, "effective": v, "file_value": entry.get("value"),
                                "source": "constant of the gw library differs from thresholds.json"})
    return {"ok": not non_default and not unlisted, "non_default": non_default, "unlisted": unlisted,
            "report_only_non_default": report_only,
            "reference": "tests/thresholds.json block 'interpretations' (orchestrator interpretations, pending user confirmation)"}


def _same_file(a, b):
    """Two paths name the same file?  Compared by RESOLVED path (symlinks, '..', case on Windows), never by spelling."""
    ra, rb = os.path.normcase(os.path.realpath(str(a))), os.path.normcase(os.path.realpath(str(b)))
    if ra == rb:
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def inputs_audit(test_name, contour_path, H, water_z, fps, sources=None):
    """Are the scene-describing inputs the project's own?  --contour must be target/base_contour.json (compared by resolved
    path), H must equal params.json WAVE_HEIGHT_M, the still-water level must be 0 (spec section 4; params.json has no
    entry for it) and the frame rate must equal params.json fps.  Only the inputs that can change a verdict of `test_name`
    are compared (RELEVANT_INPUTS: the contour is read by test_shape only, the frame rate by test_motion only).  A
    difference is not an error - the self-check judges a synthetic contour on purpose - but such a run is not an
    acceptance run: the verdict gets the suffix ' (NON-OFFICIAL INPUTS)' and the exit code is non-zero.
    --final-frame / --frame-start / --phase-frames are DESCRIPTIONS of the scene, not inputs with an official value: they
    are printed in the verdict block (summary 'scene_description'), never flagged.
    -> {'ok', 'non_official': [{name, effective, official, source}], 'relevant': [...]}"""
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
            "reference": "target/base_contour.json (resolved path), params.json WAVE_HEIGHT_M and fps, still-water level 0 (spec section 4)"}


INTERPRETATION_NOTES = {
    "tiers": "Every check is judged against BOTH tiers of tests/thresholds.json: 'spec' (values of great_wave_blender_prompt.md) and 'user_relaxed_5pct' (working interpretation of the user's '5 %' remark; PENDING USER CONFIRMATION).",
    "S1": "INTERPRETATION pending user confirmation: the crest X is the 'robust extremum' of profile_metrics (tolerance 0.1 % of image height), not the arg-max pixel. Judged against the spec target (38.2 % / 8.7 %); the difference to the base-contour crest is reported as information only.",
    "S2": "Judged as Euclidean distance to the spec target (39.5 % / 46.3 %); dx / dz and the difference to the base-contour deepest point are reported as well.",
    "S3": "Judged as percentage points of image height around 66.0 (64..68 in the spec tier); a relative reading (66 +- 1.32) can be judged from the raw number. INTERPRETATION PENDING USER CONFIRMATION (2026-09-20 hardening): S3 is judged TWICE with the same threshold entry: S3.height_err_pct_h = crest height above Z = 0 (the frame definition) and S3.from_model_trough.height_err_pct_h = crest height above the MODEL'S OWN trough level (lowest Z of the contour between the inner-arc deepest point and the right end of the profile; profile_metrics 'S3_from_model_trough'). Both are printed; because both are judged, the verdict follows the worse one. Reason: the spec words S3 as 'height from the trough to the crest'; a sea raised 3 % in front of the wave read S3 = +0.03 (pass) from Z = 0 but -2.97 from the model's trough.",
    "verdicts": "PASS = validity ok, no judged check failed or was not measurable, AND every check of thresholds.json that belongs to the test's ids (S1-S8 / M1-M6 / G1-G5) was judged at least once. INCOMPLETE = nothing failed but at least one expected check was not judged (skipped test, zero checks): never a pass. FAIL = a judged check failed or could not be measured (NOT_MEASURABLE). INVALID = a validity condition is not met (numbers not trustworthy). ERROR = the script raised (traceback in metrics.json, exit code 2). ' (NON-DEFAULT SETTINGS)' is appended when a verdict-relevant setting / measure parameter differs from tests/thresholds.json 'interpretations'; ' (NON-OFFICIAL INPUTS)' (in front of it) when --contour is not target/base_contour.json (resolved path) or --H / --water-z / --fps differ from params.json (only the inputs that the test really uses are compared). A SystemExit raised while the test body is still running (a build script that calls sys.exit(0) / gw.bootstrap.finish) is an ERROR, never exit code 0. Only the exact verdict 'PASS' gives exit code 0.",
    "validity": "INTERPRETATION pending user confirmation - conditions that make a run INVALID (2026-09-20 hardening, in addition to: profile incomplete, unfilled holes, 0 px above the water, target not segmented like the model): (1) a non-finite vertex / a triangle dropped because of one on a checked frame; (2) a silhouette component that was removed although it is larger than the speck limit (gw.silhouette.SPECK_AREA_PX_FULL_RES = 25 px at full resolution): a detached part, e.g. something standing in the cavity (spec section 5 note 2: a blocked cavity must not go unnoticed) - its bbox is named; (3) the front face never comes down to the still water (profile_metrics 'reached_still_water' false, tolerance trough_tol_pct_h = 0.3 % of image height): S3 from Z = 0 then measures to a level the model never reaches; (4) more than in_s7_false_max_share_pct (35 %) of a segment excluded from S7 by in_S7 = false flags. SECOND HARDENING 2026-09-20: (5) EVALUATION STATE - the tests evaluate the VIEWPORT depsgraph (bpy.context.evaluated_depsgraph_get()); a modifier of a tested object with show_viewport != show_render, a subdivision-type modifier with levels != render_levels, or hide_viewport != hide_render on a tested object means that a render / a RENDER-mode Alembic export delivers other geometry than the one measured -> INVALID in test_shape, test_motion and test_mesh, object and modifier are named; (6) test_mesh only: UNWELDED DUPLICATE vertices / duplicated triangles above dup_max_share_pct (0.1 %) or coincident / coplanar / touching triangle pairs above coincident_tri_pairs_max_share_pct (0.5 % of the triangles) on a checked frame (a second coincident sheet passes G1-G5: G4 counts proper crossings only).",
    "report_only_shape": "REPORT ONLY (no verdict, pending user decision): W.own_h.* = shape descriptors of profile_metrics relative to each contour's OWN crest height h (sections at 0.25 / 0.5 / 0.75 h, o / h, cavity depth / h, aspect ratios) - they do not cancel when a body is wider AND lower; S7.<segment>.signed_* = signed normal deviation (+ = model outside the target body); S7.underside / S7.belly = the inner arc split at the armpit (point of the inner arc between head tip and deepest point farthest from the line tip -> deepest); S1.crest_inside_painted_plateau / S1.height_on_x0_plumb_*: companions of S1 because the painted crest is a plateau about 4-5 % wide; S8.max_vertex_window_turn_deg: turning of the polyline's own vertices over closed 1 % windows (the official base contour itself reads 19 deg there, so no 15 deg verdict).",
    "S4": "The three angles are report-only (S7 governs). The windows 'near the left end / middle / before the crest' and the tolerances of the three boolean checks are INTERPRETATIONS of profile_metrics (docs/measurement_definitions.md 3.1), pending user confirmation.",
    "S5": "Target = head tip of the base contour (right-most point of the head, claws excluded); direction = phi of profile_metrics (chord of the TOP side of the head, 2 %..8 % H of arc length before the tip) applied to BOTH contours - this is THE direction of S5 and of M4 (INTERPRETATION of 'direction of the head tip', pending user confirmation). The direction of the straight line crest -> head tip is reported next to it for both contours (S5.crest_to_tip_*, report only).",
    "S6": "Outer bound only: the right-most point of the wave body between crest and deepest point must stay left of 59.2 % (the toe of the front face is not part of the 'body'; INTERPRETATION).",
    "S7": "Per segment, nearest distance in BOTH directions (model->base and base->model; the backlog definition sheet asks for both), each direction printed separately (S7.<segment>.model_to_base.* / base_to_model.*, INFO) and the WORSE one judged; segments are compared with a 3 % margin into their neighbours; base points with in_S7 = false (completed / occluded) are not counted. INTERPRETATION of profile_metrics, pending user confirmation.",
    "segmentation": "Head tip = right-most point of the whole overhanging head: on the front stretch (crest .. first touch of the still water) the pair (tip before deepest) with the largest come-back of X (profile_metrics 'tip_rule' = max_reversal; an overhang exists from a come-back of 0.3 % of image height). The MODEL is always segmented by this detection; the BASE CONTOUR by its json joints. The same detection is therefore also run on the base contour (T.seg_*): when a json joint (crest, head tip) or the deepest point that follows from them is farther than 0.2 % of image height from the detected one, target and model are not segmented the same way and the run is marked INVALID (not FAIL).",
    "W": "REPORT ONLY - PENDING USER DECISION (no thresholds): horizontal section widths of the contour at Z = 0.25 / 0.5 / 0.75 H (x_back = left-most crossing of the back, or the left frame edge where the back is outside the frame; x_inner = left-most crossing of the front where the section is overhung; x_front = right-most crossing of the front), distances from the crest plumb line, overhang o, cavity depth and the area between the contour and Z = 0, for the model and the base contour with differences in %. Reason: a body 5-8 % too wide passes every spec-tier check (docs/records/step1_tests.md).",
    "S8": "SPEC-LITERAL SINCE 2026-09-20 (second hardening): tangent difference of neighbouring samples (spacing 1 %, 4 phases) < 15 deg with NO exclusion around the head tip (measure parameter s8_tip_exclusion_pct_h = 0). INTERPRETATION that remains: the two stretches [left end, head tip] and [head tip, trough end] are sampled separately (within segments), and the tip itself is covered by extra junctions ON the tip and at every phase offset within one spacing on both sides of it (their chords span the tip). Until 2026-09-20 junctions within 2 % (arc length) of the tip were not judged - an orchestrator interpretation made when the target was expected to have a thin rim; the official large-form target turns only about 10 deg per sample across its tip and the spec text has no exemption, so a pointed tip (38 deg corner) passed. The old number is still reported: S8.max_tip_zone_excluded_deg (REPORT ONLY), next to tip_turn_deg, max_unexcluded_deg and tip_junction_deg. The thin-rimmed SYNTHETIC FIXTURE (rim 2.5 % H, turns ~67 deg per sample at its tip) cannot pass the literal S8; its self-check cases set s8_tip_exclusion_pct_h = 2 explicitly (--measure-param, fixture only; listed as a NON-DEFAULT SETTING).",
    "phases": "INTERPRETATION pending user confirmation. Phase boundaries detected from the data: overhang phase starts at the first frame from which the profile stays overhanging (a head tip exists, o > 0); curl-in phase starts at the frame where phi(t) is largest (the head stops stretching out and starts to turn downward); the motion ends at the last frame (<= declared final frame) whose contour still moved. --phase-frames A,B or params.json 'motion_phase_frames' replace the detected A (first overhang frame) and B (first curl-in frame).",
    "M2": "h must not decrease from the first frame up to the first overhang frame. theta_start = theta of the first frame; theta_end = theta of the LAST NON-OVERHANGING frame (so a jump from a gentle slope straight into an overhang fails). Decreases below the noise floor are judged as 0 (INTERPRETATION); the raw value is reported.",
    "M3": "o must not decrease inside the overhang phase; h_drop = (h at phase start - min h in the phase) / h at phase start; tip_crosses_crest_plumb = o > 0 at the end of the phase and the head tip did not move back towards -X over the phase.",
    "M4": "phi must not increase from the first curl-in frame to the stop frame (increases below the noise floor are judged as 0).",
    "M5": "Contour speed of a frame = pm.contour_displacement to the previous frame (largest nearest-point distance between the two contours, both directions, water run ignored). stop frame = last frame <= the declared final frame whose contour still moved; stop_speed_ratio = its speed / largest speed of the whole animation. 'Gradual deceleration during the last second' has NO numeric threshold in thresholds.json: the speeds of that window are reported (decel_*), not judged. post_stop (SECOND HARDENING 2026-09-20) = largest contour displacement over EVERY hold frame the scene has after the declared final frame (final + 1 .. scene.frame_end), frame to frame AND against the final frame's contour (slow drift), floored at static_disp_eps_H. The scene must provide a hold of at least min_hold_s = 1 s (30 frames at 30 fps): with a shorter hold in which nothing moves the check is NOT judged (status NOT_JUDGED: 'not measurable on this scene') and the verdict is INCOMPLETE, never PASS; movement inside a short hold still FAILS. Until then 3 extrapolated frames were judged, so a pose held 3 frames and drifting afterwards passed. --hold-frames N evaluates exactly N frames after the final frame instead (NON-DEFAULT SETTING); --hold-frames 0 = NOT_MEASURABLE (counts as failed), never a silent 0. The final frame is --final-frame, else scene['gw_final_frame'] (set by the builder), else scene.frame_end (then the scene has no hold).",
    "M6": "INTERPRETATION pending user confirmation: jump ratio of frame pair k = d(k) / max(min(d(k-1), d(k+1)), floor) with floor = 5 % of the largest displacement; i.e. a displacement must stay below 3 x BOTH neighbours, and neighbours that are (almost) at rest are not used as a denominator. This is the JUDGED reading of the spec text; the backlog-definition reading is reported next to it (M6_backlog).",
    "M6_backlog": "REPORT ONLY - PENDING USER DECISION (docs/backlog_crosscheck.md item 2: the backlog definition sheet says 'must not exceed 3 x the MEDIAN of the neighbouring frames, excluding the transition to the stop', the spec says '< 3 x the displacement of the neighbouring frames'): ratio(k) = d(k) / median(d of the m6_backlog_half_window = 2 frame pairs before and the 2 after k), no floor; frame pairs inside the last m6_backlog_exclude_window_s (= M5 deceleration window, 1 s) before the stop frame and after it are excluded; the maximum over the remaining pairs is reported as M6.backlog_jump_ratio next to the reference factor 3.",
    "hold_backlog": "REPORT ONLY - PENDING USER DECISION (docs/backlog_crosscheck.md item 3: 'the still pose is held 10 s with contour movement <= 0.2 % of image height'; the spec's M5 only says the shape does not change after the stop): the hold after the final frame (backlog_hold_s = 10 s = 300 frames at 30 fps; frames beyond scene.frame_end are evaluated as Blender extrapolates the animation) is sampled every backlog_hold_step_frames and each sample is compared with the FINAL frame's contour; the largest movement is reported as M5.backlog_hold_max_disp_pct_h next to the reference 0.2 %. Still REPORT ONLY, but since 2026-09-20 a movement above the reference (M5.backlog_hold_within_reference = False) prints a WARNING line in summary.md and in the GW RESULT line.",
    "inputs": "NON-OFFICIAL INPUTS (2026-09-20): the verdict gets the suffix ' (NON-OFFICIAL INPUTS)' and the exit code is non-zero when --contour is not target/base_contour.json (compared by RESOLVED path, not by spelling) or when H / still-water level / frame rate differ from params.json WAVE_HEIGHT_M / 0 / fps. Compared are only the inputs the test uses (shape: contour, H, water level; motion: H, water level, fps - also the scene's own fps when --fps is not given; mesh: H, water level). --final-frame, --frame-start and --phase-frames describe the scene; they are printed in the verdict block (summary.scene_description) and never flagged.",
    "evaluation_state": "The tests evaluate the VIEWPORT depsgraph (bpy.context.evaluated_depsgraph_get()): modifiers with show_viewport, viewport subdivision levels. gw.silhouette.viewport_render_mismatches() lists modifiers whose viewport and render state differ; any entry -> INVALID (T.n_viewport_render_mismatches). Not detectable: node groups that branch on 'Is Viewport', drivers / handlers reading the evaluation mode, scene simplify settings.",
    "mesh_duplicates": "INTERPRETATION pending user confirmation (validity of test_mesh, 2026-09-20): on the final frame and every G4 frame, vertices are clustered by position (dup_vertex_eps_rel_H = 1e-6 H). A cluster whose vertices are NOT all joined by collapsed (zero-length) mesh edges holds UNWELDED DUPLICATES (second sheet, unwelded seam): T.n_duplicate_vertices. Non-degenerate triangles with the same three corner positions as another triangle: T.n_duplicate_triangles. Coincident / coplanar / touching triangle pairs (the BVH-overlapping pairs that G4 ignores): T.max_coincident_triangle_pairs. Limits dup_max_share_pct = 0.1 % and coincident_tri_pairs_max_share_pct = 0.5 % of the triangle count; above -> INVALID. NOT detectable: a second sheet that is offset by more than the epsilon and does not touch the first one.",
    "G1": "Evaluated mesh of every frame: vertex / edge / polygon / loop counts, polygon sizes, loop->vertex indices, UV layer names and UV coordinates are hashed and compared with the first frame.",
    "G2": "Hem = vertices of boundary edges (edges used by exactly one polygon) of the evaluated mesh; measured = max |Z_world - water_z| over all frames in % of H.",
    "G3": "INTERPRETATION pending user confirmation: rim thickness = diameter of the largest circle inscribed in the cross-section (plane Y = const) that touches the section at the rim point; the rim point is where the section crosses mesh edges whose two vertices are in the vertex group 'crest_rim'. For a rounded rim this is the diameter of the rounding (2 r). Judged on the final frame, on the sections whose head tip coincides with the head tip seen by CAM_print; the maximum over those sections is judged.",
    "G4": "Candidate pairs from mathutils BVHTree.overlap(tree, tree); pairs that share a vertex are ignored; a pair counts as a self-intersection only if the two triangles cross PROPERLY (each has vertices strictly on both sides of the other's plane, planes not parallel, intersection segment longer than the tolerance). Coincident / touching / degenerate pairs are reported separately and not judged (INTERPRETATION).",
    "G5": "The builder script is run again in a reset scene of this process AND in a fresh Blender process; evaluated vertex positions (float32 bytes) and the world matrix are compared bit-exactly on several frames.",
}


# ------------------------------------------------------------------------------------ json helpers
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
            raise ValueError("expected key=value, got %r" % it)
        k, v = it.split("=", 1)
        out[k.strip()] = _parse_value(v.strip())
    return out


# ------------------------------------------------------------------------------------ command line
def add_common_args(ap):
    g = ap.add_argument_group("scene")
    g.add_argument("--object", default=None, help="name of the wave mesh object (comma separated list = several objects form the silhouette; the first one is the mesh that the G tests inspect). Default: the object returned by the builder, or the only mesh object of the scene.")
    g.add_argument("--blend", default=None, help=".blend file to open (alternative: pass it to blender before --python)")
    g.add_argument("--build-script", default=None, help="python file that builds the wave into the scene (see common_test.py: builder-script protocol)")
    g.add_argument("--build-func", default=None, help="function of the build script to call (default: build_for_tests | build | build_object)")
    g.add_argument("--build-arg", action="append", default=[], metavar="KEY=VALUE", help="keyword argument for the build function (repeatable, json-decoded)")
    g.add_argument("--contour", default=None, help="base contour json (default target/base_contour.json)")
    g.add_argument("--frame-start", type=int, default=None, help="first frame (default scene.frame_start)")
    g.add_argument("--final-frame", type=int, default=None, help="frame of the final shape (default scene.frame_end)")
    g.add_argument("--fps", type=float, default=None, help="frames per second (default: scene render fps)")
    g.add_argument("--H", type=float, default=None, help="wave height in m (default params.json WAVE_HEIGHT_M)")
    g.add_argument("--water-z", type=float, default=0.0, help="world Z of the still-water plane (default 0)")
    g.add_argument("--res-scale", type=float, default=None, help="mask resolution factor (default: per test, see TEST_SETTINGS)")
    o = ap.add_argument_group("output")
    o.add_argument("--out-dir", default=None, help="result directory (default results/<YYYYMMDD_HHMMSS>_<test>/)")
    o.add_argument("--tag", default=None, help="text appended to the default result directory name")
    o.add_argument("--exit-tier", default="spec", choices=list(TIERS) + ["none"], help="tier that decides the process exit code (both tiers are always reported)")
    o.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a TEST_SETTINGS entry (repeatable)")
    o.add_argument("--measure-param", action="append", default=[], metavar="KEY=VALUE",
                   help="override a measure parameter of gw.profile_metrics.DEFAULT_PARAMS (repeatable; unknown names raise). A verdict-relevant "
                        "one puts ' (NON-DEFAULT SETTINGS)' behind the verdict. Used by the self-check for the thin-rimmed synthetic fixture "
                        "(s8_tip_exclusion_pct_h=2, fixture only)")
    o.add_argument("--background-image", default="auto", choices=["auto", "painting", "white"], help="overlay background: auto = painting when the contour json names an image, else white")
    return ap


# ------------------------------------------------------------------------------------ context
class Ctx:
    """Everything a test needs: scene, objects, frame range, H, run directory, settings."""

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
        self.settings_sources = {}     # {name: 'params.json test_settings' | '--set'} of the settings that were overridden
        self.builder = None            # callable(scene) -> object, or None
        self.source = {}
        self.frame_start = None
        self.final_frame = None
        self.fps = None
        self.contour_path = None
        self.background = "auto"
        self.untested_mesh_objects = []   # mesh objects of the scene that are NOT part of the tested silhouette (reported)
        self.measure_overrides = {}       # --measure-param key=value
        self.measure_params = None        # flat dict of pm.get_params(measure_overrides): THE measure parameters of this run
        self.input_sources = {}           # {'H' | 'fps' | 'frame_start' | 'final_frame' | 'contour': where the value came from}
        self.scene_frame_end = None       # scene.frame_end when the context was set up (hold window of test_motion)

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
            "evaluation": "VIEWPORT depsgraph (bpy.context.evaluated_depsgraph_get()); see interpretation note 'evaluation_state'",
            "command_line": bootstrap.script_args(),
        }

    def audit(self, effective=None, measure_params=None):
        """settings_audit() of this context (see there); `effective` = settings replaced directly by the command line.
        The measure parameters are those of the run (--measure-param overrides included)."""
        mp = measure_params if measure_params is not None else self.measure_params
        return settings_audit(self.settings, self.settings_sources, mp, effective)

    def inputs(self, test_name=None):
        """inputs_audit() of this context for `test_name` (default: the context's own test)."""
        return inputs_audit(test_name or self.test_name, self.contour_path, self.H, self.water_z, self.fps, self.input_sources)

    def scene_description(self, **extra):
        """The scene-describing arguments that are NOT compared with an official value (printed in the verdict block)."""
        d = {"frame_start": self.frame_start, "frame_start_source": self.input_sources.get("frame_start"),
             "final_frame": self.final_frame, "final_frame_source": self.input_sources.get("final_frame"),
             "scene_frame_end": self.scene_frame_end, "fps": self.fps, "fps_source": self.input_sources.get("fps"),
             "H_m": self.H, "water_z_m": self.water_z, "objects": [o.name for o in self.objs]}
        d.update(extra)
        return d


def file_sha1(path):
    """sha1 of a file (None when it cannot be read): recorded so that a result can be tied to the exact target file."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except (OSError, TypeError):
        return None


def untested_objects_report(ctx):
    """REPORT ONLY.  A build script (or a .blend) may hold more mesh objects than the ones that are tested: only the object the
    builder returns / --object names is part of the silhouette.  Something that stands in the cavity as a SEPARATE, unlisted
    object is therefore invisible to every check.  -> (report record T.n_untested_mesh_objects, note or None)"""
    names = list(ctx.untested_mesh_objects)
    rec = report_value("T", "n_untested_mesh_objects", len(names), "count",
                       note="mesh objects of the scene that are NOT part of the tested silhouette%s; no verdict - the test cannot know whether they belong to the wave"
                            % ("" if not names else ": " + ", ".join(names[:10])))
    note = None if not names else ("NOTE (no verdict): the scene holds %d mesh object(s) that are NOT tested: %s. Only %s form(s) the silhouette; list further objects with "
                                   "--object a,b if they belong to the wave." % (len(names), ", ".join(names[:10]), ", ".join(o.name for o in ctx.objs)))
    return rec, note


def resolve_path(p):
    """Absolute path of an input file given absolute, relative to the current directory or relative
    to the project root (in this order).  No other fallback; a missing file raises later."""
    if p is None:
        return None
    p = str(p)
    if os.path.isabs(p) or os.path.exists(p):
        return paths.norm(p)
    cand = os.path.join(paths.PROJECT_ROOT, p)
    return paths.norm(cand) if os.path.exists(cand) else paths.norm(p)


def load_builder(script_path, func_name=None, build_args=None):
    """-> (callable(scene) -> object | None, info dict)"""
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
            raise BuildScriptExit("build script called sys.exit(%r) while it was being IMPORTED (%s): module-level code must not end the "
                                  "process; nothing was built and no check ran" % (exc.code, script_path)) from exc
    names = [func_name] if func_name else ["build_for_tests", "build", "build_object"]
    func = None
    for nm in names:
        if hasattr(mod, nm):
            func, func_name = getattr(mod, nm), nm
            break
    if func is None:
        raise AttributeError("build script %s has none of the functions %s" % (script_path, names))
    kwargs = dict(build_args or {})

    def _build(scene):
        # A build function that ends with sys.exit(0) / gw.bootstrap.finish(True, ..) - the convention of every STAND-ALONE
        # script of this project - would end the TEST process with exit code 0 before a single check ran.  SystemExit is
        # caught HERE, specifically, and turned into an ordinary error that names the cause (guarded_main -> ERROR, exit 2).
        try:
            ret = func(scene, **kwargs)
        except SystemExit as exc:
            raise BuildScriptExit("build script called sys.exit(%r) inside %s() of %s: a build function must RETURN (the object or None), "
                                  "not end the process (gw.bootstrap.finish() is sys.exit); no check ran"
                                  % (exc.code, func_name, script_path)) from exc
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
                raise KeyError("object %r not found in the scene (mesh objects: %s)"
                               % (nm, ", ".join(o.name for o in _mesh_objects(scene)) or "none"))
            objs.append(ob)
        return objs
    if built is not None and hasattr(built, "name"):
        return [built]
    meshes = _mesh_objects(scene)
    if len(meshes) == 1:
        return meshes
    raise KeyError("--object is required: the scene has %d mesh objects (%s)"
                   % (len(meshes), ", ".join(o.name for o in meshes)))


def run_dir_from_args(args, test_name):
    """The result directory of a run: --out-dir, else results/<YYYYMMDD_HHMMSS>_<test>[_<tag>]/ (created)."""
    if getattr(args, "out_dir", None):
        return paths.ensure_dir(args.out_dir)
    name = test_name if not getattr(args, "tag", None) else "%s_%s" % (test_name, args.tag)
    return paths.results_run_dir(name)


def setup_context(args, test_name, run_dir=None):
    """Open / build the scene described by the common arguments and return a Ctx.
    run_dir: the directory prepared by guarded_main() (None = derive it from the arguments here)."""
    import bpy
    ctx = Ctx()
    ctx.args = args
    ctx.test_name = test_name
    if run_dir is None:
        run_dir = run_dir_from_args(args, test_name)
    ctx.run_dir = paths.ensure_dir(run_dir)
    ctx.settings, ctx.settings_sources = get_settings(parse_kv_list(getattr(args, "set", [])), with_sources=True)
    ctx.measure_overrides = parse_kv_list(getattr(args, "measure_param", []) or [])
    ctx.measure_params = pm.get_params(ctx.measure_overrides or None)          # unknown names raise here, before the build
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
    # final frame: --final-frame, else the builder's declaration scene['gw_final_frame'], else scene.frame_end.  A scene that
    # HOLDS the final pose (M5: at least min_hold_s after the final frame) has frame_end > final frame, so it must declare it.
    declared = ctx.scene.get("gw_final_frame") if hasattr(ctx.scene, "get") else None
    if args.final_frame is not None:
        ctx.final_frame, src_ff = int(args.final_frame), "--final-frame"
    elif declared is not None:
        ctx.final_frame, src_ff = int(declared), "scene['gw_final_frame'] (declared by the builder / the .blend)"
    else:
        ctx.final_frame, src_ff = int(ctx.scene.frame_end), "scene.frame_end (no hold frames after it)"
    ctx.scene_frame_end = int(ctx.scene.frame_end)
    ctx.fps = float(args.fps) if args.fps is not None else float(ctx.scene.render.fps) / float(ctx.scene.render.fps_base)
    ctx.contour_path = resolve_path(args.contour) if args.contour else paths.BASE_CONTOUR_JSON
    ctx.input_sources = {"H": "--H" if args.H is not None else "params.json WAVE_HEIGHT_M", "water_z": "--water-z",
                         "fps": "--fps" if args.fps is not None else "scene render fps (no --fps given)",
                         "contour": "--contour" if args.contour else "default target/base_contour.json",
                         "frame_start": "--frame-start" if args.frame_start is not None else "scene.frame_start", "final_frame": src_ff}
    log("[%s] object=%s H=%.3f m frames %d..%d (final frame from %s; scene.frame_end %d) fps=%.3g run_dir=%s"
        % (test_name, ",".join(o.name for o in ctx.objs), ctx.H, ctx.frame_start, ctx.final_frame, src_ff, ctx.scene_frame_end, ctx.fps, ctx.run_dir))
    return ctx


def evaluation_state_report(ctx):
    """VALIDITY (2026-09-20, second hardening).  The tests evaluate the VIEWPORT depsgraph.  A modifier of a tested object
    whose show_viewport differs from show_render (or whose viewport / render subdivision levels differ, or an object
    whose hide_viewport differs from hide_render) means that the geometry a render / a RENDER-mode Alembic export
    delivers is NOT the geometry that was measured (the sceptic's render-only Displace modifier: 10 % of H off, every
    number identical to the clean run).  -> (report record T.n_viewport_render_mismatches, [validity notes], ok)"""
    items = silhouette.viewport_render_mismatches(list(ctx.objs))
    rec = report_value("T", "n_viewport_render_mismatches", len(items), "count",
                       note="modifiers / objects whose VIEWPORT state differs from their RENDER state (the tests evaluate the viewport depsgraph); > 0 -> INVALID%s"
                            % ("" if not items else ": " + "; ".join("%s / %s" % (d["object"], d["modifier"] or "object flags") for d in items[:10])))
    notes = []
    if items:
        notes.append("VIEWPORT STATE != RENDER STATE: the tests evaluate the VIEWPORT depsgraph, but %d modifier(s) / object flag(s) of the tested object(s) differ between "
                     "viewport and render: %s. A render or an Alembic export in RENDER mode would deliver OTHER geometry than the one measured here, so no number "
                     "of this run can be trusted for the delivered mesh."
                     % (len(items), "; ".join("object '%s' %s: %s (viewport %s, render %s)"
                                              % (d["object"], ("modifier '%s' [%s]" % (d["modifier"], d["type"])) if d["modifier"] else "itself",
                                                 d["what"], d["viewport"], d["render"]) for d in items[:10])))
    return rec, notes, not items


def rebuild_scene(ctx):
    """Reset the scene and run the builder again (G5).  -> list of objects."""
    import bpy
    if ctx.builder is None:
        raise RuntimeError("no build script")
    if ctx.source.get("blend"):
        bpy.ops.wm.open_mainfile(filepath=ctx.source["blend"])
    else:
        bootstrap.reset_scene()
    built = ctx.builder(bpy.context.scene)
    ctx.scene = bpy.context.scene
    ctx.objs = resolve_objects(ctx.scene, ctx.args.object, built)
    ctx.obj = ctx.objs[0]
    return ctx.objs


# ------------------------------------------------------------------------------------ checks
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
    """One check record.  Limits and the comparison come ONLY from tests/thresholds.json.

    measured   : number / bool / None (None = could not be measured -> NOT_MEASURABLE = counts as failed)
    not_judged : True = THE SCENE DOES NOT PROVIDE what the check needs (e.g. M5 post-stop without a 1 s hold): status
                 NOT_JUDGED in both tiers - neither passed nor failed; the check then counts as 'expected but not judged',
                 so the verdict is INCOMPLETE (never PASS) unless something else failed.  The note must say why.
    sub        : e.g. the S7 segment name -> id 'S7.back.mean_dev_pct_h'
    target     : the target value (or dict) the measured value is compared with, for the report
    difference : measured minus target when that is not the judged number itself
    where      : location of the measurement / failure (segment, arc length, H and painting px position)
    raw        : un-quantised value when `measured` went through a noise floor
    info_only  : evaluated against the limits for information, never counted in the verdict
    """
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
    """A reported quantity that has NO entry in thresholds.json (never judged)."""
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
    """['S1.dx_pct_h', ...]: every check of thresholds.json with a limit (value not null) that belongs to `test_ids`."""
    T = paths.load_thresholds()
    out = []
    for tid in test_ids or []:
        for name, entry in T[tid]["checks"].items():
            if entry.get("value") is not None:
                out.append("%s.%s" % (tid, name))
    return out


def validate_names(given, allowed, what):
    """Names of --only / --skip / --cases: an unknown name is an ERROR (a typo used to select nothing and the empty
    run came out as PASS).  -> list of the given names in canonical spelling"""
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
        raise ValueError("unknown name(s) %s given to %s (allowed: %s)" % (", ".join(repr(b) for b in bad), what, ", ".join(str(a) for a in allowed)))
    return out


def summarize(checks, validity_ok=True, validity_notes=None, skipped=None, expected=None, audit=None, errors=None,
              inputs=None, warnings=None, scene_description=None):
    """Verdict per tier: PASS | FAIL | INVALID | INCOMPLETE | ERROR, plus ' (NON-OFFICIAL INPUTS)' and ' (NON-DEFAULT SETTINGS)'.

    INVALID    = the validity conditions of the test are not met (no solid silhouette, target and model not segmented
                 the same way, non-finite vertices, a detached silhouette component, ...): the numbers are not trustworthy,
                 so the run is neither passed nor failed.
    FAIL       = validity ok, but a judged check failed or could not be measured (NOT_MEASURABLE counts as failed).
    INCOMPLETE = validity ok and nothing failed, but NOT every expected check was judged (`expected` = test ids, e.g.
                 ['G1', .., 'G5']; every check of thresholds.json with a limit under these ids must have been judged at
                 least once) or no check was judged at all.  A run with zero checks is never a PASS.
    PASS       = validity ok, at least one judged check, every expected check judged, nothing failed.
    ERROR      = `errors` is not empty (a sub-test of run_all raised).
    audit      = settings_audit(): when a verdict-relevant setting differs from thresholds.json 'interpretations' the verdict
                 string gets the suffix ' (NON-DEFAULT SETTINGS)' ('verdict_base' keeps the plain word).
    The process exit code is 0 only for the exact verdict 'PASS' (common_test.exit_code)."""
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
        return "n/a"
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
        parts.append("%d stretch(es)" % w["n_ranges"])
    return " ".join(parts)


def log_checks(checks, title):
    log("---- %s" % title)
    for c in checks:
        st = " ".join("%s:%s" % (t, c["tiers"][t]["status"]) for t in TIERS)
        lim = "/".join(_fmt(c["tiers"][t]["limit"]) for t in TIERS)
        extra = ""
        if c.get("target") is not None and not isinstance(c["target"], dict):
            extra += " target=%s" % _fmt(c["target"])
        if c.get("raw") is not None:
            extra += " raw=%s" % _fmt(c["raw"])
        wt = _where_text(c.get("where"))
        tsc = c.get("target_self_check")
        if tsc and tsc["spec"] in ("FAIL", "NOT_MEASURABLE"):
            extra += " TARGET-VS-ITSELF=%s(%s)" % (_fmt(tsc["measured"]), tsc["spec"])
        log("%-34s m=%-11s %s limit(%s)=%s [%s]%s%s" % (c["id"], _fmt(c["measured"]), st, c["op"], lim, c["unit"] or "",
                                                          extra, (" @ " + wt) if wt else ""))


def summary_markdown(result):
    """Markdown table of one test result (written next to metrics.json)."""
    L = ["# %s  (%s)" % (result["test"], result["context"].get("created", "")), ""]
    s = result["summary"]
    L.append("- 判定 verdict: " + ", ".join("`%s` = **%s**" % (t, s[t]["verdict"]) for t in TIERS))
    L.append("- 有效性 validity: %s %s" % ("OK" if s["validity_ok"] else "**NOT OK**", "; ".join(s["validity_notes"])))
    if s.get("skipped"):
        L.append("- 跳过 skipped: " + ", ".join(s["skipped"]))
    miss = s.get(TIERS[0], {}).get("expected_not_judged") or []
    if miss:
        L.append("- **未判定的应判项 expected but NOT judged (-> INCOMPLETE unless something failed)**: " + ", ".join(miss))
    if s.get(TIERS[0], {}).get("n_judged") == 0:
        L.append("- **没有任何一项被判定 zero judged checks**: a run without judged checks is never a PASS")
    for d in s.get("non_default_settings") or []:
        L.append("- **NON-DEFAULT SETTING** `%s.%s` = %s (tests/thresholds.json interpretations: %s; source: %s)"
                 % (d["group"], d["name"], _fmt(d["effective"]), _fmt(d["file_value"]), d["source"]))
    for d in s.get("report_only_non_default_settings") or []:
        L.append("- non-default setting that only affects report-only values: `%s.%s` = %s (default %s; source: %s)"
                 % (d["group"], d["name"], _fmt(d["effective"]), _fmt(d.get("default")), d["source"]))
    if result.get("error"):
        L += ["", "## ERROR", "", "`%s: %s`" % (result["error"]["type"], result["error"]["message"]), "", "```", result["error"]["traceback"].rstrip(), "```"]
    if result.get("test") == "all":
        for e in s.get("errors") or []:
            L.append("- **ERROR in sub-test** %s" % e)
    L += ["", "| 指标 id | 实测 measured | 目标 target | 差 diff | 单位 unit | op | spec 限 | spec | 5% 限 | 5% | 位置 / 备注 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in result["checks"]:
        ts, tr = c["tiers"][TIERS[0]], c["tiers"][TIERS[1]]
        note = _where_text(c.get("where"))
        if c.get("raw") is not None:
            note = ("raw=%s " % _fmt(c["raw"])) + note
        tsc = c.get("target_self_check")
        if tsc and tsc["spec"] in ("FAIL", "NOT_MEASURABLE"):
            note = ("**target vs itself: %s (%s)** " % (_fmt(tsc["measured"]), tsc["spec"])) + note
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["id"], _fmt(c["measured"]), _fmt(c["target"]), _fmt(c["difference"]), c["unit"] or "", c["op"],
            _fmt(ts["limit"]), ts["status"], _fmt(tr["limit"]), tr["status"], note.replace("|", "/")))
    L.append("")
    return "\n".join(L)


def write_result(ctx_or_dir, result):
    """metrics.json + summary.md in the run directory.  -> metrics path"""
    run_dir = ctx_or_dir.run_dir if isinstance(ctx_or_dir, Ctx) else ctx_or_dir
    p = paths.write_json(os.path.join(run_dir, "metrics.json"), jsonable(result))
    md = paths.ensure_parent(os.path.join(run_dir, "summary.md"))
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(summary_markdown(result))
    return p


def exit_code(result, exit_tier="spec"):
    """0 only when the verdict of the exit tier is exactly 'PASS'; 2 for ERROR (any tier); otherwise 1.
    --exit-tier none -> 0 unless ERROR (the caller asked for the numbers only; the RESULT line then says NONE)."""
    s = result["summary"]
    if any(s[t].get("verdict_base", s[t]["verdict"]) == "ERROR" for t in TIERS):
        return EXIT_CODE_ERROR
    if exit_tier == "none":
        return 0
    return 0 if s[exit_tier]["verdict"] == "PASS" else 1


def finish(result, exit_tier="spec"):
    """Log the verdicts, remove the RUNNING marker and leave Blender with exit_code()."""
    s = result["summary"]
    line = " ".join("%s=%s" % (t, s[t]["verdict"]) for t in TIERS)
    for t in TIERS:
        if s[t]["failed"] or s[t]["not_measurable"]:
            log("[%s] %s failed: %s%s" % (result["test"], t, ", ".join(s[t]["failed"]) or "-",
                                          ("; not measurable: " + ", ".join(s[t]["not_measurable"])) if s[t]["not_measurable"] else ""))
    miss = s[TIERS[0]].get("expected_not_judged") or []
    if miss:
        log("[%s] expected checks that were NOT judged: %s" % (result["test"], ", ".join(miss)))
    for d in s.get("non_default_settings") or []:
        log("[%s] NON-DEFAULT SETTING %s.%s = %s (thresholds.json interpretations: %s; source: %s)"
            % (result["test"], d["group"], d["name"], _fmt(d["effective"]), _fmt(d["file_value"]), d["source"]))
    code = exit_code(result, exit_tier)
    word = "ERROR" if code == EXIT_CODE_ERROR else ("NONE" if exit_tier == "none" else ("PASS" if code == 0 else "FAIL"))
    if result.get("run_dir"):
        end_run(result["run_dir"])
    log("RESULT %s %s %s (exit tier: %s, exit code %d) -> %s" % (word, result["test"], line, exit_tier, code, result.get("run_dir", "")))
    sys.stdout.flush()
    sys.exit(code)


# ------------------------------------------------------------------------------------ run directory / crash safety
RUNNING_MARKER = "RUNNING"
_STALE_EXACT = ("metrics.json", "summary.md", "contact_sheet.png", "g2_hem.png", "g3_sections.png", "g4_intersections.png",
                "g5_subprocess.log", "g5_subprocess_vertices.npz", RUNNING_MARKER)
_STALE_PREFIX = ("overlay_", "crop_", "plot_")


def begin_run(run_dir, test_name="?"):
    """Prepare a run directory so that it can never show the result of an EARLIER run as the result of this one:
    existing outputs of the tests (metrics.json, summary.md, the known image names; a left-over RUNNING marker of a run
    that never finished) are renamed to stale_<stamp>_<name>, then a RUNNING marker is written.  end_run() removes the
    marker; a marker that is still there afterwards means the process died (metrics.json is then absent or 'ERROR').
    -> list of the renamed files"""
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
        fh.write("test %s started %s pid %d\nThis file is removed when the run ends (also when it ends with ERROR). If it is still here, "
                 "the process died and any metrics.json next to it does not belong to a finished run.\n"
                 % (test_name, _dt.datetime.now().isoformat(timespec="seconds"), os.getpid()))
    if renamed:
        log("[%s] run directory was not empty: %d stale output file(s) renamed to stale_%s_*" % (test_name, len(renamed), stamp))
    return renamed


def end_run(run_dir):
    p = os.path.join(run_dir, RUNNING_MARKER)
    if os.path.isfile(p):
        os.remove(paths.assert_writable(p))


def error_result(test_name, run_dir, exc, tb, context=None):
    """Result dict of a run that raised: verdict ERROR in both tiers, traceback included."""
    summ = {"validity_ok": False, "validity_notes": ["ERROR: the test script raised %s: %s" % (type(exc).__name__, exc)], "skipped": [],
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
    """Crash-safe frame of every test main():  run dir -> begin_run -> body(run_dir) -> finish.

    body(run_dir) returns the result dict (already written by the test).  ANY exception inside it (bad arguments, a
    build script that raises, a bug in the test) is written to the log with its traceback AND to metrics.json /
    summary.md as verdict 'ERROR'; the process then exits with code 2.  So a crash can neither leave an older
    metrics.json in place (begin_run renamed it) nor end with exit code 0 (the sceptic's 'stale_demo': Blender without
    --python-exit-code 1 returned 0 next to a stale PASS)."""
    run_dir = None
    try:
        run_dir = run_dir_from_args(args, test_name)
        begin_run(run_dir, test_name)
        result = body(run_dir)
    except SystemExit:
        raise
    except BaseException as exc:                                       # noqa: BLE001 - everything must end as ERROR, exit 2
        tb = traceback.format_exc()
        for ln in tb.rstrip().splitlines():
            log("[%s] ERROR %s" % (test_name, ln))
        try:
            if run_dir is None:
                run_dir = paths.results_run_dir("%s_error" % test_name)
            write_result(run_dir, error_result(test_name, run_dir, exc, tb))
            end_run(run_dir)
        except Exception as exc2:                                      # the ERROR report itself must never hide the exit code
            log("[%s] ERROR while writing the ERROR result: %s: %s" % (test_name, type(exc2).__name__, exc2))
        log("RESULT ERROR %s %s (exit code %d) -> %s" % (test_name, " ".join("%s=ERROR" % t for t in TIERS), EXIT_CODE_ERROR, run_dir))
        sys.stdout.flush()
        sys.exit(EXIT_CODE_ERROR)
    finish(result, getattr(args, "exit_tier", "spec"))


# ------------------------------------------------------------------------------------ locations
def where_point(F, pH, segment=None, s_H=None, **extra):
    """Location record of one point given in H units."""
    px = F.H_to_px(pH[0], pH[1])
    pct = F.H_to_pct(pH[0], pH[1])
    w = {"segment": segment, "H": [float(pH[0]), float(pH[1])], "px": [float(px[0]), float(px[1])],
         "left_top_pct": [float(pct[0]), float(pct[1])],
         "s_pct_h": None if s_H is None else float(pm.H_to_pct_h(s_H))}
    w.update(extra)
    return w


def ranges_above(values, limit, mask=None):
    """Index ranges [(i0, i1)] (inclusive) where values > limit (and mask is True)."""
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


# ------------------------------------------------------------------------------------ evaluated mesh
def eval_mesh_arrays(obj, depsgraph=None, topology=True, uv=False):
    """Arrays of the EVALUATED mesh of `obj` on the current frame.

    -> dict: co_local (n, 3) float32, matrix_world (4, 4) float64, co_world (n, 3) float64 and, with
       topology: tris (m, 3) int32, tri_poly (m,) int32, tri_loops (m, 3) int32, loop_vert (l,) int32, poly_start,
       poly_total, edges (e, 2) int32;  with uv: uv_layers {name: (l, 2) float32};
       always: n_nonfinite_vertices, nonfinite_vertex_indices (first 20) of co_world
    """
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
    """Vertices of boundary edges (edges used by exactly one polygon).  -> (vertex indices, n boundary edges)"""
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


# ------------------------------------------------------------------------------------ overlay drawing
SEG_COLORS = {"back": "red", "head": "orange", "inner_arc": "magenta", "trough_run": "cyan"}


def upsample_mask(mask, width, height):
    """nearest-neighbour resize of a bool mask to (height, width)."""
    h, w = mask.shape
    if (h, w) == (height, width):
        return mask
    yi = np.minimum((np.arange(height) + 0.5) * h / float(height), h - 1).astype(np.int64)
    xi = np.minimum((np.arange(width) + 0.5) * w / float(width), w - 1).astype(np.int64)
    return mask[yi][:, xi]


def draw_view(base_rgb, box, scale, polylines=(), markers=(), title=None, legend=None):
    """Zoomed crop of `base_rgb` (painting-sized image) with polylines / markers given in FULL image px.
    polylines: dicts {px (N,2), color, width, dash}; markers: dicts {px, kind, color, label, size}."""
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
    yy = img.shape[0] - 6 - 24 * len(legend)           # legend in the bottom-left corner (the crest is at the top)
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
