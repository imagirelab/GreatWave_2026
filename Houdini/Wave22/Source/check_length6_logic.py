"""公開t6の読戻しと明示合成fieldでL6の停止・RPC定義を検査。Houdiniは呼ばない。"""
import ast
import asyncio
import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from checkpoint_gate import evaluate_gate, run_phases
from grid_metrics_l6 import mirror_metric, wall_pairs
from run_length6 import read_exact_record

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Source'
DEST = ROOT / 'Evidence/Length6_Planned'
DEST.mkdir(exist_ok=True)
fixture = ROOT / 'Evidence/Curated_Runs/3e5ff87a29'
load = lambda p: json.loads(p.read_text(encoding='utf8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = [fixture/n for n in ('22_pilot_samples.json', '22_pilot_conditions.json', '22_checkpoint_gate.json')]
before = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
samples, conditions, saved = load(inputs[0])['samples'], load(inputs[1]), load(inputs[2])
plan = load(SOURCE/'length6_plan.json')
checks = []


def record(name, passed, **details):
    assert passed, name
    checks.append({'check': name, 'passed': True, **details})


def rejects(name, function):
    try:
        function()
    except (AssertionError, ValueError, KeyError):
        record(name, True)
    else:
        raise AssertionError(name)


actual = evaluate_gate(samples, conditions, 6)
record('公開t6の全統計を精値のまま再現', all(actual[k] == saved[k] for k in actual))
record('元G3傾きのFAILを維持', not actual['diagnostic_stability_passed'] and
       [r['both_trend_passed'] for r in actual['gauge_checks']] == [True, True, False])
record('計画は固定2窓と旧測点のλを保持', plan['static_gate_windows_seconds'] == [[4.5, 5.25], [5.25, 6]]
       and plan['tank_inner_length_m'] == 6 and plan['wavelength_m'] == 2.9903951732918226)
record('初期粒子は旧P/IDとの一致対象外', plan['initial_P_ID_match_old_required'] is False)


async def flow(rows, expected):
    calls, permits = [], []
    async def one(k):
        calls.append(k)
    async def decide():
        return evaluate_gate(rows, conditions, 6)
    async def authorize(result):
        assert result['diagnostic_stability_passed']
        permits.append(len(calls))
    result = await run_phases(one, decide, authorize, 360, 570)
    record('同DOP分岐の模擬検査PASS=' + str(expected),
           calls == list(range(571 if expected else 361)) and permits == ([361] if expected else [])
           and result['drive_authorized'] == expected)


asyncio.run(flow(samples, False))
synthetic = copy.deepcopy(samples)
for row in synthetic:
    for gauge in row['gauges']:
        gauge['eta_m'] = -.005
    row['negative_voxel_volume_proxy_m3'] = 2.3
asyncio.run(flow(synthetic, True))
record('鏡像ラベルが良くても実静水FAILは変わらない', mirror_metric(-.18, .06, 6)['mirror_compatible_label']
       and not evaluate_gate(samples, conditions, 6)['diagnostic_stability_passed'])
old_metric = mirror_metric(-.18, .06, plan['reference_length_m'])
record('旧長の解析格子例は非鏡像', abs(old_metric['Eg_cells']-.3201608902725934) < 1e-10)
record('整数indexだけ中心をずらしてもEg不変', abs(mirror_metric(.42, .06, 6)['Eg_cells']) < 1e-12)
rejects('格子の非有限値を拒否', lambda: mirror_metric(float('nan'), .06, 6))
rejects('零voxelを拒否', lambda: mirror_metric(0, 0, 6))
box = {'min': [-.3, -.6, -.3], 'max': [6.3, 0, .3]}
ideal = lambda p: min(p[0], 6-p[0])
wall = wall_pairs(ideal, box, 6, .06, plan['collision_probe'])
record('明示合成の左右壁81対と18根', wall['pair_count'] == 81 and len(wall['wall_roots']) == 18
       and wall['maximum_absolute_difference_m'] < 1e-12
       and all(abs(r['d_from_nominal_wall_m']) < 1e-5 for r in wall['wall_roots']))
shifted = wall_pairs(lambda p: min(p[0]-.01, 6-p[0]), box, 6, .06, plan['collision_probe'])
record('壁鏡像不一致は測定値として保持し物理許可にしない', shifted['maximum_absolute_difference_m'] > .009
       and shifted['physical_pass'] is False)
rejects('欠けた壁を拒否', lambda: wall_pairs(lambda p: 1, box, 6, .06, plan['collision_probe']))
rejects('field外を拒否', lambda: wall_pairs(ideal, {'min':[0,-.6,-.3], 'max':[6,0,.3]}, 6, .06, plan['collision_probe']))
rejects('非有限SDFを拒否', lambda: wall_pairs(lambda p: float('nan'), box, 6, .06, plan['collision_probe']))

generator = (SOURCE/'generate_wave_l6.py').read_text(encoding='utf8')
old_generator = (SOURCE/'generate_wave.py').read_text(encoding='utf8')
def physical_calls(text):
    tree = ast.parse(text)
    return [ast.dump(n, include_attributes=False) for n in ast.walk(tree) if isinstance(n, ast.Call)
            and ((isinstance(n.func, ast.Name) and n.func.id in ('setp','sett','box'))
                 or (isinstance(n.func, ast.Attribute) and n.func.attr in ('setInput','setExpression','createNode')))]
record('Lと新初態保護以外のノード設定式は同じ', physical_calls(generator) == physical_calls(old_generator))
record('旧初態一致を要求せず健全性assertを残す', 'INITIAL_REFERENCE_CACHE' not in generator
       and 'assert len(points)>0 and initial_finite and initial_inside and initial_unique' in generator)
runner = (SOURCE/'run_length6.py').read_text(encoding='utf8')
tree = ast.parse(runner)
def rpc_text(label, variables):
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'execute' and isinstance(n.args[0], ast.Constant) and n.args[0].value == label)
    return eval(compile(ast.Expression(call.args[1]), '<独立RPC>', 'eval'), variables)


state = {'fps':24, 'dop':SimpleNamespace(sessionId=lambda:77, simulation=lambda:SimpleNamespace(time=lambda:6.0))}
key = '_length6_dry'
fake_hou = SimpleNamespace(VDB=type('FakeVDBType', (), {}), session=SimpleNamespace(**{key:state}), fps=lambda:24, isUIAvailable=lambda:True)
local = ROOT/'Local_Reproduction'
local.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='length6_namespace_', dir=local) as folder:
    out = Path(folder)
    (out/'Evidence').mkdir()
    namespace = {'hou':fake_hou, 'EXPECTED_PID':os.getpid(), 'STAGE':str(out), 'KEY':key, 'PHASE':'register_checkpoint'}
    exec(rpc_text('同一DOPと資源基線を登録', {'source':generator}), namespace)
    record('所有基線RPCは新namespaceで自足', namespace['result']['dop_session_id'] == 77)
    for passed, rows in ((False, samples), (True, synthetic)):
        state['samples'] = rows
        state['checkpoint_drive_authorized'] = False
        cp, sp = out/'Evidence/22_pilot_conditions.json', out/'Evidence/22_pilot_samples.json'
        cp.write_text(json.dumps(conditions), encoding='utf8')
        sp.write_text(json.dumps({'samples':rows}), encoding='utf8')
        hashes = {'sample_sha256':sha(sp), 'conditions_sha256':sha(cp)}
        text = rpc_text('t6全条件合格後の同一DOP続行許可',
                        {'policy':(SOURCE/'checkpoint_gate.py').read_text(encoding='utf8'), 'gate':hashes})
        try:
            exec(text, {'hou':fake_hou, 'KEY':key, 'STAGE':str(out), 'STATIC_LAST':360})
        except AssertionError:
            assert not passed
        record('許可RPCは原JSON・新namespaceで再判定: '+str(passed), state['checkpoint_drive_authorized'] == passed)
    ack = {'json_sha256':sha(cp), 'source_sha256':'合成試験'}
    record('原JSONの精値と出典照合を保持', read_exact_record(cp, ack, '合成試験') == conditions)
    rejects('原JSON SHA改変を拒否', lambda:read_exact_record(cp, {**ack,'json_sha256':'bad'}, '合成試験'))

    # 実probeの定義を空namespaceで評価し、偽Volumeの中心を使う。HOMの実行検証ではない。
    metrics = (SOURCE/'grid_metrics_l6.py').read_text(encoding='utf8')
    probe = (SOURCE/'probe_grid_l6.py').read_text(encoding='utf8')
    definitions = {'hou':fake_hou, 'PHASE':'dry_definitions'}
    exec(metrics+'\n'+probe, definitions)
    class FakeVolume:
        def indexToPos(self, index): return tuple(-.18+v*.06 for v in index)
        def boundingBox(self): return SimpleNamespace(minvec=lambda:(-.21,-.6,-.3), maxvec=lambda:(6.21,.3,.3))
        def resolution(self): return (107,15,10)
        def type(self): return '明示合成Volume'
        def attribValue(self, name): return 'pressure'
        def voxelSize(self): return (.06,.06,.06)
        def transform(self): return SimpleNamespace(asTuple=lambda:(.06,0,0,0,.06,0,0,0,.06))
        def isSDF(self): return False
    row = definitions['describe_grid'](FakeVolume(), '合成試験', 6)
    record('probe関数は新namespaceでindexToPos中心を使用', row['index_000_cell_center_m'][0] == -.18
           and row['bounds']['min'][0] == -.21 and row['mirror_label_applicable'])
    class FakeEmptyVDB(FakeVolume, fake_hou.VDB):
        def isEmpty(self): return True
        def activeVoxelCount(self): return 0
        def resolution(self): return (0,0,0)
        def indexToPos(self, index): raise AssertionError('空VDBの中心は照会禁止')
        def activeVoxelBoundingBox(self): raise AssertionError('空VDBのbboxは照会禁止')
    empty = definitions['describe_grid'](FakeEmptyVDB(), '空velの合成試験', 6)
    record('空velは中心/bbox/Egを照会せず背景専用とする', empty['is_empty_vdb']
           and empty['mirror'] is None and empty['bounds'] is None and not empty['mirror_label_applicable'])
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'execute' and isinstance(n.args[0], ast.BinOp)
                and isinstance(n.args[0].left, ast.Constant) and n.args[0].left.value == '所有場の格子・壁観測 ')
    filename = 'mock_grid.json'
    (out/'Evidence'/filename).write_bytes(b'{"mock_only":true}\n')
    variables = {'source':generator,'probe_code':metrics+'\n'+probe,'filename':filename}
    exact_rpc = eval(compile(ast.Expression(call.args[1]), '<grid RPC>', 'eval'), variables)
    fresh = {'hou':fake_hou,'PHASE':'dry_definitions','KEY':key,'STAGE':str(out),'EXPECTED_PID':os.getpid()}
    exec(exact_rpc, fresh)
    record('格子RPC全体は独立namespaceと精値ACKで自足',
           fresh['result']['json_sha256'] == sha(out/'Evidence'/filename)
           and fresh['result']['source_sha256'] == hashlib.sha256(variables['probe_code'].encode('utf8')).hexdigest())

    sample_function = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'sample_one')
    assignment = next(n for n in sample_function.body if isinstance(n, ast.Assign) and n.targets[0].id == 'wrapper')
    stub = "import json\nfrom pathlib import Path\ns=getattr(hou.session,KEY)\n" + \
           "def write(n,v): (Path(STAGE)/'Evidence'/n).write_text(json.dumps(v),encoding='utf8')\n" + \
           'result=' + repr(synthetic[0]) + "\ns['samples'].append(result)\nwrite('22_pilot_samples.json',{'samples':s['samples']})\n"
    wrapper = eval(compile(ast.Expression(assignment.value), '<sample RPC>', 'eval'),
                   {'policy':(SOURCE/'checkpoint_gate.py').read_text(encoding='utf8'),'source':stub,'index':0})
    state.update(samples=[], checkpoint_trace=[], checkpoint_drive_authorized=False)
    state['dop'].evalParm = lambda name: 768 if name == 'cachemaxsize' else 0
    fresh = {'hou':fake_hou,'KEY':key,'STAGE':str(out),'STATIC_LAST':360,'FINAL_LAST':570,
             'BUDGET':plan['resource_budget'],'hashlib':hashlib}
    # 本番sourceがimportするhashlibも明示合成source側へ入れ、空namespaceから検査する。
    del fresh['hashlib']
    stub = 'import hashlib\n'+stub
    wrapper = eval(compile(ast.Expression(assignment.value), '<sample RPC>', 'eval'),
                   {'policy':(SOURCE/'checkpoint_gate.py').read_text(encoding='utf8'),'source':stub,'index':0})
    exec(wrapper, fresh)
    record('標本wrapperの独立namespaceと資源・SHA経路', fresh['result']['sample'] == 0
           and len(state['checkpoint_trace']) == 1 and not state['checkpoint_drive_authorized'])

