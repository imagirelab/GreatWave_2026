"""22のL6候補：内槽長だけを6mへ変更。初期粒子の変化も含む感度試験。"""
import ctypes, hashlib, json, math, os, struct, time
from pathlib import Path
assert os.getpid()==EXPECTED_PID and hou.isUIAvailable()
ROOT=Path(STAGE); s=getattr(hou.session,KEY)
assert hou.fps()==s['fps']
LAM=2.9903951732918226; L=6.0; W=.6; H=.6; SEP=float(globals().get('PARTICLE_SEPARATION',.04))
GRAVITY=float(globals().get('GRAVITY',9.81))
GRID=float(globals().get('GRID_SCALE',2));DRIVE=bool(globals().get('PISTON_ENABLED',True));RESEED=bool(globals().get('RESEEDING',True))
START=float(globals().get('PISTON_START_SECONDS',0));MESH_STRIDE=int(globals().get('MESH_STRIDE',1))
GAUGES=(.75,1.,1.25) if globals().get('THREE_GAUGES',False) else (.75,1.25)
CASE='GreatWave22_L6_'+('Piston' if DRIVE else 'Static')+'_dp'+str(SEP).replace('.','p')+'_grid'+str(GRID).replace('.','p')
if GRAVITY!=9.81:CASE+='_Gravity'+str(GRAVITY).replace('.','p')
if not RESEED:CASE+='_NoReseed'
if START>0:CASE+='_Preroll'+str(START).replace('.','p')
OMEGA=2*math.pi/1.5; AMP=.02480741527 if DRIVE else 0.0; RAMP=3.0
def write(name,value): (ROOT/'Evidence'/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def setp(n,k,v):
 p=n.parm(k); assert p is not None,(n.type().name(),k);p.set(v)
def sett(n,k,v):
 p=n.parmTuple(k);assert p is not None,(n.type().name(),k);p.set(v)
def vec(v):return list(map(float,v))
def bounds(g):return {'min':vec(g.boundingBox().minvec()),'max':vec(g.boundingBox().maxvec())}
def memory():
 class PMC(ctypes.Structure):
  _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
 class MS(ctypes.Structure):
  _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
 p=PMC();p.cb=ctypes.sizeof(p);m=MS();m.length=ctypes.sizeof(m)
 kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
 ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(kernel.GetCurrentProcess()),ctypes.byref(p),p.cb)
 ok2=kernel.GlobalMemoryStatusEx(ctypes.byref(m));assert ok and ok2
 return {'private_commit_bytes':p.PrivateUsage,'working_set_bytes':p.WorkingSetSize,'peak_working_set_process_lifetime_bytes':p.PeakWorkingSetSize,'available_physical_bytes':m.available}
def motion(t):
 t=max(0,t-START)
 q=max(0,min(1,t/RAMP));r=.5*(1-math.cos(math.pi*q));dr=.5*math.pi/RAMP*math.sin(math.pi*q) if 0<t<RAMP else 0
 return AMP*r*math.sin(OMEGA*t),AMP*(dr*math.sin(OMEGA*t)+r*OMEGA*math.cos(OMEGA*t))
def fields(g):
 out=[]
 for p in g.prims():
  r={'number':p.number(),'type':str(p.type()),'name':p.attribValue('name') if g.findPrimAttrib('name') else None}
  if isinstance(p,(hou.Volume,hou.VDB)):r.update({'bounds':bounds(p),'resolution':vec(p.resolution()),'voxel_m':vec(p.voxelSize()),'transform':list(p.transform().asTuple())})
  out.append(r)
 return out
