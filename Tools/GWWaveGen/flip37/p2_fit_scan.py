# -*- coding: utf-8 -*-
"""参考だけ：原画カメラから見たシルエットの合い方を、置き方の倍率 s と向き ψ を広げて調べる（py -3.10）。
使い方: py -3.10 p2_fit_scan.py <run_dir> [frame]
既定のコマは analysis.json の best。s = 0.4〜1.1（指示の倍率は 0.9〜1.1。小さい s は「原画の波を頂 20 m より小さく読む」ことにあたる）、
ψ = 0〜80°。カメラが水の中になる置き方は飛ばす。出力：<run_dir>/fit_scan.json（合否に使わない）。
"""
import sys, os, json, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_common as C  # noqa: E402
import p2_analyze as A2  # noqa: E402

rd = sys.argv[1]
an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
best = an["best"]
fr = int(sys.argv[2]) if len(sys.argv) > 2 else best["frame"]
hf = A2.load_hf(rd)
k = int(np.argmin(np.abs(hf["frames"] - fr)))
cp, cx = A2.crest_profile(hf, k)
iz = int(np.argmax(cp))
anchor = (float(cx[iz]), float(cp[iz]), float(hf["zs"][iz]))
Pm, tri, t = C.load_mesh_full(os.path.join(rd, "mesh", "mesh_%04d.npz" % fr), *C.run_mirror(rd))
keep = (Pm[:, 0] > anchor[0] - 160) & (Pm[:, 0] < anchor[0] + 90)
tk = tri[keep[tri].all(1)]
SC = 0.5
cam = C.painting_cam(SC)
pm, outer, inner = C.painting_mask(SC)
win = C.window_mask(SC)
ek = hf["eta"][k]
rows = []
for s in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1):
    for psi in (0, 10, 20, 30, 40, 50, 60, 70, 80):
        U, O = C.place(Pm, anchor, psi, s, cam)
        Tv, Ev = C.TE(psi)
        Qc = (cam.pos - O) / s
        xc_, zc_ = Qc @ Tv + anchor[0], Qc @ Ev + anchor[2]
        ix_ = int(np.argmin(np.abs(hf["xs"] - xc_))); iz_ = int(np.argmin(np.abs(hf["zs"] - zc_)))
        inside = (hf["xs"][0] <= xc_ <= hf["xs"][-1]) and (hf["zs"][0] <= zc_ <= hf["zs"][-1])
        eta_cam = float(ek[iz_, ix_]) if inside and np.isfinite(ek[iz_, ix_]) else None
        if eta_cam is not None and eta_cam * s > cam.pos[1] - 1.0:
            rows.append({"s": s, "psi": psi, "skipped": "camera under water"}); continue
        m = C.raster_mask(cam, U, tk) & win
        inter = (m & pm).sum(); uni = (m | (pm & win)).sum()
        od = C.outline_distance(m, outer, inner, SC)
        rows.append({"s": s, "psi": psi, "iou": float(inter / max(uni, 1)), "dist_mean_px": od["mean_px"] if od else None,
                     "recall": float(inter / max((pm & win).sum(), 1)), "outside": float((m & ~pm).sum() / max((win & ~pm).sum(), 1))})
ok = [r for r in rows if "iou" in r]
bi = max(ok, key=lambda r: r["iou"]); bd = min([r for r in ok if r["dist_mean_px"] is not None], key=lambda r: r["dist_mean_px"])
out = {"run_id": an["run_id"], "frame": fr, "t": t, "anchor": anchor, "rows": rows, "best_iou": bi, "best_dist": bd,
       "note": "参考だけ。指示の倍率は 0.9〜1.1（頂 20 m）。s<0.9 は原画の大波を小さく読む置き方で、指示の外"}
json.dump(out, open(os.path.join(rd, "fit_scan.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("best IoU", bi); print("best dist", bd)
for s in (0.5, 0.7, 0.9, 1.0):
    q = [r for r in ok if r["s"] == s]
    if q:
        b = max(q, key=lambda r: r["iou"])
        print("s=%.1f best psi=%d IoU=%.3f dist=%.0f" % (s, b["psi"], b["iou"], b["dist_mean_px"] or -1))
