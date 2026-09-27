# -*- coding: utf-8 -*-
"""設計29：表示用サーフェスの独立した検査器（numpy。座席からの射線・3 次元の自己交差は ds29_blender_qa.py）。

表示用サーフェスの作り手（生成器）のコードは読まず、包み（keypose）の約束だけから作った。どの密度（行 × 列）でも、
格子でない三角形の網でも測れる。K*（26修正01）は読むだけ（設計27 の ds27_gates.KStar で SHA-256 を照合）で、
巻きの行・唇の列の定義（設計26 の E1/E4）と、行の c の面（断面の面）の位置を借りる。

入力（どれも読むだけ）
  --package [名前=]<包み>     keypose の包み（ds27_keypose.json の約束）。rows・cols・layers・bbox_min・bbox_size・knot_tau・
                              frame{tau, origin}・pos_file（既定 ds27_pos_rgba16.bin、RGBA16 UNORM、層 × 行 × 列 × 4）。
                              任意で tris_file（int32 の三角形の添字 (n, 3)、リトルエンディアン。無ければ K* と同じ格子の分け方）。
                              何度でも。補間は包みの約束どおり節点の間の 3 次 Hermite（傾きは両隣の差、端は片側）、枠の原点は線形補間。
  --kstar                     K*（26修正01、t* の 1 コマの静止した網）も検査する（名前 kstar）。
  --subsample 名前=<包み>:rs,cs  検査器の確かめ用：包みの行を rs 行ごと・列を cs 列ごとに間引いた網（端の行・列は残す）を
                              その場で作って検査する（作り手の密度の作り方とは別物。波頭の欠落・薄膜の検査が働くかを見る）。
  --ref <包み>                波頭の欠落を比べる基準の包み（設計28 の入れた版など）。同じ τ・同じ断面の面で比べる。
  --taus                      既定 "last3"（最後の 3 s を 0.1 s ごと）＋ --stages（既定 a/b/c/d/apex/t*：設計28 の段階の静止画の τ）。
  --blender                   ds29_blender_qa.py を Blender 5.2.2 ヘッドレスで回し、座席 v1 からの 5 万本の射線と 3 次元の自己交差を足す。
  --selftest                  わざと壊した K*（穴・継ぎ目の割れ・裏返し・潰れた唇先）で、各検査が 0 でない値を出すことを確かめる。

出力：--out のフォルダーに <名前>_qa.json と、まとめ ds29_qa_summary.json・ds29_qa_summary.md（日本語の表）。

測るもの（τ の一覧の各コマ。「30 Hz の通し」は包みの τ の全区間）
  位相（添字の網、1 回）：2 面より多くの面が接する辺（非多様体）、縁の辺と格子の外周の比較、縁の輪の数（外周以外＝継ぎ目・穴）、
      向きが隣と食い違う辺（面の向きの反転）、使われない頂点、同じ位置に重なった縁の頂点（溶接していない継ぎ目）。
  形（コマごと）：位置と頂点法線の NaN、面積 0 の面、隣の面と法線が逆を向く辺（折れ返り。二面角 > 120°）、
      前のコマ（1/30 s 前）と比べた面の反転、行の断面での自己交差（隣でない線分の真の交差）、
      唇先の厚さ（K* の定義：巻いた断面で唇先から 0.75 m 奥の鉛直の厚さ。上面の表と下面の表の向きも確かめる）、
      波頭（断面ごとの頂の高さ・唇先の位置・唇の形の片側の距離）の --ref との差。
  30 Hz の通し：波の枠の 1 コマの変位、地面の二階差分（2 g）、面の反転、唇・管の辺の最短と t* に対する伸び（P13 の (5b)〜(5d) と同じ考え）。
      網が K* と同じ 240 × 400 の格子なら、設計27 の P13 と同じ式（(2)(5a)〜(5g)(6)）も測る（記録の再現の確かめ）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_qa.py --package d28=Unity/Build/Design/28/art_on --ref Unity/Build/Design/28/art_on --kstar --blender
numpy だけを使う（Blender の側は Blender に同梱の numpy と mathutils）。
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
import ds27_gates as G27  # noqa: E402  K* の読み込み（SHA-256 の照合）と巻きの行・唇の列の定義だけを使う

SEAT_JSON = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
BLENDER_QA = os.path.join(HERE, "ds29_blender_qa.py")
G = 9.81
HZ = 30
STAGES_DEFAULT = "a=-4.433,b=-3.500,c=-2.933,d=-2.250,apex=-1.333,tstar=0"
TH = dict(
    step_m=0.6,                       # P13(1)
    acc_m=2.0 * G / HZ ** 2,          # P13(2) 2 g（30 Hz の二階差分）
    edge_min_m=0.005,                 # P13(5b)
    stretch_lo=0.05, stretch_hi=4.0,  # P13(5c)(5d)
    seam_lo=0.25, seam_hi=4.0,        # P13(5e)
    tri_area_m2=1e-4,                 # P13(5a)
    resolvable_alt_m=0.005,           # 面の反転を数える三角形：最小の高さ ≥ 5 mm（量子化 1.2 mm の約 4 倍）
    degenerate_area_m2=1e-8,          # 美術優先26 の Blender の検査と同じ
    fold_dot=-0.5,                    # 折れ返り：隣り合う 2 面の単位法線の内積 < −0.5（二面角 > 120°）
    lip_thick_m=0.3,                  # 唇先の厚さ（計画 §2.1 設計29）
    lip_behind_m=0.75,                # 厚さを測る位置（唇先から奥へ。26修正01 の定義）
    curl_H_m=3.0,                     # 巻きを探す断面の頂の高さの下限（設計26 の E1 と同じ）
    crest_tol_m=0.02,                 # 波頭の欠落の暫定の許容（原画視点 1080 px で約 0.7 px。記録のみ）
    seg_min_m=0.005,                  # 断面の自己交差を数える線分の長さの下限
    microfold_m=0.05,
    lip_ny_min=0.2,                   # 唇の厚さは、上面・下面の単位法線の上下の成分が 0.2 以上（水平から 78° 以内）の所だけで測る（急な面の鉛直の厚さは意味がない）                 # 唇の厚さの鉛直の線で、表・裏・表の 3 回の横切りがこの内なら小さな折れとして消す
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")
    except ValueError:
        return p.replace("\\", "/")


def r4(x, nd=4):
    if x is None:
        return None
    if isinstance(x, (int, np.integer)):
        return int(x)
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def grid_tris(nv, nu):
    """K* と同じ分け方：(r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)。添字 = ((r·(nu−1)) + c)·2 + k。"""
    r = np.arange(nv - 1)[:, None] * nu
    c = np.arange(nu - 1)[None, :]
    t1 = np.stack([r + c, r + c + nu, r + c + 1], -1)
    t2 = np.stack([r + c + 1, r + c + nu, r + c + nu + 1], -1)
    return np.stack([t1, t2], 2).reshape(-1, 3).astype(np.int64)


# ---------------------------------------------------------------- 網（包み・K*・間引き）
class PackageSurface:
    """keypose の包み。位置は層ごとに読む（memmap）。world(τ) = Hermite(局所) + O(τ)。"""
    static = False

    def __init__(self, d, label=None):
        self.dir = os.path.abspath(d)
        cand = [f for f in os.listdir(self.dir) if f.endswith("_keypose.json")]
        if not cand:
            raise SystemExit("[ds29_qa] keypose の json がありません：%s" % d)
        self.json_path = os.path.join(self.dir, "ds27_keypose.json" if "ds27_keypose.json" in cand else sorted(cand)[0])
        J = json.load(open(self.json_path, encoding="utf-8"))
        self.meta = J
        self.label = label or os.path.basename(self.dir.rstrip("/\\"))
        self.L, self.rows, self.cols = int(J["layers"]), int(J["rows"]), int(J["cols"])
        self.nv = self.rows * self.cols
        self.pos_path = os.path.join(self.dir, J.get("pos_file", "ds27_pos_rgba16.bin"))
        self.pos_sha = sha256_file(self.pos_path)
        self.checks = [dict(item_ja="pos_sha256 がファイルと一致", ok=self.pos_sha == J.get("pos_sha256"), detail=self.pos_sha[:12])]
        size = os.path.getsize(self.pos_path)
        self.checks.append(dict(item_ja="位置のファイル = 層 × 行 × 列 × 8 バイト", ok=size == self.L * self.nv * 8, detail="%d バイト" % size))
        if size != self.L * self.nv * 8:
            raise SystemExit("[ds29_qa] 位置のファイルの大きさが layers・rows・cols と合いません：%s" % d)
        self.raw = np.memmap(self.pos_path, dtype="<u2", mode="r", shape=(self.L, self.nv, 4))
        self.lo = np.array(J["bbox_min"], float)
        self.sz = np.array(J["bbox_size"], float)
        self.q_max = 0.5 * float(np.linalg.norm(self.sz)) / 65535.0
        self.knots = np.array(J["knot_tau"], float)
        ok = len(self.knots) == self.L and bool(np.all(np.diff(self.knots) > 0))
        self.checks.append(dict(item_ja="knot_tau が層の数・狭義単調増加", ok=ok, detail="%.3f〜%.3f s、間隔 %.4f〜%.4f s" % (
            self.knots[0], self.knots[-1], np.diff(self.knots).min(), np.diff(self.knots).max())))
        fr = J["frame"]
        self.ftau = np.array(fr["tau"], float)
        self.forg = np.array(fr["origin"], float).reshape(-1, 3)
        tf = J.get("tris_file") or J.get("index_file")
        if tf:
            tp = os.path.join(self.dir, tf)
            self.F = np.fromfile(tp, "<i4").astype(np.int64).reshape(-1, 3)
            self.grid = False
            self.tris_src = tf
        else:
            self.F = grid_tris(self.rows, self.cols)
            self.grid = True
            self.tris_src = "格子（K* と同じ分け方）"
        self._cache = {}
        self.tau0, self.tau1 = float(self.knots[0]), float(self.knots[-1])

    def layer(self, l):
        l = int(l)
        v = self._cache.get(l)
        if v is None:
            if len(self._cache) >= 8:
                self._cache.pop(next(iter(self._cache)))
            # 32 ビットに丸めて持つ（GPU のテクスチャから読む値と、設計27 の検査器の持ち方に合わせる）
            v = (self.lo + np.asarray(self.raw[l, :, :3], dtype=np.float64) / 65535.0 * self.sz).astype(np.float32).astype(np.float64)
            self._cache[l] = v
        return v

    def local(self, tau):
        """包みの約束の Hermite（独立に書いた。設計27 の検査器と照合する：--xcheck）。"""
        k = self.knots
        L = len(k)
        i = int(np.clip(np.searchsorted(k, tau, side="right") - 1, 0, L - 2))
        t1, t2 = k[i], k[i + 1]
        D = t2 - t1
        s = min(max((tau - t1) / D, 0.0), 1.0)
        p0, p1 = self.layer(i), self.layer(i + 1)
        m0 = (p1 - self.layer(i - 1)) / (t2 - k[i - 1]) if i > 0 else (p1 - p0) / D
        m1 = (self.layer(i + 2) - p0) / (k[i + 2] - t1) if i + 2 <= L - 1 else (p1 - p0) / D
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        return h00 * p0 + h10 * D * m0 + h01 * p1 + h11 * D * m1

    def origin(self, tau):
        return np.array([np.interp(tau, self.ftau, self.forg[:, j]) for j in range(3)])

    def world(self, tau):
        return self.local(tau) + self.origin(tau)

    def info(self):
        return dict(kind="包み", dir=rel(self.dir), keypose_json=os.path.basename(self.json_path), version=self.meta.get("version"),
                    number=self.meta.get("number"), layers=self.L, rows=self.rows, cols=self.cols, vertices=self.nv, faces=int(len(self.F)),
                    tris=self.tris_src, pos_sha256=self.pos_sha, pos_bytes=int(os.path.getsize(self.pos_path)),
                    quantization_max_m=r4(self.q_max, 5), knot_tau_range=[self.tau0, self.tau1], checks=self.checks)


class KStarSurface:
    """K*（26修正01、t* の静止した網。float32 のワールド座標）。"""
    static = True

    def __init__(self, ks):
        self.ks = ks
        self.label = "kstar"
        self.rows, self.cols = ks.nv, ks.nu
        self.nv = self.rows * self.cols
        self.X = ks.X.reshape(-1, 3).copy()
        self.F = grid_tris(self.rows, self.cols)
        self.grid = True
        self.q_max = 0.0
        self.tau0 = self.tau1 = 0.0

    def world(self, tau):
        return self.X

    def origin(self, tau):
        return np.zeros(3)

    def local(self, tau):
        return self.X

    def info(self):
        return dict(kind="K*（26修正01、静止）", dir=rel(G27.KSTAR_DIR), rows=self.rows, cols=self.cols, vertices=self.nv, faces=int(len(self.F)),
                    tris="K* の .gwb の三角形（格子の分け方と同じことを ds27_gates が確かめる）", sha256=self.ks.sha)


class SubsampledSurface:
    """検査器の確かめ用：包みの行・列を間引いた格子（端は残す）。"""
    static = False

    def __init__(self, parent, rs, cs, label):
        self.p = parent
        self.label = label
        ri = np.unique(np.r_[np.arange(0, parent.rows, rs), parent.rows - 1])
        ci = np.unique(np.r_[np.arange(0, parent.cols, cs), parent.cols - 1])
        self.ri, self.ci = ri, ci
        self.rows, self.cols = len(ri), len(ci)
        self.nv = self.rows * self.cols
        self.idx = (ri[:, None] * parent.cols + ci[None, :]).reshape(-1)
        self.F = grid_tris(self.rows, self.cols)
        self.grid = True
        self.q_max = parent.q_max
        self.tau0, self.tau1 = parent.tau0, parent.tau1
        self.knots = parent.knots

    def local(self, tau):
        return self.p.local(tau)[self.idx]

    def origin(self, tau):
        return self.p.origin(tau)

    def world(self, tau):
        return self.local(tau) + self.origin(tau)

    def info(self):
        return dict(kind="間引き（検査器の確かめ用）", parent=rel(self.p.dir), rows=self.rows, cols=self.cols, vertices=self.nv, faces=int(len(self.F)),
                    row_step=int(self.ri[1] - self.ri[0]), col_step=int(self.ci[1] - self.ci[0]))


class DefectSurface:
    """--selftest：K* をわざと壊した網。"""
    static = True

    def __init__(self, ks, kind):
        self.ks = ks
        self.label = "selftest_" + kind
        self.rows, self.cols = ks.nv, ks.nu
        X = ks.X.copy()
        F = grid_tris(ks.nv, ks.nu)
        nu = ks.nu
        q = ks.cq[ks.main_row]
        r0 = ks.main_row
        self.note = ""
        if kind == "hole":            # 前面（内壁の 0.3H の錨の列の近く）に 3 × 6 の四角の穴
            rr, cc = np.meshgrid(np.arange(r0 - 1, r0 + 2), np.arange(q["ja"] - 3, q["ja"] + 3), indexing="ij")
            quad = (rr * (nu - 1) + cc).reshape(-1)
            keep = np.ones(len(F), bool)
            keep[np.r_[quad * 2, quad * 2 + 1]] = False
            F = F[keep]
            self.note = "主断面の内壁（錨の列 ja の前後 3 列 × 3 行）の三角形 36 枚を消した"
        elif kind == "seam":          # 主断面の行と次の行の間の、頂の手前から rim の先までを切り、切り口の片側を 5 cm 前・2 cm 上へずらした割れ
            rs = r0
            c0, c1 = q["jt"] - 10, q["rim"] + 10
            Xn = X.reshape(-1, 3)
            cols = np.arange(c0, c1 + 1)
            extra = Xn[rs * nu + cols] + 0.05 * ks.t[None, :] + np.array([0.0, 0.02, 0.0])
            base = len(Xn)
            Xn = np.vstack([Xn, extra])
            Fq = F.copy()
            quads = rs * (nu - 1) + np.arange(c0, c1)      # 行 rs と rs+1 の間、列 c0..c1−1 の四角
            for t in np.r_[quads * 2, quads * 2 + 1]:
                f = Fq[t]
                m = (f >= rs * nu + c0) & (f <= rs * nu + c1)
                Fq[t] = np.where(m, base + (f - rs * nu - c0), f)
            X = Xn
            F = Fq
            self.note = "主断面の行と次の行の間を列 %d〜%d で切り（頂の手前から rim の先まで）、切り口の片側を 5 cm 前・2 cm 上へずらした" % (c0, c1)
        elif kind == "flip":          # 唇の上面の 20 枚の巻き方向を逆にする
            quads = r0 * (nu - 1) + np.arange(q["jt"] + 5, q["jt"] + 15)
            ids = np.r_[quads * 2, quads * 2 + 1]
            F[ids] = F[ids][:, [0, 2, 1]]
            self.note = "主断面の唇の上面（頂の列 jt+5〜jt+14）の三角形 20 枚の巻き方向を逆にした"
        elif kind == "thin":          # 巻きの行の唇を中線へ寄せて 0.1 m の膜にする（主断面 ±5 行）
            Xg = X.reshape(ks.nv, nu, 3)
            for r in range(r0 - 5, r0 + 6):
                qq = ks.cq.get(r)
                if qq is None:
                    continue
                A = (Xg[r] - ks.O) @ ks.t
                Y = Xg[r, :, 1]
                jt, jtip, rim = qq["jt"], qq["jtip"], qq["rim"]
                top = np.arange(jt, jtip + 1)
                bot = np.arange(jtip, rim + 1)
                for j in bot:        # 下面の点を、同じ a の上面の y − 0.1 m へ（上面より下に保つ）
                    ytop = np.interp(A[j], A[top], Y[top])
                    Xg[r, j, 1] = min(Y[j], ytop - 0.1) if A[j] >= A[top].min() else Y[j]
                    Xg[r, j, 1] = max(Xg[r, j, 1], ytop - 0.1)
            X = Xg.reshape(-1, 3)
            self.note = "主断面 ±5 行の唇の下面を、同じ a の上面の 0.1 m 下へ寄せた（薄い膜）"
        self.X = X.reshape(-1, 3)
        self.nv = len(self.X)
        self.F = F
        self.grid = False
        self.q_max = 0.0
        self.tau0 = self.tau1 = 0.0

    def world(self, tau):
        return self.X

    def origin(self, tau):
        return np.zeros(3)

    def local(self, tau):
        return self.X

    def info(self):
        return dict(kind="わざと壊した K*（--selftest）", defect_ja=self.note, vertices=self.nv, faces=int(len(self.F)))


# ---------------------------------------------------------------- 位相
def topology(F, nv, X_ref, grid_shape=None):
    nf = len(F)
    he = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], 0)
    face_of = np.tile(np.arange(nf), 3)
    u = np.minimum(he[:, 0], he[:, 1])
    w = np.maximum(he[:, 0], he[:, 1])
    key = u * nv + w
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    E = np.stack([uk // nv, uk % nv], 1)
    dkey = he[:, 0] * nv + he[:, 1]
    dk, dinv, dcnt = np.unique(dkey, return_inverse=True, return_counts=True)
    # 2 面の辺：2 つの半辺の向きが逆なら整合。同じ向き＝面の向きの反転
    order = np.argsort(inv, kind="stable")
    starts = np.r_[0, np.cumsum(cnt)[:-1]]
    two = np.nonzero(cnt == 2)[0]
    h1, h2 = order[starts[two]], order[starts[two] + 1]
    same_dir = he[h1, 0] == he[h2, 0]
    edge_faces = np.stack([face_of[h1], face_of[h2]], 1)
    idx_degen = int(((F[:, 0] == F[:, 1]) | (F[:, 1] == F[:, 2]) | (F[:, 0] == F[:, 2])).sum())
    used = np.zeros(nv, bool)
    used[F.reshape(-1)] = True
    # 縁の輪
    bmask_e = cnt == 1
    bhe = order[starts[np.nonzero(bmask_e)[0]]]
    nxt = {}
    multi = 0
    for a, b in he[bhe]:
        if a in nxt:
            multi += 1
        nxt.setdefault(int(a), int(b))
    loops = []
    seen = set()
    for s in list(nxt.keys()):
        if s in seen:
            continue
        loop = [s]
        seen.add(s)
        v = nxt.get(s)
        guard = 0
        while v is not None and v != s and guard < len(nxt) + 5:
            if v in seen:
                break
            loop.append(v)
            seen.add(v)
            v = nxt.get(v)
            guard += 1
        loops.append(np.array(loop))
    if loops:
        per = [float(np.linalg.norm(np.diff(X_ref[np.r_[lp, lp[:1]]], axis=0), axis=1).sum()) for lp in loops]
        oi = int(np.argmax(per))
    else:
        per, oi = [], -1
    outer = loops[oi] if loops else np.zeros(0, int)
    inner = [lp for k, lp in enumerate(loops) if k != oi]
    inner_v = np.unique(np.concatenate(inner)) if inner else np.zeros(0, int)
    # 縁の頂点で同じ位置に重なるもの（溶接していない継ぎ目）
    bv = np.unique(E[bmask_e].reshape(-1)) if bmask_e.any() else np.zeros(0, int)
    coinc = 0
    if len(bv):
        # 同じ位置（0.1 mm）に重なる縁の頂点のうち、辺でひと続きにならないもの（溶接していない継ぎ目）
        kq = np.round(X_ref[bv] / 1e-4).astype(np.int64)
        _, ci, cc = np.unique(kq, axis=0, return_inverse=True, return_counts=True)
        ci = ci.reshape(-1)
        groups = [bv[ci == g] for g in np.nonzero(cc > 1)[0]]
        if groups:
            want = set(int(v) for g in groups for v in g)
            nbr = {v: set() for v in want}
            for a_, b_ in E:
                a_, b_ = int(a_), int(b_)
                if a_ in nbr:
                    nbr[a_].add(b_)
                if b_ in nbr:
                    nbr[b_].add(a_)
            for mem in groups:
                # 重なった頂点どうしが辺でひと続きなら、詰まった列が量子化でつぶれただけ。ひと続きでない塊の数 − 1 を数える
                ms = set(int(v) for v in mem)
                left = set(ms)
                ncomp = 0
                while left:
                    ncomp += 1
                    stack = [left.pop()]
                    while stack:
                        v = stack.pop()
                        for w_ in nbr[v] & left:
                            left.discard(w_)
                            stack.append(w_)
                coinc += ncomp - 1
    out = dict(vertices=int(nv), faces=int(nf), edges=int(len(uk)),
               nonmanifold_edges_gt2=int((cnt > 2).sum()), boundary_edges=int(bmask_e.sum()),
               wire_edges=0, winding_inconsistent_edges=int(same_dir.sum()), directed_halfedge_dupes=int((dcnt > 1).sum()),
               index_degenerate_faces=idx_degen, unreferenced_vertices=int((~used).sum()),
               boundary_loops=len(loops), outer_loop_vertices=int(len(outer)), outer_loop_perimeter_m=r4(per[oi] if loops else 0.0, 2),
               inner_loops=len(inner), inner_loop_sizes=[int(len(x)) for x in inner][:20], inner_boundary_vertices=int(len(inner_v)),
               boundary_vertex_branching=int(multi), coincident_boundary_vertex_pairs_unjoined=coinc)
    if grid_shape is not None:
        nr, nc = grid_shape
        out["boundary_edges_expected_grid_perimeter"] = int(2 * (nr - 1) + 2 * (nc - 1))
    T = dict(E=E, cnt=cnt, edge_faces=edge_faces, two=two, outer=outer, inner=inner, inner_v=inner_v)
    return out, T


# ---------------------------------------------------------------- 幾何の小道具
def face_geom(X, F):
    a, b, c = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    n = np.cross(b - a, c - a)
    nl = np.linalg.norm(n, axis=1)
    area = 0.5 * nl
    emax = np.maximum.reduce([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)])
    alt = 2 * area / np.maximum(emax, 1e-15)
    un = n / np.maximum(nl, 1e-300)[:, None]
    return n, un, area, alt


def vertex_normal_nan(X, F, n, nv):
    vn = np.zeros((nv, 3))
    for j in range(3):
        for k in range(3):
            vn[:, j] += np.bincount(F[:, k], weights=n[:, j], minlength=nv)
    used = np.zeros(nv, bool)
    used[F.reshape(-1)] = True
    L = np.linalg.norm(vn, axis=1)
    bad = used & ~(L > 1e-12)
    return int(bad.sum()), int((~np.isfinite(vn)).any(1).sum())


class KMap:
    """表示用サーフェスの頂点を t* の姿で K* の最も近い頂点に対応づける（唇・管の範囲と、巻きの行の印を借りるため）。"""

    def __init__(self, ks, X0):
        D = X0 - ks.O
        a, y, c = D @ ks.t, X0[:, 1], D @ ks.e
        KA, KY = ks.A, ks.Y
        r0 = np.clip(np.searchsorted(ks.c, c), 0, ks.nv - 1)
        best_d = np.full(len(X0), np.inf)
        best_r = np.zeros(len(X0), np.int64)
        best_c = np.zeros(len(X0), np.int64)
        for dr in (-1, 0, 1):
            rr = np.clip(r0 + dr, 0, ks.nv - 1)
            for s in range(0, len(X0), 8192):
                sl = slice(s, s + 8192)
                da = KA[rr[sl]] - a[sl, None]
                dy = KY[rr[sl]] - y[sl, None]
                dc = (ks.c[rr[sl]] - c[sl])[:, None]
                d2 = da * da + dy * dy + dc * dc
                j = d2.argmin(1)
                dd = d2[np.arange(len(j)), j]
                better = dd < best_d[sl]
                idx = np.arange(s, min(s + 8192, len(X0)))[better]
                best_d[idx] = dd[better]
                best_r[idx] = rr[sl][better]
                best_c[idx] = j[better]
        self.kr, self.kc, self.dist = best_r, best_c, np.sqrt(best_d)
        self.region = ks.lipcol[self.kr, self.kc]
        self.curled = ks.is_curled[self.kr]


# ---------------------------------------------------------------- 断面（行の c の面で網を切る）
class Slicer:
    def __init__(self, ks):
        self.O, self.t, self.e = ks.O, ks.t, ks.e
        cm = 0.5 * (ks.c[:-1] + ks.c[1:]) + 1e-4
        self.planes = cm          # 隣り合う K* の行の間の面（頂点をちょうど通らないよう 0.1 mm ずらす）

    def cut(self, X, F, un):
        D = X - self.O
        va, vy, vc = D @ self.t, X[:, 1], D @ self.e
        tc = vc[F]
        cmin, cmax = tc.min(1), tc.max(1)
        order = np.argsort(cmin)
        cs = cmin[order]
        ext = float((cmax - cmin).max())
        nv = len(X)
        res = []
        for c0 in self.planes:
            lo = np.searchsorted(cs, c0 - ext)
            hi = np.searchsorted(cs, c0)
            cand = order[lo:hi]
            cand = cand[cmax[cand] > c0]
            if len(cand) == 0:
                res.append(None)
                continue
            f = F[cand]
            s = tc[cand] - c0
            pos = s >= 0
            cr = pos != np.roll(pos, -1, axis=1)          # 辺 (0,1),(1,2),(2,0)
            k2 = np.argsort(~cr, axis=1, kind="stable")[:, :2]
            ii = f[np.arange(len(f))[:, None], k2]
            jj = f[np.arange(len(f))[:, None], (k2 + 1) % 3]
            si = s[np.arange(len(f))[:, None], k2]
            sj = s[np.arange(len(f))[:, None], (k2 + 1) % 3]
            wgt = si / (si - sj)
            pa = va[ii] + wgt * (va[jj] - va[ii])
            py = vy[ii] + wgt * (vy[jj] - vy[ii])
            eid = np.minimum(ii, jj) * nv + np.maximum(ii, jj)
            res.append(dict(a=pa, y=py, eid=eid, ny=un[cand, 1], face=cand))
        return res


def uf_component(eid, keep, start):
    """線分（端の辺の番号 eid (n, 2)）を端でつなぎ、start を含む成分の線分の印を返す（keep の線分だけ）。"""
    idx = np.nonzero(keep)[0]
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for s in idx:
        a, b = int(eid[s, 0]), int(eid[s, 1])
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    root = find(int(eid[start, 0]))
    out = np.zeros(len(eid), bool)
    for s in idx:
        out[s] = find(int(eid[s, 0])) == root
    return out


def section_metrics(sec):
    """1 つの断面：頂の高さ H、唇先の a、唇先から 0.75 m 奥の鉛直の厚さ（上の面が表・下の面が裏か）、唇と頂の点。"""
    if sec is None:
        return None
    a, y, eid = sec["a"], sec["y"], sec["eid"]
    H = float(y.max())
    out = dict(H=H, a_crest=float(a.reshape(-1)[int(y.argmax())]), tip=None, thick=None, orient_ok=None, pts=None)
    if H < TH["curl_H_m"]:
        return out
    ymax_seg = y.max(1)
    keep = ymax_seg >= 0.3 * H
    start = int(np.argmax(ymax_seg))
    comp = uf_component(eid, keep, start)
    ca, cy = a[comp], y[comp]
    hi = cy >= 0.3 * H
    a_tip = float(ca[hi].max())
    out["tip"] = a_tip
    pts = np.stack([ca[hi], cy[hi]], -1)
    pts = pts[pts[:, 0] >= out["a_crest"] - 2.0]
    out["pts"] = np.unique(np.round(pts, 5), axis=0)
    av = a_tip - TH["lip_behind_m"]
    A1, A2, Y1, Y2 = ca[:, 0], ca[:, 1], cy[:, 0], cy[:, 1]
    xm = ((A1 - av) * (A2 - av) <= 0) & (A1 != A2)
    if xm.sum() >= 2:
        tt = (av - A1[xm]) / (A2[xm] - A1[xm])
        yc = Y1[xm] + tt * (Y2[xm] - Y1[xm])
        nyc = sec["ny"][comp][xm]
        o = np.argsort(-yc)
        yc, sg, ny_ = list(yc[o]), list(np.sign(nyc[o])), list(nyc[o])
        # 小さな折れ（量子化で急な面が鉛直の線を 3 回横切る：表・裏・表が 5 cm の内）は、中の 2 つを消す（偶奇は変わらない）
        nfold = 0
        k = 0
        while k + 2 < len(yc):
            if yc[k] - yc[k + 2] < TH["microfold_m"] and sg[k] == -sg[k + 1] == sg[k + 2]:
                del yc[k + 1:k + 3], sg[k + 1:k + 3], ny_[k + 1:k + 3]
                nfold += 1
                k = max(k - 1, 0)
            else:
                k += 1
        out["microfolds"] = nfold
        if len(yc) >= 2:
            if min(abs(ny_[0]), abs(ny_[1])) >= TH["lip_ny_min"]:
                out["thick"] = float(yc[0] - yc[1])
                out["orient_ok"] = bool(sg[0] > 0 and sg[1] < 0)
                out["thick_y"] = float(yc[0])
            else:
                out["steep"] = float(yc[0] - yc[1])
    return out


def section_crossings(sec):
    """断面の隣でない線分どうしの真の交差（両方 ≥ 5 mm）。a の区間で先にふるう。"""
    if sec is None:
        return 0, 0, None
    a, y, eid = sec["a"], sec["y"], sec["eid"]
    n = len(a)
    amin, amax = a.min(1), a.max(1)
    o = np.argsort(amin)
    amin_s = amin[o]
    kend = np.searchsorted(amin_s, amax[o], side="right")
    cntp = np.maximum(kend - np.arange(n) - 1, 0)
    tot = int(cntp.sum())
    if tot == 0:
        return 0, 0, None
    I = np.repeat(np.arange(n), cntp)
    offs = np.arange(tot) - np.repeat(np.cumsum(cntp) - cntp, cntp)
    J = I + 1 + offs
    si, sj = o[I], o[J]
    share = (eid[si, 0] == eid[sj, 0]) | (eid[si, 0] == eid[sj, 1]) | (eid[si, 1] == eid[sj, 0]) | (eid[si, 1] == eid[sj, 1])
    ok = ~share & (np.maximum(y[si].max(1), y[sj].max(1)) >= np.minimum(y[si].min(1), y[sj].min(1)))
    ok &= (y[si].max(1) >= y[sj].min(1)) & (y[sj].max(1) >= y[si].min(1))
    si, sj = si[ok], sj[ok]
    if len(si) == 0:
        return 0, 0, None
    A1 = np.stack([a[si, 0], y[si, 0]], -1)
    A2 = np.stack([a[si, 1], y[si, 1]], -1)
    B1 = np.stack([a[sj, 0], y[sj, 0]], -1)
    B2 = np.stack([a[sj, 1], y[sj, 1]], -1)
    d, e_ = A2 - A1, B2 - B1
    c1 = d[:, 0] * (B1[:, 1] - A1[:, 1]) - d[:, 1] * (B1[:, 0] - A1[:, 0])
    c2 = d[:, 0] * (B2[:, 1] - A1[:, 1]) - d[:, 1] * (B2[:, 0] - A1[:, 0])
    c3 = e_[:, 0] * (A1[:, 1] - B1[:, 1]) - e_[:, 1] * (A1[:, 0] - B1[:, 0])
    c4 = e_[:, 0] * (A2[:, 1] - B1[:, 1]) - e_[:, 1] * (A2[:, 0] - B1[:, 0])
    hit = (c1 * c2 < 0) & (c3 * c4 < 0)
    if not hit.any():
        return 0, 0, None
    la = np.linalg.norm(d[hit], axis=1)
    lb = np.linalg.norm(e_[hit], axis=1)
    nres = int(((la >= TH["seg_min_m"]) & (lb >= TH["seg_min_m"])).sum())
    k = np.nonzero(hit)[0][0]
    ex = dict(a=r4(A1[k, 0], 3), y=r4(A1[k, 1], 3))
    return int(hit.sum()), nres, ex


def pts_to_segs(P, sec, reach=1.0):
    """点 P (n, 2) から断面の線分への最短距離（点の外接箱 ± reach に掛かる線分だけを見る。遠い点は reach 以上と読む）。"""
    if sec is None or P is None or len(P) == 0:
        return None
    a, y = sec["a"], sec["y"]
    m = ((a.max(1) >= P[:, 0].min() - reach) & (a.min(1) <= P[:, 0].max() + reach) &
         (y.max(1) >= P[:, 1].min() - reach) & (y.min(1) <= P[:, 1].max() + reach))
    if not m.any():
        return np.full(len(P), reach)
    A = np.stack([a[m, 0], y[m, 0]], -1)
    B = np.stack([a[m, 1], y[m, 1]], -1)
    o = np.argsort(np.minimum(A[:, 0], B[:, 0]))
    A, B = A[o], B[o]
    amin = np.minimum(A[:, 0], B[:, 0])
    amax_run = np.maximum.accumulate(np.maximum(A[:, 0], B[:, 0]))
    AB = B - A
    L2 = np.maximum((AB * AB).sum(1), 1e-18)
    best = np.full(len(P), np.inf)
    po = np.argsort(P[:, 0])
    for s in range(0, len(P), 128):
        idx = po[s:s + 128]
        p = P[idx]
        lo = int(np.searchsorted(amax_run, p[:, 0].min() - reach))
        hi = int(np.searchsorted(amin, p[:, 0].max() + reach, side="right"))
        if hi <= lo:
            best[idx] = reach
            continue
        A_, AB_, L2_ = A[lo:hi], AB[lo:hi], L2[lo:hi]
        t = np.clip(((p[:, None, :] - A_[None]) * AB_[None]).sum(-1) / L2_[None], 0, 1)
        q = A_[None] + t[..., None] * AB_[None]
        best[idx] = np.minimum(np.sqrt(((p[:, None, :] - q) ** 2).sum(-1)).min(1), reach)
    return best


# ---------------------------------------------------------------- 1 つの網の検査
def tau_list(spec, stages, surf):
    out = []
    if surf.static:
        return [("tstar", 0.0)]
    if spec == "last3":
        for k in range(31):
            tv = round(-3.0 + 0.1 * k, 4)
            out.append(("τ%+.1f" % tv, tv))
    elif spec:
        for tok in spec.split(","):
            tv = float(tok)
            out.append(("τ%+.3f" % tv, tv))
    for tok in (stages or "").split(","):
        if not tok.strip():
            continue
        name, v = tok.split("=")
        tv = float(v)
        dup = [k for k, (n, t) in enumerate(out) if abs(t - tv) < 1e-9]
        if dup:
            out[dup[0]] = (out[dup[0]][0] + "/" + name.strip(), tv)
        else:
            out.append((name.strip(), tv))
    out = [(n, t) for n, t in out if surf.tau0 - 1e-9 <= t <= surf.tau1 + 1e-9]
    return sorted(out, key=lambda x: x[1])


class Compat:
    """網が K* と同じ 240 × 400 の格子のとき、設計27 の P13 と同じ式（(2)(5a)〜(5g)(6)）を 30 Hz で測る（記録の再現の確かめ）。"""

    def __init__(self, ks, q_max):
        self.ks = ks
        self.q2 = 2 * q_max
        self.thr_e = np.minimum(TH["edge_min_m"], ks.Lrow_K - 2 * q_max)
        self.rows_k = ks.curled_idx
        self.sr_r = np.array([r for r, j in ks.seam])
        self.sr_j = np.array([j for r, j in ks.seam])
        self.ref_n = None
        self.ref_ok = None
        self.prev_g = []
        self.r = dict(acc=[0.0, None], tri_min_region=[np.inf, None], ring_min=[np.inf, None], edge_min=[np.inf, None],
                      viol={k: dict(n=0, frames=0, tau_range=None) for k in ("5a", "5b", "5c", "5d", "5e", "5g", "6")},
                      st_row=[np.inf, 0.0], st_x=[np.inf, 0.0], seam=[np.inf, 0.0], flips=dict(resolvable=0, region=0, all=0, first=None))

    def _v(self, key, n, tau):
        e = self.r["viol"][key]
        if n > 0:
            e["n"] += int(n)
            e["frames"] += 1
            tr = e["tau_range"]
            e["tau_range"] = [round(tau, 4), round(tau, 4)] if tr is None else [min(tr[0], round(tau, 4)), max(tr[1], round(tau, 4))]

    def step(self, Xflat, tau):
        ks = self.ks
        X = Xflat.reshape(ks.nv, ks.nu, 3)
        Xg = X[self.rows_k]
        self.prev_g.append(Xg)
        if len(self.prev_g) == 3:
            d2 = np.linalg.norm(self.prev_g[2] - 2 * self.prev_g[1] + self.prev_g[0], axis=-1)
            i = np.unravel_index(int(d2.argmax()), d2.shape)
            if d2[i] > self.r["acc"][0]:
                self.r["acc"] = [float(d2[i]), dict(row=int(self.rows_k[i[0]]), col=int(i[1]), tau=round(tau - 1.0 / HZ, 4))]
            self.prev_g.pop(0)
        nrm = G27.tri_normals(X)
        nl = np.linalg.norm(nrm, axis=-1)
        ar = 0.5 * nl
        region3 = np.broadcast_to(ks.tri_mask[..., None], ar.shape)
        arr = np.where(region3, ar, np.inf)
        i = np.unravel_index(int(arr.argmin()), arr.shape)
        if arr[i] < self.r["tri_min_region"][0]:
            self.r["tri_min_region"] = [float(arr[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(tau, 4))]
        self._v("5a", int((arr < TH["tri_area_m2"]).sum()), tau)
        ar6 = np.where(np.broadcast_to(ks.ring_mask[..., None], ar.shape), ar, np.inf)
        self.r["ring_min"][0] = min(self.r["ring_min"][0], float(ar6.min()))
        self._v("6", int((ar6 <= 1e-10).sum()), tau)
        un_ = nrm / np.maximum(nl[..., None], 1e-15)
        valid = ar > 1e-10
        if self.ref_n is not None:
            dots = (un_ * self.ref_n).sum(-1)
            bad = valid & self.ref_ok & (dots <= 0)
            br = bad & ks.tri_resolvable
            bg = bad & region3
            self._v("5g", int((br | bg).sum()), tau)
            fl = self.r["flips"]
            fl["resolvable"] += int(br.sum())
            fl["region"] += int(bg.sum())
            fl["all"] += int(bad.sum())
            if fl["first"] is None and (br | bg).any():
                i = np.unravel_index(int(np.argmax(br | bg)), bad.shape)
                fl["first"] = dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(tau, 4))
            self.ref_n = np.where(valid[..., None], un_, self.ref_n)
            self.ref_ok = self.ref_ok | valid
        else:
            self.ref_n = un_.copy()
            self.ref_ok = valid.copy()
        Lr = np.linalg.norm(np.diff(X, axis=1), axis=-1)
        v = np.where(ks.row_edge_mask, Lr, np.inf)
        i = np.unravel_index(int(v.argmin()), v.shape)
        if v[i] < self.r["edge_min"][0]:
            self.r["edge_min"] = [float(v[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(tau, 4))]
        mg = np.where(ks.row_edge_mask, Lr - self.thr_e, np.inf)
        self._v("5b", int((mg < 0).sum()), tau)
        q2 = self.q2

        def ratio(L, LK, key, acc):
            raw = L / np.maximum(LK, 1e-9)
            lo_ = (L + q2) / np.maximum(LK, 1e-9)
            hi_ = np.maximum(L - q2, 0) / np.maximum(LK, 1e-9)
            acc[0] = min(acc[0], float(raw.min()))
            acc[1] = max(acc[1], float(raw.max()))
            lb, hb = (TH["seam_lo"], TH["seam_hi"]) if key == "5e" else (TH["stretch_lo"], TH["stretch_hi"])
            self._v(key, int((lo_ < lb).sum() + (hi_ > hb).sum()), tau)
        ratio(Lr[ks.row_edge_mask], ks.Lrow_K[ks.row_edge_mask], "5c", self.r["st_row"])
        Lv = np.linalg.norm(X[1:] - X[:-1], axis=-1)
        Ld = np.linalg.norm(X[1:, :-1] - X[:-1, 1:], axis=-1)
        ratio(np.concatenate([Lv[ks.vedge_mask], Ld[ks.dedge_mask]]), np.concatenate([ks.Lv_K[ks.vedge_mask], ks.Ld_K[ks.dedge_mask]]), "5d", self.r["st_x"])
        ratio(Lr[self.sr_r, self.sr_j], ks.Lrow_K[self.sr_r, self.sr_j], "5e", self.r["seam"])

    def result(self):
        r = self.r
        v = r["viol"]
        return {
            "(2) 地面の二階差分（30 Hz、全巻きの行の全点）_m": dict(value=r4(r["acc"][0], 6), threshold="≤ %.4f（2 g）" % TH["acc_m"], pass_=r["acc"][0] <= TH["acc_m"], at=r["acc"][1]),
            "(5a) 唇・管の三角形の面積の最小_m2": dict(value=r4(r["tri_min_region"][0], 6), threshold="≥ 1e-04", pass_=v["5a"]["n"] == 0, at=r["tri_min_region"][1]),
            "(5b) 行の方向の辺の最小_m": dict(value=r4(r["edge_min"][0], 6), threshold="≥ 0.005（K* で近い辺は K* − 2q）", pass_=v["5b"]["n"] == 0, at=r["edge_min"][1], viol=v["5b"]),
            "(5c) 行の方向の伸び（K* に対する比）": dict(value=[r4(r["st_row"][0], 3), r4(r["st_row"][1], 3)], threshold="0.05〜4（±2q を差し引いて判定）", pass_=v["5c"]["n"] == 0, viol=v["5c"]),
            "(5d) 行の間の伸び（縦と斜め）": dict(value=[r4(r["st_x"][0], 3), r4(r["st_x"][1], 3)], threshold="0.05〜4", pass_=v["5d"]["n"] == 0, viol=v["5d"]),
            "(5e) rim と管の天井の継ぎ目の比": dict(value=[r4(r["seam"][0], 3), r4(r["seam"][1], 3)], threshold="0.25〜4", pass_=v["5e"]["n"] == 0, viol=v["5e"]),
            "(5g) 面の反転（設計27 の数え方）": dict(value=int(r["flips"]["resolvable"] + r["flips"]["region"]), threshold="0", pass_=v["5g"]["n"] == 0,
                                                   at=dict(resolvable=r["flips"]["resolvable"], region=r["flips"]["region"], union=int(v["5g"]["n"]), all_incl_slivers=r["flips"]["all"],
                                                           first=r["flips"]["first"], tau_range=v["5g"]["tau_range"])),
            "(6) 唇・管の 1 環の面積の最小_m2": dict(value=r4(r["ring_min"][0], 6), threshold="> 0", pass_=v["6"]["n"] == 0),
        }


def run_surface(surf, ks, kstar_slicer, args, ref=None, log=print):
    t_clock = time.time()
    rep = dict(label=surf.label, info=surf.info())
    X0 = surf.world(0.0)
    topo, T = topology(surf.F, surf.nv, X0, (surf.rows, surf.cols) if surf.grid else None)
    rep["topology"] = topo
    F = surf.F
    E = T["E"]
    km = KMap(ks, X0)
    compat_grid = surf.grid and surf.rows == ks.nv and surf.cols == ks.nu and bool(np.all(km.kr.reshape(ks.nv, ks.nu) == np.arange(ks.nv)[:, None]))
    rep["kstar_map"] = dict(mapped_vertices=int(len(km.kr)), region_vertices=int(km.region.sum()), curled_vertices=int(km.curled.sum()),
                            map_dist_max_m=r4(km.dist.max(), 4), map_dist_p99_m=r4(np.percentile(km.dist, 99), 4), grid_equals_kstar=compat_grid)
    # 辺の種類：格子なら添字、そうでなければ t* の向き（波峰線方向 e の成分 ≥ 0.5 なら行の間）
    if surf.grid:
        er, ec = E // surf.cols, E % surf.cols
        cross = er[:, 0] != er[:, 1]
    else:
        d = X0[E[:, 1]] - X0[E[:, 0]]
        cross = np.abs(d @ ks.e) >= 0.5 * np.maximum(np.linalg.norm(d, axis=1), 1e-12)
    e_reg = km.region[E[:, 0]] | km.region[E[:, 1]]
    e_cur = km.curled[E[:, 0]] & km.curled[E[:, 1]]
    m_row = e_reg & ~cross
    m_x = e_reg & cross & e_cur
    L0 = np.linalg.norm(X0[E[:, 1]] - X0[E[:, 0]], axis=1)
    q2 = 2 * surf.q_max
    thr_e = np.minimum(TH["edge_min_m"], L0 - q2)
    f_reg = km.region[F].any(1)
    v_cur = km.curled
    n0, un0, area0, alt0 = face_geom(X0, F)
    f_res = alt0 >= TH["resolvable_alt_m"]     # t* の姿で最小の高さ ≥ 5 mm（設計27 の K* の読みと同じ考え）

    # ---------------- 30 Hz の通し（包みだけ）
    sweep = None
    if not surf.static and args.sweep:
        nt = int(math.floor(-surf.tau0 * HZ + 1e-6))
        taus = -np.arange(nt, -1, -1) / HZ
        compat = Compat(ks, surf.q_max) if compat_grid else None
        S = dict(step=[0.0, None], acc_all=[0.0, None], acc_curled=[0.0, None], flips=0, flips_frames=0, flips_first=None, flips_region_all=0, flips_all=0,
                 flips_tau=None, edge_min=[np.inf, None], edge_viol=0, st_row=[np.inf, 0.0, 0], st_x=[np.inf, 0.0, 0], nan=0, degenerate_max=0,
                 per_tau={})
        prev = []
        prev_un = prev_alt = prev_area = None
        for k, tau in enumerate(taus):
            X = surf.world(float(tau))
            loc = X - surf.origin(float(tau))
            if not np.isfinite(X).all():
                S["nan"] += 1
            prev.append((X, loc))
            if len(prev) >= 2:
                d = np.linalg.norm(prev[-1][1] - prev[-2][1], axis=1)
                i = int(d.argmax())
                if d[i] > S["step"][0]:
                    S["step"] = [float(d[i]), dict(vertex=i, tau=round(float(tau), 4))]
            if len(prev) == 3:
                d2 = np.linalg.norm(prev[2][0] - 2 * prev[1][0] + prev[0][0], axis=1)
                i = int(d2.argmax())
                if d2[i] > S["acc_all"][0]:
                    S["acc_all"] = [float(d2[i]), dict(vertex=i, tau=round(float(tau) - 1.0 / HZ, 4))]
                dc = np.where(v_cur, d2, -1.0)
                i = int(dc.argmax())
                if dc[i] > S["acc_curled"][0]:
                    S["acc_curled"] = [float(dc[i]), dict(vertex=i, tau=round(float(tau) - 1.0 / HZ, 4))]
                prev.pop(0)
            n, un, area, alt = face_geom(X, F)
            S["degenerate_max"] = max(S["degenerate_max"], int((area < TH["degenerate_area_m2"]).sum()))
            if prev_un is not None:
                dots = (un * prev_un).sum(1)
                flip = (area > 1e-10) & (prev_area > 1e-10) & (dots <= 0)
                fl = flip & (f_res | f_reg)
                nfl = int(fl.sum())
                S["flips"] += nfl
                S["flips_region_all"] += int((flip & f_reg).sum())
                S["flips_all"] += int(flip.sum())
                if nfl:
                    S["flips_frames"] += 1
                    tr = S["flips_tau"]
                    S["flips_tau"] = [round(float(tau), 4)] * 2 if tr is None else [tr[0], round(float(tau), 4)]
                    if S["flips_first"] is None:
                        fi = int(np.nonzero(fl)[0][0])
                        S["flips_first"] = dict(face=fi, tau=round(float(tau), 4), grid_rc=face_rc(surf, fi))
            prev_un, prev_alt, prev_area = un, alt, area
            L = np.linalg.norm(X[E[:, 1]] - X[E[:, 0]], axis=1)
            v = np.where(m_row, L, np.inf)
            i = int(v.argmin())
            if v[i] < S["edge_min"][0]:
                S["edge_min"] = [float(v[i]), dict(edge=[int(E[i, 0]), int(E[i, 1])], tau=round(float(tau), 4), len_tstar_m=r4(L0[i], 5),
                                                   grid_rc=vert_rc(surf, int(E[i, 0])))]
            S["edge_viol"] += int((m_row & (L < thr_e)).sum())
            for key, m in (("st_row", m_row), ("st_x", m_x)):
                raw = L[m] / np.maximum(L0[m], 1e-9)
                if len(raw):
                    S[key][0] = min(S[key][0], float(raw.min()))
                    S[key][1] = max(S[key][1], float(raw.max()))
                    lo_ = (L[m] + q2) / np.maximum(L0[m], 1e-9)
                    hi_ = np.maximum(L[m] - q2, 0) / np.maximum(L0[m], 1e-9)
                    S[key][2] += int((lo_ < TH["stretch_lo"]).sum() + (hi_ > TH["stretch_hi"]).sum())
            if compat is not None:
                compat.step(X, float(tau))
            if k % 60 == 0:
                log("    [%s] 30 Hz τ=%.2f（%d/%d、%.0f s）" % (surf.label, tau, k, len(taus), time.time() - t_clock))
        sweep = dict(frames=len(taus), tau_range=[float(taus[0]), 0.0],
                     step_local_m=dict(value=r4(S["step"][0], 4), threshold="< %.1f" % TH["step_m"], pass_=S["step"][0] < TH["step_m"], at=S["step"][1]),
                     acc_all_m=dict(value=r4(S["acc_all"][0], 5), threshold="≤ %.4f（2 g）" % TH["acc_m"], pass_=S["acc_all"][0] <= TH["acc_m"], at=S["acc_all"][1]),
                     acc_curled_m=dict(value=r4(S["acc_curled"][0], 5), threshold="≤ %.4f（2 g）" % TH["acc_m"], pass_=S["acc_curled"][0] <= TH["acc_m"], at=S["acc_curled"][1]),
                     flips_prev_frame=dict(value=S["flips"], frames=S["flips_frames"], tau_range=S["flips_tau"], first=S["flips_first"],
                                           region=S["flips_region_all"], all_incl_slivers=S["flips_all"],
                                           threshold="0（t* で最小の高さ ≥ 5 mm の三角形と唇・管の三角形。前のコマと比べる）", pass_=S["flips"] == 0),
                     region_row_edge_min_m=dict(value=r4(S["edge_min"][0], 5), violations=S["edge_viol"], threshold="≥ 0.005（t* で近い辺は t* − 2q）",
                                                pass_=S["edge_viol"] == 0, at=S["edge_min"][1]),
                     region_stretch_row=dict(value=[r4(S["st_row"][0], 3), r4(S["st_row"][1], 3)], violations=S["st_row"][2], threshold="0.05〜4（t* の長さに対する比）",
                                             pass_=S["st_row"][2] == 0),
                     region_stretch_cross=dict(value=[r4(S["st_x"][0], 3), r4(S["st_x"][1], 3)], violations=S["st_x"][2], threshold="0.05〜4", pass_=S["st_x"][2] == 0),
                     nan_frames=S["nan"], degenerate_faces_max=S["degenerate_max"])
        if compat is not None:
            sweep["compat_P13_ds27"] = compat.result()
    rep["sweep30"] = sweep

    # ---------------- τ の一覧の各コマ
    frames = []
    TL = tau_list(args.taus, args.stages, surf)
    ref_sec_cache = {}
    Xs_for_blender = []
    for name, tau in TL:
        X = surf.world(tau)
        n, un, area, alt = face_geom(X, F)
        fr = dict(name=name, tau=tau)
        fr["nan_positions"] = int((~np.isfinite(X)).any(1).sum())
        nb, nnan = vertex_normal_nan(X, F, n, surf.nv)
        fr["vertex_normals_undefined"] = nb
        fr["vertex_normals_nan"] = nnan
        fr["degenerate_faces"] = int((area < TH["degenerate_area_m2"]).sum())
        fr["zero_area_faces"] = int((area < 1e-10).sum())
        # 折れ返り（隣と逆向きの面）
        ef = T["edge_faces"]
        res = (alt[ef[:, 0]] >= TH["resolvable_alt_m"]) & (alt[ef[:, 1]] >= TH["resolvable_alt_m"])
        dd = (un[ef[:, 0]] * un[ef[:, 1]]).sum(1)
        fold = res & (dd < TH["fold_dot"])
        fr["fold_edges_gt120deg"] = int(fold.sum())
        fr["fold_edges_gt150deg"] = int((res & (dd < -0.866)).sum())
        fr["dihedral_max_deg"] = r4(math.degrees(math.acos(max(-1.0, min(1.0, float(dd[res].min()))))) if res.any() else None, 1)
        if fold.any():
            fi = int(ef[np.nonzero(fold)[0][0], 0])
            fr["fold_first"] = dict(face=fi, grid_rc=face_rc(surf, fi))
        # 前のコマ（1/30 s 前）と比べた反転
        if not surf.static and tau - 1.0 / HZ >= surf.tau0 - 1e-9:
            Xp = surf.world(tau - 1.0 / HZ)
            _, unp, areap, altp = face_geom(Xp, F)
            dots = (un * unp).sum(1)
            flip = (area > 1e-10) & (areap > 1e-10) & (dots <= 0)
            fr["flips_vs_prev_frame"] = int((flip & (f_res | f_reg)).sum())
            fr["flips_vs_prev_frame_all_incl_slivers"] = int(flip.sum())
        # 断面
        secs = kstar_slicer.cut(X, F, un)
        SM = [section_metrics(s) for s in secs]
        xs = [section_crossings(s) for s in secs]
        fr["section_self_crossings"] = int(sum(x[0] for x in xs))
        fr["section_self_crossings_ge5mm"] = int(sum(x[1] for x in xs))
        exs = [(k, x[2]) for k, x in enumerate(xs) if x[2] is not None]
        if exs:
            fr["section_crossing_example"] = dict(plane_c=r4(kstar_slicer.planes[exs[0][0]], 3), **exs[0][1])
        lips = [(k, m) for k, m in enumerate(SM) if m is not None and m["thick"] is not None]
        fr["lip_sections"] = len(lips)
        fr["steep_pairs_skipped"] = int(sum(1 for m in SM if m is not None and m.get("steep") is not None))
        if lips:
            th = np.array([m["thick"] for k, m in lips])
            kk = int(th.argmin())
            fr["lip_thick_min_m"] = r4(th.min(), 3)
            fr["lip_thick_min_at_c"] = r4(kstar_slicer.planes[lips[kk][0]], 2)
            fr["lip_thin_sections"] = int((th < TH["lip_thick_m"]).sum())
            fr["lip_orientation_bad_sections"] = int(sum(1 for k, m in lips if not m["orient_ok"]))
        else:
            fr["lip_thick_min_m"] = None
            fr["lip_thin_sections"] = 0
            fr["lip_orientation_bad_sections"] = 0
        Hs = np.array([m["H"] if m is not None else np.nan for m in SM])
        fr["crest_max_m"] = r4(np.nanmax(Hs), 3)
        # 波頭の欠落（基準の包みと同じ τ・同じ面）
        if ref is not None:
            key = round(tau, 6)
            if key not in ref_sec_cache:
                Xr = ref.world(tau)
                _, unr, _, _ = face_geom(Xr, ref.F)
                ref_sec_cache[key] = [section_metrics(s) for s in kstar_slicer.cut(Xr, ref.F, unr)]
            RM = ref_sec_cache[key]
            dH, dT, dev, dth = [], [], [], []
            for k in range(len(SM)):
                m, rm = SM[k], RM[k]
                if m is None or rm is None:
                    continue
                if rm["H"] >= TH["curl_H_m"]:
                    dH.append((rm["H"] - m["H"], k))
                    if rm["tip"] is not None and m["tip"] is not None:
                        dT.append((rm["tip"] - m["tip"], k))
                    if rm["pts"] is not None and len(rm["pts"]):
                        dd_ = pts_to_segs(rm["pts"], secs[k])
                        if dd_ is not None:
                            dev.append((float(dd_.max()), k))
                    if rm["thick"] is not None and m["thick"] is not None:
                        dth.append((rm["thick"] - m["thick"], k))

            def worst(lst):
                if not lst:
                    return None
                v, k = max(lst, key=lambda x: x[0])
                return dict(value=r4(v, 4), plane_c=r4(kstar_slicer.planes[k], 2))
            fr["vs_ref"] = dict(crest_loss_m=worst(dH), crest_gain_m=worst([(-v, k) for v, k in dH]), tip_retreat_m=worst(dT),
                                lip_deviation_m=worst(dev), lip_thinning_m=worst(dth), sections=len(dH))
        frames.append(fr)
        if args.blender:
            Xs_for_blender.append(X.astype(np.float32))
        log("    [%s] %s τ=%.3f：断面の交差 %d、唇の厚さの最小 %s m（%d 断面）、折れ返り %d（%.0f s）" % (
            surf.label, name, tau, fr["section_self_crossings"], fr["lip_thick_min_m"], fr["lip_sections"], fr["fold_edges_gt120deg"], time.time() - t_clock))
    rep["frames"] = frames
    rep["blender"] = None
    if args.blender:
        refpack = None
        if ref is not None:
            if getattr(ref, "_km", None) is None:
                ref._km = KMap(ks, ref.world(0.0))
            ridx = np.nonzero(ref._km.region)[0]
            RV = np.stack([ref.world(t)[ridx] for n_, t in TL], 0).astype(np.float32)
            RVall = np.stack([ref.world(t) for n_, t in TL], 0).astype(np.float32)
            refpack = dict(RV=RV, RVall=RVall, RF=ref.F.astype(np.int32), ref_idx=ridx.astype(np.int64),
                           subj_idx=np.nonzero(km.region)[0].astype(np.int64))
        rep["blender"] = run_blender(surf, TL, np.stack(Xs_for_blender, 0), T, args, log, refpack)
        bf = {b["name"]: b for b in rep["blender"].get("frames", [])} if rep["blender"] else {}
        for fr in frames:
            b = bf.get(fr["name"])
            if b:
                fr["blender"] = b
    rep["runtime_s"] = round(time.time() - t_clock, 1)
    rep["verdicts"] = verdicts(rep)
    return rep


def face_rc(surf, fi):
    if not surf.grid:
        return None
    q = fi // 2
    return [int(q // (surf.cols - 1)), int(q % (surf.cols - 1)), int(fi % 2)]


def vert_rc(surf, vi):
    if not surf.grid:
        return None
    return [int(vi // surf.cols), int(vi % surf.cols)]


# ---------------------------------------------------------------- Blender
def run_blender(surf, TL, Xs, T, args, log, refpack=None):
    os.makedirs(args.out, exist_ok=True)
    seat = json.load(open(SEAT_JSON, encoding="utf-8"))
    eye = np.array(seat["seat"]["eye_world"], float)
    look = np.array(seat["view"]["qa_hemisphere_look_world"], float)
    npz = os.path.join(args.out, "%s_blender_in.npz" % surf.label)
    outj = os.path.join(args.out, "%s_blender.json" % surf.label)
    inner = T["inner"]
    inner_cat = np.concatenate(inner) if inner else np.zeros(0, np.int64)
    inner_off = np.cumsum([0] + [len(x) for x in inner]).astype(np.int64)
    np.savez(npz, V=Xs, F=surf.F.astype(np.int32), taus=np.array([t for n, t in TL]), names=np.array([n for n, t in TL]),
             outer=T["outer"].astype(np.int64), inner_cat=inner_cat.astype(np.int64), inner_off=inner_off,
             eye=eye, look=look, sea_y=np.array(args.sea_y), cut_tol=np.array(0.12), n_rays=np.array(args.rays),
             selfx=np.array(1 if args.selfx else 0), res_alt=np.array(TH["resolvable_alt_m"]), label=np.array(surf.label),
             **(refpack or {}))
    cmd = [args.blender_exe, "--background", "--factory-startup", "--python-exit-code", "1", "--python", BLENDER_QA, "--", npz, outj]
    t0 = time.time()
    log("    [%s] Blender：%d コマ、射線 %d 本 …" % (surf.label, len(TL), args.rays))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    logp = os.path.join(args.out, "%s_blender.log" % surf.label)
    with open(logp, "w", encoding="utf-8", newline="\n") as f:
        f.write(p.stdout)
        f.write("\n---- stderr ----\n")
        f.write(p.stderr)
    if p.returncode != 0 or not os.path.isfile(outj):
        log("    [%s] Blender が失敗しました（%s）" % (surf.label, rel(logp)))
        return dict(error="Blender の終了コード %d。ログ %s" % (p.returncode, rel(logp)))
    B = json.load(open(outj, encoding="utf-8"))
    B["runtime_s"] = round(time.time() - t0, 1)
    B["input_npz"] = rel(npz)
    if not args.keep_npz:
        try:
            os.remove(npz)
        except OSError:
            pass
        B["input_npz"] += "（消した）"
    log("    [%s] Blender 終わり（%.0f s）" % (surf.label, time.time() - t0))
    return B


# ---------------------------------------------------------------- 判定
def verdicts(rep):
    t = rep["topology"]
    fr = rep["frames"]
    V = {}

    def put(key, value, thr, ok, note=None):
        V[key] = dict(value=value, threshold=thr, pass_=bool(ok) if ok is not None else None, note_ja=note)
    put("非多様体の辺", t["nonmanifold_edges_gt2"], "0", t["nonmanifold_edges_gt2"] == 0)
    exp = t.get("boundary_edges_expected_grid_perimeter")
    put("縁の輪（外周のほか＝継ぎ目・穴）", t["inner_loops"], "0（117）", t["inner_loops"] == 0 and t["boundary_vertex_branching"] == 0 and t["coincident_boundary_vertex_pairs_unjoined"] == 0,
        "縁の辺 %d（格子の外周 %s）、辺でつながらずに重なった縁の頂点の組 %d" % (t["boundary_edges"], exp, t["coincident_boundary_vertex_pairs_unjoined"]))
    put("面の向きの反転（隣と巻き方向が食い違う辺）", t["winding_inconsistent_edges"], "0", t["winding_inconsistent_edges"] == 0)
    put("使われない頂点・添字の潰れた面", [t["unreferenced_vertices"], t["index_degenerate_faces"]], "0", t["unreferenced_vertices"] == 0 and t["index_degenerate_faces"] == 0)
    nan = max((f["nan_positions"] + f["vertex_normals_nan"] for f in fr), default=0)
    put("位置・頂点法線の NaN（コマの最大）", nan, "0", nan == 0)
    und = max((f["vertex_normals_undefined"] for f in fr), default=0)
    put("決まらない頂点法線（周りの面がすべて面積 0、コマの最大）", und, "0", und == 0,
        "設計27 のシェーダー（DS27Normal）は長さ 0 の法線を +Y に置き換えるので NaN にはならない。16 ビットの量子化で詰まった列がつぶれた所")
    fold = max((f["fold_edges_gt120deg"] for f in fr), default=0)
    put("隣と逆向きの面（二面角 > 120°、コマの最大）", fold, "0", fold == 0)
    if any("flips_vs_prev_frame" in f for f in fr):
        fp = sum(f.get("flips_vs_prev_frame", 0) for f in fr)
        put("前のコマと比べた面の反転（一覧のコマの和）", fp, "0", fp == 0)
    sx = sum(f["section_self_crossings_ge5mm"] for f in fr)
    put("自己交差（行の断面、線分 ≥ 5 mm、コマの和）", sx, "0", sx == 0)
    lips = [f for f in fr if f["lip_sections"]]
    if lips:
        mn = min(f["lip_thick_min_m"] for f in lips)
        thin = sum(f["lip_thin_sections"] for f in lips)
        ob = sum(f["lip_orientation_bad_sections"] for f in lips)
        put("唇先の厚さ（唇先から 0.75 m 奥の鉛直）の最小_m", mn, "≥ 0.3", mn >= TH["lip_thick_m"],
            "0.3 m 未満の断面 %d（コマの和）、上面が表・下面が裏でない断面 %d" % (thin, ob))
    vr = [f["vs_ref"] for f in fr if f.get("vs_ref")]
    if vr:
        def mx(k):
            vals = [v[k]["value"] for v in vr if v.get(k)]
            return max(vals) if vals else None
        cl, tr, dv = mx("crest_loss_m"), mx("tip_retreat_m"), mx("lip_deviation_m")
        tol = TH["crest_tol_m"]
        d3 = None
        bl_ = rep.get("blender")
        if bl_ and not bl_.get("error"):
            vals = [b["ref_dev"]["ref_to_subject_max_m"] for b in bl_.get("frames", []) if b.get("ref_dev")]
            d3 = max(vals) if vals else None
        put("波頭の欠落：断面の頂の高さの低下／基準の唇・管の点から網までの 3 次元の距離（最大）_m", [cl, d3], "≤ %.2f（暫定）" % tol,
            all(v is None or v <= tol for v in (cl, d3)),
            "断面の値（記録）：唇先の後退 %s m、唇の形の片側の距離 %s m。断面の値は、行の間隔が狭く行の間で形が大きくずれる所（K* の唇・rim の列の割り付けが飛ぶ行）で切り口がずれやすいので、判定は 3 次元の距離で行う" % (fmt(tr), fmt(dv)))
    bl = rep.get("blender")
    if bl and not bl.get("error"):
        bf = bl.get("frames", [])
        tot = lambda k: sum(b["rays"].get(k, 0) for b in bf)
        put("座席 v1 の射線：穴（コマの和）", tot("hole"), "0", tot("hole") == 0)
        put("座席 v1 の射線：開いた背面（コマの和）", tot("wave_back_open"), "0", tot("wave_back_open") == 0)
        bt = [b for b in bf if abs(b["tau"]) < 1e-9]
        ct = sum(b["rays"].get("cut_end", 0) + b["rays"].get("under_edge", 0) for b in bt)
        put("座席 v1 の射線：切断端＋縁の下のすき間（外周、t* のコマ）", ct if bt else None, "0", (ct == 0) if bt else None,
            "切断端＝外周の縁の頂点が平らな海 +0.12 m より高い面に当たった射線（美術優先26 と同じ数え方）。縁の下＝その高さの縁の下をくぐった射線")
        bo = [b for b in bf if abs(b["tau"]) >= 1e-9]
        if bo:
            put("座席 v1 の射線：切断端／縁の下のすき間（外周、t* より前のコマの和。記録）",
                [sum(b["rays"].get("cut_end", 0) for b in bo), sum(b["rays"].get("under_edge", 0) for b in bo)], "記録", None,
                "外周の縁が周りの波（うねり・搬送波）で平らな仮置きの海より持ち上がる所。周りの海とのつなぎは設計30 の範囲。縁の高さの範囲はコマごとの JSON")
        put("座席 v1 の射線：継ぎ目の切断（117、コマの和）", tot("seam_cut"), "0", tot("seam_cut") == 0)
        si = sum(b.get("self_intersections", 0) or 0 for b in bf)
        sia = sum(b.get("self_intersections_all", 0) or 0 for b in bf)
        put("自己交差（3 次元、BVH の重なり、コマの和）", si, "0", si == 0, "両方の面の最小の高さ ≥ 5 mm の組。細い面を含む全部は %d" % sia)
        dn = sum(b.get("down_facing_open_sky", 0) for b in bf)
        dna = sum(b.get("down_facing_open_sky_all", 0) for b in bf)
        put("下を向き、上に網のない面（面の向きの反転、コマの和）", dn, "0", dn == 0, "最小の高さ ≥ 5 mm の面。細い面を含む全部は %d" % dna)
        so = tot("sea_over_sheet")
        put("座席 v1 の射線：平らな海が網の上にある所（記録）", so, "記録", None, "網が平らな仮置きの海 y = −0.07 m より低い所（周りの海の範囲）")
    sw = rep.get("sweep30")
    if sw:
        put("30 Hz：波の枠の 1 コマの変位_m", sw["step_local_m"]["value"], sw["step_local_m"]["threshold"], sw["step_local_m"]["pass_"])
        put("30 Hz：地面の二階差分（全頂点）_m", sw["acc_all_m"]["value"], sw["acc_all_m"]["threshold"], sw["acc_all_m"]["pass_"])
        put("30 Hz：前のコマと比べた面の反転（通し）", sw["flips_prev_frame"]["value"], "0", sw["flips_prev_frame"]["pass_"])
        put("30 Hz：唇・管の行の方向の辺の最短_m", sw["region_row_edge_min_m"]["value"], sw["region_row_edge_min_m"]["threshold"], sw["region_row_edge_min_m"]["pass_"],
            "違反 %d（辺 × コマ）" % sw["region_row_edge_min_m"]["violations"])
        put("30 Hz：唇・管の伸び（t* に対する比、行の方向／行の間）", [sw["region_stretch_row"]["value"], sw["region_stretch_cross"]["value"]], "0.05〜4",
            sw["region_stretch_row"]["pass_"] and sw["region_stretch_cross"]["pass_"],
            "違反 %d／%d（辺 × コマ）" % (sw["region_stretch_row"]["violations"], sw["region_stretch_cross"]["violations"]))
    return V


# ---------------------------------------------------------------- 書き出し
def jdump(o):
    def conv(x):
        if isinstance(x, dict):
            return {(k[:-1] if isinstance(k, str) and k.endswith("_") and k == "pass_" else k): conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v) for v in x]
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return r4(float(x), 6)
        if isinstance(x, np.ndarray):
            return conv(x.tolist())
        if isinstance(x, float):
            return x if math.isfinite(x) else None
        if isinstance(x, (np.bool_,)):
            return bool(x)
        return x
    return conv(o)


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "合格" if v else "不合格"
    if isinstance(v, float):
        return ("%.4g" % v)
    if isinstance(v, list):
        return "／".join(fmt(x) for x in v)
    return str(v)


def write_md(path, reps, title, notes):
    L = ["# " + title, ""]
    L += notes
    L.append("")
    L.append("## 判定の表（網ごと）")
    L.append("")
    keys = []
    for r in reps:
        for k in r["verdicts"]:
            if k not in keys:
                keys.append(k)
    L.append("| 項目 | しきい値 | " + " | ".join(r["label"] for r in reps) + " |")
    L.append("| --- | --- | " + " | ".join("---" for _ in reps) + " |")
    for k in keys:
        thr = next((r["verdicts"][k]["threshold"] for r in reps if k in r["verdicts"]), "")
        cells = []
        for r in reps:
            v = r["verdicts"].get(k)
            if v is None:
                cells.append("—")
                continue
            p = v["pass_"]
            mark = "" if p is None else ("（合格）" if p else "（**不合格**）")
            cells.append(fmt(v["value"]) + mark)
        L.append("| %s | %s | %s |" % (k, thr, " | ".join(cells)))
    L.append("")
    for r in reps:
        L.append("## %s" % r["label"])
        L.append("")
        inf = r["info"]
        L.append("- 網：%s、%s 行 × %s 列、頂点 %s、面 %s。%s" % (inf.get("kind"), inf.get("rows", "—"), inf.get("cols", "—"), inf.get("vertices"), inf.get("faces"),
                                                            inf.get("dir") or inf.get("parent") or inf.get("defect_ja") or ""))
        t = r["topology"]
        L.append("- 位相：辺 %d、非多様体 %d、縁の辺 %d（格子の外周 %s）、縁の輪 %d（外周のほか %d）、巻き方向の食い違い %d、使われない頂点 %d、辺でつながらずに重なった縁の頂点の組 %d。" % (
            t["edges"], t["nonmanifold_edges_gt2"], t["boundary_edges"], t.get("boundary_edges_expected_grid_perimeter", "—"), t["boundary_loops"],
            t["inner_loops"], t["winding_inconsistent_edges"], t["unreferenced_vertices"], t["coincident_boundary_vertex_pairs_unjoined"]))
        km = r["kstar_map"]
        L.append("- K* への対応：唇・管の頂点 %d、巻きの行の頂点 %d、対応の距離の最大 %s m（K* と同じ格子：%s）。" % (
            km["region_vertices"], km["curled_vertices"], km["map_dist_max_m"], "はい" if km["grid_equals_kstar"] else "いいえ"))
        sw = r.get("sweep30")
        if sw:
            L.append("- 30 Hz の通し（%d コマ）：1 コマの変位 %s m、二階差分 全頂点 %s m・巻きの行 %s m、反転 %d（%s）、唇・管の行の方向の辺の最短 %s m（違反 %d）、伸び 行 %s（違反 %d）・行の間 %s（違反 %d）、面積 0 に近い面の最大 %d。" % (
                sw["frames"], sw["step_local_m"]["value"], sw["acc_all_m"]["value"], sw["acc_curled_m"]["value"], sw["flips_prev_frame"]["value"],
                sw["flips_prev_frame"]["first"], sw["region_row_edge_min_m"]["value"], sw["region_row_edge_min_m"]["violations"],
                fmt(sw["region_stretch_row"]["value"]), sw["region_stretch_row"]["violations"], fmt(sw["region_stretch_cross"]["value"]),
                sw["region_stretch_cross"]["violations"], sw["degenerate_faces_max"]))
            cp = sw.get("compat_P13_ds27")
            if cp:
                L.append("")
                L.append("  設計27 の P13 と同じ式（K* と同じ格子のときだけ）：")
                L.append("")
                L.append("  | 項目 | 値 | しきい値 | 判定 | 詳細 |")
                L.append("  | --- | --- | --- | --- | --- |")
                for k, v in cp.items():
                    det = v.get("viol") or v.get("at")
                    L.append("  | %s | %s | %s | %s | %s |" % (k, fmt(v["value"]), v["threshold"], fmt(v["pass_"]), json.dumps(jdump(det), ensure_ascii=False) if det else ""))
        L.append("")
        L.append("| コマ | τ | 断面の交差（≥5 mm） | 折れ返り >120° | 反転（前のコマ） | 面積≈0 の面 | 唇の断面 | 唇の厚さの最小 m | 0.3 m 未満 | 基準との差：頂／唇先／唇の形 m | 射線：表／背面／切断／縁の下／穴／継ぎ目 | 3D 自己交差（細い面を含む） | 下向きで上が空（細い面を含む） |")
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for f in r["frames"]:
            vr = f.get("vs_ref")
            vrs = "—" if not vr else "%s／%s／%s" % tuple(fmt(vr[k]["value"]) if vr.get(k) else "—" for k in ("crest_loss_m", "tip_retreat_m", "lip_deviation_m"))
            b = f.get("blender")
            if b:
                ry = b["rays"]
                rs = "%d／%d／%d／%d／%d／%d" % (ry.get("wave_front", 0), ry.get("wave_back_open", 0), ry.get("cut_end", 0), ry.get("under_edge", 0), ry.get("hole", 0), ry.get("seam_cut", 0))
                si = "%s（%s）" % (b.get("self_intersections"), b.get("self_intersections_all"))
                dn = "%s（%s）" % (b.get("down_facing_open_sky"), b.get("down_facing_open_sky_all"))
            else:
                rs, si, dn = "—", "—", "—"
            L.append("| %s | %.3f | %d（%d） | %d | %s | %d | %d | %s | %d | %s | %s | %s | %s |" % (
                f["name"], f["tau"], f["section_self_crossings"], f["section_self_crossings_ge5mm"], f["fold_edges_gt120deg"],
                f.get("flips_vs_prev_frame", "—"), f["zero_area_faces"], f["lip_sections"], fmt(f["lip_thick_min_m"]), f["lip_thin_sections"], vrs, rs,
                si, dn))
        L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as fo:
        fo.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- main
def xcheck_ds27(pk, ks, log):
    """独立に書いた Hermite と、設計27 の検査器の読み方（ds27_gates.Package.world）の差。"""
    try:
        P = G27.Package(pk.dir, ks)
    except SystemExit as e:
        return dict(error=str(e))
    out = []
    for tau in (-11.99, -7.3, -3.0, -2.25, -0.8667, -0.01, 0.0):
        a = pk.world(tau)
        b = P.world(tau).reshape(-1, 3)
        out.append(dict(tau=tau, max_abs_diff_m=float(np.abs(a - b).max())))
    del P
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", action="append", default=[])
    ap.add_argument("--subsample", action="append", default=[])
    ap.add_argument("--kstar", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ref", default=None)
    ap.add_argument("--taus", default="last3")
    ap.add_argument("--stages", default=STAGES_DEFAULT)
    ap.add_argument("--no-sweep", dest="sweep", action="store_false")
    ap.add_argument("--blender", action="store_true")
    ap.add_argument("--blender-exe", default=BLENDER)
    ap.add_argument("--rays", type=int, default=50000)
    ap.add_argument("--sea-y", type=float, default=-0.07)
    ap.add_argument("--no-selfx", dest="selfx", action="store_false", help="Blender の 3 次元の自己交差を省く")
    ap.add_argument("--keep-npz", action="store_true")
    ap.add_argument("--xcheck", action="store_true", help="独立の Hermite を設計27 の検査器の読み方と照合する")
    ap.add_argument("--out", default=os.path.join(REPO, "Unity", "Build", "Design", "29", "qa"))
    ap.add_argument("--summary-name", default="ds29_qa_summary")
    ap.add_argument("--title", default="設計29：表示用サーフェスの検査（ds29_qa）")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(s, flush=True)
    ks = G27.KStar()
    slicer = Slicer(ks)
    ref = PackageSurface(args.ref, "ref") if args.ref else None
    subjects = []
    if args.kstar:
        subjects.append(KStarSurface(ks))
    for spec in args.package:
        name, d = spec.split("=", 1) if "=" in spec and not os.path.isdir(spec) else (None, spec)
        subjects.append(PackageSurface(d, name))
    for spec in args.subsample:
        name, rest = spec.split("=", 1)
        d, st = rest.rsplit(":", 1)
        rs, cs = [int(x) for x in st.split(",")]
        subjects.append(SubsampledSurface(PackageSurface(d, name + "_parent"), rs, cs, name))
    if args.selftest:
        for kind in ("hole", "seam", "flip", "thin"):
            subjects.append(DefectSurface(ks, kind))
    reps = []
    for s in subjects:
        log("[ds29_qa] %s を検査します（%s）" % (s.label, s.info().get("kind")))
        use_ref = ref
        rep = run_surface(s, ks, slicer, args, ref=use_ref, log=log)
        if args.xcheck and isinstance(s, PackageSurface) and s.rows == ks.nv and s.cols == ks.nu:
            rep["xcheck_ds27_hermite"] = xcheck_ds27(s, ks, log)
        reps.append(rep)
        with open(os.path.join(args.out, "%s_qa.json" % s.label), "w", encoding="utf-8", newline="\n") as f:
            json.dump(jdump(rep), f, ensure_ascii=False, indent=1)
        log("[ds29_qa] %s：%.0f s" % (s.label, rep["runtime_s"]))
    summary = dict(schema="GreatWave.DS29.qa/1", tool=rel(__file__), tool_sha256=sha256_file(__file__),
                   blender_tool=rel(BLENDER_QA), blender_tool_sha256=sha256_file(BLENDER_QA) if os.path.isfile(BLENDER_QA) else None,
                   ds27_gates_sha256=sha256_file(os.path.join(HERE, "..", "ds27", "ds27_gates.py")),
                   kstar_sha256=ks.sha, ref=rel(ref.dir) if ref else None, ref_pos_sha256=ref.pos_sha if ref else None,
                   thresholds=TH, taus=args.taus, stages=args.stages, rays=args.rays, sea_y=args.sea_y,
                   command=" ".join(["py -3.10 -B " + rel(__file__)] + sys.argv[1:]), runtime_s=round(time.time() - t0, 1),
                   subjects={r["label"]: dict(info=r["info"], topology=r["topology"], verdicts=r["verdicts"], xcheck=r.get("xcheck_ds27_hermite")) for r in reps})
    with open(os.path.join(args.out, args.summary_name + ".json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(jdump(summary), f, ensure_ascii=False, indent=1)
    notes = ["- 道具：`%s`（numpy）と `%s`（Blender 5.2.2 ヘッドレス）。作り手のコードは読まず、包みの約束だけで測る。" % (rel(__file__), rel(BLENDER_QA)),
             "- 基準の包み（波頭の欠落）：%s。コマ：%s ＋ 段階 %s。射線 %d 本（座席 v1 の目から、美術優先26 と同じ半球の向き）、平らな海 y = %.2f m。" % (
                 rel(ref.dir) if ref else "なし", args.taus, args.stages, args.rays, args.sea_y),
             "- 「—」は測っていない（静止した網の 30 Hz の通し、基準のない波頭の差、Blender を回さない時の射線）。"]
    write_md(os.path.join(args.out, args.summary_name + ".md"), reps, args.title, notes)
    log("[ds29_qa] 終わり：%s（%.0f s）" % (rel(os.path.join(args.out, args.summary_name + ".md")), time.time() - t0))


if __name__ == "__main__":
    main()
