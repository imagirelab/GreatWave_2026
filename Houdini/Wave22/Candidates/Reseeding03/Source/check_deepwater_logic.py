"""合成値と公開JSONだけの試験。HOM/MCP、実BGEO読込、旧証拠への書込みをしない。"""
import ast
import copy
import hashlib
import importlib.util
import json
import math
import platform
import random
import statistics
import tempfile
import time
from pathlib import Path

from deepwater_core import (ParticleSupport, compare_coverage, compare_initial_pair,
                            digest, fixed_points, inspect_points, squared_distance)
from run_baseline_readback import build_probe_code
from reseeding_policy import next_decision

ROOT=Path(__file__).resolve().parents[1]
WAVE=Path(__file__).resolve().parents[3]
checks=[]


def check(name, passed):
    assert passed,name
    checks.append({'name_ja':name,'passed':True})


def rejects(function, kind=ValueError):
    try:
        function()
    except kind:
        return True
    return False


points=fixed_points()
check('固定格子は99×8×9の7128点',len(points)==7128 and len(set(points))==7128)
check('範囲と順序は整数cmから固定',points[0]==(.06,-.54,-.24) and points[-1]==(5.94,-.12,.24))
rng=random.Random(2203)
cloud=[tuple(rng.uniform(-.4,.4) for _ in range(3)) for _ in range(311)]
index=ParticleSupport(cloud)
maximum_distance_error=0.
for q in [tuple(rng.uniform(-.6,.6) for _ in range(3)) for _ in range(96)]:
    got=index.query(q)
    values=[squared_distance(q,p) for p in cloud]
    maximum_distance_error=max(maximum_distance_error,abs(got['nearest_particle_distance_m']-math.sqrt(min(values))))
    assert got['count_within_radius']==sum(v<=.08**2 for v in values)
check('乱数96照会を全距離走査と照合',maximum_distance_error<1e-14)
check('半径ちょうどの支持を含む',ParticleSupport([(.08,0,0)]).query((0,0,0))['count_within_radius']==1)
check('半径外の最近距離を丸めない',ParticleSupport([(2,0,0)]).query((0,0,0))=={'count_within_radius':0,'nearest_particle_distance_m':2.})
check('負座標のcellを正しく探索',ParticleSupport([(-.081,0,0)]).query((-.001,0,0))['count_within_radius']==1)
check('空粒子は拒否',rejects(lambda:ParticleSupport([])))
check('非有限粒子は拒否',rejects(lambda:ParticleSupport([(float('nan'),0,0)])))
bounds={'min':[-1,-1,-1],'max':[1,1,1]}
one=[(0,0,0)]
positive=inspect_points(lambda p:.01,bounds,one,points=one)
negative_empty=inspect_points(lambda p:-.1,bounds,[(.5,.5,.5)],points=one)
check('正SDFと支持ありを独立警報',positive['category_counts']['nonnegative_with_support']==1 and positive['observations_valid'])
check('負SDFと支持0を独立警報',negative_empty['category_counts']['negative_without_support']==1 and negative_empty['observations_valid'])
outside=inspect_points(lambda p:(_ for _ in ()).throw(AssertionError('field外sample禁止')),bounds,one,points=[(2,0,0)])
check('field外でsampleを呼ばず無効',not outside['observations_valid'] and outside['rows'][0]['phi_m'] is None)
nan=inspect_points(lambda p:float('nan'),bounds,one,points=one)
check('非有限を0へ補わず無効とJSON保存',not nan['observations_valid'] and json.dumps(nan,allow_nan=False))
negative=inspect_points(lambda p:-.1,bounds,one,points=one)
check('一粒子ありを無空洞合格としない',negative['registered_points_all_negative_and_supported'] and not negative['physical_no_void_pass'])
check('低い非ゼロ支持は警報にしない',not negative['coverage_alarm_point_indices'])
tick=iter([0.,91.])
check('観測時間予算で停止',rejects(lambda:inspect_points(lambda p:-.1,bounds,one,points=one,clock=lambda:next(tick)),TimeoutError))
groups=compare_coverage(positive['rows'],negative_empty['rows'])
check('ON/OFF共有警報を新規警報としない',groups=={'shared_baseline_and_off':[0],'baseline_only':[],'off_only':[]})
check('無効fieldを警報差比較へ混ぜない',rejects(lambda:compare_coverage(nan['rows'],negative['rows'])))
identity={'particle_count':1,'ID_unique':True,'sorted_ID_P_sha256':'p','sorted_ID_v_sha256':'v',
          'sorted_ID_pscale_sha256':'s','pscale_min_max_m':[.048,.048],
          'surface_pressure_initial_fields':{'surface':{'transform':[1.]},'pressure':{'all_voxels_sha256':'x'}}}
