"""HOM未実行の純関数/状態遷移検査。既定は証拠を更新しない。"""
import argparse
import ast
import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from run_file_probe06 import CANDIDATE, ROOT, probe_rpc, sha


def check_all():
    results = []
    def check(name, condition):
        assert condition, name
        results.append({'name_ja': name, 'passed': True})
    def rejects(action):
        try: action()
        except (ValueError, TypeError, AssertionError): return True
        return False
    plan = json.loads((CANDIDATE / 'Source/file_probe_plan.json').read_bytes())
    previous=CANDIDATE.parent/'PfsSensitivity06Retry02'
    before_adapter=(previous/'Source/probe_file06.py').read_text(encoding='utf8')
    after_adapter=(CANDIDATE/'Source/probe_file06.py').read_text(encoding='utf8')
    expected_adapter=before_adapter.replace("'needs_to_cook': node.needsToCook(time=hou_api.time()),", "'needs_to_cook': node.needsToCook(), 'needs_to_cook_at_seconds': hou_api.time(),")
    check('HOM実装差は既定時刻呼出しだけ',after_adapter==expected_adapter and before_adapter!=after_adapter)
    old_plan=json.loads((previous/'Source/file_probe_plan.json').read_bytes())
    check('従来のscope/予算/動作条件が不変',all(plan[k]==v for k,v in old_plan.items() if k!='revision'))
    manifest_path=CANDIDATE/'Evidence/22_prior_attempts_manifest.json'
    prior=json.loads(manifest_path.read_bytes())
    check('前3候補と3Runの一覧SHA',sha(manifest_path)==plan['prior_attempts_manifest_sha256'])
    check('前3候補と3Runの全bytes/SHA',all((ROOT/r['path']).stat().st_size==r['bytes'] and sha(ROOT/r['path'])==r['sha256'] for r in prior['files']))
    text = '\n'.join((CANDIDATE / 'Source' / name).read_text(encoding='utf8') for name in ('support06.py', 'probe_file06.py'))
    ns = {}; exec(compile(text, '<isolated-file06-definitions>', 'exec'), ns)
    check('定義読込はHOM不要', 'hou' not in ns and callable(ns['probe_file06']))
    check('再候補scopeはk360のみ', plan['scope'] == 'FILE_NULL_K360_ONLY' and plan['sample'] == 360)
    check('新mesh/solverを禁止', not plan['new_meshing'] and not plan['new_solver'])
    check('既存2Run/2freeze/04sourceが不変', all(sha(ROOT / p) == h for p, h in plan['fixed_evidence'].items()))
    for name in ('PfsSensitivity06','PfsSensitivity06Retry01'):
        folder=CANDIDATE.parent/name; frozen=json.loads((folder/'Evidence/22_pfs06_candidate_freeze.json').read_bytes())
        check('前回候補の全凍結file不変_'+name,all(sha(folder/r['path'])==r['sha256'] and (folder/r['path']).stat().st_size==r['bytes'] for r in frozen['files']))
    check('抽出関数の元source不変', all(sha(ROOT / r['path']) == r['sha256'] for r in plan['support_origins']))
    support = ast.parse((CANDIDATE / 'Source/support06.py').read_text(encoding='utf8'))
    for row in plan['support_origins']:
        before = ast.parse((ROOT / row['path']).read_text(encoding='utf8'))
        for name in row['functions']:
            old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
            new = next(n for n in support.body if isinstance(n, ast.FunctionDef) and n.name == name)
            check('補助関数のAST不変_' + name, ast.dump(old) == ast.dump(new))
    raw = ROOT / 'Houdini/Wave22/Runs' / plan['baseline_run'] / 'Cache' / plan['input']['filename']
    check('k360原BGEOのbytes/SHA', raw.stat().st_size == plan['input']['bytes'] and sha(raw) == plan['input']['sha256'])
    check('整数はhashで保持', ns['value_hash06']([2**60]) != ns['value_hash06']([2**60 + 1]))
    check('浮動値の差を丸めない', ns['value_hash06']([1.]) != ns['value_hash06']([1. + 1e-12]))
    check('辞書の順序に依存しない', ns['value_hash06']({'a': 1, 'b': 2}) == ns['value_hash06']({'b': 2, 'a': 1}))
    check('属性NaNを拒否', rejects(lambda: ns['finite_value06']([math.nan])))
    check('未知属性型を拒否', rejects(lambda: ns['finite_value06'](object())))
    check('未接続Noneを許す', ns['disconnected_file_inputs']((None,), 0))
    check('実接続を拒否', not ns['disconnected_file_inputs']((object(),), 1))
    for value in ('invalid', '{}', '{"executed":null}'):
        check('不明RPCは停止_' + value, ns['classify_rpc_reply'](value)[0] == 'UNCERTAIN')
    check('既知RPC失敗を区別', ns['classify_rpc_reply']('{"executed":true,"error":"x"}')[0] == 'COMPLETE_ERROR')
    check('既知RPC成功', ns['classify_rpc_reply']('{"executed":true,"return_value":{}}')[0] == 'COMPLETE_SUCCESS')
    class Parm:
        def __init__(self, name, value, menu=False): self.n=name; self.value=value; self.menu=menu
        def name(self): return self.n
        def label(self): return self.n
        def parmTemplate(self): return self
        def type(self): return 'parmTemplateType.Menu' if self.menu else 'parmTemplateType.String'
        def rawValue(self): return str(self.value)
        def eval(self): return self.value
        def evalAsString(self): return str(self.value)
        def unexpandedString(self): return str(self.value)
        def set(self, value): self.value=value
        def isDynamicMenu(self): return self.menu
        def menuItems(self):
            if not self.menu: return ()
            return ('auto','read','write')
        def menuLabels(self):
            assert self.menu, '非MenuへmenuLabelsを呼んだ'
            return ('Automatic','Read Files','Write Files')
    p=Parm('file','literal')
    check('非Menuのlabel要求を避ける', 'menu_labels' not in ns['parm_record06'](p))
    check('Menu実型と全tokenを保存', ns['parm_record06'](Parm('filemode',1,True))['menu_items']==['auto','read','write'])
    class Geometry:
        def __init__(self, full=False): self.full=full
        def loadFromFile(self, path): self.full=True
        def freeze(self): return self
        def points(self): return range(3 if self.full else 0)
        def prims(self): return range(1 if self.full else 0)
        def pointAttribs(self): return ()
        def primAttribs(self): return ()
        def vertexAttribs(self): return ()
        def globalAttribs(self): return ()
    class Node:
        def __init__(self, h, kind, name): self.h=h;self.kind=kind;self.n=name;self.kids=[];self.count=0;self.display=False;self.input=None;self.parms_by_name={'file':Parm('file',''),'filemode':Parm('filemode',1,True)}
        def name(self): return self.n
        def type(self):
            class T:
                def name(inner): return self.kind
            return T()
        def createNode(self, kind, node_name, **kw):
            n=Node(self.h,kind,node_name);self.kids.append(n);return n
        def children(self): return self.kids
        def sessionId(self): return 1
        def isDisplayFlagSet(self): return self.display
        def setDisplayFlag(self,v): self.display=v
        def isRenderFlagSet(self): return False
        def isBypassed(self): return False
        def isHardLocked(self): return False
        def isSoftLocked(self): return False
        def isUnloadFlagSet(self): return False
        def inputs(self): return () if self.input is None else (self.input,)
        def inputConnections(self): return () if self.input is None else (1,)
        def setInput(self,index,node): self.input=node
        def parm(self,name): return self.parms_by_name[name]
        def parms(self): return self.parms_by_name.values()
        def errors(self): return ()
        def warnings(self): return ()
        def cookCount(self): return self.count
        def needsToCook(self): return self.count==0
        def cook(self,force):
            assert force
            if self.h.mode=='AutoUpdate': self.count+=1
        def geometry(self):
            if self.h.mode=='AutoUpdate' and self.h.raise_auto: raise RuntimeError('合成Auto失敗')
            if self.h.mode=='AutoUpdate': self.count+=1
            return Geometry(self.h.mode=='AutoUpdate' and not self.h.stay_empty)
    class Hou:
        class updateMode: Manual='Manual';AutoUpdate='AutoUpdate'
        class parmTemplateType: Button='Button'
        def __init__(self, fail=False, empty=False):
            self.mode='Manual';self.f=1.;self.raise_auto=fail;self.stay_empty=empty;self.own=Node(self,'subnet','own')
            self.session=type('Session',(),{})();self.session.key={'owned_nodes':[(self.own,1)]}
        def node(self,path): return self.own
        def updateModeSetting(self): return self.mode
        def setUpdateMode(self,mode): self.mode=mode
        def fps(self): return 24
        def frame(self): return self.f
        def setFrame(self,f): self.f=f
        def time(self): return (self.f-1)/24
        def Geometry(self): return Geometry()
    ns['memory06']=lambda root:{'available_bytes':16*1024**3,'private_bytes':1,'free_G_bytes':20*1024**3}
    signature_modes=[]
    def mock_signature(hou,g):
        signature_modes.append(hou.mode)
        assert hou.mode=='Manual','重いhashはManual復帰後だけ'
        return {'points':len(g.points()),'primitives':len(g.prims()),'mock_only':True}
    ns['all_geometry_signature06']=mock_signature
    example=Hou()
    check('実HOMと同じkeyword拒否mock',rejects(lambda:example.own.needsToCook(time=example.time())))
    check('mockは位置引数も拒否',rejects(lambda:example.own.needsToCook(example.time())))
    state=ns['node_state06'](example.own,example)
    check('無引数と別記の現在秒',state['needs_to_cook'] is True and state['needs_to_cook_at_seconds']==example.time())
    with tempfile.TemporaryDirectory(prefix='file06_check_') as td:
        folder=Path(td);src=folder/'input.bgeo.sc';src.write_bytes(b'synthetic only')
        mp=copy.deepcopy(plan);mp['input']={'sha256':sha(src),'bytes':src.stat().st_size};mp['expected_points']=3;mp['expected_primitives']=1
        for label, fail, empty in [('pass',False,False),('auto_error',True,False),('empty',False,True)]:
            h=Hou(fail,empty);dst=folder/(label+'.json');r=ns['probe_file06'](h,'key','/obj/own',str(src),mp,str(dst))
            check('同RPC内Manual復帰_' + label,h.mode=='Manual' and r['manual_restored_in_same_rpc'])
            check('結果JSONを保存_' + label,dst.exists() and json.loads(dst.read_bytes())['passed']==r['passed'])
            check('direct署名を先に保存_' + label,r['direct_signature']['points']==3)
            check('Manual空を記録_' + label,r['node_observations']['MANUAL_FILE_AFTER_EXPLICIT_COOK']['points']==0)
            if label=='pass':
                check('AutoのFile/Null厳密配対',r['passed'] and all(r['node_observations']['AUTOUPDATE_'+k+'_AFTER_EXPLICIT_COOK']['equals_direct'] for k in ('FILE','NULL')))
                check('geometryによる暗黙cookを区別',r['node_observations']['AUTOUPDATE_FILE_BEFORE_EXPLICIT_COOK']['after_geometry_call']['cook_count']>r['node_observations']['AUTOUPDATE_FILE_BEFORE_EXPLICIT_COOK']['before_geometry_call']['cook_count'])
            elif label=='auto_error': check('Auto例外も失敗phaseを保持',not r['passed'] and r['failure_type']=='RuntimeError' and r['failure_phase'].startswith('AUTOUPDATE'))
            else: check('空のままならHOLD',not r['passed'] and r['hold_reason_ja'] is not None)
    check('全signature計算はManual',signature_modes and set(signature_modes)=={'Manual'})
    tree=ast.parse((CANDIDATE/'Source/probe_file06.py').read_text(encoding='utf8'))
    types=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='createNode']
    check('probe作成型はgeo/file/nullだけ',types==['geo','file','null'])
    check('PFS/solver/描画/待機呼出しなし',not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('sleep','draw','flipbook','saveToFile') for n in ast.walk(tree)))
    check('原cacheは保存しない','saveToFile' not in text)
    for path in (CANDIDATE/'Source').glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
    compile(probe_rpc(text,{'PLAN':plan}),'<isolated-rpc06>','exec')
    check('全構文と独立RPC定義',True)
    dry=subprocess.run([sys.executable,'-X','utf8','-B',str(CANDIDATE/'Source/run_file_probe06.py')],capture_output=True,text=True,encoding='utf8',check=True)
    check('既定runnerは未接続',json.loads(dry.stdout)=={'houdini_called':False,'sample':360,'scope':'FILE_NULL_K360_ONLY','new_meshing':False})
    return {'revision':'22修正06 再候補03','passed':True,'houdini_called':False,'check_count':len(results),'checks':results,
            'source_hashes':{p.name:sha(p) for p in sorted((CANDIDATE/'Source').iterdir()) if p.is_file()},
            'meaning_ja':'合成状態遷移と原ファイルSHAのみ。実HOMのFile/Null/AutoUpdate挙動は未実行。'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--update-evidence',action='store_true');args=parser.parse_args()
    result=check_all();p=CANDIDATE/'Evidence/22_file_probe_offline_checks.json'
    if args.update_evidence:p.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    else:assert json.loads(p.read_bytes())==result,'現在sourceと報告が不一致'
    print(json.dumps({'passed':True,'checks':result['check_count'],'houdini_called':False,'evidence_written':args.update_evidence,'report_sha256':sha(p)}))
