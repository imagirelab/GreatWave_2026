"""numpy による正確で再現可能なラスタ化と2値マスクの補助処理。bpy は使わない。

ラスタ化
--------
`rasterize_triangles` は連続的な画素座標で与えられた2D三角形の和集合を塗る。
gw.frame / gw.draw と同じく左上が原点、右が X 正、下が Y 正で、
画素 (i, j) の中心は (i + 0.5, j + 0.5)。

三角形の内部または境界に画素の中心がある場合、その画素を塗る。
共有辺に隙間を作らないよう、次の走査線方式を配列で一括計算する。

  * 各三角形について、中心線 y=j+0.5 が横切る画素行ごとに区間を1つ作る。
  * 区間 [xl, xr] は中心線と水平でない辺の交点の最小値・最大値。
    交点は常に Y が小さい側の端点から計算する。同じ辺を共有する三角形は
    頂点順に関係なくビット単位で同じ X 値を得るため、丸め誤差の隙間が生じない。
  * 区間を (h, w+1) の差分画像に蓄積し、累積和1回でマスクにする。

計算量は区間の数、すなわち三角形の画素単位の高さの合計に比例し、
外接矩形の面積には依存しない。細い三角形も大きな三角形も扱いやすい。
メモリを抑えるため三角形を分割して処理する。投影面積が0の三角形は
画素中心を覆わないため通常は省く。thin='line' の場合は、これらと
`thin_px` より細い三角形の最長辺を1画素の線として描く。真正面から側面を見た
薄い面も可視化できるが、輪郭が最大約0.5 px 広がるため既定では無効。

マスクの補助処理
----------------
ランレングスに基づく連結成分の番号付け、最大成分の抽出、穴埋めと穴の報告を行う。
前景には8近傍連結、背景には4近傍連結を使用する。
"""
import numpy as np

__all__ = [
    "rasterize_triangles", "rasterize_exact", "EdgeData", "fill_below", "Components", "label_components",
    "largest_component", "fill_holes", "hole_report", "brute_force_mask",
]


# ====================================================================== ラスタ化
def _as_tri_px(tri_px):
    t = np.asarray(tri_px, dtype=np.float64)
    if t.ndim != 3 or t.shape[1:] != (3, 2):
        raise ValueError("tri_px の形は (N, 3, 2) が必要です。実際: %r" % (t.shape,))
    return t


