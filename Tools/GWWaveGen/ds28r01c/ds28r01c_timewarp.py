# -*- coding: utf-8 -*-
"""設計28修正01 試行C：時間曲線 τ(t) を作る（設計27 の ds27_timewarp.py の式、試行B の ds28r01b_timewarp.py の規則のまま）。

既定（規則は変えない）：実時間 → 1 s の S で r0 = 0.5 倍 → 0.5 倍 → 0.4 s の S で止め、t* = 12.0 s で 2 s 保持。0.5 倍へ着くのは、その版の
唇先が最初に頂点に着く τ（巻きの行すべての唇先（K* の唇先の列）の τ ≥ −4 s の最高点の最も早いもの。試行B の earliest_apex をそのまま使う）。
記録のための比べ（規則は変えない。Unity の既定には使わない）：
  --r0 0.7：同じ規則で 0.7 倍（見かけの重力 0.49 g）。
  --anchor-tau <τ>：0.5 倍へ着く τ を固定する（例：V80 の既定の −1.345833 ＝ V80 と同じ画面の時刻の割り付け）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_timewarp.py --variant C1          # → Tools/GWWaveGen/ds28r01c/timewarp_default_C1.json
  py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_timewarp.py --variant C1 --r0 0.7 --out Unity/Build/Design/28R01C/warps/tw_r07_C1.json
  py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_timewarp.py --package Unity/Build/Design/28R01B/V80/art_on --tag V80 --r0 0.7 --out ...
出力の schema は設計27 と同じ GreatWave.DS27.timewarp/1（Unity の再生器は -WarpFile で読む）。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "ds27"), os.path.join(HERE, "..", "ds28r01b")):
    p = os.path.abspath(p)
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_gates as DG  # noqa: E402
import ds27_timewarp as TW  # noqa: E402
import ds28r01b_timewarp as TB  # noqa: E402

REPO = DG.REPO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None)
    ap.add_argument("--package", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--r0", type=float, default=None)
    ap.add_argument("--anchor-tau", type=float, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    R = json.load(open(os.path.join(HERE, "ds28r01c_params.json"), encoding="utf-8"))["timewarp"]
    tag = a.tag or a.variant
    pkdir = a.package or os.path.join("Unity", "Build", "Design", "28R01C", a.variant, "art_on")
    pkdir = pkdir if os.path.isabs(pkdir) else os.path.join(REPO, pkdir)
    if a.anchor_tau is None:
        tau_a, row, info = TB.earliest_apex(pkdir)
        rule = "その版の唇先が最初に頂点に着く τ（巻きの行すべて）"
    else:
        tau_a, row, info = float(a.anchor_tau), None, None
        rule = "固定の τ（記録のための比べ）"
    d1, tf = float(R["d1"]), float(R["tf"])
    r0 = float(R["r0"]) if a.r0 is None else float(a.r0)
    tau_b = -r0 * tf / 2.0
    ta = (TW.T_STAR - tf) - (tau_b - tau_a) / r0
    t1 = ta - d1
    kw = dict(t1=round(t1, 6), d1=d1, r0=r0, tf=tf)
    t = np.round(np.arange(0, int(round(TW.T_END * TW.HZ)) + 1) / TW.HZ, 9)
    tau = TW.tau_default(t, **kw)
    info_all = dict(t1=kw["t1"], d1=d1, r0=r0, tf=tf, hold_s=float(R["hold_s"]), tau_at_t0_default=round(float(tau[0]), 6),
                    slow_reached_t=round(ta, 6), slow_reached_tau=round(tau_a, 6), slow_reached_rule_ja=rule,
                    earliest_apex_row=row, apex_stats=info, tau_at_ramp_start=round(float(np.interp(t1, t, tau)), 6), freeze_start_t=TW.T_STAR - tf,
                    apparent_g_mps2=round(9.81 * r0 ** 2, 4), package=os.path.relpath(pkdir, REPO).replace("\\", "/"),
                    package_pos_sha256=DG.sha256_file(os.path.join(pkdir, "ds27_pos_rgba16.bin")))
    if a.r0 is None and a.anchor_tau is None:
        tid = "default_ds28r01c_%s" % tag
    else:
        tid = "compare_ds28r01c_%s_r0_%g%s" % (tag, r0, "" if a.anchor_tau is None else "_anchor_%g" % a.anchor_tau)
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": tid,
         "note_ja": "設計28修正01 試行C（%s）：実時間 → 1 s で %g 倍（%s τ %.3f s に着く）→ %g 倍 → 0.4 s で止め、t* = 12 s で 2 s 保持"
                    % (tag, r0, rule, tau_a, r0),
         "t_star_s": TW.T_STAR, "hz": TW.HZ, "params": info_all,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    p = a.out or os.path.join(HERE, "timewarp_default_%s.json" % tag)
    p = p if os.path.isabs(p) else os.path.join(REPO, p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    assert abs(float(np.interp(TW.T_STAR, t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    print(json.dumps(dict(file=p, info=info_all), ensure_ascii=False))


if __name__ == "__main__":
    main()
