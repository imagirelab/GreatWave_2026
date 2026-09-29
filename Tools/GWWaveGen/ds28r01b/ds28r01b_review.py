# -*- coding: utf-8 -*-
"""設計28修正01 試行B：変種（V80・V75・V70）と設計28 の、唇の目に見える伸び出しの始まり・打ち出し・爪の育ち方の表と、要の図。

読むもの（どれも Git 対象外。パッケージは ds27_gates.Package（Unity の再生器と同じ Hermite）で読む。生成器のコードは読まない）：
  パッケージ：設計28 Unity/Build/Design/28/art_on、試行B Unity/Build/Design/28R01B/<変種>/art_on
  独立の検査器 ds28r01_overlap.py の出力（<out>.json と <out>_measure.npz：爪の係数 C・唇の伸びの始まり τ_grow など）
  関門の出力（ds28r01_gates.py、P4・P15 の段階の時刻・P16）
  生成器の記録（ds28r01b_generate_log.json の lip_launch。唇先の放出・打ち出しの表）、試行A の launch（設計28 の値）
  時間曲線（設計28 の既定 ds27、試行B の変種ごとの既定、代案＝実時間の瞬間停止）
目に見える唇の始まり（試行A のレビューと同じ読み）：
  fwd0.5 / fwd1.0：唇先（K* の唇先の列）が、唇の動きの始まりの位置から波の枠で前へ 0.5 m・1.0 m 出る最初の τ。始まりは、設計28 は較正の噴流の
      始まり（τ = −T_row）、試行B は運びの始まり（τ = σ_b + lag_r。ds28r01b_params.json と ds26_conditions.json の T_row の規則から）。
      段階 b の塔が唇先を後ろへ回す行があるので、始まりからの最も後ろの位置から測った fwdR0.5 も記録する。
  Lo0.10：張り出し Lo ≥ 0.1H が t* まで途切れずに続く最初の τ（設計26 §3.1 の定義 A）。
  見える始まり τ_vis = max(fwd0.5, Lo0.10)（主断面・峰の行それぞれ）と、その時の H/Hf。
使い方（リポジトリの根で。約 1〜2 分）：py -3.10 -B Tools/GWWaveGen/ds28r01b/ds28r01b_review.py [--out Unity/Build/Design/28R01B/review]
"""
import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds28"))
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as DX  # noqa: E402

B = os.path.join(REPO, "Unity", "Build", "Design", "28R01B")
B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
BA = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
TW27D = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json")
TWALT = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_alt.json")
VARS = ["V80", "V75", "V70"]
TAGS = ["D28"] + VARS
ROWS = {"main": 159, "peak": 192}
HZ = 60
G = 9.81
COL = {"D28": (120, 120, 120), "V80": (30, 90, 200), "V75": (20, 150, 60), "V70": (220, 110, 0)}
LABEL = {"D28": "設計28", "V80": "V80", "V75": "V75", "V70": "V70"}
FONT = "C:/Windows/Fonts/YuGothM.ttc"


def font(sz):
    return ImageFont.truetype(FONT, sz)


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


def jload(p):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


ALT_ROOT = None       # --root：修正の途中の版（run1・run2・run3 の <変種>_art_on 等）を読むとき


def paths(tag):
    if ALT_ROOT and tag != "D28":
        return dict(pkg=os.path.join(ALT_ROOT, "%s_art_on" % tag), tw=os.path.join(HERE, "timewarp_default_%s.json" % tag),
                    overlap=os.path.join(ALT_ROOT, "%s_overlap" % tag, "overlap_default.json"),
                    gates=os.path.join(ALT_ROOT, "%s_gates" % tag, "default.json"), gates_alt=os.path.join(ALT_ROOT, "%s_gates" % tag, "alt.json"),
                    genlog=os.path.join(ALT_ROOT, "%s_art_on" % tag, "ds28r01b_generate_log.json"))
    if tag == "D28":
        return dict(pkg=os.path.join(B28, "art_on"), tw=TW27D, overlap=os.path.join(BA, "overlap", "ds28_art_on.json"),
                    gates=os.path.join(B28, "gates", "art_on_default.json"), gates_alt=os.path.join(B28, "gates", "art_on_alt.json"))
    return dict(pkg=os.path.join(B, tag, "art_on"), tw=os.path.join(HERE, "timewarp_default_%s.json" % tag),
                overlap=os.path.join(B, tag, "overlap", "overlap_default.json"),
                gates=os.path.join(B, tag, "gates", "default.json"), gates_alt=os.path.join(B, tag, "gates", "alt.json"),
                genlog=os.path.join(B, tag, "art_on", "ds28r01b_generate_log.json"))


