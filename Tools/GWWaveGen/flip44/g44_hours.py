# -*- coding: utf-8 -*-
"""FLIP44：本番の計算の時間の見込みを、区切った起動のやり直しと途中保存の間隔の固定を入れて出し直す（py -3.10、numpy だけ）。
2026-10-12 の確かめ（check/check_ja.md）の F2・F3・F4 を受けて書いた。流体の計算はしない。

やり方：
  - 1 コマの秒は FLIP42 の記録（後の起動の値を使う。ana.json の wall_sum_h と同じ決まり）：粒子 0.34375 m の計算（下見・繰り返し）は R2（粒子 0.35 m）、
    0.25 m の計算（形の本番・風）は R3。巻き始めのコマを、見込みの巻き始めに来るようにずらして当てる。記録の外のコマは、記録の終わりの 200 コマの中央値。
  - 「下の端」は粒子の数の比で縮めた値（煙の試しの静かな水の数 ÷ FLIP42 の同じコマの数）、「上の端」は縮めない値。
  - g44_chain.py の起動の決まりをそのまま真似る：1 回 1,740 s（越えたコマで止まる）、途中保存はコマの番号が間隔の倍数の所、間隔は前の起動の
    終わりの 48 コマの 75 % 点と最初のコマの秒から選ぶ（ckpt_per_launch 1）、ckpt_lock_until までは固定、途中保存が作れなければ間隔を一段小さく
    して同じコマからやり直す（固定の区間の中か、いちばん小さい間隔なら止まる）。起動ごとに立ち上げ 6 s、途中保存の読み込みは最初のコマに
    2 s（0.34375 m）・3.5 s（0.25 m）【測った：FLIP42 R2・R3 の起動の最初のコマ】、止める決まりの読み 11 s（下見・形の本番）・40 s（繰り返し）
    【測った：確かめ §3】を足す。止める決まり（下見・形の本番：主な巻き波の着水 + 2 Tc と線形の焦点 + 1 Tc の両方を過ぎた起動の後。風：
    計算の中で空気の穴を見つけた 0.5 s 後か、形の本番の着水 + 2 Tc）も真似る。
  - 機械の重さ（1.0・1.33）は 1 コマの秒に掛ける。風の計算は 1 コマの秒を 1.02 倍（煙の試し S9_v2）。
  - 確かめ：FLIP42 R2・R4d（固定なし）を同じ真似で走らせ、起動の時間の和（記録）と比べる。
  - 見込みの巻き始めは 140〜165 s を 1 s ごと（c44_lock_cost.py と同じ範囲）。
使い方：
  py -3.10 g44_hours.py                         → Unity/Build/FLIP44/fixes/hours44.json と表（標準出力）
関数：b_max_hours(ckpt_frame, t_on, t_td)       → 風の計算の打ち切りの時間（g44_cfg.py が使う。確かめ F2 の直し）
"""
import os, sys, json, glob, math
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
B44 = REPO + "/Unity/Build/FLIP44"
R42 = REPO + "/Unity/Build/FLIP42/runs"
PLAN = B44 + "/plan/plan_numbers.json"
OUT = B44 + "/fixes/hours44.json"
FPS = 24.0
WL = 1740.0
BOOT_S = 6.0
CKLOAD = {0.34375: 2.0, 0.25: 3.5}
STOPCHK_S = {"PR": 11.0, "SH": 11.0, "RP": 40.0, "B": 0.0}
WIND_COST = 1.02
ONSET_R = {"R2": 3708, "R3": 3714, "R4d": 3718}          # FLIP42 の ana.json の巻き始めのコマ
TD_R = {"R2": 3728, "R3": 3745, "R4d": 3748}             # 着水のコマ
CAV_R3 = 3745                                            # 計算の中の空気の穴の読みが見つけたコマ（確かめ §3）


