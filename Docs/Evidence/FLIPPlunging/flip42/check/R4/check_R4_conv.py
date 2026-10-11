# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：R2（0.35 m）→ R3（0.25 m）→ R4（0.1767578125 m）の並びが近づいているかの数（自前）。
check_R4_geom.json を読む。細かさの比 r21 = 0.35/0.25 = 1.40、r32 = 0.25/0.1767578125 = 1.414。
見かけの次数 p は |差(R2→R3)| / |差(R3→R4)| = r^p から（r は 2 つの比の平均 1.407 とした）。並びが単調で p > 0 の時だけ、
リチャードソンの外挿 φ_∞ ≈ φ_R4 + (φ_R4 − φ_R3)/(r^p − 1) を出す。3 点だけなので目安【計算・考え】。
加えて、最大の頂（60 s から、造波板から 0〜930 m）を一番上の水面の高さ（真ん中の節）で読み直す。
py -3.10 check_R4_conv.py → check_R4_conv.json
"""
import os, json, math
import numpy as np
from ck_common import cfg, load_hf, still_level

OUTDIR = os.path.dirname(os.path.abspath(__file__))


def main():
    g = json.load(open(os.path.join(OUTDIR, "check_R4_geom.json"), encoding="utf-8"))
    ev = {r: g[r]["events"] for r in ("R2", "R3", "R4d")}
    q = {
        "onset_t": lambda e: e["onset"]["t"],
        "onset_x": lambda e: e["onset"]["x_vertical"],
        "eta_c": lambda e: e["onset"]["eta_c"],
        "H_front_rule": lambda e: e["onset"]["H"],
        "H_rear": lambda e: e["onset"]["H_rear"],
        "steep": lambda e: e["onset"]["steep"],
        "jet_time": lambda e: e["jet_time"],
        "jet_dist": lambda e: e["jet_dist"],
        "touch_t": lambda e: e["touchdown"]["t"],
        "touch_x": lambda e: e["touchdown"]["x"],
        "air_max": lambda e: (e.get("air_max_to_onset+3.6") or {}).get("area", 0.0),
    }
    r = (0.35 / 0.25 + 0.25 / 0.1767578125) / 2
    out = dict(r=r)
    for nm, fn in q.items():
        v = [fn(ev["R2"]), fn(ev["R3"]), fn(ev["R4d"])]
        d1 = v[1] - v[0]; d2 = v[2] - v[1]
        row = dict(R2=v[0], R3=v[1], R4=v[2], d21=d1, d32=d2)
        if d1 * d2 > 0 and abs(d2) < abs(d1):
            p = math.log(abs(d1) / abs(d2)) / math.log(r)
            ext = v[2] + d2 / (r ** p - 1)
            row.update(p=p, extrap=ext, R4_rel_to_extrap=(v[2] - ext) / ext, R3_rel_to_extrap=(v[1] - ext) / ext)
        else:
            row.update(p=None, note="単調に近づいていない（差の向きが変わるか、差が小さくならない）")
        out[nm] = row
    # 最大の頂（60 s から、0〜930 m）
    mx = {}
    for run in ("R4d", "R3"):
        c = cfg(run); xp = c["parms"]["x_p"]
        hf = load_hf(run)
        off = still_level(hf, xp)
        xr = hf["x"] - xp
        mt = hf["t"] >= 60.0 - 1e-9
        mxr = (xr >= 0) & (xr <= 930)
        A = hf["mid"][np.ix_(mt, mxr)] - off
        i, j = np.unravel_index(np.nanargmax(A), A.shape)
        mx[run] = dict(eta=float(A[i, j]), t=float(hf["t"][mt][i]), x=float(xr[mxr][j]))
    out["overall_max_crest"] = mx
    json.dump(out, open(os.path.join(OUTDIR, "check_R4_conv.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, json.dumps(v, ensure_ascii=False, default=float) if not isinstance(v, float) else v)


if __name__ == "__main__":
    main()
