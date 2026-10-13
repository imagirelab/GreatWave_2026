# -*- coding: utf-8 -*-
"""FLIP44：直し（record_ja.md §3 の 9・§3.1 D1〜D6）の確かめ。作った側の試し（x44_fix_tests.py）とは別の記録・別の作り方で通す（py -3.10）。
流体の計算はしない。自分の優先度を「通常より下」にし、電力の抑えを外す。子の py も「通常より下」で起こす。
試しの物は Unity/Build/FLIP44/check/fx/ に作る。smoke/・runs/・fixes/・FLIP42 は読むだけ。
  c0 ：凍結した 4 つの SHA-256、runs/ready の作り直し、runs/ に古い並びの状態がないか、hython が動いていないか、G: の空き
  c1 ：F1（D1）。FLIP42 R2（作った側は R3）から、形の本番の役 SHx と、途中保存から始めた風の計算の役 Bx（とその変わり種）を作って解析。
       S9_v2（煙の試し）を読むだけで解析（出力は check/fx へ）。Bx → g44_wind_check → g44_ctable を通す
  c2 ：F2（§3 の 9・D2）。g44_queue の chain_result・wind_after を、作った記録で通す（解析と風の判定は本当に走らせる）。B の段の dry-run
  c3 ：F5（D5）。選びの後の止まりと、続ける言葉。作った側と違う組（下見 1 が外れ、下見 2 が入る）と、両方外れる組
  c4 ：F6（D6）。wind=N と wind_mode=2 の拒み方の変わり種
  c5 ：F7（D3）。N5 の組み方を、x–t の水面で頂をたどって確かめる（FLIP42 R3）
  c6 ：F4（D4）・F2。g44_chain の決まりを自分で真似し直し、FLIP42 の起動の区切りと比べる。風の打ち切り・機械の重さ・途中保存の置き場所
  c7 ：形の本番の固定の中の止まり（機械の重さ 1.0〜2.0）、確かめを通らない段（dry-run）、g44_video の静かな水面、夜に PC を起こしておく呼び出し
  c8 ：1 コマ目からの計算（FLIP42 R3・煙の試し S8）の読みが直しの前の ana と同じか
  c9 ：2 点の方法・低い揺れ・N5 の、空と全部 NaN の守り
出力：Unity/Build/FLIP44/check/c44_fix_check.json（試しごとに足す）
"""
import sys, os, json, glob, shutil, subprocess, time, hashlib, math, ctypes
from ctypes import wintypes
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip44"
B44 = REPO + "/Unity/Build/FLIP44"
R42 = REPO + "/Unity/Build/FLIP42/runs"
FXR = "check/fx"                    # 解析の道具に渡す root（B44 の下）
FX = B44 + "/" + FXR
RES = B44 + "/check/c44_fix_check.json"
sys.path.insert(0, TOOLS)
import g44_analyze as A

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
    d = json.load(open(RES, encoding="utf8")) if os.path.exists(RES) else {}
    d[key] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), **val)
    json.dump(d, open(RES, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)


def py(args, utf8=True, cwd=TOOLS):
    env = dict(os.environ)
    if utf8:
        env["PYTHONIOENCODING"] = "utf-8"
    else:
        env.pop("PYTHONIOENCODING", None); env.pop("PYTHONUTF8", None)
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, env=env, creationflags=0x00004000)
    dec = (lambda b: b.decode("utf-8", errors="replace")) if utf8 else (lambda b: b.decode("cp932", errors="replace"))
    return r.returncode, dec(r.stdout), dec(r.stderr)


def jl(p):
    return json.load(open(p, encoding="utf8"))


# ------------------------------------------------------------------ c0
def c0():
    out = {}
    fr = jl(B44 + "/plan/plan_frozen.json")
    sh = {}
    for f in fr["frozen"]:
        h = hashlib.sha256(open(os.path.join(REPO, f["path"]), "rb").read()).hexdigest()
        sh[f["path"]] = h == f["sha256"]
    out["frozen_sha_same"] = sh
    same = {}
    for name, args in (("PR1", ["PR1", "PR1"]), ("PR2", ["PR2", "PR2"]), ("RP_reef500", ["RP", "RP", "aim=reef"]), ("RP_flat592", ["RP", "RP", "aim=flat"])):
        rc, so, se = py(["g44_cfg.py"] + args)
        same[name] = bool(rc == 0 and so.replace("\r\n", "\n").strip() == open(os.path.join(B44, "runs", "ready", name + ".json"), encoding="utf8").read().strip())
    out["ready_regen_same_stdout"] = same
    out["runs_dir"] = sorted(os.listdir(B44 + "/runs"))
    tl = subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()
    out["hython_running"] = "hython" in tl
    out["houdini_running"] = "houdini" in tl
    out["G_free_GiB"] = shutil.disk_usage("G:/").free / 2**30
    out["pr3_aim_files_in_plan"] = sorted(os.path.basename(p) for p in glob.glob(B44 + "/plan/pr3_aim*.json"))
    save("c0", out)
    print(json.dumps(out, ensure_ascii=False, default=float))


# ------------------------------------------------------------------ c1（F1）
def r2_full():
    """FLIP42 R2 を今の道具で 1 コマ目から読む（比べる元）。"""
    p = FX + "/ana_R2_full.json"
    if not os.path.exists(p):
        os.makedirs(FX, exist_ok=True)
        A.analyze("R2", "flip42", out_path=p)
    return jl(p)


