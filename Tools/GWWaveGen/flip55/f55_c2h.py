# -*- coding: utf-8 -*-
"""FLIP55 C2H: the 0.25 m nest continued to groups 2 and 3 (frames 1057-3001, 44-125 s) as the HERO, under the named deviation of Q89 extended
by the user's Q90 (py -3.10 -B; numpy; Houdini only inside the frozen chain it launches). 2026-10-19 written new (Claude, workflow subagent).
NOTHING frozen is edited: f55_nest.py (9769062c...), x55_nest_build.py (4385a162...) and f55_c2dev.py (c236548b...) are sha-checked and used
unchanged (f55_c2dev imported by path: its dev_tie, the bounded Q89 deviation, is REQUIRED here too); the parent export, the chain, the runner
(g52b3_run.py), g49_restart (seed / compare) are f55_nest.py's own code paths, called with new cfgs.

The user's words (Q90, verbatim; recorded in Docs/Workflow/Production_Workflow_ja.md):
  把 0.25 m 局部加密继续算到第 2、3 组，并和外面的水面拼接，做成主角。
Every output carries:  OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral

Steps (each prints ONE final json line with "ok"):
  export   (1) the parent's band export extended to frame 3001: a NEW export run F55P_DFGBV_c1632_export3001 = DFG-2B-V's launched cfg with
           only the restart keys changed (AM-F55-NEST parent_export cfg_rule) seeded by g49_restart.seed from the judged run's own checkpoint
           v.1632 (the last checkpoint <= 1657 of both the judged run and the registered export run), run by the patched frozen chain with
           the read-only export hook (frames 1633-3001); strict bit-identity against the judged run on EVERY frame 1633-3001 (hf / r2 / r3 /
           volcorr every frame, r4 / r5 on their common frames; h52b3_long rule); every x_<f>.npz 1633-3001 aligned with the judged hf (R1,
           <= 1e-3 m); the junction 1633-1657 equal array for array to the registered export -> export3001.json
  union    the target folder of C2H: Unity/Build/FLIP55/runs/F55X_DFGBV_union_f1056_3001/export = x_01056-x_01657 of the registered export
           (byte-identical files) + x_01658-x_03001 of the extension, vd/vd_01057-vd_03002 of the judged run (byte-equal to both export
           runs' own where present); hard links when the volume allows, else copies; union.json lists every file's source and sha256
  run      (2) C2H = C2's launch cfg (runs/ready/F55N_..._g1_launch.json, the file C2 ran with) with ONLY the hero keys changed (HERO_KEYS:
           run id, f_end 3001, records r5 every frame and the window 48-125 s, the union target, labels) -> runs/ready/<C2H>__hero_launch.json;
           the chain with f55_nest's watchdog and resumes (drive_chain, unchanged); requires c2h_tie
  identity C2H vs C2 on group 1 (frames 1057-1657): hf, r2 (sdf / u / w), r4 and r5 on C2's recorded frames, volcorr rows -> max diffs
           (g49_restart's readers, unchanged); + a REPORT-ONLY volume check of C2H vs the judged parent on every frame 1057-3001 (GN3's
           column rule) -> <C2H>/f55/identity_C2.json
  register [--dry]   AM-F55-C2H appended to plan/amendments.jsonl (verifies the facts first; same tools already registered -> nothing)
  check / status / selftest (reads only; selftest builds every cfg in memory and checks them)
Writes only under Unity/Build/FLIP55 (f55_nest.guard). Tags: [measured] records, [computed] derived, [chosen] choices, [guess] judgement.
usage: py -3.10 -B f55_c2h.py <step> [--simulate] [--wait-min=20]
"""
import os, sys, json, time, hashlib, importlib.util, glob, copy, shutil

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
SELF = HERE + "/f55_c2h.py"
SELF_REL = "Tools/GWWaveGen/flip55/f55_c2h.py"
C2DEV = HERE + "/f55_c2dev.py"
C2DEV_REL = "Tools/GWWaveGen/flip55/f55_c2dev.py"
C2DEV_SHA = "c236548ba2cf0b0faf27147d81a12f8262f2eb25bd5ef6c13145309771373d12"           # registered in AM-F55-C2-GN1DEV
NEST_TOOLS_SHA = {"Tools/GWWaveGen/flip55/f55_nest.py": "9769062cb90ef56a46b222f23ed5f831d1c13ef6c1fe30b99811714f7ed1ac21",
                  "Tools/GWWaveGen/flip55/x55_nest_build.py": "4385a162ee44b935f5531694d451a9153fee2eb6908d4fc1cbadb430963f01af"}
STITCH_REL = "Tools/GWWaveGen/flip55/f55_stitch.py"
HERO_REL = "Tools/GWWaveGen/flip55/f55_c2h_hero.py"
AUTO = "G:/research/Wave Simulation/_tools/auto_C2H.py"
LABEL = "OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral"
LABEL_JA = "規則の外の 0.25 m の入れ子（同一性の試しで頂の高さ +5.9 %、容差 ±2 %、Q89/Q90）。親 DFG-2B-V は有効。エネルギーは DM1A のスペクトル"
USER_WORDS = "把 0.25 m 局部加密继续算到第 2、3 组，并和外面的水面拼接，做成主角。"
Q90_DOC_REL = "Docs/Workflow/Production_Workflow_ja.md"
AMEND_ID = "AM-F55-C2H"
AMEND_DEV_ID = "AM-F55-C2-GN1DEV"

B55 = REPO + "/Unity/Build/FLIP55"
RUNS_ROOT = B55 + "/runs"
READY = RUNS_ROOT + "/ready"
LOG_DIR = B55 + "/_logs"
SIM_DIR = B55 + "/_scratch/sim_c2h"
FPS = 24.0
F_HERO_END = 3001                                  # t 125 s (= f55_common.F_END_FULL)
EXT_CKPT = 1632                                    # the judged run's last checkpoint <= 1657 (ckpt v.1632 exists in the judged run and the export run)
EXT_F0 = EXT_CKPT + 1
EXT_RID = "F55P_DFGBV_c1632_export3001"
EXT_RD = RUNS_ROOT + "/" + EXT_RID
EXT_DIR = EXT_RD + "/export"
EXT_JSON = EXT_DIR + "/export3001.json"
EXT_CFG = READY + "/" + EXT_RID + ".json"
UNION_RID = "F55X_DFGBV_union_f1056_3001"
UNION_RD = RUNS_ROOT + "/" + UNION_RID
UNION_DIR = UNION_RD + "/export"
UNION_VD = UNION_DIR + "/vd"
UNION_JSON = UNION_RD + "/union.json"
RID_C2 = "F55N_D19B_x180y60_dp0p25_c1056"
RD_C2 = RUNS_ROOT + "/" + RID_C2
C2_LAUNCH = READY + "/" + RID_C2 + "__g1_launch.json"
RID_C2H = "F55NH_D19B_x180y60_dp0p25_c1056_t125"
RD_C2H = RUNS_ROOT + "/" + RID_C2H
C2H_LAUNCH = READY + "/" + RID_C2H + "__hero_launch.json"
IDENT_JSON = RD_C2H + "/f55/identity_C2.json"
HERO_WINDOW = [48.0, 125.0]                        # surface every frame 1153-3001 (the Q86 hero window)
C2H_MAX_HOURS = 8.0                                # [chosen] per chain: estimate 5.4 h [computed] x 1.2 + 1.5 h; drive_chain resumes a max_hours stop twice
# the launch keys of C2H that differ from C2's launch cfg (everything else canonically equal; checked by c2h_only_hero_keys_differ)
HERO_KEYS = ("run_id", "f_end", "t_end_s", "max_hours", "pstats_frames", "records.r5.every", "records.windows", "parms.tgt_dir", "parms.rep_dir",
             "note", "case.name", "case.stage", "case.role", "case.judged", "case.hero", "f55.option", "f55.stage", "f55.c2h", "precheck",
             "nest.records")
