"""手順17の新規生成処理を実MCPで呼び出すHoudini側コード。

呼出し側は各コードへKEYとOBJ_PATHを渡す。SNAPSHOTは現在のUI状態だけを読み、
シーンのノード内容は読まない。hou.sessionへメモリー内の属性を作る。
所有する最上位コンテナを作った直後に、(node, node.sessionId())を
snapshot['owned_nodes']へ追加する。finallyからCLEANUPを実行する。
CAPTUREにはCAPTURE_PATTERNも必要（小数フレームには$FFを使う）。
HIPの保存・読込・クリアや、グローバルFPSの変更は行わない。
"""

SNAPSHOT = r'''
assert hou.isUIAvailable(), 'A live Houdini UI is required'
assert not hasattr(hou.session, KEY), 'Snapshot key collision'
assert hou.node(OBJ_PATH) is None, 'Owned container path already exists'
viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
assert viewer is not None, 'No current Scene Viewer'
assert not hou.selectedConnections(), 'Connection selection needs a narrower UI operation'
viewport = viewer.curViewport()
assert not viewport.isViewingThroughExtraCamera(), 'Extra state camera cannot be safely restored'
snapshot = {
    'viewer': viewer, 'viewport': viewport,
    'camera': viewport.camera(), 'camera_settings': viewport.defaultCamera().stash(),
    'camera_locked': viewport.isCameraLockedToView(),
    'camera_export': viewport.isViewExportedToCameraContinuously(),
    'viewport_type': viewport.type(), 'view_transform': viewport.viewTransform().asTuple(),
    'visible_objects': viewport.settings().visibleObjects(),
    'selection': tuple(hou.selectedItems()), 'selection_mode': viewer.selectionMode(),
    'geometry_selection': viewer.currentGeometrySelection(),
    'viewer_state': viewer.currentState(), 'global_pwd': hou.pwd(),
    'frame': hou.frame(), 'fps': hou.fps(), 'update_mode': hou.updateModeSetting(),
    'dirty': hou.hipFile.hasUnsavedChanges(),
    'undo_labels': tuple(hou.undos.undoLabels()), 'redo_labels': tuple(hou.undos.redoLabels()),
    'panes': [], 'active_tabs': [p for p in hou.ui.paneTabs() if p.isCurrentTab()],
    'owned_nodes': [],
}
for pane in hou.ui.paneTabs():
    if isinstance(pane, hou.PathBasedPaneTab):
        item = {'pane': pane, 'pwd': pane.pwd(), 'current': pane.currentNode(), 'link_group': pane.linkGroup()}
        if pane.type() == hou.paneTabType.NetworkEditor:
            item['bounds'] = pane.visibleBounds()
        snapshot['panes'].append(item)
setattr(hou.session, KEY, snapshot)
result = {'snapshot_ready': True, 'pane_name': viewer.name(), 'selected_item_count': len(snapshot['selection']), 'frame': snapshot['frame'], 'fps': snapshot['fps'], 'update_mode': str(snapshot['update_mode']), 'dirty_before': snapshot['dirty'], 'undo_count_before': len(snapshot['undo_labels']), 'redo_count_before': len(snapshot['redo_labels'])}
'''

SHOW_OWNED = r'''
s = getattr(hou.session, KEY)
owned = hou.node(OBJ_PATH)
assert owned is not None and any(n == owned and n.sessionId() == sid for n, sid in s['owned_nodes']), 'Ownership guard failed'
assert hou.fps() == s['fps'], 'Global FPS changed'
s['viewer'].setPin(True)
s['viewport'].lockCameraToView(False)
s['viewport'].exportViewToCameraContinuously(False)
s['viewport'].useDefaultCamera()
s['viewport'].settings().setVisibleObjects(OBJ_PATH)
s['viewer'].setPwd(owned.parent())
s['viewer'].setSelectionMode(hou.selectionMode.Object)
hou.clearAllSelected()
owned.setSelected(True)
s['viewer'].setIsCurrentTab()
s['viewport'].frameSelected()
s['viewport'].draw()
result = {'showing_only_owned_container': s['viewport'].settings().visibleObjects() == OBJ_PATH, 'pane_name': s['viewer'].name()}
'''

