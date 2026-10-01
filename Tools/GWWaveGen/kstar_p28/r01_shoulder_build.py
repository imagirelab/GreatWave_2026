# -*- coding: utf-8 -*-
"""仕上げ28修正01 の案 SHOULDER（肩）の生成器。py -3.10 r01_shoulder_build.py <out_prefix> [design.json]

土台は採用中の K*′ P28R2rec（変えない）。原画のカメラから見て輪郭の縁（rim）より奥の殻（背と、奥の行の頂・唇の上）だけを動かす：
  1. 原画視点の厳密な z バッファー（rec_common.zbuf）で、土台の見えている四角形を求め、その頂点（と隣の行）を「止める点」にする。
     行ごとの錨の列 ja（背の側で最初に見える列 − anchor_margin_cols、上限 anchor_cap）と、動かせる最後の列 jf（その行で最初に見える列
     − anchor_margin_cols、上限 free_cap）を決め、c 方向に ±anchor_minwin_rows 行の最小をとる（保守的に）。
  2. 望む変位（設計で選ぶ。足し合わせる）：
     stretch：背（列 18..ja）を錨の点のまわりで水平に (1 + k(c)·g) 倍に伸ばす（高さはそのまま。背が後ろへ長く、ゆるくなる）。
     offset ：動かせる所（列 18..jf、または背だけ）を、面の外向きの法線（行の面の中、c と列の方向にならした面で）の向きに M(c)·w(j) ずらす。
              w は足で 0（海から浮かせない）・jf で 0。M(c) は c 方向に少しずつ増える（c_ramp の smoothstep）。
     defold ：動かせる所を、c 方向にならした形（σ sigma_c_m）へ寄せる（後ろから見た縦の襞を消す）。
     どれも奥の端の行（c > 15 − end_fade_m）で 0 へ戻し、境の輪（列 0、行 0・239）と海の帯の高さは動かさない。
     列 0..17 の海の帯は、列 0 を止めたまま、新しい足（列 18）までの間に比例で並べ直す。
  3. 余地：各頂点が変位の向きに沿って動ける距離（その行の空の射線の禁止域（第2回と同じ、膨らみ 3 px）と、船・手前の海の射線の
     禁止域（回復と同じ）のうち、土台の塗りにないセルまで）から clear_margin_m を引いた値で、変位の割合（0..1）を上から押さえる。
  4. 割合を c 方向（σ sigma_c_m）と列の方向（σ sigma_cols）にならし、余地で押さえる、をくり返す（3 次元でなめらかな下の包絡）。
     組み立てた行が禁止域に新しくかかる・自己交差する時は、かかったセルの近くの頂点の割合を減らしてくり返す（土台へ戻して段を作らない）。
原画の輪郭を作る点（78・130・131 の頂の列、132 の唇、72 の唇先と管の口）は見えている四角形の頂点なので動かない。
格子 400×240、目印の列、UV、行の c、境の輪は変えない。参照モデルは読まない（F13-1）。
"""
import os
import sys
import json
import time

import numpy as np
from scipy.ndimage import gaussian_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402
import rec_common as RC  # noqa: E402
import r2_build as B2  # noqa: E402

R = S.R
KC = S.KC

DEFAULT = {
    "stretch": None,              # {"k_max", "c_ramp": [c0, c1], "fade_m"}
    "offset": None,               # {"m_max", "c_ramp": [c0, c1], "foot_m", "top_m", "cols": "free"|"back"}
    "defold": None,               # {"sigma_c_m", "foot_m", "top_m", "cols": "free"|"back", "c_min"}
    "free_cap": 190,
    "end_fade_m": 1.5,
    "anchor_margin_cols": 6,
    "anchor_cap": 84,
    "anchor_minwin_rows": 3,
    "sea_cols": 18,
    "sigma_c_m": 0.8,
    "sigma_cols": 2.0,
    "clear_margin_m": 0.3,
    "desired_sigma_c_m": 0.0,     # 望む変位を c 方向にならす σ（0 で使わない）
    "desired_sigma_cols": 0.0,    # 同じく列の方向
}


def vis_vertices(c, A, Y, cache=None):
    """原画視点で見えている四角形（厳密な z バッファー、ss=1）と、その 4 頂点（と上下の行）の bool（NV×NU）。"""
    if cache and os.path.isfile(cache):
        q = np.load(cache)
    else:
        zb, ids = RC.zbuf(c, A, Y, 1)
        iv, iu = RC.tri_quad(ids)
        q = np.zeros((A.shape[0], A.shape[1] - 1), bool)
        ok = iv >= 0
        q[iv[ok], iu[ok]] = True
        if cache:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            np.save(cache, q)
    v = np.zeros(A.shape, bool)
    v[:, :-1] |= q; v[:, 1:] |= q
    v[1:] |= v[:-1].copy(); v[:-1] |= v[1:].copy()
    return q, v


