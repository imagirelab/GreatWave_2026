# -*- coding: utf-8 -*-
"""設計28修正01 試行F：自分のプロセスの電力の抑制（Windows 11 の EcoQoS・効率モード）を切る小さな道具と、それを掛けてから台本を走らせる起動器。

背景（試行F で測った）：この作業環境で裏で走らせたプロセスは EcoQoS（実行速度の抑制）が掛かり、効率のコアだけで走る。同じ Python の
空回しで、抑制ありは 約 5.6 M 回/s、抑制を切ると 約 14.1 M 回/s（2.5 倍）。多数のプロセスを並べると効率のコアを取り合い、1 つあたり
数 % しか進まない。試行E の生成が 2,585 s（43 分）かかった理由の一部と考えられる（M5）。SetProcessInformation(ProcessPowerThrottling)
で自分のプロセスの抑制だけを切る（ほかのプロセスとシステムの設定は変えない）。
使い方：
  import ds28r01f_proc; ds28r01f_proc.opt_out()                 # 自分のプロセス
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_proc.py <台本.py> <引数...>   # 抑制を切ってから台本を __main__ として走らせる
"""
import os
import runpy
import sys


def opt_out():
    """自分のプロセスの実行速度の抑制を切る。戻り (成功, エラー番号)。Windows 以外では何もしない。"""
    if os.name != "nt":
        return False, 0
    import ctypes
    import ctypes.wintypes as wt

    class PPT(ctypes.Structure):
        _fields_ = [("Version", wt.ULONG), ("ControlMask", wt.ULONG), ("StateMask", wt.ULONG)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = wt.HANDLE
    k.SetProcessInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    k.SetProcessInformation.restype = wt.BOOL
    s = PPT(1, 0x1, 0)      # PROCESS_POWER_THROTTLING_EXECUTION_SPEED を制御し、切る
    ok = k.SetProcessInformation(k.GetCurrentProcess(), 4, ctypes.byref(s), ctypes.sizeof(s))   # 4 = ProcessPowerThrottling
    return bool(ok), ctypes.get_last_error()


if __name__ == "__main__":
    opt_out()
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    d = os.path.dirname(os.path.abspath(script))
    if d not in sys.path:
        sys.path.insert(0, d)
    runpy.run_path(script, run_name="__main__")
