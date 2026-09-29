# -*- coding: utf-8 -*-
"""設計28修正01 Houdini 経路（kstar_h）の共通部。numpy だけを使い、hython（Python 3.13）と py -3.10 の両方で読み込める。

座標の約束（この経路のすべての道具で同じ）
  Unity ワールド：左手系、Y 上、m、静水面 y = 0（K* 26修正01・GWW0・評価器の座標）。
  Houdini ワールド：右手系、Y 上、m。変換は Z の符号だけを反転する鏡映
      (x, y, z)_H = (x, y, -z)_U 、逆も同じ式（U2H = diag(1, 1, -1)、行列式 -1）。
  * 原画カメラ PaintingCam v1（Unity 位置 (0, 3, -62)、注視点 (-2.5, 9.7, 4)、縦画角 26°、1920×1080）は
    Houdini で位置 (0, 3, 62)、注視点 (-2.5, 9.7, -4) になり、Houdini のカメラの既定どおり -Z 方向を向き、
    画面の右は +X のまま（Unity の右 r と Houdini の右 r_H = U2H·r が一致する。証明は houdini_cam_axes の注）。
  * 三角形の頂点順は変えない：Unity の表（時計回り、flat sea で +Y）は鏡映で右手系の反時計回りになるが、
    Houdini の多角形の法線は時計回り（左手の規則）で計算されるので、同じ順のまま +Y を向く（kh_houdini で検査）。
  * 断面座標（K* の断面の座標系、K* 26修正01 の meta の frame）：a = 進行方向 t、y = 高さ、c = 波峰線 e。
      world_U = O + a·T + y·UP + c·E 。行＝c 一定の鉛直面。
"""
import os
import json
import math
import struct
import hashlib

import numpy as np

REPO = r"G:\Unity\GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__))
KSTAR_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
KSTAR_GWB = os.path.join(KSTAR_DIR, "kstar_a45.gwb")
KSTAR_ROWS = os.path.join(KSTAR_DIR, "kstar_a45_rows.npz")
KSTAR_META = os.path.join(KSTAR_DIR, "kstar_a45_meta.json")
LOOP2_GWB = os.path.join(REPO, "Unity", "Build", "Q20", "final", "kstarF_a45.gwb")
LOOP2_ROWS = os.path.join(REPO, "Unity", "Build", "Q20", "final", "kstarF_a45_rows.npz")
A4_GWB = os.path.join(REPO, "Unity", "Build", "Q20L3", "candA4", "kstarA4_a45.gwb")
A4_ROWS = os.path.join(REPO, "Unity", "Build", "Q20L3", "candA4", "kstarA4_a45_rows.npz")
A3B_GWB = os.path.join(REPO, "Unity", "Build", "Q20L3", "candA3b", "kstarA3b_a45.gwb")
OUT_ROOT = os.path.join(REPO, "Unity", "Build", "Q20H")
TMP = os.path.join(OUT_ROOT, "_tmp")
PLATE = os.path.join(OUT_ROOT, "plate", "painting_display_1920x1080.png")
PAINTING = os.path.join(REPO, "Docs", "References", "Met_JP1847_DP130155.jpg")
HIP_DIR = os.path.join(REPO, "Houdini", "Design28R01")
HIP_BASE = os.path.join(HIP_DIR, "kstar_h_base.hiplc")
REF_OBJ = r"G:\research\model\wave_repair_zbrush2.obj"
REF_SHA_HEAD, REF_SHA_TAIL = "AB4124F9", "3D40"
ALIGN_B = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26", "reference", "align_B_upright.json")
HYTHON = r"G:\SteamLibrary\steamapps\common\Houdini Indie\bin\hython.exe"
BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
PY310 = "py"          # py -3.10

# K* 26修正01 の断面の座標系（kstar_a45_meta.json の frame）
E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
UP = np.array([0.0, 1.0, 0.0])
H0_KSTAR = 20.752853190871733
NU, NV = 400, 240
LM = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_corner": 314, "j_facebot": 379, "j_E": 394}
LM_ORDER = ("j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E")

