# -*- coding: utf-8 -*-
"""参照の水体を一度だけ初期化し、FLIP で自由発展させる。波の形成過程の証明ではない。"""
import argparse,json,math,time,os,ctypes
from pathlib import Path
import hou
import numpy as np
from 初期水体を構成 import build_initial, sdf, check_samples

parser=argparse.ArgumentParser(description='参照水体を初期値にして、指定フレームまで FLIP 計算する。')
parser.add_argument('--frames',type=int,default=6,help='計算する最終フレーム。最大 144。')
parser.add_argument('--config',type=Path,default=Path(__file__).resolve().parent/'条件.json',help='物理条件の JSON。')
parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent.parent/'results'/'reference_release'/'試行01')
parser.add_argument('--input',type=Path,default=Path(__file__).resolve().parent/'inputs'/'参照水体.obj')
parser.add_argument('--checks',type=Path,default=Path(__file__).resolve().parent/'inputs'/'確認点.json')
args=parser.parse_args()
assert 1 <= args.frames <= 144
src=Path(__file__).resolve().parent
cfg=json.loads(args.config.read_text(encoding='utf-8'))
out=args.output_dir.resolve()
if (out/'計測.json').exists():raise RuntimeError('既存の計算結果を上書きしない。別の出力先を指定する。')
out.mkdir(parents=True,exist_ok=True)
for sub in ['particles','surface','fields']:(out/sub).mkdir(exist_ok=True)
sep=cfg['particle_separation_m']
hou.setUpdateMode(hou.updateMode.Manual)
hou.setFps(cfg['fps']);hou.playbar.setFrameRange(1,cfg['frames']);hou.playbar.setPlaybackRange(1,cfg['frames'])
hip_path=src/'参照水体の自由発展.hiplc'
hou.hipFile.setName(str(hip_path))

def node(parent,kind,name,note):
 n=parent.createNode(kind,name);n.setComment(note);n.setGenericFlag(hou.nodeFlag.DisplayComment,True);return n

def rss_mb():
 class PM(ctypes.Structure):
  _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
 pm=PM();pm.cb=ctypes.sizeof(pm)
 ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
 ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(PM),ctypes.c_ulong]
 ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(pm),pm.cb)
 if not ok:raise RuntimeError('メモリ使用量を取得できない。')
 return pm.WorkingSetSize/1024**2

obj=hou.node('/obj')
initial,pts,checks,initial_report=build_initial(obj,cfg,args.input,args.checks,out,src)

dop=node(obj,'dopnet','wave_dynamics','実際の FLIP 計算。全水深粒子、重力、圧力投影、平らな閉じた底境界。')
dop.parm('cachemaxsize').set(1500)
fluid=node(dop,'flipobject','water','水。条件 JSON の粒子間隔と密度 1000 kg/m³、初期粒子の速度を使用。')
fluid.setParms({'surfacetype':1,'soppath':pts.path(),'particlesep':sep,'gridscale':2.,'closedends':1,'closeypos':0,'overridecollisionsep':0,'collisionsep':0.12,'initvel':0,'density':1000.})
solver=node(dop,'flipsolver::2.0','fluid_solver','FLIP の粒子移流と圧力投影。粒子再生成を無効にして粒子数を追跡する。')
solver.setInput(0,fluid)
solver.setParms({'substeps':cfg['max_substeps'],'minimumsubsteps':1,'cflcond':1.,'reseed':0,'doid':1,'dynamicresize':1,'limit_sizex':cfg['length_m'],'limit_sizey':cfg['domain_height_m'],'limit_sizez':cfg['width_m'],'limit_tx':0.,'limit_ty':cfg['domain_height_m']/2,'limit_tz':0.,'useboundarylayer':0,'usewaterline':0,'killoutside':1})
gravity=node(dop,'gravity','gravity','重力加速度 -9.80665 m/s²。')
gravity.setInput(0,solver);gravity.parm('forcey').set(-cfg['gravity_m_s2'])
output=node(dop,'output','output','粒子と体積場の計算結果。');output.setInput(0,gravity);output.setDisplayFlag(True)

