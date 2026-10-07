# -*- coding: utf-8 -*-
"""FLIP39 E：計算どうしの比べの表（table.json・table_ja.md）と比べの図（sheet_compare.png・sheet_curves.png）。py -3.10。
使い方: py -3.10 e_compare.py <run_id> ...   （Unity/Build/FLIP39/E/<run_id>/ の analysis_e.json・seat_e.json・render/ を読む）
"""
import sys, os, json, glob
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_plot import Sheet, Ax, PAL, font

E = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"


def g(d, *ks, default=None):
    for k in ks:
        if d is None or k not in d or d[k] is None:
            return default
        d = d[k]
    return d


def row_of(rid, label):
    rd = os.path.join(E, rid)
    an = json.load(open(os.path.join(rd, "analysis_e.json"), encoding="utf8"))
    se = json.load(open(os.path.join(rd, "seat_e.json"), encoding="utf8")) if os.path.exists(os.path.join(rd, "seat_e.json")) else {}
    rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    br = an.get("breaking") or {}
    ev = br.get("events", {}) if br else {}
    sh = br.get("shape_at_overturn", {}) if br else {}
    sh1 = br.get("shape_overturn_plus_1s", {}) if br else {}
    bs = se.get("best_seat") or {}
    ds = se.get("design_seat") or {}
    grp = an["group"]
    S = None
    try:
        cj = json.load(open(os.path.join(rd, "comp_c0001.json"), encoding="utf8"))
        sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
        from e_lin import kdisp
        S = float(np.sum(np.array(cj["a"]) * kdisp(np.array(cj["om"]), 60.0)))
    except Exception:
        pass
    # 育つ分の割合（終わりの 15 秒、仰角によらない）：乗る目の series の「頂が高くなる分」と「近づく分」（°/s）の正の部分の和の比
    gs15 = None
    sr = (bs.get("ride") or {}).get("series") if bs else None
    if sr and sr.get("t_group"):
        tt = np.array(sr["t_group"]); gr = np.clip(np.array(sr["grow"]), 0, None); ap = np.clip(np.array(sr["appr"]), 0, None)
        m = tt >= tt[-1] - 15.0
        gs15 = float(gr[m].sum() / max(gr[m].sum() + ap[m].sum(), 1e-9))
    # 立ち上がりの時間：頂の歩み（造波の帯の外で最も高い水面）で、最後に頂が「最終の 0.6 倍」を下回った時刻から、最終（垂直を過ぎた時、なければ最も高い時）まで
    ch = an["crest_history"]; tg_ = np.array(ch["t_group"]); cs_ = np.array(ch["crest_sim"])
    t_fin = (ev.get("face_past_vertical") or {}).get("t_group") or an["crest_max_any"]["t_group"]
    fin = float(an.get("m1_num_m") or an["crest_max_any"]["crest_m"])
    below = np.where((tg_ < t_fin) & (cs_ < 0.6 * fin))[0]
    rise06 = float(t_fin - tg_[below[-1]]) if below.size else None
    # 厳しい方の集中の比 m1s：最終の頂 ÷ 最終の 10 秒より前に水槽の中（造波の帯の外）で最も高かった頂（前を通った波の高さに対して、どれだけ高いか）
    xs_ = np.array(ch["x_sim"])
    early = tg_ < t_fin - 10.0
    early_max = float(cs_[early].max()) if early.any() else None
    early_x = float(xs_[early][np.argmax(cs_[early])]) if early.any() else None
    early_t = float(tg_[early][np.argmax(cs_[early])]) if early.any() else None
    m1s = fin / early_max if early_max else None
    # 同じ場所の比 m1p：最終の頂 ÷ 崩れる所（x_ov ± 30 m）を、主役の波が来る 6 秒より前に通った波の最も高い頂（座席の近くで前に見える波に対して）
    m1p = None; prev_local = None
    try:
        import e_analyze as EA
        from e_analyze import load_hf, focus_row
        EA.ROW_Z = an.get("row_z")
        rj_ = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
        hf_ = load_hf(rd); row_ = focus_row(hf_, rj_) - float(an.get("level_offset_m", 0.43))
        xg_ = hf_["grid"]["x0"] + hf_["grid"]["dx"] * np.arange(row_.shape[1]); tq = hf_["t"] + float(an["t_off"])
        xo = (ev.get("face_past_vertical") or {}).get("x") or an["crest_max_any"]["x"]
        win = (xg_ >= xo - 30) & (xg_ <= xo + 30)
        bef = tq < t_fin - 6.0
        prev_local = float(np.nanmax(row_[bef][:, win]))
        m1p = fin / prev_local
    except Exception as ex_:
        print("m1p error", rid, ex_)
    btype = "砕けない"
    if ev.get("breaking_onset_B085"):
        btype = "崩れ波（垂直を過ぎない）"
    if ev.get("face_past_vertical"):
        btype = "前の面が垂直を過ぎた（空洞は閉じない）"
    if br and br.get("plunging"):
        btype = "巻き波（空洞が閉じた）"
    vis = json.load(open(os.path.join(E, "visual_breaker.json"), encoding="utf8")) if os.path.exists(os.path.join(E, "visual_breaker.json")) else {}
    return dict(run_id=rid, label=label, breaker_visual=vis.get(rid, "—"), Lz=rj["parms"]["Lz"], t_off=an["t_off"], flat=an.get("flat"), sigma_deg=grp.get("sigma_deg", 0),
                A_f=grp.get("A_f"), S_lin=S, mound=float(rj["parms"].get("lg1_d", 0)) > 0,
                m1=an.get("m1"), m1_num_m=an.get("m1_num_m"), m1_den_m=g(an, "m1_den", "used_m"),
                crest_max_m=g(an, "crest_max_any", "crest_m"), lin_focus_m=g(an, "linear_focus", "crest_m"),
                t_onset=g(ev, "breaking_onset_B085", "t_group"), x_onset=g(ev, "breaking_onset_B085", "x"),
                t_overturn=g(ev, "face_past_vertical", "t_group"), x_overturn=g(ev, "face_past_vertical", "x"),
                t_tube=g(ev, "tube_closed_or_nearly", "t"), plunging=bool(br and br.get("plunging")), breaker=btype,
                crest_before_overturn_m=ev.get("crest_max_before_overturn_m"),
                chord_deg=g(sh1, "front_face_chord_angle_deg") or g(sh, "front_face_chord_angle_deg"),
                reach_Hc=g(sh1, "reach_over_Hc"), overhang_Hc=g(sh1, "overhang_over_Hc"), back_dx=g(sh1, "back_dx_to_075Hc_m"),
                rise_05=g(an, "rise", "s_from_0.5"), rise_07=g(an, "rise", "s_from_0.7"), rise06=rise06,
                t_final=float(t_fin), m1s=m1s, early_max_m=early_max, early_x=early_x, early_t=early_t, m1p=m1p, prev_local_m=prev_local,
                L80=g(se, "crest_line", "L80_m"), L50=g(se, "crest_line", "L50_m"),
                seat_x=bs.get("x_seat"), alpha=bs.get("alpha_max_before_wet"), hmd=bs.get("hmd_fill_max"), overhead=bs.get("lip_overhead_while_dry"),
                growth_share=bs.get("growth_share"), growth_share_15s=gs15, view_s=bs.get("view_s"), w80=bs.get("w80_at"),
                ride_end=(bs.get("ride") or {}).get("end_why"), fixed_alpha=(bs.get("fixed") or {}).get("alpha_max"),
                fixed_end_t=(bs.get("fixed") or {}).get("end_t_group"), chord_seat=(bs.get("ride") or {}).get("chord_at"),
                d_seat_x=ds.get("x_seat"), d_alpha=ds.get("alpha_max_before_wet"), d_overhead=ds.get("lip_overhead_while_dry"),
                wall_s=an.get("wall_total_s"), stopped=an.get("stopped"))


