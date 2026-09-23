"""numpy のみを使う小さなラスタ描画ライブラリ。PIL / cv2 / matplotlib は使わない。

画像は上から下へ並ぶ uint8 配列で、形は (h, w) のグレースケール、
(h, w, 3) の RGB、または (h, w, 4) の RGBA。
描画関数は配列をその場で変更し、同じ画像を返す。

座標は連続的な画素座標（右が X 正、下が Y 正）。画素 (i, j) は
[i, i+1] x [j, j+1] を覆い、中心は (i + 0.5, j + 0.5)。
gw.frame と同じ約束なので、Frame.H_to_px で変換した点をそのまま描ける。
点は (x, y)、点列は (N, 2) の配列とする。

画像に描く文字は ASCII に限る。内蔵の5x7画素フォントを5x9画素の枠に置き、
g j p q y の下部も描く。使用できる文字は32～126、拡大率は整数。
"""
import math

import numpy as np

COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128),
    "lightgray": (210, 210, 210), "darkgray": (70, 70, 70),
    "red": (225, 30, 30), "green": (20, 160, 40), "blue": (30, 80, 230),
    "orange": (245, 140, 0), "yellow": (250, 220, 0), "cyan": (0, 190, 210),
    "magenta": (220, 0, 200), "purple": (130, 60, 190), "brown": (140, 85, 40),
    "lime": (120, 230, 0), "pink": (250, 120, 170), "navy": (10, 30, 110),
}
PALETTE = ["blue", "red", "green", "orange", "purple", "cyan", "magenta", "brown",
           "darkgray", "lime", "pink", "navy"]


# ------------------------------------------------------------------ 基本処理
def canvas(h, w, color="white", channels=3):
    """color で塗りつぶした新しい画像を作る。channels は 1（2 次元のグレースケール）、3、4。"""
    h, w = int(h), int(w)
    if channels == 1:
        img = np.empty((h, w), np.uint8)
        img[...] = int(round(_prep_color(img, color)))
        return img
    img = np.empty((h, w, channels), np.uint8)
    img[...] = np.rint(_prep_color(img, color)).astype(np.uint8)
    return img


def to_rgb(img):
    """グレースケール、RGBA、bool の画像を形状 (h, w, 3) の RGB uint8 に変換する。必要に応じて複写する。"""
    a = np.asarray(img)
    if a.dtype == np.bool_:
        a = a.astype(np.uint8) * 255
    if a.dtype != np.uint8:
        raise TypeError("expected uint8 or bool image, got %s" % a.dtype)
    if a.ndim == 2:
        return np.repeat(a[:, :, None], 3, axis=2)
    if a.shape[2] == 1:
        return np.repeat(a, 3, axis=2)
    if a.shape[2] == 4:
        return np.ascontiguousarray(a[:, :, :3])
    return a


