# -*- coding: utf-8 -*-
"""美術の見本02 BACK：評価基準（rubric_check.py の json）を土台と候補で並べ、値・必須の合否が変わった項目を出す。
py -3.10 back_rubric_diff.py <base.json> <cand.json> [out.json]
"""
import sys
import json


def main():
    a = json.load(open(sys.argv[1], encoding="utf-8"))
    b = json.load(open(sys.argv[2], encoding="utf-8"))
    A = {"%s | %s" % (f, x["name"]): x for f, lst in a["checks"].items() for x in lst}
    B = {"%s | %s" % (f, x["name"]): x for f, lst in b["checks"].items() for x in lst}
    rows = []
    for k in A:
        x, y = A[k], B.get(k)
        if y is None:
            continue
        vx, vy = x.get("value"), y.get("value")
        mx, my = x.get("pass_must"), y.get("pass_must")
        if vx != vy or mx != my:
            rows.append({"item": k, "base": vx, "cand": vy, "must_base": mx, "must_cand": my, "must": x.get("must")})
    out = {"summary_base": a.get("summary"), "summary_cand": b.get("summary"), "changed": rows}
    for r in rows:
        flag = "" if r["must_base"] == r["must_cand"] else ("  <-- must %s -> %s" % (r["must_base"], r["must_cand"]))
        print("%-70s %s -> %s%s" % (r["item"][:70], r["base"], r["cand"], flag))
    print("summary", a.get("summary"), "->", b.get("summary"))
    if len(sys.argv) > 3:
        json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
