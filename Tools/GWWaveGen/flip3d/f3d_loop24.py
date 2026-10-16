# -*- coding: utf-8 -*-
"""FLIP3D：毎コマの記録（DA3r）で、12 s の繰り返しの窓の始め τ を 1 コマ刻みで選び直し、画面で見える継ぎ目の跳びを測る（py -3.10 -B、numpy・scipy・PIL）。
2026-10-16 進行役のサブエージェントが新しく書いた。DA3r（DA3 の途中保存 v.1824 から同じ物理で計算し直し、面 R5 と SDF r4 を毎コマ書いた記録）を読むだけ。
決まり（測る前に書いた）：
  - 窓の長さ L = 288 コマ（12 s、入口のうねりの周期そのもの。前の窓と同じ）。見せる記録は τ〜τ+287 の 288 個（24 個/s）。最後の記録 τ+287 の次に τ を見せる。
  - τ の候補：崩れ k5 の巻き始め〜着水 + 0.5 s（DA3 の pana/best_frames.json の window_frames 2085〜2142）を全部含み、
    τ+288（計算なら次に来る面）も DA3r の記録（コマ 1825〜2161）にある τ。つまり τ = 1855〜1873（77.25〜78.0 s、19 個）。
  - 見える跳び J(τ)：記録 τ+287 → τ。物差しは f3d_loop_ana.py・f3d_seam_jump.py と同じ
      (a) 面と面の距離（片方の面の点で、もう片方の r4 の SDF を読んだ |d| の両向き。崩れの所の箱 x 225.5〜361.5・上 −9.5〜15.5・横 0.5〜84.5 m）の中央値・p95・最大
      (b) 上の水面の高さの差 Δη（hf、崩れの所 x 225〜362 m）の RMS
  - 比べの物差し：同じ τ の窓の中のふつうの 1/24 s の 1 歩 287 個の同じ値。計算どおりの 1 歩（τ+287 → τ+288）と継ぎ目の違い（τ と τ+288）も書く。
  - 選び：J(τ) の面の距離の p95 が最も小さい τ（同じ値なら Δη の RMS が小さい方）。前の 8 個/s の窓（τ = 1855）も同じ物差しで並べる。
  - 原画に最も近い瞬間：best_frames の k5 のコマ 2099（87.417 s）。毎コマの記録なので、そのコマをそのまま見せる（前は 1 コマ前の記録 2098）。
追記 AM-24a（最初の結果を見た後に足した。選びの決まりは変えない）：(a) の物差しには約 1.0 m の床がある。同じコマの面の点で同じコマの r4 の SDF を
  読んでも p95 が 1.007〜1.017 m（5 コマで確かめ、self_floor に残す）。r4 は格子 1 m の別の面なので、面の記録（R5）との食い違いが p95 に出る。
  そこで床のない 3 つ目の物差しを足す：(c) 面の記録どうしの距離 mesh_nn（片方の面の点から、もう片方の面の三角形を細かく分けた点（1 つの三角形に
  15 点）への最も近い距離の両向き。同じ箱。同じコマなら 0）。
使い方：py -3.10 -B f3d_loop24.py   → Unity/Build/FLIP3D/loop24/loop24_ana.json・loop24_ana.png（数の印：どれも【測定】）
"""
import os, sys, json, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402
from f3d_loop_ana import mesh_dist, eta_stats   # noqa: E402

L_FR = 288
K = 5
OUTD = C.OUT + "/loop24"
RUN = C.RUN24


BOX_PAD = 2.0


def tri_samples(Q, T, lo, hi, n=4):
    """箱（BOX_PAD m 広げた）に頂点が 1 つでも入る三角形を、重心の格子 i+j+k=n（15 点）で細かく分けた点。"""
    inb = np.all((Q >= lo - BOX_PAD) & (Q <= hi + BOX_PAD), axis=1)
    T = T[inb[T].any(axis=1)]
    A, B, Cc = Q[T[:, 0]], Q[T[:, 1]], Q[T[:, 2]]
    out = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            k = n - i - j
            out.append((i * A + j * B + k * Cc) / n)
    return np.concatenate(out)


def nn_dist(Pa, TreeB, Pb, TreeA):
    from scipy.spatial import cKDTree  # noqa: F401
    da, _ = TreeB.query(Pa)
    db, _ = TreeA.query(Pb)
    d = np.concatenate([da, db])
    return dict(median=float(np.median(d)), p95=float(np.percentile(d, 95)), p99=float(np.percentile(d, 99)), max=float(d.max()), n=int(len(d)))


