# figure: main-row jet sheet history (ballistic inverse solution, wave frame) over K* main row. py -3.10 (OpenCV)
# usage (リポジトリの根で): py -3.10 -B Tools/GWWaveGen/ds26/fig_e1.py   （e3_keypose_sampling.py の e3_mainrow_snapshots.npz を読む。旧規則＝頂の1点・補間 0.6 s の解）
#   → Docs/Evidence/Design/26/e1_mainrow_history.png
import sys, numpy as np, cv2
import os
import ds26_paths as DP
d = np.load(os.path.join(DP.OUT_FEAS, 'e3_mainrow_snapshots.npz')); outp = os.path.join(DP.outdir(DP.EVID), 'e1_mainrow_history.png')
W, Hh = 1600, 900
img = np.full((Hh, W, 3), 255, np.uint8)
ax0, ax1, ay0, ay1 = -12.0, 26.0, -2.0, 25.0
def P(a, y):
    return (int(80 + (a - ax0) / (ax1 - ax0) * (W - 120)), int(Hh - 60 - (y - ay0) / (ay1 - ay0) * (Hh - 110)))
# grid
for gy in range(0, 26, 5):
    cv2.line(img, P(ax0, gy), P(ax1, gy), (230, 230, 230), 1); cv2.putText(img, f'{gy} m', (20, P(0, gy)[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
for gx in range(-10, 27, 5):
    cv2.line(img, P(gx, ay0), P(gx, ay1), (235, 235, 235), 1); cv2.putText(img, f'a={gx}', (P(gx, 0)[0] - 20, Hh - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)
cv2.line(img, P(ax0, 0), P(ax1, 0), (180, 120, 60), 2)
Ka, Ky = d['K_a'], d['K_y']
pts = np.array([P(a, y) for a, y in zip(Ka, Ky)], np.int32)
cv2.polylines(img, [pts], False, (150, 150, 150), 3)
t = d['t']; X = d['X']; nup = int(d['n_up'])
order = list(range(nup - 1, -1, -1)) + list(range(nup, X.shape[0]))
cols = [(200, 60, 20), (210, 110, 30), (200, 160, 40), (120, 170, 60), (60, 160, 120), (0, 0, 0), (60, 60, 220), (40, 40, 180), (20, 20, 140)]
for k in range(len(t)):
    Pl = X[order, k, :]
    if t[k] > 0:  # near-root points (tau < Tr) are still being ejected at t*; their solve is ill-conditioned -> not drawn after t*
        keep = d['tau'][order] >= float(d['Tr'])
        Pl = Pl[keep]
    # skip points still attached (wave-frame x equal to the crest top x and y at release path) -> draw anyway
    pp = np.array([P(a, y) for a, y in Pl], np.int32)
    cv2.polylines(img, [pp], False, cols[k], 2 if t[k] != 0 else 3)
    tip = X[0, k]
    cv2.circle(img, P(*tip), 6, cols[k], -1)
    cv2.putText(img, f'{t[k]:+.1f} s', (P(*tip)[0] + 8, P(*tip)[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, cols[k], 2)
# seat (ground-fixed) in wave frame at t>=0: a = 16.57 - beta*c0*t
for k in range(len(t)):
    if t[k] >= 0:
        sa = float(d['seat_a_ground']) - float(d['beta']) * float(d['c0']) * t[k]
        cv2.drawMarker(img, P(sa, float(d['seat_y'])), cols[k], cv2.MARKER_TRIANGLE_UP, 18, 2)
cv2.putText(img, 'Main row (c=0), wave-following frame. Grey: K* at t*. Coloured: jet-sheet points of the inverse-ballistic solution', (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
cv2.putText(img, '(c0=20 m/s, jet onset -2.4 s, p=0.5, decel to 0.8c0, release ramp 0.6 s). Triangles: seat v1 at t>=0. Body/tube not modelled.', (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
cv2.imwrite(outp, img)
print('ok', outp)
