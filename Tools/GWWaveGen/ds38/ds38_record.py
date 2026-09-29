# -*- coding: utf-8 -*-
# 設計38 の記録の道具（記録の部）。作る部の出力（Git 対象外の Unity/Build/Design/38/outlines/）から、証拠 Docs/Evidence/Design/38/ を作る：
#   - 作る部の出力とコードが ds38_run.json の SHA-256 のままかを確かめる（違えば止まる）
#   - 記録の照合（作る部の評価のコードを使わない）：t* の原画視点の画像の違う画素の数（設計36・修正1・修正の回）、原画視点の連続 301 コマで
#     主役波の線の画素が修正1 と違う所が near の線と重なる所だけか、頭の揺れの 301 コマの線の出入り（検査の定義：次のコマの線から 5.5 px より
#     遠い 10 px 以上の塊）を 1 回目の評価・修正1・確かめ・候補A・修正の回で数え直し、出入りした線の出どころ（シート・列・行）を書く
#   - 図（1920×1080）・動画（5 MB 以下）・JSON を写し、metrics.json（バックログの項目 → 値 → 合格／不合格／記録のみ）と run.json を書く
# 値はすべて、ここで読んだファイルから取る（作る部の値は書き換えない）。
# 使い方：py -3.10 -B Tools/GWWaveGen/ds38/ds38_record.py（約 1〜2 分。ほかの重い numpy の処理と同時に回さない）
import hashlib
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
assert (ROOT / 'AGENTS.md').exists(), ROOT
B38 = ROOT / 'Unity/Build/Design/38'
OL = B38 / 'outlines'
IND = B38 / 'indep_check'
EV = ROOT / 'Docs/Evidence/Design/38'
EV36 = ROOT / 'Docs/Evidence/Design/36'
B36 = ROOT / 'Unity/Build/Design/36/palette'
W, H = 1920, 1080
MB5 = 5 * 1024 * 1024
SEQ_DT = np.dtype([('idx', '<u4'), ('id', '<u2'), ('c', '<u2'), ('r', '<u2'), ('d', '<u2')])
SHEETS = {1: 'hero', 2: 'near', 4: 'claws'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def jload(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def mtime(p):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p)))


def stop(msg):
    print('止める：' + msg)
    sys.exit(1)


def read_seq(p):
    """DS38Render の線の表（コマごとに int32 の n、続いて n 個 × 12 バイト）を読む。"""
    b = open(p, 'rb').read()
    off, out = 0, []
    while off < len(b):
        n = int(np.frombuffer(b, '<i4', 1, off)[0])
        off += 4
        out.append(np.frombuffer(b, SEQ_DT, n, off))
        off += 12 * n
    return out


def id_image(fr):
    m = np.zeros(H * W, np.uint8)
    m[fr['idx']] = fr['id']
    return m.reshape(H, W)


# ---- 1. 作る部の出力とコードが ds38_run.json の SHA-256 のままか（違えば止まる）
run38 = jload(OL / 'ds38_run.json')
checked = 0
for group in ('code_sha256', 'outputs_sha256', 'inputs_sha256'):
    for k, v in run38[group].items():
        p = ROOT / k
        if not p.exists():
            stop('見つからない ' + k)
        if sha(p) != v:
            stop('SHA-256 が ds38_run.json と違う ' + k)
        checked += 1
print('ds38_run.json の SHA-256 の照合', checked, '件、すべて同じ')

acc = jload(OL / 'ds38_acceptance.json')
rep = jload(OL / 'unity/ds38_render_report.json')
fixev = jload(OL / 'unity/ds38_fix_eval.json')
m36 = jload(EV36 / 'metrics.json')

# ---- 2. 評価器の出力（計画 §2.0）が設計36 と同じファイルか
reg = {}
for name, p in (('ds38_fixround', OL / 'unity/ds30_tstar_regress.json'), ('ds38_fix1', OL / 'unity_fix1/ds30_tstar_regress.json'),
                ('ds36_build', B36 / 'unity/ds30_tstar_regress.json'), ('ds36_evidence', EV36 / 'ds36_tstar_regress.json')):
    reg[name] = {'path': rel(p), 'sha256': sha(p)}
reg_identical = len({v['sha256'] for v in reg.values()}) == 1
if not reg_identical:
    stop('評価器の出力が設計36 と違う')

