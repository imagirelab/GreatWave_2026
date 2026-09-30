# -*- coding: utf-8 -*-
# 設計41 の記録の道具（記録の部）。作る部の出力（Git 対象外の Unity/Build/Design/41/）から、証拠 Docs/Evidence/Design/41/ を作る：
#   - 作る部のコード・資産・出力が ds41_model_run.json の SHA-256 のままかを確かめる（違えば止まる）。調べの表の SHA-256 も確かめる
#   - 守るファイル（DS41 の描画の報告の protectedFiles）の SHA-256 が今も同じか
#   - 記録の照合（作る部の比べのコードを使わない数え直し）：
#       ・評価器23 の出力（設計41・設計40 × 線なし・線あり）から 74・75・157・159・71・76・213・78〜72・212 を読み直し、CP1 の値（CP1 の metrics.json、a45）と並べる
#       ・進行役の独立の検査の評価器の出し直し（indep_check/eval_*）が作る部の出力と同じか
#       ・回帰の評価器の出力 ds30_tstar_regress.json が設計40 と同じファイルか。t* の組（t28_claws・t28_white）のファイルを設計40 と比べる（PNG は画素、ほかはバイト）
#       ・原画視点の色画像・全体の ID 画像の設計40 との違いが船の所だけか。置き換えの前の対照の描画が設計40 と同じか。座席などの視点の違い
#       ・ID 画像の船の色の画素の数と、右船の bbox（69）
#   - 図（1920×1080。1920×1080 でない図は縮小と白の余白で 1920×1080 にする）と JSON を写し、metrics.json・run.json を書く
# 値はすべて、ここで読んだファイルから取る（作る部の値は書き換えない）。
# 使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds41/ds41_record.py（約 30 秒）
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
from PIL import Image, ImageDraw, ImageFont

T0 = time.time()
ROOT = Path(__file__).resolve().parents[3]
assert (ROOT / 'AGENTS.md').exists(), ROOT
B41 = ROOT / 'Unity/Build/Design/41'
M = B41 / 'model'
U = M / 'unity'
RS = B41 / 'research'
IND = B41 / 'indep_check'
C40 = ROOT / 'Unity/Build/Design/40/compare'
U40 = C40 / 'unity'
EV = ROOT / 'Docs/Evidence/Design/41'
EV40 = ROOT / 'Docs/Evidence/Design/40'
W, H = 1920, 1080
FONT = r'C:\Windows\Fonts\YuGothM.ttc'
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


def stop(msg):
    print('STOP:', msg)
    sys.exit(1)


def rgb(p):
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if im is None:
        stop('読めない ' + str(p))
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def mtime(p):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(Path(p).stat().st_mtime))


EV.mkdir(parents=True, exist_ok=True)

# ---- 1. 作る部の SHA-256 の照合
run = jload(M / 'ds41_model_run.json')
checked, mism = 0, []
for sec in ('inputs', 'code', 'unity_assets', 'outputs_blender', 'outputs_unity', 'outputs_eval'):
    for k, v in run[sec].items():
        want = v if isinstance(v, str) else v['sha256']
        p = ROOT / k
        checked += 1
        if not p.exists() or sha(p) != want:
            mism.append(k)
for k, v in run['figures'].items():
    checked += 1
    if sha(M / 'fig' / k) != v['sha256']:
        mism.append('fig/' + k)
if mism:
    stop('作る部のファイルが ds41_model_run.json の SHA-256 と違う：%s' % mism[:10])
RESEARCH = RS / 'oshiokuri_dimensions.json'
research_sha = sha(RESEARCH)
if research_sha != run['inputs']['Unity/Build/Design/41/research/oshiokuri_dimensions.json']:
    stop('調べの表の SHA-256 が違う')
print('builder sha256 checked', checked)

# ---- 2. 守るファイル
rr = jload(U / 'ds41_render_report.json')
prot, prot_bad = 0, []
for line in rr['protectedFiles']:
    path, want = line.rsplit(' ', 1)
    prot += 1
    if sha(ROOT / 'Unity' / path) != want:
        prot_bad.append(path)