def gauge(vol,x,z):
 b=vol.boundingBox();lo=b.minvec();hi=b.maxvec();eps=1e-5
 if not(lo[0]+eps<x<hi[0]-eps and lo[2]+eps<z<hi[2]-eps):return {'valid':False,'reason':'outside_xz'}
 bottom=max(-H+.12,lo[1]+.01);top=min(.25,hi[1]-.01)
 ys=[bottom+(top-bottom)*j/120 for j in range(121)];vs=[float(vol.sample((x,y,z))) for y in ys]
 crossings=[j for j in range(120) if vs[j]<0 and vs[j+1]>=0]
 valid=all(math.isfinite(v) for v in vs) and vs[0]<0 and vs[-1]>0 and len(crossings)==1
 result={'x':x,'z':z,'valid':valid,'crossing_count':len(crossings),'bottom_value':vs[0],'top_value':vs[-1],'bracket_y':[bottom,top]}
 if valid:
  j=crossings[0];a=ys[j];b=ys[j+1]
  for _ in range(25):
   mid=(a+b)/2
   if vol.sample((x,mid,z))<0:a=mid
   else:b=mid
  result['eta_m']=(a+b)/2
 return result

if PHASE=='create':
 assert hou.node(OBJ_PATH) is None
 hou.setUpdateMode(hou.updateMode.AutoUpdate)
 with hou.undos.group('GreatWave 22 新規小水槽'):
  own=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False);s['owned_nodes'].append((own,own.sessionId()));s['container']=own
  geo=own.createNode('geo',node_name='wave22',run_init_scripts=False)
  def box(name,size,center):
   n=geo.createNode('box',node_name=name,run_init_scripts=False);sett(n,'size',size);sett(n,'t',center);return n
  domain=geo.createNode('flipcontainer',node_name='domain_with_margin',run_init_scripts=False)
  for k,v in [('particlesep',SEP),('gridscale',GRID),('gravity',GRAVITY),('density',1000),('doid',1),('dosurfacetension',0),('viscosity',0)]:setp(domain,k,v)
  sett(domain,'size',(L+1.2,1.8,1.8));sett(domain,'t',(L/2,-.15,0))
  water=box('initial_rest_water',(L,H,W),(L/2,-H/2,0))
  initial=geo.createNode('flipboundary',node_name='initial_water_once',run_init_scripts=False)
  for ch in range(3):initial.setInput(ch,domain,ch)
  initial.setInput(3,water);setp(initial,'type','source');setp(initial,'boundarytype','none');sett(initial,'velocity',(0,0,0))
  initial.parm('activate').setExpression('$FF <= 1.001',hou.exprLanguage.Hscript)
  walls=[box('bottom',(L+.8,.24,1.2),(L/2,-H-.12,0)),box('side_minus',(L+.8,1.3,.24),(L/2,-.2,-W/2-.12)),box('side_plus',(L+.8,1.3,.24),(L/2,-.2,W/2+.12)),box('end_wall',(.24,1.3,1.2),(L+.12,-.2,0))]
  piston=box('piston_fixed_topology',(.24,1.3,1.2),(-.12,-.2,0))
  expression='import math\nt=max(0,(hou.frame()-1)/hou.fps()-%r)\nr=.5*(1-math.cos(math.pi*min(1,t/3.0)))\nreturn -.12+%r*r*math.sin(%r*t)'%(START,AMP,OMEGA)
  piston.parm('tx').setExpression(expression,hou.exprLanguage.Python)
  merge=geo.createNode('merge',node_name='all_solid_colliders',run_init_scripts=False)
  for i,n in enumerate(walls+[piston]):merge.setInput(i,n)
  collision=geo.createNode('flipcollide',node_name='actual_collision_velocity',run_init_scripts=False)
  for ch in range(3):collision.setInput(ch,initial,ch)
  collision.setInput(3,merge)
  for k,v in [('computevel',1),('computevelsubstep',5),('velscale',1),('dovolume',1),('dosurface',1)]:setp(collision,k,v)
  collisionout=geo.createNode('null',node_name='COLLISION_FIELDS',run_init_scripts=False);collisionout.setInput(0,collision,2)
  solver=geo.createNode('flipsolver',node_name='actual_wave_solver',run_init_scripts=False)
  for ch in range(3):solver.setInput(ch,collision,ch)
  for k,v in [('particlesep',SEP),('gridscale',GRID),('startframe',1),('timescale',1),('substep',5),('minimumsubsteps',1),('substeps',4),('cachemaxsize',768),('dowaterline',0),('donarrowband',0),('veltransfer','apic'),('useground','none'),('doreseeding',int(RESEED)),('seed',2101),('useadaptivepressure',0),('collision','particle')]:setp(solver,k,v)
  solver.allowEditingOfContents();dop=solver.node('dopnet1');assert dop is not None
  for k,v in [('timestep',1/120),('interpolate',0),('cachesubsteps',1)]:p=dop.parm(k);p.deleteAllKeyframes();p.set(v)
  particles=geo.createNode('null',node_name='SOLVER_FIELDS_PARTICLES',run_init_scripts=False);particles.setInput(0,solver)
  mesh=geo.createNode('particlefluidsurface::3.0',node_name='display_meshing_only',run_init_scripts=False);mesh.setInput(0,particles)
  for k,v in [('particlesep',SEP),('surfmethod','particlefluid'),('voxelsize',.5),('adaptivity',0),('dodilate',0),('dosmooth',0),('doerode',0),('dofinalsmooth',0),('closedcontainer',0),('closedends',0),('flattengeo',0)]:setp(mesh,k,v)
  convert=geo.createNode('convert',node_name='display_polygons',run_init_scripts=False);convert.setInput(0,mesh);setp(convert,'totype','poly')
  out=geo.createNode('null',node_name='DISPLAY_SURFACE',run_init_scripts=False);out.setInput(0,convert)
  out.setDisplayFlag(True);out.setRenderFlag(True);geo.setDisplayFlag(True);own.setDisplayFlag(True)
  disk_settings=[]
  for p in dop.parms():
   label=p.parmTemplate().label()
   if label=='Allow Caching To Disk':
    before=p.eval();p.deleteAllKeyframes();p.set(0);disk_settings.append({'name':p.name(),'label':label,'before':before,'applied':p.eval()})
  assert len(disk_settings)==1 and disk_settings[0]['applied']==0
  s['disk_settings']=disk_settings
  s.update({'geo':geo,'initial':initial,'piston':piston,'collision':collision,'collisionout':collisionout,'solver':solver,'dop':dop,'particles':particles,'out':out,'samples':[]})
 result={'case_id':CASE,'gravity_domain_actual_m_s2':domain.evalParm('gravity'),'tank_inner_m':[L,H,W],'particle_separation_m':SEP,'collision_pressure_voxel_expected_m':SEP*GRID,'display_voxel_m':SEP*.5,'piston_half_amplitude_m':AMP,'piston_ramp_seconds':RAMP,'source_once':True,'boundary_flow_input_connected':solver.input(3) is not None,'air_top_open':True,'absorber_implemented':False,'closed_end_wall':True,'global_fps':hou.fps(),'disk_settings':s['disk_settings'],'dop_cache_parameters':[{ 'name':p.name(),'value':p.eval()} for p in dop.parms() if 'cache' in p.name().lower() and p.parmTemplate().type()!=hou.parmTemplateType.String],'velocity_transfer_token':solver.parm('veltransfer').menuItems()[solver.evalParm('veltransfer')],'solver_parameters':{k:solver.evalParm(k) for k in ('particlesep','gridscale','substep','minimumsubsteps','substeps','veltransfer','doreseeding','seed','useadaptivepressure','collision','dowaterline','donarrowband')},'collision_parameters':{k:collision.evalParm(k) for k in ('computevel','computevelsubstep','velscale','dovolume','dosurface')},'memory':memory()}
 result.update({'piston_start_absolute_seconds':START,'solver_sampling_hz':60,'mesh_sampling_hz':60/MESH_STRIDE,'diagnostic_gauge_x_wavelengths':list(GAUGES),'stability_gate':{'window_seconds':.75,'minimum_consecutive_windows':2,'maximum_mean_change_m':.003,'maximum_residual_rms_m':.003,'maximum_linear_trend_change_per_window_m':.003,'maximum_proxy_relative_window_change':.01,'meaning_ja':'駆動開始を検討する診断。初期水深・収支・理論精度の合格ではない。'}})
 write('22_pilot_conditions.json',result)