HERO_KEYS_WHY = {
    "run_id / f_end / t_end_s": "the new run folder F55NH_... to frame 3001 (t 125 s): groups 2 and 3 (Q90)",
    "max_hours": "%.1f h per chain [chosen]: C2 measured 1.213 h for 601 frames (7.25 s / frame incl. 113 surfaces) [measured]; C2H 1945 frames "
                 "+ 1849 surfaces x 2.93 s -> about 5.4 h [computed]" % C2H_MAX_HOURS,
    "pstats_frames": "[1057, 1058, 3001] (particle stats at the first frames and the new last frame; report only)",
    "records.r5.every / records.windows": "surface every frame in 48-125 s (frames 1153-3001) for the Unity hero (Q86 window); r4 keeps every 3rd "
                                          "frame (same phase as C2, so C2's r4 frames are a subset), now in 48-125 s",
    "parms.tgt_dir / parms.rep_dir": "the union folder F55X_DFGBV_union_f1056_3001/export (x_01056-x_01657 = the registered export's own files "
                                     "byte for byte, x_01658-x_03001 = the extension; vd = the judged run's) - the nest scene reads x_<f>.npz of "
                                     "tgt_dir and vd_<f>.txt of rep_dir and nothing else changes for frames <= 1657",
    "note / case.* / f55.option / f55.stage / f55.c2h": "labels (C2H, hero, OUT-OF-RULE, Q90, the amendment, this tool and its sha256)",
    "nest.records": "label text only (no tool reads it): C2's text said 'r4 / r5 every 3rd frame in [55, 69] s'; C2H's says what C2H records",
    "precheck": "this launch's own precheck (C2's checks + the C2H checks)",
}
EXT_TOP_ALLOWED = {"run_id", "out_root", "f_start", "f_first", "f_end", "still_offset_m", "note", "restart", "f55", "precheck"}


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def rel(p):
    p = str(p).replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO + "/") else p


# ====================================================================== the frozen modules (sha first)
D = N = None


def load():
    """f55_c2dev by path (sha = AM-F55-C2-GN1DEV's wrapper sha), which loads f55_nest by path (sha = AM-F55-NEST's) and installs dev_tie."""
    global D, N
    if D is not None:
        return D, N
    if sha(C2DEV) != C2DEV_SHA:
        raise SystemExit("f55_c2dev.py sha %s differs from the registered %s: not run" % (sha(C2DEV), C2DEV_SHA))
    bad = {p: sha(REPO + "/" + p) for p, v in NEST_TOOLS_SHA.items() if sha(REPO + "/" + p) != v}
    if bad:
        raise SystemExit("nest tools differ from the registered sha256: %s" % json.dumps(bad))
    spec = importlib.util.spec_from_file_location("f55_c2dev", C2DEV)
    m = importlib.util.module_from_spec(spec)
    sys.modules["f55_c2dev"] = m
    spec.loader.exec_module(m)
    m.load_nest()
    D, N = m, m.N
    return D, N


def final(d):
    d = dict([("label", LABEL)] + [(k, v) for k, v in d.items() if k != "label"])
    return N.final(d) if N is not None else (print(json.dumps(d, ensure_ascii=False, default=str), flush=True) or (0 if d.get("ok") else 1))


