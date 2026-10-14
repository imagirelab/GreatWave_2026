# -*- coding: utf-8 -*-
"""FLIP48：A 字の盛り上がりの読み（py -3.10 -B、numpy・PIL）。2026-10-15 新しく書いた。
FLIP46 の g46_lateral.py・g46_curlwidth.py（main session が 10/15 に足した物、変えていない）の考えを写し、FLIP48 の凍らせた目標
（Build/FLIP48/plan/plan_frozen.json の P1〜P5・H、R0 の S1〜S3）の判定を足した。

読む物：<記録>/hf_c*_b*.npz（一番上の水面 eta[コマ, 横 y, x]）、r4_c*_b*.npz（3D の狭い帯の水面の場）、cfg.json、run_c*.json、r6_c*.npz、
        ana.json（g48_analyze.py。巻き始め・最も巻いた・着水のコマ、真ん中の頂の追い、形の量、静かな水面のずれ）。
量（y = 0 の対称の面から片側を読み、幅は両側の全幅に直す。高さは静かな水面のずれを引いた値）：
  c(y)        頂の高さ：各 y の行で x ∈ [150 m, Lx − 15 m] の一番上の水面（x の向きに 3 格子の中央値で細い水の針を除いた後）の最大。
              横の端の帯は x ≤ 340 m だけで探す（下流の壁に寄る水を数えない）
  c0          真ん中（y < 1 m の行）の c。Hc = 巻き始めのコマの真ん中の頂（ana.json の onset.eta_c。hf の c0 も並べる）
  c_side      横の端の帯 |y| 70〜84 m（W − 15〜W − 1 m）の c の平均。比 c0/c_side
  半分の幅    c(y) − c_side ≥ (c0 − c_side)/2 が y = 0 から続く全幅（行の間は線形に補う）。盛り上がりの幅
  90% の幅    c(y) ≥ 0.9 c0 が y = 0 から続く全幅
  c(2Hc)・c(4Hc)  |y| = 2 Hc・4 Hc の c（行の間を補う）と、c0 との比
  巻いた全幅  主：g46_analyze.lateral_rows_r4（r4 の各 y の断面で前の面の最大の角 thmax ≥ 90° の行が y = 0 から続く範囲 × 2）を
              巻き始めから着水（なければ + 2 s）まで 2 コマごと。確かめ：r4 の列に水・空気・水（覆いかぶさり）が 2 列以上ある行が
              y = 0 から続く範囲（頂の x − 10〜+40 m）。全幅 ÷ Hc
  剥がれ角    atan(c_crest / v)。v = 巻いた半幅の伸びる速さ（巻き始め〜最大の幅の線形の当てはめ）、c_crest = 真ん中の頂の進む速さ（巻き始めの ±0.5 s）
  集まりの利得  Hc_3D / Hc_2D（R0 の板の peak.json。--ref2d で与える。既定は runs/R0_strip_RS_A<A>/peak.json）
使い方：py -3.10 -B g48_peak_metrics.py <記録> [<記録> ...] [--ref2d=<R0 の記録か peak.json>] [--every=6] [--no-curl]
        py -3.10 -B g48_peak_metrics.py --selftest（答えの分かった合成の値で読みを確かめる）
出す物：<記録>/peak.json・PEAK_ja.md・video/<run_id>_peak_lateral.png（FLIP48 の置き場所の中だけ。外の記録は読むだけで、書かずに画面に出す）
2026-10-15 R3 の試し（plan/campaign_R3_judge.json）のために足した（P1〜P5・H の判定は変えない）：
  - 補いの読み（g48_supp.py）：巻き始めの apron、前の水の層から測った弦、噴き出しの先の印、体の弦、足・空洞・覆い、棚の上の最小の水深、
    c0/H0、c0 ÷ 溝の外の帯 |y| 35〜48 m。peak.json の supp・supp_lateral と PEAK_ja.md の「補いの読み」の節
  - cfg の case.campaign が R3 の板（G0a・G0b・G0c）なら、G0 の 2D の門（plan/plan_R3_frozen.json の G0.gate）の各々を書く（g0_gate）
  - 水の量のずれの水の体積：箱の底 zb（溝のある R3 は −25 m）で数える（g48_cfg.count_particles に zb を渡す）
"""
import os, sys, json, glob, math, time

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, _HERE)
import numpy as np                  # noqa: E402
import g48_common as GC             # noqa: E402
import g48_supp as GS               # noqa: E402  R3 の補いの読み

X_MIN = 150.0          # 頂を探す x の始まり（尾根に入った後）
X_END_PAD = 15.0       # 下流の壁の手前を除く幅（m）
X_SIDE_MAX = 340.0     # 横の端の帯の頂を探す x の終わり（計画 P4a）
SIDE_BAND = (70.0, 84.0)  # R1（半幅 85 m）の横の端の帯。ほかの幅では (W − 15, W − 1)


def side_band(W):
    return (float(W) - 15.0, float(W) - 1.0)
MIN_EXCESS = 0.3       # 盛り上がりの幅を読む最小の差（m）
FONT = r"C:/Windows/Fonts/meiryo.ttc"


# ======================================================================== 記録を読む
def load_hf(rd):
    """hf の全部のブロックを読み、いちばん多いコマの格子の物をつなぐ（1 コマ目は初めの水面の VDB の広い格子なので別）。
    返り値 dict(frames, t, eta[f, y, x], xs, ys, meta)。"""
    groups = {}
    for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz"))):
        d = np.load(p)
        if d["eta"].ndim != 3:
            continue
        m = json.loads(str(d["meta"]))
        key = (tuple(d["eta"].shape[1:]), round(float(m["x0"]), 6), round(float(m["z0"]), 6))
        g = groups.setdefault(key, dict(fr=[], t=[], eta=[], meta=m))
        g["fr"].append(d["frames"]); g["t"].append(d["t"]); g["eta"].append(d["eta"])
    if not groups:
        raise SystemExit("hf の記録がない：%s" % rd)
    key = max(groups, key=lambda k: sum(len(a) for a in groups[k]["fr"]))
    g = groups[key]
    fr = np.concatenate(g["fr"]); t = np.concatenate(g["t"]); eta = np.concatenate(g["eta"], axis=0)
    o = np.argsort(fr, kind="stable")
    fr, t, eta = fr[o], t[o], eta[o]
    keep = np.concatenate([[True], np.diff(fr) > 0])          # 同じコマが 2 度あれば（途中保存からの続き）先の物
    m = g["meta"]
    xs = m["x0"] + m["dx"] * np.arange(eta.shape[2]); ys = m["z0"] + m["dz"] * np.arange(eta.shape[1])
    return dict(frames=fr[keep], t=t[keep], eta=eta[keep], xs=xs, ys=ys, meta=m)


