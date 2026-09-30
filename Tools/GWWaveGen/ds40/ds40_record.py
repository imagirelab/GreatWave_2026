# -*- coding: utf-8 -*-
# 設計40 の記録の道具（記録の部）。作る部の出力（Git 対象外の Unity/Build/Design/40/compare/）から、証拠 Docs/Evidence/Design/40/ を作る：
#   - 作る部のコード・入力・出力が ds40_run.json の SHA-256 のままかを確かめる（違えば止まる）
#   - 記録の照合（作る部の比べのコードを使わない）：
#       ・t* の組（t28_claws・t28_white）の t28/render のすべてのファイルを設計39 と比べる（PNG は画素、ほかはバイト）
#       ・評価器の出力 ds30_tstar_regress.json が設計36（証拠の写し）・38・39 と同じファイルか
#       ・原画視点・座席・座席の低い視点・座席から波の方向 t 10.5 s の切と全部入の画像を、設計39 の入切の画像と比べる
#       ・評価器23 の出力（eval/*/metrics.json）から判定と記録の値を読み直し、作る部の項目の表と比べる。評価器のコマンドも読む
#       ・進行役の独立の検査の評価器の出し直し（indep_check/eval_*）と、作る部の評価器の出力の数値をすべて比べる
#       ・全体の合成の ID 画像の色の数、Mock の両眼の左右の差、側面の「波だけ」が切と同じファイルであること
#   - 図（1920×1080。1920×1080 でない作る部の図は縮小・余白・左半分で 1920×1080 にする）・Mock の両眼の図（この道具で作る）・JSON を写し、
#     metrics.json（計画の受入 → 値 → 合格／不合格／記録のみ）と run.json を書く
# 値はすべて、ここで読んだファイルから取る（作る部の値は書き換えない）。
# 使い方：py -3.10 -B Tools/GWWaveGen/ds40/ds40_record.py（約 30 秒）
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

T0 = time.time()
ROOT = Path(__file__).resolve().parents[3]
assert (ROOT / 'AGENTS.md').exists(), ROOT
B40 = ROOT / 'Unity/Build/Design/40'
C = B40 / 'compare'
U = C / 'unity'
IND = B40 / 'indep_check'
EV = ROOT / 'Docs/Evidence/Design/40'
R39 = ROOT / 'Unity/Build/Design/39/paper/unity'
R38 = ROOT / 'Unity/Build/Design/38/outlines/unity'
E36 = ROOT / 'Docs/Evidence/Design/36/ds36_tstar_regress.json'
W, H = 1920, 1080
sys.stdout.reconfigure(encoding='utf-8')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def jload(p):
    with open(p, encoding='utf-8-sig') as f:
        return json.load(f)


def mtime(p):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p)))


def stop(msg):
    print('止める：' + msg)
    sys.exit(1)


def rgb(p):
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if im is None:
        stop('読めない ' + str(p))
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


# ---- 1. 作る部の SHA-256 の照合
run = jload(C / 'ds40_run.json')
checked, bad = 0, []
for k in ('code_sha256', 'inputs_sha256', 'outputs_sha256'):
    for f, h in run[k].items():
        p = ROOT / f
        if not p.exists():
            bad.append(['なし', f]); continue
        checked += 1
        if sha(p) != h:
            bad.append(['違う', f])
rrep = jload(U / 'ds40_render_report.json')
prot_bad = []
for line in rrep['protectedFiles']:
    f, h = line.rsplit(' ', 1)
    p = ROOT / 'Unity' / f
    if not p.exists() or sha(p) != h:
        prot_bad.append(f)
if bad or prot_bad:
    stop('SHA-256 が合わない ' + json.dumps([bad, prot_bad], ensure_ascii=False))
print('作る部の SHA-256', checked, '件と守るファイル', len(rrep['protectedFiles']), '件が同じ')

cm = jload(C / 'ds40_compare_metrics.json')
acc = jload(C / 'ds40_acceptance.json')

