# -*- coding: utf-8 -*-
"""FLIP44：計算 1 本の設定（JSON）を作る。数は凍結した計画の plan/plan_numbers.json（と、下見 3 本目の plan/pr3_aim<x>.json）
から読む。ここで値を決め直さない。FLIP42 の g_cfg.py（変えていない）を写して直した。
py -3.10 g44_cfg.py <kind> <run_id> [k=v ...] [--write <path>]
  kind：PR1・PR2・PR3（aim=<x> が要る）・SH（prog=PR1|PR2|PR3、onset_pre=<下見の巻き始めの s>）・RP（aim=flat|reef|pr3:<x>）・
        B（wind=S、U10=<m/s>、sh=<形の本番の run_id>、t_on=<形の本番の巻き始めの s>、t_td=<形の本番の着水の s>、ckpt_frame=<コマ>、
           still_offset=<形の本番の静かな水面のずれ。省くと runs/<sh>/ana.json から読む>）・
           wind=N は、はがれのない流れの道具（g44_airflow.py）と場面の mode 2 ができるまで受け付けない（2026-10-12 確かめ F6）。
           打ち切り max_hours は FLIP42 R3 の 1 コマの秒から出す（g44_hours.b_max_hours。確かめ F2）。
        SMOKE（試し。下の make() の引数をそのまま k=v で）
  共通の k=v：dp、f_end、reef（1/0）、amp_gain、out_root（runs/smoke）、note、max_hours
水槽（計画 §2）：FLIP42 と同じ。帯 0〜x_p、自由に進む所 x_p〜xa0、吸う帯 xa0〜Lx。Lx は格子の倍数へ切り上げ。
2026-10-12（2 回目の確かめ check/check_fixes_ja.md の後。record_ja.md §3.2）：
  G6：風の値（wind_on・wind_mode）を、作った設定と k=v の上書きの後の両方で確かめる（check_wind）。PR1・PR2・PR3・SH・RP は風なし（wind_on 0）だけ、
      B は wind_on 1 と form の wind_mode（S は 1）だけを受け付ける。wind_on は 0 か 1、wind_mode は 1・2・3（3 は試しの形で SMOKE だけ）。
  G3：下見 3 本目の入口のフォルダーは PR3_DIR（既定は plan/。g44_queue.py の --dry-run だけが試しの置き場所に替える）。
"""
import sys, json, math, os
import numpy as np

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = ROOT + "/Tools/GWWaveGen/flip44"
AIRFLOW_TOOL = TOOLS + "/g44_airflow.py"     # はがれのない流れの形（N）の道具（S6）。まだない
PLAN = ROOT + "/Unity/Build/FLIP44/plan/plan_numbers.json"
PLAN_DIR = ROOT + "/Unity/Build/FLIP44/plan"
PR3_DIR = PLAN_DIR        # 下見 3 本目の入口 pr3_aim<x>.json の置き場所（g44_queue.py の --dry-run だけが替える。G3）
FPS = 24
G = 9.80665
GAUGES_REL = [33.9, 63.9, 161.0, 220.0, 250.0, 268.8, 300.0, 395.0, 420.0, 450.0, 470.0, 500.0, 530.0, 560.0, 600.0, 700.0]   # 計画 §2
PROG_KEY = {"PR1": "PR1_R3_flat592", "PR2": "PR2_reef_aim500", "RPflat": "RP_flat592", "RPreef": "RP_reef500"}
SEC_X_REL = [250.0, 850.0]


def rup(v, q):
    return float(math.ceil(v / q - 1e-9) * q)


def k_of(f, h):
    """p_plan_numbers.py の k_of と同じ式（分散の関係、ニュートン法）。"""
    om = 2 * np.pi * np.atleast_1d(np.asarray(f, float))
    k = np.maximum(om * om / G, om / math.sqrt(G * h))
    for _ in range(100):
        th = np.tanh(k * h)
        F = G * k * th - om * om
        dF = G * th + G * k * h * (1 - th * th)
        dk = F / dF
        k = k - dk
        if np.all(np.abs(dk) < 1e-14 * k):
            break
    return k


def plan():
    return json.load(open(PLAN, encoding="utf-8"))


