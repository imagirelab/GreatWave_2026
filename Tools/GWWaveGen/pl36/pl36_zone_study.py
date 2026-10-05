# 仕上げ36：原画視点 t* で、主役波の前の白（頂から唇の先の側）の (c, F) の升ごとに、原画の色区（白・淡い水色／藍）の割合と、
# 3D の爪が覆う割合を数える。爪の所の主役波の地の色（藍か白か）を、面の座標の升ごとの数値として決めるための調べ（色は投影しない。Q28）。
import sys, os, json, argparse
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import pl36_fields as pf

def id_classes(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    cls = np.full(a.shape[:2], -1, int)
    cls[(a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 0)] = 0
    cls[(a[..., 0] == 0) & (a[..., 1] == 255) & (a[..., 2] == 0)] = 1
    cls[(a[..., 0] == 0) & (a[..., 1] == 0) & (a[..., 2] == 255)] = 2
    cls[(a[..., 0] == 255) & (a[..., 1] == 255) & (a[..., 2] == 0)] = 3
    return cls, a

def down2(m):
    h, w = m.shape[0] // 2, m.shape[1] // 2
    return m[:2 * h, :2 * w].reshape(h, 2, w, 2).mean(axis=(1, 3))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fields', default='Unity/Build/Polish/29/fix01/p29g/fields/painting_t120')
    ap.add_argument('--ids', default='Unity/Build/Polish/35/r_after/full/ids_noline.png')
    ap.add_argument('--ids_nc', default='Unity/Build/Polish/35/r_after/full/ids_noline_noclaws.png')
    ap.add_argument('--labels', default='Tools/PaintingTruth/colour/masks/mw_colour_labels.png')
    ap.add_argument('--out', default='Unity/Build/Polish/36/look/zone_study.json')
    a = ap.parse_args()
    d = pf.load(a.fields)
    lab = np.asarray(Image.open(a.labels))
    c1, A = id_classes(a.ids)
    c0, B = id_classes(a.ids_nc)
    claw = down2((np.abs(A - B).sum(-1) > 0).astype(float))
    clawW = down2(((np.abs(A - B).sum(-1) > 0) & ((c1 == 0) | (c1 == 1))).astype(float))
    F, c, m = d['F'], d['c'], d['mask']
    wm = np.isin(lab, [1, 2]); ind = np.isin(lab, [3, 4]); sky = np.isin(lab, [0, 9]); line = lab == 5
    Fb = np.arange(1.0, 2.71, 0.1); cb = np.arange(-22, 14.1, 2.0)
    rows = []
    for i in range(len(cb) - 1):
        for j in range(len(Fb) - 1):
            mm = m & (c >= cb[i]) & (c < cb[i + 1]) & (F >= Fb[j]) & (F < Fb[j + 1])
            n = int(mm.sum())
            if n < 40:
                continue
            nn = max(int((wm | ind)[mm].sum()), 1)
            rows.append(dict(c0=float(cb[i]), F0=float(round(Fb[j], 2)), n=n,
                             wm=float(wm[mm].sum() / nn), ind=float(ind[mm].sum() / nn),
                             sky=float(sky[mm].mean()), line=float(line[mm].mean()),
                             claw=float(claw[mm].mean()), clawW=float(clawW[mm].mean())))
    json.dump(dict(rows=rows), open(a.out, 'w'), indent=1)
    # 表：行 c、列 F、値 = 原画の白・淡い水色の割合（爪の覆い）
    print('c\F ' + ' '.join(f'{f:5.1f}' for f in Fb[:-1]))
    for i in range(len(cb) - 1):
        line_s = f'{cb[i]:5.0f} '
        for j in range(len(Fb) - 1):
            r = [x for x in rows if x['c0'] == cb[i] and abs(x['F0'] - round(Fb[j], 2)) < 1e-6]
            line_s += (f'{int(100*r[0]["wm"]):3d}/{int(100*r[0]["claw"]):2d}' if r else '   .  ').rjust(7)
        print(line_s)
