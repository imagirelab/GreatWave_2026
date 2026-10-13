# -*- coding: utf-8 -*-
"""FLIP44：3 回目の確かめ（check/check_fixes2_ja.md）の H1・H7 の直し（record_ja.md §3.3）の試し。py -3.10。
流体の計算（hython）は走らせない。自分の優先度を「通常より下」にし、子の py も「通常より下」で起こす。
書くのは Unity/Build/FLIP44/fixes3/ だけ。ファイルは消さない（途中保存を消す道は、os.remove を差し替えて試しのフォルダーの中の _moved/ へ動かす）。
  ck3a：形の本番の起動の真似（g44_hours、下見の巻き始め 140〜165 s × 機械の重さ 1.0・1.33）の上で after_launch を本当に動かし、
        巻き始め t_on ＝ 下見 + δ（−20〜+9 s）で prune_after_onset を本当に動かす。風の計算の始め（t_on − 3 s より前の最後の途中保存）が
        消さない時と同じか、残る数、計算の間に何も消さないか
  ck3b：並びの dry-run（--from SH）：形の本番の巻き始めが下見より 5 s 早い。SH の段が片付け（dry なので消すはずの物を書くだけ）をして、
        B35S・B45S が計画の始めから走る設定になるか
  ck3c：片付けを本当に動かした後（動かす形）に並びの dry-run（--only B35S）：始めが同じで、報告に余計な行がないか
  ck3d：計画の始めがない時の言葉：前の版の決まりで消した・帳面にあるのにない・作っていない・片付けの時に始めがない（何も消さない）
  ck3e：1 本ずつの道（ckpt_keep なし）の後に並びが同じフォルダーで続ける（c44_fix2_check の g_single_then_queue と同じ形）、origin のない古い帳面、
        風の計算の元の写しの origin
  ck3f：消す途中で 1 個が消せない時の帳面（H6）
  ck3g：置き場所の見込み（全部の段・2 晩目からの段）
  c44 ：確かめの道具 c44_fix2_check.py の k4（g_single_then_queue を含む）・k4e・k5・k1 を、道具を変えずに走らせる（出力だけ fixes3/c44 へ）
出力：Unity/Build/FLIP44/fixes3/fix3_tests.json
"""
import sys, os, json, glob, shutil, subprocess, time, ctypes, types
from ctypes import wintypes

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip44"
B44 = REPO + "/Unity/Build/FLIP44"
FXR = "fixes3"
FX = B44 + "/" + FXR
RES = FX + "/fix3_tests.json"
FPS = 24.0
AG = "x44_fix3_tests の試し（本番ではない）"
sys.path.insert(0, TOOLS)
DELTAS = [-20.0, -9.0, -7.0, -5.0, -4.0, -3.5, -3.0, -2.5, -1.0, 0.0, 1.0, 3.0, 6.0, 9.0]
ONSETS = (140.0, 145.0, 150.0, 155.0, 160.0, 165.0)
LOADS = (1.0, 1.33)


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


def lines(p):
    return open(p, encoding="utf8").read().strip().splitlines() if os.path.exists(p) else []


def queue(root, args, enc="cp932"):
    env = dict(os.environ); env.pop("PYTHONUTF8", None); env["PYTHONIOENCODING"] = enc
    r = subprocess.run([sys.executable, "g44_queue.py", "--agreed", AG, "--root", root, "--dry-run"] + args, cwd=TOOLS, capture_output=True, env=env,
                       creationflags=0x00004000)
    txt = (r.stdout.decode(enc, "replace") + r.stderr.decode(enc, "replace")).strip()
    return r.returncode, ("Traceback" in txt), txt.splitlines()[-3:]


