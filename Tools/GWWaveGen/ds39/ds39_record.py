# -*- coding: utf-8 -*-
# 設計39 の記録の道具（記録の部）。作る部の出力（Git 対象外の Unity/Build/Design/39/paper/）から、証拠 Docs/Evidence/Design/39/ を作る：
#   - 作る部の出力・コード・入力・守るファイルが ds39_run.json の SHA-256 のままかを確かめる（違えば止まる）
#   - 記録の照合（作る部の評価のコードを使わない）：
#       ・全部切の t* の組（t28_white・t28_claws）のすべてのファイルを設計38 と比べる（PNG は画素、ほかはバイト）
#       ・評価器の出力が設計38 と同じファイルか
#       ・入切の画像の ΔE00 > 2 の画素の数（作る部の割合は 5 桁に丸めてあるので数で書き直す）
#       ・①② の見えやすさ：入 ÷ 切 の明るさの比の散らばり（利得 1 の作品の値）と、8 bit の値が変わった画素の割合
#       ・プレイヤーの画面（perf/run1・run2）の入切で変わった画素の割合と最大の差
#       ・場面の既定（全部切）と、ログのエラーの行
#   - 図（1920×1080。作る部の図は余白を足して 1920×1080 にする）・むらの継ぎ目の図（この道具で作る）・動画（5 MB 以下）・JSON を写し、
#     metrics.json（計画の受入 → 値 → 合格／不合格／記録のみ）と run.json を書く
# 値はすべて、ここで読んだファイルから取る（作る部の値は書き換えない）。
# 使い方：py -3.10 -B Tools/GWWaveGen/ds39/ds39_record.py（約 1〜2 分。ほかの重い numpy の処理と同時に回さない）
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
from skimage.color import deltaE_ciede2000, rgb2lab

T0 = time.time()
ROOT = Path(__file__).resolve().parents[3]
assert (ROOT / 'AGENTS.md').exists(), ROOT
B39 = ROOT / 'Unity/Build/Design/39'
P = B39 / 'paper'
U = P / 'unity'
IND = B39 / 'indep_check'
REC = B39 / 'record'
EV = ROOT / 'Docs/Evidence/Design/39'
R38 = ROOT / 'Unity/Build/Design/38/outlines/unity'
W, H = 1920, 1080
MB5 = 5 * 1024 * 1024
VIEWS = ['painting_t120', 'seat_t120', 'seat_low_t120', 'seat_toward_wave_t105']
CONDS = ['paper', 'mura', 'spray', 'all']
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
run = jload(P / 'ds39_run.json')
checked, bad = 0, []
for k in ('code_sha256', 'outputs_sha256', 'inputs_sha256'):
    for f, h in run[k].items():
        p = ROOT / f
        if not p.exists():
            bad.append(['なし', f]); continue
        checked += 1
        if sha(p) != h:
            bad.append(['違う', f])
for line in run['unity_protected_files']:
    f, h = line.rsplit(' ', 1)
    p = ROOT / 'Unity' / f
    if not p.exists():
        bad.append(['なし', f]); continue
    checked += 1
    if sha(p) != h:
        bad.append(['違う', f])
if bad:
    stop('ds39_run.json の SHA-256 と合わない ' + json.dumps(bad, ensure_ascii=False))
print('作る部の SHA-256', checked, '件が同じ')

acc = jload(P / 'ds39_acceptance.json')
met = jload(P / 'ds39_paper_metrics.json')
build = jload(P / 'ds39_build_report.json')
rrep = jload(U / 'ds39_render_report.json')
spray_log = jload(P / 'spray/ds39_spray_dense_log.json')

