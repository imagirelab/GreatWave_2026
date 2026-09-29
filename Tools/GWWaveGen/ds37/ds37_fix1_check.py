# -*- coding: utf-8 -*-
"""設計37 修正1 の確かめ：頭の揺れの形成の動画（座席）が、船の上下に付いていくか。
修正後（unity_fix1/video）と修正前（unity_r1_sway_defect）の ds37_sway_seat_formation_30fps.mp4 を、揺れのない座席の動画
ds37_formation_seat_30fps.mp4 とコマごとに比べる。
  - 揺れが 0 のコマ（i が 30 の倍数、sin(π k) = 0）：画素の差の平均（0 に近いこと）。
  - 全コマ：画素の差の平均と、位相相関（半分の大きさの灰色）で求めた画面のずれ（揺れは左右だけなので、上下のずれ dy は小さいこと）。
結果を ds37_flowlines_metrics.json の fix1_sway_formation へ書き、図 fig/fig_ds37_fix1_sway_formation.png を作る。
py -3.10 -B Tools/GWWaveGen/ds37/ds37_fix1_check.py"""
import hashlib
import json
import math

import cv2
import numpy as np

ROOT = 'G:/Unity/GreatWave_2026_Fresh'
OUT = ROOT + '/Unity/Build/Design/37/flowlines'
PLAIN = OUT + '/unity/video/ds37_formation_seat_30fps.mp4'
NEW = OUT + '/unity_fix1/video/ds37_sway_seat_formation_30fps.mp4'
OLD = OUT + '/unity_r1_sway_defect/ds37_sway_seat_formation_30fps.mp4'
FPS, SWAY, PERIOD = 30, 0.1, 2.0
FIG_T = [4.0, 8.0, 9.0, 10.5, 12.0, 13.5]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def frames(p):
    cap = cv2.VideoCapture(p)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        yield f
    cap.release()


