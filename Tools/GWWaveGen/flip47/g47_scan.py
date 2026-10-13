# -*- coding: utf-8 -*-
"""FLIP47：海底を変える 2D の組（targets_ja.md §4 の S1〜S6、粒子 0.25 m）の設定を作り、読み、並べる（py -3.10 -B）。
2026-10-12 海底の組を走らせる役（Claude）が書いた。読むだけの物：targets.json（文献と組の案の役）、g47_cfg.py・g47_common.py・
g47_solitary_npz.py（場面の役）、g47_analyze.py（読みと図の役。変えずに読み込み、記録の読み方だけをこの中で差し替える）。
書くのは Unity/Build/FLIP47 の中だけ。

使い方：
  py -3.10 -B g47_scan.py cfg <組の id> [--reseed 0|1] [--name <run_id>] [--allz 1]   → runs/ready/<run_id>.json（と孤立波の npz）
      --veltransfer flip（2026-10-13 足した。既定 apic は前と同じ。推奨は flip：APIC は板の −z の壁の側へ偽の横流れを作り、層で噴流と空洞が
      2 倍違う。record_ja.md「2D の板の層の差の元を分けて直した」）→ runs/ready/<組>_dp0p25_flip.json
  py -3.10 -B g47_scan.py ana <run_id> [--nofig]                                      → runs/<run_id>/ana47（真ん中に近い層 iz 1、E1a と同じ）・
                                                                                         ana47_zmean（4 層の平均の場）・ana47_z0〜z3（層ごと、図なし）
  py -3.10 -B g47_scan.py table <run_id> ...                                          → runs/SCAN_compare/scan_table.json・scan_table.md
組の id は targets.json の scan[].id（S1_E1a・S2_s1-10・S3_s1-14.4・S4_s1-20・S5_ledge1-7・S6_twostep）。

判定の決まり（2026-10-12、走らせる前に凍結。record_ja.md の「海底の組の役」の節と同じ）：
  主の点数 score3：原画の帯の外れ（g47_targets.score と同じ 1 つの式。原画 cn の値で割り 1 で頭打ち）を、前の面の弦・前の足・覆いの面積の
    3 つだけ足す（0〜3）。唇の下の空気・唇の厚みは、E1a で FLIP 0.25 m の偏りが大きい（論文の図 5b に対し空気 −35 %、唇 +53 %、1 つの海底だけで
    測った値）ので点数から外し、生の値と偏りを割り戻した値（空気 ÷ 0.644、唇 ÷ 1.534）を別に書く。
  コマ：巻き始め〜最初に触れたコマの全部で score3 が最小のコマ（同じなら覆いの高い方）。着水のコマの score3 も必ず並べる。
  組の順位：最小のコマの score3、同じなら着水のコマの score3。参考に、もとの 5 つの点数（targets_ja.md §5）と、空気・唇を割り戻した 5 つの点数も出す。
  層：主の値は板の真ん中に近い層（iz 1、z = −0.25 m。E1a と同じ）。4 層の平均の場と、層ごとの値の幅（最小〜最大）を並べる。
"""
import os, sys, json, math, glob, time, argparse, copy
sys.dont_write_bytecode = True
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC
import g47_solitary_npz as SN

B47 = GC.B47
TARGETS = B47 + "/targets.json"
CMP = B47 + "/runs/SCAN_compare"

V_TD = 18.9            # E1a 短い領域：頂 475 m → 着水の所 797 m を 17.04 s（平均 18.9 m/s）【測った】。着水の時刻の目安に使う
AIR_BIAS = 0.308 / 0.478      # E1a_full_dp0p25 の着水（0.308）÷ 論文の図 5b を同じ物差しで（0.478）
LIP_BIAS = 0.316 / 0.206      # 同じく唇の厚み
SCORE3_KEYS = ["face_chord_deg_01_05", "front_x01_rel", "hood_area"]


def scan_entry(sid):
    t = json.load(open(TARGETS, encoding="utf8"))
    for s in t["scan"]:
        if s["id"] == sid:
            return s
    raise SystemExit("targets.json に組 %s がない" % sid)


def sol_npz(a_over_h, crest, x0, x1):
    p = GC.SOL_DIR + "/gn_a%.2f_h%g_x%g_d0.25_X%g-%g.npz" % (a_over_h, GC.H0, crest, x0, x1)
    if not os.path.exists(p):
        SN.build("gn", a_over_h, GC.H0, crest, x0, x1, dx=0.25, dz=0.25, out=p)
    return p


