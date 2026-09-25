"""22修正03の公開候補をハッシュ・リンク・個人パス検査で固定する。"""
import gzip
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

CANDIDATE=Path(__file__).resolve().parents[1]
REPO=Path(__file__).resolve().parents[5]
PROVENANCE=CANDIDATE/'Evidence/22_revision03_provenance.json'
DOCUMENTS=[REPO/p for p in ('README.md','Docs/Progress/Step_22_ja.md','Docs/Progress/README.md',
                           'Docs/Progress/Verification_Status_ja.md','Houdini/Wave22/README_ja.md')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths=sorted([p for p in CANDIDATE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=PROVENANCE]+DOCUMENTS)
assert not any(p.suffix=='.bgeo.sc' or p.name.endswith('.log') for p in paths)
link_count=0
for path in paths:
    payload=path.read_bytes()
    if path.suffix=='.gz':payload=gzip.decompress(payload)
    if path.suffix in ('.py','.md','.json','.txt','.csv','.gz'):
        text=payload.decode('utf8')
        assert not re.search(r'[A-Z]:[\\/]Users[\\/]',text,re.I),path
        if path.suffix!='.gz':assert b'\r\n' not in payload,path
    if path.suffix=='.md':
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=unquote(target.strip('<>').split('#')[0])
            if not target or re.match(r'^[a-z]+://',target,re.I):continue
            resolved=(path.parent/target).resolve()
            assert resolved==PROVENANCE or resolved.exists(),(path,target)
            link_count+=1
report={'revision':'22修正03','baseline_case':'db52394211','candidate_case':'4250d4451f',
        'previous_commit':'7ddbc83cce083f49d17b59ab210fb331774964e4',
        'path_base':'repository_root','static_gate_passed':True,'drive_authorized':False,
        'wave_verified':False,'physical_accuracy_verified':False,
        'publication_checks':{'local_links_checked':link_count,'private_user_paths_found':0,'tracked_raw_bgeo':0,'text_LF':True},
        'records':[{'path':str(p.relative_to(REPO)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths],
        'meaning_ja':'元実行Sourceと原JSON/gzipを保持。公開再計算・実BGEO照合・静水判定はそれぞれ別記録。'}
PROVENANCE.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'records':len(paths),'links':link_count,'bytes':sum(p.stat().st_size for p in paths),
                  'provenance_sha256':sha(PROVENANCE)},ensure_ascii=False))
