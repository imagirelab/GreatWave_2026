# -*- coding: utf-8 -*-
"""FLIP50 (option D): VEX and Python SOP code of the tank Houdini/FLIP50/g50_tank.hiplc (used by g50_build_tank.py).
2026-10-15 written new (option D implementation, Claude). Reuse, unchanged in substance:
  g49_tanklib.VEX_HEAD (flip49, read only): the bed (bedy/bedgrad/bedsdf_out: D19B goes through the FLIP48 plain path, k 0, shelf_h 0),
    smooth01, sol_eta/sol_vel (wave_on 0), relaxw, walltaper, rampT, sf_chch/sf_shch, sf_setenv, sfwave (Fenton, S2D strips), vc_divergence.
    The text is taken from the module at import time; only the node paths G49_SETUP -> G50_SETUP are renamed and the FLIP49 band function
    relax_apply (laterally uniform Fenton inlet + exit sponge) is REPLACED by the FLIP50 one below. g49_tanklib's sha256 is recorded by
    g50_common.module_shas; g50_build_tank.py checks that the replaced block was found exactly once.
  g49_tanklib.PYSOP (solitary table, unused: wave_on 0), PYSOP_VOLDIV (stage A/B/C file reader).
Added (FLIP50):
  1. dirwave(): the directional periodic target from the complex table OUT_DIRTAB (g50_table.py npz read by PYSOP_DIRTAB):
       eta_t = g (er c + ei s), c = cos(omega (t - dir_tf)), s = sin(...);  z' = clamp(h (z - eta_t)/max(h + eta_t, 0.1 h), -h, 0)
       U = g (ur c + ui s) cosh(k (z' + h))/cosh(k h) + ret_on g^2 mx;  V likewise with vr, vi, my (horizontal only)
  2. bands50(): FLIP45 g45_tanklib bands() rule for an inlet band (x < xg_end, FLIP42 weight relaxw, per substep 1 - (1 - w)^(dt/dt0)) and a
       side band (y > sd0 up to the outer wall W): x <= sd_gen generates (same weight), x >= sd_sw absorbs (1 - exp(-sd_sigma chi^sd_pow dt),
       target 0), smooth01 blend between; corner = larger weight, target factors multiplied. Optional exit sponge (abs_on, D has none).
  3. relax_apply(): target factor g = gain (in_gain in the inlet band, else sd_gain) x side factor x walltaper(x) (upstream wall) x
       sdtaper(y) (outer side wall, FLIP45 rule) x rampT. dir_on 1 -> dirwave; else sf_on 1 -> Fenton sfwave (x only, S2D strips).
       Stage C du_abs (Sommerfeld term) is added to the x target inside the inlet band, times walltaper (as FLIP49).
       Only vel.x and vel.z (horizontal) are relaxed; the vertical velocity and the surface never.
Coordinates: VEX first returns to plan coordinates pl = @P - o: x = wave direction, y = up (still level 0), z = lateral (z = 0 symmetry plane).
The numpy mirror of every function here is g50_table.py (dirwave_np, bands_np, relax_np); the build checks compare them point by point.
"""
import importlib.util as _ilu, os as _os

_T49 = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49/g49_tanklib.py"
_spec = _ilu.spec_from_file_location("g49_tanklib_ro50", _T49)
_g49t = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_g49t)

CT = "/obj/G50_SETUP/CTRL/"
TABD = "op:/obj/G50_SETUP/OUT_DIRTAB"

_A0 = "// ---------------------------------------------------------------- FLIP49 の帯"
_A1 = "// 水の量の直しの目標の発散"

