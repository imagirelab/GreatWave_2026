# -*- coding: utf-8 -*-
"""FLIP44：繰り返しの本番（RP）の判定（計画 plan_ja.md §3.3 (c)）。py -3.10、g44_analyze.py の頂の読みを使う。
回ごと（狙いの時刻 focus_k ± P/2）に主な巻き波（その回の 300〜800 m で、着水までの頂の高さの最大が最も大きい頂）を選び、
  巻き始めの時刻・場所（頂の x）・η_c・H、§3.3 (a) の 3 条件、頂を 300 m までさかのぼって通った時刻 t300 を出す。
さかのぼり：断面の頂の道（g44_analyze の頂のつなぎ）が 300 m より手前から続いていればその道で、届かなければ、一番上の水面の記録
  （板の内側の節の平均）で、1 コマ前の頂の位置を「今の位置 − その所の水深の線形の速さ（中心の周期）× 1/24 s」の ±1.0 m の中の
  いちばん高い所として続ける（record_ja.md の計画の読み方 14）。
判定の文は計画の 3 つの場合（case1・case2・case3）のとおり。
使い方：py -3.10 g44_repeat.py <run_id> [runs|smoke]  → <root>/<run_id>/repeat.json
"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_analyze as A

FPS = 24.0


def program(cfg, P):
    nm = cfg["inlet"]["name"]
    for k, v in P["programs"].items():
        if v["name"] == nm and v.get("repeat"):
            return v
    raise SystemExit("not a repeat program: %s" % nm)


def backtrack_t300(D, EX, xp, parms, path, Tc, x_target=300.0):
    """頂の道 path（[コマ, x_rel, η]）を 300 m までさかのぼる。"""
    path = sorted(path)
    xs = np.array([p[1] for p in path]); fs = np.array([p[0] for p in path])
    if xs.min() <= x_target:
        j = int(np.where(xs <= x_target)[0].max())
        if j + 1 < len(xs) and xs[j + 1] > xs[j]:
            f = fs[j] + (x_target - xs[j]) / (xs[j + 1] - xs[j]) * (fs[j + 1] - fs[j])
        else:
            f = fs[j]
        return dict(t300=float((f - 1) / FPS), how="section_track", start_frame=int(fs[0]), start_x=float(xs[0]))
    # 一番上の水面の記録でさかのぼる
    x = D["x"] - xp
    fidx = {int(f): i for i, f in enumerate(D["frames"])}
    f = int(fs[0]); xc = float(xs[0])
    fc = 1.0 / Tc
    steps = 0
    while xc > x_target and f - 1 in fidx and steps < 4000:
        h = -float(A.bed_y(parms, np.array([xc + xp]))[0])
        c = float(2 * np.pi * fc / A.k_of_f(np.array([fc]), h)[0])
        xpred = xc - c / FPS
        e = EX[fidx[f - 1]]
        m = (x >= xpred - 1.0) & (x <= xpred + 1.0)
        if not m.any():
            break
        ii = np.where(m)[0]
        j = ii[int(np.nanargmax(e[ii]))]
        xn = float(x[j])
        if 0 < j < len(x) - 1 and np.isfinite(e[j - 1]) and np.isfinite(e[j + 1]):
            d = e[j - 1] - 2 * e[j] + e[j + 1]
            if d < 0:
                xn = float(x[j] + 0.5 * (e[j - 1] - e[j + 1]) / d * (x[1] - x[0]))
        f -= 1; xprev = xc; xc = xn; steps += 1
    if xc > x_target:
        return dict(t300=None, how="hf_backtrack_failed", start_frame=int(fs[0]), start_x=float(xs[0]), stopped_at=[f, xc])
    # 300 m を切ったコマと 1 つ後のコマの間で一次の補間
    tt = (f - 1) / FPS + (x_target - xc) / max(xprev - xc, 1e-6) / FPS
    return dict(t300=float(tt), how="hf_backtrack", start_frame=int(fs[0]), start_x=float(xs[0]), steps=steps)


def analyze(rid, root="runs", groups=None):
    P = A.plan(); Tc = P["tank"]["Tc"]; Lc = P["tank"]["Lc"]
    rd = A.run_dir(rid, root)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    prog = program(cfg, P)
    Pr = prog["repeat"]["P_s"]; foci = prog["repeat"]["focus_times_s"]
    crit = P["criteria"]["repeat"]; sel = P["criteria"]["selection"]
    xp = cfg["parms"]["x_p"]
    D = A.load_hf(rd)
    off = A.still_offset(cfg, D, root)[0]      # 計画 N1（1 コマ目からの計算なのでこの計算の 0.5〜2.0 s。記録が足りなければ理由を書いて止まる）
    EX = A.zmean(D) - off
    CA = A.crest_analysis(rd, cfg, off)
    ev = CA["events"] if CA else []
    t_done = float(D["t"].max())
    G = []
    for k, tf in enumerate(foci, 1):
        if groups and k not in groups:
            continue
        if t_done < tf + 0.5 * Pr - 1e-9 and t_done < tf + 2 * Tc:
            G.append(dict(k=k, focus_t=tf, done=False)); continue
        cand = [e for e in ev if tf - 0.5 * Pr <= (e["frame_eta_max"] - 1) / FPS <= tf + 0.5 * Pr]
        m = A.main_event(cand)
        g = dict(k=k, focus_t=tf, done=True, main=None)
        if m is not None:
            on, td = m["onset"], m["touchdown"]
            oth = A.other_onsets(ev, m, Tc, Lc, sel["one_plunger_window_Tc"]) if on else []
            g.update(main=dict(first_frame=m["first_frame"], x_first_rel=m["x_first_rel"], eta_max_pre_td=m["eta_max_pre_td"]), onset=on, touchdown=td,
                     a1=bool(on is not None and sel["onset_x_window_m"][0] <= on["xc_rel"] <= sel["onset_x_window_m"][1]),
                     a2=bool(on is not None and td is not None), a3=bool(on is not None and not [o for o in oth if not o["piece_of_main"]]),
                     other_onsets=oth)
            g["t300"] = backtrack_t300(D, EX, xp, cfg["parms"], m["path"], Tc, crit["crest_gauge_x_m"]) if on else None
        G.append(g)
    out = dict(run_id=rid, P_s=Pr, foci=foci, still_level_offset_m=off, groups=G, criteria=crit)

    def cmp(base, others, shift0):
        rows = []
        for g in others:
            if not (g.get("onset") and base.get("onset")):
                rows.append(dict(k=g["k"], ok=False, why="no onset")); continue
            n = g["k"] - base["k"]
            dt_on = g["onset"]["t"] - (base["onset"]["t"] + n * Pr)
            dx_on = g["onset"]["xc_rel"] - base["onset"]["xc_rel"]
            de = g["onset"]["eta_c"] / base["onset"]["eta_c"] - 1
            dH = g["onset"]["H"] / base["onset"]["H"] - 1
            t3 = (g.get("t300") or {}).get("t300"); t3b = (base.get("t300") or {}).get("t300")
            d300 = (t3 - (t3b + n * Pr)) if (t3 is not None and t3b is not None) else None
            ok = bool(d300 is not None and abs(d300) <= crit["same_crest_dt_at_300m_Tc"] * Tc and abs(dt_on) <= crit["onset_dt_s"]
                      and abs(dx_on) <= crit["onset_dx_m"] and abs(de) <= crit["eta_c_rel"] and abs(dH) <= crit["H_rel"])
            rows.append(dict(k=g["k"], vs=base["k"], d_t300_s=d300, d_onset_t_s=dt_on, d_onset_x_m=dx_on, d_eta_c_rel=de, d_H_rel=dH, ok=ok))
        return rows
    done = [g for g in G if g.get("done")]
    if len(done) == 4 and all(g.get("onset") for g in done):
        c1 = cmp(done[0], done[1:], 0)
        c2 = cmp(done[1], done[2:], 1)
        if all(r["ok"] for r in c1):
            case = "case1"
        elif all(r["ok"] for r in c2):
            case = "case2"
        else:
            case = "case3"
        out.update(vs_first=c1, vs_second=c2, case=case, verdict_ja=P["criteria"]["repeat"]["verdict_ja"][case])
        # ずれが回ごとに同じ向きに大きくなるか（記録。6 回の計算の提案の材料）
        dts = [r["d_onset_t_s"] for r in c1]
        out["drift_grows_same_sign"] = bool(all(np.sign(dts[i]) == np.sign(dts[0]) for i in range(len(dts))) and all(abs(dts[i + 1]) > abs(dts[i]) for i in range(len(dts) - 1)))
    else:
        out["case"] = None
        out["note_ja"] = "4 回の巻き始めがそろっていない（走りきっていないか、巻き始めのない回がある）"
    json.dump(out, open(os.path.join(rd, "repeat.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


def stop_first_group(rid, root, t_done, cfg):
    """繰り返しの 1 回目が §3.3 (a) を外れたら、1 回目の着水 + 2 Tc で止める（計画 §3.3 (c) の最後）。"""
    P = A.plan(); Tc = P["tank"]["Tc"]
    prog = program(cfg, P)
    tf = prog["repeat"]["focus_times_s"][0]; Pr = prog["repeat"]["P_s"]
    if t_done < tf + 2 * Tc:
        return False, "group 1 not finished (t %.1f < focus %.1f + 2 Tc)" % (t_done, tf)
    o = analyze(rid, root, groups=[1])
    g = o["groups"][0]
    ok = bool(g.get("a1") and g.get("a2") and g.get("a3"))
    if ok:
        return False, dict(group1="pass", onset=g.get("onset"))
    td = (g.get("touchdown") or {}).get("t")
    lim = (td + 2 * Tc) if td is not None else (tf + 0.5 * Pr)
    return bool(t_done >= lim), dict(group1="fail", a1=g.get("a1"), a2=g.get("a2"), a3=g.get("a3"), onset=g.get("onset"), stop_at_t=lim,
                                     note_ja="1 回目が (a) を外れた。(a) と同じ式で狙いを 1 回だけ直し、最初から走らせ直す（直した後も外れたら止めて伺う）")


if __name__ == "__main__":
    rid = sys.argv[1]; root = sys.argv[2] if len(sys.argv) > 2 else "runs"
    o = analyze(rid, root)
    for g in o["groups"]:
        print(g["k"], g.get("focus_t"), "onset", g.get("onset") and (round(g["onset"]["t"], 3), round(g["onset"]["xc_rel"], 1), round(g["onset"]["eta_c"], 2)),
              "a", g.get("a1"), g.get("a2"), g.get("a3"), "t300", (g.get("t300") or {}).get("t300"))
    print("case", o.get("case"), o.get("verdict_ja", o.get("note_ja")))
