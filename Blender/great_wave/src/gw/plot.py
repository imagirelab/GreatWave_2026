"""numpy のみを使う最小限の線グラフ。この環境では matplotlib を使わない。

    img = plot.line_plot(
        series=[{"label": "h(t)", "x": t, "y": h, "color": "blue"},
                {"label": "ref",  "x": t2, "y": h2, "color": "red", "dash": (8, 5)}],
        title="h(t)", xlabel="t [s]", ylabel="h [H]",
        vlines=[{"x": 4.0, "label": "t1"}],
        spans=[{"x0": 0, "x1": 4, "label": "A", "color": "green"}],
        ylim=(0, 1.2), size=(1100, 520))
    imgio.save_png(path, img)

画像上の文字は ASCII に限る。返り値は上から下に並ぶ RGB uint8 配列。
"""
import math

import numpy as np

from . import draw


def nice_ticks(lo, hi, n=6):
    """[lo, hi] を覆う1・2・2.5・5刻みの目盛りを求め、(目盛り, 刻み幅) を返す。"""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return np.array([0.0, 1.0]), 1.0
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / max(1, n)
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = m * mag
        if raw <= step:
            break
    first = math.ceil(lo / step - 1e-9) * step
    ticks = np.arange(first, hi + step * 1e-6, step)
    ticks[np.abs(ticks) < step * 1e-9] = 0.0
    return ticks, step


def _fmt(v, step):
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e5 or a < 1e-4:
        return "%.2e" % v
    dec = max(0, int(math.ceil(-math.log10(step) - 1e-9))) if step < 1 else 0
    if abs(step * 10 ** dec - round(step * 10 ** dec)) > 1e-6:
        dec += 1
    return "%.*f" % (dec, v)


def _limits(vals, lim, pad_frac=0.05):
    if lim is not None and lim[0] is not None and lim[1] is not None:
        return float(lim[0]), float(lim[1])
    v = np.concatenate([np.ravel(np.asarray(a, dtype=np.float64)) for a in vals]) if vals else np.array([0.0, 1.0])
    v = v[np.isfinite(v)]
    if v.size == 0:
        lo, hi = 0.0, 1.0
    else:
        lo, hi = float(v.min()), float(v.max())
    if hi - lo < 1e-12:
        d = abs(lo) * 0.05 + 0.5
        lo, hi = lo - d, hi + d
    else:
        d = (hi - lo) * pad_frac
        lo, hi = lo - d, hi + d
    if lim is not None:
        if lim[0] is not None:
            lo = float(lim[0])
        if lim[1] is not None:
            hi = float(lim[1])
    return lo, hi


