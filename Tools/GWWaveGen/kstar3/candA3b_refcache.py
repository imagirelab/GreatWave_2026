# -*- coding: utf-8 -*-
"""Q21 candidate A3b (loop 3): TEMPORARY cache of the reference model placed by align_B_upright (Unity world).

The reference model (G:/research/model/wave_repair_zbrush2.obj, SHA-256 AB4124F9...3D40) is a scan of someone else's
exhibited sculpture.  It is read only here (numpy OBJ parser, SHA checked) to build a temporary cache in the git-ignored
Build folder (Unity/Build/Q20L3/candA3b/_tmp).  The cache and everything derived from the mesh are deleted at the end
(SHA-256 recorded in deleted_caches_sha256.txt).  Nothing of the model's mesh goes into the repo.

usage: py -3.10 candA3b_refcache.py <out_cache.npz>
"""
import sys, os, json, hashlib, time
import numpy as np

SRC = r"G:\research\model\wave_repair_zbrush2.obj"
AL = r"G:\Unity\GreatWave_2026_Fresh\Docs\Evidence\ArtFirst\26\reference\align_B_upright.json"


def main(out):
    t0 = time.time()
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    assert h.startswith("AB4124F9") and h.endswith("3D40"), h
    lines = raw.split(b"\n")
    V = np.array([l.split()[1:4] for l in lines if l.startswith(b"v ")], dtype=np.float64)
    tris, quads = [], []
    for l in lines:
        if not l.startswith(b"f "):
            continue
        p = [int(x.split(b"/")[0]) - 1 for x in l.split()[1:]]
        if len(p) == 3:
            tris.append(p)
        elif len(p) == 4:
            quads.append(p)
        else:
            for j in range(1, len(p) - 1):
                tris.append([p[0], p[j], p[j + 1]])
    Q = np.array(quads, np.int64).reshape(-1, 4)
    T = np.array(tris, np.int64).reshape(-1, 3)
    F = np.vstack([T, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
    M4 = np.array(json.load(open(AL, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    det = float(np.linalg.det(M4[:3, :3]))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, V=Vu.astype(np.float32), tris=F, det=det)
    print("sha", h, "V", len(V), "F", len(F), "det", det, "bbox", Vu.min(0), Vu.max(0), "%.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1])
