"""063フレーム先導の候補runner。既定は表示のみ、拡張142フレームの実行機能はない。"""
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

from sensitivity_core import allow_next, classify_rpc_reply, schedule

CANDIDATE = Path(__file__).resolve().parents[1]
WAVE = CANDIDATE.parents[1]
BASE = WAVE / 'Candidates/WaveStart04/Evidence/Result_22e7801642'
P05 = WAVE / 'Candidates/PfsDiagnosis05/Source'
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def check_frozen():
    plan_path = CANDIDATE / 'Source/pfs06_plan.json'
    plan = json.loads(plan_path.read_bytes())
    report = json.loads((CANDIDATE / 'Evidence/22_pfs06_offline_checks.json').read_bytes())
    assert report['passed'] and report['houdini_called'] is False
    assert all(sha(CANDIDATE / 'Source' / name) == value for name, value in report['source_hashes'].items())
    assert all(sha(BASE / name) == value for name, value in plan['baseline_files'].items())
    assert all(sha(P05 / name) == value for name, value in plan['profile05_dependencies'].items())
    assert plan['pilot_samples'] == [360, 474, 496] and plan['extension_implemented'] is False
    cache = WAVE / 'Runs' / plan['baseline_run'] / 'Cache'
    for k in plan['pilot_samples']:
        entry = next(r for r in plan['records'] if r['sample'] == k)
        for kind in ('pilot', 'mesh'):
            path = cache / entry[kind]['filename']
            assert path.stat().st_size == entry[kind]['bytes'] and sha(path) == entry[kind]['sha256']
    return plan


def combined_source(sources):
    return '\n'.join(sources[name] for name in ('profile_core.py', 'read_profile05.py', 'sensitivity_core.py', 'remesh_pilot06.py'))


def stage_code(source, parameters):
    """各RPCが単独namespaceで完結し、ACKは原JSON/sourceのSHAだけを返す。"""
    prefix = 'import os\n'
    prefix += '\n'.join(f'{key}={value!r}' for key, value in parameters.items()) + '\n'
    prefix += 'assert os.getpid()==PID and hou.isUIAvailable() and hou.fps()==24\n'
    body = '''
prior=None
if PRIOR_PATH is not None:
    assert file_sha(Path(PRIOR_PATH))==PRIOR_SHA
    prior=json.loads(Path(PRIOR_PATH).read_bytes())
with hou.undos.disabler():
    record=remesh_one06(hou,KEY,OBJ_PATH,STAGE,EXPECTED,PLAN,PATHS,prior,BASE_PRIVATE,PREVIOUS_COOKS)
record=serializable_observation(record)
record['combined_source_sha256']=SOURCE_SHA
record['plan_sha256']=PLAN_SHA
destination=Path(DESTINATION)
assert not destination.exists()
payload=(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
destination.write_bytes(payload)
result={'json_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':SOURCE_SHA}
'''
    return prefix + source + '\n' + body


