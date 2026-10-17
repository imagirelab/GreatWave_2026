# -*- coding: utf-8 -*-
"""FLIP50 option D: the HERO rule (AM-D23) - which ONE run gets the long every-frame re-record (about 48-138 s, 7-8 breakers) that the
Unity FLIP3D player shows in the VR experience (boat seat -> visible move to the print view at the most print-like instant, no white-out).
2026-10-17 written new (Claude, orchestrator workflow step). Pure Python (no numpy, no Houdini). Nothing of flip46-flip50, flip50g, flip50g2,
flip50dg2, the hips, build_check*.json, the frozen plans, the ready cfgs or the amendments already written is edited.

The rule (registered as Unity/Build/FLIP50/plan/hero_rule.json + amendments.jsonl AM-D23 BEFORE any DG1 number exists):
  0  the user's override (Unity/Build/FLIP50/_logs/hero_override.json, written by the main session from the user's own words)
  1  DG1's pana/q80_DG1.json key Q80_met is the boolean true  -> hero = DG1   (the frozen 92 s verdict: the backup copy that
     flip50g2/g50g2_cont.py backup makes before a DD3 is read first)
  2  otherwise (false, missing, unreadable, DG1 incomplete)     -> hero = DM1A  (healthy, Q77 height >= 10 m, the most periodic D run)
  DF1A is not the default: H_front median 9.85 m < 10.0 m (Q77). DG2 (AM-D22 opt-in) is outside this rule.
  Asked (20 min, no answer -> the rule's hero; the user's 10/17 no-answer rule): the user answered STOP in auto_post_dg1, a DG2 run met
  Q80, or AM-D22's delivery pick (RR) names a different run than this rule.

  py -3.10 -B h50_hero.py write-rule        writes plan/hero_rule.json once (refuses to change an existing different file)
  py -3.10 -B h50_hero.py show              prints the rule
  py -3.10 -B h50_hero.py pick              applies the rule to the files as they are now (read only; prints the decision)
Tags: 【測定】 measured, 【計算】 computed, 【推測】 guess, 【選び】 chosen.
"""
import os, sys, json, re, hashlib

REPO = "G:/Unity/GreatWave_2026_Fresh"
B50 = REPO + "/Unity/Build/FLIP50"
LOGS = B50 + "/_logs"
PLAN = B50 + "/plan"
HERO_RULE = PLAN + "/hero_rule.json"
AMEND = PLAN + "/amendments.jsonl"
AM_ID = "AM-D23"
OVERRIDE = LOGS + "/hero_override.json"
POST_STATUS = LOGS + "/auto_post_dg1_status.txt"
POST = B50 + "/_scratch/post_dg1"
IDS = dict(DM1A="DM1A_D19B_T12_th80_dp0p5", DG1="DG1_D19Bgr_T12_th80_dp0p5", DF1A="DF1A_D19B_T10_th80_dp0p5")
NAME_OF = {v: k for k, v in IDS.items()}
OPTIONS = ("DM1A", "DG1", "DF1A", "NONE")        # NONE = no long re-record (only on the user's words)
T_FROM_S, T_END_S = 48.0, 138.0                    # 【選び】 the window (see RULE['long_rerecord'])
H_Q77 = 10.0                                       # the user's Q77 height floor (m)

