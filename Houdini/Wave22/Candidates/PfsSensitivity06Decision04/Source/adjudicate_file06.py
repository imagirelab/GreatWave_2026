"""既定は読み取り専用の再照合。Houdini/MCPをimportも実行もしない。"""
import argparse
import hashlib
import json
from pathlib import Path
from decision_core06 import adjudicate, exact

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = CANDIDATE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSONキーの重複: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('非有限JSON値: ' + value)
    return json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=invalid)


def verify_manifest(root, manifest):
    seen = set()
    for row in manifest['files']:
        name = row['path']
        path = (root / name).resolve()
        assert path.is_relative_to(root.resolve()) and name not in seen, '保護対象パスが不正'
        seen.add(name)
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], '保護対象bytes/SHAが変化: ' + name
    assert len(seen) == manifest['file_count'] and sum(r['bytes'] for r in manifest['files']) == manifest['total_bytes']
    actual = {p.relative_to(root).as_posix() for name in manifest['protected_directories'] for p in (root / name).rglob('*') if p.is_file()}
    assert actual == seen, '保護ディレクトリのファイル集合が変化'
    return {'files': len(seen), 'bytes': manifest['total_bytes'], 'exact_file_set': True}


def verified_inputs():
    plan = read(CANDIDATE / 'Source/decision_plan.json')
    assert plan['scope'] == 'OFFLINE_RETRY03_SIGNATURE_ADJUDICATION_ONLY' and plan['houdini_allowed'] is False
    manifest_path = CANDIDATE / 'Evidence/22_prior_attempts_manifest.json'
    assert sha(manifest_path) == plan['prior_attempts_manifest_sha256']
    prior = verify_manifest(ROOT, read(manifest_path))
    files = {}
    for name, row in plan['inputs'].items():
        path = ROOT / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], '入力bytes/SHAが変化: ' + name
        files[name] = path
    raw, execution = read(files['raw_result']), read(files['execution'])
    assert execution['token'] == 'file06_22b8368396'
    assert execution['result']['file'] == files['raw_result'].name
    assert execution['result']['sha256'] == sha(files['raw_result']) and execution['result']['bytes'] == files['raw_result'].stat().st_size
    original_source = files['execution'].parent / 'Source'
    for name, expected in execution['source_hashes'].items():
        assert sha(original_source / name) == expected, '実行元sourceが変化'
    combined = '\n'.join((original_source / name).read_text(encoding='utf8') for name in ('support06.py', 'probe_file06.py'))
    assert hashlib.sha256(combined.encode('utf8')).hexdigest() == raw['combined_source_sha256'] == execution['combined_source_sha256']
    assert sha(original_source / 'file_probe_plan.json') == raw['plan_sha256'] == execution['plan_sha256']
    assert raw['source_cache_sha_after'] == sha(files['physical_input_cache'])
    expected_phases = ['METADATA', 'SNAPSHOT', 'OWNED_SETUP', 'FILE_NULL_DIAGNOSTIC', 'RESTORE_UI18']
    assert [e['phase'] for e in execution['events']] == expected_phases
    replies = []
    for event in execution['events']:
        reply = json.loads(event['raw_response_local'])
        assert reply['executed'] is True and not reply.get('error') and not reply.get('eval_error')
        replies.append(reply['return_value'])
    assert replies[3]['json_sha256'] == sha(files['raw_result']) and replies[3]['source_sha256'] == raw['combined_source_sha256']
    assert exact(replies[4], execution['cleanup']), 'UI復元ACKと保存値が不一致'
    assert exact(replies[0], execution['metadata']) and exact(replies[1], execution['snapshot']) and exact(replies[2], execution['setup'])
    return plan, raw, execution, prior


def build_report():
    plan, raw, execution, prior = verified_inputs()
    before_raw, before_execution = encode(raw), encode(execution)
    result = adjudicate(raw, execution)
    assert encode(raw) == before_raw and encode(execution) == before_execution, '比較で入力dictを変更した'
    result['source_hashes'] = {p.name: sha(p) for p in sorted((CANDIDATE / 'Source').glob('*')) if p.is_file()}
    result['input_files'] = plan['inputs']
    result['prior_protection'] = prior
    result['prior_manifest_sha256'] = plan['prior_attempts_manifest_sha256']
    result['ui18_checks'] = execution['cleanup']['checks']
    result['transport_completion_uncertain'] = execution['transport_completion_uncertain']
    result['resources_observed'] = {'minimum_available_bytes': min(x['available_bytes'] for x in raw['resources']),
                                    'maximum_private_bytes': max(x['private_bytes'] for x in raw['resources']),
                                    'minimum_free_G_bytes': min(x['free_G_bytes'] for x in raw['resources'])}
    assert all(result['checks'].values()), '判読条件不成立。原資料は変更しない'
    verified_inputs()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-evidence', action='store_true', help='新候補の判読JSONだけを明示更新する')
    args = parser.parse_args()
    result = build_report()
    target = CANDIDATE / 'Evidence/22_file_signature_adjudication.json'
    if args.write_evidence:
        target.write_bytes(encode(result))
    else:
        assert target.read_bytes() == encode(result), '保存済み判読とのbytes不一致'
    print(json.dumps({'interpretation': result['interpretation'], 'checks': len(result['checks']),
                      'report_sha256': sha(target), 'houdini_called': False, 'evidence_updated': args.write_evidence}, ensure_ascii=False))
