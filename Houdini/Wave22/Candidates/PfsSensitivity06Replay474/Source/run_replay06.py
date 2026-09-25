"""既定は表示だけ。明示放行後もk474旧.5面化を一回だけ実行する。"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path
from replay_support06 import classify_rpc_reply

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = CANDIDATE.parents[3]
WAVE = CANDIDATE.parents[1]
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
GUARD = 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Executed_Source/ui_guard.py'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def validate_frozen():
    plan = json.loads((CANDIDATE / 'Source/replay_plan.json').read_bytes())
    report = json.loads((CANDIDATE / 'Evidence/22_replay_offline_checks.json').read_bytes())
    freeze_path = CANDIDATE / 'Evidence/22_replay_candidate_freeze.json'
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
    actual_prior = {p.relative_to(ROOT).as_posix() for d in prior['protected_directories'] for p in (ROOT / d).rglob('*') if p.is_file()}
    assert actual_prior == {r['path'] for r in prior['files']}
    assert len(actual_prior) == prior['file_count'] and sum(r['bytes'] for r in prior['files']) == prior['total_bytes']
    for row in (plan['decision_freeze'], plan['decision_report']):
        assert (ROOT / row['path']).stat().st_size == row['bytes'] and sha(ROOT / row['path']) == row['sha256']
    assert all(sha(ROOT / r['path']) == r['sha256'] for r in plan['support_origins'])
    baseline = WAVE / 'Candidates/WaveStart04/Evidence/Result_22e7801642'
    assert all(sha(baseline / name) == expected for name, expected in plan['baseline_files'].items())
    assert plan['scope'] == 'ONE_K474_OLD_HALF_PFS_REPLAY_ONLY' and plan['sample'] == 474
    assert plan['global_frame'] == 1 + (474 / 60) * 24 and plan['fps'] == 24 and plan['mesh_parameters']['voxelsize'] == .5
    assert plan['refinement_allowed'] is False and plan['other_samples_allowed'] is False
    for kind in ('pilot', 'mesh'):
        row = plan['record'][kind]
        path = WAVE / 'Runs' / plan['baseline_run'] / 'Cache' / row['filename']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    return plan


def probe_rpc(source, values):
    prefix = '\n'.join(f'{k}={v!r}' for k, v in values.items()) + '\n'
    return prefix + source + '''
with hou.undos.disabler():
    observed=replay_k474(hou,KEY,OBJ_PATH,PLAN,PATHS)
observed['combined_source_sha256']=SOURCE_SHA
observed['plan_sha256']=PLAN_SHA
payload=(json.dumps(serializable_observation(observed),ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
Path(DESTINATION).write_bytes(payload)
result={'json_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':SOURCE_SHA}
'''


async def execute():
    plan = validate_frozen()
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    token = 'pfsreplay06_' + uuid.uuid4().hex[:10]
    output = WAVE / 'Runs' / token; output.mkdir(exist_ok=False); (output / 'Source').mkdir(); (output / 'Cache').mkdir()
    for path in (CANDIDATE / 'Source').iterdir():
        if path.is_file(): (output / 'Source' / path.name).write_bytes(path.read_bytes())
    (output / 'Source/ui_guard.py').write_bytes((ROOT / GUARD).read_bytes())
    spec = importlib.util.spec_from_file_location('guard_file06', output / 'Source/ui_guard.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    source = '\n'.join((output / 'Source' / name).read_text(encoding='utf8') for name in ('replay_support06.py', 'replay_window06.py', 'replay_k474.py'))
    source_sha = hashlib.sha256(source.encode('utf8')).hexdigest(); plan_sha = sha(output / 'Source/replay_plan.json')
    name = 'gw22_' + token; key = '_' + name
    report = {'token': token, 'scope': plan['scope'], 'source_hashes': {p.name: sha(p) for p in (output / 'Source').iterdir()},
              'events': [], 'new_meshing_planned': True, 'new_solver': False, 'refinement_planned': False, 'combined_source_sha256': source_sha, 'plan_sha256': plan_sha}
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
                            'justification': '審査済みk474旧.5面化だけ。入力判定後の二つの短い更新窓、DOPなし、UI18復元。' + label})
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
                    destination = output / 'replay_474.json'; assert not destination.exists()
                    cache = WAVE / 'Runs' / plan['baseline_run'] / 'Cache'
                    paths = {'raw': str(cache / plan['record']['pilot']['filename']), 'original_mesh': str(cache / plan['record']['mesh']['filename']),
                             'mesh_output': str(output / 'Cache/replay_474.bgeo.sc'), 'progress': str(output / 'replay_474_progress.json')}
                    values = {'PATHS': paths, 'PLAN': plan, 'DESTINATION': str(destination), 'SOURCE_SHA': source_sha, 'PLAN_SHA': plan_sha}
                    ack = await call('K474_OLD_HALF_REPLAY', probe_rpc(source, values))
                    assert ack['source_sha256'] == source_sha and sha(destination) == ack['json_sha256']
                    result = json.loads(destination.read_bytes())
                    assert result['combined_source_sha256'] == source_sha and result['plan_sha256'] == plan_sha
                    report['result'] = {'file': destination.name, 'sha256': sha(destination), 'bytes': destination.stat().st_size,
                                        'passed': result['passed'], 'failure_phase': result.get('failure_phase'), 'mesh_output': result.get('mesh_output')}
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
                    report['passed_for_review'] = report.get('result', {}).get('passed', False) and not report.get('failure_type') and report.get('cleanup', {}).get('all_ui_and_owned_node_checks_passed', False)
                    if uncertain: report['recovery_required_ja'] = '完了不明。再要求・kill・並行cleanupを行わずrootへ報告する。'
                    write(report_path, report)
    print(json.dumps({'output': str(output), 'passed_for_review': report['passed_for_review'], 'uncertain': uncertain}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--execute-reviewed-k474-old-half-replay', action='store_true')
    args = parser.parse_args()
    if args.execute_reviewed_k474_old_half_replay: asyncio.run(execute())
    else: print(json.dumps({'houdini_called': False, 'sample': 474, 'scope': 'ONE_K474_OLD_HALF_PFS_REPLAY_ONLY', 'houdini_execution_allowed_by_default': False, 'refinement_allowed': False}, ensure_ascii=False))
