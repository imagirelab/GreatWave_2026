# -*- coding: utf-8 -*-
"""FLIP44：2 回目の直し（record_ja.md §3.2、x44_fix2_tests.py）の確かめ。直していない者が書いた（py -3.10）。
流体の計算（hython）は走らせない。自分の優先度を「通常より下」にし、子の py も「通常より下」で起こす。
書くのは Unity/Build/FLIP44/check/fx2/ と check/c44_fix2_check.json だけ。ほかのファイルは読むだけ。ファイルは消さない
（途中保存を消す決まりの試しは、消す代わりに試しのフォルダーの中の _moved/ へ動かす）。
  k0 ：凍結した 4 つの SHA-256、runs/ready の作り直し、runs/・plan/ の中身、hython、G: の空き
  k1 ：並びの dry-run（標準出力 cp932）：最初の夜の道、--from・--only の全部の段（状態なし・確かめなし・確かめあり）、知らない名前、
       下見 3 本目の道（入る・外れる）、RP の古い途中保存
  k2 ：並びの関数を直に呼ぶ（chain を差し替え、解析・風の判定・表は本当に走らせる）：下見 1 の計算が落ちた時、下見 1 の解析が止まった時、
       風の計算の打ち切り（cut）・唇の先で止まった（online_tip）・前の段がない、RP の外れと走らせ直し
  k3 ：計算の中の着水の読み（g44_online.TouchdownWatch）を、今ある記録 8 本（FLIP42 R1b・R2・R3・R3d・R3m・R4d・R5p、煙の試し S8）と
       巻かない記録 2 本（FLIP42 R1、煙の試し S9_v2）にかけ、自分で書いた読み（skimage の等高線・scipy の塊）と比べる
  k4 ：途中保存の残し方（g44_ckpt.after_launch）を、g44_hours の起動の真似の上で本当に動かす（消す代わりに動かす）。続きの元・確かめた始め・
       前からある物・書きかけ・やり直しの道、形の本番の巻き始めが下見とずれた時に風の計算の始めが残るか
  k5 ：置き場所の見込みと、並びの始めの置き場所の確かめ
  k6 ：直した側の h2・h3（hython）の記録を読み直す
出力：Unity/Build/FLIP44/check/c44_fix2_check.json（試しごとに足す）
"""
import sys, os, json, glob, shutil, subprocess, time, ctypes, hashlib, types, math
from ctypes import wintypes
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip44"
B44 = REPO + "/Unity/Build/FLIP44"
R42 = REPO + "/Unity/Build/FLIP42/runs"
FXR = "check/fx2"
FX = B44 + "/" + FXR
RES = B44 + "/check/c44_fix2_check.json"
FPS = 24.0
AG = "c44_fix2_check の試し（本番ではない）"
sys.path.insert(0, TOOLS)


def lower_self():
    k = ctypes.WinDLL("kernel32", use_last_error=True)

    class PPTS(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetPriorityClass.argtypes = [wintypes.HANDLE]
    h = k.GetCurrentProcess()
    s = PPTS(1, 0x1, 0x0)
    r1 = bool(k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s)))
    r2 = bool(k.SetPriorityClass(h, 0x4000))
    return dict(power_throttling_off=r1, below_normal=r2, priority_class=hex(k.GetPriorityClass(h)))


