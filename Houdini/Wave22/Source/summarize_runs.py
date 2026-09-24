"""22の実行記録と実キャッシュの対応を集計する。合格は接続試験に限定する。"""
import hashlib, json, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for p in sorted((ROOT/'Evidence').glob('run_*.json')):
 r=json.loads(p.read_text(encoding='utf8'));path=Path(r['output_directory']) if 'output_directory' in r else ROOT
 if 'cleanup' not in r:continue
 samplespath=path/'Evidence/22_pilot_samples.json'
 row={'token':r['token'],'raw_report':str(p.relative_to(ROOT)).replace('\\','/'),'raw_report_sha256':sha(p),'restoration_passed':r.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False),'run_execution_success':r.get('success',False),'case_id':r.get('create',{}).get('case_id'),'failure':({'type':r['failure'].get('type'),'reason_ja':'Houdini操作が失敗した。不採用試行の詳細tracebackはローカルraw記録に保持。','failed_phase':next((e['phase'] for e in r.get('events',[]) if e.get('result',{}).get('error') or e.get('result',{}).get('eval_error')),None)} if r.get('failure') else None),'source_hashes':r.get('source_hashes',{})}
 # 初期試行の共通パスは後続実行で上書きされたため、別runの標本へ結び付けない。
 if 'output_directory' in r and samplespath.exists():
  a=json.loads(samplespath.read_text(encoding='utf8'))['samples'];checks=[]
  for x in a:
   cache=path/('Cache/pilot_%03d.bgeo.sc'%x['sample']);checks.append(cache.exists() and sha(cache)==x['cache_sha256'])
   if x.get('mesh_file_sha256'):
    mesh=path/('Cache/mesh_%03d.bgeo.sc'%x['sample']);checks.append(mesh.exists() and sha(mesh)==x['mesh_file_sha256'])
  row.update({'samples':len(a),'end_seconds':a[-1]['requested_seconds'],'samples_json_sha256':sha(samplespath),'cache_checks':len(checks),'cache_checks_passed':all(checks),'max_clock_error_s':max(abs(x['simulation_seconds']-x['requested_seconds']) for x in a),'particle_count_initial_final':[a[0]['particle_count'],a[-1]['particle_count']],'max_abs_eta_m':[max(abs(x['gauges'][g]['eta_m']) for x in a) for g in range(len(a[0]['gauges']))],'final_eta_m':[q['eta_m'] for q in a[-1]['gauges']],'max_wall_tolerance_outside_points':max(x['outside_inner_walls_beyond_20mm'] for x in a),'max_dop_memory_bytes':max(x['simulation_memory_bytes'] for x in a),'cook_median_s':statistics.median(x['cook_seconds'] for x in a),'cook_max_s':max(x['cook_seconds'] for x in a),'proxy_initial_final_m3':[a[0]['negative_voxel_volume_proxy_m3'],a[-1]['negative_voxel_volume_proxy_m3']]})
 rows.append(row)
out={'status_ja':'接続と初期過渡の実測。進行波・非砕波・理論一致の合格ではない。','wave_propagation_verified':False,'physical_accuracy_verified':False,'hmd_verified':False,'runs':rows,'script_sha256':sha(Path(__file__))}
(ROOT/'Evidence/22_run_ledger.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'runs':len(rows),'all_completed_run_caches_match':all(r.get('cache_checks_passed',True) for r in rows),'all_recorded_restorations_passed':all(r['restoration_passed'] for r in rows)},ensure_ascii=False))