VEX_D = r'''
#define TABD "%s"
// ---------------------------------------------------------------- FLIP50：方向のある周期の波の表（OUT_DIRTAB、X = x、Y = 2 枚の同じ層、Z = 横 y）
vector dtab_pos(float x; float zl) {
    float xa = detail(TABD, "d_x0", 0); float xb = detail(TABD, "d_x1", 0);      // typed locals: detail() is overloaded by return type
    float ya = detail(TABD, "d_y0", 0); float yb = detail(TABD, "d_y1", 0);
    return set(clamp(x, xa, xb), 0.0, clamp(zl, ya, yb));
}
void dirwave(float x; float yv; float zl; float t; float g; float eta; vector vel) {
    vector tp = dtab_pos(x, zl);
    float om = detail(TABD, "d_omega", 0);
    float ph = om*(t - chf(CT+"dir_tf"));
    float c = cos(ph); float s = sin(ph);
    eta = g*(volumesample(TABD, "er", tp)*c + volumesample(TABD, "ei", tp)*s);
    float h = volumesample(TABD, "hh", tp);
    float k = volumesample(TABD, "kk", tp);
    float ye = clamp(h*(yv - eta)/max(h + eta, 0.1*h), -h, 0.0);
    float prof = sf_chch(k*(ye + h), k*h);
    float U = g*(volumesample(TABD, "ur", tp)*c + volumesample(TABD, "ui", tp)*s)*prof;
    float V = g*(volumesample(TABD, "vr", tp)*c + volumesample(TABD, "vi", tp)*s)*prof;
    if (chf(CT+"ret_on") > 0.5) {
        U += g*g*volumesample(TABD, "mx", tp);
        V += g*g*volumesample(TABD, "my", tp);
    }
    vel = set(U, 0.0, V);
}
// 外の横の壁 y = W へ目標を 0 に落とす（FLIP45 の wallE の横の項。横の帯がある時だけ）
float sdtaper(float zl) {
    float L = chf(CT+"sd_taper_m");
    if (chf(CT+"sd_on") < 0.5 || L <= 0.0) return 1.0;
    return smooth01((chf(CT+"W") - zl)/L);
}
// 帯の重み（この小刻みで寄せる割合 wdt）、目標の掛け数 ftg、入口の帯の中か inb、横の帯の中か insd（FLIP45 bands() の決まり）
void bands50(float x; float zl; float dts; float wdt; float ftg; int inb; int insd) {
    float dt0 = chf(CT+"dt0"); float rg = chf(CT+"relax_g");
    wdt = 0.0; ftg = 1.0; inb = 0; insd = 0;
    float xg = chf(CT+"xg_end");
    if (chf(CT+"relax_on") > 0.5 && rg > 0.0 && x < xg) {
        float w = clamp(relaxw((xg - x)/max(xg - chf(CT+"x0"), 1e-6))*rg, 0.0, 1.0);
        wdt = max(wdt, 1.0 - pow(1.0 - w, dts/dt0));
        inb = 1;
    }
    float a = chf(CT+"sd0"); float b = chf(CT+"W");
    if (chf(CT+"sd_on") > 0.5 && zl > a) {
        float chi = clamp((zl - a)/max(b - a, 1e-6), 0.0, 1.0);
        float s = smooth01((x - chf(CT+"sd_gen"))/max(chf(CT+"sd_sw") - chf(CT+"sd_gen"), 1e-6));
        float wg = 1.0 - pow(1.0 - clamp(relaxw(chi)*rg, 0.0, 1.0), dts/dt0);
        float wa = 1.0 - exp(-chf(CT+"sd_sigma")*pow(chi, chf(CT+"sd_pow"))*dts);
        wdt = max(wdt, lerp(wg, wa, s));
        ftg *= (1.0 - s);
        insd = 1;
    }
    float xa0 = chf(CT+"xa0"); float x1 = chf(CT+"x0") + chf(CT+"Lx");
    if (chf(CT+"abs_on") > 0.5 && x > xa0) {
        float chi = clamp((x - xa0)/max(x1 - xa0, 1e-6), 0.0, 1.0);
        wdt = max(wdt, 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*dts));
        ftg = 0.0;
    }
}
// FLIP50 の帯：方向のある周期の波（dir_on 1）か流れ関数の波（sf_on 1、S2D の板）へ水平の流速だけを寄せる
vector relax_apply(vector pl; vector vel; float t; float dts) {
    float x = pl.x; float zl = pl.z;
    float wdt; float ftg; int inb; int insd;
    bands50(x, zl, dts, wdt, ftg, inb, insd);
    if (wdt <= 0.0) return vel;
    float wt = walltaper(x);
    float gb = inb ? chf(CT+"in_gain") : chf(CT+"sd_gain");
    float gm = gb*ftg*wt*sdtaper(zl)*rampT(t, chf(CT+"ramp_s"));
    float eta = 0.0; vector tv = {0, 0, 0};
    if (gm != 0.0) {
        if (chf(CT+"dir_on") > 0.5) {
            dirwave(x, pl.y, zl, t, gm, eta, tv);
        } else if (chf(CT+"sf_on") > 0.5) {
            sfwave(x, pl.y, t, gm*sf_setenv(t, x), eta, tv);
            tv = set(tv.x, 0.0, 0.0);
        }
    }
    float ux = tv.x;
    if (inb && chf(CT+"duabs_on") > 0.5) { float dua = detail(VDT, "du_abs", 0); ux += wt*dua; }
    return set(lerp(vel.x, ux, wdt), vel.y, lerp(vel.z, tv.z, wdt));      // 縦の流速は寄せない
}
''' % TABD


def _make_head():
    h = _g49t.VEX_HEAD
    n_paths = h.count("/obj/G49_SETUP/")
    h = h.replace("/obj/G49_SETUP/", "/obj/G50_SETUP/")
    i0 = h.find(_A0); i1 = h.find(_A1)
    if h.count(_A0) != 1 or h.count(_A1) != 1 or not (0 < i0 < i1):
        raise RuntimeError("g49_tanklib.VEX_HEAD changed: the FLIP49 band block to replace was not found exactly once")
    old = h[i0:i1]
    if old.count("vector relax_apply(") != 1:
        raise RuntimeError("g49_tanklib.VEX_HEAD changed: relax_apply not inside the replaced block")
    return h[:i0] + VEX_D + "\n" + h[i1:], dict(paths_renamed=n_paths, replaced_chars=len(old), replaced_block_head=old[:120])