RULE = dict(
    id="hero_rule", am=AM_ID, version=1,
    purpose="pick the ONE run whose ~48-138 s window (7-8 breakers at T 12 s) is re-recorded with the surface (R5) every frame, for the Unity "
            "FLIP3D player in the VR experience (boat seat -> visible move to the print view at the most print-like instant, no white-out; "
            "zemi 10/21, deadline 10/29). It decides only which run is re-recorded; it judges nothing and changes no frozen rule.",
    order=[
        "0 user override: Unity/Build/FLIP50/_logs/hero_override.json {\"hero\": \"DM1A\"|\"DG1\"|\"DF1A\"|\"NONE\", \"user_words\": <verbatim, "
        "non-empty>, \"by\", \"time\"} written by the main session from the user's own words -> that run (NONE = no long re-record)",
        "1 DG1 pana/q80_DG1.json key 'Q80_met' is the JSON boolean true -> hero = DG1 (read from the file, never from a status line; the "
        "copy in Unity/Build/FLIP50/_scratch/post_dg1/backup_DG1_D19Bgr_T12_th80_dp0p5_t92/pana/ (g50g2_cont backup before a DD3) is read "
        "first, so the frozen 92 s verdict decides)",
        "2 otherwise (false, null, missing, unreadable, or DG1 incomplete) -> hero = DM1A",
    ],
    why_DM1A_default=dict(
        text="DM1A is healthy, meets the user's Q77 height floor and is the most periodic D run (one breaker every ~12 s at the same place)",
        numbers="DM1A pana/planD_ana.json 【測定】: health hard [] (soft: H_wall 3.58 h > 3.0 h, reported), volume_rel 0.39 %, frames 2209/2209; "
                "medians_judged H_front 10.33 m (>= 10.0 m, Q77), back_best 13.84 deg, w07_best 2.54, curl_w_maxov_over_Hc 5.99, Hc 7.85 m, "
                "x_on 256.5 m; periodic: judged intervals 12.25 / 11.58 / 12.29 s, onset x scatter 3.0 m, Hc CV 1.9 % (PERIODIC flag false "
                "only because the curl 6.0 Hc > 2.5 Hc clause fails); verdict partial (round 1)",
    ),
    why_not_DF1A=dict(
        text="DF1A is NOT the default: its median front height H_front 9.85 m is below the user's Q77 floor 10.0 m, so it fails by height "
             "although its curl and width are narrower",
        numbers="DF1A pana/planD_ana.json 【測定】: H_front 9.85 m < 10.0 m (Q77); curl_w_maxov_over_Hc 4.15, w07_best 1.90, back_best 16.13 deg; "
                "health hard []; intervals 10.29 / 10.04 / 10.25 s, onset scatter 3.0 m, Hc CV 4.9 %; verdict fail (round 2: 'worse items "
                "[H_front]')",
    ),
    why_DG1_only_with_Q80="Q80 is the user's own target for DG1 ('let the curl become narrower while keeping the option-D profile'); a DG1 "
                          "that did not meet it is a failed round by dg1_frozen decision 2, so the delivery wave stays the healthy, periodic, "
                          ">= 10 m DM1A 【選び】",
    differs_from_AM_D22_delivery="AM-D22's delivery rule (12 s loop re-record) can pick DG1 at tier 2 (S1, S2 and H_front >= 10.0 m without Q80). "
                                 "This rule is stricter (DG1 only with Q80_met). When the two disagree, auto_hero asks (20 min) and the "
                                 "default stays this rule's hero; the 12 s loop clip of the AM-D22 pick exists either way",
    DG2="DG2 is AM-D22's opt-in round (only on the user's explicit words); it is not in this rule (no long re-record path is built for the "
        "flip50dg2 chain). If a DG2 run met Q80, auto_hero asks (20 min) with this rule's hero as the default",
    ask_cases=["the user answered STOP to an auto_post_dg1 question (POST_DG1 ANSWER ... action=STOP)",
               "a DG2 run exists whose pana/q80_DG2.json Q80_met is true",
               "the last AM-D22 delivery pick in auto_post_dg1_status.txt (DECISION ... delivery=<run>) is a different run"],
    no_answer="answer file Unity/Build/FLIP50/_logs/hero_answer.json {ask_id, action in options or HOLD, user_words}; no valid answer within "
              "20 min -> the rule's hero runs (the user's 10/17 'no prompt answer -> run the recommendation; the work must not stop'). "
              "HOLD waits with no deadline. NONE (no long re-record) needs the user's words",
    user_may_override=True,
    long_rerecord=dict(
        window="from the latest checkpoint of the hero at or before 48.0 s (frame 1153; DM1A: v.1152 = 47.958 s) to 138.0 s (frame 3313) "
               "【選び】: covers the judged breakers from k2 (DM1A onset ~49.6 s) on, 7-8 breakers at T 12 s, and the touchdown of the "
               "breaker near 134.8 s with ~2 s margin",
        physics="same physics keys byte-equal (canonical JSON) to the source cfg.json and every launch cfg_c*.json; same hip (sha), same "
                "runtime modules; only time/output keys change (run_id, f_start/f_first/f_end/t_end_s, records r4/r5 every 1 and the "
                "window, ckpt_every 48 / ckpt_list [48, 24], wall_limit_s <= 1740, max_hours, pstats_frames, case labels, note, restart, "
                "still_offset_m copied from the run's launch records)",
        beyond_source="DM1A (and DG1 without a DD3) ran 0-92 s only: frames after the source end (2209) are NEW computation of the same "
                      "settings (as DD3's '+48 s'); closed-tank drift after ~100 s is expected (DD3 note). Frames 1153-2209 must reproduce "
                      "the source bit for bit (as DA3r: R5 bytes on the source's every-3rd frames, hf/r2/r3/r4 arrays, volcorr rows); "
                      "frames after 2209 have no source to compare",
        paths=dict(D19B="flip50/g50_chain.py (unchanged) with the long cfg", DG1="flip50g2/g50g2_cont.py chain (flip50g/g50g_chain.py in memory, "
                   "groove hip Houdini/FLIP50/g50_tank_g.hiplc; the id 'DG1r_..._long' is accepted by g50g2_cont.accept_rr)"),
        tools="Tools/GWWaveGen/flip50h/h50_long.py (cfg, selfcheck, gate, compare, export); seed = flip50g2/g50g2_cont.py seed",
        automation="G:/research/Wave Simulation/_tools/auto_hero.py (waits for '^<date> <time> POST_DG1 FINISHED' after the last POST_DG1 "
                   "START line; never started by this amendment)",
    ),
    never="no threshold, criterion, gate, decision rule or the plan changes; the hero is not a judged round",
    tags="【測定】 measured, 【計算】 computed, 【推測】 guess, 【選び】 chosen",
)


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=float)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def lines(p):
    return open(p, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(p) else []


def write_rule(date):
    os.makedirs(PLAN, exist_ok=True)
    r = dict(RULE, date=date)
    raw = (json.dumps(r, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    if os.path.exists(HERO_RULE):
        old = jload(HERO_RULE) or {}
        if canon({k: v for k, v in old.items() if k != "date"}) != canon({k: v for k, v in r.items() if k != "date"}):
            raise SystemExit("%s exists with other content; a change is a new dated amendment, not an overwrite" % HERO_RULE)
        return HERO_RULE, sha256_file(HERO_RULE), "kept"
    with open(HERO_RULE, "wb") as fh:
        fh.write(raw)
    return HERO_RULE, sha256_file(HERO_RULE), "written"


# ====================================================================== the inputs as files (read only)
def q80_dg1():
    """(dict or None, path) - the frozen 92 s verdict: the g50g2_cont backup copy first, else the run's own pana."""
    for p in sorted(glob_backups()) + [B50 + "/runs/" + IDS["DG1"] + "/pana/q80_DG1.json"]:
        if os.path.exists(p):
            return jload(p), p
    return None, None


def glob_backups():
    import glob
    return glob.glob(POST + "/backup_" + IDS["DG1"] + "_t92/pana/q80_DG1.json")


def dg2_runs():
    import glob
    out = []
    for rd in sorted(glob.glob(B50 + "/runs/DG2*_D19Bgr_T12_th80_dp0p5")):
        q = jload(rd + "/pana/q80_DG2.json") or {}
        out.append(dict(run_id=os.path.basename(rd), Q80_met=q.get("Q80_met")))
    return out


POST_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) POST_DG1 (.*)$")


def post_events(ls):
    """auto_post_dg1 status lines -> dict(finished, last_start, user_stop, delivery, stops). Only lines that START with '<date> <time> POST_DG1 '
    count; a FINISHED line counts only after the last START line (a restarted auto_post_dg1 is waited for again)."""
    ev = [(m.group(1), m.group(2)) for m in (POST_LINE.match(l) for l in ls) if m]
    starts = [i for i, (_, s) in enumerate(ev) if s == "START" or s.startswith("START ")]
    i0 = starts[-1] if starts else 0
    seg = ev[i0:]
    fin = [t for t, s in seg if s == "FINISHED" or s.startswith("FINISHED ")]
    user_stop = [s for _, s in seg if s.startswith("ANSWER ") and re.search(r"\baction=STOP\b", s)]
    dec = [s for _, s in seg if s.startswith("DECISION ") or s.startswith("DECISION_DG2 ")]
    deliv = None
    for s in dec:
        m = re.search(r"\bdelivery=(\S+)", s)
        if m and m.group(1) not in ("None", "null"):
            deliv = m.group(1)
        m2 = re.search(r"\bdefault=RR:(\S+)", s)
        if m2 and deliv is None:
            deliv = m2.group(1)
    stops = [s for _, s in seg if s.startswith("STOP")]
    return dict(finished=fin[-1] if fin else None, last_start=ev[i0][0] if ev else None, user_stop=user_stop[-1] if user_stop else None,
                delivery=deliv, stops=stops[-3:], n_lines=len(seg))


# ====================================================================== the rule
def pick(q80, q80_path, override, post_ev, dg2):
    """-> dict(hero (DM1A/DG1/DF1A/NONE), run_id, rule_step, why, ask, options, default, facts). Pure function of its inputs."""
    facts = dict(q80_path=q80_path, Q80_met=(q80 or {}).get("Q80_met") if isinstance(q80, dict) else None, override=override,
                 post=post_ev, dg2=dg2)
    ov = override if isinstance(override, dict) else None
    if ov and str(ov.get("hero")) in OPTIONS and str(ov.get("user_words") or "").strip():
        h = str(ov["hero"])
        return dict(hero=h, run_id=IDS.get(h), rule_step=0, ask=False, options=list(OPTIONS), default=h, facts=facts,
                    why="rule 0: the user's override (hero_override.json): %s" % str(ov.get("user_words"))[:300])
    met = isinstance(q80, dict) and q80.get("Q80_met") is True
    h = "DG1" if met else "DM1A"
    why = ("rule 1: DG1 Q80_met true (%s)" % q80_path) if met else (
        "rule 2: DG1 Q80_met is %s (%s) -> DM1A (healthy, H_front 10.33 m >= 10.0 m Q77, judged breakers every 12.25/11.58/12.29 s; "
        "DF1A not: H_front 9.85 m < 10.0 m)" % (facts["Q80_met"], q80_path or "q80_DG1.json missing"))
    ask_why = []
    if (post_ev or {}).get("user_stop"):
        ask_why.append("the user answered STOP in auto_post_dg1 (%s)" % post_ev["user_stop"][:160])
    met2 = [d["run_id"] for d in (dg2 or []) if d.get("Q80_met") is True]
    if met2:
        ask_why.append("DG2 run(s) %s met Q80 (DG2 is outside this rule; no long path is built for it)" % met2)
    dv = (post_ev or {}).get("delivery")
    if dv and NAME_OF.get(dv, dv) != h:
        ask_why.append("AM-D22's delivery pick is %s, this rule's hero is %s" % (dv, IDS[h]))
    d = dict(hero=h, run_id=IDS[h], rule_step=1 if met else 2, ask=bool(ask_why), options=list(OPTIONS), default=h, facts=facts, why=why)
    if ask_why:
        d["why"] = why + " | asked because: " + "; ".join(ask_why)
    return d


def pick_now():
    q, qp = q80_dg1()
    return pick(q, qp, jload(OVERRIDE), post_events(lines(POST_STATUS)), dg2_runs())


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "write-rule":
        import time
        p, s, how = write_rule(time.strftime("%Y-%m-%d %H:%M:%S"))
        print(how, p, s)
    elif a[0] == "show":
        print(json.dumps(RULE, ensure_ascii=False, indent=1))
    elif a[0] == "pick":
        print(json.dumps(pick_now(), ensure_ascii=False, indent=1, default=str))
    else:
        print(__doc__); sys.exit(1)
