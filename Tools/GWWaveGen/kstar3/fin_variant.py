# quick variant runner: py -3.10 fin_variant.py tag '{"img_rounds":[1000],"loc":4}'
import sys, json, numpy as np
sys.path.insert(0, '.')
import fin_pipeline as FP, candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_check as RC, rubric_measure as RM
tag, cfg = sys.argv[1], json.loads(sys.argv[2])
W = r'G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/final/_work/'
FP.run('fin_params.json', W + 'var_%s.npz' % tag, log=lambda s: None, cfg=cfg)
z = np.load(W + 'var_%s.npz' % tag); A, Y, c = z['A'], z['Y'], z['c']
V1, tgt, fr = C.painting_frame()
g = V1.preview_metrics(fr, tgt, fr.world(c, A, Y), V1.triangles(400, 240), W + '_g_%s.png' % tag, tag)
H = Y.max(1); H0 = H[159]
body = [r for r in range(len(c)) if -5 <= c[r] <= 4 and H[r] >= 0.75 * H0]
lip = [r for r in range(len(c)) if -10 <= c[r] <= 3 and H[r] >= 0.75 * H0]
def m(r): return RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
l075 = max((m(r).get('lip_thick_0p75_m') or 0) for r in lip); l2 = max((m(r).get('lip_thick_2m_m') or 0) for r in lip)
bs = [RM.back_shape(RM.poly_to_segs(A[r], Y[r]), 0.0, m(r)['H'], m(r)['a_top']) for r in body]
Rr = [b['back_R_over_H'] for b in bs]; sh = [b['shell_thick_normal_over_H'][1] for b in bs if b.get('shell_thick_normal_over_H')]
rmin = min(RC.corner_q17(A[r], Y[r], 200)['Rmin_m'] for r in range(len(c)) if -5 <= c[r] <= 3 and H[r] >= 0.5 * H0)
print(tag, json.dumps(cfg), {k: round(g[k]['max_px'], 2) for k in ('78', '130', '131', '132')}, '72p95 %.2f' % g['72']['p95_px'],
      'Rmin %.2f l075 %.2f l2 %.2f backR %.2f-%.2f shell %.2f-%.2f' % (rmin, l075, l2, min(Rr), max(Rr), min(sh), max(sh)), flush=True)
