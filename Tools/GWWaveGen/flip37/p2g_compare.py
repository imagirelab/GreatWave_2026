# -*- coding: utf-8 -*-
"""P2g 誘導の双子の比べ（py -3.10）。使い方: py -3.10 p2g_compare.py [G1_dir] [G0_dir]

誘導あり（G1）と誘導なしの双子（G0）を、同じ瞬間・同じ置き方で比べる。誘導なしの双子が P2 の R18 と同じ計算になったかも確かめる。
- 誘導の報告：energy.json（run_p2g.py が書く）から、力の最大・平均（重力の何倍か）、当てた体積、時間の形、仕事、波のエネルギーに対する割合。
- 形：t* = 10.375 s（コマ 250。R18 のいちばん原画に近い瞬間）と、誘導が 0 になった時（9.0 s）などで、
  峰に沿う頂の高さ（hf.npz）、原画カメラのシルエット（R18 と同じ置き方 ψ 30°・倍率 1.1、頂は各計算の z=0 の頂）、
  断面（sec/z+000・z-020・z-040・z-060）の出来事と形（P1 の p1_analyze と同じ定義）。
出力：Unity/Build/FLIP37/P2g/compare.json、fig_compare.png、fig_sections.png
"""
import sys, os, json, glob, math
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p2_common as C  # noqa: E402
import p2_analyze as A2  # noqa: E402
import p1_analyze as A1  # noqa: E402
from p2_figs import font, painting_display  # noqa: E402

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
OUT = ROOT + "/P2g"
G1 = sys.argv[1] if len(sys.argv) > 1 else OUT + "/G1_R18_drag010"
G0 = sys.argv[2] if len(sys.argv) > 2 else OUT + "/G0_R18_twin"
R18 = ROOT + "/P2/R18_X30L120LG_H39"
F_STAR = 250          # t* = (250-1)/24 = 10.375 s
PSI, SCL = 30, 1.1
SC = 0.5
REF_E_PROPOSAL = 7.5e9   # 提案 §3.5 の見積もり（波の高さ 26 m・波長 200 m・幅 45 m）
GRAV = 9.80665


def tof(f):
    return (f - 1) / 24.0


def crest_at(hf, f):
    k = int(np.argmin(np.abs(hf["frames"] - f)))
    cp, cx = A2.crest_profile(hf, k)
    return cp, cx, k


def profile_metrics(hf, f):
    cp, cx, k = crest_at(hf, f)
    zs = hf["zs"]
    Hc = float(cp.max()); zc = float(zs[int(np.argmax(cp))])
    i0 = int(np.argmin(np.abs(zs)))
    dz = float(np.median(np.diff(zs)))
    pick = {"z%+d" % z: float(np.interp(z, zs, cp)) for z in (-100, -80, -60, -40, -20, 0, 20, 40, 60)}
    near = cp[zs < 0]
    return {"f": int(hf["frames"][k]), "t": float(hf["t"][k]), "Hc_m": Hc, "z_Hc": zc, "y_z0": float(cp[i0]), "x_z0": float(cx[i0]),
            "crest_y_at": pick,
            "near_mean_z-100..-20_m": float(np.mean(cp[(zs >= -100) & (zs <= -20)])),
            "crest_len_075Hc_m": float((cp >= 0.75 * Hc).sum() * dz),
            "half_width_m": float((cp >= 0.5 * (Hc + np.nanmin(cp))).sum() * dz),
            "near_len_ge_0.75Hc_from_z0_m": float(((zs <= 0) & (cp >= 0.75 * Hc)).sum() * dz),
            "peaks": A2.peaks_1d(cp, zs, prom=0.8)}


