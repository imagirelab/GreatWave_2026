"""実Houdini/MCPを呼ばない始動候補検査。公開fixtureは読取りだけ。"""
import ast
import asyncio
import copy
import gzip
import hashlib
import json
import math
import tempfile
from pathlib import Path

import run_wave_start as runner
from startup_response import baseline_threshold, inspect_series, ordered_chains, analyze_response

checks = []


def check(name, condition):
    assert condition, name
    checks.append({'name_ja': name, 'passed': True})


def rejected(fn):
    try:
        fn()
    except (AssertionError, ValueError, FileNotFoundError):
        return True
    return False


plan, baseline, originals, executed = runner.load_inputs()
base = runner.WAVE/'Candidates/Reseeding03/Evidence/OFF_Result_4250d4451f'
frozen = {p: runner.sha(p) for p in base.rglob('*') if p.is_file()}
conditions = originals['off_pilot_conditions.json']['record']
rows = originals['off_pilot_samples.json']['record']['samples']
policy = (executed/'checkpoint_gate.py').read_text(encoding='utf8')
gate = runner.load_module('check_start_frozen_gate', executed/'checkpoint_gate.py')
core = (runner.CANDIDATE/'Source/deepwater_core.py').read_text(encoding='utf8')
source = (executed/'generate_wave_l6.py').read_text(encoding='utf8')
script = (runner.CANDIDATE/'Source/run_wave_start.py').read_text(encoding='utf8')
off_gate = gate.evaluate_gate(rows, conditions, 6.)
on_rows = json.loads(gzip.decompress((base/'Original/on_pilot_samples.json.gz').read_bytes()))['samples']
on_conditions = json.loads((base/'Original/on_pilot_conditions.json').read_text(encoding='utf8'))
on_gate = gate.evaluate_gate(on_rows, on_conditions, 6.)
check('OFF公開361標本は元判定PASS', off_gate['diagnostic_stability_passed'])
check('ON公開361標本は元判定FAIL', not on_gate['diagnostic_stability_passed'])
check('同じOFF作成条件だけを許容', runner.verify_same_conditions(conditions, conditions))
for key, value in [('tank_inner_m', [6.01, .6, .6]), ('piston_start_absolute_seconds', 5.9), ('piston_half_amplitude_m', .03)]:
    changed = copy.deepcopy(conditions); changed[key] = value
    check('作成条件変更を拒否 '+key, rejected(lambda: runner.verify_same_conditions(changed, conditions)))
for key, value in [('doreseeding', 1), ('seed', 1), ('gridscale', 2)]:
    changed = copy.deepcopy(conditions); changed['solver_parameters'][key] = value
    check('solver条件変更を拒否 '+key, rejected(lambda: runner.verify_same_conditions(changed, conditions)))
schema = originals['off_initialization_schema.json']['record']
same = copy.deepcopy(schema); same['owned_path'] = '/obj/new_owned'
check('schemaは所有パスだけを無視', not runner.compare_initialization_schema(schema, same)['differences'])
same['nodes'][-1]['parameters'][0]['value'] = '違う値'
check('内部実設定差を検出', bool(runner.compare_initialization_schema(schema, same)['differences']))


async def phase_fixture(evaluation):
    calls = []
    async def sample(k): calls.append(('sample', k))
    async def decide(): calls.append(('decide', 360)); return evaluation
    async def authorize(value):
        assert value['diagnostic_stability_passed']
        calls.append(('authorize', 360))
    outcome = await gate.run_phases(sample, decide, authorize, 360, 555)
    return calls, outcome


calls, outcome = asyncio.run(phase_fixture(on_gate))
check('実ON FAILは361標本で終了しauthorizeを呼ばない',
      outcome['last_sample'] == 360 and not outcome['drive_authorized'] and
      [k for tag, k in calls if tag == 'sample'] == list(range(361)) and not any(tag == 'authorize' for tag, _ in calls))
calls, outcome = asyncio.run(phase_fixture(off_gate))
check('実OFF PASSの制御模擬だけ556標本へ進む', outcome['last_sample'] == 555 and outcome['drive_authorized'] and
      [k for tag, k in calls if tag == 'sample'] == list(range(556)) and
      calls.index(('decide',360)) < calls.index(('authorize',360)) < calls.index(('sample',361)))


class Dop:
    def sessionId(self): return 22
    def evalParm(self, name): return 768 if name == 'cachemaxsize' else 0
    def simulation(self): return self
    def time(self): return 6.
class Solver:
    def evalParm(self, name): return 0
class Session: pass
class FakeHou:
    session = Session()


