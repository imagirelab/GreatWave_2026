# -*- coding: utf-8 -*-
"""FLIP55 option C2: the NEST scene Houdini/FLIP55/f55_nest.hiplc, its build check Unity/Build/FLIP55/_logs/build_check55_nest.json and the
0.5 m smoke (py -3.10 launcher + writer; hython builder). 2026-10-19 written new (Claude); one of the two nest tools registered BY NAME in
f55_common.NEST_TOOLS (the other: f55_nest.py). It writes ONLY Houdini/FLIP55/f55_nest.hiplc (refuses any other hip) and files under
Unity/Build/FLIP55; DFG-2B-V's scene and tools are read only.

The scene = DFG-2B-V's scene graph (flip52b/g52b_build_tank.py lineage: the same node names G52_SETUP / G52_SIM / G52_READ / G52_SURF, the
FLIP52 VEX head of flip52/g52_tanklib.py unchanged, the bed SDF, particle columns, FLIP Solver 2.0 settings, explicit-cache checkpoints, the
surface path for R5) with these nest additions (so the FROZEN g52b3_run.py records it exactly as DFG-2B-V):
  CTRL       every DFG-2B-V CTRL parm (defaults: the C2ID nest box x 180-356, y 0-60, z -19..17, dp 0.5; bands off; wall_taper_m 0) +
             NEST_PARMS (nest_on, band_surf, rep_on, sim_f0, relax_vert, kill_margin_dp, seed_margin_dp, seed_depth_m, seed_r_dp,
             seed_fill_frac, w_min, seed_once_per_frame, end_on, end_band_m, s_off, bed_trust_m, tgt_dir, rep_dir); the build check asserts
             that every key of DFG-2B-V's launched cfg parms and every launch parm of f55_nest.py exists.
  OUT_TARGET Python SOP (PYSOP_TARGET): the parent's export files x_<fa>.npz / x_<fb>.npz, fb = ceil($FF), fa = fb - 1 (fa missing -> fb),
             each frame's boxes assembled on the parent's own lattice (no resampling) into volumes s_a vx_a vy_a vz_a e_a / ..._b in nest
             Houdini coordinates (e = the parent's top surface by the runner's R1 rule, plan height; dry columns = the bed height); detail
             t_ff t_fa t_fb t_ok t_pad t_border. Every volume carries ONE GHOST CELL on each side (edge copy = a Streak border; at the y = 0
             symmetry plane the even mirror for cell-centred fields and the odd mirror for the vel.z face grid), and the 2-D e volumes are
             2 voxels tall, so no sample inside the data ever reaches Houdini's (constant 0) volume border (2026-10-19 review fix: the first
             0.5 m beside the plane read 0.625-0.875 x the field). Like OUT_VOLDIV it is cooked at the DOP substep time, so the weight
             (ff - fa) / (fb - fa) is the substep's.
  OUT_REPLAY the FLIP49 PYSOP_VOLDIV reader (unchanged) pointed at CTRL rep_dir: the parent's vd_<f>.txt.
  water      tgt_water(P, y, bed, e, m): the parent's water = below the parent's PARTICLE level (SDF + s_off < -m; s_off = the parent's
             still offset 0.0759846568107605 m [measured]: its SDF zero sits that far above the level its particles fill), or within
             bed_trust_m (1 m = one parent cell) of the bed and below e - s_off - m (the parent's SDF reads air in some cells just above
             the bed [measured, review M4]).
  init       particle_columns (unchanged) -> init_particles (nest VEX): nest_on 1 -> lattice points that are tgt_water (m 0) above bed +
             bed_gap dp, jitter 0.2 dp (the parent's hash), v = the parent's velocity at the particle; nest_on 1 with no target -> NO
             particles (fails loudly); nest_on 0 -> DFG-2B-V's still-water rule.
  DOP        the DOP network starts at frame 1 like DFG-2B-V's ($SF = $F, simulation time = global time, checkpoint names = global frames,
             as the frozen chain's resume needs); the FLIP and static objects are CREATED at frame sim_f0 = 1056 (creation frame in global
             frames, not solved on that frame), so frames 1-1055 hold no object; relax_zones = nest_apply (bands50 weights, walltaper /
             sdtaper / rampT like relax_apply, target = the parent's velocity, horizontal unless relax_vert; launched with wall_taper_m 0);
             vc_rep (rep_on) = the replayed divergence in vol_x0..vol_x1 (vc_divergence's window rule); pre-solve = substep_count then
             band_kill (point) and band_seed (detail): the surface relaxation by particles (once per frame on the first substep,
             probability = the band weight over one frame: delete particle centres that are not tgt_water (margin kill_margin_dp dp); seed
             tgt_water lattice points (margin seed_margin_dp dp), down to seed_depth_m, where fewer than seed_fill_frac x the full-water
             count of nest particles lie within seed_r_dp dp; a seed is a copy of its nearest nest particle (all attributes) with its own
             P, v = the parent's and a fresh id).
Build check items (all_ok needs every item; the smoke is needed for f55_nest.py amend --write):
  ctrl_superset, bed (OUT_BED + bed SDF vs numpy at the C2ID and C2 nest boxes), still_particles (nest_on 0 count = f55_common.count_particles),
  target_probe (synthetic export: OUT_TARGET values vs the analytic fields at an integer and a half frame, the time weight, the fallback, and
  rows at lateral 0-0.5 m against the mirrored expectation), band_probe (nest_wdt / nest_apply vs the frozen numpy mirror g50_table.bands_np /
  tapers_np / rampT), replay_probe, init_particles (synthetic target: Houdini count = numpy count, velocities), init_no_target (0 particles),
  dop_setup (DOP start frame 1, creation frames 1056 in global frames, no solve on creation, solver inputs), saved_defaults; smoke (--smoke,
  the REAL export): no object at 1055, object created at 1056, init count vs numpy on x_01056.npz within 0.5 %, initial velocity vs the
  parent's (mean |dv| < 0.05 m/s), 24 frames finite, DOP time = global time, checkpoint file name = global frame, particle attributes sane
  (pscale > 0, ids unique), nest volume vs the parent's within 5 % (report: band edge rms, seeds per frame).
usage:
  py -3.10 -B x55_nest_build.py [--smoke] [--simulate|--dry]
        default: preflight, wait for every other hython, run hython (this file --hython), then WRITE _logs/build_check55_nest.json
        --simulate / --dry: preflight + the numpy self-test of the scene code + the planned hython command; writes only _scratch/sim_nest
  hython x55_nest_build.py --hython [--smoke]      (internal; raw results -> _logs/build_raw55_nest.json)
Tags: [measured] [computed] [chosen].
"""
import os, sys, json, time, math, hashlib, subprocess, copy, glob

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
T52 = TOOLS + "/flip52"
T52B3 = TOOLS + "/flip52b3"
T50 = TOOLS + "/flip50"
B55 = REPO + "/Unity/Build/FLIP55"
HIP = REPO + "/Houdini/FLIP55/f55_nest.hiplc"
HIP_DIR = REPO + "/Houdini/FLIP55"
LOG_DIR = B55 + "/_logs"
BUILD_CHECK = LOG_DIR + "/build_check55_nest.json"
RAW = LOG_DIR + "/build_raw55_nest.json"
SMOKE_CFG = LOG_DIR + "/build_smoke_cfg55.json"
SMOKE_DIR = B55 + "/_scratch/nest_smoke"
SYNTH_DIR = B55 + "/_scratch/nest_build_synth"
SIM_DIR = B55 + "/_scratch/sim_nest"
TMP_HOUDINI = B55 + "/tmp_houdini"
TOOL_REL = "Tools/GWWaveGen/flip55/x55_nest_build.py"
NEST_TOOLS = ("Tools/GWWaveGen/flip55/x55_nest_build.py", "Tools/GWWaveGen/flip55/f55_nest.py")
DFGBV_READY = REPO + "/Unity/Build/FLIP52B3/runs/ready/DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5.json"
DFGBV_RUN = REPO + "/Unity/Build/FLIP52B3/runs/DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"
CT = "/obj/G52_SETUP/CTRL/"
SMOKE_FRAMES = 24
CKPT = 1056
FPS = 24.0

# the C2ID nest box (= f55_common.OPTIONS['C2ID'] / box(); the build check compares)
NEST_BOX = dict(dp=0.5, x0=180.0, Lx=176.0, W=60.0, zb=-19.0, Hz=36.0, ox=0.5, oy=0.5, oz=0.5)
NEST_BANDS = dict(xg_end=195.0, wall_taper_m=0.0, x_p=192.0, sd0=45.0, sd_gen=357.0, sd_sw=358.0, sd_taper_m=0.0, vol_x0=195.0, vol_x1=356.0,
                  crop_x0=180.0, crop_x1=356.0, crop_z1=45.0)
NEST_PARMS = [("nest_on", 0.0, "nest: bands relax toward the parent's fields (OUT_TARGET)"),
              ("band_surf", 0.0, "nest: surface relaxation by particles in the bands"),
              ("rep_on", 0.0, "nest: replay the parent's stage-A divergence (OUT_REPLAY) in vol_x0..vol_x1"),
              ("sim_f0", float(CKPT), "nest: DOP start frame = FLIP object creation frame"),
              ("relax_vert", 0.0, "nest: also relax the vertical velocity (0 = horizontal only, as DFG-2B-V's inlet band)"),
              ("kill_margin_dp", 0.0, "nest: delete band particles that are not the parent's water by this margin x dp (tgt_water)"),
              ("seed_margin_dp", 0.0, "nest: seed band lattice points that are the parent's water by this margin x dp (tgt_water)"),
              ("seed_depth_m", 2.0, "nest: seed candidates down to this depth below the parent's top surface (m)"),
              ("seed_r_dp", 1.5, "nest: radius (x dp) of the local fill count around a seed candidate"),
              ("seed_fill_frac", 0.5, "nest: seed a candidate if the nest particles within seed_r_dp dp are fewer than this x the full-water count"),
              ("w_min", 1e-3, "nest: band weight below this: no surface relaxation"),
              ("seed_once_per_frame", 1.0, "nest: surface relaxation once per frame (first substep)"),
              ("end_on", 0.0, "nest: OPTIONAL end band at the closed face x0 + Lx (0 = the frozen design 'outflow: none')"),
              ("end_band_m", 15.0, "nest: width of the optional end band (m), the inlet band's rule mirrored"),
              ("s_off", 0.0, "nest: the parent's still offset (m): its SDF zero lies this far above its particle level (launch: 0.0759846568107605)"),
              ("bed_trust_m", 1.0, "nest: within this height above the bed the parent's top surface decides water (its SDF reads air there)")]
NEST_STR_PARMS = [("tgt_dir", "", "nest: the parent export folder (x_<f>.npz)"), ("rep_dir", "", "nest: the parent's vd_<f>.txt folder")]

# ====================================================================== VEX (appended to flip52/g52_tanklib.VEX_HEAD, which stays unchanged)
NEST_VEX = r'''
// ---------------------------------------------------------------- FLIP55 nest (x55_nest_build.py): the parent's fields as the band target
#define TGT "op:/obj/G52_SETUP/OUT_TARGET"
#define REP "op:/obj/G52_SETUP/OUT_REPLAY"
#define NEST_FRAME_DT (1.0/24.0)
int tgt_ok() { int k = detail(TGT, "t_ok", 0); return k; }
float tgt_w() {
    float ff = detail(TGT, "t_ff", 0); float fa = detail(TGT, "t_fa", 0); float fb = detail(TGT, "t_fb", 0);
    if (fb <= fa) return 1.0;
    return clamp((ff - fa)/(fb - fa), 0.0, 1.0);
}
float tgt_sdf(vector P) { float w = tgt_w(); return lerp(volumesample(TGT, "s_a", P), volumesample(TGT, "s_b", P), w); }
vector tgt_vel(vector P) {
    float w = tgt_w();
    vector va = set(volumesample(TGT, "vx_a", P), volumesample(TGT, "vy_a", P), volumesample(TGT, "vz_a", P));
    vector vb = set(volumesample(TGT, "vx_b", P), volumesample(TGT, "vy_b", P), volumesample(TGT, "vz_b", P));
    return lerp(va, vb, w);
}
float tgt_eta(vector P) { float w = tgt_w(); return lerp(volumesample(TGT, "e_a", P), volumesample(TGT, "e_b", P), w); }
// the parent's WATER at the Houdini point P (plan height y, bed height yb, the parent's top surface e of the column, margin m): below the
// parent's PARTICLE level (its SDF zero sits s_off = its still offset above the level its particles fill), or within bed_trust_m of the bed
// and below e - s_off - m (the parent's SDF reads air in some cells just above the bed)
int tgt_water(vector P; float y; float yb; float e; float m) {
    float so = chf(CT+"s_off");
    if (tgt_sdf(P) + so < -m) return 1;
    if (y - yb < chf(CT+"bed_trust_m") && y < e - so - m) return 1;
    return 0;
}
// OPTIONAL end band (end_on 1) at the closed face x1 = x0 + Lx: the inlet band's weight mirrored (relaxw from x1 - L), target = the parent's
// velocity with NO taper toward the face (a taper would make it a sponge, review 2026-10-19 B1 / M7); end_on 0 (default, the frozen design)
// -> weight 0: nothing changes
float end_w(float x; float dts) {
    if (chf(CT+"end_on") < 0.5) return 0.0;
    float L = chf(CT+"end_band_m"); float x1 = chf(CT+"x0") + chf(CT+"Lx");
    if (L <= 0.0 || x <= x1 - L) return 0.0;
    float w = clamp(relaxw((x - (x1 - L))/L)*chf(CT+"relax_g"), 0.0, 1.0);
    return 1.0 - pow(1.0 - w, dts/chf(CT+"dt0"));
}
// DFG-2B-V's band weight (bands50, unchanged) for a step dts (+ the optional end band, max)
float nest_wdt(float x; float zl; float dts) {
    float wdt; float ftg; int inb; int insd; bands50(x, zl, dts, wdt, ftg, inb, insd);
    return max(wdt, end_w(x, dts));
}
// the nest band = relax_apply's rule with the parent's velocity as the target (walltaper = 1: launched with wall_taper_m 0)
vector nest_apply(vector pl; vector vel; vector P; float t; float dts) {
    if (chf(CT+"nest_on") < 0.5) return relax_apply(pl, vel, t, dts);
    float wdt; float ftg; int inb; int insd;
    bands50(pl.x, pl.z, dts, wdt, ftg, inb, insd);
    float w = max(wdt, end_w(pl.x, dts));
    if (w <= 0.0 || tgt_ok() < 1) return vel;
    float gb = inb ? chf(CT+"in_gain") : chf(CT+"sd_gain");
    float gm = gb*ftg*walltaper(pl.x)*sdtaper(pl.z)*rampT(t, chf(CT+"ramp_s"));
    vector tv = gm*tgt_vel(P);
    float vy = (chf(CT+"relax_vert") > 0.5) ? lerp(vel.y, tv.y, w) : vel.y;
    return set(lerp(vel.x, tv.x, w), vy, lerp(vel.z, tv.z, w));
}
// the parent's stage-A divergence replayed (vc_divergence's window rule)
float vc_replay(vector pl) {
    if (chf(CT+"rep_on") < 0.5) return 0.0;
    float xa = chf(CT+"vol_x0"); float xb = chf(CT+"vol_x1");
    if (xb <= xa || (pl.x >= xa && pl.x <= xb)) { float d = detail(REP, "vol_div", 0); return d; }
    return 0.0;
}
// deterministic draw between 0 and 1 of a plan position and a time (the band surface relaxation)
float nest_draw(vector pl; float t) { return random(set(pl.x*1.6180339 + t*7.31, pl.y*2.7182818 + 0.5, pl.z*3.1415927 + t*1.13)); }
'''

