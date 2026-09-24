"""新規FLIPを段階実行し、成功・失敗にかかわらず所有ノードとUIを復元する。"""
import asyncio, hashlib, json, sys, time, uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ui_guard
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
TOKEN=uuid.uuid4().hex[:10];NAME='gw19_owned_'+TOKEN;KEY='_gw19_'+TOKEN;OBJ_PATH='/obj/'+NAME
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
async def main():
 for folder in ('Cache','Evidence','Evidence/Frames'): (ROOT/folder).mkdir(parents=True,exist_ok=True)
 metadata=json.loads((ROOT/'Evidence/19_connection.json').read_text(encoding='utf8'))['metadata']
 expected=metadata['pid']
 report={'utc':datetime.now(timezone.utc).isoformat(),'token':TOKEN,'expected_pid':expected,'owned_path':OBJ_PATH,'events':[],'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'Source/export_sampling.py',ROOT/'Source/ui_guard.py')}}
 reportpath=ROOT/('Evidence/run_'+TOKEN+'.json')
 def save(): reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 def constants(phase): return '\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'EXPECTED_PID':expected,'STAGE':str(ROOT),'PHASE':phase,'CAPTURE_PATTERN':str(ROOT/'Evidence/Frames'/f'{TOKEN}_$F4.png').replace('\\','/')}.items())+'\n'
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
 with (ROOT/('Evidence/run_'+TOKEN+'_proxy.log')).open('w',encoding='utf8') as err:
  async with stdio_client(params,errlog=err) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as client:
    await client.initialize()
    async def execute(label,source,phase=''):
     response=await client.call_tool('execute_python',{'code':constants(phase)+'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable()\n'+source,'return_expression':'result','justification':'手順19：既存HIPを読まず、新規所有FLIPだけを計算・保存・表示する。既存FPSを変えず、finallyでUIを復元。 '+label})
     data=json.loads(next(x.text for x in response.content if x.type=='text'));report['events'].append({'phase':label,'result':data});save()
     assert not response.isError and data.get('executed') and not data.get('error') and not data.get('eval_error'),data
     return data['return_value']
    snapshot=False
    try:
     report['snapshot']=await execute('UI snapshot',ui_guard.SNAPSHOT);snapshot=True
     source=(ROOT/'Source/export_sampling.py').read_text(encoding='utf8')
     report['create']=await execute('create fresh FLIP',source,'create');print(json.dumps({'created':report['create']},ensure_ascii=False),flush=True)
     for phase in ('export:60:0:40','export:60:40:80','export:60:80:120','export:30:0:120'):
      result=await execute('export '+phase,source,phase);print(json.dumps(result,ensure_ascii=False),flush=True)
    except Exception as exc:
     report['failure']={'type':type(exc).__name__,'message':str(exc)};print(json.dumps(report['failure'],ensure_ascii=False),flush=True)
    finally:
     if snapshot:
      try: report['cleanup']=await execute('restore UI and remove owned nodes',ui_guard.CLEANUP)
      except Exception as exc: report['cleanup_failure']={'type':type(exc).__name__,'message':str(exc)}
     report['success']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False)
     save();(ROOT/'Evidence/latest_run.json').write_text(json.dumps({'path':reportpath.name,'success':report['success']},indent=2),encoding='utf8')
 print(json.dumps({'report':str(reportpath),'success':report['success'],'cleanup':report.get('cleanup')},ensure_ascii=False),flush=True)
if __name__=='__main__': asyncio.run(main())


