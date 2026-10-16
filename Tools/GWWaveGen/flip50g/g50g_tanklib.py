# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): the VEX of the groove hip Houdini/FLIP50/g50_tank_g.hiplc (used by g50g_build_tank.py). 2026-10-17 written new (Claude).
Everything is g50_tanklib (flip50, read only; its sha256_16 is frozen in dg1_frozen.json untouched) except the bed head, changed by exact,
counted string replacements of g50_tanklib.VEX_HEAD:
  1. the FLIP50 bed functions are renamed  bedy -> bedy_d19b,  bedgrad -> bedgrad_d19b  (their text is unchanged: D19B / FLIP48 plain path)
  2. inserted before bedsdf_out (which, like every other caller, now calls the new bedy / bedgrad):
       gr_dz(x, zl) = (dz, d dz/dx, d dz/dzl) of the frozen groove, read from CTRL gr_on, gr_D, gr_b, gr_Y, gr_x1..gr_x4
       (gr_on < 0.5 or gr_D == 0 -> exactly 0: the D19B bed, the switch-off check of T0G)
       bedy(x, zl) = bedy_d19b(x, zl) - dz;  bedgrad(x, zl) = bedgrad_d19b(x, zl) - grad dz
  The numpy mirror is g50g_common.gr_dz / gr_grad (and the patched g49_common.bed_z / bed_grad / bed_sdf); x50g_build.py compares OUT_BED and
  the bed SDF with it at every point (whole bed and the groove box x 230-360 m, |y| <= 60 m).
Plan coordinates as FLIP50: x = wave direction, zl = lateral (y of the plan), still level 0; the groove is even in zl.
"""
import os as _os, sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50", _HERE):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
import g50_tanklib as _L50        # noqa: E402  read only

CT = _L50.CT
TABD = _L50.TABD
TABF = _L50.TABF
SFT = _L50.SFT
VDT = _L50.VDT
PYSOP = _L50.PYSOP
PYSOP_VOLDIV = _L50.PYSOP_VOLDIV
PYSOP_DIRTAB = _L50.PYSOP_DIRTAB
BODIES = dict(_L50.BODIES)

_A_BEDY = "float bedy(float x; float zl) {"
_A_GRAD = "vector2 bedgrad(float x; float zl) {"
_A_SDF = "float bedsdf_out(float x; float y; float zl) {"

VEX_GR = r'''// ---------------------------------------------------------------- FLIP50 DG1 (AM-D20, Unity/Build/FLIP50/plan/dg1_frozen.json)
// the CHOSEN groove pair beside the axis (rip-channel / spur-and-groove analogue, not a measured site):
//   dz = D (1 - exp(-(y/b)^2)) exp(-(y/Y)^2) r(x),  r = S((x - x1)/(x2 - x1)) (1 - S((x - x3)/(x4 - x3))),  S = smoothstep,  bed = D19B - dz
float gr_S(float u) { float v = clamp(u, 0.0, 1.0); return v*v*(3.0 - 2.0*v); }
float gr_Sp(float u) { return (u > 0.0 && u < 1.0) ? 6.0*u*(1.0 - u) : 0.0; }
// (dz, d dz/dx, d dz/dzl); exactly 0 when gr_on < 0.5 or gr_D == 0
vector gr_dz(float x; float zl) {
    float gD = chf(CT+"gr_D");
    if (chf(CT+"gr_on") < 0.5 || gD == 0.0) return {0, 0, 0};
    float x1 = chf(CT+"gr_x1"); float x2 = chf(CT+"gr_x2"); float x3 = chf(CT+"gr_x3"); float x4 = chf(CT+"gr_x4");
    float u1 = (x - x1)/(x2 - x1); float u3 = (x - x3)/(x4 - x3);
    float sa = gr_S(u1); float sb = 1.0 - gr_S(u3);
    float r = sa*sb;
    float rp = gr_Sp(u1)/(x2 - x1)*sb - sa*gr_Sp(u3)/(x4 - x3);
    if (r == 0.0 && rp == 0.0) return {0, 0, 0};
    float gb = chf(CT+"gr_b"); float gY = chf(CT+"gr_Y");
    float qb = zl/gb; float qY = zl/gY;
    float eb = exp(-qb*qb); float eY = exp(-qY*qY);
    float Ly = (1.0 - eb)*eY;
    float Lp = 2.0*zl*(eb/(gb*gb) - (1.0 - eb)/(gY*gY))*eY;
    return set(gD*Ly*r, gD*Ly*rp, gD*Lp*r);
}
// the DG1 bed (plan coordinates): D19B (bedy_d19b / bedgrad_d19b, unchanged FLIP50 text) minus the groove
float bedy(float x; float zl) {
    vector g = gr_dz(x, zl);
    return bedy_d19b(x, zl) - g.x;
}
vector2 bedgrad(float x; float zl) {
    vector2 g0 = bedgrad_d19b(x, zl);
    vector g = gr_dz(x, zl);
    return set(g0.x - g.y, g0.y - g.z);
}
'''


def _make_head():
    h = _L50.VEX_HEAD
    for a in (_A_BEDY, _A_GRAD, _A_SDF):
        if h.count(a) != 1:
            raise RuntimeError("g50_tanklib.VEX_HEAD changed: %r found %d times (expected 1)" % (a, h.count(a)))
    i_y, i_g, i_s = h.find(_A_BEDY), h.find(_A_GRAD), h.find(_A_SDF)
    if not (i_y < i_g < i_s):
        raise RuntimeError("g50_tanklib.VEX_HEAD changed: bedy / bedgrad / bedsdf_out order")
    if "bedy(" in h[:i_y] or "bedgrad(" in h[:i_g].replace(_A_GRAD, ""):
        raise RuntimeError("g50_tanklib.VEX_HEAD: bedy / bedgrad called before their definition")
    if "gr_dz" in h or "gr_S(" in h:
        raise RuntimeError("g50_tanklib.VEX_HEAD already has a gr_ function")
    h2 = h.replace(_A_BEDY, "float bedy_d19b(float x; float zl) {").replace(_A_GRAD, "vector2 bedgrad_d19b(float x; float zl) {")
    # insert the groove block before the comment line that heads bedsdf_out
    j = h2.find(_A_SDF)
    k = h2.rfind("\n", 0, j - 1) + 1          # start of the comment line just above bedsdf_out
    if not h2[k:j].lstrip().startswith("//"):
        k = j
    h2 = h2[:k] + VEX_GR + h2[k:]
    return h2, dict(base=_L50.HEAD_INFO, renamed=["bedy -> bedy_d19b", "bedgrad -> bedgrad_d19b"], inserted_chars=len(VEX_GR),
                    inserted_before="the bedsdf_out comment line", n_bedy_calls_after=h2.count("bedy("), n_bedgrad_calls_after=h2.count("bedgrad("))


VEX_HEAD, HEAD_INFO = _make_head()


def snippet(path):
    return VEX_HEAD + BODIES[path]
