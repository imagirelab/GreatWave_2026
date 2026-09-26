# default global time warp tau(t) (physical s, rel. t*) vs experience time t (s). 設計26 draft, default pending the user.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/timewarp_table.py   （前稿の旧既定の表。記録のみ）→ Unity/Build/Design/26/feas/timewarp_table.json
import os, json, numpy as np
import ds26_paths as DP
def S(x): x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)
def rate(t):
    if t < 8.0: return 1.0
    if t < 12.0: return 1.0 - S((t - 8.0) / 4.0)
    if t < 14.0: return 0.0
    if t < 16.0: return S((t - 14.0) / 2.0)
    return 1.0
ts = np.arange(0, 18.0 + 1e-9, 1e-4)
r = np.array([rate(t) for t in ts])
tau = np.concatenate([[0], np.cumsum((r[1:] + r[:-1]) / 2 * 1e-4)])
tau = tau - tau[np.argmin(np.abs(ts - 12.0))]
ev = {'pre-roll start': None, 'a (round crest)': -3.9, 'b (sharp crest, 2nd peak)': -3.3, 'c (face vertical, jet onset, first white)': -2.4,
      'slow-down starts': -2.0, 'd (overhang >= 0.1H)': -1.8, 'main row jet onset': -2.2, 'tip apex (~2 m above crest)': -1.4, 'farthest curled row jet onset (c=-29.5 m)': -0.73, 't* = K*': 0.0,
      'lip tip passes over seat (9.0 m high)': 0.22, 'wave face reaches seat': 0.30, 'lip tip impact (p5)': 0.45, 'lip tip impact (p50)': 0.66, 'lip tip impact (p95)': 0.74, 'collapse end': 3.0}
out = {'tau_at_t0': float(tau[0]), 'tau_at_t18': float(tau[-1]), 'events': {}}
for k, v in ev.items():
    if v is None:
        out['events'][k] = dict(tau=float(tau[0]), t=0.0); continue
    if v == 0.0:
        out['events'][k] = dict(tau=0.0, t=12.0); continue
    i = np.argmin(np.abs(tau - v)) if v < 0 else np.where(tau >= v - 1e-9)[0][0]
    out['events'][k] = dict(tau=v, t=round(float(ts[i]), 2))
for tt in (0, 2, 4, 6, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18):
    out.setdefault('grid', {})[str(tt)] = round(float(tau[np.argmin(np.abs(ts - tt))]), 3)
json.dump(out, open(os.path.join(DP.outdir(DP.OUT_FEAS), 'timewarp_table.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False); print(json.dumps(out, indent=1, ensure_ascii=False))