def lip_onset(tag, ks, cond):
    """唇の動きの始まり τ（行ごと）。設計28 は較正の噴流の始まり、試行B は運びの始まり σ_b + lag_r。"""
    Tc = DX.calib_onset(ks, cond)
    if tag == "D28":
        return -Tc
    RB = jload(os.path.join(HERE, "ds28r01b_params.json"))
    sb = float(RB["variants"][tag]["carry_start_sigma"])
    lag = abs(cond["tau0"]) - Tc
    return sb + lag


class Warp:
    def __init__(self, p):
        J = jload(p)
        self.t = np.asarray(J["t"], float)
        self.tau = np.asarray(J["tau"], float)
        k = int(np.argmax(self.tau >= -1e-9))
        self.tu, self.tauu = self.t[:k + 1], self.tau[:k + 1]
        self.params = J.get("params", {})

    def t_of(self, tau):
        if tau is None:
            return None
        if tau < self.tauu[0]:
            return None
        return float(np.interp(tau, self.tauu, self.tu))


def series(pk, ks, rows, t0=-4.6):
    taus = np.round(np.arange(t0, 1e-9, 1.0 / HZ), 9)
    taus[-1] = 0.0
    rr = np.array(rows)
    out = {k: np.full((len(taus), len(rows)), np.nan) for k in ("H", "Lo", "phi", "ca", "tip_a", "tip_y")}
    tipc = ks.tip_col[rr]
    for k, tv in enumerate(taus):
        Xl = pk.local(float(tv)) + ks.O
        A, Y, _ = ks.section(Xl)
        A, Y = A[rr], Y[rr]
        rm = DG.row_metrics(A, Y, ks.crest_hi[rr], ks.j_E)
        out["H"][k], out["Lo"][k], out["phi"][k], out["ca"][k] = rm["H"], rm["Lo"], rm["phi"], rm["ca"]
        out["tip_a"][k] = A[np.arange(len(rr)), tipc]
        out["tip_y"][k] = Y[np.arange(len(rr)), tipc]
    out["taus"] = taus
    return out


def first_sustained(mask):
    if len(mask) == 0 or not mask[-1]:
        return None
    bad = np.nonzero(~mask)[0]
    return int(bad[-1] + 1) if len(bad) else 0