check('初態の全項目一致だけを配対PASS',compare_initial_pair(identity,copy.deepcopy(identity))['strict_pair_matched'])
for key in ('sorted_ID_P_sha256','sorted_ID_v_sha256','sorted_ID_pscale_sha256','surface_pressure_initial_fields'):
    changed=copy.deepcopy(identity);changed[key]='different'
    check('初態差を拒否 '+key,not compare_initial_pair(identity,changed)['strict_pair_matched'])

# 新規namespaceへ連結するコードを構文検査し、Houdini APIは模擬の読戻し入口へ置換する。
adapter=(ROOT/'Source/readback_deepwater.py').read_text(encoding='utf8')
core=(ROOT/'Source/deepwater_core.py').read_text(encoding='utf8')
namespace={}
exec(compile(core+'\n'+adapter,'combined_reader','exec'),namespace)
check('読戻し定義はhouなし独立namespaceで構築可能',callable(namespace['read_cached_probe']))
class Point:
    def __init__(self,n):self.n=n
    def number(self):return self.n
class Vertex:
    def point(self):return Point(0)
class Primitive:
    def vertices(self):return [Vertex()]
class Geometry:
    def prims(self):return [Primitive()]
    def points(self):return [Point(0),Point(1),Point(2)]
real,held=namespace['_real_particles'](Geometry())
check('Volume保持点を粒子支持から除外',held==1 and [p.number() for p in real]==[1,2])
rpc,source_sha=build_probe_code(core,adapter,123,Path('sample.bgeo.sc'),'fake',0,2,Path('new.json'))
tree=ast.parse(rpc)
check('RPCは独立したimportと全関数を含む',{'read_cached_probe','inspect_points'} <= {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)})
forbidden=('setFrame','setFps','createNode','cook','load','save','clear')
calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
check('RPCに時刻/ノード/solver/HIP変更APIなし',not any(name in calls for name in forbidden))
check('RPC戻り値はJSON/source SHAのみ',"result={'json_sha256':" in rpc and "'source_sha256':" in rpc)

# 実ファイルではない小さなfixtureと模擬Volumeで、RPC全体を新規namespaceへ一度だけ実行する。
class Box:
    def minvec(self):return (0.,-.6,-.3)
    def maxvec(self):return (6.,.1,.3)
class Matrix:
    def asTuple(self):return (1.,0.,0.,0.,1.,0.,0.,0.,1.)
class FluidPoint:
    def __init__(self,n,p):self.n,self.p=n,p
    def number(self):return self.n
    def position(self):return self.p
    def attribValue(self,key):return {'id':self.n,'v':(0.,0.,0.),'pscale':.048}[key]
class Volume:
    def __init__(self,name):self.name=name
    def attribValue(self,key):return self.name
    def type(self):return 'Volume'
    def vertices(self):return []
    def indexToPos(self,index):return tuple((.03,-.57,-.27)[a]+index[a]*.06 for a in range(3))
    def boundingBox(self):return Box()
    def resolution(self):return (100,12,10)
    def voxelSize(self):return (.06,.06,.06)
    def transform(self):return Matrix()
    def isSDF(self):return self.name=='surface'
    def allVoxels(self):return (-.1,.1) if self.name=='surface' else (0.,0.)
    def sample(self,p):return p[1]
class FakeGeometry:
    def loadFromFile(self,path):self.loaded=path
    def findPrimAttrib(self,name):return True
    def findPointAttrib(self,name):return True
    def prims(self):return [Volume('surface'),Volume('pressure')]
    def points(self):return [FluidPoint(i,p) for i,p in enumerate(points)]
class FakeHip:
    def hasUnsavedChanges(self):return True
class FakeHou:
    Volume=Volume
    Geometry=FakeGeometry
    hipFile=FakeHip()
    def isUIAvailable(self):return True
    def frame(self):return 17.
    def fps(self):return 24.
    def updateModeSetting(self):return 'Manual'
import os
temp_root=WAVE/'Local_Reproduction';temp_root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='deepwater_mock_',dir=temp_root) as folder:
    fixture=Path(folder)/'synthetic.bin';fixture.write_bytes(b'not a real BGEO')
    destination=Path(folder)/'probe.json'
    code,code_sha=build_probe_code(core,adapter,os.getpid(),fixture,hashlib.sha256(fixture.read_bytes()).hexdigest(),0,len(points),destination)
    fresh={'hou':FakeHou()}
    exec(compile(code,'synthetic_rpc','exec'),fresh)
    readback=json.loads(destination.read_text(encoding='utf8'))
    check('RPCをhouだけの新規namespaceで模擬実行',readback['deepwater']['query_count']==7128 and readback['ui_metadata_unchanged'])
    check('模擬RPCは原JSON SHAへ結合',fresh['result']['json_sha256']==hashlib.sha256(destination.read_bytes()).hexdigest() and fresh['result']['source_sha256']==code_sha)
    check('キャッシュhash不一致は読戻し拒否',rejects(lambda:namespace['read_cached_probe'](FakeHou(),fixture,'bad',0,len(points))))

