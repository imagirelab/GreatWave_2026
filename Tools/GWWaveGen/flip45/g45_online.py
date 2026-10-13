# -*- coding: utf-8 -*-
"""FLIP45：計算の途中（hython の中）で使う、numpy だけの読み（g45_run.py が読む）。
2026-10-12 FLIP44 の g44_online.py（変えていない）を写した。中身は変えていない（海底の bed_y は CTRL の h0 から平らな −20 m になる）。
FLIP45 での使い方（計画 plan_ja.md §2・§6.1）：y = 0 の断面（対称の壁に接する格子の層、記録 R2）で、(a) 閉じた空気の穴（格子 1 個以上）か
(b) 唇の先が静かな水面以下（覆いかぶさりが 2 列以上）を見つけたら、その 1 T（7.004 s）後で止める。g45_cfg.py が stop_touchdown に
after_s = tip_wait_s = T、Lc = λ 72.03 m を入れる（読み方 R9。record_ja.md）。wind_guard は FLIP45 では使わない。
以下は g44_online.py の説明のまま：
FLIP44：計算の途中（hython の中）で使う、numpy だけの読み（g44_run.py が読む）。
cavity_frame：断面の水面の場から、閉じた空気の穴（格子 1 個以上）を探す。風の計算を「着水の 0.5 s 後で止める」ための読み（計画 §4.1）。
  FLIP42 の着水の読み（record の計画の読み方 8）の「空気を囲む閉じた線」と同じ形で、等高線の代わりに、上の端と左右の端から空気をたどって
  届かない空気を穴とする（hython には scikit-image がないため）。海底の中は水と同じに扱う。頂（一番高い水）の後ろ 0.25 Lc から前 0.75 Lc の間で、
  頂より下の穴だけ。py -3.10 g44_online.py --test で、FLIP42 R3 の 3700〜3760 コマで、等高線の読みの着水（3745 コマ）と比べる。
lip_tip（2026-10-12 の直し。確かめ check_fixes_ja.md の「唇の先の着水」）：唇の先が静かな水面以下になったか（計画の読み方 8 のもう一つの形）。
  cavity_frame と同じ頂（断面の一番高い水）から前へ、一番上の水の区間を列ごとにつないでたどり、つながりが切れた列を唇の先の列とする。
  その列を含めて 2 列以上、区間の下に空気（格子 1 個以上）とその下の水がある（前へ張り出している）時、先の列の区間の真ん中の高さを唇の先の高さとする。
TouchdownWatch：g44_run.py の止め方（計算の中の着水の読み）。空気の穴を見つけたらその after_s（0.5 s）後で止める（前と同じ）。
  空気の穴より先に唇の先が静かな水面以下になったら（2 コマ続けて）、そのまま空気の穴を待ち、見つからなければ唇の先の tip_wait_s 後で止める。
  唇の先だけで 0.5 s 後に止めないのは、解析（g44_analyze.py）の着水が実際には空気の穴で決まる（唇の先の読みは等高線を静かな水面で
  切るので働かない。record_ja.md §3.2 の E1）ため。解析が着水を読めるコマまで記録を残す。
wind_guard（確かめ G6）：g44_run.py が起動の前に、風の設定（wind_on・wind_mode・case の form）を確かめる。numpy は使わない。
"""
import numpy as np


def bed_y(parms, xs):
    h0 = float(parms["h0"])
    if float(parms.get("reef_on", 0.0)) < 0.5:
        return np.full(np.shape(xs), -h0)
    xr = np.asarray(xs) - float(parms["x_p"])
    n = float(parms["rf_slope_n"]); ht = float(parms["rf_h_top"])
    df = h0 - (xr - float(parms["rf_foot"])) / n
    db = ht + (xr - float(parms["rf_top_end"])) / n
    return -np.minimum(h0, np.maximum(ht, np.maximum(df, db)))


def _components(mask):
    """2 次元の真の所を 4 近傍でつないだ塊（行・列の番号の配列の組）。穴は少ないので Python で幅優先にたどる。"""
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ny, nx = mask.shape
    for j0, i0 in zip(*np.where(mask)):
        if seen[j0, i0]:
            continue
        stack = [(int(j0), int(i0))]; seen[j0, i0] = True; cells = []
        while stack:
            j, i = stack.pop(); cells.append((j, i))
            for jj, ii in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= jj < ny and 0 <= ii < nx and mask[jj, ii] and not seen[jj, ii]:
                    seen[jj, ii] = True; stack.append((jj, ii))
        c = np.array(cells)
        out.append((c[:, 0], c[:, 1]))
    return out


