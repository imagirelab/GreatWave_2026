# -*- coding: utf-8 -*-
"""FLIP55 option C2 run as a NAMED DEVIATION (user decision Q89, 2026-10-19): the dp 0.25 m nest, group 1, although the 0.5 m identity nest
C2ID failed GN1 on the crest height only. 2026-10-19 written new (Claude). NOTHING frozen is edited: f55_nest.py (sha 9769062c...) and
x55_nest_build.py (sha 4385a162...) are checked by sha256 and used unchanged; f55_nest.py is imported by path and ONE function is replaced in
the memory of this process only: c2_tied_to_c2id (the rule 'C2 runs only against a C2ID that passed GN1-GN3') by dev_tie below. Everything
else ('run C2' with its still-water calibration first, the chain, the watchdog, the resumes, 'analyse C2') is f55_nest.py's own code.

The user's words (Q89, verbatim; recorded in Docs/Workflow/Production_Workflow_ja.md):
  先跑 0.25 m 局部加密的第 1 组，写明核对里浪顶高 +5.9% 超出 ±2% 的容差，算作规则外的试算。

dev_tie is ok ONLY if ALL of these hold (otherwise C2 is refused exactly as before):
  1. every condition of the original c2_tied_to_c2id except 'GN1-GN3 on C2ID have not passed' holds (gates_GN.json written by this f55_nest.py
     and this x55; the C2ID launch cfg's nest scene / build check / x55 / f55_nest sha = the current ones; AM-F55-NEST code_sha256 = the
     current tools);
  2. gates_GN.json: GN2 ok, GN3 ok, GN1 NOT ok and the ONLY failed GN1 item is 'Hc' (x_pk, t_conv, t_lip1, hood_max, air_max all present and
     inside the frozen tolerances, re-checked here from the values), |Hc_rel| <= 0.06 (the measured +0.0587 [measured], no wider), Hc_rel =
     Hc_nest / Hc_parent - 1 of the file's own conv values, tolerances = f55_nest.GN_TOL; its nest scene / build check / C2ID launch cfg sha =
     the current files; C2ID complete;
  3. the amendment AM-F55-C2-GN1DEV (the LAST record of that id in plan/amendments.jsonl, status REGISTERED) carries the user's verbatim
     words, the gates_GN.json sha256, THIS file's sha256, the exact GN values, the bound 0.06 and the nest tools' sha256 (all = the current).
Every line this tool prints carries the label below (json lines: key "deviation"; text lines: the label as a prefix):
  DEVIATION Q89: C2ID GN1 crest +5.9% outside +-2%; out-of-rule trial
usage (py -3.10 -B):
  f55_c2dev.py check                      dev_tie and the facts (reads only)
  f55_c2dev.py register [--dry]           verify the facts, then append AM-F55-C2-GN1DEV to plan/amendments.jsonl (--dry: print the record only);
                                          a record with the same gates / wrapper sha256 already registered -> nothing appended
  f55_c2dev.py run C2 [--simulate] [--wait-min=20]   f55_nest.py 'run C2' (calibration first when missing / stale, then the chain) with dev_tie
  f55_c2dev.py analyse C2 [--simulate]    f55_nest.py 'analyse C2'; then the deviation label is added to <C2>/f55/analyse_C2.json
  f55_c2dev.py status                     dev_tie, amendment, calibration, C2 run state (reads only)
Writes only: plan/amendments.jsonl (register), <C2 run>/f55/DEVIATION_Q89.json, the label keys in <C2 run>/f55/analyse_C2.json, one header
line in _logs/f55_nest_run_C2.log (all under Unity/Build/FLIP55); f55_nest.py writes what it always writes.
Tags: [measured] records, [computed] derived, [chosen] design choices.
"""
import os, sys, json, time, hashlib, importlib.util, io

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
SELF = HERE + "/f55_c2dev.py"
SELF_REL = "Tools/GWWaveGen/flip55/f55_c2dev.py"
NEST_PATH = HERE + "/f55_nest.py"
NEST_TOOLS_SHA = {"Tools/GWWaveGen/flip55/f55_nest.py": "9769062cb90ef56a46b222f23ed5f831d1c13ef6c1fe30b99811714f7ed1ac21",
                  "Tools/GWWaveGen/flip55/x55_nest_build.py": "4385a162ee44b935f5531694d451a9153fee2eb6908d4fc1cbadb430963f01af"}
