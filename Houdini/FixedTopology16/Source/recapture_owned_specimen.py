"""所有 CPIO だけを読み直して、境界に合わせた実ビューポート証拠を撮影する。"""
from __future__ import annotations
import asyncio,hashlib,json,sys,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
import ui_guard
ROOT=Path(__file__).resolve().parents[1]
FULL='--full' in sys.argv
TOKEN=uuid.uuid4().hex[:12]; NAME='gw16_preview_'+TOKEN; KEY='_gw16_preview_'+TOKEN; OBJ_PATH='/obj/'+NAME
IMAGE=ROOT/('Evidence/preview_'+TOKEN+'.png'); PATTERN=str(ROOT/('Evidence/Frames/'+TOKEN+'_$FF.png')).replace('\\','/')
REPORT=ROOT/('Evidence/preview_'+TOKEN+'.json')
LOAD=r'''
s=getattr(hou.session,KEY)
assert hou.node(OBJ_PATH) is None
container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
s['owned_nodes'].append((container,container.sessionId()))
container.loadItemsFromFile(CPIO,ignore_load_warnings=False)
children=container.children(); assert len(children)==1
out=children[0].node('surface/OUT'); assert out is not None
assert children[0].node('exports/exact_owned_surface').node('../../surface/OUT')==out
s['out']=out
geo=out.geometryAtFrame(1.0); assert len(geo.points())==1129
bbox=geo.boundingBox(); low=bbox.minvec(); high=bbox.maxvec(); center=(low+high)*0.5; half=(high-low)*0.65
s['own_bbox']=hou.BoundingBox(*(tuple(center-half)+tuple(center+half)))
result={'owned_cpio_loaded':True,'point_count':len(geo.points()),'framing_min':list(center-half),'framing_max':list(center+half)}
'''
async def main():
 report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'full60':FULL,'token':TOKEN,'snapshot_key':KEY,'owned_container':OBJ_PATH,'events':[],'cpio_sha256':hashlib.sha256((ROOT/'Source/fixed_topology_16.cpio').read_bytes()).hexdigest(),'cache_hashes_before':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'Cache/fixed_topology_16.abc',ROOT/'Cache/reference_samples.json')}}
 def save(): REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 constants='\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'CPIO':str(ROOT/'Source/fixed_topology_16.cpio'),'CAPTURE_PATTERN':PATTERN,'IMAGE':str(IMAGE).replace('\\','/')}.items())+'\nimport os\nassert os.getpid()==53912 and hou.isUIAvailable()\n'
 params=StdioServerParameters(command=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe',args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'WARNING'})
 with (ROOT/('Evidence/preview_'+TOKEN+'_proxy.log')).open('w') as log:
  async with stdio_client(params,errlog=log) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=115)) as session:
    await session.initialize()
    async def call(label,code):
     response=await asyncio.wait_for(session.call_tool('execute_python',{'code':constants+code,'return_expression':'result','justification':'Camera-only correction of authorized new specimen preview. Load only generated owned CPIO, preserve existing scene/FPS and restore UI in finally. '+label}),110)
     data=json.loads(next(c.text for c in response.content if c.type=='text'));report['events'].append({'phase':label,'result':data});save()
     assert not response.isError and data.get('executed') and not data.get('error') and not data.get('eval_error'),data
     return data['return_value']
    snap=False
    try:
     report['snapshot']=await call('snapshot',ui_guard.SNAPSHOT); snap=True
     report['load']=await call('load only owned CPIO',LOAD)
     show=ui_guard.SHOW_OWNED.replace("s['viewport'].frameSelected()","s['viewport'].changeType(hou.geometryViewportType.Perspective)\ns['viewport'].defaultCamera().setRotation(hou.hmath.buildRotate((28.0,-35.0,0.0)).extractRotationMatrix3())\ns['viewport'].frameBoundingBox(s['own_bbox'])\nhou.clearAllSelected()")
     report['show']=await call('frame explicit owned geometry bounds',show)
     await asyncio.sleep(2)
     capture=ui_guard.CAPTURE
     if not FULL:
      capture=capture.replace('settings.output(CAPTURE_PATTERN)','settings.output(IMAGE)').replace('settings.frameRange((start, end))','settings.frameRange((1.0, 1.0))').replace("'expected_frame_count': 60","'expected_frame_count': 1").replace("'output_pattern': CAPTURE_PATTERN","'output_pattern': IMAGE").replace("'clip_duration_seconds': 2.0","'clip_duration_seconds': None")
     report['capture']=await call('capture actual preview',capture)
     files=list((ROOT/'Evidence/Frames').glob(TOKEN+'_*.png')) if FULL else list((ROOT/'Evidence').glob('preview_'+TOKEN+'*.png'))
     report['images']=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files]
     assert len(files)==(60 if FULL else 1),len(files)
    except Exception as e: report['failure']={'type':type(e).__name__,'message':str(e)}
    finally:
     if snap:
      try: report['cleanup']=await call('restore and delete only owned preview nodes',ui_guard.CLEANUP)
      except Exception as e: report['cleanup_failure']=str(e)
     report['cache_hashes_after']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'Cache/fixed_topology_16.abc',ROOT/'Cache/reference_samples.json')}
     report['cache_unchanged']=report['cache_hashes_before']==report['cache_hashes_after']
     report['success']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False) and report['cache_unchanged']; save()
 print(json.dumps({'report':str(REPORT),'success':report['success'],'images':report.get('images',[])[:1],'failure':report.get('failure'),'cleanup':report.get('cleanup')},ensure_ascii=False))
if __name__=='__main__': asyncio.run(main())