def crest_profile(eta_f, xs, x_lo, x_hi, med=3):
    """eta_f[y, x] → (c(y), x_c(y))。x ∈ [x_lo, x_hi] で、x の向きに med 格子の中央値（1〜2 格子の水の針を除く）の最大。"""
    sel = np.where((xs >= x_lo) & (xs <= x_hi))[0]
    e = eta_f[:, sel].astype(np.float64)
    if med > 1:
        h = med // 2
        pad = np.pad(e, ((0, 0), (h, h)), mode="edge")
        e = np.nanmedian(np.stack([pad[:, i:i + e.shape[1]] for i in range(med)]), axis=0)
    good = np.isfinite(e).any(axis=1)
    c = np.full(e.shape[0], np.nan); xc = np.full(e.shape[0], np.nan)
    if good.any():
        ee = np.where(np.isfinite(e[good]), e[good], -1e9)
        i = np.argmax(ee, axis=1)
        c[good] = ee[np.arange(len(i)), i]; xc[good] = xs[sel][i]
    return c, xc


def _cross_width(c, ys, thr):
    """c(y) ≥ thr が最初の行から続く範囲の全幅（行の間を線形に補う）。返り値 (全幅 m, 壁まで届いたか)。"""
    if not np.isfinite(c[0]) or c[0] < thr:
        return 0.0, False
    ok = np.isfinite(c) & (c >= thr)
    j = int(np.argmin(ok)) if not ok.all() else len(ok)
    if j >= len(ys):
        return 2.0 * float(ys[-1] + 0.5 * (ys[1] - ys[0] if len(ys) > 1 else 1.0)), True
    if not np.isfinite(c[j]):
        return 2.0 * float(ys[j - 1]), False
    y0, y1, c0_, c1_ = ys[j - 1], ys[j], c[j - 1], c[j]
    yq = y0 + (c0_ - thr) / max(c0_ - c1_, 1e-12) * (y1 - y0)
    return 2.0 * float(yq), False


def lateral(c, ys, c_side_prof=None, Hc=None, band=SIDE_BAND):
    """1 コマの横の分け方。c：頂の高さ c(y)（静かな水面から）、c_side_prof：横の端の帯に使う c（x ≤ 340 m）。"""
    cs = c if c_side_prof is None else c_side_prof
    c0 = float(np.nanmean(c[ys < 1.0])) if (ys < 1.0).any() else float(c[0])
    out = dict(c0=c0)
    bm = (ys >= band[0]) & (ys <= band[1])
    side = float(np.nanmean(cs[bm])) if bm.any() and np.isfinite(cs[bm]).any() else None
    out["c_side"] = side
    out["ratio_side"] = (c0 / side) if side and side > 0 else None
    H = float(Hc) if Hc else c0
    out["Hc_used"] = H
    for mult in (1, 2, 4):
        yq = mult * H
        v = float(np.interp(yq, ys, c)) if yq <= ys[-1] else None
        out["c_%dHc" % mult] = v
        out["ratio_%dHc" % mult] = (c0 / v) if v and v > 0 else None
    if side is not None and c0 - side >= MIN_EXCESS:
        w, wall = _cross_width(c, ys, side + 0.5 * (c0 - side))
        out["half_excess_width_m"] = w; out["half_excess_reaches_wall"] = wall
        out["half_excess_width_over_Hc"] = w / H if H > 0 else None
    else:
        out["half_excess_width_m"] = None; out["half_excess_reaches_wall"] = None; out["half_excess_width_over_Hc"] = None
    w9, wall9 = _cross_width(c, ys, 0.9 * c0)
    out["w90_m"] = w9; out["w90_reaches_wall"] = wall9
    return out


def r4_overhang_width(rd_reader, f, xc, bed_fn, off, margin, x_back=10.0, x_front=40.0, min_cols=2, bed_fill_vox=1.5):
    """確かめの巻いた全幅：r4 の各 y の行で、x_c − x_back〜x_c + x_front の列のうち、上から水・空気・水の列が min_cols 列以上続く行が、
    y = 0 から続く範囲 × 2。海底 + 余白 + bed_fill_vox 格子より下は水とする（速い頂の下で海底のすぐ上に 1 格子の空気の層が出て、
    覆いかぶさりと読み違えた。FLIP46 P05_k0p5_W136 の 289 コマで確かめた。g46_analyze も海底から 2 格子以内の空気の穴を数えない）。
    返り値 (全幅 m, 覆いかぶさりのある行の y の list)。"""
    if f not in rd_reader.b:
        return None, None
    a, m, t = rd_reader.get(f)
    a = a.astype(np.float32)
    xs = m["x0"] + m["dx"] * np.arange(a.shape[2]); yv = m["y0"] + m["dy"] * np.arange(a.shape[1]); zs = m["z0"] + m["dz"] * np.arange(a.shape[0])
    sel = (xs >= xc - x_back) & (xs <= xc + x_front)
    if not sel.any():
        return None, None
    rows = []
    for k in range(a.shape[0]):
        S = a[k][:, sel]
        bed = bed_fn(xs[sel], float(zs[k]))
        water = (S < 0) | (yv[:, None] < (bed + margin + bed_fill_vox * float(m["dy"]))[None, :])
        below = np.maximum.accumulate(water, axis=0)                # その段より下（を含む）に水
        above = np.maximum.accumulate(water[::-1], axis=0)[::-1]    # その段より上（を含む）に水
        gap = (~water) & below & above
        col = gap.any(axis=0)
        run = 0; best = 0
        for v in col:
            run = run + 1 if v else 0; best = max(best, run)
        rows.append(best >= min_cols)
    rows = np.array(rows)
    ov_y = [float(z) for z, v in zip(zs, rows) if v]
    if not rows[0]:
        return 0.0, ov_y
    j = int(np.argmin(rows)) if not rows.all() else len(rows)
    return 2.0 * float(zs[j - 1] + 0.5 * m["dz"]), ov_y


