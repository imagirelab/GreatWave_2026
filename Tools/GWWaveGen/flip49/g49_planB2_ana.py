# -*- coding: utf-8 -*-
"""FLIP49 campaign B round 2 (plan B2, 2026-10-16): numbers of the steep-ledge strips S2/S3, gate G2 (S2 vs S0) and the Q73 test of the
steep-ledge direction; S3 vs S1 is report-only (stand-in). py -3.10 -B; numpy, scipy, scikit-image via the read-only analysis modules.
Written new by the plan-B2 freeze step (Claude), before any S2/S3 run.

Reads (never edits): <run>/pana/periodic_ana.json and best_frames.json (g49_periodic_ana.py all, unchanged), the r2/hf records through
g49_planB_ana.measure (the round-1 per-breaker code, unchanged, so S2/S3 and S0/S1 are read with the same code), plan/plan_B2_frozen.json
(gate_G2 thresholds, stop rule) and the round-1 baselines strips/BS0_axDA3_T12H7p5/pana/planB_ana.json (S2) and
strips/BS1_axDA3_T12H10p7_standin/pana/planB_ana.json (S3), whose SHA-256 must equal the values frozen in the plan.
Writes <run>/pana/planB2_ana.json and planB2_table.txt; appends G2 (S2) or S3_report_only (S3) to campaignB/registry.jsonl once per run.
usage: py -3.10 -B g49_planB.py ana2 <run dir>
"""
import os, sys, json, time

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np                 # noqa: E402
import g49_common as GC            # noqa: E402
import g49_planB as PB             # noqa: E402
import g49_planB_ana as AB         # noqa: E402

PERIOD_T0 = 24.0                    # inlet.json level period means: 12 s periods from 24 s (as AM-B3 read them)


def _d(a, b):
    return (a - b) if (a is not None and b is not None) else None