if prot_bad:
    stop('守るファイルが変わった：%s' % prot_bad)
br = jload(U / 'ds41_build_report.json')
scene39_now = sha(ROOT / 'Unity/Assets/GreatWave/Design39/Scenes/DS39_Paper.unity')

# ---- 3. 調べの表の数え
rs = jload(RESEARCH)
research_counts = dict(sources_read=len(rs['sources']), held_sources=len(rs['held_sources']), source_values=len(rs['source_values']),
                       painting_estimates=len(rs['painting_estimates']['estimates']), adopted_items=len(rs['adopted_for_model']['items']),
                       adopted_source=sum(1 for i in rs['adopted_for_model']['items'] if i['kind'] == 'source'),
                       adopted_estimate=sum(1 for i in rs['adopted_for_model']['items'] if i['kind'] == 'estimate'))

# ---- 4. 評価器23 の読み直し
EVAL = {'41_noline': M / 'eval/off_noline/metrics.json', '41_line': M / 'eval/off_line/metrics.json',
        '40_noline': C40 / 'eval/off_noline/metrics.json', '40_line': C40 / 'eval/off_line/metrics.json'}
E = {k: jload(v) for k, v in EVAL.items()}
ITEMS = ['74', '75', '157', '159', '71', '76', '213', '78', '130', '131', '132', '72', '212']


def measures(run_name, item):
    out = []
    for m in E[run_name]['items'][item]['measures']:
        d = dict(target=m.get('target'), verdict=m.get('verdict'))
        if 'value_max_px' in m:
            d.update(max_px=m['value_max_px'], p95_px=m['p95_px'], worst_display_xy=m.get('worst_display_xy'))
        elif 'value' in m:
            d.update(value=m['value'])
        out.append(d)
    return out


eval_table = {it: {k: measures(k, it) for k in E} for it in ITEMS}
cp1 = jload(ROOT / 'Docs/Evidence/ArtFirst/CP1/metrics.json')['items']
boats = {}
for it, tgt in (('74', 'fuji_ridge'), ('75', 'boat_fg'), ('157', 'boat_left'), ('159', 'boat_mid')):
    a = eval_table[it]['41_noline'][0]
    b = eval_table[it]['40_noline'][0]
    c = cp1[it]['by_interpretation']['a45']
    boats[it] = dict(target=tgt, ds41_max_px=a['max_px'], ds41_p95_px=a['p95_px'], ds40_max_px=b['max_px'], ds40_p95_px=b['p95_px'],
                     cp1_max_px=c['max_px'], cp1_p95_px=c['p95_px'],
                     change_vs_cp1_max_px=round(a['max_px'] - c['max_px'], 4), change_vs_cp1_p95_px=round(a['p95_px'] - c['p95_px'], 4),
                     change_vs_ds40_max_px=round(a['max_px'] - b['max_px'], 4), change_vs_ds40_p95_px=round(a['p95_px'] - b['p95_px'], 4),
                     line_ids_ds41=eval_table[it]['41_line'][0], worst_display_xy_ds41=a['worst_display_xy'])
indep_same = {}
for mode in ('noline', 'line'):
    a = jload(M / ('eval/off_%s/metrics.json' % mode))['items']
    b = jload(IND / ('eval_off_%s/metrics.json' % mode))['items']
    indep_same[mode] = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---- 5. 回帰の照合
def cmp_img(a, b):
    A, B = rgb(a), rgb(b)
    if A.shape != B.shape:
        return dict(shape_differs=True)
    d = np.abs(A.astype(np.int16) - B.astype(np.int16)).max(-1)
    return dict(differing_px=int((d > 0).sum()), max_step=int(d.max()))


def numeric_leaves(x, pre=''):
    # JSON の数と真偽の葉だけ（パス・時刻などの文字列は比べない）
    out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            out.update(numeric_leaves(v, pre + '/' + str(k)))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(numeric_leaves(v, pre + '[%d]' % i))
    elif isinstance(x, (bool, int, float)) and x is not None:
        out[pre] = x
    return out


