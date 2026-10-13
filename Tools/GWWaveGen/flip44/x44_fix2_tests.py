# -*- coding: utf-8 -*-
"""FLIP44：2 回目の確かめ（check/check_fixes_ja.md の G1〜G8 と、計算の中の着水の読み）の直しの試し（py -3.10）。
流体の計算は走らせない（h1・h2 だけ hython を数分。ほかの hython が動いている間は待つ）。自分の優先度を「通常より下」にし、電力の抑えを外す。
子の py も「通常より下」で起こす。試しの物は全部 Unity/Build/FLIP44/fixes2/ に作る。smoke/・runs/・check/・fixes/・FLIP42 は読むだけ。
ファイルは消さない（途中保存を消す決まりの試しは「消すはずの物」を書くだけ）。
  td  ：計算の中の着水の読み（TouchdownWatch：空気の穴＋唇の先）を、今ある記録（FLIP42 R2・R3・R4d、煙の試し S8）にかけ、解析の着水と比べる
  q1  ：G1（確かめのない段・状態のない段が traceback でなく QUEUE_STOP.txt で止まる）、G8（RP の古い途中保存）、引数の誤り（dry-run）
  q3  ：G3（下見 3 本目の道を最後まで dry-run で通す。狙いの入口を凍結した道具と同じ計算で fixes2 へ書く）
  q4  ：G4（下見 1 の解析が止まっても下見 2 へ進み、選びで止まる）。計算は走らせず、解析は本当に走らせる
  g5  ：G5（断面が巻き始めより後から始まる記録で notes に書く）
  g6  ：G6（g44_cfg の wind_on・wind_mode の上書き、g44_online.wind_guard）。runs/ready の 4 つを作り直して同じか
  g7  ：G7（g44_ctable の表示を cp932 で）
  g8  ：G8（chain_result が古い STOPPED_BY_RULE.txt を読まない）
  ck  ：G2（途中保存の残し方の決まり。作った空のファイルで、消すはずの物を数える）と、置き場所の見込み（DISK_PLAN_ja.md）
  aw  ：夜の間に PC を眠らせない呼び出し（SetThreadExecutionState）が返るか
  h1  ：hython：g44_run.py の守り（mode 2・form と wind_on 0）が、場面を読む前に拒むか
  h2  ：hython：S8 の 1,152 コマの途中保存から g44_chain.py で数回の起動に分けて走らせ、計算の中の着水の読みと途中保存の残し方（消さない形）を通す
  h3  ：hython：g44_run.py を 2 回に分け、前の起動で見つけた着水を次の起動が引き継ぐか（h2 の途中保存の写しから）
出力：Unity/Build/FLIP44/fixes2/fix2_tests.json（試しごとに足す）
"""
import sys, os, json, glob, shutil, subprocess, time, ctypes
from ctypes import wintypes
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip44"
B44 = REPO + "/Unity/Build/FLIP44"
R42 = REPO + "/Unity/Build/FLIP42/runs"
FXR = "fixes2"
FX = B44 + "/" + FXR
RES = FX + "/fix2_tests.json"
sys.path.insert(0, TOOLS)
FPS = 24.0


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
    os.makedirs(FX, exist_ok=True)
    d = json.load(open(RES, encoding="utf8")) if os.path.exists(RES) else {}
    d[key] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), **val)
    json.dump(d, open(RES, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


def py(args, enc="utf-8", cwd=TOOLS, env_extra=None):
    """子の py を「通常より下」で起こす。enc="cp932" の時は標準出力を cp932 にする（Git Bash やファイルへ流した時と同じ）。"""
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env["PYTHONIOENCODING"] = enc
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, env=env, creationflags=0x00004000)
    return r.returncode, r.stdout.decode(enc, errors="replace"), r.stderr.decode(enc, errors="replace")


def jl(p):
    return json.load(open(p, encoding="utf8"))


def jw(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


# ------------------------------------------------------------------ td：計算の中の着水の読みを今ある記録で
def sec_best(rd):
    best = {}
    meta = None
    for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
        f0 = int(os.path.basename(p)[5:9]); d = np.load(p)
        m = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i, json.dumps([m["res"], m["x0"], m["nx"], m["y0"]]))
        meta = meta or {}
        meta[json.dumps([m["res"], m["x0"], m["nx"], m["y0"]])] = m
    return best, meta


def cavity_frame_old(sl, xs, ys, Lc, vox, off, parms):
    """直す前の g44_online.cavity_frame（2026-10-12 05:00 の版をそのまま写した。比べるためだけ）。"""
    import g44_online as O
    water = sl < 0
    bed = ys[:, None] < (O.bed_y(parms, xs)[None, :] + 0.5 * vox)
    air = (~water) & (~bed)
    wy = np.where(water.any(1))[0]
    if len(wy) == 0:
        return None
    jt = wy.max()
    ic = int(np.where(water[jt])[0].mean())
    xc = xs[ic]; yc = ys[jt]
    m = (xs >= xc - 0.25 * Lc) & (xs <= xc + 0.75 * Lc)
    Am = air[:, m]
    reach = np.zeros_like(Am)
    reach[-1, :] = Am[-1, :]; reach[:, 0] |= Am[:, 0]; reach[:, -1] |= Am[:, -1]
    for _ in range(4000):
        r2 = reach.copy()
        r2[1:, :] |= reach[:-1, :]; r2[:-1, :] |= reach[1:, :]; r2[:, 1:] |= reach[:, :-1]; r2[:, :-1] |= reach[:, 1:]
        r2 &= Am
        if (r2 == reach).all():
            break
        reach = r2
    hole = Am & ~reach
    area = float(hole.sum()) * (xs[1] - xs[0]) * (ys[1] - ys[0])
    if area < vox * vox:
        return dict(xc=float(xc), yc=float(yc - off), area=area, found=False)
    jj, ii = np.where(hole)
    cy = float(ys[jj].mean()); cx = float(xs[m][ii].mean())
    return dict(xc=float(xc), yc=float(yc - off), area=area, cx=cx, cy=cy - off, found=bool(cy < yc))


def td_one(rd, cfg, off, f_on, f_td, tip_wait_s=2.0, extra_after=48):
    """解析の巻き始め − 1 s から、解析の着水 + extra_after コマまで、毎コマ TouchdownWatch（新しい読み）と、直す前の空気の穴の読みに通す。"""
    import g44_online as O
    best, metas = sec_best(rd)
    vox = 2.0 * float(cfg["parms"]["dp"])
    xp = cfg["parms"]["x_p"]
    st = dict(after_s=0.5, t_from=(f_on - 1) / FPS - 1.0, Lc=135.46329754326246, still_offset_m=off, tip_wait_s=tip_wait_s)
    W = O.TouchdownWatch(st, vox, cfg["parms"], FPS)
    cache = {}
    tips = []; stop = None; old_first = None; t_cost = []
    for f in range(f_on - 24, f_td + extra_after + 1):
        if f not in best:
            continue
        f0, p, i, key = best[f]
        if p not in cache:
            cache.clear(); cache[p] = np.load(p)["sdf"]
        sl = cache[p][i].astype(np.float32)
        m = metas[key]
        xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
        t = (f - 1) / FPS
        if stop is None:
            t0 = time.time()
            W.step(f, t, sl, xs, ys)
            t_cost.append(time.time() - t0)
            s = W.should_stop(t)
            stop = (f, s) if s else None
        if old_first is None and t >= st["t_from"] - 1e-9:
            c = cavity_frame_old(sl, xs, ys, st["Lc"], vox, off, cfg["parms"])
            if c and c["found"]:
                old_first = dict(frame=f, area=c["area"], cx_rel=c["cx"] - xp, cy=c["cy"], xc_rel=c["xc"] - xp)
        lt = O.lip_tip(sl, xs, ys, st["Lc"], vox, off, cfg["parms"])
        if lt and lt.get("y_tip") is not None:
            tips.append([f, round(lt["y_tip"], 3), lt["over_cols"], round(lt["x_tip"] - xp, 1), bool(lt["found"])])
        if stop is not None and old_first is not None and f > f_td + 2:
            break
    td = dict(W.td) if W.td else None
    if td:
        for k in ("xc", "cx"):
            if k in td:
                td[k + "_rel"] = td.pop(k) - xp
    return dict(f_onset_ana=f_on, f_touchdown_ana=f_td, cavity_old_first=old_first, cavity_new=td, tip_online=W.tip,
                stop_new=stop, stop_old=(old_first["frame"] + 12) if old_first else None,
                record_has_touchdown_new=bool(stop and stop[0] >= f_td),
                record_has_touchdown_old=bool(old_first and old_first["frame"] + 12 >= f_td),
                tip_first_found_frame=next((r[0] for r in tips if r[4]), None),
                tip_y_at_ana_touchdown=next((r[1] for r in tips if r[0] == f_td), None), tips_head=tips[:80],
                ms_per_frame_median=1000 * float(np.median(t_cost)) if t_cost else None)


def synth_lip(tip_y, trough=-2.5, thick=1.5, dx=0.5):
    """作った断面：x ≤ 100 m は頂 8 m の水、その前は谷 trough。唇は (100, 7) から (106, tip_y) へ放物線で下りる厚さ thick の水。"""
    xs = np.arange(0.0, 200.0 + 1e-9, dx); ys = np.arange(-44.0, 18.0 + 1e-9, dx)
    X, Y = np.meshgrid(xs, ys)
    water = np.where(X <= 100.0, Y < 8.0, Y < trough)
    u = np.clip((X - 100.0) / 6.0, 0, 1)
    yc = 7.0 - (7.0 - tip_y) * u * u
    lip = (X > 100.0) & (X <= 106.0) & (np.abs(Y - yc) <= 0.5 * thick)
    water = water | lip
    return np.where(water, -1.0, 1.0).astype(np.float32), xs, ys


def t_td():
    import g44_online as O
    out = {}
    for rid in ("R3", "R2", "R4d"):
        rd = os.path.join(R42, rid)
        cfg = jl(rd + "/cfg.json"); a = jl(rd + "/ana.json")
        out[rid] = td_one(rd, cfg, a["still_level_offset_m"], a["onset"]["frame"], a["touchdown"]["frame"])
    # 煙の試し S8（礁あり、粒子 0.5 m）。主な頂は 300 m より手前なので、解析の全部の頂のうち巻き始めと着水のある頂
    rd = B44 + "/smoke/S8"
    cfg = jl(rd + "/cfg.json"); a = jl(rd + "/ana.json")
    e = [e for e in a["events"] if e.get("onset") and e.get("touchdown")][0]
    out["S8"] = td_one(rd, cfg, a["still_level_offset_m"], e["onset"]["frame"], e["touchdown"]["frame"])
    out["S8"]["event_x_rel"] = e["onset"]["xc_rel"]
    # 作った断面で唇の先の読み
    parms = dict(h0=42.0, reef_on=0.0, x_p=0.0)
    syn = {}
    for name, ty, tr in (("tip_below", -0.5, -2.5), ("tip_above", 2.0, -2.5), ("tip_touches_trough", -0.5, -0.75)):
        sl, xs, ys = synth_lip(ty, tr)
        lt = O.lip_tip(sl, xs, ys, 135.46329754326246, 0.5, 0.0, parms)
        cav = O.cavity_frame(sl, xs, ys, 135.46329754326246, 0.5, 0.0, parms)
        syn[name] = dict(lip=lt, cavity_found=bool(cav and cav["found"]))
    # 2 コマ続けて見つけた唇の先の tip_wait_s 後で止まり、その間に空気の穴が見つかれば穴の 0.5 s 後で止まるか
    sl_b, xs, ys = synth_lip(-0.5, -2.5)
    W = O.TouchdownWatch(dict(after_s=0.5, t_from=0.0, Lc=135.46329754326246, still_offset_m=0.0, tip_wait_s=2.0), 0.5, parms)
    stops = []
    for f in range(1, 80):
        t = (f - 1) / FPS
        W.step(f, t, sl_b, xs, ys)
        s = W.should_stop(t)
        if s:
            stops.append((f, s)); break
    syn["watch_tip_only"] = dict(tip=W.tip, stop=stops)
    W2 = O.TouchdownWatch(dict(after_s=0.5, t_from=0.0, Lc=135.46329754326246, still_offset_m=0.0, tip_wait_s=2.0), 0.5, parms)
    sl_c, _, _ = synth_lip(-0.5, -0.75)       # 唇が谷に届いて空気を囲んだ形
    stops2 = []
    for f in range(1, 80):
        t = (f - 1) / FPS
        W2.step(f, t, sl_b if f < 10 else sl_c, xs, ys)
        s = W2.should_stop(t)
        if s:
            stops2.append((f, s)); break
    syn["watch_tip_then_cavity"] = dict(tip=W2.tip, td=W2.td, stop=stops2)
    out["synthetic"] = syn
    # 等高線の面積（skimage、解析と同じ）と、計算の中の読みの面積（numpy）の比べ。巻き始めから着水の後までのコマ
    from skimage import measure
    import g44_analyze as A
    ac = dict(frames=0, frames_with_holes=0, holes=0, mismatch=[])
    for rid, rng in (("R4d", range(3730, 3752)), ("R3", range(3738, 3750)), ("R2", range(3722, 3734)), ("S8", range(1608, 1622))):
        rd = (B44 + "/smoke/S8") if rid == "S8" else (R42 + "/" + rid)
        cfg = jl(rd + "/cfg.json"); off = jl(rd + "/ana.json")["still_level_offset_m"]
        best, metas = sec_best(rd); vox = 2 * cfg["parms"]["dp"]
        for f in rng:
            f0, p, i, key = best[f]; m = metas[key]
            sl = np.load(p)["sdf"][i].astype(np.float32)
            xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
            water = sl < 0; bed = ys[:, None] < (O.bed_y(cfg["parms"], xs)[None, :] + 0.5 * vox)
            S = sl.astype(np.float64).copy(); S[bed] = -1.0
            air = (~water) & (~bed)
            reach = np.zeros_like(air); reach[-1, :] = air[-1, :]; reach[:, 0] |= air[:, 0]; reach[:, -1] |= air[:, -1]
            for _ in range(4000):
                r2 = reach.copy(); r2[1:, :] |= reach[:-1, :]; r2[:-1, :] |= reach[1:, :]; r2[:, 1:] |= reach[:, :-1]; r2[:, :-1] |= reach[:, 1:]
                r2 &= air
                if (r2 == reach).all():
                    break
                reach = r2
            on = sorted(O._ms_area(S, jj, ii) * m["dx"] * m["dy"] for jj, ii in O._components(air & ~reach))
            sk = []
            for c in measure.find_contours(S, 0.0):
                if len(c) > 4 and np.allclose(c[0], c[-1]):
                    X = xs[0] + c[:, 1] * m["dx"]; Y = ys[0] + c[:, 0] * m["dy"]
                    ix = int(round((X.mean() - xs[0]) / m["dx"])); iy = int(round((Y.mean() - ys[0]) / m["dy"]))
                    if S[iy, ix] > 0:
                        sk.append(A.poly_area(np.stack([X, Y], 1)))
            sk = sorted(sk)
            ac["frames"] += 1; ac["holes"] += len(sk); ac["frames_with_holes"] += 1 if sk else 0
            if len(on) != len(sk) or not np.allclose(on, sk, rtol=1e-9, atol=1e-9):
                ac["mismatch"].append([rid, f, on[-3:], sk[-3:]])
    out["area_check"] = ac
    # 判定（a・b・c・d は走らせる前に決めた。a2・a3 は 1 回目で R4d の格子 1 個の泡を見つけた後に足した）：(a) R3 の空気の穴の読みは 3745 コマのまま、(b) 新しい止め方でも、4 つの記録の全部で、止まるコマが
    # 解析の着水のコマ以上（記録に着水が入る）、(c) 作った断面で、静かな水面より下の唇の先を見つけ、上の唇の先と谷に届いた唇では見つけない、
    # (d) 唇の先だけなら tip_wait_s 後、その間に空気の穴が見つかれば穴の 0.5 s 後で止まる
    real = [out[k] for k in ("R3", "R2", "R4d", "S8")]
    out["pass"] = dict(
        a=bool((out["R3"]["cavity_new"] or {}).get("frame") == 3745),
        a2=bool(not ac["mismatch"] and ac["holes"] > 0),
        a3=all((out[k]["cavity_new"] or {}).get("frame") == out[k]["f_touchdown_ana"] for k in ("R3", "R2", "R4d", "S8")),
        b=all(v["record_has_touchdown_new"] for v in real),
        c=bool(syn["tip_below"]["lip"]["found"] and not syn["tip_above"]["lip"]["found"] and not syn["tip_touches_trough"]["lip"]["found"]
               and syn["tip_touches_trough"]["cavity_found"]),
        d=bool(stops and stops[0][0] == 1 + 48 and "touchdown_online_tip" in stops[0][1]
               and stops2 and "touchdown_online at frame 10" in stops2[0][1] and stops2[0][0] == 22))
    save("td", out)
    for k, v in out.items():
        if k in ("R3", "R2", "R4d", "S8"):
            print(k, json.dumps({kk: vv for kk, vv in v.items() if kk != "tips_head"}, ensure_ascii=False, default=float)[:900])
    print("synthetic", json.dumps(syn, ensure_ascii=False, default=float)[:1500])
    print("pass", out["pass"])


# ------------------------------------------------------------------ 並びの dry-run の助け
AG = "x44_fix2 の試し（本番ではない）"


def q(root, args, enc="utf-8"):
    rc, so, se = py(["g44_queue.py", "--agreed", AG, "--root", root, "--dry-run"] + args, enc=enc)
    txt = (so + se).strip()
    stopf = os.path.join(B44, root, "QUEUE_STOP.txt"); pausef = os.path.join(B44, root, "QUEUE_PAUSE.txt")
    last_stop = open(stopf, encoding="utf8").read().strip().splitlines()[-1] if os.path.exists(stopf) else None
    last_pause = open(pausef, encoding="utf8").read().strip().splitlines()[-2:] if os.path.exists(pausef) else None
    return dict(rc=rc, traceback=("Traceback" in txt), tail=txt.splitlines()[-3:], last_stop=last_stop, last_pause=last_pause)


def setstate(root, S):
    jw(os.path.join(B44, root, "queue_state.json"), S)


# ------------------------------------------------------------------ q1：G1・G8・引数（dry-run。標準出力は cp932）
def t_q1():
    TAG = time.strftime("%H%M%S")
    R = FXR + "/q1_" + TAG
    os.makedirs(B44 + "/" + R)
    steps = []

    def step(name, args, want, S=None, enc="cp932"):
        if S is not None:
            setstate(R, S)
        r = q(R, args, enc)
        r.update(step=name, want=want, ok=bool(r["rc"] == want and not r["traceback"]))
        steps.append(r)
        print(name, r["rc"], want, r["ok"], (r["last_stop"] or "")[-160:])

    step("empty_from_B35S", ["--from", "B35S"], 2, S={})
    step("empty_only_RP", ["--only", "RP"], 2, S={})
    step("empty_only_TABLE", ["--only", "TABLE"], 2, S={})
    step("empty_only_SH", ["--only", "SH"], 2, S={})
    step("empty_only_PR3", ["--only", "PR3"], 2, S={})
    step("empty_only_SELECT_no_previews", ["--only", "SELECT"], 2, S={})
    U = dict(select=dict(choice="PR2", confirmed=False))
    step("unconf_from_RP", ["--from", "RP"], 2, S=U)
    step("unconf_only_TABLE", ["--only", "TABLE"], 2, S=U)
    step("unconf_from_B35S", ["--from", "B35S"], 2, S=U)
    step("unconf_from_SH_waits", ["--from", "SH"], 3, S=U)
    Cf = dict(select=dict(choice="PR2", confirmed=True))
    step("conf_noSH_from_B35S", ["--from", "B35S"], 2, S=Cf)
    step("conf_noSH_only_TABLE", ["--only", "TABLE"], 2, S=Cf)
    P3 = dict(select=dict(choice="PR3", PR3_aim_m=470.0, confirmed=True))
    step("pr3_unconf_only_RP", ["--only", "RP"], 2, S=P3)
    step("pr3_unconf_from_SH_waits", ["--from", "SH"], 3, S=P3)
    # G8：runs/RP に前の試みの途中保存（空のファイル）と起動の記録
    rp = os.path.join(B44, R, "RP")
    os.makedirs(rp + "/ckpt")
    open(rp + "/ckpt/v.0480.sim", "wb").close()
    jw(rp + "/run_c0001.json", dict(f_start=1, f_end_done=500, stopped="wall_limit at frame 500"))
    step("rp_old_ckpt_refused", ["--only", "RP"], 2, S=Cf)
    step("rp_old_ckpt_resume", ["--only", "RP", "--resume-rp"], 0, S=Cf)
    open(rp + "/STOPPED_BY_RULE.txt", "w", encoding="utf8").write("2026-10-12 00:00:00 試しの古い止まり\n")
    old = time.time() - 7200
    os.utime(rp + "/STOPPED_BY_RULE.txt", (old, old))
    step("rp_old_rule_refused_even_with_resume", ["--only", "RP", "--resume-rp"], 2, S=Cf)
    step("bad_from_name", ["--from", "XYZ"], 1, S={})
    step("bad_confirm_name", ["--confirm-select", "PRX"], 1, S={})
    out = dict(root=R, steps=steps, all_ok=all(s["ok"] for s in steps),
               disk_plan_written=os.path.exists(os.path.join(B44, R, "DISK_PLAN_ja.md")),
               rp_cfg_written_while_refused=None)
    out["stop_file_tail"] = open(os.path.join(B44, R, "QUEUE_STOP.txt"), encoding="utf8").read().strip().splitlines()[-8:]
    save("q1", out)
    print("all_ok", out["all_ok"])


# ------------------------------------------------------------------ q3：G3（下見 3 本目の道を最後まで dry-run）
def t_q3():
    TAG = time.strftime("%H%M%S")
    R = FXR + "/q3_" + TAG
    D = B44 + "/" + R
    r3 = jl(B44 + "/check/ana44_R3.json")
    fail = json.loads(json.dumps(r3))
    fail["selection_a"]["pass_"] = False; fail["selection_a"]["c1_onset_in_window"] = False; fail["onset"]["xc_rel"] = 600.0
    for k in ("PR1", "PR2"):
        jw(D + "/%s/ana.json" % k, fail)
    plan_before = sorted(os.listdir(B44 + "/plan"))
    steps = []
    s1 = q(R, ["--only", "SELECT"]); s1["step"] = "select"; steps.append(s1)
    sel = jl(D + "/select.json")
    jw(D + "/PR3/ana.json", r3)                       # 下見 3 本目の結果の役（入る）
    s2 = q(R, ["--confirm-select", "PR3"]); s2["step"] = "confirm_select_PR3"; steps.append(s2)
    aim_p = D + "/plan_pr3/pr3_aim%.0f.json" % sel["PR3_aim_m"]
    # 形の本番の役：R3 の ana と、t_on − 3 s より前の途中保存（空のファイル）
    jw(D + "/SH/ana.json", r3)
    os.makedirs(D + "/SH/ckpt", exist_ok=True)
    for k in (3240, 3480, 3600, 3624, 3660):
        open(D + "/SH/ckpt/v.%04d.sim" % k, "wb").close()
    s3 = q(R, ["--confirm-pr3"]); s3["step"] = "confirm_pr3_to_end"; steps.append(s3)
    cf = lambda rid: jl(D + "/%s/cfg_queue.json" % rid) if os.path.exists(D + "/%s/cfg_queue.json" % rid) else None
    pr3c, shc, bc, rpc = cf("PR3"), cf("SH"), cf("B35S"), cf("RP")
    out = dict(root=R, steps=steps, select=sel, aim_file=os.path.exists(aim_p),
               aim_name=(jl(aim_p)["name"] if os.path.exists(aim_p) else None),
               PR3_cfg=dict(inlet=pr3c["inlet"]["name"], prog=pr3c["case"]["prog"], ckpt_keep=pr3c.get("ckpt_keep", {}).get("mode")) if pr3c else None,
               SH_cfg=dict(inlet=shc["inlet"]["name"], prog=shc["case"]["prog"], f_w=shc["case"]["f_w"], keep=shc.get("ckpt_keep")) if shc else None,
               B35S_cfg=dict(prog=bc["case"]["prog"], f_start=bc["f_start"], from_ckpt=bc["from_ckpt"], stop_touchdown=bc["stop_touchdown"]) if bc else None,
               RP_cfg=dict(inlet=rpc["inlet"]["name"], prog=rpc["case"]["prog"], f_end=rpc["f_end"]) if rpc else None,
               plan_dir_unchanged=(sorted(os.listdir(B44 + "/plan")) == plan_before),
               pr3_pause=open(D + "/QUEUE_PAUSE.txt", encoding="utf8").read().strip().splitlines()[-2:] if os.path.exists(D + "/QUEUE_PAUSE.txt") else None,
               report=open(D + "/QUEUE_REPORT.txt", encoding="utf8").read().strip().splitlines() if os.path.exists(D + "/QUEUE_REPORT.txt") else None)
    # 本番の道の終わりのコードの確かめ（並びの関数を直に呼ぶ。道具は走らせず、終わりのコードと置き場所だけを作り変える）
    import g44_queue as Q
    R2_ = FXR + "/q3rc_" + TAG
    res = {}
    for name, fake in (("tool_rc1", lambda cmd: (1, "試しの失敗")), ("tool_rc0_no_file", lambda cmd: (0, "書いたと言うがない"))):
        Q.setup(R2_, dry=False); Q.AGREED = AG
        Q.C.PR3_DIR = B44 + "/" + R2_ + "/plan_pr3_none"
        Q.run_now = fake
        S = dict(select=dict(choice="PR3", PR3_aim_m=470.0, confirmed=True))
        try:
            Q.stage_pr3(S); code = None
        except SystemExit as e:
            code = e.code
        res[name] = dict(exit=code, stop=open(B44 + "/" + R2_ + "/QUEUE_STOP.txt", encoding="utf8").read().strip().splitlines()[-1])
    Q.C.PR3_DIR = Q.C.PLAN_DIR
    out["prod_path_rc_checks"] = res
    # 凍結した道具の写しは plan/ に書かない
    rc, so, se = py(["x44_aim3_dry.py", "470", B44 + "/plan"])
    out["wrapper_refuses_plan_dir"] = dict(rc=rc, msg=(so + se).strip()[-200:])
    out["pass"] = bool(s1["rc"] == 3 and s2["rc"] == 3 and s3["rc"] == 0 and not any(s["traceback"] for s in steps) and out["aim_file"]
                       and out["plan_dir_unchanged"] and pr3c and shc and bc and rpc and all(v["exit"] == 2 for v in res.values())
                       and rc == 2)
    save("q3", out)
    print(json.dumps({k: v for k, v in out.items() if k != "steps"}, ensure_ascii=False, default=float)[:3000])
    for s in steps:
        print(s["step"], s["rc"], s["traceback"], s["tail"])
    print("pass", out["pass"])


# ------------------------------------------------------------------ q4：G4（下見 1 の解析が止まっても下見 2 へ。計算は走らせず、解析は本当に）
def t_q4():
    import g44_queue as Q
    TAG = time.strftime("%H%M%S")
    R = FXR + "/q4_" + TAG
    D = B44 + "/" + R
    s8 = B44 + "/smoke/S8"
    # PR1 の役：S8 の後の起動の記録だけ（0.5〜2.0 s のコマがない → 解析はコード 3 で止まる）。PR2 の役：S8 の全部の記録
    for rid, pats in (("PR1", ["hf_c1153.npz", "sec_c1153_*.npz"]), ("PR2", ["hf_c*.npz", "sec_c*.npz"])):
        os.makedirs(D + "/" + rid)
        for pat in pats:
            for p in glob.glob(s8 + "/" + pat):
                shutil.copy2(p, D + "/" + rid)
        c = jl(s8 + "/cfg.json"); c["run_id"] = rid; c["out_root"] = R
        jw(D + "/%s/cfg.json" % rid, c)
    calls = []

    def fake_chain(cfg):
        calls.append(cfg["run_id"]); return ("rule", 1632, "試し：計算は走らせない")
    Q.chain = fake_chain
    runs_ = []
    for name, args in (("from_PR1", ["--from", "PR1"]), ("from_SELECT_still_broken", ["--from", "SELECT"])):
        sys.argv = ["g44_queue.py", "--agreed", AG, "--root", R] + args
        try:
            Q.main(); code = 0
        except SystemExit as e:
            code = e.code
        runs_.append(dict(step=name, exit=code))
        print(name, code)
    # PR1 の記録を足して（S8 の始めの起動の記録を写す）解析が通る形にし、選びからやり直す
    for p in glob.glob(s8 + "/hf_c0001.npz") + glob.glob(s8 + "/sec_c0001_*.npz"):
        shutil.copy2(p, D + "/PR1")
    sys.argv = ["g44_queue.py", "--agreed", AG, "--root", R, "--from", "SELECT"]
    try:
        Q.main(); code = 0
    except SystemExit as e:
        code = e.code
    runs_.append(dict(step="from_SELECT_after_fix", exit=code)); print("from_SELECT_after_fix", code)
    S = jl(D + "/queue_state.json")
    out = dict(root=R, runs=runs_, chain_calls=calls, state_ana_fail=S.get("ana_fail"), state_select=S.get("select"),
               report=open(D + "/QUEUE_REPORT.txt", encoding="utf8").read().strip().splitlines(),
               pause=open(D + "/QUEUE_PAUSE.txt", encoding="utf8").read().strip().splitlines(),
               stop=open(D + "/QUEUE_STOP.txt", encoding="utf8").read().strip().splitlines() if os.path.exists(D + "/QUEUE_STOP.txt") else None)
    # 判定（走らせる前に決めた）：1 回目は PR1・PR2 の両方の計算の段を通り（chain が 2 回呼ばれる）、選びで待つ（3）。直す前の選びからは
    # また待つ（3）。直した後は解析が通り、選びが走る（S8 は 300〜800 m に主な頂がないので両方外れ、下見 2 に巻き始めがなく止まる：2）
    out["pass"] = bool(calls == ["PR1", "PR2"] and [r["exit"] for r in runs_] == [3, 3, 2] and not S.get("ana_fail"))
    save("q4", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:3000])
    print("pass", out["pass"])


