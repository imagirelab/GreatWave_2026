# -*- coding: utf-8 -*-
"""仕上げ28 の原画視点の後退の回復（rec）の生成器：第2回の生成器（r2_build.Build）と同じ設計（r2_design.json）を、同じ土台 P28R1 から、
次の 2 つを足して作り直す。py -3.10 rec_build.py <out_prefix> <design.json> [rec_design.json]

なぜ（評審の must_fix の 1・2、rec_diag・rec_score の診断）：
  P28R2 の管を前へ出す段（T）は、原画の空を通る射線の禁止域だけを見ていた。原画視点の左下では、主役波の管の内壁（行 c −16〜−5、
  列 285〜305 のまわり）が船（157 boat_left）と手前の海の前へ 4 m ほど出て、左の船を半分隠し（段階9 の Unity の ID 画像で船の画素
  46,803 → 22,429）、管の角（行 129〜142、列 307〜356）の輪郭が原画視点の面の中に縦の線を描いた（設計38 の線の印は R4 に合わせたまま）。
  b区域の 3 つの房の段（L）も、肩の稜の輪郭を印のない頂点へ動かし、泡の中に短い線を 3 つ出した（行 74〜79・90〜94・104〜110）。
足すもの：
  P 船と手前の海の射線の禁止域（protect）：段階9 の Unity の t* の ID 画像で船（boat_left・boat_mid・boat_fg）と CPU のメッシュ
    （手前の海）が見える画素を通る射線のうち、カメラから R4 の面（段階9 の主役波。そこでは船・海の後ろ）の手前 margin_m までの区間を、
    行ごとの禁止域にする（空の射線の禁止域と同じ作り、r2_common.keepout_grids）。管を前へ出す段（T）と変位のならし（D）は、
    空の禁止域に加えてこの禁止域にも新しくかからない量だけ動かす（行ごとの二分探索と、c 方向のなめらかな下限は r2 と同じ）。
  G 線の見張り（line_guard）：最後に、設計38 の反転シェルの線を numpy で描き（rec_common.shell_lines、Unity の t* の線の ID 画像で
    新しい線の塊の画素数が一致することを確かめた）、土台 P28R1 に対して新しく出た線の塊（ss=1 で min_px 画素以上）ごとに、
    その線を描いた四角形の行・列のまわりの窓（端はなめらか）で、土台からの変位を割合 f ずつ土台へ戻す（くり返し）。
    土台 P28R1 にすでにある線（第1回の頂・唇先の読み直しによるもの。設計38 の印の作り直しで消える種類）は扱わない。
原画の輪郭を作る点（78・130・131・132・72）は、r2 と同じく動かさない（どの段も土台からの変位を減らす向きにだけ働く）。
格子 400×240、目印の列、UV、行の c は変えない。参照モデルは読まない（F13-1）。
"""
import os
import sys
import json
import time
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_common as R  # noqa: E402
import r2_build as B2  # noqa: E402
import rec_common as RC  # noqa: E402

KC = R.KC

REC_DEFAULT = {
    "protect": {"margin_m": 0.25, "step_px": 2, "classes": ["boat_left", "boat_mid", "boat_fg", "cpu"]},
    "shell_guard": {"target_over_H": 0.22, "c": [-20.0, 4.0], "H_min_over_H0": 0.5, "sigma_c_m": 0.8},
    "line_guard": {"ss": 1, "min_px": 20, "frac": 0.5, "iters": 8, "pad_rows": 3, "pad_cols": 8, "fade_rows": 3.0, "fade_cols": 6.0},
}