def inlet_of(P, prog):
    """入口の表（成分の周波数・振幅・位相と、水深 h0 の波数）。prog は PR1・PR2・RPflat・RPreef か、PR3:<x>。"""
    if prog.startswith("PR3:"):
        x = float(prog.split(":")[1])
        p = json.load(open(os.path.join(PR3_DIR, "pr3_aim%.0f.json" % x), encoding="utf-8"))
        name = p["name"]
    elif prog.startswith("RP3:"):      # 下見 3 本目を選んだ時の繰り返しの入口（同じ狙い。p_plan_numbers.py --aim3 が repeat_same_aim に書く）
        x = float(prog.split(":")[1])
        p = json.load(open(os.path.join(PR3_DIR, "pr3_aim%.0f.json" % x), encoding="utf-8"))["repeat_same_aim"]
        name = p["name"]
    else:
        p = P["programs"][PROG_KEY[prog]]; name = p["name"]
    fr = np.array(p["freqs_Hz"], float)
    k = k_of(fr, P["tank"]["h0"])
    rep = p.get("repeat", {}).get("P_s", 0.0) if p.get("repeat") else 0.0
    return dict(name=name, freqs_Hz=list(map(float, fr)), amps_m=list(map(float, p["amps_m"])), phases_rad=list(map(float, p["phases_rad"])),
                k=list(map(float, k)), rep_P=float(rep), aim_x_from_paddle=p["aim_x_from_paddle"], aim_t_s=p["aim_t_s"],
                sum_a=float(np.sum(p["amps_m"])))


def make(run_id, dp, prog="PR1", reef=1, f_end=4560, amp_gain=1.0, ckpt_every=240, ckpt_list=(240, 120, 60, 30, 15), minsub=1, maxsub=8,
         cfl=1.0, pcfl=0.75, sec_t0=100.0, sec_x_rel=None, note="", out_root="runs", max_hours=None, Lx=None, xa0_rel=None,
         reef_shift=0.0, relax_g=1.0, wind=None, extra=None):
    P = plan()
    tank, rf = P["tank"], P["reef"]
    vox = 2.0 * dp
    xp = tank["x_p"]
    Lx = rup(tank["Lx_plan"], vox) if Lx is None else float(Lx)
    xa0 = xp + (tank["absorber_from_paddle"] if xa0_rel is None else float(xa0_rel))
    inl = inlet_of(P, prog)
    parms = dict(dp=dp, gridscale=2.0, Lz=tank["slab_cells_z"] * vox, Lx=Lx, h0=tank["h0"], ytop=tank["y_top"], band_vox=1000.0,
                 maxsub=float(maxsub), minsub=float(minsub), cfl=float(cfl), pcfl=float(pcfl), x_p=xp, ramp_s=tank["ramp_s"],
                 xg_end=xp, relax_g=float(relax_g), dt0=1.0 / FPS, wall_taper_m=tank["wall_taper_m"], xa0=xa0, abs_sigma=0.8, abs_pow=2.0,
                 amp_gain=float(amp_gain), rep_P=inl["rep_P"],
                 reef_on=float(reef), rf_foot=rf["foot"] + reef_shift, rf_top_end=rf["top_end"] + reef_shift, rf_h_top=rf["h_top"],
                 rf_slope_n=rf["slope_n"],
                 wind_on=0.0, wind_mode=1.0, wind_q=0.0, wind_t0=1e9, wind_tramp=1.0, wind_t1=1e9,
                 wind_x0=xp + P["criteria"]["wind"]["region_m"][0], wind_x1=xp + P["criteria"]["wind"]["region_m"][1],
                 wind_tap=P["criteria"]["wind"]["taper_m"], wind_band_vox=3.0, thin_mult=P["criteria"]["wind"]["thin_water_min_thickness_dp"],
                 wt_p0=2000.0, wt_lam=40.0, wt_ramp=10.0)
    if wind:
        parms.update(wind)
    if extra:
        parms.update(extra)
    sx = SEC_X_REL if sec_x_rel is None else sec_x_rel
    sec = dict(x0=xp + sx[0], x1=xp + sx[1], t0=float(sec_t0))
    case = dict(kind="FLIP44", dp=dp, vox=vox, reef=int(reef), reef_shift=reef_shift, prog=prog, inlet_name=inl["name"],
                aim_x_from_paddle=inl["aim_x_from_paddle"], aim_t_s=inl["aim_t_s"], sum_a=inl["sum_a"], rep_P=inl["rep_P"],
                Tc=tank["Tc"], Lc=tank["Lc"], x_p=xp, gauges_rel=GAUGES_REL, gauges_scene=[xp + g for g in GAUGES_REL],
                plan_frozen="Unity/Build/FLIP44/plan/plan_frozen.json")
    c = dict(run_id=run_id, out_root=out_root, parms=parms, inlet=inl, solver=dict(veltransfer="apic", donarrowband=0), case=case, sec=sec,
             f_start=1, f_end=int(f_end), ckpt_on=1, ckpt_every=int(ckpt_every), ckpt_list=list(ckpt_list), wall_limit_s=1740,
             level_guard_m=P["criteria"]["level_guard_m"], disk_stop_free_gb=P["criteria"]["disk_stop_free_GB"],
             note=note or ("FLIP44 %s：入口 %s、粒子 %g m、%s、帯なし" % (run_id, inl["name"], dp, "礁あり" if reef else "礁なし")))
    if max_hours is not None:
        c["max_hours"] = float(max_hours)
    return c