def rasterize_triangles(tri_px, width, height, thin="skip", thin_px=1.0, eps=1e-9,
                        max_spans=2_000_000, out=None, return_info=False, _edge_store=None):
    """三角形の和集合を bool マスク (高さ, 幅) にする。

    tri_px: (N, 3, 2) の浮動小数配列。連続画素座標で右が X 正、下が Y 正。
    thin: 'skip'（既定値）では画素中心に対する正確な被覆のみを使う。
          'line' では最長辺に対する高さが thin_px 未満の三角形も、
          その最長辺に沿う1画素の線として描く。面積0や側面向きの三角形も含む。
    eps: 画素中心が境界上にあるか判定するための px 単位の許容差。
    out: 結果との論理和を取る既存の bool マスク (高さ, 幅)。省略可能。
    有限でない三角形は省き、info['n_nonfinite'] に数を記録する。
    _edge_store は内部用。rasterize_exact を参照。
    """
    w, h = int(width), int(height)
    if w <= 0 or h <= 0:
        raise ValueError("幅と高さは正の値にしてください")
    tri = _as_tri_px(tri_px)
    info = {"n_triangles": int(tri.shape[0]), "n_spans": 0, "n_chunks": 0,
            "n_nonfinite": 0, "n_thin_lines": 0, "n_zero_area": 0}
    finite = np.isfinite(tri).all(axis=(1, 2))
    info["n_nonfinite"] = int((~finite).sum())
    if not finite.all():
        tri = tri[finite]

    diff = np.zeros(h * (w + 1), dtype=np.int32)
    if _edge_store is not None:
        _edge_store["hi"] = np.full(h * w, -np.inf, np.float32)
        _edge_store["lo"] = np.full(h * w, np.inf, np.float32)
        _edge_store["sliver"] = []
    if tri.shape[0]:
        x = tri[:, :, 0]
        y = tri[:, :, 1]
        ymin = y.min(axis=1)
        ymax = y.max(axis=1)
        xmin = x.min(axis=1)
        xmax = x.max(axis=1)
        area2 = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
        info["n_zero_area"] = int((area2 == 0).sum())
        # 中心線が三角形を横切る行。j + 0.5 が [ymin, ymax] に入る。
        j0 = np.ceil(ymin - 0.5 - eps)
        j1 = np.floor(ymax - 0.5 + eps)
        j0 = np.clip(j0, 0, h).astype(np.int64)
        j1 = np.clip(j1, -1, h - 1).astype(np.int64)
        cnt = j1 - j0 + 1
        cnt[(cnt < 0) | (xmax < 0.5 - eps) | (xmin > w - 0.5 + eps)] = 0
        keep = np.nonzero(cnt > 0)[0]
        if keep.size:
            cnt_k = cnt[keep]
            csum = np.cumsum(cnt_k)
            total = int(csum[-1])
            info["n_spans"] = total
            # 各処理単位に約 max_spans 個の区間が入るよう境界を決める。
            n_chunks = max(1, int(np.ceil(total / float(max_spans))))
            bounds = np.searchsorted(csum, np.arange(1, n_chunks) * (total / float(n_chunks)), side="left")
            bounds = np.unique(np.concatenate([[0], bounds + 1, [keep.size]]))
            info["n_chunks"] = int(len(bounds) - 1)
            for a, b in zip(bounds[:-1], bounds[1:]):
                _accumulate_spans(diff, x[keep[a:b]], y[keep[a:b]], j0[keep[a:b]], cnt_k[a:b], w, h, eps,
                                  _edge_store)
    mask = np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1, dtype=np.int32) > 0
    del diff
    if _edge_store is not None:
        _edge_store["hi"] = _edge_store["hi"].reshape(h, w)
        _edge_store["lo"] = _edge_store["lo"].reshape(h, w)
        sl = _edge_store["sliver"]
        if sl:
            key = np.concatenate([s[0] for s in sl])
            lo = np.concatenate([s[1] for s in sl])
            hi = np.concatenate([s[2] for s in sl])
            order = np.lexsort((lo, key))
            _edge_store["sliver"] = (key[order], lo[order], hi[order])
        else:
            _edge_store["sliver"] = (np.zeros(0, np.int64), np.zeros(0, np.float32), np.zeros(0, np.float32))

    if thin == "line" and tri.shape[0]:
        n_lines = _draw_thin_lines(mask, tri, float(thin_px))
        info["n_thin_lines"] = int(n_lines)
    elif thin not in ("skip", "line"):
        raise ValueError("thin は 'skip' または 'line' にしてください")

    if out is not None:
        if out.shape != mask.shape:
            raise ValueError("out の形は %r ですが、必要な形は %r です" % (out.shape, mask.shape))
        np.logical_or(out, mask, out=out)
        mask = out
    return (mask, info) if return_info else mask


