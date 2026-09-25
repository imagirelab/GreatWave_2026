"""公開集合・出典・履歴保護・相対リンクを読取専用で点検する。HOMを呼ばない。"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


def digest(raw): return hashlib.sha256(raw).hexdigest()
def git(root, *args): return subprocess.run(['git', *args], cwd=root, capture_output=True, check=True).stdout


def check(root):
    pub=root/'Houdini/Wave22/Evidence/Revision07'
    provenance=pub/'22_revision07_provenance.json'; manifest=json.loads(provenance.read_bytes())
    rows=manifest['records']; paths={r['path'] for r in rows}
    assert len(paths)==len(rows)==manifest['record_count']
    assert sum(r['bytes'] for r in rows)==manifest['total_record_bytes']
    paths.add(provenance.relative_to(root).as_posix())
    changed={x.decode('utf8') for x in git(root,'diff','--name-only','-z','HEAD').split(b'\0') if x}
    changed|={x.decode('utf8') for x in git(root,'ls-files','--others','--exclude-standard','-z').split(b'\0') if x}
    assert paths==changed, {'missing':sorted(changed-paths),'extra':sorted(paths-changed)}
    for row in rows:
        raw=(root/row['path']).read_bytes(); assert len(raw)==row['bytes'] and digest(raw)==row['sha256'], row['path']
    assert digest((root/'.gitattributes').read_bytes())==manifest['unchanged_git_attributes_sha256']
    originals=json.loads((pub/'22_original_manifest.json').read_bytes())
    for row in originals['records']:
        packed=(pub/row['path']).read_bytes(); raw=gzip.decompress(packed)
        assert len(packed)==row['stored_bytes'] and digest(packed)==row['stored_sha256']
        assert len(raw)==row['original_bytes'] and digest(raw)==row['original_sha256']
    candidate=root/'Houdini/Wave22/Candidates/PfsSensitivity07Refine474'
    fixed=json.loads((pub/'22_frozen_candidate_manifest.json').read_bytes())
    actual={p.relative_to(root).as_posix() for p in candidate.rglob('*') if p.is_file()}
    assert actual=={r['path'] for r in fixed['files']}
    for row in fixed['files']:
        raw=(root/row['path']).read_bytes(); assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
    prior=json.loads((candidate/'Evidence/22_prior_attempts_manifest.json').read_bytes())
    archived={r['original_path']:r for r in originals['records'] if r.get('origin_commit')}
    current_changes=[]
    for row in prior['files']:
        path=root/row['path']; raw=path.read_bytes()
        if row['path'] in archived:
            historic=gzip.decompress((pub/archived[row['path']]['path']).read_bytes())
            assert len(historic)==row['bytes'] and digest(historic)==row['sha256']
            if raw!=historic: current_changes.append(row['path'])
        else: assert len(raw)==row['bytes'] and digest(raw)==row['sha256'],row['path']
    assert set(current_changes)=={'README.md','Docs/Progress/README.md','Docs/Progress/Step_22_ja.md',
        'Docs/Progress/Verification_Status_ja.md','Houdini/Wave22/README_ja.md'}
    for name in prior['protected_directories']:
        actual={p.relative_to(root).as_posix() for p in (root/name).rglob('*') if p.is_file()}
        assert actual=={r['path'] for r in prior['files'] if r['path'].startswith(name+'/')},name
    links=0; text_files=0; gzip_files=0
    for name in sorted(paths):
        path=root/name
        assert not any(p in {'Runs','__pycache__'} for p in Path(name).parts) and not name.endswith(('.pyc','.bgeo.sc'))
        raw=path.read_bytes()
        if path.suffix=='.gz': raw=gzip.decompress(raw); gzip_files+=1
        elif path.suffix not in ('.md','.py','.json','.csv','.txt'): continue
        text=raw.decode('utf8'); text_files+=1
        assert '\ufffd' not in text, name
        assert not re.search(r'[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+',text),name
        assert not re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b',text),name
        if path.suffix!='.gz': assert b'\r' not in raw,name
        if path.suffix=='.py': compile(text,name,'exec')
        if path.suffix=='.md':
            for target in re.findall(r'!?\[[^\]]*\]\(([^\)]+)\)',text):
                target=target.strip('<>').split('#',1)[0]
                if not target or re.match(r'\w+://',target): continue
                assert (path.parent/unquote(target)).exists(),(name,target)
                links+=1
    attributes=git(root,'check-attr','-z','text','--',*sorted(paths)).split(b'\0')
    for i in range(0,len(attributes)-1,3): assert attributes[i+2]==b'unset',attributes[i:i+3]
    git(root,'diff','--check')
    return {'passed':True,'files':len(paths),'total_bytes':sum((root/p).stat().st_size for p in paths),
        'provenance_sha256':digest(provenance.read_bytes()),'candidate_files_exact':len(fixed['files']),
        'prior_files_verified':len(prior['files']),'historic_document_snapshots':len(archived),
        'authorized_current_document_updates':current_changes,'local_links':links,'scanned_text_including_gzip':text_files,
        'gzip_files_verified':gzip_files,'all_attributes_text_unset':True,'houdini_called':False,
        'staged_file_count':len([x for x in git(root,'diff','--cached','--name-only','-z').split(b'\0') if x])}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    print(json.dumps(check(parser.parse_args().root.resolve()),ensure_ascii=False,indent=2))
