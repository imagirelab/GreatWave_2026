"""輪郭線に基づく方法Bの基準輪郭抽出。numpy のみを使う基礎処理。

すべて再現可能な処理で、原画の連続画素座標を使う。左上が原点、右が X 正、
下が Y 正で、画素 (i, j) の中心は (i + 0.5, j + 0.5)。

内容
----
* 特徴画像: 輝度と青み D = B - R。
* flood_fill: 行内の連続区間を一括走査する4近傍の塗りつぶし。
* trace_cracks: 領域を進行方向の左側に置く、順序付きの画素間境界。
* edt_capped: 最大半径で制限する正確なユークリッド距離変換。
* opening: 円盤による形態学的オープニング。波本体側から球を転がす操作。
* bilinear: 1画素未満の位置での補間。
* refine_edge: 局所法線に沿った半値の縁の位置合わせ。
* 弧長の補助計算、弧長方向のガウス平滑化、等間隔の再標本化、接線角。
"""
import math

import numpy as np


# ------------------------------------------------------------------ 特徴画像
def luma(rgb):
    a = rgb.astype(np.float32)
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def blueness(rgb):
    """D=B-R の float32 画像。空は -50～-3、白い泡は約 -22、墨の輪郭は +25～+45、
    濃青の塗りは約 +65。値は原画での測定に基づく。記録を参照。"""
    a = rgb.astype(np.float32)
    return a[:, :, 2] - a[:, :, 0]


def box_blur(a, r):
    """端を複製して (2r+1)^2 の矩形平均を取る。r=0 なら a をそのまま返す。"""
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge").astype(np.float64)
    c = np.cumsum(p, axis=0)
    c = np.concatenate([np.zeros((1, c.shape[1])), c], axis=0)
    v = c[k:] - c[:-k]
    c = np.cumsum(v, axis=1)
    c = np.concatenate([np.zeros((c.shape[0], 1)), c], axis=1)
    h = c[:, k:] - c[:, :-k]
    return (h / float(k * k)).astype(np.float32)


def _running_extreme(a, k, axis, fn):
    """`axis` 方向の奇数 k 点の中央窓で最大値または最小値を取る。端を複製する。"""
    r = k // 2
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    n = a.shape[axis]
    out = None
    for s in range(k):
        sl = [slice(None), slice(None)]
        sl[axis] = slice(s, s + n)
        v = p[tuple(sl)]
        out = v.copy() if out is None else fn(out, v, out=out)
    return out


def grey_dilate(a, k):
    """奇数 k の k x k 正方形によるグレースケール膨張（局所最大）。"""
    return _running_extreme(_running_extreme(a, k, 0, np.maximum), k, 1, np.maximum)


def grey_erode(a, k):
    """奇数 k の k x k 正方形によるグレースケール収縮（局所最小）。"""
    return _running_extreme(_running_extreme(a, k, 0, np.minimum), k, 1, np.minimum)


def black_tophat(a, k):
    """k x k 正方形による closing(a)-a。幅が k px 未満の暗い部分を強調する。"""
    return grey_erode(grey_dilate(a, k), k) - a


# ------------------------------------------------------------------ 塗りつぶし
def _run_ids(mask):
    """bool マスク (h, w) の行内の連続区間へ番号を付ける。同じ区間の画素は同じ番号。
    (マスク内で有効な int64 の番号画像 (h, w), 区間数) を返す。"""
    h, w = mask.shape
    start = mask.copy()
    start[:, 1:] &= ~mask[:, :-1]
    ids = np.cumsum(start.ravel()).reshape(h, w) - 1
    return ids, int(start.sum())


