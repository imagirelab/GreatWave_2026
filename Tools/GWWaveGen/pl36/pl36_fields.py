# 仕上げ36：面の座標の画像（PL29Render の fields 段、_PL29Diag 3・4・6）を読み、(F, hrel, c, ca, kc) の画素の配列にする道具。
# 原画視点で原画の色区と面の座標を並べて数値を合わせるためだけに使う（色は投影しない。Q28）。
import numpy as np
from PIL import Image

def _q16(im):
    a = np.asarray(Image.open(im).convert('RGBA')).astype(np.float64)
    mask = np.abs(a[..., 3] - 128) < 2
    v = (a[..., 0] * 256 + a[..., 1]) / 65535.0
    b = a[..., 2] / 255.0
    return v, b, mask

def load(prefix):
    """prefix = '.../fields/painting_t120' → dict of arrays (nan outside the hero)"""
    v3, b3, m = _q16(prefix + '_m3.png')
    v4, b4, _ = _q16(prefix + '_m4.png')
    v6, b6, _ = _q16(prefix + '_m6.png')
    out = {
        'mask': m,
        'F': v3 * 12.0 - 2.0,
        'hrel': b3 * 1.2,
        'c': v4 * 96.0 - 64.0,
        'ny': b4 * 2.0 - 1.0,
        'ca': v6 * 140.0 - 80.0,
        'kc': b6 * 4.0,
    }
    for k in list(out):
        if k != 'mask':
            out[k] = np.where(m, out[k], np.nan)
    return out
