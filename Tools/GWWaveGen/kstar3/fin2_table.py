# -*- coding: utf-8 -*-
"""Q20 final loop 2: side-by-side rubric table K* | loop 1 | final (numpy-bool-safe pass flags).
usage: py -3.10 fin2_table.py kstar.json loop1.json final.json out.md"""
import sys, json
def load(p):
    R = json.load(open(p, encoding="utf-8"))
    out = {}
    for fid, L in R["checks"].items():
        for x in L:
            out[(fid, x["name"])] = x
    return R, out
def fmt(x):
    if x is None:
        return "-"
    v = x["value"]
    vs = ("[%.2f, %.2f]" % tuple(v)) if isinstance(v, list) else (("%.2f" % v) if isinstance(v, float) else str(v))
    pm = x["pass_must"]
    tag = "" if pm is None else (" pass" if bool(pm) else " FAIL")
    return vs + tag
Rk, K = load(sys.argv[1]); R1, L1 = load(sys.argv[2]); Rf, F = load(sys.argv[3])
keys = list(F.keys())
for k in list(K.keys()) + list(L1.keys()):
    if k not in keys:
        keys.append(k)
def cnt(D):
    return sum(1 for x in D.values() if x["pass_must"] is not None and not bool(x["pass_must"]))
lines = ["| id | check | must | K* 26修正01 | loop 1 | final (loop 2) |", "| --- | --- | --- | --- | --- | --- |"]
for k in sorted(keys, key=lambda t: (t[0], keys.index(t))):
    x = F.get(k) or L1.get(k) or K.get(k)
    lines.append("| %s | %s | %s | %s | %s | %s |" % (k[0], k[1], x["must"], fmt(K.get(k)), fmt(L1.get(k)), fmt(F.get(k))))
lines.append("| | must failures (numpy-bool-safe) | | %d / %d | %d / %d | %d / %d |" % (cnt(K), len(K), cnt(L1), len(L1), cnt(F), len(F)))
open(sys.argv[4], "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines[-3:]))