def cut_run(dst, src_rd, f0, f1, sec0=None, sec1=None, cfg_mod=None, nan_t=None, copy_first_hf=False):
    """src_rd の f0〜f1 コマの一番上の水面と、sec0〜sec1 の断面を、dst に 1 回の起動の記録として書く。"""
    rd = os.path.join(FX, dst)
    os.makedirs(rd, exist_ok=True)      # 消さない。同じ名前のファイルは上書き
    D = A.load_hf(src_rd)
    if copy_first_hf:
        shutil.copy2(os.path.join(src_rd, "hf_c0001.npz"), rd)
    k = (D["frames"] >= f0) & (D["frames"] <= f1)
    eta = D["eta"][k].copy()
    if nan_t is not None:
        tt = D["t"][k]
        eta[(tt >= nan_t[0]) & (tt <= nan_t[1])] = np.nan
    np.savez_compressed(os.path.join(rd, "hf_c%04d.npz" % f0), eta=eta, x=D["x"], z=D["z"], frames=D["frames"][k], t=D["t"][k],
                        wall=D["wall"][k], npts=D["npts"][k], ss_n=D["ss_n"][k], wind_calls=D["wind_calls"][k])
    if sec0 is not None:
        SR = A.SecReader(src_rd)
        fr = [f for f in SR.frames if sec0 <= f <= sec1]
        sdf = np.stack([np.clip(SR.get(f), -8, 8).astype(np.float16) for f in fr])
        np.savez_compressed(os.path.join(rd, "sec_c%04d_b%04d.npz" % (f0, fr[0])), sdf=sdf, frames=np.array(fr), meta=json.dumps(SR.meta))
    cfg = jl(os.path.join(src_rd, "cfg.json"))
    cfg["run_id"] = dst
    if cfg_mod:
        cfg_mod(cfg)
    json.dump(cfg, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return rd


def my_still(rd_hf_file, xp):
    """計画 N1 の自分の読み：0.5〜2.0 s・造波板から 0〜930 m の一番上の水面の中央値（z の節を (a) 2 番目だけ、(b) 内側の全部）。"""
    d = np.load(rd_hf_file)
    fr = d["frames"]; t = (fr - 1) / FPS
    m = (t >= 0.5) & (t <= 2.0)
    x = d["x"]; xm = (x >= xp) & (x <= xp + 930.0)
    e = d["eta"][m][:, :, xm].astype(np.float64)
    return dict(z2=float(np.nanmedian(e[:, 2, :])), zin=float(np.nanmedian(e[:, 1:-1, :])), n_frames=int(m.sum()))


def c1():
    lower = None
    out = {}
    os.makedirs(FX, exist_ok=True)
    R2 = R42 + "/R2"
    ref = r2_full()
    on, td = ref["onset"], ref["touchdown"]
    out["R2_full"] = dict(onset=[on["frame"], on["t"], on["xc_rel"], on["eta_c"], on["H"]], touchdown=[td["frame"], td["by"]],
                          still=ref["still_level_offset_m"], flip42_ana_still=jl(R2 + "/ana.json")["still_level_offset_m"])
    xp = jl(R2 + "/cfg.json")["parms"]["x_p"]
    out["R2_my_still"] = my_still(R2 + "/hf_c0001.npz", xp)
    f_on = on["frame"]; f_td = td["frame"]; Tc = A.plan()["tank"]["Tc"]
    t_on = on["t"]; t_td = td["t"]
    ckf = f_on - 144                                   # 巻き始めの 6 s 前（形の本番の f_w の役）
    f_cap = int(math.floor((t_td + 2 * Tc) * FPS + 1e-9)) + 1
    f_sec0 = int(round((t_on - 3.5) * FPS)) + 1        # g44_cfg の B の sec_t0 ＝ t_on − 3 − 0.5
    out["frames"] = dict(ckf=ckf, f_on=f_on, f_td=f_td, f_cap=f_cap, f_sec0=f_sec0)
    # 形の本番の役 SHx：1 コマ目からの記録（R2 の始めの起動の hf をそのまま写す）＋ 3400〜4100 コマの水面と断面
    cut_run("SHx", R2, 3400, 4100, 3400, 4100, copy_first_hf=True)
    rc, so, se = py(["g44_analyze.py", "SHx", FXR])
    sx = jl(FX + "/SHx/ana.json") if rc == 0 else {}
    out["SHx"] = dict(rc=rc, err=se[-400:], still=sx.get("still_level_offset_m"), started_from_ckpt=sx.get("started_from_ckpt"),
                      onset=(sx.get("onset") or {}).get("frame"), touchdown=(sx.get("touchdown") or {}).get("frame"),
                      same_as_full=bool(sx and sx["onset"]["frame"] == f_on and sx["touchdown"]["frame"] == f_td
                                        and sx["still_level_offset_m"] == ref["still_level_offset_m"]))
    still_sh = sx.get("still_level_offset_m")
    q = 0.5 * 1.2 * (35 + 12) ** 2

    def bmod(still_val, src_run="SHx", from_frame=ckf, with_from=True, still_from=True):
        def f(c):
            if with_from:
                c["from_ckpt"] = dict(run=src_run, frame=from_frame)          # 本番と同じ：root を書かない（解析と同じ置き場所）
            c["parms"].update(wind_on=1.0, wind_mode=1.0, wind_q=q, wind_t0=t_on - 3.0, wind_tramp=1.0, wind_t1=1e9,
                              wind_x0=xp, wind_x1=xp + 930.86, wind_tap=10.0, ytop=18.0, thin_mult=2.0)
            st = dict(after_s=0.5, t_from=t_on - 1.0, Lc=135.46329754326246, still_offset_m=still_val)
            if still_from:
                st["still_offset_from"] = "c44_fix_check（SHx の ana.json）"
            c["stop_touchdown"] = st
            c["case"] = dict(c.get("case", {}), form="S", U10=35.0, t_on_SH=t_on, t_td_SH=t_td)
            c["sec"] = dict(c["sec"], t0=t_on - 3.5)
        return f
    cases = {
        # 名前: (f_end, sec0, cfg_mod, 期待)
        "Bx_cap": (f_cap, f_sec0, bmod(still_sh), "onset/touchdown/still が SHx と同じ"),
        "Bx_online": (f_td + 12, f_sec0, bmod(still_sh), "着水 + 0.5 s で切れた記録でも着水が取れる"),
        "Bx_pre": (f_on - 24, f_sec0, bmod(still_sh), "巻き始めの前で切れた記録：止まらず、巻き始めなしと書く"),
        "Bx_warn": (f_td + 12, f_sec0, bmod(0.0), "cfg の値 0.0 との違いを書き残す"),
        "Bx_late": (f_cap, f_on + 4, bmod(still_sh), "断面が巻き始めの後から（本番では起きない）：どう読むか"),
    }
    for name, (f1, s0, mod, want) in cases.items():
        cut_run(name, R2, ckf + 1, f1, s0, f1, cfg_mod=mod)
        rc, so, se = py(["g44_analyze.py", name, FXR])
        a = jl(FX + "/%s/ana.json" % name) if rc == 0 else {}
        out[name] = dict(want=want, rc=rc, err=se[-400:], still=a.get("still_level_offset_m"), how=(a.get("still_level_source") or {}).get("how"),
                         warn=(a.get("still_level_source") or {}).get("warning_ja"), ckpt=a.get("started_from_ckpt"),
                         onset=(a.get("onset") or {}).get("frame"), onset_t=(a.get("onset") or {}).get("t"),
                         onset_eta=(a.get("onset") or {}).get("eta_c"), touchdown=(a.get("touchdown") or {}).get("frame"),
                         td_by=(a.get("touchdown") or {}).get("by"), N3_N7_skipped=bool(a.get("N3_N7_skipped_ja")), has_N5="N5" in a,
                         gauges_note=bool(a.get("gauges_note_ja")), notes=a.get("notes_ja"))
    # 元の計算の hf が読めない時：ana.json の値へ下りる（SHy は ana.json と cfg.json だけ）
    os.makedirs(FX + "/SHy", exist_ok=True)
    shutil.copy2(FX + "/SHx/cfg.json", FX + "/SHy/cfg.json"); shutil.copy2(FX + "/SHx/ana.json", FX + "/SHy/ana.json")
    cut_run("Bx_anaonly", R2, ckf + 1, f_td + 12, f_sec0, f_td + 12, cfg_mod=bmod(still_sh, src_run="SHy"))
    rc, so, se = py(["g44_analyze.py", "Bx_anaonly", FXR])
    a = jl(FX + "/Bx_anaonly/ana.json") if rc == 0 else {}
    out["Bx_anaonly"] = dict(rc=rc, err=se[-300:], how=(a.get("still_level_source") or {}).get("how"), still=a.get("still_level_offset_m"),
                             hf_err=(a.get("still_level_source") or {}).get("source_hf_error"))
    # 元の計算の 0.5〜2.0 s が全部 NaN：ana.json へ下りる
    cut_run("SHn", R2, 3400, 4100, None, None, copy_first_hf=False)
    d0 = np.load(R2 + "/hf_c0001.npz")
    e0 = d0["eta"].copy(); e0[:60] = np.nan
    np.savez_compressed(FX + "/SHn/hf_c0001.npz", **{k: d0[k] for k in d0.files if k != "eta"}, eta=e0)
    shutil.copy2(FX + "/SHx/ana.json", FX + "/SHn/ana.json")
    cut_run("Bx_srcnan", R2, ckf + 1, f_td + 12, f_sec0, f_td + 12, cfg_mod=bmod(still_sh, src_run="SHn"))
    rc, so, se = py(["g44_analyze.py", "Bx_srcnan", FXR])
    a = jl(FX + "/Bx_srcnan/ana.json") if rc == 0 else {}
    out["Bx_srcnan"] = dict(rc=rc, err=se[-300:], how=(a.get("still_level_source") or {}).get("how"), still=a.get("still_level_offset_m"),
                            hf_err=((a.get("still_level_source") or {}).get("source_hf_error") or "")[:200])
    # 元の計算も ana.json もなく、cfg の値に出所が書いていない → 止まる（コード 3）
    cut_run("Bx_nosrc", R2, ckf + 1, f_td + 12, f_sec0, f_td + 12, cfg_mod=bmod(still_sh, src_run="SH_none", still_from=False))
    rc, so, se = py(["g44_analyze.py", "Bx_nosrc", FXR])
    out["Bx_nosrc"] = dict(rc=rc, err=se.strip()[-300:])
    # 同じ、ただし標準出力を cp932 のまま（PowerShell の外や Git Bash から走らせた時の形）
    rc, so, se = py(["g44_analyze.py", "Bx_nosrc", FXR], utf8=False)
    out["Bx_nosrc_cp932"] = dict(rc=rc, err=se.strip()[-300:])
    rc, so, se = py(["g44_analyze.py", "Bx_online", FXR], utf8=False)
    out["Bx_online_cp932"] = dict(rc=rc, err=se.strip()[-300:])
    # 風の判定と表（Bx_cap を風あり、SHx を風なしに）
    rc, so, se = py(["g44_wind_check.py", "Bx_cap", "SHx", FXR])
    w = jl(FX + "/Bx_cap/wind_check.json") if rc == 0 else {}
    m = (w.get("W1_5") or {}).get("measures") or []
    out["wind_check_Bx_cap"] = dict(rc=rc, err=se[-500:], still=w.get("still_offset_m"), W6_frames=(w.get("W6") or {}).get("frames"),
                                    W8_rows=len((w.get("W8") or {}).get("rows", [])),
                                    W8_max_abs=max([abs(r["d_eta"]) for r in (w.get("W8") or {}).get("rows", [])] or [None]) if (w.get("W8") or {}).get("rows") else None,
                                    W8_gauges=(w.get("W8") or {}).get("gauges"), W1_5_n=len(m),
                                    W1_5_max_abs=max([abs(r["delta"]) for r in m if "delta" in r] or [None]) if m else None,
                                    W1_5_err=(w.get("W1_5") or {}).get("error"), onset_cmp=(w.get("W1_5") or {}).get("onset"))
    rc, so, se = py(["g44_wind_check.py", "Bx_online", "SHx", FXR])
    w = jl(FX + "/Bx_online/wind_check.json") if rc == 0 else {}
    out["wind_check_Bx_online"] = dict(rc=rc, err=se[-300:], W8_rows=len((w.get("W8") or {}).get("rows", [])),
                                       W1_5_err=(w.get("W1_5") or {}).get("error"), onset_cmp=(w.get("W1_5") or {}).get("onset"))
    rc, so, se = py(["g44_ctable.py", "SHx", "--wind", "B35S=Bx_cap", "B45S=Bx_online", "--root", FXR, "--out", FX + "/ctable"])
    out["ctable"] = dict(rc=rc, err=se[-300:], md=os.path.exists(FX + "/ctable/remaining_gap_ja.md"))
    # 風の計算が 1 本も表に入らない時（並びは --wind を渡さない）。cp932 の標準出力でも止まらないか
    rc, so, se = py(["g44_ctable.py", "SHx", "--root", FXR, "--out", FX + "/ctable0"], utf8=False)
    out["ctable_nowind_cp932"] = dict(rc=rc, err=se.strip()[-300:], md=os.path.exists(FX + "/ctable0/remaining_gap_ja.md"))
    # S9_v2（煙の試しの風の計算）：読むだけ。出力は check/fx へ
    try:
        a = A.analyze("S9_v2", "smoke", out_path=FX + "/ana_S9_v2.json")
        s8 = my_still(B44 + "/smoke/S8/hf_c0001.npz", jl(B44 + "/smoke/S8/cfg.json")["parms"]["x_p"])
        out["S9_v2"] = dict(ok=True, still=a["still_level_offset_m"], how=a["still_level_source"].get("how"), my_S8_still=s8,
                            onset=a.get("onset"), notes=a.get("notes_ja"))
    except Exception as e:
        out["S9_v2"] = dict(ok=False, err=repr(e)[:300])
    # 止める決まり（g44_chain が下見・形の本番の起動ごとに呼ぶ）を、1 コマ目からの記録 SHx で
    cfg_sh = jl(FX + "/SHx/cfg.json")
    cfg_sh.setdefault("case", {})["aim_t_s"] = 0.0
    st = {}
    for tdone in (t_td + 2 * Tc - 0.5, t_td + 2 * Tc + 0.5):
        try:
            s, note = A.stop_main_touchdown("SHx", FXR, tdone, cfg_sh)
            st["%.2f" % tdone] = [s, str(note)[:120]]
        except Exception as e:
            st["%.2f" % tdone] = ["error", repr(e)[:200]]
    out["stop_main_touchdown_SHx"] = st
    save("c1_F1", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:6000])


