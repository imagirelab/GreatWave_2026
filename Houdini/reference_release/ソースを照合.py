# -*- coding: utf-8 -*-
"""条件 JSON と保存済み HIP の物理設定を照合する。計算や保存は行わない。"""
import ast,hashlib,json
from pathlib import Path
import hou
base=Path(__file__).resolve().parent;hip=base/'参照水体の自由発展.hiplc';cfg=json.loads((base/'条件.json').read_text(encoding='utf-8'));before=hashlib.sha256(hip.read_bytes()).hexdigest()
hou.setUpdateMode(hou.updateMode.Manual);hou.hipFile.load(str(hip),suppress_save_prompt=True,ignore_load_warnings=True)
code=hou.node('/obj/initial_water/initial_velocity').parm('python').unexpandedString();tree=ast.parse(code)
embedded=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='c' for t in n.targets))
assert embedded==cfg,'初期場の条件が JSON と一致しない。'
fluid=hou.node('/obj/wave_dynamics/water');solver=hou.node('/obj/wave_dynamics/fluid_solver');gravity=hou.node('/obj/wave_dynamics/gravity')
for key,value in {'particlesep':cfg['particle_separation_m'],'gridscale':2.,'closedends':1,'closeypos':0,'overridecollisionsep':0,'density':1000.}.items():assert abs(fluid.parm(key).eval()-value)<1e-9,key
for key,value in {'limit_sizex':cfg['length_m'],'limit_sizez':cfg['width_m'],'limit_sizey':cfg['domain_height_m'],'limit_ty':cfg['domain_height_m']/2,'reseed':0,'doid':1,'substeps':cfg['max_substeps']}.items():assert abs(solver.parm(key).eval()-value)<1e-9,key
assert abs(gravity.parm('forcey').eval()+cfg['gravity_m_s2'])<1e-9
assert hou.fps()==cfg['fps']
assert solver.input(0)==fluid and all(n is None for n in solver.inputs()[1:])
assert gravity.input(0)==solver
assert hou.node('/obj/tank_boundaries') is None
assert hou.node('/obj/initial_water/reference_water').parm('file').unexpandedString()=='$HIP/inputs/参照水体.obj'
assert hou.node('/obj/initial_water/clipped_reference').parm('operation').evalAsString()=='sdfintersect'
assert hou.node('/obj/initial_water/joined_surface').parm('operation').evalAsString()=='sdfunion'
assert hashlib.sha256(hip.read_bytes()).hexdigest()==before
result={'Houdiniバージョン':hou.applicationVersionString(),'条件':'条件.json','制作元':hip.name,'初期条件一致':True,'主要DOP設定一致':True,'追加の形状誘導入力':False,'制作元変更なし':True,'制作元SHA256':before,'シミュレーション実行':False,'注意':'設定照合であり、参照形状が自然に形成されたことや作品の完成を保証しない。'}
(base/'ソース照合.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