def _accumulate_spans(diff, x, y, j0, cnt, w, h, eps, edge_store=None):
    """三角形 (x, y: (n, 3)) の区間を平坦な差分画像に加える。
    edge_store を指定すると、各（行, 画素）について、その画素を最後に覆う区間の
    最大右端 ('hi')、最初に覆う区間の最小左端 ('lo')、画素中心を覆わない
    細い区間 ('sliver') も記録する。"""
    n = x.shape[0]
    total = int(cnt.sum())
    t = np.repeat(np.arange(n, dtype=np.int64), cnt)
    first = np.cumsum(cnt) - cnt
    rows = j0[t] + (np.arange(total, dtype=np.int64) - first[t])
    yc = rows.astype(np.float64) + 0.5
    xl = np.full(total, np.inf)
    xr = np.full(total, -np.inf)
    for ia, ib in ((0, 1), (1, 2), (2, 0)):
        xa, ya, xb, yb = x[:, ia], y[:, ia], x[:, ib], y[:, ib]
        swap = ya > yb                      # Y の小さい端点を先に置く標準順。
        xa, xb = np.where(swap, xb, xa), np.where(swap, xa, xb)
        ya, yb = np.where(swap, yb, ya), np.where(swap, ya, yb)
        dy = yb - ya
        inv = np.zeros_like(dy)
        np.divide(1.0, dy, out=inv, where=dy > 0)
        ya_t = ya[t]
        valid = (dy[t] > 0) & (yc >= ya_t - eps) & (yc <= yb[t] + eps)
        tt = np.clip((yc - ya_t) * inv[t], 0.0, 1.0)
        xa_t = xa[t]
        xe = xa_t + tt * (xb[t] - xa_t)
        xl = np.where(valid & (xe < xl), xe, xl)
        xr = np.where(valid & (xe > xr), xe, xr)
    fin = np.isfinite(xl) & np.isfinite(xr)
    # 画素中心 i + 0.5 が [xl, xr] に入る。
    i0r = np.ceil(np.where(fin, xl, 0.0) - 0.5 - eps)
    i1r = np.floor(np.where(fin, xr, -1.0) - 0.5 + eps)
    i0 = np.clip(i0r, 0, w).astype(np.int64)
    i1 = np.clip(i1r, -1, w - 1).astype(np.int64)
    ok = fin & (i0 <= i1)
    if edge_store is not None:
        # 画素中心を覆わず、画面内で画素 g の右隣の隙間にある区間。
        sl = fin & (i0r > i1r) & (xr > xl) & (i1r >= -1) & (i1r <= w - 1)
        if sl.any():
            g = i1r[sl].astype(np.int64)
            edge_store["sliver"].append((rows[sl] * (w + 2) + (g + 1), xl[sl].astype(np.float32),
                                         xr[sl].astype(np.float32)))
    if not ok.any():
        return
    rows = rows[ok]
    i0, i1 = i0[ok], i1[ok]
    base = rows * (w + 1)
    diff += np.bincount(base + i0, minlength=diff.size).astype(np.int32)
    diff -= np.bincount(base + i1 + 1, minlength=diff.size).astype(np.int32)
    if edge_store is not None:
        b2 = rows * w
        np.maximum.at(edge_store["hi"], b2 + i1, xr[ok].astype(np.float32))
        np.minimum.at(edge_store["lo"], b2 + i0, xl[ok].astype(np.float32))


def _draw_thin_lines(mask, tri, thin_px):
    """細い三角形や退化した三角形の最長辺を、その場で1画素の線として描く。"""
    h, w = mask.shape
    x = tri[:, :, 0]
    y = tri[:, :, 1]
    area2 = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
    e = np.stack([np.hypot(x[:, 1] - x[:, 0], y[:, 1] - y[:, 0]),
                  np.hypot(x[:, 2] - x[:, 1], y[:, 2] - y[:, 1]),
                  np.hypot(x[:, 0] - x[:, 2], y[:, 0] - y[:, 2])], axis=1)
    longest = e.max(axis=1)
    height_over_longest = np.where(longest > 0, area2 / np.where(longest > 0, longest, 1.0), 0.0)
    sel = np.nonzero(height_over_longest < thin_px)[0]
    if sel.size == 0:
        return 0
    k = e[sel].argmax(axis=1)
    ia = k
    ib = (k + 1) % 3
    ax, ay = x[sel, ia], y[sel, ia]
    bx, by = x[sel, ib], y[sel, ib]
    # 画面の完全に外にある線を除く。
    vis = ~((np.maximum(ax, bx) < 0) | (np.minimum(ax, bx) > w) | (np.maximum(ay, by) < 0) | (np.minimum(ay, by) > h))
    ax, ay, bx, by = ax[vis], ay[vis], bx[vis], by[vis]
    if ax.size == 0:
        return 0
    L = np.hypot(bx - ax, by - ay)
    ns = np.maximum(1, np.ceil(L / 0.5).astype(np.int64)) + 1      # 0.5 px 以下の間隔で標本化する。
    chunk = 200_000
    for s in range(0, ax.size, chunk):
        sl = slice(s, s + chunk)
        n_s = ns[sl]
        tot = int(n_s.sum())
        t = np.repeat(np.arange(n_s.size), n_s)
        first = np.cumsum(n_s) - n_s
        f = (np.arange(tot) - first[t]) / np.maximum(n_s[t] - 1, 1)
        px = ax[sl][t] + f * (bx[sl][t] - ax[sl][t])
        py = ay[sl][t] + f * (by[sl][t] - ay[sl][t])
        ix = np.floor(px).astype(np.int64)
        iy = np.floor(py).astype(np.int64)
        ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
        mask[iy[ok], ix[ok]] = True
    return int(ax.size)


