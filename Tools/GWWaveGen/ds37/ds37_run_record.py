# -*- coding: utf-8 -*-
"""設計37 第「流れに沿う線」部の実行の記録（ds37_run.json：コマンド、道具の版、入力と出力の SHA-256）。py -3.10 -B Tools/GWWaveGen/ds37/ds37_run_record.py"""
import glob
import hashlib
import json
import os
import platform
import sys

import cv2
import numpy as np

ROOT = 'G:/Unity/GreatWave_2026_Fresh'
OUT = ROOT + '/Unity/Build/Design/37/flowlines'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


rep = json.load(open(OUT + '/unity/ds37_render_report.json', encoding='utf-8'))
code = [ROOT + '/' + p for p in (
    'Tools/GWWaveGen/ds37/run_ds37_unity.ps1', 'Tools/GWWaveGen/ds37/ds37_flow_eval.py', 'Tools/GWWaveGen/ds37/ds37_figs.py',
    'Tools/GWWaveGen/ds37/ds37_run_record.py', 'Unity/Assets/GreatWave/Design37/Editor/DS37Render.cs',
    'Unity/Assets/GreatWave/Design37/Scripts/DS37HeadSway.cs', 'Unity/Assets/GreatWave/Design37/Shaders/DS37_Surface_Coord.shader',
    'Unity/Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity', 'Tools/GWWaveGen/ds37/ds37_fix1_check.py')]
inputs = [rep['heroSdfPath'], ROOT + '/Tools/PaintingTruth/colour/colour_truth.json', ROOT + '/Tools/PaintingTruth/colour/colour_polylines.json',
          ROOT + '/Unity/Build/Design/36/palette/unity/t28_claws/t28/render/af28r01_painting.png',
          ROOT + '/Unity/Build/Design/36/palette/unity/tstar_sym_t28_claws/tstar_sym.json']
outs = sorted(glob.glob(OUT + '/*.json') + glob.glob(OUT + '/fig/*.png') + glob.glob(OUT + '/unity/video/*.mp4') + glob.glob(OUT + '/unity/check/*.png')
              + [OUT + '/unity/ds37_render_report.json', OUT + '/unity_fix1/ds37_render_report.json', OUT + '/unity_fix1/ds37_fix1_sway_compare.json']
              + glob.glob(OUT + '/unity_fix1/video/*.mp4') + glob.glob(OUT + '/unity_fix1/check/*.png') + glob.glob(OUT + '/unity_r1_sway_defect/*.mp4'))
fix = json.load(open(OUT + '/unity_fix1/ds37_render_report.json', encoding='utf-8'))
run = {
    'number': '設計37 第「流れに沿う線」部',
    'commands': [
        'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds37/run_ds37_unity.ps1 -Method GreatWave.Design37.EditorTools.DS37Render.Render -Log run4 '
        '-Extra "-ds37Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/37/flowlines/unity"（約 1 分）',
        'py -3.10 -B Tools/GWWaveGen/ds37/ds37_flow_eval.py（約 3 分）', 'py -3.10 -B Tools/GWWaveGen/ds37/ds37_figs.py（約 30 秒）',
        'py -3.10 -B Tools/GWWaveGen/ds37/ds37_run_record.py',
        '修正1：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds37/run_ds37_unity.ps1 -Method GreatWave.Design37.EditorTools.DS37Render.Render -Log fix1 '
        '-Extra "-ds37Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/37/flowlines/unity_fix1 -ds37Skip scene,flow,flowk,h177,l191"（約 40 秒）',
        '修正1：修正前の ds37_sway_seat_formation_30fps.mp4 を unity_r1_sway_defect/ へ写し、unity_fix1/video の同じ名の動画を unity/video/ へ写した',
        '修正1：py -3.10 -B Tools/GWWaveGen/ds37/ds37_fix1_check.py（約 40 秒）'],
    'tools': {'unity': rep['unity'], 'device': rep['device'], 'graphicsApi': rep['graphicsApi'], 'python': sys.version.split()[0], 'numpy': np.__version__,
              'opencv': cv2.__version__, 'platform': platform.platform(), 'ffmpeg': 'G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe'},
    'unity_seconds': rep['secondsTotal'], 'protected_unchanged': rep['protectedUnchanged'], 'protected_files': rep['protectedFiles'],
    'fix1_unity_seconds': fix['secondsTotal'], 'fix1_protected_unchanged': fix['protectedUnchanged'],
    'fix1_note_ja': 'unity/ds37_render_report.json の videos の sway_seat_formation の SHA-256 は修正前（unity_r1_sway_defect/ に残した動画）。'
                    '今の unity/video/ds37_sway_seat_formation_30fps.mp4 は unity_fix1/ds37_render_report.json の動画と同じ。',
    'code_sha256': {rel(p): sha(p) for p in code if os.path.exists(p)},
    'inputs_sha256': {(rel(p) if p.replace('\\', '/').startswith(ROOT) else p): sha(p) for p in inputs if os.path.exists(p)},
    'outputs_sha256': {rel(p): sha(p) for p in outs if os.path.exists(p) and not p.endswith('ds37_run.json')},
    'not_kept_note_ja': 'unity/flow・flowk・sway・verts・h177・l191 の生データ（面の座標 16.6 MB × 96 枚など、Build/Design/37 の全体で約 1.8 GB）は Build の中に置いたまま（Git 対象外）。',
}
json.dump(run, open(OUT + '/ds37_run.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('run record written', len(run['outputs_sha256']))
