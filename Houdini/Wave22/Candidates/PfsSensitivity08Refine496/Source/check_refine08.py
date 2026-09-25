"""新.25候補の離線検査。実HOM/MCPを呼ばず、既定では証拠を変更しない。"""
import argparse
import ast
import asyncio
import builtins
from contextlib import asynccontextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import types
from unittest.mock import patch
import refine_core06 as core
import refine_contract08 as contract
import replay_window06 as windows
import replay_support06 as support
import profile_core as profiles
import run_refine08 as runner

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
    return {'profiles': rows, 'completed_readback': True, 'metadata_unchanged': True,
            'sample':496, 'seconds':496/60, 'mesh_sha256':'mock-mesh', 'solver_sha256':'mock-solver',
            'mesh_points':8, 'mesh_faces':6, 'mesh_P_float64_sha256':'mock-P', 'field':{},
            'spatial_neighbour_differences':[], 'center_parity_passed':True,
            'strict_incidence_consistency_passed':True, 'strict_incidence_mismatch_profile_indices':[],
            'solver_executed':False, 'nodes_created':False}


def mock_orchestration(mode):
    """通信を完全な偽物へ置換。各失敗後に追加RPCが無いことを確認する。"""
    calls = []
    with tempfile.TemporaryDirectory(prefix='gw06_offline_', dir=str(C.parents[1])) as temp:
        root = Path(temp); wave = root / 'wave'; wave.mkdir()
        cache = wave / 'Runs/22e7801642/Cache'; cache.mkdir(parents=True)
        (cache / 'pilot_496.bgeo.sc').write_bytes(b'synthetic-particles')
        (cache / 'mesh_496.bgeo.sc').write_bytes(b'synthetic-old-mesh')
        (root / 'guard.py').write_bytes(b"SNAPSHOT='result={}'\nCLEANUP='result={}'\n")
        plan = json.loads((C / 'Source/refine_plan.json').read_bytes())
        plan['record']['pilot']['sha256'] = sha(cache / 'pilot_496.bgeo.sc')
        plan['record']['mesh']['sha256'] = sha(cache / 'mesh_496.bgeo.sc')
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
                label = next(x for x in ('METADATA', 'SNAPSHOT', 'OWNED_SETUP', 'K496_QUARTER_MESH', 'RESTORE_UI18',
                                        'READ_ONLY_PROFILE_OLD', 'READ_ONLY_PROFILE_NEW') if payload['justification'].endswith(x))
                calls.append(label); v = literals(payload['code'])
                if mode == 'uncertain_mesh' and label == 'K496_QUARTER_MESH' or mode == 'uncertain_old' and label == 'READ_ONLY_PROFILE_OLD':
                    return types.SimpleNamespace(isError=False, content=[types.SimpleNamespace(type='text', text='invalid-json')])
                if label == 'METADATA': value = {'pid': 123, 'version': '22.0.429', 'license': 'licenseCategoryType.Indie', 'ui': True, 'fps': 24}
                elif label in ('SNAPSHOT', 'OWNED_SETUP'): value = {}
                elif label == 'RESTORE_UI18': value = {'all_ui_and_owned_node_checks_passed': mode != 'cleanup_fail', 'checks': {str(i): True for i in range(18)}}
                elif label == 'K496_QUARTER_MESH':
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
                    if mode == 'old_published_mismatch' and label.endswith('OLD'): result['field'] = {'unexpected':1}
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
             patch.object(runner, 'WAVE', wave), patch.object(runner, 'GUARD', 'guard.py'), \
             patch.object(runner.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10**12)), \
             patch.object(runner, 'read_profile_baseline08', return_value=synthetic_profile()), redirect_stdout(io.StringIO()):
            asyncio.run(runner.execute())
        outputs = list((wave / 'Runs').glob('pfsrefine08_*/execution.json')); assert len(outputs) == 1
        result = json.loads(outputs[0].read_bytes())
        return calls, result