def visible(S, j, tau_on):
    taus = S["taus"]
    H, Lo, ta, ty, ca = S["H"][:, j], S["Lo"][:, j], S["tip_a"][:, j], S["tip_y"][:, j], S["ca"][:, j]
    Hf = H[-1]
    hn = H / Hf
    k0 = int(np.argmin(np.abs(taus - tau_on)))
    a0 = ta[k0]
    idx = np.arange(len(taus))
    rm = np.minimum.accumulate(np.where(idx >= k0, ta, np.inf))
    d = dict(tau_on=r3(taus[k0]), H_over_Hf_at_on=r3(hn[k0]), tip_a_at_on_m=r3(a0))

    def at(k):
        return None if k is None else dict(tau=r3(taus[k]), H_over_Hf=r3(hn[k]))
    for dx in (0.5, 1.0, 2.0):
        m = (idx >= k0) & (ta - a0 >= dx)
        d["fwd%.1f" % dx] = at(int(np.argmax(m)) if m.any() else None)
        m = (idx >= k0) & (ta - rm >= dx)
        d["fwdR%.1f" % dx] = at(int(np.argmax(m)) if m.any() else None)
    lo0 = np.nan_to_num(Lo, nan=-1.0)
    for thr in (0.05, 0.10):
        d["Lo%.2f" % thr] = at(first_sustained(lo0 >= thr * H))
    cand = [d["fwd0.5"], d["Lo0.10"]]
    if all(c is not None for c in cand):
        tv = max(c["tau"] for c in cand)
        k = int(np.argmin(np.abs(taus - tv)))
        d["visible"] = dict(tau=r3(taus[k]), H_over_Hf=r3(hn[k]), by=("fwd0.5" if d["fwd0.5"]["tau"] >= d["Lo0.10"]["tau"] else "Lo0.10"),
                            gain_after_over_Hf=r3(1 - hn[k]))
    else:
        d["visible"] = None
    # 唇先の頂点（始まりの後の最高点）と、その時の頂との差
    m = idx >= k0
    kap = int(np.nonzero(m)[0][0] + np.argmax(ty[m]))
    d["tip_apex"] = dict(tau=r3(taus[kap]), y_m=r3(ty[kap]), crest_m=r3(H[kap]), above_crest_m=r3(ty[kap] - H[kap]))
    d["tip_minus_crest_max_m"] = r3(float(np.max((ty - H)[m])))
    for tq in (-3.3, -3.0, -2.7, -2.4, -2.0, -1.6, -1.2, -0.8, -0.4, 0.0):
        k = int(np.argmin(np.abs(taus - tq)))
        d["at_%+.1f" % tq] = dict(H_over_Hf=r3(hn[k]), tip_forward_m=r3(ta[k] - a0), tip_ahead_of_crest_m=r3(ta[k] - ca[k]),
                                 tip_minus_crest_y_m=r3(ty[k] - H[k]), Lo_over_H=r3(Lo[k] / H[k]))
    return d


def claw_series(overlap_json, row):
    """独立の検査器の測定（<out>_measure.npz）から、行の爪の係数 C（上面の段 claw_steps、t* で 1）と H・Lo の時系列。"""
    base = os.path.splitext(overlap_json)[0] + "_measure.npz"
    if not os.path.isfile(base):
        return None
    z = np.load(base)
    rows = list(z["rows"])
    i = rows.index(row)
    return dict(taus=z["taus"], C=z["CL_claw_steps"][:, i], H=z["H"][:, i], Lo=z["Lo"][:, i])


def find_row(J, row):
    """ds28r01_overlap の出力から行の評価を探す（構造に依らず、row == 行 の dict を深さ優先で探す）。"""
    if J is None:
        return None
    stack = [J]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if o.get("row") == row and "tau_ext" in o:
                return o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return None