# ---- 3. 記録の照合（作る部の評価のコードを使わない）
xc = {}
# 3a. t* の原画視点の画像（爪あり）：違う画素（RGB のどれかが違う）の数
imgs = {'ds36': B36 / 'unity/t28_claws/t28/render/af28r01_painting.png',
        'ds38_fix1': OL / 'unity_fix1/t28_claws/t28/render/af28r01_painting.png',
        'ds38_fixround': OL / 'unity/t28_claws/t28/render/af28r01_painting.png'}
arr = {k: np.asarray(Image.open(p).convert('RGB')).astype(np.int16) for k, p in imgs.items()}
xc['tstar_painting_diff_px'] = {
    'definition_ja': 'RGB の 3 つのどれかが違う画素の数（1920×1080。爪あり t28_claws の af28r01_painting.png）',
    'files_sha256': {k: sha(p) for k, p in imgs.items()},
    'ds36_vs_fix1': int((np.abs(arr['ds36'] - arr['ds38_fix1']).max(2) > 0).sum()),
    'ds36_vs_fixround': int((np.abs(arr['ds36'] - arr['ds38_fixround']).max(2) > 0).sum()),
    'fix1_vs_fixround': int((np.abs(arr['ds38_fix1'] - arr['ds38_fixround']).max(2) > 0).sum()),
}
del arr

# 3b. 原画視点の連続 301 コマ：主役波（番号 1）の線の画素が修正1 と違う所は near（番号 2）の線と重なる所だけか
fa = read_seq(OL / 'unity/l191/l191_form_painting.bin')
fb = read_seq(OL / 'unity_fix1/l191/l191_form_painting.bin')
lost = added = lost_nn = added_nn = 0
for x, y in zip(fa, fb):
    hx, hy = set(x['idx'][x['id'] == 1].tolist()), set(y['idx'][y['id'] == 1].tolist())
    near = set(x['idx'][x['id'] == 2].tolist()) | set(y['idx'][y['id'] == 2].tolist())
    lo, ad = hy - hx, hx - hy
    lost += len(lo)
    added += len(ad)
    lost_nn += len(lo - near)
    added_nn += len(ad - near)
xc['painting_hero_lines_fix1_vs_fixround'] = {
    'frames': len(fa), 'hero_px_lost': lost, 'hero_px_added': added, 'hero_px_lost_not_on_near_line': lost_nn,
    'hero_px_added_not_on_near_line': added_nn,
    'note_ja': '301 コマの和。near の線の画素（どちらかの版）と重ならない所で主役波の線の画素が違うのは lost/added_not_on_near_line。'}
xc['near_line_px_301_frames'] = {}
for tag in ('unity_fix1', 'unity'):
    d = {}
    for s in ('form_painting', 'form_seat', 'form_seat_toward_wave'):
        fr = read_seq(OL / tag / ('l191/l191_%s.bin' % s))
        d[s] = int(sum(int((x['id'] == 2).sum()) for x in fr))
    xc['near_line_px_301_frames']['fix1' if tag == 'unity_fix1' else 'fixround'] = d
del fa, fb

