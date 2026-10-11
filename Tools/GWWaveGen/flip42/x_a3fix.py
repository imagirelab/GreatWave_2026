# -*- coding: utf-8 -*-
"""FLIP42：A3'（焦点の模型）の符号を直した値を、残してある計算の記録から出し直す。2026-10-11。
- 入力：runs/<計算>/hf_c*.npz（一番上の水面の高さ）と cfg.json。g_analyze.py の読み込み・線形の値・測る点の読み方をそのまま使う
  （analyze() の A1・A2' と同じ手順で R・e_f・g_f を作る）。
- 出す値：直した版（g_analyze.a3p_model）と 10/9 の版（a3p_model_old_sign）。10/9 の版が ana.json の A3p_model と同じになるかで、
  入力が記録の時と同じことを確かめる。直した版は、探す格子を 1,001 × 901（計画の関数 p_plan_numbers.py と同じ）にした値も参考に出す。
- 出力：Unity/Build/FLIP42/a3fix/a3p_fix.json。ana.json は書き換えない。
新しい流体の計算はしない。Houdini は起動しない。何も消さない。
使い方：py -3.10 -B Tools/GWWaveGen/flip42/x_a3fix.py [R1b R2 R3 R4d]
"""
import sys, os, json, datetime
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g_analyze as GA

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/a3fix"
JUDGED = {"R3", "R4d"}   # 計画 §5 (a)：A3' は R3・R4 で判定、ほかは記録


def inputs(rid):
    P = GA.plan(); C = GA.comps_full(P)
    cfg = json.load(open(os.path.join(GA.ROOT, rid, "cfg.json"), encoding="utf8"))
    xp = cfg["parms"]["x_p"]; Lc = C["Lc"]; Tc = C["Tc"]
    D = GA.load_hf(rid)
    off = GA.still_level(D, xp)
    EX = GA.zmean(D) - off
    t = D["t"]; x = D["x"]
    win = t <= P["tank"]["t_end"] + 1e-9
    xr = P["gauges"]["band_exit"]["x_rel"]
    em = GA.gauge(EX, x, xp + xr)[win]; el = GA.lin_series(C, xr, t[win])
    fr, Fm, Fl = GA.spec_ratio(np.nan_to_num(em), el, C)
    R = Fm / np.where(abs(Fl) > 0, Fl, 1)
    xr2 = P["gauges"]["kc(x-xb)=-15"]["x_rel"]
    em2 = GA.gauge(EX, x, xp + xr2)[win]; el2 = GA.lin_series(C, xr2, t[win])
    fr2, Fm2, Fl2 = GA.spec_ratio(np.nan_to_num(em2), el2, C)
    R2 = Fm2 / np.where(abs(Fl2) > 0, Fl2, 1)
    band = P["criteria"]["A2p_propagation"]["band_Hz"]
    m2 = (fr >= band[0]) & (fr <= band[1])
    kf = GA.k_of_f(fr, C["h"])
    dx2 = xr2 - xr
    e_f = -np.angle(R2[m2] / R[m2]) / (kf[m2] * dx2)
    g_f = abs(R2[m2]) / abs(R[m2])
    w2 = abs(Fl[m2]) ** 2
    return dict(C=C, f=C["f"], fr=fr, R=R, m2=m2, e_f=e_f, g_f=g_f, xr=xr, dx2=dx2, Lc=Lc, Tc=Tc,
                e_wmean=GA.wmean(e_f, w2), g_wmean=GA.wmean(g_f, w2), frames_done=int(D["frames"].max()))


def main(rids):
    os.makedirs(OUT, exist_ok=True)
    res = {"schema": "GreatWave.FLIP42.a3p_fix/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "why_ja": "g_analyze.py の A3'（10/9 の版）は、帯の出口で測った位相 arg R と速さの誤差による波数の変化を、成分の位相に逆の符号で入れていた"
                     "（独立の確かめ Unity/Build/FLIP42/check/R4/check_ja.md の見つけた所 1）。直した版で出し直した。ana.json は書き換えていない",
           "tolerance_ja": "計画 §5 (a) A3'：場所 ±0.1 Lc・時刻 ±0.1 Tc・頂と H の比 0.95 以上、R4 のずれが R3 より小さいこと（R3・R4 で判定、ほかは記録）",
           "grid_ja": "判定に使う値は 10/9 の版と同じ探す格子（x 501 × t 451）。fine_grid は 1,001 × 901 の参考",
           "runs": {}}
    for rid in rids:
        I = inputs(rid)
        a = (I["C"], I["f"], I["fr"], I["R"], I["m2"], I["e_f"], I["g_f"], I["xr"], I["dx2"], I["Lc"], I["Tc"])
        new = GA.a3p_model(*a)
        old = GA.a3p_model_old_sign(*a)
        fine = GA.a3p_model(*a, nx=1001, nt=901)
        ana = json.load(open(os.path.join(GA.ROOT, rid, "ana.json"), encoding="utf8"))
        rec = ana["A3p_model"]
        keys = ("dx_focus_over_Lc", "dt_focus_over_Tc", "crest_ratio", "H_ratio")
        same = all(abs(old[k] - rec[k]) < 1e-9 for k in keys)
        same_a2 = abs(I["e_wmean"] - ana["A2p"]["speed_err_wmean"]) < 1e-12 and abs(I["g_wmean"] - ana["A2p"]["amp_change_wmean"]) < 1e-12
        ok = (abs(new["dx_focus_over_Lc"]) <= 0.1 and abs(new["dt_focus_over_Tc"]) <= 0.1 and new["crest_ratio"] >= 0.95 and new["H_ratio"] >= 0.95)
        for d in (new, old, fine):
            d.pop("note", None)
        res["runs"][rid] = dict(frames_done=I["frames_done"], A2p_speed_err_wmean=I["e_wmean"], A2p_amp_change_wmean=I["g_wmean"],
                                fixed=new, old_sign=old, fixed_fine_grid=fine, ana_json_A3p_model=dict((k, rec[k]) for k in keys),
                                old_sign_equals_ana_json=bool(same), A2p_equals_ana_json=bool(same_a2),
                                within_tolerance=bool(ok), judged=rid in JUDGED)
        print(rid, "fixed", {k: round(new[k], 4) for k in keys}, "old", {k: round(old[k], 4) for k in keys},
              "fine", {k: round(fine[k], 4) for k in keys}, "old==ana", same, "A2p==ana", same_a2)
    if "R3" in res["runs"] and "R4d" in res["runs"]:
        r3, r4 = res["runs"]["R3"]["fixed"], res["runs"]["R4d"]["fixed"]
        res["R4_smaller_than_R3"] = dict(dx=bool(abs(r4["dx_focus_over_Lc"]) < abs(r3["dx_focus_over_Lc"])),
                                         dt=bool(abs(r4["dt_focus_over_Tc"]) < abs(r3["dt_focus_over_Tc"])))
    json.dump(res, open(os.path.join(OUT, "a3p_fix.json"), "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--")] or ["R1b", "R2", "R3", "R4d"])
