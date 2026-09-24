"""新規FLIPを段階実行し、成功・失敗にかかわらず所有ノードとUIを復元する。"""
import asyncio, hashlib, json, sys, time, uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ui_guard
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
TOKEN=uuid.uuid4().hex[:10];NAME='gw22_owned_'+TOKEN;KEY='_gw22_'+TOKEN;OBJ_PATH='/obj/'+NAME
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
def argument(name,default):return float(sys.argv[sys.argv.index(name)+1]) if name in sys.argv else default
async def main():
 output=ROOT/'Runs'/TOKEN
 for folder in ('Cache','Evidence','Source'): (output/folder).mkdir(parents=True,exist_ok=True)
 for name in ('run_pilot.py','generate_wave.py','ui_guard.py'):(output/'Source'/name).write_bytes((ROOT/'Source'/name).read_bytes())
 metadata=json.loads((ROOT/'Evidence/22_connection.json').read_text(encoding='utf8'))['metadata']
 expected=metadata['pid']
 report={'arguments':sys.argv[1:],'utc':datetime.now(timezone.utc).isoformat(),'token':TOKEN,'expected_pid':expected,'owned_path':OBJ_PATH,'events':[],'output_directory':str(output),'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'Source/generate_wave.py',ROOT/'Source/ui_guard.py')}}
 reportpath=ROOT/('Evidence/run_'+TOKEN+'.json')
 def save(): reportpath.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 def constants(phase): return '\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'EXPECTED_PID':expected,'STAGE':str(output),'PHASE':phase,'PISTON_ENABLED':'--static' not in sys.argv,'PARTICLE_SEPARATION':argument('--particle-separation',.04),'GRID_SCALE':argument('--grid-scale',2.0),'PISTON_START_SECONDS':argument('--piston-start',0),'MESH_STRIDE':int(argument('--mesh-stride',1)),'THREE_GAUGES':'--three-gauges' in sys.argv,'CAPTURE_PATTERN':str(ROOT/'Evidence/Frames'/f'{TOKEN}_$F4.png').replace('\\','/')}.items())+'\n'
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
 with (ROOT/('Evidence/run_'+TOKEN+'_proxy.log')).open('w',encoding='utf8') as err:
  async with stdio_client(params,errlog=err) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as client:
    await client.initialize()
    async def execute(label,source,phase=''):
     wall_start=time.monotonic()
     response=await client.call_tool('execute_python',{'code':constants(phase)+'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable()\n'+source,'return_expression':'result','justification':'手順22：既存HIPを読まず、新規所有FLIPだけを計算・保存・表示する。既存FPSを変えず、finallyでUIを復元。 '+label})
     data=json.loads(next(x.text for x in response.content if x.type=='text'));report['events'].append({'phase':label,'rpc_wall_seconds':time.monotonic()-wall_start,'result':data});save()
     assert not response.isError and data.get('executed') and not data.get('error') and not data.get('eval_error'),data
     return data['return_value']
    snapshot=False
    try:
     report['snapshot']=await execute('UI snapshot',ui_guard.SNAPSHOT);snapshot=True
     source=(ROOT/'Source/generate_wave.py').read_text(encoding='utf8')
     report['create']=await execute('create fresh FLIP',source,'create');print(json.dumps({'created':report['create']},ensure_ascii=False),flush=True)
     report['collision_probe']=await execute('verify actual collision output',source,'collision_probe');print(json.dumps(report['collision_probe'],ensure_ascii=False),flush=True)
     count=0 if '--collision-only' in sys.argv else int(argument('--samples',91 if '--one-half-second' in sys.argv else (31 if '--half-second' in sys.argv else 9)))
     batch_size=int(argument('--batch-size',1));assert 1<=batch_size<=6
     for start in range(0,count,batch_size):
      indices=list(range(start,min(start+batch_size,count)))
      # 各標本の保存とガードは元スクリプト内で直ちに行う。通信だけをまとめる。
      batched=f'_wave_source={source!r}\n_wave_results=[]\nfor _wave_index in {indices!r}:\n PHASE="sample:"+str(_wave_index)\n exec(compile(_wave_source,"generate_wave.py","exec"),globals())\n _wave_results.append(result)\nresult=_wave_results\n'
      rows=await execute('actual wave pilot '+str(indices),batched)
      for row in rows:print(json.dumps({'sample':row['sample'],'particles':row['particle_count'],'gauges':row['gauges'],'cook_seconds':row['cook_seconds'],'memory':row['memory']},ensure_ascii=False),flush=True)
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