def logger(name, sim=False):
    lines = []

    def log(*a):
        msg = "%s %s | %s" % (now(), " ".join(str(x) for x in a), LABEL)
        lines.append(msg)
        print(msg, flush=True)
        if not sim:
            with open(N.guard(LOG_DIR + "/" + name), "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
    log.lines = lines
    return log


def c2_state():
    return N.run_state(RD_C2, N.F_END)


def c2h_state():
    return N.run_state(RD_C2H, F_HERO_END)


# ====================================================================== the tie: the Q89 deviation (unchanged) + the Q90 record
def amendments(aid):
    return [a for a in N.C_().amendments() if a.get("id") == aid]


def tool_shas():
    return {SELF_REL: sha(SELF), STITCH_REL: sha(REPO + "/" + STITCH_REL), HERO_REL: sha(REPO + "/" + HERO_REL), C2DEV_REL: sha(C2DEV),
            **{p: sha(REPO + "/" + p) for p in NEST_TOOLS_SHA}}


def stitch_mod():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import f55_stitch as S
    return S


def c2h_tie():
    D_, N_ = load()
    t = D_.dev_tie()
    why = ["Q89 deviation tie (f55_c2dev.dev_tie): %s" % w for w in t["why"]]
    ck = {}
    am = amendments(AMEND_ID)
    a = am[-1] if am else {}
    doc = REPO + "/" + Q90_DOC_REL
    txt = open(doc, encoding="utf-8").read() if os.path.exists(doc) else ""
    ck["q90_words_in_record"] = bool(USER_WORDS in txt and "### Q90" in txt)
    ck["amendment_exists"] = bool(am)
    ck["amendment_registered"] = a.get("status") == "REGISTERED"
    ck["amendment_user_words"] = (a.get("user_decision") or {}).get("words_verbatim") == USER_WORDS
    ck["amendment_label"] = a.get("label") == LABEL
    cs = a.get("code_sha256") or {}
    cur = tool_shas()
    ck["amendment_tools_sha_current"] = bool(cs and all(cs.get(k) == v for k, v in cur.items()))
    dev = amendments(AMEND_DEV_ID)
    ck["extends_last_Q89_record"] = bool(dev and (a.get("extends") or {}).get("date") == dev[-1].get("date")
                                         and (a.get("extends") or {}).get("gates_sha256") == (dev[-1].get("facts") or {}).get("gates_sha256"))
    ck["c2_complete"] = bool(c2_state()["complete"])
    ck["c2_launch_cfg_as_registered"] = bool((a.get("c2") or {}).get("launch_cfg_sha256") == sha(C2_LAUNCH) and sha(C2_LAUNCH))
    S = stitch_mod()
    ck["seam_as_registered"] = bool((a.get("stitch") or {}).get("seam") == S.SEAM)
    ck["seamscan_as_registered"] = bool((a.get("stitch") or {}).get("seamscan_sha256") == sha(S.SCAN_JSON) and sha(S.SCAN_JSON))
    why += ["C2H record: %s" % k for k, v in ck.items() if not v]
    return dict(ok=not why, why=why, label=LABEL, q89_tie=dict(ok=t["ok"], values=t.get("values")), checks=ck, amendment=AMEND_ID,
                amendment_date=a.get("date"), tools=cur)


def register_facts():
    D_, N_ = load()
    ck = {}
    t = D_.dev_tie()
    ck["q89_tie_ok"] = bool(t["ok"])
    doc = REPO + "/" + Q90_DOC_REL
    txt = open(doc, encoding="utf-8").read() if os.path.exists(doc) else ""
    ck["q90_words_in_record"] = bool(USER_WORDS in txt and "### Q90" in txt)
    ck["c2_complete"] = bool(c2_state()["complete"])
    ck["c2_launch_cfg_exists"] = os.path.exists(C2_LAUNCH)
    ck["plan_sha_ok"] = bool(N_.C_().plan_sha_ok())
    S = stitch_mod()
    sc = N_.jtry(S.SCAN_JSON) or {}
    ck["seamscan_matches_tool"] = bool(sc.get("tool_matches_rule") and sc.get("seam_in_tool") == S.SEAM)
    ck["tools_exist"] = bool(all(v for v in tool_shas().values()))
    ck["c2h_not_started"] = not os.path.exists(RD_C2H + "/chain.log")
    return ck, t, sc


def amendment_record():
    D_, N_ = load()
    ck, t, sc = register_facts()
    S = stitch_mod()
    dev = amendments(AMEND_DEV_ID)[-1]
    doc = REPO + "/" + Q90_DOC_REL
    c2r = N_.jtry(RD_C2 + "/f55/reading_C2dev_Q89.json") or {}
    return dict(
        id=AMEND_ID, date=now(), by="workflow subagent of the main session (Claude), from the user's Q90 words", status="REGISTERED", label=LABEL,
        label_ja=LABEL_JA,
        what=("NAMED EXTENSION of the deviation %s (Q89) from 'C2 group 1' to the HERO: the dp 0.25 m nest continued to frames 1057-3001 (groups "
              "1-3, 44-125 s) as run C2H, its parent export extended to frame 3001, and its surface stitched to DFG-2B-V's every-frame hero surface "
              "for the Unity hero; still an OUT-OF-RULE trial (C2ID GN1 crest +5.9 %% vs +-2 %%), not a plan verdict" % AMEND_DEV_ID),
        user_decision=dict(q="Q90", date="2026-10-19", words_verbatim=USER_WORDS, recorded_in=Q90_DOC_REL, recorded_in_sha256_at_registration=sha(doc),
                           context=("asked after C2 group 1 (out-of-rule) reported: at the same crest the cavity 24.9 m2 vs 11.5 m2 at 0.5 m (x2.2), "
                                    "print-like score3 0.244 at f1455 [measured]; question 'hero = 0.375 m full re-record or the 0.25 m nest on "
                                    "all groups?'")),
        extends=dict(id=AMEND_DEV_ID, date=dev.get("date"), gates_sha256=(dev.get("facts") or {}).get("gates_sha256"),
                     wrapper_sha256=(dev.get("wrapper") or {}).get("sha256"),
                     tie="f55_c2dev.dev_tie, unchanged and REQUIRED (C2ID GN2 / GN3 pass, GN1 failed on Hc alone, |Hc_rel| <= 0.06)"),
        scope=dict(
            parent_export=dict(run=rel(EXT_RD), cfg_rule=("AM-F55-NEST parent_export cfg_rule unchanged (DFG-2B-V's launched cfg with only the "
                                                          "restart keys changed), seeded by g49_restart.seed from the judged run's own v.%04d" % EXT_CKPT),
                               hook="the read-only export hook of f55_nest.py (mode export), unchanged; boxes = the registered export's xb / yb / eb",
                               frames=[EXT_F0, F_HERO_END],
                               acceptance=("strict bit-identity vs the judged run on every frame %d-%d (hf / r2 / r3 / volcorr every frame, r4 / r5 "
                                           "common frames; complete counts) + R1 alignment <= 1e-3 m on every x_<f>.npz + the junction %d-1657 "
                                           "equal array for array to the registered export" % (EXT_F0, F_HERO_END, EXT_F0))),
            union=dict(dir=rel(UNION_DIR), rule=("x_01056-x_01657 = the registered export's files byte for byte, x_01658-x_03001 = the "
                                                  "extension's, vd_01057-vd_03002 = the judged run's (byte-equal to both export runs' own where "
                                                  "present); union.json: every file's source and sha256")),
            run=dict(run=rel(RD_C2H), launch_rule=("C2's launch cfg (%s, the file C2 ran with) with only HERO_KEYS changed: %s" % (
                rel(C2_LAUNCH), ", ".join(HERO_KEYS))), why=HERO_KEYS_WHY, scene_tools="the C2 nest scene / tools / calibration (C2's launch "
                                                                                      "parms incl. band_lin 1 and init_lvl_m)"),
            identity=("C2H vs C2 on 1057-1657 (hf / r2 / r4 / r5 / volcorr): reported with max differences; a difference does not stop the hero "
                      "but every output then says 'C2H group 1 differs from C2 (max ... m)' and the C2H numbers are its own [chosen]"),
            stitch=dict(tool=STITCH_REL, rule=S.STITCH_RULE, seam=S.SEAM, seam_rule=S.SEAM_RULE, display=S.DISPLAY_EN),
            hero=("seat A (284, -20, eye 1.5) with clearance on the STITCHED surface every frame (rule of h52b3_hero: >= 1 m); print pose = pv53 "
                  "option D of C2H's own group-2 most print-like instant (pv53.PVRun on the C2H records with the PARENT's judge periods: the nest's "
                  "own judge-like tracker mis-tracked Hc 3.2 m vs ~7.2 m in group 1 [measured], so it is not used); move Q86: move 6 s, hold 2 s, "
                  "stay by the crest-leaves-frame rule (h52b3_hero STAY_RULE: 2.5 s kept if within 0.5 s of DFG-2B-E's), back 6 s; captures "
                  "cseat / cprint / cmove 1920x1080 24 fps; 3-view 2x2 video (front / top / print view / print); sheet")),
        not_allowed=["no frozen tool, gate rule, tolerance, reading rule or design cfg is changed; GN1-GN3 are not re-run or re-read",
                     "C2H is NOT a plan verdict and NOT a valid run by any frozen rule: the identity nest failed GN1 on the crest height",
                     "the stitch is display only: no record of C2H or of DFG-2B-V is changed; the blend strip and the zipper exist only in the "
                     "stitched Unity records"],
        facts=dict(c2_group1=dict(cavity_m2=[24.9, 11.5], cavity_ratio=2.2, print_like=dict(frame=1455, score3=0.244), tag="measured (main-session report "
                                  "of C2 group 1, out-of-rule)"),
                   c2_reading=dict(verdict=c2r.get("verdict_by_frozen_rule"), file=rel(RD_C2 + "/f55/reading_C2dev_Q89.json")),
                   tracker_caveat="inside the nest the judge-like convergence tracker mis-tracked Hc (3.2 m vs ~7.2 m) [measured]; the hero uses "
                                  "pv53's print-like instants on the centre section r2 with the parent's judge periods",
                   q89_values=t.get("values"), seamscan=dict(file=rel(S.SCAN_JSON), chosen=sc.get("chosen_by_rule"),
                                                             at_chosen={k: (sc.get("summary") or {}).get(k, {}).get(str(v)) for k, v in
                                                                        (sc.get("chosen_by_rule") or {}).items()})),
        stitch=dict(seam=S.SEAM, seamscan=rel(S.SCAN_JSON), seamscan_sha256=sha(S.SCAN_JSON)),
        c2=dict(run=rel(RD_C2), launch_cfg=rel(C2_LAUNCH), launch_cfg_sha256=sha(C2_LAUNCH), complete=bool(c2_state()["complete"])),
        code_sha256=tool_shas(), launcher=dict(path=AUTO, sha256=sha(AUTO)),
        reporting_rule="every report, figure, video, manifest and status line of C2H says: '%s' / '%s'" % (LABEL, LABEL_JA),
        tie_rule=("f55_c2h.c2h_tie: ok only if f55_c2dev.dev_tie is ok (unchanged), this record (the LAST %s, REGISTERED) carries the user's Q90 "
                  "words, the current sha256 of f55_c2h.py / f55_stitch.py / f55_c2h_hero.py / f55_c2dev.py / f55_nest.py / x55_nest_build.py, "
                  "the date and gates sha256 of the last %s, C2's launch cfg sha256 and the seam + seamscan sha256, and C2 is complete" % (
                      AMEND_ID, AMEND_DEV_ID)),
        honesty=("the user decided (Q90) to make the 0.25 m nest the hero; the deviation of Q89 is carried over unchanged and named on every "
                 "output; the parent DFG-2B-V stays the valid run of the frozen DFGB4 rule; energy: sum a^2 = DM1A's (spectral), in-tank power "
                 "0.23 x DM1A"),
        checks_at_registration=ck,
        tags=dict(values="measured", choices="chosen", estimates="computed"))


def same_registered():
    """the AM-F55-C2H records that already carry the CURRENT tool shas, seamscan sha, C2 launch-cfg sha and the last Q89 record's date."""
    load()
    S = stitch_mod()
    dev = amendments(AMEND_DEV_ID)
    cur = dict(code=tool_shas(), seamscan=sha(S.SCAN_JSON), c2cfg=sha(C2_LAUNCH), ext_date=(dev[-1].get("date") if dev else None))
    return [a for a in amendments(AMEND_ID) if (a.get("code_sha256") or {}) == cur["code"]
            and (a.get("stitch") or {}).get("seamscan_sha256") == cur["seamscan"]
            and (a.get("c2") or {}).get("launch_cfg_sha256") == cur["c2cfg"]
            and (a.get("extends") or {}).get("date") == cur["ext_date"]]


def cmd_register(dry=False):
    # idempotent FIRST (review 2026-10-19): a launcher restart after C2H has started must not fail on 'c2h_not_started' when the same
    # tools / seam / C2 cfg are already registered; a NEW registration after C2H started stays refused (register_facts below)
    same = same_registered()
    if same and not dry:
        return final(dict(ok=True, step="register", appended=False, why="already registered with these tools / seam / C2 cfg", date=same[-1].get("date"),
                          tie_ok=c2h_tie()["ok"]))
    ck, t, sc = register_facts()
    if not all(ck.values()):
        return final(dict(ok=False, step="register", appended=False, why=[k for k, v in ck.items() if not v], checks=ck))
    rec = amendment_record()
    if dry:
        return final(dict(ok=True, step="register", dry=True, appended=False, record=rec))
    same = [a for a in amendments(AMEND_ID) if (a.get("code_sha256") or {}) == rec["code_sha256"]
            and (a.get("stitch") or {}).get("seamscan_sha256") == rec["stitch"]["seamscan_sha256"]
            and (a.get("c2") or {}).get("launch_cfg_sha256") == rec["c2"]["launch_cfg_sha256"]
            and (a.get("extends") or {}).get("date") == rec["extends"]["date"]]
    if same:
        return final(dict(ok=True, step="register", appended=False, why="already registered with these tools / seam / C2 cfg", date=same[-1].get("date"),
                          tie_ok=c2h_tie()["ok"]))
    with open(N.guard(N.AMENDMENTS), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(N.clean(rec), ensure_ascii=False) + "\n")
    t2 = c2h_tie()
    return final(dict(ok=bool(t2["ok"]), step="register", appended=True, id=AMEND_ID, date=rec["date"], tie_ok=t2["ok"], tie_why=t2["why"]))


# ====================================================================== (1) the parent export extended to 3001
def ext_spec():
    s = N.export_spec()
    s.pop("boxes_ckpt_extra", None)
    s.pop("boxes_ckpt_note", None)
    s.update(frames=[EXT_F0, F_HERO_END], frame_ckpt=EXT_CKPT, out_dir=rel(EXT_DIR),
             extension_note=("C2H (Q90): the registered export's boxes and rule unchanged, frames %d-%d; the initial-state box nb is not needed "
                             "(C2H starts from C2's own frame-1056 state, the registered export's x_01056)" % (EXT_F0, F_HERO_END)))
    return s


def ext_cfg():
    C = N.C_()
    rd0 = C.DFGBV_RUN
    c0 = N.jload(rd0 + "/cfg.json")
    if c0.get("run_id") != N.DFGBV_RID or (c0.get("dir") or {}).get("set") != "DFGB4" or c0.get("restart"):
        raise SystemExit("the extension reruns DFG-2B-V only")
    sys.path.insert(0, N.T52)
    import g52_ana as GA52
    off, off_src = GA52.still_offset(rd0)
    c = copy.deepcopy(c0)
    for k in N.POP_TOP:
        c.pop(k, None)
    spec = ext_spec()
    c.update(run_id=EXT_RID, out_root=N.RUNS_ROOT, f_start=EXT_F0, f_first=EXT_F0, f_end=F_HERO_END, still_offset_m=off)
    c["case"].update(judged=False, role=("FLIP55 C2H parent export EXTENSION (Q90): DFG-2B-V recomputed from its own checkpoint v.%04d with the frozen "
                                         "runner and the read-only field export (NOT judged; bit-identical to the judged run is REQUIRED)" % EXT_CKPT),
                     restart_of=c0["run_id"], restart_ckpt_frame=EXT_CKPT, f55_export=True)
    ck = rd0 + "/ckpt/v.%04d.sim" % EXT_CKPT
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=EXT_CKPT, ckpt_t_s=(EXT_CKPT - 1) / FPS, ckpt_file=ck,
                        ckpt_bytes=os.path.getsize(ck) if os.path.exists(ck) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B %s export (g49_restart.seed through f55_nest.restart_module, dirs() replaced in memory)" % SELF_REL,
                        compare="g49_restart.compare + f55_nest.strict_compare (strict, h52b3_long rule) inside %s export" % SELF_REL)
    c["f55"] = dict(mode="export", option="C2HP", export=spec, runner=rel(N.RUNNER), runner_sha256=N.RUNNER_SHA, chain=rel(N.CHAIN), chain_sha256=N.CHAIN_SHA,
                    hook="hou.setFrame wrapped: fields of frame f (cooked by the runner) exported before frame f + 1; original call unchanged",
                    tool=N.TOOL_REL, extension_tool=SELF_REL, label=LABEL, amendment=AMEND_ID)
    c["note"] = ("FLIP55 C2H parent export EXTENSION (%s, 2026-10-19, Q90): DFG-2B-V %s recomputed from v.%04d (%.3f s) to frame %d with its own "
                 "launched cfg (only the restart keys changed), the frozen g52b3_run.py and the read-only export hook; physics unchanged "
                 "(bit-identity against the judged run checked on every frame) | %s" % (SELF_REL, c0["run_id"], EXT_CKPT, (EXT_CKPT - 1) / FPS,
                                                                                       F_HERO_END, LABEL))
    c["precheck"] = ext_precheck(c, c0, off)
    return c, c0