# PaintingCam v1（Tools/PaintingTruth/painting_truth.json、Unity の LookAt と同じ規約）
CAM_POS_U = np.array([0.0, 3.0, -62.0])
CAM_TGT_U = np.array([-2.5, 9.7, 4.0])
CAM_VFOV = 26.0
CAM_W, CAM_H = 1920, 1080
CAM_NEAR, CAM_FAR = 0.1, 900.0
HOU_APERTURE = 41.4214          # Houdini の既定の横アパーチャ（mm）。焦点距離はこれから決める

U2H = np.diag([1.0, 1.0, -1.0])


def u2h(P):
    P = np.asarray(P, np.float64)
    return P * np.array([1.0, 1.0, -1.0])


h2u = u2h   # 同じ鏡映（自分自身が逆）


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- camera
def cam_basis_unity():
    """truthlib.cam_basis と同じ式：f = normalize(tgt - pos), r = normalize(up × f), u = f × r（数値の外積）。"""
    f = CAM_TGT_U - CAM_POS_U
    f = f / np.linalg.norm(f)
    r = np.cross(UP, f)
    r = r / np.linalg.norm(r)
    u = np.cross(f, r)
    return CAM_POS_U.copy(), r, u, f


def project_unity(P):
    """gw_wavegen.PaintingCam.project と同じ：Unity ワールド → (表示 px x, y, 奥行き)。"""
    pos, r, u, f = cam_basis_unity()
    t = math.tan(math.radians(CAM_VFOV) / 2.0)
    asp = CAM_W / float(CAM_H)
    d = np.asarray(P, np.float64) - pos
    cx, cy, cz = d @ r, d @ u, d @ f
    vx = 0.5 + 0.5 * (cx / cz) / (t * asp)
    vy = 0.5 + 0.5 * (cy / cz) / t
    return np.stack([vx * CAM_W - 0.5, (1.0 - vy) * CAM_H - 0.5, cz], -1)


def houdini_cam_axes():
    """Houdini のカメラ（局所 -Z を向き、+X が画面の右、+Y が画面の上）のワールドの軸。
    鏡映 M = U2H では、直交行列について M a × M b = det(M)·M (a × b) = -M (a × b)。
    Unity の u = f × r だから f × u = -r、よって f_H × u_H = -M(f × u) = M r = r_H：右手系の右 = 鏡映した Unity の右。
    戻り値：pos_H, x_axis(=r_H), y_axis(=u_H), z_axis(=-f_H)。"""
    pos, r, u, f = cam_basis_unity()
    rH, uH, fH = U2H @ r, U2H @ u, U2H @ f
    assert np.allclose(np.cross(fH, uH), rH, atol=1e-12)
    return U2H @ pos, rH, uH, -fH


def houdini_cam_world_matrix():
    """hou.Matrix4 に渡す 4×4（Houdini の行ベクトル規約：行 0..2 = 局所軸、行 3 = 位置）。"""
    p, x, y, z = houdini_cam_axes()
    M = np.eye(4)
    M[0, :3], M[1, :3], M[2, :3], M[3, :3] = x, y, z, p
    return M


def houdini_focal_mm(aperture=HOU_APERTURE):
    """Houdini の aperture は横。tan(横半画角) = tan(縦半画角)·W/H = (aperture/2)/focal。"""
    return (aperture / 2.0) / (math.tan(math.radians(CAM_VFOV) / 2.0) * CAM_W / float(CAM_H))


def ndc_to_display(ndc):
    """Houdini の toNDC（x, y ∈ [0, 1]、y は上向き）→ 評価器の表示 px（画素中心が整数、y は下向き）。"""
    ndc = np.asarray(ndc, np.float64)
    return np.stack([ndc[:, 0] * CAM_W - 0.5, (1.0 - ndc[:, 1]) * CAM_H - 0.5], -1)


# ---------------------------------------------------------------- section frame
def sec(P):
    """Unity world (n, 3) -> (a, y, c)"""
    Q = np.atleast_2d(np.asarray(P, np.float64)) - O
    return np.stack([Q @ T, Q[:, 1], Q @ E], -1)


def world(c, A, Y):
    """rows c (nv,), A/Y (nv, nu) -> Unity world (nv, nu, 3)"""
    return O[None, None, :] + A[..., None] * T + Y[..., None] * UP + np.asarray(c, np.float64)[:, None, None] * E


def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


