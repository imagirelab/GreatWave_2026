# -*- coding: utf-8 -*-
"""設計27：大波の動きの関門 P1〜P16（設計26 の記録 §4.1）と、t* の原画の関門の前提（τ = 0 で K* と一致）を測る検査器。

生成器から独立に、設計26 の記録（Docs/Progress/Design_26_ja.md の §3.1・§3.2・§4.1・§4.2・§6）だけから作った。
Q11（2026-09-27）で t* の後の崩壊は作らないので、測るのは τ ≤ 0 だけ。

入力（DS27 の keypose の包み。生成器と Unity の再生器が同じ約束で読み書きする）：
  <包み>/ds27_keypose.json   layers・rows(240)・cols(400)・bbox_min[3]・bbox_size[3]・knot_tau[layers]（秒、狭義単調増加、
                             最後 = 0.0 = t*）・frame{tau[], origin[[x,y,z]]}（≥240 Hz、線形補間）・pos_sha256・twhite_file・twhite_sha256
  <包み>/ds27_pos_rgba16.bin  RGBA16 UNORM、層 × 行 × 列 × 4。xyz は外接箱で正規化、A = 65535。
                             位置は波の枠の局所座標（ワールド − O(τ)、O は平行移動だけ、軸はワールドの軸）
  <包み>/ds27_twhite_r32f.bin R32F 行 × 列。T_white（τ の秒）。τ ≥ T_white で白、+1e9 = t* まで白くならない
  --timewarp <表.json>        {"t":[...], "tau":[...]}（≥240 Hz、t ∈ [0, 14]、t* = 12.0 s で τ = 0、12〜14 s は保持）。P16 に使う
補間：節点 i と i+1 の間の 3 次 Hermite、傾き m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})（端は片側の差）。範囲外は端の層。
座標：K* の断面の座標（kstar_a45_meta.json の frame。a = 進行方向 t、y = 上、c = 波峰線方向 e。行 = c が一定の面）。
      「地面」＝ワールド（局所 + O(τ)）、「波の枠」＝局所。

使い方（リポジトリの根で）:
  py -3.10 -B Tools/GWWaveGen/ds27/ds27_gates.py --package Unity/Build/Design/27/art_on \\
      --timewarp Tools/GWWaveGen/ds27/timewarp_default.json --out <出力.json>
  出力：<出力.json>（関門ごとに value・threshold・pass と詳細）と、同じ名前の .md（日本語の表）。
  任意：--sea <海.npz>（シートの外の解析式の海を行の断面に沿って標本化したもの。P2・P11 をシートの外まで測る。
        キー tau[nt]・a[na]（地面の a、m）・eta[nt, 240, na] か eta[nt, na]）。無ければ P2・P11 はシートの上だけで測り、そう書く。
numpy だけを使う。K* は読むだけ（SHA-256 を照合）。
"""
import argparse
import hashlib
import json
import math
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KSTAR_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
COND_JSON = os.path.join(REPO, "Docs", "Evidence", "Design", "26", "ds26_conditions.json")
SHA256 = {
    "kstar_a45.gwb": "e9bc3572590b5b237ddd302fca64f54f2d325813ad787f20e4d7524b6b84cd26",
    "kstar_a45_rows.npz": "c9eff8ddc6aa8f887c809b36431fafe00f5747084d8f689b75b9ae23029322bb",
    "kstar_a45_meta.json": "0651821b9e44f25724c8dc819d04567c97b36aec54e3c04454924949293f22fb",
    "ds26_conditions.json": "ec8ae040da4a10a371815b207bee7ad5e8c44af6d56b0fb35989aeee8fb6c072",
}
G = 9.81
HZ = 60              # 形の関門の時刻の刻み（物理の時刻 τ）
HZ_OUT = 30          # 出力のコマ（P13 の 1 コマの変位・二階差分・面の反転）
HZ_KIN = 240         # 唇先の運動（P4・P5・P16）
NEVER = 1.0e8        # T_white がこれ以上なら「t* まで白くならない」

# ---------------------------------------------------------------- しきい値（設計26 の記録 §4.1。変えるときは記録を先に直す）
TH = dict(
    P1_speed_mps=10.0, P1_back_m=0.1, P1_window_s=3.0,
    P2_ratio=0.2, P2_trough_over_Hstar=-0.1, P2_ahead_m=112.5, P2_window_half_m=112.5, P2_calm_painting_from_tau=-2.0,
    P3_frac=0.10,
    P4_acc_lo=-12.8, P4_acc_hi=-6.9, P4_win_s=0.3, P4_up_run_s=0.1, P4_fall_tol=0.30,
    P5_speed_mps=16.0,
    P6_mid_over_root=0.5, P6_root_over_tip_h=0.6,
    P7_lo_s=1.6, P7_hi_s=2.8,
    P8_frac=0.5, P8_tau=-0.2,
    P9_lead_s=0.3, P9_frac=0.05, P9_tip_arc_over_H=0.1,
    P10_corr=-0.3, P10_std_s=0.1,
    P11_rms_over_Hstar=0.05, P11_height_over_Hstar=0.2, P11_tau=-4.0,
    P12_back_m=0.05,
    P13_step_m=0.6, P13_acc_g=2.0, P13_ymin_over_Hstar=-0.5, P13_crest_mono_m=0.05,
    P13_tri_area_m2=1e-4, P13_row_edge_m=0.005, P13_stretch_lo=0.05, P13_stretch_hi=4.0, P13_seam_lo=0.25, P13_seam_hi=4.0,
    P15_tol_s=0.3,
    P16_tol_mps2=0.05, P16_stop_ramp_max_s=0.5,
)
# 段階の判定（設計26 §3.1 の表。数で書かれていない所は、この検査器の読み方として detail に書く）
STAGE = dict(
    a=dict(H=(0.5, 0.7), theta_min=140.0, phi_max=35.0, Lo_max=0.02),
    b=dict(H=(0.65, 0.8), phi_min=45.0, theta_max=130.0, Lo_max=0.02, asym_deg=5.0),
    c=dict(H=(0.8, 0.9), phi_band=(0.8, 0.9), phi_band_min=90.0, theta=(105.0, 135.0), Lo_max=0.05),
    d=dict(H_min=0.9, Lo_min=0.1, B_min=1.0),
)


# 設計26 の記録が数で決めていない所の、この検査器の読み方（報告に書き出す。変えるときは進行役に見せる）
READINGS_JA = [
    "行・巻きの行・唇先：K* の断面の行（c 一定の面）。巻きの行 133 行と唇先の列 jtip・rim・内壁 0.3H の錨 ja は設計26 の E1/E4 と同じ規則で K* から決める（切った版でも同じ行と列を使う）。峰で最も高い巻きの行は行 192（c = +3.85 m）。",
    "頂（本体の頂）：巻きの行では列 ≤ K* の頂の列 jt の最高点（放出した唇先が頂より上へ出ても頂に数えない）。ほかの行は全列の最高点。P1・P12 の頂の位置と P13(4)・P15 の H はこの頂。",
    "H/H*：P15 の段階の H はその行の t*（包みの τ = 0）の頂で割る（設計26 E1 の『H/H* 0.89』と同じ割り方。峰の行の K* の頂は 22.58 m）。",
    "φ：頂から前の足（列 j_E）までの下りの線分の最大の角（中点が 0.15〜0.97H、90° で鉛直）。段階 c の φ は頂の下 0.1〜0.2H（中点が 0.8〜0.9H）の線分だけ。ψ：背面の上りの最大の角。θc：頂から 0.9H の高さの前後の点（前は頂から前へ、後ろは頂から後ろへ初めて 0.9H を下回る所）への弦のなす角。Lo：前の部分で 0.3H を最後に下へ横切る点から、0.3H より上の前の部分の a の最大まで（定義 A）。",
    "噴流の始まり：前面が鉛直（φ ≥ 90°）を初めて満たす時刻（P7・P9・P10・P3・P5）。打ち出しの補間の終わり（P16 の窓の始まり）は、測った始まり＋min(0.6 s, 始まりから t* の半分) と、ds26_conditions.json の表（峰の行 −2.4 s、20 m/s で広がる、下限 1.2 s）から同じく求めた値の遅い方。",
    "段階（P15）：a＝H/Hf 0.5〜0.7・θc ≥ 140°・φ ≤ 35°・Lo ≤ 0.02H・行に白なし。b＝H/Hf 0.65〜0.8・φ ≥ 45°・θc ≤ 130°・Lo ≤ 0.02H・|φ − ψ| ≥ 5°・白なし。c＝H/Hf 0.8〜0.9・頂の下 0.1〜0.2H の φ ≥ 90°・θc 105〜135°・Lo < 0.05H。d＝Lo ≥ 0.1H・H/Hf ≥ 0.9・dH/dτ > 0・唇先の水平の速さ ≥ 頂の速さ。どれも全部を初めて満たした時刻。表の τ は ds26_conditions.json（主断面は +0.19 s）。",
    "白：τ ≥ T_white の頂点が白（T_white ≥ 1e8 は t* まで白くならない）。白の割合は K* の頂点の面積の重み（UV のテクセルの割合とは違う）。最初の白の場所は、最小の T_white から 1/60 s 以内の頂点がすべて巻きの行の唇先から K* の弧長 0.1H 以内にあること。噴流の始まりのない行（奥の壁など）の白は記録のみ。",
    "P2・P3・P11：包みには周りの海（シートの外の解析式）がないので、--sea を渡さなければシートの上（a 方向に約 82 m）だけで測り、判定の横に書く。--sea があれば、P2・P3 は頂を中心に 225 m の窓（シートの断面＋周りの海の標本を τ で線形補間）の符号付きの断面積で測る（設計27 の統合で、設計26 §4.1 の定義に合わせて直した。初めの版は --sea を谷と P11 にだけ使っていた）。入れた版（ds_sea_calm_painting）は、周りの海を平らにする τ > −2.0 s を P2・P3 の判定から除いて記録する（設計26 §4.1 P2 の『平らにした行・コマは除外して記録』）。P2 は A_pos < 1 m² の行・コマ（波がまだない所）を除く。P3 は巻きの行ごと。P11 の『峰の外』は K* で y < 0.05H* の頂点。",
    "P4：唇先の頂点（噴流の始まりの後の最高点）から t* まで 0.3 s ごとの平均（0.15 s より短い最後の区間は捨てる）、上向きの続く時間は ±1/30 s の中心差分の縦の加速度、落下は K* の唇先の高さに届くまで。P5：始まりから打ち出しの補間の終わりまでの唇先の水平の速さの最大と、その時の頂の速さ。P6：t* の速さは最後の区間の片側の傾き（包みの補間の約束どおり）。",
    "P13：(1)(2) は物理の時刻の 30 Hz（体験の 30 fps のコマは r ≤ 1 なので Δτ ≤ 1/30 s）。(4) は主断面・峰の行・全行の最高の頂の戻り ≤ 0.05 m。(5) は唇（jt..rim）と管の天井（rim+1..ja−1）の列に触れる辺と三角形（設計26 の E4b と同じ範囲）。5 mm の辺の下限は、K* でもう 5 mm に近い・未満の辺では K* の長さ − 量子化の 2 倍。伸びの比の判定は辺の長さから量子化の 2 倍を差し引く。面の反転は、向きの決まった最後のコマの法線と比べ、全体は K* の最小の高さ ≥ 5 mm の三角形（残りは細長く量子化だけで裏返る）、唇・管は全部。自己交差は巻きの行の断面と、隣り合う巻きの行の間の中央の面の切り口（三角形の分け方どおり）で、−2.5 s より前は 0.5 s ごと、最後の 2.5 s は 30 Hz。(6) は唇・管の頂点の 1 環の三角形の面積 > 0。",
    "P14：包みのフォルダー名（art_on／art_off）の隣の版があれば合格とし、切った版の t* の K* との差（RMS・最大・場所）を記録する。",
    "P16：A(t) = d²y(τ(t))/dt²（y は包みの Hermite の値そのもの、h = 1/30 s の中心差分、窓の端から h 内側）。止めるための区間は、t* の直前で r = dτ/dt が減り続けている区間（0.5 s を超えれば 0.5 s）。許容 0.05 m/s²。",
    "原画の前提：τ = 0 の全頂点が K*（gwb）と、外接箱の量子化の半刻み（3 次元）＋0.1 mm 以内。切った版は判定なし（P14 で差を記録）。",
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return os.path.relpath(p, REPO).replace("\\", "/")
    except ValueError:
        return p.replace("\\", "/")


def fnum(x, nd=4):
    if x is None:
        return None
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    x = float(x)
    if not math.isfinite(x):
        return None
    return round(x, nd)


# ---------------------------------------------------------------- K*
class KStar:
    """26修正01 の K*（t* の姿）。巻きの行・唇の列などの定義は設計26 の E1/E4 と同じ規則。"""

    def __init__(self, kdir=KSTAR_DIR):
        paths = {k: os.path.join(kdir, k) for k in ("kstar_a45.gwb", "kstar_a45_rows.npz", "kstar_a45_meta.json")}
        for k, p in paths.items():
            if not os.path.isfile(p):
                raise SystemExit("[ds27_gates] K* がありません：%s" % rel(p))
            if sha256_file(p) != SHA256[k]:
                raise SystemExit("[ds27_gates] K* の SHA-256 が記録と違います：%s" % k)
        b = open(paths["kstar_a45.gwb"], "rb").read()
        if b[:4] != b"GWW0":
            raise SystemExit("[ds27_gates] GWW0 ではありません")
        _, nu, nv, _ = struct.unpack("<4i", b[4:20])
        ntri = struct.unpack("<i", b[28:32])[0]
        n = nu * nv
        o = 32 + n * 16
        tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3)
        o += ntri * 12
        self.X = np.frombuffer(b, np.float32, n * 3, o).reshape(nv, nu, 3).astype(np.float64)
        self.nu, self.nv = nu, nv
        # 三角形の分け方：(r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)。下の法線の計算はこの並びを前提にする
        r = np.arange(nv - 1)[:, None] * nu
        c = np.arange(nu - 1)[None, :]
        t1 = np.stack([r + c, r + c + nu, r + c + 1], -1)
        t2 = np.stack([r + c + 1, r + c + nu, r + c + nu + 1], -1)
        want = np.stack([t1, t2], 2).reshape(-1, 3)
        if not np.array_equal(want, tris):
            raise SystemExit("[ds27_gates] K* の三角形の並びが想定と違います")
        meta = json.load(open(paths["kstar_a45_meta.json"], encoding="utf-8"))
        fr = meta["frame"]
        self.O = np.array(fr["section_origin_world"], float)
        self.e = np.array(fr["e_crest"], float)
        self.t = np.array(fr["t_travel"], float)
        self.main_row = int(meta["rows"]["main_row"])
        pi = meta["profile"]["index"]
        self.j_corner, self.j_E = int(pi["j_corner"]), int(pi["j_E"])
        z = np.load(paths["kstar_a45_rows.npz"])
        self.A, self.Y, self.c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
        self.Hrow = self.Y.max(1)
        self.H_star = float(self.Hrow[self.main_row])
        self.sha = {k: SHA256[k] for k in paths}
        self._curled()
        # K* の弧長（行ごと）と、頂点の面積（隣の三角形の面積の 1/3 の和。白の割合の重み）
        seg = np.hypot(np.diff(self.A, axis=1), np.diff(self.Y, axis=1))
        self.s_arc = np.concatenate([np.zeros((nv, 1)), np.cumsum(seg, 1)], 1)
        nrm = tri_normals(self.X)
        ar = 0.5 * np.linalg.norm(nrm, axis=-1)            # (nv-1, nu-1, 2)
        va = np.zeros((nv, nu))
        a1, a2 = ar[..., 0] / 3.0, ar[..., 1] / 3.0
        va[:-1, :-1] += a1; va[1:, :-1] += a1; va[:-1, 1:] += a1
        va[:-1, 1:] += a2; va[1:, :-1] += a2; va[1:, 1:] += a2
        self.vert_area = va
        self._mesh_region()

    def _curled(self):
        """巻きの行：H ≥ 3 m、頂の列 jt < 200、唇先 jtip = 頂から角までで a が最大の列、張り出し（定義 A：内壁の 0.3H から唇先）≥ 0.2H。
        rim = 唇先の後の下面で最初の極小（6 点以上）、ja = 内壁の 0.3H の錨の列。設計26 の E1/E4（e4_common.py）と同じ規則。"""
        A, Y, C = self.A, self.Y, self.c
        rows = []
        for r in range(self.nv):
            y, a = Y[r], A[r]
            H = y.max()
            if H < 3.0:
                continue
            jt = int(np.argmax(y))
            if jt >= 200:
                continue
            seg = np.arange(jt, self.j_corner + 1)
            jtip = int(seg[np.argmax(a[seg])])
            w = np.arange(self.j_corner, self.j_E + 1)
            yw, aw = y[w], a[w]
            k = np.where((yw[:-1] - 0.3 * H) * (yw[1:] - 0.3 * H) <= 0)[0]
            if len(k) == 0:
                continue
            k = k[0]
            f = (0.3 * H - yw[k]) / (yw[k + 1] - yw[k] + 1e-12)
            a03 = aw[k] + f * (aw[k + 1] - aw[k])
            if a[jtip] - a03 < 0.2 * H or jtip <= jt + 5:
                continue
            un = np.arange(jtip, self.j_corner + 1)
            yy = y[un]
            kmin = next((i for i in range(1, len(yy) - 1) if yy[i] <= yy[i - 1] and yy[i] < yy[i + 1]), len(yy) - 1)
            un = un[:max(kmin + 1, 6)]
            rows.append(dict(r=r, c=float(C[r]), H=float(H), jt=jt, jtip=jtip, rim=int(un[-1]),
                             ja=int(self.j_corner + k + (1 if f > 0.5 else 0))))
        self.curled = rows
        self.curled_idx = np.array([q["r"] for q in rows])
        self.is_curled = np.zeros(self.nv, bool)
        self.is_curled[self.curled_idx] = True
        self.peak_row = max(rows, key=lambda q: q["H"])["r"]
        self.cq = {q["r"]: q for q in rows}
        # 本体の頂を探す列の上限：巻きの行は K* の頂の列 jt（唇＝噴流の膜は jt より先。放出した唇先が頂より上へ出ても頂に数えない）
        self.crest_hi = np.full(self.nv, self.nu - 1)
        self.tip_col = np.full(self.nv, -1)
        for q in rows:
            self.crest_hi[q["r"]] = q["jt"]
            self.tip_col[q["r"]] = q["jtip"]

    def _mesh_region(self):
        """P13(5) の網の形を見る範囲：巻きの行の唇（jt..rim）と管の天井（rim+1..ja−1）の列に触れる辺と三角形（設計26 の E4b と同じ）。"""
        nv, nu = self.nv, self.nu
        lipcol = np.zeros((nv, nu), bool)
        for q in self.curled:
            lipcol[q["r"], q["jt"]:q["ja"]] = True
        self.lipcol = lipcol
        # 行の方向の辺 (j, j+1)
        self.row_edge_mask = lipcol[:, :-1] | lipcol[:, 1:]
        # 隣り合う巻きの行の間（両方とも巻きの行）の三角形と、行の間の辺
        pair = self.is_curled[:-1] & self.is_curled[1:]
        tch = (lipcol[:-1] | lipcol[1:]) & pair[:, None]          # (nv-1, nu)
        self.tri_mask = (tch[:, :-1] | tch[:, 1:])                 # (nv-1, nu-1)
        tany = lipcol[:-1] | lipcol[1:]
        self.ring_mask = tany[:, :-1] | tany[:, 1:]                # 唇・管の頂点の 1 環（P13(6)）
        self.vedge_mask = tch                                       # (r,j)-(r+1,j)
        self.dedge_mask = self.tri_mask                             # (r,j+1)-(r+1,j)
        self.seam = [(q["r"], q["rim"]) for q in self.curled]
        K = self.X
        self.Lrow_K = np.linalg.norm(np.diff(K, axis=1), axis=-1)
        self.Lv_K = np.linalg.norm(K[1:] - K[:-1], axis=-1)
        self.Ld_K = np.linalg.norm(K[1:, :-1] - K[:-1, 1:], axis=-1)
        nrm = tri_normals(K)
        self.tri_area_K = 0.5 * np.linalg.norm(nrm, axis=-1)
        # 16 ビットで向きが決まる三角形：K* の最小の高さ（2 × 面積 / 最長の辺）≥ 5 mm（量子化 1.2 mm の約 4 倍）。
        # K* の 15% ほどは細長い三角形（平らな縁の列の詰まった所）で、量子化だけで面が裏返るので、面の反転はここだけで数える
        P00, P10, P01, P11 = K[:-1, :-1], K[1:, :-1], K[:-1, 1:], K[1:, 1:]
        e1 = np.maximum.reduce([np.linalg.norm(P10 - P00, axis=-1), np.linalg.norm(P01 - P10, axis=-1), np.linalg.norm(P00 - P01, axis=-1)])
        e2 = np.maximum.reduce([np.linalg.norm(P10 - P01, axis=-1), np.linalg.norm(P11 - P10, axis=-1), np.linalg.norm(P01 - P11, axis=-1)])
        alt = 2 * self.tri_area_K / np.maximum(np.stack([e1, e2], 2), 1e-15)
        self.tri_resolvable = alt >= 0.005
        # 自己交差を見る列の範囲（全巻きの行で共通）
        self.J0 = max(min(q["jt"] for q in self.curled) - 3, 0)
        self.J1 = min(max(q["ja"] for q in self.curled) + 2, nu - 1)

    def section(self, X):
        D = X - self.O
        return D @ self.t, X[..., 1], D @ self.e


