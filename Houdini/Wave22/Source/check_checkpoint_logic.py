"""公開t3標本を読み取り、Houdiniを呼ばず停止分岐と資源ガードを模擬実行する。"""
import asyncio
import ast
import copy
import hashlib
import json
import os
import tempfile
from types import SimpleNamespace
from pathlib import Path

from checkpoint_gate import check_resources, evaluate_gate, run_phases
from run_checkpoint6 import read_exact_record

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'Evidence/Checkpoint6_Planned'
DEST.mkdir(exist_ok=True)
samples_path = ROOT / 'Evidence/Curated_Runs/0652da0179/22_pilot_samples.json'
conditions_path = samples_path.with_name('22_pilot_conditions.json')
original_gate_path = samples_path.with_name('22_preroll_stability.json')
samples = json.loads(samples_path.read_text(encoding='utf8'))['samples']
conditions = json.loads(conditions_path.read_text(encoding='utf8'))
original = json.loads(original_gate_path.read_text(encoding='utf8'))
plan_path = ROOT / 'Source/checkpoint6_plan.json'
plan = json.loads(plan_path.read_text(encoding='utf8'))
paths = (samples_path, conditions_path, original_gate_path)
before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
checks = []


def record(name, passed, **details):
    assert passed, name
    checks.append({'check': name, 'passed': bool(passed), **details})


def rejected(name, change):
    rows = copy.deepcopy(samples)
    change(rows)
    try:
        evaluate_gate(rows, conditions, 3)
    except (AssertionError, ValueError, KeyError):
        record(name, True)
    else:
        raise AssertionError(name)


actual = evaluate_gate(samples, conditions, 3)
max_difference = 0
for old_window, new_window in zip(original['windows'], actual['windows']):
    for old, new in zip(old_window['gauges'], new_window['gauges']):
        for field in ('mean_eta_m', 'residual_rms_about_mean_m', 'linear_trend_m_s', 'trend_change_per_window_m'):
            max_difference = max(max_difference, abs(old[field] - new[field]))
record('公開t3固定窓のFAILを再現', actual['diagnostic_stability_passed'] is False)
record('公開統計値と一致', max_difference < 1e-14, maximum_difference_m=max_difference)
record('唯一の超過は中央測点の前窓の傾き',
       [c['both_trend_passed'] for c in actual['gauge_checks']] == [True, False, True]
       and all(c['mean_change_passed'] and c['both_rms_passed'] for c in actual['gauge_checks']),
       central_trend_change_m=actual['windows'][0]['gauges'][1]['trend_change_per_window_m'])


async def exercise(rows, label, expected_pass):
    sampled, authorization = [], []
    async def sample(index):
        sampled.append(index)
    async def decide():
        return evaluate_gate(rows, conditions, 3)
    async def authorize(gate):
        assert gate['diagnostic_stability_passed']
        authorization.append(len(sampled))
    outcome = await run_phases(sample, decide, authorize, 180, 182)
    record(label, sampled == list(range(183 if expected_pass else 181))
           and authorization == ([181] if expected_pass else [])
           and outcome['drive_authorized'] == expected_pass, outcome=outcome,
           sample_calls=len(sampled), authorization_calls=len(authorization))


asyncio.run(exercise(samples, '実t3 FAILで追加標本・駆動許可を呼ばない', False))
synthetic = copy.deepcopy(samples)
for row in synthetic:
    for gauge in row['gauges']:
        gauge['eta_m'] = -.005
    row['negative_voxel_volume_proxy_m3'] = 2.3
asyncio.run(exercise(synthetic, '合成一定値PASSの場合だけ分岐を続行する', True))
rejected('終端欠損を拒否', lambda rows: rows.pop())
rejected('重複標本を拒否', lambda rows: rows.__setitem__(100, copy.deepcopy(rows[99])))
rejected('非有限ゲージを拒否', lambda rows: rows[180]['gauges'][0].__setitem__('eta_m', float('nan')))
rejected('無効なゲージを拒否', lambda rows: rows[180]['gauges'][0].__setitem__('valid', False))
rejected('静水窓の駆動済み標本を拒否', lambda rows: rows[180].__setitem__('piston_displacement_m', .001))
rejected('実DOP時刻不一致を拒否', lambda rows: rows[180].__setitem__('simulation_seconds', 2.9))
rejected('壁外の残存粒子を拒否', lambda rows: rows[180].__setitem__('outside_inner_walls_beyond_20mm', 1))
budget = plan['resource_budget']
baseline = conditions['memory']['private_commit_bytes']
check_resources(samples, budget, baseline, 100 * 1024**3, 570)
record('実t3の費用が新しい運用上限内', True)
for field, invalid in (('simulation_memory_bytes', budget['maximum_dop_cache_bytes'] + 1),
                       ('cook_seconds', budget['maximum_sample_seconds'] + 1)):
    rows = copy.deepcopy(samples)
    rows[-1][field] = invalid
    try:
        check_resources(rows, budget, baseline, 100 * 1024**3, 570)
    except AssertionError:
        record('資源上限超過を拒否: ' + field, True)
    else:
        raise AssertionError(field)
