# -*- coding: utf-8 -*-
"""評価器 23 の 4 組（線あり・なし × 爪あり・なし）の合否と項目ごとの値を、前（採用の PL29/PL36）と見本 B で並べる。"""
import json
import os
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/"
out = {}
for tag, root in (("before", B + "eval_before"), ("sampleB", B + "final/eval23")):
    out[tag] = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        d = json.load(open(os.path.join(root, "off_" + c, "metrics.json"), encoding="utf-8"))
        items = d["items"]
        cnt = {}
        per = {}
        for k, it in items.items():
            v = it.get("verdict", "other")
            v = v if v in ("pass", "fail") else "other"
            cnt[v] = cnt.get(v, 0) + 1
            ms = it.get("measures", [])
            per[k] = dict(verdict=it.get("verdict"), values={m.get("metric", "?"): (m.get("value_max_px", m.get("value"))) for m in ms if isinstance(m, dict)})
        out[tag][c] = dict(counts=cnt, items=per)
json.dump(out, open(B + "final/eval23_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
    print(c, "before", out["before"][c]["counts"], "B", out["sampleB"][c]["counts"])
    for k in out["before"][c]["items"]:
        vb = out["before"][c]["items"][k]["verdict"]; va = out["sampleB"][c]["items"][k]["verdict"]
        if vb != va:
            print("   changed", k, vb, "->", va, out["before"][c]["items"][k]["values"], out["sampleB"][c]["items"][k]["values"])
