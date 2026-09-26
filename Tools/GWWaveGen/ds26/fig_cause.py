# Cause figure for 設計26 (review fix 16a; plan §2.1 "explain the cause of breaking in text and figure").
# Left: plan view at t* - two linear JONSWAP groups at +-30 deg to the travel direction t focus at the K* crest foot
#       (world (-7.23, 0, -2.71)); background = combined carrier elevation at t* (A_c = 3 m), thin lines = crest lines of the
#       two systems (peak wavelength 195 m), the hero sheet footprint, PaintingCam v1 frustum (painting columns), seat v1,
#       the next crossing peaks (about 113 m along t, 195 m across).
# Right: main-row section (ground frame, metres, t* = K*): crest top advancing at c0 (dots at the a-b-c-d stage times),
#       lip vertices parked on the crest front, launched (release ramp) and then flying under gravity only to K*.
# usage (リポジトリの根で): py -3.10 -B Tools/GWWaveGen/ds26/fig_cause.py   → Docs/Evidence/Design/26/fig_ds26_cause.png
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
import sys, json, math
import numpy as np, cv2
from e4_common import *
import os
meta = json.load(open(DP.require(DP.KSTAR_META, 'kstar_a45_meta.json'), encoding='utf-8')); outp = os.path.join(DP.outdir(DP.EVID), 'fig_ds26_cause.png')
fr = meta['frame']; O = np.array(fr['section_origin_world']); tv = np.array(fr['t_travel']); ev = np.array(fr['e_crest'])
t2 = np.array([tv[0], tv[2]]); e2 = np.array([ev[0], ev[2]]); O2 = np.array([O[0], O[2]])
W, H_ = 1900, 940
img = np.full((H_, W, 3), 255, np.uint8)
FONT = cv2.FONT_HERSHEY_SIMPLEX
def txt(s, p, sc=0.5, col=(0, 0, 0), th=1):
    cv2.putText(img, s, (int(p[0]), int(p[1])), FONT, sc, col, th, cv2.LINE_AA)
# ---------------- plan view ----------------
X0, X1, Z0, Z1 = -260.0, 200.0, -230.0, 270.0; SC = 1.6; ox, oy = 20, 60
pw, ph = int((X1 - X0) * SC), int((Z1 - Z0) * SC)
def P(x, z):
    return (int(ox + (x - X0) * SC), int(oy + (Z1 - z) * SC))
xs = np.linspace(X0, X1, pw); zs = np.linspace(Z1, Z0, ph)
XX, ZZ = np.meshgrid(xs, zs)
aa = (XX - O2[0]) * t2[0] + (ZZ - O2[1]) * t2[1]; cc = (XX - O2[0]) * e2[0] + (ZZ - O2[1]) * e2[1]
lam = 195.0; fp = math.sqrt(g / (2 * math.pi * lam)); fq = np.linspace(0.5 * fp, 2.5 * fp, 120)
sj = np.where(fq <= fp, 0.07, 0.09)
Sp = fq ** -5 * np.exp(-1.25 * (fp / fq) ** 4) * 3.3 ** np.exp(-(fq - fp) ** 2 / (2 * sj * sj * fp * fp))
amp = np.sqrt(Sp); amp /= amp.sum(); kk = (2 * math.pi * fq) ** 2 / g
c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
x1 = aa * c30 + cc * s30; x2 = aa * c30 - cc * s30
eta = np.zeros_like(aa)
for n in range(len(kk)):
    eta += amp[n] * (np.cos(kk[n] * x1) + np.cos(kk[n] * x2))
eta *= 1.5
v = np.clip(eta / 3.0, -1, 1)
bg = np.zeros((ph, pw, 3), np.float32)
bg[..., 0] = np.where(v < 0, 1.0, 1 - v); bg[..., 1] = 1 - np.abs(v) * 0.85; bg[..., 2] = np.where(v > 0, 1.0, 1 + v)  # BGR: blue trough, red crest
img[oy:oy + ph, ox:ox + pw] = (bg * 255).astype(np.uint8)
cv2.rectangle(img, (ox, oy), (ox + pw, oy + ph), (0, 0, 0), 1)
d1 = c30 * t2 + s30 * e2; d2 = c30 * t2 - s30 * e2
for dd, col in ((d1, (0, 110, 0)), (d2, (120, 0, 120))):
    nrm = np.array([-dd[1], dd[0]])
    for n in range(-3, 4):
        base = O2 + n * lam * dd
        pa = base - 600 * nrm; pb = base + 600 * nrm
        ok, c1_, c2_ = cv2.clipLine((ox, oy, pw, ph), P(*pa), P(*pb))
        if ok:
            cv2.line(img, c1_, c2_, col, 1, cv2.LINE_AA)
    st = O2 - 200 * dd; en = O2 - 60 * dd
    cv2.arrowedLine(img, P(*st), P(*en), col, 3, cv2.LINE_AA, tipLength=0.25)
