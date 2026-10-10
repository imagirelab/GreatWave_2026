# -*- coding: utf-8 -*-
"""FLIP42：動いている hython（計算）に、Windows の実行速度の抑え（電力の抑え、EcoQoS）を使わないように頼み、優先度を「通常より下」にする。
2026-10-10 04:10 に足した。ほかのプログラム（ゲーム）が前にある間、hython が 0.6 コア分しか使えず 1 コマが 100 秒を越えたため。
抑えを外すと 8.7 コア分を使った【測った】。優先度を下げるので、前にあるプログラムが先に CPU を使う。計算の中身は変えない。
py -3.10 g_unthrottle.py   （新しい hython が出るたびに 1 回だけ設定する。止めるまで回り続ける）
記録：Unity/Build/FLIP42/runs/unthrottle_log.txt"""
import ctypes, subprocess, time
from ctypes import wintypes

LOG = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/unthrottle_log.txt"
k = ctypes.WinDLL("kernel32", use_last_error=True)


class PPTS(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]


k.OpenProcess.restype = wintypes.HANDLE
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k.CloseHandle.argtypes = [wintypes.HANDLE]


def pids():
    out = subprocess.run(["tasklist", "/fi", "imagename eq hython.exe", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         encoding="mbcs", errors="ignore").stdout
    r = []
    for line in out.splitlines():
        p = [q.strip('"') for q in line.split('","')]
        if len(p) > 1 and p[0].lower().startswith("hython"):
            try:
                r.append(int(p[1]))
            except ValueError:
                pass
    return r


done = set()
while True:
    for pid in pids():
        if pid in done:
            continue
        h = k.OpenProcess(0x0200 | 0x0400, False, pid)
        if not h:
            continue
        s = PPTS(1, 0x1, 0x0)
        r1 = k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s))
        r2 = k.SetPriorityClass(h, 0x4000)
        k.CloseHandle(h)
        done.add(pid)
        open(LOG, "a", encoding="utf8").write("%s pid %d power_throttling_off %s below_normal %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid, bool(r1), bool(r2)))
    time.sleep(15)
