# -*- coding: utf-8 -*-
"""RT48 の焼きと確かめで共通に使う部品（py -3.10、numpy・scipy・scikit-image）。読み方は Unity/Build/RT48/record_ja.md と
Unity/Build/RT48/data/record_ja.md の「読み方」のとおり。R3 のファイルは開いて読むだけ。

座標：x_rel＝造波板からの距離（場面の x − x_p）、y＝静かな水面からの高さ（解く格子の y − 静かな水面のずれ）。
焼きのファイルの X＝x_rel − 527.0（最初の接触の所。float32 の刻みを小さくするため）、Y＝y。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 数値の部品のスレッドの予約（1 つの起動で約 0.6 GB）を小さくする
    _os.environ.setdefault(_v, "1")
import os, sys, json, glob
import numpy as np
from scipy.spatial import cKDTree
from skimage import measure

XP = 135.46329754326246          # 造波板の場面の x（R3 cfg）
OFF_R3 = 0.116838239133358       # R3 の静かな水面のずれ（shape.json still_level_offset_m）
FPS = 24.0
X0_BAKE = 527.0                  # 焼きの X の原点（x_rel）
N_PTS = 8192
WIN = (100.0, 925.0)
F0, F1 = 3319, 3889
SEATS = (556.0, 574.0)
HULL = 12.0
CREST_START = 261.53670245673754  # 3319 コマの巻く頂（plan_numbers.json view_at_boat.plunging_crest_before_141s）
SEARCH = 40.0                    # 頂を探す幅（前のコマの頂から ±）
WIN_I = 30.0                     # 補間の窓（頂から ±）
WIN_C2 = 20.0                    # C2 (c) の窓
VOX = 0.5                        # 解く格子
R3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:   # 手元の作業（ゲームなど）を邪魔しないように、この道具の計算は優先度「通常より下」で走らせる
    import ctypes
    _k = ctypes.windll.kernel32
    _k.GetCurrentProcess.restype = ctypes.c_void_p
    _k.SetPriorityClass(ctypes.c_void_p(_k.GetCurrentProcess()), 0x00004000)
except Exception:
    pass


def t_of(f):
    return (f - 1) / FPS


# ------------------------------------------------------------------ 記録の読み込み
class Records:
    """hf と sec の記録。同じコマが二つの起動にある時は、始めが最も遅い起動の記録を使う（計画 §2.1。C1 (a) で同じと確かめた）。"""

    def __init__(self, rd):
        self.rd = rd
        self.sec_idx, self.hf_idx = {}, {}
        for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
            b = os.path.basename(p); c0 = int(b[5:9])
            for i, f in enumerate(np.load(p)["frames"]):
                f = int(f)
                if f not in self.sec_idx or self.sec_idx[f][0] < c0:
                    self.sec_idx[f] = (c0, p.replace("\\", "/"), i)
        for p in glob.glob(os.path.join(rd, "hf_c*.npz")):
            c0 = int(os.path.basename(p)[4:8])
            for i, f in enumerate(np.load(p)["frames"]):
                f = int(f)
                if f not in self.hf_idx or self.hf_idx[f][0] < c0:
                    self.hf_idx[f] = (c0, p.replace("\\", "/"), i)
        self._c = {}
        self.used = set()

    def _arr(self, p, key):
        if (p, key) not in self._c:
            if len(self._c) > 4:
                self._c.clear()
            d = np.load(p)
            self._c[(p, key)] = (d[key], d["meta"] if key == "sdf" else None, d["x"] if key == "eta" else None)
            self.used.add(p)
        return self._c[(p, key)]

    def sec(self, f, off):
        c0, p, i = self.sec_idx[f]
        a, meta, _ = self._arr(p, "sdf")
        m = json.loads(str(meta))
        xs = m["x0"] + m["dx"] * np.arange(m["nx"]) - XP
        ys = m["y0"] + m["dy"] * np.arange(m["ny"]) - off
        return a[i].astype(np.float32), xs, ys, m

    def hf(self, f, off):
        c0, p, i = self._hfi(f)
        a, _, x = self._arr(p, "eta")
        return a[i][2].astype(np.float64) - off, x - XP        # 板の真ん中（z = 0）の節

    def _hfi(self, f):
        return self.hf_idx[f]


# ------------------------------------------------------------------ 等高線と閉じた線
def _pip(px, py, poly):
    """点（配列）が多角形の中か（偶奇）"""
    x, y = poly[:, 0], poly[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    inside = np.zeros(len(px), bool)
    for a, b, c, d in zip(x, y, x2, y2):
        cond = ((b > py) != (d > py))
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = a + (py - b) * (c - a) / (d - b)
        inside ^= cond & (px < xi)
    return inside


def loop_phase(c_rc, S):
    """閉じた線（行・列の座標）の内側が水（-1）か空気（+1）か。線の頂点が乗る格子の辺の両端の節のうち、多角形の中にある節の符号の多数決。"""
    n = len(c_rc) - 1
    idx = np.unique(np.linspace(0, n - 1, min(n, 9)).astype(int))
    votes = []
    for k in idx:
        r, c = c_rc[k]
        if abs(r - round(r)) < 1e-9:
            nodes = [(int(round(r)), int(np.floor(c))), (int(round(r)), int(np.ceil(c)))]
        else:
            nodes = [(int(np.floor(r)), int(round(c))), (int(np.ceil(r)), int(round(c)))]
        nodes = [q for q in nodes if 0 <= q[0] < S.shape[0] and 0 <= q[1] < S.shape[1]]
        if len(nodes) < 2 or nodes[0] == nodes[1]:
            continue
        pr = np.array([q[0] for q in nodes], float); pc = np.array([q[1] for q in nodes], float)
        ins = _pip(pc, pr, c_rc[:, ::-1])
        if ins.sum() == 1:
            q = nodes[int(np.argmax(ins))]
            votes.append(-1 if S[q] < 0 else 1)
    if not votes:
        return 0
    return -1 if sum(votes) < 0 else 1


def poly_area(l):
    x, y = l[:, 0], l[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def field_curves(S, xs, ys, y_min=None):
    """場 S（行＝y、列＝x）の 0 の等高線。返り値：open（開いた線の一覧、各 (n,2) の x,y）、loops（閉じた線：dict(pts, phase, area)）"""
    j0 = 0 if y_min is None else int(np.searchsorted(ys, y_min))
    S2 = S[j0:]
    dx = xs[1] - xs[0]; dy = ys[1] - ys[0]
    opn, loops = [], []
    for c in measure.find_contours(S2, 0.0):
        P = np.stack([xs[0] + c[:, 1] * dx, ys[j0] + c[:, 0] * dy], 1)
        if len(c) > 2 and np.allclose(c[0], c[-1]):
            ph = loop_phase(c, S2)
            loops.append(dict(pts=P, phase=int(ph), area=float(poly_area(P))))
        else:
            opn.append(P)
    return opn, loops


def pick_main(opn, x_left, x_right, tol=1e-6):
    """左の端から右の端まで続く開いた線（x の増える向きにそろえる）。"""
    ext = [l[:, 0].max() - l[:, 0].min() for l in opn]
    k = int(np.argmax(ext))
    m = opn[k]
    if m[0, 0] > m[-1, 0]:
        m = m[::-1]
    ok = abs(m[0, 0] - x_left) < 1e-3 and abs(m[-1, 0] - x_right) < 1e-3
    others = [opn[i] for i in range(len(opn)) if i != k]
    return m, ok, others


def coarse_frame(rec, f, off=OFF_R3):
    """粗い元の 1 コマ：断面の範囲は sec の 0 の等高線、外は一番上の水面（hf の z = 0 の節）。"""
    S, xs, ys, m = rec.sec(f, off)
    opn, loops = field_curves(S, xs, ys, y_min=-25.0)
    main_in, ok, others = pick_main(opn, xs[0], xs[-1])
    eh, xh = rec.hf(f, off)
    L = (xh >= WIN[0] - 1e-9) & (xh < xs[0] - 1e-6)
    Rr = (xh > xs[-1] + 1e-6) & (xh <= WIN[1] + 1e-9)
    left = np.stack([xh[L], eh[L]], 1); right = np.stack([xh[Rr], eh[Rr]], 1)
    i0 = int(np.argmin(abs(xh - xs[0]))); i1 = int(np.argmin(abs(xh - xs[-1])))
    stitch = [float(main_in[0, 1] - eh[i0]), float(main_in[-1, 1] - eh[i1])]
    main = np.concatenate([left, main_in, right], 0)
    return dict(main=main, loops=loops, main_ok=ok, other_open=len(others), stitch=stitch, field=(S, xs, ys))


# ------------------------------------------------------------------ 頂・目印
def crest_in(main, xc_prev, half=SEARCH):
    m = (main[:, 0] >= xc_prev - half) & (main[:, 0] <= xc_prev + half)
    idx = np.where(m)[0]
    i = int(idx[np.argmax(main[idx, 1])])
    return i


def lip_tip(main, ic, xc, half=WIN_I, back=VOX):
    """頂から前へ（番号の増える向き）たどり、x が初めて極大になり、その後 back 以上戻る点（FLIP42 g_shape.py の唇の先と同じ決め方）。窓の中だけ。"""
    xx = main[:, 0]
    n = len(xx)
    i = ic + 1
    while i < n - 1 and xx[i] <= xc + half:
        if xx[i] >= xx[i - 1] and xx[i] > xx[i + 1]:
            j = i + 1
            while j < n and xx[j] <= xx[i]:
                j += 1
            if xx[i] - xx[i:j].min() >= back:
                return i
        i += 1
    return None


def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])


def at_s(P, s, q):
    """弧長 q の点（線形）"""
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], 1)


def split_counts(Lavg, total):
    w = np.asarray(Lavg, float)
    raw = total * w / w.sum()
    n = np.maximum(1, np.floor(raw).astype(int))
    while n.sum() < total:
        n[int(np.argmax(raw - n))] += 1
    while n.sum() > total:
        k = int(np.argmax(n - raw)); n[k] -= 1
    return n


def resample_pair(Pa, la, Pb, lb, N=N_PTS):
    """目印で区切った区間ごとに、二つのコマそれぞれの弧長で等しく点を置く（区間の点の数は二つの区間の長さの平均で割り振る）。
    la・lb は目印の頂点の番号（同じ数・同じ順）。返り値：A、B（各 (N,2)）、目印の点の番号。"""
    sa, sb = arclen(Pa), arclen(Pb)
    ka = [0.0] + [sa[i] for i in la] + [sa[-1]]
    kb = [0.0] + [sb[i] for i in lb] + [sb[-1]]
    Lavg = [0.5 * ((ka[j + 1] - ka[j]) + (kb[j + 1] - kb[j])) for j in range(len(ka) - 1)]
    n = split_counts(Lavg, N - 1)
    qa, qb, marks = [], [], []
    pos = 0
    for j in range(len(n)):
        ua = np.linspace(ka[j], ka[j + 1], n[j] + 1)
        ub = np.linspace(kb[j], kb[j + 1], n[j] + 1)
        if j > 0:
            ua = ua[1:]; ub = ub[1:]
        qa.append(ua); qb.append(ub)
        pos += n[j]
        if j < len(n) - 1:
            marks.append(pos)
    qa = np.concatenate(qa); qb = np.concatenate(qb)
    return at_s(Pa, sa, qa), at_s(Pb, sb, qb), marks


def resample_uniform(P, N=N_PTS):
    s = arclen(P)
    return at_s(P, s, np.linspace(0, s[-1], N))


def densify(P, h):
    s = arclen(P)
    n = max(2, int(np.ceil(s[-1] / h)) + 1)
    return at_s(P, s, np.linspace(0, s[-1], n))


def dist_to_curve(Pts, Q, h=0.005):
    """点 Pts から折れ線 Q までの距離（Q を h で細かくして最も近い点。上に h/2 まで多く出る）"""
    T = cKDTree(densify(Q, h))
    return T.query(Pts)[0]


def two_way(P, Q, h=0.005, win=None):
    """二つの折れ線の両向きの距離（P の点を h で細かくした物から Q へ、と逆）。win=(x0,x1) なら x がその中の点だけ"""
    Pd, Qd = densify(P, h), densify(Q, h)
    if win is not None:
        Pd = Pd[(Pd[:, 0] >= win[0]) & (Pd[:, 0] <= win[1])]
        Qd = Qd[(Qd[:, 0] >= win[0]) & (Qd[:, 0] <= win[1])]
    d1 = cKDTree(Qd).query(Pd)[0] if len(Pd) and len(Qd) else np.zeros(0)
    d2 = cKDTree(Pd).query(Qd)[0] if len(Pd) and len(Qd) else np.zeros(0)
    return d1, d2


def seg_intersect_any(P, win):
    """窓の中の線分（端の点の一つでも x が窓の中）どうしが、隣り合う物を除いて交わるか（触れるのも交わりと数える）。交わった組の数を返す。"""
    m = (P[:-1, 0] >= win[0]) & (P[:-1, 0] <= win[1]) | (P[1:, 0] >= win[0]) & (P[1:, 0] <= win[1])
    idx = np.where(m)[0]
    if len(idx) < 3:
        return 0
    A = P[idx]; B = P[idx + 1]
    n = len(idx)
    cnt = 0
    blk = 1024
    for s0 in range(0, n, blk):
        a = A[s0:s0 + blk, None, :]; b = B[s0:s0 + blk, None, :]
        c = A[None, :, :]; d = B[None, :, :]

        def orient(p, q, r):
            return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
        o1 = orient(a, b, c); o2 = orient(a, b, d); o3 = orient(c, d, a); o4 = orient(c, d, b)
        hit = (o1 * o2 <= 0) & (o3 * o4 <= 0)
        # 並んだ（同じ直線の上の）線分の誤判定を除く：外接の箱が重ならなければ交わらない
        bx = (np.minimum(a[..., 0], b[..., 0]) <= np.maximum(c[..., 0], d[..., 0])) & (np.minimum(c[..., 0], d[..., 0]) <= np.maximum(a[..., 0], b[..., 0]))
        by = (np.minimum(a[..., 1], b[..., 1]) <= np.maximum(c[..., 1], d[..., 1])) & (np.minimum(c[..., 1], d[..., 1]) <= np.maximum(a[..., 1], b[..., 1]))
        hit &= bx & by
        ii = idx[s0:s0 + blk][:, None]; jj = idx[None, :]
        hit &= np.abs(ii - jj) > 1
        cnt += int((hit & (jj > ii)).sum())
    return cnt


def monotone_outside(P, win):
    """窓の外で、線に沿って x が増え続けるか（減る・同じになる点の数を返す）"""
    dx = np.diff(P[:, 0])
    out = ~(((P[:-1, 0] >= win[0]) & (P[:-1, 0] <= win[1])) | ((P[1:, 0] >= win[0]) & (P[1:, 0] <= win[1])))
    return int(((dx <= 0) & out).sum())


# ------------------------------------------------------------------ 船
def crossings(P, xq):
    x0, x1 = P[:-1, 0], P[1:, 0]
    k = np.where(((x0 - xq) * (x1 - xq) <= 0) & (x0 != x1))[0]
    w = (xq - x0[k]) / (x1[k] - x0[k])
    return P[k, 1] + w * (P[k + 1, 1] - P[k, 1])


def boat(P, xb, hull=HULL):
    """船体の 9 点（±6 m）の一番上の水面の平均（上下）と最小二乗の傾き（縦揺れ、度。+x へ上る時を正）"""
    hx = np.linspace(-hull / 2, hull / 2, 9)
    yy = np.array([crossings(P, xb + h).max() for h in hx])
    return float(yy.mean()), float(np.degrees(np.arctan(np.polyfit(hx, yy, 1)[0]))), yy


def multivalued_cols(S, xs, ys, y_min=-10.0):
    """読み方 1：静かな水面から 10 m 下より上に、水と空気の入れ替わりが 2 回以上ある列の x"""
    j0 = int(np.searchsorted(ys, y_min))
    sub = (S[j0:] < 0)
    ch = np.abs(np.diff(sub.astype(np.int8), axis=0)).sum(0)
    return xs[ch > 1]