# ---- 2. 全部切の t* の組のすべてのファイルを設計38 と比べる（作る部の評価のコードを使わない）
ident = {'files': 0, 'png': 0, 'other': 0, 'differ': [], 'only_one_side': []}
for st in ('t28_white', 't28_claws'):
    d39, d38 = U / st / 't28/render', R38 / st / 't28/render'
    n39 = sorted(os.listdir(d39)); n38 = sorted(os.listdir(d38))
    ident['only_one_side'] += [st + '/' + n for n in sorted(set(n39) ^ set(n38))]
    for n in sorted(set(n39) & set(n38)):
        ident['files'] += 1
        a, b = d39 / n, d38 / n
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
reg39, reg38 = U / 'ds30_tstar_regress.json', R38 / 'ds30_tstar_regress.json'
ident['regress_sha256_ds39'] = sha(reg39)
ident['regress_sha256_ds38'] = sha(reg38)
ident['regress_same_file'] = ident['regress_sha256_ds39'] == ident['regress_sha256_ds38']
print('全部切の組', ident['files'], 'ファイル、違い', ident['differ'], ident['only_one_side'], '評価器', ident['regress_same_file'])
if not ident['all_same'] or not ident['regress_same_file']:
    stop('全部切が設計38 と同じでない')


# ---- 3. 入切の画像：ΔE00 > 2 の画素の数と、①② の見えやすさ（利得 1 の作品の値）
def lum(im):
    return im.astype(np.float32).mean(-1) / 255.0


onoff = {}
for v in VIEWS:
    off = rgb(U / 'onoff' / ('ds39_%s_off.png' % v))
    lab_off = rgb2lab(off.astype(np.float32) / 255.0)
    L0 = lum(off)
    rec = {}
    for c in CONDS:
        on = rgb(U / 'onoff' / ('ds39_%s_%s.png' % (v, c)))
        d = deltaE_ciede2000(rgb2lab(on.astype(np.float32) / 255.0), lab_off)
        diff = np.abs(on.astype(np.int16) - off.astype(np.int16)).max(-1)
        r = dict(de00_gt2_px=int((d > 2).sum()), de00_gt5_px=int((d > 5).sum()), de00_max=round(float(d.max()), 3),
                 de00_mean=round(float(d.mean()), 4), changed_px_frac=round(float((diff > 0).mean()), 4), max_level_diff=int(diff.max()))
        if c in ('paper', 'mura'):
            m = L0 >= 0.08
            ratio = lum(on)[m] / np.maximum(L0[m], 1e-3) - 1.0
            r['ratio_std_pct'] = round(float(ratio.std() * 100), 3)
            r['ratio_p99_abs_pct'] = round(float(np.percentile(np.abs(ratio), 99) * 100), 3)
            r['ratio_px'] = int(m.sum())
            if r['de00_gt2_px']:
                ys, xs = np.nonzero(d > 2)
                r['de00_gt2_bbox_xy'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        rec[c] = r
    onoff[v] = rec
print('入切', json.dumps({v: {c: (onoff[v][c]['de00_gt2_px'], onoff[v][c].get('ratio_std_pct')) for c in CONDS} for v in VIEWS}))

# ---- 4. プレイヤーの画面（Release の DS39Perf.exe の最後のコマの写し）
player = {}
for tag in ('run1', 'run2'):
    rr = {}
    for cond in ('desk1080_painting', 'desk1080_seat', 'proxy_stereo_seat'):
        base = P / 'perf' / tag / ('ds39_%s_base_%s.png' % (tag, cond))
        if not base.exists():
            continue
        b = rgb(base)
        for var in ('paper', 'mura', 'spray', 'all'):
            q = P / 'perf' / tag / ('ds39_%s_%s_%s.png' % (tag, var, cond))
            if not q.exists():
                continue
            a = rgb(q)
            if a.shape != b.shape:
                rr[var + '|' + cond] = dict(shape_differs=True); continue
            diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)
            rr[var + '|' + cond] = dict(size=[int(a.shape[1]), int(a.shape[0])], changed_px_frac=round(float((diff > 0).mean()), 4),
                                        max_level_diff=int(diff.max()), p99_level_diff=float(np.percentile(diff, 99)))
    player[tag] = rr

