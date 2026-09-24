# -*- coding: utf-8 -*-
"""有限波槽における初期波包の FLIP 自由発展。参照模型への追従は行わない。"""
import argparse,json,math,time,os,ctypes
from pathlib import Path
import hou
import numpy as np

parser=argparse.ArgumentParser(description='低解像度 FLIP 波槽を生成し、指定フレームまで計算する。')
parser.add_argument('--frames',type=int,default=6,help='計算する最終フレーム。最大 72。')
parser.add_argument('--config',type=Path,default=Path(__file__).resolve().parent/'条件_02.json',help='物理条件の JSON。')
parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent.parent/'results'/'wave_tank'/'本計算02')
args=parser.parse_args()
assert 1 <= args.frames <= 72
src=Path(__file__).resolve().parent
cfg=json.loads(args.config.read_text(encoding='utf-8'))
out=args.output_dir.resolve()
if (out/'計測.json').exists():raise RuntimeError('既存の計算結果を上書きしない。別の出力先を指定する。')
out.mkdir(parents=True,exist_ok=True)
for sub in ['particles','surface','fields']:(out/sub).mkdir(exist_ok=True)
sep=cfg['particle_separation_m']
hou.setUpdateMode(hou.updateMode.Manual)
hou.setFps(cfg['fps']);hou.playbar.setFrameRange(1,72);hou.playbar.setPlaybackRange(1,72)
hip_path=src/('低解像度波槽_'+args.config.stem.removeprefix('条件_')+'.hiplc')
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
initial=node(obj,'geo','initial_water','初期水体。ガウス形の水面と長波近似の初速を一度だけ設定する。')
for child in initial.children():child.destroy()
pts=node(initial,'python','initial_particles','初期粒子。造波後の位置拘束、毎フレームの形状目標、速度再注入は使わない。')
pts_code=r"""
import hou,math,random
c=CONFIG
geo=hou.pwd().geometry();sep=c['particle_separation_m'];h=c['still_depth_m'];a=c['crest_amplitude_m'];L=c['gaussian_width_m'];x0=c['crest_center_x_m']
speed=math.sqrt(c['gravity_m_s2']*(h+a));rng=random.Random(c['seed'])
pos=[];vel=[]
for ix in range(round(c['length_m']/sep)):
 x=-c['length_m']/2+(ix+.5)*sep
 bed=c['slope_height_m']*min(1,max(0,(x-c['slope_start_x_m'])/(c['slope_end_x_m']-c['slope_start_x_m'])))
 eta=a*math.exp(-((x-x0)/L)**2)
 ux=speed*eta/(h+eta)
 du=speed*h/(h+eta)**2*(-2*(x-x0)/L**2*eta)
 for iz in range(round(c['width_m']/sep)):
  z=-c['width_m']/2+(iz+.5)*sep
  for iy in range(math.ceil((h+eta)/sep)):
   y=(iy+.5)*sep
   if y<=bed+sep*.4 or y>h+eta-sep*.4:continue
   jitter=[rng.uniform(-.08,.08)*sep for _ in range(3)]
   pos.append((x+jitter[0],y+jitter[1],z+jitter[2]));vel.append((ux,-max(0,y-bed)*du,0))
geo.createPoints(pos)
geo.addAttrib(hou.attribType.Point,'v',(0.,0.,0.));geo.setPointFloatAttribValues('v',[x for v in vel for x in v])
geo.addAttrib(hou.attribType.Point,'pscale',sep*1.2)
geo.addAttrib(hou.attribType.Point,'mass',1000*sep**3)
geo.addAttrib(hou.attribType.Point,'density',1000.)
""".replace('CONFIG',repr(cfg))
pts.parm('python').set(pts_code);pts.setDisplayFlag(True);pts.setRenderFlag(True)
initial.setDisplayFlag(False)