temp_root = runner.WAVE/'Local_Reproduction'; temp_root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='start04_offline_', dir=temp_root) as folder:
    folder = Path(folder); (folder/'Evidence').mkdir(); (folder/'Source').mkdir()
    for name, expected in plan['baseline_executed_sources'].items():
        (folder/'Source'/name).write_bytes((executed/name).read_bytes())
        assert runner.sha(folder/'Source'/name) == expected
    function = next(n for n in ast.walk(ast.parse(script)) if isinstance(n, ast.FunctionDef) and n.name=='constants')
    ns={'json':json,'output':folder,'name':'fake','key':'owned','expected_pid':123,'budget':plan['resource_budget']}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_constants','exec'),ns)
    values={}; exec(ns['constants']('register'),values)
    check('constantsのlength6_plan依存を実ファイルで満たす', values['GRID_PLAN']['collision_probe'] == json.loads((executed/'length6_plan.json').read_text(encoding='utf8'))['collision_probe'])
    (folder/'Source/length6_plan.json').unlink()
    check('length6_plan欠落を検出', rejected(lambda: ns['constants']('register')))
    state={'dop':Dop(),'solver':Solver(),'checkpoint_dop_id':22,'checkpoint_drive_authorized':False,
           'initial_pair_verified':False,'checkpoint_baseline_private':rows[0]['memory']['private_commit_bytes'],
           'checkpoint_trace':[],'samples':[]}
    setattr(FakeHou.session,'owned',state)
    # 実solverの代わりに明示的なfixture一行を保存する。実流体計算ではない。
    mock_source="""import hashlib,json
from pathlib import Path
s=getattr(hou.session,KEY)
def write(name,value):
 (Path(STAGE)/'Evidence'/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\\n').encode('utf8'))
result=SYNTHETIC_ROW
s['samples'].append(result)
write('22_pilot_samples.json',{'samples':s['samples']})
"""
    def sample_ns(row):
        return {'hou':FakeHou,'KEY':'owned','STAGE':str(folder),'BUDGET':plan['resource_budget'],'SYNTHETIC_ROW':copy.deepcopy(row)}
    ns=sample_ns(rows[0]);exec(runner.sample_code(mock_source,policy,0),ns)
    check('標本0のRPCは独立namespaceでJSON/SHAを返す', ns['result']['sample']==0 and ns['result']['json_sha256']==runner.sha(folder/'Evidence/22_pilot_samples.json'))
    check('厳密初態配対前のsample1を拒否', rejected(lambda:exec(runner.sample_code(mock_source,policy,1),sample_ns(rows[1]))))
    a=folder/'a.json';b=folder/'b.json'
    a.write_bytes(baseline[0]['raw']);b.write_bytes(a.read_bytes())
    ns={'hou':FakeHou,'KEY':'owned'}
    exec(runner.pair_code(core,b,runner.sha(b),a,runner.sha(a)),ns)
    check('元精度ID/P/v/pscaleと2場の全指紋配対後のみsample1許可', state['initial_pair_verified'] and ns['result']['strict_pair_matched'])
    fingerprint=baseline[0]['record']['initial_pairing_reference']
    for key in fingerprint:
        if key=='meaning_ja':continue
        record=copy.deepcopy(baseline[0]['record']);record['initial_pairing_reference'][key]='異なる指紋'
        b.write_bytes(json.dumps(record).encode());state['initial_pair_verified']=False
        check('初態差を拒否 '+key, rejected(lambda:exec(runner.pair_code(core,b,runner.sha(b),a,runner.sha(a)),{'hou':FakeHou,'KEY':'owned'})) and not state['initial_pair_verified'])
    check('初態ファイルSHA改変を拒否',rejected(lambda:exec(runner.pair_code(core,b,'bad',a,runner.sha(a)),{'hou':FakeHou,'KEY':'owned'})))
    state['samples']=copy.deepcopy(rows);state['initial_pair_verified']=True
    check('未許可のsample361を拒否',rejected(lambda:exec(runner.sample_code(mock_source,policy,361),sample_ns(rows[-1]))))
    static_path=folder/'Evidence/22_static_gate_input.json';static_path.write_bytes(originals['off_pilot_samples.json']['raw'])
    condition_path=folder/'Evidence/22_pilot_conditions.json';condition_path.write_bytes(originals['off_pilot_conditions.json']['raw'])
    ns={'hou':FakeHou,'KEY':'owned','STAGE':str(folder)}
    exec(runner.final_gate_code(policy,runner.sha(static_path),runner.sha(condition_path)),ns)
    check('remote gate独立namespaceが実OFF PASSと完全一致',runner.exact_record(folder/'Evidence/22_static_gate_remote.json',ns['result'],hashlib.sha256(policy.encode()).hexdigest())==off_gate)
    binding={'evaluation':off_gate,'sample_sha256':runner.sha(static_path),'conditions_sha256':runner.sha(condition_path),'policy_sha256':hashlib.sha256(policy.encode()).hexdigest()}
    gate_path=folder/'Evidence/22_checkpoint_gate.json';runner.write(gate_path,binding)
    code=runner.authorize_code(policy,runner.sha(gate_path),runner.sha(static_path),runner.sha(condition_path))
    bad_code=runner.authorize_code(policy,'bad',runner.sha(static_path),runner.sha(condition_path))
    check('gateファイルSHAの改変で許可拒否',rejected(lambda:exec(bad_code,{'hou':FakeHou,'KEY':'owned','STAGE':str(folder)})) and not state['checkpoint_drive_authorized'])
    state['coverage_alert_latched']=True
    check('被覆警報があればPASSでも駆動不許可',rejected(lambda:exec(code,{'hou':FakeHou,'KEY':'owned','STAGE':str(folder)})) and not state['checkpoint_drive_authorized'])
    state['coverage_alert_latched']=False
    ns={'hou':FakeHou,'KEY':'owned','STAGE':str(folder)};exec(code,ns)
    permission=runner.exact_record(folder/'Evidence/22_drive_authorization.json',ns['result'],hashlib.sha256(policy.encode()).hexdigest())
    check('原JSON+条件+policy+gate SHA再確認後だけ同じDOPを許可',permission['authorized'] and permission['dop_session_id']==22 and not permission['parameters_changed'] and not permission['simulation_reset'])
    row=copy.deepcopy(rows[-1]);row['sample']=361;row['requested_seconds']=361/60
    exec(runner.sample_code(mock_source,policy,361),sample_ns(row))
    check('許可後sample361へ前進',len(state['samples'])==362)
    check('続行後も361行入力と許可SHAは不変',runner.sha(static_path)==binding['sample_sha256'] and len(json.loads(static_path.read_bytes())['samples'])==361)
    check('同じ許可を二重発行しない',rejected(lambda:exec(code,{'hou':FakeHou,'KEY':'owned','STAGE':str(folder)})))
    check('sample556を拒否',rejected(lambda:exec(runner.sample_code(mock_source,policy,556),sample_ns(row))))
    state['checkpoint_dop_id']=999
    check('DOP sessionIdが変われば停止',rejected(lambda:exec(runner.sample_code(mock_source,policy,362),sample_ns(row))))

