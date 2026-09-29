# -*- coding: utf-8 -*-
"""設計28修正01（Q13）：唇の伸び出しと頂の上昇の重なりを測る、動きの生成器から独立の検査器。

Q13（利用者、2026-09-27）：原画の手前の爪の形の大きな部分（唇と爪）が、波が最も高くなった後に伸び出すのがおかしい。
唇（爪を含む）は、平らな海から最高点へ育つ過程の後半に、もう伸び始めているべき。
この検査器は、DS27 の keypose の包みと時間曲線の表だけから、行ごとに次を測る（生成器のコードは読まない）。

  H(τ)      本体の頂の高さ（巻きの行は K* の頂の列 jt より後ろの列の最高点。放出した唇は頂に数えない）
  Lo(τ)     張り出し（設計26 §3.1 の定義 A：前の部分で 0.3H を最後に下へ横切る点から、0.3H より上の前の部分の a の最大まで）
  伸び出しの始まり τ_ext  Lo ≥ 0.05H が t* まで続く最初の時刻（初めて満たした時刻も記録）
  H/H* は行の t*（包みの τ = 0）の頂 Hf で割る（設計26 E1・ds27_gates の P15 と同じ割り方）
  爪・鉤の細部の振幅 C(τ)  K* の唇の断面の細部（折れ線 − 列の方向のガウスでならした線、の法線の向きの成分 dn_K）へ、
            今の唇の細部 dn(τ) を射影した係数 Σ dn·dn_K / Σ dn_K²（t* で 1）。3 つの尺度：
              claw_steps：上面（列 jt..jtip）、σ 8 列（K* で約 1.1 m。上面の段＝爪の背の並び。原画の爪群の段）
              fine_upper：上面、σ 2 列（`ds_claws` がならす尺度）
              hooks     ：下面（列 jtip..rim）、σ 2 列（唇先の下の鉤。下面が 10 列以上の行だけ）
            ほかに振幅の比 D(τ) = RMS(dn)/RMS(dn_K)（模様によらない細部の量）
  唇の伸び出しの進み P(τ) = (Lo − Lo(τ_ext)) / (Lo(0) − Lo(τ_ext))
  体験の時刻（画面）  既定と代案の時間曲線の表で τ → t。重なり＝画面の時間で「頂が上がり（dH/dt ≥ v）かつ唇が伸びる
            （Lo ≥ 0.05H かつ dLo/dt ≥ v）」の割合

使い方（リポジトリの根で）:
  py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_overlap.py --package Unity/Build/Design/28/art_on \\
      --tw-default Tools/GWWaveGen/ds27/timewarp_default.json --tw-alt Tools/GWWaveGen/ds27/timewarp_alt.json \\
      --out Unity/Build/Design/28R01/overlap/ds28_art_on.json [--label 設計28 既定（art_on）] [--evidence <小さい要約.json>]
  出力：<out>（行ごとの要約・主断面と峰の行の時系列・判定）と同じ名前の .md（日本語）。--evidence があれば時系列を除いた要約も書く。
包み・K* の読み込み（バイトの約束・Hermite の補間・SHA-256 の照合）は設計27 の検査器 ds27_gates の KStar・Package を使う
（設計27 の約束そのもの）。測る量と判定はこのファイルで書いた。numpy だけ。出力は同じ入力なら同じ（実行時間を除く）。
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
import ds27_gates as g27  # noqa: E402  包みと K* の読み込みだけ

HZ = 60                      # 物理の時刻 τ の刻み
CLAW_FROM_TAU = -6.0         # 爪・鉤の細部を測り始める τ（これより前は唇がない。0 として扱う）
MAIN_ROW, PEAK_ROW = 159, 192

# 目標（進行役の Q13 の T1・T2・T5。変えるときは記録を先に直す）と、この検査器の読み方の値
TH = dict(
    ext_Lo_over_H=0.05,          # 伸び出しの始まり：Lo ≥ 0.05H
    ext_H_max=0.75,              # T1：始まりの H/H* ≤ 0.75
    gain_min=0.25,               # T1：H(t*) − H(始まり) ≥ 0.25H*
    mono_tol_m=0.05,             # T1：始まりから t* まで H が減らない（許容 0.05 m）
    plateau_H=0.95,              # T1：H ≥ 0.95H* が
    plateau_max_s=0.5,           #     t* の前に 0.5 s（物理）を超えない
    hmax_window_s=0.2,           # T1：最高点は t* から 0.2 s 以内
    claw_mono_tol=0.05,          # T2：爪の係数 C が始まりから減らない（許容 K* の 5%）
    claw_lag_max_s=0.3,          # T2：C が 0.5 に届く時刻が、唇の進み P が 0.5 に届く時刻より 0.3 s（物理）を超えて遅れない
    claw_start_max=0.2,          # T2：始まりの C ≤ 0.2（始まりの時にもう爪が出来上がっていない＝唇と一緒に育つ）
    claw_follow_max=0.25,        # T2：始まりから t* まで |C − P| ≤ 0.25（爪が唇の進みについて育つ）
    grow_rel_per_s=0.02,         # 唇が伸びている（物理）：dLo/dτ ≥ 0.02 Hf/s（主断面で約 0.42 m/s）。伸びの始まり・停滞に使う
    stall_max_s=0.3,             # 厳しい読み（記録）：始まりの後に唇が伸びない時間（物理）≤ 0.3 s
    rate_rel_per_s=0.03,         # 重なり（主）：画面の速さ ≥ 0.03 Hf/s（主断面で約 0.62 m/s）を「見て上がる・伸びる」とする
    rate_strict_rel_per_s=0.05,  # 重なり（厳しい）：≥ 0.05 Hf/s（主断面で約 1.04 m/s）
    rate_any_mps=0.1,            # 参考：≥ 0.1 m/s（ほぼ止まっていない）
    warp_same_regime=0.02,       # T5：伸び出しの間の速さ r が、止めるための区間の前の一定の値の ±2% 以内
)
CLAW_SCALES = [
    dict(key="claw_steps", seg="upper", sigma=8.0, min_cols=40, ja="上面の段（爪の背の並び、σ 8 列）"),
    dict(key="fine_upper", seg="upper", sigma=2.0, min_cols=20, ja="上面の細かい鉤（σ 2 列、ds_claws の尺度）"),
    dict(key="hooks", seg="under", sigma=2.0, min_cols=10, ja="唇先の下の鉤（下面、σ 2 列）"),
]
PRIMARY_CLAW = "claw_steps"

READINGS_JA = [
    "行：K* の巻きの行（ds27_gates.KStar の規則、133 行）。主断面は行 159、峰で最も高い巻きの行は行 192。頂は列 ≤ K* の頂の列 jt の最高点（地面の y）。",
    "Hf：その行の包みの τ = 0（t*）の頂。H/H* はすべて H/Hf（設計26 E1・ds27_gates P15 と同じ割り方）。",
    "Lo：設計26 §3.1 の定義 A。前の部分（列 cj..j_E、j_E は K* の前の足の列）で 0.3H を最後に下へ横切る点の a から、前の部分で y > 0.3H の点の a の最大まで。H はその時刻の頂。",
    "伸び出しの始まり τ_ext（T1 の定義）：Lo ≥ 0.05H が t* まで途切れずに続く最初の時刻（物理の時刻、60 Hz）。初めて満たした時刻 τ_ext_first も記録する。",
    "唇の伸びの始まり τ_grow（厳しい読み、記録）：dLo/dτ ≥ 0.02 Hf/s が t* の直前まで途切れずに続く最初の時刻。τ_ext の後に唇が伸びない時間の最長（停滞）と、Lo の戻り（張り出しが減る量）も記録する。設計28 のように、噴流の始まりに小さな張り出しの段ができて、その後しばらく伸びない動きを見分けるため。",
    "H の単調：始まりから t* までの最大の戻り（それまでの最大 − 今）。H/Hf ≥ 0.5 に初めて届いてから t* までの戻りも記録する。台：t* の前で H ≥ 0.95Hf の時間の合計（物理と画面）。最高点：τ ≤ 0 の H の最大の時刻。",
    "高さで見た重なり（時間曲線によらない）：rise_share_after_ext＝後半の上昇（0.5Hf → Hf）のうち伸び出しの始まりの後の割合 (1 − H_ext/Hf)/0.5（T1 の増え 0.25 は 0.5 に当たる）。rise_share_while_lip_grows＝ 0.5Hf の後の H の増えのうち、唇が伸びている（Lo ≥ 0.05H かつ dLo/dτ ≥ 0.02 Hf/s）間の割合。P_at_H95＝頂が 0.95Hf に届いた時の唇の進み P（伸び出しのうち台の前に済んだ割合）。",
    "c・d の目安（段階の判定そのものではない。P15 は ds27_gates で測る）：前面が初めて鉛直（頂から前の足までの下りの線分で、中点が 0.15〜0.97H のものの最大の角 ≥ 90°）の時刻と、Lo ≥ 0.1H が t* まで続く最初の時刻。それぞれの H/Hf と dH/dτ。",
    "爪・鉤の細部：上面＝列 jt..jtip、下面＝列 jtip..rim（K* の列。包みの列は K* と同じ）。区間の断面の折れ線 (a, y) を列の方向にガウス（σ 列、両端は奇の折り返し）でならし、ならした線の法線の向きの差 dn を取る（両端の 2 列は除く）。C = Σ dn·dn_K / Σ dn_K²（K* の模様の射影、t* で 1）、D = RMS(dn)/RMS(dn_K)。K* の RMS(dn_K) < 1 cm の行は判定から除く。τ < −6 s は 0。判定には claw_steps（上面の段、原画の爪群の段に当たる）だけを使い、ほかの 2 つは記録。",
    "唇の進み P：(Lo − Lo(τ_ext)) / (Lo(0) − Lo(τ_ext))。T2：始まりから t* まで C の戻り ≤ 0.05、始まりの C ≤ 0.2、|C − P| ≤ 0.25、C が 0.5 に届く（以後 0.5 未満へ戻らない）時刻 − P が 0.5 に届く時刻 ≤ 0.3 s（物理）。最後の 1 s（物理）の C の増えの割合と、P の割合も記録する。",
    "体験の時刻：時間曲線の表（t, τ）で、τ に初めて届く t（線形補間）。表の始まりより前の τ は『画面の前』。速さ r = dτ/dt。止めるための区間の始まり t_fs＝ t* の前で r が一定（|dr/dt| < 0.02 /s）だった最後の時刻。一定の遅さに入った時刻 t_slow＝ t_fs まで r ≤ 1.02 r(t_fs) が続く最初の時刻。T5 の読み：t_slow ≤ t_ext（伸び出しの前に一定の遅さへ入る）。",
    "重なり（画面）：t ∈ [0, 12) の各コマ（表の 240 Hz）で、上がる＝H/Hf ≥ 0.5 の後で dH/dt ≥ v、伸びる＝Lo ≥ 0.05H かつ dLo/dt ≥ v（dH/dt = dH/dτ·r、dH/dτ は物理の 60 Hz の中心差分 ±2 刻み）。v は 0.03 Hf/s（主、見て分かる上昇）・0.05 Hf/s（厳しい）・0.1 m/s（参考）。割合：伸びる時間のうち上がる時間（frac_of_ext）、上がる時間のうち伸びる時間（frac_of_rise）、両方の和に対する重なり（jaccard）、唇の伸び（dLo の和）のうち頂が上がっている間の割合（lip_growth_share_while_rising）。ext_share_before_H95＝画面の伸び出しの時間（t_ext → t*）のうち頂が 0.95Hf に届く前の割合。",
]


# ---------------------------------------------------------------- 小道具
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


def clean(o, nd=4):
    if isinstance(o, dict):
        return {k: clean(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v, nd) for v in o]
    if isinstance(o, np.ndarray):
        return [clean(v, nd) for v in o.tolist()]
    if isinstance(o, (float, int, np.floating, np.integer, np.bool_, bool)) or o is None:
        return fnum(o, nd)
    return o


def first_sustained(mask):
    """mask（時刻の並び）が最後まで True で続く最初の添字。最後が False なら None。"""
    if len(mask) == 0 or not mask[-1]:
        return None
    bad = np.nonzero(~mask)[0]
    return int(bad[-1] + 1) if len(bad) else 0


def first_true(mask):
    idx = np.nonzero(mask)[0]
    return int(idx[0]) if len(idx) else None


def drawdown(x):
    x = np.asarray(x, float)
    if len(x) == 0:
        return 0.0
    m = np.maximum.accumulate(np.nan_to_num(x, nan=-np.inf))
    return float(np.nanmax(m - x))


def deriv(y, dt, k=2):
    """中心差分（±k 刻み。端は片側）。"""
    y = np.asarray(y, float)
    n = len(y)
    d = np.empty(n)
    for i in range(n):
        a, b = max(i - k, 0), min(i + k, n - 1)
        d[i] = (y[b] - y[a]) / ((b - a) * dt) if b > a else 0.0
    return d


# ---------------------------------------------------------------- 時間曲線
class Warp:
    def __init__(self, path, name):
        J = json.load(open(path, encoding="utf-8"))
        self.path, self.name = path, name
        self.sha = sha256_file(path)
        self.id = J.get("id", name)
        self.t = np.array(J["t"], float)
        self.tau = np.array(J["tau"], float)
        self.t_star = float(J.get("t_star_s", 12.0))
        self.r = np.gradient(self.tau, self.t)
        # 狭義単調の部分（τ → t の逆引き）
        keep = np.concatenate([[True], np.diff(self.tau) > 1e-12])
        self.tau_u, self.t_u = self.tau[keep], self.t[keep]
        # 止めるための区間の始まり t_fs と、一定の遅さに入った時刻 t_slow
        dr = np.gradient(self.r, self.t)
        m = (self.t < self.t_star - 1e-3) & (np.abs(dr) < 0.02) & (self.r > 0.05)
        idx = np.nonzero(m)[0]
        i_fs = int(idx[-1]) if len(idx) else int(np.searchsorted(self.t, self.t_star)) - 1
        self.t_fs = float(self.t[i_fs])
        self.r_plateau = float(self.r[i_fs])
        ok = self.r[: i_fs + 1] <= self.r_plateau * (1 + TH["warp_same_regime"])
        j = first_sustained(ok)
        self.t_slow = float(self.t[j]) if j is not None else None
        self.tau0 = float(self.tau[0])

    def t_of(self, tau):
        """τ に初めて届く体験の時刻。表の始まりより前は None。"""
        if tau is None:
            return None
        tau = float(tau)
        if tau < self.tau_u[0] - 1e-9:
            return None
        if tau >= self.tau_u[-1]:
            return float(self.t_u[-1])
        return float(np.interp(tau, self.tau_u, self.t_u))

    def r_at_t(self, t):
        if t is None:
            return None
        return float(np.interp(t, self.t, self.r))

    def summary(self):
        return dict(path=rel(self.path), sha256=self.sha, id=self.id, tau_at_t0=self.tau0, t_star=self.t_star,
                    t_freeze_start=self.t_fs, r_plateau_before_freeze=self.r_plateau, t_slow_regime=self.t_slow)


# ---------------------------------------------------------------- 行の断面の量
def crest_lo_phi(A, Y, crest_hi, jE):
    """A, Y (nr, nu)。戻り H・cj・Lo（定義 A）・φ（前面の最大の角、中点 0.15〜0.97H、90° で鉛直）。"""
    nr, nu = A.shape
    rr = np.arange(nr)
    cols = np.arange(nu)
    Ym = np.where(cols[None, :] <= crest_hi[:, None], Y, -np.inf)
    cj = Ym.argmax(1)
    H = Y[rr, cj]
    Hc = H[:, None]
    # φ
    da, dy = np.diff(A, axis=1), np.diff(Y, axis=1)
    ym = 0.5 * (Y[:, 1:] + Y[:, :-1])
    seglen = np.hypot(da, dy)
    sc = cols[:-1][None, :]
    front_seg = (sc >= cj[:, None]) & (sc < jE)
    msk = front_seg & (seglen > 1e-3) & (dy < 0) & (ym > 0.15 * Hc) & (ym < 0.97 * Hc)
    ang = np.degrees(np.arctan2(-dy, da))
    phi = np.where(msk, ang, -np.inf).max(1)
    phi[~msk.any(1)] = np.nan
    # Lo：前の部分で 0.3H を最後に下へ横切る線分（y_j > 0.3H ≥ y_{j+1}）
    y3 = 0.3 * Hc
    cross = front_seg & (Y[:, :-1] > y3) & (Y[:, 1:] <= y3)
    has = cross.any(1)
    k = (nu - 2) - np.argmax(cross[:, ::-1], axis=1)
    ya, yb = Y[rr, k], Y[rr, k + 1]
    f = (ya - 0.3 * H) / np.maximum(ya - yb, 1e-12)
    a3 = A[rr, k] + f * (A[rr, k + 1] - A[rr, k])
    abv = (cols[None, :] >= cj[:, None]) & (cols[None, :] <= jE) & (Y > y3)
    amax = np.where(abv, A, -np.inf).max(1)
    Lo = np.where(has, amax - a3, np.nan)
    low = H < 1.0
    Lo[low] = np.nan
    phi[low] = np.nan
    return H, cj, Lo, phi


def gauss_detail(P, sigma, trim=2):
    """折れ線 P (n, 2) を列の方向にガウス（σ 列、両端は奇の折り返し）でならし、ならした線の法線の向きの差 dn（n,）を返す。
    両端の trim 列は nan。"""
    n = len(P)
    m = int(math.ceil(3 * sigma))
    m = min(m, n - 1)
    x = np.arange(-m, m + 1, dtype=float)
    kern = np.exp(-0.5 * (x / sigma) ** 2)
    kern /= kern.sum()
    # 奇の折り返し：P[-i] = 2P[0] − P[i]
    head = 2 * P[0] - P[m:0:-1]
    tail = 2 * P[-1] - P[-2:-m - 2:-1]
    Pp = np.concatenate([head, P, tail], 0)
    S = np.stack([np.convolve(Pp[:, i], kern, mode="valid") for i in range(2)], 1)
    T = np.gradient(S, axis=0)
    tl = np.linalg.norm(T, axis=1)
    nrm = np.stack([-T[:, 1], T[:, 0]], 1) / np.maximum(tl, 1e-12)[:, None]
    dn = ((P - S) * nrm).sum(1)
    dn[tl < 1e-9] = 0.0
    if trim > 0:
        dn[:trim] = np.nan
        dn[-trim:] = np.nan
    return dn


def seg_cols(q, seg):
    if seg == "upper":
        return np.arange(q["jt"], q["jtip"] + 1)
    return np.arange(q["jtip"], q["rim"] + 1)


# ---------------------------------------------------------------- 測定
def measure(ks, pk, log=print):
    rows = np.array([q["r"] for q in ks.curled])
    nr = len(rows)
    crest_hi = ks.crest_hi[rows]
    jE = ks.j_E
    taus = np.round(np.arange(pk.knots[0], 1e-9, 1.0 / HZ), 9)
    if abs(taus[-1]) > 1e-9:
        taus = np.append(taus, 0.0)
    taus[-1] = 0.0
    nt = len(taus)
    H = np.empty((nt, nr))
    Lo = np.empty((nt, nr))
    PHI = np.empty((nt, nr))
    # K* の細部の型
    tmpl = {}
    for sc in CLAW_SCALES:
        for i, q in enumerate(ks.curled):
            cols = seg_cols(q, sc["seg"])
            if len(cols) < sc["min_cols"]:
                continue
            P = np.stack([ks.A[q["r"], cols], ks.Y[q["r"], cols]], 1)
            dk = gauss_detail(P, sc["sigma"])
            ok = np.isfinite(dk)
            rmsk = float(np.sqrt(np.mean(dk[ok] ** 2)))
            tmpl[(sc["key"], i)] = dict(cols=cols, dk=dk, ok=ok, rms=rmsk, ss=float(np.sum(dk[ok] ** 2)))
    CL = {sc["key"]: np.zeros((nt, nr)) for sc in CLAW_SCALES}
    DL = {sc["key"]: np.zeros((nt, nr)) for sc in CLAW_SCALES}
    t0 = time.time()
    for it, tau in enumerate(taus):
        X = pk.world(tau)[rows]                            # (nr, nu, 3) 地面
        D = X - ks.O
        A = D @ ks.t
        Y = X[..., 1]
        h, cj, lo, ph = crest_lo_phi(A, Y, crest_hi, jE)
        H[it], Lo[it], PHI[it] = h, lo, ph
        if tau >= CLAW_FROM_TAU - 1e-9:
            for sc in CLAW_SCALES:
                key = sc["key"]
                for i, q in enumerate(ks.curled):
                    tp = tmpl.get((key, i))
                    if tp is None:
                        CL[key][it, i] = np.nan
                        DL[key][it, i] = np.nan
                        continue
                    cols = tp["cols"]
                    P = np.stack([A[i, cols], Y[i, cols]], 1)
                    dn = gauss_detail(P, sc["sigma"])
                    ok = tp["ok"] & np.isfinite(dn)
                    CL[key][it, i] = float(np.sum(dn[ok] * tp["dk"][ok]) / max(tp["ss"], 1e-12))
                    DL[key][it, i] = float(np.sqrt(np.mean(dn[ok] ** 2)) / max(tp["rms"], 1e-12))
        if it % 120 == 0:
            log("[ds28r01_overlap] τ %.3f（%d/%d）%.1f s" % (tau, it + 1, nt, time.time() - t0))
    tmpl_rms = {sc["key"]: np.array([tmpl[(sc["key"], i)]["rms"] if (sc["key"], i) in tmpl else np.nan for i in range(nr)])
                for sc in CLAW_SCALES}
    return dict(rows=rows, taus=taus, H=H, Lo=Lo, PHI=PHI, CL=CL, DL=DL, tmpl_rms=tmpl_rms)


def longest_run(mask, dt):
    """True の連続の最長の長さ（秒）。"""
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best * dt


def row_eval(M, i, warps):
    taus = M["taus"]
    dt = 1.0 / HZ
    nt = len(taus)
    H = M["H"][:, i]
    Lo = M["Lo"][:, i]
    phi = M["PHI"][:, i]
    Hf = float(H[-1])
    Hn = H / Hf
    Lo0 = np.nan_to_num(Lo, nan=-1.0)
    dH = deriv(H, dt)
    dLo = deriv(np.nan_to_num(Lo, nan=0.0), dt)
    Lof = float(Lo[-1])
    out = dict(row=int(M["rows"][i]), Hf=Hf, Lo_tstar=Lof, Lo_tstar_over_H=float(Lof / Hf))
    tau = lambda k: float(taus[k]) if k is not None else None
    hn = lambda k: float(Hn[k]) if k is not None else None
    ext_mask = Lo0 >= TH["ext_Lo_over_H"] * H
    k_ext = first_sustained(ext_mask)
    k_ext_first = first_true(ext_mask)
    k05 = first_true(Hn >= 0.5)
    out["tau_H05"] = tau(k05)
    for lv in (0.6, 0.7, 0.75, 0.8, 0.9, 0.95):
        out["tau_H%02d" % int(round(lv * 100))] = tau(first_true(Hn >= lv))
    k95 = first_true(Hn >= TH["plateau_H"])
    # --- T1
    out["tau_ext"] = tau(k_ext)
    out["tau_ext_first"] = tau(k_ext_first)
    out["H_over_Hf_at_ext"] = hn(k_ext)
    out["H_over_Hf_at_ext_first"] = hn(k_ext_first)
    out["gain_after_ext_over_Hf"] = float(1.0 - Hn[k_ext]) if k_ext is not None else None
    out["dHdtau_at_ext_mps"] = float(dH[k_ext]) if k_ext is not None else None
    out["drawdown_from_ext_m"] = drawdown(H[k_ext:]) if k_ext is not None else None
    out["drawdown_from_H05_m"] = drawdown(H[k05:]) if k05 is not None else None
    kmax = int(np.argmax(H))
    out["tau_Hmax"] = float(taus[kmax])
    out["Hmax_over_Hf"] = float(H[kmax] / Hf)
    out["plateau_s"] = float((Hn[:-1] >= TH["plateau_H"]).sum() * dt)
    # --- 唇の伸び方（段のあとの停滞を見る）
    vg = TH["grow_rel_per_s"] * Hf
    # 最後まで続く伸びの始まり（t* の直前の数コマの差分が片側になるので、最後の 2 コマは除いて探す）
    kg = first_sustained((dLo >= vg)[:-2])
    out["tau_grow"] = tau(kg)
    out["H_over_Hf_at_grow"] = hn(kg)
    out["Lo_over_H_at_grow"] = float(Lo[kg] / H[kg]) if kg is not None else None
    out["lip_stall_after_ext_s"] = longest_run((dLo < vg)[k_ext:-2], dt) if k_ext is not None else None
    out["Lo_drawdown_after_ext_m"] = drawdown(Lo0[k_ext:]) if k_ext is not None else None
    for fr in (0.25, 0.5):
        kk = first_sustained(Lo0 >= fr * Lof)
        out["tau_Lof%02d" % int(fr * 100)] = tau(kk)
        out["H_over_Hf_at_Lof%02d" % int(fr * 100)] = hn(kk)
    # --- c・d の目安
    kv = first_true(np.nan_to_num(phi, nan=-1) >= 90.0)
    out["tau_front_vertical"] = tau(kv)
    out["H_over_Hf_at_front_vertical"] = hn(kv)
    kd = first_sustained(Lo0 >= 0.1 * H)
    out["tau_Lo010"] = tau(kd)
    out["H_over_Hf_at_Lo010"] = hn(kd)
    out["dHdtau_at_Lo010_mps"] = float(dH[kd]) if kd is not None else None
    # --- 唇の進み P
    if k_ext is not None and Lof - Lo[k_ext] > 1e-6:
        P = (Lo - Lo[k_ext]) / (Lof - Lo[k_ext])
    else:
        P = np.full_like(Lo, np.nan)
    kp50 = first_sustained(np.nan_to_num(P, nan=-1) >= 0.5)
    out["tau_P50"] = tau(kp50)
    out["H_over_Hf_at_P50"] = hn(kp50)
    # 重なり（物理、時間曲線によらない）
    out["rise_share_after_ext"] = float((1.0 - Hn[k_ext]) / 0.5) if k_ext is not None else None
    out["P_at_H95"] = float(P[k95]) if (k95 is not None and k_ext is not None and k95 >= k_ext) else (0.0 if k_ext is not None else None)
    after05 = np.arange(nt) >= (k05 if k05 is not None else nt)
    growing = ext_mask & (dLo >= vg)
    inc = np.clip(np.diff(H), 0, None)
    tot = float(inc[after05[:-1]].sum())
    out["rise_share_while_lip_grows"] = float(inc[(after05 & growing)[:-1]].sum() / tot) if tot > 0 else None
    # --- 爪・鉤
    claws = {}
    k1 = int(np.searchsorted(taus, -1.0 - 1e-9))
    for sc in CLAW_SCALES:
        key = sc["key"]
        C = M["CL"][key][:, i]
        Dd = M["DL"][key][:, i]
        rmsk = float(M["tmpl_rms"][key][i])
        e = dict(kstar_rms_m=rmsk)
        if not np.isfinite(rmsk) or rmsk < 0.01 or k_ext is None:
            e["evaluated"] = False
            claws[key] = e
            continue
        e["evaluated"] = True
        e["C_at_ext"] = float(C[k_ext])
        e["D_at_ext"] = float(Dd[k_ext])
        e["C_tstar"] = float(C[-1])
        e["C_drawdown_from_ext"] = drawdown(C[k_ext:])
        e["D_drawdown_from_ext"] = drawdown(Dd[k_ext:])
        kc50 = first_sustained(np.nan_to_num(C, nan=-1) >= 0.5)
        e["tau_C50"] = tau(kc50)
        e["H_over_Hf_at_C50"] = hn(kc50)
        e["lag_C50_minus_P50_s"] = (float(taus[kc50]) - float(taus[kp50])) if (kc50 is not None and kp50 is not None) else None
        span = C[-1] - C[k_ext]
        e["C_share_last_1s"] = float((C[-1] - C[k1]) / span) if (abs(span) > 1e-6 and k1 >= k_ext) else None
        e["P_share_last_1s"] = float(1.0 - P[k1]) if k1 >= k_ext else None
        w = slice(k_ext, None)
        e["max_abs_C_minus_P"] = float(np.nanmax(np.abs(C[w] - P[w])))
        e["C_at_P50"] = float(C[kp50]) if kp50 is not None else None
        e["pass_monotone"] = bool(e["C_drawdown_from_ext"] <= TH["claw_mono_tol"])
        e["pass_start_small"] = bool(e["C_at_ext"] <= TH["claw_start_max"])
        e["pass_lag"] = bool(e["lag_C50_minus_P50_s"] is not None and e["lag_C50_minus_P50_s"] <= TH["claw_lag_max_s"])
        e["pass_follow"] = bool(e["max_abs_C_minus_P"] <= TH["claw_follow_max"])
        e["pass"] = bool(e["pass_monotone"] and e["pass_start_small"] and e["pass_lag"] and e["pass_follow"])
        claws[key] = e
    out["claws"] = claws
    # --- T1 の判定（進行役の定義）と、段のあとの停滞を見る厳しい読み（記録）
    t1 = dict(
        ext_start=bool(out["H_over_Hf_at_ext"] is not None and out["H_over_Hf_at_ext"] <= TH["ext_H_max"]),
        gain=bool(out["gain_after_ext_over_Hf"] is not None and out["gain_after_ext_over_Hf"] >= TH["gain_min"]),
        monotone=bool(out["drawdown_from_ext_m"] is not None and out["drawdown_from_ext_m"] <= TH["mono_tol_m"]),
        no_plateau=bool(out["plateau_s"] <= TH["plateau_max_s"]),
        hmax_at_tstar=bool(out["tau_Hmax"] >= -TH["hmax_window_s"] - 1e-9),
    )
    t1["pass"] = bool(all(t1.values()))
    out["T1"] = t1
    out["T1_strict"] = dict(
        grow_start=bool(out["H_over_Hf_at_grow"] is not None and out["H_over_Hf_at_grow"] <= TH["ext_H_max"]),
        no_stall=bool(out["lip_stall_after_ext_s"] is not None and out["lip_stall_after_ext_s"] <= TH["stall_max_s"]),
        lip_half_before_plateau=bool(out["P_at_H95"] is not None and out["P_at_H95"] >= 0.5),
    )
    out["T1_strict"]["pass"] = bool(all(out["T1_strict"].values()))
    # --- 画面の時刻
    scr = {}
    for wname, W in warps.items():
        s = dict()
        for key in ("tau_H05", "tau_H75", "tau_H90", "tau_H95", "tau_ext", "tau_ext_first", "tau_grow", "tau_Hmax",
                    "tau_front_vertical", "tau_Lo010", "tau_P50", "tau_Lof25", "tau_Lof50"):
            s["t" + key[3:]] = W.t_of(out[key])
        s["r_at_ext"] = W.r_at_t(s["t_ext"])
        s["r_at_grow"] = W.r_at_t(s["t_grow"])
        s["rise_H05_to_H95_s"] = (s["t_H95"] - s["t_H05"]) if (s["t_H05"] is not None and s["t_H95"] is not None) else None
        s["rise_H05_to_Hmax_s"] = (s["t_Hmax"] - s["t_H05"]) if s["t_H05"] is not None else None
        s["ext_to_tstar_s"] = (W.t_star - s["t_ext"]) if s["t_ext"] is not None else None
        s["ext_share_before_H95"] = ((min(s["t_H95"], W.t_star) - s["t_ext"]) / (W.t_star - s["t_ext"])
                                     if (s["t_ext"] is not None and s["t_H95"] is not None and W.t_star > s["t_ext"]) else None)
        if s["ext_share_before_H95"] is not None:
            s["ext_share_before_H95"] = max(0.0, s["ext_share_before_H95"])
        tt = W.t[(W.t < W.t_star) & (W.tau >= taus[0])]
        tauq = np.interp(tt, W.t, W.tau)
        dtt = np.diff(np.append(tt, W.t_star))
        Hq = np.interp(tauq, taus, H)
        s["plateau_screen_s"] = float(dtt[Hq / Hf >= TH["plateau_H"]].sum())
        rq = np.interp(tt, W.t, W.r)
        dHq = np.interp(tauq, taus, dH) * rq
        dLq = np.interp(tauq, taus, dLo) * rq
        Loq = np.interp(tauq, taus, Lo0)
        extq = Loq >= TH["ext_Lo_over_H"] * Hq
        aft = tauq >= (out["tau_H05"] if out["tau_H05"] is not None else 0.0)
        ov = {}
        for vname, v in (("primary", TH["rate_rel_per_s"] * Hf), ("strict", TH["rate_strict_rel_per_s"] * Hf),
                         ("any", TH["rate_any_mps"])):
            rise = aft & (dHq >= v)
            grow = extq & (dLq >= v)
            both = rise & grow
            Tr, Tg, Tb = float(dtt[rise].sum()), float(dtt[grow].sum()), float(dtt[both].sum())
            gl = np.clip(dLq, 0, None) * dtt
            ov[vname] = dict(v_mps=v, rise_s=Tr, grow_s=Tg, both_s=Tb,
                             frac_of_ext=(Tb / Tg) if Tg > 0 else None,
                             frac_of_rise=(Tb / Tr) if Tr > 0 else None,
                             jaccard=(Tb / (Tr + Tg - Tb)) if (Tr + Tg - Tb) > 0 else None,
                             lip_growth_share_while_rising=(float(gl[extq & rise].sum() / gl[extq].sum())
                                                            if gl[extq].sum() > 0 else None))
        s["overlap"] = ov
        s["slow_regime_before_ext"] = bool(W.t_slow is not None and s["t_ext"] is not None and W.t_slow <= s["t_ext"] + 1e-6)
        s["slow_regime_before_grow"] = bool(W.t_slow is not None and s["t_grow"] is not None and W.t_slow <= s["t_grow"] + 1e-6)
        s["r_range_in_ext"] = None
        if s["t_ext"] is not None:
            m = (W.t >= s["t_ext"]) & (W.t <= W.t_fs)
            if m.any():
                s["r_range_in_ext"] = [float(W.r[m].min()), float(W.r[m].max())]
        scr[wname] = s
    out["screen"] = scr
    out["_series"] = dict(H=H, Hn=Hn, Lo=Lo, P=P, phi=phi, dH=dH, dLo=dLo,
                          C={sc["key"]: M["CL"][sc["key"]][:, i] for sc in CLAW_SCALES},
                          D={sc["key"]: M["DL"][sc["key"]][:, i] for sc in CLAW_SCALES})
    return out


def dist(vals):
    v = np.array([x for x in vals if x is not None and np.isfinite(x)], float)
    if len(v) == 0:
        return dict(n=0)
    return dict(n=int(len(v)), min=float(v.min()), p10=float(np.percentile(v, 10)), median=float(np.median(v)),
                p90=float(np.percentile(v, 90)), max=float(v.max()))


def series_out(R, warps, taus, step=2):
    s = R["_series"]
    k = np.arange(0, len(taus), step)
    if k[-1] != len(taus) - 1:
        k = np.append(k, len(taus) - 1)
    o = dict(tau=taus[k], H=s["H"][k], H_over_Hf=s["Hn"][k], Lo=s["Lo"][k], Lo_over_H=s["Lo"][k] / s["H"][k], P=s["P"][k],
             phi_deg=s["phi"][k], dHdtau=s["dH"][k], dLodtau=s["dLo"][k])
    for key in s["C"]:
        o["C_" + key] = s["C"][key][k]
        o["D_" + key] = s["D"][key][k]
    for wname, W in warps.items():
        o["t_" + wname] = [W.t_of(x) for x in taus[k]]
    return o


def load_or_measure(ks, pk, cache, log=print):
    """測った時系列（重い部分）を包みの pos SHA-256 と検査器の測り方の版で照合して使い回す（G: の出力の隣）。"""
    tag = "%s|%s|%d|%.2f|%s" % (pk.pos_sha, pk.meta.get("frame", {}).get("tau", [0])[-1] if isinstance(pk.meta.get("frame"), dict) else "",
                                HZ, CLAW_FROM_TAU, json.dumps([[c["key"], c["seg"], c["sigma"], c["min_cols"]] for c in CLAW_SCALES]))
    tag += "|measure/2"
    if cache and os.path.isfile(cache):
        z = np.load(cache, allow_pickle=False)
        if str(z["tag"]) == tag:
            log("[ds28r01_overlap] 測定の使い回し：%s" % rel(cache))
            M = dict(rows=z["rows"], taus=z["taus"], H=z["H"], Lo=z["Lo"], PHI=z["PHI"],
                     CL={c["key"]: z["CL_" + c["key"]] for c in CLAW_SCALES},
                     DL={c["key"]: z["DL_" + c["key"]] for c in CLAW_SCALES},
                     tmpl_rms={c["key"]: z["TR_" + c["key"]] for c in CLAW_SCALES})
            return M
    M = measure(ks, pk, log=log)
    if cache:
        kw = dict(tag=np.array(tag), rows=M["rows"], taus=M["taus"], H=M["H"], Lo=M["Lo"], PHI=M["PHI"])
        for c in CLAW_SCALES:
            kw["CL_" + c["key"]] = M["CL"][c["key"]]
            kw["DL_" + c["key"]] = M["DL"][c["key"]]
            kw["TR_" + c["key"]] = M["tmpl_rms"][c["key"]]
        np.savez_compressed(cache, **kw)
    return M


def run(package, tw_default, tw_alt, out, label=None, evidence=None, fig=True, log=print):
    t_clock = time.time()
    ks = g27.KStar()
    pk = g27.Package(package, ks)
    warps = dict(default=Warp(tw_default, "default"), alt=Warp(tw_alt, "alt"))
    cache = os.path.splitext(out)[0] + "_measure.npz"
    M = load_or_measure(ks, pk, cache, log=log)
    del pk.P
    rows = list(M["rows"])
    R = {}
    for i, r in enumerate(rows):
        R[int(r)] = row_eval(M, i, warps)
    main, peak = R[MAIN_ROW], R[PEAK_ROW]
    allr = list(R.values())

    def t2p(x):
        e = x["claws"].get(PRIMARY_CLAW, {})
        return e.get("pass") if e.get("evaluated") else None

    ovd = lambda x, w, k: x["screen"][w]["overlap"]["primary"][k]
    summary_all = dict(
        n_rows=len(allr),
        H_over_Hf_at_ext=dist([x["H_over_Hf_at_ext"] for x in allr]),
        H_over_Hf_at_grow=dist([x["H_over_Hf_at_grow"] for x in allr]),
        gain_after_ext_over_Hf=dist([x["gain_after_ext_over_Hf"] for x in allr]),
        tau_ext=dist([x["tau_ext"] for x in allr]),
        tau_grow=dist([x["tau_grow"] for x in allr]),
        lip_stall_after_ext_s=dist([x["lip_stall_after_ext_s"] for x in allr]),
        Lo_drawdown_after_ext_m=dist([x["Lo_drawdown_after_ext_m"] for x in allr]),
        drawdown_from_ext_m=dist([x["drawdown_from_ext_m"] for x in allr]),
        plateau_s=dist([x["plateau_s"] for x in allr]),
        tau_Hmax=dist([x["tau_Hmax"] for x in allr]),
        rise_share_after_ext=dist([x["rise_share_after_ext"] for x in allr]),
        rise_share_while_lip_grows=dist([x["rise_share_while_lip_grows"] for x in allr]),
        P_at_H95=dist([x["P_at_H95"] for x in allr]),
        H_over_Hf_at_P50=dist([x["H_over_Hf_at_P50"] for x in allr]),
        H_over_Hf_at_front_vertical=dist([x["H_over_Hf_at_front_vertical"] for x in allr]),
        H_over_Hf_at_Lo010=dist([x["H_over_Hf_at_Lo010"] for x in allr]),
        default_frac_of_ext=dist([ovd(x, "default", "frac_of_ext") for x in allr]),
        default_jaccard=dist([ovd(x, "default", "jaccard") for x in allr]),
        default_lip_growth_share_while_rising=dist([ovd(x, "default", "lip_growth_share_while_rising") for x in allr]),
        alt_frac_of_ext=dist([ovd(x, "alt", "frac_of_ext") for x in allr]),
        alt_jaccard=dist([ovd(x, "alt", "jaccard") for x in allr]),
        alt_lip_growth_share_while_rising=dist([ovd(x, "alt", "lip_growth_share_while_rising") for x in allr]),
        claw_C_at_ext=dist([x["claws"][PRIMARY_CLAW].get("C_at_ext") for x in allr]),
        claw_max_abs_C_minus_P=dist([x["claws"][PRIMARY_CLAW].get("max_abs_C_minus_P") for x in allr]),
        claw_lag_C50_minus_P50_s=dist([x["claws"][PRIMARY_CLAW].get("lag_C50_minus_P50_s") for x in allr]),
        claw_C_share_last_1s=dist([x["claws"][PRIMARY_CLAW].get("C_share_last_1s") for x in allr]),
        claw_H_over_Hf_at_C50=dist([x["claws"][PRIMARY_CLAW].get("H_over_Hf_at_C50") for x in allr]),
        T1_pass_rows=int(sum(1 for x in allr if x["T1"]["pass"])),
        T1_sub_pass_rows={k: int(sum(1 for x in allr if x["T1"][k])) for k in ("ext_start", "gain", "monotone", "no_plateau", "hmax_at_tstar")},
        T1_strict_pass_rows=int(sum(1 for x in allr if x["T1_strict"]["pass"])),
        T1_strict_sub_pass_rows={k: int(sum(1 for x in allr if x["T1_strict"][k])) for k in ("grow_start", "no_stall", "lip_half_before_plateau")},
        T2_evaluated_rows=int(sum(1 for x in allr if t2p(x) is not None)),
        T2_pass_rows=int(sum(1 for x in allr if t2p(x))),
        rows_without_ext=[x["row"] for x in allr if x["tau_ext"] is None],
    )
    verdict = {}
    for nm, x in (("main_159", main), ("peak_192", peak)):
        c = x["claws"][PRIMARY_CLAW]
        verdict[nm] = dict(T1=x["T1"], T1_strict=x["T1_strict"],
                           T2=dict(evaluated=c.get("evaluated"), monotone=c.get("pass_monotone"), start_small=c.get("pass_start_small"),
                                   follow=c.get("pass_follow"), lag=c.get("pass_lag"), passed=c.get("pass")),
                           T5_default_slow_before_ext=x["screen"]["default"]["slow_regime_before_ext"],
                           T5_default_slow_before_grow=x["screen"]["default"]["slow_regime_before_grow"])
    verdict["T1_main_and_peak"] = bool(main["T1"]["pass"] and peak["T1"]["pass"])
    verdict["T1_strict_main_and_peak_record"] = bool(main["T1_strict"]["pass"] and peak["T1_strict"]["pass"])
    verdict["T2_main_and_peak"] = bool(t2p(main) and t2p(peak))
    verdict["T5_default_slow_before_ext_main_and_peak"] = bool(main["screen"]["default"]["slow_regime_before_ext"]
                                                               and peak["screen"]["default"]["slow_regime_before_ext"])
    rep = dict(
        schema="GreatWave.DS28R01.overlap/1",
        number="設計28修正01",
        tool=rel(os.path.abspath(__file__)),
        tool_sha256=sha256_file(os.path.abspath(__file__)),
        label=label or os.path.basename(os.path.abspath(package).rstrip("/\\")),
        evidence_kind_ja="検査器の出力（物理の時刻 τ で測り、体験の時刻は時間曲線の表で写した値）。Q13 の T1・T2・T5 の読み。",
        package=dict(dir=rel(pk.dir), version=pk.version, pos_sha256=pk.pos_sha, layers=pk.L, interface=pk.iface),
        kstar=dict(sha256=ks.sha, main_row=ks.main_row, peak_row=ks.peak_row, n_curled=len(ks.curled), H_star_main=ks.H_star),
        warps={k: W.summary() for k, W in warps.items()},
        thresholds=TH,
        claw_scales=[{k: v for k, v in sc.items()} for sc in CLAW_SCALES],
        primary_claw=PRIMARY_CLAW,
        readings_ja=READINGS_JA,
        hz=HZ,
        verdict=verdict,
        main_159={k: v for k, v in main.items() if k != "_series"},
        peak_192={k: v for k, v in peak.items() if k != "_series"},
        summary_all_curled=summary_all,
        rows={str(r): {k: v for k, v in x.items() if k not in ("_series", "screen")} | dict(
            screen={w: {kk: vv for kk, vv in s.items() if kk != "overlap"} | dict(overlap_primary=s["overlap"]["primary"])
                    for w, s in x["screen"].items()}) for r, x in R.items()},
        series=dict(main_159=series_out(main, warps, M["taus"]), peak_192=series_out(peak, warps, M["taus"])),
    )
    rep = clean(rep)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    figp = os.path.splitext(out)[0] + "_fig.png" if fig else None
    if figp:
        write_fig(figp, rep, warps)
        rep["figure"] = rel(os.path.abspath(figp))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    md = os.path.splitext(out)[0] + ".md"
    write_md(md, rep)
    if evidence:
        ev_fig = os.path.splitext(evidence)[0] + "_fig.png"
        small = {k: v for k, v in rep.items() if k not in ("rows", "series")}
        if figp:
            small["figure"] = rel(os.path.abspath(ev_fig))
        small["rows_compact"] = {r: dict(H_over_Hf_at_ext=x["H_over_Hf_at_ext"], H_over_Hf_at_grow=x["H_over_Hf_at_grow"],
                                         tau_ext=x["tau_ext"], gain=x["gain_after_ext_over_Hf"], plateau_s=x["plateau_s"],
                                         tau_Hmax=x["tau_Hmax"], P_at_H95=x["P_at_H95"], T1=x["T1"]["pass"],
                                         claw_C_at_ext=x["claws"][PRIMARY_CLAW].get("C_at_ext"),
                                         claw_lag_s=x["claws"][PRIMARY_CLAW].get("lag_C50_minus_P50_s"))
                                 for r, x in rep["rows"].items()}
        small["full_report"] = rel(os.path.abspath(out))
        os.makedirs(os.path.dirname(os.path.abspath(evidence)), exist_ok=True)
        with open(evidence, "w", encoding="utf-8") as f:
            json.dump(small, f, ensure_ascii=False, indent=1)
        write_md(os.path.splitext(evidence)[0] + ".md", dict(rep, figure=small.get("figure")))
        if figp:
            import shutil
            shutil.copyfile(figp, ev_fig)
    log("[ds28r01_overlap] 書いた：%s（%.1f s）" % (rel(os.path.abspath(out)), time.time() - t_clock))
    return rep


# ---------------------------------------------------------------- 図（PIL。H/Hf・Lo/Lo(t*)・爪 C を体験の時刻で）
def write_fig(path, rep, warps):
    from PIL import Image, ImageDraw, ImageFont
    W_, H_ = 1600, 900
    im = Image.new("RGB", (W_, H_), "white")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 18)
        fs = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 14)
    except Exception:
        font = fs = ImageFont.load_default()
    d.text((20, 8), "Q13 重なりの検査：%s（青 H/Hf、橙 Lo/Lo(t*)、緑 爪 C（claw_steps）、灰 速さ r。縦線：実線 伸び出しの始まり、破線 H = 0.95Hf）" % rep["label"],
           fill="black", font=font)
    panels = [("main_159", "default"), ("main_159", "alt"), ("peak_192", "default"), ("peak_192", "alt")]
    t0, t1 = 4.0, 12.3
    for n, (rk, w) in enumerate(panels):
        ox, oy = 70 + (n % 2) * 780, 72 + (n // 2) * 420
        pw, ph = 700, 340
        d.rectangle([ox, oy, ox + pw, oy + ph], outline="black")
        X = lambda t: ox + (t - t0) / (t1 - t0) * pw
        Yv = lambda v: oy + ph - (min(max(v, -0.05), 1.1) + 0.05) / 1.15 * ph
        for g in (0.0, 0.25, 0.5, 0.75, 1.0):
            d.line([ox, Yv(g), ox + pw, Yv(g)], fill=(225, 225, 225))
            d.text((ox - 40, Yv(g) - 9), "%.2f" % g, fill="black", font=fs)
        for t in range(int(t0), int(t1) + 1):
            d.line([X(t), oy + ph, X(t), oy + ph + 5], fill="black")
            d.text((X(t) - 8, oy + ph + 6), "%d" % t, fill="black", font=fs)
        s = rep["series"][rk]
        tt = np.array([np.nan if x is None else x for x in s["t_" + w]], float)
        Wp = warps[w]
        m = (Wp.t >= t0) & (Wp.t <= t1)
        d.line([(X(a), Yv(b)) for a, b in zip(Wp.t[m][::4], Wp.r[m][::4])], fill=(150, 150, 150), width=2)
        Lof = s["Lo"][-1]
        curves = [(s["H_over_Hf"], (30, 90, 200)), ([np.nan if v is None else v / Lof for v in s["Lo"]], (230, 130, 20)),
                  (s["C_" + PRIMARY_CLAW], (40, 160, 60))]
        for vals, col in curves:
            pts = [(X(a), Yv(b)) for a, b in zip(tt, vals) if b is not None and np.isfinite(a) and np.isfinite(b) and t0 <= a <= t1]
            if len(pts) > 1:
                d.line(pts, fill=col, width=3)
        sc = rep[rk]["screen"][w]
        for key, dash in (("t_ext", False), ("t_H95", True)):
            t = sc.get(key)
            if t is None or not (t0 <= t <= t1):
                continue
            if dash:
                for yy in range(oy, oy + ph, 12):
                    d.line([X(t), yy, X(t), yy + 6], fill="black", width=1)
            else:
                d.line([X(t), oy, X(t), oy + ph], fill="black", width=1)
        o = sc["overlap"]["primary"]
        d.text((ox + 2, oy - 24), "%s・%s（t_ext %s s、H/Hf %s）重なり frac_of_ext %s・jaccard %s" % (
            "主断面 159" if rk == "main_159" else "峰の行 192", "既定" if w == "default" else "代案",
            f2(sc.get("t_ext"), 2), f2(rep[rk]["H_over_Hf_at_ext"], 3), f2(o["frac_of_ext"], 2), f2(o["jaccard"], 2)),
            fill="black", font=fs)
        d.text((ox + pw - 120, oy + ph + 22), "体験の時刻 t [s]", fill="black", font=fs)
    im.save(path)


# ---------------------------------------------------------------- 日本語の表
def f2(x, nd=2, unit=""):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "合格" if x else "不合格"
    return ("%." + str(nd) + "f%s") % (x, unit)


def write_md(path, rep):
    L = []
    L.append("# 設計28修正01 Q13 の重なりの検査：%s" % rep["label"])
    L.append("")
    L.append("検査器 `%s`（動きの生成器から独立）。包み `%s`（%d 層、pos SHA-256 %s…）。時間曲線：既定 `%s`、代案 `%s`。"
             % (rep["tool"], rep["package"]["dir"], rep["package"]["layers"], rep["package"]["pos_sha256"][:12],
                rep["warps"]["default"]["path"], rep["warps"]["alt"]["path"]))
    L.append("物理の時刻 τ（t\\* = 0）で %d Hz に測り、体験の時刻 t（t\\* = 12.0 s）へ表で写した。H/H\\* はその行の t\\* の頂 Hf で割る。" % rep["hz"])
    if rep.get("figure"):
        L.append("")
        L.append("図：`%s`（主断面・峰の行 × 既定・代案。青 H/Hf、橙 Lo/Lo(t\\*)、緑 爪 C、灰 速さ r）。" % rep["figure"])
    L.append("")
    v = rep["verdict"]
    L.append("## 判定（主断面 159・峰の行 192）")
    L.append("")
    L.append("| 目標 | 主断面 159 | 峰の行 192 |")
    L.append("| --- | --- | --- |")
    for k, ja in (("ext_start", "T1 伸び出しの始まり（Lo ≥ 0.05H）の H/H\\* ≤ 0.75"), ("gain", "T1 始まりから t\\* までの H の増え ≥ 0.25H\\*"),
                  ("monotone", "T1 始まりから t\\* まで H が減らない（0.05 m）"), ("no_plateau", "T1 H ≥ 0.95H\\* の時間 ≤ 0.5 s（物理）"),
                  ("hmax_at_tstar", "T1 最高点が t\\* から 0.2 s 以内"), ("pass", "**T1 まとめ**")):
        L.append("| %s | %s | %s |" % (ja, f2(v["main_159"]["T1"][k]), f2(v["peak_192"]["T1"][k])))
    for k, ja in (("grow_start", "（厳しい読み・記録）唇の伸びの始まり τ_grow の H/H\\* ≤ 0.75"),
                  ("no_stall", "（厳しい読み・記録）始まりの後に唇が止まる時間 ≤ 0.3 s"),
                  ("lip_half_before_plateau", "（厳しい読み・記録）頂が 0.95H\\* に届くまでに伸び出しの半分以上"),
                  ("pass", "（厳しい読み・記録）まとめ")):
        L.append("| %s | %s | %s |" % (ja, f2(v["main_159"]["T1_strict"][k]), f2(v["peak_192"]["T1_strict"][k])))
    for k, ja in (("monotone", "T2 爪の係数 C が始まりから減らない（0.05）"), ("start_small", "T2 始まりの C ≤ 0.2"),
                  ("follow", "T2 始まりから t\\* まで \\|C − P\\| ≤ 0.25"),
                  ("lag", "T2 C の 50% が唇の進み P の 50% より 0.3 s を超えて遅れない"), ("passed", "**T2 まとめ**（%s）" % rep["primary_claw"])):
        L.append("| %s | %s | %s |" % (ja, f2(v["main_159"]["T2"][k]), f2(v["peak_192"]["T2"][k])))
    L.append("| T5 既定の時間曲線：伸び出しの始まりの前に一定の遅さへ入る | %s | %s |" % (
        f2(v["main_159"]["T5_default_slow_before_ext"]), f2(v["peak_192"]["T5_default_slow_before_ext"])))
    L.append("| （記録）既定の時間曲線：唇の伸びの始まりの前に一定の遅さへ入る | %s | %s |" % (
        f2(v["main_159"]["T5_default_slow_before_grow"]), f2(v["peak_192"]["T5_default_slow_before_grow"])))
    L.append("")
    L.append("## 主な値（物理の時刻）")
    L.append("")
    L.append("| 量 | 主断面 159 | 峰の行 192 |")
    L.append("| --- | --- | --- |")
    m, p = rep["main_159"], rep["peak_192"]
    for ja, k, nd in (
        ("Hf（t\\* の頂）[m]", "Hf", 2), ("t\\* の Lo / Hf", "Lo_tstar_over_H", 3),
        ("H/Hf 0.5 に届く τ [s]", "tau_H05", 3), ("H/Hf 0.75 に届く τ [s]", "tau_H75", 3), ("H/Hf 0.9 に届く τ [s]", "tau_H90", 3),
        ("H/Hf 0.95 に届く τ [s]", "tau_H95", 3),
        ("伸び出しの始まり τ_ext（Lo ≥ 0.05H が続く）[s]", "tau_ext", 3), ("その時の H/Hf", "H_over_Hf_at_ext", 3),
        ("初めて Lo ≥ 0.05H の τ [s]", "tau_ext_first", 3), ("その時の H/Hf", "H_over_Hf_at_ext_first", 3),
        ("唇の伸びの始まり τ_grow [s]", "tau_grow", 3), ("その時の H/Hf", "H_over_Hf_at_grow", 3), ("その時の Lo/H", "Lo_over_H_at_grow", 3),
        ("始まりの後に唇が伸びない最長の時間 [s]", "lip_stall_after_ext_s", 3), ("始まりの後の Lo の戻り [m]", "Lo_drawdown_after_ext_m", 3),
        ("Lo が t\\* の 25% に届く τ [s]", "tau_Lof25", 3), ("その時の H/Hf", "H_over_Hf_at_Lof25", 3),
        ("Lo が t\\* の 50% に届く τ [s]", "tau_Lof50", 3), ("その時の H/Hf", "H_over_Hf_at_Lof50", 3),
        ("始まりから t\\* までの H の増え / Hf", "gain_after_ext_over_Hf", 3), ("始まりの dH/dτ [m/s]", "dHdtau_at_ext_mps", 2),
        ("後半の上昇（0.5→1.0Hf）のうち始まりの後の割合", "rise_share_after_ext", 3),
        ("0.5Hf の後の上昇のうち唇が伸びている間の割合", "rise_share_while_lip_grows", 3),
        ("頂が 0.95Hf に届いた時の唇の進み P", "P_at_H95", 3),
        ("始まりから t\\* までの H の戻り [m]", "drawdown_from_ext_m", 3), ("H/Hf 0.5 から t\\* までの戻り [m]", "drawdown_from_H05_m", 3),
        ("H ≥ 0.95Hf の時間（物理）[s]", "plateau_s", 3), ("最高点の τ [s]", "tau_Hmax", 3), ("最高点 / Hf", "Hmax_over_Hf", 4),
        ("c の目安：前面が初めて鉛直の τ [s]", "tau_front_vertical", 3), ("その時の H/Hf", "H_over_Hf_at_front_vertical", 3),
        ("d の目安：Lo ≥ 0.1H が続く τ [s]", "tau_Lo010", 3), ("その時の H/Hf", "H_over_Hf_at_Lo010", 3),
        ("その時の dH/dτ [m/s]", "dHdtau_at_Lo010_mps", 2), ("唇の進み P が 0.5 の τ [s]", "tau_P50", 3), ("その時の H/Hf", "H_over_Hf_at_P50", 3),
    ):
        L.append("| %s | %s | %s |" % (ja, f2(m.get(k), nd), f2(p.get(k), nd)))
    L.append("")
    L.append("### 爪・鉤の細部（K\\* の模様への射影 C、t\\* で 1）")
    L.append("")
    L.append("| 尺度 | 量 | 主断面 159 | 峰の行 192 |")
    L.append("| --- | --- | --- | --- |")
    for sc in rep["claw_scales"]:
        k = sc["key"]
        cm, cp = m["claws"].get(k, {}), p["claws"].get(k, {})
        for ja, kk, nd in (("K\\* の RMS(dn) [m]", "kstar_rms_m", 3), ("始まりの C", "C_at_ext", 3), ("始まりの D（振幅の比）", "D_at_ext", 3),
                           ("始まりから t\\* までの C の戻り", "C_drawdown_from_ext", 3), ("C が 0.5 に届く τ [s]", "tau_C50", 3),
                           ("その時の H/Hf", "H_over_Hf_at_C50", 3),
                           ("C の 50% − P の 50% [s]", "lag_C50_minus_P50_s", 3), ("最後の 1 s の C の増えの割合", "C_share_last_1s", 3),
                           ("最後の 1 s の P の増えの割合", "P_share_last_1s", 3), ("P = 0.5 の時の C", "C_at_P50", 3),
                           ("max \\|C − P\\|", "max_abs_C_minus_P", 3)):
            def cell(e, kk=kk, nd=nd):
                if kk == "kstar_rms_m":
                    return f2(e.get(kk), nd)
                return f2(e.get(kk), nd) if e.get("evaluated") else "対象外"
            L.append("| %s | %s | %s | %s |" % (sc["ja"] if kk == "kstar_rms_m" else "", ja, cell(cm), cell(cp)))
    L.append("")
    L.append("## 体験の時刻（画面）")
    L.append("")
    for w in ("default", "alt"):
        W = rep["warps"][w]
        L.append("### %s（`%s`）" % ("既定" if w == "default" else "代案", W["path"]))
        L.append("")
        L.append("t = 0 の τ %s s。止めるための区間の始まり t_fs %s s（その前の速さ r %s）。一定の遅さに入る t_slow %s s。" % (
            f2(W["tau_at_t0"], 3), f2(W["t_freeze_start"], 3), f2(W["r_plateau_before_freeze"], 3), f2(W["t_slow_regime"], 3)))
        L.append("")
        L.append("| 量 | 主断面 159 | 峰の行 192 |")
        L.append("| --- | --- | --- |")
        sm, sp = m["screen"][w], p["screen"][w]
        for ja, k, nd in (("H/Hf 0.5 の t [s]", "t_H05", 2), ("H/Hf 0.75 の t [s]", "t_H75", 2), ("H/Hf 0.9 の t [s]", "t_H90", 2),
                          ("H/Hf 0.95 の t [s]", "t_H95", 2), ("伸び出しの始まり t_ext [s]", "t_ext", 2), ("唇の伸びの始まり t_grow [s]", "t_grow", 2),
                          ("Lo が t\\* の 25% の t [s]", "t_Lof25", 2), ("Lo が t\\* の 50% の t [s]", "t_Lof50", 2), ("最高点の t [s]", "t_Hmax", 2),
                          ("前面が鉛直の t [s]", "t_front_vertical", 2), ("Lo ≥ 0.1H の t [s]", "t_Lo010", 2), ("P = 0.5 の t [s]", "t_P50", 2),
                          ("伸び出しの始まりの速さ r", "r_at_ext", 3), ("唇の伸びの始まりの速さ r", "r_at_grow", 3),
                          ("上昇 0.5→0.95Hf の画面の時間 [s]", "rise_H05_to_H95_s", 2),
                          ("上昇 0.5Hf→最高点の画面の時間 [s]", "rise_H05_to_Hmax_s", 2), ("伸び出し（始まり → t\\*）の画面の時間 [s]", "ext_to_tstar_s", 2),
                          ("伸び出しの画面の時間のうち頂が 0.95Hf の前の割合", "ext_share_before_H95", 3),
                          ("H ≥ 0.95Hf の画面の時間 [s]", "plateau_screen_s", 2)):
            L.append("| %s | %s | %s |" % (ja, f2(sm.get(k), nd), f2(sp.get(k), nd)))
        for vn, vja in (("primary", "主（≥ 0.03 Hf/s）"), ("strict", "厳しい（≥ 0.05 Hf/s）"), ("any", "参考（≥ 0.1 m/s）")):
            om, op = sm["overlap"][vn], sp["overlap"][vn]
            for ja, k, nd in (("唇が伸びる時間 [s]", "grow_s", 2), ("頂が上がる時間（0.5Hf の後）[s]", "rise_s", 2), ("両方の時間 [s]", "both_s", 2),
                              ("伸びる時間のうち上がる割合", "frac_of_ext", 3), ("上がる時間のうち伸びる割合", "frac_of_rise", 3),
                              ("両方の和に対する重なり（jaccard）", "jaccard", 3), ("唇の伸びのうち頂が上がっている間の割合", "lip_growth_share_while_rising", 3)):
                L.append("| 重なり %s：%s | %s | %s |" % (vja, ja, f2(om[k], nd), f2(op[k], nd)))
        L.append("")
    s = rep["summary_all_curled"]
    L.append("## 巻きの行すべて（%d 行）" % s["n_rows"])
    L.append("")
    L.append("| 量 | 最小 | 10% | 中央 | 90% | 最大 |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for ja, k in (("伸び出しの始まりの H/Hf", "H_over_Hf_at_ext"), ("唇の伸びの始まりの H/Hf", "H_over_Hf_at_grow"),
                  ("始まりの後の H の増え / Hf", "gain_after_ext_over_Hf"),
                  ("伸び出しの始まり τ [s]", "tau_ext"), ("唇の伸びの始まり τ [s]", "tau_grow"),
                  ("始まりの後に唇が伸びない最長の時間 [s]", "lip_stall_after_ext_s"), ("始まりの後の Lo の戻り [m]", "Lo_drawdown_after_ext_m"),
                  ("始まりからの H の戻り [m]", "drawdown_from_ext_m"),
                  ("H ≥ 0.95Hf の時間 [s]", "plateau_s"), ("最高点の τ [s]", "tau_Hmax"),
                  ("後半の上昇のうち始まりの後の割合", "rise_share_after_ext"), ("0.5Hf の後の上昇のうち唇が伸びている間の割合", "rise_share_while_lip_grows"),
                  ("頂が 0.95Hf に届いた時の唇の進み P", "P_at_H95"), ("P = 0.5 の時の H/Hf", "H_over_Hf_at_P50"),
                  ("前面が鉛直の時の H/Hf", "H_over_Hf_at_front_vertical"), ("Lo ≥ 0.1H の時の H/Hf", "H_over_Hf_at_Lo010"),
                  ("既定：伸びる時間のうち上がる割合（主）", "default_frac_of_ext"), ("既定：jaccard（主）", "default_jaccard"),
                  ("既定：唇の伸びのうち頂が上がっている間（主）", "default_lip_growth_share_while_rising"),
                  ("代案：伸びる時間のうち上がる割合（主）", "alt_frac_of_ext"), ("代案：jaccard（主）", "alt_jaccard"),
                  ("代案：唇の伸びのうち頂が上がっている間（主）", "alt_lip_growth_share_while_rising"),
                  ("爪 C（%s）の始まりの値" % rep["primary_claw"], "claw_C_at_ext"), ("爪 max \\|C − P\\|", "claw_max_abs_C_minus_P"),
                  ("爪 C の 50% − P の 50% [s]", "claw_lag_C50_minus_P50_s"), ("爪 C の最後の 1 s の増えの割合", "claw_C_share_last_1s"),
                  ("爪 C が 0.5 の時の H/Hf", "claw_H_over_Hf_at_C50")):
        d = s[k]
        if d.get("n", 0) == 0:
            L.append("| %s | — | — | — | — | — |" % ja)
        else:
            L.append("| %s（%d 行） | %.3f | %.3f | %.3f | %.3f | %.3f |" % (ja, d["n"], d["min"], d["p10"], d["median"], d["p90"], d["max"]))
    L.append("")
    L.append("T1 を全部満たす行：%d / %d（伸び出しの始まり %d・増え %d・単調 %d・台なし %d・最高点 %d）。厳しい読み（記録）を満たす行：%d（伸びの始まり %d・停滞なし %d・台の前に半分 %d）。T2（%s）を満たす行：%d / 判定した %d 行。伸び出しのない行：%s。" % (
        s["T1_pass_rows"], s["n_rows"], s["T1_sub_pass_rows"]["ext_start"], s["T1_sub_pass_rows"]["gain"], s["T1_sub_pass_rows"]["monotone"],
        s["T1_sub_pass_rows"]["no_plateau"], s["T1_sub_pass_rows"]["hmax_at_tstar"], s["T1_strict_pass_rows"],
        s["T1_strict_sub_pass_rows"]["grow_start"], s["T1_strict_sub_pass_rows"]["no_stall"], s["T1_strict_sub_pass_rows"]["lip_half_before_plateau"],
        rep["primary_claw"], s["T2_pass_rows"], s["T2_evaluated_rows"], s["rows_without_ext"] or "なし"))
    L.append("")
    L.append("## 読み方（この検査器の約束）")
    L.append("")
    for x in rep["readings_ja"]:
        L.append("- " + x)
    L.append("")
    L.append("包みの約束の確認（ds27_gates.Package）：" + "、".join("%s %s" % (c["item_ja"], "可" if c["ok"] else "**否**") for c in rep["package"]["interface"]))
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description="設計28修正01 Q13：唇の伸び出しと頂の上昇の重なりの検査器")
    ap.add_argument("--package", required=True)
    ap.add_argument("--tw-default", default=os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json"))
    ap.add_argument("--tw-alt", default=os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_alt.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None)
    ap.add_argument("--evidence", default=None, help="時系列と全行の詳細を除いた小さい要約（.json と .md と図）を書く場所")
    ap.add_argument("--no-fig", action="store_true")
    a = ap.parse_args()
    run(a.package, a.tw_default, a.tw_alt, a.out, label=a.label, evidence=a.evidence, fig=not a.no_fig)


if __name__ == "__main__":
    main()
