# -*- coding: utf-8 -*-
"""RT48 の確かめ C1（計画 §4）：計算し直しが R3 と同じか。R3 のファイルは開いて読むだけ（py -3.10）。
  (a) R3 の記録で、同じコマが二つの起動の記録にある所が、hf の eta と sec の sdf でバイト単位で同じか（NaN の位置も）。
  (b) R3e（計算し直し）の hf の eta と sec の sdf が、そのコマを持つ R3 の全部の記録とバイト単位で同じか（NaN の位置も）。
使い方: py -3.10 r_c1.py a            → Unity/Build/RT48/data/c1a.json
        py -3.10 r_c1.py b [run_dir]  → Unity/Build/RT48/data/c1b.json（run_dir の既定は Unity/Build/RT48/rerun/R3e）
バイト単位で同じ＝float の値を整数のビットとして比べる（NaN のビットも含む）。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 数値の部品のスレッドの予約（1 つの起動で約 0.6 GB）を小さくする
    _os.environ.setdefault(_v, "1")
import sys, os, json, glob, time, hashlib
import numpy as np

R3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
OUTD = os.environ.get("RT48_DATA", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/data")   # 試しの時だけ環境変数で替える


def records(rd, kind):
    """{コマ: [(ファイル, 番号), ...]}（そのコマを持つ全部の記録）"""
    pat = "hf_c*.npz" if kind == "hf" else "sec_c*_b*.npz"
    idx = {}
    for p in sorted(glob.glob(os.path.join(rd, pat))):
        fr = np.load(p)["frames"]
        for i, f in enumerate(fr):
            idx.setdefault(int(f), []).append((p.replace("\\", "/"), i))
    return idx


class Cache:
    def __init__(self):
        self.d = {}

    def get(self, p, key):
        if (p, key) not in self.d:
            if len(self.d) > 6:
                self.d.clear()
            self.d[(p, key)] = np.load(p)[key]
        return self.d[(p, key)]


def bits(a):
    a = np.ascontiguousarray(a)
    return a.view(np.uint16 if a.dtype == np.float16 else np.uint32)


def same(a, b):
    if a.shape != b.shape or a.dtype != b.dtype:
        return False, "shape/dtype %s %s / %s %s" % (a.shape, a.dtype, b.shape, b.dtype)
    ba, bb = bits(a), bits(b)
    n = int((ba != bb).sum())
    if n == 0:
        return True, ""
    na, nb = np.isnan(a), np.isnan(b)
    with np.errstate(all="ignore"):
        dmax = float(np.nanmax(np.abs(a.astype(np.float64) - b.astype(np.float64))))
    return False, "differ %d values, nan_pos_same %s, max_abs %.3g" % (n, bool((na == nb).all()), dmax)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def part_a():
    C = Cache()
    out = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "check": "C1(a)", "r3": R3, "kinds": {}}
    ok_all = True
    for kind, key in (("hf", "eta"), ("sec", "sdf")):
        idx = records(R3, kind)
        multi = {f: v for f, v in idx.items() if len(v) > 1}
        bad = []
        for f, v in sorted(multi.items()):
            a = C.get(v[0][0], key)[v[0][1]]
            for p, i in v[1:]:
                ok, why = same(a, C.get(p, key)[i])
                if not ok:
                    bad.append({"frame": f, "a": os.path.basename(v[0][0]), "b": os.path.basename(p), "why": why})
        fr = sorted(multi)
        runs = []
        for f in fr:
            if runs and f == runs[-1][1] + 1:
                runs[-1][1] = f
            else:
                runs.append([f, f])
        out["kinds"][kind] = {"frames_with_2plus_records": len(fr), "ranges": runs, "pairs_compared": sum(len(v) - 1 for v in multi.values()),
                              "n_bad": len(bad), "bad_first": bad[:20]}
        ok_all = ok_all and not bad
    out["pass"] = ok_all
    json.dump(out, open(os.path.join(OUTD, "c1a.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: (v if k != "kinds" else {kk: {q: vv[q] for q in ("frames_with_2plus_records", "ranges", "pairs_compared", "n_bad")} for kk, vv in v.items()}) for k, v in out.items()}, ensure_ascii=False, indent=1))
    return ok_all


def part_b(rd):
    C = Cache()
    out = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "check": "C1(b)", "r3": R3, "rerun": rd, "kinds": {}}
    ok_all = True
    for kind, key in (("hf", "eta"), ("sec", "sdf")):
        ia = records(rd, kind)
        ib = records(R3, kind)
        frames = sorted(f for f in ia if 3319 <= f <= 3889)
        bad, n_cmp, missing_r3 = [], 0, []
        inner_bad = []
        for f in frames:
            # R3e の中で同じコマが二つの起動にある時も、同じであることを確かめる
            a0 = C.get(ia[f][0][0], key)[ia[f][0][1]]
            for p, i in ia[f][1:]:
                ok, why = same(a0, C.get(p, key)[i])
                if not ok:
                    inner_bad.append({"frame": f, "why": why})
            if f not in ib:
                missing_r3.append(f)
                continue
            for p, i in ib[f]:
                n_cmp += 1
                ok, why = same(a0, C.get(p, key)[i])
                if not ok:
                    bad.append({"frame": f, "r3": os.path.basename(p), "why": why})
        expect = list(range(3319, 3890))
        out["kinds"][kind] = {"frames_rerun": [frames[0], frames[-1]] if frames else None, "n_frames": len(frames),
                              "missing_in_rerun": [f for f in expect if f not in ia], "missing_in_r3": missing_r3,
                              "comparisons": n_cmp, "n_bad": len(bad), "bad_first": bad[:20], "rerun_internal_bad": inner_bad[:20]}
        ok_all = ok_all and not bad and not inner_bad and not out["kinds"][kind]["missing_in_rerun"]
    out["pass"] = ok_all
    json.dump(out, open(os.path.join(OUTD, "c1b.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
    return ok_all


if __name__ == "__main__":
    os.makedirs(OUTD, exist_ok=True)
    if sys.argv[1] == "a":
        ok = part_a()
    else:
        ok = part_b(sys.argv[2] if len(sys.argv) > 2 else "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/rerun/R3e")
    sys.exit(0 if ok else 3)
