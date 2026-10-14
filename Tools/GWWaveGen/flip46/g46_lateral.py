# -*- coding: utf-8 -*-
"""FLIP46：頂の高さの横の分け方を読む（py -3.10 -B、numpy・PIL）。2026-10-15、3D を「細い盛り上がり」にする試しのために足した。
読む物：走らせた所の hf_c*_b*.npz（一番上の水面 eta[コマ, 横 y, x]、格子 1 m）、cfg.json、ana.json（巻き始め・最も巻いた・着水のコマ、静かな水面のずれ）。
量（どれも y = 0 の対称の面から片側を読み、幅は両側の全幅に直す）：
  c(y)      各 y で x ≥ 150 m の頂の高さ（x の向きに 3 格子の中央値で細い水の針を除いてからの最大）。静かな水面のずれを引く
  c0・c_far 真ん中（y < 1 m）と、横の端の 10 m（y ≥ W − 10）の平均
  比        c0 / c_far（1 なら横に一様な長い波）
  半分の幅  c(y) − c_far ≥ (c0 − c_far)/2 の全幅（盛り上がりの幅。c0 − c_far が 0.3 m より小さい時は読まない）
  90% の幅  c(y) ≥ 0.9 c0 の全幅
  包み      各 y で、着水のコマまでの頂の高さの最大（波が通る間の一番高い所）。下流の壁の手前 10 m は読まない
巻いた所の横の全幅は ana.json の short_crest（g46_analyze.py の r4 の読み）をそのまま写す。
使い方：py -3.10 -B g46_lateral.py <走らせた所> [<走らせた所> ...]
出す物：<走らせた所>/lateral.json・LATERAL_ja.md・video/<run_id>_lateral.png
"""
import os, sys, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

X_MIN = 150.0          # 頂を探す x の始まり（波が尾根に入ってからの所。g46_analyze の r4 と同じ）
X_END_PAD = 10.0       # 下流の壁の手前を除く幅（m）。壁で跳ね上がる水を頂に数えない
FAR_BAND = 10.0        # 横の端の帯（m）
MIN_EXCESS = 0.3       # 盛り上がりの幅を読む最小の差（m）
FONT = r"C:/Windows/Fonts/meiryo.ttc"


