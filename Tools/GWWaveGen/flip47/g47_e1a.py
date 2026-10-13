# -*- coding: utf-8 -*-
"""FLIP47 E1a のまとめ：いくつかの計算（g47_analyze を先にかけた物）を並べ、論文（Feddersen ら 2024、風なし）と原画の物差しと比べる。
py -3.10 -B で走らせる（numpy・scikit-image・PIL）。読むだけ。書くのは --out（Unity/Build/FLIP47 の中だけ）。

  py -3.10 -B g47_e1a.py --out=<FLIP47 の中の置き場所> <記録1> <記録2> ...   （記録は runs/<id>。<記録>/ana47/g47_ana.json を読む）
     [--ref=<全部の領域の記録の id>]   短い領域との差（%）の基準。既定は名前に full と同じ粒子を含む物
→ <out>/e1a_compare.json、<out>/e1a_crest_track.png（頂の高さと位置、海底）、<out>/e1a_touchdown_vs_paper.png（着水の断面を論文の図 5b に重ねる）、
  <out>/e1a_ratio_to_paper.png（論文の値に対する比）、<out>/e1a_table.md（表）
"""
import sys, os, json, math, glob
sys.dont_write_bytecode = True
import numpy as np
from skimage import measure
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B47 = REPO + "/Unity/Build/FLIP47"
H0 = 19.0
G = 9.80665
PAPER = dict(Hb_h0=0.64, xbp_h0=42.05, xbp_wind=(40.9, 42.2), t_tilde=19.96, AJ_Hb2=0.219, AO_Hb2=0.352, W_L=0.300, W_L_g47=0.351,
             theta_o_deg=29.0, jet_width_h0=0.05, jet_width_h0_s05_g47=0.085, jet_width_h0_s09_g47=0.049)
PAPER_MASK = B47 + "/lit/F24_fig5b_Re0_t19.96.png"       # g47_lit_ruler.py：x 38〜43 h0・z −1.0〜1.4 h0、0.002 h0、上の行が z 1.4
PRINT = dict(face_chord_deg_01_05=64.3, front_x01_rel=0.254, gap_max=0.541, lip_thick_mid=0.350, hood_area=0.186)
BG = (247, 247, 244); TXT = (25, 25, 25); SUB = (95, 95, 92); LINE = (150, 150, 150); GRID = (225, 225, 220)
COLS = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (148, 103, 189), (255, 127, 14), (23, 190, 207)]
FONT = "C:/Windows/Fonts/YuGothM.ttc"; FONTB = "C:/Windows/Fonts/YuGothB.ttc"


def font(sz, b=False):
    try:
        return ImageFont.truetype(FONTB if b else FONT, sz)
    except Exception:
        return ImageFont.load_default()


def guard(p):
    a = os.path.abspath(p).replace("\\", "/")
    if not a.lower().startswith(B47.lower() + "/"):
        raise SystemExit("書く場所は Unity/Build/FLIP47 の中だけ：%s" % a)
    return a


def jload(p):
    return json.load(open(p, encoding="utf8"))


