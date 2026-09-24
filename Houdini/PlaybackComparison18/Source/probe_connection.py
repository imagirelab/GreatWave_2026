"""18の開始前に、実行環境とVAT型の登録状況だけを読み取る。"""
import asyncio, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
async def main():
    (ROOT/'Evidence').mkdir(parents=True,exist_ok=True)
    params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
    with (ROOT/'Evidence/probe_proxy.log').open('w',encoding='utf8') as err:
        async with stdio_client(params,errlog=err) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=45)) as client:
                init=await client.initialize()
                response=await client.call_tool('execute_python',{'code':'import os\nresult={"pid":os.getpid(),"version":hou.applicationVersionString(),"ui":hou.isUIAvailable(),"license":str(hou.licenseCategory()),"fps":hou.fps(),"vat_types":[{"category":cat.name(),"name":name,"library":nt.definition().libraryFilePath() if nt.definition() else None} for cat in hou.nodeTypeCategories().values() for name,nt in cat.nodeTypes().items() if "vertex_animation" in name.lower() or "vat" in name.lower() and "labs" in name.lower()],"hfs":hou.getenv("HFS"),"labs":hou.getenv("SIDEFXLABS"),"alembic_rop_available":"alembic" in hou.ropNodeTypeCategory().nodeTypes()}','return_expression':'result','justification':'手順18の開始前にPID・版・ライセンス分類とVAT登録型を読む。既存HIPの内容や形状を調べない。'})
                result=json.loads(next(c.text for c in response.content if c.type=='text'))
                assert not response.isError and result.get('executed') and not result.get('error'),result
                report={'utc':datetime.now(timezone.utc).isoformat(),'protocol':init.protocolVersion,'metadata':result['return_value'],'scene_read_or_changed':False}
                (ROOT/'Evidence/18_connection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