cv2.arrowedLine(img, P(*(O2 - 150 * t2)), P(*(O2 - 20 * t2)), (0, 0, 0), 2, cv2.LINE_AA, tipLength=0.2)
# hero sheet footprint
corn = [(-49.2, -60), (32.5, -60), (32.5, 15), (-49.2, 15), (-49.2, -60)]
pts = [P(*(O2 + a_ * t2 + c_ * e2)) for a_, c_ in corn]
for i in range(4):
    cv2.line(img, pts[i], pts[i + 1], (0, 0, 0), 2, cv2.LINE_AA)
cv2.circle(img, P(*O2), 6, (0, 0, 0), -1)
# PaintingCam v1 frustum (horizontal edges of painting columns 157 / 1762)
cam = np.array([0.0, -62.0]); fw = np.array([-2.5, 66.0]); fw /= np.linalg.norm(fw); rt = np.array([fw[1], -fw[0]])
tw = math.tan(math.radians(13.0)) * 1920 / 1080
for col in (157, 1762):
    xn = (2 * (col + 0.5) / 1920 - 1) * tw
    dd = fw + xn * rt; dd /= np.linalg.norm(dd)
    ok, c1_, c2_ = cv2.clipLine((ox, oy, pw, ph), P(*cam), P(*(cam + 400 * dd)))
    if ok:
        cv2.line(img, c1_, c2_, (60, 60, 60), 1, cv2.LINE_AA)
cv2.circle(img, P(*cam), 5, (60, 60, 60), -1)
seat = np.array([3.954, -15.031]); cv2.circle(img, P(*seat), 5, (0, 140, 255), -1)
for sgn in (-1, 1):
    pk = O2 + (lam / (2 * c30)) * t2 + sgn * (lam / (2 * s30)) * e2
    pk2 = O2 - (lam / (2 * c30)) * t2 + sgn * (lam / (2 * s30)) * e2
    for pp in (P(*pk), P(*pk2)):
        if ox + 8 <= pp[0] <= ox + pw - 8 and oy + 8 <= pp[1] <= oy + ph - 8:
            cv2.drawMarker(img, pp, (0, 0, 180), cv2.MARKER_TILTED_CROSS, 14, 2)
txt('Plan view at t* (world X right, Z up; 1 px = 0.625 m)', (ox, 30), 0.6, th=2)
txt('focus = K* crest foot (-7.2, -2.7) at t*', (P(*O2)[0] - 330, P(*O2)[1] + 150), 0.45)
cv2.line(img, P(*O2), (P(*O2)[0] - 120, P(*O2)[1] + 140), (0, 0, 0), 1)
txt('system 1 (+30 deg)', (P(*(O2 - 210 * d1))[0] - 60, P(*(O2 - 210 * d1))[1] + 20), 0.45, (0, 110, 0))
txt('system 2 (-30 deg)', (P(*(O2 - 210 * d2))[0] - 40, P(*(O2 - 210 * d2))[1] + 20), 0.45, (120, 0, 120))
txt('t (bisector, travel)', (P(*(O2 - 150 * t2))[0] - 150, P(*(O2 - 150 * t2))[1] - 8), 0.45)
txt('hero sheet (82 m x 75 m)', (P(*(O2 + 32 * t2 + 15 * e2))[0] + 6, P(*(O2 + 32 * t2 + 15 * e2))[1] - 10), 0.45)
txt('PaintingCam v1', (P(*cam)[0] + 8, P(*cam)[1] + 4), 0.45, (60, 60, 60))
txt('seat v1', (P(*seat)[0] + 30, P(*seat)[1] + 30), 0.45, (0, 110, 230))
txt('x = next crossing peaks (113 m along t, 195 m across)', (ox + 8, oy + ph - 12), 0.45, (0, 0, 180))
txt('colour: carrier elevation at t*, blue -3 m .. red +3 m (linear, A_c 3 m)', (ox + 8, oy + ph + 22), 0.45)
txt('lines: crest lines of each system, lambda_p 195 m', (ox + 8, oy + ph + 42), 0.45)
# ---------------- section ----------------
sx0, sy0 = 790, 70; SA, a0_, a1_, y0_, y1_ = 9.2, -88.0, 30.0, -2.0, 26.0
def Q(a_, y_):
    return (int(sx0 + (a_ - a0_) * SA), int(sy0 + (y1_ - y_) * SA))
