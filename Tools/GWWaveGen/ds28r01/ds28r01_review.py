# -*- coding: utf-8 -*-
"""設計28修正01 のレビュー対応：記録のみの測り直し（生成器・パッケージ・関門の判定は変えない）。

測るもの（設計28修正01 の既定 art_on と、設計28 の既定 art_on。どちらも Git 対象外のパッケージを読むだけ）：
  1. P18 を固定の高さで読む：巻きの行ごとに、内壁の 0.5·Hf・0.3·Hf の点（Hf＝その行の t* の頂の高さ。時刻によらず固定）の、
     波の枠（パッケージの局所座標）での後ろへの戻り（それまでの最大 − 今）。起点は較正の噴流の始まり（関門 P18 と同じ）と、
     前面が鉛直になった時刻（φ ≥ 90°）。関門 P18（ds28_gates_extra.py）の点は 0.5·H(τ)・0.3·H(τ) で、頂が上がると点が前面を上る。
     照合のため、同じループで関門と同じ動く点の値も出す。
  2. 唇先（K* の唇先の列）と唇の前の端（0.3H より上の前の部分の a の最大）の位置を、設計28 と波の枠で比べる（τ −3.0〜0、行 159・192）。
  3. 画面の頂の上昇：3 つの時間曲線（設計28 の既定＝ds27、設計28修正01 の既定、代案＝実時間）で、頂の高さの画面の速さ（m/s）・加速度、
     H/H* が 0.3・0.5 から 0.8 へ着く画面の時間。物理の時刻の上昇の速さ（t* の速さを含む）。
  4. 見える唇の始まり：張り出し Lo/H が 0.05・0.10・0.15 に着く画面の時刻と、その時の H/H*、その後の頂の増え。
     H と Lo は生成器から独立の検査器 ds28r01_overlap.py の測定（<out>_measure.npz、60 Hz）を使う。
  5. 図：画面の時刻の H/H* と Lo/H（日本語の証拠用と、利用者の預覧用の中国語）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_review.py [--out Unity/Build/Design/28R01/review] [--fig-zh <中国語の図の出力>]
numpy と Pillow だけを使う。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds28"))
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as DX  # noqa: E402

B = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
PKG = {"ds28r01": os.path.join(B, "art_on"), "ds28": os.path.join(REPO, "Unity", "Build", "Design", "28", "art_on")}
MEAS = {"ds28r01": os.path.join(B, "overlap", "ds28r01_art_on_measure.npz"), "ds28": os.path.join(B, "overlap", "ds28_art_on_measure.npz")}
WARPS = {"ds28_default": os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json"),
         "ds28r01_default": os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01", "timewarp_default.json"),
         "alt": os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_alt.json")}
ROWS = {"main_159": 159, "peak_192": 192}
HZ = 60
FIXED = (0.5, 0.3)
LIM = 0.3


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")


def r3(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


# ---------------------------------------------------------------- 1・2：パッケージを読む
def package_series(ks, pk, t_start=-4.6):
    tau0 = max(float(pk.knots[0]), t_start)
    K = int(np.floor(-tau0 * HZ + 1e-6))
    taus = -np.arange(K, -1, -1) / HZ
    nv = ks.nv
    rows = np.arange(nv)
    tipc = np.where(ks.tip_col >= 0, ks.tip_col, 0)
    S = {k: np.full((len(taus), nv), np.nan) for k in ("H", "phi", "crest", "w5", "w3", "tip_a", "tip_y", "front_a")}
    Xl = pk.local(0.0) + ks.O
    A, Y, _ = ks.section(Xl)
    Hf = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)["H"]
    for f in FIXED:
        S["f%02d" % int(f * 10)] = np.full((len(taus), nv), np.nan)
    for k, tau in enumerate(taus):
        Xl = pk.local(float(tau)) + ks.O
        A, Y, _ = ks.section(Xl)
        rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
        S["H"][k], S["phi"][k], S["crest"][k] = rm["H"], rm["phi"], rm["ca"]
        S["w5"][k] = DX.front_cross(A, Y, rm["cj"], rm["H"], 0.5, ks.j_E)
        S["w3"][k] = DX.front_cross(A, Y, rm["cj"], rm["H"], 0.3, ks.j_E)
        for f in FIXED:
            S["f%02d" % int(f * 10)][k] = DX.front_cross(A, Y, rm["cj"], Hf, f, ks.j_E)
        S["tip_a"][k], S["tip_y"][k] = A[rows, tipc], Y[rows, tipc]
        cols = np.arange(ks.nu)[None, :]
        abv = (cols >= rm["cj"][:, None]) & (cols <= ks.j_E) & (Y > 0.3 * rm["H"][:, None])
        S["front_a"][k] = np.where(abv, A, -np.inf).max(1)
    S["taus"], S["Hf"] = taus, Hf
    return S


def p18_readings(ks, S, cond):
    taus = S["taus"]
    Tc = DX.calib_onset(ks, cond)
    out = {}
    for start in ("calibrated_onset", "face_vertical"):
        for key in ("f05", "f03", "w5", "w3", "tip_a"):
            worst, rows_over, per = (0.0, None, None), [], {}
            for r in ks.curled_idx:
                if start == "calibrated_onset":
                    k0 = int(np.argmin(np.abs(taus + Tc[r])))
                else:
                    kk = np.nonzero(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0)[0]
                    if not len(kk):
                        continue
                    k0 = int(kk[0])
                v, j = DX.retreat(S[key][k0:, r])
                if v is None:
                    continue
                per[int(r)] = (v, k0, k0 + j)
                if v > worst[0]:
                    worst = (v, int(r), float(taus[k0 + j]))
                if v > LIM:
                    rows_over.append(int(r))
            ent = dict(worst_m=r3(worst[0]), worst_row=worst[1], worst_tau=r3(worst[2]), rows_over_0p3m=len(rows_over), curled_rows=int(len(ks.curled_idx)))
            for name, r in ROWS.items():
                if r in per:
                    v, k0, kj = per[r]
                    seg = S[key][k0:kj + 1, r]
                    km = k0 + int(np.nanargmax(seg))
                    ent[name] = dict(retreat_m=r3(v), start_tau=r3(taus[k0]), a_at_start_m=r3(S[key][k0, r]), max_a_m=r3(S[key][km, r]), max_tau=r3(taus[km]),
                                     a_at_worst_m=r3(S[key][kj, r]), worst_tau=r3(taus[kj]),
                                     crest_a_at_max_m=r3(S["crest"][km, r]), crest_a_at_worst_m=r3(S["crest"][kj, r]),
                                     H_over_Hf_at_start=r3(S["H"][k0, r] / S["Hf"][r]), H_over_Hf_at_worst=r3(S["H"][kj, r] / S["Hf"][r]))
            out["%s/%s" % (start, key)] = ent
    return out


def lip_compare(Sa, Sb):
    """設計28修正01（Sa）と設計28（Sb）の唇先・唇の前の端の位置の差（波の枠、τ −3.0〜0）。"""
    taus = Sa["taus"]
    m = taus >= -3.0 - 1e-9
    out = {}
    for name, r in ROWS.items():
        d = {}
        for key in ("tip_a", "tip_y", "front_a", "crest"):
            x = np.abs(Sa[key][m, r] - Sb[key][m, r])
            d[key + "_maxdiff_m"] = r3(np.nanmax(x))
        for tq in (-3.0, -2.8, -2.4, -2.0, -1.5, -1.0, -0.5, 0.0):
            k = int(np.argmin(np.abs(taus - tq)))
            d["at_%+.1f" % tq] = dict(tip_a=[r3(Sa["tip_a"][k, r]), r3(Sb["tip_a"][k, r])], front_a=[r3(Sa["front_a"][k, r]), r3(Sb["front_a"][k, r])],
                                      crest_a=[r3(Sa["crest"][k, r]), r3(Sb["crest"][k, r])], H=[r3(Sa["H"][k, r]), r3(Sb["H"][k, r])])
        out[name] = d
    return dict(note_ja="[設計28修正01, 設計28] の組。波の枠（パッケージの局所座標を K* の断面へ）の a（前が +）。tip は K* の唇先の列の点、front は 0.3H より上の前の部分の a の最大（張り出しの定義 A の前の端）", rows=out)


def lip_tip_motion(ks, S, cond, warp_by_name):
    """唇先（K* の唇先の列）が較正の噴流の始まりの位置から波の枠で前へ 0.5 m・1.0 m・2.0 m 出る τ と、その時の H/H*、各時間曲線の画面の時刻。
    側面の輪郭で目に見える唇の動きの目安（Lo の始まりは内壁のえぐりで、輪郭ではほかの行に隠れる）。"""
    taus = S["taus"]
    Tc = DX.calib_onset(ks, cond)
    out = {}
    for name, r in ROWS.items():
        k0 = int(np.argmin(np.abs(taus + Tc[r])))
        a0 = S["tip_a"][k0, r]
        d = dict(onset_tau=r3(taus[k0]), tip_a_at_onset_m=r3(a0))
        for dx in (0.5, 1.0, 2.0):
            m = (np.arange(len(taus)) >= k0) & (S["tip_a"][:, r] - a0 >= dx)
            if not m.any():
                d["forward_%.1fm" % dx] = None
                continue
            k = int(np.argmax(m))
            e = dict(tau=r3(taus[k]), H_over_Hf=r3(S["H"][k, r] / S["Hf"][r]), crest_gain_after_over_Hf=r3(1.0 - S["H"][k, r] / S["Hf"][r]))
            for wn, (wt, wtau) in warp_by_name.items():
                kk = int(np.argmax(wtau >= -1e-9)) + 1
                e["t_" + wn] = r3(float(np.interp(taus[k], wtau[:kk], wt[:kk])), 2)
            d["forward_%.1fm" % dx] = e
        out[name] = d
    return out


# ---------------------------------------------------------------- 3・4：画面の時刻
def load_warp(p):
    J = json.load(open(p, encoding="utf-8"))
    return np.asarray(J["t"], float), np.asarray(J["tau"], float)


def smooth(x, n=5):
    k = np.ones(n) / n
    xp = np.pad(x, (n // 2, n // 2), mode="edge")
    return np.convolve(xp, k, mode="valid")


def screen_series(meas, row, warp):
    z = np.load(meas)
    rows = list(z["rows"])
    i = rows.index(row)
    tq = z["taus"]
    H, Lo = z["H"][:, i], z["Lo"][:, i]
    Hf = H[-1]
    dH = smooth(np.gradient(H, tq))
    t, tau = warp
    k = int(np.argmax(tau >= -1e-9))
    t, tau = t[:k + 1], tau[:k + 1]           # t* まで（保持は含めない）
    dtaudt = np.gradient(tau, t)
    h = np.interp(tau, tq, H)
    v = np.interp(tau, tq, dH) * dtaudt        # 画面の速さ m/s
    acc = np.gradient(smooth(v, 25), t)
    lo = np.interp(tau, tq, np.nan_to_num(Lo, nan=0.0))
    return dict(t=t, tau=tau, h=h / Hf, v=v, acc=acc, loh=lo / np.maximum(h, 1e-6), Hf=Hf, tq=tq, H=H, dH=dH, Lo=Lo)


def first_t(s, key, thr, after_t=0.0):
    m = (s[key] >= thr) & (s["t"] >= after_t)
    return float(s["t"][np.argmax(m)]) if m.any() else None


def lip_start_ext(s, thr):
    """Lo/H ≥ thr が t* まで続く最初の画面の時刻。"""
    ok = s["loh"] >= thr
    bad = np.nonzero(~ok)[0]
    k = 0 if not len(bad) else bad[-1] + 1
    return None if k >= len(ok) else k


def rise_summary(s):
    t, h, v = s["t"], s["h"], s["v"]
    out = {}
    for a in (0.3, 0.5):
        ta, tb = first_t(s, "h", a), first_t(s, "h", 0.8)
        out["screen_s_from_%.1f_to_0.8" % a] = r3(tb - ta, 2) if ta is not None and tb is not None else None
    for a in (0.3, 0.5, 0.8, 0.9, 0.95):
        out["t_at_H_%.2f" % a] = r3(first_t(s, "h", a), 2)
    kmax = int(np.argmax(v))
    out["max_screen_rise_mps"] = r3(v[kmax], 2)
    out["t_at_max_screen_rise"] = r3(t[kmax], 2)
    out["H_over_Hf_at_max_screen_rise"] = r3(h[kmax])
    m = h >= 0.8
    out["mean_screen_rise_after_0p8_mps"] = r3(float(np.mean(v[m])), 2) if m.any() else None
    m = (h >= 0.5) & (h < 0.8)
    out["mean_screen_rise_0p5_to_0p8_mps"] = r3(float(np.mean(v[m])), 2) if m.any() else None
    m = t >= t[-1] - 0.5
    out["screen_rise_last_0p5s_mps"] = r3(float(np.mean(v[m])), 2)
    mm = t < t[-1] - 0.6                     # t* の直前の止め（0.4 s の S）を除く
    kmin = int(np.argmin(np.where(mm, s["acc"], np.inf)))
    out["min_screen_acc_before_freeze_mps2"] = r3(s["acc"][kmin], 2)
    out["t_at_min_screen_acc"] = r3(t[kmin], 2)
    out["screen_rise_before_min_acc_mps"] = r3(float(v[max(kmin - int(0.5 * 240), 0)]), 2)
    out["screen_rise_after_min_acc_mps"] = r3(float(v[min(kmin + int(0.5 * 240), len(v) - 1)]), 2)
    out["screen_rise_at_tstar_mps"] = r3(float(v[-1]), 2)
    for thr in (0.05, 0.10, 0.15):
        k = lip_start_ext(s, thr)
        if k is None:
            out["lip_Lo_over_H_%.2f" % thr] = None
            continue
        out["lip_Lo_over_H_%.2f" % thr] = dict(t=r3(t[k], 2), tau=r3(s["tau"][k]), H_over_Hf=r3(h[k]), crest_gain_after_over_Hf=r3(1.0 - h[k]),
                                               Lo_m=r3(s["loh"][k] * h[k] * s["Hf"], 2))
    return out


def phys_summary(s):
    tq, H, dH = s["tq"], s["H"], s["dH"]
    m = (tq >= -6.0)
    k = int(np.argmax(np.where(m, dH, -np.inf)))
    out = dict(Hf_m=r3(s["Hf"], 2), max_rise_mps_after_tau_m6=r3(dH[k], 2), tau_at_max_rise=r3(tq[k], 2),
               rise_at_tstar_mps=r3((H[-1] - H[-4]) / (tq[-1] - tq[-4]), 2))
    for a, b in ((-6.0, -4.0), (-4.0, -3.0), (-3.0, -2.4), (-2.4, -1.2), (-1.2, 0.0)):
        ka, kb = int(np.argmin(np.abs(tq - a))), int(np.argmin(np.abs(tq - b)))
        out["mean_rise_mps_%+.1f_%+.1f" % (a, b)] = r3((H[kb] - H[ka]) / (tq[kb] - tq[ka]), 2)
    for a in (0.5, 0.8, 0.9):
        kk = int(np.argmax(H / s["Hf"] >= a))
        out["tau_at_H_%.1f" % a] = r3(tq[kk], 3)
    return out


# ---------------------------------------------------------------- 5：図
def fig(series, out, lang):
    zh = lang == "zh"
    F = r"C:\Windows\Fonts\msyh.ttc" if zh else r"C:\Windows\Fonts\YuGothM.ttc"
    FBd = r"C:\Windows\Fonts\msyhbd.ttc" if zh else r"C:\Windows\Fonts\YuGothB.ttc"
    f1, f2, f3 = ImageFont.truetype(FBd, 22), ImageFont.truetype(F, 17), ImageFont.truetype(F, 15)
    W, Hh = 1500, 1010
    img = Image.new("RGB", (W, Hh), (250, 250, 247))
    d = ImageDraw.Draw(img)
    title = ("浪顶高度 H/H*（实线）和唇伸出 Lo/H（细线）在画面时间上的变化（与侧面视频叠加的数值相同）" if zh else
             "画面の時刻の頂の高さ H/H*（太線）と張り出し Lo/H（細線）。3 つの組：設計28 既定／設計28修正01 既定／設計28修正01 代案（実時間）")
    d.text((20, 12), title, font=f1, fill=(20, 20, 20))
    cases = [("ds28_default", (120, 120, 120), "设计28 默认" if zh else "設計28 既定"),
             ("ds28r01_default", (200, 60, 30), "设计28修正01 默认" if zh else "設計28修正01 既定"),
             ("ds28r01_alt", (40, 90, 200), "设计28修正01 代案（实时，t* 瞬停）" if zh else "設計28修正01 代案（実時間、t* で瞬間に止める）")]
    panels = [("peak_192", "峰行（行 192）" if zh else "峰の行（行 192）"), ("main_159", "主断面（行 159）" if zh else "主断面（行 159）")]
    x0, pw, ph = 90, 1380, 380
    for pi, (row, pname) in enumerate(panels):
        y0 = 60 + pi * (ph + 70)
        d.rectangle([x0, y0, x0 + pw, y0 + ph], outline=(60, 60, 60))
        d.text((x0 + 8, y0 + 6), pname, font=f2, fill=(20, 20, 20))

        def X(t):
            return x0 + pw * t / 14.0

        def Yv(v):
            return y0 + ph - ph * v / 1.05
        for g in (0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0):
            d.line([x0, Yv(g), x0 + pw, Yv(g)], fill=(225, 225, 220))
            d.text((x0 - 40, Yv(g) - 9), "%.1f" % g, font=f3, fill=(60, 60, 60))
        for tt in range(0, 15):
            d.line([X(tt), y0 + ph, X(tt), y0 + ph + 5], fill=(60, 60, 60))
            d.text((X(tt) - 6, y0 + ph + 8), "%d" % tt, font=f3, fill=(60, 60, 60))
        for key, col, lab in cases:
            s = series[key][row]
            t, h, lo = s["t"], s["h"], s["loh"]
            pts = [(X(a), Yv(b)) for a, b in zip(t[::4], h[::4])]
            d.line(pts + [(X(14.0), Yv(h[-1]))], fill=col, width=4)
            pts = [(X(a), Yv(max(0.0, b))) for a, b in zip(t[::4], lo[::4])]
            d.line(pts, fill=col, width=1)
            k = lip_start_ext(s, 0.10)
            if k is not None:
                xx, yy = X(t[k]), Yv(h[k])
                d.ellipse([xx - 7, yy - 7, xx + 7, yy + 7], outline=col, width=3)
        d.text((x0 + pw - 60, y0 + ph + 26), "t (s)", font=f3, fill=(60, 60, 60))
    ly = 60 + 2 * (ph + 70) - 20
    for i, (key, col, lab) in enumerate(cases):
        d.line([x0 + i * 460, ly + 10, x0 + i * 460 + 40, ly + 10], fill=col, width=4)
        d.text((x0 + i * 460 + 48, ly), lab, font=f2, fill=(20, 20, 20))
    note = ("圆圈：唇伸出 Lo/H 达到 0.10 并一直保持到 t* 的时刻（肉眼大致能看出唇的时刻）。t* = 12 s（代案在 t* 瞬间停住）。"
            if zh else "丸：Lo/H が 0.10 に着き t* まで続く画面の時刻（唇が目で見えてくる目安）。t* = 12 s。値は ds28r01_overlap.py の測定（60 Hz）を各時間曲線で画面の時刻へ写した")
    d.text((x0, ly + 34), note, font=f3, fill=(60, 60, 60))
    img.save(out, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "review"))
    ap.add_argument("--evidence-fig", default=os.path.join(REPO, "Docs", "Evidence", "Design", "28R01", "fig_ds28r01_review_rise.png"))
    ap.add_argument("--fig-zh", default=None)
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    ks = DG.KStar()
    cond, _ = DG.load_conditions()
    S = {}
    for k, p in PKG.items():
        pk = DG.Package(p, ks)
        S[k] = package_series(ks, pk)
        S[k]["pos_sha256"] = pk.pos_sha
        print("[review] %s read (%.0f s)" % (k, time.time() - t0))
    rep = dict(schema="GreatWave.DS28R01.review/1", number="設計28修正01（レビュー対応、記録のみ）", tool=rel(__file__), tool_sha256=sha(__file__),
               packages={k: dict(dir=rel(PKG[k]), pos_sha256=S[k]["pos_sha256"]) for k in PKG},
               measures={k: dict(path=rel(MEAS[k]), sha256=sha(MEAS[k])) for k in MEAS},
               warps={k: dict(path=rel(p), sha256=sha(p)) for k, p in WARPS.items()})
    rep["p18_fixed_height"] = dict(
        note_ja="P18 の読み直し（記録のみ、判定は変えない）。f05・f03＝内壁の 0.5·Hf・0.3·Hf（Hf＝行の t* の頂、固定）の点、w5・w3＝関門 P18 と同じ 0.5·H(τ)・0.3·H(τ) の点、"
                "tip_a＝唇先。戻り＝その時刻までの最大 − 今（波の枠の a、前が +）。上限 0.3 m は関門 P18 と同じ",
        **{k: p18_readings(ks, S[k], cond) for k in PKG})
    rep["lip_position_vs_ds28"] = lip_compare(S["ds28r01"], S["ds28"])
    wd = {k: load_warp(p) for k, p in WARPS.items()}
    rep["lip_tip_forward"] = dict(
        note_ja="唇先が較正の噴流の始まりの位置から波の枠で前へ出る τ と画面の時刻（目に見える唇の動きの目安）。唇先の前後の位置は設計28 と同じ（lip_position_vs_ds28）なので τ は両版で同じで、違うのはその時の頂の高さと時間曲線",
        ds28r01={**lip_tip_motion(ks, S["ds28r01"], cond, {"ds28r01_default": wd["ds28r01_default"], "alt": wd["alt"]})},
        ds28={**lip_tip_motion(ks, S["ds28"], cond, {"ds28_default": wd["ds28_default"], "alt": wd["alt"]})})
    series = {}
    for key, (pkg, wk) in {"ds28_default": ("ds28", "ds28_default"), "ds28r01_default": ("ds28r01", "ds28r01_default"),
                           "ds28r01_alt": ("ds28r01", "alt"), "ds28_alt": ("ds28", "alt")}.items():
        w = load_warp(WARPS[wk])
        series[key] = {name: screen_series(MEAS[pkg], r, w) for name, r in ROWS.items()}
    rep["screen_rise"] = dict(
        note_ja="頂の高さ H（ds28r01_overlap.py の測定、60 Hz）を時間曲線で画面の時刻 t へ写した。速さは m/s（画面の時刻）、加速度は 0.1 s でならした速さの微分。"
                "lip_Lo_over_H_x は Lo/H ≥ x が t* まで続く最初の画面の時刻（0.05 は T1 の始まり、0.10・0.15 は目で見える唇の目安）",
        **{k: {name: rise_summary(s) for name, s in v.items()} for k, v in series.items()})
    rep["physical_rise"] = {k: {name: phys_summary(series[k2][name]) for name in ROWS} for k, k2 in (("ds28", "ds28_default"), ("ds28r01", "ds28r01_default"))}
    fig(series, a.evidence_fig, "ja")
    rep["figure"] = dict(path=rel(a.evidence_fig), sha256=sha(a.evidence_fig))
    if a.fig_zh:
        fig(series, a.fig_zh, "zh")
    rep["runtime_s"] = round(time.time() - t0, 1)
    out = os.path.join(a.out, "review_ds28r01.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("[review] → %s (%.0f s)" % (rel(out), rep["runtime_s"]))


if __name__ == "__main__":
    main()