def _prep_color(img, color):
    c = COLORS[color] if isinstance(color, str) else color
    if img.ndim == 2:
        if np.isscalar(c):
            return float(c)
        return float(0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    ch = img.shape[2]
    if np.isscalar(c):
        c = (c, c, c)
    c = list(c)
    if len(c) < ch:
        c = c + [255] * (ch - len(c))
    return np.array(c[:ch], dtype=np.float32)


def _blend_cov(img, x0, y0, cov, color, alpha=1.0):
    """整数座標 (x0, y0) に置いた被覆率配列 cov（浮動小数点数 0～1）を使い、img に color を混合する。"""
    H, W = img.shape[:2]
    h, w = cov.shape
    xa, ya = max(x0, 0), max(y0, 0)
    xb, yb = min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return img
    c = cov[ya - y0:yb - y0, xa - x0:xb - x0]
    idx = np.nonzero(c > 0)
    if idx[0].size == 0:
        return img
    a = (c[idx] * float(alpha)).astype(np.float32)
    region = img[ya:yb, xa:xb]
    col = _prep_color(img, color)
    if img.ndim == 3:
        a = a[:, None]
    old = region[idx].astype(np.float32)
    region[idx] = np.clip(np.rint(old * (1.0 - a) + col * a), 0, 255).astype(np.uint8)
    return img


def _pts(points):
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("points must have shape (N, 2), got %r" % (p.shape,))
    return p


# 線分の描画
def _segment_cov(mask, ox, oy, a, b, r, aa):
    """両端が丸い線分 a-b（半径 r）の被覆率を mask へ最大値で合成する。
    mask[j, i] は画素 (ox + i, oy + j) に対応する。"""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(math.ceil(length / 192.0)))
    H, W = mask.shape
    for k in range(n):
        p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
        q = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
        m = r + 1.5
        x0 = max(int(math.floor(min(p[0], q[0]) - m)) - ox, 0)
        x1 = min(int(math.ceil(max(p[0], q[0]) + m)) - ox, W)
        y0 = max(int(math.floor(min(p[1], q[1]) - m)) - oy, 0)
        y1 = min(int(math.ceil(max(p[1], q[1]) + m)) - oy, H)
        if x0 >= x1 or y0 >= y1:
            continue
        xs = (np.arange(x0, x1, dtype=np.float32) + (ox + 0.5 - p[0]))[None, :]
        ys = (np.arange(y0, y1, dtype=np.float32) + (oy + 0.5 - p[1]))[:, None]
        dx, dy = q[0] - p[0], q[1] - p[1]
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            d = np.hypot(xs, ys)
        else:
            t = np.clip((xs * dx + ys * dy) / l2, 0.0, 1.0)
            d = np.hypot(xs - t * dx, ys - t * dy)
        cov = np.clip(r + 0.5 - d, 0.0, 1.0) if aa else (d <= max(r, 0.5)).astype(np.float32)
        sub = mask[y0:y1, x0:x1]
        np.maximum(sub, cov, out=sub)


