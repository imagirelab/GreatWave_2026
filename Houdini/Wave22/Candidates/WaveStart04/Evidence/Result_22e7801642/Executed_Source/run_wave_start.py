"""新所有DOPの実活塞始動候補。既定は計画表示だけ、別途放行が必要。"""
import argparse
import asyncio
import hashlib
import gzip
import importlib.util
import json
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deepwater_core import compare_coverage, compare_initial_pair
from startup_response import analyze_response
from run_baseline_readback import build_probe_code

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=Path(__file__).resolve().parents[3]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'


class CoverageHold(Exception):
    """数値静水判定とは独立した被覆警報による非駆動終了。"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))


def exact_record(path,ack,source_sha):
    assert ack['source_sha256']==source_sha and sha(path)==ack['json_sha256']
    return json.loads(path.read_text(encoding='utf8'))


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_inputs():
    plan_path=CANDIDATE/'Source/wave_start_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf8'))
    assert plan['paired_baseline_case']=='4250d4451f'
    assert plan['static_sample_count']==361 and plan['final_sample']==555 and plan['stop_s']==9.25
    assert plan['sample_count']==556 and plan['piston_start_s']==6 and plan['drive_requires_static_pass']
    assert plan['only_physical_parameter_change'] is None
    result=WAVE/'Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f'
    assert sha(result/'22_original_manifest.json')==plan['baseline_original_manifest_sha256']
    originals={}
    for name,item in plan['baseline_originals'].items():
        path=result/name
        assert sha(path)==item['stored_sha256'] and path.stat().st_size==item['stored_bytes']
        raw=gzip.decompress(path.read_bytes()) if item['gzip'] else path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==item['source_sha256'] and len(raw)==item['source_bytes']
        originals[Path(name).name.removesuffix('.gz')]={'raw':raw,'sha256':item['source_sha256'],'record':json.loads(raw)}
    baseline={k:originals['off_deepwater_%03d.json'%k] for k in plan['checkpoint_samples']}
    assert all(v['record']['deepwater']['observations_valid'] and not v['record']['deepwater']['coverage_alarm_point_indices'] for v in baseline.values())
    executed=result/'Executed_Source'
    for name,expected in plan['baseline_executed_sources'].items():assert sha(executed/name)==expected
    for name,expected in plan['baseline_helper_sources'].items():assert sha(CANDIDATE/'Source'/name)==expected
    return plan,baseline,originals,executed


def verify_same_conditions(actual,baseline):
    """識別子・実資源だけを除外する。全作成条件はOFF基線と同一。"""
    assert set(actual)==set(baseline)
    assert actual['solver_parameters']['doreseeding']==baseline['solver_parameters']['doreseeding']==0
    for key in actual:
        if key not in ('case_id','memory'):assert actual[key]==baseline[key],key
    return True


def compare_initialization_schema(baseline,actual):
    """所有ルート名だけを除外し、記録済みの実パラメータ差を列挙する。"""
    def flatten(record):
        result={k:v for k,v in record.items() if k not in ('owned_path','nodes')}
        for node in record['nodes']:
            prefix='nodes/'+node['relative_path']
            result[prefix+'/type']=node['type']
            for parameter in node['parameters']:
                result[prefix+'/parameters/'+parameter['name']]=parameter
        return result
    a,b=flatten(baseline),flatten(actual)
    differences=[{'key':key,'baseline':a.get(key),'candidate':b.get(key)}
                 for key in sorted(set(a)|set(b)) if a.get(key)!=b.get(key)]
    return {'ignored_keys':['owned_path'],'differences':differences,
            'compared_record_count':len(set(a)|set(b)),
            'meaning_ja':'取得済みSOP・内部DOP設定の観測差。未収録パラメータの一致やOnly Source Seedingとの同義性は証明しない。'}


def initialization_code(source):
    # 既存generatorは変更せず、その所有ノード内だけの追加読取りを別ファイルへ保存する。
    return source+"""
schema_path=Path(STAGE)/'Evidence/22_initialization_schema.json'
schema=json.loads(schema_path.read_text(encoding='utf8'))
details=[]
for item in schema['nodes']:
 if item['type'].split('::')[0]!='flipsolver':continue
 node=hou.node(OBJ_PATH+'/'+item['relative_path'])
 assert node is not None and node.path().startswith(OBJ_PATH+'/')
 values=[]
 for parm in node.parms():
  label=parm.parmTemplate().label()
  if 'seed' not in (parm.name()+' '+label).lower():continue
  values.append({'name':parm.name(),'label':label,'value':parm.eval()})
 details.append({'relative_path':item['relative_path'],'type':item['type'],'parameters':values})