# ======================================================================== 1 本を読む
def _ana(rd):
    p = os.path.join(rd, "ana.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def _key_frames(ana):
    on = ana.get("onset") or {}
    sh = (ana.get("shape") or {}).get("frames") or {}
    td = ana.get("touchdown") or {}
    k = {}
    if on.get("frame"):
        k["onset"] = int(on["frame"])
    if sh.get("max_overturn"):
        k["max_overturn"] = int(sh["max_overturn"])
    if td.get("frame"):
        k["touchdown"] = int(td["frame"])
    if not k and ana.get("steepest"):
        k["steepest"] = int(ana["steepest"]["frame"])
    return k


def curl_series(rd, ana, every=2, dt_after=2.0, want_r4=True):
    """巻き始めから着水（なければ + dt_after s）まで、巻いた全幅（主：thmax の行、確かめ：r4 の覆いかぶさり）と真ん中の頂。"""
    import g48_analyze as A48
    A46 = A48.A46
    on = ana.get("onset")
    if not on:
        return dict(note_ja="巻き始めがないので読まない")
    cx = A48.Ctx48(rd, {})
    tr = {int(s[0]): s for s in ((ana.get("centre_track") or {}).get("series") or [])}
    f0 = int(on["frame"])
    td = ana.get("touchdown") or {}
    f1 = int(td["frame"]) if td.get("frame") else f0 + int(round(dt_after * 24))
    f1 = min(f1 + 6, max(cx.R4.frames) if cx.R4.frames else f1)
    xc = float(on["xc"])
    rows = []
    for f in range(f0, f1 + 1, every):
        if f not in cx.R4.b:
            continue
        if f in tr:
            xc = float(tr[f][2])
        r4 = A46.lateral_rows_r4(cx, f, xc)
        s = (r4 or {}).get("summary") or {}
        row = dict(frame=f, t=float(cx.R4.get(f)[2]), xc=xc, overturned_full_m=s.get("overturned_full_m"),
                   y_over90=s.get("y_over90"), centre_eta=(s.get("crest_eta") or {}).get("centre"))
        if want_r4:
            w2, ov = r4_overhang_width(cx.R4, f, xc, cx.bed_z, cx.off, cx.margin)
            row["overhang_full_m"] = w2; row["overhang_rows_n"] = len(ov or [])
        rows.append(row)
    return dict(rows=rows, onset_frame=f0, end_frame=f1, every=every,
                rule_ja="主：thmax ≥ 90° の行が y = 0 から続く範囲 × 2（g46_analyze.rows_summary）。確かめ：水・空気・水の列が 2 列以上の行（頂の x −10〜+40 m）")


def peel(curl, ana):
    """剥がれ角。v = 巻いた半幅の伸びる速さ（巻き始め〜最大の幅、最小二乗）、c_crest = 真ん中の頂の速さ（巻き始めの ±0.5 s の x の当てはめ）。"""
    rows = [r for r in (curl.get("rows") or []) if r.get("overturned_full_m") is not None]
    if len(rows) < 3:
        return dict(note_ja="巻いた幅の時系列が短い")
    t = np.array([r["t"] for r in rows]); w = np.array([r["overturned_full_m"] for r in rows]) / 2.0
    i1 = int(np.argmax(w))
    if i1 < 2:
        return dict(note_ja="幅が伸びない", half_width_max_m=float(w.max()))
    v = float(np.polyfit(t[:i1 + 1], w[:i1 + 1], 1)[0])
    on = ana["onset"]
    tr = (ana.get("centre_track") or {}).get("series") or []
    pts = [(s[1], s[2]) for s in tr if abs(s[1] - on["t"]) <= 0.5 + 1e-9]
    cc = float(np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)[0]) if len(pts) >= 3 else None
    ang = math.degrees(math.atan2(cc, v)) if (cc is not None and v > 0) else (90.0 if cc is not None else None)
    return dict(v_lat_mps=v, c_crest_mps=cc, peel_angle_deg=ang, t_fit=[float(t[0]), float(t[i1])], half_width_max_m=float(w[i1]),
                note_ja="剥がれ角 = atan(c_crest / v)。90° は横へ広がらない、小さいほど横へ早く広がる（Scarfe 2003 の定義）")


def health(rd, cfg, ana):
    """H の量：海底より下の粒子、2 コマ目の流速の確かめ、静かな水面のずれ、水の量のずれ、時間、mp4。"""
    import g48_cfg as CF
    recs = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]
    out = {}
    leaks = [l for r in recs for l in ((r.get("info") or {}).get("leak") or [])]
    pmax = max([r.get("particles_max") or 0 for r in recs] or [0])
    if leaks and pmax:
        lm = max(leaks, key=lambda l: l.get("n_below_bed") or 0)
        out["bed_leak_max"] = dict(n=lm.get("n_below_bed"), frame=lm.get("frame"), frac=(lm.get("n_below_bed") or 0) / pmax, gap_min=lm.get("gap_min"))
    ic = [c for r in recs for c in ((r.get("info") or {}).get("init_check") or []) if int(c.get("frame", 0)) == 2]
    if ic:
        rels = [abs(row["u_grid"] / row["u_ana"] - 1.0) for row in ic[0]["rows"]
                if row.get("u_grid") is not None and abs(row.get("u_ana") or 0) >= 1.0 and abs(row.get("dx", 1)) < 1e-9]
        out["init_check_f2"] = dict(n=len(rels), rel_max=max(rels) if rels else None, rel_median=float(np.median(rels)) if rels else None,
                                    rule_ja="頂の真下（dx 0）、|u 解| ≥ 1 m/s の行の |u 格子/u 解 − 1|")
    out["still_offset_m"] = ana.get("still_level_offset_m")
    # 水の量のずれ：閉じた水槽の平均の水面（level_box の η_top の平均）の動き × 面積 ÷ 水の体積（巻き始めまで）
    r6 = sorted(glob.glob(os.path.join(rd, "r6_c*.npz")))
    if r6:
        fr = np.concatenate([np.load(p)["frames"] for p in r6]); lv = np.concatenate([np.load(p)["lvl"] for p in r6])
        o = np.argsort(fr); fr, lv = fr[o], lv[o]
        f_on = int((ana.get("onset") or {}).get("frame") or fr[-1])
        tq = (fr - 1) / 24.0
        m = (fr <= f_on) & (lv > -900) & (tq >= 0.5 - 1e-9)        # 1 コマ目（初めの水面の VDB）と 2 コマ目の段（粒子の水面のずれ 0.07〜0.12 m）を除く
        ref_m = m & (tq <= 1.0 + 1e-9)
        P = cfg["parms"]; spec = GC.bed_spec(cfg)
        sp = cfg.get("solitary_npz")
        ef = CF.eta_from_npz(sp) if sp and os.path.exists(sp) else (lambda xq: np.zeros_like(xq))
        _, V = CF.count_particles(spec, float(P["Lx"]), float(P["W"]), float(P.get("dp", 0.5)), ef, zb=float(P.get("zb", GC.Z_BOTTOM)),
                                  bed_gap=float(P.get("bed_gap", 0.5)))
        Ar = float(P["Lx"]) * float(P["W"])
        if m.sum() > 2 and ref_m.any():
            ref = float(np.median(lv[ref_m]))
            d = float(np.max(np.abs(lv[m] - ref)))
            out["volume_drift"] = dict(level_change_max_m=d, frac=d * Ar / V, water_m3=V, ref_level_m=ref, frames=[int(fr[m][0]), int(fr[m][-1])],
                                       rule_ja="閉じた水槽の η_top の平均（level_box）の、t 0.5〜1.0 s の中央値からの動きの最大 × 箱の面積 ÷ 水の体積（巻き始めのコマまで。"
                                               "巻くと η_top が一価でない）。粒子から作る水面のずれ（FLIP46 §3 の 3：静かな所で 0.03〜0.05 m 上がる）も入るので、本当の水の量の変わりより大きく出る")
    out["wall_min"] = sum(float(r.get("wall_launch_s") or r.get("wall_total_s") or 0) for r in recs) / 60.0
    out["mp4"] = os.path.exists(os.path.join(rd, "video", "%s_4view.mp4" % cfg["run_id"]))
    return out


