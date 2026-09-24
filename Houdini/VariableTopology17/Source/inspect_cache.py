"""保存済み17キャッシュのみをMCP接続先で計測する。UIやノードは変更しない。"""
import asyncio,json
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
PYTHON=r'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe'
async def main():
 expected=json.loads((ROOT/'Evidence/17_connection.json').read_text())['metadata']['pid']
 params=StdioServerParameters(command=PYTHON,args=['-m','fxhoudinimcp'],env={'HOUDINI_HOST':'127.0.0.1','HOUDINI_PORT':'8100','MCP_TRANSPORT':'stdio','LOG_LEVEL':'ERROR'})
 with (ROOT/'Evidence/inspect_proxy.log').open('w') as err:
  async with stdio_client(params,errlog=err) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=180)) as client:
    await client.initialize()
    code=f'import os\nassert os.getpid()=={expected}\nSTAGE={str(ROOT)!r}\n'+(ROOT/'Source/validate_cached.py').read_text(encoding='utf8')
    response=await client.call_tool('execute_python',{'code':code,'return_expression':'result','justification':'新規17キャッシュの形状・粒子連結・継承IDを読み取り測定する。既存HIP/UI/ノードは変更しない。'})
    result=json.loads(next(c.text for c in response.content if c.type=='text'))
    assert not response.isError and result.get('executed') and not result.get('error'),result
    print(json.dumps(result['return_value'],ensure_ascii=False))
asyncio.run(main())