def run_info(rd):
    """記録の置き場所から、条件・費用・初めのコマの確かめ・静かな水面・漏れ・読みの結果を集める。"""
    rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
    rid = os.path.basename(rd)
    cfg = jload(rd + "/cfg.json")
    ana = jload(rd + "/ana47/g47_ana.json")
    rcs = sorted(glob.glob(rd + "/run_c*.json"))
    R = [jload(p) for p in rcs]
    o = dict(id=rid, rd=rd, domain=cfg.get("domain"), dp=float(cfg["parms"]["dp"]), vox=2.0 * float(cfg["parms"]["dp"]),
             x_range=[float(cfg["box"]["x0"]), float(cfg["box"]["x1"])], x0_crest=float(cfg["solitary"]["x0"]),
             wave=cfg["solitary"].get("kind"), a_over_h=cfg["solitary"].get("a_over_h"))
    o["launches"] = len(R)
    o["wall_s"] = float(sum(float(r.get("wall_total_s") or 0) for r in R))
    o["particles_max"] = max(int(r.get("particles_max") or 0) for r in R)
    o["rss_peak_gb"] = max(float(r.get("rss_peak_gb") or 0) for r in R)
    o["substeps_min_max"] = [min(r["substeps_min_max"][0] for r in R), max(r["substeps_min_max"][1] for r in R)]
    o["f_end_done"] = int(R[-1].get("f_end_done") or 0)
    o["stopped"] = R[-1].get("stopped")
    # 初めのコマ（t = 0）の格子の流速と GN の式の差
    ic = None
    for r in R:
        ic = ic or (r.get("info") or {}).get("init_check")
    rows = []
    if ic:
        for blk in ic:
            for row in blk.get("rows", []):
                rows.append(dict(frame=blk["frame"], t=blk["t"], dx=row["dx"], y=row["y"], u_gn=row["u_gn"], w_gn=row["w_gn"],
                                 u_grid=row.get("u_grid"), w_grid=row.get("w_grid"), u_part=row.get("u_part"), w_part=row.get("w_part")))
    f1 = [q for q in rows if q["frame"] == 1]
    if f1:
        o["frame0"] = dict(
            n_points=len(f1),
            max_abs_du_grid=max(abs(q["u_grid"] - q["u_gn"]) for q in f1),
            max_abs_dw_grid=max(abs(q["w_grid"] - q["w_gn"]) for q in f1),
            max_abs_du_part=max(abs(q["u_part"] - q["u_gn"]) for q in f1 if q["u_part"] is not None),
            max_abs_dw_part=max(abs(q["w_part"] - q["w_gn"]) for q in f1 if q["w_part"] is not None),
            crest_deep=[dict(y=q["y"], u_grid=q["u_grid"], u_gn=q["u_gn"]) for q in f1 if q["dx"] == 0.0],
            front_deep=[dict(y=q["y"], w_grid=q["w_grid"], w_gn=q["w_gn"]) for q in f1 if q["dx"] > 0],
            later=[dict(frame=fr, max_abs_du=max(abs(q["u_grid"] - q["u_gn"]) for q in rows if q["frame"] == fr),
                        max_abs_dw=max(abs(q["w_grid"] - q["w_gn"]) for q in rows if q["frame"] == fr))
                   for fr in sorted(set(q["frame"] for q in rows)) if fr != 1])
    so = None
    for r in R:
        v = (r.get("info") or {}).get("still_offset_online")
        if v and v.get("value") is not None:
            so = v
    o["still_offset_m"] = so.get("value") if so else ana.get("still_offset_m")
    lk = []
    for r in R:
        lk += (r.get("info") or {}).get("leak") or []
    o["leak"] = dict(n_checks=len(lk), max_below_bed=max([q.get("n_below_bed", 0) for q in lk] or [0]),
                     max_out_x=max([q.get("n_out_x", 0) for q in lk] or [0]), max_out_z=max([q.get("n_out_z", 0) for q in lk] or [0]),
                     min_gap_m=min([q.get("gap_min", 9) for q in lk] or [None]))
    # 一番上の水面の積分 ∫(η − ずれ)dx（板の 4 層の平均。水の量そのものではなく、面の作りの膨らみも入る）
    try:
        hfs = sorted(glob.glob(rd + "/hf_c*.npz"))
        E, T, F = [], [], []
        for p in hfs:
            d = np.load(p)
            E.append(np.nanmean(d["eta"], axis=1)); T.append(d["t"]); F.append(d["frames"])
            xh = d["x"]
        E = np.concatenate(E); T = np.concatenate(T); F = np.concatenate(F)
        _, ui = np.unique(F, return_index=True)
        E, T, F = E[ui], T[ui], F[ui]
        dxh = float(xh[1] - xh[0])
        V = np.nansum(E - float(o["still_offset_m"] or 0.0), axis=1) * dxh
        i2 = int(np.argmin(np.abs(F - 2)))
        tdf = (ana.get("touchdown") or {}).get("frame") or int(F[-1])
        it = int(np.argmin(np.abs(F - tdf)))
        o["surface_integral"] = dict(rule_ja="∫(η − 静かな水面のずれ)dx。記録の x の範囲全部（短い領域は 380〜893 m）。2 コマ目と着水のコマ",
                                     m2_frame2=float(V[i2]), m2_touchdown=float(V[it]), t_touchdown=float(T[it]),
                                     gain_pct=float(100.0 * (V[it] - V[i2]) / V[i2]))
    except Exception as e:
        o["surface_integral"] = dict(error=str(e))
    # 読みの結果
    pm = ana.get("paper_measures") or {}
    on = ana.get("onset") or {}
    td = ana.get("touchdown") or {}
    at = ana.get("at") or {}
    sc = ana.get("score") or {}
    o["onset"] = dict(frame=on.get("frame"), t=on.get("t"), t_tilde=on.get("t_tilde"), x_vert_h0=on.get("x_vert_h0"),
                      xc_h0=on.get("xc_h0"), Hb_onset_h0=on.get("Hb_onset_h0"))
    o["eta_max_before_onset"] = ana.get("eta_max_before_onset")
    o["touchdown"] = dict(frame=td.get("frame"), t=td.get("t"), by=td.get("by"), prev_frame_gap_m=td.get("prev_frame_gap_low_m"),
                          t_tilde=pm.get("t_tilde"), t_tilde_if_x0_15h0=pm.get("t_tilde_if_x0_15h0"))
    o["paper_measures"] = {k: pm.get(k) for k in ("Hb_h0", "xbp_h0", "xbp_how", "AJ_Hb2", "AO_Hb2", "cavity_how", "W_L", "theta_o_deg", "L_Hb",
                                                   "jet_width_h0", "jet_width_09_h0", "jet_width_Hb", "jet_width_vox", "jet_width_profile_m",
                                                   "AJ_m2", "AO_m2", "Hb_m", "xbp_m", "fit_rms_over_L", "AO_fit_over_direct", "Hb_max_before_td_m")}
    rul = {}
    for k in ("onset", "touchdown", "max_overturn", "best_score"):
        a = at.get(k) or {}
        s = a.get("s52") or {}
        rul[k] = dict(frame=a.get("frame"), t=a.get("t"), eta_c=a.get("eta_c"),
                      **{q: s.get(q) for q in ("face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area", "reach", "tip_z")})
        rul[k]["score"] = (sc.get("at") or {}).get(k)
    o["ruler"] = rul
    o["score_best"] = sc.get("best")
    o["coarse"] = ana.get("coarse")
    sh = (o["x0_crest"] / H0 - 15.0) / 1.265          # 頂を 15 h0 に置いた時の時刻にそろえる（GN の速さ）
    TS = math.sqrt(H0 / G)
    o["series"] = [dict(frame=q["frame"], tt=q["t"] / TS + sh, eta=q.get("eta"), AJ=(q.get("ov") or {}).get("AJ_m2"),
                        AO=(q.get("ov") or {}).get("AO_m2"), reach=(q.get("ov") or {}).get("reach_m"),
                        gap=(q.get("ov") or {}).get("gap_low_m"), contact=(q.get("ov") or {}).get("contact"))
                   for q in (ana.get("fine") or [])]
    o["selected_frames"] = ana.get("selected_frames")
    o["masks"] = rd + "/ana47/%s_masks.npz" % rid
    o["bed"] = cfg.get("bed")
    return o


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return 100.0 * (a - b) / b


