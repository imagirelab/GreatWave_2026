# -*- coding: utf-8 -*-
"""仕上げ27：生成器（ds28r01f）の抜き取りの再現の確かめ（記録）。ds28r01f_determinism.py と同じ式で、パッケージの節点の層を 1 つのプロセスで
作り直し、16 bit と精度の層のバイトが同じかを比べる。違いは 2 つ：
  --off：生成の記録の off の代わりに、切る名前を渡す（仕上げ27 で足した balance_swell_calm・sea_sample_range を切って F_final を再現できるか）。
         ［仕上げ27 の修正 1 回目］--off を渡さない時は、ds28r01f_determinism.py と同じく、記録の off に記録の f_on に無い F の名前を足して切る
         （ds28r01f_pkglog.package_off。F_final ではこの 2 つが切りになる）。
  --out：結果を書く場所（パッケージのフォルダーに書かない。F_final の determinism_check.json を上書きしないため）。
層は既定で、最初・τ −4 s・τ −2 s・τ −1.5 s・最後（仕上げ27 の直しが効く区間を含める）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_repro_check.py --package Unity/Build/Design/28R01F/F_final/art_on \
      --off balance_swell_calm,sea_sample_range --out Unity/Build/Polish/27/repro/repro_F_final_off.json
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_repro_check.py --package Unity/Build/Polish/27/F_p27/art_on --out Unity/Build/Polish/27/repro/repro_F_p27.json
"""
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FDIR = os.path.abspath(os.path.join(HERE, "..", "ds28r01f"))
if FDIR not in sys.path:
    sys.path.insert(0, FDIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--off", default=None)
    ap.add_argument("--out", required=True)
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
    import ds28r01f_pkglog as PL
    off = [s for s in a.off.split(",") if s] if a.off is not None else PL.package_off(L)
    GEN._winit(os.path.join(REPO, L["kstar"]["dir"]), L.get("overrides"), off)
    GEN._ensure(stage)
    kn = np.asarray(J["knot_tau"], float)
    nl, nv, nu = int(J["layers"]), int(J["rows"]), int(J["cols"])
    pick = sorted({0, int(np.argmin(np.abs(kn + 4.0))), int(np.argmin(np.abs(kn + 2.0))), int(np.argmin(np.abs(kn + 1.5))), nl - 1})
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
    out = dict(package=os.path.relpath(pkg, REPO).replace("\\", "/"), off=off, generator_variant=GEN._G.variant, f_on=GEN._G.f_on,
               layers_checked=res, all_same=all(r["same_rgba16"] and r["same_lo_rgba8"] for r in res), seconds=round(time.time() - t0, 1),
               note_ja="抜き取り（5 層）。全層のバイトの一致は確かめていない")
    op = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("all_same", out["all_same"])


if __name__ == "__main__":
    main()