class Mover:
    """os.remove の代わり：試しのフォルダーの中の _moved/ へ動かす。fail_at（何回目か）で PermissionError を出す。"""
    def __init__(self, rd, fail_at=None):
        self.rd = rd; self.moved = []; self.n = 0; self.fail_at = fail_at
        os.makedirs(rd + "/_moved", exist_ok=True)

    def remove(self, p):
        self.n += 1
        if self.fail_at is not None and self.n == self.fail_at:
            raise PermissionError("試し：ほかの処理が使っている")
        self.moved.append(int(os.path.basename(p)[2:6]))
        os.replace(p, os.path.join(self.rd, "_moved", os.path.basename(p)))


def patched(K, mv):
    K.os = types.SimpleNamespace(path=os.path, remove=mv.remove)


def unpatch(K):
    K.os = os


def write_ck(rd, k, size=1000):
    os.makedirs(rd + "/ckpt", exist_ok=True)
    open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\1" * size)


def replay(K, rd, cfg, trace, size=lambda k: 1000):
    """g44_chain の起動の決まりの上で after_launch を本当に動かす（消す物は Mover が動かす）。返り値：起動ごとの行。"""
    rows = []
    for L in trace:
        have = K.ckpt_frames(rd)
        start_ok = (L["f0"] == 1) or ((L["f0"] - 1) in have)
        before = list(have)
        for k in L["cks"]:
            write_ck(rd, k, size(k))
        r = K.after_launch(rd, cfg, L["f0"], L["done"], before, 2.0, 1.0, log=lambda *a: None)
        rows.append(dict(f0=L["f0"], start_ok=start_ok, deleted=r["deleted"], would=r["would"], why=r["why"]))
    return rows


def sh_trace(H, onset_pre, load):
    P = H.plan(); Tc = P["tank"]["Tc"]
    tr = []
    r = H.est_SH(onset_pre, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, load, Tc, trace=tr)
    return tr, r, Tc


# ================================================================== ck3a：巻き始めのずれ
def t_ck3a():
    import g44_ckpt as K
    import g44_hours as H
    D = FX + "/ck3a_" + time.strftime("%H%M%S")
    rows = []
    during = []
    for onset_pre in ONSETS:
        for load in LOADS:
            tr, r, Tc = sh_trace(H, onset_pre, load)
            f_w = r["f_w"]
            pol = K.keep_policy("SH", onset_pre=onset_pre, f_w=f_w, Tc=Tc)
            allk = sorted(set(k for L in tr for k in L["cks"]))
            for d in DELTAS:
                rd = D + "/SH_%g_%g_%+g" % (onset_pre, load, d)
                mv = Mover(rd)
                patched(K, mv)
                try:
                    rr = replay(K, rd, dict(out_root="runs", ckpt_keep=pol), tr)
                    left_during = K.ckpt_frames(rd)
                    t_on = onset_pre + d
                    pr = K.prune_after_onset(rd, t_on, f_w=f_w, real=True, log=lambda *a: None)
                finally:
                    unpatch(K)
                left = K.ckpt_frames(rd)
                want = [k for k in allk if (k - 1) / FPS < t_on - 3.0]
                w = K.wind_start(rd, t_on)
                if d == 0.0:
                    during.append(dict(onset_pre=onset_pre, load=load, launches=len(tr), made=len(allk), moved_during_run=sum(len(x["deleted"]) for x in rr),
                                       all_kept_during_run=(left_during == allk), all_starts_ok=all(x["start_ok"] for x in rr)))
                rows.append(dict(onset_pre=onset_pre, load=load, delta=d, f_w=f_w, made=len(allk), plan_start=(want[-1] if want else None),
                                 start=pr["start"], wind_start=w["start"], same=bool(want and pr["start"] == want[-1] and w["start"] == want[-1]),
                                 why=w["why_ja"], left=left, n_left=len(left), moved=len(mv.moved),
                                 extra_kept=sorted(set(left) - {want[-1] if want else None, f_w, allk[-1]})))
    nbad = [x for x in rows if not x["same"]]
    out = dict(dir=D, n=len(rows), n_start_same=len(rows) - len(nbad), bad=[(x["onset_pre"], x["load"], x["delta"], x["plan_start"], x["start"], x["why"]) for x in nbad],
               n_left_range=[min(x["n_left"] for x in rows), max(x["n_left"] for x in rows)], made_range=[min(x["made"] for x in rows), max(x["made"] for x in rows)],
               any_extra_kept=[(x["onset_pre"], x["load"], x["delta"], x["extra_kept"]) for x in rows if x["extra_kept"]],
               during_run=during, rows=rows)
    save("ck3a", out)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, default=float)[:4000])


