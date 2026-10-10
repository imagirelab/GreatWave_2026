# -*- coding: utf-8 -*-
"""FLIP42：粒子の帯の判定 N1・N2（計画 §5 (b)）。帯 4 m の計算と帯なしの計算の ana.json を比べる。
py -3.10 g_compare.py <帯ありの run_id> <帯なしの run_id> <out.json>
N1：帯の出口・kc(x − xb) = −20・−10 の点で、深い谷 3 つの深さの平均の差が、その点の線形の波高（一点の時系列で隣り合う頂と谷の差の最大）の 5 % 以内。
N2：それぞれの計算の「最も険しくなった時刻」（巻き始めがあればその時刻）の H・η_c が ±5 %、前の面の険しさ（η_c ÷ 頂から前で静かな水面を切る点までの距離）が ±10 %。
    比べの基準は帯なしの計算（帯の働きがない方）。
どれかが幅を越えたら、以後の計算（R3・R5'・R4）は帯なし。
"""
import sys, os, json
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A


def main(rb, rn, outp):
    P = A.plan()
    a = json.load(open(os.path.join(A.ROOT, rb, "ana.json"), encoding="utf8"))
    b = json.load(open(os.path.join(A.ROOT, rn, "ana.json"), encoding="utf8"))
    N1 = []
    for g in ("band_exit", "kc(x-xb)=-20", "kc(x-xb)=-10"):
        Hl = P["gauges"][g]["H_lin_adjacent_max"]
        ta = a["gauges"][g]["troughs3_mean"]; tb = b["gauges"][g]["troughs3_mean"]
        tol = 0.05 * Hl
        N1.append(dict(gauge=g, x_rel=P["gauges"][g]["x_rel"], band=ta, noband=tb, diff=ta - tb, tol=tol, ok=bool(abs(ta - tb) <= tol),
                       band_troughs=a["gauges"][g]["troughs3"], noband_troughs=b["gauges"][g]["troughs3"], lin_troughs=P["gauges"][g]["deepest_troughs_lin"]))
    ra = a["N2_time"]["row"]; rb_ = b["N2_time"]["row"]
    N2 = dict(band_by=a["N2_time"]["by"], noband_by=b["N2_time"]["by"], band=ra, noband=rb_)
    chk = {}
    for q, tol in (("H", 0.05), ("eta_c", 0.05), ("steep", 0.10)):
        va, vb = ra.get(q), rb_.get(q)
        rel = (va - vb) / vb if (va is not None and vb not in (None, 0)) else None
        chk[q] = dict(band=va, noband=vb, rel=rel, tol=tol, ok=bool(rel is not None and abs(rel) <= tol))
    N2["check"] = chk
    n1ok = all(r["ok"] for r in N1); n2ok = all(c["ok"] for c in chk.values())
    out = dict(band_run=rb, noband_run=rn, N1=N1, N1_ok=n1ok, N2=N2, N2_ok=n2ok,
               decision="band4m" if (n1ok and n2ok) else "noband",
               decision_ja="帯 4 m を使う" if (n1ok and n2ok) else "以後の計算（R3・R5'・R4）は帯なし")
    json.dump(out, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(N1=[(r["gauge"], round(r["band"], 3), round(r["noband"], 3), round(r["diff"], 3), round(r["tol"], 3), r["ok"]) for r in N1],
                          N2={k: (v["band"], v["noband"], v["rel"], v["ok"]) for k, v in chk.items()}, decision=out["decision"]), ensure_ascii=False, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