LABEL = "DEVIATION Q89: C2ID GN1 crest +5.9% outside +-2%; out-of-rule trial"
LABEL_JA = "同一性の試しで頂の高さ +5.9 %（容差 ±2 %）、規則の外の試算"
USER_WORDS = "先跑 0.25 m 局部加密的第 1 组，写明核对里浪顶高 +5.9% 超出 ±2% 的容差，算作规则外的试算。"
Q89_DOC_REL = "Docs/Workflow/Production_Workflow_ja.md"
AMEND_DEV_ID = "AM-F55-C2-GN1DEV"
HC_REL_MAX = 0.06                    # |Hc_rel| bound of this deviation = the measured +0.0587 rounded up to 0.06 [chosen]; no wider
GN1_KEYS = ("Hc", "x_pk", "t_conv", "t_lip1", "hood_max", "air_max")
VAL_KEYS = ("Hc_rel", "x_m", "t_conv_s", "t_lip1_s", "hood_max_rel", "air_max_rel")
ORIG_GN_WHY = "GN1-GN3 on C2ID have not passed"


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ====================================================================== every printed line carries the label
class Labelled(io.TextIOBase):
    """stdout filter: json object lines get "deviation": LABEL as their first key, every other line gets LABEL as a prefix."""

    def __init__(self, raw):
        super().__init__()
        self.raw, self.buf = raw, ""

    def writable(self):
        return True

    def reconfigure(self, **kw):
        try:
            self.raw.reconfigure(**kw)
        except Exception:
            pass

    @property
    def encoding(self):
        return getattr(self.raw, "encoding", "utf-8")

    def _line(self, ln):
        s = ln.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    d = dict([("deviation", LABEL)] + [(k, v) for k, v in d.items() if k != "deviation"])
                    return json.dumps(d, ensure_ascii=False, default=str)
            except ValueError:
                pass
        return LABEL + " | " + ln if s else ln

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            ln, self.buf = self.buf.split("\n", 1)
            self.raw.write(self._line(ln) + "\n")
        return len(s)

    def flush(self):
        try:
            self.raw.flush()
        except Exception:
            pass

    def close_out(self):
        if self.buf:
            self.raw.write(self._line(self.buf) + "\n")
            self.buf = ""
        self.flush()


# ====================================================================== f55_nest.py by path (sha first)
N = None
ORIG_TIE = None


