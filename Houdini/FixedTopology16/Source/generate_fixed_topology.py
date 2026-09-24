"""手順16: 新規の解析式変形メッシュ。流体シミュレーションではない。"""
import hashlib, json, math, os
from pathlib import Path
assert os.getpid() == EXPECTED_PID == 53912 and hou.isUIAvailable()
ROOT = Path(STAGE)
s = getattr(hou.session, KEY)
assert abs(hou.fps() - s['fps']) < 1e-9, 'Global FPS must remain unchanged'
RATE = 30.0
MARKERS = [
 {'name':'unit_cube_1m','center':{'x':-5.0,'y':0.5,'z':-5.0},'size':{'x':1.0,'y':1.0,'z':1.0},'color':(0.9,0.75,0.15)},
 {'name':'axis_x_positive','center':{'x':5.0,'y':0.5,'z':0.0},'size':{'x':0.35,'y':1.0,'z':0.35},'color':(1.0,0.1,0.1)},
 {'name':'axis_y_positive','center':{'x':0.0,'y':2.0,'z':0.0},'size':{'x':0.35,'y':0.7,'z':0.35},'color':(0.1,1.0,0.1)},
 {'name':'axis_z_positive','center':{'x':0.0,'y':0.5,'z':5.0},'size':{'x':0.35,'y':1.0,'z':0.35},'color':(0.1,0.25,1.0)},
 {'name':'asym_p123','center':{'x':1.0,'y':2.0,'z':3.0},'size':{'x':0.3,'y':0.5,'z':0.7},'color':(1.0,0.15,0.8)},
]
def vec(values): return dict(zip(('x','y','z'), (float(x) for x in values)))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,data):
 (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def topology(g): return [p.number() for prim in g.prims() for p in prim.points()]
def grid_sample(g,frame,time):
 points=g.points()[:1089]
 assert len(points)==1089 and g.findPointAttrib('N') is not None
 p=[vec(pt.position()) for pt in points]; n=[vec(pt.attribValue('N')) for pt in points]
 assert all(q['y']>0.9 for q in n), 'Actual cooked grid normals must face upward'
 for marker_index,marker in enumerate(MARKERS):
  center=hou.Vector3(tuple(marker['center'][a] for a in 'xyz'))
  for corner in g.points()[1089+8*marker_index:1089+8*(marker_index+1)]:
   assert hou.Vector3(corner.attribValue('N')).dot(corner.position()-center)>0, 'Actual marker corner normals must point outward'
 assert all(math.isfinite(v) for seq in (p,n) for q in seq for v in q.values())
 return {'frame':frame,'time_seconds':time,'positions':p,'normals':n,
  'bounds_min':{axis:min(q[axis] for q in p) for axis in 'xyz'},
  'bounds_max':{axis:max(q[axis] for q in p) for axis in 'xyz'}}

if PHASE=='create':
 assert hou.node(OBJ_PATH) is None
 with hou.undos.group('GreatWave step16 owned transfer specimen'):
  container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
  assert container.path()==OBJ_PATH
  s['owned_nodes'].append((container,container.sessionId()))
  geo=container.createNode('geo',node_name='surface',run_init_scripts=False)
  base=geo.createNode('python',node_name='fresh_triangulated_grid_and_markers',run_init_scripts=False)
  base_code='''import hou\ng=hou.pwd().geometry()\ng.clear()\npath=g.addAttrib(hou.attribType.Prim,"path","")\ncd=g.addAttrib(hou.attribType.Point,"Cd",(0.1,0.45,0.85))\nkind=g.addAttrib(hou.attribType.Point,"sample_grid",0)\npts=[]\nfor z in range(33):\n for x in range(33):\n  p=g.createPoint(); p.setPosition((-4+x*0.25,0,-4+z*0.25)); p.setAttribValue(kind,1); pts.append(p)\nfor z in range(32):\n for x in range(32):\n  a=z*33+x; b=a+1; c=a+33; d=c+1\n  for indices in ((a,c,b),(b,c,d)):\n   poly=g.createPolygon()\n   for idx in reversed(indices): poly.addVertex(pts[idx])\n   poly.setAttribValue(path,"/kinematic_grid")\nmarkers=MARKERS_LITERAL\nfor m in markers:\n center=[m['center'][a] for a in 'xyz']; size=[m['size'][a] for a in 'xyz']; vertices=[]\n for v in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):\n  p=g.createPoint(); p.setPosition(tuple(center[i]+v[i]*size[i]/2 for i in range(3))); p.setAttribValue(cd,m['color']); vertices.append(p)\n for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)):\n  for tri in ((face[0],face[1],face[2]),(face[0],face[2],face[3])):\n   p=g.createPolygon()\n   for idx in reversed(tri): p.addVertex(vertices[idx])\n   p.setAttribValue(path,'/'+m['name'])\n'''.replace('MARKERS_LITERAL',repr(MARKERS))
  base.parm('python').set(base_code)
  deform=geo.createNode('attribwrangle',node_name='kinematic_sine_NOT_FLUID',run_init_scripts=False)
  deform.setInput(0,base)
  deform.parm('snippet').set('if (i@sample_grid == 1) { @P.y = 0.2 * sin(2 * M_PI * @P.x / 4.0 - M_PI * @Time); }')
  normal=geo.createNode('normal',node_name='computed_point_normals',run_init_scripts=False); normal.setInput(0,deform)
  items=list(normal.parm('type').menuItems()); labels=list(normal.parm('type').menuLabels())
  index=next(i for i,label in enumerate(labels) if label.lower() in ('points','point'))
  normal.parm('type').set(items[index])
  out=geo.createNode('null',node_name='OUT',run_init_scripts=False); out.setInput(0,normal); out.setDisplayFlag(True); out.setRenderFlag(True)
  geo.setDisplayFlag(True); container.setDisplayFlag(True)
  ropnet=container.createNode('ropnet',node_name='exports',run_init_scripts=False)
  rop=ropnet.createNode('alembic',node_name='exact_owned_surface',run_init_scripts=False)
  rop.parm('filename').set(str(ROOT/'Cache/fixed_topology_16.abc').replace('\\','/'))
  rop.parm('use_sop_path').set(1); rop.parm('sop_path').set('../../surface/OUT')
  assert rop.node(rop.parm('sop_path').eval())==out
  rop.parm('build_from_path').set(1); rop.parm('path_attrib').set('path')
  rop.parm('initsim').set(0); rop.parm('trange').set(1); rop.parm('motionBlur').set(0)
  rop.parmTuple('f').set((1.0,1+2*s['fps'],s['fps']/30))
  rop.parm('render_full_range').set(1)
  for name in ('tprerender','tpreframe','tpostframe','tpostrender'): rop.parm(name).set(0)
  assert not rop.inputs()
  s['out']=out; s['rop']=rop; s['container']=container
 result={'created':True,'owned_container':OBJ_PATH,'source_fps_preserved':hou.fps(),'alembic_sop_path':rop.parm('sop_path').eval(),'normal_menu':{'items':items,'labels':labels,'selected':items[index]},'grid_points':1089,'grid_triangles':2048,'markers':MARKERS,'classification':'kinematic analytic transfer test, not fluid simulation'}

elif PHASE=='sample':
 out=s['out']; samples=[]; hashes=[]; all_topology=None
 for k in range(61):
  time=k/RATE; frame=1+time*s['fps']; g=out.geometryAtFrame(frame)
  ids=topology(g)
  if all_topology is None: all_topology=ids
  assert ids==all_topology and len(g.points())==1129 and len(g.prims())==2108
  samples.append(grid_sample(g,frame,time))
  cache=ROOT/('Cache/bgeo/sample_%03d.bgeo.sc'%k); g.saveToFile(str(cache))
  reread=hou.Geometry(); reread.loadFromFile(str(cache))
  assert topology(reread)==ids and len(reread.points())==len(g.points())
  assert max((a.position()-b.position()).length() for a,b in zip(g.points(),reread.points()))<1e-7
  assert max((hou.Vector3(a.attribValue('N'))-hou.Vector3(b.attribValue('N'))).length() for a,b in zip(g.points(),reread.points()))<1e-7
  hashes.append({'sample':k,'path':str(cache.relative_to(ROOT)).replace('\\','/'),'sha256':sha(cache)})
 assert samples[0]['positions'] != samples[15]['positions']
 loop_error=max(abs(a[axis]-b[axis]) for a,b in zip(samples[0]['positions'],samples[60]['positions']) for axis in 'xyz')
 assert loop_error<1e-6
 report={'schema_version':1,'classification':'KINEMATIC_ANALYTIC_NOT_FLUID','grid_object_name':'kinematic_grid','fps':30,'houdini_session_fps':s['fps'],'time_to_houdini_frame':'frame = 1 + time_seconds * houdini_session_fps','coordinate_system':'Houdini right handed Y-up, meters','unity_expected_mapping':'(-x,y,z), scaleFactor=1, swapHandedness=true','samples':samples,'triangles':all_topology[:2048*3],'markers':MARKERS,'all_geometry_point_count':1129,'all_geometry_triangle_count':2108,'full_topology_sha256':hashlib.sha256(json.dumps(all_topology,separators=(',',':')).encode()).hexdigest(),'loop_endpoint_max_position_error_m':loop_error,'normal_source':'Houdini Normal SOP, point normals','all_grid_normals_y_above_0_9':True,'all_marker_corner_normals_outward':True,'bgeo_roundtrip_all_61_passed':True,'bgeo_files':hashes}
 write('Cache/reference_samples.json',report)
 result={'sample_count':61,'time_start':0,'time_end':2,'sample_rate':30,'full_topology_sha256':report['full_topology_sha256'],'bgeo_roundtrip_all_61_passed':True,'deformation_changed':True,'loop_endpoint_max_position_error_m':loop_error,'reference':str(ROOT/'Cache/reference_samples.json'),'reference_sha256':sha(ROOT/'Cache/reference_samples.json')}

elif PHASE=='export':
 rop=s['rop']; out=s['out']
 assert rop.node(rop.parm('sop_path').eval())==out and rop.parm('initsim').eval()==0 and not rop.inputs()
 rop.render(frame_range=(1.0,1.0+2*s['fps'],s['fps']/30),ignore_inputs=True)
 abc=ROOT/'Cache/fixed_topology_16.abc'; assert abc.is_file() and abc.stat().st_size>100
 import _alembic_hom_extensions as abcapi
 api_names=[name for name in dir(abcapi) if any(part in name.lower() for part in ('time','hierarchy','sample'))]
 result={'exported':True,'alembic_bytes':abc.stat().st_size,'sha256':sha(abc),'sop_path_exact_owned':True,'initialize_simulation_ops':False,'ignore_inputs':True,'current_fps_preserved':hou.fps(),'alembic_inspection_api_names':api_names}
 try: result['archive_time_range']=abcapi.alembicTimeRange(str(abc))
 except Exception as exc: result['archive_time_range_error']=str(exc)
 try: result['archive_hierarchy']=abcapi.alembicGetSceneHierarchy(str(abc),'/')
 except Exception as exc: result['archive_hierarchy_error']=str(exc)
 write('Evidence/alembic_export.json',result)

elif PHASE=='source_roundtrip':
 cpio=ROOT/'Source/fixed_topology_16.cpio'
 hou.node('/obj').saveItemsToFile((s['container'],),str(cpio),save_hda_fallbacks=False)
 assert hou.node(OBJ_PATH+'_roundtrip') is None
 clone=hou.node('/obj').createNode('subnet',node_name=NAME+'_roundtrip',run_init_scripts=False)
 s['owned_nodes'].append((clone,clone.sessionId())); clone.setDisplayFlag(False)
 clone.loadItemsFromFile(str(cpio),ignore_load_warnings=False)
 children=clone.children(); assert len(children)==1
 cloneout=children[0].node('surface/OUT'); assert cloneout is not None
 clone_rop=children[0].node('exports/exact_owned_surface')
 assert clone_rop.node(clone_rop.parm('sop_path').eval())==cloneout
 assert not clone_rop.inputs()
 for k in range(61):
  f=1+k/30*s['fps']; a=s['out'].geometryAtFrame(f); b=cloneout.geometryAtFrame(f)
  assert topology(a)==topology(b)
  assert max((pa.position()-pb.position()).length() for pa,pb in zip(a.points(),b.points()))<1e-7
 result={'owned_container_cpio_saved':True,'cpio_path':str(cpio),'cpio_sha256':sha(cpio),'loaded_only_owned_cpio':True,'all_61_sample_positions_and_topology_match':True,'relative_export_sop_resolves_to_clone':True,'hip_saved_loaded_cleared':False,'hiplc_roundtrip':'UNEXECUTED: second Steam GUI launch exited3; current user HIP deliberately untouched'}
 write('Evidence/source_roundtrip.json',result)
else: raise ValueError(PHASE)

