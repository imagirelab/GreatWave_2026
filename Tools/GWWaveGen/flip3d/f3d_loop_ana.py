# -*- coding: utf-8 -*-
"""FLIP3D：DA3 から 12 s（うねりの 1 周期）の繰り返しの窓を選び、継ぎ目の違いを m で測る（py -3.10 -B、numpy・scipy・PIL）。
2026-10-16 進行役（Claude）が新しく書いた。
決まり（測る前に書いた）：
  - 窓の長さ L = 12 s（入口のうねりの周期そのもの。288 コマ = 面の記録 96 個）。面の記録（3 コマおき）が続けてある 47.0〜92.0 s の中で、
    窓の始め τ を記録のコマごとに動かす（τ + 12 s にも面の記録が要る）。
  - 継ぎ目の違い：繰り返しの最後の次に見せるのは τ だが、計算では τ + 12 s が来る。この 2 つの面の違いを測る。
      (a) 面と面の距離：τ + 12 s の面の点で τ の SDF（記録 r4、格子 1 m）を読んだ |d| と、その逆を合わせた中央値・p95・最大（崩れの所
          x 225.5〜361.5 m・横 0〜84.5 m・上 −9.5〜15.5 m の中。SDF は ±6 m で切ってあるので最大は 6 m まで）
      (b) 上の水面の高さの差 Δη（記録 hf、格子 1 m）の RMS・p95・最大。所は崩れの所（x 225〜362 m）と、入口の帯の外の全部（x 100〜442 m）
      比べの物差しとして、隣の記録（0.125 s 後）との同じ値も測る（ふつうの 1 歩でどれだけ動くか）
  - 続く周期の似方：C(τ) = 窓 [τ, τ+12) の各コマ t で、Δη(t) = η(t+12) − η(t) の崩れの所の RMS を平均した物（hf、3 コマおき、0〜140 s）。
    続きの 92〜140 s は面の記録が窓ごとにしかないが、hf は毎コマあるので、k2〜k9 の全部の周期を比べられる。
  - 窓の選び：判定した崩れ（pana/best_frames.json の k2〜k5）のうち、巻き始め〜着水 + 0.5 s（window_frames）を全部含む τ の中で、
    (a) の p95 が最も小さい τ。原画に最も近い瞬間はその崩れの best_frames の値（面の記録は 3 コマおきなので、最も近い記録のコマで見せる）。
使い方：py -3.10 -B f3d_loop_ana.py   → Unity/Build/FLIP3D/loop/loop_ana.json・loop_ana.png
"""
import os, sys, json, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402

L_FR = 288          # 12 s
STEP = 3            # 面の記録の間（コマ）
OUTD = C.OUT + "/loop"


def mesh_dist(PA, sdfB, PB, sdfA, meta):
    dA = np.abs(C.sdf_at(sdfB, meta, PA))
    dB = np.abs(C.sdf_at(sdfA, meta, PB))
    d = np.concatenate([dA[np.isfinite(dA)], dB[np.isfinite(dB)]])
    if len(d) == 0:
        return None
    return dict(median=float(np.median(d)), p95=float(np.percentile(d, 95)), p99=float(np.percentile(d, 99)), max=float(d.max()),
                n=int(len(d)), frac_at_clip=float(np.mean(d >= meta["clip_m"] - 1e-3)))


def eta_stats(a, b, mask):
    d = (b - a)[mask]
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return None
    return dict(rms=float(np.sqrt(np.mean(d * d))), p95=float(np.percentile(np.abs(d), 95)), max=float(np.abs(d).max()), n=int(len(d)))


