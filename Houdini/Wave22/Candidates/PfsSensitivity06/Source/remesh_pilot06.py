"""審査後だけ所有File→PFS→Convertをcookする定義。単独では実行しない。"""
import ctypes
import hashlib
import json
import math
import shutil
import struct
import time
from pathlib import Path


def memory06(root):
    class MS(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in (
            'total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]
    class PM(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in (
            'peak_working', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
    ms = MS(); ms.length = ctypes.sizeof(ms)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    pm = PM(); pm.cb = ctypes.sizeof(pm)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(pm), pm.cb)
    return {'available_bytes': int(ms.available), 'private_bytes': int(pm.private),
            'working_set_bytes': int(pm.working), 'peak_working_since_process_bytes': int(pm.peak_working),
            'free_G_bytes': shutil.disk_usage(root).free}


def mesh_data06(geometry):
    return {'P': geometry.pointFloatAttribValues('P'),
            'indices': tuple(tuple(v.point().number() for v in p.vertices()) for p in geometry.prims()),
            'primitive_type_closed': tuple((str(p.type()), bool(p.isClosed())) for p in geometry.prims())}


def mesh_hash06(data):
    p = struct.pack('<%dd' % len(data['P']), *data['P'])
    topology = json.dumps([data['indices'], data['primitive_type_closed']], separators=(',', ':')).encode('utf8')
    return {'P_float64_sha256': hashlib.sha256(p).hexdigest(), 'oriented_topology_sha256': hashlib.sha256(topology).hexdigest()}


def input_signature06(hou_api, geometry):
    held = {v.point().number() for prim in geometry.prims() for v in prim.vertices()}
    particles = [p for p in geometry.points() if p.number() not in held]
    assert particles and all(geometry.findPointAttrib(a) is not None for a in ('id', 'v', 'pscale'))
    rows = sorted((int(p.attribValue('id')), *map(float, p.position()), *map(float, p.attribValue('v')), float(p.attribValue('pscale'))) for p in particles)
    assert len({r[0] for r in rows}) == len(rows) and all(math.isfinite(v) for r in rows for v in r[1:])
    payload = b''.join(struct.pack('<q7d', *r) for r in rows)
    fields = []
    for p in geometry.prims():
        assert isinstance(p, hou_api.Volume), '04のraw field型が変わった'
        values = p.allVoxels()
        assert all(math.isfinite(v) for v in values)
        fields.append({'name': p.attribValue('name'), 'resolution': list(p.resolution()),
                       'transform': list(p.transform().asTuple()), 'voxel_m': list(p.voxelSize()),
                       'values_float64_sha256': hashlib.sha256(struct.pack('<%dd' % len(values), *values)).hexdigest(),
                       'is_sdf_metadata': bool(p.isSDF())})
    return {'particle_count': len(rows), 'held_point_count': len(held), 'point_count': len(geometry.points()),
            'ID_P_v_pscale_float64_sha256': hashlib.sha256(payload).hexdigest(), 'fields': fields,
            'all_point_P_float64_sha256': hashlib.sha256(struct.pack('<%dd' % (len(geometry.points()) * 3), *geometry.pointFloatAttribValues('P'))).hexdigest()}


def definition06(node):
    definition = node.type().definition()
    assert definition is not None
    sections = {}
    for name, section in sorted(definition.sections().items()):
        value = section.contents()
        value = value.encode('utf8') if isinstance(value, str) else value
        sections[name] = hashlib.sha256(value).hexdigest()
    path = Path(definition.libraryFilePath())
    return {'type': node.type().name(), 'library_name': path.name,
            'library_sha256': file_sha(path) if path.is_file() else None, 'section_sha256': sections}


def parameters06(node, owner_path):
    def simple(value):
        if value is None or isinstance(value, (bool, int)): return value
        if isinstance(value, str): return value.replace(owner_path, '<OWNED>')
        if isinstance(value, float):
            assert math.isfinite(value)
            return value
        if isinstance(value, (tuple, list)): return [simple(v) for v in value]
        raise TypeError('未対応の評価parm型: ' + type(value).__name__)
    result = {}
    for p in node.parms():
        kind = p.parmTemplate().type()
        if kind == hou.parmTemplateType.Button:
            continue
        value = p.eval()
        if kind == hou.parmTemplateType.Ramp:
            result[p.name()] = {'kind': 'Ramp', 'keys': simple(value.keys()), 'values': simple(value.values()),
                                'basis': [str(v) for v in value.basis()]}
        elif kind == hou.parmTemplateType.Menu:
            items = list(p.menuItems())
            assert isinstance(value, int) and 0 <= value < len(items)
            result[p.name()] = {'kind': 'Menu', 'index': value, 'token': items[value], 'items': items}
        else:
            result[p.name()] = simple(value)
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


def set_verified06(hou_api, parm, requested):
    """Menuのevalは索引。文字列tokenと数値評価を混同しない。"""
    assert parm is not None
    parm.set(requested)
    raw = parm.eval()
    is_menu = parm.parmTemplate().type() == hou_api.parmTemplateType.Menu
    effective = raw
    if is_menu:
        assert isinstance(raw, int) and 0 <= raw < len(parm.menuItems())
        effective = parm.menuItems()[raw]
    assert effective == requested
    return {'requested': requested, 'raw_evaluated': raw, 'menu_token': effective if is_menu else None}


def native_first06(hou_api, geometry, x):
    pos, normal, uvw = hou_api.Vector3(), hou_api.Vector3(), hou_api.Vector3()
    number = geometry.intersect(hou_api.Vector3((x, .4, 0)), hou_api.Vector3((0, -1, 0)), pos, normal, uvw)
    return None if number < 0 else finite_native_hit(number, pos, normal, uvw)


def remesh_one06(hou_api, key, obj_path, stage, expected, plan, paths, prior_record, base_private, previous_cooks):
    """失敗時も観測済み部分をJSONへ残す。完了したRPCの外側がfinally復元する。"""
    started = time.monotonic()
    record = {'stage': stage, 'sample': expected['sample'], 'seconds': expected['seconds'],
              'passed_for_next': False, 'new_solver_executed': False, 'raw_input_modified': False,
              'observations': {}, 'resource_readings': []}
    own = hou_api.node(obj_path)
    state = getattr(hou_api.session, key)
    assert own is not None and any(node == own and sid == node.sessionId() for node, sid in state['owned_nodes'])
    limits = plan['budgets']
    def health():
        value = memory06(str(Path(paths['mesh_output']).anchor))
        record['resource_readings'].append(value)
        check = resource_decision(value, base_private, previous_cooks + record.get('cook_seconds_list', []), 142, limits)
        record['last_resource_check'] = check
        if not check['passed']: raise RuntimeError('資源保護により停止')
        if time.monotonic() - started > limits['per_rpc_cooperative_seconds']: raise TimeoutError('1RPCの協調予算超過')
    try:
        assert stage in ('replay', 'refine') and hou_api.fps() == 24 and hou_api.updateModeSetting() == hou_api.updateMode.Manual
        health()
        raw_path, old_mesh = Path(paths['raw']), Path(paths['original_mesh'])
        assert file_sha(raw_path) == expected['pilot']['sha256'] and file_sha(old_mesh) == expected['mesh']['sha256']
        raw = hou_api.Geometry(); raw.loadFromFile(str(raw_path))
        original = hou_api.Geometry(); original.loadFromFile(str(old_mesh))
        assert not own.children(), '前RPCの所有SOPが残っている'
        # Manualのまま04と同じ絶対評価時刻へ置く。新しいDOPやsolverは存在しない。
        hou_api.setFrame(expected['global_frame'])
        assert abs(hou_api.frame() - expected['global_frame']) < 1e-8
        record['actual_global_frame'] = hou_api.frame()
        geo = own.createNode('geo', node_name='meshing_only', run_init_scripts=False)
        geo.setDisplayFlag(False)
        reader = geo.createNode('file', node_name='literal_cache', run_init_scripts=False)
        assert not reader.inputs() and '$' not in str(raw_path)
        reader.parm('file').set(raw_path.as_posix())
        particles = geo.createNode('null', node_name='SOLVER_FIELDS_PARTICLES', run_init_scripts=False)
        particles.setInput(0, reader)
        pfs = geo.createNode('particlefluidsurface::3.0', node_name='display_meshing_only', run_init_scripts=False, exact_type_name=True)
        pfs.setInput(0, particles)
        assert pfs.type().name() == plan['node_types']['PFS']
        settings = dict(plan['mesh_parameters'])
        if stage == 'refine': settings['voxelsize'] = .25
        settings_readback = {}
        for name, value in settings.items():
            assert pfs.parm(name) is not None, '必要PFS parmがない: ' + name
            settings_readback[name] = set_verified06(hou_api, pfs.parm(name), value)
        convert = geo.createNode('convert', node_name='display_polygons', run_init_scripts=False)
        convert.setInput(0, pfs)
        convert_readback = set_verified06(hou_api, convert.parm('totype'), 'poly')
        out = geo.createNode('null', node_name='DISPLAY_SURFACE', run_init_scripts=False)
        out.setInput(0, convert)
        # 入力は原BGEO全体。field保持点をPFS入力から勝手に取り除かない。
        reader.cook(force=True)
        particles.cook(force=True)
        from_file = particles.geometry().freeze()
        direct_signature = input_signature06(hou_api, raw)
        file_signature = input_signature06(hou_api, from_file)
        record['observations']['input_signature'] = direct_signature
        assert direct_signature == file_signature, 'File SOP入力読戻し不一致'
        definition = definition06(pfs)
        actual_parameters = parameters06(pfs, obj_path)
        convert_parameters = parameters06(convert, obj_path)
        record['observations'].update(PFS_definition=definition, PFS_parameters=actual_parameters, convert_parameters=convert_parameters,
                                      explicit_settings_readback=settings_readback, convert_readback=convert_readback,
                                      requested_voxel_scale=settings['voxelsize'], expected_voxel_m=.04 * settings['voxelsize'],
                                      actual_output_volume_voxel_measured=False)
        if stage == 'refine':
            assert prior_record is not None and prior_record['stage'] == 'replay' and prior_record['sample'] == expected['sample'] and prior_record['passed_for_next']
            before = prior_record['observations']
            parameter_check = parameter_pair(before['PFS_parameters'], actual_parameters)
            record['observations']['parameter_pair'] = parameter_check
            assert parameter_check['passed'] and definition == before['PFS_definition'] and convert_parameters == before['convert_parameters']
            assert direct_signature == before['input_signature']
        health()
        cook_start = time.monotonic()
        out.cook(force=True)
        record['cook_seconds_list'] = [time.monotonic() - cook_start]
        record['node_messages'] = {n.name(): {'errors': list(n.errors()), 'warnings': list(n.warnings())} for n in (reader, particles, pfs, convert, out)}
        assert not any(v['errors'] or v['warnings'] for v in record['node_messages'].values()), '所有SOPの警告/エラー'
        generated = out.geometry().freeze()
        observed = mesh_data06(generated); source = mesh_data06(original)
        assert observed['P'] and observed['indices'] and all(math.isfinite(v) for v in observed['P'])
        record['observations']['mesh_fingerprint'] = mesh_hash06(observed)
        record['observations']['old_mesh_fingerprint'] = mesh_hash06(source)
        record['observations']['mesh_counts'] = {'points': len(generated.points()), 'faces': len(generated.prims())}
        # 交点queryが失敗しても生成済みの幾何は再検査できるよう先に保存する。
        destination = Path(paths['mesh_output']); assert not destination.exists()
        generated.saveToFile(str(destination))
        record['mesh_output'] = {'filename': destination.name, 'sha256': file_sha(destination), 'bytes': destination.stat().st_size}
        if destination.stat().st_size > limits['maximum_mesh_bytes']: raise RuntimeError('面キャッシュ容量上限')
        reread = hou_api.Geometry(); reread.loadFromFile(str(destination))
        assert compare_mesh_data(observed, mesh_data06(reread))['passed'], '生成面の保存読戻し不一致'
        health()
        native_new = [native_first06(hou_api, generated, x) for x in plan['gauge_x_m']]
        native_old = [native_first06(hou_api, original, x) for x in plan['gauge_x_m']]
        record['observations']['native_new'] = native_new
        record['observations']['native_original'] = native_old
        record['observations']['original_record_parity'] = all(h is not None and abs(h['position_m'][1] - g['mesh_eta_m']) <= 1e-6 for h, g in zip(native_old, expected['gauges']))
        if stage == 'replay':
            parity = compare_mesh_data(source, observed)
            parity['native_exact'] = native_new == native_old
            parity['passed'] = parity['passed'] and parity['native_exact'] and record['observations']['original_record_parity']
            record['observations']['strict_old_parity'] = parity
        if stage == 'replay' and not record['observations']['strict_old_parity']['passed']:
            record['hold_reason_ja'] = '原.5幾何の厳密配対が不成立。再設定・並替え・許容差拡大せず停止。'
        else:
            # 05の公開済み原関数を使う。候補のcenter errorは差であり、ゼロを要求しない。
            reader_expected = {'sample': expected['sample'], 'mesh_sha256': file_sha(destination), 'solver_sha256': expected['pilot']['sha256'],
                               'mesh_points': len(generated.points()), 'mesh_faces': len(generated.prims()), 'gauges': expected['gauges']}
            profile_plan = {'gauge_x_m': plan['gauge_x_m'], 'intersection': plan['intersection'],
                            'budgets': {'per_pair_cooperative_seconds': limits['per_rpc_cooperative_seconds'],
                                        'minimum_available_RAM_bytes': limits['minimum_available_RAM_bytes']}}
            profile = read_pair(hou_api, destination, raw_path, reader_expected, profile_plan)
            profile['center_original_mesh_comparison_role'] = 'STRICT_REPLAY_PARITY' if stage == 'replay' else 'CANDIDATE_MINUS_ORIGINAL_DIFFERENCE'
            profile['center_parity_required_for_this_stage'] = stage == 'replay'
            profile['comparison_meaning_ja'] = ('旧.5の中央原観測配対。' if stage == 'replay' else
                '.25のcenter_mesh_error_mは旧.5との差。center_parity_passed=falseはこの差だけなら失敗ではない。原solver配対は両stageで必要。')
            record['profiles_readback'] = profile
            acceptance = profile_acceptance(profile, prior_record['profiles_readback'] if stage == 'refine' else None)
            record['observations']['profile_acceptance'] = acceptance
            assert all(abs(p['center_solver_error_m']) <= 1e-8 for p in profile['profiles'] if 'center_solver_error_m' in p), '原solver符号場の観測が不一致'
            record['passed_for_next'] = acceptance['passed']
            if not acceptance['passed']: record['hold_reason_ja'] = '原観測を保存した。局所形状/数値queryの不一致を審査する。'
        assert file_sha(raw_path) == expected['pilot']['sha256'] and file_sha(old_mesh) == expected['mesh']['sha256']
        health()
    except Exception as exc:
        record['passed_for_next'] = False
        record['failure_type'] = type(exc).__name__
        record['failure_message_local'] = str(exc)
    finally:
        record['total_seconds'] = time.monotonic() - started
        # 完了したRPCだけがここへ到達する。所有scope内のSOPだけを片付ける。
        try:
            for node in own.children(): node.destroy()
            record['owned_pair_children_removed'] = not own.children()
        except Exception as exc:
            record['passed_for_next'] = False; record['owned_pair_cleanup_error'] = type(exc).__name__
    return record