def _dash_pieces(p, dash):
    """折れ線 p（N, 2）を、破線パターン (on_len, off_len) の描画部分へ分割する。"""
    on, off = float(dash[0]), float(dash[1])
    seg = np.hypot(*(p[1:] - p[:-1]).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    pieces, start = [], 0.0
    while start < total:
        end = min(start + on, total)
        ss = np.concatenate([[start], s[(s > start) & (s < end)], [end]])
        pieces.append(np.stack([np.interp(ss, s, p[:, 0]), np.interp(ss, s, p[:, 1])], axis=1))
        start += on + off
    return pieces


def polyline(img, points, color="red", width=2.0, closed=False, dash=None, alpha=1.0, aa=True):
    """接合部と端を丸くして折れ線を描く。
    dash=(on_px, off_px) で破線を指定する。NaN を含む行で折れ線を分割する。"""
    p_all = np.asarray(points, dtype=np.float64)
    if p_all.ndim != 2 or p_all.shape[1] != 2:
        raise ValueError("points must have shape (N, 2)")
    good = np.isfinite(p_all).all(axis=1)
    runs, start = [], None
    for i, g in enumerate(good):
        if g and start is None:
            start = i
        if (not g) and start is not None:
            runs.append(p_all[start:i])
            start = None
    if start is not None:
        runs.append(p_all[start:])
    if closed and len(runs) == 1 and len(runs[0]) > 2:
        runs = [np.vstack([runs[0], runs[0][:1]])]
    r = max(float(width), 0.0) / 2.0
    H, W = img.shape[:2]
    for p in runs:
        if len(p) == 0:
            continue
        if len(p) > 2:                       # 0.25 px より近い点を除く。
            keep = [0]
            for i in range(1, len(p) - 1):
                if math.hypot(p[i, 0] - p[keep[-1], 0], p[i, 1] - p[keep[-1], 1]) >= 0.25:
                    keep.append(i)
            keep.append(len(p) - 1)
            p = p[keep]
        m = r + 2.0
        ox = max(int(math.floor(p[:, 0].min() - m)), 0)
        oy = max(int(math.floor(p[:, 1].min() - m)), 0)
        ex = min(int(math.ceil(p[:, 0].max() + m)), W)
        ey = min(int(math.ceil(p[:, 1].max() + m)), H)
        if ox >= ex or oy >= ey:
            continue
        mask = np.zeros((ey - oy, ex - ox), np.float32)
        pieces = [p] if (dash is None or len(p) < 2) else _dash_pieces(p, dash)
        for piece in pieces:
            if len(piece) == 1:
                _segment_cov(mask, ox, oy, piece[0], piece[0], r, aa)
            for i in range(len(piece) - 1):
                _segment_cov(mask, ox, oy, piece[i], piece[i + 1], r, aa)
        _blend_cov(img, ox, oy, mask, color, alpha)
    return img


def line(img, p0, p1, color="red", width=2.0, dash=None, alpha=1.0, aa=True):
    """p0=(x, y) から p1 までの太い直線を描く。"""
    return polyline(img, [p0, p1], color, width, False, dash, alpha, aa)


def hline(img, y, color="red", width=2.0, x0=None, x1=None, dash=None, alpha=1.0):
    W = img.shape[1]
    return line(img, (0 if x0 is None else x0, y), (W if x1 is None else x1, y), color, width, dash, alpha)


def vline(img, x, color="red", width=2.0, y0=None, y1=None, dash=None, alpha=1.0):
    H = img.shape[0]
    return line(img, (x, 0 if y0 is None else y0), (x, H if y1 is None else y1), color, width, dash, alpha)


# マーカーと図形
def circle(img, center, radius, color="red", fill=True, width=2.0, alpha=1.0):
    """塗りつぶした円盤（fill=True）または線幅 width の円環を描く。"""
    cx, cy = float(center[0]), float(center[1])
    rr = float(radius)
    m = rr + width / 2.0 + 2.0
    x0, x1 = int(math.floor(cx - m)), int(math.ceil(cx + m))
    y0, y1 = int(math.floor(cy - m)), int(math.ceil(cy + m))
    xs = (np.arange(x0, x1, dtype=np.float32) + 0.5 - cx)[None, :]
    ys = (np.arange(y0, y1, dtype=np.float32) + 0.5 - cy)[:, None]
    d = np.hypot(xs, ys)
    cov = np.clip(rr + 0.5 - d, 0, 1) if fill else np.clip(width / 2.0 + 0.5 - np.abs(d - rr), 0, 1)
    return _blend_cov(img, x0, y0, cov.astype(np.float32), color, alpha)


def cross(img, center, size=10, color="red", width=2.0, diagonal=False, alpha=1.0):
    """十字の + マーカーを描く。diagonal=True なら斜めの x にする。size は腕の半長（px）。"""
    cx, cy = float(center[0]), float(center[1])
    s = float(size)
    if diagonal:
        s *= 0.7071
        line(img, (cx - s, cy - s), (cx + s, cy + s), color, width, None, alpha)
        line(img, (cx - s, cy + s), (cx + s, cy - s), color, width, None, alpha)
    else:
        line(img, (cx - s, cy), (cx + s, cy), color, width, None, alpha)
        line(img, (cx, cy - s), (cx, cy + s), color, width, None, alpha)
    return img


def marker(img, center, kind="o", size=6, color="red", width=2.0, outline=None):
    """kind は o が円盤、O が円環、+ が十字、x が斜め十字、s が正方形、d がひし形。
    outline は任意の下地色。1.5 px 広い下線を描き、背景上での視認性を上げる。"""
    cx, cy = float(center[0]), float(center[1])
    if outline is not None:
        marker(img, center, kind, size + (1.5 if kind in "osd" else 0), outline,
               width + 3.0 if kind in "O+x" else width, None)
    if kind == "o":
        circle(img, (cx, cy), size, color, True)
    elif kind == "O":
        circle(img, (cx, cy), size, color, False, width)
    elif kind == "+":
        cross(img, (cx, cy), size, color, width)
    elif kind == "x":
        cross(img, (cx, cy), size, color, width, diagonal=True)
    elif kind == "s":
        rect(img, cx - size, cy - size, cx + size, cy + size, color, fill=True)
    elif kind == "d":
        fill_polygon(img, [(cx - size, cy), (cx, cy - size), (cx + size, cy), (cx, cy + size)], color)
    else:
        raise ValueError("unknown marker kind %r" % kind)
    return img


def rect(img, x0, y0, x1, y1, color="red", width=2.0, fill=False, alpha=1.0):
    """連続的な画素座標の二つの角から、軸に平行な長方形を作る。
    輪郭は整数の線幅で長方形の内側に描く。"""
    H, W = img.shape[:2]
    xa, xb = sorted((int(round(x0)), int(round(x1))))
    ya, yb = sorted((int(round(y0)), int(round(y1))))
    if fill:
        boxes = [(xa, ya, xb, yb)]
    else:
        t = max(1, int(round(width)))
        boxes = [(xa, ya, xb, ya + t), (xa, yb - t, xb, yb), (xa, ya, xa + t, yb), (xb - t, ya, xb, yb)]
    col = _prep_color(img, color)
    for bx0, by0, bx1, by1 in boxes:
        bx0, bx1 = max(bx0, 0), min(bx1, W)
        by0, by1 = max(by0, 0), min(by1, H)
        if bx0 >= bx1 or by0 >= by1:
            continue
        reg = img[by0:by1, bx0:bx1]
        if alpha >= 1.0:
            reg[...] = np.rint(col).astype(np.uint8)
        else:
            reg[...] = np.clip(np.rint(reg.astype(np.float32) * (1 - alpha) + col * alpha), 0, 255).astype(np.uint8)
    return img


def polygon_mask(shape, points):
    """画素の中心が閉じた多角形の内側にある場合に真となる、形状 (h, w) のマスク。
    偶奇則で判定する。shape には (h, w) または画像を渡せる。"""
    h, w = (shape.shape[:2] if hasattr(shape, "shape") else shape[:2])
    p = _pts(points)
    q = np.roll(p, -1, axis=0)
    x0, y0, x1, y1 = p[:, 0], p[:, 1], q[:, 0], q[:, 1]
    ylo, yhi = np.minimum(y0, y1), np.maximum(y0, y1)
    j0 = np.clip(np.ceil(ylo - 0.5).astype(np.int64), 0, h)       # 中心が ylo 以上になる最初の行。
    j1 = np.clip(np.ceil(yhi - 0.5).astype(np.int64), 0, h)       # 中心が yhi 以上になる最初の行。
    cnt = np.maximum(j1 - j0, 0)
    total = int(cnt.sum())
    diff = np.zeros((h, w + 1), np.int32)
    if total:
        e = np.repeat(np.arange(len(p)), cnt)
        offs = np.arange(total) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        rows = j0[e] + offs
        yc = rows + 0.5
        xc = x0[e] + (yc - y0[e]) * (x1[e] - x0[e]) / (y1[e] - y0[e])
        cols = np.clip(np.ceil(xc - 0.5).astype(np.int64), 0, w)   # 中心が交点以上になる最初の画素。
        np.add.at(diff, (rows, cols), 1)
    return (np.cumsum(diff[:, :w], axis=1) & 1).astype(bool)


def fill_polygon(img, points, color="red", alpha=1.0):
    """閉じた多角形を偶奇則で塗る。アンチエイリアス処理はしない。"""
    return overlay_mask(img, polygon_mask(img, points), color, alpha)


# 重ね描き
def overlay_mask(img, mask, color="red", alpha=0.5):
    """mask が設定された場所へ color をアルファ混合する。mask は形状 (h, w) の bool、0～255 の uint8、または 0～1 の float。"""
    m = np.asarray(mask)
    if m.shape[:2] != img.shape[:2]:
        raise ValueError("mask shape %r != image shape %r" % (m.shape, img.shape[:2]))
    cov = m.astype(np.float32) / 255.0 if m.dtype == np.uint8 else m.astype(np.float32)
    return _blend_cov(img, 0, 0, cov, color, alpha)


def overlay_image(img, top, alpha=0.5, x=0, y=0, mask=None):
    """画像 top を整数オフセット (x, y) で img へアルファ混合する。
    alpha は単一の値。mask は任意の重み配列 (h, w) で、bool または float。"""
    H, W = img.shape[:2]
    t = to_rgb(top) if img.ndim == 3 else np.asarray(top)
    h, w = t.shape[:2]
    xa, ya, xb, yb = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if xa >= xb or ya >= yb:
        return img
    tt = t[ya - y:yb - y, xa - x:xb - x].astype(np.float32)
    a = np.full((yb - ya, xb - xa), float(alpha), np.float32)
    if mask is not None:
        a = a * np.asarray(mask, dtype=np.float32)[ya - y:yb - y, xa - x:xb - x]
    reg = img[ya:yb, xa:xb]
    if img.ndim == 3:
        a = a[:, :, None]
        tt = tt[:, :, :img.shape[2]] if tt.shape[2] >= img.shape[2] else np.concatenate(
            [tt, np.full(tt.shape[:2] + (img.shape[2] - tt.shape[2],), 255, np.float32)], axis=2)
    reg[...] = np.clip(np.rint(reg.astype(np.float32) * (1 - a) + tt * a), 0, 255).astype(np.uint8)
    return img


def mask_outline(mask, thickness=1):
    """真偽値マスクの内側の境界画素を返す。外側へ 4 近傍で接する画素を境界とする。"""
    m = np.asarray(mask, dtype=bool)
    out = np.zeros_like(m)
    cur = m
    for _ in range(max(1, int(thickness))):
        p = np.pad(cur, 1, mode="constant", constant_values=False)
        er = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        out |= cur & ~er
        cur = er
    return out


# 切り出しとサイズ変更
def crop(img, x0, y0, x1, y1, return_origin=False):
    """領域 [x0, x1) × [y0, y1) の複写を返す。座標を整数へ丸め、画像内へ制限する。
    return_origin=True なら、実際に使った整数原点を含む (crop, (ox, oy)) を返す。"""
    H, W = img.shape[:2]
    xa, xb = sorted((int(round(x0)), int(round(x1))))
    ya, yb = sorted((int(round(y0)), int(round(y1))))
    xa, xb = max(xa, 0), min(xb, W)
    ya, yb = max(ya, 0), min(yb, H)
    if xa >= xb or ya >= yb:
        raise ValueError("crop box is outside the image")
    out = img[ya:yb, xa:xb].copy()
    return (out, (xa, ya)) if return_origin else out


def _area_resample_axis(a, new_n, axis):
    """一つの軸を面積平均で正確に再標本化する（ボックスフィルター）。入力と出力は float32。"""
    n = a.shape[axis]
    if new_n == n:
        return a
    a = np.moveaxis(a, axis, 0)
    csum = np.concatenate([np.zeros((1,) + a.shape[1:], np.float64), np.cumsum(a, axis=0, dtype=np.float64)], axis=0)
    edges = np.arange(new_n + 1, dtype=np.float64) * (n / float(new_n))
    i = np.minimum(np.floor(edges).astype(np.int64), n - 1)
    frac = (edges - i).reshape((-1,) + (1,) * (a.ndim - 1))
    integ = csum[i] + frac * a[i]                     # 区分的に一定な信号の積分。
    out = (integ[1:] - integ[:-1]) * (new_n / float(n))
    return np.moveaxis(out.astype(np.float32), 0, axis)


def _bilinear_axis(a, new_n, axis):
    n = a.shape[axis]
    if new_n == n:
        return a
    a = np.moveaxis(a, axis, 0)
    pos = (np.arange(new_n, dtype=np.float64) + 0.5) * (n / float(new_n)) - 0.5
    pos = np.clip(pos, 0, n - 1)
    i0 = np.floor(pos).astype(np.int64)
    i1 = np.minimum(i0 + 1, n - 1)
    f = (pos - i0).astype(np.float32).reshape((-1,) + (1,) * (a.ndim - 1))
    out = a[i0] * (1 - f) + a[i1] * f
    return np.moveaxis(out, 0, axis)


def resize(img, new_w=None, new_h=None, scale=None, method="auto"):
    """(new_w, new_h) または scale で画像の大きさを変える。幅か高さの片方を None にすると縦横比を保つ。
    method は auto（縮小時はボックス、拡大時はバイリニア）、box（正確な面積平均）、nearest、bilinear。"""
    H, W = img.shape[:2]
    if scale is not None:
        new_w, new_h = int(round(W * scale)), int(round(H * scale))
    elif new_w is None:
        new_w = int(round(W * new_h / float(H)))
    elif new_h is None:
        new_h = int(round(H * new_w / float(W)))
    new_w, new_h = max(1, int(new_w)), max(1, int(new_h))
    if (new_w, new_h) == (W, H):
        return img.copy()
    if method == "nearest":
        yi = np.minimum(((np.arange(new_h) + 0.5) * H / new_h).astype(np.int64), H - 1)
        xi = np.minimum(((np.arange(new_w) + 0.5) * W / new_w).astype(np.int64), W - 1)
        return img[yi][:, xi].copy()
    was_bool = img.dtype == np.bool_
    a = img.astype(np.float32)
    for axis, n_new, n_old in ((0, new_h, H), (1, new_w, W)):
        m = method
        if m == "auto":
            m = "box" if n_new < n_old else "bilinear"
        if m == "box":
            a = _area_resample_axis(a, n_new, axis)
        elif m == "bilinear":
            a = _bilinear_axis(a, n_new, axis)
        else:
            raise ValueError("unknown resize method %r" % method)
    if was_bool:
        return a >= 0.5
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)


