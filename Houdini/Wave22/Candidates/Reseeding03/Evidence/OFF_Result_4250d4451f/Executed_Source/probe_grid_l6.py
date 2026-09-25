"""許可後だけ所有SOPと指定旧BGEOを読む。定義は各RPCへ明示的に注入する。"""
import hashlib
import json
import math
import shutil
import time
from pathlib import Path


def named_field(geometry, name):
    matches = [p for p in geometry.prims() if isinstance(p, (hou.Volume, hou.VDB))
               and p.attribValue('name') == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def describe_grid(volume, label, length):
    # indexToPosはvoxel中心を返す。boundsの端をcell中心として代用しない。
    sparse = isinstance(volume, hou.VDB)
    empty = bool(volume.isEmpty()) if sparse else False
    active_count = int(volume.activeVoxelCount()) if sparse else None
    active_bounds = volume.activeVoxelBoundingBox() if sparse and not empty else None
    if empty:
        return {'label': label, 'type': str(volume.type()), 'name': volume.attribValue('name'),
                'sparse_vdb': True, 'is_empty_vdb': True, 'active_voxel_count': active_count,
                'active_voxel_bounds_hom_raw': None, 'resolution': list(map(int, volume.resolution())),
                'bounds': None, 'index_000_cell_center_m': None, 'index_unit_step_vectors_m': None,
                'voxel_size_m': list(map(float, volume.voxelSize())),
                'transform': list(volume.transform().asTuple()), 'is_sdf': bool(volume.isSDF()),
                'covers_both_walls_at_middepth': False, 'mirror': None, 'mirror_label_applicable': False,
                'meaning_ja': '空の疎なVDB。active bounds・index中心・鏡像は評価しない。背景値を別に採録する。'}
    center = list(map(float, volume.indexToPos((0, 0, 0))))
    steps = []
    for axis in range(3):
        index = [0, 0, 0]
        index[axis] = 1
        at = volume.indexToPos(tuple(index))
        steps.append([float(at[j])-center[j] for j in range(3)])
    assert all(math.isfinite(v) for v in center+[c for step in steps for c in step])
    assert all(steps[a][a] > 0 for a in range(3))
    assert max(abs(steps[a][j]) for a in range(3) for j in range(3) if a != j) < 1e-7
    box = volume.boundingBox()
    bounds = {'min': list(map(float, box.minvec())), 'max': list(map(float, box.maxvec()))}
    resolution = list(map(int, volume.resolution()))
    expanded = within_bounds((0, -.3, 0), bounds) and within_bounds((length, -.3, 0), bounds)
    return {'label': label, 'type': str(volume.type()), 'name': volume.attribValue('name'),
            'resolution': resolution, 'bounds': bounds, 'index_000_cell_center_m': center,
            'sparse_vdb': sparse, 'is_empty_vdb': empty, 'active_voxel_count': active_count,
            'active_voxel_bounds_hom_raw': None if active_bounds is None else {
                'min': list(map(float, active_bounds.minvec())), 'max': list(map(float, active_bounds.maxvec()))},
            'index_zero_is_not_assumed_active': True,
            'index_unit_step_vectors_m': steps, 'voxel_size_m': list(map(float, volume.voxelSize())),
            'transform': list(volume.transform().asTuple()), 'is_sdf': bool(volume.isSDF()),
            'covers_both_walls_at_middepth': expanded,
            'mirror': mirror_metric(center[0], steps[0][0], length),
            'mirror_label_applicable': expanded and not empty,
            'meaning_ja': 't0の小さいpressure fieldは両壁へ展開していなければ鏡像判定対象外。'}


if PHASE == 'grid_old_reference':
    # 実行許可後、明示された新規repo内の旧t6キャッシュだけを読み、HIP内容は調べない。
    path = Path(OLD_GRID_CACHE)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == OLD_GRID_CACHE_SHA
    old = hou.Geometry()
    old.loadFromFile(str(path))
    records = [describe_grid(named_field(old, name), 'old_saved_'+name, OLD_LENGTH)
               for name in ('pressure', 'surface')]
    result = {'source_cache_sha256': OLD_GRID_CACHE_SHA, 'sample': 1, 'seconds': 1/60,
              'length_m': OLD_LENGTH, 'fields': records, 'old_collision_available': False,
              'existing_scene_read': False}
    write('22_length6_old_grid.json', result)

elif PHASE.startswith('grid_new:'):
    requested = float(PHASE.split(':')[1])
    assert requested in (0, 1/120, 1/60)
    started = time.monotonic()
    state = getattr(hou.session, KEY)
    assert state['dop'].sessionId() == state['checkpoint_dop_id']
    assert not state['checkpoint_drive_authorized']
    assert shutil.disk_usage(ROOT).free >= BUDGET['minimum_disk_free_bytes']
    assert all(state['dop'].evalParm(p) == 0 for p in ('cachetodisk', 'cachetodisknoninteractive', 'explicitcache'))
    if requested in (0, 1/60):
        # 通常標本の直後は保存済みBGEOを読むだけ。同時刻SOPを強制再cookしない。
        assert abs(hou.frame()-(1+requested*hou.fps())) < 1e-8
        original_path = ROOT / 'Cache' / ('pilot_%03d.bgeo.sc' % round(requested*60))
        original_sha = state['samples'][round(requested*60)]['cache_sha256']
        assert hashlib.sha256(original_path.read_bytes()).hexdigest() == original_sha
        raw = hou.Geometry()
        raw.loadFromFile(str(original_path))
        observation_mode = 'saved_regular_BGEO_without_force_cook'
    else:
        # 新しい実1/120秒の状態を前進評価する。resetや補間、同時刻のforceは行わない。
        hou.setFrame(1+requested*hou.fps())
        state['particles'].cook(force=False)
        raw = state['particles'].geometry().freeze()
        observation_mode = 'new_half_sample_forward_cook'
    # 衝突はsolverの同時刻依存出力を読む。独立のforce-cookは要求しない。
    collision = state['collisionout'].geometry().freeze()
    simulation = state['dop'].simulation()
    assert abs(simulation.time()-requested) < 1e-6 and abs(simulation.timestep()-1/120) < 1e-9
    records = [describe_grid(named_field(raw, name), 'solver_'+name, L)
               for name in ('pressure', 'surface')]
    assert all(isinstance(named_field(raw, name), hou.Volume) for name in ('pressure', 'surface'))
    assert all(math.isfinite(v) for name in ('pressure', 'surface')
               for v in named_field(raw, name).allVoxels())
    collider = named_field(collision, 'surface')
    assert collider.isSDF()
    records.append(describe_grid(collider, 'collision_surface', L))
    assert all(r['resolution'][0] > 0 for r in records)
    if requested == 1/60:
        assert records[0]['covers_both_walls_at_middepth'], 'pressure場が両壁まで未展開'
    wall = wall_pairs(collider.sample, records[-1]['bounds'], L,
                      records[-1]['index_unit_step_vectors_m'][0][0], GRID_PLAN['collision_probe'])
    velocity_field = named_field(collision, 'vel')
    # 静止時の疎なvel fieldはactive領域が空でも背景0が有効。surfaceの有効性とは分ける。
    velocity_record = describe_grid(velocity_field, 'collision_velocity', L)
    velocity_record['active_background_only'] = any(n == 0 for n in velocity_record['resolution'])
    actual_collision_velocity = list(map(float, velocity_field.samplev((-.12, -.3, 0))))
    assert all(math.isfinite(v) for v in actual_collision_velocity)
    assert abs(actual_collision_velocity[0]-motion(requested)[1]) < 1e-4
    assert max(abs(actual_collision_velocity[a]) for a in (1, 2)) < 1e-6
    held = {v.point().number() for primitive in raw.prims() for v in primitive.vertices()}
    points = [p for p in raw.points() if p.number() not in held]
    positions = [list(p.position()) for p in points]
    velocities = [list(p.attribValue('v')) for p in points]
    assert points and len({p.attribValue('id') for p in points}) == len(points)
    assert all(math.isfinite(v) for p in positions+velocities for v in p)
    assert all(-.02 <= p[0] <= L+.02 and p[1] >= -H-.02 and abs(p[2]) <= W/2+.02 for p in positions)
    gauges = [gauge(named_field(raw, 'surface'), LAM*f, 0) for f in GAUGES]
    assert all(g['valid'] for g in gauges)
    assert not state['solver'].errors() and not state['solver'].warnings()
    raw_path = ROOT / 'Cache' / ('grid_substep_%03d.bgeo.sc' % round(requested*120))
    collision_path = ROOT / 'Cache' / ('collision_substep_%03d.bgeo.sc' % round(requested*120))
    raw.saveToFile(str(raw_path))
    collision.saveToFile(str(collision_path))
    row = {'requested_seconds': requested, 'simulation_seconds': simulation.time(),
           'raw_observation_mode': observation_mode,
           'dt_seconds': simulation.timestep(), 'fields': records, 'collision_pairs': wall,
           'collision_velocity_field': velocity_record,
           'actual_collision_velocity_m_s': actual_collision_velocity,
           'particle_count': len(points), 'particle_ids_unique': True, 'finite_P_v': True,
           'gauges': gauges, 'piston_analytic_displacement_velocity': list(motion(requested)),
           'simulation_memory_bytes': simulation.memoryUsage(), 'memory': memory(),
           'cook_seconds': time.monotonic()-started,
           'saved_geometry': [{'name': p.name, 'bytes': p.stat().st_size,
                               'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                              for p in (raw_path, collision_path)]}
    state.setdefault('grid_preflight_rows', []).append(row)
    result = {'rows': state['grid_preflight_rows'], 'physical_pass': False,
              'meaning_ja': '格子・衝突の測定。静水の許可判定はt6の固定窓で別実行。'}
    write('22_length6_grid_preflight.json', result)
    assert motion(requested) == (0.0, 0.0)
    assert row['memory']['available_physical_bytes'] >= BUDGET['minimum_available_ram_bytes']
    assert row['memory']['private_commit_bytes']-state['checkpoint_baseline_private'] <= BUDGET['maximum_private_growth_bytes']
    assert row['simulation_memory_bytes'] <= BUDGET['maximum_dop_cache_bytes']
    assert row['cook_seconds'] <= BUDGET['maximum_sample_seconds']
