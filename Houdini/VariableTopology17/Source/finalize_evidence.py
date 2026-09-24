"""実キャッシュ・実ビューポート出力から公開用の索引と動画を保存する。"""
import argparse,hashlib,json,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
FFMPEG=Path(r'G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def digest(p):return {'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
parser=argparse.ArgumentParser();parser.add_argument('--simulation',required=True);parser.add_argument('--capture',required=True);args=parser.parse_args()
run_path=ROOT/'Evidence'/args.simulation;capture_path=ROOT/'Evidence'/args.capture
run=read(run_path);capture=read(capture_path);validation=read(ROOT/'Evidence/17_validation.json');index=read(ROOT/'Evidence/17_cache_index.json')
assert run['success'] and capture['success'] and capture['cache_bytes_unchanged']
for name,value in run['source_hashes'].items():assert hashlib.sha256((ROOT/'Source'/name).read_bytes()).hexdigest()==value
files=[]
for row in index['samples']:
 for kind in ('mesh','particle'):
  p=ROOT/row[kind+'_file'];item=digest(p);assert item['sha256']==row[kind+'_sha256'];files.append(item)
selected=ROOT/'Evidence/SelectedCache';selected.mkdir(exist_ok=True)
for k in (0,3,18,19,24,48):
 for kind in ('surface','particles'):shutil.copy2(ROOT/('Cache/%s_%03d.bgeo.sc'%(kind,k)),selected)
pattern=capture['capture']['video_pattern'];frames=sorted((ROOT/'Evidence/Frames').glob(pattern.replace('%04d','*')));assert len(frames)==48
video=ROOT/'Evidence/17_FLIP_Surface_2s.mp4'
subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y','-framerate','24','-start_number','1','-i',str(ROOT/'Evidence/Frames'/pattern),'-frames:v','48','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-i',str(video),'-f','null','-'],check=True)
probe=json.loads(subprocess.check_output([str(FFMPEG.with_name('ffprobe.exe')),'-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate,nb_frames,duration','-of','json',str(video)],text=True))['streams'][0]
assert int(probe['nb_frames'])==48 and probe['r_frame_rate']=='24/1' and float(probe['duration'])==2
rows=validation['samples'];merge=[e for e in validation['particle_lineage_events'] if e['merge_successors'] and e['time_after']<=1]
split=[e for e in validation['particle_lineage_events'] if e['split_predecessors'] and e['time_after']<=1]
def clearance(row):
 b=row['particle_bounds'];return min(6-abs(b[bound][axis]) for bound in ('min','max') for axis in (0,2))
checks={'actual_FLIP_solver': 'flipsolver' in run['source']['node_types'],'sample_count_49':len(rows)==49,'all_49_cache_roundtrips':all(r['cache_reread_P_N_v_topology_match'] for r in index['samples']),'all_topologies_distinct':validation['distinct_mesh_topology_count']==49,'all_finite':validation['all_finite_normals_and_geometry'],'closed_manifold':validation['all_meshes_closed_manifold'],'positive_component_volumes':validation['positive_component_volumes'],'all_real_particle_ids_unique':all(r['particle_ids_unique'] for r in rows),'particle_merge_before_one_second':bool(merge),'particle_split_before_one_second':bool(split),'event_particles_away_from_horizontal_domain':bool(merge and split) and all(clearance(rows[e['sample_after']])>.16 for e in (merge[0],split[0])),'surface_merge':rows[0]['mesh_components_significant']==2 and rows[3]['mesh_components_significant']==1,'surface_split_before_outflow':rows[24]['mesh_components_significant']>=2 and rows[24]['particle_count']==rows[18]['particle_count'] and clearance(rows[24])>.16,'simulation_UI_restored':run['cleanup']['all_ui_and_owned_node_checks_passed'],'capture_UI_restored':capture['cleanup']['all_ui_and_owned_node_checks_passed'],'video_verified':True}
summary={'clip_id':'GreatWave17_FLIP_02','recorded_utc':datetime.now(timezone.utc).isoformat(),'technical_specimen_checks':checks,'technical_specimen_passed':all(checks.values()),'scope_ja':'実FLIP由来の変動トポロジー試料。初期の結合・境界へ達する前の分離だけを検証し、物理精度や質量保存は合格対象としない。','particle_merge':merge[0] if merge else None,'particle_split':split[0] if split else None,'surface_split_sample':24,'surface_split_horizontal_clearance_m':clearance(rows[24]),'particle_count_excludes_five_volume_points':True,'historical_index_particle_count_ja':'実行時17_cache_indexのparticle_countはVolume保持点5個を含む生点数。正しい実粒子数は17_validation.samples.particle_count。','initial_real_particles':rows[0]['particle_count'],'final_real_particles':rows[-1]['particle_count'],'mesh_volume_initial_m3':rows[0]['mesh_signed_volume_m3'],'mesh_volume_max_m3':max(r['mesh_signed_volume_m3'] for r in rows),'mesh_volume_end_m3':rows[-1]['mesh_signed_volume_m3'],'volume_preservation_verified':False,'ocean_physical_accuracy_verified':False,'hmd_verified':False,'step18_executed':False,'video':probe,'actual_viewport_readback':True,'particle_glyph_radius_m':.025,'particle_glyph_color_ja':'白い表示用球。初期IDの色分けは表示されていない。数値のID系譜は別記。','capture_ja':'静止画は同じ時刻・同じ範囲で表面と粒子を対比。動画は全時刻の範囲に固定し終盤の流出も表示。','simulation_report':dict(digest(run_path),path='Evidence/17_simulation_run.json'),'capture_report':dict(digest(capture_path),path='Evidence/17_capture_run.json'),'final_UI_cleanup':capture['cleanup'],'cache_count':len(files),'cache_bytes':sum(f['bytes'] for f in files),'cache_files':files,'source_files':[digest(p) for p in sorted((ROOT/'Source').glob('*')) if p.is_file()]}
write(ROOT/'Evidence/17_summary.json',summary)
shutil.copy2(run_path,ROOT/'Evidence/17_simulation_run.json');shutil.copy2(capture_path,ROOT/'Evidence/17_capture_run.json')
published=[p for p in (ROOT/'Evidence').glob('17_*') if p.is_file() and p.name!='17_provenance.json']+list(selected.glob('*'))
write(ROOT/'Evidence/17_provenance.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'git_context_at_recording':{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True).strip())},'scope_ja':'この時点のGit開始点だけで完成版を示さず、実行ソース・実キャッシュ・媒体の各ハッシュを使う。生フレームと全キャッシュはローカル、選択12キャッシュは公開。','source_files':summary['source_files'],'evidence_files':[digest(p) for p in sorted(published)],'raw_frame_hashes':[digest(p) for p in frames]})
print(json.dumps({'technical_specimen_passed':summary['technical_specimen_passed'],'checks':checks,'video':probe,'cache_bytes':summary['cache_bytes'],'selected_cache_bytes':sum(p.stat().st_size for p in selected.glob('*'))},ensure_ascii=False))
