# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): the comparison and whole-run videos of a DG1 calculation (py -3.10 -B). 2026-10-17 written new (Claude).
It patches the bed in memory first (g50g_common.patch_modules), so the top view's depth contours (2 / 6 / 10 / 20 m, g49_video2 from
g49_common.bed_z with the cfg bed) and every section's bed show the groove pair, and then runs flip50/g50_video.py (unchanged) - by default
through the scratch label tolerance Unity/Build/FLIP50/_scratch/video_DM1/video_D_labels_ok.py that auto_D.py used for DM1 / DM1A
(--plain: g50_video.py alone). The header's bed wording 'D19B (a laterally straight 1:10 beach)' is replaced for a cfg with a groove.
usage (after `py -3.10 -B g50g_ana.py all <run> --prev=<DM1A run>`):
  py -3.10 -B g50g_video.py all <DG1 run> [g49_video2 options] [--plain]
  py -3.10 -B g50g_video.py compare|whole <DG1 run> ...
outputs: <run>/video/<run_id>_compare.mp4, <run_id>_whole.mp4 (+ json)
"""
import os, sys, importlib.util

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50g_common as GG        # noqa: E402

GC = GG.patch_modules()
for _p in (GG.TOOLS49, GG.TOOLS50):
    if _p not in sys.path:
        sys.path.insert(0, _p)
LABELS_OK = GG.B50 + "/_scratch/video_DM1/video_D_labels_ok.py"
PLAIN = "--plain" in sys.argv
sys.argv = [a for a in sys.argv if a != "--plain"]
if not PLAIN and os.path.exists(LABELS_OK):
    _spec = importlib.util.spec_from_file_location("video_D_labels_ok_dg1", LABELS_OK)
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)                 # patches g49_video2.overlaps (label tolerance); imports g50_video
import g50_video as GVD           # noqa: E402
V2 = GVD.V2

BED_OLD = ("海底 D19B（横にまっすぐな 1:10 の浜、水深 19 m）", "海底 D19B（横にまっすぐな 1:10 の浜）")
BED_NEW = "海底 D19B に選んだ浅い溝 2 本（軸の両側、|y| 12 m で最も深く 2.1 m、x 238〜350 m。離岸流の溝の類比で測った所ではない【選び】）"


def _fix(s):
    if isinstance(s, str):
        for a in BED_OLD:
            s = s.replace(a, BED_NEW)
    return s


_orig_text_fit = V2.GV.text_fit
_orig_head = V2.Compare49.head_lines


def text_fit_g(dr, xy, s, *a, **k):
    return _orig_text_fit(dr, xy, _fix(s), *a, **k)


def head_lines_g(self):
    return tuple(_fix(s) for s in _orig_head(self))


V2.GV.text_fit = text_fit_g
V2.Compare49.head_lines = head_lines_g
V2.TOOL = "Tools/GWWaveGen/flip50g/g50g_video.py (g50_video / g49_video2 with the DG1 groove bed)"

if __name__ == "__main__":
    GG.frozen()
    V2.main()