def flood_fill(mask, seeds, max_iter=10000):
    """整数画素 (x, y) の種点リスト `seeds` から bool の `mask` 内を4近傍で塗る。
    行と列の連続区間への伝播を、変化がなくなるまで交互に一括計算する。
    (到達した bool 配列, 反復回数) を返す。"""
    m = np.ascontiguousarray(mask.astype(bool))
    mt = np.ascontiguousarray(m.T)
    ids_r, n_r = _run_ids(m)
    ids_c, n_c = _run_ids(mt)
    reached = np.zeros_like(m)
    for (x, y) in seeds:
        if not m[y, x]:
            raise ValueError("flood_fill seed (%d, %d) is outside the mask" % (x, y))
        reached[y, x] = True
    count = int(reached.sum())
    it = 0
    while it < max_iter:
        it += 1
        hit = np.bincount(ids_r[m], weights=reached[m], minlength=n_r) > 0
        reached = m & hit[np.clip(ids_r, 0, max(n_r - 1, 0))]
        rt = np.ascontiguousarray(reached.T)
        hit = np.bincount(ids_c[mt], weights=rt[mt], minlength=n_c) > 0
        rt = mt & hit[np.clip(ids_c, 0, max(n_c - 1, 0))]
        reached = np.ascontiguousarray(rt.T)
        new_count = int(reached.sum())
        if new_count == count:
            break
        count = new_count
    return reached, it


def geodesic_dilate(seed, within, steps):
    """`seed` を `within` 内で `steps` 画素分広げる。4近傍と8近傍を交互に使い、
    ユークリッド距離を八角形で近似する。`within` の外へは広がらず、細い墨線を越えない。"""
    cur = seed & within
    for i in range(int(steps)):
        p = np.pad(cur, 1, mode="constant", constant_values=False)
        g = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
        if i % 2 == 1:
            g |= p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
        cur = g & within
    return cur


# ------------------------------------------------------------------ 画素間の境界追跡
_DX = (1, 0, -1, 0)      # 画像座標で 0=東、1=南、2=西、3=北。Y は下向き。
_DY = (0, 1, 0, -1)


#: 頂点 (x, y) から始まる境界の進行方向左側の画素のずれ。方向は0=東、1=南、2=西、3=北。
LEFT_PIXEL = ((0, -1), (0, 0), (-1, 0), (-1, -1))


def crack_left_pixels(path):
    """単位歩幅の画素間経路 (N, 2) について、各歩の左側の画素座標 (N-1, 2) を返す。
    trace_cracks の経路では領域側の画素に相当する。"""
    d = np.diff(path, axis=0)
    direction = np.where(d[:, 0] == 1, 0, np.where(d[:, 1] == 1, 1, np.where(d[:, 0] == -1, 2, 3)))
    off = np.asarray(LEFT_PIXEL, dtype=np.int64)[direction]
    return path[:-1] + off


def trace_cracks_open(region, start_vertex, start_dir, n_vertices):
    """trace_cracks と同様に追跡し、n_vertices 個の頂点で返す。開いた経路で閉鎖判定なし。"""
    return trace_cracks(region, start_vertex, start_dir, max_steps=int(n_vertices), allow_open=True)


def trace_cracks(region, start_vertex, start_dir, max_steps=5_000_000, allow_open=False):
    """bool 配列 `region` (h, w) の画素間境界を、領域を進行方向の左側に見て追跡する。
    領域は4近傍連結とみなし、斜め接触はつながらない。頂点は整数格子点で、
    (x, y) は画素 (x, y) の左上角。start_vertex と start_dir（0=東、1=南、
    2=西、3=北）は有効な境界の開始を示す必要がある。最初の歩の左側の画素は
    領域内、右側の画素は領域外とする。配列外の画素も領域外とみなす。
    閉じた経路の頂点 (N, 2) の整数配列を返し、最初の頂点は末尾に重複させない。"""
    h, w = region.shape
    reg = region

    def inside(px, py):
        return 0 <= px < w and 0 <= py < h and bool(reg[py, px])

    # 方向 d へ進むときの頂点 (x, y) の左前／右前の画素。
    # E: AL = (x, y-1), AR = (x, y);  S: AL = (x, y), AR = (x-1, y)
    # W: AL = (x-1, y), AR = (x-1, y-1);  N: AL = (x-1, y-1), AR = (x, y-1)
    AL = ((0, -1), (0, 0), (-1, 0), (-1, -1))
    AR = ((0, 0), (-1, 0), (-1, -1), (0, -1))
    x, y = int(start_vertex[0]), int(start_vertex[1])
    d = int(start_dir)
    if not (inside(x + AL[d][0], y + AL[d][1]) and not inside(x + AR[d][0], y + AR[d][1])):
        raise ValueError("trace_cracks: invalid start crack")
    out = []
    x0, y0, d0 = x, y, d
    for _ in range(max_steps):
        out.append((x, y))
        x += _DX[d]
        y += _DY[d]
        # 新しい頂点で次の方向を選ぶ。
        al = inside(x + AL[d][0], y + AL[d][1])
        ar = inside(x + AR[d][0], y + AR[d][1])
        if not al:
            d = (d + 3) % 4          # 左へ曲がる。
        elif ar:
            d = (d + 1) % 4          # 右へ曲がる。
        if x == x0 and y == y0 and d == d0:
            break
    else:
        if not allow_open:
            raise RuntimeError("trace_cracks: boundary did not close within max_steps")
    return np.asarray(out, dtype=np.int64)