def compare_short_full(runs, ref_id=None):
    """同じ粒子の full と short の差（%）。計画 §5.1：崩れる位置と Hb が 5% 以内なら short を使ってよい。"""
    out = []
    for s in runs:
        if s["domain"] != "short":
            continue
        f = [r for r in runs if r["domain"] == "full" and abs(r["dp"] - s["dp"]) < 1e-9]
        if ref_id:
            f = [r for r in runs if r["id"] == ref_id] or f
        if not f:
            continue
        f = f[0]
        d = dict(short=s["id"], full=f["id"], dp=s["dp"])
        pairs = [("onset_x_vert_h0", s["onset"]["x_vert_h0"], f["onset"]["x_vert_h0"]),
                 ("Hb_onset_h0", s["onset"]["Hb_onset_h0"], f["onset"]["Hb_onset_h0"]),
                 ("xbp_h0", s["paper_measures"]["xbp_h0"], f["paper_measures"]["xbp_h0"]),
                 ("Hb_h0", s["paper_measures"]["Hb_h0"], f["paper_measures"]["Hb_h0"]),
                 ("AJ_Hb2", s["paper_measures"]["AJ_Hb2"], f["paper_measures"]["AJ_Hb2"]),
                 ("AO_Hb2", s["paper_measures"]["AO_Hb2"], f["paper_measures"]["AO_Hb2"]),
                 ("t_tilde_touchdown_x0_15h0", s["touchdown"]["t_tilde_if_x0_15h0"], f["touchdown"]["t_tilde_if_x0_15h0"])]
        for k, a, b in pairs:
            d[k] = dict(short=a, full=b, diff_pct=pct(a, b))
        d["within_5pct_break_and_Hb"] = all(abs(d[k]["diff_pct"]) <= 5.0 for k in ("onset_x_vert_h0", "xbp_h0", "Hb_h0", "Hb_onset_h0")
                                            if d[k]["diff_pct"] is not None)
        out.append(d)
    return out


# ------------------------------------------------------------------ 図
def axes(dr, x0, y0, w, h, xl, xr, yb, yt, xt, yt_, xlab, ylab, fx="%g", fy="%g"):
    dr.rectangle([x0, y0, x0 + w, y0 + h], outline=LINE)
    X = lambda v: x0 + (v - xl) / (xr - xl) * w
    Y = lambda v: y0 + (yt - v) / (yt - yb) * h
    for v in xt:
        dr.line([(X(v), y0), (X(v), y0 + h)], fill=GRID)
        dr.text((X(v) - 12, y0 + h + 4), fx % v, fill=SUB, font=font(13))
    for v in yt_:
        dr.line([(x0, Y(v)), (x0 + w, Y(v))], fill=GRID)
        dr.text((x0 - 46, Y(v) - 8), fy % v, fill=SUB, font=font(13))
    dr.rectangle([x0, y0, x0 + w, y0 + h], outline=LINE)
    dr.text((x0 + w / 2 - 60, y0 + h + 22), xlab, fill=TXT, font=font(14))
    dr.text((x0 - 50, y0 - 24), ylab, fill=TXT, font=font(14))
    return X, Y


def label_of(r):
    return "%s（粒子 %.3g m、%s）" % (r["id"], r["dp"], "全部の領域 x 0〜1130 m" if r["domain"] == "full" else "短い領域 x 380〜893 m")


