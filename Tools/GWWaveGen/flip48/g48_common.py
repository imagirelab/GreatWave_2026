# -*- coding: utf-8 -*-
"""FLIP48：道具が共に使う物（numpy だけ。hython からも py -3.10 からも読む）。
2026-10-15 FLIP46 の g46_common.py（Tools/GWWaveGen/flip46、変えていない）を読み込んで使い、FLIP48 の分だけ上書きした（flip46 の
ファイルは一つも書き換えない。FLIP46 の計算が走っている間も読むだけ）。
計画：Docs/Progress/FLIP48_3D_Peak_Setup_ja.md（A 字の盛り上がり：H0/h0 0.3 の Tanaka の孤立波を、真ん中の断面が 1:10 で水深 1.7 m の棚へ
上る GG06 型の sech² の尾根に当てる）。

座標は FLIP46 と同じ（計画の x＝波の進む向き・x = 0 が上流の壁、y＝横・y = 0 が対称の面、z＝上・静かな水面 0、平らな海底 −17 m。
Houdini の中は上が y・横が z。Houdini = 計画 + o）。

FLIP46 から変えた所：
  - 置き場所（flip48・Build/FLIP48・Houdini/FLIP48/g48_tank.hiplc）
  - 定数（孤立波 H0/h0 0.3、頂 x0 107 m、尾根の始まり 143 m、真ん中の勾配 1:10、棚の水深 1.7 m = 0.1 h0、箱の長さ 360 m）
  - 海底の式 bed_z に棚（shelf_h）を足した：水深 = max(shelf_h, h0 − max(x − x_toe, 0) sech²(k y/h0)/s)。shelf_h 0 なら g46_common.bed_z と同じ
2026-10-15 R3 の試し（Unity/Build/FLIP48/plan/campaign_R3_judge.json の queue。凍らせた物は plan/plan_R3_frozen.json）のために足した所
（どれも選びで、既定は「無し」。既定のままなら R0・R1・R2b の海底と 1 bit も違わない：g48_cfg.py check が確かめる）：
  - 尾根の k の先細り k(x) = k + (k_end − k)·clip((x − xk1)/(xk2 − xk1), 0, 1)（k_end None で無し。勾配に dk/dx の項）
  - 横の遠くの深い溝：w = ½(1 + tanh((|y| − ch_y0)/ch_w))·clip((x − ch_x0)/ch_lx, 0, 1)、水深 ← 水深(1 − w) + max(水深, ch_h)·w（ch_h 0 で無し）
  - 真ん中の断面の段（G0c・R3L）：上り R(x) を 1:s1 で水深 h0 − shelf_h − dL まで、1:s2 で dL、また 1:s1（s1 0 で無し。無しなら R = (x − x_toe)/s）
    水深 = max(shelf_h, h0 − R(x) sech²(k(x) y/h0))、その後に溝
  - 深い箱 box48（g46_common.box は箱の底 −17 m・高さ 34 m が定数なので、底 zb を選べる包みを足した。上の端は +17 m のまま）
  - 谷のある波（g48_nwave.py）の置き場所と既定（β 0.12、d = 1.6/k_s）
"""
import os, sys, math, hashlib

sys.dont_write_bytecode = True
TOOLS46 = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46"
if TOOLS46 not in sys.path:
    sys.path.append(TOOLS46)          # flip46 は後ろに足す（flip48 の名前が先に見つかるように）
import g46_common as G46               # noqa: E402  元（変えない）
from g46_common import (REPO, HY, FFMPEG, G, H0, TS, FPS, Z_BOTTOM, H_BOX, PLAN_DP, SMOKE_ONLY_DP,   # noqa: E402,F401
                        is_binary_exact, check_dp, sha256_file, rup, box, frames_for, t_of_frame,
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb)

TOOLS = REPO + "/Tools/GWWaveGen/flip48"
B48 = REPO + "/Unity/Build/FLIP48"
B46 = B48                      # 写した g46_run・g46_chain の中の GC.B46 が FLIP48 を指すように（読み替えの名前。FLIP46 の置き場所ではない）
B46_REAL = G46.B46             # 本当の FLIP46 の置き場所（読むだけ）
HIP = REPO + "/Houdini/FLIP48/g48_tank.hiplc"
SOL_DIR = B48 + "/solitary"

