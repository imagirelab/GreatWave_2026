"""入力判定前には面化ノードを作らない、二つの更新窓。"""
import threading
import time


class InputParityHold(Exception):
    """入力の署名不一致により面化前で保留する。"""


def auto_window06(hou_api, label, capture, record, limit):
    assert threading.current_thread() is threading.main_thread(), 'main-thread以外の更新切替禁止'
    assert hou_api.updateModeSetting() == hou_api.updateMode.Manual, '窓の前はManual必須'
    window = {'label': label, 'started': False, 'manual_restored': False}
    record.setdefault('auto_windows', []).append(window)
    start = time.monotonic()
    try:
        hou_api.setUpdateMode(hou_api.updateMode.AutoUpdate)
        window['started'] = True
        assert hou_api.updateModeSetting() == hou_api.updateMode.AutoUpdate
        result = capture()
    except Exception as exc:
        window['failure_type'] = type(exc).__name__
        raise
    finally:
        hou_api.setUpdateMode(hou_api.updateMode.Manual)
        window['manual_restored'] = hou_api.updateModeSetting() == hou_api.updateMode.Manual
        window['seconds'] = time.monotonic() - start
    assert window['manual_restored'], '同RPC内Manual復帰失敗'
    if window['seconds'] >= limit:
        raise TimeoutError('Auto窓の協調時間上限')
    return result


def two_windows06(hou_api, capture_input, compare_input, prepare_mesh, capture_mesh, compare_mesh, record, limit):
    """比較は必ずManual。第1判定の真だけが第2窓を許可する。"""
    input_data = auto_window06(hou_api, 'INPUT_FILE_NULL', capture_input, record, limit)
    assert hou_api.updateModeSetting() == hou_api.updateMode.Manual
    record['input_gate_passed'] = compare_input(input_data) is True
    if not record['input_gate_passed']:
        raise InputParityHold('入力署名不一致。PFS未作成、第二Auto窓禁止')
    prepare_mesh()
    mesh_data = auto_window06(hou_api, 'OLD_HALF_PFS', capture_mesh, record, limit)
    assert hou_api.updateModeSetting() == hou_api.updateMode.Manual
    return compare_mesh(mesh_data) is True