def fig_crest(runs, out_png):
    W, Hh = 1500, 900
    im = Image.new("RGB", (W, Hh), BG); dr = ImageDraw.Draw(im)
    dr.text((20, 10), "E1a：頂の高さと位置（静かな水面から、h0 = 19 m で割った値）と海底。重力だけの FLIP、2D の板", fill=TXT, font=font(20, True))
    dr.text((20, 40), "●＝巻き始め（前の面に鉛直の接線。私たちの読み）、◆＝着水（論文の決まり）の xbp と Hb。灰の帯＝論文の風の 8 本の xbp 40.9〜42.2 h0、★＝論文の風なし（xbp 42.05、Hb 0.64）",
            fill=SUB, font=font(14))
    x0, y0, w, h = 110, 100, 1150, 480
    xl, xr = 14.0, 46.0
    X, Y = axes(dr, x0, y0, w, h, xl, xr, 0.4, 0.8, range(14, 47, 2), [0.4, 0.5, 0.6, 0.7, 0.8], "頂の位置 x / h0", "η_c / h0", fy="%.1f")
    dr.rectangle([X(40.9), y0 + 1, X(42.2), y0 + h - 1], fill=(228, 228, 228))
    for k, r in enumerate(runs):
        c = COLS[k % len(COLS)]
        co = np.array(r["coarse"], float)
        co = co[np.argsort(co[:, 0])]
        if r["touchdown"]["frame"]:
            co = co[co[:, 0] <= r["touchdown"]["frame"]]
        xs = co[:, 2] / H0; es = co[:, 3] / H0
        # 頂の位置は 1 格子で飛ぶので 5 コマの中央値でならす
        from scipy.ndimage import median_filter
        xs = median_filter(xs, 5, mode="nearest"); es = median_filter(es, 5, mode="nearest")
        P = [(X(a), Y(b)) for a, b in zip(xs, es) if xl <= a <= xr and 0.4 <= b <= 0.8]
        if len(P) > 1:
            dr.line(P, fill=c, width=2)
        on = r["onset"]
        if on.get("x_vert_h0") is not None:
            u, v = X(on["x_vert_h0"]), Y(on["Hb_onset_h0"])
            dr.ellipse([u - 6, v - 6, u + 6, v + 6], fill=c, outline=(0, 0, 0))
        pm = r["paper_measures"]
        if pm.get("xbp_h0") is not None:
            u, v = X(pm["xbp_h0"]), Y(pm["Hb_h0"])
            dr.polygon([(u, v - 8), (u + 8, v), (u, v + 8), (u - 8, v)], fill=c, outline=(0, 0, 0))
        ly = y0 + 10 + 24 * k
        dr.line([(x0 + 14, ly + 10), (x0 + 44, ly + 10)], fill=c, width=3)
        dr.text((x0 + 50, ly), label_of(r), fill=TXT, font=font(14))
    u, v = X(PAPER["xbp_h0"]), Y(PAPER["Hb_h0"])
    star = [(u + 10 * math.cos(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45), v - 10 * math.sin(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45)) for i in range(10)]
    dr.polygon(star, fill=(250, 200, 0), outline=(0, 0, 0))
    # 海底
    y1, h1 = y0 + h + 70, 150
    X2, Y2 = axes(dr, x0, y1, w, h1, xl, xr, -1.05, 0.05, range(14, 47, 2), [-1.0, -0.5, 0.0], "x / h0", "z / h0", fy="%.1f")
    b = np.array(runs[0]["bed"], float)
    xx = np.linspace(xl, xr, 600)
    zz = -np.interp(xx * H0, b[:, 0], b[:, 1]) / H0
    poly = [(X2(a), Y2(z)) for a, z in zip(xx, zz)] + [(X2(xr), Y2(-1.05)), (X2(xl), Y2(-1.05))]
    dr.polygon(poly, fill=(196, 178, 140))
    dr.line([(X2(xl), Y2(0)), (X2(xr), Y2(0))], fill=(80, 120, 170), width=1)
    dr.text((X2(30.2), Y2(-0.95)), "勾配 0.0693（30〜39.08 h0）", fill=TXT, font=font(13))
    dr.text((X2(39.4), Y2(-0.5)), "棚 0.371 h0（7.05 m）", fill=TXT, font=font(13))
    for k, r in enumerate(runs):
        c = COLS[k % len(COLS)]
        a0, a1 = r["x_range"][0] / H0, min(r["x_range"][1] / H0, xr)
        yy = y1 + h1 + 40 + 0 * k
    im.save(out_png)
    return out_png


def paper_mask():
    A = np.asarray(Image.open(PAPER_MASK).convert("L"))[::-1] > 127      # 下の行が z −1.0
    xs = 38.0 + 0.002 * (np.arange(A.shape[1]) + 0.5)
    zs = -1.0 + 0.002 * (np.arange(A.shape[0]) + 0.5)
    return A, xs, zs