# ------------------------------------------------------------------ g5：断面が巻き始めより後から始まる記録
def t_g5():
    res = {}
    for rid in ("Bx_late", "Bx_cap"):
        outp = FX + "/g5/%s_ana.json" % rid
        os.makedirs(FX + "/g5", exist_ok=True)
        rc, so, se = py(["g44_analyze.py", rid, "check/fx", "--out", outp])
        a = jl(outp) if os.path.exists(outp) else {}
        res[rid] = dict(rc=rc, onset_frame=(a.get("onset") or {}).get("frame"), main_first_frame=(a.get("main") or {}).get("first_frame"),
                        onset_at_path_start=a.get("onset_at_path_start"), notes=a.get("notes_ja"))
    out = dict(res=res, pass_=bool(res["Bx_late"]["onset_at_path_start"] and not res["Bx_cap"]["onset_at_path_start"]
                                   and res["Bx_late"]["rc"] == 0 and res["Bx_cap"]["rc"] == 0))
    save("g5", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:2500])


# ------------------------------------------------------------------ g6：風の値の上書きと守り
def t_g6():
    import g44_online as O
    B = ["B", "B35S", "wind=S", "U10=35", "sh=SHx", "prog=PR2", "t_on=154.458", "t_td=155.29", "ckpt_frame=3564", "still_offset=0.1627"]
    cases = [("B_ok", B, 0), ("B_wind_on_0", B + ["wind_on=0"], 1), ("B_wind_mode_3", B + ["wind_mode=3"], 1), ("B_wind_mode_2", B + ["wind_mode=2"], 1),
             ("B_wind_on_yes", B + ["wind_on=yes"], 1), ("B_wind_on_2", B + ["wind_on=2"], 1), ("B_wind_mode_1_same", B + ["wind_mode=1"], 0),
             ("PR1_wind_on_1", ["PR1", "PR1", "wind_on=1"], 1), ("SH_wind_on_1", ["SH", "SH", "prog=PR2", "onset_pre=155", "wind_on=1"], 1),
             ("RP_wind_on_1", ["RP", "RP", "aim=reef", "wind_on=1"], 1), ("PR2_wind_mode_3_off", ["PR2", "PR2", "wind_mode=3"], 0),
             ("SMOKE_mode3", ["SMOKE", "X", "dp=0.5", 'wind={"wind_on": 1.0, "wind_mode": 3.0}'], 0),
             ("SMOKE_mode2", ["SMOKE", "X", "dp=0.5", 'wind={"wind_on": 1.0, "wind_mode": 2.0}'], 1),
             ("B_N", ["B", "B35N", "wind=N", "U10=35", "sh=SHx", "prog=PR2", "t_on=154.458", "t_td=155.29", "ckpt_frame=3564", "still_offset=0.1627"], 1)]
    res = {}
    for name, args, want in cases:
        rc, so, se = py(["g44_cfg.py"] + args)
        res[name] = dict(rc=rc, want=want, ok=bool(rc == want and "Traceback" not in se), msg=(se.strip().splitlines() or [""])[-1][:200])
    same = {}
    for name, args in (("PR1", ["PR1", "PR1"]), ("PR2", ["PR2", "PR2"]), ("RP_reef500", ["RP", "RP", "aim=reef"]), ("RP_flat592", ["RP", "RP", "aim=flat"])):
        rc, so, se = py(["g44_cfg.py"] + args)
        same[name] = bool(rc == 0 and so.replace("\r\n", "\n").strip() == open(os.path.join(B44, "runs", "ready", name + ".json"), encoding="utf8").read().strip())
    base_B = dict(out_root="runs", parms=dict(wind_on=1.0, wind_mode=1.0), case=dict(form="S"))
    g = {
        "B_ok": O.wind_guard(base_B, airflow_exists=False),
        "B_wind_on_0": O.wind_guard(dict(base_B, parms=dict(wind_on=0.0, wind_mode=1.0)), airflow_exists=False),
        "B_mode2": O.wind_guard(dict(base_B, parms=dict(wind_on=1.0, wind_mode=2.0)), airflow_exists=False),
        "B_mode3_runs": O.wind_guard(dict(base_B, parms=dict(wind_on=1.0, wind_mode=3.0)), airflow_exists=False),
        "smoke_mode3": O.wind_guard(dict(out_root="smoke", parms=dict(wind_on=1.0, wind_mode=3.0), case={}), airflow_exists=False),
        "runs_mode3_noform": O.wind_guard(dict(out_root="runs", parms=dict(wind_on=1.0, wind_mode=3.0), case={}), airflow_exists=False),
        "PR_off": O.wind_guard(dict(out_root="runs", parms=dict(wind_on=0.0, wind_mode=1.0), case={}), airflow_exists=False),
        "wind_on_2": O.wind_guard(dict(out_root="smoke", parms=dict(wind_on=2.0), case={}), airflow_exists=False),
        "mode_4": O.wind_guard(dict(out_root="smoke", parms=dict(wind_on=1.0, wind_mode=4.0), case={}), airflow_exists=False),
        "N_with_tool": O.wind_guard(dict(out_root="runs", parms=dict(wind_on=1.0, wind_mode=2.0), case=dict(form="N")), airflow_exists=True),
        "form_S_mode2_with_tool": O.wind_guard(dict(base_B, parms=dict(wind_on=1.0, wind_mode=2.0)), airflow_exists=True),
    }
    want_none = {"B_ok", "smoke_mode3", "PR_off", "N_with_tool"}
    gok = all((v is None) == (k in want_none) for k, v in g.items())
    out = dict(cfg=res, ready_same=same, guard=g, pass_=bool(all(v["ok"] for v in res.values()) and all(same.values()) and gok))
    save("g6", out)
    for k, v in res.items():
        print(k, v["rc"], v["want"], v["ok"], v["msg"][:120])
    print("ready_same", same); print("guard", json.dumps(g, ensure_ascii=False)[:1500]); print("pass", out["pass_"])


