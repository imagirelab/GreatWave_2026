# -*- coding: utf-8 -*-
"""RT48 の独立の確かめ（Unity/Build/RT48/check/）の共通部品。

作った者は RT48 を作っていない確かめ役。プロジェクトの比べる道具（Tools/GWWaveGen/rt48/ の r_lib.py・v_compare.py・
u_bakeio.py・v_timing_sum.py など）は読み込まない。R3 の記録（sec・hf）を自分で読み、自分で 0 の等高線を取り、
Unity の書き出し・焼き・動画と比べる。R3 のファイルは開いて読むだけ。
座標：x＝造波板からの距離（場面の x − cfg の x_p）、y＝静かな水面からの高さ（場面の y − shape.json の still_level_offset_m）。
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import sys, json, glob
import numpy as np
from scipy.spatial import cKDTree
from skimage import measure

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

R3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
RT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"
CK = RT + "/check"
OUT = CK + "/out"
os.makedirs(OUT, exist_ok=True)
FPS = 24.0
F0, F1 = 3319, 3889
T0 = (F0 - 1) / FPS            # 138.25 s
X0B = 527.0                    # 焼きの x の原点（manifest の coords.origin_x_rel）
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def jsave(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


_cfg = jload(R3 + "/cfg.json")
_shp = jload(R3 + "/shape.json")
XP = float(_cfg["parms"]["x_p"])                  # 造波板の場面の x
OFF = float(_shp["still_level_offset_m"])         # 静かな水面のずれ


def t_of(f):
    return (f - 1) / FPS


# ------------------------------------------------------------------ R3 の記録
class R3Rec:
    """sec（板の真ん中の断面の符号付き距離、0.5 m、float16）と hf（一番上の水面、z の節 5 個）。
    同じコマが二つの記録にある時は、全部を読み、バイト単位で同じかを overlap_check で数える。"""

    def __init__(self):
        self.sec, self.hf, self._a = {}, {}, {}
        for p in sorted(glob.glob(R3 + "/sec_c*_b*.npz")):
            fr = np.load(p)["frames"]
            for i, f in enumerate(fr):
                f = int(f)
                if F0 <= f <= F1:
                    self.sec.setdefault(f, []).append((p.replace("\\", "/"), i))
        for p in sorted(glob.glob(R3 + "/hf_c*.npz")):
            fr = np.load(p)["frames"]
            for i, f in enumerate(fr):
                f = int(f)
                if F0 <= f <= F1:
                    self.hf.setdefault(f, []).append((p.replace("\\", "/"), i))

    def _load(self, p, key):
        if (p, key) not in self._a:
            d = np.load(p)
            if key == "sdf":
                self._a[(p, key)] = (d["sdf"], json.loads(str(d["meta"])))
            else:
                self._a[(p, key)] = (d["eta"], d["x"], d["z"])
        return self._a[(p, key)]

    def overlap_check(self):
        n_multi, n_diff = 0, 0
        for f in range(F0, F1 + 1):
            for key, tab in (("sdf", self.sec), ("eta", self.hf)):
                L = tab.get(f, [])
                if len(L) > 1:
                    n_multi += 1
                    a0 = self._load(L[0][0], key)[0][L[0][1]]
                    for p, i in L[1:]:
                        a1 = self._load(p, key)[0][i]
                        if a0.tobytes() != a1.tobytes():
                            n_diff += 1
        return n_multi, n_diff

    def section(self, f):
        p, i = self.sec[f][-1]
        a, m = self._load(p, "sdf")
        S = a[i].astype(np.float64)
        xs = m["x0"] + m["dx"] * np.arange(m["nx"]) - XP
        ys = m["y0"] + m["dy"] * np.arange(m["ny"]) - OFF
        return S, xs, ys

    def height(self, f):
        p, i = self.hf[f][-1]
        a, x, z = self._load(p, "eta")
        iz = int(np.argmin(np.abs(z)))
        return a[i][iz].astype(np.float64) - OFF, x - XP


# ------------------------------------------------------------------ 線の部品
def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])


def at_s(P, s, q):
    return np.column_stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])])


def densify(P, h):
    s = arclen(P)
    n = max(2, int(np.ceil(s[-1] / h)) + 1)
    return at_s(P, s, np.linspace(0.0, s[-1], n))


def shoelace(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


class SegTree:
    """折れ線（または閉じた線の集まり）の線分への正確な距離。線分の中点の近い k 本の中から最短を取る。"""

    def __init__(self, polys, closed=None):
        A, B = [], []
        for j, P in enumerate(polys):
            if len(P) < 2:
                continue
            A.append(P[:-1]); B.append(P[1:])
            if closed is not None and closed[j] and not np.allclose(P[0], P[-1]):
                A.append(P[-1:]); B.append(P[:1])
        self.A = np.vstack(A); self.B = np.vstack(B)
        self.Lmax = float(np.hypot(*(self.B - self.A).T).max())
        self.tree = cKDTree(0.5 * (self.A + self.B))

    def dist(self, Q, k=24):
        Q = np.asarray(Q, float)
        if len(Q) == 0:
            return np.zeros(0), 0
        k = min(k, len(self.A))
        dm, idx = self.tree.query(Q, k=k)
        if k == 1:
            dm = dm[:, None]; idx = idx[:, None]
        a = self.A[idx]; ab = self.B[idx] - a
        ap = Q[:, None, :] - a
        L2 = (ab ** 2).sum(-1)
        t = np.clip(np.where(L2 > 0, (ap * ab).sum(-1) / np.where(L2 > 0, L2, 1.0), 0.0), 0.0, 1.0)
        d = np.hypot(*(ap - t[..., None] * ab).transpose(2, 0, 1))
        dmin = d.min(1)
        # k 本の外に、もっと近い線分がありうる点の数（k 本目の中点の距離 < 最短 ＋ 線分の長さの半分）
        unsure = int((dm[:, -1] < dmin + 0.5 * self.Lmax).sum()) if k < len(self.A) else 0
        return dmin, unsure


def crossings_y(P, xq):
    """鉛直の線 x = xq と折れ線 P の交わりの y（全部）"""
    x0, x1 = P[:-1, 0], P[1:, 0]
    k = np.where(((x0 - xq) * (x1 - xq) <= 0) & (x0 != x1))[0]
    w = (xq - x0[k]) / (x1[k] - x0[k])
    return P[k, 1] + w * (P[k + 1, 1] - P[k, 1])


def top_y(P, xq):
    c = crossings_y(P, xq)
    return float(c.max()) if len(c) else float("nan")


# ------------------------------------------------------------------ 1 コマの線
def loop_phase(P, S, xs, ys):
    """閉じた線の中が水（−1）か空気（+1）か：中に入る格子の節の符号の多数決。節がなければ重心の双一次の値。"""
    x0, x1 = P[:, 0].min(), P[:, 0].max(); y0, y1 = P[:, 1].min(), P[:, 1].max()
    ii = np.where((xs >= x0) & (xs <= x1))[0]; jj = np.where((ys >= y0) & (ys <= y1))[0]
    if len(ii) and len(jj):
        X, Y = np.meshgrid(xs[ii], ys[jj])
        pts = np.column_stack([X.ravel(), Y.ravel()])
        ins = measure.points_in_poly(pts, P)
        if ins.any():
            v = S[np.ix_(jj, ii)].ravel()[ins]
            return -1 if (v < 0).sum() >= (v > 0).sum() else 1
    c = P.mean(0)
    return -1 if bilinear(S, xs, ys, c[None])[0] < 0 else 1


def bilinear(S, xs, ys, P):
    dx = xs[1] - xs[0]; dy = ys[1] - ys[0]
    u = (P[:, 0] - xs[0]) / dx; v = (P[:, 1] - ys[0]) / dy
    i = np.clip(np.floor(u).astype(int), 0, len(xs) - 2); j = np.clip(np.floor(v).astype(int), 0, len(ys) - 2)
    fu = u - i; fv = v - j
    return (S[j, i] * (1 - fu) * (1 - fv) + S[j, i + 1] * fu * (1 - fv) + S[j + 1, i] * (1 - fu) * fv + S[j + 1, i + 1] * fu * fv)


def frame_curves(rec, f, ymin=-25.0, xlo=100.0, xhi=925.0):
    """自分の読み方：sec の 0 の等高線（静かな水面から 25 m 下より上）の、断面の左の端から右の端まで続く線を主な線とし、
    その外の x（xlo〜断面の左の端、断面の右の端〜xhi）は hf の z = 0 の節の高さでつなぐ。閉じた線は水か空気か。"""
    S, xs, ys = rec.section(f)
    j0 = int(np.searchsorted(ys, ymin))
    Ss = S[j0:]
    dx = xs[1] - xs[0]; dy = ys[1] - ys[0]
    opens, loops = [], []
    for c in measure.find_contours(Ss, 0.0):
        P = np.column_stack([xs[0] + c[:, 1] * dx, ys[j0] + c[:, 0] * dy])
        if len(c) > 3 and np.allclose(c[0], c[-1]):
            loops.append(P)
        else:
            opens.append(P)
    ext = [P[:, 0].max() - P[:, 0].min() for P in opens]
    k = int(np.argmax(ext))
    m = opens[k]
    if m[0, 0] > m[-1, 0]:
        m = m[::-1]
    spans = abs(m[0, 0] - xs[0]) < 1e-6 and abs(m[-1, 0] - xs[-1]) < 1e-6
    eh, xh = rec.height(f)
    L = (xh >= xlo - 1e-9) & (xh < m[0, 0] - 1e-6)
    R = (xh > m[-1, 0] + 1e-6) & (xh <= xhi + 1e-9)
    main = np.vstack([np.column_stack([xh[L], eh[L]]), m, np.column_stack([xh[R], eh[R]])])
    i0 = int(np.argmin(np.abs(xh - xs[0]))); i1 = int(np.argmin(np.abs(xh - xs[-1])))
    lp = []
    for P in loops:
        lp.append(dict(pts=P, phase=loop_phase(P, Ss, xs, ys[j0:]), area=abs(shoelace(P))))
    return dict(main=main, sec=m, loops=lp, n_other_open=len(opens) - 1, spans=spans,
                stitch=(float(m[0, 1] - eh[i0]), float(m[-1, 1] - eh[i1])), field=(S, xs, ys), hf=(eh, xh))


def crest_index(P, xprev, half=40.0):
    idx = np.where((P[:, 0] >= xprev - half) & (P[:, 0] <= xprev + half))[0]
    return int(idx[np.argmax(P[idx, 1])])


def front_overturn(P, ic, chord=0.5, maxlen=40.0):
    """頂から前へ（番号の増える向き）、水面が静かな水面の下に入るまで（か 40 m）の前の面を、線に沿って chord 離れた 2 点の弦で測る。
    弦の下る角 atan2(−dy, dx) の最大と、初めて 90° 以上になった所の x を返す（90° 以上＝鉛直か、前へかぶさる）。"""
    s = arclen(P)
    iend = ic
    while iend < len(P) - 1 and s[iend] - s[ic] < maxlen and P[iend, 1] >= 0.0:
        iend += 1
    if iend <= ic + 1:
        return -999.0, None
    q = s[ic:iend]
    Q0 = P[ic:iend]
    Q1 = at_s(P, s, np.minimum(q + chord, s[-1]))
    d = Q1 - Q0
    ang = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
    ang = np.where(d[:, 1] < 0, ang, -999.0)
    j = np.where(ang >= 90.0)[0]
    return float(ang.max()), (float(Q0[j[0], 0]) if len(j) else None)


def lip(P, ic, half=40.0, back=0.5):
    """唇の先：頂から前へたどり、x が極大で、その後 back 以上戻る最初の点。届く距離＝先の x − 先の下の面（先から、線が先の x を
    再び越えるまで）の最も後ろの x。厚み＝その半分の x での、上の面（頂〜先）と下の面（先〜最も後ろ）の高さの差。"""
    x = P[:, 0]; n = len(P)
    i = ic + 1; tip = None
    while i < n - 1 and x[i] <= x[ic] + half:
        if x[i] >= x[i - 1] and x[i] > x[i + 1]:
            j = i + 1
            while j < n and x[j] <= x[i]:
                j += 1
            if x[i] - x[i:j].min() >= back:
                tip = i; jret = j
                break
        i += 1
    if tip is None:
        return None
    ib = tip + int(np.argmin(x[tip:jret]))
    reach = float(x[tip] - x[ib])
    xm = x[tip] - 0.5 * reach
    yu = crossings_y(P[ic:tip + 1], xm); yl = crossings_y(P[tip:ib + 1], xm)
    thick = float(yu.max() - yl.max()) if len(yu) and len(yl) else float("nan")
    return dict(tip=(float(x[tip]), float(P[tip, 1])), x_back=float(x[ib]), reach=reach, thick=thick, i_tip=tip)


HULL_DX = np.linspace(-6.0, 6.0, 9)


def boat_pose(P, seat):
    ys = np.array([top_y(P, seat + d) for d in HULL_DX])
    h = ys.mean()
    slope = np.sum(HULL_DX * (ys - h)) / np.sum(HULL_DX ** 2)
    return float(h), float(np.degrees(np.arctan(slope))), ys


def taper_w(x, a0=100.0, a1=200.0, b0=825.0, b1=925.0):
    """x の両端の下ろし（計画 §3.2 の文から：100〜200 m で 0→1、825〜925 m で 1→0 の余弦）。x は造波板からの距離"""
    x = np.asarray(x, float)
    w = np.ones_like(x)
    w = np.where(x <= a0, 0.0, w); w = np.where(x >= b1, 0.0, w)
    m = (x > a0) & (x < a1); w = np.where(m, 0.5 - 0.5 * np.cos(np.pi * (x - a0) / (a1 - a0)), w)
    m = (x > b0) & (x < b1); w = np.where(m, 0.5 + 0.5 * np.cos(np.pi * (x - b0) / (b1 - b0)), w)
    return w


# ------------------------------------------------------------------ 自分の R3 の線の置き場
def save_frames(path, frames):
    """frames: dict f -> dict(main, loops[pts, phase, area])"""
    mains, moff, lpts, linfo = [], [0], [], []
    for f in range(F0, F1 + 1):
        d = frames[f]
        mains.append(d["main"]); moff.append(moff[-1] + len(d["main"]))
        for L in d["loops"]:
            linfo.append([f, sum(len(q) for q in lpts), len(L["pts"]), L["phase"], L["area"]])
            lpts.append(L["pts"])
    np.savez(path, main=np.vstack(mains), moff=np.array(moff), lpts=np.vstack(lpts) if lpts else np.zeros((0, 2)),
             linfo=np.array(linfo, float) if linfo else np.zeros((0, 5)))


class MyFrames:
    def __init__(self, path=OUT + "/my_r3_frames.npz"):
        d = np.load(path)
        self.main, self.moff, self.lpts, self.linfo = d["main"], d["moff"], d["lpts"], d["linfo"]

    def main_of(self, f):
        k = f - F0
        return self.main[self.moff[k]:self.moff[k + 1]]

    def loops_of(self, f, phase=None):
        out = []
        for r in self.linfo[self.linfo[:, 0] == f]:
            if phase is None or int(r[3]) == phase:
                out.append(dict(pts=self.lpts[int(r[1]):int(r[1]) + int(r[2])], phase=int(r[3]), area=r[4]))
        return out


def load_pairs():
    m = jload(RT + "/data/coarse/manifest.json")
    a = np.fromfile(RT + "/data/coarse/pairs.bin", dtype="<f4").reshape(570, 2, 8192, 2)
    return a, m
