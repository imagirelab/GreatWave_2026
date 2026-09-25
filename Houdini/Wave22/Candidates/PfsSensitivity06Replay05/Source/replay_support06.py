"""凍結済み関数をそのまま抽出。定義の読込ではHOMを実行しない。"""

import ctypes
import hashlib
import json
import math
import shutil
import struct
from pathlib import Path
from copy import deepcopy

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

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

def input_signature06(hou_api, geometry, observe=None):
    held = {v.point().number() for prim in geometry.prims() for v in prim.vertices()}
    particles = [p for p in geometry.points() if p.number() not in held]
    diagnostic = {'point_count': len(geometry.points()), 'held_point_count': len(held), 'particle_count': len(particles),
                  'attribute_presence': {a: geometry.findPointAttrib(a) is not None for a in ('id', 'v', 'pscale')},
                  'attribute_types': {a: str(geometry.findPointAttrib(a).dataType()) if geometry.findPointAttrib(a) is not None else None for a in ('id', 'v', 'pscale')},
                  'primitive_types': [str(p.type()) for p in geometry.prims()]}
    if observe: observe(diagnostic)
    assert particles and all(diagnostic['attribute_presence'].values()), '粒子集合または必須属性がない'
    rows = sorted((int(p.attribValue('id')), *map(float, p.position()), *map(float, p.attribValue('v')), float(p.attribValue('pscale'))) for p in particles)
    seen = set(); duplicates = []
    for row in rows:
        if row[0] in seen: duplicates.append(row[0])
        seen.add(row[0])
    bad = next(([r[0], j, repr(v)] for r in rows for j, v in enumerate(r[1:]) if not math.isfinite(v)), None)
    diagnostic.update(first_ID=rows[0][0] if rows else None, last_ID=rows[-1][0] if rows else None,
                      duplicate_ID_count=len(duplicates), first_duplicate_ID=duplicates[0] if duplicates else None, first_nonfinite_particle=bad)
    if observe: observe(diagnostic)
    assert not duplicates and bad is None, 'ID重複または非有限粒子'
    payload = b''.join(struct.pack('<q7d', *r) for r in rows)
    fields = []
    for p in geometry.prims():
        assert isinstance(p, hou_api.Volume), '04のraw field型が変わった'
        values = p.allVoxels()
        bad_voxel = next(([i, repr(v)] for i, v in enumerate(values) if not math.isfinite(v)), None)
        diagnostic['last_field'] = {'name': p.attribValue('name'), 'voxel_count': len(values), 'first_nonfinite_voxel': bad_voxel}
        if observe: observe(diagnostic)
        assert bad_voxel is None, '非有限field voxel'
        fields.append({'name': p.attribValue('name'), 'resolution': list(p.resolution()),
                       'transform': list(p.transform().asTuple()), 'voxel_m': list(p.voxelSize()),
                       'values_float64_sha256': hashlib.sha256(struct.pack('<%dd' % len(values), *values)).hexdigest(),
                       'is_sdf_metadata': bool(p.isSDF())})
    return {'particle_count': len(rows), 'held_point_count': len(held), 'point_count': len(geometry.points()),
            'ID_P_v_pscale_float64_sha256': hashlib.sha256(payload).hexdigest(), 'fields': fields,
            'all_point_P_float64_sha256': hashlib.sha256(struct.pack('<%dd' % (len(geometry.points()) * 3), *geometry.pointFloatAttribValues('P'))).hexdigest()}

def menu_observation(raw, items):
    """HOMのint-indexとstr-tokenを区別して保存する。どちらも実tokenを照合する。"""
    if type(raw) is int and 0 <= raw < len(items):
        return {'raw_type': 'int', 'raw_value': raw, 'index': raw, 'token': items[raw], 'items': list(items)}
    if isinstance(raw, str) and raw in items:
        return {'raw_type': 'str', 'raw_value': raw, 'index': items.index(raw), 'token': raw, 'items': list(items)}
    raise ValueError('Menuのraw/index/tokenが不正: ' + repr({'raw': raw, 'items': items}))

def disconnected_file_inputs(inputs, connection_count):
    """未接続connectorのNone占位を接続済みと取り違えない。"""
    return all(node is None for node in inputs) and connection_count == 0

def classify_rpc_reply(text, is_error=False):
    """応答の実行状態を読めない場合は完了不明とし、cleanupを追加しない。"""
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return 'UNCERTAIN', None
    if not isinstance(body, dict) or type(body.get('executed')) is not bool:
        return 'UNCERTAIN', body
    if is_error or not body['executed'] or body.get('error') or body.get('eval_error'):
        return 'COMPLETE_ERROR', body
    return 'COMPLETE_SUCCESS', body

