# -*- coding: utf-8 -*-
"""FLIP44：計算の記録から、計画 plan_ja.md §3.3 (a)(d) の量を出す（py -3.10、numpy・scipy・scikit-image）。
FLIP42 の g_analyze.py（A3' の符号を直した版。変えていない）の読み方を写し、礁の計算に合わせて足した。
同じにした読み方（FLIP42 の記録の「計画の読み方」）：
  1 静かな水面＝造波板から 0〜930 m の 0.5〜2.0 s の一番上の水面の中央値（計画 N1）。2 測る点は板の内側の節の平均。
  7 巻き始め＝前の面の線の傾き（線に沿って格子 1 個分の弦）が初めて 90° 以上になったコマ。場所＝そのコマの頂の x（計画 §3.3 (a)）。
  8 着水＝巻き始めの後、唇の先が静かな水面以下になったか、空気を囲む閉じた線（格子 1 個以上）ができた最初のコマ。
  9 η_c・H＝頂の高さと、頂から前へ 0.75 Lc までの最も低い所との差。
足した所：
  - 断面のどのコマでも、全部の頂（一番上の水面の山。高さ 0.5 m 以上、前後の谷からの高さ 0.3 m 以上）を見つけ、コマの間でつないで
    頂ごとの巻き始めと着水を出す（計画 §3.3 (a) 3「一つの群の中で巻く波は一つ」、(c) の各回の頂のため）。
  - 断面の海底の中は水として扱う（礁の上で海底の線を拾わないため）。
  - 主な巻き波＝300〜800 m で、着水までの頂の高さの最大が最も大きい頂（群の中で最も高い頂）。繰り返しでは回ごと（g44_repeat.py）。
  - (a) の 3 条件、N3（帯の出口の 3 帯域の比と位相。窓を決めて FLIP42 の記録も同じ窓で出し直す）、N4（帯の出口から 268.8 m の
    エネルギーの流れの減り）、N5（群の前を行く頂の速さ、沖と礁の上）、N6（220・250 m の 2 点で跳ね返りを分ける）、N7（0.03 Hz より低い揺れ）。
  - stop_main_touchdown：区切った起動の後に、主な巻き波の着水 + 2 Tc を過ぎたら止める（計画 §3.2）。
  - 2026-10-12（2 回目の確かめ G5）：主な頂がその頂の道の最初のコマですでに巻いていた時（断面が巻き始めより後から始まった時など）は、
    notes_ja と onset_at_path_start に書く。読みは変えない。
使い方：
  py -3.10 g44_analyze.py <run_id> [runs|smoke] [--quick] [--out <path>]   → <root>/<run_id>/ana.json（--out は試しの時だけ）
    途中保存から始めた計算（風。cfg の from_ckpt）：静かな水面は元の計算の値（計画 N1）、N3〜N7 は読まず理由を書く。
    記録が決まりに足りない時は AnalysisInputError で理由を書いて止める（終わりのコード 3）。2026-10-12 確かめ F1 の直し。
  py -3.10 g44_analyze.py --flip42 <R3|R2|R4d>              → FLIP42 の記録を同じ道具で読む（道具の確かめ。ana44.json を FLIP44 の check/ に書く）
  py -3.10 g44_analyze.py --select <PR1 の id> <PR2 の id>   → 計画 §3.3 (a) の決まりで形の本番の入口を選ぶ（select.json）
"""
import sys, os, json, glob, math, warnings
import numpy as np
from skimage import measure
from scipy.signal import find_peaks

REPO = r"G:/Unity/GreatWave_2026_Fresh"
B44 = REPO + "/Unity/Build/FLIP44"
R42 = REPO + "/Unity/Build/FLIP42/runs"
PLAN = B44 + "/plan/plan_numbers.json"
G = 9.80665
FPS = 24.0


def plan():
    return json.load(open(PLAN, encoding="utf-8"))


def run_dir(rid, root="runs"):
    return os.path.join(R42, rid) if root == "flip42" else os.path.join(B44, root, rid)


class AnalysisInputError(ValueError):
    """記録が読みの決まりに足りない時（何が足りないかを文で返す。2026-10-12 確かめ F1 の直し）。"""


# ------------------------------------------------------------------ 読み込み（FLIP42 と同じ決まり：後の起動が上書き）
def load_hf(rd, f_max=None):
    """f_max：このコマまでだけ読む（静かな水面を元の計算から出す時に、始めの起動の記録だけを読むため）。"""
    files = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    if f_max is not None:
        files = [p for p in files if int(os.path.basename(p)[4:8]) <= f_max]
    if not files:
        raise AnalysisInputError("一番上の水面の記録（hf_c*.npz）がない：%s" % rd)
    F, E, W, N, SS, WC = [], [], [], [], [], []
    x = z = None
    for p in files:
        d = np.load(p)
        fr = list(d["frames"])
        if not fr:
            continue
        if F:
            keep = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in keep]; E = [E[i] for i in keep]; W = [W[i] for i in keep]; N = [N[i] for i in keep]
            SS = [SS[i] for i in keep]; WC = [WC[i] for i in keep]
        F += fr; E += list(d["eta"]); W += list(d["wall"]); N += list(d["npts"]); SS += list(d["ss_n"])
        WC += list(d["wind_calls"]) if "wind_calls" in d.files else [-1] * len(fr)
        x = d["x"]; z = d["z"]
    F = np.array(F)
    E = np.array(E, np.float32); W = np.array(W); N = np.array(N); SS = np.array(SS); WC = np.array(WC)
    if f_max is not None and len(F):
        k = F <= f_max
        F, E, W, N, SS, WC = F[k], E[k], W[k], N[k], SS[k], WC[k]
    if len(F) == 0:
        raise AnalysisInputError("一番上の水面の記録にコマが 1 つもない：%s" % rd)
    return dict(frames=F, t=(F - 1) / FPS, x=x, z=z, eta=E, wall=W, npts=N, ss_n=SS, wind_calls=WC)


