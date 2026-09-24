"""19：新規FLIPの小試料。既存ノード・外部形状は使用しない。"""
import hashlib, json, math, os, struct, time
from pathlib import Path
assert os.getpid()==EXPECTED_PID and hou.isUIAvailable()
ROOT=Path(STAGE)
s=getattr(hou.session,KEY)
assert hou.fps()==s['fps']
SEP=.08
def vec(v): return dict(zip('xyz',map(float,v)))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,data): (ROOT/path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def setp(node,name,value):
 p=node.parm(name); assert p is not None,(node.type().name(),name)
 p.set(value)
def sett(node,name,value):
 p=node.parmTuple(name); assert p is not None,(node.type().name(),name)
 p.set(value)

if PHASE=='create':
 assert hou.node(OBJ_PATH) is None
 with hou.undos.group('GreatWave 19 新規FLIP試料'):
  container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
  assert container.path()==OBJ_PATH
  s['owned_nodes'].append((container,container.sessionId()));s['container']=container
  geo=container.createNode('geo',node_name='fluid19',run_init_scripts=False)
  domain=geo.createNode('flipcontainer',node_name='domain',run_init_scripts=False)
  setp(domain,'particlesep',SEP);sett(domain,'size',(12,4,12));sett(domain,'t',(0,1.5,0));setp(domain,'doid',1)
  setp(domain,'gravity',9.80665);setp(domain,'density',1000);setp(domain,'dosurfacetension',0)
  prev=domain
  for i,sign in enumerate((-1,1)):
   sphere=geo.createNode('sphere',node_name='initial_sphere_'+str(i),run_init_scripts=False)
   sett(sphere,'rad',(.45,.45,.45));sett(sphere,'t',(sign*.67,1.15,sign*.12))
   boundary=geo.createNode('flipboundary',node_name='initial_source_'+str(i),run_init_scripts=False)
   for channel in range(3): boundary.setInput(channel,prev,channel)
   boundary.setInput(3,sphere)
   setp(boundary,'type','source');setp(boundary,'boundarytype','none')
   boundary.parm('activate').setExpression('$FF <= 1.001',hou.exprLanguage.Hscript)
   sett(boundary,'velocity',(-sign*2.2,0,0))
   prev=boundary
  solver=geo.createNode('flipsolver',node_name='actual_FLIP_solver',run_init_scripts=False)
  for channel in range(3): solver.setInput(channel,prev,channel)
  for name,value in [('particlesep',SEP),('startframe',1),('timescale',1),('substep',2),('minimumsubsteps',1),('substeps',4),('cachemaxsize',1024),('dowaterline',0),('donarrowband',0),('veltransfer','flip'),('useground','ground'),('doreseeding',1),('seed',19)]: setp(solver,name,value)
  sett(solver,'ground_pos',(0,0,0))
  outparticles=geo.createNode('null',node_name='PARTICLES',run_init_scripts=False);outparticles.setInput(0,solver)
  mesh=geo.createNode('particlefluidsurface::3.0',node_name='remesh_every_frame',run_init_scripts=False);mesh.setInput(0,outparticles)
  for name,value in [('particlesep',SEP),('surfmethod','particlefluid'),('voxelsize',.75),('adaptivity',0),('dodilate',0),('dosmooth',0),('doerode',0),('dofinalsmooth',0)]: setp(mesh,name,value)
  polygons=geo.createNode('convert',node_name='explicit_polygons',run_init_scripts=False);polygons.setInput(0,mesh)
  setp(polygons,'totype','poly')
  normal=geo.createNode('normal',node_name='point_normals',run_init_scripts=False);normal.setInput(0,polygons)
  parm=normal.parm('type');items=parm.menuItems();labels=parm.menuLabels();parm.set(items[next(i for i,t in enumerate(labels) if t.lower() in ('point','points'))])
  color=geo.createNode('attribwrangle',node_name='display_blue',run_init_scripts=False);color.setInput(0,normal);setp(color,'snippet','@Cd = set(0.08,0.4,0.75);')
  out=geo.createNode('null',node_name='SURFACE',run_init_scripts=False);out.setInput(0,color)
  out.setDisplayFlag(True);out.setRenderFlag(True);geo.setDisplayFlag(True);container.setDisplayFlag(True)
  # 既存ノードの配置を変更しない。
  s.update({'out':out,'particles':outparticles,'solver':solver,'geo':geo,'samples':[],'fps':hou.fps()})
  # 今回作ったinstanceだけを編集可能にし、共有定義や既存HIPのsolverへ触れない。
  solver.allowEditingOfContents()
  dop=solver.node('dopnet1');assert dop is not None
  for name,value in [('timestep',1/120),('interpolate',0),('cachesubsteps',1)]:
   p=dop.parm(name);assert p is not None;p.deleteAllKeyframes();p.set(value)
  s['dop']=dop
 result={'created':True,'container':OBJ_PATH,'global_fps_unchanged':hou.fps(),'duration_seconds':2,'sample_rate':60,'sample_count':121,'subset_rate':30,'subset_count':61,'particle_separation_m':SEP,'domain_size_m':[12,4,12],'domain_center_m':[0,1.5,0],'density_kg_m3':1000,'gravity_m_s2':9.80665,'source_centers':[[-.67,1.15,-.12],[.67,1.15,.12]],'source_radius_m':.45,'source_velocities_m_s':[[2.2,0,0],[-2.2,0,0]],'source_activation':'$FF <= 1.001','sop_substep_parameter':2,'owned_dop_timestep_seconds':1/120,'dop_interpolation':False,'cache_substeps':True,'minimum_solver_substeps':1,'maximum_solver_substeps':4,'time_scale':1,'reseeding':True,'seed':19,'narrow_band':False,'waterline':False,'ground_y':0,'surface_tension':False,'surface_method':'Average Position','surface_voxel_scale':.75,'surface_voxel_m':.06,'mesh_adaptivity':0,'dilate_erode_smooth':False,'classification':'NEW_REAL_FLIP_SAMPLING_SPECIMEN_NOT_OCEAN_VALIDATION'}
 write('Evidence/19_solver_conditions.json',result)
 (ROOT/'Exports').mkdir(exist_ok=True)
 with (ROOT/'Exports/reference60.bytes').open('wb') as f:f.write(struct.pack('<8siii',b'GW19REF1',1,121,60))

elif PHASE=='probe':
 solver=s['solver'];dopnets=[n for n in solver.allSubChildren() if n.type().name()=='dopnet']
 result={'solver_parameters':[{'name':p.name(),'type':str(p.parmTemplate().type()),'value':p.eval()} for p in solver.parms() if any(x in p.name().lower() for x in ('sub','cache','time','frame'))],
 'owned_dopnets':[{'path':n.path(),'parameters':[{'name':p.name(),'type':str(p.parmTemplate().type()),'value':p.eval(),'expression':p.unexpandedString() if p.parmTemplate().type()==hou.parmTemplateType.String else None} for p in n.parms() if any(x in p.name().lower() for x in ('step','time','cache','frame','inter'))]} for n in dopnets]}
 write('Evidence/19_owned_clock_schema.json',result)

elif PHASE=='pilot':
 import struct
 rows=[]
 for k in range(9):
  requested=k/60;frame=1+requested*hou.fps();start=time.monotonic()
  # geometryAtFrameの暗黙補間を認めず、実DOP時計と厳密時刻を併記する。
  hou.setFrame(frame)
  raw=s['particles'].geometry().freeze();surface=s['out'].geometry().freeze()
  simulation=s['dop'].simulation()
  used={v.point().number() for prim in raw.prims() for v in prim.vertices()}
  points=[p for p in raw.points() if p.number() not in used]
  values=[float(x) for p in points for x in p.position()]
  row={'sample':k,'requested_seconds':requested,'global_frame':hou.frame(),'global_seconds':hou.time(),'simulation_seconds':simulation.time(),'simulation_timestep':simulation.timestep(),'simulation_memory_bytes':simulation.memoryUsage(),'particles':len(points),'particle_id_unique':len({p.attribValue('id') for p in points})==len(points),'particle_position_sha256':hashlib.sha256(struct.pack('<%df'%len(values),*values)).hexdigest(),'surface_points':len(surface.points()),'surface_faces':len(surface.prims()),'surface_P_sha256':hashlib.sha256(struct.pack('<%df'%len(surface.pointFloatAttribValues('P')),*surface.pointFloatAttribValues('P'))).hexdigest(),'cook_seconds':time.monotonic()-start,'solver_errors':list(s['solver'].errors())}
  rows.append(row)
  write('Evidence/19_clock_pilot.json',{'global_fps':hou.fps(),'dop_timestep_parameter':s['dop'].evalParm('timestep'),'dop_interpolate':s['dop'].evalParm('interpolate'),'dop_cache_substeps':s['dop'].evalParm('cachesubsteps'),'samples':rows})
 result={'rows':rows}

elif PHASE.startswith('sample:'):
 first,last=map(int,PHASE.split(':')[1:]);rows=[]
 for k in range(first,last+1):
  start=time.monotonic();requested=k/60;hou.setFrame(1+requested*hou.fps())
  particles=s['particles'].geometry().freeze();surface=s['out'].geometry().freeze();simulation=s['dop'].simulation()
  assert abs(simulation.time()-requested)<1e-6 and abs(simulation.timestep()-1/120)<1e-6
  assert not s['solver'].errors() and not s['out'].errors()
  held={v.point().number() for prim in particles.prims() for v in prim.vertices()};points=[p for p in particles.points() if p.number() not in held]
  ids=[p.attribValue('id') for p in points];pv=[float(x) for p in points for x in p.position()];vel=[float(x) for p in points for x in p.attribValue('v')]
  p=surface.pointFloatAttribValues('P');n=surface.pointFloatAttribValues('N');tri=[]
  for prim in surface.prims():
   corners=[x.number() for x in prim.points()]
   for j in range(1,len(corners)-1):tri.extend((corners[0],corners[j],corners[j+1]))
  assert p and len(p)==len(n) and len(ids)==len(set(ids)) and all(math.isfinite(x) for x in p+n+tuple(pv)+tuple(vel))
  surfacepath=ROOT/('Cache/surface_%03d.bgeo.sc'%k);particlepath=ROOT/('Cache/particles_%03d.bgeo.sc'%k)
  surface.saveToFile(str(surfacepath));particles.saveToFile(str(particlepath))
  for actual,path in ((surface,surfacepath),(particles,particlepath)):
   loaded=hou.Geometry();loaded.loadFromFile(str(path));assert len(loaded.prims())==len(actual.prims())
   for attr in ('P','N','v'):
    if actual.findPointAttrib(attr):assert loaded.pointFloatAttribValues(attr)==actual.pointFloatAttribValues(attr)
  with (ROOT/'Exports/reference60.bytes').open('ab') as f:
   f.write(struct.pack('<ifii',k,requested,len(p)//3,len(tri)));f.write(struct.pack('<%df'%len(p),*p));f.write(struct.pack('<%df'%len(n),*n));f.write(struct.pack('<%di'%len(tri),*tri))
  row={'sample60':k,'sample30':k//2 if k%2==0 else None,'relative_seconds':requested,'global_frame':hou.frame(),'simulation_seconds':simulation.time(),'simulation_timestep':simulation.timestep(),'simulation_memory_bytes':simulation.memoryUsage(),'particle_count':len(points),'particle_IDs_unique':True,'particle_P_sha256':hashlib.sha256(struct.pack('<%df'%len(pv),*pv)).hexdigest(),'mesh_points':len(p)//3,'triangles':len(tri)//3,'mesh_P_sha256':hashlib.sha256(struct.pack('<%df'%len(p),*p)).hexdigest(),'mesh_topology_sha256':hashlib.sha256(struct.pack('<%di'%len(tri),*tri)).hexdigest(),'surface_file':str(surfacepath.relative_to(ROOT)).replace('\\','/'),'surface_sha256':sha(surfacepath),'particle_file':str(particlepath.relative_to(ROOT)).replace('\\','/'),'particle_sha256':sha(particlepath),'cache_reread_P_N_v_match':True,'cook_seconds':time.monotonic()-start,'solver_errors':list(s['solver'].errors()),'solver_warnings':list(s['solver'].warnings())}
  s['samples'].append(row);rows.append(row);write('Evidence/19_cache_index.json',{'clip_id':'GreatWave19_FLIP60_01','units':'m','up':'Y','source_fps':hou.fps(),'sampling_rate':60,'interpolation':False,'subset30':'even master sample indices; no new simulation','samples':s['samples']})
 result={'samples':rows}

elif PHASE=='save_source':
 path=ROOT/'Source/fluid19_owned.cpio';hou.node('/obj').saveItemsToFile((s['container'],),str(path),save_hda_fallbacks=False)
 result={'source':str(path),'sha256':sha(path),'hip_saved':False};write('Evidence/19_source_saved.json',result)


