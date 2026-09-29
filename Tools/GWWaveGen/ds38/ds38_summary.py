# -*- coding: utf-8 -*-
"""設計38 第「輪郭線」部：最小の受入の表（ds38_acceptance.json）。ds38_line_eval.py と評価器（ds30b_tstar_regress.py）の後に回す。

設計38 修正の回（進行役の検査の後の 1 回、Q26）で、納める版は修正の回（unity/）になり、修正1 の出力は unity_fix1/ へ移した。
読む：<out>/ds38_outlines_metrics.json（修正の回＝納める版）、<out>/unity_fix1/ds38_outlines_metrics.json（修正1）、
      <out>/unity/ds38_fix_eval.json・<out>/unity_fix1/ds38_fix_eval.json（ゆるい定義の数え）、<out>/fixr_x*/ds38_fix_eval.json（修正の回の試し）、<out>/unity_r1_seq/ds38_outlines_metrics.json（1 回目の評価）、
      <out>/unity_cand_a/ds38_outlines_metrics.json（候補A、採らない。記録）、評価器の ds30_tstar_regress.json（設計36・設計38・候補A）、
      t* の評価の evidence/metrics.json（142・143・外殻線の内側の線）。
使い方：py -3.10 -B Tools/GWWaveGen/ds38/ds38_summary.py
"""
import json
import os

ROOT = 'G:/Unity/GreatWave_2026_Fresh'
OUT = ROOT + '/Unity/Build/Design/38/outlines'
D36 = ROOT + '/Unity/Build/Design/36/palette/unity'


def load(p):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def flat(v, p=''):
    out = {}
    if isinstance(v, dict):
        for k, x in v.items():
            out.update(flat(x, p + '/' + str(k)))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            out.update(flat(x, p + '[' + str(i) + ']'))
    else:
        out[p] = v
    return out


def regress_diff(a, b):
    if a is None or b is None:
        return None
    fa, fb = flat(a), flat(b)
    skip = ('sha', 'path', 'dir', 'seconds', 'out')
    d = [(k, fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k) and not any(s in k.lower() for s in skip)]
    return {'values_compared': len(fa), 'values_different': len(d), 'differences': d[:40]}