# ---------------------------------------------------------------- 図
def draw_fig(res, secs, out_png):
    W = 2200
    ph = 260
    top = 110
    rows_plot = [("main", "主断面（行 159）"), ("peak", "峰の行（行 192）")]
    n_sec = len(res)
    sec_h = 250
    Hh = top + 2 * (4 * ph + 60) + n_sec * (sec_h + 30) + 160
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    f18, f22, f28 = font(18), font(22), font(30)
    d.text((40, 14), "設計28修正01 試行B（Q13）：頂の高さ H/Hf・張り出し Lo/H・唇先の前への距離・爪の細部 C（物理の時刻 τ、t* = 0）", font=f28, fill=(0, 0, 0))
    d.text((40, 58), "丸＝目に見える唇の始まり（唇先が唇の動きの始まりから前へ 0.5 m、かつ Lo ≥ 0.1H が t* まで続く）、三角＝唇先の頂点。設計28＝灰、V80＝青、V75＝緑、V70＝橙", font=f22, fill=(0, 0, 0))
    x0, x1 = 170, W - 60
    t0, t1 = -4.2, 0.0

    def X(t):
        return x0 + (t - t0) / (t1 - t0) * (x1 - x0)
    y_cursor = top
    for key, title in rows_plot:
        panels = [("H/Hf", 0.4, 1.02, "H"), ("Lo/H", -0.02, 0.45, "LoH"), ("唇先の前への距離 [m]（唇の動きの始まりから、波の枠）", -1.0, 11.0, "fwd"),
                  ("爪の細部の係数 C（上面の段を K* の爪の模様へ射影、t* で 1。独立の検査器）", -0.1, 1.05, "C")]
        for pi, (lab, v0, v1, kind) in enumerate(panels):
            ya, yb = y_cursor + 10, y_cursor + ph - 30

            def Yv(v):
                return yb - (v - v0) / (v1 - v0) * (yb - ya)
            d.rectangle([x0, ya, x1, yb], outline=(0, 0, 0))
            for tt in np.arange(-4.0, 0.01, 0.5):
                d.line([(X(tt), ya), (X(tt), yb)], fill=(230, 230, 230))
                d.text((X(tt) - 18, yb + 4), "%.1f" % tt, font=f18, fill=(0, 0, 0))
            ticks = {"H": [0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0], "LoH": [0.0, 0.05, 0.1, 0.2, 0.3, 0.4], "fwd": [0, 0.5, 1, 2, 4, 6, 8, 10],
                     "C": [0.0, 0.25, 0.5, 0.75, 1.0]}[kind]
            for v in ticks:
                d.line([(x0, Yv(v)), (x1, Yv(v))], fill=(215, 215, 215) if v not in (0.7, 0.75, 0.8, 0.1, 0.5) else (180, 180, 220))
                d.text((x0 - 60, Yv(v) - 10), ("%g" % v), font=f18, fill=(0, 0, 0))
            d.text((x0 + 8, ya + 4), "%s — %s" % (title, lab), font=f22, fill=(0, 0, 0))
            for tag in [t for t in TAGS if t in res]:
                S = res[tag]["series"]
                if S is None:
                    continue
                j = list(ROWS.values()).index(ROWS[key])
                taus = S["taus"]
                H = S["H"][:, j]
                Hf = H[-1]
                vis = res[tag]["rows"][key]
                a0 = vis["tip_a_at_on_m"]
                if kind == "H":
                    v = H / Hf
                elif kind == "LoH":
                    v = S["Lo"][:, j] / H
                elif kind == "C":
                    if "C" not in S:
                        continue
                    v = S["C"][:, j]
                else:
                    v = S["tip_a"][:, j] - a0
                    v = np.where(taus >= vis["tau_on"] - 1e-9, v, np.nan)
                m = (taus >= t0) & np.isfinite(v)
                pts = [(X(t), Yv(min(max(y, v0), v1))) for t, y in zip(taus[m], v[m])]
                wdt = 5 if tag != "D28" else 4
                if len(pts) > 1:
                    d.line(pts, fill=COL[tag], width=wdt if kind != "H" or tag == "D28" else 2)
                vv = vis.get("visible")
                if vv:
                    k = int(np.argmin(np.abs(taus - vv["tau"])))
                    if np.isfinite(v[k]):
                        cx, cy = X(taus[k]), Yv(min(max(v[k], v0), v1))
                        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=COL[tag], width=4)
                ap = vis["tip_apex"]["tau"]
                k = int(np.argmin(np.abs(taus - ap)))
                if np.isfinite(v[k]):
                    cx, cy = X(taus[k]), Yv(min(max(v[k], v0), v1))
                    d.polygon([(cx, cy - 10), (cx - 9, cy + 7), (cx + 9, cy + 7)], outline=COL[tag])
            y_cursor += ph
        y_cursor += 20
    # 凡例
    lx = x0
    for tag in [t for t in TAGS if t in res]:
        d.line([(lx, y_cursor + 12), (lx + 50, y_cursor + 12)], fill=COL[tag], width=5)
        d.text((lx + 58, y_cursor), LABEL[tag], font=f22, fill=(0, 0, 0))
        lx += 200
    d.text((lx + 40, y_cursor), "頂の高さの線は 4 本が重なる（設計28 の上昇のまま）。x 軸は物理の時刻 τ [s]（t* = 0）", font=f22, fill=(0, 0, 0))
    y_cursor += 60
    # 断面の帯
    for tag in [t for t in TAGS if t in res]:
        sl = secs.get(tag) or []
        d.text((40, y_cursor + 2), LABEL[tag], font=f28, fill=COL[tag])
        cw = (W - 200) / max(len(sl), 1)
        for i, (name, tv, A, Y, Ap, Yp, tipm, tipp, hn) in enumerate(sl):
            ox = 200 + i * cw + cw * 0.28
            oy = y_cursor + sec_h - 20
            sc = 7.0
            ac = A[int(np.argmax(np.where(np.arange(len(Y)) <= 120, Y, -1)))]
            acp = Ap[int(np.argmax(np.where(np.arange(len(Yp)) <= 120, Yp, -1)))]
            pts = [(ox + (a - ac) * sc, oy - y * sc) for a, y in zip(A, Y) if -25 < a - ac < 22]
            ptsp = [(ox + (a - acp) * sc, oy - y * sc) for a, y in zip(Ap, Yp) if -25 < a - acp < 22]
            d.line([(ox - 25 * sc, oy), (ox + 22 * sc, oy)], fill=(200, 200, 200))
            if len(ptsp) > 1:
                d.line(ptsp, fill=(170, 170, 170), width=1)
            if len(pts) > 1:
                d.line(pts, fill=(0, 0, 0), width=2)
            tx, ty = tipm
            cx, cy = ox + (tx - ac) * sc, oy - ty * sc
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=COL[tag])
            d.text((ox - 18 * sc, y_cursor + 34), "%s τ %.2f  H/Hf %.2f" % (name, tv, hn), font=f18, fill=(0, 0, 0))
        y_cursor += sec_h + 30
    d.text((40, y_cursor), "断面：黒＝主断面（行 159）、灰＝峰の行（行 192、頂をそろえて重ねた）、点＝主断面の唇先。尺度は縦横同じ。段階 a・b・c は関門 P15（設計26 の表）の主断面の時刻", font=f18, fill=(0, 0, 0))
    d.text((40, y_cursor + 26), "（試行B は c が設計26 の帯に入らないので表の時刻 σ −2.4）。見える始まりは主断面の τ_vis、頂点は主断面の唇先の頂点", font=f18, fill=(0, 0, 0))
    y_cursor += 26
    img = img.crop((0, 0, W, y_cursor + 40))
    img.save(out_png, optimize=True)