record('公開fixtureのbytesは無変更', before == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
ack = {'json_sha256': hashlib.sha256(conditions_path.read_bytes()).hexdigest(), 'source_sha256': '検査用固定hash'}
exact = read_exact_record(conditions_path, ack, '検査用固定hash')
record('MCPの六桁数値を使わず保存JSONの精値を読む',
       exact['tank_inner_m'] == conditions['tank_inner_m'] and exact['tank_inner_m'][0] != round(exact['tank_inner_m'][0], 6))
for field in ('json_sha256', 'source_sha256'):
    invalid_ack = dict(ack)
    invalid_ack[field] = '不一致'
    try:
        read_exact_record(conditions_path, invalid_ack, '検査用固定hash')
    except AssertionError:
        record('保存JSONの出典不一致を拒否: ' + field, True)
    else:
        raise AssertionError(field)
for filename in ('checkpoint_gate.py', 'run_checkpoint6.py', 'check_checkpoint_logic.py'):
    compile((ROOT / 'Source' / filename).read_text(encoding='utf8'), filename, 'exec')
record('新規Pythonソース構文確認', True)
runner_text = (ROOT / 'Source/run_checkpoint6.py').read_text(encoding='utf8')
tree = ast.parse(runner_text)


def rpc_text(label, variables):
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == 'execute'
                and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == label)
    return eval(compile(ast.Expression(call.args[1]), '<RPC文字列の抽出>', 'eval'), variables)


# 実RPC文字列を毎回空のnamespaceから実行する。houは最小の偽物で、MCPをimportしない。
state = {'fps': 24, 'dop': SimpleNamespace(sessionId=lambda: 77, simulation=lambda: SimpleNamespace(time=lambda: 6.0))}
key = '_dry_checkpoint'
session = SimpleNamespace(**{key: state})
fake_hou = SimpleNamespace(session=session, fps=lambda: 24, isUIAvailable=lambda: True)
local = ROOT / 'Local_Reproduction'
local.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='checkpoint_namespace_', dir=local) as folder:
    temporary = Path(folder).resolve()
    assert temporary.is_relative_to(local.resolve())
    (temporary / 'Evidence').mkdir()
    ownership = rpc_text('同一DOPと資源基線を登録', {'source': (ROOT / 'Source/generate_wave.py').read_text(encoding='utf8')})
    namespace = {'hou': fake_hou, 'EXPECTED_PID': os.getpid(), 'STAGE': str(temporary),
                 'KEY': key, 'PHASE': 'register_checkpoint'}
    exec(ownership, namespace)
    record('所有基線RPCは独立namespaceで定義不足なし', namespace['result']['dop_session_id'] == 77)
    conditions6 = copy.deepcopy(conditions)
    conditions6['piston_start_absolute_seconds'] = 6.0
    write_path = temporary / 'Evidence/22_pilot_conditions.json'
    write_path.write_text(json.dumps(conditions6), encoding='utf8')
    for passed in (False, True):
        state['samples'] = []
        for k in range(361):
            row = copy.deepcopy(synthetic[0])
            row.update(sample=k, requested_seconds=k / 60, simulation_seconds=k / 60, global_frame=1 + k / 60 * 24)
            state['samples'].append(row)
        if not passed:
            # 明示合成の不安定傾向。許可を立てないことだけを検査する。
            for row in state['samples']:
                row['gauges'][1]['eta_m'] = row['requested_seconds'] * .01
        state['checkpoint_drive_authorized'] = False
        sample_file = temporary / 'Evidence/22_pilot_samples.json'
        sample_file.write_text(json.dumps({'samples': state['samples']}), encoding='utf8')
        gate_hashes = {'sample_sha256': hashlib.sha256(sample_file.read_bytes()).hexdigest(),
                       'conditions_sha256': hashlib.sha256(write_path.read_bytes()).hexdigest()}
        authorization = rpc_text('t6全条件合格後の同一DOP続行許可', {'policy': (ROOT / 'Source/checkpoint_gate.py').read_text(encoding='utf8'), 'gate': gate_hashes})
        fresh_namespace = {'hou': fake_hou, 'KEY': key, 'STAGE': str(temporary), 'STATIC_LAST': 360}
        try:
            exec(authorization, fresh_namespace)
        except AssertionError:
            assert not passed
        record('再判定RPCの独立namespaceと許可分岐: ' + str(passed), state['checkpoint_drive_authorized'] == passed)
result = {'executed_houdini': False, 'fluid_simulation_performed': False, 't6_measured': False,
          'scope_ja': '公開済み実t3の読戻し＋合成一定値による制御の模擬実行。合成値は流体の証拠ではない。',
          'input_sha256': before, 'actual_t3_gate': actual, 'checks': checks, 'passed': all(c['passed'] for c in checks),
          'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            (Path(__file__), ROOT / 'Source/checkpoint_gate.py', ROOT / 'Source/run_checkpoint6.py', plan_path)}}
(DEST / '22_checkpoint_logic_checks.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
print(json.dumps({'checks': len(checks), 'passed': result['passed'], 't3_gate': actual['diagnostic_stability_passed'], 'houdini_executed': False}))
