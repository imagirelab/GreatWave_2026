# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): read a DG1 calculation (py -3.10 -B). 2026-10-17 written new (Claude).
It patches the bed in memory (g50g_common.patch_modules: every numpy bed consumer of g50_ana / g49_periodic_ana / g46 sections sees the
groove of the cfg: h_b, the q track, the section fill / cavity rule, the still-offset masks) and runs the UNCHANGED flip50/g50_ana.py
(periodic_ana, plan_d_numbers, decide_D, report --prev, smoke). Added, DG1 only:
  smoke  after g50_ana smoke: the DG1 smoke gates of dg1_frozen.json smoke (gates_as_before = smoke_D.json gates; inlet / side mean ratio
         within 0.03 of 0.945 / 0.930; the run's hip sha = build_check_g.json and CTRL gr_* = frozen; frame-1 particles (a) count = groove
         model within 0.2 % and the difference to SMOKE50DA = the model difference within 10 %, (b) the core-box seeding
         (groove_seed_check.json, reading of g50g_common.readings), (c) none more than 0.25 vox below the groove bed) and the report-only
         differences to SMOKE50DA -> pana/smoke_DG1.json (ok = all gates)
  q80    the frozen Q80 test S0-S4 (dg1_frozen.json criteria) from <DG1 run>/pana/planD_ana.json and the DM1A one -> pana/q80_DG1.json
usage:
  py -3.10 -B g50g_ana.py smoke <SMOKE50DG1 run>
  py -3.10 -B g50g_ana.py all <DG1 run> --prev=<DM1A run>      (g50_ana all with the groove; Q73 vs DM1A in planD_ana.json)
  py -3.10 -B g50g_ana.py report <DG1 run> --prev=<DM1A run>
  py -3.10 -B g50g_ana.py q80 <DG1 run> [--prev=<DM1A run>]     (after all/report)
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g50g_common as GG           # noqa: E402

GC = GG.patch_modules()            # before g50_ana imports g50_common / g49_periodic_ana
sys.path.insert(0, GG.TOOLS50)
import g50_ana as AN               # noqa: E402  flip50 (unchanged file; uses the patched g50_common / g49_common)

SMOKE_REF = dict(inlet_mean_ratio=0.945, side_mean_ratio=0.930, tol=0.03)     # dg1_frozen.json smoke.gates_added_for_DG1 [chosen]

# 2026-10-17 review fix (labels only): the unchanged g50_ana texts call the bed of every D run "D19B" / "a straight 1:10 beach"; for a cfg
# with the groove the smoke mp4 header and the PERIODIC_ja.md title name the chosen groove pair instead (short: the smoke header is drawn
# without wrapping on a 1600 px frame).
_LABEL_FIX = (("、海底 D19B。", "、海底 D19B＋選んだ浅い溝 2 本（x 238〜350 m）【選び】。"),
              ("まっすぐな 1:10 の浜", "1:10 の浜＋選んだ浅い溝 2 本【選び】"))


def _fix_label(s):
    if isinstance(s, str):
        for a, b in _LABEL_FIX:
            s = s.replace(a, b)
    return s


def _has_groove(cfg):
    try:
        return GG.groove_of(GC.bed_spec(cfg)) is not None
    except Exception:
        return False


_ORIG_MD_D = AN.PA.md


def md_g(o, cfg):
    s = _ORIG_MD_D(o, cfg)
    return _fix_label(s) if _has_groove(cfg) else s


AN.PA.md = md_g
_ORIG_SMOKE_VIDEO = AN.smoke_video


def smoke_video_g(xs, ys, tt, eta, cfg, *a, **k):
    if not _has_groove(cfg):
        return _ORIG_SMOKE_VIDEO(xs, ys, tt, eta, cfg, *a, **k)
    from PIL import ImageDraw
    orig_text = ImageDraw.ImageDraw.text

    def text_g(self, xy, text, *aa, **kk):
        return orig_text(self, xy, _fix_label(text), *aa, **kk)
    ImageDraw.ImageDraw.text = text_g
    try:
        return _ORIG_SMOKE_VIDEO(xs, ys, tt, eta, cfg, *a, **k)
    finally:
        ImageDraw.ImageDraw.text = orig_text


