"""新.25候補の離線検査。実HOM/MCPを呼ばず、既定では証拠を変更しない。"""
import argparse
import ast
import asyncio
from contextlib import asynccontextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch
import refine_core06 as core
import replay_window06 as windows
import replay_support06 as support
import profile_core as profiles
import run_refine06 as runner

C = Path(__file__).resolve().parents[1]
ROOT = C.parents[3]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(x): return (json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def synthetic_profile(delta=0.):
    rows = []
    for p in profiles.registered_positions([2., 3., 4.]):
        def hit(number, y, normal):
            return {'primitive': number, 'position_m': [p['x_m'], y, p['z_m']], 'normal': normal, 'uvw': [.5, .5, 0.]}
        upper = hit(0, delta, [0., 1., 0.]); lower = hit(1, -.6, [0., -1., 0.])
        row = dict(p, native_default_first=deepcopy(upper), native_default_first_y_m=delta,
                   strict_distinct_height_hits={'hits': [deepcopy(upper), deepcopy(lower)], 'complete_within_step': True},
                   sensitivity_distinct_height_hits={'hits': [deepcopy(upper), deepcopy(lower)], 'complete_within_step': True},
                   unmerged_primitive_incidences=[deepcopy(upper), deepcopy(lower)], strict_incidence_consistency={'passed': True},
                   field_profile={'single_wet_to_dry_local': True, 'height_m': 0., 'phi': [-.5, .2]})
        if p['dx_m'] == 0 and p['z_m'] == 0:
            row.update(center_parity_passed=delta == 0, center_mesh_error_m=delta, center_solver_error_m=0.)
        rows.append(row)
    return {'profiles': rows, 'completed_readback': True, 'metadata_unchanged': True}


def mock_orchestration(mode):
    """通信を完全な偽物へ置換。各失敗後に追加RPCが無いことを確認する。"""
    calls = []
    with tempfile.TemporaryDirectory(prefix='gw06_offline_', dir=str(C.parents[1])) as temp:
        root = Path(temp); wave = root / 'wave'; wave.mkdir()
        cache = wave / 'Runs/22e7801642/Cache'; cache.mkdir(parents=True)
        (cache / 'pilot_360.bgeo.sc').write_bytes(b'synthetic-particles')
        (cache / 'mesh_360.bgeo.sc').write_bytes(b'synthetic-old-mesh')
        (root / 'guard.py').write_bytes(b"SNAPSHOT='result={}'\nCLEANUP='result={}'\n")
        plan = json.loads((C / 'Source/refine_plan.json').read_bytes())
        plan['record']['pilot']['sha256'] = sha(cache / 'pilot_360.bgeo.sc')
        plan['record']['mesh']['sha256'] = sha(cache / 'mesh_360.bgeo.sc')
        def literals(code):
            result = {}
            for node in ast.parse(code).body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    try: result[node.targets[0].id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError): pass
            return result
        class Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
            async def initialize(self): pass
            async def call_tool(self, name, payload):
                label = next(x for x in ('METADATA', 'SNAPSHOT', 'OWNED_SETUP', 'K360_QUARTER_MESH', 'RESTORE_UI18',
                                        'READ_ONLY_PROFILE_OLD', 'READ_ONLY_PROFILE_NEW') if payload['justification'].endswith(x))
                calls.append(label); v = literals(payload['code'])
                if mode == 'uncertain_mesh' and label == 'K360_QUARTER_MESH' or mode == 'uncertain_old' and label == 'READ_ONLY_PROFILE_OLD':
                    return types.SimpleNamespace(isError=False, content=[types.SimpleNamespace(type='text', text='invalid-json')])
                if label == 'METADATA': value = {'pid': 123, 'version': '22.0.429', 'license': 'licenseCategoryType.Indie', 'ui': True, 'fps': 24}
                elif label in ('SNAPSHOT', 'OWNED_SETUP'): value = {}
                elif label == 'RESTORE_UI18': value = {'all_ui_and_owned_node_checks_passed': mode != 'cleanup_fail', 'checks': {str(i): True for i in range(18)}}
                elif label == 'K360_QUARTER_MESH':
                    mesh = Path(v['PATHS']['mesh_output']); mesh.write_bytes(b'synthetic-new-mesh')
                    result = {'passed': mode != 'mesh_hold', 'combined_source_sha256': v['SOURCE_SHA'], 'plan_sha256': v['PLAN_SHA'],
                              'mesh_output': {'sha256': sha(mesh), 'bytes': mesh.stat().st_size}, 'replay_mesh_counts': {'points': 8, 'faces': 6},
                              'resources': [{'private_bytes': 1}]}
                    if mode == 'nonfinite_mesh':
                        result.update(nonfinite_observation_paths=['/mock_invalid'], passed_for_next=False)
                    out = Path(v['DESTINATION']); out.write_bytes(encoded(result)); value = {'json_sha256': sha(out), 'source_sha256': v['SOURCE_SHA']}
                else:
                    result = synthetic_profile(.002 if label.endswith('NEW') else 0.)
                    if mode == 'old_hold' and label.endswith('OLD'): result['profiles'][0]['native_default_first'] = None
                    if mode == 'old_metadata_changed' and label.endswith('OLD'): result['metadata_unchanged'] = False
                    if mode == 'new_hold' and label.endswith('NEW'): result['profiles'][0]['strict_incidence_consistency']['passed'] = False
                    result.update(combined_reader_sha256=v['SOURCE_SHA'], plan_sha256=v['PLAN_SHA'], input_sha_after={
                        'mesh': v['EXPECTED']['mesh_sha256'], 'solver': v['EXPECTED']['solver_sha256']})
                    out = Path(v['DESTINATION'])
                    if mode == 'old_budget_hold' and label.endswith('OLD'):
                        value = {'json_sha256': None, 'source_sha256': v['SOURCE_SHA'], 'json_written': False,
                                 'budget_hold': {'attempted_json_bytes': 33554432}}
                    else:
                        out.write_bytes(encoded(result)); value = {'json_sha256': sha(out), 'source_sha256': v['SOURCE_SHA']}
                return types.SimpleNamespace(isError=False, content=[types.SimpleNamespace(type='text', text=json.dumps({'executed': True, 'return_value': value}))])
        @asynccontextmanager
        async def transport(*a, **k): yield (None, None)
        mcp = types.ModuleType('mcp'); mcp.ClientSession = Client; mcp.StdioServerParameters = lambda **kw: kw
        client_module = types.ModuleType('mcp.client'); stdio = types.ModuleType('mcp.client.stdio'); stdio.stdio_client = transport
        with patch.dict(sys.modules, {'mcp': mcp, 'mcp.client': client_module, 'mcp.client.stdio': stdio}), \
             patch.object(runner, 'validate_frozen', return_value=plan), patch.object(runner, 'ROOT', root), \
             patch.object(runner, 'WAVE', wave), patch.object(runner, 'GUARD', 'guard.py'), redirect_stdout(io.StringIO()):
            asyncio.run(runner.execute())
        outputs = list((wave / 'Runs').glob('pfsrefine06_*/execution.json')); assert len(outputs) == 1
        result = json.loads(outputs[0].read_bytes())
        return calls, result


def run_checks():
    checks = []
    def ck(name, value):
        assert value, name
        checks.append({'name': name, 'passed': True})
    plan = json.loads((C / 'Source/refine_plan.json').read_bytes())
    ck('k360 .25単一対象', plan['sample'] == 360 and plan['global_frame'] == 145 and plan['fps'] == 24
       and plan['scope'] == 'ONE_K360_QUARTER_MESH_SENSITIVITY_ONLY' and plan['mesh_parameters']['voxelsize'] == .25)
    ck('他時刻solver detector禁止', not plan['other_samples_allowed'] and not plan['new_solver'] and not plan['detector_executed'])
    prior_path = C / 'Evidence/22_prior_attempts_manifest.json'; prior = json.loads(prior_path.read_bytes())
    ck('旧180ファイル保護一覧SHA', sha(prior_path) == plan['prior_attempts_manifest_sha256'] and prior['file_count'] == 180)
    paths = {p.relative_to(ROOT).as_posix() for d in prior['protected_directories'] for p in (ROOT / d).rglob('*') if p.is_file()}
    ck('旧集合一致', paths == {x['path'] for x in prior['files']})
    ck('旧bytesとSHA一致', all((ROOT / x['path']).stat().st_size == x['bytes'] and sha(ROOT / x['path']) == x['sha256'] for x in prior['files']))
    ck('保護合計容量', sum(x['bytes'] for x in prior['files']) == prior['total_bytes'])
    for key, group in plan['baseline_successes'].items():
        for name, x in group.items(): ck('旧成功SHA:' + key + ':' + name, sha(ROOT / x['path']) == x['sha256'])
        raw = json.loads((ROOT / group['raw']['path']).read_bytes()); ex = json.loads((ROOT / group['execution']['path']).read_bytes())
        ck('旧成功実parity:' + key, raw['passed'] and raw['mesh_parity']['passed'] and raw['native_exact'] and raw['saved_mesh_reread_parity']['passed'])
        ck('旧成功UI18:' + key, all(ex['cleanup']['checks'].values()) and len(ex['cleanup']['checks']) == 18 and not ex['transport_completion_uncertain'])
    for name, x in {**plan['profile_dependencies'], **plan['support_dependency']['files']}.items():
        ck('凍結依存byte同一:' + name, sha(ROOT / x['path']) == sha(C / 'Source' / name) == x['sha256'])
    baseline = ROOT / 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642'
    ck('原04公開資料SHA', all(sha(baseline / n) == h for n, h in plan['baseline_files'].items()))
    for kind in ('pilot', 'mesh'):
        x = plan['record'][kind]; p = ROOT / 'Houdini/Wave22/Runs/22e7801642/Cache' / x['filename']
        ck('原k360 cache:' + kind, sha(p) == x['sha256'] and p.stat().st_size == x['bytes'])
    base_plan = json.loads((ROOT / plan['support_dependency']['directory'] / 'Source/replay_plan.json').read_bytes())
    expected = deepcopy(base_plan['mesh_parameters']); expected['voxelsize'] = .25
    ck('11明示設定はvoxel以外同一', plan['mesh_parameters'] == expected and plan['record'] == base_plan['record'])
    ck('195同一登録点', len(profiles.registered_positions(plan['gauge_x_m'])) == plan['profile_count_per_mesh'] == 195 and plan['profile_count_total'] == 390)
    old = synthetic_profile(); new = synthetic_profile(.002)
    ck('旧正常profile', core.profile_shape06(old)['passed'])
    ck('新旧差は許容してquery shapeを確認', core.profile_shape06(new, old)['passed'])
    ck('判定は物理PASSでない', not core.profile_shape06(new, old)['physical_pass'])
    for label, change in [
        ('missing', lambda r: r.update(native_default_first=None)),
        ('incidence', lambda r: r['strict_incidence_consistency'].update(passed=False)),
        ('ambiguous', lambda r: r['field_profile'].update(single_wet_to_dry_local=False)),
        ('nonfinite', lambda r: r['native_default_first']['uvw'].__setitem__(0, float('nan'))),
        ('default_height', lambda r: r['native_default_first']['position_m'].__setitem__(1, .01)),
        ('default_normal', lambda r: r['native_default_first']['normal'].__setitem__(1, -1.)),
        ('pattern', lambda r: r['unmerged_primitive_incidences'][0].update(primitive=99)),
        ('sensitivity', lambda r: r['sensitivity_distinct_height_hits']['hits'][0]['position_m'].__setitem__(1, .01)),
        ('incomplete', lambda r: r['strict_distinct_height_hits'].update(complete_within_step=False)),
        ('coordinate', lambda r: r.update(x_m=99.)),
        ('field_changed', lambda r: r['field_profile']['phi'].__setitem__(0, -.1))]:
        mutant = deepcopy(new); change(mutant['profiles'][0]); ck('保留:' + label, not core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new); mutant['profiles'].pop(); ck('194行を拒否', not core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new); mutant['profiles'][1] = deepcopy(mutant['profiles'][0]); ck('重複座標を拒否', not core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new)
    for key in ('strict_distinct_height_hits', 'sensitivity_distinct_height_hits'):
        mutant['profiles'][0][key]['hits'].pop()
    ck('新旧上下交点数変更を保留', not core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new); r = mutant['profiles'][0]
    for hit in [r['native_default_first'], r['strict_distinct_height_hits']['hits'][0],
                r['sensitivity_distinct_height_hits']['hits'][0], r['unmerged_primitive_incidences'][0]]:
        hit['normal'][1] = -1.
    ck('同面queryが一致しても上面反転を保留', not core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new); r = mutant['profiles'][0]
    r['native_default_first']['primitive'] = 9
    r['unmerged_primitive_incidences'].append(deepcopy(r['native_default_first']))
    ck('共有辺のdefault別primitiveは裏付けがあれば許容', core.profile_shape06(mutant, old)['passed'])
    mutant = deepcopy(new); center = next(x for x in mutant['profiles'] if 'center_solver_error_m' in x); center['center_solver_error_m'] = 2e-8
    ck('solver中央差を拒否', not core.profile_shape06(mutant, old)['passed'])
    ck('parameter voxelだけPASS', core.same_parameters_except_voxel({'voxelsize': .5, 'nested': [1]}, {'voxelsize': .25, 'nested': [1]})['passed'])
    for changed in ({'voxelsize': .25, 'nested': [True]}, {'voxelsize': .5, 'nested': [1]}, {'voxelsize': .25, 'nested': [2]}):
        ck('parameter追加差拒否:' + repr(changed), not core.same_parameters_except_voxel({'voxelsize': .5, 'nested': [1]}, changed)['passed'])
    class FakeHou:
        class updateMode: Manual = 'M'; AutoUpdate = 'A'
        def __init__(self): self.mode = 'M'
        def updateModeSetting(self): return self.mode
        def setUpdateMode(self, v): self.mode = v
    for rejected in (False, None, 1, 'true'):
        h = FakeHou(); calls = []; rec = {}
        try:
            windows.two_windows06(h, lambda: 'input', lambda x: rejected, lambda: calls.append('prepare'),
                                  lambda: calls.append('mesh'), lambda x: True, rec, 30)
        except windows.InputParityHold: pass
        ck('入力真以外で第二窓禁止:' + repr(rejected), not calls and h.mode == 'M' and len(rec['auto_windows']) == 1)
    for fail in ('capture_input', 'compare_input', 'prepare_mesh', 'capture_mesh', 'compare_mesh'):
        h = FakeHou(); calls = []; record = {}
        def f(name):
            def run(*a):
                calls.append(name)
                if name == fail: raise RuntimeError(name)
                return True
            return run
        try: windows.two_windows06(h, *[f(n) for n in ('capture_input','compare_input','prepare_mesh','capture_mesh','compare_mesh')], record, 30)
        except RuntimeError: pass
        ck('例外復帰Manual:' + fail, h.mode == 'M')
        if fail in ('capture_input','compare_input','prepare_mesh'): ck('第二窓禁止:' + fail, 'capture_mesh' not in calls)
    for mode in ('success', 'mesh_hold', 'nonfinite_mesh', 'cleanup_fail', 'old_hold', 'old_metadata_changed',
                 'old_budget_hold', 'new_hold', 'uncertain_mesh', 'uncertain_old'):
        calls, r = mock_orchestration(mode)
        ck('mock終了:' + mode, r['passed_for_review'] is (mode == 'success'))
        if mode in ('mesh_hold', 'nonfinite_mesh', 'cleanup_fail', 'uncertain_mesh'): ck('profile未開始:' + mode, not any(x.startswith('READ_ONLY') for x in calls))
        if mode in ('old_hold', 'old_metadata_changed', 'old_budget_hold', 'uncertain_old'):
            ck('旧FAIL後新禁止:' + mode, 'READ_ONLY_PROFILE_NEW' not in calls)
        if mode == 'old_budget_hold': ck('容量HOLDのACKをexecutionへ保持', r['profiles']['old']['ack']['json_written'] is False)
        if mode == 'uncertain_mesh': ck('不明時cleanup禁止', 'RESTORE_UI18' not in calls and r['transport_completion_uncertain'])
        if mode == 'uncertain_old': ck('読戻し不明後追加RPCなし', calls[-1] == 'READ_ONLY_PROFILE_OLD' and r['transport_completion_uncertain'])
        if mode == 'success': ck('UI復元後だけ旧→新', calls[-3:] == ['RESTORE_UI18','READ_ONLY_PROFILE_OLD','READ_ONLY_PROFILE_NEW'])
    source = (C / 'Source/refine_k360.py').read_text(encoding='utf8')
    ck('native前mesh保存', source.index('save_generated()\n            health()') < source.index("record['native_original'] = []"))
    ck('旧新完全mesh一致は観測だけ', "record['old_new_mesh_comparison_diagnostic_only']" in source and "record['mesh_parity']['passed']" not in source)
    ck('入力全署名と定義全比較', "baseline_input_canonical_equal" in source and "record['parameter_pair']['passed'] and record['definition_equal'] and record['convert_equal']" in source)
    tree = ast.parse(source)
    capture = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'capture_mesh')
    capture_source = ast.get_source_segment(source, capture)
    ck('第二AutoはOutのみforce', capture_source.count('.cook(force=True)') == 1 and "nodes['OUT'].cook(force=True)" in capture_source)
    combined = '\n'.join((C / 'Source' / n).read_text(encoding='utf8') for n in ('replay_support06.py','replay_window06.py','refine_core06.py','refine_k360.py'))
    ns = {'hou': object()}; exec(compile(combined, '<offline-definitions>', 'exec'), ns)
    ck('独立namespaceで定義のみ', all(callable(ns[n]) for n in ('refine_k360','same_parameters_except_voxel','all_geometry_signature06','parameters06')))
    with tempfile.TemporaryDirectory(prefix='gw06_wrapper_', dir=str(C.parents[1])) as temp:
        t = Path(temp); (t/'mesh').write_bytes(b'mesh'); (t/'solver').write_bytes(b'solver')
        class ReadHou:
            hipFile = types.SimpleNamespace(hasUnsavedChanges=lambda: False)
            def frame(self): return 1.
            def fps(self): return 24.
            def updateModeSetting(self): return 'AutoUpdate'
            def node(self, path): return None
        fake_source = '''import json,hashlib
from pathlib import Path
def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def serializable_observation(x):return x
def memory06(anchor):return {'available_bytes':10**12,'private_bytes':10,'free_G_bytes':10**12}
def read_pair(*args):return {'profiles':[], 'completed_readback':True}
'''
        for fails in (False, True):
            out = t / ('failure.json' if fails else 'success.json')
            src = fake_source if not fails else fake_source.replace("return {'profiles':[], 'completed_readback':True}", "raise ValueError('明示したreader例外')")
            values = {'DESTINATION':str(out),'MESH_PATH':str(t/'mesh'),'SOLVER_PATH':str(t/'solver'),
                      'OBJ_PATH':'/unused','SOURCE_SHA':'source','PLAN_SHA':'plan','EXPECTED':{},'PROFILE_PLAN':{},
                      'PROFILE_LIMITS':plan['budgets'],'BASE_PRIVATE':10,'OUTPUT_ROOT':str(t)}
            ns = {'hou': ReadHou()}; exec(compile(runner.profile_rpc06(src, values), '<mock-profile-rpc>', 'exec'), ns)
            data = json.loads(out.read_bytes())
            ck('断面wrapper単独namespace/原JSONACK:' + str(fails), ns['result']['json_sha256'] == sha(out)
               and data['metadata_unchanged'] and data['completed_readback'] is (not fails))
            ck('断面wrapper入力SHAと資源:' + str(fails), data['input_sha_after'] == {'mesh':sha(t/'mesh'),'solver':sha(t/'solver')}
               and len(data['resource_readings']) == (1 if fails else 2))
            ck('断面HIP変更flag不変:' + str(fails), data['metadata_before']['hip_has_unsaved_changes'] is False
               and data['metadata_after']['hip_has_unsaved_changes'] is False)
        for mode in ('single_limit', 'total_limit', 'no_summary_space', 'hip_changed'):
            out = t / (mode + '.json'); limits = deepcopy(plan['budgets'])
            src = fake_source.replace("return {'profiles':[], 'completed_readback':True}",
                                      "return {'profiles':[], 'padding':'x'*32768, 'completed_readback':True}")
            if mode == 'single_limit': limits['maximum_profile_bytes'] = 4096
            if mode in ('total_limit', 'no_summary_space'):
                used = sum(p.stat().st_size for p in t.rglob('*') if p.is_file())
                limits['auxiliary_reserved_bytes'] = used + limits['profile_output_bookkeeping_reserved_bytes'] + (4096 if mode == 'total_limit' else 1)
            h = ReadHou()
            if mode == 'hip_changed':
                flags = iter((False, True)); h.hipFile = types.SimpleNamespace(hasUnsavedChanges=lambda: next(flags))
            values.update(DESTINATION=str(out), PROFILE_LIMITS=limits)
            ns = {'hou': h}; exec(compile(runner.profile_rpc06(src, values), '<mock-bounded-profile-rpc>', 'exec'), ns)
            if mode == 'no_summary_space':
                ck('容量余地なしは書込前HOLD', not out.exists() and ns['result']['json_written'] is False and ns['result']['budget_hold'] is not None)
            elif mode == 'hip_changed':
                data = json.loads(out.read_bytes())
                ck('HIP変更は原JSONへ明示', not data['metadata_unchanged'] and data['metadata_after']['hip_has_unsaved_changes'])
            else:
                data = json.loads(out.read_bytes())
                ck('容量超過完全JSONを保存しない:' + mode, out.stat().st_size <= 4096 and 'padding' not in data
                   and data['completed_readback'] is False and data['failure_type'] == 'ProfileOutputBudgetHold')
                ck('容量HOLDの原サイズSHAとACK:' + mode, data['budget_hold']['attempted_json_bytes'] > 32768
                   and len(data['budget_hold']['attempted_json_sha256']) == 64 and ns['result']['json_sha256'] == sha(out))
    for file in (C / 'Source').glob('*.py'): ck('構文:' + file.name, compile(file.read_text(encoding='utf8'),str(file),'exec') is not None)
    return {'passed': True, 'houdini_called': False, 'checks': checks, 'check_count': len(checks),
            'source_hashes': {p.name: sha(p) for p in sorted((C / 'Source').iterdir()) if p.is_file()},
            'prior_manifest_sha256': sha(prior_path), 'protected_file_count': prior['file_count'], 'protected_bytes': prior['total_bytes']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--update-evidence', action='store_true'); args = parser.parse_args()
    result = run_checks(); p = C / 'Evidence/22_refine_offline_checks.json'
    if args.update_evidence: p.write_bytes(encoded(result))
    else: assert p.read_bytes() == encoded(result), '離線報告と現在sourceが不一致'
    print(json.dumps({'passed': True, 'checks': result['check_count'], 'report_sha256': sha(p), 'houdini_called': False, 'evidence_updated': args.update_evidence}))