for name in ('run_length6.py','generate_wave_l6.py','probe_grid_l6.py','grid_metrics_l6.py','check_length6_logic.py'):
    compile((SOURCE/name).read_text(encoding='utf8'), name, 'exec')
record('新規ソースの構文', True)
record('新規probeの順番が0→半標本→1標本', "await grid_probe('grid_new:0')" in runner
       and "await grid_probe('grid_new:' + repr(1/120))" in runner
       and "elif index == 1:" in runner and "elif index == 30:" in runner)
record('作成前Manualとframe1の既存保護を保持', 'hou.setUpdateMode(hou.updateMode.Manual)' in runner and 'hou.setFrame(1)' in runner)
record('元fixtureは無変更', before == {str(p.relative_to(ROOT)):sha(p) for p in inputs})
sources = ['run_length6.py','generate_wave_l6.py','length6_plan.json','probe_grid_l6.py','grid_metrics_l6.py',
           'check_length6_logic.py','checkpoint_gate.py','ui_guard.py']
result = {'houdini_called':False,'new_fluid_simulated':False,'old_BGEO_HOM_read':False,
          'scope_ja':'公開t6原JSONと明示合成field/namespaceだけ。実HOM互換性・L6の鏡像や静水は未検証。',
          'input_sha256':before,'checks':checks,'passed':True,
          'source_sha256':{n:sha(SOURCE/n) for n in sources}}
(DEST/'22_length6_logic_checks.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'checks':len(checks),'passed':True,'houdini_called':False}))