def save(key, val):
    d = json.load(open(RES, encoding="utf8")) if os.path.exists(RES) else {}
    d[key] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), **val)
    json.dump(d, open(RES, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


def jl(p):
    return json.load(open(p, encoding="utf8"))


def jw(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


def py(args, enc="utf-8"):
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env["PYTHONIOENCODING"] = enc
    r = subprocess.run([sys.executable] + args, cwd=TOOLS, capture_output=True, env=env, creationflags=0x00004000)
    return r.returncode, r.stdout.decode(enc, errors="replace"), r.stderr.decode(enc, errors="replace")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


def snap(d):
    """フォルダーの中身（名前・大きさ・時刻）。"""
    out = {}
    for p in glob.glob(d + "/**", recursive=True):
        if os.path.isfile(p):
            out[os.path.relpath(p, d).replace("\\", "/")] = [os.path.getsize(p), round(os.path.getmtime(p), 2)]
    return out


# ================================================================== k0
def t_k0():
    fz = jl(B44 + "/plan/plan_frozen.json")
    shas = {f["path"]: (sha(REPO + "/" + f["path"]) == f["sha256"]) for f in fz["frozen"]}
    import g44_cfg as C
    same = {}
    for name, kind, kw in (("PR1", "PR1", {}), ("PR2", "PR2", {}), ("RP_reef500", "RP", {"aim": "reef"}), ("RP_flat592", "RP", {"aim": "flat"})):
        c = C.kind_cfg(kind, "RP" if kind == "RP" else kind, dict(kw))
        same[name] = json.dumps(c, ensure_ascii=False, indent=1) == open(B44 + "/runs/ready/%s.json" % name, encoding="utf8").read().strip()
    runs_files = sorted(os.listdir(B44 + "/runs"))
    plan_files = {k: v for k, v in snap(B44 + "/plan").items()}
    out = dict(frozen_sha_same=shas, ready_same=same, runs_dir=runs_files, ready_mtimes={k: v[1] for k, v in snap(B44 + "/runs/ready").items()},
               plan_files=plan_files, hython=hython_running(), free_gib=shutil.disk_usage("G:/").free / 2**30,
               report_dir_exists=os.path.isdir(B44 + "/report"))
    save("k0", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:3000])


# ================================================================== k1：並びの dry-run
def q(root, args, enc="cp932"):
    rc, so, se = py(["g44_queue.py", "--agreed", AG, "--root", root, "--dry-run"] + args, enc=enc)
    txt = (so + se).strip()
    D = B44 + "/" + root
    rd = lambda n: open(D + "/" + n, encoding="utf8").read().strip().splitlines() if os.path.exists(D + "/" + n) else []
    return dict(args=args, rc=rc, traceback=("Traceback" in txt), tail=txt.splitlines()[-2:], stop=(rd("QUEUE_STOP.txt") or [None])[-1],
                pause=rd("QUEUE_PAUSE.txt")[-2:], n_report=len(rd("QUEUE_REPORT.txt")))


def r3_ana():
    return jl(B44 + "/check/ana44_R3.json")


def failing(a):
    f = json.loads(json.dumps(a))
    f["selection_a"]["pass_"] = False; f["selection_a"]["c1_onset_in_window"] = False; f["onset"]["xc_rel"] = 600.0
    return f


def t_k1():
    TAG = time.strftime("%H%M%S")
    res = {}
    plan_before = snap(B44 + "/plan")
    # ---------------- (A) 最初の夜の道（下見 1・2 とも入る）と、その後の言葉
    R = FXR + "/k1a_" + TAG; D = B44 + "/" + R
    a = r3_ana()
    for k in ("PR1", "PR2"):
        jw(D + "/%s/ana.json" % k, a)
    steps = []

    def st(name, args, want, prep=None):
        if prep:
            prep()
        r = q(R, args); r.update(name=name, want=want, ok=bool(r["rc"] == want and not r["traceback"]))
        steps.append(r); print("k1a", name, r["rc"], want, r["ok"], (r["stop"] or "")[-120:])
        return r
    st("night1_default", [], 3)
    S1 = jl(D + "/queue_state.json")
    sel_md = open(D + "/SELECT_RESULT_ja.md", encoding="utf8").read() if os.path.exists(D + "/SELECT_RESULT_ja.md") else ""
    disk_md = os.path.exists(D + "/DISK_PLAN_ja.md")
    pr1c = jl(D + "/PR1/cfg_queue.json"); ready = jl(B44 + "/runs/ready/PR1.json")
    diff_keys = sorted(k for k in set(pr1c) | set(ready) if pr1c.get(k) != ready.get(k))
    st("unconf_from_SH", ["--from", "SH"], 3)
    st("unconf_only_SH", ["--only", "SH"], 3)
    st("unconf_from_PR3", ["--from", "PR3"], 3)
    st("unconf_from_B35S", ["--from", "B35S"], 2)
    st("unconf_only_B45S", ["--only", "B45S"], 2)
    st("unconf_from_RP", ["--from", "RP"], 2)
    st("unconf_only_RP", ["--only", "RP"], 2)
    st("unconf_only_TABLE", ["--only", "TABLE"], 2)
    st("confirm_wrong_choice", ["--confirm-select", "PR2"], 1)
    st("confirm_pr3_without_pr3", ["--confirm-pr3"], 1)
    st("confirm_right_choice_runs_to_SH_end", ["--confirm-select", "PR1"], 0)
    S2 = jl(D + "/queue_state.json")
    shc = jl(D + "/SH/cfg_queue.json") if os.path.exists(D + "/SH/cfg_queue.json") else None
    st("conf_noSH_from_B35S", ["--from", "B35S"], 2)
    st("conf_noSH_only_B45S", ["--only", "B45S"], 2)
    st("conf_noSH_only_TABLE", ["--only", "TABLE"], 2)
    st("conf_only_RP_dry", ["--only", "RP"], 0)
    rpc = jl(D + "/RP/cfg_queue.json") if os.path.exists(D + "/RP/cfg_queue.json") else None
    # 形の本番の役（R3 の ana）と途中保存（空のファイル）を置いて、形の本番から最後まで
    t_on = a["onset"]["t"]

    def prep_sh():
        jw(D + "/SH/ana.json", a)
        os.makedirs(D + "/SH/ckpt", exist_ok=True)
        for k in (3240, 3480, 3576, 3600, 3624, 3648, 3672):
            open(D + "/SH/ckpt/v.%04d.sim" % k, "wb").close()
    st("conf_from_SH_to_end", ["--from", "SH"], 0, prep_sh)
    bc = jl(D + "/B35S/cfg_queue.json") if os.path.exists(D + "/B35S/cfg_queue.json") else None
    want_ck = max(k for k in (3240, 3480, 3576, 3600, 3624, 3648, 3672) if (k - 1) / FPS < t_on - 3.0)
    report_a = open(D + "/QUEUE_REPORT.txt", encoding="utf8").read().strip().splitlines() if os.path.exists(D + "/QUEUE_REPORT.txt") else []
    # 最初の夜の言葉をもう一度打つと（確かめの後に打ち間違えた時）
    st("retype_night1_after_confirm", [], 3)
    S3 = jl(D + "/queue_state.json")
    st("bad_from_name", ["--from", "XYZ"], 1)
    st("bad_from_missing", ["--from"], 1)
    st("bad_only_lower", ["--only", "rp"], 1)
    st("bad_confirm_PR4", ["--confirm-select", "PR4"], 1)
    rc, so, se = py(["g44_queue.py", "--root", R, "--dry-run"], enc="cp932")
    steps.append(dict(name="no_agreed", rc=rc, want=1, ok=bool(rc == 1 and "Traceback" not in so + se)))
    res["A"] = dict(root=R, steps=steps, state_after_night1=S1.get("select"), select_md_has_confirm=("--confirm-select PR1" in sel_md),
                    disk_plan_written=disk_md, PR1_cfg_vs_ready_diff_keys=diff_keys,
                    state_after_confirm=S2.get("select"),
                    SH_cfg=dict(f_w=shc["case"]["f_w"], ckpt_every=shc["ckpt_every"], lock=shc.get("ckpt_lock_until"), keep=shc.get("ckpt_keep"),
                                max_hours=shc.get("max_hours")) if shc else None,
                    RP_cfg=dict(prog=rpc["case"].get("prog"), f_end=rpc["f_end"], keep=(rpc.get("ckpt_keep") or {}).get("mode")) if rpc else None,
                    B35S_cfg=dict(from_ckpt=bc["from_ckpt"], f_start=bc["f_start"], f_end=bc["f_end"], max_hours=bc["max_hours"],
                                  stop_touchdown=bc["stop_touchdown"], wind_t0=bc["parms"]["wind_t0"], keep=(bc.get("ckpt_keep") or {}).get("mode"))
                    if bc else None, want_ckpt_frame=want_ck, report=report_a, state_after_retype=S3.get("select"))
    # ---------------- (B) 下見 3 本目の道（両方外れ → PR3 入る → 最後まで）
    R = FXR + "/k1b_" + TAG; D = B44 + "/" + R
    for k in ("PR1", "PR2"):
        jw(D + "/%s/ana.json" % k, failing(a))
    steps = []
    st("pr3_select", ["--only", "SELECT"], 3)
    sel = jl(D + "/select.json")
    jw(D + "/PR3/ana.json", a)
    st("pr3_from_SH_before_confirm", ["--from", "SH"], 3)
    st("pr3_confirm_select", ["--confirm-select", "PR3"], 3)
    st("pr3_only_RP_before_confirm_pr3", ["--only", "RP"], 2)
    st("pr3_from_SH_before_confirm_pr3", ["--from", "SH"], 3)
    st("pr3_confirm_pr3_to_end", ["--confirm-pr3"], 0, prep_sh)
    aimf = glob.glob(D + "/plan_pr3/pr3_aim*.json")
    rp3 = jl(D + "/RP/cfg_queue.json") if os.path.exists(D + "/RP/cfg_queue.json") else None
    sh3 = jl(D + "/SH/cfg_queue.json") if os.path.exists(D + "/SH/cfg_queue.json") else None
    res["B"] = dict(root=R, steps=steps, select=dict(choice=sel["choice"], aim=sel.get("PR3_aim_m")), aim_files=[os.path.basename(p) for p in aimf],
                    SH_inlet=(sh3 or {}).get("inlet", {}).get("name"), RP_inlet=(rp3 or {}).get("inlet", {}).get("name"),
                    RP_prog=((rp3 or {}).get("case") or {}).get("prog"))
    # ---------------- (C) 下見 3 本目も外れる
    R = FXR + "/k1c_" + TAG; D = B44 + "/" + R
    for k in ("PR1", "PR2"):
        jw(D + "/%s/ana.json" % k, failing(a))
    steps = []
    st("pr3fail_select", ["--only", "SELECT"], 3)
    jw(D + "/PR3/ana.json", failing(a))
    st("pr3fail_confirm_select", ["--confirm-select", "PR3"], 2)
    st("pr3fail_confirm_pr3_refused", ["--confirm-pr3"], 1)
    res["C"] = dict(root=R, steps=steps)
    # ---------------- (D) RP の古い途中保存
    R = FXR + "/k1d_" + TAG; D = B44 + "/" + R
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True)))
    os.makedirs(D + "/RP/ckpt")
    open(D + "/RP/ckpt/v.0480.sim", "wb").close()
    jw(D + "/RP/run_c0001.json", dict(f_start=1, f_end_done=500, stopped="wall_limit at frame 500"))
    open(D + "/RP/STOPPED_CRASH.txt", "w", encoding="utf8").write("試しの古い落ち\n")
    steps = []
    st("rp_old_from_RP", ["--from", "RP"], 2)
    st("rp_old_only_RP", ["--only", "RP"], 2)
    st("rp_old_resume", ["--only", "RP", "--resume-rp"], 0)
    st("rp_old_resume_from_RP_then_TABLE_noSH", ["--from", "RP", "--resume-rp"], 2)
    open(D + "/RP/STOPPED_BY_RULE.txt", "w", encoding="utf8").write("試しの古い外れ\n")
    st("rp_old_rule_resume", ["--only", "RP", "--resume-rp"], 2)
    res["D"] = dict(root=R, steps=steps)
    res["plan_unchanged"] = bool(snap(B44 + "/plan") == plan_before)
    allsteps = res["A"]["steps"] + res["B"]["steps"] + res["C"]["steps"] + res["D"]["steps"]
    res["n_steps"] = len(allsteps)
    res["all_ok"] = bool(all(s["ok"] for s in allsteps))
    res["not_ok"] = [s["name"] for s in allsteps if not s["ok"]]
    save("k1", res)
    print(json.dumps({k: v for k, v in res.items() if k in ("n_steps", "all_ok", "not_ok", "plan_unchanged")}, ensure_ascii=False))


