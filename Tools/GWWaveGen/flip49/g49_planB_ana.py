# -*- coding: utf-8 -*-
"""FLIP49 campaign B: plan-B per-breaker numbers of a strip (S0/S1) or 3D run, the S0 baseline registration and gate G1 (py -3.10 -B;
numpy, scipy, scikit-image via the read-only analysis modules). Written new 2026-10-16 (campaign-B implementation step, Claude).

Reads (never edits): <run>/pana/periodic_ana.json and best_frames.json (g49_periodic_ana.py all, unchanged), the r2/hf records through
g49_periodic_ana.Ctx49, the STUDY52 ruler (Tools/GWWaveGen/ruler/s52_shape.measure_mask), plan/plan_B_frozen.json (definitions, gate G1,
Q73 test). The per-breaker shape measures copy the D1 diagnosis (Unity/Build/FLIP49/diag_B/d1_measure.py + d1_summary.py, which gave the DA3
reference medians), so S0/S1 and DA3 are read with the same code:
  incoming back  = median of the hf-track back_deg_07_09 while the crest is over depth >= 16.5 m
  pre-onset max  = max ruler back_angle_07_09_deg over onset - 3 s .. onset;  onset = ruler frame nearest onset;  best = score3 best frame
  width07        = ruler width07_silhouette;  lip/chord/hood = P5 maxima over the shape window (periodic_ana);  hollow = hood_wall_x_rel;
  front foot     = front_x01_rel;  H_front / H_rear = crest - front / rear trough on the y 0.5 m top surface at onset.
Writes <run>/pana/planB_ana.json and planB_table.txt; S0 appends its baseline and the S0-DA3 offset to campaignB/registry.jsonl; S1 applies G1
and (on PASS) appends X1's registered expected back.
usage: py -3.10 -B g49_planB.py ana <run dir> [--force_register=1]
"""
import os, sys, json, math, glob, time

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/ruler", _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                 # noqa: E402
import g49_common as GC            # noqa: E402
import g49_planB as PB             # noqa: E402

FPS = 24.0


# ---------------------------------------------------------------- top-surface helpers (copied from diag_B/d1_measure.py, unchanged)
def cross_back(x, e, ic, level):
    for i in range(ic, 0, -1):
        if e[i - 1] < level <= e[i]:
            return float(x[i - 1] + (level - e[i - 1]) * (x[i] - x[i - 1]) / (e[i] - e[i - 1]))
    return float("nan")


def cross_fwd(x, e, ic, level):
    for i in range(ic, len(e) - 1):
        if e[i + 1] < level <= e[i]:
            return float(x[i] + (e[i] - level) * (x[i + 1] - x[i]) / (e[i] - e[i + 1]))
    return float("nan")


def profile_stats(x, e, xg, search=(-6.0, 2.0), Lmax=220.0):
    sel = np.where((x >= xg + search[0]) & (x <= xg + search[1]) & np.isfinite(e))[0]
    if not len(sel):
        return None
    ic = int(sel[np.argmax(e[sel])])
    ec = float(e[ic]); xc = float(x[ic])
    out = dict(xc=xc, eta_c=ec)
    j = ic; mn = ec; jm = ic
    while j < len(e) - 1 and x[j] < xc + 90.0:
        j += 1
        if not np.isfinite(e[j]):
            continue
        if e[j] < mn:
            mn = e[j]; jm = j
        elif e[j] > mn + 0.3 * max(ec, 1.0) and x[j] - x[jm] > 5.0:
            break
    out.update(trough_f=float(mn), trough_f_x=float(x[jm]))
    j = ic; mn = ec; jm = ic; jc2 = None
    while j > 0 and x[j] > xc - Lmax:
        j -= 1
        if not np.isfinite(e[j]):
            continue
        if e[j] < mn:
            mn = e[j]; jm = j
        elif e[j] > mn + 0.3 * max(ec, 1.0):
            k = j
            while k > 0 and np.isfinite(e[k - 1]) and e[k - 1] >= e[k]:
                k -= 1
            jc2 = k
            break
    out.update(trough_r=float(mn), trough_r_x=float(x[jm]))
    if jc2 is not None:
        out.update(crest2_x=float(x[jc2]), crest2_eta=float(e[jc2]), L_crest_spacing=float(xc - x[jc2]))
    for lev in (0.9, 0.7, 0.5, 0.3, 0.0):
        out["xb_%02d" % int(lev * 10)] = cross_back(x, e, ic, lev * ec) - xc
    for lev in (0.9, 0.7, 0.5):
        out["xf_%02d" % int(lev * 10)] = cross_fwd(x, e, ic, lev * ec) - xc
    d79 = out["xb_09"] - out["xb_07"]
    out["back_deg_07_09"] = math.degrees(math.atan2(0.2 * ec, d79)) if np.isfinite(d79) and ec > 0 else float("nan")
    out["w07_single"] = (out["xf_07"] - out["xb_07"]) / ec if ec > 0 else float("nan")
    tf = out["trough_f"]; Hf = ec - tf
    out["H_front"] = Hf
    out["H_rear"] = ec - out["trough_r"]
    return out


