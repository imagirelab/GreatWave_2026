# -*- coding: utf-8 -*-
"""設計29：表示用サーフェスの点検（密度ごと）。

測るもの（1 つの網 = 1 回の実行。--display に Unity/Build/Design/29/<名前>、または src（設計28 の既定のパッケージそのもの、比べる基準））：
  P13      設計27 の関門 ds27_gates.py の P13（30 Hz、物理の時刻）と同じ項目・しきい値・測り方を、行・列の数によらない形に写したもの。
           基準の形（「K* に対する比」の K*）は、その網の t* の形（表示の網では K* の面の上の点）。範囲は巻きの行（源の行 60〜192）の
           唇〜管の天井（表示では頂の目印の列から内壁の錨の目印の列の手前まで。src では ds27_gates の KStar の範囲そのもの）。
           (4) の頂の高さは 30 Hz（関門は 60 Hz）。
  薄膜     t* と形成の τ（ds29_params.json の measure.film_taus）で、巻きの行ごとの断面の唇の上面の、唇先から弧長 d の点から、
           唇先より先の折れ線（下面・管の天井）への最短の距離（唇先の厚み）。
  波頭の欠落 行ごとの頂の高さ（y の最大）と唇の前への届き（巻きの行の a の最大）を、源の面の同じ c の曲線（区分線形の面の c 一定の
           切り口を正確に標本化）と比べた差（源 − 網、30 Hz の全コマ）。網は正確な表示の網（量子化・Hermite なし）と、パッケージの
           再生（Hermite）の両方。
  面の差   表示の網の辺の 1/4・1/2・3/4 の点（網の弦）と、同じ媒介変数の源の面の点の差（10 Hz と t*）。距離と、源の面の法線の向きの成分。
           t* は K*（26修正01）の面との差。
  Hermite  パッケージの再生と正確な表示の網（生成器の値を網に写したもの）の差：30 Hz の全コマ、全区間の中点、節点の間隔が変わる所
           （隣の区間との間隔の比 ≥ 1.5）の区間の内側の 8 点。
  GPU      位置のバッファ（層 × 頂点 × 6 バイト、設計27 の再生器の詰め方）、T_white、網（頂点・添字）の見積もり。
使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/ds29/ds29_measure.py --display full_240x400 [--out Unity/Build/Design/29/measure]
    py -3.10 -B Tools/GWWaveGen/ds29/ds29_measure.py --display src
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds29_surface as S  # noqa: E402
import ds27_gates as GT  # noqa: E402

REPO = S.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "29", "measure")
TH = GT.TH
G = 9.81
HZ = 30


def fnum(x, nd=6):
    return GT.fnum(x, nd)


def drawdown(x):
    return GT.drawdown(x)


# ---------------------------------------------------------------- 網の定義（範囲・基準）
class Net:
    """網の形と P13 の範囲。src は設計28 のパッケージと ds27_gates の KStar の範囲。"""

    def __init__(self, name, src):
        self.name = name
        self.src = src
        K = src.K
        if name == "src":
            self.dir = src.pkg_dir
            ks = GT.KStar()
            self.ks = ks
            self.nv, self.nu = ks.nv, ks.nu
            self.rho = np.arange(self.nv, dtype=np.float64)
            self.kappa0 = np.broadcast_to(np.arange(self.nu, dtype=np.float64)[None, :], (self.nv, self.nu)).copy()
            self.disp = None
            self.lipcol = ks.lipcol
            self.curled = ks.is_curled.copy()
            self.seam = list(ks.seam)
            self.crest_hi = ks.crest_hi.copy()
            self.J0, self.J1 = ks.J0, ks.J1
            self.main_row, self.peak_row = ks.main_row, ks.peak_row
            self.tip_rows = [(q["r"], q["jt"], q["rim"], q["ja"]) for q in ks.curled]
            self.Xref = ks.X.copy()
        else:
            self.dir = name if os.path.isdir(name) else os.path.join(REPO, "Unity", "Build", "Design", "29", name)
            self.name = os.path.basename(self.dir.rstrip("/\\"))
            M = np.load(os.path.join(self.dir, "ds29_map.npz"))
            J = json.load(open(os.path.join(self.dir, "ds27_keypose.json"), encoding="utf-8"))
            ds = J["display_surface"]
            modes = {nm: str(v) for nm, v in zip(S.SEGMENTS, M["modes"])}
            d = S.Display(src, int(J["rows"]), int(J["cols"]), name=self.name, modes=modes)
            if not (np.allclose(d.kappa0, M["kappa0"], atol=1e-12, rtol=0) and np.array_equal(d.k_seg, M["k_seg"])):
                raise SystemExit("[ds29_measure] 網の媒介変数が ds29_map.npz と違います（コードが変わった？）")
            self.disp = d
            self.nv, self.nu = d.nv, d.nu
            self.rho, self.kappa0 = d.rho, d.kappa0
            reg = d.region()
            kr, km, kj = reg["k_root"], reg["k_rim"], reg["k_ja"]
            self.curled = reg["curled"]
            lip = np.zeros((self.nv, self.nu), bool)
            lip[self.curled, kr:kj] = True
            self.lipcol = lip
            self.seam = [(int(i), km) for i in np.nonzero(self.curled)[0]]
            self.crest_hi = np.where(self.curled, kr, self.nu - 1)
            self.J0, self.J1 = max(kr - 3, 0), min(kj + 2, self.nu - 1)
            self.main_row, self.peak_row = reg["main_row"], reg["peak_row"]
            self.tip_rows = [(int(i), kr, km, kj) for i in np.nonzero(self.curled)[0]]
            self.Xref = d.eval(K.X, 0.0)
            self.ds = ds
        self.pk = GT.Package(self.dir, SimpleNamespace(nv=self.nv, nu=self.nu))
        self.q_max = self.pk.q_max
        nv, nu = self.nv, self.nu
        # P13 の範囲（ds27_gates.KStar._mesh_region と同じ組み立て）
        self.row_edge_mask = self.lipcol[:, :-1] | self.lipcol[:, 1:]
        pair = self.curled[:-1] & self.curled[1:]
        tch = (self.lipcol[:-1] | self.lipcol[1:]) & pair[:, None]
        self.tri_mask = tch[:, :-1] | tch[:, 1:]
        tany = self.lipcol[:-1] | self.lipcol[1:]
        self.ring_mask = tany[:, :-1] | tany[:, 1:]
        self.vedge_mask = tch
        self.dedge_mask = self.tri_mask
        Kx = self.Xref
        self.Lrow_K = np.linalg.norm(np.diff(Kx, axis=1), axis=-1)
        self.Lv_K = np.linalg.norm(Kx[1:] - Kx[:-1], axis=-1)
        self.Ld_K = np.linalg.norm(Kx[1:, :-1] - Kx[:-1, 1:], axis=-1)
        nrm = GT.tri_normals(Kx)
        self.tri_area_K = 0.5 * np.linalg.norm(nrm, axis=-1)
        P00, P10, P01, P11 = Kx[:-1, :-1], Kx[1:, :-1], Kx[:-1, 1:], Kx[1:, 1:]
        e1 = np.maximum.reduce([np.linalg.norm(P10 - P00, axis=-1), np.linalg.norm(P01 - P10, axis=-1), np.linalg.norm(P00 - P01, axis=-1)])
        e2 = np.maximum.reduce([np.linalg.norm(P10 - P01, axis=-1), np.linalg.norm(P11 - P10, axis=-1), np.linalg.norm(P01 - P11, axis=-1)])
        alt = 2 * self.tri_area_K / np.maximum(np.stack([e1, e2], 2), 1e-15)
        self.tri_resolvable = alt >= 0.005
        self.rows_k = np.nonzero(self.curled)[0]

    def exact_local(self, X_src, tau):
        """正確な表示の網（局所）と時刻の κ。"""
        if self.disp is None:
            return X_src, self.kappa0
        return self.disp.eval(X_src, tau, return_kappa=True)


# ---------------------------------------------------------------- P13（ds27_gates.measure の 30 Hz の部分を写したもの）
class P13:
    def __init__(self, net):
        self.n = net
        self.step30 = dict(max=0.0, at=None)
        self.acc30 = dict(max=0.0, at=None)
        self.flips = dict(n_resolvable=0, n_region=0, n_all=0, at=None, at_region=None)
        self.tri_min_region = (np.inf, None)
        self.tri_min_all = (np.inf, None)
        self.edge_min = (np.inf, None)
        self.edge_margin = (np.inf, None)
        self.st_row = [np.inf, 0.0]
        self.st_x = [np.inf, 0.0]
        self.seam = [np.inf, 0.0]
        self.prev_loc = None
        self.prev_g = []
        self.ref_n = None
        self.ref_ok = None
        self.vt = GT.ViolTracker()
        self.si = dict(frames=0, row_hits=0, mid_hits=0, resolvable_hits=0, tau_range=None, examples=[])
        self.ymin = (np.inf, None)
        self.H = []
        self.zero_all_tstar = 0
        self.thr_e = np.minimum(TH["P13_row_edge_m"], net.Lrow_K - 2 * net.q_max)
        self.n_relaxed = int((net.row_edge_mask & (self.thr_e < TH["P13_row_edge_m"])).sum())

    def add(self, tau, X, loc, do_si, last=False):
        n = self.n
        K = n.src.K
        if self.prev_loc is not None:
            d = np.linalg.norm(loc - self.prev_loc, axis=-1)
            i = np.unravel_index(int(d.argmax()), d.shape)
            if d[i] > self.step30["max"]:
                self.step30 = dict(max=float(d[i]), at=dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4)))
        self.prev_loc = loc
        Xg = X[n.rows_k]
        self.prev_g.append(Xg)
        if len(self.prev_g) == 3:
            d2 = np.linalg.norm(self.prev_g[2] - 2 * self.prev_g[1] + self.prev_g[0], axis=-1)
            i = np.unravel_index(int(d2.argmax()), d2.shape)
            if d2[i] > self.acc30["max"]:
                self.acc30 = dict(max=float(d2[i]), at=dict(row=int(n.rows_k[i[0]]), col=int(i[1]), tau=round(float(tau) - 1.0 / HZ, 4)))
            self.prev_g.pop(0)
        y = X[..., 1]
        if float(y.min()) < self.ymin[0]:
            self.ymin = (float(y.min()), round(float(tau), 4))
        cols = np.arange(n.nu)
        Hrow = np.where(cols[None, :] <= n.crest_hi[:, None], y, -np.inf).max(1)
        self.H.append(Hrow)
        nrm = GT.tri_normals(X)
        nl = np.linalg.norm(nrm, axis=-1)
        ar = 0.5 * nl
        if last:
            self.zero_all_tstar = int((ar < 1e-10).sum())
        region3 = np.broadcast_to(n.tri_mask[..., None], ar.shape)
        arr = np.where(region3, ar, np.inf)
        i = np.unravel_index(int(arr.argmin()), arr.shape)
        if arr[i] < self.tri_min_region[0]:
            self.tri_min_region = (float(arr[i]), dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4)))
        ar6 = np.where(np.broadcast_to(n.ring_mask[..., None], ar.shape), ar, np.inf)
        i = np.unravel_index(int(ar6.argmin()), ar6.shape)
        if ar6[i] < self.tri_min_all[0]:
            self.tri_min_all = (float(ar6[i]), dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4)))
        un_ = nrm / np.maximum(nl[..., None], 1e-15)
        valid = ar > 1e-10
        if self.ref_n is not None:
            dots = (un_ * self.ref_n).sum(-1)
            bad = valid & self.ref_ok & (dots <= 0)
            if bad.any():
                br = bad & n.tri_resolvable
                bg = bad & region3
                self.vt.add("5g", int((br | bg).sum()), tau)
                self.flips["n_all"] += int(bad.sum())
                self.flips["n_resolvable"] += int(br.sum())
                self.flips["n_region"] += int(bg.sum())
                if self.flips["at"] is None and br.any():
                    i = np.unravel_index(int(np.argmax(br)), br.shape)
                    self.flips["at"] = dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4))
                if self.flips["at_region"] is None and bg.any():
                    i = np.unravel_index(int(np.argmax(bg)), bg.shape)
                    self.flips["at_region"] = dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4))
            self.ref_n = np.where(valid[..., None], un_, self.ref_n)
            self.ref_ok = self.ref_ok | valid
        else:
            self.ref_n = un_.copy()
            self.ref_ok = valid.copy()
        Lr = np.linalg.norm(np.diff(X, axis=1), axis=-1)
        v = np.where(n.row_edge_mask, Lr, np.inf)
        i = np.unravel_index(int(v.argmin()), v.shape)
        if v[i] < self.edge_min[0]:
            self.edge_min = (float(v[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4), K_len_m=round(float(n.Lrow_K[i]), 5)))
        mg = np.where(n.row_edge_mask, Lr - self.thr_e, np.inf)
        i = np.unravel_index(int(mg.argmin()), mg.shape)
        self.vt.add("5b", int((mg < 0).sum()), tau)
        if mg[i] < self.edge_margin[0]:
            self.edge_margin = (float(mg[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4), len_m=round(float(Lr[i]), 5)))
        self.vt.add("5a", int((arr < TH["P13_tri_area_m2"]).sum()), tau)
        self.vt.add("6", int((ar6 <= 1e-10).sum()), tau)
        q2 = 2 * n.q_max

        def ratio_check(L, LK, key, acc):
            raw = L / np.maximum(LK, 1e-9)
            lo_ = (L + q2) / np.maximum(LK, 1e-9)
            hi_ = np.maximum(L - q2, 0) / np.maximum(LK, 1e-9)
            acc[0] = min(acc[0], float(raw.min()))
            acc[1] = max(acc[1], float(raw.max()))
            lo_b, hi_b = (TH["P13_seam_lo"], TH["P13_seam_hi"]) if key == "5e" else (TH["P13_stretch_lo"], TH["P13_stretch_hi"])
            self.vt.add(key, int((lo_ < lo_b).sum() + (hi_ > hi_b).sum()), tau)

        ratio_check(Lr[n.row_edge_mask], n.Lrow_K[n.row_edge_mask], "5c", self.st_row)
        Lv = np.linalg.norm(X[1:] - X[:-1], axis=-1)
        Ld = np.linalg.norm(X[1:, :-1] - X[:-1, 1:], axis=-1)
        ratio_check(np.concatenate([Lv[n.vedge_mask], Ld[n.dedge_mask]]), np.concatenate([n.Lv_K[n.vedge_mask], n.Ld_K[n.dedge_mask]]), "5d", self.st_x)
        sr = np.array([r for r, j in n.seam])
        sj = np.array([j for r, j in n.seam])
        ratio_check(Lr[sr, sj], n.Lrow_K[sr, sj], "5e", self.seam)
        if do_si:
            self.si["frames"] += 1
            D = X - K.O
            A = D @ K.t
            rows_k = n.rows_k
            Pr = np.stack([A[rows_k, n.J0:n.J1 + 1], y[rows_k, n.J0:n.J1 + 1]], -1)
            hits, nres = GT.seg_crossings(Pr)
            if len(hits):
                self.si["row_hits"] += int(len(hits))
                self.si["resolvable_hits"] += nres
                tr = self.si["tau_range"] or [float(tau), float(tau)]
                self.si["tau_range"] = [min(tr[0], float(tau)), max(tr[1], float(tau))]
                if len(self.si["examples"]) < 6:
                    h0 = hits[0]
                    self.si["examples"].append(dict(kind="row", row=int(rows_k[h0[0]]), seg_cols=[int(n.J0 + h0[1]), int(n.J0 + h0[2])], tau=round(float(tau), 4)))
            pr = rows_k[:-1][np.diff(rows_k) == 1]
            j0, j1 = n.J0, n.J1
            Mx = 0.5 * (X[pr, j0:j1 + 1] + X[pr + 1, j0:j1 + 1])
            Dx = 0.5 * (X[pr, j0 + 1:j1 + 1] + X[pr + 1, j0:j1])
            n_ = Mx.shape[1]
            Q = np.empty((len(pr), 2 * n_ - 1, 3))
            Q[:, 0::2] = Mx
            Q[:, 1::2] = Dx
            Pm = np.stack([(Q - K.O) @ K.t, Q[..., 1]], -1)
            hits, nres = GT.seg_crossings(Pm)
            if len(hits):
                self.si["mid_hits"] += int(len(hits))
                self.si["resolvable_hits"] += nres
                tr = self.si["tau_range"] or [float(tau), float(tau)]
                self.si["tau_range"] = [min(tr[0], float(tau)), max(tr[1], float(tau))]
                if len(self.si["examples"]) < 6:
                    self.si["examples"].append(dict(kind="mid", rows=[int(pr[hits[0][0]]), int(pr[hits[0][0]] + 1)], tau=round(float(tau), 4)))

    def result(self, H_star):
        n = self.n
        Hs = np.stack(self.H)
        mono = {"main_row": drawdown(Hs[:, n.main_row]), "peak_row": drawdown(Hs[:, n.peak_row]), "all_rows_max": drawdown(Hs.max(1))}
        mw = max(mono.values())
        lim2 = TH["P13_acc_g"] * G / HZ ** 2
        V_ = self.vt.d
        vinfo = lambda key: dict(violations=V_.get(key, {}).get("n", 0), frames=V_.get(key, {}).get("frames", 0), tau_range=V_.get(key, {}).get("tau_range"))
        vok = lambda key: V_.get(key, {}).get("n", 0) == 0
        it = {}
        it["(1)"] = dict(value=self.step30["max"], threshold="< 0.6", pass_=self.step30["max"] < TH["P13_step_m"], at=self.step30["at"])
        it["(2)"] = dict(value=self.acc30["max"], threshold="≤ %.4f（2g）" % lim2, pass_=self.acc30["max"] <= lim2, at=self.acc30["at"])
        it["(3)"] = dict(value=self.ymin[0], threshold="≥ %.2f" % (TH["P13_ymin_over_Hstar"] * H_star), pass_=self.ymin[0] >= TH["P13_ymin_over_Hstar"] * H_star, at=dict(tau=self.ymin[1]))
        it["(4)"] = dict(value=mw, threshold="≤ 0.05", pass_=mw <= TH["P13_crest_mono_m"], at={k: fnum(v, 4) for k, v in mono.items()})
        it["(5a)"] = dict(value=self.tri_min_region[0], threshold="≥ 1e-4", pass_=vok("5a"), at=dict(at=self.tri_min_region[1], **vinfo("5a")))
        it["(5b)"] = dict(value=self.edge_min[0], threshold="≥ 0.005（基準の網で 5 mm に近い・未満の %d 辺は基準 − 量子化の 2 倍）" % self.n_relaxed, pass_=vok("5b"),
                          at=dict(at=self.edge_min[1], worst_margin_m=fnum(self.edge_margin[0], 5), worst_margin_at=self.edge_margin[1], **vinfo("5b")))
        it["(5c)"] = dict(value=[fnum(self.st_row[0], 4), fnum(self.st_row[1], 3)], threshold="0.05〜4", pass_=vok("5c"), at=vinfo("5c"))
        it["(5d)"] = dict(value=[fnum(self.st_x[0], 4), fnum(self.st_x[1], 3)], threshold="0.05〜4", pass_=vok("5d"), at=vinfo("5d"))
        it["(5e)"] = dict(value=[fnum(self.seam[0], 4), fnum(self.seam[1], 3)], threshold="0.25〜4", pass_=vok("5e"), at=vinfo("5e"))
        si_ = self.si
        it["(5f)"] = dict(value=si_["row_hits"] + si_["mid_hits"], threshold="0", pass_=si_["row_hits"] + si_["mid_hits"] == 0,
                          at=dict(frames=si_["frames"], row=si_["row_hits"], mid=si_["mid_hits"], both_ge_5mm=si_["resolvable_hits"], tau_range=si_["tau_range"], examples=si_["examples"]))
        fl = self.flips
        it["(5g)"] = dict(value=fl["n_resolvable"] + fl["n_region"], threshold="0", pass_=fl["n_resolvable"] + fl["n_region"] == 0,
                          at=dict(resolvable_whole_mesh=fl["n_resolvable"], lip_tube_region=fl["n_region"], all_incl_slivers=fl["n_all"],
                                  first=fl["at"], first_region=fl["at_region"], tau_range=V_.get("5g", {}).get("tau_range")))
        it["(6)"] = dict(value=self.tri_min_all[0], threshold="> 0", pass_=self.tri_min_all[0] > 1e-10,
                         at=dict(at=self.tri_min_all[1], zero_area_faces_whole_mesh_at_tstar=self.zero_all_tstar, **vinfo("6")))
        for v in it.values():
            v["pass_"] = bool(v["pass_"])
            if not isinstance(v["value"], list):
                v["value"] = fnum(v["value"], 6)
        nfail = sum(1 for v in it.values() if not v["pass_"])
        return dict(items=it, n_fail=nfail, n_items=len(it), summary_ja="%d 項目中 %d 項目が不合格" % (len(it), nfail))


# ---------------------------------------------------------------- 源の面の c 一定の切り口（波頭の欠落の基準）
class RowCurve:
    """表示の行 i ごとに、源の区分線形の面の c 一定の切り口の頂点（源の列の辺と対角線との交点）を重心座標で持つ。"""

    def __init__(self, net):
        src = net.src
        nvs, nus = src.nv, src.nu
        fr = net.rho - np.floor(np.clip(net.rho, 0, nvs - 2 + 1e-12))
        fr = np.where(net.rho >= nvs - 1, 1.0, fr)
        j = np.arange(nus, dtype=np.float64)
        kap = np.concatenate([np.broadcast_to(j[None, :], (net.nv, nus)), (j[:-1][None, :] + 1.0 - fr[:, None])], 1)
        kap = np.sort(kap, 1)
        rho = np.broadcast_to(net.rho[:, None], kap.shape)
        self.idx, self.w = S.bary(rho, kap, nvs, nus)

    def eval(self, Xw_src):
        return S.gather(Xw_src.reshape(-1, 3), self.idx, self.w)


def crest_metrics(Xw_disp, Xw_curve, K, curled):
    """行ごとの頂の高さ（y の最大）と、巻きの行の唇の前への届き（a の最大）。戻り (dH (nv,), dA (nv,) 巻きの行以外は nan)。"""
    Hd = Xw_disp[..., 1].max(1)
    Hs = Xw_curve[..., 1].max(1)
    Ad = ((Xw_disp - K.O) @ K.t).max(1)
    As = ((Xw_curve - K.O) @ K.t).max(1)
    dA = np.where(curled, As - Ad, np.nan)
    return Hs - Hd, dA


# ---------------------------------------------------------------- 面の差（網の弦と源の面）
class Chords:
    def __init__(self, net, fracs):
        self.net = net
        nv, nu = net.nv, net.nu
        E = []
        for di, dj in ((0, 1), (1, 0), (1, -1)):
            i0 = np.arange(max(0, -di), nv - max(0, di))
            j0 = np.arange(max(0, -dj), nu - max(0, dj))
            I, Jj = np.meshgrid(i0, j0, indexing="ij")
            E.append(np.stack([I.ravel(), Jj.ravel(), (I + di).ravel(), (Jj + dj).ravel()], 1))
        self.E = np.concatenate(E, 0)
        self.fracs = np.asarray(fracs, np.float64)
        self.a = self.E[:, 0] * nu + self.E[:, 1]
        self.b = self.E[:, 2] * nu + self.E[:, 3]

    def deviation(self, Dw, kap, Xw_src):
        """Dw：表示の網（ワールド、(nv, nu, 3)）、kap：時刻の κ、Xw_src：源（ワールド）。戻り (距離, 法線の成分) の全標本の配列。"""
        net = self.net
        src = net.src
        Df = Dw.reshape(-1, 3)
        rho = np.broadcast_to(net.rho[:, None], (net.nv, net.nu)).reshape(-1)
        kf = kap.reshape(-1)
        Xf = Xw_src.reshape(-1, 3)
        dist, nd = [], []
        for f in self.fracs:
            P = (1 - f) * Df[self.a] + f * Df[self.b]
            r = (1 - f) * rho[self.a] + f * rho[self.b]
            k = (1 - f) * kf[self.a] + f * kf[self.b]
            idx, w = S.bary(r, k, src.nv, src.nu)
            Q = S.gather(Xf, idx, w)
            nrm = np.cross(Xf[idx[:, 1]] - Xf[idx[:, 0]], Xf[idx[:, 2]] - Xf[idx[:, 0]])
            nl = np.linalg.norm(nrm, axis=1)
            dv = P - Q
            dist.append(np.linalg.norm(dv, axis=1))
            nd.append(np.where(nl > 1e-12, np.abs((dv * nrm).sum(1)) / np.maximum(nl, 1e-12), np.linalg.norm(dv, axis=1)))
        return np.concatenate(dist), np.concatenate(nd)


# ---------------------------------------------------------------- 薄膜
def film_row(a, y, jtip_lo, jtip_hi, j_end, dlist):
    """断面の折れ線 (a, y) の唇先（列 jtip_lo〜jtip_hi の a の最大）から上面へ弧長 d の点の、上面の法線の向きの厚み。"""
    seg = np.arange(jtip_lo, jtip_hi + 1)
    jt = int(seg[np.argmax(a[seg])])
    P = np.stack([a, y], 1)
    up = P[jtip_lo:jt + 1][::-1]          # 唇先から頂へ
    ds = np.hypot(*np.diff(up, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(ds)])
    tail = P[jt:j_end + 1]                 # 唇先から先（下面・管の天井）
    out = []
    for d in dlist:
        if s[-1] < d or len(tail) < 2:
            out.append(np.nan)
            continue
        k = int(np.searchsorted(s, d) - 1)
        k = min(max(k, 0), len(up) - 2)
        f = (d - s[k]) / max(ds[k], 1e-12)
        p = up[k] + f * (up[k + 1] - up[k])
        # 厚み = 上面の点 p から、唇先より先の折れ線（下面・管の天井）への最短の距離（上面の法線の向きの線は、巻いた唇先で
        # 下面に当たらず抜けることがあるので、最短の距離で測る。平らな膜なら法線の向きの厚みと同じ）
        p1, p2 = tail[:-1], tail[1:]
        e = p2 - p1
        ll = np.maximum((e * e).sum(1), 1e-18)
        tt = np.clip(((p - p1) * e).sum(1) / ll, 0.0, 1.0)
        q = p1 + tt[:, None] * e
        out.append(float(np.hypot(*(q - p).T).min()))
    return out


def film(net, Xw, dlist):
    K = net.src.K
    A = (Xw - K.O) @ K.t
    Y = Xw[..., 1]
    res = []
    for (i, jt, rim, ja) in net.tip_rows:
        if net.disp is None:
            q = net.ks.cq[i]
            lo, hi, end = q["jt"], q["rim"], q["ja"]
        else:
            lo, hi, end = jt, rim, ja
        res.append(film_row(A[i], Y[i], lo, hi, end, dlist))
    return np.array(res)


# ---------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", required=True)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--dev-every", type=int, default=3)
    ap.add_argument("--si-last-hz", type=int, default=HZ, help="最後の 2.5 s の自己交差の検査の頻度（既定 30 Hz = 設計27 の関門と同じ。約 2 倍の網は 2 にして 30 分以内にする）")
    a = ap.parse_args()
    t_all = time.time()
    P = S.load_params()
    PM = P["measure"]
    src = S.Source(P)
    net = Net(a.display, src)
    pk = net.pk
    K = src.K
    print("網 %s：%d × %d、%d 層（%.0f s）" % (net.name, net.nv, net.nu, pk.L, time.time() - t_all), flush=True)
    kn = pk.knots
    n30 = int(math.floor(-kn[0] * HZ + 1e-6))
    taus = -np.arange(n30, -1, -1) / HZ
    p13 = P13(net)
    rc = RowCurve(net)
    ch = Chords(net, PM["edge_samples"])
    si_frames = set()
    for m_ in range(int(math.floor(-kn[0] * 2 + 1e-6)) + 1):
        tv = -0.5 * m_
        if tv < -2.5 - 1e-9 and tv >= kn[0] - 1e-9:
            si_frames.add(round(tv * HZ))
    step_si = max(1, HZ // max(1, a.si_last_hz))
    for m_ in range(0, int(2.5 * HZ) + 1, step_si):
        si_frames.add(-m_)
    herm = dict(max=0.0, at=None, p99s=[], nmax=0.0)
    crest = dict(ex_H=[], ex_A=[], pb_H=[], pb_A=[])
    dev = dict(dist_max=0.0, dist_at=None, nrm_max=0.0, nrm_at=None, sq=0.0, nsq=0.0, cnt=0)
    film_rec = {}
    t0 = time.time()
    for k, tau in enumerate(taus):
        Xs = src.local(tau)
        O = src.origin(tau)
        Dex, kap = net.exact_local(Xs, tau)
        Dh = pk.local(tau)
        e = np.linalg.norm(Dh - Dex, axis=-1)
        if float(e.max()) > herm["max"]:
            i = np.unravel_index(int(e.argmax()), e.shape)
            herm.update(max=float(e.max()), at=dict(tau=round(float(tau), 4), row=int(i[0]), col=int(i[1])))
        herm["p99s"].append(float(np.percentile(e, 99)))
        Xw = Dh + O
        p13.add(tau, Xw, Dh, do_si=(round(tau * HZ) in si_frames), last=(k == len(taus) - 1))
        Xws = Xs + O
        Cw = rc.eval(Xws)
        dH, dA = crest_metrics(Dex + O, Cw, K, net.curled)
        crest["ex_H"].append(dH)
        crest["ex_A"].append(dA)
        dH2, dA2 = crest_metrics(Xw, Cw, K, net.curled)
        crest["pb_H"].append(dH2)
        crest["pb_A"].append(dA2)
        if net.disp is not None and (k % a.dev_every == 0 or k == len(taus) - 1):
            dist, nd = ch.deviation(Dex + O, kap, Xws)
            if dist.max() > dev["dist_max"]:
                dev["dist_max"], dev["dist_at"] = float(dist.max()), round(float(tau), 4)
            if nd.max() > dev["nrm_max"]:
                dev["nrm_max"], dev["nrm_at"] = float(nd.max()), round(float(tau), 4)
            dev["sq"] += float((dist ** 2).sum())
            dev["nsq"] += float((nd ** 2).sum())
            dev["cnt"] += len(dist)
        for ft in PM["film_taus"]:
            if abs(tau - ft) < 0.5 / HZ and str(ft) not in film_rec:
                film_rec[str(ft)] = dict(tau=round(float(tau), 4), exact=film(net, Dex + O, PM["film_d_m"]), playback=film(net, Xw, PM["film_d_m"]))
        if k % 60 == 0:
            print("  %d/%d τ=%.2f（%.0f s）" % (k, len(taus), tau, time.time() - t0), flush=True)
    p13r = p13.result(float(K.Y.max(1)[K.main_row]))
    # ---- t* と K* の面の差
    tstar = {}
    if net.disp is not None:
        D0 = net.disp.eval(K.X, 0.0)
        dist, nd = ch.deviation(D0, net.kappa0, K.X)
        tstar = dict(vs_kstar_chord_dist_max_m=float(dist.max()), vs_kstar_chord_dist_rms_m=float(np.sqrt((dist ** 2).mean())),
                     vs_kstar_chord_normal_max_m=float(nd.max()), vs_kstar_chord_normal_rms_m=float(np.sqrt((nd ** 2).mean())),
                     vertices_on_kstar_surface_max_m=0.0,
                     package_last_layer_vs_exact_max_m=float(np.linalg.norm(pk.local(0.0) + src.origin(0.0) - D0, axis=-1).max()))
    else:
        tstar = dict(package_last_layer_vs_kstar_max_m=float(np.linalg.norm(pk.local(0.0) + src.origin(0.0) - K.X, axis=-1).max()))
    # ---- 波頭の欠落
    def stat(arrs, curled_only=False):
        A_ = np.stack(arrs)
        if curled_only:
            A_ = A_[:, net.curled]
        v = A_[np.isfinite(A_)]
        i = np.unravel_index(int(np.nanargmax(np.where(np.isfinite(A_), A_, -np.inf))), A_.shape)
        return dict(max_m=float(v.max()), rms_m=float(np.sqrt((v ** 2).mean())), min_m=float(v.min()),
                    at=dict(tau=round(float(taus[i[0]]), 4), row=int(np.nonzero(net.curled)[0][i[1]] if curled_only else i[1])))
    crest_out = dict(exact_crest_height=stat(crest["ex_H"]), exact_crest_height_curled_rows=stat(crest["ex_H"], True),
                     playback_crest_height_curled_rows=stat(crest["pb_H"], True), exact_lip_reach=stat(crest["ex_A"], True),
                     playback_crest_height=stat(crest["pb_H"]), playback_lip_reach=stat(crest["pb_A"], True),
                     note_ja="源 − 網（正なら網が低い・届かない）。exact は正確な表示の網、playback はパッケージの再生（量子化・Hermite を含む）。"
                             "crest_height は全行（平らな余白のうねりを含む）、_curled_rows は主役波の巻きの行（源の行 60〜192）だけ")
    # ---- 薄膜
    dl = PM["film_d_m"]
    film_out = {}
    import warnings
    warnings.simplefilter("ignore", RuntimeWarning)
    for key, v in film_rec.items():
        ent = dict(tau=v["tau"])
        for nm in ("exact", "playback"):
            F = v[nm]
            ent[nm] = {("d_%.1fm" % d): dict(min_m=fnum(np.nanmin(F[:, j]), 4), p5_m=fnum(np.nanpercentile(F[:, j], 5), 4),
                                             rows_below_min=int(np.sum(F[:, j] < PM["film_min_m"])), rows_nan=int(np.sum(~np.isfinite(F[:, j]))),
                                             rows=int(F.shape[0]),
                                             min_row=(int(net.tip_rows[int(np.nanargmin(F[:, j]))][0]) if np.isfinite(F[:, j]).any() else None))
                       for j, d in enumerate(dl)}
        film_out[key] = ent
    # ---- Hermite：全区間の中点と、節点の間隔が変わる所
    D = np.diff(kn)
    ratio = np.ones(len(D))
    ratio[1:] = np.maximum(ratio[1:], np.maximum(D[1:] / D[:-1], D[:-1] / D[1:]))
    ratio[:-1] = np.maximum(ratio[:-1], np.maximum(D[:-1] / D[1:], D[1:] / D[:-1]))
    trans = np.nonzero(ratio >= PM["nonuniform_ratio"])[0]
    hmid = []
    htr = []
    t1 = time.time()
    for i in range(len(D)):
        pts = [0.5]
        if i in set(trans.tolist()):
            m = int(PM["nonuniform_samples_per_interval"])
            pts = [(j + 1) / (m + 1) for j in range(m)]
        for f in pts:
            t = kn[i] + f * D[i]
            Xs = src.local(t)
            Dex, _ = net.exact_local(Xs, t)
            e = float(np.linalg.norm(pk.local(t) - Dex, axis=-1).max())
            (htr if i in set(trans.tolist()) else hmid).append((float(t), e, i))
    print("  Hermite の区間の検査（%.0f s）" % (time.time() - t1), flush=True)
    worst_tr = max(htr, key=lambda x: x[1]) if htr else None
    worst_mid = max(hmid, key=lambda x: x[1]) if hmid else None
    herm_out = dict(frames_30hz_max_m=herm["max"], frames_30hz_at=herm["at"], frames_30hz_p99_of_frame_p99_m=float(np.percentile(herm["p99s"], 99)),
                    uniform_interval_midpoints=dict(n=len(hmid), max_m=worst_mid[1] if worst_mid else None, at_tau=worst_mid[0] if worst_mid else None),
                    nonuniform_intervals=dict(n_intervals=int(len(trans)), n_samples=len(htr), max_m=worst_tr[1] if worst_tr else None,
                                              at_tau=worst_tr[0] if worst_tr else None,
                                              spacing_at_worst=[float(D[worst_tr[2] - 1]) if worst_tr and worst_tr[2] > 0 else None,
                                                                float(D[worst_tr[2]]) if worst_tr else None,
                                                                float(D[worst_tr[2] + 1]) if worst_tr and worst_tr[2] + 1 < len(D) else None],
                                              intervals_tau=[[float(kn[i]), float(kn[i + 1]), float(ratio[i])] for i in trans][:60]),
                    note_ja="パッケージの再生（量子化した節点の Hermite）と正確な表示の網（生成器の値を網に写したもの）の差、全頂点の最大。"
                            "節点の間隔が変わる所＝隣の区間との間隔の比が 1.5 以上の区間（内側の 8 点）。")
    # ---- GPU
    n = net.nv * net.nu
    ntri = 2 * (net.nv - 1) * (net.nu - 1)
    gpu = dict(position_buffer_mib=pk.L * n * 6 / 2 ** 20, twhite_mib=n * 4 / 2 ** 20,
               mesh_vertex_mib_estimate=n * (12 + 12 + 16 + 8 + 8 + 8) / 2 ** 20, mesh_index_mib=ntri * 3 * 4 / 2 ** 20,
               note_ja="位置 = 層 × 頂点 × 6 バイト（設計27 の再生器：StructuredBuffer<uint> に 16 bit × 3、CPU の写しなし）。網の頂点は位置・法線・接線・UV・UV2・UV3 の見積もり（Unity の実測ではない）")
    gpu["total_mib_estimate"] = gpu["position_buffer_mib"] + gpu["twhite_mib"] + gpu["mesh_vertex_mib_estimate"] + gpu["mesh_index_mib"]
    gpu["within_512"] = bool(gpu["total_mib_estimate"] <= P["gpu"]["budget_mib"])
    dev_out = {}
    if dev["cnt"]:
        dev_out = dict(chord_dist_max_m=dev["dist_max"], chord_dist_max_tau=dev["dist_at"], chord_dist_rms_m=math.sqrt(dev["sq"] / dev["cnt"]),
                       chord_normal_max_m=dev["nrm_max"], chord_normal_max_tau=dev["nrm_at"], chord_normal_rms_m=math.sqrt(dev["nsq"] / dev["cnt"]),
                       frames_hz=HZ / a.dev_every, samples=dev["cnt"],
                       note_ja="表示の網（正確）の辺の 1/4・1/2・3/4 の点と、同じ媒介変数の源の面（設計28 の動き）の点の差。距離と源の面の法線の成分")
    out = dict(display=net.name, rows=net.nv, cols=net.nu, vertices=n, triangles=ntri, layers=int(pk.L), package=S.rel(net.dir),
               package_iface=pk.iface, q_max_m=net.q_max, P13=p13r, tstar=tstar, crest_loss=crest_out, film=film_out, hermite=herm_out,
               deviation_from_ds28_motion=dev_out, gpu=gpu, settings=dict(dev_every_frames=a.dev_every, si_last_2p5s_hz=a.si_last_hz),
               seconds=round(time.time() - t_all, 1))
    os.makedirs(a.out, exist_ok=True)
    S.dump_json(os.path.join(a.out, "%s.json" % net.name), out)
    print("DONE %s %.0f s" % (net.name, time.time() - t_all), flush=True)


if __name__ == "__main__":
    main()