# ------------------------------------------------------------------ g7：表の表示（cp932）
def t_g7():
    res = {}
    for name, extra in (("no_wind", []), ("with_wind", ["--wind", "B35S=Bx_cap", "B45S=Bx_online"])):
        od = FX + "/g7/" + name
        os.makedirs(od, exist_ok=True)
        rc, so, se = py(["g44_ctable.py", "SHx"] + extra + ["--root", "check/fx", "--out", od], enc="cp932")
        md = open(od + "/remaining_gap_ja.md", encoding="utf8").read() if os.path.exists(od + "/remaining_gap_ja.md") else ""
        res[name] = dict(rc=rc, has_dash=("—" in md), traceback=("Traceback" in se), tail=(so + se).strip().splitlines()[-2:])
    out = dict(res=res, pass_=all(v["rc"] == 0 and not v["traceback"] for v in res.values()) and res["no_wind"]["has_dash"])
    save("g7", out)
    print(json.dumps(out, ensure_ascii=False)[:1500])


# ------------------------------------------------------------------ g8：chain_result が古い止まりのファイルを読まない
def t_g8():
    import g44_queue as Q
    TAG = time.strftime("%H%M%S")
    R = FXR + "/g8_" + TAG
    Q.setup(R, dry=True)
    rd = os.path.join(B44, R, "RP")
    os.makedirs(rd)
    jw(rd + "/run_c0001.json", dict(f_start=1, f_end_done=4000, stopped="wall_limit at frame 4000"))
    open(rd + "/STOPPED_BY_RULE.txt", "w", encoding="utf8").write("試しの古い止まり\n")
    old = time.time() - 7200
    os.utime(rd + "/STOPPED_BY_RULE.txt", (old, old))
    t0 = time.time() - 60
    open(rd + "/STOPPED_MAX_HOURS.txt", "w", encoding="utf8").write("試しの新しい打ち切り\n")
    a = Q.chain_result("RP", 9830, t0)
    b = Q.chain_result("RP", 9830, old - 60)
    out = dict(new_chain=a, chain_older_than_rule_file=b, pass_=bool(a[0] == "cut" and b[0] == "rule"))
    save("g8", out)
    print(json.dumps(out, ensure_ascii=False))