def tri_normals(X):
    """X (nv, nu, 3) → 三角形の法線（面積の 2 倍の長さ）(nv-1, nu-1, 2, 3)。並びは K* の三角形と同じ。"""
    P00, P10, P01, P11 = X[:-1, :-1], X[1:, :-1], X[:-1, 1:], X[1:, 1:]
    n1 = np.cross(P10 - P00, P01 - P00)
    n2 = np.cross(P10 - P01, P11 - P01)
    return np.stack([n1, n2], 2)


# ---------------------------------------------------------------- Hermite（包みの約束。numpy とシェーダーで同じ式）
def hermite_weights(knots, tau, deriv=0):
    """時刻 tau（配列）の補間に使う 4 つの層の添字 (n, 4) と重み (n, 4)。deriv = 0（位置）・1（dτ）・2（dτ²）。
    区間 [τ_i, τ_{i+1}]、s = (τ − τ_i)/Δ。m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})（端は片側）。範囲外は端の区間で s を 0〜1 に切る。"""
    tau = np.atleast_1d(np.asarray(tau, float))
    L = len(knots)
    i = np.clip(np.searchsorted(knots, tau, side="right") - 1, 0, L - 2)
    t1, t2 = knots[i], knots[i + 1]
    D = t2 - t1
    s = np.clip((tau - t1) / D, 0.0, 1.0)
    i0 = np.maximum(i - 1, 0)
    i3 = np.minimum(i + 2, L - 1)
    if deriv == 0:
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        sc = np.ones_like(s)
    elif deriv == 1:
        h00, h10, h01, h11 = 6 * s ** 2 - 6 * s, 3 * s ** 2 - 4 * s + 1, -6 * s ** 2 + 6 * s, 3 * s ** 2 - 2 * s
        sc = 1.0 / D
    else:
        h00, h10, h01, h11 = 12 * s - 6, 6 * s - 4, -12 * s + 6, 6 * s - 2
        sc = 1.0 / D ** 2
    w = np.zeros((len(tau), 4))
    w[:, 1] += h00
    w[:, 2] += h01
    f = h10 * D / (t2 - knots[i0])       # m_i の項（i0 = i なら片側の差）
    w[:, 2] += f
    w[:, 0] -= f
    g_ = h11 * D / (knots[i3] - t1)      # m_{i+1} の項（i3 = i+1 なら片側の差）
    w[:, 3] += g_
    w[:, 1] -= g_
    w *= sc[:, None]
    idx = np.stack([i0, i, i + 1, i3], 1)
    return idx, w