def ext_precheck(c, c0, off):
    """f55_nest.precheck_export (unchanged) + the three items bound to its own checkpoint 1056 / frame 1657 / folder replaced by the extension's."""
    C = N.C_()
    pc = N.precheck_export(c, c0, off)
    ck = pc["checks"]
    rd0 = C.DFGBV_RUN
    vdir = rd0 + "/volcorr"
    rows = set()
    for ln in open(vdir + "/state.jsonl", encoding="utf-8"):
        try:
            rows.add(int(json.loads(ln)["f"]))
        except Exception:
            pass
    nT = int(round(float(c0["sf"]["T"]) * FPS))
    rep = {}
    rep["export_volcorr_state_ready"] = (bool(os.path.exists(vdir + "/ref.json") and os.path.exists(vdir + "/vd_%05d.txt" % EXT_CKPT)
                                              and os.path.exists(vdir + "/vd_%05d.txt" % EXT_F0) and all(f in rows for f in range(EXT_CKPT - nT + 1, EXT_CKPT + 1))),
                                         "vd_%05d / vd_%05d and the state rows of the last period before %d (f55_nest's item names 1056 / 1057)"
                                         % (EXT_CKPT, EXT_F0, EXT_CKPT))
    est_gb = (F_HERO_END - EXT_CKPT) * 1.2e-3 + 1.6 * (F_HERO_END - EXT_F0 + 1) / 3001.0 + 15 * 0.2
    import g52b3_common as GCC
    free = GCC.free_gb()
    rep["export_disk_ok"] = (bool(free - est_gb >= float(c.get("disk_stop_free_gb", 25.0)) + N.DISK_MARGIN_GB),
                             "export %.1f GB + records + checkpoints for %d frames [computed] vs G: free %.1f GB" % (est_gb, F_HERO_END - EXT_CKPT, free))
    ran = glob.glob(EXT_RD + "/run_c*.json") or os.path.exists(EXT_RD + "/chain.log")
    if ran:
        old = N.jtry(EXT_RD + "/cfg.json") or {}
        strip = lambda d: {k: v for k, v in d.items() if k not in ("precheck", "hip_sha256", "module_shas_at_chain_start")}
        rep["export_existing_run_is_this_cfg"] = (bool(N.canon(strip(old)) == N.canon(strip(c))), "the extension folder's own cfg.json")
    else:
        rep["export_existing_run_is_this_cfg"] = (True, "the extension folder has not run")
    for k, (v, why) in rep.items():
        if k in ck:
            pc.setdefault("replaced", {})[k] = dict(value=ck[k], why="f55_nest's item is bound to the registered export (ckpt 1056, frame 1657, "
                                                                     "its folder); the extension's: " + why)
        ck[k] = v
    ck["ext_ckpt_in_judged_run"] = bool(os.path.exists(rd0 + "/ckpt/v.%04d.sim" % EXT_CKPT))
    ck["ext_registered_export_ok"] = bool((N.jtry(N.EXPORT_JSON) or {}).get("ok"))
    ck["ext_frames"] = bool(c["f_start"] == EXT_F0 == c["f_first"] and c["f_end"] == F_HERO_END and c["f55"]["export"]["frames"] == [EXT_F0, F_HERO_END])
    sd = N.source_diff(c0, c)
    ck["export_selfcheck_vs_source"] = bool(sd["ok"])
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    pc["extension"] = dict(tool=SELF_REL, label=LABEL, date=now())
    return pc


def validate_ext(frames):
    """R1 alignment of the extension's x files vs the judged hf (f55_nest's rule, its readers unchanged)."""
    import numpy as np
    spec = ext_spec()
    H = N.HF(N.DFGBV_RUN)
    missing, bad, rows = [], [], []
    worst = dict(dmax=0.0, frame=None)
    nbytes = 0
    for f in frames:
        p = EXT_DIR + "/x_%05d.npz" % f
        if not os.path.exists(p):
            missing.append(f); continue
        nbytes += os.path.getsize(p)
        try:
            meta, A = N.load_x(np, p)
        except Exception as e:
            bad.append("%d unreadable %r" % (f, e)); continue
        need = ["%s_%s" % (b, k) for b in spec["boxes"] for k, _ in N.FIELDS]
        if sorted(need) != sorted(A) or int(meta.get("frame", -1)) != f or not all(np.isfinite(A[k].astype(np.float64)).all() for k in A):
            bad.append("%d keys / frame / finite" % f); continue
        s = A["xb_s"]; m = meta["keys"]["xb_s"]
        et = N.r1_eta(np, s, m["p0"][1], m["d"][1])
        xs = m["p0"][0] + m["d"][0] * np.arange(s.shape[2]); ys = m["p0"][2] + m["d"][2] * np.arange(s.shape[0])
        e, hm = H.get(f)
        if e is None:
            bad.append("%d no judged hf" % f); continue
        X, Y = np.meshgrid(xs, ys)
        eh = N.eta_at(np, e, hm, X, Y)
        ok = np.isfinite(et) & np.isfinite(eh)
        dmax = float(np.abs(et[ok] - eh[ok]).max()) if ok.any() else float("inf")
        nan_mis = int((np.isfinite(et) != np.isfinite(eh)).sum())
        # f55_nest.validate_export's third criterion (review 2026-10-19): the file must match its OWN frame better than frames f +- 1
        # (catches an off-by-one frame label of the hook)
        neigh = []
        for g in (f - 1, f + 1):
            e2, hm2 = H.get(g)
            if e2 is not None:
                e2i = N.eta_at(np, e2, hm2, X, Y)
                ok2 = np.isfinite(et) & np.isfinite(e2i)
                neigh.append(float(np.abs(et[ok2] - e2i[ok2]).max()) if ok2.any() else float("inf"))
        rows.append(dict(frame=f, dmax=dmax, nan_mismatch=nan_mis, neighbour_dmax=min(neigh) if neigh else None))
        if dmax > worst["dmax"]:
            worst = dict(dmax=dmax, frame=f)
    al_ok = bool(rows and len(rows) == len(frames) - len(missing) - len(bad)
                 and all(r["dmax"] <= 1e-3 and r["nan_mismatch"] == 0 and (r["neighbour_dmax"] is None or r["neighbour_dmax"] > r["dmax"])
                         for r in rows))
    return dict(frames=[frames[0], frames[-1]], n_expected=len(frames), n_missing=len(missing), missing=missing[:30], n_bad=len(bad), bad=bad[:10],
                alignment_ok=al_ok, alignment_worst=worst, gb=round(nbytes / 1e9, 3), ok=bool(not missing and not bad and al_ok),
                rule=("R1 top surface of the exported xb SDF vs the judged hf of the same frame: max |diff| <= 1e-3 m, no NaN mismatch, and smaller "
                      "than against frames f +- 1 (f55_nest.validate_export's rule, all three criteria)"))