def contours_h0(M, X, Z):
    """水の塗りの境の線（h0 で割る）。塗りの窓の縁（記録の窓の端）に沿う所は除き、途切れた所で線を分ける。"""
    out = []
    ny, nx = M.shape
    for c in measure.find_contours(np.pad(M, 1).astype(float), 0.5):
        edge = (c[:, 1] < 1.0) | (c[:, 1] > nx) | (c[:, 0] < 1.0) | (c[:, 0] > ny)
        x = X[0] + (c[:, 1] - 1) * (X[1] - X[0]); z = Z[0] + (c[:, 0] - 1) * (Z[1] - Z[0])
        P = np.stack([x / H0, z / H0], 1)
        ok = ~edge
        i = 0
        while i < len(P):
            if not ok[i]:
                i += 1; continue
            j = i
            while j < len(P) and ok[j]:
                j += 1
            if j - i > 1:
                out.append(P[i:j])
            i = j
    return out


def poly_in(c, sh, xl, xr, zb, zt):
    """窓の中の点だけを、続く所ごとの線にする。"""
    ok = (c[:, 0] + sh >= xl) & (c[:, 0] + sh <= xr) & (c[:, 1] >= zb) & (c[:, 1] <= zt)
    segs, i = [], 0
    while i < len(c):
        if not ok[i]:
            i += 1; continue
        j = i
        while j < len(c) and ok[j]:
            j += 1
        if j - i > 1:
            segs.append(c[i:j])
        i = j
    return segs


def fig_touchdown(runs, out_png):
    PA, PX, PZ = paper_mask()
    pc = contours_h0(PA, PX * H0, PZ * H0)
    W, Hh = 1520, 1010
    im = Image.new("RGB", (W, Hh), BG); dr = ImageDraw.Draw(im)
    dr.text((20, 10), "E1a：着水のコマの断面を論文の図 5b（風なし、t̃ 19.96、2 相・表面張力 Bo 4000）に重ねる。縦横同じ倍率、h0 で割った値", fill=TXT, font=font(20, True))
    dr.text((20, 40), "灰の塗り＝論文の図 5b の水と海底（g47_lit_ruler が図のベクターから読んだ形）。色の線＝私たちの着水のコマの水面（0.05 m の水の格子、g47_analyze の masks）。私たちは水だけ・重力だけ・h0 19 m",
            fill=SUB, font=font(14))
    panels = [("(a) 置いたままの x（論文の座標）", False), ("(b) 頂の x を論文の図 5b の頂にそろえた", True)]
    xl, xr, zb, zt = 38.6, 43.0, -0.45, 0.80
    s = 300.0
    pw, ph = int((xr - xl) * s), int((zt - zb) * s)
    xc_paper = 41.209
    for pi_, (title, align) in enumerate(panels):
        px0, py0 = 70, 90 + pi_ * (ph + 90)
        X = lambda v: px0 + (v - xl) * s
        Y = lambda v: py0 + (zt - v) * s
        # 論文の塗り
        sub = np.zeros((ph, pw), bool)
        xx = xl + (np.arange(pw) + 0.5) / s; zz = zt - (np.arange(ph) + 0.5) / s
        ix = np.clip(((xx - 38.0) / 0.002).astype(int), 0, PA.shape[1] - 1); iz = np.clip(((zz + 1.0) / 0.002).astype(int), 0, PA.shape[0] - 1)
        sub = PA[iz][:, ix]
        img = np.empty((ph, pw, 3), np.uint8); img[:] = (255, 255, 255); img[sub] = (205, 205, 205)
        im.paste(Image.fromarray(img), (px0, py0))
        for v in np.arange(39.0, 43.01, 0.5):
            dr.line([(X(v), py0), (X(v), py0 + ph)], fill=GRID)
            dr.text((X(v) - 14, py0 + ph + 4), "%.1f" % v, fill=SUB, font=font(13))
        for v in (-0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8):
            if zb <= v <= zt:
                dr.line([(px0, Y(v)), (px0 + pw, Y(v))], fill=GRID)
                dr.text((px0 - 44, Y(v) - 8), "%.1f" % v, fill=SUB, font=font(13))
        dr.rectangle([px0, py0, px0 + pw, py0 + ph], outline=LINE)
        dr.text((px0, py0 - 26), title, fill=TXT, font=font(16, True))
        dr.text((px0 + pw / 2 - 30, py0 + ph + 22), "x / h0", fill=TXT, font=font(14))
        dr.text((px0 + pw + 8, py0 + ph / 2), "z / h0", fill=TXT, font=font(14))
        for c in pc:
            for seg in poly_in(c, 0.0, xl, xr, zb, zt):
                dr.line([(X(a), Y(b)) for a, b in seg], fill=(120, 120, 120), width=1)
        legs = []
        for k, r in enumerate(runs):
            col = COLS[k % len(COLS)]
            d = np.load(r["masks"])
            M, MX, MZ = d["touchdown_M"], d["touchdown_X"], d["touchdown_Z"]
            sh = 0.0
            if align:
                a = (r["ruler"].get("touchdown") or {})
                if a.get("frame") is not None:
                    xcm = None
                    co = {int(q[0]): q for q in r["coarse"]}
                    # 頂の x：着水のコマの水の一番高い列（0.05 m の格子）
                    top = np.where(M.any(0), MZ[M.shape[0] - 1 - np.argmax(M[::-1], 0)], -99)
                    xcm = MX[int(np.argmax(top))] / H0
                    sh = xc_paper - xcm
            for c in contours_h0(M, MX, MZ):
                for seg in poly_in(c, sh, xl, xr, zb, zt):
                    dr.line([(X(a + sh), Y(b)) for a, b in seg], fill=col, width=2)
            legs.append((col, label_of(r) + "  着水 t̃ %.2f%s" % (r["touchdown"]["t_tilde_if_x0_15h0"] or float("nan"),
                                                                 ("、x を %+.2f h0 ずらした" % sh) if align else "")))
        lx, ly0 = px0 + 12, py0 + ph - 14 - 22 * (len(legs) + 1)
        dr.rectangle([lx - 6, ly0 - 6, lx + 720, py0 + ph - 8], fill=(255, 255, 255), outline=LINE)
        for k, (col, lab) in enumerate(legs):
            ly = ly0 + 22 * k
            dr.line([(lx, ly + 10), (lx + 30, ly + 10)], fill=col, width=3)
            dr.text((lx + 36, ly), lab, fill=TXT, font=font(13))
        ly = ly0 + 22 * len(legs)
        dr.rectangle([lx, ly + 3, lx + 30, ly + 17], fill=(205, 205, 205), outline=(120, 120, 120))
        dr.text((lx + 36, ly), "論文 図 5b（風なし、着水 t̃ 19.96、xbp 42.05 h0、Hb 0.64 h0）", fill=TXT, font=font(13))
    im.save(out_png)
    return out_png