def main():
    t0 = time.time()
    os.makedirs(OUTD, exist_ok=True)
    bf = json.load(open(C.RUN + "/pana/best_frames.json", encoding="utf8"))
    ev = json.load(open(C.RUN + "/pana/events.json", encoding="utf8"))
    brk = {p["k"]: p for p in bf["per_breaker"]}
    onset = {e["k"]: e for e in ev["events"] if e.get("judged")}
    sf = C.surf_frames()
    sfs = set(sf)
    hf = C.Rec("hf")
    r4 = C.Rec("r4")
    xs, zs = C.axes_hf(hf.meta)
    m_break = (xs >= 225.0) & (xs <= 362.0)
    m_all = (xs >= 100.0) & (xs <= 442.0)
    MB = np.broadcast_to(m_break[None, :], (len(zs), len(xs)))
    MA = np.broadcast_to(m_all[None, :], (len(zs), len(xs)))
    meta4 = r4.meta
    box_lo = np.array([meta4["x0"], meta4["y0"], meta4["z0"]])
    box_hi = box_lo + np.array([meta4["dx"] * (meta4["nx"] - 1), meta4["dy"] * (meta4["ny"] - 1), meta4["dz"] * (meta4["nz"] - 1)])
    # 面の点（崩れの所の箱の中だけ）を覚える
    cont = [f for f in sf if 1129 <= f <= 2209]
    P = {}
    for f in cont:
        d = C.read_surf(f)
        Q = d["P"]
        k = np.all((Q >= box_lo) & (Q <= box_hi), axis=1)
        P[f] = Q[k].astype(np.float64)
    print("surf read", len(P), "frames", round(time.time() - t0, 1), "s"); sys.stdout.flush()
    taus = [f for f in cont if (f + L_FR) in sfs and (f + L_FR) <= 2209]
    rows = []
    for f in taus:
        g = f + L_FR
        s_f, s_g = r4.get(f), r4.get(g)
        seam_mesh = mesh_dist(P[g], s_f, P[f], s_g, meta4)
        e_f, e_g = hf.get(f), hf.get(g)
        row = dict(tau_frame=f, tau_s=C.t_of(f), end_frame=g, seam_mesh=seam_mesh,
                   seam_eta_break=eta_stats(e_f, e_g, MB), seam_eta_all=eta_stats(e_f, e_g, MA))
        h = f + STEP                    # 隣の記録との比べ（ふつうの 1 歩）
        if h in P:
            row["step_mesh"] = mesh_dist(P[h], s_f, P[f], r4.get(h), meta4)
            row["step_eta_break"] = eta_stats(e_f, hf.get(h), MB)
        rows.append(row)
    print("seam rows", len(rows), round(time.time() - t0, 1), "s"); sys.stdout.flush()
    # 続く周期の似方 C(τ)（hf、3 コマおき）
    hf_fr = set(hf.frames())
    cyc = []
    f_lo, f_hi = 961, max(hf_fr) - 2 * L_FR      # 40.04 s 〜（τ + 24 s ≤ 140 s）
    H = {}

    def eta(f):
        if f not in H:
            H[f] = hf.get(f)
        return H[f]
    for f in range(f_lo, f_hi + 1, STEP):
        if not all((f + j) in hf_fr and (f + j + L_FR) in hf_fr for j in range(0, L_FR, STEP)):
            continue
        v = []
        for j in range(0, L_FR, STEP):
            s = eta_stats(eta(f + j), eta(f + j + L_FR), MB)
            if s:
                v.append(s["rms"])
        cyc.append(dict(tau_frame=f, tau_s=C.t_of(f), C_rms_break_mean=float(np.mean(v)), C_rms_break_max=float(np.max(v))))
    print("cycle rows", len(cyc), round(time.time() - t0, 1), "s"); sys.stdout.flush()
    # 窓の選び
    cand = []
    for k, p in brk.items():
        w0, w1 = p["window_frames"]
        ok = [r for r in rows if r["tau_frame"] <= w0 and w1 < r["tau_frame"] + L_FR and r["seam_mesh"]]
        if not ok:
            continue
        best = min(ok, key=lambda r: r["seam_mesh"]["p95"])
        cand.append(dict(k=k, n_tau=len(ok), tau_range_s=[ok[0]["tau_s"], ok[-1]["tau_s"]], best_tau_frame=best["tau_frame"], best_tau_s=best["tau_s"],
                         seam_mesh=best["seam_mesh"], seam_eta_break=best["seam_eta_break"], seam_eta_all=best["seam_eta_all"],
                         print_frame=p["frame"], print_t=p["t"], score3=p["score3"]))
    rule_choice = min(cand, key=lambda c: c["seam_mesh"]["p95"])
    # 追記 AM-L1（結果を見た後に足した。2026-10-16）：決まりどおりの選び（k4）では、k4 の best_frames の瞬間に覆いと唇がない（score3 1.769 は
    # 覆いのない時の値で、k2・k7・k8・k9 と同じ）。原画の視点へ移る先が唇のない前の面になるので、p95 が最小の 1.05 倍以内の候補のうち
    # score3 が最も小さい（原画に最も近い）崩れの窓を選ぶ。決まりどおりの選びも rule_choice として残す。
    near = [c for c in cand if c["seam_mesh"]["p95"] <= 1.05 * rule_choice["seam_mesh"]["p95"]]
    chosen = min(near, key=lambda c: (c["score3"], c["seam_mesh"]["p95"]))
    tau = chosen["best_tau_frame"]
    pf = chosen["print_frame"]
    rec_frames = list(range(tau, tau + L_FR, STEP))
    pr = min(rec_frames, key=lambda f: abs(f - pf))
    # 選んだ τ の周期の数（k2〜k9 の全部の周期を同じ位相で）
    cyc_d = {c["tau_frame"]: c for c in cyc}
    seam_d = {r["tau_frame"]: r for r in rows}
    per_cycle = []
    for n in range(-6, 8):
        f = tau + n * L_FR
        ks = [k for k, p in brk.items() if f <= p["frame"] < f + L_FR]               # 窓の中に原画に最も近い瞬間がある崩れ
        ks_next = [k for k, p in brk.items() if f + L_FR <= p["frame"] < f + 2 * L_FR]
        c = cyc_d.get(f)
        if c is None:
            continue
        sh = eta_stats(eta(f), eta(f + L_FR), MB)
        per_cycle.append(dict(tau_frame=f, tau_s=C.t_of(f), cycle=("k%s→k%s" % (ks[0] if ks else "?", ks_next[0] if ks_next else "?")),
                              C_rms_break_mean=c["C_rms_break_mean"], C_rms_break_max=c["C_rms_break_max"], seam_eta_break=sh,
                              seam_mesh=(seam_d[f]["seam_mesh"] if f in seam_d else None)))
    steps = [r["step_mesh"]["p95"] for r in rows if r.get("step_mesh")]
    steps_e = [r["step_eta_break"]["rms"] for r in rows if r.get("step_eta_break")]
    res = dict(
        run=C.RUN, created=time.strftime("%Y-%m-%d %H:%M:%S"), rule_ja=__doc__.split("決まり（測る前に書いた）：")[1].split("使い方")[0].strip(),
        L_frames=L_FR, L_s=L_FR / C.FPS_SIM, record_step_frames=STEP,
        surf_windows_s=[[47.0, 92.0], [95.9167, 102.7917], [107.9167, 114.7917], [119.9167, 126.7917], [131.9167, 138.75]],
        candidates=cand,
        rule_choice=dict(k=rule_choice["k"], tau_frame=rule_choice["best_tau_frame"], tau_s=rule_choice["best_tau_s"], seam_mesh=rule_choice["seam_mesh"],
                         score3=rule_choice["score3"]),
        amendment_ja="追記 AM-L1（結果を見た後）：決まりどおりの選びは k%d（p95 %.3f m）だが、その崩れの best_frames の瞬間に覆いと唇がない（score3 %.3f）。"
                     "p95 が最小の 1.05 倍以内の候補のうち score3 が最も小さい崩れ k%d（p95 %.3f m、score3 %.3f）の窓を選んだ" % (
                         rule_choice["k"], rule_choice["seam_mesh"]["p95"], rule_choice["score3"], chosen["k"], chosen["seam_mesh"]["p95"], chosen["score3"]),
        chosen=dict(k=chosen["k"], tau_frame=tau, tau_s=C.t_of(tau), end_frame=tau + L_FR, end_s=C.t_of(tau + L_FR),
                    record_frames=[rec_frames[0], rec_frames[-1]], n_records=len(rec_frames),
                    print_frame_bestframes=pf, print_t_bestframes=chosen["print_t"], print_record_frame=pr, print_record_t=C.t_of(pr),
                    print_record_index=rec_frames.index(pr), print_record_offset_frames=pr - pf, score3=chosen["score3"],
                    seam_mesh=chosen["seam_mesh"], seam_eta_break=chosen["seam_eta_break"], seam_eta_all=chosen["seam_eta_all"]),
        step_reference=dict(mesh_p95_median=float(np.median(steps)), mesh_p95_max=float(np.max(steps)), eta_break_rms_median=float(np.median(steps_e))),
        per_cycle=per_cycle, seam_rows=rows, cycle_rows=cyc, seconds=round(time.time() - t0, 1))
    C.write_json(OUTD + "/loop_ana.json", res)
    plot(res, onset, brk)
    print(json.dumps(dict(candidates=cand, chosen=res["chosen"], step_reference=res["step_reference"],
                          per_cycle=[dict((k, v) for k, v in c.items()) for c in per_cycle]), ensure_ascii=False, indent=1, default=float))


