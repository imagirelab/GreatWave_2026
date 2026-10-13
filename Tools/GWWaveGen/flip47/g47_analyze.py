# -*- coding: utf-8 -*-
"""FLIP47：2D の板の計算の記録（板の真ん中の断面の水面の場）から、崩れ・着水・唇と巻きの量を読み、図を描く。
py -3.10 -B で走らせる（numpy・scipy・scikit-image・PIL。__pycache__ を作らない）。読むだけ。書くのは Unity/Build/FLIP47 の中だけ。

計画：Docs/Research/BigWave_Recipes_ja.md §5.1「E1a」（Feddersen・Hanson・Mostert・Fincham 2024、JFM 1000 A48 を h0 19 m で）。
論文の定義（2026-10-12 に本文 §3.3・§3.4 と図 5〜7 の説明を Cambridge Core の本文で読んだ。式の番号は論文の物）：
  Hb   ：空気と水の境の最も高い所（静かな水面 z = 0 から。前に谷がないので 0 から測る）。図 6 は着水の時刻の図で、Hb もその時刻の値と読んだ
         （本文は時刻を書いていない）。
  着水 ：噴流のいちばん低い所と、その下の水面の縦の隙間 Δz が Δz/h0 ≤ 0.015 になる最初の時刻（a0 の 2.5%、最も細かい格子の約 4 倍）。
         出力の間隔の都合で、すでに触れていた時はその時刻を着水とする。
  xbp  ：Δz がいちばん小さい所の x（すでに触れていた時は、別の決まり：本文「z/h0 = 0 を切る最も小さい x」。下の注 2）。
  AJ   ：噴流の面積。水面が x について多価になる上の所（図 6 の灰色）。AJ/Hb² で比べる。
  Ao   ：巻きの面積。巻きの中の空気を囲む線（図 6 の赤）の中。Ao/Hb²。
  W・L・θo：巻きの線を θo だけ回して横にし、Longuet-Higgins の形（式 3.1）z'/W = ±(3√3/4)√(x'/L)(x'/L − 1) に当てはめる。
         θo は巻きの向きと水平の角（task の「噴流の向き 29°」はこれ）。当てはめ方は Feddersen ら 2023（JFM 958 A4）§3.4 に従い、
         5 つの数（L・W・θ・巻きの後ろの点 x0・z0）を、線の点から曲線までの最短の距離の 2 乗の平均が最小になるように Nelder–Mead で決める。
         2023 の面積の式（3.2）は A = (2√3/5) L W。楕円ではない。
  噴流の幅：論文は「横切りの幅 約 0.05 h0」とだけ書き、測り方を書いていない。ここでは計画 §5.1 の決まり：噴流の軸に沿って、根元から
         先までの長さの半分の所で、軸に直角の幅（内に入る最大の円の直径）。
  論文の値（風なし Re* = 0）：Hb/h0 0.64、xbp/h0 42.05（風の 8 本で 40.9〜42.2）、着水 t̃ 19.96、AJ/Hb² 0.219、Ao/Hb² 0.352、W/L 0.300、θo 29°。
  論文の計算は 2 相（空気あり）・表面張力あり（Bo 4000、Re 4×10⁴）・Basilisk の最小格子 h0/270。私たちは水だけ・重力だけ・実物の大きさ。
注 1：私たちの読み（論文にない物）：巻き始め＝前の面に初めて鉛直の接線（FLIP42・44 と同じ。前の面の線に沿って格子 1 個分の弦の向きが
      90° 以上）。Hb_onset＝その時刻の頂の高さ（静かな水面から）。
注 2：「すでに触れていた」時の xbp は、閉じた空気の穴の前の端（噴流の先が下の水に触れた所）の x にした（本文の言い方は読み切れなかった）。
同じ物差し：Unity/Build/STUDY52/tools/s52_shape.py の measure_mask（変えずに読む）。水の格子は STUDY52 の flip_mask と同じ作り方
  （記録の場を 0.05 m に一次の補間、頂の x の ±105 m、静かな水面の 12 m 下から頂の 1.5 m 上、底につながる水だけ）。
  違いは 1 つ：海底の中を水にした（棚の上で 12 m 下が海底の中になるため。STUDY52 の FLIP42 は深い平らな所なので同じ）。

使い方：
  py -3.10 -B g47_analyze.py <記録の置き場所> [--out=<置き場所>] [--h0=19] [--off=<m>] [--xref=<m>] [--f0=<コマ>] [--f1=<コマ>]
         [--t0=<s>] [--t1=<s>] [--xwin=<a>,<b>] [--kind=sec|r2] [--name=<名前>] [--label=<図の頭の言葉>] [--nofig] [--after=<コマ>]
     → <out>/g47_ana.json、<out>/<名前>_section_zoom.png、<out>/<名前>_print_overlay.png、<out>/<名前>_masks.npz
     out の既定：記録が Unity/Build/FLIP47 の中なら <記録>/ana47、外なら Unity/Build/FLIP47/smoke/test_<名前>
     x は計画の座標（FLIP47 は論文の x と同じ。cfg に x_p があれば x − x_p＝FLIP42・44 の「造波板から」）。--xref で変えられる。
  py -3.10 -B g47_analyze.py --table <記録か g47_ana.json> ... [--csv=<path>]   → 1 本 1 行の表（Markdown）。論文・原画・FLIP42 R3 の行も付ける
"""
import sys, os, json, math, glob, time
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from skimage import measure
from skimage.graph import MCP_Geometric
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B47 = REPO + "/Unity/Build/FLIP47"
STUDY52 = REPO + "/Unity/Build/STUDY52"
sys.path.insert(0, STUDY52 + "/tools")
import s52_shape as S52          # noqa: E402  同じ物差し（読むだけ）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import g47_targets as TG     # noqa: E402  原画の帯と点数（文献と組の案の役が書いた targets_ja.md §5 の決まり。読むだけ）
except Exception:                # 点数がなくても他の読みはできる
    TG = None

G = 9.80665
FPS = 24.0
FINE = 0.05                      # 水の格子の間隔（m）。STUDY52 と同じ
HALF = 105.0                     # 頂の x の ±105 m（STUDY52 と同じ）
ZLO = -12.0                      # 静かな水面の 12 m 下から（STUDY52 と同じ）
LC_S52 = 135.4633                # measure_mask の谷を探す窓 ±0.75 Lc（STUDY52 の FLIP42 の値をそのまま。孤立波には波長がない）
GAP_H0 = 0.015                   # 着水の隙間 Δz/h0（論文 §3.3）
LH_C = 3.0 * math.sqrt(3.0) / 4.0
LH_AREA = 2.0 * math.sqrt(3.0) / 5.0   # Feddersen ら 2023 式 (3.2)

PAPER = dict(
    source="Feddersen, Hanson, Mostert & Fincham 2024, J. Fluid Mech. 1000, A48（風なし Re* = 0）。§3.3〜3.5・図 5〜7",
    Hb_h0=0.64, xbp_h0=42.05, xbp_h0_wind_range=[40.9, 42.2], t_impact_tilde=19.96,
    AJ_Hb2=0.219, AO_Hb2=0.352, W_L=0.300, theta_o_deg=29.0, jet_width_h0=0.05, jet_width_Hb=0.05 / 0.64,
    gap_h0=GAP_H0, two_phase=True, Bo=4000, Re=4.0e4, dx_min_h0=3.7e-3,
    note_ja="2 相（空気あり）・表面張力あり（Bo 4000）。噴流の幅 0.05 h0 は本文の「横切りの幅」で、測り方は書かれていない")

BG = (247, 247, 244); WATER = (38, 86, 128); SAND = (196, 178, 140); LINE = (150, 150, 150)
TXT = (25, 25, 25); SUB = (95, 95, 92); RED = (200, 40, 40)
FONT = "C:/Windows/Fonts/YuGothM.ttc"; FONTB = "C:/Windows/Fonts/YuGothB.ttc"


def font(sz, b=False):
    return ImageFont.truetype(FONTB if b else FONT, sz)


class InputError(ValueError):
    pass


# ======================================================================== 小さな道具
def runs(b):
    """1 列の水の続き [(始め, 終わり), ...]（行の番号、下から）。s52_shape.runs と同じ。"""
    return S52.runs(b)


def groups_of(idx):
    idx = sorted(idx)
    if not idx:
        return []
    out, g = [], [idx[0]]
    for i in idx[1:]:
        if i == g[-1] + 1:
            g.append(i)
        else:
            out.append(g); g = [i]
    out.append(g)
    return out


def fnum(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    try:
        v = float(v)
    except Exception:
        return v
    return v if math.isfinite(v) else None


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float, np.integer, int, np.bool_, bool)) or o is None:
        return fnum(o)
    return o


def guard_out(p):
    a = os.path.abspath(p).replace("\\", "/")
    if not a.lower().startswith(os.path.abspath(B47).replace("\\", "/").lower()):
        raise InputError("書く所は Unity/Build/FLIP47 の中だけ：%s" % a)
    return a


# ======================================================================== 記録
class Rec:
    """断面の水面の場の記録（<kind>_c*_b*.npz：sdf[コマ, 縦, x]・frames・t・meta）。同じコマは後の起動の物（FLIP42〜46 と同じ）。
    1 コマ目の場は格子が違うことがあるので、いちばん多くのコマの格子（meta）に合うコマだけを使う（g44_analyze.sec_index と同じ）。"""

    def __init__(self, rd, kind):
        best, metas = {}, {}
        for p in glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind)):
            b = os.path.basename(p)
            f0 = int(b.split("_c")[1].split("_")[0])
            d = np.load(p)
            m = json.loads(str(d["meta"]))
            key = json.dumps([m.get("res"), m["y0"], m["x0"], m.get("nx"), m["dx"], m["dy"]])
            metas[key] = m
            ts = d["t"] if "t" in d.files else None
            for i, f in enumerate(d["frames"]):
                f = int(f)
                if f >= f0 and (f not in best or best[f][0] <= f0):
                    best[f] = (f0, p, i, key, float(ts[i]) if ts is not None else (f - 1) / FPS)
        if not best:
            raise InputError("断面の記録（%s_c*_b*.npz）がない：%s" % (kind, rd))
        cnt = {}
        for v in best.values():
            cnt[v[3]] = cnt.get(v[3], 0) + 1
        main = max(cnt, key=cnt.get)
        self.best = {f: v for f, v in best.items() if v[3] == main}
        self.meta = metas[main]
        self.frames = sorted(self.best)
        self.dropped = sorted(f for f, v in best.items() if v[3] != main)
        self._p = None; self._d = None

    def t(self, f):
        return self.best[f][4]

    def get(self, f):
        f0, p, i, _, _ = self.best[f]
        if p != self._p:
            self._d = np.load(p)["sdf"]; self._p = p
        return self._d[i].astype(np.float32)


