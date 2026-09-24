# -*- coding: utf-8 -*-
"""閉じた参照水体と水槽を SDF で結合し、一度だけ初期粒子を作る。"""
from pathlib import Path
import json
import hashlib
import hou
import numpy as np


def make_node(parent, kind, name, note):
    n = parent.createNode(kind, name)
    n.setComment(note)
    n.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return n


def sdf(parent, upstream, name, voxel):
    n = make_node(parent, 'vdbfrompolygons', name, '閉じた模型から符号付き距離場を作る。水体内は負、空気は正。')
    n.setInput(0, upstream)
    n.setParms({'voxelsize': voxel, 'builddistance': 1, 'buildfog': 0,
                'fillinterior': 1, 'unsigneddist': 0, 'preserveholes': 1})
    return n


def check_samples(sdf_node, points, label, tolerance):
    sdf_node.cook(force=True)
    if not sdf_node.geometry().prims():
        details = {n.path(): list(n.errors()) for n in sdf_node.parent().children()}
        raise RuntimeError('SDF が空: ' + json.dumps(details, ensure_ascii=False))
    field = sdf_node.geometry().prims()[0]
    result = []
    for p in points:
        value = float(field.sample(tuple(p['position'])))
        if p['kind'] not in ('air', 'water'):
            raise ValueError('確認点の種別が不正。')
        ok = value > tolerance if p['kind'] == 'air' else value < -tolerance
        result.append({'名称': p['name'], '種別': p['kind'], '位置_m': p['position'],
                       'SDF値_m': value, '符号と余裕を確認': bool(ok)})
    if not all(p['符号と余裕を確認'] for p in result):
        raise RuntimeError(label + 'で開口または水体の確認に失敗: ' + json.dumps(result, ensure_ascii=False))
    return result