# ---------------------------------------------------------------- 包み
class Package:
    def __init__(self, d, ks):
        self.dir = os.path.abspath(d)
        self.iface = []
        jp = os.path.join(self.dir, "ds27_keypose.json")
        if not os.path.isfile(jp):
            raise SystemExit("[ds27_gates] ds27_keypose.json がありません：%s" % d)
        J = json.load(open(jp, encoding="utf-8"))
        self.meta = J
        self.version = str(J.get("version") or os.path.basename(self.dir.rstrip("/\\")))
        L, nv, nu = int(J["layers"]), int(J["rows"]), int(J["cols"])
        self._chk("rows・cols が K* と同じ（240 × 400）", nv == ks.nv and nu == ks.nu, "%d × %d" % (nv, nu))
        pp = os.path.join(self.dir, "ds27_pos_rgba16.bin")
        sha = sha256_file(pp)
        self._chk("pos_sha256 がファイルと一致", sha == J.get("pos_sha256"), sha[:12])
        raw = np.fromfile(pp, "<u2")
        self._chk("位置のファイルの大きさ = layers × 行 × 列 × 8 バイト", raw.size == L * nv * nu * 4, "%d 層" % (raw.size // max(nv * nu * 4, 1)))
        if raw.size != L * nv * nu * 4:
            raise SystemExit("[ds27_gates] 位置のファイルの大きさが layers と合いません")
        raw = raw.reshape(L, nv, nu, 4)
        self._chk("A = 65535", bool((raw[..., 3] == 65535).all()), "")
        lo = np.array(J["bbox_min"], float)
        sz = np.array(J["bbox_size"], float)
        self.q_max = 0.5 * float(np.linalg.norm(sz)) / 65535.0     # 量子化の最大誤差（3 次元、半刻み）
        self.P = np.empty((L, nv, nu, 3), np.float32)
        for l in range(L):
            self.P[l] = (lo + raw[l, ..., :3].astype(np.float64) / 65535.0 * sz).astype(np.float32)
        del raw
        self.knots = np.array(J["knot_tau"], float)
        ok = len(self.knots) == L and bool(np.all(np.diff(self.knots) > 0)) and self.knots[-1] == 0.0
        self._chk("knot_tau：層の数・狭義単調増加・最後 = 0.0", ok, "τ %.3f〜%.3f s、間隔 %.4f〜%.4f s" % (
            self.knots[0], self.knots[-1], np.diff(self.knots).min(), np.diff(self.knots).max()))
        if not ok:
            raise SystemExit("[ds27_gates] knot_tau が約束と違います")
        fr = J["frame"]
        self.ftau = np.array(fr["tau"], float)
        self.forg = np.array(fr["origin"], float).reshape(-1, 3)
        dt = np.diff(self.ftau)
        ok = (len(self.ftau) == len(self.forg) and bool(np.all(dt > 0)) and self.ftau[0] <= self.knots[0] + 1e-9
              and self.ftau[-1] >= -1e-9 and float(dt.max()) <= 1.0 / 240 + 1e-6)
        self._chk("frame：τ が狭義単調・keypose の範囲を覆う・≥240 Hz", ok, "%d 点、最大の間隔 %.5f s" % (len(self.ftau), float(dt.max())))
        tw_name = J.get("twhite_file", "ds27_twhite_r32f.bin")
        tp = os.path.join(self.dir, tw_name)
        tsha = sha256_file(tp)
        self._chk("twhite_sha256 がファイルと一致", tsha == J.get("twhite_sha256"), tsha[:12])
        self.twhite = np.fromfile(tp, "<f4").astype(np.float64).reshape(nv, nu)
        self.pos_sha = sha
        self.twhite_sha = tsha
        self.L = L

    def _chk(self, name, ok, detail):
        self.iface.append(dict(item_ja=name, ok=bool(ok), detail=detail))

    def origin(self, tau):
        tau = np.atleast_1d(np.asarray(tau, float))
        return np.stack([np.interp(tau, self.ftau, self.forg[:, k]) for k in range(3)], -1)

    def origin_vel(self, tau):
        tau = np.atleast_1d(np.asarray(tau, float))
        i = np.clip(np.searchsorted(self.ftau, tau, side="right") - 1, 0, len(self.ftau) - 2)
        i = np.where(tau >= self.ftau[-1], len(self.ftau) - 2, i)
        return (self.forg[i + 1] - self.forg[i]) / (self.ftau[i + 1] - self.ftau[i])[:, None]

    def local(self, tau, deriv=0):
        idx, w = hermite_weights(self.knots, [tau], deriv)
        out = np.zeros(self.P.shape[1:], np.float64)
        for q in range(4):
            if w[0, q] != 0.0:
                out += w[0, q] * self.P[idx[0, q]]
        return out

    def world(self, tau):
        return self.local(tau) + self.origin(tau)[0]

    def world_vel(self, tau):
        return self.local(tau, 1) + self.origin_vel(tau)[0]

    def sub(self, taus, vidx, deriv=0):
        """頂点の添字 vidx の地面の位置（または微分）を多くの時刻で。戻り (nt, n, 3)。"""
        taus = np.asarray(taus, float)
        Ps = self.P.reshape(self.L, -1, 3)[:, vidx, :].astype(np.float64)
        idx, w = hermite_weights(self.knots, taus, deriv)
        out = np.zeros((len(taus), len(vidx), 3))
        for q in range(4):
            out += w[:, q, None, None] * Ps[idx[:, q]]
        if deriv == 0:
            out += self.origin(taus)[:, None, :]
        elif deriv == 1:
            out += self.origin_vel(taus)[:, None, :]
        return out


def load_timewarp(path):
    J = json.load(open(path, encoding="utf-8"))
    t = np.array(J["t"], float)
    tau = np.array(J["tau"], float)
    chk = []
    dt = np.diff(t)
    chk.append(dict(item_ja="t が狭義単調・≥240 Hz", ok=bool(np.all(dt > 0) and dt.max() <= 1.0 / 240 + 1e-6), detail="最大の間隔 %.5f s" % dt.max()))
    chk.append(dict(item_ja="t が 0〜14 s を覆う", ok=bool(t[0] <= 1e-9 and t[-1] >= 14.0 - 1e-6), detail="%.3f〜%.3f s" % (t[0], t[-1])))
    chk.append(dict(item_ja="τ が減らない", ok=bool(np.all(np.diff(tau) >= -1e-9)), detail=""))
    t12 = float(np.interp(12.0, t, tau))
    hold = tau[(t >= 12.0) & (t <= 14.0)]
    chk.append(dict(item_ja="τ(12 s) = 0、12〜14 s は τ = 0", ok=bool(abs(t12) < 1e-6 and np.all(np.abs(hold) < 1e-6)), detail="τ(12) = %.2e" % t12))
    rmax = float((np.diff(tau) / dt).max())
    chk.append(dict(item_ja="r = dτ/dt ≤ 1（出力の 30 fps のコマの Δτ ≤ 1/30 s。P13 の (1)(2) を物理の時刻の 30 Hz で測る前提）",
                    ok=bool(rmax <= 1.0 + 1e-6), detail="r の最大 %.4f、τ(0) = %.3f s" % (rmax, tau[0])))
    return dict(path=path, sha256=sha256_file(path), t=t, tau=tau, checks=chk)


def reference_timewarp(kind, tau_apex=-1.432, r0=0.5, d1=1.0, tf=0.4, dt=1.0 / 2400):
    """設計26 §3.2 の τ(t)（既定 = 実時間 → 1 s で 0.5 倍 → 0.5 倍 → 0.4 s で止めて t* で保持。代案 = 実時間 → t* で瞬間に止める）。
    渡された表が記録どおりかを見るための参照（関門ではない）。"""
    S = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    Lc = (abs(tau_apex) - r0 * tf / 2) / r0
    t_ap = 12 - tf - Lc
    t1 = t_ap - d1

    def rate(tt):
        r = np.ones_like(tt)
        if kind == "default":
            m = (tt >= t1) & (tt < t_ap)
            r[m] = 1 - (1 - r0) * S((tt[m] - t1) / d1)
            r[(tt >= t_ap) & (tt < 12 - tf)] = r0
            m = (tt >= 12 - tf) & (tt < 12)
            r[m] = r0 * (1 - S((tt[m] - (12 - tf)) / tf))
        r[tt >= 12] = 0.0
        return r

    t = np.arange(0, 14 + 1e-9, dt)
    tau = np.concatenate([[0], np.cumsum(rate(t[:-1] + dt / 2) * dt)])      # 区間の中点の速さで積分（段差でも半刻みずれない）
    tau -= tau[int(round(12 / dt))]
    return t, tau


# ---------------------------------------------------------------- 行の断面の量（全行を一度に）
def row_metrics(A, Y, crest_hi, jE):
    """A, Y (nr, nu) の各行の、本体の頂（列 ≤ crest_hi の最高点）、前面の最大の角 φ（0.15〜0.97H、90° で鉛直、それ以上は張り出し）、
    頂の下 0.1〜0.2H の前面の最大の角 φb、背面の最大の角 ψ、頂の角 θc（頂から 0.1H 下の前後の点への弦のなす角）、
    張り出し Lo（定義 A：前の部分で 0.3H を最後に下へ横切る点から、0.3H より上の前の部分の a の最大まで）。"""
    nr, nu = A.shape
    rr = np.arange(nr)
    cols = np.arange(nu)
    Ym = np.where(cols[None, :] <= crest_hi[:, None], Y, -np.inf)
    cj = Ym.argmax(1)
    H = Y[rr, cj]
    ca = A[rr, cj]
    Hc = H[:, None]
    da, dy = np.diff(A, axis=1), np.diff(Y, axis=1)
    ym = 0.5 * (Y[:, 1:] + Y[:, :-1])
    L = np.hypot(da, dy)
    seg = cols[:-1][None, :]
    front = (seg >= cj[:, None]) & (seg < jE)
    back = seg < cj[:, None]
    band = (ym > 0.15 * Hc) & (ym < 0.97 * Hc)
    ang_f = np.degrees(np.arctan2(-dy, da))
    m = front & (L > 1e-3) & (dy < 0) & band
    phi = np.where(m, ang_f, -np.inf).max(1)
    phi[~m.any(1)] = np.nan
    mb = front & (L > 1e-3) & (dy < 0) & (ym >= 0.8 * Hc) & (ym <= 0.9 * Hc)
    phib = np.where(mb, ang_f, -np.inf).max(1)
    phib[~mb.any(1)] = np.nan
    mk = back & (L > 1e-3) & (dy > 0) & band
    psi = np.where(mk, np.degrees(np.arctan2(dy, da)), -np.inf).max(1)
    psi[~mk.any(1)] = np.nan
    # 張り出し
    y3 = 0.3 * Hc
    cr3 = front & (Y[:, :-1] > y3) & (Y[:, 1:] <= y3)
    has3 = cr3.any(1)
    k3 = (nu - 2) - np.argmax(cr3[:, ::-1], axis=1)
    y0, y1 = Y[rr, k3], Y[rr, k3 + 1]
    f = (y0 - 0.3 * H) / np.maximum(y0 - y1, 1e-12)
    a3 = A[rr, k3] + f * (A[rr, k3 + 1] - A[rr, k3])
    abv = (cols[None, :] >= cj[:, None]) & (cols[None, :] <= jE) & (Y > y3)
    amax = np.where(abv, A, -np.inf).max(1)
    Lo = np.where(has3, amax - a3, np.nan)
    # 頂の角
    y9 = 0.9 * Hc
    below = Y < y9
    mbk = below & (cols[None, :] < cj[:, None])
    hasb = mbk.any(1)
    kb = (nu - 1) - np.argmax(mbk[:, ::-1], axis=1)
    kb1 = np.minimum(kb + 1, nu - 1)
    fb = (0.9 * H - Y[rr, kb]) / np.maximum(Y[rr, kb1] - Y[rr, kb], 1e-12)
    ab = A[rr, kb] + fb * (A[rr, kb1] - A[rr, kb])
    mfr = below & (cols[None, :] > cj[:, None])
    hasf = mfr.any(1)
    kf = np.argmax(mfr, axis=1)
    kf0 = np.maximum(kf - 1, 0)
    ff = (Y[rr, kf0] - 0.9 * H) / np.maximum(Y[rr, kf0] - Y[rr, kf], 1e-12)
    af = A[rr, kf0] + ff * (A[rr, kf] - A[rr, kf0])
    vb = np.stack([ab - ca, np.full(nr, -0.1) * H], -1)
    vf = np.stack([af - ca, np.full(nr, -0.1) * H], -1)
    cosang = (vb * vf).sum(-1) / np.maximum(np.linalg.norm(vb, axis=-1) * np.linalg.norm(vf, axis=-1), 1e-12)
    theta = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    theta = np.where(hasb & hasf, theta, np.nan)
    low = H < 1.0
    for v in (phi, phib, psi, Lo, theta):
        v[low] = np.nan
    return dict(cj=cj, H=H, ca=ca, phi=phi, phib=phib, psi=psi, Lo=Lo, theta=theta)


def row_areas(A, Y):
    """行ごとの符号付きの断面積（折れ線を両端で y = 0 へ下ろして閉じ、shoelace。上が正。張り出しの下の空気は自動で引かれる）
    と、y > 0 の部分の面積 A_pos（y = 0 で切った多角形）。戻り (A_net, A_pos)。"""
    a0, y0 = A[:, 0:1], Y[:, 0:1]
    a1, y1 = A[:, -1:], Y[:, -1:]
    z = np.zeros_like(a0)
    Pa = np.concatenate([a0, A, a1], 1)
    Py = np.concatenate([z, Y, z], 1)
    pa, py, qa, qy = Pa[:, :-1], Py[:, :-1], Pa[:, 1:], Py[:, 1:]
    term = pa * qy - qa * py
    A_net = -0.5 * term.sum(1)            # 閉じる辺（y = 0 の上）は 0
    # y ≥ 0 の部分
    with np.errstate(divide="ignore", invalid="ignore"):
        xz = pa + (qa - pa) * (0 - py) / (qy - py)
    t_pos = np.where((py >= 0) & (qy >= 0), term,
                     np.where((py >= 0) & (qy < 0), -xz * py,
                              np.where((py < 0) & (qy >= 0), xz * qy, 0.0)))
    A_pos = -0.5 * np.nan_to_num(t_pos).sum(1)
    return A_net, A_pos


def seg_crossings(P, chunk=6):
    """折れ線 P (npoly, npts, 2) の、隣でない線分どうしの真の交差。戻り (hits (n, 3) = 折れ線・線分 i・線分 j, 両方の線分が 5 mm 以上の交差の数)。"""
    npoly, npts, _ = P.shape
    nseg = npts - 1
    I, J = np.triu_indices(nseg, k=2)
    p1 = P[:, :-1].astype(np.float64)
    p2 = P[:, 1:].astype(np.float64)
    seglen = np.linalg.norm(p2 - p1, axis=-1)
    hits = []
    for s in range(0, npoly, chunk):
        a1, a2 = p1[s:s + chunk][:, I], p2[s:s + chunk][:, I]
        b1, b2 = p1[s:s + chunk][:, J], p2[s:s + chunk][:, J]
        # 外接箱で先にふるう
        ok = ((np.maximum(a1[..., 0], a2[..., 0]) >= np.minimum(b1[..., 0], b2[..., 0])) &
              (np.maximum(b1[..., 0], b2[..., 0]) >= np.minimum(a1[..., 0], a2[..., 0])) &
              (np.maximum(a1[..., 1], a2[..., 1]) >= np.minimum(b1[..., 1], b2[..., 1])) &
              (np.maximum(b1[..., 1], b2[..., 1]) >= np.minimum(a1[..., 1], a2[..., 1])))
        if not ok.any():
            continue
        pi_, qi = np.nonzero(ok)
        A1, A2, B1, B2 = a1[pi_, qi], a2[pi_, qi], b1[pi_, qi], b2[pi_, qi]
        d = A2 - A1
        e = B2 - B1
        c1 = d[:, 0] * (B1[:, 1] - A1[:, 1]) - d[:, 1] * (B1[:, 0] - A1[:, 0])
        c2 = d[:, 0] * (B2[:, 1] - A1[:, 1]) - d[:, 1] * (B2[:, 0] - A1[:, 0])
        c3 = e[:, 0] * (A1[:, 1] - B1[:, 1]) - e[:, 1] * (A1[:, 0] - B1[:, 0])
        c4 = e[:, 0] * (A2[:, 1] - B1[:, 1]) - e[:, 1] * (A2[:, 0] - B1[:, 0])
        hit = (c1 * c2 < 0) & (c3 * c4 < 0)
        if hit.any():
            hits.append(np.stack([s + pi_[hit], I[qi[hit]], J[qi[hit]]], 1))
    H = np.concatenate(hits, 0) if hits else np.zeros((0, 3), np.int64)
    n_res = int(((seglen[H[:, 0], H[:, 1]] >= 0.005) & (seglen[H[:, 0], H[:, 2]] >= 0.005)).sum()) if len(H) else 0
    return H, n_res


class ViolTracker:
    """P13(5)(6) の各項目の違反の数（辺・三角形 × コマ）と、違反のあった τ の範囲。"""

    def __init__(self):
        self.d = {}

    def add(self, key, n, tau):
        e = self.d.setdefault(key, dict(n=0, frames=0, tau_range=None))
        if n > 0:
            e["n"] += int(n)
            e["frames"] += 1
            tr = e["tau_range"]
            e["tau_range"] = [round(float(tau), 4), round(float(tau), 4)] if tr is None else [min(tr[0], round(float(tau), 4)), max(tr[1], round(float(tau), 4))]


def first_true(mask, taus):
    idx = np.nonzero(mask)[0]
    return (float(taus[idx[0]]), int(idx[0])) if len(idx) else (None, None)


def drawdown(x):
    """時系列 x の最大の戻り（それまでの最大 − 今）。"""
    x = np.asarray(x, float)
    m = np.maximum.accumulate(np.nan_to_num(x, nan=-np.inf))
    return float(np.nanmax(m - x)) if len(x) else 0.0


# ---------------------------------------------------------------- 測定
def measure(ks, pk, sea=None, log=print):
    t_clock = time.time()
    nv, nu = ks.nv, ks.nu
    tau0 = float(pk.knots[0])
    K = int(math.floor(-tau0 * HZ + 1e-6))
    taus = -np.arange(K, -1, -1) / HZ
    nt = len(taus)
    M = dict(taus=taus, tau0=tau0)
    keys = ("H", "ca", "cj", "phi", "phib", "psi", "Lo", "theta", "Anet", "Apos")
    S = {k: np.zeros((nt, nv)) for k in keys}
    S["cj"] = np.zeros((nt, nv), np.int32)
    S["Hall"] = np.zeros((nt, nv))              # 唇を含む行の最高点（記録）
    S["Anet_w"] = np.full((nt, nv), np.nan)       # 225 m の窓（シート＋周りの海）の符号付きの断面積（--sea があるとき）
    S["Apos_w"] = np.full((nt, nv), np.nan)
    ymin = np.zeros(nt)
    p95 = np.zeros(nt)
    cdev = np.zeros(nt)
    tipu = np.full((nt, nv), np.nan)             # 唇先の地面の水平の速さ（t 方向）
    trough = {}
    P11 = []
    rows_k = ks.curled_idx
    tipc = ks.tip_col
    # P13（30 Hz、物理の時刻）
    step30 = dict(max=0.0, at=None)
    acc30 = dict(max=0.0, at=None)
    flips = dict(n_resolvable=0, n_region=0, n_all=0, at=None, at_region=None)
    zero_all_tstar = 0
    tri_min_region = (np.inf, None)
    tri_min_all = (np.inf, None)
    edge_min = (np.inf, None)
    edge_exempt_min = (np.inf, None)
    st_row = [np.inf, 0.0]
    st_x = [np.inf, 0.0]
    seam = [np.inf, 0.0]
    prev_loc = None
    prev_g = []
    ref_n = None
    ref_ok = None
    si_frames = set()
    for m_ in range(int(math.floor(-tau0 * 2 + 1e-6)) + 1):      # 0.5 s ごと（−2.5 s より前）
        tv = -0.5 * m_
        if tv < -2.5 - 1e-9 and tv >= tau0 - 1e-9:
            si_frames.add(round(tv * HZ))
    for m_ in range(int(2.5 * HZ_OUT) + 1):                       # 最後の 2.5 s は 30 Hz
        tv = -m_ / HZ_OUT
        if tv >= tau0 - 1e-9:
            si_frames.add(round(tv * HZ))
    si = dict(frames=0, row_hits=0, mid_hits=0, resolvable_hits=0, tau_range=None, examples=[])
    vt = ViolTracker()
    # 行の方向の辺の下限：5 mm。ただし K* でもう 5 mm に近い・未満の辺は、K* の長さ − 量子化の 2 倍（辺の両端の誤差）まで許す
    thr_e = np.minimum(TH["P13_row_edge_m"], ks.Lrow_K - 2 * pk.q_max)
    n_relaxed = int((ks.row_edge_mask & (thr_e < TH["P13_row_edge_m"])).sum())
    edge_viol = 0
    w_area = ks.vert_area
    vtip = np.array([r * nu + tipc[r] for r in rows_k])
    for k, tau in enumerate(taus):
        X = pk.world(tau)
        Vw = pk.world_vel(tau)
        A, Y, C = ks.section(X)
        cdev[k] = float(np.abs(C - ks.c[:, None]).max())
        rm = row_metrics(A, Y, ks.crest_hi, ks.j_E)
        for kk in ("H", "ca", "cj", "phi", "phib", "psi", "Lo", "theta"):
            S[kk][k] = rm[kk]
        S["Hall"][k] = Y.max(1)
        an, ap = row_areas(A, Y)
        S["Anet"][k], S["Apos"][k] = an, ap
        if sea is not None:
            # 設計27 の統合で足した（設計26 §4.1 P2 の定義どおり）：頂を中心に搬送波 1 波長（t 方向 225 m）の窓で、
            # シートの断面とその外の解析式の海（--sea の標本、τ で線形補間）をつないで符号付きの断面積を測る
            es_all, as_ = sea_rows_interp(sea, tau)
            for r in rows_k:
                a_cr = rm["ca"][r]
                w0, w1 = a_cr - TH["P2_window_half_m"], a_cr + TH["P2_window_half_m"]
                mb = (as_ >= w0) & (as_ < A[r, 0])
                mf = (as_ > A[r, -1]) & (as_ <= w1)
                pa = np.concatenate([as_[mb], A[r], as_[mf]])[None]
                py = np.concatenate([es_all[r][mb], Y[r], es_all[r][mf]])[None]
                anw, apw = row_areas(pa, py)
                S["Anet_w"][k, r], S["Apos_w"][k, r] = float(anw[0]), float(apw[0])
        ymin[k] = float(Y.min())
        sp = np.linalg.norm(Vw, axis=-1)
        body = Y > 0.5
        p95[k] = float(np.percentile(sp[body], 95)) if body.any() else 0.0
        tipu[k, rows_k] = Vw[rows_k, tipc[rows_k]] @ ks.t
        # P2：頂の前 0.5 波長以内の最低の水面（シートの上。--sea があればその標本も）
        for r in (ks.main_row, ks.peak_row):
            a_cr = rm["ca"][r]
            m = (A[r] >= a_cr) & (A[r] <= a_cr + TH["P2_ahead_m"])
            v = float(Y[r][m].min()) if m.any() else np.nan
            if sea is not None:
                es, as_ = sea_row(sea, tau, r)
                ms = (as_ > A[r].max()) & (as_ <= a_cr + TH["P2_ahead_m"])
                if ms.any():
                    v = min(v, float(es[ms].min()))
            trough.setdefault(r, []).append(v)
        # P11：K* で平らな所（y_K < 0.05H*）＝主役の峰の外の水面（シートの上）
        if tau <= TH["P11_tau"] + 1e-9:
            flat = ks.Y < 0.05 * ks.H_star
            yf = Y[flat]
            rms = float(np.sqrt(np.mean(yf ** 2))) if yf.size else 0.0
            yr = np.where(flat, Y, np.nan)
            hgt = float(np.nanmax(np.nanmax(yr, 1) - np.nanmin(yr, 1))) if flat.any() else 0.0
            if sea is not None:
                es, as_ = sea_row(sea, tau, ks.main_row)
                mm = (as_ < A[ks.main_row].min()) | (as_ > A[ks.main_row].max())
                if mm.any():
                    rms = max(rms, float(np.sqrt(np.mean(es[mm] ** 2))))
                    hgt = max(hgt, float(es[mm].max() - es[mm].min()))
            P11.append((float(tau), rms, hgt))
        # ---- 30 Hz の検査（τ = −m/30）
        if (K - k) % (HZ // HZ_OUT) == 0:
            loc = X - pk.origin(tau)[0]
            if prev_loc is not None:
                d = np.linalg.norm(loc - prev_loc, axis=-1)
                i = np.unravel_index(int(d.argmax()), d.shape)
                if d[i] > step30["max"]:
                    step30 = dict(max=float(d[i]), at=dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4)))
            prev_loc = loc
            Xg = X[rows_k]
            prev_g.append(Xg)
            if len(prev_g) == 3:
                d2 = np.linalg.norm(prev_g[2] - 2 * prev_g[1] + prev_g[0], axis=-1)
                i = np.unravel_index(int(d2.argmax()), d2.shape)
                if d2[i] > acc30["max"]:
                    acc30 = dict(max=float(d2[i]), at=dict(row=int(rows_k[i[0]]), col=int(i[1]), tau=round(float(tau) - 1.0 / HZ_OUT, 4)))
                prev_g.pop(0)
            nrm = tri_normals(X)
            nl = np.linalg.norm(nrm, axis=-1)
            ar = 0.5 * nl
            if k == nt - 1:
                zero_all_tstar = int((ar < 1e-10).sum())
            region3 = np.broadcast_to(ks.tri_mask[..., None], ar.shape)
            arr = np.where(region3, ar, np.inf)
            i = np.unravel_index(int(arr.argmin()), arr.shape)
            if arr[i] < tri_min_region[0]:
                tri_min_region = (float(arr[i]), dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4)))
            ar6 = np.where(np.broadcast_to(ks.ring_mask[..., None], ar.shape), ar, np.inf)
            i = np.unravel_index(int(ar6.argmin()), ar6.shape)
            if ar6[i] < tri_min_all[0]:
                tri_min_all = (float(ar6[i]), dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4)))
            # 面の反転：向きの決まった最後のコマの法線と比べる（面積 0 を通って裏返るのも数える）
            un_ = nrm / np.maximum(nl[..., None], 1e-15)
            valid = ar > 1e-10
            if ref_n is not None:
                dots = (un_ * ref_n).sum(-1)
                bad = valid & ref_ok & (dots <= 0)
                if bad.any():
                    br = bad & ks.tri_resolvable
                    bg = bad & region3
                    vt.add("5g", int((br | bg).sum()), tau)
                    flips["n_all"] += int(bad.sum())
                    flips["n_resolvable"] += int(br.sum())
                    flips["n_region"] += int(bg.sum())
                    if flips["at"] is None and br.any():
                        i = np.unravel_index(int(np.argmax(br)), br.shape)
                        flips["at"] = dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4))
                    if flips["at_region"] is None and bg.any():
                        i = np.unravel_index(int(np.argmax(bg)), bg.shape)
                        flips["at_region"] = dict(row=int(i[0]), col=int(i[1]), tri=int(i[2]), tau=round(float(tau), 4))
                ref_n = np.where(valid[..., None], un_, ref_n)
                ref_ok = ref_ok | valid
            else:
                ref_n = un_.copy()
                ref_ok = valid.copy()
            Lr = np.linalg.norm(np.diff(X, axis=1), axis=-1)
            v = np.where(ks.row_edge_mask, Lr, np.inf)
            i = np.unravel_index(int(v.argmin()), v.shape)
            if v[i] < edge_min[0]:
                edge_min = (float(v[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4), K_len_m=round(float(ks.Lrow_K[i]), 5)))
            mg = np.where(ks.row_edge_mask, Lr - thr_e, np.inf)
            i = np.unravel_index(int(mg.argmin()), mg.shape)
            nv_ = int((mg < 0).sum())
            edge_viol += nv_
            vt.add("5b", nv_, tau)
            if mg[i] < edge_exempt_min[0]:
                edge_exempt_min = (float(mg[i]), dict(row=int(i[0]), col=int(i[1]), tau=round(float(tau), 4), len_m=round(float(Lr[i]), 5),
                                                     threshold_m=round(float(thr_e[i]), 5)))
            vt.add("5a", int(((arr < TH["P13_tri_area_m2"])).sum()), tau)
            vt.add("6", int((ar6 <= 1e-10).sum()), tau)
            # 伸びの比：表示は生の比、判定は量子化の分（辺の長さ ±2q）を差し引いた比
            q2 = 2 * pk.q_max

            def ratio_check(L, LK, mask, key, acc):
                raw = L[mask] / np.maximum(LK[mask], 1e-9)
                lo_ = (L[mask] + q2) / np.maximum(LK[mask], 1e-9)
                hi_ = np.maximum(L[mask] - q2, 0) / np.maximum(LK[mask], 1e-9)
                acc[0] = min(acc[0], float(raw.min()))
                acc[1] = max(acc[1], float(raw.max()))
                lo_b, hi_b = (TH["P13_seam_lo"], TH["P13_seam_hi"]) if key == "5e" else (TH["P13_stretch_lo"], TH["P13_stretch_hi"])
                vt.add(key, int((lo_ < lo_b).sum() + (hi_ > hi_b).sum()), tau)

            ratio_check(Lr, ks.Lrow_K, ks.row_edge_mask, "5c", st_row)
            Lv = np.linalg.norm(X[1:] - X[:-1], axis=-1)
            Ld = np.linalg.norm(X[1:, :-1] - X[:-1, 1:], axis=-1)
            ratio_check(np.concatenate([Lv[ks.vedge_mask], Ld[ks.dedge_mask]])[None], np.concatenate([ks.Lv_K[ks.vedge_mask], ks.Ld_K[ks.dedge_mask]])[None],
                        np.ones((1, int(ks.vedge_mask.sum() + ks.dedge_mask.sum())), bool), "5d", st_x)
            sr_r = np.array([r for r, j in ks.seam])
            sr_j = np.array([j for r, j in ks.seam])
            ratio_check(Lr[sr_r, sr_j][None], ks.Lrow_K[sr_r, sr_j][None], np.ones((1, len(sr_r)), bool), "5e", seam)
        # ---- 自己交差（間引いたコマ）
        if round(tau * HZ) in si_frames:
            si["frames"] += 1
            Pr = np.stack([A[rows_k, ks.J0:ks.J1 + 1], Y[rows_k, ks.J0:ks.J1 + 1]], -1)
            hits, nres = seg_crossings(Pr)
            if len(hits):
                si["row_hits"] += int(len(hits))
                si["resolvable_hits"] += nres
                tr = si["tau_range"] or [float(tau), float(tau)]
                si["tau_range"] = [min(tr[0], float(tau)), max(tr[1], float(tau))]
                if len(si["examples"]) < 6:
                    h0 = hits[0]
                    si["examples"].append(dict(kind="row", row=int(rows_k[h0[0]]), seg_cols=[int(ks.J0 + h0[1]), int(ks.J0 + h0[2])], tau=round(float(tau), 4)))
            # 隣り合う巻きの行の間の中央の面での切り口（三角形の分け方どおり M_j, D_j, M_{j+1}, ...）
            pr = rows_k[:-1][np.diff(rows_k) == 1]
            j0, j1 = ks.J0, ks.J1
            Mx = 0.5 * (X[pr, j0:j1 + 1] + X[pr + 1, j0:j1 + 1])
            Dx = 0.5 * (X[pr, j0 + 1:j1 + 1] + X[pr + 1, j0:j1])
            n_ = Mx.shape[1]
            Q = np.empty((len(pr), 2 * n_ - 1, 3))
            Q[:, 0::2] = Mx
            Q[:, 1::2] = Dx
            Da = (Q - ks.O) @ ks.t
            Pm = np.stack([Da, Q[..., 1]], -1)
            hits, nres = seg_crossings(Pm)
            if len(hits):
                si["mid_hits"] += int(len(hits))
                si["resolvable_hits"] += nres
                tr = si["tau_range"] or [float(tau), float(tau)]
                si["tau_range"] = [min(tr[0], float(tau)), max(tr[1], float(tau))]
                if len(si["examples"]) < 6:
                    si["examples"].append(dict(kind="mid", rows=[int(pr[hits[0][0]]), int(pr[hits[0][0]] + 1)], tau=round(float(tau), 4)))
        if k % 120 == 0:
            log("  frame %d/%d τ=%.2f (%.0f s)" % (k, nt, tau, time.time() - t_clock))
    M.update(S=S, ymin=ymin, p95=p95, cdev=cdev, tipu=tipu, trough=trough, P11=P11,
             P13=dict(step30=step30, acc30=acc30, flips=flips, tri_min_all=tri_min_all, tri_min_region=tri_min_region, zero_area_all_tstar=zero_all_tstar,
                      edge_min=edge_min, edge_margin_min=edge_exempt_min, n_edge_relaxed=n_relaxed, edge_violations=edge_viol,
                      stretch_row=st_row, stretch_cross=st_x, seam=seam, si=si, viol=vt.d,
                      tri_min_region_K=float(ks.tri_area_K[ks.tri_mask].min())))
    # ---- 唇先の運動（240 Hz、物理の時刻）
    tk = np.linspace(tau0, 0.0, int(round(-tau0 * HZ_KIN)) + 1)
    Xt = pk.sub(tk, vtip, 0)
    Vt = pk.sub(tk, vtip, 1)
    At = pk.sub(tk, vtip, 2)
    M["kin"] = dict(tau=tk, rows=rows_k, a=(Xt - ks.O) @ ks.t, y=Xt[..., 1], va=Vt @ ks.t, vy=Vt[..., 1], ay=At[..., 1], vtip=vtip)
    # ---- t* の姿（K* との差）と t* の速さ
    X0 = pk.world(0.0)
    M["X0"] = X0
    M["V0"] = pk.world_vel(0.0)
    M["runtime_measure_s"] = time.time() - t_clock
    return M


