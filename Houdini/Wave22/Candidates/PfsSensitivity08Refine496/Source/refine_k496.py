"""所有SOPによるk496新.25面の感度読戻し。関数定義だけではHOMを実行しない。"""
import time
import threading
import traceback


def refine_k496(hou_api, key, owner_path, plan, paths):
    started = time.monotonic()
    record = {'sample': 496, 'scope': plan['scope'], 'passed': False, 'phase': 'BEGIN', 'history': [],
              'resources': [], 'new_solver': False, 'refinement_started': False, 'physical_pass': False, 'detector_executed': False,
              'input_gate_passed': False, 'pfs_created': False, 'auto_windows': [],
              'external_DOP_state_monitored': False, 'direct_external_DOP_calls': False}
    limits = plan['budgets']; frozen_mesh = None; initial_private = None
    source = Path(paths['raw']); old_path = Path(paths['original_mesh']); destination = Path(paths['mesh_output'])
    def save(label):
        record['phase'] = label
        record['history'].append({'phase': label, 'seconds': time.monotonic() - started})
        if hou_api.updateModeSetting() == hou_api.updateMode.Manual:
            Path(paths['progress']).write_bytes((json.dumps(serializable_observation(record), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
    def health():
        nonlocal initial_private
        assert hou_api.updateModeSetting() == hou_api.updateMode.Manual
        value = memory06(source.anchor); record['resources'].append(value)
        if initial_private is None:
            initial_disk08(value['free_G_bytes'], plan)
            initial_private = value['private_bytes']
        assert value['available_bytes'] >= limits['minimum_available_RAM_bytes'], '可用RAM保護'
        assert value['private_bytes'] - initial_private < limits['maximum_private_increase_bytes'], 'private増分保護'
        assert value['free_G_bytes'] >= limits['minimum_free_G_bytes'], 'G空き保護'
        assert time.monotonic() - started < limits['per_rpc_cooperative_seconds'], 'RPC協調時間保護'
    def save_generated():
        assert hou_api.updateModeSetting() == hou_api.updateMode.Manual
        if frozen_mesh is not None and 'mesh_output' not in record:
            assert not destination.exists(), '新meshの上書き禁止'
            frozen_mesh.saveToFile(str(destination))
            record['mesh_output'] = {'filename': destination.name, 'bytes': destination.stat().st_size, 'sha256': file_sha(destination)}
            assert destination.stat().st_size <= limits['maximum_mesh_bytes'], 'mesh容量保護'
    try:
        target08(plan)
        save('INITIAL_GUARDS'); health()
        assert plan['scope'] == 'ONE_K496_QUARTER_MESH_SENSITIVITY_ONLY' and plan['sample'] == 496
        assert plan['mesh_parameters']['voxelsize'] == .25 and plan['refinement_allowed'] is True
        assert plan['other_samples_allowed'] is False and hou_api.fps() == 24
        assert hou_api.updateModeSetting() == hou_api.updateMode.Manual
        assert threading.current_thread() is threading.main_thread()
        assert source.stat().st_size == plan['record']['pilot']['bytes'] and file_sha(source) == plan['record']['pilot']['sha256']
        assert old_path.stat().st_size == plan['record']['mesh']['bytes'] and file_sha(old_path) == plan['record']['mesh']['sha256']
        own = hou_api.node(owner_path); state = getattr(hou_api.session, key)
        assert own is not None and any(n == own and sid == n.sessionId() for n, sid in state['owned_nodes'])
        assert not own.children() and not own.isDisplayFlagSet()
        hou_api.setFrame((1 + .4 * 496))
        assert abs(hou_api.frame() - plan['global_frame']) < plan['frame_contract']['assert_tolerance_frames']
        record['actual_frame'] = hou_api.frame(); record['fps'] = hou_api.fps()
        record['main_thread'] = threading.current_thread().name
        baseline_path = Path(paths['baseline_replay'])
        assert file_sha(baseline_path) == plan['baseline_successes']['496']['raw']['sha256']
        baseline = json.loads(baseline_path.read_bytes())
        assert baseline['passed'] and baseline['input_gate_passed'] and baseline['native_exact'] and baseline['mesh_parity']['passed']
        save('DIRECT_CACHE_READ')
        direct = hou_api.Geometry(); direct.loadFromFile(str(source))
        original_mesh = hou_api.Geometry(); original_mesh.loadFromFile(str(old_path))
        record['original_mesh_counts'] = {'points': len(original_mesh.points()), 'faces': len(original_mesh.prims())}
        assert record['original_mesh_counts'] == {'points': plan['record']['mesh_points'], 'faces': plan['record']['mesh_faces']}
        record['direct_input_signature'] = all_geometry_signature06(hou_api, direct)
        record['baseline_input_canonical_equal'] = compare_signatures(baseline['direct_input_signature'], record['direct_input_signature'])
        assert record['baseline_input_canonical_equal'], '成功旧.5と同じ入力でない'
        assert len(direct.points()) == 53853 and len(direct.prims()) == 5
        assert record['direct_input_signature']['particle_count'] == 53848
        save('CREATE_FILE_NULL_ONLY')
        geo = own.createNode('geo', node_name='meshing_only', run_init_scripts=False); geo.setDisplayFlag(False)
        reader = geo.createNode('file', node_name='literal_cache', run_init_scripts=False)
        particles = geo.createNode('null', node_name='SOLVER_FIELDS_PARTICLES', run_init_scripts=False); particles.setInput(0, reader)
        assert disconnected_file_inputs(reader.inputs(), len(reader.inputConnections())) and '$' not in str(source)
        reader.parm('file').set(source.as_posix())
        record['file_parameters'] = {p.name(): parm_record06(p) for p in reader.parms() if p.parmTemplate().type() != hou_api.parmTemplateType.Button}
        assert reader.parm('file').rawValue() == source.as_posix() and Path(reader.parm('file').evalAsString()).resolve() == source.resolve()
        nodes = {'FILE': reader, 'NULL': particles}
        record['node_observations'] = {}
        def capture_input():
            result = {}
            for label, node in nodes.items():
                save('AUTO1_' + label + '_COOK')
                before = node_state06(node, hou_api)
                node.cook(force=True)
                result[label] = node.geometry().freeze()
                after = node_state06(node, hou_api)
                record['node_observations']['INPUT_' + label] = {'before': before, 'after': after}
            return result
        def compare_input(captured):
            save('MANUAL_INPUT_FULL_SIGNATURES'); health()
            comparisons = {}
            for label, geometry in captured.items():
                signature = all_geometry_signature06(hou_api, geometry)
                observation = record['node_observations']['INPUT_' + label]
                good = compare_signatures(record['direct_input_signature'], signature)
                good = good and len(geometry.points()) == 53853 and len(geometry.prims()) == 5
                good = good and not observation['after']['errors'] and not observation['after']['warnings']
                good = good and observation['after']['cook_count'] > observation['before']['cook_count']
                comparisons[label] = {'signature': signature, 'canonical_equal': good,
                                      'raw_leaf_differences': leaf_differences(record['direct_input_signature'], signature)}
            record['input_comparisons'] = comparisons
            save('MANUAL_INPUT_GATE_SAVED'); health()
            return all(row['canonical_equal'] for row in comparisons.values())
        def prepare_mesh():
            assert record['input_gate_passed'] is True
            save('CREATE_PFS_AFTER_INPUT_PASS'); health()
            pfs = geo.createNode('particlefluidsurface::3.0', node_name='display_meshing_only', run_init_scripts=False, exact_type_name=True)
            record['pfs_created'] = True
            assert pfs.type().name() == 'particlefluidsurface::3.0'
            pfs.setInput(0, particles)
            record['explicit_settings'] = {name: set_verified06(hou_api, pfs.parm(name), value) for name, value in plan['mesh_parameters'].items()}
            convert = geo.createNode('convert', node_name='display_polygons', run_init_scripts=False); convert.setInput(0, pfs)
            record['convert_setting'] = set_verified06(hou_api, convert.parm('totype'), 'poly')
            out = geo.createNode('null', node_name='DISPLAY_SURFACE', run_init_scripts=False); out.setInput(0, convert)
            out.setDisplayFlag(True); out.setRenderFlag(True)
            nodes.update(PFS=pfs, CONVERT=convert, OUT=out)
            record['flags'] = {'owner_display': own.isDisplayFlagSet(), 'geo_display': geo.isDisplayFlagSet(),
                               'out_display': out.isDisplayFlagSet(), 'out_render': out.isRenderFlagSet()}
            assert record['flags'] == plan['node_flags']
            record['graph'] = {label: {'type': n.type().name(), 'inputs': [x.name() if x is not None else None for x in n.inputs()]} for label, n in nodes.items()}
            record['PFS_definition'] = definition06(pfs)
            record['PFS_parameters'] = parameters06(pfs, owner_path)
            record['convert_parameters'] = parameters06(convert, owner_path)
            assert len(baseline['PFS_parameters']) == len(record['PFS_parameters']) == plan['expected_evaluated_PFS_parameter_count'], 'PFS全評価166項の件数差'
            record['parameter_pair'] = same_parameters_except_voxel(baseline['PFS_parameters'], record['PFS_parameters'])
            record['definition_equal'] = exact(baseline['PFS_definition'], record['PFS_definition'])
            record['convert_equal'] = exact(baseline['convert_parameters'], record['convert_parameters'])
            assert record['parameter_pair']['passed'] and record['definition_equal'] and record['convert_equal'], 'voxelsize以外の定義/設定差'
            save('MESH_CHAIN_PARAMETERS_SAVED'); health()
        def capture_mesh():
            nonlocal frozen_mesh
            # 04と同じくOutだけを強制cookし、依存PFS/Convertの実計数を読む。
            for label in ('PFS', 'CONVERT', 'OUT'):
                record['node_observations']['MESH_' + label] = {'before': node_state06(nodes[label], hou_api)}
            save('AUTO2_OUT_COOK')
            record['refinement_started'] = True
            nodes['OUT'].cook(force=True)
            frozen_mesh = nodes['OUT'].geometry().freeze()
            for label in ('PFS', 'CONVERT', 'OUT'):
                record['node_observations']['MESH_' + label]['after'] = node_state06(nodes[label], hou_api)
            return frozen_mesh
        def compare_mesh(captured):
            save('MANUAL_MESH_SAVE_BEFORE_QUERIES')
            save_generated()
            health()
            observed, original = mesh_data06(captured), mesh_data06(original_mesh)
            record['replay_mesh_counts'] = {'points': len(captured.points()), 'faces': len(captured.prims())}
            record['mesh_fingerprint'] = mesh_hash06(observed); record['original_mesh_fingerprint'] = mesh_hash06(original)
            record['old_new_mesh_comparison_diagnostic_only'] = compare_mesh_data(original, observed)
            record['new_mesh_nonempty_finite'] = bool(observed['P']) and bool(observed['indices']) and all(math.isfinite(v) for v in observed['P'])
            record['original_mesh_fingerprint_equal_to_success'] = exact(record['original_mesh_fingerprint'], baseline['original_mesh_fingerprint'])
            record['node_messages'] = {name: {'errors': list(n.errors()), 'warnings': list(n.warnings())} for name, n in nodes.items()}
            reread = hou_api.Geometry(); reread.loadFromFile(str(destination))
            record['saved_mesh_reread_parity'] = compare_mesh_data(observed, mesh_data06(reread))
            # nativeのNaN/Infは明示例外で保持し、既に保存したBGEOを失わない。
            record['native_original'] = []; record['native_replay'] = []
            for x in plan['gauge_x_m']:
                save('MANUAL_NATIVE_GAUGE')
                record['native_original'].append(native_first06(hou_api, original_mesh, x))
                record['native_replay'].append(native_first06(hou_api, captured, x))
            record['original_native_equal_to_success'] = all(h is not None for h in record['native_original']) and exact(record['native_original'], baseline['native_original'])
            record['new_native_present'] = all(h is not None for h in record['native_replay'])
            record['center_raw_differences'] = center_differences06(record['native_original'], record['native_replay'], plan['record']['gauges'])
            record['native_exact_old_new_diagnostic_only'] = record['native_replay'] == record['native_original']
            record['original_record_height_parity'] = all(h is not None and abs(h['position_m'][1] - g['mesh_eta_m']) <= plan['parity']['original_record_height_tolerance_m']
                                                         for h, g in zip(record['native_original'], plan['record']['gauges']))
            health(); save('STRICT_MESH_PARITY_SAVED')
            return (record['new_mesh_nonempty_finite'] and record['saved_mesh_reread_parity']['passed'] and record['original_native_equal_to_success']
                    and record['new_native_present'] and record['original_mesh_fingerprint_equal_to_success']
                    and record['original_record_height_parity'] and not any(v['errors'] or v['warnings'] for v in record['node_messages'].values()))
        record['passed'] = two_windows06(hou_api, capture_input, compare_input, prepare_mesh, capture_mesh, compare_mesh,
                                        record, limits['maximum_cook_window_seconds'])
        if not record['passed']: record['hold_reason_ja'] = '新.25面の有限/保存/旧native確認が不成立。後続断面読戻しを保留し、再設定・閾値変更しない。'
        health()
    except Exception as exc:
        record['passed'] = False; record['failure_type'] = type(exc).__name__; record['failure_message_local'] = str(exc)
        record['failure_phase'] = record['phase']
        record['exception_locations'] = [{'source_identifier': Path(f.filename).name, 'function': f.name, 'line': f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
    finally:
        # cook時間超過でも得られた面を保持する。未知/完了不明RPCの外側から追加要求しない。
        try: save_generated()
        except Exception as exc:
            record['passed'] = False; record['mesh_preservation_failure_type'] = type(exc).__name__
        record['manual_at_return'] = hou_api.updateModeSetting() == hou_api.updateMode.Manual
        record['source_cache_sha_after'] = file_sha(source); record['original_mesh_sha_after'] = file_sha(old_path)
        if (not record['manual_at_return'] or record['source_cache_sha_after'] != plan['record']['pilot']['sha256']
                or record['original_mesh_sha_after'] != plan['record']['mesh']['sha256']): record['passed'] = False
        record['seconds'] = time.monotonic() - started
        save('FINAL_SAVED')
    return record
