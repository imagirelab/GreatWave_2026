"""終了済みt6ケースを読戻し、FAILのまま公開候補へ複製する。Houdiniは呼ばない。"""
import csv
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[1]
TOKEN = '3e5ff87a29'
RUN = ROOT / 'Runs' / TOKEN
DEST = ROOT / 'Evidence' / ('Checkpoint6_Result_' + TOKEN)
DEST.mkdir(exist_ok=True)
CURATED = ROOT / 'Evidence/Curated_Runs' / TOKEN
SOURCE = DEST / 'Executed_Source'
CURATED.mkdir(exist_ok=True)
SOURCE.mkdir(exist_ok=True)
CURATED_ONLY = '--curated-only' in sys.argv
FONT = Path('C:/Windows/Fonts/meiryo.ttc')
fp = FontProperties(fname=str(FONT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))


report_path = RUN / 'Evidence/22_checkpoint_execution.json'
INPUT = CURATED if CURATED_ONLY else RUN / 'Evidence'
report = load(CURATED / 'execution_summary.json') if CURATED_ONLY else load(report_path)
raw_report_sha = report['raw_execution_report_sha256'] if CURATED_ONLY else sha(report_path)
gate = load(INPUT / '22_checkpoint_gate.json')
samples_path = INPUT / '22_pilot_samples.json'
rows = load(samples_path)['samples']
conditions = load(INPUT / '22_pilot_conditions.json')
trace = load(INPUT / '22_checkpoint_trace.json')['samples']
assert report['outcome'] == {'status': 'STATIC_GATE_FAILED', 'last_sample': 360, 'drive_authorized': False}
assert report['execution_succeeded'] and report['cleanup']['all_ui_and_owned_node_checks_passed']
assert 'drive_authorization' not in report and not gate['diagnostic_stability_passed']
assert len(rows) == len(trace) == 361 and [r['sample'] for r in rows] == list(range(361))
assert all(not r['drive_authorized'] for r in trace)
assert len({r['dop_session_id'] for r in trace}) == 1
assert all(r['piston_displacement_m'] == r['piston_velocity_m_s'] == 0 for r in rows)
assert gate['sample_sha256'] == sha(samples_path)
assert gate['conditions_sha256'] == sha(INPUT / '22_pilot_conditions.json')

for name in ('22_pilot_conditions.json', '22_pilot_samples.json', '22_checkpoint_gate.json',
             '22_checkpoint_trace.json', '22_initial_particle_identity.json'):
    original = INPUT / name
    if not CURATED_ONLY:
        (CURATED / name).write_bytes(original.read_bytes())
    assert sha(CURATED / name) == sha(original)
for name, expected in report['source_hashes'].items():
    original = SOURCE / name if CURATED_ONLY else RUN / 'Source' / name
    assert sha(original) == expected
    if not CURATED_ONLY:
        (SOURCE / name).write_bytes(original.read_bytes())

cache = []
published_cache = {r['filename']: r for r in load(DEST / '22_cache_manifest.json')['cache_files']} if CURATED_ONLY else None
for row in rows:
    for kind, filename, expected in (
        ('solver_fields_and_particles', 'pilot_%03d.bgeo.sc' % row['sample'], row['cache_sha256']),
        ('display_mesh', 'mesh_%03d.bgeo.sc' % row['sample'], row['mesh_file_sha256'])):
        if expected is None:
            continue
        path = RUN / 'Cache' / filename
        if CURATED_ONLY:
            assert published_cache[filename]['sha256'] == expected
            size = published_cache[filename]['bytes']
        else:
            assert sha(path) == expected, filename
            size = path.stat().st_size
        cache.append({'sample': row['sample'], 'absolute_seconds': row['requested_seconds'],
                      'kind': kind, 'filename': filename, 'bytes': size, 'sha256': expected})
write(DEST / '22_cache_manifest.json', {'token': TOKEN, 'local_only_path_ja': 'Houdini/Wave22/Runs/' + TOKEN + '/Cache',
                                      'cache_files': cache, 'total_bytes': sum(r['bytes'] for r in cache)})