regress = dict(ds41=sha(U / 'ds30_tstar_regress.json'), ds40=sha(U40 / 'ds30_tstar_regress.json'))
regress['same'] = regress['ds41'] == regress['ds40']
t28 = {}
for s in ('t28_claws', 't28_white'):
    base41, base40 = U / s, U40 / s
    files = sorted(p.relative_to(base41).as_posix() for p in base41.rglob('*') if p.is_file())
    files40 = sorted(p.relative_to(base40).as_posix() for p in base40.rglob('*') if p.is_file())
    only = sorted(set(files) ^ set(files40))
    differ_png, differ_json_bytes, differ_json_numbers, differ_other = [], [], {}, []
    for f in sorted(set(files) & set(files40)):
        a, b = base41 / f, base40 / f
        if f.endswith('.png'):
            if cmp_img(a, b).get('differing_px', 1):
                differ_png.append(f)
        elif f.endswith('.json'):
            if sha(a) != sha(b):
                differ_json_bytes.append(f)
                na, nb = numeric_leaves(jload(a)), numeric_leaves(jload(b))
                dk = sorted(k for k in set(na) | set(nb) if na.get(k) != nb.get(k))
                if dk:
                    differ_json_numbers[f] = dict(count=len(dk), first=dk[:6])
        else:
            if a.stat().st_size != b.stat().st_size or sha(a) != sha(b):
                differ_other.append(f)
    t28[s] = dict(files=len(files), files_ds40=len(files40), only_one_side=only, png=sum(1 for f in files if f.endswith('.png')),
                  differ_png=differ_png, differ_json_bytes=differ_json_bytes, differ_json_numeric_leaves=differ_json_numbers,
                  differ_other=differ_other)
# 原画視点の色画像と ID 画像
BOATC = {'boat_left': (34, 0, 0), 'boat_mid': (0, 34, 0), 'boat_fg': (34, 34, 0)}
id41, id40 = rgb(U / 'full/ids_noline.png'), rgb(U40 / 'full/ids_noline.png')


def boatmask(ids):
    m = np.zeros(ids.shape[:2], bool)
    for c in BOATC.values():
        m |= np.all(ids == np.array(c, np.uint8), -1)
    return m