def sea_rows_interp(sea, tau):
    """周りの海の標本（全行）を τ で線形に補間する。戻り (eta (nv, na), a (na,))。"""
    ts = sea["tau"]
    k = int(np.clip(np.searchsorted(ts, tau) - 1, 0, len(ts) - 2))
    f = float(np.clip((tau - ts[k]) / max(ts[k + 1] - ts[k], 1e-12), 0.0, 1.0))
    e0, e1 = sea["eta"][k], sea["eta"][k + 1]
    eta = e0 + f * (e1 - e0)
    if eta.ndim == 1:
        eta = np.broadcast_to(eta, (len(sea.get("c", [0])) or 1, eta.shape[0]))
    return eta, sea["a"]


def sea_row(sea, tau, r):
    k = int(np.argmin(np.abs(sea["tau"] - tau)))
    eta = sea["eta"][k]
    if eta.ndim == 2:
        eta = eta[r]
    return eta, sea["a"]


# ---------------------------------------------------------------- 関門
def gate(name_ja, value, threshold, ok, detail=None, scope=None):
    g = dict(name_ja=name_ja, value=value, threshold=threshold, pass_=ok, detail=detail or {})
    if scope:
        g["scope_ja"] = scope
    return g


def evaluate(ks, pk, tw, M, sibling=None, sea_used=False, cond=None):
    taus = M["taus"]
    S = M["S"]
    nv, nu = ks.nv, ks.nu
    mr, pr = ks.main_row, ks.peak_row
    rows_k = ks.curled_idx
    Hf = S["H"][-1]                                   # 行ごとの t* の頂の高さ（包みの τ = 0）
    Hn = S["H"] / np.maximum(Hf[None, :], 1e-9)
    tw_T = pk.twhite
    white_ok = tw_T < NEVER
    out = {}
    named = {mr: "主断面", pr: "峰で最も高い巻きの行"}

    # 噴流の始まり（前面が鉛直＝φ ≥ 90° を初めて満たす時刻）
    onset = np.full(nv, np.nan)
    for r in rows_k:
        tt, _ = first_true(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0, taus)
        if tt is not None:
            onset[r] = tt

    # 頂の速さ（地面、t 方向）
    ca_v = np.gradient(S["ca"], taus, axis=0)

    # ---- P1
    det = {}
    ok = True
    vals = []
    i3 = int(np.argmin(np.abs(taus + TH["P1_window_s"])))
    for r in (mr, pr):
        spd = (S["ca"][-1, r] - S["ca"][i3, r]) / (taus[-1] - taus[i3])
        back = drawdown(S["ca"][:, r])
        det[named[r]] = dict(row=int(r), c_m=fnum(ks.c[r], 2), mean_speed_mps=fnum(spd, 3), back_travel_m=fnum(back, 4))
        ok &= spd >= TH["P1_speed_mps"] and back <= TH["P1_back_m"]
        vals.append(spd)
    allsp = (S["ca"][-1, rows_k] - S["ca"][i3, rows_k]) / (taus[-1] - taus[i3])
    det["巻きの行の最小の速さ_mps"] = fnum(allsp.min(), 3)
    out["P1"] = gate("峰が進む（τ −3〜0 s の地面での平均の速さ、後ろへの戻り）", fnum(min(vals), 3),
                     "≥ %.0f m/s、戻り ≤ %.2f m（主断面と峰の行）" % (TH["P1_speed_mps"], TH["P1_back_m"]), bool(ok), det)

    # ---- P2（A_pos < 1 m² の行・コマ＝波がまだない所は、比が定まらないので除く）
    # 設計27 の統合で直した：--sea があれば、設計26 §4.1 の定義どおり 225 m の窓（シート＋周りの海）で測る。
    # 入れた版（ds_sea_calm_painting が入っている）では、周りの海を平らにする最後の約 2 s（τ > −2.0 s）を判定から除いて記録する
    win = sea_used and np.isfinite(S["Anet_w"][:, rows_k]).all()
    calm_on = calm_painting_on(pk)
    Anet_s = S["Anet_w"] if win else S["Anet"]
    Apos_s = S["Apos_w"] if win else S["Apos"]
    judge = np.ones(len(taus), bool)
    if calm_on:
        judge = taus <= TH["P2_calm_painting_from_tau"] + 1e-9
    Apos = Apos_s[:, rows_k]
    ratio_all = np.where(Apos >= 1.0, np.abs(Anet_s[:, rows_k]) / np.maximum(Apos, 1e-9), np.nan)
    ratio = np.where(judge[:, None], ratio_all, np.nan)
    if not np.isfinite(ratio).any():
        ratio = np.zeros_like(ratio)
    i = np.unravel_index(int(np.nanargmax(ratio)), ratio.shape)
    tro = {}
    tro_ok = True
    for r in (mr, pr):
        tv = np.array(M["trough"][r])
        # 段階 a〜c の間（表の τ ±0.3 s を含む窓。段階が測れた場合はその時刻）
        lo, hi = -4.5, -1.9
        m = (taus >= lo) & (taus <= hi)
        v = float(np.nanmin(tv[m])) if m.any() else np.nan
        tro[named[r]] = fnum(v, 3)
        tro_ok &= (v <= TH["P2_trough_over_Hstar"] * ks.H_star)
    rmax = float(np.nanmax(ratio))
    ok = bool(rmax <= TH["P2_ratio"]) and bool(tro_ok)
    out["P2"] = gate("谷と釣り合う（行ごとの符号付きの断面積 |A_net| / A_pos、段階 a〜c の前 0.5 波長の谷）",
                     fnum(rmax, 3), "毎フレーム ≤ %.1f、谷 ≤ %.2f m" % (TH["P2_ratio"], TH["P2_trough_over_Hstar"] * ks.H_star), ok,
                     dict(worst_row=int(rows_k[i[1]]), worst_tau=fnum(taus[i[0]], 3), main_row_max_ratio=fnum(float(np.nanmax(ratio[:, list(rows_k).index(mr)])), 3),
                          excluded_row_frames_Apos_lt_1m2=int((Apos < 1.0).sum()),
                          area_window_ja=("頂を中心に 225 m の窓（シート＋ --sea の周りの海、τ で線形補間）" if win else "シートの上だけ"),
                          calm_painting_excluded_ja=("τ > %.1f s（ds_sea_calm_painting で周りの海を平らにする区間）は判定から除いた。記録：その区間の比の最大 %s" % (
                              TH["P2_calm_painting_from_tau"], fnum(float(np.nanmax(ratio_all[~judge])) if (~judge).any() else None, 3)) if calm_on else None),
                          sheet_only_max_ratio=fnum(float(np.nanmax(np.where(S["Apos"][:, rows_k] >= 1.0, np.abs(S["Anet"][:, rows_k]) / np.maximum(S["Apos"][:, rows_k], 1e-9), np.nan))), 3),
                          trough_ahead_min_m=tro, window_ja="谷：τ −4.5〜−1.9 s（段階 a〜c の表の時刻 ±0.3 s）"),
                     scope=None if sea_used else "シートの上だけ（包みに周りの海の式がない。--sea で渡せば窓 225 m まで測る）")

    # ---- P3（P2 と同じ窓の A_net。入れた版は P2 と同じく周りの海を平らにする区間を除く。分母はその行の t* の A_pos）
    worst = (0.0, None)
    worst_all = (0.0, None)
    n_empty = 0
    for r in rows_k:
        if not np.isfinite(onset[r]):
            continue
        m_all = taus >= onset[r]
        m = m_all & judge
        k0 = int(np.nonzero(m_all)[0][0])
        den = max(Apos_s[-1, r], 1e-9)
        dev_all = np.abs(Anet_s[m_all, r] - Anet_s[k0, r]).max() / den
        if dev_all > worst_all[0]:
            worst_all = (float(dev_all), int(r))
        if not m.any():
            n_empty += 1
            continue
        dev = np.abs(Anet_s[m, r] - Anet_s[k0, r]).max() / den
        if dev > worst[0]:
            worst = (float(dev), int(r))
    km = int(np.nonzero(taus >= onset[mr])[0][0]) if np.isfinite(onset[mr]) else None
    kme = int(np.nonzero(judge)[0][-1])
    main_dev = (float((Anet_s[kme, mr] - Anet_s[km, mr]) / max(Apos_s[-1, mr], 1e-9)) if (km is not None and kme >= km) else None)
    dc = np.gradient(ks.c)
    vol = (S["Anet"] * dc[None, :]).sum(1)
    # 設計27 のレビュー対応（記録だけ。判定は変えない）：判定の区間の長さと、除いた区間を含めた始まり → t* の値（主断面・峰の行）、
    # シートの上の水の量の最大の後の最小（巻きの間に水が減って t* の前に戻るか）
    p3_rows = {}
    for r in (mr, pr):
        if not np.isfinite(onset[r]):
            continue
        m_all = taus >= onset[r]
        k0 = int(np.nonzero(m_all)[0][0])
        den = max(Apos_s[-1, r], 1e-9)
        d_all = (Anet_s[m_all, r] - Anet_s[k0, r]) / den
        jl = float(max(0.0, min(TH["P2_calm_painting_from_tau"], 0.0) - onset[r])) if calm_on else float(-onset[r])
        p3_rows[named[r]] = dict(row=int(r), onset_tau=fnum(onset[r], 3), judged_interval_s=fnum(jl, 3),
                                 full_interval_max_abs_change_frac=fnum(float(np.abs(d_all).max()), 4),
                                 full_interval_change_at_tstar_frac=fnum(float(d_all[-1]), 4),
                                 window_Anet_onset_m2=fnum(Anet_s[k0, r], 1), window_Anet_tstar_m2=fnum(Anet_s[-1, r], 1),
                                 window_Apos_tstar_m2=fnum(Apos_s[-1, r], 1),
                                 sheet_Anet_series_m2={("%.1f" % tv): fnum(S["Anet"][int(np.argmin(np.abs(taus - tv))), r], 1)
                                                       for tv in (-3.2, -2.4, -2.0, -1.6, -1.2, -1.0, -0.8, -0.4, 0.0)})
    kv = int(vol.argmax())
    kv_min = kv + int(vol[kv:].argmin())
    out["P3"] = gate("巻いても水が消えない（前面が鉛直になってから t* までの行ごとの A_net の変化 / t* の A_pos）",
                     fnum(worst[0], 4), "≤ %.2f（全巻きの行）" % TH["P3_frac"], worst[0] <= TH["P3_frac"],
                     dict(worst_row=worst[1], main_row_change_frac=fnum(main_dev, 4),
                          area_window_ja=("P2 と同じ 225 m の窓" if win else "シートの上だけ"),
                          calm_painting_excluded_ja=("τ > %.1f s を除いた。除いた区間を含めた最大 %s（行 %s）。判定の区間が空の行 %d" % (
                              TH["P2_calm_painting_from_tau"], fnum(worst_all[0], 4), worst_all[1], n_empty) if calm_on else None),
                          full_interval_worst_frac=fnum(worst_all[0], 4), full_interval_worst_row=worst_all[1],
                          rows_with_onset=int(np.isfinite(onset[rows_k]).sum()), rows_judged_interval_empty=int(n_empty),
                          rows_record_ja="記録（判定は変えない）：判定の区間の長さと、除いた区間を含めた始まり → t* の窓の A_net の変化 / t* の A_pos",
                          rows_record=p3_rows,
                          volume_above_swl_max_m3=fnum(vol.max(), 1), volume_max_tau=fnum(taus[kv], 3),
                          volume_min_after_max_m3=fnum(vol[kv_min], 1), volume_min_after_max_tau=fnum(taus[kv_min], 3),
                          volume_drop_to_min_frac=fnum(1 - vol[kv_min] / vol.max(), 4),
                          volume_rise_min_to_tstar_frac=fnum(vol[-1] / max(vol[kv_min], 1e-9) - 1, 4),
                          volume_tstar_m3=fnum(vol[-1], 1), volume_loss_from_max_frac=fnum(1 - vol[-1] / vol.max(), 4),
                          volume_ja="シートの上（窓ではない）の符号付きの断面積 × 行の間隔の和（m³）。記録のみ"),
                     scope=None if sea_used else "シートの上だけ")

    # ---- P4・P5・P16 用の唇先の運動
    kin = M["kin"]
    ktau = kin["tau"]
    rpos = {int(r): i for i, r in enumerate(kin["rows"])}

    def tip_series(r):
        i = rpos[r]
        return kin["a"][:, i], kin["y"][:, i], kin["va"][:, i], kin["vy"][:, i], kin["ay"][:, i]

    def ramp_end(r):
        """打ち出しの補間の終わり：測った噴流の始まり＋min(0.6, 始まりから t* までの半分) と、設計26 の表の放出の時刻から同じく求めた値の遅い方。"""
        vals_ = []
        if np.isfinite(onset[r]):
            vals_.append(onset[r] + min(0.6, -onset[r] / 2))
        if cond is not None:
            T_row = max(abs(cond["tau0"]) - abs(ks.c[r] - ks.c[pr]) / cond["peel"], cond["floor"])
            vals_.append(-T_row + min(0.6, T_row / 2))
        return max(vals_) if vals_ else None

    det = {}
    ok = True
    val = None
    for r in (mr, pr):
        a_, y_, va_, vy_, ay_ = tip_series(r)
        yK = y_[-1]
        start = onset[r] if np.isfinite(onset[r]) else ktau[0]
        m = ktau >= start
        k_ap = int(np.nonzero(m)[0][0] + np.argmax(y_[m]))
        t_ap = float(ktau[k_ap])
        if k_ap >= len(ktau) - 2:        # 頂点がない（上がり続ける）→ 張り出し 0.05H の時刻から
            lo_t, _ = first_true(np.nan_to_num(S["Lo"][:, r]) >= 0.05 * np.maximum(S["H"][:, r], 1e-9), taus)
            t_ap = lo_t if lo_t is not None else t_ap
            k_ap = int(np.argmin(np.abs(ktau - t_ap)))
        wins = []
        tw0 = t_ap
        while tw0 < -1e-9:
            tw1 = min(tw0 + TH["P4_win_s"], 0.0)
            if tw1 - tw0 < 0.5 * TH["P4_win_s"] and wins:
                break
            v0, v1 = np.interp(tw0, ktau, vy_), np.interp(tw1, ktau, vy_)
            wins.append(round(float((v1 - v0) / (tw1 - tw0)), 3))
            tw0 = tw1
        mean_acc = float((vy_[-1] - vy_[k_ap]) / max(-t_ap, 1e-9))
        h = 1.0 / HZ_OUT
        vp = np.interp(ktau + h, ktau, vy_)
        vm = np.interp(ktau - h, ktau, vy_)
        asm = (vp - vm) / (2 * h)
        up = (asm > 0) & (ktau >= t_ap) & (ktau <= -h)
        run = 0.0
        best = 0.0
        for u in up:
            run = run + 1.0 / HZ_KIN if u else 0.0
            best = max(best, run)
        y_ap = float(y_[k_ap])
        after = np.nonzero((ktau > t_ap) & (y_ <= yK + 1e-6))[0]
        t_reach = float(ktau[after[0]]) if len(after) else 0.0
        fall = t_reach - t_ap
        fall_ref = math.sqrt(max(2 * (y_ap - yK) / G, 0.0))
        fr = fall / fall_ref if fall_ref > 0 else np.nan
        okr = (len(wins) > 0 and all(TH["P4_acc_lo"] <= w <= TH["P4_acc_hi"] for w in wins) and best <= TH["P4_up_run_s"]
               and np.isfinite(fr) and abs(fr - 1) <= TH["P4_fall_tol"])
        ok &= okr
        det[named[r]] = dict(tip_col=int(ks.tip_col[r]), apex_tau=fnum(t_ap, 3), apex_y_m=fnum(y_ap, 3), window_mean_acc_mps2=wins,
                             mean_acc_apex_to_tstar_mps2=fnum(mean_acc, 3), longest_upward_run_s=fnum(best, 3),
                             fall_time_s=fnum(fall, 3), fall_ref_s=fnum(fall_ref, 3), fall_ratio=fnum(fr, 3))
        if r == mr:
            val = mean_acc
    out["P4"] = gate("唇先は投げ出された水（頂点から t* まで 0.3 s ごとの縦の加速度の平均、上向きの続く時間、落下時間）",
                     fnum(val, 3), "各区間 %.1f〜%.1f m/s²、上向き ≤ %.1f s、落下 √(2Δy/g) ±%d%%" % (TH["P4_acc_lo"], TH["P4_acc_hi"], TH["P4_up_run_s"], int(TH["P4_fall_tol"] * 100)),
                     bool(ok), det)

    # ---- P5
    det = {}
    ok = True
    vmin = None
    for r in (mr, pr):
        if not np.isfinite(onset[r]):
            det[named[r]] = "噴流の始まり（φ ≥ 90°）がない"
            ok = False
            continue
        te = min(onset[r] + min(0.6, -onset[r] / 2), 0.0)
        a_, y_, va_, vy_, ay_ = tip_series(r)
        m = (ktau >= onset[r]) & (ktau <= te + 1e-9)
        k = int(np.nonzero(m)[0][0] + np.argmax(va_[m]))
        u = float(va_[k])
        cs = float(np.interp(ktau[k], taus, ca_v[:, r]))
        det[named[r]] = dict(onset_tau=fnum(onset[r], 3), window_tau=[fnum(onset[r], 3), fnum(te, 3)], tip_u_max_mps=fnum(u, 3),
                             at_tau=fnum(ktau[k], 3), crest_speed_mps=fnum(cs, 3))
        ok &= (u >= TH["P5_speed_mps"]) and (u >= cs)
        vmin = u if vmin is None else min(vmin, u)
    ts_all = np.hypot(np.gradient(kin["a"][:, rpos[mr]], ktau), np.gradient(kin["y"][:, rpos[mr]], ktau))
    det["主断面の唇先の速さの最大_全区間_mps"] = fnum(ts_all.max(), 3)
    # 設計27 のレビュー対応（記録だけ）：打ち出しの補間の終わり（P16 の窓の始まりと同じ ramp_end）の唇先の地面の速さ
    # （P5 の窓は測った始まりから 0.6 s までなので、生成器が唇先を放す前に終わる行がある）
    post = {}
    for r in rows_k:
        re_ = ramp_end(int(r))
        if re_ is None or re_ >= 0.0:
            continue
        i = rpos[int(r)]
        post[int(r)] = (float(np.interp(re_, ktau, kin["va"][:, i])), float(np.hypot(np.interp(re_, ktau, kin["va"][:, i]), np.interp(re_, ktau, kin["vy"][:, i]))))
    if post:
        uu = np.array([v[0] for v in post.values()])
        det["打ち出しの補間の後の唇先_記録"] = dict(
            ja="ramp_end の時刻の唇先の地面の水平の速さ・速さ（記録のみ）", rows=len(post),
            horizontal_median_mps=fnum(float(np.median(uu)), 3), speed_median_mps=fnum(float(np.median([v[1] for v in post.values()])), 3),
            main_row_horizontal_mps=fnum(post.get(int(mr), (np.nan,))[0], 3), peak_row_horizontal_mps=fnum(post.get(int(pr), (np.nan,))[0], 3),
            main_row_speed_mps=fnum(post.get(int(mr), (np.nan, np.nan))[1], 3), peak_row_speed_mps=fnum(post.get(int(pr), (np.nan, np.nan))[1], 3))
    out["P5"] = gate("唇先の速さ（噴流が出る時の水平の速さ。始まりから打ち出しの補間の終わりまでの最大）", fnum(vmin, 3),
                     "≥ %.0f m/s かつ ≥ 峰の速さ" % TH["P5_speed_mps"], bool(ok), det)

    # ---- P6（t* の速さ、地面。唇の上面の列 jt..jtip）
    det = {}
    ok = True
    vv = None
    for r in (mr, pr):
        q = ks.cq[r]
        V = M["V0"][r, q["jt"]:q["jtip"] + 1]
        sp = np.linalg.norm(V, axis=-1)
        uh = V @ ks.t
        root, tip = sp[0], sp[-1]
        mid = sp[1:-1].min() if len(sp) > 2 else root
        r1 = mid / max(root, 1e-9)
        r2 = uh[0] / max(uh[-1], 1e-9)
        ok &= (r1 >= TH["P6_mid_over_root"]) and (r2 >= TH["P6_root_over_tip_h"])
        det[named[r]] = dict(cols=[q["jt"], q["jtip"]], root_speed_mps=fnum(root, 3), tip_speed_mps=fnum(tip, 3), mid_min_mps=fnum(mid, 3),
                             mid_over_root=fnum(r1, 3), root_h_over_tip_h=fnum(r2, 3))
        if r == mr:
            vv = r1
    out["P6"] = gate("唇は頂に運ばれる（t* の唇に沿った地面の速さ）", fnum(vv, 3),
                     "途中の最小 ≥ %.1f × 根元、根元の水平 ≥ %.1f × 唇先の水平" % (TH["P6_mid_over_root"], TH["P6_root_over_tip_h"]), bool(ok), det)

    # ---- P7
    det = {}
    ok = True
    for r in (mr, pr):
        dur = -onset[r] if np.isfinite(onset[r]) else None
        det[named[r]] = dict(onset_tau=fnum(onset[r], 3), vertical_to_tstar_s=fnum(dur, 3))
        ok &= dur is not None and TH["P7_lo_s"] <= dur <= TH["P7_hi_s"]
    oc = onset[rows_k]
    det["巻きの行の始まりの範囲_tau"] = [fnum(np.nanmin(oc), 3), fnum(np.nanmax(oc), 3)] if np.isfinite(oc).any() else None
    det["始まりのない巻きの行の数"] = int((~np.isfinite(oc)).sum())
    out["P7"] = gate("巻きの時間（前面が鉛直 → t*、物理の時刻）", fnum(-onset[mr] if np.isfinite(onset[mr]) else None, 3),
                     "%.1f〜%.1f s（主断面と峰の行）" % (TH["P7_lo_s"], TH["P7_hi_s"]), bool(ok), det)

    # ---- P8
    k8 = int(np.argmin(np.abs(taus - TH["P8_tau"])))
    fr8 = M["p95"][k8] / max(M["p95"].max(), 1e-9)
    out["P8"] = gate("止め方（τ −0.2 s の水面の速さ p95 / 最大、地面）", fnum(fr8, 3), "≥ %.1f" % TH["P8_frac"], bool(fr8 >= TH["P8_frac"]),
                     dict(p95_at_tau_mps=fnum(M["p95"][k8], 3), p95_max_mps=fnum(M["p95"].max(), 3), p95_max_tau=fnum(taus[int(M["p95"].argmax())], 3)))

    # ---- P9
    T = tw_T
    finalw = white_ok & (T <= 0.0)
    wv = ks.vert_area
    Wtot = float((wv * finalw).sum())

    def wfrac(tau):
        return float((wv * (finalw & (T <= tau))).sum()) / max(Wtot, 1e-12)

    row_first = np.where(finalw.any(1), np.where(finalw, T, np.inf).min(1), np.inf)
    lead = []
    for r in rows_k:
        if np.isfinite(onset[r]) and np.isfinite(row_first[r]):
            lead.append((row_first[r] - onset[r], int(r)))
    lead_min = min(lead) if lead else (None, None)
    no_onset_white = [int(r) for r in range(nv) if np.isfinite(row_first[r]) and not (ks.is_curled[r] and np.isfinite(onset[r]))]
    frac_on = wfrac(onset[mr]) if np.isfinite(onset[mr]) else None
    tip_ok, first_info = first_white_at_tip(ks, T, finalw)
    ok = (lead_min[0] is not None and lead_min[0] >= -TH["P9_lead_s"] and frac_on is not None and frac_on <= TH["P9_frac"] and tip_ok)
    out["P9"] = gate("白は砕波から（行ごとの最初の白 − 噴流の始まり、主断面の始まりでの白の割合、最初の白は唇先）",
                     fnum(lead_min[0], 3), "≥ −%.1f s、割合 ≤ %.0f%%、最初の白が唇先" % (TH["P9_lead_s"], TH["P9_frac"] * 100), bool(ok),
                     dict(worst_row=lead_min[1], white_fraction_at_main_onset=fnum(frac_on, 4), first_white=first_info,
                          rows_white_without_onset=len(no_onset_white),
                          rows_white_without_onset_c_range=([fnum(ks.c[min(no_onset_white)], 2), fnum(ks.c[max(no_onset_white)], 2)] if no_onset_white else None),
                          note_ja="噴流の始まりのない行（奥の壁など）の白は記録のみ（ds_farwall_hold）。割合は K* の頂点の面積の重み"))

    # ---- P10
    ok_rows = [r for r in rows_k if np.isfinite(onset[r])]
    if len(ok_rows) >= 3:
        corr = float(np.corrcoef(onset[ok_rows], Hf[ok_rows])[0, 1])
    else:
        corr = None
    t50 = np.array([first_true(S["H"][:, r] >= 0.5 * Hf[r], taus)[0] for r in rows_k], dtype=float)
    std50 = float(np.nanstd(t50))
    big = np.nonzero(Hf > 3.0)[0]
    t50b = np.array([first_true(S["H"][:, r] >= 0.5 * Hf[r], taus)[0] for r in big], dtype=float)
    ok = corr is not None and corr <= TH["P10_corr"] and std50 >= TH["P10_std_s"]
    out["P10"] = gate("波峰線に沿った順（噴流の始まりと頂の高さの相関、0.5H に届く時刻の行の間の標準偏差）", fnum(corr, 3),
                      "相関 ≤ %.1f、標準偏差 ≥ %.1f s（巻きの行）" % (TH["P10_corr"], TH["P10_std_s"]), bool(ok),
                      dict(rows=len(ok_rows), t50_std_s=fnum(std50, 4), t50_range_tau=[fnum(np.nanmin(t50), 3), fnum(np.nanmax(t50), 3)],
                           big_rows_H_gt_3m=int(len(big)), big_rows_t50_std_s=fnum(np.nanstd(t50b), 4)))

    # ---- P11
    P11 = np.array(M["P11"]) if M["P11"] else np.zeros((0, 3))
    if len(P11):
        rms_min, h_min = float(P11[:, 1].min()), float(P11[:, 2].min())
        ok = rms_min >= TH["P11_rms_over_Hstar"] * ks.H_star and h_min >= TH["P11_height_over_Hstar"] * ks.H_star
    else:
        rms_min = h_min = None
        ok = False
    out["P11"] = gate("海が波を運ぶ（τ ≤ −4 s の主役の峰の外の水面の RMS と、見える波の高さ）", fnum(rms_min, 3),
                      "RMS ≥ %.2f m、波高 ≥ %.2f m" % (TH["P11_rms_over_Hstar"] * ks.H_star, TH["P11_height_over_Hstar"] * ks.H_star), bool(ok),
                      dict(frames=int(len(P11)), height_min_m=fnum(h_min, 3), outside_def_ja="K* で y < 0.05H* の頂点（平らな縁と端の低い行）"),
                      scope=None if sea_used else "シートの上だけ（シートは a 方向に約 82 m。周りの海の式は包みにない）")

    # ---- P12
    det = {}
    ok = True
    worst = 0.0
    for r in (mr, pr):
        dd = drawdown(S["ca"][:, r])
        det[named[r]] = fnum(dd, 4)
        ok &= dd <= TH["P12_back_m"]
        worst = max(worst, dd)
    allc = [drawdown(S["ca"][:, r]) for r in rows_k]
    det["巻きの行の最大の戻り_m"] = fnum(max(allc), 4)
    det["巻きの行の最大の戻りの行"] = int(rows_k[int(np.argmax(allc))])
    out["P12"] = gate("峰が後ろへ戻らない（t* までの頂の位置、地面）", fnum(worst, 4), "戻り ≤ %.2f m（主断面と峰の行）" % TH["P12_back_m"], bool(ok), det)

    # ---- P13
    P = M["P13"]
    items = {}
    # (1)〜(4) は Step_30 の項目（設計26 で測り方を変えた）、(5)(6) は設計26 で足した網の形の項目
    items["(1) 波の枠の 1 コマの変位（30 Hz）_m"] =(P["step30"]["max"], "< %.1f" % TH["P13_step_m"], P["step30"]["max"] < TH["P13_step_m"], P["step30"]["at"])
    lim2 = TH["P13_acc_g"] * G / HZ_OUT ** 2
    items["(2) 地面の二階差分（30 Hz、全巻きの行の全点）_m"] = (P["acc30"]["max"], "≤ %.4f（2g）" % lim2, P["acc30"]["max"] <= lim2, P["acc30"]["at"])
    items["(3) 最も低い点_m"] = (float(M["ymin"].min()), "≥ %.2f（−0.5H*）" % (TH["P13_ymin_over_Hstar"] * ks.H_star),
                            float(M["ymin"].min()) >= TH["P13_ymin_over_Hstar"] * ks.H_star, dict(tau=fnum(taus[int(M["ymin"].argmin())], 3)))
    mono = {named[mr]: drawdown(S["H"][:, mr]), named[pr]: drawdown(S["H"][:, pr]), "全行の最高": drawdown(S["H"].max(1))}
    mw = max(mono.values())
    items["(4) 頂の高さの単調（戻りの最大）_m"] = (mw, "≤ %.2f" % TH["P13_crest_mono_m"], mw <= TH["P13_crest_mono_m"], {k: fnum(v, 4) for k, v in mono.items()})
    V_ = P["viol"]
    vinfo = lambda key: dict(violations=V_.get(key, {}).get("n", 0), frames=V_.get(key, {}).get("frames", 0), tau_range=V_.get(key, {}).get("tau_range"))
    vok = lambda key: V_.get(key, {}).get("n", 0) == 0
    items["(5a) 唇・管の三角形の面積の最小_m2"] = (P["tri_min_region"][0], "≥ %.0e（K* のこの部分は %.1e）" % (TH["P13_tri_area_m2"], P["tri_min_region_K"]),
                                     vok("5a"), dict(at=P["tri_min_region"][1], **vinfo("5a")))
    items["(5b) 行の方向の辺の最小_m"] = (P["edge_min"][0], "≥ %.3f（K* で 5 mm に近い・未満の %d 辺は K* − 量子化の 2 倍）" % (TH["P13_row_edge_m"], P["n_edge_relaxed"]),
                                 vok("5b"),
                                 dict(at=P["edge_min"][1], worst_margin_m=fnum(P["edge_margin_min"][0], 5), worst_margin_at=P["edge_margin_min"][1], **vinfo("5b")))
    qn = "（判定は辺の長さから量子化の 2 倍を差し引いた比）"
    items["(5c) 辺の長さの K* に対する比（行の方向）"] = ([fnum(P["stretch_row"][0], 3), fnum(P["stretch_row"][1], 3)], "%.2f〜%.0f%s" % (TH["P13_stretch_lo"], TH["P13_stretch_hi"], qn),
                                         vok("5c"), vinfo("5c"))
    items["(5d) 辺の長さの K* に対する比（行の間、縦と斜め）"] = ([fnum(P["stretch_cross"][0], 3), fnum(P["stretch_cross"][1], 3)], "%.2f〜%.0f%s" % (TH["P13_stretch_lo"], TH["P13_stretch_hi"], qn),
                                        vok("5d"), vinfo("5d"))
    items["(5e) rim と管の天井の継ぎ目の比"] = ([fnum(P["seam"][0], 3), fnum(P["seam"][1], 3)], "%.2f〜%.0f%s" % (TH["P13_seam_lo"], TH["P13_seam_hi"], qn),
                                     vok("5e"), vinfo("5e"))
    si_ = P["si"]
    items["(5f) 自己交差（巻きの行の断面と、隣り合う巻きの行の間の中央の面）"] = (
        si_["row_hits"] + si_["mid_hits"], "0", si_["row_hits"] + si_["mid_hits"] == 0,
        dict(frames=si_["frames"], frames_ja="−2.5 s より前は 0.5 s ごと、最後の 2.5 s は 30 Hz", row=si_["row_hits"], mid=si_["mid_hits"],
             both_segments_ge_5mm=si_["resolvable_hits"], tau_range=si_["tau_range"], examples=si_["examples"]))
    fl = P["flips"]
    items["(5g) 面の反転（30 Hz、向きの決まった最後のコマと比べる）"] = (
        fl["n_resolvable"] + fl["n_region"], "0", fl["n_resolvable"] + fl["n_region"] == 0,
        dict(resolvable_whole_mesh=fl["n_resolvable"], lip_tube_region=fl["n_region"], all_triangles_incl_slivers=fl["n_all"],
             first=fl["at"], first_region=fl["at_region"], tau_range=V_.get("5g", {}).get("tau_range"),
             note_ja="全体は K* の最小の高さ ≥ 5 mm の三角形だけ（残り約 15% は細長く、16 ビットの量子化だけで裏返る）。唇・管は全部"))
    items["(6) 法線が有限（唇・管の頂点の 1 環の面積の最小 > 0）_m2"] = (
        P["tri_min_all"][0], "> 0", P["tri_min_all"][0] > 1e-10,
        dict(at=P["tri_min_all"][1], zero_area_faces_whole_mesh_at_tstar=P["zero_area_all_tstar"], **vinfo("6"),
             note_ja="全体の面積 0 の面の数は t* の記録（K* の細長い三角形が量子化でつぶれる）"))
    det = {k: dict(value=(fnum(v[0], 6) if not isinstance(v[0], list) else v[0]), threshold=v[1], pass_=bool(v[2]), at=v[3],
                   origin_ja=("Step_30" if k[:3] in ("(1)", "(2)", "(3)", "(4)") else "設計26 で追加")) for k, v in items.items()}
    det["行が c 一定の面から外れた最大_m"] = fnum(M["cdev"].max(), 5)
    nfail = sum(1 for v in items.values() if not v[2])
    step30_ok = all(v[2] for k, v in items.items() if k[:3] in ("(1)", "(2)", "(3)", "(4)"))
    det["Step_30 の項目 (1)〜(4) がすべて合格"] = bool(step30_ok)
    out["P13"] = gate("連続性の検査一式（Step_30 ＋ 設計26 の変更）", "%d 項目中 %d 項目が不合格" % (len(items), nfail), "全項目", nfail == 0, det)

    # ---- P14
    if sibling is not None:
        out["P14"] = gate("美術の誘導を分ける（入れた版と切った版の両方、切った版の t* の差）", sibling.get("value"),
                          "両方の版がある（差は記録）", sibling.get("ok"), sibling)
    else:
        out["P14"] = gate("美術の誘導を分ける（入れた版と切った版の両方、切った版の t* の差）", None, "両方の版がある（差は記録）", False,
                          dict(note_ja="隣の版（art_on / art_off）の包みが見つからない"))

    # ---- P15
    det = {}
    ok = True
    tab = cond["stage_tau"] if cond else None
    for r in (mr, pr):
        res = stage_times(ks, S, taus, r, Hn[:, r], tw_T, finalw, M, rpos, ca_v)
        want = {k: tab[k] + (cond["main_lag"] if r == mr else 0.0) for k in "abcd"} if tab else None
        tt = [res["tau"][k] for k in "abcd"]
        order = all(v is not None for v in tt) and all(tt[i] < tt[i + 1] for i in range(3))
        within = want is not None and all(res["tau"][k] is not None and abs(res["tau"][k] - want[k]) <= TH["P15_tol_s"] for k in "abcd")
        wok = res["white_ok"]
        ok &= order and within and wok
        det[named[r]] = dict(row=int(r), tau={k: fnum(v, 3) for k, v in res["tau"].items()}, table_tau={k: fnum(v, 3) for k, v in (want or {}).items()},
                             order_ok=bool(order), within_tol=bool(within), first_white_tau=fnum(res["first_white"], 3), white_ok=bool(wok),
                             first_white_at_tip=res["first_white_tip"])
    det["判定の読み方_ja"] = ("a：H/Hf 0.5〜0.7・θc ≥ 140°・φ ≤ 35°・Lo ≤ 0.02H・行に白なし。b：H/Hf 0.65〜0.8・φ ≥ 45°・θc ≤ 130°・Lo ≤ 0.02H・|φ − ψ| ≥ 5°（前後が非対称）・白なし。"
                          "c：H/Hf 0.8〜0.9・頂の下 0.1〜0.2H の前面 φ ≥ 90°・θc 105〜135°（≈120°）・Lo < 0.05H。d：Lo ≥ 0.1H・H/Hf ≥ 0.9・dH/dτ > 0・唇先の水平の速さ ≥ 頂の速さ。"
                          "各段階は全部を初めて満たした時刻。Hf はその行の t* の頂。白：行の最初の白が τ_c − 1/30 s 以後 τ_d 以前、唇先の 0.1H 以内")
    out["P15"] = gate("a→b→c→d の順（主断面と峰で最も高い巻きの行、各 ±0.3 s、最初の白は c）", None, "順・±%.1f s・白" % TH["P15_tol_s"], bool(ok), det)
    out["P15"]["value"] = {named[r]: det[named[r]]["tau"] for r in (mr, pr)}

    # ---- P16
    out["P16"] = p16(ks, pk, M, tw, onset, ramp_end, rpos)

    # ---- 原画の関門の前提
    err = np.linalg.norm(M["X0"] - ks.X, axis=-1)
    i = np.unravel_index(int(err.argmax()), err.shape)
    lim = pk.q_max + 1e-4
    is_off = "off" in pk.version.lower()
    out["Painting"] = gate("原画の関門の前提（τ = 0 の位置 = K*、量子化の内）", fnum(float(err.max()), 5),
                           "≤ %.5f m（量子化の最大 %.5f m + 0.1 mm）" % (lim, pk.q_max), (bool(err.max() <= lim) if not is_off else None),
                           dict(max_at=dict(row=int(i[0]), col=int(i[1])), rms_m=fnum(float(np.sqrt((err ** 2).mean())), 6),
                                per_axis_max_m=[fnum(float(np.abs(M["X0"][..., k] - ks.X[..., k]).max()), 6) for k in range(3)],
                                note_ja=("切った版（art_off）の t* は K* ではない（P14 で差を記録）" if is_off else "")))
    return out, onset