def shift(a, b):
    ga = cv2.cvtColor(cv2.resize(a, (960, 540), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float64)
    gb = cv2.cvtColor(cv2.resize(b, (960, 540), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float64)
    win = cv2.createHanningWindow((960, 540), cv2.CV_64F)
    (dx, dy), resp = cv2.phaseCorrelate(ga, gb, win)
    return 2 * dx, 2 * dy, resp


def main():
    rows = []
    figs = {}
    for i, (fp, fn, fo) in enumerate(zip(frames(PLAIN), frames(NEW), frames(OLD))):
        t = i / FPS
        off = SWAY * math.sin(2 * math.pi * t / PERIOD)
        dn = float(np.abs(fn.astype(np.int16) - fp.astype(np.int16)).mean())
        do = float(np.abs(fo.astype(np.int16) - fp.astype(np.int16)).mean())
        sxn, syn, _ = shift(fp, fn)
        sxo, syo, _ = shift(fp, fo)
        rows.append(dict(i=i, t=round(t, 4), sway_m=off, diff_new=dn, diff_old=do, shift_new=[sxn, syn], shift_old=[sxo, syo]))
        for ft in FIG_T:
            if i == round(ft * FPS):
                figs[ft] = (fp, fo, fn)
    n = len(rows)
    zero = [r for r in rows if r['i'] % FPS == 0]
    late = [r for r in rows if r['t'] >= 8.0]
    res = {
        'what_ja': '頭の揺れの形成の動画（座席、t 0〜14 s、目 ±0.1 m・周期 2 s）を揺れのない座席の形成の動画とコマごとに比べた（修正後・修正前）。'
                   '差は 0〜255 の画素の差の絶対値の平均。ずれは位相相関（960×540 の灰色、ハニングの窓）の画面の px（1920×1080 に直した）。',
        'cause_ja': 'DS37HeadSway.Apply が基準の位置を最初の 1 回だけ読み、動画の繰り返しで揺れが 0 にならない（t = 1/30 s 以降）ため、'
                    't = 1/30 s の位置が、DS30BoatHeave が毎コマ座席のカメラに書く船の上下を上書きしていた。',
        'fix_ja': 'DS37HeadSway：前に置いた位置から動かされていたら（船の上下など）今の位置を基準に読み直す。Restore はほかの部品が書き換えた後の位置に触らない。'
                  'DS37Render.Video：各コマで揺れを外してから時刻を合わせ、そのあと揺れを足す。',
        'frames': n,
        'plain_sha256': sha(PLAIN), 'new_sha256': sha(NEW), 'old_sha256': sha(OLD),
        'zero_offset_frames': len(zero),
        'zero_offset_diff_new_max': max(r['diff_new'] for r in zero),
        'zero_offset_diff_new_mean': float(np.mean([r['diff_new'] for r in zero])),
        'zero_offset_diff_old_max': max(r['diff_old'] for r in zero),
        'diff_new_all_max': max(r['diff_new'] for r in rows),
        'diff_old_t_ge_8_mean': float(np.mean([r['diff_old'] for r in late])),
        'diff_new_t_ge_8_mean': float(np.mean([r['diff_new'] for r in late])),
        'abs_shift_dy_new_max_px': max(abs(r['shift_new'][1]) for r in rows),
        'abs_shift_dy_old_max_px': max(abs(r['shift_old'][1]) for r in rows),
        'abs_shift_dx_new_max_px': max(abs(r['shift_new'][0]) for r in rows),
        'at_t': {f'{r["t"]:.1f}': dict(sway_m=round(r['sway_m'], 5), diff_new=round(r['diff_new'], 3), diff_old=round(r['diff_old'], 3),
                                         shift_new=[round(v, 2) for v in r['shift_new']], shift_old=[round(v, 2) for v in r['shift_old']])
                 for r in rows if r['i'] % 15 == 0},
    }
    # 合否の読み（進行役の判断）：揺れ 0 のコマで差の平均 ≤ 1（符号化の揺らぎの範囲）、全コマで上下のずれ ≤ 2 px
    res['pass'] = bool(res['zero_offset_diff_new_max'] <= 1.0 and res['abs_shift_dy_new_max_px'] <= 2.0)
    res['pass_rule_ja'] = '揺れが 0 のコマ（15 コマ）で差の平均の最大 ≤ 1、全 421 コマで上下のずれの最大 ≤ 2 px（揺れは左右だけ）。既定値、進行役の判断。'
    mp = OUT + '/ds37_flowlines_metrics.json'
    m = json.load(open(mp, encoding='utf-8'))
    m['fix1_sway_formation'] = res
    json.dump(m, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(dict(res, rows=rows), open(OUT + '/unity_fix1/ds37_fix1_sway_compare.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 図：行 = 時刻、列 = 揺れなし・修正前・修正後（各 640×360）
    cw, ch, top = 640, 360, 40
    H = top + len(FIG_T) * (ch + 30)
    img = np.full((max(H, 1080), 1920, 3), 255, np.uint8)
    for k, lab in enumerate(['no sway (formation_seat)', 'sway BEFORE fix (r1, defect)', 'sway AFTER fix (fix1)']):
        cv2.putText(img, lab, (k * cw + 10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    for r, ft in enumerate(FIG_T):
        if ft not in figs:
            continue
        y = top + r * (ch + 30)
        rr = rows[round(ft * FPS)]
        for k, f in enumerate(figs[ft]):
            img[y:y + ch, k * cw:(k + 1) * cw] = cv2.resize(f, (cw, ch), interpolation=cv2.INTER_AREA)
        txt = f't {ft:.1f} s  eye {rr["sway_m"]:+.3f} m  diff vs no-sway: before {rr["diff_old"]:.1f} / after {rr["diff_new"]:.1f}'
        cv2.putText(img, txt, (10, y + ch + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(OUT + '/fig/fig_ds37_fix1_sway_formation.png', img)
    print(json.dumps({k: v for k, v in res.items() if k not in ('at_t', 'what_ja', 'cause_ja', 'fix_ja', 'pass_rule_ja')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
