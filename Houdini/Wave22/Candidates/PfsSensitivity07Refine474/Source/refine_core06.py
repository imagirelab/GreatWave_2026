"""単一面化感度の判定。波検出・閾値調整・HOM呼出しは行わない。"""
import math


def typed_equal06(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(typed_equal06(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(typed_equal06(x, y) for x, y in zip(a, b))
    return a == b


def same_parameters_except_voxel(reference, candidate):
    differences = sorted(k for k in reference.keys() | candidate.keys()
                         if k not in reference or k not in candidate or not typed_equal06(reference[k], candidate[k]))
    return {'passed': differences == ['voxelsize'] and reference.get('voxelsize') == .5 and candidate.get('voxelsize') == .25,
            'different_parameters': differences}


def profile_shape06(result, reference=None):
    """全原交点を別JSONへ保存してから、局所形状/queryの保留条件を評価する。"""
    reasons = []
    rows = result['profiles']
    if len(rows) != 195 or reference is not None and len(reference['profiles']) != 195:
        return {'passed': False, 'hold_reasons': [[None, 'PROFILE_COUNT']], 'physical_pass': False}
    coordinates = [(r['gauge'], r['dx_m'], r['x_m'], r['z_m']) for r in rows]
    if len(set(coordinates)) != 195:
        reasons.append([None, 'DUPLICATE_PROFILE_COORDINATES'])
    for i, row in enumerate(rows):
        strict = row['strict_distinct_height_hits']['hits']
        sensitive = row['sensitivity_distinct_height_hits']['hits']
        incidences = row['unmerged_primitive_incidences']
        first = row['native_default_first']
        raw_hits = strict + sensitive + incidences + ([] if first is None else [first])
        if not all(math.isfinite(v) for hit in raw_hits for key in ('position_m', 'normal', 'uvw') for v in hit[key]):
            reasons.append([i, 'NONFINITE_HIT']); continue
        if not row['strict_incidence_consistency']['passed']:
            reasons.append([i, 'QUERY_INCIDENCE_MISMATCH'])
        if not row['field_profile']['single_wet_to_dry_local']:
            reasons.append([i, 'FIELD_AMBIGUOUS'])
        if not row['strict_distinct_height_hits']['complete_within_step'] or not row['sensitivity_distinct_height_hits']['complete_within_step']:
            reasons.append([i, 'INCOMPLETE_INTERSECTIONS'])
        if first is None or not strict:
            reasons.append([i, 'MISSING_INTERSECTION'])
        else:
            if abs(first['position_m'][1] - strict[0]['position_m'][1]) > 1e-6:
                reasons.append([i, 'DEFAULT_STRICT_MISMATCH'])
            if sum(a * b for a, b in zip(first['normal'], strict[0]['normal'])) <= 0:
                reasons.append([i, 'DEFAULT_STRICT_NORMAL_MISMATCH'])
            if not any(p['primitive'] == first['primitive'] and abs(p['position_m'][1] - first['position_m'][1]) <= 1e-6 for p in incidences):
                reasons.append([i, 'DEFAULT_INCIDENCE_MISMATCH'])
        if len(strict) != len(sensitive) or any(abs(a['position_m'][1] - b['position_m'][1]) > 1e-6 for a, b in zip(strict, sensitive)):
            reasons.append([i, 'TOLERANCE_SENSITIVITY'])
        if 'center_solver_error_m' in row and (row['center_solver_error_m'] is None or not math.isfinite(row['center_solver_error_m']) or abs(row['center_solver_error_m']) > 1e-8):
            reasons.append([i, 'ORIGINAL_SOLVER_GAUGE_MISMATCH'])
        if reference is None:
            if 'center_parity_passed' in row and row['center_parity_passed'] is not True:
                reasons.append([i, 'ORIGINAL_MESH_GAUGE_MISMATCH'])
        else:
            old = reference['profiles'][i]
            if coordinates[i] != (old['gauge'], old['dx_m'], old['x_m'], old['z_m']):
                reasons.append([i, 'COORDINATE_MISMATCH'])
            if row['field_profile'] != old['field_profile']:
                reasons.append([i, 'UNCHANGED_FIELD_QUERY_MISMATCH'])
            previous = old['strict_distinct_height_hits']['hits']
            if len(strict) != len(previous):
                reasons.append([i, 'LOCAL_INTERSECTION_COUNT_CHANGED'])
            if strict and previous and strict[0]['normal'][1] * previous[0]['normal'][1] <= 0:
                reasons.append([i, 'UPPER_NORMAL_DIRECTION_CHANGED'])
    return {'passed': not reasons, 'hold_reasons': reasons, 'physical_pass': False,
            'meaning_ja': '局所交点の数値整合と形状の保留判定だけ。上下交点は複数自由面を意味せず、全域連通・非砕波・精度を認定しない。'}


def center_differences06(original, refined, gauges):
    assert len(original) == len(refined) == len(gauges) == 3
    rows = []
    for index, (old, new, gauge) in enumerate(zip(original, refined, gauges)):
        a = None if old is None else old['position_m'][1]
        b = None if new is None else new['position_m'][1]
        rows.append({'gauge': index + 1, 'x_m': gauge['x'], 'z_m': gauge['z'],
                     'old_mesh_eta_m': a, 'new_mesh_eta_m': b, 'solver_observed_eta_m': gauge['eta_m'],
                     'new_minus_old_m': None if a is None or b is None else b - a,
                     'old_minus_solver_m': None if a is None else a - gauge['eta_m'],
                     'new_minus_solver_m': None if b is None else b - gauge['eta_m']})
    return rows
