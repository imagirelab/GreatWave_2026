"""Houdiniを呼ばず、二窓の順序・復帰・入力判定と凍結出典を試験する。"""
import argparse
import ast
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import replay_window06 as windows
import replay_support06 as support
import run_replay06 as runner

C = Path(__file__).resolve().parents[1]
ROOT = C.parents[3]


def encode(value): return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeHou:
    class updateMode:
        Manual = 'MANUAL'
        AutoUpdate = 'AUTO'
    def __init__(self): self.mode = 'MANUAL'; self.log = []
    def updateModeSetting(self): return self.mode
    def setUpdateMode(self, mode): self.mode = mode; self.log.append(('mode', mode))


def pipeline_case(fail_at=None, input_result=True, mesh_result=True):
    hou = FakeHou(); record = {}; calls = []
    def callback(name, expected_mode, returned):
        def run(*args):
            calls.append(name); assert hou.mode == expected_mode
            if fail_at == name: raise RuntimeError('明示した合成例外: ' + name)
            return returned
        return run
    caught = None
    try:
        result = windows.two_windows06(hou, callback('input_capture', 'AUTO', 'frozen_input'),
                    callback('input_gate', 'MANUAL', input_result), callback('prepare_mesh', 'MANUAL', None),
                    callback('mesh_capture', 'AUTO', 'frozen_mesh'), callback('mesh_gate', 'MANUAL', mesh_result), record, 30)
    except Exception as exc: caught = type(exc).__name__; result = False
    return hou, record, calls, caught, result


