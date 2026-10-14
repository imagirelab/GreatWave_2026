# -*- coding: utf-8 -*-
"""FLIP48 R3：補いの読み（py -3.10 -B、numpy・scipy・scikit-image）。2026-10-15 新しく書いた。g48_peak_metrics.py が呼ぶ。
P1〜P5・H の判定（plan/plan_frozen.json の写し）には使わない。G0 の 2D の門（plan/plan_R3_frozen.json の G0.gate）だけがこの読みを使う。
読み方は Unity/Build/FLIP48/diag/D1_front_face/d1_shelf.py（level_stats・chord_variants）を写し、決まり（下の定数）は plan_R3_frozen.json に凍らせた：
  前の水の層（apron）  真ん中の行（hf の y 0.5 m の行）の一番上の水面 − 静かな水面のずれ を、頂 xc + 1.5 η_c〜xc + 3 η_c（x ≤ Lx − 10 m）で
                       平均し η_c で割った物（xc・η_c は ana.json の centre_track）。巻き始めのコマの値が「巻き始めの apron」【測定】
  前の水の層から測った弦  STUDY52 の measure_mask を、静かな水面の代わりに前の水の層の高さ ζ_a から測った物（D1 の chord_local）
  噴き出しの先の印      0.5 η_c の点が覆いの先と |x05 − hood_tip| ≤ 0.05 η_c で重なる（弦が噴き出しの先を測っている）【選び：D1 で R0 の
                       347〜351 コマは 0.02 以内、R1 の 365 コマは 0.024】
  0.1 η_c の点が体か噴き出しの面にある  そのコマの apron ≤ 0.05（前の水の層が 0.1 η_c より 0.05 η_c 以上低い）【選び：R0 の噴き出しの
                       コマ 0.025〜0.033、R1 の 365 コマ（層の上）0.097】
  噴き出しの落ち始め    巻き始め後、覆いが育ち（reach ≥ 0.3 η_c）、その下の端 hood_low_z が 0.45 η_c より下がった最初のコマ
                       【選び：R0 は 346、R1 は 363 コマ（D1 の分け方と同じ）。小さい覆いの間（R0 327 コマ reach 0.03）は数えない】
  体の弦               巻き始め〜噴き出しの落ち始めの前のコマの、静かな水面から測った弦の中央値（と前の水の層から測った弦の中央値・範囲）
  足・空洞・覆い        ana.json の形の表の「最も巻いた」コマの front_x01_rel・gap_max・reach（原画 0.25・0.54・0.59）
  棚の上の最小の水深    t ≥ 2 s〜巻き始めのコマ（なければ最後）の各コマで、真ん中の行の頂より前（x > xc、x ≤ Lx − 10 m）、静かな時の水深が棚の水深
                       以下の所の（一番上の水面 − ずれ）− 海底 の最小（水が無い列は 0 m）【測定】。β を変えた時の見込み：h_sh − (h_sh − d_min)·β'/β【選び：線形】
  c0/H0・溝の外の帯     c0（巻き始めの真ん中の頂、g48_peak_metrics の c(y)）÷ H0（= A h0、谷を足す前の Tanaka の頂）と、
                       c0 ÷ |y| 35〜48 m の頂の平均（x ≤ 340 m。P4a の横の帯 70〜84 m は溝の中なので、溝の外で比べる）
使い方：py -3.10 -B g48_supp.py <記録> [<記録> ...]（画面に出すだけ。書くのは g48_peak_metrics.py）
"""
import os, sys, json, math

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, _HERE)
import numpy as np                  # noqa: E402
import g48_common as GC             # noqa: E402

