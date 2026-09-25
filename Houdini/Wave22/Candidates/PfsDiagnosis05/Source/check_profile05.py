"""05候補の合成・公開JSON・独立namespace試験。hou/MCPを呼ばない。"""
import ast
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import random
import statistics
import time
from pathlib import Path

import profile_core as core
import run_profile05 as runner

HERE=Path(__file__).parent;CANDIDATE=HERE.parent;WAVE=CANDIDATE.parents[1]
parser=argparse.ArgumentParser(description='既定は保存証拠を変更しない離線検査。証拠更新は明示フラグだけ。')
parser.add_argument('--update-evidence',action='store_true',help='今回の計測値と源SHAで証拠を明示更新する')
args=parser.parse_args()
BASE=WAVE/'Candidates/WaveStart04/Evidence/Result_22e7801642'
PLAN=json.loads((HERE/'profile05_plan.json').read_bytes());CHECKS=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,truth):
    assert truth,name;CHECKS.append({'name':name,'passed':True})
def raises(name,fn,error=ValueError):
    try:fn()
    except error:check(name,True)
    else:raise AssertionError(name)
positions=core.registered_positions(PLAN['gauge_x_m'])
check('195断面・原中央3点',len(positions)==195 and sum(p['dx_m']==p['z_m']==0 for p in positions)==3)
check('30時刻5850断面',len(PLAN['pairs'])==30 and PLAN['total_profiles']==195*30)
check('固定偶数時刻7p8から8p7667',[r['sample']for r in PLAN['pairs']]==list(range(468,527,2)))
check('60ファイル容量',[PLAN['budgets']['input_total_bytes']]==[sum(r['cache_total_bytes']for r in PLAN['pairs'])])
bounds={'min':[-1,-.8,-1],'max':[7,.4,1]}
plane=core.sign_profile(lambda p:p[1]-.013,3.,0.,bounds)
check('平水面符号根',plane['single_wet_to_dry_local']and abs(plane['height_m']-.013)<=1e-6)
check('原上界p25まで',plane['y_m'][-1]==.25 and plane['y_m'][0]==-.5999)
clipped=core.sign_profile(lambda p:p[1],3.,0.,{'min':[-1,-.8,-1],'max':[7,.2,1]})
check('field上界で上端固定',clipped['y_m'][-1]==.19)
multi=core.sign_profile(lambda p:(p[1]+.4)*(p[1]+.2)*p[1],3.,0.,bounds)
check('複数符号交差を保持',len(multi['crossings'])==3 and multi['wet_to_dry_count']==2 and not multi['single_wet_to_dry_local'])
zero=core.sign_profile(lambda p:0 if abs(p[1])<=.01 else p[1],3.,0.,bounds)
check('零台地は未確定',zero['zero_plateau_detected']and not zero['single_wet_to_dry_local']and zero['height_m']is None)
tangent=core.sign_profile(lambda p:p[1]**2,3.,0.,bounds)
check('接線接触は自由面合格にしない',bool(tangent['tangent_zero_indices'])and not tangent['single_wet_to_dry_local'])
raises('場外をゼロで補わない',lambda:core.sign_profile(lambda p:0,8.,0.,bounds))
raises('非有限を拒否',lambda:core.sign_profile(lambda p:float('nan'),3.,0.,bounds))
flat=core.sign_profile(lambda p:0,3.,0.,bounds)
check('全零fieldは自由面合格にしない',not flat['single_wet_to_dry_local'])

def make_ray(heights):
    def query(lo,hi):
        for index,y in enumerate(sorted(heights,reverse=True)):
            if lo<=.4-y<=hi:return {'primitive':index,'position_m':[3.,y,0.],'normal':[0.,1.,0.]}
        return None
    return query
for epsilon in (2e-6,2e-5):
    hit=core.enumerate_hits(make_ray([0.,-.0005,-.0015,-.6]),epsilon=epsilon)
    check('0p5mm層とprimitive0保持_'+str(epsilon),len(hit['hits'])==4 and hit['hits'][0]['primitive']==0)
