# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: TEST ONLY. Writes a synthetic run folder (the exact LINEAR sea of the table, in the record formats of g52_run.py: cfg.json,
run_c00001.json, hf / r2 / r4 / r6 npz) into the session scratchpad, so that g52_ana.py (smoke / judge) and g52_video.py can be checked end to
end with numpy before any FLIP52 run exists (py -3.10 -B). 2026-10-17 written new (Claude). Never writes into Unity/Build (guarded).
The synthetic field is NOT a simulation: eta = ramp(t) x sum_n Re(A_n e^{-i w_n (t - t_f)}) + eta0 everywhere (no propagation from the bands),
so the analysis of it must reproduce the linear screen numbers of plan_DFG_frozen.json (Hc 6.32, W50 4.57, miss 2.35, gain ~3.2, Nt ~0.42).
Optional lip: water above an air gap at the centre section near the focus in group 2 (tests the onset rule and the B2 overturning count).
usage: py -3.10 -B g52_synth.py <out_dir under the scratchpad> smoke|main [--lip]
"""
import os, sys, json, math

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52_common as GC              # noqa: E402
import g52_table as TB               # noqa: E402
import g52_pcfg as PC                # noqa: E402

ETA0 = 0.07


def write_run(out, preset, lip=False):
    o = os.path.abspath(out).replace("\\", "/")
    if not o.lower().startswith(GC.SCRATCH_PREFIX.lower()):
        raise SystemExit("test output only under the scratchpad %s" % GC.SCRATCH_PREFIX)
    c = PC.make(preset)
    rid = c["run_id"]
    rd = o + "/" + rid
    os.makedirs(rd, exist_ok=True)
    c = dict(c, out_root=o, synthetic_test=True)
    json.dump(c, open(rd + "/cfg.json", "w", encoding="utf8"), indent=1, default=float)
    dp = float(c["parms"]["dp"]); vox = 2.0 * dp
    C = GC.components(c["dir"]["set"])
    xs = 0.5 * vox + vox * np.arange(int(GC.LX / vox)); ys = 0.5 * vox + vox * np.arange(int(GC.W_MAIN / vox))
    zv = GC.ZB - 2 * vox + 0.5 * vox + vox * np.arange(int((GC.Z_TOP - GC.ZB + 2 * vox) / vox))
    A = [TB.layer_complex(C, n, xs, ys)[0] for n in range(len(C["om"]))]
    f_end = int(c["f_end"])
    meta_hf = dict(res=[len(xs), len(zv), len(ys)], x0=float(xs[0]), dx=vox, z0=float(ys[0]), dz=vox, y0=float(zv[0]), dy=vox, t_off=0.0)
    meta_r2 = dict(res=[len(xs), len(zv), len(ys)], iz=0, z=float(ys[0]), x0=float(xs[0]), dx=vox, nx=len(xs), y0=float(zv[0]), dy=vox, ny=len(zv),
                   clip_m=8.0, t_off=0.0, vel={})
    r4x = (xs >= GC.R4_X[0]) & (xs <= GC.R4_X[1]); r4z = ys <= GC.R4_Y1; r4v = (zv >= GC.R4_Z[0]) & (zv <= GC.R4_Z[1])
    meta_r4 = dict(x0=float(xs[r4x][0]), dx=vox, nx=int(r4x.sum()), z0=float(ys[0]), dz=vox, nz=int(r4z.sum()), y0=float(zv[r4v][0]), dy=vox,
                   ny=int(r4v.sum()), clip_m=6.0 * vox, t_off=0.0)
    wins = c["records"]["windows"]
    bh = dict(eta=[], f=[]); b2 = dict(sdf=[], f=[]); b4 = dict(sdf=[], f=[])
    r6 = dict(frames=[], t=[], vol=[], npts=[])

    def flush(kind, buf, key, meta, force=False, nmax=120):
        if buf["f"] and (force or len(buf["f"]) >= nmax):
            np.savez_compressed(rd + "/%s_c00001_b%05d.npz" % (kind, buf["f"][0]), **{key: np.array(buf[key], np.float16 if kind != "hf" else np.float32)},
                                frames=np.array(buf["f"]), t=np.array([(f - 1) / 24.0 for f in buf["f"]]), meta=json.dumps(meta))
            buf[key] = []; buf["f"] = []
    for f in range(1, f_end + 1):
        t = (f - 1) / 24.0
        ramp = TB.rampT(t, GC.RAMP_S)
        eta = ETA0 + ramp * sum((A[n] * np.exp(-1j * C["om"][n] * (t - GC.T_F))).real for n in range(len(A)))     # (ny, nx)
        bh["eta"].append(eta.astype(np.float32)); bh["f"].append(f)
        flush("hf", bh, "eta", meta_hf)
        sec = np.clip(zv[:, None] - eta[0][None, :], -8.0, 8.0)
        if lip and abs(t - 71.5) <= 0.5:
            m = (xs >= 148.0) & (xs <= 152.0)
            zz = (zv >= ETA0 + 7.5) & (zv <= ETA0 + 8.5)
            sec[np.ix_(zz, m)] = -0.4
        b2["sdf"].append(sec.astype(np.float16)); b2["f"].append(f)
        flush("r2", b2, "sdf", meta_r2)
        inw = any(a - 1e-9 <= t <= b + 1e-9 for a, b in wins)
        if inw and (f - 1) % 3 == 0:
            e4 = eta[np.ix_(r4z, r4x)]
            s4 = np.clip(zv[r4v][None, :, None] - e4[:, None, :], -6.0 * vox, 6.0 * vox)
            b4["sdf"].append(s4.astype(np.float16)); b4["f"].append(f)
            flush("r4", b4, "sdf", meta_r4, nmax=24)
        elif not inw and b4["f"]:
            flush("r4", b4, "sdf", meta_r4, force=True)
        V = 580000.0 * (1.0 + 0.002 * math.sin(0.1 * t))
        r6["frames"].append(f); r6["t"].append(t); r6["vol"].append([V, 0.5 * V, 0, 0, 0, 0, 0, 0]); r6["npts"].append(int(4.64e6))
    flush("hf", bh, "eta", meta_hf, True); flush("r2", b2, "sdf", meta_r2, True); flush("r4", b4, "sdf", meta_r4, True)
    np.savez(rd + "/r6_c00001.npz", frames=np.array(r6["frames"]), t=np.array(r6["t"]), vol=np.array(r6["vol"]), npts=np.array(r6["npts"]),
             vol_names=np.array(["V_m3", "Vwin_m3", "vol_div", "cap", "I_B", "vol_div_band", "du_abs", "cum_added_m3"]),
             gauge=np.zeros((len(r6["frames"]), 20)), gauge_xy=np.array([[x, y] for y in GC.GAUGE_Y for x in GC.GAUGE_X]))
    rec = dict(stage="FLIP52", run_id=rid, f_start=1, f_end_req=f_end, f_end_done=f_end, stopped=None, hip_sha256="synthetic", wall_total_s=0.0,
               particles_max=int(4.64e6), info=dict(still_offset_online=dict(value=ETA0, n_frames=12)), synthetic_test=True)
    json.dump(rec, open(rd + "/run_c00001.json", "w", encoding="utf8"), indent=1)
    return rd


if __name__ == "__main__":
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    print(write_run(a[0], a[1], lip="--lip" in sys.argv))