# ------------------------------------------------------------------ 距離変換とオープニング
def edt_capped(mask, rmax):
    """`mask` の True 画素から最も近い False 画素までの正確なユークリッド距離を求める。
    画素中心間の float32 の値で、rmax を超える場合は rmax+1 を返す。
    False 画素は0。配列外は True とみなし、画面端の影響を受けない。
    (2*rmax+1) 回の一括走査を行う。"""
    m = mask.astype(bool)
    h, w = m.shape
    rmax = int(rmax)
    big = rmax + 1
    # 列方向の上限付き1D距離。
    g = np.full((h, w), big, np.int32)
    run = np.full(w, big, np.int32)
    for yy in range(h):                       # 上から下へ。
        run = np.where(m[yy], np.minimum(run + 1, big), 0)
        g[yy] = run
    run = np.full(w, big, np.int32)
    for yy in range(h - 1, -1, -1):           # 下から上へ。
        run = np.where(m[yy], np.minimum(run + 1, big), 0)
        g[yy] = np.minimum(g[yy], run)
    g2 = g.astype(np.float32) ** 2
    g2[g >= big] = np.float32(1e12)
    best = g2.copy()
    for dx in range(1, rmax + 1):
        add = np.float32(dx * dx)
        best[:, dx:] = np.minimum(best[:, dx:], g2[:, :-dx] + add)
        best[:, :-dx] = np.minimum(best[:, :-dx], g2[:, dx:] + add)
    d = np.sqrt(np.minimum(best, np.float32(big * big)))
    d[d > rmax] = big
    return d.astype(np.float32)


def opening(mask, radius):
    """指定半径の円盤で `mask` を形態学的に開く。正確な EDT に基づき、
    マスク内に収まる同半径の円盤すべての和集合を取る。距離は画素中心間で測る。"""
    r = float(radius)
    rcap = int(math.ceil(r)) + 1
    core = edt_capped(mask, rcap) > r            # 収縮: 円盤が収まる中心。
    back = edt_capped(~core, rcap) <= r          # 中心領域を膨張させる。
    return back & mask


# ------------------------------------------------------------------ サンプリング
def bilinear(a, x, y):
    """配列 a (h, w) を連続画素座標 (x, y) で補間する（画素中心は +0.5）。"""
    h, w = a.shape
    fx = np.clip(np.asarray(x, np.float64) - 0.5, 0, w - 1.000001)
    fy = np.clip(np.asarray(y, np.float64) - 0.5, 0, h - 1.000001)
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    tx = fx - x0
    ty = fy - y0
    v00 = a[y0, x0]
    v01 = a[y0, x0 + 1]
    v10 = a[y0 + 1, x0]
    v11 = a[y0 + 1, x0 + 1]
    return (v00 * (1 - tx) + v01 * tx) * (1 - ty) + (v10 * (1 - tx) + v11 * tx) * ty