def protect_grids(c, cfg, cache=None):
    """段階9 の船・手前の海の画素の射線の、R4 の面の手前 margin_m までの区間の行ごとの禁止域（NY×NA、r2_common と同じ格子）。"""
    import cv2
    key = json.dumps(cfg, sort_keys=True)
    if cache and os.path.isfile(cache):
        z = np.load(cache)
        if np.allclose(z["c"], c) and str(z["key"]) == key:
            return np.unpackbits(z["G"], axis=-1)[..., :R.NA].astype(bool), json.loads(str(z["info"]))
    S9 = RC.stage9_classes(1)
    prot = np.zeros_like(S9["cpu"])
    for k in cfg["classes"]:
        prot |= S9[k]
    st = int(cfg["step_px"])
    ys, xs = np.nonzero(prot[::st, ::st]); xs = xs * st; ys = ys * st
    # R4 の面の奥行き（段階9 の主役波）
    c4, A4, Y4 = RC.load_rows(RC.ROWS["R4"])
    z4, _ = RC.zbuf(c4, A4, Y4, 1)
    zr = z4[ys, xs]
    pos, r, u, f = KC.cam_basis_unity()
    t = math.tan(math.radians(KC.CAM_VFOV) / 2.0); asp = KC.CAM_W / float(KC.CAM_H)
    vx = (xs + 0.5) / KC.CAM_W; vy = 1.0 - (ys + 0.5) / KC.CAM_H
    D = ((2 * vx - 1) * t * asp)[:, None] * r + ((2 * vy - 1) * t)[:, None] * u + f[None, :]
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    df = D @ f
    t_r4 = np.where(np.isfinite(zr), zr / np.maximum(df, 1e-6), np.inf)
    t_sea = np.where(D[:, 1] < -1e-6, (0.0 - pos[1]) / np.minimum(D[:, 1], -1e-6), np.inf)
    tcap = np.minimum(t_r4 - float(cfg["margin_m"]), t_sea)
    s0 = KC.sec(pos[None])[0]
    dE = D @ KC.E; dT = D @ KC.T; dY = D[:, 1]
    G = np.zeros((len(c), R.NY, R.NA), bool)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    for i, cc in enumerate(c):
        ok = np.abs(dE) > 1e-6
        tt = np.full(len(D), -1.0); tt[ok] = (cc - s0[2]) / dE[ok]
        m = (tt > 0) & (tt < tcap)
        a = s0[0] + tt[m] * dT[m]; y = s0[1] + tt[m] * dY[m]
        ia = np.round((a - R.GA0) / R.GRES).astype(int); iy = np.round((y - R.GY0) / R.GRES).astype(int)
        mm = (ia >= 0) & (ia < R.NA) & (iy >= 0) & (iy < R.NY)
        g = np.zeros((R.NY, R.NA), np.uint8); g[iy[mm], ia[mm]] = 1
        G[i] = cv2.dilate(g, k).astype(bool)
    info = {"rays": int(len(D)), "rays_with_r4_behind": int(np.isfinite(t_r4).sum()), "rows_with_cells": int(G.any((1, 2)).sum()),
            "cells_total": int(G.sum())}
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez_compressed(cache, c=c, key=key, G=np.packbits(G, axis=-1), info=json.dumps(info))
    return G, info