elif PHASE=='initialization_probe':
 # 対象はこの実行で生成・登録した所有ソルバー内部だけ。既存HIPは走査しない。
 assert s['solver'].path().startswith(OBJ_PATH+'/')
 selected=[]
 for n in (s['solver'],)+s['solver'].allSubChildren():
  type_name=n.type().name().split('::')[0]
  if n is not s['solver'] and type_name not in ('flipsolver','flipobject') and 'gravity' not in type_name:continue
  settings=[]
  for parm in n.parms():
   label=parm.parmTemplate().label()
   if any(word in label.lower() for word in ('initial surface','waterline','narrow band','radius scale','smooth surface','update surface','reseeding','birth threshold','death threshold','oversampl','initialize','input type','particle separation','grid scale','surface extrapolation','gravity','force')):
    value=parm.eval()
    entry={'name':parm.name(),'label':label,'value':value}
    if parm.parmTemplate().type()==hou.parmTemplateType.Menu:
     entry['menu_token']=parm.menuItems()[value];entry['menu_label']=parm.menuLabels()[value]
    settings.append(entry)
  selected.append({'relative_path':n.path()[len(OBJ_PATH)+1:],'type':n.type().name(),'parameters':settings})
 result={'owned_path':OBJ_PATH,'existing_scene_read':False,'nodes':selected,
         'actual_boundary_flow_connected':s['solver'].input(3) is not None,
         'source_activation_expression':s['initial'].parm('activate').expression(),
         'source_activation_substep_values':[{'seconds':t,'global_frame':1+t*hou.fps(),'value':s['initial'].parm('activate').evalAtFrame(1+t*hou.fps())} for t in (0,1/120,1/60)],
         'solver_initialsurface_actual':s['solver'].evalParm('initialsurface'),
         'solver_partsep_actual':s['solver'].evalParm('partsep'),'solver_extrapdist_actual':s['solver'].evalParm('extrapdist')}
 write('22_initialization_schema.json',result)