def fit_width(img, max_w=1600, method="auto"):
    """幅が max_w 以下になるまで縮小する。拡大はしない。"""
    return img.copy() if img.shape[1] <= max_w else resize(img, new_w=max_w, method=method)


class View:
    """細部を判定するため、座標の対応関係を保持した拡大切り出し画像を作る。

        v = View(painting, cx - 300, cy - 225, cx + 300, cy + 225, scale=2)
        draw.polyline(v.img, v.to_view(pts_px), 'red', 2)   # 元画像での画素座標
        imgio.save_png(path, v.img)
    """

    def __init__(self, img, x0, y0, x1, y1, scale=2.0, method="auto"):
        sub, (self.ox, self.oy) = crop(img, x0, y0, x1, y1, return_origin=True)
        self.scale = float(scale)
        sub = to_rgb(sub) if sub.ndim == 2 else sub
        self.img = resize(sub, scale=self.scale, method=method) if self.scale != 1.0 else sub
        # 出力サイズの丸めを反映した、軸ごとの実際の倍率。
        self.sx = self.img.shape[1] / float(sub.shape[1])
        self.sy = self.img.shape[0] / float(sub.shape[0])

    def to_view(self, points):
        p = np.asarray(points, dtype=np.float64)
        single = p.ndim == 1
        p = np.atleast_2d(p)
        out = np.stack([(p[:, 0] - self.ox) * self.sx, (p[:, 1] - self.oy) * self.sy], axis=1)
        return out[0] if single else out

    def to_image(self, points):
        p = np.asarray(points, dtype=np.float64)
        single = p.ndim == 1
        p = np.atleast_2d(p)
        out = np.stack([p[:, 0] / self.sx + self.ox, p[:, 1] / self.sy + self.oy], axis=1)
        return out[0] if single else out

    def length(self, d_px):
        return d_px * self.sx


