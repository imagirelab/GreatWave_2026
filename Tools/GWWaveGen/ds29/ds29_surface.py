# -*- coding: utf-8 -*-
"""設計29：表示用サーフェス（display surface）の網の組み立て。

README
======
設計28 の既定の動き（ds28_model.Generator("art_on")、K* と同じ 240 行 × 400 列の固定トポロジーの格子）を「源」とし、
その面の上に、行 × 列の数を変えられる新しい格子（表示用の網）を張り直す。動き（物質の点・唇の点の位置、t* の形 = K*）は変えない。
表示用の頂点は、源の格子の媒介変数 (ρ, κ)（ρ = 源の行の番号の小数、κ = 源の列の番号の小数）の点で、源の三角形
（四角 (r, c) ごとに T1 = (r,c)(r+1,c)(r,c+1)、T2 = (r,c+1)(r+1,c)(r+1,c+1)。K* の .gwb と同じ分け方）の重心座標で求める。
重みの和は 1 で、どの時刻でも表示用の頂点は源の面の上にある（t* では K* の面の上）。

網の張り方（設計27・28 の P13 の網の検査の不合格の直し。Docs/Progress/Design_28_ja.md §4.1・§8.1）：
  - 行：表示の行 i の ρ_i は源の行の番号で等間隔（K* の行の間隔の分布＝頂の付近が密、を保つ）。行の間の対応は同じ媒介変数の線形補間。
  - 列：源の行ごとに目印の列（0・j_B・頂 root・rim・内壁の錨 ja・j_E・最後の列。設計28 の生成器の整数の列。
    landmark_row_smooth_rows > 0 なら行の間でガウスでならした小数。r01 は 0＝ならさない：頂の列は源の頂の点なので頂の高さを保ち、
    rim・ja で唇と管の継ぎ目が源と同じ列になる）を求め、表示の列は目印を全行で同じ列の番号に置く。唇先は目印にせず、
    唇（root〜rim）の中は t* の弧長の比で行の間を対応させる（K* の唇先の列の割り付けの跳び（行 180/181 など）を渡らない）。
    区間ごとの張り方（ds29_params.json の segments.mode）：
      column    ：目印の間を K* の列の割り付けのまま線形に写す（背面・内壁の下・平らな余白。今の分布を保つ）
      arc_tstar ：t*（K*）の弧長で一様（唇 root〜rim。時刻によらない物質の点なので、唇は重力だけの動きを保つ）
      arc_tau_col：arc_tau と同じく形成の間はその時刻の弧長で一様、ただし t* の土台（w = 0 の κ）は column（K* の列の割り付け）。
                  設計29 の修正2（r02）で足した。t* の表示の網を K* の列の分布に近づけ、原画視点の回帰を減らすため
      arc_tau   ：その時刻の源の弧長で一様（管の天井と内壁の上 rim〜ja。源でも列の番号の比で作った物質でない点で、
                  形成の間に列が詰まる・伸びる所（P13 (5b)(5c)(5e)）を均す）。t* の直前は滑りが速く二階差分と節点を増やすので、
                  κ(τ) = κ_t* + w(τ)·(κ_弧長(τ) − κ_t*)、w は tube_tau_blend_s の [τ0, τ1] で 1 → 0（smoothstep）
  - 区間ごとの表示の列の数は、源の各区間の列の数（体のある行の中央値）に比例して、全体の列の数に割り付ける（全体は 200／400／800）。
表示用の頂点の色の座標（UV・UV2・UV3）と白の時刻 T_white は、t* の媒介変数の点で源から補間する（UV3 は 28修正01 の焼き込み用の
UV の表を頂点ごとにしたもの。表示の網では列の番号と行の番号で分けられないので、頂点ごとのファイル ds29_uv3_f32.bin にする）。
arc_tau の区間は形成の間に源の面の上を滑るので、色は t* の場所の色のまま動く（t* では一致）。

使い方（numpy だけ）：
    from ds29_surface import Source, Display
    src = Source()                              # 設計28 の既定の生成器と K*（SHA-256 を照合）
    d = Display(src, rows=240, cols=400)        # 表示用の網
    X = src.g.local(-2.0)                       # 源の局所座標 (240, 400, 3)
    D = d.eval(X, tau=-2.0)                     # 表示用の局所座標 (rows, cols, 3)
"""
import hashlib
import json
import math
import os
import struct
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
for _p in (DS28, DS27):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import ds27_model as MD  # noqa: E402
import ds28_model as M8  # noqa: E402