# ------------------------------------------------------------------ 定数（理由は FLIP48_3D_Peak_Setup_ja.md §2）
A0 = 0.3                       # 孤立波 H0/h0（0.6 では横も砕ける寸前で、真ん中だけ高くする余地がない【測定 P05】）
X0_CREST = 107.0               # 初めの頂の x（m）。尾根の始まりの 36 m 前（GG06 は始まりの 9.5 m 後ろ）
RIDGE_X0 = 143.0               # 尾根の始まり x_toe（m）
RIDGE_S = 10.0                 # 真ん中の断面の勾配 1:10（FLIP47 の S2）
RIDGE_K = 0.35                 # sech²(k y/h0) の k（R1。R0 の板は 0）
SHELF_H = 1.7                  # 棚の水深（m）= 0.1 h0（FLIP47 S2 の 0.1 h0）
LX = 360.0                     # 箱の長さ（m）
W_MAIN = 85.0                  # 3D の半幅（m）。y = 85 m は壁 → 尾根が 170 m ごとに並ぶのと同じ
W_STRIP = 6.0                  # 準 2D の板の半幅（m）
SHORE_X = RIDGE_X0 + (H0 - SHELF_H) * RIDGE_S     # 296 m：真ん中の断面が棚に着く x
SOL_DEFAULT = SOL_DIR + "/tanaka_a0p3_x107.npz"
SOL_TANAKA = SOL_DEFAULT       # g46 の名前の読み替え（FLIP46 の a0.6 の表を使わないように）
GN_PLACEHOLDER = None

# flip48 の計算が読み込む flip46 の道具（run.json に SHA-256 を残す。FLIP46 側が書き換えられた時に分かるように）
IMPORTED_46 = ("g46_common.py", "g46_online.py", "g46_ckpt.py", "g46_analyze.py", "g46_video.py", "g46_solitary.py")


def sol_path(a_over_h, x0=X0_CREST):
    return SOL_DIR + "/tanaka_a%s_x%g.npz" % (("%g" % a_over_h).replace(".", "p"), x0)


def tag(v):
    return ("%g" % v).replace(".", "p")


# ------------------------------------------------------------------ R3 の試しの既定（campaign_R3_judge.json の queue。どれも選んだ形【選び】）
TAPER_R3 = dict(k_end=1.0, xk1=240.0, xk2=296.0)          # k 0.35 → 1.0 を x 240〜296 m で（尾根の先を細く）
CHANNEL_R3 = dict(ch_y0=55.0, ch_w=4.0, ch_h=25.0, ch_x0=150.0, ch_lx=40.0)   # |y| ≳ 55 m を水深 25 m に（x 150〜190 m で入る）
LEDGE_G0C = dict(s1=11.2, dL=2.8, s2=4.0)                  # 1:11.2 で水深 4.5 m（x 283.0）、1:4 の段 2.8 m で棚 1.7 m（x 294.2）
ZB_DEEP = -25.0                                            # 溝のある箱の底（平らな所の海底ではない。底の下げ floor_pad 2 格子でさらに下）
Z_TOP = Z_BOTTOM + H_BOX                                   # 箱の上の端 +17 m（g46_common.box と同じ。深い箱でも変えない）
C0_LIN = math.sqrt(G * H0)                                 # 線形の長い波の速さ √(g h0) = 12.91 m/s（谷の流速 u_t = c0 η_t/(h0 + η)）【計算】


def kappa_gn(a_over_h, h0=H0):
    """GN（sech²）の孤立波の κ = √(3a/(4 h0²(h0 + a)))（1/m）。A 0.3 で 0.024472 /m（判定の k_s 0.02447）【計算】。"""
    a = a_over_h * h0
    return math.sqrt(3.0 * a / (4.0 * h0 * h0 * (h0 + a)))


KS_R3 = kappa_gn(0.3)                                      # 谷の幅 k_s（β・A によらず固定。1 本で 1 つだけ変えるため【選び】）
BETA_R3 = 0.12                                             # 谷の深さ β（谷 = β × 頂 a）【選び】
DK_R3 = 1.6                                                # 谷の中心の位置 d = DK/k_s = 65.4 m（頂の前）【選び】


def nwave_path(a_over_h=A0, beta=BETA_R3, dk=DK_R3, x0=X0_CREST):
    """谷のある波の表（g48_nwave.py が書く）：solitary/nwave_a0p3_b0p12_d1p6_x107.npz の形。"""
    return SOL_DIR + "/nwave_a%s_b%s_d%s_x%g.npz" % (tag(a_over_h), tag(beta), tag(dk), x0)