def load_cfg(rd):
    for nm in ["cfg.json"] + sorted(os.path.basename(p) for p in glob.glob(os.path.join(rd, "cfg_*.json"))):
        p = os.path.join(rd, nm)
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf8")), nm
            except Exception:
                continue
    return {}, None


def bed_from_parms(P):
    """FLIP47 の海底（cfg の bed＝[[x, 水深], ...] か bed_prof＝「x0 d0 x1 d1 ...」、計画の座標）。なければ None。"""
    b = P.get("bed")
    if b is None and P.get("bed_prof"):
        v = [float(t) for t in str(P["bed_prof"]).split()]
        b = [[v[2 * i], v[2 * i + 1]] for i in range(len(v) // 2)]
    if not b:
        return None
    bx = np.array([float(p[0]) for p in b]); bd = np.array([float(p[1]) for p in b])
    return lambda x: -np.interp(np.asarray(x, float), bx, bd)


class Ctx:
    """1 本の計算の読み方（記録・静かな水面・x の基準・海底）。"""

    def __init__(self, rd, opt):
        self.rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
        self.name = opt.get("name") or os.path.basename(self.rd)
        self.cfg, self.cfg_name = load_cfg(self.rd)
        P = dict(self.cfg.get("parms") or {})
        self.P = P
        kind = opt.get("kind")
        if not kind:
            kind = "sec" if glob.glob(os.path.join(self.rd, "sec_c*_b*.npz")) else "r2"
        self.kind = kind
        self.rec = Rec(self.rd, kind)
        m = self.rec.meta
        self.vox = float(m["dx"])
        self.dp = float(P.get("dp", 0.5 * self.vox))
        self.h0 = float(opt["h0"]) if opt.get("h0") is not None else float(P.get("h0", 19.0))
        self.TS = math.sqrt(self.h0 / G)
        self.t_ic = float(P.get("t_off", 0.0))
        # x の基準
        if opt.get("xref") is not None:
            self.xref, self.xref_src = float(opt["xref"]), "指定（--xref）"
        elif self.cfg.get("ana_xref") is not None:      # 2026-10-13 周期の波の実験の役：cfg の ana_xref（既定なし＝前と同じ）
            self.xref, self.xref_src = float(self.cfg["ana_xref"]), "cfg の ana_xref（周期の波：計画の座標のまま）"
        elif "x_p" in P:
            self.xref, self.xref_src = float(P["x_p"]), "cfg の x_p（FLIP42・44：造波板から）"
        else:
            self.xref, self.xref_src = 0.0, "計画の座標のまま（FLIP47：論文の x と同じ）"
        self.off, self.off_src = self.still_offset(opt)
        nx = int(m.get("nx", m.get("res", [0])[0])); ny = int(m.get("ny", 0)) or self.rec.get(self.rec.frames[0]).shape[0]
        self.xs = float(m["x0"]) + float(m["dx"]) * np.arange(nx) - self.xref
        self.ys = float(m["y0"]) + float(m["dy"]) * np.arange(ny) - self.off
        self.bedf, self.bed_src = self.bed_profile()
        self.thr = GAP_H0 * self.h0
        self.x0_crest = None
        for k in ("x0_crest", "sol_x0", "x0_sol", "crest_x0"):
            if k in P:
                self.x0_crest = float(P[k]) - self.xref; break
        if self.x0_crest is None and isinstance(self.cfg.get("solitary"), dict) and "x0" in self.cfg["solitary"]:
            self.x0_crest = float(self.cfg["solitary"]["x0"]) - self.xref

    # ---- 静かな水面のずれ（N1）
    def still_offset(self, opt):
        if opt.get("off") is not None:
            return float(opt["off"]), "指定（--off）"
        if self.cfg.get("still_offset_m") is not None:
            return float(self.cfg["still_offset_m"]), "cfg の still_offset_m"
        for p in sorted(glob.glob(os.path.join(self.rd, "run_c*.json"))):
            try:
                o = ((json.load(open(p, encoding="utf8")).get("info") or {}).get("still_offset_online") or {})
                if o.get("value") is not None:
                    return float(o["value"]), "計算の中で測った値（%s の still_offset_online）" % os.path.basename(p)
            except Exception:
                pass
        for nm, key in (("run.json", "still_offset"), ("ana.json", "still_level_offset_m")):
            p = os.path.join(self.rd, nm)
            if os.path.exists(p):
                try:
                    v = json.load(open(p, encoding="utf8")).get(key)
                    v = v.get("value") if isinstance(v, dict) else v
                    if v is not None:
                        return float(v), "%s の %s" % (nm, key)
                except Exception:
                    pass
        # 最後の手：記録の始めの 0.5〜2.0 s（なければ始めの 1 s）の一番上の水面の中央値（頂から 4 h0 より遠い所）
        fr = [f for f in self.rec.frames if 0.5 - 1e-9 <= self.rec.t(f) - self.t_ic <= 2.0 + 1e-9] or self.rec.frames[:24]
        m = self.rec.meta
        xs = float(m["x0"]) + float(m["dx"]) * np.arange(int(m.get("nx", m.get("res", [0])[0])))
        ys = float(m["y0"]) + float(m["dy"]) * np.arange(self.rec.get(fr[0]).shape[0])
        vals = []
        for f in fr:
            top = top_surface(self.rec.get(f), ys)
            if not np.isfinite(top).any():
                continue
            ic = int(np.nanargmax(top))
            far = np.abs(xs - xs[ic]) > 4.0 * float((self.cfg.get("parms") or {}).get("h0", 19.0))
            if far.any() and np.isfinite(top[far]).any():
                vals.append(float(np.nanmedian(top[far])))
        if not vals:
            raise InputError("静かな水面のずれを決められない（--off で与える）")
        return float(np.median(vals)), "記録の始めのコマ %d〜%d の一番上の水面の中央値（頂から 4 h0 より遠い所。目安）" % (fr[0], fr[-1])

    # ---- 海底
    def bed_profile(self):
        PB = dict(self.P)
        if "bed" not in PB and "bed_prof" not in PB and self.cfg.get("bed"):
            PB["bed"] = self.cfg["bed"]                    # FLIP47 の cfg は bed を上の段に置く（g47_cfg.py）
        f = bed_from_parms(PB)
        if f is not None:
            return (lambda x: f(np.asarray(x) + self.xref) - self.off), "cfg の bed（計画の座標の折れ線）"
        # 記録の最初のコマで、列ごとの一番下の水の下の端を海底とみなす（記録の下の端まで水なら海底は記録の外）
        f0 = self.rec.frames[0]
        S = self.rec.get(f0)
        water = S < 0
        has = water.any(0)
        jl = np.argmax(water, axis=0)
        dy = float(self.ys[1] - self.ys[0])
        b = np.where(has & (jl > 0), self.ys[jl] - 0.5 * dy, -np.inf)
        bm = ndi.median_filter(np.where(np.isfinite(b), b, -1e4), size=5)
        b = np.where(bm < -1e3, -np.inf, bm)
        xs = self.xs.copy()
        src = "記録の最初のコマ %d の列ごとの一番下の水（cfg に海底がないので）" % f0

        def fb(x):
            x = np.asarray(x, float)
            i = np.clip(np.round((x - xs[0]) / (xs[1] - xs[0])).astype(int), 0, len(xs) - 1)
            return b[i]
        return fb, src

    def sdf(self, f, fill_bed=True):
        """コマ f の場（水で負）。fill_bed：海底の中を水（−1）にする。"""
        S = self.rec.get(f)
        if fill_bed:
            bb = self.bedf(self.xs)
            pad = 0.5 * self.vox if self.bed_src.startswith("cfg") else 0.0
            S[self.ys[:, None] < (bb[None, :] + pad)] = -1.0
        return S

    def t(self, f):
        return self.rec.t(f)

    def tt(self, t):
        """論文の時間 t̃ = (t − t0)·√(g/h0)。"""
        return (t - self.t_ic) / self.TS


# ======================================================================== 粗い読み（記録の格子のまま）：頂と前の面の向き
def top_surface(S, ys):
    water = S < 0
    has = water.any(0)
    jt = water.shape[0] - 1 - np.argmax(water[::-1, :], axis=0)
    jt = np.clip(jt, 0, water.shape[0] - 2)
    ii = np.arange(water.shape[1])
    v0 = S[jt, ii]; v1 = S[jt + 1, ii]
    fr = np.where(v1 - v0 > 1e-9, -v0 / np.maximum(v1 - v0, 1e-9), 0.0)
    return np.where(has, ys[jt] + (ys[1] - ys[0]) * np.clip(fr, 0, 1), np.nan)


def resample(path, ds):
    seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < ds:
        return path
    q = np.arange(0, s[-1], ds)
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], 1)