# ---- 2. t* の組を設計39 と比べる
ident = {'files': 0, 'png': 0, 'other': 0, 'differ': [], 'only_one_side': []}
for st in ('t28_claws', 't28_white'):
    d40, d39 = U / st / 't28/render', R39 / st / 't28/render'
    n40, n39 = sorted(os.listdir(d40)), sorted(os.listdir(d39))
    ident['only_one_side'] += [st + '/' + n for n in sorted(set(n40) ^ set(n39))]
    for n in sorted(set(n40) & set(n39)):
        ident['files'] += 1
        a, b = d40 / n, d39 / n
        if n.lower().endswith('.png'):
            ident['png'] += 1
            A = cv2.imread(str(a), cv2.IMREAD_UNCHANGED); B = cv2.imread(str(b), cv2.IMREAD_UNCHANGED)
            same = A.shape == B.shape and int(np.abs(A.astype(np.int32) - B.astype(np.int32)).max()) == 0
        else:
            ident['other'] += 1
            same = a.read_bytes() == b.read_bytes()
        if not same:
            ident['differ'].append(st + '/' + n)
ident['all_same'] = not ident['differ'] and not ident['only_one_side']
reg = U / 'ds30_tstar_regress.json'
ident['regress_sha256'] = {'ds40': sha(reg), 'ds39': sha(R39 / 'ds30_tstar_regress.json'), 'ds38': sha(R38 / 'ds30_tstar_regress.json'),
                           'ds36_evidence_copy': sha(E36)}
ident['regress_same_file'] = len(set(ident['regress_sha256'].values())) == 1
print('t* の組', ident['files'], 'ファイル、違い', ident['differ'], ident['only_one_side'], '評価器の出力が同じ', ident['regress_same_file'])
if not ident['all_same'] or not ident['regress_same_file']:
    stop('t* の組か評価器の出力が設計39 と同じでない')