REPO = MD.REPO
PARAMS_JSON = os.path.join(HERE, "ds29_params.json")
SEGMENTS = ("back_margin", "back", "lip", "tube", "wall", "front_margin")
NEVER = 1.0e8


def sha256_file(path):
    return MD.sha256_file(path)


def load_params(path=PARAMS_JSON):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rel(p):
    try:
        return os.path.relpath(p, REPO).replace("\\", "/")
    except ValueError:
        return p.replace("\\", "/")


# ---------------------------------------------------------------- 格子の三角形（K* の .gwb と同じ並び）
def grid_tris(nv, nu):
    r = np.arange(nv - 1)[:, None] * nu
    c = np.arange(nu - 1)[None, :]
    t1 = np.stack([r + c, r + c + nu, r + c + 1], -1)
    t2 = np.stack([r + c + 1, r + c + nu, r + c + nu + 1], -1)
    return np.stack([t1, t2], 2).reshape(-1, 3).astype(np.int32)


def bary(rho, kappa, nv, nu):
    """媒介変数 (ρ, κ)（同じ形の配列）→ 源の頂点の添字 (…, 3) と重み (…, 3)。源の三角形の分け方どおりの区分線形。"""
    rho = np.asarray(rho, np.float64)
    kappa = np.asarray(kappa, np.float64)
    r0 = np.clip(np.floor(rho).astype(np.int64), 0, nv - 2)
    c0 = np.clip(np.floor(kappa).astype(np.int64), 0, nu - 2)
    fr = np.clip(rho - r0, 0.0, 1.0)
    fc = np.clip(kappa - c0, 0.0, 1.0)
    i00 = r0 * nu + c0
    t1 = (fr + fc) <= 1.0
    idx = np.where(t1[..., None], np.stack([i00, i00 + nu, i00 + 1], -1), np.stack([i00 + 1, i00 + nu, i00 + nu + 1], -1))
    w = np.where(t1[..., None], np.stack([1.0 - fr - fc, fr, fc], -1), np.stack([1.0 - fr, 1.0 - fc, fr + fc - 1.0], -1))
    return idx, w


def gather(Xflat, idx, w):
    """Xflat (N, d) の重み付きの和 → (…, d)。"""
    return (Xflat[idx] * w[..., None]).sum(-2)


def row_arc(X):
    """行ごとの累積の弧長 (nv, nu)。X (nv, nu, 3)。狭義単調にするため列ごとに 1e-9 m を足す。"""
    e = np.linalg.norm(np.diff(X, axis=1), axis=-1)
    s = np.concatenate([np.zeros((X.shape[0], 1)), np.cumsum(e, 1)], 1)
    return s + 1e-9 * np.arange(X.shape[1])[None, :]


def interp_rows(x, xp, fp):
    """行ごとの np.interp。x (nv, m)、xp (nv, n)、fp (n,) か (nv, n)。"""
    out = np.empty(x.shape, np.float64)
    for r in range(x.shape[0]):
        out[r] = np.interp(x[r], xp[r], fp if fp.ndim == 1 else fp[r])
    return out


