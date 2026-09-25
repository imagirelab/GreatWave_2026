"""22 L6感度候補：格子観測と健康点後、元t6判定PASS時だけ同DOPで駆動する。"""
import argparse
import asyncio
import hashlib
import json
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from checkpoint_gate import evaluate_gate, run_phases

ROOT = Path(__file__).resolve().parents[1]
PYTHON = r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))


def read_exact_record(path, acknowledgment, source_sha):
    """MCPの数値丸めを避け、Houdiniで保存・hash化されたJSONのbytesを読む。"""
    assert acknowledgment['source_sha256'] == source_sha
    assert sha(path) == acknowledgment['json_sha256']
    return json.loads(path.read_text(encoding='utf8'))


async def execute_reviewed_plan():
    # 既存の公開済みSource・条件・図表を上書きしない。
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import ui_guard
    plan_path = ROOT / 'Source/length6_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf8'))
    assert plan['piston_start_seconds'] == 6 and plan['observation_end_seconds'] == 9.5
    assert plan['sample_rate_hz'] == 60 and plan['mesh_stride'] == 2
    assert (plan['particle_separation_m'], plan['grid_scale'], plan['gravity_m_s2']) == (.04, 1.5, 9.81)
    static_last, final_last = 360, 570
    reference = ROOT / 'Runs' / plan['reference_case'] / 'Cache/pilot_001.bgeo.sc'
    reference_rows_path = ROOT / 'Evidence/Curated_Runs' / plan['reference_case'] / '22_pilot_samples.json'
    reference_conditions_path = reference_rows_path.with_name('22_pilot_conditions.json')
    reference_rows = json.loads(reference_rows_path.read_text(encoding='utf8'))['samples']
    assert reference.is_file() and sha(reference) == reference_rows[1]['cache_sha256']
    expected_conditions = json.loads(reference_conditions_path.read_text(encoding='utf8'))
    budget = plan['resource_budget']
    predicted = (final_last + 1) * budget['predicted_raw_bytes_per_sample'] + budget['grid_probe_reserved_bytes']
    free = shutil.disk_usage(ROOT).free
    assert free >= 2 * predicted + budget['minimum_disk_free_bytes'], '開始前のディスク余裕不足'
    token = uuid.uuid4().hex[:10]
    name, key = 'gw22_length6_' + token, '_gw22_length6_' + token
    object_path = '/obj/' + name
    output = ROOT / 'Runs' / token
    for folder in ('Cache', 'Evidence', 'Source'):
        (output / folder).mkdir(parents=True, exist_ok=False)
    source_names = ('run_length6.py', 'checkpoint_gate.py', 'length6_plan.json', 'generate_wave_l6.py', 'ui_guard.py', 'grid_metrics_l6.py', 'probe_grid_l6.py')
    for filename in source_names:
        (output / 'Source' / filename).write_bytes((ROOT / 'Source' / filename).read_bytes())
    source = (output / 'Source/generate_wave_l6.py').read_text(encoding='utf8')
    assert hashlib.sha256(source.encode('utf8')).hexdigest() == sha(output / 'Source/generate_wave_l6.py')
    policy = (output / 'Source/checkpoint_gate.py').read_text(encoding='utf8')
    probe_code = (output / 'Source/grid_metrics_l6.py').read_text(encoding='utf8') + '\n' + (output / 'Source/probe_grid_l6.py').read_text(encoding='utf8')
    probe_code_sha = hashlib.sha256(probe_code.encode('utf8')).hexdigest()
    report_path = output / 'Evidence/22_checkpoint_execution.json'
    report = {'token': token, 'utc': datetime.now(timezone.utc).isoformat(), 'plan': plan,
              'owned_path': object_path, 'events': [], 'wave_verified': False,
              'source_hashes': {n: sha(output / 'Source' / n) for n in source_names},
              'grid_probe_code_sha256': probe_code_sha,
              'reference_hashes': {'old_grid_cache_sample1': sha(reference), 'samples': sha(reference_rows_path),
                                   'conditions': sha(reference_conditions_path)},
              'predicted_raw_bytes': predicted, 'free_disk_before_bytes': free}
    expected_pid = None
    uncertain = False
    snapshot = False
    rows = []

    def save():
        write(report_path, report)

    def constants(phase):
        values = {'NAME': name, 'KEY': key, 'OBJ_PATH': object_path, 'EXPECTED_PID': expected_pid,
                  'STAGE': str(output), 'PHASE': phase, 'GRAVITY': 9.81, 'RESEEDING': True,
                  'OLD_GRID_CACHE': str(reference), 'OLD_GRID_CACHE_SHA': sha(reference),
                  'OLD_LENGTH': expected_conditions['tank_inner_m'][0], 'GRID_PLAN': plan, 'PISTON_ENABLED': True,
                  'PARTICLE_SEPARATION': .04, 'GRID_SCALE': 1.5, 'PISTON_START_SECONDS': 6.0,
                  'MESH_STRIDE': 2, 'THREE_GAUGES': True, 'BUDGET': budget,
                  'STATIC_LAST': static_last, 'FINAL_LAST': final_last}
        return '\n'.join(f'{k}={v!r}' for k, v in values.items()) + '\n'

    params = StdioServerParameters(command=PYTHON, args=['-m', 'fxhoudinimcp'],
                                  env={'HOUDINI_HOST': '127.0.0.1', 'HOUDINI_PORT': '8100',
                                       'MCP_TRANSPORT': 'stdio', 'LOG_LEVEL': 'ERROR',
                                       'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    with (output / 'Evidence/proxy.log').open('w', encoding='utf8') as err:
        async with stdio_client(params, errlog=err) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()

                async def execute(label, code, phase='', metadata_only=False):
                    nonlocal uncertain
                    assert not uncertain, '未完了の可能性があるRPCへ並行要求を送らない'
                    prefix = '' if metadata_only else constants(phase) + 'import os\nassert os.getpid()==EXPECTED_PID and hou.isUIAvailable() and hou.fps()==24\n'
                    started = time.monotonic()
                    try:
                        response = await client.call_tool('execute_python',
                            {'code': prefix + code, 'return_expression': 'result',
                             'justification': '22改訂の所有水槽のみ。固定t6開始判定、不合格で駆動禁止。' + label})
                    except Exception:
                        # タイムアウトはHoudiniの中断完了を意味しない。二重作成・並行cleanup・GUI killを禁止。
                        uncertain = True
                        raise
                    data = json.loads(next(c.text for c in response.content if c.type == 'text'))
                    report['events'].append({'phase': label, 'rpc_wall_seconds': time.monotonic() - started,
                                             'executed': data.get('executed'), 'error': data.get('error'),
                                             'eval_error': data.get('eval_error')})
                    save()
                    assert not response.isError and data.get('executed') and not data.get('error') and not data.get('eval_error'), data
                    return data['return_value']

                try:
                    report['metadata'] = await execute('接続先の現metadataのみ',
                        "import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'ui':hou.isUIAvailable(),'license':str(hou.licenseCategory()),'fps':hou.fps()}\n",
                        metadata_only=True)
                    meta = report['metadata']
                    assert meta['ui'] and meta['version'] == '22.0.429' and meta['license'] == 'licenseCategoryType.Indie' and meta['fps'] == 24
                    expected_pid = meta['pid']
                    report['snapshot'] = await execute('UI保存', ui_guard.SNAPSHOT)
                    snapshot = True
                    report['clock_initialization'] = await execute('作成前に時刻を開始点へ限定',
                        "before=hou.frame()\nhou.setUpdateMode(hou.updateMode.Manual)\nhou.setFrame(1)\nassert hou.frame()==1\nresult={'frame_before':before,'frame_for_creation':hou.frame(),'fps':hou.fps(),'original_frame_will_be_restored':True}\n")
                    report['create_acknowledgment'] = await execute('新規t6固定ケース作成', source +
                        "\nresult={'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_conditions.json').read_bytes()).hexdigest(),"
                        f"'source_sha256':hashlib.sha256({source!r}.encode('utf8')).hexdigest()}}\n", 'create')
                    report['create'] = read_exact_record(output / 'Evidence/22_pilot_conditions.json',
                                                        report['create_acknowledgment'], report['source_hashes']['generate_wave_l6.py'])
                    conditions = report['create']
                    assert conditions['tank_inner_m'] == [6.0, .6, .6]
                    assert plan['tank_inner_length_m'] == 6.0 and plan['wavelength_m'] == 2.9903951732918226
                    for field in ('particle_separation_m', 'collision_pressure_voxel_expected_m',
                                  'display_voxel_m', 'piston_half_amplitude_m', 'piston_ramp_seconds',
                                  'solver_parameters', 'collision_parameters', 'velocity_transfer_token',
                                  'diagnostic_gauge_x_wavelengths', 'stability_gate'):
                        assert conditions[field] == expected_conditions[field], field
                    assert conditions['piston_start_absolute_seconds'] == 6
                    assert not conditions['boundary_flow_input_connected'] and conditions['mesh_sampling_hz'] == 30
                    report['ownership'] = await execute('同一DOPと資源基線を登録',
                        source + "\ns=getattr(hou.session,KEY)\ns['checkpoint_dop_id']=s['dop'].sessionId()\ns['checkpoint_drive_authorized']=False\ns['checkpoint_baseline_private']=memory()['private_commit_bytes']\ns['checkpoint_trace']=[]\nresult={'dop_session_id':s['checkpoint_dop_id'],'baseline_private_commit_bytes':s['checkpoint_baseline_private']}\n", 'register_checkpoint')
                    report['initialization_probe'] = await execute('所有初期化設定', source, 'initialization_probe')
                    async def grid_probe(phase):
                        # 毎RPCへ必要な定義を注入。数値は返却floatではなく原JSONから読む。
                        filename = '22_length6_old_grid.json' if phase == 'grid_old_reference' else '22_length6_grid_preflight.json'
                        acknowledgment = await execute('所有場の格子・壁観測 ' + phase,
                            source + '\n' + probe_code +
                            "\nresult={'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence'/" + repr(filename) + ").read_bytes()).hexdigest()," +
                            "'source_sha256':hashlib.sha256(" + repr(probe_code) + ".encode('utf8')).hexdigest()}\n", phase)
                        exact_grid = read_exact_record(output / 'Evidence' / filename, acknowledgment, probe_code_sha)
                        report[phase] = {'json_sha256': acknowledgment['json_sha256'], 'source_sha256': probe_code_sha}
                        save()
                        return exact_grid

                    await grid_probe('grid_old_reference')

                    async def sample_one(index):
                        wrapper = (
                            "import shutil\n" + policy + "\n"
                            "s=getattr(hou.session,KEY)\n"
                            "assert s['dop'].sessionId()==s['checkpoint_dop_id']\n"
                            f"assert len(s['samples'])=={index}\n"
                            f"assert {index}<=STATIC_LAST or s['checkpoint_drive_authorized']\n"
                            "assert s['dop'].evalParm('cachetodisk')==0 and s['dop'].evalParm('cachemaxsize')==768\n"
                            "assert s['dop'].evalParm('cachetodisknoninteractive')==0 and s['dop'].evalParm('explicitcache')==0\n"
                            "assert shutil.disk_usage(STAGE).free>=BUDGET['minimum_disk_free_bytes']\n"
                            f"exec(compile({source!r},'generate_wave_l6.py','exec'),globals())\n"
                            "assert s['dop'].sessionId()==s['checkpoint_dop_id']\n"
                            "resource=check_resources(s['samples'],BUDGET,s['checkpoint_baseline_private'],shutil.disk_usage(STAGE).free,FINAL_LAST)\n"
                            "s['checkpoint_trace'].append({'sample':result['sample'],'dop_session_id':s['dop'].sessionId(),'drive_authorized':s['checkpoint_drive_authorized'],'resource':resource})\n"
                            "write('22_checkpoint_trace.json',{'samples':s['checkpoint_trace']})\n"
                            "result={'sample':result['sample'],'json_sha256':hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_samples.json').read_bytes()).hexdigest(),"
                            f"'source_sha256':hashlib.sha256({source!r}.encode('utf8')).hexdigest()}}\n")
                        acknowledgment = await execute('実標本 ' + str(index), wrapper, 'sample:' + str(index))
                        exact = read_exact_record(output / 'Evidence/22_pilot_samples.json', acknowledgment,
                                                  report['source_hashes']['generate_wave_l6.py'])['samples']
                        assert len(exact) == index + 1 and acknowledgment['sample'] == index
                        row = exact[-1]
                        rows.append(row)
                        if index == 0:
                            await grid_probe('grid_new:0')
                            await grid_probe('grid_new:' + repr(1/120))
                        elif index == 1:
                            await grid_probe('grid_new:' + repr(1/60))
                        elif index == 30:
                            # 健康点は有限/壁/資源検査の通過だけ。静水や造波の許可ではない。
                            health = {'sample_count': len(rows), 'seconds': row['requested_seconds'],
                                      'resource_and_field_guards_passed': True, 'drive_authorized': False,
                                      'static_gate_evaluated': False, 'same_dop_session_id': report['ownership']['dop_session_id']}
                            write(output / 'Evidence/22_length6_health_checkpoint.json', health)
                            report['health_checkpoint'] = health
                            save()
                        if index % 30 == 0 or index in (static_last, final_last):
                            print(json.dumps({'token': token, 'sample': index, 'seconds': row['requested_seconds'],
                                              'particles': row['particle_count'], 'cook_seconds': row['cook_seconds'],
                                              'dop_bytes': row['simulation_memory_bytes']}, ensure_ascii=False), flush=True)

                    async def decide():
                        gate = evaluate_gate(rows, conditions, plan['piston_start_seconds'])
                        gate.update({'sample_sha256': sha(output / 'Evidence/22_pilot_samples.json'),
                                     'conditions_sha256': sha(output / 'Evidence/22_pilot_conditions.json'),
                                     'policy_sha256': sha(output / 'Source/checkpoint_gate.py')})
                        write(output / 'Evidence/22_checkpoint_gate.json', gate)
                        report['gate'] = gate
                        save()
                        print(json.dumps({'token': token, 'gate': gate}, ensure_ascii=False), flush=True)
                        return gate

                    async def authorize(gate):
                        assert gate['diagnostic_stability_passed'] and len(rows) == static_last + 1
                        # Houdini側でも同じ全標本・純関数を再判定する。パラメータや時計は変更しない。
                        report['drive_authorization'] = await execute('t6全条件合格後の同一DOP続行許可',
                            policy + "\nimport json\nfrom pathlib import Path\ns=getattr(hou.session,KEY)\n"
                            "assert s['dop'].sessionId()==s['checkpoint_dop_id']\n"
                            "assert len(s['samples'])==STATIC_LAST+1 and abs(s['dop'].simulation().time()-6)<1e-6\n"
                            "import hashlib\n"
                            f"assert hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_samples.json').read_bytes()).hexdigest()=={gate['sample_sha256']!r}\n"
                            f"assert hashlib.sha256((Path(STAGE)/'Evidence/22_pilot_conditions.json').read_bytes()).hexdigest()=={gate['conditions_sha256']!r}\n"
                            "assert json.loads((Path(STAGE)/'Evidence/22_pilot_samples.json').read_text(encoding='utf8'))['samples']==s['samples']\n"
                            "c=json.loads((Path(STAGE)/'Evidence/22_pilot_conditions.json').read_text(encoding='utf8'))\n"
                            "remote_gate=evaluate_gate(s['samples'],c,6.0)\n"
                            "assert remote_gate['diagnostic_stability_passed']\n"
                            "s['checkpoint_drive_authorized']=True\n"
                            "result={'authorized':True,'dop_session_id':s['dop'].sessionId(),'absolute_seconds':s['dop'].simulation().time(),'parameters_changed':False,'simulation_reset':False,"
                            f"'sample_sha256':{gate['sample_sha256']!r},'conditions_sha256':{gate['conditions_sha256']!r}}}\n")
                        save()

                    report['outcome'] = await run_phases(sample_one, decide, authorize, static_last, final_last)
                except Exception as exc:
                    report['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
                finally:
                    if snapshot and not uncertain:
                        try:
                            report['cleanup'] = await execute('所有物削除とUI復元', ui_guard.CLEANUP)
                        except Exception as exc:
                            report['cleanup_failure'] = {'type': type(exc).__name__, 'message': str(exc)}
                    report['transport_completion_uncertain'] = uncertain
                    if uncertain:
                        report['recovery_required_ja'] = 'RPCの終了を確認してから所有KEY/sessionIdで復旧する。並行要求・既存GUIの強制終了は禁止。'
                    report['execution_succeeded'] = 'failure' not in report and report.get('cleanup', {}).get('all_ui_and_owned_node_checks_passed', False)
                    save()
    print(json.dumps({'report': str(report_path), 'outcome': report.get('outcome'),
                      'execution_succeeded': report.get('execution_succeeded')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='実行前レビュー用。指定フラグなしではHoudiniへ接続しない。')
    parser.add_argument('--execute-reviewed-plan', action='store_true')
    args = parser.parse_args()
    if args.execute_reviewed_plan:
        asyncio.run(execute_reviewed_plan())
    else:
        print((ROOT / 'Source/length6_plan.json').read_text(encoding='utf8'))
