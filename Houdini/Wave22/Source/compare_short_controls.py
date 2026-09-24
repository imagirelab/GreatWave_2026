"""初期P/ID一致済みの短い独立対照を、同時刻・同じ外側2ゲージで比較する。"""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
tokens=['0652da0179','82243c001f','7e7bb86ca7']
loaded={}
sources={}
for token in tokens:
 path=ROOT/'Evidence/Curated_Runs'/token/'22_pilot_samples.json'
 loaded[token]=json.loads(path.read_text(encoding='utf8'))['samples'][:9]
 sources[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
baseline=loaded[tokens[0]]
comparisons=[]
for token in tokens[1:]:
 identity=json.loads((ROOT/'Evidence/Curated_Runs'/token/'22_initial_particle_identity.json').read_text(encoding='utf8'))
 assert identity['P_ID_exact_match']
 rows=loaded[token]
 sample_rows=[]
 for a,b in zip(baseline,rows):
  assert a['sample']==b['sample'] and a['requested_seconds']==b['requested_seconds']
  gauge_rows=[]
  for g in b['gauges']:
   match=next(q for q in a['gauges'] if abs(q['x']-g['x'])<1e-8)
   gauge_rows.append({'x_m':g['x'],'solver_eta_m':g['eta_m'],'baseline_solver_eta_m':match['eta_m'],
                      'solver_difference_m':g['eta_m']-match['eta_m'],'mesh_eta_m':g['mesh_eta_m'],
                      'baseline_mesh_eta_m':match['mesh_eta_m'],'mesh_difference_m':g['mesh_eta_m']-match['mesh_eta_m'] if match['mesh_eta_m'] is not None else None})
  sample_rows.append({'sample':b['sample'],'seconds':b['requested_seconds'],'gauges':gauge_rows,
                      'particle_count':b['particle_count'],'baseline_particle_count':a['particle_count'],
                      'id_births_since_previous':b['particle_id_births_since_previous'],
                      'id_deaths_since_previous':b['particle_id_deaths_since_previous'],
                      'velocity_rms_m_s':b['particle_velocity_rms_m_s']})
 comparisons.append({'token':token,'initial_identity':identity,'samples':sample_rows})
out={'baseline_token':tokens[0],'baseline_only_first_9_samples':True,'comparisons':comparisons,
     'scope_ja':'reseeding OFFと重力0を独立に変更。初期P/ID一致。重力0は物理作品ではなく初期再構成の診断。元t3安定判定は不合格のまま。',
     'source_sha256':sources,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
dest=ROOT/'Evidence/Short_Controls';dest.mkdir(exist_ok=True)
(dest/'22_short_control_comparison.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(str(dest))