def series(rid):
    """FLIP42 の 1 コマの秒（後の起動の値）と粒子の数。"""
    fs = sorted(glob.glob(os.path.join(R42, rid, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    F, W, N = [], [], []
    for p in fs:
        d = np.load(p); fr = list(map(int, d["frames"]))
        if F:
            k = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in k]; W = [W[i] for i in k]; N = [N[i] for i in k]
        F += fr; W += list(map(float, d["wall"])); N += list(map(int, d["npts"]))
    return np.array(F), np.array(W), np.array(N)


_CACHE = {}


def rec(rid):
    if rid not in _CACHE:
        F, W, N = series(rid)
        _CACHE[rid] = dict(F=F, W=W, N=N, w=dict(zip(F.tolist(), W.tolist())), tail=float(np.median(W[-200:])), f_last=int(F[-1]))
    return _CACHE[rid]


def launch_sum(rid):
    """FLIP42 の起動の時間の和（run_c*.json の wall_total_s）と起動の数。"""
    tot = 0.0; n = 0
    for p in glob.glob(os.path.join(R42, rid, "run_c*.json")):
        r = json.load(open(p, encoding="utf8")); tot += float(r.get("wall_total_s") or 0.0); n += 1
    return tot, n


def cost_fn(rid, f_on_new=None, scale=1.0, load=1.0):
    """FLIP42 の rid の 1 コマの秒を、rid の巻き始めが f_on_new に来るようにずらした関数。"""
    R = rec(rid)
    sh = 0 if f_on_new is None else ONSET_R[rid] - int(f_on_new)

    def c(f):
        g = f + sh
        if g < 2:
            g = 2
        v = R["w"].get(g, R["tail"]) if g <= R["f_last"] else R["tail"]
        return v * scale * load
    return c


def simulate(c, f_first, f_end, base_sp, sp_list, lock_until=0, ckload=3.0, boot=BOOT_S, stopchk=0.0, nper=1.0,
             rule_after_launch=None, online_stop_frame=None, max_h=None, trace=None):
    """g44_chain.py の起動の決まりの真似。返り値：時間（h）、起動の数、やり直したコマ、記録だけの時間、止まったか、打ち切りか。
    trace（リスト）を渡すと、起動ごとに dict(f0, done, sp, cks：その起動で作る途中保存のコマ) を足す（置き場所の見込み。2026-10-12 G2）。
    trace は返り値と時間の計算を変えない。"""
    sp_list = sorted(set(sp_list), reverse=True)
    f0 = f_first; prev = None; force_idx = None; el = 0.0; launches = 0; resim = 0; stalled = None; cut = False; done = f_first - 1
    while f0 <= f_end:
        if max_h is not None and el / 3600 > max_h:
            cut = True; break
        if f0 <= lock_until:
            sp = base_sp
        else:
            sp = base_sp if base_sp in sp_list else sp_list[0]
            if prev is not None and len(prev) >= 3:
                s_est = float(np.percentile(np.array(prev[1:])[-48:], 75)); load0 = prev[0]
                ok = [v for v in sp_list if load0 + 1.5 * nper * v * s_est <= 0.92 * WL]
                sp = ok[0] if ok else sp_list[-1]
            if force_idx is not None:
                sp = min(sp, sp_list[min(force_idx, len(sp_list) - 1)])
        wl = WL if max_h is None else min(WL, max(60.0, max_h * 3600 - el))
        walls = []; s = 0.0; f = f0; why = "end"
        while f <= f_end:
            w = c(f) + (ckload if (f == f0 and f0 > 1) else 0.0)
            s += w; walls.append(w)
            if online_stop_frame is not None and f >= online_stop_frame:
                why = "online"; f += 1; break
            f += 1
            if s > wl:
                why = "wall"; break
        launches += 1
        el += boot + s + stopchk
        done = f - 1
        cks = [k for k in range((f0 // sp) * sp, done + 1, sp) if f0 <= k <= done and k > 0]
        if trace is not None:
            trace.append(dict(f0=f0, done=done, sp=sp, cks=list(cks)))
        if why != "wall" or done >= f_end:
            break
        if rule_after_launch is not None and rule_after_launch(done):
            break
        prev = walls
        if not cks:
            idx = sp_list.index(sp) if sp in sp_list else 0
            if idx + 1 >= len(sp_list) or f0 <= lock_until:
                stalled = dict(at_frame=f0, sp=sp, in_lock=bool(f0 <= lock_until)); break
            force_idx = idx + 1
            resim += done - f0 + 1
            continue
        force_idx = None
        resim += done - cks[-1]
        f0 = cks[-1] + 1
    ideal = sum(c(f) for f in range(f_first, min(done, f_end) + 1))
    return dict(hours=el / 3600, ideal_hours=ideal / 3600, launches=launches, resim_frames=int(resim), last_frame=int(done),
                stalled=stalled, cut_by_max_hours=cut, overhead_ratio=(el / 3600) / (ideal / 3600) if ideal > 0 else None)


def plan():
    return json.load(open(PLAN, encoding="utf-8"))


def frames_for(t):
    return int(math.floor(t * FPS + 1e-9)) + 1


def f_w_rule(onset_pre, pre_s=6.0):
    """g44_cfg.py の形の本番の固定（record_ja.md の計画の読み方 18）。"""
    f_w = int(math.floor(FPS * (onset_pre - pre_s)))
    while not [d for d in range(120, 301) if f_w % d == 0]:
        f_w -= 1
    divs = [d for d in range(120, 301) if f_w % d == 0]
    return f_w, min(divs, key=lambda d: (abs(d - 240), -d))


def particle_scale():
    """煙の試しの静かな水の粒子の数 ÷ FLIP42 の同じコマの数（礁の分と細かさの違い）。"""
    def smoke_n(run, frame):
        for p in glob.glob(os.path.join(B44, "smoke", run, "hf_c*.npz")):
            d = np.load(p); fr = list(map(int, d["frames"])); n = list(map(int, d["npts"]))
            if frame in fr and n[fr.index(frame)] > 0:
                return n[fr.index(frame)]
        return None
    out = {}
    for dp, sm, fr, rid in ((0.34375, "S2", 120, "R2"), (0.25, "S2b", 24, "R3")):
        a = smoke_n(sm, fr); R = rec(rid)
        b = int(R["N"][list(R["F"]).index(fr)]) if fr in list(R["F"]) else None
        out[dp] = dict(smoke=sm, frame=fr, n_smoke=a, flip42=rid, n_flip42=b, scale=(a / b) if (a and b and b > 0) else None)
    return out


# ------------------------------------------------------------------ 計算ごと
def est_PR(onset_s, aim_t, scale, load, Tc, max_h=None, trace=None):
    f_on = int(round(onset_s * FPS)) + 1
    c = cost_fn("R2", f_on, scale, load)
    t_td = onset_s + (TD_R["R2"] - ONSET_R["R2"]) / FPS
    rule = lambda done: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= aim_t + Tc
    return simulate(c, 1, 4560, 240, (240, 120, 60, 30, 15), 0, CKLOAD[0.34375], stopchk=STOPCHK_S["PR"], rule_after_launch=rule, max_h=max_h,
                    trace=trace)


def est_SH(onset_s, aim_t, scale, load, Tc, max_h=None, trace=None):
    f_on = int(round(onset_s * FPS)) + 1
    c = cost_fn("R3", f_on, scale, load)
    f_w, sp = f_w_rule(onset_s)
    t_td = onset_s + (TD_R["R3"] - ONSET_R["R3"]) / FPS
    rule = lambda done: (done - 1) / FPS >= t_td + 2 * Tc and (done - 1) / FPS >= aim_t + Tc
    r = simulate(c, 1, 4560, sp, (240, 120, 60, 30, 15, 10), f_w, CKLOAD[0.25], stopchk=STOPCHK_S["SH"], rule_after_launch=rule, max_h=max_h,
                 trace=trace)
    r.update(f_w=f_w, sp_lock=sp)
    return r


def est_B(onset_s, scale, load, Tc, path="cap", ckpt_frame=None, t_td=None, max_h=None, trace=None):
    """path：normal（計算の中で空気の穴を見つけ、その 0.5 s 後で止まる）／cap（見つけず、形の本番の着水 + 2 Tc まで）。"""
    f_on = int(round(onset_s * FPS)) + 1
    c0 = cost_fn("R3", f_on, scale, load)
    c = lambda f: c0(f) * WIND_COST
    ckf = ckpt_frame if ckpt_frame is not None else f_w_rule(onset_s)[0]
    t_td = onset_s + (TD_R["R3"] - ONSET_R["R3"]) / FPS if t_td is None else t_td
    f_cap = frames_for(t_td + 2 * Tc)
    stop_f = None
    if path == "normal":
        f_cav = f_on + (CAV_R3 - ONSET_R["R3"])
        stop_f = f_cav + int(round(0.5 * FPS))
    r = simulate(c, ckf + 1, f_cap, 24, (48, 24, 12), 0, CKLOAD[0.25], stopchk=STOPCHK_S["B"], online_stop_frame=stop_f, max_h=max_h, trace=trace)
    r.update(ckpt_frame=ckf, f_cap=f_cap, frames=(min(stop_f, f_cap) if stop_f else f_cap) - ckf)
    return r


def rp_cost(aim, scale, load, P):
    """繰り返しの 1 コマの秒：R2 の崩れの前の秒（1 回目の巻き始めに合わせてずらす）＋崩れの後の落ち着いた秒（R2 の終わりの 200 コマの
    中央値）＋各回の崩れの分（R2 の巻き始め −144〜+800 コマの、落ち着いた秒を越える分）。巻き始め＝線形の焦点 − 17.05 s（R2 の焦点と巻き始めの差）。"""
    R = rec("R2")
    prog = P["programs"]["RP_reef500" if aim == "reef" else "RP_flat592"]
    lead = P["programs"]["PR1_R3_flat592"]["aim_t_s"] - (ONSET_R["R2"] - 1) / FPS
    ons = [int(round((tf - lead) * FPS)) + 1 for tf in prog["repeat"]["focus_times_s"]]
    base_after = R["tail"]
    sh = ONSET_R["R2"] - ons[0]
    exc = {d: max(0.0, R["w"].get(ONSET_R["R2"] + d, base_after) - base_after) for d in range(-144, 801)}

    def c(f):
        if f <= ons[0] - 144:
            g = min(max(f + sh, 2), ONSET_R["R2"] - 144)
            v = R["w"].get(g, base_after)
        else:
            v = base_after
        for o in ons:
            d = f - o
            if -144 <= d <= 800:
                v += exc[d]
        return v * scale * load
    return c, frames_for(prog["repeat"]["t_end_s"]), ons


def est_RP(aim, scale, load, P, max_h=None, trace=None):
    c, f_end, ons = rp_cost(aim, scale, load, P)
    r = simulate(c, 1, f_end, 240, (240, 120, 60, 30, 15), 0, CKLOAD[0.34375], stopchk=STOPCHK_S["RP"], max_h=max_h, trace=trace)
    r.update(f_end=f_end, onsets_frames=ons)
    return r


# ------------------------------------------------------------------ 風の計算の打ち切り（g44_cfg.py の B から呼ぶ。確かめ F2）
def b_max_hours(ckpt_frame, t_on, t_td, Tc=None):
    """形の本番の途中保存 ckpt_frame から、形の本番の着水 + 2 Tc（計画 §4.1 の打ち切り）まで、計算の中の着水の読みが空気の穴を見つけない
    場合でも走りきれる時間。FLIP42 R3 の 1 コマの秒（縮めない、機械の重さ 1.0）を、R3 の巻き始めが t_on に来るようにずらし、風の分 1.02 倍、
    区切った起動のやり直しを入れた見込みの、計画の決まり（§3.2：見込みの上の端の 2 倍）どおり 2 倍。"""
    P = plan(); Tc = Tc or P["tank"]["Tc"]
    r = est_B(t_on, 1.0, 1.0, Tc, path="cap", ckpt_frame=int(ckpt_frame), t_td=t_td)
    mh = math.ceil(2.0 * r["hours"] * 100) / 100
    return mh, dict(rule_ja="FLIP42 R3 の 1 コマの秒（縮めない・機械の重さ 1.0・風 1.02 倍・区切りのやり直し込み）で、途中保存 %d コマから"
                            "形の本番の着水 + 2 Tc（%d コマ）までの見込み %.2f 時間の 2 倍（計画 §3.2 の打ち切りの決まり）。2026-10-12 確かめ F2 の直し"
                            % (int(ckpt_frame), r["f_cap"], r["hours"]),
                    est_hours_cap_path=r["hours"], launches=r["launches"], frames=r["frames"], tool="g44_hours.py b_max_hours")


# ------------------------------------------------------------------ 本体
def main():
    P = plan(); Tc = P["tank"]["Tc"]; runs = P["runs"]
    PS = particle_scale()
    out = dict(note_ja=__doc__.split("使い方")[0], particle_scale={str(k): v for k, v in PS.items()})
    # 確かめ：FLIP42 の R2・R4d を同じ真似で
    val = {}
    for rid, lst in (("R2", (240, 120, 60, 30, 15, 7)), ("R4d", (240, 120, 80, 60, 40, 30, 20, 14, 10, 7))):
        R = rec(rid)
        cfg = json.load(open(os.path.join(R42, rid, "cfg.json"), encoding="utf8"))
        c = lambda f, R=R: R["w"].get(f, R["tail"])
        sim = simulate(c, 1, int(cfg["f_end"]), int(cfg["ckpt_every"]), lst, 0, 2.0 if rid == "R2" else 3.5, boot=0.0,
                       nper=float(cfg.get("ckpt_per_launch", 1)))
        ls, n = launch_sum(rid)
        val[rid] = dict(record_frame_sum_h=float(R["W"].sum() / 3600), record_launch_sum_h=ls / 3600, record_launches=n,
                        record_ratio=ls / R["W"].sum(), sim_hours=sim["hours"], sim_launches=sim["launches"], sim_ratio=sim["overhead_ratio"])
    out["validation_flip42"] = val
    onsets = list(np.arange(140.0, 166.0, 1.0))
    aims = {"PR1": P["programs"]["PR1_R3_flat592"]["aim_t_s"], "PR2": P["programs"]["PR2_reef_aim500"]["aim_t_s"]}
    res = {}
    for load in (1.0, 1.33):
        L = "%.2f" % load
        for end, sc in (("lo", True), ("hi", False)):
            s34 = PS[0.34375]["scale"] if sc else 1.0
            s25 = PS[0.25]["scale"] if sc else 1.0
            rows = {}
            for pr in ("PR1", "PR2"):
                rows[pr] = [est_PR(o, aims[pr], s34, load, Tc, max_h=2 * runs[pr]["hours"]["hi"]) for o in onsets]
                rows["SH_" + pr] = [est_SH(o, aims[pr], s25, load, Tc, max_h=2 * runs["SH"]["hours"]["hi"]) for o in onsets]
            rows["B_normal"] = [est_B(o, s25, load, Tc, "normal") for o in onsets]
            rows["B_cap"] = [est_B(o, s25, load, Tc, "cap") for o in onsets]
            rows["B_cap_old_limit"] = [est_B(o, s25, load, Tc, "cap", max_h=2 * runs["B35S"]["hours"]["hi"]) for o in onsets]
            rows["RP_reef"] = [est_RP("reef", s34, load, P, max_h=2 * runs["RP"]["hours"]["hi"])]
            rows["RP_flat"] = [est_RP("flat", s34, load, P, max_h=2 * runs["RP"]["hours"]["hi"])]
            summ = {}
            for k, rr in rows.items():
                h = [r["hours"] for r in rr]; idl = [r["ideal_hours"] for r in rr]
                summ[k] = dict(hours_min=min(h), hours_max=max(h), ideal_min=min(idl), ideal_max=max(idl),
                               overhead_ratio_min=min(r["overhead_ratio"] for r in rr), overhead_ratio_max=max(r["overhead_ratio"] for r in rr),
                               stalled=[float(onsets[i]) for i, r in enumerate(rr) if r["stalled"]] if len(rr) > 1 else [bool(rr[0]["stalled"])],
                               cut_by_max_hours=[float(onsets[i]) for i, r in enumerate(rr) if r["cut_by_max_hours"]] if len(rr) > 1 else [bool(rr[0]["cut_by_max_hours"])],
                               launches_max=max(r["launches"] for r in rr))
            res["load%s_%s" % (L, end)] = summ
    out["estimates"] = res
    # 報告に入れる計算の和（PR1・PR2・SH・B35S・B45S・RP）。SH は下見 1 の入口（焦点が遅い方）、RP は平らの狙い（長い方）を上に、
    # 下見 2・礁の狙いを下に使う。風は計算の中で着水を見つける道（normal）。cap の道は別に書く
    tot = {}
    for load in ("1.00", "1.33"):
        lo = res["load%s_lo" % load]; hi = res["load%s_hi" % load]
        a = lo["PR1"]["hours_min"] + lo["PR2"]["hours_min"] + lo["SH_PR2"]["hours_min"] + 2 * lo["B_normal"]["hours_min"] + lo["RP_reef"]["hours_min"]
        b = hi["PR1"]["hours_max"] + hi["PR2"]["hours_max"] + hi["SH_PR1"]["hours_max"] + 2 * hi["B_normal"]["hours_max"] + hi["RP_flat"]["hours_max"]
        bc = b - 2 * hi["B_normal"]["hours_max"] + 2 * hi["B_cap"]["hours_max"]
        tot[load] = dict(report_runs_hours_lo=a, report_runs_hours_hi=b, report_runs_hours_hi_if_both_B_reach_cap=bc)
    out["totals"] = tot
    out["plan_hours"] = {k: runs[k]["hours"] for k in ("PR1", "PR2", "SH", "B35S", "RP")}
    out["plan_totals"] = P["totals"]["hours"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return out


def fmt(o):
    L = []
    L.append("validation " + json.dumps(o["validation_flip42"], ensure_ascii=False, default=lambda v: round(float(v), 3)))
    L.append("particle_scale " + json.dumps(o["particle_scale"], ensure_ascii=False, default=float))
    for k, summ in o["estimates"].items():
        L.append("== " + k)
        for r, s in summ.items():
            L.append("  %-16s %6.2f-%6.2f h (record only %6.2f-%6.2f, x%.3f-%.3f) launches<=%d stalled=%s cut=%s" % (
                r, s["hours_min"], s["hours_max"], s["ideal_min"], s["ideal_max"], s["overhead_ratio_min"], s["overhead_ratio_max"],
                s["launches_max"], s["stalled"], s["cut_by_max_hours"]))
    L.append("totals " + json.dumps(o["totals"], default=lambda v: round(float(v), 2)))
    L.append("plan " + json.dumps(o["plan_hours"]) + " " + json.dumps(o["plan_totals"]))
    return "\n".join(L)


if __name__ == "__main__":
    o = main()
    print(fmt(o))
