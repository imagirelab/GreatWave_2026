"""静水待機の固定窓を診断する。波高を補正せず、駆動前の安定性だけを測る。"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('token')
parser.add_argument('--end', type=float, required=True)
args = parser.parse_args()
run = ROOT / 'Evidence/Curated_Runs' / args.token
source = run / '22_pilot_samples.json'
conditions_path = run / '22_pilot_conditions.json'
if not source.exists():
    run=ROOT/'Runs'/args.token/'Evidence'
    source=run/'22_pilot_samples.json';conditions_path=run/'22_pilot_conditions.json'
samples = json.loads(source.read_text(encoding='utf8'))['samples']
conditions = json.loads(conditions_path.read_text(encoding='utf8'))
gate = conditions['stability_gate']
window = gate['window_seconds']
assert args.end >= 2 * window and samples[-1]['requested_seconds'] >= args.end - 1e-7


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(a, b):
    # 左端を除き、右端を含む45標本。隣接窓で標本を重複させない。
    rows = [r for r in samples if a + 1e-8 < r['requested_seconds'] <= b + 1e-8]
    assert len(rows) == round(window * 60)
    assert all(r['piston_displacement_m'] == 0 and r['piston_velocity_m_s'] == 0 for r in rows)
    times = [r['requested_seconds'] for r in rows]
    mean_t = statistics.mean(times)
    gauges = []
    for g in range(len(rows[0]['gauges'])):
        assert all(r['gauges'][g]['valid'] for r in rows)
        eta = [r['gauges'][g]['eta_m'] for r in rows]
        avg = statistics.mean(eta)
        slope = sum((t-mean_t)*(h-avg) for t, h in zip(times, eta)) / sum((t-mean_t)**2 for t in times)
        gauges.append({'x_m': rows[0]['gauges'][g]['x'], 'z_m': rows[0]['gauges'][g]['z'],
                       'mean_eta_m': avg, 'depth_from_mean_solver_sdf_m': .6+avg,
                       'residual_rms_about_mean_m': math.sqrt(statistics.mean((h-avg)**2 for h in eta)),
                       'linear_trend_m_s': slope, 'trend_change_per_window_m': slope*window,
                       'min_eta_m': min(eta), 'max_eta_m': max(eta)})
    return {'left_open_seconds': a, 'right_closed_seconds': b, 'count': len(rows), 'gauges': gauges,
            'negative_voxel_proxy_mean_m3': statistics.mean(r['negative_voxel_volume_proxy_m3'] for r in rows),
            'negative_voxel_proxy_first_last_m3': [rows[0]['negative_voxel_volume_proxy_m3'], rows[-1]['negative_voxel_volume_proxy_m3']],
            'particle_count_first_last': [rows[0]['particle_count'], rows[-1]['particle_count']],
            'particle_velocity_rms_mean_m_s': statistics.mean(r['particle_velocity_rms_m_s'] for r in rows),
            'particle_velocity_rms_max_m_s': max(r['particle_velocity_rms_m_s'] for r in rows),
            'particle_velocity_max_m_s': max(r['particle_velocity_max_m_s'] for r in rows)}


windows = [measure(args.end-2*window, args.end-window), measure(args.end-window, args.end)]
checks = []
for a, b in zip(windows[0]['gauges'], windows[1]['gauges']):
    checks.append({'x_m': a['x_m'], 'mean_change_m': b['mean_eta_m']-a['mean_eta_m'],
                   'mean_change_passed': abs(b['mean_eta_m']-a['mean_eta_m']) <= gate['maximum_mean_change_m'],
                   'both_rms_passed': max(a['residual_rms_about_mean_m'], b['residual_rms_about_mean_m']) <= gate['maximum_residual_rms_m'],
                   'both_trend_passed': max(abs(a['trend_change_per_window_m']), abs(b['trend_change_per_window_m'])) <= gate['maximum_linear_trend_change_per_window_m']})
proxy_change = windows[1]['negative_voxel_proxy_mean_m3']/windows[0]['negative_voxel_proxy_mean_m3']-1
passed = all(r['mean_change_passed'] and r['both_rms_passed'] and r['both_trend_passed'] for r in checks) and abs(proxy_change) <= gate['maximum_proxy_relative_window_change']
out = {'case_id': conditions['case_id'], 'token': args.token, 'end_seconds': args.end,
       'purpose_ja': '静止初期化の健康診断。ηは未補正。平均回りRMSは統計量であり、ゲージ時系列から平均を差し引いていない。',
       'negative_voxel_proxy_caution_ja': '固体やhaloと量子化を含む負SDFセル数。実水量・収支合格ではない。',
       'drive_gate_eligible': args.end >= conditions['piston_start_absolute_seconds'],
       'diagnostic_stability_passed': passed, 'wave_verified': False, 'physical_accuracy_verified': False,
       'conditions': gate, 'windows': windows, 'gauge_checks': checks,
       'proxy_relative_window_change': proxy_change,
       'resources': {'cook_median_s': statistics.median(r['cook_seconds'] for r in samples),
                     'cook_max_s': max(r['cook_seconds'] for r in samples),
                     'dop_memory_max_bytes': max(r['simulation_memory_bytes'] for r in samples),
                     'available_ram_min_bytes': min(r['memory']['available_physical_bytes'] for r in samples),
                     'particle_count_initial_final': [samples[0]['particle_count'], samples[-1]['particle_count']]},
       'source_sha256': {str(p.relative_to(ROOT)).replace('\\','/'): sha(p) for p in (source, conditions_path, Path(__file__))}}
dest = ROOT/'Evidence'/('Preroll_'+args.token)/'22_preroll_stability_recomputed.json'
dest.parent.mkdir(exist_ok=True)
dest.write_bytes((json.dumps(out, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
print(json.dumps(out, ensure_ascii=False, indent=2))
