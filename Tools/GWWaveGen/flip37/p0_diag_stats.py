# -*- coding: utf-8 -*-
"""P0 の診断 2：場（collision・surface・pressure・vel）の全体の最小・最大と、中央の z の縦断面の様子（hython）。"""
import hou, sys, json
import numpy as np
args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
HIP = args.get("hip", r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p0_tank.hiplc")
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P0_SETUP/CTRL")
for k, v in args.get("parms", {"H": 0.0}).items():
    ctrl.parm(k).set(v)
for k, v in args.get("node_parms", {}).items():
    path, pn = k.rsplit("/", 1)
    hou.node(path).parm(pn).set(v)
for path in args.get("bypass", []):
    hou.node(path).bypass(True)
if args.get("vdb"):
    st = hou.node("/obj/P0_SETUP")
    for src, imp in (("OUT_SURFACE", "import_nbsurface"), ("OUT_VEL", "import_nbvelocity")):
        cv = st.createNode("convertvdb", "vdb_" + src)
        cv.setInput(0, hou.node("/obj/P0_SETUP/" + src))
        cv.parm("conversion").set("vdb")
        if src == "OUT_SURFACE" and cv.parm("vdbclass") is not None:
            print("vdbclass menu", cv.parm("vdbclass").menuItems())
            cv.parm("vdbclass").set(args.get("vdbclass", "sdf"))
        hou.node("/obj/P0_SIM/water").parm(imp).set(cv.path())
        g = cv.geometry()
        print("converted", src, [(p.type(), p.resolution() if hasattr(p, "resolution") else None) for p in g.prims()][:2])
hou.setSimulationEnabled(True)
fi = hou.node("/obj/P0_READ/surface_field")
names = args.get("fields", ["collision", "surface", "pressure", "vel"])
fi.parm("fields").set(len(names))
for i, nm in enumerate(names):
    fi.parm("objname%d" % (i + 1)).set("water"); fi.parm("fieldname%d" % (i + 1)).set(nm)
for f in args.get("frames", [2, 4]):
    hou.setFrame(f)
    g = fi.geometry()
    print("== frame", f)
    for p in g.prims():
        nm = p.attribValue("name") if g.findPrimAttrib("name") else "?"
        nx, ny, nz = p.resolution()
        a = np.frombuffer(p.allVoxelsAsString(), dtype=np.float32).reshape(nz, ny, nx)
        k = nz // 2
        c = a[k]
        p0 = p.indexToPos((0, 0, 0)); p1 = p.indexToPos((1, 1, 1))
        # 列 x=300 の縦の並び（y の 6 点）
        i300 = int(round((300 - p0[0]) / (p1[0] - p0[0])))
        i650 = int(round((650 - p0[0]) / (p1[0] - p0[0])))
        js = np.linspace(0, ny - 1, 8).astype(int)
        if nx < 10:
            print("  %-10s res=%s value=%.3f" % (nm, (nx, ny, nz), a.min())); continue
        print("  %-10s res=%s min=%.3f max=%.3f  zmid col300=%s col650=%s" % (
            nm, (nx, ny, nz), a.min(), a.max(),
            np.round(c[js, i300], 2).tolist(), np.round(c[js, i650], 2).tolist()))
