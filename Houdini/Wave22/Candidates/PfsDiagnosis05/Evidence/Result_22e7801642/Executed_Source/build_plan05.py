"""公開04の原JSONだけから、05の固定入力/範囲を作る。HOM不使用。"""
import gzip
import hashlib
import json
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
BASE=WAVE/'Candidates/WaveStart04/Evidence/Result_22e7801642'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
samples=json.loads(gzip.decompress((BASE/'Original/22_pilot_samples.json.gz').read_bytes()))['samples']
cache=json.loads((BASE/'22_cache_manifest.json').read_bytes())['cache_files'];byname={r['filename']:r for r in cache}
pairs=[]
for k in range(468,527,2):
    r=samples[k];assert r['mesh_sampled']
    pairs.append({'sample':k,'seconds':k/60,'mesh_sha256':r['mesh_file_sha256'],'solver_sha256':r['cache_sha256'],
                  'mesh_points':r['mesh_points'],'mesh_faces':r['mesh_faces'],'gauges':r['gauges'],
                  'cache_total_bytes':sum(byname[f'{kind}_{k:03d}.bgeo.sc']['bytes']for kind in ('pilot','mesh'))})
plan={'revision':'22修正05','state_ja':'実行前の固定計画。root審査前にHoudini/MCPへ接続しない。',
      'baseline_run':'22e7801642','baseline_commit':'d3be3eb205f6e3ff91c215806bb85df84976cac6',
      'baseline_files':{p.relative_to(BASE).as_posix():sha(p)for p in [BASE/'22_cache_manifest.json',BASE/'Original/22_pilot_samples.json.gz',BASE/'Original/22_startup_response.json',BASE/'Executed_Source/startup_response.py',BASE/'Executed_Source/generate_wave_l6.py']},
      'gauge_x_m':[g['x']for g in samples[0]['gauges']],'sampling_seconds':[7.8,526/60],'pairs':pairs,
      'profiles_per_pair':195,'pair_count':30,'total_profiles':5850,'original_center_pairs':90,
      'x_offsets_m':[i*.02 for i in range(-6,7)],'z_offsets_m':[i*.06 for i in range(-2,3)],
      'intersection':{'native_first':'04と同じy=.4,dir=(0,-1,0),既定引数。primitive>=0が有効',
                      'strict_tolerance_m':1e-6,'advance_epsilon_m':2e-6,'sensitivity_tolerance_m':1e-5,'sensitivity_advance_m':2e-5,'ray_top_m':.4,'ray_bottom_m':-.7,
                      'maximum_distinct_height_hits':64,'mesh_parity_tolerance_m':1e-6,'solver_parity_tolerance_m':1e-8,
                      'strict_incidence_height_tolerance_m':1e-6,
                      'incidences_ja':'XZ面候補ごとのnative patternで未統合face/vertex/normalを保持。同一高さの別面を削除しない。主queryの各primitive/高さを面限定queryと照合し、逆方向は各incidence高さが主query内にあるかを照合する。逆方向は共有辺の別primitiveを許す。不一致も原JSONへ保存して次組を保留する。'},
      'field_profile':{'bottom_m':-.5999,'top_rule':'min(.25,field_max_y-.01)','coarse_dy_m':.03,'surface_band_start_m':-.12,'surface_band_dy_m':.0025,
                       'zero_root_tolerance_m':1e-6,'meaning_ja':'原04上界を含む有限区間。場外/非有限停止、零接触/零台地/複数交差は曖昧記録。single_wet_to_dry_localが偽ならheight_mはnullで出図の単値に使わない。細い未標本化層を排除しない。'},
      'interpretation':{'original_response_unchanged':True,'fixed_height_correction_m':None,'numerical_sensitivity_m':.0001,'response_scale_m':.001,
                        'meaning_ja':'04全時系列/原baseline/原関数を維持。5点窓幅は60Hz4/60秒と30Hz4/30秒で異なる。近傍断面に中心qや唯一鎖判定を移植しない。'},
      'frozen_explicit_PFS_settings':{'type':'particlefluidsurface::3.0','surfmethod':'particlefluid','voxel_scale':.5,'expected_voxel_m':.02,'adaptivity':0,'dodilate':0,'dosmooth':0,'doerode':0,'dofinalsmooth':0,
                                     'meaning_ja':'凍結ソースの明示設定。既存HDAの全既定値を現在再測定した記録ではない。Final Smoothを原因と断定しない。'},
      'budgets':{'per_pair_cooperative_seconds':90,'rpc_wait_seconds':180,'maximum_cumulative_read_seconds':900,'maximum_result_bytes_per_pair':16777216,
                 'minimum_available_RAM_bytes':8589934592,'first_real_pair_only':468,'remaining_pairs_require_new_review':True,
                 'continuation_requires_explicit_flag_and_reviewed_preflight_sha':True,
                 'input_total_bytes':sum(r['cache_total_bytes']for r in pairs),'largest_pair_bytes':max(r['cache_total_bytes']for r in pairs),
                 'meaning_ja':'原manifestの容量。最初1組の実費用後に残29組を判断。90秒はloadFromFile強制中断ではない。完了不明後に再要求/killしない。'},
      'outputs_ja':['原交点/φ/近傍差JSON、中央原観測配対、元BGEO/ソース/JSON SHA','公開元04規則の不採用理由内訳','実cache由来の断面または時空間静止図、原高さと差を併記'],
      'sources':['https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html','https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html'],
      'solver_executed':False,'wave_verified':False,'step22_complete':False}
(CANDIDATE/'Source/profile05_plan.json').write_bytes((json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'pairs':30,'profiles':5850,'input_bytes':plan['budgets']['input_total_bytes'],'houdini_called':False}))