def sec_index(rd):
    """断面の記録の索引。コマ F には、F を含む記録のうち起動の始め f0 が最も大きいもの（後の起動が上書き）を使う。
    1 コマ目の場は初めの網から作った物で、格子の数と箱が違う（FLIP42 の res_changes と同じ）。いちばん多くのコマの格子（meta）に
    合うコマだけを使う。"""
    best = {}
    metas = {}
    for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
        f0 = int(os.path.basename(p)[5:9])
        d = np.load(p)
        m = json.loads(str(d["meta"]))
        key = json.dumps([m["res"], m["y0"], m["x0"], m["nx"]])
        metas[key] = m
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i, key)
    if not best:
        return {}, None
    cnt = {}
    for v in best.values():
        cnt[v[3]] = cnt.get(v[3], 0) + 1
    main = max(cnt, key=cnt.get)
    best = {f: v[:3] for f, v in best.items() if v[3] == main}
    return best, metas[main]


class SecReader:
    def __init__(self, rd):
        self.best, self.meta = sec_index(rd)
        self.cache = {}
        self.frames = sorted(self.best)

    def get(self, f):
        f0, p, i = self.best[f]
        if p not in self.cache:
            self.cache.clear(); self.cache[p] = np.load(p)["sdf"]
        return self.cache[p][i].astype(np.float32)


def still_level(D, xp):
    """計画 N1：0.5〜2.0 s・造波板から 0〜930 m の一番上の水面の中央値。その時刻のコマがない記録（途中保存から始めた計算）や、
    全部 NaN の時は、NaN を返さずに AnalysisInputError で止める（2026-10-12 確かめ F1：NaN が後の nanargmax を落としていた）。"""
    m = (D["t"] >= 0.5) & (D["t"] <= 2.0)
    if not m.any():
        raise AnalysisInputError("静かな水面（計画 N1）を読む 0.5〜2.0 s のコマが記録にない（記録は %.2f〜%.2f s）。途中保存から始めた計算は "
                                 "cfg の from_ckpt の元の計算の値を使う（still_offset）" % (float(D["t"].min()), float(D["t"].max())))
    xm = (D["x"] >= xp) & (D["x"] <= xp + 930.0)
    e = D["eta"][m][:, 2, :][:, xm] if D["eta"].shape[1] >= 3 else D["eta"][m][:, 0, :][:, xm]
    if e.size == 0 or not np.isfinite(e).any():
        raise AnalysisInputError("静かな水面（計画 N1）：0.5〜2.0 s・造波板から 0〜930 m の一番上の水面が全部 NaN か空")
    return float(np.nanmedian(e))


def still_offset(cfg, D, root="runs"):
    """計画 N1 の静かな水面のずれと、どこから取ったか。返り値 (off, info)。
    - 1 コマ目から走らせた計算：この計算の still_level。
    - 途中保存から始めた計算（cfg の from_ckpt。風の計算）：計画 N1「風の計算は形の本番の値を使う」。元の計算（from_ckpt の run、
      from_ckpt に root があればその置き場所、なければこの計算と同じ置き場所）の一番上の水面の記録の 0.5〜2.0 s から出し直す。
      読めなければ元の計算の ana.json の still_level_offset_m、それもなければ cfg の stop_touchdown.still_offset_m（g44_cfg が形の本番の
      ana.json から入れ、still_offset_from に出所を書いた物だけ）。どれもなければ AnalysisInputError。
    - cfg の stop_touchdown.still_offset_m（計算の中の着水の読みが使った値）と 0.005 m より違えば、warning_ja に書く。"""
    xp = cfg["parms"]["x_p"]
    fc = cfg.get("from_ckpt")
    st = cfg.get("stop_touchdown") or {}
    cfg_val = st.get("still_offset_m")
    if not fc:
        return still_level(D, xp), dict(rule_ja="計画 N1：この計算の 0.5〜2.0 s", how="this_run")
    src_root = fc.get("root", root)
    srd = run_dir(fc["run"], src_root)
    info = dict(rule_ja="計画 N1：途中保存から始めた計算は元の計算（形の本番）の値", source_run=fc["run"], source_root=src_root,
                from_frame=int(fc["frame"]), cfg_stop_touchdown_value=cfg_val)
    off = None
    try:
        Ds = load_hf(srd, f_max=int(math.ceil(2.0 * FPS)) + 1)
        scfg = json.load(open(os.path.join(srd, "cfg.json"), encoding="utf8"))
        off = still_level(Ds, scfg["parms"]["x_p"]); info["how"] = "source_hf"
    except Exception as e:
        info["source_hf_error"] = repr(e)[:300]
    if off is None:
        try:
            off = float(json.load(open(os.path.join(srd, "ana.json"), encoding="utf8"))["still_level_offset_m"]); info["how"] = "source_ana_json"
        except Exception as e:
            info["source_ana_error"] = repr(e)[:300]
    if off is None and cfg_val is not None and st.get("still_offset_from"):
        off = float(cfg_val); info["how"] = "cfg_stop_touchdown（%s）" % st.get("still_offset_from")
    if off is None:
        raise AnalysisInputError("途中保存から始めた計算 %s の静かな水面（計画 N1）を決められない：元の計算 %s（%s）の記録も ana.json も読めず、"
                                 "cfg に出所つきの still_offset_m もない" % (cfg.get("run_id"), fc["run"], srd))
    if cfg_val is not None:
        info["cfg_minus_used_m"] = float(cfg_val) - off
        if abs(float(cfg_val) - off) > 0.005:
            info["warning_ja"] = ("計算の中の着水の読み（stop_touchdown）は静かな水面のずれ %.4f m を使ったが、計画 N1 の値は %.4f m（差 %.4f m）。"
                                  "その読み（g44_online.cavity_frame）はずれを記録の高さから引くだけで、穴を見つけたかどうかには使わないので、"
                                  "止めたコマは変わらない" % (float(cfg_val), off, float(cfg_val) - off))
    return off, info


def ckpt_started(cfg, D):
    """途中保存から始めた計算か（from_ckpt があるか、記録の最初のコマが 2 より後）。"""
    return bool(cfg.get("from_ckpt")) or int(D["frames"].min()) > 2


def argmax_or_none(a):
    a = np.asarray(a, float)
    if a.size == 0 or not np.isfinite(a).any():
        return None
    return int(np.nanargmax(a))


