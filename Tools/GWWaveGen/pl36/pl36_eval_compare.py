# 仕上げ36：評価器 23 の 4 組（線あり・なし × 爪あり・なし）の項目ごとの値と判定を、前（仕上げ35＝仕上げ33修正01 と同じ値）と後で並べる（記録）。
import sys, json, os
CONDS = ['off_line', 'off_line_noclaws', 'off_noline', 'off_noline_noclaws']
def load(run, c):
    return json.load(open(os.path.join(run, 'eval23', c, 'metrics.json'), encoding='utf-8'))['items']
def flat(o, pre=''):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('render_lab', 'truth_lab', 'pixels', 'threshold', 'backlog', 'worst_xy'): continue
            out.update(flat(v, pre + '/' + str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            key = v.get('target', i) if isinstance(v, dict) else i
            out.update(flat(v, pre + '[' + str(key) + ']'))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        out[pre] = o
    elif isinstance(o, str) and pre.endswith('verdict'):
        out[pre] = o
    return out
def scalar(v):
    if isinstance(v, dict):
        for k in ('value', 'max_px', 'p95_px', 'dE00', 'mean_dE00'):
            if k in v and isinstance(v[k], (int, float)): return k, v[k]
        for k, vv in v.items():
            if isinstance(vv, (int, float)) and not isinstance(vv, bool): return k, vv
    return None, None
def main():
    before, after, out = sys.argv[1], sys.argv[2], sys.argv[3]
    res = {}
    for c in CONDS:
        b, a = load(before, c), load(after, c)
        rows = {}
        for k in a:
            vb, va = b.get(k, {}), a[k]
            kb, sb = scalar(vb.get('value', vb)) if isinstance(vb, dict) else (None, None)
            ka, sa = scalar(va.get('value', va)) if isinstance(va, dict) else (None, None)
            fb, fa = flat(vb), flat(va)
            diff = {kk: [fb.get(kk), fa.get(kk)] for kk in sorted(set(fb) | set(fa)) if fb.get(kk) != fa.get(kk)}
            rows[k] = {'measure': ka, 'before': sb, 'after': sa, 'verdict_before': vb.get('verdict') if isinstance(vb, dict) else None,
                       'verdict_after': va.get('verdict') if isinstance(va, dict) else None, 'diff': diff}
        cnt = lambda key: {v: sum(1 for r in rows.values() if r[key] == v) for v in set(r[key] for r in rows.values())}
        res[c] = {'items': rows, 'counts_before': cnt('verdict_before'), 'counts_after': cnt('verdict_after'),
                  'changed': [k for k, r in rows.items() if r['diff'] or r['verdict_before'] != r['verdict_after']]}
        print(c, 'before', res[c]['counts_before'], 'after', res[c]['counts_after'], 'changed', res[c]['changed'])
        for k in res[c]['changed']:
            print('   ', k, rows[k]['verdict_before'], '->', rows[k]['verdict_after'], {kk: v for kk, v in list(rows[k]['diff'].items())[:8] if 'command' not in kk and 'sha' not in kk})
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
main()