def fig_ratio(runs, out_png):
    items = [("Hb/h0", "Hb_h0", PAPER["Hb_h0"]), ("xbp/h0", "xbp_h0", PAPER["xbp_h0"]), ("着水 t̃", "t_tilde", PAPER["t_tilde"]),
             ("AJ/Hb²", "AJ_Hb2", PAPER["AJ_Hb2"]), ("Ao/Hb²", "AO_Hb2", PAPER["AO_Hb2"]), ("W/L（論文 0.300）", "W_L", PAPER["W_L"]),
             ("W/L（図 5b を g47 で 0.351）", "W_L", PAPER["W_L_g47"]), ("θo", "theta_o_deg", PAPER["theta_o_deg"]),
             ("噴流の幅 s0.5（図 5b を g47 で 0.085 h0）", "jet_width_h0", PAPER["jet_width_h0_s05_g47"]),
             ("噴流の幅 s0.9（図 5b を g47 で 0.049 h0）", "jet_width_09_h0", PAPER["jet_width_h0_s09_g47"])]
    W, Hh = 1400, 120 + 52 * len(items) + 40
    im = Image.new("RGB", (W, Hh), BG); dr = ImageDraw.Draw(im)
    dr.text((20, 10), "E1a：論文（Feddersen ら 2024、風なし）の値に対する私たちの値の比。1 が一致、灰の帯は ±5 %", fill=TXT, font=font(20, True))
    dr.text((20, 40), "論文は 2 相・表面張力（Bo 4000）・粘り（Re 4×10⁴）・h0 5.5 cm。私たちは水だけ・重力だけ・h0 19 m。噴流の幅は粒子 0.25 m（格子 0.5 m）で格子 3〜5 個分、粒子 0.5 m（格子 1 m）で 1〜3 個分",
            fill=SUB, font=font(14))
    x0, y0, w = 430, 100, 900
    lo, hi = 0.0, 2.5
    X = lambda v: x0 + (min(max(v, lo), hi) - lo) / (hi - lo) * w
    h = 52 * len(items)
    dr.rectangle([X(0.95), y0, X(1.05), y0 + h], fill=(225, 225, 225))
    for v in np.arange(0.0, 2.51, 0.25):
        dr.line([(X(v), y0), (X(v), y0 + h)], fill=GRID if abs(v - 1) > 1e-9 else (90, 90, 90))
        dr.text((X(v) - 12, y0 + h + 4), "%.2f" % v, fill=SUB, font=font(13))
    for i, (lab, key, ref) in enumerate(items):
        yy = y0 + 52 * i + 26
        dr.text((20, yy - 10), lab, fill=TXT, font=font(15))
        for k, r in enumerate(runs):
            if key == "t_tilde":
                v = r["touchdown"]["t_tilde_if_x0_15h0"]
            else:
                v = r["paper_measures"].get(key)
            if v is None:
                continue
            q = v / ref
            u = X(q); vv = yy - 14 + 9 * k
            dr.ellipse([u - 6, vv - 6, u + 6, vv + 6], fill=COLS[k % len(COLS)], outline=(0, 0, 0))
            dr.text((u + 9 if q < 2.2 else u - 60, vv - 8), "%.2f" % q, fill=SUB, font=font(11))
    for k, r in enumerate(runs):
        dr.ellipse([20 + 330 * k, Hh - 30, 32 + 330 * k, Hh - 18], fill=COLS[k % len(COLS)], outline=(0, 0, 0))
        dr.text((38 + 330 * k, Hh - 34), "%s" % r["id"], fill=TXT, font=font(13))
    im.save(out_png)
    return out_png