CAPTURE = r'''
s = getattr(hou.session, KEY)
assert hou.fps() == s['fps'], 'Global FPS changed'
assert s['viewport'].settings().visibleObjects() == OBJ_PATH, 'Viewport not isolated to owned container'
assert '$F4' in CAPTURE_PATTERN, '整数フレームを固有名で保存する'
step = 1.0
start = 1.0
end = 1.0 + (2.0 * s['fps'] - 1) * step
settings = s['viewer'].flipbookSettings().stash()
settings.outputToMPlay(False)
settings.output(CAPTURE_PATTERN)
settings.frameRange((start, end))
settings.frameIncrement(step)
settings.useResolution(True)
settings.resolution((1280, 720))
settings.outputZoom(100)
settings.useSheetSize(False)
settings.appendFramesToCurrent(False)
settings.cropOutMaskOverlay(False)
s['viewport'].draw()
s['viewer'].flipbook(s['viewport'], settings)
result = {'capture_requested': True, 'output_pattern': CAPTURE_PATTERN, 'expected_frame_count': int(2*s['fps']), 'playback_fps': s['fps'], 'source_fps_unchanged': hou.fps() == s['fps'], 'source_start_frame': start, 'source_end_frame': end, 'source_frame_step': step, 'start_time_seconds': 0.0, 'last_sample_time_seconds': 2.0-1.0/s['fps'], 'clip_duration_seconds': 2.0, 'output_to_mplay': False, 'note_ja': '実ファイル数を別途確認し、既存FPSと同じ速度で符号化する。キャッシュには終端も保存する。'}
'''

