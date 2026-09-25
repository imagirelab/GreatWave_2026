"""本機原記録を新しい公開先へ無損失複製する。Houdini/旧Runを書き換えない。"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


CASES = [
    ('Initial', 'PfsSensitivity06', 'pfs06_da9e62c8df', 'replay_360.json', 'HOLD_ASSERTION_BEFORE_INPUT', '入力署名前のAssertionError。原因は原記録だけでは確定しない。PFS未実行。'),
    ('Retry01', 'PfsSensitivity06Retry01', 'pfs06_4e658eee02', 'replay_360.json', 'HOLD_EMPTY_MANUAL_INPUT', 'ManualのFile/Null入力が空で停止。PFS未実行。'),
    ('Retry02', 'PfsSensitivity06Retry02', 'file06_261a7a4f72', 'file_probe_360.json', 'HOLD_HOM_KEYWORD', 'needsToCookのtimeキーワードによるTypeError。Auto窓前に停止。'),
    ('Retry03', 'PfsSensitivity06Retry03', 'file06_22b8368396', 'file_probe_360.json', 'HOLD_RAW_SIGNATURE_ORDER', '原比較はdetail属性一覧の順序差でHOLD。別のDecision04で許容範囲を限定した再解釈を保存。'),
    ('Replay05', 'PfsSensitivity06Replay05', 'pfsreplay06_55fa260d7f', 'replay_360.json', 'HOLD_HDA_TEXT_ENCODING', '入力一致後、HDA文字列UTF-8化でUnicodeEncodeError。第2Auto窓前、meshなし。'),
    ('Retry06', 'PfsSensitivity06Retry06', 'pfsreplay06_af76bc8ec2', 'replay_360.json', 'PASS_OLD_HALF_K360', 'HDA原binary bytesを読む修正後、旧.5のk360形状と三点nativeが厳密一致。'),
    ('Replay474', 'PfsSensitivity06Replay474', 'pfsreplay06_ac6451419c', 'replay_474.json', 'PASS_OLD_HALF_K474', '旧.5のk474形状と三点nativeが厳密一致。'),
    ('Replay496', 'PfsSensitivity06Replay496', 'pfsreplay06_b13cd6bcb8', 'replay_496.json', 'PASS_OLD_HALF_K496', '旧.5のk496形状と三点nativeが厳密一致。'),
    ('Refine360', 'PfsSensitivity06Refine360', 'pfsrefine06_c208ac35e3', 'refine_360.json', 'PASS_LOCAL_QUARTER_K360', 'k360だけ.25へ変更。入力・定義・局所390断面の診断成立。物理/波精度の合格ではない。'),
]


def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def curate(root, output):
    wave = root / 'Houdini/Wave22'
    output.mkdir(parents=True, exist_ok=True)
    records, cases, caches, source_maps = [], [], [], []
    for label, candidate, token, result, status, meaning in CASES:
        run = wave / 'Runs' / token
        for path in sorted(run.glob('*.json')):
            raw = path.read_bytes()
            # 公開原件は無修正。個人ディレクトリがあれば匿名化を自動せず停止する。
            text = raw.decode('utf8')
            assert ':\\\\Users\\\\' not in text and ':/Users/' not in text, path
            relative = Path('Original') / token / (path.name + '.gz')
            dest = output / relative; dest.parent.mkdir(parents=True, exist_ok=True)
            stored = gzip.compress(raw, compresslevel=9, mtime=0); dest.write_bytes(stored)
            assert gzip.decompress(dest.read_bytes()) == raw
            records.append({'path': relative.as_posix(), 'original_path': path.relative_to(root).as_posix(),
                            'original_bytes': len(raw), 'original_sha256': sha_bytes(raw),
                            'stored_bytes': len(stored), 'stored_sha256': sha_bytes(stored), 'representation': 'LOSSLESS_GZIP_MTIME_ZERO'})
        source_rows = []
        for path in sorted((run / 'Source').glob('*')):
            if path.is_file(): source_rows.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha_bytes(path.read_bytes())})
        source_maps.append({'token': token, 'candidate_directory': 'Houdini/Wave22/Candidates/' + candidate, 'executed_sources': source_rows})
        for path in sorted((run / 'Cache').glob('*.bgeo.sc')):
            caches.append({'token': token, 'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                           'sha256': sha_bytes(path.read_bytes()), 'published': False})
        cases.append({'label': label, 'candidate': candidate, 'token': token,
                      'result': f'Original/{token}/{result}.gz', 'execution': f'Original/{token}/execution.json.gz',
                      'status': status, 'meaning_ja': meaning})
    # 元04粒子と比較面は本機に保持し、公開manifestへSHAを結ぶ。
    latest = json.loads((wave / 'Candidates/PfsSensitivity06Refine360/Source/refine_plan.json').read_bytes())
    for k in ('360', '474', '496'):
        candidate = {'360': 'PfsSensitivity06Retry06', '474': 'PfsSensitivity06Replay474', '496': 'PfsSensitivity06Replay496'}[k]
        plan = json.loads((wave / 'Candidates' / candidate / 'Source/replay_plan.json').read_bytes())
        for kind in ('pilot', 'mesh'):
            rec = plan['record'][kind]; path = wave / 'Runs/22e7801642/Cache' / rec['filename']
            assert path.stat().st_size == rec['bytes'] and sha_bytes(path.read_bytes()) == rec['sha256']
            caches.append({'token': '22e7801642', 'path': path.relative_to(root).as_posix(), 'bytes': rec['bytes'], 'sha256': rec['sha256'], 'published': False})
    candidate_dirs = sorted({x[1] for x in CASES} | {'PfsSensitivity06Decision04'})
    candidate_files = []
    for name in candidate_dirs:
        for path in sorted((wave / 'Candidates' / name).rglob('*')):
            if path.is_file():
                assert path.suffix != '.pyc'
                candidate_files.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha_bytes(path.read_bytes())})
    source_index = {row['sha256']: row['path'] for row in candidate_files}
    for group in source_maps:
        for row in group['executed_sources']:
            if row['sha256'] not in source_index:
                path = wave / 'Runs' / group['token'] / 'Source' / row['name']
                dest = output / 'Executed_Source' / (row['sha256'][:12] + '_' + row['name'])
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(path.read_bytes())
                source_index[row['sha256']] = dest.relative_to(root).as_posix()
            row['published_source_path'] = source_index[row['sha256']]
    write(output / '22_original_manifest.json', {'meaning_ja': '原bytesを変更せずgzip保存。展開SHAと保存SHAを別記する。', 'records': records})
    write(output / '22_attempt_manifest.json', {'cases': cases, 'decision04': 'Houdini/Wave22/Candidates/PfsSensitivity06Decision04/Evidence/22_file_signature_adjudication.json', 'executed_source_maps': source_maps})
    write(output / '22_cache_manifest.json', {'meaning_ja': '本機BGEO実読によるSHA。公開包の復算ではBGEOを再読しない。', 'files': caches})
    write(output / '22_frozen_candidates_manifest.json', {'candidate_directories': candidate_dirs, 'file_count': len(candidate_files), 'files': candidate_files})
    # 隔離復算用の純関数だけを原bytesで同梱する。
    for name in ('refine_core06.py',):
        (output / 'Source' / name).write_bytes((wave / 'Candidates/PfsSensitivity06Refine360/Source' / name).read_bytes())
    print(json.dumps({'original_files': len(records), 'original_bytes': sum(x['original_bytes'] for x in records),
                      'stored_bytes': sum(x['stored_bytes'] for x in records), 'candidate_files': len(candidate_files), 'local_cache_files': len(caches)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); curate(args.root.resolve(), args.output.resolve())
