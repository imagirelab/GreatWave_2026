"""既定は計画表示だけ。放行後も既存BGEOを順次1組ずつ読む。"""
import argparse
import asyncio
import hashlib
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))


def validate_request(sample_numbers,plan,continuation,preflight=None,reader_sha=None,plan_sha=None):
    """首組と追加組の放行を分ける。追加は審査済み首組のSHA付き原記録が必要。"""
    first=plan['budgets']['first_real_pair_only']
    assert sample_numbers and sample_numbers==sorted(set(sample_numbers))and all(k in [r['sample']for r in plan['pairs']]for k in sample_numbers)
    if not continuation:
        assert sample_numbers==[first]and preflight is None,'既定の実読戻しはk468の1組だけ'
        return
    assert first not in sample_numbers and preflight is not None,'追加組には独立放行と首組原JSONが必要'
    expected=next(r for r in plan['pairs']if r['sample']==first)
    assert preflight['sample']==first and preflight['plan_sha256']==plan_sha
    assert preflight['combined_reader_sha256']==reader_sha
    assert preflight['mesh_sha256']==expected['mesh_sha256']and preflight['solver_sha256']==expected['solver_sha256']
    assert preflight['center_parity_passed']and preflight['strict_incidence_consistency_passed']and preflight['ui_metadata_unchanged'],'首組の不一致は追加実行を保留する'
    assert not preflight['solver_executed']and not preflight['nodes_created']