def judged_period_idx(T, rows):
    """indices of the 12 s level periods (from 24 s) that contain the judged onsets and the period before each."""
    idx = set()
    for r in rows:
        i = int((float(r["t_on"]) - PERIOD_T0) // T)
        idx.update([i - 1, i])
    return sorted(i for i in idx if i >= 0)


def q73_B2(new, old, thr):
    """Q73 test of the steep-ledge direction (plan_B2 stop_rule.q73): improvement = best back >= +3 deg or best width07 <= -0.3,
    nothing worse than back -2 deg, width07 +0.2, crest-to-front-trough -0.5 m. A height gain alone is not an improvement here."""
    d_back = _d(new.get("back_best"), old.get("back_best"))
    d_w = _d(new.get("w07_best"), old.get("w07_best"))
    d_hf = _d(new.get("H_front"), old.get("H_front"))
    nw = thr["nothing_worse_than"]
    imp = dict(back=bool(d_back is not None and d_back >= 3.0), width07=bool(d_w is not None and d_w <= -0.3))
    worse = dict(back=bool(d_back is not None and d_back < nw["back_deg"]), width07=bool(d_w is not None and d_w > nw["width07"]),
                 H_front=bool(d_hf is not None and d_hf < nw["H_front_m"]))
    return dict(d_back_best_deg=d_back, d_width07_best=d_w, d_H_front_m=d_hf, d_Hc_m=_d(new.get("Hc"), old.get("Hc")), improved_items=imp, worse_items=worse,
                improvement=bool(any(imp.values()) and not any(worse.values())))


def g2_items(m, base, jud, th):
    """the G2 items on medians m (S2 or S3) against base (S0 or S1)."""
    n_lip = sum(1 for r in jud if r.get("lip_max") is not None and r["lip_max"] >= th["lip_min"])
    n_ledge = sum(1 for r in jud if r.get("x_on") is not None and r["x_on"] >= th["x_ledge_foot_m"] - 1e-9)
    d_on = _d(m.get("back_on"), base.get("back_on"))
    d_best = _d(m.get("back_best"), base.get("back_best"))
    it = dict(
        back_on=dict(value=m.get("back_on"), d_vs_base=d_on, ok=bool(m.get("back_on") is not None and m["back_on"] >= th["back_on_min_deg"]
                                                                    and d_on is not None and d_on >= th["d_back_on_min_deg"])),
        back_best=dict(value=m.get("back_best"), d_vs_base=d_best, ok=bool(d_best is not None and d_best >= th["d_back_best_min_deg"])),
        w07_best=dict(value=m.get("w07_best"), d_vs_base=_d(m.get("w07_best"), base.get("w07_best")),
                      ok=bool(m.get("w07_best") is not None and m["w07_best"] <= th["w07_best_max"])),
        lip=dict(n_ge_min=n_lip, ok=bool(n_lip >= th["n_lip_min"])),
        H_front=dict(value=m.get("H_front"), d_vs_base=_d(m.get("H_front"), base.get("H_front")),
                     ok=bool(m.get("H_front") is not None and m["H_front"] >= th["H_front_min_m"])),
        Hc_reported=dict(value=m.get("Hc"), d_vs_base=_d(m.get("Hc"), base.get("Hc"))),
        n_judged=dict(n=len(jud), ok=bool(len(jud) >= th["n_judged_min"])),
        n_on_ledge=dict(n=n_ledge, ok=bool(n_ledge >= th["n_on_ledge_min"])))
    return it


def append_registry_B2(entry):
    os.makedirs(os.path.dirname(PB.REGISTRY), exist_ok=True)
    entry = dict(entry, registered_at=time.strftime("%Y-%m-%d %H:%M:%S"), plan_sha256=GC.sha256_file(PB.PLAN_B2))
    with open(PB.REGISTRY, "a", encoding="utf8", newline="\n") as fh:
        fh.write(json.dumps(AB.clean(entry), ensure_ascii=False) + "\n")
    return entry


def main(argv, cfg_override=None):
    """--dry=1: self-test mode (cfg_override given by a test harness): nothing is appended to the registry and nothing is written into the run;
    --out=<dir> then receives the json/table."""
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    rd = os.path.abspath(pos[0]).replace("\\", "/")
    dry = bool(opt.get("dry"))
    if cfg_override is not None and not dry:
        raise SystemExit("cfg_override is for the --dry self-test only")
    cfg = cfg_override if cfg_override is not None else json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    if (cfg.get("case") or {}).get("plan_frozen") != PB.PLAN_B2_REL:
        raise SystemExit("not a plan-B2 run")
    sp = open(PB.PLAN_B2 + ".sha256", encoding="utf8").read().split()[0]
    if sp != GC.sha256_file(PB.PLAN_B2):
        raise SystemExit("plan_B2_frozen.json changed (SHA differs from .sha256)")
    plan = json.load(open(PB.PLAN_B2, encoding="utf8"))
    qid = (cfg.get("case") or {}).get("queue_id")
    if qid not in ("S2", "S3"):
        raise SystemExit("plan B2 analyses S2/S3 only (DL1 needs its own amendment first)")
    bname = {"S2": "S0", "S3": "S1"}[qid]
    bref = plan["round1_results"][bname]
    bp = os.path.join(GC.REPO, bref["source"])
    if GC.sha256_file(bp) != bref["sha256"]:
        raise SystemExit("the round-1 baseline %s changed after the freeze (SHA differs from plan_B2 round1_results)" % bref["source"])
    b0 = json.load(open(bp, encoding="utf8"))
    base = b0["medians_judged"]
    pap = os.path.join(rd, "pana", "periodic_ana.json")
    if not os.path.exists(pap):
        raise SystemExit("run `py -3.10 -B g49_periodic_ana.py all %s` first" % rd)
    pa = json.load(open(pap, encoding="utf8"))
    bf = {b["k"]: b for b in json.load(open(os.path.join(rd, "pana", "best_frames.json"), encoding="utf8"))["per_breaker"]}
    rows, cx = AB.measure(rd, pa, bf)
    T = float(pa["T"])
    jw = (cfg.get("case") or {}).get("judged_onset_window_s") or list(PB.JUDGE_T)
    jud = [r for r in rows if float(jw[0]) - 1e-9 <= r["t_on"] <= float(jw[1]) + 1e-9]
    for r in rows:
        r["judged"] = r in jud
    meds = {k: AB.med([r.get(k) for r in jud]) for k in AB.MED_KEYS}
    Hdesign = float((cfg.get("wave") or {}).get("H_m") or 0.0)
    inl = AB.inlet_numbers(rd, pa, Hdesign)
    wins = [(r["k"], r["t_on"] - T, r["t_on"] + 0.25) for r in jud]
    hits = AB.scan_breaking_lt180(cx, wins)
    pa_lt180 = [e for e in (pa.get("breaking_offshore_of_180m") or []) if any(a <= e["on_t"] <= b for _, a, b in wins)]
    periods_lt180 = sorted(set([h["period_k"] for h in hits] + [k for (k, a, b) in wins for e in pa_lt180 if a <= e["on_t"] <= b]))
    hl = pa.get("health") or {}
    vol = (hl.get("volume") or {}).get("corrected_max_rel")
    leak = (hl.get("bed_leak_max") or {}).get("frac", 0.0)
    th = plan["gate_G2"]["thresholds"]
    # health (plan_B2 frozen_criteria.health.strip_health_S2/S3): pass/fail items and reported items
    hs = dict(inlet_H_within_5pct=bool(inl["H_rel"] is not None and abs(inl["H_rel"]) <= 0.05), bed_leak_ok=bool(leak < 1e-4),
              completed=bool(rows))
    if qid == "S3":
        hs.pop("inlet_H_within_5pct")              # S3 inlet reported (S1 arrived -12 %), as S1
    # comparability flags vs the round-1 partner (frozen in strip_health_S2)
    pidx = judged_period_idx(T, jud)
    lv_new = inl.get("levels_flat_period_means") or []
    lv_old = bref.get("flat_level_period_means") or []
    dl = [abs(lv_new[i] - lv_old[i]) for i in pidx if i < len(lv_new) and i < len(lv_old) and lv_new[i] is not None and lv_old[i] is not None]
    comp = dict(flat_level_period_idx=pidx, flat_level_max_abs_diff_m=(max(dl) if dl else None),
                volume_stageC_max_rel=vol, volume_partner=bref.get("volume_stageC_max_rel"),
                volume_abs_diff_points=(abs(vol - bref["volume_stageC_max_rel"]) * 100.0 if (vol is not None and bref.get("volume_stageC_max_rel") is not None) else None),
                reflection_Kr=inl.get("Kr"))
    comp["flags"] = [f for f, c in (("flat level differs > 0.5 m", comp["flat_level_max_abs_diff_m"] is not None and comp["flat_level_max_abs_diff_m"] > 0.5),
                                    ("interior volume differs > 2 points", comp["volume_abs_diff_points"] is not None and comp["volume_abs_diff_points"] > 2.0),
                                    ("ledge reflection Kr > 0.20", comp["reflection_Kr"] is not None and comp["reflection_Kr"] > 0.20)) if c]
    comp["comparison_weakened"] = bool(comp["flags"])
    items = g2_items(meds, base, jud, th)
    pre_ok = bool(all(hs.values()) and items["n_judged"]["ok"] and items["n_on_ledge"]["ok"] and len(periods_lt180) <= th["periods_breaking_x_lt_180_max"])
    shape_ok = bool(items["back_on"]["ok"] and items["back_best"]["ok"] and items["w07_best"]["ok"] and items["lip"]["ok"] and items["H_front"]["ok"])
    q73 = q73_B2(meds, base, plan["stop_rule"]["q73"])
    hard = []
    if not items["n_on_ledge"]["ok"]:
        hard.append("fewer than 2 judged breakers reach the ledge foot")
    if len(periods_lt180) >= 2:
        hard.append("breaking at x < 180 m in >= 2 judged periods")
    out = dict(run_id=cfg["run_id"], queue_id=qid, date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_planB2_ana.py",
               plan=PB.PLAN_B2_REL, plan_sha256=sp, standin=bool((cfg.get("case") or {}).get("standin")), label=(cfg.get("case") or {}).get("label"),
               judged_rule="strip: onset %g-%g s" % (float(jw[0]), float(jw[1])), judged_k=[r["k"] for r in jud], report_only_k=[r["k"] for r in rows if not r["judged"]],
               medians_judged=meds, base=dict(name=bname, run_id=b0["run_id"], source=bref["source"], medians_judged={k: base.get(k) for k in AB.MED_KEYS}),
               d_vs_base={k: _d(meds.get(k), base.get(k)) for k in AB.MED_KEYS},
               inlet=inl, breaking_x_lt_180=dict(scan_hits=hits, periodic_ana_events=pa_lt180, periods=periods_lt180),
               health=dict(checks=hs, ok=bool(all(hs.values())), volume_corrected_max_rel=vol, bed_leak_frac=leak, still_offset_m=hl.get("still_offset_m"),
                           particles=hl.get("particles"), wall_h=hl.get("wall_h"), rule=plan["frozen_criteria"]["health"]["strip_health_%s" % qid]),
               comparability=comp, G2_items=items, Q73_vs_base=q73, hard_stops=hard,
               intervals_s=[float(b["t_on"] - a["t_on"]) for a, b in zip(rows[:-1], rows[1:])],
               print_ref=PB.PRINT_REF, rows=[{k: v for k, v in r.items() if k not in ("ruler", "track")} for r in rows],
               tags=dict(all_shape_numbers="measured (FLIP + STUDY52 ruler; AI self-assessment, the user judges print-likeness)",
                         gate_thresholds="chosen (frozen in plan_B2_frozen.json before S2)"))
    reg = AB.registry()
    if qid == "S2":
        if not all(hs.values()):
            res = "health_fail"
            verdict = "S2 health fails (%s): diagnose, fix the preset and rerun S2 (not a round); G2 not applied" % [k for k, v in hs.items() if not v]
        elif hard:
            res = "stop"
            verdict = "STOP (hard stop: %s) -> stop and ask" % "; ".join(hard)
        elif pre_ok and shape_ok:
            res = "PASS"
            verdict = "G2 PASS -> freeze DL1 in an amendment (bed numbers, particles/wall, expected numbers from S2 through both transfer models), then build and run DL1"
        else:
            res = "FAIL"
            miss = [k for k in ("back_on", "back_best", "w07_best", "lip", "H_front", "n_judged", "n_on_ledge") if not items[k]["ok"]]
            verdict = "G2 FAIL (missing: %s) -> do not build DL1; after S3, stop and ask the user (plan_B2 gate_G2.then_fail)" % ", ".join(miss)
        if comp["comparison_weakened"]:
            verdict += " | comparison weakened: %s" % "; ".join(comp["flags"])
        out["G2"] = dict(result=res, verdict=verdict, prerequisites_ok=pre_ok, shape_items_ok=shape_ok, thresholds=th)
        if res == "PASS":
            tf = plan["gate_G2"]["transfer_2d_to_3d"]
            out["G2"]["DL1_expected_register"] = {k: dict(ratio_model=(meds[a] * tf[k]["ratio"]) if meds.get(a) is not None else None,
                                                          offset_model=(meds[a] + tf[k]["offset"]) if meds.get(a) is not None else None)
                                                  for k, a in (("back_on", "back_on"), ("back_best", "back_best"), ("w07_best", "w07_best"), ("H_front", "H_front"), ("Hc", "Hc"))}
        prev = [e for e in reg if e.get("what") == "G2" and e.get("run_id") == cfg["run_id"]]
        if dry:
            out["registered"] = "dry run: not registered"
        elif not prev and res != "health_fail":
            out["registered"] = append_registry_B2(dict(what="G2", plan=PB.PLAN_B2_REL, run_id=cfg["run_id"], result=res, items=items, Q73_vs_S0=q73,
                                                        comparability=comp, base_run=b0["run_id"], expected_DL1=out["G2"].get("DL1_expected_register"),
                                                        note="registered before S3 is read (plan_B2 queue S2 decision_after)"))
        elif prev:
            out["registered"] = prev[-1]
    else:
        g2 = [e for e in reg if e.get("what") == "G2" and e.get("plan") == PB.PLAN_B2_REL]
        out["S3_report"] = dict(note="STAND-IN: report-only, never passes or fails G2; ledge effect at the stand-in's q (S3 vs S1)",
                                items_as_if=items, G2_of_S2=(g2[-1]["result"] if g2 else None))
        if not g2 and not opt.get("force"):
            out["warning"] = "S2's G2 is not registered yet (the frozen order is S2, G2, then S3)"
        prev = [e for e in reg if e.get("what") == "S3_report_only" and e.get("run_id") == cfg["run_id"]]
        if dry:
            out["registered"] = "dry run: not registered"
        elif not prev:
            out["registered"] = append_registry_B2(dict(what="S3_report_only", plan=PB.PLAN_B2_REL, run_id=cfg["run_id"], items_as_if=items, Q73_like_vs_S1=q73,
                                                        comparability=comp, base_run=b0["run_id"]))
        else:
            out["registered"] = prev[-1]
    if dry:
        txt = table(out)
        print(txt)
        if opt.get("out"):
            os.makedirs(opt["out"], exist_ok=True)
            json.dump(AB.clean(out), open(os.path.join(opt["out"], "planB2_ana_dry.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
            open(os.path.join(opt["out"], "planB2_table_dry.txt"), "w", encoding="utf8", newline="\n").write(txt)
        return out
    od = GC.guard_out49(os.path.join(rd, "pana"))
    json.dump(AB.clean(out), open(os.path.join(od, "planB2_ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(AB.clean(dict(run_id=cfg["run_id"], rows=rows)), open(os.path.join(od, "planB2_rows_full.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    txt = table(out)
    open(os.path.join(od, "planB2_table.txt"), "w", encoding="utf8", newline="\n").write(txt)
    print(txt)
    return out


def table(o):
    f = AB._f
    L = [AB.table(dict(o, plan_sha256=o["plan_sha256"])).rstrip("\n").replace("next: -", "")]
    b = o["base"]["medians_judged"]
    L.append("base %s (%s): back on %s best %s | w07 best %s | Hfront %s Hc %s | lip %s" % (
        o["base"]["name"], o["base"]["run_id"], f(b.get("back_on"), "%.1f"), f(b.get("back_best"), "%.1f"), f(b.get("w07_best")), f(b.get("H_front")),
        f(b.get("Hc")), f(b.get("lip_max"))))
    L.append("comparability: %s" % {k: v for k, v in o["comparability"].items() if k != "flat_level_period_idx"})
    L.append("G2 items: %s" % {k: v.get("ok", "-") for k, v in o["G2_items"].items()})
    L.append("Q73 vs base: %s" % o["Q73_vs_base"])
    if "G2" in o:
        L.append("G2: %s" % o["G2"]["verdict"])
    if "S3_report" in o:
        L.append("S3: %s (S2's G2: %s)" % (o["S3_report"]["note"], o["S3_report"]["G2_of_S2"]))
    return "\n".join(x for x in L if x.strip()) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main(sys.argv[1:])
