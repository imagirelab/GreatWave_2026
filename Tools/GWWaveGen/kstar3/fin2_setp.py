# -*- coding: utf-8 -*-
"""Q20 final loop 2: set knot tables / pipeline values in a params json (small helper for the iterations).
usage: py -3.10 fin2_setp.py in.json out.json 'knot=[[c,v],...]' 'pipeline.key=value' 'grid.key=value' ..."""
import sys, json
src, dst = sys.argv[1], sys.argv[2]
p = json.load(open(src, encoding="utf-8"))
for a in sys.argv[3:]:
    k, v = a.split("=", 1)
    v = json.loads(v)
    if "." in k:
        g, kk = k.split(".", 1); p.setdefault(g, {})[kk] = v
    else:
        p["knots"][k] = v
json.dump(p, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok", dst)
