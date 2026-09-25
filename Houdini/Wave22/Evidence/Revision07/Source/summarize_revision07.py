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
from refine_contract07 import compare_profile05_07
from decision_core06 import compare_signatures, exact

FONT = Path('C:/Windows/Fonts/meiryo.ttc')
OUTPUTS = ['22_refine07_summary.json', '22_refine07_centers.csv', '22_refine07_profiles.csv',
           '22_refine07_centers.png', '22_refine07_spatial_difference.png']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
def csv_write(path, rows):
    with path.open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(rows)


def analyze(source, output):
    output.mkdir(parents=True, exist_ok=True)
    originals=load(source/'22_original_manifest.json'); manifest=load(source/'22_run_manifest.json')
    for row in originals['records']:
        path=source/row['path']; raw=gzip.decompress(path.read_bytes())
        assert sha(path)==row['stored_sha256'] and path.stat().st_size==row['stored_bytes']
        assert hashlib.sha256(raw).hexdigest()==row['original_sha256'] and len(raw)==row['original_bytes']
    r=load(source/manifest['result']); e=load(source/manifest['execution'])
    old=load(source/manifest['old_profile']); new=load(source/manifest['new_profile'])
    baseline=load(source/manifest['baseline_replay']); published05=load(source/manifest['baseline_profile05'])
    assert r['sample']==474 and abs(r['actual_frame']-(1+.4*474))<1e-8 and r['fps']==24
    assert r['passed'] and e['passed_for_review'] and r['input_gate_passed']
    assert len(r['PFS_parameters'])==166 and same_parameters_except_voxel(baseline['PFS_parameters'],r['PFS_parameters'])==r['parameter_pair']
    assert r['parameter_pair']['passed'] and exact(baseline['PFS_definition'],r['PFS_definition']) and exact(baseline['convert_parameters'],r['convert_parameters'])
    assert compare_signatures(baseline['direct_input_signature'],r['direct_input_signature'])
    assert all(compare_signatures(r['direct_input_signature'],x['signature']) for x in r['input_comparisons'].values())
    assert exact(baseline['native_original'],r['native_original'])
    assert compare_profile05_07(published05,old)==e['profiles']['old']['published05_pair'] and e['profiles']['old']['published05_pair']['passed']
    assert profile_shape06(old)==e['profiles']['old']['acceptance'] and profile_shape06(new,old)==e['profiles']['new']['acceptance']
    assert all(x['acceptance']['passed'] for x in e['profiles'].values())
    assert r['saved_mesh_reread_parity']['passed'] and not r['new_solver'] and not r['detector_executed'] and not r['physical_pass']
    assert len(e['cleanup']['checks'])==18 and all(e['cleanup']['checks'].values()) and not e['transport_completion_uncertain']
    assert [x['phase'] for x in e['events']]==['METADATA','SNAPSHOT','OWNED_SETUP','K474_QUARTER_MESH','RESTORE_UI18','READ_ONLY_PROFILE_OLD','READ_ONLY_PROFILE_NEW']
    assert all(x['completion_class']=='COMPLETE_SUCCESS' for x in e['events'])
    for event in e['events']:
        reply=json.loads(event['raw_response_local']); assert reply['executed'] is True
        if event['phase']=='K474_QUARTER_MESH':
            assert reply['return_value']['json_sha256']==e['result']['sha256']
        for label in ('old','new'):
            if event['phase']=='READ_ONLY_PROFILE_'+label.upper():
                assert reply['return_value']['json_sha256']==e['profiles'][label]['sha256']
    assert old['metadata_before']==old['metadata_after'] and new['metadata_before']==new['metadata_after']
    flat=[]
    for a,b in zip(old['profiles'],new['profiles']):
        assert a['field_profile']==b['field_profile'] and a['field_profile']['single_wet_to_dry_local']
        assert a['strict_incidence_consistency']['passed'] and b['strict_incidence_consistency']['passed']
        for row in (a,b):
            assert len(row['strict_distinct_height_hits']['hits'])==len(row['sensitivity_distinct_height_hits']['hits'])==len(row['unmerged_primitive_incidences'])==2
        x,y,field=a['native_default_first_y_m'],b['native_default_first_y_m'],a['field_profile']['height_m']
        flat.append({'gauge':a['gauge'],'dx_m':a['dx_m'],'x_m':a['x_m'],'z_m':a['z_m'],
            'old_half_eta_m':x,'new_quarter_eta_m':y,'solver_local_sign_field_eta_m':field,
            'new_minus_old_m':y-x,'old_minus_solver_local_m':x-field,'new_minus_solver_local_m':y-field})
    assert len(flat)==195
    centers=[]
    for observed in r['center_raw_differences']:
        row=dict(observed); profile=next(v for v in flat if v['gauge']==row['gauge'] and v['dx_m']==0 and v['z_m']==0)
        assert profile['old_half_eta_m']==row['old_mesh_eta_m'] and profile['new_quarter_eta_m']==row['new_mesh_eta_m']
        row['solver_local_sign_field_eta_m']=profile['solver_local_sign_field_eta_m']; centers.append(row)
    resources=r['resources']+old['resource_readings']+new['resource_readings']
    delta=[v['new_minus_old_m'] for v in flat]; per_gauge=[]
    for g in (1,2,3):
        d=[v['new_minus_old_m'] for v in flat if v['gauge']==g]
        per_gauge.append({'gauge':g,'count':len(d),'min_m':min(d),'max_m':max(d),'mean_m':statistics.mean(d),'rms_m':math.sqrt(statistics.mean(v*v for v in d))})
    summary={'revision':'22修正07','token':manifest['token'],'sample':474,'physical_seconds':7.9,'actual_frame':r['actual_frame'],'fps':r['fps'],
        'meaning_ja':'保存粒子から作る表示面の単一時刻感度。物理精度・時間波形・唯一鎖・22完成を認定しない。',
        'new_solver':False,'detector_executed':False,'physical_pass':False,'metadata':e['metadata'],
        'full_PFS_parameter_count':len(r['PFS_parameters']),'different_parameters':r['parameter_pair']['different_parameters'],
        'HDA_and_convert_exact':True,'input_particle_count':r['direct_input_signature']['particle_count'],
        'new_mesh':r['mesh_output'],'old_counts':r['original_mesh_counts'],'new_counts':r['replay_mesh_counts'],
        'mesh_fingerprint':r['mesh_fingerprint'],'original_mesh_fingerprint':r['original_mesh_fingerprint'],
        'saved_mesh_reread_parity':r['saved_mesh_reread_parity'],'center_raw_differences':centers,
        'old_profile05_exact_pair':e['profiles']['old']['published05_pair'],
        'profile_count_per_mesh':195,'profile_count_total':390,'each_profile_intersections':2,
        'profile_old_center_parity':old['center_parity_passed'],'profile_new_center_parity_diagnostic_only':new['center_parity_passed'],
        'solver_center_max_error_m':max(abs(v['center_solver_error_m']) for d in (old,new) for v in d['profiles'] if 'center_solver_error_m' in v),
        'local_delta_m':{'min':min(delta),'max':max(delta),'mean':statistics.mean(delta),'rms':math.sqrt(statistics.mean(v*v for v in delta))},
        'per_gauge_delta_m':per_gauge,'meshing_rpc_seconds':r['seconds'],'auto_windows':r['auto_windows'],
        'old_profile_seconds':old['read_seconds'],'new_profile_seconds':new['read_seconds'],
        'minimum_available_RAM_bytes':min([v['available_bytes'] for v in resources]+[old['memory_guard']['min_available_bytes'],new['memory_guard']['min_available_bytes']]),
        'maximum_observed_private_bytes':max(v['private_bytes'] for v in resources),
        'maximum_observed_private_increase_bytes':max(v['private_bytes'] for v in resources)-r['resources'][0]['private_bytes'],
        'process_lifetime_peak_working_set_bytes':max(v['peak_working_since_process_bytes'] for v in resources),
        'minimum_observed_free_G_bytes':min(v['free_G_bytes'] for v in resources),
        'ui18_and_owned_cleanup':e['cleanup']['all_ui_and_owned_node_checks_passed'],'dirty_before':e['cleanup']['dirty_before'],'dirty_after':e['cleanup']['dirty_after'],
        'readonly_profile_metadata_unchanged':old['metadata_unchanged'] and new['metadata_unchanged'],'transport_completion_uncertain':False,
        'inherited_window_label_ja':'OLD_HALF_PFSは原helperの識別子。実評価voxelsizeは.25。',
        'original_record_count':len(originals['records']),'original_bytes':sum(v['original_bytes'] for v in originals['records']),
        'stored_gzip_bytes':sum(v['stored_bytes'] for v in originals['records']),
        'limitations_ja':['上下二交点は二つの自由水面ではない。','surface Volume isSDF metadata=falseの符号場を読む。',
            '原04中央25二分値と05局所断面水位を互いに置換しない。','privateは節目の観測、working-set peakはprocess生涯値。VRAMではない。',
            '無関係DOP状態は監視していない。単一面から伝播・物理収束を推論しない。']}
    write(output/OUTPUTS[0],summary);csv_write(output/OUTPUTS[1],centers);csv_write(output/OUTPUTS[2],flat)
    assert FONT.exists()
    font_manager.fontManager.addfont(str(FONT)); plt.rcParams.update({'font.family': font_manager.FontProperties(fname=str(FONT)).get_name(), 'axes.unicode_minus': False, 'font.size': 11})
    colors = ['#677b8b', '#087e8b', '#ad4b1e']; groups = [1, 2, 3]
    fig, axes = plt.subplots(2, 1, figsize=(11.6, 7.7), gridspec_kw={'height_ratios': [1.1, 1]}, layout='constrained')
    fig.suptitle('22修正07｜保存粒子の面化感度・k474 / t=7.900秒', fontsize=17, weight='bold')
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
    fig.suptitle('同じ195位置における新.25 − 旧.5 PFS高さ｜k474 / t=7.900秒', fontsize=16, weight='bold')
    xs=sorted({v['dx_m'] for v in flat}); zs=sorted({v['z_m'] for v in flat})
    for ax,g in zip(axes,groups):
        arr=[[next(v['new_minus_old_m']*1000 for v in flat if v['gauge']==g and v['dx_m']==x and v['z_m']==z) for x in xs] for z in zs]
        im=ax.imshow(arr, origin='lower', interpolation='nearest', extent=[-130,130,-150,150], cmap='RdBu_r', vmin=-limit,vmax=limit, aspect='auto')
        ax.scatter(0,0,s=55,facecolors='none',edgecolors='black',linewidths=1.2)
        ax.set(title=f'G{g}近傍・65点', xlabel='中央測点からの X [mm]', ylabel='Z [mm]', xticks=[-120,-60,0,60,120], yticks=[-120,-60,0,60,120])
    fig.colorbar(im, ax=axes, label='新−旧の高さ差 [mm]', shrink=.8)
    fig.supxlabel('色は登録点の実測差。格子セル表示に補間なし。丸は中央。時系列・q・伝播鎖は再判定していない。', fontsize=10)
    fig.savefig(output / OUTPUTS[4], dpi=160, metadata={'Software': 'GreatWave measured analysis'}); plt.close(fig)
    write(output/'22_analysis_manifest.json',{'input_manifest_sha256':sha(source/'22_original_manifest.json'),
        'run_manifest_sha256':sha(source/'22_run_manifest.json'),'source_sha256':sha(Path(__file__)),
        'pure_sources':{name:sha(Path(__file__).with_name(name)) for name in ('refine_core06.py','refine_contract07.py','decision_core06.py')},
        'font_sha256':sha(FONT),'versions':{'python':platform.python_version(),'matplotlib':matplotlib.__version__,'numpy':numpy.__version__},
        'houdini_called':False,'outputs':[{'path':name,'bytes':(output/name).stat().st_size,'sha256':sha(output/name)} for name in OUTPUTS]})
    print(json.dumps({'original_records_verified':len(originals['records']),'profiles':390,'physical_pass':False,'output_count':len(OUTPUTS)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();analyze(args.input.resolve(),(args.output or args.input).resolve())