def junction_check():
    """the extension's x_<f> vs the registered export's on the overlap EXT_F0..1657: every array equal (same physics, same hook)."""
    import numpy as np
    rows, diff = [], []
    for f in range(EXT_F0, N.F_END + 1):
        pa, pb = N.EXPORT_DIR + "/x_%05d.npz" % f, EXT_DIR + "/x_%05d.npz" % f
        if not (os.path.exists(pa) and os.path.exists(pb)):
            diff.append((f, "missing")); continue
        ma, A = N.load_x(np, pa); mb, B = N.load_x(np, pb)
        same = sorted(A) == sorted(B) and all(np.array_equal(A[k], B[k], equal_nan=True) for k in A)
        rows.append(f)
        if not same:
            mx = max(float(np.nanmax(np.abs(A[k].astype(np.float64) - B[k].astype(np.float64)))) for k in A if k in B)
            diff.append((f, "max %.3g" % mx))
    return dict(frames=[EXT_F0, N.F_END], n=len(rows), differ=diff[:20], n_differ=len(diff), ok=bool(rows and not diff),
                rule="np.array_equal on every array of x_<f>.npz, frames %d-1657 (the registered export vs the extension)" % EXT_F0)


def cmd_export(sim=False, o=None):
    t0 = time.time()
    log = logger("c2h_export.log", sim)
    done = N.jtry(EXT_JSON) or {}
    if done.get("ok") and not sim:
        return final(dict(ok=True, step="export", skipped="export3001.json exists and is ok", export=rel(EXT_JSON)))
    c, c0 = ext_cfg()
    pc = c["precheck"]
    log("extension cfg", EXT_RID, "precheck ok", pc["ok"], pc.get("reason") or "")
    src, counts = N.chain_source()
    compile(src, "patched chain", "exec")
    plan = [("seed", "g49_restart.seed (v.%04d of the judged run, volcorr ref.json, vd_%05d, vd_%05d, state rows f <= %d) -> %s" % (
                EXT_CKPT, EXT_CKPT, EXT_F0, EXT_CKPT, rel(EXT_RD))),
            ("chain", "py -3.10 -B %s chain export %s (g52b3_chain.py, replacements %s -> hython %s hyrun -> g52b3_run.py unchanged + hook, frames "
                      "%d-%d)" % (N.SELF, EXT_CFG, counts, N.SELF, EXT_F0, F_HERO_END)),
            ("compare", "g49_restart.compare + f55_nest.strict_compare: frames %d-%d vs %s" % (EXT_F0, F_HERO_END, rel(N.DFGBV_RUN))),
            ("validate", "x_<f>.npz %d-%d R1 alignment vs the judged hf; junction %d-1657 vs the registered export" % (EXT_F0, F_HERO_END, EXT_F0))]
    if sim:
        for k, v in plan:
            log("[simulate]", k, v)
        out = dict(ok=bool(pc["ok"]), step="export", simulate=True, precheck=dict(ok=pc["ok"], reason=pc.get("reason"), checks=pc["checks"],
                                                                                 replaced=list((pc.get("replaced") or {}).keys())),
                   source_diff=pc["export"]["source_diff"], chain_replacements=counts, plan=plan, spec=c["f55"]["export"])
        N.jdump(dict(out, cfg=c), SIM_DIR + "/export3001_plan.json")
        return final(out)
    if not pc["ok"]:
        return final(dict(ok=False, step="export", why="extension cfg precheck: %s" % pc.get("reason")))
    if not N.chain_alive(EXT_RID):
        eg = N.entry_guard("export3001", "export", wait_min=float((o or {}).get("wait-min", N.WAIT_MIN)))
        log("entry guard", "ok" if eg["ok"] else eg["why"])
        if not eg["ok"]:
            return final(dict(ok=False, step="export", why="entry guard: %s" % eg["why"], guard=eg))
    p, how = N.write_cfg_once(c, EXT_CFG)
    log("cfg", rel(p), how)
    rec = dict(date=now(), tool=SELF_REL, tool_sha256=sha(SELF), cfg=rel(p), cfg_sha256=sha(p), run=rel(EXT_RD), spec=c["f55"]["export"], label=LABEL)
    RS = N.restart_module()
    if not (glob.glob(EXT_RD + "/run_c*.json") or os.path.exists(EXT_RD + "/chain.log")):
        sd = RS.seed(p)
        ok_seed = all(v.get("dst_sha256") in (v.get("src_sha256"), v.get("src_sha256_of_rows")) for v in sd["files"].values())
        rec["seed"] = dict(ok=ok_seed, files={k: {kk: v.get(kk) for kk in ("bytes", "rows", "frames")} for k, v in sd["files"].items()})
        log("seed ok", ok_seed)
        if not ok_seed:
            return final(dict(ok=False, step="export", why="seed sha mismatch", seed=rec["seed"]))
    else:
        rec["seed"] = dict(ok=True, skipped="the folder already holds this cfg's chain")
    st, hist = N.drive_chain("export", p, EXT_RID, F_HERO_END, log, "export")
    rec["chain"] = dict(state=st, history=hist)
    if not st["complete"]:
        return final(dict(ok=False, step="export", why="the extension did not reach frame %d (%s; %s)" % (F_HERO_END, st["state"], st.get("stop")),
                          chain=rec["chain"]))
    rc = RS.compare(p)
    s = N.strict_compare(c, rc)
    rec["compare"] = s
    log("compare strict ok", s["ok"], json.dumps({k: s[k] for k in ("hf_eta", "r2_sdf", "r4_sdf", "r5_bytes_equal", "volcorr_equal")}))
    v = validate_ext(list(range(EXT_F0, F_HERO_END + 1)))
    rec["validation"] = v
    j = junction_check()
    rec["junction"] = j
    hooks = [N.jtry(q) for q in sorted(glob.glob(EXT_DIR + "/hook_c*.json"))]
    rec["hooks"] = [dict((k, h.get(k)) for k in ("n", "errors", "export_s", "setframe_calls")) for h in hooks if h]
    rec["ok"] = bool(s["ok"] and v["ok"] and j["ok"] and not any((h or {}).get("errors") for h in hooks))
    rec["seconds"] = round(time.time() - t0, 1)
    rec["tags"] = dict(compare="measured (record to record)", alignment="measured", junction="measured")
    N.jdump(rec, EXT_JSON)
    # a complete chain whose checks fail is NOT resumable (a relaunch would only repeat the same compare): the launcher matches this text
    why = None if rec["ok"] else ("export check failed (not resumable): strict compare %s, R1 alignment %s, junction %s, hook errors %s" % (
        s["ok"], v["ok"], j["ok"], any((h or {}).get("errors") for h in hooks)))
    return final(dict(ok=rec["ok"], step="export", why=why, export=rel(EXT_JSON), compare_ok=s["ok"], validation_ok=v["ok"], junction_ok=j["ok"],
                      gb=v.get("gb"), seconds=rec["seconds"]))


# ====================================================================== union target folder
def union_plan():
    C = N.C_()
    items = []
    for f in range(N.CKPT, F_HERO_END + 1):
        src = (N.EXPORT_DIR if f <= N.F_END else EXT_DIR) + "/x_%05d.npz" % f
        items.append(("x_%05d.npz" % f, src))
    for f in range(N.F0, F_HERO_END + 2):
        items.append(("vd/vd_%05d.txt" % f, C.DFGBV_RUN + "/volcorr/vd_%05d.txt" % f))
    return items


