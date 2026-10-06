# -*- coding: utf-8 -*-
"""Windows の電力の絞り（EcoQoS：裏の処理を効率の核へ寄せて遅くする）を、計算の処理だけ外す（py -3.10 または hython の中から）。
使い方: py -3.10 p3_nothrottle.py <pid> [<pid> ...]   または  import p3_nothrottle; p3_nothrottle.off()（自分の処理）
P1 の記録：ゲームが動いている間、計算が 4〜7 倍遅くなった。P3 の初め（23:00）も R18 の計算が 1 コマ 3.2 秒 → 15.6 秒になった。
機械の設定は変えない（その処理の性質だけ）。
"""
import ctypes, sys
from ctypes import wintypes

PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ProcessPowerThrottling = 4
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4


class PPTS(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]


def _set(h):
    k = ctypes.windll.kernel32
    s = PPTS(1, PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION, 0)
    f = k.SetProcessInformation
    f.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    ok = f(h, ProcessPowerThrottling, ctypes.byref(s), ctypes.sizeof(s))
    return bool(ok), k.GetLastError()


def off(pid=None):
    k = ctypes.windll.kernel32
    if pid is None:
        k.GetCurrentProcess.restype = wintypes.HANDLE
        return _set(k.GetCurrentProcess())
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False, k.GetLastError()
    r = _set(h)
    k.CloseHandle(h)
    return r


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, off(int(p)))