write('22_reseed_internal_detail.json',{'nodes':details,'existing_scene_read':False,
 'meaning_ja':'新所有ノードの補足観測。OFF基線の同じ実設定と比較する。設定は変更しない。'})
result={'json_sha256':hashlib.sha256(schema_path.read_bytes()).hexdigest(),
 'detail_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_reseed_internal_detail.json').read_bytes()).hexdigest(),
 'source_sha256':hashlib.sha256(SCHEMA_CODE.encode('utf8')).hexdigest()}
"""


def sample_code(source,policy,index):
    return (
        'import shutil\n'+policy+'\n'
        "s=getattr(hou.session,KEY)\n"
        "assert s['dop'].sessionId()==s['checkpoint_dop_id']\n"
        f"assert len(s['samples'])=={index} and 0<={index}<=555\n"
        f"assert {index}==0 or s['initial_pair_verified']\n"
        f"assert ({index}<=360 and not s['checkpoint_drive_authorized']) or ({index}>360 and s['checkpoint_drive_authorized'])\n"
        "assert s['solver'].evalParm('doreseeding')==0\n"
        "assert s['dop'].evalParm('cachemaxsize')==768\n"
        "assert all(s['dop'].evalParm(p)==0 for p in ('cachetodisk','cachetodisknoninteractive','explicitcache'))\n"
        "assert shutil.disk_usage(STAGE).free>=BUDGET['minimum_disk_free_bytes']\n"
        f"exec(compile({source!r},'generate_wave_l6.py','exec'),globals())\n"
        "assert s['dop'].sessionId()==s['checkpoint_dop_id']\n"
        "resource=check_resources(s['samples'],BUDGET,s['checkpoint_baseline_private'],shutil.disk_usage(STAGE).free,555)\n"
        "s['checkpoint_trace'].append({'sample':result['sample'],'dop_session_id':s['dop'].sessionId(),'drive_authorized':s['checkpoint_drive_authorized'],'resource':resource})\n"
        "write('22_checkpoint_trace.json',{'samples':s['checkpoint_trace']})\n"
        "result={'sample':result['sample'],'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_samples.json').read_bytes()).hexdigest(),"
        f"'source_sha256':hashlib.sha256({source!r}.encode('utf8')).hexdigest()}}\n")


def pair_code(core,new_path,new_sha,reference_path,reference_sha):
    return (core+'\nimport json,hashlib\nfrom pathlib import Path\n'
        f"a=Path({str(reference_path)!r});b=Path({str(new_path)!r})\n"
        f"assert hashlib.sha256(a.read_bytes()).hexdigest()=={reference_sha!r}\n"
        f"assert hashlib.sha256(b.read_bytes()).hexdigest()=={new_sha!r}\n"
        "a=json.loads(a.read_text(encoding='utf8'));b=json.loads(b.read_text(encoding='utf8'))\n"
        "result=compare_initial_pair(a['initial_pairing_reference'],b['initial_pairing_reference'])\n"
        "assert result['strict_pair_matched']\n"
        "s=getattr(hou.session,KEY)\n"
        "assert s['dop'].sessionId()==s['checkpoint_dop_id'] and len(s['samples'])==1\n"
        "assert not s['checkpoint_drive_authorized']\n"
        "s['initial_pair_verified']=True\n")


def final_gate_code(policy,samples_sha,conditions_sha):
    return (policy+'\nimport json,hashlib\nfrom pathlib import Path\n'
        "s=getattr(hou.session,KEY)\n"
        "assert s['dop'].sessionId()==s['checkpoint_dop_id'] and len(s['samples'])==361\n"
        "assert s['initial_pair_verified'] and not s['checkpoint_drive_authorized']\n"
        "p=Path(STAGE)/'Evidence/22_static_gate_input.json';c=Path(STAGE)/'Evidence/22_pilot_conditions.json'\n"
        f"assert hashlib.sha256(p.read_bytes()).hexdigest()=={samples_sha!r}\n"
        f"assert hashlib.sha256(c.read_bytes()).hexdigest()=={conditions_sha!r}\n"
        "rows=json.loads(p.read_text(encoding='utf8'))['samples'];assert rows==s['samples']\n"
        "gate=evaluate_gate(rows,json.loads(c.read_text(encoding='utf8')),6.)\n"
        "p=Path(STAGE)/'Evidence/22_static_gate_remote.json'\n"
        "p.write_bytes((json.dumps(gate,ensure_ascii=False,indent=2)+'\\n').encode('utf8'))\n"
        "result={'json_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),"
        f"'source_sha256':hashlib.sha256({policy!r}.encode('utf8')).hexdigest()}}\n")


def authorize_code(policy,gate_sha,samples_sha,conditions_sha):
    """独立RPC内で同じ固定原JSONと純関数を再評価してから許可を一度だけ登録。"""
    return final_gate_code(policy,samples_sha,conditions_sha)+f"""