# ================================================================== k2：並びの関数を直に呼ぶ
def qmain(Q, root, args):
    sys.argv = ["g44_queue.py", "--agreed", AG, "--root", root] + args
    try:
        Q.main(); return 0
    except SystemExit as e:
        return e.code


def lines(p):
    return open(p, encoding="utf8").read().strip().splitlines() if os.path.exists(p) else []


def t_k2():
    import g44_queue as Q
    TAG = time.strftime("%H%M%S")
    out = {}
    calls = []
    real_run = Q.run

    def guarded_run(cmd):
        # 表の道具は --out を試しの置き場所へ向ける（--out がないと Unity/Build/FLIP44/report へ書くため）
        s = " ".join(cmd)
        if "p_plan_numbers.py" in s:
            raise RuntimeError("試しで p_plan_numbers.py を本当に走らせない")
        if "g44_ctable.py" in s and "--out" not in cmd:
            cmd = cmd + ["--out", B44 + "/" + Q.ROOT + "/table"]
        calls.append(os.path.basename(cmd[1]) if len(cmd) > 1 else s)
        return real_run(cmd)
    Q.run = guarded_run
    # ---------------- (a) 下見 1 の計算が落ちた時（hython が落ちた・打ち切り）：下見 2 は走るか
    for kind in ("crash", "cut"):
        R = FXR + "/k2a_%s_%s" % (kind, TAG); D = B44 + "/" + R
        chained = []

        def fake_chain(cfg, kind=kind):
            chained.append(cfg["run_id"])
            if cfg["run_id"] == "PR1":
                return (kind, 2000, "試し：%s" % kind)
            return ("rule", 4000, "試し")
        Q.chain = fake_chain
        a = r3_ana()
        jw(D + "/PR2/ana.json", a)
        Q.analyze_soft = lambda rid: (jl(B44 + "/" + Q.ROOT + "/%s/ana.json" % rid), None) if os.path.exists(B44 + "/" + Q.ROOT + "/%s/ana.json" % rid) else (None, "ない")
        code = qmain(Q, R, [])
        out["a_" + kind] = dict(exit=code, chained=chained, stop=lines(D + "/QUEUE_STOP.txt")[-1:])
        print("k2a", kind, code, chained)
    # ---------------- (b) 下見 1 の解析が止まった時（1 回目だけ止まる）→ 下見 2 → 選びで待つ → --from SELECT で通る
    R = FXR + "/k2b_" + TAG; D = B44 + "/" + R
    a = r3_ana()
    jw(D + "/PR2/ana.json", a)
    os.makedirs(D + "/PR1", exist_ok=True)
    open(D + "/PR1/hf_c0001.npz", "wb").close()        # 記録がある印（選びの段は hf_c*.npz を見る）
    chained = []
    Q.chain = lambda cfg: (chained.append(cfg["run_id"]) or ("rule", 4000, "試し"))
    state = dict(n=0)

    def fake_ana(rid):
        p = B44 + "/" + Q.ROOT + "/%s/ana.json" % rid
        if rid == "PR1" and state["n"] < 2:
            state["n"] += 1
            return None, "試し：PR1 の解析が止まった"
        if rid == "PR1" and not os.path.exists(p):
            jw(p, a)
        return (jl(p), None) if os.path.exists(p) else (None, "ない")
    Q.analyze_soft = fake_ana
    c1 = qmain(Q, R, [])
    c2 = qmain(Q, R, ["--from", "SELECT"])
    out["b_pr1_ana_fail"] = dict(exit_first=c1, exit_after=c2, chained=chained, report=lines(D + "/QUEUE_REPORT.txt"),
                                 pause=lines(D + "/QUEUE_PAUSE.txt")[-4:], select=jl(D + "/queue_state.json").get("select"))
    print("k2b", c1, c2, chained)
    # ---------------- (c) 風の計算：打ち切り（cut）・唇の先で止まった（online_tip）・解析が止まった、の本当の解析と風の判定
    import importlib
    Q = importlib.reload(Q)
    real_run = Q.run
    Q.run = guarded_run
    R = FXR + "/k2c_" + TAG; D = B44 + "/" + R
    fx = B44 + "/check/fx"
    shutil.copytree(fx + "/SHx", D + "/SH")
    c = jl(D + "/SH/cfg.json"); c["run_id"] = "SH"; c["out_root"] = R; jw(D + "/SH/cfg.json", c)
    sh_a = jl(D + "/SH/ana.json")
    os.makedirs(D + "/SH/ckpt", exist_ok=True)
    for k in (3240, 3480, 3564, 3660):
        open(D + "/SH/ckpt/v.%04d.sim" % k, "wb").close()
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True),
                                     SH=dict(onset=sh_a["onset"], touchdown=sh_a["touchdown"], still=sh_a["still_level_offset_m"])))
    src_of = {"B35S": "Bx_cap", "B45S": "Bx_pre"}
    mode_of = {"B35S": "cut", "B45S": "cut"}
    seen = {}

    def fake_wind_chain(cfg):
        rid = cfg["run_id"]; rd = B44 + "/" + Q.ROOT + "/" + rid
        os.makedirs(rd, exist_ok=True)
        seen[rid] = dict(f_start=cfg["f_start"], f_end=cfg["f_end"], from_ckpt=cfg["from_ckpt"], max_hours=cfg["max_hours"],
                         tip_on=cfg["stop_touchdown"].get("tip_on"), t_from=cfg["stop_touchdown"]["t_from"])
        t0 = time.time()
        src = fx + "/" + src_of[rid]
        for p in glob.glob(src + "/*.npz"):
            shutil.copy2(p, rd)
        cc = jl(src + "/cfg.json"); cc["run_id"] = rid; cc["out_root"] = Q.ROOT; cc["from_ckpt"] = dict(run="SH", frame=3564)
        cc["stop_touchdown"] = cfg["stop_touchdown"]
        jw(rd + "/cfg.json", cc)
        m = mode_of[rid]
        if m == "cut":
            jw(rd + "/run_c3565.json", dict(f_start=3565, f_end_done=4100, stopped="wall_limit at frame 4100"))
            open(rd + "/STOPPED_MAX_HOURS.txt", "w", encoding="utf8").write("試し：打ち切り\n")
        elif m == "tip":
            jw(rd + "/run_c3565.json", dict(f_start=3565, f_end_done=3800, stopped="touchdown_online_tip at frame 3752 (+2.00 s, lip tip at or below still level, no cavity seen)"))
        return Q.chain_result(rid, int(cfg["f_end"]), t0)
    Q.chain = fake_wind_chain
    cb = qmain(Q, R, ["--only", "B35S"])
    cb2 = qmain(Q, R, ["--only", "B45S"])
    S = jl(D + "/queue_state.json")
    ct = qmain(Q, R, ["--only", "TABLE"])
    tab = open(D + "/table/remaining_gap_ja.md", encoding="utf8").read() if os.path.exists(D + "/table/remaining_gap_ja.md") else ""
    out["c_wind"] = dict(exit_B35S=cb, exit_B45S=cb2, exit_TABLE=ct, wind_state=S.get("wind"), cfg_seen=seen,
                         report=lines(D + "/QUEUE_REPORT.txt"), table_has_B35S=("B35S" in tab), table_has_B45S=("B45S" in tab),
                         ana_B35S=dict((k, (jl(D + "/B35S/ana.json").get(k) or {}).get("frame") if isinstance(jl(D + "/B35S/ana.json").get(k), dict) else None)
                                       for k in ("onset", "touchdown")) if os.path.exists(D + "/B35S/ana.json") else None,
                         wind_check_written=os.path.exists(D + "/B35S/wind_check.json"))
    print("k2c", cb, cb2, ct, json.dumps(S.get("wind"), ensure_ascii=False)[:400])
    # 唇の先で止まった時（online_tip）の読み分け：記録は Bx_online（着水 + 0.5 s で切れた記録）、止まりの文は唇の先
    R2 = FXR + "/k2c2_" + TAG; D2 = B44 + "/" + R2
    shutil.copytree(D + "/SH", D2 + "/SH")
    c = jl(D2 + "/SH/cfg.json"); c["out_root"] = R2; jw(D2 + "/SH/cfg.json", c)
    jw(D2 + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True),
                                      SH=dict(onset=sh_a["onset"], touchdown=sh_a["touchdown"], still=sh_a["still_level_offset_m"])))
    src_of["B35S"] = "Bx_online"; mode_of["B35S"] = "tip"
    ct2 = qmain(Q, R2, ["--only", "B35S"])
    S2 = jl(D2 + "/queue_state.json")
    out["c_wind_tip"] = dict(exit=ct2, wind_state=S2.get("wind"), report=lines(D2 + "/QUEUE_REPORT.txt"))
    print("k2c tip", ct2, json.dumps(S2.get("wind"), ensure_ascii=False)[:300])
    # ---------------- (d) RP：1 回目が外れた（新しい STOPPED_BY_RULE）→ 止まる。走らせ直しの言葉
    R = FXR + "/k2d_" + TAG; D = B44 + "/" + R
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True)))

    def fake_rp(cfg):
        rd = B44 + "/" + Q.ROOT + "/RP"; t0 = time.time()
        os.makedirs(rd + "/ckpt", exist_ok=True)
        open(rd + "/ckpt/v.2880.sim", "wb").close()
        jw(rd + "/run_c0001.json", dict(f_start=1, f_end_done=2900, stopped="wall_limit at frame 2900"))
        open(rd + "/STOPPED_BY_RULE.txt", "w", encoding="utf8").write("試し：1 回目が外れた\n")
        return Q.chain_result("RP", int(cfg["f_end"]), t0)
    Q.chain = fake_rp
    d1 = qmain(Q, R, ["--only", "RP"])
    d2 = qmain(Q, R, ["--from", "RP"])
    d3 = qmain(Q, R, ["--from", "RP", "--resume-rp"])
    out["d_rp_rule"] = dict(exits=[d1, d2, d3], stop=lines(D + "/QUEUE_STOP.txt")[-3:])
    # RP が打ち切りで止まった → --from RP --resume-rp で続く（古い STOPPED_MAX_HOURS は読まない）
    R = FXR + "/k2e_" + TAG; D = B44 + "/" + R
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True)))
    n = dict(i=0)

    def fake_rp2(cfg):
        rd = B44 + "/" + Q.ROOT + "/RP"; t0 = time.time()
        os.makedirs(rd + "/ckpt", exist_ok=True)
        n["i"] += 1
        if n["i"] == 1:
            open(rd + "/ckpt/v.2880.sim", "wb").close()
            jw(rd + "/run_c0001.json", dict(f_start=1, f_end_done=2900, stopped="wall_limit at frame 2900"))
            open(rd + "/STOPPED_MAX_HOURS.txt", "w", encoding="utf8").write("試し：打ち切り\n")
            old = time.time() - 30
            os.utime(rd + "/STOPPED_MAX_HOURS.txt", None)
        else:
            time.sleep(1.5)
            t0 = time.time()
            jw(rd + "/run_c2881.json", dict(f_start=2881, f_end_done=int(cfg["f_end"]), stopped=None))
        return Q.chain_result("RP", int(cfg["f_end"]), t0)
    Q.chain = fake_rp2
    e1 = qmain(Q, R, ["--only", "RP"])
    time.sleep(1.5)
    e2 = qmain(Q, R, ["--from", "RP"])
    e3 = qmain(Q, R, ["--only", "RP", "--resume-rp"])
    out["e_rp_cut_resume"] = dict(exits=[e1, e2, e3], stop=lines(D + "/QUEUE_STOP.txt")[-3:], report=lines(D + "/QUEUE_REPORT.txt")[-3:])
    print("k2d", out["d_rp_rule"]["exits"], "k2e", out["e_rp_cut_resume"]["exits"])
    out["run_calls"] = calls
    save("k2", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:6000])