# 画像の配置
def _match_channels(imgs):
    return [to_rgb(i) for i in imgs]


def pad(img, top=0, right=0, bottom=0, left=0, color="white"):
    H, W = img.shape[:2]
    out = canvas(H + top + bottom, W + left + right, color, 1 if img.ndim == 2 else img.shape[2])
    out[top:top + H, left:left + W] = img
    return out


def hstack(imgs, gap=8, bg="white", align="top"):
    """画像を横に並べる。align は top、center、bottom。"""
    imgs = _match_channels(imgs)
    H = max(i.shape[0] for i in imgs)
    W = sum(i.shape[1] for i in imgs) + gap * (len(imgs) - 1)
    out = canvas(H, W, bg)
    x = 0
    for i in imgs:
        y = 0 if align == "top" else (H - i.shape[0]) // (2 if align == "center" else 1)
        out[y:y + i.shape[0], x:x + i.shape[1]] = i
        x += i.shape[1] + gap
    return out


def vstack(imgs, gap=8, bg="white", align="left"):
    """画像を縦に並べる。align は left、center、right。"""
    imgs = _match_channels(imgs)
    W = max(i.shape[1] for i in imgs)
    H = sum(i.shape[0] for i in imgs) + gap * (len(imgs) - 1)
    out = canvas(H, W, bg)
    y = 0
    for i in imgs:
        x = 0 if align == "left" else (W - i.shape[1]) // (2 if align == "center" else 1)
        out[y:y + i.shape[0], x:x + i.shape[1]] = i
        y += i.shape[0] + gap
    return out


