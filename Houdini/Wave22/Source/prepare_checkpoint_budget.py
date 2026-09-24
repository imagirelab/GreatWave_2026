"""公開t3実測とローカルcache容量から費用を外挿する。実計算を開始しない。"""
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'Evidence/Checkpoint6_Planned'
DEST.mkdir(exist_ok=True)
samples_path = ROOT / 'Evidence/Curated_Runs/0652da0179/22_pilot_samples.json'
theory_path = ROOT.parent / 'WaveBaseline21/Evidence/21_derived_parameters.json'
plan_path = ROOT / 'Source/checkpoint6_plan.json'
samples = json.loads(samples_path.read_text(encoding='utf8'))['samples']
theory = json.loads(theory_path.read_text(encoding='utf8'))
plan = json.loads(plan_path.read_text(encoding='utf8'))
cache = ROOT / 'Runs/0652da0179/Cache'
sizes, files = [], []
for row in samples:
    paths = [cache / ('pilot_%03d.bgeo.sc' % row['sample'])]
    if row['mesh_sampled']:
        paths.append(cache / ('mesh_%03d.bgeo.sc' % row['sample']))
    assert paths[0].stat().st_size == row['cache_bytes']
    sizes.append(sum(p.stat().st_size for p in paths))
    files.extend({'name': p.name, 'bytes': p.stat().st_size} for p in paths)
lam = theory['wavelength_m']
length = 2 * lam
arrival = []
for multiple in (.5, .75, 1, 1.25):
    x = multiple * lam
    arrival.append({'x_wavelengths': multiple, 'x_m': x,
                    'carrier_phase_arrival_s': 6 + x / theory['phase_speed_m_s'],
                    'carrier_group_arrival_s': 6 + x / theory['group_speed_m_s'],
                    'completed_ramp_group_arrival_s': 9 + x / theory['group_speed_m_s'],
                    'long_wave_closed_end_return_s': 6 + (2 * length - x) / theory['long_wave_speed_bound_m_s']})
budget = plan['resource_budget']
estimate = []
for count in (361, 571):
    estimate.append({'sample_count': count,
                     'raw_mean_extrapolation_bytes': statistics.mean(sizes) * count,
                     'raw_maximum_observed_extrapolation_bytes': max(sizes) * count,
                     'reserved_raw_estimate_bytes': budget['predicted_raw_bytes_per_sample'] * count,
                     'cook_mean_extrapolation_seconds': statistics.mean(r['cook_seconds'] for r in samples) * count,
                     'cook_median_extrapolation_seconds': statistics.median(r['cook_seconds'] for r in samples) * count})
out = {'measured_new_case': False, 'reference_token': '0652da0179',
       'caution_ja': 't3実測の線形外挿。MCP通信・新規設定・駆動後の非線形費用を保証しない。',
       'reference_sample_count': len(samples), 'reference_cache_file_count': len(files),
       'reference_cache_total_bytes': sum(sizes), 'mean_cache_bytes_per_timestamp': statistics.mean(sizes),
       'maximum_cache_bytes_per_timestamp': max(sizes), 'maximum_single_file_bytes': max(r['bytes'] for r in files),
       'reference_cook_total_seconds': sum(r['cook_seconds'] for r in samples),
       'reference_cook_mean_seconds': statistics.mean(r['cook_seconds'] for r in samples),
       'reference_cook_median_seconds': statistics.median(r['cook_seconds'] for r in samples),
       'reference_cook_max_seconds': max(r['cook_seconds'] for r in samples),
       'reference_dop_cache_max_bytes': max(r['simulation_memory_bytes'] for r in samples),
       'estimate': estimate, 'required_initial_free_disk_bytes': 2 * estimate[-1]['reserved_raw_estimate_bytes'] + budget['minimum_disk_free_bytes'],
       'analytical_arrival_heuristics': arrival,
       'arrival_caution_ja': '解析的な到達目安。初期化反射・非局所的圧力応答は排除しない。実FLIP伝播や無反射窓の証明ではない。',
       'input_sha256': {str(p.relative_to(ROOT.parent)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (samples_path, theory_path, plan_path)},
       'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(DEST / '22_checkpoint_budget.json').write_bytes((json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
print(json.dumps({'reference_cache_bytes': sum(sizes), 'required_initial_free_disk_bytes': out['required_initial_free_disk_bytes'], 'houdini_executed': False}))
