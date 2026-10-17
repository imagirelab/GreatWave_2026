# -*- coding: utf-8 -*-
"""FLIP51 crossing screen, sweep C (2026-10-17, Claude): candidate lobes at T 7 s for the coarse FLIP setups (numpy only)."""
import sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import c51_screen as C
t0 = time.time()
cases = []
for (th0, dl, nl, xf) in ((60.0, 15.0, 11, 190.25), (60.0, 20.0, 11, 190.25), (55.0, 15.0, 11, 190.25), (50.0, 15.0, 11, 190.25),
                          (65.0, 15.0, 11, 190.25), (60.0, 15.0, 11, 150.25), (60.0, 15.0, 11, 220.25)):
    cases.append(C.run_case(7.0, "lobes", th0, dl, nl, xf, [0.40, 0.50, 0.55]))
json.dump(dict(cases=cases, cpu_s=time.time() - t0), open(C.OUT + "/screen_C.json", "w", encoding="utf8"), indent=1, default=float)
for c in cases:
    for r in c["rows"]:
        o = r["o2"]
        print("th0 %4.0f dl %4.0f xf %6.2f h_f %4.1f eps %.2f a_sum %.2f | Hc %5.2f kHc %.2f | W20 %5.2f W50 %5.2f(%4.1fm) W80 %4.2f W95 %4.2f K %4.2f S1 %4.2f S2 %5.2f ring %4.2f Lx50 %5.2f A50 %4.2f miss %4.2f | gin %.2f cin %.2f kAband %.2f ap %.2f"
              % (c["theta0"], c["delta"], c["x_f"], c["h_f"], r["eps"], r["a_sum"], o["Hc"], o["kHc"], o["W20"], o["W50"], o["W50_m"], o["W80"], o["W95"], o["K"],
                 o.get("S1", float("nan")), o["S2"], o.get("ring_max", float("nan")), o["Lx50"], o["A50"], o["target_miss"], r["gain_over_incoming"], r["c_in_x110"], r["k_inlet_band_max"], c["aperture"]))
print("cpu %.1f s" % (time.time() - t0))
