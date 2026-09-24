"""17の実BGEOの凹多角形・非平面性を読む。シーン変更や再計算は行わない。"""
import asyncio,json
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
CODE=r'''
import os,json,numpy as np
from pathlib import Path
assert os.getpid()==EXPECTED_PID
root=Path(STAGE);source=root.parent/'VariableTopology17';records=[]
for k in range(49):
 g=hou.Geometry();g.loadFromFile(str(source/('Cache/surface_%03d.bgeo.sc'%k)))
 p=np.array(g.pointFloatAttribValues('P'),dtype=np.float64).reshape(-1,3)
 maximum=0.;nonplanar=0;concave=0;ngon=0;degenerate=0
 for prim in g.prims():
  ids=[pt.number() for pt in prim.points()];q=p[ids]
  if len(ids)>3:
   ngon+=1
   axis=np.cross(q[1]-q[0],q[2]-q[0]);length=np.linalg.norm(axis)
   if length<1e-12:degenerate+=1;continue
   normal=axis/length;deviation=float(np.max(np.abs((q-q[0])@normal)));maximum=max(maximum,deviation)
   if deviation>1e-5:nonplanar+=1
   turns=[np.dot(np.cross(q[(i+1)%len(ids)]-q[i],q[(i+2)%len(ids)]-q[(i+1)%len(ids)]),normal) for i in range(len(ids))]
   if min(turns)<-1e-10:concave+=1
 records.append({'sample':k,'polygons':len(g.prims()),'polygons_over_three_vertices':ngon,'nonplanar_over_1e_minus5m':nonplanar,'maximum_plane_deviation_m':maximum,'projected_concave_polygons':concave,'first_triangle_degenerate':degenerate})
result={'method_ja':'元面の先頭3点の平面に対する距離と、その平面への角の向きを測る。18の誤差基準は共通fan三角化後。点位置/Nは保持するが、非平面quad内部の元の一意な曲面復元は主張しない。','samples':records,'maximum_plane_deviation_m':max(r['maximum_plane_deviation_m'] for r in records),'total_nonplanar_polygons':sum(r['nonplanar_over_1e_minus5m'] for r in records),'total_projected_concave_polygons':sum(r['projected_concave_polygons'] for r in records)}
(root/'Evidence/18_triangulation_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
result={k:v for k,v in result.items() if k!='samples'}
'''
async def main():
 metadata=json.loads((ROOT/'Evidence/18_connection.json').read_text(encoding='utf8'))['metadata']
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
 with (ROOT/'Evidence/18_triangulation_proxy.log').open('w',encoding='utf8') as log:
  async with stdio_client(params,errlog=log) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as c:
    await c.initialize();response=await c.call_tool('execute_python',{'code':f'EXPECTED_PID={metadata["pid"]!r}\nSTAGE={str(ROOT)!r}\n'+CODE,'return_expression':'result','justification':'所有キャッシュファイル49件のみ読み、三角化の限界を測定する。既存シーンを調べず変更しない。'})
    data=json.loads(next(x.text for x in response.content if x.type=='text'));assert not response.isError and data.get('executed') and not data.get('error'),data
    print(json.dumps(data['return_value'],ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
