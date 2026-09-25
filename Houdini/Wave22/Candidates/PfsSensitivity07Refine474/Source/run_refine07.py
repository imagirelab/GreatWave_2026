"""既定は表示だけ。明示実行許可後もk474新.25面化を一回だけ実行する。"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from replay_support06 import classify_rpc_reply
from refine_core06 import profile_shape06
from refine_contract07 import target07, initial_disk07, read_profile_baseline07, compare_profile05_07

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = CANDIDATE.parents[3]
WAVE = CANDIDATE.parents[1]
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
GUARD = 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Executed_Source/ui_guard.py'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def validate_frozen():
    plan = json.loads((CANDIDATE / 'Source/refine_plan.json').read_bytes())
    report = json.loads((CANDIDATE / 'Evidence/22_refine_offline_checks.json').read_bytes())
    freeze_path = CANDIDATE / 'Evidence/22_refine_candidate_freeze.json'
    freeze = json.loads(freeze_path.read_bytes())
    assert report['passed'] and report['houdini_called'] is False
    actual = {p.relative_to(CANDIDATE).as_posix() for p in CANDIDATE.rglob('*') if p.is_file() and p != freeze_path}
    assert actual == {r['path'] for r in freeze['files']}
    assert all((CANDIDATE / r['path']).stat().st_size == r['bytes'] and sha(CANDIDATE / r['path']) == r['sha256'] for r in freeze['files'])
    assert all(sha(CANDIDATE / 'Source' / name) == expected for name, expected in report['source_hashes'].items())
    prior_path = CANDIDATE / 'Evidence/22_prior_attempts_manifest.json'
    assert sha(prior_path) == plan['prior_attempts_manifest_sha256']
    prior = json.loads(prior_path.read_bytes())
    assert all((ROOT / row['path']).stat().st_size == row['bytes'] and sha(ROOT / row['path']) == row['sha256'] for row in prior['files'])
    actual_prior = {p.relative_to(ROOT).as_posix() for d in prior['protected_directories'] for p in (ROOT / d).rglob('*') if p.is_file()} | set(prior['protected_files'])
    assert actual_prior == {r['path'] for r in prior['files']}
    assert len(actual_prior) == prior['file_count'] and sum(r['bytes'] for r in prior['files']) == prior['total_bytes']
    for row in (plan['decision_freeze'], plan['decision_report']):
        assert (ROOT / row['path']).stat().st_size == row['bytes'] and sha(ROOT / row['path']) == row['sha256']
    assert all(sha(ROOT / r['path']) == r['sha256'] for r in plan['support_origins'])
    baseline = WAVE / 'Candidates/WaveStart04/Evidence/Result_22e7801642'
    assert all(sha(baseline / name) == expected for name, expected in plan['baseline_files'].items())
    assert plan['scope'] == 'ONE_K474_QUARTER_MESH_SENSITIVITY_ONLY' and plan['sample'] == 474
    assert plan['global_frame'] == (1 + .4 * 474) and plan['fps'] == 24 and plan['mesh_parameters']['voxelsize'] == .25
    assert plan['refinement_allowed'] is True and plan['other_samples_allowed'] is False
    for group in plan['baseline_successes'].values():
        for row in group.values():
            assert sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes']
        raw = json.loads((ROOT / group['raw']['path']).read_bytes())
        execution = json.loads((ROOT / group['execution']['path']).read_bytes())
        assert raw['passed'] and raw['native_exact'] and raw['mesh_parity']['passed']
        assert execution['passed_for_review'] and not execution['transport_completion_uncertain']
    for name, row in plan['profile_dependencies'].items():
        assert sha(ROOT / row['path']) == sha(CANDIDATE / 'Source' / name) == row['sha256']
    for name, row in plan['support_dependency']['files'].items():
        assert sha(ROOT / row['path']) == sha(CANDIDATE / 'Source' / name) == row['sha256']
    for kind in ('pilot', 'mesh'):
        row = plan['record'][kind]
        path = WAVE / 'Runs' / plan['baseline_run'] / 'Cache' / row['filename']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    target07(plan)
    for row in [plan['comparison_plan'], *plan['validated_refine360'].values()]:
        assert sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes']
    assert read_profile_baseline07(ROOT, plan['profile05_baseline'])['mesh_sha256'] == plan['record']['mesh']['sha256']
    return plan


def probe_rpc(source, values):
    prefix = '\n'.join(f'{k}={v!r}' for k, v in values.items()) + '\n'
    return prefix + source + '''
with hou.undos.disabler():
    observed=refine_k474(hou,KEY,OBJ_PATH,PLAN,PATHS)
observed['combined_source_sha256']=SOURCE_SHA
observed['plan_sha256']=PLAN_SHA
payload=(json.dumps(serializable_observation(observed),ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
Path(DESTINATION).write_bytes(payload)
result={'json_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':SOURCE_SHA}
'''


def profile_rpc06(source, values):
    """UI復元後の別RPC。既存BGEOを読むだけで、ノード/時刻を変更しない。"""
    prefix = '\n'.join(f'{k}={v!r}' for k, v in values.items()) + '\n'
    return prefix + source + '''
def metadata_profile06():
    return {'frame':hou.frame(),'fps':hou.fps(),'mode':str(hou.updateModeSetting()),
            'hip_has_unsaved_changes':hou.hipFile.hasUnsavedChanges()}
before=metadata_profile06()
assert hou.node(OBJ_PATH) is None, '所有SOP復元前の断面読戻し禁止'
observed={'completed_readback':False,'new_solver':False,'nodes_created':False}
resource_reads=[]
def resource_profile06():
    value=memory06(Path(SOLVER_PATH).anchor)
    resource_reads.append(value)
    assert value['available_bytes']>=PROFILE_LIMITS['minimum_available_RAM_bytes'], '断面RAM保護'
    assert value['free_G_bytes']>=PROFILE_LIMITS['minimum_free_G_bytes'], '断面G空き保護'
    assert value['private_bytes']-BASE_PRIVATE<PROFILE_LIMITS['maximum_private_increase_bytes'], '断面private増分保護'
try:
    resource_profile06()
    observed=read_pair(hou,Path(MESH_PATH),Path(SOLVER_PATH),EXPECTED,PROFILE_PLAN)
    resource_profile06()
    observed['completed_readback']=True
except Exception as exc:
    observed['completed_readback']=False
    observed['failure_type']=type(exc).__name__
    observed['failure_message_local']=str(exc)
finally:
    observed['metadata_before']=before
    observed['metadata_after']=metadata_profile06()
    observed['metadata_unchanged']=before==observed['metadata_after']
    observed['combined_reader_sha256']=SOURCE_SHA
    observed['plan_sha256']=PLAN_SHA
    observed['expected_inputs']=EXPECTED
    observed['resource_readings']=resource_reads
    observed['input_sha_after']={'mesh':file_sha(Path(MESH_PATH)),'solver':file_sha(Path(SOLVER_PATH))}
    payload=(json.dumps(serializable_observation(observed),ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
    assert not Path(DESTINATION).exists(), '断面JSON上書き禁止'
    used=sum(p.stat().st_size for p in Path(OUTPUT_ROOT).rglob('*') if p.is_file())
    remaining=PROFILE_LIMITS['auxiliary_reserved_bytes']-used-PROFILE_LIMITS['profile_output_bookkeeping_reserved_bytes']
    budget_hold=None
    if len(payload)>PROFILE_LIMITS['maximum_profile_bytes'] or len(payload)>remaining:
        budget_hold={'attempted_json_bytes':len(payload),'attempted_json_sha256':hashlib.sha256(payload).hexdigest(),
                     'existing_run_bytes':used,'remaining_payload_bytes':remaining,
                     'maximum_profile_bytes':PROFILE_LIMITS['maximum_profile_bytes']}
        # 完全断面を保存しない容量HOLD。数値を部分結果として採用しない。
        retained={k:observed[k] for k in ('metadata_before','metadata_after','metadata_unchanged',
                  'combined_reader_sha256','plan_sha256','expected_inputs','resource_readings','input_sha_after')}
        retained.update(completed_readback=False,failure_type='ProfileOutputBudgetHold',budget_hold=budget_hold,
                        complete_profiles_saved=False,attempted_profile_rows=len(observed.get('profiles',[])))
        payload=(json.dumps(serializable_observation(retained),ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
    can_write=len(payload)<=PROFILE_LIMITS['maximum_profile_bytes'] and len(payload)<=remaining
    if can_write:
        Path(DESTINATION).write_bytes(payload)
result={'json_sha256':hashlib.sha256(payload).hexdigest() if can_write else None,
        'source_sha256':SOURCE_SHA,'json_written':can_write,'budget_hold':budget_hold}
'''


async def execute():
    plan = validate_frozen()
    target07(plan)
    initial_disk = initial_disk07(shutil.disk_usage(WAVE.anchor).free, plan)
    published_old_profile = read_profile_baseline07(ROOT, plan['profile05_baseline'])
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    token = 'pfsrefine07_' + uuid.uuid4().hex[:10]
    output = WAVE / 'Runs' / token; output.mkdir(exist_ok=False); (output / 'Source').mkdir(); (output / 'Cache').mkdir()
    for path in (CANDIDATE / 'Source').iterdir():
        if path.is_file(): (output / 'Source' / path.name).write_bytes(path.read_bytes())
    (output / 'Source/ui_guard.py').write_bytes((ROOT / GUARD).read_bytes())
    spec = importlib.util.spec_from_file_location('guard_file06', output / 'Source/ui_guard.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    source = '\n'.join((output / 'Source' / name).read_text(encoding='utf8') for name in ('replay_support06.py', 'replay_window06.py', 'refine_core06.py', 'refine_contract07.py', 'refine_k474.py'))
    source_sha = hashlib.sha256(source.encode('utf8')).hexdigest(); plan_sha = sha(output / 'Source/refine_plan.json')
    name = 'gw22_' + token; key = '_' + name
    report = {'initial_disk': initial_disk, 'token': token, 'scope': plan['scope'], 'source_hashes': {p.name: sha(p) for p in (output / 'Source').iterdir()},
              'events': [], 'new_meshing_planned': True, 'new_solver': False, 'refinement_planned': True, 'passed_for_review': False, 'combined_source_sha256': source_sha, 'plan_sha256': plan_sha}
    report_path = output / 'execution.json'; pid = None; snapshot_attempted = False; uncertain = False
    parameters = StdioServerParameters(command=PYTHON, args=['-m', 'fxhoudinimcp'], env={
        'HOUDINI_HOST': '127.0.0.1', 'HOUDINI_PORT': '8100', 'MCP_TRANSPORT': 'stdio',
        'LOG_LEVEL': 'ERROR', 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    with (output / 'proxy.log').open('w', encoding='utf8') as log:
        async with stdio_client(parameters, errlog=log) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=plan['budgets']['rpc_wait_seconds'])) as client:
                await client.initialize()
                async def call(label, code, metadata=False):
                    nonlocal uncertain
                    assert not uncertain
                    prefix = f'KEY={key!r}\nOBJ_PATH={"/obj/" + name!r}\n'
                    if not metadata: prefix += f'import os\nassert os.getpid()=={pid} and hou.isUIAvailable() and hou.fps()==24\n'
                    started = time.monotonic()
                    try:
                        reply = await client.call_tool('execute_python', {'code': prefix + code, 'return_expression': 'result',
                            'justification': '審査済みk474新.25面化だけ。入力判定後の二つの短い更新窓、DOPなし、UI18復元。' + label})
                    except Exception:
                        uncertain = True; raise
                    raw_text = None
                    try:
                        raw_text = next((c.text for c in reply.content if c.type == 'text'), None)
                        status, data = classify_rpc_reply(raw_text, reply.isError)
                    except Exception: status, data = 'UNCERTAIN', None
                    if status == 'UNCERTAIN': uncertain = True
                    report['events'].append({'phase': label, 'seconds': time.monotonic() - started, 'completion_class': status,
                                              'raw_response_local': raw_text})
                    write(report_path, report)
                    assert status == 'COMPLETE_SUCCESS', 'RPC失敗または完了不明'
                    return data['return_value']
                try:
                    meta = await call('METADATA', "import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'license':str(hou.licenseCategory()),'ui':hou.isUIAvailable(),'fps':hou.fps()}", True)
                    assert meta['version'] == '22.0.429' and meta['license'] == 'licenseCategoryType.Indie' and meta['ui'] and meta['fps'] == 24
                    report['metadata'] = meta; pid = meta['pid']
                    snapshot_attempted = True; report['snapshot'] = await call('SNAPSHOT', guard.SNAPSHOT)
                    setup = f'''
with hou.undos.disabler():
    state=getattr(hou.session,KEY)
    hou.setUpdateMode(hou.updateMode.Manual)
    own=hou.node('/obj').createNode('subnet',node_name={name!r},run_init_scripts=False)
    state['owned_nodes'].append((own,own.sessionId()))
    own.setDisplayFlag(False)
result={{'owned_created':True,'manual':hou.updateModeSetting()==hou.updateMode.Manual}}
'''
                    report['setup'] = await call('OWNED_SETUP', setup)
                    destination = output / 'refine_474.json'; assert not destination.exists()
                    cache = WAVE / 'Runs' / plan['baseline_run'] / 'Cache'
                    paths = {'raw': str(cache / plan['record']['pilot']['filename']), 'original_mesh': str(cache / plan['record']['mesh']['filename']),
                             'mesh_output': str(output / 'Cache/refine_474.bgeo.sc'), 'progress': str(output / 'refine_474_progress.json'),
                             'baseline_replay': str(ROOT / plan['baseline_successes']['474']['raw']['path'])}
                    values = {'PATHS': paths, 'PLAN': plan, 'DESTINATION': str(destination), 'SOURCE_SHA': source_sha, 'PLAN_SHA': plan_sha}
                    ack = await call('K474_QUARTER_MESH', probe_rpc(source, values))
                    assert ack['source_sha256'] == source_sha and sha(destination) == ack['json_sha256']
                    result = json.loads(destination.read_bytes())
                    assert result['combined_source_sha256'] == source_sha and result['plan_sha256'] == plan_sha
                    report['result'] = {'file': destination.name, 'sha256': sha(destination), 'bytes': destination.stat().st_size,
                                        'passed': result['passed'], 'failure_phase': result.get('failure_phase'), 'mesh_output': result.get('mesh_output'),
                                        'nonfinite_observation_paths': result.get('nonfinite_observation_paths', [])}
                    assert not result.get('nonfinite_observation_paths') and result.get('passed_for_next', True) is True, '非有限観測の後続処理禁止'
                    assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) <= plan['budgets']['auxiliary_reserved_bytes'], '今回の補助出力予算'
                    assert destination.stat().st_size <= plan['budgets']['maximum_report_bytes'], '診断JSON容量保護'
                except Exception as exc:
                    report['failure_type'] = type(exc).__name__
                finally:
                    if snapshot_attempted and not uncertain:
                        try:
                            cleanup = 'with hou.undos.disabler():\n' + '\n'.join('    ' + line for line in guard.CLEANUP.splitlines())
                            report['cleanup'] = await call('RESTORE_UI18', cleanup)
                        except Exception as exc: report['cleanup_failure_type'] = type(exc).__name__
                    report['transport_completion_uncertain'] = uncertain
                    report['meshing_and_cleanup_passed'] = report.get('result', {}).get('passed', False) and not report.get('failure_type') and report.get('cleanup', {}).get('all_ui_and_owned_node_checks_passed', False)
                    if uncertain: report['recovery_required_ja'] = '完了不明。再要求・kill・並行cleanupを行わずrootへ報告する。'
                    write(report_path, report)
                if report.get('meshing_and_cleanup_passed') and not uncertain:
                    # 所有ノードの復元後だけ、旧→新の順で完全な195断面を読む。
                    reader_source = '\n'.join((output / 'Source' / name).read_text(encoding='utf8') for name in
                                               ('replay_support06.py', 'profile_core.py', 'read_profile05.py'))
                    reader_sha = hashlib.sha256(reader_source.encode('utf8')).hexdigest()
                    profile_plan = {'gauge_x_m': plan['gauge_x_m'], 'intersection': plan['intersection'],
                                    'budgets': {'per_pair_cooperative_seconds': plan['budgets']['per_rpc_cooperative_seconds'],
                                                'minimum_available_RAM_bytes': plan['budgets']['minimum_available_RAM_bytes']}}
                    report['profiles'] = {}; old_profile = None
                    try:
                        for label in ('old', 'new'):
                            mesh_path = cache / plan['record']['mesh']['filename'] if label == 'old' else output / 'Cache/refine_474.bgeo.sc'
                            pinned_mesh_sha = plan['record']['mesh']['sha256'] if label == 'old' else result['mesh_output']['sha256']
                            assert sha(mesh_path) == pinned_mesh_sha, '断面前の面SHA変化'
                            counts = {'points': plan['record']['mesh_points'], 'faces': plan['record']['mesh_faces']} if label == 'old' else result['replay_mesh_counts']
                            expected = {'sample': 474, 'mesh_sha256': pinned_mesh_sha, 'solver_sha256': plan['record']['pilot']['sha256'],
                                        'mesh_points': counts['points'], 'mesh_faces': counts['faces'], 'gauges': plan['record']['gauges']}
                            destination = output / ('profiles_' + label + '_474.json')
                            values = {'MESH_PATH': str(mesh_path), 'SOLVER_PATH': str(cache / plan['record']['pilot']['filename']),
                                      'EXPECTED': expected, 'PROFILE_PLAN': profile_plan, 'DESTINATION': str(destination),
                                      'SOURCE_SHA': reader_sha, 'PLAN_SHA': plan_sha, 'PROFILE_LIMITS': plan['budgets'],
                                      'BASE_PRIVATE': result['resources'][0]['private_bytes'], 'OUTPUT_ROOT': str(output)}
                            ack = await call('READ_ONLY_PROFILE_' + label.upper(), profile_rpc06(reader_source, values))
                            report['profiles'][label] = {'ack': ack}; write(report_path, report)
                            assert ack.get('json_written', True) is True, '断面容量HOLD・完全JSONなし'
                            assert sha(destination) == ack['json_sha256'] and ack['source_sha256'] == reader_sha
                            profile = json.loads(destination.read_bytes())
                            item = {'file': destination.name, 'sha256': sha(destination), 'bytes': destination.stat().st_size}
                            report['profiles'][label] = item; write(report_path, report)
                            assert profile['combined_reader_sha256'] == reader_sha and profile['plan_sha256'] == plan_sha
                            assert profile['input_sha_after'] == {'mesh': expected['mesh_sha256'], 'solver': expected['solver_sha256']}
                            assert profile['completed_readback'] and profile['metadata_unchanged'] and not profile.get('nonfinite_observation_paths')
                            assert destination.stat().st_size <= plan['budgets']['maximum_profile_bytes']
                            assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) <= plan['budgets']['auxiliary_reserved_bytes']
                            item['acceptance'] = profile_shape06(profile, old_profile)
                            if label == 'old':
                                item['published05_pair'] = compare_profile05_07(published_old_profile, profile)
                                if not item['published05_pair']['passed']:
                                    item['acceptance']['passed'] = False
                                    item['acceptance']['hold_reasons'].append([None, 'PUBLISHED05_OLD_PROFILE_MISMATCH'])
                            item['center_parity_role'] = 'OLD_ORIGINAL_PARITY' if label == 'old' else 'DIFFERENCE_ONLY_MESH_PARITY_NOT_REQUIRED'
                            write(report_path, report)
                            if not item['acceptance']['passed']:
                                report['hold_reason_ja'] = '局所断面の数値/形状審査を保留する。solver失敗や物理合否とは区別する。'
                                break
                            if label == 'old': old_profile = profile
                        report['passed_for_review'] = len(report['profiles']) == 2 and all(x.get('acceptance', {}).get('passed') is True for x in report['profiles'].values())
                    except Exception as exc:
                        report['profile_failure_type'] = type(exc).__name__; report['passed_for_review'] = False
                    finally:
                        report['transport_completion_uncertain'] = uncertain
                        if uncertain: report['recovery_required_ja'] = '断面RPCの完了不明。追加要求・retry・killを行わない。UI18は先に完了している。'
                        write(report_path, report)
    print(json.dumps({'output': str(output), 'passed_for_review': report['passed_for_review'], 'uncertain': uncertain}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--execute-reviewed-k474-quarter-mesh', action='store_true')
    args = parser.parse_args()
    if args.execute_reviewed_k474_quarter_mesh: asyncio.run(execute())
    else: print(json.dumps({'houdini_called': False, 'sample': 474, 'scope': 'ONE_K474_QUARTER_MESH_SENSITIVITY_ONLY', 'houdini_execution_allowed_by_default': False, 'refinement_allowed': True}, ensure_ascii=False))
