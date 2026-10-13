# -*- coding: utf-8 -*-
"""gw_shoal の 2 次元の波の計算（win_*.bin・full_*.bin・log.txt）を動画（MP4）にする。

- render_case：1 本の計算。上半分は計算領域の全体（縦を伸ばした側面）、下半分は頂を追う拡大（縦横 1:1）。
  原画の輪郭（Tools/GWWaveGen/ruler の s52_shape.print_outline、縦÷1.3 の読み）を、頂の高さと位置を合わせて重ねる。
- render_compare：複数の計算を並べる。τ = t − t_ref でそろえ、各枠は頂を追う拡大（縦横 1:1）。
- 長さはどれも h0（静かな水の深さ）を単位とする。y = 0 が静かな水面、重力は −y。時間 t は √(h0/g) を単位とする。
- 水は f > 0.5（f=0.5 の等値線を境とする）。海底は meta の bathy の節点（区分線形の深さ）で描き、
  節点がなければ最初の全体のコマの cs < 0.5 で描く。固体の中の f は意味を持たないので、海底は水の上に塗る。
- コマは 0.1 ごとに、波が急になると（log の dense = 1）0.02 ごとに書かれている。1 コマを動画の 1 コマにするので、
  細かい区間はスローになる。その倍率を画面に出す。
- 動画は matplotlib（Agg）で描いた RGB を ffmpeg（libx264）へ流して作る。1 本 20 MB を超えたら crf を上げて作り直す。

使い方：
  python3 gwvideo.py case RUN_DIR OUT.mp4 --meta META.json [--overlay OVERLAY.json|none] [--fps 25] [--stride 1] [--max-frames N]
  python3 gwvideo.py compare CASES.json OUT.mp4 [--fps 25] [--tau-start T] [--tau-end T]
"""
import os, sys, json, math, time, argparse, subprocess, shutil

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402
from scipy import ndimage  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RULER = os.path.join(REPO, "Tools", "GWWaveGen", "ruler")
sys.path.insert(0, HERE)
import gwread as G  # noqa: E402

# ------------------------------------------------------------------ 字形と色
for _p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
    if os.path.exists(_p):
        try:
            font_manager.fontManager.addfont(_p)
        except Exception:  # 字形を読めなくても描画は続ける（日本語が豆腐になるだけ）
            pass
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["mathtext.fontset"] = "dejavusans"
plt.rcParams["axes.unicode_minus"] = True

AIR = "#f3f6fa"          # 空気
WATER = "#3a76b2"        # 水
WATER_LINE = "#0c2846"   # 水と空気の境（f = 0.5）
SAND = "#cdb98f"         # 海底（固体）
SAND_EDGE = "#7d6640"
SWL = "#4a4a4a"          # 静かな水面
OVER = "#f0560a"         # 原画の輪郭
MARK = "#c92a2a"         # 頂の印
INK = "#1d1d1d"
SUB = "#555555"

G_SI = 9.81              # 実寸の秒に直すときの重力（m/s²）
SIZE_LIMIT = 20e6        # 1 本の上限（バイト）


# ------------------------------------------------------------------ 原画の輪郭
_PAINT = None


def painting_outline():
    """原画の外の輪郭と内の輪郭（C&N の読み：X = x_px、Z = (水平線 − y_px)/1.3。単位は画素）と、原画の頂（x_c, η_c）。"""
    global _PAINT
    if _PAINT is None:
        if RULER not in sys.path:
            sys.path.insert(0, RULER)
        import s52_shape as S
        outer, inner, _d = S.print_outline()
        with open(os.path.join(RULER, "shape_measures.json"), encoding="utf8") as fp:
            cn = json.load(fp)["print"]["cn"]

        def conv(a):
            a = np.asarray(a, float)
            return np.column_stack([a[:, 0], (S.Y_HORIZON - a[:, 1]) / S.STRETCH])

        _PAINT = dict(outer=conv(outer), inner=conv(inner), eta_c=float(cn["eta_c"]), x_c=float(cn["x_c"]))
    return _PAINT


def painting_in_h0(eta_sim, xc_sim):
    """原画の輪郭を h0 の座標へ移す。倍率 s = η_c（計算）/ η_c（原画）、原画の頂を計算の頂へ重ねる。
    η_c はどちらも静かな水面（y = 0）から測るので、縦は y = s·Z だけになる。"""
    P = painting_outline()
    s = eta_sim / P["eta_c"]

    def tr(a):
        return np.column_stack([xc_sim + s * (a[:, 0] - P["x_c"]), s * a[:, 1]])

    return tr(P["outer"]), tr(P["inner"]), s


# ------------------------------------------------------------------ 小さな道具
def _head(path):
    """コマの頭だけを読む（t, x0, y0, dx, xcrest, nx, ny）と、ファイルが書き終わっているか。"""
    with open(path, "rb") as fp:
        tag = fp.read(4)
        if tag != b"GWS1":
            return None
        b = fp.read(48)
        if len(b) < 48:
            return None
    hd = np.frombuffer(b[:40], dtype="<f8")
    nx, ny = np.frombuffer(b[40:48], dtype="<i4")
    need = 4 + 40 + 8 + 2 * int(nx) * int(ny)
    ok = os.path.getsize(path) >= need
    return dict(t=float(hd[0]), x0=float(hd[1]), y0=float(hd[2]), dx=float(hd[3]), xcrest=float(hd[4]),
                nx=int(nx), ny=int(ny), complete=ok)


def _fnum(path):
    return int(os.path.basename(path).split("_")[-1].split(".")[0])


def _tdict(d):
    """{t: 値}（JSON では t が文字列）を、時刻の配列と値の配列にする。"""
    if not d:
        return np.zeros(0), np.zeros(0)
    items = sorted((float(k), float(v)) for k, v in d.items() if v is not None)
    if not items:
        return np.zeros(0), np.zeros(0)
    a = np.array(items)
    return a[:, 0], a[:, 1]