def judge(res, cfg, tg):
    """凍らせた目標（cfg の case.targets = plan_frozen.json の targets）で P1〜P5・H、または R0 の S1〜S3 の判定。"""
    P = cfg["parms"]
    strip = float(P["W"]) <= 12.0                         # R0 の板（半幅 6 m）
    J = {}
    on = res.get("onset") or {}
    Hc = on.get("eta_c")
    sh = res.get("shape_window") or {}
    if strip:
        rr = (cfg.get("case") or {}).get("r0_rule") or {}
        s1 = rr.get("S1", {}); s2 = rr.get("S2", {}); s3 = rr.get("S3", {})
        J["S1"] = bool(on and on["xc"] <= s1.get("x_max_m", 330) and on["t"] <= s1.get("t_max_s", 17.5))
        J["S2"] = bool(sh.get("chord_max") is not None and sh["chord_max"] >= s2.get("chord_min_deg", 55))
        J["S3"] = bool(sh.get("lip_max") is not None and sh["lip_max"] >= s3.get("lip_min", 0.2) and (sh.get("hood_max") or 0) >= s3.get("hood_min", 0.1))
        J["R0_rule_A0p4"] = bool((not J["S1"]) or (sh.get("chord_max") is None or sh["chord_max"] < 45.0))
    else:
        p1 = tg.get("P1", {})
        J["P1"] = bool(on and on["xc"] <= p1.get("x_max_m", 330) and on["t"] <= p1.get("t_max_s", 17.5))
        w = res.get("widths") or {}
        J["P2"] = bool(w.get("onset_over_Hc") is not None and w["onset_over_Hc"] <= tg.get("P2", {}).get("width_over_hc_max", 2.0))
        J["P3"] = bool(w.get("max_overturn_over_Hc") is not None and w["max_overturn_over_Hc"] <= tg.get("P3", {}).get("width_over_hc_max_overturn", 2.5)
                       and (w.get("touchdown_over_Hc") is None or w["touchdown_over_Hc"] <= tg.get("P3", {}).get("width_over_hc_touchdown", 3.0)))
        J["P3_touchdown_read"] = w.get("touchdown_over_Hc") is not None
        lo = (res.get("lateral_key") or {}).get("onset") or {}
        J["P4a"] = bool(lo.get("ratio_side") is not None and lo["ratio_side"] >= tg.get("P4a", {}).get("ratio_min", 1.5))
        J["P4a_clear"] = bool(lo.get("ratio_side") is not None and lo["ratio_side"] >= tg.get("P4a", {}).get("ratio_clear", 2.0))
        J["P4b"] = bool(lo.get("ratio_4Hc") is not None and lo["ratio_4Hc"] >= tg.get("P4b", {}).get("ratio_4hc_min", 1.3)
                        and not res.get("rows_beyond_4Hc_overturned_before_touchdown", False))
        p5 = tg.get("P5", {})
        J["P5"] = bool(sh.get("chord_max") is not None and sh["chord_max"] >= p5.get("chord_min_deg", 55) and (sh.get("lip_max") or 0) >= p5.get("lip_min", 0.2)
                       and (sh.get("hood_max") or 0) >= p5.get("hood_min", 0.1))
        J["overall_P1_P5"] = bool(all(J[k] for k in ("P1", "P2", "P3", "P4a", "P4b", "P5")))
    h = res.get("health") or {}
    H = tg.get("H", {})
    J["H_bed_leak"] = bool((h.get("bed_leak_max") or {}).get("frac", 0.0) < H.get("bed_leak_frac_max", 1e-4))
    J["H_init_f2"] = bool((h.get("init_check_f2") or {}).get("rel_max") is not None and h["init_check_f2"]["rel_max"] <= H.get("init_check_rel_max", 0.06))
    J["H_still_offset"] = bool(h.get("still_offset_m") is not None and abs(h["still_offset_m"]) < H.get("still_offset_max_m", 0.1))
    J["H_volume"] = bool((h.get("volume_drift") or {}).get("frac") is not None and h["volume_drift"]["frac"] < H.get("volume_drift_max", 0.01))
    J["H_wall"] = bool(h.get("wall_min", 1e9) <= H.get("wall_max_min", 30.0))
    J["H_mp4"] = bool(h.get("mp4"))
    return J


