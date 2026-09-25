"""公開原JSONだけから単一時刻の面化差を再計算する。HOM/MCP/solverを呼ばない。"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy
from refine_core06 import profile_shape06, same_parameters_except_voxel

FONT = Path('C:/Windows/Fonts/meiryo.ttc')
OUTPUTS = ['22_refine06_summary.json', '22_refine06_centers.csv', '22_refine06_profiles.csv',
           '22_refine06_centers.png', '22_refine06_spatial_difference.png']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
def csv_write(path, rows):
    with path.open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(rows)


def analyze(source, output):
    output.mkdir(parents=True, exist_ok=True)
    originals = load(source / '22_original_manifest.json'); attempt_manifest = load(source / '22_attempt_manifest.json')
    for row in originals['records']:
        path = source / row['path']; stored = path.read_bytes(); raw = gzip.decompress(stored)
        assert sha(path) == row['stored_sha256'] and len(stored) == row['stored_bytes']
        assert hashlib.sha256(raw).hexdigest() == row['original_sha256'] and len(raw) == row['original_bytes']
    cases = attempt_manifest['cases']; attempts = []; successful = {}
    for c in cases:
        r = load(source / c['result']); e = load(source / c['execution']); cleanup = e['cleanup']
        assert len(cleanup['checks']) == 18 and all(cleanup['checks'].values())
        assert not e['transport_completion_uncertain']
        row = {'label': c['label'], 'token': c['token'], 'status': c['status'], 'meaning_ja': c['meaning_ja'],
               'original_passed_for_review': e['passed_for_review'], 'original_failure_type': r.get('failure_type'),
               'original_failure_phase': r.get('failure_phase'), 'ui18_passed': True,
               'dirty_before': cleanup['dirty_before'], 'dirty_after': cleanup['dirty_after'],
               'metadata': e['metadata'], 'uncertain': False, 'result_path': c['result'], 'execution_path': c['execution']}
        attempts.append(row)
        if c['label'] in ('Retry06', 'Replay474', 'Replay496'):
            assert r['mesh_parity']['passed'] and r['native_exact'] and r['saved_mesh_reread_parity']['passed']
            successful[c['label']] = {'sample': r['sample'], 'physical_seconds': r['sample']/60, 'meshing_rpc_seconds': r['seconds'], 'new_mesh': r['mesh_output'],
                                      'geometry_points_faces': r['replay_mesh_counts'], 'geometry_and_native_exact': True,
                                      'BGEO_bytes_equal_required': False}
    latest = cases[-1]; r = load(source / latest['result']); e = load(source / latest['execution'])
    old = load(source / 'Original/pfsrefine06_c208ac35e3/profiles_old_360.json.gz')
    new = load(source / 'Original/pfsrefine06_c208ac35e3/profiles_new_360.json.gz')
    baseline = load(source / next(c['result'] for c in cases if c['label'] == 'Retry06'))
    assert r['passed'] and e['passed_for_review'] and r['input_gate_passed'] and r['baseline_input_canonical_equal']
    assert same_parameters_except_voxel(baseline['PFS_parameters'], r['PFS_parameters']) == r['parameter_pair']
    assert r['parameter_pair']['passed'] and r['definition_equal'] and r['convert_equal']
    assert profile_shape06(old)['passed'] and profile_shape06(new, old)['passed']
    assert r['saved_mesh_reread_parity']['passed'] and not r['new_solver'] and not r['detector_executed']
    assert old['metadata_before'] == old['metadata_after'] and new['metadata_before'] == new['metadata_after']
    flat = []
    for a, b in zip(old['profiles'], new['profiles']):
        assert a['field_profile'] == b['field_profile']
        assert a['strict_incidence_consistency']['passed'] and b['strict_incidence_consistency']['passed']
        assert a['field_profile']['single_wet_to_dry_local']
        assert all(math.isfinite(v) for v in a['field_profile']['phi'])
        for row in (a, b):
            assert len(row['strict_distinct_height_hits']['hits']) == len(row['sensitivity_distinct_height_hits']['hits']) == len(row['unmerged_primitive_incidences']) == 2
        x, y, field = a['native_default_first_y_m'], b['native_default_first_y_m'], a['field_profile']['height_m']
        flat.append({'gauge': a['gauge'], 'dx_m': a['dx_m'], 'x_m': a['x_m'], 'z_m': a['z_m'],
                     'old_half_eta_m': x, 'new_quarter_eta_m': y, 'solver_local_sign_field_eta_m': field,
                     'new_minus_old_m': y - x, 'old_minus_solver_local_m': x - field, 'new_minus_solver_local_m': y - field})
    assert len(flat) == 195
    centers = []
    for row in r['center_raw_differences']:
        centers.append(dict(row))
        profile = next(x for x in flat if x['gauge'] == row['gauge'] and x['dx_m'] == 0 and x['z_m'] == 0)
        assert profile['old_half_eta_m'] == row['old_mesh_eta_m'] and profile['new_quarter_eta_m'] == row['new_mesh_eta_m']
    resources = r['resources'] + old['resource_readings'] + new['resource_readings']
    delta = [row['new_minus_old_m'] for row in flat]
    per_gauge = []
    for g in (1, 2, 3):
        d = [x['new_minus_old_m'] for x in flat if x['gauge'] == g]
        per_gauge.append({'gauge': g, 'count': len(d), 'min_m': min(d), 'max_m': max(d), 'mean_m': statistics.mean(d), 'rms_m': math.sqrt(statistics.mean(v*v for v in d))})
    summary = {
        'meaning_ja': '既存k360粒子の面化だけを変更した単一静水時刻の測定。波形検出/物理精度/22完成ではない。',
        'attempts': attempts, 'old_half_successes': successful,
        'refine360': {'sample': 360, 'physical_seconds': 6., 'new_solver': False, 'detector_executed': False, 'physical_pass': False,
            'metadata': e['metadata'], 'full_PFS_parameter_count': len(r['PFS_parameters']), 'different_parameters': r['parameter_pair']['different_parameters'],
            'HDA_and_convert_exact': r['definition_equal'] and r['convert_equal'],
            'input_particle_count': r['direct_input_signature']['particle_count'], 'new_mesh': r['mesh_output'],
            'old_counts': r['original_mesh_counts'], 'new_counts': r['replay_mesh_counts'],
            'mesh_fingerprint': r['mesh_fingerprint'], 'original_mesh_fingerprint': r['original_mesh_fingerprint'],
            'saved_mesh_reread_parity': r['saved_mesh_reread_parity'], 'center_raw_differences': centers,
            'profile_count_per_mesh': 195, 'profile_count_total': 390, 'each_profile_intersections': 2,
            'profile_old_center_parity': old['center_parity_passed'], 'profile_new_center_parity_diagnostic_only': new['center_parity_passed'],
            'solver_center_max_error_m': max(abs(x['center_solver_error_m']) for d in (old, new) for x in d['profiles'] if 'center_solver_error_m' in x),
            'local_delta_m': {'min': min(delta), 'max': max(delta), 'mean': statistics.mean(delta), 'rms': math.sqrt(statistics.mean(v*v for v in delta))},
            'per_gauge_delta_m': per_gauge, 'meshing_rpc_seconds': r['seconds'], 'auto_windows': r['auto_windows'],
            'old_profile_seconds': old['read_seconds'], 'new_profile_seconds': new['read_seconds'],
            'minimum_available_RAM_bytes': min(v['available_bytes'] for v in resources),
            'maximum_observed_private_bytes': max(v['private_bytes'] for v in resources),
            'maximum_observed_private_increase_bytes': max(v['private_bytes'] for v in resources) - r['resources'][0]['private_bytes'],
            'process_lifetime_peak_working_set_bytes': max(v['peak_working_since_process_bytes'] for v in resources),
            'minimum_observed_free_G_bytes': min(v['free_G_bytes'] for v in resources),
            'ui18_and_owned_cleanup': e['cleanup']['all_ui_and_owned_node_checks_passed'], 'dirty_before': e['cleanup']['dirty_before'],
            'dirty_after': e['cleanup']['dirty_after'], 'readonly_profile_metadata_unchanged': old['metadata_unchanged'] and new['metadata_unchanged'],
            'transport_completion_uncertain': e['transport_completion_uncertain'],
            'inherited_window_label_ja': 'OLD_HALF_PFSは変更していないwindow helperの履歴ラベル。実設定はvoxelsize=.25。',
            'memory_limit_ja': 'Manual節目/読戻し前後の観測privateで、連続privateピークやVRAMではない。working set peakはプロセス生涯値。'},
        'original_gzip_file_count': len(originals['records']), 'original_json_bytes': sum(v['original_bytes'] for v in originals['records']),
        'stored_gzip_bytes': sum(v['stored_bytes'] for v in originals['records']),
        'limitations_ja': ['t6の一時刻だけ。連続波・q・唯一鎖を評価していない。', '局所の上下二交点は二層自由面を意味しない。',
            'fieldのisSDF metadata=falseを保持。solverを細分化していない。', 'HDA/166評価parmの整合は確認したが、未観測の外部DOP状態の不変は証明しない。']}
    write(output / OUTPUTS[0], summary); csv_write(output / OUTPUTS[1], centers); csv_write(output / OUTPUTS[2], flat)
    assert FONT.exists()
    font_manager.fontManager.addfont(str(FONT)); plt.rcParams.update({'font.family': font_manager.FontProperties(fname=str(FONT)).get_name(), 'axes.unicode_minus': False, 'font.size': 11})
    colors = ['#677b8b', '#087e8b', '#ad4b1e']; groups = [1, 2, 3]
    fig, axes = plt.subplots(2, 1, figsize=(11.6, 7.7), gridspec_kw={'height_ratios': [1.1, 1]}, layout='constrained')
    fig.suptitle('22修正06｜保存粒子の面化感度・k360 / t=6.000秒', fontsize=17, weight='bold')
    for key, name, color, marker in [('old_mesh_eta_m', '旧 .5 PFS', colors[0], 'o'), ('new_mesh_eta_m', '新 .25 PFS', colors[1], 's'), ('solver_observed_eta_m', '元solver符号場（原04測点）', colors[2], '^')]:
        axes[0].plot(groups, [c[key]*1000 for c in centers], marker=marker, lw=1.4, label=name, color=color)
    axes[0].set(title='中央3測点の原水位：補正・平行移動なし', ylabel='高さ Y [mm]', xticks=groups, xticklabels=['G1', 'G2', 'G3'])
    axes[0].grid(alpha=.2); axes[0].legend(loc='upper center', ncol=3, fontsize=10)
    for g, stats, c in zip(groups, per_gauge, centers):
        axes[1].plot([g,g], [stats['min_m']*1000, stats['max_m']*1000], color='#a9cfd2', lw=12, solid_capstyle='round')
        axes[1].plot(g, c['new_minus_old_m']*1000, 'o', color=colors[1], ms=8)
        axes[1].annotate(f"{c['new_minus_old_m']*1000:+.6f} mm", (g, c['new_minus_old_m']*1000), xytext=(9, 5), textcoords='offset points', fontsize=10)
    axes[1].axhline(0, color='#888888', lw=.8); axes[1].grid(axis='y', alpha=.2)
    axes[1].set(title='新−旧：点は中央、太線は各65位置の最小〜最大（誤差棒ではない）', ylabel='面化による差 [mm]', xticks=groups, xticklabels=['G1', 'G2', 'G3'], xlim=(.65,3.7))
    fig.supxlabel('粒子/solver再計算なし。195点の局所観測であり、物理精度・波形改善・22完成の証明ではない。', fontsize=10)
    fig.savefig(output / OUTPUTS[3], dpi=160, metadata={'Software': 'GreatWave measured analysis'}); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.9), layout='constrained'); limit=max(abs(v) for v in delta)*1000
    fig.suptitle('同じ195位置における新.25 − 旧.5 PFS高さ｜k360 / t=6.000秒', fontsize=16, weight='bold')
    xs=sorted({v['dx_m'] for v in flat}); zs=sorted({v['z_m'] for v in flat})
    for ax,g in zip(axes,groups):
        arr=[[next(v['new_minus_old_m']*1000 for v in flat if v['gauge']==g and v['dx_m']==x and v['z_m']==z) for x in xs] for z in zs]
        im=ax.imshow(arr, origin='lower', interpolation='nearest', extent=[-130,130,-150,150], cmap='RdBu_r', vmin=-limit,vmax=limit, aspect='auto')
        ax.scatter(0,0,s=55,facecolors='none',edgecolors='black',linewidths=1.2)
        ax.set(title=f'G{g}近傍・65点', xlabel='中央測点からの X [mm]', ylabel='Z [mm]', xticks=[-120,-60,0,60,120], yticks=[-120,-60,0,60,120])
    fig.colorbar(im, ax=axes, label='新−旧の高さ差 [mm]', shrink=.8)
    fig.supxlabel('色は登録点の実測差。格子セル表示に補間なし。丸は中央。時系列・q・伝播鎖は再判定していない。', fontsize=10)
    fig.savefig(output / OUTPUTS[4], dpi=160, metadata={'Software': 'GreatWave measured analysis'}); plt.close(fig)
    write(output / '22_analysis_manifest.json', {'input_manifest_sha256': sha(source/'22_original_manifest.json'),
        'attempt_manifest_sha256': sha(source/'22_attempt_manifest.json'), 'source_sha256': sha(Path(__file__)),
        'pure_core_sha256': sha(Path(__file__).with_name('refine_core06.py')), 'font_sha256': sha(FONT),
        'versions': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__, 'numpy': numpy.__version__},
        'houdini_called': False, 'outputs': [{'path': n, 'bytes': (output/n).stat().st_size, 'sha256': sha(output/n)} for n in OUTPUTS]})
    print(json.dumps({'original_files_verified': len(originals['records']), 'profiles': len(flat)*2, 'physical_pass': False, 'output_count': len(OUTPUTS)}, ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--input', type=Path, required=True); parser.add_argument('--output', type=Path)
    args=parser.parse_args(); analyze(args.input.resolve(), (args.output or args.input).resolve())
