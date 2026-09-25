"""今回公開する通常Gitファイルの集合と元bytesを固定する。stage/commitしない。"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root):
    publication=root/'Houdini/Wave22/Evidence/Revision06'; dest=publication/'22_revision06_provenance.json'
    frozen=json.loads((publication/'22_frozen_candidates_manifest.json').read_bytes())
    originals=json.loads((publication/'22_original_manifest.json').read_bytes())
    candidates=[root/r['path'] for r in frozen['files']]
    assert all(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'] for p,r in zip(candidates,frozen['files']))
    paths=candidates+[p for p in publication.rglob('*') if p.is_file() and p!=dest and p.suffix!='.pyc']
    paths += [root/n for n in ('.gitattributes','README.md','Docs/Progress/README.md','Docs/Progress/Step_22_ja.md','Docs/Progress/Verification_Status_ja.md','Houdini/Wave22/README_ja.md')]
    assert len(paths)==len(set(paths)) and not any(p.suffix=='.bgeo.sc' or '__pycache__' in p.parts for p in paths)
    records=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(paths)]
    value={'revision':'22修正06','baseline_commit':'76fabdf8ce09ee7b4ad3f531e61cdda8dba51116',
           'meaning_ja':'凍結候補は元bytesの通常Gitファイル。原Runは無損失gzip。BGEOは本機保持。記録のPASSは単一時刻の局所面化に限る。',
           'records':records,'record_count':len(records),'total_record_bytes':sum(r['bytes'] for r in records),
           'original_run_json_count':len(originals['records']),
           'original_manifest_sha256':sha(publication/'22_original_manifest.json'),
           'candidate_manifest_sha256':sha(publication/'22_frozen_candidates_manifest.json'),
           'isolated_reproduction_sha256':sha(publication/'22_isolated_reproduction.json')}
    dest.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'records':len(records),'files_including_self':len(records)+1,'total_record_bytes':value['total_record_bytes'],'provenance_sha256':sha(dest)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();prepare(args.root.resolve())