APRON_BAND = (1.5, 3.0)        # 頂の前の η_c の倍（D1）
X_END_PAD = 10.0               # 下流の壁の手前を除く（D1 は x ≤ 350 m）
JET_TIP_TOL = 0.05             # |x05 − hood_tip| ≤ これ（η_c の倍）で噴き出しの先【選び】
ON_FACE_APRON_MAX = 0.05       # そのコマの apron ≤ これで 0.1 η_c の点は体か噴き出しの面【選び】
JET_FALL_HOOD_LOW = 0.45       # 覆いの下の端がこれより下で噴き出しが落ち始めた【選び】
JET_FALL_REACH_MIN = 0.3       # ただし覆いの前への長さがこれ以上（育った覆い）【選び】
OUT_BAND = (35.0, 48.0)        # 溝の外の帯 |y|（m）【判定の queue】
T_SHELF_FROM = 2.0             # 棚の水深を読み始める時刻（s。初めの水面の格子のコマを除く）
DEFS = dict(apron_band_eta=list(APRON_BAND), x_end_pad_m=X_END_PAD, jet_tip_tol_eta=JET_TIP_TOL, on_face_apron_max=ON_FACE_APRON_MAX,
            jet_fall_hood_low_eta=JET_FALL_HOOD_LOW, jet_fall_reach_min_eta=JET_FALL_REACH_MIN, out_of_channel_band_m=list(OUT_BAND), shelf_depth_t_from_s=T_SHELF_FROM,
            shelf_depth_scaling="d_min(beta') = h_sh - (h_sh - d_min(beta)) * beta'/beta (linear in beta; guess)",
            tags=dict(apron="measured (D1 definition)", jet_tip_tol="chosen", on_face_apron_max="chosen", jet_fall_hood_low="chosen", jet_fall_reach_min="chosen",
                      out_band="chosen (judge queue)", shelf_depth="measured", scaling="guess"))


def _ctx(rd):
    import g48_analyze as A48
    return A48.Ctx48(rd, {})


def _track(ana):
    s = (ana.get("centre_track") or {}).get("series") or []
    return {int(r[0]): dict(t=float(r[1]), xc=float(r[2]), eta=float(r[3]), thmax=float(r[4]) if r[4] is not None else None) for r in s}


def _row(cx, f, row=0):
    e, m, t = cx.R1.get(f)
    xs = m["x0"] + m["dx"] * np.arange(e.shape[1])
    ys = m["z0"] + m["dz"] * np.arange(e.shape[0])
    return xs, np.asarray(e[row], float) - cx.off, t, float(ys[row])


def apron_level(xs, eta, xc, ec, x_hi):
    """頂の前 xc + 1.5 η_c〜xc + 3 η_c（x ≤ x_hi）の水面の平均（m、静かな水面から）。"""
    s = (xs >= xc + APRON_BAND[0] * ec) & (xs <= xc + APRON_BAND[1] * ec) & (xs <= x_hi)
    v = eta[s]
    return float(np.nanmean(v)) if s.any() and np.isfinite(v).any() else None


def chord_rows(cx, ana, tr, x_hi):
    """ana.json の形の量のコマ（巻き始め〜着水、なければ + 2 s）で、静かな水面と前の水の層から測った弦・噴き出しの先の印・0.1 η_c の点の位置。"""
    import g46_analyze as A46
    S52 = A46.S52
    sh = [r for r in ((ana.get("shape") or {}).get("series") or []) if "error" not in r]
    on = ana.get("onset") or {}
    xg = on.get("xc")
    rows = []
    for r0 in sh:
        f = int(r0["frame"])
        if f in tr:
            xg = tr[f]["xc"]
        row = dict(frame=f)
        try:
            xs, eta, t, _ = _row(cx, f)
            ec = tr[f]["eta"] if f in tr else float(on.get("eta_c"))
            xcl = tr[f]["xc"] if f in tr else xg
            za = apron_level(xs, eta, xcl, ec, x_hi)
            M, X, Z, t = A46.r2_mask(cx, f, xg)
            m0 = S52.measure_mask(M, X, Z, flip_extra=dict(Lc=cx.Lc))
            e0 = m0["eta_c"]
            row.update(t=float(t), eta_c=e0, chord_swl=m0["face_chord_deg_01_05"], x01=m0["front_x01_rel"], x05=m0["front_x05_rel"],
                       hood=bool(m0.get("hood")), hood_tip=m0.get("hood_tip_x_rel"), hood_wall=m0.get("hood_wall_x_rel"), hood_low_z=m0.get("hood_low_z"),
                       lip=m0.get("lip_thick_mid"), area=m0.get("hood_area"), gap_max=m0.get("gap_max"), reach=m0.get("reach"),
                       chord_ana=r0.get("face_chord_deg_01_05"), zeta_a_m=za, apron=(za / ec) if (za is not None and ec) else None)
            if za is not None:
                m1 = S52.measure_mask(M, X, Z - za, flip_extra=dict(Lc=cx.Lc))
                row.update(chord_local=m1["face_chord_deg_01_05"], x01_local=m1["front_x01_rel"], x05_local=m1["front_x05_rel"])
            ht = row["hood_tip"]
            row["jet_tip"] = bool(row["hood"] and ht is not None and abs(row["x05"] - ht) <= JET_TIP_TOL)
            row["on_face_01"] = bool(row["apron"] is not None and row["apron"] <= ON_FACE_APRON_MAX)
        except Exception as e:
            row["error"] = repr(e)[:200]
        rows.append(row)
    return rows


