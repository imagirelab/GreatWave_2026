"""22の接続先と組込みノードの型定義のみを読む。既存HIPの内容は読まない。"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
PYTHON = r"G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe"
CODE = r'''
import os
types=hou.sopNodeTypeCategory().nodeTypes()
schema={}
for name in ('flipcontainer','flipboundary','flipcollide','flipsolver','box','particlefluidsurface::3.0'):
    nt=types.get(name)
    assert nt is not None,name
    rows=[]
    for pt in nt.parmTemplateGroup().entriesWithoutFolders():
        row={'name':pt.name(),'label':pt.label(),'type':str(pt.type())}
        if hasattr(pt,'defaultValue'):row['default']=pt.defaultValue()
        if hasattr(pt,'menuItems'):row['menu_items']=pt.menuItems();row['menu_labels']=pt.menuLabels()
        rows.append(row)
    schema[name]=rows
result={'pid':os.getpid(),'version':hou.applicationVersionString(),'ui':hou.isUIAvailable(),'license':str(hou.licenseCategory()),'fps':hou.fps(),'node_schema':schema}
'''

async def main():
    (ROOT / 'Evidence').mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(command=PYTHON, args=['-m', 'fxhoudinimcp'], env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
    with (ROOT / 'Evidence/probe_proxy.log').open('w', encoding='utf-8') as err:
        async with stdio_client(params, errlog=err) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=45)) as client:
                init=await client.initialize()
                response=await client.call_tool('execute_python', {'code':CODE,'return_expression':'result','justification':'22の事前確認として接続先のPID/版/分類/FPSとノード型定義を読む。既存HIPのノードや形状を調べず、変更しない。'})
                data=json.loads(next(x.text for x in response.content if x.type=='text'))
                assert not response.isError and data.get('executed') and not data.get('error'),data
                value=data['return_value'];schema=value.pop('node_schema')
                report={'utc':datetime.now(timezone.utc).isoformat(),'protocol':init.protocolVersion,'metadata':value,'scene_read_or_changed':False}
                for name,obj in [('22_connection.json',report),('22_node_schema.json',schema)]:
                    (ROOT/'Evidence'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
                print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