# ================================================================== k3：着水の読み
def sec_frames(rd):
    """コマ → (ファイル, 番号, meta)。同じコマが 2 つの起動にある時は後の起動の物。"""
    best = {}
    for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
        f0 = int(os.path.basename(p)[5:9]); d = np.load(p)
        m = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i, m)
    return best


def shoelace(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def my_reading(sl, m, off, vox, Lc, parms, xc_main=None):
    """自分の読み：海底の中は水、静かな水面の 25 m より下は切る。(1) skimage の閉じた等高線のうち、中が空気、面積 ≥ vox²、
    中心が頂（一番高い水、または主な頂の道）の後ろ 0.25 Lc〜前 0.75 Lc、頂より下。(2) scipy の空気の塊（辺でつなぐ）のうち、上の端と左右の端に
    触れない物の格子の面積。(3) 唇の先：いちばん長い等高線を頂から前へたどり、x がいちばん前に出た点（0 で切らない）。"""
    from skimage import measure
    from scipy import ndimage
    import g44_online as O
    xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"]) - off
    S = sl.astype(np.float64).copy()
    bed = O.bed_y(parms, xs) - off
    S[ys[:, None] < (bed[None, :])] = -1.0
    j0 = int(np.searchsorted(ys, -25.0)); S = S[j0:]; ys = ys[j0:]
    water = S < 0
    wy = np.where(water.any(1))[0]
    jt = wy.max(); xc_hi = float(xs[int(np.where(water[jt])[0].mean())]); yc = float(ys[jt])
    out = dict(xc_high=xc_hi, yc=yc)
    lines_ = []
    for c in measure.find_contours(S, 0.0):
        X = xs[0] + c[:, 1] * m["dx"]; Y = ys[0] + c[:, 0] * m["dy"]
        lines_.append(np.stack([X, Y], 1))
    for tag, xc in (("high", xc_hi), ("main", xc_main)):
        if xc is None:
            continue
        cav = []; amax = 0.0
        for l in lines_:
            if len(l) > 4 and np.allclose(l[0], l[-1]):
                A = shoelace(l); cx, cy = l[:, 0].mean(), l[:, 1].mean()
                ix = int(round((cx - xs[0]) / m["dx"])); iy = int(round((cy - ys[0]) / m["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0 and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                    amax = max(amax, A / (vox * vox))
                    if A >= vox * vox:
                        cav.append((round(A, 4), round(cx, 2), round(cy, 2)))
        out["cav_" + tag] = sorted(cav, reverse=True)[:3]
        out["hole_ratio_" + tag] = amax
    # (2) scipy の塊
    air = ~water
    lab, n = ndimage.label(air)
    edge = set(np.unique(np.concatenate([lab[-1, :], lab[:, 0], lab[:, -1]]))) - {0}
    blobs = []
    for k in range(1, n + 1):
        if k in edge:
            continue
        jj, ii = np.where(lab == k)
        cx = float(xs[ii].mean()); cy = float(ys[jj].mean())
        if (xc_hi - 0.25 * Lc) <= cx <= (xc_hi + 0.75 * Lc) and cy < yc:
            blobs.append((len(jj) * m["dx"] * m["dy"], round(cx, 2), round(cy, 2)))
    out["blobs"] = sorted(blobs, reverse=True)[:3]
    # (3) 唇の先
    if lines_:
        ext = [l[:, 0].max() - l[:, 0].min() for l in lines_]
        L = lines_[int(np.argmax(ext))]
        if L[0, 0] > L[-1, 0]:
            L = L[::-1]
        xc = xc_main if xc_main is not None else xc_hi
        near = np.where(np.abs(L[:, 0] - xc) <= 2.0 * m["dx"] + 1e-6)[0]
        if len(near):
            ic = int(near[np.argmax(L[near, 1])])
            fwd = L[ic:]
            far = np.where(fwd[:, 0] > xc + 0.75 * Lc)[0]
            if len(far):
                fwd = fwd[:far[0]]
            if len(fwd) > 2:
                # 頂から前へたどり、x が前の最大から vox 以上戻った所で、その最大の点を唇の先とする（高さ 0 で切らない）
                im = 0; tip = None
                for j in range(1, len(fwd)):
                    if fwd[j, 0] > fwd[im, 0]:
                        im = j
                    elif fwd[j, 0] < fwd[im, 0] - vox:
                        tip = im; break
                if tip is not None:
                    out["tip"] = dict(x=float(fwd[tip, 0]), y=float(fwd[tip, 1]), turned=True)
                else:
                    out["tip"] = dict(x=float(fwd[im, 0]), y=float(fwd[im, 1]), turned=False)
    return out


def t_k3():
    import g44_online as O
    import g44_analyze as A
    P = A.plan(); Lc = P["tank"]["Lc"]
    recs = []
    for rid in ("R1b", "R2", "R3", "R4d"):
        rd = R42 + "/" + rid; a = jl(rd + "/ana.json")
        main = a.get("main") or {}
        recs.append(dict(name=rid, rd=rd, cfg=jl(rd + "/cfg.json"), off=a["still_level_offset_m"], on=a["onset"]["frame"], td=a["touchdown"]["frame"],
                         path={int(p[0]): p[1] for p in (main.get("path") or [])}))
    for rid in ("R3d", "R3m", "R5p"):
        rd = R42 + "/" + rid; s = jl(rd + "/shape.json")
        recs.append(dict(name=rid, rd=rd, cfg=jl(rd + "/cfg.json"), off=s["still_level_offset_m"], on=s["onset"]["frame"], td=s["touchdown"]["frame"], path={}))
    rd = B44 + "/smoke/S8"; a = jl(rd + "/ana.json")
    e = [e for e in a["events"] if e.get("onset") and e.get("touchdown")][0]
    recs.append(dict(name="S8", rd=rd, cfg=jl(rd + "/cfg.json"), off=a["still_level_offset_m"], on=e["onset"]["frame"], td=e["touchdown"]["frame"],
                     path={int(p[0]): p[1] for p in (e.get("path") or [])}))
    out = {}
    for r in recs:
        best = sec_frames(r["rd"]); parms = r["cfg"]["parms"]; xp = parms["x_p"]; vox = 2.0 * float(parms["dp"])
        t_on = (r["on"] - 1) / FPS
        st = dict(after_s=0.5, t_from=t_on - 1.0, Lc=Lc, still_offset_m=r["off"], tip_on=True, tip_wait_s=2.0)
        W = O.TouchdownWatch(st, vox, parms, FPS)
        stop = None; first_mine = dict(high=None, main=None); first_blob = None; rows = []; cache = {}
        margin = dict(pre_td_window=(0.0, None), before_t_from=(0.0, None)); tips_all = []
        f_lo = r["on"] - 72; f_hi = r["td"] + 60
        for f in range(f_lo, f_hi + 1):
            if f not in best:
                continue
            f0, p, i, m = best[f]
            if p not in cache:
                cache.clear(); cache[p] = np.load(p)["sdf"]
            sl = cache[p][i].astype(np.float32)
            xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
            t = (f - 1) / FPS
            if stop is None:
                W.step(f, t, sl, xs, ys)
                s_ = W.should_stop(t)
                if s_:
                    stop = (f, s_)
            xm = (r["path"][f] + xp) if f in r["path"] else None
            mr = my_reading(sl, m, r["off"], vox, Lc, parms, xm)
            lt = O.lip_tip(sl, xs, ys, Lc, vox, r["off"], parms)
            if f < r["td"]:
                hr = mr.get("hole_ratio_high", 0.0)
                key = "pre_td_window" if t >= st["t_from"] - 1e-9 else "before_t_from"
                if hr > margin[key][0]:
                    margin[key] = (hr, f)
            tips_all.append((f, (mr.get("tip") or {}).get("y"), (mr.get("tip") or {}).get("turned"), lt.get("y_tip") if lt else None))
            if t >= st["t_from"] - 1e-9:
                for tag in ("high", "main"):
                    if first_mine[tag] is None and mr.get("cav_" + tag):
                        first_mine[tag] = f
                if first_blob is None and mr["blobs"] and mr["blobs"][0][0] >= vox * vox:
                    first_blob = f
            if r["td"] - 3 <= f <= r["td"] + 1 or f == r["on"]:
                rows.append(dict(f=f, mine_tip=mr.get("tip"), online_tip=dict(found=lt.get("found"), y=lt.get("y_tip"), over=lt.get("over_cols"), why=lt.get("why")) if lt else None,
                                 cav_high=mr.get("cav_high"), cav_main=mr.get("cav_main"), blobs=mr["blobs"][:2]))
        out[r["name"]] = dict(dp=r["cfg"]["parms"]["dp"], vox=vox, sec_dx=m["dx"], onset_ana=r["on"], touchdown_ana=r["td"],
                              online_td=(W.td or {}).get("frame"), online_tip=(W.tip or {}).get("frame"), online_stop=stop,
                              mine_first_contour_high=first_mine["high"], mine_first_contour_main=first_mine["main"], mine_first_blob=first_blob,
                              same_as_analysis=bool((W.td or {}).get("frame") == r["td"]), rows=rows,
                              hole_ratio_max_before_td=margin,
                              mine_tip_at_td=next((tt[1] for tt in tips_all if tt[0] == r["td"]), None),
                              mine_tip_turned_at_td=next((tt[2] for tt in tips_all if tt[0] == r["td"]), None),
                              online_tip_at_td=next((tt[3] for tt in tips_all if tt[0] == r["td"]), None),
                              mine_tip_min_on_to_td=min([tt[1] for tt in tips_all if r["on"] <= tt[0] <= r["td"] and tt[2] and tt[1] is not None] or [None], key=lambda v: 1e9 if v is None else v))
        print(r["name"], "ana", r["td"], "online", (W.td or {}).get("frame"), "tip", (W.tip or {}).get("frame"), "stop", stop and stop[0],
              "mine", first_mine, "blob", first_blob)
    # 巻かない記録：全部のコマで、計算の中の読みが何かを見つけるか（R1 は FLIP42 の巻かない計算、S9_v2 は煙の試しのなだらかな波）
    neg = {}
    for name, rd in (("R1", R42 + "/R1"), ("S9_v2", B44 + "/smoke/S9_v2")):
        cfg = jl(rd + "/cfg.json"); parms = cfg["parms"]; vox = 2.0 * float(parms["dp"])
        ap = rd + "/ana.json" if os.path.exists(rd + "/ana.json") else B44 + "/check/fx/ana_%s.json" % name
        off = jl(ap)["still_level_offset_m"] if os.path.exists(ap) else 0.0
        best = sec_frames(rd)
        W = O.TouchdownWatch(dict(after_s=0.5, t_from=0.0, Lc=Lc, still_offset_m=off, tip_on=True, tip_wait_s=2.0), vox, parms, FPS)
        n = 0; cache = {}; tip_found = 0; first = None
        for f in sorted(best):
            f0, p, i, m = best[f]
            if p not in cache:
                cache.clear(); cache[p] = np.load(p)["sdf"]
            sl = cache[p][i].astype(np.float32)
            xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
            W.step(f, (f - 1) / FPS, sl, xs, ys); n += 1
            lt = O.lip_tip(sl, xs, ys, Lc, vox, off, parms)
            tip_found += 1 if (lt and lt.get("found")) else 0
            if first is None and (W.td or W.tip):
                first = f
        neg[name] = dict(frames=n, td=(W.td or {}).get("frame"), tip=(W.tip or {}).get("frame"), lip_found_frames=tip_found, first=first)
        print("neg", name, neg[name])
    out["negative"] = neg
    # 判定（走らせる前に決めた）：8 本の全部で、計算の中の穴の読みのコマ ＝ 解析の着水のコマ（S8 と FLIP42 は解析の記録、R3d・R3m・R5p は
    # FLIP42 の shape.json）、止まるコマ ≥ 着水のコマ、自分の等高線の読みの最初のコマ ＝ 解析の着水、巻かない 2 本で何も見つけない
    out["pass"] = dict(
        online_eq_analysis=all(out[k]["same_as_analysis"] for k in out if k != "negative"),
        stop_after_td=all(out[k]["online_stop"] and out[k]["online_stop"][0] >= out[k]["touchdown_ana"] for k in out if k not in ("negative",)),
        mine_eq_analysis=all(out[k]["mine_first_contour_high"] == out[k]["touchdown_ana"] for k in out if k not in ("negative",)),
        negatives_quiet=all(v["td"] is None and v["tip"] is None for v in neg.values()))
    save("k3", out)
    print("pass", out["pass"])


def t_k3c():
    """計算の中の穴の面積（g44_online._ms_area。numpy で書いた等高線）と skimage の閉じた等高線の面積を、8 本の記録の巻き始め − 1 s から
    着水 + 1 s の全部のコマで、窓の中の全部の穴について比べる（窓・海底・25 m の切りは g44_online.cavity_frame と同じ）。"""
    import g44_online as O
    import g44_analyze as A
    from skimage import measure
    Lc = A.plan()["tank"]["Lc"]
    recs = []
    for rid in ("R1b", "R2", "R3", "R4d"):
        rd = R42 + "/" + rid; a = jl(rd + "/ana.json")
        recs.append((rid, rd, a["still_level_offset_m"], a["onset"]["frame"], a["touchdown"]["frame"]))
    for rid in ("R3d", "R3m", "R5p"):
        rd = R42 + "/" + rid; s = jl(rd + "/shape.json")
        recs.append((rid, rd, s["still_level_offset_m"], s["onset"]["frame"], s["touchdown"]["frame"]))
    rd = B44 + "/smoke/S8"; a = jl(rd + "/ana.json")
    e = [e for e in a["events"] if e.get("onset") and e.get("touchdown")][0]
    recs.append(("S8", rd, a["still_level_offset_m"], e["onset"]["frame"], e["touchdown"]["frame"]))
    tot = dict(frames=0, frames_with_holes=0, holes_online=0, holes_sk=0, mismatch=[], max_abs_diff=0.0)
    for rid, rd, off, f_on, f_td in recs:
        cfg = jl(rd + "/cfg.json"); parms = cfg["parms"]; vox = 2.0 * float(parms["dp"])
        best = sec_frames(rd); cache = {}
        for f in range(f_on - 24, f_td + 25):
            if f not in best:
                continue
            f0, p, i, m = best[f]
            if p not in cache:
                cache.clear(); cache[p] = np.load(p)["sdf"]
            sl = cache[p][i].astype(np.float32)
            xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
            # g44_online.cavity_frame と同じ窓と穴
            water = sl < 0
            bed = ys[:, None] < (O.bed_y(parms, xs)[None, :] + 0.5 * vox)
            air = (~water) & (~bed)
            wy = np.where(water.any(1))[0]; jt = wy.max()
            ic = int(np.where(water[jt])[0].mean()); xc = xs[ic]
            mm = (xs >= xc - 0.25 * Lc) & (xs <= xc + 0.75 * Lc)
            Am = air[:, mm]
            reach = np.zeros_like(Am); reach[-1, :] = Am[-1, :]; reach[:, 0] |= Am[:, 0]; reach[:, -1] |= Am[:, -1]
            for _ in range(4000):
                r2 = reach.copy(); r2[1:, :] |= reach[:-1, :]; r2[:-1, :] |= reach[1:, :]; r2[:, 1:] |= reach[:, :-1]; r2[:, :-1] |= reach[:, 1:]
                r2 &= Am
                if (r2 == reach).all():
                    break
                reach = r2
            hole = Am & ~reach
            hole[(ys - off) < -25.0, :] = False
            S = sl[:, mm].astype(np.float64).copy(); S[bed[:, mm]] = -1.0
            on = sorted(O._ms_area(S, jj, ii) * m["dx"] * m["dy"] for jj, ii in O._components(hole))
            sk = []
            for c in measure.find_contours(S, 0.0):
                if len(c) > 4 and np.allclose(c[0], c[-1]):
                    cyv = ys[0] + c[:, 0].mean() * m["dy"]
                    iy = int(round(c[:, 0].mean())); ix = int(round(c[:, 1].mean()))
                    if S[iy, ix] > 0 and (cyv - off) >= -25.0:
                        P_ = np.stack([c[:, 1] * m["dx"], c[:, 0] * m["dy"]], 1)
                        sk.append(shoelace(P_))
            sk = sorted(sk)
            tot["frames"] += 1; tot["frames_with_holes"] += 1 if on else 0
            tot["holes_online"] += len(on); tot["holes_sk"] += len(sk)
            if len(on) != len(sk) or (on and not np.allclose(on, sk, rtol=1e-9, atol=1e-9)):
                if len(tot["mismatch"]) < 20:
                    tot["mismatch"].append([rid, f, [round(v, 4) for v in on[-4:]], [round(v, 4) for v in sk[-4:]]])
            elif on:
                tot["max_abs_diff"] = max(tot["max_abs_diff"], float(np.max(np.abs(np.array(on) - np.array(sk)))))
    save("k3c", tot)
    print(json.dumps(tot, ensure_ascii=False, default=float)[:3000])


# ================================================================== k4：途中保存の残し方
class Mover:
    def __init__(self, rd):
        self.rd = rd; self.moved = []
        os.makedirs(rd + "/_moved", exist_ok=True)

    def remove(self, p):
        self.moved.append(int(os.path.basename(p)[2:6]))
        os.replace(p, os.path.join(self.rd, "_moved", os.path.basename(p)))


def replay_chain(K, rd, cfg, trace, pre=(), size=lambda k: 1000, start_copy=None, crash_after=None):
    """g44_chain の起動の決まりの上で after_launch を本当に動かす（消す代わりに _moved/ へ動かす）。返り値：確かめの行。"""
    os.makedirs(rd + "/ckpt", exist_ok=True)
    for k in pre:
        open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\1" * 1000)
    if start_copy is not None:
        open(rd + "/ckpt/v.%04d.sim" % start_copy, "wb").write(b"\1" * 1000)
        L = K.load_ledger(rd); K.note_made(rd, L, [start_copy], "copy"); K.save_ledger(rd, L)
    mv = Mover(rd)
    K.os = types.SimpleNamespace(path=os.path, remove=mv.remove)
    rows = []
    try:
        for n, L in enumerate(trace):
            f0 = L["f0"]
            have = K.ckpt_frames(rd)
            need = f0 - 1
            start_ok = (f0 == 1) or (need in have)
            before = list(have)
            for k in L["cks"]:
                open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\1" * size(k))
            if crash_after is not None and n == crash_after:
                rows.append(dict(f0=f0, start_ok=start_ok, crashed=True)); break
            r = K.after_launch(rd, cfg, f0, L["done"], before, 2.0, 1.0, log=lambda *a: None)
            have2 = K.ckpt_frames(rd)
            nxt = max([k for k in have2 if k <= L["done"]] or [None]) if have2 else None
            rows.append(dict(f0=f0, done=L["done"], new=r["new"], deleted=r["deleted"], why=r["why"], start_ok=start_ok, next_start=nxt,
                             pre_intact=all(k in have2 for k in pre)))
    finally:
        K.os = os
    return rows, mv.moved


def t_k4():
    import g44_ckpt as K
    import g44_hours as H
    import g44_cfg as C
    TAG = time.strftime("%H%M%S")
    D = FX + "/k4_" + TAG
    P = H.plan(); Tc = P["tank"]["Tc"]
    out = {}
    # (a) 下見：前からある物 2 個（帳面にない）、本番の置き場所の道で起動の真似を最後まで
    tr = []; H.est_PR(155.0, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 1.0, Tc, trace=tr)
    rd = D + "/PR"
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr, pre=(100, 200))
    out["a_PR"] = dict(launches=len(tr), made=sum(len(L["cks"]) for L in tr), moved=len(moved), left=K.ckpt_frames(rd),
                       all_starts_ok=all(r["start_ok"] for r in rows), pre_intact=all(r["pre_intact"] for r in rows),
                       next_starts_match_trace=[r["next_start"] for r in rows[:-1]] == [L["f0"] - 1 for L in tr[1:]])
    # (b) やり直しの道（新しい途中保存なし → 同じ所から小さい間隔で）。重い機械で起動の真似
    tr = []; H.est_SH(150.0, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 2.0, Tc, trace=tr)
    f_w, sp = H.f_w_rule(150.0)
    retry = [i for i in range(1, len(tr)) if tr[i]["f0"] == tr[i - 1]["f0"]]
    rd = D + "/SH_retry"
    pol = K.keep_policy("SH", onset_pre=150.0, f_w=f_w, Tc=Tc)
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=pol), tr)
    out["b_SH_load2"] = dict(launches=len(tr), retries=retry, all_starts_ok=all(r["start_ok"] for r in rows), moved=len(moved),
                             protected_moved=[k for k in moved if k in K.protected([k], pol)], left=K.ckpt_frames(rd))
    # (c) 書きかけ：いちばん新しい物が 60 % の大きさ（半分より大きい）→ 消す。続きの元（確かめた始め）は残るか
    tr = []; H.est_PR(155.0, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 1.0, Tc, trace=tr)
    rd = D + "/PR_partial"
    ib = next(i for i in range(3, len(tr)) if tr[i]["cks"])
    bad = tr[ib]["cks"][-1]
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr[:ib + 1], size=lambda k: 600 if k == bad else 1000)
    L = K.load_ledger(rd)
    out["c_partial60"] = dict(bad=bad, left=K.ckpt_frames(rd), verified=L["verified"], last=L.get("last"))
    rd = D + "/PR_partial40"
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr[:ib + 1], size=lambda k: 400 if k == bad else 1000)
    out["c_partial40"] = dict(bad=bad, left=K.ckpt_frames(rd), why=rows[-1]["why"])
    # (d) 起動が落ちた（記録なし → after_launch は呼ばれない）後に続きから：落ちた起動の途中保存は帳面にないので消さない
    rd = D + "/PR_crash"
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr, crash_after=3)
    crashed_cks = tr[3]["cks"]
    tr2 = [dict(L) for L in tr[4:]]
    rows2, moved2 = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr2)
    out["d_crash"] = dict(crashed_launch_cks=crashed_cks, moved_after=moved2, crashed_kept=all(k in K.ckpt_frames(rd) for k in crashed_cks),
                          starts_ok=all(r["start_ok"] for r in rows2))
    # (e) 風の計算：元の途中保存の写しから。写しは帳面にあり消える。元（SH）は別のフォルダーなので触らない
    tr = []; r = H.est_B(155.0, 1.0, 1.0, Tc, "cap", ckpt_frame=3624, trace=tr)
    rd = D + "/B35S"
    rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("B")), tr, start_copy=3624)
    out["e_B"] = dict(launches=len(tr), made=sum(len(L["cks"]) for L in tr) + 1, moved=len(moved), left=K.ckpt_frames(rd),
                      all_starts_ok=all(r_["start_ok"] for r_ in rows), copy_moved=(3624 in moved))
    # (f) 形の本番：巻き始めが下見とずれた時、風の計算の始め（t_on − 3 s より前の最後の途中保存）が残るか。
    #     下見の巻き始め 140〜165 s、機械の重さ 1.0・1.33。ずれ δ = 形の本番 − 下見（負は早く巻いた）
    deltas = [-9.0, -7.0, -5.0, -4.0, -3.5, -3.0, -2.5, -1.0, 0.0, 1.0, 3.0, 6.0, 9.0]
    rowsF = []
    for onset_pre in (140.0, 145.0, 150.0, 155.0, 160.0, 165.0):
        for load in (1.0, 1.33):
            tr = []; H.est_SH(onset_pre, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, load, Tc, trace=tr)
            f_w, sp = H.f_w_rule(onset_pre)
            pol = K.keep_policy("SH", onset_pre=onset_pre, f_w=f_w, Tc=Tc)
            rd = D + "/SHd_%g_%g" % (onset_pre, load)
            rows, moved = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=pol), tr)
            left = K.ckpt_frames(rd)
            allk = sorted(set(k for L in tr for k in L["cks"]))
            for d in deltas:
                t_on = onset_pre + d
                want = [k for k in allk if (k - 1) / FPS < t_on - 3.0]
                have = [k for k in left if (k - 1) / FPS < t_on - 3.0]
                rowsF.append(dict(onset_pre=onset_pre, load=load, delta=d, f_w=f_w, sp_lock=sp, protect=pol["protect_ranges"][0],
                                  plan_start=(want[-1] if want else None), left_start=(have[-1] if have else None),
                                  lost_s=(((want[-1] - have[-1]) / FPS) if (want and have) else None), wind_not_run=bool(want and not have)))
    nr = [r_ for r_ in rowsF if r_["wind_not_run"]]
    out["f_SH_shift"] = dict(rows=rowsF, n=len(rowsF), n_wind_not_run=len(nr),
                             not_run_deltas=sorted(set(r_["delta"] for r_ in nr)), run_deltas_all_same=sorted(set(r_["delta"] for r_ in rowsF if r_["left_start"] == r_["plan_start"])),
                             worst_lost_s=max([r_["lost_s"] for r_ in rowsF if r_["lost_s"] is not None] or [0.0]))
    # 並びの言葉の確かめ：消えていた時の報告（wind_stage）は「途中保存がない」と書くか、「消してあった」と書くか
    import g44_queue as Q
    R = FXR + "/k4q_" + TAG; DQ = B44 + "/" + R
    onset_pre = 155.0; f_w, sp = H.f_w_rule(onset_pre)
    os.makedirs(DQ + "/SH/ckpt")
    pol = K.keep_policy("SH", onset_pre=onset_pre, f_w=f_w, Tc=Tc)
    tr = []; H.est_SH(onset_pre, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 1.0, Tc, trace=tr)
    rows, moved = replay_chain(K, DQ + "/SH", dict(out_root="runs", ckpt_keep=pol), tr)
    a = r3_ana()
    t_on = onset_pre - 5.0
    on = dict(a["onset"]); on["t"] = t_on; td = dict(a["touchdown"]); td["t"] = t_on + 1.3
    jw(DQ + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True), SH=dict(onset=on, touchdown=td, still=0.16)))
    rc, so, se = py(["g44_queue.py", "--agreed", AG, "--root", R, "--dry-run", "--only", "B35S"], enc="cp932")
    out["f_queue_message"] = dict(rc=rc, report=lines(DQ + "/QUEUE_REPORT.txt"), state=jl(DQ + "/queue_state.json").get("wind"),
                                  ledger_pruned_before=K.pruned_before(DQ + "/SH", t_on - 3.0))
    # (g) 帳面の「作った物」は、並びでない chain（README §2 の 1 本ずつの道、ckpt_keep なし）が作った物も入る → 後で並びが同じフォルダーで消せる
    rd = D + "/mixed"
    tr = []; H.est_PR(155.0, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 1.0, Tc, trace=tr)
    rows1, _ = replay_chain(K, rd, dict(out_root="runs"), tr[:3])
    made_by_single = sorted(int(k) for k in K.load_ledger(rd)["made"])
    rows2, moved2 = replay_chain(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr[3:5])
    out["g_single_then_queue"] = dict(made_by_single_run=made_by_single, moved_by_queue=sorted(moved2),
                                      single_run_ckpts_moved=sorted(set(moved2) & set(made_by_single)))
    save("k4", out)
    print(json.dumps({k: (v if k != "f_SH_shift" else {kk: vv for kk, vv in v.items() if kk != "rows"}) for k, v in out.items()}, ensure_ascii=False, default=float)[:6000])