# ---------------------------------------------------------------- 源（設計28 の既定の動き）
class Source:
    def __init__(self, params=None, log=None):
        self.P = params or load_params()
        self.log = log or (lambda *a: None)
        sp = self.P["source"]
        self.pkg_dir = os.path.join(REPO, sp["package_dir"])
        jp = os.path.join(self.pkg_dir, "ds27_keypose.json")
        with open(jp, encoding="utf-8") as f:
            self.pkg = json.load(f)
        if self.pkg["pos_sha256"] != sp["package_pos_sha256"]:
            raise SystemExit("[ds29] 源のパッケージが設計28 の既定（art_on）と違います")
        self.pkg_json_sha = sha256_file(jp)
        self.g = M8.Generator(sp["version"], log=None)
        K = self.g.K
        self.K = K
        self.nv, self.nu = K.nv, K.nu
        # K* の .gwb の UV・UV2（読むだけ）
        b = open(os.path.join(K.dir, "kstar_a45.gwb"), "rb").read()
        n = self.nv * self.nu
        o = 32
        self.uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).astype(np.float64)
        o += n * 8
        self.uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).astype(np.float64)
        # 28修正01 の焼き込み用の UV（UV3）の表（列ごとの u′、行ごとの v′）
        wp = os.path.join(REPO, sp["uv3_warp"])
        with open(wp, encoding="utf-8") as f:
            W = json.load(f)
        if int(W["nu"]) != self.nu or int(W["nv"]) != self.nv:
            raise SystemExit("[ds29] UV3 の表の大きさが K* と違います")
        uw = np.asarray(W["uWarp"], np.float64)
        vw = np.asarray(W["vWarp"], np.float64)
        self.uv3 = np.stack(np.broadcast_arrays(uw[None, :], vw[:, None]), -1).reshape(n, 2)
        self.uv3_sha = sha256_file(wp)
        self.uv3_path = wp
        # 白の時刻（設計28 のパッケージと同じ。生成器から作り、パッケージのファイルと照合する）
        T = self.g.twhite().astype(np.float32)
        tp = os.path.join(self.pkg_dir, self.pkg["twhite_file"])
        Tp = np.fromfile(tp, "<f4").reshape(self.nv, self.nu)
        self.twhite_matches_package = bool(np.array_equal(T, Tp))
        self.twhite = Tp.astype(np.float64)
        self.knots = np.asarray(self.pkg["knot_tau"], np.float64)
        self.arc0 = row_arc(K.X)                 # t*（K*）の行ごとの弧長
        self._landmarks()

    def _landmarks(self):
        g, P = self.g, self.P
        nv, nu = self.nv, self.nu
        body = g.has_body.copy()
        bi = np.nonzero(body)[0]
        root = g.root.astype(np.float64).copy()
        rim = g.rim.astype(np.float64).copy()
        ja = g.ja.astype(np.float64).copy()
        for r in range(nv):
            if not body[r]:
                q = bi[np.argmin(np.abs(bi - r))]
                root[r], rim[r], ja[r] = root[q], rim[q], ja[q]
        s = float(P["landmark_row_smooth_rows"])
        if s > 0:
            i = np.arange(nv, dtype=np.float64)
            Wm = np.exp(-0.5 * ((i[:, None] - i[None, :]) / s) ** 2)
            Wm /= Wm.sum(1, keepdims=True)
            root, rim, ja = Wm @ root, Wm @ rim, Wm @ ja
        gap = float(P["min_segment_gap_columns"])
        jB, jE = float(g.jB), float(g.jE)
        root = np.clip(root, jB + gap, jE - 3 * gap)
        rim = np.clip(rim, root + gap, jE - 2 * gap)
        ja = np.clip(ja, rim + gap, jE - gap)
        self.L = np.stack([np.zeros(nv), np.full(nv, jB), root, rim, ja, np.full(nv, jE), np.full(nv, nu - 1.0)], 1)
        self.body = body

    def local(self, tau):
        return self.g.local(float(tau))

    def origin(self, tau):
        return self.g.origin(float(tau))


