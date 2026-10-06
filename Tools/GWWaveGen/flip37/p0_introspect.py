# P0 下準備：古い .hiplc が 22.0.459 で開けるかの確認と、SOP FLIP Solver の中身の調査（計算はしない）
import hou, json, os, sys, time
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P0"
res = {"version": hou.applicationVersionString(), "temp": os.environ.get("HOUDINI_TEMP_DIR")}
# 1) 古いシーンの読み込み
loads = []
for p in [r"G:/Unity/GreatWave_2026_Fresh/Houdini/Design28R01/kstar_h_R4.hiplc",
          r"G:/Unity/GreatWave_2026_Fresh/Houdini/Polish28/rec.hiplc"]:
    t0 = time.time()
    rec = {"file": p}
    try:
        hou.hipFile.load(p, suppress_save_prompt=True, ignore_load_warnings=True)
        rec["ok"] = True
    except hou.LoadWarning as w:
        rec["ok"] = True; rec["warning"] = str(w)[:500]
    except Exception as e:
        rec["ok"] = False; rec["error"] = str(e)[:500]
    rec["load_s"] = round(time.time() - t0, 2)
    try:
        allnodes = hou.node("/").allSubChildren()
        rec["nodes"] = len(allnodes)
        errs = []
        for n in allnodes:
            try:
                if n.errors(): errs.append(n.path())
            except Exception: pass
        rec["nodes_with_errors_before_cook"] = errs[:10]
        rec["saved_version"] = hou.hscript("version")[0].strip()[:200]
    except Exception as e:
        rec["inspect_error"] = str(e)
    loads.append(rec)
res["old_scene_loads"] = loads
hou.hipFile.clear(suppress_save_prompt=True)
# 2) SOP FLIP Solver の全パラメータと中のDOP
geo = hou.node("/obj").createNode("geo", "chk")
s = geo.createNode("flipsolver")
res["sop_flipsolver_inputs"] = list(s.inputLabels())
res["sop_flipsolver_outputs"] = list(s.outputLabels())
res["sop_flipsolver_parms"] = [[p.name(), p.parmTemplate().label(), str(p.eval())[:60]] for p in s.parms()]
inner = []
for n in s.allSubChildren():
    inner.append([n.path().replace(s.path(), ""), n.type().name()])
res["sop_flipsolver_inner"] = inner
# DOP flipsolver inside: narrowband parms and expressions
for n in s.allSubChildren():
    if n.type().name().startswith("flipsolver"):
        d = []
        for p in n.parms():
            nm = p.name()
            if any(k in nm.lower() for k in ("band", "bound", "narrow", "pad", "kill", "sink", "veloc", "surface", "explicit", "check")):
                try: ex = p.expression()
                except Exception: ex = None
                d.append([nm, p.parmTemplate().label(), str(p.eval())[:80], ex])
        res["inner_flipsolver_" + n.name()] = d
c = geo.createNode("flipcontainer")
res["sop_flipcontainer_outputs"] = list(c.outputLabels())
res["sop_flipcontainer_parms_all"] = [[p.name(), p.parmTemplate().label(), str(p.eval())[:40]] for p in c.parms()]
b = geo.createNode("flipboundary")
res["sop_flipboundary_inputs"] = list(b.inputLabels())
res["sop_flipboundary_parms_all"] = [[p.name(), p.parmTemplate().label(), str(p.eval())[:40]] for p in b.parms()]
col = geo.createNode("flipcollide")
res["sop_flipcollide_inputs"] = list(col.inputLabels())
json.dump(res, open(os.path.join(OUT, "p0_introspect.json"), "w"), indent=1, default=str)
print("done")