def _nearest(ts, vs, t, tol):
    if len(ts) == 0:
        return None
    i = int(np.argmin(np.abs(ts - t)))
    return float(vs[i]) if abs(ts[i] - t) <= tol else None


def _smooth_track(t, x, sigma=0.3):
    """時刻の間隔がそろわない列 x(t) を、ガウスの重みの局所一次の当てはめでなめらかにする（端で遅れない）。
    重みには各点の受け持つ時間の幅を掛け、細かい区間の点が重みを独り占めしないようにする。"""
    t = np.asarray(t, float)
    x = np.asarray(x, float)
    n = len(t)
    if n < 3:
        return x.copy()
    span = np.empty(n)
    span[1:-1] = 0.5 * (t[2:] - t[:-2])
    span[0] = t[1] - t[0]
    span[-1] = t[-1] - t[-2]
    span = np.maximum(span, 1e-6)

    def fit(xx, keep):
        out = np.empty(n)
        for i in range(n):
            tt = t - t[i]
            w = np.exp(-0.5 * (tt / sigma) ** 2) * span * keep
            s0, s1, s2 = w.sum(), (w * tt).sum(), (w * tt * tt).sum()
            q0, q1 = (w * xx).sum(), (w * tt * xx).sum()
            det = s0 * s2 - s1 * s1
            out[i] = (s2 * q0 - s1 * q1) / det if det > 1e-12 * max(s0, 1e-30) ** 2 else q0 / max(s0, 1e-30)
        return out

    keep = np.ones(n)
    sm = fit(x, keep)
    # 飛び（しぶきの頂へ移った等）を外してもう一度
    bad = np.abs(x - sm) > 0.8
    if bad.any() and (~bad).sum() >= 3:
        keep = (~bad).astype(float)
        sm = fit(x, keep)
    return sm


def crest_from_frame(fr):
    """コマから頂を測る：底につながる水（f > 0.5、4 近傍）の最も高い行。x はその行の水の点の x の平均。
    高さ η は、その行と一つ上の行の f を一次で補間して 0.5 を横切る所（格子より細かく読む）。戻り値 (x, η) か None。"""
    f, cs = fr["f"], fr["cs"]
    X, Y = G.coords(fr)
    solid = cs < 0.5
    wet = (f > 0.5) & ~solid
    lab, n = ndimage.label(wet | solid)
    if n == 0:
        return None
    b = lab[0][lab[0] > 0]
    if len(b) == 0:
        return None
    comp = (lab == np.bincount(b).argmax()) & wet
    rows = np.where(comp.any(1))[0]
    if len(rows) == 0:
        return None
    jt = int(rows.max())
    cols = np.where(comp[jt])[0]
    xc = float(X[cols].mean())
    eta = float(Y[jt])
    if jt + 1 < fr["ny"]:
        fa = f[jt, cols]
        fb = np.where(solid[jt + 1, cols], 0.0, f[jt + 1, cols])
        d = fa - fb
        ok = d > 1e-6
        if ok.any():
            eta = float(np.max(Y[jt] + fr["dx"] * np.clip((fa[ok] - 0.5) / d[ok], 0.0, 1.0)))
    return xc, eta


def _feff(fr):
    """描くための f：静かな水面より下の固体（cs < 0.5）は水として埋める（海底の上に境の線が出ないように）。"""
    X, Y = G.coords(fr)
    F = fr["f"]
    sol = (fr["cs"] < 0.5) & (Y[:, None] < 0.0)
    if sol.any():
        F = np.where(sol, 1.0, F)
    return X, Y, F


def _depth_fn(nodes):
    a = np.asarray(nodes, float)
    a = a[np.argsort(a[:, 0])]
    return lambda x: np.interp(x, a[:, 0], a[:, 1])


