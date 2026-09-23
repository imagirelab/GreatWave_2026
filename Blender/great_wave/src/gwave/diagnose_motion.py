"""断面曲線の運動モデルを2Dで診断する。時間別の断面、仕様6.2の曲線、自己交差を確認する。
実行: tools/run_blender.ps1 src/gwave/diagnose_motion.py"""
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
    bootstrap.log("最終形状: n_u", mo.n_u, "波頭／先端／最深点の番号", mo.i_c, mo.i_t, mo.i_d,
                  "左端の角度 %.1f 度、延長 %.2f H" % (F["left_alpha_deg"], F["left_extension_used_H"]))
    fm = F["metrics"]
    bootstrap.log("最終形状の指標: h %.4f x_c %.4f theta %.1f o %.4f phi %s S8最大 %.2f" % (
        fm["h"], fm["x_c"], fm["theta"], fm["o"], fm["phi"]["deg"] if fm["phi"] else None,
        fm["S8"]["max_tangent_diff_deg"]))
    seg = np.hypot(np.diff(mo.q[:, 0]), np.diff(mo.q[:, 1]))
    bootstrap.log("最終形状の試料間隔（高さ比%%）: 最小 %.2f、最大 %.2f" % (pm.H_to_pct_h(seg.min()), pm.H_to_pct_h(seg.max())))
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
    bootstrap.log("最初に波頭が張り出すフレーム", int(on[0, 0]) if len(on) else None, "自己交差（5フレームごと）", n_bad)
    bootstrap.log("張り出し開始まで h は単調増加:", bool(np.all(np.diff(R[:int(WP['frame_overhang_onset']), 2]) >= -1e-9)),
                  "開始後の h の最大低下率 %.3f%%" % (100 * (R[:, 2].max() - R[-1, 2])))
    oo = R[R[:, 10] > 0.5, 5]
    ph = R[R[:, 10] > 0.5, 6]
    bootstrap.log("o は単調増加:", bool(np.all(np.diff(oo) >= -1e-6)), "最小増分 %.5f" % (np.diff(oo).min() if len(oo) > 1 else 0))
    bootstrap.log("phi の変化: 最大上昇 %.3f 度、開始 %.1f -> 最終 %.1f" % (
        np.nanmax(np.diff(ph)) if len(ph) > 1 else 0, ph[0] if len(ph) else np.nan, ph[-1] if len(ph) else np.nan))
    bootstrap.log("フレーム1の theta %.1f、theta>=80 となる最初のフレーム: %s" % (R[0, 4], int(R[R[:, 4] >= 80][0, 0]) if (R[:, 4] >= 80).any() else None))
    v = R[:, 9]
    bootstrap.log("フレーム間の頂点変位の最大値 %.4f H（フレーム %d）、最終フレーム %.5f（最大値の %.1f %%）" % (
        v.max(), int(R[int(np.argmax(v)), 0]), v[-1], 100 * v[-1] / v.max()))

    # ---- 診断画像
    cols = [(27, 58, 107), (31, 95, 168), (42, 140, 196), (53, 176, 160), (124, 195, 106), (212, 196, 71),
            (240, 162, 58), (236, 106, 44), (216, 52, 42), (142, 27, 27)]
    key = [1, 60, 110, 140, 152, 170, 190, 210, 250, 285]
    series = [{"label": "f%d" % f, "x": mo.profile(f)[:, 0], "y": mo.profile(f)[:, 1], "color": cols[i % len(cols)]}
              for i, f in enumerate(key)]
    a = plot.line_plot(series, title="XZ [H]", xlabel="X [H]", ylabel="Z [H]",
                       size=(1700, 620), equal_aspect=True, xlim=(-6.2, 2.2), ylim=(-0.1, 1.15))
    series2 = []
    for i, f in enumerate(key):
        p = mo.profile(f)
        series2.append({"label": "f%d" % f, "x": p[:, 0] - p[mo.i_c, 0], "y": p[:, 1], "color": cols[i % len(cols)]})
    b = plot.line_plot(series2, title="XZ - Xc [H]", xlabel="X - Xc [H]",
                       ylabel="Z [H]", size=(1700, 900), equal_aspect=True, xlim=(-1.6, 1.4), ylim=(-0.05, 1.1))
    vl = [{"x": float(WP["frame_overhang_onset"]), "label": "t1"}, {"x": float(WP["frame_curl_start"]), "label": "t2"}]
    pl = []
    for j, (nm, yl) in enumerate([("h", 2), ("x_c", 3), ("theta", 4), ("o", 5), ("phi", 6), ("dmax/f [H]", 9)]):
        pl.append({"series": [{"label": nm, "x": R[:, 0], "y": R[:, yl], "color": (192, 57, 43)}], "title": nm,
                   "xlabel": "f", "ylabel": nm, "size": (1700, 300), "vlines": vl})
    try:
        c = plot.multi_plot(pl, ncols=1)
    except Exception as ex:                                           # vlines の形式が不明なら縦線なしで再描画する。
        bootstrap.log("縦線付き multi_plot に失敗しました（%r）。縦線なしで再試行します" % (ex,))
        for d in pl:
            d.pop("vlines", None)
        c = plot.multi_plot(pl, ncols=1)
    imgio.save_png(os.path.join(out, "profiles_world.png"), a)
    imgio.save_png(os.path.join(out, "profiles_aligned.png"), b)
    imgio.save_png(os.path.join(out, "curves.png"), c)
    bootstrap.log("出力先", out)
    bootstrap.finish(True, "diagnose_motion")


if __name__ == "__main__":
    main()
