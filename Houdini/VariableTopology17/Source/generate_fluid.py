"""17：新規FLIPの小試料。既存ノード・外部形状は使用しない。"""
import hashlib, json, math, os, time
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
 with hou.undos.group('GreatWave 17 新規FLIP試料'):
  container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
  assert container.path()==OBJ_PATH
  s['owned_nodes'].append((container,container.sessionId()));s['container']=container
  geo=container.createNode('geo',node_name='fluid17',run_init_scripts=False)
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
   boundary.parm('activate').setExpression('$F <= 1.01',hou.exprLanguage.Hscript)
   sett(boundary,'velocity',(-sign*2.2,0,0))
   prev=boundary
  solver=geo.createNode('flipsolver',node_name='actual_FLIP_solver',run_init_scripts=False)
  for channel in range(3): solver.setInput(channel,prev,channel)
  for name,value in [('particlesep',SEP),('startframe',1),('timescale',1),('substep',2),('minimumsubsteps',1),('substeps',4),('cachemaxsize',1024),('dowaterline',0),('donarrowband',0),('veltransfer','flip'),('useground','ground'),('doreseeding',1),('seed',17)]: setp(solver,name,value)
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
  geo.layoutChildren()
  s.update({'out':out,'particles':outparticles,'solver':solver,'geo':geo,'samples':[],'fps':hou.fps()})
 result={'created':True,'container':OBJ_PATH,'fps':hou.fps(),'duration_seconds':2,'sample_rate':hou.fps(),'sample_count':int(2*hou.fps())+1,'particle_separation_m':SEP,'domain_size_m':[12,4,12],'domain_center_m':[0,1.5,0],'density':1000,'gravity_m_s2':9.80665,'source_centers':[[-.67,1.15,-.12],[.67,1.15,.12]],'source_radius_m':.45,'source_velocities_m_s':[[2.2,0,0],[-2.2,0,0]],'source_activation':'$F <= 1.01','global_substeps':2,'minimum_substeps':1,'maximum_substeps':4,'time_scale':1,'reseeding':True,'seed':17,'narrow_band':False,'waterline':False,'ground_y':0,'surface_tension':False,'surface_method':'Average Position','surface_voxel_scale':.75,'surface_voxel_m':.06,'mesh_adaptivity':0,'dilate_erode_smooth':False,'classification':'REAL_FLIP_SMALL_TRANSFER_SPECIMEN_NOT_OCEAN_VALIDATION'}
 write('Evidence/17_solver_conditions.json',result)

elif PHASE.startswith('sample:'):
 first,last=map(int,PHASE.split(':')[1:]);results=[]
 for k in range(first,last+1):
  start=time.monotonic();frame=1+k;particles=s['particles'].geometryAtFrame(frame);geometry=s['out'].geometryAtFrame(frame)
  assert not s['solver'].errors() and not s['out'].errors(),(s['solver'].errors(),s['out'].errors())
  assert len(particles.points())>0 and len(geometry.points())>0
  particle_file=ROOT/('Cache/particles_%03d.bgeo.sc'%k);mesh_file=ROOT/('Cache/surface_%03d.bgeo.sc'%k)
  particles.saveToFile(str(particle_file));geometry.saveToFile(str(mesh_file))
  for original,path in ((particles,particle_file),(geometry,mesh_file)):
   loaded=hou.Geometry();loaded.loadFromFile(str(path))
   assert len(loaded.points())==len(original.points()) and len(loaded.prims())==len(original.prims())
   for attribute in ('P','N','v'):
    if original.findPointAttrib(attribute): assert loaded.pointFloatAttribValues(attribute)==original.pointFloatAttribValues(attribute)
   assert [[p.number() for p in f.points()] for f in loaded.prims()]==[[p.number() for p in f.points()] for f in original.prims()]
  row={'sample':k,'frame':frame,'time_seconds':k/s['fps'],'particle_count':len(particles.points()),'mesh_points':len(geometry.points()),'mesh_primitives':len(geometry.prims()),'mesh_file':str(mesh_file.relative_to(ROOT)).replace('\\','/'),'particle_file':str(particle_file.relative_to(ROOT)).replace('\\','/'),'mesh_sha256':sha(mesh_file),'particle_sha256':sha(particle_file),'cook_seconds':round(time.monotonic()-start,4),'cache_reread_P_N_v_topology_match':True,'solver_warnings':list(s['solver'].warnings()),'mesh_warnings':list(s['out'].warnings())}
  s['samples'].append(row);results.append(row)
  write('Evidence/17_cache_index.json',{'samples':s['samples'],'fps':s['fps'],'duration_seconds':2,'units':'m','up_axis':'Y','source_fps_unchanged':hou.fps()==s['fps']})
 result={'samples':results}

elif PHASE=='save_source':
 cpio=ROOT/'Source/fluid17_owned.cpio'
 hou.node('/obj').saveItemsToFile((s['container'],),str(cpio),save_hda_fallbacks=False)
 result={'owned_cpio':str(cpio.relative_to(ROOT)),'sha256':sha(cpio),'hip_saved_loaded_cleared':False,'source_node_count':len(s['geo'].children()),'node_types':[n.type().name() for n in s['geo'].children()]}
 write('Evidence/17_source_saved.json',result)

elif PHASE=='cached_display':
 # 以降の表示は保存した実メッシュのみ。ソルバーを再評価しない。
 reader=s['geo'].createNode('file',node_name='DISPLAY_CACHED_SURFACE',run_init_scripts=False)
 reader.parm('file').set(str(ROOT/'Cache/surface_`padzero(3,$F-1)`.bgeo.sc').replace('\\','/'))
 reader.setDisplayFlag(True);reader.setRenderFlag(True);s['display_reader']=reader
 bounds=hou.BoundingBox()
 for row in s['samples']:
  cached=hou.Geometry();cached.loadFromFile(str(ROOT/row['mesh_file']));bounds.enlargeToContain(cached.boundingBox())
 s['capture_bounds']=bounds
 result={'cached_display':True,'pattern':reader.parm('file').unexpandedString()}
else: raise ValueError(PHASE)