check('初期時刻Manual/frame1はcreate前',script.index('hou.setUpdateMode(hou.updateMode.Manual)')<script.index("'create')"))
check('半ステップ観測の元順序を維持',"await grid('grid_new:0');await grid('grid_new:'+repr(1/120))" in script and "await grid('grid_new:'+repr(1/60))" in script)
check('不明RPC後は追加cleanupを行わない', 'if snapshot and not uncertain:' in script and 'assert not uncertain' in script)
check('原UI18復元関数を再利用', 'guard.CLEANUP' in script and 'all_ui_and_owned_node_checks_passed' in script)
check('静水PASSでも被覆holdをsolver故障/静水FAILへ書換えない',"'status':'STATIC_PASS_COVERAGE_HOLD'" in script and "'solver_failure':False,'static_gate_passed':True" in script)
check('公開OFF基線全ファイル不変',all(runner.sha(p)==value for p,value in frozen.items()))

# 応答検出規則は合成水位でのみ検査。実波の合格とは区別する。
config=plan['response_detection']
series=[(k/60,-.01) for k in range(556)]
flat=inspect_series(series,config,60)
check('一定の絶対負水位をゼロへ補正せず無応答扱い',flat['onset'] is None and flat['features']==[] and flat['raw_eta_at_t6_m']==-.01)
threshold=baseline_threshold([(k/60, .002 if k<=315 else -.001) for k in range(271,361)])
check('Eは新run二静水窓の全標本から後窓平均との差を取る',abs(threshold['threshold_m']-.003)<1e-12 and threshold['window_counts']==[45,45])
pulse=[(t,v+(.01*math.exp(-((t-7.4)/.13)**2) if t>6 else 0)) for t,v in series]
event=inspect_series(pulse,config,60)
check('宣言したq/両側prominenceで合成峰を検出',event['onset'] is not None and len(event['features'])==1)
shifted=[inspect_series([(t,v+(.01*math.exp(-((t-center)/.13)**2) if t>6 else 0)) for t,v in series],config,60) for center in (7.4,7.7,8.1)]
chains=ordered_chains(shifted,config['ordered_same_sign_adjacent_lag_open_s'])
check('理論へ合わせず一意な同号三点鎖を検出',len(chains)==1 and chains[0]['adjacent_lags_s']!=[.375,.375])
ambiguous=copy.deepcopy(shifted);extra=copy.deepcopy(ambiguous[1]['features'][0]);extra['time_s']+=.1;ambiguous[1]['features'].append(extra)
check('複数可能鎖を理論近傍で勝手に選ばない',len(ordered_chains(ambiguous,config['ordered_same_sign_adjacent_lag_open_s']))==2)
edge=inspect_series([(t,v+(.01*math.exp(-((t-9.1)/.1)**2) if t>6 else 0)) for t,v in series],config,60)
check('終端でprominence窓が切れる極値を保留',len(edge['features'])==0 and len(edge['truncated_candidates'])>0)
low=inspect_series([(t,v+.0005*math.sin(8*t) if t>6 else v) for t,v in series],config,60)
check('q未満の合成応答は不検出',low['onset'] is None and not low['features'])
isolated=inspect_series([(t,v+(.01 if t==7.5 else 0)) for t,v in series],config,60)
check('単一rawスパイクは同符号5標本のonsetにならない',isolated['onset'] is None)
all_rows=copy.deepcopy(rows)
for k in range(361,556):
    row=copy.deepcopy(rows[-1]);row.update(sample=k,requested_seconds=k/60,simulation_seconds=k/60,mesh_sampled=k%2==0)
    all_rows.append(row)