def fill_below(mask, y_px):
    """中心が水平線 y=y_px 以下にある画素をその場で塗り、マスクを返す。
    連続画素座標で Y は下向き。水面の下を埋める層に用いる。"""
    h = mask.shape[0]
    j = int(np.clip(np.ceil(float(y_px) - 0.5 - 1e-9), 0, h))
    mask[j:, :] = True
    return mask


class EdgeData:
    """画素中心を通る格子線と輪郭の正確な交点。rasterize_exact の結果。
    内外の画素間にある境界を ±0.5 px ではなく浮動小数精度で求められる。

      x_hi[j, i]: 行 j で画素 i を最後に覆う区間の最大右端 X。
      x_lo[j, i]: 行 j で画素 i を最初に覆う区間の最小左端 X。
      y_hi[j, i]: 列 i で行 j を最後に覆う区間の最大下端 Y。
      y_lo[j, i]: 列 i で行 j を最初に覆う区間の最小上端 Y。
    画素中心を覆わない細い区間は別に保持し、接する場合に連結する。
    """

    def __init__(self, shape, row_store, col_store):
        self.shape = shape
        h, w = shape
        self.x_hi, self.x_lo = row_store["hi"], row_store["lo"]
        self.y_hi, self.y_lo = col_store["hi"].T, col_store["lo"].T
        self._sl_row = row_store["sliver"]           # キー = 行 * (w + 2) + (隙間 + 1)。
        self._sl_col = col_store["sliver"]           # キー = 列 * (h + 2) + (隙間 + 1)。

    @staticmethod
    def _chain(sl, key, start, grow_up, tol=1e-4):
        keys, lo, hi = sl
        a = np.searchsorted(keys, key, side="left")
        b = np.searchsorted(keys, key, side="right")
        if b <= a:
            return start
        reach = float(start)
        if grow_up:                                   # 右端／下端を大きい方向へ延ばす。
            for k in range(a, b):                     # lo 順に並んでいる。
                if lo[k] <= reach + tol and hi[k] > reach:
                    reach = float(hi[k])
        else:                                         # 左端／上端を小さい方向へ延ばす。
            for k in sorted(range(a, b), key=lambda q: -hi[q]):
                if hi[k] >= reach - tol and lo[k] < reach:
                    reach = float(lo[k])
        return reach

    def crossing(self, kind, j, i):
        """内部画素（行 j、列 i）に隣接する正確な境界座標。
        kind は 'right'（画素右側の X）、'left'、'bottom'（下側の Y）、'top'。
        記録がなければ NaN を返す。その画素は三角形に覆われていない。"""
        h, w = self.shape
        if kind == "right":
            v = float(self.x_hi[j, i])
            return self._chain(self._sl_row, j * (w + 2) + (i + 1), v, True) if np.isfinite(v) else np.nan
        if kind == "left":
            v = float(self.x_lo[j, i])
            return self._chain(self._sl_row, j * (w + 2) + i, v, False) if np.isfinite(v) else np.nan
        if kind == "bottom":
            v = float(self.y_hi[j, i])
            return self._chain(self._sl_col, i * (h + 2) + (j + 1), v, True) if np.isfinite(v) else np.nan
        if kind == "top":
            v = float(self.y_lo[j, i])
            return self._chain(self._sl_col, i * (h + 2) + j, v, False) if np.isfinite(v) else np.nan
        raise ValueError(kind)


