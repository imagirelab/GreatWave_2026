"""既存L6 cacheの読戻し候補。既定は計画表示のみ、明示許可フラグでだけMCPを使う。"""
import argparse
import asyncio
import hashlib
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

CANDIDATE = Path(__file__).resolve().parents[1]
WAVE = Path(__file__).resolve().parents[3]
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf8'))


def build_probe_code(core, adapter, pid, cache, expected_sha, sample, count, destination):
    """各RPCへ全定義とimportを渡す。直前RPCのnamespaceに依存しない。"""
    combined = core+'\n'+adapter
    code_sha = hashlib.sha256(combined.encode('utf8')).hexdigest()
    header = f'''import os
assert os.getpid()=={pid!r} and hou.isUIAvailable()
before={{'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges(),'update_mode':str(hou.updateModeSetting())}}
'''
    tail = f'''
record=read_cached_probe(hou,{str(cache)!r},{expected_sha!r},{sample!r},{count!r})
after={{'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges(),'update_mode':str(hou.updateModeSetting())}}
record['ui_metadata_before_after']=[before,after]
record['ui_metadata_unchanged']=before==after
record['combined_reader_sha256']={code_sha!r}
assert before==after
destination=Path({str(destination)!r})
assert not destination.exists()
destination.write_bytes((json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8'))
result={{'json_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'source_sha256':{code_sha!r}}}
'''
    return header+combined+tail, code_sha


async def execute_readback(sample_numbers):
    # 接続ライブラリのimportも明示実行時のみ。単独の計画表示と単体試験はHOMを呼ばない。
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    plan_path = CANDIDATE/'Source/reseeding03_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf8'))
    assert all(k in plan['checkpoint_samples'] for k in sample_numbers)
    assert sample_numbers == sorted(set(sample_numbers))
    reference = WAVE/'Evidence/Curated_Runs/db52394211/22_pilot_samples.json'
    assert sha(reference) == '9f88f7e893cd6a2c30973f0e2b8a22065ead99682be25384d5d16ae363bde7c4'
    rows = json.loads(reference.read_text(encoding='utf8'))['samples']
    output = WAVE/'Runs'/('deepwater03_'+uuid.uuid4().hex[:10])
    output.mkdir(exist_ok=False)
    report = {'baseline_case':'db52394211','source_samples_sha256':sha(reference),
              'requested_samples':sample_numbers,'simulation_executed':False,
              'plan_sha256':sha(plan_path),'source_hashes':{p.name:sha(p) for p in (CANDIDATE/'Source').glob('*.py')},
              'events':[],'transport_completion_uncertain':False}
    core = (CANDIDATE/'Source/deepwater_core.py').read_text(encoding='utf8')
    adapter = (CANDIDATE/'Source/readback_deepwater.py').read_text(encoding='utf8')
    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],
        env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
    try:
        with (output/'proxy.log').open('w',encoding='utf8') as error:
            async with stdio_client(params,errlog=error) as (reader,writer):
                async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=180)) as client:
                    await client.initialize()

                    async def call(code):
                        try:
                            response=await client.call_tool('execute_python',{'code':code,'return_expression':'result',
                                'justification':'許可された新L6の既存BGEOだけを読む。ノード・HIP・UI時刻・solverを変更しない。'})
                        except Exception:
                            report['transport_completion_uncertain']=True
                            raise
                        data=json.loads(next(x.text for x in response.content if x.type=='text'))
                        if response.isError or not data.get('executed') or data.get('error') or data.get('eval_error'):
                            # tracebackはローカル報告だけに保持し、公開要約へ無加工で転記しない。
                            report['local_rpc_error']=data
                            raise RuntimeError('読戻しRPCが完了エラーを返した')
                        return data['return_value']

                    report['metadata']=await call("import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'ui':hou.isUIAvailable(),'license':str(hou.licenseCategory()),'fps':hou.fps()}\n")
                    m=report['metadata']
                    assert m['ui'] and m['version']=='22.0.429' and m['license']=='licenseCategoryType.Indie' and m['fps']==24
                    for k in sample_numbers:
                        row=rows[k]
                        assert row['sample']==k and row['requested_seconds']==k/60
                        cache=WAVE/'Runs/db52394211/Cache'/('pilot_%03d.bgeo.sc'%k)
                        assert sha(cache)==row['cache_sha256']
                        destination=output/('deepwater_%03d.json'%k)
                        code,code_sha=build_probe_code(core,adapter,m['pid'],cache,row['cache_sha256'],k,row['particle_count'],destination)
                        start=time.monotonic()
                        ack=await call(code)
                        assert ack['source_sha256']==code_sha and sha(destination)==ack['json_sha256']
                        exact=json.loads(destination.read_text(encoding='utf8'))
                        report['events'].append({'sample':k,'rpc_seconds':time.monotonic()-start,
                            'result_filename':destination.name,'result_sha256':sha(destination),
                            'valid':exact['deepwater']['observations_valid'],
                            'coverage_alarm_count':len(exact['deepwater']['coverage_alarm_point_indices'])})
                        write(output/'execution.json',report)
                        if not exact['deepwater']['observations_valid']:
                            report['stop_reason_ja']='場外または非有限。無効観測で停止。'
                            break
                    report['all_requested_readbacks_completed']=len(report['events'])==len(sample_numbers)
    except Exception as error:
        report['failure_type']=type(error).__name__
        report['completed_without_execution_error']=False
        raise
    else:
        report['completed_without_execution_error']=True
    finally:
        # Geometryのみでノードはない。完了不明RPCへ再要求・復元要求・killを送らない。
        write(output/'execution.json',report)
        print(json.dumps({'output':str(output),'samples_completed':len(report['events']),
                          'transport_completion_uncertain':report['transport_completion_uncertain']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='基線の粗い深水被覆を読む候補。既定は計画表示だけ。')
    parser.add_argument('--execute-reviewed-readback',action='store_true')
    parser.add_argument('--samples',nargs='+',type=int,default=[0])
    args=parser.parse_args()
    if args.execute_reviewed_readback:
        asyncio.run(execute_readback(args.samples))
    else:
        print(json.dumps({'state_ja':'未実行。まず単一cache費用を承認後に計測する。',
                          'samples':args.samples,'houdini_called':False},ensure_ascii=False))