async def execute():
    # 条件/証拠不一致はMCPを読み込む前に拒否する。
    plan = check_frozen()
    assert shutil.disk_usage(WAVE.anchor).free >= plan['budgets']['start_minimum_free_G_bytes']
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    token = 'pfs06_' + uuid.uuid4().hex[:10]
    output = WAVE / 'Runs' / token
    output.mkdir(exist_ok=False)
    (output / 'Source').mkdir(); (output / 'Cache').mkdir()
    source_files = {p.name: p for p in (CANDIDATE / 'Source').iterdir() if p.is_file()}
    source_files.update({name: P05 / name for name in plan['profile05_dependencies']})
    source_files['ui_guard.py'] = BASE / 'Executed_Source/ui_guard.py'
    for name, path in source_files.items(): (output / 'Source' / name).write_bytes(path.read_bytes())
    spec = importlib.util.spec_from_file_location('owned_guard06', output / 'Source/ui_guard.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    source = combined_source({name: (output / 'Source' / name).read_text(encoding='utf8') for name in source_files if name.endswith('.py')})
    source_sha = hashlib.sha256(source.encode('utf8')).hexdigest()
    plan_sha = sha(output / 'Source/pfs06_plan.json')
    name = 'gw22_' + token; key = '_' + name
    report = {'token': token, 'baseline_run': plan['baseline_run'], 'events': [], 'stages': [],
              'source_hashes': {name: sha(output / 'Source' / name) for name in source_files},
              'plan_sha256': plan_sha, 'combined_source_sha256': source_sha,
              'new_solver_executed': False, 'detector_executed': False, 'extension_started': False}
    report_path = output / 'execution.json'
    snapshot_attempted = False; uncertain = False; pid = None
    params = StdioServerParameters(command=PYTHON, args=['-m', 'fxhoudinimcp'],
                                   env={'HOUDINI_HOST': '127.0.0.1', 'HOUDINI_PORT': '8100', 'MCP_TRANSPORT': 'stdio',
                                        'LOG_LEVEL': 'ERROR', 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    with (output / 'proxy.log').open('w', encoding='utf8') as log:
        async with stdio_client(params, errlog=log) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=plan['budgets']['rpc_wait_seconds'])) as client:
                await client.initialize()
                async def call(label, code, metadata=False):
                    nonlocal uncertain
                    assert not uncertain
                    prefix = f'KEY={key!r}\nOBJ_PATH={"/obj/"+name!r}\n'
                    if not metadata: prefix += f'import os\nassert os.getpid()=={pid} and hou.isUIAvailable()\n'
                    started = time.monotonic()
                    try:
                        response = await client.call_tool('execute_python', {'code': prefix + code, 'return_expression': 'result',
                            'justification': '審査済み06の既存粒子面化だけ。新DOP/solverなし、所有SOPとUI18復元。' + label})
                    except Exception:
                        uncertain = True
                        raise
                    text_block = None
                    try:
                        text_block = next((c.text for c in response.content if c.type == 'text'), None)
                        status, data = classify_rpc_reply(text_block, response.isError)
                    except Exception:
                        status, data = 'UNCERTAIN', None
                    if status == 'UNCERTAIN': uncertain = True
                    report['events'].append({'stage': label, 'rpc_seconds': time.monotonic() - started,
                                              'completion_class': status, 'raw_response_text_local': text_block,
                                              'executed': data.get('executed') if isinstance(data, dict) else None,
                                              'error': data.get('error') if isinstance(data, dict) else None,
                                              'eval_error': data.get('eval_error') if isinstance(data, dict) else None})
                    write(report_path, report)
                    assert status == 'COMPLETE_SUCCESS', 'RPC失敗または完了不明'
                    return data['return_value']
                try:
                    meta = await call('METADATA', "import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'license':str(hou.licenseCategory()),'ui':hou.isUIAvailable(),'fps':hou.fps()}", True)
                    assert meta['version'] == '22.0.429' and meta['license'] == 'licenseCategoryType.Indie' and meta['ui'] and meta['fps'] == 24
                    report['metadata'] = meta; pid = meta['pid']
                    snapshot_attempted = True
                    report['snapshot'] = await call('SNAPSHOT', guard.SNAPSHOT)
                    setup = source + f'''
with hou.undos.disabler():
    state=getattr(hou.session,KEY)
    hou.setUpdateMode(hou.updateMode.Manual)
    assert hou.fps()==24 and hou.updateModeSetting()==hou.updateMode.Manual
    own=hou.node('/obj').createNode('subnet',node_name={name!r},run_init_scripts=False)
    state['owned_nodes'].append((own,own.sessionId()))
    own.setDisplayFlag(False)
    resource=memory06({WAVE.anchor!r})
    output=Path({str(output / 'initial_resource.json')!r})
    payload=(json.dumps(resource,indent=2)+'\\n').encode('utf8');output.write_bytes(payload)
result={{'json_sha256':hashlib.sha256(payload).hexdigest()}}
'''
                    ack = await call('OWNED_SETUP', setup)
                    initial = output / 'initial_resource.json'
                    assert sha(initial) == ack['json_sha256']
                    resource = json.loads(initial.read_bytes()); report['initial_resource'] = resource
                    completed = []; cooks = []; total = 0.
                    for stage, k in schedule(plan):
                        assert allow_next(completed, (stage, k), plan), '先導順序または配対判定違反'
                        assert total + plan['budgets']['per_rpc_cooperative_seconds'] <= plan['budgets']['pilot_cumulative_seconds']
                        entry = next(r for r in plan['records'] if r['sample'] == k)
                        raw_cache = WAVE / 'Runs' / plan['baseline_run'] / 'Cache'
                        destination = output / f'{stage}_{k:03d}.json'
                        prior_path = output / f'replay_{k:03d}.json' if stage == 'refine' else None
                        paths = {'raw': str(raw_cache / entry['pilot']['filename']), 'original_mesh': str(raw_cache / entry['mesh']['filename']),
                                 'mesh_output': str(output / 'Cache' / f'{stage}_{k:03d}.bgeo.sc')}
                        parameters = {'PID': pid, 'KEY': key, 'OBJ_PATH': '/obj/' + name, 'STAGE': stage, 'EXPECTED': entry,
                                      'PLAN': plan, 'PATHS': paths, 'PRIOR_PATH': str(prior_path) if prior_path else None,
                                      'PRIOR_SHA': sha(prior_path) if prior_path else None, 'BASE_PRIVATE': resource['private_bytes'],
                                      'PREVIOUS_COOKS': cooks, 'SOURCE_SHA': source_sha, 'PLAN_SHA': plan_sha, 'DESTINATION': str(destination)}
                        ack = await call(stage.upper() + '_' + str(k), stage_code(source, parameters))
                        assert ack['source_sha256'] == source_sha and sha(destination) == ack['json_sha256']
                        original = json.loads(destination.read_bytes())
                        assert original['combined_source_sha256'] == source_sha and original['plan_sha256'] == plan_sha
                        total += original['total_seconds']; cooks += original.get('cook_seconds_list', [])
                        event = {'stage': stage, 'sample': k, 'passed_for_next': original['passed_for_next'],
                                 'result_file': destination.name, 'result_sha256': sha(destination), 'result_bytes': destination.stat().st_size,
                                 'total_seconds': original['total_seconds'], 'mesh_output': original.get('mesh_output')}
                        completed.append(event); report['stages'].append(event)
                        # 64MiB予備には旧.5三面・JSON・実行元を含む。新.25面は16MiB×142の別枠。
                        auxiliary_bytes = sum(p.stat().st_size for p in output.rglob('*')
                                              if p.is_file() and not (p.parent.name == 'Cache' and p.name.startswith('refine_')))
                        assert auxiliary_bytes <= plan['budgets']['auxiliary_reserved_bytes'], '補助記録の容量予算'
                        write(report_path, report)
                        print(json.dumps(event, ensure_ascii=False), flush=True)
                        if not original['passed_for_next']:
                            report['review_hold'] = True
                            break
                    report['all_six_completed'] = len(completed) == 6 and all(r['passed_for_next'] for r in completed)
                except Exception as exc:
                    report['failure_type'] = type(exc).__name__
                finally:
                    if snapshot_attempted and not uncertain:
                        try:
                            cleanup = 'with hou.undos.disabler():\n' + '\n'.join('    ' + line for line in guard.CLEANUP.splitlines())
                            report['cleanup'] = await call('RESTORE_UI18', cleanup)
                        except Exception as exc: report['cleanup_failure_type'] = type(exc).__name__
                    report['transport_completion_uncertain'] = uncertain
                    report['passed_for_review'] = report.get('all_six_completed', False) and not report.get('failure_type') and report.get('cleanup', {}).get('all_ui_and_owned_node_checks_passed', False)
                    if uncertain: report['recovery_required_ja'] = '完了不明。追加RPC・kill・並行cleanupを行わずrootへ報告する。'
                    write(report_path, report)
    print(json.dumps({'output': str(output), 'passed_for_review': report['passed_for_review'], 'uncertain': uncertain}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-reviewed-three-frame-pilot', action='store_true')
    args = parser.parse_args()
    if args.execute_reviewed_three_frame_pilot: asyncio.run(execute())
    else:
        plan = json.loads((CANDIDATE / 'Source/pfs06_plan.json').read_bytes())
        print(json.dumps({'houdini_called': False, 'stage_order': schedule(plan), 'extension_implemented': False,
                          'meaning_ja': '表示のみ。rootの実行放行前に実行flagを指定しない。'}, ensure_ascii=False))
