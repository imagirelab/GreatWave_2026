# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 (DFG-2B-V): launcher of the scene and the inputs (py -3.10; numpy, no Houdini). 2026-10-18 written new (Claude) by
adapting flip52b2/x52b2_build.py (DFGB3, frozen, not edited). It never writes into Houdini/FLIP52B, Houdini/FLIP52B2, Houdini/FLIP52S2 or their
Build folders.
DFG-2B-V keeps DFG-2B-E's bed and box, so NO new scene is built (no hython): the scene is a BYTE COPY of DFG-2B-E's scene
Houdini/FLIP52B/g52b_tank.hiplc (read only) to Houdini/FLIP52B3/g52b3_tank.hiplc, accepted only if the source's sha256 equals the one that
flip52b's hython build check validated (Unity/Build/FLIP52B/_logs/build_check52b.json all_ok: the D19B bed VEX = numpy on the strip and at
W 140, particles, the N-layer table probe and the D-layout band probe) and that every DFG-2B-E launch used (run_c*.json hip_sha256); the copy
must have the same sha256. The N-layer VEX path does not depend on the table content (the run itself checks OUT_DIRTAB against the cfg table
at start and records dir_check samples).
1. checks the frozen plan's .sha256, that the generated copies (g52b3_run.py, g52b3_chain.py, g52b3_video.py) still equal g52b3_mkcopy.py's
   output (no hand edit) and the numpy bed self-check; writes (numpy) the DFGB4 generator table (g52b3_table.write) and refuses to go on if
   the G1 numpy table check fails (g52b3_table.checks -> Unity/Build/FLIP52B3/plan/table_check_DFGB4.json) or the table differs from the plan's
   frozen content sha.