def fmt(v, p=2):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "はい" if v else "いいえ"
    if isinstance(v, (int, float)):
        return ("%." + str(p) + "f") % v
    return str(v)


def table(rows, out_md):
    cols = [("label", "計算", None), ("S_lin", "S（線形の険しさ）", 2), ("A_f", "線形の焦点の頂 (m)", 1), ("m1_den_m", "入口の最も高い頂 (m)", 1),
            ("m1_num_m", "砕ける時の頂 (m)", 1), ("m1", "m1 集中の比", 2), ("early_max_m", "最終の 10 秒より前の水槽の最も高い頂 (m)", 1), ("m1s", "m1s 前の波に対する比", 2), ("prev_local_m", "崩れる所を前に通った最も高い頂 (m)", 1), ("m1p", "m1p 同じ場所の前の波に対する比", 2), ("breaker", "崩れ方（自動の判定）", None), ("breaker_visual", "崩れ方（目で見た）", None), ("x_overturn", "垂直を過ぎた x (m)", 0),
            ("chord_deg", "前の面の弦 (°)", 0), ("reach_Hc", "唇の届き/Hc", 2), ("rise06", "頂が 0.6 倍→最終の時間 (s)", 1), ("L80", "峰の 0.8 倍以上の長さ (m)", 0),
            ("seat_x", "座席 x (m)", 0), ("alpha", "仰角の最大（乾いている間）(°)", 0), ("hmd", "前の窓の水", 2), ("overhead", "乾いたまま唇が頭上", None),
            ("growth_share", "育つ分の割合（仰角 10° 以上）", 2), ("growth_share_15s", "育つ分の割合（終わりの 15 秒）", 2)]
    L = ["| " + " | ".join(c[1] for c in cols) + " |", "|" + " --- |" * len(cols)]
    for r in rows:
        L.append("| " + " | ".join(fmt(r.get(c[0]), c[2] if c[2] is not None else 2) for c in cols) + " |")
    open(out_md, "w", encoding="utf8").write("\n".join(L) + "\n")