def fig_series(runs, out_png):
    """巻き始め〜着水の後の AJ・Ao・届き（論文の時刻 t̃ にそろえる）。Hb は各計算の着水のコマの値で割る。"""
    W, Hh = 1500, 1000
    im = Image.new("RGB", (W, Hh), BG); dr = ImageDraw.Draw(im)
    dr.text((20, 10), "E1a：噴流の面積 AJ・巻きの空気 Ao・噴流の届きの時間の変わり（t̃ は頂を 15 h0 に置いた時の時刻にそろえた）", fill=TXT, font=font(20, True))
    dr.text((20, 40), "AJ と Ao は各計算の着水のコマの Hb² で、届きは h0 で割った。触れる前の Ao は噴流のいちばん低い所の縦の隙間を縦の線で閉じた面積。◆＝着水のコマ、★＝論文の風なしの着水（t̃ 19.96）",
            fill=SUB, font=font(14))
    pan = [("AJ / Hb²", "AJ", 0.0, 0.3, 2), ("Ao / Hb²", "AO", 0.0, 0.4, 2), ("届き（頂の列から噴流の先まで）/ h0", "reach", 0.0, 0.8, 1)]
    ref = {"AJ": PAPER["AJ_Hb2"], "AO": PAPER["AO_Hb2"], "reach": 0.73}
    tl, tr_ = 19.0, 20.8
    for k, (lab, key, lo, hi, norm) in enumerate(pan):
        x0, y0, w, h = 110, 100 + k * 290, 1100, 220
        X, Y = axes(dr, x0, y0, w, h, tl, tr_, lo, hi, [19.0, 19.2, 19.4, 19.6, 19.8, 20.0, 20.2, 20.4, 20.6, 20.8],
                    list(np.arange(lo, hi + 1e-9, 0.05 if hi <= 0.3 else 0.1)), "t̃", lab, fx="%.1f", fy="%.2f")
        for j, r in enumerate(runs):
            c = COLS[j % len(COLS)]
            Hb = r["paper_measures"].get("Hb_m") or 1.0
            P = []
            for q in r["series"]:
                v = q.get(key)
                if v is None or not (tl <= q["tt"] <= tr_):
                    continue
                v = v / (Hb * Hb) if norm == 2 else v / H0
                P.append((X(q["tt"]), Y(min(max(v, lo), hi))))
            if len(P) > 1:
                dr.line(P, fill=c, width=2)
            tdf = r["touchdown"]["frame"]
            for q in r["series"]:
                if q["frame"] == tdf and q.get(key) is not None:
                    v = q[key] / (Hb * Hb) if norm == 2 else q[key] / H0
                    u, vv = X(q["tt"]), Y(min(max(v, lo), hi))
                    dr.polygon([(u, vv - 7), (u + 7, vv), (u, vv + 7), (u - 7, vv)], fill=c, outline=(0, 0, 0))
            if k == 0:
                dr.line([(x0 + w + 20, y0 + 10 + 22 * j + 8), (x0 + w + 50, y0 + 10 + 22 * j + 8)], fill=c, width=3)
                dr.text((x0 + w + 56, y0 + 10 + 22 * j), r["id"], fill=TXT, font=font(13))
        u, v = X(PAPER["t_tilde"]), Y(ref[key])
        star = [(u + 10 * math.cos(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45), v - 10 * math.sin(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45)) for i in range(10)]
        dr.polygon(star, fill=(250, 200, 0), outline=(0, 0, 0))
        if key == "reach":
            dr.text((u + 12, v - 8), "論文 図 5b を g47 で読んだ 0.73", fill=SUB, font=font(12))
    im.save(out_png)
    return out_png


def fmt(v, f="%.3f"):
    return "-" if v is None else (f % v)