def make_cfg(sid, run_id=None, reseed=1, dp=0.25, allz=True, veltransfer="apic"):
    s = scan_entry(sid)
    GC.check_dp(dp)
    bed = GC.bed_points(s["bed"])
    x0, x1 = float(s["domain"][0]), float(s["domain"][1])
    crest = float(s["crest"]); a_over_h = float(s["a_over_h"])
    b = GC.box(dp, x0, x1, bed, floor_pad=2)
    C, _ = GC.gn_params(a_over_h * GC.H0, GC.H0)
    C06, _ = GC.gn_params(0.6 * GC.H0, GC.H0)
    x_imp = float(s["predicted"]["x_impact_over_h0"]) * GC.H0
    t_td = (x_imp - crest) / (V_TD * C / C06)
    t_from = max(3.0, t_td - 9.0)
    t_end = float(math.ceil(t_td + 8.0))
    f_end = GC.frames_for(t_end)
    tag = repr(float(dp)).replace(".", "p")
    rid = run_id or "%s_dp%s%s%s" % (sid, tag, "" if int(reseed) else "_noreseed", "" if veltransfer == "apic" else "_" + veltransfer)
    parms = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], Lz=b["Lz"], y_floor=b["y_floor"], Hy=b["Hy"], h0=GC.H0,
                 hmax=b["hmax"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0, ox=b["ox"], oy=b["oy"], oz=b["oz"],
                 bed_gap=0.5, floor_pad=2.0, wave_on=1.0, relax_on=0.0, abs_on=0.0, xa0=1e9)
    solver = dict(veltransfer="apic", donarrowband=0)
    if veltransfer != "apic":      # 2026-10-13 板の層の差を調べる役：FLIP の受け渡し（推奨。GC.VELTRANSFER_RECOMMENDED）。Velocity Smoothing は既定 0.1 を書いて固定
        solver.update(GC.solver_for(veltransfer))
    if not int(reseed):
        solver["reseed"] = 0
    sp = sol_npz(a_over_h, crest, b["x0"], b["x1"])
    return dict(
        run_id=rid, out_root="runs", stage="FLIP47", kind="scan", scan_id=sid, domain="scan",
        case=dict(name="FLIP47 scan %s" % sid, name_ja=s.get("name_ja"), plan="Unity/Build/FLIP47/targets_ja.md §4", targets_scan=s,
                  t_touchdown_estimate_s=round(t_td, 2), x_impact_predicted_m=x_imp,
                  timing_note_ja="着水の目安 = (予測の着水の x − 頂) ÷ (18.9 m/s × C/C(0.6))（E1a 短い領域の平均の速さ）。"
                                 "着水の読みは目安の 9 s 前から、終わりは目安 + 8 s。計算の中の着水の読みが先に止める"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=t_end, parms=parms, box=b, bed=bed,
        solitary_npz=sp, solitary=dict(kind="gn", a_over_h=a_over_h, h0=GC.H0, x0=crest, c_gn=C),
        solver=solver,
        sec=dict(x0=b["x0"], x1=b["x1"], t0=0.0, block=120, allz=bool(allz)),
        stop_touchdown=dict(after_s=2.5, tip_wait_s=2.5, tip_on=True, t_from=round(t_from, 2), Lc=60.0),
        n1_x=[crest + 180.0, b["x1"] - 20.0], n1_window=[0.5, 1.5],
        init_check_frames=[1, 2, 3], init_check_dx=[-20.0, 0.0, 20.0], init_check_y=[-2.0, -9.5, -17.0],
        pstats_frames=[1, 2, int(f_end)], fieldbox_frames=[2], leak_every=24,
        ckpt_on=1, ckpt_every=120, ckpt_list=[240, 120, 48, 24], wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0,
        max_hours=1.0, wait_hython_max_s=1800,
        note="FLIP47 海底の組 %s（%s）、粒子 %g m、GN a0/h0 %g、頂 %g m、領域 %g〜%g m、reseed %s、板の 4 層の断面も記録" % (
            sid, s.get("name_ja"), dp, a_over_h, crest, b["x0"], b["x1"], "既定（あり）" if int(reseed) else "0（なし）"))


# ====================================================================== 読み（g47_analyze を層を選んで）
def _ga():
    import g47_analyze as GA
    return GA


def patch_rec(GA, zsel):
    """g47_analyze.Rec.get を差し替える：zsel が None なら元のまま（sdf＝iz 1）、'mean' なら 4 層の平均、整数なら sdfz のその層。"""
    orig = GA.Rec.get if not hasattr(GA.Rec, "_orig_get") else GA.Rec._orig_get
    GA.Rec._orig_get = orig
    if zsel is None:
        GA.Rec.get = orig
        return

    def get(self, f):
        f0, p, i, _, _ = self.best[f]
        key = (p, "z")
        if getattr(self, "_pz", None) != key:
            d = np.load(p)
            self._dz = d["sdfz"] if "sdfz" in d.files else None
            self._d1 = d["sdf"]
            self._pz = key
        if self._dz is None:
            raise GA.InputError("sdfz がない（板の層ごとの記録がない）：%s" % p)
        a = self._dz[i].astype(np.float32)
        return a.mean(axis=0) if zsel == "mean" else a[int(zsel)]
    GA.Rec.get = get


def run_ana(rd, out, zsel, nofig=False, label=""):
    GA = _ga()
    patch_rec(GA, zsel)
    opt = dict(out=out, label=label)
    if nofig:
        opt["nofig"] = True
    cx = GA.Ctx(rd, opt)
    res, masks = GA.analyze(cx, opt)
    os.makedirs(out, exist_ok=True)
    res["zsel"] = zsel if zsel is not None else "sdf (iz 1, z -0.25 m)"
    res["out"] = out
    figs = {}
    nm = cx.name + ("" if zsel is None else "_z%s" % zsel)
    if not nofig:
        figs["section_zoom"] = GA.zoom_figure(cx, res, masks, os.path.join(out, "%s_section_zoom.png" % nm), label)
        if masks:
            figs["print_overlay"] = GA.overlay_figure(cx, res, masks, os.path.join(out, "%s_print_overlay.png" % nm), label)
    res["figures"] = figs
    if masks:
        np.savez_compressed(os.path.join(out, "%s_masks.npz" % nm),
                            **{"%s_%s" % (k, kk): v for k, mk in masks.items() for kk, v in (("M", mk["M"]), ("X", mk["X"]), ("Z", mk["Z"]))})
    json.dump(GA.clean(res), open(os.path.join(out, "g47_ana.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    patch_rec(GA, None)
    return res


def _bands():
    import g47_targets as TG
    GA = _ga()
    return TG, TG.print_bands(json.load(open(GA.STUDY52 + "/shape_measures.json", encoding="utf8")))


def scores(s52, TG, bands):
    """score3（弦・足・覆い）、もとの 5 つの点数、空気・唇を E1a の偏りで割り戻した 5 つの点数。"""
    if not s52:
        return None
    tot, parts = TG.score(s52, bands)
    adj = dict(s52)
    if adj.get("gap_max") is not None:
        adj["gap_max"] = adj["gap_max"] / AIR_BIAS
    if adj.get("lip_thick_mid") is not None:
        adj["lip_thick_mid"] = adj["lip_thick_mid"] / LIP_BIAS
    tot_adj, parts_adj = TG.score(adj, bands)
    s3 = sum(parts[k] for k in SCORE3_KEYS if parts.get(k) is not None)
    return dict(score3=round(s3, 3), score5=tot, score5_adj=tot_adj, parts=parts, parts_adj=parts_adj,
                air_adj=adj.get("gap_max"), lip_adj=adj.get("lip_thick_mid"))


def ruler(s52):
    if not s52:
        return None
    return dict(chord=s52.get("face_chord_deg_01_05"), foot=s52.get("front_x01_rel"), air=s52.get("gap_max"),
                lip=s52.get("lip_thick_mid"), area=s52.get("hood_area"), reach_m=s52.get("reach_m"), hood_height_m=s52.get("hood_height_m"))


def summarize(res, TG, bands):
    """g47_ana.json（dict）→ 組の行。score3 が最小のコマ（巻き始め〜最初に触れたコマ）、着水のコマ、いちばん巻いたコマ。"""
    out = dict(run=res.get("run"), zsel=res.get("zsel", "sdf (iz 1)"), still_offset_m=res.get("still_offset_m"))
    on = res.get("onset")
    sel = res.get("selected_frames") or {}
    fine = res.get("fine") or []
    for w in fine:
        w["sc"] = scores(w.get("s52"), TG, bands)
    if on:
        out["onset"] = dict(frame=on["frame"], t=on["t"], x_vert_h0=on.get("x_vert_h0"), xc_h0=on.get("xc_h0"), Hb_onset_h0=on.get("Hb_onset_h0"))
    cf = (res.get("contact_first") or {}).get("frame")
    td = sel.get("touchdown")
    end_f = cf if cf is not None else (td if td is not None else (fine[-1]["frame"] if fine else None))
    if on and end_f is not None:
        cand = [w for w in fine if on["frame"] <= w["frame"] <= end_f and w.get("sc")]
        if cand:
            b = min(cand, key=lambda w: (w["sc"]["score3"], -((w["s52"] or {}).get("hood_height_m") or 0.0)))
            out["best3"] = dict(frame=b["frame"], t=b["t"], xc=b["xc"], eta=b["eta"], ruler=ruler(b["s52"]), **b["sc"])
            out["series3"] = [[w["frame"], w["sc"]["score3"]] for w in cand]
            out["window"] = [on["frame"], end_f]
    byf = {w["frame"]: w for w in fine}
    for nm in ("touchdown", "max_overturn", "best_score"):
        f = sel.get(nm)
        if f is not None and f in byf and byf[f].get("sc"):
            w = byf[f]
            out[nm] = dict(frame=f, t=w["t"], xc=w["xc"], eta=w["eta"], ruler=ruler(w["s52"]), **w["sc"])
    pm = res.get("paper_measures")
    if pm:
        out["paper"] = {k: pm.get(k) for k in ("frame", "t", "t_tilde", "t_tilde_if_x0_15h0", "Hb_m", "Hb_h0", "xbp_h0", "AJ_Hb2", "AO_Hb2",
                                                 "W_L", "theta_o_deg", "jet_width_h0", "jet_width_09_h0", "contact", "Hb_max_before_td_m",
                                                 "cavity_how")}
    out["touchdown_by"] = (res.get("touchdown") or {}).get("by")
    out["eta_max_before_onset"] = res.get("eta_max_before_onset")
    return out, byf


def hf_tilt(rd, frames_at=()):
    """一番上の水面の板の層ごとの差（hf_c*.npz の eta[コマ, 層 4, x]）。各コマで、4 層の平均の頂の x の ±3 m の各層の最大（頂の高さ）と、
    頂の前後 ±40 m の (層 3 − 層 0) の平均（傾き）。返り値：時間の並びと、frames_at のコマの値。"""
    ps = sorted(glob.glob(rd + "/hf_c*.npz"))
    if not ps:
        return None
    E, X, F, T = [], None, [], []
    for p in ps:
        d = np.load(p)
        E.append(d["eta"]); F.append(d["frames"]); T.append(d["t"]); X = d["x"]; Z = d["z"]
    E = np.concatenate(E); F = np.concatenate(F); T = np.concatenate(T)
    _, ui = np.unique(F, return_index=True)
    ser = []
    for i in ui:
        e = E[i]
        m = np.nanmean(e, axis=0)
        if not np.isfinite(m).any():
            continue
        ic = int(np.nanargmax(m))
        w = np.abs(X - X[ic]) <= 3.0
        cr = [float(np.nanmax(e[k, w])) for k in range(e.shape[0])]
        w2 = np.abs(X - X[ic]) <= 40.0
        tilt = float(np.nanmean(e[-1, w2] - e[0, w2]))
        ser.append([int(F[i]), float(T[i]), float(X[ic]), cr, tilt])
    out = dict(z=[float(v) for v in Z], cols=["frame", "t", "x_crest", "crest_by_layer", "mean(eta_z3 - eta_z0) within ±40 m"],
               every24=[s for s in ser if s[0] % 24 == 0])
    out["at"] = {str(f): next((s for s in ser if s[0] == f), None) for f in frames_at if f}
    sp = [max(s[3]) - min(s[3]) for s in ser]
    out["crest_spread_max"] = max(sp) if sp else None
    out["crest_spread_last"] = sp[-1] if sp else None
    return out


def at_frame(byf, f):
    w = byf.get(f)
    if not w or not w.get("sc"):
        return None
    return dict(ruler=ruler(w["s52"]), score3=w["sc"]["score3"], eta=w["eta"])


def run_dir(rid):
    return B47 + "/runs/" + rid


def ana(rid, nofig=False, reuse=False):
    """1 本を読む：主（iz 1）は runs/<rid>/ana47、4 層の平均は ana47_zmean、層ごとは ana47_z0〜z3（図なし）。そのあと scan_summary.json。
    E1a の役の計算（E1a_short_dp0p25 など。sdfz なし）は ana47 を読み直さず、そのまま使う。"""
    rd = run_dir(rid)
    cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
    own = cfg.get("kind") == "scan"
    label = "%s %s" % (cfg.get("scan_id", "E1a"), (cfg.get("case") or {}).get("name_ja") or "")
    TG, bands = _bands()
    if own and not (reuse and os.path.exists(rd + "/ana47/g47_ana.json")):
        t0 = time.time()
        res = run_ana(rd, rd + "/ana47", None, nofig=nofig, label=label)
        print("main", rid, "%.0f s" % (time.time() - t0)); sys.stdout.flush()
    else:
        res = json.load(open(rd + "/ana47/g47_ana.json", encoding="utf8"))
    main, byf = summarize(res, TG, bands)
    has_z = bool(glob.glob(rd + "/sec_c*_b*.npz")) and "sdfz" in np.load(sorted(glob.glob(rd + "/sec_c*_b*.npz"))[-1]).files
    sl = {}
    if has_z:
        for z in ["mean", 0, 1, 2, 3]:
            out = rd + "/ana47_z%s" % z
            if reuse and os.path.exists(out + "/g47_ana.json"):
                r = json.load(open(out + "/g47_ana.json", encoding="utf8"))
            else:
                r = run_ana(rd, out, z, nofig=(nofig or z != "mean"), label=label + "（4 層の平均の場）" if z == "mean" else label)
            s, bz = summarize(r, TG, bands)
            s["at_main_best3"] = at_frame(bz, (main.get("best3") or {}).get("frame"))
            s["at_main_touchdown"] = at_frame(bz, (main.get("touchdown") or {}).get("frame"))
            sl[str(z)] = s
            print("slice", z, "done"); sys.stdout.flush()
    main["slices"] = sl
    main["has_allz"] = has_z
    main["tilt"] = hf_tilt(rd, [(main.get(k) or {}).get("frame") for k in ("best3", "touchdown")] + [(main.get("onset") or {}).get("frame")])
    # 層ごとの幅（同じコマで）
    if has_z:
        spread = {}
        for which in ("at_main_best3", "at_main_touchdown"):
            vals = {}
            for k in ("0", "1", "2", "3"):
                a = (sl.get(k) or {}).get(which)
                if a:
                    for q, v in a["ruler"].items():
                        if v is not None:
                            vals.setdefault(q, []).append(v)
                    vals.setdefault("score3", []).append(a["score3"]); vals.setdefault("eta_m", []).append(a["eta"])
            spread[which] = {q: [min(v), max(v)] for q, v in vals.items()}
        own_td = {}
        for k in ("0", "1", "2", "3"):
            p = (sl.get(k) or {}).get("paper") or {}
            for q in ("frame", "Hb_h0", "xbp_h0", "AJ_Hb2", "AO_Hb2", "W_L", "theta_o_deg", "jet_width_h0"):
                if p.get(q) is not None:
                    own_td.setdefault(q, []).append(p[q])
        spread["own_touchdown_paper"] = {q: [min(v), max(v)] for q, v in own_td.items()}
        b3 = {}
        for k in ("0", "1", "2", "3"):
            b = (sl.get(k) or {}).get("best3")
            if b:
                b3.setdefault("frame", []).append(b["frame"]); b3.setdefault("score3", []).append(b["score3"])
        spread["own_best3"] = {q: [min(v), max(v)] for q, v in b3.items()}
        main["slice_spread"] = spread
    # 選んだコマの水の形（図のため）
    GA = _ga()
    patch_rec(GA, None)
    cx = GA.Ctx(rd, {})
    mk = {}
    for nm in ("best3", "touchdown", "max_overturn"):
        d = main.get(nm)
        if d:
            M, X, Z = GA.fine_mask(cx, d["frame"], d["xc"], S=cx.sdf(d["frame"]))
            mk[nm + "_M"] = M; mk[nm + "_X"] = X; mk[nm + "_Z"] = Z
            m52, _e = GA.s52_measure(M, X, Z)
            if m52:      # 点数に入れない参考：後ろの面（0.7〜0.9 η_c の角度、0.7 η_c の幅）・唇の先の高さ・張り出し（η_c で割る）
                d["extra"] = {k: GA.fnum(m52.get(k)) for k in ("back_angle_07_09_deg", "width07_silhouette", "tip_z", "reach", "hood_low_z",
                                                                "hood_height", "steep60_frac", "eta_c")}
            mk[nm + "_xc"] = np.float64(d["xc"]); mk[nm + "_eta"] = np.float64(d["eta"])
    os.makedirs(CMP, exist_ok=True)
    np.savez_compressed(CMP + "/masks_%s.npz" % rid, **mk)
    main["cfg"] = dict(scan_id=cfg.get("scan_id"), bed=cfg.get("bed"), solver=cfg.get("solver"), domain=[cfg["box"]["x0"], cfg["box"]["x1"]],
                       crest=(cfg.get("solitary") or {}).get("x0"), a_over_h=(cfg.get("solitary") or {}).get("a_over_h"), dp=cfg["parms"]["dp"])
    rj = sorted(glob.glob(rd + "/run_c*.json"))
    if rj:
        runs_ = [json.load(open(p, encoding="utf8")) for p in rj]
        r0 = runs_[0]; inf = r0.get("info") or {}
        main["run"] = dict(wall_s=sum(float(r.get("wall_total_s") or 0) for r in runs_), launches=len(runs_),
                           particles_first=r0.get("particles_first"), particles_max=max(int(r.get("particles_max") or 0) for r in runs_),
                           substeps=r0.get("substeps_min_max"), rss_peak_gb=max(float(r.get("rss_peak_gb") or 0) for r in runs_),
                           stopped=runs_[-1].get("stopped"), f_end_done=runs_[-1].get("f_end_done"),
                           leak_below_bed_max=max([l.get("n_below_bed", 0) for r in runs_ for l in (r.get("info") or {}).get("leak", [])] or [0]),
                           leak_out_max=max([l.get("n_out_x", 0) + l.get("n_out_z", 0) for r in runs_ for l in (r.get("info") or {}).get("leak", [])] or [0]),
                           z_mean_y2=[[l["frame"], l.get("z_mean_y2"), l.get("vz_mean_y2")] for r in runs_ for l in (r.get("info") or {}).get("leak", []) if "z_mean_y2" in l],
                           init_check=inf.get("init_check"), touchdown_online=inf.get("touchdown_online"))
    json.dump(GA.clean(main), open(rd + "/ana47/scan_summary.json" if own else CMP + "/scan_summary_%s.json" % rid, "w", encoding="utf8"),
              indent=1, ensure_ascii=False)
    return main


COLS = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (148, 103, 189), (255, 127, 14), (140, 86, 75), (23, 190, 207), (127, 127, 127)]


def load_summary(rid):
    p = run_dir(rid) + "/ana47/scan_summary.json"
    if not os.path.exists(p):
        p = CMP + "/scan_summary_%s.json" % rid
    return json.load(open(p, encoding="utf8"))


def print_lines():
    GA = _ga()
    S52 = GA.S52
    outer, inner, _ = S52.print_outline()
    pr = json.load(open(GA.STUDY52 + "/shape_measures.json", encoding="utf8"))
    p = pr["print"]["cn"]
    conv = lambda a: np.stack([(a[:, 0] - p["x_c"]) / p["eta_c"], (S52.Y_HORIZON - a[:, 1]) * (1.0 / S52.STRETCH) / p["eta_c"]], 1)
    return [conv(outer), conv(inner)], pr


def fig_sections(rids, labels, out_png, which="best3"):
    """組ごとに、選んだコマ（score3 最小）の断面を η_c で割って原画の輪郭と重ねる（着水のコマは紫の破線）。"""
    from PIL import Image, ImageDraw
    GA = _ga()
    PL, pr = print_lines()
    XL, XR, ZB, ZT = -3.0, 2.2, -0.3, 1.12
    PX = 190
    W = int((XR - XL) * PX); H = int((ZT - ZB) * PX)
    ncol = 2; nrow = int(math.ceil(len(rids) / ncol))
    pw, ph = W + 40, H + 130
    img = Image.new("RGB", (ncol * pw + 30, nrow * ph + 120), "white"); dr = ImageDraw.Draw(img)
    ttl = ("原画に最も近いコマ（score3 最小、青の塗り）と着水のコマ（紫の破線）" if which == "best3" else "着水のコマ（最初に触れたコマ、青の塗り）")
    dr.text((20, 12), "海底の組（粒子 0.25 m の 2D の板）：%s を、原画（黒、縦の伸びを戻した形）と重ねる" % ttl,
            fill=GA.TXT, font=GA.font(18, True))
    dr.text((20, 42), "縦横同じ倍率。頂の高さ η_c で割り、頂の位置をそろえた。右が進む向き。灰の線は静かな水面と η_c の 0.1・0.5（弦を測る高さ）",
            fill=GA.SUB, font=GA.font(14))
    for n, (rid, lab) in enumerate(zip(rids, labels)):
        s = load_summary(rid)
        mkp = CMP + "/masks_%s.npz" % rid
        mk = np.load(mkp) if os.path.exists(mkp) else None
        cx0 = 20 + (n % ncol) * pw; cy0 = 80 + (n // ncol) * ph
        ox, oy = cx0 + 20, cy0 + 60
        tr = lambda p: (ox + (p[0] - XL) * PX, oy + (ZT - p[1]) * PX)
        b = s.get(which) or {}
        td = s.get("touchdown") or {}
        rl = b.get("ruler") or {}
        dr.text((cx0, cy0), lab, fill=GA.TXT, font=GA.font(16, True))
        if b:
            dr.text((cx0, cy0 + 24), "コマ %d（t %.2f s、η_c %.2f m）score3 %.2f｜弦 %.0f°・足 %.2f・覆い %.3f｜空気 %.2f・唇 %.2f" % (
                b["frame"], b["t"], b["eta"], b["score3"], rl.get("chord") or 0, rl.get("foot") or 0, rl.get("area") or 0,
                rl.get("air") or 0, rl.get("lip") or 0), fill=GA.SUB, font=GA.font(13))
        dr.rectangle([ox, oy, ox + W, oy + H], outline=(170, 170, 170))
        for zv in (0.0, 0.1, 0.5, 1.0):
            a_ = tr((XL, zv)); b_ = tr((XR, zv))
            dr.line([a_, b_], fill=(120, 120, 120) if zv == 0 else (225, 225, 225), width=2 if zv == 0 else 1)
            dr.text((ox - 30, a_[1] - 8), "%g" % zv, fill=GA.SUB, font=GA.font(11))
        for xv in np.arange(-3.0, 2.21, 1.0):
            a_ = tr((xv, ZB)); dr.text((a_[0] - 6, a_[1] + 2), "%g" % xv, fill=GA.SUB, font=GA.font(11))
        if mk is not None and which + "_M" in mk.files:
            M = mk[which + "_M"]; X = mk[which + "_X"]; Z = mk[which + "_Z"]
            xc = float(mk[which + "_xc"]); eta = float(mk[which + "_eta"])
            # 塗り（水）：細かい格子を 2 画素ごとに
            xn = (X - xc) / eta; zn = Z / eta
            ii = np.where((xn >= XL) & (xn <= XR))[0][::2]; jj = np.where((zn >= ZB) & (zn <= ZT))[0][::2]
            sub = M[np.ix_(jj, ii)]
            for a_, j in enumerate(jj):
                row = sub[a_]
                if not row.any():
                    continue
                d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
                for s0, s1 in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
                    p0 = tr((xn[ii[s0]], zn[j])); p1 = tr((xn[ii[s1 - 1]], zn[j]))
                    dr.line([p0, p1], fill=(150, 185, 225), width=3)
            for L in GA.mask_lines(M, X, Z, xc, eta):
                P_ = [tr(p) for p in L if XL - 0.1 <= p[0] <= XR + 0.1 and ZB - 0.1 <= p[1] <= ZT + 0.1]
                if len(P_) > 1:
                    dr.line(P_, fill=(20, 60, 200), width=2)
        if mk is not None and "touchdown_M" in mk.files and td and td.get("frame") != b.get("frame"):
            for L in GA.mask_lines(mk["touchdown_M"], mk["touchdown_X"], mk["touchdown_Z"], float(mk["touchdown_xc"]), float(mk["touchdown_eta"])):
                P_ = [tr(p) for p in L if XL - 0.1 <= p[0] <= XR + 0.1 and ZB - 0.1 <= p[1] <= ZT + 0.1]
                for i in range(0, len(P_) - 1, 8):
                    dr.line(P_[i:i + 4], fill=(150, 60, 170), width=2)
        for L in PL:
            P_ = [tr(p) for p in L if XL - 0.1 <= p[0] <= XR + 0.1 and ZB - 0.1 <= p[1] <= ZT + 0.1]
            if len(P_) > 1:
                dr.line(P_, fill=(0, 0, 0), width=3)
    img.save(out_png)
    return out_png


def fig_beds(rids, labels, out_png):
    """海底の形（x/h0、水深/h0）と、巻き始め（○）・着水の xbp（×）の所。"""
    from PIL import Image, ImageDraw
    GA = _ga()
    XL, XR, YB, YT = 20.0, 50.0, -1.05, 0.85
    W, H = 1500, 560
    ox, oy = 90, 90
    img = Image.new("RGB", (W + 640, H + 170), "white"); dr = ImageDraw.Draw(img)
    tr = lambda x, y: (ox + (x - XL) / (XR - XL) * W, oy + (YT - y) / (YT - YB) * H)
    vex = (H / (YT - YB)) / (W / (XR - XL))
    dr.text((20, 15), "海底の組の海底（縦は h0 で割った高さ、横は x/h0。縦を %.1f 倍に伸ばした）" % vex + "と、巻き始め（○、前の面が鉛直）・着水（×、xbp）・着水の頂の高さ（横棒）",
            fill=GA.TXT, font=GA.font(17, True))
    dr.text((20, 45), "頂の初めの位置は 25 h0（S6 だけ 22 h0）。h0 = 19 m。灰の横線は静かな水面", fill=GA.SUB, font=GA.font(14))
    dr.rectangle([ox, oy, ox + W, oy + H], outline=(170, 170, 170))
    for yv in (-1.0, -0.5, 0.0, 0.5):
        a_ = tr(XL, yv); b_ = tr(XR, yv)
        dr.line([a_, b_], fill=(120, 120, 120) if yv == 0 else (230, 230, 230), width=2 if yv == 0 else 1)
        dr.text((ox - 45, a_[1] - 8), "%g" % yv, fill=GA.SUB, font=GA.font(12))
    for xv in range(20, 51, 5):
        a_ = tr(xv, YB); dr.line([a_, (a_[0], a_[1] - 6)], fill=(120, 120, 120)); dr.text((a_[0] - 8, a_[1] + 4), "%d" % xv, fill=GA.SUB, font=GA.font(12))
    y_leg = oy
    for n, (rid, lab) in enumerate(zip(rids, labels)):
        s = load_summary(rid)
        col = COLS[n % len(COLS)]
        bed = s["cfg"]["bed"]
        xs = np.linspace(XL * GC.H0, XR * GC.H0, 3000)
        by = GC.bed_y(xs, bed) / GC.H0
        # 鉛直の段を見せるため、点の並びをそのまま線に
        pts = [(p[0] / GC.H0, -p[1] / GC.H0) for p in bed]
        pts = [(XL, -bed[0][1] / GC.H0)] + [p for p in pts if XL <= p[0] <= XR] + [(XR, -bed[-1][1] / GC.H0)]
        dr.line([tr(*p) for p in pts], fill=col, width=3)
        on = s.get("onset") or {}
        pa = s.get("paper") or {}
        xo = on.get("x_vert_h0") or on.get("xc_h0")
        if xo:
            yo = on.get("Hb_onset_h0") or 0.0
            c = tr(xo, yo); dr.ellipse([c[0] - 7, c[1] - 7, c[0] + 7, c[1] + 7], outline=col, width=3)
        if pa.get("xbp_h0"):
            c = tr(pa["xbp_h0"], 0.0)
            dr.line([(c[0] - 8, c[1] - 8), (c[0] + 8, c[1] + 8)], fill=col, width=3); dr.line([(c[0] - 8, c[1] + 8), (c[0] + 8, c[1] - 8)], fill=col, width=3)
            if pa.get("Hb_h0"):
                c2 = tr(pa["xbp_h0"], pa["Hb_h0"]); dr.line([(c2[0] - 14, c2[1]), (c2[0] + 14, c2[1])], fill=col, width=3)
        dr.line([(ox + W + 20, y_leg + 10), (ox + W + 55, y_leg + 10)], fill=col, width=4)
        txt = lab
        if pa.get("Hb_h0"):
            txt += "：Hb %.2f h0、xbp %.1f h0" % (pa["Hb_h0"], pa["xbp_h0"])
        dr.text((ox + W + 62, y_leg), txt, fill=GA.TXT, font=GA.font(13)); y_leg += 28
    img.save(out_png)
    return out_png


def fig_measures(rids, labels, out_png, which="best3"):
    """5 つの量の、原画の帯（灰）・原画（黒）・論文の図 5b（白抜きの四角）と、組ごとの値（色の点。○ は score3 最小のコマ、× は着水のコマ）。
    空気・唇は E1a の偏りで割り戻した値も細い線で示す（矢印の先）。"""
    from PIL import Image, ImageDraw
    GA = _ga()
    TG, bands = _bands()
    lit = json.load(open(TARGETS, encoding="utf8"))["reference_scores"]["lit_F24_fig5b_Re0_t19.96"]
    items = [("前の面の弦 0.1〜0.5 η_c（度）", "face_chord_deg_01_05", "chord", 0, 160, "score3 に入る"),
             ("前の足（0.1 η_c、頂からの距離 ÷ η_c）", "front_x01_rel", "foot", 0, 1.3, "score3 に入る"),
             ("覆いの面積 ÷ η_c²", "hood_area", "area", 0, 0.42, "score3 に入る"),
             ("唇の下の空気 ÷ η_c", "gap_max", "air", 0, 1.1, "点数の外（FLIP は約 −35 %）"),
             ("唇の厚み ÷ η_c", "lip_thick_mid", "lip", 0, 0.65, "点数の外（FLIP は約 +53 %）")]
    W = 1000; RH = 40 + 26 * len(rids)
    ox = 380
    img = Image.new("RGB", (ox + W + 60, 110 + len(items) * (RH + 50)), "white"); dr = ImageDraw.Draw(img)
    dr.text((20, 12), "原画の物差しの 5 つの量：組ごとの値（○ score3 最小のコマ、× 着水のコマ）と原画の帯（灰）・原画（黒の縦線）・論文の図 5b（□、E1a の海底）",
            fill=GA.TXT, font=GA.font(17, True))
    dr.text((20, 40), "空気・唇の細い矢印は、E1a で測った FLIP の偏り（空気 ÷ 0.644、唇 ÷ 1.534）で割り戻した値（1 つの海底・1 つの層で測った偏りなので目安）。弦が 90° より大きいのは 0.1〜0.5 η_c の前の面が後ろへ傾いている時",
            fill=GA.SUB, font=GA.font(14))
    y = 80
    for title, key, rk, lo, hi, note in items:
        dr.text((20, y), title, fill=GA.TXT, font=GA.font(15, True)); dr.text((20, y + 20), note, fill=GA.SUB, font=GA.font(12))
        tx = lambda v: ox + (v - lo) / (hi - lo) * W
        bl, bh = bands[key]["band"]
        bh = hi if bh is None else bh
        dr.rectangle([tx(bl), y, tx(bh), y + RH], fill=(225, 225, 225))
        c = bands[key]["center"]; dr.line([(tx(c), y), (tx(c), y + RH)], fill=(0, 0, 0), width=3)
        lv = lit.get(key)
        if lv is not None:
            dr.rectangle([tx(lv) - 6, y + 4, tx(lv) + 6, y + 16], outline=(0, 0, 0), width=2)
        for k in range(6):
            v = lo + (hi - lo) * k / 5.0
            dr.line([(tx(v), y + RH), (tx(v), y + RH + 5)], fill=(120, 120, 120))
            dr.text((tx(v) - 12, y + RH + 6), ("%.0f" % v) if hi > 10 else ("%.2f" % v), fill=GA.SUB, font=GA.font(11))
        for n, (rid, lab) in enumerate(zip(rids, labels)):
            s = load_summary(rid)
            col = COLS[n % len(COLS)]
            yy = y + 28 + 26 * n
            dr.text((ox - 200, yy - 8), lab[:18], fill=col, font=GA.font(12))
            b = (s.get(which) or {}).get("ruler") or {}
            t = (s.get("touchdown") or {}).get("ruler") or {}
            v = b.get(rk)
            if v is not None:
                vv = min(max(v, lo), hi)
                dr.ellipse([tx(vv) - 6, yy - 6, tx(vv) + 6, yy + 6], outline=col, width=3)
                if rk in ("air", "lip"):
                    va = v / (AIR_BIAS if rk == "air" else LIP_BIAS)
                    va = min(max(va, lo), hi)
                    dr.line([(tx(vv), yy), (tx(va), yy)], fill=col, width=1)
                    dr.polygon([(tx(va), yy), (tx(va) - (6 if va > vv else -6), yy - 4), (tx(va) - (6 if va > vv else -6), yy + 4)], fill=col)
            v2 = t.get(rk)
            if v2 is not None:
                vv = min(max(v2, lo), hi)
                dr.line([(tx(vv) - 5, yy - 5), (tx(vv) + 5, yy + 5)], fill=col, width=2); dr.line([(tx(vv) - 5, yy + 5), (tx(vv) + 5, yy - 5)], fill=col, width=2)
        y += RH + 50
    img.save(out_png)
    return out_png


def fig_layers(rids, labels, out_png, which="touchdown"):
    """板の 4 層の断面（各層の着水のコマ。層ごとの η_c で割り、頂をそろえる）を重ねる。青 z −0.75 m → 赤 z +0.75 m。黒は原画。"""
    from PIL import Image, ImageDraw
    GA = _ga()
    PL, _ = print_lines()
    XL, XR, ZB, ZT = -1.6, 2.0, -0.15, 1.08
    PX = 230
    W = int((XR - XL) * PX); H = int((ZT - ZB) * PX)
    ncol = 3; nrow = int(math.ceil(len(rids) / ncol))
    pw, ph = W + 40, H + 120
    img = Image.new("RGB", (ncol * pw + 30, nrow * ph + 130), "white"); dr = ImageDraw.Draw(img)
    LC = [(30, 80, 220), (90, 160, 230), (240, 150, 60), (210, 30, 30)]
    dr.text((20, 12), "板の 4 層ごとの断面（各層の着水のコマ、層ごとの η_c で割り頂をそろえた）：青 z −0.75 m・水色 −0.25 m（主の読み）・橙 +0.25 m・赤 +0.75 m、黒は原画",
            fill=GA.TXT, font=GA.font(17, True))
    dr.text((20, 42), "2D の板（厚さ格子 4 個、両面は滑る壁）なのに、どの海底でも −z の側ほど噴流が太く空洞が小さい。各組の上の数は層ごとの Ao/Hb²",
            fill=GA.SUB, font=GA.font(14))
    for n, (rid, lab) in enumerate(zip(rids, labels)):
        rd = run_dir(rid)
        cx0 = 20 + (n % ncol) * pw; cy0 = 80 + (n // ncol) * ph
        ox, oy = cx0 + 20, cy0 + 50
        tr = lambda p: (ox + (p[0] - XL) * PX, oy + (ZT - p[1]) * PX)
        dr.text((cx0, cy0), lab, fill=GA.TXT, font=GA.font(15, True))
        dr.rectangle([ox, oy, ox + W, oy + H], outline=(170, 170, 170))
        for zv in (0.0, 0.5, 1.0):
            a_ = tr((XL, zv)); b_ = tr((XR, zv))
            dr.line([a_, b_], fill=(120, 120, 120) if zv == 0 else (225, 225, 225), width=1)
        txt = []
        for k in range(4):
            p = rd + "/ana47_z%d/%s_z%d_masks.npz" % (k, rid, k)
            j = rd + "/ana47_z%d/g47_ana.json" % k
            if not (os.path.exists(p) and os.path.exists(j)):
                continue
            mk = np.load(p); a = json.load(open(j, encoding="utf8"))
            at = (a.get("at") or {}).get(which)
            if not at or which + "_M" not in mk.files:
                continue
            for L in GA.mask_lines(mk[which + "_M"], mk[which + "_X"], mk[which + "_Z"], at["x_c"], at["eta_c"]):
                P_ = [tr(q) for q in L if XL - 0.05 <= q[0] <= XR + 0.05 and ZB - 0.05 <= q[1] <= ZT + 0.05]
                if len(P_) > 1:
                    dr.line(P_, fill=LC[k], width=2)
            pm = a.get("paper_measures") or {}
            if pm.get("AO_Hb2") is not None:
                txt.append("%.2f" % pm["AO_Hb2"])
        for L in PL:
            P_ = [tr(q) for q in L if XL - 0.05 <= q[0] <= XR + 0.05 and ZB - 0.05 <= q[1] <= ZT + 0.05]
            if len(P_) > 1:
                dr.line(P_, fill=(0, 0, 0), width=2)
        dr.text((cx0, cy0 + 24), "Ao/Hb²（層 z −0.75 → +0.75 m）：" + "・".join(txt), fill=GA.SUB, font=GA.font(13))
    img.save(out_png)
    return out_png


def label_of(rid, s=None):
    s = s or load_summary(rid)
    sid = (s.get("cfg") or {}).get("scan_id") or "S1_E1a"
    t = scan_entry(sid)
    rs = (s.get("cfg") or {}).get("solver") or {}
    tag = "" if rs.get("reseed", 1) else "（reseed 0）"
    short = {"S1_E1a": "S1 E1a 0.0693・棚 0.371", "S2_s1-10": "S2 1:10・平ら 0.1", "S3_s1-14.4": "S3 1:14.4・平ら 0.1",
             "S4_s1-20": "S4 1:20・平ら 0.1", "S5_ledge1-7": "S5 1:7・岩棚 0.2", "S6_twostep": "S6 2 段の段"}.get(sid, sid)
    return short + tag, t


def table(rids):
    TG, bands = _bands()
    pr = json.load(open(_ga().STUDY52 + "/shape_measures.json", encoding="utf8"))["print"]["cn"]
    lit = json.load(open(TARGETS, encoding="utf8"))["reference_scores"]["lit_F24_fig5b_Re0_t19.96"]
    rows = []
    for rid in rids:
        s = load_summary(rid)
        lab, t = label_of(rid, s)
        pf = t.get("pick_feddersen") or {}
        pdn = t.get("predicted") or {}
        rp = t.get("ruler_predicted") or {}
        b = s.get("best3") or {}; td = s.get("touchdown") or {}; pa = s.get("paper") or {}; on = s.get("onset") or {}
        rows.append(dict(
            run=rid, label=lab, scan_id=t["id"], s=t.get("s"), psi0=pf.get("psi0"), S0=pf.get("S0"), fit_valid=pf.get("fit_valid"),
            onset_x_h0=on.get("x_vert_h0") or on.get("xc_h0"), Hb_onset_h0=on.get("Hb_onset_h0"),
            td_frame=pa.get("frame"), td_t=pa.get("t"), Hb_h0=pa.get("Hb_h0"), xbp_h0=pa.get("xbp_h0"), AJ_Hb2=pa.get("AJ_Hb2"), AO_Hb2=pa.get("AO_Hb2"),
            W_L=pa.get("W_L"), theta=pa.get("theta_o_deg"), jetw_h0=pa.get("jet_width_h0"),
            pred_Hb_h0=pdn.get("Hb_over_h0"), pred_HI_h0=pdn.get("HI_over_h0"), pred_xbreak_h0=pdn.get("x_break_over_h0"), pred_ximpact_h0=pdn.get("x_impact_over_h0"),
            pred_AJ=pf.get("AJ_over_HI2"), pred_AO=pf.get("AO_over_HI2"), pred_WL=pf.get("WO_over_LO"), pred_theta=pf.get("thetaO_deg"),
            pred_ruler=dict(chord=rp.get("face_chord_deg_01_05"), foot=rp.get("front_x01_rel"), air=rp.get("gap_max"), lip=rp.get("lip_thick_mid"),
                            area=rp.get("hood_area"), score5=rp.get("score"), source=rp.get("source_ja")),
            best3=b, touchdown=td, max_overturn=s.get("max_overturn"), slice_spread=s.get("slice_spread"), run_info=s.get("run"),
            still_offset_m=s.get("still_offset_m"), init_check=init_check_max(((s.get("run") or {}).get("init_check"))),
            eta_max_before_onset=s.get("eta_max_before_onset"), window=s.get("window")))
    out = dict(made="g47_scan.py table %s" % time.strftime("%Y-%m-%d %H:%M"), rule_ja=__doc__.split("判定の決まり")[1].strip() if "判定の決まり" in __doc__ else "",
               print_cn=dict(chord=pr["face_chord_deg_01_05"], foot=pr["front_x01_rel"], air=pr["gap_max"], lip=pr["lip_thick_mid"], area=pr["hood_area"]),
               bands={k: bands[k]["band"] for k in ("face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area")},
               fig5b=dict(chord=lit["face_chord_deg_01_05"], foot=lit["front_x01_rel"], air=lit["gap_max"], lip=lit["lip_thick_mid"], area=lit["hood_area"]),
               bias=dict(air=AIR_BIAS, lip=LIP_BIAS), rows=rows)
    os.makedirs(CMP, exist_ok=True)
    json.dump(_ga().clean(out), open(CMP + "/scan_table.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
    # Markdown（主の表）
    f = lambda v, fm="%.3f": "–" if v is None else (fm % v)
    L = ["| 組 | ψ0 | Hb/h0 着水（予測） | 巻き始め x/h0 | xbp/h0（予測） | AJ/Hb²（P&F） | Ao/Hb²（P&F） | 弦° 最小／着水 | 足 | 覆い | 空気 生（割り戻し） | 唇 生（割り戻し） | score3 最小（コマ）／着水 | 5 つの点数 生／割り戻し |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    L.append("| 原画 cn（帯） | – | – | – | – | – | – | %.1f（%.1f〜%.1f） | %.2f（%.2f〜%.2f） | %.3f（%.3f〜%.3f） | %.2f 以上（%.2f〜） | %.2f（%.2f〜%.2f） | 0 | 0 |" % (
        pr["face_chord_deg_01_05"], *bands["face_chord_deg_01_05"]["band"], pr["front_x01_rel"], *bands["front_x01_rel"]["band"],
        pr["hood_area"], *bands["hood_area"]["band"], pr["gap_max"], bands["gap_max"]["band"][0], pr["lip_thick_mid"], *bands["lip_thick_mid"]["band"]))
    for r in rows:
        b = r["best3"] or {}; td = r["touchdown"] or {}; bl = b.get("ruler") or {}; tl = td.get("ruler") or {}
        L.append("| %s | %s | %s（%s） | %s | %s（%s） | %s（%s） | %s（%s） | %s／%s | %s／%s | %s／%s | %s（%s）／%s | %s（%s）／%s | %s（%s）／%s | %s／%s |" % (
            r["label"], f(r["psi0"]), f(r["Hb_h0"]), f(r["pred_Hb_h0"], "%.2f"), f(r["onset_x_h0"], "%.2f"), f(r["xbp_h0"], "%.2f"),
            f(r["pred_ximpact_h0"], "%.1f"), f(r["AJ_Hb2"]), f(r["pred_AJ"]) + ("" if r["fit_valid"] else " 外"), f(r["AO_Hb2"]),
            f(r["pred_AO"]) + ("" if r["fit_valid"] else " 外"),
            f(bl.get("chord"), "%.1f"), f(tl.get("chord"), "%.1f"), f(bl.get("foot"), "%.2f"), f(tl.get("foot"), "%.2f"),
            f(bl.get("area")), f(tl.get("area")), f(bl.get("air"), "%.2f"), f(b.get("air_adj"), "%.2f"), f(tl.get("air"), "%.2f"),
            f(bl.get("lip"), "%.2f"), f(b.get("lip_adj"), "%.2f"), f(tl.get("lip"), "%.2f"),
            f(b.get("score3"), "%.2f"), b.get("frame", "–"), f(td.get("score3"), "%.2f"), f(b.get("score5"), "%.2f"), f(b.get("score5_adj"), "%.2f")))
    open(CMP + "/scan_table.md", "w", encoding="utf8").write("\n".join(L) + "\n")
    print("\n".join(L))
    fr = [(r["run"], r["label"]) for r in rows if "noreseed" not in r["run"]]       # 図は reseed の試しを除く
    fids = [a for a, _ in fr]; labels = [b for _, b in fr]
    fig_sections(fids, labels, CMP + "/scan_sections_best3.png", "best3")
    fig_sections(fids, labels, CMP + "/scan_sections_touchdown.png", "touchdown")
    fig_beds(fids, labels, CMP + "/scan_beds.png")
    fig_measures(fids, labels, CMP + "/scan_measures.png")
    zr = [(a, b) for a, b in fr if (load_summary(a).get("has_allz"))]
    if zr:
        fig_layers([a for a, _ in zr], [b for _, b in zr], CMP + "/scan_layers_touchdown.png", "touchdown")
    return out


def init_check_max(ic):
    """1 コマ目の格子・粒子の流速と GN の式の差の最大（9 点）。"""
    if not ic:
        return None
    r1 = [r for c in ic if c["frame"] == 1 for r in c["rows"]]
    if not r1:
        return None
    du = max(abs(r["u_grid"] - r["u_gn"]) for r in r1); dw = max(abs(r["w_grid"] - r["w_gn"]) for r in r1)
    dup = max(abs(r.get("u_part", r["u_gn"]) - r["u_gn"]) for r in r1); dwp = max(abs(r.get("w_part", r["w_gn"]) - r["w_gn"]) for r in r1)
    crest = [r for r in r1 if r["dx"] == 0.0]
    return dict(du_grid=du, dw_grid=dw, du_part=dup, dw_part=dwp, u_crest_grid=[r["u_grid"] for r in crest], u_crest_gn=crest[0]["u_gn"] if crest else None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["cfg", "ana", "table"])
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--reseed", type=int, default=1)
    ap.add_argument("--name", default=None)
    ap.add_argument("--allz", type=int, default=1)
    ap.add_argument("--veltransfer", choices=["apic", "flip"], default="apic",
                    help="cfg: 速度の受け渡し。既定 apic（前と同じ）。推奨は flip（板の層の差が消える。record_ja.md 2026-10-13 の節）")
    ap.add_argument("--nofig", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="ana: 読み（g47_ana.json）があればそれを使い、まとめだけ作り直す")
    a = ap.parse_args()
    if a.what == "cfg":
        for sid in a.ids:
            c = make_cfg(sid, run_id=a.name, reseed=a.reseed, allz=bool(a.allz), veltransfer=a.veltransfer)
            p = B47 + "/runs/ready/%s.json" % c["run_id"]
            json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
            b = c["box"]
            print(p, "f_end", c["f_end"], "t_end", c["t_end_s"], "t_td_est", c["case"]["t_touchdown_estimate_s"],
                  "t_from", c["stop_touchdown"]["t_from"], "box", b["x0"], b["x1"], b["y_floor"], b["y_top"], "cells", b["cells"],
                  "o", b["ox"], b["oy"], b["oz"], "solver", c["solver"], "sol", os.path.basename(c["solitary_npz"]))
    elif a.what == "ana":
        for rid in a.ids:
            m = ana(rid, nofig=a.nofig, reuse=a.reuse)
            show = dict(run=rid, onset=m.get("onset"), best3={k: (m.get("best3") or {}).get(k) for k in ("frame", "score3", "score5", "score5_adj", "ruler")},
                        touchdown={k: (m.get("touchdown") or {}).get(k) for k in ("frame", "score3", "ruler")}, paper=m.get("paper"),
                        spread=m.get("slice_spread"))
            print(json.dumps(_ga().clean(show), ensure_ascii=False, indent=0))
    elif a.what == "table":
        table(a.ids)
