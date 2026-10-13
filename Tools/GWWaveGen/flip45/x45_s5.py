# -*- coding: utf-8 -*-
"""FLIP45 煙の試し S5（区切った起動）と S9（途中保存から始めた計算の解析）（py -3.10。計画 plan_ja.md §10.2）。
S5：L1・粒子 0.5 m・F45 の入口（利得なし）で 120 コマを、(i) 1 回の起動（S5_single）と (ii) 1 回 45 秒の起動を 3 回以上つないだ物（S5_chain、
    g45_chain.py）で走らせる。判定：R1・R2・粒子の数・小刻みの数が全部のコマでビット単位で同じ。コマの抜けと重なりがない（重なったコマは
    両方の起動の値が同じ）。止める決まりが誤りなく呼ばれる（chain.log の止まり方）。
S9：S5_single の 60 コマ目の途中保存から始めた計算（S9_from_ckpt、61〜96 コマ）を g45_analyze.py で読み、静かな水面のずれを元の計算の
    記録から読んで、どこから読んだかを書く（FLIP44 の D1）。
使い方：py -3.10 x45_s5.py [run|check]
"""
import sys, os, json, glob, subprocess, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_cfg as C

SM = GC.B45 + "/smoke"
TMP = GC.B45 + "/tmp_houdini"


def run():
    GC.unthrottle_self()
    base = C.smoke("S5", dp=0.5, tag="S5_single")
    base["ckpt_every"] = 12
    base = C.table_for(base)
    # (i) 1 回の起動
    rd = os.path.join(SM, "S5_single"); os.makedirs(rd, exist_ok=True)
    p = os.path.join(rd, "cfg.json"); json.dump(base, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    GC.wait_no_hython()
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    with open(os.path.join(rd, "log_c00001.txt"), "w", encoding="utf8", errors="ignore") as lg:
        subprocess.run([GC.HY, GC.TOOLS + "/g45_run.py", p], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    # (ii) 45 秒の起動をつなぐ
    c2 = dict(base, run_id="S5_chain", wall_limit_s=45.0, ckpt_list=[12], ckpt_every=12)
    c2["table"] = dict(base["table"])
    rd2 = os.path.join(SM, "S5_chain"); os.makedirs(rd2, exist_ok=True)
    p2 = os.path.join(rd2, "cfg_in.json"); json.dump(c2, open(p2, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, GC.TOOLS + "/g45_chain.py", p2], stdin=subprocess.DEVNULL)
    # S9：S5_single の 60 コマ目の途中保存から
    c3 = dict(base, run_id="S9_from_ckpt", f_end=96, ckpt_every=12, still_offset_from="S5_single",
              from_ckpt=dict(run="S5_single", frame=60, why="S9：途中保存から始めた計算の解析"))
    c3["table"] = dict(base["table"])
    rd3 = os.path.join(SM, "S9_from_ckpt"); os.makedirs(rd3, exist_ok=True)
    p3 = os.path.join(rd3, "cfg_in.json"); json.dump(c3, open(p3, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, GC.TOOLS + "/g45_chain.py", p3], stdin=subprocess.DEVNULL)


def merged(rd, kind, key):
    by = {}
    dup = {}
    for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
        c0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            f = int(f)
            a = d[key][i]
            if f in by:
                dup.setdefault(f, []).append(bool(np.array_equal(by[f][1], a, equal_nan=True)))
                if c0 >= by[f][0]:
                    by[f] = (c0, a)
            else:
                by[f] = (c0, a)
    return {f: v[1] for f, v in by.items()}, dup


def r6(rd):
    out = {}
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz"))):
        c0 = int(os.path.basename(p)[4:9])
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            out.setdefault(int(f), []).append((c0, int(d["npts"][i]), int(d["ss_n"][i])))
    return out


def check():
    a, b = os.path.join(SM, "S5_single"), os.path.join(SM, "S5_chain")
    res = {}
    for kind, key in (("hf", "eta"), ("r2", "sdf"), ("r2", "u"), ("r3", "sdf")):
        A, _ = merged(a, kind, key); B, dupB = merged(b, kind, key)
        fr = sorted(set(A) | set(B))
        miss = [f for f in range(1, 121) if f not in B]
        diff = [f for f in fr if f in A and f in B and not np.array_equal(A[f], B[f], equal_nan=True)]
        res["%s.%s" % (kind, key)] = dict(frames_single=len(A), frames_chain=len(B), missing_in_chain=miss, differ=diff[:20], n_differ=len(diff),
                                          duplicates=len(dupB), duplicates_all_equal=bool(all(all(v) for v in dupB.values())))
    RA, RB = r6(a), r6(b)
    dn = [f for f in RA if f in RB and RA[f][-1][1:] != max(RB[f])[1:]]
    res["particles_substeps_differ"] = dn[:20]
    launches = sorted(glob.glob(os.path.join(b, "run_c*.json")))
    res["chain_launches"] = len(launches)
    res["chain_stops"] = [json.load(open(p, encoding="utf8")).get("stopped") for p in launches]
    res["chain_log_tail"] = open(os.path.join(b, "chain.log"), encoding="utf8").read().splitlines()[-4:]
    ok = all(v["n_differ"] == 0 and not v["missing_in_chain"] and v["duplicates_all_equal"] for k, v in res.items() if isinstance(v, dict) and "n_differ" in v)
    res["pass"] = bool(ok and not dn and len(launches) >= 3 and all((s or "").startswith("wall_limit") for s in res["chain_stops"][:-1])
                       and res["chain_stops"][-1] is None)
    # S9
    import g45_analyze as GA
    try:
        an = GA.analyze("S9_from_ckpt", "smoke", quick=True)
        res["S9"] = dict(still_level_offset_m=an["still_level_offset_m"], source=an["still_offset_source"], checkpoint_started=an["checkpoint_started"],
                         single_offset=json.load(open(os.path.join(a, "run.json"), encoding="utf8"))["still_offset"])
        res["S9"]["pass"] = bool(abs(an["still_level_offset_m"] - res["S9"]["single_offset"]["value"]) < 1e-12 and "S5_single" in an["still_offset_source"])
    except Exception as e:
        res["S9"] = dict(error=repr(e)[:300], passed=False)
    R = json.load(open(SM + "/smoke_results.json", encoding="utf8")) if os.path.exists(SM + "/smoke_results.json") else {}
    R["S5_S9"] = res
    json.dump(R, open(SM + "/smoke_results.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.argv[1] == "run":
        run()
    print(json.dumps(check(), ensure_ascii=False, indent=1, default=str))
