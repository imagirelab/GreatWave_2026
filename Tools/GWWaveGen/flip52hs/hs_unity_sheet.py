# -*- coding: utf-8 -*-
"""FLIP52HS hs_unity_sheet: image measures and comparison sheets of the Unity captures made by hs_unity_compare.py
(py -3.10 -B; numpy, scipy, PIL). 2026-10-18 written new (Claude subagent). Reads only; writes under Unity/Build/FLIP52B/hires/unity_cmp/.

Image measures [measured on the Unity JPEG captures, 8-bit luma Y = 0.299 R + 0.587 G + 0.114 B]:
  water mask   hue < 205 deg and Y < 160 (sky and the flat outer sea are excluded), AND over all rows of the same view (the same pixels for
               every row), eroded 8 px (no silhouette edge).
  fine         mean |Y - Gauss(1.5 px)(Y)| on the mask: per-pixel detail (facet edges, ripples, specks).
  band         mean |Gauss(1.5 px)(Y) - Gauss(6 px)(Y)|: the 2-8 px scale (facets / lumps of about 0.3-2 m at these distances).
  specks       pixels darker than their 9 x 9 median by more than 20 levels, per megapixel of mask (the dark dashes of inverted slivers).
Numbers of the earlier steps (read from their json, tags kept): Houdini crop variants hs_upper_compare_f2112.json (visible surface:
  distance to b0_base, crest change, dihedral, normal jump) and hs_surface_test_f2112*.json (cook s, full-frame MB estimate); exporter variants
  hs_smooth_report.json (crest-region distance, crest change, normal step across edges, smoothing s / frame).
"""
import os, sys, json, math, time
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "2"
sys.dont_write_bytecode = True
import numpy as np                                    # noqa: E402
from scipy import ndimage as ndi                      # noqa: E402
from PIL import Image, ImageDraw, ImageFont           # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
HIRES = REPO + "/Unity/Build/FLIP52B/hires"
OUT = HIRES + "/unity_cmp"
OUT3D = REPO + "/Unity/Build/FLIP3D"
TOOL = "Tools/GWWaveGen/flip52hs/hs_unity_sheet.py"