def silhouette_metrics(rd, hf, f, scale=SC):
    cp, cx, k = crest_at(hf, f)
    zs = hf["zs"]
    i0 = int(np.argmin(np.abs(zs)))
    anchor = (float(cx[i0]), float(cp[i0]), float(zs[i0]))
    mp = os.path.join(rd, "mesh", "mesh_%04d.npz" % f)
    if not os.path.isfile(mp):
        return None, None
    Pm, tri, t = C.load_mesh_full(mp, *C.run_mirror(rd))
    keep = (Pm[:, 0] > anchor[0] - 160) & (Pm[:, 0] < anchor[0] + 90)
    tk = tri[keep[tri].all(1)]
    cam = C.painting_cam(scale)
    U, O = C.place(Pm, anchor, PSI, SCL, cam)
    m_full = C.raster_mask(cam, U, tk)
    pm, outer, inner = C.painting_mask(scale)
    win = C.window_mask(scale)
    m = m_full & win
    inter = (m & pm).sum(); uni = (m | (pm & win)).sum()
    H_, W_ = m.shape
    left = np.zeros_like(m); left[:, : int(round(C.CREST_PX[0] * scale))] = True
    sky = win & ~pm
    res = {"f": f, "t": tof(f), "anchor": anchor, "O": O.tolist(), "iou": float(inter / max(uni, 1)),
           "painting_covered": float(inter / max((pm & win).sum(), 1)),
           "outside_covered": float((m & sky).sum() / max(sky.sum(), 1)),
           "outside_left_covered": float((m & sky & left).sum() / max((sky & left).sum(), 1)),
           "outside_right_covered": float((m & sky & ~left).sum() / max((sky & ~left).sum(), 1)),
           "outline_dist": C.outline_distance(m, outer, inner, scale)}   # P2 と同じ（窓で切ったシルエット）
    return res, m_full


def sections(rd):
    out = {}
    for name in ("z+000", "z-020", "z-040", "z-060", "z+020", "z+040"):
        sd = os.path.join(rd, "sec", name)
        if not os.path.isdir(sd):
            continue
        try:
            r = A1.analyze(sd, quiet=True)
        except Exception as e:
            out[name] = {"error": str(e)[:200]}
            continue
        tl = r["timeline"]
        q = min(tl, key=lambda q: abs(q["t"] - tof(F_STAR))) if tl else None
        keys = ("crest", "lip_tip", "reach_over_Hc", "drop_over_Hc", "overhang_over_Hc", "tube_aspect_w_over_h",
                "front_face_chord_angle_deg", "tube_inscribed_r_m", "back_dx_to_075Hc_m", "overturned")
        ev = r["events"]
        out[name] = {"plunging": r["plunging"],
                     "onset_t": (ev.get("breaking_onset_B085") or {}).get("t"),
                     "past_vertical_t": (ev.get("face_past_vertical") or {}).get("t"),
                     "tube_closed_t": (ev.get("tube_closed_or_nearly") or {}).get("t"),
                     "at_tstar": ({k: q.get(k) for k in keys} | {"t": q["t"]}) if q else None,
                     "best_vs_painting_A": (r.get("best_frame_vs_painting") or {}).get("A_side")}
    return out


def identity(g0, r18):
    a = np.load(os.path.join(g0, "crest.npy")); b = np.load(os.path.join(r18, "crest.npy"))
    n = min(len(a), len(b))
    ya, yb = a[:n, 2::3], b[:n, 2::3]
    xa, xb = a[:n, 3::3], b[:n, 3::3]
    dy = np.nanmax(np.abs(ya - yb), axis=1); dx = np.nanmax(np.abs(xa - xb), axis=1)
    ha = np.load(os.path.join(g0, "hf.npz"))["eta"]; hb = np.load(os.path.join(r18, "hf.npz"))["eta"]
    m = min(len(ha), len(hb))
    de = [float(np.nanmax(np.abs(ha[i].astype(np.float32) - hb[i].astype(np.float32)))) for i in range(0, m, 6)]
    first_diff = int(np.argmax(dy > 1e-4)) + 1 if (dy > 1e-4).any() else None
    return {"frames_compared": int(n), "crest_y_maxdiff_m": float(np.nanmax(dy)), "crest_x_maxdiff_m": float(np.nanmax(dx)),
            "first_frame_crest_differs": first_diff, "eta_maxdiff_m_every6": float(max(de)), "eta_frames_compared": int(m)}