elif PHASE=='collision_probe':
 rows=[]
 for k in (0,8):
  t=k/60;hou.setFrame(1+t*hou.fps());s['collisionout'].cook(force=True);s['piston'].cook(force=True);g=s['collisionout'].geometry().freeze()
  row={'t':t,'fields':fields(g),'point_attributes':[(a.name(),a.size(),str(a.dataType())) for a in g.pointAttribs()],'points':len(g.points()),'primitives':len(g.prims()),'piston_expected':motion(t),'piston_actual_box_center_x':s['piston'].geometry().boundingBox().center()[0],'piston_errors':list(s['piston'].errors()),'collision_errors':list(s['collision'].errors()),'piston_parm':s['piston'].evalParm('tx'),'piston_points':len(s['piston'].geometry().points()),'update_mode':str(hou.updateModeSetting())}
  assert len(g.prims())>0 and not s['collision'].errors()
  vf=[p for p in g.prims() if isinstance(p,hou.VDB) and p.attribValue('name')=='vel'];assert len(vf)==1
  row['collision_velocity_samples']=[{'at':[x,-.3,0],'v':vec(vf[0].samplev((x,-.3,0)))} for x in (-.12+motion(t)[0],motion(t)[0],L+.12)]
  row['finite_difference_velocity_backward_m_s']=(motion(t)[0]-motion(max(0,t-1/120))[0])*120
  if g.findPointAttrib('v'):
   velocities=[vec(p.attribValue('v')) for p in g.points()];row['point_velocity_extrema']={'min':[min(v[a] for v in velocities) for a in range(3)],'max':[max(v[a] for v in velocities) for a in range(3)]}
  rows.append(row)
 result={'rows':rows};write('22_collision_probe.json',result)

