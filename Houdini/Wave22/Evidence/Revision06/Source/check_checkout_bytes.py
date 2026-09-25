"""一時Git索引でautocrlf=trueのcheckoutを検査し、実索引を変更しない。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


TARGETS = ['.gitattributes', 'README.md', 'Docs/Progress/README.md', 'Docs/Progress/Step_22_ja.md', 'Docs/Progress/Verification_Status_ja.md']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root):
    def git(*args, env=None):
        return subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True, text=True, encoding='utf8').stdout.strip()
    actual_index = Path(git('rev-parse', '--git-path', 'index'))
    if not actual_index.is_absolute(): actual_index = root / actual_index
    before_index = sha(actual_index)
    scratch = root / 'Houdini/Wave22/Local_Reproduction'; scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='checkout06_', dir=str(scratch)) as temp:
        temp = Path(temp); index = temp/'index'; checkout = temp/'checkout'; checkout.mkdir()
        env = os.environ.copy(); env['GIT_INDEX_FILE'] = str(index)
        git('read-tree', 'HEAD', env=env)
        git('add', '--', *TARGETS, env=env)
        git('-c', 'core.autocrlf=true', 'checkout-index', '--prefix='+checkout.as_posix()+'/', '--', *TARGETS, env=env)
        attrs = git('check-attr', 'text', '--', *TARGETS, env=env).splitlines()
        assert len(attrs) == len(TARGETS) and all(line.endswith(': text: unset') for line in attrs)
        rows=[]
        for name in TARGETS:
            original=root/name; copy=checkout/name
            assert original.read_bytes()==copy.read_bytes() and b'\r' not in original.read_bytes()
            rows.append({'path':name,'bytes':original.stat().st_size,'sha256':sha(original),'checkout_sha256':sha(copy),'text_attribute':'unset','exact':True})
    assert sha(actual_index)==before_index
    return {'passed':True,'meaning_ja':'autocrlf=trueで一時索引から実checkoutした。主索引・凍結候補・Runは変更しない。',
            'actual_index_unchanged':True,'core_autocrlf_forced_for_checkout':'true','source_sha256':sha(Path(__file__)),
            'targets':rows,'houdini_called':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--update-evidence',action='store_true')
    args=parser.parse_args();root=args.root.resolve();result=check(root)
    dest=root/'Houdini/Wave22/Evidence/Revision06/22_checkout_byte_validation.json'
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.update_evidence:dest.write_bytes(raw)
    else:assert dest.read_bytes()==raw
    print(json.dumps({'passed':True,'files':len(result['targets']),'actual_index_unchanged':True,'report_sha256':sha(dest),'evidence_updated':args.update_evidence}))