BODIES_NEST = {
    "relax_zones": r'''
vector pl = plan(@P);
v@vel = nest_apply(pl, v@vel, @P, f@Time + chf(CT+"t_off"), f@TimeInc);
''',
    "vc_rep": r'''
f@divergence = vc_replay(plan(@P));
''',
    "band_kill": r'''
if (chf(CT+"nest_on") < 0.5 || chf(CT+"band_surf") < 0.5 || tgt_ok() < 1) return;
int once = chf(CT+"seed_once_per_frame") > 0.5;
int ssn = detail(0, "ss_n", 0);
if (once && ssn != 1) return;
vector pl = plan(@P);
float dts = once ? NEST_FRAME_DT : f@TimeInc;
float wdt = nest_wdt(pl.x, pl.z, dts);
if (wdt <= chf(CT+"w_min")) return;
float dp = chf(CT+"dp");
if (nest_draw(pl, f@Time) >= wdt) return;
// kill = NOT the parent's water by the margin kill_margin_dp dp (the complement of tgt_water with margin -km)
if (!tgt_water(@P, pl.y, bedy(pl.x, pl.z), tgt_eta(@P), -chf(CT+"kill_margin_dp")*dp)) removepoint(0, @ptnum);
''',
    "band_seed": r'''
i@band_added = 0; i@band_cand = 0;
if (chf(CT+"nest_on") < 0.5 || chf(CT+"band_surf") < 0.5 || tgt_ok() < 1) return;
int once = chf(CT+"seed_once_per_frame") > 0.5;
int ssn = detail(0, "ss_n", 0);
if (once && ssn != 1) return;
float dts = once ? NEST_FRAME_DT : f@TimeInc;
float dp = chf(CT+"dp"); float x0 = chf(CT+"x0"); float Lx = chf(CT+"Lx"); float W = chf(CT+"W"); float zb = chf(CT+"zb");
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
float xg = chf(CT+"xg_end"); float sd0 = chf(CT+"sd0"); float wmin = chf(CT+"w_min");
float sm = chf(CT+"seed_margin_dp")*dp; float depth = chf(CT+"seed_depth_m"); float rr = chf(CT+"seed_r_dp")*dp;
float nfull = 4.18879*pow(chf(CT+"seed_r_dp"), 3.0);          // particles within rr in full water (1 per dp^3)
float nneed = chf(CT+"seed_fill_frac")*nfull;
int nq = int(ceil(nneed));                                     // len(near) >= nneed <=> len(near) >= nq: no need to find more
float gap = chf(CT+"bed_gap")*dp;
int nx = int(floor(Lx/dp + 1e-6)); int nz = int(floor(W/dp + 1e-6));
int nadd = 0; int ncand = 0;
int hasid = haspointattrib(0, "id"); int hasnext = hasdetailattrib(0, "nextid"); int idn = -1;
for (int iz = 0; iz < nz; iz++) {
    float zl = (iz + 0.5)*dp;
    for (int ix = 0; ix < nx; ix++) {
        float x = x0 + (ix + 0.5)*dp;
        if (x >= xg && zl <= sd0 && end_w(x, dts) <= 0.0) continue;
        float wdt = nest_wdt(x, zl, dts);
        if (wdt <= wmin) continue;
        float e = tgt_eta(set(x, 0.0, zl) + o);
        float yb = bedy(x, zl);
        float ylo = max(yb + gap, e - depth);
        int k0 = max(int(ceil((ylo - zb)/dp - 0.5 - 1e-9)), 0);
        int k1 = int(ceil((e - zb)/dp - 0.5 - 1e-9));
        for (int k = k0; k < k1; k++) {
            float y = zb + (k + 0.5)*dp;
            vector q = set(x, y, zl) + o;
            if (!tgt_water(q, y, yb, e, sm)) continue;
            ncand++;
            if (nest_draw(set(x, y, zl), f@Time) >= wdt) continue;    // the draw first: independent of the query (same result, fewer queries)
            int near[] = nearpoints(0, q, rr, nq);
            if (len(near) >= nneed) continue;                 // the nest already has water around the candidate
            int c = iz*nx + ix;
            vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
            // a seed = a copy of the nearest nest particle (every attribute the FLIP object gave it), then its own P, v and a fresh id
            int tp = -1;
            if (len(near) > 0) tp = near[0]; else tp = nearpoint(0, q);
            int p = -1;                                       // no ternary around addpoint: one call, never both
            if (tp >= 0) p = addpoint(0, tp); else p = addpoint(0, q + jit);
            setpointattrib(0, "P", p, q + jit);
            setpointattrib(0, "v", p, tgt_vel(q + jit));
            if (hasid) {
                if (idn < 0) {
                    if (hasnext) { idn = detail(0, "nextid", 0); }
                    else { int mx = -1; int npt = npoints(0); for (int i = 0; i < npt; i++) { int pid = point(0, "id", i); mx = max(mx, pid); } idn = mx + 1; }
                }
                setpointattrib(0, "id", p, idn + nadd);
            }
            nadd++;
        }
    }
}
if (hasid && hasnext && nadd > 0) setdetailattrib(0, "nextid", idn + nadd, "set");
i@band_added = nadd; i@band_cand = ncand;
''',
    "init_particles": r'''
float dp = ch(CT+"dp"); float zb = ch(CT+"zb");
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
int c = i@col;
vector pc = @P - o;
int nest = chf(CT+"nest_on") > 0.5;
if (nest && tgt_ok() < 1) { removepoint(0, @ptnum); return; }
float vox = dp*ch(CT+"gridscale");
float et = nest ? tgt_eta(@P) : 0.0;
float e = nest ? et + vox : sol_eta(pc.x);
float yb = bedy(pc.x, pc.z);
float ylo = yb + chf(CT+"bed_gap")*dp;
for (int k = 0; k < 100000; k++) {
    float y = zb + (k + 0.5)*dp;
    if (y >= e) break;
    if (y < ylo) continue;
    if (nest && !tgt_water(set(pc.x, y, pc.z) + o, y, yb, et, 0.0)) continue;
    vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
    vector q = set(pc.x, y, pc.z) + jit;
    int p = addpoint(0, q + o);
    setpointattrib(0, "v", p, nest ? tgt_vel(q + o) : sol_vel(q.x, q.y));
}
removepoint(0, @ptnum);
''',
    "nest_probe": r'''
vector pl = set(f@px, f@py, f@pz);
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
vector P = pl + o;
f@s_t = tgt_sdf(P); v@v_t = tgt_vel(P); f@e_t = tgt_eta(P); f@w_t = tgt_w(); i@ok_t = tgt_ok();
f@wat = tgt_water(P, pl.y, bedy(pl.x, pl.z), f@e_t, 0.0);
f@wdt = nest_wdt(pl.x, pl.z, f@dts);
v@v1 = nest_apply(pl, v@v0, P, f@pt, f@dts);
f@div = vc_replay(pl);
''',
}

# ====================================================================== the target SOP (pure numpy part, also exec'd by the py -3.10 self-test)
TARGET_PURE = r'''
import os, json, math
import numpy as np
F55_FILL = {"s": 10.0, "vx": 0.0, "vy": 0.0, "vz": 0.0}


def f55_load_x(path):
    with np.load(path, allow_pickle=False) as d:
        meta = json.loads(str(d["meta"]))
        arrs = {k: np.array(d[k]) for k in d.files if k != "meta"}
    return meta, arrs


def f55_r1(a, y0, dy):
    """the runner's R1 rule: top water surface of every column of an SDF [lat, up, x] (NaN: no water)."""
    ny = a.shape[1]
    neg = a < 0
    has = neg.any(axis=1)
    jtop = ny - 1 - np.argmax(neg[:, ::-1, :], axis=1)
    jtop = np.clip(jtop, 0, ny - 2)
    iz, ix = np.meshgrid(np.arange(a.shape[0]), np.arange(a.shape[2]), indexing="ij")
    vj = a[iz, jtop, ix].astype(np.float64)
    vj1 = a[iz, jtop + 1, ix].astype(np.float64)
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    yc = y0 + dy * np.arange(ny)
    return np.where(has, yc[jtop] + dy * np.clip(frac, 0.0, 1.0), np.nan)


def f55_pad(U, p0, d, odd_lat):
    """ONE GHOST CELL on every side, so that no sample inside the data's own cells ever reaches the volume border (Houdini's default border is
    a constant 0): edge copies (= a Streak border); at the y = 0 symmetry plane this edge copy IS the even mirror of a cell-centred field (ghost
    at -d/2 = the row at +d/2); the lateral face grid of vel.z (first face at 0, odd under the mirror) gets ghost face -d = -face(+d)."""
    V = np.pad(np.asarray(U, np.float32), 1, mode="edge")
    if odd_lat and V.shape[0] > 2:
        V[0] = -V[2]
    return np.ascontiguousarray(V), [float(p0[i]) - float(d[i]) for i in range(3)]


def f55_union(meta, arrs, lat_max, bed_fn=None):
    """{key: (array [lat, up, x] float32, p0 plan (x, up, lat), d)} of every field: the file's boxes placed on the field's own lattice (no
    resampling); cells outside every box get F55_FILL (surface +10 = air, velocity 0); lateral cells beyond lat_max dropped; then one ghost
    cell on every side (f55_pad). + 'eta' (R1 top surface of the padded SDF; dry columns = the bed height bed_fn(x, lat), -1000 without one)."""
    out = {}
    boxes = sorted(set(k.split("_", 1)[0] for k in arrs))
    for key in ("s", "vx", "vy", "vz"):
        parts = []
        for b in boxes:
            k = "%s_%s" % (b, key)
            if k in arrs:
                m = meta["keys"][k]
                parts.append((np.asarray(arrs[k], np.float32), [float(v) for v in m["p0"]], [float(v) for v in m["d"]]))
        if not parts:
            raise ValueError("no box holds field %s" % key)
        d = parts[0][2]
        ref = parts[0][1]
        offs = []
        for a, p0, dd in parts:
            if any(abs(dd[i] - d[i]) > 1e-9 for i in range(3)):
                raise ValueError("boxes of %s on different grids" % key)
            oi = [int(round((p0[i] - ref[i]) / d[i])) for i in range(3)]
            if any(abs(p0[i] - (ref[i] + oi[i] * d[i])) > 1e-6 for i in range(3)):
                raise ValueError("boxes of %s not on one lattice" % key)
            offs.append(oi)
        lo = [min(o[i] for o in offs) for i in range(3)]
        hi = [max(o[i] + a.shape[2 - i] for o, (a, _, _) in zip(offs, parts)) for i in range(3)]
        n = [hi[i] - lo[i] for i in range(3)]
        U = np.full((n[2], n[1], n[0]), F55_FILL[key], np.float32)
        for o, (a, _, _) in zip(offs, parts):
            s = [o[i] - lo[i] for i in range(3)]
            U[s[2]:s[2] + a.shape[0], s[1]:s[1] + a.shape[1], s[0]:s[0] + a.shape[2]] = a
        p0u = [ref[i] + lo[i] * d[i] for i in range(3)]
        lat = p0u[2] + d[2] * np.arange(n[2])
        keep = np.where(lat <= lat_max + 1e-9)[0]
        U = np.ascontiguousarray(U[:keep[-1] + 1]) if len(keep) else U
        U, p0u = f55_pad(U, p0u, d, odd_lat=bool(key == "vz" and abs(p0u[2]) < 1e-6))
        out[key] = (U, p0u, d)
    S, p0s, ds = out["s"]
    eta = f55_r1(S, p0s[1], ds[1])
    dry = ~np.isfinite(eta)
    fill = np.full(eta.shape, -1000.0)
    if bed_fn is not None and dry.any():
        xs = p0s[0] + ds[0] * np.arange(S.shape[2])
        zs = p0s[2] + ds[2] * np.arange(S.shape[0])
        fill = np.asarray(bed_fn(xs[None, :], zs[:, None]), np.float64) * np.ones(eta.shape)
    out["eta"] = (np.where(dry, fill, eta).astype(np.float32), p0s, ds)
    out["n_dry"] = int(dry.sum())
    return out


def f55_pair(tdir, ff, lat_max, cache=None, bed_fn=None):
    """the two frames around the frame ff (fb = ceil(ff), fa = fb - 1; fa missing -> fb) assembled; t_ok = 1 iff fb's file exists."""
    fb = int(math.ceil(float(ff) - 1e-6))
    fa = fb - 1
    cache = {} if cache is None else cache

    def get(f):
        p = os.path.join(tdir, "x_%05d.npz" % f)
        if not os.path.exists(p):
            return None
        key = (p, os.path.getmtime(p), float(lat_max))
        if key not in cache:
            if len(cache) >= 4:
                cache.pop(next(iter(cache)))
            meta, arrs = f55_load_x(p)
            cache[key] = f55_union(meta, arrs, lat_max, bed_fn)
        return cache[key]
    B = get(fb)
    A = get(fa) if B is not None else None
    if B is None:
        return dict(ok=0, fa=float(fa), fb=float(fb), ff=float(ff), A=None, B=None, src="", err="no x_%05d.npz in %s" % (fb, tdir))
    if A is None:
        A, fa = B, fb
    return dict(ok=1, fa=float(fa), fb=float(fb), ff=float(ff), A=A, B=B, src="%s x_%05d / x_%05d" % (tdir, fa, fb), err="")
'''

PYSOP_TARGET = TARGET_PURE + r'''
import hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
for nm in ("t_ff", "t_fa", "t_fb"):
    geo.addAttrib(hou.attribType.Global, nm, 0.0)
geo.addAttrib(hou.attribType.Global, "t_ok", 0)
geo.addAttrib(hou.attribType.Global, "t_pad", 0)
geo.addAttrib(hou.attribType.Global, "t_src", "")
geo.addAttrib(hou.attribType.Global, "t_err", "")
geo.addAttrib(hou.attribType.Global, "t_border", "")
geo.addAttrib(hou.attribType.Prim, "name", "")
ff = float(node.evalParm("fr"))
tdir = node.evalParm("tdir")
ctrl = hou.node("/obj/G52_SETUP/CTRL")
o = [float(ctrl.evalParm("ox")), float(ctrl.evalParm("oy")), float(ctrl.evalParm("oz"))]
lat_max = float(ctrl.evalParm("W")) + 2.0
geo.setGlobalAttribValue("t_ff", ff)


def f55_bed_fn():
    """the bed height of DFG-2B-V's tank (g52b3_common.bed_z, SPEC_BED: the nest's bed; the build check compares the scene's bed with it)."""
    import sys
    for p_ in ("G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52", "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48",
               "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49", "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3"):
        if p_ not in sys.path:
            sys.path.append(p_)
    import g52b3_common as _GC
    return lambda x, z: _GC.bed_z(x, z, **_GC.SPEC_BED)


def f55_volume(arr, p0, d, name):
    """a volume whose voxel centres are p0 + i d (plan) + o; the border set to streak where the intrinsic is writable (the ghost cells
    already make every in-data sample border-free)."""
    nz, ny, nx = arr.shape
    h = [p0[i] + o[i] for i in range(3)]
    bb = hou.BoundingBox(h[0] - 0.5 * d[0], h[1] - 0.5 * d[1], h[2] - 0.5 * d[2],
                         h[0] + (nx - 0.5) * d[0], h[1] + (ny - 0.5) * d[1], h[2] + (nz - 0.5) * d[2])
    v = geo.createVolume(nx, ny, nz, bb)
    v.setAttribValue("name", name)
    v.setAllVoxelsFromString(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
    try:
        v.setIntrinsicValue("volumeborder", "streak")
        return "streak"
    except Exception:
        return "constant (ghost cells)"


if tdir:
    try:
        cache = hou.session.__dict__.setdefault("_f55_target_cache", {})
    except Exception:
        cache = {}
    try:
        R = f55_pair(tdir, ff, lat_max, cache, f55_bed_fn())
        geo.setGlobalAttribValue("t_fa", R["fa"])
        geo.setGlobalAttribValue("t_fb", R["fb"])
        geo.setGlobalAttribValue("t_src", R["src"])
        geo.setGlobalAttribValue("t_err", R["err"])
        if R["ok"]:
            borders = set()
            for tag in ("a", "b"):
                U = R["A"] if tag == "a" else R["B"]
                for key in ("s", "vx", "vy", "vz"):
                    arr, p0, d = U[key]
                    borders.add(f55_volume(arr, p0, d, "%s_%s" % (key, tag)))
                eta, p0, d = U["eta"]
                # 2-D top surface as a volume 2 voxels tall (centres at plan height -500 and +500, both = eta): any nest height samples
                # between two equal values, never toward the border
                borders.add(f55_volume(np.repeat(eta[:, None, :], 2, axis=1), [p0[0], -500.0, p0[2]], [d[0], 1000.0, d[2]], "e_%s" % tag))
            geo.setGlobalAttribValue("t_pad", 1)
            geo.setGlobalAttribValue("t_border", ",".join(sorted(borders)))
            geo.setGlobalAttribValue("t_ok", 1)
    except Exception as e:
        geo.setGlobalAttribValue("t_ok", 0)
        geo.setGlobalAttribValue("t_err", repr(e)[:500])
'''