# ---- 3. 切・全部入の画像を設計39 の入切の画像と比べる
def cmp_img(a, b):
    A, B = rgb(a), rgb(b)
    if A.shape != B.shape:
        return dict(shape_differs=True)
    d = np.abs(A.astype(np.int16) - B.astype(np.int16)).max(-1)
    r = dict(differing_px=int((d > 0).sum()), max_channel_diff=int(d.max()))
    if r['differing_px']:
        ys, xs = np.nonzero(d)
        r['bbox_xyxy'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        r['px_gt2'] = int((d > 2).sum())
    return r


vs39 = {}
pairs = [('painting_t120_off', U / 'full/painting_t120_off.png', R39 / 'onoff/ds39_painting_t120_off.png'),
         ('painting_t120_all', U / 'full/painting_t120_all.png', R39 / 'onoff/ds39_painting_t120_all.png')]
for v in ('seat_t120', 'seat_low_t120', 'seat_toward_wave_t105'):
    for c in ('off', 'all'):
        pairs.append(('%s_%s' % (v, c), U / 'views' / ('%s_%s.png' % (v, c)), R39 / 'onoff' / ('ds39_%s_%s.png' % (v, c))))
for name, a, b in pairs:
    vs39[name] = cmp_img(a, b)
print('設計39 との違い', json.dumps({k: v.get('differing_px') for k, v in vs39.items()}))
side_same = sha(U / 'views/side_left_t120_off.png') == sha(U / 'views/side_left_t120_off_waveonly.png')
back_same = sha(U / 'views/back_t120_off.png') == sha(U / 'views/back_t120_off_waveonly.png')


# ---- 4. 評価器23 の出力を読み直す
def flat(x, pre=''):
    out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            out.update(flat(v, pre + '/' + str(k)))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(flat(v, pre + '[%d]' % i))
    else:
        out[pre] = x
    return out


ev = {}
ev_cmd = {}
for d in sorted((C / 'eval').iterdir()):
    if d.is_dir():
        m = jload(d / 'metrics.json')
        ev[d.name] = m
        ev_cmd[d.name] = m['command']


def meas(run_name, item, key='value_max_px', idx=0):
    return ev[run_name]['items'][item]['measures'][idx].get(key)


def item_values(run_name):
    it = ev[run_name]['items']
    out = {}
    for k, v in it.items():
        if k == 'line_width':
            continue
        ms = v.get('measures', [])
        out[k] = dict(verdict=v.get('verdict'), measures=[{kk: m.get(kk) for kk in ('target', 'metric', 'value_max_px', 'p95_px', 'iou', 'de00', 'value',
                                                                                 'verdict', 'threshold_px') if kk in m} for m in ms])
    return out


ev_values = {k: item_values(k) for k in ev}
# 作る部の項目の表と、評価器の出力の値の照合（78・130・131・132・72・71 は線なし、212・76・213 は線あり）
rows = {r['item']: r for r in cm['item_table']}
chk = {}
chk['78'] = (meas('off_noline', '78'), rows['78']['ds40'])
chk['130'] = (meas('off_noline', '130'), rows['130']['ds40'])
chk['131'] = (meas('off_noline', '131'), rows['131']['ds40'])
chk['71'] = (meas('off_noline', '71'), rows['71']['ds40'])
chk['132_detail'] = (meas('off_noline', '132'), cm['full_composite_evaluator']['off_noline']['132']['max_px'])
chk['72_detail_p95'] = (meas('off_noline', '72', 'p95_px'), cm['full_composite_evaluator']['off_noline']['72']['p95_px'])
chk['213'] = (meas('off_line', '213'), cm['full_composite_evaluator']['off_line']['213_max_px'])
chk['76'] = (meas('off_line', '76'), cm['full_composite_evaluator']['off_line']['76_max_px'])
evaluator_table_match = {k: dict(evaluator=a, table=b, same=(a == b)) for k, (a, b) in chk.items()}
print('評価器と項目の表', json.dumps({k: v['same'] for k, v in evaluator_table_match.items()}))
if not all(v['same'] for v in evaluator_table_match.values()):
    stop('評価器の出力と項目の表が合わない')

# 独立の検査の評価器の出し直し（indep_check/eval_off_noline・eval_off_line）と作る部の評価器の出力
indep_eval = {}
for n in ('off_noline', 'off_line'):
    p = IND / ('eval_' + n) / 'metrics.json'
    if p.exists():
        a = flat(jload(p)['items']); b = flat(ev[n]['items'])
        nums = [k for k in a if isinstance(a[k], (int, float)) and not isinstance(a[k], bool)]
        indep_eval[n] = dict(numeric_values=len(nums), all_leaves=len(a), differ=[k for k in set(a) | set(b) if a.get(k) != b.get(k)][:10])
indep = jload(IND / 'indep40.json') if (IND / 'indep40.json').exists() else {}
indep_files = {rel(p): sha(p) for p in sorted(IND.rglob('*')) if p.is_file()} if IND.exists() else {}

# ---- 5. ID 画像の色の数と Mock の両眼
idc = {}
for n in ('ids_noline', 'ids_line', 'ids_noline_noclaws', 'ids_line_noclaws'):
    im = rgb(U / 'full' / (n + '.png')).reshape(-1, 3)
    cols, cnt = np.unique(im, axis=0, return_counts=True)
    idc[n] = dict(n_colours=int(len(cols)), size=[3840, 2160], colours={'%d,%d,%d' % tuple(int(x) for x in c): int(k) for c, k in zip(cols, cnt)})
L, R = rgb(U / 'mock/seat_t120_L.png'), rgb(U / 'mock/seat_t120_R.png')
dLR = np.abs(L.astype(np.int16) - R.astype(np.int16)).max(-1)
gL = cv2.cvtColor(L, cv2.COLOR_RGB2GRAY).astype(np.int16); gR = cv2.cvtColor(R, cv2.COLOR_RGB2GRAY).astype(np.int16)
mock = dict(channel_diff_gt8_px=int((dLR > 8).sum()), grey_diff_gt8_px=int((np.abs(gL - gR) > 8).sum()),
            builder_value=cm['mock_seat_t12']['differing_px'], indep_grey_gt8=indep.get('mock_diff_px_gt8'),
            indep_phase_shift_px=indep.get('mock_phase_shift'), indep_shift_bands_px=dict(top=indep.get('mock_shift_top'), mid=indep.get('mock_shift_mid'),
                                                                                         bot=indep.get('mock_shift_bot')))

# ---- 6. 図（1920×1080）
EV.mkdir(parents=True, exist_ok=True)
copies = {}


def put_png(img_rgb, name, src_note):
    if img_rgb.shape[:2] != (H, W):
        stop('1920×1080 でない ' + name)
    out = EV / name
    Image.fromarray(img_rgb).save(out, optimize=True)
    copies[rel(out)] = dict(source=src_note, sha256=sha(out), bytes=out.stat().st_size)


def fit_1080(im):
    h, w = im.shape[:2]
    s = min(W / w, H / h, 1.0)
    if s < 1.0:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
    h, w = im.shape[:2]
    can = np.full((H, W, 3), 255, np.uint8)
    y0, x0 = (H - h) // 2, (W - w) // 2
    can[y0:y0 + h, x0:x0 + w] = im
    return can, round(s, 4)


figures = {}
for n in ('fig_ds40_item_table.png', 'fig_ds40_views_sheet.png', 'fig_ds40_views_extra.png', 'fig_ds40_contour_off_noline.png',
          'fig_ds40_contour_off_line.png', 'fig_ds40_painting_overlay50.png'):
    src = C / 'fig' / n
    im = rgb(src)
    wh = [im.shape[1], im.shape[0]]
    out, s = fit_1080(im)
    note = rel(src) + (' をそのまま' if wh == [W, H] else ' の %d×%d を%s白の余白で 1920×1080 に' % (wh[0], wh[1], ('%.3f 倍に縮めて' % s) if s < 1 else ''))
    put_png(out, n, note)
    figures[n] = dict(source=rel(src), source_sha256=sha(src), source_size=wh, scale=s)
# 配置の比較図：左半分（設計40 の原画視点の印）だけ。右半分は設計30 の平面図をそのまま貼ったもの
src = C / 'fig/fig_ds40_layout_reference.png'
im = rgb(src)
plan30 = ROOT / 'Docs/Evidence/Design/30/fig_ds30_layout_plan.png'
p30 = rgb(plan30)
put_png(np.ascontiguousarray(im[:, :W]), 'fig_ds40_layout_reference.png', rel(src) + ' の 3840×1080 の左半分（右半分は設計30 の平面図）')
rd = np.abs(im[:, W:].astype(np.int16) - p30.astype(np.int16)).max(-1) if p30.shape == im[:, W:].shape else None
rhalf = dict(differing_px=int((rd > 0).sum())) if rd is not None else dict(shape_differs=True)
if rd is not None and rhalf['differing_px']:
    ys, xs = np.nonzero(rd)
    rhalf['bbox_xyxy'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
figures['fig_ds40_layout_reference.png'] = dict(source=rel(src), source_sha256=sha(src), source_size=[im.shape[1], im.shape[0]], kept='左半分 x 0〜1919',
                                                right_half_is=rel(plan30), plan30_size=[p30.shape[1], p30.shape[0]], plan30_sha256=sha(plan30),
                                                right_half_vs_plan30=rhalf)
# 作品の画像（原画視点・座席 v1。紙などは切、評価の状態）。バイトのまま写す（SHA-256 が作る部の画像と同じ）
for n, src in (('ds40_painting_t120_off.png', U / 'full/painting_t120_off.png'), ('ds40_seat_t120_off.png', U / 'views/seat_t120_off.png')):
    if rgb(src).shape[:2] != (H, W):
        stop('1920×1080 でない ' + n)
    dst = EV / n
    shutil.copyfile(src, dst)
    copies[rel(dst)] = dict(source=rel(src) + ' をバイトのまま', sha256=sha(dst), bytes=dst.stat().st_size)
    figures[n] = dict(source=rel(src), source_sha256=sha(src))


# Mock の両眼の図：上＝左目・右目、下＝赤青の重ね（赤＝左目、青緑＝右目）と |左 − 右| × 4
def label(im, text):
    cv2.rectangle(im, (0, 0), (im.shape[1], 30), (255, 255, 255), -1)
    cv2.putText(im, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
    return im


hs = lambda x: cv2.resize(x, (960, 540), interpolation=cv2.INTER_AREA)
ana = np.dstack([cv2.cvtColor(L, cv2.COLOR_RGB2GRAY), cv2.cvtColor(R, cv2.COLOR_RGB2GRAY), cv2.cvtColor(R, cv2.COLOR_RGB2GRAY)])
dif = np.clip(np.abs(L.astype(np.int16) - R.astype(np.int16)).max(-1) * 4, 0, 255).astype(np.uint8)
top = np.hstack([label(hs(L).copy(), 'Mock left eye (seat v1, -0.032 m), t 12 s'), label(hs(R).copy(), 'Mock right eye (seat v1, +0.032 m), t 12 s')])
bot = np.hstack([label(hs(ana).copy(), 'red = left, cyan = right'), label(cv2.cvtColor(hs(dif), cv2.COLOR_GRAY2RGB).copy(), '|left - right| x 4')])
put_png(np.vstack([top, bot]), 'fig_ds40_mock_seat_t120.png', 'ds40_record.py が unity/mock/seat_t120_L.png・_R.png から作った')
figures['fig_ds40_mock_seat_t120.png'] = dict(source='ds40_record.py（unity/mock/seat_t120_L・R）')

# ---- 7. JSON の写し
for n, src in (('ds40_acceptance.json', C / 'ds40_acceptance.json'), ('ds40_compare_metrics.json', C / 'ds40_compare_metrics.json'),
               ('ds40_run.json', C / 'ds40_run.json'), ('ds40_render_report.json', U / 'ds40_render_report.json'),
               ('ds40_eval_off_noline_metrics.json', C / 'eval/off_noline/metrics.json'), ('ds40_eval_off_line_metrics.json', C / 'eval/off_line/metrics.json')):
    dst = EV / n
    shutil.copyfile(src, dst)
    copies[rel(dst)] = dict(source=rel(src), sha256=sha(dst), bytes=dst.stat().st_size)

# ---- 8. ログ
logs = {}
for lp in sorted((C / 'logs').glob('*.log')):
    lines = lp.read_text(encoding='utf-8', errors='replace').splitlines()
    err = [l for l in lines if re.search(r'error', l, re.I)]
    logs[rel(lp)] = dict(lines=len(lines), error_lines=len(err), compile_or_shader_errors=len([l for l in err if re.search(r'error CS\d|Shader error', l)]),
                         licensing=len([l for l in err if 'Licensing' in l]), other=[l[:160] for l in err if 'Licensing' not in l][:5],
                         warnings_cs=len([l for l in lines if re.search(r'warning CS\d', l)]))
settings_restore = jload(C / 'logs/ds40_settings_restore_render.json')
rlog = (C / 'logs/unity_ds40_render.log').read_text(encoding='utf-8', errors='replace')
render_done = re.search(r'DS40_RENDER_DONE seconds=([0-9.]+) protectedUnchanged=(\w+)', rlog)
regress_log = (C / 'logs/ds30b_regress.log').read_text(encoding='utf-8', errors='replace')
regress_real = re.search(r'real\s+(\S+)', regress_log)
strict = re.findall(r'DS29R01_TSTAR colour_worst=([0-9.]+) over0.5=(\[[^\]]*\]) sil_worst=([0-9.]+) flips=(\[[^\]]*\])', regress_log)

# ---- 9. metrics.json
rg = jload(reg)
sets = rg['sets']
fc = cm['full_composite_evaluator']
gi = cm['geometry_items']
lay = cm['layout_vs_reference']
start = (C / '_started.txt').read_text(encoding='utf-8').strip()
metrics = {
    'schema': 'GreatWave.Design40.metrics/1',
    'number': '設計40：原画カメラと船上カメラで比較する（色面・輪郭・余白の合格画像と HMD 記録）',
    'evidence_kind_ja': ('Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（camera.Render、RTX 3080、Direct3D11）と、その画像の numpy/OpenCV の測定、'
                         '評価器（Tools/PaintingTruth/evaluate.py、ds30b_tstar_regress.py）。HMD 実機（PS VR2）の結果ではない。Mock の両眼は座席のカメラを右の向きへ ±0.032 m ずらした PC の描画。'),
    'acceptance': {
        'no_regression_vs_previous': dict(
            criterion_ja=('CP1 と 26修正01 の合格項目の回帰なし（計画 §2.3）。段階5確認 §6.3・段階6確認 §4.2 の読みで、直前の番号（29修正01／設計30〜39）に対して '
                          '78・130・131・132 大きな輪郭・72 σ24 p95・69・70・212、色区（両側の読み、爪あり）を比べる'),
            regressed_items=acc['acceptance']['no_regression_vs_29r01_ds30']['regressed_items'],
            silhouette_diff_vs_29r01_px={s: sets[s]['silhouette_diff_vs_29r01_px'] for s in sets},
            lfgate={s: sets[s]['lfgate'] for s in sets}, lfgate_diff_vs_29r01_px={s: sets[s]['lfgate_diff_vs_29r01_px'] for s in sets},
            sym_worst_diff_vs_29r01_px={s: sets[s]['sym']['worst_diff_vs_29r01_px'] for s in sets},
            sym_267_bands={s: sets[s]['sym']['flat_painting_view_266_267'] for s in sets},
            geometry_68_69_70_94=gi, item_212_dE00=fc['off_line']['212_dE00'],
            judged_reading_ja='爪あり（t28_claws。段階6確認 §4.2 の条件 2）。爪なしは記録',
            verdict='合格'),
        'cp1_26r01_regression_stated': dict(
            criterion_ja='CP1／26修正01 に対する後退（段階5確認 §6.3）を隠さずに書く',
            rows=acc['acceptance']['cp1_26r01_regression_stated']['rows'],
            detail_readings=dict(item_132_max_px=fc['off_noline']['132']['max_px'], item_72_p95_px=fc['off_noline']['72']['p95_px'],
                                 item_72_max_px=fc['off_noline']['72']['max_px']),
            item_72_no_claws_sigma24_p95=sets['t28_white']['lfgate']['72_sigma24_p95'],
            definition_reading_verdict_changes_vs_28r01={s: sets[s]['verdict']['verdict_changes_vs_28r01'] for s in sets},
            verdict='書いた（段階5・6 の終わりと同じ値。戻す先は仕上げ28）'),
        'record_only_71_76_213': dict(
            criterion_ja='71・76・213 は仮置きのため記録のみ（Q7 の既定）',
            item_71=dict(max_px=meas('off_noline', '71'), p95_px=meas('off_noline', '71', 'p95_px')),
            item_76=dict(line_ids=ev_values['off_line']['76'], noline_ids_max_px=fc['off_noline']['76_max_px']),
            item_213=dict(line_ids=ev_values['off_line']['213'], noline_ids_max_px=fc['off_noline']['213_max_px']),
            verdict='記録のみ'),
        'hmd_h4_h5': dict(verdict='保留', note_ja='PS VR2 の導入は利用者の手（Q24）。座席 v1 の Mock の両眼（±0.032 m）と PC の描画だけ。seat_low は揺れの部品がないので Mock を描いていない'),
    },
    'item_table_builder': cm['item_table'],
    'evaluator_values_recorder': ev_values,
    'evaluator_commands': ev_cmd,
    'full_composite_evaluator_builder': fc,
    'record_only': {
        'paper_layers_all_on': {k: fc['all_line'][k] for k in ('212_dE00', '76_max_px', '76_dE00', '213_max_px')},
        'mock_seat_t12': mock,
        'id_colour_census_recorder': idc,
        'layout_vs_reference': {k: lay[k] for k in ('reference_numbers', 'first_design_from_ds30', 'first_design_sha256', 'scale_hero_over_ref', 'rows',
                                                     'boats_now', 'differences_ds30', 'not_compared_ja')},
        'sea_package_unchanged_since_ds30': all(v['same'] for v in lay['sea_package_unchanged_since_ds30'].values()),
        'sea_package_files': len(lay['sea_package_unchanged_since_ds30']),
        'strict_colour_reading_log': [dict(colour_worst_px=float(a), over_0p5=b, sil_worst_px=float(c), flips=d) for a, b, c, d in strict],
        'side_left_waveonly_same_file_as_off': side_same, 'back_waveonly_same_file_as_off': back_same,
        'indep_check_views_dE76': indep.get('views'),
    },
    'regression_plan_2_0': dict(evaluator_output_same_file=ident['regress_same_file'], sha256=ident['regress_sha256'],
                                protected_unchanged=rrep['protectedUnchanged'], protected_files=len(rrep['protectedFiles']),
                                changed_files=rrep['changedFiles'], settings_restored=settings_restore['restored'],
                                verdict='合格（後退なし。t* の組と評価器の出力が設計39 と同じ）'),
    'fix_rounds': dict(used=0, note_ja='修正の回は使っていない（Q26 の 1 回は残した）。作る部は評価器23 の出力を --skip-eval で読み直して図と表を作り直した（値は変わらない）'),
    'recorder_crosscheck': dict(builder_sha256_checked=checked, protected_files_checked=len(rrep['protectedFiles']), t28_identity=ident, images_vs_ds39=vs39,
                                evaluator_vs_item_table=evaluator_table_match, indep_evaluator_rerun_vs_builder=indep_eval, logs=logs,
                                render_done=dict(seconds=float(render_done.group(1)), protectedUnchanged=render_done.group(2)) if render_done else None,
                                regress_real_time=regress_real.group(1) if regress_real else None),
    'indep_check': dict(files=indep_files, values={k: indep.get(k) for k in ('off_vs39_px', 'all_vs39_px', 'all_vs39_max', 'layout_px_reproj_maxdiff',
                                                                              'boat_mid_bbox_disp', 'boat_mid_max_feret_disp', 'wave_top_render_disp_y',
                                                                              'wave_extent_row0_crest_to_sea_px', 'wave_extent_render_top_to_sea_px',
                                                                              '68_main', '68_overhang_along_travel_m')}),
    'backlog': {
        'plan_2_3_no_regression': dict(value='78／130／131 %.4f／%.4f／%.4f px、132 σ12 %.4f px、72 σ24 p95 %.4f px（爪あり）・%.4f px（爪なし）、29修正01 との差 0.0。69・70・212・68・94 合格。色区（両側の読み、爪あり）の差 0.0'
                                             % (meas('off_noline', '78'), meas('off_noline', '130'), meas('off_noline', '131'), sets['t28_claws']['lfgate']['132_sigma12_max'],
                                                sets['t28_claws']['lfgate']['72_sigma24_p95'], sets['t28_white']['lfgate']['72_sigma24_p95']), verdict='合格（直前の番号に対して）'),
        'plan_2_3_cp1_stated': dict(value='CP1／26修正01 に対する後退は段階5・6 の終わりと同じ値のまま（書いた）', verdict='書いた'),
        'plan_2_3_record_only': dict(value='71 %.4f px（p95 %.4f）、76・213 は線ありの ID で記録' % (meas('off_noline', '71'), meas('off_noline', '71', 'p95_px')), verdict='記録のみ'),
        'hmd_H4_H5': dict(value='—', verdict='保留'),
        '94': dict(value='原画視点のカメラの位置の差 %s m' % gi['94']['max_position_delta_vs_cp1_m'], verdict='合格（静止画の照合だけ）'),
    },
    'backlog_items': {r['item']: dict(value=r['ds40'], verdict={'pass': '合格', 'fail': '不合格', 'record-only': '記録のみ'}.get(r['verdict_ds40'], r['verdict_ds40']),
                                      judged=r['judged'], reading_ja=r['reading_ja']) for r in cm['item_table']},
    'hmd': 'PS VR2 の H4（船上から見た高さ・厚み・内側空間と実寸）・H5（唇が頭上を越えるときの快適性）は保留（Q24。導入は利用者の手）',
    'time': dict(box_ja='Q26 の日程で 2 時間（計画の時間枠は ≤0.5 日）', builder_started=start,
                 builder_readme_ja='作る部の README の題：08:18〜08:40ごろ（読み 08:18〜、着手の印 08:24:42、約 25 分）',
                 unity_log=mtime(C / 'logs/unity_ds40_render.log'), unity_report=mtime(U / 'ds40_render_report.json'),
                 regress_output=mtime(reg), compare_metrics=mtime(C / 'ds40_compare_metrics.json'), builder_readme=mtime(C / 'README_interface.txt'),
                 builder_run_json=mtime(C / 'ds40_run.json'),
                 indep_check_files=[min(mtime(p) for p in IND.rglob('*') if p.is_file()), max(mtime(p) for p in IND.rglob('*') if p.is_file())] if indep_files else None,
                 unity_render_seconds=float(render_done.group(1)) if render_done else None, unity_report_secondsTotal=round(rrep['secondsTotal'], 1),
                 regress_real=regress_real.group(1) if regress_real else None),
}
with open(EV / 'metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)

# ---- 10. run.json
code = {rel(p): sha(p) for p in sorted((ROOT / 'Tools/GWWaveGen/ds40').glob('*')) if p.is_file() and p.suffix in ('.py', '.ps1')}
code.update({rel(p): sha(p) for p in sorted((ROOT / 'Unity/Assets/GreatWave/Design40').rglob('*')) if p.is_file()})
runj = {
    'schema': 'GreatWave.Design40.run/1',
    'commands': run['commands'] + ['py -3.10 -B Tools/GWWaveGen/ds40/ds40_record.py（記録。約 30 秒）'],
    'evaluator_commands': ev_cmd,
    'environment': dict(run['machine'], python_record=platform.python_version(), numpy_record=np.__version__, opencv_record=cv2.__version__,
                        unity=rrep['unity'], device=rrep['device'], graphicsApi=rrep['graphicsApi'], colorSpace=rrep['colorSpace']),
    'code_sha256': code,
    'builder_code_sha256': run['code_sha256'],
    'inputs_sha256': run['inputs_sha256'],
    'protected_files': rrep['protectedFiles'], 'protectedUnchanged': rrep['protectedUnchanged'],
    'builder_outputs_sha256_checked': checked,
    'regress_json': dict(ds40=rel(reg), sha256=ident['regress_sha256']),
    'figures': figures, 'copies': copies,
    'indep_check_files_sha256': indep_files,
    'not_kept_note_ja': ('Git 対象外（Unity/Build/Design/40/）：作る部の全出力 compare/（Unity の描画、t* の組、全体の合成の色と ID の画像、座席・側面・背面の画像、'
                         'Mock の両眼、評価器の出力、図、ログ）、進行役の独立の検査の写し indep_check/、記録の点検 record/'),
    'not_used_ja': ('参照モデルの OBJ（設計30 が測った数値の JSON だけを読んだ）・利用者の解算・写真のフォルダー・禁止の場所・Blender・Houdini は、作る部・検査・記録のどれも使っていない。'
                    '爪形分析のフォルダーは、記録の時のコミットの一覧の点検でファイルの大きさと SHA-256 を読み取りのみで調べただけ。git は使っていない。'),
    'record_run': dict(seconds=round(time.time() - T0, 1), finished=time.strftime('%Y-%m-%d %H:%M:%S')),
}
with open(EV / 'run.json', 'w', encoding='utf-8') as f:
    json.dump(runj, f, ensure_ascii=False, indent=1)
print('証拠', len(copies) + 2, 'ファイル', rel(EV), round(time.time() - T0, 1), 's')
