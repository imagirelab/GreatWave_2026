"""面化候補の順序・厳密配対・予算・応答入力を検査する純関数。"""
import copy
import json
import math
import statistics


def finite_native_hit(primitive, position, normal, uvw):
    """異常をNaNのままJSONへ流さず、例外文字列に原値を保持する。"""
    raw = {'primitive': primitive, 'position_m': list(position), 'normal': list(normal), 'uvw': list(uvw)}
    if not all(math.isfinite(v) for name in ('position_m', 'normal', 'uvw') for v in raw[name]):
        raise ValueError('native交点の非有限値: ' + repr(raw))
    return raw


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


def schedule(plan):
    return [('replay', k) for k in plan['pilot_samples']] + [('refine', k) for k in plan['pilot_samples']]


def allow_next(completed, next_stage, plan):
    ordered = schedule(plan)
    if len(completed) >= len(ordered) or next_stage != ordered[len(completed)]:
        return False
    return all(r['passed_for_next'] and (r['stage'], r['sample']) == ordered[i]
               for i, r in enumerate(completed))


def compare_mesh_data(reference, replay):
    """頂点/面の並替えによる救済はしない。原bytesの同一性とは区別する。"""
    checks = {name: reference[name] == replay[name] for name in ('P', 'indices', 'primitive_type_closed')}
    checks['finite'] = all(math.isfinite(v) for data in (reference, replay) for v in data['P'])
    return {'passed': all(checks.values()), 'checks': checks,
            'reference_points': len(reference['P']) // 3, 'replay_points': len(replay['P']) // 3,
            'reference_faces': len(reference['indices']), 'replay_faces': len(replay['indices'])}


def parameter_pair(reference, candidate):
    """同時刻・同じノード定義の全評価parmを比べる。変更可はvoxelsizeだけ。"""
    differing = sorted(k for k in reference.keys() | candidate.keys() if reference.get(k) != candidate.get(k))
    return {'passed': differing == ['voxelsize'] and reference.get('voxelsize') == .5 and candidate.get('voxelsize') == .25,
            'different_parameters': differing}


def resource_decision(reading, base_private, elapsed_cooks, remaining, limits):
    recent = elapsed_cooks[-30:]
    estimate = statistics.median(recent) * remaining if recent else 0
    checks = {
        'available_RAM': reading['available_bytes'] >= limits['minimum_available_RAM_bytes'],
        'private_increase': reading['private_bytes'] - base_private < limits['maximum_private_increase_bytes'],
        'free_G': reading['free_G_bytes'] >= limits['running_minimum_free_G_bytes'],
        'latest_cook': not recent or recent[-1] < limits['maximum_cook_seconds'],
        'recent_30': len(recent) < 30 or statistics.median(recent) < limits['recent_30_median_seconds'],
        'projected_remaining': estimate < limits['maximum_projected_remaining_seconds']}
    return {'passed': all(checks.values()), 'checks': checks, 'projected_remaining_seconds': estimate,
            'recent_count': len(recent), 'median_seconds': statistics.median(recent) if recent else None}


def make_response_rows(original, remeshed):
    """別放行後の142面が全部揃った場合だけ、原detector用入力を作る。"""
    expected = list(range(272, 555, 2))
    assert sorted(remeshed) == expected and len(original) == 556
    out = copy.deepcopy(original)
    for k, row in enumerate(out):
        assert row['sample'] == k
        # これはdetector専用派生入力。旧meshのhash/点面数を新高さへ誤結合しない。
        row['derived_for_detector_only'] = True
        for field in ('mesh_file_sha256', 'mesh_points', 'mesh_faces', 'mesh_cache_reread_P_match'):
            row[field] = None
        row['mesh_sampled'] = k in remeshed
        if k in remeshed:
            heights = remeshed[k]
            assert len(heights) == 3 and all(v is not None and math.isfinite(v) for v in heights)
            for g, eta in zip(row['gauges'], heights):
                g['mesh_eta_m'] = eta
                g['mesh_sampled'] = True
                g['mesh_vertical_hit_valid'] = True
                g['mesh_minus_solver_m'] = eta - g['eta_m']
        else:
            for g in row['gauges']:
                g['mesh_sampled'] = False
                g['mesh_eta_m'] = None
                g['mesh_vertical_hit_valid'] = False
                g['mesh_minus_solver_m'] = None
    return out


def profile_acceptance(result, reference=None):
    """無効をゼロで補わず、数値整合と局所形状を分けて保留する。"""
    reasons = []
    for i, row in enumerate(result['profiles']):
        strict = row['strict_distinct_height_hits']['hits']
        sensitive = row['sensitivity_distinct_height_hits']['hits']
        if not row['strict_incidence_consistency']['passed']:
            reasons.append([i, 'QUERY_INCIDENCE_MISMATCH'])
        if not row['field_profile']['single_wet_to_dry_local']:
            reasons.append([i, 'FIELD_AMBIGUOUS'])
        if row['native_default_first'] is None or not strict:
            reasons.append([i, 'MISSING_INTERSECTION'])
        else:
            first = row['native_default_first']
            if abs(first['position_m'][1] - strict[0]['position_m'][1]) > 1e-6:
                reasons.append([i, 'DEFAULT_STRICT_MISMATCH'])
            if sum(a * b for a, b in zip(first['normal'], strict[0]['normal'])) <= 0:
                reasons.append([i, 'DEFAULT_STRICT_NORMAL_MISMATCH'])
            # 共有辺では別primitiveでもよいが、default自体も面限定queryで裏付ける。
            if not any(p['primitive'] == first['primitive'] and abs(p['position_m'][1] - first['position_m'][1]) <= 1e-6
                       for p in row['unmerged_primitive_incidences']):
                reasons.append([i, 'DEFAULT_INCIDENCE_MISMATCH'])
        if len(strict) != len(sensitive) or any(abs(a['position_m'][1] - b['position_m'][1]) > 1e-6 for a, b in zip(strict, sensitive)):
            reasons.append([i, 'TOLERANCE_SENSITIVITY'])
        if reference is not None:
            previous = reference['profiles'][i]['strict_distinct_height_hits']['hits']
            if len(strict) != len(previous):
                reasons.append([i, 'LOCAL_INTERSECTION_COUNT_CHANGED'])
            if strict and previous and strict[0]['normal'][1] * previous[0]['normal'][1] <= 0:
                reasons.append([i, 'UPPER_NORMAL_DIRECTION_CHANGED'])
    return {'passed': not reasons, 'hold_reasons': reasons,
            'meaning_ja': '局所交点の数値/形状保留判定だけ。全域トポロジー・非砕波・物理精度の合格ではない。'}