def load_nest():
    global N, ORIG_TIE
    if N is not None:
        return N
    bad = {p: sha(REPO + "/" + p) for p, v in NEST_TOOLS_SHA.items() if sha(REPO + "/" + p) != v}
    if bad:
        raise SystemExit("nest tools differ from the registered sha256 (not run): %s" % json.dumps(bad))
    spec = importlib.util.spec_from_file_location("f55_nest", NEST_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f55_nest"] = mod
    spec.loader.exec_module(mod)
    N = mod
    ORIG_TIE = mod.c2_tied_to_c2id
    mod.c2_tied_to_c2id = dev_tie            # the ONE in-memory replacement (cmd_run looks the name up in its module at call time)
    return N


def paths():
    C = N.C_()
    rd0 = N.RUNS_ROOT + "/" + C.RID["C2ID"]
    rd = N.RUNS_ROOT + "/" + C.RID["C2"]
    return C, rd0, rd, rd0 + "/f55/gates_GN.json"


def fin(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


# ====================================================================== the facts of gates_GN.json
def gate_facts(g, C=None):
    """the checks of rule 2 (see the docstring) on a gates_GN.json dict -> (checks dict, values dict)."""
    C = C or N.C_()
    _, rd0, _, gp = paths()
    T = N.GN_TOL
    ck, val = {}, {}
    g1, g2, g3 = (g or {}).get("GN1") or {}, (g or {}).get("GN2") or {}, (g or {}).get("GN3") or {}
    v = g1.get("values") or {}
    ck["gates_file_exists"] = bool(g)
    ck["gates_ok_false"] = bool(g) and g.get("ok") is False
    ck["GN2_ok"] = bool(g2.get("ok") is True and fin(g2.get("rms_m")) and fin(g2.get("tol_m")) and g2["rms_m"] <= g2["tol_m"])
    w3 = (g3.get("worst") or {}).get("rel")
    ck["GN3_ok"] = bool(g3.get("ok") is True and fin(w3) and abs(w3) <= T["gn3_rel"] + 1e-12)
    ck["GN1_not_ok"] = g1.get("ok") is False
    chk = g1.get("checks") or {}
    ck["GN1_items_complete"] = bool(set(chk) == set(GN1_KEYS) and all(k in v and fin(v[k]) for k in VAL_KEYS))
    ck["GN1_only_Hc_failed"] = bool(ck["GN1_items_complete"] and chk.get("Hc") is False and all(chk.get(k) is True for k in GN1_KEYS if k != "Hc"))
    if ck["GN1_items_complete"]:
        ck["recheck_x_pk"] = abs(v["x_m"]) <= T["x_m"] + 1e-9
        ck["recheck_t_conv"] = abs(v["t_conv_s"]) <= T["t_s"] + 1e-9
        ck["recheck_t_lip1"] = abs(v["t_lip1_s"]) <= T["t_s"] + 1e-9
        ck["recheck_hood_max"] = abs(v["hood_max_rel"]) <= T["hollow_rel"] + 1e-12
        ck["recheck_air_max"] = abs(v["air_max_rel"]) <= T["hollow_rel"] + 1e-12
        ck["Hc_outside_tol"] = abs(v["Hc_rel"]) > T["Hc_rel"] + 1e-12
        ck["Hc_within_dev_bound"] = abs(v["Hc_rel"]) <= HC_REL_MAX + 1e-12
        pc, nc = ((g1.get("parent") or {}).get("conv") or {}), ((g1.get("nest") or {}).get("conv") or {})
        ck["Hc_rel_from_conv"] = bool(fin(pc.get("Hc")) and fin(nc.get("Hc")) and pc["Hc"] != 0
                                      and abs(nc["Hc"] / pc["Hc"] - 1.0 - v["Hc_rel"]) < 1e-12)
        ck["label_number_matches"] = ("%+.1f%%" % (100.0 * v["Hc_rel"])) == "+5.9%"
        val = {k: v[k] for k in VAL_KEYS}
        val.update(Hc_parent_m=pc.get("Hc"), Hc_nest_m=nc.get("Hc"), x_parent_m=pc.get("x"), x_nest_m=nc.get("x"), t_conv_parent_s=pc.get("t"),
                   t_conv_nest_s=nc.get("t"), lip1_parent_s=(g1.get("parent") or {}).get("lip1_t"), lip1_nest_s=(g1.get("nest") or {}).get("lip1_t"))
    ck["GN_tol_as_frozen"] = (g1.get("tol") or {}) == T
    ck["gates_by_this_f55_nest"] = bool(g) and g.get("tool_sha256") == sha(N.SELF)
    ck["gates_by_this_x55"] = bool(g) and g.get("x55_sha256") == sha(N.BUILD_TOOL)
    ck["gates_nest_hip_current"] = bool(g) and g.get("nest_hip_sha256") == sha(N.NEST_HIP)
    ck["gates_build_check_current"] = bool(g) and g.get("build_check_sha256") == sha(N.NEST_BUILD_CHECK)
    ck["gates_launch_cfg_current"] = bool(g) and g.get("launch_cfg_sha256") == sha(N.launch_path("C2ID"))
    ck["C2ID_complete"] = bool(N.run_state(rd0, N.F_END)["complete"])
    val.update(GN2_rms_m=g2.get("rms_m"), GN2_tol_m=g2.get("tol_m"), GN2_frames=g2.get("frames"), GN3_worst_rel=w3,
               GN3_worst_frame=(g3.get("worst") or {}).get("frame"), gates_date=(g or {}).get("date"))
    return ck, val


def amendments_dev():
    return [a for a in N.C_().amendments() if a.get("id") == AMEND_DEV_ID]


def amend_checks(g, am):
    _, _, _, gp = paths()
    ck = {}
    ck["amendment_exists"] = bool(am)
    a = am[-1] if am else {}
    f = a.get("facts") or {}
    gv = ((g or {}).get("GN1") or {}).get("values") or {}
    ck["amendment_registered"] = a.get("status") == "REGISTERED"
    ck["amendment_label"] = a.get("label") == LABEL
    ck["amendment_user_words_verbatim"] = (a.get("user_decision") or {}).get("words_verbatim") == USER_WORDS
    ck["amendment_gates_sha256"] = bool(f.get("gates_sha256")) and f.get("gates_sha256") == sha(gp)
    ck["amendment_wrapper_sha256"] = bool((a.get("wrapper") or {}).get("sha256")) and (a.get("wrapper") or {}).get("sha256") == sha(SELF)
    ck["amendment_GN1_values_exact"] = bool(gv) and (f.get("GN1") or {}).get("values") == gv
    ck["amendment_GN2_GN3_exact"] = bool(g and (f.get("GN2") or {}).get("rms_m") == (g.get("GN2") or {}).get("rms_m")
                                         and (f.get("GN3") or {}).get("worst_rel") == ((g.get("GN3") or {}).get("worst") or {}).get("rel"))
    ck["amendment_bound"] = (a.get("bound") or {}).get("Hc_rel_abs_max") == HC_REL_MAX
    cs = a.get("code_sha256") or {}
    ck["amendment_nest_tools_sha"] = bool(all(cs.get(p) == v == sha(REPO + "/" + p) for p, v in NEST_TOOLS_SHA.items()))
    return ck, dict(date=a.get("date"), id=a.get("id"), n_records=len(am))


def dev_tie(C=None):
    """the deviation-aware replacement of f55_nest.c2_tied_to_c2id (rules 1-3 of the docstring)."""
    C = C or N.C_()
    _, rd0, _, gp = paths()
    base = ORIG_TIE(C)
    why = []
    other = [w for w in (base.get("why") or []) if not w.startswith(ORIG_GN_WHY)]
    why += ["original condition: %s" % w for w in other]
    g = N.jtry(gp) or {}
    fck, fval = gate_facts(g, C)
    why += ["gates fact: %s" % k for k, v in fck.items() if not v]
    ack, ainfo = amend_checks(g, amendments_dev())
    why += ["amendment: %s" % k for k, v in ack.items() if not v]
    return dict(ok=not why, why=why, deviation=LABEL, deviation_ja=LABEL_JA, amendment=AMEND_DEV_ID, amendment_info=ainfo,
                original_tie=base, gates=N.rel(gp), gates_sha256=sha(gp), facts=fck, values=fval, amendment_checks=ack,
                wrapper=SELF_REL, wrapper_sha256=sha(SELF), bound_Hc_rel_abs_max=HC_REL_MAX,
                tags=dict(values="measured (gates_GN.json, f55_nest.py gates C2ID)", bound="chosen (= the measured +0.0587 rounded up)"))


# ====================================================================== the amendment AM-F55-C2-GN1DEV
def register_facts():
    """everything register needs true before it appends."""
    C, rd0, rd, gp = paths()
    ck = {}
    base = ORIG_TIE(C)
    ck["original_tie_fails_only_on_GN"] = bool(base.get("why")) and all(w.startswith(ORIG_GN_WHY) for w in base["why"])
    g = N.jtry(gp) or {}
    fck, fval = gate_facts(g, C)
    ck.update({"gates." + k: v for k, v in fck.items()})
    doc = REPO + "/" + Q89_DOC_REL
    txt = open(doc, encoding="utf-8").read() if os.path.exists(doc) else ""
    ck["user_words_in_Q89_record"] = bool(USER_WORDS in txt and "### Q89" in txt)
    ck["nest_tools_sha_as_expected"] = bool(all(sha(REPO + "/" + p) == v for p, v in NEST_TOOLS_SHA.items()))
    nest_am = [a for a in C.amendments() if a.get("id") == N.AMEND_ID]
    ck["AM_F55_NEST_registers_these_tools"] = bool(nest_am and all((nest_am[-1].get("code_sha256") or {}).get(p) == v for p, v in NEST_TOOLS_SHA.items()))
    ck["plan_sha_ok"] = bool(C.plan_sha_ok())
    ck["C2_not_started"] = not os.path.exists(rd + "/chain.log")
    return ck, g, fval, base, txt


def amendment_record(g, fval, txt):
    C, rd0, rd, gp = paths()
    g1, g2, g3 = g["GN1"], g["GN2"], g["GN3"]
    nest_am = [a for a in C.amendments() if a.get("id") == N.AMEND_ID][-1]
    doc = REPO + "/" + Q89_DOC_REL
    return dict(
        id=AMEND_DEV_ID, date=N.now(), by="workflow subagent of the main session (Claude), from the user's Q89 words",
        status="REGISTERED", label=LABEL, label_ja=LABEL_JA,
        what=("NAMED DEVIATION from the frozen run order of option C2: the dp 0.25 m nest (group 1, frames 1057-1657) is run although the 0.5 m "
              "identity nest C2ID failed GN1 on the crest height alone; an OUT-OF-RULE TRIAL, not a plan verdict"),
        user_decision=dict(q="Q89", date="2026-10-19", words_verbatim=USER_WORDS, recorded_in=Q89_DOC_REL,
                           recorded_in_sha256_at_registration=sha(doc),
                           context=("asked after the fixed C2ID: GN2 / GN3 passed, GN1 failed on the crest height only; question 'run 0.25 m as "
                                    "out-of-rule, or make 0.375 m the main candidate?'")),
        deviates_from=dict(rule=N.GN_RULES["order"], plan=C.PLAN_REL, plan_sha256=C.sha(C.PLAN), amendment=N.AMEND_ID,
                           amendment_date=nest_am.get("date"),
                           frozen_code_path="f55_nest.c2_tied_to_c2id refuses C2 because gates_GN.json ok is false"),
        facts=dict(gates_file=N.rel(gp), gates_sha256=sha(gp), gates_date=g.get("date"),
                   GN1=dict(ok=g1.get("ok"), checks=g1.get("checks"), values=g1.get("values"), tol=g1.get("tol"), failed_only=["Hc"],
                            parent_conv=(g1.get("parent") or {}).get("conv"), nest_conv=(g1.get("nest") or {}).get("conv"),
                            parent_lip1_t=(g1.get("parent") or {}).get("lip1_t"), nest_lip1_t=(g1.get("nest") or {}).get("lip1_t")),
                   GN2=dict(ok=g2.get("ok"), rms_m=g2.get("rms_m"), tol_m=g2.get("tol_m"), frames=g2.get("frames")),
                   GN3=dict(ok=g3.get("ok"), worst_rel=(g3.get("worst") or {}).get("rel"), worst_frame=(g3.get("worst") or {}).get("frame"),
                            tol=g3.get("tol")),
                   in_words=("GN2 PASS rms %.3f m (tol %.3f m); GN3 PASS worst %.2f %% (tol 2 %%); GN1 FAIL only on Hc_rel %+.4f (tol +-0.02): "
                             "x %+.1f m, t_conv %+.3f s, t_lip1 %+.3f s, hood %+.1f %%, air %+.1f %% all inside their tolerances [measured]"
                             % (fval["GN2_rms_m"], fval["GN2_tol_m"], 100 * fval["GN3_worst_rel"], fval["Hc_rel"], fval["x_m"], fval["t_conv_s"],
                                fval["t_lip1_s"], 100 * fval["hood_max_rel"], 100 * fval["air_max_rel"])),
                   tags="measured (f55_nest.py gates C2ID with the rules registered by AM-F55-NEST)"),
        bound=dict(Hc_rel_abs_max=HC_REL_MAX, why="the measured +0.0587 rounded up to 0.06 [chosen]; a C2ID with a larger crest error, or any other "
                                                  "failed GN item, is NOT covered and C2 stays refused"),
        allowed=("C2 group 1 run by f55_c2dev.py 'run C2' = f55_nest.py cmd_run('C2') unchanged (still-water calibration first, then the chain, "
                 "watchdog and resumes) and 'analyse C2' = f55_nest.py cmd_analyse('C2') unchanged; the reading C2 vs C2ID by f55_hollow.py "
                 "verdict (the frozen +25 % rule, unchanged), reported as an out-of-rule trial"),
        not_allowed=["no frozen tool, gate rule, tolerance, reading rule or cfg is changed",
                     "the C2 reading is NOT a plan verdict: C2ID's crest is +5.9 % above the parent's [measured], so C2 vs C2ID mixes the "
                     "resolution with the nest's own crest bias of unknown sign at dp 0.25",
                     "no other run, option or stage is covered (C2 full scope, a C2 rerun after a scene / tool change need their own record)"],
        reporting_rule=("every report, figure and video of this C2 says: '%s' / '%s'" % (LABEL, LABEL_JA)),
        code_sha256=dict(NEST_TOOLS_SHA), wrapper=dict(path=SELF_REL, sha256=sha(SELF)),
        c2id=dict(run=N.rel(rd0), launch_cfg=N.rel(N.launch_path("C2ID")), launch_cfg_sha256=sha(N.launch_path("C2ID")),
                  nest_hip_sha256=sha(N.NEST_HIP), build_check_sha256=sha(N.NEST_BUILD_CHECK)),
        tie_rule=("f55_c2dev.dev_tie: ok only if every other condition of f55_nest.c2_tied_to_c2id holds, gates_GN.json GN2 and GN3 ok and GN1 "
                  "failed only on Hc with |Hc_rel| <= 0.06, and this record (status REGISTERED) carries the gates_GN.json sha256, the wrapper "
                  "sha256, these exact values and the nest tools' sha256"),
        honesty=("the user decided (Q89) to run the 0.25 m trial although the identity gate failed on the crest height; the deviation is named, "
                 "bounded to the measured failure and written on every output; the GN rules stay as frozen"),
        tags=dict(values="measured", bound="chosen", reading="decided later by the frozen rule from measured quantities; out-of-rule"))


def cmd_register(dry=False):
    ck, g, fval, base, txt = register_facts()
    if not all(ck.values()):
        return N.final(dict(ok=False, step="register", appended=False, why=[k for k, v in ck.items() if not v], checks=ck))
    rec = amendment_record(g, fval, txt)
    if dry:
        return N.final(dict(ok=True, step="register", dry=True, appended=False, checks=ck, record=rec))
    same = [a for a in amendments_dev() if (a.get("facts") or {}).get("gates_sha256") == rec["facts"]["gates_sha256"]
            and (a.get("wrapper") or {}).get("sha256") == rec["wrapper"]["sha256"]]
    if same:
        return N.final(dict(ok=True, step="register", appended=False, why="already registered with this gates_GN.json and this wrapper",
                            date=same[-1].get("date"), tie=dev_tie()["ok"]))
    with open(N.guard(N.AMENDMENTS), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(N.clean(rec), ensure_ascii=False) + "\n")
    t = dev_tie()
    return N.final(dict(ok=bool(t["ok"]), step="register", appended=True, amendments=N.rel(N.AMENDMENTS), id=AMEND_DEV_ID, date=rec["date"],
                        gates_sha256=rec["facts"]["gates_sha256"], wrapper_sha256=rec["wrapper"]["sha256"], tie_ok=t["ok"], tie_why=t["why"]))


# ====================================================================== steps
def deviation_record(extra=None):
    t = dev_tie()
    am = amendments_dev()
    return dict(dict(label=LABEL, label_ja=LABEL_JA, out_of_rule=True, amendment=AMEND_DEV_ID, amendment_date=(am[-1].get("date") if am else None),
                     user_words_verbatim=USER_WORDS, recorded_in=Q89_DOC_REL, gates=t["gates"], gates_sha256=t["gates_sha256"], values=t["values"],
                     tie_ok=t["ok"], wrapper=SELF_REL, wrapper_sha256=sha(SELF), date=N.now(),
                     note=("C2 ran under the named deviation Q89 (C2ID GN1 failed on the crest height alone, +5.9 % vs +-2 %); its numbers are an "
                           "out-of-rule trial, not a plan verdict"), tags=dict(values="measured")), **(extra or {}))


def cmd_run(option, sim, o):
    _, rd0, rd, gp = paths()
    if option != "C2":
        return N.final(dict(ok=False, step="run", why="f55_c2dev.py runs only C2 (the deviation covers C2 group 1)"))
    t = dev_tie()
    print(N.now(), "dev_tie ok %s%s" % (t["ok"], (" | why: " + "; ".join(t["why"])) if t["why"] else ""), flush=True)
    if sim:
        cp = N.calib_core(sim=True)
        print(N.now(), "calibration preconditions (f55_nest.py calib C2 --simulate): %s; calibration state: %s" % (
            json.dumps(cp.get("pre"), ensure_ascii=False), json.dumps(N.calib_state(), ensure_ascii=False)), flush=True)
        if not t["ok"]:
            return N.final(dict(ok=False, step="run", option="C2", simulate=True, why="dev_tie: %s" % "; ".join(t["why"]), tie=t))
        return N.main(["run", "C2", "--simulate"])
    if not t["ok"]:
        return N.final(dict(ok=False, step="run", option="C2", why="C2 is not run (dev_tie): %s" % "; ".join(t["why"]), tie=t))
    with open(N.guard(N.LOG_DIR + "/f55_nest_run_C2.log"), "a", encoding="utf-8") as fh:
        fh.write("%s %s | %s | run by %s (sha %s) under %s\n" % (N.now(), LABEL, LABEL_JA, SELF_REL, sha(SELF), AMEND_DEV_ID))
    args = ["run", "C2"] + (["--wait-min=%s" % o["wait-min"]] if "wait-min" in o else [])
    rc = N.main(args)
    st = N.run_state(rd, N.F_END)
    if st["complete"]:
        N.jdump(deviation_record(dict(step="run", run=N.rel(rd), frames_done=st["frames_done"])), rd + "/f55/DEVIATION_Q89.json")
    return rc


def cmd_analyse(option, sim):
    _, rd0, rd, gp = paths()
    if option != "C2":
        return N.final(dict(ok=False, step="analyse", why="f55_c2dev.py analyses only C2"))
    t = dev_tie()
    print(N.now(), "dev_tie ok %s%s" % (t["ok"], (" | why: " + "; ".join(t["why"])) if t["why"] else ""), flush=True)
    if not t["ok"]:
        return N.final(dict(ok=False, step="analyse", option="C2", simulate=bool(sim), why="dev_tie: %s" % "; ".join(t["why"]), tie=t))
    if sim:
        return N.main(["analyse", "C2", "--simulate"])
    rc = N.main(["analyse", "C2"])
    ap = rd + "/f55/analyse_C2.json"
    a = N.jtry(ap)
    if a is not None:
        a = dict([("deviation", LABEL), ("deviation_ja", LABEL_JA), ("out_of_rule", True), ("amendment", AMEND_DEV_ID)] +
                 [(k, v) for k, v in a.items() if k not in ("deviation", "deviation_ja", "out_of_rule", "amendment")])
        N.jdump(a, ap)
    if os.path.isdir(rd):
        N.jdump(deviation_record(dict(step="analyse", run=N.rel(rd), analyse=N.rel(ap), analyse_ok=bool(a and a.get("ok")))),
                rd + "/f55/DEVIATION_Q89.json")
    return rc


def cmd_status():
    C, rd0, rd, gp = paths()
    t = dev_tie()
    return N.final(dict(ok=True, step="status", tie_ok=t["ok"], tie_why=t["why"], amendment=t["amendment_info"], values=t["values"],
                        calib_C2=N.calib_state(), run_C2=N.run_state(rd, N.F_END), run_C2ID=N.run_state(rd0, N.F_END),
                        c2_launch_cfg_exists=os.path.exists(N.launch_path("C2")), wrapper_sha256=sha(SELF)))


def main(argv):
    lab = Labelled(sys.stdout)
    sys.stdout = lab
    try:
        try:
            load_nest()
        except (SystemExit, Exception) as e:
            why = str(e.code) if isinstance(e, SystemExit) else "%s: %s" % (type(e).__name__, e)
            print(json.dumps(dict(ok=False, step=(argv[0] if argv else None), why=why[:600]), ensure_ascii=False), flush=True)
            return 2
        if not argv:
            print(__doc__)
            return 1
        cmd = argv[0]
        pos, o = N.opts(argv[1:])
        sim = "simulate" in o
        try:
            if cmd == "check":
                t = dev_tie()
                return N.final(dict(t, step="check"))
            if cmd == "register":
                return cmd_register("dry" in o)
            if cmd == "run":
                return cmd_run(pos[0] if pos else "C2", sim, o)
            if cmd == "analyse":
                return cmd_analyse(pos[0] if pos else "C2", sim)
            if cmd == "status":
                return cmd_status()
            print(__doc__)
            return 1
        except KeyboardInterrupt:
            raise
        except SystemExit as e:
            if isinstance(e.code, int) or e.code is None:
                raise
            N.final(dict(ok=False, step=cmd, why=str(e.code)[:800]))
            return 2
        except Exception as e:
            import traceback
            N.final(dict(ok=False, step=cmd, why="%s: %s" % (type(e).__name__, str(e)[:600]), traceback=traceback.format_exc()[-1500:]))
            return 2
    finally:
        lab.close_out()
        sys.stdout = lab.raw


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
