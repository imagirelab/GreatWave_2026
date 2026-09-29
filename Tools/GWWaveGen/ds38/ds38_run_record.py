# -*- coding: utf-8 -*-
"""設計38 第「輪郭線」部の実行の記録（ds38_run.json：コマンド、道具の版、入力と出力とコードの SHA-256）。py -3.10 -B Tools/GWWaveGen/ds38/ds38_run_record.py"""
import glob
import hashlib
import json
import os
import platform
import sys

import cv2
import numpy as np

ROOT = 'G:/Unity/GreatWave_2026_Fresh'
OUT = ROOT + '/Unity/Build/Design/38/outlines'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


def load(p):
    return json.load(open(p, encoding='utf-8'))


rep = load(OUT + '/unity/ds38_render_report.json')
code = [ROOT + '/' + p for p in (
    'Tools/GWWaveGen/ds38/run_ds38_unity.ps1', 'Tools/GWWaveGen/ds38/ds38_line_eval.py', 'Tools/GWWaveGen/ds38/ds38_figs.py',
    'Tools/GWWaveGen/ds38/ds38_run_record.py', 'Tools/GWWaveGen/ds38/ds38_fix_eval.py', 'Tools/GWWaveGen/ds38/ds38_fixround_figs.py',
    'Tools/GWWaveGen/ds38/ds38_summary.py', 'Unity/Assets/GreatWave/Design38/Editor/DS38Render.cs',
    'Unity/Assets/GreatWave/Design38/Scripts/DS38SheetOutline.cs', 'Unity/Assets/GreatWave/Design38/Scripts/DS38ClawOutline.cs',
    'Unity/Assets/GreatWave/Design38/Scripts/DS38LineGlobals.cs', 'Unity/Assets/GreatWave/Design38/Shaders/DS38LineCommon.cginc',
    'Unity/Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader', 'Unity/Assets/GreatWave/Design38/Shaders/DS38_Outline_Mesh.shader',
    'Unity/Assets/GreatWave/Design38/Materials/DS38_Outline_hero.mat', 'Unity/Assets/GreatWave/Design38/Materials/DS38_Outline_near.mat',
    'Unity/Assets/GreatWave/Design38/Materials/DS38_Outline_claws.mat', 'Unity/Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity')]
inputs = [ROOT + '/Unity/Build/Design/36/palette/unity/t28_claws/t28/render/af28r01_painting.png',
          ROOT + '/Unity/Build/Design/36/palette/unity/t28_claws/t28/render/af28r01_line_ids.png',
          ROOT + '/Unity/Build/Design/36/palette/unity/ds30_tstar_regress.json',
          ROOT + '/Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin', ROOT + '/Unity/Build/Design/33/claws/ds33_claw_frames_f32.bin']
outs = sorted(glob.glob(OUT + '/*.json') + glob.glob(OUT + '/fig/*.png') + glob.glob(OUT + '/unity/video/*.mp4')
              + glob.glob(OUT + '/unity/t28_*/t28/render/*.png') + [OUT + '/unity/ds38_render_report.json', OUT + '/unity/ds30_tstar_regress.json',
                                                                     OUT + '/unity/prep/ds38_hero_linemask_f32.bin']
              + glob.glob(OUT + '/unity/l191/*.bin') + glob.glob(OUT + '/unity_cand_a/ds38_outlines_metrics.json')
              + glob.glob(OUT + '/unity_cand_a_tv/video/*.mp4') + glob.glob(OUT + '/unity_cand_a_tv/ds30_tstar_regress.json')
              + glob.glob(OUT + '/unity_r1_seq/ds38_outlines_metrics.json') + glob.glob(OUT + '/unity_r1_t28/ds30_tstar_regress.json')
              + glob.glob(OUT + '/unity/ds38_fix_eval.json') + glob.glob(OUT + '/unity_fix1/*.json') + glob.glob(OUT + '/unity_fix1/video/*.mp4')
              + glob.glob(OUT + '/fixr_x*/ds38_fix_eval.json'))
reports = {k: load(p) for k, p in (('first_eval_t28', OUT + '/unity_r1_t28/ds38_render_report.json'), ('first_eval_seq', OUT + '/unity_r1_seq/ds38_render_report.json'),
                                   ('candidate_a', OUT + '/unity_cand_a/ds38_render_report.json'), ('candidate_a_t28_video', OUT + '/unity_cand_a_tv/ds38_render_report.json'),
                                   ('verify_tau0', OUT + '/unity_verify/ds38_render_report.json'), ('fix1_delivered_before_fixround', OUT + '/unity_fix1/ds38_render_report.json'),
                                   ('fixround_x1', OUT + '/fixr_x1/ds38_render_report.json'), ('fixround_x2', OUT + '/fixr_x2/ds38_render_report.json'),
                                   ('fixround_x3', OUT + '/fixr_x3/ds38_render_report.json'), ('fixround_x4_rejected_code_removed', OUT + '/fixr_x4/ds38_render_report.json'), ('fixround_x5_not_adopted', OUT + '/fixr_x5/ds38_render_report.json')) if os.path.exists(p)}
