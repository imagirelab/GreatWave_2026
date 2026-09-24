"""MCP 経由で新規の所有ノードだけを作成し、必ず UI を復元する。"""
from __future__ import annotations
import asyncio, hashlib, json, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ui_guard
ROOT=Path(__file__).resolve().parents[1]
TOKEN=uuid.uuid4().hex[:12]
NAME='gw16_owned_'+TOKEN
KEY='_gw16_owned_'+TOKEN
OBJ_PATH='/obj/'+NAME
REPORT=ROOT/('Evidence/run_'+TOKEN+'.json')
PATTERN=str(ROOT/('Evidence/Frames/'+TOKEN+'_$FF.png')).replace('\\','/')
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def constants(phase=''):
 return '\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'CAPTURE_PATTERN':PATTERN,'EXPECTED_PID':53912,'STAGE':str(ROOT),'PHASE':phase}.items())+'\n'
async def main():
 (ROOT/'Evidence/Frames').mkdir(exist_ok=True)
 report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'expected_pid':53912,'mcp_port':8100,'token':TOKEN,'owned_container':OBJ_PATH,'snapshot_key':KEY,'events':[],'classification':'KINEMATIC_ANALYTIC_NOT_FLUID','source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'Source/generate_fixed_topology.py',ROOT/'Source/ui_guard.py')}}
 def save(): REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'WARNING'})
 with (ROOT/('Evidence/run_'+TOKEN+'_proxy.log')).open('w',encoding='utf-8') as log:
  async with stdio_client(params,errlog=log) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=115)) as session:
    init=await asyncio.wait_for(session.initialize(),30); report['protocol_version']=init.protocolVersion
    async def execute(label,source,phase='',timeout=100):
     start=time.monotonic()
     response=await asyncio.wait_for(session.call_tool('execute_python',{'code':constants(phase)+'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable()\n'+source,'return_expression':'result','justification':'Authorized step16: operate only newly generated, uniquely owned nodes; preserve existing scene content and global FPS, restore UI in finally. '+label}),timeout)
     content=[c.text for c in response.content if c.type=='text']; assert len(content)==1
     payload=json.loads(content[0]); report['events'].append({'phase':label,'elapsed_seconds':round(time.monotonic()-start,3),'is_error':response.isError,'result':payload}); save()
     assert not response.isError and payload.get('executed') and not payload.get('eval_error') and not payload.get('error'),payload
     return payload['return_value']
    snap=False
    try:
     report['snapshot']=await execute('snapshot minimal UI',ui_guard.SNAPSHOT); snap=True
     generator=(ROOT/'Source/generate_fixed_topology.py').read_text(encoding='utf-8-sig')
     for phase in ('create','sample','export','source_roundtrip'):
      report[phase]=await execute(phase,generator,phase); print(json.dumps({'phase':phase,'result':report[phase]},ensure_ascii=False),flush=True)
     if '--no-capture' not in sys.argv:
      show=ui_guard.SHOW_OWNED.replace("s['viewport'].frameSelected()","s['viewport'].changeType(hou.geometryViewportType.Perspective)\ns['viewport'].defaultCamera().setRotation(hou.hmath.buildRotate((28.0,-35.0,0.0)).extractRotationMatrix3())\ns['viewport'].frameSelected()")
      report['show']=await execute('show only owned specimen',show)
      await asyncio.sleep(1)
      report['capture']=await execute('capture exact 60 frame preview',ui_guard.CAPTURE,timeout=110)
      files=sorted((ROOT/'Evidence/Frames').glob(TOKEN+'_*.png'))
      report['raw_preview_files']=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
      assert len(files)==60, f'Expected60 actual previews, got{len(files)}'
    except Exception as e:
     report['failure']={'type':type(e).__name__,'message':str(e)}; print(json.dumps(report['failure'],ensure_ascii=False),flush=True)
    finally:
     if snap:
      try: report['cleanup']=await execute('restore UI and delete only owned nodes',ui_guard.CLEANUP,timeout=60)
      except Exception as e: report['cleanup_failure']={'type':type(e).__name__,'message':str(e)}
     report['success']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False)
     save()
     (ROOT/'Evidence/latest_run.json').write_text(json.dumps({'report':str(REPORT),'success':report['success'],'token':TOKEN},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'report':str(REPORT),'success':report['success'],'cleanup':report.get('cleanup')},ensure_ascii=False),flush=True)
if __name__=='__main__': asyncio.run(main())