def zmean(D):
    nz = D["eta"].shape[1]
    zz = slice(1, nz - 1) if nz >= 3 else slice(0, nz)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)      # 全部 NaN の列（水がない所）は NaN のまま
        return np.nanmean(D["eta"][:, zz, :], axis=1)


def gauge(EX, x, xs):
    i = np.searchsorted(x, xs) - 1
    w = (xs - x[i]) / (x[i + 1] - x[i])
    return (1 - w) * EX[:, i] + w * EX[:, i + 1]


def bed_y(parms, xs):
    h0 = float(parms["h0"])
    if float(parms.get("reef_on", 0.0)) < 0.5:
        return np.full(np.shape(xs), -h0)
    xr = np.asarray(xs) - float(parms["x_p"])
    n = float(parms["rf_slope_n"]); ht = float(parms["rf_h_top"])
    df = h0 - (xr - float(parms["rf_foot"])) / n
    db = ht + (xr - float(parms["rf_top_end"])) / n
    return -np.minimum(h0, np.maximum(ht, np.maximum(df, db)))


# ------------------------------------------------------------------ 線形（入口の表から。造波板の所の目標を平らな 42 m で進める：礁の手前だけで使う）
def k_of_f(fr, h):
    om = 2 * np.pi * np.asarray(fr, float)
    k = np.maximum(om * om / G, om / np.sqrt(G * h))
    pos = om > 0
    for _ in range(60):
        th = np.tanh(k * h)
        fval = G * k * th - om * om
        dfv = G * th + G * k * h * (1 - th * th)
        dk = np.where(pos, fval / np.where(dfv > 0, dfv, 1.0), 0.0)
        k = k - dk
    return np.where(pos, k, 0.0)


def cg_of_f(fr, h):
    k = k_of_f(fr, h); om = 2 * np.pi * np.asarray(fr, float)
    kh = k * h
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(k > 0, om / np.where(k > 0, k, 1), np.sqrt(G * h))
        n = np.where(kh > 1e-6, 0.5 * (1 + 2 * kh / np.sinh(np.minimum(2 * kh, 600))), 1.0)
    return c * n


def rampT(t, R):
    c = np.clip(np.asarray(t) / R, 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * c)


def comps_of(cfg, P):
    """入口の表（FLIP44 の cfg の inlet。FLIP42 の計算は R3 の入口＝PR1 の表）。"""
    inl = cfg.get("inlet") or {**P["programs"]["PR1_R3_flat592"], "rep_P": 0.0}
    f = np.array(inl["freqs_Hz"]); a = np.array(inl["amps_m"]); ph = np.array(inl["phases_rad"])
    return dict(f=f, om=2 * np.pi * f, k=k_of_f(f, 42.0), a=a, ph=ph, ramp=P["tank"]["ramp_s"], name=inl.get("name"),
                df=float(f[1] - f[0]) if len(f) > 1 else 0.0, rep_P=float(inl.get("rep_P", 0.0)))


def target_at_paddle(C, t):
    return rampT(t, C["ramp"]) * (C["a"][None, :] * np.cos(C["ph"][None, :] - C["om"][None, :] * t[:, None])).sum(1)


def lin_series(C, x_rel, t, h=42.0):
    e0 = target_at_paddle(C, t)
    n = 1 << 18
    F = np.fft.rfft(e0, n)
    fr = np.fft.rfftfreq(n, 1 / FPS)
    kk = k_of_f(fr, h)
    return np.fft.irfft(F * np.exp(-1j * kk * x_rel), n)[:len(t)]


def wmean(v, w):
    return float((v * w).sum() / w.sum()) if w.sum() > 0 else float("nan")


# ------------------------------------------------------------------ 断面：全部の頂
def resample(path, ds):
    seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < ds:
        return path
    q = np.arange(0, s[-1], ds)
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], 1)


