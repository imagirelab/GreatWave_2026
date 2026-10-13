# -*- coding: utf-8 -*-
"""FLIP45：入口の利得を煙の試しの結果だけから決めて書く（py -3.10。計画 plan_ja.md §4.1、見直し H3）。
計画の式：G(dp, θ_j) = 1 / {r0(dp) · r(θ_j) / r0(0.5)}（r0 は S2b の 2D の板、r(θ) は S2a の 4 点）を横の形ごとに表へ入れ、全部の帯に掛ける。
2026-10-12 の S2a で、横の帯の近く（(72, 66) m）の振幅は目標の 0.99〜1.00 倍、入口の帯から来る所（y 0・18 m）は 0.78〜0.93 倍と分かれ、
4 点の差 0.151（幅 0.05）・角の点 +18 %（幅 ±5 %）で外れた【測った】。横の帯は波の進む向きに長く寄せ続けるので目標に近く、足りないのは
入口の帯から出る波だけと読める【考え】。計画の式で全部の帯に掛けると、横の帯から来る成分（焦点へ急な角で来る成分）を 1/r(θ) 倍まで上げすぎる。
そこで「計画から変えた所」として、利得は入口の帯だけに掛ける（method inlet_band_scalar：in_gain(dp) = 1 / r0(dp)、横の帯は 1）。
r0(dp) は S2b（x 252 m の板、跳ね返りの混じらない窓）。S2b が判定（0.85 ≤ r0 ≤ 1.05、2 点の差 ≤ 0.02）を外れた粒子があれば決めない。
S2a の値は記録（diagnostics）として一緒に書く。この後は変えない。すでに gain45.json がある時は上書きしない（変える時は利用者に伺う）。
使い方：py -3.10 x45_gain.py   → Unity/Build/FLIP45/gain/gain45.json
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

R = json.load(open(GC.B45 + "/smoke/smoke_results.json", encoding="utf8"))
s2b = R.get("S2b") or {}
problems = []
r0 = {}
for dp in GC.PLAN_DP:
    o = s2b.get(repr(dp))
    if not o:
        problems.append("S2b（x 252 m）の粒子 %s m の結果がない" % dp); continue
    if not o.get("pass"):
        problems.append("S2b の粒子 %s m が判定を外れた（r0 %.4f、2 点の差 %.4f）" % (dp, o["r0"], o["spread"]))
    r0[repr(dp)] = float(o["r0"])
if problems:
    print("利得を決めない：\n  " + "\n  ".join(problems))
    sys.exit(2)
out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), method="inlet_band_scalar",
           in_gain={k: 1.0 / v for k, v in r0.items()}, sd_gain=1.0, r0=r0,
           formula_ja="入口の帯の目標だけに in_gain(dp) = 1 / r0(dp) を掛ける（g45_tanklib の bandgain、CTRL の in_gain）。横の帯は 1。表には利得を入れない",
           plan_formula_not_used_ja="計画の式 G(dp, θ) = 1 / {r0(dp) · r(θ) / r0(0.5)} を全部の帯に掛ける形は使わない（S2a で横の帯の近くは目標の 1.0 倍、"
                                    "入口の帯から来る所だけが足りなかったため）",
           diagnostics=dict(S2a_plan_window=R.get("S2a"), S2a_late_window=R.get("S2a_late_window_35_45p5"),
                            S2b_first_x180=R.get("S2b_x180_first")),
           sources=dict(smoke_results=GC.B45 + "/smoke/smoke_results.json", sha256=GC.sha256_file(GC.B45 + "/smoke/smoke_results.json")),
           note_ja="煙の試し S2b（と記録の S2a）だけから決めた（計画 §4.1 の決め方を、利得を掛ける帯だけ変えた。record_ja.md の計画から変えた所 C3）。"
                   "S2c と S4 はこの利得で行う。この後は変えない")
os.makedirs(os.path.dirname(GC.GAIN_FILE), exist_ok=True)
if os.path.exists(GC.GAIN_FILE):
    print("gain45.json はすでにある（上書きしない）：", GC.GAIN_FILE)
    sys.exit(3)
json.dump(out, open(GC.GAIN_FILE, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps(dict((k, v) for k, v in out.items() if k != "diagnostics"), ensure_ascii=False, indent=1))
