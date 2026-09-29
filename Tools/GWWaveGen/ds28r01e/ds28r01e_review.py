# -*- coding: utf-8 -*-
"""設計28修正01 試行E：依頼の目標（E1〜E6）と D の目標（M1〜M4）を、パッケージ（Unity の再生器と同じ Hermite）から測り、C1・D と並べる検査器。

生成器のコードは読まない（パッケージ・時間曲線・K* のフォルダーだけ）。試行D の検査器（ds28r01d_review.py）の測り方をそのまま使い
（M1 の Θ・Lo・vdef、M2 の再上昇と加速度、M3 の谷、M4 の J1・J3・頂の角、試行C の巻き下がりの検査）、E の目標を足す：
  E1 前面の立ち方（行 159・192、画面の時刻）：Θ 45°・90° の時刻とその時の H/Hf（90° は H ≥ 0.72 Hf から）、Θ が 85〜110° にある時間、
     唇ができる前（Lo < 0.05H、H ≥ 0.3 Hf）の頂の角 θc の最小（≥ 125°）と θc ≤ 110° の時間、小山 → C（Θ45 → Lo 0.15H）の画面の時間（≥ 3 s）、
     形の変わる速さ vdef_up の最大（C1 より 40% 以上小さい）とその立ち上がり（≤ 2.0 m/s²、速さの段がない）。
  E2 峰の行の巻き下がりの画面 10 s より後の割合（≤ 0.50）：独立の検査器（作業場所 ds28r01d_check/c2_curl.py）と同じ読み
     （列 199・200・223 と K* の唇先の列。唇先が頂より画面 t = 0 の時より 1 m 前へ出た時から t* までの、頂に対する高さの下がりのうち、
     画面 10 s より後の割合）と、試行C の読み（ds28r01c_curl.row_curl の share_after_t10）。単調（再上昇）と重力だけ（M2）は D の読み。
  E3 keypose の精度：量子化の刻み（16 bit だけ・精度の層つき）、法線の二階差分の p99 の比（節点のこま ÷ 間のこま、画面 60 fps、
     t 7.0〜11.55 s、作業場所 ds28r01d_check/c4_jag.py と同じ読み。止めの前までの窓も記録）を 16 bit だけ・精度の層つきの両方で。GPU の見積もり。
  E4 止めの長さ（時間曲線の速さが r0 から 0 へ落ちる区間）と、唇先の画面の加速度の最大（最後の 1 s。波の枠と地面の両方）。止めが 0.5 s より
     長い時は、M2 の画面の読みを実際の止めの始まりの前までにした読み（no_rebound_before_stop）も記録する。
  E6 画面の最後の 2 s の頂の尖り θc(t 10) − θc(t*)（≤ 5°）と、その間の θc の最小。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_review.py --tags C1,D,E --out Unity/Build/Design/28R01E/review/review_E.json
  版は TAGS の表か --tag-spec 'E2=<pkg>|<warp>|<kstar>|<carry_start_sigma>' で足す。--skip で重い項目を省く（j5,spatial など）。
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DSD = os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01d")
for p in (DSD, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds28r01d_review as RV  # noqa: E402

DG, DGW, CC, RB = RV.DG, RV.DGW, RV.CC, RV.RB
r3 = RV.r3
absrepo = RV.absrepo
TAGS = dict(RV.TAGS)
TAGS["E"] = dict(pkg="Unity/Build/Design/28R01E/E/art_on", warp="Tools/GWWaveGen/ds28r01e/timewarp_default_E.json",
                 kstar="Unity/Build/Design/28R01D/kstar_foot", carry_sigma=-3.85)
ROWS = RV.ROWS
TIP = RV.TIP


class FinePackage(DG.Package):
    """ds27_gates.Package（16 bit の読み）に、精度の層（ds27_pos_lo_rgba8.bin、試行E の後方互換の追加）があれば足して読む。"""

    def __init__(self, d, ks, fine=True):
        super().__init__(d, ks)
        J = self.meta
        self.fine = False
        self.hi_step_mm = float(np.max(np.asarray(J["bbox_size"], float))) / 65535 * 1000
        self.step_mm = self.hi_step_mm
        if fine and J.get("pos_lo_file"):
            p = os.path.join(self.dir, J["pos_lo_file"])
            sha = DG.sha256_file(p)
            self._chk("pos_lo_sha256 がファイルと一致", sha == J.get("pos_lo_sha256"), sha[:12])
            lo8 = np.fromfile(p, np.uint8).reshape(self.L, self.P.shape[1], self.P.shape[2], 4)
            self._chk("精度の層の A = 255", bool((lo8[..., 3] == 255).all()), "")
            sz = np.asarray(J["bbox_size"], float)
            for l in range(self.L):
                self.P[l] = (self.P[l].astype(np.float64) + (lo8[l, ..., :3].astype(np.float64) / 255.0 - 0.5) / 65535.0 * sz).astype(np.float32)
            del lo8
            self.fine = True
            self.step_mm = self.hi_step_mm / 255.0


def open_pkg(spec, fine=True):
    d = DGW.patch_kstar(spec["kstar"])
    ks = DG.KStar(d)
    pk = FinePackage(absrepo(spec["pkg"]), ks, fine=fine)
    W = json.load(open(absrepo(spec["warp"]), encoding="utf-8"))
    return ks, pk, np.asarray(W["t"], float), np.asarray(W["tau"], float)


def warp_info(wt, wtau):
    rate = np.gradient(wtau, wt)
    k12 = int(np.nonzero(wtau >= -1e-12)[0][0])
    r0 = float(np.median(rate[max(k12 - 400, 0):k12 - 300])) if k12 > 400 else float(rate[0])
    # 止め：速さが r0 の 99% を下回ってから t* まで
    k = k12
    while k > 0 and rate[k - 1] < 0.99 * r0:
        k -= 1
    return dict(t_star=float(wt[k12]), r0=round(r0, 4), stop_start_t=round(float(wt[k]), 4), stop_len_s=round(float(wt[k12] - wt[k]), 4),
                tau_at_t0=round(float(wtau[0]), 4), tau_at_t10=round(float(np.interp(10.0, wt, wtau)), 4))


# ---------------------------------------------------------------- E1・E6
def front_and_crest(ks, pk, wt, wtau, fps=60.0):
    ts = np.arange(int(round(12.0 * fps)) + 1) / fps
    taus = np.interp(ts, wt, wtau)
    A, Y = RV.sections_at(pk, ks, taus, ROWS)
    rate = np.interp(ts, wt, np.gradient(wtau, wt))
    out = {}
    jB, jE = 18, int(ks.j_E)
    for k, r in enumerate(ROWS):
        M = [RV.sec_metrics(A[n, k], Y[n, k], jB, jE, TIP[r]) for n in range(len(ts))]
        Th = np.array([m["Theta"] for m in M])
        H = np.array([m["H"] for m in M])
        Lo = np.array([m["Lo"] for m in M]) / H
        h = H / H[-1]
        th = DG.row_metrics(A[:, k], Y[:, k], np.full(len(ts), int(ks.crest_hi[r])), jE)["theta"]
        e = {nm: RV.cross(ts, x, thr) for nm, x, thr in (("Theta45", Th, 45), ("Theta90", Th, 90), ("Lo0.05H", Lo, 0.05), ("Lo0.10H", Lo, 0.10),
                                                        ("Lo0.15H", Lo, 0.15))}
        lip_t = e["Lo0.05H"] if e["Lo0.05H"] is not None else 12.0
        mm = (ts < lip_t) & (h >= 0.3)
        i10 = int(np.searchsorted(ts, 10.0))
        vert = (Th >= 85) & (Th <= 110)
        o = dict(events={kk: (None if v is None else dict(t=r3(v), tau=r3(float(np.interp(v, ts, taus))), H_over_Hf=r3(float(np.interp(v, ts, h)))))
                         for kk, v in e.items()},
                 Theta90_H_over_Hf=r3(float(np.interp(e["Theta90"], ts, h))) if e["Theta90"] else None,
                 Theta45_H_over_Hf=r3(float(np.interp(e["Theta45"], ts, h))) if e["Theta45"] else None,
                 Theta_85_110_s=r3(float(vert.sum() / fps), 2),
                 theta_c_min_before_lip_deg=r3(float(np.nanmin(th[mm])), 1) if mm.any() else None,
                 theta_c_min_before_lip_t=r3(float(ts[mm][np.nanargmin(th[mm])]), 2) if mm.any() else None,
                 theta_c_le110_before_lip_s=r3(float(((th <= 110) & mm).sum() / fps), 2),
                 theta_c_le110_all_s=r3(float(((th <= 110) & (h >= 0.3) & (ts < 10.0)).sum() / fps), 2),
                 sharpen_last2s_deg=r3(float(th[i10] - th[-1]), 2), theta_c_t10_deg=r3(float(th[i10]), 1), theta_c_tstar_deg=r3(float(th[-1]), 1),
                 theta_c_min_last2s_deg=r3(float(np.nanmin(th[i10:])), 1),
                 theta_c_at_t={("%.1f" % t): r3(float(th[int(round(t * fps))]), 1) for t in (4.0, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 9.0, 10.0, 11.0, 11.5, 12.0)})
        out[str(r)] = o
    return out


# ---------------------------------------------------------------- E2（独立の検査器 c2_curl.py の読み）
def curl_share(ks, pk, wt, wtau):
    ts2 = np.arange(0, 12.0 + 1e-9, 1 / 60)
    taus = np.interp(ts2, wt, wtau)
    A, Y = RV.sections_at(pk, ks, taus, ROWS)
    jB, jE = 18, int(ks.j_E)
    out = {}
    for k, r in enumerate(ROWS):
        a, y = A[:, k], Y[:, k]
        H = y[:, jB:jE + 1].max(1)
        jc = np.argmax(y[:, jB:jE + 1], 1) + jB
        cols = sorted({199, 200, 223, int(ks.tip_col[r])})
        o = {}
        for jtp in cols:
            hh = y[:, jtp] - H
            dx = a[np.arange(len(ts2)), jtp] - a[np.arange(len(ts2)), jc]
            dx = dx - dx[0]
            iv = np.nonzero(dx >= 1.0)[0]
            if not len(iv):
                o[str(jtp)] = None
                continue
            i0 = iv[0]
            drop = hh[i0] - hh[-1]
            hr = hh[i0:]
            i10 = np.searchsorted(ts2, 10.0)
            o[str(jtp)] = dict(t_visible=r3(ts2[i0], 3), H_over_Hf_visible=r3(H[i0] / H[-1]), rel_h_visible_m=r3(hh[i0]), rel_h_tstar_m=r3(hh[-1]),
                               drop_m=r3(drop), share_after_t10=r3((hh[i10] - hh[-1]) / drop) if drop > 0 else None,
                               rel_rerise_after_visible_m=r3(float(np.max(hr - np.minimum.accumulate(hr)))))
        out[str(r)] = o
    return out


# ---------------------------------------------------------------- E4（J7）：唇先の画面の加速度（最後の 1 s）
def tip_screen_accel(ks, pk, wt, wtau):
    ts = np.arange(10.5, 12.0 + 1e-9, 1 / 240)
    taus = np.interp(ts, wt, wtau)
    out = {}
    for r in ROWS:
        j = int(ks.tip_col[r])
        vidx = np.array([r * ks.nu + j])
        W = pk.sub(taus, vidx, 0)[:, 0, :]                      # 地面（ワールド）
        Lc = W - pk.origin(taus)                                 # 波の枠
        dt = 1 / 240

        def acc(P):
            a = (P[2:] - 2 * P[1:-1] + P[:-2]) / dt ** 2
            return np.linalg.norm(a, axis=1)
        m = ts[1:-1] >= 11.0
        out[str(r)] = dict(tip_col=j, max_world_mps2=r3(float(acc(W)[m].max()), 2), max_wave_frame_mps2=r3(float(acc(Lc)[m].max()), 2))
    return out


# ---------------------------------------------------------------- E3（J5）
def j5(ks, pk, wt, wtau, t_end):
    R, C = ks.nv, ks.nu
    r_, c_ = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a_ = (r_ * C + c_).ravel()
    b_ = ((r_ + 1) * C + c_).ravel()
    cc = (r_ * C + c_ + 1).ravel()
    d_ = ((r_ + 1) * C + c_ + 1).ravel()
    tris = np.concatenate([np.stack([a_, b_, cc], 1), np.stack([cc, b_, d_], 1)])

    def normals(P):
        V = P.reshape(-1, 3)
        fn = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
        n = np.zeros_like(V)
        for k in range(3):
            np.add.at(n, tris[:, k], fn)
        return (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)).reshape(R, C, 3)
    ts = np.arange(7.0, t_end + 1e-9, 1 / 60)
    tq = np.interp(ts, wt, wtau)
    Ns = np.stack([normals(pk.local(float(t))).astype(np.float32) for t in tq])
    d2 = np.linalg.norm(Ns[2:] - 2 * Ns[1:-1] + Ns[:-2], axis=-1) * 57.2958
    mv = pk.P[-1][..., 1] > 0.3
    p99 = np.array([np.percentile(d2[i][mv], 99) for i in range(d2.shape[0])])
    tmid = tq[1:-1]
    step = np.abs(np.gradient(tq))[1:-1] / 2
    dk = np.min(np.abs(tmid[:, None] - pk.knots[None, :]), 1)
    atk = dk <= step + 1e-9
    return dict(window_t=[7.0, r3(t_end, 3)], frames=int(len(p99)), knot_frames=int(atk.sum()),
                p99_knot_median_deg=r3(float(np.median(p99[atk])), 4), p99_between_median_deg=r3(float(np.median(p99[~atk])), 4),
                ratio_knot_over_between=r3(float(np.median(p99[atk]) / np.median(p99[~atk])), 3), p99_max_deg=r3(float(p99.max()), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="C1,D,E")
    ap.add_argument("--tag-spec", action="append", default=[])
    ap.add_argument("--out", default="Unity/Build/Design/28R01E/review/review_E.json")
    ap.add_argument("--skip", default="", help="省く項目（pace,rise,m2,trough,spatial,theta,curl,e1,e2,j7,j5）")
    a = ap.parse_args()
    for s in a.tag_spec:
        k, v = s.split("=", 1)
        pkg, warp, kst, cs = v.split("|")
        TAGS[k] = dict(pkg=pkg, warp=warp, kstar=kst, carry_sigma=float(cs))
        RV.TAGS[k] = TAGS[k]
    skip = set(x for x in a.skip.split(",") if x)
    res = {}
    rise = {}
    for tag in a.tags.split(","):
        t0 = time.time()
        spec = TAGS[tag]
        ks, pk, wt, wtau = open_pkg(spec, fine=True)
        wi = warp_info(wt, wtau)
        e = dict(spec=spec, pos_sha256=pk.pos_sha, layers=int(pk.L), fine_layer=bool(pk.fine), quant_step_mm=r3(pk.step_mm, 4),
                 quant_step_hi_mm=r3(pk.hi_step_mm, 3), gpu_estimate=pk.meta.get("gpu_estimate"), pos_precision=pk.meta.get("pos_precision"),
                 landmarks=dict(j_corner=int(ks.j_corner), j_E=int(ks.j_E)), warp=wi, package_iface=pk.iface)
        if "pace" not in skip:
            e["pace"] = RV.pace(ks, pk, wt, wtau)
        if "e1" not in skip:
            e["front_crest"] = front_and_crest(ks, pk, wt, wtau)
        if "rise" not in skip:
            rise[tag] = RV.rise_curve(ks, pk)
        if "curl" not in skip:
            e["curl"] = RV.curl_c1_checks(ks, pk, spec, wt, wtau)
        if "e2" not in skip:
            e["curl_share_checker"] = curl_share(ks, pk, wt, wtau)
        if "m2" not in skip:
            e["no_rebound"] = RV.no_rebound(ks, pk, wt, wtau)
            if wi["stop_len_s"] > 0.5 + 1e-6:
                # 止めが 0.5 s より長い時間曲線（E4）：画面の読みの窓を、実際の止めの始まりの前までにした読みも記録する
                # （D の読みは止めの区間を最大 0.5 s しか除かないので、止めで唇の落下が遅くなる分を「上向きの加速度」に数える）
                orig = RV.stop_end
                RV.stop_end = lambda wt_, wtau_: float(wi["stop_start_t"])
                try:
                    e["no_rebound_before_stop"] = RV.no_rebound(ks, pk, wt, wtau)
                finally:
                    RV.stop_end = orig
        if "trough" not in skip:
            e["trough"] = RV.trough(ks, pk)
        if "spatial" not in skip:
            e["spatial"] = RV.spatial(ks, pk)
        if "theta" not in skip:
            e["crest_angle"] = RV.crest_angle(ks, pk)
        if "j7" not in skip:
            e["tip_screen_accel_last1s"] = tip_screen_accel(ks, pk, wt, wtau)
        if "j5" not in skip:
            # 窓は独立の検査器と同じ t 7.0〜11.55 s。止めの区間を除いた窓（t 7.0〜止めの始まり − 0.05 s）も記録
            t_pre = min(11.55, wi["stop_start_t"] - 0.05)
            e["j5"] = dict(fine=j5(ks, pk, wt, wtau, 11.55), fine_before_stop=j5(ks, pk, wt, wtau, t_pre))
            if pk.fine:
                del pk
                ks, pk, wt, wtau = open_pkg(spec, fine=False)
                e["j5"]["hi_only"] = j5(ks, pk, wt, wtau, 11.55)
            else:
                e["j5"]["hi_only"] = e["j5"]["fine"]
        e["seconds"] = round(time.time() - t0, 1)
        res[tag] = e
        print("done", tag, e["seconds"], flush=True)
        del pk
    for ref in ("C1", "D"):
        if ref in rise:
            for tag in rise:
                if tag == ref:
                    continue
                taus, Hs = rise[tag]
                tc, Hc = rise[ref]
                res[tag]["rise_vs_%s" % ref] = {r: dict(max_abs_dH_m=r3(np.max(np.abs(Hs[r] - Hc[r]))), max_abs_dH_over_Hf=r3(np.max(np.abs(Hs[r] - Hc[r])) / Hc[r][-1], 4))
                                               for r in Hs}
    os.makedirs(os.path.dirname(absrepo(a.out)), exist_ok=True)
    try:
        RV.draw_fig(res, os.path.join(os.path.dirname(absrepo(a.out)), "fig_" + os.path.splitext(os.path.basename(a.out))[0] + ".png"))
    except Exception as ex:
        print("fig error", repr(ex))
    for tag in res:
        for r in (res[tag].get("pace") or {}):
            res[tag]["pace"][r].pop("_series", None)
    res["_definitions_ja"] = __doc__
    out = absrepo(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=lambda o: r3(o) if isinstance(o, (np.floating, float)) else (int(o) if isinstance(o, np.integer) else str(o)))
    print(out)


if __name__ == "__main__":
    main()