def additional_checks08(ck, plan):
    """対象の取り違え・05配対の欠落・開始容量不足を実際の純関数へ注入する。"""
    ck('08対象契約', contract.target08(plan))
    ck('08基線commit固定', subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
       == plan['baseline_commit'] == '3c30afac96772a586ff3f24a0ccd6230542f3f3f')
    for key in ('minimum_available_RAM_bytes','maximum_private_increase_bytes','maximum_cook_window_seconds',
                'per_rpc_cooperative_seconds','rpc_wait_seconds','maximum_mesh_bytes','maximum_report_bytes',
                'maximum_profile_bytes','auxiliary_reserved_bytes','profile_output_bookkeeping_reserved_bytes'):
        mutant=deepcopy(plan); mutant['budgets'][key]+=1
        try: contract.target08(mutant); refused=False
        except AssertionError: refused=True
        ck('登録資源値の変更拒否:'+key, refused)
    mutant=deepcopy(plan); mutant['sample']=474
    try: contract.target08(mutant); refused=False
    except AssertionError: refused=True
    ck('前回k474への誤復帰を拒否', refused)
    for key, value in (('sample',360), ('seconds',6.), ('global_frame',145.), ('fps',30),
                       ('other_samples_allowed',True), ('new_solver',True), ('detector_executed',True)):
        candidate = deepcopy(plan); candidate[key] = value
        try: contract.target08(candidate); refused = False
        except AssertionError: refused = True
        ck('誤対象を拒否:' + key, refused)
    for value in (15636365311, 10737418240):
        try: contract.initial_disk08(value, plan); refused = False
        except AssertionError: refused = True
        ck('開始G下限を拒否:' + str(value), refused)
    ck('開始G境界は可', contract.initial_disk08(15636365312, plan)['passed'])
    # 本物のexecute入口を呼ぶが容量門で終了。MCPへ到達すれば偽物の例外となる。
    with patch.object(runner, 'validate_frozen', return_value=plan), \
         patch.object(runner.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=15636365311)), \
         patch.object(runner, 'read_profile_baseline08', side_effect=RuntimeError('ここへ到達してはいけない')) as blocked:
        try: asyncio.run(runner.execute()); refused = False
        except AssertionError: refused = True
        ck('開始G不足は読戻し/Run作成/MCP前停止', refused and blocked.call_count == 0)
    baseline = contract.read_profile_baseline08(ROOT, plan['profile05_baseline'])
    ck('公開05原全195有効', core.profile_shape06(baseline)['passed'])
    ck('公開05科学15項の同一性', contract.compare_profile05_08(baseline, deepcopy(baseline))['passed'])
    modified = deepcopy(baseline)
    modified.update(read_seconds=99., memory_guard={}, meaning_ja='今回の説明', metadata_before={}, plan_sha256='別の実行計画')
    ck('計測時間/資源/最上位説明/実行metadata差を許す', contract.compare_profile05_08(baseline, modified)['passed'])
    mutations = [
        ('field', lambda v: v['field']['resolution'].__setitem__(0, 999)),
        ('point_count', lambda v: v.update(mesh_points=999)),
        ('cache_sha', lambda v: v.update(mesh_sha256='違う面')),
        ('P_sha', lambda v: v.update(mesh_P_float64_sha256='違う座標')),
        ('native_height', lambda v: v['profiles'][0]['native_default_first']['position_m'].__setitem__(1, 0.)),
        ('native_primitive', lambda v: v['profiles'][0]['native_default_first'].update(primitive=-1)),
        ('native_normal', lambda v: v['profiles'][0]['native_default_first']['normal'].__setitem__(0, 99.)),
        ('native_uvw', lambda v: v['profiles'][0]['native_default_first']['uvw'].__setitem__(0, 99.)),
        ('missing_row', lambda v: v['profiles'].pop()),
        ('reorder', lambda v: v['profiles'].reverse()),
        ('nested_description', lambda v: v['profiles'][0]['field_profile'].update(meaning_ja='変更')),
    ]
    for label, mutation in mutations:
        modified = deepcopy(baseline); mutation(modified)
        ck('公開05不一致HOLD:' + label, not contract.compare_profile05_08(baseline, modified)['passed'])
    centers = [i for i, row in enumerate(baseline['profiles']) if row['dx_m'] == 0 and row['z_m'] == 0]
    for gauge, index in enumerate(centers, 1):
        modified = deepcopy(baseline); modified['profiles'][index]['center_original_gauge_replay']['eta_m'] += 1e-9
        ck('原04中心二分値の変更拒否:G' + str(gauge), not contract.compare_profile05_08(baseline, modified)['passed'])
    replay = json.loads((ROOT / plan['baseline_successes']['496']['raw']['path']).read_bytes())
    actual=deepcopy(replay['PFS_parameters']); actual['voxelsize']=.25
    ck('k496実166項でvoxelのみ許容', core.same_parameters_except_voxel(replay['PFS_parameters'], actual)['passed'])
    for key in ('particlesep','dofinalsmooth'):
        mutant=deepcopy(actual); mutant[key]=actual[key]+.01
        ck('k496実166項の追加差拒否:'+key, not core.same_parameters_except_voxel(replay['PFS_parameters'],mutant)['passed'])
    mutant=deepcopy(actual); mutant.pop('voxelsize')
    ck('k496実設定の欠損拒否', not core.same_parameters_except_voxel(replay['PFS_parameters'],mutant)['passed'])
    ck('旧k496 native全3点は05と一致', [baseline['profiles'][i]['native_default_first'] for i in centers] == replay['native_original'])
    ck('二つのsolver観測定義を原値のまま保持', all(
        baseline['profiles'][i]['center_original_gauge_replay']['eta_m'] == plan['record']['gauges'][j]['eta_m']
        and baseline['profiles'][i]['field_profile']['height_m'] != plan['record']['gauges'][j]['eta_m']
        for j, i in enumerate(centers)))
    ck('実基線PFS全166項', len(replay['PFS_parameters']) == plan['expected_evaluated_PFS_parameter_count'] == 166)
    for key in ('sha256', 'original_sha256', 'bytes', 'original_bytes'):
        row = deepcopy(plan['profile05_baseline']); row[key] = 0 if key.endswith('bytes') else '0' * 64
        try: contract.read_profile_baseline08(ROOT, row); refused = False
        except AssertionError: refused = True
        ck('公開gzip原/圧縮bytesSHA拒否:' + key, refused)
    ck('06純query判定はbyte同一', sha(C / 'Source/refine_core06.py') == sha(ROOT / plan['source_comparison_candidate'] / 'Source/refine_core06.py'))
    ck('旧.5原plan SHA', sha(ROOT / plan['comparison_plan']['path']) == plan['comparison_plan']['sha256'])
    for key, row in plan['validated_refine474'].items():
        ck('実測07成功記録を保護:' + key, sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes'])
    success = json.loads((ROOT / plan['validated_refine474']['execution.json']['path']).read_bytes())
    ck('07はUI18復元済み実成功', success['passed_for_review'] and success['cleanup']['all_ui_and_owned_node_checks_passed']
       and not success['transport_completion_uncertain'])
    # ローカルSource moduleがHoudini側に無い独立namespaceを模擬する。
    combined = '\n'.join((C / 'Source' / name).read_text(encoding='utf8') for name in
                         ('replay_support06.py', 'replay_window06.py', 'refine_core06.py', 'refine_contract08.py', 'refine_k496.py'))
    local_names = {p.stem for p in (C / 'Source').glob('*.py')}
    original_import = builtins.__import__
    def controlled_import(name, *args, **kwargs):
        if name in local_names: raise ImportError('RPC側にローカルmoduleは無い')
        return original_import(name, *args, **kwargs)
    namespace = {'hou': object()}
    with patch.object(builtins, '__import__', controlled_import):
        exec(compile(combined, '<fresh-houdini-namespace>', 'exec'), namespace)
    ck('実RPC結合sourceはローカルmodule依存なし', callable(namespace['refine_k496']) and namespace['target08'](plan))
    ck('RPC内署名比較は型差を拒否', not namespace['typed_equal08']({'x':1}, {'x':True}))
    isolated = """import json,sys
class NoHOM:
    def __getattr__(self,name):raise AssertionError('離線中のHOM呼出し禁止')
namespace={'hou':NoHOM()}
exec(compile(sys.stdin.read(),'<isolated-rpc-definitions>','exec'),namespace)
print(json.dumps({'defined':callable(namespace['refine_k496']), 'sys_path':sys.path}))
"""
    with tempfile.TemporaryDirectory(prefix='gw08_namespace_', dir=str(C.parents[1])) as temporary:
        child = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', '-c', isolated], input=combined,
                               cwd=temporary, capture_output=True, text=True, encoding='utf8', check=True)
    child_report = json.loads(child.stdout)
    ck('隔離子processにSourceパスなし/実HOMアクセスなし', child_report['defined']
       and str(C / 'Source') not in child_report['sys_path'] and '' not in child_report['sys_path'])
    command = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(C / 'Source/run_refine08.py')],
                             capture_output=True, text=True, encoding='utf8', check=True)
    default = json.loads(command.stdout)
    ck('既定入口はk496表示だけ', default == {'houdini_called':False, 'sample':496,
       'scope':'ONE_K496_QUARTER_MESH_SENSITIVITY_ONLY', 'houdini_execution_allowed_by_default':False, 'refinement_allowed':True})
    ck('原frame式との差を隠さず規定内で照合', plan['global_frame'] != 1 + (496 / 60) * 24
       and abs(plan['global_frame']-(1+(496/60)*24)) == plan['frame_contract']['original_formula_difference_frames']
       and abs(plan['global_frame']-(1+(496/60)*24)) < plan['frame_contract']['assert_tolerance_frames'])
    for name in ('profile_core.py', 'read_profile05.py', 'replay_support06.py', 'replay_window06.py', 'refine_core06.py'):
        ck('検証済み06実装のbyte維持:' + name,
           sha(C / 'Source' / name) == sha(ROOT / plan['source_comparison_candidate'] / 'Source' / name))