def cmd_union(sim=False):
    t0 = time.time()
    items = union_plan()
    ex, ee = N.jtry(N.EXPORT_JSON) or {}, N.jtry(EXT_JSON) or {}
    pre = dict(registered_export_ok=bool(ex.get("ok")), extension_ok=bool(ee.get("ok")))
    if sim:
        miss = [s for _, s in items if not os.path.exists(s)]
        return final(dict(ok=True, step="union", simulate=True, pre=pre, n_items=len(items), would_write=rel(UNION_DIR),
                          sources_missing_now=len(miss), first_missing=[rel(m) for m in miss[:3]],
                          note="the extension's x_01658-x_03001 exist only after 'export'"))
    if not all(pre.values()):
        return final(dict(ok=False, step="union", why="preconditions: %s" % ", ".join(k for k, v in pre.items() if not v), pre=pre))
    rows, bad, how_n = [], [], {"link": 0, "copy": 0, "kept": 0}
    vd_cmp = []
    for name, src in items:
        dst = UNION_DIR + "/" + name
        if not os.path.exists(src):
            bad.append("missing source %s" % rel(src)); continue
        hs = sha(src)
        if os.path.exists(dst) and sha(dst) == hs:
            how_n["kept"] += 1
        else:
            N.guard(dst)
            if os.path.exists(dst):
                os.remove(dst)
            try:
                os.link(src, dst); how_n["link"] += 1
            except OSError:
                shutil.copyfile(src, dst); how_n["copy"] += 1
        hd = sha(dst)
        if hd != hs:
            bad.append("sha differs %s" % name)
        rows.append(dict(name=name, src=rel(src), sha256=hd, bytes=os.path.getsize(dst)))
        if name.startswith("vd/"):
            for other in (N.EXPORT_RD, EXT_RD):
                q = other + "/volcorr/" + os.path.basename(name)
                if os.path.exists(q) and sha(q) != hs:
                    vd_cmp.append("%s differs in %s" % (os.path.basename(name), rel(other)))
            # the files C2 itself read (its rep_dir = the registered export's vd copy, frames 1057-1658): byte-equal REQUIRED (review 2026-10-19)
            f_vd = int(os.path.basename(name)[3:8])
            if f_vd <= N.F_END + 1:
                q = N.REPLAY_DIR + "/" + os.path.basename(name)
                if not os.path.exists(q) or sha(q) != hs:
                    vd_cmp.append("%s differs from (or is missing in) C2's rep_dir %s" % (os.path.basename(name), rel(N.REPLAY_DIR)))
    rec = dict(date=now(), tool=SELF_REL, tool_sha256=sha(SELF), label=LABEL, dir=rel(UNION_DIR), n=len(rows), how=how_n, bad=bad[:20],
               vd_differs_from_export_runs=vd_cmp[:20], files=rows,
               rule=("x_01056-x_01657 = %s (byte-identical), x_01658-x_03001 = %s, vd_01057-vd_03002 = the judged run's volcorr (byte-equal to both "
                     "export runs' own where present, and vd_01057-vd_01658 byte-equal to C2's own rep_dir %s)" % (rel(N.EXPORT_DIR), rel(EXT_DIR),
                                                                                                                 rel(N.REPLAY_DIR))),
               ok=bool(not bad and not vd_cmp and len(rows) == len(items)), seconds=round(time.time() - t0, 1))
    N.jdump(rec, UNION_JSON)
    return final(dict(ok=rec["ok"], step="union", union=rel(UNION_JSON), n=len(rows), how=how_n, bad=bad[:5], vd_differs=vd_cmp[:5], seconds=rec["seconds"]))


def union_state(full=True):
    u = N.jtry(UNION_JSON) or {}
    why = []
    if not u.get("ok"):
        why.append("union.json missing or not ok")
    else:
        names = {r["name"]: r for r in u.get("files") or []}
        want = [n for n, _ in union_plan()]
        miss = [n for n in want if n not in names]
        if miss:
            why.append("union.json lacks %d files (first %s)" % (len(miss), miss[:3]))
        chk = want if full else want[::97]
        badf = [n for n in chk if n in names and sha(UNION_DIR + "/" + n) != names[n]["sha256"]]
        if badf:
            why.append("%d union files changed after union.json (first %s)" % (len(badf), badf[:3]))
    return dict(ok=not why, why="; ".join(why) or None, file=rel(UNION_JSON), sha256=sha(UNION_JSON))