def first_white_at_tip(ks, T, finalw):
    """最初の白（最小の T_white から 1/60 s 以内の頂点）が、巻きの行の唇先の弧長 0.1H 以内にあるか。"""
    if not finalw.any():
        return False, dict(note_ja="白の頂点がない")
    Tm = np.where(finalw, T, np.inf)
    t0 = float(Tm.min())
    rr, cc = np.nonzero(Tm <= t0 + 1.0 / HZ)
    ok = []
    for r, c in zip(rr, cc):
        if not ks.is_curled[r]:
            ok.append(False)
            continue
        jt = ks.tip_col[r]
        ok.append(abs(ks.s_arc[r, c] - ks.s_arc[r, jt]) <= TH["P9_tip_arc_over_H"] * ks.Hrow[r])
    ok = np.array(ok)
    return bool(ok.all()), dict(tau=fnum(t0, 3), vertices=int(len(rr)), at_tip=int(ok.sum()),
                                example=dict(row=int(rr[0]), col=int(cc[0]), c_m=fnum(ks.c[rr[0]], 2),
                                             tip_col=int(ks.tip_col[rr[0]]) if ks.is_curled[rr[0]] else None))


def stage_times(ks, S, taus, r, Hn, T, finalw, M, rpos, ca_v):
    st = STAGE
    H = S["H"][:, r]
    phi = S["phi"][:, r]
    phib = S["phib"][:, r]
    psi = S["psi"][:, r]
    th = S["theta"][:, r]
    Lo = S["Lo"][:, r] / np.maximum(H, 1e-9)
    Lo0 = np.nan_to_num(Lo, nan=0.0)
    rowT = np.where(finalw[r], T[r], np.inf)
    white_n = (rowT[None, :] <= taus[:, None]).sum(1)
    dH = np.gradient(H, taus)
    u_tip = np.interp(taus, M["kin"]["tau"], M["kin"]["va"][:, rpos[r]]) if r in rpos else np.full(len(taus), np.nan)
    B = u_tip / np.maximum(ca_v[:, r], 1e-6)
    thf = np.nan_to_num(th, nan=180.0)
    a = st["a"]
    ma = (Hn >= a["H"][0]) & (Hn <= a["H"][1]) & (thf >= a["theta_min"]) & (np.nan_to_num(phi, nan=0.0) <= a["phi_max"]) & (Lo0 <= a["Lo_max"]) & (white_n == 0)
    b = st["b"]
    mb = ((Hn >= b["H"][0]) & (Hn <= b["H"][1]) & (np.nan_to_num(phi, nan=0.0) >= b["phi_min"]) & (np.nan_to_num(th, nan=999) <= b["theta_max"])
          & (Lo0 <= b["Lo_max"]) & (np.abs(np.nan_to_num(phi, nan=0.0) - np.nan_to_num(psi, nan=0.0)) >= b["asym_deg"]) & (white_n == 0))
    c = st["c"]
    mc = ((Hn >= c["H"][0]) & (Hn <= c["H"][1]) & (np.nan_to_num(phib, nan=0.0) >= c["phi_band_min"])
          & (np.nan_to_num(th, nan=0) >= c["theta"][0]) & (np.nan_to_num(th, nan=999) <= c["theta"][1]) & (Lo0 < c["Lo_max"]))
    d = st["d"]
    md = (Lo0 >= d["Lo_min"]) & (Hn >= d["H_min"]) & (dH > 0) & (np.nan_to_num(B, nan=0.0) >= d["B_min"])
    res = {k: first_true(m_, taus)[0] for k, m_ in zip("abcd", (ma, mb, mc, md))}
    fw = float(rowT.min()) if np.isfinite(rowT.min()) else None
    wok = False
    tip_ok = None
    if fw is not None and res["c"] is not None:
        hi = res["d"] if res["d"] is not None else 0.0
        wok = (fw >= res["c"] - 1.0 / HZ_OUT - 1e-9) and (fw <= hi + 1e-9)
        cmin = int(np.argmin(rowT))
        tip_ok = bool(ks.is_curled[r] and abs(ks.s_arc[r, cmin] - ks.s_arc[r, ks.tip_col[r]]) <= TH["P9_tip_arc_over_H"] * ks.Hrow[r])
        wok = wok and tip_ok
    return dict(tau=res, first_white=fw, white_ok=bool(wok), first_white_tip=tip_ok)