def main():
    from scipy.spatial import cKDTree
    t0 = time.time()
    os.makedirs(OUTD, exist_ok=True)
    bf = json.load(open(C.RUN + "/pana/best_frames.json", encoding="utf8"))       # DA3 の判定（読むだけ）
    brk = {p["k"]: p for p in bf["per_breaker"]}[K]
    w0, w1 = brk["window_frames"]
    sf = C.surf_frames(RUN)
    sfs = set(sf)
    r4 = C.Rec("r4", RUN)
    hf = C.Rec("hf", RUN)
    if not all(f in sfs for f in range(sf[0], sf[-1] + 1)):
        raise RuntimeError("DA3r の面の記録に抜けがある")
    meta = r4.meta
    lo = np.array([meta["x0"], meta["y0"], meta["z0"]])
    hi = lo + np.array([meta["dx"] * (meta["nx"] - 1), meta["dy"] * (meta["ny"] - 1), meta["dz"] * (meta["nz"] - 1)])
    xs, zs = C.axes_hf(hf.meta)
    MB = np.broadcast_to(((xs >= 225.0) & (xs <= 362.0))[None, :], (len(zs), len(xs)))
    taus = [f for f in range(sf[0], sf[-1] + 1) if f <= w0 and w1 < f + L_FR and (f + L_FR) in sfs]
    need = range(min(taus), max(taus) + L_FR + 1)
    P, S, E, TR = {}, {}, {}, {}
    for f in need:
        d = C.read_surf(f, RUN)
        Q = d["P"].astype(np.float64)
        P[f] = Q[np.all((Q >= lo) & (Q <= hi), axis=1)]
        S[f] = r4.get(f)
        E[f] = hf.get(f)
        TR[f] = cKDTree(tri_samples(Q, d["tri"].astype(np.int64), lo, hi))
    floor = []
    for f in (1855, 1950, 2050, 2099, 2142):
        dd = np.abs(C.sdf_at(S[f], meta, P[f]))
        dd = dd[np.isfinite(dd)]
        floor.append(dict(frame=f, median=float(np.median(dd)), p95=float(np.percentile(dd, 95)), p99=float(np.percentile(dd, 99)), max=float(dd.max())))
    print("read", len(P), "frames", round(time.time() - t0, 1), "s"); sys.stdout.flush()

    def pair(a, b):
        return dict(frames=[a, b], t=[C.t_of(a), C.t_of(b)], mesh=mesh_dist(P[b], S[a], P[a], S[b], meta), eta_break=eta_stats(E[a], E[b], MB),
                    mesh_nn=nn_dist(P[a], TR[b], P[b], TR[a]))

    steps = {f: pair(f, f + 1) for f in range(min(taus), max(taus) + L_FR)}
    print("steps", len(steps), round(time.time() - t0, 1), "s"); sys.stdout.flush()
    rows = []
    for tau in taus:
        last = tau + L_FR - 1
        jump = pair(last, tau)
        mism = pair(tau, tau + L_FR)
        nat = steps[last]
        inn = [steps[f] for f in range(tau, last)]                 # 窓の中の 1 歩 287 個
        sm = np.array([[s["mesh"]["median"], s["mesh"]["p95"], s["mesh"]["max"], s["eta_break"]["rms"], s["mesh_nn"]["median"], s["mesh_nn"]["p95"],
                        s["mesh_nn"]["max"]] for s in inn])
        rows.append(dict(
            tau_frame=tau, tau_s=C.t_of(tau), last_frame=last, last_s=C.t_of(last),
            jump=jump, natural_step=nat, mismatch=mism,
            steps_summary=dict(n=len(inn), mesh_median_median=float(np.median(sm[:, 0])), mesh_p95_median=float(np.median(sm[:, 1])),
                               mesh_p95_min=float(sm[:, 1].min()), mesh_p95_max=float(sm[:, 1].max()), mesh_max_max=float(sm[:, 2].max()),
                               eta_rms_median=float(np.median(sm[:, 3])), eta_rms_p95=float(np.percentile(sm[:, 3], 95)), eta_rms_max=float(sm[:, 3].max()),
                               n_steps_p95_ge_jump=int((sm[:, 1] >= jump["mesh"]["p95"]).sum()),
                               n_steps_median_ge_jump=int((sm[:, 0] >= jump["mesh"]["median"]).sum()),
                               n_steps_eta_rms_ge_jump=int((sm[:, 3] >= jump["eta_break"]["rms"]).sum()),
                               nn_median_median=float(np.median(sm[:, 4])), nn_p95_median=float(np.median(sm[:, 5])), nn_p95_p95=float(np.percentile(sm[:, 5], 95)),
                               nn_p95_max=float(sm[:, 5].max()), nn_max_max=float(sm[:, 6].max()),
                               n_steps_nn_p95_ge_jump=int((sm[:, 5] >= jump["mesh_nn"]["p95"]).sum())),
            jump_over_step_nn_p95=jump["mesh_nn"]["p95"] / float(np.median(sm[:, 5])),
            jump_over_step_eta_rms=jump["eta_break"]["rms"] / float(np.median(sm[:, 3])),
            jump_over_step_mesh_p95=jump["mesh"]["p95"] / float(np.median(sm[:, 1]))))
    # 比べ：前の 8 個/s の再生（τ = 1855、記録 1855〜2140 を 3 コマおき）の見える跳び 2140 → 1855 と 0.125 s の 1 歩 95 個を、同じ 3 つの物差しで
    o8j = pair(2140, 1855)
    o8s = [pair(f, f + 3) for f in range(1855, 2140, 3)]
    o8 = np.array([[s["mesh"]["p95"], s["eta_break"]["rms"], s["mesh_nn"]["median"], s["mesh_nn"]["p95"]] for s in o8s])
    old8 = dict(jump=o8j, steps_n=len(o8s), steps_mesh_p95_median=float(np.median(o8[:, 0])), steps_eta_rms_median=float(np.median(o8[:, 1])),
                steps_eta_rms_max=float(o8[:, 1].max()), steps_nn_median_median=float(np.median(o8[:, 2])), steps_nn_p95_median=float(np.median(o8[:, 3])),
                steps_nn_p95_max=float(o8[:, 3].max()))
    best = min(rows, key=lambda r: (r["jump"]["mesh"]["p95"], r["jump"]["eta_break"]["rms"]))
    best_eta = min(rows, key=lambda r: r["jump"]["eta_break"]["rms"])
    old = [r for r in rows if r["tau_frame"] == 1855][0]
    pf = brk["frame"]
    res = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"), tag="測定", run=RUN.replace(C.REPO + "/", ""), breaker_k=K, window_frames=[w0, w1],
        rule_ja=__doc__.split("決まり（測る前に書いた）：")[1].split("使い方")[0].strip(),
        L_frames=L_FR, record_step_frames=1, tau_candidates=[taus[0], taus[-1]], n_tau=len(taus),
        chosen=dict(tau_frame=best["tau_frame"], tau_s=best["tau_s"], last_frame=best["last_frame"], last_s=best["last_s"],
                    end_frame=best["tau_frame"] + L_FR, end_s=C.t_of(best["tau_frame"] + L_FR),
                    print_frame=pf, print_t=brk["t"], print_record_index=pf - best["tau_frame"], score3=brk["score3"],
                    jump=best["jump"], natural_step=best["natural_step"], mismatch=best["mismatch"], steps_summary=best["steps_summary"],
                    jump_over_step_eta_rms=best["jump_over_step_eta_rms"], jump_over_step_mesh_p95=best["jump_over_step_mesh_p95"],
                    jump_over_step_nn_p95=best["jump_over_step_nn_p95"]),
        self_floor_r4_mesh=floor, old8_same_measures=old8,
        best_by_nn_p95=dict(tau_frame=min(rows, key=lambda r: r["jump"]["mesh_nn"]["p95"])["tau_frame"],
                            jump_nn_p95=min(r["jump"]["mesh_nn"]["p95"] for r in rows)),
        best_by_eta_rms=dict(tau_frame=best_eta["tau_frame"], tau_s=best_eta["tau_s"], jump_eta_rms=best_eta["jump"]["eta_break"]["rms"],
                             jump_mesh_p95=best_eta["jump"]["mesh"]["p95"]),
        old_tau_1855=dict(jump_mesh=old["jump"]["mesh"], jump_eta_rms=old["jump"]["eta_break"]["rms"], jump_nn=old["jump"]["mesh_nn"], steps_summary=old["steps_summary"]),
        rows=rows, seconds=round(time.time() - t0, 1))
    C.write_json(OUTD + "/loop24_ana.json", res)
    plot(res)
    print("tau   t_s     jump p95  med   max  | eta_rms | step eta med | mism p95 eta | nn med p95 max | step nn p95 med")
    for r in rows:
        j, m = r["jump"], r["mismatch"]
        print("%d %.3f  %.3f %.3f %.3f | %.3f | %.3f | %.3f %.3f | %.3f %.3f %.3f | %.3f" % (
            r["tau_frame"], r["tau_s"], j["mesh"]["p95"], j["mesh"]["median"], j["mesh"]["max"], j["eta_break"]["rms"], r["steps_summary"]["eta_rms_median"],
            m["mesh"]["p95"], m["eta_break"]["rms"], j["mesh_nn"]["median"], j["mesh_nn"]["p95"], j["mesh_nn"]["max"], r["steps_summary"]["nn_p95_median"]))
    print("floor", floor)
    print("old8 jump", {k: round(v["p95"], 3) if k != "eta_break" else round(v["rms"], 3) for k, v in o8j.items() if isinstance(v, dict)},
          {k: round(v, 3) if isinstance(v, float) else v for k, v in old8.items() if k != "jump"})
    print("chosen", best["tau_frame"], "best by eta", best_eta["tau_frame"], "seconds", res["seconds"])


