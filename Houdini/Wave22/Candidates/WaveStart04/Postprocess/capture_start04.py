"""実PFS BGEOの固定時刻読戻し撮影。既定は計画表示だけ、別途審査後に実行。"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'

EXTRA=r'''
s=getattr(hou.session,KEY)
s['reference_grid']=s['viewer'].referencePlane().isVisible()
s['construction_grid']=s['viewer'].constructionPlane().isVisible()
s['color_scheme']=s['viewport'].settings().colorScheme()
'''
RESTORE=r'''
s=getattr(hou.session,KEY)
s['viewer'].referencePlane().setIsVisible(s['reference_grid'])
s['viewer'].constructionPlane().setIsVisible(s['construction_grid'])
s['viewport'].settings().setColorScheme(s['color_scheme'])
extra_checks={'reference_grid':s['viewer'].referencePlane().isVisible()==s['reference_grid'],
 'construction_grid':s['viewer'].constructionPlane().isVisible()==s['construction_grid'],
 'color_scheme':s['viewport'].settings().colorScheme()==s['color_scheme']}
'''
CREATE=r'''
import hashlib
from pathlib import Path
s=getattr(hou.session,KEY)
assert hou.frame()==s['frame'] and hou.fps()==s['fps']
first=Path(FIRST_CACHE);assert first.is_file() and hashlib.sha256(first.read_bytes()).hexdigest()==FIRST_SHA
own=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
s['owned_nodes'].append((own,own.sessionId()))
geo=own.createNode('geo',node_name='cached_PFS_only',run_init_scripts=False)
reader=geo.createNode('file',node_name='literal_readback',run_init_scripts=False)
assert not reader.inputs()
reader.parm('file').set(first.as_posix())
color=geo.createNode('attribwrangle',node_name='Cd_only',run_init_scripts=False)
color.setInput(0,reader);color.parm('snippet').set('@Cd=set(0.08,0.4,0.75);')
color.setDisplayFlag(True);color.setRenderFlag(True);geo.setDisplayFlag(True);own.setDisplayFlag(True)
s.update({'reader':reader,'out':color,'capture_geo':geo,'capture_own_id':own.sessionId()})
s['viewer'].referencePlane().setIsVisible(False);s['viewer'].constructionPlane().setIsVisible(False)
s['viewport'].settings().setColorScheme(hou.viewportColorScheme.DarkGrey)
assert hou.frame()==s['frame']
result={'created':True,'file_SOP_inputs':len(reader.inputs()),'global_frame':hou.frame(),
 'display_attribute_only':'Cd','existing_DOP_accessed':False,'simulation_initialized':False}
'''

FRAME=r'''
import hashlib,json,struct,time
from pathlib import Path
started=time.monotonic();s=getattr(hou.session,KEY)
own=hou.node(OBJ_PATH)
assert own is not None and own.sessionId()==s['capture_own_id']
assert hou.frame()==s['frame'] and hou.fps()==s['fps']
path=Path(CACHE);assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==CACHE_SHA
assert '$' not in str(path)
direct=hou.Geometry();direct.loadFromFile(str(path))
s['reader'].parm('file').set(path.as_posix())
assert not s['reader'].inputs()
s['out'].cook(force=True)
assert not s['out'].errors() and not s['reader'].errors()
shown=s['out'].geometry().freeze()
def indices(g):return tuple(tuple(v.point().number() for v in prim.vertices())for prim in g.prims())
assert direct.pointFloatAttribValues('P')==shown.pointFloatAttribValues('P')
assert indices(direct)==indices(shown)
assert len(direct.points())==EXPECTED_POINTS and len(direct.prims())==EXPECTED_FACES
view_type=hou.geometryViewportType.Front if VIEW=='Front' else hou.geometryViewportType.Perspective
s['viewport'].changeType(view_type)
if VIEW=='Perspective':s['viewport'].defaultCamera().setRotation(hou.hmath.buildRotate((25,-20,0)).extractRotationMatrix3())
s['viewport'].frameBoundingBox(hou.BoundingBox(0,-.65,-.35,6,.15,.35))
settings=s['viewer'].flipbookSettings().stash()
settings.initializeSimulations(False);settings.useMotionBlur(False);settings.leaveFrameAtEnd(False)
settings.outputToMPlay(False);settings.renderAllViewports(False);settings.scopeChannelKeyframesOnly(False)
settings.visibleObjects(s['capture_geo'].path())
settings.frameRange((s['frame'],s['frame']));settings.frameIncrement(1)
settings.useResolution(True);settings.resolution((1280,720));settings.outputZoom(100)
settings.useSheetSize(False);settings.appendFramesToCurrent(False);settings.cropOutMaskOverlay(False)
settings.beautyPassOnly(True)
settings.output(Path(IMAGE).as_posix())
checks={'initializeSimulations':settings.initializeSimulations(),'motionBlur':settings.useMotionBlur(),
 'leaveFrameAtEnd':settings.leaveFrameAtEnd(),'outputToMPlay':settings.outputToMPlay(),
 'renderAllViewports':settings.renderAllViewports(),'scopeChannelKeyframesOnly':settings.scopeChannelKeyframesOnly()}
assert not any(checks.values())
assert settings.frameRange()==(s['frame'],s['frame']) and settings.visibleObjects()==s['capture_geo'].path()
s['viewport'].draw();s['viewer'].flipbook(s['viewport'],settings)
assert hou.frame()==s['frame'] and hou.fps()==s['fps']
png=Path(IMAGE);assert png.is_file() and png.stat().st_size>0
record={'sample':SAMPLE,'simulation_seconds':SIM_SECONDS,'cache_file':path.name,'cache_sha256':CACHE_SHA,
 'image_file':png.name,'image_sha256':hashlib.sha256(png.read_bytes()).hexdigest(),'image_bytes':png.stat().st_size,
 'view':VIEW,'global_frame_fixed':hou.frame(),'fps_unchanged':hou.fps(),
 'points':len(shown.points()),'faces':len(shown.prims()),'P_and_indices_equal_direct_BGEO':True,
 'flipbook_flags':checks,'beautyPassOnly':settings.beautyPassOnly(),'visible_exact_owned_geometry':True,
 'frame_range':list(settings.frameRange()),'view_transform':list(s['viewport'].viewTransform().asTuple()),
 'view_bounds_fixed':[0,-.65,-.35,6,.15,.35],'capture_seconds':time.monotonic()-started,
 'meaning_ja':'実計算PFSキャッシュの読戻し。物理時刻はsimulation_seconds、固定UI frameは物理時刻ではない。'}
out=Path(RECORD);out.write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
result={'json_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'sample':SAMPLE,'view':VIEW}
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'))


def capture_plan(mode):
    if mode=='preflight':
        return [(k,'Front')for k in (360,420,480,540,554)]+[(480,'Perspective'),(554,'Perspective')]
    assert mode=='video'
    return [(k,'Front')for k in range(360,554,2)]


async def execute(token,mode):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    run=WAVE/'Runs'/token
    source_execution=json.loads((run/'Evidence/22_wave_start_execution.json').read_text(encoding='utf8'))
    assert source_execution['execution_succeeded'] and source_execution['cleanup']['all_ui_and_owned_node_checks_passed']
    spec=importlib.util.spec_from_file_location('capture_guard',run/'Source/ui_guard.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    assert sha(run/'Source/ui_guard.py')==source_execution['source_hashes']['ui_guard.py']
    rows=json.loads((run/'Evidence/22_pilot_samples.json').read_text(encoding='utf8'))['samples']
    selected=capture_plan(mode)
    for k,_ in selected:
        assert rows[k]['mesh_sampled']
        assert sha(run/'Cache'/('mesh_%03d.bgeo.sc'%k))==rows[k]['mesh_file_sha256']
    capture_token=uuid.uuid4().hex[:10]
    output=run/'Capture'/capture_token;output.mkdir(parents=True,exist_ok=False)
    name,key='gw22_capture04_'+capture_token,'_gw22_capture04_'+capture_token
    report={'capture_token':capture_token,'simulation_run':token,'mode':mode,'events':[],'frames':[],
            'source_sha256':sha(Path(__file__)),'source_samples_sha256':sha(run/'Evidence/22_pilot_samples.json'),
            'source_execution_sha256':sha(run/'Evidence/22_wave_start_execution.json'),'source_guard_sha256':sha(run/'Source/ui_guard.py')}
    (output/'capture_start04.py').write_bytes(Path(__file__).read_bytes())
    report_path=output/'22_capture_report.json'
    snapshot=False;uncertain=False;expected_pid=None
    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    with (output/'proxy.log').open('w',encoding='utf8')as errors:
        async with stdio_client(params,errlog=errors)as(reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=180))as client:
                await client.initialize()
                async def call(label,code,values=None,metadata=False):
                    nonlocal uncertain
                    assert not uncertain
                    fields={'NAME':name,'KEY':key,'OBJ_PATH':'/obj/'+name}
                    fields.update(values or {})
                    prefix='\n'.join(f'{k}={v!r}'for k,v in fields.items())+'\n'
                    if not metadata:prefix+=f'import os\nassert os.getpid()=={expected_pid} and hou.isUIAvailable() and hou.fps()==24\n'
                    started=time.monotonic()
                    try:r=await client.call_tool('execute_python',{'code':prefix+code,'return_expression':'result','justification':'新所有File SOPで既存PFSだけを固定時刻読戻し撮影。sim初期化・HIP操作・時間変更をせずUI復元。'+label})
                    except Exception:uncertain=True;raise
                    body=json.loads(next(x.text for x in r.content if x.type=='text'))
                    report['events'].append({'phase':label,'rpc_seconds':time.monotonic()-started,'executed':body.get('executed'),'error':body.get('error'),'eval_error':body.get('eval_error')})
                    write(report_path,report)
                    assert not r.isError and body.get('executed') and not body.get('error') and not body.get('eval_error'),body
                    return body['return_value']
                try:
                    metadata=await call('現metadata',"import os\nresult={'pid':os.getpid(),'version':hou.applicationVersionString(),'license':str(hou.licenseCategory()),'fps':hou.fps(),'ui':hou.isUIAvailable()}\n",metadata=True)
                    assert metadata['ui'] and metadata['version']=='22.0.429' and metadata['license']=='licenseCategoryType.Indie' and metadata['fps']==24
                    report['metadata']=metadata;expected_pid=metadata['pid']
                    report['snapshot']=await call('UI保存',guard.SNAPSHOT+EXTRA);snapshot=True
                    k=selected[0][0]
                    report['create']=await call('読戻し所有物だけ作成',CREATE,{'FIRST_CACHE':str(run/'Cache'/('mesh_%03d.bgeo.sc'%k)),'FIRST_SHA':rows[k]['mesh_file_sha256']})
                    report['show']=await call('所有物だけ表示',guard.SHOW_OWNED.replace("s['viewport'].frameSelected()","hou.clearAllSelected()"))
                    for index,(k,view)in enumerate(selected):
                        image=output/('22_%s_%03d.png'%(view,k))
                        record=output/('frame_%03d.json'%index)
                        ack=await call('読戻し画像 '+str(k)+' '+view,FRAME,{'SAMPLE':k,'SIM_SECONDS':rows[k]['requested_seconds'],
                            'CACHE':str(run/'Cache'/('mesh_%03d.bgeo.sc'%k)),'CACHE_SHA':rows[k]['mesh_file_sha256'],
                            'EXPECTED_POINTS':rows[k]['mesh_points'],'EXPECTED_FACES':rows[k]['mesh_faces'],'VIEW':view,
                            'IMAGE':str(image),'RECORD':str(record)})
                        assert sha(record)==ack['json_sha256']
                        report['frames'].append(json.loads(record.read_text(encoding='utf8')));write(report_path,report)
                        print(json.dumps({'capture_token':capture_token,'index':index,'sample':k,'view':view},ensure_ascii=False),flush=True)
                except Exception as exc:report['failure']={'type':type(exc).__name__,'message':str(exc)}
                finally:
                    if snapshot and not uncertain:
                        try:report['cleanup']=await call('UI18と追加表示状態を復元',RESTORE+guard.CLEANUP+"\nresult['extra_checks']=extra_checks\nresult['all_ui_and_owned_node_checks_passed']=result['all_ui_and_owned_node_checks_passed'] and all(extra_checks.values())\n")
                        except Exception as exc:report['cleanup_failure']={'type':type(exc).__name__,'message':str(exc)}
                    report['transport_completion_uncertain']=uncertain
                    report['passed']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False) and len(report['frames'])==len(selected)
                    if uncertain:report['recovery_required_ja']='RPC完了不明。追加cleanup・並行再要求・killはしない。'
                    write(report_path,report)
    print(json.dumps({'capture':str(output),'passed':report['passed'],'frames':len(report['frames']),'failure':report.get('failure')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='22e7801642');parser.add_argument('--mode',choices=['preflight','video'],default='preflight');parser.add_argument('--execute-reviewed-capture',action='store_true')
    args=parser.parse_args()
    if args.execute_reviewed_capture:asyncio.run(execute(args.run,args.mode))
    else:print(json.dumps({'houdini_called':False,'mode':args.mode,'frames':capture_plan(args.mode)},ensure_ascii=False))
