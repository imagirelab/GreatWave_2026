# -*- coding: utf-8 -*-
"""FLIP49：周期の波の計算（PER49）の動画（py -3.10 -B、numpy・scipy・scikit-image・PIL・ffmpeg）。2026-10-15 新しく書いた。
g48_video.py（flip48、変えていない）を読み込み、この起動の中だけ次を読み替える（ファイルは書き換えない。g48_video2.py は読まない）：
  - 記録の読み：g49_periodic_ana.Ctx49（海底は g49_common.bed_z。PG12s の段・礁の上・礁湖が断面の砂の色と上からの等深線に出る）。
    g48_video をそのまま FLIP49 の記録に使うと Ctx48（FLIP48 の海底の式）になり、段と礁湖が描けないため。出力は Unity/Build/FLIP49 の中だけ。
  - 頭書き：FLIP49 の海底・入口の帯の規則波・粒子と「選んだ物・計算した物」。
  - 崩れごと：<記録>/pana/periodic_ana.json の崩れ k の窓 [t_on − T/2, t_on + T/2] の中では、その崩れの ana.json（pana/waves/kNN）の
    巻き始めを青い印に、拡大の窓をその崩れの巻き始めの x に合わせる。
  - 原画に最も近い瞬間（利用者 2026-10-15「大浪最像原画的时候用红框框出来」）：<記録>/pana/best_frames.json（g49_periodic_ana.py all が
    凍らせた決まりで選んだコマ、score3 = g47_video.score3）の各崩れのコマで、横からの図の頂のまわりと拡大の図を太い赤の枠で囲み、
    拡大の図に原画の輪郭（g47_video.print_phys：縦の伸びを戻した原画の輪郭を、そのコマの η_c と頂の x に合わせた物）を太い黒の線で重ね、
    1 s 止める。巻き始め〜着水 + 0.5 s の間は同じ輪郭を細い黒の破線で重ねる。その前後 [−0.75 s, +0.5 s] は 0.25 倍のスロー、ほかは 2 倍の早送り。
  - 並べ方：板（半幅 ≤ 12 m）は 横からの全体・崩れる頂の拡大（左下）・崩れごとの量の表と来る波の列（波高計の時系列、右下）。
    3D は g48_video の 4 つの図（横から・上から・拡大・斜め上から・頂の高さの横の分け方 c(y)）の上に同じ赤い枠と輪郭を重ねる。
使い方：
  py -3.10 -B g49_video.py <記録> [--speed=2] [--slow=0.25] [--hold=1] [--t0=<s>] [--t1=<s>] [--label=..] [--still=<s>|best] [--sup=0]
  pana/sup/sup.json（g49_periodic_ana.py sup の補いの読み）があれば、その崩れ s1, s2, … も紫の印と赤い枠で出す（--sup=0 で出さない）。
出す物：<記録>/video/<名前>_periodic.mp4・_periodic.json・_periodic_best.png（どの計算も mp4 を出す：この研究の決まり）。--still は PNG 1 枚。
数の印：形の量・score3 は g49_periodic_ana.py の値（AI の読み）。原画らしさは利用者が決める。
2026-10-15 直した（方案 A を実装する役）：D0 の 3D の動画は g48_video の図の上に字を重ねて読めず、拡大の窓（V46.zoom_window）が崩れごとの窓と
  原画に最も近いコマの頂を外していた。既定では g49_video2.py（崩れごとに g48_video2 の比べの図・赤い枠・原画の輪郭・3D の前から斜めの図・c(y)、
  拡大の窓は最も近いコマの頂を 20 m 内側に、字の重なりを確かめる。と計算の全部の 2 倍の動画）を呼ぶ。前の並べ方は --legacy=1 で出す
  （3D の拡大の窓は zoom_range に直した）。
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46", r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47",
           r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48", _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                   # noqa: E402
from PIL import Image, ImageDraw     # noqa: E402
import g48_video as V48              # noqa: E402  g46_video の関数を g48 の物に読み替える（読み込むだけ）
import g49_periodic_ana as PA        # noqa: E402  A46.Ctx = Ctx49・A46.B46 = Build/FLIP49（この起動の中だけ）
import g49_common as GC              # noqa: E402
import g47_video as GV               # noqa: E402  print_phys・text_fit・label_box・dashed・Writer・probe（読むだけ）

V46 = V48.V46
A46 = PA.A46
font = V46.font
W, H = V46.W, V46.H
RED = (205, 30, 30)
FPS = 24


def _g(v, f="%g"):
    return "—" if v is None else (f % v)


def heads49(D, opt):
    cx = D.cx
    c = cx.cfg
    w = c.get("wave") or {}
    P = c.get("parms") or {}
    strip = float(P.get("W", 85.0)) <= 12.0
    kind = "準 2D の板（真ん中の断面を横に一様、半幅 %g m）" % float(P.get("W")) if strip else "3D の半分の水槽（半幅 %g m、y = 0 は対称の面）" % float(P.get("W"))
    head = "FLIP49 %s：%s。海底 %s。入口の帯で規則波 T %s s・H %s m。粒子 %.4g m%s。力は重力だけ %s" % (
        D.name, kind, GC.bed_kind(GC.bed_spec(c, parms=P)), _g(w.get("T_s")), _g(w.get("H_m")), cx.dp, "（粗い）" if cx.dp > 0.25 + 1e-9 else "",
        opt.get("label", ""))
    sub = ("縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。x は上流の壁から（m）。入口の帯 0〜%g m・出口の帯 %g〜%g m は図の外。"
           "選んだ物：波の T・H（in_gain %s）と海底。計算した物：崩れ・巻き。赤い枠＝原画に最も近い瞬間（score3 の最小、AI の読み。原画らしさは利用者が決める）" % (
               D.off, float(P.get("xg_end", 100.0)), float(P.get("xa0", 290.0)), float(P.get("Lx", 360.0)), _g(w.get("in_gain"), "%.4g")))
    return head, sub


def bed_title(D):
    b = D.cx.bed49
    if not b.get("on", True):
        return "砂の色＝海底（平ら %g m）" % float(b.get("h0", 17.0))
    if GC.is_new(b):
        return "砂の色＝真ん中の海底：1:%g で %g → %g m（集める所）、1:%g の段で礁の上 %g m、その先 1:%g で礁湖 %g m" % (
            float(b["s"]), float(b["h0"]), float(b["pg_hL"]), float(b["pg_s2"]), float(b["shelf_h"]), float(b["s_back"]), float(b["h_lag"]))
    return "砂の色＝真ん中の海底"


class Periodic:
    """崩れの表・崩れごとの ana.json・原画に最も近いコマ（best_frames.json）・波高計の時系列。"""

    def __init__(self, rd, T, use_sup=True):
        od = os.path.join(rd, "pana")
        p = os.path.join(od, "periodic_ana.json")
        if not os.path.exists(p):
            raise SystemExit("先に py -3.10 -B g49_periodic_ana.py all %s（%s がない）" % (rd, p))
        self.pa = json.load(open(p, encoding="utf8"))
        self.T = T
        self.ev = []
        for e in self.pa.get("events_found") or []:
            self.ev.append(dict(e, lab="k%d" % int(e["k"]), sup=False))
        bp = os.path.join(od, "best_frames.json")
        self.best = {}
        if os.path.exists(bp):
            for r in json.load(open(bp, encoding="utf8")).get("per_breaker") or []:
                if r.get("frame") is not None:
                    self.best["k%d" % int(r["k"])] = r
        self.ana = {}
        for e in self.ev:
            ap = os.path.join(od, "waves", "k%02d" % int(e["k"]), "ana.json")
            self.ana[e["lab"]] = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
        self.rows = {"k%d" % int(r["k"]): r for r in (self.pa.get("waves") or [])}
        # 補いの読み（g49_periodic_ana.py sup、凍らせた崩れの選びの外）：名前 s1, s2, …
        sp = os.path.join(od, "sup", "sup.json")
        self.has_sup = os.path.exists(sp) and not use_sup is False
        if self.has_sup:
            su = json.load(open(sp, encoding="utf8"))
            for i, e in enumerate(su.get("events") or []):
                lab = str(e["k"])
                self.ev.append(dict(e, lab=lab, sup=True))
                ap = os.path.join(od, "sup", "s%02d" % (i + 1), "ana.json")
                self.ana[lab] = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else {}
            for r in su.get("per_breaker") or []:
                if r.get("frame") is not None:
                    self.best[str(r["k"])] = r
            for r in su.get("waves") or []:
                self.rows[str(r["k"])] = r
        self.ev.sort(key=lambda e: e["on_t"])
        R = PA.load_r6(rd)
        self.gt = R["t"]
        self.g = {}
        for j, (xg, yg) in enumerate(R["gxy"]):
            if abs(float(yg) - GC.GAUGE_Y[0]) < 1e-6:
                self.g[float(xg)] = R["gauge"][:, j]

    def k_at(self, t):
        for e in self.ev:
            if e["on_t"] - 0.5 * self.T <= t < e["on_t"] + 0.5 * self.T:
                return e
        return None

    def best_frames(self):
        return {int(r["frame"]): lab for lab, r in self.best.items()}


def _XY(g, x, z):
    return g["px0"] + (x - g["x0"]) * g["s"], g["py0"] + (g["z1"] - z) * g["s"]


def sec_geom(px0, py0, px1, x0, x1, z0, z1):
    """g46_video.section と同じ置き方（縦横同じ縮尺、s = 幅 / x の範囲）。"""
    s = (px1 - px0) / (x1 - x0)
    return dict(px0=px0, py0=py0, px1=px1, s=s, ph=int(round((z1 - z0) * s)), x0=x0, x1=x1, z0=z0, z1=z1)


def print_outline(dr, g, x_c, eta_c, width, dash):
    for q in GV.print_phys(x_c, eta_c):
        pts = [_XY(g, x, z) for x, z in q]
        segs, cur = [], []
        for (u, v) in pts:
            if g["px0"] <= u <= g["px1"] and g["py0"] <= v <= g["py0"] + g["ph"]:
                cur.append((u, v))
            elif cur:
                segs.append(cur); cur = []
        if cur:
            segs.append(cur)
        for sg in segs:
            if len(sg) > 1:
                if dash:
                    GV.dashed(dr, sg, (0, 0, 0), width)
                else:
                    dr.line(sg, fill=(0, 0, 0), width=width)


def state_banner(dr, x, y, state, speed, slow, hold_s, k):
    if state == "hold":
        txt, col = "止め %.1f s：原画に最も近い瞬間（崩れ %s）" % (hold_s, k), RED
    elif state == "slow":
        txt, col = "%.3g 倍のスロー（計算の 1 s を %.3g s で）" % (slow, 1.0 / slow), (225, 120, 20)
    elif abs(speed - 1.0) > 1e-9:
        txt, col = "%.3g 倍の早送り（計算の 1 s を %.3g s で）" % (speed, 1.0 / speed), (20, 60, 200)
    else:
        txt, col = "実時間", (90, 90, 90)
    fz = font(16, True)
    w = dr.textlength(txt, font=fz)
    dr.rectangle([x, y, x + w + 16, y + 26], fill=col)
    dr.text((x + 8, y + 3), txt, fill=(255, 255, 255), font=fz)


def _shape_row(ana, f):
    for r in ((ana.get("shape") or {}).get("series") or []):
        if int(r.get("frame", -1)) == int(f):
            return r
    return None


def set_breaker(D, PR, t):
    e = PR.k_at(t)
    k = e["lab"] if e else None
    D.ana = PR.ana.get(k, {}) if k else {}
    on = D.ana.get("onset") or {}
    if on:
        D.xB = float(on["xc"])
    elif e:
        D.xB = float(e["on_x"])
    else:
        D.xB = float(GC.foot_x(D.cx.bed49) or 230.0) + 10.0
    return e, k


def zoom_range(D, PR=None, k=None):
    """拡大の窓（幅 70 m）。巻き始めの x の 25 m 先までを基本に、その崩れの原画に最も近いコマの頂が窓の右端から 20 m 以上内側に入るよう延ばす
    （2026-10-15：巻き始めから最も近いコマまでに頂が約 27 m 進み、窓の外に出た）。"""
    x1 = D.xB + 25.0
    b = PR.best.get(k) if (PR is not None and k) else None
    if b:
        xb = b.get("x_c") if b.get("x_c") is not None else b.get("xc")
        if xb is not None:
            x1 = max(x1, float(xb) + 20.0)
    x1 = min(x1, D.cx.x_max)
    return x1 - 70.0, x1


def overlays(im, dr, D, PR, f, k, state, tg, zg):
    """原画の輪郭（巻き始め〜着水 + 0.5 s は細い破線、原画に最も近いコマは太線）と赤い枠。tg：横からの図、zg：拡大の図の置き方。"""
    t = D.t(f)
    on = D.ana.get("onset") or {}
    td = D.ana.get("touchdown") or {}
    b = PR.best.get(k) if k else None
    t_end = (td.get("t") if td.get("t") is not None else (on.get("t", 0.0) + 2.0)) + 0.5
    in_ov = bool(on and on["t"] - 1e-9 <= t <= t_end + 1e-9)
    is_best = bool(b and int(b["frame"]) == int(f))
    near_best = bool(b and abs(t - float(b["t"])) <= 0.5 + 1e-9)
    if in_ov and not is_best:
        row = _shape_row(D.ana, f)
        if row and row.get("eta_c") and row.get("x_c") is not None:
            print_outline(dr, zg, float(row["x_c"]), float(row["eta_c"]), 2, True)
            GV.text_fit(dr, (zg["px0"] + 8, zg["py0"] + 6), "黒の破線＝原画の輪郭（縦の伸びを戻した形）を、このコマの η_c %.2f m と頂の x に合わせた（巻き始め〜着水 + 0.5 s）"
                        % float(row["eta_c"]), zg["px1"] - zg["px0"] - 16, 14, False, fill=(0, 0, 0))
    if b and (is_best or near_best or state == "hold") and b.get("eta_c") and (b.get("x_c") is not None or b.get("xc") is not None):
        xc = float(b.get("x_c") if b.get("x_c") is not None else b["xc"]); ec = float(b["eta_c"])
        full = is_best or state == "hold"
        if full:
            print_outline(dr, zg, xc, ec, 4, False)
        u0, v0 = _XY(tg, xc - 25.0, ec + 3.0); u1, v1 = _XY(tg, xc + 12.0, -5.0)
        dr.rectangle([u0, v0, u1, v1], outline=RED, width=4)
        GV.label_box(dr, (u0 + 2, v0 - 24), "原画に最も近い瞬間 %s" % k, RED, font(14, True))
        dr.rectangle([zg["px0"] - 5, zg["py0"] - 5, zg["px1"] + 5, zg["py0"] + zg["ph"] + 5], outline=RED, width=6)
        lab = "原画に最も近い瞬間（崩れ %s、t %.2f s、score3 %s）" % (k, float(b["t"]), _g(b.get("score3"), "%.2f"))
        if full:
            lab += "：黒の太線＝原画の輪郭（縦の伸びを戻し、η_c %.2f m と頂の x %.1f m に合わせた）" % (ec, xc)
        GV.text_fit(dr, (zg["px0"] + 8, zg["py0"] + 6), lab, zg["px1"] - zg["px0"] - 16, 15, True, fill=RED)


def head_block(dr, D, PR, f, e, k, head, sub, state, opt):
    t = D.t(f)
    GV.text_fit(dr, (40, 12), head, W - 420, 21, True)
    GV.text_fit(dr, (40, 44), sub, W - 80, 14, False, fill=V46.SUB)
    dr.text((W - 330, 8), "t = %6.2f s" % t, fill=V46.TXT, font=font(28, True))
    speed = float(opt.get("speed", 2.0)); slow = float(opt.get("slow", 0.25)); hold = float(opt.get("hold", 1.0))
    state_banner(dr, W - 640, 74, state, speed, slow, hold, k or "—")
    if e:
        b = PR.best.get(k) or {}
        s = "崩れ %s（%s%s）：巻き始め t %.2f s・x %.1f m" % (k, "補いの読み・" if e.get("sup") else "", ("判定する t ≥ %g s" % GC.T_JUDGE) if e.get("judged")
                                                    else "判定しない：入口の立ち上がりの間", e["on_t"], e["on_x"])
        if b.get("score3") is not None:
            s += "・原画に最も近い t %.2f s（score3 %.2f）" % (b["t"], b["score3"])
        GV.text_fit(dr, (40, 76), s, W - 700, 17, True)


def gauge_panel(im, dr, D, PR, f, box):
    """入口の側の波高計（x 110・160 m、y 0.5 m）の η の時系列：規則的な波の列が来ているか。巻き始め（青）・原画に最も近い瞬間（赤）・今（黒）。"""
    px0, py0, px1, py1 = box
    dr.rectangle([px0, py0, px1, py1], outline=(150, 150, 150), fill=(255, 255, 255))
    GV.text_fit(dr, (px0, py0 - 24), "来る波の列：波高計 η（x 110 m 紺・160 m 水色、y 0.5 m、静かな水面から）と崩れ（青 k・赤＝原画に最も近い）",
                px1 - px0, 15, True)
    t = PR.gt
    ta, tb = float(t[0]), float(t[-1])
    lo, hi = -4.0, 7.0
    X = lambda v: px0 + 40 + (v - ta) / max(tb - ta, 1e-9) * (px1 - px0 - 50)
    Y = lambda v: py1 - 18 - (v - lo) / (hi - lo) * (py1 - py0 - 28)
    for zv in (-2, 0, 2, 4, 6):
        dr.line([(px0 + 40, Y(zv)), (px1 - 10, Y(zv))], fill=(225, 225, 225) if zv else (150, 150, 150))
        dr.text((px0 + 4, Y(zv) - 8), "%+d m" % zv, fill=V46.SUB, font=font(11))
    for tv in range(0, int(tb) + 1, 12):
        dr.line([(X(tv), py1 - 18), (X(tv), py1 - 12)], fill=V46.SUB)
        dr.text((X(tv) - 8, py1 - 14), "%d s" % tv, fill=V46.SUB, font=font(11))
    for xg, col in ((110.0, (30, 60, 130)), (160.0, (90, 170, 220))):
        if xg in PR.g:
            e = PR.g[xg] - D.off
            pts = [(X(a), Y(min(max(b, lo), hi))) for a, b in zip(t[::2], e[::2]) if np.isfinite(b)]
            if len(pts) > 1:
                dr.line(pts, fill=col, width=2)
    for ev in PR.ev:
        u = X(ev["on_t"])
        dr.line([(u, py0 + 4), (u, py1 - 18)], fill=(30, 110, 200), width=1)
        dr.text((u + 2, py0 + 4), ev["lab"], fill=(30, 110, 200) if not ev.get("sup") else (120, 60, 160), font=font(12, True))
    for k, b in PR.best.items():
        u = X(float(b["t"]))
        dr.line([(u, py0 + 18), (u, py1 - 18)], fill=RED, width=2)
    u = X(D.t(f))
    dr.line([(u, py0), (u, py1)], fill=(0, 0, 0), width=2)


def table_panel(dr, PR, k_now, box):
    px0, py0, px1, py1 = box
    GV.text_fit(dr, (px0, py0 - 24), "崩れごとの量（真ん中の断面、AI の読み。原画：弦 64.3°・唇 0.35・覆い 0.186）", px1 - px0, 15, True)
    cols = [("k", 34), ("巻き始め t", 88), ("x m", 66), ("Hc m", 66), ("弦 °", 64), ("唇", 56), ("覆い", 64), ("score3", 70), ("最も近い t", 90)]
    x = px0; y = py0
    for nm, w in cols:
        dr.text((x, y), nm, fill=V46.SUB, font=font(13, True)); x += w
    y += 20
    for ev in PR.ev:
        k = ev["lab"]
        r = PR.rows.get(k) or {}
        b = PR.best.get(k) or {}
        ru = b.get("ruler") or {}
        vals = [k, "%.2f" % ev["on_t"], "%.1f" % ev["on_x"], _g(r.get("Hc"), "%.2f"), _g(ru.get("chord"), "%.1f"), _g(ru.get("lip"), "%.2f"),
                _g(ru.get("hood"), "%.3f"), _g(b.get("score3"), "%.2f"), _g(b.get("t"), "%.2f")]
        col = RED if k == k_now else ((120, 60, 160) if ev.get("sup") else (V46.TXT if ev.get("judged") else (150, 150, 150)))
        x = px0
        for (nm, w), v in zip(cols, vals):
            dr.text((x, y), v, fill=col, font=font(13, k == k_now)); x += w
        y += 18
        if y > py1 - 18:
            break
    dr.text((px0, py1 - 16), "灰＝判定しない（t < %g s）。紫 s＝補いの読み（凍らせた選びの外）。赤＝今の崩れ。弦・唇・覆い＝原画に最も近いコマの値" % GC.T_JUDGE,
            fill=V46.SUB, font=font(12))


def render_strip(D, PR, f, head, sub, state, opt):
    cx = D.cx
    t = D.t(f)
    e, k = set_breaker(D, PR, t)
    im = Image.new("RGB", (W, H), V46.BG); dr = ImageDraw.Draw(im)
    head_block(dr, D, PR, f, e, k, head, sub, state, opt)
    tg = sec_geom(60, 132, W - 60, cx.x_min, cx.x_max, -cx.h0, 14.0)
    V48.section48(im, dr, D, f, (tg["px0"], tg["py0"], tg["px1"]), tg["x0"], tg["x1"], tg["z0"], tg["z1"],
                  "横から（y = 0 の断面、x %.0f〜%.0f m）。%s" % (tg["x0"], tg["x1"], bed_title(D)))
    xz0, xz1 = zoom_range(D, PR, k)
    yz = tg["py0"] + tg["ph"] + 62
    zg = sec_geom(60, yz, 1100, xz0, xz1, max(-cx.h0, -8.0), 15.0)
    V48.section48(im, dr, D, f, (zg["px0"], zg["py0"], zg["px1"]), zg["x0"], zg["x1"], zg["z0"], zg["z1"],
                  "崩れる頂の拡大（x %.0f〜%.0f m、縦横同じ縮尺、10 m の目盛り）" % (xz0, xz1), tick=10.0)
    u0, _ = _XY(tg, xz0, 0.0); u1, _ = _XY(tg, xz1, 0.0)
    dr.rectangle([u0, tg["py0"] + 1, u1, tg["py0"] + tg["ph"] - 1], outline=(120, 120, 120), width=1)
    yb = zg["py0"] + zg["ph"]
    table_panel(dr, PR, k, (1150, yz, W - 40, yz + int(0.56 * (yb - yz))))
    gauge_panel(im, dr, D, PR, f, (1150, yz + int(0.56 * (yb - yz)) + 34, W - 40, yb))
    overlays(im, dr, D, PR, f, k, state, tg, zg)
    time_strip(dr, D, PR, f, yb + 70)
    return im


def time_strip(dr, D, PR, f, y):
    """時刻の帯（g47_video.timebar）：崩れの巻き始め（青 k）と原画に最も近い瞬間（赤）。"""
    marks = [(float(e["on_t"]), e["lab"], (30, 110, 200) if not e.get("sup") else (120, 60, 160)) for e in PR.ev]
    marks += [(float(b["t"]), "", RED) for b in PR.best.values()]
    ta = D.t(D.frames[0]); tb = D.t(D.frames[-1])
    dr.text((40, y - 30), "時刻の帯：青＝崩れ k の巻き始め、赤＝原画に最も近い瞬間（そこで 0.25 倍のスローと 1 s の止め）", fill=V46.TXT, font=font(15, True))
    GV.timebar(dr, 40, W - 40, y, ta, tb, D.t(f), marks, None, head="t ")


def render_3d(D, PR, f, head, sub, state, opt):
    t = D.t(f)
    e, k = set_breaker(D, PR, t)
    im = V48.render48(D, f, head, sub)
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, W, 72], fill=V46.BG)
    head_block(dr, D, PR, f, e, k, head, sub, state, opt)
    cx = D.cx
    tg = sec_geom(60, 110, W - 60, cx.x_min, cx.x_max, -cx.h0, 16.0)
    xz0, xz1 = zoom_range(D, PR, k)                  # 2026-10-15：崩れごとの窓（最も近いコマの頂を入れる）。前は V46.zoom_window（崩れを見ない）
    zg = sec_geom(980, 110 + tg["ph"] + 64, W - 60, xz0, xz1, max(-cx.h0, -8.0), 16.0)
    overlays(im, dr, D, PR, f, k, state, tg, zg)
    return im


def render49(D, PR, f, head, sub, state="real", opt=None):
    opt = opt or {}
    if float((D.cfg.get("parms") or {}).get("W", 85.0)) <= 12.0:
        return render_strip(D, PR, f, head, sub, state, opt)
    return render_3d(D, PR, f, head, sub, state, opt)


def schedule(D, PR, frames, opt):
    speed = float(opt.get("speed", 2.0)); slow = float(opt.get("slow", 0.25)); hold = float(opt.get("hold", 1.0))
    bf = PR.best_frames()
    slow_w = [(float(b["t"]) - 0.75, float(b["t"]) + 0.5) for b in PR.best.values()]
    out, acc, emitted = [], 0.0, 0
    for f in frames:
        t = D.t(f)
        sl = any(a - 1e-9 <= t <= c + 1e-9 for a, c in slow_w)
        sp = slow if sl else speed
        acc += 1.0 / sp
        n = int(math.floor(acc + 1e-9)) - emitted
        emitted += n
        if n > 0:
            out.append((f, n, "slow" if sl else "real"))
        if f in bf and hold > 0:
            out.append((f, int(round(hold * FPS)), "hold"))
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    rd = os.path.abspath(sys.argv[1]).replace("\\", "/")
    opt = A46.parse_opt(sys.argv[2:])
    if str(opt.get("legacy", "0")) != "1":          # 2026-10-15：既定は g49_video2（比べの動画と全部の動画）
        import g49_video2 as V2
        o2 = {k: v for k, v in opt.items() if k in ("k", "still", "fast", "slow", "hold", "ss", "speed")}
        S = V2.Shared(rd)
        if "still" in o2:
            V2.make_compare(rd, o2, S=S)
            return
        V2.make_compare(rd, o2, S=S)
        V2.make_whole(rd, {k: v for k, v in o2.items() if k in ("speed",)}, S=S)
        return
    t_start = time.time()
    D = V46.Data(rd, opt)
    T = float((D.cfg.get("sf") or {}).get("T", GC.T_WAVE))
    PR = Periodic(rd, T, use_sup=(str(opt.get("sup", "1")) != "0"))
    head, sub = heads49(D, opt)
    out = GC.guard_out49(opt.get("out") or os.path.join(rd, "video"))
    bfp = os.path.join(rd, "pana", "best_frames.json")
    ov = json.load(open(bfp, encoding="utf8")).get("overall_best") if os.path.exists(bfp) else None
    if "still" in opt:
        f = int(ov["frame"]) if (opt["still"] == "best" and ov) else D.frame_at(float(opt["still"]))
        p = os.path.join(out, "%s_periodic_f%05d.png" % (D.name, f)).replace("\\", "/")
        render49(D, PR, f, head, sub, "hold" if f in PR.best_frames() else "real", opt).save(p)
        print(p); return
    t0 = float(opt.get("t0", -1e9)); t1 = float(opt.get("t1", 1e9))
    frs = [f for f in D.frames if t0 - 1e-9 <= D.t(f) <= t1 + 1e-9]
    sch = schedule(D, PR, frs, opt)
    path = os.path.join(out, "%s_periodic.mp4" % D.name).replace("\\", "/")
    wr = GV.Writer(path)
    cache = {}
    nr = 0
    for f, n, st in sch:
        key = (f, st == "hold")
        if key not in cache:
            cache.clear()
            cache[key] = render49(D, PR, f, head, sub, st, opt); nr += 1
        wr.put(cache[key], n)
    wr.close()
    pr = GV.probe(path)
    best_png = None
    if ov:
        best_png = os.path.join(out, "%s_periodic_best.png" % D.name).replace("\\", "/")
        render49(D, PR, int(ov["frame"]), head, sub, "hold", opt).save(best_png)
    res = dict(run_dir=rd, mp4=path, best_png=best_png, frames_rendered=nr, frames_written=wr.n, probe=pr, still_offset=D.off,
               speed=float(opt.get("speed", 2.0)), slow=float(opt.get("slow", 0.25)), hold_s=float(opt.get("hold", 1.0)),
               best_frames={str(k): dict(frame=b["frame"], t=b["t"], score3=b.get("score3")) for k, b in PR.best.items()},
               tool="Tools/GWWaveGen/flip49/g49_video.py（g48_video.py を読み替え）", elapsed_s=round(time.time() - t_start, 1),
               note_ja="赤い枠＝pana/best_frames.json の原画に最も近いコマ（凍らせた決まり、score3 は AI の読み）。原画らしさは利用者が決める")
    json.dump(A46._clean(res), open(os.path.join(out, "%s_periodic.json" % D.name), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(A46._clean(res), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
