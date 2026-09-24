"""実キャッシュを近接表示して撮影する。計算・粒子位置・表面形状は変更しない。"""
import asyncio,hashlib,json,sys,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
import ui_guard
ROOT=Path(__file__).resolve().parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
TOKEN=uuid.uuid4().hex[:10];NAME='gw17_view_'+TOKEN;KEY='_gw17_view_'+TOKEN;OBJ_PATH='/obj/'+NAME
SNAPSHOT_EXTRA="""
s=getattr(hou.session,KEY)
s['reference_grid']=s['viewer'].referencePlane().isVisible()
s['construction_grid']=s['viewer'].constructionPlane().isVisible()
s['color_scheme']=s['viewport'].settings().colorScheme()
result['extra_view_snapshot']=True
"""
RESTORE_EXTRA="""
s=getattr(hou.session,KEY)
s['viewer'].referencePlane().setIsVisible(s['reference_grid'])
s['viewer'].constructionPlane().setIsVisible(s['construction_grid'])
s['viewport'].settings().setColorScheme(s['color_scheme'])
extra_checks={'reference_grid_restored':s['viewer'].referencePlane().isVisible()==s['reference_grid'],'construction_grid_restored':s['viewer'].constructionPlane().isVisible()==s['construction_grid'],'color_scheme_restored':s['viewport'].settings().colorScheme()==s['color_scheme']}
"""
CREATE=r'''
from pathlib import Path
import json
s=getattr(hou.session,KEY);root=Path(STAGE)
container=hou.node('/obj').createNode('subnet',node_name=NAME,run_init_scripts=False)
assert container.path()==OBJ_PATH
s['owned_nodes'].append((container,container.sessionId()))
geo=container.createNode('geo',node_name='cached17_only',run_init_scripts=False)
surface=geo.createNode('file',node_name='actual_surface',run_init_scripts=False)
surface.parm('file').set(str(root/'Cache/surface_`padzero(3,clamp($F-1,0,48))`.bgeo.sc').replace('\\','/'))
particles=geo.createNode('python',node_name='actual_particle_positions',run_init_scripts=False)
code="""import hou
from pathlib import Path
root=Path(ROOT_LITERAL)
initial=hou.Geometry();initial.loadFromFile(str(root/'Cache/particles_000.bgeo.sc'))
origin={p.intAttribValue('id'):p.position()[0] for p in initial.points() if not p.prims()}
cached=hou.Geometry();cached.loadFromFile(str(root/('Cache/particles_%03d.bgeo.sc'%int(max(0,min(48,round(hou.frame()-1)))))))
g=hou.pwd().geometry();g.clear();cd=g.addAttrib(hou.attribType.Point,'Cd',(0.5,0.5,0.5))
for p in cached.points():
 if p.prims(): continue
 q=g.createPoint();q.setPosition(p.position());birth=origin.get(p.intAttribValue('id'))
 q.setAttribValue(cd,(.08,.7,1) if birth is not None and birth<0 else ((1,.38,.05) if birth is not None else (.5,.5,.5)))
""".replace('ROOT_LITERAL',repr(STAGE.replace('\\','/')))
particles.parm('python').set(code)
glyph=geo.createNode('sphere',node_name='particle_position_glyph_radius_025m',run_init_scripts=False);glyph.parmTuple('rad').set((.025,.025,.025))
copies=geo.createNode('copytopoints::2.0',node_name='particle_glyphs',run_init_scripts=False);copies.setInput(0,glyph);copies.setInput(1,particles)
surface.setDisplayFlag(True);surface.setRenderFlag(True);geo.setDisplayFlag(True);container.setDisplayFlag(True)
s.update({'surface':surface,'particles_glyphs':copies,'geo':geo,'out':surface})
s['viewer'].referencePlane().setIsVisible(False);s['viewer'].constructionPlane().setIsVisible(False)
s['viewport'].settings().setColorScheme(hou.viewportColorScheme.DarkGrey)
result={'reader_created':True,'real_cache_only':True,'glyph_radius_m':.025,'glyphs_are_measurement_symbols':True,'visible_origin_color_coding':False,'source_positions_unchanged':True}
'''
CAPTURE=r'''
from pathlib import Path
import json
s=getattr(hou.session,KEY);root=Path(STAGE)
def photograph(path,start,end):
 settings=s['viewer'].flipbookSettings().stash();settings.outputToMPlay(False);settings.output(str(path).replace('\\','/'));settings.frameRange((start,end));settings.frameIncrement(1)
 settings.useResolution(True);settings.resolution((1280,720));settings.outputZoom(100);settings.useSheetSize(False);settings.appendFramesToCurrent(False);settings.cropOutMaskOverlay(False)
 s['viewport'].draw();s['viewer'].flipbook(s['viewport'],settings)
s['viewport'].changeType(hou.geometryViewportType.Perspective)
s['viewport'].defaultCamera().setRotation(hou.hmath.buildRotate((35,-25,0)).extractRotationMatrix3())
rows=json.loads((root/'Evidence/17_validation.json').read_text(encoding='utf8'))['samples']
if PHASE=='preview': selected=[3]
else: selected=[0,3,18,19,24,48]
records=[]
for k in selected:
 row=rows[k];bounds=hou.BoundingBox(*(row['mesh_bounds']['min']+row['mesh_bounds']['max']))
 for kind,node in (('Surface',s['surface']),('Particles',s['particles_glyphs'])):
  node.setDisplayFlag(True);node.setRenderFlag(True);hou.setFrame(k+1)
  try: node.cook(force=True)
  except Exception as exc: raise AssertionError((kind,str(exc),node.errors(),s['geo'].node('actual_particle_positions').errors()))
  assert not node.errors() and len(node.geometry().points())>0, (kind,node.errors(),s['geo'].node('actual_particle_positions').errors())
  s['viewport'].frameBoundingBox(bounds);s['viewport'].draw()
  photograph(root/('Evidence/17_%s_%03d.png'%(kind,k)),k+1,k+1)
 records.append({'sample':k,'time_seconds':k/s['fps'],'same_pair_frame_bounds':row['mesh_bounds']})
if PHASE!='preview':
 s['surface'].setDisplayFlag(True);s['surface'].setRenderFlag(True)
 full=hou.BoundingBox()
 for row in rows: full.enlargeToContain(hou.BoundingBox(*(row['mesh_bounds']['min']+row['mesh_bounds']['max'])))
 s['viewport'].frameBoundingBox(full)
 photograph(root/'Evidence/Frames'/(TOKEN+'_surface_$F4.png'),1,48)
result={'stills':records,'full_clip_samples':48 if PHASE!='preview' else 0,'video_pattern':TOKEN+'_surface_%04d.png','camera_mode':'実Houdiniビューポート。静止画は各時刻の同一境界で粒子/面を比較、動画は全時刻境界を固定。','simulation_recomputed':False}
'''
async def main():
 expected=json.loads((ROOT/'Evidence/17_connection.json').read_text())['metadata']['pid'];report={'utc':datetime.now(timezone.utc).isoformat(),'token':TOKEN,'expected_pid':expected,'owned_path':OBJ_PATH}
 cache=json.loads((ROOT/'Evidence/17_cache_index.json').read_text())['samples']
 before={r['mesh_file']:hashlib.sha256((ROOT/r['mesh_file']).read_bytes()).hexdigest() for r in cache}
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
 with (ROOT/'Evidence/capture_proxy.log').open('w') as err:
  async with stdio_client(params,errlog=err) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as client:
    await client.initialize()
    async def execute(code,phase=''):
     prefix='\n'.join(f'{k}={v!r}' for k,v in {'NAME':NAME,'KEY':KEY,'OBJ_PATH':OBJ_PATH,'STAGE':str(ROOT),'PHASE':phase,'TOKEN':TOKEN}.items())+'\n'
     response=await client.call_tool('execute_python',{'code':prefix+f'import os\nassert os.getpid()=={expected}\n'+code,'return_expression':'result','justification':'手順17の実キャッシュだけを新規所有ノードで描画し、撮影後にUIと追加表示設定を復元する。シミュレーションは再実行しない。'})
     value=json.loads(next(c.text for c in response.content if c.type=='text'));assert not response.isError and value.get('executed') and not value.get('error'),value
     return value['return_value']
    snapshot=False
    try:
     report['snapshot']=await execute(ui_guard.SNAPSHOT+SNAPSHOT_EXTRA);snapshot=True
     report['create']=await execute(CREATE)
     show=ui_guard.SHOW_OWNED.replace("s['viewport'].frameSelected()","hou.clearAllSelected()")
     report['show']=await execute(show)
     report['capture']=await execute(CAPTURE,'preview' if '--preview' in sys.argv else 'final')
    except Exception as exc: report['failure']={'type':type(exc).__name__,'message':str(exc)}
    finally:
     if snapshot:
      try: report['cleanup']=await execute(RESTORE_EXTRA+ui_guard.CLEANUP+"\nresult['extra_view_checks']=extra_checks\nresult['all_ui_and_owned_node_checks_passed'] = result['all_ui_and_owned_node_checks_passed'] and all(extra_checks.values())\n")
      except Exception as exc: report['cleanup_failure']={'type':type(exc).__name__,'message':str(exc)}
 report['cache_bytes_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in before.items())
 report['success']='failure' not in report and report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed',False) and report['cache_bytes_unchanged']
 (ROOT/('Evidence/capture_'+TOKEN+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