def rasterize_exact(tri_px, width, height, thin="skip", thin_px=1.0, eps=1e-9, max_spans=2_000_000):
    """rasterize_triangles と EdgeData を行・列の2回の走査で求める。
    (mask, EdgeData, info) を返す。時間は約2倍、メモリは float32 画像4枚分。"""
    tri = _as_tri_px(tri_px)
    row_store, col_store = {}, {}
    mask, info = rasterize_triangles(tri, width, height, thin, thin_px, eps, max_spans,
                                     return_info=True, _edge_store=row_store)
    mask_t, info_t = rasterize_triangles(tri[:, :, ::-1], height, width, "skip", thin_px, eps, max_spans,
                                         return_info=True, _edge_store=col_store)
    info["n_spans_columns"] = info_t["n_spans"]
    if thin == "skip":
        info["row_col_mask_disagree_px"] = int((mask != mask_t.T).sum())
    return mask, EdgeData((int(height), int(width)), row_store, col_store), info


def brute_force_mask(tri_px, width, height, eps=1e-9):
    """参照実装。辺関数で閉じた三角形に画素中心が入るか調べる。
    O(N * w * h) と遅いため、少数の三角形・小画像のテスト専用。"""
    tri = _as_tri_px(tri_px)
    w, h = int(width), int(height)
    xs = (np.arange(w) + 0.5)[None, :]
    ys = (np.arange(h) + 0.5)[:, None]
    mask = np.zeros((h, w), bool)
    for a, b, c in tri:
        if not np.isfinite([a, b, c]).all():
            continue
        area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if area == 0:
            continue
        s = 1.0 if area > 0 else -1.0
        scale = max(abs(area), 1e-300) ** 0.5
        tol = eps * scale
        e0 = s * ((b[0] - a[0]) * (ys - a[1]) - (b[1] - a[1]) * (xs - a[0]))
        e1 = s * ((c[0] - b[0]) * (ys - b[1]) - (c[1] - b[1]) * (xs - b[0]))
        e2 = s * ((a[0] - c[0]) * (ys - c[1]) - (a[1] - c[1]) * (xs - c[0]))
        mask |= (e0 >= -tol) & (e1 >= -tol) & (e2 >= -tol)
    return mask


# ====================================================================== 連結成分
class Components:
    """label_components() の結果。番号付きマスクを行内の連続区間で表す。

    属性は区間ごとの numpy 配列。区間は1行内の [start, end):
      row, start, end, label。label は 0..n-1 で、成分は最初の区間の順に並ぶ。
    成分ごとの長さ n の配列: area、touches_border、bbox (n, 4)。
    bbox は x0, y0, x1, y1 で、終端を含まない。
    """

    def __init__(self, shape, row, start, end, label, n):
        self.shape = (int(shape[0]), int(shape[1]))
        self.row, self.start, self.end, self.label = row, start, end, label
        self.n = int(n)
        h, w = self.shape
        ln = (end - start).astype(np.int64)
        self.area = np.bincount(label, weights=ln, minlength=n).astype(np.int64) if n else np.zeros(0, np.int64)
        tb = (row == 0) | (row == h - 1) | (start == 0) | (end == w)
        self.touches_border = np.bincount(label, weights=tb, minlength=n) > 0 if n else np.zeros(0, bool)
        bbox = np.zeros((n, 4), np.int64)
        if n:
            bbox[:, 0] = w
            bbox[:, 1] = h
            np.minimum.at(bbox[:, 0], label, start)
            np.minimum.at(bbox[:, 1], label, row)
            np.maximum.at(bbox[:, 2], label, end)
            np.maximum.at(bbox[:, 3], label, row + 1)
        self.bbox = bbox

    def mask_of(self, labels):
        """指定した成分番号の和集合を bool マスクとして返す。整数または反復可能な値を受け付ける。"""
        h, w = self.shape
        sel = np.isin(self.label, np.atleast_1d(labels))
        diff = np.zeros(h * (w + 1), np.int32)
        base = self.row[sel] * (w + 1)
        np.add.at(diff, base + self.start[sel], 1)
        np.add.at(diff, base + self.end[sel], -1)
        return np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1, dtype=np.int32) > 0

    def label_image(self):
        """int32 画像を返す。0 はマスク外、k+1 は成分 k。"""
        h, w = self.shape
        diff = np.zeros(h * (w + 1), np.int64)
        base = self.row * (w + 1)
        np.add.at(diff, base + self.start, self.label + 1)
        np.add.at(diff, base + self.end, -(self.label + 1))
        return np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1).astype(np.int32)


