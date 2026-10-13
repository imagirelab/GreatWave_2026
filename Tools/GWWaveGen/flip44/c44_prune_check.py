# -*- coding: utf-8 -*-
"""FLIP44：4 回目の確かめ（3 回目の確かめの H1・H7 を直した途中保存の片付けの確かめ。直していない者による）。py -3.10。
hython は走らせない。本番の置き場所 runs/・plan/ には書かない。書くのは Unity/Build/FLIP44/check/fx3/ と check/c44_prune_check.json だけ。
ファイルは消さない：この確かめの中では os.remove・os.unlink を「check/fx3 の中の _moved/ へ動かす」物に差し替え、fx3 の外は断る。

  p1  形の本番の起動の真似 × 巻き始めのずれ（全部の組）。g44_ckpt の after_launch・prune_after_onset・wind_start を、記憶の中の
      ファイル置き場（ファイルを作らない）で本当に動かす。下見の巻き始め 140〜165 s を 1 s ごと × 機械の重さ 1.0・1.33 × 下見 1・2 の入口 ×
      δ = −9〜+9 s を 0.5 s ごと。起動の真似は 2 通り：
        shift：1 コマの秒の山と止める決まりを、本当の巻き始め t_on = 下見 + δ に置く（直した側の ck3a にない形）。固定 f_w と間隔は下見から。
        pre  ：1 コマの秒の山と止める決まりを下見の巻き始めに置く（直した側の ck3a と同じ形。比べのため）。
  p2  本当の g44_chain.py を、hython の代わりの真似（subprocess.run の差し替え）で動かす。BASE を試しの置き場所に替えて out_root runs の道
      （本当に消す道。消す代わりに動かす）を通す。形の本番の後に prune_after_onset、続けて風の計算 B35S の chain（形の本番の途中保存の写し）。
      起動ごとのコマと間隔が g44_hours.simulate と同じかも見る（p1 の真似が chain と同じ決まりか）。
  p3  本当の g44_queue.py --dry-run（試しの置き場所）で --from SH（SH → B35S → B45S → RP → TABLE）と、片付けを本当に動かした後の --only B35S。
  p4  1 本ずつの道（ckpt_keep なし）の途中保存が消えないか（本当の g44_chain.py。SH・B・PR、順番の入れ替え、古い帳面、帳面にない物、
      同じコマの作り直し）。
  p5  置き場所の見込み（disk_plan と、p1 の作る数の最大から出し直した値）と G: の空き。
  snap 走らせる前と後の runs/・plan/ の一覧と、凍結した 4 つの SHA-256。
使い方：py -3.10 Tools/GWWaveGen/flip44/c44_prune_check.py [p1] [p2] [p3] [p4] [p5]（なしは全部）
"""
import sys, os, json, glob, time, math, shutil, subprocess, types, ctypes, hashlib, fnmatch, io, contextlib, copy
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip44"
B44 = REPO + "/Unity/Build/FLIP44"
CHK = B44 + "/check"
FX = CHK + "/fx3"
RES = CHK + "/c44_prune_check.json"
FPS = 24.0
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
STAMP = time.strftime("%H%M%S")
AG = "c44_prune_check の試し（本番ではない。合意の記録ではない）"
sys.path.insert(0, TOOLS)
import g44_ckpt as K
import g44_hours as H
import g44_cfg as C

REAL_RUN = subprocess.run
GLOB_MOD = glob
os.makedirs(FX, exist_ok=True)

# ------------------------------------------------------------------ 消さない守り
MOVED = []


def guarded_remove(p, *a, **kw):
    ap = os.path.abspath(p).replace("\\", "/")
    if not ap.lower().startswith(FX.lower() + "/"):
        raise PermissionError("c44_prune_check：fx3 の外は消さない（%s）" % p)
    d = os.path.join(os.path.dirname(os.path.dirname(ap)), "_moved")
    os.makedirs(d, exist_ok=True)
    b = os.path.basename(ap); dst = os.path.join(d, b); i = 1
    while os.path.exists(dst):
        dst = os.path.join(d, "%s.%d" % (b, i)); i += 1
    os.replace(ap, dst)
    MOVED.append(ap)


os.remove = guarded_remove
os.unlink = guarded_remove


def lower_self():
    try:
        k = ctypes.windll.kernel32
        h = k.GetCurrentProcess()
        return bool(k.SetPriorityClass(h, 0x4000))      # BELOW_NORMAL（この処理だけ）
    except Exception:
        return False


