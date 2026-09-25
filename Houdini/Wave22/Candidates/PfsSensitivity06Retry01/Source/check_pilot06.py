"""純関数と公開fixtureのみを試験する。既定は証拠を変更しない。"""
import argparse
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from sensitivity_core import allow_next, classify_rpc_reply, compare_mesh_data, disconnected_file_inputs, finite_native_hit, make_response_rows, menu_observation, parameter_pair, profile_acceptance, resource_decision, schedule, serializable_observation
from run_pilot06 import combined_source, stage_code

CANDIDATE = Path(__file__).resolve().parents[1]
WAVE = CANDIDATE.parents[1]
BASE = WAVE / 'Candidates/WaveStart04/Evidence/Result_22e7801642'
P05 = WAVE / 'Candidates/PfsDiagnosis05/Source'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def run_checks():
    plan = json.loads((CANDIDATE / 'Source/pfs06_plan.json').read_bytes())
    results = []
    def check(name, condition):
        assert condition, name
        results.append({'name_ja': name, 'passed': True})
    def rejected(action):
        try: action()
        except (AssertionError, ValueError): return True
        return False
    check('3フレームの固定時刻', plan['pilot_samples'] == [360, 474, 496])
    check('再候補はk360旧面一回のみ', plan['current_attempt_scope'] == 'FIRST_REPLAY_ONLY' and schedule(plan)[:plan['current_attempt_max_stages']] == [('replay', 360)])
    check('File入力tupleが空', disconnected_file_inputs((), 0))
    check('File未接続None占位を許可', disconnected_file_inputs((None,), 0))
    check('File複数のNone占位を許可', disconnected_file_inputs((None, None), 0))
    check('File実接続は拒否', not disconnected_file_inputs((object(),), 1))
    check('File接続APIの不一致も拒否', not disconnected_file_inputs((None,), 1))
    check('Menu文字列tokenを正規化', menu_observation('poly', ['poly', 'mesh'])['index'] == 0)
    check('先導は旧面3枚の後に新面3枚', schedule(plan) == [('replay', 360), ('replay', 474), ('replay', 496), ('refine', 360), ('refine', 474), ('refine', 496)])
    check('先頭から新面を作らない', not allow_next([], ('refine', 360), plan))
    for failed_at in range(3):
        completed = []
        calls = []
        for i, (stage, k) in enumerate(schedule(plan)):
            if not allow_next(completed, (stage, k), plan): break
            calls.append(stage)
            completed.append({'stage': stage, 'sample': k, 'passed_for_next': i != failed_at})
        check('旧面%d番の不一致で新面cookゼロ' % (failed_at + 1), calls.count('refine') == 0)
    completed = []
    for stage, k in schedule(plan):
        check('正常順序_%s_%s' % (stage, k), allow_next(completed, (stage, k), plan))
        completed.append({'stage': stage, 'sample': k, 'passed_for_next': True})
    check('先導後の追加要求を拒否', not allow_next(completed, ('refine', 272), plan))
    reference = {'P': (0., 0., 0., 1., 0., 0., 0., 0., 1.), 'indices': ((0, 1, 2),), 'primitive_type_closed': (('Polygon', True),)}
    check('同じP/有向indices', compare_mesh_data(reference, copy.deepcopy(reference))['passed'])
    for name, changed in (
        ('P一成分差', dict(reference, P=(1e-8,) + reference['P'][1:])),
        ('巻き順反転', dict(reference, indices=((2, 1, 0),))),
        ('閉鎖フラグ差', dict(reference, primitive_type_closed=(('Polygon', False),))),
        ('非有限', dict(reference, P=(float('nan'),) + reference['P'][1:]))):
        check(name + 'を拒否', not compare_mesh_data(reference, changed)['passed'])
    a = {'voxelsize': .5, 'particlesep': .04, 'dosmooth': 0}
    check('唯一の許可parm', parameter_pair(a, dict(a, voxelsize=.25))['passed'])
    check('filter同時変更を拒否', not parameter_pair(a, dict(a, voxelsize=.25, dosmooth=1))['passed'])
    check('scale未変更を拒否', not parameter_pair(a, a)['passed'])
    limits = plan['budgets']; reading = {'available_bytes': 40 * 1024**3, 'private_bytes': 8 * 1024**3, 'free_G_bytes': 800 * 1024**3}
    check('通常資源', resource_decision(reading, reading['private_bytes'], [2.], 142, limits)['passed'])
    for name, value in (('available_bytes', 8 * 1024**3 - 1), ('free_G_bytes', 10 * 1024**3 - 1), ('private_bytes', 20 * 1024**3)):
        check(name + '超過拒否', not resource_decision(dict(reading, **{name: value}), reading['private_bytes'], [2.], 142, limits)['passed'])
    check('30秒cook拒否', not resource_decision(reading, reading['private_bytes'], [30.], 142, limits)['passed'])
    check('直近30中位15秒拒否', not resource_decision(reading, reading['private_bytes'], [15.] * 30, 142, limits)['passed'])
    check('予測90分拒否', not resource_decision(reading, reading['private_bytes'], [20.], 300, limits)['passed'])
    check('容量予算', limits['reserved_output_bytes'] == 2449473536 and limits['start_minimum_free_G_bytes'] == 15636365312)
    profile_module = load_module('profile05_core_offline', P05 / 'profile_core.py')
    point = {'primitive': 0, 'position_m': [0., 0., 0.], 'normal': [0., 1., 0.], 'uvw': [0., 0., 0.]}
    hit = lambda low, high: copy.deepcopy(point) if low <= .4 <= high else None
    check('primitive0は有効', len(profile_module.enumerate_hits(hit, epsilon=2e-6)['hits']) == 1)
    check('default命中なのにstrict空は保留', not profile_module.incidence_consistency([], [], default_first_present=True)['passed'])
    base_profile = {'native_default_first': copy.deepcopy(point), 'strict_distinct_height_hits': {'hits': [copy.deepcopy(point)]},
                    'sensitivity_distinct_height_hits': {'hits': [copy.deepcopy(point)]}, 'strict_incidence_consistency': {'passed': True},
                    'unmerged_primitive_incidences': [copy.deepcopy(point)],
                    'field_profile': {'single_wet_to_dry_local': True}}
    check('局所交点の正常例', profile_acceptance({'profiles': [base_profile]}, {'profiles': [base_profile]})['passed'])
    changed = copy.deepcopy(base_profile); changed['strict_distinct_height_hits']['hits'] = []
    check('空交点を保留', not profile_acceptance({'profiles': [changed]}, {'profiles': [base_profile]})['passed'])
    changed = copy.deepcopy(base_profile); changed['field_profile']['single_wet_to_dry_local'] = False
    check('曖昧fieldを保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed = copy.deepcopy(base_profile); changed['strict_incidence_consistency']['passed'] = False
    check('面限定query不一致を保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed = copy.deepcopy(base_profile); changed['sensitivity_distinct_height_hits']['hits'][0]['position_m'][1] = .00001
    check('dual tolerance差を保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed = copy.deepcopy(base_profile); changed['native_default_first']['position_m'][1] = .01
    check('同一面のdefaultとstrict不一致を保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed = copy.deepcopy(base_profile); changed['native_default_first']['normal'][1] = -1
    check('defaultとstrictのnormal方向反転を保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed = copy.deepcopy(base_profile); changed['native_default_first']['primitive'] = 1
    check('default自体の面限定根拠がなければ保留', not profile_acceptance({'profiles': [changed]})['passed'])
    changed['unmerged_primitive_incidences'].append(copy.deepcopy(changed['native_default_first']))
    check('共有辺の別primitiveは面限定根拠で許可', profile_acceptance({'profiles': [changed]})['passed'])
    check('正常RPCの完了', classify_rpc_reply('{"executed":true,"return_value":{}}')[0] == 'COMPLETE_SUCCESS')
    check('実行済みcode errorは既知の完了', classify_rpc_reply('{"executed":true,"error":"mock"}')[0] == 'COMPLETE_ERROR')
    check('明示実行拒否は既知の完了', classify_rpc_reply('{"executed":false}')[0] == 'COMPLETE_ERROR')
    for raw in (None, '{bad', '{}', '[]', '{"executed":"true"}'):
        check('読めないRPCは完了不明_' + repr(raw), classify_rpc_reply(raw)[0] == 'UNCERTAIN')
    # 旧04全時系列を142面だけ残したときも、凍結detectorの全出力が同じであること。
    original = json.loads(gzip.decompress((BASE / 'Original/22_pilot_samples.json.gz').read_bytes()))['samples']
    frozen_result = json.loads((BASE / 'Original/22_startup_response.json').read_bytes())
    detector = load_module('response04_offline', BASE / 'Executed_Source/startup_response.py')
    mesh = {k: [g['mesh_eta_m'] for g in original[k]['gauges']] for k in plan['extension_samples']}
    unchanged_input = copy.deepcopy(original)
    masked = make_response_rows(original, mesh)
    check('入力JSONを変更しない', original == unchanged_input)
    check('全556solver値/時計は不変', all(a['requested_seconds'] == b['requested_seconds'] and a['simulation_seconds'] == b['simulation_seconds'] and
                                         [g['eta_m'] for g in a['gauges']] == [g['eta_m'] for g in b['gauges']] for a, b in zip(original, masked)))
    check('142面と残りfalse', sum(r['mesh_sampled'] for r in masked) == 142 and not any(r['mesh_sampled'] for r in masked[:272]))
    check('新高さへ旧meshSHAを流用しない', all(r['mesh_file_sha256'] is None and r['derived_for_detector_only'] for r in masked))
    result = detector.analyze_response(masked, frozen_result['config'])
    check('原04detector全結果を厳密再現', result == {k: v for k, v in frozen_result.items() if k != 'sample_sha256'})
    check('PFS静水窗は22/23標本', all(g['baseline']['window_counts'] == [22, 23] for g in result['observations']['PFS_display_surface']['gauges']))
    check('PFS主窗98標本/末9.233333', len([k for k in mesh if 360 <= k <= 555]) == 98 and max(mesh) / 60 == 9.233333333333333)
    missing = dict(mesh); missing.pop(474)
    check('欠落フレームを拒否', rejected(lambda: make_response_rows(original, missing)))
    invalid = dict(mesh); invalid[474] = [None, 0, 0]
    check('無効測点を補わない', rejected(lambda: make_response_rows(original, invalid)))
    increased = copy.deepcopy(mesh)
    for k in increased:
        if k <= 360: increased[k] = [v + (.004 if k % 4 == 0 else -.004) for v in increased[k]]
    raised = detector.analyze_response(make_response_rows(original, increased), frozen_result['config'])
    check('新面の静水変動でqも増加', all(g['baseline']['threshold_m'] > .001 for g in raised['observations']['PFS_display_surface']['gauges']))
    check('先導のdetector禁止', plan['response']['pilot_detector_executed'] is False)
    check('拡張実行入口なし', plan['extension_implemented'] is False)
    # namespaceはRPCごとに空から組み立てる。HOM自体は呼ばない。
    source_paths = list((CANDIDATE / 'Source').glob('*.py'))
    for path in source_paths:
        ast.parse(path.read_text(encoding='utf8'))
    check('全候補Pythonの構文', True)
    sources = {name: (P05 / name).read_text(encoding='utf8') for name in ('profile_core.py', 'read_profile05.py')}
    sources.update({name: (CANDIDATE / 'Source' / name).read_text(encoding='utf8') for name in ('sensitivity_core.py', 'remesh_pilot06.py')})
    joined = combined_source(sources)
    fake_hou = object()
    namespace = {'hou': fake_hou}
    exec(compile(joined, '<offline-definitions06>', 'exec'), namespace)
    check('独立namespaceの全定義依存', all(name in namespace for name in ('remesh_one06', 'read_pair', 'profile_acceptance', 'resource_decision', 'Path', 'json', 'hashlib', 'memory06')))
    class Types:
        Menu = 'menu'
        Ramp = 'ramp'
        Button = 'button'
    class MockHou:
        parmTemplateType = Types
    class MockParm:
        def __init__(self, kind, name='test'): self.kind = kind; self._name = name
        def set(self, value): self.requested = value
        def eval(self): return 0 if self.kind == 'menu' else self.requested
        def parmTemplate(self): return self
        def type(self): return self.kind
        def menuItems(self): return ('particlefluid', 'spherical')
        def name(self): return self._name
    menu_result = namespace['set_verified06'](MockHou, MockParm('menu'), 'particlefluid')
    check('Menu索引0とtokenを別照合', menu_result['raw_evaluated'] == 0 and menu_result['menu_token'] == 'particlefluid')
    check('数値parmは厳密照合', namespace['set_verified06'](MockHou, MockParm('float'), .25)['raw_evaluated'] == .25)
    check('別Menu tokenを拒否', rejected(lambda: namespace['set_verified06'](MockHou, MockParm('menu'), 'spherical')))
    class StringMenuParm(MockParm):
        def eval(self): return self.requested
        def menuItems(self): return ('poly', 'mesh')
    capture = []
    string_result = namespace['set_verified06'](MockHou, StringMenuParm('menu'), 'poly', lambda d: capture.append(copy.deepcopy(d)))
    check('Menu rawがstrでもtoken配対', string_result['raw_type'] == 'str' and string_result['menu_token'] == 'poly')
    check('断言前にraw/type/itemsを記録', any('menu_items' in r and r['raw_type'] == 'str' for r in capture))
    capture = []
    failed_set = rejected(lambda: namespace['set_verified06'](MockHou, MockParm('menu'), 'spherical', lambda d: capture.append(copy.deepcopy(d))))
    check('setter失敗でも実効値が残る', failed_set and capture[-1]['effective'] == 'particlefluid' and capture[-1]['requested'] == 'spherical')
    class MockRamp:
        def keys(self): return (0., .5, 1.)
        def values(self): return ((0., 0., 0.), (.2, .4, .6), (1., 1., 1.))
        def basis(self): return ('Linear', 'Constant', 'Linear')
    class RampParm(MockParm):
        def eval(self): return MockRamp()
    ramp = RampParm('ramp', 'velvisramp')
    menu = MockParm('menu', 'surfmethod'); menu.set('particlefluid')
    scalar = MockParm('float', 'voxelsize'); scalar.set(.5)
    path = MockParm('string', 'nodepath'); path.set('/obj/owned/pfs')
    class MockNode:
        def parms(self): return [ramp, menu, scalar, path]
    namespace['hou'] = MockHou
    evaluated = namespace['parameters06'](MockNode(), '/obj/owned')
    check('Rampをkeys/values/basisへ正規化', evaluated['velvisramp']['keys'] == [0., .5, 1.] and evaluated['velvisramp']['values'][1] == [.2, .4, .6])
    check('全parm結果をJSONへ保存可能', bool(json.dumps(evaluated, allow_nan=False)) and evaluated['surfmethod']['token'] == 'particlefluid')
    check('所有pathだけ正規化', evaluated['nodepath'] == '<OWNED>/pfs')
    check('native原語0を保存', finite_native_hit(0, [0, 0, 0], [0, 1, 0], [0, 0, 0])['primitive'] == 0)
    check('native位置NaNを早期検出', rejected(lambda: finite_native_hit(0, [0, math.nan, 0], [0, 1, 0], [0, 0, 0])))
    check('native uvw無限を早期検出', rejected(lambda: finite_native_hit(0, [0, 0, 0], [0, 1, 0], [0, math.inf, 0])))
    safe = serializable_observation({'passed_for_next': True, 'raw_hit': [0, math.nan, math.inf]})
    check('異常値を失わずJSON保存/保留', not safe['passed_for_next'] and len(safe['nonfinite_observation_paths']) == 2 and bool(json.dumps(safe, allow_nan=False)))
    code = stage_code(joined, {'PID': 0, 'KEY': 'unused', 'OBJ_PATH': '/obj/unused', 'STAGE': 'replay', 'EXPECTED': {}, 'PLAN': plan,
                              'PATHS': {}, 'PRIOR_PATH': None, 'PRIOR_SHA': None, 'BASE_PRIVATE': 0, 'PREVIOUS_COOKS': [],
                              'SOURCE_SHA': 'unused', 'PLAN_SHA': 'unused', 'DESTINATION': 'unused'})
    compile(code, '<offline-rpc06>', 'exec')
    check('RPC文字列の構文/注入', True)
    adapter_tree = ast.parse((CANDIDATE / 'Source/remesh_pilot06.py').read_text(encoding='utf8'))
    adapter_text = (CANDIDATE / 'Source/remesh_pilot06.py').read_text(encoding='utf8')
    check('生成面の保存はnative検査より先', adapter_text.index('generated.saveToFile') < adapter_text.index('native_new ='))
    node_types = [n.args[0].value for n in ast.walk(adapter_tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'createNode' and n.args and isinstance(n.args[0], ast.Constant)]
    check('作成typeはSOP面化限定', set(node_types) <= {'geo', 'file', 'null', 'convert', 'particlefluidsurface::3.0'} and 'particlefluidsurface::3.0' in node_types)
    text = (CANDIDATE / 'Source/run_pilot06.py').read_text(encoding='utf8')
    check('許可flag以外は表示のみ', "--execute-reviewed-single-replay" in text and "--execute-reviewed-extension" not in text and "--execute-reviewed-three-frame-pilot" not in text)
    dry = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(CANDIDATE / 'Source/run_pilot06.py')], capture_output=True, text=True, encoding='utf8', check=True)
    check('既定runnerはHoudini未接続', json.loads(dry.stdout)['houdini_called'] is False)
    check('既定runnerの範囲もk360だけ', json.loads(dry.stdout)['stage_order'] == [['replay', 360]])
    check('失敗段階と例外位置を保存', all(token in adapter_text for token in ('failure_phase', 'exception_locations', 'progress_output', 'traceback.extract_tb')))
    check('既存04出典SHA', all(sha(BASE / name) == value for name, value in plan['baseline_files'].items()))
    check('既存05読戻しSHA', all(sha(P05 / name) == value for name, value in plan['profile05_dependencies'].items()))
    previous = WAVE / 'Candidates/PfsSensitivity06'
    old_plan = json.loads((previous / 'Source/pfs06_plan.json').read_bytes())
    fixed_keys = ('baseline_files', 'profile05_dependencies', 'gauge_x_m', 'records', 'stage_order', 'mesh_parameters',
                  'candidate_change', 'convert_parameters', 'parity', 'intersection', 'response', 'budgets', 'ui_contract')
    check('元計画の科学条件と閾値は不変', all(old_plan[k] == plan[k] for k in fixed_keys))
    old_freeze = previous / 'Evidence/22_pfs06_candidate_freeze.json'
    check('初回freezeは不変', sha(old_freeze) == '9755f56dde86304afdcd6a6ad2202ee454bd0951c7d5c2a586ec904487260f60' and
          all(sha(previous / r['path']) == r['sha256'] for r in json.loads(old_freeze.read_bytes())['files']))
    rejected_run = WAVE / 'Runs/pfs06_da9e62c8df'
    check('初回の原失敗記録は不変', sha(rejected_run / 'replay_360.json') == plan['previous_attempt']['replay_json_sha256'] and
          sha(rejected_run / 'execution.json') == plan['previous_attempt']['execution_json_sha256'])
    # manifestだけでなく先導6入力の実bytesも読む。BGEOの解釈/HOMはしない。
    actual_bytes = 0
    for k in plan['pilot_samples']:
        record = next(r for r in plan['records'] if r['sample'] == k)
        for kind in ('pilot', 'mesh'):
            entry = record[kind]; path = WAVE / 'Runs/22e7801642/Cache' / entry['filename']
            assert sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes']
            actual_bytes += entry['bytes']
    check('先導6入力BGEOのbytes/SHA', actual_bytes == limits['pilot_input_unique_bytes'])
    return {'revision': '22修正06', 'passed': True, 'houdini_called': False, 'new_meshing_executed': False,
            'check_count': len(results), 'checks': results,
            'source_hashes': {p.name: sha(p) for p in sorted((CANDIDATE / 'Source').iterdir()) if p.is_file()},
            'pilot_input_unique_bytes': actual_bytes,
            'meaning_ja': 'mock/純関数/公開JSONとファイルSHAの検査だけ。実HOM/HDA/面化/性能/元mesh配対は未実行。'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--update-evidence', action='store_true')
    args = parser.parse_args(); result = run_checks()
    evidence = CANDIDATE / 'Evidence/22_pfs06_offline_checks.json'
    if args.update_evidence:
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
    else:
        assert json.loads(evidence.read_bytes()) == result, '報告が現sourceと異なる。明示更新後に再審査する。'
    print(json.dumps({'passed': result['passed'], 'checks': result['check_count'], 'houdini_called': False,
                      'evidence_written': args.update_evidence, 'evidence_sha256': sha(evidence)}, ensure_ascii=False))
