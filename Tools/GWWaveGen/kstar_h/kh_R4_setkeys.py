# -*- coding: utf-8 -*-
"""K*′ 精修 R4：設計の json の ramp の鍵を書き換える小さな道具（py -3.10）。
usage: py -3.10 kh_R4_setkeys.py in.json out.json name=c1:v1,c2:v2,... [name2=const] [--drop-sculpt]
"""
import sys
import json

a = sys.argv[1:]
d = json.load(open(a[0], encoding="utf-8"))
for x in a[2:]:
    if x == "--drop-sculpt":
        for n in list(d["keys"]):
            if n.startswith("sculpt_"):
                d["keys"][n] = {"c": [0.0], "v": [0.0]}
        continue
    n, v = x.split("=", 1)
    if ":" in v:
        cs, vs = zip(*[tuple(float(t) for t in kv.split(":")) for kv in v.split(",")])
        d["keys"][n] = {"c": list(cs), "v": list(vs)}
    else:
        d["keys"][n] = {"c": [0.0], "v": [float(v)]}
for k in ("sculpt_log", "lipfit_log"):
    d.pop(k, None)
json.dump(d, open(a[1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok", a[1])
