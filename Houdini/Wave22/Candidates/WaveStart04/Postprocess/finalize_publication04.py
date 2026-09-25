"""22修正04の公開出典を固定し、リンク・個人パス・行末・範囲を検査する。"""
import gzip
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

CANDIDATE=Path(__file__).resolve().parents[1]
REPO=Path(__file__).resolve().parents[5]
PROVENANCE=CANDIDATE/'Evidence/22_revision04_provenance.json'
DOCUMENTS=[REPO/p for p in ('README.md','Docs/Progress/Step_22_ja.md','Docs/Progress/README.md',
                           'Docs/Progress/Verification_Status_ja.md','Houdini/Wave22/README_ja.md')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=sorted([p for p in CANDIDATE.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p!=PROVENANCE]+DOCUMENTS)
assert not any(p.name.endswith(('.bgeo.sc','.log'))for p in paths)
links=0
for p in paths:
    raw=p.read_bytes();payload=gzip.decompress(raw)if p.suffix=='.gz'else raw
    if p.suffix in ('.py','.json','.md','.csv','.txt','.ass','.gz'):
        text=payload.decode('utf8');assert not re.search(r'[A-Z]:[\\/]Users[\\/]',text,re.I),p
        if p.suffix!='.gz':assert b'\r\n'not in payload,p
    if p.suffix=='.md':
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=unquote(target.strip('<>').split('#')[0])
            if not target or re.match(r'^[a-z]+://',target,re.I):continue
            resolved=(p.parent/target).resolve();assert resolved==PROVENANCE or resolved.exists(),(p,target)
            links+=1
report={'revision':'22修正04','baseline_case':'4250d4451f','candidate_case':'22e7801642',
        'previous_commit':'6bcd7fd8620db5490a81a57e2278cb092d9e1219','path_base':'repository_root',
        'static_gate_passed':True,'drive_authorized':True,'short_startup_response_observed':True,
        'solver_unique_feature_chain':True,'PFS_unique_feature_chain':False,
        'wave_verified':False,'physical_accuracy_verified':False,'step22_complete':False,
        'publication_checks':{'local_links_checked':links,'private_user_paths_found':0,'tracked_raw_bgeo':0,'text_LF':True},
        'records':[{'path':p.relative_to(REPO).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}for p in paths],
        'meaning_ja':'短槽の実始動診断。実行・公開復算・媒体読戻し・物理未認定を区別する。'}
PROVENANCE.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'records':len(paths),'links':links,'bytes':sum(p.stat().st_size for p in paths),'provenance_sha256':sha(PROVENANCE)}))