# ====================================================================== synthetic export (same format as f55_nest.export_frame) + analytic fields
def synth_fields(f):
    """analytic fields of the synthetic frame f (plan coordinates; linear in every coordinate, so trilinear sampling is exact): surface
    s = y - eta(x, lat), eta = 0.3137 + 0.010931 (x - 180) - 0.0071129 lat + 0.0517 (f - 1056) (non-round coefficients: no lattice point lies
    exactly on the surface); velocities linear with frame-dependent coefficients."""
    k = float(f - CKPT)
    eta = lambda x, z: 0.3137 + 0.010931 * (x - 180.0) - 0.0071129 * z + 0.0517 * k
    vx = lambda x, y, z: 0.40 + 0.010 * (x - 180.0) + 0.020 * y - 0.003 * z + 0.10 * k
    vy = lambda x, y, z: -0.05 + 0.002 * (x - 180.0) - 0.010 * y + 0.001 * z - 0.02 * k
    vz = lambda x, y, z: 0.03 - 0.001 * (x - 180.0) + 0.004 * y + 0.006 * z + 0.03 * k
    return dict(eta=eta, s=lambda x, y, z: y - eta(x, z), vx=vx, vy=vy, vz=vz)


def synth_expect(F, key, X, Y=None, Z=None):
    """what OUT_TARGET must return for the synthetic field: the analytic (linear) value, except within 0.5 m of the y = 0 plane, where the
    cell-centred fields (s, vx, vy, eta: first lateral centre at 0.5 m) read their even mirror, i.e. the value at lateral 0.5 m (vel.z, lateral
    faces at 0, 1, .., is linear there), and above the top cell centre (16.5 m; vel.y faces to 17.0 m), where the edge copy holds the top value."""
    import numpy as np
    if key == "eta":
        return F["eta"](X, np.maximum(Y, 0.5))           # (x, lateral)
    Ze = Z if key == "vz" else np.maximum(Z, 0.5)
    Ye = np.minimum(Y, 17.0 if key == "vy" else 16.5)
    return F[key](X, Ye, Ze)


def write_synth_export(out_dir, frames=(1056, 1057), full_at=1056):
    """files x_<f>.npz with the export layout on a 1 m lattice like the parent's (cell centres k + 0.5; vel.x faces at integer x, vel.y faces at
    integer y, vel.z faces at integer lateral), boxes xb / yb (and nb = the whole nest box at full_at)."""
    import numpy as np
    os.makedirs(out_dir, exist_ok=True)
    boxes = dict(xb=dict(x=[178.0, 199.0], y=[0.0, 140.0]), yb=dict(x=[180.0, 356.0], y=[41.0, 62.0]), eb=dict(x=[339.0, 358.0], y=[0.0, 62.0]))
    grid = {"s": ((0.5, -20.5, 0.5), (412, 38, 140)), "vx": ((0.0, -20.5, 0.5), (413, 38, 140)),
            "vy": ((0.5, -21.0, 0.5), (412, 39, 140)), "vz": ((0.5, -20.5, 0.0), (412, 38, 141))}
    names = {"s": "surface", "vx": "vel.x", "vy": "vel.y", "vz": "vel.z"}
    paths = []
    for f in frames:
        F = synth_fields(f)
        bx = dict(boxes)
        if f == full_at:
            bx["nb"] = dict(x=[178.0, 358.0], y=[0.0, 62.0])
        arrs, meta = {}, dict(frame=int(f), t=(f - 1) / FPS, o_parent=[0.5, 0.5, 0.5], boxes=bx, keys={}, kind="SYNTHETIC export (build check)")
        for bname, box in bx.items():
            for key, (p0, res) in grid.items():
                ix = [i for i in range(res[0]) if box["x"][0] - 1e-6 <= p0[0] + i <= box["x"][1] + 1e-6]
                iz = [k for k in range(res[2]) if box["y"][0] - 1e-6 <= p0[2] + k <= box["y"][1] + 1e-6]
                xs = p0[0] + np.array(ix, float); ys = p0[1] + np.arange(res[1], dtype=float); zs = p0[2] + np.array(iz, float)
                Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
                a = F[key](X, Y, Z)
                dt = np.float32 if key == "s" else np.float16
                arrs["%s_%s" % (bname, key)] = a.astype(dt)
                meta["keys"]["%s_%s" % (bname, key)] = dict(p0=[float(xs[0]), p0[1], float(zs[0])], d=[1.0, 1.0, 1.0], shape=list(a.shape),
                                                           dtype=np.dtype(dt).name, field=names[key])
        p = os.path.join(out_dir, "x_%05d.npz" % f).replace("\\", "/")
        with open(p, "wb") as fh:
            np.savez_compressed(fh, meta=np.array(json.dumps(meta)), **arrs)
        paths.append(p)
    with open(os.path.join(out_dir, "vd_%05d.txt" % (frames[-1])), "w") as fh:
        fh.write("%r %r %r\n" % (3.25e-05, 0.0, 0.0))
    return paths


def end_w_np(x, dts, P):
    """numpy mirror of the VEX end_w (the optional end band)."""
    if P.get("end_on", 0.0) < 0.5:
        return 0.0
    L = P["end_band_m"]; x1 = P["x0"] + P["Lx"]
    if L <= 0.0 or x <= x1 - L:
        return 0.0
    c = min(max((x - (x1 - L)) / L, 0.0), 1.0)
    w = min(max((math.exp(c ** 3.5) - 1.0) / (math.e - 1.0) * P["relax_g"], 0.0), 1.0)
    return 1.0 - (1.0 - w) ** (dts / P["dt0"])


def nest_apply_np(TB50, x, yv, zl, v0, tv_raw, t, dts, P):
    """numpy mirror of the VEX nest_apply (horizontal unless relax_vert) with the raw parent velocity tv_raw at the point."""
    wdt, ftg, inb, insd = TB50.bands_np(x, zl, dts, P)
    w = max(wdt, end_w_np(x, dts, P))
    v0 = [float(c) for c in v0]
    if w <= 0.0:
        return v0, w
    wt, ws = TB50.tapers_np(x, zl, P)
    gm = (P["in_gain"] if inb else P["sd_gain"]) * ftg * wt * ws * TB50.rampT(t, P["ramp_s"])
    tv = [gm * c for c in tv_raw]
    vy = v0[1] + (tv[1] - v0[1]) * w if P.get("relax_vert", 0.0) > 0.5 else v0[1]
    return [v0[0] + (tv[0] - v0[0]) * w, vy, v0[2] + (tv[2] - v0[2]) * w], w


def water_np(sdf, y, yb, e, s_off, bed_trust, m=0.0):
    """numpy mirror of the VEX tgt_water."""
    import numpy as np
    return (np.asarray(sdf) + s_off < -m) | ((np.asarray(y) - yb < bed_trust) & (np.asarray(y) < np.asarray(e) - s_off - m))


def numpy_init_count(sdf_fn, eta_fn, dp, x0, Lx, W, zb, bed_gap=0.5, vox=None, s_off=0.0, bed_trust=0.0):
    """the init_particles rule (nest_on 1) in numpy: lattice points that are the parent's water (water_np: sdf + s_off < 0 at the lattice
    point, or y - bed < bed_trust and y < eta - s_off), with y >= bed + bed_gap dp and y < eta + vox."""
    import numpy as np
    sys.path.insert(0, T52B3)
    import g52b3_common as GC
    vox = vox if vox is not None else 2.0 * dp
    xs = x0 + (np.arange(int(math.floor(Lx / dp + 1e-6))) + 0.5) * dp
    zs = (np.arange(int(math.floor(W / dp + 1e-6))) + 0.5) * dp
    n = 0
    for z in zs:
        bed = GC.bed_z(xs, z, **GC.SPEC_BED)
        e = eta_fn(xs, z)
        k_lo = np.maximum(np.ceil((bed + bed_gap * dp - zb) / dp - 0.5 - 1e-9), 0).astype(int)
        k_hi = np.ceil((e + vox - zb) / dp - 0.5 - 1e-9).astype(int)
        for i, x in enumerate(xs):
            if k_hi[i] <= k_lo[i]:
                continue
            ys = zb + (np.arange(k_lo[i], k_hi[i]) + 0.5) * dp
            sd = sdf_fn(np.full_like(ys, x), ys, np.full_like(ys, z))
            n += int(water_np(sd, ys, bed[i], e[i], s_off, bed_trust).sum())
    return n


# ====================================================================== numpy self-test of the scene code (py -3.10; no Houdini)
def balanced(s):
    return s.count("{") == s.count("}") and s.count("(") == s.count(")") and s.count("[") == s.count("]")


def vsample_const0(arr, p0, d, X, Y, Z):
    """numpy emulation of VEX volumesample on a volume [lat, up, x] with voxel centres p0 + i d and Houdini's default CONSTANT 0 border:
    trilinear between voxel centres, toward 0 beyond the outermost centre."""
    import numpy as np
    A = np.pad(np.asarray(arr, np.float64), 1, mode="constant", constant_values=0.0)
    q0 = [p0[i] - d[i] for i in range(3)]
    f = [(np.asarray(V, float) - q0[a]) / d[a] for a, V in enumerate((X, Y, Z))]
    n = (A.shape[2], A.shape[1], A.shape[0])
    ii = [np.clip(np.floor(f[a]).astype(int), 0, n[a] - 2) for a in range(3)]
    ww = [np.clip(f[a] - ii[a], 0.0, 1.0) for a in range(3)]
    out = 0.0
    for dk in (0, 1):
        for dj in (0, 1):
            for di in (0, 1):
                out = out + A[ii[2] + dk, ii[1] + dj, ii[0] + di] * (ww[0] if di else 1 - ww[0]) * (ww[1] if dj else 1 - ww[1]) * (ww[2] if dk else 1 - ww[2])
    return out


