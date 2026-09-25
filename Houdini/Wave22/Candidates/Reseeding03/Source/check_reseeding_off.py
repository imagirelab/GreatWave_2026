"""OFF実行候補の離線検査。実Houdini/MCP・既存証拠への書込みは行わない。"""
import ast
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from run_reseeding_off import (CANDIDATE, WAVE, exact_record, final_gate_code, compare_initialization_schema, initialization_code,
                              load_inputs, load_module, pair_code, sample_code,
                              verify_only_reseed_change)
from reseeding_policy import next_decision

checks=[]


def check(label,condition):
    assert condition,label
    checks.append({'name_ja':label,'passed':True})


def rejected(function):
    try:function()
    except (AssertionError,ValueError):return True
    return False


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


plan,baseline,conditions,executed=load_inputs()
check('唯一基線と6原JSON/source SHAを照合',sorted(baseline)==[0,30,180,270,315,360])
off=copy.deepcopy(conditions);off['solver_parameters']['doreseeding']=0;off['case_id']+='NoReseed'
check('作成条件でreseedだけの変更を許容',verify_only_reseed_change(off,conditions))
for field,new in [('tank_inner_m',[5.98,.6,.6]),('piston_start_absolute_seconds',6.1),('display_voxel_m',.04)]:
    changed=copy.deepcopy(off);changed[field]=new
    check('他条件変更を拒否 '+field,rejected(lambda:verify_only_reseed_change(changed,conditions)))
changed=copy.deepcopy(off);changed['solver_parameters']['seed']=2203
check('seed変更を拒否',rejected(lambda:verify_only_reseed_change(changed,conditions)))
check('reseed ONのままなら拒否',rejected(lambda:verify_only_reseed_change(conditions,conditions)))
samples_path=WAVE/'Evidence/Curated_Runs/db52394211/22_pilot_samples.json'
before_sha=sha(samples_path)
raw=json.loads(samples_path.read_text(encoding='utf8'));rows=raw['samples']
gate_module=load_module('offline_original_gate',executed/'checkpoint_gate.py')
actual=gate_module.evaluate_gate(rows,conditions,6.)
check('元L6の2つのG3傾きFAILを保持',not actual['diagnostic_stability_passed'] and
      [i for i,g in enumerate(actual['gauge_checks']) if not g['both_trend_passed']]==[2])
policy=(executed/'checkpoint_gate.py').read_text(encoding='utf8')
core=(CANDIDATE/'Source/deepwater_core.py').read_text(encoding='utf8')
runner=(CANDIDATE/'Source/run_reseeding_off.py').read_text(encoding='utf8')
check('PASSからauthorizeする旧run_phasesを使わない','run_phases' not in runner and 'async def authorize' not in runner)
check('全実標本は固定range361','for index in range(361)' in runner)
check('基線と同じhalf-step観測順序を維持',"await grid('grid_new:0');await grid('grid_new:'+repr(1/120))" in runner and "await grid('grid_new:'+repr(1/60))" in runner)
check('時計をManual/frame1へ固定してからcreate',runner.index('hou.setUpdateMode(hou.updateMode.Manual)')<runner.index("'create')"))
check('完了不明ではcleanupを送らない','if snapshot and not uncertain:' in runner)
check('終了は元18項目UI復元','guard.CLEANUP' in runner and 'all_ui_and_owned_node_checks_passed' in runner)
check('実初期化schemaを所有scopeで採録',"+schema_code,'initialization_probe'" in runner)
schema=json.loads((samples_path.parent/'22_initialization_schema.json').read_text(encoding='utf8'))
schema_off=copy.deepcopy(schema);schema_off['owned_path']='/obj/new_owned'
check('schema比較は所有ルート名だけを無視',not compare_initialization_schema(schema,schema_off)['differences'])
for node in schema_off['nodes']:
    for parameter in node['parameters']:
        if parameter['name']=='doreseeding':parameter['value']=0
delta=compare_initialization_schema(schema,schema_off)
check('実reseed差をschema比較へ保持',len(delta['differences'])==1 and delta['differences'][0]['key'].endswith('/doreseeding'))
schema_off['nodes'][-1]['parameters'][0]['value']=2
check('内部DOPの別設定差も報告',len(compare_initialization_schema(schema,schema_off)['differences'])==2)
check('補足schemaは読取りだけ',"parm.set(" not in initialization_code('') and 'existing_scene_read' in initialization_code(''))