def _runs(mask):
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    p = np.zeros((h, w + 2), np.int8)
    p[:, 1:-1] = m
    d = np.diff(p, axis=1)                       # (h, w+1): 区間の開始で +1、終了で -1。
    rs, cs = np.nonzero(d == 1)
    re, ce = np.nonzero(d == -1)
    return rs.astype(np.int64), cs.astype(np.int64), ce.astype(np.int64)


def label_components(mask, connectivity=8):
    """bool マスクの4近傍または8近傍の連結成分を求め、Components を返す。"""
    if connectivity not in (4, 8):
        raise ValueError("connectivity は 4 または 8 にしてください")
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    row, start, end = _runs(m)
    n_runs = row.size
    if n_runs == 0:
        return Components((h, w), row, start, end, np.zeros(0, np.int64), 0)
    K = w + 2
    key_s = row * K + start
    key_e = row * K + end
    prev = (row - 1) * K
    if connectivity == 4:      # 重なりの条件: s_a < e_b かつ e_a > s_b。
        first = np.searchsorted(key_e, prev + start, side="right")
        last = np.searchsorted(key_s, prev + end, side="left") - 1
    else:                      # 8近傍: s_a <= e_b かつ e_a >= s_b。
        first = np.searchsorted(key_e, prev + start, side="left")
        last = np.searchsorted(key_s, prev + end, side="right") - 1
    cnt = np.maximum(last - first + 1, 0)
    cnt[row == 0] = 0
    # 候補が実際に直前の行にあることを確認する。先頭行とキー境界の例外を防ぐ。
    b = np.repeat(np.arange(n_runs, dtype=np.int64), cnt)
    off = np.arange(int(cnt.sum()), dtype=np.int64) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    a = first[b] + off
    good = row[a] == row[b] - 1
    a, b = a[good], b[good]

    parent = np.arange(n_runs, dtype=np.int64)
    while True:
        pa, pb = parent[a], parent[b]
        lo = np.minimum(pa, pb)
        hi = np.maximum(pa, pb)
        ch = lo != hi
        if not ch.any():
            break
        np.minimum.at(parent, hi[ch], lo[ch])
        while True:                              # 親ポインターをまとめてたどる。
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    roots, label = np.unique(parent, return_inverse=True)
    return Components((h, w), row, start, end, label.astype(np.int64), roots.size)


