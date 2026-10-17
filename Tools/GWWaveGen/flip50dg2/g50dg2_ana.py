# -*- coding: utf-8 -*-
"""FLIP50 DG2 (AM-D22): read a DG2 calculation (py -3.10 -B). 2026-10-17 written new (Claude).
It runs flip50g/g50g_ana.py in memory (which runs the unchanged flip50/g50_ana.py with the groove bed patched in) after:
  - g50dg2_common.install (DG2 ids accepted with their own gr_*),
  - g50g_ana.validity: for a DG2 run the CTRL gr_* of every launch record must equal the variant's (dg2_frozen.json) instead of DG1's, and
    both frozen files must still have their sha256,
  - the label of the groove in the md / smoke mp4 names the DG2 variant.
  smoke <SMOKE50DG2 run>          g50g_ana smoke gates (dg1_frozen smoke, the variant's core box) -> pana/smoke_DG2.json
  all|report <DG2 run> --prev=<DM1A run>   g50_ana all (S2 / Q73 against DM1A in planD_ana.json)
  q80 <DG2 run>                   the frozen S0-S4 (dg1_frozen criteria, DM1A baseline) + Q73 vs DG1 (report only) -> pana/q80_DG2.json
The DG1-named files that g50g_ana writes in a DG2 folder (smoke_DG1.json, q80_DG1.json) are moved to pana/_dg1_named/ after the DG2 file is
written, so no DG2 folder holds a file that reads as a DG1 result.
"""
import os, sys, json, time, shutil

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50dg2_common as D          # noqa: E402

GG = D.GG
D.install(GG)
import g50g_ana as AG              # noqa: E402  flip50g (unchanged file)

GC = AG.GC
AN = AG.AN
_ORIG_VALIDITY = AG.validity


def validity_dg2(rd, cfg):
    v, kind = D.variant_of(cfg.get("run_id"))
    if v is None:
        return _ORIG_VALIDITY(rd, cfg)
    recs = AG.run_records(rd)
    bc = AG._load(GG.BUILD_CHECK_G) or {}
    shas = sorted(set(r.get("hip_sha256") for r in recs))
    hips = sorted(set(str(r.get("hip")) for r in recs))
    gr = [{k: (r.get("bed_spec_ctrl") or {}).get(k) for k in D.CTRL_KEYS} for r in recs]
    want = D.ctrl(v)
    dg2_ok = bool(os.path.exists(D.DG2_FROZEN) and (cfg.get("case") or {}).get("dg2_frozen_sha256") == D.sha256_file(D.DG2_FROZEN))
    out = dict(variant=v, hip_sha256=shas, hip=hips, build_check_g_hip_sha256=bc.get("hip_sha256"),
               hip_ok=bool(recs and len(shas) == 1 and shas[0] == bc.get("hip_sha256") and all(os.path.normcase(h) == os.path.normcase(GG.HIP_G) for h in hips)),
               ctrl_gr=gr[0] if gr else None, ctrl_gr_ok=bool(gr and all(g == want for g in gr)),
               cfg_groove_bad=GG.cfg_groove_ok(cfg), frozen_sha_ok=bool(GG.sha256_file(GG.DG1_FROZEN) == GG.DG1_SHA256 and dg2_ok))
    out["ok"] = bool(out["hip_ok"] and out["ctrl_gr_ok"] and not out["cfg_groove_bad"] and out["frozen_sha_ok"])
    return out


AG.validity = validity_dg2


def _label(v):
    g = D.params(v)
    AG._LABEL_FIX = (("、海底 D19B。", "、海底 D19B＋選んだ浅い溝 2 本 DG2-%s（x %g〜%g m）【選び】。" % (v, g["x1"], g["x4"])),
                     ("まっすぐな 1:10 の浜", "1:10 の浜＋選んだ浅い溝 2 本 DG2-%s【選び】" % v))


def _move_dg1_named(rd, name):
    p = os.path.join(rd, "pana", name)
    if os.path.exists(p):
        dst = GC.guard_out50(os.path.join(rd, "pana", "_dg1_named"))
        shutil.move(p, os.path.join(dst, name))


