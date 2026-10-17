# -*- coding: utf-8 -*-
"""FLIP50 after DG1: the AM-D22 mapping rules (pure Python, no numpy, no Houdini). 2026-10-17 written new (Claude), registered in AM-D22
(amendments.jsonl; its sha256 is frozen there) BEFORE any DG1 main-run result existed. auto_post_dg1.py refuses to act if this file's
sha256 differs from AM-D22.

What it decides (and nothing else):
  classify_dg1(...)  DG1's outputs (auto_DG1_status.txt, DG1 chain.log, pana/q80_DG1.json, pana/planD_ana.json, DM1A planD_ana.json)
                     -> exactly one mode, its default next action, whether the user is asked first, and the allowed answers.
  delivery_pick(...) the frozen delivery rule among DM1A, DG1 (and DG2 if it ran) with S0 ok.
  classify_dg2(...)  DG2's outputs (pana/q80_DG2.json) -> the same kind of decision; after DG2 the shape search has ended whatever the result.
Checks run top to bottom; the first match wins. The thresholds are the frozen ones (dg1_frozen.json S1-S3, periodic_D 2.5 Hc) plus four
chosen labels (MED_COUPLED 3.5, H_Q77 10.0, H_NEAR 10.08, S3_MARGIN_D4 2.5 %) that only name the failure mode and DG2 eligibility.

Actions (an answer file may only name one of the decision's options):
An action is one step or several steps joined by '+', run left to right:
  DG1_RESUME       re-run the unchanged DG1 chain (resumes from its last checkpoint; only after a max_hours stop; not a round)
  ANA_RERUN        re-run g50g_ana all + q80 on DG1 (analysis fault; CPU only)
  DD3:<run_id>     DD3 of that run (+48 s, same physics, same run id; flip50g2/g50g2_cont.py dd3), then its report analysis + video
  RR:<run_id>      the delivery path for that run: every-frame re-record of its chosen 12 s window (flip50g2), exports for the player
  DG2 / DG2:<v>    opt-in only (never a default): the variant the model-validity gate picks / the variant the user names
  STOP             nothing more runs; wait for the user
e.g. 'DD3:DG1_...+RR:DG1_...' (frozen decision 1, PASS) or 'RR:DG1_...+DD3:DG1_...'.
"""
import os, json, statistics

DM1A_ID = "DM1A_D19B_T12_th80_dp0p5"
DG1_ID = "DG1_D19Bgr_T12_th80_dp0p5"
CURL_MAX = 2.5            # periodic_D curl clause (frozen)
FLOOR_S3 = 10.283         # dg1_frozen S3 (DA3 10.783 - 0.5), frozen
MED_COUPLED = 3.5         # 【選び】 DG1 median curl/Hc above which the row tables match lateral coupling sigma >= ~6 m (post_dg1 rm_g2e)
H_Q77 = 10.0              # Q77 / targets_D crest-to-front-trough height (frozen target)
H_NEAR = 10.08            # 【選び】 S3 gap <= 2 % (label only: F3-near)
S3_MARGIN_D4 = 0.025      # 【選び】 L12D4 (H -2.3 %) only if DG1's S3 margin >= 2.5 %
DG2_ELIGIBLE = ("F1a-CURL", "F13-CURL+HEIGHT", "F1c-PERIODIC-OTHER", "F2-SECTION")
MAX_ANA_RERUN = 1
MAX_DG1_RESUME = 1        # one more resume cycle after auto_DG1's two (each cycle = up to 3 chain launches of max_hours 3.0)


# ====================================================================== inputs
def status_state(lines):
    """auto_DG1_status.txt -> dict(ana_done, finished, stop, video_done)."""
    st = dict(ana_done=False, finished=False, stop=None, video_done=False, smoke_ok=None)
    for l in lines:
        if " DG1 ANA_DONE" in l:
            st["ana_done"] = True
        if " DG1 FINISHED" in l:
            st["finished"] = True
        if " DG1 VIDEO_DONE" in l:
            st["video_done"] = True
        if " DG1 STOP at " in l:
            st["stop"] = l.split(" DG1 STOP at ", 1)[1].strip()
    return st