def guide_report(g1, g0):
    e1 = json.load(open(os.path.join(g1, "energy.json")))
    e0 = json.load(open(os.path.join(g0, "energy.json")))
    r1 = json.load(open(os.path.join(g1, "run.json"), encoding="utf8"))
    P = r1["parms"]
    E = [q for q in e1["energy"] if "P_W" in q]
    gt0 = P["g_t0"]
    Eon = [q for q in e1["energy"] if q["t"] <= gt0 + 1e-6][-1]
    full = [q for q in E if q["Wt"] > 0.999]
    W = E[-1]["W_cum_J"] if E else 0.0
    ws = [q for q in E if q["Wt"] > 0.0]
    rep = {
        "g_amp_g": P["g_amp"], "form_ja": "流れに逆らう弱い抵抗 a = -A·W·v/max(|v|, v_ref)（|a| <= A·W）",
        "v_ref_mps": P["g_vref"], "t_on_s": gt0, "t_full_s": [gt0 + P["g_ramp"], P["g_t1"] - P["g_ramp"]], "t_off_s": P["g_t1"],
        "t_star_s": tof(F_STAR), "off_before_tstar_s": tof(F_STAR) - P["g_t1"],
        "z_range": "z < -%g（%g で 0 → %g で 1）、%g〜%g で壁の手前で 0 へ" % (P["g_zin"], P["g_zin"], P["g_zfull"], P["g_zw0"], P["g_zw1"]),
        "x_window": "R18 の頂の x の上のガウス（広がり %g m、ずらし %g m）" % (P["g_sx"], P["g_dx"]),
        "y_window": "高さ y が %g m より下は 0、%g m より上で 1" % (P.get("g_y0", -999), P.get("g_y1", -998)),
        "a_peak_g": max(q["a_peak_g"] for q in E) if E else 0.0,
        "a_mean_g_in_W>0.05_fullwindow": float(np.mean([q["a_mean_g_W>0.05"] for q in full])) if full else None,
        "vol_W>0.05_m3_max": max(q["vol_W>0.05_m3"] for q in E) if E else 0.0,
        "vol_W>0.5_m3_max": max(q["vol_W>0.5_m3"] for q in E) if E else 0.0,
        "W_eff_vol_m3_mean_full": float(np.mean([q["W_eff_vol_m3"] for q in full])) if full else None,
        "work_J": W, "E_wave_at_t_on_J": Eon["E"], "E_near_z<-10_at_t_on_J": Eon["E_near_z<-10"],
        "work_pct_of_E_wave": 100.0 * abs(W) / Eon["E"], "work_pct_of_E_near": 100.0 * abs(W) / Eon["E_near_z<-10"],
        "work_pct_of_proposal_ref_7.5e9J": 100.0 * abs(W) / REF_E_PROPOSAL,
        "power_peak_W": min(q["P_W"] for q in E) if E else 0.0,
        "frames_with_guide": len(ws),
        "timeline": [{"t": q["t"], "Wt": q["Wt"], "a_peak_g": q["a_peak_g"], "P_W": q["P_W"], "W_cum_J": q["W_cum_J"]} for q in E[::6]],
    }
    # エネルギーの差（誘導あり − なし）を同じ時刻で
    d0 = {round(q["t"], 4): q for q in e0["energy"]}
    diff = []
    for q in e1["energy"]:
        k = round(q["t"], 4)
        if k in d0:
            diff.append({"t": q["t"], "E1": q["E"], "E0": d0[k]["E"], "dE": q["E"] - d0[k]["E"], "dE_near": q["E_near_z<-10"] - d0[k]["E_near_z<-10"],
                         "W_cum": q.get("W_cum_J")})
    rep["energy_diff"] = diff
    rep["E_twin_timeline"] = [{"t": q["t"], "E": q["E"], "E_near": q["E_near_z<-10"]} for q in e0["energy"]]
    rep["E_guided_timeline"] = [{"t": q["t"], "E": q["E"], "E_near": q["E_near_z<-10"]} for q in e1["energy"]]
    return rep


