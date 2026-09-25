"""許可後の指定BGEOだけを読む定義。単独実行なし、houと純関数は呼出側から渡す。"""
import hashlib
import json
import math
import struct
import time
from pathlib import Path


def _file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _field_record(volume, include_values=False):
    center = list(map(float, volume.indexToPos((0, 0, 0))))
    steps = []
    for axis in range(3):
        index = [0, 0, 0]
        index[axis] = 1
        value = volume.indexToPos(tuple(index))
        steps.append([float(value[j])-center[j] for j in range(3)])
    lo, hi = volume.boundingBox().minvec(), volume.boundingBox().maxvec()
    record = {'name': volume.attribValue('name'), 'type': str(volume.type()),
              'bounds': {'min': list(map(float, lo)), 'max': list(map(float, hi))},
              'resolution': list(map(int, volume.resolution())),
              'voxel_size_m': list(map(float, volume.voxelSize())),
              'transform': list(volume.transform().asTuple()),
              'index_zero_center_m': center, 'index_unit_steps_m': steps,
              'is_sdf_metadata': bool(volume.isSDF())}
    if not all(n > 0 for n in record['resolution']):
        raise ValueError('密Volumeの解像度が空')
    numeric = center + record['transform'] + record['voxel_size_m'] + [c for s in steps for c in s]
    if not all(math.isfinite(x) for x in numeric):
        raise ValueError('field transformが非有限')
    if not all(steps[a][a] > 0 for a in range(3)) or any(
            abs(steps[a][b]) > 1e-7 for a in range(3) for b in range(3) if a != b):
        raise ValueError('事前条件の軸平行fieldではない')
    if include_values:
        values = volume.allVoxels()
        if not all(math.isfinite(v) for v in values):
            raise ValueError('初期field値が非有限')
        record['all_voxels_sha256'] = hashlib.sha256(struct.pack('<%dd' % len(values), *values)).hexdigest()
        record['voxel_hash_encoding'] = 'HOM_values_as_little_endian_float64'
    return record


def _real_particles(geometry):
    # Volume/VDB保持点を含む全primitive参照点を除外する。粒子数へ加えない。
    held = {vertex.point().number() for primitive in geometry.prims() for vertex in primitive.vertices()}
    actual = [point for point in geometry.points() if point.number() not in held]
    return actual, len(held)


def _initial_identity(geometry, particles, hou_api):
    for name in ('id', 'v', 'pscale'):
        if geometry.findPointAttrib(name) is None:
            raise ValueError('初期配対に必要な属性がない: '+name)
    rows = sorted((int(p.attribValue('id')), tuple(map(float, p.position())),
                   tuple(map(float, p.attribValue('v'))), float(p.attribValue('pscale')))
                  for p in particles)
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError('実粒子ID重複')
    if not all(math.isfinite(v) for r in rows for v in (*r[1], *r[2], r[3])):
        raise ValueError('初期P/v/pscaleが非有限')
    fields = {}
    for name in ('surface', 'pressure'):
        found = [p for p in geometry.prims() if isinstance(p, hou_api.Volume) and p.attribValue('name') == name]
        if len(found) != 1:
            raise ValueError('初期Volumeの名前/型/数が不一致: '+name)
        fields[name] = _field_record(found[0], include_values=True)
    return {'particle_count': len(rows), 'ID_unique': True,
            'sorted_ID_P_sha256': digest([(r[0], r[1]) for r in rows]),
            'sorted_ID_v_sha256': digest([(r[0], r[2]) for r in rows]),
            'sorted_ID_pscale_sha256': digest([(r[0], r[3]) for r in rows]),
            'pscale_min_max_m': [min(r[3] for r in rows), max(r[3] for r in rows)],
            'surface_pressure_initial_fields': fields,
            'meaning_ja': '同じID順の元精度P/v/pscaleと全初期fieldを照合する。同seed/同数だけで一致とはしない。'}


def read_cached_probe(hou_api, cache_path, expected_sha, sample, expected_particles,
                      maximum_seconds=90.):
    """UI・ノード・時刻を変更せずGeometryへ1ファイルを読込み、全点記録を返す。"""
    start = time.monotonic()
    path = Path(cache_path)
    actual_sha = _file_sha(path)
    if actual_sha != expected_sha:
        raise ValueError('指定cache SHA不一致')
    hashed = time.monotonic()
    geometry = hou_api.Geometry()
    geometry.loadFromFile(str(path))
    loaded = time.monotonic()
    if geometry.findPrimAttrib('name') is None:
        raise ValueError('field名属性なし')
    named = [p for p in geometry.prims() if p.attribValue('name') == 'surface']
    if len(named) != 1 or not isinstance(named[0], hou_api.Volume):
        raise ValueError('surfaceは単一の密Volumeでなければならない')
    volume = named[0]
    field = _field_record(volume)
    particles, held_count = _real_particles(geometry)
    if len(particles) != expected_particles:
        raise ValueError('元標本と実粒子数が一致しない')
    if geometry.findPointAttrib('id') is None or len({p.attribValue('id') for p in particles}) != len(particles):
        raise ValueError('実粒子IDなしまたは重複')
    positions = [tuple(map(float, p.position())) for p in particles]
    identified = time.monotonic()
    remaining = maximum_seconds-(identified-start)
    if remaining <= 0:
        raise TimeoutError('BGEO読込み/属性抽出で予算超過')
    measured = inspect_points(volume.sample, field['bounds'], positions, maximum_seconds=remaining)
    identity = _initial_identity(geometry, particles, hou_api) if sample == 0 else None
    finished = time.monotonic()
    if finished-start > maximum_seconds:
        raise TimeoutError('単一BGEO観測の全体予算超過')
    return {'sample': sample, 'absolute_seconds': sample/60, 'cache_filename': path.name,
            'cache_sha256': actual_sha, 'cache_bytes': path.stat().st_size,
            'surface_field': field, 'primitive_count': len(geometry.prims()),
            'all_geometry_points': len(geometry.points()), 'primitive_held_points_excluded': held_count,
            'initial_pairing_reference': identity, 'deepwater': measured,
            'timing_seconds': {'hash': hashed-start, 'load_from_file': loaded-hashed,
                               'identify_field_and_particles': identified-loaded,
                               'sampling_and_identity': finished-identified, 'total': finished-start},
            'nodes_created': False, 'simulation_cooked': False,
            'meaning_ja': '指定した保存cacheの読戻し。現HIPのgeometry・simulationは読まず、旧DOPの再cookもしない。'}