def build_code(core,adapter,pid,mesh,solver,expected,plan,destination):
    combined=core+'\n'+adapter;source_sha=hashlib.sha256(combined.encode('utf8')).hexdigest()
    plan_sha=hashlib.sha256((json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf8')).hexdigest()
    code=f'''import os
assert os.getpid()=={pid!r} and hou.isUIAvailable()
before={{'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges(),'update_mode':str(hou.updateModeSetting())}}
'''+combined+f'''
record=read_pair(hou,{str(mesh)!r},{str(solver)!r},{expected!r},{plan!r})
after={{'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges(),'update_mode':str(hou.updateModeSetting())}}
record['ui_metadata_before_after']=[before,after]
record['ui_metadata_unchanged']=before==after
record['combined_reader_sha256']={source_sha!r}
record['plan_sha256']={plan_sha!r}
assert before==after
destination=Path({str(destination)!r});assert not destination.exists()
payload=(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
assert len(payload)<={plan['budgets']['maximum_result_bytes_per_pair']!r}
destination.write_bytes(payload)
result={{'json_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':{source_sha!r}}}
'''
    return code,source_sha


async def execute(sample_numbers,continuation=False,preflight_path=None,preflight_sha=None):
    plan_path=CANDIDATE/'Source/profile05_plan.json';plan=json.loads(plan_path.read_bytes())
    verified=json.loads((CANDIDATE/'Evidence/22_profile05_offline_checks.json').read_bytes())
    assert verified['passed']and all(sha(CANDIDATE/'Source'/p)==h for p,h in verified['source_hashes'].items())
    core=(CANDIDATE/'Source/profile_core.py').read_text(encoding='utf8');adapter=(CANDIDATE/'Source/read_profile05.py').read_text(encoding='utf8')
    reader_sha=hashlib.sha256((core+'\n'+adapter).encode('utf8')).hexdigest();preflight=None
    if continuation:
        assert preflight_path and preflight_sha,'追加放行には首組原JSONと審査したSHAを明示する'
        assert sha(Path(preflight_path))==preflight_sha,'首組の審査対象bytesと不一致'
        preflight=json.loads(Path(preflight_path).read_bytes())
    else:assert preflight_path is None and preflight_sha is None
    validate_request(sample_numbers,plan,continuation,preflight,reader_sha,sha(plan_path))
    # 不正な追加要求はMCPのimport/接続より前に拒否する。
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    base=WAVE/'Candidates/WaveStart04/Evidence/Result_22e7801642'
    for path,h in plan['baseline_files'].items():assert sha(base/path)==h
    out=WAVE/'Runs'/('profiles05_'+uuid.uuid4().hex[:10]);out.mkdir(exist_ok=False);(out/'Source').mkdir()
    source_paths=list((CANDIDATE/'Source').glob('*'));source_paths=[p for p in source_paths if p.is_file()]
    for p in source_paths:(out/'Source'/p.name).write_bytes(p.read_bytes())
    report={'baseline_run':plan['baseline_run'],'requested_samples':sample_numbers,'source_hashes':{p.name:sha(p)for p in source_paths},
            'plan_sha256':sha(plan_path),'continuation_requested':continuation,'reviewed_preflight_sha256':preflight_sha,
            'events':[],'solver_executed':False,'nodes_created':False,'transport_completion_uncertain':False}
    core=(out/'Source/profile_core.py').read_text(encoding='utf8');adapter=(out/'Source/read_profile05.py').read_text(encoding='utf8')
    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
    try:
        with (out/'proxy.log').open('w',encoding='utf8')as error:
            async with stdio_client(params,errlog=error)as(reader,writer):
                async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=180))as client:
                    await client.initialize()
                    async def call(code):
                        try:r=await client.call_tool('execute_python',{'code':code,'return_expression':'result','justification':'放行された04既存BGEOの読み取り断面。ノード・UI・solverを変更しない。'})
                        except Exception:
                            report['transport_completion_uncertain']=True;raise
                        data=json.loads(next(x.text for x in r.content if x.type=='text'))
                        if r.isError or not data.get('executed')or data.get('error')or data.get('eval_error'):
                            report['local_rpc_error']=data;raise RuntimeError('読戻しRPC完了エラー')
                        return data['return_value']
                    m=await call("import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'license':str(hou.licenseCategory()),'ui':hou.isUIAvailable(),'fps':hou.fps()}")
                    report['metadata']=m;assert m['ui']and m['version']=='22.0.429'and m['license']=='licenseCategoryType.Indie'and m['fps']==24
                    total=0.
                    for k in sample_numbers:
                        assert total+plan['budgets']['per_pair_cooperative_seconds']<=plan['budgets']['maximum_cumulative_read_seconds'],'次組の予算余地がない'
                        expected=next(r for r in plan['pairs']if r['sample']==k);cache=WAVE/'Runs'/plan['baseline_run']/'Cache'
                        mesh=cache/f'mesh_{k:03d}.bgeo.sc';solver=cache/f'pilot_{k:03d}.bgeo.sc'
                        assert sha(mesh)==expected['mesh_sha256']and sha(solver)==expected['solver_sha256']
                        dest=out/f'profiles_{k:03d}.json';code,source_sha=build_code(core,adapter,m['pid'],mesh,solver,expected,plan,dest)
                        started=time.monotonic();ack=await call(code)
                        assert ack['source_sha256']==source_sha and sha(dest)==ack['json_sha256']
                        exact=json.loads(dest.read_bytes());total+=exact['read_seconds']
                        report['events'].append({'sample':k,'rpc_seconds':time.monotonic()-started,'read_seconds':exact['read_seconds'],
                                                 'result_file':dest.name,'result_sha256':sha(dest),'result_bytes':dest.stat().st_size,
                                                 'center_parity_passed':exact['center_parity_passed'],'strict_incidence_consistency_passed':exact['strict_incidence_consistency_passed']})
                        write(out/'execution.json',report)
                        if not exact['center_parity_passed']or not exact['strict_incidence_consistency_passed']:
                            report['review_hold_reason_ja']='原交点JSONを保存した。中央配対または主query/面限定queryの不一致により次組を保留する。'
                            break
                        assert total<=plan['budgets']['maximum_cumulative_read_seconds'],'総読戻し時間上限'
                        print(json.dumps({'sample':k,'read_seconds':exact['read_seconds'],'profiles':len(exact['profiles'])}),flush=True)
                    report['all_requested_completed']=len(report['events'])==len(sample_numbers)
                    report['passed_for_continuation']=report['all_requested_completed']and'review_hold_reason_ja'not in report
    except Exception as error:
        report['failure_type']=type(error).__name__;raise
    finally:
        # Geometryのみ。完了不明RPCには復元・再試行・killを送らない。
        write(out/'execution.json',report);print(json.dumps({'output':str(out),'completed':len(report['events']),'uncertain':report['transport_completion_uncertain']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--samples',nargs='+',type=int,default=[468]);p.add_argument('--execute-reviewed-profile-readback',action='store_true')
    p.add_argument('--execute-reviewed-continuation',action='store_true',help='rootが首組を再審査して追加組を放行した場合のみ')
    p.add_argument('--reviewed-preflight-result',type=Path);p.add_argument('--reviewed-preflight-sha256');a=p.parse_args()
    if a.execute_reviewed_profile_readback:asyncio.run(execute(a.samples,a.execute_reviewed_continuation,a.reviewed_preflight_result,a.reviewed_preflight_sha256))
    else:print(json.dumps({'state_ja':'未実行。rootの明示放行後に最初1組だけ読む。','samples':a.samples,'houdini_called':False},ensure_ascii=False))
