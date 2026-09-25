"""Runsを含めない隔離コピーで公開資料だけの再計算を検査する。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser=argparse.ArgumentParser()
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
source=args.evidence.resolve()
repo=Path(__file__).resolve().parents[5]
temporary_parent=repo/'Local_Reproduction'
temporary_parent.mkdir(exist_ok=True)
assert temporary_parent.resolve().is_relative_to(repo.resolve())
script=Path(__file__).with_name('summarize_reseeding03.py')
expected=json.loads((source/'22_reproduction_manifest.json').read_text(encoding='utf8'))
before={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
with tempfile.TemporaryDirectory(prefix='reseed03_',dir=temporary_parent) as name:
    root=Path(name).resolve()
    assert root.is_relative_to(temporary_parent.resolve())
    target=root/'Evidence';target.mkdir()
    for directory in ('Original','Executed_Source'):
        shutil.copytree(source/directory,target/directory)
    for filename in ('22_original_manifest.json','22_execution_summary.json','22_cache_manifest.json'):
        shutil.copyfile(source/filename,target/filename)
    isolated_script=root/'Postprocess'/'summarize_reseeding03.py'
    isolated_script.parent.mkdir();shutil.copyfile(script,isolated_script)
    assert not list(root.rglob('*.bgeo.sc')) and not (root/'Runs').exists()
    result=subprocess.run([sys.executable,'-X','utf8',str(isolated_script),'--evidence',str(target)],
                          cwd=root,capture_output=True,text=True,encoding='utf8',check=True)
    products=[]
    for item in expected['products']:
        path=target/item['path']
        assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],item['path']
        products.append({'path':item['path'],'sha256':sha(path),'same_bytes':True})
    assert sha(target/'22_reproduction_manifest.json')==sha(source/'22_reproduction_manifest.json')
assert before=={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
report={'public_inputs_only':True,'houdini_called':False,'raw_bgeo_present':False,
        'raw_bgeo_rehashed':False,'source_inputs_unchanged':True,'passed':True,
        'products':products,'reproduction_manifest_same_bytes':True,
        'script_sha256':sha(script),'check_script_sha256':sha(Path(__file__)),
        'meaning_ja':'元入力を変更せず、Runsなしの隔離コピーで図2枚/CSV/数値摘要/READMEと再計算manifestの一致を確認。BGEO再検証ではない。'}
(source/'22_isolated_reproduction.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'passed':True,'products':len(products),'raw_bgeo_present':False}))