def poly_area(c):
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def frame_crests(sdf, meta, off, vox, Lc, parms, min_eta=0.5, prom=0.3):
    """1 コマの断面の全部の頂：頂の位置と高さ、前の面の最大の傾き、唇の先、頂の窓の中の空気を囲む閉じた線。座標は場面の x、高さは静かな水面から。"""
    S = sdf.astype(np.float32).copy()
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"])
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - off
    bed = bed_y(parms, xs) - off
    S[ys[:, None] < bed[None, :]] = -1.0          # 海底の中は水として扱う
    j0 = int(np.searchsorted(ys, -25.0))
    S = S[j0:]; ys = ys[j0:]
    lines = []
    for c in measure.find_contours(S, 0.0):
        X = xs[0] + c[:, 1] * meta["dx"]; Y = ys[0] + c[:, 0] * meta["dy"]
        lines.append(np.stack([X, Y], 1))
    if not lines:
        return [], None
    ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
    main = lines[int(np.argmax(ext))]
    if main[0, 0] > main[-1, 0]:
        main = main[::-1]
    # 一番上の水面（列ごとの一番上の水の上の端）
    water = S < 0
    has = water.any(0)
    jt = water.shape[0] - 1 - np.argmax(water[::-1, :], axis=0)
    jt = np.clip(jt, 0, water.shape[0] - 2)
    ii = np.arange(water.shape[1])
    v0 = S[jt, ii]; v1 = S[jt + 1, ii]
    fr_ = np.where(v1 - v0 > 1e-9, -v0 / np.maximum(v1 - v0, 1e-9), 0.0)
    top = np.where(has, ys[jt] + meta["dy"] * np.clip(fr_, 0, 1), np.nan)
    topf = np.nan_to_num(top, nan=-99.0)
    pk, pr = find_peaks(topf, prominence=prom, distance=max(1, int(0.2 * Lc / meta["dx"])))
    closed = [l for l in lines if len(l) > 4 and np.allclose(l[0], l[-1])]
    out = []
    for i in pk:
        if topf[i] < min_eta:
            continue
        xc, yc = float(xs[i]), float(topf[i])
        near = np.where(np.abs(main[:, 0] - xc) <= 2.0 * meta["dx"] + 1e-6)[0]
        if len(near) == 0:
            continue
        ic = int(near[np.argmax(main[near, 1])])
        fwd = main[ic:]
        j_end = len(fwd)
        for j in range(1, len(fwd)):
            if fwd[j, 1] <= 0.0 or fwd[j, 0] - xc > 0.75 * Lc or fwd[j, 0] < xc - 0.75 * Lc:
                j_end = j + 1
                break
        face = resample(fwd[:j_end], 0.5 * vox)
        thmax = float("nan"); tip = None; xv = None
        if len(face) >= 3:
            d = face[2:] - face[:-2]
            th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
            okm = (th >= 0) & (th <= 180)
            if okm.any():
                thmax = float(th[okm].max())
                iv = np.where(okm & (th >= 90))[0]
                xv = float(face[1:-1][iv[0], 0]) if len(iv) else None
            xx = face[:, 0]
            imax = int(np.argmax(xx))
            if imax < len(xx) - 1 and (xx[imax] - xx[imax:].min()) >= vox:
                tip = [float(xx[imax]), float(face[imax, 1])]
        cav = []
        for l in closed:
            A = poly_area(l)
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            if A >= vox * vox and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                ix = int(round((cx - xs[0]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0:
                    cav.append([float(cx), float(cy), float(A)])
        # 前の谷・H（頂から前へ 0.75 Lc までの一番上の水面の最も低い所）
        m = (xs > xc) & (xs <= xc + 0.75 * Lc)
        if m.any() and np.isfinite(top[m]).any():
            jt2 = np.where(m)[0][int(np.nanargmin(top[m]))]
            H = yc - float(top[jt2]); xtr = float(xs[jt2])
        else:
            H = float("nan"); xtr = None
        out.append(dict(xc=xc, eta=yc, thmax=thmax, x_vert=xv, tip=tip, ncav=len(cav), cav=cav[:3], H=H, x_trough=xtr))
    return out, top


def track_crests(rows_by_frame, dx):
    """コマの間で頂をつなぐ：前のコマの頂のうち、x が [x − 8 m, x + 3 m] にあり、x − 0.6 m にいちばん近いもの（高い頂から順に選ぶ）。
    頂は 1 コマに 0.4〜0.6 m 進むが、なだらかな頂の一番高い所は格子の幅で数 m 跳ぶので、窓を広くとった（頂どうしは 0.2 Lc 以上離れる）。"""
    tracks = []
    last = {}
    prev_f = None
    for f in sorted(rows_by_frame):
        rows = rows_by_frame[f]
        used = set()
        assign = []
        for r in sorted(rows, key=lambda r: -r["eta"]):
            best = None
            for tid, (pf, px) in last.items():
                if prev_f is None or pf != prev_f or tid in used:
                    continue
                if r["xc"] - 8.0 <= px <= r["xc"] + 3.0:
                    d = abs(px - (r["xc"] - 0.6))
                    if best is None or d < best[0]:
                        best = (d, tid)
            if best is None:
                tid = len(tracks); tracks.append([])
            else:
                tid = best[1]
            used.add(tid)
            assign.append((tid, r))
        for tid, r in assign:
            tracks[tid].append((f, r)); last[tid] = (f, r["xc"])
        prev_f = f
    return tracks


def track_events(tr, xp, Tc):
    """1 つの頂の巻き始め・着水・着水までの高さの最大。"""
    on = td = None
    emax = -1e9; f_emax = None
    for f, r in tr:
        if on is None:
            if r["eta"] > emax:
                emax, f_emax = r["eta"], f
            if np.isfinite(r["thmax"]) and r["thmax"] >= 90.0:
                on = dict(frame=f, t=(f - 1) / FPS, xc_rel=r["xc"] - xp, x_vert_rel=(r["x_vert"] - xp) if r["x_vert"] is not None else None,
                          eta_c=r["eta"], H=r["H"], thmax=r["thmax"])
        elif td is None:
            if r["eta"] > emax:
                emax, f_emax = r["eta"], f
            if (r["tip"] is not None and r["tip"][1] <= 0.0) or r["ncav"] > 0:
                td = dict(frame=f, t=(f - 1) / FPS, xc_rel=r["xc"] - xp, eta_c=r["eta"], by="tip<=0" if (r["tip"] is not None and r["tip"][1] <= 0.0) else "cavity",
                          tip=r["tip"], cav=r["cav"])
    f0, f1 = tr[0][0], tr[-1][0]
    return dict(first_frame=f0, last_frame=f1, x_first_rel=tr[0][1]["xc"] - xp, x_last_rel=tr[-1][1]["xc"] - xp, eta_max_pre_td=emax,
                frame_eta_max=f_emax, onset=on, touchdown=td, n=len(tr),
                path=[[int(f), round(r["xc"] - xp, 3), round(r["eta"], 3)] for f, r in tr])


def crest_analysis(rd, cfg, off, frames=None, t_from=None):
    parms = cfg["parms"]; xp = parms["x_p"]; vox = 2 * parms["dp"]
    P = plan(); Lc = P["tank"]["Lc"]; Tc = P["tank"]["Tc"]
    SR = SecReader(rd)
    if not SR.frames:
        return None
    rows = {}
    tops = {}
    for f in SR.frames:
        if frames is not None and f not in frames:
            continue
        if t_from is not None and (f - 1) / FPS < t_from:
            continue
        cr, top = frame_crests(SR.get(f), SR.meta, off, vox, Lc, parms)
        rows[f] = cr
    tracks = track_crests(rows, SR.meta["dx"])
    ev = [track_events(tr, xp, Tc) for tr in tracks if len(tr) >= 3]
    return dict(events=ev, frames=[min(rows), max(rows)] if rows else None, meta=SR.meta)


def main_event(events, x_lo=300.0, x_hi=800.0, t_lo=None, t_hi=None):
    """主な巻き波：300〜800 m で、着水までの頂の高さの最大が最も大きい頂（巻き始めがない頂も候補に入れる）。"""
    cand = []
    for e in events:
        if not (x_lo <= e["x_last_rel"] and e["x_first_rel"] <= x_hi):
            continue
        t0 = (e["first_frame"] - 1) / FPS; t1 = (e["last_frame"] - 1) / FPS
        if t_lo is not None and t1 < t_lo:
            continue
        if t_hi is not None and t0 > t_hi:
            continue
        cand.append(e)
    return max(cand, key=lambda e: e["eta_max_pre_td"]) if cand else None


def other_onsets(events, m, Tc, Lc, win_Tc=2.0, x_lo=300.0, x_hi=800.0):
    """主な巻き波 m の巻き始めの ±win_Tc の間に、x_lo〜x_hi で巻き始めたほかの頂（record_ja.md の計画の読み方 13）。
    主な巻き波の巻き始めより後に生まれ、生まれた所が主な頂の巻き始めの位置 − 0.25 Lc より前の頂は、主な巻き波の崩れの一部（しぶき・崩れの後の段）として除く。"""
    on = m["onset"]
    out = []
    for e in events:
        if e is m or e["onset"] is None:
            continue
        o = e["onset"]
        if not (abs(o["t"] - on["t"]) <= win_Tc * Tc and x_lo <= o["xc_rel"] <= x_hi):
            continue
        piece = bool(e["first_frame"] > on["frame"] and e["x_first_rel"] >= on["xc_rel"] - 0.25 * Lc)
        out.append(dict(t=o["t"], frame=o["frame"], xc_rel=o["xc_rel"], eta_c=o["eta_c"], touchdown=e["touchdown"] is not None,
                        born_frame=e["first_frame"], born_x_rel=e["x_first_rel"], piece_of_main=piece))
    return out


def selection_check(events, crit, Tc, Lc=135.46329754326246):
    """計画 §3.3 (a) の 3 条件（下見）。"""
    m = main_event(events)
    if m is None:
        return dict(main=None, pass_=False, why="no crest")
    on, td = m["onset"], m["touchdown"]
    c1 = bool(on is not None and crit["onset_x_window_m"][0] <= on["xc_rel"] <= crit["onset_x_window_m"][1])
    c2 = bool(on is not None and td is not None)
    oth = other_onsets(events, m, Tc, Lc, crit["one_plunger_window_Tc"]) if on is not None else []
    c3 = bool(on is not None and not [o for o in oth if not o["piece_of_main"]])
    return dict(main=m, c1_onset_in_window=c1, c2_plunges_forward=c2, c3_one_plunger=c3, other_onsets=oth, pass_=bool(c1 and c2 and c3))


# ------------------------------------------------------------------ N3・N4・N5・N6・N7
def inlet_bands(EX, x, t, xp, C, win, x_rel=33.865824385815614, subbands=((1, 11), (12, 21), (22, 32))):
    m = (t >= win[0] - 1e-9) & (t <= win[1] + 1e-9)
    em = np.nan_to_num(gauge(EX, x, xp + x_rel)[m]); el = lin_series(C, x_rel, t[m])
    Fm = np.fft.rfft(em); Fl = np.fft.rfft(el); fr = np.fft.rfftfreq(len(em), 1 / FPS)
    R = Fm / np.where(abs(Fl) > 0, Fl, 1); wl = abs(Fl) ** 2
    f = C["f"]; df = C["df"]
    out = []
    for (i0, i1) in subbands:
        if i1 > len(f):
            continue
        mm = (fr >= f[i0 - 1] - df / 2) & (fr <= f[i1 - 1] + df / 2)
        out.append(dict(components=[i0, i1], nbins=int(mm.sum()), amp_ratio=wmean(abs(R[mm]), wl[mm]), phase_rad=wmean(np.angle(R[mm]), wl[mm])))
    return out, (fr, Fm, Fl)


def flux_ratio(EX, x, t, xp, C, win, x_rel):
    m = (t >= win[0] - 1e-9) & (t <= win[1] + 1e-9)
    em = np.nan_to_num(gauge(EX, x, xp + x_rel)[m]); el = lin_series(C, x_rel, t[m])
    Fm = np.fft.rfft(em); Fl = np.fft.rfft(el); fr = np.fft.rfftfreq(len(em), 1 / FPS)
    f = C["f"]; df = C["df"] if C["df"] > 0 else 0.01
    mb = (fr >= f[0] - df / 2) & (fr <= f[-1] + df / 2)
    cg = cg_of_f(fr, 42.0)
    return float((abs(Fm[mb]) ** 2 * cg[mb]).sum() / (abs(Fl[mb]) ** 2 * cg[mb]).sum())


def two_point(EX, x, t, xp, x1, x2, win, fband, h=42.0):
    """Goda & Suzuki（1976）の 2 点の方法：入ってくる波と戻る波の振幅のスペクトル。エネルギーの重みの跳ね返りの係数。
    窓の長さが帯の一番低い周波数の 2 周期に足りない時は、計算せずに理由を返す（確かめ F1：空の配列で止まっていた）。"""
    m = (t >= win[0] - 1e-9) & (t <= win[1] + 1e-9)
    need = 2.0 / max(fband[0], 1e-3)
    if m.sum() < 8 or m.sum() / FPS < need:
        return dict(Kr_energy=None, x=[x1, x2], window_s=list(win), band_Hz=list(fband),
                    skipped_ja="窓の中のコマが %d（%.1f s）で、帯の一番低い周波数の 2 周期 %.1f s に足りない" % (int(m.sum()), m.sum() / FPS, need))
    e1 = np.nan_to_num(gauge(EX, x, xp + x1)[m]); e2 = np.nan_to_num(gauge(EX, x, xp + x2)[m])
    F1 = np.fft.rfft(e1); F2 = np.fft.rfft(e2); fr = np.fft.rfftfreq(len(e1), 1 / FPS)
    k = k_of_f(fr, h)
    mb = (fr >= fband[0]) & (fr <= fband[1])
    if not mb.any():
        return dict(Kr_energy=None, x=[x1, x2], window_s=list(win), band_Hz=list(fband), skipped_ja="帯の中に周波数の刻みが 1 つもない")
    I = np.zeros(len(fr), complex); Rr = np.zeros(len(fr), complex)
    for i in np.where(mb)[0]:
        A = np.array([[np.exp(-1j * k[i] * x1), np.exp(1j * k[i] * x1)], [np.exp(-1j * k[i] * x2), np.exp(1j * k[i] * x2)]])
        if abs(np.sin(k[i] * (x2 - x1))) < 0.15:
            continue
        sol = np.linalg.solve(A, np.array([F1[i], F2[i]]))
        I[i], Rr[i] = sol
    EI = (abs(I[mb]) ** 2).sum(); ER = (abs(Rr[mb]) ** 2).sum()
    return dict(Kr_energy=float(np.sqrt(ER / EI)) if EI > 0 else None, x=[x1, x2], window_s=list(win), band_Hz=list(fband),
                kdx_range=[float(k[mb].min() * (x2 - x1)), float(k[mb].max() * (x2 - x1))])


def lowfreq(EX, x, t, xp, x_rel, fcut=0.03, t_from=0.0):
    m = t >= t_from
    if m.sum() / FPS < 2.0 / fcut:
        return dict(x_rel=x_rel, amp_lowfreq_m=None, skipped_ja="記録が %.1f s で、%.2f Hz の 2 周期 %.0f s に足りない" % (m.sum() / FPS, fcut, 2.0 / fcut))
    e = np.nan_to_num(gauge(EX, x, xp + x_rel)[m])
    F = np.fft.rfft(e - e.mean()); fr = np.fft.rfftfreq(len(e), 1 / FPS)
    F[fr >= fcut] = 0
    lo = np.fft.irfft(F, len(e))
    return dict(x_rel=x_rel, amp_lowfreq_m=float(0.5 * (lo.max() - lo.min())), mean_level_m=float(e.mean()), std_lowfreq_m=float(lo.std()))


def wave_crests(s, min_amp):
    """0 の上向きの交わりの間ごとに頂を 1 つ（その間の最も高い所）。高さ min_amp 以上の物だけ。返り値 [(頂の添字, 前の交わり, 後の交わり)]。
    1 つの頂の上の小さな山を別の頂として数えないため（2026-10-12 確かめ F7 の直し。record_ja.md の途中で決めたこと）。"""
    up = np.where((s[:-1] <= 0) & (s[1:] > 0))[0]
    out = []
    for a, b in zip(up[:-1], up[1:]):
        j = a + 1 + int(np.argmax(s[a + 1:b + 1]))
        if s[j] >= min_amp:
            out.append((j, int(a), int(b)))
    return out


def crest_speeds(EX, x, t, xp, xa, xb, h, min_amp, t_max=None):
    """xa と xb の時系列の頂の時刻の差から、頂の速さを出す（xa の頂の、その周期の線形の速さで来るはずの時刻の ±0.35 周期にある xb の頂と組む）。
    頂は 0 の上向きの交わりの間ごとに 1 つ（wave_crests。両方の点で同じ）。xb の頂は 1 つの xa の頂とだけ組む（時刻の順に、まだ組んでいない
    いちばん近い頂）。頂の時刻は前後の 3 点の放物線で細かくする。周期は xa の時系列の、その頂の前後の上向きの 0 の交わりの間隔。
    振幅は両方の点で min_amp 以上。2026-10-12 の直しの前は、1 つの頂の小さな山を別の頂として拾い、同じ xb の頂と 2〜3 回組んでいた（確かめ F7）。"""
    sa = np.nan_to_num(gauge(EX, x, xp + xa)); sb = np.nan_to_num(gauge(EX, x, xp + xb))

    def tpk(s, j):
        if 0 < j < len(s) - 1:
            d = s[j - 1] - 2 * s[j] + s[j + 1]
            if d < 0:
                return t[j] + 0.5 * (s[j - 1] - s[j + 1]) / d / FPS
        return t[j]
    ca = wave_crests(sa, min_amp); cb = [c[0] for c in wave_crests(sb, min_amp)]
    used = set()
    res = []
    for j, a, b in ca:
        if t_max is not None and t[j] > t_max:
            continue
        T = (b - a) / FPS
        c_lin = float(2 * np.pi / T / k_of_f(np.array([1 / T]), h)[0])
        ta = tpk(sa, j)
        texp = ta + (xb - xa) / c_lin
        cand = [i for i in cb if i not in used and abs(t[i] - texp) <= 0.35 * T]
        if not cand:
            continue
        i = min(cand, key=lambda i: abs(t[i] - texp))
        used.add(i)
        tb_ = tpk(sb, i)
        c = (xb - xa) / (tb_ - ta)
        res.append(dict(t_a=float(ta), t_b=float(tb_), amp_a=float(sa[j]), amp_b=float(sb[i]), T=float(T), c=float(c), c_lin=c_lin, err=float(c / c_lin - 1)))
    return res


# ------------------------------------------------------------------ 本体
def analyze(rid, root="runs", quick=False, out_path=None):
    P = plan()
    rd = run_dir(rid, root)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    xp = cfg["parms"]["x_p"]; Lc = P["tank"]["Lc"]; Tc = P["tank"]["Tc"]
    C = comps_of(cfg, P)
    D = load_hf(rd)
    ck = ckpt_started(cfg, D)
    off, off_info = still_offset(cfg, D, root)
    EX = zmean(D) - off
    t = D["t"]; x = D["x"]
    out = dict(run_id=rid, root=root, dp=cfg["parms"]["dp"], inlet=C["name"], frames_done=int(D["frames"].max()), t_done=float(t.max()),
               frames_first=int(D["frames"].min()), t_first=float(t.min()), started_from_ckpt=ck,
               still_level_offset_m=off, still_level_source=off_info)
    notes = []
    if "warning_ja" in off_info:
        notes.append(off_info["warning_ja"])
    ss = D["ss_n"][D["ss_n"] > 0]
    w1 = D["wall"][1:] if len(D["wall"]) > 1 else D["wall"]
    out["cost"] = dict(wall_per_frame_median=float(np.median(w1)) if len(w1) else None, wall_sum_h=float(D["wall"].sum() / 3600),
                       substeps_hist={str(int(v)): int((ss == v).sum()) for v in np.unique(ss)},
                       particles_max=int(D["npts"].max()) if len(D["npts"]) else None)
    # N2：水面の平均（0.2〜0.6 Lx）
    Lx = cfg["parms"]["Lx"]
    xm = (x > 0.2 * Lx) & (x < 0.6 * Lx)
    with np.errstate(all="ignore"):
        lev = np.nanmean(D["eta"][:, :, xm], axis=(1, 2)) if xm.any() else np.full(len(t), np.nan)
    if np.isfinite(lev).any():
        out["N2_level"] = dict(start=float(lev[0]), min=float(np.nanmin(lev)), drop_max=float(lev[0] - np.nanmin(lev)))
    else:
        out["N2_level"] = dict(start=None, min=None, drop_max=None, skipped_ja="水槽の 0.2〜0.6 の一番上の水面が全部 NaN")
        notes.append("N2：水槽の 0.2〜0.6 の一番上の水面が全部 NaN")
    # 測る点（途中保存から始めた計算では、その計算の区間の中の最大）
    gx = cfg["case"].get("gauges_rel", [33.9, 63.9, 161.0, 220.0, 250.0, 268.8, 300.0, 395.0, 420.0, 450.0, 470.0, 500.0, 530.0, 560.0, 600.0, 700.0])
    out["gauges"] = {}
    out["gauges_window_s"] = [float(t.min()), float(t.max())]
    if ck:
        out["gauges_note_ja"] = "途中保存から始めた計算なので、読む点の最大はこの計算の区間（%.2f〜%.2f s）の中の最大" % (float(t.min()), float(t.max()))
    for g in gx:
        if xp + g > x[-2]:
            continue
        e = gauge(EX, x, xp + g)
        j = argmax_or_none(e)
        if j is None:
            out["gauges"]["%g" % g] = dict(max=None, t_max=None, min=None, skipped_ja="この点の一番上の水面が全部 NaN（水がない）")
            notes.append("読む点 %g m：一番上の水面が全部 NaN" % g)
            continue
        out["gauges"]["%g" % g] = dict(max=float(e[j]), t_max=float(t[j]), min=float(np.nanmin(e)))
    # N3・N4・N5・N6・N7（造波の入口のある計算だけ）。途中保存から始めた計算（風）は読まない
    if ck:
        out["N3_N7_skipped_ja"] = ("途中保存（%s）から始めた計算（%.2f〜%.2f s）なので N3〜N7 は読まない。計画の N3〜N7 は入口と礁の計算"
                                   "（下見・形の本番・繰り返し）の記録で、風の計算の区間は元の計算と同じ入口の続き" % (
                                       json.dumps(cfg.get("from_ckpt"), ensure_ascii=False), float(t.min()), float(t.max())))
    elif float(cfg["parms"].get("amp_gain", 1.0)) > 0 and C["name"]:
        nm = C["name"]
        win = None
        for key in ("PR1_R3_flat592", "PR2_reef_aim500"):
            if nm == key:
                win = P["programs"][key]["band_exit_compare_window_s"]
        if win is None and nm.startswith("PR3"):
            win = [0.0, 122.0]
        if win is not None and t.min() <= win[0] + 1.0 / FPS + 1e-9 and t.max() >= win[1]:
            bands, _ = inlet_bands(EX, x, t, xp, C, win)
            out["N3"] = dict(window_s=win, bands=bands)
            out["N4"] = dict(window_s=win, flux_ratio_exit=flux_ratio(EX, x, t, xp, C, win, 33.865824385815614),
                             flux_ratio_268=flux_ratio(EX, x, t, xp, C, win, 268.8))
            out["N4"]["loss_exit_to_268"] = 1 - out["N4"]["flux_ratio_268"] / out["N4"]["flux_ratio_exit"]
        elif win is not None:
            out["N3"] = dict(window_s=win, skipped_ja="記録（%.2f〜%.2f s）が窓を覆わない" % (float(t.min()), float(t.max())))
        fb = [C["f"][0] - 0.01, C["f"][-1] + 0.01]
        tw = [0.0, float(t.max())]
        out["N6"] = two_point(EX, x, t, xp, 220.0, 250.0, tw, fb)
        out["N6_band_exit"] = two_point(EX, x, t, xp, 33.9, 63.9, tw, fb)
        out["N7"] = [lowfreq(EX, x, t, xp, xr) for xr in (33.9, 500.0) if xp + xr < x[-2]]
        # N5：群の前を行く頂（その点の最大の頂より前の時刻）、振幅が格子 2 個以上
        vox = 2 * cfg["parms"]["dp"]
        try:
            ja = argmax_or_none(gauge(EX, x, xp + 161.0)); jr = argmax_or_none(gauge(EX, x, xp + 470.0))
            if ja is None or jr is None:
                raise AnalysisInputError("N5：161 m か 470 m の一番上の水面が全部 NaN")
            t_off = float(t[ja]); t_reef = float(t[jr])
            off_ = crest_speeds(EX, x, t, xp, 161.0, 268.8, 42.0, 2 * vox, t_max=t_off)
            hr = 12.0 if float(cfg["parms"].get("reef_on", 0)) > 0.5 else 42.0
            reef_ = crest_speeds(EX, x, t, xp, 470.0, 530.0, hr, 2 * vox, t_max=t_reef)
            out["N5"] = dict(offshore=off_, reef=reef_, h_reef=hr, pairing="one_far_crest_per_crest（2026-10-12）",
                             err_range_offshore=[min(r["err"] for r in off_), max(r["err"] for r in off_)] if off_ else None,
                             err_range_reef=[min(r["err"] for r in reef_), max(r["err"] for r in reef_)] if reef_ else None,
                             ratio_reef_over_offshore=(float(np.mean([r["c"] for r in reef_]) / np.mean([r["c"] for r in off_])) if off_ and reef_ else None),
                             linear_ratio=P["reef"]["linear_speed_fc"]["ratio"])
        except Exception as e:
            out["N5"] = dict(error=repr(e)[:200])
            notes.append("N5：" + repr(e)[:200])
    # 断面：頂ごとの巻き始めと着水、(a) の判定
    if not quick:
        CA = crest_analysis(rd, cfg, off)
        if CA:
            out["events"] = CA["events"]
            sel = selection_check(CA["events"], P["criteria"]["selection"], Tc, Lc)
            m = sel["main"]
            out["selection_a"] = {k: v for k, v in sel.items() if k != "main"}
            out["main"] = m
            out["onset"] = m["onset"] if m else None
            out["touchdown"] = m["touchdown"] if m else None
            if m is None:
                notes.append("断面：300〜800 m に主な頂がない")
            elif m["onset"] is None:
                notes.append("断面：主な頂は巻き始めていない（記録 %.2f〜%.2f s）" % (float(t.min()), float(t.max())))
            elif m["touchdown"] is None:
                notes.append("断面：主な頂は巻き始めたが、記録の中で着水していない")
            if m is not None and m["onset"] is not None and m["onset"]["frame"] <= m["first_frame"]:
                # 2026-10-12 確かめ G5：断面が巻き始めより後から始まると、巻き始めを遅く読む。その時は書く（読みは変えない）
                sec0 = CA["frames"][0] if CA.get("frames") else None
                msg = ("断面：主な頂は、その頂の道の最初のコマ（%d コマ%s）ですでに巻いていた。本当の巻き始めはそれより前の見込みで、"
                       "巻き始めのコマ・時刻・η_c は遅い側に読んでいる" % (m["first_frame"], "。断面の記録の始め" if sec0 == m["first_frame"] else ""))
                notes.append(msg)
                out["onset_at_path_start"] = msg
        else:
            out["onset"] = out["touchdown"] = None
            notes.append("断面の記録（sec_c*.npz）がない")
    out["notes_ja"] = notes
    json.dump(out, open(out_path or os.path.join(rd, "ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


# ------------------------------------------------------------------ 区切った起動の後の止める決まり（g44_chain.py の stop_check）
def stop_main_touchdown(rid, root, t_done, cfg, n_Tc=2.0):
    """主な巻き波の着水 + 2 Tc を過ぎ、かつ線形の焦点の時刻 + 1 Tc を過ぎたら止める（record_ja.md の計画の読み方）。"""
    P = plan(); Tc = P["tank"]["Tc"]
    rd = run_dir(rid, root)
    D = load_hf(rd)
    off = still_offset(cfg, D, root)[0]
    t_from = max(0.0, t_done - 60.0)
    CA = crest_analysis(rd, cfg, off, t_from=float(cfg["sec"]["t0"]))
    if not CA:
        return False, "no section yet"
    m = main_event(CA["events"])
    if m is None or m["touchdown"] is None:
        return False, "main touchdown not yet"
    t_td = m["touchdown"]["t"]
    t_aim = float(cfg["case"].get("aim_t_s", 0.0))
    stop = bool(t_done >= t_td + n_Tc * Tc and t_done >= t_aim + Tc)
    return stop, dict(t_done=t_done, main_onset=m["onset"], main_touchdown=m["touchdown"], t_aim=t_aim)


def select(pr1, pr2, root="runs"):
    """計画 §3.3 (a)：両方入れば PR1、片方なら入った方、どちらも外れたら PR3 の狙い。"""
    P = plan(); cr = P["criteria"]["selection"]
    a1 = json.load(open(os.path.join(run_dir(pr1, root), "ana.json"), encoding="utf8"))
    a2 = json.load(open(os.path.join(run_dir(pr2, root), "ana.json"), encoding="utf8"))
    s1 = a1.get("selection_a", {}).get("pass_"); s2 = a2.get("selection_a", {}).get("pass_")
    if s1:
        choice = "PR1"
    elif s2:
        choice = "PR2"
    else:
        choice = "PR3"
    out = dict(PR1=a1.get("selection_a"), PR2=a2.get("selection_a"), PR1_onset=a1.get("onset"), PR2_onset=a2.get("onset"), choice=choice,
               rule_ja=cr["rule_ja"])
    if choice == "PR3":
        on2 = a2.get("onset")
        if on2:
            aim = 500.0 + (cr["reaim_center_m"] - on2["xc_rel"])
            aim = min(max(aim, cr["reaim_window_m"][0]), cr["reaim_window_m"][1])
            out["PR3_aim_m"] = cr["reaim_round_m"] * round(aim / cr["reaim_round_m"])
            out["PR3_command"] = "py -3.10 Tools/GWWaveGen/flip44/p_plan_numbers.py --aim3 %g" % out["PR3_aim_m"]
        else:
            out["PR3_aim_m"] = None
            out["note_ja"] = "下見 2 に巻き始めがないので、決まりの式で狙いを出せない。止めて伺う"
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--flip42":
        rid = a[1]
        os.makedirs(B44 + "/check", exist_ok=True)
        o = analyze(rid, "flip42", out_path=os.path.join(B44, "check", "ana44_%s.json" % rid))
    elif a[0] == "--select":
        o = select(a[1], a[2], a[3] if len(a) > 3 else "runs")
        json.dump(o, open(os.path.join(B44, a[4] if len(a) > 4 else "runs", "select.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
        print(json.dumps({k: o[k] for k in o if k in ("choice", "PR3_aim_m", "PR3_command", "note_ja")}, ensure_ascii=False))
        sys.exit(0)
    else:
        rid = a[0]; root = a[1] if len(a) > 1 and not a[1].startswith("--") else "runs"
        outp = a[a.index("--out") + 1] if "--out" in a else None      # 試しの時だけ：ana.json を別の所へ書く
        try:
            o = analyze(rid, root, quick="--quick" in a, out_path=outp)
        except AnalysisInputError as e:
            print("解析を止めた（記録が足りない）：%s" % e, file=sys.stderr)
            sys.exit(3)
    print(json.dumps({k: o.get(k) for k in ("run_id", "still_level_offset_m", "still_level_source", "onset", "touchdown", "selection_a", "N2_level", "notes_ja")}, ensure_ascii=False, default=float)[:3000])
    for k in ("N3", "N4", "N6", "N6_band_exit", "N7"):
        if k in o:
            print(k, json.dumps(o[k], ensure_ascii=False, default=float)[:600])
    if "N5" in o:
        n5 = o["N5"]
        print("N5 ratio", n5.get("ratio_reef_over_offshore"), "offshore", [round(r["err"], 3) for r in n5.get("offshore", [])][:8], "reef", [round(r["err"], 3) for r in n5.get("reef", [])][:8])