# ================================================================== ck3b・ck3c：並びの dry-run
def _prep_queue_root(K, H, R, onset_pre=155.0, delta=-5.0, load=1.0):
    """試しの置き場所：選び PR2（確かめ済み）、PR2 の解析（巻き始め onset_pre）、形の本番の途中保存（起動の真似の上で after_launch が帳面に書いた物）、
    形の本番の解析（巻き始め onset_pre + delta）。"""
    D = B44 + "/" + R
    a = jl(B44 + "/check/ana44_R3.json")
    pre = json.loads(json.dumps(a)); pre["onset"]["t"] = onset_pre
    jw(D + "/PR2/ana.json", pre)
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True)))
    tr, r, Tc = sh_trace(H, onset_pre, load)
    pol = K.keep_policy("SH", onset_pre=onset_pre, f_w=r["f_w"], Tc=Tc)
    mv = Mover(D + "/SH")
    patched(K, mv)
    try:
        rows = replay(K, D + "/SH", dict(out_root="runs", ckpt_keep=pol), tr)
    finally:
        unpatch(K)
    sh = json.loads(json.dumps(a)); sh["onset"]["t"] = onset_pre + delta; sh["touchdown"]["t"] = onset_pre + delta + 1.3
    sh.pop("onset_at_path_start", None)
    jw(D + "/SH/ana.json", sh)
    allk = sorted(set(k for L in tr for k in L["cks"]))
    want = max(k for k in allk if (k - 1) / FPS < onset_pre + delta - 3.0)
    return D, r["f_w"], allk, want, mv, rows


def t_ck3b():
    import g44_ckpt as K
    import g44_hours as H
    R = FXR + "/ck3b_" + time.strftime("%H%M%S")
    D, f_w, allk, want, mv, rows = _prep_queue_root(K, H, R)
    rc, tb, tail = queue(R, ["--from", "SH"])
    L = K.load_ledger(D + "/SH")
    S = jl(D + "/queue_state.json")
    b35 = jl(D + "/B35S/cfg_queue.json") if os.path.exists(D + "/B35S/cfg_queue.json") else {}
    b45 = jl(D + "/B45S/cfg_queue.json") if os.path.exists(D + "/B45S/cfg_queue.json") else {}
    shc = jl(D + "/SH/cfg_queue.json") if os.path.exists(D + "/SH/cfg_queue.json") else {}
    out = dict(root=R, rc=rc, traceback=tb, tail=tail, f_w_cfg=(shc.get("case") or {}).get("f_w"), f_w_replay=f_w, sh_keep=shc.get("ckpt_keep"),
               made=len(allk), moved_during_run=len(mv.moved), plan_start=want,
               B35S_from=(b35.get("from_ckpt") or {}).get("frame"), B45S_from=(b45.get("from_ckpt") or {}).get("frame"),
               files_after=len(K.ckpt_frames(D + "/SH")), would_prune=len(L["would_prune"]), pruned=len(L["pruned"]),
               after_onset=L.get("after_onset"), state_SH_ckpt=(S.get("SH") or {}).get("ckpt"), report=lines(D + "/QUEUE_REPORT.txt"),
               disk_plan=lines(D + "/DISK_PLAN_ja.md"))
    save("ck3b", out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("disk_plan", "after_onset")}, ensure_ascii=False, default=float)[:4000])