def coarse_frame(cx, f, prev_x=None, xwin=None):
    """頂（一番上の水面の山）と、頂から前の面の線の向き（FLIP42・44 の巻き始めの読み：線に沿って格子 1 個分の弦の向き）。"""
    S = cx.sdf(f)
    xs, ys = cx.xs, cx.ys
    top = top_surface(S, ys)
    topf = np.nan_to_num(top, nan=-99.0)
    if xwin is not None:
        topf = np.where((xs >= xwin[0]) & (xs <= xwin[1]), topf, -99.0)
    dist = max(1, int(min(27.0, 1.5 * cx.h0) / (xs[1] - xs[0])))
    pk, _ = find_peaks(topf, prominence=0.3, distance=dist)
    pk = [i for i in pk if topf[i] >= 0.5]
    if prev_x is None:
        cand = pk
    else:
        cand = [i for i in pk if prev_x - 6.0 <= xs[i] <= prev_x + 12.0]
    if not cand:
        if not pk:
            i = int(np.argmax(topf))
        else:
            i = min(pk, key=lambda k: abs(xs[k] - (prev_x if prev_x is not None else xs[k])))
        lost = prev_x is not None
    else:
        i = max(cand, key=lambda k: topf[k]); lost = False
    xc, yc = float(xs[i]), float(topf[i])
    lines = []
    for c in measure.find_contours(S, 0.0):
        lines.append(np.stack([xs[0] + c[:, 1] * (xs[1] - xs[0]), ys[0] + c[:, 0] * (ys[1] - ys[0])], 1))
    thmax = float("nan"); xv = None
    if lines:
        ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
        main = lines[int(np.argmax(ext))]
        if main[0, 0] > main[-1, 0]:
            main = main[::-1]
        near = np.where(np.abs(main[:, 0] - xc) <= 2.0 * (xs[1] - xs[0]) + 1e-6)[0]
        if len(near):
            ic = int(near[np.argmax(main[near, 1])])
            fwd = main[ic:]
            j_end = len(fwd)
            for j in range(1, len(fwd)):
                if fwd[j, 1] <= 0.0 or abs(fwd[j, 0] - xc) > 3.0 * cx.h0:
                    j_end = j + 1
                    break
            face = resample(fwd[:j_end], 0.5 * cx.vox)
            if len(face) >= 3:
                d = face[2:] - face[:-2]
                th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
                okm = (th >= 0) & (th <= 180)
                if okm.any():
                    thmax = float(th[okm].max())
                    iv = np.where(okm & (th >= 90))[0]
                    xv = [float(face[1:-1][iv[0], 0]), float(face[1:-1][iv[0], 1])] if len(iv) else None
    return dict(frame=int(f), t=cx.t(f), xc=xc, eta=yc, thmax=thmax, x_vert=xv, lost=lost)