def body_face(rows, f_on):
    """噴き出しの落ち始めの前（巻き始め〜）の体の弦。"""
    ok = [r for r in rows if "error" not in r and r["frame"] >= f_on]
    if not ok:
        return dict(note_ja="形の量のコマがない")
    f_jet = None
    for r in ok:
        if r["hood"] and r.get("hood_low_z") is not None and r["hood_low_z"] < JET_FALL_HOOD_LOW and (r.get("reach") or 0.0) >= JET_FALL_REACH_MIN:
            f_jet = r["frame"]; break
    body = [r for r in ok if f_jet is None or r["frame"] < f_jet]
    if not body:
        return dict(jet_fall_frame=f_jet, note_ja="巻き始めのコマで噴き出しがもう落ちている")
    cs = np.array([r["chord_swl"] for r in body]); cl = np.array([r["chord_local"] for r in body if r.get("chord_local") is not None])
    return dict(jet_fall_frame=f_jet, frames=[body[0]["frame"], body[-1]["frame"]], n=len(body),
                chord_swl_median_deg=float(np.median(cs)), chord_swl_range_deg=[float(cs.min()), float(cs.max())],
                chord_local_median_deg=float(np.median(cl)) if len(cl) else None, chord_local_range_deg=[float(cl.min()), float(cl.max())] if len(cl) else None)


def min_shelf_depth(cx, ana, tr, spec, x_hi, f_end=None):
    """棚の上・頂より前の最小の水深（真ん中の行）。返り値 dict（最小・コマ・x・時系列の抜き）。"""
    shelf = float(spec["shelf_h"])
    on = ana.get("onset") or {}
    f_last = int(on["frame"]) if on.get("frame") else (f_end or max(cx.R1.frames))
    best = None
    ser = []
    for f in cx.R1.frames:
        if f > f_last:
            break
        xs, eta, t, y_row = _row(cx, f)
        if t < T_SHELF_FROM - 1e-9:
            continue
        bed = GC.bed_z(xs, y_row, **spec)
        on_shelf = (-bed <= shelf + 1e-6) & (xs <= x_hi)
        if f in tr:
            xc = tr[f]["xc"]
        else:
            sel = (xs >= 150.0) & (xs <= x_hi)
            e_ = np.where(np.isfinite(eta[sel]), eta[sel], -1e9)
            xc = float(xs[sel][int(np.argmax(e_))])
        m = on_shelf & (xs > xc)
        if not m.any():
            continue
        dep = np.where(np.isfinite(eta[m]), eta[m] - bed[m], 0.0)
        i = int(np.argmin(dep))
        v = float(dep[i])
        if (f - 1) % 6 == 0:
            ser.append([int(f), round(float(t), 3), round(float(xc), 1), round(v, 3), round(float(xs[m][i]), 1)])
        if best is None or v < best["min_depth_m"]:
            best = dict(min_depth_m=v, frame=int(f), t=float(t), x=float(xs[m][i]), x_crest=float(xc), y_row=y_row)
    out = dict(best or dict(min_depth_m=None), shelf_h=shelf, frames_to=f_last, t_from=T_SHELF_FROM, series_every6=ser,
               rule_ja="t ≥ %g s〜巻き始めのコマ、真ん中の行（y %.2f m）、頂より前（x > xc、x ≤ %g m）の静かな時の水深 ≤ 棚 %g m の所の（一番上の水面 − ずれ）− 海底 の最小"
                       "（水が無い列は 0 m）" % (T_SHELF_FROM, best["y_row"] if best else 0.5, x_hi, shelf))
    return out


