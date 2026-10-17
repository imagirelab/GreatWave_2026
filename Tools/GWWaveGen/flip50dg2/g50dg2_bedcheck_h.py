# -*- coding: utf-8 -*-
"""FLIP50 DG2 (AM-D22): read the groove hip's bed, bed SDF and frame-1 particles at a DG2 variant's CTRL values (hython; READ ONLY: the hip is
loaded, CTRL is set in memory, nothing is saved; the hip sha256 is compared before and after). 2026-10-17 written new (Claude).
Started by `py -3.10 -B g50dg2_pcfg.py bedcheck <variant>` (which waits for every other hython first); the comparison with numpy is done
there (bedcheck-eval), so this file only extracts arrays:
  main cfg (dp 0.5): OUT_BED points (all), OUT_BED_SDF voxels inside the groove box x 230-360 m, |y| <= 60 m
  smoke cfg (dp 1.0): OUT_PARTICLES (the FLIP object imports exactly this at frame 1)
usage: hython g50dg2_bedcheck_h.py <main cfg.json> <smoke cfg.json> <out.npz>     (+ <out.npz>.json record)
"""
import hou, sys, os, json, time
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
for _p in (HERE, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50g"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import g50dg2_common as D       # noqa: E402

GG = D.GG
GC = GG.patch_modules(hip=True)
BOX_X, BOX_Y = (230.0, 360.0), 60.0


def main():
    main_cfg, smoke_cfg, out_npz = sys.argv[1:4]
    t0 = time.time()
    rec = dict(tool="flip50dg2/g50dg2_bedcheck_h.py", date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=GG.HIP_G, main_cfg=main_cfg, smoke_cfg=smoke_cfg)
    arrays = {}
    try:
        rec["hip_sha256_before"] = GC.sha256_file(GG.HIP_G)
        hou.hipFile.load(GG.HIP_G, suppress_save_prompt=True, ignore_load_warnings=True)
        ctrl = hou.node("/obj/G50_SETUP/CTRL")

        def setp(cfg):
            for k, v in cfg["parms"].items():
                p = ctrl.parm(k)
                if p is None:
                    raise RuntimeError("CTRL has no parm %s" % k)
                p.set(v)
            return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}
        cm = json.load(open(main_cfg, encoding="utf8"))
        P = setp(cm)
        o = np.array([float(P["ox"]), float(P["oy"]), float(P["oz"])])
        rec["main_parms"] = {k: v for k, v in P.items() if k.startswith("gr_") or k in ("dp", "W", "Lx", "zb", "ox", "oy", "oz", "gridscale", "Hz")}
        hou.node("/obj/G50_SETUP/bed_height").cook(force=True)
        g = hou.node("/obj/G50_SETUP/OUT_BED").geometry()
        arrays["bedP"] = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
        hou.node("/obj/G50_SETUP/bed_sdf_value").cook(force=True)
        gs = hou.node("/obj/G50_SETUP/OUT_BED_SDF").geometry()
        vols = [q for q in gs.prims() if q.type() in (hou.primType.Volume, hou.primType.VDB)]
        if not vols:
            raise RuntimeError("OUT_BED_SDF has no volume")
        v = vols[0]
        r = v.resolution()
        a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])
        p0 = np.array([float(c) for c in v.indexToPos((0, 0, 0))]) - o
        p1 = np.array([float(c) for c in v.indexToPos((1, 1, 1))]) - o
        dd = p1 - p0
        xs = p0[0] + dd[0] * np.arange(r[0]); ys = p0[1] + dd[1] * np.arange(r[1]); zs = p0[2] + dd[2] * np.arange(r[2])
        ix = (xs >= BOX_X[0]) & (xs <= BOX_X[1]); kz = np.abs(zs) <= BOX_Y
        arrays["sdf"] = np.ascontiguousarray(a[kz][:, :, ix])
        arrays["sdf_xs"] = xs[ix]; arrays["sdf_ys"] = ys; arrays["sdf_zs"] = zs[kz]
        rec["sdf_res"] = [int(c) for c in r]
        cs = json.load(open(smoke_cfg, encoding="utf8"))
        P2 = setp(cs)
        o2 = np.array([float(P2["ox"]), float(P2["oy"]), float(P2["oz"])])
        rec["smoke_parms"] = {k: v for k, v in P2.items() if k.startswith("gr_") or k in ("dp", "W", "Lx", "zb", "ox", "oy", "oz", "bed_gap", "gridscale")}
        po = hou.node("/obj/G50_SETUP/OUT_PARTICLES")
        po.cook(force=True)
        gp = po.geometry()
        arrays["parts"] = np.frombuffer(gp.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o2
        hou.hipFile.clear(suppress_save_prompt=True)
        rec["hip_sha256_after"] = GC.sha256_file(GG.HIP_G)
        rec["hip_unchanged"] = bool(rec["hip_sha256_after"] == rec["hip_sha256_before"])
        np.savez_compressed(out_npz, **arrays)
        rec["npz"] = out_npz
        rec["n"] = {k: list(np.shape(x)) for k, x in arrays.items()}
    except Exception as e:
        import traceback
        rec["error"] = repr(e)[:400]
        rec["traceback"] = traceback.format_exc()[-2000:]
    rec["wall_s"] = round(time.time() - t0, 1)
    json.dump(rec, open(out_npz + ".json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    print("DG2 bedcheck extract", json.dumps({k: rec.get(k) for k in ("n", "hip_unchanged", "wall_s", "error")}, default=str))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
