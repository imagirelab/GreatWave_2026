# 仕上げ36：原画視点 t* の ID の画像（評価器 23 の入力、爪あり・線なし）で、主浪の範囲の色区の面積の割合と、原画の色区との一致を数える（記録のみ）。
# 頂の帯（原画の色区の地図で、主浪の上の部分＝表示 y < 520 かつ x 300〜1150）でも数える。
import sys, json
import numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
from pl36_zone_study import id_classes

LAB = 'G:/Unity/GreatWave_2026_Fresh/Tools/PaintingTruth/colour/masks/mw_colour_labels.png'

def stats(ids_path):
    cls, _ = id_classes(ids_path)
    cls = cls[::2, ::2] if cls.shape[0] == 2160 else cls
    lab = np.asarray(Image.open(LAB))
    pl = np.full(lab.shape, -1); pl[lab == 1] = 0; pl[lab == 2] = 1; pl[lab == 3] = 2; pl[lab == 4] = 3
    out = {}
    yy, xx = np.mgrid[0:1080, 0:1920]
    for name, reg in [('main', np.isin(lab, [1, 2, 3, 4])), ('crest', np.isin(lab, [1, 2, 3, 4]) & (yy < 520) & (xx > 300) & (xx < 1150))]:
        m = reg & (cls >= 0)
        r = {}
        for k, nm in enumerate(['white', 'mizuiro', 'ai_mid', 'ai_dark']):
            r[nm] = float((cls[m] == k).mean()); r[nm + '_painting'] = float((pl[m] == k).mean())
        r['agree_class'] = float((cls[m] == pl[m]).mean())
        wi = lambda a: np.where(a <= 1, 0, 1)
        r['agree_white_indigo'] = float((wi(cls[m]) == wi(pl[m])).mean())
        r['n'] = int(m.sum())
        out[name] = r
    return out

if __name__ == '__main__':
    res = {}
    for arg in sys.argv[1:]:
        name, p = arg.split('=')
        res[name] = stats(p)
        print(name, json.dumps({k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in res[name].items()}))