def selftest_numpy(out_dir):
    import numpy as np
    ok, det = {}, {}
    # 1. VEX text: balanced, every CTRL name used exists
    for nm, body in [("NEST_VEX", NEST_VEX)] + list(BODIES_NEST.items()):
        ok["vex_balanced_" + nm] = balanced(body)
    import re
    used = set(re.findall(r'ch[fs]?\(CT\+"(\w+)"\)', NEST_VEX + "".join(BODIES_NEST.values())))
    have = set(dfgbv_parm_names()) | set(n for n, _, _ in NEST_PARMS) | set(n for n, _, _ in NEST_STR_PARMS)
    ok["vex_ctrl_names_exist"] = bool(used <= have)
    det["vex_ctrl_names_missing"] = sorted(used - have)
    sys.path.insert(0, HERE)
    import f55_nest as FN
    ok["launch_parms_on_ctrl"] = bool(set(FN.LAUNCH_PARMS) <= set(n for n, _, _ in NEST_PARMS)
                                      and set(FN.LAUNCH_STR_PARMS) <= set(n for n, _, _ in NEST_STR_PARMS)
                                      and set(FN.OVERRIDE_PARMS) <= set(dfgbv_parm_names()))
    compile(PYSOP_TARGET, "PYSOP_TARGET", "exec")
    ok["pysop_compiles"] = True
    # 2. the target assembly on synthetic files (the same text the Python SOP runs)
    write_synth_export(out_dir)
    ns = {}
    exec(compile(TARGET_PURE, "TARGET_PURE", "exec"), ns)
    R = ns["f55_pair"](out_dir, 1056.5, 62.0)
    ok["pair_frames"] = bool(R["ok"] == 1 and R["fa"] == 1056.0 and R["fb"] == 1057.0)
    R0 = ns["f55_pair"](out_dir, 1056.0, 62.0)
    ok["pair_creation_frame_fallback"] = bool(R0["ok"] == 1 and R0["fa"] == R0["fb"] == 1056.0)
    Rn = ns["f55_pair"](out_dir, 1060.0, 62.0)
    ok["pair_missing_not_ok"] = bool(Rn["ok"] == 0)
    errs = {}
    for tag, f in (("A", 1056), ("B", 1057)):
        F = synth_fields(f)
        U = R[tag]
        for key in ("s", "vx", "vy", "vz"):
            arr, p0, d = U[key]
            arr = arr[1:-1, 1:-1, 1:-1]                       # the data cells (the ghost cells are checked below)
            q0 = [p0[i] + d[i] for i in range(3)]
            xs = q0[0] + d[0] * np.arange(arr.shape[2]); ys = q0[1] + d[1] * np.arange(arr.shape[1]); zs = q0[2] + d[2] * np.arange(arr.shape[0])
            # band cells only (inside xb or yb): exact up to the storage dtype
            Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
            inb = ((X <= 199.0) | (Z >= 41.0)) & (Z <= 62.0)
            ref = F[key](X, Y, Z)
            errs["%s_%s" % (tag, key)] = float(np.abs(arr[inb] - ref[inb]).max() / max(1.0, np.abs(ref[inb]).max()))
        eta, p0, d = U["eta"]
        eta = eta[1:-1, 1:-1]
        xs = p0[0] + d[0] * (1 + np.arange(eta.shape[1])); zs = p0[2] + d[2] * (1 + np.arange(eta.shape[0]))
        Xe, Ze = np.meshgrid(xs, zs)
        inb = (Xe <= 199.0) | (Ze >= 41.0)
        errs["%s_eta" % tag] = float(np.abs(eta[inb] - F["eta"](Xe, Ze)[inb]).max())
        full = bool(np.all(U["s"][0][:, :, :] != ns["F55_FILL"]["s"])) if tag == "A" else None
        det["frame_%d_full_box" % f] = full
    ok["assembly_values"] = bool(all(v < 2e-3 for k, v in errs.items() if not k.endswith("_s") and not k.endswith("_eta"))
                                 and all(v < 1e-5 for k, v in errs.items() if k.endswith("_s")) and all(v < 1e-4 for k, v in errs.items() if k.endswith("_eta")))
    det["assembly_rel_errors"] = errs
    ok["frame_1056_full_box"] = bool(det["frame_1056_full_box"])
    ok["frame_1057_interior_filled"] = bool(np.any(R["B"]["s"][0] == ns["F55_FILL"]["s"]))
    ok["lateral_trimmed"] = bool(R["B"]["s"][1][2] + R["B"]["s"][2][2] * (R["B"]["s"][0].shape[0] - 2) <= 62.0 + 1e-9)
    # 2b. ghost cells (review 2026-10-19 B2): even mirror / edge copy for cell-centred fields, odd mirror for the vel.z face grid at y = 0
    A = R["A"]
    ok["ghost_lateral_even_s"] = bool(abs(A["s"][1][2] + 0.5) < 1e-9 and np.array_equal(A["s"][0][0], A["s"][0][1]))
    ok["ghost_lateral_odd_vz"] = bool(abs(A["vz"][1][2] + 1.0) < 1e-9 and np.array_equal(A["vz"][0][0], -A["vz"][0][2]))
    ok["ghost_all_sides"] = bool(all(np.array_equal(A["s"][0][:, :, 0], A["s"][0][:, :, 1]) and np.array_equal(A["s"][0][:, -1, :], A["s"][0][:, -2, :])
                                     and np.array_equal(A["s"][0][-1], A["s"][0][-2]) for _ in (0,)))
    # Houdini volumesample with its default constant-0 border, emulated: the padded layout is exact at lateral 0-0.5 m; the old layout
    # (no ghost cells, 1-voxel e volume) was not
    rng = np.random.RandomState(7)
    Xq = rng.uniform(180.5, 198.5, 300); Yq = rng.uniform(-12.0, 3.0, 300); Zq = rng.uniform(0.02, 0.48, 300)
    Fa = synth_fields(1056)
    perr, oerr = {}, {}
    for key in ("s", "vx", "vy", "vz"):
        arr, p0, d = A[key]
        got = vsample_const0(arr, p0, d, Xq, Yq, Zq)
        perr[key] = float(np.abs(got - synth_expect(Fa, key, Xq, Yq, Zq)).max())
        old = vsample_const0(arr[1:-1, 1:-1, 1:-1], [p0[i] + d[i] for i in range(3)], d, Xq, Yq, Zq)
        oerr[key] = float(np.abs(old - synth_expect(Fa, key, Xq, Yq, Zq)).max())
    eta, p0, d = A["eta"]
    e2 = np.repeat(eta[:, None, :], 2, axis=1)
    got = vsample_const0(e2, [p0[0], -500.0, p0[2]], [d[0], 1000.0, d[2]], Xq, Yq, Zq)
    perr["eta"] = float(np.abs(got - synth_expect(Fa, "eta", Xq, Zq)).max())
    old = vsample_const0(eta[1:-1, None, 1:-1], [p0[0] + d[0], 0.0, p0[2] + d[2]], [d[0], 2000.0, d[2]], Xq, Yq, Zq)
    oerr["eta"] = float(np.abs(old - synth_expect(Fa, "eta", Xq, Zq)).max())
    ok["border_free_near_plane"] = bool(perr["s"] < 1e-5 and perr["eta"] < 1e-4 and all(perr[k] < 2e-3 for k in ("vx", "vy", "vz")))
    det["border_emulation_max_err_padded"] = perr
    det["border_emulation_max_err_old_layout"] = oerr
    # 2c. dry columns: the eta of a column without water = the bed height (not -1000: bilinear next to it would fall to ~ -500)
    meta1, arrs1 = ns["f55_load_x"](out_dir + "/x_01057.npz")
    arrs_dry = dict(arrs1)
    arrs_dry["yb_s"] = np.array(arrs1["yb_s"], copy=True)
    arrs_dry["yb_s"][:, :, -3:] = 5.0                       # the last 3 x columns of box yb: air everywhere
    sys.path.insert(0, HERE)
    import f55_common as C55
    Ud = ns["f55_union"](meta1, arrs_dry, 62.0, C55.bed_z)
    ed, pe, de = Ud["eta"]
    xs = pe[0] + de[0] * np.arange(ed.shape[1]); zs = pe[2] + de[2] * np.arange(ed.shape[0])
    jx = int(np.argmin(np.abs(xs - 355.5))); jz = int(np.argmin(np.abs(zs - 50.5)))
    ok["dry_column_eta_is_bed"] = bool(Ud["n_dry"] > 0 and abs(float(ed[jz, jx]) - float(C55.bed_z(np.array([355.5]), np.array([50.5]))[0])) < 1e-4)
    # 2d. the water rule mirror (tgt_water): particle level = SDF zero - s_off; near the bed the top surface decides
    so = FN.STILL_OFFSET
    ok["water_rule_mirror"] = bool(water_np(-0.08, 0.0, -5.0, 0.0, so, 1.0) and not water_np(-0.07, 0.0, -5.0, 0.0, so, 1.0)
                                   and water_np(+0.3, -4.5, -5.0, 0.0, so, 1.0) and not water_np(+0.3, -4.5, -5.0, -4.6, so, 1.0)
                                   and not water_np(+0.3, -3.5, -5.0, 0.0, so, 1.0))
    # 2e. VEX text: the water rule everywhere, the draw before the neighbour query, seeds copied from a nest particle, no wall / end taper
    sb = BODIES_NEST["band_seed"]
    ok["vex_water_rule_used"] = bool(all("tgt_water(" in BODIES_NEST[k] for k in ("band_kill", "band_seed", "init_particles"))
                                     and "tgt_sdf(q) >" not in sb and ">= 0.0) continue" not in BODIES_NEST["init_particles"])
    ok["vex_draw_before_query"] = bool(sb.index("nest_draw(") < sb.index("nearpoints(") and "addpoint(0, tp)" in sb and '"id", p' in sb)
    ok["vex_no_end_taper"] = bool("end_taper" not in NEST_VEX and "end_taper" not in "".join(BODIES_NEST.values()))
    # 3. the band weights: DFG-2B-V's numpy mirror (g50_table.bands_np) on the nest parms
    P = nest_parms_for_mirror()
    sys.path.insert(0, T50)
    sys.path.insert(0, T52)
    import g50_table as TB50
    w = lambda x, z, dts=1.0 / 24.0: TB50.bands_np(x, z, dts, P)[0]
    ok["band_wall_weights"] = bool(abs(w(180.0, 10.0) - 1.0) < 1e-12 and abs(w(195.0 - 1e-9, 10.0)) < 1e-6 and w(200.0, 10.0) == 0.0
                                   and abs(w(250.0, 60.0) - 1.0) < 1e-12 and abs(w(250.0, 45.0 + 1e-9)) < 1e-6 and w(250.0, 30.0) == 0.0)
    ok["band_corner_max"] = bool(abs(w(185.0, 55.0) - max(w(185.0, 10.0), w(250.0, 55.0))) < 1e-12)
    wt, ws = TB50.tapers_np(180.0, 10.0, P)
    wt2, _ = TB50.tapers_np(195.0, 10.0, P)
    ok["walltaper_off_target_full_at_face"] = bool(P["wall_taper_m"] == 0.0 and wt == 1.0 and wt2 == 1.0 and ws == 1.0)
    # nest_apply at the face: weight 1 -> the parent's velocity itself (with the frozen 15 m taper it was 0 there and 0.18 x at 4 m)
    v_face, w_face = nest_apply_np(TB50, 180.25, -2.0, 10.0, (0.0, 0.0, 0.0), (1.0, 0.0, 0.3), 44.0, 1.0 / 24.0, P)
    v4_15, _ = nest_apply_np(TB50, 184.0, -2.0, 10.0, (0.0, 0.0, 0.0), (1.0, 0.0, 0.3), 44.0, 1.0 / 24.0, dict(P, wall_taper_m=15.0))
    ok["band_target_is_parent_velocity"] = bool(abs(v_face[0] - w_face) < 1e-12 and abs(v_face[2] - 0.3 * w_face) < 1e-12 and w_face > 0.9)
    det["frozen_15m_taper_at_4m"] = dict(u_after_one_frame=v4_15[0], weight=w(184.0, 10.0))
    Pe = dict(P, end_on=1.0)
    ok["end_band_off_by_default"] = bool(P.get("end_on") == 0.0 and end_w_np(355.9, 1.0 / 24.0, P) == 0.0)
    ok["end_band_weights_when_on"] = bool(abs(end_w_np(356.0, 1.0 / 24.0, Pe) - 1.0) < 1e-12 and end_w_np(341.0, 1.0 / 24.0, Pe) == 0.0)
    det["band_samples"] = {"%g_%g" % (x, z): w(x, z) for x, z in ((180, 10), (184, 10), (188, 10), (192, 10), (250, 50), (250, 55), (250, 58))}
    # 4. the build-check writer on a fake raw record
    fake = dict(items={k: dict(ok=True) for k in RAW_ITEMS}, hip_sha256="0" * 64, smoke=None, houdini="test")
    bc = compose_build_check(fake, smoke_requested=False)
    ok["writer_all_ok_without_smoke"] = bool(bc["all_ok"] is True and bc["smoke_ok"] is None)
    fake2 = copy.deepcopy(fake)
    fake2["items"]["band_probe"]["ok"] = False
    ok["writer_fails_on_item"] = bool(compose_build_check(fake2, smoke_requested=False)["all_ok"] is False)
    bc3 = compose_build_check(fake, smoke_requested=True)
    ok["writer_smoke_missing_fails"] = bool(bc3["all_ok"] is False and bc3["smoke_ok"] is False)
    fake4 = dict(fake, smoke=dict(ok=True))
    ok["writer_smoke_needs_py_side"] = bool(compose_build_check(fake4, True, dict(ok=False))["all_ok"] is False
                                            and compose_build_check(fake4, True, dict(ok=True))["all_ok"] is True)
    fake5 = dict(fake, error="boom")
    ok["writer_fails_on_error"] = bool(compose_build_check(fake5, False)["all_ok"] is False)
    return dict(ok=bool(all(ok.values())), checks=ok, detail=det)


def nest_parms_for_mirror():
    """the C2ID launch parms as plain floats (the numpy mirror input)."""
    sys.path.insert(0, HERE)
    import f55_nest as FN
    L, _ = FN.launch_cfg("C2ID", for_smoke=True)
    return {k: float(v) for k, v in L["parms"].items() if isinstance(v, (int, float))}


def dfgbv_parm_names():
    with open(DFGBV_READY, encoding="utf-8") as fh:
        return list(json.load(fh)["parms"].keys())


# ====================================================================== the build-check writer (py -3.10)
RAW_ITEMS = ("ctrl_superset", "bed_C2ID", "bed_C2", "still_particles", "target_probe_integer", "target_probe_half", "band_probe", "replay_probe",
             "init_particles", "init_no_target", "dop_setup", "saved_defaults")


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def compose_build_check(raw, smoke_requested, smoke_py=None):
    """build_check55_nest.json from the hython raw record (+ the py-side smoke comparisons). all_ok = every RAW_ITEMS item ok, no build error,
    and (smoke requested) smoke_ok."""
    items = raw.get("items") or {}
    miss = [k for k in RAW_ITEMS if not (items.get(k) or {}).get("ok")]
    sm = raw.get("smoke")
    smoke_ok = None
    if smoke_requested:                     # the hython smoke AND the py-side comparisons must both be ok (a missing one fails)
        smoke_ok = bool(sm and sm.get("ok") and smoke_py is not None and smoke_py.get("ok"))
    bc = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), kind="FLIP55 nest scene build check (x55_nest_build.py)", hip=HIP.replace(REPO + "/", ""),
              hip_sha256=raw.get("hip_sha256"), houdini=raw.get("houdini"), items=items, failed_items=miss, error=raw.get("error"),
              smoke_requested=bool(smoke_requested), smoke=sm, smoke_py=smoke_py, smoke_ok=smoke_ok,
              tool_sha256={p: sha(REPO + "/" + p) for p in NEST_TOOLS}, raw=RAW.replace(REPO + "/", ""))
    bc["all_ok"] = bool(not miss and not raw.get("error") and raw.get("hip_sha256") and (smoke_ok if smoke_requested else True))
    return bc


def smoke_py_checks(raw):
    """py-side smoke comparisons: the init count vs numpy on the REAL x_01056.npz (trilinear of the parent's SDF at the nest lattice points),
    and the nest's column volume vs the parent's hf on the smoke frames (report + 5 % sanity), the band-edge rms (report)."""
    import numpy as np
    sys.path.insert(0, HERE)
    import f55_nest as FN
    sm = raw.get("smoke") or {}
    out = {}
    try:
        import f55_common as C55
        meta, A = FN.load_x(np, FN.EXPORT_DIR + "/x_%05d.npz" % CKPT)
        ns = {}
        exec(compile(TARGET_PURE, "TARGET_PURE", "exec"), ns)
        U = ns["f55_union"](meta, A, NEST_BOX["W"] + 2.0, C55.bed_z)
        E, pe, de = U["eta"]

        def trif(key):
            S, p0, d = U[key]

            def tri(x, y, z):                                   # clamped trilinear = volumesample on the padded volume
                fx = (x - p0[0]) / d[0]; fy = (y - p0[1]) / d[1]; fz = (z - p0[2]) / d[2]
                i = np.clip(np.floor(fx).astype(int), 0, S.shape[2] - 2); j = np.clip(np.floor(fy).astype(int), 0, S.shape[1] - 2)
                k = np.clip(np.floor(fz).astype(int), 0, S.shape[0] - 2)
                wx, wy, wz = np.clip(fx - i, 0, 1), np.clip(fy - j, 0, 1), np.clip(fz - k, 0, 1)
                c = 0.0
                for dk in (0, 1):
                    for dj in (0, 1):
                        for di in (0, 1):
                            c = c + S[k + dk, j + dj, i + di] * (wx if di else 1 - wx) * (wy if dj else 1 - wy) * (wz if dk else 1 - wz)
                return c
            return tri
        tri = trif("s")

        def etaf(x, z):
            fx = (x - pe[0]) / de[0]; fz = (z - pe[2]) / de[2]
            i = np.clip(np.floor(fx).astype(int), 0, E.shape[1] - 2); k = int(np.clip(math.floor(fz), 0, E.shape[0] - 2))
            wx = np.clip(fx - i, 0, 1); wz = min(max(fz - k, 0.0), 1.0)
            return (1 - wz) * ((1 - wx) * E[k, i] + wx * E[k, i + 1]) + wz * ((1 - wx) * E[k + 1, i] + wx * E[k + 1, i + 1])
        Lp = FN.LAUNCH_PARMS
        n_np = numpy_init_count(tri, etaf, NEST_BOX["dp"], NEST_BOX["x0"], NEST_BOX["Lx"], NEST_BOX["W"], NEST_BOX["zb"],
                                s_off=float(Lp["s_off"]), bed_trust=float(Lp["bed_trust_m"]))
        n_h = int(sm.get("particles_init") or 0)
        out["init_count"] = dict(houdini=n_h, numpy=n_np, rel=(n_h / n_np - 1.0) if n_np else None,
                                 ok=bool(n_np and abs(n_h / n_np - 1.0) <= 0.005))
        # the initial velocity the FLIP object kept: particle v at frame 1056 vs the parent's grid velocity at the particle
        pv = sm.get("p1056")
        if pv and os.path.exists(pv):
            with np.load(pv) as dd:
                Pp, Vp = np.array(dd["P"], float), np.array(dd["v"], float)
            ref = np.stack([trif(k)(Pp[:, 0], Pp[:, 1], Pp[:, 2]) for k in ("vx", "vy", "vz")], 1)
            dv = np.linalg.norm(Vp - ref, axis=1)
            out["init_velocity"] = dict(n=int(len(dv)), mean_abs_dv=float(dv.mean()), p99_abs_dv=float(np.percentile(dv, 99)),
                                        mean_speed_parent=float(np.linalg.norm(ref, axis=1).mean()), ok=bool(len(dv) > 100 and dv.mean() < 0.05))
        else:
            out["init_velocity"] = dict(ok=False, why="no particle sample of frame 1056 in the smoke record")
    except Exception as e:
        out["init_count"] = dict(ok=False, error=repr(e)[:300])
    try:
        H = FN.HF(DFGBV_RUN)
        import f55_common as C
        rows = []
        for f, path in sorted((int(k), v) for k, v in (sm.get("eta_files") or {}).items()):
            with np.load(path) as dd:
                en = np.array(dd["eta"]); mn = json.loads(str(dd["meta"]))
            ep, mp = H.get(f)
            vp, _, _ = FN.column_volume(np, ep, mp, C.bed_z)
            vn, _, _ = FN.column_volume(np, en, mn, C.bed_z)
            xq, yq = FN.edge_cells()
            a = FN.eta_at(np, ep, mp, xq, yq); b = FN.eta_at(np, en, mn, xq, yq)
            okm = np.isfinite(a) & np.isfinite(b)
            rows.append(dict(frame=f, V_rel=vn / vp - 1.0, edge_rms_m=float(np.sqrt(np.mean((b[okm] - a[okm]) ** 2))) if okm.any() else None))
        out["frames"] = rows
        out["volume_ok"] = bool(rows and all(abs(r["V_rel"]) <= 0.05 for r in rows))
    except Exception as e:
        out["frames_error"] = repr(e)[:300]
        out["volume_ok"] = False
    out["ok"] = bool((out.get("init_count") or {}).get("ok") and (out.get("init_velocity") or {}).get("ok") and out.get("volume_ok"))
    out["rule"] = ("init count within 0.5 % of numpy on the real x_01056.npz; initial particle velocity vs the parent's grid velocity mean |dv| "
                   "< 0.05 m/s; nest column volume within 5 % of the parent's on every smoke frame (a sanity check only: GN3 decides at +-2 % "
                   "on the full C2ID run); band-edge rms reported")
    return out


