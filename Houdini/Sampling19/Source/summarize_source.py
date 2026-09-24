"""第19号の実計算・復元と不採用採録を簡潔な出典へまとめる。計算は実行しない。"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'Evidence'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def item(p):return {'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)}
runs=[]
for name,role in [('run_64e19d0155.json','設定調査のみ・採用計算ではない'),('run_65e827446c.json','実1/120秒刻みの9時刻pilot'),('run_86ed0b4b04.json','正式121時刻の実FLIP'),('run_37f7428132.json','正式キャッシュから4Alembic書出')]:
 p=E/name;d=load(p);runs.append({'role_ja':role,'source_report':item(p),'utc':d['utc'],'expected_pid':d['expected_pid'],'source_hashes':d['source_hashes'],'success':d['success'],'cleanup':d['cleanup']})
index=load(E/'19_cache_index.json');rows=index['samples'];files=[ROOT/r[k] for r in rows for k in ('surface_file','particle_file')]
summary={'clip_id':index['clip_id'],'classification_ja':'新規2球の実FLIPによる時間標本密度の技術試験。主役の巻き波/波頭形状・海洋精度の検証ではない。','units':'m','axis':'Y-up; UnityはX反転','sample_rate':60,'samples':121,'duration_seconds':2,'subset30_indices':list(range(0,121,2)),'cache_files':len(files),'cache_bytes':sum(p.stat().st_size for p in files),'cache_sha_checks_passed':all(sha(ROOT/r[k+'_file'])==r[k+'_sha256'] for r in rows for k in ('surface','particle')),'maximum_solver_clock_error_seconds':max(abs(r['relative_seconds']-r['simulation_seconds']) for r in rows),'timestep_seconds':sorted(set(r['simulation_timestep'] for r in rows)),'all_P_N_v_cache_roundtrips_passed':all(r['cache_reread_P_N_v_match'] for r in rows),'unique_position_hashes':len(set(r['mesh_P_sha256'] for r in rows)),'unique_topology_hashes':len(set(r['mesh_topology_sha256'] for r in rows)),'particle_count_first_last':[rows[0]['particle_count'],rows[-1]['particle_count']],'solver_memory_max_bytes':max(r['simulation_memory_bytes'] for r in rows),'sample_cook_seconds_sum':sum(r['cook_seconds'] for r in rows),'solver_errors':[x for r in rows for x in r['solver_errors']],'solver_warnings':[x for r in rows for x in r['solver_warnings']],'runs':runs,'hmd_tested':False,'full_hip_saved_or_loaded':False,'owned_cpio_only':True}
(E/'19_source_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
failed=ROOT.parents[1]/'Unity/Builds/Sampling19/Capture_20260925_041639/capture_report.json'
if failed.exists():
 d=load(failed);(E/'19_rejected_depth_capture.json').write_text(json.dumps({'source_report_path':str(failed),'sha256':sha(failed),'reason_ja':'Camera.Render後にカメラ依存の深度/投影定数を読む実装で眼奥行きがNaN。判定は不合格で媒体の公開を中止した。正式版は描画中OnRenderImageで3専用RTへ保存し、後でそれだけを読む。閾値緩和なし。','original_report':d},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cache_bytes':summary['cache_bytes'],'solver_seconds':summary['sample_cook_seconds_sum'],'memory_max':summary['solver_memory_max_bytes']}))
