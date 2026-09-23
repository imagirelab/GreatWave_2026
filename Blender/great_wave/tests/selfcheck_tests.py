"""Self-check of the S / M / G tests: prove that they are meaningful.

The synthetic fixture (tests/fixtures/make_synthetic_wave.py; target = its own analytic contour
tests/fixtures/synthetic_contour.json) is built unmodified and with DELIBERATE defects.  The
unmodified build must PASS; every defect must make exactly the expected checks FAIL.

  blender --background --factory-startup --python-exit-code 1 --python tests/selfcheck_tests.py -- [--cases a,b,...] [--quick]
(--python-exit-code 1 is REQUIRED for direct calls; an unknown name in --cases is an error, exit code 2.)

Expectations were written down BEFORE the first run (reasoning in the comments of CASES).  Two kinds:
  exact     : the set of failing checks of the test must EQUAL `must_fail`
  analytic  : `must_fail` must be contained in the failing set AND the failing set must equal the
              set predicted by an independent evaluation: the same defect applied to the fixture's
              profile polyline, judged by test_shape.judge_profile WITHOUT mesh / silhouette / Blender
  at_least  : only `must_fail` must be contained (negative demos whose side effects are not predicted)

HARDENING CASES (2026-09-20, after the sceptic's audit results/step1_prepare/verify_tests/): HARDEN_CASES below.
Their expectations come from the spec text / from closed forms and were written down BEFORE their first run; a copy
of this file as it was before that run is kept in results/step1_prepare/harden_tests/expectations_before_first_run/.
  mode 'harden'     : the swept OFFICIAL contour (target/base_contour.json, taper lift_clip) with one of the sceptic's
                      attacks, run in this process; expectation = verdict words, ids that must / must not fail,
                      value ranges of judged and report-only checks
  mode 'subprocess' : a test script is started as its own Blender process; expectation = exit code, verdict in
                      metrics.json, RUNNING marker gone, stale files renamed
No pre-existing expectation, tolerance or threshold was changed.

This file is also a builder script for the stand-alone tests (builder protocol of common_test.py):
  --build-script tests/selfcheck_tests.py --build-func build_case --build-arg case=hem_lift_2pctH
  --build-script tests/selfcheck_tests.py --build-func build_attack_case --build-arg attack=wide_low:5:1.9

Output: results/<YYYYMMDD_HHMMSS>_selfcheck/ selfcheck_report.json, selfcheck_table.md and one
sub-directory per (case, test) with the usual metrics.json / images.
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

PCT = 100.0 / 66.0 / 100.0            # 1 % of image height in H units (frame_h / 100)
N_SHORT, N_LONG = 31, 121             # frames: shape / mesh cases use the short build, motion cases the long one
JUMP_FRAME = 40

# ------------------------------------------------------------------------------------ the cases
# 'tests': which test scripts are run on the build.  Expectations are for the 'spec' tier; 'relaxed' lists
# the expectation for the 'user_relaxed_5pct' tier (None = same as spec).
# REPORT-ONLY numbers (no thresholds) are checked separately from the failing sets ('expect_W', 'expect_report'; added
# 2026-09-20 with the report-only metrics, written down BEFORE their first run):
#   expect_W {'factor': k} : the fixture is scaled by k in X about X = 0 = its crest plumb line, so every horizontal
#       distance from the crest plumb line scales by exactly k.  The W rows listed in W_KEYS_EXACT (section width at
#       Z = 0.75 H, front / back distance from the crest plumb line, overhang o, cavity depth) must therefore read
#       (k - 1) * 100 % +- W_TOL_PCT against the unscaled base contour, through the mesh + silhouette AND on the
#       section polyline.  The area must grow by MORE than 0 and by LESS than (k - 1) * 100 %: the part right of the
#       crest scales by k, the part left of it is cut by the left frame edge.  k = 1 (baseline): all within +-W_TOL_PCT.
#   expect_report {check id: (op, value)} : report-only values of test_motion (backlog-definition variants).
W_KEYS_EXACT = ("z75.width_full_H", "z75.front_from_crest_H", "z75.back_from_crest_H", "z50.back_from_crest_H", "o_H", "cavity_depth_H")
W_KEY_AREA = "area_above_still_water_H2"
W_TOL_PCT = 0.3                       # percentage points; measurement error of the pipeline 0.016 % of image height = 0.07 % of o

CASES = [
    {"name": "baseline", "n_frames": N_LONG, "defect": "none (unmodified fixture, 121 frames)",
     # backlog readings on the unmodified fixture: smooth motion -> d(k) <= 3 x median of its neighbours; the shape keys hold
     # the final pose -> no movement over the 10 s hold
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.0},
                         "expect_verdict": {"spec": "PASS", "user_relaxed_5pct": "PASS"}},
               "motion": {"mode": "exact", "must_fail": [],
                          "expect_report": {"M6.backlog_jump_ratio": ("<=", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}},
               "mesh": {"mode": "exact", "must_fail": []}}},
    # crest moved by 3 % of image height in X by a smooth Gaussian X-displacement (sigma 6 % of arc length, final frame
    # only).  Z is untouched, so the material crest point moves by exactly 3 %.  The normal deviation is
    # shift * sin(slope) * weight <= ~0.8 % near the crest -> S7 stays inside 1 % / 2 %.  3 % > 2 % but < 5 %.
    # MEASURED (run 20260920_064705): the +3 % case reads S1.dx = 2.43 % through the mesh but 3.08 % on the single
    # section.  Cause: the fixture's 'clip' taper clamps X at the deepest point's X (0.0178 H); the shifted crest
    # (0.045 H) lies to the RIGHT of it, so the tapered end rows pile full-height points leftwards and the UNION
    # silhouette gets a wider, left-shifted top.  The silhouette is measured correctly; the single-section
    # prediction does not model the union.  The -3 % case moves the crest away from the clip line (added afterwards).
    {"name": "crest_shift_x_3pct", "n_frames": N_SHORT, "defect": "crest shifted +3 % of image height in X (smooth, local)",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dx_pct_h"], "relaxed": []}}},
    {"name": "crest_shift_x_minus3pct", "n_frames": N_SHORT, "defect": "crest shifted -3 % of image height in X (smooth, local)",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dx_pct_h"], "relaxed": []}}},
    # crest raised +3 % of image height by a Gaussian Z-bump (sigma 6 %): S1.dz and S3 see +3 %; more than 5 % of the
    # back / head samples then deviate by > 2 %, so S7 p95 of those segments is expected as well (analytic prediction).
    {"name": "crest_raise_z_3pct", "n_frames": N_SHORT, "defect": "crest raised +3 % of image height (smooth bump)",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S1.dz_pct_h", "S3.height_err_pct_h"], "relaxed": []}}},
    # whole profile scaled in X about the crest plumb line (all frames).  A-priori estimate: normal deviation of the
    # back = 0.05 * |X| * sin(slope) = 0.5 .. 1.2 % -> mean about 0.8 %: S7 is NOT expected to fail at 5 %.  The exact
    # expectation is the analytic prediction; the 10 % case shows where the tests start to react.
    {"name": "widen_x_5pct", "n_frames": N_SHORT, "defect": "profile widened 5 % in X about the crest plumb line",
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.05}}}},
    # added 2026-09-20 (report-only width metrics).  must_fail is what the widening sweep of run 20260920_065550 measured
    # at 1.08 (S7 back mean 1.19 % > 1 %; nothing in the 5 % tier); the spec tier reacts only weakly, the W numbers must
    # read +8 %.
    {"name": "widen_x_8pct", "n_frames": N_SHORT, "defect": "profile widened 8 % in X about the crest plumb line",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S7.back.mean_dev_pct_h"], "relaxed": [], "expect_W": {"factor": 1.08}}}},
    {"name": "widen_x_10pct", "n_frames": N_SHORT, "defect": "profile widened 10 % in X about the crest plumb line",
     "tests": {"shape": {"mode": "analytic", "must_fail": [], "expect_W": {"factor": 1.10}}}},
    # tent-shaped bump (height 1.2 %, half width 3 samples = 2.3 % of image height) in the middle of the straight
    # 47-degree part of the back, final frame only: tangent turns by about 27 / 55 / 27 deg -> S8 fails; after the
    # steepest point the slope drops and rises again by about 27 deg -> S4 'flattens towards the crest' fails.
    # Height 1.2 % < 2 % and the bump is short -> S7 must NOT fail.
    {"name": "back_kink", "n_frames": N_SHORT, "defect": "kink (tent 1.2 % high, 4.6 % wide) inserted in the back",
     "tests": {"shape": {"mode": "analytic", "must_fail": ["S8.max_tangent_diff_deg", "S4.flattens_towards_crest"], "relaxed": None}}},
    # frame 40 of 121 only: the whole mesh is shifted by +0.3 H in X and jumps back on frame 41.  Z is untouched
    # (h, theta unchanged) -> only M6 may fail.
    # backlog reading: the jump out (39->40) and back (40->41) are each ~0.3 H against neighbours of a few 1e-3 H; with 2
    # neighbours on each side the median is NOT pulled up by the second jump -> ratio far above 3.
    {"name": "frame_jump", "n_frames": N_LONG, "defect": "whole wave shifted by 0.3 H in X on frame %d only" % JUMP_FRAME,
     "tests": {"motion": {"mode": "exact", "must_fail": ["M6.jump_ratio"], "relaxed": None,
                          "expect_report": {"M6.backlog_jump_ratio": (">", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}}}},
    # the animation runs only to t = 0.9 of the fixture's motion: it ends in the middle of the curl-in, still moving.
    # backlog reading: the cut itself lies inside the excluded ease-to-stop window -> M6_backlog stays <= 3; after the cut
    # the shape keys hold the pose -> no movement over the hold.
    {"name": "abrupt_stop", "n_frames": N_LONG, "defect": "animation cut at 90 % of the motion (stops while still moving)",
     "tests": {"motion": {"mode": "exact", "must_fail": ["M5.stop_speed_ratio"], "relaxed": None,
                          "expect_report": {"M6.backlog_jump_ratio": ("<=", 3.0), "M5.backlog_hold_max_disp_pct_h": ("<=", 0.2)}}}},
    # all boundary vertices raised by 2 % of H on every frame.  The front face reaches the water level before the
    # lifted last column, so the CAM_print contour metrics are not involved; only G2 may fail.
    {"name": "hem_lift_2pctH", "n_frames": N_SHORT, "defect": "mesh boundary (hem) lifted by 2 % of H on all frames",
     "tests": {"mesh": {"mode": "exact", "must_fail": ["G2.hem_step_pct_H"], "relaxed": None}}},
    # final frame: a dimple pushed from the top side of the head through its underside (central rows).  Site and
    # depth come from a ray test on the profile (fold_site): depth = measured head thickness + 0.08 H.  Topology,
    # hem and rim are untouched -> only G4 may fail.  HISTORY: the first design (F2 mid-point, fixed depth 0.25 H)
    # was not a fold at all - the head root is solid there - and G4 correctly reported 0; the expectation below
    # was NOT changed, the defect was.
    {"name": "self_fold", "n_frames": N_SHORT, "defect": "top side of the head pushed through its underside (final frame)",
     "tests": {"mesh": {"mode": "exact", "must_fail": ["G4.n_self_intersections"], "relaxed": None}}},
    # added 2026-09-20 (target / model segmented the same way).  The MODEL is the unmodified fixture; the TARGET json is a copy of
    # synthetic_contour.json whose head / inner_arc joint is moved 40 samples (80 px = 3.1 % of image height) back along the top
    # side of the head - the geometry of the contour is unchanged.  The library detects the tip at the right-most point, 3.1 %
    # away from the json joint (> 0.2 %): the run must come out INVALID (validity not ok), not PASS and not FAIL.  The S5 / S7
    # numbers of such a run compare different stretches; which of them fail is a side effect (mode at_least).
    {"name": "target_joint_shifted", "n_frames": N_SHORT, "contour_mod": "tip_joint_shift_40",
     "defect": "TARGET json: head / inner_arc joint moved 3.1 % up the head (model = unmodified fixture)",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["VALIDITY"],
                         "expect_verdict": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}}}},
    # negative demos of the fixture itself (docs/measurement_definitions.md 1.1)
    {"name": "taper_zscale", "n_frames": N_SHORT, "taper": "zscale", "defect": "end sections block the cavity (taper = zscale)",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["S2.dist_pct_h", "S5.pos_pct_h", "S5.dir_deg", "S6.body_rightmost_left_pct",
                                                           "S7.head.mean_dev_pct_h", "S7.inner_arc.mean_dev_pct_h"]}}},
    {"name": "taper_none", "n_frames": N_SHORT, "taper": "none", "defect": "pure extrusion: the sheet has no projected area (taper = none)",
     "tests": {"shape": {"mode": "at_least", "must_fail": ["VALIDITY"],
                         "expect_verdict": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}}}},
]
WIDEN_SWEEP = [1.02, 1.05, 1.08, 1.10, 1.12, 1.15, 1.20]

# ------------------------------------------------------------------------------------ hardening cases (2026-09-20)
# EXPECTATIONS WRITTEN BEFORE THE FIRST RUN OF EACH CASE.  Sources: the spec text (great_wave_blender_prompt.md), closed
# forms, and - where a number is quoted - the MEASUREMENT-LAYER record docs/records/step1_harden_measure.md (measured with
# the gw library only, not through these test scripts).  The attacks are the sceptic's (results/step1_prepare/verify_tests/
# scripts/attack_common.py); the two section attacks used here are ported below (apply_attack) so that tests/ does not
# depend on a results/ directory.
# INHERITED: the official base contour fails S4.flattens_towards_crest against itself (docs/records/step1_proof.md), so every
# sweep of it fails that check; it is part of every expectation below and says nothing about the attack.
# Expectation keys:  verdict_base {tier: word} ; must_fail / must_not_fail [ids] (spec tier; 'VALIDITY' = validity not ok) ;
#   failing_equals [ids] (spec tier, exact) ; values {check id: (op, ref[, ref2])} on c['measured'], ops < <= > >= == between ;
#   diff_pct {check id: (lo, hi)} on c['difference']['pct_of_target'] ; validity_note_contains [text] ;
#   vs_clean {check id: (op, delta)}: measured minus the same check of case 'official_clean' ; suffix True/False.
INHERITED = ["S4.flattens_towards_crest"]
HARDEN_CASES = [
    # reproduction of the proof's base run: only the inherited check fails; nothing detached, nothing dropped, the front face
    # reaches Z = 0, S3 from the model's own trough = S3 from Z = 0 (the completed trough of the official contour is at Z = 0).
    {"name": "official_clean", "kind": "harden", "test": "shape", "attack": "none",
     "defect": "none: official base contour swept with lift_clip (reference of the attack cases)",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "failing_equals": INHERITED, "suffix": False,
                "values": {"T.n_removed_islands": ("==", 0), "T.n_nonfinite_vertices": ("==", 0), "T.n_dropped_triangles": ("==", 0),
                           "T.reached_still_water": ("==", 1), "S3.from_model_trough.height_err_pct_h": ("between", -0.2, 0.2),
                           "S3.height_err_pct_h": ("between", -0.2, 0.2)},
                "diff_pct": {"W.own_h.aspect_ratio_h75": (-0.5, 0.5), "W.own_h.o_over_h": (-0.5, 0.5), "W.own_h.cavity_depth_over_h": (-0.5, 0.5)}}},
    # THE USER'S ORIGINAL COMPLAINT ('too wide, not high enough'): X scaled by 1.05 about the crest plumb line, Z scaled so that
    # the crest is 1.9 % of image height lower.  Spec tolerances: S1.dz / S3 = -1.87 (< 2), tip moves 1.9 % (< 2), and on the
    # back 'wider' pushes the contour out while 'lower' pushes it in, so S7 stays inside 1 % / 2 %: the JUDGED checks are
    # expected to stay as in the clean run (the hole the sceptic found; it needs a threshold the user has not given).  What MUST
    # show it are the report-only numbers: every length / own h scales by 1.05 / (1 - 1.9 * 0.0151515 / 1.0006) = 1.0811, i.e.
    # +8.1 % (closed form; +-1.1 for the landmark noise of the clean run +0.2 / -0.2).  Signed S7 (a-priori geometry: near the
    # crest the lowering (1.7 % x cos 45) beats the widening (0.7 % x sin 45) -> back and top of the head INSIDE the target = negative;
    # the cavity roof moves down and the belly to the right -> inner arc OUTSIDE the target body = positive), sizes 0.2 .. 1.5 %.
    {"name": "wide_low_5_1p9", "kind": "harden", "test": "shape", "attack": "wide_low:5:1.9",
     "defect": "5 % wider AND 1.9 % lower (aspect ratio +8 %): the user's old complaint",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "must_fail": INHERITED, "must_not_fail": ["VALIDITY"], "suffix": False,
                "values": {"S3.height_err_pct_h": ("between", -2.0, -1.7), "S3.from_model_trough.height_err_pct_h": ("between", -2.0, -1.7),
                           "S7.back.signed_mean_dev_pct_h": ("between", -1.5, -0.2), "S7.head.signed_mean_dev_pct_h": ("between", -1.5, -0.2),
                           "S7.inner_arc.signed_mean_dev_pct_h": ("between", 0.2, 1.5)},
                "diff_pct": {"W.own_h.aspect_ratio_h75": (7.0, 9.2), "W.own_h.o_over_h": (7.0, 9.4), "W.own_h.cavity_depth_over_h": (7.0, 9.2),
                             "W.own_h.h75.width_full_over_h": (7.0, 9.2)},
                "document": ["S7.back.mean_dev_pct_h", "S7.back.p95_dev_pct_h", "S7.head.mean_dev_pct_h", "S7.head.p95_dev_pct_h", "S5.pos_pct_h",
                             "S1.dz_pct_h", "W.z75.width_full_H"]}},
    # the sea in front of the wave stands 3 % of image height above Z = 0 (second object 'Floor').  Spec S3 = 'height from the
    # TROUGH to the crest' = 63 %, 3 points short (tolerance 2): must be INVALID or fail S3.  Expected: BOTH - the front face
    # never reaches the still water (validity) and S3.from_model_trough = +0.03 - 3.0 = -2.97 fails the spec tier (passes 5 %);
    # S3 from Z = 0 stays at +0.03.
    {"name": "floor_raised_3pct", "kind": "harden", "test": "shape", "attack": "none", "floor_pct": 3.0, "objects": "SweptAttack,Floor",
     "defect": "sea in front of the wave raised by 3 % of image height (trough-to-crest height 63 %, not 66 %)",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY", "S3.from_model_trough.height_err_pct_h"],
                "must_not_fail": ["S3.height_err_pct_h"], "suffix": False, "validity_note_contains": ["NEVER REACHES THE STILL WATER"],
                "values": {"S3.from_model_trough.height_err_pct_h": ("between", -3.15, -2.8), "S3.height_err_pct_h": ("between", -0.2, 0.2),
                           "T.reached_still_water": ("==", 0)}}},
    # a detached quad (0.13 H x 0.15 H) stands in the middle of the cavity opening.  Spec section 5 note 2: a cavity blocked by
    # something must make S2 / S7 fail; the contour tracer removes detached components, so every S value is that of the clean
    # run -> the run must be INVALID and must NAME the component (bbox X 0.17..0.30 H, Z 0.22..0.37 H).
    {"name": "island_in_cavity", "kind": "harden", "test": "shape", "attack": "none", "island": 1, "objects": "SweptAttack,Island",
     "defect": "detached object standing in the cavity (removed by the contour tracer)",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["DETACHED SILHOUETTE COMPONENT", "X 0.17", "Z 0.22"],
                "values": {"T.n_removed_islands": ("==", 1)}}},
    # one vertex of the final shape key is NaN (a realistic generator bug, 0 / 0).  Blender propagates it, the library drops the
    # triangles that use it and the metrics are bit-identical to the clean run -> must be INVALID in test_shape AND test_mesh.
    {"name": "nan_vertex", "kind": "harden", "test": "shape", "attack": "none", "nan_vertex": 1,
     "defect": "one NaN vertex on the final frame",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": INHERITED + ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["NON-FINITE GEOMETRY"],
                "values": {"T.n_nonfinite_vertices": ("==", 1), "T.n_dropped_triangles": (">=", 1)}}},
    {"name": "nan_vertex_mesh", "kind": "harden", "test": "mesh", "attack": "none", "nan_vertex": 1, "mesh_skip": ("G5",),
     "defect": "one NaN vertex on the final frame (test_mesh; G5 skipped: the verdict must be INVALID whatever else happens)",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["NON-FINITE GEOMETRY"], "values": {"T.n_frames_nonfinite_geometry": (">=", 1)}}},
    # KNOWN LIMIT, pinned: the same island, but the second object is NOT listed in --object (the builder returns only the wave).
    # The test cannot see an object it was not given, so every S value and the verdict are those of the clean run.  What must
    # happen: it is COUNTED and NAMED (T.n_untested_mesh_objects = 1, a note with its name), so that the reader of the summary sees it.
    {"name": "island_not_listed", "kind": "harden", "test": "shape", "attack": "none", "island": 1,
     "defect": "detached object in the cavity that is not listed in --object (known limit: reported, no verdict)",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "failing_equals": INHERITED, "suffix": False,
                "validity_note_contains": ["NOT tested: Island"], "values": {"T.n_untested_mesh_objects": ("==", 1), "T.n_removed_islands": ("==", 0)}}},
    # a 17 deg kink of the back, placed exactly BETWEEN two of the 4 sample phases of S8.  Spec S8: tangent difference of
    # neighbouring samples (spacing 1 %) < 15 deg -> a 17 deg crease 'should' fail.  A-priori: chord tangents dilute a kink that
    # lies 1/8 spacing from the nearest sample to 17 x 0.875 = 14.9 < 15, so the JUDGED S8 is expected NOT to fail (documented
    # blind spot of a sampled definition; the judged definition is the spec's and was not changed).  What must show the kink is the
    # report-only vertex-window turn of the back: at least 15.5 deg and at least 2.5 deg above the clean run.
    {"name": "back_kink_17_worst", "kind": "harden", "test": "shape", "attack": "back_kink:17:worst",
     "defect": "17 deg kink in the back, placed between the S8 sample phases",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "must_fail": INHERITED, "must_not_fail": ["VALIDITY"], "suffix": False,
                "values": {"S8.max_tangent_diff_deg": ("between", 12.0, 15.0), "S8.back.vertex_window_turn_deg": (">=", 15.5)},
                "vs_clean": {"S8.back.vertex_window_turn_deg": (">=", 2.5)},
                "document": ["S8.max_tangent_diff_deg", "S8.max_vertex_window_turn_deg", "S8.back.vertex_window_turn_deg", "S7.back.p95_dev_pct_h"]}},
    # the same two defects through test_motion (2-frame sweep of the official contour + 3 hold frames; the M checks themselves are
    # meaningless on 2 frames and are not part of the expectation): a NaN vertex on the final frame / a detached object on every
    # frame must make the motion test INVALID and must be counted (T.n_frames_*).
    {"name": "nan_vertex_motion", "kind": "harden", "test": "motion", "attack": "none", "nan_vertex": 1, "extra_args": ["--backlog-hold-s", "0"],
     "defect": "one NaN vertex on the final frame (test_motion)",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["NON-FINITE GEOMETRY"], "values": {"T.n_frames_nonfinite_geometry": (">=", 1), "T.n_frames_with_islands": ("==", 0)}}},
    {"name": "island_motion", "kind": "harden", "test": "motion", "attack": "none", "island": 1, "objects": "SweptAttack,Island", "extra_args": ["--backlog-hold-s", "0"],
     "defect": "detached object in front of the wave on every frame (test_motion)",
     "expect": {"verdict_base": {"spec": "INVALID", "user_relaxed_5pct": "INVALID"}, "must_fail": ["VALIDITY"], "suffix": False,
                "validity_note_contains": ["DETACHED SILHOUETTE COMPONENT"], "values": {"T.n_frames_with_islands": (">=", 2), "T.n_frames_nonfinite_geometry": ("==", 0)}}},
    # the settings back door: the sceptic made the 0.3 H frame jump pass M6 with --set jump_floor_frac_of_vmax=1.0 and nothing in
    # the result said so.  Expected now: the verdict carries the suffix in both tiers, the entry is listed with its source, and the
    # exit code of such a run is 1 (common_test.exit_code).  The base verdict is expected to be PASS - that IS the back door.
    {"name": "settings_backdoor_frame_jump", "kind": "harden", "test": "motion", "fixture_case": "frame_jump", "n_frames": N_LONG,
     "extra_args": ["--set", "jump_floor_frac_of_vmax=1.0"],
     "defect": "frame jump 0.3 H hidden by --set jump_floor_frac_of_vmax=1.0",
     "expect": {"verdict_base": {"spec": "PASS", "user_relaxed_5pct": "PASS"}, "suffix": True, "exit_code_spec": 1,
                "non_default_names": ["jump_floor_frac_of_vmax"], "must_not_fail": ["M6.jump_ratio"]}},
    # --hold-frames 0: 'the shape does not change after the stop' is not measured.  Must be NOT_MEASURABLE (-> FAIL), never a
    # silent 0 = PASS; and --hold-frames differs from the documented 3 -> suffix.  (31 frames: M6 fails on this short build, known.)
    {"name": "no_hold_frames", "kind": "harden", "test": "motion", "fixture_case": "baseline", "n_frames": N_SHORT, "extra_args": ["--hold-frames", "0"],
     "defect": "motion test without hold frames",
     "expect": {"verdict_base": {"spec": "FAIL", "user_relaxed_5pct": "FAIL"}, "suffix": True, "exit_code_spec": 1,
                "not_measurable": ["M5.post_stop_max_disp_H"], "non_default_names": ["hold_frames"]}},
    # ---- unit cases (pure python, added AFTER the first expectation copy; second copy: selfcheck_tests_before_unit_cases.py).
    # Expectations = the verdict vocabulary of the hardening task, word for word: PASS only if at least one judged check exists
    # AND every expected check was judged; otherwise INCOMPLETE; NOT_MEASURABLE counts as failed; validity -> INVALID; a raising
    # sub-test -> ERROR (exit 2); a changed verdict-relevant setting -> suffix and exit code 1.  The table is in unit_verdict_vocabulary().
    {"name": "unit_verdict_vocabulary", "kind": "unit", "func": "unit_verdict_vocabulary", "defect": "common_test.summarize / exit_code on hand-made check lists",
     "expect": {}},
    # unknown --set name -> ValueError; the defaults of the code agree with thresholds.json 'interpretations' (audit ok, nothing
    # unlisted); --set of a verdict-relevant setting and an override of a verdict-relevant measure parameter are listed with their
    # source; a report-only setting / parameter is listed separately and does NOT flag the verdict.
    {"name": "unit_settings_audit", "kind": "unit", "func": "unit_settings_audit", "defect": "common_test.get_settings / settings_audit", "expect": {}},
    # params.json is not edited: gw.paths.param is replaced for the duration of the case.  Expected: a 'test_settings' entry of
    # params.json with a verdict-relevant value is listed with source 'params.json test_settings'; an unknown name in it and a
    # 'test_settings' entry that is not an object raise (ValueError / TypeError); an ABSENT entry is fine (defaults, nothing listed).
    {"name": "unit_settings_from_params_json", "kind": "unit", "func": "unit_settings_from_params_json",
     "defect": "params.json 'test_settings' (simulated): listed / unknown name / wrong type", "expect": {}},
    # ---- own Blender processes: exit codes and files
    # every G test skipped -> zero judged checks: INCOMPLETE, exit code 1 (the sceptic got PASS / 0)
    {"name": "zero_checks_mesh_skip_all", "kind": "subprocess", "script": "test_mesh.py", "defect": "test_mesh with every G test skipped (zero judged checks)",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--skip", "G1,G2,G3,G4,G5"],
     "expect": {"exit_code": 1, "verdict_base": {"spec": "INCOMPLETE", "user_relaxed_5pct": "INCOMPLETE"}, "n_judged": 0, "running_marker": False}},
    # a typo in --only used to select nothing and came out as PASS
    {"name": "run_all_only_typo", "kind": "subprocess", "script": "run_all.py", "defect": "run_all --only shpae (typo)",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--only", "shpae"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "ValueError", "running_marker": False}},
    {"name": "mesh_skip_unknown_name", "kind": "subprocess", "script": "test_mesh.py", "defect": "test_mesh --skip G9 (unknown name)",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--skip", "G9"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "ValueError", "running_marker": False}},
    # one sub-test of run_all raises (test_shape: the --contour file does not exist = the sceptic's 'stale_demo' crash).  Expected:
    # the other sub-tests still run, shape = ERROR with its own metrics.json, the total is ERROR, exit code 2, no RUNNING marker.
    {"name": "run_all_subtest_crash", "kind": "subprocess", "script": "run_all.py", "defect": "run_all: test_shape raises (missing --contour file), the other sub-tests must still run",
     "argv": ["--build-script", "{fixture}", "--build-func", "build_object", "--build-arg", "n_frames=5", "--contour", "does_not_exist.json", "--skip", "G5"],
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "running_marker": False,
                "sub_test_verdict_base": {"shape": "ERROR"}, "sub_tests_present": ["shape", "motion", "mesh"]}},
    # a build script that raises, into a run directory that already holds a PASS result of an earlier run (the sceptic's
    # 'stale_demo').  Expected: exit code 2, metrics.json = ERROR with the traceback, the old files renamed to stale_*, no RUNNING
    # marker left.  Run twice: with and WITHOUT --python-exit-code 1 on the Blender command line (the exception is caught by
    # guarded_main, so the exit code must not depend on that flag).
    {"name": "crashing_build_script", "kind": "subprocess", "script": "test_shape.py", "defect": "build script raises; run directory holds a stale PASS result",
     "argv": ["--build-script", "{this}", "--build-func", "build_crash"], "seed_stale_pass": True,
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "RuntimeError",
                "error_message_contains": "deliberate crash", "running_marker": False, "stale_files": ["metrics.json", "summary.md"]}},
    {"name": "crashing_build_script_no_exit_code_flag", "kind": "subprocess", "script": "test_shape.py", "python_exit_code_flag": False,
     "defect": "same, Blender started WITHOUT --python-exit-code 1",
     "argv": ["--build-script", "{this}", "--build-func", "build_crash"], "seed_stale_pass": True,
     "expect": {"exit_code": 2, "verdict_base": {"spec": "ERROR", "user_relaxed_5pct": "ERROR"}, "error_type": "RuntimeError",
                "error_message_contains": "deliberate crash", "running_marker": False, "stale_files": ["metrics.json", "summary.md"]}},
]


# ------------------------------------------------------------------------------------ defects
def _arc_s(pts):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])))])


def perturb_profile(case, pts, ids, info, is_final):
    """Defects that act on the section profile (H units).  -> (pts, info)"""
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
    """Distance from pts[i] along n_in to the first later part of the polyline (None = the ray never
    meets it, i.e. there is solid body behind the surface, not a second sheet)."""
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
    """Where the self_fold defect is applied: the top-side sample of the head (piece F2) FARTHEST from the rim
    whose inward-normal ray still meets the underside within 0.10 H (measured on the profile, not assumed).
    First design (fixed F2 mid-point, depth 0.25 H) was NOT a fold: that ray meets no underside, the dimple
    sank into the solid head root and G4 correctly reported 0 (see docs/records/step1_tests.md).
    -> (u index, inward unit normal, measured head thickness along it in H)"""
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
    """Builder (protocol of common_test.py): the synthetic fixture with one deliberate defect."""
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
    """Rotate the tangent of edges i0 .. i1-1 by delta (rad, per edge), re-integrate from pts[i0] and spread the closing
    error linearly (ported from the sceptic's attack_common.py)."""
    seg = np.diff(pts[i0:i1 + 1], axis=0)
    ds = np.hypot(seg[:, 0], seg[:, 1])
    psi = np.arctan2(seg[:, 1], seg[:, 0]) + delta
    q = pts[i0] + np.concatenate([[[0.0, 0.0]], np.cumsum(np.stack([ds * np.cos(psi), ds * np.sin(psi)], axis=1), axis=0)])
    err = q[-1] - pts[i1]
    ss = np.concatenate([[0.0], np.cumsum(ds)])
    q -= err[None, :] * (ss / ss[-1])[:, None]
    return q, float(math.hypot(err[0], err[1]))


def apply_attack(pts, attack, x_left=None):
    """The sceptic's section attacks that the hardening cases use (results/step1_prepare/verify_tests/scripts/
    attack_common.py, ported 1:1):  'none' | 'wide_low:<pct wider>:<pct of image height lower>' | 'back_kink:<deg>:worst'.
    -> (pts, info)"""
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
            raise ValueError("only back_kink:<deg>:worst is ported")
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
        raise ValueError("unknown attack %r" % attack)
    return pts, info


def make_attack_wave_class(attack):
    class AttackWave(msw.SyntheticWave):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            if self._final_json_pts is None:
                raise ValueError("the attacks need the profile-json mode of the fixture")
            self._final_json_pts, self.attack_info = apply_attack(self._final_json_pts, attack)
            pts, _ids, _info = self.profile(msw.FRAME_START)
            self.n_u = pts.shape[0]
            self.faces = msw.grid_faces(self.n_u, self.n_v)
            self.triangles = msw.grid_triangles(self.n_u, self.n_v)

    return AttackWave


def build_attack_case(scene, attack="none", island=0, floor_pct=0.0, nan_vertex=0, n_frames=2, H=11.0, taper="lift_clip"):
    """Builder of the hardening cases: target/base_contour.json swept with the fixture (taper lift_clip, the proof's
    set-up), optionally with a section attack and / or
      island=1     a second, detached object 'Island' (camera-facing quad X 0.17..0.30 H, Z 0.22..0.37 H) in the cavity opening
      floor_pct=p  a third object 'Floor': slab X 0.10 H .. 1.6 H, Z -0.02 H .. p % of image height (the sea in front of the wave
                   stands p % above Z = 0)
      nan_vertex=1 one vertex of the centre row (middle of the back) is NaN in the final shape key
    Pass --object SweptAttack,Island / SweptAttack,Floor so that the extra object is part of the silhouette."""
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
    """Builder that raises (hardening case 'crashing_build_script')."""
    raise RuntimeError("deliberate crash of the build script (selfcheck case crashing_build_script)")


# ------------------------------------------------------------------------------------ analytic prediction (shape)
def analytic_contour(case, n_frames, F):
    """The defective FINAL profile as the contour CAM_print would show: clipped at the left frame edge and
    continued along the still water to the right frame edge.  No mesh, no raster, no Blender."""
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
    """Target json of a case: the fixture's own analytic contour, or a deliberately mis-segmented copy of it
    (written into the run directory; tests/fixtures/synthetic_contour.json itself is never touched)."""
    mod = case.get("contour_mod")
    if not mod:
        return msw.SYNTHETIC_CONTOUR_JSON
    if not mod.startswith("tip_joint_shift_"):
        raise ValueError("unknown contour_mod %r" % mod)
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
    """INFORMATION: M6_backlog of a finished test_motion result recomputed with another neighbour window
    (shows why the default is 2 pairs on each side and not 1)."""
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
    """Largest |pipeline - single-section prediction| over the judged numeric checks, per unit.  REPORTED only:
    equal failing sets can hide a numeric disagreement (found on crest_shift_x_3pct)."""
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
    """Do the REPORT-ONLY size metrics show a widening by `factor`?  (expectation: comment above CASES)
    -> (ok, {name: {expected_pct, pipeline_pct, section_pct}}, [problems])"""
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
    """Compare a test result with a HARDEN_CASES expectation.  -> (problems [text], observed {..})"""
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
            problems.append("verdict suffix '%s' present = %s, expected %s" % (ct.NON_DEFAULT_SUFFIX.strip(), has, exp["suffix"]))
    failing = ct.failing_ids(res, "spec")
    obs["failing_spec"] = failing
    for cid in exp.get("must_fail", []):
        if cid not in failing:
            problems.append("%s does not fail (spec tier)" % cid)
    for cid in exp.get("must_not_fail", []):
        if cid in failing:
            problems.append("%s fails (spec tier) but must not" % cid)
    if "failing_equals" in exp and sorted(exp["failing_equals"]) != failing:
        problems.append("failing set %s, expected exactly %s" % (failing, sorted(exp["failing_equals"])))
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
            problems.append("validity notes do not contain %r" % text)
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
            problems.append("exit code for --exit-tier spec would be %d, expected %d" % (code, exp["exit_code_spec"]))
    obs["document"] = {cid: (by.get(cid) or {}).get("measured") for cid in exp.get("document", [])}
    return problems, obs


def unit_verdict_vocabulary():
    """-> (problems, observed): summarize() / exit_code() on hand-made check lists of test_mesh (expected ids G1-G5)."""
    mk = ct.make_check
    full = [mk("G1", "n_topology_or_uv_changes", 0), mk("G2", "hem_step_pct_H", 0.0), mk("G3", "rim_thickness_pct_H", 1.0),
            mk("G4", "n_self_intersections", 0), mk("G4", "frame_step", 15), mk("G5", "rebuild_max_abs_diff_m", 0.0)]
    no_g5 = full[:-1]
    flagged = {"non_default": [{"group": "test_settings", "name": "jump_floor_frac_of_vmax", "effective": 1.0, "file_value": 0.05, "source": "--set"}], "unlisted": []}
    table = [  # name, checks, validity, audit, errors, expected verdict (both tiers), expected exit code (--exit-tier spec)
        ("every expected check judged and passing", full, True, None, None, "PASS", 0),
        ("zero checks", [], True, None, None, "INCOMPLETE", 1),
        ("only report values", [ct.report_value("G1", "max_vertex_step_H", 0.1)], True, None, None, "INCOMPLETE", 1),
        ("G5 not judged (skipped)", no_g5, True, None, None, "INCOMPLETE", 1),
        ("G5 not measurable", no_g5 + [mk("G5", "rebuild_max_abs_diff_m", None)], True, None, None, "FAIL", 1),
        ("G3 fails", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:], True, None, None, "FAIL", 1),
        ("G3 fails and G5 not judged", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:-1], True, None, None, "FAIL", 1),
        ("validity not ok, everything passing", full, False, None, None, "INVALID", 1),
        ("a sub-test raised", full, True, None, ["shape: RuntimeError: x"], "ERROR", 2),
        ("non-default verdict-relevant setting, everything passing", full, True, flagged, None, "PASS" + ct.NON_DEFAULT_SUFFIX, 1),
        ("non-default setting and a failing check", full[:2] + [mk("G3", "rim_thickness_pct_H", 9.0)] + full[3:], True, flagged, None, "FAIL" + ct.NON_DEFAULT_SUFFIX, 1),
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
        problems.append("the defaults of the code differ from tests/thresholds.json interpretations: %s" % (a0["non_default"] + a0["unlisted"]))
    S1, src1 = ct.get_settings({"jump_floor_frac_of_vmax": 1.0, "contact_sheet_step": 10}, with_sources=True)
    a1 = ct.settings_audit(S1, src1)
    names = [(d["name"], d["source"]) for d in a1["non_default"]]
    vals["--set jump_floor_frac_of_vmax=1.0"] = str(names)
    if names != [("jump_floor_frac_of_vmax", "--set")]:
        problems.append("audit of --set jump_floor_frac_of_vmax=1.0 lists %s" % names)
    if [d["name"] for d in a1["report_only_non_default"]] != ["contact_sheet_step"]:
        problems.append("report-only setting contact_sheet_step is not listed separately: %s" % a1["report_only_non_default"])
    a2 = ct.settings_audit(S0, src0, measure_params=pm.get_params({"s8_tip_exclusion_pct_h": 3.0, "width_levels_H": [0.3, 0.6]}))
    vals["override s8_tip_exclusion_pct_h=3"] = str([(d["group"], d["name"]) for d in a2["non_default"]])
    if [(d["group"], d["name"]) for d in a2["non_default"]] != [("measure_params", "s8_tip_exclusion_pct_h")]:
        problems.append("audit of the measure-parameter override lists %s" % a2["non_default"])
    if [d["name"] for d in a2["report_only_non_default"]] != ["width_levels_H"]:
        problems.append("report-only measure parameter width_levels_H is not listed separately: %s" % a2["report_only_non_default"])
    a3 = ct.settings_audit(S0, src0, effective={"hold_frames": (0, "--hold-frames"), "motion_frame_step": (2, "--frame-step")})
    got3 = sorted((d["name"], d["source"]) for d in a3["non_default"])
    vals["--hold-frames 0 --frame-step 2"] = str(got3)
    if got3 != [("hold_frames", "--hold-frames"), ("motion_frame_step", "--frame-step")]:
        problems.append("audit of the command-line replacements lists %s" % got3)
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
            problems.append("an absent test_settings entry is not the clean default case")
        vals["entry absent"] = "defaults, audit ok"
    finally:
        paths.param = real
    return problems, {"values": vals}