# ====================================================================== (2) the C2H launch cfg and run
def dpaths(a, b, pre=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            p = (pre + "." + k) if pre else k
            if k not in a:
                out.append(p)
            elif k not in b:
                out.append(p)
            else:
                out += dpaths(a[k], b[k], p)
        return out
    return [] if N.canon(a) == N.canon(b) else [pre]


def allowed(path):
    return any(path == k or path.startswith(k + ".") for k in HERO_KEYS)


def c2h_cfg(for_check=False):
    L0 = N.jload(C2_LAUNCH)
    L = copy.deepcopy(L0)
    L.update(run_id=RID_C2H, f_end=F_HERO_END, t_end_s=(F_HERO_END - 1) / FPS, max_hours=C2H_MAX_HOURS,
             pstats_frames=[int(L0["f_start"]), int(L0["f_start"]) + 1, F_HERO_END])
    L["records"]["r5"]["every"] = 1
    L["records"]["windows"] = [list(HERO_WINDOW)]
    L["parms"]["tgt_dir"] = UNION_DIR
    L["parms"]["rep_dir"] = UNION_VD
    if isinstance(L.get("nest"), dict) and "records" in L["nest"]:
        L["nest"]["records"] = ("hf / r2 every frame, r4 every 3rd frame (C2's phase) and r5 (surface) EVERY frame in the window [48, 125] s; "
                                "gauges as C2 (C2H, Q90; label only)")
    L["case"].update(name="FLIP55_C2H_hero_nest_x180y60_dp0p25_t125", stage="hero", judged=False,
                     role="C2H: the dp 0.25 m nest of DFG-2B-V continued to 125 s as the hero (Q90) - OUT-OF-RULE trial, not judged",
                     hero=dict(label=LABEL, label_ja=LABEL_JA, amendment=AMEND_ID, user_words_q90=USER_WORDS, extends=AMEND_DEV_ID))
    L["note"] = ("FLIP55 C2H (%s, 2026-10-19, Q90): C2's launch cfg (%s) continued to frame %d with the surface every frame in 48-125 s and the "
                 "union target; scene / tools / launch parms = C2's | %s" % (SELF_REL, rel(C2_LAUNCH), F_HERO_END, LABEL))
    L["f55"].update(option="C2H", stage="hero",
                    c2h=dict(label=LABEL, amendment=AMEND_ID, tool=SELF_REL, tool_sha256=sha(SELF), base_launch_cfg=rel(C2_LAUNCH), base_launch_cfg_sha256=sha(C2_LAUNCH), hero_keys=list(HERO_KEYS),
                             hero_keys_why=HERO_KEYS_WHY, union=rel(UNION_JSON), union_sha256=sha(UNION_JSON)))
    # the precheck: C2's own checks (as launched) + the C2H checks
    ck = {}
    pc0 = L0.get("precheck") or {}
    ck["c2_precheck_was_ok"] = bool(pc0.get("ok"))
    ck["c2_complete"] = bool(c2_state()["complete"])
    diff = dpaths(L0, L)
    bad = [p for p in diff if not allowed(p)]
    ck["c2h_only_hero_keys_differ"] = bool(not bad)
    ck["nest_scene_as_c2"] = bool(L["f55"].get("nest_hip_sha256") == sha(N.NEST_HIP))
    ck["build_check_as_c2"] = bool(L["f55"].get("build_check_sha256") == sha(N.NEST_BUILD_CHECK))
    ck["nest_tools_as_c2"] = bool(L0["f55"].get("tool_sha256") == sha(N.SELF) and L0["f55"].get("x55_sha256") == sha(N.BUILD_TOOL)
                                  and L["f55"].get("tool_sha256") == L0["f55"].get("tool_sha256"))
    cs = N.calib_state()
    ck["calib_as_c2"] = bool(cs["ok"] and abs(float(L["parms"]["init_lvl_m"]) - float(cs["step_m"])) < 1e-12)
    ck["records_hero"] = bool(L["records"]["r5"]["every"] == 1 and L["records"]["windows"] == [HERO_WINDOW] and int(L["records"]["r4"]["every"]) == 3
                              and int(L["records"]["r4"]["every"]) == int(L0["records"]["r4"]["every"]))
    ck["frames"] = bool(L["f_start"] == L0["f_start"] == N.F0 and L["f_end"] == F_HERO_END)
    ck["out_root_FLIP55"] = bool(N.under(L["out_root"], B55))
    ck["no_temp_paths"] = N.no_temp(L)
    if not for_check:
        ck["union_ok"] = bool(union_state()["ok"])
        ck["c2h_tie"] = bool(c2h_tie()["ok"])
    L["precheck"] = dict(ok=bool(all(ck.values())), checks=ck, reason=None if all(ck.values()) else "failed: " + ", ".join(k for k, v in ck.items() if not v),
                         differs_from_c2=diff, not_allowed=bad, c2_precheck=dict(ok=pc0.get("ok"), date=pc0.get("date")),
                         kind="F55 C2H launch precheck (C2's launch cfg + HERO_KEYS)", date=now(), label=LABEL)
    return L, L0


def cmd_run(sim=False, o=None):
    o = o or {}
    L, L0 = c2h_cfg(for_check=sim)
    pc = L["precheck"]
    if sim:
        t = c2h_tie()
        out = dict(ok=bool(pc["ok"]), step="run", option="C2H", simulate=True, precheck=pc, run_dir=rel(RD_C2H), launch_cfg=rel(C2H_LAUNCH),
                   c2h_tie=dict(ok=t["ok"], why=t["why"]), slot_need_gb=N.need_of("C2"),
                   would_run="py -3.10 -B %s chain nest %s (patched g52b3_chain.py; hython %s hyrun -> g52b3_run.py with HIP = %s), frames %d-%d" % (
                       N.SELF, C2H_LAUNCH, N.SELF, rel(N.NEST_HIP), L["f_start"], L["f_end"]),
                   note="c2h_tie and union_ok become true after 'register' and 'export' + 'union'")
        N.jdump(dict(out, cfg=L), SIM_DIR + "/run_C2H_plan.json")
        return final(out)
    t = c2h_tie()
    if not t["ok"]:
        return final(dict(ok=False, step="run", option="C2H", why="C2H is not run (c2h_tie): %s" % "; ".join(t["why"]), tie=t))
    if not pc["ok"]:
        return final(dict(ok=False, step="run", option="C2H", why="launch precheck: %s" % pc["reason"], not_allowed=pc.get("not_allowed")))
    if not N.chain_alive(RID_C2H):
        eg = N.entry_guard("run C2H", "C2", wait_min=float(o.get("wait-min", N.WAIT_MIN)))
        if not eg["ok"]:
            return final(dict(ok=False, step="run", option="C2H", why="entry guard: %s" % eg["why"], guard=eg))
    p, how = N.write_cfg_once(L, C2H_LAUNCH)
    log = logger("f55_c2h_run.log")
    log("launch cfg", rel(p), how, "| under", AMEND_ID)
    st, hist = N.drive_chain("nest", p, RID_C2H, F_HERO_END, log, "C2")
    if st["complete"]:
        N.jdump(dict(label=LABEL, label_ja=LABEL_JA, amendment=AMEND_ID, user_words_q90=USER_WORDS, run=rel(RD_C2H), frames_done=st["frames_done"],
                     date=now(), tie=dict(ok=t["ok"], amendment_date=t.get("amendment_date"))), RD_C2H + "/f55/C2H_Q90.json")
    return final(dict(ok=bool(st["complete"]), step="run", option="C2H", run_dir=rel(RD_C2H), state=st["state"], frames_done=st["frames_done"],
                      stop=st.get("stop"), history=hist))


# ====================================================================== identity: C2H vs C2 on group 1
def cmd_identity(sim=False):
    import numpy as np
    t0 = time.time()
    if sim:
        return final(dict(ok=True, step="identity", simulate=True, would_compare=dict(src=rel(RD_C2), dst=rel(RD_C2H), frames=[N.F0, N.F_END],
                                                                                    records="hf eta, r2 sdf/u/w, r4 sdf, r5 surf (C2's 113 frames), volcorr rows"),
                          c2h_complete=c2h_state()["complete"]))
    if not c2h_state()["complete"]:
        return final(dict(ok=False, step="identity", why="C2H is not complete"))
    RS = N.restart_module()                                   # g49_restart unchanged (its readers only)
    f0, f1 = N.F0, N.F_END
    out = dict(date=now(), tool=SELF_REL, label=LABEL, src=rel(RD_C2), dst=rel(RD_C2H), frames=[f0, f1],
               rule="same frame numbers; a frame present in two launches is read from the later launch (g49_restart.index)")
    allbit = True
    for kind, keys in (("hf", ("eta",)), ("r2", ("sdf", "u", "w")), ("r4", ("sdf",))):
        wa, wb = RS.index(RD_C2, kind, f0, f1), RS.index(RD_C2H, kind, f0, f1)
        fr = sorted(set(wa) & set(wb))
        res = dict(n_c2=len(wa), n_c2h=len(wb), n_common=len(fr), c2_frames_missing_in_c2h=len(set(wa) - set(wb)))
        # no vacuous identity (review 2026-10-19): every C2 frame of this record must be in C2H
        allbit = allbit and len(wa) > 0 and res["c2_frames_missing_in_c2h"] == 0
        if fr:
            A, B = RS.fetch(wa, keys, fr), RS.fetch(wb, keys, fr)
            for k_ in keys:
                rw = []
                for f in fr:
                    if f in A[k_] and f in B[k_]:
                        s_ = RS.diff_stats(A[k_][f], B[k_][f]); s_["frame"] = f; rw.append(s_)
                res[k_] = RS.summarize(rw)
                allbit = allbit and res[k_].get("n_frames") == len(fr) and res[k_].get("n_bit_equal") == res[k_].get("n_frames")
        out[kind] = res
    sa = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(RD_C2 + "/surf/s_*.gw45s"))
    rows = []
    for f in sa:
        q = RD_C2H + "/surf/s_%05d.gw45s" % f
        if os.path.exists(q):
            r = RS.surf_compare(RD_C2 + "/surf/s_%05d.gw45s" % f, q); r["frame"] = f; rows.append(r)
    out["r5"] = dict(n_c2=len(sa), n_common=len(rows), n_bytes_equal=int(sum(r["bytes_equal"] for r in rows)),
                     max_m=float(max([r["max_m"] for r in rows] or [0.0])), not_equal_first=[r for r in rows if not r["bytes_equal"]][:5])
    allbit = allbit and len(sa) > 0 and out["r5"]["n_common"] == len(sa) and out["r5"]["n_bytes_equal"] == len(sa)

    def vrows(rd):
        d = {}
        p = rd + "/volcorr/state.jsonl"
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8"):
                try:
                    q = json.loads(ln)
                    if f0 <= int(q["f"]) <= f1:
                        d[int(q["f"])] = q
                except Exception:
                    pass
        return d
    va, vb = vrows(RD_C2), vrows(RD_C2H)
    fr = sorted(set(va) & set(vb))
    neq = [f for f in fr if N.canon({k: v for k, v in va[f].items() if k != "t_wall"}) != N.canon({k: v for k, v in vb[f].items() if k != "t_wall"})]
    out["volcorr"] = dict(n_c2=len(va), n_common=len(fr), n_equal=len(fr) - len(neq), not_equal_first=neq[:10])
    allbit = allbit and len(fr) == len(va)                    # every C2 volcorr row must be in C2H (no vacuous identity)
    # report only: the nest's water volume against the parent's on EVERY C2H frame (GN3's column rule; its 2 % gate was registered for group 1)
    C = N.C_()
    HP, HN = N.HF(N.DFGBV_RUN), N.HF(RD_C2H)
    fp, fn = set(HP.frames()), set(HN.frames())
    vrows = []
    for f in range(N.F0, F_HERO_END + 1):
        if f in fp and f in fn:
            ep, mp = HP.get(f); en, mn = HN.get(f)
            vp_, _, _ = N.column_volume(np, ep, mp, C.bed_z); vn_, _, _ = N.column_volume(np, en, mn, C.bed_z)
            vrows.append((f, vn_ / vp_ - 1.0))
    wins = {1: (55.0, 69.0), 2: (83.0, 97.0), 3: (111.0, 125.0)}
    per = {}
    for g, (a, b) in wins.items():
        rr = [r for f, r in vrows if a - 1e-9 <= (f - 1) / FPS <= b + 1e-9]
        per[str(g)] = dict(max_abs_rel=float(max(abs(r) for r in rr)) if rr else None, n=len(rr))
    worst = max(vrows, key=lambda x: abs(x[1])) if vrows else (None, None)
    out["volume_report"] = dict(rule=("GN3's column volume (hf, x 180-356 m, y 0-60 m, max(eta - bed, 0)) of C2H vs the judged parent on every frame "
                                      "1057-3001; REPORT ONLY (GN3's +-2 % gate was registered for group 1 of C2ID)"),
                                n=len(vrows), worst=dict(frame=worst[0], rel=worst[1]), n_outside_2pct=int(sum(abs(r) > 0.02 for _, r in vrows)),
                                per_group_window=per, series_every_24=[[f, round(r, 5)] for f, r in vrows[::24]], tag="measured")
    hf_max = (out.get("hf") or {}).get("eta", {}).get("max_of_max")
    out["all_bit_identical"] = bool(allbit and not neq)
    out["summary"] = ("C2H reproduces C2 bit for bit on group 1" if out["all_bit_identical"] else
                      "C2H group 1 differs from C2: hf max %s m, r2 sdf max %s, r5 max %s m (C2H's own numbers are used for the hero)" % (
                          None if hf_max is None else round(hf_max, 4), (out.get("r2") or {}).get("sdf", {}).get("max_of_max"), out["r5"]["max_m"]))
    out["seconds"] = round(time.time() - t0, 1)
    out["tags"] = dict(all="measured (record to record)")
    N.jdump(out, IDENT_JSON)
    return final(dict(ok=True, step="identity", identity=rel(IDENT_JSON), all_bit_identical=out["all_bit_identical"], summary=out["summary"],
                      hf_max_m=hf_max, r5=dict((k, out["r5"][k]) for k in ("n_common", "n_bytes_equal", "max_m")), volcorr=out["volcorr"]["n_equal"],
                      volume_report=dict((k, out["volume_report"][k]) for k in ("worst", "n_outside_2pct", "per_group_window")), seconds=out["seconds"]))


