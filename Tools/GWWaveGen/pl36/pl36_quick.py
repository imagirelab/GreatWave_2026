# 仕上げ36：試しの描画を前（仕上げ35 の r_after）と並べて見る小さな道具（点検用。証拠の図は pl36_sheets.py）。
import sys, os
from PIL import Image
B = 'G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish'
def sheet(names, view, t, cond='asis', crop=None, scale=0.5, out=None):
    ims = []
    for n in names:
        p = (B + '/35/r_after/views/' if n == 'before' else B + '/36/' + n + '/views/') + f'{view}_{t}_{cond}.png'
        im = Image.open(p).convert('RGB')
        if crop: im = im.crop(crop)
        im = im.resize((int(im.width * scale), int(im.height * scale)))
        ims.append(im)
    W = sum(i.width for i in ims); H = max(i.height for i in ims)
    o = Image.new('RGB', (W, H)); x = 0
    for i in ims: o.paste(i, (x, 0)); x += i.width
    o.save(out)
if __name__ == '__main__':
    names = sys.argv[1].split(','); view = sys.argv[2]; t = sys.argv[3]
    crop = tuple(int(v) for v in sys.argv[4].split(',')) if len(sys.argv) > 4 and sys.argv[4] != '-' else None
    scale = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
    sheet(names, view, t, crop=crop, scale=scale, out=B + f'/36/look/q_{view}_{t}_{"_".join(names)}.png')
