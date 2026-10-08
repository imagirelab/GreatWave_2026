# FLIP41：斜面と同じ位相の風の圧力（p_mode 2）が書き込まれるかの短い試し（読むだけ。場面は保存しない）
import hou, json, sys, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
import v_cfg
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP41/v_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
c = v_cfg.b1(5, 25, 1.0, HL=0.04, wind=True, P0=295.732)
ctrl = hou.node("/obj/V_SETUP/CTRL")
for k, v in c["parms"].items():
    ctrl.parm(k).set(v)
ctrl.parm("ramp_s").set(3.0); ctrl.parm("p_ramp").set(1.0); ctrl.parm("pw_x0").set(0.0); ctrl.parm("pw_tap").set(1.0); ctrl.parm("ckpt_on").set(0)
hou.setSimulationEnabled(True)
fd = hou.node("/obj/V_READ/diag_fields")
fi = hou.node("/obj/V_READ/surface_field")
for f in range(1, 241):
    hou.setFrame(f)
g = fd.geometry()
for pr in g.prims():
    nm = pr.attribValue("name")
    if nm == "surfacepressure":
        vals = [round(float(pr.sample(hou.Vector3(x, 0.4, 0.0))), 2) for x in [float(v) for v in np.arange(2, 42, 2)]]
        print("surfacepressure y=0.4:", vals)
        vals = [round(float(pr.sample(hou.Vector3(x, -1.5, 0.0))), 2) for x in [float(v) for v in np.arange(2, 42, 2)]]
        print("surfacepressure y=-1.5:", vals)
gs = fi.geometry(); v = gs.prims()[0]
print("surface sdf y=0:", [round(float(v.sample(hou.Vector3(x, 0.0, 0.0))), 2) for x in [float(v) for v in np.arange(2, 42, 2)]])
w = hou.node("/obj/V_SIM/wind_pressure"); print("wrangle errors", w.errors(), w.warnings())
