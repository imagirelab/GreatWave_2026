# -*- coding: utf-8 -*-
# 設計37 の記録の道具（記録の部）。作る部の出力（Git 対象外の Unity/Build/Design/37/flowlines/）と、進行役の独立の検査の写し
# （Git 対象外の Unity/Build/Design/37/indep_check/）から、証拠 Docs/Evidence/Design/37/ を作る：
#   - 図を 1920×1080 に収める（修正1 の縦長の図は上下 2 枚に分ける）、頭の揺れの動画 3 本（5 MB 以下）と JSON を写す
#   - metrics.json（バックログの項目 → 値 → 合格／不合格／記録のみ）と run.json（コマンド、道具の版、入出力とコードの SHA-256）を書く
# 値はすべて、ここで読んだファイルから取る（作る部の値は書き換えない）。作る部の出力とコードの SHA-256 が ds37_run.json と違えば止まる。
# 使い方：py -3.10 -B Tools/GWWaveGen/ds37/ds37_record.py（約 10 秒）
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
B37 = ROOT / 'Unity/Build/Design/37'
FL = B37 / 'flowlines'
IND = B37 / 'indep_check'
EV = ROOT / 'Docs/Evidence/Design/37'
EV36 = ROOT / 'Docs/Evidence/Design/36'
W, H = 1920, 1080
MB5 = 5 * 1024 * 1024


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


# ---- 1. 作る部の出力とコードが ds37_run.json の SHA-256 のままかを確かめる（違えば止まる）
run37 = jload(FL / 'ds37_run.json')
checked = 0
for group in ('outputs_sha256', 'code_sha256'):
    for k, v in run37[group].items():
        p = ROOT / k
        if not p.exists():
            stop('見つからない ' + k)
        if sha(p) != v:
            stop('SHA-256 が ds37_run.json と違う ' + k)
        checked += 1
print('ds37_run.json の SHA-256 の照合', checked, '件、すべて同じ')

m = jload(FL / 'ds37_flowlines_metrics.json')
m36 = jload(EV36 / 'metrics.json')

# ---- 2. 設計36 と同じファイルであることの照合（原画視点 t*、形成の動画 2 本）
same36 = {}
pairs36 = {
    'painting_tstar': (FL / 'unity/check/ds37_painting_tstar.png', ROOT / 'Unity/Build/Design/36/palette/unity/t28_claws/t28/render/af28r01_painting.png'),
    'formation_painting_video': (FL / 'unity/video/ds37_formation_painting_30fps.mp4', EV36 / 'ds36_palette_painting_30fps.mp4'),
    'formation_seat_video': (FL / 'unity/video/ds37_formation_seat_30fps.mp4', EV36 / 'ds36_palette_seat_30fps.mp4'),
}
for k, (a, b) in pairs36.items():
    ha, hb = sha(a), sha(b)
    same36[k] = {'ds37': rel(a), 'ds36': rel(b), 'sha256': ha, 'identical': ha == hb}
    if ha != hb:
        stop('設計36 と違う ' + k)

# 修正1 の描き直しで、頭の揺れの静止画（色と面の座標）が修正の前と同じか（数え直し）
sw_a, sw_b = FL / 'unity/sway', FL / 'unity_fix1/sway'
fa, fb = sorted(os.listdir(sw_a)), sorted(os.listdir(sw_b))
sway_same = sum(1 for f in fa if f in fb and sha(sw_a / f) == sha(sw_b / f))
sway_fix1 = {'files_before': len(fa), 'files_after': len(fb), 'byte_identical': sway_same}

# ---- 3. 図（1920×1080）
EV.mkdir(parents=True, exist_ok=True)
figs = []
for name in ('fig_ds37_formation_bands.png', 'fig_ds37_sway_seat_toward_wave_t09.png', 'fig_ds37_sway_triptych.png',
             'fig_ds37_follow_vs_stay.png', 'fig_ds37_191_precheck.png'):
    src = FL / 'fig' / name
    im = Image.open(src)
    if im.size != (W, H):
        stop('1920×1080 でない ' + name)
    dst = EV / name
    shutil.copyfile(src, dst)
    figs.append({'src': rel(src), 'dst': rel(dst), 'scale': 1.0, 'src_sha256': sha(src), 'sha256': sha(dst)})

# 修正1 の図（1920×2380）：見出し（行 0〜40）＋ 3 段ずつの 2 枚（段の境は行 1210）に分け、1080 の高さへ縮めて白で左右を埋める
src = FL / 'fig/fig_ds37_fix1_sway_formation.png'
big = Image.open(src).convert('RGB')
if big.size != (1920, 2380):
    stop('修正1 の図の大きさが想定と違う ' + str(big.size))