def line_plot(series, title="", xlabel="", ylabel="", size=(1100, 520), xlim=None, ylim=None,
              vlines=None, hlines=None, spans=None, legend="right", grid=True, font_scale=2,
              bg="white", equal_aspect=False, left_margin=None, legend_width=None, _layout_only=False):
    """線グラフを形状 (size[1], size[0], 3) の RGB uint8 配列として返す。

    series : 辞書 {label, x, y, color?, width?=2, dash?=(on,off), marker?='o'|'+'|'x'|'s', marker_size?=3,
             line?=True} のリスト。y の NaN は線の切れ目を表す。color は draw.COLORS の名前または (r,g,b)。
    vlines : [{x, label?, color?, dash?}]   縦の補助線
    hlines : [{y, label?, color?, dash?}]   横の補助線
    spans  : [{x0, x1, label?, color?, alpha?=0.15}]  背景を塗る x の区間
    xlim / ylim : (lo, hi)。各端に None を指定すると、その端を自動設定。
    legend : 'right'（枠外、既定値）、'inside'（軸の内側左上）、または None
    equal_aspect : 両軸で1画素当たりのデータ単位をそろえる（輪郭グラフ用）
    left_margin / legend_width : 軸の左側／右側の凡例に確保する最小画素幅。
             multi_plot はこれらを使い、縦に並べたグラフの x 軸をそろえる。
    """
    W, Hh = int(size[0]), int(size[1])
    fs = max(1, int(font_scale))
    small = max(1, fs - 1) if fs > 2 else fs
    img = draw.canvas(Hh, W, bg)
    series = [dict(s) for s in (series or [])]       # 呼出し元の辞書を変更しない
    for k, s in enumerate(series):
        s.setdefault("color", draw.PALETTE[k % len(draw.PALETTE)])

    xs_all = [s["x"] for s in series]
    ys_all = [s["y"] for s in series]
    x_lo, x_hi = _limits(xs_all, xlim, 0.02)
    y_lo, y_hi = _limits(ys_all, ylim, 0.06)

    # ---- 配置
    labels = [str(s.get("label", "")) for s in series]
    leg_w = 0
    if legend == "right" and any(labels):
        leg_w = max(draw.text_size(l, small)[0] for l in labels) + 48
    yt, ystep = nice_ticks(y_lo, y_hi, 6)
    ytick_w = max([draw.text_size(_fmt(v, ystep), small)[0] for v in yt] + [10])
    left = 12 + (draw.text_size("X", fs)[1] + 10 if ylabel else 0) + ytick_w + 10
    if left_margin is not None:
        left = max(left, int(left_margin))
    if legend_width is not None and legend == "right":
        leg_w = max(leg_w, int(legend_width))
    if _layout_only:
        return {"left_margin": left, "legend_width": leg_w}
    right = W - 16 - leg_w
    top = 12 + (draw.text_size("X", fs)[1] + 12 if title else 0)
    if spans and any(sp.get("label") for sp in spans):
        top += 0
    bottom = Hh - (12 + draw.text_size("0", small)[1] + 10 + (draw.text_size("X", fs)[1] + 8 if xlabel else 0))
    pw, ph = right - left, bottom - top
    if pw < 50 or ph < 50:
        raise ValueError("plot size %r is too small" % (size,))

    if equal_aspect:
        ux = (x_hi - x_lo) / pw
        uy = (y_hi - y_lo) / ph
        if ux > uy:
            c = 0.5 * (y_lo + y_hi)
            y_lo, y_hi = c - 0.5 * ux * ph, c + 0.5 * ux * ph
        else:
            c = 0.5 * (x_lo + x_hi)
            x_lo, x_hi = c - 0.5 * uy * pw, c + 0.5 * uy * pw
        yt, ystep = nice_ticks(y_lo, y_hi, 6)
    xt, xstep = nice_ticks(x_lo, x_hi, 8)

    def X(v):
        return (np.asarray(v, dtype=np.float64) - x_lo) / (x_hi - x_lo) * pw

    def Y(v):
        return (y_hi - np.asarray(v, dtype=np.float64)) / (y_hi - y_lo) * ph

    area = img[top:bottom, left:right]            # 配列ビューへの描画は範囲外を自動的に切り取る

    # ---- 背景を塗る区間
    for k, sp in enumerate(spans or []):
        xa, xb = float(X(sp["x0"])), float(X(sp["x1"]))
        draw.rect(area, xa, 0, xb, ph, sp.get("color", draw.PALETTE[(k + 2) % len(draw.PALETTE)]),
                  fill=True, alpha=sp.get("alpha", 0.15))
    # ---- 格子と目盛り
    for v in xt:
        px = float(X(v))
        if -0.5 <= px <= pw + 0.5:
            if grid:
                draw.line(area, (px, 0), (px, ph), "lightgray", 1, aa=False)
            draw.line(img, (left + px, bottom), (left + px, bottom + 5), "black", 1, aa=False)
            draw.text(img, left + px, bottom + 8, _fmt(v, xstep), "black", small, anchor="ct")
    for v in yt:
        py = float(Y(v))
        if -0.5 <= py <= ph + 0.5:
            if grid:
                draw.line(area, (0, py), (pw, py), "lightgray", 1, aa=False)
            draw.line(img, (left - 5, top + py), (left, top + py), "black", 1, aa=False)
            draw.text(img, left - 8, top + py, _fmt(v, ystep), "black", small, anchor="rm")
    # ---- 区間名（内側上部）と補助線
    for k, sp in enumerate(spans or []):
        if sp.get("label"):
            xa, xb = float(X(sp["x0"])), float(X(sp["x1"]))
            draw.text(area, 0.5 * (max(xa, 0) + min(xb, pw)), 4, str(sp["label"]),
                      sp.get("color", draw.PALETTE[(k + 2) % len(draw.PALETTE)]), small, anchor="ct",
                      bg="white", bg_alpha=0.6, margin=1)
    for k, vl in enumerate(vlines or []):
        px = float(X(vl["x"]))
        col = vl.get("color", "darkgray")
        draw.line(area, (px, 0), (px, ph), col, vl.get("width", 2), dash=vl.get("dash", (6, 4)))
        if vl.get("label"):
            row = 1 + (k % 3)
            draw.text(area, px + 4, 4 + row * (draw.text_size("X", small)[1] + 4), str(vl["label"]), col, small,
                      anchor="lt", bg="white", bg_alpha=0.6, margin=1)
    for k, hl in enumerate(hlines or []):
        py = float(Y(hl["y"]))
        col = hl.get("color", "darkgray")
        draw.line(area, (0, py), (pw, py), col, hl.get("width", 2), dash=hl.get("dash", (6, 4)))
        if hl.get("label"):
            draw.text(area, pw - 4, py - 3, str(hl["label"]), col, small, anchor="rb", bg="white",
                      bg_alpha=0.6, margin=1)
    # ---- データ
    for s in series:
        x = np.asarray(s["x"], dtype=np.float64).ravel()
        y = np.asarray(s["y"], dtype=np.float64).ravel()
        if x.shape != y.shape:
            raise ValueError("series %r: x and y differ in length" % s.get("label"))
        pts = np.stack([X(x), Y(y)], axis=1)
        pts[~np.isfinite(pts).all(axis=1)] = np.nan
        # 遠方の点でラスタ描画の反復が膨らまないよう、座標の範囲を制限する
        pts = np.clip(pts, -4.0 * max(pw, ph), 5.0 * max(pw, ph))
        if s.get("line", True) and len(pts) > 1:
            draw.polyline(area, pts, s["color"], s.get("width", 2), dash=s.get("dash"))
        mk = s.get("marker")
        if mk:
            for p in pts[np.isfinite(pts).all(axis=1)]:
                if -5 <= p[0] <= pw + 5 and -5 <= p[1] <= ph + 5:
                    draw.marker(area, p, mk, s.get("marker_size", 3), s["color"], 1.5)
    # ---- 枠と軸名
    draw.rect(img, left - 1, top - 1, right + 1, bottom + 1, "black", 1)
    if title:
        draw.text(img, 0.5 * (left + right), 8, str(title), "black", fs, anchor="ct")
    if xlabel:
        draw.text(img, 0.5 * (left + right), Hh - 8, str(xlabel), "black", fs, anchor="cb")
    if ylabel:
        tw, th = draw.text_size(str(ylabel), fs)
        tmp = draw.canvas(th + 2, tw + 2, bg)
        draw.text(tmp, 1, 1, str(ylabel), "black", fs)
        rot = np.rot90(tmp, 1)                      # 下から上へ読む向き
        y0 = int(round(0.5 * (top + bottom) - rot.shape[0] / 2.0))
        y0 = max(0, min(y0, Hh - rot.shape[0]))
        hh = min(rot.shape[0], Hh - y0)
        img[y0:y0 + hh, 8:8 + rot.shape[1]] = rot[:hh]
    # ---- 凡例
    if legend and any(labels):
        lh = draw.text_size("X", small)[1] + 8
        if legend == "right":
            lx, ly = right + 12, top + 4
        else:
            lx, ly = left + 10, top + 8
            bw = max(draw.text_size(l, small)[0] for l in labels) + 44
            draw.rect(img, lx - 4, ly - 4, lx + bw, ly + lh * sum(1 for l in labels if l) + 2, "white",
                      fill=True, alpha=0.8)
        row = 0
        for s, l in zip(series, labels):
            if not l:
                continue
            yy = ly + row * lh + lh / 2.0
            if s.get("line", True):
                draw.line(img, (lx, yy), (lx + 28, yy), s["color"], s.get("width", 2) + 1, dash=s.get("dash"))
            if s.get("marker"):
                draw.marker(img, (lx + 14, yy), s["marker"], s.get("marker_size", 3) + 1, s["color"], 1.5)
            draw.text(img, lx + 34, yy, l, "black", small, anchor="lm")
            row += 1
    return img


