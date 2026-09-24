"""実BGEOのsolver SDFを床直上まで読み戻す。既存HIP/UI/時刻は変更しない。"""
import asyncio
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
TOKEN=sys.argv[1]
RUN=ROOT/'Runs'/TOKEN
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
PID=json.loads((ROOT/'Evidence/22_connection.json').read_text(encoding='utf8'))['metadata']['pid']
CODE=r'''
import hashlib,json,math,os
from pathlib import Path
assert os.getpid()==EXPECTED_PID and hou.isUIAvailable()
before={'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges()}
source=Path(RUN)/'Evidence/22_pilot_samples.json'
samples=json.loads(source.read_text(encoding='utf8'))['samples']
rows=[]
for row in samples:
    path=Path(RUN)/('Cache/pilot_%03d.bgeo.sc'%row['sample'])
    cache_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert cache_sha==row['cache_sha256']
    geo=hou.Geometry();geo.loadFromFile(str(path))
    volumes=[p for p in geo.prims() if isinstance(p,hou.Volume) and p.attribValue('name')=='surface']
    assert len(volumes)==1
    vol=volumes[0];lo=vol.boundingBox().minvec();hi=vol.boundingBox().maxvec()
    voxel=list(vol.voxelSize());gauges=[]
    for original in row['gauges']:
        x=original['x'];z=original['z'];eta=original['eta_m']
        bottom=-.6+.0001;top=eta-.0001
        inside=lo[0]<x<hi[0] and lo[2]<z<hi[2] and lo[1]<bottom<top<hi[1]
        count=max(2,math.ceil((top-bottom)/(min(voxel)/2))+1)
        ys=[bottom+(top-bottom)*i/(count-1) for i in range(count)]
        values=[float(vol.sample((x,y,z))) for y in ys] if inside else []
        finite=bool(values) and all(math.isfinite(v) for v in values)
        connected=original['valid'] and inside and finite and all(v<0 for v in values)
        gauges.append({'x_m':x,'z_m':z,'local_crossing_valid':original['valid'],
                       'bed_clearance_m':.0001,'root_clearance_m':.0001,
                       'sampling_step_max_m':min(voxel)/2,'inside_field_bounds':inside,
                       'finite':finite,'bottom_connected_at_sample_resolution':connected,
                       'y_m':ys,'phi_m':values})
    rows.append({'sample':row['sample'],'seconds':row['requested_seconds'],'cache_sha256':cache_sha,
                 'surface_bounds_m':[list(lo),list(hi)],'surface_voxel_m':voxel,'gauges':gauges})
    del vol,volumes,geo
after={'frame':hou.frame(),'fps':hou.fps(),'dirty':hou.hipFile.hasUnsavedChanges()}
assert before==after
report={'token':TOKEN,'source_samples_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'method_ja':'床直上0.1mmから記録済み局所自由面0.1mm下まで、最小voxel辺の半分以下でSDFを照会。全点が実field bounds内かつ負の時だけ連結診断を通す。粒子体積・完全な連続体の証明ではない。',
        'existing_hip_read_or_changed':False,'ui_frame_fps_dirty_before_after':[before,after],
        'rows':rows,'all_queries_passed':all(g['bottom_connected_at_sample_resolution'] for r in rows for g in r['gauges'])}
dest=Path(RUN)/'Evidence/22_bottom_connection.json'
dest.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
result={'samples':len(rows),'queries':sum(len(r['gauges']) for r in rows),'all_queries_passed':report['all_queries_passed'],
        'failed':[(r['sample'],g['x_m']) for r in rows for g in r['gauges'] if not g['bottom_connected_at_sample_resolution']],
        'report_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'before_after_equal':before==after}
'''

async def main():
    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
    with (RUN/'Evidence/readback_proxy.log').open('w',encoding='utf8') as error:
        async with stdio_client(params,errlog=error) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as session:
                await session.initialize()
                code=f'EXPECTED_PID={PID!r}\nRUN={str(RUN)!r}\nTOKEN={TOKEN!r}\n'+CODE
                response=await session.call_tool('execute_python',{'code':code,'return_expression':'result','justification':'22の所有キャッシュだけをメモリへ読戻し、底から水面へのSDF連続性を検査する。既存HIP/UI/時刻/ノードを変更しない。'})
                data=json.loads(next(b.text for b in response.content if b.type=='text'))
                assert not response.isError and data.get('executed') and not data.get('error'),data
                result=data['return_value'];result['reader_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
                (RUN/'Evidence/22_bottom_connection_execution.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
                print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
