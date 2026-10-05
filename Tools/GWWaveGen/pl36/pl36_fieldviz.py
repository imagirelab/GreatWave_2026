# 仕上げ36：面の座標の画像を色の帯にして、描画の上に重ねた点検の図を作る（記録と数値の合わせのためだけ）。
import sys, os, argparse
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import pl36_fields as pf

COLS = np.array([[230,60,60],[240,170,40],[230,230,40],[60,200,60],[40,200,220],[60,90,240],[170,60,230],[240,80,180],[120,120,120],[40,40,40],[255,255,255]], float)

def bands(base, arr, mask, edges):
    idx = np.digitize(np.nan_to_num(arr, nan=-1e9), edges) - 1
    out = base.copy()
    for i in range(len(edges) - 1):
        mm = mask & (idx == i)
        out[mm] = 0.4 * base[mm] + 0.6 * COLS[i % len(COLS)]
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fields', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--key', default='F')
    ap.add_argument('--edges', default='0,1,1.2,1.4,1.6,1.8,2,2.3,2.6,3,4,9')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    d = pf.load(a.fields)
    base = np.asarray(Image.open(a.base).convert('RGB')).astype(float)
    edges = [float(x) for x in a.edges.split(',')]
    out = bands(base, d[a.key], d['mask'], edges)
    img = Image.fromarray(out.astype(np.uint8))
    dr = ImageDraw.Draw(img)
    for i in range(len(edges) - 1):
        dr.rectangle([10, 10 + i * 22, 30, 28 + i * 22], fill=tuple(int(x) for x in COLS[i % len(COLS)]))
        dr.text((36, 12 + i * 22), f'{a.key} {edges[i]}-{edges[i+1]}', fill=(0, 0, 0))
    img.save(a.out)