def scaled_min_depth(d_min, beta_from, beta_to, shelf_h=GC.SHELF_H):
    """β を変えた時の最小の水深の見込み（線形：下がり（h_sh − d_min）が β に比例）【選び】。"""
    if d_min is None or not beta_from:
        return None
    return shelf_h - (shelf_h - d_min) * beta_to / beta_from


def supp(rd, ana=None, cfg=None):
    """1 本の記録の補いの読み（apron・前の層から測った弦・噴き出しの先の印・体の弦・足/空洞/覆い・棚の上の最小の水深）。書かない。"""
    rd = os.path.abspath(rd).replace("\\", "/")
    ana = ana or json.load(open(os.path.join(rd, "ana.json"), encoding="utf8"))
    cfg = cfg or json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    cx = _ctx(rd)
    tr = _track(ana)
    spec = GC.bed_spec(cfg)
    x_hi = cx.x_max - X_END_PAD
    on = ana.get("onset") or {}
    out = dict(run_id=cfg.get("run_id"), defs=DEFS, still_offset_m=cx.off, x_hi_m=x_hi, wave=cfg.get("wave"), bed_kind=GC.bed_kind(spec))
    if on.get("frame"):
        f_on = int(on["frame"])
        xs, eta, t, _ = _row(cx, f_on)
        ec = tr[f_on]["eta"] if f_on in tr else float(on["eta_c"])
        xc = tr[f_on]["xc"] if f_on in tr else float(on["xc"])
        za = apron_level(xs, eta, xc, ec, x_hi)
        out["onset_apron"] = dict(frame=f_on, t=float(t), xc=xc, eta_c=ec, level_m=za, apron=(za / ec) if za is not None else None)
        rows = chord_rows(cx, ana, tr, x_hi)
        out["chords"] = rows
        ok = [r for r in rows if "error" not in r]
        if ok:
            im = int(np.argmax([r["chord_swl"] for r in ok]))
            rm = ok[im]
            out["frozen_chord_max"] = dict(frame=rm["frame"], chord_deg=rm["chord_swl"], jet_tip=rm["jet_tip"], on_face_01=rm["on_face_01"],
                                           apron=rm["apron"], chord_local_deg=rm.get("chord_local"), x01=rm["x01"], x05=rm["x05"], hood_tip=rm["hood_tip"])
            over = [r for r in ok if r["chord_swl"] >= 55.0]
            out["frames_chord_ge55"] = [dict(frame=r["frame"], chord=round(r["chord_swl"], 1), jet_tip=r["jet_tip"], on_face_01=r["on_face_01"],
                                             apron=None if r["apron"] is None else round(r["apron"], 3)) for r in over]
            out["chord55_with_01_on_face"] = bool(any(r["on_face_01"] for r in over))
            out["chord55_only_on_jet_tip"] = bool(over and all(r["jet_tip"] for r in over))
            cl = [r["chord_local"] for r in ok if r.get("chord_local") is not None]
            out["chord_local_max_deg"] = float(max(cl)) if cl else None
            out["chord_ana_max_abs_diff_deg"] = float(max(abs(r["chord_swl"] - r["chord_ana"]) for r in ok if r.get("chord_ana") is not None)) \
                if any(r.get("chord_ana") is not None for r in ok) else None
        out["body_face"] = body_face(rows, f_on)
    else:
        out["note_ja"] = "巻き始めがない（弦・apron は読まない）"
    tab = (ana.get("shape") or {}).get("table") or {}
    if tab:
        g = lambda k, w="max_overturn": (tab.get(k) or {}).get(w)
        out["print_ruler"] = dict(frame=((ana.get("shape") or {}).get("frames") or {}).get("max_overturn"),
                                  Hc_m=on.get("eta_c"), foot=g("front_x01_rel"), cavity=g("gap_max"), hood=g("reach"),
                                  lip_at_max_overturn=g("lip_thick_mid"), area_at_max_overturn=g("hood_area"),
                                  chord_at_max_overturn=g("face_chord_deg_01_05"),
                                  print=dict(foot=g("front_x01_rel", "print_cn"), cavity=g("gap_max", "print_cn"), hood=g("reach", "print_cn"),
                                             chord=g("face_chord_deg_01_05", "print_cn")),
                                  rule_ja="ana.json の形の表の「最も巻いた」コマ（覆いの高さが最大）：足 = front_x01_rel、空洞 = gap_max、覆い = reach（÷ η_c）")
    out["shelf_depth"] = min_shelf_depth(cx, ana, tr, spec, x_hi)
    w = cfg.get("wave") or {}
    if w.get("kind") == "nwave" and out["shelf_depth"].get("min_depth_m") is not None:
        b = float(w["beta"])
        out["shelf_depth"]["scaled_to"] = {("%g" % b2): scaled_min_depth(out["shelf_depth"]["min_depth_m"], b, b2) for b2 in (0.06, 0.09, 0.12, 0.15, 0.18)}
    return out


