# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：評価基準（rubric_check.py --gate）の AS02C と AS04 の差（新しく落ちた必須・新しく通った必須・値の変わり）。
使い方：py -3.10 -B shape_rubric_diff.py <AS02C.json> <AS04.json> <out.json>"""
import json
import sys


def flat(d):
    out = {}
    for fid, rows in d["checks"].items():
        for r in rows:
            out[(fid, r["name"])] = r
    return out


def main():
    a, b = json.load(open(sys.argv[1], encoding="utf-8")), json.load(open(sys.argv[2], encoding="utf-8"))
    fa, fb = flat(a), flat(b)
    new_fail, new_pass, changed = [], [], []
    for k, ra in fa.items():
        rb = fb.get(k)
        if rb is None:
            continue
        e = {"id": k[0], "name": k[1], "AS02C": ra["value"], "AS04": rb["value"], "must": ra["must"]}
        if ra["pass_must"] and not rb["pass_must"]:
            new_fail.append(e)
        elif (not ra["pass_must"]) and rb["pass_must"]:
            new_pass.append(e)
        elif ra["value"] != rb["value"]:
            changed.append(e)
    res = {"summary": {"AS02C": a["summary"], "AS04": b["summary"]}, "new_must_fail": new_fail, "new_must_pass": new_pass, "value_changed_same_verdict": changed}
    json.dump(res, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res["summary"], ensure_ascii=False))
    for e in new_fail:
        print("新しく否：", e)
    for e in new_pass:
        print("新しく合：", e)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
