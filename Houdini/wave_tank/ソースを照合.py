# -*- coding: utf-8 -*-
"""保存済み小規模シーンと条件 JSON を、シミュレーションせず照合する。"""
import ast,hashlib,json
from pathlib import Path
import hou
base=Path(__file__).resolve().parent
checks=[]
for label in ['01','02']:
 config=base/f'条件_{label}.json';hip=base/f'低解像度波槽_{label}.hiplc'
 cfg=json.loads(config.read_text(encoding='utf-8'));before=hashlib.sha256(hip.read_bytes()).hexdigest()
 hou.setUpdateMode(hou.updateMode.Manual)
 hou.hipFile.load(str(hip),suppress_save_prompt=True,ignore_load_warnings=True)
 code=hou.node('/obj/initial_water/initial_particles').parm('python').unexpandedString()
 tree=ast.parse(code)
 embedded=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='c' for t in n.targets))
 assert embedded==cfg,'初期条件と JSON が一致しない。'
 fluid=hou.node('/obj/wave_dynamics/water');solver=hou.node('/obj/wave_dynamics/fluid_solver')
 expected={'particlesep':cfg['particle_separation_m'],'gridscale':2.,'closedends':1,'closeypos':0,'overridecollisionsep':0,'density':1000.}
 for key,value in expected.items():assert abs(fluid.parm(key).eval()-value)<1e-9,key
 for key,value in {'limit_sizex':cfg['length_m'],'limit_sizez':cfg['width_m'],'limit_sizey':5.,'limit_ty':2.5,'reseed':0,'doid':1,'substeps':cfg['max_substeps']}.items():assert abs(solver.parm(key).eval()-value)<1e-9,key
 assert abs(hou.node('/obj/wave_dynamics/gravity').parm('forcey').eval()+cfg['gravity_m_s2'])<1e-9
 assert hou.fps()==cfg['fps']
 if label=='02':
  box=hou.node('/obj/tank_boundaries/slope_solid')
  assert box.parm('type').evalAsString()=='polymesh'
  assert tuple(box.parmTuple('divrate').eval())==(4,2,2)
 assert hashlib.sha256(hip.read_bytes()).hexdigest()==before
 checks.append({'条件':config.name,'制作元':hip.name,'初期条件一致':True,'主要DOP設定一致':True,'制作元変更なし':True,'制作元SHA256':before,'シミュレーション実行':False})
result={'Houdiniバージョン':hou.applicationVersionString(),'照合':checks,'注意':'読み取りのみの設定照合。物理的精度と砕波の形態を保証する検査ではない。'}
(base/'ソース照合.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