def t_ck3c():
    import g44_ckpt as K
    import g44_hours as H
    R = FXR + "/ck3c_" + time.strftime("%H%M%S")
    D, f_w, allk, want, mv, rows = _prep_queue_root(K, H, R)
    sh = jl(D + "/SH/ana.json")
    jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True),
                                     SH=dict(onset=sh["onset"], touchdown=sh["touchdown"], still=sh.get("still_level_offset_m", 0.16))))
    mv2 = Mover(D + "/SH")
    patched(K, mv2)
    try:
        pr = K.prune_after_onset(D + "/SH", sh["onset"]["t"], f_w=f_w, real=True, log=lambda *a: None)
    finally:
        unpatch(K)
    left = K.ckpt_frames(D + "/SH")
    rc, tb, tail = queue(R, ["--only", "B35S"])
    b35 = jl(D + "/B35S/cfg_queue.json") if os.path.exists(D + "/B35S/cfg_queue.json") else {}
    out = dict(root=R, plan_start=want, prune_start=pr["start"], moved=len(mv2.moved), left=left, report_prune=pr["report_ja"], rc=rc, traceback=tb,
               B35S_from=(b35.get("from_ckpt") or {}).get("frame"), queue_report=lines(D + "/QUEUE_REPORT.txt"))
    save("ck3c", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


# ================================================================== ck3d：計画の始めがない時の言葉
def t_ck3d():
    import g44_ckpt as K
    TAG = time.strftime("%H%M%S")
    a = jl(B44 + "/check/ana44_R3.json")
    out = {}
    t_on = 150.0       # t_on − 3 s ＝ 147 s → 3,528 コマより前
    cases = {
        # 名前：(残すファイル, 帳面の made（origin queue）, 帳面の pruned（前の版の書き方：why なし）)
        "old_rule_pruned_none_left": ([3576, 3600], [3278, 3576, 3600], {"3278": dict(bytes=1000, time="2026-10-12 06:20:00", newest=3576)}),
        "old_rule_pruned_earlier_left": ([2980, 3576, 3600], [2980, 3278, 3576, 3600], {"3278": dict(bytes=1000, time="2026-10-12 06:20:00", newest=3576)}),
        "made_but_missing": ([2980, 3576], [2980, 3278, 3576], {}),
        "never_made": ([3576, 3600], [3576, 3600], {}),
    }
    for name, (files, made, pruned) in cases.items():
        R = FXR + "/ck3d_%s_%s" % (name, TAG); D = B44 + "/" + R
        for k in files:
            write_ck(D + "/SH", k)
        L = K.load_ledger(D + "/SH")
        for k in made:
            L["made"][str(k)] = dict(bytes=1000, time="2026-10-12 06:00:00", how="launch", launch=1, origin="queue")
        L["pruned"].update(pruned)
        K.save_ledger(D + "/SH", L)
        w = K.wind_start(D + "/SH", t_on)
        # 片付け（巻き始めが決まった後）：始めが計画どおりでないので何も消さないか（動かす形で本当に呼ぶ）
        mv = Mover(D + "/SH"); patched(K, mv)
        try:
            pr = K.prune_after_onset(D + "/SH", t_on, f_w=3576, real=True, log=lambda *a: None)
        finally:
            unpatch(K)
        sh = json.loads(json.dumps(a)); sh["onset"]["t"] = t_on; sh["touchdown"]["t"] = t_on + 1.3
        jw(D + "/queue_state.json", dict(select=dict(choice="PR2", confirmed=True),
                                         SH=dict(onset=sh["onset"], touchdown=sh["touchdown"], still=0.16)))
        rc, tb, tail = queue(R, ["--only", "B35S"])
        b35 = jl(D + "/B35S/cfg_queue.json") if os.path.exists(D + "/B35S/cfg_queue.json") else {}
        out[name] = dict(wind_start=w, prune_moved=mv.moved, prune_report=pr["report_ja"], rc=rc, traceback=tb,
                         B35S_from=(b35.get("from_ckpt") or {}).get("frame"), report=lines(D + "/QUEUE_REPORT.txt"),
                         state_wind=(jl(D + "/queue_state.json").get("wind") or {}).get("B35S"))
    save("ck3d", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:6000])