# ------------------------------------------------------------------ ck：途中保存の残し方と置き場所の見込み（G2）
def t_ck():
    import g44_ckpt as K
    import g44_hours as H
    TAG = time.strftime("%H%M%S")
    D = FX + "/ck_" + TAG
    out = {}

    def mk(rd, frames, size=1000):
        os.makedirs(rd + "/ckpt", exist_ok=True)
        for k in frames:
            open(rd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\0" * size)

    # (1) 試しの置き場所（out_root が runs でない）では消さず、消すはずの物を書く。前からある物（帳面にない物）は候補にしない
    rd = D + "/PR"
    mk(rd, [100])                                  # 前からある物
    cfg = dict(out_root=FXR, ckpt_keep=K.keep_policy("PR"))
    seq = []
    before = K.ckpt_frames(rd)
    mk(rd, [240, 480]); seq.append(K.after_launch(rd, cfg, 1, 500, before, 2.0, 1.0, log=lambda *a: None))
    before = K.ckpt_frames(rd)
    mk(rd, [720]); seq.append(K.after_launch(rd, cfg, 481, 800, before, 5.0, 1.0, log=lambda *a: None))
    before = K.ckpt_frames(rd)
    mk(rd, [960, 1080]); seq.append(K.after_launch(rd, cfg, 721, 1100, before, 5.0, 1.0, log=lambda *a: None))
    L = K.load_ledger(rd)
    out["test_root"] = dict(seq=[dict(new=s["new"], would=s["would"], deleted=s["deleted"]) for s in seq], files=K.ckpt_frames(rd),
                            would_prune=sorted(int(k) for k in L["would_prune"]), verified=L["verified"])
    ok1 = bool(K.ckpt_frames(rd) == [100, 240, 480, 720, 960, 1080] and 100 not in [int(k) for k in L["would_prune"]]
               and sorted(int(k) for k in L["would_prune"]) == [240, 480, 960] and L["verified"] == [480, 720])
    # (2) 本番の置き場所の道（os.remove を差し替えて、消す代わりに試しのフォルダーの中の moved/ へ動かす。ファイルは消さない）
    removed = []
    real_remove = K.os.remove
    rd2 = D + "/SH"
    os.makedirs(rd2 + "/moved", exist_ok=True)

    def fake_remove(p):
        removed.append(os.path.basename(p)); os.replace(p, rd2 + "/moved/" + os.path.basename(p))
    K.os.remove = fake_remove
    try:
        pol = K.keep_policy("SH", onset_pre=155.0, f_w=3576, Tc=9.4)
        cfg2 = dict(out_root="runs", ckpt_keep=pol)
        lo, hi = pol["protect_ranges"][0]
        frames_all = [240, 480, 3360, 3576, 3600, 3648, 3696, 3720, 3744, 3792]
        before = []
        res2 = []
        f0 = 1
        for chunk in ([240, 480], [3360, 3576], [3600, 3648], [3696, 3720], [3744, 3792]):
            mk(rd2, chunk)
            r = K.after_launch(rd2, cfg2, f0, chunk[-1] + 5, before, 3.0, 2.0, log=lambda *a: None)
            res2.append(dict(new=r["new"], deleted=r["deleted"], kept=r["kept"]))
            before = K.ckpt_frames(rd2); f0 = chunk[-1] + 1
        # 書きかけ（いちばん新しい物が小さい）の時は消さない
        mk(rd2, [3840], size=10)
        r = K.after_launch(rd2, cfg2, 3793, 3845, before, 3.0, 2.0, log=lambda *a: None)
        res2.append(dict(new=r["new"], deleted=r["deleted"], why=r["why"]))
    finally:
        K.os.remove = real_remove
    L2 = K.load_ledger(rd2)
    out["prod_path"] = dict(protect=[lo, hi], steps=res2, removed_calls=removed, pruned=sorted(int(k) for k in L2["pruned"]),
                            files_still_there=K.ckpt_frames(rd2))
    prot = set(k for k in frames_all if lo <= k <= hi) | {3576}
    moved = sorted(int(x[2:6]) for x in os.listdir(rd2 + "/moved"))
    out["prod_path"]["moved_instead_of_deleted"] = moved
    ok2 = bool(not (set(int(k) for k in L2["pruned"]) & prot) and res2[-1]["deleted"] == [] and "書きかけ" in (res2[-1]["why"] or "")
               and len(removed) == len(L2["pruned"]) and sorted(K.ckpt_frames(rd2) + moved) == sorted(frames_all + [3840])
               and sorted(int(k) for k in L2["pruned"]) == [240, 480, 3360])
    # (3) 置き場所の見込み
    d = K.disk_plan(["PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP"])
    free = shutil.disk_usage("G:/").free / 2**30
    open(D + "/DISK_PLAN_ja.md", "w", encoding="utf8").write(K.plan_md(d, free, 25.0, FXR))
    out["disk_plan"] = dict(need=d["total_need_gb"], keep=d["total_keep_gb"], peak=d["peak_extra_gb"], without=d["total_all_gb"], free=free,
                            rows=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in d["rows"]])
    # (4) g44_hours の出力が trace を足す前と同じか（fixes/hours44.json と比べる。書くのは fixes2）
    H.OUT = D + "/hours44_check.json"
    o = H.main()
    ref = jl(B44 + "/fixes/hours44.json")
    a_, b_ = json.loads(json.dumps(o, default=float)), ref
    a_.pop("note_ja", None); b_.pop("note_ja", None)
    out["hours44_same"] = bool(a_ == b_)
    out["pass"] = dict(test_root=ok1, prod_path=ok2, disk_fits=bool(d["total_need_gb"] < free - 25.0), hours44_same=out["hours44_same"])
    save("ck", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


# ------------------------------------------------------------------ aw：夜の間に眠らないように頼めるか
def t_aw():
    import g44_queue as Q
    out = dict(queue_keep_awake=Q.keep_awake())
    src = open(TOOLS + "/g44_chain.py", encoding="utf8").read()
    out["chain_calls_it"] = ("SetThreadExecutionState" in src and "keep_awake()" in src)
    save("aw", out)
    print(out)


# ------------------------------------------------------------------ h1・h2：hython の短い試し
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"


def wait_hython():
    t = time.time(); n = 0
    while hython_running():
        if n % 12 == 0:
            print("waiting for another hython ...", round((time.time() - t) / 60, 1), "min", flush=True)
        n += 1
        time.sleep(10)
    return time.time() - t


def t_h1():
    TAG = time.strftime("%H%M%S")
    R = FXR + "/h1_" + TAG
    base = jl(B44 + "/smoke/S8/cfg_c1153.json")
    res = {}
    for name, mod in (("mode2", dict(wind_on=1.0, wind_mode=2.0)), ("formS_wind_off", dict(wind_on=0.0, wind_mode=1.0))):
        c = json.loads(json.dumps(base))
        c["run_id"] = "h1_" + name; c["out_root"] = R; c["f_start"] = 1153; c["f_end"] = 1160
        c["parms"].update(mod)
        if name == "formS_wind_off":
            c["case"]["form"] = "S"
        p = B44 + "/" + R + "/cfg_%s.json" % name
        jw(p, c)
        waited = wait_hython()
        t0 = time.time()
        env = dict(os.environ, HOUDINI_TEMP_DIR=B44 + "/tmp_houdini", TEMP=B44 + "/tmp_houdini", TMP=B44 + "/tmp_houdini")
        r = subprocess.run([HY, TOOLS + "/g44_run.py", p], capture_output=True, env=env, creationflags=0x00004000, stdin=subprocess.DEVNULL)
        rec = B44 + "/" + R + "/h1_%s/run_c1153.json" % name
        res[name] = dict(rc=r.returncode, seconds=round(time.time() - t0, 1), waited_s=round(waited, 1),
                         stopped=(jl(rec)["stopped"] if os.path.exists(rec) else None),
                         tail=r.stdout.decode("utf-8", "replace").strip().splitlines()[-2:])
        print(name, res[name])
    out = dict(root=R, res=res, pass_=all((v["stopped"] or "").startswith("refused") for v in res.values()))
    save("h1", out)


def t_h2():
    """S8 の 1,152 コマの途中保存から、g44_chain.py で 1 回 70 s の起動に分けて走らせる（風なし）。計算の中の着水の読み（TouchdownWatch）と、
    途中保存の帳面・消すはずの物（試しの置き場所なので消さない）を通す。記録は S8 の同じコマと比べる。"""
    TAG = time.strftime("%H%M%S")
    rid = "h2_" + TAG
    base = jl(B44 + "/smoke/S8/cfg_c1153.json")
    c = json.loads(json.dumps(base))
    c.update(run_id=rid, out_root=FXR, f_start=1153, f_first=1153, f_end=1700, ckpt_every=48, ckpt_list=[48, 24, 12], wall_limit_s=70,
             max_hours=0.4, from_ckpt=dict(run="S8", frame=1152, root="smoke"),
             stop_touchdown=dict(after_s=0.5, t_from=(1577 - 1) / FPS - 1.0, Lc=135.46329754326246, still_offset_m=0.23149146139621735,
                                 tip_on=True, tip_wait_s=2.0),
             ckpt_keep=dict(mode="latest", protect_frames=[], protect_ranges=[], dry=False, kind="test"),
             note="x44_fix2 h2：S8 の 1152 コマから、区切った起動で着水の読みと途中保存の帳面を通す（試し）")
    c.pop("fieldbox_frames", None)
    p = FX + "/cfg_%s.json" % rid
    jw(p, c)
    waited = wait_hython()
    t0 = time.time()
    r = subprocess.run([sys.executable, TOOLS + "/g44_chain.py", p], capture_output=True, creationflags=0x00004000)
    el = time.time() - t0
    rd = FX + "/" + rid
    recs = sorted(glob.glob(rd + "/run_c*.json"))
    R_ = [jl(x) for x in recs]
    import g44_queue as Q
    Q.setup(FXR, dry=True)
    state_ = Q.chain_result(rid, 1700, t0)
    # 一番上の水面を S8 の同じコマと比べる（ビット単位）
    import g44_analyze as A
    D1 = A.load_hf(rd); D0 = A.load_hf(B44 + "/smoke/S8")
    common = sorted(set(D1["frames"].tolist()) & set(D0["frames"].tolist()))
    i1 = [list(D1["frames"]).index(f) for f in common]; i0 = [list(D0["frames"]).index(f) for f in common]
    e1 = D1["eta"][i1]; e0 = D0["eta"][i0]
    same = bool(np.array_equal(np.nan_to_num(e1, nan=-999), np.nan_to_num(e0, nan=-999)))
    L = jl(rd + "/ckpt_ledger.json") if os.path.exists(rd + "/ckpt_ledger.json") else {}
    out = dict(rid=rid, waited_s=round(waited, 1), elapsed_s=round(el, 1), chain_rc=r.returncode, state=state_,
               launches=[dict(f_start=x["f_start"], done=x["f_end_done"], stopped=x["stopped"], prio=(x.get("priority") or {}).get("priority_class"),
                              td=(x.get("info") or {}).get("touchdown_online", {}).get("frame") if (x.get("info") or {}).get("touchdown_online") else None,
                              restored=(x.get("info") or {}).get("online_restored")) for x in R_],
               frames_compared=len(common), frames_range=[common[0], common[-1]] if common else None, eta_bitwise_same_as_S8=same,
               ledger=dict(made=sorted(int(k) for k in L.get("made", {})), would_prune=sorted(int(k) for k in L.get("would_prune", {})),
                           pruned=sorted(int(k) for k in L.get("pruned", {})), verified=L.get("verified"), last=L.get("last")),
               ckpt_files=sorted(os.listdir(rd + "/ckpt")) if os.path.isdir(rd + "/ckpt") else None,
               chain_log_tail=open(rd + "/chain.log", encoding="utf8").read().strip().splitlines()[-6:] if os.path.exists(rd + "/chain.log") else None)
    last_stop = (R_[-1]["stopped"] if R_ else "") or ""
    out["pass"] = dict(online_at_1616=bool(last_stop.startswith("touchdown_online at frame 1616")), stops_at_1628=bool(R_ and R_[-1]["f_end_done"] == 1628),
                       state_online=bool(state_[0] == "online"), multi_launch=bool(len(R_) >= 2), bitwise=same,
                       nothing_deleted=bool(not L.get("pruned")), would_prune_listed=bool(L.get("would_prune")))
    save("h2", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:5000])


