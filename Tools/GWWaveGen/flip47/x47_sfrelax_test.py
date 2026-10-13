# -*- coding: utf-8 -*-
"""FLIP47：周期の波の場面（Houdini/FLIP47/g47_tank_periodic.hiplc）の入口の帯の VEX（g47_tanklib.VEX_SF の sfwave・sf_setenv）を、
numpy の流れ関数の解（g47_sfwave.eta・vel）と同じ点で比べる（hython。数十秒）。2026-10-13 周期の波の実験の役（Claude）が書いた。
periodic_design_ja.md §7 の 2 の確かめ：帯の中の点（深い所・水面の近く・水面の上）× 時刻で、u・w の差が 1e-6 c、η の差が 1e-6 H 以内。
組の包絡 sf_setenv は、numpy の同じ式（g47_periodic.set_envelope）と 1e-6 以内（点の属性が 32 ビットのため。初めの 1e-9 から直した）。
場面は読むだけ（保存しない）。書く物：Unity/Build/FLIP47/periodic/sfrelax_test_vex.json（hython の段）・sfrelax_test.json（比べた結果）。
使い方：hython x47_sfrelax_test.py          （VEX の値を書く。hython には scipy がないので比べない）
      py -3.10 -B x47_sfrelax_test.py --compare （g47_sfwave と比べて合否を書く）
"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
import g47_common as GC
COMPARE = "--compare" in sys.argv[1:]
if not COMPARE:
    import hou
    import g47_tanklib as L

HIP = GC.REPO + "/Houdini/FLIP47/g47_tank_periodic.hiplc"
OUT = GC.B47 + "/periodic/sfrelax_test.json"
RAW = GC.B47 + "/periodic/sfrelax_test_vex.json"     # hython の段の生の値
D = json.load(open(GC.B47 + "/periodic_design.json", encoding="utf8"))
sf = D["runs"]["P1_S2_sf14"]["sf"]
SETS = dict(P=84.0, up=14.0, flat=28.0, down=14.0)

if not COMPARE:
    hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
    ctrl = hou.node("/obj/G47_SETUP/CTRL")
    XP = 432.0
    ctrl.parm("x_p").set(XP)
    ctrl.parm("sf_tab").set(L.sf_tab_string(sf))
    for k, v in (("set_P", SETS["P"]), ("set_up", SETS["up"]), ("set_flat", SETS["flat"]), ("set_down", SETS["down"])):
        ctrl.parm(k).set(v)
    g = hou.node("/obj/G47_SETUP/OUT_SF").geometry()
    tab = {a.name(): g.attribValue(a.name()) for a in g.globalAttribs()}

    xs = [150.0, 250.0, 400.0, 431.9]
    ys = [-18.9, -9.5, -1.0, 0.0, 5.0, 8.0, 12.0]
    ts = [0.0, 3.3, 7.1, 13.9, 50.0, 97.25]
    pts = [(x, y, t) for x in xs for y in ys for t in ts]
    setup = hou.node("/obj/G47_SETUP")
    src = setup.createNode("attribwrangle", "x47_pts")
    src.parm("class").set(0)
    src.parm("snippet").set("\n".join("{ int p = addpoint(0, set(%r, %r, 0.0)); setpointattrib(0, \"tq\", p, %r); }" % (x, y, t) for x, y, t in pts))
    w = setup.createNode("attribwrangle", "x47_eval")
    w.setInput(0, src)
    w.parm("vex_precision").set("64")
    w.parm("snippet").set(L.VEX_HEAD + L.VEX_SF + r'''
    float eta; vector tv;
    sfwave(@P.x, @P.y, f@tq, 1.0, eta, tv);
    f@eta_v = eta; f@u_v = tv.x; f@w_v = tv.y;
    f@env_v = sf_setenv(f@tq);
    ''')
    geo = w.geometry()
    errs = [str(e) for e in w.errors()]
    P = np.array(geo.pointFloatAttribValues("P")).reshape(-1, 3)
    tq = np.array(geo.pointFloatAttribValues("tq"))
    ev = np.array(geo.pointFloatAttribValues("eta_v")); uv = np.array(geo.pointFloatAttribValues("u_v"))
    wv = np.array(geo.pointFloatAttribValues("w_v")); env = np.array(geo.pointFloatAttribValues("env_v"))

    raw = dict(tool="x47_sfrelax_test.py (hython)", hip=HIP, hip_sha256=GC.sha256_file(HIP), table=dict((k, tab[k]) for k in ("sfh", "sfk", "sfc", "sfUb", "sfN")),
               wrangle_errors=errs, x_p=XP, sets=SETS,
               rows=[dict(x=x, y=y, t=t, eta_vex=float(ev[i]), u_vex=float(uv[i]), w_vex=float(wv[i]), env_vex=float(env[i])) for i, (x, y, t) in enumerate(pts)])
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    json.dump(raw, open(RAW, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print("VEX values written", RAW, "sfN", tab.get("sfN"), "errors", errs)
    sys.exit(0)

import g47_sfwave as SF
raw = json.load(open(RAW, encoding="utf8"))
XP = raw["x_p"]; tab = raw["table"]; errs = raw["wrangle_errors"]
s = dict(sf); s["E"] = np.array(sf["E"]); s["B"] = np.array(sf["B"])
rows = []
for r0 in raw["rows"]:
    x, y, t = r0["x"], r0["y"], r0["t"]
    e_ref = float(SF.eta(s, np.array([x - XP]), t)[0])
    yq = min(y, e_ref)
    u_ref, w_ref = SF.vel(s, np.array([x - XP]), np.array([yq]), t)
    tau = t - SETS["P"] * math.floor(t / SETS["P"])
    up, fl, dn = SETS["up"], SETS["flat"], SETS["down"]
    env_ref = (0.5 - 0.5 * math.cos(math.pi * tau / up)) if tau < up else 1.0 if tau < up + fl else         (0.5 + 0.5 * math.cos(math.pi * (tau - up - fl) / dn)) if tau < up + fl + dn else 0.0
    rows.append(dict(r0, eta_np=e_ref, u_np=float(u_ref[0]), w_np=float(w_ref[0]), env_np=env_ref))
HIP = raw["hip"]
c, H = float(sf["c"]), float(sf["H"])
du = max(abs(r["u_vex"] - r["u_np"]) for r in rows) / c
dw = max(abs(r["w_vex"] - r["w_np"]) for r in rows) / c
de = max(abs(r["eta_vex"] - r["eta_np"]) for r in rows) / H
den = max(abs(r["env_vex"] - r["env_np"]) for r in rows)
ok = du <= 1e-6 and dw <= 1e-6 and de <= 1e-6 and den <= 1e-6 and not errs and int(tab.get("sfN", -1)) == len(sf["B"])
res = dict(tool="x47_sfrelax_test.py", hip=HIP, hip_sha256=raw["hip_sha256"], n_points=len(rows), table=dict((k, tab[k]) for k in ("sfh", "sfk", "sfc", "sfUb", "sfN")),
           max_rel_err=dict(u_over_c=du, w_over_c=dw, eta_over_H=de, envelope_abs=den), band=dict(vel=1e-6, eta=1e-6, env=1e-6),
           band_note_ja="包絡の帯は初め 1e-9 にしたが、試しの点の t と結果は 32 ビットの点の属性に入る（相対 6e-8 の丸め）ので 1e-6 にした（2026-10-13）",
           passed=bool(ok), wrangle_errors=errs, rows=rows,
           note_ja="VEX（64 ビット）と numpy の同じ式。水面より上（y > η）の点は、どちらも水面の値（Y = min(y, η) + h）")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
print("sfN", tab.get("sfN"), "max rel err u %.2e w %.2e eta %.2e env %.2e" % (du, dw, de, den), "PASS" if ok else "FAIL", errs)
