"""公開t6のJSON/manifestだけからL6の費用予算を作る。HOM・BGEOを読まない。"""
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
load = lambda p: json.loads(p.read_text(encoding='utf8'))
sample_path = ROOT/'Evidence/Curated_Runs/3e5ff87a29/22_pilot_samples.json'
cache_path = ROOT/'Evidence/Checkpoint6_Result_3e5ff87a29/22_cache_manifest.json'
execution_path = ROOT/'Evidence/Curated_Runs/3e5ff87a29/execution_summary.json'
plan_path = ROOT/'Source/length6_plan.json'
rows, cache, plan = load(sample_path)['samples'], load(cache_path)['cache_files'], load(plan_path)
sizes = [sum(c['bytes'] for c in cache if c['sample'] == k) for k in range(len(rows))]
estimated = []
for count in (31, 361, 571):
    estimated.append({'sample_count':count,'old_case_mean_raw_extrapolation_bytes':statistics.mean(sizes)*count,
                      'old_case_max_raw_extrapolation_bytes':max(sizes)*count,
                      'old_case_mean_cook_extrapolation_seconds':statistics.mean(r['cook_seconds'] for r in rows)*count})
budget = plan['resource_budget']
reserve = 571*budget['predicted_raw_bytes_per_sample'] + budget['grid_probe_reserved_bytes']
result = {'new_case_executed':False,'old_BGEO_read':False,'reference_token':'3e5ff87a29',
          'length_ratio':plan['tank_inner_length_m']/plan['reference_length_m'],
          'reference_total_cache_bytes':sum(sizes),'reference_cache_files':len(cache),
          'reference_cook_total_seconds':sum(r['cook_seconds'] for r in rows),
          'reference_rpc_total_seconds':load(execution_path)['rpc_wall_seconds_sum'],
          'reference_max_private_commit_bytes':max(r['memory']['private_commit_bytes'] for r in rows),
          'reference_max_dop_bytes':max(r['simulation_memory_bytes'] for r in rows),
          'reference_mean_cache_bytes_per_sample':statistics.mean(sizes),'reference_max_cache_bytes_per_sample':max(sizes),
          'extrapolations':estimated,'reserved_raw_bytes':reserve,
          'grid_extra_reserved_bytes':budget['grid_probe_reserved_bytes'],
          'required_initial_free_disk_bytes':2*reserve+budget['minimum_disk_free_bytes'],
          'budget':budget,
          'limits_ja':'旧caseの線形外挿。新幾何・初substep観測・通信/表示・駆動後費用は保証しない。長さ比を精密な費用比例と扱わない。',
          'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'input_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (sample_path,cache_path,execution_path,plan_path)}}
out = ROOT/'Evidence/Length6_Planned'
out.mkdir(exist_ok=True)
(out/'22_length6_budget.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'required_initial_free_disk_bytes':result['required_initial_free_disk_bytes'],'houdini_called':False}))