def serializable_observation(value):
    """数値異常は明示タグへ保持する。0や前値への補完ではない。"""
    anomalies = []
    def visit(item, path):
        if isinstance(item, float) and not math.isfinite(item):
            anomalies.append(path)
            return {'invalid_nonfinite_float': repr(item)}
        if isinstance(item, dict): return {k: visit(v, path + '/' + str(k)) for k, v in item.items()}
        if isinstance(item, (tuple, list)): return [visit(v, path + '/' + str(i)) for i, v in enumerate(item)]
        return item
    result = visit(value, '')
    if anomalies:
        result['passed_for_next'] = False
        result['nonfinite_observation_paths'] = anomalies
        result['failure_type'] = 'NonFiniteObservation'
    return result

def finite_value06(value):
    if value is None or isinstance(value, (bool, int, str)): return value
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('非有限属性値')
        return value
    if isinstance(value, (tuple, list)): return [finite_value06(v) for v in value]
    if isinstance(value, dict): return {str(k): finite_value06(v) for k, v in sorted(value.items())}
    raise TypeError('未対応の属性値型: ' + type(value).__name__)

def value_hash06(value):
    return hashlib.sha256(json.dumps(finite_value06(value), ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf8')).hexdigest()

def attribute_inventory06(geometry):
    return {label: [{'name': a.name(), 'type': str(a.dataType()), 'size': a.size(), 'array': a.isArrayType()}
                    for a in attrs()] for label, attrs in (
                        ('point', geometry.pointAttribs), ('primitive', geometry.primAttribs),
                        ('vertex', geometry.vertexAttribs), ('detail', geometry.globalAttribs))}

def all_geometry_signature06(hou_api, geometry):
    """全属性・群・接続と、粒子/5場の数値を別々に記録する。未知型は停止。"""
    result = input_signature06(hou_api, geometry)
    scopes = [('point', geometry.pointAttribs(), geometry.points()),
              ('primitive', geometry.primAttribs(), geometry.prims()),
              ('vertex', geometry.vertexAttribs(), tuple(v for p in geometry.prims() for v in p.vertices())),
              ('detail', geometry.globalAttribs(), (geometry,))]
    result['attribute_inventory'] = attribute_inventory06(geometry)
    result['attribute_value_sha256'] = {label: {a.name(): value_hash06([element.attribValue(a) for element in elements])
                                               for a in attrs} for label, attrs, elements in scopes}
    result['oriented_indices'] = [[v.point().number() for v in p.vertices()] for p in geometry.prims()]
    result['groups'] = {
        'point': {g.name(): [p.number() for p in g.points()] for g in geometry.pointGroups()},
        'primitive': {g.name(): [p.number() for p in g.prims()] for g in geometry.primGroups()},
        'vertex': {g.name(): [[v.prim().number(), v.number()] for v in g.vertices()] for g in geometry.vertexGroups()},
        'edge': {g.name(): [sorted(p.number() for p in edge.points()) for edge in g.edges()] for g in geometry.edgeGroups()}}
    return result

def parm_record06(parm):
    template = parm.parmTemplate()
    result = {'name': parm.name(), 'label': template.label(), 'template_type': str(template.type()),
              'raw_value': parm.rawValue(), 'evaluated': finite_value06(parm.eval())}
    # Parm.menuItemsは非MenuでOperationFailed。template/動的Menuを先に判別する。
    template_items = list(template.menuItems()) if hasattr(template, 'menuItems') else []
    if str(template.type()) == 'parmTemplateType.Menu' or template_items or parm.isDynamicMenu():
        result['menu_items'] = list(parm.menuItems()); result['menu_labels'] = list(parm.menuLabels())
    return result

def node_state06(node, hou_api):
    return {'name': node.name(), 'type': node.type().name(), 'cook_count': node.cookCount(),
            'needs_to_cook': node.needsToCook(), 'needs_to_cook_at_seconds': hou_api.time(), 'errors': list(node.errors()), 'warnings': list(node.warnings()),
            'display': node.isDisplayFlagSet(), 'render': node.isRenderFlagSet(), 'bypassed': node.isBypassed(),
            'hard_locked': node.isHardLocked(), 'soft_locked': node.isSoftLocked(), 'unload': node.isUnloadFlagSet()}

def mesh_data06(geometry):
    return {'P': geometry.pointFloatAttribValues('P'),
            'indices': tuple(tuple(v.point().number() for v in p.vertices()) for p in geometry.prims()),
            'primitive_type_closed': tuple((str(p.type()), bool(p.isClosed())) for p in geometry.prims())}

def mesh_hash06(data):
    p = struct.pack('<%dd' % len(data['P']), *data['P'])
    topology = json.dumps([data['indices'], data['primitive_type_closed']], separators=(',', ':')).encode('utf8')
    return {'P_float64_sha256': hashlib.sha256(p).hexdigest(), 'oriented_topology_sha256': hashlib.sha256(topology).hexdigest()}

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
            result[p.name()] = {'kind': 'Menu', **menu_observation(value, items)}
        else:
            result[p.name()] = simple(value)
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result

def set_verified06(hou_api, parm, requested, observe=None):
    """Menuの索引/文字列tokenを区別して実効値を照合する。"""
    assert parm is not None, '必要parmがない'
    evidence = {'requested': requested, 'requested_type': type(requested).__name__, 'template_type': str(parm.parmTemplate().type())}
    if observe: observe(evidence)
    parm.set(requested)
    raw = parm.eval()
    evidence.update(raw_value=raw, raw_type=type(raw).__name__)
    if observe: observe(evidence)
    is_menu = parm.parmTemplate().type() == hou_api.parmTemplateType.Menu
    effective = raw
    if is_menu:
        evidence['menu_items'] = list(parm.menuItems())
        if observe: observe(evidence)
        evidence['menu'] = menu_observation(raw, evidence['menu_items'])
        effective = evidence['menu']['token']
    evidence['effective'] = effective
    if observe: observe(evidence)
    assert effective == requested, '設定の要求値と実効値が異なる: ' + repr(evidence)
    return {**evidence, 'raw_evaluated': raw, 'menu_token': effective if is_menu else None}

def native_first06(hou_api, geometry, x):
    pos, normal, uvw = hou_api.Vector3(), hou_api.Vector3(), hou_api.Vector3()
    number = geometry.intersect(hou_api.Vector3((x, .4, 0)), hou_api.Vector3((0, -1, 0)), pos, normal, uvw)
    return None if number < 0 else finite_native_hit(number, pos, normal, uvw)

def finite_native_hit(primitive, position, normal, uvw):
    """異常をNaNのままJSONへ流さず、例外文字列に原値を保持する。"""
    raw = {'primitive': primitive, 'position_m': list(position), 'normal': list(normal), 'uvw': list(uvw)}
    if not all(math.isfinite(v) for name in ('position_m', 'normal', 'uvw') for v in raw[name]):
        raise ValueError('native交点の非有限値: ' + repr(raw))
    return raw

def compare_mesh_data(reference, replay):
    """頂点/面の並替えによる救済はしない。原bytesの同一性とは区別する。"""
    checks = {name: reference[name] == replay[name] for name in ('P', 'indices', 'primitive_type_closed')}
    checks['finite'] = all(math.isfinite(v) for data in (reference, replay) for v in data['P'])
    return {'passed': all(checks.values()), 'checks': checks,
            'reference_points': len(reference['P']) // 3, 'replay_points': len(replay['P']) // 3,
            'reference_faces': len(reference['indices']), 'replay_faces': len(replay['indices'])}

def exact(a, b):
    """数値の型も保持する。辞書のキー順だけはJSONの意味に含めない。"""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b and (not isinstance(a, float) or math.isfinite(a))

def canonical_signature(signature):
    """比較用の深い複製だけを変更する。名前重複は拒否する。"""
    result = deepcopy(signature)
    rows = result['attribute_inventory']['detail']
    if not isinstance(rows, list):
        raise ValueError('detail一覧は列挙リストでなければならない')
    by_name = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name']:
            raise ValueError('detail属性名が不正')
        if row['name'] in by_name:
            raise ValueError('detail属性名の重複')
        by_name[row['name']] = row
    result['attribute_inventory']['detail'] = by_name
    return result

def compare_signatures(direct, other):
    try:
        return exact(canonical_signature(direct), canonical_signature(other))
    except (KeyError, TypeError, ValueError):
        return False

def leaf_differences(a, b, path=''):
    """原列挙順の差分を失わず保存する。"""
    if type(a) is not type(b):
        return [{'path': path, 'direct': a, 'observed': b}]
    if isinstance(a, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                result.append({'path': path + '/' + key, 'missing_direct': key not in a, 'missing_observed': key not in b})
            else:
                result.extend(leaf_differences(a[key], b[key], path + '/' + key))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': path, 'direct_length': len(a), 'observed_length': len(b)}]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in leaf_differences(x, y, path + '/' + str(i))]
    return [] if exact(a, b) else [{'path': path, 'direct': a, 'observed': b}]