# ====================================================================== py -3.10 launcher
def preflight():
    sys.path.insert(0, HERE)
    import f55_common as C
    import f55_nest as FN
    ck = {}
    ck["plan_sha_ok"] = bool(C.plan_sha_ok())
    ck["tools_present"] = bool(all(os.path.exists(REPO + "/" + p) for p in NEST_TOOLS))
    ck["g52_tanklib_present"] = os.path.exists(T52 + "/g52_tanklib.py")
    b = C.box(NEST_BOX["dp"], NEST_BOX["x0"], NEST_BOX["Lx"], NEST_BOX["W"], NEST_BOX["zb"])
    ck["nest_box_as_plan"] = bool(b["Lx"] == NEST_BOX["Lx"] and b["W"] == NEST_BOX["W"] and b["Hz"] == NEST_BOX["Hz"]
                                  and [b["ox"], b["oy"], b["oz"]] == [NEST_BOX["ox"], NEST_BOX["oy"], NEST_BOX["oz"]])
    L, _ = FN.launch_cfg("C2ID", for_smoke=True)
    ck["nest_bands_as_cfg"] = bool(all(float(L["parms"][k]) == float(v) for k, v in NEST_BANDS.items()))
    ck["hip_path_flip55"] = bool(HIP.startswith(REPO + "/Houdini/FLIP55/") and os.path.basename(HIP) == "f55_nest.hiplc")
    return dict(ok=bool(all(ck.values())), checks=ck)


def write_smoke_cfg():
    sys.path.insert(0, HERE)
    import f55_nest as FN
    L, _ = FN.launch_cfg("C2ID", for_smoke=True)
    sm = dict(parms=L["parms"], solver=L["solver"], frames=[CKPT, CKPT + SMOKE_FRAMES], ckpt_dir=SMOKE_DIR + "/ckpt", out_dir=SMOKE_DIR,
              ckpt_every=12, export_dir=FN.EXPORT_DIR, note="the C2ID launch parms (f55_nest.launch_cfg) for the build smoke; nothing judged")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(SMOKE_CFG, "w", encoding="utf-8") as fh:
        json.dump(sm, fh, indent=1, ensure_ascii=False, default=float)
    return sm


