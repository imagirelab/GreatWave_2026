# -*- coding: utf-8 -*-
"""P0：古い版（22.0.429 のころ）で保存した .hiplc が 22.0.459 で開けるかを確かめる（hython。計算はしない）。
保存した版（$_HIP_SAVEVERSION）、読み込みの警告、ノード数、表示ノードを cook した時のエラーを JSON に書く。"""
import hou, json, os, time
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P0/oldhip_check.json"
FILES = [r"G:/Unity/GreatWave_2026_Fresh/Houdini/Design28R01/kstar_h_R4.hiplc",
         r"G:/Unity/GreatWave_2026_Fresh/Houdini/Polish28/rec.hiplc",
         r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP36/p0_tank.hiplc"]
res = {"running": hou.applicationVersionString(), "files": []}
for p in FILES:
    rec = {"file": p, "exists": os.path.exists(p)}
    if not rec["exists"]:
        res["files"].append(rec); continue
    t0 = time.time()
    try:
        hou.hipFile.load(p, suppress_save_prompt=True, ignore_load_warnings=False)
        rec["load"] = "ok"
    except hou.LoadWarning as w:
        rec["load"] = "ok_with_warnings"; rec["warning"] = str(w)[:800]
    except Exception as e:
        rec["load"] = "error"; rec["error"] = str(e)[:800]
    rec["load_s"] = round(time.time() - t0, 2)
    rec["saved_version"] = hou.text.expandString("$_HIP_SAVEVERSION")
    nodes = hou.node("/").allSubChildren()
    rec["nodes"] = len(nodes)
    errs = []
    # 表示ノードの SOP だけを cook して、エラーを集める（DOP の計算はしない）
    for n in hou.node("/obj").children():
        try:
            dn = n.displayNode() if hasattr(n, "displayNode") else None
            if dn is not None and n.type().name() == "geo":
                dn.cook(force=False)
                if dn.errors():
                    errs.append([dn.path(), [str(e)[:200] for e in dn.errors()]])
        except Exception as e:
            errs.append([n.path(), str(e)[:200]])
    rec["cook_errors"] = errs
    res["files"].append(rec)
hou.hipFile.clear(suppress_save_prompt=True)
json.dump(res, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1, ensure_ascii=False))