def frames_for(t_end):
    return int(math.floor(t_end * FPS + 1e-9)) + 1


STOP_MAIN = dict(module="g44_analyze", func="stop_main_touchdown")
STOP_RP = dict(module="g44_repeat", func="stop_first_group")


def refuse_N_if_no_tool(mode):
    """はがれのない流れの形（N、wind_mode 2）は、道具 g44_airflow.py ができるまで作らない。場面の VEX の mode 2 は 0 Pa を書くので、
    作ると風なしの計算が「N の形」の名前で残る（2026-10-12 確かめ F6 の直し）。"""
    if float(mode) == 2.0 and not os.path.exists(AIRFLOW_TOOL):
        raise SystemExit("はがれのない流れの形（N、wind_mode 2）は、道具 %s がまだないので作らない。場面の VEX の mode 2 は 0 Pa を書くため、"
                         "作ると風なしの計算になる（計画 §4.1・S6）。道具と場面の mode 2 をつないで S6 を通してから使う" % AIRFLOW_TOOL)


def check_wind(kind, c):
    """風の値の確かめ（G6）。おかしければ理由の文で SystemExit。"""
    p = c["parms"]
    try:
        on = float(p.get("wind_on", 0.0)); mode = float(p.get("wind_mode", 1.0))
    except (TypeError, ValueError):
        raise SystemExit("wind_on・wind_mode は数で書く（%r・%r）" % (p.get("wind_on"), p.get("wind_mode")))
    if on not in (0.0, 1.0):
        raise SystemExit("wind_on は 0 か 1（%r）" % p.get("wind_on"))
    if mode not in (1.0, 2.0, 3.0):
        raise SystemExit("wind_mode は 1（はがれた流れの形 S）・2（N）・3（試しの形）のどれか（%r）" % p.get("wind_mode"))
    if kind in ("PR1", "PR2", "PR3", "SH", "RP") and on != 0.0:
        raise SystemExit("%s は風なしの計算（計画 §3.2）。wind_on=%r は受け付けない" % (kind, p.get("wind_on")))
    if kind == "B":
        form = c["case"].get("form")
        want = {"S": 1.0, "N": 2.0}.get(form)
        if on != 1.0:
            raise SystemExit("B（風の計算、形 %s）で wind_on=%r は受け付けない。風なしは形の本番 SH をそのまま使う（record_ja.md §4 の S4）" % (form, p.get("wind_on")))
        if mode != want:
            raise SystemExit("B の形 %s は wind_mode %g。wind_mode=%r は受け付けない（名前と中身が違う計算になる）" % (form, want, p.get("wind_mode")))
    if kind != "SMOKE" and mode == 3.0 and on > 0.5:
        raise SystemExit("wind_mode 3（試しの形）は SMOKE だけ")
    if on > 0.5:
        refuse_N_if_no_tool(mode)


def kind_cfg(kind, rid, kw):
    c = _kind_cfg(kind, rid, kw)
    check_wind(kind, c)
    if kind in ("PR1", "PR2", "PR3", "SH"):
        c["stop_check"] = STOP_MAIN
    elif kind == "RP":
        c["stop_check"] = STOP_RP
    return c