def seq_table(m):
    if m is None:
        return None
    return {n: {'flash': s['flash_clusters'], 'hole': s['hole_clusters'], 'jump': s['jump_clusters'], 'hole_ds37_def': s['hole_ds37_clusters'],
                'by_sheet': s.get('clusters_by_sheet'), 'line_px_median': sorted(s['line_px'])[len(s['line_px']) // 2], 'pass': s['pass']}
            for n, s in m['191']['sequences'].items()}


def acceptance(m):
    mock = m['mock']
    near = m['near']
    return {
        '191_blink_jump_0_over_300_frames': {
            'criterion_ja': '連続 301 コマ（t 2.0〜12.0 s・30 fps、視点 painting・seat・seat_toward_wave）と頭の揺れ（seat_toward_wave t 9 s、目 ±0.1 m・周期 2 s の 301 コマ）で、'
                            '一瞬だけ出た線・一瞬だけ消えた線（出どころが同じ線）・跳びの 10 px 以上の塊が 0',
            'value': seq_table(m), 'verdict': 'pass' if m['191']['pass'] else 'fail'},
        '192_stale_lines_0': {
            'criterion_ja': '同じコマをでたらめな順で描き直した線の画素が連続の描画と 1 画素も違わない（48 コマ）。線の画素のうち面から 4 px より離れた塊が 0（画面の縁から 40 px の帯は除く）',
            'value': {'diff_px': m['192']['total_diff_px'], 'orphan_clusters_inner': m['192']['total_orphan_clusters_inner'], 'orphan_px_inner': m['192']['total_orphan_px_inner'],
                      'orphan_px_all_incl_border': m['192']['total_orphan_px'], 'orphan_clusters_all_incl_border': m['192']['total_orphan_clusters']},
            'verdict': 'pass' if m['192']['pass'] else 'fail'},
        'mock_LR_line_px_diff_lt_10pct': {
            'criterion_ja': 'Mock の両眼（±0.032 m、中心眼をそろえた 2 回の描画）の線の画素の数の差 ÷ 平均 < 10%（両眼の平均 500 px 以上の組）',
            'value': [{k: p[k] for k in ('view', 't', 'L_px', 'R_px', 'rel_diff', 'one_eye_only_frac_L', 'one_eye_only_frac_R', 'pass')} for p in mock['pairs']],
            'max_rel_diff_judged': mock['max_rel_diff_judged'], 'max_one_eye_only_frac': mock['max_one_eye_only_frac'],
            'verdict': 'pass' if mock['pass'] else 'fail'},
        'near_line_not_too_thick_world_cap': {
            'criterion_ja': '座席の向きのまま主役波の最も近い点へ 4・8・16 m まで寄せたカメラ（視野 80°）で、DS38 の線の太さの p95 ≤ 3 px。設計27 の外殻線 v0 の決まり（世界寸法の下限 5 cm）と並べる。'
                            '決まりの上限：押し出し幅 ≤ min(d × 0.0012866, 0.3 m) か d × 1.5 画素の角の大きい方',
            'value': near['probes'], 'verdict': 'pass' if near['pass'] else 'fail'},
    }


def loose_table(fx):
    if fx is None:
        return None
    return {n: {'official': v['official'], 'loose_blink': v['loose']['loose_blink'], 'appear': v['loose']['appear'], 'vanish': v['loose']['vanish'],
                'ds37_hole': v['loose']['ds37_hole'], 'line_px_by_sheet_total': v['line_px_by_sheet_total']} for n, v in fx['seqs'].items()}


def mock_split(ud):
    """Mock の座席の低い視点 t 6 s の線の画素を x < 1440 と x ≥ 1440（目の近くの遮る物の所）に分ける（記録）。"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ds38_line_eval as le
    out = {}
    for e in ('L', 'R'):
        p = ud + '/mock/lines_seat_low_t06.0s_' + e + '.bin'
        if not os.path.exists(p):
            return None
        a = le.read_one(p)
        x = a['idx'] % le.W
        out[e] = {'all': int(len(a)), 'x_lt_1440': int((x < 1440).sum()), 'x_ge_1440': int((x >= 1440).sum())}
    L, R = out['L'], out['R']
    out['rel_diff_x_lt_1440'] = abs(L['x_lt_1440'] - R['x_lt_1440']) / max(0.5 * (L['x_lt_1440'] + R['x_lt_1440']), 1)
    return out


def main():
    m = load(OUT + '/ds38_outlines_metrics.json')
    m1 = load(OUT + '/unity_fix1/ds38_outlines_metrics.json')
    r1 = load(OUT + '/unity_r1_seq/ds38_outlines_metrics.json')
    ca = load(OUT + '/unity_cand_a/ds38_outlines_metrics.json')
    reg36 = load(D36 + '/ds30_tstar_regress.json')
    reg38 = load(OUT + '/unity/ds30_tstar_regress.json')
    reg38f1 = load(OUT + '/unity_fix1/ds30_tstar_regress.json')
    regA = load(OUT + '/unity_cand_a_tv/ds30_tstar_regress.json')
    ev36 = load(D36 + '/t28_claws/t28/evidence/metrics.json')
    ev38 = load(OUT + '/unity/t28_claws/t28/evidence/metrics.json')
    ev38f1 = load(OUT + '/unity_fix1/t28_claws/t28/evidence/metrics.json')
    acc = acceptance(m)
    rec = {
        '142_143_outer_line_precheck_record': {'ds36': {k: ev36['items'][k]['value'] for k in ('142', '143')} if ev36 else None,
                                               'ds38_fix1': {k: ev38f1['items'][k]['value'] for k in ('142', '143')} if ev38f1 else None,
                                               'ds38_fixround': {k: ev38['items'][k]['value'] for k in ('142', '143')} if ev38 else None},
        'outline_interior_record_evaluator': {'ds36': ev36['items']['outline_interior_record']['value']['r01'] if ev36 else None,
                                              'ds38_fix1': ev38f1['items']['outline_interior_record']['value']['r01'] if ev38f1 else None,
                                              'ds38_fixround': ev38['items']['outline_interior_record']['value']['r01'] if ev38 else None,
                                              'note_ja': '評価器は空（主役波・海のどれもない所）から 4 px より内側の線を数えるので、設計38 の値には手前の海（near）の線が入る。'},
        '146_147_claw_lines': '記録のみ・測っていない（爪の線は原画視点では描かない決まりなので、原画との ≤4 px は仕上げ38）',
        'mock_seat_low_t06_split_fixround': mock_split(OUT + '/unity'),
        'mock_seat_low_t06_split_fix1': mock_split(OUT + '/unity_fix1'),
    }
    exps = {}
    for x in ('x1', 'x2', 'x3', 'x4'):
        f = load(OUT + '/fixr_' + x + '/ds38_fix_eval.json')
        if f:
            exps[x] = {'candidate': f.get('candidate'), 'table': loose_table(f)}
    out = {
        'schema': 'GreatWave.DS38.acceptance/2',
        'note_ja': '設計38 修正の回（進行役の検査の後の 1 回、Q26）の後。納める版は修正の回（unity/）。修正1 の版は unity_fix1/（acceptance_after_fix1）。',
        'acceptance_after_fixround': acc,
        'acceptance_after_fix1': acceptance(m1) if m1 else None,
        'loose_191_fixround': loose_table(load(OUT + '/unity/ds38_fix_eval.json')),
        'loose_191_fix1': loose_table(load(OUT + '/unity_fix1/ds38_fix_eval.json')),
        'loose_191_definition_ja': 'ds38_fix_eval.py：loose_blink＝f−1 と f+1 の同じ画素に同じ出どころ（番号だけ）の線があり、f ではどの線も 1 px の内にない 10 px 以上の塊。'
                                   'appear・vanish＝次のコマの線から 5.5 px より遠い線の塊（頭の揺れの組の出入り）。進行役の検査の定義を別のコードで書いたもの。',
        'fixround_experiments': exps,
        'record': rec,
        'regression_plan_2_0': {'ds36_vs_ds38_fixround': regress_diff(reg36, reg38), 'ds36_vs_ds38_fix1': regress_diff(reg36, reg38f1),
                                'ds36_vs_candidate_a': regress_diff(reg36, regA)},
        'first_eval_191': seq_table(r1), 'first_eval_mock_max': r1['mock']['max_rel_diff_judged'] if r1 else None,
        'first_eval_192': {'diff_px': r1['192']['total_diff_px'], 'orphan_px_inner': r1['192'].get('total_orphan_px_inner')} if r1 else None,
        'candidate_a_not_adopted': {'settings_ja': '主役波は幾何シェーダーの表裏の選別なし、near は選別あり＋内積の下限 0.15、爪は選別あり（修正1 の後に測った。採らない）',
                                    '191': seq_table(ca), 'mock_max': ca['mock']['max_rel_diff_judged'] if ca else None,
                                    '192_diff_px': ca['192']['total_diff_px'] if ca else None, 'near': ca['near']['pass'] if ca else None},
    }
    json.dump(out, open(OUT + '/ds38_acceptance.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in acc.items():
        print(k, v['verdict'])
    for k, v in out['regression_plan_2_0'].items():
        print('regression', k, None if v is None else (v['values_compared'], v['values_different']))
    print('mock split', rec['mock_seat_low_t06_split_fixround'])


if __name__ == '__main__':
    main()