def chain_segment(lines):
    """DG1 chain.log -> dict(state complete / incomplete / running / absent, max_hours_stop, last): the last chain start..end segment."""
    if not lines:
        return dict(state="absent", max_hours_stop=False, last="")
    ends = [i for i, l in enumerate(lines) if " chain end " in l]
    starts = [i for i, l in enumerate(lines) if " chain start " in l]
    gates = [i for i, l in enumerate(lines) if "gate failed" in l]
    if gates and gates[-1] > max(ends + starts + [-1]):
        return dict(state="gate_failed", max_hours_stop=False, last=lines[-1])
    if not ends or (starts and starts[-1] > ends[-1]):
        return dict(state="running", max_hours_stop=False, last=lines[-1])
    seg = lines[(starts[-1] if starts else 0):]
    done = any("stopped None" in l for l in seg)
    mh = any("max_hours exceeded" in l for l in seg)        # g50_chain breaks right after this line, so no other stop shares the segment
    return dict(state="complete" if done else "incomplete", max_hours_stop=bool(mh and not done), last=lines[-1])


def judged_rows(ana):
    ks = set((ana or {}).get("judged_k") or [])
    return [r for r in (ana or {}).get("rows") or [] if r.get("k") in ks]


def curl_clause(rows):
    """>= 3 consecutive judged breakers with curl_w_maxov_over_Hc <= 2.5 (the curl part of PERIODIC)."""
    best = cur = 0
    for r in rows:
        v = r.get("curl_w_maxov_over_Hc")
        cur = cur + 1 if (v is not None and v <= CURL_MAX) else 0
        best = max(best, cur)
    return best >= 3, best


def median_curl(rows):
    c = [r["curl_w_maxov_over_Hc"] for r in rows if r.get("curl_w_maxov_over_Hc") is not None]
    return statistics.median(c) if c else None


def hard_kind(item):
    """one hard health string of g50_ana.health_D -> 'incomplete' / 'analysis' / 'impl_or_ask' / 'leak_ask' / 'phys' / 'unknown'."""
    s = str(item)
    if s.startswith("run incomplete"):
        return "incomplete"
    if s.startswith("volume not read"):
        return "analysis"
    if s.startswith("onset on the flat") or s.startswith("generation at x 160"):
        return "impl_or_ask"            # not groove-caused (the bed change starts at x 238 m): implementation / chain fault or ask
    if s.startswith("bed leak"):
        return "leak_ask"               # the diagnosis decides implementation vs groove physics
    if s.startswith("swash set-up") or "whole-tank volume" in s or "window volume" in s:
        return "phys"
    return "unknown"


def analysis_faults(q80, ana, prev_id=DM1A_ID):
    """analysis faults checked BEFORE S1/S3 (they must not be read as a shape result)."""
    f = []
    s2 = (q80 or {}).get("S2") or {}
    if s2.get("previous_round") != prev_id:
        f.append("S2.previous_round %r is not %s" % (s2.get("previous_round"), prev_id))
    wi = s2.get("worse_items")
    if not wi:
        f.append("S2.worse_items empty")
    elif wi.get("missing"):
        f.append("S2.worse_items.missing true")
    rows = judged_rows(ana)
    if not rows:
        f.append("no judged rows in planD_ana.json")
    if any(r.get("curl_w_maxov_over_Hc") is None for r in rows):
        f.append("a judged breaker has curl_w_maxov_over_Hc None")
    hf = ((ana or {}).get("medians_judged") or {}).get("H_front")
    if hf is None:
        f.append("medians_judged.H_front None")
    return f


def run_facts(run_id, q80, ana):
    """the numbers the delivery rule reads for one run (DM1A: no q80; S1 from its planD_ana)."""
    med = (ana or {}).get("medians_judged") or {}
    rows = judged_rows(ana)
    if q80 is None:
        hard = ((ana or {}).get("health") or {}).get("hard")
        return dict(run_id=run_id, S0=bool(ana is not None and not hard), Q80_met=False, S1=bool(((ana or {}).get("periodic") or {}).get("PERIODIC") is True),
                    S2=None, H_front=med.get("H_front"), median_curl=median_curl(rows), back_best=med.get("back_best"), w07_best=med.get("w07_best"))
    return dict(run_id=run_id, S0=bool((q80.get("S0") or {}).get("ok")), Q80_met=bool(q80.get("Q80_met")), S1=bool((q80.get("S1") or {}).get("ok")),
                S2=bool((q80.get("S2") or {}).get("ok")), S3=bool((q80.get("S3") or {}).get("ok")), H_front=med.get("H_front"),
                median_curl=median_curl(rows), back_best=med.get("back_best"), w07_best=med.get("w07_best"),
                verdict=((q80.get("S4") or {}).get("verdict")))