def lateral_extra(c, cs, ys, H0, band=OUT_BAND, Hc=None):
    """c(y)（x ≤ Lx − 15 m）と cs(y)（x ≤ 340 m）から、c0/H0 と c0 ÷ 溝の外の帯 |y| 35〜48 m の平均。"""
    c = np.asarray(c, float); cs = np.asarray(cs, float); ys = np.asarray(ys, float)
    c0 = float(np.nanmean(c[ys < 1.0])) if (ys < 1.0).any() else float(c[0])
    out = dict(c0=c0, H0=H0, c0_over_H0=(c0 / H0) if H0 else None, Hc_over_H0=(Hc / H0) if (Hc and H0) else None, out_band=list(band))
    bm = (ys >= band[0]) & (ys <= band[1])
    if bm.any() and np.isfinite(cs[bm]).any():
        v = float(np.nanmean(cs[bm]))
        out.update(c_out=v, c0_over_c_out=(c0 / v) if v > 0 else None)
    else:
        out.update(c_out=None, c0_over_c_out=None, note_ja="帯 |y| %g〜%g m が箱の外（板）" % band)
    return out


# ------------------------------------------------------------------ G0 の門（plan_R3_frozen.json の G0.gate）
def load_frozen_r3():
    p = GC.B48 + "/plan/plan_R3_frozen.json"
    if not os.path.exists(p):
        return None, p
    return json.load(open(p, encoding="utf8")), p


def g0_gate(res, sup, frz):
    """G0 の 2D の門の各々（はい/いいえ）と、G0c の「正」の決まり。決まりの当てはめ（次に何を走らせるか）は主の会話がする。"""
    G = frz["G0"]["gate"]; Pc = frz["G0"]["g0c_positive"]
    J = res.get("judge") or {}
    on = res.get("onset") or {}
    sw = res.get("shape_window") or {}
    sd = (sup.get("shelf_depth") or {}).get("min_depth_m")
    ap = (sup.get("onset_apron") or {}).get("apron")
    it = dict(
        H_bed_leak=bool(J.get("H_bed_leak")), H_init_f2=bool(J.get("H_init_f2")), H_still_offset=bool(J.get("H_still_offset")), H_volume=bool(J.get("H_volume")),
        onset_x=bool(on and G["onset_x_m"][0] <= on["xc"] <= G["onset_x_m"][1]), onset_t=bool(on and on["t"] <= G["onset_t_max_s"]),
        apron=bool(ap is not None and ap <= G["apron_onset_max"]),
        lip=bool((sw.get("lip_max") or 0.0) >= G["lip_min"]), area=bool((sw.get("hood_max") or 0.0) >= G["area_min"]),
        chord55_01_on_face=bool(sw.get("chord_max") is not None and sw["chord_max"] >= G["frozen_chord_min_deg"] and sup.get("chord55_with_01_on_face")),
        shelf_depth=bool(sd is not None and sd >= G["shelf_depth_ahead_min_m"]))
    H_ok = all(it[k] for k in ("H_bed_leak", "H_init_f2", "H_still_offset", "H_volume"))
    fails = [k for k, v in it.items() if not v]
    bf = sup.get("body_face") or {}
    pr = sup.get("print_ruler") or {}
    r0b = (frz["G0"].get("reference_R0") or {}).get("body_chord_swl_median_deg")
    body_gain = (bf.get("chord_swl_median_deg") - r0b) if (bf.get("chord_swl_median_deg") is not None and r0b is not None) else None
    pos = dict(onset=bool(on and on["xc"] <= Pc["onset_x_max_m"]),
               body_or_foot=bool((body_gain is not None and body_gain >= Pc["body_chord_gain_deg"]) or (pr.get("foot") is not None and pr["foot"] <= Pc["foot_max"])),
               chord55=bool(sw.get("chord_max") is not None and sw["chord_max"] >= Pc["frozen_chord_min_deg"]),
               lip=bool((sw.get("lip_max") or 0.0) >= Pc["lip_min"]), area=bool((sw.get("hood_max") or 0.0) >= Pc["area_min"]))
    return dict(items=it, H_ok=H_ok, gate_pass=bool(all(it.values())), fails=fails,
                values=dict(onset_x=on.get("xc") if on else None, onset_t=on.get("t") if on else None, apron=ap, lip_max=sw.get("lip_max"),
                            area_max=sw.get("hood_max"), chord_max=sw.get("chord_max"), shelf_depth_min_m=sd,
                            body_chord_swl_median_deg=bf.get("chord_swl_median_deg"), body_gain_vs_R0_deg=body_gain, foot=pr.get("foot")),
                g0c_positive_items=pos, g0c_positive=bool(all(pos.values())),
                body_10deg_above_R0=bool(body_gain is not None and body_gain >= 10.0),
                note_ja="門の各々の判定だけ。次に何を走らせるか（G0 の decision_after の 1〜6）は plan_R3_frozen.json の決まりで主の会話が決める。"
                        "G0c の「正」は G0c の記録の時だけ意味がある")


