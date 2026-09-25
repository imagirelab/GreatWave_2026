"""07公開ファイルの集合と原bytesを固定する。Git索引・実行候補・原Runは変更しない。"""
import argparse
import hashlib
import json
from pathlib import Path

DOCUMENTS = ['README.md', 'Docs/Progress/README.md', 'Docs/Progress/Step_22_ja.md',
             'Docs/Progress/Verification_Status_ja.md', 'Houdini/Wave22/README_ja.md']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root):
    publication = root / 'Houdini/Wave22/Evidence/Revision07'
    dest = publication / '22_revision07_provenance.json'
    frozen = json.loads((publication / '22_frozen_candidate_manifest.json').read_bytes())
    candidates = [root / row['path'] for row in frozen['files']]
    for path, row in zip(candidates, frozen['files']):
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], path
    paths = candidates + [p for p in publication.rglob('*') if p.is_file() and p != dest and p.suffix != '.pyc']
    paths += [root / p for p in DOCUMENTS]
    assert len(paths) == len(set(paths))
    assert not any('__pycache__' in p.parts or 'Runs' in p.relative_to(root).parts or p.name.endswith('.bgeo.sc') for p in paths)
    records = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(paths)]
    value = {'revision': '22修正07', 'baseline_commit': '352e1ba8fae0057c17dcbc9595d4177094c1b74d',
        'meaning_ja': '凍結候補14件は元bytes。原Runは無損失gzip、BGEOは本機保持。現況文書5件だけを更新し、実行前文書は別保存する。',
        'records': records, 'record_count': len(records), 'total_record_bytes': sum(r['bytes'] for r in records),
        'original_manifest_sha256': sha(publication / '22_original_manifest.json'),
        'candidate_manifest_sha256': sha(publication / '22_frozen_candidate_manifest.json'),
        'isolated_reproduction_sha256': sha(publication / '22_isolated_reproduction.json'),
        'unchanged_git_attributes_sha256': sha(root / '.gitattributes')}
    dest.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'records': len(records), 'files_including_self': len(records)+1,
                     'total_bytes_including_self': value['total_record_bytes']+dest.stat().st_size,
                     'provenance_sha256': sha(dest)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    prepare(parser.parse_args().root.resolve())