def p16(ks, pk, M, tw, onset, ramp_end, rpos):
    """体験の時刻の唇先の見かけの縦の加速度 A(t) = d²y(τ(t))/dt²（y は Hermite の値そのもの、中心の二階差分 h = 1/60 s）。
    窓：各巻きの行の打ち出しの補間の終わりから、最後の止めるための区間（≤0.5 s）の前まで。"""
    t = tw["t"]
    tau = tw["tau"]
    dt = 1.0 / 240
    tg = np.arange(0, 12.5 + 1e-9, dt)
    tg_tau = np.interp(tg, t, tau)
    # 止めるための区間：t* の直前で r = dτ/dt が減り続けている区間（表の丸めの雑音を 1/60 s の箱でならす）
    rr = np.gradient(tg_tau, tg)
    box = np.ones(4) / 4
    rr_s = np.convolve(rr, box, mode="same")
    rd = np.gradient(rr_s, tg)
    kstar = int(np.nonzero(tg_tau >= -1e-9)[0][0])
    t_star = float(tg[kstar])
    k = kstar
    while k > 0 and rr[k] < 0.02:          # 止まりきる直前（r ≈ 0、傾きも 0 に近い）を飛ばす
        k -= 1
    while k > 0 and rd[k] < -0.01:         # r が減り続けている間さかのぼる
        k -= 1
    t_stop = float(tg[k])
    stop_len = t_star - t_stop
    t_end = t_stop if stop_len <= TH["P16_stop_ramp_max_s"] + 1e-9 else t_star - TH["P16_stop_ramp_max_s"]
    kin = M["kin"]
    ktau = kin["tau"]
    worst = (-np.inf, None, None)
    n_fail = 0
    n_eval = 0
    detail_rows = {}
    tq = np.clip(tg_tau, pk.knots[0], 0.0)
    Yall = pk.sub(tq, kin["vtip"], 0)[..., 1]            # (nt, 巻きの行)
    for r in kin["rows"]:
        r = int(r)
        te = ramp_end(r)
        if te is None:
            continue
        yy = Yall[:, rpos[r]]
        A = np.full_like(yy, np.nan)
        s = int(round(240 / HZ_OUT))        # h = 1/30 s（出力のコマの間隔。16 ビットの量子化の雑音を抑える）。窓の端から h だけ内側で測る
        A[s:-s] = (yy[2 * s:] - 2 * yy[s:-s] + yy[:-2 * s]) / (s * dt) ** 2
        m = (tg_tau >= te) & (tg <= t_end - s * dt - 1e-9) & np.isfinite(A) & (tg_tau >= pk.knots[0] + s * dt)
        if not m.any():
            continue
        n_eval += 1
        i = int(np.nonzero(m)[0][np.argmax(A[m])])
        if A[i] > TH["P16_tol_mps2"]:
            n_fail += 1
        if A[i] > worst[0]:
            worst = (float(A[i]), r, float(tg[i]))
        if r in (ks.main_row, ks.peak_row):
            detail_rows[int(r)] = dict(window_t=[fnum(float(np.interp(te, tg_tau, tg)), 3), fnum(t_end, 3)], max_A_mps2=fnum(A[i], 3), at_t=fnum(tg[i], 3))
    # 主断面の画面での落下（唇先の頂点 → t*）
    r = ks.main_row
    y_ = kin["y"][:, rpos[r]]
    st_ = onset[r] if np.isfinite(onset[r]) else ktau[0]
    mm = ktau >= st_
    kap = int(np.nonzero(mm)[0][0] + np.argmax(y_[mm]))
    tau_ap = float(ktau[kap])
    t_ap = float(np.interp(tau_ap, tg_tau, tg)) if tau_ap > tg_tau[0] else 0.0
    ok = n_eval > 0 and n_fail == 0
    return gate("体験の時刻で唇がブレーキをかけない（巻きの行の唇先の見かけの縦の加速度）", fnum(worst[0], 3),
                "≤ 0（許容 %.2f m/s²）、打ち出しの補間の後から止めるための区間の前まで" % TH["P16_tol_mps2"], bool(ok),
                dict(rows_evaluated=n_eval, rows_failing=n_fail, worst_row=worst[1], worst_t=fnum(worst[2], 3),
                     stop_ramp_t=[fnum(t_stop, 3), fnum(t_star, 3)], window_end_t=fnum(t_end, 3), rows=detail_rows,
                     main_tip_apex_tau=fnum(tau_ap, 3), main_fall_on_screen_s=fnum(t_star - t_ap, 3), main_fall_physical_s=fnum(-tau_ap, 3)))


