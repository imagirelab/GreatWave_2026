"""20の独立プロセス実測を集計する。ゼロ/未取得のGPUを高速と解釈しない。"""
import json,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'Docs/Evidence/M1/Decision20'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
order=load(E/'20_run_order.json');runs=[load(E/f"20_run_{r['ordinal']:02d}_{r['format']}.json") for r in order['order']]
def spread(values):return {'values':values,'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
summary={'classification_ja':'同じ24Hz小試料のWindows PC暫定選択用。HMD/主役波/60Hz VAT/最終描画は未検証。','runs':len(runs),'all_runtime_passed':all(r['passed'] for r in runs),'gpu_time_note_ja':'有効なら同offscreen workloadを含むUnityアプリframe GPU時間。shader専用時間・HMD時間ではない。未取得は0msとしない。','memory_note_ja':'Windows GetProcessMemoryInfoのworking set/private bytes。GPU専用量ではない。peakWorkingSetSinceProcessはプロセス開始以降、private peakは49回ごとの標本最大。','formats':[]}
for fmt in ('abc','vat'):
 rows=[r for r in runs if r['format']==fmt];out={'format':fmt,'process_runs':len(rows),'scene_load_ms':spread([r['sceneLoadMilliseconds'] for r in rows]),'initialize_ms':spread([r['initializeMilliseconds'] for r in rows]),'first_render_cpu_ms':spread([r['firstRenderCpuMilliseconds'] for r in rows]),'first_readback_ms':spread([r['firstReadbackMilliseconds'] for r in rows]),'private_after_first_visible_bytes':spread([r['afterFirstVisible']['privateBytes'] for r in rows]),'private_delta_first_visible_bytes':spread([r['afterFirstVisible']['privateBytes']-r['beforeLoad']['privateBytes'] for r in rows]),'working_set_after_first_visible_bytes':spread([r['afterFirstVisible']['workingSet'] for r in rows]),'asset_isolation':all(r['assetIsolationPassed'] for r in rows),'gpu_feature_enabled':[r['frameTimingFeatureEnabled'] for r in rows],'paths':[]}
 for mode,views in [(m,v) for m in ("wide","near_window") for v in (1,2)]:
  timings=[next(t for t in r['timings'] if t['views']==views and t['cameraMode']==mode) for r in rows];d={'camera_mode':mode,'views':views,'pixels_per_view':[1280,720],'measured_frames_per_run':980,'warmup_per_run':98,'gpu_valid_counts':[t['frameTimingGpu']['count'] for t in timings],'gpu_zero_counts':[t['frameTimingGpuZero'] for t in timings],'gpu_missing_counts':[t['frameTimingGpuMissingOrDuplicate'] for t in timings]}
  for metric in ('cpuUpdate','cpuSubmission','frameInterval','frameTimingCpu','frameTimingGpu','frameTimingMainThread','frameTimingRenderThread'):
   d[metric]={'available_all_runs':all(t[metric]['available'] for t in timings),'runs':[t[metric] for t in timings]}
   if d[metric]['available_all_runs']:d[metric]['median_of_run_p50']=statistics.median(t[metric]['p50'] for t in timings);d[metric]['maximum_run_p99']=max(t[metric]['p99'] for t in timings)
  d['private_sampled_peak_bytes']=spread([max(m['privateBytes'] for m in t['memorySnapshots']) for t in timings]);d['working_set_process_peak_bytes']=spread([max(m['peakWorkingSetSinceProcess'] for m in t['memorySnapshots']) for t in timings]);out['paths'].append(d)
 summary['formats'].append(out)
summary['input_assets']=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [ROOT/'Unity/Assets/GreatWave/Art/Playback18/fluid17.abc',*[ROOT/'Unity/Assets/GreatWave/Art/Playback18/VAT'/n for n in ('fluid17_mesh.fbx','fluid17_pos.exr','fluid17_rot.exr','fluid17_lookup.exr','metadata.json')]]]
build=load(E/'20_build.json');context=load(E/'20_build_context.json')
summary['shared_build_capacity']={'unity_build_report_bytes':int(build['bytes']),'payload_file_count':len(context['build_payload_files']),'actual_payload_bytes':sum(f['bytes'] for f in context['build_payload_files']),'note_ja':'実配布一式は実ファイル合計で数える。Unity BuildReportとの差は61,097,540bytesでABC本体サイズと同じだが、報告側の除外原因は断定しない。両形式を含む共通buildであり、方式別パッケージ差ではない。'}
(E/'20_measurement_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':summary['all_runtime_passed'],'formats':[(x['format'],x['scene_load_ms']['median'],[p['gpu_valid_counts'] for p in x['paths']]) for x in summary['formats']]}))