def run_checks():
    checks = []
    def check(name, condition):
        assert condition, name
        checks.append({'name': name, 'passed': True})
    plan = json.loads((C / 'Source/replay_plan.json').read_bytes())
    check('k496旧.5のみ', plan['scope'] == 'ONE_K496_OLD_HALF_PFS_REPLAY_ONLY' and plan['sample'] == 496 and plan['mesh_parameters']['voxelsize'] == .5)
    check('他時刻細粒化detector禁止', plan['other_samples_allowed'] is False and plan['refinement_allowed'] is False and plan['detector_executed'] is False)
    check('原04のframe式とFPS24', plan['global_frame'] == 1 + (496 / 60) * 24 and plan['fps'] == 24)
    check('frame記録丸め差の明記', plan['frame_contract']['original_record_frame'] == plan['record']['global_frame']
          and plan['frame_contract']['serialization_difference_frames'] == plan['global_frame'] - plan['record']['global_frame']
          and abs(plan['global_frame'] - plan['record']['global_frame']) < plan['frame_contract']['assert_tolerance_frames'] == 1e-8)
    check('11PFS設定固定', len(plan['mesh_parameters']) == 11 and plan['mesh_parameters'] == json.loads((ROOT / 'Houdini/Wave22/Candidates/PfsSensitivity06Retry01/Source/pfs06_plan.json').read_bytes())['mesh_parameters'])
    check('geo非表示out表示', plan['node_flags'] == {'owner_display': False, 'geo_display': False, 'out_display': True, 'out_render': True})
    check('原二入力SHAと容量', all((ROOT / 'Houdini/Wave22/Runs/22e7801642/Cache' / plan['record'][kind]['filename']).stat().st_size == plan['record'][kind]['bytes']
          and sha(ROOT / 'Houdini/Wave22/Runs/22e7801642/Cache' / plan['record'][kind]['filename']) == plan['record'][kind]['sha256'] for kind in ('pilot', 'mesh')))
    manifest_path = C / 'Evidence/22_prior_attempts_manifest.json'
    prior = json.loads(manifest_path.read_bytes())
    check('保護一覧SHA', sha(manifest_path) == plan['prior_attempts_manifest_sha256'])
    actual = {p.relative_to(ROOT).as_posix() for d in prior['protected_directories'] for p in (ROOT / d).rglob('*') if p.is_file()}
    check('前候補Run156ファイル集合不変', actual == {r['path'] for r in prior['files']} and len(actual) == prior['file_count'] == 156)
    check('前候補Run156ファイルbytesSHA不変', all((ROOT / r['path']).stat().st_size == r['bytes'] and sha(ROOT / r['path']) == r['sha256'] for r in prior['files']))
    check('保護容量一致', sum(r['bytes'] for r in prior['files']) == prior['total_bytes'])
    for key in ('decision_freeze', 'decision_report'):
        row = plan[key]; check(key + '不変', (ROOT / row['path']).stat().st_size == row['bytes'] and sha(ROOT / row['path']) == row['sha256'])
    decision = json.loads((ROOT / plan['decision_report']['path']).read_bytes())
    check('Decision04新判読と原HOLD保持', decision['new_offline_interpretation_passed'] is True and decision['original_passed'] is False and decision['original_hold_overwritten'] is False)
    local_source = (C / 'Source/replay_support06.py').read_text(encoding='utf8')
    local_defs = {n.name: ast.get_source_segment(local_source, n) for n in ast.parse(local_source).body if isinstance(n, ast.FunctionDef)}
    for origin in plan['support_origins']:
        path = ROOT / origin['path']; check('抽出元SHA:' + path.name, sha(path) == origin['sha256'])
        text = path.read_text(encoding='utf8')
        original_defs = {n.name: ast.get_source_segment(text, n) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
        for name in origin['functions']:
            if name == 'definition06':
                fix = plan['support_function_exception']
                check('唯一のHDA bytes API修正', original_defs[name].count(fix['old_lines']) == 1
                      and local_defs[name] == original_defs[name].replace(fix['old_lines'], fix['new_lines']))
            else:
                check('凍結元関数と同一:' + name, local_defs[name] == original_defs[name])
    previous_candidate = ROOT / plan['source_comparison_candidate']
    check('成功Retry06を比較元に固定', previous_candidate == C.parent / 'PfsSensitivity06Retry06')
    for name in ('replay_support06.py', 'replay_window06.py'):
        check('実行源byte同一:' + name, (C / 'Source' / name).read_bytes() == (previous_candidate / 'Source' / name).read_bytes())
    for name, replacements in plan['target_source_changes'].items():
        old_name = 'replay_k360.py' if name == 'replay_k496.py' else name
        expected = (previous_candidate / 'Source' / old_name).read_text(encoding='utf8')
        for replacement in replacements:
            check('対象限定置換の旧記述存在:' + name + ':' + replacement['old'], replacement['old'] in expected)
            expected = expected.replace(replacement['old'], replacement['new'])
        check('実行源は対象限定置換だけ:' + name, (C / 'Source' / name).read_text(encoding='utf8') == expected)
    old_support = (C.parent / 'PfsSensitivity06Replay05/Source/replay_support06.py').read_text(encoding='utf8')
    fix = plan['support_function_exception']
    check('helper全体の差は一箇所のみ', local_source == old_support.replace(fix['old_lines'], fix['new_lines']) and old_support.count(fix['old_lines']) == 1)
    old_plan = json.loads((previous_candidate / 'Source/replay_plan.json').read_bytes())
    allowed = {'revision', 'status_ja', 'scope', 'sample', 'seconds', 'global_frame', 'record', 'expected_input_counts',
               'prior_attempts_manifest_sha256', 'only_execution_change_ja', 'target_source_changes',
               'source_comparison_candidate', 'frame_contract', 'successful_k360', 'successful_k474'}
    check('対象以外の設定parity予算は同一', {k: v for k, v in plan.items() if k not in allowed} == {k: v for k, v in old_plan.items() if k not in allowed})
    baseline = ROOT / 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642'
    check('原04公開資料7件SHA不変', len(plan['baseline_files']) == 7 and all(sha(baseline / name) == expected for name, expected in plan['baseline_files'].items()))
    samples = json.loads(gzip.decompress((baseline / 'Original/22_pilot_samples.json.gz').read_bytes()))['samples']
    sample = next(row for row in samples if row['sample'] == 496)
    check('原04時刻と粒子数', sample['requested_seconds'] == plan['seconds'] == 496 / 60
          and sample['particle_count'] == plan['expected_input_counts']['actual_particles'] == 53848)
    check('入力点数とVolume保持点を区別', plan['expected_input_counts'] == {'points': 53853, 'primitives': 5, 'actual_particles': 53848})
    original_plan = json.loads((C.parent / 'PfsSensitivity06Retry01/Source/pfs06_plan.json').read_bytes())
    original_record = next(row for row in original_plan['records'] if row['sample'] == 496)
    check('原04由来事前記録を無変更コピー', plan['record'] == original_record)
    check('原04三native高さと座標', plan['record']['gauges'] == sample['gauges']
          and plan['gauge_x_m'] == [g['x'] for g in sample['gauges']]
          and all(g['mesh_sampled'] and g['mesh_vertical_hit_valid'] for g in sample['gauges']))
    success = plan['successful_k360']
    for key in ('raw_result', 'execution', 'new_mesh', 'freeze'):
        row = success[key]
        check('成功k360出典SHA:' + key, sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes'])
    success_raw = json.loads((ROOT / success['raw_result']['path']).read_bytes())
    success_exec = json.loads((ROOT / success['execution']['path']).read_bytes())
    check('成功k360の実parityとreread', success_raw['passed'] is True and success_raw['input_gate_passed'] is True
          and success_raw['mesh_parity']['passed'] is True and success_raw['native_exact'] is True
          and success_raw['saved_mesh_reread_parity']['passed'] is True)
    check('成功k360のUI18と完了既知', len(success_exec['cleanup']['checks']) == 18 and all(success_exec['cleanup']['checks'].values())
          and success_exec['transport_completion_uncertain'] is False and success_exec['passed_for_review'] is True)
    check('成功k360のACKとmesh結合', success_exec['result']['sha256'] == success['raw_result']['sha256']
          and success_raw['mesh_output']['sha256'] == success['new_mesh']['sha256'])
    check('成功k360もmeshfile同一とはしない', success['file_bytes_equal'] is False
          and success['original_mesh_file_sha256'] != success['new_mesh_file_sha256'] == success['new_mesh']['sha256'])
    review = json.loads((C / 'Evidence/22_k360_success_review.json').read_bytes())
    check('成功読取要約の出典と原値', review['binding'] == success and review['mesh_parity'] == success_raw['mesh_parity']
          and review['saved_reread'] == success_raw['saved_mesh_reread_parity'] and review['auto_windows'] == success_raw['auto_windows']
          and review['seconds'] == success_raw['seconds'] and review['ui18_checks'] == success_exec['cleanup']['checks'])
    recent = plan['successful_k474']
    for key in ('raw_result', 'execution', 'new_mesh', 'freeze'):
        row = recent[key]
        check('成功k474出典SHA:' + key, sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes'])
    recent_raw = json.loads((ROOT / recent['raw_result']['path']).read_bytes())
    recent_exec = json.loads((ROOT / recent['execution']['path']).read_bytes())
    check('成功k474の実入力mesh native reread', recent_raw['sample'] == 474 and recent_raw['passed'] is True
          and recent_raw['input_gate_passed'] is True and recent_raw['mesh_parity']['passed'] is True
          and recent_raw['native_exact'] is True and recent_raw['saved_mesh_reread_parity']['passed'] is True)
    check('成功k474の原JSON ACK結合', recent_exec['result']['sha256'] == recent['raw_result']['sha256']
          and recent_raw['mesh_output']['sha256'] == recent['new_mesh']['sha256'])
    check('成功k474のUI18と完了既知', len(recent_exec['cleanup']['checks']) == 18 and all(recent_exec['cleanup']['checks'].values())
          and recent_exec['transport_completion_uncertain'] is False and recent_exec['passed_for_review'] is True)
    check('成功k474もBGEO byte同一としない', recent['file_bytes_equal'] is False
          and recent['original_mesh_file_sha256'] != recent['new_mesh_file_sha256'] == recent['new_mesh']['sha256'])
    recent_review = json.loads((C / 'Evidence/22_k474_success_review.json').read_bytes())
    check('k474読取要約を原値に結ぶ', recent_review['binding'] == recent and recent_review['mesh_parity'] == recent_raw['mesh_parity']
          and recent_review['saved_reread'] == recent_raw['saved_mesh_reread_parity'] and recent_review['auto_windows'] == recent_raw['auto_windows']
          and recent_review['seconds'] == recent_raw['seconds'] and recent_review['ui18_checks'] == recent_exec['cleanup']['checks'])
    previous = plan['previous_attempt']
    for key in ('raw_result', 'execution', 'freeze'):
        row = previous[key]
        check('前Run入力SHA:' + key, sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes'])
    previous_raw = json.loads((ROOT / previous['raw_result']['path']).read_bytes())
    previous_exec = json.loads((ROOT / previous['execution']['path']).read_bytes())
    check('前Run実HOLDと入力PASS保持', previous_raw['passed'] is False and previous_raw['input_gate_passed'] is True
          and previous_raw['failure_type'] == 'UnicodeEncodeError' and len(previous_raw['auto_windows']) == 1 and 'mesh_output' not in previous_raw)
    check('前RunのUI18と完了既知', len(previous_exec['cleanup']['checks']) == 18 and all(previous_exec['cleanup']['checks'].values())
          and previous_exec['transport_completion_uncertain'] is False)
    check('前Runの原JSONACK結合', previous_exec['result']['sha256'] == previous['raw_result']['sha256'])
    class BinarySection:
        def __init__(self, value): self.value = value; self.binary_calls = 0
        def binaryContents(self): self.binary_calls += 1; return self.value
        def contents(self): raise AssertionError('文字列APIは禁止')
    class Definition:
        def __init__(self, sections): self.data = sections
        def sections(self): return self.data
        def libraryFilePath(self): return str(C / 'Source/replay_plan.json')
    class Node:
        def __init__(self, definition): self.data = definition
        def type(self): return self
        def name(self): return 'particlefluidsurface::3.0'
        def definition(self): return self.data
    payloads = {'all_256': bytes(range(256)), 'invalid_utf8': b'\x8b\xff\xfe\xc0', 'nul': b'\x00text\x00',
                'gzip_like': b'\x1f\x8b\x08\x00\xff\xfe', 'empty': b'', 'utf8': '日本語\r\n'.encode('utf8')}
    sections = {name: BinarySection(value) for name, value in payloads.items()}
    binary_result = support.definition06(Node(Definition(sections)))
    for name, value in payloads.items():
        check('原binary SHA:' + name, binary_result['section_sha256'][name] == hashlib.sha256(value).hexdigest() and sections[name].binary_calls == 1)
    check('全sectionを省略しない', set(binary_result['section_sha256']) == set(payloads))
    check('section名で整列', list(binary_result['section_sha256']) == sorted(payloads))
    check('ライブラリfile SHA維持', binary_result['library_sha256'] == sha(C / 'Source/replay_plan.json'))
    for wrong in ('\udc8b', None, bytearray(b'raw')):
        rejected = False
        try: support.definition06(Node(Definition({'bad': BinarySection(wrong)})))
        except AssertionError: rejected = True
        check('binaryContents型不正を拒否:' + type(wrong).__name__, rejected)
    class OldSection:
        def contents(self): return '\udc8b'
    old_tree = ast.parse(old_support)
    old_definition = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'definition06')
    old_ns = {'Path': Path, 'hashlib': hashlib, 'file_sha': sha}
    exec(ast.get_source_segment(old_support, old_definition), old_ns)
    failed_unicode = False
    try: old_ns['definition06'](Node(Definition({'binary': OldSection()})))
    except UnicodeEncodeError: failed_unicode = True
    check('前回と同じsurrogate例外を再現', failed_unicode)
    class RaisingSection(BinarySection):
        def binaryContents(self): raise RuntimeError('明示したAPI失敗')
    propagated = False
    try: support.definition06(Node(Definition({'bad': RaisingSection(b'')})))
    except RuntimeError: propagated = True
    check('HOM例外を隠さず停止する', propagated)
    hou, rec, calls, error, passed = pipeline_case()
    check('二窓の順序', calls == ['input_capture', 'input_gate', 'prepare_mesh', 'mesh_capture', 'mesh_gate'])
    check('正常復帰Manual', passed and error is None and hou.mode == 'MANUAL' and len(rec['auto_windows']) == 2)
    check('両窓finally記録', all(w['manual_restored'] and w['started'] for w in rec['auto_windows']))
    for value in (False, None, 1, 'true'):
        hou, rec, calls, error, passed = pipeline_case(input_result=value)
        check('入力真以外で第二窓禁止:' + repr(value), calls == ['input_capture', 'input_gate'] and error == 'InputParityHold' and len(rec['auto_windows']) == 1 and not passed)
        check('入力拒否でもManual:' + repr(value), hou.mode == 'MANUAL')
    for phase in ('input_capture', 'input_gate', 'prepare_mesh', 'mesh_capture', 'mesh_gate'):
        hou, rec, calls, error, passed = pipeline_case(fail_at=phase)
        check(phase + '例外でManual復帰', error == 'RuntimeError' and not passed and hou.mode == 'MANUAL')
        if phase in ('input_capture', 'input_gate', 'prepare_mesh'):
            check(phase + '例外で第二窓未開始', len(rec['auto_windows']) == 1 and 'mesh_capture' not in calls)
    hou, rec, calls, error, passed = pipeline_case(mesh_result=False)
    check('旧mesh不一致でHOLD', not passed and error is None and len(rec['auto_windows']) == 2 and hou.mode == 'MANUAL')
    h = FakeHou(); r = {}; timed = False
    with patch.object(windows.time, 'monotonic', side_effect=[0.0, 30.0]):
        try: windows.auto_window06(h, 'TEST', lambda: 'frozen', r, 30)
        except TimeoutError: timed = True
    check('協調30秒境界で復帰後停止', timed and h.mode == 'MANUAL' and r['auto_windows'][0]['manual_restored'])
    h = FakeHou(); r = {}; refused = False
    with patch.object(windows.threading, 'current_thread', return_value=object()):
        try: windows.auto_window06(h, 'TEST', lambda: None, r, 30)
        except AssertionError: refused = True
    check('非main-thread更新を拒否', refused and not h.log)
    h = FakeHou(); h.mode = 'AUTO'; refused = False
    try: windows.auto_window06(h, 'TEST', lambda: None, {}, 30)
    except AssertionError: refused = True
    check('入口Manual以外を拒否', refused and not h.log)
    raw = json.loads((ROOT / 'Houdini/Wave22/Runs/file06_22b8368396/file_probe_360.json').read_bytes())
    direct = raw['direct_signature']; auto = raw['node_observations']['AUTOUPDATE_NULL_AFTER_EXPLICIT_COOK']['signature']
    before = deepcopy(auto)
    check('実Retry03入力のdetail順序差のみ許可', support.compare_signatures(direct, auto))
    check('入力dictを変更しない', support.exact(before, auto))
    for key in direct:
        mutant = deepcopy(auto)
        if key == 'attribute_inventory': mutant[key]['detail'][0]['size'] += 1
        else: mutant[key] = None
        check('入力他差を拒否:' + key, not support.compare_signatures(direct, mutant))
    mutant = deepcopy(auto); mutant['attribute_inventory']['detail'].append(deepcopy(mutant['attribute_inventory']['detail'][0]))
    check('入力detail重名拒否', not support.compare_signatures(direct, mutant))
    for raw_menu in (0, 'particlefluid'):
        check('Menu int/token:' + str(raw_menu), support.menu_observation(raw_menu, ['particlefluid'])['token'] == 'particlefluid')
    check('未接続None入力を許容', support.disconnected_file_inputs((None,), 0))
    check('File入力接続を拒否', not support.disconnected_file_inputs((object(),), 1))
    mesh = {'P': (0., 0., 0., 1., 0., 0., 0., 0., 1.), 'indices': ((0, 1, 2),), 'primitive_type_closed': (('Polygon', True),)}
    check('同じordered meshを許可', support.compare_mesh_data(mesh, deepcopy(mesh))['passed'])
    for key, value in [('P', (0., 0., 1e-12)), ('indices', ((2, 1, 0),)), ('primitive_type_closed', (('Polygon', False),))]:
        mutant = deepcopy(mesh); mutant[key] = value
        check('mesh' + key + '差を拒否', not support.compare_mesh_data(mesh, mutant)['passed'])
    failed = False
    try: support.finite_native_hit(0, [float('nan'), 0, 0], [0, 1, 0], [0, 0, 0])
    except ValueError: failed = True
    check('native非有限を明示拒否', failed)
    check('primitive0の有効hit', support.finite_native_hit(0, [0, 0, 0], [0, 1, 0], [0, 0, 0])['primitive'] == 0)
    for text in ('bad', '{}', '{"executed":null}'):
        check('不明RPC拒否:' + text, support.classify_rpc_reply(text)[0] == 'UNCERTAIN')
    check('完了errorを区別', support.classify_rpc_reply('{"executed":false}')[0] == 'COMPLETE_ERROR')
    check('完了successを区別', support.classify_rpc_reply('{"executed":true,"return_value":{}}')[0] == 'COMPLETE_SUCCESS')
    class FakeNode:
        def name(self): return 'test'
        def type(self): return self
        def cookCount(self): return 1
        def needsToCook(self): return False
        def errors(self): return ()
        def warnings(self): return ()
        def isDisplayFlagSet(self): return False
        isRenderFlagSet = isDisplayFlagSet
        isBypassed = isDisplayFlagSet
        isHardLocked = isDisplayFlagSet
        isSoftLocked = isDisplayFlagSet
        isUnloadFlagSet = isDisplayFlagSet
    class Clock:
        def time(self): return 6.0
    check('実needsToCook無引数adapter', support.node_state06(FakeNode(), Clock())['needs_to_cook_at_seconds'] == 6.0)
    code = (C / 'Source/replay_k496.py').read_text(encoding='utf8'); tree = ast.parse(code)
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    cap = ast.get_source_segment(code, functions['capture_mesh'])
    check('第二窓Outのみforce', cap.count('.cook(force=True)') == 1 and "nodes['OUT'].cook(force=True)" in cap)
    check('mesh保存はnative前', ast.get_source_segment(code, functions['compare_mesh']).index('save_generated()') < ast.get_source_segment(code, functions['compare_mesh']).index('native_first06'))
    check('PFS作成はprepareだけ', 'createNode' not in ast.get_source_segment(code, functions['capture_input']) and 'particlefluidsurface::3.0' in ast.get_source_segment(code, functions['prepare_mesh']))
    check('Auto窓内には全署名と保存なし', not any(word in cap + ast.get_source_segment(code, functions['capture_input']) for word in ('all_geometry_signature06', 'saveToFile', 'write_bytes', 'parameters06')))
    sources = '\n'.join((C / 'Source' / n).read_text(encoding='utf8') for n in ('replay_support06.py', 'replay_window06.py', 'replay_k496.py'))
    namespace = {'hou': object()}; exec(compile(sources, '<offline-definitions>', 'exec'), namespace)
    check('独立RPC namespaceで全関数定義', all(callable(namespace[n]) for n in ('replay_k496', 'two_windows06', 'all_geometry_signature06', 'compare_signatures', 'parameters06', 'native_first06')))
    probe = runner.probe_rpc('import json,hashlib\nfrom pathlib import Path\ndef serializable_observation(x):return x\ndef replay_k496(*a):return {"passed":False}',
                             {'PLAN': {}, 'PATHS': {}, 'KEY': '_unused', 'OBJ_PATH': '/unused', 'DESTINATION': 'UNUSED', 'SOURCE_SHA': 'source', 'PLAN_SHA': 'plan'})
    check('独立RPC wrapper構文', compile(probe, '<offline-rpc>', 'exec') is not None)
    for path in (C / 'Source').glob('*.py'):
        check('構文:' + path.name, compile(path.read_text(encoding='utf8'), str(path), 'exec') is not None)
    return {'passed': True, 'houdini_called': False, 'check_count': len(checks), 'checks': checks,
            'source_hashes': {p.name: sha(p) for p in sorted((C / 'Source').glob('*')) if p.is_file()},
            'prior_manifest_sha256': sha(manifest_path), 'protected_file_count': prior['file_count'], 'protected_bytes': prior['total_bytes']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--update-evidence', action='store_true'); args = parser.parse_args()
    result = run_checks(); target = C / 'Evidence/22_replay_offline_checks.json'
    if args.update_evidence: target.write_bytes(encode(result))
    else: assert target.read_bytes() == encode(result), '離線報告のbytes不一致'
    print(json.dumps({'passed': True, 'checks': result['check_count'], 'report_sha256': sha(target), 'houdini_called': False, 'evidence_updated': args.update_evidence}, ensure_ascii=False))