for row in all_rows:
    for index,g in enumerate(row['gauges']):
        g['eta_m']=shifted[index]['raw_eta_at_t6_m'];g['mesh_eta_m']=g['eta_m']-.01
observed=analyze_response(all_rows,config)
check('SDF/PFS別集計で精度/無反射/22完了は宣言しない',not observed['wave_verified'] and not observed['reflection_free_verified'] and not observed['step22_complete'] and len(observed['observations'])==2)

manifest=json.loads((base/'22_cache_manifest.json').read_text(encoding='utf8'))
cache=manifest['cache_files'];per_sample=[r['cache_bytes']+sum(c['bytes'] for c in cache if c['kind']=='PFS' and c['seconds']==r['requested_seconds']) for r in rows]
mean_bytes=sum(per_sample)/len(per_sample);max_bytes=max(per_sample)
reserve=plan['sample_count']*plan['resource_budget']['predicted_raw_bytes_per_sample']+plan['resource_budget']['probe_reports_reserved_bytes']
report={'houdini_or_mcp_called':False,'real_startup_run_executed':False,'checks':checks,'passed':True,
        'source_hashes':{p.name:runner.sha(p) for p in sorted((runner.CANDIDATE/'Source').iterdir()) if p.is_file()},
        'frozen_generator_dependencies':plan['baseline_executed_sources'],
        'off_baseline_measured':{'solver_cook_sum_s':sum(r['cook_seconds'] for r in rows),'maximum_sample_cook_s':max(r['cook_seconds'] for r in rows),
            'all_cache_bytes':sum(c['bytes'] for c in cache),'mean_solver_plus_optional_PFS_bytes_per_sample':mean_bytes,'maximum_solver_plus_PFS_bytes_per_sample':max_bytes,
            'minimum_available_ram_bytes':min(r['memory']['available_physical_bytes'] for r in rows),'maximum_private_commit_bytes':max(r['memory']['private_commit_bytes'] for r in rows)},
        'startup_budget':{'final_sample':555,'sample_count':556,'mesh_count':278,'cache_file_count':840,
            'linear_cook_estimate_s':sum(r['cook_seconds'] for r in rows)*556/361,'raw_at_mean_bytes':mean_bytes*556,'raw_at_maximum_bytes':max_bytes*556,
            'reserved_bytes':reserve,'required_free_disk_before_bytes':2*reserve+plan['resource_budget']['minimum_disk_free_bytes'],
            'meaning_ja':'静水実績の線形外挿であり、駆動費用の保証ではない。実行時は各標本の既定資源保護で停止する。'},
        'timing_estimates':plan['timing_estimates']}
runner.write(runner.CANDIDATE/'Evidence/22_startup_offline_checks.json',report)
print(json.dumps({'checks':len(checks),'passed':True,'houdini_or_mcp_called':False},ensure_ascii=False))