# ======================================================================== 細かい水の格子（STUDY52 flip_mask と同じ作り方）
def fine_mask(cx, f, xc_hint, half=HALF, zlo=ZLO, S=None):
    if S is None:
        S = cx.sdf(f)
    xs, ys = cx.xs, cx.ys
    water = S < 0
    win = np.abs(xs - xc_hint) <= 60.0
    rows = np.where((water & win[None, :]).any(1))[0]
    jt = rows.max()
    xc0 = float(xs[np.where(water[jt] & win)[0]].mean())
    X = np.arange(xc0 - half, xc0 + half, FINE)
    Z = np.arange(zlo, ys[jt] + 1.5, FINE)
    dxr = xs[1] - xs[0]; dyr = ys[1] - ys[0]
    fx = (X - xs[0]) / dxr; fz = (Z - ys[0]) / dyr
    ix = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2); wx = np.clip(fx - ix, 0.0, 1.0)
    iz = np.clip(np.floor(fz).astype(int), 0, len(ys) - 2); wz = np.clip(fz - iz, 0.0, 1.0)
    A = S[iz][:, ix] * (1 - wx)[None, :] + S[iz][:, ix + 1] * wx[None, :]
    B = S[iz + 1][:, ix] * (1 - wx)[None, :] + S[iz + 1][:, ix + 1] * wx[None, :]
    F = A * (1 - wz)[:, None] + B * wz[:, None]
    M = F < 0
    lab = measure.label(M, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        k = np.bincount(keep).argmax()
        M = lab == k
    return M, X, Z


# ======================================================================== 噴流と巻き（論文の量）
def lh_curve(p, n=400):
    L, W, th, x0, z0 = p
    s = np.linspace(0.0, 1.0, n)
    xp = L * s; zp = W * LH_C * np.sqrt(s) * (s - 1.0)
    xp = np.concatenate([xp, xp[::-1]]); zp = np.concatenate([zp, -zp[::-1]])
    c, sn = math.cos(th), math.sin(th)
    return np.stack([x0 + xp * c + zp * sn, z0 - xp * sn + zp * c], 1)


def lh_fit(pts, tip, area=None):
    """Longuet-Higgins の形（式 3.1）を巻きの線の点に当てはめる。θ は時計回り（先が下がる向きが正）。
    Feddersen ら 2023 §3.4：5 つの数（L・W・θ・後ろの点 x0・z0）、最短の距離の 2 乗の平均を最小に（Nelder–Mead）。"""
    pts = np.asarray(pts, float)
    if len(pts) > 500:
        pts = pts[np.linspace(0, len(pts) - 1, 500).astype(int)]
    tip = np.asarray(tip, float)
    d = np.hypot(pts[:, 0] - tip[0], pts[:, 1] - tip[1])
    back = pts[int(np.argmax(d))]
    v = tip - back
    L0 = float(np.hypot(*v)); th0 = math.atan2(-v[1], v[0])
    W0 = float(area / (LH_AREA * L0)) if area else 0.35 * L0
    sc = max(L0, 1e-6)

    def cost(q):
        L, W, th, x0, z0 = q[0] * sc, q[1] * sc, q[2], q[3] * sc, q[4] * sc
        if L <= 0 or W <= 0:
            return 1e9
        cur = lh_curve((L, W, th, x0, z0))
        dd, _ = cKDTree(cur).query(pts)
        return float(np.mean((dd / sc) ** 2))
    best = None
    for dth in (0.0, math.radians(10), -math.radians(10)):
        q0 = np.array([L0 / sc, W0 / sc, th0 + dth, back[0] / sc, back[1] / sc])
        r = minimize(cost, q0, method="Nelder-Mead", options=dict(maxiter=6000, xatol=1e-6, fatol=1e-12))
        if best is None or r.fun < best.fun:
            best = r
    q = best.x
    L, W, th, x0, z0 = q[0] * sc, q[1] * sc, q[2], q[3] * sc, q[4] * sc
    return dict(L=L, W=W, W_L=W / L, theta_deg=math.degrees(th), x0=x0, z0=z0, rms=math.sqrt(best.fun) * sc,
                rms_over_L=math.sqrt(best.fun) * sc / L, area_fit=LH_AREA * L * W, n_pts=int(len(pts)),
                start=dict(L=L0, W=W0, theta_deg=math.degrees(th0), back=[float(back[0]), float(back[1])]))


def overturn(M, X, Z, xc, eta, vox, h0, want=False):
    """1 コマの噴流（水面が x について多価の上の所）と巻き（噴流の下の空気）の量。M[行=z（下から）, 列=x]。
    返り値の長さは m、面積は m²。want：図のための噴流と巻きの格子も返す。"""
    dx = float(X[1] - X[0]); dz = float(Z[1] - Z[0])
    out = dict(overturned=False, AJ_m2=0.0)
    lab, n = ndi.label(~M)
    cnt = np.bincount(lab.ravel(), minlength=n + 1)
    atm = set(np.unique(lab[-1, :]).tolist()) - {0}
    amin = vox * vox
    small = np.zeros(n + 1, bool)
    for k in range(1, n + 1):
        if k not in atm and cnt[k] * dx * dz < amin:
            small[k] = True               # 格子 1 個より小さい閉じた泡は水として扱う（解析の着水の決まりと同じ大きさ）
    sm = small[lab]
    Mf = M | sm
    lab = np.where(sm, 0, lab)
    out["bubbles_filled"] = int(small.sum())
    i0 = max(0, int(np.searchsorted(X, xc - 1.0 * eta))); i1 = min(len(X), int(np.searchsorted(X, xc + 3.0 * eta)))
    cols = {}
    for i in range(i0, i1):
        rr = runs(Mf[:, i])
        if len(rr) < 2:
            continue
        top, below = rr[-1], rr[-2]
        k = int(lab[top[0] - 1, i])
        if k == 0:
            continue
        cols[i] = (top, below, "open" if k in atm else "closed", k)
    if not cols:
        return out
    gs = groups_of(cols)
    g = min(gs, key=lambda gg: abs(X[gg[0]] - xc))
    x_back = float(X[g[0]] - 0.5 * dx); x_tip = float(X[g[-1]] + 0.5 * dx)
    reach = x_tip - x_back
    under = {i: float(Z[cols[i][0][0]] - 0.5 * dz) for i in g}
    AJ = float(sum(cols[i][0][1] - cols[i][0][0] + 1 for i in g)) * dx * dz
    closed = [i for i in g if cols[i][2] == "closed"]
    fwd = [i for i in g if X[i] >= x_back + 0.5 * reach]
    i_low = min(fwd, key=lambda i: under[i])
    gap_low = float((cols[i_low][0][0] - cols[i_low][1][1] - 1) * dz) if cols[i_low][2] == "open" else 0.0
    gaps_f = [float((cols[i][0][0] - cols[i][1][1] - 1) * dz) for i in fwd if cols[i][2] == "open"]
    out.update(overturned=True, x_back=x_back, x_tip=x_tip, reach_m=reach, n_cols=len(g), AJ_m2=AJ,
               jet_low_x=float(X[i_low]), jet_low_z=under[i_low], gap_low_m=gap_low,
               gap_min_fwd_m=(min(gaps_f) if gaps_f else 0.0), contact=bool(closed), n_closed_cols=len(closed))
    # ---- 巻きの空気
    cav = None
    if closed:
        ks = set(cols[i][3] for i in closed)
        k = max(ks, key=lambda kk: cnt[kk])
        cav = lab == k
        jc = np.where(cav.any(0))[0]
        x_close = float(X[jc.max()] + 0.5 * dx)
        z_close = float(Z[np.where(cav[:, jc.max()])[0]].mean())
        how = "contact（閉じた空気の穴。噴流の先が下の水に触れた後）"
    else:
        i = i_low
        top, below = cols[i][0], cols[i][1]
        M2 = Mf.copy()
        M2[below[1] + 1:top[0], i] = True                       # 噴流のいちばん低い所の縦の隙間を水で閉じる
        lab2, _ = ndi.label(~M2)
        atm2 = set(np.unique(lab2[-1, :]).tolist()) - {0}
        side = i - 1 if (i - 1) in cols else (i + 1 if (i + 1) in cols else None)
        seeds = []
        if side is not None:
            ts, bs = cols[side][0], cols[side][1]
            seeds = [int(lab2[j, side]) for j in range(bs[1] + 1, ts[0]) if lab2[j, side] > 0]
        k = max(set(seeds), key=seeds.count) if seeds else 0
        if k and k not in atm2:
            cav = lab2 == k
        x_close = float(X[i]); z_close = float(0.5 * (Z[below[1]] + Z[top[0]]))
        how = "closed_at_jet_low（噴流のいちばん低い所の縦の隙間 %.3f m を縦の線で閉じた）" % gap_low
    out["cavity_how"] = how
    out["x_close"] = x_close; out["z_close"] = z_close
    if cav is not None and cav.any():
        AO = float(cav.sum()) * dx * dz
        jj, ii = np.where(cav)
        out.update(AO_m2=AO, cav_x=[float(X[ii.min()] - 0.5 * dx), float(X[ii.max()] + 0.5 * dx)],
                   cav_z=[float(Z[jj.min()] - 0.5 * dz), float(Z[jj.max()] + 0.5 * dz)])
        cs = measure.find_contours(np.pad(cav, 1).astype(float), 0.5)
        c = max(cs, key=len)
        pts = np.stack([X[0] + (c[:, 1] - 1) * dx, Z[0] + (c[:, 0] - 1) * dz], 1)
        out["_cav_line"] = pts
    else:
        out.update(AO_m2=None)
    # ---- 噴流の格子と、根元から先までの長さの半分の所の幅
    J = np.zeros_like(M)
    for i in g:
        J[cols[i][0][0]:cols[i][0][1] + 1, i] = True
    jr, ir = np.where(J)
    r0, r1, c0, c1 = max(jr.min() - 2, 0), min(jr.max() + 3, M.shape[0]), max(ir.min() - 2, 0), min(ir.max() + 3, M.shape[1])
    Jc = J[r0:r1, c0:c1]
    starts = [(int(j - r0), int(g[0] - c0)) for j in range(cols[g[0]][0][0], cols[g[0]][0][1] + 1)]
    cum, _ = MCP_Geometric(np.where(Jc, 1.0, np.inf)).find_costs(starts)
    okc = Jc & np.isfinite(cum)
    if okc.any():
        Lpx = float(cum[okc].max())
        jt_, it_ = np.unravel_index(np.argmax(np.where(okc, cum, -1)), cum.shape)
        # 噴流の格子だけで、空気（と根元の切り口）までの距離。幅＝内に入る最大の円の直径（升 1 個の分を引く）
        EJ = ndi.distance_transform_edt(np.pad(Jc, 3))[3:-3, 3:-3]
        prof = {}
        for sfrac in (0.25, 0.5, 0.75, 0.9):
            band = okc & (np.abs(cum - sfrac * Lpx) <= 0.75)
            if not band.any():
                continue
            eb = np.where(band, EJ, -1)
            jb, ib = np.unravel_index(np.argmax(eb), eb.shape)
            col = c0 + ib
            prof["%.2f" % sfrac] = dict(w=(2.0 * float(EJ[jb, ib]) - 1.0) * dx, x=float(X[col]), z=float(Z[r0 + jb]),
                                       vthick=(float((cols[col][0][1] - cols[col][0][0] + 1) * dz) if col in cols else None))
        out.update(jet_len_m=Lpx * dx, jet_tip_geo=[float(X[c0 + it_]), float(Z[r0 + jt_])],
                   jet_width_profile={k: v["w"] for k, v in prof.items()},
                   jet_width_how="噴流（多価の上の所）の中を根元の列から測った道のりの長さ s の所で、内に入る最大の円の直径。"
                                 "計画の決まりは s 0.5（jet_width_half_m）。論文の「約 0.05 h0」は論文の図 5b を同じ道具で読むと s 0.8〜0.9 の細い所に当たる")
        if "0.50" in prof:
            out.update(jet_width_half_m=prof["0.50"]["w"], jet_half_point=[prof["0.50"]["x"], prof["0.50"]["z"]], jet_vthick_half_m=prof["0.50"]["vthick"])
        if "0.90" in prof:
            out.update(jet_width_09_m=prof["0.90"]["w"])
    if want:
        out["_J"] = (J[r0:r1, c0:c1].copy(), X[c0:c1].copy(), Z[r0:r1].copy())
        if cav is not None:
            jj, ii = np.where(cav)
            a0, a1, b0, b1 = max(jj.min() - 2, 0), min(jj.max() + 3, M.shape[0]), max(ii.min() - 2, 0), min(ii.max() + 3, M.shape[1])
            out["_cav"] = (cav[a0:a1, b0:b1].copy(), X[b0:b1].copy(), Z[a0:a1].copy())
    return out


def s52_measure(M, X, Z):
    try:
        return S52.measure_mask(M, X, Z, flip_extra=dict(Lc=LC_S52)), None
    except Exception as e:
        return None, repr(e)[:200]


S52_KEYS = ["eta_c", "x_c", "face_chord_deg_01_05", "front_x01_rel", "front_x05_rel", "eta_over_front01", "steep45_frac", "steep60_frac",
            "back_angle_07_09_deg", "width07_silhouette", "hood", "gap_max", "gap_under_tip", "lip_thick_mid", "lip_thick_mid_m",
            "hood_area", "hood_area_m2", "hood_wall_x_rel", "reach", "reach_m", "hood_height", "hood_height_m", "tip_z", "hood_low_z",
            "face_concavity_01_05", "trough_front", "H_front_over_eta", "front_x00_rel"]


def pick52(m):
    return {k: fnum(m.get(k)) for k in S52_KEYS} if m else None


# ======================================================================== 本体
def analyze(cx, opt):
    t_start = time.time()
    frames = cx.rec.frames
    if opt.get("f0") is not None:
        frames = [f for f in frames if f >= int(opt["f0"])]
    if opt.get("f1") is not None:
        frames = [f for f in frames if f <= int(opt["f1"])]
    if opt.get("t0") is not None:
        frames = [f for f in frames if cx.t(f) >= float(opt["t0"]) - 1e-9]
    if opt.get("t1") is not None:
        frames = [f for f in frames if cx.t(f) <= float(opt["t1"]) + 1e-9]
    if not frames:
        raise InputError("読むコマがない")
    xwin = [float(v) for v in opt["xwin"].split(",")] if opt.get("xwin") else None
    # ---- 粗い読み：全部のコマ
    rows = []
    prev = None
    for f in frames:
        r = coarse_frame(cx, f, prev, xwin)
        rows.append(r); prev = r["xc"]
    on_i = next((k for k, r in enumerate(rows) if np.isfinite(r["thmax"]) and r["thmax"] >= 90.0), None)
    res = dict(stage="FLIP47", tool="g47_analyze.py", run=cx.name, rd=cx.rd, kind=cx.kind, cfg=cx.cfg_name,
               dp=cx.dp, vox=cx.vox, h0=cx.h0, TS=cx.TS, t_ic=cx.t_ic, xref=cx.xref, xref_src=cx.xref_src,
               still_offset_m=cx.off, still_offset_src=cx.off_src, bed_src=cx.bed_src, x0_crest=cx.x0_crest,
               frames=[frames[0], frames[-1]], n_frames=len(frames), dropped_frames=cx.rec.dropped[:20],
               gap_thr_m=cx.thr, gap_rule_ja=("記録の格子 %.3g m は隙間の閾値 %.3g m（0.015 h0）より%s。" % (cx.vox, cx.thr, "粗い：触れた最初のコマも着水とする（論文の出力の間隔の時と同じ扱い）" if cx.vox > cx.thr else "細かい")),
               paper=PAPER)
    pc = B47 + "/smoke/test_analyze/paper_fig5_check.json"
    if os.path.exists(pc):
        res["paper_fig5_by_g47"] = dict(src="x47_paper_check.py（論文の図 5 の水の形をこの道具で読んだ値。長さは h0 で割った値）",
                                        b_Re0=json.load(open(pc, encoding="utf8"))["panels"].get("b_Re0"))
    res["coarse"] = [[r["frame"], round(r["t"], 4), round(r["xc"], 3), round(r["eta"], 3),
                      (round(r["thmax"], 2) if np.isfinite(r["thmax"]) else None)] for r in rows]
    res["coarse_cols"] = ["frame", "t", "xc", "eta", "thmax_deg"]
    k_max = int(np.argmax([r["eta"] for r in rows[:on_i + 1]])) if on_i is not None else int(np.argmax([r["eta"] for r in rows]))
    res["eta_max_before_onset"] = dict(frame=rows[k_max]["frame"], t=rows[k_max]["t"], eta=rows[k_max]["eta"], xc=rows[k_max]["xc"])
    if on_i is None:
        res["onset"] = None
        res["notes_ja"] = ["巻き始め（前の面の鉛直の接線）が読んだコマの中にない"]
    else:
        r = rows[on_i]
        pers = on_i + 1 < len(rows) and np.isfinite(rows[on_i + 1]["thmax"]) and rows[on_i + 1]["thmax"] >= 90.0
        res["onset"] = dict(frame=r["frame"], t=r["t"], t_tilde=cx.tt(r["t"]), xc=r["xc"], xc_h0=r["xc"] / cx.h0,
                            x_vert=(r["x_vert"][0] if r["x_vert"] else None), z_vert=(r["x_vert"][1] if r["x_vert"] else None),
                            x_vert_h0=(r["x_vert"][0] / cx.h0 if r["x_vert"] else None),
                            Hb_onset_m=r["eta"], Hb_onset_h0=r["eta"] / cx.h0, thmax=r["thmax"], next_frame_also_vertical=bool(pers),
                            at_first_frame=bool(on_i == 0),
                            rule_ja="前の面に初めて鉛直の接線（頂から前の面の線に沿って格子 1 個分の弦の向きが 90° 以上。FLIP42・44 と同じ）。Hb_onset は頂の高さ（静かな水面から）")
    # ---- 細かい読み：巻き始めの 1 s 前から、着水の after コマ後まで
    after = int(opt.get("after", 12))
    if on_i is not None:
        k0 = max(0, on_i - 24); k1 = len(rows)
    else:
        k0 = max(0, len(rows) - 24); k1 = len(rows)
    fine = []
    td_k = None
    reach_min = None
    for k in range(k0, k1):
        r = rows[k]
        S = cx.sdf(r["frame"])
        M, X, Z = fine_mask(cx, r["frame"], r["xc"], S=S)
        m52, err = s52_measure(M, X, Z)
        eta = float(m52["eta_c"]) if m52 else float(Z[np.where(M.any(1))[0].max()] + 0.5 * FINE)
        xc = float(m52["x_c"]) if m52 else r["xc"]
        ov = overturn(M, X, Z, xc, eta, cx.vox, cx.h0)
        row = dict(frame=r["frame"], t=r["t"], xc=xc, eta=eta, s52=pick52(m52), s52_err=err,
                   ov={kk: vv for kk, vv in ov.items() if not kk.startswith("_")})
        fine.append(row)
        if on_i is not None and k >= on_i and td_k is None:
            reach_min = max(2.0 * cx.vox, 0.1 * eta)
            if ov.get("overturned") and (ov.get("contact") or (ov["reach_m"] >= reach_min and ov["gap_low_m"] <= cx.thr)):
                td_k = len(fine) - 1
        if td_k is not None and len(fine) - 1 >= td_k + after:
            break
    res["fine_cols_ja"] = "細かい読み（0.05 m の水の格子）。s52＝同じ物差しの量（η_c で割った値・度）、ov＝噴流と巻きの量（m・m²）"
    res["fine"] = [dict(frame=w["frame"], t=w["t"], xc=w["xc"], eta=w["eta"],
                        s52=({kk: w["s52"][kk] for kk in ("face_chord_deg_01_05", "gap_max", "lip_thick_mid", "hood_area", "hood_height_m", "reach_m", "front_x01_rel")} if w["s52"] else None),
                        ov={kk: w["ov"].get(kk) for kk in ("overturned", "reach_m", "AJ_m2", "AO_m2", "gap_low_m", "jet_low_x", "jet_low_z", "contact", "cavity_how")},
                        score=w.get("score"))
                   for w in fine]
    sel = {}
    if on_i is not None:
        sel["onset"] = rows[on_i]["frame"]
        on_f = rows[on_i]["frame"]
        if td_k is not None:
            td = fine[td_k]
            sel["touchdown"] = td["frame"]
            ov = td["ov"]
            by_gap = (not ov.get("contact"))
            # 隙間の決まりで着水に入ったコマの前のコマの隙間（記録の間隔の中でいつ閾値を切ったかの目安）
            prev = fine[td_k - 1]["ov"] if td_k > 0 else {}
            res["touchdown"] = dict(frame=td["frame"], t=td["t"], t_tilde=cx.tt(td["t"]), by=("gap<=0.015h0" if by_gap else "contact"),
                                    gap_low_m=ov.get("gap_low_m"), gap_low_h0=(ov.get("gap_low_m") or 0.0) / cx.h0,
                                    prev_frame_gap_low_m=prev.get("gap_low_m"), prev_frame_contact=prev.get("contact"),
                                    reach_min_m=reach_min,
                                    rule_ja="巻き始めの後、噴流のいちばん低い所（張り出しの前の半分の中で、噴流の下の面がいちばん低い列）の縦の隙間が "
                                            "0.015 h0 以下になるか、噴流の下に閉じた空気の穴（格子 1 個以上）ができた最初のコマ。張り出しの長さが "
                                            "max(格子 2 個, 0.1 η_c) より短い時は隙間の決まりを使わない（巻き始めの小さな出っ張りを着水と読まないため）")
            pre = [w for w in fine if on_f <= w["frame"] <= td["frame"] and w["s52"]]
            if pre:
                sel["max_overturn"] = max(pre, key=lambda w: (w["s52"]["hood_height_m"] or 0.0))["frame"]
        else:
            pre = [w for w in fine if w["frame"] >= on_f and w["s52"]]
            res["touchdown"] = None
            res.setdefault("notes_ja", []).append("着水（隙間 0.015 h0 以下か閉じた穴）が読んだコマの中にない")
            if pre:
                sel["max_overturn"] = max(pre, key=lambda w: (w["s52"]["hood_height_m"] or 0.0))["frame"]
    # ---- 原画への近さの点数（targets_ja.md §5：巻き始め〜最初に触れたコマの全部を同じ物差しで測り、5 つの量の帯の外れの和）
    if on_i is not None:
        on_f = rows[on_i]["frame"]
        cont = next((w for w in fine if w["frame"] >= on_f and w["ov"].get("contact")), None)
        res["contact_first"] = dict(frame=cont["frame"], t=cont["t"], t_tilde=cx.tt(cont["t"])) if cont else None
        if TG is not None:
            bands = TG.print_bands(json.load(open(STUDY52 + "/shape_measures.json", encoding="utf8")))
            for w in fine:
                if w["s52"]:
                    w["score"], w["score_parts"] = TG.score(w["s52"], bands)
            end_f = cont["frame"] if cont else (res["touchdown"]["frame"] if res.get("touchdown") else fine[-1]["frame"])
            cand = [w for w in fine if on_f <= w["frame"] <= end_f and w.get("score") is not None]
            if cand:
                best = min(cand, key=lambda w: (w["score"], -(w["s52"].get("hood_height_m") or 0.0)))
                sel["best_score"] = best["frame"]
                sc_at = {nm: next((w.get("score") for w in fine if w["frame"] == f), None) for nm, f in sel.items()}
                res["score"] = dict(rule_ja="targets_ja.md §5（g47_targets.score。0 が原画の帯の中、5 がいちばん遠い）。巻き始め〜最初に触れたコマ"
                                            "（触れなければ着水のコマ）で最小のコマ。同じ点数なら覆いの高い方",
                                    window=[on_f, end_f], best=dict(frame=best["frame"], t=best["t"], score=best["score"], parts=best["score_parts"]),
                                    at=sc_at, series=[[w["frame"], w["score"]] for w in cand])
    res["selected_frames"] = sel
    res["max_overturn_rule_ja"] = "巻き始め〜着水のコマで、覆いの高さ（s52 の hood_height_m）が最大のコマ（STUDY52 と同じ）"
    # ---- 選んだコマで、全部の量
    sel_out = {}
    masks = {}
    by_f = {w["frame"]: w for w in fine}
    for nm, f in sel.items():
        w = by_f[f]
        S = cx.sdf(f)
        M, X, Z = fine_mask(cx, f, w["xc"], S=S)
        m52, err = s52_measure(M, X, Z)
        eta = float(m52["eta_c"]) if m52 else w["eta"]
        xc = float(m52["x_c"]) if m52 else w["xc"]
        ov = overturn(M, X, Z, xc, eta, cx.vox, cx.h0, want=True)
        d = dict(frame=f, t=cx.t(f), t_tilde=cx.tt(cx.t(f)), x_c=xc, x_c_h0=xc / cx.h0, eta_c=eta, s52=pick52(m52), s52_err=err)
        d["ov"] = {k: v for k, v in ov.items() if not k.startswith("_")}
        if ov.get("_cav_line") is not None and ov.get("AO_m2"):
            try:
                fit = lh_fit(ov["_cav_line"], (ov["x_close"], ov["z_close"]), ov["AO_m2"])
                d["lh_fit"] = fit
            except Exception as e:
                d["lh_fit_err"] = repr(e)[:200]
        sel_out[nm] = d
        masks[nm] = dict(M=M, X=X, Z=Z, J=ov.get("_J"), cav=ov.get("_cav"), cav_line=ov.get("_cav_line"),
                         fit=d.get("lh_fit"), x_c=xc, eta=eta, ov=d["ov"])
    res["at"] = sel_out
    # ---- 論文の量（着水のコマ）
    if "touchdown" in sel_out:
        d = sel_out["touchdown"]; ov = d["ov"]; Hb = d["eta_c"]
        fit = d.get("lh_fit") or {}
        if ov.get("contact"):
            xbp = ov.get("x_close"); xbp_how = "触れた後：閉じた空気の穴の前の端（噴流の先が触れた所）の x（注 2）"
        else:
            xbp = ov.get("jet_low_x"); xbp_how = "噴流のいちばん低い所（隙間の最も小さい所）の x"
        res["paper_measures"] = dict(
            frame=d["frame"], t=d["t"], t_tilde=d["t_tilde"],
            # 頂を x0 15 h0 より前に置いた計算は、その分（GN の速さ 1.265√(g h0) で走る時間）だけ早く着くので足す（2026-10-12 E1a の役が符号を直した）
            t_tilde_if_x0_15h0=(d["t_tilde"] + (cx.x0_crest / cx.h0 - 15.0) / 1.265 if cx.x0_crest is not None else None),
            Hb_m=Hb, Hb_h0=Hb / cx.h0, Hb_rule_ja="着水のコマの水面の最も高い所（静かな水面から）",
            xbp_m=xbp, xbp_h0=(xbp / cx.h0 if xbp is not None else None), xbp_how=xbp_how,
            AJ_m2=ov.get("AJ_m2"), AJ_Hb2=(ov.get("AJ_m2") or 0.0) / Hb ** 2,
            AO_m2=ov.get("AO_m2"), AO_Hb2=(ov["AO_m2"] / Hb ** 2 if ov.get("AO_m2") else None), cavity_how=ov.get("cavity_how"),
            W_L=fit.get("W_L"), theta_o_deg=fit.get("theta_deg"), L_m=fit.get("L"), W_m=fit.get("W"), L_Hb=(fit["L"] / Hb if fit else None),
            fit_rms_over_L=fit.get("rms_over_L"), AO_fit_over_direct=(fit["area_fit"] / ov["AO_m2"] if fit and ov.get("AO_m2") else None),
            jet_width_m=ov.get("jet_width_half_m"), jet_width_Hb=(ov["jet_width_half_m"] / Hb if ov.get("jet_width_half_m") else None),
            jet_width_h0=(ov["jet_width_half_m"] / cx.h0 if ov.get("jet_width_half_m") else None),
            jet_width_vox=(ov["jet_width_half_m"] / cx.vox if ov.get("jet_width_half_m") else None),
            jet_len_m=ov.get("jet_len_m"), jet_vthick_half_m=ov.get("jet_vthick_half_m"), jet_width_profile_m=ov.get("jet_width_profile"),
            jet_width_09_m=ov.get("jet_width_09_m"), jet_width_09_h0=(ov["jet_width_09_m"] / cx.h0 if ov.get("jet_width_09_m") else None),
            gap_low_m=ov.get("gap_low_m"), contact=ov.get("contact"),
            Hb_max_before_td_m=max(r["eta"] for r in rows if r["frame"] <= d["frame"]))
        if "onset" in sel_out:
            res["paper_measures"]["Hb_onset_m"] = res["onset"]["Hb_onset_m"]
    # ---- 原画と同じ物差し（巻き始め・いちばん巻いた・着水）
    pr = json.load(open(STUDY52 + "/shape_measures.json", encoding="utf8"))
    res["same_ruler"] = dict(
        rule_ja="STUDY52 s52_shape.measure_mask（η_c で割った値・度）。原画は縦の伸びを戻した読み（cn）",
        print_cn=pick52(pr["print"]["cn"]), print_drawn=pick52(pr["print"]["drawn"]),
        flip42_R3=dict((n, pick52(pr["flip"]["R3"][n])) for n in ("onset", "max_overturn", "contact")),
        ours=dict((n, sel_out[n]["s52"]) for n in sel_out))
    res["elapsed_s"] = time.time() - t_start
    return res, masks


# ======================================================================== 図
def zoom_figure(cx, res, masks, out_png, label=""):
    sel = res.get("selected_frames") or {}
    on = res.get("onset"); td = res.get("touchdown")
    fr_all = cx.rec.frames

    def frame_at(t):
        return min(fr_all, key=lambda q: abs(cx.t(q) - t))
    panels = []
    if on and td:
        tm = cx.t(sel["max_overturn"]) if "max_overturn" in sel else 0.5 * (on["t"] + td["t"])
        fmo = sel.get("max_overturn", frame_at(tm))
        p4 = (fmo, "いちばん巻いた（覆いが最も高い）") if fmo != td["frame"] else (frame_at(td["t"] - 0.25), "着水の 0.25 s 前（いちばん巻いたのは着水のコマ）")
        panels = [(frame_at(on["t"] - 0.75), "巻き始めの 0.75 s 前"), (on["frame"], "巻き始め（鉛直の接線）"),
                  (frame_at(0.5 * (on["t"] + cx.t(p4[0]))), "巻き始めとその次の間"), p4,
                  (td["frame"], "着水（%s）" % td["by"]), (frame_at(td["t"] + 0.3), "着水の 0.3 s 後")]
        xcen = res["paper_measures"]["xbp_m"] if res.get("paper_measures") and res["paper_measures"].get("xbp_m") is not None else on["xc"]
    elif on:
        t_last = res["fine"][-1]["t"] if res.get("fine") else on["t"] + 2.0
        ts = [on["t"] - 0.75, on["t"]] + list(np.linspace(on["t"] + 0.25 * (t_last - on["t"]), t_last, 4))
        panels = [(frame_at(t), "巻き始め %+.2f s%s" % (t - on["t"], "（記録の終わり、着水なし）" if k == 5 else "")) for k, t in enumerate(ts)]
        xcs = {int(r[0]): r[2] for r in res["coarse"]}
        xcen = 0.5 * (xcs.get(panels[0][0], on["xc"]) + xcs.get(panels[-1][0], on["xc"])) + 7.0
    else:
        lastrows = res["coarse"][-24:]
        panels = [(int(r[0]), "巻き始めなし") for r in lastrows[::max(1, len(lastrows) // 6)]][:6]
        xcen = lastrows[-1][2] + 7.0
    xz0, xz1 = xcen - 50.0, xcen + 14.0
    etamax = max(r[3] for r in res["coarse"])
    zlo, zhi = -8.0, math.ceil(etamax + 2.0)
    s = 10.0
    pw = int(round((xz1 - xz0) * s)); ph = int(round((zhi - zlo) * s))
    ncol = 3; nrow = int(math.ceil(len(panels) / ncol))
    Wd = 40 + ncol * (pw + 20); Hd = 96 + nrow * (ph + 54)
    im = Image.new("RGB", (Wd, Hd), BG); dr = ImageDraw.Draw(im)
    coarse = "粗い：" if cx.dp > 0.25 + 1e-9 else ""
    dr.text((20, 10), "%s%s（%s粒子 %.4g m・格子 %.4g m）断面の拡大。縦横同じ縮尺（1 m = 10 px）。点線は静かな水面、砂の色は海底。力は重力だけ" % (
        label + " " if label else "", cx.name, coarse, cx.dp, cx.vox), fill=TXT, font=font(19, True))
    sub = "x は%s（m）。h0 %.3g m。t* = t·√(g/h0)（論文の無次元の時間）。着水の図：灰＝噴流（多価の上の所）、赤＝巻きの空気の線、赤の破線＝Longuet-Higgins の当てはめ、桃の菱形＝xbp、黄の菱形＝Hb" % (
        "論文の座標" if cx.xref == 0 else "基準 %.2f m から" % cx.xref, cx.h0)
    dr.text((20, 38), sub, fill=SUB, font=font(15))
    Xp = xz0 + (np.arange(pw) + 0.5) / s
    Zp = zhi - (np.arange(ph) + 0.5) / s
    bed = cx.bedf(Xp)
    for k, (f, name) in enumerate(panels):
        r, c = divmod(k, ncol)
        px0 = 20 + c * (pw + 20); py0 = 70 + r * (ph + 54)
        S = cx.sdf(f, fill_bed=False)
        xs, ys = cx.xs, cx.ys
        fx = np.clip((Xp - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.001); fz = np.clip((Zp - ys[0]) / (ys[1] - ys[0]), 0, len(ys) - 1.001)
        ix = np.floor(fx).astype(int); wx = fx - ix; iz = np.floor(fz).astype(int); wz = fz - iz
        A = S[iz][:, ix] * (1 - wx)[None, :] + S[iz][:, ix + 1] * wx[None, :]
        B = S[iz + 1][:, ix] * (1 - wx)[None, :] + S[iz + 1][:, ix + 1] * wx[None, :]
        F = A * (1 - wz)[:, None] + B * wz[:, None]
        img = np.empty((ph, pw, 3), np.uint8); img[:] = (255, 255, 255)
        img[F < 0] = WATER
        sand = Zp[:, None] < bed[None, :]
        img[sand] = SAND
        im.paste(Image.fromarray(img), (px0, py0))
        dr.rectangle([px0, py0, px0 + pw, py0 + ph], outline=LINE)
        yz = py0 + (zhi - 0.0) * s
        for xx in range(px0, px0 + pw, 10):
            dr.line([(xx, yz), (xx + 5, yz)], fill=(120, 120, 120))
        for xv in np.arange(math.ceil(xz0 / 10) * 10, xz1 + 1e-6, 10):
            u = px0 + (xv - xz0) * s
            dr.line([(u, py0 + ph), (u, py0 + ph + 5)], fill=LINE)
            dr.text((u - 14, py0 + ph + 6), "%g" % xv, fill=SUB, font=font(13))
        lab = "t = %.2f s（t* %.2f、コマ %d）" % (cx.t(f), cx.tt(cx.t(f)), f)
        dr.text((px0 + 6, py0 + 4), lab, fill=RED, font=font(16, True))
        dr.text((px0 + 6, py0 + 26), name, fill=TXT, font=font(15))
        tr = lambda x, z: (px0 + (x - xz0) * s, py0 + (zhi - z) * s)
        if on and f == on["frame"] and on.get("x_vert") is not None:
            u, v = tr(on["x_vert"], on["z_vert"])
            dr.polygon([(u, v - 7), (u - 6, v - 17), (u + 6, v - 17)], fill=RED)
        if td and f == td["frame"] and "touchdown" in masks:
            mk = masks["touchdown"]
            if mk.get("J") is not None:
                J, XJ, ZJ = mk["J"]
                for cc in measure.find_contours(np.pad(J, 1).astype(float), 0.5):
                    P_ = [tr(XJ[0] + (q[1] - 1) * FINE, ZJ[0] + (q[0] - 1) * FINE) for q in cc]
                    dr.polygon(P_, fill=(170, 170, 170), outline=(110, 110, 110))
            if mk.get("cav_line") is not None:
                P_ = [tr(x, z) for x, z in mk["cav_line"]]
                dr.line(P_ + [P_[0]], fill=(220, 30, 30), width=2)
            if mk.get("fit"):
                cur = lh_curve((mk["fit"]["L"], mk["fit"]["W"], math.radians(mk["fit"]["theta_deg"]), mk["fit"]["x0"], mk["fit"]["z0"]))
                P_ = [tr(x, z) for x, z in cur]
                for i in range(0, len(P_) - 1, 6):
                    dr.line(P_[i:i + 3], fill=(240, 90, 90), width=1)
            pm = res.get("paper_measures") or {}
            if pm.get("xbp_m") is not None:
                zb = mk["ov"].get("z_close", 0.0)
                u, v = tr(pm["xbp_m"], zb)
                dr.polygon([(u, v - 6), (u + 6, v), (u, v + 6), (u - 6, v)], fill=(220, 0, 200))
            u, v = tr(mk["x_c"], mk["eta"])
            dr.polygon([(u, v - 6), (u + 6, v), (u, v + 6), (u - 6, v)], fill=(240, 200, 0), outline=(120, 100, 0))
    pm = res.get("paper_measures")
    if pm:
        txt = ("着水の時（論文の定義）：Hb/h0 %.3f（論文 0.64）・xbp/h0 %s（42.05）・AJ/Hb² %.3f（0.219）・Ao/Hb² %s（0.352）・W/L %s（0.300、論文の図 5b をこの道具で 0.351）・"
               "θo %s（29°）・噴流の幅（長さの半分）/Hb %s（図 5b をこの道具で 0.132）" % (pm["Hb_h0"], "%.2f" % pm["xbp_h0"] if pm.get("xbp_h0") is not None else "-", pm["AJ_Hb2"],
                                          "%.3f" % pm["AO_Hb2"] if pm.get("AO_Hb2") is not None else "-", "%.3f" % pm["W_L"] if pm.get("W_L") is not None else "-",
                                          "%.1f°" % pm["theta_o_deg"] if pm.get("theta_o_deg") is not None else "-",
                                          "%.3f" % pm["jet_width_Hb"] if pm.get("jet_width_Hb") is not None else "-"))
        dr.text((20, Hd - 24), txt, fill=TXT, font=font(15))
    im.save(out_png)
    return out_png


def mask_lines(M, X, Z, xc, eta):
    out = []
    for c in measure.find_contours(M.astype(float), 0.5):
        x = X[0] + c[:, 1] * (X[1] - X[0]); z = Z[0] + c[:, 0] * (Z[1] - Z[0])
        out.append(np.stack([(x - xc) / eta, z / eta], 1))
    return out


def overlay_figure(cx, res, masks, out_png, label=""):
    """いちばん巻いたコマの形を、原画の輪郭（STUDY52 と同じ読み）と η_c で割った同じ倍率で重ねる（d_shape_figure.py の (b) の写し）。"""
    XL, XR, ZB, ZT = -3.2, 2.4, -0.32, 1.1
    PX = 300
    outer, inner, _ = S52.print_outline()
    pr = json.load(open(STUDY52 + "/shape_measures.json", encoding="utf8"))

    def print_lines(k, sw, sy):
        p = pr["print"][k]
        conv = lambda a: np.stack([(a[:, 0] - p["x_c"]) / p["eta_c"], (sw - a[:, 1]) * sy / p["eta_c"]], 1)
        return [conv(outer), conv(inner)]
    P_cn = print_lines("cn", S52.Y_HORIZON, 1.0 / S52.STRETCH)
    P_dr = print_lines("drawn", S52.Y_HORIZON, 1.0)
    d42 = np.load(STUDY52 + "/work/mask_R3_max_overturn.npz"); m42 = pr["flip"]["R3"]["max_overturn"]
    F42 = mask_lines(d42["M"], d42["X"], d42["Z"], m42["x_c"], m42["eta_c"])
    ours = {}
    for nm in ("onset", "max_overturn", "touchdown", "best_score"):
        if nm in masks:
            mk = masks[nm]
            ours[nm] = mask_lines(mk["M"], mk["X"], mk["Z"], mk["x_c"], mk["eta"])
    W = int((XR - XL) * PX); H = int((ZT - ZB) * PX)
    ox, oy = 70, 90
    img = Image.new("RGB", (W + 780, H + 200), "white"); dr = ImageDraw.Draw(img)
    dr.text((20, 10), "%s%s：同じ物差しの重ね（頂の高さ η_c で割り、頂の位置をそろえ、縦横同じ倍率。右が進む向き）" % (label + " " if label else "", cx.name),
            fill=TXT, font=font(19, True))
    dr.text((20, 40), "縦軸：静かな水面からの高さ ÷ η_c。横軸：頂（一番高い水の列の真ん中）からの距離 ÷ η_c。原画は縦 30 % の伸びを戻した形（黒）と描かれたまま（灰の破線）",
            fill=SUB, font=font(14))
    tr = lambda p: (ox + (p[0] - XL) * PX, oy + (ZT - p[1]) * PX)
    dr.rectangle([ox, oy, ox + W, oy + H], outline=(160, 160, 160))
    for zv in (-0.25, 0.0, 0.25, 0.5, 0.7, 1.0):
        a = tr((XL, zv)); b = tr((XR, zv))
        dr.line([a, b], fill=(110, 110, 110) if zv == 0 else (228, 228, 228), width=2 if zv == 0 else 1)
        dr.text((ox - 44, a[1] - 9), "%g" % zv, fill=SUB, font=font(13))
    for xv in np.arange(-3.0, 2.41, 0.5):
        a = tr((xv, ZB))
        dr.line([a, (a[0], a[1] - 6)], fill=(120, 120, 120))
        dr.text((a[0] - 10, a[1] + 4), "%g" % xv, fill=SUB, font=font(13))
    BLK, GRY, ORG, BLU, LBL, PUR = (0, 0, 0), (150, 150, 150), (235, 140, 20), (20, 60, 200), (120, 170, 240), (150, 60, 170)
    items = [(P_dr, GRY, 2, True), (P_cn, BLK, 4, False), (F42, ORG, 2, False)]
    if "onset" in ours:
        items.append((ours["onset"], LBL, 2, False))
    if "touchdown" in ours:
        items.append((ours["touchdown"], PUR, 2, True))
    sf = res.get("selected_frames") or {}
    if "best_score" in ours and sf.get("best_score") not in (sf.get("max_overturn"), sf.get("touchdown")):
        items.append((ours["best_score"], (30, 150, 60), 3, False))
    if "max_overturn" in ours:
        items.append((ours["max_overturn"], BLU, 4, False))
    for lines, col, wd, dash in items:
        for L in lines:
            P_ = [tr(p) for p in L if XL - 0.2 <= p[0] <= XR + 0.2 and ZB - 0.2 <= p[1] <= ZT + 0.2]
            if len(P_) < 2:
                continue
            if dash:
                for i in range(0, len(P_) - 1, 8):
                    dr.line(P_[i:i + 4], fill=col, width=wd)
            else:
                dr.line(P_, fill=col, width=wd, joint="curve")
    at = res.get("at") or {}
    leg = [("原画（縦の伸びを戻した形）", BLK), ("原画（描かれたまま、破線）", GRY), ("FLIP42 R3 いちばん巻いた（2D、粒子 0.25 m）", ORG)]
    if "onset" in at:
        leg.append(("%s 巻き始め コマ %d（η_c %.2f m）" % (cx.name, at["onset"]["frame"], at["onset"]["eta_c"]), LBL))
    if "max_overturn" in at:
        leg.append(("%s いちばん巻いた コマ %d（η_c %.2f m）" % (cx.name, at["max_overturn"]["frame"], at["max_overturn"]["eta_c"]), BLU))
    if "touchdown" in at:
        leg.append(("%s 着水 コマ %d（破線）" % (cx.name, at["touchdown"]["frame"]), PUR))
    if "best_score" in at:
        sc = ((res.get("score") or {}).get("best") or {}).get("score")
        leg.append(("%s 原画に最も近い コマ %d（点数 %s）" % (cx.name, at["best_score"]["frame"], "%.2f" % sc if sc is not None else "-"), (30, 150, 60)))
    y = oy
    for txt, col in leg:
        dr.line([(ox + W + 16, y + 10), (ox + W + 46, y + 10)], fill=col, width=4)
        dr.text((ox + W + 54, y), txt, fill=TXT, font=font(14)); y += 30
    # 数の表
    rowsq = [("前の面の弦 0.1〜0.5 η_c（度）", "face_chord_deg_01_05", "%.1f"), ("足（0.1 η_c）の頂の前の距離", "front_x01_rel", "%.3f"),
             ("唇の下の空気（最大）", "gap_max", "%.3f"), ("唇の厚さ（真ん中）", "lip_thick_mid", "%.3f"), ("覆いの面積", "hood_area", "%.3f"),
             ("覆いの高さ", "hood_height", "%.3f"), ("張り出し", "reach", "%.3f")]
    colsq = [("原画 cn", pr["print"]["cn"]), ("FLIP42 R3", pr["flip"]["R3"]["max_overturn"])]
    if "max_overturn" in at and at["max_overturn"]["s52"]:
        colsq.append(("%s 最も巻いた" % cx.name, at["max_overturn"]["s52"]))
    if "touchdown" in at and at["touchdown"]["s52"]:
        colsq.append(("%s 着水" % cx.name, at["touchdown"]["s52"]))
    if "best_score" in at and at["best_score"]["s52"]:
        colsq.append(("%s 点数最小" % cx.name, at["best_score"]["s52"]))
    y = max(y + 20, oy + 210)
    x0t = ox + W + 16
    dr.text((x0t, y), "同じ物差しの量（η_c で割った値）", fill=TXT, font=font(15, True)); y += 28
    cw = [215] + [100] * len(colsq)
    xx = x0t + cw[0]
    for (nm, _), w in zip(colsq, cw[1:]):
        dr.text((xx, y), nm[:14], fill=SUB, font=font(12)); xx += w
    y += 22
    for lab_, key, fm in rowsq:
        dr.text((x0t, y), lab_, fill=TXT, font=font(13))
        xx = x0t + cw[0]
        for (_, m), w in zip(colsq, cw[1:]):
            v = m.get(key)
            dr.text((xx, y), (fm % v) if isinstance(v, (int, float)) and v is not None else "-", fill=TXT, font=font(13)); xx += w
        y += 22
    pm = res.get("paper_measures")
    yb = oy + H + 40
    notes = ["原画の輪郭：Tools/PaintingTruth/targets/main_wave_outline_envelope.json（STUDY52 と同じ読み。静かな水面＝水平線 y 1885 px）。原画の前の面は 0.07 η_c より下が手前の波に隠れている。",
             "FLIP42 R3：Unity/Build/STUDY52/work/mask_R3_max_overturn.npz。%s：%s（静かな水面のずれ %.3f m、%s）" % (cx.name, cx.rd, cx.off, cx.off_src[:40])]
    if pm:
        notes.append("論文の定義の量（着水のコマ %d）：Hb/h0 %.3f・AJ/Hb² %.3f・Ao/Hb² %s・W/L %s・θo %s。論文（2 相・Bo 4000）は 0.64・0.219・0.352・0.300・29°" % (
            pm["frame"], pm["Hb_h0"], pm["AJ_Hb2"], "%.3f" % pm["AO_Hb2"] if pm.get("AO_Hb2") is not None else "-",
            "%.3f" % pm["W_L"] if pm.get("W_L") is not None else "-", "%.1f°" % pm["theta_o_deg"] if pm.get("theta_o_deg") is not None else "-"))
    for t in notes:
        dr.text((20, yb), t, fill=SUB, font=font(13)); yb += 24
    img.save(out_png)
    return out_png


# ======================================================================== 表（1 本 1 行）
TABLE_COLS = [
    ("run", "計算", "%s"), ("dp", "粒子 m", "%.4g"), ("h0", "h0", "%.3g"),
    ("on_t", "巻き始め t", "%.2f"), ("on_x_h0", "x/h0", "%.2f"), ("Hb_on_h0", "Hb巻始/h0", "%.3f"),
    ("td_by", "着水の決まり", "%s"), ("td_tt", "着水 t̃", "%.2f"), ("xbp_h0", "xbp/h0", "%.2f"), ("Hb_h0", "Hb/h0", "%.3f"),
    ("AJ_Hb2", "AJ/Hb²", "%.3f"), ("AO_Hb2", "Ao/Hb²", "%.3f"), ("W_L", "W/L", "%.3f"), ("theta", "θo°", "%.1f"),
    ("jetw_Hb", "幅½/Hb", "%.3f"), ("jetw_h0", "幅½/h0", "%.3f"), ("jetw09_h0", "幅0.9/h0", "%.3f"),
    ("score_best", "点数最小", "%.2f"), ("score_td", "着水の点数", "%.2f"), ("chord", "弦°", "%.1f"), ("gap", "空気", "%.3f"), ("lip", "唇", "%.3f"), ("area", "覆い", "%.3f"), ("foot", "足", "%.3f"),
]


def summary_row(a):
    """g47_ana.json（dict）→ 1 行（dict）。形の量（弦・空気・唇・覆い・足）はいちばん巻いたコマの同じ物差しの値。"""
    on = a.get("onset") or {}; td = a.get("touchdown") or {}; pm = a.get("paper_measures") or {}
    mo = ((a.get("at") or {}).get("max_overturn") or {}).get("s52") or {}
    return dict(run=a.get("run"), dp=a.get("dp"), h0=a.get("h0"), on_t=on.get("t"),
                on_x_h0=(on.get("x_vert_h0") if on.get("x_vert_h0") is not None else on.get("xc_h0")), Hb_on_h0=on.get("Hb_onset_h0"),
                td_by=td.get("by"), td_tt=pm.get("t_tilde"), xbp_h0=pm.get("xbp_h0"), Hb_h0=pm.get("Hb_h0"),
                AJ_Hb2=pm.get("AJ_Hb2"), AO_Hb2=pm.get("AO_Hb2"), W_L=pm.get("W_L"), theta=pm.get("theta_o_deg"),
                jetw_Hb=pm.get("jet_width_Hb"), jetw_h0=pm.get("jet_width_h0"), jetw09_h0=pm.get("jet_width_09_h0"),
                chord=mo.get("face_chord_deg_01_05"), gap=mo.get("gap_max"), lip=mo.get("lip_thick_mid"), area=mo.get("hood_area"),
                foot=mo.get("front_x01_rel"),
                score_best=((a.get("score") or {}).get("best") or {}).get("score"),
                score_td=((a.get("score") or {}).get("at") or {}).get("touchdown"))


def ref_rows():
    pr = json.load(open(STUDY52 + "/shape_measures.json", encoding="utf8"))
    cn = pr["print"]["cn"]; r3 = pr["flip"]["R3"]["max_overturn"]
    paper = dict(run="論文 Re*=0（2 相・Bo 4000）", h0=None, Hb_h0=PAPER["Hb_h0"], xbp_h0=PAPER["xbp_h0"], td_tt=PAPER["t_impact_tilde"], td_by="gap<=0.015h0",
                 AJ_Hb2=PAPER["AJ_Hb2"], AO_Hb2=PAPER["AO_Hb2"], W_L=PAPER["W_L"], theta=PAPER["theta_o_deg"],
                 jetw_Hb=PAPER["jet_width_Hb"], jetw_h0=PAPER["jet_width_h0"])
    prt = dict(run="原画 cn（目標の形）", chord=cn["face_chord_deg_01_05"], gap=cn["gap_max"], lip=cn["lip_thick_mid"], area=cn["hood_area"], foot=cn["front_x01_rel"])
    f42 = dict(run="FLIP42 R3 最も巻いた", dp=0.25, h0=42.0, chord=r3["face_chord_deg_01_05"], gap=r3["gap_max"], lip=r3["lip_thick_mid"],
               area=r3["hood_area"], foot=r3["front_x01_rel"])
    rows = [paper]
    pc = B47 + "/smoke/test_analyze/paper_fig5_check.json"          # x47_paper_check.py：論文の図 5b を g47 の道具で読んだ値
    if os.path.exists(pc):
        b = json.load(open(pc, encoding="utf8"))["panels"]["b_Re0"]
        s5 = b.get("s52") or {}
        rows.append(dict(run="論文の図 5b を g47 で読んだ", h0=1.0, Hb_h0=b.get("Hb_h0"), xbp_h0=b.get("xbp_h0"), td_by="図（着水の時刻）",
                         AJ_Hb2=b.get("AJ_Hb2"), AO_Hb2=b.get("AO_Hb2"), W_L=b.get("W_L"), theta=b.get("theta_deg"),
                         jetw_Hb=(b["jet_width_h0"] / b["Hb_h0"] if b.get("jet_width_h0") else None), jetw_h0=b.get("jet_width_h0"),
                         jetw09_h0=b.get("jet_width_09_h0"), chord=s5.get("face_chord_deg_01_05"), gap=s5.get("gap_max"),
                         lip=s5.get("lip_thick_mid"), area=s5.get("hood_area"), foot=s5.get("front_x01_rel")))
    return rows + [prt, f42]


def table_md(rows, refs=True):
    allr = (ref_rows() if refs else []) + list(rows)
    head = "| " + " | ".join(c[1] for c in TABLE_COLS) + " |"
    sep = "| " + " | ".join("---" for _ in TABLE_COLS) + " |"
    lines = [head, sep]
    for r in allr:
        cells = []
        for k, _, fm in TABLE_COLS:
            v = r.get(k)
            if v is None:
                cells.append("-")
            elif isinstance(v, str):
                cells.append(v)
            else:
                try:
                    cells.append(fm % v)
                except Exception:
                    cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_ana(p):
    p = p.replace("\\", "/").rstrip("/")
    if p.endswith(".json"):
        return json.load(open(p, encoding="utf8"))
    for q in (os.path.join(p, "ana47", "g47_ana.json"), os.path.join(p, "g47_ana.json"),
              os.path.join(B47, "smoke", "test_" + os.path.basename(p), "g47_ana.json")):
        if os.path.exists(q):
            return json.load(open(q, encoding="utf8"))
    raise InputError("g47_ana.json が見つからない：%s" % p)


# ======================================================================== 起動
def default_out(cx):
    if cx.rd.lower().startswith(B47.lower()):
        return cx.rd + "/ana47"
    return B47 + "/smoke/test_" + cx.name


def parse(argv):
    opt, pos = {}, []
    for a in argv:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v if v != "" else True
        else:
            pos.append(a)
    for k in ("h0", "off", "xref"):
        if k in opt:
            opt[k] = float(opt[k])
    return opt, pos


def main(argv):
    opt, pos = parse(argv)
    if opt.get("table"):
        rows = [summary_row(load_ana(p)) for p in pos]
        md = table_md(rows)
        print(md)
        if opt.get("csv"):
            p = guard_out(opt["csv"])
            with open(p, "w", encoding="utf-8-sig") as fo:
                fo.write(",".join(c[0] for c in TABLE_COLS) + "\n")
                for r in ref_rows() + rows:
                    fo.write(",".join("" if r.get(c[0]) is None else str(r.get(c[0])) for c in TABLE_COLS) + "\n")
        return 0
    if not pos:
        print(__doc__)
        return 2
    cx = Ctx(pos[0], opt)
    out = guard_out(opt.get("out") or default_out(cx))
    os.makedirs(out, exist_ok=True)
    res, masks = analyze(cx, opt)
    res["out"] = out
    figs = {}
    if not opt.get("nofig"):
        figs["section_zoom"] = zoom_figure(cx, res, masks, os.path.join(out, "%s_section_zoom.png" % cx.name), opt.get("label", ""))
        if masks:
            figs["print_overlay"] = overlay_figure(cx, res, masks, os.path.join(out, "%s_print_overlay.png" % cx.name), opt.get("label", ""))
    res["figures"] = figs
    if masks:
        np.savez_compressed(os.path.join(out, "%s_masks.npz" % cx.name),
                            **{"%s_%s" % (nm, k): v for nm, mk in masks.items() for k, v in (("M", mk["M"]), ("X", mk["X"]), ("Z", mk["Z"]))})
    json.dump(clean(res), open(os.path.join(out, "g47_ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 表示
    show = dict(run=res["run"], off=round(res["still_offset_m"], 4), off_src=res["still_offset_src"], bed=res["bed_src"],
                onset=res.get("onset") and {k: res["onset"][k] for k in ("frame", "t", "xc", "x_vert", "Hb_onset_m", "thmax", "next_frame_also_vertical")},
                touchdown=res.get("touchdown") and {k: res["touchdown"][k] for k in ("frame", "t", "by", "gap_low_m", "prev_frame_gap_low_m")},
                selected=res.get("selected_frames"), elapsed_s=round(res["elapsed_s"], 1))
    print(json.dumps(clean(show), ensure_ascii=False))
    if res.get("paper_measures"):
        pm = res["paper_measures"]
        print(json.dumps(clean({k: (round(v, 4) if isinstance(v, float) else v) for k, v in pm.items()}), ensure_ascii=False))
    print(table_md([summary_row(clean(res))]))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except InputError as e:
        print("InputError:", e)
        sys.exit(3)