# ---------------------------------------------------------------- 表示用の網
class Display:
    def __init__(self, src, rows, cols, name=None, modes=None):
        self.src = src
        self.name = name or "%dx%d" % (rows, cols)
        self.nv, self.nu = int(rows), int(cols)
        P = src.P
        self.modes = dict(P["segments"]["mode"]) if modes is None else dict(modes)
        nvs, nus = src.nv, src.nu
        L = src.L
        # 区間ごとの表示の列の数（源の列の数の中央値に比例、最後の列までの辺の数 = cols − 1）
        E_src = np.diff(L, axis=1)[src.body]
        med = np.median(E_src, 0)
        E = self.nu - 1
        raw = med / med.sum() * E
        n = np.maximum(np.floor(raw).astype(int), 1)
        rem = E - int(n.sum())
        order = np.argsort(-(raw - np.floor(raw)), kind="stable")
        k = 0
        while rem != 0:
            j = order[k % len(order)]
            if rem > 0:
                n[j] += 1
                rem -= 1
            elif n[j] > 1:
                n[j] -= 1
                rem += 1
            k += 1
        self.n_seg = n
        self.k_seg = np.concatenate([[0], np.cumsum(n)]).astype(int)     # 目印の表示の列
        self.src_median_cols = med
        # 表示の行の ρ（源の行の番号で等間隔）
        self.rho = np.linspace(0.0, nvs - 1.0, self.nv)
        r0 = np.clip(np.floor(self.rho).astype(int), 0, nvs - 2)
        self.r0 = r0
        self.fr = self.rho - r0
        # 源の行ごとの t* の κ の表 (nvs, nu_d)
        self.kap_src0 = self._kappa_src(src.arc0, tau_mode=False)
        self.kappa0 = self._to_display_rows(self.kap_src0)
        self.rho_grid = np.broadcast_to(self.rho[:, None], (self.nv, self.nu)).copy()
        self.idx0, self.w0 = bary(self.rho_grid, self.kappa0, nvs, nus)
        # 時刻で動く列（arc_tau の区間の内側の列）
        self.tau_cols = np.zeros(self.nu, bool)
        for s, nm in enumerate(SEGMENTS):
            if self.modes[nm] in ("arc_tau", "arc_tau_col"):
                self.tau_cols[self.k_seg[s] + 1:self.k_seg[s + 1]] = True
        self.has_tau = bool(self.tau_cols.any())
        self.tris = grid_tris(self.nv, self.nu)

    # 源の行ごとの κ（表示の列 k ごと）。arc は源の行ごとの累積の弧長 (nvs, nus)。tau_mode=True のときは arc_tau の区間だけ使う
    def _kappa_src(self, arc, tau_mode=False, base=None):
        src = self.src
        nvs, nus = src.nv, src.nu
        L = src.L
        jcol = np.arange(nus, dtype=np.float64)
        out = np.zeros((nvs, self.nu)) if base is None else base.copy()
        for s, nm in enumerate(SEGMENTS):
            mode = self.modes[nm]
            if tau_mode and mode not in ("arc_tau", "arc_tau_col"):
                continue
            k0, k1 = self.k_seg[s], self.k_seg[s + 1]
            u = (np.arange(k0, k1 + 1) - k0) / float(k1 - k0)
            La, Lb = L[:, s], L[:, s + 1]
            if mode == "column" or (mode == "arc_tau_col" and not tau_mode):   # arc_tau_col：t* の土台は column、時刻の弧長へ w(τ) で寄せる
                out[:, k0:k1 + 1] = La[:, None] + u[None, :] * (Lb - La)[:, None]
            else:
                sa = np.array([np.interp(La[r], jcol, arc[r]) for r in range(nvs)])
                sb = np.array([np.interp(Lb[r], jcol, arc[r]) for r in range(nvs)])
                tgt = sa[:, None] + u[None, :] * (sb - sa)[:, None]
                kk = interp_rows(tgt, arc, jcol)
                kk[:, 0], kk[:, -1] = La, Lb
                out[:, k0:k1 + 1] = kk
        return out

    def _to_display_rows(self, kap_src):
        return (1.0 - self.fr)[:, None] * kap_src[self.r0] + self.fr[:, None] * kap_src[self.r0 + 1]

    def tau_weight(self, tau):
        """arc_tau の区間の時刻の重み w(τ)（tube_tau_blend_s の [τ0, τ1] で 1 → 0、smoothstep）。"""
        b = self.src.P.get("tube_tau_blend_s")
        if not b:
            return 1.0
        x = (float(tau) - b[0]) / (b[1] - b[0])
        x = min(max(x, 0.0), 1.0)
        return 1.0 - x * x * (3.0 - 2.0 * x)

    def kappa_at(self, X_src, tau):
        """時刻 τ の源の位置 X_src (nvs, nus, 3) での表示の κ (nv, nu)。arc_tau の区間がなければ t* の κ。"""
        if not self.has_tau:
            return self.kappa0
        w = self.tau_weight(tau)
        if w <= 0.0:
            return self.kappa0
        ks = self._kappa_src(row_arc(X_src), tau_mode=True, base=self.kap_src0)
        ks = self.kap_src0 + w * (ks - self.kap_src0)
        return self._to_display_rows(ks)

    def eval(self, X_src, tau, kappa=None, return_kappa=False):
        """源の局所座標 X_src (nvs, nus, 3)（時刻 τ）→ 表示用の局所座標 (nv, nu, 3)。"""
        Xf = X_src.reshape(-1, 3)
        D = gather(Xf, self.idx0, self.w0)
        kap = self.kappa0
        if self.has_tau:
            kap = self.kappa_at(X_src, tau) if kappa is None else kappa
            cols = self.tau_cols
            idx, w = bary(self.rho_grid[:, cols], kap[:, cols], self.src.nv, self.src.nu)
            D[:, cols] = gather(Xf, idx, w)
        return (D, kap) if return_kappa else D

    def attr(self, A):
        """頂点ごとの属性 A (nvs·nus, d) を t* の媒介変数で補間 → (nv·nu, d)。"""
        return gather(A, self.idx0.reshape(-1, 3), self.w0.reshape(-1, 3))

    def twhite(self):
        """T_white の補間：寄与する源の頂点がすべて有限なら重み付きの平均。t* まで白くならない頂点（1e9）の重みが 0.5 以上なら 1e9、
        それより小さければ有限の頂点だけで重みを割り直した平均。"""
        T = self.src.twhite.reshape(-1)
        idx = self.idx0.reshape(-1, 3)
        w = self.w0.reshape(-1, 3)
        Tv = T[idx]
        fin = Tv < NEVER
        wf = np.where(fin, w, 0.0)
        sf = wf.sum(1)
        mean = (wf * np.where(fin, Tv, 0.0)).sum(1) / np.maximum(sf, 1e-12)
        never = sf < 0.5 - 1e-12
        out = np.where(never, float(self.src.P["twhite_never"]), mean)
        return out.reshape(self.nv, self.nu)

    def region(self):
        """P13 の網の検査の範囲（設計27 の関門と同じ考え方：巻きの行の唇〜管の天井。表示では、源の巻きの行（K* の E1/E4 の規則、
        行 60〜192）の中にある表示の行の、頂の目印の列から内壁の錨の目印の列の手前まで）。"""
        lo, hi = 60, 192
        curled = (self.rho >= lo - 1e-9) & (self.rho <= hi + 1e-9)
        k_root, k_rim, k_ja = self.k_seg[2], self.k_seg[3], self.k_seg[4]
        return dict(curled=curled, k_root=int(k_root), k_rim=int(k_rim), k_ja=int(k_ja),
                    main_row=int(np.argmin(np.abs(self.rho - self.src.K.main_row))),
                    peak_row=int(np.argmin(np.abs(self.rho - 192))))

    def describe(self):
        return dict(name=self.name, rows=self.nv, cols=self.nu, vertices=self.nv * self.nu, triangles=int(len(self.tris)),
                    segments=[dict(name=nm, mode=self.modes[nm], display_cols=[int(self.k_seg[s]), int(self.k_seg[s + 1])],
                                   display_edges=int(self.n_seg[s]), source_median_edges=float(self.src_median_cols[s]))
                              for s, nm in enumerate(SEGMENTS)],
                    rows_rho="ρ_i = i·(240 − 1)/(rows − 1)（源の行の番号で等間隔）",
                    landmark_row_smooth_rows=float(self.src.P["landmark_row_smooth_rows"]))