def run(rd, opt=None):
    opt = opt or {}
    t_start = time.time()
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    ana = _ana(rd)
    if not ana:
        raise SystemExit("ana.json がない（先に py -3.10 -B g48_analyze.py %s）" % rd)
    rid = cfg["run_id"]; P = cfg["parms"]; W = float(P["W"]); Lx = float(P["x0"]) + float(P["Lx"])
    band = side_band(W)
    tg = ((cfg.get("case") or {}).get("targets")) or {}
    off = float(ana.get("still_level_offset_m") or 0.0)
    H = load_hf(rd)
    xs, ys, frames, tt = H["xs"], H["ys"], H["frames"], H["t"]
    x_hi = Lx - X_END_PAD
    every = int(opt.get("every", 6))
    sup_lat = None
    key = _key_frames(ana)
    on = ana.get("onset") or {}
    Hc = on.get("eta_c")
    f_last = key.get("touchdown") or key.get("max_overturn") or key.get("steepest") or int(frames[-1])
    f_last = min(int(frames[-1]), f_last + 12)

    def prof(i):
        c, xc = crest_profile(H["eta"][i], xs, X_MIN, x_hi)
        cs, _ = crest_profile(H["eta"][i], xs, X_MIN, min(X_SIDE_MAX, x_hi))
        return c - off, xc, cs - off
    series = []
    profiles = {}
    t_series0 = 8.0
    for i, f in enumerate(frames):
        if not (tt[i] >= t_series0 - 1e-9 and f <= f_last) and int(f) not in key.values():
            continue
        if (int(f) - 1) % every != 0 and int(f) not in key.values():
            continue
        c, xc, cs = prof(i)
        L_ = lateral(c, ys, cs, Hc=Hc if (Hc and f >= key.get("onset", 10 ** 9)) else None, band=band)
        L_.update(frame=int(f), t=float(tt[i]), x_crest_centre=float(xc[0]) if np.isfinite(xc[0]) else None)
        series.append(L_)
        profiles[int(f)] = dict(c=[round(float(v), 3) for v in c], xc=[round(float(v), 1) if np.isfinite(v) else None for v in xc])
    lat_key = {}
    for nm, f in key.items():
        ii = np.where(frames == f)[0]
        if len(ii):
            c, xc, cs = prof(int(ii[0]))
            L_ = lateral(c, ys, cs, Hc=Hc, band=band)
            L_.update(frame=int(f), t=float(tt[ii[0]]))
            # 2026-10-15 見直し（判定には使わない、読みの確かめ）：下流の壁 x 360 m で跳ね返った前の裾が横の端の頂に足される。
            # 線形の重ね合わせの見積もりで、横の頂が x 310 / 320 / 330 m の時に +3 / +7 / +20 %【計算】。横の頂の x と、x ≤ 320 m で読んだ c_side を並べる
            bm_ = (ys >= band[0]) & (ys <= band[1])
            cs320, xcs = crest_profile(H["eta"][int(ii[0])], xs, X_MIN, min(320.0, x_hi))
            _, xcs340 = crest_profile(H["eta"][int(ii[0])], xs, X_MIN, min(X_SIDE_MAX, x_hi))
            if bm_.any() and W > 12.0:
                s320 = float(np.nanmean(cs320[bm_] - off)) if np.isfinite(cs320[bm_]).any() else None
                L_["x_side_crest_m"] = float(np.nanmedian(xcs340[bm_])) if np.isfinite(xcs340[bm_]).any() else None
                L_["c_side_x320"] = s320
                L_["ratio_side_x320"] = (L_["c0"] / s320) if s320 and s320 > 0 else None
            lat_key[nm] = L_
            if nm == "onset":
                sol_ = cfg.get("solitary") or {}
                H0_ = float(sol_["H0_nd"]) * float(P.get("h0", GC.H0)) if sol_.get("H0_nd") is not None else None
                sup_lat = GS.lateral_extra(c, cs, ys, H0_, Hc=Hc)
                b_ = GC.bed_spec(cfg)
                sup_lat["P4a_side_band_in_channel"] = bool(b_.get("ch_h", 0.0) > 0 and band[0] >= b_["ch_y0"] - 2.0 * b_["ch_w"])
    # 包み：着水（なければ最後に読んだコマ）までの各 y の最大
    m = (frames <= f_last)
    env_c = np.nanmax(np.stack([prof(i)[0] for i in np.where(m)[0][::3]]), axis=0) if m.any() else None
    res = dict(run_id=rid, tool="g48_peak_metrics.py", date=time.strftime("%Y-%m-%d %H:%M:%S"), W=W, Lx=Lx, bed=cfg.get("bed"), solitary=cfg.get("solitary"),
               wave=cfg.get("wave"), campaign=(cfg.get("case") or {}).get("campaign"), queue_id=(cfg.get("case") or {}).get("queue_id"),
               still_offset_m=off, x_window=[X_MIN, x_hi], x_side_max=X_SIDE_MAX, side_band=list(band), key_frames=key,
               onset=dict(frame=on.get("frame"), t=on.get("t"), xc=on.get("xc"), eta_c=on.get("eta_c"), thmax=on.get("thmax")) if on else None,
               steepest=ana.get("steepest"), touchdown=dict(frame=(ana.get("touchdown") or {}).get("frame"), t=(ana.get("touchdown") or {}).get("t")) if ana.get("touchdown") else None,
               lateral_key=lat_key, series=series, envelope=lateral(env_c, ys, band=band) if env_c is not None else None,
               ys=[float(v) for v in ys], profiles_every=every, profiles=profiles)
    # 巻いた幅
    if on and "no-curl" not in opt and W >= 2.0:
        cs_ = curl_series(rd, ana)
        res["curl"] = cs_
        rows = {r["frame"]: r for r in cs_.get("rows", [])}

        def w_at(f):
            if f is None:
                return None
            if f in rows:
                return rows[f]["overturned_full_m"]
            k_ = [q for q in rows if abs(q - f) <= 1]
            return rows[k_[0]]["overturned_full_m"] if k_ else None
        sc = ana.get("short_crest") or {}
        w_on = (sc.get("onset") or {}).get("overturned_full_m")
        w_on = w_on if w_on is not None else w_at(key.get("onset"))
        w_mo = w_at(key.get("max_overturn")); w_td = (sc.get("touchdown") or {}).get("overturned_full_m")
        w_td = w_td if w_td is not None else w_at(key.get("touchdown"))
        okw = [r["overturned_full_m"] for r in rows.values() if r.get("overturned_full_m") is not None and (key.get("touchdown") is None or r["frame"] <= key["touchdown"])]
        # 2026-10-15 見直し：着水のコマでは真ん中（y 0.5 m）の行の thmax が 90° を切ることが多く、「y = 0 から続く」幅が 0 m と読める
        # （FLIP46 P05_FLIP：307 コマ 70 m → 309 コマ 12 m → 着水 310 コマ 0 m。覆いかぶさりの確かめは同じ時に 58〜62 m）。
        # 0 m で P3 の着水の条件が素通りで満たされないよう、判定には「着水の 0.25 s 前〜着水」の thmax の幅の最大を使う（読みそのものは touchdown_raw_m に残す）
        w_td_raw = w_td
        f_td = key.get("touchdown")
        if f_td is not None:
            near_td = [r["overturned_full_m"] for r in rows.values() if r.get("overturned_full_m") is not None and f_td - 6 <= r["frame"] <= f_td]
            if w_td_raw is not None:
                near_td.append(w_td_raw)
            w_td = max(near_td) if near_td else w_td_raw
        res["widths"] = dict(Hc=Hc, onset_m=w_on, max_overturn_m=w_mo, touchdown_m=w_td, touchdown_raw_m=w_td_raw,
                             touchdown_rule_ja="着水の 0.25 s 前〜着水のコマの thmax ≥ 90° の全幅の最大（着水のコマで真ん中の行が 90° を切ると 0 m と読めるため）",
                             max_before_touchdown_m=max(okw) if okw else None,
                             onset_over_Hc=(w_on / Hc) if (w_on is not None and Hc) else None,
                             max_overturn_over_Hc=(w_mo / Hc) if (w_mo is not None and Hc) else None,
                             touchdown_over_Hc=(w_td / Hc) if (w_td is not None and Hc) else None,
                             max_before_touchdown_over_Hc=(max(okw) / Hc) if (okw and Hc) else None)
        y4 = 4.0 * Hc if Hc else None
        beyond = [r for r in rows.values() if y4 and any(y >= y4 for y in (r.get("y_over90") or [])) and (key.get("touchdown") is None or r["frame"] <= key["touchdown"])]
        res["rows_beyond_4Hc_overturned_before_touchdown"] = bool(beyond)
        res["rows_beyond_4Hc_first"] = dict(frame=beyond[0]["frame"], y=[y for y in beyond[0]["y_over90"] if y >= y4][:5]) if beyond else None
        res["peel"] = peel(cs_, ana)
    # 形の量（真ん中の断面、巻き始め〜着水）
    shs = [r for r in ((ana.get("shape") or {}).get("series") or []) if "error" not in r]
    if shs:
        def mx(k):
            v = [r.get(k) for r in shs if isinstance(r.get(k), (int, float))]
            return max(v) if v else None
        res["shape_window"] = dict(frames=[shs[0]["frame"], shs[-1]["frame"]], chord_max=mx("face_chord_deg_01_05"), lip_max=mx("lip_thick_mid"),
                                   hood_max=mx("hood_area"), table=(ana.get("shape") or {}).get("table"))
    # 2D の基準（R0）
    ref = opt.get("ref2d")
    if not ref:
        a_ = (cfg.get("solitary") or {}).get("H0_nd")
        ref = GC.B48 + "/runs/R0_strip_RS_A%s/peak.json" % (("%g" % a_).replace(".", "p") if a_ is not None else "0p3")
    if os.path.isdir(ref):
        ref = os.path.join(ref, "peak.json")
    if os.path.exists(ref) and W > 12.0:
        r0 = json.load(open(ref, encoding="utf8"))
        h2 = (r0.get("onset") or {}).get("eta_c")
        res["focusing_gain"] = dict(ref=ref, Hc_2D=h2, Hc_3D=Hc, gain=(Hc / h2) if (Hc and h2) else None)
    res["health"] = health(rd, cfg, ana)
    res["judge"] = judge(res, cfg, tg)
    # 補いの読み（判定に使わない。R3 の試しの G0 の門だけが使う）
    res["supp_lateral"] = sup_lat
    try:
        sup = GS.supp(rd, ana, cfg)
        res["supp"] = sup
    except Exception as e:
        import traceback
        res["supp"] = dict(error=repr(e)[:300], traceback=traceback.format_exc()[-1500:])
    cs_ = cfg.get("case") or {}
    if cs_.get("campaign") == "R3" and W <= 12.0 and "error" not in res["supp"]:
        frz, pfrz = GS.load_frozen_r3()
        if frz:
            res["g0_gate"] = dict(GS.g0_gate(res, res["supp"], frz), plan=pfrz, queue_id=cs_.get("queue_id"))
        else:
            res["g0_gate"] = dict(note_ja="plan_R3_frozen.json が無いので G0 の門を読まない（%s）" % pfrz)
    res["elapsed_s"] = round(time.time() - t_start, 1)
    return res