def _n(v, f="%.2f"):
    return "—" if v is None else (f % v)


def md(sup, lat=None, gate=None, queue_id=None):
    """PEAK_ja.md に足す節（日本語）。"""
    L = ["", "## 補いの読み（判定に使わない。g48_supp.py、決まりは plan/plan_R3_frozen.json）", ""]
    oa = sup.get("onset_apron") or {}
    if oa:
        L.append("- 巻き始めの前の水の層（apron、頂の前 1.5〜3 η_c の水面の平均 ÷ η_c）：%s（%s m、コマ %s）【測定】。R0 は 0.068。" % (
            _n(oa.get("apron"), "%.3f"), _n(oa.get("level_m"), "%.2f"), oa.get("frame")))
    fc = sup.get("frozen_chord_max") or {}
    if fc:
        L.append("- 凍らせた弦の最大 %s°（コマ %s）：噴き出しの先の印 %s、0.1 η_c の点が体か噴き出しの面 %s（そのコマの apron %s）、前の層から測った弦 %s°。"
                 % (_n(fc.get("chord_deg"), "%.1f"), fc.get("frame"), "はい" if fc.get("jet_tip") else "いいえ", "はい" if fc.get("on_face_01") else "いいえ",
                    _n(fc.get("apron"), "%.3f"), _n(fc.get("chord_local_deg"), "%.1f")))
        g55 = sup.get("frames_chord_ge55") or []
        L.append("- 弦 ≥ 55° のコマ：%s。%s" % ("、".join("%d（%.1f°%s%s）" % (r["frame"], r["chord"], "・先" if r["jet_tip"] else "", "・面" if r["on_face_01"] else "・層")
                                                     for r in g55) or "なし",
                                             "55° を越えたのは噴き出しの先だけ。" if sup.get("chord55_only_on_jet_tip") else ""))
        L.append("- 前の層から測った弦の最大 %s°。" % _n(sup.get("chord_local_max_deg"), "%.1f"))
    bf = sup.get("body_face") or {}
    if bf.get("chord_swl_median_deg") is not None:
        L.append("- 体の弦（巻き始め〜噴き出しの落ち始めの前、コマ %s〜%s。落ち始め %s）：静かな水面から 中央値 %.1f°（%.1f〜%.1f°）、前の層から 中央値 %s°（%s）。"
                 % (bf["frames"][0], bf["frames"][1], bf.get("jet_fall_frame"), bf["chord_swl_median_deg"], bf["chord_swl_range_deg"][0], bf["chord_swl_range_deg"][1],
                    _n(bf.get("chord_local_median_deg"), "%.1f"), "〜".join("%.1f" % v for v in (bf.get("chord_local_range_deg") or []))))
    pr = sup.get("print_ruler") or {}
    if pr:
        p_ = pr.get("print") or {}
        L.append("- 原画の物差し（最も巻いたコマ %s）：足 %s（原画 %s）、空洞 %s（%s）、覆い %s（%s）、Hc %s m。" % (
            pr.get("frame"), _n(pr.get("foot")), _n(p_.get("foot")), _n(pr.get("cavity")), _n(p_.get("cavity")), _n(pr.get("hood")), _n(p_.get("hood")),
            _n(pr.get("Hc_m"))))
    sd = sup.get("shelf_depth") or {}
    if sd.get("min_depth_m") is not None:
        L.append("- 棚の上・頂より前の最小の水深 %.2f m（コマ %s、t %.2f s、x %.1f m、頂 x %.1f m）【測定】。%s" % (
            sd["min_depth_m"], sd["frame"], sd["t"], sd["x"], sd["x_crest"],
            ("β を変えた時の見込み【選び：線形】：%s" % "、".join("β %s → %.2f m" % (k, v) for k, v in sd["scaled_to"].items())) if sd.get("scaled_to") else ""))
    if lat:
        L.append("- c0/H0 %s（c0 %s m、H0 = A h0 %s m、谷を足す前の Tanaka の頂）。c0 ÷ 溝の外の帯 |y| %g〜%g m の頂 %s（%s m）%s。" % (
            _n(lat.get("c0_over_H0"), "%.3f"), _n(lat.get("c0")), _n(lat.get("H0")), lat["out_band"][0], lat["out_band"][1], _n(lat.get("c0_over_c_out"), "%.3f"),
            _n(lat.get("c_out")), "" if lat.get("c_out") is not None else "（%s）" % lat.get("note_ja", "")))
        if lat.get("P4a_side_band_in_channel"):
            L.append("  P4a の横の帯 |y| 70〜84 m は溝の中（P4a の上がりの約半分は横の頂が低い分【計算、判定の注】）。溝の外の比は上の c0 ÷ 帯の値と P4b を見る。")
    if gate:
        it = gate["items"]; v = gate["values"]
        L += ["", "### G0 の門（plan_R3_frozen.json の G0.gate。%s）" % (queue_id or "—"), ""]
        lab = dict(H_bed_leak="H 海底より下の粒子", H_init_f2="H 2 コマ目の確かめ", H_still_offset="H 静かな水面のずれ < 0.1 m", H_volume="H 水の量のずれ",
                   onset_x="巻き始め x 273〜305 m", onset_t="巻き始め t ≤ 13.5 s", apron="apron ≤ 0.03", lip="唇 ≥ 0.25", area="巻いた面積 ≥ 0.12",
                   chord55_01_on_face="弦 ≥ 55°（0.1 η_c の点が体か噴き出しの面）", shelf_depth="棚の上の最小の水深 ≥ 0.5 m")
        for k, ok in it.items():
            L.append("- %s：%s" % (lab.get(k, k), "はい" if ok else "いいえ"))
        L.append("")
        L.append("門：%s（外れ：%s）。値：巻き始め x %s m・t %s s、apron %s、唇 %s、面積 %s、弦の最大 %s°、最小の水深 %s m、体の弦 %s°（R0 との差 %s°）、足 %s。" % (
            "通る" if gate["gate_pass"] else "通らない", "・".join(gate["fails"]) or "なし", _n(v["onset_x"], "%.1f"), _n(v["onset_t"], "%.2f"), _n(v["apron"], "%.3f"),
            _n(v["lip_max"], "%.3f"), _n(v["area_max"], "%.3f"), _n(v["chord_max"], "%.1f"), _n(v["shelf_depth_min_m"], "%.2f"),
            _n(v["body_chord_swl_median_deg"], "%.1f"), _n(v["body_gain_vs_R0_deg"], "%+.1f"), _n(v["foot"])))
        if not gate["body_10deg_above_R0"]:
            L.append("体の弦が R0 より 10° 以上は立っていない：P5 は噴き出しの先だけで通るかもしれず、前の面は原画の帯（60.5〜78°）に届かない。")
        if (queue_id or "").startswith("G0c"):
            L.append("G0c の「正」の決まり：%s（%s）。" % ("正" if gate["g0c_positive"] else "負", gate["g0c_positive_items"]))
        L.append("次に走らせる物は plan_R3_frozen.json の G0 の決まり（1〜6）で主の会話が決める。")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for rd in sys.argv[1:]:
        s = supp(rd)
        s.pop("chords", None)
        print(json.dumps(s, ensure_ascii=False, indent=1, default=float)[:6000])