def load_hf(rd):
    ds = [np.load(p) for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz")))]
    ds = [d for d in ds if d["eta"].ndim == 3]
    shapes = [d["eta"].shape[1:] for d in ds]
    main = max(set(shapes), key=lambda s: sum(len(d["frames"]) for d, s2 in zip(ds, shapes) if s2 == s))
    fr, et = [], []
    for d, s in zip(ds, shapes):
        if s != main:
            continue                                   # 0 コマ目の別の大きさ（箱の外まで）の記録は飛ばす
        fr.append(d["frames"]); et.append(d["eta"])
    frames = np.concatenate(fr); eta = np.concatenate(et, axis=0)
    o = np.argsort(frames, kind="stable")
    return frames[o], eta[o]


def crest_profile(eta_f, x_idx):
    """eta_f[y, x] → c(y)。x の向きに 3 格子の中央値（1〜2 格子の水の針を除く）を取ってから x ≥ X_MIN の最大。"""
    e = eta_f[:, x_idx]
    pad = np.pad(e, ((0, 0), (1, 1)), mode="edge")
    med = np.median(np.stack([pad[:, :-2], pad[:, 1:-1], pad[:, 2:]]), axis=0)
    return np.nanmax(med, axis=1)


def widths(c, y, W):
    c0 = float(np.mean(c[y < 1.0]))
    far = float(np.mean(c[y >= W - FAR_BAND]))
    ex = c0 - far
    out = dict(c0=c0, c_far=far, ratio=c0 / far if far > 0 else None, excess=ex)
    if ex >= MIN_EXCESS:
        m = (c - far) >= 0.5 * ex
        # 真ん中から続く所だけ（離れた所の別の山は数えない）
        k = int(np.argmin(m)) if not m.all() else len(m)
        out["half_width_full_m"] = 2.0 * float(y[k - 1] + 0.5) if k > 0 else 0.0
    else:
        out["half_width_full_m"] = None
    m9 = c >= 0.9 * c0
    k9 = int(np.argmin(m9)) if not m9.all() else len(m9)
    out["w90_full_m"] = 2.0 * float(y[k9 - 1] + 0.5) if k9 > 0 else 0.0
    return out


def plot(path, y, curves, title, sub):
    Wp, Hp = 1280, 720
    im = Image.new("RGB", (Wp, Hp), (250, 250, 247)); dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 26); f2 = ImageFont.truetype(FONT, 17); f3 = ImageFont.truetype(FONT, 15)
    dr.text((40, 16), title, fill=(20, 20, 20), font=f1)
    dr.text((40, 54), sub, fill=(90, 90, 90), font=f2)
    L, R, T, B = 110, Wp - 300, 100, Hp - 80
    ys = np.concatenate([-y[::-1], y])
    allv = np.concatenate([c for _, c, _ in curves])
    lo = 0.0; hi = max(14.0, float(np.nanmax(allv)) + 0.5)
    Y = lambda v: B - (v - lo) / (hi - lo) * (B - T)
    X = lambda v: L + (v - ys[0]) / (ys[-1] - ys[0]) * (R - L)
    for g in range(0, int(hi) + 1, 2):
        dr.line([(L, Y(g)), (R, Y(g))], fill=(225, 225, 225)); dr.text((L - 50, Y(g) - 10), "%d m" % g, fill=(90, 90, 90), font=f3)
    for g in np.arange(-np.floor(ys[-1] / 20) * 20, ys[-1] + 1, 20):
        dr.line([(X(g), T), (X(g), B)], fill=(235, 235, 235)); dr.text((X(g) - 18, B + 8), "%d" % g, fill=(90, 90, 90), font=f3)
    dr.text(((L + R) / 2 - 120, B + 34), "横の位置 y（m、0 が真ん中）", fill=(60, 60, 60), font=f2)
    dr.rectangle([L, T, R, B], outline=(120, 120, 120))
    for i, (lab, c, col) in enumerate(curves):
        cs = np.concatenate([c[::-1], c])
        pts = [(X(a), Y(b)) for a, b in zip(ys, cs) if np.isfinite(b)]
        dr.line(pts, fill=col, width=3)
        dr.line([(R + 20, T + 20 + 30 * i), (R + 50, T + 20 + 30 * i)], fill=col, width=4)
        dr.text((R + 58, T + 10 + 30 * i), lab, fill=(30, 30, 30), font=f3)
    im.save(path)