if not CURATED_ONLY:
 write(CURATED / 'execution_summary.json', {
    'token': TOKEN, 'utc': report['utc'], 'metadata': report['metadata'],
    'clock_initialization': report['clock_initialization'], 'ownership': report['ownership'],
    'outcome': report['outcome'], 'execution_succeeded': report['execution_succeeded'],
    'transport_completion_uncertain': report['transport_completion_uncertain'],
    'cleanup': report['cleanup'], 'reference_hashes': report['reference_hashes'],
    'source_hashes': report['source_hashes'], 'raw_execution_report_sha256': raw_report_sha,
    'rpc_wall_seconds_sum': sum(e['rpc_wall_seconds'] for e in report['events']),
    'meaning_ja': '実行と復元は成功、静水の駆動開始判定は不合格。波の合格ではない。'})

with (DEST / '22_checkpoint6_gauges.csv').open('w', encoding='utf8', newline='') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['sample', 'absolute_seconds'] + [f'G{i+1}_{kind}_eta_m' for i in range(3) for kind in ('solver_sdf', 'display_mesh')] +
                    ['piston_displacement_m', 'piston_analytic_velocity_m_s', 'actual_collision_vx_m_s', 'particle_count', 'negative_voxel_proxy_m3'])
    for r in rows:
        writer.writerow([r['sample'], r['requested_seconds']] + [value for g in r['gauges'] for value in (g['eta_m'], g['mesh_eta_m'])] +
                        [r['piston_displacement_m'], r['piston_velocity_m_s'], r['piston_actual_collision_velocity_m_s'][0],
                         r['particle_count'], r['negative_voxel_volume_proxy_m3']])


def fitted(values, times):
    avg, mt = statistics.mean(values), statistics.mean(times)
    slope = sum((t-mt)*(y-avg) for t, y in zip(times, values)) / sum((t-mt)**2 for t in times)
    return {'mean_m': avg, 'trend_per_0p75s_m': slope * .75,
            'rms_about_mean_m': (statistics.mean((y-avg)**2 for y in values)) ** .5}


matched = []
for a, b in ((4.5, 5.25), (5.25, 6.0)):
    selection = [r for r in rows if a < r['requested_seconds'] <= b and r['mesh_sampled']]
    times = [r['requested_seconds'] for r in selection]
    matched.append({'left_open_s': a, 'right_closed_s': b, 'sample_count': len(selection),
                    'gauges': [{'x_m': selection[0]['gauges'][i]['x'],
                                'solver_sdf_at_mesh_times': fitted([r['gauges'][i]['eta_m'] for r in selection], times),
                                'display_mesh': fitted([r['gauges'][i]['mesh_eta_m'] for r in selection], times)} for i in range(3)]})
summary = {
    'token': TOKEN, 'wave_verified': False, 'drive_authorized': False, 'video_created': False,
    'static_gate_passed': False, 'sample_count': len(rows), 'mesh_sample_count': sum(r['mesh_sampled'] for r in rows),
    'exact_source_samples_sha256': sha(samples_path), 'gate_sha256': sha(INPUT / '22_checkpoint_gate.json'),
    'gate_windows': gate['windows'], 'gauge_checks': gate['gauge_checks'],
    'proxy_relative_window_change': gate['proxy_relative_window_change'],
    'matched_30hz_sdf_and_mesh_windows': matched,
    'piston_analytic_displacement_and_velocity_all_zero': True,
    'nonzero_actual_collision_velocity': [{'sample': r['sample'], 'seconds': r['requested_seconds'],
                                          'v_m_s': r['piston_actual_collision_velocity_m_s']} for r in rows
                                         if any(v != 0 for v in r['piston_actual_collision_velocity_m_s'])],
    'maximum_clock_error_s': max(abs(r['simulation_seconds']-r['requested_seconds']) for r in rows),
    'resource': {'cache_count': len(cache), 'cache_bytes': sum(r['bytes'] for r in cache),
                 'cook_median_s': statistics.median(r['cook_seconds'] for r in rows),
                 'cook_max_s': max(r['cook_seconds'] for r in rows),
                 'dop_cache_max_bytes': max(r['simulation_memory_bytes'] for r in rows),
                 'process_private_commit_max_bytes': max(r['memory']['private_commit_bytes'] for r in rows),
                 'available_ram_min_bytes': min(r['memory']['available_physical_bytes'] for r in rows),
                 'maximum_wall_outside_particle_count': max(r['outside_inner_walls_beyond_20mm'] for r in rows)},
    'cleanup': report['cleanup'], 'plot_source_sha256': sha(Path(__file__)),
    'plot_environment': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                         'font_name': FONT.name, 'font_sha256': sha(FONT)},
    'limitations_ja': ['静水の開始判定FAIL。駆動・進行波・動画はない。',
                      'SDFは元の局所湿乾交差で、全6秒の底連通読戻しは未実施。',
                      'PFSは表示面の最初の縦線交差。主水柱・実水量の証明ではない。',
                      '負SDFセル代理量・粒子数を水量/質量保存へ読み替えない。',
                      '30Hzに揃えたSDF/PFS統計は比較専用で、元60Hz判定を置き換えない。']}