# ====================================================================== the delivery rule (frozen)
def delivery_pick(cands):
    """cands: run_facts dicts (DM1A first). Among runs with S0 ok:
      tier 1  Q80 met (two: the smaller median curl/Hc)
      tier 2  S1 true, S2 true and H_front >= 10.0 m (the Q77 target; the height floor drops from S3 10.283 to 10.0, and the run 'did
              not meet Q80'): the smallest median curl/Hc, ties the higher back_best
      tier 3  DM1A (healthy, periodic every ~12 s at x 253-260, best measured D section; curl 6.0 Hc)
    The user judges print-likeness from the compare mp4s of the top two; default = the pick. Returns dict(pick, tier, top2, ranking, why)."""
    ok = [c for c in cands if c.get("S0")]
    big = 1e9

    def key(c):
        mc = c.get("median_curl")
        return (mc if mc is not None else big, -(c.get("back_best") or -big))
    t1 = sorted([c for c in ok if c.get("Q80_met")], key=key)
    t2 = sorted([c for c in ok if not c.get("Q80_met") and c.get("S1") and c.get("S2") and c.get("H_front") is not None
                 and c["H_front"] >= H_Q77], key=key)
    rank = [(1, c) for c in t1] + [(2, c) for c in t2]
    seen = set(c["run_id"] for _, c in rank)
    dm = [c for c in ok if c["run_id"] == DM1A_ID]
    if dm and DM1A_ID not in seen:
        rank.append((3, dm[0]))
    rest = sorted([c for c in ok if c["run_id"] not in seen and c["run_id"] != DM1A_ID], key=key)
    rank += [(4, c) for c in rest]
    if not rank:
        return dict(pick=None, tier=None, top2=[], ranking=[], why="no run with S0 ok")
    tier, best = rank[0]
    why = {1: "Q80 met", 2: "S1 + S2 + H_front >= 10.0 m (Q77): did NOT meet Q80 (S3 floor 10.283 lowered to the Q77 10.0)",
           3: "default: DM1A (no DG run met tier 1 or 2)", 4: "S0 ok only"}[tier]
    return dict(pick=best["run_id"], tier=tier, top2=[c["run_id"] for _, c in rank[:2]],
                ranking=[dict(tier=t, run_id=c["run_id"], median_curl=c.get("median_curl"), H_front=c.get("H_front"), back_best=c.get("back_best"))
                         for t, c in rank], why=why)


# ====================================================================== DG1 -> one mode
def _dec(mode, why, default, options, ask, facts, **kw):
    d = dict(mode=mode, why=why, default=default, options=list(dict.fromkeys([default] + list(options))), ask=bool(ask), facts=facts)
    d.update(kw)
    return d