def grid(imgs, ncols=4, gap=8, bg="white", labels=None, label_scale=2, label_color="black",
         cell_size=None):
    """一覧画像を作る。labels は各セルの上へ置く任意の ASCII 文字列。
    cell_size=(w, h) の場合は、各画像をボックスフィルターで縮小して枠内へ収める。"""
    imgs = _match_channels(imgs)
    if cell_size is not None:
        cw, ch = cell_size
        fitted = []
        for i in imgs:
            s = min(cw / float(i.shape[1]), ch / float(i.shape[0]))
            fitted.append(resize(i, scale=s) if abs(s - 1.0) > 1e-9 else i)
        imgs = fitted
    cells = []
    for k, i in enumerate(imgs):
        if labels is not None and k < len(labels) and labels[k]:
            tw, th = text_size(labels[k], label_scale)
            cap = canvas(th + 4, max(tw + 4, i.shape[1]), bg)
            text(cap, 2, 2, labels[k], label_color, label_scale)
            i = vstack([cap, i], gap=0, bg=bg)
        cells.append(i)
    cw = max(c.shape[1] for c in cells)
    ch = max(c.shape[0] for c in cells)
    nrows = int(math.ceil(len(cells) / float(ncols)))
    ncols = min(ncols, len(cells))
    out = canvas(nrows * ch + gap * (nrows + 1), ncols * cw + gap * (ncols + 1), bg)
    for k, c in enumerate(cells):
        r, q = divmod(k, ncols)
        y, x = gap + r * (ch + gap), gap + q * (cw + gap)
        out[y:y + c.shape[0], x:x + c.shape[1]] = c
    return out