# ------------------------------------------------------------------ 計算 1 本の索引
class Run:
    """計算の書き出しの索引：win と full がそろって書き終わったコマだけを、時刻の順に持つ。"""

    def __init__(self, run_dir, meta=None):
        self.dir = os.path.abspath(run_dir)
        self.meta = self._meta(meta or {})
        win = {_fnum(p): p for p in G.frames(self.dir, "win")}
        full = {_fnum(p): p for p in G.frames(self.dir, "full")}
        ks, ts, xs, wp, fp = [], [], [], [], []
        self.full_head = None
        for k in sorted(set(win) & set(full)):
            hw = _head(win[k])
            hf = _head(full[k])
            if hw is None or hf is None or not (hw["complete"] and hf["complete"]):
                continue  # 書きかけのコマ（計算中）は使わない
            ks.append(k); ts.append(hw["t"]); xs.append(hw["xcrest"]); wp.append(win[k]); fp.append(full[k])
            if self.full_head is None:
                self.full_head = hf
                self.win_dx = hw["dx"]
        if len(ks) < 2:
            raise ValueError("コマが足りない：%s" % self.dir)
        o = np.argsort(ts, kind="stable")
        self.k = np.array(ks)[o]
        self.t = np.array(ts)[o]
        self.xcrest = np.array(xs)[o]
        self.win = [wp[i] for i in o]
        self.full = [fp[i] for i in o]
        self.n = len(self.k)
        # 時刻の間隔：通常の間隔（最も大きい、3 回以上ある間隔）と、各コマの受け持つ間隔
        dts = np.diff(self.t)
        vals, cnt = np.unique(np.round(dts, 4), return_counts=True)
        big = vals[cnt >= 3]
        self.base_dt = float(big.max()) if len(big) else float(dts.max())
        self.dt = np.append(dts, dts[-1])
        # log（計算中は短いことがある）
        self.log = {}
        try:
            for r in G.read_log(self.dir):
                self.log[r["frame"]] = r
        except (OSError, ValueError, IndexError):
            pass
        # カメラ：頂の x をなめらかにした列
        self.cam = _smooth_track(self.t, self.xcrest, sigma=0.3)
        # 海底の多角形（静的）
        hf = self.full_head
        self.full_x = (hf["x0"], hf["x0"] + hf["dx"] * (hf["nx"] - 1))
        self.full_y = (hf["y0"], hf["y0"] + hf["dx"] * (hf["ny"] - 1))
        self.solid_poly = self._solid_polygon()

    def _meta(self, m):
        m = dict(m)
        m.setdefault("name", os.path.basename(self.dir.rstrip("/")))
        m.setdefault("title_ja", "")
        m.setdefault("h0_m", 19.0)
        m.setdefault("level", None)
        m.setdefault("bathy", None)
        return m

    def _solid_polygon(self):
        """海底の多角形（h0 の座標）。bathy の節点があればそれで、なければ最初の全体のコマの cs < 0.5 の等値線で。"""
        xl = float(self.meta.get("xl", self.full_x[0]))
        lb = float(self.meta.get("lbox", self.full_x[1] - xl))
        x_a, x_b = xl - 50.0, xl + lb + 50.0
        bottom = min(self.full_y[0], -1.0) - 50.0
        nodes = self.meta.get("bathy")
        if nodes:
            d = _depth_fn(nodes)
            xs = np.unique(np.concatenate([[x_a, xl, xl + lb, x_b], np.asarray(nodes, float)[:, 0]]))
            top = np.column_stack([xs, -d(xs)])
            return np.vstack([top, [[x_b, bottom], [x_a, bottom]]])
        fr = G.read_frame(self.full[0])
        X, Y = G.coords(fr)
        sol = fr["cs"] < 0.5
        if not sol.any():
            return None
        # 各列の、下から続く固体の最も高い所（cs を一次で補間して 0.5）
        top = np.full(fr["nx"], Y[0] - fr["dx"])
        cs = fr["cs"]
        for i in range(fr["nx"]):
            col = cs[:, i]
            j = 0
            while j < fr["ny"] and col[j] < 0.5:
                j += 1
            if j == 0:
                continue
            if j < fr["ny"]:
                a, b = col[j - 1], col[j]
                top[i] = Y[j - 1] + fr["dx"] * (0.5 - a) / max(b - a, 1e-6)
            else:
                top[i] = Y[-1]
        top = ndimage.uniform_filter1d(top, 9, mode="nearest")
        pts = np.column_stack([X, top])
        pts = np.vstack([[[x_a, top[0]]], pts, [[x_b, top[-1]], [x_b, bottom], [x_a, bottom]]])
        return pts

    def frame_pair(self, i):
        return G.read_frame(self.win[i]), G.read_frame(self.full[i])

    def crest_log(self, i):
        r = self.log.get(int(self.k[i]))
        if r is not None and abs(r["t"] - self.t[i]) < 1e-3:
            return r["xcrest"], r["ycrest"]
        return None

    def first_t(self, key="nov", thr=2):
        for k in sorted(self.log):
            if self.log[k].get(key, 0) >= thr:
                return float(self.log[k]["t"])
        return None

    def index_at(self, t, eps=1e-4):
        """時刻 t 以前で最も近いコマの番号（t より前のコマがなければ 0）。"""
        i = int(np.searchsorted(self.t, t + eps, side="right")) - 1
        return max(0, min(self.n - 1, i))


# ------------------------------------------------------------------ 原画の輪郭の重ね方
class Overlay:
    """overlay の指定（None なら既定、False なら重ねない）を、各コマの (x_c, η_c) に読み替える。"""

    def __init__(self, run, spec):
        self.on = spec is not False
        self.t0 = self.t1 = None
        self.eta = self.xc = (np.zeros(0), np.zeros(0))
        self.note = ""
        if not self.on:
            return
        if spec is None or spec == {}:
            t0 = run.first_t("nov", 2)
            if t0 is None:
                self.on = False
                return
            self.t0, self.t1 = t0, t0 + 1.0
            self.note = "既定：log の nov ≥ 2 の最初のコマから 1.0"
        else:
            self.t0 = float(spec["t_start"])
            self.t1 = float(spec["t_end"])
            self.eta = _tdict(spec.get("eta_c_by_t"))
            self.xc = _tdict(spec.get("xc_by_t"))
        self.tol = 0.5 * max(1e-3, float(np.min(run.dt)))

    def crest(self, t, fr_win):
        """そのコマで重ねるなら (x_c, η_c)、重ねないなら None。指定にない時刻は、コマから測る。"""
        if not self.on or t < self.t0 - 1e-6 or t > self.t1 + 1e-6:
            return None
        e = _nearest(*self.eta, t, self.tol)
        x = _nearest(*self.xc, t, self.tol)
        if e is None or x is None:
            c = crest_from_frame(fr_win)
            if c is None:
                return None
            x = c[0] if x is None else x
            e = c[1] if e is None else e
        if not (e > 0.0):
            return None
        return x, e


