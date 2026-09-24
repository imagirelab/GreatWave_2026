"""17の採用BGEOを読み、18専用の参照・Alembic・公式VATを作る。再シミュレーションしない。"""
import hashlib,json,os,struct,time
from pathlib import Path
assert os.getpid()==EXPECTED_PID and hou.isUIAvailable()
ROOT=Path(STAGE); SOURCE=ROOT.parent/'VariableTopology17'
s=getattr(hou.session,KEY)
assert hou.fps()==s['fps']==24
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,data):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if PHASE=='create':
 index=json.loads((SOURCE/'Evidence/17_cache_index.json').read_text(encoding='utf8'))['samples']
 assert len(index)==49
 for row in index:assert sha(SOURCE/row['mesh_file'])==row['mesh_sha256']
 container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
 s['owned_nodes'].append((container,container.sessionId()));s['container']=container
 geo=container.createNode('geo','source17',run_init_scripts=False)
 file=geo.createNode('file','read_exact_step17',run_init_scripts=False)
 file.parm('file').set(str(SOURCE/'Cache/surface_`padzero(3,$F-1)`.bgeo.sc').replace('\\','/'))
 triangles=geo.createNode('python','triangulate_fan_preserve_P_N',run_init_scripts=False);triangles.setInput(0,file)
 triangles.parm('python').set('''import hou
g=hou.pwd().geometry(); original=hou.pwd().inputs()[0].geometry();g.clear()
n=g.addAttrib(hou.attribType.Point,'N',(0.,1.,0.));path=g.addAttrib(hou.attribType.Prim,'path','/fluid17');pts=[]
for old in original.points():
 p=g.createPoint();p.setPosition(old.position());p.setAttribValue(n,old.attribValue('N'));pts.append(p)
for prim in original.prims():
 ids=[p.number() for p in prim.points()]
 for i in range(1,len(ids)-1):
  face=g.createPolygon()
  for j in (ids[0],ids[i],ids[i+1]):face.addVertex(pts[j])
  face.setAttribValue(path,'/fluid17')
''')
 out=geo.createNode('null','OUT',run_init_scripts=False);out.setInput(0,triangles);out.setDisplayFlag(True);out.setRenderFlag(True);s['out']=out
 ropnet=container.createNode('ropnet','exports',run_init_scripts=False)
 abc=ropnet.createNode('alembic','exact_alembic',run_init_scripts=False)
 abc.setParms({'filename':str(ROOT/'Exports/fluid17.abc').replace('\\','/'),'use_sop_path':1,'sop_path':'../../source17/OUT','build_from_path':1,'path_attrib':'path','initsim':0,'trange':1,'motionBlur':0,'render_full_range':1,'tprerender':0,'tpreframe':0,'tpostframe':0,'tpostrender':0})
 abc.parmTuple('f').set((1,49,1));s['abc']=abc
 assert abc.node(abc.parm('sop_path').eval())==out and not abc.inputs()
 s['source_rows']=index;s['reference_rows']=[];s['installed_hdas']=[]
 (ROOT/'Exports').mkdir(exist_ok=True)
 if BUILD_REFERENCE:
  with (ROOT/'Exports/reference.bytes').open('wb') as f:f.write(struct.pack('<8siii',b'GW18REF1',1,49,24))
 result={'created':True,'clip_id':'GreatWave17_FLIP_02','source_sha_verified_count':49,'fps':24,'triangulation':'元ポリゴンの頂点0からfan分割。点位置・点法線を保持し、共通入力として両形式へ渡す。'}