# ---------------------------------------------------------------- 図
def plot_lines(W_, H_, series, xlim, ylim, title, xlabel, ylabel, hlines=(), vlines=()):
    im = Image.new("RGB", (W_, H_), (255, 255, 255))
    d = ImageDraw.Draw(im)
    L, R, T, B = 70, 20, 40, 50
    pw, ph = W_ - L - R, H_ - T - B
    def X(v): return L + (v - xlim[0]) / (xlim[1] - xlim[0]) * pw
    def Y(v): return T + (1 - (v - ylim[0]) / (ylim[1] - ylim[0])) * ph
    d.rectangle([L, T, L + pw, T + ph], outline=(0, 0, 0))
    f1, f2 = font(16), font(13)
    d.text((L, 8), title, fill=(0, 0, 0), font=f1)
    for i in range(6):
        v = ylim[0] + (ylim[1] - ylim[0]) * i / 5
        d.line([L - 4, Y(v), L, Y(v)], fill=(0, 0, 0)); d.text((4, Y(v) - 8), "%.3g" % v, fill=(0, 0, 0), font=f2)
        d.line([L, Y(v), L + pw, Y(v)], fill=(232, 232, 232))
    for i in range(7):
        v = xlim[0] + (xlim[1] - xlim[0]) * i / 6
        d.text((X(v) - 14, T + ph + 4), "%.4g" % v, fill=(0, 0, 0), font=f2)
    d.text((L + pw // 2 - 60, H_ - 22), xlabel, fill=(0, 0, 0), font=f2)
    d.text((L + 4, T + 4), ylabel, fill=(80, 80, 80), font=f2)
    for (v, col) in hlines:
        d.line([L, Y(v), L + pw, Y(v)], fill=col)
    for (v, col) in vlines:
        d.line([X(v), T, X(v), T + ph], fill=col)
    ly = T + 22
    for (xs, ys, col, lab, dash) in series:
        pts = [(X(a), Y(b)) for a, b in zip(xs, ys) if np.isfinite(b) and xlim[0] <= a <= xlim[1]]
        if dash:
            for i in range(0, len(pts) - 1, 2):
                d.line([pts[i], pts[i + 1]], fill=col, width=2)
        else:
            d.line(pts, fill=col, width=2)
        d.line([L + pw - 260, ly + 7, L + pw - 230, ly + 7], fill=col, width=3)
        d.text((L + pw - 224, ly), lab, fill=(0, 0, 0), font=f2)
        ly += 18
    return im


def overlay_sil(m, label, sub):
    base = np.array(painting_display(SC)).astype(np.float64) * 0.55 + 255 * 0.45
    over = base.copy()
    over[m] = over[m] * 0.45 + np.array([235, 120, 40]) * 0.55
    img = Image.fromarray(np.clip(over, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(img)
    outer, inner, _ = C.painting_outline()
    for pl in (outer, inner):
        dr.line([tuple((p + 0.5) * SC - 0.5) for p in pl], fill=(20, 60, 200), width=2)
    x0, x1, y0, y1 = C.WIN
    dr.rectangle([x0 * SC, y0 * SC, x1 * SC, y1 * SC], outline=(120, 120, 120))
    dr.rectangle([0, 0, 960, 52], fill=(255, 255, 255))
    dr.text((6, 4), label, fill=(0, 0, 0), font=font(17))
    dr.text((6, 28), sub, fill=(40, 40, 40), font=font(14))
    return img


def topdiff(hf1, hf0, f, title, guide_P=None, tg=None):
    k1 = int(np.argmin(np.abs(hf1["frames"] - f))); k0 = int(np.argmin(np.abs(hf0["frames"] - f)))
    xs, zs = hf1["xs"], hf1["zs"]
    m = (xs >= 380) & (xs <= 706)
    D = (hf1["eta"][k1] - hf0["eta"][k0])[:, m]
    H_, W_ = D.shape
    v = np.clip(D / 3.0, -1, 1)
    rgb = np.ones((H_, W_, 3))
    rgb[..., 0] = np.where(v > 0, 1.0, 1.0 + v); rgb[..., 1] = 1.0 - np.abs(v); rgb[..., 2] = np.where(v < 0, 1.0, 1.0 - v)
    img = Image.fromarray((rgb[::-1] * 255).astype(np.uint8)).resize((W_ * 3, H_ * 3), Image.NEAREST)
    # 頂の線（誘導なし）
    d = ImageDraw.Draw(img)
    cp0, cx0, _ = crest_at(hf0, f)
    pts = [((x - 380) / 2 * 3, (len(zs) - 1 - i) * 3) for i, x in enumerate(cx0) if 380 <= x <= 706]
    if len(pts) > 1:
        d.line(pts, fill=(0, 0, 0), width=1)
    can = Image.new("RGB", (max(img.width, 520), img.height + 52), (255, 255, 255))
    can.paste(img, (0, 52))
    dc = ImageDraw.Draw(can)
    dc.text((4, 2), title, fill=(0, 0, 0), font=font(15))
    dc.text((4, 20), "水面の差（誘導あり − なし）赤＝高い・青＝低い（±3 m）", fill=(60, 60, 60), font=font(12))
    dc.text((4, 34), "x 380〜706 m（右が岸）、上 z=+120・下 z=−120。黒＝誘導なしの頂", fill=(60, 60, 60), font=font(12))
    return can


def section_strip(rd_list, labels, zname, times):
    tw, th = 420, 230
    S = Image.new("RGB", (tw * len(times), th * len(rd_list) + 30), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((6, 4), "断面 %s（粒子、x 470〜650 m・y −10〜28 m。色＝速さ 0〜25 m/s）" % zname, fill=(0, 0, 0), font=font(15))
    for j, (rd, lab) in enumerate(zip(rd_list, labels)):
        for i, t in enumerate(times):
            f = int(round(t * 24)) + 1
            if f % 2 == 0:
                f += 1
            p = os.path.join(rd, "sec", zname, "snap_%04d.npz" % f)
            tile = Image.new("RGB", (tw, th), (250, 250, 250))
            dt = ImageDraw.Draw(tile)
            if os.path.isfile(p):
                q = np.load(p)
                x, y = q["x"], q["y"]; sp = np.hypot(q["vx"], q["vy"])
                X = (x - 470) / 180 * tw; Y = th - (y + 10) / 38 * th
                ok = (X >= 0) & (X < tw) & (Y >= 0) & (Y < th)
                a = np.array(tile)
                c = np.clip(sp[ok] / 25.0, 0, 1)
                col = np.stack([255 * c, 80 + 100 * (1 - c), 255 * (1 - c)], 1).astype(np.uint8)
                a[Y[ok].astype(int), X[ok].astype(int)] = col
                tile = Image.fromarray(a); dt = ImageDraw.Draw(tile)
                y0 = th - (0 + 10) / 38 * th
                dt.line([0, y0, tw, y0], fill=(200, 200, 200))
            dt.text((4, 2), "%s  t=%.2f s" % (lab, (f - 1) / 24.0), fill=(0, 0, 0), font=font(13))
            S.paste(tile, (i * tw, 30 + j * th))
    return S


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    hf1, hf0, hfr = A2.load_hf(G1), A2.load_hf(G0), A2.load_hf(R18)
    rep = {"G1": G1, "G0": G0, "R18": R18, "t_star": tof(F_STAR), "placement": {"psi_deg": PSI, "scale": SCL, "anchor_rule_ja": "各計算の z=0 の頂（巻いた所）を原画の頂の画素へ"}}
    rep["identity_G0_vs_R18"] = identity(G0, R18)
    rep["guide"] = guide_report(G1, G0)
    rep["profiles"] = {}
    for f in (169, 193, 217, 229, 241, F_STAR, 262, 274):
        rep["profiles"]["f%04d" % f] = {"G0": profile_metrics(hf0, f), "G1": profile_metrics(hf1, f)}
    rep["silhouette"] = {}
    masks = {}
    for f in range(238, 266, 3):
        s0, m0 = silhouette_metrics(G0, hf0, f); s1, m1 = silhouette_metrics(G1, hf1, f)
        if s0 and s1:
            rep["silhouette"]["f%04d" % f] = {"G0": s0, "G1": s1}
            masks[f] = (m0, m1)
    rep["sections"] = {"G0": sections(G0), "G1": sections(G1)}
    json.dump(rep, open(os.path.join(OUT, "compare.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)

    # ---- 図 1
    g = rep["guide"]
    tag1 = "物理＋誘導（仕事 %.1f %%、最大 %.2f 倍の重力、t* の %.2f 秒前に切る）" % (g["work_pct_of_E_wave"], g["a_peak_g"], g["off_before_tstar_s"])
    s0 = rep["silhouette"]["f%04d" % F_STAR]["G0"]; s1 = rep["silhouette"]["f%04d" % F_STAR]["G1"]
    m0, m1 = masks[F_STAR]
    im0 = overlay_sil(m0, "誘導なし（双子 G0）t = %.2f s：物理だけ" % tof(F_STAR),
                      "IoU %.3f・空の所を覆う %.0f %%（左 %.0f %%）・輪郭の距離 平均 %.0f px" % (s0["iou"], 100 * s0["outside_covered"], 100 * s0["outside_left_covered"], s0["outline_dist"]["mean_px"]))
    im1 = overlay_sil(m1, "誘導あり（G1）t = %.2f s：%s" % (tof(F_STAR), tag1),
                      "IoU %.3f・空の所を覆う %.0f %%（左 %.0f %%）・輪郭の距離 平均 %.0f px" % (s1["iou"], 100 * s1["outside_covered"], 100 * s1["outside_left_covered"], s1["outline_dist"]["mean_px"]))
    cp0, _, _ = crest_at(hf0, F_STAR); cp1, _, _ = crest_at(hf1, F_STAR); cpr, _, _ = crest_at(hfr, F_STAR)
    cp0o, _, _ = crest_at(hf0, 217); cp1o, _, _ = crest_at(hf1, 217)
    zs = hf0["zs"]
    sP, yP = C.painting_crest_profile(PSI, Hc=float(cp0[int(np.argmin(np.abs(zs)))]))
    pl = plot_lines(960, 420, [(zs, cp0, (40, 40, 40), "誘導なし t*", False), (zs, cp1, (220, 90, 20), "誘導あり t*", False),
                               (zs, cp0o, (150, 150, 150), "誘導なし 9.0 s", True), (zs, cp1o, (240, 170, 120), "誘導あり 9.0 s", True),
                               (sP, yP, (30, 70, 210), "原画の読み（ψ30°）", False)],
                    (-120, 120), (8, 22), "峰に沿う頂の高さ（m）。z<0 が画面の左・手前（誘導は z<−10 だけ）", "z (m)", "頂 (m)",
                    vlines=((-10, (200, 200, 255)), (-35, (200, 200, 255))))
    E0 = g["E_twin_timeline"]; E1 = g["E_guided_timeline"]
    tl = g["timeline"]
    pe = plot_lines(960, 420, [([q["t"] for q in E0], [q["E"] / 1e10 for q in E0], (40, 40, 40), "波のエネルギー 誘導なし", False),
                               ([q["t"] for q in E1], [q["E"] / 1e10 for q in E1], (220, 90, 20), "波のエネルギー 誘導あり", False),
                               ([q["t"] for q in E0], [q["E_near"] / 1e10 for q in E0], (150, 150, 150), "手前 z<−10 誘導なし", True),
                               ([q["t"] for q in E1], [q["E_near"] / 1e10 for q in E1], (240, 170, 120), "手前 z<−10 誘導あり", True),
                               ([q["t"] for q in tl], [-10 * q["W_cum_J"] / 1e10 for q in tl], (30, 140, 60), "誘導が抜いた仕事の積み ×10", False)],
                    (0, 12.5), (0, 7), "エネルギー（10^10 J）。誘導は %.1f〜%.1f s（t* = %.2f s）" % (g["t_on_s"], g["t_off_s"], tof(F_STAR)), "t (s)", "E",
                    vlines=((g["t_on_s"], (180, 220, 180)), (g["t_off_s"], (180, 220, 180)), (tof(F_STAR), (255, 180, 180))))
    td1 = topdiff(hf1, hf0, 217, "誘導が 0 になった時（t = 9.00 s）")
    td2 = topdiff(hf1, hf0, F_STAR, "t* = %.2f s" % tof(F_STAR))
    Wd = 1920
    Hd = 60 + 540 + 420 + max(td1.height, td2.height) + 10
    sheet = Image.new("RGB", (Wd, Hd), (255, 255, 255))
    ds = ImageDraw.Draw(sheet)
    ds.text((8, 6), "P2g 誘導の双子：R18 に、手前の峰（z<−10）の上の流れに逆らう弱い力を足した計算（右）と、同じ場面で誘導だけを切った計算（左）", fill=(0, 0, 0), font=font(20))
    ds.text((8, 34), "原画カメラ（PaintingCam v1）、置き方は R18 と同じ ψ 30°・倍率 1.1、各計算の z=0 の頂を原画の頂の画素へ。橙＝流体、青＝原画の大波の輪郭。粗い 3D（粒子 1 m・格子 2 m）", fill=(60, 60, 60), font=font(14))
    sheet.paste(im0, (0, 60)); sheet.paste(im1, (960, 60))
    sheet.paste(pl, (0, 600)); sheet.paste(pe, (960, 600))
    sheet.paste(td1, (0, 1020)); sheet.paste(td2, (td1.width + 20, 1020))
    sheet.save(os.path.join(OUT, "fig_compare.png"))
    # ---- 図 2（断面）
    times = (9.25, 10.0, 10.375, 10.75, 11.25)
    parts = [section_strip([G0, G1], ["誘導なし", "誘導あり"], z, times) for z in ("z+000", "z-020", "z-040", "z-060")]
    Hs = sum(p.height for p in parts) + 40
    S = Image.new("RGB", (parts[0].width, Hs), (255, 255, 255))
    dS = ImageDraw.Draw(S)
    dS.text((6, 6), "P2g 断面の比べ（上＝誘導なし、下＝誘導あり。%s）" % tag1, fill=(0, 0, 0), font=font(18))
    y = 40
    for p in parts:
        S.paste(p, (0, y)); y += p.height
    S.save(os.path.join(OUT, "fig_sections.png"))
    print(json.dumps({"identity": rep["identity_G0_vs_R18"], "guide": {k: v for k, v in g.items() if k not in ("timeline", "energy_diff", "E_twin_timeline", "E_guided_timeline")},
                      "prof_tstar": rep["profiles"]["f%04d" % F_STAR], "sil_tstar": {"G0": {k: s0[k] for k in ("iou", "outside_covered", "outside_left_covered")} | {"dist": s0["outline_dist"]["mean_px"]},
                                                                                       "G1": {k: s1[k] for k in ("iou", "outside_covered", "outside_left_covered")} | {"dist": s1["outline_dist"]["mean_px"]}},
                      "sections": {k: {n: {kk: v.get(kk) for kk in ("plunging", "onset_t", "past_vertical_t", "tube_closed_t")} for n, v in d.items()} for k, d in rep["sections"].items()}},
                     ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