# ------------------------------------------------------------------ c2（F2・D2）
def c2():
    import g44_queue as Q
    out = {}
    # (a) chain_result の読み分け（作った起動の記録と STOPPED_*.txt。古いファイルは読まない）
    TAG = time.strftime("%H%M%S")      # 試しの置き場所は毎回新しく作る（消さない）
    cr = FX + "/qcr_" + TAG
    Q.setup(FXR + "/qcr_" + TAG)
    t_now = time.time()

    def mk(rid, done, stopped, files=(), old=(), stopfile=False):
        rd = os.path.join(cr, rid); os.makedirs(rd, exist_ok=True)
        json.dump(dict(f_end_done=done, stopped=stopped), open(os.path.join(rd, "run_c0577.json"), "w", encoding="utf8"))
        for n in files:
            open(os.path.join(rd, n), "w", encoding="utf8").write("new " + n)
        for n in old:
            p = os.path.join(rd, n); open(p, "w", encoding="utf8").write("old " + n); os.utime(p, (t_now - 3600, t_now - 3600))
        if stopfile:
            open(os.path.join(rd, "STOP"), "w").close()
    mk("cut", 700, "wall_limit at frame 700", files=("STOPPED_MAX_HOURS.txt",))
    mk("cut_old", 700, "wall_limit at frame 700", old=("STOPPED_MAX_HOURS.txt",))
    mk("online", 800, "touchdown_online at frame 790 (+0.50 s)")
    mk("done", 1100, "wall_limit at frame 1100")
    mk("rule_old_and_cut", 700, "wall_limit at frame 700", files=("STOPPED_MAX_HOURS.txt",), old=("STOPPED_BY_RULE.txt",))
    mk("nockpt", 650, "wall_limit at frame 650", files=("STOPPED_NO_CKPT.txt",))
    mk("stopfile", 650, "wall_limit at frame 650", stopfile=True)
    mk("freefall", 640, "free_fall at frame 640 (mean level -1.20 m, start 0.00 m)")
    os.makedirs(os.path.join(cr, "crash"), exist_ok=True)
    os.makedirs(os.path.join(cr, "disk"), exist_ok=True); open(os.path.join(cr, "disk", "STOP_DISK.txt"), "w", encoding="utf8").write("disk")
    res = {}
    for rid in ("cut", "cut_old", "online", "done", "rule_old_and_cut", "nockpt", "stopfile", "freefall", "crash", "disk"):
        s, d, why = Q.chain_result(rid, 1100, t_now - 5)
        res[rid] = [s, d, why[:80] if isinstance(why, str) else why]
    out["chain_result"] = res
    # (b) wind_after を本当の解析で（B35S ＝ 打ち切りで切れたが巻き始めと着水を含む、B45S ＝ 巻き始めの前で切れた）
    qw = FX + "/qw_" + TAG
    os.makedirs(qw)
    os.makedirs(qw + "/SH")
    for p in glob.glob(FX + "/SHx/*.npz") + [FX + "/SHx/cfg.json", FX + "/SHx/ana.json"]:
        shutil.copy2(p, qw + "/SH")
    c = jl(qw + "/SH/cfg.json"); c["run_id"] = "SH"; json.dump(c, open(qw + "/SH/cfg.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for st_, src in (("B35S", "Bx_cap"), ("B45S", "Bx_pre")):
        os.makedirs(qw + "/" + st_)
        for p in glob.glob(FX + "/" + src + "/*.npz") + [FX + "/" + src + "/cfg.json"]:
            shutil.copy2(p, qw + "/" + st_)
        c = jl(qw + "/%s/cfg.json" % st_); c["run_id"] = st_; c["from_ckpt"] = dict(run="SH", frame=c["from_ckpt"]["frame"])
        json.dump(c, open(qw + "/%s/cfg.json" % st_, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        json.dump(dict(f_end_done=int(np.load(glob.glob(qw + "/%s/hf_c*.npz" % st_)[0])["frames"].max()), stopped="wall_limit"),
                  open(qw + "/%s/run_c%04d.json" % (st_, c["f_start"] if "f_start" in c else 1), "w", encoding="utf8"))
        open(qw + "/%s/STOPPED_MAX_HOURS.txt" % st_, "w", encoding="utf8").write("打ち切りの時間（c44 の試し）")
    Q.setup(FXR + "/qw_" + TAG)
    Q.AGREED = "c44 の試し（本番ではない）"
    S = dict(select=dict(choice="PR1", confirmed=True), SH=dict(onset=jl(qw + "/SH/ana.json")["onset"], touchdown=jl(qw + "/SH/ana.json")["touchdown"],
                                                                still=jl(qw + "/SH/ana.json")["still_level_offset_m"]))
    for st_ in ("B35S", "B45S"):
        s, d, why = Q.chain_result(st_, 99999, time.time() - 60)
        Q.wind_after(st_, S, s, d, why)
    out["wind_after"] = dict(state=S.get("wind"), report=open(qw + "/QUEUE_REPORT.txt", encoding="utf8").read()[-1500:],
                             B35S_wind_check=os.path.exists(qw + "/B35S/wind_check.json"))
    for st_, s in (("B35S", "disk"), ("B35S", "stopfile")):
        try:
            Q.wind_after(st_, dict(S), s, 0, "試し")
            out["wind_after_" + s] = "returned（止まらなかった）"
        except SystemExit as e:
            out["wind_after_" + s] = "SystemExit %s" % e.code
    # 表の段：complete の物だけ --wind に入るか（dry-run で言葉だけ）
    json.dump(S, open(qw + "/queue_state.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    rc, so, se = py(["g44_queue.py", "--agreed", "c44 の試し（本番ではない）", "--root", FXR + "/qw_" + TAG, "--dry-run", "--only", "TABLE"])
    out["table_dry"] = dict(rc=rc, log=[l for l in (so + se).splitlines() if "g44_ctable" in l or "表" in l][-4:])
    # (c) B の段の dry-run：形の本番の途中保存（空のファイル）と状態を置き、B35S から最後まで
    for name0, cks in (("qwd", (3240, 3480, 3560, 3600, 3624, 3660)), ("qwd_none", (3700, 3720))):
        name = name0 + "_" + TAG
        qd = FX + "/" + name
        os.makedirs(qd + "/SH/ckpt")
        for k in cks:
            open(qd + "/SH/ckpt/v.%04d.sim" % k, "w").close()
        shutil.copy2(FX + "/SHx/ana.json", qd + "/SH/ana.json")
        json.dump(S, open(qd + "/queue_state.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
        rc, so, se = py(["g44_queue.py", "--agreed", "c44 の試し（本番ではない）", "--root", FXR + "/" + name, "--dry-run", "--from", "B35S"])
        r = dict(rc=rc, tail=(so + se).strip().splitlines()[-12:])
        for st_ in ("B35S", "B45S"):
            p = qd + "/%s/cfg_queue.json" % st_
            if os.path.exists(p):
                c = jl(p)
                r[st_] = dict(max_hours=c.get("max_hours"), basis=(c["case"].get("max_hours_basis") or {}).get("est_hours_cap_path"),
                              f_start=c["f_start"], f_end=c["f_end"], from_ckpt=c.get("from_ckpt"), still=c["stop_touchdown"]["still_offset_m"],
                              t_from=c["stop_touchdown"]["t_from"], wind_t0=c["parms"]["wind_t0"], sec_t0=c["sec"]["t0"], q=c["parms"]["wind_q"],
                              ckpt_list=c["ckpt_list"], out_root=c.get("out_root"))
        r["report"] = open(qd + "/QUEUE_REPORT.txt", encoding="utf8").read()[-800:] if os.path.exists(qd + "/QUEUE_REPORT.txt") else None
        out["dry_from_B35S_" + name0] = r
    save("c2_F2", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:8000])


# ------------------------------------------------------------------ c3（F5・D5）
def c3():
    out = {}
    AG = "c44 の試し（本番ではない）"
    r3 = jl(B44 + "/check/ana44_R3.json")
    # 下見 1 が外れ、下見 2 が入る組（作った側の試しは逆）。下見 1 ＝ R3 の巻き始めを窓の外へ動かした物
    fail = json.loads(json.dumps(r3))
    fail["selection_a"]["pass_"] = False; fail["selection_a"]["c1_onset_in_window"] = False
    fail["onset"]["xc_rel"] = 600.0
    TAG = time.strftime("%H%M%S")
    RT = {"qsel": "qsel_" + TAG, "qpr3": "qpr3_" + TAG}
    for name, pr1, pr2 in (("qsel", fail, r3), ("qpr3", fail, fail)):
        q = FX + "/" + RT[name]
        for k, a in (("PR1", pr1), ("PR2", pr2)):
            os.makedirs(q + "/" + k)
            json.dump(a, open(q + "/%s/ana.json" % k, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    steps = []
    plan = [("qsel", "select", ["--only", "SELECT"], 3),
            ("qsel", "from_SH_no_confirm", ["--from", "SH"], 3),
            ("qsel", "only_SH_no_confirm", ["--only", "SH"], 3),
            ("qsel", "from_RP_no_confirm", ["--from", "RP"], None),
            ("qsel", "only_TABLE_no_confirm", ["--only", "TABLE"], None),
            ("qsel", "confirm_PR1_wrong", ["--confirm-select", "PR1"], 1),
            ("qsel", "confirm_pr3_wrong", ["--confirm-pr3"], 1),
            ("qsel", "confirm_PR2", ["--confirm-select", "PR2"], 0),
            ("qsel", "rerun_PR1_then_confirm", ["--only", "PR1"], None),
            ("qsel", "confirm_after_rerun", ["--confirm-select", "PR2"], 1),
            ("qpr3", "select_both_fail", ["--only", "SELECT"], 3),
            ("qpr3", "confirm_PR3", ["--confirm-select", "PR3"], None)]
    for root, name, args, want in plan:
        rc, so, se = py(["g44_queue.py", "--agreed", AG, "--root", FXR + "/" + RT[root], "--dry-run"] + args)
        txt = (so + se).strip()
        steps.append(dict(root=root, step=name, rc=rc, want=want, ok=(None if want is None else rc == want), tail=txt.splitlines()[-6:]))
    out["steps"] = steps
    sel = jl(FX + "/" + RT["qsel"] + "/select.json")
    out["qsel_choice"] = sel["choice"]
    sh = FX + "/" + RT["qsel"] + "/SH/cfg_queue.json"
    out["qsel_SH_cfg"] = (lambda c: dict(prog=c["case"]["prog"], f_w=c["case"].get("f_w"), lock=c.get("ckpt_lock_until"), ckpt_every=c["ckpt_every"],
                                         max_hours=c.get("max_hours"), f_end=c["f_end"]))(jl(sh)) if os.path.exists(sh) else None
    out["qpr3_select"] = {k: v for k, v in jl(FX + "/" + RT["qpr3"] + "/select.json").items() if k in ("choice", "PR3_aim_m", "PR3_command", "note_ja")}
    out["qsel_RP_cfg_written_without_confirm"] = os.path.exists(FX + "/" + RT["qsel"] + "/RP/cfg_queue.json")
    out["files_qsel"] = sorted(os.listdir(FX + "/" + RT["qsel"]))
    out["SELECT_RESULT_head"] = open(FX + "/" + RT["qpr3"] + "/SELECT_RESULT_ja.md", encoding="utf8").read()[:900] if os.path.exists(FX + "/" + RT["qpr3"] + "/SELECT_RESULT_ja.md") else None
    save("c3_F5", out)
    for s in steps:
        print(s["root"], s["step"], s["rc"], s["want"], " | ".join(s["tail"])[-400:])
    print(json.dumps({k: v for k, v in out.items() if k != "steps"}, ensure_ascii=False, default=float)[:3000])


# ------------------------------------------------------------------ c4（F6・D6）
def c4():
    out = {}
    base = ["B", "B35X", "U10=35", "sh=SH", "prog=PR1", "t_on=150.0", "t_td=151.3", "ckpt_frame=3456", "still_offset=0.1"]
    var = {"wind=N": ["wind=N"], "wind=S wind_mode=2": ["wind=S", "wind_mode=2"], "wind=S wind_mode=2.0": ["wind=S", "wind_mode=2.0"],
           "wind=S wind_mode=\"2\"": ["wind=S", 'wind_mode="2"'], "wind=n": ["wind=n"], "wind=S": ["wind=S"],
           "wind=S wind_mode=3": ["wind=S", "wind_mode=3"], "wind=S wind_on=0 wind_mode=2": ["wind=S", "wind_on=0", "wind_mode=2"]}
    for k, extra in var.items():
        rc, so, se = py(["g44_cfg.py"] + base + extra)
        c = json.loads(so) if (rc == 0 and so.strip().startswith("{")) else None
        out[k] = dict(rc=rc, msg=se.strip()[-160:], wind_on=(c or {}).get("parms", {}).get("wind_on"), wind_mode=(c or {}).get("parms", {}).get("wind_mode"),
                      max_hours=(c or {}).get("max_hours"))
    rc, so, se = py(["g44_cfg.py", "PR1", "PR1x", "wind_on=1", "wind_mode=2"])
    out["PR1 + wind_on=1 wind_mode=2"] = dict(rc=rc, msg=se.strip()[-160:])
    rc, so, se = py(["g44_cfg.py", "SMOKE", "SMx", "dp=0.5", 'wind={"wind_on":1,"wind_mode":2}'])
    out["SMOKE wind dict mode 2"] = dict(rc=rc, msg=se.strip()[-160:])
    # g44_run.py（hython）は cfg を読むだけで、mode 2 を拒まない（手で書いた cfg）：文字で探す
    src = open(TOOLS + "/g44_run.py", encoding="utf8").read()
    out["g44_run_checks_wind_mode"] = ("wind_mode" in src)
    save("c4_F6", out)
    print(json.dumps(out, ensure_ascii=False, default=float))


# ------------------------------------------------------------------ c5（F7・D3：N5）
def c5():
    out = {}
    rd = R42 + "/R3"
    cfg = jl(rd + "/cfg.json"); xp = cfg["parms"]["x_p"]
    D = A.load_hf(rd)
    off = jl(B44 + "/check/ana44_R3.json")["still_level_offset_m"]
    nz = D["eta"].shape[1]
    with np.errstate(all="ignore"):
        import warnings
        warnings.simplefilter("ignore")
        EX = np.nanmean(D["eta"][:, 1:nz - 1, :].astype(np.float64), axis=1) - off
    x = D["x"]; t = D["t"]
    new = jl(B44 + "/fixes/f1/ana44_R3_after_fix.json")["N5"]
    xa, xb = 161.0, 268.8
    ia = int(np.argmin(np.abs(x - (xp + xa)))); ib = int(np.argmin(np.abs(x - (xp + xb))))
    out["grid_x_nearest"] = [float(x[ia] - xp), float(x[ib] - xp)]

    def g(xr):
        return np.array([np.interp(xp + xr, x, np.nan_to_num(r)) for r in EX])
    sa = g(xa); sb = g(xb)
    # 頂を x–t でたどる：xa の頂の時刻のコマで xa の近くの山から始め、1 コマずつ、前の位置 + c_lin/24 の ±1.5 m の中のいちばん高い所へ
    rows = []
    for r in new["offshore"]:
        ta = r["t_a"]; T = r["T"]; c_lin = r["c_lin"]
        f = int(round(ta * FPS))         # t = (frame-1)/24 → 添字は frame-1
        fidx = {int(fr): i for i, fr in enumerate(D["frames"])}
        fr = f + 1
        i = fidx[fr]
        m = np.abs(x - (xp + xa)) <= 3.0
        jj = np.where(m)[0][int(np.nanargmax(EX[i][m]))]
        xc = float(x[jj]); path = [(fr, xc)]
        while xc < xp + xb + 5 and fr + 1 in fidx:
            fr += 1; i = fidx[fr]
            xpred = xc + c_lin / FPS
            mm = np.abs(x - xpred) <= 1.5
            if not mm.any():
                break
            jj = np.where(mm)[0][int(np.nanargmax(EX[i][mm]))]
            xc = float(x[jj]); path.append((fr, xc))
        ps = np.array(path, float)
        # 頂の道が xb を越えた時刻（一次の補間）と、その間の平均の速さ
        k = np.where(ps[:, 1] >= xp + xb)[0]
        t_cross = None; c_track = None
        if len(k):
            k0 = k[0]
            f_c = ps[k0 - 1, 0] + (xp + xb - ps[k0 - 1, 1]) / max(ps[k0, 1] - ps[k0 - 1, 1], 1e-9)
            t_cross = (f_c - 1) / FPS
            k1 = np.where(ps[:, 1] >= xp + xa)[0][0]
            f_a = ps[max(k1 - 1, 0), 0] + ((xp + xa - ps[max(k1 - 1, 0), 1]) / max(ps[k1, 1] - ps[max(k1 - 1, 0), 1], 1e-9) if k1 > 0 else 0.0)
            c_track = (xb - xa) / (t_cross - (f_a - 1) / FPS)
        rows.append(dict(t_a=ta, T=T, tool_t_b=r["t_b"], track_t_b=t_cross, track_minus_tool_s=(t_cross - r["t_b"]) if t_cross else None,
                         tool_err=r["err"], track_err=(c_track / c_lin - 1) if c_track else None, amp_a=r["amp_a"], amp_b=r["amp_b"]))
    out["offshore_pairs"] = rows
    out["tool_err_range"] = new.get("err_range_offshore")
    out["reef"] = new.get("reef"); out["ratio"] = new.get("ratio_reef_over_offshore")
    # 自分の頂の数え方（0 の上向きの交わりの間の最大、高さ 2 格子以上）で、xa の時系列の群の前の頂を全部並べ、道具が落とした物がないか
    vox = 2 * cfg["parms"]["dp"]
    ja = int(np.nanargmax(sa))
    up = np.where((sa[:-1] <= 0) & (sa[1:] > 0))[0]
    mine = []
    for a, b in zip(up[:-1], up[1:]):
        j = a + 1 + int(np.argmax(sa[a + 1:b + 1]))
        if sa[j] >= 2 * vox and t[j] <= t[ja]:
            mine.append(dict(t=float(t[j]), amp=float(sa[j]), T=float((b - a) / FPS)))
    out["my_crests_at_161_before_max"] = mine
    out["t_max_161"] = float(t[ja])
    save("c5_F7", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:4000])


# ------------------------------------------------------------------ c6（F4・F2：時間と置き場所）
def series42(rid):
    fs = sorted(glob.glob(os.path.join(R42, rid, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    F, W = [], []
    for p in fs:
        d = np.load(p); fr = list(map(int, d["frames"]))
        if F:
            k = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in k]; W = [W[i] for i in k]
        F += fr; W += list(map(float, d["wall"]))
    return dict(zip(F, W)), float(np.median(W[-200:])), max(F)


def replay(cost, f_first, f_end, sp0, sp_list, lock=0, ckload=3.5, boot=6.0, stopchk=0.0, online=None, rule=None, max_h=None, WL=1740.0, nper=1.0):
    """g44_chain.py の決まりを読み直して書いた真似（g44_hours.simulate は使わない）。途中保存のファイルの数も数える。"""
    sp_list = sorted(set(sp_list), reverse=True)
    el = 0.0; f0 = f_first; prev_f0 = None; prev_w = None; force = None; launches = []; ck_files = set(); stalled = None; cut = False
    while f0 <= f_end:
        if max_h is not None and el / 3600 > max_h:
            cut = True; break
        if f0 <= lock:
            sp = sp0
        else:
            sp = sp0 if sp0 in sp_list else sp_list[0]
            if prev_w is not None and len(prev_w) >= 3:
                s_est = float(np.percentile(prev_w[1:][-48:], 75)); load0 = prev_w[0]
                ok = [v for v in sp_list if load0 + 1.5 * nper * v * s_est <= 0.92 * WL]
                sp = ok[0] if ok else sp_list[-1]
            if force is not None:
                sp = min(sp, sp_list[min(force, len(sp_list) - 1)])
        wl = WL if max_h is None else min(WL, max(60.0, max_h * 3600 - el))
        ws = []; acc = 0.0; f = f0; why = "end"
        while f <= f_end:
            w = cost(f) + (ckload if (f == f0 and f0 > 1) else 0.0)
            acc += w; ws.append(w)
            if f % sp == 0:
                ck_files.add(f)
            if online is not None and f >= online:
                why = "online"; f += 1; break
            f += 1
            if acc > wl:
                why = "wall"; break
        done = f - 1
        launches.append((f0, done, sp))
        el += boot + acc + stopchk
        if why != "wall" or done >= f_end:
            break
        if rule is not None and rule(done):
            break
        cks = [k for k in ck_files if f0 <= k <= done]
        prev_w = ws
        if not cks:
            idx = sp_list.index(sp) if sp in sp_list else 0
            if idx + 1 >= len(sp_list) or f0 <= lock:
                stalled = f0; break
            force = idx + 1; continue
        force = None; f0 = max(cks) + 1
    return dict(hours=el / 3600, launches=launches, n_launch=len(launches), ck_files=len(ck_files), stalled=stalled, cut=cut, last=done)


def c6():
    out = {}
    P = A.plan(); Tc = P["tank"]["Tc"]
    # (a) FLIP42 の起動の和と記録だけの和（計画の 1 コマの秒の元）
    rec = {}
    for rid in ("R2", "R3", "R4d"):
        w, tail, fl = series42(rid)
        ls = sum(float(jl(p).get("wall_total_s") or 0) for p in glob.glob(os.path.join(R42, rid, "run_c*.json")))
        starts = sorted((int(jl(p)["f_start"]), int(jl(p).get("f_end_done") or 0)) for p in glob.glob(os.path.join(R42, rid, "run_c*.json")))
        rec[rid] = dict(frame_sum_h=sum(w.values()) / 3600, launch_sum_h=ls / 3600, ratio=ls / sum(w.values()), launches=len(starts), bounds=starts)
    out["flip42"] = {k: {kk: vv for kk, vv in v.items() if kk != "bounds"} for k, v in rec.items()}
    # (b) 自分の真似で R2・R4d の起動の区切りを再現（同じ間隔の表、固定なし）
    for rid, lst, ckl in (("R2", (240, 120, 60, 30, 15, 7), 2.0), ("R4d", (240, 120, 80, 60, 40, 30, 20, 14, 10, 7), 3.5)):
        w, tail, fl = series42(rid)
        cfg = jl(os.path.join(R42, rid, "cfg.json"))
        sim = replay(lambda f: w.get(f, tail), 1, int(cfg["f_end"]), int(cfg["ckpt_every"]), lst, ckload=ckl, boot=0.0, nper=float(cfg.get("ckpt_per_launch", 1)))
        sim0 = replay(lambda f: w.get(f, tail), 1, int(cfg["f_end"]), int(cfg["ckpt_every"]), lst, ckload=0.0, boot=0.0, nper=float(cfg.get("ckpt_per_launch", 1)))
        rb = rec[rid]["bounds"]
        sb = [(a, b) for a, b, _ in sim["launches"]]
        out["replay_" + rid] = dict(sim_h=sim["hours"], rec_h=rec[rid]["launch_sum_h"], n_sim=sim["n_launch"], n_rec=len(rb),
                                    same_starts=[a for a, _ in sb] == [a for a, _ in rb], starts_sim=[a for a, _ in sb][:40], starts_rec=[a for a, _ in rb][:40],
                                    ck_files_sim=sim["ck_files"], ck_files_rec=len(glob.glob(os.path.join(R42, rid, "ckpt", "v.*.sim"))),
                                    sim_noload_h=sim0["hours"], same_starts_noload=[a for a, _, _ in sim0["launches"]] == [a for a, _ in rb],
                                    starts_sim_noload=[a for a, _, _ in sim0["launches"]][:40])
    # (c) 風の計算の打ち切り（g44_cfg の B が使う b_max_hours）と、その道の時間を、機械の重さを変えて
    import g44_hours as H
    w3, tail3, fl3 = series42("R3")
    on3, td3 = 3714, 3745
    rows = []
    for onset in np.arange(140.0, 166.0, 1.0):
        f_on = int(round(onset * FPS)) + 1
        f_w = int(math.floor(FPS * (onset - 6.0)))
        while not [d for d in range(120, 301) if f_w % d == 0]:
            f_w -= 1
        t_td = onset + (td3 - on3) / FPS
        f_cap = int(math.floor((t_td + 2 * Tc) * FPS + 1e-9)) + 1
        mh, basis = H.b_max_hours(f_w, onset, t_td, Tc)
        r = dict(onset=float(onset), f_w=f_w, f_cap=f_cap, frames=f_cap - f_w, max_hours=mh)
        for load in (1.0, 1.33, 1.5, 2.0, 3.0):
            sh = on3 - f_on
            cost = lambda f, sh=sh, load=load: w3.get(max(f + sh, 2), tail3) * 1.02 * load
            s = replay(cost, f_w + 1, f_cap, 24, (48, 24, 12), ckload=3.5, boot=6.0, max_h=mh)
            r["load%.2f" % load] = dict(h=s["hours"], cut=s["cut"], last=s["last"], ck=s["ck_files"])
            if load == 1.0:
                f_stop = f_on + (3745 - on3) + 12
                s2 = replay(cost, f_w + 1, f_cap, 24, (48, 24, 12), ckload=3.5, boot=6.0, online=f_stop, max_h=mh)
                r["online_h"] = s2["hours"]; r["online_ck"] = s2["ck_files"]
        rows.append(r)
    out["B_rows"] = rows
    out["B_summary"] = {("load%.2f" % L): dict(h=[min(r["load%.2f" % L]["h"] for r in rows), max(r["load%.2f" % L]["h"] for r in rows)],
                                               cut=[r["onset"] for r in rows if r["load%.2f" % L]["cut"]],
                                               ck=[min(r["load%.2f" % L]["ck"] for r in rows), max(r["load%.2f" % L]["ck"] for r in rows)])
                        for L in (1.0, 1.33, 1.5, 2.0, 3.0)}
    out["B_max_hours_range"] = [min(r["max_hours"] for r in rows), max(r["max_hours"] for r in rows)]
    # (d) 途中保存の置き場所の見込み（報告に入れる計算。1 個の大きさは FLIP42 の平均と煙の試し）
    sz = {}
    for rid in ("R2", "R3"):
        fs = glob.glob(os.path.join(R42, rid, "ckpt", "v.*.sim"))
        sz[rid] = sum(os.path.getsize(p) for p in fs) / len(fs) / 2**30
    out["ckpt_GiB_each_flip42"] = sz
    reef25 = sz["R3"] * 0.875          # 礁の分（煙の試しの粒子の数の比、record §5）
    reef34 = sz["R2"] * 0.905
    # 形の本番（巻き始め 140・155・165 s、下見 1 の狙い）と下見・繰り返しの途中保存の数（g44_hours の関数の 1 コマの秒で、自分の真似で数える）
    disk = {}
    for onset in (140.0, 155.0, 165.0):
        f_on = int(round(onset * FPS)) + 1
        c = H.cost_fn("R3", f_on, 1.0, 1.0)
        f_w, sp = H.f_w_rule(onset)
        t_td = onset + (td3 - on3) / FPS
        aim = P["programs"]["PR1_R3_flat592"]["aim_t_s"]
        rule = lambda done, t_td=t_td: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= aim + Tc
        s = replay(c, 1, 4560, sp, (240, 120, 60, 30, 15, 10), lock=f_w, ckload=3.5, stopchk=11.0, rule=rule)
        c2 = H.cost_fn("R2", f_on, 1.0, 1.0)
        rule2 = lambda done, t_td=t_td: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= aim + Tc
        s2 = replay(c2, 1, 4560, 240, (240, 120, 60, 30, 15), ckload=2.0, stopchk=11.0, rule=rule2)
        disk["onset%.0f" % onset] = dict(SH_ck=s["ck_files"], SH_GiB=s["ck_files"] * reef25, PR_ck=s2["ck_files"], PR_GiB=s2["ck_files"] * reef34)
    cr, fe, ons = H.rp_cost("flat", 1.0, 1.0, P)
    s = replay(cr, 1, fe, 240, (240, 120, 60, 30, 15), ckload=2.0, stopchk=40.0)
    disk["RP_ck"] = s["ck_files"]; disk["RP_GiB"] = s["ck_files"] * reef34
    Bn = [r["online_ck"] for r in rows]; Bc = [r["load1.00"]["ck"] for r in rows]
    disk["B_online_ck"] = [min(Bn), max(Bn)]; disk["B_cap_ck"] = [min(Bc), max(Bc)]
    disk["B_online_GiB_each"] = [min(Bn) * reef25, max(Bn) * reef25]; disk["B_cap_GiB_each"] = [min(Bc) * reef25, max(Bc) * reef25]
    tot_on = 2 * disk["onset155"]["PR_GiB"] + disk["onset155"]["SH_GiB"] + disk["RP_GiB"] + 2 * max(Bn) * reef25
    tot_cap = 2 * disk["onset155"]["PR_GiB"] + disk["onset155"]["SH_GiB"] + disk["RP_GiB"] + 2 * max(Bc) * reef25
    disk["total_GiB_wind_online"] = tot_on; disk["total_GiB_wind_cap"] = tot_cap
    disk["plan_GB_hi"] = 69.0
    disk["G_free_GiB_now"] = shutil.disk_usage("G:/").free / 2**30
    out["disk"] = disk
    # (e) 合計と日付の計算し直し（hours44.json の数から）
    h = jl(B44 + "/fixes/hours44.json")["estimates"]
    tot = {}
    for L in ("1.00", "1.33"):
        lo = h["load%s_lo" % L]; hi = h["load%s_hi" % L]
        a = lo["PR1"]["hours_min"] + lo["PR2"]["hours_min"] + lo["SH_PR2"]["hours_min"] + 2 * lo["B_normal"]["hours_min"] + lo["RP_reef"]["hours_min"]
        b = hi["PR1"]["hours_max"] + hi["PR2"]["hours_max"] + hi["SH_PR1"]["hours_max"] + 2 * hi["B_normal"]["hours_max"] + hi["RP_flat"]["hours_max"]
        bc = b - 2 * hi["B_normal"]["hours_max"] + 2 * hi["B_cap"]["hours_max"]
        sel_lo = lo["PR1"]["hours_min"] + lo["PR2"]["hours_min"]; sel_hi = hi["PR1"]["hours_max"] + hi["PR2"]["hours_max"]
        tot[L] = dict(lo=a, hi=b, hi_cap=bc, select_arrives_after_h=[sel_lo, sel_hi])
    out["totals_recomputed"] = tot
    save("c6_F4", out)
    print(json.dumps({k: v for k, v in out.items() if k != "B_rows"}, ensure_ascii=False, default=float)[:6000])


# ------------------------------------------------------------------ c7（残りの小さな確かめ）
def c7():
    out = {}
    import g44_hours as H
    P = A.plan(); Tc = P["tank"]["Tc"]
    # (a) 形の本番が f_w までの固定の中で止まる数（自分の真似。機械の重さ 1.0〜2.0、粒子の数で縮めた・縮めない）
    scale25 = H.particle_scale()[0.25]["scale"]
    aims = {"PR1": P["programs"]["PR1_R3_flat592"]["aim_t_s"], "PR2": P["programs"]["PR2_reef_aim500"]["aim_t_s"]}
    st = {}
    for load in (1.0, 1.33, 1.5, 2.0):
        for end, sc in (("lo", scale25), ("hi", 1.0)):
            for pr in ("PR1", "PR2"):
                n = 0; hrs = []
                for onset in np.arange(140.0, 166.0, 1.0):
                    f_on = int(round(onset * FPS)) + 1
                    c = H.cost_fn("R3", f_on, sc, load)
                    f_w, sp = H.f_w_rule(onset)
                    t_td = onset + (3745 - 3714) / FPS
                    rule = lambda done, t_td=t_td, aim=aims[pr]: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= aim + Tc
                    r = replay(c, 1, 4560, sp, (240, 120, 60, 30, 15, 10), lock=f_w, ckload=3.5, stopchk=11.0, rule=rule, max_h=26.58)
                    n += 1 if r["stalled"] else 0
                    hrs.append(r["hours"])
                st["load%.2f_%s_%s" % (load, end, pr)] = dict(stalled=n, h=[min(hrs), max(hrs)])
    out["SH_lock_stall"] = st
    # (b) 確かめのない B35S・RP の段、選びのない RP の段（dry-run）
    TAG = time.strftime("%H%M%S")
    q = FX + "/qbyp_" + TAG
    os.makedirs(q)
    json.dump(dict(select=dict(choice="PR2", confirmed=False)), open(q + "/queue_state.json", "w", encoding="utf8"))
    res = {}
    for name, args in (("from_B35S_no_SH_state", ["--from", "B35S"]), ("only_RP_unconfirmed", ["--only", "RP"])):
        rc, so, se = py(["g44_queue.py", "--agreed", "c44 の試し（本番ではない）", "--root", FXR + "/qbyp_" + TAG, "--dry-run"] + args)
        res[name] = dict(rc=rc, tail=(so + se).strip().splitlines()[-3:])
    json.dump({}, open(q + "/queue_state.json", "w", encoding="utf8"))
    rc, so, se = py(["g44_queue.py", "--agreed", "c44 の試し（本番ではない）", "--root", FXR + "/qbyp_" + TAG, "--dry-run", "--only", "RP"])
    res["only_RP_no_select"] = dict(rc=rc, tail=(so + se).strip().splitlines()[-2:])
    out["bypass"] = res
    # (c) g44_video の静かな水面（ana.json がある時とない時）
    import g44_video as V
    d1 = V.Data("Bx_cap", FXR)
    os.makedirs(FX + "/Bx_noana", exist_ok=True)
    for p in glob.glob(FX + "/Bx_cap/*.npz") + [FX + "/Bx_cap/cfg.json"]:
        shutil.copy2(p, FX + "/Bx_noana")
    c = jl(FX + "/Bx_noana/cfg.json"); c["run_id"] = "Bx_noana"; json.dump(c, open(FX + "/Bx_noana/cfg.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    try:
        d2 = V.Data("Bx_noana", FXR); off2 = d2.off
    except Exception as e:
        off2 = repr(e)[:200]
    out["video_off"] = dict(with_ana=d1.off, without_ana=off2)
    # (d) 夜の間に PC が眠らないようにする呼び出しが道具にあるか（文字で探す）
    srcs = "".join(open(p, encoding="utf8").read() for p in glob.glob(TOOLS + "/g44_*.py"))
    out["keep_awake_call_in_tools"] = ("SetThreadExecutionState" in srcs)
    save("c7_misc", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:5000])


# ------------------------------------------------------------------ c8（1 コマ目からの計算の読みが直しの前と同じか）・c9（空・全部 NaN の守り）
def c8():
    out = {}
    for rid, root, ref in (("R3", "flip42", B44 + "/check/ana44_R3.json"), ("S8", "smoke", B44 + "/smoke/S8/ana.json")):
        a = A.analyze(rid, root, out_path=FX + "/ana_%s_now.json" % rid)
        r = jl(ref)
        keys = sorted(set(a) | set(r))
        diff = [k for k in keys if json.dumps(a.get(k), sort_keys=True, default=float) != json.dumps(r.get(k), sort_keys=True, default=float)]
        out[rid] = dict(differs=diff, only_new=[k for k in a if k not in r], only_old=[k for k in r if k not in a])
    save("c8_regression", out)
    print(json.dumps(out, ensure_ascii=False))


def c9():
    rd = R42 + "/R3"
    D = A.load_hf(rd); xp = jl(rd + "/cfg.json")["parms"]["x_p"]
    EX = A.zmean(D) - 0.1168; t = D["t"]; x = D["x"]
    out = dict(two_point_short=A.two_point(EX[:120], x, t[:120], xp, 220.0, 250.0, [0.0, float(t[119])], [0.05, 0.2]),
               two_point_noband=A.two_point(EX, x, t, xp, 220.0, 250.0, [0.0, float(t.max())], [0.0001, 0.0002]),
               lowfreq_short=A.lowfreq(EX[:600], x, t[:600], xp, 33.9))
    E2 = EX.copy(); E2[:] = np.nan
    try:
        out["crest_speeds_allnan"] = A.crest_speeds(E2, x, t, xp, 161.0, 268.8, 42.0, 1.0)
    except Exception as e:
        out["crest_speeds_allnan"] = "error " + repr(e)[:200]
    out["argmax_or_none_allnan"] = A.argmax_or_none(np.full(10, np.nan))
    save("c9_guards", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:1500])


if __name__ == "__main__":
    print("priority", lower_self())
    {"c0": c0, "c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6, "c7": c7, "c8": c8, "c9": c9}[sys.argv[1]]()
