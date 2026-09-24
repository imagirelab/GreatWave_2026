"""18の新規所有物だけを実MCPで操作し、UIと一時HDA登録をfinallyで戻す。"""
import asyncio,hashlib,json,sys,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
import ui_guard
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1];TOKEN=uuid.uuid4().hex[:10];NAME='gw18_owned_'+TOKEN;KEY='_gw18_'+TOKEN
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
async def main():
 meta=json.loads((ROOT/'Evidence/18_connection.json').read_text(encoding='utf8'))['metadata']
 report={'utc':datetime.now(timezone.utc).isoformat(),'token':TOKEN,'expected_pid':meta['pid'],'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'Source/export_playback.py',ROOT/'Source/ui_guard.py')},'events':[]}
 path=ROOT/('Evidence/run_'+TOKEN+'.json')
 def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 def constants(phase):return '\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':'/obj/'+NAME,'EXPECTED_PID':meta['pid'],'STAGE':str(ROOT),'PHASE':phase,'BUILD_REFERENCE':not any(x.startswith('--vat-') for x in sys.argv)}.items())+'\n'
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR','HOUDINI_TIMEOUT':'600'})
 with (ROOT/('Evidence/run_'+TOKEN+'.log')).open('w',encoding='utf8') as log:
  async with stdio_client(params,errlog=log) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=600)) as c:
    await c.initialize()
    async def execute(label,code,phase=''):
     x=await c.call_tool('execute_python',{'code':constants(phase)+'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable()\n'+code,'return_expression':'result','justification':'手順18の新規所有コンテナーだけで実17キャッシュを出力する。既存HIP/ライセンス/FPSを変更せず最後に所有物とUIを復元。 '+label})
     raw=next(t.text for t in x.content if t.type=='text')
     try:value=json.loads(raw)
     except json.JSONDecodeError:
      report['events'].append({'phase':label,'transport_error':raw});save()
      if phase not in ('vat_first','vat_second'):raise
      # 旧ブリッジの120秒期限後も実計算は続く。読み取りを直列に待たせ、同tokenの完了だけを認める。
      recovery=constants(phase)+"import json\nfrom pathlib import Path\np=Path(STAGE)/('Evidence/18_'+PHASE+'.json')\nresult=json.loads(p.read_text(encoding='utf8'))\nassert result['owned_token']==NAME and result['passed']"
      read=await c.call_tool('execute_python',{'code':recovery,'return_expression':'result','justification':'応答期限を超えた所有VAT計算の完了を、同tokenのJSONから確認する。重複書出しや既存シーン変更はしない。'})
      value=json.loads(next(t.text for t in read.content if t.type=='text'));x=read
      report['events'].append({'phase':label+'_completion_read_after_transport_timeout','result':value});save()
     report['events'].append({'phase':label,'result':value});save()
     assert not x.isError and value.get('executed') and not value.get('error') and not value.get('eval_error'),value
     return value['return_value']
    snap=False
    try:
     report['snapshot']=await execute('snapshot',ui_guard.SNAPSHOT);snap=True
     code=(ROOT/'Source/export_playback.py').read_text(encoding='utf8')
     phases=['create']+([] if any(x.startswith('--vat-') for x in sys.argv) else [f'reference:{i}:{min(i+6,48)}' for i in range(0,49,7)]+['alembic'])+['vat_schema','vat_setup']+([] if '--vat-second-only' in sys.argv else ['vat_first'])+['vat_second','save_source']
     for phase in phases:
      result=await execute(phase,code,phase);report[phase]=result;print(json.dumps({'phase':phase,'result':result},ensure_ascii=False),flush=True)
    except Exception as exc:report['failure']={'type':type(exc).__name__,'message':str(exc)};print(str(exc),flush=True)
    finally:
     if snap:
      try:
       report['installed']=await execute('record temporary registrations',"s=getattr(hou.session,KEY)\nresult=list(s.get('installed_hdas',[]))")
       report['cleanup']=await execute('restore UI',ui_guard.CLEANUP)
       report['unregister']=await execute('unregister only own HDA files','paths='+repr(report['installed'])+'\nfor p in reversed(paths): hou.hda.uninstallFile(p)\nresult={"all_temporary_hdas_unregistered":all(p not in hou.hda.loadedFiles() for p in paths)}')
      except Exception as exc:report['cleanup_failure']=str(exc)
     report['success']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False) and report.get('unregister',{}).get('all_temporary_hdas_unregistered',False);save()
 print(json.dumps({'report':str(path),'success':report['success']},ensure_ascii=False),flush=True)
if __name__=='__main__':asyncio.run(main())
