"""19で新規計算した保存面のみを30/60Hz Alembicへ出す。再計算・補間・既存HIPの読込はしない。"""
import hashlib,json,os,time
from pathlib import Path
assert os.getpid()==EXPECTED_PID and hou.isUIAvailable()
ROOT=Path(STAGE);s=getattr(hou.session,KEY)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
if PHASE=='create':
 index=json.loads((ROOT/'Evidence/19_cache_index.json').read_text(encoding='utf8'))['samples'];assert len(index)==121 and hou.fps()==24
 for row in index:assert sha(ROOT/row['surface_file'])==row['surface_sha256']
 container=hou.node('/obj').createNode('subnet',NAME,run_init_scripts=False);s['owned_nodes'].append((container,container.sessionId()));s['container']=container
 geo=container.createNode('geo','cached19',run_init_scripts=False);reader=geo.createNode('file','read60_actual_cache',run_init_scripts=False)
 reader.parm('file').set(str(ROOT/'Cache/surface_`padzero(3,round(($FF-1)*60/24))`.bgeo.sc').replace('\\','/'))
 fan=geo.createNode('python','same_fan_P_N',run_init_scripts=False);fan.setInput(0,reader)
 fan.parm('python').set("""import hou
g=hou.pwd().geometry();old=hou.pwd().inputs()[0].geometry();g.clear()
n=g.addAttrib(hou.attribType.Point,'N',(0.,1.,0.));path=g.addAttrib(hou.attribType.Prim,'path','/fluid19');points=[]
for q in old.points():
 p=g.createPoint();p.setPosition(q.position());p.setAttribValue(n,q.attribValue('N'));points.append(p)
for face in old.prims():
 ids=[p.number() for p in face.points()]
 for j in range(1,len(ids)-1):
  f=g.createPolygon()
  for k in (ids[0],ids[j],ids[j+1]):f.addVertex(points[k])
  f.setAttribValue(path,'/fluid19')
""")
 out=geo.createNode('null','OUT',run_init_scripts=False);out.setInput(0,fan);s['out']=out
 ropnet=container.createNode('ropnet','exports',run_init_scripts=False);rop=ropnet.createNode('alembic','actual_sampling',run_init_scripts=False)
 rop.setParms({'use_sop_path':1,'sop_path':'../../cached19/OUT','build_from_path':1,'path_attrib':'path','initsim':0,'trange':1,'motionBlur':0,'render_full_range':1,'tprerender':0,'tpreframe':0,'tpostframe':0,'tpostrender':0});s['rop']=rop;s['exports']=[]
 result={'source_count':121,'source_sha_matches':True,'global_fps':hou.fps(),'source_clip':'GreatWave19_FLIP60_01'}
elif PHASE.startswith('export:'):
 rate,first,last=map(int,PHASE.split(':')[1:]);assert rate in (30,60)
 path=ROOT/('Exports/fluid19_%d_%03d_%03d.abc'%(rate,first,last));rop=s['rop'];rop.parm('filename').set(str(path).replace('\\','/'))
 frame0=1+first*24/60;frame1=1+last*24/60;increment=24/rate
 rop.parmTuple('f').set((frame0,frame1,increment));start=time.monotonic();rop.render(frame_range=(frame0,frame1,increment),ignore_inputs=True)
 import _alembic_hom_extensions as abc
 row={'rate':rate,'first_master_sample':first,'last_master_sample':last,'count':(last-first)//(60//rate)+1,'relative_start':first/60,'relative_end':last/60,'houdini_global_fps':hou.fps(),'rop_frame_range':[frame0,frame1,increment],'archive_time_range':abc.alembicTimeRange(str(path)),'bytes':path.stat().st_size,'sha256':sha(path),'path':str(path.relative_to(ROOT)).replace('\\','/'),'export_seconds':time.monotonic()-start,'errors':list(rop.errors()),'warnings':list(rop.warnings())}
 assert not row['errors'] and row['bytes']>1000
 s['exports'].append(row);(ROOT/'Evidence/19_alembic_exports.json').write_text(json.dumps({'clip_id':'GreatWave19_FLIP60_01','exports':s['exports']},ensure_ascii=False,indent=2)+'\n',encoding='utf8');result=row
else:raise ValueError(PHASE)
