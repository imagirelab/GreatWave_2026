"""22の実キャッシュだけを別所有ノードで撮影し、既存UIを復元する。"""
import asyncio, hashlib, json, sys, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import ui_guard
ROOT=Path(__file__).resolve().parents[1]
RUN=(ROOT/'Runs'/sys.argv[1]).resolve();assert RUN.parent==ROOT/'Runs'
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
TOKEN=uuid.uuid4().hex[:10];NAME='gw22_view_'+TOKEN;KEY='_gw22_view_'+TOKEN;OBJ_PATH='/obj/'+NAME
EXTRA=r'''
s=getattr(hou.session,KEY)
s['reference_grid']=s['viewer'].referencePlane().isVisible();s['construction_grid']=s['viewer'].constructionPlane().isVisible();s['color_scheme']=s['viewport'].settings().colorScheme()
'''
RESTORE=r'''
s=getattr(hou.session,KEY)
s['viewer'].referencePlane().setIsVisible(s['reference_grid']);s['viewer'].constructionPlane().setIsVisible(s['construction_grid']);s['viewport'].settings().setColorScheme(s['color_scheme'])
extra_checks={'reference_grid':s['viewer'].referencePlane().isVisible()==s['reference_grid'],'construction_grid':s['viewer'].constructionPlane().isVisible()==s['construction_grid'],'color_scheme':s['viewport'].settings().colorScheme()==s['color_scheme']}
'''
CREATE=r'''
from pathlib import Path
import json
s=getattr(hou.session,KEY);root=Path(STAGE)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
own=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False);s['owned_nodes'].append((own,own.sessionId()))
geo=own.createNode('geo',node_name='cached_wave22',run_init_scripts=False)
reader=geo.createNode('file',node_name='actual_meshed_cache',run_init_scripts=False)
color=geo.createNode('attribwrangle',node_name='display_color_only',run_init_scripts=False);color.setInput(0,reader);color.parm('snippet').set('@Cd=set(0.08,0.4,0.75);')
color.setDisplayFlag(True);color.setRenderFlag(True);geo.setDisplayFlag(True);own.setDisplayFlag(True)
s.update({'reader':reader,'out':color})
s['viewer'].referencePlane().setIsVisible(False);s['viewer'].constructionPlane().setIsVisible(False);s['viewport'].settings().setColorScheme(hou.viewportColorScheme.DarkGrey)
result={'reader_created':True,'actual_cache_only':True,'geometry_recomputed':False,'display_attribute_only':'Cd'}
'''
CAPTURE=r'''
from pathlib import Path
import json
s=getattr(hou.session,KEY);root=Path(STAGE);evidence=Path(OUTPUT)
rows=json.loads((root/'Evidence/22_pilot_samples.json').read_text(encoding='utf8'))['samples'];last=rows[-1]['sample']
records=[]
for k in sorted({0,last//3,2*last//3,last}):
 t=rows[k]['requested_seconds'];frame=1+t*hou.fps();hou.setFrame(frame)
 s['reader'].parm('file').set(str(root/('Cache/mesh_%03d.bgeo.sc'%k)).replace('\\','/'));s['out'].cook(force=True)
 assert len(s['out'].geometry().prims())>0 and not s['out'].errors()
 for view in ('Front','Perspective'):
  s['viewport'].changeType(hou.geometryViewportType.Front if view=='Front' else hou.geometryViewportType.Perspective)
  if view=='Perspective':s['viewport'].defaultCamera().setRotation(hou.hmath.buildRotate((25,-20,0)).extractRotationMatrix3())
  s['viewport'].frameBoundingBox(hou.BoundingBox(0,-.7,-.4,5.9807903466,.25,.4))
  path=evidence/('22_%s_%03d.png'%(view,k));settings=s['viewer'].flipbookSettings().stash();settings.outputToMPlay(False);settings.output(str(path).replace('\\','/'));settings.frameRange((frame,frame));settings.frameIncrement(1)
  settings.useResolution(True);settings.resolution((1280,720));settings.outputZoom(100);settings.useSheetSize(False);settings.appendFramesToCurrent(False);settings.cropOutMaskOverlay(False)
  s['viewport'].draw();s['viewer'].flipbook(s['viewport'],settings)
  records.append({'sample':k,'seconds':t,'global_frame':frame,'view':view,'file':str(path)})
result={'stills':records,'simulation_recomputed':False,'global_fps_unchanged':hou.fps()==s['fps']}
'''
async def main():
 expected=json.loads((ROOT/'Evidence/22_connection.json').read_text())['metadata']['pid'];output=ROOT/'Evidence/Frames'/TOKEN;output.mkdir(parents=True)
 report={'utc':datetime.now(timezone.utc).isoformat(),'token':TOKEN,'source_run':str(RUN),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
 with (ROOT/'Evidence/capture_proxy.log').open('w',encoding='utf8') as err:
  async with stdio_client(params,errlog=err) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as client:
    await client.initialize()
    async def execute(code):
     pre='\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'STAGE':str(RUN),'OUTPUT':str(output)}.items())+'\n'
     response=await client.call_tool('execute_python',{'code':pre+f'import os\nassert os.getpid()=={expected}\n'+code,'return_expression':'result','justification':'22の実FLIP静水キャッシュを新規所有ノードで表示・撮影し、既存UIを復元する。既存HIP内容を調べず保存しない。'})
     v=json.loads(next(c.text for c in response.content if c.type=='text'));assert not response.isError and v.get('executed') and not v.get('error'),v
     return v['return_value']
    snapshot=False
    try:
     report['snapshot']=await execute(ui_guard.SNAPSHOT+EXTRA);snapshot=True
     report['create']=await execute(CREATE)
     report['show']=await execute(ui_guard.SHOW_OWNED.replace("s['viewport'].frameSelected()","hou.clearAllSelected()"))
     report['capture']=await execute(CAPTURE)
    except Exception as exc:report['failure']={'type':type(exc).__name__,'message':str(exc)}
    finally:
     if snapshot:
      try:report['cleanup']=await execute(RESTORE+ui_guard.CLEANUP+"\nresult['extra_checks']=extra_checks\nresult['all_ui_and_owned_node_checks_passed']=result['all_ui_and_owned_node_checks_passed'] and all(extra_checks.values())\n")
      except Exception as exc:report['cleanup_failure']=str(exc)
 report['passed']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False)
 (output/'capture_report.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 print(json.dumps({'path':str(output),'passed':report['passed'],'failure':report.get('failure')},ensure_ascii=False))
asyncio.run(main())