_POS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))      # 四角の角（列の向き x、行の向き y）。順は (j,i)・(j,i+1)・(j+1,i+1)・(j+1,i)


def _shoelace(pts):
    a = np.array(pts)
    return 0.5 * abs(float(np.dot(a[:, 0], np.roll(a[:, 1], -1)) - np.dot(a[:, 1], np.roll(a[:, 0], -1))))


def _ms_area(S, comp_j, comp_i):
    """穴（空気の塊。行 comp_j・列 comp_i の格子）を囲む等高線（値 0、格子の間は辺に沿って直線で補う）の中の面積（格子 1 個 = 1）。
    解析（g44_analyze.frame_crests）の skimage.measure.find_contours（fully_connected='low'：水は斜めにもつながり、空気は辺でだけつながる）
    と同じ線になるように、鞍（向かい合う 2 つの角だけ空気）は角ごとの三角形に分ける。"""
    ny, nx = S.shape
    mine = set(zip(comp_j.tolist(), comp_i.tolist()))
    sq = set()
    for j, i in mine:
        for dj in (-1, 0):
            for di in (-1, 0):
                if 0 <= j + dj < ny - 1 and 0 <= i + di < nx - 1:
                    sq.add((j + dj, i + di))
    tot = 0.0
    for j, i in sq:
        cj = ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))
        v = [float(S[a, b]) for a, b in cj]
        p = [x > 0 for x in v]
        if p in ([True, False, True, False], [False, True, False, True]):
            for k in range(4):
                if p[k] and cj[k] in mine:
                    a1 = v[k] / (v[k] - v[(k + 1) % 4]); a2 = v[k] / (v[k] - v[(k - 1) % 4])
                    tot += 0.5 * a1 * a2
            continue
        if not any(p[k] and cj[k] in mine for k in range(4)):
            continue
        pts = []
        for k in range(4):
            k2 = (k + 1) % 4
            if p[k]:
                pts.append(_POS[k])
            if p[k] != p[k2]:
                t = v[k] / (v[k] - v[k2])
                pts.append((_POS[k][0] + t * (_POS[k2][0] - _POS[k][0]), _POS[k][1] + t * (_POS[k2][1] - _POS[k][1])))
        if len(pts) >= 3:
            tot += _shoelace(pts)
    return tot


def cavity_frame(sl, xs, ys, Lc, vox, off, parms):
    """sl[y, x]：断面の水面の場（水の中で負）。xs・ys：場面の座標。off：静かな水面のずれ。
    2026-10-12（2 回目の確かめの後）：穴を、空気を辺でつないだ塊ごとに見て、その塊を囲む等高線の中の面積（_ms_area）が vox² 以上で、
    塊の中心が頂より下の時だけ見つけたとする。静かな水面の 25 m より下の穴は見ない。どれも解析の着水の読み（g44_analyze.frame_crests の
    閉じた線）と同じ決まり。前は全部の穴の格子の数の和が格子 1 個分以上で見つけたとしたので、FLIP42 R4d で頂の後ろの格子 1 個の泡
    （3736 コマ。等高線の面積は vox² より小さい）を拾い、解析の着水（3748 コマ）より 0.5 s 早く止まる形だった（record_ja.md §3.2 の TD）。"""
    water = sl < 0
    bed = ys[:, None] < (bed_y(parms, xs)[None, :] + 0.5 * vox)
    air = (~water) & (~bed)
    wy = np.where(water.any(1))[0]
    if len(wy) == 0:
        return None
    jt = wy.max()
    ic = int(np.where(water[jt])[0].mean())
    xc = xs[ic]; yc = ys[jt]
    m = (xs >= xc - 0.25 * Lc) & (xs <= xc + 0.75 * Lc)
    Am = air[:, m]
    reach = np.zeros_like(Am)
    reach[-1, :] = Am[-1, :]; reach[:, 0] |= Am[:, 0]; reach[:, -1] |= Am[:, -1]
    for _ in range(4000):
        r2 = reach.copy()
        r2[1:, :] |= reach[:-1, :]; r2[:-1, :] |= reach[1:, :]; r2[:, 1:] |= reach[:, :-1]; r2[:, :-1] |= reach[:, 1:]
        r2 &= Am
        if (r2 == reach).all():
            break
        reach = r2
    hole = Am & ~reach
    hole[(ys - off) < -25.0, :] = False
    cell = (xs[1] - xs[0]) * (ys[1] - ys[0])
    area = float(hole.sum()) * cell
    if not hole.any():
        return dict(xc=float(xc), yc=float(yc - off), area=area, found=False)
    S = sl[:, m].astype(np.float64).copy()
    S[bed[:, m]] = -1.0                       # 海底の中は水（解析と同じ）
    xm = xs[m]
    best = None
    for jj, ii in _components(hole):
        a = _ms_area(S, jj, ii) * cell
        cy = float(ys[jj].mean()); cx = float(xm[ii].mean())
        ok = bool(a >= vox * vox and cy < yc)
        if best is None or (ok, a) > (best[0], best[1]):
            best = (ok, a, cx, cy, len(jj))
    ok, a, cx, cy, n = best
    return dict(xc=float(xc), yc=float(yc - off), area=area, cx=cx, cy=cy - off, hole_area=a, hole_cells=int(n), found=ok)