AN.smoke_video = smoke_video_g


def _load(p):
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def _fin(v):
    return v is not None and isinstance(v, (int, float)) and math.isfinite(float(v))


def run_records(rd):
    import glob
    out = []
    for p in sorted(glob.glob(os.path.join(rd, "run_c*.json"))):
        out.append(json.load(open(p, encoding="utf8")))
    return out


def validity(rd, cfg):
    """DG1 validity (health hard item): the run's hip sha = build_check_g.json, the CTRL gr_* = frozen, the cfg's dg1_frozen sha = AM-D20 and
    the file still has it."""
    recs = run_records(rd)
    bc = _load(GG.BUILD_CHECK_G) or {}
    shas = sorted(set(r.get("hip_sha256") for r in recs))
    hips = sorted(set(str(r.get("hip")) for r in recs))
    gr = [{k: (r.get("bed_spec_ctrl") or {}).get(k) for k in GG.CTRL_KEYS} for r in recs]
    out = dict(hip_sha256=shas, hip=hips, build_check_g_hip_sha256=bc.get("hip_sha256"),
               hip_ok=bool(recs and len(shas) == 1 and shas[0] == bc.get("hip_sha256") and all(os.path.normcase(h) == os.path.normcase(GG.HIP_G) for h in hips)),
               ctrl_gr=gr[0] if gr else None, ctrl_gr_ok=bool(gr and all(g == GG.SPEC_GR_ON for g in gr)),
               cfg_groove_bad=GG.cfg_groove_ok(cfg), frozen_sha_ok=bool(GG.sha256_file(GG.DG1_FROZEN) == GG.DG1_SHA256))
    out["ok"] = bool(out["hip_ok"] and out["ctrl_gr_ok"] and not out["cfg_groove_bad"] and out["frozen_sha_ok"])
    return out


def first_harmonic_rows(rd, xs_q=(240.0, 260.0, 280.0), y_band=(10.0, 15.0)):
    """report only: first-harmonic amplitude |A1| on the groove rows |y| 10-15 m at x 240 / 260 / 280 m over the last full period (hf records)."""
    PA = AN.PA
    H = AN.PM.load_hf(rd)
    recs = PA.run_recs(rd)
    off = PA.still_off(recs)
    cfg = PA.load_cfg(rd)
    T = float((cfg.get("sf") or {}).get("T", 12.0)); om = 2 * math.pi / T
    xs, ys, tt = H["xs"], H["ys"], H["t"]
    eta = H["eta"].astype(np.float64) - off
    t1 = float(tt[-1]); m = tt >= t1 - T - 1e-9
    jy = (ys >= y_band[0]) & (ys <= y_band[1])
    out = {}
    for xq in xs_q:
        ix = int(np.argmin(np.abs(xs - xq)))
        A = AN.first_harmonic(eta[m][:, :, ix], tt[m], om)
        out["x%g" % xq] = dict(x=float(xs[ix]), A1_mean_groove_rows=float(np.mean(np.abs(A[jy]))), A1_axis=float(np.abs(A[int(np.argmin(np.abs(ys - 0.5)))])))
    return dict(window_s=[t1 - T, t1], y_band=list(y_band), rows=out)