write(DEST / '22_checkpoint6_summary.json', summary)

times = [r['requested_seconds'] for r in rows]
for detail in (False, True):
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    for i, ax in enumerate(axes):
        ax.plot(times, [r['gauges'][i]['eta_m']*1000 for r in rows], color='#125c85', label='実solver SDF（60Hz・未補正）')
        meshes = [r for r in rows if r['mesh_sampled']]
        ax.plot([r['requested_seconds'] for r in meshes], [r['gauges'][i]['mesh_eta_m']*1000 for r in meshes],
                color='#b65d20', linestyle='--', label='PFS表示mesh（30Hz・未補正）')
        ax.axvspan(4.5, 5.25, color='#dbe7ec', alpha=.7)
        ax.axvspan(5.25, 6, color='#f1e7d6', alpha=.7)
        ax.axhline(0, color='#555555', linewidth=.6)
        ax.set_ylabel('水位 η [mm]', fontproperties=fp)
        ax.set_title(f'G{i+1}  x={rows[0]["gauges"][i]["x"]:.6f} m', fontproperties=fp, fontsize=10, loc='left')
        ax.grid(alpha=.2)
        ax.set_xlim(4.5 if detail else 0, 6)
        if detail:
            visible = [r['gauges'][i][key]*1000 for r in rows if r['requested_seconds'] >= 4.5
                       for key in ('eta_m', 'mesh_eta_m') if r['gauges'][i][key] is not None]
            ax.set_ylim(min(visible)-1, max(visible)+1)
        ax.legend(prop=fp, fontsize=8, loc='lower left')
    axes[-1].set_xlabel('絶対DOP時刻 [s]（板の解析変位・速度は全時刻0）', fontproperties=fp)
    fig.suptitle('第22号 t6 静水待機：開始判定FAIL・造波未実行', fontproperties=fp, fontsize=15)
    fig.text(.5, .01, 'G3の傾き×.75秒：前窓 +5.624mm / 後窓 −4.552mm、上限3mm。表示meshで元判定を置き換えない。',
             ha='center', fontproperties=fp, fontsize=10)
    fig.tight_layout(rect=(0, .035, 1, .95))
    fig.savefig(DEST / ('22_static_late_windows.png' if detail else '22_static_full_series.png'), dpi=140)
    plt.close(fig)

paths = sorted(p for p in DEST.rglob('*') if p.is_file() and p.name != '22_result_provenance.json')
paths += sorted(p for p in CURATED.rglob('*') if p.is_file())
paths.append(Path(__file__))
paths += [ROOT / 'Source' / n for n in ('checkpoint_gate.py', 'run_checkpoint6.py', 'checkpoint6_plan.json',
                                      'check_checkpoint_logic.py', 'prepare_checkpoint_budget.py')]
paths += sorted((ROOT / 'Evidence/Checkpoint6_Planned').glob('*.json'))
paths += [ROOT / 'Checkpoint6_Plan_ja.md', ROOT / 'README_ja.md']
REPO = ROOT.parents[1]
paths += [REPO / n for n in ('Docs/Progress/Step_22_ja.md', 'Docs/Progress/README.md',
                             'Docs/Progress/Verification_Status_ja.md', 'README.md')]
paths = sorted(set(p for p in paths if p.is_file()))
write(DEST / '22_result_provenance.json', {'token': TOKEN, 'simulation_inputs_modified': False,
    'path_base': 'repository_root', 'previous_step22_commit': 'a103c0d38496a49425bb21a7f2f3e0b08868ded1',
    'raw_execution_report_sha256': raw_report_sha, 'records': [
        {'path': str(p.relative_to(REPO)).replace('\\', '/'), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]})
print(json.dumps({'token': TOKEN, 'static_gate_passed': False, 'copied_files': len(paths),
                  'cache_verified_files': 0 if CURATED_ONLY else len(cache),
                  'curated_only_reproduction': CURATED_ONLY, 'output': str(DEST)}, ensure_ascii=False))