# 3c. 頭の揺れの 301 コマの線の出入り（検査の定義の数え直し。出どころも書く）
T = 5.5
runs = (('first_eval_r1', 'unity_r1_seq'), ('fix1', 'unity_fix1'), ('verify_tau0', 'unity_verify'), ('candidate_a', 'unity_cand_a'), ('fixround', 'unity'))
sway = {}
cells = {'cols212_216_rows124_131': (212, 216, 124, 131), 'cols195_198_rows106_111': (195, 198, 106, 111)}
for name, tag in runs:
    q = read_seq(OL / tag / 'l191/l191_sway_seat_toward_wave_t09.bin')
    prev_im = id_image(q[0])
    prev_dt = cv2.distanceTransform((prev_im == 0).astype(np.uint8), cv2.DIST_L2, 5)
    counts = {v: 0 for v in SHEETS.values()}
    groups = {}
    for f in range(len(q) - 1):
        im = id_image(q[f + 1])
        dtm = cv2.distanceTransform((im == 0).astype(np.uint8), cv2.DIST_L2, 5)
        for sid, sname in SHEETS.items():
            for kind, mask, src in (('appear', (im == sid) & (prev_dt > T), f + 1), ('vanish', (prev_im == sid) & (dtm > T), f)):
                n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
                for k in range(1, n):
                    if st[k, 4] < 10:
                        continue
                    counts[sname] += 1
                    ys, xs = np.nonzero(lab == k)
                    fr = q[src]
                    sel = np.isin(fr['idx'], ys * W + xs)
                    cols, rows = fr['c'][sel] / 10.0, fr['r'][sel] / 10.0
                    key = '%s (%d, %d)' % (sname, int(round(cen[k, 0] / 10) * 10), int(round(cen[k, 1] / 10) * 10))
                    g = groups.setdefault(key, {'events': 0, 'frames': [], 'px': [], 'col': [1e9, -1e9], 'row': [1e9, -1e9]})
                    g['events'] += 1
                    g['frames'].append(f)
                    g['px'].append(int(st[k, 4]))
                    if len(cols):
                        g['col'] = [min(g['col'][0], float(cols.min())), max(g['col'][1], float(cols.max()))]
                        g['row'] = [min(g['row'][0], float(rows.min())), max(g['row'][1], float(rows.max()))]
        prev_im, prev_dt = im, dtm
    for g in groups.values():
        g['frames'] = [min(g['frames']), max(g['frames'])]
        g['px'] = [min(g['px']), max(g['px'])]
        g['col'] = [round(v, 1) for v in g['col']]
        g['row'] = [round(v, 1) for v in g['row']]
    per_cell = {}
    for cname, (c0, c1, r0, r1) in cells.items():
        per_cell[cname] = []
        for f in range(24, 36):
            x = q[f]
            h = x[x['id'] == 1]
            cc, rr = h['c'] / 10.0, h['r'] / 10.0
            per_cell[cname].append(int(((cc >= c0) & (cc <= c1) & (rr >= r0) & (rr <= r1)).sum()))
    sway[name] = {'dir': rel(OL / tag), 'bin_sha256': sha(OL / tag / 'l191/l191_sway_seat_toward_wave_t09.bin'),
                  'appear_vanish_clusters': counts, 'by_place': groups, 'hero_px_from_cells_frames_24_35': per_cell}
    print('頭の揺れ', name, counts, {k: v['events'] for k, v in groups.items()})
xc['sway_appear_vanish_recount'] = {
    'definition_ja': '進行役の検査の定義：頭の揺れの連続 301 コマ（座席から波の方向 t 9 s、目 ±0.1 m・周期 2 s）で、次のコマ（または前のコマ）のどの線からも 5.5 px より遠い線の、8 近傍で 10 px 以上の塊を、出た（appear）・消えた（vanish）として数えた。by_place は画面の位置（10 px に丸めた塊の中心）ごと、col・row はその塊の線の出どころ（主役波の列・行）。hero_px_from_cells は、出どころの列・行が範囲に入る主役波の線の画素の数（コマ 24〜35）',
    'runs': sway}

# ---- 4. 図（1920×1080）
EV.mkdir(parents=True, exist_ok=True)
figs = []
fig_list = [(OL / 'fig' / n, n) for n in (
    'fig_ds38_fixround_before_after.png', 'fig_ds38_fixround_limits.png', 'fig_ds38_before_after.png', 'fig_ds38_painting_mask.png',
    'fig_ds38_claws_seat.png', 'fig_ds38_seam.png', 'fig_ds38_near.png', 'fig_ds38_mock.png', 'fig_ds38_mock_limit_seat_low_t06.png',
    'fig_ds38_191.png')]
fig_list.append((OL / 'unity_fix1/fig_fix1/fig_ds38_191_limit_spikes.png', 'fig_ds38_fix1_spikes.png'))
for src, dname in fig_list:
    im = Image.open(src)
    if im.size != (W, H):
        stop('1920×1080 でない ' + rel(src))
    dst = EV / dname
    shutil.copyfile(src, dst)
    figs.append({'src': rel(src), 'dst': rel(dst), 'bytes': os.path.getsize(dst), 'sha256': sha(dst)})