CLEANUP = r'''
if not hasattr(hou.session, KEY):
    result = {'snapshot_present': False, 'owned_primary_path_absent': hou.node(OBJ_PATH) is None}
else:
    s = getattr(hou.session, KEY)
    errors = []
    owned_paths = []
    def attempt(label, action):
        try:
            action()
        except Exception as exc:
            errors.append(label + ': ' + type(exc).__name__ + ': ' + str(exc))
    for node, session_id in reversed(s['owned_nodes']):
        try:
            path = node.path()
            assert node.sessionId() == session_id, 'Owned session ID mismatch; refused deletion'
        except hou.ObjectWasDeleted:
            continue
        except Exception as exc:
            errors.append('ownership guard: ' + str(exc))
            continue
        owned_paths.append(path)
        attempt('delete owned container', node.destroy)
    attempt('camera unlock for restore', lambda: s['viewport'].lockCameraToView(False))
    attempt('stop camera export for restore', lambda: s['viewport'].exportViewToCameraContinuously(False))
    attempt('detach camera for restore', s['viewport'].useDefaultCamera)
    for item in s['panes']:
        attempt('pin pane for restore', lambda item=item: item['pane'].setPin(True))
        if item['current'] is not None:
            attempt('restore current node', lambda item=item: item['pane'].setCurrentNode(item['current'], False))
        # setCurrentNodeでpwdが変わるため、コンテキストの復元は後に行う。
        attempt('restore pane context', lambda item=item: item['pane'].setPwd(item['pwd']))
        if 'bounds' in item:
            attempt('restore network view', lambda item=item: item['pane'].setVisibleBounds(item['bounds'], 0.0))
    attempt('restore global context', lambda: hou.setPwd(s['global_pwd']))
    attempt('clear owned selection', hou.clearAllSelected)
    for item in s['selection']:
        attempt('restore selection', lambda item=item: item.setSelected(True))
    attempt('restore selection mode', lambda: s['viewer'].setSelectionMode(s['selection_mode']))
    if s['viewer'].currentState() != s['viewer_state']:
        attempt('restore viewer state', lambda: s['viewer'].setCurrentState(s['viewer_state'], generate=hou.stateGenerateMode.Enter, request_new_on_generate=False))
    if s['geometry_selection'] is not None:
        gs = s['geometry_selection']
        attempt('restore geometry selection', lambda: s['viewer'].setCurrentGeometrySelection(gs.geometryType(), gs.nodes(), gs.selections()))
    attempt('restore viewport type', lambda: s['viewport'].changeType(s['viewport_type']))
    attempt('restore viewport mask', lambda: s['viewport'].settings().setVisibleObjects(s['visible_objects']))
    attempt('restore camera settings', lambda: s['viewport'].setDefaultCamera(s['camera_settings']))
    if s['camera'] is not None:
        attempt('restore camera binding', lambda: s['viewport'].setCamera(s['camera']))
    attempt('restore camera export', lambda: s['viewport'].exportViewToCameraContinuously(s['camera_export']))
    attempt('restore camera lock', lambda: s['viewport'].lockCameraToView(s['camera_locked']))
    for item in s['panes']:
        attempt('restore pane link', lambda item=item: item['pane'].setLinkGroup(item['link_group']))
    for pane in s['active_tabs']:
        attempt('restore active tab', pane.setIsCurrentTab)
    if hou.frame() != s['frame']:
        attempt('restore frame', lambda: hou.setFrame(s['frame']))
    if hou.updateModeSetting() != s['update_mode']:
        attempt('restore update mode', lambda: hou.setUpdateMode(s['update_mode']))
    attempt('redraw restored viewport', s['viewport'].draw)
    current_undo = tuple(hou.undos.undoLabels())
    old_undo = s['undo_labels']
    transforms = s['viewport'].viewTransform().asTuple()
    checks = {
        'all_owned_paths_absent': all(hou.node(p) is None for p in owned_paths) and hou.node(OBJ_PATH) is None,
        'selected_items_restored': tuple(hou.selectedItems()) == s['selection'],
        'global_context_restored': hou.pwd() == s['global_pwd'],
        'pane_contexts_restored': all(i['pane'].pwd() == i['pwd'] for i in s['panes']),
        'pane_current_nodes_restored': all(i['pane'].currentNode() == i['current'] for i in s['panes']),
        'pane_links_restored': all(i['pane'].linkGroup() == i['link_group'] for i in s['panes']),
        'active_tabs_restored': all(p.isCurrentTab() for p in s['active_tabs']),
        'frame_restored': hou.frame() == s['frame'],
        'fps_unchanged': hou.fps() == s['fps'],
        'update_mode_restored': hou.updateModeSetting() == s['update_mode'],
        'viewer_state_restored': s['viewer'].currentState() == s['viewer_state'],
        'selection_mode_restored': s['viewer'].selectionMode() == s['selection_mode'],
        'viewport_type_restored': s['viewport'].type() == s['viewport_type'],
        'viewport_visible_mask_restored': s['viewport'].settings().visibleObjects() == s['visible_objects'],
        'camera_binding_restored': s['viewport'].camera() == s['camera'],
        'camera_lock_restored': s['viewport'].isCameraLockedToView() == s['camera_locked'],
        'camera_export_restored': s['viewport'].isViewExportedToCameraContinuously() == s['camera_export'],
        'view_transform_restored': max(abs(a-b) for a,b in zip(transforms, s['view_transform'])) < 1e-5,
    }
    result = {'checks': checks, 'restore_errors': errors, 'all_ui_and_owned_node_checks_passed': all(checks.values()) and not errors, 'dirty_before': s['dirty'], 'dirty_after': hou.hipFile.hasUnsavedChanges(), 'prior_undo_labels_retained': not old_undo or current_undo[-len(old_undo):] == old_undo, 'undo_count_before': len(old_undo), 'undo_count_after': len(current_undo), 'redo_stack_unchanged': tuple(hou.undos.redoLabels()) == s['redo_labels'], 'undo_history_cleared': False, 'hip_saved_or_loaded': False}
    if result['all_ui_and_owned_node_checks_passed']:
        delattr(hou.session, KEY)
        result['temporary_session_snapshot_removed'] = True
    else:
        result['temporary_session_snapshot_removed'] = False
'''
