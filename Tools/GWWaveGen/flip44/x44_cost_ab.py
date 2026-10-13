# -*- coding: utf-8 -*-
"""FLIP44 費用の比べ（記録だけ。record_ja.md の計画から変えた所 7）：同じ機械の同じ時間帯に、FLIP42 の場面（g_tank.hiplc、R3 の設定）と
FLIP44 の場面（g44_tank.hiplc、S1b の設定＝R3 と同じ水槽・入口を表で）を、粒子 0.25 m で同じコマ数だけ続けて走らせ、1 コマの秒を比べる。
FLIP42 の場面は読むだけ（保存しない。途中保存を切る。FLIP42 のフォルダーには何も書かない）。
hython x44_cost_ab.py <42|44> <コマ数>  → Unity/Build/FLIP44/smoke/S1c/cost_<42|44>.json
"""
import hou, sys, os, json, time, ctypes
from ctypes import wintypes
import numpy as np

which, nf = sys.argv[1], int(sys.argv[2])
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44/smoke/S1c"
os.makedirs(OUT, exist_ok=True)
k = ctypes.WinDLL("kernel32", use_last_error=True)


class PPTS(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]


k.GetCurrentProcess.restype = wintypes.HANDLE
k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
h = k.GetCurrentProcess(); s_ = PPTS(1, 0x1, 0x0)
prio = dict(power_throttling_off=bool(k.SetProcessInformation(h, 4, ctypes.byref(s_), ctypes.sizeof(s_))), below_normal=bool(k.SetPriorityClass(h, 0x4000)))
if which == "42":
    cfg = json.load(open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3/cfg.json", encoding="utf8"))
    hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
    ctrl = hou.node("/obj/G_SETUP/CTRL"); sim = "/obj/G_SIM"; rd = "/obj/G_READ/surface_field"
else:
    cfg = json.load(open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44/smoke/S1b/cfg.json", encoding="utf8"))
    hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP44/g44_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
    ctrl = hou.node("/obj/G44_SETUP/CTRL"); sim = "/obj/G44_SIM"; rd = "/obj/G44_READ/surface_field"
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
    import g44_tanklib as L
    inl = cfg["inlet"]; ctrl.parm("inlet_tab").set(L.inlet_tab_string(inl["freqs_Hz"], inl["amps_m"], inl["phases_rad"], inl["k"]))
for kk, v in cfg["parms"].items():
    ctrl.parm(kk).set(v)
ctrl.parm("ckpt_on").set(0)
fs = hou.node(sim + "/flipsolver")
fs.parm("veltransfer").set("apic"); fs.parm("donarrowband").set(0)
hou.setSimulationEnabled(True)
fi = hou.node(rd)
W = []
t_all = time.time()
for f in range(1, nf + 1):
    t0 = time.time(); hou.setFrame(f); g = fi.geometry(); W.append(time.time() - t0)
res = dict(which=which, frames=nf, wall=W, median_2_n=float(np.median(W[1:])), total_s=time.time() - t_all, priority=prio,
           date=time.strftime("%Y-%m-%d %H:%M:%S"))
json.dump(res, open(os.path.join(OUT, "cost_%s.json" % which), "w", encoding="utf8"), indent=1)
print("DONE", which, "median s/frame (2..%d)" % nf, round(res["median_2_n"], 3))