def table_md(runs, cmp_):
    L = []
    L.append("| 計算 | 粒子 m | 領域 | 起動 | 計算の時間 分 | 粒子の数 | 巻き始め x/h0 | Hb巻始/h0 | 着水の決まり | 着水 t̃（x0 15 h0 にそろえた） | xbp/h0 | Hb/h0 | AJ/Hb² | Ao/Hb² | W/L | θo° | 幅 s0.5/h0 | 幅 s0.9/h0 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    L.append("| 論文 風なし（2 相・Bo 4000） | - | 0〜59 h0 | - | - | - | - | - | 隙間 ≤ 0.015 h0 | 19.96 | 42.05（風 40.9〜42.2） | 0.64 | 0.219 | 0.352 | 0.300（g47 で図を読むと 0.351） | 29 | 0.05（g47 で 0.085） | （g47 で 0.049） |")
    for r in runs:
        pm = r["paper_measures"]; on = r["onset"]; td = r["touchdown"]
        L.append("| %s | %.3g | %s | %d | %.1f | %.2f M | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["id"], r["dp"], r["domain"], r["launches"], r["wall_s"] / 60.0, r["particles_max"] / 1e6, fmt(on["x_vert_h0"], "%.2f"), fmt(on["Hb_onset_h0"]),
            td["by"], fmt(td["t_tilde_if_x0_15h0"], "%.2f"), fmt(pm["xbp_h0"], "%.2f"), fmt(pm["Hb_h0"]), fmt(pm["AJ_Hb2"]), fmt(pm["AO_Hb2"]),
            fmt(pm["W_L"]), fmt(pm["theta_o_deg"], "%.1f"), fmt(pm["jet_width_h0"]), fmt(pm["jet_width_09_h0"])))
    L.append("")
    L.append("| 計算（STUDY52 の物差し、η_c で割った値） | コマ | 弦 0.1〜0.5 η_c ° | 足 | 唇の下の空気 | 唇の厚さ | 覆いの面積 | 点数 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    L.append("| 原画 cn | - | 64.3 | 0.254 | 0.541 | 0.350 | 0.186 | 0 |")
    L.append("| 論文 図 5b（着水） | - | 32.7 | 0.798 | 0.478 | 0.206 | 0.196 | 1.78 |")
    L.append("| FLIP42 R3 いちばん巻いた | - | 19.2 | 1.656 | 0.152 | 0.113 | 0.046 | 3.2〜3.4 |")
    for r in runs:
        for k, nm in (("touchdown", "着水"), ("max_overturn", "いちばん巻いた"), ("best_score", "原画に最も近い")):
            a = r["ruler"][k]
            L.append("| %s %s | %s | %s | %s | %s | %s | %s | %s |" % (r["id"], nm, a.get("frame"), fmt(a.get("face_chord_deg_01_05"), "%.1f"),
                                                             fmt(a.get("front_x01_rel")), fmt(a.get("gap_max")), fmt(a.get("lip_thick_mid")),
                                                             fmt(a.get("hood_area")), fmt(a.get("score"), "%.2f")))
    if cmp_:
        L.append("")
        L.append("| 短い領域 − 全部の領域（%） | 粒子 m | 巻き始め x | Hb 巻き始め | xbp | Hb | AJ/Hb² | Ao/Hb² | 着水 t̃ | 5 % 以内（崩れの位置と Hb） |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for d in cmp_:
            L.append("| %s − %s | %.3g | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                d["short"], d["full"], d["dp"], fmt(d["onset_x_vert_h0"]["diff_pct"], "%+.2f"), fmt(d["Hb_onset_h0"]["diff_pct"], "%+.2f"),
                fmt(d["xbp_h0"]["diff_pct"], "%+.2f"), fmt(d["Hb_h0"]["diff_pct"], "%+.2f"), fmt(d["AJ_Hb2"]["diff_pct"], "%+.1f"),
                fmt(d["AO_Hb2"]["diff_pct"], "%+.1f"), fmt(d["t_tilde_touchdown_x0_15h0"]["diff_pct"], "%+.2f"),
                "はい" if d["within_5pct_break_and_Hb"] else "いいえ"))
    return "\n".join(L) + "\n"


def main(argv):
    out = None; ref = None; rds = []
    for a in argv:
        if a.startswith("--out="):
            out = a[6:]
        elif a.startswith("--ref="):
            ref = a[6:]
        else:
            rds.append(a)
    if not out or not rds:
        print(__doc__); return 2
    out = guard(out)
    os.makedirs(out, exist_ok=True)
    runs = [run_info(rd) for rd in rds]
    cmp_ = compare_short_full(runs, ref)
    figs = dict(crest_track=fig_crest(runs, guard(out + "/e1a_crest_track.png")),
                touchdown_vs_paper=fig_touchdown(runs, guard(out + "/e1a_touchdown_vs_paper.png")),
                ratio_to_paper=fig_ratio(runs, guard(out + "/e1a_ratio_to_paper.png")),
                overturn_series=fig_series(runs, guard(out + "/e1a_overturn_series.png")))
    md = table_md(runs, cmp_)
    open(guard(out + "/e1a_table.md"), "w", encoding="utf8").write(md)
    slim = []
    for r in runs:
        q = dict(r); q.pop("coarse", None); q.pop("series", None)
        slim.append(q)
    json.dump(dict(tool="g47_e1a.py", paper=PAPER, print_target=PRINT, runs=slim, short_vs_full=cmp_, figures=figs),
              open(guard(out + "/e1a_compare.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(md)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