def t_h3():
    """着水の引き継ぎ：g44_run.py を 2 回起動する。A は 1585〜1620 コマ（1616 コマで空気の穴を見つけ、1620 コマの途中保存を作って終わる）、
    B は 1621 コマから。B が A の記録から着水を引き継げば 1628 コマ（1616 + 0.5 s）で止まる。引き継がなければ B は 1621 コマ以後に
    穴を見つけ直し、1633 コマ以後で止まる。h2 の 1584 コマの途中保存を写して使う（消さない）。"""
    TAG = time.strftime("%H%M%S")
    rid = "h3_" + TAG
    h2 = sorted(glob.glob(FX + "/h2_*/ckpt/v.1584.sim"))[-1]
    rd = FX + "/" + rid
    os.makedirs(rd + "/ckpt")
    shutil.copy2(h2, rd + "/ckpt/v.1584.sim")
    base = jl(B44 + "/smoke/S8/cfg_c1153.json")
    st = dict(after_s=0.5, t_from=(1577 - 1) / FPS - 1.0, Lc=135.46329754326246, still_offset_m=0.23149146139621735, tip_on=True, tip_wait_s=2.0)
    res = {}
    for name, f0, f1 in (("A", 1585, 1620), ("B", 1621, 1700)):
        c = json.loads(json.dumps(base))
        c.update(run_id=rid, out_root=FXR, f_start=f0, f_first=1585, f_end=f1, ckpt_every=36, wall_limit_s=600, stop_touchdown=st,
                 note="x44_fix2 h3：着水の引き継ぎの試し")
        c.pop("fieldbox_frames", None)
        p = rd + "/cfg_%s.json" % name
        jw(p, c)
        waited = wait_hython()
        env = dict(os.environ, HOUDINI_TEMP_DIR=B44 + "/tmp_houdini", TEMP=B44 + "/tmp_houdini", TMP=B44 + "/tmp_houdini")
        t0 = time.time()
        r = subprocess.run([HY, TOOLS + "/g44_run.py", p], capture_output=True, env=env, creationflags=0x00004000, stdin=subprocess.DEVNULL)
        rec = jl(rd + "/run_c%04d.json" % f0)
        inf = rec.get("info") or {}
        res[name] = dict(rc=r.returncode, seconds=round(time.time() - t0, 1), waited_s=round(waited, 1), done=rec.get("f_end_done"), stopped=rec.get("stopped"),
                         td=(inf.get("touchdown_online") or {}).get("frame"), restored=inf.get("online_restored"),
                         ckpts=sorted(os.listdir(rd + "/ckpt")))
        print(name, res[name], flush=True)
    out = dict(rid=rid, res=res, pass_=bool(res["A"]["td"] == 1616 and res["A"]["done"] == 1620 and res["B"]["restored"] == {"td": 1616, "tip": None}
                                           and res["B"]["done"] == 1628 and (res["B"]["stopped"] or "").startswith("touchdown_online at frame 1616")))
    save("h3", out)
    print("pass", out["pass_"])


if __name__ == "__main__":
    print("priority", lower_self())
    os.makedirs(FX, exist_ok=True)
    cmd = sys.argv[1]
    globals()["t_" + cmd]()