# ------------------------------------------------------------------ 深い箱（g46_common.box の包み）
def box48(dp, Lx=LX, W=W_MAIN, x0=0.0, zb=Z_BOTTOM, floor_pad=0, side_pad=0):
    """g46_common.box と同じ箱を、底 zb（既定 −17 m）から上の端 Z_TOP（+17 m）までにする。zb = −17 m なら g46_common.box と全部同じ
    （g48_cfg.py check が確かめる）。高さ Hz = Z_TOP − zb を格子の倍数に切り上げ、ずらし oy = (½ 格子 − zb) mod 格子。
    zb −25 m・格子 1 m（粒子 0.5 m）・2 m（粒子 1.0 m）では oy は −17 m の時と同じ（8 m が格子の倍数）。粒子の段 zb + (k + ½)dp も同じ並び。"""
    b = box(dp, Lx=Lx, W=W, x0=x0, floor_pad=floor_pad, side_pad=side_pad)
    zb = float(zb)
    if zb == float(Z_BOTTOM):
        return b
    vox = b["vox"]
    Hz, ny = rup(Z_TOP - zb, vox)
    b.update(z_bottom=zb, z_top=zb + Hz, Hz=Hz, z_floor=zb - int(floor_pad) * vox)
    b["cells"] = [b["cells"][0], b["cells"][1], ny + int(floor_pad)]
    b["oy"] = (0.5 * vox - zb) % vox
    for k_ in ("z_top", "Hz", "oy"):
        if not is_binary_exact(abs(b[k_]) if b[k_] != 0 else 1.0):
            raise ValueError("箱の %s = %r が 2 進で割り切れない" % (k_, b[k_]))
    return b


# ------------------------------------------------------------------ 海底（numpy。VEX の bedy・bedgrad と同じ式：g48_tanklib.py）
BED_EXTRA_DEFAULTS = dict(k_end=None, xk1=240.0, xk2=296.0, ch_y0=55.0, ch_w=4.0, ch_h=0.0, ch_x0=150.0, ch_lx=40.0, s1=0.0, dL=0.0, s2=0.0)


def _k_of_x(x, k, k_end, xk1, xk2):
    """尾根の k(x) と dk/dx（先細りが無ければ k そのもの・0）。"""
    import numpy as np
    if k_end is None or k_end < 0:
        return k, 0.0
    r = (x - xk1) / (xk2 - xk1)
    kk = k + (k_end - k) * np.clip(r, 0.0, 1.0)
    dk = np.where((r > 0.0) & (r < 1.0), (k_end - k) / (xk2 - xk1), 0.0)
    return kk, dk


def _rise(x, x_toe, s, h0, shelf_h, s1, dL, s2):
    """真ん中の断面の上り R(x)（m）と R'(x)。s1 ≤ 0 なら R = max(x − x_toe, 0)/s。段：u = x − x_toe、uL = (h0 − shelf_h − dL) s1 まで 1:s1、
    次の dL·s2 を 1:s2、その先 1:s1（VEX の rise と同じ。継ぎ目は左の傾き）。"""
    import numpy as np
    u = x - x_toe
    if not (s1 and s1 > 0):
        return np.maximum(u, 0.0) / s, np.where(u > 0.0, 1.0 / s, 0.0)
    uL = (h0 - shelf_h - dL) * s1
    R = np.where(u <= 0.0, 0.0, np.where(u <= uL, u / s1, np.where(u <= uL + dL * s2, uL / s1 + (u - uL) / s2, uL / s1 + dL + (u - uL - dL * s2) / s1)))
    Rp = np.where(u <= 0.0, 0.0, np.where(u <= uL, 1.0 / s1, np.where(u <= uL + dL * s2, 1.0 / s2, 1.0 / s1)))
    return R, Rp


def _channel_w(x, y, ch_y0, ch_w, ch_x0, ch_lx):
    """溝の重み w と dw/dx・dw/dy。"""
    import numpy as np
    q = (np.abs(y) - ch_y0) / ch_w
    tq = np.tanh(q)
    g = 0.5 * (1.0 + tq)
    r = (x - ch_x0) / ch_lx
    rc = np.clip(r, 0.0, 1.0)
    rp = np.where((r > 0.0) & (r < 1.0), 1.0 / ch_lx, 0.0)
    return g * rc, g * rp, 0.5 * (1.0 - tq * tq) / ch_w * np.sign(y) * rc