def smoke_dg1(rd):
    rd = os.path.abspath(rd).replace("\\", "/")
    o = AN.smoke(rd)                                    # the unchanged frozen smoke gates (smoke_D.json, smoke mp4) with the groove bed
    cfg = AN.PA.load_cfg(rd)
    ref = _load(os.path.join(GG.SMOKE50DA_RUN, "pana", "smoke_D.json")) or {}
    ref_run = _load(os.path.join(GG.SMOKE50DA_RUN, "run.json")) or {}
    gates = {}
    for k, v in (o.get("gates") or {}).items():
        gates["as_before." + k] = bool(v)
    gg = o.get("gauges") or {}
    gates["inlet_gauges_as_before"] = bool(_fin(gg.get("inlet_mean_ratio")) and _fin(gg.get("side_mean_ratio"))
                                           and abs(gg["inlet_mean_ratio"] - SMOKE_REF["inlet_mean_ratio"]) <= SMOKE_REF["tol"]
                                           and abs(gg["side_mean_ratio"] - SMOKE_REF["side_mean_ratio"]) <= SMOKE_REF["tol"])
    val = validity(rd, cfg)
    gates["hip_is_the_groove_hip"] = bool(val["hip_ok"] and val["ctrl_gr_ok"] and val["frozen_sha_ok"] and not val["cfg_groove_bad"])
    recs = run_records(rd)
    ps1 = None
    for r in recs:
        ps = ((r.get("info") or {}).get("pstats") or {}).get("1")
        if ps:
            ps1 = ps
    P = cfg["parms"]
    spec = GC.bed_spec(cfg)
    n_model = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), float(P["dp"]), zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))[0]
    D19 = {k: v for k, v in spec.items() if not k.startswith("gr_")}
    n_model0 = GC.count_particles(D19, float(P["Lx"]), float(P["W"]), float(P["dp"]), zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))[0]
    ref_ps1 = ((ref_run.get("info") or {}).get("pstats") or {}).get("1") or {}
    a = dict(frame1_n=(ps1 or {}).get("n"), model_groove=int(n_model), model_D19B=int(n_model0), smoke50DA_frame1_n=ref_ps1.get("n"))
    if ps1 and ref_ps1.get("n"):
        a["ratio"] = float(ps1["n"]) / n_model
        a["diff_vs_smoke50DA"] = int(ps1["n"] - ref_ps1["n"]); a["model_diff"] = int(n_model - n_model0)
        a["diff_rel_err"] = float(a["diff_vs_smoke50DA"] / max(a["model_diff"], 1) - 1.0)
        a["ok"] = bool(abs(a["ratio"] - 1.0) < 0.002 and abs(a["diff_rel_err"]) <= 0.10)
    else:
        a["ok"] = False
    seed = _load(os.path.join(rd, "groove_seed_check.json")) or {}
    core = seed.get("core") or {}
    b = dict(core, seed_particles=seed.get("particles"), seed_error=seed.get("error"))
    b["seed_equals_frame1"] = bool(ps1 is not None and seed.get("particles") == ps1.get("n"))
    # 2026-10-17 review fix: the reading is the one in force when the gates are READ (g50g_common.readings()), not the one baked into
    # groove_seed_check.json at the smoke launch; the three pass flags are recorded there, so a dated amendment written after the launch
    # (but before this read) applies without a re-smoke
    rd_now, rsrc = GG.readings()
    sel = rd_now["smoke_b"]
    flags = dict(literal_per_column=core.get("literal_per_column_pass"), medians=core.get("medians_pass"), model=core.get("model_pass"))
    flags["medians+model"] = bool(core.get("medians_pass") and core.get("model_pass"))
    b.update(ok_at_seed_launch=core.get("ok"), reading_at_seed_launch=core.get("reading"), reading=sel,
             reading_source=rsrc or "default (literal frozen text)", ok=bool(flags.get(sel)))
    b["gate"] = bool(b["ok"] and b["seed_equals_frame1"] and not seed.get("error"))
    vox = float(P["dp"]) * float(P["gridscale"])
    c = dict(frame1_n_below_groove_bed_quarter_vox=(ps1 or {}).get("n_below_bed"), frame1_gap_min_m=(ps1 or {}).get("gap_min"),
             seed_n_below=seed.get("n_below_groove_bed_quarter_vox"), rule="gap < -0.25 vox (%.2f m) against the groove bed" % (0.25 * vox),
             bed_spec_has_groove=bool(GG.groove_of(((recs[0] if recs else {}).get("bed_spec_ctrl") or {}))))
    c["ok"] = bool(ps1 is not None and ps1.get("n_below_bed") == 0 and c["bed_spec_has_groove"])
    gates["houdini_bed_equals_numpy_at_grooves_a"] = a["ok"]
    gates["houdini_bed_equals_numpy_at_grooves_b"] = b["gate"]
    gates["houdini_bed_equals_numpy_at_grooves_c"] = c["ok"]
    rep = dict(gauge_ratio_diff_vs_smoke50DA={k: (v.get("ratio") - ((ref.get("gauges") or {}).get("rows") or {}).get(k, {}).get("ratio", float("nan")))
                                              for k, v in (gg.get("rows") or {}).items() if _fin(v.get("ratio"))},
               focus=dict(x_hot=(o.get("focus") or {}).get("x_hot"), x_hot_ref=(ref.get("focus") or {}).get("x_hot"),
                          contrast=(o.get("focus") or {}).get("contrast_at_hot"), contrast_ref=(ref.get("focus") or {}).get("contrast_at_hot")),
               pattern_corr=(o.get("pattern_x160") or {}).get("complex_corr_y_le_95"), pattern_corr_ref=(ref.get("pattern_x160") or {}).get("complex_corr_y_le_95"),
               launches=o.get("launches"), wall_ref_s=581.8)
    try:
        rep["groove_rows_first_harmonic"] = first_harmonic_rows(rd)
        rep["groove_rows_first_harmonic_ref"] = first_harmonic_rows(GG.SMOKE50DA_RUN) if os.path.isdir(GG.SMOKE50DA_RUN) else None
    except Exception as e:
        rep["groove_rows_first_harmonic"] = dict(error=repr(e)[:300])
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip50g/g50g_ana.py smoke", judged=False,
               dg1=GG.frozen_ref(), readings=dict(zip(("readings", "source"), GG.readings())), gates=gates, a=a, b=b, c=c, validity=val,
               smoke_D_ok=o.get("ok"), report_only=rep, video=o.get("video"))
    out["ok"] = bool(all(gates.values()))
    out["next"] = ("all DG1 smoke gates pass -> DG1 main run (py -3.10 %s/g50g_chain.py %s)" % (GG.TOOLS50G, GG.B50 + "/runs/ready/" + GG.RUN_MAIN + ".json")
                   if out["ok"] else
                   "DG1 smoke gate(s) failed (%s): an implementation fault -> fix the code and re-smoke (not a round); a failure caused by the groove "
                   "physics or a fix that would change a frozen number -> stop and ask" % ", ".join(k for k, v in gates.items() if not v))
    od = GC.guard_out50(os.path.join(rd, "pana"))
    json.dump(AN.A46._clean(out), open(os.path.join(od, "smoke_DG1.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    return out


def q80(rd, prev=None):
    """dg1_frozen.json criteria: Q80 met only if S0-S4 all hold (script; no human judgement)."""
    rd = os.path.abspath(rd).replace("\\", "/")
    prev = os.path.abspath(prev or GG.DM1A_RUN).replace("\\", "/")
    d = _load(os.path.join(rd, "pana", "planD_ana.json"))
    p = _load(os.path.join(prev, "pana", "planD_ana.json"))
    if d is None or p is None:
        raise SystemExit("planD_ana.json missing (%s / %s): run g50g_ana.py all <DG1 run> --prev=<DM1A run> first" % (rd, prev))
    cfg = AN.PA.load_cfg(rd)
    plan = AN.PA.load_plan(cfg)
    crit = plan["criteria"]
    nw = crit["q73_vs_DA3"]["nothing_worse"]
    h = d.get("health") or {}
    val = validity(rd, cfg)
    S0 = dict(hard=h.get("hard"), dg1_validity=val, soft_printed=h.get("soft"))
    S0["ok"] = bool(not h.get("hard") and val["ok"])
    per = d.get("periodic") or {}
    S1 = dict(PERIODIC=per.get("PERIODIC"), PERIODIC_k=per.get("PERIODIC_k"), windows=per.get("windows"), rule=per.get("rule"))
    S1["ok"] = bool(per.get("PERIODIC") is True)
    qp = d.get("q73_vs_previous_round") or {}
    S2 = dict(previous_round=d.get("previous_round"), expected_previous=os.path.basename(prev), d_back_best_deg=qp.get("d_back_best_deg"),
              d_width07_best=qp.get("d_width07_best"), d_H_front_m=qp.get("d_H_front_m"), worse_items=qp.get("worse_items"),
              thresholds=dict(back_deg=nw["back_deg"], width07=nw["width07"], H_front_m=nw["H_front_m"]))
    wi = qp.get("worse_items") or {}
    S2["ok"] = bool(d.get("previous_round") == os.path.basename(prev) and wi and not any(wi.get(k) for k in ("back", "width07", "H_front", "missing")))
    floor = float(crit["DA3_reference"]["H_front_m"]) + float(nw["H_front_m"])
    hf = (d.get("medians_judged") or {}).get("H_front")
    S3 = dict(H_front_median=hf, floor_m=floor, floor_rule="DA3 %.3f + (%g) m" % (crit["DA3_reference"]["H_front_m"], nw["H_front_m"]))
    S3["ok"] = bool(_fin(hf) and hf >= floor)
    dec = d.get("decision") or {}
    S4 = dict(verdict=dec.get("verdict"), rule=dec.get("rule"), next=dec.get("next"))
    S4["ok"] = bool(dec.get("verdict") in ("pass", "partial"))
    met = bool(S0["ok"] and S1["ok"] and S2["ok"] and S3["ok"] and S4["ok"])
    if not S0["ok"] and h.get("hard"):
        decision = "0 hard health -> not judged: diagnose read-only, stop and ask (%s)" % "; ".join(h.get("hard") or [])
    elif not S0["ok"]:
        decision = "0 DG1 validity failed (%s) -> not judged: diagnose read-only, stop and ask" % [k for k in ("hip_ok", "ctrl_gr_ok", "frozen_sha_ok") if not val.get(k)]
    elif met and dec.get("verdict") == "pass":
        decision = "1 Q80 met and verdict_D PASS -> DD3 (+48 s continuation, seamless 12 s loop) then show the user"
    elif met:
        decision = "1 Q80 met (verdict_D %s) -> stop and show the user (round 3 = the last D round)" % dec.get("verdict")
    else:
        decision = ("2 Q80 not met (不行): STOP. No further D round, no retune, no deeper groove; report with the mp4 and the tagged numbers. Failed: %s"
                    % ", ".join(n for n, s in (("S1 PERIODIC", S1), ("S2 section vs DM1A", S2), ("S3 H_front floor", S3), ("S4 verdict_D", S4)) if not s["ok"]))
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip50g/g50g_ana.py q80", dg1=GG.frozen_ref(),
               prev=os.path.basename(prev), S0=S0, S1=S1, S2=S2, S3=S3, S4=S4, Q80_met=met, decision=decision,
               report_only=dict(targets=d.get("targets"), q73_vs_DA3=d.get("q73_vs_DA3"), q73_vs_DM1A=qp, medians_judged=d.get("medians_judged"),
                                medians_DM1A=p.get("medians_judged"), improvement_vs_DM1A=qp.get("improvement"),
                                note="DG1 is expected to show 'no improvement' vs DM1A (back/width07 only by definition); reported so, never relabelled"),
               tags="measured (FLIP + the STUDY52 ruler, AI self-assessment); thresholds chosen and frozen before any DM1A / DF1A / DG1 result")
    od = GC.guard_out50(os.path.join(rd, "pana"))
    json.dump(AN.A46._clean(out), open(os.path.join(od, "q80_DG1.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    GG.frozen()
    if pos[0] == "smoke":
        o = smoke_dg1(pos[1])
        print("DG1 smoke gates ok %s (never judged)" % o["ok"], json.dumps(o["gates"], ensure_ascii=False), "| next:", o["next"])
    elif pos[0] == "q80":
        o = q80(pos[1], opt.get("prev"))
        print("Q80 met %s | %s" % (o["Q80_met"], o["decision"]))
        print(json.dumps({k: o[k]["ok"] for k in ("S0", "S1", "S2", "S3", "S4")}))
    elif pos[0] in ("all", "report"):
        AN.main()
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