def largest_component(mask, connectivity=8, speck_max_area_px=None, max_listed=20):
    """最大の連結成分の bool マスクと情報の辞書を返す。

    最大成分以外は返すマスクから取り除き、その内訳を必ず報告する:
      n_components, largest_area_px, largest_bbox, second_largest_area_px: 成分数と大きさ。
      removed_area_px: 取り除いた全成分の面積の合計。
      n_removed: 取り除いた成分数（n_components - 1）。
      speck_max_area_px: 下記の分類に使う限界値。None なら分類を指定していない。
      n_removed_specks / removed_specks_area_px: 限界値より小さい成分の数と面積。
      n_removed_islands / removed_islands_area_px: 限界値以上の成分の数と面積。
        限界値がなければ、取り除いた成分をすべて島と数える。
      removed: 最大から `max_listed` 件までの一覧。
        各項目は {'area_px', 'bbox_px' [x0, y0, x1, y1)（終端を含まない）, 'kind' 'speck' | 'island'}。
      removed_list_truncated: 一覧に載らない成分があれば True。
    'speck' は数画素のラスタ化ノイズ。'island' は噴霧、別オブジェクト、
    マスク上で波から分離して見えるメッシュ部分など、実際に離れた形状を表す。
    島の扱いは呼出側が決め、この関数は報告だけを行う。"""
    comp = label_components(mask, connectivity)
    lim = None if speck_max_area_px is None else float(speck_max_area_px)
    if comp.n == 0:
        return np.zeros(comp.shape, bool), {"n_components": 0, "largest_area_px": 0, "removed_area_px": 0,
                                           "second_largest_area_px": 0, "n_removed": 0, "speck_max_area_px": lim,
                                           "n_removed_specks": 0, "removed_specks_area_px": 0, "n_removed_islands": 0,
                                           "removed_islands_area_px": 0, "removed": [], "removed_list_truncated": False}
    k = int(comp.area.argmax())
    areas = np.sort(comp.area)[::-1]
    info = {"n_components": int(comp.n), "largest_area_px": int(areas[0]),
            "second_largest_area_px": int(areas[1]) if comp.n > 1 else 0,
            "removed_area_px": int(areas[1:].sum()), "largest_bbox": [int(v) for v in comp.bbox[k]]}
    others = np.array([i for i in range(comp.n) if i != k], dtype=np.int64)
    a_o = comp.area[others] if others.size else np.zeros(0, np.int64)
    is_speck = (a_o < lim) if lim is not None else np.zeros(a_o.size, bool)
    order = np.argsort(-a_o, kind="stable")
    info.update({"n_removed": int(others.size), "speck_max_area_px": lim,
                 "n_removed_specks": int(is_speck.sum()), "removed_specks_area_px": int(a_o[is_speck].sum()),
                 "n_removed_islands": int((~is_speck).sum()), "removed_islands_area_px": int(a_o[~is_speck].sum()),
                 "removed": [{"area_px": int(a_o[i]), "bbox_px": [int(v) for v in comp.bbox[others[i]]],
                              "kind": "speck" if is_speck[i] else "island"} for i in order[:int(max_listed)]],
                 "removed_list_truncated": bool(others.size > int(max_listed))})
    return comp.mask_of(k), info


def fill_holes(mask, sky="top"):
    """4近傍連結で空に属さない背景領域を穴として埋める。

    sky='top': 上端に接する背景成分を空とする（既定値）。水面下を埋める層を持つ輪郭では、
      掃引されていない領域が左右端に接していても穴として扱える。
    sky='border': いずれかの画面端に接する背景成分を空とする。
    (穴埋め後のマスク, 穴のマスク, info) を返す。info には穴の数・面積・最大穴の面積、
    最大穴の bbox [x0, y0, x1, y1)、最大10件の穴一覧（面積、bbox）を含む。"""
    m = np.asarray(mask, dtype=bool)
    comp = label_components(~m, connectivity=4)
    if comp.n == 0:
        hole_ids = np.zeros(0, np.int64)
    elif sky == "top":
        touches_top = np.bincount(comp.label, weights=(comp.row == 0), minlength=comp.n) > 0
        hole_ids = np.nonzero(~touches_top)[0]
    elif sky == "border":
        hole_ids = np.nonzero(~comp.touches_border)[0]
    else:
        raise ValueError("sky は 'top' または 'border' にしてください")
    info = {"n_holes": int(hole_ids.size), "hole_area_px": 0, "largest_hole_area_px": 0,
            "largest_hole_bbox": None, "holes": []}
    if hole_ids.size == 0:
        return m.copy(), np.zeros_like(m), info
    holes = comp.mask_of(hole_ids)
    areas = comp.area[hole_ids]
    order = np.argsort(areas)[::-1]
    info["hole_area_px"] = int(areas.sum())
    info["largest_hole_area_px"] = int(areas[order[0]])
    info["largest_hole_bbox"] = [int(v) for v in comp.bbox[hole_ids[order[0]]]]
    info["holes"] = [{"area_px": int(areas[i]), "bbox": [int(v) for v in comp.bbox[hole_ids[i]]]}
                     for i in order[:10]]
    return m | holes, holes, info


def hole_report(mask, sky="top"):
    """輪郭マスク内の未充填の穴と、穴埋め後の輪郭面積に対する割合を報告する。
    fill_holes を参照。中身が詰まった輪郭では n_holes == 0。"""
    filled, _holes, info = fill_holes(mask, sky)
    tot = int(filled.sum())
    info["filled_area_px"] = tot
    info["hole_area_frac"] = float(info["hole_area_px"]) / tot if tot else 0.0
    return info