class RecBuild(B2.Build):
    def __init__(self, design=None, rec=None, base=None):
        super().__init__(design, base)
        self.rec = json.loads(json.dumps(REC_DEFAULT))
        if rec:
            for k, v in rec.items():
                if isinstance(v, dict) and isinstance(self.rec.get(k), dict):
                    self.rec[k].update(v)
                else:
                    self.rec[k] = v
        self.Gp = None
        if self.rec.get("protect"):
            self.Gp, self.protect_info = protect_grids(self.c, self.rec["protect"], cache=os.path.join(RC.OUT, "cache", "protect_grids.npz"))
            self.base_fill_p = [R.section_fill(self.A0[i], self.Y0[i]) & self.Gp[i] for i in range(self.nv)]

    def new_spill_p(self, i, a, y):
        if self.Gp is None:
            return 0
        f = R.section_fill(a, y) & self.Gp[i]
        return int((f & ~self.base_fill_p[i]).sum())

    # ------------------------------------------------------------ T（r2 と同じ。禁止域の確かめに船・手前の海の禁止域を足した）
    def tube(self, A, Y):
        d = self.d
        c = self.c
        ph = B2.phi_cols(self.nu, d["tube_cols"])
        c0, c1 = d["tube_c"]
        wr = R.ss((c - c0) / 2.0) * R.ss((c1 - c) / d["tube_fade_m"])
        jt = Y.argmax(1)
        atop = A[np.arange(self.nv), jt]
        dtar = np.maximum(0.0, atop + d["tube_a_off"] - A[:, 314])
        dok = np.zeros(self.nv)
        lim = {}
        for i in np.nonzero(wr > 1e-3)[0]:
            if Y[i].max() < 1.0 or dtar[i] <= 0.05:
                continue
            lo, hi = 0.0, dtar[i]
            sp_ref = self.new_spill(i, A[i], Y[i])
            pp_ref = self.new_spill_p(i, A[i], Y[i])
            for _ in range(10):
                mid = 0.5 * (lo + hi)
                a2 = A[i] + mid * ph
                ok = (self.new_spill(i, a2, Y[i]) <= sp_ref and self.new_spill_p(i, a2, Y[i]) <= pp_ref
                      and B2.seg_selfx(a2, Y[i], 150, 395) == 0)
                if ok:
                    lo = mid
                else:
                    hi = mid
            dok[i] = lo
            # 何が止めたか（記録）：空の禁止域だけなら動けた量
            lo2, hi2 = 0.0, dtar[i]
            for _ in range(8):
                mid = 0.5 * (lo2 + hi2)
                a2 = A[i] + mid * ph
                if self.new_spill(i, a2, Y[i]) <= sp_ref and B2.seg_selfx(a2, Y[i], 150, 395) == 0:
                    lo2 = mid
                else:
                    hi2 = mid
            lim[i] = (lo, lo2)
        ds = dok.copy()
        for _ in range(4):
            ds = np.minimum(R.csmooth(c, ds, d["tube_sigma_m"]), dok)
        ds = R.csmooth(c, ds, 0.6)
        ds = np.minimum(ds, dok)
        ds *= wr
        A = A + ds[:, None] * ph[None, :]
        self.tube_shift = ds
        self.tube_limit = lim
        self.log.append({"tube_shift_m": {"%.1f" % c[i]: round(float(ds[i]), 2) for i in range(0, self.nv, 6) if ds[i] > 0.01},
                         "tube_target_max": round(float(dtar[wr > 0.5].max()), 2),
                         "tube_ok_protect_vs_sky_only_m": {"%.1f" % c[i]: [round(float(v[0]), 2), round(float(v[1]), 2)]
                                                           for i, v in sorted(lim.items())[::4]}})
        return A, Y

    # ------------------------------------------------------------ D（r2 と同じ。戻す条件に船・手前の海の禁止域を足した）
    def disp_smooth(self, A, Y):
        g = self.d["disp_smooth"]
        c = self.c
        sc = float(g.get("sigma_c_m", 0.5))
        dA = A - self.A0; dY = Y - self.Y0
        sA = R.csmooth(c, dA, sc); sY = R.csmooth(c, dY, sc)
        mag = np.hypot(dA, dY)
        keep0 = mag < 1e-9
        A2 = self.A0 + np.where(keep0, 0.0, sA); Y2 = self.Y0 + np.where(keep0, 0.0, sY)
        back = 0
        for i in range(self.nv):
            if np.array_equal(A2[i], A[i]) and np.array_equal(Y2[i], Y[i]):
                continue
            if (self.new_spill(i, A2[i], Y2[i]) > self.new_spill(i, A[i], Y[i])
                    or self.new_spill_p(i, A2[i], Y2[i]) > self.new_spill_p(i, A[i], Y[i])
                    or (B2.seg_selfx(A2[i], Y2[i], 0, None) > 0 and B2.seg_selfx(A[i], Y[i], 0, None) == 0)):
                A2[i], Y2[i] = A[i], Y[i]; back += 1
        self.log.append({"disp_smooth_rows_reverted": back})
        return A2, Y2

    # ------------------------------------------------------------ L の端（b区域の房の段の c 方向の端を、なめらかに 0 へ）
    def b_lobes(self, A, Y):
        """第2回の b区域の房の段（r2_build.Build.b_lobes）をそのまま回し、その変位（高さ）を、変位のある行の両端で fade_m かけて 0 へ落とし、
        c 方向に σ sigma_c_m でならす（rec_design の b_lobes_edge）。房の段は行 c −18.5〜−3.5 m の内だけを動かすので、端の行（c −18.4 m）で
        隣の行と 60° を超える折れ（列 170〜174）ができ、原画視点の泡の中の線を太くした（rec/try の P4）。"""
        A1, Y1 = super().b_lobes(A, Y)
        g = self.rec.get("b_lobes_edge")
        if not g:
            return A1, Y1
        c = self.c
        d = Y1 - Y
        moved = np.nonzero(np.abs(d).max(1) > 1e-6)[0]
        if not len(moved):
            return A1, Y1
        lo, hi = float(c[moved].min()), float(c[moved].max())
        fade = float(g.get("fade_m", 1.0))
        w = R.ss((c - lo) / fade) * R.ss((hi - c) / fade)
        d2 = R.csmooth(c, d, float(g.get("sigma_c_m", 0.3))) * w[:, None]
        Y2 = Y + d2
        back = 0
        for i in np.nonzero(np.abs(d2).max(1) > 1e-6)[0]:
            if B2.seg_selfx(A1[i], Y2[i], 0, None) > 0 and B2.seg_selfx(A1[i], Y1[i], 0, None) == 0:
                Y2[i] = Y1[i]; back += 1
        self.log.append({"b_lobes_edge": {"rows_c": [lo, hi], "fade_m": fade, "sigma_c_m": float(g.get("sigma_c_m", 0.3)), "rows_reverted": back,
                                          "max_change_vs_r2_m": round(float(np.abs(Y2 - Y1).max()), 3)}})
        return A1, Y2

    # ------------------------------------------------------------ S（殻の見張り）
    def shell_guard(self, A, Y):
        """背の殻の厚み（評価基準 F03 と同じ読み：rubric_measure.back_shape の背の法線の厚みの中央値 / H）が、行ごとに
        min(target, 土台 P28R1 の値) を割る行だけ、背の列（0..JK）を土台へ割合 f で戻す（f は二分探索、c 方向になめらかな上の包絡）。
        管を前へ出せない行（船・手前の海の禁止域）では、第2回の背（θ_b 52°）が管の内壁に近づき、殻が 0.16 H まで薄くなる
        （Q21「又太单薄了」、評価基準 F03 の必須 ≥ 0.20）。"""
        sys.path.insert(0, os.path.join(R.REPO, "Tools", "GWWaveGen", "rubric"))
        import rubric_measure as RM
        g = self.rec["shell_guard"]
        c = self.c
        JK = int(self.d["JK"])
        H = Y.max(1); H0 = float(H[int(np.argmin(np.abs(c)))])

        def shell(a, y):
            try:
                segs = RM.poly_to_segs(a, y); m = RM.section_metrics(segs, 0.0, H0, open_w=0.0)
                b = RM.back_shape(segs, 0.0, m["H"], m["a_top"])
                v = b.get("shell_thick_normal_over_H")
                return float(v[1]) if v else np.nan
            except Exception:
                return np.nan
        rows = np.nonzero((c >= g["c"][0]) & (c <= g["c"][1]) & (H >= g["H_min_over_H0"] * H0))[0]
        f = np.zeros(self.nv); rec = {}
        for i in rows:
            s_now = shell(A[i], Y[i]); s_base = shell(self.A0[i], self.Y0[i])
            tgt = min(float(g["target_over_H"]), s_base) if np.isfinite(s_base) else float(g["target_over_H"])
            if not np.isfinite(s_now) or s_now >= tgt:
                continue
            lo, hi = 0.0, 1.0
            for _ in range(8):
                mid = 0.5 * (lo + hi)
                a1 = A[i].copy(); y1 = Y[i].copy()
                a1[:JK + 1] = (1 - mid) * A[i, :JK + 1] + mid * self.A0[i, :JK + 1]
                y1[:JK + 1] = (1 - mid) * Y[i, :JK + 1] + mid * self.Y0[i, :JK + 1]
                sv = shell(a1, y1)
                if np.isfinite(sv) and sv >= tgt:
                    hi = mid
                else:
                    lo = mid
            f[i] = hi
            rec["%.1f" % c[i]] = [round(s_now, 3), round(tgt, 3), round(hi, 2)]
        if f.any():
            fs = np.maximum(R.csmooth(c, f, float(g["sigma_c_m"])), f)
            fs = np.maximum(R.csmooth(c, fs, float(g["sigma_c_m"])), f)
            A = A.copy(); Y = Y.copy()
            for i in np.nonzero(fs > 1e-3)[0]:
                a1 = A[i].copy(); y1 = Y[i].copy()
                a1[:JK + 1] = (1 - fs[i]) * A[i, :JK + 1] + fs[i] * self.A0[i, :JK + 1]
                y1[:JK + 1] = (1 - fs[i]) * Y[i, :JK + 1] + fs[i] * self.Y0[i, :JK + 1]
                if B2.seg_selfx(a1, y1, 0, None) == 0 or B2.seg_selfx(A[i], Y[i], 0, None) > 0:
                    A[i], Y[i] = a1, y1
            self.shell_f = fs
        self.log.append({"shell_guard_now_target_f": rec, "shell_guard_rows": int((f > 0).sum())})
        return A, Y

    # ------------------------------------------------------------ G（線の見張り）
    def line_guard(self, A, Y):
        import cv2
        g = self.rec["line_guard"]
        ss = int(g["ss"])
        mask = RC.load_linemask()
        c = self.c
        base_ln, _, _ = RC.shell_lines(c, self.A0, self.Y0, mask, ss=ss)
        kd = np.ones((2 * ss + 1, 2 * ss + 1), np.uint8)
        base_d = cv2.dilate(base_ln.astype(np.uint8), kd).astype(bool)
        rr = np.arange(self.nv, dtype=float); jj = np.arange(self.nu, dtype=float)
        hist = []
        Wacc = np.zeros((self.nv, self.nu))
        for it in range(int(g["iters"])):
            ln, _, _, src = RC.shell_lines(c, A, Y, mask, ss=ss, want_src=True)
            new = ln & ~base_d
            n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(new.astype(np.uint8), np.ones((5 * ss, 5 * ss), np.uint8)), connectivity=8)
            blobs = []
            for k in range(1, n):
                m = (lab == k) & new
                if m.sum() < int(g["min_px"]) * ss * ss:
                    continue
                q = src[m]; q = q[q >= 0]
                if not len(q):
                    continue
                r_ = q // (self.nu - 1); j_ = q % (self.nu - 1)
                ys, xs = np.nonzero(m)
                blobs.append({"px": int(m.sum()), "x": [int(xs.min() / ss), int(xs.max() / ss)], "y": [int(ys.min() / ss), int(ys.max() / ss)],
                              "rows": [int(r_.min()), int(r_.max())], "cols": [int(j_.min()), int(j_.max())]})
            hist.append({"iter": it, "new_px": int(new.sum()), "blobs": blobs})
            if not blobs:
                break
            W = np.zeros((self.nv, self.nu))
            for b in blobs:
                r0, r1 = b["rows"][0] - g["pad_rows"], b["rows"][1] + 1 + g["pad_rows"]
                j0, j1 = b["cols"][0] - g["pad_cols"], b["cols"][1] + 1 + g["pad_cols"]
                wr_ = R.ss((rr - (r0 - g["fade_rows"])) / g["fade_rows"]) * R.ss(((r1 + g["fade_rows"]) - rr) / g["fade_rows"])
                wj_ = R.ss((jj - (j0 - g["fade_cols"])) / g["fade_cols"]) * R.ss(((j1 + g["fade_cols"]) - jj) / g["fade_cols"])
                W = np.maximum(W, wr_[:, None] * wj_[None, :])
            f = float(g["frac"])
            A1 = A - f * W * (A - self.A0); Y1 = Y - f * W * (Y - self.Y0)
            for i in np.nonzero(W.max(1) > 1e-3)[0]:
                if B2.seg_selfx(A1[i], Y1[i], 0, None) > 0 and B2.seg_selfx(A[i], Y[i], 0, None) == 0:
                    A1[i], Y1[i] = A[i], Y[i]
            A, Y = A1, Y1
            Wacc = 1 - (1 - Wacc) * (1 - f * W)
        self.guard_weight = Wacc
        self.log.append({"line_guard": hist, "line_guard_back_to_base_max": round(float(Wacc.max()), 3),
                         "line_guard_rows_touched": [int(x) for x in np.nonzero(Wacc.max(1) > 0.01)[0][[0, -1]]] if (Wacc > 0.01).any() else []})
        return A, Y

    def run(self):
        A, Y = super().run()
        if self.rec.get("shell_guard"):
            A, Y = self.shell_guard(A, Y)
            self.A, self.Y = A, Y
        if self.rec.get("line_guard"):
            A, Y = self.line_guard(A, Y)
            self.A, self.Y = A, Y
        sp = np.array([self.new_spill(i, A[i], Y[i]) for i in range(self.nv)])
        pp = np.array([self.new_spill_p(i, A[i], Y[i]) for i in range(self.nv)])
        self.log.append({"final_new_spill_cells_sky": int(sp.sum()), "final_new_spill_cells_protect": int(pp.sum()),
                         "final_protect_rows": {"%.1f" % self.c[i]: int(pp[i]) for i in np.nonzero(pp)[0]}})
        return A, Y


def main():
    pre = sys.argv[1]
    design = json.load(open(sys.argv[2], encoding="utf-8"))
    rec = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
    t0 = time.time()
    b = RecBuild(design, rec)
    A, Y = b.run()
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    prov = {"route": "仕上げ28 の原画視点の後退の回復（rec）Tools/GWWaveGen/kstar_p28/rec_build.py（r2_build.Build を継ぐ）",
            "base": "P28R1 (r1_rays/cand/kstarP28R1_a45_rows.npz)", "design": b.d, "rec": b.rec,
            "reference_model_read_by_generator": False}
    KC.write_candidate(pre, b.c, A, Y, prov)
    rep = {"design": b.d, "rec": b.rec, "protect_info": getattr(b, "protect_info", None), "log": b.log, "seconds": round(time.time() - t0, 1)}
    R.jdump(rep, pre + "_build_report.json")
    np.savez_compressed(pre + "_build_aux.npz", tube_shift=getattr(b, "tube_shift", np.zeros(b.nv)),
                        guard_weight=getattr(b, "guard_weight", np.zeros((b.nv, b.nu))), **b.L)
    print(json.dumps(b.log[-3:], ensure_ascii=False)[:6000])
    print("seconds", round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