def launcher(argv):
    """every path ends with ONE json line with "ok" (also on an exception: ok false + why)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        return launcher_body(argv)
    except BaseException as e:                     # SystemExit / TimeoutExpired / anything: the caller still gets its json line
        if isinstance(e, KeyboardInterrupt):
            raise
        print(json.dumps(dict(ok=False, step="x55_nest_build", why="%s: %s" % (type(e).__name__, str(e)[:600]))), flush=True)
        return 2


def launcher_body(argv):
    smoke = "--smoke" in argv
    sim = "--simulate" in argv or "--dry" in argv
    pf = preflight()
    sys.path.insert(0, T52B3)
    import g52b3_common as GC
    cmd = [GC.HY, os.path.abspath(__file__).replace("\\", "/"), "--hython"] + (["--smoke"] if smoke else [])
    if sim:
        st = selftest_numpy(SIM_DIR + "/xb_selftest")
        o = dict(ok=bool(pf["ok"] and st["ok"]), step="x55_nest_build", simulate=True, preflight=pf, selftest=st["checks"], would_run=" ".join(cmd),
                 env="HOUDINI_TEMP_DIR=TEMP=TMP=%s" % TMP_HOUDINI.replace(REPO + "/", ""), writes=[HIP.replace(REPO + "/", ""),
                                                                                                    BUILD_CHECK.replace(REPO + "/", "")],
                 smoke_needs=("the real export (f55_nest.py export ok) for --smoke" if smoke else None))
        os.makedirs(SIM_DIR, exist_ok=True)
        with open(SIM_DIR + "/build_check55_nest.sim.json", "w", encoding="utf-8") as fh:
            json.dump(dict(o, all_ok=None, note="simulation: no hython, nothing built"), fh, indent=1, ensure_ascii=False, default=str)
        print(json.dumps(o, ensure_ascii=False, default=str))
        return 0 if o["ok"] else 1
    if not pf["ok"]:
        print(json.dumps(dict(ok=False, step="x55_nest_build", why="preflight", preflight=pf)))
        return 2
    sys.path.insert(0, HERE)
    import f55_nest as FN
    if smoke:
        if not (FN.jtry(FN.EXPORT_JSON) or {}).get("ok"):
            print(json.dumps(dict(ok=False, step="x55_nest_build", why="--smoke needs the parent export (f55_nest.py export ok)")))
            return 2
    # the machine must be free (no other pipeline / hython / Unity batch, no foreign auto_F55) with the C2ID commit and disk need
    eg = FN.entry_guard("x55_nest_build", "C2ID", wait_min=float(FN.opts(argv)[1].get("wait-min", 20)))
    if not eg["ok"]:
        print(json.dumps(dict(ok=False, step="x55_nest_build", why="entry guard: %s" % eg["why"], guard=eg), ensure_ascii=False, default=str))
        return 2
    if smoke:
        write_smoke_cfg()
    GC.wait_no_hython(log=lambda *a: print(*a, flush=True))
    os.makedirs(TMP_HOUDINI, exist_ok=True)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP_HOUDINI, TEMP=TMP_HOUDINI, TMP=TMP_HOUDINI)
    if os.path.exists(RAW):
        os.remove(RAW)
    with open(LOG_DIR + "/build55_nest.log", "a", encoding="utf-8") as lf:
        lf.write("\n=== %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(cmd)))
        lf.flush()
        r = subprocess.run(cmd, cwd=REPO, env=env, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=2 * 3600)
    raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else dict(error="no raw record (hython rc %s; see _logs/build55_nest.log)" % r.returncode)
    smoke_py = smoke_py_checks(raw) if smoke and raw.get("smoke") else (dict(ok=False, why="no smoke record") if smoke else None)
    bc = compose_build_check(raw, smoke, smoke_py)
    bc["hython_rc"] = r.returncode
    with open(BUILD_CHECK, "w", encoding="utf-8") as fh:
        json.dump(bc, fh, indent=1, ensure_ascii=False, default=str)
    print(json.dumps(dict(ok=bc["all_ok"], step="x55_nest_build", build_check=BUILD_CHECK.replace(REPO + "/", ""), hip_sha256=bc.get("hip_sha256"),
                          failed_items=bc["failed_items"], smoke_ok=bc.get("smoke_ok"), error=bc.get("error")), ensure_ascii=False, default=str))
    return 0 if bc["all_ok"] else 1


# ====================================================================== hython: the scene, its checks and the smoke
def hython_build(smoke=False):
    import hou
    import numpy as np
    for p in (T52, T52B3):
        if p not in sys.path:
            sys.path.insert(0, p)
    import g52_tanklib as L
    import g52b3_common as GC
    sys.path.insert(0, HERE)
    import f55_common as C
    raw = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), houdini=hou.applicationVersionString(), items={}, tool=TOOL_REL)
    HEAD = L.VEX_HEAD + NEST_VEX

    def item(name, d):
        raw["items"][name] = d
        print("ITEM", name, json.dumps({k: v for k, v in d.items() if not isinstance(v, (list, dict))}, default=str)[:600], flush=True)

    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    setup = obj.createNode("geo", "G52_SETUP")
    for c_ in setup.children():
        c_.destroy()
    ctrl = setup.createNode("null", "CTRL")
    ptg = ctrl.parmTemplateGroup()
    _bp = GC.bed_parms(dict(GC.SPEC_BED))
    B0 = NEST_BOX
    PARMS = [("dp", B0["dp"]), ("gridscale", 2.0), ("x0", B0["x0"]), ("Lx", B0["Lx"]), ("W", B0["W"]), ("zb", B0["zb"]), ("Hz", B0["Hz"]),
             ("h0", GC.H0), ("maxsub", 8.0), ("minsub", 1.0), ("cfl", 1.0), ("pcfl", 0.75), ("t_off", 0.0), ("ox", B0["ox"]), ("oy", B0["oy"]),
             ("oz", B0["oz"])] + [(k, _bp[k]) for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h", "ridge_kend", "ridge_xk1",
                                                        "ridge_xk2", "ch_h", "ch_y0", "ch_w", "ch_x0", "ch_lx")] + \
            [("ledge_s1", 0.0), ("ledge_dl", 0.0), ("ledge_s2", 0.0)] + [(k, _bp[k]) for k in ("pg_hL", "pg_s2", "b_end", "b_x1", "b_x2", "lag_xb",
                                                                                               "lag_s", "lag_h")] + \
            [("bed_gap", 0.5), ("floor_pad", 2.0), ("wave_on", 0.0), ("side_pad", 0.0), ("relax_on", 0.0), ("abs_on", 0.0), ("sf_on", 0.0),
             ("dir_on", 0.0), ("dir_tf", GC.T_F), ("ret_on", 0.0), ("sd_on", 0.0), ("sd0", NEST_BANDS["sd0"]), ("sd_gen", NEST_BANDS["sd_gen"]),
             ("sd_sw", NEST_BANDS["sd_sw"]), ("sd_sigma", GC.SD_SIGMA), ("sd_pow", GC.SD_POW), ("sd_taper_m", NEST_BANDS["sd_taper_m"]),
             ("sd_gain", 1.0), ("relax_g", 1.0), ("dt0", 1.0 / 24.0), ("ramp_s", 0.0), ("wall_taper_m", NEST_BANDS["wall_taper_m"]),
             ("in_gain", 1.0), ("x_p", NEST_BANDS["x_p"]), ("xg_end", NEST_BANDS["xg_end"]), ("xa0", GC.XA0), ("abs_sigma", GC.ABS_SIGMA),
             ("abs_pow", GC.ABS_POW), ("set_P", 0.0), ("set_up", 0.0), ("set_flat", 0.0), ("set_down", 0.0), ("set_cg", 0.0), ("duabs_on", 0.0),
             ("volcorr_on", 0.0), ("vol_x0", NEST_BANDS["vol_x0"]), ("vol_x1", NEST_BANDS["vol_x1"]), ("hold_on", 0.0), ("hold_x0", GC.HOLD_X[0]),
             ("hold_x1", GC.HOLD_X[1]), ("surf_layer_m", 2.5), ("mirror_m", 1.0), ("surf_vox_scale", 1.0), ("crop_x0", NEST_BANDS["crop_x0"]),
             ("crop_x1", NEST_BANDS["crop_x1"]), ("crop_z1", NEST_BANDS["crop_z1"]), ("surf_ycut", -15.0), ("surf_keep_vox", 1.0),
             ("surf_bed_vox", 0.5)] + [(n, v) for n, v, _ in NEST_PARMS]
    for nm, dv in PARMS:
        ptg.append(hou.FloatParmTemplate(nm, nm, 1, default_value=(dv,)))
    for nm in ("sol_npz", "sf_tab", "vol_dir", "dir_npz"):
        ptg.append(hou.StringParmTemplate(nm, nm, 1, default_value=("",)))
    for nm, dv, lb in NEST_STR_PARMS:
        ptg.append(hou.StringParmTemplate(nm, lb, 1, default_value=(dv,)))
    ptg.append(hou.StringParmTemplate("ckpt", "checkpoint folder", 1, default_value=(B55 + "/runs/ckpt_default",)))
    ptg.append(hou.IntParmTemplate("ckpt_on", "write checkpoints", 1, default_value=(0,)))
    ptg.append(hou.IntParmTemplate("ckpt_every", "checkpoint spacing (frames)", 1, default_value=(48,)))
    ctrl.setParmTemplateGroup(ptg)
    for nm, dv in PARMS:
        ctrl.parm(nm).set(dv)
    VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

    # ---------------------------------------------------------------- tables (as DFG-2B-V's scene) + the nest target / replay
    sol = setup.createNode("python", "solution_table")
    t_ = sol.parmTemplateGroup()
    t_.append(hou.StringParmTemplate("npz", "npz", 1, default_value=("",)))
    t_.append(hou.FloatParmTemplate("wave_on", "wave_on", 1, default_value=(0.0,)))
    t_.append(hou.FloatParmTemplate("h0", "h0", 1, default_value=(GC.H0,)))
    sol.setParmTemplateGroup(t_)
    sol.parm("npz").set('`chs("%ssol_npz")`' % CT)
    sol.parm("wave_on").setExpression('ch("%swave_on")' % CT)
    sol.parm("h0").setExpression('ch("%sh0")' % CT)
    sol.parm("python").set(L.PYSOP)
    solout = setup.createNode("null", "OUT_SOL"); solout.setInput(0, sol)
    sftab = setup.createNode("attribwrangle", "sf_table")
    sftab.parm("class").set(0); sftab.parm("vex_precision").set("64")
    sftab.parm("snippet").set(L.snippet("/obj/G52_SETUP/sf_table"))
    sfo = setup.createNode("null", "OUT_SF"); sfo.setInput(0, sftab)

    def pysop(name, code, parms):
        n = setup.createNode("python", name)
        tg = n.parmTemplateGroup()
        for pn, kind in parms:
            tg.append(hou.FloatParmTemplate(pn, pn, 1, default_value=(1.0,)) if kind == "f" else hou.StringParmTemplate(pn, pn, 1, default_value=("",)))
        n.setParmTemplateGroup(tg)
        n.parm("python").set(code)
        return n
    vdp = pysop("voldiv_table", L.PYSOP_VOLDIV, [("fr", "f"), ("vdir", "s")])
    vdp.parm("fr").setExpression("$FF"); vdp.parm("vdir").set('`chs("%svol_dir")`' % CT)
    vdo = setup.createNode("null", "OUT_VOLDIV"); vdo.setInput(0, vdp)
    rpp = pysop("replay_table", L.PYSOP_VOLDIV, [("fr", "f"), ("vdir", "s")])
    rpp.parm("fr").setExpression("$FF"); rpp.parm("vdir").set('`chs("%srep_dir")`' % CT)
    rpo = setup.createNode("null", "OUT_REPLAY"); rpo.setInput(0, rpp)
    tgp = pysop("parent_target", PYSOP_TARGET, [("fr", "f"), ("tdir", "s")])
    tgp.parm("fr").setExpression("$FF"); tgp.parm("tdir").set('`chs("%stgt_dir")`' % CT)
    tgo = setup.createNode("null", "OUT_TARGET"); tgo.setInput(0, tgp)
    dtab = setup.createNode("python", "dir_table")
    t_ = dtab.parmTemplateGroup(); t_.append(hou.StringParmTemplate("npz", "npz", 1, default_value=("",))); dtab.setParmTemplateGroup(t_)
    dtab.parm("npz").set('`chs("%sdir_npz")`' % CT); dtab.parm("python").set(L.PYSOP_DIRTAB52)
    dto = setup.createNode("null", "OUT_DIRTAB"); dto.setInput(0, dtab)

    # ---------------------------------------------------------------- bed (= DFG-2B-V's nodes and expressions, generic in x0)
    PADE = 'ch("%sfloor_pad")*%s' % (CT, VOXE)
    SPADE = 'ch("%sside_pad")*%s' % (CT, VOXE)
    BOXC = dict(sx='ch("%sLx")' % CT, sy='ch("%sHz") + %s' % (CT, PADE), sz='ch("%sW") + %s' % (CT, SPADE),
                tx='ch("%sx0") + 0.5*ch("%sLx") + ch("%sox")' % (CT, CT, CT),
                ty='ch("%szb") - %s + 0.5*(ch("%sHz") + %s) + ch("%soy")' % (CT, PADE, CT, PADE, CT),
                tz='0.5*(ch("%sW") - %s) + ch("%soz")' % (CT, SPADE, CT))
    bgrid = setup.createNode("grid", "bed_grid")
    bgrid.parm("orient").set(2)
    bgrid.parm("sizex").setExpression('ch("%sLx") + 20' % CT); bgrid.parm("sizey").setExpression('ch("%sW") + 12' % CT)
    bgrid.parm("rows").setExpression('int(2*(ch("%sLx") + 20)) + 1' % CT); bgrid.parm("cols").setExpression('int(ch("%sW") + 12) + 1' % CT)
    bgrid.parm("tx").setExpression(BOXC["tx"]); bgrid.parm("ty").setExpression('ch("%soy")' % CT); bgrid.parm("tz").setExpression(BOXC["tz"])
    bw = setup.createNode("attribwrangle", "bed_height"); bw.setInput(0, bgrid); bw.parm("snippet").set(L.snippet("/obj/G52_SETUP/bed_height"))
    bedout = setup.createNode("null", "OUT_BED"); bedout.setInput(0, bw)
    bsdf = setup.createNode("volume", "bed_sdf")
    bsdf.parm("name").set("collision"); bsdf.parm("rank").set("scalar"); bsdf.parm("uniformsamples").set("size")
    bsdf.parm("divsize").setExpression(VOXE)
    bsdf.parm("sizex").setExpression('ch("%sLx") + 12*%s' % (CT, VOXE)); bsdf.parm("sizey").setExpression('%s + 12*%s' % (BOXC["sy"], VOXE))
    bsdf.parm("sizez").setExpression('ch("%sW") + 12*%s' % (CT, VOXE))
    bsdf.parm("tx").setExpression(BOXC["tx"]); bsdf.parm("ty").setExpression(BOXC["ty"]); bsdf.parm("tz").setExpression(BOXC["tz"])
    bsdfw = setup.createNode("volumewrangle", "bed_sdf_value"); bsdfw.setInput(0, bsdf); bsdfw.parm("snippet").set(L.snippet("/obj/G52_SETUP/bed_sdf_value"))
    bsdfout = setup.createNode("null", "OUT_BED_SDF"); bsdfout.setInput(0, bsdfw)

    # ---------------------------------------------------------------- initial particles (nest rule) + the (unused, donarrowband 0) initial surface / vel
    cols = setup.createNode("attribwrangle", "particle_columns")
    cols.parm("class").set(0)
    cols.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float W = ch(CT+"W");
int nx = int(floor(Lx/dp + 1e-6)); int nz = int(floor(W/dp + 1e-6));
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++) {
        int p = addpoint(0, set(x0 + (ix + 0.5)*dp + chf(CT+"ox"), 0.0, (iz + 0.5)*dp + chf(CT+"oz")));
        setpointattrib(0, "col", p, iz*nx + ix);
    }
""")
    pts0 = setup.createNode("attribwrangle", "init_particles")
    pts0.setInput(0, cols); pts0.setInput(1, solout)
    pts0.parm("class").set(2)
    pts0.parm("snippet").set(HEAD + BODIES_NEST["init_particles"])
    pclean = setup.createNode("attribdelete", "drop_col"); pclean.setInput(0, pts0); pclean.parm("ptdel").set("col")
    ptsout = setup.createNode("null", "OUT_PARTICLES"); ptsout.setInput(0, pclean)
    wmesh0 = setup.createNode("attribwrangle", "water_mesh")
    wmesh0.parm("class").set(0); wmesh0.setInput(1, solout)
    wmesh0.parm("snippet").set(L.VEX_HEAD + r"""
float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float W = ch(CT+"W"); float zb = ch(CT+"zb");
float vox = ch(CT+"dp")*ch(CT+"gridscale");
float ox = ch(CT+"ox"); float oy = ch(CT+"oy"); float oz = ch(CT+"oz");
float xa = x0 - 3.0*vox; float xb = x0 + Lx + 3.0*vox; float za = -3.0*vox; float zc = W + 3.0*vox;
float yb = zb - (6.0 + ch(CT+"floor_pad"))*vox;
float hx = 0.5*vox;
int n = int(ceil((xb - xa)/hx - 1e-6)) + 1;
int tA[]; int tC[]; int bA[]; int bC[];
resize(tA, n); resize(tC, n); resize(bA, n); resize(bC, n);
for (int i = 0; i < n; i++) {
    float x = min(xa + i*hx, xb);
    float e = sol_eta(x);
    tA[i] = addpoint(0, set(x + ox, e + oy, za + oz)); tC[i] = addpoint(0, set(x + ox, e + oy, zc + oz));
    bA[i] = addpoint(0, set(x + ox, yb + oy, za + oz)); bC[i] = addpoint(0, set(x + ox, yb + oy, zc + oz));
}
for (int i = 0; i < n - 1; i++) {
    addprim(0, "poly", tA[i], tC[i], tC[i + 1], tA[i + 1]);
    addprim(0, "poly", bA[i], bA[i + 1], bC[i + 1], bC[i]);
    addprim(0, "poly", bA[i], tA[i], tA[i + 1], bA[i + 1]);
    addprim(0, "poly", bC[i + 1], tC[i + 1], tC[i], bC[i]);
}
addprim(0, "poly", bC[0], tC[0], tA[0], bA[0]);
addprim(0, "poly", bA[n - 1], tA[n - 1], tC[n - 1], bC[n - 1]);
""")
    wvdb = setup.createNode("vdbfrompolygons", "surface_vdb"); wvdb.setInput(0, wmesh0)
    wvdb.parm("voxelsize").setExpression(VOXE); wvdb.parm("builddistance").set(1); wvdb.parm("distancename").set("surface")
    wvdb.parm("exteriorbandvoxels").set(6); wvdb.parm("interiorbandvoxels").set(6); wvdb.parm("fillinterior").set(1)
    vsvdb = setup.createNode("null", "OUT_SURFACE_VDB"); vsvdb.setInput(0, wvdb)
    vv = setup.createNode("volume", "vol_vel")
    vv.parm("name").set("vel"); vv.parm("rank").set("vector"); vv.parm("uniformsamples").set("size"); vv.parm("divsize").setExpression(VOXE)
    for a_, b_ in (("sizex", "sx"), ("sizey", "sy"), ("sizez", "sz"), ("tx", "tx"), ("ty", "ty"), ("tz", "tz")):
        vv.parm(a_).setExpression(BOXC[b_])
    vvw = setup.createNode("volumewrangle", "vel_value"); vvw.setInput(0, vv); vvw.setInput(1, solout)
    vvw.parm("snippet").set(L.snippet("/obj/G52_SETUP/vel_value"))
    vvo = setup.createNode("null", "OUT_VEL"); vvo.setInput(0, vvw)

    # ---------------------------------------------------------------- probe points
    PTS_PY = r'''
import json, hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
rows = json.loads(node.evalParm("pts_json") or "[]")
keys = sorted(set(k for r in rows for k in r if k not in ("v0",)))
for k in keys:
    geo.addAttrib(hou.attribType.Point, k, 0.0)
geo.addAttrib(hou.attribType.Point, "v0", (0.0, 0.0, 0.0))
for r in rows:
    p = geo.createPoint()
    p.setPosition((0.0, 0.0, 0.0))
    for k in keys:
        p.setAttribValue(k, float(r.get(k, 0.0)))
    p.setAttribValue("v0", tuple(float(v) for v in r.get("v0", (0.0, 0.0, 0.0))))
'''
    npp = setup.createNode("python", "nest_probe_pts")
    t_ = npp.parmTemplateGroup(); t_.append(hou.StringParmTemplate("pts_json", "pts_json", 1, default_value=("[]",))); npp.setParmTemplateGroup(t_)
    npp.parm("python").set(PTS_PY)
    npr = setup.createNode("attribwrangle", "nest_probe")
    npr.setInput(0, npp); npr.parm("class").set(2); npr.parm("vex_precision").set("64")
    npr.parm("snippet").set(HEAD + BODIES_NEST["nest_probe"])
    setup.layoutChildren()

    # ---------------------------------------------------------------- DOP (DFG-2B-V's settings; nest: start / creation frame, bands, replay, surface)
    dop = obj.createNode("dopnet", "G52_SIM")
    dop.parm("cachemaxsize").set(3000)
    dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
    dop.parm("explicitcachename").set('`chs("%sckpt")`/v.$SF4.sim' % CT)
    dop.parm("explicitcachecheckpointspacing").setExpression('ch("%sckpt_every")' % CT)
    dop.parm("explicitcachensteps").set(0)
    setup_log = {}

    def find_parm(node, names, labels=()):
        """a parm by name, else by its label (the DOP objects' creation parms are found either way)."""
        for nm in names:
            if node.parm(nm) is not None:
                return node.parm(nm)
        for p_ in node.parms():
            try:
                if p_.parmTemplate().label() in labels:
                    return p_
            except Exception:
                pass
        return None

    def set_expr(node, names, expr, labels=()):
        p_ = find_parm(node, names, labels)
        if p_ is None:
            return None
        p_.setExpression(expr)
        return p_.name()

    def set_val(node, names, val, labels=()):
        p_ = find_parm(node, names, labels)
        if p_ is None:
            return None
        p_.set(val)
        return p_.name()
    # the DOP network keeps DFG-2B-V's start (frame 1, no time offset): $SF = $F, checkpoint names = global frames (the frozen chain's resume
    # parses them), simulation time = global time; the objects are created at sim_f0 instead (frames 1-1055 hold no object)
    setup_log["dop_startframe"] = dop.parm("startframe").eval() if dop.parm("startframe") is not None else None
    setup_log["dop_timeoffset"] = dop.parm("timeoffset").eval() if dop.parm("timeoffset") is not None else None
    for c_ in dop.children():
        c_.destroy()
    fo = dop.createNode("flipobject", "water")
    fo.parm("objname").set("water")
    fo.parm("particlesep").setExpression('ch("%sdp")' % CT)
    fo.parm("gridscale").setExpression('ch("%sgridscale")' % CT)
    fo.parm("closedends").set(1)
    for s_ in ("closexpos", "closexneg", "closeyneg", "closezpos", "closezneg"):
        fo.parm(s_).set(1)
    fo.parm("closeypos").set(0)
    fo.parm("surfacetype").set("4")
    fo.parm("soppath").set("/obj/G52_SETUP/OUT_PARTICLES")
    fo.parm("import_nbsurface").set("/obj/G52_SETUP/OUT_SURFACE_VDB")
    fo.parm("import_nbvelocity").set("/obj/G52_SETUP/OUT_VEL")
    fo.parm("jitterscale").set(0.0)
    fo.parm("adddivergence").setExpression('ch("%svolcorr_on") > 0.5 || ch("%shold_on") > 0.5 || ch("%srep_on") > 0.5' % (CT, CT, CT))
    CREATE_LABELS = ("Creation Frame",)
    SF_LABELS = ("Creation Frame Specifies Simulation Frame",)
    setup_log["flip_createframe_parm"] = set_expr(fo, ("createframe", "creationframe"), 'ch("%ssim_f0")' % CT, CREATE_LABELS)
    setup_log["flip_create_sf_toggle"] = set_val(fo, ("usesfframe", "createframe_sf"), 0, SF_LABELS)      # creation frame = a GLOBAL frame
    setup_log["flip_solvefirstframe"] = set_val(fo, ("solvefirstframe",), 0)     # frame 1056 = the parent's state, not solved on creation
    so = dop.createNode("staticobject", "seabed")
    so.parm("object_name").set("seabed"); so.parm("soppath").set("/obj/G52_SETUP/OUT_BED"); so.parm("usevolume").set(1)
    so.parm("mode").set("volume"); so.parm("proxyvolume").set("/obj/G52_SETUP/OUT_BED_SDF"); so.parm("collisiondetection").set("volume")
    setup_log["static_createframe_parm"] = set_expr(so, ("createframe", "creationframe"), 'ch("%ssim_f0")' % CT, CREATE_LABELS)
    setup_log["static_create_sf_toggle"] = set_val(so, ("usesfframe", "createframe_sf"), 0, SF_LABELS)
    relax = dop.createNode("gasfieldwrangle", "relax_zones")
    relax.parm("snippet").set(HEAD + BODIES_NEST["relax_zones"]); relax.parm("exportlist").set("vel"); relax.parm("vex_precision").set("64")
    en_r = dop.createNode("enablesolver", "enable_zones"); en_r.setInput(0, relax)
    en_r.parm("enable").setExpression('ch("%srelax_on") > 0.5 || ch("%sabs_on") > 0.5 || ch("%ssd_on") > 0.5' % (CT, CT, CT))
    vcd = dop.createNode("gasfieldwrangle", "vc_div")
    vcd.parm("snippet").set(L.snippet("/obj/G52_SIM/vc_div")); vcd.parm("exportlist").set("divergence"); vcd.parm("vex_precision").set("64")
    en_vc = dop.createNode("enablesolver", "enable_volcorr"); en_vc.setInput(0, vcd)
    en_vc.parm("enable").setExpression('ch("%svolcorr_on") > 0.5 || ch("%shold_on") > 0.5' % (CT, CT))
    vcr = dop.createNode("gasfieldwrangle", "vc_rep")
    vcr.parm("snippet").set(HEAD + BODIES_NEST["vc_rep"]); vcr.parm("exportlist").set("divergence"); vcr.parm("vex_precision").set("64")
    en_rep = dop.createNode("enablesolver", "enable_replay"); en_rep.setInput(0, vcr)
    en_rep.parm("enable").setExpression('ch("%srep_on") > 0.5' % CT)
    msv = dop.createNode("enablesolver", "volume_velocity")
    msv.setInput(0, en_r); msv.setInput(1, en_vc); msv.setInput(2, en_rep); msv.parm("enable").set(1)
    ssc = dop.createNode("geometrywrangle", "substep_count")
    ssc.parm("bindclass").set("detail"); ssc.parm("snippet").set(L.BODIES["/obj/G52_SIM/substep_count"]); ssc.parm("exportlist").set("ss_acc ss_n ss_dt")
    bk = dop.createNode("geometrywrangle", "band_kill")
    try:
        bk.parm("bindclass").set("point")
    except Exception:
        bk.parm("bindclass").set(2)
    bk.parm("snippet").set(HEAD + BODIES_NEST["band_kill"]); bk.parm("exportlist").set("*")
    bsd = dop.createNode("geometrywrangle", "band_seed")
    bsd.parm("bindclass").set("detail"); bsd.parm("snippet").set(HEAD + BODIES_NEST["band_seed"]); bsd.parm("exportlist").set("*")
    en_bs = dop.createNode("enablesolver", "enable_band_surface"); en_bs.setInput(0, bk); en_bs.setInput(1, bsd)
    en_bs.parm("enable").setExpression('ch("%snest_on") > 0.5 && ch("%sband_surf") > 0.5' % (CT, CT))
    pre = dop.createNode("enablesolver", "pre_solve"); pre.setInput(0, ssc); pre.setInput(1, en_bs); pre.parm("enable").set(1)
    fs = dop.createNode("flipsolver::2.0", "flipsolver")
    fs.setInput(0, fo); fs.setInput(1, pre); fs.setInput(2, msv)
    fs.parm("veltransfer").set("flip"); fs.parm("usemgpreconditioner").set(0); fs.parm("usepreconditioner").set(1)
    fs.parm("minimumsubsteps").setExpression('ch("%sminsub")' % CT); fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
    fs.parm("cflcond").setExpression('ch("%scfl")' % CT); fs.parm("partcflcond").setExpression('ch("%spcfl")' % CT)
    fs.parm("dynamicresize").set(0); fs.parm("usewaterline").set(0); fs.parm("useboundarylayer").set(0)
    fs.parm("donarrowband").set(1); fs.parm("narrowbandwidth").set(1000.0); fs.parm("dosurfacetension").set(0)
    for a_, b_ in (("limit_sizex", "sx"), ("limit_sizey", "sy"), ("limit_sizez", "sz"), ("limit_tx", "tx"), ("limit_ty", "ty"), ("limit_tz", "tz")):
        fs.parm(a_).setExpression(BOXC[b_])
    mg = dop.createNode("merge", "merge"); mg.setInput(0, so); mg.setInput(1, fs)
    gr = dop.createNode("gravity", "gravity"); gr.setInput(0, mg)
    out = dop.createNode("output", "output"); out.setInput(0, gr); out.setDisplayFlag(True)
    dop.layoutChildren()

    # ---------------------------------------------------------------- read + surface (= DFG-2B-V's)
    rdn = obj.createNode("geo", "G52_READ")
    for c_ in rdn.children():
        c_.destroy()
    for nm in ("surface", "vel", "collision"):
        q = rdn.createNode("dopimportfield::2.0", nm + "_field")
        q.parm("doppath").set("/obj/G52_SIM"); q.parm("fields").set(1); q.parm("objname1").set("water"); q.parm("fieldname1").set(nm)
    sfn = obj.createNode("geo", "G52_SURF")
    for c_ in sfn.children():
        c_.destroy()
    di = sfn.createNode("dopimport", "particles"); di.parm("doppath").set("/obj/G52_SIM"); di.parm("objpattern").set("water")
    sfield = sfn.createNode("object_merge", "surface_field"); sfield.parm("objpath1").set("/obj/G52_READ/surface_field")
    layer = sfn.createNode("attribwrangle", "layer_and_mirror"); layer.setInput(0, di); layer.setInput(1, sfield); layer.parm("class").set(2)
    layer.parm("snippet").set(r"""
#define CT "%s"
float lm = ch(CT+"surf_layer_m");
if (lm > 0.0) {
    float vox = ch(CT+"dp")*ch(CT+"gridscale");
    float s = volumesample(1, "surface", @P);
    if (s < -0.5*vox) {
        int keep = 0;
        for (float h = vox; h <= lm + 1e-6; h += vox) {
            if (volumesample(1, "surface", @P + set(0, h, 0)) > 0.0) { keep = 1; break; }
        }
        if (!keep) { removepoint(0, @ptnum); return; }
    }
}
float oz = ch(CT+"oz");
if (@P.z - oz < ch(CT+"mirror_m")) {
    int p = addpoint(0, @ptnum);
    setpointattrib(0, "P", p, set(@P.x, @P.y, 2.0*oz - @P.z));
    setpointattrib(0, "v", p, set(v@v.x, v@v.y, -v@v.z));
}
""" % CT)
    pfs = sfn.createNode("particlefluidsurface", "fluid_surface"); pfs.setInput(0, layer)
    pfs.parm("particlesep").setExpression('ch("%sdp")' % CT); pfs.parm("voxelsize").setExpression('ch("%ssurf_vox_scale")' % CT)
    pfs.parm("adaptivity").set(0.005); pfs.parm("conversion").set("poly"); pfs.parm("dotransferattribs").set(1); pfs.parm("transferattribs").set("v")
    clip = sfn.createNode("clip::2.0", "cut_symmetry"); clip.setInput(0, pfs)
    clip.parm("clipop").set("above"); clip.parm("dirx").set(0.0); clip.parm("diry").set(0.0); clip.parm("dirz").set(1.0)
    clip.parm("originz").setExpression('ch("%soz")' % CT)
    tri = sfn.createNode("divide", "triangles"); tri.setInput(0, clip); tri.parm("convex").set(1); tri.parm("numsides").set(3)
    crop = sfn.createNode("attribwrangle", "crop"); crop.setInput(0, tri); crop.setInput(1, sfield); crop.parm("class").set(1)
    crop.parm("snippet").set(L.VEX_HEAD + r"""
int pts[] = primpoints(0, @primnum);
vector c = 0;
foreach (int p; pts) c += point(0, "P", p);
c /= max(1, len(pts));
float sdfc = volumesample(1, "surface", c);
float vox = ch(CT+"dp")*ch(CT+"gridscale");
vector cp = c - set(ch(CT+"ox"), ch(CT+"oy"), ch(CT+"oz"));
float gapb = cp.y - bedy(cp.x, cp.z);
if (len(pts) != 3 || cp.x < ch(CT+"crop_x0") || cp.x > ch(CT+"crop_x1") || cp.z > ch(CT+"crop_z1") || cp.y < ch(CT+"surf_ycut")
    || abs(sdfc) > ch(CT+"surf_keep_vox")*vox || gapb < ch(CT+"surf_bed_vox")*vox)
    removeprim(0, @primnum, 1);
""")
    nrm = sfn.createNode("normal", "point_normals"); nrm.setInput(0, crop); nrm.parm("type").set(0)
    idx = sfn.createNode("attribwrangle", "tri_index"); idx.setInput(0, nrm); idx.parm("class").set(1)
    idx.parm("snippet").set("int pts[] = primpoints(0, @primnum);\ni@a = pts[0]; i@b = pts[1]; i@c = pts[2];\n")
    sout = sfn.createNode("null", "OUT_SURF"); sout.setInput(0, idx)
    sfn.layoutChildren()

    # ======================================================================== checks
    def ctrl_floats():
        return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}
    DEFAULT_CTRL = ctrl_floats()
    DEFAULT_STR = {p.name(): p.evalAsString() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.String}

    def restore():
        for k, v in DEFAULT_CTRL.items():
            ctrl.parm(k).set(v)
        for k, v in DEFAULT_STR.items():
            ctrl.parm(k).set(v)

    def set_box(dp):
        b = C.box(dp, NEST_BOX["x0"], NEST_BOX["Lx"], NEST_BOX["W"], NEST_BOX["zb"])
        for k, v in dict(dp=b["dp"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], ox=b["ox"], oy=b["oy"], oz=b["oz"], x0=b["x0"]).items():
            ctrl.parm(k).set(v)
        return b

    def bed_check(tag, dp):
        b = set_box(dp)
        P_ = ctrl_floats()
        spec = GC.bed_spec(parms=P_)
        o = np.array([P_["ox"], P_["oy"], P_["oz"]])
        bw.cook(force=True)
        g_ = bedout.geometry()
        Pp = np.frombuffer(g_.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
        dz = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **spec)
        out_ = dict(tag=tag, dp=dp, box=b, bed_points=int(len(Pp)), bed_max_abs_dz_m=float(np.abs(dz).max()))
        bsdfw.cook(force=True)
        vols = [q for q in bsdfout.geometry().prims() if q.type() in (hou.primType.Volume, hou.primType.VDB)]
        v = vols[0]
        r = v.resolution()
        a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0]).astype(np.float64)
        p0 = np.array([float(c_) for c_ in v.indexToPos((0, 0, 0))]) - o
        p1 = np.array([float(c_) for c_ in v.indexToPos((1, 1, 1))]) - o
        dd = p1 - p0
        xs = p0[0] + dd[0] * np.arange(r[0]); ys = p0[1] + dd[1] * np.arange(r[1]); zs = p0[2] + dd[2] * np.arange(r[2])
        ref = np.empty_like(a)
        for k0 in range(0, r[2], 16):
            Z, Y, X = np.meshgrid(zs[k0:k0 + 16], ys, xs, indexing="ij")
            ref[k0:k0 + 16] = GC.bed_sdf(X, Y, Z, **spec)
        near = np.abs(ref) < 3.0
        out_["sdf_max_abs_diff_near_m"] = float(np.abs(a - ref)[near].max())
        far = np.abs(ref) > 0.05
        out_["sdf_sign_mismatch_frac"] = float(np.mean(np.sign(a[far]) != np.sign(ref[far])))
        out_["ok"] = bool(out_["bed_max_abs_dz_m"] < 1e-3 and out_["sdf_max_abs_diff_near_m"] < 0.02 and out_["sdf_sign_mismatch_frac"] == 0.0
                          and xs[0] <= NEST_BOX["x0"] and xs[-1] >= NEST_BOX["x0"] + NEST_BOX["Lx"])
        return out_

    def particles_geo():
        g = ptsout.geometry()
        P_ = ctrl_floats()
        o = np.array([P_["ox"], P_["oy"], P_["oz"]])
        Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
        V = np.frombuffer(g.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3).astype(np.float64) if len(Pp) else np.zeros((0, 3))
        return Pp, V

    def probe(rows):
        npp.parm("pts_json").set(json.dumps(rows))
        npr.cook(force=True)
        g = npr.geometry()
        get = lambda nm, n=1: np.array(g.pointFloatAttribValues(nm)).reshape(-1, n) if n > 1 else np.array(g.pointFloatAttribValues(nm))
        return dict(s=get("s_t"), v=get("v_t", 3), e=get("e_t"), w=get("w_t"), ok=np.array(g.pointIntAttribValues("ok_t")), wdt=get("wdt"),
                    v1=get("v1", 3), div=get("div"), wat=get("wat"))

    def set_frame(ff):
        hou.setTime((ff - 1.0) / hou.fps())          # fractional frames by time ($FF = 1056.5 at t = 1055.5 / 24)
        for n_ in (tgp, rpp):
            n_.cook(force=True)

    try:
        # ctrl superset
        need = set(dfgbv_parm_names())
        sys.path.insert(0, HERE)
        import f55_nest as FN
        need |= set(FN.LAUNCH_PARMS) | set(FN.LAUNCH_STR_PARMS)
        have = set(p.name() for p in ctrl.parms())
        item("ctrl_superset", dict(ok=bool(need <= have), missing=sorted(need - have)))
        item("bed_C2ID", bed_check("nest box dp 0.5", 0.5))
        item("bed_C2", bed_check("nest box dp 0.25", 0.25))
        restore()
        # still water (nest_on 0): DFG-2B-V's seeding rule on the nest box
        set_box(0.5)
        for n_ in (sol, cols, pts0):
            n_.cook(force=True)
        Pp, V = particles_geo()
        n_model, _ = C.count_particles(0.5, NEST_BOX["x0"], NEST_BOX["Lx"], NEST_BOX["W"], NEST_BOX["zb"])
        gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **GC.SPEC_BED)
        item("still_particles", dict(ok=bool(len(Pp) == n_model and (gap < 0).sum() == 0), houdini=int(len(Pp)), model=int(n_model),
                                     n_below_bed=int((gap < 0).sum())))
        # synthetic target
        write_synth_export(SYNTH_DIR)
        ctrl.parm("tgt_dir").set(SYNTH_DIR); ctrl.parm("rep_dir").set(SYNTH_DIR); ctrl.parm("nest_on").set(1.0); ctrl.parm("rep_on").set(1.0)
        Pm = nest_parms_for_mirror()
        for k in ("relax_on", "sd_on", "xg_end", "x0", "Lx", "W", "sd0", "sd_gen", "sd_sw", "sd_taper_m", "wall_taper_m", "ramp_s", "in_gain", "sd_gain",
                  "relax_g", "dt0", "vol_x0", "vol_x1", "abs_on", "volcorr_on", "s_off", "bed_trust_m", "seed_margin_dp", "kill_margin_dp"):
            ctrl.parm(k).set(Pm[k])
        rng = np.random.RandomState(55)
        rows = []
        for i in range(400):
            if i % 2:
                x = rng.uniform(180.5, 198.5); z = rng.uniform(0.5, 59.5)
            else:
                x = rng.uniform(180.5, 355.5); z = rng.uniform(41.5, 59.5)
            rows.append(dict(px=x, py=rng.uniform(-12.0, 3.0), pz=z, pt=44.0, dts=1.0 / 96.0, v0=(0.7, -0.3, 0.4)))
        for i in range(80):                       # the first 0.5 m beside the y = 0 plane (the review's border case) and near the top
            rows.append(dict(px=rng.uniform(180.5, 198.5), py=rng.uniform(-12.0, 3.0) if i % 4 else rng.uniform(15.5, 16.9),
                             pz=rng.uniform(0.02, 0.48), pt=44.0, dts=1.0 / 96.0, v0=(0.7, -0.3, 0.4)))
        X_ = np.array([np.float32(r["px"]) for r in rows], float); Y_ = np.array([np.float32(r["py"]) for r in rows], float)
        Z_ = np.array([np.float32(r["pz"]) for r in rows], float)
        plane = Z_ < 0.5
        for nm, ff, wt in (("target_probe_integer", 1056.0, None), ("target_probe_half", 1056.5, 0.5)):
            set_frame(ff)
            pr = probe(rows)
            Fa, Fb = synth_fields(1056), synth_fields(1057 if wt is not None else 1056)
            w = 0.0 if wt is None else wt
            mix = lambda k, *a: (1 - w) * synth_expect(Fa, k, *a) + w * synth_expect(Fb, k, *a)
            es = float(np.abs(pr["s"] - mix("s", X_, Y_, Z_)).max())
            ev = float(np.abs(pr["v"] - np.stack([mix("vx", X_, Y_, Z_), mix("vy", X_, Y_, Z_), mix("vz", X_, Y_, Z_)], 1)).max())
            ee = float(np.abs(pr["e"] - mix("eta", X_, Z_)).max())
            es_pl = float(np.abs(pr["s"] - mix("s", X_, Y_, Z_))[plane].max())
            # the water rule against its numpy mirror (points within 1 mm of a threshold are not judged)
            s_x, e_x = mix("s", X_, Y_, Z_), mix("eta", X_, Z_)
            yb_ = GC.bed_z(X_, Z_, **GC.SPEC_BED)
            wat_x = water_np(s_x, Y_, yb_, e_x, Pm["s_off"], Pm["bed_trust_m"])
            clear = (np.abs(s_x + Pm["s_off"]) > 1e-3) & (np.abs(Y_ - yb_ - Pm["bed_trust_m"]) > 1e-3)
            wat_ok = bool(np.all((pr["wat"] > 0.5)[clear] == wat_x[clear]))
            det_ = tgo.geometry()
            item(nm, dict(ok=bool(es < 1e-4 and ev < 5e-3 and ee < 2e-3 and wat_ok and np.all(pr["ok"] == 1) and int(det_.attribValue("t_pad")) == 1
                                  and abs(float(pr["w"][0]) - (1.0 if wt is None else wt)) < 1e-6),
                          err_s=es, err_v=ev, err_eta=ee, err_s_plane_rows=es_pl, n_plane_rows=int(plane.sum()), water_rule_ok=wat_ok,
                          n_water=int(wat_x.sum()), t_fa=det_.attribValue("t_fa"), t_fb=det_.attribValue("t_fb"), t_ff=det_.attribValue("t_ff"),
                          w=float(pr["w"][0]), t_err=det_.attribValue("t_err"), t_pad=det_.attribValue("t_pad"), t_border=det_.attribValue("t_border")))
            if wt is not None:
                # band weights and nest_apply vs the frozen numpy mirror (g50_table bands_np / tapers_np / rampT) with the analytic target
                sys.path.insert(0, T50)
                import g50_table as TB50
                dts32 = float(np.float32(1.0 / 96.0))

                def mirror(Pq, Xq, Yq, Zq):
                    v1s, ws_ = [], []
                    for i in range(len(Xq)):
                        tv = [float(mix(k_, Xq[i], Yq[i], Zq[i])) for k_ in ("vx", "vy", "vz")]
                        v1_, w_ = nest_apply_np(TB50, float(Xq[i]), float(Yq[i]), float(Zq[i]), (0.7, -0.3, 0.4), tv, 44.0, dts32, Pq)
                        v1s.append(v1_); ws_.append(w_)
                    return np.array(v1s), np.array(ws_)
                v1r, ref_w = mirror(Pm, X_, Y_, Z_)
                okb = bool(np.abs(pr["wdt"] - ref_w).max() < 1e-6 and np.abs(pr["v1"] - v1r).max() < 5e-3 and np.allclose(pr["v1"][:, 1], -0.3, atol=1e-6))
                # the optional end band (end_on 1) near the closed face, against the same mirror
                rows_e = [dict(px=float(rng.uniform(330.5, 355.5)), py=float(rng.uniform(-3.0, 0.0)), pz=float(rng.uniform(0.5, 59.5)), pt=44.0,
                               dts=1.0 / 96.0, v0=(0.7, -0.3, 0.4)) for _ in range(120)]
                Xe = np.array([np.float32(r["px"]) for r in rows_e], float); Ye = np.array([np.float32(r["py"]) for r in rows_e], float)
                Ze = np.array([np.float32(r["pz"]) for r in rows_e], float)
                ctrl.parm("end_on").set(1.0)
                pre_ = probe(rows_e)
                ctrl.parm("end_on").set(0.0)
                v1e, we = mirror(dict(Pm, end_on=1.0), Xe, Ye, Ze)
                oke = bool(np.abs(pre_["wdt"] - we).max() < 1e-6 and np.abs(pre_["v1"] - v1e).max() < 5e-3 and (we > 0).any())
                item("band_probe", dict(ok=bool(okb and oke), wdt_max_diff=float(np.abs(pr["wdt"] - ref_w).max()),
                                        v1_max_diff=float(np.abs(pr["v1"] - v1r).max()), n_in_band=int((ref_w > 0).sum()),
                                        vertical_unchanged=bool(np.allclose(pr["v1"][:, 1], -0.3, atol=1e-6)),
                                        end_band=dict(ok=oke, wdt_max_diff=float(np.abs(pre_["wdt"] - we).max()), v1_max_diff=float(np.abs(pre_["v1"] - v1e).max()),
                                                      n_in_end_band=int((we > 0).sum()))))
                inwin = (X_ >= Pm["vol_x0"]) & (X_ <= Pm["vol_x1"])
                item("replay_probe", dict(ok=bool(np.allclose(pr["div"][inwin], 3.25e-05, atol=1e-12) and np.all(pr["div"][~inwin] == 0.0) and inwin.any()
                                                  and (~inwin).any()), n_in=int(inwin.sum()), n_out=int((~inwin).sum()),
                                          vol_div=rpo.geometry().attribValue("vol_div")))
        # initial particles from the synthetic frame 1056 (full box)
        set_frame(1056.0)
        set_box(0.5)
        for n_ in (tgp, cols, pts0):
            n_.cook(force=True)
        Pp, V = particles_geo()
        F = synth_fields(1056)
        n_np = numpy_init_count(lambda x, y, z: synth_expect(F, "s", x, y, z), lambda x, z: synth_expect(F, "eta", x, z), 0.5, NEST_BOX["x0"],
                                NEST_BOX["Lx"], NEST_BOX["W"], NEST_BOX["zb"], s_off=Pm["s_off"], bed_trust=Pm["bed_trust_m"])
        sel = np.arange(0, len(Pp), max(1, len(Pp) // 2000))
        sel = np.union1d(sel, np.where(Pp[:, 2] < 0.5)[0][::25])          # include particles of the first lateral row (the plane)
        vref = np.stack([synth_expect(F, k, Pp[sel, 0], Pp[sel, 1], Pp[sel, 2]) for k in ("vx", "vy", "vz")], 1)
        gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **GC.SPEC_BED)
        item("init_particles", dict(ok=bool(len(Pp) > 0 and abs(len(Pp) - n_np) <= max(2, int(1e-4 * n_np)) and np.abs(V[sel] - vref).max() < 1e-2
                                            and (gap < 0).sum() == 0), houdini=int(len(Pp)), numpy=int(n_np), v_max_diff=float(np.abs(V[sel] - vref).max()),
                                    n_checked=int(len(sel)), n_plane_row=int((Pp[:, 2] < 0.5).sum()), n_below_bed=int((gap < 0).sum())))
        ctrl.parm("tgt_dir").set("")
        for n_ in (tgp, cols, pts0):
            n_.cook(force=True)
        Pp0, _ = particles_geo()
        item("init_no_target", dict(ok=bool(len(Pp0) == 0), particles=int(len(Pp0)), rule="nest_on 1 without a target seeds NOTHING (fails loudly)"))
        restore()
        set_frame(1.0)
        for n_ in (sol, sftab, vdp, rpp, tgp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
            n_.cook(force=True)
        npp.parm("pts_json").set("[]")
        dop_err = {n_.path(): [str(e)[:200] for e in n_.errors()] for n_ in (relax, vcd, vcr, en_r, en_vc, en_rep, msv, ssc, bk, bsd, en_bs, pre, fo, so, fs)
                   if n_.errors()}
        cf_f = fo.parm(setup_log["flip_createframe_parm"]).eval() if setup_log["flip_createframe_parm"] else None
        cf_s = so.parm(setup_log["static_createframe_parm"]).eval() if setup_log["static_createframe_parm"] else None
        sff = fo.parm("solvefirstframe").eval() if fo.parm("solvefirstframe") is not None else None
        start_ok = bool((setup_log["dop_startframe"] is None or int(round(float(setup_log["dop_startframe"]))) == 1)
                        and (setup_log["dop_timeoffset"] is None or abs(float(setup_log["dop_timeoffset"])) < 1e-12))
        item("dop_setup", dict(ok=bool(start_ok and cf_f is not None and cf_s is not None and int(round(float(cf_f))) == CKPT
                                       and int(round(float(cf_s))) == CKPT and (sff is None or int(sff) == 0)
                                       and fs.inputs()[1] is not None and fs.inputs()[2] is not None and len(msv.inputs()) >= 3
                                       and all(n_ is not None for n_ in msv.inputs()[:3])
                                       and bk.parm("bindclass").evalAsString() in ("point", "points")),
                               parms=setup_log, createframe_flip=cf_f, createframe_static=cf_s, solvefirstframe=sff,
                               rule="DOP start frame 1 / no time offset (as DFG-2B-V: $SF = $F); FLIP + static objects created at 1056 (global "
                                    "frames); not solved on creation; 3 inputs on volume_velocity; band_kill over points",
                               solver_inputs=[n_.path() if n_ else None for n_ in fs.inputs()], input_labels=list(fs.inputLabels()),
                               volume_velocity_inputs=[n_.path() if n_ else None for n_ in msv.inputs()],
                               band_kill_bindclass=bk.parm("bindclass").evalAsString(), dop_errors=dop_err))
        item("saved_defaults", dict(ok=bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).eval() == 0.0 for k in (
            "relax_on", "sd_on", "nest_on", "band_surf", "rep_on", "volcorr_on", "dir_on")))))
    except Exception as e:
        import traceback
        raw["error"] = repr(e)[:400]
        raw["traceback"] = traceback.format_exc()[-3000:]
        try:
            restore()
        except Exception:
            pass
    if not HIP.startswith(REPO + "/Houdini/FLIP55/"):
        raise SystemExit("refused: hip path")
    os.makedirs(HIP_DIR, exist_ok=True)
    hou.hipFile.save(HIP)
    raw["hip_sha256"] = sha(HIP)
    print("saved", HIP, raw["hip_sha256"][:16], flush=True)
    # ======================================================================== smoke (the REAL export; after the save: the hip is never saved again)
    if smoke and not raw.get("error"):
        raw["smoke"] = smoke_run(hou, np, ctrl, dop, fs)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(RAW, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=1, ensure_ascii=False, default=str)
    print("RAW written", RAW, flush=True)