class Build:
    def __init__(self, design=None, base=None):
        self.d = json.loads(json.dumps(DEFAULT))
        if design:
            self.d.update(design)
        self.base = base or S.BASE_ROWS
        self.c, self.A0, self.Y0 = S.load_rows(self.base)
        self.nv, self.nu = self.A0.shape
        self.G = R.keepout_grids(self.c, 3, 2, cache=S.KEEPOUT_CACHE)
        self.base_fill = [R.section_fill(self.A0[i], self.Y0[i]) & self.G[i] for i in range(self.nv)]
        z = np.load(S.PROTECT_CACHE)
        assert np.allclose(z["c"], self.c)
        self.Gp = np.unpackbits(z["G"], axis=-1)[..., :R.NA].astype(bool)
        self.base_fill_p = [R.section_fill(self.A0[i], self.Y0[i]) & self.Gp[i] for i in range(self.nv)]
        self.visq, self.visv = vis_vertices(self.c, self.A0, self.Y0, cache=os.path.join(S.OUT, "cache", "vis_quads_base.npy"))
        self.base_selfx = np.array([B2.seg_selfx(self.A0[i], self.Y0[i], 0, None) for i in range(self.nv)])
        self.log = []

    # ------------------------------------------------------------ 確かめ
    def spill(self, i, a, y):
        f = R.section_fill(a, y)
        return int((f & self.G[i] & ~self.base_fill[i]).sum()), int((f & self.Gp[i] & ~self.base_fill_p[i]).sum())

    def row_ok(self, i, a, y):
        s, p = self.spill(i, a, y)
        if s > 0 or p > 0:
            return False
        if B2.seg_selfx(a, y, 0, None) > self.base_selfx[i]:
            return False
        if np.any(np.diff(a[:self.d["sea_cols"] + 1]) <= 1e-4):
            return False
        return True

    # ------------------------------------------------------------ 錨と動かせる列
    def _first_vis(self, jcap, j_hi=None):
        d = self.d
        out = np.full(self.nv, int(jcap), int)
        for i in range(self.nv):
            v = np.nonzero(self.visv[i, :j_hi])[0]
            if len(v):
                out[i] = min(int(v.min()) - d["anchor_margin_cols"], int(jcap))
        w = int(d["anchor_minwin_rows"])
        o2 = out.copy()
        for i in range(self.nv):
            o2[i] = out[max(0, i - w):i + w + 1].min()
        return np.maximum(o2, d["sea_cols"] + 8)

    def anchors(self):
        self.ja = self._first_vis(self.d["anchor_cap"], 140)
        self.jf = self._first_vis(self.d["free_cap"], None)
        self.jf = np.maximum(self.jf, self.ja)

    def row_weight(self, i, jmax, foot_m, top_m):
        """列の重み：足（列 sea_cols）で 0 → 弧長 foot_m で 1、jmax の手前 top_m で 1 → jmax で 0。"""
        a, y = self.A0[i], self.Y0[i]
        s = R.arclen(a, y)
        js = int(self.d["sea_cols"])
        w = np.zeros(self.nu)
        jj = np.arange(js, jmax + 1)
        w[jj] = R.ss((s[jj] - s[js]) / foot_m) * R.ss((s[jmax] - s[jj]) / top_m)
        return w

    @staticmethod
    def normals2d(a, y):
        ta = np.gradient(a); ty = np.gradient(y)
        L = np.maximum(np.hypot(ta, ty), 1e-9)
        return -ty / L, ta / L          # 外向き（背では上・後ろ、頂では上）

    def cramp(self, g):
        """c 方向の重み：c_ramp [c0, c1] の smoothstep（c0 > c1 なら −c 方向へ増える）、任意の窓 c_window [lo0, lo1, hi1, hi0]
        （lo0→lo1 で 0→1、hi1→hi0 で 1→0）、奥の端の手前 end_fade_m で 0。"""
        c0, c1 = g["c_ramp"]
        w = R.ss((self.c - c0) / (c1 - c0)) * R.ss((self.c.max() - self.c) / self.d["end_fade_m"])
        if g.get("c_window"):
            lo0, lo1, hi1, hi0 = g["c_window"]
            w = w * R.ss((self.c - lo0) / (lo1 - lo0)) * R.ss((hi0 - self.c) / (hi0 - hi1))
        return w

    # ------------------------------------------------------------ 望む変位
    def desired(self):
        d = self.d
        js = int(d["sea_cols"])
        dA = np.zeros_like(self.A0); dY = np.zeros_like(self.Y0)
        info = {}
        st = d.get("stretch")
        if st and st.get("k_max", 0) > 0:
            k = st["k_max"] * self.cramp(st)
            for i in range(self.nv):
                if k[i] <= 1e-6:
                    continue
                a = self.A0[i]; y = self.Y0[i]; ja = int(self.ja[i])
                s = R.arclen(a, y)
                g = R.ss((s[ja] - s[:ja + 1]) / st.get("fade_m", 4.0))
                dA[i, :ja + 1] += (a[:ja + 1] - a[ja]) * k[i] * g
            info["stretch_k_max"] = round(float(k.max()), 3)
        of = d.get("offset")
        if of and abs(of.get("m_max", 0)) > 0:
            M = of["m_max"] * self.cramp(of)
            As = gaussian_filter1d(R.csmooth(self.c, self.A0, 1.0), 3, axis=1, mode="nearest")
            Ys = gaussian_filter1d(R.csmooth(self.c, self.Y0, 1.0), 3, axis=1, mode="nearest")
            for i in range(self.nv):
                if abs(M[i]) <= 1e-6:
                    continue
                jmax = int(self.jf[i]) if of.get("cols", "free") == "free" else int(self.ja[i])
                w = self.row_weight(i, jmax, of.get("foot_m", 5.0), of.get("top_m", 3.0))
                na, ny = self.normals2d(As[i], Ys[i])
                dA[i] += M[i] * w * na; dY[i] += M[i] * w * ny
            info["offset_m_max"] = round(float(M.max()), 3)
        df = d.get("defold")
        if df and df.get("sigma_c_m", 0) > 0:
            As = R.csmooth(self.c, self.A0 + dA, df["sigma_c_m"]); Ys = R.csmooth(self.c, self.Y0 + dY, df["sigma_c_m"])
            for i in range(self.nv):
                jmax = int(self.jf[i]) if df.get("cols", "free") == "free" else int(self.ja[i])
                w = self.row_weight(i, jmax, df.get("foot_m", 2.0), df.get("top_m", 3.0))
                if df.get("c_min") is not None:
                    w = w * R.ss((self.c[i] - df["c_min"]) / 2.0)
                w = w * R.ss((self.c.max() - self.c[i]) / d["end_fade_m"])
                dA[i] += w * (As[i] - (self.A0[i] + dA[i])); dY[i] += w * (Ys[i] - (self.Y0[i] + dY[i]))
            info["defold_sigma_c_m"] = df["sigma_c_m"]
        # 望む変位そのものを c 方向・列の方向にならす（行ごとの錨の列の違いが、後ろから見た細い縦の筋にならないように）
        sdc = float(d.get("desired_sigma_c_m", 0.0)); sdj = float(d.get("desired_sigma_cols", 0.0))
        if sdc > 0:
            dA = R.csmooth(self.c, dA, sdc); dY = R.csmooth(self.c, dY, sdc)
        if sdj > 0:
            dA = gaussian_filter1d(dA, sdj, axis=1, mode="nearest"); dY = gaussian_filter1d(dY, sdj, axis=1, mode="nearest")
        info["desired_smoothing"] = [sdc, sdj]
        dA[:, :js] = 0.0; dY[:, :js] = 0.0
        dA[self.visv] = 0.0; dY[self.visv] = 0.0
        dA[0] = dA[-1] = 0.0; dY[0] = dY[-1] = 0.0
        return dA, dY, info

    # ------------------------------------------------------------ 余地（変位の向きに沿って禁止域まで）
    def clearance_along(self, dA, dY, step=0.06, tmax=16.0):
        L = np.hypot(dA, dY)
        cl = np.full(dA.shape, 1e3)
        ts = np.arange(step, tmax + step, step)
        for i in range(self.nv):
            jj = np.nonzero(L[i] > 1e-6)[0]
            if not len(jj):
                continue
            K = (self.G[i] & ~self.base_fill[i]) | (self.Gp[i] & ~self.base_fill_p[i])
            if not K.any():
                continue
            ua = dA[i, jj] / L[i, jj]; uy = dY[i, jj] / L[i, jj]
            pa = self.A0[i, jj][:, None] + ts[None, :] * ua[:, None]
            py = self.Y0[i, jj][:, None] + ts[None, :] * uy[:, None]
            ia = np.round((pa - R.GA0) / R.GRES).astype(int); iy = np.round((py - R.GY0) / R.GRES).astype(int)
            inb = (ia >= 0) & (ia < R.NA) & (iy >= 0) & (iy < R.NY)
            hit = np.zeros(ia.shape, bool)
            hit[inb] = K[iy[inb], ia[inb]]
            first = np.where(hit.any(1), hit.argmax(1), -1)
            cl[i, jj] = np.where(first >= 0, ts[np.maximum(first, 0)] - step, 1e3)
        return cl

    # ------------------------------------------------------------ 全体
    def run(self):
        d = self.d
        self.anchors()
        dA, dY, info = self.desired()
        L = np.hypot(dA, dY)
        cl = self.clearance_along(dA, dY)
        lim = np.where(L > 1e-6, np.clip((cl - float(d["clear_margin_m"])) / np.maximum(L, 1e-9), 0.0, 1.0), 1.0)
        lim[self.visv] = 0.0
        mul = lim.copy()

        def sm(m):
            m = R.csmooth(self.c, m, d["sigma_c_m"])
            return gaussian_filter1d(m, d["sigma_cols"], axis=1, mode="nearest") if d["sigma_cols"] > 0 else m
        for _ in range(6):
            mul = np.minimum(sm(mul), lim)
        hist = []
        for it in range(20):
            A, Y = self.assemble(mul, dA, dY)
            bad = [i for i in range(self.nv) if not (np.array_equal(A[i], self.A0[i]) and np.array_equal(Y[i], self.Y0[i]))
                   and not self.row_ok(i, A[i], Y[i])]
            hist.append({"iter": it, "bad_rows_c": [round(float(self.c[i]), 2) for i in bad]})
            if not bad:
                break
            for i in bad:
                f = R.section_fill(A[i], Y[i])
                K = f & ((self.G[i] & ~self.base_fill[i]) | (self.Gp[i] & ~self.base_fill_p[i]))
                ys, xs = np.nonzero(K)
                if len(ys):
                    pa = R.GA0 + xs * R.GRES; py = R.GY0 + ys * R.GRES
                    for r in range(max(0, i - 2), min(self.nv, i + 3)):
                        dd = np.min(np.hypot(A[r][:, None] - pa[None, :], Y[r][:, None] - py[None, :]), 1)
                        lim[r] = np.where(dd < 1.5, lim[r] * 0.6, lim[r])
                else:
                    lim[max(0, i - 1):i + 2] *= 0.8
            mul = np.minimum(mul, lim)
            for _ in range(2):
                mul = np.minimum(sm(mul), lim)
        self.log.append({"assemble_iters": hist, **info})
        for i in range(self.nv):
            if not (np.array_equal(A[i], self.A0[i]) and np.array_equal(Y[i], self.Y0[i])) and not self.row_ok(i, A[i], Y[i]):
                raise RuntimeError("row %d still fails" % i)
        self.mul = mul
        Lr = L.max(1)
        self.k_eff = np.array([float((mul[i] * L[i]).max() / max(Lr[i], 1e-9)) if Lr[i] > 1e-6 else 0.0 for i in range(self.nv)])
        self.log.append({"desired_max_m": round(float(L.max()), 2), "applied_max_m": round(float((mul * L).max()), 2),
                         "applied_over_desired_rows": {"%.1f" % self.c[i]: round(float(self.k_eff[i]), 2)
                                                       for i in range(0, self.nv, 6) if Lr[i] > 0.05}})
        self.A, self.Y = A, Y
        return A, Y

    def assemble(self, mul, dA, dY):
        js = int(self.d["sea_cols"])
        A = self.A0 + mul * dA
        Y = self.Y0 + mul * dY
        a_0 = self.A0[:, :1]
        f = (self.A0[:, :js + 1] - a_0) / np.maximum(self.A0[:, js:js + 1] - a_0, 1e-9)
        sea = a_0 + f * (A[:, js:js + 1] - a_0)
        moved = (A[:, js] != self.A0[:, js])[:, None]
        A[:, :js + 1] = np.where(moved, sea, self.A0[:, :js + 1])     # 足が動かない行は海の帯をバイトまで土台のまま
        Y[:, :js] = self.Y0[:, :js]
        A = np.where(self.visv, self.A0, A); Y = np.where(self.visv, self.Y0, Y)
        return A, Y


def main():
    pre = sys.argv[1]
    design = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
    t0 = time.time()
    b = Build(design)
    A, Y = b.run()
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    prov = {"route": "仕上げ28修正01 の案 SHOULDER Tools/GWWaveGen/kstar_p28/r01_shoulder_build.py",
            "base": "K*′ P28R2rec (Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_rows.npz, sha256 %s)" % S.BASE_SHA["rows"],
            "design": b.d, "reference_model_read_by_generator": False}
    KC.write_candidate(pre, b.c, A, Y, prov)
    mv = np.hypot(A - b.A0, Y - b.Y0)
    rep = {"design": b.d, "log": b.log, "anchor_cols": b.ja.tolist(), "free_cols": b.jf.tolist(),
           "applied_over_desired": [round(float(x), 4) for x in b.k_eff],
           "moved_vertices_gt_1cm": int((mv > 0.01).sum()), "max_move_m": round(float(mv.max()), 3),
           "visible_vertices_moved": int((mv[b.visv] > 1e-9).sum()), "seconds": round(time.time() - t0, 1)}
    S.jdump(rep, pre + "_build_report.json")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("anchor_cols", "free_cols", "applied_over_desired")}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
