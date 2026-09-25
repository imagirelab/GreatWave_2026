"""Runsなしの隔離コピーから4出力を復算し、元入力不変を検査する。"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
SOURCE=CANDIDATE/'Evidence/Result_22e7801642'
TEMP=CANDIDATE.parents[1]/'Local_Reproduction'
SCRIPT=Path(__file__).with_name('summarize_start04.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={p.relative_to(SOURCE).as_posix():sha(p)for p in SOURCE.rglob('*')if p.is_file()}
expected=json.loads((SOURCE/'22_reproduction_manifest.json').read_bytes())
TEMP.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='start04_',dir=TEMP)as folder:
    root=Path(folder).resolve();assert root.is_relative_to(TEMP.resolve())
    target=root/'Evidence';target.mkdir()
    for directory in ('Original','Executed_Source'):shutil.copytree(SOURCE/directory,target/directory)
    shutil.copyfile(SOURCE/'22_original_manifest.json',target/'22_original_manifest.json')
    script=root/'Postprocess/summarize_start04.py';script.parent.mkdir();shutil.copyfile(SCRIPT,script)
    assert not list(root.rglob('*.bgeo.sc')) and not(root/'Runs').exists()
    subprocess.run([sys.executable,'-X','utf8',str(script),'--input',str(target)],cwd=root,check=True,capture_output=True)
    products=[]
    for row in expected['outputs']:
        p=target/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path']
        products.append({**row,'same_bytes':True})
    assert sha(target/'22_reproduction_manifest.json')==sha(SOURCE/'22_reproduction_manifest.json')
assert before=={p.relative_to(SOURCE).as_posix():sha(p)for p in SOURCE.rglob('*')if p.is_file()}
report={'passed':True,'public_inputs_only':True,'source_inputs_unchanged':True,'houdini_called':False,
        'raw_bgeo_present':False,'raw_bgeo_rehashed':False,'products':products,'reproduction_manifest_same_bytes':True,
        'source_sha256':sha(SCRIPT),'check_source_sha256':sha(Path(__file__)),
        'meaning_ja':'CSV・2図・数値摘要をRunsなしで復算。実BGEOや撮影の再実行ではない。'}
(SOURCE/'22_isolated_reproduction.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'passed':True,'outputs':len(products),'raw_bgeo_present':False}))