def sheet(rows, out_png):
    n = len(rows)
    W, Hrow = 3 * 480 + 360, 300
    sh = Sheet(W, 60 + n * Hrow, "FLIP39 E：仕組みごとの小さな実験（物理だけ：境界の造波と海底だけ。粘土の図は崩れの最中＝前の面が垂直を過ぎて 0.75 秒）")
    for i, r in enumerate(rows):
        y0 = 60 + i * Hrow
        rd = os.path.join(E, r["run_id"], "render")
        for j, k in enumerate(("seat", "oblique", "painting")):
            fs = sorted(glob.glob(os.path.join(rd, "still_%s_f*.png" % k)))
            if fs:
                im = Image.open(fs[0]).resize((480, 270))
                sh.im.paste(im, (j * 480, y0 + 24))
        sh.text((6, y0 + 2), "%s　座席の目／斜め／原画カメラ（雰囲気の参考）" % r["label"], 15, bold=True)
        x = 3 * 480 + 10
        lines = ["m1 %s（頂 %s m ÷ 入口 %s m）、m1s %s（÷ 前の最も高い頂 %s m）" % (fmt(r["m1"]), fmt(r["m1_num_m"], 1), fmt(r["m1_den_m"], 1), fmt(r["m1s"]), fmt(r["early_max_m"], 1)),
                 "崩れ方（目で見た）：%s" % r["breaker_visual"][:22],
                 "前の面の弦 %s°　唇の届き %s Hc" % (fmt(r["chord_deg"], 0), fmt(r["reach_Hc"])),
                 "立ち上がり（頂 0.6 倍→最終）：%s s" % fmt(r["rise06"], 1),
                 "峰の 0.8 倍以上の長さ：%s m" % (fmt(r["L80"], 0) if r["L80"] else "端なし（一方向）"),
                 "座席 x %s m：仰角 %s°（乾いている間）" % (fmt(r["seat_x"], 0), fmt(r["alpha"], 0)),
                 "前の窓の水 %s、唇が頭上 %s" % (fmt(r["hmd"]), fmt(r["overhead"])),
                 "育つ分の割合 %s" % fmt(r["growth_share"])]
        for k, s in enumerate(lines):
            sh.text((x, y0 + 30 + 30 * k), s, 15)
    sh.save(out_png)


def curves(rows, out_png):
    sh = Sheet(1500, 520, "頂の歩み（破線＝線形の見込み）と座席から見た仰角。横軸は最終（垂直を過ぎた時、なければ最も高い時）からの秒")
    ax = Ax(sh, (80, 90, 720, 460), (-45, 8), (0, 20), "最終からの時間 (s)", "頂 (m)", "頂の高さ", xticks=np.arange(-45, 9, 5), yticks=np.arange(0, 21, 4))
    ax2 = Ax(sh, (840, 90, 1480, 460), (-20, 4), (0, 90), "最終からの時間 (s)", "仰角 (°)", "座席の目（乗る目）から見た水の最も高い所の仰角（終わりまで）",
             xticks=np.arange(-20, 5, 4), yticks=np.arange(0, 91, 15))
    for i, r in enumerate(rows):
        an = json.load(open(os.path.join(E, r["run_id"], "analysis_e.json"), encoding="utf8"))
        ch = an["crest_history"]
        c = PAL[i % len(PAL)]
        tt = np.array(ch["t_group"]) - r["t_final"]
        ax.line(tt, ch["crest_sim"], col=c, label=r["label"])
        ax.line(tt, ch["crest_lin"], col=c, dash=True, w=1)
        sp = os.path.join(E, r["run_id"], "seat_e.json")
        if os.path.exists(sp):
            se = json.load(open(sp, encoding="utf8"))
            s_ = se.get("series_best")
            if s_:
                ax2.line(np.array(s_["t_group"]) - r["t_final"], s_["alpha"], col=c, label=r["label"])
    for a in (25, 55, 60):
        ax2.hline(a)
    ax.legend("tl"); ax2.legend("tl")
    sh.save(out_png)


if __name__ == "__main__":
    args = sys.argv[1:]
    pairs = [a.split("=", 1) if "=" in a else (a, a) for a in args]
    rows = [row_of(r, l) for r, l in pairs]
    json.dump(rows, open(os.path.join(E, "table.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    table(rows, os.path.join(E, "table_ja.md"))
    sheet(rows, os.path.join(E, "sheet_compare.png"))
    curves(rows, os.path.join(E, "sheet_curves.png"))
    print(open(os.path.join(E, "table_ja.md"), encoding="utf8").read())