VEX_HEAD, HEAD_INFO = _make_head()
TABF = _g49t.TABF
SFT = "op:/obj/G50_SETUP/OUT_SF"
VDT = "op:/obj/G50_SETUP/OUT_VOLDIV"
if ('"%s"' % SFT) not in VEX_HEAD or ('"%s"' % VDT) not in VEX_HEAD or ('"%s"' % CT) not in VEX_HEAD:
    raise RuntimeError("renamed node paths missing in the FLIP50 VEX head")

BODIES = {
    "/obj/G50_SIM/substep_count": _g49t.BODIES["/obj/G49_SIM/substep_count"],
    "/obj/G50_SETUP/bed_height": _g49t.BODIES["/obj/G49_SETUP/bed_height"],
    "/obj/G50_SETUP/bed_sdf_value": _g49t.BODIES["/obj/G49_SETUP/bed_sdf_value"],
    "/obj/G50_SETUP/vel_value": _g49t.BODIES["/obj/G49_SETUP/vel_value"],
    "/obj/G50_SETUP/sf_table": _g49t.BODIES["/obj/G49_SETUP/sf_table"],
    "/obj/G50_SIM/relax_zones": _g49t.BODIES["/obj/G49_SIM/relax_zones"],
    "/obj/G50_SIM/vc_div": _g49t.BODIES["/obj/G49_SIM/vc_div"],
    "/obj/G50_SETUP/sf_probe": _g49t.BODIES["/obj/G49_SETUP/sf_probe"],
    "/obj/G50_SETUP/relax_probe": _g49t.BODIES["/obj/G49_SETUP/relax_probe"],
    # FLIP50：方向のある波の表の確かめ（点の属性 px・py・pz・pt、g = 1。ret_on は CTRL の値）
    "/obj/G50_SETUP/dir_probe": r'''
float eta; vector tv;
dirwave(f@px, f@py, f@pz, f@pt, 1.0, eta, tv);
f@eta_v = eta; f@u_v = tv.x; f@v_v = tv.z;
''',
}

PYSOP = _g49t.PYSOP
PYSOP_VOLDIV = _g49t.PYSOP_VOLDIV

# 方向のある波の表（g50_table.py の npz）を体積にする Python SOP。CTRL の dir_npz が空か無いファイルなら、体積なし（d_nfield 0）
PYSOP_DIRTAB = r'''
import os, json
import hou
import numpy as np
node = hou.pwd()
geo = node.geometry()
geo.clear()
for nm in ("d_omega", "d_T", "d_x0", "d_x1", "d_y0", "d_y1", "d_dx", "d_dy", "d_tf"):
    geo.addAttrib(hou.attribType.Global, nm, 0.0)
geo.addAttrib(hou.attribType.Global, "d_nfield", 0)
geo.addAttrib(hou.attribType.Global, "d_src", "")
geo.addAttrib(hou.attribType.Global, "d_content", "")
geo.addAttrib(hou.attribType.Prim, "name", "")
p = node.evalParm("npz")
if p and os.path.exists(p):
    d = np.load(p, allow_pickle=False)
    info = json.loads(str(d["info"]))
    nx, ny = int(info["nx"]), int(info["ny"])
    x0, dx, y0, dy = float(info["x0"]), float(info["dx"]), float(info["y0"]), float(info["dy"])
    bb = hou.BoundingBox(x0 - 0.5 * dx, -1.0, y0 - 0.5 * dy, x0 + (nx - 0.5) * dx, 1.0, y0 + (ny - 0.5) * dy)
    nf = 0
    for nm in info["fields"]:
        a = np.asarray(d[nm], dtype=np.float32)
        if a.shape != (ny, nx):
            raise hou.NodeError("table field %s has shape %s, expected %s" % (nm, a.shape, (ny, nx)))
        a3 = np.ascontiguousarray(np.repeat(a[:, None, :], 2, axis=1))      # (ny, 2, nx): x fastest, then the 2 identical layers, then y
        v = geo.createVolume(nx, 2, ny, bb)
        v.setAttribValue("name", nm)
        v.setAllVoxelsFromString(a3.tobytes())
        nf += 1
    geo.setGlobalAttribValue("d_omega", float(info["omega"]))
    geo.setGlobalAttribValue("d_T", float(info["T"]))
    geo.setGlobalAttribValue("d_x0", x0)
    geo.setGlobalAttribValue("d_x1", x0 + (nx - 1) * dx)
    geo.setGlobalAttribValue("d_y0", y0)
    geo.setGlobalAttribValue("d_y1", y0 + (ny - 1) * dy)
    geo.setGlobalAttribValue("d_dx", dx)
    geo.setGlobalAttribValue("d_dy", dy)
    geo.setGlobalAttribValue("d_tf", float(info.get("t_f", 0.0)))
    geo.setGlobalAttribValue("d_nfield", nf)
    geo.setGlobalAttribValue("d_src", p)
    geo.setGlobalAttribValue("d_content", str(info.get("content_sha256", "")))
'''


def snippet(path):
    return VEX_HEAD + BODIES[path]