def multi_plot(plots, ncols=1, gap=10, title=None, bg="white", font_scale=3, align_axes=True):
    """複数のグラフを一つの図に並べる。
    plots: RGB 配列、または line_plot のキーワード引数を収めた辞書のリスト。
    align_axes: 辞書で指定したグラフの左余白と凡例幅をそろえ、同じ `size` と `xlim` を持つ
    グラフを縦一列に並べたときに x 軸の位置を一致させる。"""
    dicts = [p for p in plots if isinstance(p, dict)]
    if align_axes and dicts:
        lay = [line_plot(_layout_only=True, **p) for p in dicts]
        lm = max(l["left_margin"] for l in lay)
        lw = max(l["legend_width"] for l in lay)
        plots = [dict(p, left_margin=max(lm, p.get("left_margin") or 0),
                      legend_width=max(lw, p.get("legend_width") or 0)) if isinstance(p, dict) else p
                 for p in plots]
    imgs = [line_plot(**p) if isinstance(p, dict) else draw.to_rgb(p) for p in plots]
    rows = []
    for r in range(0, len(imgs), max(1, ncols)):
        rows.append(draw.hstack(imgs[r:r + ncols], gap=gap, bg=bg))
    fig = draw.vstack(rows, gap=gap, bg=bg)
    if title:
        tw, th = draw.text_size(title, font_scale)
        head = draw.canvas(th + 16, max(fig.shape[1], tw + 16), bg)
        draw.text(head, head.shape[1] / 2.0, 8, title, "black", font_scale, anchor="ct")
        fig = draw.vstack([head, fig], gap=0, bg=bg, align="center")
    return fig