U = 'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds38/run_ds38_unity.ps1 -Method GreatWave.Design38.EditorTools.DS38Render.Render'
run = {
    'number': '設計38 第「輪郭線」部',
    'commands': [
        '1 回目の評価（修正前）：' + U + ' -Log run2 -Extra "-ds38Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/38/outlines/unity -ds38Skip l191,s192,mock,near,video"'
        '（場面・印・t* の組、約 17 s。出力は後で unity_r1_t28/ へ移した）',
        '1 回目の評価（修正前）：' + U + ' -Log run3 -Extra "-ds38Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/38/outlines/unity_run3 -ds38Skip scene,mask,t28"（約 2.5 分。後で unity_r1_seq/ へ移した）',
        '修正1：' + U + ' -Log fix1 -Extra "-ds38Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/38/outlines/unity"（全部、約 2.2 分）',
        'py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/38/outlines/unity --sets t28_claws,t28_white（評価器、約 7 分）',
        'py -3.10 -B Tools/GWWaveGen/ds38/ds38_line_eval.py --unity Unity/Build/Design/38/outlines/unity --out Unity/Build/Design/38/outlines（約 1 分）',
        'py -3.10 -B Tools/GWWaveGen/ds38/ds38_figs.py --unity Unity/Build/Design/38/outlines/unity --t28 Unity/Build/Design/38/outlines/unity --fig Unity/Build/Design/38/outlines/fig',
        '確かめ（_DS38FacingMin を足した後、既定 0 で修正1 と画素まで同じか）：' + U + ' -Log verify -Extra "-ds38Out .../unity_verify -ds38Skip scene,mask,t28,s192,mock,near,video"',
        '候補A（採らない。記録）：' + U + ' -Log candA -Extra "-ds38Out .../unity_cand_a -ds38Skip scene,mask,t28,video -ds38Candidate hero:0:0,near:1:0.15,claws:1:0"、'
        '同 -Log candA_t28video -Extra "-ds38Out .../unity_cand_a_tv -ds38Skip scene,mask,l191,s192,mock,near -ds38Candidate hero:0:0,near:1:0.15,claws:1:0"、'
        'ds38_line_eval.py --unity .../unity_cand_a、ds30b_tstar_regress.py --out .../unity_cand_a_tv',
        '修正の回（進行役の検査の後の 1 回、Q26。修正1 の出力 unity/ は unity_fix1/ へ移した）の試し：' + U + ' -Log fixr_xN -Extra "-ds38Out .../fixr_xN -ds38Skip scene,mask,t28,s192,mock,near,video -ds38Candidate <組>"'
        '（X1 hero:1:0:1:1:0,near:1:0:1:0:0／X2 hero:1:0:1:1:2,near:1:0:1:0:1／X3 hero:1:0:3:1:2,near:1:0.1:1:0:1,claws:1:0:1:0／'
        'X4 hero:1:0:3:1:2:0.15,near:1:0:1:0:1:0.15（X4 の 7 つ目の値 _DS38SmoothMax のコードは採らずに消した）／X5 hero:1:0:3:1:2,near:1:0:3:0:1（ds38_fix_eval は回していない。README の F）。prep/ は unity_fix1/prep の写し）、各 ds38_fix_eval.py --unity .../fixr_xN --out .../fixr_xN/ds38_fix_eval.json',
        '修正の回（採った値は DS38Render.Adopted）：' + U + ' -Log fixround -Extra "-ds38Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/38/outlines/unity"（全部、約 2.2 分）、'
        '評価器・ds38_line_eval.py（上と同じ）、py -3.10 -B Tools/GWWaveGen/ds38/ds38_fix_eval.py --unity Unity/Build/Design/38/outlines/unity --out Unity/Build/Design/38/outlines/unity/ds38_fix_eval.json'
        '（修正1 の unity_fix1 にも同じもの）、ds38_figs.py（上と同じ）、py -3.10 -B Tools/GWWaveGen/ds38/ds38_fixround_figs.py、py -3.10 -B Tools/GWWaveGen/ds38/ds38_summary.py',
        'py -3.10 -B Tools/GWWaveGen/ds38/ds38_run_record.py'],
    'tools': {'unity': rep['unity'], 'device': rep['device'], 'graphicsApi': rep['graphicsApi'], 'python': sys.version.split()[0], 'numpy': np.__version__,
              'opencv': cv2.__version__, 'platform': platform.platform(), 'ffmpeg': 'G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe'},
    'unity_seconds': rep['secondsTotal'], 'protected_unchanged': rep['protectedUnchanged'], 'protected_files': rep['protectedFiles'],
    'other_runs': {k: {'secondsTotal': v.get('secondsTotal'), 'protectedUnchanged': v.get('protectedUnchanged'), 'candidate': v.get('candidate', '')} for k, v in reports.items()},
    'verify_tau0_l191_identical_to_fix1': all(sha(OUT + '/unity_fix1/l191/' + os.path.basename(s['path'])) == sha(OUT + '/unity_verify/l191/' + os.path.basename(s['path']))
                                              for s in rep['seqs']) if os.path.isdir(OUT + '/unity_verify/l191') else None,
    'fixround_mask_identical_to_fix1': sha(OUT + '/unity/prep/ds38_hero_linemask_f32.bin') == sha(OUT + '/unity_fix1/prep/ds38_hero_linemask_f32.bin'),
    'code_sha256': {rel(p): sha(p) for p in code if os.path.exists(p)},
    'inputs_sha256': {rel(p): sha(p) for p in inputs if os.path.exists(p)},
    'outputs_sha256': {rel(p): sha(p) for p in outs if os.path.exists(p) and not p.endswith('ds38_run.json')},
    'not_kept_note_ja': 'unity/l191・s192・mock・near の生データ（線の画素の表と 1 bit、Build/Design/38 の全体で約 1 GB）は Build の中に置いたまま（Git 対象外）。',
}
json.dump(run, open(OUT + '/ds38_run.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('run record written', len(run['outputs_sha256']), run['verify_tau0_l191_identical_to_fix1'], run['fixround_mask_identical_to_fix1'])