# ---------------------------------------------------------------- GWW0
def triangles(nu, nv):
    """gw_wavegen_v1.triangles と同じ順（K* の三角形の並び。平らな海で +Y が表）。"""
    iu, iv = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1))
    a = (iv * nu + iu).ravel()
    b = ((iv + 1) * nu + iu).ravel()
    c = (iv * nu + iu + 1).ravel()
    d = ((iv + 1) * nu + iu + 1).ravel()
    return np.stack([np.stack([a, b, c], -1), np.stack([c, b, d], -1)], 1).reshape(-1, 3).astype(np.int32)


def read_gwb(path):
    b = open(path, "rb").read()
    if b[:4] != b"GWW0":
        raise ValueError("not a GWW0 file: %s" % path)
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4")
    fps = float(np.frombuffer(b[20:24], "<f4")[0])
    tstar = int(np.frombuffer(b[24:28], "<i4")[0])
    ntri = int(np.frombuffer(b[28:32], "<i4")[0])
    n = int(nu) * int(nv)
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64); o += n * 12
    return dict(version=int(ver), nu=int(nu), nv=int(nv), frames=int(nf), fps=fps, tstar_frame=tstar,
                uv=uv, uv2=uv2, tris=tris, X=X, trailing_bytes=len(b) - o)


def write_gwb(path, nu, nv, uv, uv2, tris, X):
    with open(path, "wb") as fo:
        fo.write(b"GWW0" + struct.pack("<iiiifii", 1, nu, nv, 1, 30.0, 0, len(tris)))
        for arr in (np.asarray(uv, np.float32), np.asarray(uv2, np.float32), np.asarray(tris, np.int32),
                    np.asarray(X, np.float64).reshape(-1, 3).astype(np.float32)):
            fo.write(np.ascontiguousarray(arr).tobytes())


def write_obj(path, X, uv, tris, header):
    """gw_wavegen_v1.write_obj と同じ書式（Unity 座標のまま、m、頂点順もそのまま）。"""
    V = np.asarray(X, np.float64).reshape(-1, 3)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for h in header:
            f.write("# %s\n" % h)
        f.write("o kstar\n")
        f.write("".join("v %.6f %.6f %.6f\n" % tuple(p) for p in V))
        f.write("".join("vt %.7f %.7f\n" % tuple(t) for t in np.asarray(uv)))
        f.write("".join("f %d/%d %d/%d %d/%d\n" % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1) for a, b, c in tris))