def section_strip(tag, pk, ks, res, gates):
    stg = {}
    if gates:
        det = gates.get("gates", {}).get("P15", {}).get("detail", {}).get("主断面", {})
        stg = det.get("tau") or {}
    lag = 0.1925
    table = {"a": -4.2 + lag, "b": -3.4 + lag, "c": -2.4 + lag}
    out = []
    vis = res[tag]["rows"]["main"]
    items = [("a" if stg.get("a") is not None else "a（表）", stg.get("a") if stg.get("a") is not None else table["a"]),
             ("b" if stg.get("b") is not None else "b（表）", stg.get("b") if stg.get("b") is not None else table["b"]),
             ("c" if stg.get("c") is not None else "c（表 σ −2.4）", stg.get("c") if stg.get("c") is not None else table["c"]),
             ("見える始まり", vis["visible"]["tau"] if vis.get("visible") else None), ("唇先の頂点", vis["tip_apex"]["tau"]), ("t*", 0.0)]
    Hf = None
    X0 = pk.local(0.0) + ks.O
    A0, Y0, _ = ks.section(X0)
    Hf = float(DG.row_metrics(A0[[159]], Y0[[159]], ks.crest_hi[[159]], ks.j_E)["H"][0])
    for name, tv in items:
        if tv is None:
            continue
        Xl = pk.local(float(tv)) + ks.O
        A, Y, _ = ks.section(Xl)
        tc = int(ks.tip_col[159])
        H = float(DG.row_metrics(A[[159]], Y[[159]], ks.crest_hi[[159]], ks.j_E)["H"][0])
        out.append((name, float(tv), A[159], Y[159], A[192], Y[192], (A[159, tc], Y[159, tc]), (A[192, int(ks.tip_col[192])], Y[192, int(ks.tip_col[192])]), H / Hf))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "review"))
    ap.add_argument("--tags", default=",".join(TAGS))
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    global ALT_ROOT
    ALT_ROOT = a.root
    os.makedirs(a.out, exist_ok=True)
    ks = DG.KStar()
    cond, _ = DG.load_conditions()
    alt = Warp(TWALT)
    res = {}
    secs = {}
    rows = list(ROWS.values())
    for tag in a.tags.split(","):
        P = paths(tag)
        if not os.path.isfile(os.path.join(P["pkg"], "ds27_keypose.json")):
            print("skip", tag)
            continue
        pk = DG.Package(P["pkg"], ks)
        S = series(pk, ks, rows)
        Cs = [claw_series(P["overlap"], r) for r in rows]
        if all(c is not None for c in Cs):
            S["C"] = np.stack([np.interp(S["taus"], c["taus"], np.nan_to_num(c["C"])) for c in Cs], 1)
        on = lip_onset(tag, ks, cond)
        wd = Warp(P["tw"]) if os.path.isfile(P["tw"]) else None
        ov = jload(P["overlap"])
        gates = jload(P["gates"])
        gates_alt = jload(P["gates_alt"])
        e = dict(package=rel(P["pkg"]), pos_sha256=pk.pos_sha, warp_default=rel(P["tw"]) if wd else None,
                 warp_default_params={k: wd.params.get(k) for k in ("t1", "slow_reached_tau", "tau_at_t0_default", "tau_at_ramp_start", "earliest_apex_row")} if wd else None,
                 rows={}, series=S)
        for key, r in ROWS.items():
            j = rows.index(r)
            v = visible(S, j, float(on[r]))
            for wn, W in (("default", wd), ("alt", alt)):
                if W is None:
                    continue
                v["screen_" + wn] = dict(t_visible=r3(W.t_of(v["visible"]["tau"]) if v.get("visible") else None, 2),
                                         t_tip_apex=r3(W.t_of(v["tip_apex"]["tau"]), 2),
                                         t_H90=r3(W.t_of(float(S["taus"][int(np.argmax(S["H"][:, j] / S["H"][-1, j] >= 0.9))])), 2),
                                         t_H95=r3(W.t_of(float(S["taus"][int(np.argmax(S["H"][:, j] / S["H"][-1, j] >= 0.95))])), 2),
                                         r_at_visible=r3(float(np.interp(W.t_of(v["visible"]["tau"]), W.t, np.gradient(W.tau, W.t))) if v.get("visible") and W.t_of(v["visible"]["tau"]) is not None else None, 3))
            oe = find_row(ov, r)
            if oe:
                cl = (oe.get("claws") or {}).get("claw_steps", {})
                v["overlap"] = dict(tau_ext=oe.get("tau_ext"), H_over_Hf_at_ext=oe.get("H_over_Hf_at_ext"), tau_grow=oe.get("tau_grow"),
                                    H_over_Hf_at_grow=oe.get("H_over_Hf_at_grow"), lip_stall_after_ext_s=oe.get("lip_stall_after_ext_s"),
                                    P_at_H95=oe.get("P_at_H95"), tau_Lof50=oe.get("tau_Lof50"), H_over_Hf_at_Lof50=oe.get("H_over_Hf_at_Lof50"),
                                    T1=oe.get("T1"), T1_strict=oe.get("T1_strict"),
                                    claw=dict((k, cl.get(k)) for k in ("C_at_ext", "tau_C50", "H_over_Hf_at_C50", "C_share_last_1s", "P_share_last_1s",
                                                                      "max_abs_C_minus_P", "lag_C50_minus_P50_s", "C_drawdown_from_ext", "pass")))
            cs = claw_series(P["overlap"], r)
            if cs and "C" in cs:
                taus_c = cs["taus"]
                vt = v["visible"]["tau"] if v.get("visible") else None
                v["claw_C_vs_tau"] = {("%+.2f" % tq): r3(float(np.interp(tq, taus_c, cs["C"]))) for tq in
                                      ([vt] if vt is not None else []) + [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0]}
                if vt is not None:
                    k1 = int(np.searchsorted(taus_c, -1.0))
                    kv = int(np.argmin(np.abs(taus_c - vt)))
                    span = cs["C"][-1] - cs["C"][kv]
                    v["claw_share_last_1s_from_visible"] = r3((cs["C"][-1] - cs["C"][k1]) / span) if abs(span) > 1e-6 else None
            e["rows"][key] = v
        # 関門の要約
        for gname, G_ in (("gates_default", gates), ("gates_alt", gates_alt)):
            if G_ is None:
                continue
            gs = G_.get("gates", {})
            gx = G_.get("gates_ds28", {})
            e[gname] = dict(failed=G_.get("summary_all", {}).get("failed"),
                            values={k: gs[k].get("value") for k in gs}, values_ds28={k: gx[k].get("value") for k in gx},
                            P4=gs.get("P4", {}).get("detail"), P16=gs.get("P16", {}).get("detail"))
        # 打ち出し
        if tag == "D28":
            L = jload(os.path.join(BA, "launch", "ds28r01_launch.json"))
            e["launch"] = (L or {}).get("ds28_art_on", {}).get("rows")
        else:
            GL = jload(P["genlog"])
            e["launch"] = (GL or {}).get("result", {}).get("lip_launch")
            e["generator_summary"] = {k: (GL or {}).get("result", {}).get("summary", {}).get(k) for k in
                                      ("carry_start_sigma", "free_release_fraction", "carry_start_tau", "free_release_tip_tau", "max_abs_kick_mps", "lip_plausible_fraction")}
            e["gen_seconds"] = (GL or {}).get("result", {}).get("seconds")
        res[tag] = e
        secs[tag] = section_strip(tag, pk, ks, res, gates)
        print("done", tag, flush=True)
    draw_fig(res, secs, os.path.join(a.out, "fig_ds28r01b_q13_variants.png"))
    # 修正の記録：初回（run1）・修正1（run2）の関門の要約（最後の版は各変種の gates/）
    hist = {}
    for run, sub in (("run1_first_full_run", "run1"), ("run2_iteration1", "run2"), ("run3_iteration2_before_edge_row_ramp_fix", "run3")):
        hr = {}
        for v in VARS:
            e = {}
            for w in ("default", "alt"):
                G_ = jload(os.path.join(B, sub, "%s_gates" % v, "%s.json" % w))
                if G_ is None:
                    continue
                gs, gx = G_["gates"], G_["gates_ds28"]
                e[w] = dict(failed=G_["summary_all"]["failed"], P4=gs["P4"]["value"], P13=gs["P13"]["value"], P16=gs["P16"]["value"],
                            P17=gx["P17"]["value"], P18=gx["P18"]["value"], P19=gx["P19"]["value"], P3=gs["P3"]["value"], P7=gs["P7"]["value"])
            hr[v] = e
        hist[run] = hr
    res["_history"] = hist
    for tag in res:
        if isinstance(res[tag], dict):
            res[tag].pop("series", None)
    with open(os.path.join(a.out, "review_ds28r01b.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=lambda o: r3(o) if isinstance(o, (np.floating, float)) else (int(o) if isinstance(o, np.integer) else str(o)))
    print(os.path.join(a.out, "review_ds28r01b.json"))


if __name__ == "__main__":
    main()
