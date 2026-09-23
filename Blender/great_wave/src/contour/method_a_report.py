"""基準輪郭の候補Aの画像。重ね画像、拡大切出し、診断マスク、グラフを作る。
画像内へ描ける文字は ASCII のみ。"""
import os

import numpy as np

from gw import imgio, draw, plot

SEG_COLORS = {"back": "red", "head": "magenta", "inner_arc": "lime"}
COMPLETED_COLOR = "cyan"
BRIDGE_COLOR = "orange"

# 名前: (x0, y0, x1, y1, 拡大率)。拡大後の切出し幅はすべて 1600 px 以下。
CROPS = {
    "01_left_end": (0, 760, 530, 1080, 3.0),
    "02_mid_back": (450, 280, 1250, 880, 2.0),
    "03_crest": (1180, 150, 1780, 420, 2.6),
    "04_head_top": (1560, 240, 2340, 940, 2.0),
    "05_head_tip": (2020, 640, 2420, 1010, 4.0),
    "06_head_underside": (1600, 800, 2260, 1160, 2.4),
    "07_inner_arc_deepest": (1420, 1020, 1820, 1400, 4.0),
    "08_inner_arc_low_near_wave": (1640, 1560, 2040, 1960, 4.0),
    "09_trough": (1700, 1650, 2400, 2000, 2.2),
    "10_belly_to_underside": (1540, 780, 1860, 1040, 5.0),
    "11_head_step_thin_line": (1840, 560, 2160, 800, 5.0),
}


def _runs(flags):
    out, i, n = [], 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def draw_contour(im, to_view, segs, width=2.0, bridge_width=1.0):
    for name in ("back", "head", "inner_arc"):
        p = segs[name]["pts"]
        src = np.array([str(s) for s in segs[name]["src"]])
        comp = np.array([s.startswith("completed") for s in src])
        for a, b in _runs(~comp):
            draw.polyline(im, to_view(p[max(a - 1, 0):b + 1]), SEG_COLORS[name], width)
        for a, b in _runs(comp):
            draw.polyline(im, to_view(p[max(a - 1, 0):b + 1]), COMPLETED_COLOR, width, dash=(10, 6))
        for a, b in _runs(src == "claw_root_bridge"):
            draw.polyline(im, to_view(p[max(a - 1, 0):b + 1]), BRIDGE_COLOR, width)
    return im


def draw_landmarks(im, to_view, landmarks, scale=2, inside=None):
    names = {"crest": "crest", "head_tip": "head tip", "inner_deepest": "inner deepest", "claw_rightmost": "claw rightmost (S6)",
             "junction_near_wave": "junction (near wave)", "back_left_dip": "left dip"}
    offs = {"crest": (12, -14), "head_tip": (14, -12), "inner_deepest": (14, 4), "claw_rightmost": (14, 6),
            "junction_near_wave": (16, -6), "back_left_dip": (10, 12)}
    h, w = im.shape[:2]
    for k, lab in names.items():
        if k not in landmarks:
            continue
        p = to_view(np.array(landmarks[k]["px"], dtype=float))
        if not (0 <= p[0] < w and 0 <= p[1] < h):
            continue
        draw.label_point(im, p, "%s %.1f%%/%.1f%%" % (lab, landmarks[k]["pct"][0], landmarks[k]["pct"][1]),
                         "blue", scale, offset=offs[k], kind="+", size=9, width=2.0)
    return im


TITLE = "A"            # 変種がある場合は method_a_run が設定する。


def legend(im, extra=""):
    txt = TITLE + ": back=red head=magenta inner_arc=lime completed=cyan(dashed) claw_root_bridge=orange"
    if extra:
        txt += "\n" + extra
    draw.text(im, 6, 6, txt, "black", 2, bg="white", bg_alpha=0.85)
    return im


