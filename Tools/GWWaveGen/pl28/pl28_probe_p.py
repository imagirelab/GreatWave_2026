# -*- coding: utf-8 -*-
"""仕上げ28：ds28p の 2 つの美術の誘導（ds_upper_back_aspect・ds_far_hook_earlier）を、包みを作らずに 1 つのプロセスで試す。
G_final（試行F の当て直し）と同じ生成の段階のファイル（num_no_rebound_after_apex の格子・small_lip_body・橋渡し）を読み込み、
値を切った形（= G_final と同じ式）と入れた形を同じ時刻で比べる。
数えるもの：側面の包絡の塊（pl28_loaf.loaf_metrics）、主断面・峰の行と本体の行（唇ができる前）の頂の ±2 m 弦角、
背の上の列の波の枠の中の横の往復（0.1 s ごと、τ −6〜0。背が後ろへ引かれて戻る「引き戻し」の検出）、切った形との頂点の差の最大（P20）。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_probe_p.py --package Unity/Build/Polish/28/G_final/art_on --variants "off;a=0.8;a=0.8,hook=-4.2/-1.4" --out <json>
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c", "ds28r01d", "ds28r01e", "ds28r01f", "ds28p"):
    sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", sub))
sys.path.insert(0, HERE)
import pl28_loaf as LF  # noqa: E402
import pl28_fr_motion_lib as FM  # noqa: E402

LOAF_TAUS = [-3.894, -3.49, -3.2, -2.95, -2.7, -2.45]
CHORD_TAUS = [-2.95, -2.7, -2.45, -2.3, -2.2, -2.1, -2.0, -1.95]


def build(pkg):
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    import ds28r01f_pkglog as PL
    import ds28p_model as MP
    L = json.load(open(os.path.join(pkg, "ds28r01f_generate_log.json"), encoding="utf-8"))["result"]
    work = os.path.join(pkg, "_work")
    sl = (L.get("scan") or {}).get("small_lip_body") or {}
    g = MP.Generator(kstar_dir=os.path.join(REPO, L["kstar"]["dir"]), f_overrides=L.get("overrides") or None, off=PL.package_off(L),
                     defer_no_rebound=True)
    if sl.get("rows"):
        g.apply_delip(tuple(sl["rows"]))
    nr = os.path.join(work, "nr_cache_small_lip.npz") if sl.get("rows") else os.path.join(work, "nr_cache.npz")
    g.load_no_rebound(nr)
    gw = os.path.join(work, "guard_window.npz")
    g.set_guard_window(gw if os.path.isfile(gw) else None)
    br = os.path.join(work, "bridge.npz")
    if os.path.isfile(br):
        g.set_bridge(br)
    g.set_layers(**g.f_on)
    return g, L


def set_variant(g, spec):
    g.p_on = {"upper_back_aspect": False, "far_hook_earlier": False}
    if spec == "off":
        return
    for part in spec.split(","):
        k, v = part.split("=")
        if k == "k":
            g.p_on["upper_back_aspect"] = True
            g.RP["upper_back_aspect"]["k"] = float(v)
        elif k == "eta0":
            g.RP["upper_back_aspect"]["eta0"] = float(v)
        elif k == "hook":
            s0, s1 = [float(x) for x in v.split("/")]
            g.p_on["far_hook_earlier"] = True
            g.RP["far_hook_earlier"]["sigma_start"], g.RP["far_hook_earlier"]["sigma_end"] = s0, s1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--variants", default="off;a=0.8")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    pkg = a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package)
    g, L = build(pkg)
    T = np.asarray(g.K.src["meta"]["frame"]["t_travel"], float)
    X0 = g.local(0.0)
    a0 = X0[164] @ T
    sign = 1.0 if a0[200] > a0[int(np.argmax(X0[164, 18:394, 1])) + 18] else -1.0
    res = dict(package=os.path.relpath(pkg, REPO).replace("\\", "/"), sign=sign, p_info=g.p_info, variants={})
    rev_taus = np.round(np.arange(-6.0, 1e-9, 0.1), 4)
    base_X = {}
    for spec in a.variants.split(";"):
        set_variant(g, spec)
        out = dict(loaf={}, chord={}, p20_max_m=0.0)
        for tau in sorted(set(LOAF_TAUS + CHORD_TAUS + [0.0])):
            X = g.local(tau)
            if spec == "off":
                base_X[tau] = X
            elif tau in base_X:
                out["p20_max_m"] = max(out["p20_max_m"], float(np.linalg.norm(X - base_X[tau], axis=-1).max()))
            A = (X @ T) * sign
            Y = X[..., 1]
            if tau in LOAF_TAUS or tau == 0.0:
                out["loaf"]["%+.3f" % tau] = LF.loaf_metrics(X, T, sign)
            if tau in CHORD_TAUS or tau == 0.0:
                ch = np.asarray(FM.crest_chord(A, Y), float)
                lo = np.array([FM.lo_ratio(A, Y, r, 1.0) for r in range(A.shape[0])])
                H = Y[:, 18:395].max(1)
                body = (H > 3.0) & (lo < 0.05) & np.isfinite(ch)
                out["chord"]["%+.3f" % tau] = dict(main=round(float(ch[164]), 1), peak=round(float(ch[183]), 1),
                                                    body_min=round(float(ch[body].min()), 1) if body.any() else None,
                                                    argmin=int(np.nonzero(body)[0][np.argmin(ch[body])]) if body.any() else None,
                                                    rows_le110=int((body & (ch <= 110)).sum()), rows_le125=int((body & (ch <= 125)).sum()))
        # 背の上の列の横の往復（波の枠。頂の横の位置からの距離 d = a_頂 − a_列 の時間の往復）
        rows = list(range(100, 211, 10))
        D = []
        for tau in rev_taus:
            X = g.local(float(tau))
            A = (X @ T) * sign
            Y = X[..., 1]
            dd = []
            for r in rows:
                root = int(g.root[r])
                jc = 18 + int(np.argmax(Y[r, 18:root + 1]))
                dd.append(A[r, jc] - A[r, 18:root + 1][::6][:30])
            D.append(dd)
        rev = 0
        worst = 0.0
        for i, r in enumerate(rows):
            M = np.array([D[k][i][:min(len(x[i]) for x in D)] for k in range(len(rev_taus))])   # (時刻, 列)
            dM = np.diff(M, axis=0)
            for j in range(M.shape[1]):
                s = dM[:, j]
                # 往復：増えてから減る（または逆）で、戻りの量が 0.1 m を超える
                cum_up = np.maximum.accumulate(M[:, j]) - M[:, j]
                cum_dn = M[:, j] - np.minimum.accumulate(M[:, j])
                w = float(min(cum_up.max(), cum_dn.max()))
                if w > 0.1:
                    rev += 1
                worst = max(worst, w)
        out["back_reversal_cols_gt_0p1m"] = rev
        out["back_reversal_worst_m"] = round(worst, 3)
        res["variants"][spec] = out
        print(spec, json.dumps({k: v for k, v in out.items() if k != "loaf"}, ensure_ascii=False)[:900], flush=True)
        print("   loaf", {k: (v["loaf_index"], v["plateau_95_over_H"], v["back_run_80_m"]) for k, v in out["loaf"].items()}, flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    op = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
