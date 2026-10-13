# -*- coding: utf-8 -*-
"""FLIP44 煙の試し S3：入口の表の VEX（g44_tanklib.groupwave）を numpy の線形の和と比べる（hython。場面は保存しない。読むだけ）。
計画 plan_ja.md §6 S3：PR1・PR2・RP の表で、帯の中の 5 点の η・u・v を、時刻 0・50・171.5・300・410 s で比べる。
精度は本番の帯の wrangle と同じ 64 ビット。RP は VEX が t mod P を使い、numpy は t のまま（f_n = m_n/P なので同じ値のはず）。
判定：差の最大が、η は Σa の 1e-5 倍以内、u・v は Σ a_i ω_i coth(k_i h) の 1e-5 倍以内。
hython x44_s3_vex.py → Unity/Build/FLIP44/smoke/S3/s3.json
"""
import hou, sys, json, os, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_tanklib as L
import g44_cfg as C

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44/smoke/S3"
os.makedirs(OUT, exist_ok=True)
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP44/g44_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G44_SETUP/CTRL")
P = C.plan()
h = P["tank"]["h0"]; xp = P["tank"]["x_p"]
PTS = [(10.0, -35.0), (40.0, -20.0), (80.0, -5.0), (110.0, 0.0), (135.0, 3.0)]
TIMES = [0.0, 50.0, 171.5, 300.0, 410.0]
G = 9.80665


def numpy_wave(inl, x, y, t):
    fr = np.array(inl["freqs_Hz"]); a = np.array(inl["amps_m"]); ph = np.array(inl["phases_rad"])
    k = C.k_of(fr, h)      # numpy で計算し直す（表の k を使わない）
    om = 2 * np.pi * fr
    th = k * (x - xp) - om * t + ph
    eta = float((a * np.cos(th)).sum())
    ye = min(max(h * (y - eta) / (h + eta), -h), 0.0)
    u = float((a * om * np.cosh(k * (ye + h)) / np.sinh(k * h) * np.cos(th)).sum())
    v = float((a * om * np.sinh(k * (ye + h)) / np.sinh(k * h) * np.sin(th)).sum())
    ref_uv = float((a * om / np.tanh(k * h)).sum())
    return eta, u, v, ref_uv


res = {"note_ja": "S3：入口の表の VEX と numpy の線形の和の比べ（計画 §6）", "tol_rel": 1e-5, "programs": {}}
w = hou.node("/obj/G44_SETUP").createNode("attribwrangle", "s3_check")
w.parm("class").set(0)
w.parm("vex_precision").set("64")
code = L.VEX_HEAD + "\n"
for i, (x, y) in enumerate(PTS):
    for j, t in enumerate(TIMES):
        code += ("{ float e; vector v; groupwave(%r, %r, %r, 1.0, e, v); int p = addpoint(0, set(%r, %r, 0.0)); "
                 "setpointattrib(0, \"eta\", p, e); setpointattrib(0, \"vel\", p, v); setpointattrib(0, \"tt\", p, %r); }\n") % (x, y, t, x, y, t)
w.parm("snippet").set(code)
allok = True
for prog in ("PR1", "PR2", "RPflat", "RPreef"):
    inl = C.inlet_of(P, prog)
    ctrl.parm("inlet_tab").set(L.inlet_tab_string(inl["freqs_Hz"], inl["amps_m"], inl["phases_rad"], inl["k"]))
    ctrl.parm("rep_P").set(inl["rep_P"])
    ctrl.parm("amp_gain").set(1.0)
    ctrl.parm("x_p").set(xp); ctrl.parm("h0").set(h)
    w.cook(force=True)
    g = w.geometry()
    errs = list(w.errors())
    rows = []
    for pt in g.points():
        x, y, _ = pt.position(); t = pt.attribValue("tt")
        e, u, v, ref = numpy_wave(inl, x, y, t)
        ev = pt.attribValue("eta"); vv = pt.attribValue("vel")
        rows.append(dict(x=x, y=y, t=t, vex=[ev, vv[0], vv[1]], numpy=[e, u, v], d_eta=ev - e, d_u=vv[0] - u, d_v=vv[1] - v))
    sa = inl["sum_a"]
    ref_uv = numpy_wave(inl, 0.0, 0.0, 0.0)[3]
    m_eta = max(abs(r["d_eta"]) for r in rows); m_u = max(abs(r["d_u"]) for r in rows); m_v = max(abs(r["d_v"]) for r in rows)
    ok = bool(m_eta <= 1e-5 * sa and m_u <= 1e-5 * ref_uv and m_v <= 1e-5 * ref_uv and not errs)
    allok &= ok
    res["programs"][prog] = dict(name=inl["name"], rep_P=inl["rep_P"], sum_a=sa, sum_a_om_coth=ref_uv, max_abs_d_eta=m_eta, max_abs_d_u=m_u,
                                 max_abs_d_v=m_v, rel_eta=m_eta / sa, rel_u=m_u / ref_uv, rel_v=m_v / ref_uv, ok=ok, errors=errs,
                                 vex_ncomp=len(inl["freqs_Hz"]), rows=rows)
    print(prog, "max |d| eta %.3e (rel %.2e) u %.3e (rel %.2e) v %.3e (rel %.2e) ok %s" % (m_eta, m_eta / sa, m_u, m_u / ref_uv, m_v, m_v / ref_uv, ok))
# OUT_INLET の 64 ビットの確かめ（表の値が丸められていないか）
inl = C.inlet_of(P, "PR2")
ctrl.parm("inlet_tab").set(L.inlet_tab_string(inl["freqs_Hz"], inl["amps_m"], inl["phases_rad"], inl["k"]))
tg = hou.node("/obj/G44_SETUP/OUT_INLET").geometry()
res["table_roundtrip_max_abs"] = dict(freq=max(abs(a - b) for a, b in zip(tg.attribValue("freq"), inl["freqs_Hz"])),
                                      phase=max(abs(a - b) for a, b in zip(tg.attribValue("phase"), inl["phases_rad"])),
                                      k=max(abs(a - b) for a, b in zip(tg.attribValue("k"), inl["k"])))
res["pass"] = bool(allok)
print("table roundtrip", res["table_roundtrip_max_abs"], "PASS" if allok else "FAIL")
json.dump(res, open(os.path.join(OUT, "s3.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