def make_all(out_dir, img, M, P, F, segs, landmarks, spectrum, plateau, vis_raw, vis_traced,
             s8_prof, sl_s, sl, bp, bs, inside_rb, S, j_idx, sens_traces=None, compat_curves=None):
    files = {}
    H, W = img.shape[:2]

    # ---- 診断: 基準輪郭に重ねる、ガウス平滑化した滑らかなメッシュ輪郭の代用線。
    if compat_curves:
        cols = ["yellow", "cyan", "blue", "black"]
        v = draw.View(img, 1400, 150, 2400, 1250, scale=1.6)
        draw_contour(v.img, v.to_view, segs, width=2.5)
        txt = "diagnostic only: base contour A + smooth stand-ins (region closed+opened with a ball of radius r): "
        for i, sg in enumerate(sorted(compat_curves)):
            draw.polyline(v.img, v.to_view(compat_curves[sg]), cols[i % len(cols)], 1.5)
            txt += "r=%d px:%s  " % (sg, cols[i % len(cols)])
        draw.text(v.img, 6, 6, txt, "black", 2, bg="white", bg_alpha=0.85)
        files["diagnostic_s7_s8_compat_head"] = imgio.save_png(
            os.path.join(out_dir, "diagnostic_s7_s8_compat_head.png"), v.img)

    # ---- オープニング半径に対する感度（平滑化前の画素間境界）。
    if sens_traces:
        cols = ["yellow", "red", "lime", "cyan", "blue", "black"]
        v = draw.View(img, 1500, 200, 2400, 1200, scale=1600.0 / 900.0)
        txt = "opening radius sensitivity (raw traces): "
        for i, rad in enumerate(sorted(sens_traces)):
            c = cols[i % len(cols)]
            draw.polyline(v.img, v.to_view(sens_traces[rad].astype(float)), c, 3.0 if rad == P["open_radius_px"] else 1.5)
            txt += "R=%d:%s%s  " % (rad, c, "(chosen)" if rad == P["open_radius_px"] else "")
        draw.text(v.img, 6, 6, txt, "black", 2, bg="white", bg_alpha=0.85)
        files["sensitivity_open_radius_head"] = imgio.save_png(
            os.path.join(out_dir, "sensitivity_open_radius_head.png"), v.img)

    # ---- 全体の重ね画像。
    full = img.copy()
    draw_contour(full, lambda p: p, segs, width=4.0, bridge_width=1.5)
    sc = 1600.0 / W
    small = draw.resize(img, new_w=1600)
    tv = lambda p: np.asarray(p, dtype=float) * sc
    draw_contour(small, tv, segs, width=2.5, bridge_width=1.0)
    y_tr = landmarks["trough_level"]["y_px"] * sc
    draw.hline(small, y_tr, "cyan", 1.0, dash=(6, 6))
    draw.text(small, 1594, y_tr - 4, "Z=0 trough level 74.7%", "cyan", 1, bg="black", anchor="rb")
    draw_landmarks(small, tv, landmarks, scale=1)
    legend(small, "candidate A, opening R=%d px; full painting 3859x2594 shown at 1600 px" % P["open_radius_px"])
    files["overlay_full_1600"] = imgio.save_png(os.path.join(out_dir, "overlay_full_1600.png"), small)
    draw_landmarks(full, lambda p: np.asarray(p, dtype=float), landmarks, scale=3)
    files["overlay_full_res"] = imgio.save_png(os.path.join(out_dir, "overlay_full_res.png"), full)

    # 波だけを大きく表示した全体図（0..2700 x 100..2100 を幅 1600 に縮小）。
    v = draw.View(img, 0, 100, 2700, 2050, scale=1600.0 / 2700.0)
    draw_contour(v.img, v.to_view, segs, width=2.5, bridge_width=1.0)
    draw_landmarks(v.img, v.to_view, landmarks, scale=1)
    legend(v.img)
    files["overlay_wave_1600"] = imgio.save_png(os.path.join(out_dir, "overlay_wave_1600.png"), v.img)

    # ---- 切出し画像と元のマスク境界を重ねた切出し画像。
    raw_outline = None
    for name, (x0, y0, x1, y1, s) in CROPS.items():
        v = draw.View(img, x0, y0, x1, y1, scale=s)
        draw_contour(v.img, v.to_view, segs, width=2.0, bridge_width=1.0)
        draw_landmarks(v.img, v.to_view, landmarks, scale=2)
        legend(v.img, "crop x %d..%d y %d..%d px, zoom %.1fx" % (x0, x1, y0, y1, s))
        files["crop_" + name] = imgio.save_png(os.path.join(out_dir, "crop_%s.png" % name), v.img)

    # ---- 診断用マスク。
    files.update(save_mask_debug(out_dir, M, segs, P))

    # ---- グラフ。
    rr = [r["R_px"] for r in spectrum]
    area = [r["removed_px2"] for r in spectrum]
    rate = [np.nan if r["d_removed_per_px_of_R"] is None else r["d_removed_per_px_of_R"] for r in spectrum]
    p1 = plot.line_plot([{"label": "removed area", "x": rr, "y": area, "color": "blue", "marker": "o"}],
                        title="pattern spectrum in the claw zone: area removed by an opening of radius R",
                        xlabel="R [px]", ylabel="removed [px^2]", size=(1100, 420),
                        vlines=[{"x": P["open_radius_px"], "label": "chosen R", "color": "red"}])
    p2 = plot.line_plot([{"label": "d(removed)/dR", "x": rr, "y": rate, "color": "green", "marker": "o"}],
                        title="removal rate (fingers: R<=20, flat: 24..32, lobes: R>=36)", xlabel="R [px]",
                        ylabel="[px^2 / px]", size=(1100, 420),
                        vlines=[{"x": P["open_radius_px"], "label": "chosen R", "color": "red"}])
    files["plot_pattern_spectrum"] = imgio.save_png(os.path.join(out_dir, "plot_pattern_spectrum.png"),
                                                    draw.vstack([p1, p2]))

    ps = plot.line_plot([{"label": "slope of the back", "x": sl_s / H * 100.0, "y": sl, "color": "red"}],
                        title="S4: slope of the back (chord over +-%.1f%% of image height)" % P["s4_tangent_window_pct_h"],
                        xlabel="arclength from the left frame edge [% of image height]", ylabel="slope [deg]",
                        size=(1100, 460), hlines=[{"y": 25, "label": "spec 25"}, {"y": 47, "label": "spec 47"},
                                                  {"y": 8, "label": "spec 8"}, {"y": 0, "label": "0"}])
    files["plot_back_slope"] = imgio.save_png(os.path.join(out_dir, "plot_back_slope.png"), ps)

    series = []
    off = 0.0
    spans = []
    for name in ("back", "head", "inner_arc"):
        pr = s8_prof[name]
        x = (pr["t"][1:] + off) / H * 100.0
        series.append({"label": name, "x": x, "y": pr["tangent_diff_deg"], "color": SEG_COLORS[name]})
        off += pr["t"][-1]
    p8 = plot.line_plot(series, title="own S8: tangent direction change between samples 1% of image height apart",
                        xlabel="arclength [% of image height]", ylabel="[deg]", size=(1300, 460),
                        hlines=[{"y": 15, "label": "S8 limit 15", "color": "black"}])
    files["plot_s8_own"] = imgio.save_png(os.path.join(out_dir, "plot_s8_own.png"), p8)

    # 接続点の根拠: 内側の弧に沿った輪郭のすぐ内側の色。
    i0 = max(j_idx - 900, 0)
    xs = np.arange(i0, min(j_idx + 300, len(inside_rb)))
    pj = plot.line_plot([{"label": "R-B inside", "x": xs - j_idx, "y": inside_rb[xs], "color": "blue"}],
                        title="junction detection: box-mean R-B %d px inside the contour (blue belly < %d)" % (
                            P["junction"]["inside_offset_px"], P["junction"]["blue_rb_max"]),
                        xlabel="arclength relative to the detected junction [px]", ylabel="R-B", size=(1100, 420),
                        vlines=[{"x": 0, "label": "junction", "color": "red"}],
                        hlines=[{"y": P["junction"]["blue_rb_max"], "label": "threshold"}])
    files["plot_junction"] = imgio.save_png(os.path.join(out_dir, "plot_junction.png"), pj)
    return files