def t_k4e():
    """消す途中で 1 個が消せなかった時（ほかの処理がファイルを使っているなど）、帳面に何が残るか。消す代わりに _moved/ へ動かす。"""
    import g44_ckpt as K
    rd = FX + "/k4e_" + time.strftime("%H%M%S")
    os.makedirs(rd + "/ckpt")
    for k in (240, 480, 720):
        open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\1" * 1000)
    cfg = dict(out_root="runs", ckpt_keep=K.keep_policy("PR"))
    mv = Mover(rd)
    K.os = types.SimpleNamespace(path=os.path, remove=mv.remove)
    try:
        K.after_launch(rd, cfg, 1, 730, [], 2.0, 1.0, log=lambda *a: None)
        n = dict(i=0)

        def rem(p):
            n["i"] += 1
            if n["i"] >= 2:
                raise PermissionError("試し：ほかの処理が使っている")
            mv.remove(p)
        K.os = types.SimpleNamespace(path=os.path, remove=rem)
        for k in (960, 1200):
            open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\1" * 1000)
        try:
            K.after_launch(rd, cfg, 721, 1210, [240, 480, 720], 2.0, 1.0, log=lambda *a: None); err = None
        except Exception as e:
            err = repr(e)
    finally:
        K.os = os
    L = K.load_ledger(rd)
    out = dict(error=err, files_left=K.ckpt_frames(rd), moved=mv.moved, ledger_pruned=sorted(int(k) for k in L["pruned"]), verified=L["verified"])
    save("k4e", out)
    print(json.dumps(out, ensure_ascii=False))