# ======================================================================== 書く
def _n(v, f="%.2f"):
    return "—" if v is None else (f % v)


def plot(path, res, title):
    from PIL import Image, ImageDraw, ImageFont
    ys = np.array(res["ys"])
    curves = []
    cols = {"onset": (40, 90, 200), "max_overturn": (30, 150, 90), "touchdown": (130, 80, 170), "steepest": (40, 90, 200)}
    labs = {"onset": "巻き始め", "max_overturn": "最も巻いた", "touchdown": "着水", "steepest": "最も険しい（巻かない）"}
    for nm, f in res["key_frames"].items():
        p = res["profiles"].get(f) or res["profiles"].get(str(f))
        if p:
            curves.append(("%s（コマ %d）" % (labs.get(nm, nm), f), np.array([np.nan if v is None else v for v in p["c"]], float), cols.get(nm, (0, 0, 0))))
    if not curves:
        return None
    Wp, Hp = 1280, 720
    im = Image.new("RGB", (Wp, Hp), (250, 250, 247)); dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 24); f2 = ImageFont.truetype(FONT, 16); f3 = ImageFont.truetype(FONT, 14)
    dr.text((40, 14), title, fill=(20, 20, 20), font=f1)
    lo_ = res["lateral_key"].get("onset") or {}
    dr.text((40, 50), "c0/c_side %s、c0/c(4Hc) %s、盛り上がりの半分の幅 %s m（%s Hc）、巻いた全幅 ÷ Hc（巻き始め）%s" % (
        _n(lo_.get("ratio_side"), "%.2f"), _n(lo_.get("ratio_4Hc"), "%.2f"), _n(lo_.get("half_excess_width_m"), "%.0f"),
        _n(lo_.get("half_excess_width_over_Hc"), "%.1f"), _n((res.get("widths") or {}).get("onset_over_Hc"), "%.2f")), fill=(80, 80, 80), font=f2)
    L, R, T, B = 100, Wp - 290, 100, Hp - 80
    yy = np.concatenate([-ys[::-1], ys])
    allv = np.concatenate([c for _, c, _ in curves])
    hi = max(8.0, float(np.nanmax(allv)) + 0.5); lo = 0.0
    Y = lambda v: B - (v - lo) / (hi - lo) * (B - T)
    X = lambda v: L + (v - yy[0]) / (yy[-1] - yy[0]) * (R - L)
    for g in range(0, int(hi) + 1, 2):
        dr.line([(L, Y(g)), (R, Y(g))], fill=(225, 225, 225)); dr.text((L - 48, Y(g) - 9), "%d m" % g, fill=(90, 90, 90), font=f3)
    Hc = (res.get("onset") or {}).get("eta_c")
    if Hc:
        for mlt, colr in ((2, (200, 150, 60)), (4, (200, 90, 60))):
            for sgn in (-1, 1):
                xv = sgn * mlt * Hc
                if yy[0] <= xv <= yy[-1]:
                    dr.line([(X(xv), T), (X(xv), B)], fill=colr, width=1)
            if mlt * Hc <= yy[-1]:
                dr.text((X(mlt * Hc) + 3, T + 2), "%d Hc" % mlt, fill=colr, font=f3)
    sb = res.get("side_band") or list(SIDE_BAND)
    if ys[-1] >= sb[0] and res["W"] > 12.0:
        for sgn in (-1, 1):
            a_, b_ = sorted((X(sgn * sb[0]), X(sgn * min(sb[1], ys[-1]))))
            dr.rectangle([a_, B - 6, b_, B], fill=(170, 170, 170))
    dr.rectangle([L, T, R, B], outline=(120, 120, 120))
    dr.text(((L + R) / 2 - 130, B + 30), "横の位置 y（m、0 が真ん中、両側に写した）", fill=(60, 60, 60), font=f2)
    for i, (lab, c, col) in enumerate(curves):
        cc = np.concatenate([c[::-1], c])
        pts = [(X(a), Y(b)) for a, b in zip(yy, cc) if np.isfinite(b)]
        if len(pts) > 1:
            dr.line(pts, fill=col, width=3)
        dr.line([(R + 20, T + 20 + 28 * i), (R + 50, T + 20 + 28 * i)], fill=col, width=4)
        dr.text((R + 58, T + 10 + 28 * i), lab, fill=(30, 30, 30), font=f3)
    im.save(path)
    return path


