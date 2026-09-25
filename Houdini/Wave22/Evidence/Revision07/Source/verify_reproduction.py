"""Runs/候補ディレクトリ/BGEOを含めない一時コピーで公開復算を照合する。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def check(source, scratch):
    inputs = ['22_original_manifest.json', '22_run_manifest.json', 'Source/summarize_revision07.py', 'Source/refine_core06.py', 'Source/refine_contract07.py', 'Source/decision_core06.py']
    inputs += [p.relative_to(source).as_posix() for p in sorted(source.rglob('*.gz')) if p.is_file()]
    expected = json.loads((source/'22_analysis_manifest.json').read_bytes())
    outputs = [row['path'] for row in expected['outputs']] + ['22_analysis_manifest.json']
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='revision07_', dir=str(scratch)) as tmp:
        isolated = Path(tmp)/'input'; result = Path(tmp)/'output'
        for rel in inputs:
            dest=isolated/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,dest)
        assert not (isolated/'Runs').exists() and not (isolated/'Candidates').exists() and not list(isolated.rglob('*.bgeo.sc'))
        subprocess.run([sys.executable,'-X','utf8','-B',str(isolated/'Source/summarize_revision07.py'),'--input',str(isolated),'--output',str(result)],cwd=isolated,check=True,capture_output=True)
        rows=[]
        for rel in outputs:
            assert (source/rel).read_bytes()==(result/rel).read_bytes(),rel
            rows.append({'path':rel,'bytes':(result/rel).stat().st_size,'sha256':sha(result/rel),'exact':True})
    return {'passed':True,'houdini_called':False,'Runs_present':False,'BGEO_present':False,'candidate_directories_present':False,
            'meaning_ja':'公開原gzipと後処理だけの隔離復算。Houdini再計算や本機BGEO再読ではない。',
            'source_sha256':sha(Path(__file__)),'inputs':[{'path':rel,'bytes':(source/rel).stat().st_size,'sha256':sha(source/rel)} for rel in inputs],
            'outputs':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--scratch',type=Path,required=True);parser.add_argument('--update-evidence',action='store_true')
    args=parser.parse_args();source=args.input.resolve();report=check(source,args.scratch.resolve())
    raw=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8');dest=source/'22_isolated_reproduction.json'
    if args.update_evidence:dest.write_bytes(raw)
    else:assert dest.read_bytes()==raw
    print(json.dumps({'passed':True,'outputs':len(report['outputs']),'report_sha256':sha(dest),'evidence_updated':args.update_evidence}))