class Dop:
    def sessionId(self):return 22
    def evalParm(self,name):return 768 if name=='cachemaxsize' else 0
class Solver:
    def evalParm(self,name):return 0
class Session:pass
class FakeHou:
    session=Session()


temp_root=WAVE/'Local_Reproduction';temp_root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='off_logic_',dir=temp_root) as folder:
    folder=Path(folder);(folder/'Evidence').mkdir()
    # runner内の実constants関数を独立namespaceへ取り出し、コピー依存を実体で検査する。
    (folder/'Source').mkdir()
    for name,expected in plan['baseline_executed_sources'].items():
        target=folder/'Source'/name;target.write_bytes((executed/name).read_bytes());assert sha(target)==expected
    function=next(n for n in ast.walk(ast.parse(runner)) if isinstance(n,ast.FunctionDef) and n.name=='constants')
    ns={'json':json,'output':folder,'name':'fake','key':'owned','expected_pid':123,'budget':plan['resource_budget']}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_constants','exec'),ns)
    values={};exec(ns['constants']('register'),values)
    check('constants全依存をコピー後に実評価',values['GRID_PLAN']['collision_probe']==json.loads((executed/'length6_plan.json').read_text(encoding='utf8'))['collision_probe'] and values['RESEEDING'] is False)
    (folder/'Source/length6_plan.json').unlink()
    missing=False
    try:ns['constants']('register')
    except FileNotFoundError:missing=True
    check('凍結length6_plan欠落を再現して検出',missing)
    state={'dop':Dop(),'solver':Solver(),'checkpoint_dop_id':22,'checkpoint_drive_authorized':False,
           'initial_pair_verified':False,'checkpoint_baseline_private':0,'checkpoint_trace':[],'samples':[]}
    setattr(FakeHou.session,'owned',state)
    budget=copy.deepcopy(plan['resource_budget']);budget['maximum_private_growth_bytes']=128*1024**3
    # 既存rawを変えず、明示的に模擬値だけを生成するsourceでwrapperを実行する。
    synthetic_source="""import hashlib,json
from pathlib import Path
s=getattr(hou.session,KEY)
def write(name,value):
    (Path(STAGE)/'Evidence'/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\\n').encode('utf8'))
result=SYNTHETIC_ROW
s['samples'].append(result)
write('22_pilot_samples.json',{'samples':s['samples']})
"""
    ns={'hou':FakeHou,'KEY':'owned','STAGE':str(folder),'BUDGET':budget,'SYNTHETIC_ROW':copy.deepcopy(rows[0])}
    exec(compile(sample_code(synthetic_source,policy,0),'sample_rpc','exec'),ns)
    check('標本RPCを独立namespaceで実行',len(state['samples'])==1 and ns['result']['sample']==0)
    check('標本RPCが原JSONとsource SHAへ結合',ns['result']['json_sha256']==sha(folder/'Evidence/22_pilot_samples.json') and
          ns['result']['source_sha256']==hashlib.sha256(synthetic_source.encode('utf8')).hexdigest())
    blocked={'hou':FakeHou,'KEY':'owned','STAGE':str(folder),'BUDGET':budget,'SYNTHETIC_ROW':copy.deepcopy(rows[1])}
    check('t0厳密配対前にはsample1を拒否',rejected(lambda:exec(sample_code(synthetic_source,policy,1),blocked)))
    check('sample361は無条件拒否',rejected(lambda:exec(sample_code(synthetic_source,policy,361),blocked)))
    a=folder/'reference.json';b=folder/'candidate.json'
    fixture={'initial_pairing_reference':baseline[0]['record']['initial_pairing_reference']}
    a.write_bytes((json.dumps(fixture)+'\n').encode());b.write_bytes(a.read_bytes())
    ns={'hou':FakeHou,'KEY':'owned'}
    exec(compile(pair_code(core,b,sha(b),a,sha(a)),'pair_rpc','exec'),ns)
    check('配対RPCは原SHA/全指紋一致後だけ許可',state['initial_pair_verified'] and ns['result']['strict_pair_matched'])
    changed=copy.deepcopy(fixture);changed['initial_pairing_reference']['sorted_ID_v_sha256']='different'
    b.write_bytes(json.dumps(changed).encode());state['initial_pair_verified']=False
    check('初期vの差で配対拒否',rejected(lambda:exec(pair_code(core,b,sha(b),a,sha(a)),{'hou':FakeHou,'KEY':'owned'})) and not state['initial_pair_verified'])
    check('原JSON SHA不一致でも拒否',rejected(lambda:exec(pair_code(core,b,'bad',a,sha(a)),{'hou':FakeHou,'KEY':'owned'})))
    # 実公開361標本の読み取りだけでremote gate経路を模擬する。
    sample_target=folder/'Evidence/22_pilot_samples.json';sample_target.write_bytes(samples_path.read_bytes())
    condition_target=folder/'Evidence/22_pilot_conditions.json';condition_target.write_bytes(json.dumps(conditions).encode())
    state['samples']=rows;state['initial_pair_verified']=True
    ns={'hou':FakeHou,'KEY':'owned','STAGE':str(folder)}
    exec(compile(final_gate_code(policy,sha(sample_target),sha(condition_target)),'gate_rpc','exec'),ns)
    stored=exact_record(folder/'Evidence/22_static_gate_remote.json',ns['result'],hashlib.sha256(policy.encode('utf8')).hexdigest())
    check('別namespace remote gateが元FAILと完全一致',stored==actual and not state['checkpoint_drive_authorized'])