# ------------------------------------------------------------------ 拡大の枠（頂を追う、縦横 1:1）
class ZoomPanel:
    def __init__(self, fig, rect_px, run, width_h0=7.0, ylim=(-0.65, 1.35), crest_frac=0.45, fs=1.0,
                 scalebar=True, xlabel=True, overlay_label=True):
        W, H = fig.canvas.get_width_height()
        l, b, w, h = rect_px
        self.ax = ax = fig.add_axes([l / W, b / H, w / W, h / H])
        self.run = run
        self.wz = float(width_h0)
        self.ylim = ylim
        self.cf = crest_frac
        ax.set_facecolor(AIR)
        ax.set_ylim(*ylim)
        ax.set_xlim(0, self.wz)
        ax.set_aspect("equal", adjustable="box", anchor="C")
        ax.xaxis.set_major_locator(MultipleLocator(1.0))
        ax.yaxis.set_major_locator(MultipleLocator(0.5))
        ax.tick_params(labelsize=10 * fs, length=3, color=SUB, labelcolor=SUB)
        for s in ax.spines.values():
            s.set_color("#888888")
            s.set_linewidth(0.8)
        if xlabel:
            ax.set_xlabel("x / $h_0$", fontsize=11 * fs, color=SUB, labelpad=2)
        ax.set_ylabel("y / $h_0$", fontsize=11 * fs, color=SUB, labelpad=2)
        if run.solid_poly is not None:
            ax.add_patch(Polygon(run.solid_poly, closed=True, facecolor=SAND, edgecolor=SAND_EDGE, lw=1.0, zorder=3))
        ax.axhline(0.0, color=SWL, lw=1.0, ls=(0, (6, 4)), zorder=4)
        if scalebar:
            # 1 h0 の物差し（軸の幅に対する割合で置く。x の範囲の幅は一定なので長さは 1 h0 のまま）
            frac = 1.0 / self.wz
            x1 = 0.975
            ax.plot([x1 - frac, x1], [0.93, 0.93], transform=ax.transAxes, color=INK, lw=2.4,
                    solid_capstyle="butt", zorder=7)
            for xx in (x1 - frac, x1):
                ax.plot([xx, xx], [0.91, 0.95], transform=ax.transAxes, color=INK, lw=1.2, zorder=7)
            h0m = run.meta.get("h0_m", 19.0)
            ax.text(x1 - frac / 2, 0.955, "1 $h_0$ = %g m" % h0m, transform=ax.transAxes, ha="center", va="bottom",
                    fontsize=10 * fs, color=INK, zorder=7)
        self.fill = []
        self.air = Rectangle((0, 0), 1, 1, facecolor=AIR, edgecolor="none", zorder=1.8)
        ax.add_patch(self.air)
        (self.ov_out,) = ax.plot([], [], color=OVER, lw=1.6 * fs, zorder=5, solid_joinstyle="round")
        (self.ov_in,) = ax.plot([], [], color=OVER, lw=1.6 * fs, zorder=5, solid_joinstyle="round")
        (self.ov_pt,) = ax.plot([], [], marker="+", ms=9 * fs, mew=1.6, color=OVER, zorder=5, ls="none")
        self.ov_lab = None
        if overlay_label:
            self.ov_lab = ax.text(0.012, 0.965, "", transform=ax.transAxes, ha="left", va="top", fontsize=10.5 * fs,
                                  color=OVER, zorder=8,
                                  bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75))
            self.ov_lab.set_visible(False)

    def view(self, i):
        x0 = float(self.run.cam[i]) - self.cf * self.wz
        return x0, x0 + self.wz

    def update(self, i, fr_win, fr_full, ov=None):
        """i 番目のコマを描く。ov は (x_c, η_c) か None。戻り値：表示した x の範囲。"""
        ax = self.ax
        for c in self.fill:
            c.remove()
        self.fill = []
        xa, xb = self.view(i)
        ya, yb = self.ylim
        # 窓の外の所は全体のコマで埋める（カメラが窓の端に寄ったとき用）
        Xf, Yf, Ff = _feff(fr_full)
        ia = max(0, int(np.searchsorted(Xf, xa)) - 2)
        ib = min(len(Xf), int(np.searchsorted(Xf, xb)) + 2)
        ja = max(0, int(np.searchsorted(Yf, ya)) - 2)
        jb = min(len(Yf), int(np.searchsorted(Yf, yb)) + 2)
        if ib - ia >= 2 and jb - ja >= 2:
            sub = Ff[ja:jb, ia:ib]
            if (sub > 0.5).any():
                self.fill.append(ax.contourf(Xf[ia:ib], Yf[ja:jb], sub, levels=[0.5, 1.5], colors=[WATER], zorder=1))
        # 窓（細かい格子）
        Xw, Yw, Fw = _feff(fr_win)
        self.air.set_bounds(Xw[0], Yw[0], Xw[-1] - Xw[0], Yw[-1] - Yw[0])
        if (Fw > 0.5).any():
            self.fill.append(ax.contourf(Xw, Yw, Fw, levels=[0.5, 1.5], colors=[WATER], zorder=2))
            if (Fw < 0.5).any():
                self.fill.append(ax.contour(Xw, Yw, Fw, levels=[0.5], colors=[WATER_LINE], linewidths=1.3, zorder=2.5))
        ax.set_xlim(xa, xb)
        if ov is not None:
            out, inn, s = painting_in_h0(ov[1], ov[0])
            self.ov_out.set_data(out[:, 0], out[:, 1])
            self.ov_in.set_data(inn[:, 0], inn[:, 1])
            self.ov_pt.set_data([ov[0]], [ov[1]])
            if self.ov_lab is not None:
                self.ov_lab.set_text("原画の輪郭（縦÷1.3、頂の高さと位置を合わせた）\n頂 $\\eta_c$ = %.3f $h_0$、$x_c$ = %.2f $h_0$（原画 1000 px = %.3f $h_0$）"
                                     % (ov[1], ov[0], 1000.0 * s))
                self.ov_lab.set_visible(True)
        else:
            for a in (self.ov_out, self.ov_in, self.ov_pt):
                a.set_data([], [])
            if self.ov_lab is not None:
                self.ov_lab.set_visible(False)
        return xa, xb


