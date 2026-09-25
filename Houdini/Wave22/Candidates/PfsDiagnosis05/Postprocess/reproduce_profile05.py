"""Runs/BGEOを持たない隔離入力から05の全解析出力を再現する。"""
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
SOURCE=CANDIDATE/'Evidence/Result_22e7801642'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(root):return {p.relative_to(root).as_posix():sha(p)for p in sorted(root.rglob('*'))if p.is_file()}
def main():
    # 新規所有ディレクトリのみ。既存成果を削除・移動しない。
    work=WAVE/'Runs'/('reproduce_profile05_'+uuid.uuid4().hex[:10]);work.mkdir(exist_ok=False)
    copied=work/'input';shutil.copytree(SOURCE,copied,ignore=shutil.ignore_patterns('__pycache__','22_profile05_isolated_reproduction.json'))
    script=work/'summarize_profile05.py';script.write_bytes((CANDIDATE/'Postprocess/summarize_profile05.py').read_bytes())
    assert not list(copied.rglob('*.bgeo.sc'))and not any(p.name=='Runs'for p in copied.rglob('*'))
    before=tree(copied);result=subprocess.run([sys.executable,'-B','-X','utf8',str(script),'--input',str(copied),'--output',str(work/'output')],cwd=work,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr
    after=tree(copied);assert before==after and not list(copied.rglob('__pycache__'))
    names=['22_profile05_sections.csv','22_profile05_summary.json','22_profile05_centers.png','22_profile05_sections.png','22_profile05_G3_prominence.png','22_profile05_analysis_manifest.json']
    matched=[]
    for name in names:
        p=work/'output'/name;assert p.read_bytes()==(SOURCE/name).read_bytes()
        matched.append({'path':name,'sha256':sha(p),'bytes':p.stat().st_size})
    report={'passed':True,'input_records':len(before),'input_bytes_unchanged':True,'copied_analysis_sha256':sha(script),
            'no_BGEO_or_Runs_in_input':True,'no_generated_bytecode_in_input':True,'outputs':matched,'Houdini_called':False,'MCP_called':False,
            'meaning_ja':'コピーした公開JSON/gzip/Baseline04/Executed_Sourceだけを--inputへ指定。解析は隔離cwdで実行し、原04フォルダーやRunsを参照しない。fontと描画依存は同じ環境。BGEO再照合ではない。'}
    (SOURCE/'22_profile05_isolated_reproduction.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'passed':True,'outputs':len(matched),'input_unchanged':True,'houdini_called':False}))

if __name__=='__main__':main()
