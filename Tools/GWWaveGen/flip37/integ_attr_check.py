# -*- coding: utf-8 -*-
"""組み込みの準備：変換した網目の AS05 の頂点の属性が、約束（Unity/Build/Polish/sample04/mat/README.md の 3 節）に合うかを測る。
- 値がどれも有限か。F・u・w・hrow・λ・whiteSD・whiteOn の範囲。
- u・w の面の上の勾配（格子の差分で：|∇u| は列の向き、|∇w| は行の向き）の p10〜p90 が 1/3〜3 の中か（見本03 の T1 の規則）。
- 隣の頂点の間の跳び（u・w・whiteSD・q）：帯と白が切れる所がないか。
方法 A（sheet）だけ。使い方：py -3.10 integ_attr_check.py <seq>
出力：Unity/Build/FLIP37/integration_prep/<seq>/attr_check.json
"""
import os, sys, json, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C


def load_bin(path, n, m):
    b = np.fromfile(path, dtype=np.float32, count=n * 22)
    o = 0
    out = {}
    for name, k in (("position", 3), ("normal", 3), ("uv3", 4), ("uv4", 4), ("uv5", 4), ("uv6", 4)):
        out[name] = b[o:o + n * k].reshape(n, k); o += n * k
    return out


def main():
    seq = sys.argv[1]
    idx = json.load(open(C.OUT + "/pkg/%s/sheet/index.json" % seq, encoding="utf8"))
    frs = idx["frames"]
    pick = [frs[0], frs[len(frs) // 2], frs[-1]]
    res = []
    for fr in pick:
        ch = load_bin(C.OUT + "/pkg/%s/sheet/%s" % (seq, fr["bin"]), fr["vertices"], fr["triangles"])
        P = ch["position"].reshape(C.NV, C.NU, 3).astype(np.float64)
        F, hrel, u, w = [ch["uv3"][:, k].reshape(C.NV, C.NU) for k in range(4)]
        gq, hrow, Lq, q = [ch["uv4"][:, k].reshape(C.NV, C.NU) for k in range(4)]
        wsd = ch["uv5"][:, 2].reshape(C.NV, C.NU)
        lam = ch["uv6"][:, 2].reshape(C.NV, C.NU); won = ch["uv6"][:, 3].reshape(C.NV, C.NU)
        dPj = np.linalg.norm(np.diff(P, axis=1), axis=-1); dPr = np.linalg.norm(np.diff(P, axis=0), axis=-1)
        gu = np.abs(np.diff(u, axis=1)) / np.maximum(dPj, 1e-6)
        gw = np.abs(np.diff(w, axis=0)) / np.maximum(dPr, 1e-6)
        face = (F[:, :-1] > 2.0) & (F[:, :-1] < 4.0)   # 前の面（頂 → 前の谷）
        faceR = (F[:-1, :] > 2.0) & (F[:-1, :] < 4.0)
        def pr(a):
            a = a[np.isfinite(a)]
            return [float(np.percentile(a, 10)), float(np.percentile(a, 50)), float(np.percentile(a, 90))] if len(a) else None
        rec = {"t": fr["t"], "finite": bool(all(np.isfinite(ch[k]).all() for k in ch)),
               "F_range": [float(F.min()), float(F.max())], "u_range": [float(u.min()), float(u.max())],
               "w_range": [float(w.min()), float(w.max())], "hrow_range": [float(hrow.min()), float(hrow.max())],
               "lambda_range": [float(lam.min()), float(lam.max())], "whiteSD_range": [float(wsd.min()), float(wsd.max())],
               "white_fraction": float((wsd > 0).mean()), "whiteOn_fraction": float((won > 0.5).mean()),
               "grad_u_front_p10_50_90": pr(gu[face]), "grad_w_front_p10_50_90": pr(gw[faceR]),
               "grad_in_1_3_to_3": bool(pr(gu[face]) and pr(gw[faceR]) and pr(gu[face])[0] >= 1 / 3 and pr(gu[face])[2] <= 3 and pr(gw[faceR])[0] >= 1 / 3 and pr(gw[faceR])[2] <= 3),
               "neighbour_jump_max": {"u_m": float(np.abs(np.diff(u, axis=1)).max()), "w_m": float(np.abs(np.diff(w, axis=0)).max()),
                                      "whiteSD_cols_m": float(np.abs(np.diff(wsd, axis=1)).max()), "whiteSD_rows_m": float(np.abs(np.diff(wsd, axis=0)).max()),
                                      "q_rows": float(np.abs(np.diff(q, axis=0)).max()), "q_cols": float(np.abs(np.diff(q, axis=1)).max())},
               "edge_len_m": {"cols_p50": float(np.median(dPj)), "cols_max": float(dPj.max()), "rows_p50": float(np.median(dPr)), "rows_max": float(dPr.max())}}
        res.append(rec)
    out = {"seq": seq, "frames": res, "contract": "Unity/Build/Polish/sample04/mat/README.md の 3 節（静止のメッシュの道 _AS03Src = 1）"}
    json.dump(out, open(C.OUT + "/%s/attr_check.json" % seq, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