def _plain(k_end, s1):
    return (k_end is None or k_end < 0) and not (s1 and s1 > 0)


def bed_z(x, y_lat=0.0, k=RIDGE_K, x_toe=RIDGE_X0, s=RIDGE_S, h0=H0, on=True, shelf_h=SHELF_H,
          k_end=None, xk1=240.0, xk2=296.0, ch_y0=55.0, ch_w=4.0, ch_h=0.0, ch_x0=150.0, ch_lx=40.0, s1=0.0, dL=0.0, s2=0.0):
    """海底の高さ（静かな水面 0、上向き）。x < x_toe は −h0。先は −max(shelf_h, h0 − (x − x_toe) sech²(k y/h0)/s)。
    shelf_h ≤ 0 なら g46_common.bed_z（GG06 の尾根）と同じ。y について偶（cosh）。
    R3 の選び（既定は無し、無しなら前と同じ式を同じ順に計算する）：k_end（先細り k(x)）、ch_h > 0（横の遠くの溝）、s1 > 0（段 s1・dL・s2）。"""
    import numpy as np
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    if not on:
        return np.full(np.broadcast(x, y).shape, -float(h0))
    if _plain(k_end, s1):
        sh = 1.0 / np.cosh(k * y / h0)
        dep = h0 - np.maximum(x - x_toe, 0.0) * sh * sh / s
    else:
        kk, _ = _k_of_x(x, k, k_end, xk1, xk2)
        sh = 1.0 / np.cosh(kk * y / h0)
        R, _ = _rise(x, x_toe, s, h0, shelf_h, s1, dL, s2)
        dep = h0 - R * sh * sh
    if shelf_h is not None and shelf_h > 0:
        dep = np.maximum(dep, shelf_h)
    if ch_h and ch_h > 0:
        w, _, _ = _channel_w(x, y, ch_y0, ch_w, ch_x0, ch_lx)
        dep = dep * (1.0 - w) + np.maximum(dep, ch_h) * w
    return -dep


def bed_grad(x, y_lat=0.0, k=RIDGE_K, x_toe=RIDGE_X0, s=RIDGE_S, h0=H0, on=True, shelf_h=SHELF_H,
             k_end=None, xk1=240.0, xk2=296.0, ch_y0=55.0, ch_w=4.0, ch_h=0.0, ch_x0=150.0, ch_lx=40.0, s1=0.0, dL=0.0, s2=0.0):
    """d bed_z/dx・d bed_z/dy（VEX の bedgrad と同じ。棚の上と x ≤ x_toe は 0。先細りの dk/dx の項・段の R'・溝の dw を含む）。"""
    import numpy as np
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    x, y = np.broadcast_arrays(x, y)
    gx = np.zeros(x.shape); gy = np.zeros(x.shape)
    if not on:
        return gx, gy
    if _plain(k_end, s1):
        a = k * y / h0
        sh = 1.0 / np.cosh(a)
        dep = h0 - np.maximum(x - x_toe, 0.0) * sh * sh / s
        m = x > x_toe
        if shelf_h is not None and shelf_h > 0:
            m &= dep > shelf_h
        gx = np.where(m, sh * sh / s, 0.0)
        gy = np.where(m, (x - x_toe) / s * (-2.0 * sh * sh * np.tanh(a) * k / h0), 0.0)
    else:
        kk, dk = _k_of_x(x, k, k_end, xk1, xk2)
        a = kk * y / h0
        sh = 1.0 / np.cosh(a)
        S = sh * sh
        th = np.tanh(a)
        R, Rp = _rise(x, x_toe, s, h0, shelf_h, s1, dL, s2)
        dep = h0 - R * S
        m = x > x_toe
        if shelf_h is not None and shelf_h > 0:
            m &= dep > shelf_h
        # 水深 d = h0 − R S、∂d/∂x = −(R' S + R ∂S/∂x)、∂S/∂x = −2 S tanh(a) (dk/dx) y/h0、∂d/∂y = 2 R S tanh(a) k/h0。勾配 = −∂d
        gx = np.where(m, Rp * S - 2.0 * R * S * th * dk * y / h0, 0.0)
        gy = np.where(m, -2.0 * R * S * th * kk / h0, 0.0)
        if shelf_h is not None and shelf_h > 0:
            dep = np.maximum(dep, shelf_h)
    if ch_h and ch_h > 0:
        if _plain(k_end, s1):
            dep = np.maximum(dep, shelf_h) if (shelf_h is not None and shelf_h > 0) else dep
        w, wx, wy = _channel_w(x, y, ch_y0, ch_w, ch_x0, ch_lx)
        ddx, ddy = -gx, -gy                                   # 水深の微分
        deep = dep > ch_h
        D2 = np.maximum(dep, ch_h)
        nx = ddx * (1.0 - w) + np.where(deep, ddx, 0.0) * w + (D2 - dep) * wx
        ny = ddy * (1.0 - w) + np.where(deep, ddy, 0.0) * w + (D2 - dep) * wy
        gx, gy = -nx, -ny
    return gx, gy


