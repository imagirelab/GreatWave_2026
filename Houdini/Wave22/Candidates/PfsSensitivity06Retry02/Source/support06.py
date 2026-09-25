"""既に凍結した定義から抽出した補助関数。HOM呼出しは関数内だけ。"""
import ctypes
import hashlib
import json
import math
import shutil
import struct
from pathlib import Path

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

