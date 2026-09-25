"""既存JSONの比較だけ。detail属性一覧の列挙順以外は変更・正規化しない。"""
from copy import deepcopy
import math


def exact(a, b):
    """数値の型も保持する。辞書のキー順だけはJSONの意味に含めない。"""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b and (not isinstance(a, float) or math.isfinite(a))


def canonical_signature(signature):
    """比較用の深い複製だけを変更する。名前重複は拒否する。"""
    result = deepcopy(signature)
    rows = result['attribute_inventory']['detail']
    if not isinstance(rows, list):
        raise ValueError('detail一覧は列挙リストでなければならない')
    by_name = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name']:
            raise ValueError('detail属性名が不正')
        if row['name'] in by_name:
            raise ValueError('detail属性名の重複')
        by_name[row['name']] = row
    result['attribute_inventory']['detail'] = by_name
    return result


def compare_signatures(direct, other):
    try:
        return exact(canonical_signature(direct), canonical_signature(other))
    except (KeyError, TypeError, ValueError):
        return False


def leaf_differences(a, b, path=''):
    """原列挙順の差分を失わず保存する。"""
    if type(a) is not type(b):
        return [{'path': path, 'direct': a, 'observed': b}]
    if isinstance(a, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                result.append({'path': path + '/' + key, 'missing_direct': key not in a, 'missing_observed': key not in b})
            else:
                result.extend(leaf_differences(a[key], b[key], path + '/' + key))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': path, 'direct_length': len(a), 'observed_length': len(b)}]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in leaf_differences(x, y, path + '/' + str(i))]
    return [] if exact(a, b) else [{'path': path, 'direct': a, 'observed': b}]


AUTO_NAMES = tuple('AUTOUPDATE_' + node + '_' + moment + '_EXPLICIT_COOK'
                   for node in ('FILE', 'NULL') for moment in ('BEFORE', 'AFTER'))
UI_CHECKS = ('all_owned_paths_absent', 'selected_items_restored', 'global_context_restored',
             'pane_contexts_restored', 'pane_current_nodes_restored', 'pane_links_restored', 'active_tabs_restored',
             'frame_restored', 'fps_unchanged', 'update_mode_restored', 'viewer_state_restored', 'selection_mode_restored',
             'viewport_type_restored', 'viewport_visible_mask_restored', 'camera_binding_restored', 'camera_lock_restored',
             'camera_export_restored', 'view_transform_restored')


def adjudicate(raw, execution):
    """新しい判読を返す。原passed/equals_directは上書きしない。"""
    checks = {}
    def check(name, value):
        checks[name] = value is True
    check('original_hold_retained', raw['passed'] is False and execution['result']['passed'] is False
          and execution['passed_for_review'] is False)
    check('diagnostic_scope', raw['sample'] == 360 and raw['frame'] == 145.0 and raw['fps'] == 24.0
          and raw['new_meshing'] is False and raw['new_solver'] is False
          and execution['new_meshing'] is False and execution['new_solver'] is False)
    check('normal_completion', raw['phase'] == 'FINAL_SAVED' and not raw.get('failure_type')
          and not execution.get('failure_type') and not execution.get('cleanup_failure_type'))
    check('direct_counts', raw['direct_counts']['points'] == 53811 and raw['direct_counts']['primitives'] == 5
          and raw['direct_signature']['particle_count'] == 53806 and raw['direct_signature']['held_point_count'] == 5)
    check('manual_restored', raw['manual_restored_in_same_rpc'] is True and raw['update_mode'] == 'updateMode.Manual')
    check('main_thread_auto', raw['main_thread']['is_main'] is True
          and raw['temporary_update_mode'] == 'updateMode.AutoUpdate' and 0 < raw['auto_window_seconds'] < 90)
    check('no_external_dop_calls_recorded', raw['direct_external_DOP_calls'] is False)
    check('known_rpc_completion', execution['transport_completion_uncertain'] is False
          and all(e['completion_class'] == 'COMPLETE_SUCCESS' for e in execution['events']))
    cleanup = execution['cleanup']
    check('ui18', set(cleanup['checks']) == set(UI_CHECKS) and all(cleanup['checks'][k] is True for k in UI_CHECKS))
    check('owned_cleanup', cleanup['all_ui_and_owned_node_checks_passed'] is True and cleanup['restore_errors'] == []
          and cleanup['temporary_session_snapshot_removed'] is True)
    check('hip_undo_unchanged', cleanup['hip_saved_or_loaded'] is False and cleanup['undo_history_cleared'] is False
          and cleanup['prior_undo_labels_retained'] is True and cleanup['redo_stack_unchanged'] is True
          and cleanup['dirty_before'] == cleanup['dirty_after']
          and cleanup['undo_count_before'] == cleanup['undo_count_after'])
    observations = raw['node_observations']
    all_states = [state for row in observations.values() for state in row.values()
                  if isinstance(state, dict) and 'cook_count' in state]
    check('no_node_errors_or_warnings', bool(all_states) and all(s['errors'] == [] and s['warnings'] == [] for s in all_states))
    comparison = []
    for name in AUTO_NAMES:
        row = observations[name]
        differences = leaf_differences(raw['direct_signature'], row['signature'])
        equivalent = compare_signatures(raw['direct_signature'], row['signature'])
        check(name + '_counts', row['points'] == 53811 and row['primitives'] == 5)
        check(name + '_canonical_equal', equivalent)
        check(name + '_original_unequal', row['equals_direct'] is False)
        check(name + '_only_16_detail_order_leaves', len(differences) == 16
              and all(d['path'].startswith('/attribute_inventory/detail/') for d in differences))
        check(name + '_named_value_hashes_exact', exact(raw['direct_signature']['attribute_value_sha256'], row['signature']['attribute_value_sha256']))
        check(name + '_mode', row['capture_update_mode'] == 'updateMode.AutoUpdate' and row['signature_update_mode'] == 'updateMode.Manual')
        comparison.append({'observation': name, 'original_equals_direct': row['equals_direct'], 'canonical_equivalent': equivalent,
                           'raw_leaf_difference_count': len(differences), 'raw_leaf_differences': differences,
                           'direct_detail_order': [x['name'] for x in raw['direct_signature']['attribute_inventory']['detail']],
                           'observed_detail_order': [x['name'] for x in row['signature']['attribute_inventory']['detail']]})
    check('all_four_auto_signatures_exact', all(exact(observations[AUTO_NAMES[0]]['signature'], observations[n]['signature']) for n in AUTO_NAMES))
    cook = {}
    for node in ('FILE', 'NULL'):
        before = observations['AUTOUPDATE_' + node + '_BEFORE_EXPLICIT_COOK']
        force = observations['AUTOUPDATE_' + node + '_EXPLICIT_COOK']
        counts = [before['before_geometry_call']['cook_count'], before['after_geometry_call']['cook_count'], force['after']['cook_count']]
        check(node + '_cook_count_rose', counts[0] < counts[1] < counts[2]
              and force['before']['cook_count'] == counts[1] and force['after']['needs_to_cook'] is False)
        manual = observations['MANUAL_' + node + '_AFTER_EXPLICIT_COOK']
        check(node + '_manual_empty_recorded', manual['points'] == 0 and manual['primitives'] == 0
              and manual['after_geometry_call']['cook_count'] == 0 and manual['after_geometry_call']['needs_to_cook'] is True)
        cook[node] = {'auto_getter_then_explicit_cook_counts': counts, 'manual_points': manual['points'], 'auto_points': before['points'], 'auto_primitives': before['primitives']}
    return {'interpretation': 'RECORDED_SIGNATURES_EQUIVALENT_EXCEPT_DETAIL_ENUMERATION' if all(checks.values()) else 'HOLD',
            'new_offline_interpretation_passed': all(checks.values()), 'original_passed': raw['passed'], 'original_hold_overwritten': False,
            'houdini_called': False, 'pfs_parity_established': False, 'checks': checks, 'comparison': comparison, 'cook_observations': cook,
            'auto_window_seconds': raw['auto_window_seconds'], 'original_probe_seconds': raw['seconds'],
            'external_dop_state_monitored': raw['external_DOP_state_monitored'],
            'limitation_ja': '保存した署名の範囲で意味が一致し、detail属性の列挙順だけが異なる。原HOLDを改変しない。未保存の内部属性・intrinsic、他DOPの状態、PFS面化の同一性、流体の物理精度を認定しない。'}