# ---- 5. 場面の既定（全部切）とログ
scene_defaults = {}
for sc in ('DS39_Paper.unity', 'DS39_Perf.unity'):
    t = (ROOT / 'Unity/Assets/GreatWave/Design39/Scenes' / sc).read_text(encoding='utf-8')
    blk = t[t.find('paperOn:') - 400: t.find('sprayOn:', t.find('paperOn:')) + 20]
    vals = {k: int(re.search(k + r': (\d)', blk).group(1)) for k in ('paperOn', 'muraOn', 'sprayOn')}
    amps = {k: float(re.search(k + r': ([0-9.]+)', t).group(1)) for k in ('paperAmp', 'muraAmp')}
    i = t.find('ds39_spray_dense_frames.json')
    dense_draw = int(re.search(r'drawInPlayMode: (\d)', t[i:i + 600]).group(1))
    dense_path = re.search(r'dataPath: (.*ds39_spray_dense_frames\.json)', t).group(1)
    scene_defaults[sc] = dict(sha256=sha(ROOT / 'Unity/Assets/GreatWave/Design39/Scenes' / sc), **vals, **amps,
                              dense_spray_drawInPlayMode=dense_draw, dense_spray_dataPath=dense_path)
logs = {}
for lp in sorted(list((P / 'logs').glob('unity_ds39_*.log')) + list((P / 'perf').glob('run*/player_run*.log'))):
    lines = lp.read_text(encoding='utf-8', errors='replace').splitlines()
    err = [l for l in lines if re.search(r'error', l, re.I)]
    logs[rel(lp)] = dict(lines=len(lines), error_lines=len(err), compile_or_shader_errors=len([l for l in err if re.search(r'error CS\d|Shader error', l)]),
                         licensing=len([l for l in err if 'Licensing' in l]), xr_runtime_unavailable=len([l for l in err if 'XR_ERROR_RUNTIME_UNAVAILABLE' in l]),
                         other=[l[:160] for l in err if not re.search(r'Licensing|XR_ERROR_RUNTIME_UNAVAILABLE|DS39_DONE', l)][:5])
ds38_mats = {}
for n in ('DS38_Outline_hero.mat', 'DS38_Outline_near.mat', 'DS38_Outline_claws.mat'):
    p = ROOT / 'Unity/Assets/GreatWave/Design38/Materials' / n
    ds38_mats[n] = dict(sha256=sha(p), mtime=mtime(p))

# ---- 6. 図（1920×1080）
EV.mkdir(parents=True, exist_ok=True)
copies = {}


def put_png(img_rgb, name, src_note):
    out = EV / name
    Image.fromarray(img_rgb).save(out, optimize=True)
    copies[rel(out)] = dict(source=src_note, sha256=sha(out), bytes=out.stat().st_size)


def pad_1080(p):
    im = np.array(Image.open(p).convert('RGB'))
    h, w = im.shape[:2]
    if w > W or h > H:
        stop('1920×1080 より大きい ' + str(p))
    can = np.full((H, W, 3), 255, np.uint8)
    y0, x0 = (H - h) // 2, (W - w) // 2
    can[y0:y0 + h, x0:x0 + w] = im
    return can, [w, h]


figures = {}
for n in ['fig_ds39_onoff_painting_t120.png', 'fig_ds39_onoff_seat_t120.png', 'fig_ds39_onoff_seat_low_t120.png',
          'fig_ds39_onoff_seat_toward_wave_t105.png', 'fig_ds39_zoom_painting_t120.png', 'fig_ds39_zoom_seat_t120.png',
          'fig_ds39_swim_seat_toward_wave_t090.png', 'fig_ds39_swim_seat_t120.png']:
    src = P / 'fig' / n
    im, wh = pad_1080(src)
    put_png(im, n, rel(src) + (' をそのまま' if wh == [W, H] else ' の %d×%d を白の余白で 1920×1080 に' % tuple(wh)))
    figures[n] = dict(source=rel(src), source_sha256=sha(src), source_size=wh)


