"""22改訂候補：固定窓の純粋な判定と段階制御。Houdiniを起動しない。"""
import math
import statistics


def evaluate_gate(samples, conditions, end_seconds):
    """実SDFを未補正で検査する。欠損・非有限・駆動済み入力は拒否する。"""
    rate = conditions['solver_sampling_hz']
    gate = conditions['stability_gate']
    width = gate['window_seconds']
    last = round(end_seconds * rate)
    assert rate == 60 and end_seconds >= 2 * width
    assert end_seconds == conditions['piston_start_absolute_seconds']
    assert len(samples) == last + 1
    positions = [(g['x'], g['z']) for g in samples[0]['gauges']]
    assert len(positions) == 3 and len(set(positions)) == 3
    for k, row in enumerate(samples):
        assert row['sample'] == k and abs(row['requested_seconds'] - k / rate) < 1e-9
        assert abs(row['simulation_seconds'] - k / rate) < 1e-6
        assert abs(row['global_frame'] - (1 + k / rate * conditions['global_fps'])) < 1e-7
        assert abs(row['simulation_dt'] - 1 / 120) < 1e-9
        assert row['piston_displacement_m'] == row['piston_velocity_m_s'] == 0
        assert row['finite_pv'] and row['particle_ids_unique']
        assert not row['solver_errors'] and not row['solver_warnings']
        assert row['outside_inner_walls_beyond_20mm'] == 0
        assert [(g['x'], g['z']) for g in row['gauges']] == positions
        assert all(g['valid'] and math.isfinite(g['eta_m']) for g in row['gauges'])
        assert math.isfinite(row['negative_voxel_volume_proxy_m3'])
        assert row['negative_voxel_volume_proxy_m3'] > 0
    windows = []
    for left, right in ((end_seconds - 2 * width, end_seconds - width),
                        (end_seconds - width, end_seconds)):
        rows = [r for r in samples if left + 1e-8 < r['requested_seconds'] <= right + 1e-8]
        assert len(rows) == round(width * rate)
        times = [r['requested_seconds'] for r in rows]
        mean_t = statistics.mean(times)
        gauges = []
        for index, (x, z) in enumerate(positions):
            values = [r['gauges'][index]['eta_m'] for r in rows]
            mean = statistics.mean(values)
            slope = sum((t - mean_t) * (h - mean) for t, h in zip(times, values)) / sum((t - mean_t) ** 2 for t in times)
            gauges.append({'x_m': x, 'z_m': z, 'mean_eta_m': mean,
                           'residual_rms_about_mean_m': math.sqrt(statistics.mean((h - mean) ** 2 for h in values)),
                           'linear_trend_m_s': slope, 'trend_change_per_window_m': slope * width})
        windows.append({'left_open_seconds': left, 'right_closed_seconds': right,
                        'count': len(rows), 'gauges': gauges,
                        'negative_voxel_proxy_mean_m3': statistics.mean(r['negative_voxel_volume_proxy_m3'] for r in rows),
                        'negative_voxel_proxy_first_last_m3': [rows[0]['negative_voxel_volume_proxy_m3'], rows[-1]['negative_voxel_volume_proxy_m3']],
                        'particle_count_first_last': [rows[0]['particle_count'], rows[-1]['particle_count']],
                        'particle_velocity_rms_mean_m_s': statistics.mean(r['particle_velocity_rms_m_s'] for r in rows),
                        'particle_velocity_rms_max_m_s': max(r['particle_velocity_rms_m_s'] for r in rows),
                        'particle_velocity_max_m_s': max(r['particle_velocity_max_m_s'] for r in rows)})
    checks = []
    for a, b in zip(windows[0]['gauges'], windows[1]['gauges']):
        change = b['mean_eta_m'] - a['mean_eta_m']
        checks.append({'x_m': a['x_m'], 'mean_change_m': change,
                       'mean_change_passed': abs(change) <= gate['maximum_mean_change_m'],
                       'both_rms_passed': max(a['residual_rms_about_mean_m'], b['residual_rms_about_mean_m']) <= gate['maximum_residual_rms_m'],
                       'both_trend_passed': max(abs(a['trend_change_per_window_m']), abs(b['trend_change_per_window_m'])) <= gate['maximum_linear_trend_change_per_window_m']})
    proxy_change = windows[1]['negative_voxel_proxy_mean_m3'] / windows[0]['negative_voxel_proxy_mean_m3'] - 1
    passed = all(c['mean_change_passed'] and c['both_rms_passed'] and c['both_trend_passed'] for c in checks) and abs(proxy_change) <= gate['maximum_proxy_relative_window_change']
    return {'end_seconds': end_seconds, 'windows': windows, 'gauge_checks': checks,
            'proxy_relative_window_change': proxy_change, 'diagnostic_stability_passed': passed,
            'wave_verified': False, 'physical_accuracy_verified': False,
            'meaning_ja': '静水待機の駆動許可条件だけ。SDF代理量は実水量ではない。'}


def check_resources(rows, budget, baseline_private_bytes, free_bytes, final_index):
    """各標本を保存した後、次をcookする前の運用停止条件。物理精度判定ではない。"""
    row = rows[-1]
    assert row['memory']['available_physical_bytes'] >= budget['minimum_available_ram_bytes'], '空きRAM不足'
    assert row['memory']['private_commit_bytes'] - baseline_private_bytes <= budget['maximum_private_growth_bytes'], '私有コミット増加上限'
    assert row['simulation_memory_bytes'] <= budget['maximum_dop_cache_bytes'], '所有DOPキャッシュ上限'
    assert free_bytes >= budget['minimum_disk_free_bytes'], 'Gドライブ空き容量不足'
    assert row['cook_seconds'] <= budget['maximum_sample_seconds'], '標本計算時間上限'
    recent = rows[-budget['recent_window_samples']:]
    median = statistics.median(r['cook_seconds'] for r in recent)
    remaining = max(0, final_index - row['sample'])
    if len(recent) == budget['recent_window_samples']:
        assert median <= budget['maximum_recent_median_seconds'], '直近計算費用の上限'
        assert median * remaining <= budget['maximum_projected_remaining_seconds'], '残り計算時間予測の上限'
    return {'recent_median_cook_seconds': median, 'projected_remaining_cook_seconds': median * remaining,
            'free_disk_bytes': free_bytes, 'private_growth_bytes': row['memory']['private_commit_bytes'] - baseline_private_bytes}


async def run_phases(sample_one, decide, authorize, static_last, final_last):
    """FAIL時は許可・追加標本を一切呼ばない。実行と模擬実行が同じ分岐を使う。"""
    assert 0 <= static_last < final_last
    for index in range(static_last + 1):
        await sample_one(index)
    gate = await decide()
    if not gate['diagnostic_stability_passed']:
        return {'status': 'STATIC_GATE_FAILED', 'last_sample': static_last, 'drive_authorized': False}
    await authorize(gate)
    for index in range(static_last + 1, final_last + 1):
        await sample_one(index)
    return {'status': 'OBSERVATION_CHECKPOINT_REACHED', 'last_sample': final_last, 'drive_authorized': True}