def plot(res, onset, brk):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1600, 900
    im = Image.new("RGB", (W, H), (250, 250, 247))
    dr = ImageDraw.Draw(im)
    F = lambda s: ImageFont.truetype("C:/Windows/Fonts/NotoSansJP-VF.ttf", s)
    x0, x1 = 90, W - 40
    t_lo, t_hi = 40.0, 116.0
    X = lambda t: x0 + (t - t_lo) / (t_hi - t_lo) * (x1 - x0)
    dr.text((20, 10), "FLIP3D：DA3 の 12 s の繰り返しの窓の選び（横軸＝窓の始め τ）", font=F(24), fill=(20, 20, 20))
    dr.text((20, 44), "上：継ぎ目の違い（τ と τ+12 s の面の距離の p95、記録 r4・格子 1 m）。下：続く周期の似方 C(τ)（Δη の RMS の周期の平均、記録 hf、崩れの所 x 225〜362 m）。"
            "灰の帯＝面の記録が続けてある τ の範囲。縦線＝巻き始め。● ＝選んだ τ", font=F(15), fill=(60, 60, 60))
    panels = [(100, 460, "継ぎ目 面の距離 p95 (m)", [(r["tau_s"], r["seam_mesh"]["p95"]) for r in res["seam_rows"] if r["seam_mesh"]], (200, 40, 40)),
              (540, 860, "C(τ) Δη RMS の平均 (m)", [(c["tau_s"], c["C_rms_break_mean"]) for c in res["cycle_rows"]], (30, 80, 170))]
    for y0, y1, lab, pts, col in panels:
        vmax = max(v for _, v in pts) * 1.1
        Y = lambda v: y1 - v / vmax * (y1 - y0)
        dr.rectangle([X(47.0), y0, X(80.04), y1], fill=(232, 232, 228))
        dr.line([(x0, y1), (x1, y1)], fill=(0, 0, 0)); dr.line([(x0, y0), (x0, y1)], fill=(0, 0, 0))
        for tt in range(40, 117, 4):
            dr.line([(X(tt), y1), (X(tt), y1 + 5)], fill=(0, 0, 0)); dr.text((X(tt) - 10, y1 + 6), "%d" % tt, font=F(13), fill=(0, 0, 0))
        for k in range(5):
            v = vmax * k / 4
            dr.text((20, Y(v) - 8), "%.2f" % v, font=F(13), fill=(0, 0, 0)); dr.line([(x0 - 4, Y(v)), (x0, Y(v))], fill=(0, 0, 0))
        for k, e in onset.items():
            dr.line([(X(e["on_t"]), y0), (X(e["on_t"]), y1)], fill=(180, 120, 40)); dr.text((X(e["on_t"]) + 3, y0), "k%d" % k, font=F(13), fill=(180, 120, 40))
        pts = sorted(pts)
        for a, b in zip(pts[:-1], pts[1:]):
            if b[0] - a[0] < 0.2:
                dr.line([(X(a[0]), Y(a[1])), (X(b[0]), Y(b[1]))], fill=col, width=2)
        dr.text((x0 + 8, y0 + 18), lab, font=F(15), fill=col)
        ch = res["chosen"]
        v = [p[1] for p in pts if abs(p[0] - ch["tau_s"]) < 1e-6]
        if v:
            dr.ellipse([X(ch["tau_s"]) - 6, Y(v[0]) - 6, X(ch["tau_s"]) + 6, Y(v[0]) + 6], fill=(0, 0, 0))
    ch = res["chosen"]
    dr.text((x0 + 8, 492), "選んだ窓 %.3f〜%.3f s（崩れ k%d を含む）。継ぎ目：面の距離 中央値 %.2f m・p95 %.2f m・最大 %.2f m、Δη の RMS %.2f m（隣の記録 0.125 s の 1 歩の p95 の中央値 %.2f m）"
            % (ch["tau_s"], ch["end_s"], ch["k"], ch["seam_mesh"]["median"], ch["seam_mesh"]["p95"], ch["seam_mesh"]["max"], ch["seam_eta_break"]["rms"],
               res["step_reference"]["mesh_p95_median"]), font=F(15), fill=(0, 0, 0))
    im.save(OUTD + "/loop_ana.png")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
