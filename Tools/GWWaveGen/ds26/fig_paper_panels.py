# Fig. 4 a-d (120 deg, the user's choice) beside Fig. 5 a-f (60 deg, the draft's default), from the PDF-embedded JPEGs,
# mirrored to the published orientation (the PDF draws them with a negative x scale), with the CC BY credit.
# Only PDF-extracted panels are used (no pixels from the user's high-resolution photos).
# usage (リポジトリの根で): py -3.10 -B Tools/GWWaveGen/ds26/fig_paper_panels.py --pdf <McAllister 2019 の PDF>
#   PDF（CC BY 4.0、doi:10.1017/jfm.2018.886、SHA-256 を照合）から Fig. 4・5 の埋め込み JPEG（obj 465〜468・476〜481）を
#   Unity/Build/Design/26/paper/ へ取り出し、並べ図を Docs/Evidence/Design/26/fig_paper_fig4_fig5.png に書く。
#   利用者の高解像度の写真（webp）は読まない。
import sys
import numpy as np, cv2
import os, re
import ds26_paths as DP
pd = DP.outdir(DP.OUT_PAPER)
_data = open(DP.paper_pdf(), 'rb').read()
_objs = {}
for _m in re.finditer(rb'(\d+)\s+(\d+)\s+obj(.*?)endobj', _data, re.S):
    _objs[int(_m.group(1))] = _m.group(3)
for _n in (465, 466, 467, 468, 476, 477, 478, 479, 480, 481):
    _b = _objs[_n]; _sm = re.search(rb'stream\r?\n', _b); _head = _b[:_sm.start()]
    if b'/Image' not in _head or b'/DCTDecode' not in _head:
        sys.exit('obj %d is not a DCT image' % _n)
    _raw = _b[_sm.end():]; _raw = _raw[:_raw.rfind(b'endstream')]
    open(os.path.join(pd, 'img_%d.jpg' % _n), 'wb').write(_raw.rstrip(b'\r\n'))
outp = os.path.join(DP.outdir(DP.EVID), 'fig_paper_fig4_fig5.png')
S = 1.6
def panel(n):
    im = cv2.imread(f'{pd}/img_{n}.jpg'); im = cv2.flip(im, 1)
    return cv2.resize(im, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
p = panel(465); ph, pw = p.shape[:2]
gap = 10; lab_h = 34; W = 4 * pw + 5 * gap
rows = [('Fig. 4 (crossing 120 deg) a-d  = the four frames the user picked; e-f (not picked) jet upward', [465, 466, 467, 468], 'abcd'),
        ('Fig. 5 (crossing 60 deg, draft default) a-d', [476, 477, 478, 479], 'abcd'),
        ('Fig. 5 (60 deg) e-f', [480, 481], 'ef')]
H = sum(lab_h + ph + gap for _ in rows) + 70
cv = np.full((H, W, 3), 255, np.uint8)
y = gap
for title, ids, letters in rows:
    cv2.putText(cv, title, (gap, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    y += lab_h
    for k, (n, L) in enumerate(zip(ids, letters)):
        x = gap + k * (pw + gap)
        cv[y:y + ph, x:x + pw] = panel(n)
        cv2.putText(cv, f'({L})', (x + 8, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(cv, f'({L})', (x + 8, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 1, cv2.LINE_AA)
    y += ph + gap
cred = ['McAllister et al. 2019, J. Fluid Mech. 860, Fig. 4/5, photos D. Noble, CC BY 4.0 https://creativecommons.org/licenses/by/4.0/',
        '- cropped, mirrored to published orientation. Frames 100 ms apart in the tank (about 0.6 s at field scale).']
for i, t in enumerate(cred):
    cv2.putText(cv, t, (gap, y + 22 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
cv2.imwrite(outp, cv)
print('wrote', outp, cv.shape)