# ------------------------------------------------------------------ 全体の枠（縦を伸ばした側面）
class OverviewPanel:
    def __init__(self, fig, rect_px, run, fs=1.0):
        W, H = fig.canvas.get_width_height()
        l, b, w, h = rect_px
        self.run = run
        m = run.meta
        xl = float(m.get("xl", run.full_x[0]))
        lb = float(m.get("lbox", run.full_x[1] - xl))
        self.xlim = (xl, xl + lb)
        self.ylim = (run.full_y[0], run.full_y[1])
        pxh0 = w / lb
        self.ex = max(1, int(math.floor(h / ((self.ylim[1] - self.ylim[0]) * pxh0))))
        hh = (self.ylim[1] - self.ylim[0]) * pxh0 * self.ex
        b2 = b + (h - hh) / 2.0
        self.ax = ax = fig.add_axes([l / W, b2 / H, w / W, hh / H])
        self.rect_px = (l, b2, w, hh)
        ax.set_facecolor(AIR)
        ax.set_xlim(*self.xlim)
        ax.set_ylim(*self.ylim)
        ax.set_aspect(self.ex, adjustable="box", anchor="C")
        ax.xaxis.set_major_locator(MultipleLocator(5.0))
        ax.yaxis.set_major_locator(MultipleLocator(0.5))
        ax.tick_params(labelsize=10 * fs, length=3, color=SUB, labelcolor=SUB)
        for s in ax.spines.values():
            s.set_color("#888888")
            s.set_linewidth(0.8)
        ax.set_xlabel("x / $h_0$", fontsize=11 * fs, color=SUB, labelpad=1)
        ax.set_ylabel("y / $h_0$", fontsize=11 * fs, color=SUB, labelpad=2)
        if run.solid_poly is not None:
            ax.add_patch(Polygon(run.solid_poly, closed=True, facecolor=SAND, edgecolor=SAND_EDGE, lw=0.8, zorder=3))
        ax.axhline(0.0, color=SWL, lw=0.9, ls=(0, (6, 4)), zorder=4)
        # 5 h0 の物差し（左上の空気の所）
        h0m = m.get("h0_m", 19.0)
        sx0 = xl + 0.02 * lb
        sy = self.ylim[1] - 0.16 * (self.ylim[1] - self.ylim[0])
        ax.plot([sx0, sx0 + 5.0], [sy, sy], color=INK, lw=2.4, solid_capstyle="butt", zorder=7)
        tk = 0.035 * (self.ylim[1] - self.ylim[0])
        for xx in (sx0, sx0 + 5.0):
            ax.plot([xx, xx], [sy - tk, sy + tk], color=INK, lw=1.2, zorder=7)
        ax.text(sx0 + 5.4, sy, "5 $h_0$ = %g m（1 $h_0$ = %g m）" % (5 * h0m, h0m), ha="left", va="center",
                fontsize=10 * fs, color=INK, zorder=7)
        self.fill = []
        # 拡大の範囲と頂の印
        self.zrect = Rectangle((0, 0), 1, 1, facecolor="none", edgecolor="#333333", lw=0.9, ls=(0, (3, 2)), zorder=6)
        ax.add_patch(self.zrect)
        (self.mark,) = ax.plot([], [], marker="v", ms=8 * fs, color=MARK, mec="white", mew=0.6, ls="none", zorder=8)
        self.mark_off = 9.0 / (pxh0 * self.ex)   # 頂の 9 px 上に置く

    def update(self, i, fr_full, zoom_x=None, zoom_y=None):
        ax = self.ax
        for c in self.fill:
            c.remove()
        self.fill = []
        X, Y, F = _feff(fr_full)
        if (F > 0.5).any():
            self.fill.append(ax.contourf(X, Y, F, levels=[0.5, 1.5], colors=[WATER], zorder=2))
        c = self.run.crest_log(i)
        if c is None:
            c = (self.run.xcrest[i], np.nan)
        if np.isfinite(c[1]):
            self.mark.set_data([c[0]], [c[1] + self.mark_off])
        else:
            self.mark.set_data([], [])
        if zoom_x is not None:
            self.zrect.set_bounds(zoom_x[0], zoom_y[0], zoom_x[1] - zoom_x[0], zoom_y[1] - zoom_y[0])


# ------------------------------------------------------------------ ffmpeg
def _ffmpeg_cmd(out, w, h, fps, crf=28):
    return ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-threads", "2", "-movflags", "+faststart", out]


def _shrink(out, crf, limit=SIZE_LIMIT):
    """上限を超えたら crf を上げて作り直す。戻り値：最後の crf。"""
    while os.path.getsize(out) > limit and crf < 45:
        crf += 4
        tmp = out + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-c:v", "libx264", "-preset", "slow",
                        "-crf", str(crf), "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart", tmp],
                       check=True)
        shutil.move(tmp, out)
    return crf


class _Writer:
    def __init__(self, fig, out, fps, crf=28):
        self.fig = fig
        self.w, self.h = fig.canvas.get_width_height()
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
        self.out = out
        self.crf = crf
        self.p = subprocess.Popen(_ffmpeg_cmd(out, self.w, self.h, fps, crf), stdin=subprocess.PIPE)
        self.count = 0

    def frame(self):
        self.fig.canvas.draw()
        buf = np.asarray(self.fig.canvas.buffer_rgba())
        self.p.stdin.write(np.ascontiguousarray(buf[:, :, :3]).tobytes())
        self.count += 1

    def close(self):
        self.p.stdin.close()
        rc = self.p.wait()
        if rc != 0:
            raise RuntimeError("ffmpeg が失敗した（終了の符号 %d）" % rc)
        return _shrink(self.out, self.crf)


def _speed_note(run, i, fps):
    dt = float(run.dt[i])
    slow = run.base_dt / dt if dt > 0 else 1.0
    if slow >= 1.5:
        return "スロー ×%d（1 コマ Δ$\\tilde{t}$ = %.2f）" % (int(round(slow)), dt)
    return "通常の速さ（1 コマ Δ$\\tilde{t}$ = %.2f、1 秒 = %.1f $\\tilde{t}$）" % (dt, dt * fps)


