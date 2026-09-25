"""既定は証拠を変更せず再検査する。反例はメモリー内の複製だけに作る。"""
import argparse
import ast
from copy import deepcopy
import json
from adjudicate_file06 import CANDIDATE, ROOT, encode, read, sha, verify_manifest, verified_inputs
from decision_core06 import AUTO_NAMES, adjudicate, canonical_signature, compare_signatures, exact, leaf_differences


def run_checks():
    checks = []
    def check(name, value):
        assert value, name
        checks.append({'name': name, 'passed': True})
    plan, raw, execution, prior = verified_inputs()
    original_raw, original_execution = encode(raw), encode(execution)
    base = raw['direct_signature']; observed = raw['node_observations'][AUTO_NAMES[0]]['signature']
    check('実記録の新判読成立', adjudicate(raw, execution)['new_offline_interpretation_passed'])
    check('原HOLD維持', raw['passed'] is False and execution['passed_for_review'] is False)
    check('四Auto署名一致', all(exact(observed, raw['node_observations'][n]['signature']) for n in AUTO_NAMES))
    for name in AUTO_NAMES:
        other = raw['node_observations'][name]['signature']
        diff = leaf_differences(base, other)
        check(name + 'の原16葉差分', len(diff) == 16 and all(d['path'].startswith('/attribute_inventory/detail/') for d in diff))
        check(name + 'の名前対応値SHA完全一致', exact(base['attribute_value_sha256'], other['attribute_value_sha256']))
    permuted = deepcopy(base); permuted['attribute_inventory']['detail'].reverse()
    check('detail順序だけの逆転を許可', compare_signatures(base, permuted))
    check('同一署名を許可', compare_signatures(base, base))
    copy_before = deepcopy(permuted); canonical_signature(permuted)
    check('比較対象dict無変更', exact(permuted, copy_before))
    for field, value in [('name', ''), ('type', 'attribData.InvalidForTest'), ('size', 999), ('array', True)]:
        mutant = deepcopy(base); mutant['attribute_inventory']['detail'][0][field] = value
        check('detail属性' + field + '変更を拒否', not compare_signatures(base, mutant))
    for kind in ('duplicate', 'missing', 'added', 'missing_name', 'not_list'):
        mutant = deepcopy(base); detail = mutant['attribute_inventory']['detail']
        if kind == 'duplicate': detail.append(deepcopy(detail[0]))
        elif kind == 'missing': detail.pop()
        elif kind == 'added': detail.append({'name': 'extra', 'type': 'attribData.Int', 'size': 1, 'array': False})
        elif kind == 'missing_name': del detail[0]['name']
        else: mutant['attribute_inventory']['detail'] = {}
        check('detailの' + kind + 'を拒否', not compare_signatures(base, mutant))
    for cls in ('point', 'primitive', 'vertex'):
        mutant = deepcopy(base); rows = mutant['attribute_inventory'][cls]
        if rows: rows.reverse()
        else: rows.append({'name': 'extra', 'type': 'attribData.Int', 'size': 1, 'array': False})
        check('detail以外' + cls + '一覧の変更を拒否', not compare_signatures(base, mutant))
    for key in base:
        if key == 'attribute_inventory': continue
        mutant = deepcopy(base); mutant[key] = {'unexpected': '不一致'}
        check('他の署名項目' + key + '変更を拒否', not compare_signatures(base, mutant))
    mutant = deepcopy(base)
    name = next(iter(mutant['attribute_value_sha256']['detail']))
    mutant['attribute_value_sha256']['detail'][name] = '0' * 64
    check('同名detail値SHA変更を拒否', not compare_signatures(base, mutant))
    mutant = deepcopy(base); mutant['fields'][0]['transform'][0] += 1e-15
    check('微小field座標差を拒否', not compare_signatures(base, mutant))
    mutant = deepcopy(base); mutant['fields'][0]['values_float64_sha256'] = '0' * 64
    check('field voxel SHA差を拒否', not compare_signatures(base, mutant))
    mutant = deepcopy(base); mutant['point_count'] = float(mutant['point_count'])
    check('型変更を拒否', not compare_signatures(base, mutant))
    mutant = deepcopy(base); mutant['extra'] = 0
    check('新キーを拒否', not compare_signatures(base, mutant))
    check('非有限値を拒否', not exact(float('nan'), float('nan')))
    raw_cases = {
        '原passed改変': lambda r: r.update(passed=True),
        '点数不足': lambda r: r['node_observations'][AUTO_NAMES[0]].update(points=0),
        'Manual復帰なし': lambda r: r.update(manual_restored_in_same_rpc=False),
        '別thread': lambda r: r['main_thread'].update(is_main=False),
        '警告あり': lambda r: r['node_observations'][AUTO_NAMES[0]]['after_geometry_call'].update(warnings=['警告']),
        'エラーあり': lambda r: r['node_observations'][AUTO_NAMES[0]]['after_geometry_call'].update(errors=['エラー']),
        'cook増加なし': lambda r: r['node_observations']['AUTOUPDATE_FILE_EXPLICIT_COOK']['after'].update(cook_count=1),
        '原equals改変': lambda r: r['node_observations'][AUTO_NAMES[0]].update(equals_direct=True),
        '新solver': lambda r: r.update(new_solver=True),
        'PFS実施': lambda r: r.update(new_meshing=True),
    }
    for name, mutate in raw_cases.items():
        mutant = deepcopy(raw); mutate(mutant)
        check(name + 'を拒否', not adjudicate(mutant, execution)['new_offline_interpretation_passed'])
    exec_cases = {
        'RPC不明': lambda e: e.update(transport_completion_uncertain=True),
        'UI失敗': lambda e: e['cleanup']['checks'].update(frame_restored=False),
        'owned残存': lambda e: e['cleanup']['checks'].update(all_owned_paths_absent=False),
        'UI項目欠落': lambda e: e['cleanup']['checks'].pop('fps_unchanged'),
        '復元エラー': lambda e: e['cleanup'].update(restore_errors=['失敗']),
        'session残存': lambda e: e['cleanup'].update(temporary_session_snapshot_removed=False),
        'HIP保存': lambda e: e['cleanup'].update(hip_saved_or_loaded=True),
        '実行エラー': lambda e: e['events'][0].update(completion_class='COMPLETE_ERROR'),
    }
    for name, mutate in exec_cases.items():
        mutant = deepcopy(execution); mutate(mutant)
        check(name + 'を拒否', not adjudicate(raw, mutant)['new_offline_interpretation_passed'])
    manifest = read(CANDIDATE / 'Evidence/22_prior_attempts_manifest.json')
    check('前4候補4Runの全80ファイル不変', prior['files'] == 80 and prior['exact_file_set'])
    for field, value in [('sha256', '0' * 64), ('bytes', -1)]:
        mutated = deepcopy(manifest); mutated['files'][0][field] = value
        rejected = False
        try: verify_manifest(ROOT, mutated)
        except AssertionError: rejected = True
        check('保護manifestの' + field + '差を拒否', rejected)
    for path in sorted((CANDIDATE / 'Source').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf8'))
        imports = [a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        imports += [n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        check(path.name + 'はHoudini/MCP/ネットワーク/プロセス実行をimportしない', not set(imports) & {'hou', 'mcp', 'fxhoudinimcp', 'subprocess', 'socket', 'requests', 'urllib', 'http'})
    check('全反例試験後も元dict不変', encode(raw) == original_raw and encode(execution) == original_execution)
    verified_inputs()
    return {'passed': True, 'houdini_called': False, 'checks': checks, 'check_count': len(checks),
            'source_hashes': {p.name: sha(p) for p in sorted((CANDIDATE / 'Source').glob('*')) if p.is_file()},
            'protected_files': prior, 'input_files': plan['inputs']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--update-evidence', action='store_true')
    args = parser.parse_args(); result = run_checks()
    path = CANDIDATE / 'Evidence/22_decision_offline_checks.json'
    if args.update_evidence: path.write_bytes(encode(result))
    else: assert path.read_bytes() == encode(result), '既存検査報告と再計算が一致しない'
    print(json.dumps({'passed': True, 'checks': result['check_count'], 'report_sha256': sha(path),
                      'houdini_called': False, 'evidence_updated': args.update_evidence}, ensure_ascii=False))