# 文字の描画
# 古典的なパブリックドメインの 5×7 LCD フォント。ASCII 32～126、各文字は 5 列のバイト列で、ビット 0 が最上段。
_FONT_HEX = (
    "0000000000" "00005F0000" "0007000700" "147F147F14" "242A7F2A12" "2313086462" "3649552250" "0005030000"
    "001C224100" "0041221C00" "14083E0814" "08083E0808" "0050300000" "0808080808" "0060600000" "2010080402"
    "3E5149453E" "00427F4000" "4261514946" "2141454B31" "1814127F10" "2745454539" "3C4A494930" "0171090503"
    "3649494936" "064949291E" "0036360000" "0056360000" "0814224100" "1414141414" "0041221408" "0201510906"
    "324979413E" "7E1111117E" "7F49494936" "3E41414122" "7F4141221C" "7F49494941" "7F09090901" "3E4149497A"
    "7F0808087F" "00417F4100" "2040413F01" "7F08142241" "7F40404040" "7F020C027F" "7F0408107F" "3E4141413E"
    "7F09090906" "3E4151215E" "7F09192946" "4649494931" "01017F0101" "3F4040403F" "1F2040201F" "3F4038403F"
    "6314081463" "0708700807" "6151494543" "007F414100" "0204081020" "0041417F00" "0402010204" "4040404040"
    "0001020400" "2054545478" "7F48444438" "3844444420" "384444487F" "3854545418" "087E090102" "0C5252523E"
    "7F08040478" "00447D4000" "2040443D00" "7F10284400" "00417F4000" "7C04180478" "7C08040478" "3844444438"
    "7C14141408" "081414187C" "7C08040408" "4854545420" "043F444020" "3C4040207C" "1C2040201C" "3C4030403C"
    "4428102844" "0C5050503C" "4464544C44" "0008364100" "00007F0000" "0041360800" "0804081008"
)
# 下にはみ出す小文字は 5×9 のセルで描き直す。7～8 行目が下にはみ出す部分となり、
# g を 9 と見間違えず、p と q の小文字としての高さも保てる。
_DESCENDERS = {
    "g": (".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
    "j": ("....#", ".....", "...##", "....#", "....#", "....#", "....#", "#...#", ".###."),
    "p": (".....", ".....", "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."),
    "q": (".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"),
    "y": (".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
}
FONT_W, FONT_H = 5, 9  # 文字セルは本体 7 行と下にはみ出す部分の 2 行。
CHAR_ADVANCE = 6       # 5 px の文字幅と 1 px の間隔に scale を掛ける。
LINE_ADVANCE = 11      # 9 px のセル高と 2 px の行間に scale を掛ける。
_GLYPHS = None


def _glyphs():
    global _GLYPHS
    if _GLYPHS is None:
        raw = bytes.fromhex(_FONT_HEX)
        assert len(raw) == 95 * 5, len(raw)
        g = np.zeros((95, FONT_H, FONT_W), bool)
        for k in range(95):
            for c in range(5):
                col = raw[k * 5 + c]
                for r in range(7):
                    g[k, r, c] = bool((col >> r) & 1)
        for chx, rows in _DESCENDERS.items():
            g[ord(chx) - 32] = np.array([[px == "#" for px in row] for row in rows], bool)
        _GLYPHS = g
    return _GLYPHS


def _text_bitmap(s):
    lines = str(s).split("\n")
    g = _glyphs()
    wmax = max(len(l) for l in lines)
    bm = np.zeros((LINE_ADVANCE * (len(lines) - 1) + FONT_H, max(1, wmax * CHAR_ADVANCE - 1)), bool)
    for li, l in enumerate(lines):
        for ci, chx in enumerate(l):
            o = ord(chx)
            k = o - 32 if 32 <= o <= 126 else ord("?") - 32
            bm[li * LINE_ADVANCE:li * LINE_ADVANCE + FONT_H, ci * CHAR_ADVANCE:ci * CHAR_ADVANCE + FONT_W] = g[k]
    return bm


def text_size(s, scale=2):
    """描画後の文字列の幅と高さを px 単位で返す。改行を含む複数行にも対応する。"""
    bm = _text_bitmap(s)
    return bm.shape[1] * int(scale), bm.shape[0] * int(scale)


def text(img, x, y, s, color="black", scale=2, bg=None, anchor="lt", bg_alpha=1.0, margin=3):
    """ASCII 文字列を描く。(x, y) が基準点。anchor は横方向 l/c/r と縦方向 t/m/b を組み合わせる。
    bg は任意の背景色。ASCII 以外の文字は ? になる。
    文字領域 (x0, y0, x1, y1) を返す。"""
    scale = max(1, int(scale))
    bm = _text_bitmap(s)
    if scale > 1:
        bm = np.repeat(np.repeat(bm, scale, axis=0), scale, axis=1)
    h, w = bm.shape
    x0 = float(x) - {"l": 0.0, "c": w / 2.0, "r": float(w)}[anchor[0]]
    y0 = float(y) - {"t": 0.0, "m": h / 2.0, "b": float(h)}[anchor[1]]
    x0, y0 = int(round(x0)), int(round(y0))
    if bg is not None:
        rect(img, x0 - margin, y0 - margin, x0 + w + margin, y0 + h + margin, bg, fill=True, alpha=bg_alpha)
    _blend_cov(img, x0, y0, bm.astype(np.float32), color, 1.0)
    return (x0, y0, x0 + w, y0 + h)


def label_point(img, center, s, color="red", scale=2, offset=(10, -10), bg="white", bg_alpha=0.8,
                kind="+", size=10, width=2.0, outline="white"):
    """マーカーの隣へ文字ラベルを描く。位置はマーカーの中心からの px 単位のずれで指定する。"""
    marker(img, center, kind, size, color, width, outline)
    ax = "l" if offset[0] >= 0 else "r"
    ay = "t" if offset[1] >= 0 else "b"
    text(img, center[0] + offset[0], center[1] + offset[1], s, color, scale, bg, ax + ay, bg_alpha)
    return img