def run_checks():
    checks = []
    def ck(name, value):
        assert value, name
        checks.append({'name': name, 'passed': True})
    plan = json.loads((C / 'Source/refine_plan.json').read_bytes())
    ck('k496 .25単一対象', plan['sample'] == 496 and plan['global_frame'] == (1 + .4 * 496) and plan['fps'] == 24
       and plan['scope'] == 'ONE_K496_QUARTER_MESH_SENSITIVITY_ONLY' and plan['mesh_parameters']['voxelsize'] == .25)
    ck('他時刻solver detector禁止', not plan['other_samples_allowed'] and not plan['new_solver'] and not plan['detector_executed'])
    prior_path = C / 'Evidence/22_prior_attempts_manifest.json'; prior = json.loads(prior_path.read_bytes())
    ck('先行資料の全ファイル保護一覧SHA', sha(prior_path) == plan['prior_attempts_manifest_sha256'] and prior['file_count'] == plan['preserved_file_count'])
    paths = {p.relative_to(ROOT).as_posix() for d in prior['protected_directories'] for p in (ROOT / d).rglob('*') if p.is_file()} | set(prior['protected_files'])
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
        ck('原k496 cache:' + kind, sha(p) == x['sha256'] and p.stat().st_size == x['bytes'])
    base_plan = json.loads((ROOT / plan['comparison_plan']['path']).read_bytes())
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
                 'old_budget_hold', 'old_published_mismatch', 'new_hold', 'uncertain_mesh', 'uncertain_old'):
        calls, r = mock_orchestration(mode)
        ck('mock終了:' + mode, r['passed_for_review'] is (mode == 'success'))
        if mode in ('mesh_hold', 'nonfinite_mesh', 'cleanup_fail', 'uncertain_mesh'): ck('profile未開始:' + mode, not any(x.startswith('READ_ONLY') for x in calls))
        if mode in ('old_hold', 'old_metadata_changed', 'old_budget_hold', 'old_published_mismatch', 'uncertain_old'):
            ck('旧FAIL後新禁止:' + mode, 'READ_ONLY_PROFILE_NEW' not in calls)
        if mode == 'old_budget_hold': ck('容量HOLDのACKをexecutionへ保持', r['profiles']['old']['ack']['json_written'] is False)
        if mode == 'uncertain_mesh': ck('不明時cleanup禁止', 'RESTORE_UI18' not in calls and r['transport_completion_uncertain'])
        if mode == 'uncertain_old': ck('読戻し不明後追加RPCなし', calls[-1] == 'READ_ONLY_PROFILE_OLD' and r['transport_completion_uncertain'])
        if mode == 'success': ck('UI復元後だけ旧→新', calls[-3:] == ['RESTORE_UI18','READ_ONLY_PROFILE_OLD','READ_ONLY_PROFILE_NEW'])
    source = (C / 'Source/refine_k496.py').read_text(encoding='utf8')
    ck('native前mesh保存', source.index('save_generated()\n            health()') < source.index("record['native_original'] = []"))
    ck('旧新完全mesh一致は観測だけ', "record['old_new_mesh_comparison_diagnostic_only']" in source and "record['mesh_parity']['passed']" not in source)
    ck('入力全署名と定義全比較', "baseline_input_canonical_equal" in source and "record['parameter_pair']['passed'] and record['definition_equal'] and record['convert_equal']" in source)
    tree = ast.parse(source)
    capture = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'capture_mesh')
    capture_source = ast.get_source_segment(source, capture)
    ck('第二AutoはOutのみforce', capture_source.count('.cook(force=True)') == 1 and "nodes['OUT'].cook(force=True)" in capture_source)
    combined = '\n'.join((C / 'Source' / n).read_text(encoding='utf8') for n in ('replay_support06.py','replay_window06.py','refine_core06.py','refine_contract08.py','refine_k496.py'))
    ns = {'hou': object()}; exec(compile(combined, '<offline-definitions>', 'exec'), ns)
    ck('独立namespaceで定義のみ', all(callable(ns[n]) for n in ('refine_k496','same_parameters_except_voxel','all_geometry_signature06','parameters06')))
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
    additional_checks08(ck, plan)
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