check('空ray',core.enumerate_hits(lambda a,b:None)['hits']==[])
raw_hit={'primitive':0,'position_m':[3.,-.001,0.],'normal':[0,1,0]}
incidence={**raw_hit,'requested_primitive':0}
check('主queryとpatternのprimitive0配対',core.incidence_consistency([raw_hit],[incidence])['passed'])
missing=core.incidence_consistency([raw_hit],[])
check('空patternを黙って合格にしない',not missing['passed']and missing['strict_hit_comparisons'][0]['minimum_height_error_m']is None)
empty_strict=core.incidence_consistency([],[],default_first_present=True)
check('既定命中ありstrict空は保留',not empty_strict['passed']and not empty_strict['strict_default_coverage'])
check('両ray空は形状存在を主張せず整合のみ',core.incidence_consistency([],[])['passed'])
shifted={**incidence,'position_m':[3.,-.001002,0.]};different={**incidence,'primitive':1}
check('pattern高さ差を保留',not core.incidence_consistency([raw_hit],[shifted])['passed'])
check('pattern番号違いを保留',not core.incidence_consistency([raw_hit],[different])['passed'])
check('同じ高さの別faceは一致代用にしない',not core.incidence_consistency([raw_hit],[{**different,'requested_primitive':1}])['passed'])
extra={**incidence,'primitive':2,'requested_primitive':2,'position_m':[3.,-.002,0.]}
backward=core.incidence_consistency([raw_hit],[incidence,extra])
check('面限定だけの余分な高さを保留',not backward['passed']and backward['unmatched_incidence_indices']==[1])
check('共有辺の同高別面は逆配対可能',core.incidence_consistency([raw_hit],[incidence,{**incidence,'primitive':2,'requested_primitive':2}])['passed'])
check('主ray空で面限定命中を保留',not core.incidence_consistency([],[incidence])['passed'])
check('不一致比較でも原交点を変更しない',raw_hit['position_m']==[3.,-.001,0.]and shifted['position_m']==[3.,-.001002,0.])
raises('反復停止保護',lambda:core.enumerate_hits(lambda a,b:{'primitive':0,'position_m':[0,0,0],'normal':[0,1,0]}))
raises('64命中上限',lambda:core.enumerate_hits(make_ray([-.001*i for i in range(65)])))
raises('非有限交点',lambda:core.enumerate_hits(lambda a,b:{'primitive':0,'position_m':[0,float('nan'),0],'normal':[0,1,0]}))
quad=[[0,0,0],[1,0,0],[1,0,1],[0,0,1]]
check('平面quad対角一致',core.quad_diagonal_sensitivity(quad,.5,.5)['absolute_difference_m']==0)
twisted=[list(p)for p in quad];twisted[2][1]=.004
sensitivity=core.quad_diagonal_sensitivity(twisted,.5,.5)
check('非平面quad感度のみ',abs(sensitivity['absolute_difference_m']-.002)<1e-12 and sensitivity['response_scale_1mm_flag'])
check('対角線一意は投影凸性証明ではない',not sensitivity['projected_convexity_checked']and not sensitivity['geometric_validity_certified'])
check('非平面頂点偏差',core.polygon_metrics(twisted)['max_plane_deviation_m']>0)
check('退化面',core.polygon_metrics([[0,0,0],[0,0,0],[0,0,0]])['degenerate'])
check('三角形にquad感度を偽装しない',not core.quad_diagonal_sensitivity(quad[:3],0,0)['applicable'])
boxes=[(0,0,1,0,1),(1,1,2,0,1),(2,-10,10,-10,10)]
index=core.face_index(boxes)
check('辺と頂点の全候補',core.candidate_faces(index,1,0)==[0,1,2])
check('最大tolerance分bbox拡張',0 in core.candidate_faces(index,1+5e-6,.5))
check('bbox外20umは除外',0 not in core.candidate_faces(index,1+2e-5,.5))
rng=random.Random(2205)
random_queries=[(rng.uniform(-2,3),rng.uniform(-2,3))for _ in range(100)]
check('索引は総当たりと同じ',all(set(core.candidate_faces(index,x,z))=={n for n,a,b,c,d in boxes if a-1e-5<=x<=b+1e-5 and c-1e-5<=z<=d+1e-5}for x,z in random_queries))

# 元gauge関数だけをASTから取り出す。トップレベルのHoudiniコードは実行しない。
tree=ast.parse((BASE/'Executed_Source/generate_wave_l6.py').read_text(encoding='utf8'))
func=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='gauge');space={'H':.6,'math':math}
exec(compile(ast.Module(body=[func],type_ignores=[]),'frozen_gauge_only','exec'),space)
class Box:
    def minvec(self):return bounds['min']
    def maxvec(self):return bounds['max']
class Volume:
    def __init__(self,height):self.height=height
    def boundingBox(self):return Box()
    def sample(self,p):return p[1]-self.height
check('原121点25二分完全一致',all(space['gauge'](Volume(h),3,0)['eta_m']==core.original_gauge(Volume(h).sample,3,0,bounds)['eta_m']for h in [-.04,-.001,0,.013,.08]))

spec=importlib.util.spec_from_file_location('frozen_response',BASE/'Executed_Source/startup_response.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=json.loads(gzip.decompress((BASE/'Original/22_pilot_samples.json.gz').read_bytes()))['samples'];original=json.loads((BASE/'Original/22_startup_response.json').read_bytes())
recomputed=module.analyze_response(rows,original['config'])
check('原全時系列応答判定不変',recomputed=={k:v for k,v in original.items()if k!='sample_sha256'})
check('中心qは全て元1mm',all(g['baseline']['threshold_m']==.001 for o in recomputed['observations'].values()for g in o['gauges']))
check('PFSとsolverの5点時間幅は別',4/30==2*(4/60))

core_text=(HERE/'profile_core.py').read_text(encoding='utf8');adapter=(HERE/'read_profile05.py').read_text(encoding='utf8')
code,code_sha=runner.build_code(core_text,adapter,1,'mesh.bgeo.sc','pilot.bgeo.sc',PLAN['pairs'][0],PLAN,Path('result.json'))
compile(code,'independent_namespace_rpc','exec');check('RPC全定義の構文',True)
# プローブ末尾を除いた定義部だけ独立namespaceで評価する。実readerは呼ばない。
space={};exec(core_text+'\n'+adapter,space)
check('独立namespace必要名が存在',all(k in space for k in ('Path','json','hashlib','read_pair','sign_profile','face_index','enumerate_hits')))
for p in HERE.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
check('全候補Python構文',True)
for forbidden in ('createNode','setFrame','setFps','setUpdateMode','cook','saveToFile','clear','load'):
    check('reader不使用API_'+forbidden,not any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr==forbidden for n in ast.walk(ast.parse(adapter))))
