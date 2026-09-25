"""取景コードの離線検査。明示した模擬HOMのみ、実UI/MCPを呼ばない。"""
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import capture_start04 as capture

checks=[]
def check(name,condition):
    assert condition,name
    checks.append({'name_ja':name,'passed':True})

for name in ('CREATE','FRAME','EXTRA','RESTORE'):
    compile(getattr(capture,name),name,'exec')
check('全RPC本文は独立して構文成立',True)
check('FRAMEに時刻/FPS/HIP変更/DOPアクセスなし',all(x not in capture.FRAME for x in ('setFrame','setFps','hipFile','simulation(','dopnet')))
check('CREATEは所有Fileと色属性だけ',"createNode('file'" in capture.CREATE and all(x not in capture.CREATE for x in ('flipsolver','dopnet','hipFile','setFrame','setFps')))
check('事前固定5時刻と追加斜視2枚',capture.capture_plan('preflight')==[(k,'Front')for k in (360,420,480,540,554)]+[(480,'Perspective'),(554,'Perspective')])
check('動画は97枚で最終k552、k554は別静止画',len(capture.capture_plan('video'))==97 and capture.capture_plan('video')[-1]==(552,'Front'))

class Settings:
    def __init__(self):self.values={};self.stashed=False
    def stash(self):self.stashed=True;return self
    def __getattr__(self,name):
        def call(*args):
            if args:self.values[name]=args[0]if len(args)==1 else args
            return self.values[name]
        return call
class Geometry:
    def loadFromFile(self,path):assert Path(path).exists()
    def pointFloatAttribValues(self,name):return (0.,0.,0.,1.,0.,0.,0.,1.,0.)
    def points(self):return [0,1,2]
    def prims(self):return [SimpleNamespace(vertices=lambda:[SimpleNamespace(point=lambda i=i:SimpleNamespace(number=lambda:i))for i in range(3)])]
    def freeze(self):return self
class Reader:
    def __init__(self):self.path=None
    def inputs(self):return ()
    def parm(self,name):return SimpleNamespace(set=lambda value:setattr(self,'path',value))
    def errors(self):return ()
class Output:
    def __init__(self):self.forced=False
    def cook(self,force):self.forced=force
    def errors(self):return ()
    def geometry(self):return Geometry()
class Viewport:
    def changeType(self,value):self.type=value
    def frameBoundingBox(self,value):self.bounds=value
    def draw(self):pass
    def viewTransform(self):return SimpleNamespace(asTuple=lambda:tuple(range(16)))
class Viewer:
    def __init__(self):self.settings=Settings();self.flipped=0
    def flipbookSettings(self):return self.settings
    def flipbook(self,viewport,settings):
        assert settings.stashed
        assert settings.values['initializeSimulations']is False and settings.values['useMotionBlur']is False
        assert settings.values['frameRange']==(1.,1.)
        self.flipped+=1
        Path(settings.values['output']).write_bytes(b'OFFLINE_SYNTHETIC_NOT_A_REAL_IMAGE')

root=capture.WAVE/'Local_Reproduction';root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='capture04_offline_',dir=root)as directory:
    directory=Path(directory);cache=directory/'cache.bgeo.sc';cache.write_bytes(b'OFFLINE_SYNTHETIC_NOT_BGEO')
    state={'frame':1.,'fps':24.,'capture_own_id':11,'reader':Reader(),'out':Output(),'viewport':Viewport(),'viewer':Viewer(),'capture_geo':SimpleNamespace(path=lambda:'/obj/owned/geo')}
    hou=SimpleNamespace(session=SimpleNamespace(owned=state),frame=lambda:1.,fps=lambda:24.,node=lambda path:SimpleNamespace(sessionId=lambda:11),Geometry=Geometry,
                        geometryViewportType=SimpleNamespace(Front='front',Perspective='perspective'),BoundingBox=lambda *v:v)
    variables={'hou':hou,'KEY':'owned','OBJ_PATH':'/obj/owned','CACHE':str(cache),'CACHE_SHA':capture.sha(cache),'SAMPLE':360,'SIM_SECONDS':6.,
               'EXPECTED_POINTS':3,'EXPECTED_FACES':1,'VIEW':'Front','IMAGE':str(directory/'frame.png'),'RECORD':str(directory/'frame.json')}
    exec(capture.FRAME,variables)
    record=json.loads((directory/'frame.json').read_bytes())
    check('独立namespaceで一画像と原JSON SHAを返す',variables['result']['json_sha256']==capture.sha(directory/'frame.json')and record['sample']==360)
    check('File SOP入力なし、Pと有向indicesを直接読戻しに一致',record['P_and_indices_equal_direct_BGEO']and state['reader'].inputs()==())
    check('固定UI時刻と実物理時刻を別記',record['global_frame_fixed']==1. and record['simulation_seconds']==6.)
    check('全危険flipbookフラグを明示False',all(v is False for v in record['flipbook_flags'].values())and len(record['flipbook_flags'])==6)
    check('stash設定は所有geoだけ・1280x720',state['viewer'].settings.stashed and state['viewer'].settings.values['visibleObjects']=='/obj/owned/geo'and state['viewer'].settings.values['resolution']==(1280,720))
    bad=dict(variables);bad['CACHE_SHA']='bad';stopped=False
    try:exec(capture.FRAME,bad)
    except AssertionError:stopped=True
    check('cache SHA改変はflipbook前に停止',stopped and state['viewer'].flipped==1)
    bad=dict(variables);bad['EXPECTED_POINTS']=4;stopped=False
    try:exec(capture.FRAME,bad)
    except AssertionError:stopped=True
    check('点数不一致はflipbook前に停止',stopped and state['viewer'].flipped==1)

script=Path(capture.__file__).read_text(encoding='utf8')
check('不明RPC後の並列cleanupをしない','if snapshot and not uncertain:'in script and 'assert not uncertain'in script)
check('所有登録は直後、UI18に追加表示復元を併用',"s['owned_nodes'].append((own,own.sessionId()))"in capture.CREATE and "guard.CLEANUP"in script and 'extra_checks'in script)
check('明示executeフラグがない既定は計画表示','if args.execute_reviewed_capture:'in script)
result={'houdini_or_mcp_called':False,'passed':True,'checks':checks,'source_sha256':capture.sha(Path(capture.__file__)),
        'check_source_sha256':capture.sha(Path(__file__)),'meaning_ja':'模擬HOMでの保護/構文検査。実GUI/画像成功は未検証。少数静止図を別途preflightする。'}
capture.write(capture.CANDIDATE/'Evidence/22_capture_offline_checks.json',result)
print(json.dumps({'checks':len(checks),'passed':True,'houdini_or_mcp_called':False,'capture_source_sha256':result['source_sha256']},ensure_ascii=False))
