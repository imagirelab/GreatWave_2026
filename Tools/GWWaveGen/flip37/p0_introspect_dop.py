# DOP 部品のパラメータ名の一覧（計算はしない）
import hou, json, os
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P0/p0_introspect_dop.json"
res = {}
obj = hou.node("/obj")
dn = obj.createNode("dopnet", "d")
res["dopnet_obj"] = [[p.name(), p.parmTemplate().label(), str(p.eval())[:50]] for p in dn.parms() if any(k in p.name().lower() for k in ("cache", "explicit", "check", "timestep", "substep", "start", "fps", "scale", "interp"))]
for t in ["flipobject", "flipsolver::2.0", "staticobject", "gasfieldwrangle", "volumesource", "gravity", "popwrangle", "geometrywrangle", "sopgeo"]:
    try:
        n = dn.createNode(t)
        res[t] = {"inputs": list(n.inputLabels()), "parms": [[p.name(), p.parmTemplate().label(), str(p.eval())[:50]] for p in n.parms()]}
    except Exception as e:
        res[t] = "ERR " + str(e)
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("ok")