# ================================================================== k5：置き場所の見込み
def t_k5():
    import g44_ckpt as K
    import g44_queue as Q
    t0 = time.time()
    d = K.disk_plan(["PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP"])
    t1 = time.time()
    d2 = K.disk_plan(["SH", "B35S", "B45S", "RP"], choice="PR2")
    out = dict(all=dict(need=d["total_need_gb"], keep=d["total_keep_gb"], peak=d["peak_extra_gb"], without=d["total_all_gb"],
                        rows=[dict(stage=r["stage"], made_max=r["made_max"], end=r["end"], peak=r["peak"], keep_gb=round(r["keep_gb"], 2), all_gb=round(r["all_gb_max"], 2))
                              for r in d["rows"]]), seconds=t1 - t0,
               night2=dict(need=d2["total_need_gb"], without=d2["total_all_gb"]))
    # 並びの始めの確かめ：空きが少ない時に止まるか、--disk-ok で進むか（空きを差し替える。dry-run・関数を直に）
    TAG = time.strftime("%H%M%S")
    R = FXR + "/k5_" + TAG
    Q.setup(R, dry=True); Q.AGREED = AG
    real = shutil.disk_usage
    res = {}
    try:
        for name, free_gib, ok in (("free_40", 40.0, False), ("free_40_ok", 40.0, True), ("free_300", 300.0, False)):
            Q.shutil.disk_usage = lambda p, f=free_gib: types.SimpleNamespace(free=f * 2**30, total=1, used=1)
            try:
                Q.disk_check(["PR1", "PR2", "SELECT", "PR3", "SH", "B35S", "B45S", "RP", "TABLE"], {}, ok); code = 0
            except SystemExit as e:
                code = e.code
            res[name] = code
    finally:
        Q.shutil.disk_usage = real
    out["disk_check"] = res
    out["stop_tail"] = lines(B44 + "/" + R + "/QUEUE_STOP.txt")[-1:]
    save("k5", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:3000])