def classify_dg1(status_lines, chain_lines, q80, ana, ana_dm1a, n_ana_rerun=0, n_resume=0):
    """AM-D22 mapping. Returns a decision dict (mode, default, options, ask, dg2_eligible, delivery, facts, why)."""
    st = status_state(status_lines)
    ch = chain_segment(chain_lines)
    facts = dict(status=st, chain=dict(ch, last=ch["last"][:200]))
    dm = run_facts(DM1A_ID, None, ana_dm1a)
    if not st["ana_done"] and not st["finished"]:
        return _dec("WAIT", "DG1 not analysed and not finished", "WAIT", [], False, facts)
    # (0) the pipeline stopped before the analysis (no q80 can exist)
    if not st["ana_done"]:
        dl = delivery_pick([dm])
        if ch["state"] == "incomplete" and ch["max_hours_stop"] and n_resume < MAX_DG1_RESUME:
            return _dec("F0-STOP-MAXH", "DG1 stopped at %s after auto_DG1's resumes; the last chain segment ended on max_hours (a budget stop, "
                        "not physics): resume the unchanged chain (not a round)" % st["stop"], "DG1_RESUME", ["RR:" + DM1A_ID, "STOP"], True,
                        facts, dg2_eligible=False, delivery=dl)
        return _dec("F0-STOP", "DG1 stopped at %s (chain %s): read-only diagnosis; no automatic rerun (dg1_frozen health.on_hard); the shape "
                    "search ends; delivery default DM1A" % (st["stop"], ch["state"]), "RR:" + dl["pick"], ["STOP"], True, facts,
                    dg2_eligible=False, delivery=dl)
    # (1) analysis files
    if q80 is None or ana is None:
        if n_ana_rerun < MAX_ANA_RERUN:
            return _dec("F0-ANA", "q80_DG1.json or planD_ana.json missing/unreadable: re-run g50g_ana all + q80 (CPU only)", "ANA_RERUN", [], False,
                        facts, dg2_eligible=False)
        dl = delivery_pick([dm])
        return _dec("F0-ANA2", "analysis files still missing after a re-run: diagnose, ask; delivery default DM1A", "RR:" + dl["pick"], ["STOP"],
                    True, facts, dg2_eligible=False, delivery=dl)
    dg = run_facts(DG1_ID, q80, ana)
    rows = judged_rows(ana)
    cc, best_run = curl_clause(rows)
    mc = median_curl(rows)
    H = ((ana.get("medians_judged") or {}).get("H_front"))
    facts.update(Q80_met=q80.get("Q80_met"), S={k: (q80.get(k) or {}).get("ok") for k in ("S0", "S1", "S2", "S3", "S4")},
                 verdict=dg.get("verdict"), curl_clause=cc, curl_best_run=best_run, median_curl=mc, H_front=H,
                 curls=[r.get("curl_w_maxov_over_Hc") for r in rows], back_best=dg.get("back_best"), w07_best=dg.get("w07_best"),
                 decision_q80=q80.get("decision"))
    dl = delivery_pick([dm, dg])
    other = [r for r in dl["top2"] if r != dl["pick"]]
    # (2) Q80 met
    dd3_rr = "DD3:%s+RR:%s" % (DG1_ID, DG1_ID)
    rr_dd3 = "RR:%s+DD3:%s" % (DG1_ID, DG1_ID)
    if q80.get("Q80_met") is True:
        if dg.get("verdict") == "pass":
            return _dec("MET-PASS", "Q80 met and verdict_D PASS: frozen decision 1 -> DD3 (+48 s, same physics), then the every-frame re-record "
                        "of DG1's 12 s window; show the user", dd3_rr, [rr_dd3, "STOP"], False, facts, dg2_eligible=False, delivery=dl)
        return _dec("MET-PARTIAL", "Q80 met with verdict_D %s: frozen decision 1 'stop and show the user'; asked, no answer -> the re-record of "
                    "DG1 (24/s player clip) first, then DD3" % dg.get("verdict"), rr_dd3, [dd3_rr, "RR:" + DG1_ID, "STOP"], True,
                    facts, dg2_eligible=False, delivery=dl)
    # (3) S0 false: hard health or DG1 validity
    s0 = q80.get("S0") or {}
    if not s0.get("ok"):
        hard = s0.get("hard") or []
        kinds = sorted(set(hard_kind(h) for h in hard))
        facts["hard_kinds"] = kinds
        dl0 = delivery_pick([dm])
        if "analysis" in kinds and n_ana_rerun < MAX_ANA_RERUN and len(kinds) == 1:
            return _dec("F0-ANA", "hard item 'volume not read' = an analysis fault: re-run g50g_ana all + q80", "ANA_RERUN", [], False, facts,
                        dg2_eligible=False)
        if kinds == ["incomplete"] and ch["max_hours_stop"] and n_resume < MAX_DG1_RESUME:
            return _dec("F0-STOP-MAXH", "hard item 'run incomplete' after a max_hours stop: resume the unchanged chain (not a round)", "DG1_RESUME",
                        ["RR:" + dl0["pick"], "STOP"], True, facts, dg2_eligible=False, delivery=dl0)
        if hard and all(k == "phys" for k in kinds):
            mode, why = "F0-PHYS", "hard health item from the groove physics (%s): not judged; the shape search ends; delivery default DM1A" % hard
        elif not hard:
            mode, why = "F0-IMPL", "DG1 validity failed (%s): not judged; read-only diagnosis; no automatic rerun; delivery default DM1A" % (
                [k for k in ("hip_ok", "ctrl_gr_ok", "frozen_sha_ok") if not (s0.get("dg1_validity") or {}).get(k)])
        else:
            mode, why = "F0-ASK", ("hard health %s (kinds %s): not judged; read-only diagnosis decides implementation vs physics; no automatic "
                                   "rerun (dg1_frozen health.on_hard); delivery default DM1A" % (hard, kinds))
        return _dec(mode, why, "RR:" + dl0["pick"], ["STOP"], True, facts, dg2_eligible=False, delivery=dl0)
    # (4) analysis faults before S1/S3
    af = analysis_faults(q80, ana)
    if af:
        facts["analysis_faults"] = af
        if n_ana_rerun < MAX_ANA_RERUN:
            return _dec("F0-ANA", "analysis fault(s) %s: re-run g50g_ana all + q80 (CPU only), then classify again" % af, "ANA_RERUN", [], False,
                        facts, dg2_eligible=False)
        dl0 = delivery_pick([dm])
        return _dec("F0-ANA2", "analysis fault(s) %s remain after a re-run: diagnose, ask; delivery default DM1A" % af, "RR:" + dl0["pick"], ["STOP"],
                    True, facts, dg2_eligible=False, delivery=dl0)
    # (5) Q80 not met: dg1_frozen decision 2 'STOP, no further D round' -> delivery; DG2 only as an opt-in with honest odds
    S = facts["S"]
    if not S["S1"]:
        if cc:
            mode = "F1c-PERIODIC-OTHER"
        elif mc is not None and mc > MED_COUPLED:
            mode = "F1b-COUPLED"
        elif S["S3"]:
            mode = "F1a-CURL"
        elif H is not None and H >= H_Q77:
            mode = "F13-CURL+HEIGHT"
        else:
            mode = "F13x"
    elif not S["S3"]:
        mode = "F3-HEIGHT-NEAR" if (H is not None and H >= H_NEAR) else "F3-HEIGHT-FAR"
    elif not S["S2"]:
        mode = "F2-SECTION"
    else:
        mode = "F-OTHER"                       # S1-S3 true and S4 false: unreachable by the frozen rules (reported, asked)
    elig = bool(mode in DG2_ELIGIBLE and H is not None and H >= H_Q77)
    opts = ["RR:" + o for o in other] + (["DG2"] + ["DG2:" + v for v in ("L12", "H", "L12D4")] if elig else []) + ["STOP"]
    return _dec(mode, "Q80 not met (failed %s): dg1_frozen decision 2 -> STOP the shape search; delivery by the frozen rule (pick %s, tier %s: %s)%s"
                % ([k for k in ("S1", "S2", "S3", "S4") if not S[k]], dl["pick"], dl["tier"], dl["why"],
                   "; DG2 offered as an opt-in only (P(DG2 meets Q80 | it runs) about 0.05-0.1 【推測】)" if elig else "; no DG2 for this mode"),
                "RR:" + dl["pick"], opts, True, facts, dg2_eligible=elig, delivery=dl)