2. copies the scene if it is missing (or differs) and writes Unity/Build/FLIP52B3/_logs/build_check52b3.json (all_ok, hip_sha256 = the copy's,
   the source build check's items) and build_inputs52b3.json. If all_ok is false, g52b3_chain.py will not start any run.
usage: py -3.10 -B G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3/x52b3_build.py [--dry]   (--dry: checks only, nothing written)
"""
import os, sys, time, json, shutil

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g52b3_common as GC    # noqa: E402
import g52b3_table as TB     # noqa: E402
import g52b3_mkcopy as MK    # noqa: E402


def source_ok():
    """the source scene and the evidence that it is DFG-2B-E's validated scene (reads only)."""
    out = dict(source=GC.HIP_SRC, source_exists=os.path.exists(GC.HIP_SRC))
    out["source_sha256"] = GC.sha256_file(GC.HIP_SRC) if out["source_exists"] else None
    out["source_sha_as_registered"] = bool(out["source_sha256"] == GC.HIP_SRC_SHA256)
    bc = GC.jload(GC.SRC_BUILD_CHECK) if os.path.exists(GC.SRC_BUILD_CHECK) else {}
    out["source_build_check"] = dict(file=GC.SRC_BUILD_CHECK.replace(GC.REPO + "/", ""), all_ok=bc.get("all_ok"), hip_sha256=bc.get("hip_sha256"),
                                     date=bc.get("date"), houdini=bc.get("houdini"),
                                     items={k: (bool(all(v for kk, v in bc[k].items() if (kk == "ok" or kk.endswith("_ok")) and isinstance(v, bool)))
                                                if isinstance(bc.get(k), dict) else bc.get(k))
                                            for k in("D19B_strip", "D19B_3d", "D19B_3d_particles_dp1", "D19B_numpy", "dir_probe", "relax_probe_D",
                                                      "restored_ctrl_equal_default", "saved_scene_still_water_bands_off")},
                                     W_3d=(bc.get("D19B_3d") or {}).get("W"), W_relax=(bc.get("relax_probe_D") or {}).get("W"))
    out["source_build_check_ok"] = bool(bc.get("all_ok") and bc.get("hip_sha256") == GC.HIP_SRC_SHA256)
    rr = []
    import glob
    for p in sorted(glob.glob(GC.DFGBE_RUN + "/run_c*.json")):
        try:
            rr.append(GC.jload(p).get("hip_sha256"))
        except Exception:
            rr.append(None)
    out["dfgbe_launch_hips"] = sorted(set(str(h)[:16] for h in rr))
    out["dfgbe_launches_used_source"] = bool(rr and all(h == GC.HIP_SRC_SHA256 for h in rr))
    out["ok"] = bool(out["source_exists"] and out["source_sha_as_registered"] and out["source_build_check_ok"] and out["dfgbe_launches_used_source"])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    dry = "--dry" in sys.argv
    os.makedirs(GC.LOG_DIR, exist_ok=True)
    lp = GC.LOG_DIR + "/build52b3.log"

    def log(*a):
        msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode(), flush=True)
        if not dry:
            with open(lp, "a", encoding="utf8") as fh:
                fh.write(msg + "\n")
    if not GC.plan_sha_ok():
        log("STOP the frozen plan %s does not match its .sha256" % GC.PLAN); return 2
    try:
        gen = MK.build_all()
    except SystemExit as e:
        log("STOP g52b3_mkcopy cannot regenerate the copies (a source changed?): %s" % e); return 5
    bad = [nm for nm, s in gen.items() if not (os.path.exists(os.path.join(GC.TOOLS52B3, nm)) and open(os.path.join(GC.TOOLS52B3, nm), encoding="utf8").read() == s)]
    if bad:
        log("STOP the generated copies differ from g52b3_mkcopy.py output: %s (run py -3.10 -B g52b3_mkcopy.py, then re-freeze)" % bad); return 5
    bs = GC.bed_selfcheck()
    log("bed self-check (numpy, the D19B bed of DFG-2B-E) ok", bs["ok"])
    if not bs["ok"]:
        log("STOP the numpy bed self-check failed: %s" % json.dumps(GC.clean(bs))[:800]); return 3
    p, sha, ch, info = TB.write(dry=dry)
    log("sea", GC.SET, "(DFG-2B-E's energy-matched sea x the inlet-only n5 calibration %.6f rad x the 3 %% side-band taper)" % GC.PHI5, "a_sum %.6f m" % GC.A_SUM)
    log("table", p, "sha", str(sha)[:16], "content", ch[:16])
    o = TB.checks()
    if not dry:
        GC.jdump(o, GC.TABLE_CHECK)
    log("G1 numpy table check all_ok", o["all_ok"], o["ok"], "%.1f s" % o["cpu_s"])
    if not o["all_ok"] or o["content_sha256"] != ch:
        log("STOP the DFGB4 table fails its numpy check (or differs from the written file); no scene"); return 3
    pc = (GC.plan().get("table_npz") or {}).get("content_sha256")
    if pc != ch:
        log("STOP the table content %s differs from the frozen plan's %s; no scene" % (ch[:16], str(pc)[:16])); return 3
    src = source_ok()
    log("source scene", src["source"], "sha", str(src["source_sha256"])[:16], "as registered", src["source_sha_as_registered"], "flip52b build check ok",
        src["source_build_check_ok"], "DFG-2B-E launches used it", src["dfgbe_launches_used_source"], "W", src["source_build_check"]["W_3d"],
        src["source_build_check"]["W_relax"])
    if not src["ok"]:
        log("STOP the source scene is not DFG-2B-E's validated scene: %s" % json.dumps(GC.clean(src), ensure_ascii=False)[:900]); return 4
    copied = False
    if dry:
        log("--dry: no copy, no build_check52b3.json")
        print(json.dumps(dict(build_ok=None, dry=True, source_ok=src["ok"], hip=GC.HIP, hip_exists=os.path.exists(GC.HIP))))
        return 0
    os.makedirs(os.path.dirname(GC.HIP), exist_ok=True)
    if not os.path.exists(GC.HIP) or GC.sha256_file(GC.HIP) != GC.HIP_SRC_SHA256:
        tmp = GC.HIP + ".part"
        shutil.copyfile(GC.HIP_SRC, tmp)
        if GC.sha256_file(tmp) != GC.HIP_SRC_SHA256:
            os.remove(tmp)
            log("STOP the copied scene's sha256 differs from the source"); return 4
        os.replace(tmp, GC.HIP)
        copied = True
    hs = GC.sha256_file(GC.HIP)
    ok = bool(hs == GC.HIP_SRC_SHA256 and src["ok"] and src["source_build_check"]["W_3d"] == GC.W_MAIN and src["source_build_check"]["W_relax"] == GC.W_MAIN)
    chk = dict(all_ok=ok, hip=GC.HIP, hip_sha256=hs, date=time.strftime("%Y-%m-%d %H:%M:%S"), kind="byte copy of DFG-2B-E's scene (no hython build)",
               copied_now=copied, source=src, W=GC.W_MAIN, table=dict(npz=p, npz_sha256=sha, content_sha256=ch, G1_all_ok=o["all_ok"]),
               bed_numpy=bs, module_shas=GC.module_shas(),
               note="the bed, box, bands, VEX and node names are DFG-2B-E's (validated by flip52b's hython build check on these exact bytes); "
                    "the table content is checked by G1 (numpy) and by g52b3_run.py at start (OUT_DIRTAB fields, layers, P, harmonics) and dir_check")
    GC.jdump(chk, GC.BUILD_CHECK)
    inputs = dict(dir_npz=p, dir_sha256=sha, content_sha256=ch, n_layers=info["n_layers"], a_sum=info["a_sum"], x_f=info["x_f"], t_f=info["t_f"],
                  calibration=info["calibration"], taper=info["taper"], plan=GC.PLAN_REL, plan_sha256=GC.sha256_file(GC.PLAN), hip=GC.HIP, hip_sha256=hs,
                  made=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(inputs, open(GC.BUILD_INPUTS, "w", encoding="utf8"), indent=1)
    log("build_check52b3 all_ok", ok, "hip", GC.HIP, "sha", hs[:16], "copied now", copied)
    print(json.dumps(dict(build_ok=ok, hip=GC.HIP, hip_exists=os.path.exists(GC.HIP), hip_sha256=hs, build_check=GC.BUILD_CHECK, copied=copied)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