def _segments(col):
    """1 列の水の区間 [(lo, hi), ...]（行の番号。行は下から上へ）。"""
    w = np.concatenate(([0], col.astype(np.int8), [0]))
    d = np.diff(w)
    return list(zip(np.where(d == 1)[0].tolist(), (np.where(d == -1)[0] - 1).tolist()))


def lip_tip(sl, xs, ys, Lc, vox, off, parms, min_cols=2):
    """唇の先の高さ（静かな水面から）。返り値 dict(found, x_tip, y_tip, over_cols, xc, yc, why)。found は「唇の先が静かな水面以下」。"""
    water = sl < 0
    bed = ys[:, None] < (bed_y(parms, xs)[None, :] + 0.5 * vox)
    wb = water | bed
    wy = np.where(water.any(1))[0]
    if len(wy) == 0:
        return None
    jt = int(wy.max())
    cols = np.where(water[jt])[0]
    icm = int(cols.mean())
    xc = float(xs[icm]); yc = float(ys[jt] - off)
    i = int(cols[np.argmin(np.abs(cols - icm))])           # 頂の行に水がある列（cavity_frame の頂の x にいちばん近い列）
    seg = [s for s in _segments(wb[:, i]) if s[0] <= jt <= s[1]][0]
    x_end = xc + 0.75 * Lc
    over = 0
    ended = True
    while i + 1 < len(xs) and xs[i + 1] <= x_end:
        cand = [s for s in _segments(wb[:, i + 1]) if s[1] >= seg[0] - 1 and s[0] <= seg[1] + 1]
        if not cand:
            ended = False
            break
        seg = max(cand, key=lambda s: s[1])                # つながる区間のうち一番上
        i += 1
        below = [s for s in _segments(wb[:, i]) if s[1] < seg[0] - 1]
        over = over + 1 if below else 0
    if ended:
        return dict(found=False, xc=xc, yc=yc, over_cols=over, why="頂の前 0.75 Lc まで水面がつながっている（張り出しなし）")
    if over < min_cols:
        return dict(found=False, xc=xc, yc=yc, over_cols=over, x_tip=float(xs[i]), why="先の列の張り出しが %d 列（%d 列より少ない）" % (over, min_cols))
    y_tip = 0.5 * (float(ys[seg[0]]) + float(ys[seg[1]])) - off
    return dict(found=bool(y_tip <= 0.0), xc=xc, yc=yc, over_cols=over, x_tip=float(xs[i]), y_tip=float(y_tip),
                lip_lo=float(ys[seg[0]] - off), lip_hi=float(ys[seg[1]] - off))


class TouchdownWatch:
    """計算の中の着水の読みと止め方（g44_run.py と試し x44_fix2_tests.py の両方が使う）。
    st：cfg の stop_touchdown（after_s・t_from・Lc・still_offset_m・tip_wait_s・tip_on）。"""

    def __init__(self, st, vox, parms, fps=24.0):
        self.st = st or {}
        self.vox = float(vox); self.parms = parms; self.fps = float(fps)
        self.after_s = float(self.st.get("after_s", 0.5))
        self.tip_wait_s = float(self.st.get("tip_wait_s", 2.0))
        self.tip_on = bool(self.st.get("tip_on", True))
        self.t_from = float(self.st.get("t_from", 0.0))
        self.Lc = float(self.st.get("Lc", 135.4633))
        self.off = float(self.st.get("still_offset_m", 0.0))
        self.td = None          # 空気の穴（前と同じ読み）
        self.tip = None         # 唇の先が静かな水面以下（2 コマ続いた最初のコマ）
        self._run = 0; self._cand = None

    def restore(self, td=None, tip=None):
        """同じ計算の前の起動（run_c*.json の info）で見つけた物を引き継ぐ。"""
        if td and self.td is None:
            self.td = dict(td, restored=True)
        if tip and self.tip is None:
            self.tip = dict(tip, restored=True)

    def step(self, f, tnow, sl, xs, ys):
        if tnow < self.t_from - 1e-9 or self.td is not None:
            return
        cav = cavity_frame(sl.astype(np.float32), xs, ys, self.Lc, self.vox, self.off, self.parms)
        if cav and cav.get("found"):
            self.td = dict(frame=int(f), t=float(tnow), by="cavity", **cav)
            return
        if not self.tip_on or self.tip is not None:
            return
        lt = lip_tip(sl.astype(np.float32), xs, ys, self.Lc, self.vox, self.off, self.parms)
        if lt and lt.get("found"):
            self._run += 1
            if self._run == 1:
                self._cand = dict(frame=int(f), t=float(tnow), **lt)
            if self._run >= 2:
                self.tip = dict(self._cand, by="tip<=0", confirmed_frame=int(f))
        else:
            self._run = 0; self._cand = None

    def should_stop(self, tnow):
        """止める時は stopped の文（g44_queue.chain_result が touchdown_online で始まる文を「計算の中の着水」と読む）。"""
        if self.td is not None and tnow >= self.td["t"] + self.after_s - 1e-9:
            return "touchdown_online at frame %d (+%.2f s)" % (self.td["frame"], self.after_s)
        if self.td is None and self.tip is not None and tnow >= self.tip["t"] + self.tip_wait_s - 1e-9:
            return "touchdown_online_tip at frame %d (+%.2f s, lip tip at or below still level, no cavity seen)" % (self.tip["frame"], self.tip_wait_s)
        return None