# ====================================================================== status / selftest
def cmd_status():
    t = c2h_tie()
    return final(dict(ok=True, step="status", tie_ok=t["ok"], tie_why=t["why"], c2=c2_state(), export3001=dict(json=rel(EXT_JSON), ok=(N.jtry(EXT_JSON) or {}).get("ok"),
                      run=N.run_state(EXT_RD, F_HERO_END)), union=union_state(full=False), c2h=c2h_state(),
                      identity=(N.jtry(IDENT_JSON) or {}).get("summary"), tools=tool_shas()))


def selftest():
    ck, info = {}, {}
    ck["c2dev_sha"] = sha(C2DEV) == C2DEV_SHA
    ck["nest_tools_sha"] = all(sha(REPO + "/" + p) == v for p, v in NEST_TOOLS_SHA.items())
    src, counts = N.chain_source()
    ck["chain_patch_counts"] = bool(all(v == 1 for v in counts.values()))
    C = N.C_()
    ck["rids_distinct"] = bool(len({EXT_RID, UNION_RID, RID_C2H, RID_C2, N.EXPORT_RID}) == 5 and RID_C2 == C.RID["C2"] and N.EXPORT_RID == C.RID["C2P"])
    ck["ext_ckpt_exists"] = os.path.exists(C.DFGBV_RUN + "/ckpt/v.%04d.sim" % EXT_CKPT)
    ck["ext_vd_to_3002"] = all(os.path.exists(C.DFGBV_RUN + "/volcorr/vd_%05d.txt" % f) for f in (EXT_CKPT, EXT_F0, F_HERO_END, F_HERO_END + 1))
    c, c0 = ext_cfg()
    sd = N.source_diff(c0, c)
    info["ext_precheck"] = dict(ok=c["precheck"]["ok"], reason=c["precheck"].get("reason"), replaced=list((c["precheck"].get("replaced") or {}).keys()))
    ck["ext_source_diff_ok"] = bool(sd["ok"])
    ck["ext_spec_boxes_as_registered"] = bool(N.canon(ext_spec()["boxes"]) == N.canon(N.export_spec()["boxes"]))
    ck["ext_no_temp"] = N.no_temp(c)
    L, L0 = c2h_cfg(for_check=True)
    info["c2h_differs_from_c2"] = L["precheck"]["differs_from_c2"]
    ck["c2h_only_hero_keys"] = bool(L["precheck"]["checks"]["c2h_only_hero_keys_differ"])
    ck["c2h_scene_tools_as_c2"] = bool(L["precheck"]["checks"]["nest_scene_as_c2"] and L["precheck"]["checks"]["build_check_as_c2"]
                                       and L["precheck"]["checks"]["nest_tools_as_c2"])
    ck["c2h_records"] = bool(L["precheck"]["checks"]["records_hero"])
    ck["c2h_parms_as_c2"] = bool(all(N.canon(L["parms"][k]) == N.canon(L0["parms"][k]) for k in L0["parms"] if k not in ("tgt_dir", "rep_dir")))
    ck["c2h_band_lin_init"] = bool(float(L["parms"]["band_lin"]) == 1.0 and float(L["parms"]["init_src"]) == 0.0
                                   and abs(float(L["parms"]["init_lvl_m"]) - float((N.jtry(N.CALIB_JSON) or {}).get("lvl_step_m") or -9)) < 1e-12)
    up = union_plan()
    ck["union_plan_complete"] = bool(len(up) == (F_HERO_END - N.CKPT + 1) + (F_HERO_END + 2 - N.F0))
    ck["union_registered_part_present"] = all(os.path.exists(s) for n, s in up if n.startswith("x_") and int(n[2:7]) <= N.F_END)
    # the union's vd_01057-vd_01658 (the judged run's) are byte-equal to what C2 read (its rep_dir), so C2H's group-1 inputs = C2's
    ck["union_vd_equals_c2_rep_dir"] = all(os.path.exists(N.REPLAY_DIR + "/vd_%05d.txt" % f) and
                                           open(N.REPLAY_DIR + "/vd_%05d.txt" % f, "rb").read() == open(C.DFGBV_RUN + "/volcorr/vd_%05d.txt" % f, "rb").read()
                                           for f in range(N.F0, N.F_END + 2))
    # the frames of C2's r4 / r5 records are a subset of C2H's (runner rule: (f - 1) % every == 0 inside the windows)
    every4, every5 = int(L["records"]["r4"]["every"]), int(L["records"]["r5"]["every"])
    inwin = lambda f, W: any(a - 1e-9 <= (f - 1) / FPS <= b + 1e-9 for a, b in W)
    c2_r4 = [f for f in range(N.F0, N.F_END + 1) if (f - 1) % int(L0["records"]["r4"]["every"]) == 0 and inwin(f, L0["records"]["windows"])]
    c2h_r4 = set(f for f in range(N.F0, F_HERO_END + 1) if (f - 1) % every4 == 0 and inwin(f, L["records"]["windows"]))
    c2h_r5 = set(f for f in range(N.F0, F_HERO_END + 1) if (f - 1) % every5 == 0 and inwin(f, L["records"]["windows"]))
    ck["c2_r4_frames_subset"] = bool(c2_r4 and set(c2_r4) <= c2h_r4)
    ck["c2h_surface_every_frame_1153_3001"] = bool(set(range(1153, 3002)) <= c2h_r5)
    ck["label_everywhere"] = bool(LABEL in c["note"] and LABEL in L["note"] and L["case"]["hero"]["label"] == LABEL)
    t = c2h_tie()
    info["tie_now"] = dict(ok=t["ok"], why=t["why"][:8])
    info["c2_r4_frames"] = [c2_r4[0], c2_r4[-1], len(c2_r4)] if c2_r4 else None
    res = dict(ok=bool(all(ck.values())), step="selftest", checks=ck, info=info)
    return final(res)


def cmd_check():
    t = c2h_tie()
    return final(dict(t, step="check"))


def main(argv):
    try:
        load()
    except (SystemExit, Exception) as e:
        why = str(e.code) if isinstance(e, SystemExit) else "%s: %s" % (type(e).__name__, e)
        return final(dict(ok=False, step=(argv[0] if argv else None), why=why[:600]))
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    pos, o = N.opts(argv[1:])
    sim = "simulate" in o
    try:
        if cmd == "check":
            return cmd_check()
        if cmd == "register":
            return cmd_register("dry" in o)
        if cmd == "export":
            return cmd_export(sim, o)
        if cmd == "union":
            return cmd_union(sim)
        if cmd == "run":
            return cmd_run(sim, o)
        if cmd == "identity":
            return cmd_identity(sim)
        if cmd == "status":
            return cmd_status()
        if cmd == "selftest":
            return selftest()
    except KeyboardInterrupt:
        raise
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            raise
        return final(dict(ok=False, step=cmd, why=str(e.code)[:800]))
    except Exception as e:
        import traceback
        return final(dict(ok=False, step=cmd, why="%s: %s" % (type(e).__name__, str(e)[:600]), traceback=traceback.format_exc()[-1500:]))
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