def plot(res):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1400, 760
    im = Image.new("RGB", (W, H), (250, 250, 247))
    dr = ImageDraw.Draw(im)
    F = lambda s: ImageFont.truetype("C:/Windows/Fonts/NotoSansJP-VF.ttf", s)
    rows = res["rows"]
    ts = [r["tau_s"] for r in rows]
    x0, x1 = 110, W - 40
    X = lambda t: x0 + (t - ts[0]) / (ts[-1] - ts[0]) * (x1 - x0)
    dr.text((20, 10), "FLIP3D：毎コマの記録（DA3r）で窓の始め τ を 1 コマ刻みで選ぶ（崩れ k5 を含む τ = %.3f〜%.3f s）" % (ts[0], ts[-1]), font=F(22), fill=(20, 20, 20))
    dr.text((20, 42), "赤：見える跳び（最後の記録 τ+287 → 最初の記録 τ）。灰の帯：窓の中のふつうの 1/24 s の 1 歩 287 個の中央値〜最大。● ＝選んだ τ（決まりの r4 の物差しは床が約 1.0 m あるので json だけ）",
            font=F(15), fill=(60, 60, 60))
    panels = [(90, 380, "面どうしの距離 p95 (m)（mesh_nn）", lambda r: r["jump"]["mesh_nn"]["p95"], lambda r: (r["steps_summary"]["nn_p95_median"], r["steps_summary"]["nn_p95_max"])),
              (440, 700, "Δη の RMS (m)（hf、x 225〜362 m）", lambda r: r["jump"]["eta_break"]["rms"], lambda r: (r["steps_summary"]["eta_rms_median"], r["steps_summary"]["eta_rms_max"]))]
    ch = res["chosen"]["tau_frame"]
    for y0, y1, lab, fj, fb in panels:
        vmax = max(max(fj(r), fb(r)[1]) for r in rows) * 1.15
        Y = lambda v: y1 - v / vmax * (y1 - y0)
        dr.polygon([(X(r["tau_s"]), Y(fb(r)[1])) for r in rows] + [(X(r["tau_s"]), Y(fb(r)[0])) for r in rows[::-1]], fill=(222, 222, 216))
        dr.line([(x0, y1), (x1, y1)], fill=(0, 0, 0)); dr.line([(x0, y0), (x0, y1)], fill=(0, 0, 0))
        for k in range(5):
            v = vmax * k / 4
            dr.text((30, Y(v) - 8), "%.2f" % v, font=F(13), fill=(0, 0, 0)); dr.line([(x0 - 4, Y(v)), (x0, Y(v))], fill=(0, 0, 0))
        for r in rows:
            dr.line([(X(r["tau_s"]), y1), (X(r["tau_s"]), y1 + 4)], fill=(0, 0, 0))
        for t in (77.25, 77.5, 77.75, 78.0):
            dr.text((X(t) - 18, y1 + 6), "%.2f" % t, font=F(13), fill=(0, 0, 0))
        pts = [(X(r["tau_s"]), Y(fj(r))) for r in rows]
        dr.line(pts, fill=(200, 40, 40), width=2)
        for r, p in zip(rows, pts):
            rr = 6 if r["tau_frame"] == ch else 3
            dr.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=(0, 0, 0) if r["tau_frame"] == ch else (200, 40, 40))
        dr.text((x0 + 8, y0 + 4), lab, font=F(15), fill=(200, 40, 40))
    dr.text((x0 + 8, 725), "横軸＝窓の始め τ (s)", font=F(14), fill=(0, 0, 0))
    im.save(OUTD + "/loop24_ana.png")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
