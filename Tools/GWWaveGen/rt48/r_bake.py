# -*- coding: utf-8 -*-
"""RT48（計画 §2.4）：毎コマの断面の曲線から、Unity で再生する形（焼き）を作り、C3・C4・自分との交わり・K を確かめる（py -3.10）。
使い方:
  py -3.10 r_bake.py coarse                    R3 の記録（断面 0.5 m ＋ その外は一番上の水面）から → Unity/Build/RT48/data/coarse/
  py -3.10 r_bake.py fine <fine_dir>           粒子から作った細かい面（r_surface.py の出力）から → Unity/Build/RT48/data/fine/
出力（どちらも同じ形。manifest.json に全部の説明と SHA-256）：
  pairs.bin   float32 リトルエンディアン、(組 P, 2, 点 N, 2)。組 p はコマ k = 3319 + p と k + 1。[p, 0] が A（コマ k の線の上の点）、
              [p, 1] が B（コマ k + 1 の線の上の点）。最後の 2 は (X, Y)：X = x_rel − 527.0 m、Y = 静かな水面からの高さ（m）。
  loops.bin   float32 リトルエンディアン、(点の総数, 2) の (X, Y)。コマごとの閉じた線（水の塊と囲んだ空気）を全部並べた物。索引は manifest。
  manifest.json
読み方は Unity/Build/RT48/record_ja.md（計画の読み方 3〜5・9〜11）と Unity/Build/RT48/data/record_ja.md の「焼きの読み方」。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 数値の部品のスレッドの予約（1 つの起動で約 0.6 GB）を小さくする
    _os.environ.setdefault(_v, "1")
import sys, os, json, time, hashlib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L

DATA = os.environ.get("RT48_DATA", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/data")   # 試しの時だけ環境変数で替える
TOL_C3 = 0.02
TOL_C4_MAX, TOL_C4_P99 = 0.25, 0.05
NALPHA = 30


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ 元
class Coarse:
    name = "coarse"
    label = "粗い元（計算の格子 0.5 m の面）"

    def __init__(self):
        self.rec = L.Records(L.R3)
        self.off = L.OFF_R3
        sh = json.load(open(os.path.join(L.R3, "shape.json"), encoding="utf8"))
        self.onset_frame = int(sh["onset"]["frame"]); self.touch_frame_r3 = int(sh["touchdown"]["frame"])

    def frame(self, f):
        fr = L.coarse_frame(self.rec, f, self.off)
        return fr

    def describe(self):
        return dict(kind="coarse", r3_dir=L.R3, still_offset_m=self.off,
                    how="板の真ん中（z = 0）の断面の解く格子の水面の場（sec、0.5 m、float16）の 0 の等高線（静かな水面から 25 m 下より上）を "
                        "x 321.54〜863.04 m に使い、その外（100.04〜321.04 m と 863.54〜924.54 m）は一番上の水面の高さ（hf の z = 0 の節、0.5 m おき）でつなぐ。"
                        "同じコマが二つの起動にある時は始めが最も遅い起動の記録（C1 (a) でバイト単位で同じ）。",
                    inputs={os.path.basename(p): sha(p) for p in sorted(self.rec.used)})


class Fine:
    name = "fine"
    label = "粒子から作った細かい面（Zhu & Bridson, 0.125 m）"

    def __init__(self, d):
        self.d = d
        self.meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf8"))
        self.off = float(self.meta["still_offset_m"])
        self.onset_frame = self.meta.get("onset_frame")
        self.files = {}

    def frame(self, f):
        p = os.path.join(self.d, "phi_%04d.npz" % f)
        z = np.load(p)
        self.files[os.path.basename(p)] = p
        phi = z["phi"].astype(np.float32)
        xs = float(z["x0_rel"]) + float(z["dx"]) * np.arange(phi.shape[1])
        ys = float(z["y0_abs"]) + float(z["dy"]) * np.arange(phi.shape[0]) - self.off
        opn, loops = L.field_curves(phi, xs, ys)
        main, ok, others = L.pick_main(opn, xs[0], xs[-1])
        return dict(main=main, loops=loops, main_ok=ok, other_open=len(others), stitch=[0.0, 0.0], field=(phi, xs, ys))

    def describe(self):
        return dict(kind="fine", fine_dir=self.d, still_offset_m=self.off, surface_meta=self.meta,
                    inputs_note="phi_FFFF.npz の SHA-256 は fine_dir/meta.json と r_surface の記録")


# ------------------------------------------------------------------ 本体
def run(src, f_first=L.F0, f_last=L.F1, out_dir=None):
    T0 = time.time()
    out_dir = out_dir or os.path.join(DATA, src.name)
    os.makedirs(out_dir, exist_ok=True)
    frames = list(range(f_first, f_last + 1))
    F = {}
    if f_first == L.F0:
        xc = L.CREST_START
    else:   # 試しの短い範囲：粗い元の焼きの頂から始める
        cm = json.load(open(os.path.join(DATA, "coarse", "manifest.json"), encoding="utf8"))
        xc = next(r["crest_x"] for r in cm["frames"] if r["frame"] == f_first)
    rows = []
    for f in frames:
        fr = src.frame(f)
        m = fr["main"]
        ic = L.crest_in(m, xc)
        xc, yc = float(m[ic, 0]), float(m[ic, 1])
        il = L.lip_tip(m, ic, xc)
        w0, w1 = xc - L.WIN_I, xc + L.WIN_I
        inwin = [lp for lp in fr["loops"] if lp["pts"][:, 0].max() >= w0 and lp["pts"][:, 0].min() <= w1]
        topo = (sum(1 for q in inwin if q["phase"] == 1), sum(1 for q in inwin if q["phase"] == -1), sum(1 for q in inwin if q["phase"] == 0))
        # 読み方 7（RT48）：空気を囲む閉じた線（面積 0.25 m² 以上、窓 ±30 m、頂より下）
        cav = [q for q in inwin if q["phase"] == 1 and q["area"] >= L.VOX * L.VOX and q["pts"][:, 1].mean() < yc]
        F[f] = dict(main=m, loops=fr["loops"], ic=ic, il=il, xc=xc, yc=yc, topo=topo, field=fr["field"])
        rows.append(dict(frame=f, t=L.t_of(f), crest_x=xc, crest_y=yc, lip=None if il is None else [float(m[il, 0]), float(m[il, 1])],
                         topo_air_water_unknown=list(topo), n_loops=len(fr["loops"]), main_pts=len(m), main_len=float(L.arclen(m)[-1]),
                         main_ok=bool(fr["main_ok"]), other_open=fr["other_open"], stitch=fr["stitch"],
                         cavity_big=[[float(q["pts"][:, 0].max()), float(q["area"])] for q in cav]))
    t_load = time.time() - T0
    # ---- K（読み方 3）
    K = None
    for f in frames[1:]:
        if F[f]["topo"] != F[f - 1]["topo"]:
            K = f
            break
    onset = src.onset_frame
    contact = next((r["frame"] for r in rows if r["cavity_big"] and (onset is None or r["frame"] > onset)), None)
    last_interp_k = (K - 2) if K is not None else f_last - 1
    # ---- C4（読み方 11）
    def blend_pair(ka, kb, alpha, landmarks=True):
        A, B = F[ka], F[kb]
        la, lb = [A["ic"]], [B["ic"]]
        if landmarks and A["il"] is not None and B["il"] is not None and A["il"] > A["ic"] and B["il"] > B["ic"]:
            la.append(A["il"]); lb.append(B["il"])
        if not landmarks:
            la, lb = [], []
        Pa, Pb, marks = L.resample_pair(A["main"], la, B["main"], lb)
        return (1 - alpha) * Pa + alpha * Pb

    def wdist(P, k):
        w = (F[k]["xc"] - L.WIN_I, F[k]["xc"] + L.WIN_I)
        d1, d2 = L.two_way(P, F[k]["main"], h=0.01, win=w)
        d = np.concatenate([d1, d2])
        return float(d.max()), float(np.percentile(d, 99))

    c4 = []
    c4_arc = []
    noise = []
    e3 = []
    fail_k = set()
    for k in frames:
        if k + 2 > last_interp_k + 1:      # k + 2 ≤ K − 1
            break
        mx, p99 = wdist(blend_pair(k, k + 2, 0.5), k + 1)
        ok = mx <= TOL_C4_MAX and p99 <= TOL_C4_P99
        c4.append(dict(k=k, max=mx, p99=p99, ok=ok))
        if not ok:
            fail_k.update([k, k + 1])
        amx, ap99 = wdist(blend_pair(k, k + 2, 0.5, landmarks=False), k + 1)
        c4_arc.append(dict(k=k, max=amx, p99=ap99))
        # 参考（判定にしない）：頂から 150 m 離れた同じ幅の窓での同じ量（水面の小さな揺れの大きさを見る）
        if (k - f_first) % 4 == 0:
            xcn = F[k + 1]["xc"]
            cx = xcn + 150.0 if xcn + 180.0 <= 920.0 else xcn - 150.0
            d1, d2 = L.two_way(blend_pair(k, k + 2, 0.5), F[k + 1]["main"], h=0.01, win=(cx - L.WIN_I, cx + L.WIN_I))
            dd = np.concatenate([d1, d2])
            if len(dd):
                noise.append(dict(k=k, center_x=cx, max=float(dd.max()), p99=float(np.percentile(dd, 99))))
        if k + 3 <= last_interp_k + 1:
            for a, kk in ((1 / 3, k + 1), (2 / 3, k + 2)):
                e3.append(wdist(blend_pair(k, k + 3, a), kk)[0])
    t_c4 = time.time() - T0 - t_load
    E2 = float(np.median([r["max"] for r in c4])) if c4 else None
    E3 = float(np.median(e3)) if e3 else None
    p_obs = float(np.log((9 / 8) * E3 / E2) / np.log(1.5)) if (E2 and E3 and E2 > 0 and E3 > 0) else None
    err_step = (E2 * 2 ** (-p_obs)) if (p_obs is not None and 1.5 <= p_obs <= 2.5) else None
    # ---- 組（A・B）、自分との交わり（読み方 10）、C3
    P = len(frames) - 1
    pairs = np.zeros((P, 2, L.N_PTS, 2), np.float32)
    ptab, c3max = [], 0.0
    n_x = 0
    for p in range(P):
        k = frames[p]
        A, B = F[k], F[k + 1]
        interp = k <= last_interp_k and k not in fail_k
        reason = "interp" if interp else ("after_K" if k > last_interp_k else "C4_fail")
        marks = []
        if interp:
            la, lb = [A["ic"]], [B["ic"]]
            if A["il"] is not None and B["il"] is not None and A["il"] > A["ic"] and B["il"] > B["ic"]:
                la.append(A["il"]); lb.append(B["il"])
            Pa, Pb, marks = L.resample_pair(A["main"], la, B["main"], lb)
            w = (min(A["xc"], B["xc"]) - L.WIN_I, max(A["xc"], B["xc"]) + L.WIN_I)
            bad = []
            for j in range(1, NALPHA):
                a = j / NALPHA
                C = (1 - a) * Pa + a * Pb
                nx = L.seg_intersect_any(C, w)
                nm = L.monotone_outside(C, w)
                if nx or nm:
                    bad.append([j, nx, nm])
            if bad:
                interp = False; reason = "self_intersection"; n_x += 1
                Pa, Pb, marks = L.resample_uniform(A["main"]), L.resample_uniform(B["main"]), []
        else:
            Pa, Pb = L.resample_uniform(A["main"]), L.resample_uniform(B["main"])
            bad = []
        # C3：取り直した線と元の線の距離（両向き）
        d1, d2 = L.two_way(Pa, A["main"], h=0.005)
        d3, d4 = L.two_way(Pb, B["main"], h=0.005)
        c3 = float(max(d1.max(), d2.max(), d3.max(), d4.max()))
        c3max = max(c3max, c3)
        pairs[p, 0] = np.stack([Pa[:, 0] - L.X0_BAKE, Pa[:, 1]], 1)
        pairs[p, 1] = np.stack([Pb[:, 0] - L.X0_BAKE, Pb[:, 1]], 1)
        ptab.append(dict(p=p, k=k, t_k=L.t_of(k), interp=bool(interp), reason=reason, marks=[int(v) for v in marks], c3_max=c3,
                         self_x=bad[:5]))
    t_pairs = time.time() - T0 - t_load - t_c4
    # ---- 閉じた線
    lp_pts, ltab, off = [], [], 0
    for f in frames:
        ent = []
        for q in F[f]["loops"]:
            pts = np.stack([q["pts"][:, 0] - L.X0_BAKE, q["pts"][:, 1]], 1).astype(np.float32)
            lp_pts.append(pts)
            ent.append([off, len(pts), int(q["phase"]), round(float(q["area"]), 5)])
            off += len(pts)
        ltab.append(dict(frame=f, loops=ent))
    loops = np.concatenate(lp_pts, 0) if lp_pts else np.zeros((0, 2), np.float32)
    # ---- 船（読み方 2・4）：コマごとの上下・縦揺れ、かぶさった水が船体に入るコマ
    boat = {}
    for xb in L.SEATS:
        hv, pt, hit = [], [], None
        for f in frames:
            h, a, _ = L.boat(F[f]["main"], xb)
            hv.append(round(h, 6)); pt.append(round(a, 5))
            if hit is None and contact is not None and f >= contact:
                S, xs, ys = F[f]["field"]
                mv = L.multivalued_cols(S, xs, ys)
                if np.any((mv >= xb - L.HULL / 2) & (mv <= xb + L.HULL / 2)):
                    hit = f
        end = (hit - 1) if hit is not None else f_last
        i_end = end - f_first
        boat["%g" % xb] = dict(seat_x_rel=xb, X_unity_origin=xb - L.X0_BAKE, heave_m=hv, pitch_deg=pt,
                               overturned_on_hull_frame=hit, overturned_on_hull_t=None if hit is None else L.t_of(hit),
                               clip_end_frame=end, clip_end_t=L.t_of(end),
                               heave_min_max_to_end=[min(hv[:i_end + 1]), max(hv[:i_end + 1])], pitch_min_max_to_end=[min(pt[:i_end + 1]), max(pt[:i_end + 1])],
                               heave_rate_max_mps=float(np.max(np.abs(np.diff(hv[:i_end + 1]))) * L.FPS),
                               pitch_rate_max_degps=float(np.max(np.abs(np.diff(pt[:i_end + 1]))) * L.FPS))
    # ---- 書き出し
    pp = os.path.join(out_dir, "pairs.bin"); lpth = os.path.join(out_dir, "loops.bin")
    pairs.astype("<f4").tofile(pp)
    loops.astype("<f4").tofile(lpth)
    n_interp = sum(1 for r in ptab if r["interp"])
    man = dict(
        format="RT48 bake v1", source=src.name, label=src.label, date=time.strftime("%Y-%m-%d %H:%M:%S"),
        tool="Tools/GWWaveGen/rt48/r_bake.py", source_info=src.describe(),
        units=dict(length="m", time="s (計算の時刻。始めから)", angle="deg"),
        coords=dict(X="x_rel − 527.0 m（x_rel は造波板からの距離。波は −X から +X へ進む）", Y="静かな水面からの高さ (m)",
                    origin_x_rel=L.X0_BAKE, x_paddle_scene=L.XP, still_offset_m=src.off,
                    unity="Unity の X = (X + 527.0) − 座席の x_rel、Y = Y、Z = 頂の向き（形は Z によらない）"),
        time=dict(fps=L.FPS, frame_time="t(f) = (f − 1) / 24", first_frame=f_first, last_frame=f_last, n_frames=len(frames),
                  t_first=L.t_of(f_first), t_last=L.t_of(f_last)),
        playback=dict(rule="t を含む組 p = floor((t − t_first)·24)（0〜P−1 に切る）。interp が true なら α = (t − t_k)·24 で (1−α)A + αB。"
                           "false なら A（前のコマ）をそのまま見せる。t ≥ t_last では最後の組の B。",
                      K=K, last_interp_pair_k=last_interp_k, n_pairs=P, n_interp=n_interp,
                      caption_K="K のコマ（%s s）から「ここから 24 コマ/秒、補間なし」" % (None if K is None else round(L.t_of(K), 4))),
        files=dict(pairs=dict(name="pairs.bin", dtype="<f4", shape=[P, 2, L.N_PTS, 2], bytes=os.path.getsize(pp), sha256=sha(pp)),
                   loops=dict(name="loops.bin", dtype="<f4", shape=[int(len(loops)), 2], bytes=os.path.getsize(lpth), sha256=sha(lpth))),
        n_points=L.N_PTS,
        pairs=ptab, loops_index=ltab,
        loops_note="loops[i] = [点の始めの番号, 点の数, 相（−1＝水の塊、+1＝囲んだ空気、0＝決まらない）, 面積 m²]。補間せずにコマごとに描く（水の塊）。空気は船からの絵では描かない",
        frames=[{k: v for k, v in r.items()} for r in rows],
        events=dict(onset_frame=onset, onset_t=None if onset is None else L.t_of(onset), first_contact_frame=contact,
                    first_contact_t=None if contact is None else L.t_of(contact), K=K, K_t=None if K is None else L.t_of(K),
                    K_minus_contact=None if (K is None or contact is None) else K - contact),
        boat=boat, boat_note="上下＝船体の 9 点（座席 ±6 m）の一番上の水面の平均、縦揺れ＝同じ 9 点の最小二乗の傾き（+x へ上る時を正、船首は −x）。"
                             "コマごとの値（K から先はこれを時刻で線形に補間する。K の前は描いている曲線から求める）",
        x_fade=dict(ranges_x_rel=[[100.0, 200.0], [825.0, 925.0]], rule="高さに 1 → 0 の余弦の重み（Unity の描き方。焼きの点には掛けていない）"),
        checks=dict(
            C3=dict(max=c3max, tol=TOL_C3, ok=c3max <= TOL_C3, how="各組の A とコマ k の線、B とコマ k+1 の線の距離（両向き、0.005 m に細かくして最も近い点）の最大"),
            C4=dict(tol_max=TOL_C4_MAX, tol_p99=TOL_C4_P99, n=len(c4), n_fail=sum(1 for r in c4 if not r["ok"]),
                    max_of_max=max([r["max"] for r in c4], default=None), max_of_p99=max([r["p99"] for r in c4], default=None),
                    E2=E2, E3=E3, p_observed=p_obs, err_at_1_24s=err_step,
                    err_note=None if err_step is not None else "1/24 s の誤差は測れていない（観測した次数が 1.5〜2.5 の外か、測れなかった）",
                    far_window_reference=dict(n=len(noise), median_max=float(np.median([q["max"] for q in noise])) if noise else None,
                                              median_p99=float(np.median([q["p99"] for q in noise])) if noise else None,
                                              note="判定にしない参考。頂から 150 m 離れた ±30 m の窓で、同じ (k, k+2) の割合 0.5 と k+1 の距離（4 コマおき）",
                                              rows=noise),
                    arc_only=dict(max_of_max=max([r["max"] for r in c4_arc], default=None), max_of_p99=max([r["p99"] for r in c4_arc], default=None),
                                  n_fail=sum(1 for r in c4_arc if not (r["max"] <= TOL_C4_MAX and r["p99"] <= TOL_C4_P99))),
                    rows=c4, rows_arc_only=c4_arc),
            self_intersection=dict(n_pairs_stopped=n_x, alphas="j/30, j = 1〜29"),
            main_ok_all=all(r["main_ok"] for r in rows), other_open_max=max(r["other_open"] for r in rows),
            stitch_max_abs=max(max(abs(v) for v in r["stitch"]) for r in rows),
        ),
        seconds=dict(load=round(t_load, 1), c4=round(t_c4, 1), pairs=round(t_pairs, 1), total=round(time.time() - T0, 1)),
    )
    mp = os.path.join(out_dir, "manifest.json")
    json.dump(man, open(mp, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    summ = dict(source=src.name, K=K, onset=onset, contact=contact, n_interp=n_interp, n_pairs=P, C3=man["checks"]["C3"],
                C4={k: (v if k != "far_window_reference" else {q: w for q, w in v.items() if q != "rows"})
                    for k, v in man["checks"]["C4"].items() if not k.startswith("rows")}, self_x=n_x,
                boat={k: {q: v[q] for q in ("overturned_on_hull_frame", "clip_end_frame", "clip_end_t", "heave_min_max_to_end", "pitch_min_max_to_end",
                                            "heave_rate_max_mps", "pitch_rate_max_degps")} for k, v in boat.items()},
                files=man["files"], main_ok=man["checks"]["main_ok_all"], other_open_max=man["checks"]["other_open_max"],
                stitch=man["checks"]["stitch_max_abs"], seconds=man["seconds"], manifest_sha256=sha(mp))
    json.dump(summ, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=float))
    return summ


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("kind"); ap.add_argument("fine_dir", nargs="?")
    ap.add_argument("--f0", type=int, default=L.F0); ap.add_argument("--f1", type=int, default=L.F1); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(Coarse() if a.kind == "coarse" else Fine(a.fine_dir), a.f0, a.f1, a.out)