resultgeo=node(obj,'geo','simulation_result','計算粒子と表面。表面化は物理計算と独立した再構成処理。')
for child in resultgeo.children():child.destroy()
imp=node(resultgeo,'dopimport','fluid_particles','FLIP の Geometry データから実粒子を取得する。')
imp.setParms({'doppath':dop.path(),'objpattern':'water','geodatapath':'Geometry','importstyle':'fetch'})
surf=node(resultgeo,'particlefluidsurface::2.0','water_surface','条件 JSON の粒子間隔、ボクセル倍率 0.75 の表面再構成。')
surf.setInput(0,imp);surf.setParms({'particlesep':sep,'voxelsize':0.75,'dosmooth':0,'dofinalsmooth':0})
surf.setDisplayFlag(True);surf.setRenderFlag(True)
for n in (initial,dop,resultgeo,obj):n.layoutChildren()
hou.setFrame(1);hou.hipFile.save(str(hip_path))
hou.setUpdateMode(hou.updateMode.AutoUpdate)
pts.cook(force=True)
if dop.parm('resimulate') is not None:dop.parm('resimulate').pressButton()
metrics=[];previous_ids=None;boundary_first=None;lip_ids=None
initial_surface_sdf=sdf(resultgeo,surf,'initial_reconstructed_sdf',cfg['initial_sdf_voxel_m'])
start=time.perf_counter()
for frame in range(1,args.frames+1):
 t=time.perf_counter();hou.setFrame(frame);imp.cook(force=True);g=imp.geometry()
 P=np.asarray(g.pointFloatAttribValues('P')).reshape(-1,3)
 V=np.asarray(g.pointFloatAttribValues('v')).reshape(-1,3)
 if len(P)<1000 or len(P)>cfg['max_particles']:raise RuntimeError('想定範囲外の粒子数: '+str(len(P)))
 if not np.isfinite(P).all() or not np.isfinite(V).all():raise RuntimeError('非有限値が発生した。')
 speed=np.linalg.norm(V,axis=1)
 ids=set(g.pointIntAttribValues('id')) if g.findPointAttrib('id') else set()
 id_values=np.asarray(g.pointIntAttribValues('id'),dtype=np.int64)
 if lip_ids is None:
  lip_point=next(p['position'] for p in checks if p['kind']=='water' and '唇' in p['name'])
  distance=np.linalg.norm(P-np.asarray(lip_point),axis=1)
  lip_ids=id_values[distance<sep*2.]
  if len(lip_ids)<8:lip_ids=id_values[np.argsort(distance)[:8]]
 lip_mask=np.isin(id_values,lip_ids)
 g.saveToFile(str(out/'particles'/f'water_{frame:04d}.bgeo.sc'))
 water=dop.simulation().findObject('water')
 fg=hou.Geometry()
 for field in ['surface','vel','collision']:
  field_geo=water.fieldGeometry(field)
  if field_geo is not None:fg.merge(field_geo)
 fg.saveToFile(str(out/'fields'/f'fields_{frame:04d}.bgeo.sc'))
 if frame==1:
  initial_report['実粒子半径の最小最大_m']=[min(g.pointFloatAttribValues('pscale')),max(g.pointFloatAttribValues('pscale'))]
  print('実粒子半径範囲',*initial_report['実粒子半径の最小最大_m'],flush=True)
 if frame==2:
  col=water.fieldGeometry('collision').prims()[0]
  pr=water.fieldGeometry('pressure').prims()[0]
  print('衝突場確認',col.voxelSize(),col.sample((-3,.5,0)),col.sample((1,.2,0)),'圧力場',pr.resolution(),min(pr.allVoxels()),max(pr.allVoxels()),flush=True)
  assert np.prod(pr.resolution())>1, '圧力場が初期値のままである。'
  field_diag={'衝突場ボクセル_m':list(col.voxelSize()),'圧力場の解像度':list(pr.resolution()),'圧力場の最小最大':[min(pr.allVoxels()),max(pr.allVoxels())]}
 simsec=time.perf_counter()-t
 tm=time.perf_counter();surf.cook(force=True);sg=surf.geometry();sg.saveToFile(str(out/'surface'/f'water_{frame:04d}.bgeo.sc'))
 if frame==1:
  initial_report['粒子表面の確認点']=check_samples(initial_surface_sdf,checks,'粒子から再構成した表面',cfg['initial_sdf_voxel_m']*.25)
  initial_report['粒子表面頂点数']=len(sg.points())
  initial_report['粒子表面プリミティブ数']=len(sg.prims())
  sg.saveToFile(str(out/'初期粒子_表面.obj'))
  (out/'初期水体確認.json').write_text(json.dumps(initial_report,ensure_ascii=False,indent=2),encoding='utf-8')
 # 全粒子数×間隔³は厳密な水量ではなく粒子数量による代理量。
 right=(P[:,0]>cfg['length_m']/2-.4)&(P[:,1]>cfg['still_depth_m']+.15)
 if right.any() and boundary_first is None:boundary_first=frame
 m={'フレーム':frame,'時刻_s':(frame-1)/cfg['fps'],'粒子数':len(P),'粒子ID数':len(ids),'新規ID数':len(ids-previous_ids) if previous_ids is not None else None,'消失ID数':len(previous_ids-ids) if previous_ids is not None else None,'粒子数量体積代理_m3':len(P)*sep**3,'最大高さ_m':float(P[:,1].max()),'最高粒子位置_m':P[P[:,1].argmax()].tolist(),'速度中央値_m_s':float(np.median(speed)),'速度P99_m_s':float(np.percentile(speed,99)),'最大速度_m_s':float(speed.max()),'境界箱最小_m':P.min(axis=0).tolist(),'境界箱最大_m':P.max(axis=0).tolist(),'計算と粒子保存_s':simsec,'表面化と保存_s':time.perf_counter()-tm,'使用メモリ_MiB':rss_mb(),'表面頂点数':len(sg.points()),'表面プリミティブ数':len(sg.prims()),'下流波面の壁接近_初回フレーム':boundary_first}
 upstream=P[:,0]<-6.
 m['上流域_Xが負6m未満']={'粒子数':int(upstream.sum()),'高さP995_m':float(np.percentile(P[upstream,1],99.5)),'鉛直速度P5中央値P95_m_s':np.percentile(V[upstream,1],[5,50,95]).tolist()}
 m['初期の唇を構成した粒子群']={'残存ID数':int(lip_mask.sum()),'重心_m':P[lip_mask].mean(axis=0).tolist(),'平均速度_m_s':V[lip_mask].mean(axis=0).tolist(),'高さの最小最大_m':[float(P[lip_mask,1].min()),float(P[lip_mask,1].max())]}
 if frame==1:m['追跡する唇の粒子ID']=lip_ids.tolist()
 if frame==2:m['体積場の更新確認']=field_diag
 metrics.append(m);previous_ids=ids
 (out/'計測.json').write_text(json.dumps({'条件':cfg,'座標':'Houdini の Y が鉛直上向き。X 正方向へ進行。Z は横方向。','注意':'粒子数量体積代理は厳密な質量・体積ではない。既に巻いた参照水体と設計した速度を初期値に使う。巻き形状の形成過程、実海波の測定流速、境界無反射を保証しない。','フレーム別':metrics},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(m,ensure_ascii=False),flush=True)
 if rss_mb()>cfg['max_memory_MiB']:raise RuntimeError('使用メモリの上限 12000 MiB に達した。')
 if time.perf_counter()-start>cfg['max_runtime_s']:raise RuntimeError('計算時間の上限に達した。')
print('計算完了',flush=True)