def md(res):
    J = res["judge"]
    L = ["# %s：A 字の盛り上がりの読み（g48_peak_metrics.py、%s）" % (res["run_id"], res["date"]), ""]
    b = res.get("bed") or {}; s = res.get("solitary") or {}
    L.append("尾根 k %s・真ん中 1:%s・棚 %s m、孤立波 H0/h0 %s、半幅 %g m。高さは静かな水面のずれ %.3f m を引いた。頂は x %g〜%g m（横の端の帯は x ≤ %g m）。" % (
        b.get("k"), b.get("s"), b.get("h_sh"), s.get("H0_nd"), res["W"], res["still_offset_m"], res["x_window"][0], res["x_window"][1], res["x_side_max"]))
    if b.get("kind") not in (None, "ridge_shelf") or res.get("wave"):
        ex_ = []
        if b.get("k_end") is not None:
            ex_.append("先細り k %s → %s（x %s〜%s m）" % (b.get("k"), b.get("k_end"), b.get("xk1"), b.get("xk2")))
        if (b.get("ch_h") or 0) > 0:
            ex_.append("横の遠くの溝 %s m（|y| ≳ %s m、tanh の幅 %s m、x %s〜%s m で入る）" % (b.get("ch_h"), b.get("ch_y0"), b.get("ch_w"), b.get("ch_x0"),
                                                                    (b.get("ch_x0") or 0) + (b.get("ch_lx") or 0)))
        if (b.get("s1") or 0) > 0:
            ex_.append("段 1:%s → 1:%s を %s m → 1:%s（棚に x %s m で着く）" % (b.get("s1"), b.get("s2"), b.get("dL"), b.get("s1"), _n(b.get("shelf_x_axis_m"), "%.1f")))
        w_ = res.get("wave") or {}
        if w_.get("kind") == "nwave":
            ex_.append("前の谷 β %s（%.2f m、d %.1f m。定常な解ではない）" % (w_.get("beta"), w_.get("trough_amp_m", 0.0), w_.get("d_m", 0.0)))
        L.append("R3 の試しの選び：%s。海底の種類 %s、箱の底 %s m。" % ("、".join(ex_) or "なし", b.get("kind"), b.get("box_floor_zb_m", -17.0)))
    L.append("")
    on = res.get("onset")
    if on:
        L.append("- 巻き始め（真ん中 y 0.5 m の行、g48_analyze）：コマ %d、t %.3f s、x %.1f m、Hc %.2f m、thmax %.1f°。" % (on["frame"], on["t"], on["xc"], on["eta_c"], on["thmax"]))
    else:
        st = res.get("steepest") or {}
        L.append("- 巻き始めなし。最も険しいコマ：%s" % st)
    if res.get("touchdown"):
        L.append("- 着水：コマ %s、t %s s。" % (res["touchdown"]["frame"], _n(res["touchdown"]["t"], "%.3f")))
    fg = res.get("focusing_gain")
    if fg:
        L.append("- 集まりの利得 Hc_3D/Hc_2D：%s（2D の板 %s m、3D %s m）【測定】。" % (_n(fg.get("gain"), "%.3f"), _n(fg.get("Hc_2D")), _n(fg.get("Hc_3D"))))
    L += ["", "## 頂の高さの横の分け方（hf）", "",
          "| 時 | コマ | t（s） | c0（m） | c_side（m） | c0/c_side | c(2Hc)（m） | c0/c(4Hc) | 半分の幅（全幅 m） | ÷ Hc | 90% の幅（m） |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    labs = {"onset": "巻き始め", "max_overturn": "最も巻いた", "touchdown": "着水", "steepest": "最も険しい"}
    for nm, r in res["lateral_key"].items():
        L.append("| %s | %d | %.3f | %s | %s | %s | %s | %s | %s | %s | %s |" % (labs.get(nm, nm), r["frame"], r["t"], _n(r["c0"]), _n(r["c_side"]), _n(r["ratio_side"], "%.3f"),
                                                                       _n(r.get("c_2Hc")), _n(r.get("ratio_4Hc"), "%.3f"), _n(r["half_excess_width_m"], "%.1f"),
                                                                       _n(r.get("half_excess_width_over_Hc"), "%.2f"), _n(r["w90_m"], "%.1f")))
    e = res.get("envelope")
    if e:
        L.append("| 包み（着水まで） | — | — | %s | %s | %s | — | — | %s | — | %s |" % (_n(e["c0"]), _n(e["c_side"]), _n(e["ratio_side"], "%.3f"),
                                                                             _n(e["half_excess_width_m"], "%.1f"), _n(e["w90_m"], "%.1f")))
    lo_ = res["lateral_key"].get("onset") or {}
    if lo_.get("x_side_crest_m") is not None:
        L.append("")
        L.append("下流の壁の確かめ（判定に使わない）：巻き始めの横の端の頂は x %s m。x ≤ 320 m で読むと c_side %s m、c0/c_side %s"
                 "（横の頂が壁に近い x ≥ 320 m なら、壁で跳ね返った前の裾が c_side を 7〜20 %% 押し上げる【計算、線形の見積もり】）。" % (
                     _n(lo_.get("x_side_crest_m"), "%.0f"), _n(lo_.get("c_side_x320")), _n(lo_.get("ratio_side_x320"), "%.3f")))
    w = res.get("widths")
    if w:
        L += ["", "## 巻いた全幅（r4 の各 y の断面、thmax ≥ 90° が y = 0 から続く範囲 × 2）", "",
              "| 時 | 全幅（m） | ÷ Hc |", "| --- | --- | --- |",
              "| 巻き始め | %s | %s |" % (_n(w["onset_m"], "%.1f"), _n(w["onset_over_Hc"])),
              "| 最も巻いた | %s | %s |" % (_n(w["max_overturn_m"], "%.1f"), _n(w["max_overturn_over_Hc"])),
              "| 着水（0.25 s 前〜着水の最大。着水のコマだけの読み %s m） | %s | %s |" % (_n(w.get("touchdown_raw_m"), "%.1f"), _n(w["touchdown_m"], "%.1f"), _n(w["touchdown_over_Hc"])),
              "| 着水までの最大 | %s | %s |" % (_n(w["max_before_touchdown_m"], "%.1f"), _n(w["max_before_touchdown_over_Hc"]))]
        pe = res.get("peel") or {}
        L.append("")
        L.append("剥がれ：横の速さ v %s m/s、頂の速さ %s m/s、剥がれ角 %s°（90° は横へ広がらない）。%s" % (
            _n(pe.get("v_lat_mps")), _n(pe.get("c_crest_mps")), _n(pe.get("peel_angle_deg"), "%.0f"), pe.get("note_ja", "")))
        if res.get("rows_beyond_4Hc_first"):
            L.append("着水の前に |y| ≥ 4 Hc の行が巻いた：%s" % res["rows_beyond_4Hc_first"])
        cr = (res.get("curl") or {}).get("rows") or []
        if cr:
            L += ["", "| コマ | t（s） | 頂の x（m） | 全幅 thmax（m） | 全幅 覆いかぶさり（m） |", "| --- | --- | --- | --- | --- |"]
            for r in cr[::2]:
                L.append("| %d | %.3f | %.1f | %s | %s |" % (r["frame"], r["t"], r["xc"], _n(r.get("overturned_full_m"), "%.0f"), _n(r.get("overhang_full_m"), "%.0f")))
    sw = res.get("shape_window")
    if sw:
        L += ["", "形（真ん中の断面、コマ %d〜%d の最大）：前の面の弦 %s°（原画 64.3°）、唇 ÷ η_c %s（0.35）、覆い ÷ η_c² %s（0.186）。" % (
            sw["frames"][0], sw["frames"][1], _n(sw["chord_max"], "%.1f"), _n(sw["lip_max"], "%.3f"), _n(sw["hood_max"], "%.3f"))]
    sup = res.get("supp") or {}
    if sup and "error" not in sup:
        gate = res.get("g0_gate") if (res.get("g0_gate") or {}).get("items") else None
        L.append(GS.md(sup, res.get("supp_lateral"), gate, (res.get("g0_gate") or {}).get("queue_id")))
        if (res.get("g0_gate") or {}).get("note_ja") and not gate:
            L.append(res["g0_gate"]["note_ja"])
    elif sup.get("error"):
        L += ["", "補いの読みが失敗した：%s" % sup["error"]]
    h = res.get("health") or {}
    L += ["", "## 判定（凍らせた目標 plan/plan_frozen.json）", ""]
    for k, v in J.items():
        L.append("- %s：%s" % (k, "はい" if v else "いいえ"))
    L += ["", "健全さ：海底より下の粒子 %s、2 コマ目の流速の差 最大 %s、静かな水面のずれ %s m、水の量のずれ %s、時間 %.1f 分、mp4 %s。" % (
        (h.get("bed_leak_max") or {}).get("frac"), _n((h.get("init_check_f2") or {}).get("rel_max"), "%.3f"), _n(h.get("still_offset_m"), "%.3f"),
        _n((h.get("volume_drift") or {}).get("frac"), "%.4f"), h.get("wall_min", 0.0), h.get("mp4")), "",
        "見た目の良し悪しは数でなく利用者が決める。選んだ物（振幅と尾根）が盛り上がりの出る所と横の高さを決めている。計算した物は真ん中の伸び・崩れ方・巻きの幅・剥がれ・唇。", ""]
    return "\n".join(L) + "\n"


def write(res, rd):
    rd = os.path.abspath(rd).replace("\\", "/")
    inside = (rd.lower() + "/").startswith(GC.B48.lower() + "/")
    if not inside:
        print("（FLIP48 の外の記録なので書かない）")
        return None
    json.dump(res, open(os.path.join(rd, "peak.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    open(os.path.join(rd, "PEAK_ja.md"), "w", encoding="utf8").write(md(res))
    os.makedirs(os.path.join(rd, "video"), exist_ok=True)
    plot(os.path.join(rd, "video", "%s_peak_lateral.png" % res["run_id"]), res, "%s：頂の高さの横の分け方（A 字の盛り上がり）" % res["run_id"])
    return rd


def selftest():
    """答えの分かった合成の値で読みを確かめる（numpy だけ、1 秒）。"""
    out = {}
    ys = np.arange(85) + 0.5
    sig = 10.0
    c = 5.0 + 3.0 * np.exp(-(ys / sig) ** 2)
    L_ = lateral(c, ys, Hc=8.0)
    out["half_excess_width"] = dict(got=L_["half_excess_width_m"], true=2 * sig * math.sqrt(math.log(2.0)))
    bm = (ys >= SIDE_BAND[0]) & (ys <= SIDE_BAND[1])
    out["ratio_side"] = dict(got=L_["ratio_side"], true=float(c[0] / c[bm].mean()))
    y9 = sig * math.sqrt(-math.log((0.9 * 8.0 - 5.0) / 3.0))
    out["w90"] = dict(got=L_["w90_m"], true=2 * y9)
    out["c_4Hc"] = dict(got=L_["c_4Hc"], true=5.0 + 3.0 * math.exp(-(32.0 / sig) ** 2))
    # 頂の読み：x の向きの 1 格子の針は除き、本当の頂（x 250 m）を拾う
    xs = np.arange(0.0, 360.0) + 0.5
    eta = np.zeros((len(ys), len(xs))) + c[:, None] * np.exp(-((xs[None, :] - 250.0) / 8.0) ** 2)
    eta[:, 200] = 30.0                                   # 1 格子の水の針
    cc, xc = crest_profile(eta, xs, 150.0, 345.0)
    out["crest_profile"] = dict(max_err=float(np.abs(cc - c).max()), xc=float(np.median(xc)))

    # 覆いかぶさり：y < 6 m の行に唇（水・空気・水）、全部の行の海底のすぐ上に 1 格子の空気の層（数えない）
    class R:
        pass
    nz, ny, nx = 20, 26, 60
    yv = -9.5 + np.arange(ny); xv = 280.5 + np.arange(nx); zl = 0.5 + np.arange(nz)
    S = np.where(yv[None, :, None] < 0.0, -1.0, 1.0) * np.ones((nz, ny, nx))
    bed = -6.0
    S[:, (yv > bed) & (yv < bed + 1.0), :] = 1.0          # 海底のすぐ上の空気の層（偽物）
    for k in range(nz):
        if zl[k] < 6.0:
            S[k][np.ix_((yv > 4.0) & (yv < 6.0), (xv > 300.0) & (xv < 306.0))] = -1.0   # 唇（空気の上の水）
    rd_ = R(); rd_.b = {1: None}
    rd_.get = lambda f: (S, dict(x0=xv[0], dx=1.0, y0=yv[0], dy=1.0, z0=zl[0], dz=1.0), 0.0)
    w, ov = r4_overhang_width(rd_, 1, 300.0, lambda x, y: np.full(np.shape(x), bed), 0.0, 0.0)
    out["overhang_width"] = dict(got=w, true=12.0, rows=len(ov))
    ok = (abs(out["half_excess_width"]["got"] - out["half_excess_width"]["true"]) < 0.3 and abs(out["ratio_side"]["got"] - out["ratio_side"]["true"]) < 1e-9
          and abs(out["w90"]["got"] - out["w90"]["true"]) < 0.3 and abs(out["c_4Hc"]["got"] - out["c_4Hc"]["true"]) < 0.05
          and out["crest_profile"]["max_err"] < 0.05 and abs(out["crest_profile"]["xc"] - 250.5) <= 1.0 and out["overhang_width"]["got"] == 12.0)
    out["ok"] = bool(ok)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        print(json.dumps(selftest(), ensure_ascii=False, indent=1)); sys.exit(0)
    opt = {}
    rds = []
    for a in sys.argv[1:]:
        if a.startswith("--"):
            k, _, v = a[2:].partition("="); opt[k] = v if v else "1"
        else:
            rds.append(a)
    for rd in rds:
        r = run(rd, opt)
        write(r, rd)
        print(md(r))