def bed_sdf(x, z, y_lat, **spec):
    """VEX の bedsdf_out と同じ近似の SDF（海底の外で正）：(z − bed)/√(1 + |∇bed|²)。side_pad は使わない。"""
    import numpy as np
    gx, gy = bed_grad(x, y_lat, **spec)
    return (np.asarray(z, float) - bed_z(x, y_lat, **spec)) / np.sqrt(1.0 + gx * gx + gy * gy)


def _f_or(v, d):
    return d if v is None else float(v)


def bed_spec(cfg=None, parms=None):
    """cfg['bed']（あれば先）か parms（CTRL の名前 ridge_on・ridge_x0・ridge_k・ridge_s・h0・shelf_h、R3 の ridge_kend・ridge_xk1・ridge_xk2・
    ch_h・ch_y0・ch_w・ch_x0・ch_lx・ledge_s1・ledge_dl・ledge_s2）から bed_z の引数。R3 の物がなければ既定（無し）。
    cfg['bed'] の kind：ridge_shelf（R0〜R2）・spur_channel（先細り＋溝）・ridge_shelf_ledge（段）・spur_channel_ledge（R3L）。どれも同じ鍵で読む。"""
    b = (cfg or {}).get("bed") if isinstance((cfg or {}).get("bed"), dict) else None
    P = parms if parms is not None else ((cfg or {}).get("parms") or {})
    D = BED_EXTRA_DEFAULTS
    if b:
        ke = b.get("k_end")
        return dict(k=float(b["k"]), x_toe=float(b["x_toe"]), s=float(b["s"]), h0=float(b.get("h0", H0)),
                    on=bool(b.get("on", True)), shelf_h=float(b.get("h_sh", b.get("shelf_h", 0.0))),
                    k_end=(None if ke is None or float(ke) < 0 else float(ke)), xk1=_f_or(b.get("xk1"), D["xk1"]), xk2=_f_or(b.get("xk2"), D["xk2"]),
                    ch_y0=_f_or(b.get("ch_y0"), D["ch_y0"]), ch_w=_f_or(b.get("ch_w"), D["ch_w"]), ch_h=_f_or(b.get("ch_h"), D["ch_h"]),
                    ch_x0=_f_or(b.get("ch_x0"), D["ch_x0"]), ch_lx=_f_or(b.get("ch_lx"), D["ch_lx"]),
                    s1=_f_or(b.get("s1"), D["s1"]), dL=_f_or(b.get("dL"), D["dL"]), s2=_f_or(b.get("s2"), D["s2"]))
    ke = float(P.get("ridge_kend", -1.0))
    return dict(k=float(P.get("ridge_k", RIDGE_K)), x_toe=float(P.get("ridge_x0", RIDGE_X0)), s=float(P.get("ridge_s", RIDGE_S)),
                h0=float(P.get("h0", H0)), on=float(P.get("ridge_on", 1.0)) > 0.5, shelf_h=float(P.get("shelf_h", 0.0)),
                k_end=(None if ke < 0 else ke), xk1=float(P.get("ridge_xk1", D["xk1"])), xk2=float(P.get("ridge_xk2", D["xk2"])),
                ch_y0=float(P.get("ch_y0", D["ch_y0"])), ch_w=float(P.get("ch_w", D["ch_w"])), ch_h=float(P.get("ch_h", D["ch_h"])),
                ch_x0=float(P.get("ch_x0", D["ch_x0"])), ch_lx=float(P.get("ch_lx", D["ch_lx"])),
                s1=float(P.get("ledge_s1", D["s1"])), dL=float(P.get("ledge_dl", D["dL"])), s2=float(P.get("ledge_s2", D["s2"])))