plan=json.loads((ROOT/'Source/reseeding03_plan.json').read_text(encoding='utf8'))
check('6時刻を固定しPASSでも駆動しない',plan['checkpoint_samples']==[0,30,180,270,315,360] and plan['stop_s']==6 and not plan['drive_even_if_static_passed'])
check('警報を保持して固定t6まで継続',plan['coverage_alert_latched_continue_to_s']==6 and '保存して停止' not in plan['stop_rules_ja'][2])
spec=importlib.util.spec_from_file_location('gate',WAVE/'Source/checkpoint_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
sample_path=WAVE/'Evidence/Curated_Runs/db52394211/22_pilot_samples.json'
condition_path=sample_path.with_name('22_pilot_conditions.json')
rows=json.loads(sample_path.read_text(encoding='utf8'))['samples']
conditions=json.loads(condition_path.read_text(encoding='utf8'))
measured_gate=gate.evaluate_gate(rows,conditions,6.)
original_gate=json.loads(sample_path.with_name('22_checkpoint_gate.json').read_text(encoding='utf8'))
check('公開L6 fixtureの元静水FAILを保持',not measured_gate['diagnostic_stability_passed'] and measured_gate['gauge_checks']==original_gate['gauge_checks'])
alert=False
for k in range(361):
    decision=next_decision(k,True,True,True,alert,k==30,False if k==360 else None)
    alert=decision['coverage_alert_latched']
    assert not decision['drive_authorized']
    assert decision['action']==('FINISH_STATIC_DIAGNOSTIC' if k==360 else 'CONTINUE_TO_FIXED_ENDPOINT')
check('途中被覆警報を保持して全361点まで続行',alert and decision['next_sample'] is None)
check('静水PASSでも駆動を許可しない',not next_decision(360,True,True,True,False,False,True)['drive_authorized'])
check('初態不一致は停止',next_decision(0,False,True,True,False,False)['action']=='STOP_INITIAL_PAIR_MISMATCH')
check('場外非有限は停止',next_decision(30,True,False,True,False,False)['action']=='STOP_INVALID_FIELD')
check('元の資源安全違反は停止',next_decision(30,True,True,False,False,False)['action']=='STOP_ORIGINAL_SAFETY_GUARD')

# 54,000点の明示的な合成分布で単一ファイルの探索部分だけを測る。実BGEO/HOMの費用ではない。
synthetic=[(.02+i*.04,-.59+j*(.58/17),-.285+k*.03) for i in range(150) for j in range(18) for k in range(20)]
started=time.monotonic()
benchmark=inspect_points(lambda p:p[1],{'min':[-.1,-.7,-.4],'max':[6.1,.1,.4]},synthetic)
elapsed=time.monotonic()-started
check('全7128点の合成負SDF/支持を測定',benchmark['registered_points_all_negative_and_supported'] and benchmark['query_count']==7128)
manifest=json.loads((WAVE/'Evidence/Length6_Result_db52394211/22_cache_manifest.json').read_text(encoding='utf8'))
selected=[r for r in manifest['cache_files'] if r['kind']=='solver_fields_and_particles' and r['sample'] in plan['checkpoint_samples']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={'houdini_or_mcp_called':False,'real_bgeo_decoded':False,'checks':checks,'passed':True,
 'point_count':len(points),'point_order_sha256':digest(points),'random_bruteforce_max_distance_error_m':maximum_distance_error,
 'source_hashes':{p.name:sha(p) for p in sorted((ROOT/'Source').glob('*')) if p.is_file()},
 'baseline_samples_sha256':sha(sample_path),'baseline_conditions_sha256':sha(condition_path),
 'synthetic_cost':{'particle_count':len(synthetic),'query_count':7128,'elapsed_seconds':elapsed,
                   'occupied_hash_cells':benchmark['occupied_hash_cells'],'fallback_queries':benchmark['nearest_fallback_queries'],
                   'support_count_distribution':benchmark['support_count_distribution'],
                   'excludes_ja':'実BGEOのdecode、HOMの7128回sample、MCP、JSON書込みを含まない。実測上限の保証ではない。'},
 'single_file_estimate':{'sample0_cache_bytes_from_published_manifest':next(r['bytes'] for r in selected if r['sample']==0),
                       'six_cache_bytes_from_published_manifest':sum(r['bytes'] for r in selected),
                       'first_actual_readback_sample':0,'real_readback_seconds_unmeasured':True,
                       'reader_seconds_budget':90,'client_timeout_seconds':180,
                       'strategy_ja':'承認後にt0一件だけ順次読戻しし、実費用/JSONサイズと有効性を報告してから残り5件を判断する。'},
 'python':platform.python_version(),'limitations_ja':'合成探索の数値検査であり、保存水槽の深水被覆やHOM互換性は未検証。'}
(ROOT/'Evidence/22_reseeding03_offline_checks.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'checks':len(checks),'passed':True,'synthetic_seconds':elapsed,'houdini_called':False},ensure_ascii=False))