def _sel(n, stride=1, max_frames=None):
    idx = list(range(0, n, max(1, int(stride))))
    if max_frames is not None and len(idx) > max_frames:
        idx = list(np.linspace(0, n - 1, int(max_frames)).round().astype(int))
    return idx


# ------------------------------------------------------------------ 1 本の動画
def render_case(run_dir, out_mp4, meta, overlay=None, fps=25, width=1280, height=960, stride=1, max_frames=None,
                t_range=None, verbose=True):
    """1 本の計算を動画にする。上：全体（縦を伸ばす）、下：頂を追う拡大（縦横 1:1）と原画の輪郭。
    overlay：None で既定（log の nov ≥ 2 の最初の時刻から 1.0 の間、頂はコマから測る）、False で重ねない、
    dict {t_start, t_end, eta_c_by_t, xc_by_t}（長さは h0）で指定。戻り値：作った動画の要約（dict）。"""
    t_start = time.time()
    run = Run(run_dir, meta)
    ov = Overlay(run, overlay)
    m = run.meta
    fs = min(width / 1280.0, height / 960.0)
    fig = plt.figure(figsize=(width / 100.0, height / 100.0), dpi=100)
    fig.patch.set_facecolor("white")
    W, H = width, height
    sx, sy = W / 1280.0, H / 960.0

    # 見出し
    lvl = m.get("level")
    head1 = m["name"] + ("　" + m["title_ja"] if m.get("title_ja") else "")
    fig.text(16 * sx / W, 1 - 22 * sy / H, head1, fontsize=14 * fs, weight="bold", color=INK, va="center")
    sub = []
    if lvl is not None:
        sub.append("格子 %d 段（最も細かい格子 Δ = %.4f $h_0$）" % (int(lvl), run.win_dx))
    sub.append("$h_0$ = %g m（静かな水の深さ）" % m.get("h0_m", 19.0))
    fig.text(16 * sx / W, 1 - 50 * sy / H, "　".join(sub), fontsize=11.5 * fs, color=SUB, va="center")
    t_txt = fig.text(1 - 16 * sx / W, 1 - 22 * sy / H, "", fontsize=15 * fs, color=INK, va="center", ha="right")
    sp_txt = fig.text(1 - 16 * sx / W, 1 - 50 * sy / H, "", fontsize=12 * fs, color=INK, va="center", ha="right")

    # 上：全体
    ov_rect = (70 * sx, 540 * sy, W - 94 * sx, 312 * sy)
    top = OverviewPanel(fig, ov_rect, run, fs=fs)
    l, b2, w2, h2 = top.rect_px
    fig.text(l / W, (b2 + h2 + 8 * sy) / H, "全体の側面（縦 ×%d：縦だけ %d 倍に伸ばした）　▼ 頂（計算が追う所）　点線の枠：下の拡大の範囲　破線：静かな水面"
             % (top.ex, top.ex), fontsize=11 * fs, color=SUB, va="bottom", ha="left")

    fig.text((l + w2) / W, (b2 - 46 * sy) / H, "波から遠い所の水面の角ばり：最も粗い段（5）の格子に海底と水面が一緒に入り、そこの水の量も正しくない（波の形への効きは小さいことを確かめた）",
             fontsize=9.5 * fs, color=SUB, va="top", ha="right")

    # 下：拡大（縦横 1:1）
    wz, yl = 7.0, (-0.65, 1.35)
    avail_w, avail_h = W - 94 * sx, 360 * sy
    pxh0 = min(avail_w / wz, avail_h / (yl[1] - yl[0]))
    zw, zh = wz * pxh0, (yl[1] - yl[0]) * pxh0
    zl = 70 * sx + (avail_w - zw) / 2.0
    zb = 56 * sy
    zoom = ZoomPanel(fig, (zl, zb, zw, zh), run, width_h0=wz, ylim=yl, fs=fs)
    fig.text(zl / W, (zb + zh + 8 * sy) / H, "頂を追う拡大（縦横 1:1、幅 %g $h_0$）　線：水と空気の境（f = 0.5）　破線：静かな水面（y = 0）" % wz,
             fontsize=11 * fs, color=SUB, va="bottom", ha="left")

    idx = list(range(run.n))
    if t_range is not None:
        idx = [i for i in idx if t_range[0] - 1e-6 <= run.t[i] <= t_range[1] + 1e-6]
    idx = [idx[j] for j in _sel(len(idx), stride, max_frames)]
    wr = _Writer(fig, out_mp4, fps)
    tmeas = 0.0
    n_ov = 0
    h0m = float(m.get("h0_m", 19.0))
    for j, i in enumerate(idx):
        t0 = time.time()
        fw, ff = run.frame_pair(i)
        t = fw["t"]
        crest = ov.crest(t, fw)
        n_ov += crest is not None
        zx = zoom.update(i, fw, ff, crest)
        top.update(i, ff, zoom_x=zx, zoom_y=yl)
        t_txt.set_text("$\\tilde{t} = t\\sqrt{g/h_0}$ = %.2f（$h_0$ = %g m の実寸で %.1f s）"
                       % (t, h0m, t * math.sqrt(h0m / G_SI)))
        sp_txt.set_text(_speed_note(run, i, fps))
        wr.frame()
        tmeas += time.time() - t0
        if verbose and (j % 50 == 0 or j == len(idx) - 1):
            print("  %s：%d/%d コマ（t = %.2f）" % (os.path.basename(out_mp4), j + 1, len(idx), t), flush=True)
    crf = wr.close()
    plt.close(fig)
    res = dict(out=os.path.abspath(out_mp4), frames=wr.count, seconds_video=wr.count / float(fps),
               render_s=time.time() - t_start, per_frame_s=tmeas / max(1, wr.count),
               size_bytes=os.path.getsize(out_mp4), crf=crf, overlay_frames=n_ov,
               overlay_t=(ov.t0, ov.t1) if ov.on else None, t_first=float(run.t[idx[0]]), t_last=float(run.t[idx[-1]]))
    if verbose:
        print("  できた：%s（%d コマ、%.1f MB、%.1f s、1 コマ %.3f s）" % (res["out"], res["frames"], res["size_bytes"] / 1e6,
                                                               res["render_s"], res["per_frame_s"]), flush=True)
    return res