bm41, bm40 = boatmask(id41), boatmask(id40)
idd = np.any(id41 != id40, -1)
p41, p40 = rgb(U / 'full/painting_t120_off.png'), rgb(U40 / 'full/painting_t120_off.png')
pd = np.any(p41 != p40, -1)
bm_disp = (bm41 | bm40).reshape(H, 2, W, 2).any(axis=(1, 3))
bm_dil = cv2.dilate(bm_disp.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
id_counts = {}
for k, c in BOATC.items():
    id_counts[k] = dict(ds41=int(np.all(id41 == np.array(c, np.uint8), -1).sum()), ds40=int(np.all(id40 == np.array(c, np.uint8), -1).sum()))
ys, xs = np.nonzero(np.all(id41 == np.array(BOATC['boat_mid'], np.uint8), -1))
mid_bbox_disp = [round(xs.min() / 2, 1), round(ys.min() / 2, 1), round((xs.max() + 1) / 2, 1), round((ys.max() + 1) / 2, 1)]
images = dict(
    painting_vs_ds40=dict(differing_px=int(pd.sum()), outside_boats_dilated3_px=int((pd & ~bm_dil).sum())),
    ids_noline_vs_ds40=dict(differing_px=int(idd.sum()), not_boat_in_either_px=int((idd & ~(bm41 | bm40)).sum())),
    control_blockout_painting_vs_ds40=cmp_img(U / 'views/painting_t120_off_blockout.png', U40 / 'full/painting_t120_off.png'),
    seat_vs_ds40=cmp_img(U / 'views/seat_t120_off.png', U40 / 'views/seat_t120_off.png'),
    seat_vs_blockout=cmp_img(U / 'views/seat_t120_off.png', U / 'views/seat_t120_off_blockout.png'),
    seat_low_vs_ds40=cmp_img(U / 'views/seat_low_t120_off.png', U40 / 'views/seat_low_t120_off.png'),
    seat_toward_wave_vs_ds40=cmp_img(U / 'views/seat_toward_wave_t120_off.png', U40 / 'views/seat_toward_wave_t120_off.png'),
    side_left_vs_ds40=cmp_img(U / 'views/side_left_t120_off.png', U40 / 'views/side_left_t120_off.png'),
    back_vs_ds40=cmp_img(U / 'views/back_t120_off.png', U40 / 'views/back_t120_off.png'),
    painting_ds41_sha256=sha(U / 'full/painting_t120_off.png'),
    boat_id_px_3840x2160=id_counts, boat_mid_bbox_display_px=mid_bbox_disp)
print('images', json.dumps(images, ensure_ascii=False))

# ---- 6. 図（1920×1080）
copies = {}
_font = {}


def font(sz):
    if sz not in _font:
        _font[sz] = ImageFont.truetype(FONT, sz)
    return _font[sz]


def fit_1080(im, caption=None):
    h, w = im.shape[:2]
    room = H - (44 if caption else 0)
    s = min(W / w, room / h, 1.0)
    if s < 1.0:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
    h, w = im.shape[:2]
    can = np.full((H, W, 3), 255, np.uint8)
    y0, x0 = (room - h) // 2, (W - w) // 2
    can[y0:y0 + h, x0:x0 + w] = im
    if caption:
        pil = Image.fromarray(can)
        ImageDraw.Draw(pil).text((16, H - 38), caption, fill=(0, 0, 0), font=font(24))
        can = np.asarray(pil).copy()
    return can, round(s, 4)


def put_png(img_rgb, name, src_note):
    if img_rgb.shape[:2] != (H, W):
        stop('1920×1080 でない ' + name)
    out = EV / name
    Image.fromarray(img_rgb).save(out, optimize=True)
    copies[rel(out)] = dict(source=src_note, sha256=sha(out), bytes=out.stat().st_size)


figures = {}
FIGS = [
    ('fig_ds41_painting_before_after.png', M / 'fig/fig_ds41_painting_before_after.png', None),
    ('fig_ds41_blender_model.png', M / 'fig/fig_ds41_blender_model.png', None),
    ('fig_ds41_close_before_after.png', M / 'fig/fig_ds41_close_before_after.png', None),
    ('fig_ds41_views.png', M / 'fig/fig_ds41_views.png', None),
    ('fig_ds41_76_sky_dark.png', IND / 'crop76_right.png',
     '進行役の独立の検査の切り抜き。上：評価器23 の線なしの ID の偏差図（左 設計40、右 設計41）。下：原画視点の色画像（左 設計40、右 設計41）'),
    ('fig_ds41_seat_toward_wave_40_41.png', IND / 'seat_toward_wave_40_41.png',
     '座席から波の方向 t 12 s（左 設計40：船・富士・仮置きを隠して描いた、右 設計41：隠していない）。進行役の独立の検査が並べた'),
]
for n, src, cap in FIGS:
    im = rgb(src)
    wh = [im.shape[1], im.shape[0]]
    out, s = fit_1080(im, cap)
    note = rel(src) + (' をそのまま' if wh == [W, H] and not cap else ' の %d×%d を%s白の余白で 1920×1080 に' % (
        wh[0], wh[1], ('%.3f 倍に縮めて' % s) if s < 1 else ''))
    put_png(out, n, note)
    figures[n] = dict(source=rel(src), source_sha256=sha(src), source_size=wh, scale=s)
# 評価器の重ね図と原画 50% の重ね（船の所の切り抜き 1560×560）を上下に並べる
a, b = rgb(M / 'fig/fig_ds41_eval_overlay_boats.png'), rgb(M / 'fig/fig_ds41_painting_overlay50_boats.png')
out, s = fit_1080(np.vstack([a, b]), '上：評価器23（線なしの ID）の偏差図の船の所。下：原画 50% の重ね。作る部の図 2 枚（各 1560×560）を上下に並べた')
put_png(out, 'fig_ds41_eval_overlay_boats.png', 'model/fig の fig_ds41_eval_overlay_boats.png と fig_ds41_painting_overlay50_boats.png を上下に並べ、%.3f 倍に縮めて白の余白で 1920×1080 に' % s)
figures['fig_ds41_eval_overlay_boats.png'] = dict(sources=[rel(M / 'fig/fig_ds41_eval_overlay_boats.png'), rel(M / 'fig/fig_ds41_painting_overlay50_boats.png')],
                                                 scale=s)
# 作品の画像と評価器の偏差図はバイトのまま
for n, src in (('ds41_painting_t120_off.png', U / 'full/painting_t120_off.png'),
               ('fig_ds41_contour_off_noline.png', M / 'eval/off_noline/off_noline_overlay.png'),
               ('fig_ds41_contour_off_line.png', M / 'eval/off_line/off_line_overlay.png')):
    if rgb(src).shape[:2] != (H, W):
        stop('1920×1080 でない ' + n)
    dst = EV / n
    shutil.copyfile(src, dst)
    copies[rel(dst)] = dict(source=rel(src) + ' をバイトのまま', sha256=sha(dst), bytes=dst.stat().st_size)
    figures[n] = dict(source=rel(src), source_sha256=sha(src))

# ---- 7. JSON の写し
for n, src in (('ds41_oshiokuri_dimensions.json', RESEARCH), ('ds41_model_metrics.json', M / 'ds41_model_metrics.json'),
               ('ds41_model_run.json', M / 'ds41_model_run.json'), ('ds41_blender_report.json', M / 'blender/ds41_blender_report.json'),
               ('ds41_import_check.json', U / 'ds41_import_check.json'), ('ds41_build_report.json', U / 'ds41_build_report.json'),
               ('ds41_render_report.json', U / 'ds41_render_report.json'),
               ('ds41_eval_off_noline_metrics.json', M / 'eval/off_noline/metrics.json'), ('ds41_eval_off_line_metrics.json', M / 'eval/off_line/metrics.json'),
               ('ds41_indep_check.json', IND / 'indep41.json'), ('ds41_indep_raster.json', IND / 'indep41_raster.json')):
    dst = EV / n
    shutil.copyfile(src, dst)
    copies[rel(dst)] = dict(source=rel(src), sha256=sha(dst), bytes=dst.stat().st_size)

# ---- 8. ログ
logs = {}
for lp in sorted((M / 'logs').glob('*.log')):
    lines = lp.read_text(encoding='utf-8', errors='replace').splitlines()
    err = [l for l in lines if re.search(r'error', l, re.I)]
    logs[rel(lp)] = dict(lines=len(lines), error_lines=len(err), compile_or_shader_errors=len([l for l in err if re.search(r'error CS\d|Shader error', l)]),
                         licensing=len([l for l in err if 'Licensing' in l]), other=[l[:160] for l in err if 'Licensing' not in l][:5],
                         warnings_cs=len([l for l in lines if re.search(r'warning CS\d', l)]),
                         warnings_cs_design41=len([l for l in lines if re.search(r'warning CS\d', l) and 'Design41' in l]))
rlog = (M / 'logs/unity_ds41_Render.log').read_text(encoding='utf-8', errors='replace')
render_done = re.search(r'DS41_RENDER_DONE seconds=([0-9.]+) protectedUnchanged=(\w+)', rlog)
ilog = (M / 'logs/unity_ds41_ImportCheck.log').read_text(encoding='utf-8', errors='replace')
import_done = re.search(r'DS41_IMPORT_CHECK .*', ilog)
blog = (M / 'logs/unity_ds41_BuildScene.log').read_text(encoding='utf-8', errors='replace')
build_done = re.search(r'DS41_BUILD_DONE .*', blog)
restores = {p.name: jload(p)['restored'] for p in sorted((M / 'logs').glob('ds41_settings_restore_*.json'))}

# ---- 9. metrics.json
mm = jload(M / 'ds41_model_metrics.json')
bl = jload(M / 'blender/ds41_blender_report.json')
ind = jload(IND / 'indep41.json')
ras = jload(IND / 'indep41_raster.json')
ic = jload(U / 'ds41_import_check.json')
seat = mm['seat_v1_vs_gunwale']
r76 = dict(line_ids=dict(ds41=eval_table['76']['41_line'], ds40=eval_table['76']['40_line']),
           noline_ids=dict(ds41=eval_table['76']['41_noline'], ds40=eval_table['76']['40_noline']))
metrics = dict(
    schema='GreatWave.Design41.metrics/1',
    number='設計41：仮船を資料に基づく Blender モデルへ置き換える（船体・船縁・操作物、衝突形状、浮力用形状）',
    evidence_kind_ja=('ウェブのページの読み（ダウンロードなし）、Blender 5.2.2 のヘッドレスの制作と往復の検査、Unity 6000.4.3f1 の Editor の batchmode の取り込みの検査と'
                      ' PC オフスクリーン描画（camera.Render、RTX 3080、Direct3D11）、その画像の numpy/OpenCV の測定と評価器（Tools/PaintingTruth/evaluate.py、'
                      'ds30b_tstar_regress.py）。HMD 実機（PS VR2）の結果ではない。Mock の両眼も描いていない。'),
    acceptance=dict(
        criterion_ja='計画 §2.4 設計41 の最小の受入：Unity で尺度・軸・左右の反転なし（設計07 の検査）。原画視点の 74・75・157・159 を記録し、CP1 からの変化を示す（判定は仕上げ40・41）。座席 v1 の目の高さと船縁の関係を記録。＋計画 §2.0 の回帰なし',
        design07=dict(verdict='合格', import_check_pass=ic['pass'], scale=ic['scalePass'], axis=ic['axisPass'], mirror=ic['mirrorPass'], normals=ic['normalsPass'],
                      tip_to_tip_units=ic['tipToTip'], beam_units=ic['beam'], bounds_max_abs_diff=ic['boundsMaxAbsDiff'], triple=ic['triple'],
                      starboard_oars_plusX=ic['starboardOarsPlusX'], port_oars_minusX=ic['portOarsMinusX'],
                      hull_outward=[ic['hullTrianglesOutward'], ic['hullTrianglesChecked']],
                      indep_raster_id_not_in_raster=dict((k, {m: v[m]['id_not_in_raster_frac'] for m in v if m != 'id_px'}) for k, v in ras.items())),
        record_74_75_157_159=dict(verdict='記録のみ（判定は仕上げ40・41）', values=boats),
        seat_v1_vs_gunwale=dict(verdict='記録した', builder=seat, indep=ind['seat']),
        regression=dict(verdict='合格（後退した項目 0）', regress_json_same_as_ds40=regress['same'],
                        silhouettes_78_130_131=mm['regression']['silhouettes_78_130_131_max_px'], lfgate=mm['regression']['lfgate'],
                        geometry_items=mm['regression']['geometry_items'])),
    research=dict(file='Unity/Build/Design/41/research/oshiokuri_dimensions.json', sha256=research_sha, counts=research_counts,
                  source_values=rs['source_values'], painting_estimates=rs['painting_estimates']['estimates'],
                  adopted_for_model=rs['adopted_for_model']['items'], held_sources=rs['held_sources'],
                  current_blockouts=rs['current_blockouts'], seat_estimate=rs['seat_v1_vs_gunwale']),
    model=dict(params_sha256=bl['params']['sha256'], frame=bl['coordinates'], derived_units=bl['derived_units'], tips=bl['tips'],
               parts=mm['model']['parts'], collision=mm['model']['collision'], buoyancy_hull_volume_units3_blender=mm['model']['buoyancy_hull_volume_units3'],
               buoyancy_hull_volume_units3_imported_fbx=ind['model_blender_frame']['buoyancy_signed_volume'],
               hydrostatics_table_units=mm['model']['hydrostatics_table_units'], buoyancy_points=mm['model']['buoyancy_points'],
               hydrostatics_boat_mid_at_research_draft=mm['model']['hydrostatics_boat_mid_at_research_draft'],
               real_dimensions_per_boat=mm['model']['real_dimensions_per_boat'], root_position_diff_vs_ds40_m=mm['model']['root_position_diff_vs_ds40_m'],
               tip_projection_diff_px=mm['painting_view_tip_projection']['values'], blender_checks=mm['model']['blender_checks'],
               export_flags=bl['export_flags'], roundtrip=bl['roundtrip'], indep_model=ind['model_blender_frame']),
    evaluator_table=eval_table,
    record_only=dict(item71=eval_table['71'], item76=r76, item213=eval_table['213'],
                     note_ja='71・76・213 は Q7 の既定で記録のみ。空の項目の読みは設計40 と同じく線ありの ID（76 暗い空の範囲は 37.4511 px のまま、p95 19.2455 → 17.914、下の ΔE00 0.2224 → 0.2872）。線なしの ID では 76 は 61.0855 → 188.7176 px（p95 22.3257 → 111.0935）に悪くなった（右船の船尾の所）'),
    regression_plan_2_0=dict(regress_json=regress, t28_sets=t28, images=images, evaluator_indep_same=indep_same,
                             items_previously_pass=mm['regression']['items_previously_pass'], regressed_items=mm['regression']['regressed_items']),
    recorder_crosscheck=dict(builder_sha256_checked=checked, protected_files_checked=prot, scene39_sha256_now=scene39_now,
                             scene39_before=br['scene39Sha256Before'], scene39_after=br['scene39Sha256After'], logs=logs,
                             unity_done_lines=dict(import_check=import_done.group(0) if import_done else None,
                                                   build=build_done.group(0) if build_done else None,
                                                   render=render_done.group(0) if render_done else None),
                             settings_restored=restores),
    fix_rounds=dict(used=0, note_ja='修正の回は使っていない（Q26 の 1 回は残した）'),
    hmd='PS VR2 の確かめ（座席 v1 から船縁越しの見え方、新しい船体の立体視）と Mock の両眼は保留（Q24。導入は利用者の手）',
    backlog=dict(
        items_75_157_159_74=dict((k, dict(value_max_px=v['ds41_max_px'], p95_px=v['ds41_p95_px'], change_vs_cp1_max_px=v['change_vs_cp1_max_px'],
                                           verdict='記録のみ（判定は仕上げ40・41）')) for k, v in boats.items()),
        items_217_219_222=dict(verdict='記録のみ（計画 §2.4 の割り当て）', note_ja='値は船の寸法・構造・部品の表（model・research）に記録した。項目の文言はバックログの定義シートにある'),
        item_89=dict(verdict='設計42 へ', note_ja='喫水と排水容積の表・浮力点の案を渡す（model.hydrostatics_table_units・buoyancy_points）')),
    time=dict(box_ja='Q26 の日程で 5 時間（計画の時間枠は ≤1 日）',
              stage7_commit='2026-09-30 09:29:55（段階7確認のコミット 8af8d75 の時刻）',
              research_table=mtime(RESEARCH), blender_first_save=mtime(M / 'blender/ds41_oshiokuri.blend1'),
              blender_last=mtime(M / 'blender/ds41_oshiokuri.fbx'), unity_import_check=mtime(U / 'ds41_import_check.json'),
              unity_build=mtime(U / 'ds41_build_report.json'), unity_render=mtime(U / 'ds41_render_report.json'),
              regress=mtime(U / 'ds30_tstar_regress.json'), eval=mtime(M / 'eval/off_line/metrics.json'),
              builder_last=mtime(M / 'ds41_model_run.json'), indep_first=mtime(IND / 'indep41_blender.py'),
              indep_last=mtime(IND / 'seat_toward_wave_40_41.png'),
              render_seconds=float(render_done.group(1)) if render_done else None),
    copies=copies,
)
with open(EV / 'metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)

# ---- 10. run.json
code = {}
for p in sorted((ROOT / 'Tools/GWWaveGen/ds41').glob('*')):
    if p.is_file():
        code[rel(p)] = sha(p)
assets = {}
for p in sorted((ROOT / 'Unity/Assets/GreatWave/Design41').rglob('*')):
    if p.is_file():
        assets[rel(p)] = sha(p)
assets['Unity/Assets/GreatWave/Design41.meta'] = sha(ROOT / 'Unity/Assets/GreatWave/Design41.meta')
runj = dict(
    schema='GreatWave.Design41.run/1',
    commands=[
        'py -3.10 -B Tools/GWWaveGen/ds41/ds41_research_table.py（調べの表。値は調べの部がウェブのページで読んだもの。原画は SHA-256 を取るだけ）',
        '"G:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/ds41/ds41_boat_blender.py',
        'py -3.10 -B Tools/GWWaveGen/ds41/ds41_stage_unity.py',
        'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.ImportCheck -Log ImportCheck',
        'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.BuildScene -Log BuildScene',
        'powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.Render -Log Render',
        'py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/41/model/unity --sets t28_claws,t28_white',
        'py -3.10 -B Tools/GWWaveGen/ds41/ds41_compare.py（評価器23 を 2 回。--skip-eval で読み直しだけ）',
        'py -3.10 -B Tools/GWWaveGen/ds41/ds41_record.py（記録）'],
    evaluator_commands=mm['evaluator_commands'],
    environment=dict(python=platform.python_version(), numpy=np.__version__, opencv=cv2.__version__, platform=platform.platform(),
                     blender=run['tools']['blender'], unity=run['tools']['unity'], device=run['tools']['device'], graphics_api=run['tools']['graphics_api']),
    code_sha256=code, unity_assets_sha256=assets, inputs_sha256=run['inputs'],
    builder_outputs_sha256_checked=checked, protected_files=rr['protectedFiles'], protectedUnchanged=True,
    research=dict(path='Unity/Build/Design/41/research/oshiokuri_dimensions.json', sha256=research_sha,
                  note_ja='ウェブのページを読んだだけで、ファイルはダウンロードしていない（PDF 1 件は保留）'),
    figures=figures, copies=copies,
    indep_check_files_sha256={rel(p): sha(p) for p in sorted(IND.rglob('*')) if p.is_file()},
    not_kept_note_ja=('Git 対象外（Unity/Build/Design/41/）：調べの表と覚え書き research/、作る部の全出力 model/（.blend・FBX の制作元、Blender の画像、'
                      'Unity の描画、t* の組、全体の合成の色と ID の画像、視点の画像、評価器の出力、図、ログ）、進行役の独立の検査の写し indep_check/、記録の点検 record/'),
    not_used_ja=('参照モデルの OBJ・利用者の解算・写真のフォルダー・禁止の場所・Houdini は、調べ・作る部・検査・記録のどれも使っていない。'
                 '参照モデルは船に使わない（D20）。原画は Docs/References の Met の画像（調べの部が SHA-256 を取り、絵の推定を読んだ）。'),
    record_run=dict(seconds=round(time.time() - T0, 1), finished=time.strftime('%Y-%m-%d %H:%M:%S')),
)
with open(EV / 'run.json', 'w', encoding='utf-8') as f:
    json.dump(runj, f, ensure_ascii=False, indent=1)
print('boats', json.dumps(boats, ensure_ascii=False))
print('t28', json.dumps(t28, ensure_ascii=False))
print('regress', regress)
print('indep eval same', indep_same)
print('logs', json.dumps(logs, ensure_ascii=False))
print('research', research_counts)
print('DS41_RECORD_DONE seconds=%.1f checked=%d protected=%d' % (time.time() - T0, checked, prot))