bedgeo=node(obj,'geo','tank_boundaries','標準の直方体から作る単一の浅化斜面。側壁と底は FLIP の閉鎖境界を使用。')
for child in bedgeo.children():child.destroy()
box=node(bedgeo,'box','slope_solid','標準の閉じた直方体を X 方向に 3 区間へ分割する。')
if cfg.get('bed_shape')=='slope_plateau':
 box.parm('type').set('polymesh');box.parmTuple('divrate').set((4,2,2))
 box.parmTuple('size').set((3.,1.,cfg['width_m']+.6));box.parmTuple('t').set((1.5,0.,0.))
 shape=node(bedgeo,'attribwrangle','slope_transform','単一閉曲面の底床。上面だけを斜面と水平な浅瀬へ変形する。')
 shape.setInput(0,box)
 shape.parm('snippet').set('// X 方向の切面を斜面の前後と接続する。水体の位置拘束ではない。\nint i=int(rint(@P.x));\nfloat xs[]={'+','.join(str(x) for x in [cfg['slope_start_x_m']-.6,cfg['slope_start_x_m'],cfg['slope_end_x_m'],cfg['length_m']/2+.6])+'};\n@P.x=xs[clamp(i,0,3)];\n@P.y=@P.y>0 ? '+str(cfg['slope_height_m'])+'*clamp((@P.x-'+str(cfg['slope_start_x_m'])+')/'+str(cfg['slope_end_x_m']-cfg['slope_start_x_m'])+',0.,1.) : -.6;')
else:
 box.parmTuple('size').set((8.,.6,4.))
 shape=node(bedgeo,'xform','slope_transform','第 1 試行の連続斜面。上面は X=0 で高さ 0 m、勾配 1/4。')
 shape.setInput(0,box)
 theta=math.atan(.25)
 shape.parmTuple('r').set((0.,0.,math.degrees(theta)))
 shape.parmTuple('t').set((3.,.75-.3/math.cos(theta),0.))
shape.setDisplayFlag(True);shape.setRenderFlag(True);bedgeo.setDisplayFlag(False)

dop=node(obj,'dopnet','wave_dynamics','実際の FLIP 計算。全水深粒子、重力、圧力投影、静的衝突。')
dop.parm('cachemaxsize').set(1500)
fluid=node(dop,'flipobject','water','水。条件 JSON の粒子間隔と密度 1000 kg/m³、初期粒子の速度を使用。')
fluid.setParms({'surfacetype':1,'soppath':pts.path(),'particlesep':sep,'gridscale':2.,'closedends':1,'closeypos':0,'overridecollisionsep':0,'collisionsep':0.12,'initvel':0,'density':1000.})
solver=node(dop,'flipsolver::2.0','fluid_solver','FLIP の粒子移流と圧力投影。粒子再生成を無効にして粒子数を追跡する。')
solver.setInput(0,fluid)
solver.setParms({'substeps':cfg['max_substeps'],'minimumsubsteps':1,'cflcond':1.,'reseed':0,'doid':1,'dynamicresize':1,'limit_sizex':cfg['length_m'],'limit_sizey':5.,'limit_sizez':cfg['width_m'],'limit_tx':0.,'limit_ty':2.5,'limit_tz':0.,'useboundarylayer':0,'usewaterline':0,'killoutside':1})
static=node(dop,'staticobject','tank','静止した浅化斜面。移動壁や外力による造波は行わない。')
static.setParms({'soppath':shape.path(),'uniformvoxels':'size','divsize':0.12,'friction':0.,'invert':0})
merge=node(dop,'merge','collision_relationship','衝突固体が流体に作用する。')
merge.setInput(0,static);merge.setInput(1,solver);merge.parm('affectortype').set('ordered')
gravity=node(dop,'gravity','gravity','重力加速度 -9.80665 m/s²。')
gravity.setInput(0,merge);gravity.parm('forcey').set(-cfg['gravity_m_s2'])
output=node(dop,'output','output','粒子と体積場の計算結果。');output.setInput(0,gravity);output.setDisplayFlag(True)

resultgeo=node(obj,'geo','simulation_result','計算粒子と表面。表面化は物理計算と独立した再構成処理。')
for child in resultgeo.children():child.destroy()
imp=node(resultgeo,'dopimport','fluid_particles','FLIP の Geometry データから実粒子を取得する。')
imp.setParms({'doppath':dop.path(),'objpattern':'water','geodatapath':'Geometry','importstyle':'fetch'})
surf=node(resultgeo,'particlefluidsurface::2.0','water_surface','条件 JSON の粒子間隔、ボクセル倍率 0.75 の表面再構成。')
surf.setInput(0,imp);surf.setParms({'particlesep':sep,'voxelsize':0.75,'dosmooth':0,'dofinalsmooth':0})
surf.setDisplayFlag(True);surf.setRenderFlag(True)
for n in (initial,bedgeo,dop,resultgeo,obj):n.layoutChildren()
hou.setFrame(1);hou.hipFile.save(str(hip_path))
hou.setUpdateMode(hou.updateMode.AutoUpdate)
shape.cook(force=True);pts.cook(force=True)
from collections import Counter
edges=Counter()
for polygon in shape.geometry().prims():
 vertices=[v.point().number() for v in polygon.vertices()]
 assert polygon.normal().length()>.5, '底床に退化面がある。'
 for a,b in zip(vertices,vertices[1:]+vertices[:1]):edges[tuple(sorted((a,b)))]+=1
