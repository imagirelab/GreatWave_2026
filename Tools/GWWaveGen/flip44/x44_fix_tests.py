# -*- coding: utf-8 -*-
"""FLIP44：確かめ（check/check_ja.md）の後の 6 つの直しの試し（py -3.10）。流体の計算はしない（F2 の hython の煙の試しは x44_fix_f2.json を
g44_chain.py に渡して別に走らせる）。自分の優先度を「通常より下」にし、電力の抑えを外す（g44_run.py と同じ設定）。
試しの物は全部 Unity/Build/FLIP44/fixes/ に写して使い、smoke/・runs/・check/・FLIP42 のファイルは読むだけ。
  setup  ：smoke の S9_v2・S8（途中保存なし）を fixes/f1/ に写す。FLIP42 R3 の 3570〜3800 コマを切り出して、途中保存から始めた計算の形の記録
           （fixes/f1/R3ck・R3ck_nan・R3ck_nosrc・R3ck_cfgonly・R3cut_noflag）を作る
  t1     ：F1。S9_v2 と切り出した記録で analyze()、S9_v2 と S8 で g44_wind_check、FLIP42 R3 と S8 の全部の解析が前と同じか
  t3     ：F7（N5）。R3 の沖と礁の上の組み方の前と後
  t5     ：F5。fixes/q5 に偽の下見の ana.json を置き、g44_queue.py の選びの後の止まりと続ける言葉（--dry-run）
  t6     ：F6。g44_cfg.py が wind=N と wind_mode=2 を拒むか。runs/ready の 4 つを作り直して同じか
  f2post ：F2。煙の試し F2cut（g44_chain.py、打ち切り 0.02 時間）の後に、g44_queue の風の段の後の扱い（報告して先へ進む）を通す
出力：Unity/Build/FLIP44/fixes/fix_tests.json（試しごとに足す）
"""
import sys, os, json, glob, shutil, subprocess, time, ctypes
from ctypes import wintypes
import numpy as np

TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44"
B44 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
R42 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
FIX = B44 + "/fixes"
RES = FIX + "/fix_tests.json"
sys.path.insert(0, TOOLS)
import g44_analyze as A


def unthrottle_self():
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


def py(args, cwd=TOOLS):
    """子の py も「通常より下」で（Windows の BELOW_NORMAL_PRIORITY_CLASS）。"""
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True, encoding="utf8", errors="replace",
                       creationflags=0x00004000)
    return r.returncode, r.stdout, r.stderr