check('明示実行フラグ',"if a.execute_reviewed_profile_readback:"in(HERE/'run_profile05.py').read_text(encoding='utf8'))
check('MCP importは実行関数内',all(not(isinstance(n,(ast.Import,ast.ImportFrom))and getattr(n,'module','')and n.module.startswith('mcp'))for n in ast.parse((HERE/'run_profile05.py').read_text(encoding='utf8')).body))
check('基線全公開SHA',all(sha(BASE/p)==h for p,h in PLAN['baseline_files'].items()))
runner.validate_request([468],PLAN,False);check('首組468のみを許可',True)
raises('追加flagなし複数組を拒否',lambda:runner.validate_request([468,470],PLAN,False),AssertionError)
raises('追加flagなし別組を拒否',lambda:runner.validate_request([470],PLAN,False),AssertionError)
raises('追加flagだけで首組証拠なしを拒否',lambda:runner.validate_request([470],PLAN,True),AssertionError)
preflight={'sample':468,'plan_sha256':'plan','combined_reader_sha256':'reader',
           'mesh_sha256':PLAN['pairs'][0]['mesh_sha256'],'solver_sha256':PLAN['pairs'][0]['solver_sha256'],
           'center_parity_passed':True,'strict_incidence_consistency_passed':True,'ui_metadata_unchanged':True,
           'solver_executed':False,'nodes_created':False}
runner.validate_request([470],PLAN,True,preflight,'reader','plan');check('追加flagと一致首組の配対検査',True)
raises('不一致首組で追加を拒否',lambda:runner.validate_request([470],PLAN,True,{**preflight,'strict_incidence_consistency_passed':False},'reader','plan'),AssertionError)
raises('違うreaderの首組で追加を拒否',lambda:runner.validate_request([470],PLAN,True,preflight,'wrong','plan'),AssertionError)
raises('違うplanの首組で追加を拒否',lambda:runner.validate_request([470],PLAN,True,preflight,'reader','wrong'),AssertionError)
check('生成RPCのplanSHAは元bytesと一致',sha(HERE/'profile05_plan.json')in code)

# 単一組規模の索引/純φ計算の費用だけ測る。HOM/ファイル読込み費用ではない。
start=time.monotonic();synthetic=[(i+300*j,i*.02,(i+1)*.02,j*.02,(j+1)*.02)for j in range(130)for i in range(300)]
idx=core.face_index(synthetic);candidate_count=sum(len(core.candidate_faces(idx,p['x_m'],p['z_m']))for p in positions)
for p in positions:core.sign_profile(lambda v:v[1]-.002*math.sin(v[0]*2),p['x_m'],p['z_m'],bounds)
elapsed=time.monotonic()-start
check('合成39000面の費用計測有限',math.isfinite(elapsed)and elapsed>0)
sources=[p for p in HERE.iterdir()if p.is_file()]
report={'passed':True,'checks':CHECKS,'source_hashes':{p.name:sha(p)for p in sources},'houdini_called':False,'MCP_called':False,
        'synthetic_cost':{'faces':39000,'profiles':195,'seconds':elapsed,'candidate_face_queries':candidate_count,
                          'meaning_ja':'Python索引/解析φのみ。native HOM交点・BGEO load・実所要時間は未検証。'},
        'limits_ja':['合成queryはHOMのfloat32丸め・pattern実装を保証しない。最初の実1組は別放行が必要。','2/20µm以下の重なりをnative反復だけで分離できない。未統合primitive別記録と併読。','近傍断面に元中央q/応答判定を移植しない。']}
evidence=CANDIDATE/'Evidence/22_profile05_offline_checks.json'
if args.update_evidence:
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
else:
    assert evidence.exists(),'初回だけ--update-evidenceで保存証拠を作成する'
    before=evidence.read_bytes();saved=json.loads(before)
    for key in ('passed','checks','source_hashes','houdini_called','MCP_called','limits_ja'):
        assert saved[key]==report[key],('保存証拠と不一致。自動更新しない',key)
    for key in ('faces','profiles','candidate_face_queries','meaning_ja'):
        assert saved['synthetic_cost'][key]==report['synthetic_cost'][key],key
    assert math.isfinite(saved['synthetic_cost']['seconds'])and saved['synthetic_cost']['seconds']>0
    assert evidence.read_bytes()==before
print(json.dumps({'passed':True,'checks':len(CHECKS),'current_synthetic_seconds':elapsed,'houdini_called':False,
                  'evidence_updated':args.update_evidence,'evidence_sha256':sha(evidence)}))
