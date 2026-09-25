"""既定は計画表示。審査後の1回だけFile→Null診断を実行する。"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path
from support06 import classify_rpc_reply

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = CANDIDATE.parents[3]
WAVE = CANDIDATE.parents[1]
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
GUARD = 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Executed_Source/ui_guard.py'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def validate_frozen():
    plan = json.loads((CANDIDATE / 'Source/file_probe_plan.json').read_bytes())
    report = json.loads((CANDIDATE / 'Evidence/22_file_probe_offline_checks.json').read_bytes())
    assert report['passed'] and not report['houdini_called']
    assert all(sha(CANDIDATE / 'Source' / name) == expected for name, expected in report['source_hashes'].items())
    assert all(sha(ROOT / name) == expected for name, expected in plan['fixed_evidence'].items())
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in plan['support_origins'])
    assert plan['scope'] == 'FILE_NULL_K360_ONLY' and plan['sample'] == 360
    raw = WAVE / 'Runs' / plan['baseline_run'] / 'Cache' / plan['input']['filename']
    assert sha(raw) == plan['input']['sha256'] and raw.stat().st_size == plan['input']['bytes']
    return plan, raw


def probe_rpc(source, values):
    prefix = '\n'.join(f'{k}={v!r}' for k, v in values.items()) + '\n'
    return prefix + source + '''
with hou.undos.disabler():
    observed=probe_file06(hou,KEY,OBJ_PATH,RAW_PATH,PLAN,DESTINATION)
observed['combined_source_sha256']=SOURCE_SHA
observed['plan_sha256']=PLAN_SHA
payload=(json.dumps(serializable_observation(observed),ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode('utf8')
Path(DESTINATION).write_bytes(payload)
result={'json_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':SOURCE_SHA}
'''


async def execute():
    plan, raw = validate_frozen()
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    token = 'file06_' + uuid.uuid4().hex[:10]
    output = WAVE / 'Runs' / token; output.mkdir(exist_ok=False); (output / 'Source').mkdir()
    for path in (CANDIDATE / 'Source').iterdir():
        if path.is_file(): (output / 'Source' / path.name).write_bytes(path.read_bytes())
    (output / 'Source/ui_guard.py').write_bytes((ROOT / GUARD).read_bytes())
    spec = importlib.util.spec_from_file_location('guard_file06', output / 'Source/ui_guard.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    source = '\n'.join((output / 'Source' / name).read_text(encoding='utf8') for name in ('support06.py', 'probe_file06.py'))
    source_sha = hashlib.sha256(source.encode('utf8')).hexdigest(); plan_sha = sha(output / 'Source/file_probe_plan.json')
    name = 'gw22_' + token; key = '_' + name
    report = {'token': token, 'scope': plan['scope'], 'source_hashes': {p.name: sha(p) for p in (output / 'Source').iterdir()},
              'events': [], 'new_meshing': False, 'new_solver': False, 'combined_source_sha256': source_sha, 'plan_sha256': plan_sha}
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
                            'justification': '審査済みk360保存粒子のFile/Nullだけ。PFS/DOPなし、短い更新mode比較とUI18復元。' + label})
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
                    destination = output / 'file_probe_360.json'; assert not destination.exists()
                    values = {'RAW_PATH': str(raw), 'PLAN': plan, 'DESTINATION': str(destination), 'SOURCE_SHA': source_sha, 'PLAN_SHA': plan_sha}
                    ack = await call('FILE_NULL_DIAGNOSTIC', probe_rpc(source, values))
                    assert ack['source_sha256'] == source_sha and sha(destination) == ack['json_sha256']
                    result = json.loads(destination.read_bytes())
                    assert result['combined_source_sha256'] == source_sha and result['plan_sha256'] == plan_sha
                    report['result'] = {'file': destination.name, 'sha256': sha(destination), 'bytes': destination.stat().st_size,
                                        'passed': result['passed'], 'failure_phase': result.get('failure_phase')}
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
    parser = argparse.ArgumentParser(); parser.add_argument('--execute-reviewed-file-only-diagnostic', action='store_true')
    args = parser.parse_args()
    if args.execute_reviewed_file_only_diagnostic: asyncio.run(execute())
    else: print(json.dumps({'houdini_called': False, 'sample': 360, 'scope': 'FILE_NULL_K360_ONLY', 'new_meshing': False}, ensure_ascii=False))