# ====================================================================== DG2 -> one decision (the shape search has ended either way)
def classify_dg2(v, q80_dg2, ana_dg2, ana_dg1, q80_dg1, ana_dm1a):
    dm = run_facts(DM1A_ID, None, ana_dm1a)
    d1 = run_facts(DG1_ID, q80_dg1, ana_dg1) if q80_dg1 else None
    rid = "DG2%s_D19Bgr_T12_th80_dp0p5" % v
    facts = dict(variant=v)
    if q80_dg2 is None or ana_dg2 is None:
        dl = delivery_pick([c for c in (dm, d1) if c])
        return _dec("G0-ANA", "q80_DG2.json / planD_ana.json missing: diagnose, ask; delivery by the rule without DG2", "RR:" + dl["pick"], ["STOP"],
                    True, facts, delivery=dl)
    d2 = run_facts(rid, q80_dg2, ana_dg2)
    dl = delivery_pick([c for c in (dm, d1, d2) if c])
    facts.update(Q80_met=q80_dg2.get("Q80_met"), S={k: (q80_dg2.get(k) or {}).get("ok") for k in ("S0", "S1", "S2", "S3", "S4")},
                 verdict=d2.get("verdict"), median_curl=d2.get("median_curl"), H_front=d2.get("H_front"))
    if not d2["S0"]:
        return _dec("G0-HEALTH", "DG2 S0 false: not judged; read-only diagnosis; no automatic rerun; the shape search has ended (AM-D22)",
                    "RR:" + dl["pick"], ["STOP"], True, facts, delivery=dl)
    if d2["Q80_met"]:
        if d2.get("verdict") == "pass":
            return _dec("G-MET-PASS", "DG2 meets Q80 with verdict PASS: DD3 of DG2 then its every-frame re-record", "DD3:%s+RR:%s" % (rid, rid),
                        ["RR:" + rid, "STOP"], False, facts, delivery=dl)
        return _dec("G-MET-PARTIAL", "DG2 meets Q80 (verdict %s): show the user; no answer -> its every-frame re-record" % d2.get("verdict"),
                    "RR:" + rid, ["DD3:%s+RR:%s" % (rid, rid), "STOP"], True, facts, delivery=dl)
    return _dec("G-STOP", "DG2 does not meet Q80: two groove rounds without meeting Q80 = the Q73 stop; the shape search ends; delivery by "
                "the frozen rule (pick %s, tier %s: %s)" % (dl["pick"], dl["tier"], dl["why"]), "RR:" + dl["pick"],
                ["RR:" + o for o in dl["top2"] if o != dl["pick"]] + ["STOP"], True, facts, delivery=dl)