# ================================================================== ck3e：1 本ずつの道の後に並び（H7）
def t_ck3e():
    import g44_ckpt as K
    import g44_hours as H
    TAG = time.strftime("%H%M%S")
    P = H.plan(); Tc = P["tank"]["Tc"]
    out = {}
    # (1) c44_fix2_check の g_single_then_queue と同じ形：下見の起動の真似の 3 回を ckpt_keep なしで、続く 2 回を並びの決まりで
    tr = []; H.est_PR(155.0, P["programs"]["PR2_reef_aim500"]["aim_t_s"], 1.0, 1.0, Tc, trace=tr)
    rd = FX + "/ck3e_mixed_" + TAG
    mv = Mover(rd); patched(K, mv)
    try:
        r1 = replay(K, rd, dict(out_root="runs"), tr[:3])
        made_single = sorted(int(k) for k in K.load_ledger(rd)["made"])
        r2 = replay(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), tr[3:])
    finally:
        unpatch(K)
    L = K.load_ledger(rd)
    out["single_then_queue"] = dict(made_by_single=made_single, origins_single=sorted(set(L["made"][str(k)]["origin"] for k in made_single)),
                                    moved_by_queue=sorted(mv.moved), single_moved=sorted(set(mv.moved) & set(made_single)),
                                    queue_made=sorted(int(k) for k, v in L["made"].items() if v.get("origin") == "queue"),
                                    left=K.ckpt_frames(rd), all_starts_ok=all(x["start_ok"] for x in r1 + r2))
    # (2) 形の本番：1 本ずつの道で作った物は、巻き始めの後の片付けでも消さない
    tr, r, Tc = sh_trace(H, 155.0, 1.0)
    rd = FX + "/ck3e_sh_single_" + TAG
    mv = Mover(rd); patched(K, mv)
    try:
        replay(K, rd, dict(out_root="runs"), tr[:6])
        made_single = sorted(int(k) for k in K.load_ledger(rd)["made"])
        replay(K, rd, dict(out_root="runs", ckpt_keep=K.keep_policy("SH", onset_pre=155.0, f_w=r["f_w"], Tc=Tc)), tr[6:])
        pr = K.prune_after_onset(rd, 152.0, f_w=r["f_w"], real=True, log=lambda *a: None)
    finally:
        unpatch(K)
    out["sh_single_then_queue"] = dict(made_by_single=made_single, moved=sorted(mv.moved), single_moved=sorted(set(mv.moved) & set(made_single)),
                                       start=pr["start"], report=pr["report_ja"])
    # (3) origin のない古い帳面（前の版が書いた物）：消さない
    rd = FX + "/ck3e_oldledger_" + TAG
    for k in (240, 480, 720, 960):
        write_ck(rd, k)
    L = K.load_ledger(rd)
    for k in (240, 480, 720):
        L["made"][str(k)] = dict(bytes=1000, time="2026-10-12 06:00:00", how="launch", launch=1)
    K.save_ledger(rd, L)
    mv = Mover(rd); patched(K, mv)
    try:
        r3 = K.after_launch(rd, dict(out_root="runs", ckpt_keep=K.keep_policy("PR")), 961, 1000, [240, 480, 720], 2.0, 1.0, log=lambda *a: None)
    finally:
        unpatch(K)
    out["old_ledger_no_origin"] = dict(moved=mv.moved, left=K.ckpt_frames(rd), new_origin=K.load_ledger(rd)["made"]["960"].get("origin"))
    # (4) 風の計算の元の写し：g44_chain の写しの書き方（並びの chain なら queue、1 本ずつなら single）
    src = open(TOOLS + "/g44_chain.py", encoding="utf8").read()
    out["chain_copy_origin_line"] = [l.strip() for l in src.splitlines() if "copy from" in l and "note_made" in l]
    rdq = FX + "/ck3e_copy_" + TAG
    for name, cfg in (("queue", dict(ckpt_keep=K.keep_policy("B"))), ("single", {})):
        rdx = rdq + "_" + name
        write_ck(rdx, 3576)
        Lx = K.load_ledger(rdx)
        K.note_made(rdx, Lx, [3576], "copy from SH", origin="queue" if cfg.get("ckpt_keep") else "single")
        K.save_ledger(rdx, Lx)
        out["copy_origin_" + name] = K.load_ledger(rdx)["made"]["3576"]["origin"]
    save("ck3e", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


# ================================================================== ck3f：消す途中で 1 個が消せない（H6）
def t_ck3f():
    import g44_ckpt as K
    rd = FX + "/ck3f_" + time.strftime("%H%M%S")
    for k in (240, 480, 720):
        write_ck(rd, k)
    cfg = dict(out_root="runs", ckpt_keep=K.keep_policy("PR"))
    mv = Mover(rd); patched(K, mv)
    try:
        K.after_launch(rd, cfg, 1, 730, [], 2.0, 1.0, log=lambda *a: None)
        for k in (960, 1200):
            write_ck(rd, k)
        mv2 = Mover(rd, fail_at=2); patched(K, mv2)
        err = None
        try:
            r = K.after_launch(rd, cfg, 721, 1210, [240, 480, 720], 2.0, 1.0, log=lambda *a: None)
        except Exception as e:
            err = repr(e); r = {}
    finally:
        unpatch(K)
    L = K.load_ledger(rd)
    out = dict(error=err, first_moved=mv.moved, second_moved=mv2.moved, failed=r.get("failed"), files_left=K.ckpt_frames(rd),
               ledger_pruned=sorted(int(k) for k in L["pruned"]), ledger_failed=sorted(int(k) for k in L["prune_failed"]), verified=L["verified"])
    save("ck3f", out)
    print(json.dumps(out, ensure_ascii=False))


# ================================================================== ck3g：置き場所の見込み
def t_ck3g():
    import g44_ckpt as K
    d = K.disk_plan(["PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP"])
    d2 = K.disk_plan(["SH", "B35S", "B45S", "RP"], choice="PR2")
    d1 = K.disk_plan(["PR1", "PR2"])
    f = lambda x: dict(need=x["total_need_gb"], keep=x["total_keep_gb"], peak=x["peak_extra_gb"], without=x["total_all_gb"],
                       rows=[dict(stage=r["stage"], ckpt_gb=round(r["ckpt_gb"], 3), made_max=r["made_max"], end=r["end"], peak=r["peak"],
                                  records_gb=round(r["records_gb"], 2), keep_gb=round(r["keep_gb"], 2), peak_extra_gb=round(r["peak_extra_gb"], 2),
                                  all_gb=round(r["all_gb_max"], 2), load=r["load"], onset=r["onset"]) for r in x["rows"]])
    free = shutil.disk_usage("G:/").free / 2**30
    out = dict(all=f(d), night2_PR2=f(d2), night1=f(d1), free_gib=free)
    open(FX + "/DISK_PLAN_all_ja.md", "w", encoding="utf8").write(K.plan_md(d, free, 25.0, "runs"))
    save("ck3g", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


# ================================================================== c44：確かめの道具を変えずに、出力だけ fixes3/c44 へ向けて走らせる
def t_c44():
    """check の c44_fix2_check.py の k4（g_single_then_queue を含む）・k4e・k5・k1 を、その道具を変えずに走らせる。書く所だけ fixes3/c44 と
    fixes3/c44_fix2_check_rerun.json へ向ける（確かめの結果 check/c44_fix2_check.json は書き換えない）。"""
    import c44_fix2_check as C4
    C4.FXR = FXR + "/c44"; C4.FX = B44 + "/" + C4.FXR; C4.RES = FX + "/c44_fix2_check_rerun.json"
    os.makedirs(C4.FX, exist_ok=True)
    for k in ("k4", "k4e", "k5", "k1"):
        getattr(C4, "t_" + k)()


if __name__ == "__main__":
    print(lower_self())
    os.makedirs(FX, exist_ok=True)
    for k in sys.argv[1:]:
        globals()["t_" + k]()