cv2.rectangle(img, Q(a0_, y1_), Q(a1_, y0_), (0, 0, 0), 1)
cv2.line(img, Q(a0_, 0), Q(a1_, 0), (180, 180, 180), 1)
q = rows[i_main]; a = A[q['r']]; y = Y[q['r']]
cf = Cfg('d', rule='strip', floor=1.2, tr_rule='half')
R = ramp_solve(q, cf)
Kp = [Q(a[j], y[j]) for j in range(18, 395)]
for i in range(len(Kp) - 1):
    cv2.line(img, Kp[i], Kp[i + 1], (0, 0, 0), 2, cv2.LINE_AA)
stages = [('a', -4.2 + 0.19, 0.60), ('b', -3.4 + 0.19, 0.72), ('c', -2.2075, 0.894), ('d', -1.86, 0.911), ('apex', -1.232, 0.941), ('K*', 0.0, 1.0)]
for lab, tau, hr in stages:
    T = -tau
    ac = q['a_top'] - float(D_r(np.array(T), R['T_row'], cf)); yc = hr * q['H']
    cv2.circle(img, Q(ac, yc), 6, (90, 90, 90), -1)
    txt(lab, (Q(ac, yc)[0] - 6, Q(ac, yc)[1] - 12), 0.55, (60, 60, 60), 2)
    txt(f'{tau:+.2f} s', (Q(ac, yc)[0] - 20, Q(ac, yc)[1] + 24), 0.4, (60, 60, 60))
cols_c = [(200, 120, 0), (0, 150, 0), (0, 140, 255), (200, 0, 200), (0, 0, 220), (0, 0, 0)]
snapT = [1.8, 1.4, 1.0, 0.6, 0.2]
X, V, _ = state(q, cf, R, np.array(snapT))
upm = q['cols'] <= q['jtip']
for k, T in enumerate(snapT):
    for i in np.where(upm)[0][::3]:
        released = R['Tc'][i] >= T
        cv2.circle(img, Q(*X[i, k]), 2 if released else 1, cols_c[k] if released else (150, 150, 150), -1)
    xtip = X[np.where(q['cols'] == q['jtip'])[0][0], k]
    txt(f'{-T:+.1f} s', (Q(*xtip)[0] + 4, Q(*xtip)[1] - 4), 0.42, cols_c[k])
it = int(np.where(q['cols'] == q['jtip'])[0][0])
Tg = np.linspace(R['Tc'][it] + 0.3, 0, 200)
sub = {kx: (vv[it:it + 1] if isinstance(vv, np.ndarray) and vv.ndim >= 1 and len(vv) == len(R['Tc']) else vv) for kx, vv in R.items()}
Xt, _, _ = state(q, cf, sub, Tg)
for i in range(len(Tg) - 1):
    cv2.line(img, Q(*Xt[0, i]), Q(*Xt[0, i + 1]), (0, 0, 200), 1, cv2.LINE_AA)
cv2.drawMarker(img, Q(16.57, 1.83), (0, 140, 255), cv2.MARKER_TRIANGLE_UP, 14, 2)
txt('Main-row section, ground frame (t* = K*), 1 px = 0.11 m.  Dots a..K*: crest top at the stage times (main row)', (sx0, 30), 0.5, th=2)
txt('crest advances with the wave: 20 m/s before jet onset, 16 m/s at t* (76 m from stage a, 40 m from jet onset to t*)', (sx0, 50), 0.45)
txt('coloured dots: lip upper surface at tau = -1.8/-1.4/-1.0/-0.6/-0.2 s (grey = parked on the crest front, not yet released)', (sx0 + 4, Q(0, y0_)[1] + 22), 0.45)
txt('red line: lip-tip path (parked -> 0.6 s launch ramp -> gravity only) ; black: K* at t* ; orange: seat v1', (sx0 + 4, Q(0, y0_)[1] + 42), 0.45)
txt('Cause: two swell groups meet at +-30 deg and their crests add up at the focus at t* (dispersive focusing);', (sx0, Q(0, y0_)[1] + 80), 0.5, th=2)
txt('the crest water then moves faster than the crest (u > c), so the lip leaves the crest front and flies under gravity.', (sx0, Q(0, y0_)[1] + 102), 0.5, th=2)
txt('Body width / tube roof / claws = art (recorded separately, design 28).', (sx0, Q(0, y0_)[1] + 124), 0.5, th=2)
cv2.imwrite(outp, img)
print('wrote', outp)
