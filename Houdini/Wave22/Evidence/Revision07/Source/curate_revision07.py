"""07実行原件と配対資料を無損失複製する。既存候補/Run/Houdiniには書き込まない。"""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

BASE_COMMIT = '352e1ba8fae0057c17dcbc9595d4177094c1b74d'
TOKEN = 'pfsrefine07_f2bf190159'
CANDIDATE = 'Houdini/Wave22/Candidates/PfsSensitivity07Refine474'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def curate(root, output):
    output.mkdir(parents=True, exist_ok=True)
    candidate = root / CANDIDATE
    run = root / 'Houdini/Wave22/Runs' / TOKEN
    plan = json.loads((candidate / 'Source/refine_plan.json').read_bytes())
    records = []
    def retain(raw, relative, origin, **metadata):
        text = raw.decode('utf8')
        assert not re.search(r'[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+', text), origin
        target = output / relative; target.parent.mkdir(parents=True, exist_ok=True)
        stored = gzip.compress(raw, compresslevel=9, mtime=0); target.write_bytes(stored)
        assert gzip.decompress(target.read_bytes()) == raw
        records.append({'path':relative, 'original_path':origin, 'original_bytes':len(raw), 'original_sha256':sha(raw),
                        'stored_bytes':len(stored), 'stored_sha256':sha(stored), 'representation':'LOSSLESS_GZIP_MTIME_ZERO', **metadata})
    for path in sorted(run.glob('*.json')):
        retain(path.read_bytes(), 'Original/' + TOKEN + '/' + path.name + '.gz', path.relative_to(root).as_posix())
    baseline_raw = root / plan['baseline_successes']['474']['raw']['path']
    assert sha(baseline_raw.read_bytes()) == plan['baseline_successes']['474']['raw']['sha256']
    retain(baseline_raw.read_bytes(), 'Baseline/replay_474.json.gz', baseline_raw.relative_to(root).as_posix())
    profile_raw = gzip.decompress((root / plan['profile05_baseline']['path']).read_bytes())
    assert sha(profile_raw) == plan['profile05_baseline']['original_sha256']
    retain(profile_raw, 'Baseline/profiles05_474.json.gz', plan['profile05_baseline']['path'], origin_is_gzip=True)
    # 実行時の進捗文書は固定commitから取り、今回の現況文書を上書きしない。
    prior = json.loads((candidate / 'Evidence/22_prior_attempts_manifest.json').read_bytes())
    for name in prior['protected_files']:
        raw = subprocess.run(['git', 'show', BASE_COMMIT + ':' + name], cwd=root, capture_output=True, check=True).stdout
        original = next(row for row in prior['files'] if row['path'] == name)
        assert len(raw) == original['bytes'] and sha(raw) == original['sha256']
        retain(raw, 'Baseline/Documents/' + name + '.gz', name, origin_commit=BASE_COMMIT)
    frozen = [{'path':p.relative_to(root).as_posix(), 'bytes':p.stat().st_size, 'sha256':sha(p.read_bytes())}
              for p in sorted(candidate.rglob('*')) if p.is_file()]
    assert not any('__pycache__' in r['path'] or r['path'].endswith('.pyc') for r in frozen)
    sources = []
    for path in sorted((run / 'Source').iterdir()):
        if not path.is_file(): continue
        published = CANDIDATE + '/Source/' + path.name
        if path.name == 'ui_guard.py':
            published = 'Houdini/Wave22/Candidates/WaveStart04/Evidence/Result_22e7801642/Executed_Source/ui_guard.py'
        assert (root / published).read_bytes() == path.read_bytes()
        sources.append({'name':path.name, 'bytes':path.stat().st_size, 'sha256':sha(path.read_bytes()), 'published_source_path':published})
    caches = []
    for kind in ('pilot', 'mesh'):
        expected = plan['record'][kind]; path = root / 'Houdini/Wave22/Runs/22e7801642/Cache' / expected['filename']
        assert path.stat().st_size == expected['bytes'] and sha(path.read_bytes()) == expected['sha256']
        caches.append({'path':path.relative_to(root).as_posix(), 'bytes':path.stat().st_size, 'sha256':sha(path.read_bytes()), 'published':False})
    result = json.loads((run / 'refine_474.json').read_bytes())
    path = run / 'Cache' / result['mesh_output']['filename']
    assert path.stat().st_size == result['mesh_output']['bytes'] and sha(path.read_bytes()) == result['mesh_output']['sha256']
    caches.append({'path':path.relative_to(root).as_posix(), 'bytes':path.stat().st_size, 'sha256':sha(path.read_bytes()), 'published':False})
    write(output / '22_original_manifest.json', {'meaning_ja':'原JSONをbyte単位で無損失保存する。Baseline/Documentsは実行前commitの履歴。', 'records':records})
    write(output / '22_run_manifest.json', {'token':TOKEN, 'candidate_directory':CANDIDATE, 'baseline_commit':BASE_COMMIT,
        'result':'Original/' + TOKEN + '/refine_474.json.gz', 'execution':'Original/' + TOKEN + '/execution.json.gz',
        'old_profile':'Original/' + TOKEN + '/profiles_old_474.json.gz', 'new_profile':'Original/' + TOKEN + '/profiles_new_474.json.gz',
        'baseline_replay':'Baseline/replay_474.json.gz', 'baseline_profile05':'Baseline/profiles05_474.json.gz', 'executed_sources':sources})
    write(output / '22_cache_manifest.json', {'meaning_ja':'本機BGEOの実bytes/SHA。公開復算はこのBGEOを読み直さない。', 'files':caches})
    write(output / '22_frozen_candidate_manifest.json', {'file_count':len(frozen), 'files':frozen})
    print(json.dumps({'original_records':len(records), 'original_bytes':sum(r['original_bytes'] for r in records),
                      'stored_bytes':sum(r['stored_bytes'] for r in records), 'frozen_files':len(frozen), 'local_BGEO':len(caches)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); curate(args.root.resolve(),args.output.resolve())