# ================================================================== k6：直した側の hython の試しの記録を読み直す
def t_k6():
    import g44_online as O
    out = {}
    h2 = glob.glob(B44 + "/fixes2/h2_*/*")
    rd = [d for d in glob.glob(B44 + "/fixes2/h2_*") if os.path.isdir(d)][0]
    recs = sorted(glob.glob(rd + "/run_c*.json"))
    rr = [jl(p) for p in recs]
    s8 = B44 + "/smoke/S8"
    # 一番上の水面（hf の eta）を S8 と比べる
    def hf_all(d):
        F = {}
        for p in sorted(glob.glob(d + "/hf_c*.npz")):
            z = np.load(p)
            key = [k for k in z.files if k not in ("frames", "wall", "t", "npts", "lvl", "meta")]
            for i, f in enumerate(z["frames"]):
                F[int(f)] = (p, i)
        return F
    a = hf_all(rd); b = hf_all(s8)
    common = sorted(set(a) & set(b))
    same = 0; diff = []
    keys_used = None
    for f in common:
        za = np.load(a[f][0]); zb = np.load(b[f][0])
        ka = [k for k in za.files if za[k].ndim >= 2 and za[k].shape[0] == len(za["frames"])]
        keys_used = ka
        ok = True
        for k in ka:
            if k in zb.files and not np.array_equal(za[k][a[f][1]], zb[k][b[f][1]], equal_nan=True):
                ok = False
        same += ok
        if not ok and len(diff) < 5:
            diff.append(f)
    L = jl(rd + "/ckpt_ledger.json") if os.path.exists(rd + "/ckpt_ledger.json") else {}
    out["h2"] = dict(dir=rd, launches=[(r["f_start"], r["f_end_done"], r["stopped"], r.get("priority")) for r in rr],
                     touchdown_online=[(r.get("info") or {}).get("touchdown_online", {}).get("frame") for r in rr],
                     common_frames=len(common), bit_same_frames=same, diff_frames=diff, keys=keys_used,
                     ledger=dict(made=sorted(int(k) for k in L.get("made", {})), would=sorted(int(k) for k in L.get("would_prune", {})),
                                 pruned=sorted(int(k) for k in L.get("pruned", {})), verified=L.get("verified")),
                     ckpt_files=sorted(os.listdir(rd + "/ckpt")) if os.path.isdir(rd + "/ckpt") else None)
    rd3 = [d for d in glob.glob(B44 + "/fixes2/h3_*") if os.path.isdir(d)][0]
    r3 = [jl(p) for p in sorted(glob.glob(rd3 + "/run_c*.json"))]
    out["h3"] = dict(dir=rd3, launches=[(r["f_start"], r["f_end_done"], r["stopped"], (r.get("info") or {}).get("online_restored")) for r in r3])
    save("k6", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


if __name__ == "__main__":
    print(lower_self())
    os.makedirs(FX, exist_ok=True)
    for k in sys.argv[1:]:
        globals()["t_" + k]()
