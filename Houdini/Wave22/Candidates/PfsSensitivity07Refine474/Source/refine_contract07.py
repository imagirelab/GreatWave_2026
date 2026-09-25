"""07だけの固定時刻・資源・公開05照合。HOMや通信を呼ばない。"""
import gzip
import hashlib
import json
from pathlib import Path


def typed_equal07(a, b):
    """別RPCのnamespaceでもローカルmoduleのimportを必要としない比較。"""
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(typed_equal07(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(typed_equal07(x, y) for x, y in zip(a, b))
    return a == b

PROFILE_KEYS = (
    'sample', 'seconds', 'mesh_sha256', 'solver_sha256', 'mesh_points', 'mesh_faces',
    'mesh_P_float64_sha256', 'field', 'profiles', 'spatial_neighbour_differences',
    'center_parity_passed', 'strict_incidence_consistency_passed',
    'strict_incidence_mismatch_profile_indices', 'solver_executed', 'nodes_created',
)


def target07(plan):
    assert type(plan['sample']) is int and plan['sample'] == 474
    assert plan['scope'] == 'ONE_K474_QUARTER_MESH_SENSITIVITY_ONLY'
    assert plan['seconds'] == 7.9 and plan['global_frame'] == 1 + .4 * 474 and plan['fps'] == 24
    assert plan['record']['sample'] == 474 and plan['record']['seconds'] == 7.9
    assert abs(plan['record']['global_frame'] - plan['global_frame']) < 1e-8
    assert plan['record']['pilot']['filename'] == 'pilot_474.bgeo.sc'
    assert plan['record']['mesh']['filename'] == 'mesh_474.bgeo.sc'
    assert plan['expected_input_counts'] == {'points': 53838, 'primitives': 5, 'actual_particles': 53833}
    assert plan['expected_evaluated_PFS_parameter_count'] == 166
    assert plan['mesh_parameters']['voxelsize'] == .25
    assert plan['other_samples_allowed'] is False and plan['new_solver'] is False and plan['detector_executed'] is False
    limits = plan['budgets']
    assert limits['minimum_start_free_G_bytes'] == 15636365312
    assert limits['minimum_free_G_bytes'] == 10 * 1024**3
    return True


def initial_disk07(free_bytes, plan):
    assert type(free_bytes) is int and free_bytes >= plan['budgets']['minimum_start_free_G_bytes'], '開始G空き保護'
    return {'free_G_bytes': free_bytes, 'minimum_start_free_G_bytes': plan['budgets']['minimum_start_free_G_bytes'], 'passed': True}


def profile_projection07(value):
    return {key: value[key] for key in PROFILE_KEYS}


def projection_fingerprint07(value):
    data = json.dumps(profile_projection07(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read_profile_baseline07(root, row):
    compressed = (Path(root) / row['path']).read_bytes()
    assert len(compressed) == row['bytes'] and hashlib.sha256(compressed).hexdigest() == row['sha256']
    raw = gzip.decompress(compressed)
    assert len(raw) == row['original_bytes'] and hashlib.sha256(raw).hexdigest() == row['original_sha256']
    value = json.loads(raw)
    assert value['sample'] == 474 and len(value['profiles']) == 195
    assert projection_fingerprint07(value) == row['comparison_projection']
    return value


def compare_profile05_07(reference, observed):
    differences = [key for key in PROFILE_KEYS
                   if key not in reference or key not in observed or not typed_equal07(reference[key], observed[key])]
    return {'passed': not differences, 'different_fields': differences,
            'reference_projection': projection_fingerprint07(reference),
            'observed_projection': projection_fingerprint07(observed) if all(k in observed for k in PROFILE_KEYS) else None,
            'meaning_ja': '旧面だけを公開05の195断面へ配対。最上位の時間・資源・説明・実行metadataは比較外。行内文字列も厳密比較する。新面との高さ差は別の診断。'}
