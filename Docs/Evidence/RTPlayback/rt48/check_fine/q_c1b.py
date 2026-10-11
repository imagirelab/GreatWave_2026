# -*- coding: utf-8 -*-
"""Independent check of RT48 C1(b): R3e hf eta / sec sdf vs every R3 record holding the same frame, byte for byte.
Written from scratch for the independent check (does not import project tools)."""
import glob, os, json, re, hashlib
import numpy as np
R3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
RE = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/rerun/R3e"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "q_c1b.json")

def index(folder, pat, key):
    idx = {}
    for fn in sorted(glob.glob(os.path.join(folder, pat))):
        z = np.load(fn)
        fr = z["frames"]
        for i, f in enumerate(fr):
            idx.setdefault(int(f), []).append((fn, i))
    return idx

res = {}
for kind, pat, key in (("hf", "hf_c*.npz", "eta"), ("sec", "sec_c*_b*.npz", "sdf")):
    ir3 = index(R3, pat, key); ire = index(RE, pat, key)
    cache = {}
    def get(fn):
        if fn not in cache:
            if len(cache) > 6: cache.clear()
            cache[fn] = np.load(fn)[key]
        return cache[fn]
    frames = sorted(ire)
    ncmp = 0; nbad = 0; bad = []; missing = []; internal_bad = []; nan_frames = 0
    ncmp_unique = 0
    for f in frames:
        if f not in ir3:
            missing.append(f); continue
        re_list = ire[f]
        # R3e internal duplicates
        b0 = get(re_list[0][0])[re_list[0][1]].tobytes()
        for fn, i in re_list[1:]:
            if get(fn)[i].tobytes() != b0: internal_bad.append(f)
        if np.isnan(get(re_list[0][0])[re_list[0][1]].astype(np.float32)).any(): nan_frames += 1
        for fr, ir in ir3[f]:
            br = get(fr)[ir].tobytes()
            ncmp_unique += 1
            for fn, i in re_list:
                ncmp += 1
                if get(fn)[i].tobytes() != br:
                    nbad += 1; bad.append([f, os.path.basename(fr), os.path.basename(fn)])
    res[kind] = dict(n_frames_rerun=len(frames), first=frames[0], last=frames[-1], missing_in_r3=missing,
                     comparisons_all_instances=ncmp, comparisons_unique_frame_x_r3record=ncmp_unique,
                     n_bad=nbad, bad_first=bad[:10], rerun_internal_bad=internal_bad, frames_with_nan=nan_frames,
                     n_r3_records_per_frame=dict(zip(*np.unique([len(ir3.get(f, [])) for f in frames], return_counts=True))) )
    res[kind]["n_r3_records_per_frame"] = {int(k): int(v) for k, v in res[kind]["n_r3_records_per_frame"].items()}
    print(kind, json.dumps(res[kind]))
res["pass"] = all(res[k]["n_bad"] == 0 and not res[k]["missing_in_r3"] and res[k]["n_frames_rerun"] == 571 for k in ("hf", "sec"))
json.dump(res, open(OUT, "w"), indent=1)
print("pass", res["pass"])