def smoke_run(hou, np, ctrl, dop, fs):
    """C2ID launch parms, frames 1056 .. 1056 + SMOKE_FRAMES with checkpoints every 12 frames into _scratch/nest_smoke; per frame the R1 top
    surface of the nest (as the runner) is saved for the py-side comparisons. Nothing is recorded as a run."""
    sm = json.load(open(SMOKE_CFG, encoding="utf-8"))
    out = dict(frames=[], eta_files={}, cfg=SMOKE_CFG.replace(REPO + "/", ""))
    try:
        for k, v in sm["parms"].items():
            if ctrl.parm(k) is not None:
                ctrl.parm(k).set(v)
        sv = sm.get("solver") or {}
        fs.parm("veltransfer").set(sv.get("veltransfer", "flip"))
        fs.parm("donarrowband").set(int(sv.get("donarrowband", 0)))
        ck = sm["ckpt_dir"]
        os.makedirs(ck, exist_ok=True)
        for p in glob.glob(ck + "/v.*.sim"):
            os.remove(p)
        ctrl.parm("ckpt").set(ck); ctrl.parm("ckpt_on").set(1); ctrl.parm("ckpt_every").set(int(sm["ckpt_every"]))
        hou.setSimulationEnabled(True)
        fi = hou.node("/obj/G52_READ/surface_field")
        o = np.array([ctrl.evalParm("ox"), ctrl.evalParm("oy"), ctrl.evalParm("oz")])
        os.makedirs(SMOKE_DIR + "/eta", exist_ok=True)
        f0, f1 = int(sm["frames"][0]), int(sm["frames"][1])
        # frames 1 .. f0 - 1 hold no object (DOP start frame 1, objects created at f0)
        t0 = time.time()
        hou.setFrame(f0 - 1)
        out["preroll_s"] = round(time.time() - t0, 2)
        out["absent_before_creation"] = bool(dop.simulation().findObject("water") is None)
        for f in range(f0, f1 + 1):
            t0 = time.time()
            hou.setFrame(f)
            g = fi.geometry()
            dt = time.time() - t0
            wobj = dop.simulation().findObject("water")
            n = int(wobj.geometry().intrinsicValue("pointcount")) if wobj is not None else 0
            row = dict(frame=f, s=round(dt, 2), particles=n, dop_time=float(dop.simulation().time()), global_time=(f - 1) / hou.fps())
            if f == f0 and wobj is not None and n > 0:
                # a sample of the created particles (plan P, v) for the py-side initial-velocity check
                wg = wobj.geometry()
                Pa = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
                Va = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3).astype(np.float64)
                sel = np.arange(0, n, max(1, n // 20000))
                np.savez_compressed(SMOKE_DIR + "/p1056.npz", P=Pa[sel], v=Va[sel])
                out["p1056"] = SMOKE_DIR + "/p1056.npz"
                out["point_attribs_at_creation"] = sorted(a.name() for a in wg.pointAttribs())
                del Pa, Va
            vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)] if g is not None else []
            if vols:
                v = vols[0]
                r = v.resolution()
                a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])
                p0 = np.array([float(c) for c in v.indexToPos((0, 0, 0))]) - o
                p1 = np.array([float(c) for c in v.indexToPos((1, 1, 1))]) - o
                d = p1 - p0
                zs = p0[2] + d[2] * np.arange(r[2])
                izc = int(np.searchsorted(zs, 0.0))
                a = a[izc:]
                ns = {}
                exec(compile(TARGET_PURE, "TARGET_PURE", "exec"), ns)
                eta = ns["f55_r1"](a, p0[1], d[1]).astype(np.float32)
                row["finite"] = bool(np.isfinite(a).all())
                meta = dict(res=[int(r[0]), int(r[1]), int(r[2] - izc)], x0=float(p0[0]), dx=float(d[0]), z0=float(zs[izc]), dz=float(d[2]),
                            y0=float(p0[1]), dy=float(d[1]), t_off=0.0)
                pth = SMOKE_DIR + "/eta/eta_%05d.npz" % f
                np.savez_compressed(pth, eta=eta, meta=json.dumps(meta))
                out["eta_files"][str(f)] = pth
            else:
                row["finite"] = False
            for an in ("band_added", "band_cand"):
                try:
                    row[an] = int(wobj.geometry().attribValue(an)) if wobj is not None else None
                except Exception:
                    row[an] = None
            out["frames"].append(row)
            print("SMOKE", json.dumps(row), flush=True)
        # particle attributes after 24 frames of band seeding: no zero pscale, no duplicate id (a seed copies its nearest particle)
        attr = {}
        try:
            wg = dop.simulation().findObject("water").geometry()
            names = [a.name() for a in wg.pointAttribs()]
            attr["names"] = sorted(names)
            if "pscale" in names:
                ps = np.array(wg.pointFloatAttribValues("pscale"))
                attr["pscale_min"] = float(ps.min()); attr["pscale_max"] = float(ps.max())
            if "id" in names:
                ids = np.array(wg.pointIntAttribValues("id"))
                attr["id_unique"] = bool(len(np.unique(ids)) == len(ids)); attr["n"] = int(len(ids))
            attr["ok"] = bool(attr.get("pscale_min", 1.0) > 0.0 and attr.get("id_unique", True)
                              and set(out.get("point_attribs_at_creation") or []) <= set(names))
        except Exception as e:
            attr = dict(ok=False, error=repr(e)[:300])
        out["attributes"] = attr
        out["particles_init"] = out["frames"][0]["particles"] if out["frames"] else 0
        cks = sorted(os.path.basename(p) for p in glob.glob(ck + "/v.*.sim"))
        out["ckpt_files"] = [c_ for c_ in cks if int(c_[2:6]) >= f0 - 1]
        out["ckpt_files_preroll"] = len(cks) - len(out["ckpt_files"])
        out["created_at_start"] = bool(out["particles_init"] > 0 and out["absent_before_creation"])
        out["all_finite"] = bool(out["frames"] and all(r.get("finite") for r in out["frames"]))
        out["dop_time_global"] = bool(all(abs(r["dop_time"] - r["global_time"]) < 1e-6 for r in out["frames"]))
        out["ckpt_name_global_frame"] = bool("v.1068.sim" in cks or "v.1080.sim" in cks)
        n0 = out["particles_init"]
        out["no_mass_collapse"] = bool(n0 and all(r["particles"] >= 0.9 * n0 for r in out["frames"]))
        out["ok"] = bool(out["created_at_start"] and out["all_finite"] and out["dop_time_global"] and out["ckpt_name_global_frame"] and out["no_mass_collapse"]
                         and attr.get("ok"))
    except Exception as e:
        import traceback
        out["error"] = repr(e)[:400]
        out["traceback"] = traceback.format_exc()[-2000:]
        out["ok"] = False
    return out


if __name__ == "__main__":
    if "--hython" in sys.argv:
        hython_build(smoke="--smoke" in sys.argv)
    else:
        sys.exit(launcher(sys.argv[1:]))
