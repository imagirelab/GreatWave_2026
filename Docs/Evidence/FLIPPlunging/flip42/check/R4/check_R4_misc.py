# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：記録の外側の確かめ（計画の凍結、R4fix の確かめ R3d、設定の違い、置き場、時刻、2 進の割り切れ）。
py -3.10 check_R4_misc.py → check_R4_misc.json
"""
import os, json, glob, hashlib, shutil, re
import numpy as np
from ck_common import ROOT, RUNS, load_hf, load_sec

OUTDIR = os.path.dirname(os.path.abspath(__file__))
BASE = r"G:/Unity/GreatWave_2026_Fresh"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    out = {}
    # 1. 計画の凍結
    fz = json.load(open(ROOT + "/plan/plan_frozen.json", encoding="utf-8"))
    out["plan_frozen"] = [dict(path=e["path"], frozen=e["sha256"], now=sha(os.path.join(BASE, e["path"])),
                               same=sha(os.path.join(BASE, e["path"])) == e["sha256"]) for e in fz["frozen"]]
    # 2. R3d と R3（3319〜3800）
    a = load_hf("R3", keep_full=True); b = load_hf("R3d", keep_full=True)
    fa = {int(f): i for i, f in enumerate(a["frames"])}
    same = diff = 0; ssd = 0; npd = 0
    for i, f in enumerate(b["frames"]):
        j = fa[int(f)]
        if np.array_equal(a["full"][j], b["full"][i], equal_nan=True):
            same += 1
        else:
            diff += 1
        if a["ss_n"][j] != b["ss_n"][i] and b["ss_n"][i] >= 0 and a["ss_n"][j] >= 0:
            ssd += 1
        if a["npts"][j] >= 0 and b["npts"][i] >= 0 and a["npts"][j] != b["npts"][i]:
            npd += 1
    sa = load_sec("R3"); sb = load_sec("R3d")
    s_same = s_diff = 0
    for f in sb["frames"]:
        if np.array_equal(sa["sdf"][int(f)], sb["sdf"][int(f)], equal_nan=True):
            s_same += 1
        else:
            s_diff += 1
    out["R3d_vs_R3"] = dict(hf_frames=[int(b["frames"][0]), int(b["frames"][-1]), int(len(b["frames"]))], hf_same=same, hf_diff=diff,
                            ss_n_diff=ssd, npts_diff=npd, sec_frames=int(len(sb["frames"])), sec_same=s_same, sec_diff=s_diff,
                            R3d_overlap=[b["overlap_same"], b["overlap_diff"]])
    del a, b, sa, sb
    # 3. 設定の違い（計画の R4 と R4d）
    c0 = json.load(open(RUNS + "/R4/cfg_in0.json", encoding="utf-8"))
    c1 = json.load(open(RUNS + "/R4d/cfg.json", encoding="utf-8"))
    c2 = json.load(open(ROOT + "/R4fix/cfg_R4d.json", encoding="utf-8"))
    c3 = json.load(open(ROOT + "/R4/cfg_R4d.json", encoding="utf-8"))
    c4 = json.load(open(ROOT + "/R4/cfg_R4d_b.json", encoding="utf-8"))

    def dd(x, y, pre=""):
        r = {}
        for k in sorted(set(x) | set(y)):
            if isinstance(x.get(k), dict) and isinstance(y.get(k), dict):
                r.update(dd(x[k], y[k], pre + k + "."))
            elif x.get(k) != y.get(k):
                r[pre + k] = [x.get(k), y.get(k)]
        return r
    out["cfg_diff_R4plan_vs_R4d_run"] = {k: v for k, v in dd(c0, c1).items() if k not in ("note",)}
    out["cfg_diff_R4fix_vs_R4d_run"] = {k: v for k, v in dd(c2, c1).items() if k not in ("note",)}
    out["cfg_diff_R4cfg_vs_R4cfg_b"] = {k: v for k, v in dd(c3, c4).items() if k not in ("note",)}
    # 4. 2 進の割り切れ（32 ビットの小数で丸めずに表せるか）
    def exact32(v):
        return float(np.float32(v)) == v
    vals = {}
    for nm, dp in (("R4_plan", 0.177), ("R4d", 0.1767578125), ("R3", 0.25), ("R2", 0.35)):
        vox = 2 * dp
        n = int(round(c1["parms"]["Lx"] / vox)) if nm == "R4d" else None
        vals[nm] = dict(dp=dp, vox=vox, vox_exact32=exact32(vox), half_vox_exact32=exact32(vox / 2), Lz_exact32=exact32(4 * vox),
                        vox_x_3400_exact32=exact32(3400 * vox))
    vals["R4d_Lx_over_vox"] = c1["parms"]["Lx"] / (2 * 0.1767578125)
    vals["ratio_0177_to_R4d"] = 0.177 / 0.1767578125 - 1
    vals["R4d_vs_R3_over_sqrt2"] = 0.1767578125 / (0.25 / 2 ** 0.5) - 1
    out["binary"] = vals
    # 5. 起動の記録（場面の SHA、Houdini の版、止まった理由、メモリ）
    runsum = {}
    for r in ("R2", "R3", "R3d", "R4d"):
        L = []
        for fn in sorted(glob.glob(os.path.join(RUNS, r, "run_c*.json"))):
            d = json.load(open(fn, encoding="utf-8"))
            L.append((d["hip_sha256"][:12], d["houdini"], d["stopped"], d["rss_peak_gb"]))
        runsum[r] = dict(n=len(L), hip=sorted(set(x[0] for x in L)), houdini=sorted(set(x[1] for x in L)),
                         stopped=sorted(set(str(x[2]).split(" at ")[0] for x in L)), rss_peak_max=max(x[3] for x in L))
    out["launches"] = runsum
    # 6. 途中保存と置き場
    ck = glob.glob(os.path.join(RUNS, "R4d", "ckpt", "*"))
    sz = [os.path.getsize(p) for p in ck]
    out["ckpt_R4d"] = dict(n=len(ck), total_gb=sum(sz) / 2 ** 30, min_gb=min(sz) / 2 ** 30, max_gb=max(sz) / 2 ** 30,
                           total_GB_1e9=sum(sz) / 1e9)
    du = shutil.disk_usage("G:/")
    out["G_free_now_gb"] = du.free / 2 ** 30
    # 7. 時刻（最初の起動の始まりと最後の終わり）
    l1 = open(os.path.join(RUNS, "R4d", "log_c0001.txt"), encoding="utf-8", errors="replace").readline().strip()
    ln = [x for x in open(os.path.join(RUNS, "R4d_chain_stdout_b.txt"), encoding="utf-8", errors="replace").read().splitlines() if x.strip()]
    out["times"] = dict(first_log_line=l1, last_chain_lines=ln[-2:])
    # 8. 消していないか（元の R4 の記録、試しの出力）
    out["kept"] = dict(runs_R4=sorted(os.listdir(RUNS + "/R4"))[:40], r4dbg_n=len(os.listdir(ROOT + "/tmp_houdini/r4dbg")),
                       R4fix_tests_n=len(os.listdir(ROOT + "/R4fix/tests")))
    # 9. 静かな水槽の試しの 6 コマ目の速さ（R4d と R3 の設定）
    def lastv(fn):
        s = open(fn, encoding="utf-8", errors="replace").read()
        m = re.findall(r"frame (\d+) .*?vy_mean (-?[\d.]+).*?\|v\|max ([\d.]+)", s)
        return m[-1] if m else None
    out["still_tests"] = {nm: lastv(os.path.join(ROOT, "R4fix", "tests", nm + ".txt")) for nm in ("s176758_L1202_v", "s25_L1202_v", "s177_L600", "s177_L60", "s1875_L1202", "s15625_L600", "try_R4d_36f")}
    json.dump(out, open(os.path.join(OUTDIR, "check_R4_misc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
