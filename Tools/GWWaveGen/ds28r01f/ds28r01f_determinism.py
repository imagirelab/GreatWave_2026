# -*- coding: utf-8 -*-
"""設計28修正01 試行F：パッケージの決定性の確かめ（記録）。生成（複数のプロセス）の節点の層を、1 つのプロセスで作り直して、
16 bit と精度の層のバイトが同じかを比べる（プロセスの数と順によらないことの確かめ）。

生成の記録（ds28r01f_generate_log.json）から同じ条件（num_no_rebound_after_apex の格子・small_lip_body の行・窓・橋渡し）を読み、
ds27_keypose.json の knot_tau から選んだ層（既定：最初・中ほど・τ −2 s に最も近い・最後）を、生成器の local(τ) から同じ式で量子化する。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_determinism.py --package Unity/Build/Design/28R01F/F_R1/art_on
出力：<パッケージ>/determinism_check.json
"""
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    a = ap.parse_args()
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    import ds28r01f_generate as GEN
    t0 = time.time()
    pkg = a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package)
    L = json.load(open(os.path.join(pkg, "ds28r01f_generate_log.json"), encoding="utf-8"))["result"]
    J = json.load(open(os.path.join(pkg, "ds27_keypose.json"), encoding="utf-8"))
    work = os.path.join(pkg, "_work")
    sl = (L.get("scan") or {}).get("small_lip_body") or {}
    stage = dict(nr=os.path.join(work, "nr_cache_small_lip.npz") if sl.get("rows") else os.path.join(work, "nr_cache.npz"),
                 delip=tuple(sl.get("rows") or ()), gw=os.path.join(work, "guard_window.npz") if os.path.isfile(os.path.join(work, "guard_window.npz")) else None,
                 bridge=os.path.join(work, "bridge.npz") if os.path.isfile(os.path.join(work, "bridge.npz")) else None, layers=None)
    GEN._winit(os.path.join(REPO, L["kstar"]["dir"]), L.get("overrides"), L.get("off") or [])
    GEN._ensure(stage)
    kn = np.asarray(J["knot_tau"], float)
    nl, nv, nu = int(J["layers"]), int(J["rows"]), int(J["cols"])
    pick = sorted({0, nl // 2, int(np.argmin(np.abs(kn + 2.0))), nl - 1})
    lo = np.asarray(J["bbox_min"], float)
    size = np.asarray(J["bbox_size"], float)
    P16 = np.memmap(os.path.join(pkg, J["pos_file"]), dtype="<u2", mode="r", shape=(nl, nv, nu, 4))
    P8 = np.memmap(os.path.join(pkg, J["pos_lo_file"]), dtype=np.uint8, mode="r", shape=(nl, nv, nu, 4))
    res = []
    for k in pick:
        X = GEN._G.local(float(kn[k]))
        u = (X - lo) / size * 65535.0
        q = np.clip(np.round(u), 0, 65535)
        e = u - q
        ql = np.clip(np.round((e + 0.5) * 255.0), 0, 255).astype(np.uint8)
        same16 = bool(np.array_equal(q.astype("<u2"), np.asarray(P16[k, ..., :3])))
        same8 = bool(np.array_equal(ql, np.asarray(P8[k, ..., :3])))
        res.append(dict(layer=int(k), tau=float(kn[k]), same_rgba16=same16, same_lo_rgba8=same8,
                        max_diff_counts16=int(np.abs(q.astype(np.int64) - np.asarray(P16[k, ..., :3]).astype(np.int64)).max())))
        print(res[-1], flush=True)
    out = dict(package=os.path.relpath(pkg, REPO).replace("\\", "/"), workers_in_generation=L.get("workers"), single_process=True, layers_checked=res,
               all_same=all(r["same_rgba16"] and r["same_lo_rgba8"] for r in res), seconds=round(time.time() - t0, 1),
               note_ja="生成は複数のプロセスで節点を評価し、ここでは 1 つのプロセスで同じ層を作り直した。バイトが同じなら、プロセスの数・順によらず決定的")
    with open(os.path.join(pkg, "determinism_check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("all_same", out["all_same"])


if __name__ == "__main__":
    main()