# ------------------------------------------------------------------ 折れ線の補助関数
def arclength(p):
    d = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    return np.concatenate([[0.0], np.cumsum(d)])


def resample_uniform(p, spacing, keep_end=True):
    """折れ線 p (N, 2) を等しい弧長間隔で再標本化する。

    始点を保持し、keep_end が真で終点がまだ含まれていなければ終点を追加する。
    再標本化した点 (M, 2) と、入力折れ線に沿った各点の弧長を返す。
    """
    s = arclength(p)
    total = s[-1]
    n = int(math.floor(total / spacing + 1e-9))
    t = np.arange(n + 1) * spacing
    if keep_end and total - t[-1] > 1e-6:
        t = np.concatenate([t, [total]])
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return out, t


def resample_uniform_exact(p, spacing):
    """両端点を正確に保持しながら等間隔で再標本化する。

    区間数を round(length / spacing) とし、実際の間隔は length / n となる。
    """
    s = arclength(p)
    total = s[-1]
    n = max(1, int(round(total / spacing)))
    t = np.linspace(0.0, total, n + 1)
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return out, t


def gaussian_smooth_open(p, sigma, spacing, fix_ends=True):
    """間隔 `spacing` で標本化した開いた折れ線をガウス平滑化する。

    sigma は弧長の画素単位。端部は点対称の反射で処理し、端点と端部の接線を保つ。
    fix_ends が真なら最初と最後の点を元の座標に戻す。
    """
    if sigma <= 0:
        return p.copy()
    sg = sigma / float(spacing)
    r = int(math.ceil(4 * sg))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2)
    k /= k.sum()
    n = len(p)
    r_eff = min(r, n - 1)
    head = 2 * p[0] - p[1:r_eff + 1][::-1]
    tail = 2 * p[-1] - p[-r_eff - 1:-1][::-1]
    ext = np.vstack([head, p, tail])
    if r_eff < r:
        k = k[r - r_eff:r + r_eff + 1]
        k /= k.sum()
    out = np.stack([np.convolve(ext[:, 0], k, mode="valid"),
                    np.convolve(ext[:, 1], k, mode="valid")], axis=1)
    if fix_ends:
        out[0] = p[0]
        out[-1] = p[-1]
    return out


def tangent_angles_deg(p):
    """各線分の方向を度数で返す。0 は右 (+x)、+90 は上（画素座標の y は下向き）。"""
    d = np.diff(p, axis=0)
    return np.degrees(np.arctan2(-d[:, 1], d[:, 0]))


