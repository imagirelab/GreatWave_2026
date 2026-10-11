# -*- coding: utf-8 -*-
"""FLIP42 R4fix：場面の FLIP Object・FLIP Solver・Static Object などの、既定から変えたパラメーターと、
圧力・衝突・境界にかかわるパラメーターを一覧にする（hython、読むだけ。場面は保存しない）。"""
import hou, re
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
KEY = re.compile(r"(clos|bound|coll|limit|pad|band|extrap|radius|sep|kill|sink|bounds|border|press|precond|toler|iter|reseed|surface|div|sdf|offset|thick|voxel|size)", re.I)
for path in ("/obj/G_SIM/water", "/obj/G_SIM/flipsolver", "/obj/G_SIM/seabed", "/obj/G_SIM/gravity", "/obj/G_SIM"):
    n = hou.node(path)
    print("=====", path, n.type().name())
    for p in n.parms():
        try:
            v = p.eval()
        except Exception:
            v = "?"
        nd = not p.isAtDefault()
        if nd or KEY.search(p.name()) or KEY.search(p.description()):
            try:
                raw = p.expression()
            except Exception:
                raw = ""
            print(("* " if nd else "  ") + p.name(), "|", p.description(), "|", v, "|", raw[:60])