def calm_painting_on(pk):
    """包みの ds_sea_calm_painting が入っているか（keypose.json の sea_model.calm か、無ければ版の名前 art_on）。"""
    sm = pk.meta.get("sea_model") if isinstance(pk.meta, dict) else None
    if isinstance(sm, dict) and isinstance(sm.get("calm"), dict) and "ds_sea_calm_painting" in sm["calm"]:
        return bool(sm["calm"]["ds_sea_calm_painting"])
    return pk.version == "art_on"


def sibling_p14(pk, ks):
    """隣の版（art_on ↔ art_off）の包みを探し、切った版の t* の K* との差を記録する。"""
    base = os.path.basename(pk.dir.rstrip("/\\"))
    other = {"art_on": "art_off", "art_off": "art_on"}.get(base)
    if other is None:
        return None
    od = os.path.join(os.path.dirname(pk.dir), other)
    jp = os.path.join(od, "ds27_keypose.json")
    if not os.path.isfile(jp):
        return dict(ok=False, value=None, note_ja="%s がない" % other)
    off = pk if base == "art_off" else Package(od, ks)
    X0 = off.world(0.0)
    d = np.linalg.norm(X0 - ks.X, axis=-1)
    i = np.unravel_index(int(d.argmax()), d.shape)
    A, Y, _ = ks.section(X0)
    mr = ks.main_row
    return dict(ok=True, value=fnum(float(np.sqrt((d ** 2).mean())), 4),
                artoff_tstar_vs_kstar=dict(rms_m=fnum(float(np.sqrt((d ** 2).mean())), 4), max_m=fnum(float(d.max()), 4),
                                           max_at=dict(row=int(i[0]), col=int(i[1]), c_m=fnum(ks.c[i[0]], 2)),
                                           main_row_rms_m=fnum(float(np.sqrt((d[mr] ** 2).mean())), 4)),
                other_dir=rel(od))