# むらの継ぎ目の図：② を入れた画像と、(② ÷ 切 − 1) × 25 を灰（0 = 128）で。2 視点。
def label(im, text):
    cv2.rectangle(im, (0, 0), (im.shape[1], 30), (255, 255, 255), -1)
    cv2.putText(im, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    return im


GAIN = 25.0
panels = []
for v, t in (('seat_toward_wave_t105', 'seat_toward_wave t 10.5 s'), ('seat_t120', 'seat t 12 s')):
    off = rgb(U / 'onoff' / ('ds39_%s_off.png' % v)); on = rgb(U / 'onoff' / ('ds39_%s_mura.png' % v))
    L0 = lum(off); r = lum(on) / np.maximum(L0, 1e-3) - 1.0
    g = np.clip(128 + r * GAIN * 255, 0, 255).astype(np.uint8)
    g[L0 < 0.03] = 128
    a = label(cv2.resize(on, (960, 540), interpolation=cv2.INTER_AREA).copy(), '(2) mura ON  ' + t)
    b = label(cv2.cvtColor(cv2.resize(g, (960, 540), interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2RGB), '(2) mura / OFF - 1  (x%d, grey = 0)  ' % GAIN + t)
    panels.append(np.hstack([a, b]))
put_png(np.vstack(panels), 'fig_ds39_mura_seams.png', 'ds39_record.py が unity/onoff/ の seat_toward_wave_t105・seat_t120 の mura と off から作った')
figures['fig_ds39_mura_seams.png'] = dict(source='ds39_record.py（unity/onoff/ の mura・off）', gain=GAIN)

# ---- 7. 動画と JSON の写し
videos = {}
for n in sorted(os.listdir(U / 'video')):
    src = U / 'video' / n
    if src.stat().st_size > MB5:
        stop('5 MB を超える ' + n)
    dst = EV / n
    shutil.copyfile(src, dst)
    videos[n] = dict(source=rel(src), bytes=dst.stat().st_size, sha256=sha(dst))
    copies[rel(dst)] = dict(source=rel(src), sha256=videos[n]['sha256'], bytes=videos[n]['bytes'])
for n, src in (('ds39_acceptance.json', P / 'ds39_acceptance.json'), ('ds39_paper_metrics.json', P / 'ds39_paper_metrics.json'),
               ('ds39_run.json', P / 'ds39_run.json'), ('ds39_spray_dense_log.json', P / 'spray/ds39_spray_dense_log.json')):
    dst = EV / n
    shutil.copyfile(src, dst)
    copies[rel(dst)] = dict(source=rel(src), sha256=sha(dst), bytes=dst.stat().st_size)

# ---- 8. 進行役の独立の検査（写しは Git 対象外の indep_check/。値は swim_indep.json から）
indep = {}
ij = IND / 'swim_indep.json'
if ij.exists():
    d = jload(ij)
    for pair, v in d.items():
        indep[pair] = {('hero' if s == '1' else 'near' if s == '2' else 'far' if s == '3' else s):
                       {c: dict(N=round(v[s][c]['N'], 4), N_screen=round(v[s][c]['N_screen'], 4), S=round(v[s][c]['S'], 4), F_std=round(v[s][c]['Fstd'], 5), n=v[s][c]['n'])
                        for c in ('paper', 'mura')} for s in v}
indep_files = {p.name: sha(p) for p in sorted(IND.glob('*')) if p.is_file()} if IND.exists() else {}

# ---- 9. metrics.json
sw = met['swim']
pd = met['perf_delta_vs_base']
pf = met['perf']


def gpu_row(var, cond):
    return {tag: dict(median=pf[tag]['rows'][var + '|' + cond]['gpu_median_ms'], p95=pf[tag]['rows'][var + '|' + cond]['gpu_p95_ms'],
                      zero_frac=pf[tag]['rows'][var + '|' + cond]['gpu_zero_frac'], n=pf[tag]['rows'][var + '|' + cond]['gpu_n'],
                      spray_count=pf[tag]['rows'][var + '|' + cond]['spray_count']) for tag in ('run1', 'run2')}


swim_rows = {}
for view in ('seat_toward_wave_t090', 'seat_t120'):
    for pair, r in sw[view].items():
        swim_rows[view + ' ' + pair] = dict(disp_px_median=r['disp_px_median'],
                                            paper=dict(S=r['paper']['S'], N=r['paper']['N'], N_screen_fixed_control=r['paper']['N_screen_fixed_control'],
                                                       by_sheet={k: v['N'] for k, v in r['paper']['by_sheet'].items()}),
                                            mura=dict(S=r['mura']['S'], N=r['mura']['N'], N_screen_fixed_control=r['mura']['N_screen_fixed_control'],
                                                      by_sheet={k: v['N'] for k, v in r['mura']['by_sheet'].items()}))
paper_N = [r['paper']['N'] for r in swim_rows.values()]
paper_S = [r['paper']['S'] for r in swim_rows.values()]
mura_N = [r['mura']['N'] for r in swim_rows.values()]
paper_ctrl = [r['paper']['N_screen_fixed_control'] for r in swim_rows.values()]
mura_ctrl = [r['mura']['N_screen_fixed_control'] for r in swim_rows.values()]
hero_by_sheet = [r['paper']['by_sheet'].get('1') for k, r in swim_rows.items() if k.startswith('seat_toward_wave')]

fr_start = (P / '_started.txt').read_text(encoding='utf-8').strip()
metrics = {
    'schema': 'GreatWave.Design39.metrics/1',
    'number': '設計39：紙・摺り・小飛沫を一つずつ加える（オン/オフ、追加 GPU 時間）',
    'evidence_kind_ja': ('Unity 6000.4.3f1 の Editor の batchmode の PC オフスクリーン描画（camera.Render、RTX 3080、Direct3D11）と、Release の Windows プレイヤー '
                         'DS39Perf.exe の PC の実測（FrameTiming。RTX 3080 の代理）、numpy/OpenCV/scikit-image の評価。頭の揺れは座席のカメラを右の向きへずらした PC の描画で、'
                         'HMD の頭の追跡ではない。HMD 実機（PS VR2）の結果ではない。'),
    'acceptance': {
        'off_does_not_disturb_de00': dict(
            criterion_ja='評価と原画比較は全部切で行う（ΔE00 の測定を乱さない）。既定は全部切',
            builder=acc['acceptance'][0]['value'], builder_verdict=acc['acceptance'][0]['verdict'],
            recorder=dict(files_compared=ident['files'], png=ident['png'], other=ident['other'], differ=ident['differ'], only_one_side=ident['only_one_side'],
                          regress_same_file=ident['regress_same_file'], regress_sha256=ident['regress_sha256_ds39']),
            scene_defaults=scene_defaults, verdict='合格'),
        'no_swim_with_head_motion': dict(
            criterion_ja=('入れても頭の移動（±0.1 m）で質感が泳がない。作る部の定義：面の座標の升（格子の 1/64）ごとの表でコマ B を予測した残り ÷ 模様の散らばり = N、'
                          '÷ 画面の同じ画素の差 = S。① は S・N ≤ 0.35、② は N ≤ 0.35（すべての組、画素は主役波・near・far をまとめて）。利得 15 の描画'),
            paper=dict(S_range=[min(paper_S), max(paper_S)], N_range=[min(paper_N), max(paper_N)], N_screen_fixed_control_range=[min(paper_ctrl), max(paper_ctrl)]),
            mura=dict(N_range=[min(mura_N), max(mura_N)], N_screen_fixed_control_range=[min(mura_ctrl), max(mura_ctrl)]),
            rows=swim_rows, hero_sheet_paper_N_seat_toward_wave=hero_by_sheet,
            bin_sweep_pair_m100_p100=met['swim_Q_sweep_pair_m100_p100'], builder_verdict=acc['acceptance'][1]['verdict'],
            indep_check=indep, verdict='合格（PC 描画の揺れ。HMD は保留）'),
        'onoff_images_and_gpu': dict(
            criterion_ja='各オン/オフの画像と追加 GPU 時間（成果物）',
            images=sorted(p.name for p in (U / 'onoff').glob('*.png')), gpu_delta_median_ms=acc['acceptance'][2]['value']['gpu_delta_median_ms'],
            gpu_all_on_proxy=gpu_row('all', 'proxy_stereo_seat'), gpu_base_proxy=gpu_row('base', 'proxy_stereo_seat'),
            verdict='作った（記録）'),
    },
    'record_only': {
        'onoff_de00_builder': met['onoff_de00_vs_off'],
        'onoff_recorder': onoff,
        'player_screens_recorder': player,
        'perf_rows': {k: {tag: pf[tag]['rows'][k] for tag in ('run1', 'run2')} for k in pf['run1']['rows']},
        'perf_delta_vs_base': pd,
        'spray_dense': {k: spray_log[k] for k in ('parents', 'children_made', 'children_kept', 'rejected_by_150', 'total_with_parents', 'density_ratio',
                                                    'child_radius_m', 'alive_children_at_t', 'first_child_t', 'params')},
        'render_report_rest': rrep['rest'], 'render_report_mesh_targets': len(rrep['meshTargets']),
        'render_report_mesh_targets_by_shader': {s: sum(1 for m in rrep['meshTargets'] if m['shader'] == s) for s in sorted({m['shader'] for m in rrep['meshTargets']})},
        'render_report_note_ja': 'unity/ds39_render_report.json は利得 15 の揺れの描き直し（-Log swim15）で上書きされ、t28Files・images・videos・scene39 が空。最初の実行の記録は logs/unity_ds39_render.log',
    },
    'regression_plan_2_0': dict(
        evaluator_output_same_as_ds38=ident['regress_same_file'], sha256=ident['regress_sha256_ds39'], values_in_file=112,
        key_values=acc['regression']['key_values'], builder_values_compared=acc['regression']['values_compared'],
        protected_unchanged=run['unity_protected_unchanged'], build_protected_unchanged=build['protectedUnchanged'],
        ds38_materials_after_ds39_runs=ds38_mats, verdict='合格（後退なし。全部切は設計38 と同じ）'),
    'fix_rounds': dict(used=0, note_ja='修正の回は使っていない（Q26 の 1 回は残した）。頭の揺れの測り方を受入の判定の前に 2 回直した（製品は変えていない）',
                       measurement_corrections=[sw['note_ja']]),
    'recorder_crosscheck': dict(builder_sha256_checked=checked, t28_identity=ident, logs=logs),
    'backlog': {
        'plan_2_3_off_de00': dict(value='全部切の t* の組 %d ファイル（PNG %d・ほか %d）が設計38 と同じ。評価器の出力が設計38 と SHA-256 まで同じ（%s…）。場面の既定は全部切'
                                        % (ident['files'], ident['png'], ident['other'], ident['regress_sha256_ds39'][:8]), verdict='合格'),
        'plan_2_3_no_swim': dict(value='① S %.3f〜%.3f・N %.3f〜%.3f（画面に貼り付けた対照 N %.2f〜%.2f）、② N %.3f〜%.3f（対照 %.2f〜%.2f）。基準 0.35'
                                       % (min(paper_S), max(paper_S), min(paper_N), max(paper_N), min(paper_ctrl), max(paper_ctrl), min(mura_N), max(mura_N),
                                          min(mura_ctrl), max(mura_ctrl)), verdict='合格（PC 描画の揺れ。HMD は保留）'),
        'plan_2_3_onoff_gpu': dict(value='入切の画像 %d 枚、立体の代理の GPU の中央値の差（run1／run2）① +%.3f／+%.3f・② +%.3f／+%.3f・③ +%.3f／+%.3f・全部 +%.3f／+%.3f ms'
                                         % (len(list((U / 'onoff').glob('*.png'))), pd['paper']['proxy_stereo_seat']['run1']['d_median_ms'], pd['paper']['proxy_stereo_seat']['run2']['d_median_ms'],
                                            pd['mura']['proxy_stereo_seat']['run1']['d_median_ms'], pd['mura']['proxy_stereo_seat']['run2']['d_median_ms'],
                                            pd['spray']['proxy_stereo_seat']['run1']['d_median_ms'], pd['spray']['proxy_stereo_seat']['run2']['d_median_ms'],
                                            pd['all']['proxy_stereo_seat']['run1']['d_median_ms'], pd['all']['proxy_stereo_seat']['run2']['d_median_ms']),
                                   verdict='作った（記録）'),
        'plan_2_0_regression': dict(value='評価器の 112 個の値が設計38 と同じ', verdict='合格（後退なし）'),
    },
    'hmd': 'PS VR2 の実機での見え方・GPU 時間・立体視（SPI）は保留（Q24。導入は利用者の手）',
    'time': dict(box_ja='Q26 の日程で 2 時間（計画の時間枠は ≤0.5 日）', builder_started=fr_start, builder_readme_ja='作る部の README の題：07:36〜08:10ごろ（約 35 分）',
                 builder_last_file=mtime(P / 'README_interface.txt'), spray_made=mtime(P / 'spray/ds39_spray_dense_frames.bin'),
                 unity_render_log=mtime(P / 'logs/unity_ds39_render.log'), unity_swim15_log=mtime(P / 'logs/unity_ds39_swim15.log'),
                 build_report=mtime(P / 'ds39_build_report.json'), perf_run1=mtime(P / 'perf/run1/ds39_run1.json'), perf_run2=mtime(P / 'perf/run2/ds39_run2.json'),
                 evaluator=mtime(reg39), metrics=mtime(P / 'ds39_paper_metrics.json'), builder_run_json=mtime(P / 'ds39_run.json'),
                 indep_check_files=[min(mtime(p) for p in IND.glob('*')), max(mtime(p) for p in IND.glob('*'))] if indep_files else None,
                 unity_seconds_render=float(re.search(r'DS39_RENDER_DONE seconds=([0-9.]+)', (P / 'logs/unity_ds39_render.log').read_text(encoding='utf-8', errors='replace')).group(1)),
                 unity_seconds_swim15=round(rrep['secondsTotal'], 1), build_seconds=round(build['buildSeconds'], 1),
                 eval_seconds=met['eval_seconds'], spray_seconds=spray_log['seconds']),
}
with open(EV / 'metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)

# ---- 10. run.json
code = {rel(p): sha(p) for p in sorted((ROOT / 'Tools/GWWaveGen/ds39').glob('*')) if p.is_file() and p.suffix in ('.py', '.ps1')}
code.update({rel(p): sha(p) for p in sorted((ROOT / 'Unity/Assets/GreatWave/Design39').rglob('*')) if p.is_file()})
runj = {
    'schema': 'GreatWave.Design39.run/1',
    'commands': run['commands'] + ['py -3.10 -B Tools/GWWaveGen/ds39/ds39_record.py（記録。約 1〜2 分）'],
    'environment': dict(run['tools'], python_record=platform.python_version(), numpy=np.__version__, opencv=cv2.__version__),
    'code_sha256': code,
    'inputs_sha256': run['inputs_sha256'],
    'protected_files': run['unity_protected_files'], 'protectedUnchanged': run['unity_protected_unchanged'],
    'build': dict(build_report=build),
    'builder_outputs_sha256_checked': checked,
    'regress_json': dict(ds39=rel(reg39), ds38=rel(reg38), sha256=ident['regress_sha256_ds39']),
    'figures': figures, 'videos': videos, 'copies': copies,
    'indep_check_files_sha256': indep_files,
    'not_kept_note_ja': ('Git 対象外（Unity/Build/Design/39/）：作る部の全出力 paper/（Unity の描画、入切・揺れの画像、動画、評価器の出力、プレイヤーと計時、小飛沫のデータ、ログ）、'
                         '進行役の独立の検査の写し indep_check/、記録の点検 record/'),
    'not_used_ja': ('参照モデル・利用者の解算・写真のフォルダー・禁止の場所・Blender・Houdini は、作る部・検査・記録のどれも使っていない。爪形分析のフォルダーは、'
                    '記録の時のコミットの一覧の点検でファイルの大きさと SHA-256 を読み取りのみで調べただけ。git は使っていない。'),
    'record_run': dict(seconds=round(time.time() - T0, 1), finished=time.strftime('%Y-%m-%d %H:%M:%S')),
}
with open(EV / 'run.json', 'w', encoding='utf-8') as f:
    json.dump(runj, f, ensure_ascii=False, indent=1)
print('証拠', len(copies) + 2, 'ファイル', rel(EV), round(time.time() - T0, 1), 's')