VIEWS = [("print", "cap_hires_test_views", "cprint", "print view (hero pose)"),
         ("seat", "cap_hires_test_views", "cseat", "seat A view"),
         ("crest2x", "cap_hires_test_close_f%d", "cprint", "crest face 2x (print camera, FOV 11.75)"),
         ("near2x", "cap_hires_test_close_f%d", "cseat", "near water 2x (seat A eye, FOV 27.5)")]


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def font(sz, bold=False):
    for p in (("C:/Windows/Fonts/arialbd.ttf",) if bold else ()) + ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/YuGothM.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def luma(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def water_mask(rgb):
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"), np.float32)
    h = hsv[..., 0] * 360.0 / 255.0
    return (h < 205.0) & (luma(rgb.astype(np.float32)) < 160.0)


def frame_path(view, f, idx):
    sub = VIEWS[[v[0] for v in VIEWS].index(view)]
    d = OUT + "/" + (sub[1] % f if "%d" in sub[1] else sub[1])
    return d + "/%s/frame_%05d.jpg" % (sub[2], idx)


def rows_of(f):
    man = jload(OUT3D + "/clip_hires_test_views/manifest.json")
    allr = man["test_records"]
    vi = {(r["key"], r["frame"]): i for i, r in enumerate(allr)}
    cm = jload(OUT3D + "/clip_hires_test_close_f%d/manifest.json" % f)["test_records"]
    ci = {(r["key"], r["frame"]): i for i, r in enumerate(cm)}
    return [dict(r, views_idx=vi[(r["key"], r["frame"])], close_idx=ci[(r["key"], r["frame"])]) for r in allr if r["frame"] == f]


def idx_for(view, r):
    return r["views_idx"] if view in ("print", "seat") else r["close_idx"]


def measures(f):
    rows = rows_of(f)
    out = {}
    for view, _, _, _ in VIEWS:
        imgs = [np.asarray(Image.open(frame_path(view, f, idx_for(view, r))).convert("RGB")) for r in rows]
        m = np.ones(imgs[0].shape[:2], bool)
        for im in imgs:
            m &= water_mask(im)
        m = ndi.binary_erosion(m, iterations=8)
        out[view] = dict(mask_px=int(m.sum()))
        for r, im in zip(rows, imgs):
            Y = luma(im.astype(np.float32))
            g15 = ndi.gaussian_filter(Y, 1.5)
            g6 = ndi.gaussian_filter(Y, 6.0)
            med = ndi.median_filter(Y, size=9)
            sp = (Y < med - 20.0) & m
            out[view][r["key"]] = dict(fine=float(np.abs(Y - g15)[m].mean()), band=float(np.abs(g15 - g6)[m].mean()),
                                       specks_per_mpx=float(sp.sum() / max(m.sum(), 1) * 1e6), specks=int(sp.sum()))
    return out


def numbers(key, f):
    """[measured] / [computed] numbers of the earlier steps for the label column."""
    up = jload(HIRES + "/test_f2112/hs_upper_compare_f2112.json") or {}
    st = {}
    for p in ("hs_surface_test_f2112.json", "hs_surface_test_f2112_b2.json"):
        j = jload(HIRES + "/test_f2112/" + p) or {}
        st.update(j.get("variants") or {})
    sm = jload(HIRES + "/test_smooth/hs_smooth_report.json") or {}
    L = []
    hv = (up.get("variants") or {})
    if key in ("hero",):
        u = hv.get("hero", {}).get("upper", {})
        d = u.get("dihedral_deg_p50_p90_p95_p99") or [None] * 4
        s = (((sm.get("frames") or {}).get(str(f)) or {}).get("variants") or {}).get("orig", {})
        nr = s.get("normal_rough_crest") or {}
        L.append("now: 0.5 m voxels, adaptivity 0.005")
        if f == 2112:
            L.append("facets: dihedral p90/p99 %.1f/%.1f deg" % (d[1], d[3]))
        L.append("crest normal step med/p90 %.1f/%.1f deg" % (nr.get("edge_angle_deg_median", float("nan")), nr.get("edge_angle_deg_p90", float("nan"))))
        L.append("cost: 2.1 MB/frame, 4.0 GB clip [measured]")
        return L
    if key in hv or key.startswith("a0_v050_dse_N3"):
        k2 = "a0_v050_dse" if key == "a0_v050_dse_N3" else key
        v = hv.get(k2, {})
        u = v.get("upper", {})
        d = u.get("dihedral_deg_p50_p90_p95_p99") or [float("nan")] * 4
        c = v.get("upper_vs_base") or {}
        tb = c.get("to_base_mean_p95_p99_max_m") or [float("nan")] * 4
        s = st.get(k2, {})
        if key == "b0_base":
            L.append("check: hero settings re-surfaced")
            L.append("vs hero <= 3.9 mm; pixels mean 0.01-0.03 lv")
            L.append("(composite seam check)")
            return L
        L.append("shape: mean %.1f cm, max %.2f m" % (tb[0] * 100, tb[3]))
        L.append("crest %+.3f m, section %+.3f m" % (c.get("crest_y_change_m", float("nan")), c.get("section_crest_y_change_m", float("nan"))))
        L.append("facets: dihedral p90/p99 %.1f/%.1f deg" % (d[1], d[3]))
        if key == "a0_v050_dse_N3":
            L.append("+ normals averaged 3x (no shape change)")
        L.append("cost: %.1f MB/frame, %.0f GB clip [computed]" % (s.get("full_frame_mb_est", float("nan")), s.get("full_clip_gb_est_1849_frames", float("nan"))))
        L.append("crop cook %.0f s (contended) [measured]" % s.get("cook_s", float("nan")))
        return L
    s = (((sm.get("frames") or {}).get(str(f)) or {}).get("variants") or {}).get(key, {})
    if s:
        nr = s.get("normal_rough_crest") or {}
        to = s.get("to_orig_surface_crest") or {}
        ot = s.get("orig_to_new_surface_crest") or {}
        dv = s.get("delta_vs_orig") or {}
        mx = max(to.get("max") or 0.0, ot.get("max") or 0.0)
        L.append("shape: crest-region max %.1f cm" % (mx * 100) if mx > 0 else "shape: unchanged (normals only)")
        L.append("crest top %+.3f m" % (dv.get("top3d_m") or 0.0))
        L.append("crest normal step med/p90 %.1f/%.1f deg" % (nr.get("edge_angle_deg_median", float("nan")), nr.get("edge_angle_deg_p90", float("nan"))))
        mb = (s.get("readback") or {}).get("bytes", 0) / 1e6
        L.append("cost: %.1f MB/frame, %.2f s/frame [measured]" % (mb, (s.get("info") or {}).get("t_smooth_s", float("nan"))))
    return L


ROW_TEXT = {
    "hero": "hero (as played now)",
    "b0_base": "A b0_base (check)",
    "a0_adapt0": "A adapt0: adaptivity 0",
    "v050": "A v050: 0.25 m voxels",
    "v050_dseg": "A v050_dseg: 0.25 m + SDF smooth",
    "a0_v050_dse": "A a0_v050_dse: 0.25 m, adapt 0, dse",
    "a0_v050_dseg": "A a0_v050_dseg: + gauss",
    "a0_v050_dse_N3": "A+B a0_v050_dse + N3",
    "N3": "B N3: normals averaged",
    "T2": "B T2: Taubin 2",
    "T2S1wN2": "B T2S1wN2: Taubin+subdiv+N2",
}


def sheet(f, M, path, cell=(720, 405), keys=None, gain=1.0, crop=None, title_extra=""):
    rows = rows_of(f)
    if keys:
        rows = [r for k in keys for r in rows if r["key"] == k]
    views = [v for v in VIEWS]
    lw = 430
    W, H = cell
    top = 96
    can = Image.new("RGB", (lw + W * len(views), top + H * len(rows)), (246, 246, 243))
    dr = ImageDraw.Draw(can)
    dr.text((12, 10), "Frame %d (sim t %.3f s) - same particles, same cameras, Unity FLIP3D player, 1920x1080 captures%s" % (f, (f - 1) / 24.0, title_extra),
            fill=(10, 10, 10), font=font(24, True))
    dr.text((12, 44), "A = Houdini re-surface of the SAME particles (crop x 200-300 m, |lat| <= 40 m; outside it = hero mesh).  B = exporter smoothing of the hero records.  "
            "Physics (particles) unchanged in every row.", fill=(40, 40, 40), font=font(17))
    dr.text((12, 68), "image numbers under each cell [measured]: fine = mean |Y - blur1.5px|, band = 2-8 px detail, sp = dark specks per Mpx (8-bit levels)",
            fill=(40, 40, 40), font=font(17))
    for j, (view, _, _, vt) in enumerate(views):
        pass
    for i, r in enumerate(rows):
        y0 = top + i * H
        dr.rectangle((0, y0, lw - 1, y0 + H - 1), outline=(200, 200, 200))
        dr.text((10, y0 + 8), ROW_TEXT.get(r["key"], r["key"]), fill=(0, 0, 0), font=font(21, True))
        for k, line in enumerate(numbers(r["key"], f)):
            dr.text((10, y0 + 42 + 25 * k), line, fill=(30, 30, 30), font=font(17))
        for j, (view, _, _, vt) in enumerate(views):
            im = Image.open(frame_path(view, f, idx_for(view, r))).convert("RGB")
            if crop and view in crop:
                im = im.crop(crop[view])
            if gain != 1.0:
                a = np.asarray(im, np.float32)
                mu = a.reshape(-1, 3).mean(0)
                im = Image.fromarray(np.clip((a - mu) * gain + mu, 0, 255).astype(np.uint8))
            im = im.resize((W, H), Image.LANCZOS)
            x0 = lw + j * W
            can.paste(im, (x0, y0))
            mm = (M.get(view) or {}).get(r["key"])
            lab = vt if i == 0 else view
            dr.rectangle((x0, y0, x0 + W - 1, y0 + 24), fill=(0, 0, 0))
            dr.text((x0 + 6, y0 + 3), lab, fill=(255, 255, 255), font=font(16))
            if mm:
                t = "fine %.2f  band %.2f  sp %.0f" % (mm["fine"], mm["band"], mm["specks_per_mpx"])
                dr.rectangle((x0, y0 + H - 24, x0 + W - 1, y0 + H - 1), fill=(0, 0, 0))
                dr.text((x0 + 6, y0 + H - 22), t, fill=(255, 255, 160), font=font(16))
            dr.rectangle((x0, y0, x0 + W - 1, y0 + H - 1), outline=(120, 120, 120))
    can.save(path, quality=90)
    return path


def main(a):
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL, measures={}, sheets=[])
    for f in (2112, 2149):
        M = measures(f)
        res["measures"][str(f)] = M
        p = sheet(f, M, OUT + "/sheet_f%d_all_views.jpg" % f)
        res["sheets"].append(p)
    # detail sheet: native pixels (1:1 crops of the 2x close-ups), contrast x2, the candidates
    keys = ["hero", "N3", "T2S1wN2", "a0_adapt0", "a0_v050_dse", "a0_v050_dse_N3", "a0_v050_dseg"]
    crop = {"crest2x": (480, 260, 1440, 800), "near2x": (480, 300, 1440, 840), "print": (300, 420, 1260, 960), "seat": (700, 600, 1660, 1140)}
    M = res["measures"]["2112"]
    p = sheet(2112, M, OUT + "/sheet_f2112_detail_1to1_contrast2.jpg", cell=(960, 540), keys=keys, gain=2.0, crop=crop,
              title_extra="  |  DETAIL: 1:1 pixel crops, contrast x2")
    res["sheets"].append(p)
    json.dump(res, open(OUT + "/sheet_measures.json", "w", encoding="utf-8"), indent=1)
    for f in ("2112", "2149"):
        print(f)
        for view in ("print", "seat", "crest2x", "near2x"):
            mv = res["measures"][f][view]
            print("  ", view, "mask", mv["mask_px"], " ".join("%s:%.3f/%.3f/%.0f" % (k, v["fine"], v["band"], v["specks_per_mpx"]) for k, v in mv.items() if k != "mask_px"))
    print(res["sheets"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