def _kind_cfg(kind, rid, kw):
    P = plan()
    runs = P["runs"]
    T = P["tank"]
    if kind in ("PR1", "PR2"):
        return make(rid, runs[kind]["dp"], prog=kind, f_end=runs[kind]["frames"], sec_t0=100.0, max_hours=2 * runs[kind]["hours"]["hi"],
                    note="FLIP44 %s（下見 %s）：%s、粒子 %g m、礁あり、帯なし、190 s" % (rid, kind[-1], P["programs"][PROG_KEY[kind]]["name"], runs[kind]["dp"]))
    if kind == "PR3":
        x = float(kw.pop("aim"))
        return make(rid, runs["PR3"]["dp"], prog="PR3:%g" % x, f_end=runs["PR3"]["frames"], sec_t0=100.0, max_hours=2 * runs["PR3"]["hours"]["hi"],
                    note="FLIP44 %s（下見 3 本目）：礁の上 %.0f m に狙いを直した入口、粒子 %g m" % (rid, x, runs["PR3"]["dp"]))
    if kind == "SH":
        prog = kw.pop("prog"); onset_pre = float(kw.pop("onset_pre"))
        if prog == "PR3":
            prog = "PR3:%g" % float(kw.pop("aim"))
        f_w0 = int(math.floor(FPS * (onset_pre - P["wind"]["timing"]["restart_ckpt_before_preview_onset_s"])))
        # 途中保存の間隔は f_w の約数で 240 に近いもの（計画 §4.1）。120〜300 の約数がない時（f_w が素数など）は、ある所まで f_w を 1 コマずつ
        # 前へずらす（巻き始めの 6 s 前より前になるだけで、風の計算に要る「3 s 前より前」は守られる。record_ja.md の計画の読み方 18）
        f_w = f_w0
        while not [d for d in range(120, 301) if f_w % d == 0]:
            f_w -= 1
        divs = [d for d in range(120, 301) if f_w % d == 0]
        sp = min(divs, key=lambda d: (abs(d - 240), -d))
        c = make(rid, runs["SH"]["dp"], prog=prog, f_end=runs["SH"]["frames"], sec_t0=100.0, ckpt_every=sp,
                 ckpt_list=(240, 120, 60, 30, 15, 10), max_hours=2 * runs["SH"]["hours"]["hi"],
                 note="FLIP44 %s（形の本番）：入口 %s、粒子 0.25 m、礁あり。風の計算の始めの途中保存 %d コマ（下見の巻き始め %.2f s − 6 s）" % (rid, prog, f_w, onset_pre))
        c["ckpt_lock_until"] = f_w
        c["case"]["f_w"] = f_w
        c["case"]["f_w_from_rule"] = f_w0
        return c
    if kind == "RP":
        aim = kw.pop("aim")
        if aim.startswith("pr3:"):
            key = "RP3:%g" % float(aim.split(":")[1])
            pr = json.load(open(os.path.join(PR3_DIR, "pr3_aim%.0f.json" % float(aim.split(":")[1])), encoding="utf-8"))["repeat_same_aim"]
        else:
            key = "RPflat" if aim == "flat" else "RPreef"
            pr = P["programs"][PROG_KEY[key]]
        return make(rid, runs["RP"]["dp"], prog=key, f_end=frames_for(pr["repeat"]["t_end_s"]), sec_t0=60.0,
                    max_hours=2 * runs["RP"]["hours"]["hi"],
                    note="FLIP44 %s（繰り返しの本番）：%s、粒子 %g m、最初の群＋3 回、%.1f s まで" % (rid, pr["name"], runs["RP"]["dp"], pr["repeat"]["t_end_s"]))
    if kind == "B":
        form = kw.pop("wind", "S"); U = float(kw.pop("U10")); sh = kw.pop("sh"); prog = kw.pop("prog")
        t_on = float(kw.pop("t_on")); t_td = float(kw.pop("t_td")); ckf = int(kw.pop("ckpt_frame"))
        W = P["wind"]; CW = P["criteria"]["wind"]
        q = 0.5 * W["rho_air"] * (U + W["C_crest"]) ** 2
        if form not in ("S", "N"):
            raise SystemExit("wind=%s は知らない形（S か N）" % form)
        refuse_N_if_no_tool(2.0 if form == "N" else 1.0)
        mode = {"S": 1.0, "N": 2.0}[form]
        # 静かな水面のずれ（計画 N1：風の計算は形の本番の値）。省いたら形の本番の ana.json から読む。読めなければ作らない
        # （以前は 0.0 を入れていた。確かめ F1 の直しと一緒に、2026-10-12）
        out_root = kw.get("out_root", "runs")
        if "still_offset" in kw:
            still = float(kw.pop("still_offset")); still_from = "引数 still_offset（%s の ana.json の値を渡す決まり）" % sh
        else:
            ap = os.path.join(ROOT, "Unity/Build/FLIP44", out_root, sh, "ana.json")
            if not os.path.exists(ap):
                raise SystemExit("still_offset を省いたが %s がない。形の本番を g44_analyze.py で読んでから作る" % ap)
            still = float(json.load(open(ap, encoding="utf-8"))["still_level_offset_m"]); still_from = ap
        wind = dict(wind_on=1.0, wind_mode=mode, wind_q=q, wind_t0=t_on - CW["ramp_start_before_onset_s"],
                    wind_tramp=CW["ramp_start_before_onset_s"] - CW["full_before_onset_s"], wind_t1=1e9)
        if prog == "PR3":
            prog = "PR3:%g" % float(kw.pop("aim"))
        rkey = "B%d%s" % (int(round(U)), form) if U > 0 else "B0"
        f_cap = frames_for(t_td + CW["end_cap_after_A_touchdown_Tc"] * T["Tc"])
        # 打ち切り：計算の中の着水の読みが空気の穴を見つけない時も、形の本番の着水 + 2 Tc まで走りきれる時間（確かめ F2 の直し）。
        # 計画の「見込みの上の端の 2 倍」の決まりはそのままで、見込みを着水 + 2 Tc までの道で出し直した（record_ja.md 計画から変えた所 9）
        sys.path.insert(0, TOOLS)
        import g44_hours
        mh, mh_basis = g44_hours.b_max_hours(ckf, t_on, t_td, T["Tc"])
        mh = max(mh, 2 * runs.get(rkey, runs["B35S"])["hours"]["hi"])
        c = make(rid, runs["SH"]["dp"], prog=prog, f_end=f_cap, sec_t0=t_on - CW["ramp_start_before_onset_s"] - 0.5, ckpt_every=24,
                 ckpt_list=(48, 24, 12), wind=wind,
                 max_hours=mh,
                 note="FLIP44 %s（風 %s の形、U10 %g m/s、q %.1f Pa）：%s の %d コマ目の途中保存から。%.2f s から上げ、%.2f s から全部" % (
                     rid, form, U, q, sh, ckf, wind["wind_t0"], wind["wind_t0"] + wind["wind_tramp"]))
        c["f_start"] = ckf + 1
        c["f_first"] = ckf + 1
        c["from_ckpt"] = dict(run=sh, frame=ckf)
        # tip_on・tip_wait_s（2026-10-12、2 回目の確かめの後。record_ja.md §3.2 の TD）：唇の先が静かな水面以下になっても空気の穴が見えない時は、
        # 唇の先の 2 s 後で止める（解析の着水は空気の穴で決まるので、穴ができるまで記録を残す。唇の先から谷の水面までは 0.3 s ほどの見込み）
        c["stop_touchdown"] = dict(after_s=CW["end_after_touchdown_s"], t_from=t_on - 1.0, Lc=T["Lc"],
                                   still_offset_m=still, still_offset_from=still_from, tip_on=True, tip_wait_s=2.0)
        c["case"].update(U10=U, q_Pa=q, form=form, t_on_SH=t_on, t_td_SH=t_td, max_hours_basis=mh_basis)
        return c
    if kind == "SMOKE":
        return make(rid, **kw)
    raise SystemExit("unknown kind " + kind)


if __name__ == "__main__":
    kind, rid = sys.argv[1], sys.argv[2]
    kw = {}
    outp = None
    rest = sys.argv[3:]
    if "--write" in rest:
        i = rest.index("--write"); outp = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
    for a in rest:
        k, v = a.split("=", 1)
        try:
            kw[k] = json.loads(v)
        except Exception:
            kw[k] = v
    c = kind_cfg(kind, rid, kw)
    for k, v in kw.items():      # 残りの k=v は設定の上書き（parms の名前なら parms へ）
        if k in c["parms"]:
            c["parms"][k] = v
        else:
            c[k] = v
    check_wind(kind, c)      # 上書きの後にもう一度（wind_on=0・wind_mode=2・3 の上書きを拒む。G6）
    s = json.dumps(c, ensure_ascii=False, indent=1)
    if outp:
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        open(outp, "w", encoding="utf-8").write(s)
        print("wrote", outp)
    else:
        print(s)