AIRFLOW_TOOL = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44/g44_airflow.py"


def wind_guard(args, parms=None, airflow_exists=None):
    """風の設定の守り（確かめ G6）。問題がなければ None、あれば理由の文。parms を渡すと、場面に入れた後の値（CTRL）で見る。
    - wind_on は 0 か 1。wind_mode は 1（はがれた流れの形 S）・2（N）・3（試しの形）。
    - 風の計算の設定（case の form がある）なのに wind_on 0 は拒む（B35S などの名前で風なしの計算が残るため）。
    - form と wind_mode が合わない物、mode 2（道具 g44_airflow.py がない間）、mode 3 を本番の置き場所（out_root runs）で走らせる物は拒む。"""
    import os
    p = parms if parms is not None else (args.get("parms") or {})
    try:
        on = float(p.get("wind_on", 0.0)); mode = float(p.get("wind_mode", 1.0))
    except (TypeError, ValueError):
        return "wind_on・wind_mode が数でない（%r・%r）" % (p.get("wind_on"), p.get("wind_mode"))
    if on not in (0.0, 1.0):
        return "wind_on は 0 か 1（%r）" % p.get("wind_on")
    form = (args.get("case") or {}).get("form")
    prod = (args.get("out_root", "runs") == "runs")
    if form and on < 0.5:
        return "風の計算の設定（case の form %s）なのに wind_on が 0。風なしの計算が風の計算の名前で残るので走らせない" % form
    if on > 0.5:
        if mode not in (1.0, 2.0, 3.0):
            return "知らない wind_mode %r（1・2・3 のどれか）" % p.get("wind_mode")
        if airflow_exists is None:
            airflow_exists = os.path.exists(AIRFLOW_TOOL)
        if mode == 2.0 and not airflow_exists:
            return "wind_mode 2（はがれのない流れの形 N）は、道具 g44_airflow.py がまだないので走らせない（場面の mode 2 は 0 Pa を書く）"
        if mode == 3.0 and prod:
            return "wind_mode 3（試しの形）は本番の置き場所（runs）では走らせない"
        if form and mode != {"S": 1.0, "N": 2.0}.get(form):
            return "case の form %s と wind_mode %g が合わない" % (form, mode)
    return None


if __name__ == "__main__":
    import sys, json, os, glob
    if "--test" in sys.argv:
        rd = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        off = json.load(open(os.path.join(rd, "ana.json"), encoding="utf8"))["still_level_offset_m"]
        best = {}
        for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
            f0 = int(os.path.basename(p)[5:9]); d = np.load(p)
            for i, f in enumerate(d["frames"]):
                f = int(f)
                if f >= f0 and (f not in best or best[f][0] < f0):
                    best[f] = (f0, p, i)
        meta = json.loads(str(np.load(best[3700][1])["meta"]))
        xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"]); ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"])
        first = None
        for f in range(3700, 3761):
            f0, p, i = best[f]
            sl = np.load(p)["sdf"][i].astype(np.float32)
            r = cavity_frame(sl, xs, ys, 135.46329754326246, 0.5, off, cfg["parms"])
            if r and r["found"] and first is None:
                first = (f, r)
        print("first online cavity frame", first, "(contour reading touchdown: 3745)")