elif PHASE.startswith('sample:'):
 k=int(PHASE.split(':')[1]);t=k/60;started=time.monotonic();hou.setFrame(1+t*hou.fps())
 s['particles'].cook(force=True);raw=s['particles'].geometry().freeze();sim=s['dop'].simulation()
 held={v.point().number() for prim in raw.prims() for v in prim.vertices()};points=[p for p in raw.points() if p.number() not in held]
 p=[vec(q.position()) for q in points];v=[vec(q.attribValue('v')) for q in points]
 ids={q.attribValue('id') for q in points}
 if k==0:
  # 幾何が変わるため旧P/IDとの一致は要求せず、新初期状態の健全性を実記録する。
  pairs=sorted((q.attribValue('id'),tuple(q.position())) for q in points)
  initial_finite=all(math.isfinite(c) for q in p+v for c in q)
  initial_inside=all(-.02<=q[0]<=L+.02 and -H-.02<=q[1]<=.02 and abs(q[2])<=W/2+.02 for q in p)
  initial_unique=len(ids)==len(points)
  identity={'actual_count':len(points),'P_finite':initial_finite,'ID_unique':initial_unique,
            'within_inner_bounds_tolerance_20mm':initial_inside,
            'P_ID_sorted_sha256':hashlib.sha256(json.dumps(pairs,separators=(',',':')).encode('utf8')).hexdigest(),
            'old_initial_identity_required':False,
            'meaning_ja':'L変更で初期配置は別条件。旧53,500粒子との一致や純粋な格子位相の因果を主張しない。'}
  write('22_initial_particle_identity.json',identity)
  assert len(points)>0 and initial_finite and initial_inside and initial_unique
 births=sorted(ids-s.get('previous_ids',ids));deaths=sorted(s.get('previous_ids',ids)-ids);s['previous_ids']=ids
 volumes=[q for q in raw.prims() if isinstance(q,hou.Volume) and q.attribValue('name')=='surface'];assert len(volumes)==1
 vol=volumes[0];gauge_rows=[gauge(vol,LAM*f,0) for f in GAUGES]
 surface=None
 if k%MESH_STRIDE==0:
  s['out'].cook(force=True);surface=s['out'].geometry().freeze();assert len(surface.prims())>0
 for gr in gauge_rows:
  if surface is None:
   gr.update({'mesh_sampled':False,'mesh_vertical_hit_valid':None,'mesh_eta_m':None,'mesh_minus_solver_m':None});continue
  gr['mesh_sampled']=True
  pos=hou.Vector3();normal=hou.Vector3();uvw=hou.Vector3();hit=surface.intersect(hou.Vector3((gr['x'],.4,gr['z'])),hou.Vector3((0,-1,0)),pos,normal,uvw)
  gr['mesh_vertical_hit_valid']=hit>=0;gr['mesh_eta_m']=float(pos[1]) if hit>=0 else None;gr['mesh_minus_solver_m']=float(pos[1])-gr['eta_m'] if hit>=0 and gr['valid'] else None
 cg=s['collisionout'].geometry();cv=[q for q in cg.prims() if isinstance(q,hou.VDB) and q.attribValue('name')=='vel'];assert len(cv)==1
 actual_collision_v=vec(cv[0].samplev((-.12+motion(t)[0],-.3,0)))
 surfacepath=ROOT/('Cache/mesh_%03d.bgeo.sc'%k)
 if surface is not None:surface.saveToFile(str(surfacepath))
 mins=[min(q[a] for q in p) for a in range(3)];maxs=[max(q[a] for q in p) for a in range(3)]
 leak=sum(q[1]<-H-.02 or abs(q[2])>W/2+.02 or q[0]<motion(t)[0]-.02 or q[0]>L+.02 for q in p)
 path=ROOT/('Cache/pilot_%03d.bgeo.sc'%k);path.parent.mkdir(exist_ok=True);raw.saveToFile(str(path))
 loaded=hou.Geometry();loaded.loadFromFile(str(path))
 assert loaded.pointFloatAttribValues('P')==raw.pointFloatAttribValues('P') and loaded.pointFloatAttribValues('v')==raw.pointFloatAttribValues('v')
 loaded_surface=[q for q in loaded.prims() if isinstance(q,hou.Volume) and q.attribValue('name')=='surface'];assert len(loaded_surface)==1 and loaded_surface[0].allVoxels()==vol.allVoxels()
 if surface is not None:
  meshreread=hou.Geometry();meshreread.loadFromFile(str(surfacepath));assert meshreread.pointFloatAttribValues('P')==surface.pointFloatAttribValues('P')
 row={'sample':k,'requested_seconds':t,'global_frame':hou.frame(),'simulation_seconds':sim.time(),'simulation_dt':sim.timestep(),'simulation_memory_bytes':sim.memoryUsage(),'particle_count':len(p),'particle_pscale_min_max_m':[min(q.attribValue('pscale') for q in points),max(q.attribValue('pscale') for q in points)] if raw.findPointAttrib('pscale') else None,'cache_reread_P_v_surface_voxels_match':True,'mesh_cache_reread_P_match':True if surface is not None else None,'particle_velocity_rms_m_s':math.sqrt(sum(sum(c*c for c in q) for q in v)/len(v)),'particle_velocity_max_m_s':max(math.sqrt(sum(c*c for c in q)) for q in v),'particle_id_births_since_previous':births,'particle_id_deaths_since_previous':deaths,'particle_ids_unique':len({q.attribValue('id') for q in points})==len(points),'particle_min_m':mins,'particle_max_m':maxs,'outside_inner_walls_beyond_20mm':leak,'finite_pv':all(math.isfinite(x) for q in p+v for x in q),'surface_field':fields(raw),'gauges':gauge_rows,'piston_displacement_m':motion(t)[0],'piston_velocity_m_s':motion(t)[1],'piston_actual_collision_velocity_m_s':actual_collision_v,'wave_seconds':t-START,'piston_started':t>=START,'mesh_sampled':surface is not None,'mesh_points':len(surface.points()) if surface is not None else None,'mesh_faces':len(surface.prims()) if surface is not None else None,'mesh_file_sha256':hashlib.sha256(surfacepath.read_bytes()).hexdigest() if surface is not None else None,'cache_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cache_bytes':path.stat().st_size,'negative_voxel_volume_proxy_m3':sum(q<0 for q in vol.allVoxels())*math.prod(vol.voxelSize()),'cook_seconds':time.monotonic()-started,'memory':memory(),'solver_errors':list(s['solver'].errors()),'solver_warnings':list(s['solver'].warnings())}
 s['samples'].append(row);write('22_pilot_samples.json',{'case_id':CASE,'global_fps':hou.fps(),'samples':s['samples']})
 assert abs(sim.time()-t)<1e-6 and abs(sim.timestep()-1/120)<1e-6
 assert row['finite_pv'] and row['particle_ids_unique'] and not row['solver_errors'] and not row['solver_warnings']
 assert leak==0 and all(q['valid'] and q['mesh_vertical_hit_valid'] is not False for q in gauge_rows),(leak,gauge_rows)
 assert abs(actual_collision_v[0]-motion(t)[1])<1e-4 and max(abs(actual_collision_v[a]) for a in (1,2))<1e-6
 assert len(p)<2*s['samples'][0]['particle_count'] and row['memory']['available_physical_bytes']>8*1024**3
 assert row['negative_voxel_volume_proxy_m3']>.8*s['samples'][0]['negative_voxel_volume_proxy_m3'] and row['cook_seconds']<30
 result=row