# ------------------------------------------------------------------ 比較の動画
def _grid(n, W, H, top, wz, hz, mx=74.0, my=80.0):
    """n 枚の枠を、縦横 1:1 の拡大が最も大きく見える行と列に並べる。"""
    best = None
    for cols in range(1, n + 1):
        rows = int(math.ceil(n / float(cols)))
        cw, ch = W / cols, (H - top) / rows
        s = min((cw - mx) / wz, (ch - my) / hz)
        if best is None or s > best[0] + 1e-9:
            best = (s, rows, cols)
    return best


def _load_meta(m):
    if isinstance(m, str):
        with open(m, encoding="utf8") as fp:
            return json.load(fp)
    return dict(m or {})


def render_compare(cases, out_mp4, fps=25, width=1600, height=900, tau_start=None, tau_end=0.6, width_h0=7.0,
                   verbose=True):
    """複数の計算（2〜6 本）を τ = t − t_ref でそろえて並べる。各枠は頂を追う拡大（縦横 1:1）。
    cases：[{run_dir, meta, t_ref, score_by_t（任意）, overlay（任意。None・省略で既定、False で重ねない）}]。
    τ の範囲：tau_start（省略なら全員にコマがある最初の τ）から tau_end まで。コマのない τ では、その前の最も近いコマを出す。"""
    t_start = time.time()
    if not 1 <= len(cases) <= 6:
        raise ValueError("比較は 1〜6 本まで（%d 本）" % len(cases))
    runs, ovs, trefs, scores = [], [], [], []
    for c in cases:
        r = Run(c["run_dir"], _load_meta(c.get("meta")))
        runs.append(r)
        ovs.append(Overlay(r, c.get("overlay")))
        tr = c.get("t_ref")
        if tr is None:
            tr = r.first_t("nov", 2)
            if tr is None:
                raise ValueError("t_ref がなく、log の nov ≥ 2 もない：%s" % r.dir)
        trefs.append(float(tr))
        scores.append(_tdict(c.get("score_by_t")))
    # τ の並び：各時刻で、いちばん細かい計算の間隔で進む
    tau0 = max(r.t[0] - tr for r, tr in zip(runs, trefs)) if tau_start is None else float(tau_start)
    tau_max = max(r.t[-1] - tr for r, tr in zip(runs, trefs))
    tau1 = min(float(tau_end), tau_max)
    taus = []
    tau = tau0
    while tau <= tau1 + 1e-6 and len(taus) < 20000:
        taus.append(round(tau, 6))
        st = min(float(r.dt[r.index_at(tau + tr)]) for r, tr in zip(runs, trefs))
        tau += max(st, 1e-3)
    base_dt = max(r.base_dt for r in runs)

    W, H = width, height
    fs = min(W / 1600.0, H / 900.0)
    fig = plt.figure(figsize=(W / 100.0, H / 100.0), dpi=100)
    fig.patch.set_facecolor("white")
    hdr = 66 * fs
    yl = (-0.65, 1.35)
    s, rows, cols = _grid(len(runs), W, H, hdr, width_h0, yl[1] - yl[0], mx=78 * fs, my=84 * fs)
    s = max(s, 10.0)
    fig.text(16 / W, 1 - 22 * fs / H, "比較：τ = t − $t_{ref}$ でそろえる（各枠は頂を追う拡大、縦横 1:1、幅 %g $h_0$）" % width_h0,
             fontsize=15 * fs, weight="bold", color=INK, va="center")
    any_ov = any(o.on for o in ovs)
    leg = "線：水と空気の境（f = 0.5）　破線：静かな水面　目盛りは $h_0$"
    if any_ov:
        leg += "　橙の線：原画の輪郭（縦÷1.3、頂の高さと位置を合わせた）"
    fig.text(16 / W, 1 - 50 * fs / H, leg, fontsize=11 * fs, color=SUB, va="center")
    tau_txt = fig.text(1 - 16 / W, 1 - 22 * fs / H, "", fontsize=15 * fs, color=INK, va="center", ha="right")
    sp_txt = fig.text(1 - 16 / W, 1 - 50 * fs / H, "", fontsize=12 * fs, color=INK, va="center", ha="right")
    panels, ptitle, pinfo = [], [], []
    zw, zh = width_h0 * s, (yl[1] - yl[0]) * s
    # 枠を詰めて並べ、まとまり全体を見出しの下の中央に置く（行の間に大きな空きを作らない）
    cw = min(W / cols, zw + 78 * fs + 24 * fs)
    ch = min((H - hdr) / rows, zh + 84 * fs + 16 * fs)
    gx0 = (W - cols * cw) / 2.0
    gy1 = H - hdr - ((H - hdr) - rows * ch) / 2.0
    for k, r in enumerate(runs):
        rr, cc = divmod(k, cols)
        cx0 = gx0 + cc * cw
        cy0 = gy1 - (rr + 1) * ch
        zl = cx0 + 60 * fs + (cw - 78 * fs - zw) / 2.0
        zb = cy0 + 40 * fs + (ch - 84 * fs - zh) / 2.0
        p = ZoomPanel(fig, (zl, zb, zw, zh), r, width_h0=width_h0, ylim=yl, fs=0.9 * fs, xlabel=False,
                      overlay_label=False)
        panels.append(p)
        lvl = r.meta.get("level")
        name = r.meta["name"] + ("（%d 段）" % int(lvl) if lvl is not None else "")
        ptitle.append(fig.text(zl / W, (zb + zh + 6 * fs) / H, name, fontsize=13 * fs, weight="bold", color=INK,
                               va="bottom", ha="left"))
        pinfo.append(fig.text((zl + zw) / W, (zb + zh + 6 * fs) / H, "", fontsize=11.5 * fs, color=INK,
                              va="bottom", ha="right"))

    wr = _Writer(fig, out_mp4, fps)
    tmeas = 0.0
    for j, tau in enumerate(taus):
        t0 = time.time()
        dts = []
        for k, (r, tr, p) in enumerate(zip(runs, trefs, panels)):
            i = r.index_at(tau + tr)
            fw, ff = r.frame_pair(i)
            t = fw["t"]
            p.update(i, fw, ff, ovs[k].crest(t, fw))
            dts.append(float(r.dt[i]))
            info = "τ = %+.2f　$\\tilde{t}$ = %.2f" % (t - tr, t)
            if len(scores[k][0]):
                # 最も近い時刻の値。そのコマの値でなければ、値の時刻を添える
                ts_, vs_ = scores[k]
                q = int(np.argmin(np.abs(ts_ - t)))
                if abs(ts_[q] - t) <= 5e-3:
                    info += "　score3 = %.2f" % vs_[q]
                elif abs(ts_[q] - t) <= 0.1 + 1e-6:
                    info += "　score3 = %.2f（$\\tilde{t}$ = %.2f の値）" % (vs_[q], ts_[q])
                else:
                    info += "　score3 —"
            if tau + tr > r.t[-1] + 1e-3:
                info += "（計算はここまで）"
            elif abs((t - tr) - tau) > 5e-3:
                info += "（前のコマ）"
            pinfo[k].set_text(info)
        tau_txt.set_text("τ = t − $t_{ref}$ = %+.2f" % tau)
        dt = min(dts) if j + 1 >= len(taus) else (taus[j + 1] - tau)
        slow = base_dt / dt if dt > 0 else 1.0
        if slow >= 1.5:
            sp_txt.set_text("スロー ×%d（1 コマ Δτ = %.2f）" % (int(round(slow)), dt))
        else:
            sp_txt.set_text("通常の速さ（1 コマ Δτ = %.2f、1 秒 = %.1f）" % (dt, dt * fps))
        wr.frame()
        tmeas += time.time() - t0
        if verbose and (j % 50 == 0 or j == len(taus) - 1):
            print("  %s：%d/%d コマ（τ = %+.2f）" % (os.path.basename(out_mp4), j + 1, len(taus), tau), flush=True)
    crf = wr.close()
    plt.close(fig)
    res = dict(out=os.path.abspath(out_mp4), frames=wr.count, seconds_video=wr.count / float(fps),
               render_s=time.time() - t_start, per_frame_s=tmeas / max(1, wr.count),
               size_bytes=os.path.getsize(out_mp4), crf=crf, tau=(taus[0], taus[-1]), grid=(rows, cols))
    if verbose:
        print("  できた：%s（%d コマ、%.1f MB、%.1f s、1 コマ %.3f s）" % (res["out"], res["frames"], res["size_bytes"] / 1e6,
                                                               res["render_s"], res["per_frame_s"]), flush=True)
    return res