def bed_parms(spec):
    """bed_z の引数 → CTRL の parms の名前（R3 の選びの分。無しは ridge_kend −1・ch_h 0・ledge_s1 0）。"""
    return dict(ridge_kend=(-1.0 if spec.get("k_end") is None else float(spec["k_end"])), ridge_xk1=float(spec.get("xk1", 240.0)),
                ridge_xk2=float(spec.get("xk2", 296.0)), ch_h=float(spec.get("ch_h", 0.0)), ch_y0=float(spec.get("ch_y0", 55.0)),
                ch_w=float(spec.get("ch_w", 4.0)), ch_x0=float(spec.get("ch_x0", 150.0)), ch_lx=float(spec.get("ch_lx", 40.0)),
                ledge_s1=float(spec.get("s1", 0.0)), ledge_dl=float(spec.get("dL", 0.0)), ledge_s2=float(spec.get("s2", 0.0)))


def bed_kind(spec):
    taper = spec.get("k_end") is not None
    ch = (spec.get("ch_h") or 0.0) > 0
    ledge = (spec.get("s1") or 0.0) > 0
    if (taper or ch) and ledge:
        return "spur_channel_ledge"
    if taper or ch:
        return "spur_channel"
    if ledge:
        return "ridge_shelf_ledge"
    return "ridge_shelf"


def bed_formula(spec):
    """cfg に書く海底の式（文字）。"""
    f = "z_b = -depth; d0 = h0 - R(x)*sech^2(k(x)*y/h0); depth = max(h_sh, d0)"
    f += "; R(x) = max(x - x_toe, 0)/s" if not (spec.get("s1") or 0) > 0 else \
        "; R(x) piecewise: 1:s1 to depth h0-h_sh-dL (x_L = x_toe + (h0-h_sh-dL)*s1), 1:s2 for dL, then 1:s1"
    f += "; k(x) = k" if spec.get("k_end") is None else "; k(x) = k + (k_end-k)*clip((x-xk1)/(xk2-xk1),0,1)"
    if (spec.get("ch_h") or 0) > 0:
        f += "; w = 0.5*(1+tanh((|y|-ch_y0)/ch_w))*clip((x-ch_x0)/ch_lx,0,1); depth <- depth*(1-w) + max(depth,ch_h)*w"
    return f


def bed_from(spec):
    return lambda x, y=0.0: bed_z(x, y, **spec)


def shelf_x(spec, y=0.0):
    """y の行で棚（水深 shelf_h）に着く x（届かなければ inf）。先細り・段がなければ式で、あれば 0.01 m ごとに探す（溝は棚の行を変えない所で使う）。"""
    if spec["shelf_h"] <= 0:
        return float("inf")
    if _plain(spec.get("k_end"), spec.get("s1")):
        sh2 = 1.0 / math.cosh(spec["k"] * y / spec["h0"]) ** 2
        if sh2 <= 0:
            return float("inf")
        return spec["x_toe"] + (spec["h0"] - spec["shelf_h"]) * spec["s"] / sh2
    import numpy as np
    xs = np.arange(spec["x_toe"], spec["x_toe"] + 2000.0, 0.01)
    sp = dict(spec, ch_h=0.0)
    d = -bed_z(xs, y, **sp)
    i = np.where(d <= spec["shelf_h"] + 1e-9)[0]
    return float(xs[i[0]]) if len(i) else float("inf")


# ------------------------------------------------------------------ 記録の印
def module_shas():
    """flip48 の計算が読み込む道具の SHA-256（頭 16 字）。"""
    out = {}
    for nm in IMPORTED_46:
        p = os.path.join(TOOLS46, nm)
        out["flip46/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g48_common.py", "g48_tanklib.py", "g48_run.py", "g48_build_tank.py"):
        p = os.path.join(TOOLS, nm)
        out["flip48/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    return out


def guard_out48(path):
    """FLIP48 の置き場所の外には書かない。"""
    o = os.path.abspath(path).replace("\\", "/")
    if not (o.lower() + "/").startswith(B48.lower() + "/"):
        raise SystemExit("出力の置き場所 %s は Unity/Build/FLIP48 の外。書かない" % o)
    os.makedirs(o, exist_ok=True)
    return o