# ---------------------------------------------------------------- 書き出し
def write_gwb(path, nu, nv, uv, uv2, tris, X):
    """GWW0 の 1 コマの .gwb（gw_wavegen_v1.write_gwb と同じ書式。AF26KStarMesh が読む）。"""
    with open(path, "wb") as fo:
        fo.write(b"GWW0" + struct.pack("<iiiifii", 1, nu, nv, 1, 30.0, 0, len(tris)))
        for arr in (uv.astype(np.float32), uv2.astype(np.float32), tris.astype(np.int32), X.reshape(-1, 3).astype(np.float32)):
            fo.write(np.ascontiguousarray(arr).tobytes())


def write_obj(path, X, uv, tris, header):
    V = X.reshape(-1, 3)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for h in header:
            f.write("# %s\n" % h)
        f.write("o kstar\n")
        f.write("".join("v %.6f %.6f %.6f\n" % tuple(p) for p in V))
        f.write("".join("vt %.7f %.7f\n" % tuple(t) for t in uv))
        f.write("".join("f %d/%d %d/%d %d/%d\n" % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1) for a, b, c in tris))


def dump_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def quantize(Xs):
    """設計27 の export_package と同じ外接箱（1 cm の余白、mm で切り上げ・切り下げ）と RGBA16 の量子化。"""
    lo = Xs.reshape(-1, 3).min(0) - 0.01
    hi = Xs.reshape(-1, 3).max(0) + 0.01
    lo = np.floor(lo * 1000) / 1000
    hi = np.ceil(hi * 1000) / 1000
    size = hi - lo
    q = np.clip(np.round((Xs - lo) / size * 65535.0), 0, 65535).astype("<u2")
    return lo, size, q
