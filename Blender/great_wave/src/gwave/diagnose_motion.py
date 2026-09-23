"""2-D diagnosis of the section motion model (no mesh): profiles over time, spec-6.2 curves, self-intersections.
Run:  tools/run_blender.ps1 src/gwave/diagnose_motion.py"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import numpy as np

from gw import bootstrap, imgio, paths, plot
from gw import profile_metrics as pm
from gwave import profile_motion as wm


def main():
    bootstrap.set_log_prefix("GW")
    WP = wm.load_wave_params()
    mo = wm.WaveMotion(WP)
    out = paths.ensure_dir(os.path.join(paths.PROJECT_DIR if hasattr(paths, "PROJECT_DIR") else wm.PROJECT,
                                        "results", "wave_build", "diagnose"))
    F = mo.final
    bootstrap.log("final: n_u", mo.n_u, "crest/tip/deep idx", mo.i_c, mo.i_t, mo.i_d,
                  "left alpha deg %.1f ext %.2f H" % (F["left_alpha_deg"], F["left_extension_used_H"]))
    fm = F["metrics"]
    bootstrap.log("final metrics: h %.4f x_c %.4f theta %.1f o %.4f phi %s S8max %.2f" % (
        fm["h"], fm["x_c"], fm["theta"], fm["o"], fm["phi"]["deg"] if fm["phi"] else None,
        fm["S8"]["max_tangent_diff_deg"]))
    seg = np.hypot(np.diff(mo.q[:, 0]), np.diff(mo.q[:, 1]))
    bootstrap.log("final sample spacing pct_h: min %.2f max %.2f" % (pm.H_to_pct_h(seg.min()), pm.H_to_pct_h(seg.max())))
    t_on = mo.tau_onset()
    bootstrap.log("tau_onset %.4f" % t_on)

    frames = np.arange(1, mo.n_frames + 1)
    rows = []
    n_bad = 0
    prev = None
    for f in frames:
        p = mo.profile(int(f))
        m = pm.measure_profile(p)
        nx = wm.polyline_self_intersections(p) if f % 5 == 0 or f == mo.n_frames else 0
        n_bad += nx
        disp = 0.0 if prev is None else float(np.max(np.hypot(*(p - prev).T)))
        prev = p
        rows.append([f, mo.tau_of_frame(int(f)), m["h"], m["x_c"], m["theta"], m["o"],
                     m["phi"]["deg"] if m["phi"] else np.nan, m["cavity_depth"] or 0.0, nx, disp,
                     1.0 if m["overhanging"] else 0.0])
    R = np.array(rows, dtype=float)
    np.save(os.path.join(out, "motion_table.npy"), R)
    on = R[R[:, 10] > 0.5]
    bootstrap.log("first overhanging frame", int(on[0, 0]) if len(on) else None, "self-intersections (every 5th frame)", n_bad)
    bootstrap.log("h monotone until onset:", bool(np.all(np.diff(R[:int(WP['frame_overhang_onset']), 2]) >= -1e-9)),
                  "max h drop after onset pct %.3f" % (100 * (R[:, 2].max() - R[-1, 2])))
    oo = R[R[:, 10] > 0.5, 5]
    ph = R[R[:, 10] > 0.5, 6]
    bootstrap.log("o monotone:", bool(np.all(np.diff(oo) >= -1e-6)), "min step %.5f" % (np.diff(oo).min() if len(oo) > 1 else 0))
    bootstrap.log("phi steps: max upward %.3f deg; phi onset %.1f -> final %.1f" % (
        np.nanmax(np.diff(ph)) if len(ph) > 1 else 0, ph[0] if len(ph) else np.nan, ph[-1] if len(ph) else np.nan))
    bootstrap.log("theta at frame 1 %.1f, first frame theta>=80: %s" % (R[0, 4], int(R[R[:, 4] >= 80][0, 0]) if (R[:, 4] >= 80).any() else None))
    v = R[:, 9]
    bootstrap.log("max vertex disp/frame %.4f H at frame %d; last-frame disp %.5f (%.1f %% of max)" % (
        v.max(), int(R[int(np.argmax(v)), 0]), v[-1], 100 * v[-1] / v.max()))

    # ---- pictures
    cols = [(27, 58, 107), (31, 95, 168), (42, 140, 196), (53, 176, 160), (124, 195, 106), (212, 196, 71),
            (240, 162, 58), (236, 106, 44), (216, 52, 42), (142, 27, 27)]
    key = [1, 60, 110, 140, 152, 170, 190, 210, 250, 285]
    series = [{"label": "f%d" % f, "x": mo.profile(f)[:, 0], "y": mo.profile(f)[:, 1], "color": cols[i % len(cols)]}
              for i, f in enumerate(key)]
    a = plot.line_plot(series, title="section profiles (world X, H units)", xlabel="X [H]", ylabel="Z [H]",
                       size=(1700, 620), equal_aspect=True, xlim=(-6.2, 2.2), ylim=(-0.1, 1.15))
    series2 = []
    for i, f in enumerate(key):
        p = mo.profile(f)
        series2.append({"label": "f%d" % f, "x": p[:, 0] - p[mo.i_c, 0], "y": p[:, 1], "color": cols[i % len(cols)]})
    b = plot.line_plot(series2, title="same, aligned at the crest sample (shape change only)", xlabel="X - X_crest [H]",
                       ylabel="Z [H]", size=(1700, 900), equal_aspect=True, xlim=(-1.6, 1.4), ylim=(-0.05, 1.1))
    vl = [{"x": float(WP["frame_overhang_onset"]), "label": "onset"}, {"x": float(WP["frame_curl_start"]), "label": "curl"}]
    pl = []
    for j, (nm, yl) in enumerate([("h", 2), ("x_c", 3), ("theta", 4), ("o", 5), ("phi", 6), ("max sample step / frame [H]", 9)]):
        pl.append({"series": [{"label": nm, "x": R[:, 0], "y": R[:, yl], "color": (192, 57, 43)}], "title": nm,
                   "xlabel": "frame", "ylabel": nm, "size": (1700, 300), "vlines": vl})
    try:
        c = plot.multi_plot(pl, ncols=1)
    except Exception as ex:                                           # vlines format unknown -> plain plots
        bootstrap.log("multi_plot with vlines failed (%r); retrying without" % (ex,))
        for d in pl:
            d.pop("vlines", None)
        c = plot.multi_plot(pl, ncols=1)
    imgio.save_png(os.path.join(out, "profiles_world.png"), a)
    imgio.save_png(os.path.join(out, "profiles_aligned.png"), b)
    imgio.save_png(os.path.join(out, "curves.png"), c)
    bootstrap.log("wrote", out)
    bootstrap.finish(True, "diagnose_motion")


if __name__ == "__main__":
    main()