# ------------------------------------------------------------------ 命令行
def _load_overlay(a):
    if a is None:
        return None
    if a.lower() == "none":
        return False
    with open(a, encoding="utf8") as fp:
        return json.load(fp)


def main(argv=None):
    ap = argparse.ArgumentParser(description="gw_shoal の書き出しを動画にする")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("case", help="1 本の計算（上：全体、下：頂を追う拡大）")
    a.add_argument("run_dir")
    a.add_argument("out")
    a.add_argument("--meta", required=True, help="META.json（name, title_ja, bathy, xl, lbox, level, h0_m）")
    a.add_argument("--overlay", default=None, help="OVERLAY.json か none（省略で既定の重ね方）")
    a.add_argument("--fps", type=int, default=25)
    a.add_argument("--width", type=int, default=1280)
    a.add_argument("--height", type=int, default=960)
    a.add_argument("--stride", type=int, default=1)
    a.add_argument("--max-frames", type=int, default=None)
    a.add_argument("--t-range", type=float, nargs=2, default=None)
    c = sp.add_parser("compare", help="複数の計算を τ = t − t_ref でそろえて並べる")
    c.add_argument("cases", help="CASES.json（case の dict の配列、または {cases: [...], tau_start, tau_end}）")
    c.add_argument("out")
    c.add_argument("--fps", type=int, default=25)
    c.add_argument("--width", type=int, default=1600)
    c.add_argument("--height", type=int, default=900)
    c.add_argument("--tau-start", type=float, default=None)
    c.add_argument("--tau-end", type=float, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "case":
        res = render_case(args.run_dir, args.out, _load_meta(args.meta), overlay=_load_overlay(args.overlay),
                          fps=args.fps, width=args.width, height=args.height, stride=args.stride,
                          max_frames=args.max_frames, t_range=args.t_range)
    else:
        with open(args.cases, encoding="utf8") as fp:
            spec = json.load(fp)
        if isinstance(spec, dict):
            cases = spec["cases"]
            ts = spec.get("tau_start")
            te = spec.get("tau_end", 0.6)
        else:
            cases, ts, te = spec, None, 0.6
        if args.tau_start is not None:
            ts = args.tau_start
        if args.tau_end is not None:
            te = args.tau_end
        res = render_compare(cases, args.out, fps=args.fps, width=args.width, height=args.height, tau_start=ts,
                             tau_end=te)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