def save_mask_debug(out_dir, M, segs, P):
    files = {}
    roi = M["roi"]
    base = roi.copy()
    draw.overlay_mask(base, M["sky"], "red", 0.40)
    if "opened" in M:
        draw.overlay_mask(base, M["body"] & ~M["opened"], "yellow", 0.55)        # オープニングで除かれた部分。
        draw.overlay_mask(base, draw.mask_outline(M["opened"], 2), "blue", 1.0)
    views = {"overview": (0, 0, roi.shape[1], roi.shape[0], 1600.0 / roi.shape[1]),
             "head": (1500, 200, 2400, 1200, 1600.0 / 900.0),
             "crest_back": (900, 150, 1900, 600, 1.6),
             "left_end": (0, 700, 800, 1200, 2.0),
             "inner_low": (1500, 1400, 2300, 2050, 2.0)}
    for name, (x0, y0, x1, y1, s) in views.items():
        v = draw.View(base, x0, y0, x1, y1, scale=s)
        draw.text(v.img, 6, 6, "debug: sky flood = red tint, removed by opening R=%d = yellow, opened region outline = blue"
                  % P["open_radius_px"], "black", 2, bg="white", bg_alpha=0.85)
        files["debug_masks_" + name] = imgio.save_png(os.path.join(out_dir, "debug_masks_%s.png" % name), v.img)
    b2 = roi.copy()
    draw.overlay_mask(b2, M["white"], "blue", 0.5)
    draw.overlay_mask(b2, M["ink"], "red", 0.5)
    v = draw.View(b2, 1500, 200, 2400, 1200, scale=1600.0 / 900.0)
    draw.text(v.img, 6, 6, "debug: barriers of the sky flood fill: ink/blue = red, paper white = blue", "black", 2,
              bg="white", bg_alpha=0.85)
    files["debug_barriers_head"] = imgio.save_png(os.path.join(out_dir, "debug_barriers_head.png"), v.img)
    return files