def smoke(rd):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = AN.PA.load_cfg(rd)
    v, kind = D.variant_of(cfg.get("run_id"))
    if kind != "smoke":
        raise SystemExit("%s is not a DG2 smoke" % cfg.get("run_id"))
    _label(v)
    D.set_core_box(v)
    o = AG.smoke_dg1(rd)
    o.update(tool="flip50dg2/g50dg2_ana.py smoke (flip50g/g50g_ana.smoke_dg1 in memory)", dg2=dict(variant=v, frozen=D.DG2_FROZEN_REL,
             sha256=D.sha256_file(D.DG2_FROZEN), core_box=D.CORE_BOXES[v], am=D.AMENDMENT))
    o["next"] = ("all DG2-%s smoke gates pass -> DG2-%s main run (py -3.10 %s/g50dg2_chain.py %s)" % (v, v, HERE, GC.B50 + "/runs/ready/" + D.main_id(v) + ".json")
                 if o["ok"] else "DG2-%s smoke gate(s) failed (%s): read-only diagnosis, stop and ask (no DG2 main run)" %
                 (v, ", ".join(k for k, x in (o.get("gates") or {}).items() if not x)))
    od = GC.guard_out50(os.path.join(rd, "pana"))
    json.dump(AN.A46._clean(o), open(os.path.join(od, "smoke_DG2.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    _move_dg1_named(rd, "smoke_DG1.json")
    return o


def q80(rd):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = AN.PA.load_cfg(rd)
    v, kind = D.variant_of(cfg.get("run_id"))
    if v is None:
        raise SystemExit("%s is not a DG2 run" % cfg.get("run_id"))
    o = AG.q80(rd, GG.DM1A_RUN)
    S0, S1, S2, S3, S4 = (o[k] for k in ("S0", "S1", "S2", "S3", "S4"))
    met = bool(o["Q80_met"])
    if not S0["ok"]:
        dec = "0 DG2 S0 false (%s) -> not judged: read-only diagnosis, ask; no answer -> delivery by the AM-D22 rule without DG2" % (S0.get("hard") or "validity")
    elif met and S4.get("verdict") == "pass":
        dec = "1 Q80 met and verdict_D PASS -> DD3 of DG2 (+48 s) then its every-frame re-record; show the user"
    elif met:
        dec = "1 Q80 met (verdict_D %s) -> show the user; no answer -> DG2's every-frame re-record (delivery). The shape search has ended" % S4.get("verdict")
    else:
        dec = ("2 Q80 not met -> Q73 stop (two groove rounds without meeting Q80): the shape search ends (no DG3); ask; no answer -> delivery by "
               "the AM-D22 rule. Failed: %s" % ", ".join(n for n, s in (("S1 PERIODIC", S1), ("S2 section vs DM1A", S2), ("S3 H_front floor", S3),
                                                                     ("S4 verdict_D", S4)) if not s["ok"]))
    d2 = AG._load(os.path.join(rd, "pana", "planD_ana.json")) or {}
    d1 = AG._load(os.path.join(D.DG1_RUN, "pana", "planD_ana.json")) or {}
    plan = AN.PA.load_plan(cfg)
    q73_dg1 = None
    if d1.get("medians_judged") and d2.get("medians_judged"):
        q73_dg1 = AN.q73_test(d2["medians_judged"], d1["medians_judged"], plan["criteria"]["q73_vs_DA3"])
    hf = (d2.get("medians_judged") or {}).get("H_front")
    margin = (hf / S3["floor_m"] - 1.0) if (hf is not None and S3.get("floor_m")) else None
    o.update(tool="flip50dg2/g50dg2_ana.py q80 (flip50g/g50g_ana.q80 in memory)", decision=decision_note(dec),
             dg2=dict(variant=v, frozen=D.DG2_FROZEN_REL, sha256=D.sha256_file(D.DG2_FROZEN), am=D.AMENDMENT, params=D.params(v)),
             report_only=dict(o.get("report_only") or {}, q73_vs_DG1=q73_dg1, S3_margin=margin,
                              S3_note=("S3 passed by %.1f %% (< 1.5 %%): within run noise (DM1 vs DM1A 0.14 m, U3 rms 1.5 %%), not an achievement" % (100 * margin))
                              if (S3["ok"] and margin is not None and margin < 0.015) else None))
    od = GC.guard_out50(os.path.join(rd, "pana"))
    json.dump(AN.A46._clean(o), open(os.path.join(od, "q80_DG2.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    _move_dg1_named(rd, "q80_DG1.json")
    return o


def decision_note(s):
    return s


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    GG.frozen()
    D.frozen_dg2()
    cfg = AN.PA.load_cfg(os.path.abspath(pos[1]))
    v, kind = D.variant_of(cfg.get("run_id"))
    if v is None:
        raise SystemExit("not a DG2 run: %s" % cfg.get("run_id"))
    _label(v)
    if pos[0] == "smoke":
        o = smoke(pos[1])
        print("DG2 smoke gates ok %s (never judged)" % o["ok"], json.dumps(o["gates"], ensure_ascii=False), "| next:", o["next"])
    elif pos[0] == "q80":
        o = q80(pos[1])
        print("Q80 met %s | %s" % (o["Q80_met"], o["decision"]))
        print(json.dumps({k: o[k]["ok"] for k in ("S0", "S1", "S2", "S3", "S4")}))
    elif pos[0] in ("all", "report"):
        AN.main()
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
