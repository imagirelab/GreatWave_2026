# -*- coding: utf-8 -*-
"""白波 HIP の設定と既存粒子キャッシュを読む。計算と保存は行わない。"""
import hashlib
import json
from pathlib import Path
import hou
import numpy as np

src = Path(__file__).resolve().parent
cfg = json.loads((src / '条件.json').read_text(encoding='utf-8'))
hip = src / '白波の独立計算.hiplc'
before = hashlib.sha256(hip.read_bytes()).hexdigest()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(hip), suppress_save_prompt=True, ignore_load_warnings=True)
base = hou.node('/obj/whitewater')
source = base.node('whitewater_source')
solver = base.node('whitewater_solver')
post = base.node('whitewater_mesh')
assert source.type().name() == 'whitewatersource::3.0'
for key, value in {'startframe': 2, 'enableactivate': 0, 'enablepressure': 0, 'enablesplash': 0,
                   'enableacceleration': 0, 'enablevorticity': 0, 'enablecurvature': 1,
                   'depthrangemin': cfg['depth_min_m'], 'depthrangemax': cfg['depth_max_m'],
                   'speedrangemin': cfg['speed_min_m_s'], 'speedrangemax': cfg['speed_max_m_s'],
                   'curvaturerangemin': cfg['curvature_min_m_inv'], 'curvaturerangemax': cfg['curvature_max_m_inv'],
                   'outputvolumes': 1, 'modifyvolumes': 0}.items():
    assert abs(source.parm(key).eval() - value) < 1e-9, key
for key, value in {'startframe': 2, 'scale': cfg['whitewater_scale_m'], 'voxelsize': cfg['density_voxel_m'],
                   'sdfactivate': 0, 'emissionamount': cfg['emission_amount'], 'lifespan': cfg['lifespan_s'],
                   'substep': cfg['substeps'], 'addstatevars': 1, 'seed': cfg['seed'], 'enablerepellants': 0,
                   'useopencl': 0}.items():
    assert abs(solver.parm(key).eval() - value) < 1e-9, key
for i in range(3):
    assert solver.input(i) == source
    assert post.input(i) == solver
assert post.parm('output').eval() == 2
assert post.parm('voxelsize').eval() == cfg['mesh_voxel_m']
field_path = base.node('fluid_fields').parm('file').unexpandedString()
assert field_path == '$HIP/../../results/reference_release/本計算01/fields/fields_$F4.bgeo.sc'
cache = src.parent.parent / 'results' / 'reference_release' / 'whitewater' / '本計算01'
verified = []
for frame in range(3, 25):
    g = hou.Geometry()
    g.loadFromFile(str(cache / 'particles' / f'whitewater_{frame:04d}.bgeo.sc'))
    for attrib in ['P', 'v', 'age', 'life', 'pscale', 'bubble', 'foam', 'spray', 'depth']:
        assert g.findPointAttrib(attrib) is not None, attrib
        assert np.isfinite(g.pointFloatAttribValues(attrib)).all(), attrib
    ids = g.pointIntAttribValues('id')
    assert len(ids) == len(set(ids)) == len(g.points())
    verified.append(frame)
assert hashlib.sha256(hip.read_bytes()).hexdigest() == before
result = {'制作元': hip.name, '制作元SHA256': before, '設定一致': True, '入力場': field_path,
          '独立Solver接続': True, '粒子属性と有限値とIDの照合フレーム': verified,
          'HIP変更なし': True, 'シミュレーション実行': False,
          '制限': 'モデルの空気巻込み精度や北斎の白い爪の造形を保証しない。'}
(src / 'ソース照合.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False), flush=True)
