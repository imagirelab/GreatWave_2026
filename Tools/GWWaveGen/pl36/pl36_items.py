# 仕上げ36：t28 の組（爪なし t28_white・爪あり t28_claws）の評価の metrics.json から、色区の項目（73〜270）と 175 の残る色区の数を抜き出す（記録）。
import sys, json, os
def load(run, s):
    p = os.path.join(run, s, 't28', 'evidence', 'metrics.json')
    return json.load(open(p, encoding='utf-8'))
def items(run):
    out = {}
    for s in ['t28_white', 't28_claws']:
        d = load(run, s)
        it = d['items'] if 'items' in d else d
        r = {}
        for k in ['73', '77', '79', '118', '120', '133', '134', '175', '263', '270', '265', '266', '267']:
            if k not in it: continue
            v = it[k].get('value', it[k])
            if k == '175':
                r[k] = {'regions_total': v['regions_total'], 'regions_retained': v['regions_retained'], 'regions_retained_all_pixels': v['regions_retained_all_pixels'],
                        'boundary_max_px': v['boundary_max_px'], 'boundary_by_class_max': {c: vv.get('max_px') for c, vv in v['boundary_by_class'].items()},
                        'excluding_lost_max_px': v['record_excluding_lost_regions']['boundary_max_px']}
            else:
                r[k] = {kk: vv for kk, vv in (v.items() if isinstance(v, dict) else []) if isinstance(vv, (int, float, str)) and kk in ('max_px', 'boundary_max_px', 'dE00', 'value', 'verdict', 'mean_dE00', 'max_dE00', 'bands')}
        out[s] = r
    return out
if __name__ == '__main__':
    res = {}
    for a in sys.argv[1:]:
        if a.startswith('--out='): continue
        n, p = a.split('=', 1); res[n] = items(p)
    o = [a for a in sys.argv[1:] if a.startswith('--out=')]
    if o: json.dump(res, open(o[0][6:], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for n, r in res.items():
        for s in r: print(n, s, '175', json.dumps(r[s].get('175')))