def load_conditions():
    if not os.path.isfile(COND_JSON):
        return None, None
    sha = sha256_file(COND_JSON)
    J = json.load(open(COND_JSON, encoding="utf-8"))
    cal = J["calibration"]
    st = cal["stage_tau_peak_row_s"]
    cond = dict(stage_tau={k: float(st[k]) for k in "abcd"}, main_lag=float(st["main_row_lag_s"]),
                tau0=float(cal["jet_onset_peak_row_tau_s"]["value"]), peel=float(cal["peel_speed_mps"]["value"]),
                floor=float(cal["jet_onset_floor_s"]["value"]))
    return cond, dict(path=rel(COND_JSON), sha256=sha, matches_record=(sha == SHA256["ds26_conditions.json"]))


# ---------------------------------------------------------------- 出力
def write_md(path, rep):
    L = []
    L.append("# 設計27 の関門の検査（ds27_gates.py）")
    L.append("")
    L.append("- 包み：`%s`（版 %s、%d 層、τ %s〜0 s）" % (rep["package"]["dir"], rep["package"]["version"], rep["package"]["layers"], rep["package"]["tau0"]))
    L.append("- 時間曲線：`%s`" % rep["timewarp"]["path"])
    L.append("- K\\*：主断面 行 %d（c = 0 m）、峰で最も高い巻きの行 行 %d（c = %s m）、巻きの行 %d 行" % (
        rep["kstar"]["main_row"], rep["kstar"]["peak_row"], rep["kstar"]["peak_row_c_m"], rep["kstar"]["curled_rows"]))
    L.append("- 結果：合格 %d、不合格 %d、判定なし %d（所要 %.0f s）" % (rep["summary"]["n_pass"], rep["summary"]["n_fail"], rep["summary"]["n_none"], rep["runtime_s"]))
    bad = [c for c in rep["package"]["interface"] + rep["timewarp"]["checks"] if not c["ok"]]
    if bad:
        L.append("- **書式の不一致**：" + "、".join(c["item_ja"] for c in bad))
    L.append("")
    L.append("| 関門 | 内容 | 値 | しきい値 | 判定 |")
    L.append("| --- | --- | --- | --- | --- |")
    for k, g in rep["gates"].items():
        v = g["value"]
        if isinstance(v, dict):
            v = "；".join("%s %s" % (kk, " ".join("%s %s" % (a, b) for a, b in vv.items()) if isinstance(vv, dict) else vv) for kk, vv in v.items())
        ok = g["pass"]
        verdict = "合格" if ok is True else ("不合格" if ok is False else "判定なし")
        if g.get("scope_ja"):
            verdict += "（%s）" % g["scope_ja"]
        L.append("| %s | %s | %s | %s | %s |" % (k, g["name_ja"], v, g["threshold"], verdict))
    L.append("")
    L.append("P13 の内訳：")
    L.append("")
    L.append("| 項目 | 由来 | 値 | しきい値 | 判定 |")
    L.append("| --- | --- | --- | --- | --- |")
    for k, v in rep["gates"]["P13"]["detail"].items():
        if isinstance(v, dict) and "threshold" in v:
            L.append("| %s | %s | %s | %s | %s |" % (k, v.get("origin_ja", ""), v["value"], v["threshold"], "合格" if v["pass"] else "不合格"))
    L.append("")
    L.append("- 値の詳細（行・時刻・内訳）は同じ名前の JSON にある。τ は物理の時刻（t* = 0）、t は体験の時刻（t* = 12.0 s）。")
    L.append("")
    L.append("検査器の読み方（設計26 の記録が数で決めていない所）：")
    L.append("")
    for x in rep.get("readings_ja", []):
        L.append("- " + x)
    L.append("")
    L.append("- 測る範囲は τ ≤ 0（Q11）。P1〜P15 は物理の時刻で、P16 は時間曲線を通した体験の時刻で測る。")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def run(package, timewarp, out, sea_path=None, log=print):
    t0 = time.time()
    ks = KStar()
    pk = Package(package, ks)
    tw = load_timewarp(timewarp)
    cond, cond_src = load_conditions()
    sea = None
    if sea_path:
        z = np.load(sea_path)
        sea = dict(tau=np.asarray(z["tau"], float), a=np.asarray(z["a"], float), eta=np.asarray(z["eta"], float))
    log("[ds27_gates] 包み %s（%d 層）、測定を始める" % (rel(pk.dir), pk.L))
    M = measure(ks, pk, sea=sea, log=log)
    sib = sibling_p14(pk, ks)
    gates, onset = evaluate(ks, pk, tw, M, sibling=sib, sea_used=sea is not None, cond=cond)
    # 時間曲線が設計26 の参照と合うか（記録）
    ref = {}
    for kind in ("default", "alt"):
        rt, rtau = reference_timewarp(kind)
        v = np.interp(rt, tw["t"], tw["tau"])
        ref[kind] = fnum(float(np.abs(v - rtau).max()), 5)
    for g in gates.values():
        g["pass"] = g.pop("pass_")
        if isinstance(g.get("detail"), dict):
            for v in g["detail"].values():
                if isinstance(v, dict) and "pass_" in v:
                    v["pass"] = v.pop("pass_")
    n_pass = sum(1 for g in gates.values() if g["pass"] is True)
    n_fail = sum(1 for g in gates.values() if g["pass"] is False)
    rep = dict(
        schema="GreatWave.DS27.gates/1",
        number="設計27",
        tool=rel(os.path.abspath(__file__)),
        evidence_kind_ja="numpy の測定（包みを Hermite で補間して読むだけ）。Unity の描画・HMD の結果ではない",
        package=dict(dir=rel(pk.dir), version=pk.version, layers=pk.L, tau0=fnum(pk.knots[0], 4), pos_sha256=pk.pos_sha, twhite_sha256=pk.twhite_sha,
                     quantization_max_err_m=fnum(pk.q_max, 6), interface=pk.iface),
        timewarp=dict(path=rel(tw["path"]), sha256=tw["sha256"], checks=tw["checks"], max_abs_diff_to_reference_tau_s=ref,
                      reference_ja="設計26 §3.2 の既定（τ_apex −1.432 s、r0 0.5、減速 1 s、止める 0.4 s）と代案（実時間＋瞬間の停止）。記録のみ"),
        kstar=dict(sha256=ks.sha, main_row=ks.main_row, peak_row=int(ks.peak_row), peak_row_c_m=fnum(ks.c[ks.peak_row], 2), curled_rows=int(len(ks.curled_idx)),
                   H_star_m=fnum(ks.H_star, 3)),
        conditions=cond_src,
        sea=(rel(sea_path) if sea_path else None),
        readings_ja=READINGS_JA,
        thresholds=TH,
        onset_tau_by_row={int(r): fnum(onset[r], 3) for r in ks.curled_idx},
        gates=gates,
        summary=dict(n_pass=n_pass, n_fail=n_fail, n_none=len(gates) - n_pass - n_fail,
                     failed=[k for k, g in gates.items() if g["pass"] is False]),
        runtime_s=round(time.time() - t0, 1),
    )
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=lambda o: fnum(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    write_md(os.path.splitext(out)[0] + ".md", rep)
    log("[ds27_gates] 合格 %d・不合格 %d（%s）、%.0f s → %s" % (n_pass, n_fail, ",".join(rep["summary"]["failed"]), rep["runtime_s"], out))
    return rep, M, ks, pk


def main():
    ap = argparse.ArgumentParser(description="設計27 の関門 P1〜P16 と原画の関門の前提を DS27 の keypose の包みで測る")
    ap.add_argument("--package", required=True)
    ap.add_argument("--timewarp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sea", default=None)
    a = ap.parse_args()
    run(a.package, a.timewarp, a.out, a.sea)


if __name__ == "__main__":
    main()
