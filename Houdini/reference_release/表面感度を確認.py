# -*- coding: utf-8 -*-
"""既存の FLIP 粒子を再表面化し、Droplet Scale の影響だけを比較する。"""
import argparse
import hashlib
import json
from pathlib import Path
import hou
import numpy as np

src = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description='同じ保存済み粒子から表示表面の感度を調べる。流体計算は実行しない。')
parser.add_argument('--cache-dir', type=Path, default=src.parent / 'results' / 'reference_release' / '本計算01')
parser.add_argument('--output-dir', type=Path, default=src.parent / 'results' / 'reference_release' / '表面感度')
args = parser.parse_args()
cache = args.cache_dir.resolve()
out = args.output_dir.resolve()
if (out / '表面感度.json').exists():
    raise RuntimeError('既存の比較結果を上書きしない。')
out.mkdir(parents=True, exist_ok=True)
hip = src / '参照水体の自由発展.hiplc'
hip_hash = hashlib.sha256(hip.read_bytes()).hexdigest()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(hip), suppress_save_prompt=True, ignore_load_warnings=True)
original = hou.node('/obj/simulation_result/water_surface')
keys = ['surfmethod', 'particlesep', 'voxelsize', 'influenceradius', 'surfacedistance', 'minvoxelradius',
        'preservebubbles', 'dosurfunion', 'surferosion', 'conversion', 'adaptivity', 'dosmooth',
        'dofinalsmooth', 'dodilate', 'doerode', 'limititerations', 'resamplingiterations']
settings = {k: original.parm(k).eval() for k in keys}
geo = hou.node('/obj').createNode('geo', 'surface_sensitivity')
for n in geo.children():
    n.destroy()
file = geo.createNode('file', 'saved_particles')
surface = geo.createNode('particlefluidsurface::2.0', 'surface_variant')
surface.setInput(0, file)
surface.setParms(settings)
convert = geo.createNode('convert', 'polygon_mesh')
convert.setInput(0, surface)
hou.setUpdateMode(hou.updateMode.AutoUpdate)


def topology(g):
    p = np.asarray(g.pointFloatAttribValues('P')).reshape(-1, 3)
    if not np.isfinite(p).all():
        raise RuntimeError('非有限頂点を検出した。')
    parent = list(range(len(p)))
    edges = {}
    directions = {}
    zero_area = 0
    area = 0.
    signed_volume = 0.

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for prim in g.prims():
        indices = [v.point().number() for v in prim.vertices()]
        for a, b in zip(indices, indices[1:] + indices[:1]):
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
            directions[key] = directions.get(key, 0) + (1 if a < b else -1)
            parent[find(a)] = find(b)
        face_area = 0.
        for i in range(1, len(indices) - 1):
            a, b, c = p[indices[0]], p[indices[i]], p[indices[i + 1]]
            face_area += np.linalg.norm(np.cross(b - a, c - a)) * .5
            signed_volume += np.dot(a, np.cross(b, c)) / 6.
        area += face_area
        if face_area < 1e-12:
            zero_area += 1
    return {'頂点数': len(p), '面数': len(g.prims()),
            '境界辺数': sum(v == 1 for v in edges.values()), '三面以上が共有する辺数': sum(v > 2 for v in edges.values()),
            '二面の向きが不整合な辺数': sum(edges[k] == 2 and d != 0 for k, d in directions.items()),
            '面積がほぼ零の面数': zero_area, '頂点接続の成分数': len(set(find(i) for i in range(len(p)))),
            '表示表面の面積_m2': float(area), '表示表面の符号付き体積_m3': float(signed_volume),
            '境界箱最小_m': p.min(axis=0).tolist(), '境界箱最大_m': p.max(axis=0).tolist()}


rows = []
for frame in [1, 6, 12]:
    hou.setFrame(frame)
    particle_file = cache / 'particles' / f'water_{frame:04d}.bgeo.sc'
    particle_hash = hashlib.sha256(particle_file.read_bytes()).hexdigest()
    file.parm('file').set(str(particle_file))
    file.cook(force=True)
    g = file.geometry()
    pscale = g.pointFloatAttribValues('pscale')
    saved = hou.Geometry()
    saved.loadFromFile(str(cache / 'surface' / f'water_{frame:04d}.bgeo.sc'))
    saved_p = np.asarray(saved.pointFloatAttribValues('P')).reshape(-1, 3)
    for multiplier in [1.0, .8, .6]:
        scale = settings['surfacedistance'] * multiplier
        surface.parm('surfacedistance').set(scale)
        surface.cook(force=True)
        raw_p = np.asarray(surface.geometry().pointFloatAttribValues('P')).reshape(-1, 3)
        baseline_error = None
        if multiplier == 1.0:
            if raw_p.shape != saved_p.shape:
                raise RuntimeError('基準表面の頂点数が保存済み結果と違う。')
            baseline_error = float(np.max(np.linalg.norm(raw_p - saved_p, axis=1)))
            if baseline_error > 1e-6:
                raise RuntimeError('基準表面が保存済み結果と一致しない。')
        convert.cook(force=True)
        mesh = convert.geometry()
        name = f'表面_{frame:03d}_倍率{multiplier:.1f}.obj'
        mesh.saveToFile(str(out / name))
        row = {'フレーム': frame, 'Droplet_Scale倍率': multiplier, 'Droplet_Scale実値': scale,
               '入力粒子SHA256': particle_hash, '入力pscale最小最大_m': [min(pscale), max(pscale)],
               '入力粒子数': len(g.points()), '基準と保存済み表面の最大座標差_m': baseline_error,
               '出力': name, '幾何': topology(mesh)}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    assert hashlib.sha256(particle_file.read_bytes()).hexdigest() == particle_hash
assert hashlib.sha256(hip.read_bytes()).hexdigest() == hip_hash
report = {'制作元HIPのSHA256': hip_hash, '基準ノード設定': settings,
          '変更した項目': 'surfacedistance (Droplet Scale) のみ。粒子 P/v/pscale と他の表面設定は変更しない。',
          'シミュレーション実行': False, '元の入力と出力変更なし': True,
          '制限': '小さい値が常に良いとは限らない。空隙と厚み、穴や分離を同時に比較する。自己交差と幾何学的な水量保存は別検証。',
          '比較': rows}
(out / '表面感度.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