KEYS = ["eta_c", "x_c", "back_angle_07_09_deg", "width07_silhouette", "face_chord_deg_01_05", "front_x01_rel", "trough_front",
        "trough_rear", "H_front_m", "H_rear_m", "lip_thick_mid", "hood_area", "gap_max", "back_x07_rel", "back_x09_rel", "hood_wall_x_rel", "hood"]


def pick(mm):
    o = {}
    for k in KEYS:
        v = mm.get(k)
        o[k] = (bool(v) if isinstance(v, bool) else (float(v) if isinstance(v, (int, float)) and v is not None and np.isfinite(float(v)) else None))
    return o


def nz(v):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else v


def med(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        o = float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


# ---------------------------------------------------------------- measurement (d1_measure.run_3d for flip49, per periodic_ana wave)
def measure(rd, pa, bf):
    import g49_periodic_ana as PA
    cx = PA.Ctx49(rd, {})
    A46 = PA.A46
    S52 = A46.S52
    hf = cx.R1
    m1 = hf.get(hf.frames[1])[1]
    xh = m1["x0"] + m1["dx"] * np.arange(m1["res"][0])
    off = cx.off
    gain = {r["k"]: r for r in ((pa.get("periodic_A") or {}).get("report_c0_over_c_in") or {}).get("rows", [])}
    T = float(pa["T"])
    out = []
    for w in pa["waves"]:
        if w.get("t_on") is None:
            continue
        f_on = int(round(w["t_on"] * FPS)) + 1
        f_td = (int(round(w["t_td"] * FPS)) + 1) if w.get("t_td") else None
        b = (bf.get(w["k"]) or {})
        f_best = b.get("frame")
        if f_on not in hf.b:
            continue
        trk = {}
        xg = float(w["x_on"]); f = f_on
        while f in hf.b and f > f_on - int(30 * FPS):
            e = hf.get(f)[0][0] - off
            ps = profile_stats(xh, e, xg, search=(-3.0, 3.0) if f == f_on else (-2.5, 1.0))
            if ps is None:
                break
            ps["t"] = hf.get(f)[2]; ps["depth"] = float(-cx.bed_z(np.array([ps["xc"]]), 0.0)[0])
            trk[f] = ps; xg = ps["xc"]
            if xg < 140.0:
                break
            f -= 1
        xg = float(w["x_on"]); f = f_on + 1
        f_end = f_td or f_on + 48
        while f in hf.b and f <= f_end:
            e = hf.get(f)[0][0] - off
            ps = profile_stats(xh, e, xg, search=(-1.0, 3.0))
            if ps is None:
                break
            ps["t"] = hf.get(f)[2]; ps["depth"] = float(-cx.bed_z(np.array([ps["xc"]]), 0.0)[0]); trk[f] = ps; xg = ps["xc"]; f += 1
        sel = sorted(set([f for f in range(f_on - 72, f_on, 6)] + list(range(f_on, (f_td or f_on + 48) + 1, 3)) + ([f_best] if f_best else [])))
        rser = []
        for f in sel:
            if f not in cx.R2.b or f not in trk:
                continue
            try:
                M, X, Z, t = A46.r2_mask(cx, f, trk[f]["xc"])
                mm = S52.measure_mask(M, X, Z, flip_extra=dict(Lc=cx.Lc))
                row = pick(mm); row.update(frame=int(f), t=float(t), dt=(f - f_on) / FPS)
                rser.append(row)
            except Exception as ex:
                rser.append(dict(frame=int(f), error=repr(ex)[:160]))
        on = trk[f_on]
        ru = [q for q in rser if "error" not in q]
        on_r = min(ru, key=lambda q: abs(q["dt"])) if ru else {}
        pre = [q for q in ru if -3.01 <= q["dt"] < -0.01]
        best = [q for q in ru if q["frame"] == f_best]
        best = best[0] if best else {}
        inc = [q for q in trk.values() if q["depth"] is not None and q["depth"] >= 16.5 and np.isfinite(q.get("back_deg_07_09", np.nan))]
        g = gain.get(w["k"]) or {}
        row = dict(k=w["k"], t_on=w["t_on"], x_on=w["x_on"], h_b=w.get("hB"), Hc=w.get("Hc"), t_td=w.get("t_td"),
                   eta_c_hf=on["eta_c"], trough_f=on["trough_f"], trough_r=on["trough_r"], H_front=on["H_front"], H_rear=on["H_rear"],
                   back_inc=med([q["back_deg_07_09"] for q in inc]), inc_n=len(inc), eta_inc=med([q["eta_c"] for q in inc]),
                   back_pre_max=max([q["back_angle_07_09_deg"] for q in pre if q.get("back_angle_07_09_deg") is not None], default=None),
                   back_on=on_r.get("back_angle_07_09_deg"), w07_on=on_r.get("width07_silhouette"),
                   back_best=best.get("back_angle_07_09_deg"), w07_best=best.get("width07_silhouette"),
                   w07_min=min([q["width07_silhouette"] for q in ru if q.get("width07_silhouette") is not None and q["dt"] >= -1.0], default=None),
                   best_frame=f_best, best_t=b.get("t"), best_score3=b.get("score3"),
                   best_chord=best.get("face_chord_deg_01_05"), best_lip=best.get("lip_thick_mid"), best_hood=best.get("hood_area"),
                   best_front_foot=best.get("front_x01_rel"), best_hollow=best.get("hood_wall_x_rel"), best_eta_c=best.get("eta_c"),
                   chord_max=w.get("chord_max"), lip_max=w.get("lip_max"), hood_max=w.get("hood_max"),
                   P1=(w.get("judge") or {}).get("P1"), P5=(w.get("judge") or {}).get("P5"),
                   c_in=g.get("c_in"), gain_c0_over_cin=g.get("c0_over_c_in"),
                   ruler=rser, track=[dict(frame=f, **{k: trk[f].get(k) for k in ("t", "xc", "depth", "eta_c", "trough_f", "trough_r", "H_front", "H_rear",
                                                                               "back_deg_07_09", "w07_single", "xb_07", "xb_00")}) for f in sorted(trk)[::3]])
        out.append(row)
        print("k%d t_on %.2f x %.1f h_b %s Hc %.2f back inc/pre/on/best %s/%s/%s/%s w07 best %s lip %s" % (
            w["k"], w["t_on"], w["x_on"], _f(row["h_b"]), row["Hc"] or 0, _f(row["back_inc"], "%.1f"), _f(row["back_pre_max"], "%.1f"),
            _f(row["back_on"], "%.1f"), _f(row["back_best"], "%.1f"), _f(row["w07_best"]), _f(row["lip_max"])), flush=True)
    return out, cx


def _f(v, p="%.2f"):
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else p % v


def scan_breaking_lt180(cx, windows):
    """breaking at x < 180 m by the frozen event rule (g46 centre_events: thmax >= 90 deg, crest >= 1 m), scanned over x 5-180 m per window."""
    import g49_periodic_ana as PA
    hits = []
    for (k, a, b) in windows:
        ev = PA.A46.centre_events(cx, a, b, 5.0, 180.0)
        for e in ev:
            on = e.get("onset")
            if on and on["eta_c"] >= 1.0 and on["xc"] < 180.0:
                hits.append(dict(period_k=k, t=on["t"], x=on["xc"], eta_c=on["eta_c"], thmax=on["thmax"]))
    return hits


def inlet_numbers(rd, pa, Hdesign):
    inl = json.load(open(os.path.join(rd, "pana", "inlet.json"), encoding="utf8"))
    g = inl.get("gauges") or {}

    def H(x):
        q = g.get("x%g_y0.5" % x) or {}
        return q.get("H_mean"), q.get("crest_mean"), q.get("trough_mean"), q.get("H_cv")
    rows = {str(x): dict(zip(("H", "crest", "trough", "H_cv"), H(x))) for x in (110.0, 128.0, 160.0)}
    hmax = PB.linear_numbers()["Hmax_fit_17m_T12_m"]
    H128, H160 = rows["128.0"]["H"], rows["160.0"]["H"]
    q = ((H128 + H160) / 2.0 / hmax) if (H128 and H160) else None
    Hm = inl.get("H_mean_m")
    return dict(window_s=inl.get("window_s"), periods=inl.get("periods"), gauges=rows, H_mean_110_160_m=Hm, H_design_m=Hdesign,
                H_rel=(Hm / Hdesign - 1.0) if Hm else None, c_mps=inl.get("c_mps"), c_rel=inl.get("c_rel"), Kr=inl.get("Kr"),
                realized_q=q, Hmax_17m_m=hmax, crest_160_m=rows["160.0"]["crest"],
                levels_flat_period_means=((inl.get("levels") or {}).get("flat") or {}).get("period_means"),
                levels_reef_top_period_means=((inl.get("levels") or {}).get("reef_top") or {}).get("period_means"),
                levels_lagoon_period_means=((inl.get("levels") or {}).get("lagoon") or {}).get("period_means"),
                levels_window_s=inl.get("levels_window_s"))


MED_KEYS = ("t_on", "x_on", "h_b", "Hc", "H_front", "H_rear", "back_inc", "back_pre_max", "back_on", "back_best", "w07_on", "w07_best", "w07_min",
            "lip_max", "chord_max", "hood_max", "best_chord", "best_lip", "best_hood", "best_front_foot", "best_hollow", "gain_c0_over_cin", "best_score3")


def registry():
    if not os.path.exists(PB.REGISTRY):
        return []
    return [json.loads(l) for l in open(PB.REGISTRY, encoding="utf8") if l.strip()]


def append_registry(entry):
    os.makedirs(os.path.dirname(PB.REGISTRY), exist_ok=True)
    entry = dict(entry, registered_at=time.strftime("%Y-%m-%d %H:%M:%S"), plan_sha256=GC.sha256_file(PB.PLAN_B))
    with open(PB.REGISTRY, "a", encoding="utf8", newline="\n") as fh:
        fh.write(json.dumps(clean(entry), ensure_ascii=False) + "\n")
    return entry


def q73(new, old, label):
    """Q73 improvement test (plan stop_rule.q73) on medians: new vs old (dicts with back_best, w07_best, Hc)."""
    d_back = (new["back_best"] - old["back_best"]) if (new.get("back_best") is not None and old.get("back_best") is not None) else None
    d_w = (new["w07_best"] - old["w07_best"]) if (new.get("w07_best") is not None and old.get("w07_best") is not None) else None
    d_hc = (new["Hc"] - old["Hc"]) if (new.get("Hc") is not None and old.get("Hc") is not None) else None
    imp = [d_back is not None and d_back >= 3.0, d_w is not None and d_w <= -0.3, d_hc is not None and d_hc >= 0.7]
    worse = [d_back is not None and d_back < -2.0, d_w is not None and d_w > 0.2, d_hc is not None and d_hc < -0.5]
    return dict(round=label, d_back_best_deg=d_back, d_width07_best=d_w, d_Hc_m=d_hc, improved_items=dict(back=imp[0], width07=imp[1], Hc=imp[2]),
                worse_items=dict(back=worse[0], width07=worse[1], Hc=worse[2]), improvement=bool(any(imp) and not any(worse)))


def main(argv):
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    rd = os.path.abspath(pos[0]).replace("\\", "/")
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    if (cfg.get("case") or {}).get("plan_frozen") != PB.PLAN_B_REL:
        raise SystemExit("not a plan-B run")
    sp = open(PB.PLAN_B + ".sha256", encoding="utf8").read().split()[0]
    if sp != GC.sha256_file(PB.PLAN_B):
        raise SystemExit("plan_B_frozen.json changed (SHA differs from .sha256)")
    plan = json.load(open(PB.PLAN_B, encoding="utf8"))
    qid = (cfg.get("case") or {}).get("queue_id")
    pap = os.path.join(rd, "pana", "periodic_ana.json")
    if not os.path.exists(pap):
        raise SystemExit("run `py -3.10 -B g49_periodic_ana.py all %s` first" % rd)
    pa = json.load(open(pap, encoding="utf8"))
    bf = {b["k"]: b for b in json.load(open(os.path.join(rd, "pana", "best_frames.json"), encoding="utf8"))["per_breaker"]}
    rows, cx = measure(rd, pa, bf)
    strip = float(cfg["parms"]["W"]) <= 12.0
    T = float(pa["T"])
    if strip:
        jud = [r for r in rows if PB.JUDGE_T[0] - 1e-9 <= r["t_on"] <= PB.JUDGE_T[1] + 1e-9]
    else:
        jud = [r for r in rows if r["t_on"] >= GC.T_JUDGE - 1e-9]
    for r in rows:
        r["judged"] = r in jud
    meds = {k: med([r.get(k) for r in jud]) for k in MED_KEYS}
    Hdesign = float((cfg.get("wave") or {}).get("H_m") or 0.0)
    inl = inlet_numbers(rd, pa, Hdesign)
    # breaking at x < 180 m: the frozen event list of periodic_ana + a scan over x 5-180 m in the judged periods
    wins = [(r["k"], r["t_on"] - T, r["t_on"] + 0.25) for r in jud]
    hits = scan_breaking_lt180(cx, wins)
    pa_lt180 = [e for e in (pa.get("breaking_offshore_of_180m") or []) if any(a <= e["on_t"] <= b for _, a, b in wins)]
    periods_lt180 = sorted(set([h["period_k"] for h in hits] + [k for (k, a, b) in wins for e in pa_lt180 if a <= e["on_t"] <= b]))
    hl = pa.get("health") or {}
    vol = (hl.get("volume") or {}).get("corrected_max_rel")
    leak = (hl.get("bed_leak_max") or {}).get("frac", 0.0)
    out = dict(run_id=cfg["run_id"], queue_id=qid, date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_planB_ana.py",
               plan=PB.PLAN_B_REL, plan_sha256=sp, standin=bool((cfg.get("case") or {}).get("standin")), label=(cfg.get("case") or {}).get("label"),
               judged_rule=("strip: onset %g-%g s" % PB.JUDGE_T) if strip else "3D: onset >= 45 s",
               judged_k=[r["k"] for r in jud], report_only_k=[r["k"] for r in rows if not r["judged"]],
               medians_judged=meds, inlet=inl, breaking_x_lt_180=dict(scan_hits=hits, periodic_ana_events=pa_lt180, periods=periods_lt180),
               health=dict(volume_corrected_max_rel=vol, bed_leak_frac=leak, still_offset_m=hl.get("still_offset_m"), particles=hl.get("particles"),
                           wall_h=hl.get("wall_h"), mp4=hl.get("mp4")),
               intervals_s=[float(b["t_on"] - a["t_on"]) for a, b in zip(rows[:-1], rows[1:])],
               print_ref=PB.PRINT_REF, DA3_reference=plan["frozen_criteria"]["DA3_reference"],
               rows=[{k: v for k, v in r.items() if k not in ("ruler", "track")} for r in rows],
               tags=dict(all_shape_numbers="measured (FLIP + STUDY52 ruler; AI self-assessment, the user judges print-likeness)",
                         gate_thresholds="chosen (frozen in plan_B_frozen.json before S0)"))
    ref = plan["frozen_criteria"]["DA3_reference"]
    if qid == "S0":
        hs = dict(inlet_H_within_5pct=bool(inl["H_rel"] is not None and abs(inl["H_rel"]) <= 0.05),
                  no_breaking_x_lt_180=bool(not periods_lt180),
                  volume_lt_1pct=bool(vol is not None and vol < 0.01))
        out["health_S0"] = dict(checks=hs, ok=bool(all(hs.values())),
                                rule=plan["frozen_criteria"]["health"]["strip_health_S0"])
        base = dict(back_on=meds["back_on"], back_best=meds["back_best"], w07_best=meds["w07_best"], Hc=meds["Hc"], h_b=meds["h_b"],
                    back_pre_max=meds["back_pre_max"], back_inc=meds["back_inc"], lip_max=meds["lip_max"])
        offset = dict(back_on=_d(meds["back_on"], ref["back_on_deg"]), back_best=_d(meds["back_best"], ref["back_best_deg"]),
                      w07_best=_d(meds["w07_best"], ref["width07_best"]), Hc=_d(meds["Hc"], ref["Hc_m"]))
        out["S0_baseline"] = base
        out["offset_S0_minus_DA3"] = offset
        reg = registry()
        done = [e for e in reg if e.get("what") == "S0_baseline" and e.get("run_id") == cfg["run_id"]]
        s1_read = [e for e in reg if e.get("what") == "G1"]
        if out["health_S0"]["ok"] and (not done or opt.get("force_register")):
            if s1_read and not opt.get("force_register"):
                raise SystemExit("S1 was already read; the S0 baseline is not re-registered")
            out["registered"] = append_registry(dict(what="S0_baseline", run_id=cfg["run_id"], judged_k=out["judged_k"], baseline=base,
                                                     offset_S0_minus_DA3=offset, DA3_reference={k: ref[k] for k in ("back_on_deg", "back_best_deg", "width07_best", "Hc_m")},
                                                     note="registered before S1 is read (plan_B gate_G1.s0_baseline)"))
        elif done:
            out["registered"] = done[-1]
        else:
            out["registered"] = None
            out["next"] = "S0 health fails: fix the preset and rerun S0 (not a round)"
        if out["health_S0"]["ok"]:
            out["next"] = "S0 healthy: baseline registered; go straight to S1 (no gate)"
    elif qid == "S1":
        reg = registry()
        b0 = [e for e in reg if e.get("what") == "S0_baseline"]
        provisional = False
        if not b0:
            # AM-B3: S0 never passed its health (2D volume rule). G1 is then computed as PROVISIONAL / report-only against the S0 run given by
            # --s0=<run dir> (its planB_ana.json medians, same set-up), never applied, never registered as a decision
            if not opt.get("s0"):
                raise SystemExit("the S0 baseline is not registered (S0 health failed?); give --s0=<S0 run dir> for a PROVISIONAL report-only G1 (AM-B3)")
            s0a = json.load(open(os.path.join(opt["s0"], "pana", "planB_ana.json"), encoding="utf8"))
            b0 = dict(what="S0_unregistered", run_id=s0a["run_id"], baseline={k: s0a["medians_judged"].get(k) for k in ("back_on", "back_best", "w07_best", "Hc", "h_b",
                                                                                                                     "back_pre_max", "back_inc", "lip_max")},
                      offset_S0_minus_DA3=s0a.get("offset_S0_minus_DA3"), health_S0=s0a.get("health_S0"))
            provisional = True
        else:
            b0 = b0[-1]
        base = b0["baseline"]; offset = b0["offset_S0_minus_DA3"]
        reach = [r for r in jud if r["x_on"] is not None and r["x_on"] >= 180.25]
        n_lt = len(periods_lt180)
        Ga = dict(periods_breaking_x_lt_180=periods_lt180, triggered=bool(n_lt >= 2), n_reaching_slope=len(reach))
        use = reach if Ga["triggered"] else jud
        m1 = {k: med([r.get(k) for r in use]) for k in MED_KEYS}
        d_back = _d(m1["back_on"], base["back_on"]); d_hb = _d(m1["h_b"], base["h_b"])
        n_lip = sum(1 for r in use if r.get("lip_max") is not None and r["lip_max"] >= 0.2)
        Gb = dict(d_back_on_deg=d_back, d_back_on_ok=bool(d_back is not None and d_back >= 5.0),
                  d_h_b_m=d_hb, d_h_b_ok=bool(d_hb is not None and d_hb >= 1.5),
                  n_lip_ge_0p2=n_lip, lip_ok=bool(n_lip >= 2), read_on_k=[r["k"] for r in use])
        if Ga["triggered"] and len(reach) < 2:
            verdict = "STOP: fewer than 2 S1 breakers reach the slope (G1 a) -> stop and ask"
            G1 = "stop"
        elif Gb["d_back_on_ok"] and Gb["d_h_b_ok"] and Gb["lip_ok"]:
            G1 = "PASS"
            verdict = "G1 PASS -> build and run X1" + (" with H_t 5.0 m (G1 a)" if Ga["triggered"] else " with H_t 5.35 m")
        else:
            G1 = "FAIL"
            verdict = ("G1 FAIL -> do not port the inlet, do not run X1; stop and ask the user (options: S1 at 0.25 m particles, steep-ledge axis strip "
                       "1:10 17->13 m then 1:3, X1 for height only, keep DA3)")
        if provisional:
            verdict = "PROVISIONAL, report-only (AM-B3: S0 health failed, G1 not applied): numbers say '%s'" % verdict
            G1 = "provisional_" + G1
        out["medians_used_for_G1"] = m1
        out["S0_baseline_registered" if not provisional else "S0_unregistered_used"] = b0
        out["G1"] = dict(a=Ga, b=Gb, result=G1, verdict=verdict, provisional=provisional,
                         H_t_for_X1=((5.0 if Ga["triggered"] else PB.H_T) if G1 == "PASS" else None))
        out["Q73_S1_vs_S0"] = q73(dict(back_best=m1["back_best"], w07_best=m1["w07_best"], Hc=m1["Hc"]),
                                  dict(back_best=base["back_best"], w07_best=base["w07_best"], Hc=base["Hc"]), "S1 vs S0")
        out["health_S1"] = dict(volume_lt_1pct=bool(vol is not None and vol < 0.01), bed_leak_ok=bool(leak < 1e-4), inlet_H_rel=inl["H_rel"], realized_q=inl["realized_q"])
        what = "G1" if not provisional else "G1_provisional_report_only"
        prev = [e for e in reg if e.get("what") == what and e.get("run_id") == cfg["run_id"]]
        if not prev:
            e = dict(what=what, run_id=cfg["run_id"], result=G1, a=Ga, b=Gb, s0_run=b0.get("run_id"),
                     medians=dict(back_on=m1["back_on"], back_best=m1["back_best"], h_b=m1["h_b"], w07_best=m1["w07_best"], Hc=m1["Hc"]))
            if G1 == "PASS":
                e["X1_expected_back"] = dict(onset=_d(m1["back_on"], offset["back_on"]), best=_d(m1["back_best"], offset["back_best"]),
                                             rule="S1 value minus the S0-DA3 offset (plan_B gate_G1.b_pass.then)")
            out["registered"] = append_registry(e)
        else:
            out["registered"] = prev[-1]
    od = GC.guard_out49(os.path.join(rd, "pana"))
    json.dump(clean(out), open(os.path.join(od, "planB_ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(clean(dict(run_id=cfg["run_id"], rows=rows)), open(os.path.join(od, "planB_rows_full.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    txt = table(out)
    open(os.path.join(od, "planB_table.txt"), "w", encoding="utf8").write(txt)
    print(txt)
    return out


def _d(a, b):
    return (a - b) if (a is not None and b is not None) else None


def table(o):
    L = []
    L.append("%s (%s)%s  plan %s  judged k %s" % (o["run_id"], o["queue_id"], "  [STAND-IN]" if o.get("standin") else "", o["plan_sha256"][:12], o["judged_k"]))
    inl = o["inlet"]
    L.append("inlet: H(110-160) %s m (design %s, rel %s), H128 %s H160 %s, crest160 %s, realized q %s, c_rel %s, Kr %s" % (
        _f(inl["H_mean_110_160_m"]), inl["H_design_m"], _f(inl["H_rel"], "%+.3f"), _f(inl["gauges"]["128.0"]["H"]), _f(inl["gauges"]["160.0"]["H"]),
        _f(inl["crest_160_m"]), _f(inl["realized_q"], "%.3f"), _f(inl["c_rel"], "%+.3f"), _f(inl["Kr"], "%.3f")))
    L.append("health: volume %s, leak %s, still offset %s, breaking x<180 periods %s" % (
        _f(o["health"]["volume_corrected_max_rel"], "%.4f"), _f(o["health"]["bed_leak_frac"], "%.1e"), _f(o["health"]["still_offset_m"], "%.3f"),
        o["breaking_x_lt_180"]["periods"]))
    L.append(" k  judged t_on   x_on   h_b    Hc   Hfront Hrear | back inc  pre   on  best | w07 on best | lip  chord  hood | best: chord lip  hood  foot hollow s3")
    for r in o["rows"]:
        L.append("%2s  %-5s %6.2f %6.1f %5s %5s %6s %5s | %5s %5s %5s %5s | %4s %4s | %4s %6s %5s | %6s %4s %5s %5s %5s %4s" % (
            r["k"], "yes" if r["judged"] else "rep", r["t_on"], r["x_on"], _f(r["h_b"]), _f(r["Hc"]), _f(r["H_front"]), _f(r["H_rear"]),
            _f(r["back_inc"], "%.1f"), _f(r["back_pre_max"], "%.1f"), _f(r["back_on"], "%.1f"), _f(r["back_best"], "%.1f"),
            _f(r["w07_on"]), _f(r["w07_best"]), _f(r["lip_max"]), _f(r["chord_max"], "%.0f"), _f(r["hood_max"], "%.3f"),
            _f(r["best_chord"], "%.0f"), _f(r["best_lip"]), _f(r["best_hood"], "%.3f"), _f(r["best_front_foot"]), _f(r["best_hollow"]), _f(r["best_score3"])))
    m = o["medians_judged"]
    L.append("medians (judged): h_b %s Hc %s Hfront %s Hrear %s | back inc %s pre %s on %s best %s | w07 on %s best %s | lip %s chord %s" % (
        _f(m["h_b"]), _f(m["Hc"]), _f(m["H_front"]), _f(m["H_rear"]), _f(m["back_inc"], "%.1f"), _f(m["back_pre_max"], "%.1f"), _f(m["back_on"], "%.1f"),
        _f(m["back_best"], "%.1f"), _f(m["w07_on"]), _f(m["w07_best"]), _f(m["lip_max"]), _f(m["chord_max"], "%.0f")))
    if "health_S0" in o:
        L.append("S0 health: %s -> %s" % (o["health_S0"]["checks"], "ok" if o["health_S0"]["ok"] else "FAIL"))
        L.append("offset S0 - DA3: %s" % {k: (round(v, 2) if v is not None else None) for k, v in o["offset_S0_minus_DA3"].items()})
    if "G1" in o:
        g = o["G1"]
        L.append("G1 (a) %s" % g["a"])
        L.append("G1 (b) %s" % g["b"])
        L.append("G1: %s" % g["verdict"])
        L.append("Q73 S1 vs S0: %s" % o["Q73_S1_vs_S0"])
    L.append("next: %s" % o.get("next", "-"))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main(sys.argv[1:])