assert gate['diagnostic_stability_passed']
assert abs(s['dop'].simulation().time()-6.)<1e-6
assert s['solver'].evalParm('doreseeding')==0
assert not s.get('coverage_alert_latched',False)
gate_path=Path(STAGE)/'Evidence/22_checkpoint_gate.json'
assert hashlib.sha256(gate_path.read_bytes()).hexdigest()=={gate_sha!r}
local_gate=json.loads(gate_path.read_text(encoding='utf8'))
assert local_gate['evaluation']==gate
assert local_gate['sample_sha256']=={samples_sha!r}
assert local_gate['conditions_sha256']=={conditions_sha!r}
assert local_gate['policy_sha256']=={hashlib.sha256(policy.encode('utf8')).hexdigest()!r}
s['checkpoint_drive_authorized']=True
record={{'authorized':True,'dop_session_id':s['dop'].sessionId(),'simulation_seconds':s['dop'].simulation().time(),
 'sample_sha256':{samples_sha!r},'conditions_sha256':{conditions_sha!r},
 'gate_sha256':{gate_sha!r},'policy_sha256':{hashlib.sha256(policy.encode('utf8')).hexdigest()!r},
 'parameters_changed':False,'simulation_reset':False,'final_sample':555}}
p=Path(STAGE)/'Evidence/22_drive_authorization.json'
p.write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\\n').encode('utf8'))
result={{'json_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_sha256':{hashlib.sha256(policy.encode('utf8')).hexdigest()!r}}}
"""


async def execute_reviewed_plan():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    plan,baseline,originals,executed=load_inputs()
    expected_conditions=originals['off_pilot_conditions.json']['record']
    budget=plan['resource_budget']
    reserved=plan['sample_count']*budget['predicted_raw_bytes_per_sample']+budget['probe_reports_reserved_bytes']
    assert shutil.disk_usage(WAVE).free>=2*reserved+budget['minimum_disk_free_bytes']
    token=uuid.uuid4().hex[:10]
    name,key='gw22_start04_'+token,'_gw22_start04_'+token
    output=WAVE/'Runs'/token
    for directory in ('Cache','Evidence','Source'):
        (output/directory).mkdir(parents=True,exist_ok=False)
    candidate_sources=('run_wave_start.py','wave_start_plan.json','startup_response.py','deepwater_core.py','readback_deepwater.py','run_baseline_readback.py')
    for filename in candidate_sources:
        (output/'Source'/filename).write_bytes((CANDIDATE/'Source'/filename).read_bytes())
    for filename in plan['baseline_executed_sources']:
        (output/'Source'/filename).write_bytes((executed/filename).read_bytes())
        assert sha(output/'Source'/filename)==plan['baseline_executed_sources'][filename]
    (output/'Baseline').mkdir()
    for k,v in baseline.items():
        v['path']=output/'Baseline'/('off_deepwater_%03d.json'%k)
        v['path'].write_bytes(v['raw']);assert sha(v['path'])==v['sha256']
    source=(output/'Source/generate_wave_l6.py').read_text(encoding='utf8')
    policy=(output/'Source/checkpoint_gate.py').read_text(encoding='utf8')
    core=(output/'Source/deepwater_core.py').read_text(encoding='utf8')
    adapter=(output/'Source/readback_deepwater.py').read_text(encoding='utf8')
    grid_code=(output/'Source/grid_metrics_l6.py').read_text(encoding='utf8')+'\n'+(output/'Source/probe_grid_l6.py').read_text(encoding='utf8')
    grid_sha=hashlib.sha256(grid_code.encode('utf8')).hexdigest()
    guard=load_module('off_guard',output/'Source/ui_guard.py')
    gate_module=load_module('off_gate',output/'Source/checkpoint_gate.py')
    report={'token':token,'utc':datetime.now(timezone.utc).isoformat(),'plan':plan,'events':[],
            'owned_path':'/obj/'+name,'drive_authorized':False,'coverage_alert_latched':False,
            'source_hashes':{p.name:sha(p) for p in (output/'Source').iterdir() if p.is_file()},
            'baseline_readbacks':{str(k):{'path':str(v['path'].relative_to(WAVE)),'sha256':v['sha256']} for k,v in baseline.items()},
            'reserved_bytes':reserved,'free_disk_before':shutil.disk_usage(WAVE).free}
    report_path=output/'Evidence/22_wave_start_execution.json'
    expected_pid=None
    snapshot=False
    uncertain=False
    rows=[]

    def save():write(report_path,report)

    def constants(phase):
        values={'NAME':name,'KEY':key,'OBJ_PATH':'/obj/'+name,'EXPECTED_PID':expected_pid,'STAGE':str(output),
                'PHASE':phase,'GRAVITY':9.81,'RESEEDING':False,'PISTON_ENABLED':True,
                'PARTICLE_SEPARATION':.04,'GRID_SCALE':1.5,'PISTON_START_SECONDS':6.,
                'MESH_STRIDE':2,'THREE_GAUGES':True,'BUDGET':budget,'GRID_PLAN':{
                    'collision_probe':json.loads((output/'Source/length6_plan.json').read_text(encoding='utf8'))['collision_probe']}}
        return '\n'.join(f'{k}={v!r}' for k,v in values.items())+'\n'

    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={
        'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR',
        'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    with (output/'Evidence/proxy.log').open('w',encoding='utf8') as error:
        async with stdio_client(params,errlog=error) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()

                async def execute(label,code,phase='',metadata=False):
                    nonlocal uncertain
                    assert not uncertain
                    prefix='' if metadata else constants(phase)+'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable() and hou.fps()==24\n'
                    started=time.monotonic()
                    try:
                        response=await client.call_tool('execute_python',{'code':prefix+code,'return_expression':'result',
                            'justification':'同じOFF物理条件の新所有DOP。t6静水再判定PASS後だけ固定t9.25まで始動観測。'+label})
                    except Exception:
                        uncertain=True
                        raise
                    data=json.loads(next(x.text for x in response.content if x.type=='text'))
                    report['events'].append({'phase':label,'rpc_seconds':time.monotonic()-started,
                                             'executed':data.get('executed'),'error':data.get('error'),'eval_error':data.get('eval_error')})
                    save()
                    assert not response.isError and data.get('executed') and not data.get('error') and not data.get('eval_error'),data
                    return data['return_value']

                try:
                    meta=await execute('現metadata',"import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'ui':hou.isUIAvailable(),'license':str(hou.licenseCategory()),'fps':hou.fps()}\n",metadata=True)
                    report['metadata']=meta
                    assert meta['version']=='22.0.429' and meta['ui'] and meta['license']=='licenseCategoryType.Indie' and meta['fps']==24
                    expected_pid=meta['pid']
                    report['snapshot']=await execute('UI保存',guard.SNAPSHOT);snapshot=True
                    report['clock_initialization']=await execute('作成前frame1',"before=hou.frame()\nhou.setUpdateMode(hou.updateMode.Manual)\nhou.setFrame(1)\nassert hou.frame()==1\nresult={'before':before,'creation_frame':hou.frame()}\n")
                    ack=await execute('新所有始動ケース作成',source+"\nresult={'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_conditions.json').read_bytes()).hexdigest(),"+f"'source_sha256':{report['source_hashes']['generate_wave_l6.py']!r}}}\n",'create')
                    conditions=exact_record(output/'Evidence/22_pilot_conditions.json',ack,report['source_hashes']['generate_wave_l6.py'])
                    verify_same_conditions(conditions,expected_conditions)
                    report['conditions']=conditions
                    report['ownership']=await execute('DOPと資源基線を登録',source+"\ns=getattr(hou.session,KEY)\ns['checkpoint_dop_id']=s['dop'].sessionId()\ns['checkpoint_drive_authorized']=False\ns['initial_pair_verified']=False\ns['checkpoint_baseline_private']=memory()['private_commit_bytes']\ns['checkpoint_trace']=[]\nresult={'dop_session_id':s['checkpoint_dop_id'],'baseline_private':s['checkpoint_baseline_private']}\n",'register')
                    schema_code=initialization_code(source)
                    schema_sha=hashlib.sha256(schema_code.encode('utf8')).hexdigest()
                    ack=await execute('所有初期化schema',f'SCHEMA_CODE={schema_code!r}\n'+schema_code,'initialization_probe')
                    schema_path=output/'Evidence/22_initialization_schema.json'
                    actual_schema=exact_record(schema_path,ack,schema_sha)
                    assert sha(output/'Evidence/22_reseed_internal_detail.json')==ack['detail_sha256']
                    schema_comparison=compare_initialization_schema(originals['off_initialization_schema.json']['record'],actual_schema)
                    schema_comparison.update({'baseline_sha256':originals['off_initialization_schema.json']['sha256'],'candidate_sha256':sha(schema_path),
                                              'observation_code_sha256':schema_sha,'additional_detail_sha256':ack['detail_sha256']})
                    write(output/'Evidence/22_initialization_schema_comparison.json',schema_comparison)
                    report['initialization_schema_comparison']=schema_comparison
                    assert not schema_comparison['differences']
                    detail=json.loads((output/'Evidence/22_reseed_internal_detail.json').read_text(encoding='utf8'))
                    assert detail['nodes']==originals['off_reseed_internal_detail.json']['record']['nodes']
                    report['internal_seed_parameters_match_off']=True

                    async def grid(phase):
                        ack=await execute('基線と同順の格子観測',source+'\n'+grid_code+
                            "\nresult={'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_length6_grid_preflight.json').read_bytes()).hexdigest(),"+f"'source_sha256':{grid_sha!r}}}\n",phase)
                        exact_record(output/'Evidence/22_length6_grid_preflight.json',ack,grid_sha)

                    async def deep_probe(index,row):
                        path=output/'Evidence'/('22_deepwater_%03d.json'%index)
                        code,code_sha=build_probe_code(core,adapter,expected_pid,output/'Cache'/('pilot_%03d.bgeo.sc'%index),row['cache_sha256'],index,row['particle_count'],path)
                        code+="\ns=getattr(hou.session,KEY)\nassert s['dop'].sessionId()==s['checkpoint_dop_id'] and not s['checkpoint_drive_authorized']\n"
                        ack=await execute('保存BGEOの深水観測 '+str(index),code)
                        actual=exact_record(path,ack,code_sha)
                        assert actual['deepwater']['observations_valid'],'無効fieldで停止'
                        paired=compare_coverage(baseline[index]['record']['deepwater']['rows'],actual['deepwater']['rows'])
                        alarm=bool(actual['deepwater']['coverage_alarm_point_indices'])
                        report['coverage_alert_latched']|=alarm
                        await execute('被覆警報を所有状態へ保持',"s=getattr(hou.session,KEY)\ns['coverage_alert_latched']=s.get('coverage_alert_latched',False) or "+repr(alarm)+"\nresult={'latched':s['coverage_alert_latched']}\n")
                        comparison={'sample':index,'new_report_sha256':sha(path),'baseline_report_sha256':baseline[index]['sha256'],
                                    'groups':paired,'coverage_alert_latched':report['coverage_alert_latched']}
                        write(output/'Evidence'/('22_coverage_pair_%03d.json'%index),comparison)
                        if index==0:
                            pair=compare_initial_pair(baseline[0]['record']['initial_pairing_reference'],actual['initial_pairing_reference'])
                            pair.update({'baseline_report_sha256':baseline[0]['sha256'],'candidate_report_sha256':sha(path)})
                            write(output/'Evidence/22_initial_strict_pair.json',pair)
                            report['initial_pair']=pair
                            assert pair['strict_pair_matched'],'OFF基線との初態配対が不成立。始動試験を停止'
                            await execute('同じ元JSONへ厳密配対を再確認',pair_code(core,path,sha(path),baseline[0]['path'],baseline[0]['sha256']))
                        save()

                    async def sample_one(index):
                        ack=await execute('実標本 '+str(index),sample_code(source,policy,index),'sample:'+str(index))
                        exact=exact_record(output/'Evidence/22_pilot_samples.json',ack,report['source_hashes']['generate_wave_l6.py'])['samples']
                        assert len(exact)==index+1 and exact[-1]['sample']==index
                        rows.append(exact[-1]);row=rows[-1]
                        if index in baseline:
                            await deep_probe(index,row)
                        if index==0:
                            await grid('grid_new:0');await grid('grid_new:'+repr(1/120))
                        elif index==1:
                            await grid('grid_new:'+repr(1/60))
                        elif index==30:
                            write(output/'Evidence/22_off_health_checkpoint.json',{'sample':30,'guards_passed':True,'static_gate_evaluated':False,'drive_authorized':False})
                        if index%30==0:
                            print(json.dumps({'token':token,'sample':index,'particles':row['particle_count'],
                                              'cook_seconds':row['cook_seconds'],'dop_bytes':row['simulation_memory_bytes'],
                                              'coverage_alert':report['coverage_alert_latched']},ensure_ascii=False),flush=True)
                    async def decide():
                        static_path=output/'Evidence/22_static_gate_input.json'
                        assert not static_path.exists() and len(rows)==361
                        static_path.write_bytes((output/'Evidence/22_pilot_samples.json').read_bytes())
                        assert json.loads(static_path.read_text(encoding='utf8'))['samples']==rows
                        local_gate=gate_module.evaluate_gate(rows,conditions,6.)
                        ack=await execute('t6元判定を再評価',final_gate_code(policy,sha(static_path),sha(output/'Evidence/22_pilot_conditions.json')))
                        remote_gate=exact_record(output/'Evidence/22_static_gate_remote.json',ack,report['source_hashes']['checkpoint_gate.py'])
                        assert local_gate==remote_gate
                        binding={'evaluation':local_gate,'sample_sha256':sha(static_path),'conditions_sha256':sha(output/'Evidence/22_pilot_conditions.json'),
                                 'policy_sha256':report['source_hashes']['checkpoint_gate.py'],'coverage_alert_latched':report['coverage_alert_latched']}
                        write(output/'Evidence/22_checkpoint_gate.json',binding);report['gate']=binding;save()
                        return local_gate

                    async def authorize(gate):
                        assert gate['diagnostic_stability_passed'] and len(rows)==361
                        if report['coverage_alert_latched']:
                            raise CoverageHold('静水数値判定PASS、被覆警報のため始動は未許可')
                        code=authorize_code(policy,sha(output/'Evidence/22_checkpoint_gate.json'),sha(output/'Evidence/22_static_gate_input.json'),sha(output/'Evidence/22_pilot_conditions.json'))
                        ack=await execute('同一DOPへ始動を許可',code)
                        permission=exact_record(output/'Evidence/22_drive_authorization.json',ack,report['source_hashes']['checkpoint_gate.py'])
                        assert permission['authorized'] and permission['dop_session_id']==report['ownership']['dop_session_id']
                        report['drive_authorized']=True;report['authorization']=permission;save()

                    try:
                        report['outcome']=await gate_module.run_phases(sample_one,decide,authorize,360,555)
                    except CoverageHold as exc:
                        report['outcome']={'status':'STATIC_PASS_COVERAGE_HOLD','last_sample':360,
                                           'drive_authorized':False,'reason_ja':str(exc),
                                           'solver_failure':False,'static_gate_passed':True}
                    if report['outcome']['drive_authorized']:
                        assert len(rows)==556
                        response=analyze_response(rows,plan['response_detection'])
                        response['sample_sha256']=sha(output/'Evidence/22_pilot_samples.json')
                        write(output/'Evidence/22_startup_response.json',response)
                    assert sha(output/'Evidence/22_static_gate_input.json')==report['gate']['sample_sha256']
                except Exception as exc:
                    report['failure']={'type':type(exc).__name__,'message':str(exc)}
                finally:
                    if snapshot and not uncertain:
                        try:
                            report['cleanup']=await execute('所有物削除とUI18復元',guard.CLEANUP)
                        except Exception as exc:
                            report['cleanup_failure']={'type':type(exc).__name__,'message':str(exc)}
                    report['transport_completion_uncertain']=uncertain
                    if uncertain:
                        report['recovery_required_ja']='RPCの完了確認前に追加要求・cleanup・GUI killをしない。所有KEY/sessionIdで後で復旧する。'
                    report['execution_succeeded']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False)
                    save()
    print(json.dumps({'token':token,'report':str(report_path),'outcome':report.get('outcome'),'execution_succeeded':report.get('execution_succeeded')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='承認前は計画表示だけ。静水FAILで終了、再PASS後だけ固定9.25秒まで。')
    parser.add_argument('--execute-reviewed-start-plan',action='store_true')
    args=parser.parse_args()
    if args.execute_reviewed_start_plan:
        asyncio.run(execute_reviewed_plan())
    else:
        print((CANDIDATE/'Source/wave_start_plan.json').read_text(encoding='utf8'))
