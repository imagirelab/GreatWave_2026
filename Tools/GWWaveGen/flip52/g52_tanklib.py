# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: VEX and Python SOP code of the tank Houdini/FLIP52/g52_tank.hiplc (used by g52_build_tank.py).
2026-10-17 written new (Claude). Reuse, unchanged in substance:
  g50_tanklib.VEX_HEAD (flip50, read only; itself g49_tanklib's head with the FLIP50 bands): bed, smooth01, relaxw, walltaper, rampT,
    sf_chch, sfwave (unused: sf_on 0), sdtaper, bands50 (inlet band, side band generating -> absorbing blend, exit sponge abs_on),
    relax_apply (velocity-only relaxation, vertical velocity and surface never relaxed), vc_divergence (stage A).
    The text is taken from the module at import time; only (a) the node paths G50_SETUP -> G52_SETUP are renamed and (b) the FLIP50 one-layer
    dirwave() (and its dtab_pos) is REPLACED by the N-layer one below. Both replacements are counted; HEAD_INFO records them, and
    g52_build_tank.py stores HEAD_INFO and the module shas in build_check52.json.
  g50_tanklib.BODIES / PYSOP / PYSOP_VOLDIV (node paths renamed).
Added (FLIP52):
  dirwave(): the periodic multi-frequency directional target from the N-layer table OUT_DIRTAB (g52_table.py npz, read by PYSOP_DIRTAB52):
       layers n = 0 .. d_nlayer - 1 (<= 4): harmonic h_n = d_n<n> of the sea period P = d_P, phase 2 pi h_n (t - dir_tf)/P;
       eta_t = g sum_n (er<n> c_n + ei<n> s_n);  z' = clamp(h (z - eta_t)/max(h + eta_t, 0.1 h), -h, 0)
       U = g sum_n (ur<n> c_n + ui<n> s_n) cosh(k_n (z' + h))/cosh(k_n h) + ret_on g^2 mx;  V likewise with vr, vi, my (horizontal only)
       2 pi is the literal 6.283185307179586476925 (the numpy mirror uses the same literal; independent of the precision of VEX PI);
       d_P and d_n<n> are exact in float32 (28, 3, 4, 5), so the phase is computed in 64 bit from exact inputs.
Coordinates: VEX first returns to plan coordinates pl = @P - o: x = wave direction, y = up (still level 0), z = lateral (z = 0 symmetry plane).
The numpy mirror of every function here is g52_table.py (dirwave_np, relax_np with g50_table.bands_np / tapers_np); the build checks compare
them point by point.
"""
import importlib.util as _ilu

_T50 = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50/g50_tanklib.py"
_spec = _ilu.spec_from_file_location("g50_tanklib_ro52", _T50)
_g50t = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_g50t)

CT = "/obj/G52_SETUP/CTRL/"
TABD = "op:/obj/G52_SETUP/OUT_DIRTAB"
SFT = "op:/obj/G52_SETUP/OUT_SF"
VDT = "op:/obj/G52_SETUP/OUT_VOLDIV"

_B0 = "vector dtab_pos(float x; float zl) {"
_B1 = "// 外の横の壁 y = W へ目標を 0 に落とす"

VEX_DIRWAVE = r'''vector dtab_pos(float x; float zl) {
    float xa = detail(TABD, "d_x0", 0); float xb = detail(TABD, "d_x1", 0);      // typed locals: detail() is overloaded by return type
    float ya = detail(TABD, "d_y0", 0); float yb = detail(TABD, "d_y1", 0);
    return set(clamp(x, xa, xb), 0.0, clamp(zl, ya, yb));
}
// FLIP52: N-layer periodic multi-frequency directional table (layer n: er<n> ei<n> ur<n> ui<n> vr<n> vi<n> kk<n>; shared hh mx my)
void dirwave(float x; float yv; float zl; float t; float g; float eta; vector vel) {
    vector tp = dtab_pos(x, zl);
    float nlf = detail(TABD, "d_nlayer", 0);
    float Pp = detail(TABD, "d_P", 0);
    int nl = int(nlf + 0.5);
    float tt = t - chf(CT+"dir_tf");
    float cs[]; float sn[];
    resize(cs, 4); resize(sn, 4);
    float es = 0.0;
    for (int n = 0; n < nl; n++) {
        string sx = itoa(n);
        float hn = detail(TABD, "d_n" + sx, 0);
        float ph = 6.283185307179586476925*hn*tt/Pp;
        cs[n] = cos(ph); sn[n] = sin(ph);
        es += volumesample(TABD, "er" + sx, tp)*cs[n] + volumesample(TABD, "ei" + sx, tp)*sn[n];
    }
    eta = g*es;
    float h = volumesample(TABD, "hh", tp);
    float ye = clamp(h*(yv - eta)/max(h + eta, 0.1*h), -h, 0.0);
    float us = 0.0; float vs = 0.0;
    for (int n = 0; n < nl; n++) {
        string sy = itoa(n);
        float k = volumesample(TABD, "kk" + sy, tp);
        float prof = sf_chch(k*(ye + h), k*h);
        us += (volumesample(TABD, "ur" + sy, tp)*cs[n] + volumesample(TABD, "ui" + sy, tp)*sn[n])*prof;
        vs += (volumesample(TABD, "vr" + sy, tp)*cs[n] + volumesample(TABD, "vi" + sy, tp)*sn[n])*prof;
    }
    float U = g*us; float V = g*vs;
    if (chf(CT+"ret_on") > 0.5) {
        U += g*g*volumesample(TABD, "mx", tp);
        V += g*g*volumesample(TABD, "my", tp);
    }
    vel = set(U, 0.0, V);
}
'''


def _make_head():
    h = _g50t.VEX_HEAD
    n_paths = h.count("/obj/G50_SETUP/")
    if n_paths != 4 or h.count("G50_") != 4:
        raise RuntimeError("g50_tanklib.VEX_HEAD changed: expected 4 node paths /obj/G50_SETUP/ (CT, TABD, SFT, VDT), found %d" % n_paths)
    h = h.replace("/obj/G50_SETUP/", "/obj/G52_SETUP/")
    i0 = h.find(_B0); i1 = h.find(_B1)
    if h.count(_B0) != 1 or h.count(_B1) != 1 or not (0 < i0 < i1):
        raise RuntimeError("g50_tanklib.VEX_HEAD changed: the FLIP50 dirwave block to replace was not found exactly once")
    old = h[i0:i1]
    if old.count("void dirwave(") != 1 or old.count("vector dtab_pos(") != 1 or "relax_apply" in old or "bands50" in old:
        raise RuntimeError("g50_tanklib.VEX_HEAD changed: the replaced block is not exactly dtab_pos + dirwave")
    new = h[:i0] + VEX_DIRWAVE + h[i1:]
    for need in ('#define TABD "%s"' % TABD, '"%s"' % SFT, '"%s"' % VDT, '#define CT "%s"' % CT, "void bands50(", "vector relax_apply(",
                 "float vc_divergence(", "float sdtaper("):
        if new.count(need) != 1:
            raise RuntimeError("FLIP52 VEX head: %r found %d times (expected once)" % (need, new.count(need)))
    if "G50_" in new:
        raise RuntimeError("FLIP52 VEX head still names a G50 node")
    return new, dict(paths_renamed=n_paths, replaced_chars=len(old), new_chars=len(VEX_DIRWAVE), replaced_block_head=old[:160],
                     source="flip50/g50_tanklib.VEX_HEAD")


VEX_HEAD, HEAD_INFO = _make_head()
TABF = _g50t.TABF


def _ren(s):
    return s.replace("/obj/G50_SETUP/", "/obj/G52_SETUP/").replace("/obj/G50_SIM/", "/obj/G52_SIM/")


BODIES = {_ren(k): v for k, v in _g50t.BODIES.items()}
for _k, _v in BODIES.items():
    if "G50_" in _v:
        raise RuntimeError("body %s names a G50 node" % _k)

PYSOP = _g50t.PYSOP
PYSOP_VOLDIV = _g50t.PYSOP_VOLDIV

# the N-layer table (g52_table.py npz) as volumes. CTRL dir_npz empty or a missing file -> no volumes (d_nfield 0, d_nlayer 0).
# Detail attributes read by the VEX are FLOAT (d_nlayer, d_P, d_n0..d_n3 are exact in float32); d_om<n> is for the records only.
PYSOP_DIRTAB52 = r'''
import os, json
import hou
import numpy as np
node = hou.pwd()
geo = node.geometry()
geo.clear()
for nm in ("d_P", "d_nlayer", "d_n0", "d_n1", "d_n2", "d_n3", "d_om0", "d_om1", "d_om2", "d_om3", "d_x0", "d_x1", "d_y0", "d_y1", "d_dx", "d_dy", "d_tf"):
    geo.addAttrib(hou.attribType.Global, nm, 0.0)
geo.addAttrib(hou.attribType.Global, "d_nfield", 0)
geo.addAttrib(hou.attribType.Global, "d_src", "")
geo.addAttrib(hou.attribType.Global, "d_content", "")
geo.addAttrib(hou.attribType.Prim, "name", "")
p = node.evalParm("npz")
if p and os.path.exists(p):
    d = np.load(p, allow_pickle=False)
    info = json.loads(str(d["info"]))
    nl = int(info["n_layers"])
    if nl < 1 or nl > 4:
        raise hou.NodeError("the table has %d layers; the VEX reads 1-4" % nl)
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
    geo.setGlobalAttribValue("d_P", float(info["P"]))
    geo.setGlobalAttribValue("d_nlayer", float(nl))
    for n in range(nl):
        geo.setGlobalAttribValue("d_n%d" % n, float(info["harmonics"][n]))
        geo.setGlobalAttribValue("d_om%d" % n, float(info["omega"][n]))
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