def wrap_deg(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def s8_profile(p, spacing_px):
    """折れ線の S8 方式の滑らかさを評価する。

    `spacing_px` で再標本化し、各弦の接線方向と隣接する弦の方向変化を求める。
    標本点、頂点ごとの符号付き旋回角（度、正は X-Z 平面で左回り）と最大値を辞書で返す。
    """
    q, _ = resample_uniform(p, spacing_px, keep_end=False)
    if len(q) < 3:
        return {"points": q, "turn_deg": np.zeros(0), "max_abs_deg": 0.0, "argmax_px": None}
    ang = tangent_angles_deg(q)
    turn = wrap_deg(np.diff(ang))
    i = int(np.argmax(np.abs(turn)))
    return {"points": q, "turn_deg": turn, "max_abs_deg": float(np.abs(turn).max()),
            "argmax_px": [float(q[i + 1, 0]), float(q[i + 1, 1])]}


def point_polyline_distance(pts, poly):
    """各点 (N, 2) から折れ線 poly (M, 2) の線分までの距離を求める。

    距離、最近接線分の番号、その線分上のパラメータ t を返す。分割してベクトル計算する。
    """
    a = poly[:-1]
    b = poly[1:]
    ab = b - a
    l2 = np.maximum((ab ** 2).sum(axis=1), 1e-12)
    dist = np.empty(len(pts))
    idx = np.empty(len(pts), np.int64)
    tt = np.empty(len(pts))
    chunk = max(1, int(4_000_000 // max(len(a), 1)))
    for i0 in range(0, len(pts), chunk):
        q = pts[i0:i0 + chunk]
        ap = q[:, None, :] - a[None, :, :]
        t = np.clip((ap * ab[None]).sum(axis=2) / l2[None], 0.0, 1.0)
        proj = a[None] + t[:, :, None] * ab[None]
        dd = np.hypot(q[:, None, 0] - proj[:, :, 0], q[:, None, 1] - proj[:, :, 1])
        j = dd.argmin(axis=1)
        r = np.arange(len(q))
        dist[i0:i0 + chunk] = dd[r, j]
        idx[i0:i0 + chunk] = j
        tt[i0:i0 + chunk] = t[r, j]
    return dist, idx, tt


# ------------------------------------------------------------------ 画素未満の精度で輪郭を補正
def local_normals(p, half_window):
    """弦 p[i+hw] - p[i-hw] から順序付き折れ線 (N, 2) の単位法線を求める。

    法線は進行方向の右側を向く。空を左に置いた輪郭追跡では波の内側を向く。
    """
    n = len(p)
    i0 = np.clip(np.arange(n) - half_window, 0, n - 1)
    i1 = np.clip(np.arange(n) + half_window, 0, n - 1)
    t = p[i1] - p[i0]
    ln = np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)
    t = t / ln[:, None]
    # 画像座標（y は下向き）での進行方向 (tx, ty) に対し、右側は (-ty, tx)。
    return np.stack([-t[:, 1], t[:, 0]], axis=1), t


def refine_edge(field, p, normals, search=6.0, step=0.25, outer=(3.0, 7.0), inner_max=7.0,
                level=0.5, min_contrast=12.0):
    """空側で低く、墨線・波側で高いスカラー `field` から、画素未満の輪郭位置を求める。

    各 p[i] から波の内側を向く法線に沿い、[-search - outer[1], +search + inner_max]
    の範囲を標本化する。空側の値は初期推定位置から [-outer[1], -outer[0]] にある
    標本の中央値、波側の値は [0, inner_max] にある標本の最大値とする。
    空側から sky + level * (wave - sky) を最初に超える位置を線形補間で求める。
    contrast < min_contrast、または +-search 内に交点がない点は元の位置を保持し、
    不適合として記録する。補正点 (N, 2)、適合判定 (N,)、法線方向の符号付き移動量
    (N,)（画素単位）、コントラスト (N,) を返す。
    """
    t = np.arange(-(search + outer[1]), search + inner_max + 1e-9, step)
    xs = p[:, 0][:, None] + normals[:, 0][:, None] * t[None, :]
    ys = p[:, 1][:, None] + normals[:, 1][:, None] * t[None, :]
    prof = bilinear(field, xs, ys)                                   # (N, T)
    sel_o = (t >= -outer[1]) & (t <= -outer[0])
    sky = np.median(prof[:, sel_o], axis=1)
    sel_i = (t >= 0.0) & (t <= inner_max)
    wave = prof[:, sel_i].max(axis=1)
    contrast = wave - sky
    thr = sky + level * contrast
    above = prof >= thr[:, None]
    sel_s = (t >= -search) & (t <= search)
    # 探索範囲内で値が初めてしきい値以上となり、直前の標本が下回っている位置。
    cross = above[:, 1:] & ~above[:, :-1] & sel_s[None, 1:]
    has = cross.any(axis=1)
    j = np.argmax(cross, axis=1) + 1
    r = np.arange(len(p))
    v0 = prof[r, j - 1]
    v1 = prof[r, j]
    frac = np.where(np.abs(v1 - v0) > 1e-9, (thr - v0) / np.where(np.abs(v1 - v0) > 1e-9, v1 - v0, 1.0), 0.5)
    shift = t[j - 1] + frac * step
    ok = has & (contrast >= min_contrast)
    shift = np.where(ok, shift, 0.0)
    out = p + normals * shift[:, None]
    return out, ok, shift, contrast