def run_harden_inprocess(case, parser, runners, out_dir):
    """One hardening case in this Blender process.  -> test result dict"""
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
    """One hardening case as its OWN Blender process.  -> (problems, observed)"""
    import bpy
    exp = case["expect"]
    paths.ensure_dir(out_dir)
    if case.get("seed_stale_pass"):
        fake = {"schema": ct.RESULT_SCHEMA, "test": "shape", "SEEDED_BY_SELFCHECK": "stale result of an imaginary earlier run",
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
        problems.append("exit code %s, expected %s" % (proc.returncode, exp["exit_code"]))
    mp = os.path.join(out_dir, "metrics.json")
    res = paths.read_json(mp) if os.path.isfile(mp) else None
    if res is None or res.get("SEEDED_BY_SELFCHECK"):
        problems.append("no metrics.json of THIS run in the run directory (%s)" % ("missing" if res is None else "the stale one is still in place"))
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
                problems.append("error type %s, expected %s" % ((res.get("error") or {}).get("type"), exp["error_type"]))
            if exp.get("error_message_contains") and exp["error_message_contains"] not in ((res.get("error") or {}).get("message") or ""):
                problems.append("error message does not contain %r" % exp["error_message_contains"])
            if "Traceback" not in ((res.get("error") or {}).get("traceback") or ""):
                problems.append("metrics.json has no traceback")
    files = sorted(os.listdir(out_dir))
    obs["files"] = files
    if exp.get("running_marker") is False and ct.RUNNING_MARKER in files:
        problems.append("the RUNNING marker is still in the run directory")
    for fn in exp.get("stale_files", []):
        hits = [f for f in files if f.startswith("stale_") and f.endswith("_" + fn)]
        if not hits:
            problems.append("the stale %s was not renamed to stale_*_%s" % (fn, fn))
        elif fn == "metrics.json" and not paths.read_json(os.path.join(out_dir, hits[0])).get("SEEDED_BY_SELFCHECK"):
            problems.append("stale_*_metrics.json is not the seeded file")
    return problems, obs


def main():
    import test_mesh
    import test_motion
    import test_shape
    ap = argparse.ArgumentParser(description="self-check of the great_wave tests on the synthetic fixture")
    ap.add_argument("--cases", default="", help="comma separated case names (default: all)")
    ap.add_argument("--quick", action="store_true", help="skip the fresh-process rebuild of G5 and the widening sweep")
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
        log("ERROR %s" % exc)
        log("RESULT ERROR selfcheck_tests (exit code %d)" % ct.EXIT_CODE_ERROR)
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
            problems = ["the case raised %s: %s" % (type(exc).__name__, exc)]
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
            log("widen x%.2f: spec failed = %s" % (k, pred["spec"] or "-"))
    if not rows:
        all_ok = False                                # a self-check that ran nothing is not a success
        log("ERROR no case was run")
    report = {"schema": "gw.selfcheck.v1", "created": ct.now_stamp(), "all_ok": bool(all_ok), "rows": rows, "widen_sweep": sweep,
              "fixture": {"contour": paths.norm(msw.SYNTHETIC_CONTOUR_JSON), "frames_short": N_SHORT, "frames_long": N_LONG}}
    paths.write_json(os.path.join(root, "selfcheck_report.json"), ct.jsonable(report))
    write_table(root, rows, sweep, all_ok)
    log("self-check report: %s" % root)
    bootstrap.finish(bool(all_ok), "selfcheck_tests: %d (case, test) pairs, %d mismatches"
                     % (len(rows), sum(1 for r in rows if not r["ok"])))


def write_table(root, rows, sweep, all_ok):
    L = ["# selfcheck_tests  (%s)  all_ok = %s" % (ct.now_stamp(), all_ok), "",
         "| case | defect | test | mode | must fail (spec) | analytic prediction (spec) | actual failed (spec) | actual failed (5 % tier) | key numbers | largest gap pipeline vs single section | report-only numbers | result |",
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
                ro.append("W vs base (x%.2f): " % d["factor"] + ", ".join("%s %s %%" % (k, "n/a" if v.get("pipeline_pct") is None else "%+.2f" % v["pipeline_pct"])
                                                                          for k, v in d["values"].items()) + (" -> OK" if d["ok"] else " -> **MISMATCH** " + "; ".join(d["problems"])))
            elif kind == "verdict":
                ro.append("verdict " + ", ".join("%s=%s (expected %s)" % (k, v, d["expected"][k]) for k, v in d["values"].items())
                          + (" -> OK" if d["ok"] else " -> **MISMATCH**"))
            else:
                ro.append(", ".join("%s=%s (expected %s %s)" % (k, ct._fmt(v), d["expected"][k][0], d["expected"][k][1]) for k, v in d["values"].items())
                          + ("" if d.get("backlog_jump_ratio_with_half_window_1") is None else
                             "; [info] M6_backlog with ONE neighbour pair on each side would read %s" % ct._fmt(d["backlog_jump_ratio_with_half_window_1"]))
                          + (" -> OK" if d["ok"] else " -> **MISMATCH**"))
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["case"], r["defect"], r["test"], r["mode"], ", ".join(r["must_fail_spec"]) or "-",
            "n/a" if r["predicted"] is None else (", ".join(r["predicted"]["spec"]) or "-"),
            ", ".join(r["actual"]["spec"]) or "-", ", ".join(r["actual"]["user_relaxed_5pct"]) or "-", nums or "-", gtxt,
            "<br>".join(ro) or "-", "OK" if r["ok"] else "**MISMATCH**"))
    hard = [r for r in rows if r.get("harden")]
    if hard:
        L += ["", "## hardening cases (expectations written before their first run; see HARDEN_CASES in tests/selfcheck_tests.py)", "",
              "| case | defect | test / script | verdicts | failing (spec) | observed values | problems | result |", "|---|---|---|---|---|---|---|---|"]
        for r in hard:
            o = r["harden"]["observed"]
            vals = dict(o.get("values") or {})
            vals.update({k + " [diff % of base]": v for k, v in (o.get("diff_pct") or {}).items()})
            vals.update({k + " [minus clean]": v for k, v in (o.get("vs_clean") or {}).items()})
            vals.update({k + " [documented]": v for k, v in (o.get("document") or {}).items()})
            if "exit_code" in o:
                vals["exit code"] = o["exit_code"]
            if "exit_code_spec" in o:
                vals["exit code (--exit-tier spec)"] = o["exit_code_spec"]
            if o.get("error"):
                vals["error"] = "%s: %s" % (o["error"].get("type"), o["error"].get("message"))
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r["case"], r["defect"], r["test"], "n/a" if not o.get("verdict") else ", ".join("%s=%s" % kv for kv in o["verdict"].items()),
                ", ".join(o.get("failing_spec") or []) or "-", "; ".join("%s = %s" % (k, ct._fmt(v)) for k, v in vals.items()) or "-",
                "; ".join(r["harden"]["problems"]).replace("|", "/") or "-", "OK" if r["ok"] else "**MISMATCH**"))
    if sweep:
        L += ["", "## widening sweep (analytic layer)", "",
              "W columns = REPORT-ONLY size metrics (no thresholds), difference to the base contour in % of the base value.", "",
              "| X factor | failed (spec) | failed (5 % tier) | S7 back mean / p95 | S7 head mean / p95 | S7 inner arc mean / p95 | S5 pos | W z75 width | W o | W cavity depth | W area |",
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
