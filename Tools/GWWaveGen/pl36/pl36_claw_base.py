# 仕上げ36：3D の爪がどの色の地の上に見えるかを数える（Q28・121。記録）。
# PL36Render の ids の段（diag/<視点>_<時刻>_id_claws1.png＝爪ありの色区 ID、_id_claws0.png＝爪なし）から、爪の画素 K（爪ありと爪なしで ID が違う画素）と、
# K のまわり 3 画素の輪（主役波の画素だけ）の地の色区を数える。地が藍（藍中・藍濃）・淡い水色・白のどれか。白い爪（ID 白）の縁が藍の地に接する割合も数える。
import sys, os, json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
VIEWS = ['painting', 'seat', 'seat_toward_wave', 'side_left', 'side_right', 'back65', 'top']
TS = ['t060', 't090', 't105', 't120']
COL = {(255, 0, 0): 0, (0, 255, 0): 1, (0, 0, 255): 2, (255, 255, 0): 3}
def cls(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(np.int32)
    k = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
    out = np.full(k.shape, -1, np.int8)
    for (r, g, b), v in COL.items():
        out[k == r * 65536 + g * 256 + b] = v
    return out
def hero(p):
    a = np.asarray(Image.open(p).convert('RGBA'))
    return np.abs(a[..., 3].astype(int) - 128) < 3
def measure(d, v, t):
    c1 = cls(os.path.join(d, f'{v}_{t}_id_claws1.png')); c0 = cls(os.path.join(d, f'{v}_{t}_id_claws0.png'))
    h0 = hero(os.path.join(d, f'{v}_{t}_hero_claws0.png'))
    a1 = np.asarray(Image.open(os.path.join(d, f'{v}_{t}_id_claws1.png')).convert('RGB')).astype(int)
    a0 = np.asarray(Image.open(os.path.join(d, f'{v}_{t}_id_claws0.png')).convert('RGB')).astype(int)
    K = np.abs(a1 - a0).sum(-1) > 0
    K &= c1 >= 0
    ring = ndi.binary_dilation(K, iterations=3) & ~K & h0 & (c1 >= 0)
    n = int(ring.sum()); nk = int(K.sum())
    if n == 0:
        return {'claw_px': nk, 'ring_px': 0}
    base = c1[ring]
    Kw = K & (c1 == 0)
    rw = ndi.binary_dilation(Kw, iterations=2) & ~K & h0 & (c1 >= 0)
    bw = c1[rw]
    return {'claw_px': nk, 'ring_px': n,
            'base_white': round(float((base == 0).mean()), 3), 'base_mizuiro': round(float((base == 1).mean()), 3),
            'base_indigo': round(float(np.isin(base, [2, 3]).mean()), 3),
            'white_claw_px': int(Kw.sum()), 'white_claw_edge_on_indigo': round(float(np.isin(bw, [2, 3]).mean()), 3) if bw.size else None,
            'white_claw_edge_on_white': round(float((bw == 0).mean()), 3) if bw.size else None}
if __name__ == '__main__':
    res = {}
    for arg in sys.argv[1:]:
        if arg.startswith('--out='): continue
        name, d = arg.split('=', 1)
        res[name] = {f'{v}/{t}': measure(d, v, t) for v in VIEWS for t in TS}
    out = [a for a in sys.argv[1:] if a.startswith('--out=')]
    if out: json.dump(res, open(out[0][6:], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    names = list(res)
    for v in VIEWS:
        for t in TS:
            print(f'{v:16s} {t}', '  '.join(f"{n}: claws {res[n][f'{v}/{t}'].get('claw_px',0):6d} base W/M/I {res[n][f'{v}/{t}'].get('base_white','-')}/{res[n][f'{v}/{t}'].get('base_mizuiro','-')}/{res[n][f'{v}/{t}'].get('base_indigo','-')}" for n in names))