# ------------------------------------------------------------------ setup
def cut_r3(dst_id, f0=3570, f1=3800, from_ckpt=True, cfg_extra=None, nan_x_rel=None, src_run="R3"):
    rd = os.path.join(FIX, "f1", dst_id)
    os.makedirs(rd, exist_ok=True)
    srd = os.path.join(R42, "R3")
    D = A.load_hf(srd)
    k = (D["frames"] >= f0) & (D["frames"] <= f1)
    eta = D["eta"][k].copy()
    cfg = json.load(open(os.path.join(srd, "cfg.json"), encoding="utf8"))
    if nan_x_rel is not None:
        xs = D["x"]; xp = cfg["parms"]["x_p"]
        m = np.abs(xs - (xp + nan_x_rel)) <= 3.0
        eta[:, :, m] = np.nan
    np.savez_compressed(os.path.join(rd, "hf_c%04d.npz" % f0), eta=eta, x=D["x"], z=D["z"], frames=D["frames"][k], t=D["t"][k],
                        wall=D["wall"][k], npts=D["npts"][k], ss_n=D["ss_n"][k], wind_calls=D["wind_calls"][k])
    SR = A.SecReader(srd)
    fr = [f for f in SR.frames if f0 <= f <= f1]
    sdf = np.stack([np.clip(SR.get(f), -8, 8).astype(np.float16) for f in fr])
    np.savez_compressed(os.path.join(rd, "sec_c%04d_b%04d.npz" % (f0, f0)), sdf=sdf, frames=np.array(fr), meta=json.dumps(SR.meta))
    c = dict(cfg)
    c["run_id"] = dst_id
    if from_ckpt:
        c["from_ckpt"] = dict(run=src_run, frame=f0 - 1, root="flip42")
    c.update(cfg_extra or {})
    json.dump(c, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return dict(run=dst_id, frames=[int(D["frames"][k].min()), int(D["frames"][k].max())], sec_frames=[fr[0], fr[-1]], n_sec=len(fr))


def setup():
    out = {}
    os.makedirs(FIX + "/f1", exist_ok=True)
    for rid, skip in (("S9_v2", ("ckpt",)), ("S8", ("ckpt", "video"))):
        src = os.path.join(B44, "smoke", rid); dst = os.path.join(FIX, "f1", rid)
        os.makedirs(dst, exist_ok=True)
        for p in glob.glob(os.path.join(src, "*")):
            if os.path.basename(p) in skip or os.path.isdir(p):
                continue
            shutil.copy2(p, dst)
        out[rid] = sorted(os.listdir(dst))
    out["R3ck"] = cut_r3("R3ck")
    out["R3ck_nan"] = cut_r3("R3ck_nan", nan_x_rel=700.0)
    out["R3ck_nosrc"] = cut_r3("R3ck_nosrc", src_run="R3_missing")
    out["R3ck_cfgonly"] = cut_r3("R3ck_cfgonly", src_run="R3_missing",
                                 cfg_extra=dict(stop_touchdown=dict(after_s=0.5, still_offset_m=0.116838239133358, still_offset_from="test: R3 ana.json")))
    out["R3cut_noflag"] = cut_r3("R3cut_noflag", from_ckpt=False)
    save("setup", out)
    print(json.dumps(out, ensure_ascii=False)[:2000])


# ------------------------------------------------------------------ t1（F1）
def t1():
    out = {}
    ref = json.load(open(os.path.join(B44, "check", "ana44_R3.json"), encoding="utf8"))
    # (a) S9_v2：S8 の 24 s の途中保存から始めた風の煙の試し
    rc, so, se = py(["g44_analyze.py", "S9_v2", "fixes/f1"])
    a = json.load(open(os.path.join(FIX, "f1", "S9_v2", "ana.json"), encoding="utf8")) if rc == 0 else {}
    s8 = A.still_level(A.load_hf(os.path.join(B44, "smoke", "S8")), json.load(open(os.path.join(B44, "smoke", "S8", "cfg.json"), encoding="utf8"))["parms"]["x_p"])
    out["S9_v2_analyze"] = dict(rc=rc, stderr=se[-500:], still=a.get("still_level_offset_m"), still_S8_direct=s8,
                                source=a.get("still_level_source"), skipped=a.get("N3_N7_skipped_ja"), notes=a.get("notes_ja"),
                                gauges_n=len(a.get("gauges", {})), gauges_note=a.get("gauges_note_ja"), onset=a.get("onset"), touchdown=a.get("touchdown"),
                                n_events=len(a.get("events", [])), ok=bool(rc == 0 and abs(a.get("still_level_offset_m", 9) - s8) < 1e-9))
    rc, so, se = py(["g44_wind_check.py", "S9_v2", "S8", "fixes/f1"])
    w = json.load(open(os.path.join(FIX, "f1", "S9_v2", "wind_check.json"), encoding="utf8")) if rc == 0 else {}
    out["S9_v2_wind_check"] = dict(rc=rc, stdout=so[-800:], stderr=se[-500:], still=w.get("still_offset_m"), W6_frames=(w.get("W6") or {}).get("frames"),
                                   W6_pass=(w.get("W6") or {}).get("pass_"), W8=(w.get("W8") or {}).get("skipped_ja") or (w.get("W8") or {}).get("at_nowind_onset"),
                                   W8_gauges=(w.get("W8") or {}).get("gauges"), W1_5=w.get("W1_5"), ok=bool(rc == 0))
    # (b) FLIP42 R3 を 3570 コマ（巻き始めの 6 s 前）から切った記録：巻き始め・着水・静かな水面が全部の記録の読みと同じか
    rc, so, se = py(["g44_analyze.py", "R3ck", "fixes/f1"])
    b = json.load(open(os.path.join(FIX, "f1", "R3ck", "ana.json"), encoding="utf8")) if rc == 0 else {}
    same = {}
    for k in ("frame", "t", "xc_rel", "eta_c", "H"):
        same["onset_" + k] = [b.get("onset", {}).get(k), ref["onset"][k]]
    for k in ("frame", "t", "by"):
        same["touchdown_" + k] = [b.get("touchdown", {}).get(k), ref["touchdown"][k]]
    same["still"] = [b.get("still_level_offset_m"), ref["still_level_offset_m"]]
    same["selection_a_pass"] = [(b.get("selection_a") or {}).get("pass_"), (ref.get("selection_a") or {}).get("pass_")]
    out["R3ck"] = dict(rc=rc, stderr=se[-500:], compare=same, ok=bool(rc == 0 and all(v[0] == v[1] for v in same.values())),
                       source=b.get("still_level_source"), skipped=b.get("N3_N7_skipped_ja"), notes=b.get("notes_ja"))
    # (c) 読む点 700 m を NaN にした記録
    rc, so, se = py(["g44_analyze.py", "R3ck_nan", "fixes/f1"])
    c = json.load(open(os.path.join(FIX, "f1", "R3ck_nan", "ana.json"), encoding="utf8")) if rc == 0 else {}
    out["R3ck_nan"] = dict(rc=rc, stderr=se[-500:], gauge700=(c.get("gauges") or {}).get("700"), notes=c.get("notes_ja"),
                           onset_frame=(c.get("onset") or {}).get("frame"), ok=bool(rc == 0 and (c.get("gauges") or {}).get("700", {}).get("max") is None))
    # (d) 元の計算がない・cfg の値もない → 理由を書いて止まる（コード 3）
    rc, so, se = py(["g44_analyze.py", "R3ck_nosrc", "fixes/f1"])
    out["R3ck_nosrc"] = dict(rc=rc, stderr=se.strip()[-600:], ok=bool(rc == 3 and "静かな水面" in se))
    # (e) 元の計算がなく、cfg に出所つきの値がある → cfg の値を使う
    rc, so, se = py(["g44_analyze.py", "R3ck_cfgonly", "fixes/f1"])
    e = json.load(open(os.path.join(FIX, "f1", "R3ck_cfgonly", "ana.json"), encoding="utf8")) if rc == 0 else {}
    out["R3ck_cfgonly"] = dict(rc=rc, stderr=se[-300:], how=(e.get("still_level_source") or {}).get("how"), still=e.get("still_level_offset_m"),
                               onset_frame=(e.get("onset") or {}).get("frame"), ok=bool(rc == 0 and (e.get("onset") or {}).get("frame") == ref["onset"]["frame"]))
    # (f) from_ckpt のない、途中から始まる記録 → still_level が理由を書いて止まる（以前は NaN のまま進み nanargmax で落ちた）
    rc, so, se = py(["g44_analyze.py", "R3cut_noflag", "fixes/f1"])
    out["R3cut_noflag"] = dict(rc=rc, stderr=se.strip()[-600:], ok=bool(rc == 3 and "0.5〜2.0 s" in se))
    # (g) 1 コマ目からの計算が前と同じか（FLIP42 R3、S8）
    rc, so, se = py(["g44_analyze.py", "R3", "flip42", "--out", os.path.join(FIX, "f1", "ana44_R3_after_fix.json")])
    g = json.load(open(os.path.join(FIX, "f1", "ana44_R3_after_fix.json"), encoding="utf8")) if rc == 0 else {}
    diff = {}
    for k in ("still_level_offset_m", "onset", "touchdown", "selection_a", "N2_level", "N3", "N4", "N6", "N6_band_exit", "N7", "gauges", "events"):
        if json.dumps(g.get(k), sort_keys=True, default=float) != json.dumps(ref.get(k), sort_keys=True, default=float):
            diff[k] = "違う"
    out["R3_full_regression"] = dict(rc=rc, stderr=se[-300:], differs=diff, ok=bool(rc == 0 and not diff))
    ref8 = json.load(open(os.path.join(B44, "smoke", "S8", "ana.json"), encoding="utf8"))
    rc, so, se = py(["g44_analyze.py", "S8", "smoke", "--out", os.path.join(FIX, "f1", "ana_S8_after_fix.json")])
    g8 = json.load(open(os.path.join(FIX, "f1", "ana_S8_after_fix.json"), encoding="utf8")) if rc == 0 else {}
    diff8 = {}
    for k in ("still_level_offset_m", "onset", "touchdown", "selection_a", "N2_level", "N3", "N4", "N6", "N6_band_exit", "N7", "gauges", "events"):
        if json.dumps(g8.get(k), sort_keys=True, default=float) != json.dumps(ref8.get(k), sort_keys=True, default=float):
            diff8[k] = "違う"
    out["S8_full_regression"] = dict(rc=rc, stderr=se[-300:], differs=diff8, ok=bool(rc == 0 and not diff8))
    save("t1_F1", out)
    for k, v in out.items():
        print(k, "ok" if v.get("ok") else "NG", json.dumps({kk: vv for kk, vv in v.items() if kk in ("rc", "still", "compare", "differs", "how", "stderr", "skipped", "gauge700", "W6_frames", "W6_pass", "W8")}, ensure_ascii=False, default=float)[:900])


# ------------------------------------------------------------------ t1b（F1：風の計算の後の段を通す）
def t1b():
    """R3ck に風の値を入れた写し R3ckw（記録は同じ）を「風あり」、R3ck を「風なし」にして、解析 → g44_wind_check → g44_ctable を通す。
    記録が同じなので、W8 と W1〜W5 の差は全部 0 のはず。W6 は圧力の記録がないので 0 コマ。"""
    src = os.path.join(FIX, "f1", "R3ck"); dst = os.path.join(FIX, "f1", "R3ckw")
    os.makedirs(dst, exist_ok=True)
    for q in glob.glob(os.path.join(src, "*.npz")):
        shutil.copy2(q, dst)
    c = json.load(open(os.path.join(src, "cfg.json"), encoding="utf8"))
    c["run_id"] = "R3ckw"
    c["parms"].update(wind_on=1.0, wind_mode=1.0, wind_q=1325.4, wind_t0=154.70833333333334 - 3.0, wind_tramp=1.0, wind_t1=1e9,
                      wind_x0=c["parms"]["x_p"], wind_x1=c["parms"]["x_p"] + 930.86, wind_tap=10.0, ytop=18.0, thin_mult=2.0)
    c["stop_touchdown"] = dict(after_s=0.5, t_from=153.7, still_offset_m=0.116838239133358, still_offset_from="test")
    c["case"] = dict(c.get("case", {}), form="S", U10=35.0)
    json.dump(c, open(os.path.join(dst, "cfg.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    out = {}
    rc, so, se = py(["g44_analyze.py", "R3ckw", "fixes/f1"]); out["analyze"] = dict(rc=rc, stderr=se[-300:])
    rc, so, se = py(["g44_wind_check.py", "R3ckw", "R3ck", "fixes/f1"])
    w = json.load(open(os.path.join(dst, "wind_check.json"), encoding="utf8")) if rc == 0 else {}
    m = (w.get("W1_5") or {}).get("measures") or []
    out["wind_check"] = dict(rc=rc, stderr=se[-600:], W6_frames=(w.get("W6") or {}).get("frames"), W8_rows=len((w.get("W8") or {}).get("rows", [])),
                             W8_max_abs_d_eta=max([abs(r["d_eta"]) for r in (w.get("W8") or {}).get("rows", [])] or [None]) if (w.get("W8") or {}).get("rows") else None,
                             W8_gauges_identical=[v.get("identical_series") for v in ((w.get("W8") or {}).get("gauges") or {}).values()],
                             W1_5_n=len(m), W1_5_max_abs_delta=max([abs(r["delta"]) for r in m if "delta" in r] or [None]) if m else None,
                             W1_5_error=(w.get("W1_5") or {}).get("error"), onset=(w.get("W1_5") or {}).get("onset"))
    rc, so, se = py(["g44_ctable.py", "R3ck", "--wind", "B35S=R3ckw", "--root", "fixes/f1", "--out", os.path.join(FIX, "f1", "ctable")])
    out["ctable"] = dict(rc=rc, stderr=se[-600:], md=os.path.exists(os.path.join(FIX, "f1", "ctable", "remaining_gap_ja.md")), head=so[:600])
    out["ok"] = bool(out["analyze"]["rc"] == 0 and out["wind_check"]["rc"] == 0 and out["ctable"]["rc"] == 0 and out["wind_check"]["W1_5_n"] > 0
                     and out["wind_check"]["W1_5_max_abs_delta"] == 0)
    save("t1b_F1_pipeline", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:2500])


# ------------------------------------------------------------------ t3（F7・N5）
def t3():
    ref = json.load(open(os.path.join(B44, "check", "ana44_R3.json"), encoding="utf8"))
    new = json.load(open(os.path.join(FIX, "f1", "ana44_R3_after_fix.json"), encoding="utf8"))
    o_old = ref["N5"]["offshore"]; o_new = new["N5"]["offshore"]
    tb_old = [round(r["t_b"], 3) for r in o_old]
    out = dict(old=dict(n=len(o_old), distinct_far_crests=len(set(tb_old)), errs=[round(r["err"], 4) for r in o_old], T=[round(r["T"], 2) for r in o_old],
                        err_range=[min(r["err"] for r in o_old), max(r["err"] for r in o_old)]),
               new=dict(n=len(o_new), distinct_far_crests=len(set(round(r["t_b"], 3) for r in o_new)), errs=[round(r["err"], 4) for r in o_new],
                        T=[round(r["T"], 2) for r in o_new], amp_a=[round(r["amp_a"], 2) for r in o_new], t_a=[round(r["t_a"], 2) for r in o_new],
                        err_range=new["N5"].get("err_range_offshore")),
               reef_old=[round(r["err"], 4) for r in ref["N5"].get("reef", [])], reef_new=[round(r["err"], 4) for r in new["N5"].get("reef", [])],
               ratio_old=ref["N5"].get("ratio_reef_over_offshore"), ratio_new=new["N5"].get("ratio_reef_over_offshore"))
    out["ok"] = bool(out["new"]["n"] == out["new"]["distinct_far_crests"])
    save("t3_F7_N5", out)
    print(json.dumps(out, ensure_ascii=False, default=float))


# ------------------------------------------------------------------ t5（F5）
def t5():
    q = os.path.join(FIX, "q5")
    for k, src in (("PR1", os.path.join(B44, "check", "ana44_R3.json")), ("PR2", os.path.join(B44, "smoke", "S8", "ana.json"))):
        os.makedirs(os.path.join(q, k), exist_ok=True)
        shutil.copy2(src, os.path.join(q, k, "ana.json"))
    AG = "試し（x44_fix_tests t5。本番ではない）"
    steps = []
    for name, args in (("select", ["--only", "SELECT"]),
                       ("from_SH_without_confirm", ["--from", "SH"]),
                       ("confirm_wrong", ["--confirm-select", "PR2"]),
                       ("confirm_right", ["--confirm-select", "PR1"])):
        rc, so, se = py(["g44_queue.py", "--agreed", AG, "--root", "fixes/q5", "--dry-run"] + args)
        steps.append(dict(step=name, rc=rc, out=(so + se).strip()[-900:]))
    files = {n: os.path.exists(os.path.join(q, n)) for n in ("select.json", "SELECT_RESULT_ja.md", "QUEUE_PAUSE.txt", "SELECT_CONFIRMED.txt", "queue_state.json")}
    st = json.load(open(os.path.join(q, "queue_state.json"), encoding="utf8"))
    want = {"select": 3, "from_SH_without_confirm": 3, "confirm_wrong": 1, "confirm_right": 0}
    ok = all(s["rc"] == want[s["step"]] for s in steps) and all(files.values()) and st["select"].get("confirmed") is True
    sh_cfg = os.path.join(q, "SH", "cfg_queue.json")
    out = dict(steps=steps, files=files, state_select=st.get("select"), sh_cfg_written=os.path.exists(sh_cfg),
               hython_started=False, ok=bool(ok and os.path.exists(sh_cfg)))
    save("t5_F5", out)
    for s in steps:
        print(s["step"], s["rc"], s["out"][-300:].replace("\n", " | "))
    print("files", files, "ok", out["ok"])


# ------------------------------------------------------------------ t6（F6）と ready の作り直し
def t6():
    out = {}
    rc, so, se = py(["g44_cfg.py", "B", "B35N", "wind=N", "U10=35", "sh=SH", "prog=PR1", "t_on=155.0", "t_td=156.29", "ckpt_frame=3576", "still_offset=0.117"])
    out["wind_N"] = dict(rc=rc, msg=(so + se).strip()[-400:], ok=bool(rc != 0 and "N" in se and not so.strip().startswith("{")))
    rc, so, se = py(["g44_cfg.py", "B", "B35S", "wind=S", "U10=35", "sh=SH", "prog=PR1", "t_on=155.0", "t_td=156.29", "ckpt_frame=3576", "still_offset=0.117", "wind_mode=2"])
    out["wind_mode_2_override"] = dict(rc=rc, msg=(so + se).strip()[-400:], ok=bool(rc != 0))
    rc, so, se = py(["g44_cfg.py", "B", "B35S", "wind=S", "U10=35", "sh=SH", "prog=PR1", "t_on=155.0", "t_td=156.29", "ckpt_frame=3576", "still_offset=0.117"])
    c = json.loads(so) if rc == 0 else {}
    out["wind_S"] = dict(rc=rc, wind_mode=(c.get("parms") or {}).get("wind_mode"), max_hours=c.get("max_hours"), basis=(c.get("case") or {}).get("max_hours_basis"),
                         stop_touchdown=c.get("stop_touchdown"), f_start=c.get("f_start"), f_end=c.get("f_end"), ok=bool(rc == 0 and c["parms"]["wind_mode"] == 1.0))
    rc, so, se = py(["g44_cfg.py", "B", "B35S", "wind=S", "U10=35", "sh=SH_missing", "prog=PR1", "t_on=155.0", "t_td=156.29", "ckpt_frame=3576"])
    out["wind_S_no_still"] = dict(rc=rc, msg=(so + se).strip()[-300:], ok=bool(rc != 0))
    tmp = os.path.join(FIX, "ready_regen"); os.makedirs(tmp, exist_ok=True)
    same = {}
    for name, args in (("PR1", ["PR1", "PR1"]), ("PR2", ["PR2", "PR2"]), ("RP_reef500", ["RP", "RP", "aim=reef"]), ("RP_flat592", ["RP", "RP", "aim=flat"])):
        rc, so, se = py(["g44_cfg.py"] + args + ["--write", os.path.join(tmp, name + ".json")])
        a = open(os.path.join(tmp, name + ".json"), encoding="utf8").read(); b = open(os.path.join(B44, "runs", "ready", name + ".json"), encoding="utf8").read()
        same[name] = bool(a == b)
    out["ready_regenerated_same"] = same
    out["ok"] = all(v.get("ok") for k, v in out.items() if isinstance(v, dict) and "ok" in v) and all(same.values())
    save("t6_F6", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:3000])


# ------------------------------------------------------------------ F2 の煙の試しの後
def f2post():
    import g44_queue as Q
    Q.setup("fixes/q2")
    Q.AGREED = "試し（x44_fix_tests f2post。本番ではない）"
    cfg = json.load(open(os.path.join(FIX, "q2", "F2cut", "cfg.json"), encoding="utf8"))
    t0 = os.path.getmtime(os.path.join(FIX, "q2", "F2cut", "cfg.json")) - 5
    state_, done, why = Q.chain_result("F2cut", int(cfg["f_end"]), t0)
    S = {}
    Q.wind_after("F2cut", S, state_, done, why)
    rep = open(os.path.join(FIX, "q2", "QUEUE_REPORT.txt"), encoding="utf8").read() if os.path.exists(os.path.join(FIX, "q2", "QUEUE_REPORT.txt")) else ""
    a = json.load(open(os.path.join(FIX, "q2", "F2cut", "ana.json"), encoding="utf8")) if os.path.exists(os.path.join(FIX, "q2", "F2cut", "ana.json")) else {}
    recs = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(FIX, "q2", "F2cut", "run_c*.json")))]
    out = dict(chain_state=state_, done=done, why=why, state=S, report=rep[-1500:], ana_still=a.get("still_level_offset_m"), ana_source=a.get("still_level_source"),
               launches=[dict(f_start=r["f_start"], f_end_done=r["f_end_done"], stopped=r["stopped"], wall=r["wall_total_s"], priority=r.get("priority"),
                              wind_calls_equal_substeps=r.get("wind_calls_equal_substeps")) for r in recs],
               continued=True, ok=bool(state_ == "cut" and "F2cut" in rep))
    save("f2post_F2", out)
    print(json.dumps(out, ensure_ascii=False, default=float)[:3000])


if __name__ == "__main__":
    print("priority", unthrottle_self())
    {"setup": setup, "t1": t1, "t1b": t1b, "t3": t3, "t5": t5, "t6": t6, "f2post": f2post}[sys.argv[1]]()