# ---- 5. 動画（修正の回の 4 本）
videos = []
for name in ('ds38_formation_painting_30fps.mp4', 'ds38_formation_seat_30fps.mp4', 'ds38_formation_seat_toward_wave_30fps.mp4',
             'ds38_sway_seat_toward_wave_t09_30fps.mp4'):
    src = OL / 'unity/video' / name
    if os.path.getsize(src) > MB5:
        stop('5 MB を超える ' + name)
    dst = EV / name
    shutil.copyfile(src, dst)
    cap = cv2.VideoCapture(str(dst))
    info = {'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': round(cap.get(cv2.CAP_PROP_FPS), 3), 'frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
    cap.release()
    videos.append(dict(src=rel(src), dst=rel(dst), bytes=os.path.getsize(dst), sha256=sha(dst), **info))

# ---- 6. JSON の写し（評価器の出力は設計36 の証拠 ds36_tstar_regress.json と同じファイルなので写さない）
copies = []
for src, dname in ((OL / 'ds38_acceptance.json', 'ds38_acceptance.json'), (OL / 'ds38_outlines_metrics.json', 'ds38_outlines_metrics.json'),
                   (OL / 'ds38_run.json', 'ds38_run.json'), (OL / 'unity/ds38_fix_eval.json', 'ds38_fix_eval.json')):
    dst = EV / dname
    shutil.copyfile(src, dst)
    copies.append({'src': rel(src), 'dst': rel(dst), 'bytes': os.path.getsize(dst), 'sha256': sha(dst)})

# ---- 7. metrics.json
a = acc['acceptance_after_fixround']
a1 = acc['acceptance_after_fix1']
readme = (OL / 'README_interface.txt').read_text(encoding='utf-8')
x5_line = [l.strip() for l in readme.splitlines() if l.strip().startswith('X5 ')]
started = (OL / '_started.txt').read_text(encoding='utf-8').strip()
started_fix = (OL / '_fixround_started.txt').read_text(encoding='utf-8').strip()
log = (OL / 'unity/logs/unity_ds38o_fixround.log').read_text(encoding='utf-8', errors='replace')
log_date = [l for l in log.splitlines() if l.startswith('Date: ')][:1]
ind_files = [IND / f for f in os.listdir(IND) if (IND / f).is_file()]
mats = {m_['name']: {k: m_[k] for k in ('pushBack', 'pushPaint', 'facingMode', 'backOnly', 'facingMin', 'minPx', 'maxWidth', 'lineAngle')} for m_ in rep['materials']}


def verdict(v):
    return {'pass': '合格', 'fail': '不合格'}.get(v, v)


metrics = {
    'schema': 'GreatWave.Design38.metrics/1',
    'number': '設計38：必要な輪郭線（片眼欠け、線幅、奥行き、頭の移動時のちらつき）',
    'evidence_kind_ja': 'Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と numpy/OpenCV。HMD 実機ではない（PS VR2 の H3・H6 は保留）。Mock の両眼は座席のカメラを ±0.032 m ずらした 2 回の PC の描画で、PS VR2 の立体視（SPI）の描画ではない。頭の揺れは座席のカメラを左右へずらした PC の描画。',
    'delivered_version_ja': '納める版は修正の回（Q26 の 1 回）の出力 Unity/Build/Design/38/outlines/unity/。修正1 の版は unity_fix1/。',
    'acceptance': {
        '191_blink_jump_0': {'criterion_ja': a['191_blink_jump_0_over_300_frames']['criterion_ja'],
                             'value_fixround': a['191_blink_jump_0_over_300_frames']['value'],
                             'value_fix1': a1['191_blink_jump_0_over_300_frames']['value'],
                             'first_eval': acc['first_eval_191'],
                             'verdict': verdict(a['191_blink_jump_0_over_300_frames']['verdict'])},
        '192_stale_lines_0': {'criterion_ja': a['192_stale_lines_0']['criterion_ja'], 'value_fixround': a['192_stale_lines_0']['value'],
                              'value_fix1': a1['192_stale_lines_0']['value'], 'verdict': verdict(a['192_stale_lines_0']['verdict'])},
        'mock_LR_line_px_diff_lt_10pct': {'criterion_ja': a['mock_LR_line_px_diff_lt_10pct']['criterion_ja'],
                                          'pairs_fixround': a['mock_LR_line_px_diff_lt_10pct']['value'],
                                          'max_rel_diff_judged_fixround': a['mock_LR_line_px_diff_lt_10pct']['max_rel_diff_judged'],
                                          'max_rel_diff_judged_fix1': a1['mock_LR_line_px_diff_lt_10pct']['max_rel_diff_judged'],
                                          'seat_low_t06_split_fixround': acc['record']['mock_seat_low_t06_split_fixround'],
                                          'seat_low_t06_split_fix1': acc['record']['mock_seat_low_t06_split_fix1'],
                                          'verdict': verdict(a['mock_LR_line_px_diff_lt_10pct']['verdict'])},
        'near_lines_not_too_thick': {'criterion_ja': a['near_line_not_too_thick_world_cap']['criterion_ja'],
                                     'probes_fixround': a['near_line_not_too_thick_world_cap']['value'],
                                     'verdict': verdict(a['near_line_not_too_thick_world_cap']['verdict'])},
    },
    'loose_191': {'definition_ja': acc['loose_191_definition_ja'], 'fixround': acc['loose_191_fixround'], 'fix1': acc['loose_191_fix1']},
    'record_only': {
        '142_143': acc['record']['142_143_outer_line_precheck_record'],
        '146_147': acc['record']['146_147_claw_lines'],
        'outline_interior_record_evaluator': acc['record']['outline_interior_record_evaluator'],
        '195_198': '測っていない（仕上げ38）',
    },
    'regression_plan_2_0': {
        'values': acc['regression_plan_2_0'],
        'regress_json_identical_to_ds36': reg_identical, 'regress_json': reg,
        'ds36_values_t28_claws': m36['regression_plan_2_0']['t28_claws'],
        'note_ja': '原画視点の t* の画像は設計36 と違う（線を変えた）ので評価器を回し直した（爪あり t28_claws・爪なし t28_white）。出力の ds30_tstar_regress.json は設計36 の出力と SHA-256 まで同じ（112 個の値がすべて同じ）。',
    },
    'fix_rounds': {
        'used': 1, 'limit_q26': 1,
        'note_ja': '作る部の修正1（06:05〜06:11）は進行役の検査の前の作る部の中の直し。Q26 の 1 回は進行役の検査の後の「修正の回」（06:53〜）。作る部の修正1 の後の候補A は測っただけで採っていない。',
        'fixround_experiments': {k: v['candidate'] for k, v in acc['fixround_experiments'].items()},
        'fixround_experiment_tables': acc['fixround_experiments'],
        'x5_from_readme_ja': x5_line,
        'adopted_materials': mats,
        'candidate_a_not_adopted': acc['candidate_a_not_adopted'],
    },
    'recorder_crosscheck': dict(xc, builder_sha256_checked=checked),
    'backlog': {
        '191': {'value': '連続 301 コマ × 3 視点と頭の揺れで、一瞬だけ出た線・一瞬だけ消えた線・跳びの塊 原画視点 2・0・17、座席 0・3・4、座席から波の方向 0・2・6、頭の揺れ 0・0・5（修正の回）', 'verdict': '不合格（限界として仕上げ30・38 へ。Q26）'},
        '192': {'value': 'でたらめな順の描き直し 48 コマの差 0 画素、面から 4 px より離れた線の塊 0（縁の帯 40 px を除く）', 'verdict': '合格'},
        'mock_LR_lt_10pct': {'value': '判定した 11 組のうち 10 組が 7.7% 以下、座席の低い視点 t 6 s が 17.3%（x < 1440 では 0.3%）', 'verdict': '不合格（1 組。限界として仕上げ38 へ。Q26）'},
        'near_width_world_cap': {'value': '4・8 m で線の太さ p95 2.8 px（設計27 の決まりでは 8.4・4.4 px）', 'verdict': '合格'},
        '142_143': {'value': '線あり 1.0・0.974、中心のずれ p95 6.046・6.396 px（設計36 と同じ）', 'verdict': '記録のみ'},
        '146_147': {'value': '測っていない（爪の線は原画視点では描かない決まり）', 'verdict': '記録のみ（仕上げ38）'},
        'plan_2_0_regression': {'value': '評価器の 112 個の値が設計36 と同じ', 'verdict': '合格（後退なし）'},
    },
    'hmd': 'PS VR2 の H3・H6 は保留（導入は利用者の手。Q24）。Mock の両眼と頭の揺れは PC の描画。SPI の立体視（幾何シェーダーを含む）と Play モードは確かめていない。',
    'time': {
        'box_q26_h': 4,
        'started_txt': started, 'fixround_started_txt': started_fix,
        'file_times': {
            'fix1_render_report': mtime(OL / 'unity_fix1/ds38_render_report.json'),
            'fix1_readme': mtime(OL / 'unity_fix1/README_interface.txt'),
            'indep_check_first': min(mtime(p) for p in ind_files),
            'indep_check_last': max(mtime(p) for p in ind_files),
            'fixround_unity_log_date_utc': log_date,
            'fixround_render_report': mtime(OL / 'unity/ds38_render_report.json'),
            'fixround_regress': mtime(OL / 'unity/ds30_tstar_regress.json'),
            'fixround_metrics': mtime(OL / 'ds38_outlines_metrics.json'),
            'fixround_fix_eval': mtime(OL / 'unity/ds38_fix_eval.json'),
            'fixround_acceptance': mtime(OL / 'ds38_acceptance.json'),
            'fixround_x5_render_report': mtime(OL / 'fixr_x5/ds38_render_report.json'),
            'readme': mtime(OL / 'README_interface.txt'),
            'run_builder': mtime(OL / 'ds38_run.json'),
            'materials': {n: mtime(ROOT / ('Unity/Assets/GreatWave/Design38/Materials/%s.mat' % n)) for n in ('DS38_Outline_hero', 'DS38_Outline_near', 'DS38_Outline_claws')},
        },
        'unity_seconds_fixround': run38['unity_seconds'],
        'record_run': time.strftime('%Y-%m-%d %H:%M:%S'),
    },
}
with open(EV / 'metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)

# ---- 8. run.json
code = dict(run38['code_sha256'])
code['Tools/GWWaveGen/ds38/ds38_record.py'] = sha(Path(__file__).resolve())
scene = ROOT / 'Unity/Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity'
run = {
    'schema': 'GreatWave.Design38.run/1',
    'commands': run38['commands'] + ['記録：py -3.10 -B Tools/GWWaveGen/ds38/ds38_record.py（約 1〜2 分）'],
    'environment': dict(run38['tools'], pillow=Image.__version__, python_record=platform.python_version(), numpy_record=np.__version__, opencv_record=cv2.__version__),
    'code_sha256': code,
    'scene': {'path': rel(scene), 'sha256': sha(scene), 'render_report_scene38Sha256': rep['scene38Sha256']},
    'inputs_sha256': run38['inputs_sha256'],
    'protected_files': run38['protected_files'],
    'protectedUnchanged': bool(run38['protected_unchanged']),
    'unity_seconds_fixround': run38['unity_seconds'],
    'other_runs': run38['other_runs'],
    'verify_tau0_l191_identical_to_fix1': run38['verify_tau0_l191_identical_to_fix1'],
    'fixround_mask_identical_to_fix1': run38['fixround_mask_identical_to_fix1'],
    'builder_outputs_sha256': run38['outputs_sha256'],
    'builder_sha256_checked': checked,
    'regress_json': reg,
    'figures': figs,
    'videos': videos,
    'copies': copies,
    'indep_check_files_sha256': {rel(p): sha(p) for p in sorted(ind_files)},
    'not_kept_note_ja': run38['not_kept_note_ja'],
    'not_used_ja': '参照モデル・利用者の解算・写真のフォルダー・Blender・Houdini は使っていない。爪形分析のフォルダーは、作る部も検査もこの記録の道具も開いていない（コミットの一覧の点検で、ファイルの大きさと SHA-256 を読み取りのみで照合しただけ）。',
    'record_run': metrics['time']['record_run'],
}
with open(EV / 'run.json', 'w', encoding='utf-8') as f:
    json.dump(run, f, ensure_ascii=False, indent=1)

print('図', len(figs), '動画', len(videos), '写し', len(copies))
for v in videos:
    print(' ', v['dst'], v['bytes'], v['frames'])
print('t* の違う画素', json.dumps(xc['tstar_painting_diff_px'], ensure_ascii=False)[-120:])
print('原画視点の主役波の線', json.dumps(xc['painting_hero_lines_fix1_vs_fixround'], ensure_ascii=False))
print('near の線の画素', json.dumps(xc['near_line_px_301_frames'], ensure_ascii=False))
print('証拠', rel(EV))