def run(rd):
    rd = os.path.abspath(rd)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    ana = json.load(open(os.path.join(rd, "ana.json"), encoding="utf8"))
    rid = cfg["run_id"]; P = cfg["parms"]; W = float(P["W"])
    off = float(ana.get("still_level_offset_m") or 0.0)
    frames, eta = load_hf(rd)
    ny, nx = eta.shape[1], eta.shape[2]
    y = np.arange(ny) + 0.5
    x = float(P["x0"]) + np.arange(nx) + 0.5
    x_idx = np.where((x >= X_MIN) & (x <= float(P["x0"]) + float(P["Lx"]) - X_END_PAD))[0]
    prof = np.stack([crest_profile(eta[i], x_idx) for i in range(len(frames))]) - off
    key = dict((ana.get("shape") or {}).get("frames") or {})
    if not key and ana.get("steepest"):
        key = {"steepest": int(ana["steepest"]["frame"])}         # 巻かなかった時は最も険しいコマ
    f_env = key.get("contact") or key.get("max_overturn") or key.get("steepest") or int(frames[-1])
    env = np.nanmax(prof[frames <= f_env], axis=0)          # 包みは着水まで（後の壁の跳ね上がりを除く）
    t_of = lambda f: (f - 1) / 24.0 + float(P.get("t_off", 0.0))
    rows = {}
    for nm, f in key.items():
        if f is None or f not in set(frames.tolist()):
            continue
        i = int(np.where(frames == f)[0][0])
        r = widths(prof[i], y, W); r.update(frame=int(f), t=t_of(f))
        rows[nm] = r
    env_w = widths(env, y, W)
    # 巻いた所の全幅（g46_analyze の読み）
    sc_rows = []
    for nm, v in (ana.get("short_crest") or {}).items():
        if isinstance(v, dict) and "frame" in v:
            sc_rows.append(dict(name=nm, frame=v.get("frame"), t=v.get("t"), overturned_full_m=v.get("overturned_full_m"),
                                far_single_valued=v.get("far_single_valued")))
    ts_rows = []
    for i in range(0, len(frames), 24):
        if frames[i] > f_env:
            break
        w = widths(prof[i], y, W); ts_rows.append(dict(frame=int(frames[i]), t=t_of(int(frames[i])), c0=w["c0"], c_far=w["c_far"], ratio=w["ratio"]))
    out = dict(run_id=rid, tool="g46_lateral.py", time_series=ts_rows, W=W, ridge_k=P.get("ridge_k"), still_offset_m=off, x_min=X_MIN, far_band_m=FAR_BAND,
               key=rows, envelope=env_w, envelope_profile=[round(float(v), 3) for v in env],
               profiles={nm: [round(float(v), 3) for v in prof[int(np.where(frames == r["frame"])[0][0])]] for nm, r in rows.items()},
               short_crest=sc_rows)
    json.dump(out, open(os.path.join(rd, "lateral.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    os.makedirs(os.path.join(rd, "video"), exist_ok=True)
    curves = [("包み（全コマの最大）", env, (200, 60, 40))]
    cols = {"onset": (40, 90, 200), "max_overturn": (30, 150, 90), "contact": (130, 80, 170)}
    labs = {"onset": "巻き始め", "max_overturn": "最も巻いた", "contact": "着水", "steepest": "最も険しい（巻かない）"}
    cols["steepest"] = (40, 90, 200)
    for nm, r in rows.items():
        curves.append(("%s t=%.2f s" % (labs.get(nm, nm), r["t"]), prof[int(np.where(frames == r["frame"])[0][0])], cols.get(nm, (0, 0, 0))))
    plot(os.path.join(rd, "video", "%s_lateral.png" % rid), y, curves,
         "%s：頂の高さの横の分け方" % rid, "尾根 k %s・横の半幅 %g m・粒子 %s m。y = 0 の両側に写して描いた" % (P.get("ridge_k"), W, P.get("dp")))
    L = ["# %s：頂の高さの横の分け方（g46_lateral.py）" % rid, "",
         "尾根 k %s、横の半幅 %g m。頂 = x ≥ %g m の一番上の水面の最大（x の 3 格子の中央値の後）。静かな水面のずれ %.3f m を引いた。" % (P.get("ridge_k"), W, X_MIN, off), "",
         "| 時 | コマ | t（s） | 真ん中 c0（m） | 端 c_far（m） | c0/c_far | 盛り上がりの半分の幅（全幅 m） | 90% の幅（全幅 m） |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    fmt = lambda v, s="%.2f": ("—" if v is None else s % v)
    for nm, r in rows.items():
        L.append("| %s | %d | %.3f | %s | %s | %s | %s | %s |" % (labs.get(nm, nm), r["frame"], r["t"], fmt(r["c0"]), fmt(r["c_far"]), fmt(r["ratio"], "%.3f"),
                                                             fmt(r["half_width_full_m"], "%.0f"), fmt(r["w90_full_m"], "%.0f")))
    L.append("| 包み（着水まで） | — | — | %s | %s | %s | %s | %s |" % (fmt(env_w["c0"]), fmt(env_w["c_far"]), fmt(env_w["ratio"], "%.3f"),
                                                         fmt(env_w["half_width_full_m"], "%.0f"), fmt(env_w["w90_full_m"], "%.0f")))
    L += ["", "1 s ごとの真ん中と端の頂（m）：", "", "| t（s） | 真ん中 | 端 | 比 |", "| --- | --- | --- | --- |"]
    for r in ts_rows:
        L.append("| %.1f | %s | %s | %s |" % (r["t"], fmt(r["c0"]), fmt(r["c_far"]), fmt(r["ratio"], "%.3f")))
    L += ["", "巻いた所の横の全幅（g46_analyze.py の r4 の読み）：", ""]
    for s in sc_rows:
        L.append("- %s：コマ %s、t %.3f s、%s m（端が一価 = %s）" % (s["name"], s["frame"], s["t"] or 0, s["overturned_full_m"], s["far_single_valued"]))
    open(os.path.join(rd, "LATERAL_ja.md"), "w", encoding="utf8").write("\n".join(L) + "\n")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for a in sys.argv[1:]:
        o = run(a)
        print(open(os.path.join(os.path.abspath(a), "LATERAL_ja.md"), encoding="utf8").read())