arr = np.asarray(big)
for tag, (y0, y1) in (('a', (40, 1210)), ('b', (1210, 2380))):
    part = np.concatenate([arr[0:40], arr[y0:y1]], axis=0)
    sc = H / part.shape[0]
    nw = int(round(part.shape[1] * sc))
    small = cv2.resize(part, (nw, H), interpolation=cv2.INTER_AREA)
    canvas = np.full((H, W, 3), 255, np.uint8)
    x0 = (W - nw) // 2
    canvas[:, x0:x0 + nw] = small
    dst = EV / ('fig_ds37_fix1_sway_formation_%s.png' % tag)
    Image.fromarray(canvas).save(dst, optimize=True)
    figs.append({'src': rel(src) + ' [行 0:40 と %d:%d]' % (y0, y1), 'dst': rel(dst), 'scale': round(sc, 4), 'src_sha256': sha(src), 'sha256': sha(dst)})

# ---- 4. 動画（頭の揺れの 3 本。形成の 2 本は設計36 の証拠と同じファイルなので写さない）
videos = []
for name in ('ds37_sway_seat_formation_30fps.mp4', 'ds37_sway_seat_tstar_30fps.mp4', 'ds37_sway_seat_toward_wave_t09_30fps.mp4'):
    src = FL / 'unity/video' / name
    if os.path.getsize(src) > MB5:
        stop('5 MB を超える ' + name)
    dst = EV / name
    shutil.copyfile(src, dst)
    cap = cv2.VideoCapture(str(dst))
    info = {'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': round(cap.get(cv2.CAP_PROP_FPS), 3), 'frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
    cap.release()
    videos.append(dict(src=rel(src), dst=rel(dst), bytes=os.path.getsize(dst), sha256=sha(dst), **info))
for k in ('formation_painting_video', 'formation_seat_video'):
    videos.append({'src': same36[k]['ds37'], 'dst': same36[k]['ds36'] + '（設計36 の証拠。同じファイル）', 'bytes': os.path.getsize(ROOT / same36[k]['ds36']),
                   'sha256': same36[k]['sha256']})

# ---- 5. JSON の写し
copies = []
for src, dname in ((FL / 'ds37_flowlines_metrics.json', 'ds37_flowlines_metrics.json'), (FL / 'ds37_run.json', 'ds37_run.json'),
                   (IND / 'stick_results.json', 'ds37_indep_stick.json'), (IND / 'c177.json', 'ds37_indep_177.json')):
    dst = EV / dname
    shutil.copyfile(src, dst)
    copies.append({'src': rel(src), 'dst': rel(dst), 'bytes': os.path.getsize(dst), 'sha256': sha(dst)})

# ---- 6. 組の集計（作る部の組ごとの値から）
fp = [p for p in m['formation_pairs'] if abs(p['gap'] - 0.1) < 1e-6]
f1 = [p for p in m['formation_pairs'] if abs(p['gap'] - 1.0) < 1e-6]
sp = m['sway_pairs']


def group(ps):
    disc = sum(p['disc_px'] for p in ps)
    j = [p for p in ps if p['disc_px'] > 0]
    g200 = [p for p in ps if p['disc_px'] >= 200]
    return {
        'pairs': len(ps), 'pairs_with_disc': len(j), 'pairs_with_disc_ge200': len(g200), 'disc_px': disc,
        'disc_px_by_sheet': {k: sum(p['disc_px_by_sheet'][k] for p in ps) for k in ('hero', 'near', 'far')},
        'follow_rate_weighted': round(sum(p['follow_rate'] * p['disc_px'] for p in j) / disc, 4) if disc else None,
        'stay_rate_weighted': round(sum(p['stay_rate'] * p['disc_px'] for p in j) / disc, 4) if disc else None,
        'follow_rate_range': [min(p['follow_rate'] for p in j), max(p['follow_rate'] for p in j)] if j else None,
        'of_ratio_median_range': [min(p['of_ratio_median'] for p in j), max(p['of_ratio_median'] for p in j)] if j else None,
        'neither_frac_range_ge200': [round(min(p['neither_px'] / p['disc_px'] for p in g200), 4), round(max(p['neither_px'] / p['disc_px'] for p in g200), 4)] if g200 else None,
        'stuck_clusters_ge10': sum(p['stuck_clusters_ge10'] for p in ps), 'stuck_px': sum(p['stuck_px'] for p in ps),
        'transfer_only_clusters_ge10': sum(p['transfer_only_clusters_ge10'] for p in ps),
        'of_only_lt0p3_clusters_ge10': sum(p['of_only_lt0p3_clusters_ge10'] for p in ps),
        'control_clusters_min_ge200': min(p['control_stuck_clusters_ge10'] for p in g200) if g200 else None,
        'control_detects_all_ge200': all(p['control_stuck_clusters_ge10'] > 0 for p in g200),
    }


groups = {}
for v in ('painting', 'seat'):
    for c, cn in (('colourWhiteOff', 'white_off'), ('colourWhiteOn', 'white_on')):
        groups['formation_%s_%s' % (v, cn)] = group([p for p in fp if p['view'] == v and p['colour'] == c])
for v in ('seat', 'seat_toward_wave'):
    groups['sway_' + v] = group([p for p in sp if p['view'] == v])
groups['all_70'] = group(fp + sp)
groups['formation_gap1s_record_only'] = group(f1)
groups['formation_seat_pairs_without_disc_t'] = sorted({p['t'] for p in fp if p['view'] == 'seat' and p['disc_px'] == 0})

# ---- 7. 独立の検査の集計（stick_results.json・c177.json から）
st = jload(IND / 'stick_results.json')
indep_st = {}
for pref, key in (('form_W0', 'formation_white_off'), ('form_W1', 'formation_white_on'), ('sway', 'sway')):
    g = [x for x in st if x['tag'].startswith(pref)]
    disc = sum(x['disc'] for x in g)
    indep_st[key] = {'pairs': len(g), 'disc_px': disc, 'disc_px_by_sheet': {n: sum(x['disc_by_sheet'][k] for x in g) for k, n in (('1', 'hero'), ('2', 'near'), ('3', 'far'))},
                     'follow': round(sum(x['follow'] for x in g) / disc, 4), 'stay': round(sum(x['stay'] for x in g) / disc, 4),
                     'worst_pair_follow': min(x['follow_frac'] for x in g if x['disc'] > 0),
                     'stuck_clusters_ge10': sum(len(x['stuck_clusters']) for x in g),
                     'clusters': {x['tag']: x['stuck_clusters'] for x in g if x['stuck_clusters']}}
ctrl = [x for x in st if x['control_disc'] >= 200]
indep_st['control'] = {'pairs_ge200': len(ctrl), 'all_detected': all(x['control_stuck_clusters'] > 0 for x in ctrl),
                       'control_stay_frac_min': min(x['control_stay_frac'] for x in ctrl)}
c177 = jload(IND / 'c177.json')
cb = c177['bands']
dsum = np.array([r[2] for r in c177['display']]).sum(0).tolist()
indep_177 = {'bands_mapped': sum(1 for b in cb if b['mapped']), 'rise_m_range': [round(min(b['rise'] for b in cb), 3), round(max(b['rise'] for b in cb), 3)],
             'height_t2_m_range': [round(min(b['h2'] for b in cb), 3), round(max(b['h2'] for b in cb), 3)],
             'height_tstar_m_range': [round(min(b['h12'] for b in cb), 3), round(max(b['h12'] for b in cb), 3)],
             'max_drop_per_step_m': round(max(b['max_drop_step'] for b in cb), 3), 'reproj_err_p99_max_px': round(max(b['reproj_err_p99'] for b in cb), 3),
             'lower_order_inversions_max': max(c177['inv']), 'lower_order_steps': len(c177['inv']),
             'display_counts_other_white_mizuiro_aimid_aidark': dsum, 'display_px_total': int(sum(r[1] for r in c177['display'])),
             'display_ai_mid_share': round(dsum[3] / max(1, sum(r[1] for r in c177['display'])), 4), 'display_times': len(c177['display'])}

# ---- 8. metrics.json
m177 = m['177']
ss = m['screen_sticking']
p191 = m['191_precheck']['per_view']
fix = {k: v for k, v in m['fix1_sway_formation'].items() if k != 'at_t'}
started = (FL / '_started.txt').read_text(encoding='utf-8').splitlines()
metrics = {
    'schema': 'GreatWave.Design37.metrics/1',
    'number': '設計37：波の流れに沿う線（水面の変形と模様の安定）',
    'evidence_kind_ja': 'Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と numpy/OpenCV。HMD 実機ではない（PS VR2 は保留）。頭の揺れは座席のカメラを左右へずらした PC の描画。',
    'acceptance': {
        '177_keeps_value': {
            'criterion_ja': '美術優先31 と同じ藍中の帯 25 本が面の成分へ対応し、同じ面の点が t 2 s → t* で上がり、下側の 8 本の並びの入れ替わり 0、帯の画素が白で塗られる 0、終点 77・118 ≤ 4 px（合否の読みは進行役の判断）',
            'builder': {'bands_mapped': m177['bands_mapped'], 'bands_total': m177['bands_total'], 'rise_all': m177['rise_all'],
                        'rise_m_range': [min(b['rise_m'] for b in m177['bands']), max(b['rise_m'] for b in m177['bands'])],
                        'height_t2_m_range': [min(b['height_m_t2'] for b in m177['bands']), max(b['height_m_t2'] for b in m177['bands'])],
                        'height_tstar_m_range': [min(b['height_m_tstar'] for b in m177['bands']), max(b['height_m_tstar'] for b in m177['bands'])],
                        'height_total_drop_m_max': max(b['height_total_drop_m'] for b in m177['bands']),
                        'height_max_drop_per_0p25s_m': max(b['height_max_drop_per_step_m'] for b in m177['bands']),
                        'bands_with_any_drop': sum(1 for b in m177['bands'] if b['height_total_drop_m'] > 0),
                        'lower_bands': m177['lower_bands'], 'lower_order_inversions_max': max(m177['lower_order_inversions']),
                        'lower_order_steps': len(m177['lower_order_inversions']),
                        'band_px_shown_white_total': m177['band_px_shown_white_total'], 'display_times': len(m177['display_ai_mid']),
                        'display_ai_mid_min_frac_record_only': m177['display_ai_mid_min_frac'], 'endpoints_px': m177['endpoints_px']},
            'indep': indep_177,
            'reference_art_first_31_ja': '美術優先31（Step_31_ja.md の 177 の行）：25 本すべて対応、帯の表示は全 47 時刻で 100% 藍中（ID の画像）、高さは t 2 s の 0 m から t* の 2.7〜13.5 m、唇に乗る 8 本は 0.14〜1.17 m 下がる、下側 8 本の入れ替わり 0、終点 77 1.17 px・118 0.66 px',
            'pass': bool(m177['pass']),
        },
        'screen_sticking_0': {
            'criterion_ja': m['definitions_ja']['stuck_cluster'],
            'definition_ja': m['definitions_ja']['stuck'],
            'definition_change_ja': m['definitions_ja']['stuck_definition_change_ja'],
            'builder': {k: ss[k] for k in ('pairs', 'pairs_with_disc_ge200', 'stuck_clusters_total', 'stuck_px_total', 'disc_px_total', 'follow_rate_weighted',
                                           'stay_rate_weighted', 'of_ratio_median_of_pairs', 'control_detects_all_pairs_with_disc_ge200', 'disc_px_by_sheet_total',
                                           'transfer_only_clusters_total', 'transfer_only_of_ratio_median_by_pair', 'of_only_lt0p3_clusters_total')},
            'builder_groups': groups,
            'indep': indep_st,
            'pass': bool(ss['pass']),
        },
    },
    'record_only_191_precheck': {
        'per_view': {v: {k: p191[v][k] for k in ('frames', 'line_px_median', 'flash_clusters_ge10', 'hole_clusters_ge10', 'hole_frames', 'jump_clusters_ge10',
                                                 'blink_px_frac_median', 'hero_move_max_px_median', 'slow_frames', 'blink_clusters_ge10_in_slow_frames')} for v in p191},
        'note_ja': 'コマ番号は t = k/30 s（191 の 301 コマは k = 60〜360）。hole_frames は最初の 20 コマだけ。合否は設計38。',
    },
    'regression_plan_2_0': {
        'identical_to_ds36': same36,
        'ds36_values_t28_claws': m36['regression_plan_2_0']['t28_claws'],
        'ds36_verdicts_sym_t28_claws': m36['regression_verdicts_sym']['t28_claws'],
        'note_ja': '原画視点 t* の画像が設計36 の t28_claws の画像と同じファイル（SHA-256）なので、評価器の値は設計36 のまま。評価器は回し直していない。爪なし（t28_white）の画像は設計37 では描いていない。',
    },
    'ds36_handoff_single_frame_flicker': {
        'note_ja': '設計36 から渡された 1 コマだけの色の跳び（t ≈ 10.9〜11.1 s）は、設計37 では測っていない。形成の動画は設計36 と同じファイルなので、値は設計36 の記録の数え直しのまま（下）。',
        'ds36_painting': {k: m36['flicker']['ds36_painting'][k] for k in ('sha256', 'cluster_px_max', 'cluster_px_max_frame', 'frames_gt50', 'after_frame_362_max')},
        'ds36_seat': {k: m36['flicker']['ds36_seat'][k] for k in ('sha256', 'cluster_px_max', 'cluster_px_max_frame', 'frames_gt50', 'after_frame_362_max')},
    },
    'fix_rounds': {'used': 1, 'limit_q26': 1, 'fix1': fix, 'sway_stills_before_after': sway_fix1},
    'backlog': {
        '177': {'value': m['backlog']['177']['value'], 'verdict': '合格'},
        'screen_sticking_0': {'value': m['backlog']['screen_sticking_0']['value'], 'verdict': '合格'},
        '191': {'value': m['backlog']['191']['value'], 'verdict': '記録のみ（事前検査。合否は設計38）'},
    },
    'hmd': '保留（PS VR2 の導入は利用者の手。Q24）。Mock の両眼はこの番号では描いていない（設計38）。頭の揺れは PC のカメラのずらしで、HMD の頭の追跡ではない。',
    'time': {
        'box_q26_h': 3,
        'started_txt': started,
        'file_times': {
            'eval_stdout': mtime(FL / 'eval_stdout.txt'),
            'render_report_run4': mtime(FL / 'unity/ds37_render_report.json'),
            'surface_coord_shader': mtime(ROOT / 'Unity/Assets/GreatWave/Design37/Shaders/DS37_Surface_Coord.shader'),
            'indep_check_first': min(mtime(IND / f) for f in os.listdir(IND)),
            'indep_check_last': max(mtime(IND / f) for f in os.listdir(IND)),
            'fix1_render_report': mtime(FL / 'unity_fix1/ds37_render_report.json'),
            'fix1_compare': mtime(FL / 'unity_fix1/ds37_fix1_sway_compare.json'),
            'metrics_builder': mtime(FL / 'ds37_flowlines_metrics.json'),
            'run_builder': mtime(FL / 'ds37_run.json'),
        },
        'unity_seconds_run4': run37['unity_seconds'], 'unity_seconds_fix1': run37['fix1_unity_seconds'], 'eval_seconds': m['seconds'],
        'record_run': time.strftime('%Y-%m-%d %H:%M:%S'),
    },
}
with open(EV / 'metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)

# ---- 9. run.json
code = {k: v for k, v in run37['code_sha256'].items()}
code['Tools/GWWaveGen/ds37/ds37_record.py'] = sha(Path(__file__).resolve())
run = {
    'schema': 'GreatWave.Design37.run/1',
    'commands': run37['commands'] + ['記録：py -3.10 -B Tools/GWWaveGen/ds37/ds37_record.py（約 10 秒）'],
    'environment': dict(run37['tools'], pillow=Image.__version__, python_record=platform.python_version(), numpy_record=np.__version__, opencv_record=cv2.__version__),
    'code_sha256': code,
    'scene': {'path': 'Unity/Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity', 'sha256': sha(ROOT / 'Unity/Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity')},
    'inputs_sha256': run37['inputs_sha256'],
    'protected_files': run37['protected_files'],
    'protectedUnchanged': bool(run37['protected_unchanged'] and run37['fix1_protected_unchanged']),
    'unity_seconds': {'run4': run37['unity_seconds'], 'fix1': run37['fix1_unity_seconds']},
    'builder_outputs_sha256': run37['outputs_sha256'],
    'builder_sha256_checked': checked,
    'fix1_note_ja': run37['fix1_note_ja'],
    'identical_to_ds36': same36,
    'figures': figs,
    'videos': videos,
    'copies': copies,
    'indep_check_files_sha256': {rel(IND / f): sha(IND / f) for f in sorted(os.listdir(IND))},
    'not_kept_note_ja': run37['not_kept_note_ja'],
    'not_used_ja': '参照モデル・利用者の解算・写真のフォルダー・Blender・Houdini は使っていない。爪形分析のフォルダーは、作る部も検査もこの記録の道具も開いていない（コミットの一覧の点検で、ファイルの大きさと SHA-256 を読み取りのみで照合しただけ）。',
    'record_run': metrics['time']['record_run'],
}
with open(EV / 'run.json', 'w', encoding='utf-8') as f:
    json.dump(run, f, ensure_ascii=False, indent=1)

print('図', len(figs), '動画（写した）', sum(1 for v in videos if 'frames' in v), '写し', len(copies))
for v in videos:
    print(' ', v['dst'], v['bytes'])
print('頭の揺れの静止画 修正の前後で同じ', sway_same, '/', len(fa))
print('独立の検査', json.dumps({k: (v['stuck_clusters_ge10'] if 'stuck_clusters_ge10' in v else v) for k, v in indep_st.items()}, ensure_ascii=False))
print('177 独立', json.dumps(indep_177, ensure_ascii=False))
print('証拠', rel(EV))