def save(key, val):
    d = json.load(open(RES, encoding="utf8")) if os.path.exists(RES) else {}
    d[key] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), **val)
    json.dump(d, open(RES, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def nolog(*a):
    pass


P = H.plan()
Tc = P["tank"]["Tc"]
AIM = {"PR1": P["programs"]["PR1_R3_flat592"]["aim_t_s"], "PR2": P["programs"]["PR2_reef_aim500"]["aim_t_s"]}
STOP_GB = float(P["criteria"]["disk_stop_free_GB"])
TD_OFF_R3 = (H.TD_R["R3"] - H.ONSET_R["R3"]) / FPS
TD_OFF_R2 = (H.TD_R["R2"] - H.ONSET_R["R2"]) / FPS
_CFG = {}


def sh_cfg(prog, o):
    key = (prog, float(o))
    if key not in _CFG:
        _CFG[key] = C.kind_cfg("SH", "SH", {"prog": prog, "onset_pre": float(o)})
    return json.loads(json.dumps(_CFG[key]))


def sh_trace(prog, o_pre, load, t_act):
    """形の本番の起動の真似。固定 f_w・間隔・f_end・打ち切りは本当の設定（g44_cfg.kind_cfg）から、1 コマの秒の山と止める決まりは t_act に置く。"""
    c = sh_cfg(prog, o_pre)
    cost = H.cost_fn("R3", int(round(t_act * FPS)) + 1, 1.0, load)
    t_td = t_act + TD_OFF_R3
    rule = lambda done: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= AIM[prog] + Tc
    tr = []
    r = H.simulate(cost, 1, c["f_end"], c["ckpt_every"], c["ckpt_list"], c["ckpt_lock_until"], H.CKLOAD[0.25], stopchk=H.STOPCHK_S["SH"],
                   rule_after_launch=rule, max_h=c.get("max_hours"), trace=tr)
    return tr, r, c, cost, t_td


def expect_start(made, t_on):
    """計画 §4.1（吹く時の行）：t_on − 3 s より前の最後の途中保存。自分で数える（g44_ckpt を使わない）。"""
    b = [k for k in sorted(made) if (k - 1) / FPS < t_on - 3.0]
    return b[-1] if b else None


# ------------------------------------------------------------------ 記憶の中のファイル置き場（p1）
class MemFS:
    def __init__(self):
        self.f = {}

    def k(self, p):
        return os.path.normcase(os.path.normpath(p))

    def exists(self, p):
        return self.k(p) in self.f

    def getsize(self, p):
        v = self.f[self.k(p)]
        return v if isinstance(v, int) else len("".join(v))

    def remove(self, p):
        kk = self.k(p)
        if kk not in self.f:
            raise FileNotFoundError(p)
        del self.f[kk]

    def glob(self, pat):
        d = self.k(os.path.dirname(pat)); b = os.path.basename(pat)
        return [kk for kk in self.f if os.path.dirname(kk) == d and fnmatch.fnmatch(os.path.basename(kk), b)]

    def open(self, p, mode="r", encoding=None, **kw):
        fs = self; kk = self.k(p)
        if "w" in mode:
            fs.f[kk] = []

            class W:
                def write(s, x):
                    fs.f[kk].append(x)

                def close(s):
                    pass
            return W()
        if kk not in fs.f:
            raise FileNotFoundError(p)

        class R:
            def read(s, *a):
                return "".join(fs.f[kk])

            def close(s):
                pass
        return R()

    def put(self, p, n):
        self.f[self.k(p)] = int(n)

    def snapshot(self):
        return {k: (list(v) if isinstance(v, list) else v) for k, v in self.f.items()}


def mem_patch(fs):
    K.os = types.SimpleNamespace(path=types.SimpleNamespace(join=os.path.join, exists=fs.exists, getsize=fs.getsize, basename=os.path.basename,
                                                            dirname=os.path.dirname), remove=fs.remove)
    K.glob = types.SimpleNamespace(glob=fs.glob)
    K.open = fs.open


def mem_unpatch():
    K.os = os
    K.glob = GLOB_MOD
    if "open" in K.__dict__:
        del K.open


def mem_replay(fs, rd, pol, tr, sz=1000):
    during = []; peak = 0; rows = 0
    for L in tr:
        before = K.ckpt_frames(rd)
        for k in L["cks"]:
            fs.put(K.ckpt_path(rd, k), sz)
        r = K.after_launch(rd, dict(out_root="runs", ckpt_keep=pol), L["f0"], L["done"], before, 10.0, 6.0, log=nolog)
        during += list(r["deleted"]) + list(r["would"]) + list(r["failed"])
        peak = max(peak, len(K.ckpt_frames(rd))); rows += 1
    return during, peak


def judge_after(fs, rd, made, t_on, f_w, pr):
    E = expect_start(made, t_on)
    after = K.ckpt_frames(rd)
    w = K.wind_start(rd, t_on)
    newest = max(made)
    keep = {E, newest} | ({f_w} if f_w in made else set())
    out = dict(E=E, start=pr["start"], want=pr["want"], ws_start=w["start"], ws_why=w["why_ja"], n_after=len(after),
               ok_E_exists=(E is not None), ok_start=(E is not None and pr["start"] == E and w["start"] == E and w["why_ja"] is None and E in after),
               ok_keep=(set(after) == keep), ok_deleted=(set(pr["deleted"]) == set(made) - keep and not pr["failed"]),
               E_vs_fw=("none" if E is None else ("before_fw" if E < f_w else ("fw" if E == f_w else "after_fw"))),
               gap_s=(None if E is None else (t_on - 3.0) - (E - 1) / FPS))
    return out


def t_p1():
    fs = MemFS(); mem_patch(fs)
    rd = "X:/mem/SH"
    deltas = [round(v, 2) for v in np.arange(-9.0, 9.0001, 0.5)]
    onsets = [float(v) for v in range(140, 166)]
    agg = {}
    fails = []
    made_max = {}
    stalls = []
    stall_tab = {}
    t0 = time.time()
    try:
        for variant in ("shift", "pre"):
            n = 0; bad = dict(during=0, E_missing=0, start=0, keep=0, deleted=0)
            made_rng = [10**9, 0]; after_rng = [10**9, 0]; evf = {"before_fw": 0, "fw": 0, "after_fw": 0, "none": 0}; gap_max = 0.0
            n_stall = 0; stall_E_missing = 0
            for prog in ("PR1", "PR2"):
                for o in onsets:
                    for load in (1.0, 1.33):
                        base_state = None
                        for d in deltas:
                            t_on = o + d
                            if variant == "shift" or base_state is None:
                                tr, r, c, cost, t_td = sh_trace(prog, o, load, t_on if variant == "shift" else o)
                                f_w = c["case"]["f_w"]
                                pol = K.keep_policy("SH", onset_pre=o, f_w=f_w, Tc=Tc)
                                fs.f = {}
                                during, peak = mem_replay(fs, rd, pol, tr)
                                made = sorted(set(k for L in tr for k in L["cks"]))
                                base_state = (fs.snapshot(), during, peak, made, f_w, r)
                            snap, during, peak, made, f_w, r = base_state
                            made_max[(variant, prog)] = max(made_max.get((variant, prog), 0), len(made))
                            if r.get("stalled") or r.get("cut_by_max_hours"):
                                # 計算が途中で止まる（固定の区間の中で途中保存が作れない・打ち切り）。並びは SH の段で止まり、片付けまで行かない
                                n_stall += 1
                                Es = expect_start(made, t_on)
                                if Es is None or during:
                                    stall_E_missing += 1
                                kk = "%s_%s_l%g" % (variant, prog, load)
                                stall_tab.setdefault(kk, {}).setdefault("%+.1f" % d, 0)
                                stall_tab[kk]["%+.1f" % d] += 1
                                if len(stalls) < 400:
                                    st = r.get("stalled") or {}
                                    stalls.append(dict(variant=variant, prog=prog, o=o, load=load, d=d, t_on=t_on, f_w=f_w, sp_lock=c["ckpt_every"],
                                                       at_frame=st.get("at_frame"), at_s=((st.get("at_frame") - 1) / FPS if st.get("at_frame") else None),
                                                       last_frame=r.get("last_frame"), last_s=(r.get("last_frame") - 1) / FPS, t_td=t_on + TD_OFF_R3,
                                                       cut=r.get("cut_by_max_hours"), E_kept=Es, made=len(made), nothing_pruned=not during))
                                continue
                            fs.f = {k: (list(v) if isinstance(v, list) else v) for k, v in snap.items()}
                            pr = K.prune_after_onset(rd, t_on, f_w=f_w, real=True, log=nolog)
                            j = judge_after(fs, rd, made, t_on, f_w, pr)
                            n += 1
                            made_rng = [min(made_rng[0], len(made)), max(made_rng[1], len(made))]
                            after_rng = [min(after_rng[0], j["n_after"]), max(after_rng[1], j["n_after"])]
                            evf[j["E_vs_fw"]] += 1
                            if j["gap_s"] is not None:
                                gap_max = max(gap_max, j["gap_s"])
                            ok = True
                            if during or peak != len(made):
                                bad["during"] += 1; ok = False
                            if not j["ok_E_exists"]:
                                bad["E_missing"] += 1; ok = False
                            if not j["ok_start"]:
                                bad["start"] += 1; ok = False
                            if not j["ok_keep"]:
                                bad["keep"] += 1; ok = False
                            if not j["ok_deleted"]:
                                bad["deleted"] += 1; ok = False
                            if not ok and len(fails) < 30:
                                fails.append(dict(variant=variant, prog=prog, o=o, load=load, d=d, during=during[:10], peak=peak, made=len(made), **j))
            agg[variant] = dict(cases_completed=n, bad=bad, made_range=made_rng, after_range=after_rng, E_vs_fw=evf, gap_max_s=gap_max,
                                cases_stalled=n_stall, stalled_E_missing_or_pruned=stall_E_missing)
    finally:
        mem_unpatch()
    # 巻き始めを読み直して早くなった時（直した側の open issue）：片付けの後で t_on を 6 s 早く読み直す
    fs = MemFS(); mem_patch(fs)
    try:
        tr, r, c, cost, t_td = sh_trace("PR2", 152.0, 1.33, 152.0)
        f_w = c["case"]["f_w"]
        mem_replay(fs, rd, K.keep_policy("SH", onset_pre=152.0, f_w=f_w, Tc=Tc), tr)
        K.prune_after_onset(rd, 152.0, f_w=f_w, real=True, log=nolog)
        w2 = K.wind_start(rd, 146.0)
        pr2 = K.prune_after_onset(rd, 146.0, f_w=f_w, real=True, log=nolog)
        reanalysis = dict(t_on_first=152.0, t_on_second=146.0, start=w2["start"], want=w2["want"], why=w2["why_ja"], second_prune_deleted=pr2["deleted"],
                          left=K.ckpt_frames(rd))
    finally:
        mem_unpatch()
    out = dict(deltas=[deltas[0], deltas[-1], 0.5], onsets=[onsets[0], onsets[-1], 1.0], loads=[1.0, 1.33], progs=["PR1", "PR2"], agg=agg,
               made_max={"%s_%s" % k: v for k, v in made_max.items()}, stall_table=stall_tab, stalls=stalls, fails=fails,
               reanalysis_earlier=reanalysis, wall_s=time.time() - t0)
    save("p1", out)
    print("p1", json.dumps(agg, ensure_ascii=False), "made_max", out["made_max"], "stall_table", json.dumps(stall_tab), "wall %.0f s" % out["wall_s"])
    return out


# ------------------------------------------------------------------ 本当の g44_chain.py を hython の真似で（p2・p3・p4）
CHAIN_PATH = TOOLS + "/g44_chain.py"
CHAIN_SRC = open(CHAIN_PATH, encoding="utf8").read()
BASE_LINE = 'BASE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"'
assert CHAIN_SRC.count(BASE_LINE) == 1


class _FakeSTES:
    argtypes = None
    restype = None

    def __call__(self, x):
        return 1


class FakeHython:
    def __init__(self, base, cost, ckload=3.5, stop_after=None, sz=4096):
        self.base = base; self.cost = cost; self.ckload = ckload; self.stop_after = stop_after; self.sz = sz; self.launches = []

    def run(self, cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "tasklist":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if isinstance(cmd, (list, tuple)) and cmd and os.path.normcase(os.path.normpath(cmd[0])) == os.path.normcase(os.path.normpath(HY)):
            return self.hython(cmd)
        raise RuntimeError("c44_prune_check：思わない起動 %r" % (cmd,))

    def hython(self, cmd):
        c = json.load(open(cmd[2], encoding="utf8"))
        rd = os.path.join(self.base, c.get("out_root", "runs"), c["run_id"])
        f0 = int(c["f_start"]); sp = int(c["ckpt_every"]); fe = int(c["f_end"]); wl = float(c["wall_limit_s"])
        walls = []; s = 0.0; f = f0; why = "end"
        while f <= fe:
            w = self.cost(f) + (self.ckload if (f == f0 and f0 > 1) else 0.0)
            s += w; walls.append(w); f += 1
            if s > wl:
                why = "wall"; break
        done = f - 1
        cks = [k for k in range((f0 // sp) * sp, done + 1, sp) if f0 <= k <= done and k > 0]
        for k in cks:
            with open(os.path.join(rd, "ckpt", "v.%04d.sim" % k), "wb") as fh:
                fh.write(b"\x01" * self.sz)
        np.savez(os.path.join(rd, "hf_c%04d.npz" % f0), wall=np.array(walls), frames=np.arange(f0, done + 1), npts=np.zeros(len(walls), int))
        with open(os.path.join(rd, "run_c%04d.json" % f0), "w", encoding="utf8") as fh:
            json.dump(dict(f_end_done=done, stopped=("wall_limit (fake)" if why == "wall" else None), wall_total_s=s, fake=True), fh)
        self.launches.append(dict(f0=f0, done=done, sp=sp, cks=cks))
        if self.stop_after is not None and len(self.launches) >= self.stop_after:
            with open(os.path.join(rd, "STOP"), "w") as fh:
                fh.write("c44_prune_check")
        return subprocess.CompletedProcess(cmd, 0)


stopmod = types.ModuleType("c44px_stop")


def _fake_stop(rid, out_root, t_done, cfg, t1=0.0, t2=0.0):
    return (t_done >= t1 and t_done >= t2), "fake rule %.2f >= %.2f, %.2f" % (t_done, t1, t2)


stopmod.stop = _fake_stop
sys.modules["c44px_stop"] = stopmod
_NCH = [0]


def run_chain(base, cfg, fake):
    """本当の g44_chain.py（BASE だけ試しの置き場所に替えた写し）を、この処理の中で走らせる。"""
    _NCH[0] += 1
    rd = os.path.join(base, cfg["out_root"], cfg["run_id"])
    os.makedirs(rd, exist_ok=True)
    cp = os.path.join(base, "cfgin_%s_%02d.json" % (cfg["run_id"], _NCH[0]))
    json.dump(cfg, open(cp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    src = CHAIN_SRC.replace(BASE_LINE, 'BASE = r"%s"' % base)
    code = compile(src, CHAIN_PATH, "exec")
    g = {"__name__": "__main__", "__file__": CHAIN_PATH}
    argv0 = sys.argv; sys.argv = [CHAIN_PATH, cp]
    k32 = ctypes.windll.kernel32; old = k32.SetThreadExecutionState; k32.SetThreadExecutionState = _FakeSTES()
    subprocess.run = fake.run
    buf = io.StringIO(); rc = 0
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, g)
    except SystemExit as e:
        rc = e.code
    finally:
        subprocess.run = REAL_RUN; sys.argv = argv0; k32.SetThreadExecutionState = old
    return rc, buf.getvalue()


def ledger(rd):
    p = os.path.join(rd, "ckpt_ledger.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def moved_frames(rd):
    return sorted(int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(rd, "_moved", "v.*.sim*")))


def sh_case_chain(base, prog, o, load, d, ckpt_keep=True, stop_after=None, out_root="runs", cost_at="t_on"):
    """cost_at：1 コマの秒の山と止める決まりを置く巻き始め（"t_on"＝本当の巻き始め、"pre"＝下見の巻き始め）。"""
    t_on = o + d
    t_act = t_on if cost_at == "t_on" else o
    c = sh_cfg(prog, o)
    f_w = c["case"]["f_w"]
    c["out_root"] = out_root
    if ckpt_keep:
        c["ckpt_keep"] = K.keep_policy("SH", onset_pre=o, f_w=f_w, Tc=Tc)
    t_td = t_on + TD_OFF_R3
    c["stop_check"] = dict(module="c44px_stop", func="stop", args=dict(t1=t_act + TD_OFF_R3 + 2 * Tc, t2=AIM[prog] + Tc))
    cost = H.cost_fn("R3", int(round(t_act * FPS)) + 1, 1.0, load)
    fk = FakeHython(base, cost, stop_after=stop_after)
    rc, out = run_chain(base, c, fk)
    rd = os.path.join(base, out_root, "SH")
    stalled = os.path.exists(os.path.join(rd, "STOPPED_NO_CKPT.txt"))
    return dict(c=c, f_w=f_w, t_on=t_on, t_td=t_td, cost=cost, fake=fk, rc=rc, out=out, rd=rd, stalled=stalled,
                stall_note=(open(os.path.join(rd, "STOPPED_NO_CKPT.txt"), encoding="utf8").read().strip() if stalled else None))


def b_case_chain(base, rid, prog, t_on, t_td, E, load, ckpt_keep=True, stop_after=None, sh="SH"):
    bc = C.kind_cfg("B", rid, dict(wind="S", U10=float(rid[1:3]), sh=sh, prog=prog, t_on=t_on, t_td=t_td, ckpt_frame=E, still_offset=0.0,
                                   out_root="runs"))
    bc["out_root"] = "runs"
    if ckpt_keep:
        bc["ckpt_keep"] = K.keep_policy("B")
    c0 = H.cost_fn("R3", int(round(t_on * FPS)) + 1, 1.0, load)
    fk = FakeHython(base, lambda f: c0(f) * H.WIND_COST, stop_after=stop_after)
    rc, out = run_chain(base, bc, fk)
    return dict(c=bc, fake=fk, rc=rc, out=out, rd=os.path.join(base, "runs", rid))


def t_p2():
    rows = []
    cases = [(prog, o, load, d) for prog in ("PR2",) for o in (140.0, 152.0, 165.0) for load in (1.0, 1.33) for d in (-9.0, -3.5, 0.0, 9.0)]
    cases += [("PR1", 140.0, 1.33, -9.0), ("PR1", 140.0, 1.33, 9.0), ("PR1", 140.0, 1.0, 9.0)]       # 作る数がいちばん多い組（record §5.3）
    b_cases = {("PR2", 152.0, 1.0, -9.0), ("PR2", 152.0, 1.0, 9.0), ("PR2", 140.0, 1.33, -3.5), ("PR1", 140.0, 1.0, 9.0)}
    for (prog, o, load, d) in cases:
        base = FX + "/p2_%s/%s_o%g_l%g_d%+g" % (STAMP, prog, o, load, d)
        m0 = len(MOVED)
        s = sh_case_chain(base, prog, o, load, d)
        rd = s["rd"]
        launches = s["fake"].launches
        made = sorted(set(k for L in launches for k in L["cks"]))
        tr, r, c, cost, t_td = sh_trace(prog, o, load, s["t_on"])
        same_sim = [(L["f0"], L["done"], L["sp"]) for L in launches] == [(L["f0"], L["done"], L["sp"]) for L in tr]
        files_before = K.ckpt_frames(rd)
        Lg = ledger(rd)
        origins = sorted(set(v.get("origin") for v in Lg.get("made", {}).values()))
        nothing_during = (files_before == made and not Lg.get("pruned") and not Lg.get("would_prune") and len(MOVED) == m0)
        if s["stalled"]:
            # 固定の区間の中で途中保存が作れずに止まった：並びは SH の段で止まる（chain_or_stop の nockpt）。片付けは走らない
            E = expect_start(made, s["t_on"])
            rows.append(dict(prog=prog, o=o, load=load, d=d, t_on=s["t_on"], f_w=s["f_w"], rc=s["rc"], launches=len(launches), made=len(made),
                             same_as_simulate=same_sim, sim_stalled=bool(r.get("stalled")), nothing_pruned_during=nothing_during, stalled=True,
                             stall_note=s["stall_note"][:300], last_done=(launches[-1]["done"] if launches else None),
                             last_s=((launches[-1]["done"] - 1) / FPS if launches else None), t_td=s["t_td"], E=E, E_there=(E in files_before)))
            print("p2", prog, o, load, d, "STALLED", s["stall_note"][:120])
            continue
        pr = K.prune_after_onset(rd, s["t_on"], f_w=s["f_w"], real=True, log=nolog)
        E = expect_start(made, s["t_on"])
        after = K.ckpt_frames(rd)
        keep = {E, max(made)} | ({s["f_w"]} if s["f_w"] in made else set())
        mv = moved_frames(rd)
        w = K.wind_start(rd, s["t_on"])
        row = dict(prog=prog, o=o, load=load, d=d, t_on=s["t_on"], f_w=s["f_w"], rc=s["rc"], launches=len(launches), made=len(made),
                   same_as_simulate=same_sim, nothing_pruned_during=nothing_during, ledger_origins=origins, E=E,
                   ok_start=(pr["start"] == E and w["start"] == E and w["why_ja"] is None and E in after), after=after, ok_keep=(set(after) == keep),
                   moved=len(mv), ok_moved=(set(mv) == set(made) - keep), after_onset_logged=bool(ledger(rd).get("after_onset")),
                   report=pr["report_ja"][:160])
        if (prog, o, load, d) in b_cases:
            b = b_case_chain(base, "B35S", prog, s["t_on"], s["t_td"], E, load)
            bL = b["fake"].launches
            bl = ledger(b["rd"])
            bm = bl.get("made", {})
            cp = bm.get(str(E), {})
            bmade_q = sorted(int(k) for k, v in bm.items() if v.get("origin") == "queue")
            bmv = moved_frames(b["rd"])
            row["B35S"] = dict(rc=b["rc"], first_f0=(bL[0]["f0"] if bL else None), ok_first=(bool(bL) and bL[0]["f0"] == E + 1),
                               f_end=b["c"]["f_end"], last_done=(bL[-1]["done"] if bL else None), launches=len(bL),
                               copy_how=cp.get("how", "")[:60], copy_origin=cp.get("origin"), sh_start_still_there=(E in K.ckpt_frames(rd)),
                               files_end=K.ckpt_frames(b["rd"]), moved=len(bmv), moved_subset_queue=set(bmv) <= set(bmade_q),
                               peak_files=None)
        rows.append(row)
        print("p2", prog, o, load, d, "E", E, "ok", row["ok_start"], row["ok_keep"], row["ok_moved"], "sim", same_sim, "B" if "B35S" in row else "")
    ok = all(r["ok_start"] and r["ok_keep"] and r["ok_moved"] and r["nothing_pruned_during"] and r["same_as_simulate"] and r["rc"] == 0
             for r in rows if not r.get("stalled"))
    ok = ok and all(r["same_as_simulate"] and r["nothing_pruned_during"] and r["E_there"] for r in rows if r.get("stalled"))
    okb = all(r["B35S"]["ok_first"] and r["B35S"]["sh_start_still_there"] and r["B35S"]["moved_subset_queue"] for r in rows if "B35S" in r)
    out = dict(rows=rows, all_ok=ok, b_ok=okb)
    save("p2", out)
    return out


# ------------------------------------------------------------------ 並びの dry-run（p3）
def queue_dry(root, args):
    env = dict(os.environ); env.pop("PYTHONUTF8", None); env["PYTHONIOENCODING"] = "utf-8"
    r = REAL_RUN([sys.executable, "g44_queue.py", "--agreed", AG, "--root", root, "--dry-run"] + args, cwd=TOOLS, capture_output=True, env=env,
                 creationflags=0x00004000)
    txt = (r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace"))
    return r.returncode, ("Traceback" in txt), txt.strip().splitlines()[-4:]


def lines(p):
    return open(p, encoding="utf8").read().strip().splitlines() if os.path.exists(p) else []


def t_p3():
    rows = []
    for (o, d, real_then_only) in ((155.0, -9.0, False), (155.0, -5.0, False), (155.0, 0.0, False), (155.0, 9.0, False), (155.0, -9.0, True)):
        base = FX + "/p3_%s_d%+g%s" % (STAMP, d, "_real" if real_then_only else "")
        s = sh_case_chain(base, "PR2", o, 1.0, d, out_root="q", cost_at="pre")
        root = base + "/q"
        made = K.ckpt_frames(s["rd"])
        E = expect_start(made, s["t_on"])
        json.dump(dict(select=dict(choice="PR2", PR3_aim_m=None, confirmed=True, confirmed_at="試し"), PR1={"pass_": True}, PR2={"pass_": True}),
                  open(root + "/queue_state.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
        os.makedirs(root + "/PR2", exist_ok=True)
        json.dump(dict(onset=dict(t=o, xc_rel=500.0, eta_c=10.0, H=14.0), touchdown=dict(t=o + TD_OFF_R3, by="cav"), selection_a={"pass_": True}),
                  open(root + "/PR2/ana.json", "w", encoding="utf8"))
        json.dump(dict(onset=dict(t=s["t_on"], xc_rel=500.0, eta_c=10.0, H=14.0), touchdown=dict(t=s["t_td"], by="cav"), still_level_offset_m=0.12,
                       notes_ja=[]), open(root + "/SH/ana.json", "w", encoding="utf8"))
        if real_then_only:
            # 並びの SH の段の片付けを、本当に消す道で動かした後（消す代わりに動かす）に、--only B35S
            S = json.load(open(root + "/queue_state.json", encoding="utf8"))
            S["SH"] = dict(onset=dict(t=s["t_on"]), touchdown=dict(t=s["t_td"], by="cav"), still=0.12)
            json.dump(S, open(root + "/queue_state.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
            pr = K.prune_after_onset(s["rd"], s["t_on"], f_w=s["f_w"], real=True, log=nolog)
            rc, tb, tail = queue_dry(root, ["--only", "B35S"])
        else:
            rc, tb, tail = queue_dry(root, ["--from", "SH"])
        rep = lines(root + "/QUEUE_REPORT.txt")
        bq = {}
        for st in ("B35S", "B45S"):
            p = root + "/%s/cfg_queue.json" % st
            if os.path.exists(p):
                q = json.load(open(p, encoding="utf8"))
                bq[st] = dict(from_frame=q.get("from_ckpt", {}).get("frame"), f_start=q.get("f_start"), keep=(q.get("ckpt_keep") or {}).get("kind"))
        Lg = ledger(s["rd"])
        after = K.ckpt_frames(s["rd"])
        keep = {E, max(made)} | ({s["f_w"]} if s["f_w"] in made else set())
        dp = root + "/DISK_PLAN_ja.md"
        row = dict(o=o, d=d, t_on=s["t_on"], E=E, f_w=s["f_w"], mode=("prune real then --only B35S" if real_then_only else "--from SH"), rc=rc,
                   traceback=tb, tail=tail, B=bq,
                   ok_B=all(v["from_frame"] == E and v["f_start"] == E + 1 for v in bq.values()) and len(bq) == (1 if real_then_only else 2),
                   files_after=len(after), made=len(made),
                   would=sorted(int(k) for k in Lg.get("would_prune", {})), ok_would=(real_then_only or set(int(k) for k in Lg.get("would_prune", {})) == set(made) - keep),
                   ok_files=(set(after) == (keep if real_then_only else set(made))),
                   report_sh=[l[:200] for l in rep if "SH：" in l][:2], report_missing=[l[:200] for l in rep if "計画の始め" in l or "走らせなかった" in l][:3],
                   disk_plan_head=[l for l in lines(dp)[:5]] if os.path.exists(dp) else None)
        rows.append(row)
        print("p3", d, real_then_only, "rc", rc, "tb", tb, "E", E, "B", bq, "ok", row["ok_B"], row["ok_would"], row["ok_files"])
    out = dict(rows=rows, all_ok=all(r["rc"] == 0 and not r["traceback"] and r["ok_B"] and r["ok_would"] and r["ok_files"] and not r["report_missing"]
                                     for r in rows))
    save("p3", out)
    return out


# ------------------------------------------------------------------ 1 本ずつの道（p4）
def origin_sets(rd):
    m = ledger(rd).get("made", {})
    return (sorted(int(k) for k, v in m.items() if v.get("origin") == "single"), sorted(int(k) for k, v in m.items() if v.get("origin") == "queue"),
            sorted(int(k) for k, v in m.items() if "origin" not in v))


def unstop(rd, tag):
    p = os.path.join(rd, "STOP")
    if os.path.exists(p):
        os.replace(p, os.path.join(rd, "STOP_used_%s" % tag))


def pr_case_chain(base, rid, prog, o, load, ckpt_keep, stop_after=None):
    c = C.kind_cfg(prog, rid, {})
    c["out_root"] = "runs"
    if ckpt_keep:
        c["ckpt_keep"] = K.keep_policy("PR")
    t_td = o + TD_OFF_R2
    c["stop_check"] = dict(module="c44px_stop", func="stop", args=dict(t1=t_td + 2 * Tc, t2=AIM[prog] + Tc))
    cost = H.cost_fn("R2", int(round(o * FPS)) + 1, 1.0, load)
    fk = FakeHython(base, cost, stop_after=stop_after)
    rc, out = run_chain(base, c, fk)
    return dict(c=c, fake=fk, rc=rc, rd=os.path.join(base, "runs", rid))


def t_p4():
    R = {}
    base = FX + "/p4_%s" % STAMP
    # 4a 形の本番：1 本ずつの道で 6 回 → 並びで最後まで → 巻き始めの後の片付け（本当に消す道。動かす）
    o, d, load = 152.0, -5.0, 1.33
    s1 = sh_case_chain(base, "PR2", o, load, d, ckpt_keep=False, stop_after=6, cost_at="pre")
    rd = s1["rd"]
    single_files = K.ckpt_frames(rd)
    unstop(rd, "a1")
    s2 = sh_case_chain(base, "PR2", o, load, d, ckpt_keep=True, cost_at="pre")
    sg, qu, no = origin_sets(rd)
    allmade = K.ckpt_frames(rd)
    pr = K.prune_after_onset(rd, s2["t_on"], f_w=s2["f_w"], real=True, log=nolog)
    left = K.ckpt_frames(rd); mv = moved_frames(rd)
    E = expect_start(allmade, s2["t_on"])
    R["4a_SH_single_then_queue"] = dict(single_files=single_files, ledger_single=sg, ledger_queue_n=len(qu), ledger_no_origin=no, E=E,
                                        start=pr["start"], left=left, moved=mv,
                                        ok=(set(single_files) <= set(left) and sg == single_files and set(mv) <= set(qu) and E in left
                                            and set(left) == set(single_files) | {E, max(allmade)} | ({s2["f_w"]} & set(allmade))))
    # 4b 風の計算：1 本ずつの道で 4 回（写しは single）→ 並びで最後まで
    t_on, t_td = s2["t_on"], s2["t_td"]
    b1 = b_case_chain(base, "B35S", "PR2", t_on, t_td, E, load, ckpt_keep=False, stop_after=4)
    brd = b1["rd"]
    bsingle = K.ckpt_frames(brd)
    unstop(brd, "b1")
    b2 = b_case_chain(base, "B35S", "PR2", t_on, t_td, E, load, ckpt_keep=True)
    sg, qu, no = origin_sets(brd)
    left = K.ckpt_frames(brd); mv = moved_frames(brd)
    R["4b_B_single_then_queue"] = dict(copy_origin=ledger(brd)["made"].get(str(E), {}).get("origin"), single_files=bsingle, ledger_single=sg,
                                       queue_made=len(qu), left=left, moved=len(mv), moved_subset_queue=set(mv) <= set(qu),
                                       second_first_f0=(b2["fake"].launches[0]["f0"] if b2["fake"].launches else None),
                                       ok=(set(bsingle) <= set(left) and set(mv) <= set(qu) and ledger(brd)["made"].get(str(E), {}).get("origin") == "single"))
    # 4c 風の計算：並びだけ（写しは queue。計算が進んだ後で写しが動くのは決まりどおり。元の形の本番の物は残る）
    b3 = b_case_chain(base, "B45S", "PR2", t_on, t_td, E, load, ckpt_keep=True)
    b3rd = b3["rd"]; sg, qu, no = origin_sets(b3rd); mv = moved_frames(b3rd)
    R["4c_B_queue_only"] = dict(copy_origin=ledger(b3rd)["made"].get(str(E), {}).get("origin"), copy_moved=(E in mv), sh_original_there=(E in K.ckpt_frames(rd)),
                                left=K.ckpt_frames(b3rd), moved=len(mv), ok=(ledger(b3rd)["made"].get(str(E), {}).get("origin") == "queue"
                                                                              and E in K.ckpt_frames(rd)))
    # 4d 下見：1 本ずつの道で 3 回 → 並びで最後まで
    p1 = pr_case_chain(base, "PR1", "PR1", 150.0, 1.0, ckpt_keep=False, stop_after=3)
    prd = p1["rd"]; psingle = K.ckpt_frames(prd); unstop(prd, "d1")
    p2 = pr_case_chain(base, "PR1", "PR1", 150.0, 1.0, ckpt_keep=True)
    sg, qu, no = origin_sets(prd); left = K.ckpt_frames(prd); mv = moved_frames(prd)
    R["4d_PR_single_then_queue"] = dict(single_files=psingle, ledger_single=sg, queue_made=len(qu), left=left, moved=mv,
                                        ok=(set(psingle) <= set(left) and set(mv) <= set(qu) and len(mv) > 0))
    # 4e 下見：並び 3 回 → 1 本ずつ 3 回 → 並びで最後まで
    q1 = pr_case_chain(base, "PR2", "PR2", 150.0, 1.0, ckpt_keep=True, stop_after=3)
    erd = q1["rd"]; unstop(erd, "e1")
    s_before = set(K.ckpt_frames(erd))
    q2 = pr_case_chain(base, "PR2", "PR2", 150.0, 1.0, ckpt_keep=False, stop_after=3)
    esingle = sorted(set(K.ckpt_frames(erd)) - s_before); unstop(erd, "e2")
    q3 = pr_case_chain(base, "PR2", "PR2", 150.0, 1.0, ckpt_keep=True)
    sg, qu, no = origin_sets(erd); left = K.ckpt_frames(erd); mv = moved_frames(erd)
    R["4e_PR_queue_single_queue"] = dict(single_made=esingle, ledger_single=sg, left=left, moved=mv,
                                         ok=(set(esingle) <= set(left) and set(sg) == set(esingle) and set(mv) <= set(qu)))
    # 4f 古い帳面（origin なし）と帳面にない物
    lrd = base + "/runs/PRL"
    os.makedirs(lrd + "/ckpt", exist_ok=True)
    for k in (100, 120):
        open(lrd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\x01" * 4096)
    json.dump(dict(made={"120": dict(bytes=4096, time="2026-10-12 05:50:00", how="launch", launch=1)}, pruned={}, would_prune={}, prune_failed={},
                   verified=[]), open(lrd + "/ckpt_ledger.json", "w", encoding="utf8"))
    c = C.kind_cfg("PR1", "PRL", {}); c["out_root"] = "runs"; c["ckpt_keep"] = K.keep_policy("PR")
    c["stop_check"] = dict(module="c44px_stop", func="stop", args=dict(t1=150.0 + TD_OFF_R2 + 2 * Tc, t2=AIM["PR1"] + Tc))
    fk = FakeHython(base, H.cost_fn("R2", int(round(150.0 * FPS)) + 1, 1.0, 1.0))
    run_chain(base, c, fk)
    left = K.ckpt_frames(lrd); mv = moved_frames(lrd)
    R["4f_legacy_and_unlisted"] = dict(left_head=left[:4], moved_n=len(mv), ok=(100 in left and 120 in left and 100 not in mv and 120 not in mv))
    # 4g 同じコマの作り直し（g44_ckpt を直に）：並びが作って消したコマを、1 本ずつの道が作り直した時
    grd = base + "/runs/PRG"
    os.makedirs(grd + "/ckpt", exist_ok=True)
    pol = K.keep_policy("PR")
    for k in (240, 480, 720):
        open(grd + "/ckpt/v.%04d.sim" % k, "wb").write(b"\x01" * 4096)
    K.after_launch(grd, dict(out_root="runs", ckpt_keep=pol), 1, 720, [], 10.0, 6.0, log=nolog)      # queue が 240・480・720 を作る
    b0 = K.ckpt_frames(grd)
    open(grd + "/ckpt/v.0960.sim", "wb").write(b"\x01" * 4096)
    K.after_launch(grd, dict(out_root="runs", ckpt_keep=pol), 721, 960, b0, 10.0, 6.0, log=nolog)   # 720 を確かめ、ほかを消す
    gone = moved_frames(grd)
    b4 = K.ckpt_frames(grd)
    open(grd + "/ckpt/v.0480.sim", "wb").write(b"\x01" * 4096)                                          # 1 本ずつの道が 480 を作り直した（作りの真似）
    K.after_launch(grd, dict(out_root="runs"), 241, 480, b4, 10.0, 6.0, log=nolog)
    o480 = ledger(grd)["made"]["480"].get("origin")
    b5 = K.ckpt_frames(grd)
    open(grd + "/ckpt/v.1200.sim", "wb").write(b"\x01" * 4096)
    K.after_launch(grd, dict(out_root="runs", ckpt_keep=pol), 961, 1200, b5, 10.0, 6.0, log=nolog)
    R["4g_frame_remade_by_single"] = dict(first_moved=gone, origin_480_after_single=o480, left=K.ckpt_frames(grd), moved=moved_frames(grd),
                                          remade_480_moved_again=(moved_frames(grd).count(480) >= 2))
    out = dict(R=R, all_ok=all(v.get("ok", True) for v in R.values()))
    save("p4", out)
    for k, v in R.items():
        print("p4", k, v.get("ok"), {kk: vv for kk, vv in v.items() if kk in ("moved", "left", "single_files", "origin_480_after_single")})
    return out


# ------------------------------------------------------------------ 置き場所（p5）
def t_p5():
    free = shutil.disk_usage("G:/").free / 2**30
    d_all = K.disk_plan(["PR1", "PR2", "PR3", "SH", "B35S", "B45S", "RP"])
    n2 = {ch: K.disk_plan(["SH", "B35S", "B45S", "RP"], choice=ch) for ch in ("PR1", "PR2")}
    CB = K.ckpt_bytes()
    p1 = (json.load(open(RES, encoding="utf8")).get("p1") or {}) if os.path.exists(RES) else {}
    mm = max((p1.get("made_max") or {"x": 0}).values())
    rows = {r["stage"]: r for r in d_all["rows"]}
    sh = rows["SH"]
    sh_peak_mine = mm * CB[0.25] / 2**30
    others_peak = max(r["peak_extra_gb"] for k, r in rows.items() if k != "SH")
    need_mine = d_all["total_keep_gb"] + max(others_peak, sh_peak_mine - sh["end"] * CB[0.25] / 2**30)
    # 片付けが 1 個も消さない時（巻き始めが道の最初・始めがない）：形の本番の作った物が全部残ったまま風と繰り返しへ進む
    no_sh_prune = d_all["total_keep_gb"] - sh["keep_gb"] + (mm * CB[0.25] + sh["records_gb"] * 2**30) / 2**30 + others_peak
    out = dict(free_gib=free, stop_gib=STOP_GB, usable_gib=free - STOP_GB, ckpt_gib=dict(dp034=CB[0.34375] / 2**30, dp025=CB[0.25] / 2**30),
               plan_all=dict(need=d_all["total_need_gb"], keep=d_all["total_keep_gb"], peak_extra=d_all["peak_extra_gb"], no_prune=d_all["total_all_gb"],
                             rows=[{k: r[k] for k in ("stage", "made_max", "end", "peak", "keep_gb", "all_gb_max", "peak_extra_gb", "load", "onset")}
                                   for r in d_all["rows"]]),
               night2={ch: dict(need=v["total_need_gb"], no_prune=v["total_all_gb"]) for ch, v in n2.items()},
               sh_made_max_disk_plan=sh["made_max"], sh_made_max_p1=mm, sh_peak_gib_p1=sh_peak_mine, need_with_p1_max=need_mine,
               need_if_sh_not_pruned=no_sh_prune,
               fits=dict(plan=d_all["total_need_gb"] <= free - STOP_GB, mine=need_mine <= free - STOP_GB, no_sh_prune=no_sh_prune <= free - STOP_GB,
                         no_prune_at_all=d_all["total_all_gb"] <= free - STOP_GB),
               queue_blocks_below_free_gib=d_all["total_need_gb"] + STOP_GB)
    save("p5", out)
    print("p5", json.dumps({k: out[k] for k in ("free_gib", "sh_made_max_disk_plan", "sh_made_max_p1", "need_with_p1_max", "need_if_sh_not_pruned", "fits")}))
    return out


# ------------------------------------------------------------------ 前と後
def snap():
    fr = json.load(open(B44 + "/plan/plan_frozen.json", encoding="utf8"))
    sha = {}
    for e in fr["frozen"]:
        h = hashlib.sha256(open(os.path.join(REPO, e["path"]), "rb").read()).hexdigest()
        sha[e["path"]] = (h == e["sha256"])
    lst = {}
    for d in ("runs", "plan"):
        for p in sorted(glob.glob(B44 + "/%s/**" % d, recursive=True)):
            if os.path.isfile(p):
                lst[os.path.relpath(p, B44).replace("\\", "/")] = [os.path.getsize(p), round(os.path.getmtime(p), 1)]
    return dict(sha_ok=sha, files=lst)


def main():
    parts = sys.argv[1:] or ["p1", "p2", "p3", "p4", "p5"]
    pri = lower_self()
    s0 = snap()
    t0 = time.time()
    for p in parts:
        {"p1": t_p1, "p2": t_p2, "p3": t_p3, "p4": t_p4, "p5": t_p5}[p]()
    s1 = snap()
    save("snap_" + "_".join(parts), dict(below_normal=pri, sha_ok_before=s0["sha_ok"], sha_ok_after=s1["sha_ok"], runs_plan_same=(s0["files"] == s1["files"]),
                                         runs_plan_files=sorted(s1["files"]), moved_n=len(MOVED), moved_outside_fx3=[m for m in MOVED if not m.lower().startswith(FX.lower())],
                                         wall_s=time.time() - t0))
    print("snap same", s0["files"] == s1["files"], "sha", s1["sha_ok"], "moved", len(MOVED), "wall %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