def build_initial(obj, cfg, input_path, check_path, out, src):
    initial = make_node(obj, 'geo', 'initial_water', '参照の閉じた水体を初期値として使う。波の形成過程を証明する模型ではない。')
    for child in initial.children():
        child.destroy()
    source = make_node(initial, 'file', 'reference_water', 'Y が上、X が進行方向、Z が幅方向。単位 m。変換済みの閉じた水体。')
    rel = Path(input_path).resolve().relative_to(Path(src).resolve())
    source.parm('file').set('$HIP/' + rel.as_posix())
    reference_sdf = sdf(initial, source, 'reference_sdf', cfg['initial_sdf_voxel_m'])
    cut_y = cfg['reference_cut_y_m']
    upper_region = make_node(initial, 'box', 'upper_halfspace', '模型を含む領域で Y が切断高以上の半空間。側面と上面は参照模型の外側に置く。')
    upper_region.setParms({'sizex': cfg['length_m'], 'sizey': cfg['domain_height_m'] - cut_y,
                          'sizez': cfg['width_m'], 'ty': (cfg['domain_height_m'] + cut_y) * .5})
    upper_sdf = sdf(initial, upper_region, 'upper_halfspace_sdf', cfg['initial_sdf_voxel_m'])
    clipped_reference = make_node(initial, 'vdbcombine', 'clipped_reference', 'SDF Intersection。模型内では phi=max(phi,切断高-Y) と等価な水面下の裁切。内部ブロックも処理する。')
    clipped_reference.setInput(0, reference_sdf)
    clipped_reference.setInput(1, upper_sdf)
    clipped_reference.parm('operation').set('sdfintersect')
    clipped_reference.parm('resample').set('btoa')
    pool = make_node(initial, 'box', 'still_water', '静水体。参照水体の水面下の部分と重ねて接合する。')
    pool.setParms({'sizex': cfg['length_m'], 'sizey': cfg['still_depth_m'],
                   'sizez': cfg['width_m'], 'ty': cfg['still_depth_m'] * .5})
    pool_sdf = sdf(initial, pool, 'pool_sdf', cfg['initial_sdf_voxel_m'])
    union = make_node(initial, 'vdbcombine', 'joined_surface', '独立した二つの符号付き距離場を SDF Union で結合する。')
    union.setInput(0, clipped_reference)
    union.setInput(1, pool_sdf)
    union.parm('operation').set('sdfunion')
    union.parm('resample').set('btoa')
    points = make_node(initial, 'pointsfromvolume', 'initial_sampling', '結合 SDF の内部を等間隔で一度だけ粒子化する。')
    points.setInput(0, union)
    points.setParms({'source': 3, 'particlesep': cfg['particle_separation_m'],
                    'pointmethod': 0, 'iso': -cfg['particle_separation_m'] * .25,
                    'jitterscale': .08, 'jitterseed': cfg['seed'], 'addscale': 0,
                    'offsetx': .5 * cfg['particle_separation_m'],
                    'offsety': .5 * cfg['particle_separation_m'],
                    'offsetz': .5 * cfg['particle_separation_m']})
    velocity = make_node(initial, 'python', 'initial_velocity', '上層の前進速度と小さい下降速度を一度だけ与える。実海の測定速度ではない。以後は自由な FLIP 計算。')
    velocity.setInput(0, points)
    code = '''import hou,numpy as np
c=CONFIG
g=hou.pwd().geometry();P=np.asarray(g.pointFloatAttribValues('P')).reshape(-1,3)
q=np.clip((P[:,1]-c['still_depth_m'])/c['velocity_height_ramp_m'],0.,1.)
w=q*q*(3.-2.*q)
V=np.zeros_like(P);V[:,0]=c['initial_forward_speed_m_s']*w
V[:,1]=-c['initial_tip_down_speed_m_s']*w*w
g.addAttrib(hou.attribType.Point,'v',(0.,0.,0.));g.setPointFloatAttribValues('v',V.ravel().tolist())
g.addAttrib(hou.attribType.Point,'pscale',c['particle_separation_m']*1.2)
g.addAttrib(hou.attribType.Point,'density',1000.);g.addAttrib(hou.attribType.Point,'mass',1000.*c['particle_separation_m']**3)
'''.replace('CONFIG', repr(cfg))
    velocity.parm('python').set(code)
    velocity.setDisplayFlag(True)
    velocity.setRenderFlag(True)
    initial.setDisplayFlag(False)
    checks = json.loads(Path(check_path).read_text(encoding='utf-8'))['points']
    if not any(p['kind'] == 'air' for p in checks) or not any(p['kind'] == 'water' for p in checks):
        raise RuntimeError('開口の空気点と水体内点を両方指定する。')
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    source.cook(force=True)
    source_bounds = source.geometry().boundingBox()
    expected_top = cfg['still_depth_m'] + cfg['reference_height_above_water_m']
    if abs(source_bounds.maxvec()[1] - expected_top) > .15:
        raise RuntimeError('入力模型の最高点が指定した高さと一致しない。')
    reference_sdf.cook(force=True)
    clipped_reference.cook(force=True)
    raw_field = reference_sdf.geometry().prims()[0]
    clipped_field = clipped_reference.geometry().prims()[0]
    clipping_checks = []
    for x in np.arange(source_bounds.minvec()[0], source_bounds.maxvec()[0], .2):
        for z in np.arange(source_bounds.minvec()[2], source_bounds.maxvec()[2], .2):
            position = (float(x), cut_y - .10, float(z))
            before = float(raw_field.sample(position))
            if before < -.025:
                after = float(clipped_field.sample(position))
                if after <= .025:
                    raise RuntimeError('水面下の体積裁切が内部に反映されていない。')
                clipping_checks.append({'位置_m': list(position), '裁切前SDF_m': before, '裁切後SDF_m': after})
            if len(clipping_checks) == 3:
                break
        if len(clipping_checks) == 3:
            break
    if not clipping_checks:
        raise RuntimeError('裁切前の模型で水面下の内部点を確認できない。')
    measured = check_samples(union, checks, '結合 SDF', cfg['initial_sdf_voxel_m'] * .5)
    union.geometry().saveToFile(str(out / '初期水体.vdb'))
    proxy = make_node(initial, 'convertvdb', 'sdf_reconstruction', '体積化した後の形を実際に確認するための模型。')
    proxy.setInput(0, union)
    proxy.parm('conversion').set(2)
    proxy.cook(force=True)
    proxy.geometry().saveToFile(str(out / '初期SDF_表面.obj'))
    velocity.cook(force=True)
    g = velocity.geometry()
    if not 1000 <= len(g.points()) <= cfg['max_particles']:
        raise RuntimeError('想定範囲外の初期粒子数: ' + str(len(g.points())))
    g.saveToFile(str(out / '初期粒子.bgeo.sc'))
    report = {'入力': rel.as_posix(), '入力SHA256': hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
              '座標': 'X は前、Y は上、Z は幅、m。',
              '入力境界箱最小_m': list(source_bounds.minvec()),
              '入力境界箱最大_m': list(source_bounds.maxvec()),
              '水面下の裁切確認': clipping_checks,
              '初期粒子数': len(g.points()), 'SDF確認点': measured,
              '体積化のボクセル_m': cfg['initial_sdf_voxel_m'],
              '注意': 'SDF の符号確認。粒子化後の表面、圧力場、実際の自由発展は別途確認する。'}
    (out / '初期水体確認.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return initial, velocity, checks, report