elif PHASE.startswith('reference:'):
 first,last=map(int,PHASE.split(':')[1:]);records=[]
 with (ROOT/'Exports/reference.bytes').open('ab') as f:
  for k in range(first,last+1):
   g=s['out'].geometryAtFrame(k+1);p=g.pointFloatAttribValues('P');n=g.pointFloatAttribValues('N');ids=[v.point().number() for face in g.prims() for v in face.vertices()]
   assert len(p)==len(n) and len(ids)%3==0
   f.write(struct.pack('<ifii',k,k/24,len(p)//3,len(ids)));f.write(struct.pack('<%df'%len(p),*p));f.write(struct.pack('<%df'%len(n),*n));f.write(struct.pack('<%di'%len(ids),*ids))
   b=g.boundingBox();row={'sample':k,'time_seconds':k/24,'source_frame':k+1,'points':len(p)//3,'triangles':len(ids)//3,'bounds_min':list(b.minvec()),'bounds_max':list(b.maxvec()),'source_bgeo_sha256':s['source_rows'][k]['mesh_sha256'],'triangulated_topology_sha256':hashlib.sha256(struct.pack('<%di'%len(ids),*ids)).hexdigest()};records.append(row);s['reference_rows'].append(row)
 write('Evidence/18_reference.json',{'clip_id':'GreatWave17_FLIP_02','binary':'Exports/reference.bytes','fps':24,'coordinate_system':'Houdini Y-up m; Unityへ(-x,y,z)','samples':s['reference_rows']})
 result={'samples':len(records),'first':first,'last':last}
elif PHASE=='alembic':
 a=s['abc'];start=time.monotonic();a.render(frame_range=(1,49,1),ignore_inputs=True);elapsed=time.monotonic()-start
 import _alembic_hom_extensions as abcapi
 path=ROOT/'Exports/fluid17.abc'
 result={'seconds':elapsed,'bytes':path.stat().st_size,'sha256':sha(path),'archive_time_range':abcapi.alembicTimeRange(str(path)),'hierarchy':abcapi.alembicGetSceneHierarchy(str(path),'/'),'input_sop':a.parm('sop_path').eval(),'initsim':a.parm('initsim').eval(),'ignore_inputs':True,'fps':hou.fps(),'source_sha256':sha(ROOT/'Exports/reference.bytes')}
 write('Evidence/18_alembic_export.json',result)
elif PHASE=='vat_schema':
 prior=set(hou.hda.loadedFiles());base=ROOT/'ThirdParty/SideFXLabs'
 for name in ('coord_swizzle_quaternion.hda','coord_swizzle_vector.hda','vertical_point_index.hda','vertex_animation_textures.3.1.hda'):
  path=str(base/name).replace('\\','/');assert path not in prior;hou.hda.installFile(path);s['installed_hdas'].append(path)
 vat=s['container'].node('exports').createNode('labs::vertex_animation_textures::3.1','official_fluid_vat',run_init_scripts=False);s['vat']=vat
 schema=[]
 for p in vat.parms():
  t=p.parmTemplate();row={'name':p.name(),'label':t.label(),'type':str(t.type()),'value':p.eval()}
  if hasattr(t,'menuItems'):row.update(items=list(t.menuItems()),labels=list(t.menuLabels()))
  schema.append(row)
 write('Evidence/18_vat_schema.json',schema)
 result={'registered_type':vat.type().name(),'definition':vat.type().definition().libraryFilePath(),'initial_errors':list(vat.errors()),'initial_warnings':list(vat.warnings()),'parameters':len(schema)}
elif PHASE=='vat_setup':
 vat=s['vat'];vat.setParms({'mode':2,'engine':'unity','f1':1,'f2':49,'soppath':'../../source17/OUT','scale':1,'coordsys':2,'coord_pos':0,'coord_flip':1,'coord_rot':8,'debugplane':0,'shaderengine':'unity',
  'fluidpass':0,'packnorm_fluid':0,'fluiduvinalphas':0,'fluiduvinrg':0,'enablefuse':0,'fixoverlaps':0,'deleteoverlappairs':0,'lookupdataformat':0,'imageformat_lookup':0,'normalizedata':0,'imageformat':0,'depth':4,
  'targettexsize':'1024','targettexsize_lookup':'2048','exportpath':str(ROOT/'Exports/VAT_Final').replace('\\','/'),'assetname':'fluid17','include':'custom','enable_geo':1,'enable_pos':1,'enable_rot':1,'enable_col':0,'enable_col2':0,'enable_lookup':1,'enable_unitymat':1,'enable_datafile':1,'enable_velocity':0,'enablecooking':0,'croptextofirstframe':0,'initsim':0,'tpostrender':0,'autonormalmode':0})
 # 範囲の既定式を明示解除し、HDA内部の範囲同期にも同じ値を渡す。
 for name,value in (('f1',1),('f2',49),('f_s1',1),('f_s2',49),('f_s3',0)):
  parm=vat.parm(name);parm.deleteAllKeyframes();parm.set(value)
 assert vat.evalParm('f1')==1 and vat.evalParm('f2')==49
 vat.parm('enablecooking').set(1)
 assert vat.node(vat.parm('soppath').eval())==s['out']
 # 登録済みHDAの内部だけを読み、初期化スイッチが既存DOPへ向かないことを確認する。
 internal=[{'path':n.path(),'value':n.parm('initsim').eval()} for n in vat.allSubChildren() if n.parm('initsim') is not None]
 settings={p.name():p.eval() for p in vat.parms() if p.name() not in ('mat_unity_fluid','mat_unity_soft','mat_unity_rigid','mat_unity_sprite')}
 write('Evidence/18_vat_settings.json',settings)
 result={'settings':{k:settings[k] for k in ('mode','engine','f1','f2','scale','coord_pos','coord_flip','coord_rot','lookupdataformat','normalizedata','depth','targettexsize','targettexsize_lookup','packnorm_fluid')},'internal_initsim':internal,'errors':list(vat.errors())}
elif PHASE in ('vat_first','vat_second'):
 vat=s['vat'];second=PHASE=='vat_second';vat.setParms({'fluidpass':int(second),'enable_lookup':int(not second)})
 assert vat.evalParm('f1')==1 and vat.evalParm('f2')==49
 start=time.monotonic();vat.render(ignore_inputs=True);elapsed=time.monotonic()-start
 files=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in (ROOT/'Exports/VAT_Final').rglob('*') if p.is_file()]
 result={'owned_token':NAME,'pass':2 if second else 1,'seconds':elapsed,'files':files,'errors':list(vat.errors()),'warnings':list(vat.warnings()),'final_texture_size':[vat.evalParm('finaltexsizex'),vat.evalParm('finaltexsizey')]}
 result['passed']=not result['errors'] and bool(files) and not any('Error:' in w or 'Unable to read' in w for w in result['warnings']) and (not second or result['final_texture_size'][1]>49)
 write('Evidence/18_'+PHASE+'.json',result)
 assert result['passed'],result
 if second:assert result['final_texture_size'][0]>=1024 and result['final_texture_size'][1]>49
elif PHASE=='save_source':
 path=ROOT/'Source/playback18_owned.cpio';hou.node('/obj').saveItemsToFile((s['container'],),str(path),save_hda_fallbacks=False)
 result={'own_cpio':str(path),'sha256':sha(path),'hip_saved':False}
else:raise ValueError(PHASE)