for gate_pass in (False,True):
    alert=False
    for k in range(361):
        d=next_decision(k,True,True,True,alert,k in (30,315),gate_pass if k==360 else None)
        alert=d['coverage_alert_latched']
        assert not d['drive_authorized']
        assert d['next_sample']==(k+1 if k<360 else None)
    check('被覆警報は終点選択に使わずt6まで '+str(gate_pass),alert and d['action']=='FINISH_STATIC_DIAGNOSTIC')
baseline_execution=json.loads((WAVE/'Runs/deepwater03_c4aab88dc2/execution.json').read_text(encoding='utf8'))
check('6源の基線読戻しコードは実行時のSHAを保持',all(
    sha(CANDIDATE/'Source'/name)==expected for name,expected in baseline_execution['source_hashes'].items()) and
    sha(CANDIDATE/'Source/reseeding03_plan.json')==baseline_execution['plan_sha256'])
check('公開fixtureは不変',sha(samples_path)==before_sha)

summary=json.loads((CANDIDATE/'Evidence/22_baseline_readback_summary.json').read_text(encoding='utf8'))
cache=json.loads((WAVE/'Evidence/Length6_Result_db52394211/22_cache_manifest.json').read_text(encoding='utf8'))
reserve=361*plan['resource_budget']['predicted_raw_bytes_per_sample']+plan['resource_budget']['probe_reports_reserved_bytes']
report={'houdini_or_mcp_called':False,'off_simulation_executed':False,'checks':checks,'passed':True,
        'source_hashes':{p.name:sha(p) for p in sorted((CANDIDATE/'Source').iterdir()) if p.is_file()},
        'unchanged_executed_source_hashes':plan['baseline_executed_sources'],
        'baseline_summary_sha256':sha(CANDIDATE/'Evidence/22_baseline_readback_summary.json'),
        'actual_baseline_cost':{'solver_cook_sum_seconds':sum(r['cook_seconds'] for r in rows),
            'all_548_cache_bytes':cache['total_bytes'],'deepwater_readback_six_seconds':summary['readback_seconds_total'],
            'deepwater_original_json_six_bytes':summary['json_bytes_total'],
            'meaning_ja':'実ON基線の費用。OFFの速度・容量を保証しない。追加観測は標本cook時間と別記する。'},
        'operational_budget':{'reserved_bytes':reserve,'initial_required_free_disk_bytes':2*reserve+10*1024**3,
                              'maximum_deepwater_read_seconds':90,'rpc_timeout_seconds':180},
        'meaning_ja':'配対・条件差分・独立namespace・固定終点の離線検査。実OFFの初態一致、内部reseed設定、静水結果は未検証。'}
(CANDIDATE/'Evidence/22_off_runner_checks.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'checks':len(checks),'passed':True,'off_simulation_executed':False},ensure_ascii=False))