def read_obj_unity(path):
    """v と f（三角形・多角形は扇に分割）だけを読む。座標はそのまま返す。"""
    V, F = [], []
    with open(path, "rb") as f:
        for line in f:
            if line.startswith(b"v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith(b"f "):
                idx = [int(t.split(b"/")[0]) for t in line.split()[1:]]
                idx = [i - 1 if i > 0 else len(V) + i for i in idx]
                for k in range(1, len(idx) - 1):
                    F.append([idx[0], idx[k], idx[k + 1]])
    return np.array(V, np.float64), np.array(F, np.int32)


def kstar_rows_c():
    return np.asarray(json.load(open(KSTAR_META, encoding="utf-8"))["rows"]["c_m"], np.float64)


def kstar_uv():
    """K* の UV0 / UV2（行×列の並び）。UV0 = (σ/σ_total, (c-c_min)/(c_max-c_min))、σ = 主断面 P0 の弧長。"""
    K = read_gwb(KSTAR_GWB)
    return K["uv"].reshape(K["nv"], K["nu"], 2), K["uv2"].reshape(K["nv"], K["nu"], 2)


# ---------------------------------------------------------------- slicing an arbitrary triangle mesh on row planes
class Slicer:
    """三角形メッシュ（Unity 座標）を c 一定の面で切り、各行の断面の折れ線（a, y）と点属性の補間値を返す。
    交点は辺ごとに 1 回だけ計算し（添字の小さい頂点から）、面にちょうど乗る頂点（|d| < eps）は頂点そのものを節にする。
    節は辺の番号か頂点の番号で識別するので、許容誤差なしで折れ線をつなげる。"""

    def __init__(self, Xu, tris, attrs=None, eps=1e-5):
        self.S = sec(Xu)
        self.tris = np.asarray(tris, np.int64)
        self.n = len(self.S)
        self.eps = eps
        self.attrs = {} if attrs is None else {k: np.asarray(v, np.float64).reshape(self.n, -1) for k, v in attrs.items()}
        e = np.concatenate([self.tris[:, [0, 1]], self.tris[:, [1, 2]], self.tris[:, [2, 0]]])
        e.sort(1)
        self.edges, inv = np.unique(e, axis=0, return_inverse=True)
        inv = inv.ravel()
        m = len(self.tris)
        self.tri_edges = np.stack([inv[:m], inv[m:2 * m], inv[2 * m:]], 1)      # edge ids of (01, 12, 20)
        cc = self.S[:, 2][self.tris]
        self.tri_cmin, self.tri_cmax = cc.min(1), cc.max(1)
        self.cmin, self.cmax = float(self.S[:, 2].min()), float(self.S[:, 2].max())

    def chains(self, c0):
        """面 c = c0 の断面の折れ線の一覧。各要素は dict(P=(k,2) の a,y、attr={name:(k,m)}、closed=bool)。"""
        sel = np.nonzero((self.tri_cmin <= c0 + self.eps) & (self.tri_cmax >= c0 - self.eps))[0]
        if len(sel) == 0:
            return [], {"segments": 0, "branch_nodes": 0}
        d = self.S[:, 2] - c0
        d = np.where(np.abs(d) < self.eps, 0.0, d)
        s = np.sign(d)
        tt = self.tris[sel]
        te = self.tri_edges[sel]
        st = s[tt]
        # 節の候補：頂点（s == 0）と辺（両端の符号が逆）
        vnode = st == 0                                           # (k, 3)
        pairs = ((0, 1), (1, 2), (2, 0))
        enode = np.stack([st[:, i] * st[:, j] < 0 for i, j in pairs], 1)
        cnt = vnode.sum(1) + enode.sum(1)
        use = cnt == 2                                           # 断面の線分を作る三角形（3 頂点とも面上＝面内の三角形は除く）
        tt, te, vnode, enode = tt[use], te[use], vnode[use], enode[use]
        # 節の番号：頂点 = 頂点番号、辺 = n + 辺番号
        keys = np.where(vnode, tt, -1)
        ekeys = np.where(enode, self.n + te, -1)
        allk = np.concatenate([keys, ekeys], 1)                 # (k, 6)、有効な 2 つを取り出す
        order = np.argsort(allk < 0, axis=1, kind="stable")[:, :2]
        seg = np.take_along_axis(allk, order, 1)
        seg.sort(1)
        seg = np.unique(seg, axis=0)
        seg = seg[seg[:, 0] != seg[:, 1]]
        if len(seg) == 0:
            return [], {"segments": 0, "branch_nodes": 0}
        # 節の位置と属性
        nodes = np.unique(seg)
        pos = {}
        vn = nodes[nodes < self.n]
        en = nodes[nodes >= self.n] - self.n
        P = np.zeros((len(nodes), 2))
        Aattr = {k: np.zeros((len(nodes), v.shape[1])) for k, v in self.attrs.items()}
        idx_of = {int(k): i for i, k in enumerate(nodes)}
        iv = np.array([idx_of[int(k)] for k in vn], np.int64)
        if len(vn):
            P[iv] = self.S[vn, :2]
            for k, v in self.attrs.items():
                Aattr[k][iv] = v[vn]
        if len(en):
            ie = np.array([idx_of[int(k) + self.n] for k in en], np.int64)
            i0, i1 = self.edges[en, 0], self.edges[en, 1]
            t = d[i0] / (d[i0] - d[i1])
            P[ie] = self.S[i0, :2] + t[:, None] * (self.S[i1, :2] - self.S[i0, :2])
            for k, v in self.attrs.items():
                Aattr[k][ie] = v[i0] + t[:, None] * (v[i1] - v[i0])
        # 隣接
        adj = {}
        for a_, b_ in seg:
            a_, b_ = idx_of[int(a_)], idx_of[int(b_)]
            adj.setdefault(a_, []).append(b_)
            adj.setdefault(b_, []).append(a_)
        branch = sum(1 for v in adj.values() if len(v) > 2)
        seen_e = set()
        out = []
        starts = [k for k, v in adj.items() if len(v) == 1] + [k for k, v in adj.items() if len(v) != 1]
        for st0 in starts:
            if all((min(st0, nb), max(st0, nb)) in seen_e for nb in adj[st0]):
                continue
            path = [st0]
            cur, prev = st0, None
            closed = False
            while True:
                nxt = None
                for nb in adj[cur]:
                    e = (min(cur, nb), max(cur, nb))
                    if e in seen_e:
                        continue
                    if nxt is None:
                        nxt = nb
                    elif prev is not None:
                        # 分岐：進行方向に近い方
                        dcur = P[cur] - P[prev]
                        if np.dot(P[nb] - P[cur], dcur) > np.dot(P[nxt] - P[cur], dcur):
                            nxt = nb
                if nxt is None:
                    break
                seen_e.add((min(cur, nxt), max(cur, nxt)))
                path.append(nxt)
                prev, cur = cur, nxt
                if cur == st0:
                    closed = True
                    break
            if len(path) >= 2:
                ii = np.array(path)
                out.append({"P": P[ii], "attr": {k: v[ii] for k, v in Aattr.items()}, "closed": closed})
        return out, {"segments": int(len(seg)), "branch_nodes": int(branch)}


def dedupe_polyline(P, attr, tol=1e-9):
    ds = np.hypot(*np.diff(P, axis=0).T)
    keep = np.r_[True, ds > tol]
    return P[keep], {k: v[keep] for k, v in attr.items()}


# ---------------------------------------------------------------- landmarks and resampling
def geometric_landmarks(a, y, eps_y=0.02):
    """列の目印を形から決める（col 属性がないときの代わり。候補 A4 の定義）。戻り値は弧長の位置（m）と警告。
      j_B      背の平らな海が終わる所（後ろから見て |y| > eps_y になる最初の点）
      j_top    頂（最も高い点）
      j_tip    唇先：頂の後で y > 0.25H が続く間の、0.3 m で平滑した曲率が最大の点（丸い先の頂点）
      j_corner 管の最も後ろの点（唇先の後、y > 0 の間の a 最小）
      j_facebot 前の谷の底（管の後の y 最小。谷がなければ y が eps_y 以下になる最初の点）
      j_E      前の平らな海が始まる所（前から見て |y| > eps_y になる最初の点）"""
    s = arclen(a, y)
    warn = []
    H = float(y.max())
    if H < 0.05:
        return None, ["flat row"]
    nz = np.nonzero(np.abs(y) > eps_y)[0]
    iB = max(int(nz[0]) - 1, 0)
    iE = min(int(nz[-1]) + 1, len(a) - 1)
    itop = int(np.argmax(y))
    st = 0.05
    ss = np.arange(0.0, s[-1], st)
    aa = np.interp(ss, s, a); yy = np.interp(ss, s, y)
    k = max(int(round(0.3 / st)), 1)
    ker = np.exp(-0.5 * (np.arange(-4 * k, 4 * k + 1) / float(k)) ** 2); ker /= ker.sum()
    xa = np.convolve(np.pad(aa, 4 * k, mode="edge"), ker, "valid"); xy = np.convolve(np.pad(yy, 4 * k, mode="edge"), ker, "valid")
    dx, dy = np.gradient(xa), np.gradient(xy); ddx, ddy = np.gradient(dx), np.gradient(dy)
    kap = np.abs(dx * ddy - dy * ddx) / np.maximum((dx * dx + dy * dy) ** 1.5, 1e-12) / st
    jt = int(np.searchsorted(ss, s[itop]))
    run = jt
    while run + 1 < len(ss) and yy[run + 1] > 0.25 * H:
        run += 1
    if run - jt < 4:
        warn.append("no lip run")
        s_tip = s[itop] + 0.25 * (s[iE] - s[itop])
    else:
        lo = jt + max(int(round(0.5 / st)), 1)
        s_tip = ss[lo + int(np.argmax(kap[lo:run + 1]))] if run + 1 > lo else ss[run]
    itip = int(np.searchsorted(s, s_tip))
    after = np.arange(itip, iE + 1)
    pos = after[y[after] > 0]
    icor = int(pos[np.argmin(a[pos])]) if len(pos) else itip + 1
    rest = np.arange(icor, iE + 1)
    ifb = int(rest[np.argmin(y[rest])]) if len(rest) else icor + 1
    s_fb = s[ifb]
    if y[ifb] > -eps_y:
        # 谷がない（K* のような台座の足）：管と前の海の間で曲率が最大の点（足の角）
        warn.append("no front trough")
        a0 = int(np.searchsorted(ss, s[icor] + 0.5)); a1 = int(np.searchsorted(ss, s[iE] - 0.3))
        s_fb = ss[a0 + int(np.argmax(kap[a0:a1]))] if a1 > a0 + 1 else 0.5 * (s[icor] + s[iE])
    L = {"j_B": s[iB], "j_top": s[itop], "j_tip": s_tip, "j_corner": s[icor], "j_facebot": s_fb, "j_E": s[iE]}
    # 順序を保つ（最小の間隔 0.02 m。弧長の端を越えない）
    prev = 0.0
    for k in LM_ORDER:
        if L[k] < prev + 0.02:
            warn.append("landmark %s moved to keep the order" % k)
            L[k] = prev + 0.02
        prev = L[k]
    top = s[-1] - 0.02 * (len(LM_ORDER) + 1)
    if prev > s[-1] - 0.02:
        for i, k in enumerate(LM_ORDER):
            L[k] = min(L[k], top + 0.02 * (i + 1))
    return L, warn


def attr_landmarks(s, col):
    """col 属性の値が 18, 90, 200, 314, 379, 394 になる弧長の位置。col は単調に増えるように整える。"""
    cm = np.maximum.accumulate(col)
    nonmono = float(np.max(cm - col))
    L = {k: float(np.interp(v, cm + np.arange(len(cm)) * 1e-9, s)) for k, v in LM.items()}
    return L, nonmono


def resample_landmarks(s, a, y, L, nu=NU):
    """目印の間を弧長で等分して 400 列に置く（候補 A4 と同じ規則：7 区間それぞれ一様）。"""
    knots_col = [0] + [LM[k] for k in LM_ORDER] + [nu - 1]
    knots_s = [s[0]] + [L[k] for k in LM_ORDER] + [s[-1]]
    ks = np.maximum.accumulate(np.array(knots_s, float))
    st = np.empty(nu)
    for i in range(len(knots_col) - 1):
        j0, j1 = knots_col[i], knots_col[i + 1]
        st[j0:j1 + 1] = np.linspace(ks[i], ks[i + 1], j1 - j0 + 1)
    return np.interp(st, s, a), np.interp(st, s, y), st


def resample_attr_cols(s, a, y, col, nu=NU):
    """col 属性の値が 0..399 になる位置に各列を置く（トポロジーを保った編集なら元の格子をそのまま再現する）。"""
    cm = np.maximum.accumulate(col)
    nonmono = float(np.max(cm - col))
    x = cm + np.arange(len(cm)) * 1e-9
    tgt = np.arange(nu, dtype=float)
    st = np.interp(tgt, x, s)
    lo_miss = float(max(cm[0] - 0.0, 0.0)); hi_miss = float(max((nu - 1) - cm[-1], 0.0))
    return np.interp(st, s, a), np.interp(st, s, y), st, nonmono, (lo_miss, hi_miss)


def pick_main_chain(chains):
    """いちばん長い開いた折れ線（背の海から前の海まで）を選ぶ。"""
    if not chains:
        return None, 0.0
    lens = [float(arclen(ch["P"][:, 0], ch["P"][:, 1])[-1]) for ch in chains]
    i = int(np.argmax(lens))
    other = float(sum(lens) - lens[i])
    return chains[i], other


def orient_back_to_front(ch):
    P = ch["P"]
    if "col" in ch["attr"]:
        rev = ch["attr"]["col"][0, 0] > ch["attr"]["col"][-1, 0]
    else:
        rev = P[0, 0] > P[-1, 0]
    if rev:
        return {"P": P[::-1].copy(), "attr": {k: v[::-1].copy() for k, v in ch["attr"].items()}, "closed": ch["closed"]}
    return ch


def grid_from_mesh(Xu, tris, attrs, c_rows, columns="auto", log=print):
    """任意の三角形メッシュ（Unity 座標、行の面を横切る 1 枚の面）→ 400 列 × len(c_rows) 行の格子 (A, Y)。
    columns: 'attr'（col 属性の 0..399 の位置）、'landmark'（目印は col 属性、目印の間は弧長で等分）、
             'geometric'（目印も形から）、'auto'（col 属性があれば attr、なければ geometric）。"""
    has_col = attrs is not None and "col" in attrs
    if columns == "auto":
        columns = "attr" if has_col else "geometric"
    if columns in ("attr", "landmark") and not has_col:
        raise ValueError("columns=%s needs the point attribute 'col'" % columns)
    sl = Slicer(Xu, tris, attrs)
    nv = len(c_rows)
    A = np.zeros((nv, NU)); Y = np.zeros((nv, NU))
    rep = []
    Lrow = [None] * nv
    for r, c0 in enumerate(c_rows):
        cc = float(np.clip(c0, sl.cmin, sl.cmax))        # 端の行はちょうど縁の上で切る（面上の頂点を節にするので切れる）
        chains, st = sl.chains(cc)
        ch, other = pick_main_chain([x for x in chains if not x["closed"]])
        info = {"row": r, "c": float(c0), "c_sliced": cc, "chains": len(chains), "closed_chains": int(sum(x["closed"] for x in chains)),
                "other_chain_length_m": round(other, 4), "branch_nodes": st["branch_nodes"], "warn": []}
        if abs(cc - c0) > 1e-3:
            info["warn"].append("row plane outside the mesh (clamped by %.3f m)" % (cc - c0))
        if ch is None:
            info["warn"].append("no open section chain")
            rep.append(info)
            continue
        ch = orient_back_to_front(ch)
        P, at = dedupe_polyline(ch["P"], ch["attr"])
        a, y = P[:, 0], P[:, 1]
        s = arclen(a, y)
        if columns == "attr":
            A[r], Y[r], st_, nonmono, miss = resample_attr_cols(s, a, y, at["col"][:, 0])
            if nonmono > 1e-3:
                info["warn"].append("col attribute not monotonic along the section (by %.3f)" % nonmono)
            if max(miss) > 1e-3:
                info["warn"].append("section does not reach col 0 / 399 (missing %.3f / %.3f cols)" % miss)
            info["col_range"] = [float(at["col"][0, 0]), float(at["col"][-1, 0])]
            Lrow[r] = "attr"
        else:
            if columns == "landmark":
                L, nonmono = attr_landmarks(s, at["col"][:, 0])
                if nonmono > 1e-3:
                    info["warn"].append("col attribute not monotonic (by %.3f)" % nonmono)
            else:
                L, w = geometric_landmarks(a, y)
                info["warn"] += w
            if L is None:
                Lrow[r] = ("flat", a[0], a[-1], s)
                info["warn"].pop(-1) if info["warn"] and info["warn"][-1] == "flat row" else None
                A[r] = np.interp(np.linspace(0, s[-1], NU), s, a)
                Y[r] = np.interp(np.linspace(0, s[-1], NU), s, y)
            else:
                vals = [L[k] for k in LM_ORDER]
                if any(np.diff(vals) <= 0):
                    info["warn"].append("landmarks out of order: %s" % [round(v, 2) for v in vals])
                A[r], Y[r], _ = resample_landmarks(s, a, y, L)
                Lrow[r] = L
        rep.append(info)
    # 形のない行（平らな海）は、目印の近い行の列の a を使う（geometric / landmark のとき）
    ok = [i for i, L in enumerate(Lrow) if isinstance(L, dict) or L == "attr"]
    for r, L in enumerate(Lrow):
        if isinstance(L, tuple) and L[0] == "flat" and ok:
            rr = min(ok, key=lambda i: abs(i - r))
            a0, a1 = L[1], L[2]
            A[r] = np.clip(A[rr], a0, a1)
            A[r] = np.maximum.accumulate(A[r])
            Y[r] = 0.0
            rep[r]["warn"].append("flat row: columns copied from row %d" % rr)
        elif L is None and ok:
            rr = min(ok, key=lambda i: abs(i - r))
            A[r] = A[rr]; Y[r] = 0.0
            rep[r]["warn"].append("no section: flat sea row, columns copied from row %d" % rr)
    return A, Y, rep, columns


def row_landmarks(A, Y):
    """出力の各行の目印の列（固定の 18/90/200/314/379/394）と、確かめ用の頂（argmax y）の列。"""
    top = np.array([int(np.argmax(Y[r, :LM["j_tip"]])) for r in range(len(A))])
    return {"top_argmax_col": top}


def write_candidate(prefix, c, A, Y, provenance, uv_mode="kstar"):
    """rows npz + GWW0 + OBJ（Unity 座標）+ meta json を書く。三角形は K* と同じ並び。"""
    nv, nu = A.shape
    tris = triangles(nu, nv)
    X = world(c, A, Y)
    main = int(np.argmin(np.abs(c)))
    if uv_mode == "kstar" and nv == NV and nu == NU:
        uvk, uv2k = kstar_uv()
        uv = uvk.reshape(-1, 2)
        uv2 = np.stack([uv2k[..., 0], np.broadcast_to(c[:, None], (nv, nu))], -1).reshape(-1, 2)
        uv_note = "UV0 = K* の UV0 をそのまま（列 → σ/σ_total、行 → v）。UV2 = (K* の σ [m], この候補の行の c [m])。"
    else:
        sig = arclen(A[main], Y[main])
        U = sig / sig[-1]; V = (c - c.min()) / (c.max() - c.min())
        uv = np.stack(np.meshgrid(U, V), -1).reshape(-1, 2)
        uv2 = np.stack(np.meshgrid(sig, c), -1).reshape(-1, 2)
        uv_note = "UV0 = (この候補の主断面（c = 0 の行）の弧長 σ/σ_total, (c-c_min)/(c_max-c_min))、UV2 = (σ [m], c [m])（候補 A と同じ）。"
    gwb = prefix + ".gwb"
    write_gwb(gwb, nu, nv, uv, uv2, tris, X)
    obj = prefix + ".obj"
    write_obj(obj, X, uv, tris, ["kstar_h bridge output %s, Unity world coordinates (left-handed, Y up, metres)" % os.path.basename(prefix),
                                 "rows = constant-c planes of the K* 26R01 section frame; columns 0..399 with landmarks %s" % json.dumps(LM)])
    V3 = X.reshape(-1, 3)
    p0, p1, p2 = V3[tris[:, 0]], V3[tris[:, 1]], V3[tris[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0)
    area = 0.5 * np.linalg.norm(fn, axis=1)
    flat = (np.abs(p0[:, 1]) < 1e-6) & (np.abs(p1[:, 1]) < 1e-6) & (np.abs(p2[:, 1]) < 1e-6)
    lmk = row_landmarks(A, Y)
    np.savez_compressed(prefix + "_rows.npz", A=A, Y=Y, c=c, P=np.stack([A[main], Y[main]], -1),
                        top_argmax_col=lmk["top_argmax_col"])
    H = Y.max(1)
    km = json.load(open(KSTAR_META, encoding="utf-8"))
    meta = {"schema": "GreatWave.GWWaveGen.kstar_meta/1", "generator": "Tools/GWWaveGen/kstar_h (Houdini bridge)",
            "key": "a45", "nu": nu, "nv": nv, "vertex_count": int(nu * nv), "triangle_count": int(len(tris)),
            "files": {"gwb": os.path.basename(gwb), "gwb_sha256": sha256(gwb), "gwb_bytes": os.path.getsize(gwb),
                      "obj": os.path.basename(obj), "obj_sha256": sha256(obj), "rows": os.path.basename(prefix + "_rows.npz")},
            "format_ja": km["format_ja"], "uv_layout_ja": uv_note, "frame": km["frame"],
            "profile": {"index": dict(LM, main_row=main)},
            "rows": {"c_m": [round(float(x), 6) for x in c], "main_row": main, "H_m": [round(float(x), 4) for x in H]},
            "H0_m": float(H[main]), "highest_point": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])},
            "checks": {"nan": int((~np.isfinite(V3)).sum()), "degenerate_triangles_area_lt_1e-6_m2": int((area < 1e-6).sum()),
                       "min_triangle_area_m2": float(area.min()), "flat_sea_triangles_facing_down": int((flat & (fn[:, 1] < 0)).sum()),
                       "topology_same_as_kstar": bool(nu == NU and nv == NV)},
            "provenance": provenance}
    json.dump(meta, open(prefix + "_meta.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return meta
