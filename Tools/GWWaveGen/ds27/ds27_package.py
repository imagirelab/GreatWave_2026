# -*- coding: utf-8 -*-
"""設計27：DS27 keypose パッケージの読み込みと再生（関門の検査と組み立てが import する小さな API）。

パッケージ（生成器 ds27_generate.py と再生側の約束。Unity/Build/Design/27/<版>/、版は art_on・art_off）：
  ds27_pos_rgba16.bin  RGBA16 UNORM、層 × 行(240) × 列(400) × 4。xyz は外接箱で正規化（位置 = bbox_min + q/65535·bbox_size）、A = 65535。
                       位置は波の枠の局所座標 = ワールド − O(τ)（O は波の枠の原点。平行移動だけ、軸はワールドの軸）。
  ds27_keypose.json    layers・rows・cols・bbox_min・bbox_size・knot_tau（秒、狭義単調増加、最後 = 0.0 = t*）・
                       frame{tau, origin}（480 Hz、線形補間）・pos_sha256・twhite_file・twhite_sha256（ほかは記録）
  ds27_twhite_r32f.bin R32F 行 × 列、T_white（τ の秒）。τ ≥ T_white で白、+1e9 は t* まで白くならない。
補間：節点 i と i+1 の間の τ の 3 次 Hermite。傾き m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})（端は片側）。範囲の外は端の層。

API：
    from ds27_package import load_package, evaluate, Package
    knot_tau, P, origin = load_package("art_on")   # P：float64 [L, 240, 400, 3]（局所）、origin(τ) → (3,) ワールド
    X = evaluate(-1.0, knot_tau, P)                # (240, 400, 3) 局所（Hermite）
    pk = Package("art_on"); W = pk.world(-1.0)     # ワールド = origin(τ) + 局所。pk.twhite は (240, 400) float64
numpy だけを使う。
"""
import hashlib
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_ROOT = os.path.join(REPO, "Unity", "Build", "Design", "27")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hermite_weights(knots, tau):
    """τ の補間に使う 4 つの層の添字と重み（非一様の節点の Hermite、傾きは中心差分、端は片側）。範囲の外は端の層。
    美術優先30 の af30_formation.cr_weights、再生側（ds27_player_ref.hermite_weights・Unity）と同じ式。"""
    n = len(knots)
    if tau <= knots[0]:
        return (0, 0, 0, 0), (0.0, 1.0, 0.0, 0.0)
    if tau >= knots[-1]:
        return (n - 1, n - 1, n - 1, n - 1), (0.0, 1.0, 0.0, 0.0)
    i1 = int(np.searchsorted(knots, tau, side="right") - 1)
    i1 = min(i1, n - 2)
    i2 = i1 + 1
    i0 = max(i1 - 1, 0)
    i3 = min(i2 + 1, n - 1)
    t1, t2 = knots[i1], knots[i2]
    D = t2 - t1
    s = (tau - t1) / D
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    w = np.zeros(4)
    w[1] += h00
    w[2] += h01
    if i0 == i1:
        w[2] += h10
        w[1] -= h10
    else:
        f = h10 * D / (t2 - knots[i0])
        w[2] += f
        w[0] -= f
    if i3 == i2:
        w[2] += h11
        w[1] -= h11
    else:
        f = h11 * D / (knots[i3] - t1)
        w[3] += f
        w[1] -= f
    return (i0, i1, i2, i3), tuple(float(v) for v in w)


def evaluate(tau, knot_tau, positions):
    """局所座標の Hermite の再生（(rows, cols, 3)）。"""
    idx, w = hermite_weights(np.asarray(knot_tau, np.float64), float(tau))
    out = np.zeros(positions.shape[1:], np.float64)
    for q in range(4):
        if w[q] != 0.0:
            out += w[q] * positions[idx[q]]
    return out


def package_dir(version, root=None):
    return os.path.join(root or OUT_ROOT, version)


class Package:
    def __init__(self, version="art_on", root=None, check=True):
        self.dir = version if os.path.isdir(str(version)) else package_dir(version, root)
        self.meta = json.load(open(os.path.join(self.dir, "ds27_keypose.json"), encoding="utf-8"))
        M = self.meta
        L, nv, nu = int(M["layers"]), int(M["rows"]), int(M["cols"])
        pp = os.path.join(self.dir, M.get("pos_file", "ds27_pos_rgba16.bin"))
        if check and _sha256(pp) != M["pos_sha256"]:
            raise SystemExit("[ds27_package] 位置のファイルの SHA-256 が ds27_keypose.json と違います")
        q = np.fromfile(pp, "<u2").reshape(L, nv, nu, 4)
        lo = np.asarray(M["bbox_min"], np.float64)
        size = np.asarray(M["bbox_size"], np.float64)
        self.knot_tau = np.asarray(M["knot_tau"], np.float64)
        self.positions = lo + q[..., :3].astype(np.float64) / 65535.0 * size
        tp = os.path.join(self.dir, M["twhite_file"])
        if check and _sha256(tp) != M["twhite_sha256"]:
            raise SystemExit("[ds27_package] T_white のファイルの SHA-256 が ds27_keypose.json と違います")
        self.twhite = np.fromfile(tp, "<f4").astype(np.float64).reshape(nv, nu)
        self.ftau = np.asarray(M["frame"]["tau"], np.float64)
        self.forg = np.asarray(M["frame"]["origin"], np.float64)

    def origin(self, tau):
        """波の枠の原点（ワールド、(3,)）。表の間は線形、範囲の外は端の標本。"""
        return np.array([np.interp(float(tau), self.ftau, self.forg[:, k]) for k in range(3)])

    def local(self, tau):
        return evaluate(tau, self.knot_tau, self.positions)

    def world(self, tau):
        return self.local(tau) + self.origin(tau)[None, None, :]


def load_package(version="art_on", root=None):
    """(knot_tau, positions float64 [L, 240, 400, 3] 局所, origin(τ) → (3,) ワールド) を返す。"""
    pk = Package(version, root)
    return pk.knot_tau, pk.positions, pk.origin
