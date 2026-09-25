"""所有File/Nullの読戻し診断。定義の読込だけではHOMを呼ばない。"""
import hashlib
import json
import math
import time
import threading
import traceback
from pathlib import Path


def finite_value06(value):
    if value is None or isinstance(value, (bool, int, str)): return value
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('非有限属性値')
        return value
    if isinstance(value, (tuple, list)): return [finite_value06(v) for v in value]
    if isinstance(value, dict): return {str(k): finite_value06(v) for k, v in sorted(value.items())}
    raise TypeError('未対応の属性値型: ' + type(value).__name__)


def value_hash06(value):
    return hashlib.sha256(json.dumps(finite_value06(value), ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf8')).hexdigest()


def attribute_inventory06(geometry):
    return {label: [{'name': a.name(), 'type': str(a.dataType()), 'size': a.size(), 'array': a.isArrayType()}
                    for a in attrs()] for label, attrs in (
                        ('point', geometry.pointAttribs), ('primitive', geometry.primAttribs),
                        ('vertex', geometry.vertexAttribs), ('detail', geometry.globalAttribs))}


def all_geometry_signature06(hou_api, geometry):
    """全属性・群・接続と、粒子/5場の数値を別々に記録する。未知型は停止。"""
    result = input_signature06(hou_api, geometry)
    scopes = [('point', geometry.pointAttribs(), geometry.points()),
              ('primitive', geometry.primAttribs(), geometry.prims()),
              ('vertex', geometry.vertexAttribs(), tuple(v for p in geometry.prims() for v in p.vertices())),
              ('detail', geometry.globalAttribs(), (geometry,))]
    result['attribute_inventory'] = attribute_inventory06(geometry)
    result['attribute_value_sha256'] = {label: {a.name(): value_hash06([element.attribValue(a) for element in elements])
                                               for a in attrs} for label, attrs, elements in scopes}
    result['oriented_indices'] = [[v.point().number() for v in p.vertices()] for p in geometry.prims()]
    result['groups'] = {
        'point': {g.name(): [p.number() for p in g.points()] for g in geometry.pointGroups()},
        'primitive': {g.name(): [p.number() for p in g.prims()] for g in geometry.primGroups()},
        'vertex': {g.name(): [[v.prim().number(), v.number()] for v in g.vertices()] for g in geometry.vertexGroups()},
        'edge': {g.name(): [sorted(p.number() for p in edge.points()) for edge in g.edges()] for g in geometry.edgeGroups()}}
    return result


def parm_record06(parm):
    template = parm.parmTemplate()
    result = {'name': parm.name(), 'label': template.label(), 'template_type': str(template.type()),
              'raw_value': parm.rawValue(), 'evaluated': finite_value06(parm.eval())}
    # Parm.menuItemsは非MenuでOperationFailed。template/動的Menuを先に判別する。
    template_items = list(template.menuItems()) if hasattr(template, 'menuItems') else []
    if str(template.type()) == 'parmTemplateType.Menu' or template_items or parm.isDynamicMenu():
        result['menu_items'] = list(parm.menuItems()); result['menu_labels'] = list(parm.menuLabels())
    return result


def node_state06(node, hou_api):
    return {'name': node.name(), 'type': node.type().name(), 'cook_count': node.cookCount(),
            'needs_to_cook': node.needsToCook(), 'needs_to_cook_at_seconds': hou_api.time(), 'errors': list(node.errors()), 'warnings': list(node.warnings()),
            'display': node.isDisplayFlagSet(), 'render': node.isRenderFlagSet(), 'bypassed': node.isBypassed(),
            'hard_locked': node.isHardLocked(), 'soft_locked': node.isSoftLocked(), 'unload': node.isUnloadFlagSet()}


def probe_file06(hou_api, key, owner_path, raw_path, plan, output_path):
    started = time.monotonic(); raw_path = Path(raw_path); output_path = Path(output_path)
    record = {'sample': 360, 'phase': 'BEGIN', 'passed': False, 'new_meshing': False, 'new_solver': False,
              'node_observations': {}, 'resources': [], 'history': [], 'geometry_getter_may_cook': True}
    auto_active = False
    deferred_geometry = []
    def save(phase):
        record['phase'] = phase
        record['history'].append({'phase': phase, 'seconds': time.monotonic() - started})
        if not auto_active:
            output_path.write_bytes((json.dumps(serializable_observation(record), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
    initial_private = None
    def health():
        nonlocal initial_private
        value = memory06(raw_path.anchor); record['resources'].append(value)
        if initial_private is None: initial_private = value['private_bytes']
        limits = plan['budgets']
        assert value['available_bytes'] >= limits['minimum_available_RAM_bytes'], '可用RAM保護'
        assert value['private_bytes'] - initial_private < limits['maximum_private_increase_bytes'], 'private増分保護'
        assert value['free_G_bytes'] >= limits['minimum_free_G_bytes'], 'G空き保護'
        assert time.monotonic() - started <= limits['per_rpc_cooperative_seconds'], '協調時間保護'
    def sample_geometry(node, label, defer=False):
        observation = {'before_geometry_call': node_state06(node, hou_api)}
        record['node_observations'][label] = observation; save(label + '_BEFORE_GEOMETRY')
        geometry = node.geometry().freeze()
        observation['after_geometry_call'] = node_state06(node, hou_api)
        observation['points'] = len(geometry.points()); observation['primitives'] = len(geometry.prims())
        observation['attributes'] = attribute_inventory06(geometry)
        observation['capture_update_mode'] = str(hou_api.updateModeSetting())
        save(label + '_COUNTS')
        if defer:
            deferred_geometry.append((label, geometry))
            return observation
        # 空も証拠として残し、署名関数へ渡して上書き例外にしない。
        if observation['points'] and observation['primitives']:
            observation['signature'] = all_geometry_signature06(hou_api, geometry)
            observation['equals_direct'] = observation['signature'] == record['direct_signature']
        else:
            observation['signature'] = None; observation['equals_direct'] = False
        save(label + '_COMPLETE'); health()
        return observation
    try:
        save('BEFORE_GUARDS'); health()
        assert plan['scope'] == 'FILE_NULL_K360_ONLY' and plan['sample'] == 360
        assert file_sha(raw_path) == plan['input']['sha256'] and raw_path.stat().st_size == plan['input']['bytes']
        assert '$' not in str(raw_path) and raw_path.is_file()
        own = hou_api.node(owner_path); state = getattr(hou_api.session, key)
        assert any(n == own and sid == n.sessionId() for n, sid in state['owned_nodes'])
        assert not own.children() and not own.isDisplayFlagSet()
        assert hou_api.updateModeSetting() == hou_api.updateMode.Manual and hou_api.fps() == plan['fps']
        hou_api.setFrame(plan['global_frame']); assert hou_api.frame() == plan['global_frame']
        record['frame'] = hou_api.frame(); record['fps'] = hou_api.fps(); record['update_mode'] = str(hou_api.updateModeSetting())
        save('DIRECT_LOAD')
        direct = hou_api.Geometry(); direct.loadFromFile(str(raw_path))
        record['direct_counts'] = {'points': len(direct.points()), 'primitives': len(direct.prims()), 'attributes': attribute_inventory06(direct),
                                   'node_cook_state': None, 'meaning_ja': 'ノードではない直接読込のためcookCount/errors/needsToCookは適用外。'}
        record['direct_signature'] = all_geometry_signature06(hou_api, direct)
        assert len(direct.points()) == plan['expected_points'] and len(direct.prims()) == plan['expected_primitives']
        save('DIRECT_SIGNATURE_SAVED'); health()
        geo = own.createNode('geo', node_name='file_only_diagnostic', run_init_scripts=False); geo.setDisplayFlag(False)
        reader = geo.createNode('file', node_name='literal_k360', run_init_scripts=False)
        out = geo.createNode('null', node_name='passthrough_only', run_init_scripts=False); out.setInput(0, reader)
        record['created_nodes'] = {n.name(): n.type().name() for n in (geo, reader, out)}
        record['file_input_slots'] = [n.path() if n else None for n in reader.inputs()]
        assert disconnected_file_inputs(reader.inputs(), len(reader.inputConnections())), 'Fileへの入力禁止'
        # Buttonは実行/評価しない。filemode/load等の実schemaを全scalar parmと共に保存する。
        record['file_parameters_before'] = {p.name(): parm_record06(p) for p in reader.parms()
                                            if p.parmTemplate().type() != hou_api.parmTemplateType.Button}
        save('FILE_DEFAULT_PARAMETERS')
        reader.parm('file').set(raw_path.as_posix())
        record['file_parameters_after'] = {p.name(): parm_record06(p) for p in reader.parms()
                                           if p.parmTemplate().type() != hou_api.parmTemplateType.Button}
        path_parm = reader.parm('file')
        record['file_path'] = {'raw_value': path_parm.rawValue(), 'unexpanded': path_parm.unexpandedString(),
                               'evaluated': path_parm.evalAsString(), 'expected': raw_path.as_posix()}
        assert record['file_path']['raw_value'] == raw_path.as_posix() and Path(record['file_path']['evaluated']).resolve() == raw_path.resolve()
        save('FILE_LITERAL_BOUND')
        def inspect_pair(mode, defer=False):
            # geometry()自体がcookし得るため、その前後counterを分ける。
            for node, name in ((reader, 'FILE'), (out, 'NULL')):
                label = mode + '_' + name
                sample_geometry(node, label + '_BEFORE_EXPLICIT_COOK', defer)
                record['node_observations'][label + '_EXPLICIT_COOK'] = {'before': node_state06(node, hou_api)}
                save(label + '_EXPLICIT_COOK_REQUEST')
                node.cook(force=True)
                record['node_observations'][label + '_EXPLICIT_COOK']['after'] = node_state06(node, hou_api)
                sample_geometry(node, label + '_AFTER_EXPLICIT_COOK', defer)
        inspect_pair('MANUAL')
        record['main_thread'] = {'current_name': threading.current_thread().name,
                                 'is_main': threading.current_thread() is threading.main_thread()}
        assert record['main_thread']['is_main'], 'main thread以外では更新modeを切り替えない'
        save('BEFORE_AUTOUPDATE_WINDOW')
        mode_before = hou_api.updateModeSetting()
        assert mode_before == hou_api.updateMode.Manual
        auto_start = time.monotonic()
        try:
            # 同一main-thread呼出し内。待機/yield/UI描画/別RPCは入れない。
            hou_api.setUpdateMode(hou_api.updateMode.AutoUpdate)
            auto_active = True
            record['temporary_update_mode'] = str(hou_api.updateModeSetting())
            assert hou_api.updateModeSetting() == hou_api.updateMode.AutoUpdate
            inspect_pair('AUTOUPDATE', defer=True)
        except Exception:
            record['auto_failure_phase'] = record['phase']
            raise
        finally:
            hou_api.setUpdateMode(mode_before)
            auto_active = False
            record['manual_restored_in_same_rpc'] = hou_api.updateModeSetting() == mode_before
            record['auto_window_seconds'] = time.monotonic() - auto_start
            save('AFTER_AUTOUPDATE_FINALLY')
        assert record['manual_restored_in_same_rpc']
        # Auto内では凍結geometryの取得だけ。重い全属性hash/JSON出力はManualへ戻してから。
        for label, geometry in deferred_geometry:
            observation = record['node_observations'][label]
            save(label + '_SIGNATURE_AFTER_MANUAL')
            observation['signature_update_mode'] = str(hou_api.updateModeSetting())
            if observation['points'] and observation['primitives']:
                observation['signature'] = all_geometry_signature06(hou_api, geometry)
                observation['equals_direct'] = observation['signature'] == record['direct_signature']
            else:
                observation['signature'] = None; observation['equals_direct'] = False
            health(); save(label + '_COMPLETE')
        record['external_DOP_state_monitored'] = False
        record['direct_external_DOP_calls'] = False
        finals = [record['node_observations']['AUTOUPDATE_' + x + '_AFTER_EXPLICIT_COOK'] for x in ('FILE', 'NULL')]
        record['passed'] = all(r['equals_direct'] and not r['after_geometry_call']['errors'] and not r['after_geometry_call']['warnings'] for r in finals)
        record['hold_reason_ja'] = None if record['passed'] else '事前登録したManual/AutoUpdateのFile/Null読戻しが未成立。追加設定変更/再試行はしない。'
        assert file_sha(raw_path) == plan['input']['sha256']
        health(); save('COMPLETE')
    except Exception as exc:
        record['passed'] = False; record['failure_type'] = type(exc).__name__; record['failure_message_local'] = str(exc)
        record['failure_phase'] = record.get('auto_failure_phase', record['phase'])
        record['exception_locations'] = [{'source_identifier': Path(f.filename).name, 'function': f.name, 'line': f.lineno}
                                         for f in traceback.extract_tb(exc.__traceback__)]
    finally:
        record['seconds'] = time.monotonic() - started
        record['source_cache_sha_after'] = file_sha(raw_path)
        save('FINAL_SAVED')
    return record