assert edges and all(n==2 for n in edges.values()), '底床が単一の閉じた面ではない。'
if dop.parm('resimulate') is not None:dop.parm('resimulate').pressButton()
metrics=[];previous_ids=None;boundary_first=None
start=time.perf_counter()
for frame in range(1,args.frames+1):
 t=time.perf_counter();hou.setFrame(frame);imp.cook(force=True);g=imp.geometry()
 P=np.asarray(g.pointFloatAttribValues('P')).reshape(-1,3)
 V=np.asarray(g.pointFloatAttribValues('v')).reshape(-1,3)
 if len(P)<1000 or len(P)>200000:raise RuntimeError('想定範囲外の粒子数: '+str(len(P)))
 if not np.isfinite(P).all() or not np.isfinite(V).all():raise RuntimeError('非有限値が発生した。')
 speed=np.linalg.norm(V,axis=1)
 ids=set(g.pointIntAttribValues('id')) if g.findPointAttrib('id') else set()
 g.saveToFile(str(out/'particles'/f'water_{frame:04d}.bgeo.sc'))
 water=dop.simulation().findObject('water')
 fg=hou.Geometry()
 for field in ['surface','vel','collision']:
  field_geo=water.fieldGeometry(field)
  if field_geo is not None:fg.merge(field_geo)
 fg.saveToFile(str(out/'fields'/f'fields_{frame:04d}.bgeo.sc'))
 if frame==1:
  print('実粒子半径範囲',min(g.pointFloatAttribValues('pscale')),max(g.pointFloatAttribValues('pscale')),flush=True)
 if frame==2:
  col=water.fieldGeometry('collision').prims()[0]
  pr=water.fieldGeometry('pressure').prims()[0]
  print('衝突場確認',col.voxelSize(),col.sample((-3,.5,0)),col.sample((1,.2,0)),'圧力場',pr.resolution(),min(pr.allVoxels()),max(pr.allVoxels()),flush=True)
  assert np.prod(pr.resolution())>1, '圧力場が初期値のままである。'
 simsec=time.perf_counter()-t
 tm=time.perf_counter();surf.cook(force=True);sg=surf.geometry();sg.saveToFile(str(out/'surface'/f'water_{frame:04d}.bgeo.sc'))
 # 全粒子数×間隔³は厳密な水量ではなく粒子数量による代理量。
 right=(P[:,0]>cfg['length_m']/2-.4)&(P[:,1]>cfg['still_depth_m']+.15)
 if right.any() and boundary_first is None:boundary_first=frame
 m={'フレーム':frame,'時刻_s':(frame-1)/cfg['fps'],'粒子数':len(P),'粒子ID数':len(ids),'新規ID数':len(ids-previous_ids) if previous_ids is not None else None,'消失ID数':len(previous_ids-ids) if previous_ids is not None else None,'粒子数量体積代理_m3':len(P)*sep**3,'最大高さ_m':float(P[:,1].max()),'最高粒子位置_m':P[P[:,1].argmax()].tolist(),'速度中央値_m_s':float(np.median(speed)),'速度P99_m_s':float(np.percentile(speed,99)),'最大速度_m_s':float(speed.max()),'境界箱最小_m':P.min(axis=0).tolist(),'境界箱最大_m':P.max(axis=0).tolist(),'計算と粒子保存_s':simsec,'表面化と保存_s':time.perf_counter()-tm,'使用メモリ_MiB':rss_mb(),'表面頂点数':len(sg.points()),'表面プリミティブ数':len(sg.prims()),'下流波面の壁接近_初回フレーム':boundary_first}
 metrics.append(m);previous_ids=ids
 (out/'計測.json').write_text(json.dumps({'条件':cfg,'座標':'Houdini の Y が鉛直上向き。X 正方向へ進行。Z は横方向。','注意':'粒子数量体積代理は厳密な質量・体積ではない。初期条件は長波近似であり厳密な定常波解ではない。','フレーム別':metrics},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(m,ensure_ascii=False),flush=True)
 if rss_mb()>12000:raise RuntimeError('使用メモリの上限 12000 MiB に達した。')
 if time.perf_counter()-start>1200:raise RuntimeError('計算時間の上限 20 分に達した。')
print('計算完了',flush=True)
