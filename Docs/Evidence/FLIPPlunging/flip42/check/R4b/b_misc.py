# -*- coding: utf-8 -*-
"""R4b 確かめ：R3d と R3 の一致、起動の数と時間（runs.jsonl）、途中保存と runs/ の大きさ。py -3.10 b_misc.py → b_misc.json"""
import os, json, glob, collections
import numpy as np
import b_common as B


def main():
    out = {}
    # R3d と R3（3319〜3800 コマ）
    a = B.hf("R3d"); b = B.hf("R3")
    ia = {int(f): i for i, f in enumerate(a["frames"])}; ib = {int(f): i for i, f in enumerate(b["frames"])}
    common = sorted(set(ia) & set(ib))
    same = sum(np.array_equal(a["eta"][ia[f]], b["eta"][ib[f]], equal_nan=True) for f in common)
    ss_same = sum(int(a["ss_n"][ia[f]] == b["ss_n"][ib[f]]) for f in common)
    sa = B.SecReader("R3d"); sb = B.SecReader("R3")
    cs = sorted(set(map(int, sa.frames)) & set(map(int, sb.frames)))
    ssec = sum(np.array_equal(sa.get(f), sb.get(f)) for f in cs)
    out["R3d_vs_R3"] = dict(hf_frames=[common[0], common[-1], len(common)], hf_identical=int(same), substeps_identical=ss_same,
                            sec_frames=[cs[0], cs[-1], len(cs)], sec_identical=int(ssec), r3d_overlap=a["ndup"], r3d_overlap_diff=a["ndiff"])
    # runs.jsonl
    rows = [json.loads(l) for l in open(os.path.join(B.ROOT, "runs.jsonl"), encoding="utf-8") if l.strip()]
    agg = collections.OrderedDict()
    for r in rows:
        agg.setdefault(r["run_id"], [0, 0.0]); agg[r["run_id"]][0] += 1; agg[r["run_id"]][1] += r["wall_launch_s"] / 3600
    out["runs_jsonl"] = {k: [v[0], round(v[1], 3)] for k, v in agg.items()}
    out["runs_jsonl_total"] = [len(rows), round(sum(v[1] for v in agg.values()), 3)]
    pre = [k for k in agg if k not in ("R3d", "R4d")]
    out["runs_jsonl_before_R3d_R4d"] = [sum(agg[k][0] for k in pre), round(sum(agg[k][1] for k in pre), 3)]
    out["R4d_houdini"] = sorted(set(r["houdini"] for r in rows if r["run_id"] == "R4d"))
    # 大きさ
    ck = glob.glob(os.path.join(B.ROOT, "R4d", "ckpt", "*"))
    sz = [os.path.getsize(p) for p in ck]
    out["R4d_ckpt"] = dict(n=len(ck), bytes=sum(sz), GB=sum(sz) / 1e9, GiB=sum(sz) / 2 ** 30, each_GiB=[min(sz) / 2 ** 30, max(sz) / 2 ** 30])
    tot = 0
    for dp, dn, fn in os.walk(B.ROOT):
        for f in fn:
            tot += os.path.getsize(os.path.join(dp, f))
    out["runs_dir"] = dict(bytes=tot, GB=tot / 1e9, GiB=tot / 2 ** 30)
    # 小刻み 8 のコマ
    d = B.hf("R4d")
    m = d["ss_n"] == 8
    out["R4d_substep8"] = dict(n=int(m.sum()), t=[float(d["t"][m].min()), float(d["t"][m].max())] if m.any() else None,
                               hist={str(int(k)): int((d["ss_n"] == k).sum()) for k in np.unique(d["ss_n"])})
    B.dump("b_misc.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
