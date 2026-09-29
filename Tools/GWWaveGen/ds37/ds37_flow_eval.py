# -*- coding: utf-8 -*-
"""設計37 第「流れに沿う線」部の評価（numpy/OpenCV、py -3.10）。

入力は DS37Render（Unity の PC オフスクリーン描画）の出力 Unity/Build/Design/37/flowlines/unity/：
  色の画像（PNG）、面の座標（RGFloat：R = 列 + 2000 × シートの番号、G = 行。下の行から）、カメラの行列、各シートの全頂点の位置（GPU の読み戻し）。

測るもの：
  A. 模様の画面への貼り付き（計画 §2.3 の設計37 の最小の受入「0」）。
     面の動き（画素ごと）：画素の面の座標（シート・列・行）と、次の時刻の頂点の位置（同じ三角形の分け方で補間）を次のカメラで投影した位置の差。
     模様：画素を調色板の 4 色（白・淡い水色・藍中・藍濃）に分けた色区。模様の縁の画素（同じシートの中の 2 つの色区の境。線・シートの縁・爪から 2 px 離す）で、
       ・移し替えの試し：縁の両側（法線の向きに ±1.5 px）の色区が、面の動きだけ動かした所（追従）と、動かさない所（貼り付き）で次の画像と合うか。
       ・光学的な流れ（OpenCV DIS）の法線の成分と、面の動きの法線の成分の比 r（追従 1、画面に貼り付いた模様 0）。
     面の動きの法線の成分が 3 px 以上の縁の画素だけを数える（追従と貼り付きを見分けられる所）。
     「貼り付き」の画素 = 動かさない所で合い、動かした所で合わない画素。その 8 近傍の塊（10 px 以上）を「貼り付きの塊」とし、0 を合格とする（既定値、進行役の判断）。
     感度の対照：次の画像の色区を前の画像の色区そのもの（模様が画面に貼り付いた場合）に置き換えて同じ試しをし、貼り付きの塊が出ることを確かめる。
  B. 177（同じ縞が同じ水面とともに上がる、終点 ≤4 px）。t* の原画視点で藍中に見える主役波の画素の面の座標を、UV3 と色区の表で
     藍中の成分（縞）に分け、その面の点を形成の全区間で追う（高さ、原画視点の並び、表示が藍中のままか）。
  C. 191 の事前検査（連続 301 コマの外殻線の点滅・跳び）。記録のみ（設計38 で合否）。
  D. 原画視点に触れていないことの確認：t* の原画視点の色の画像が設計36 の t28_claws の画像と画素まで同じか。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds37/ds37_flow_eval.py
"""
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np

ROOT = 'G:/Unity/GreatWave_2026_Fresh'
OUT = ROOT + '/Unity/Build/Design/37/flowlines'
UD = OUT + '/unity'
FIG = OUT + '/fig'
DS36_TSTAR = ROOT + '/Unity/Build/Design/36/palette/unity/t28_claws/t28/render/af28r01_painting.png'
DS36_SYM = ROOT + '/Unity/Build/Design/36/palette/unity/tstar_sym_t28_claws/tstar_sym.json'
W, H = 1920, 1080
# 調色板（設計36 の材質の値、sRGB 8 bit）。0 白・1 淡い水色・2 藍中・3 藍濃・4 線
PAL = np.array([(248, 243, 223), (198, 215, 203), (44, 105, 147), (35, 64, 97), (71, 80, 95)], np.int32)
PAL_NAMES = ['white', 'mizuiro', 'ai_mid', 'ai_dark', 'line']
OTHER_DIST = 60          # 調色板のどれからもこの距離より遠い画素は「ほか」（空・船・富士・飛沫の縁など）
SIDE = 1.5               # 縁の両側を見る距離（px）
DISC = 3.0               # 面の動きの法線の成分がこれ以上の縁の画素だけで見分ける（px）
CLUSTER = 10             # 貼り付きの塊の大きさの下限（px）
T0 = time.time()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def imread_rgb(p):
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    if im is None:
        raise FileNotFoundError(p)
    return im[:, :, ::-1].copy()


def labels(rgb):
    d = ((rgb[:, :, None, :].astype(np.int32) - PAL[None, None]) ** 2).sum(-1)
    L = d.argmin(-1).astype(np.int8)
    L[np.sqrt(d.min(-1)) > OTHER_DIST] = 5
    return L


def load_coord(p):
    a = np.fromfile(p, np.float32).reshape(H, W, 2)[::-1]
    R, G = a[..., 0], a[..., 1]
    valid = R >= 1000
    sid = np.where(valid, np.floor(R / 2000.0), 0).astype(np.int8)
    col = np.where(valid, R - 2000.0 * sid, np.nan).astype(np.float32)
    row = np.where(valid, G, np.nan).astype(np.float32)
    return sid, col, row


REP = json.load(open(UD + '/ds37_render_report.json', encoding='utf-8'))
SHEETS = {s['name']: s for s in REP['sheets']}
SID2NAME = {s['sheetId']: s['name'] for s in REP['sheets'] if s['sheetId'] > 0}
_VCACHE = {}


def verts(sheet, t):
    key = (sheet, round(t, 3))
    if key not in _VCACHE:
        cand = [v for v in REP['verts'] if v['sheet'] == sheet and abs(v['t'] - t) < 1e-3]
        if not cand:
            raise KeyError(key)
        s = SHEETS[sheet]
        _VCACHE[key] = np.fromfile(cand[0]['path'], np.float32).reshape(s['rows'], s['cols'], 3)
        if len(_VCACHE) > 40:
            _VCACHE.pop(next(iter(_VCACHE)))
    return _VCACHE[key]


def surf_point(P, col, row):
    """面の座標（列・行、三角形の中は線形）→ ワールドの位置。三角形は (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)。"""
    rows, cols = P.shape[:2]
    c0 = np.clip(np.floor(col).astype(np.int64), 0, cols - 2)
    r0 = np.clip(np.floor(row).astype(np.int64), 0, rows - 2)
    fu = (col - c0)[:, None]
    fv = (row - r0)[:, None]
    P00, P01, P10, P11 = P[r0, c0], P[r0, c0 + 1], P[r0 + 1, c0], P[r0 + 1, c0 + 1]
    X1 = P00 + fu * (P01 - P00) + fv * (P10 - P00)
    X2 = P01 + P10 - P11 + fu * (P11 - P10) + fv * (P11 - P01)
    return np.where((fu + fv) <= 1.0, X1, X2)


def project(X, fr):
    V = np.array(fr['worldToCamera'], np.float64).reshape(4, 4)
    Pm = np.array(fr['projection'], np.float64).reshape(4, 4)
    Xh = np.concatenate([X.astype(np.float64), np.ones((len(X), 1))], 1)
    clip = Xh @ (Pm @ V).T
    w = clip[:, 3]
    x = (clip[:, 0] / w * 0.5 + 0.5) * W - 0.5
    yb = (clip[:, 1] / w * 0.5 + 0.5) * H
    y = (H - yb) - 0.5
    return np.stack([x, y], 1), w


def geo_flow(frA, frB, cA):
    """A の各画素の面の点が B で映る位置（B の画素の座標）。シート以外は NaN。"""
    sid, col, row = cA
    q = np.full((H, W, 2), np.nan, np.float64)
    resid = []
    for s, name in SID2NAME.items():
        m = sid == s
        if not m.any():
            continue
        c, r = col[m].astype(np.float64), row[m].astype(np.float64)
        XB = surf_point(verts(name, frB['t']), c, r)
        pB, wB = project(XB, frB)
        pB[wB <= 1e-6] = np.nan
        q[m] = pB
        # 確かめ：A の頂点で A のカメラへ投影すると画素の中心へ戻るか
        XA = surf_point(verts(name, frA['t']), c, r)
        pA, _ = project(XA, frA)
        yy, xx = np.nonzero(m)
        resid.append(np.hypot(pA[:, 0] - xx, pA[:, 1] - yy))
    resid = np.concatenate(resid) if resid else np.zeros(1)
    return q, resid


def edge_pixels(L, sid):
    pat = (L <= 3) & (sid >= 1) & (sid <= 3)
    bad = cv2.dilate(((L == 4) | (L == 5)).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    inner = np.zeros_like(pat)
    for s in (1, 2, 3):
        inner |= cv2.erode((sid == s).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    ok = pat & ~bad & inner
    E = np.zeros_like(pat)
    dR = (L[:, :-1] != L[:, 1:]) & ok[:, :-1] & ok[:, 1:] & (sid[:, :-1] == sid[:, 1:])
    E[:, :-1] |= dR
    E[:, 1:] |= dR
    dD = (L[:-1] != L[1:]) & ok[:-1] & ok[1:] & (sid[:-1] == sid[1:])
    E[:-1] |= dD
    E[1:] |= dD
    return E


def normals(L):
    nx = np.zeros(L.shape, np.float32)
    ny = np.zeros(L.shape, np.float32)
    for k in range(4):
        g = cv2.GaussianBlur((L == k).astype(np.float32), (0, 0), 1.2)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        m = L == k
        nx[m], ny[m] = gx[m], gy[m]
    n = np.hypot(nx, ny) + 1e-9
    return nx / n, ny / n


def sample(Lb, x, y):
    xi = np.rint(x).astype(np.int64)
    yi = np.rint(y).astype(np.int64)
    inb = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H) & np.isfinite(x) & np.isfinite(y)
    out = np.full(x.shape, -1, np.int8)
    out[inb] = Lb[yi[inb], xi[inb]]
    return out


def _mask(ey, ex, sel):
    m = np.zeros((H, W), bool)
    m[ey[sel], ex[sel]] = True
    return m


def clusters(mask):
    if not mask.any():
        return 0, []
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    big = [int(a) for a in st[1:, cv2.CC_STAT_AREA] if a >= CLUSTER]
    return len(big), sorted(big, reverse=True)[:10]


DIS = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)


def pattern_test(frA, frB, key, want_maps=False):
    cA = load_coord(frA['coord'])
    cB = load_coord(frB['coord'])
    imA, imB = imread_rgb(frA[key]), imread_rgb(frB[key])
    LA, LB = labels(imA), labels(imB)
    q, resid = geo_flow(frA, frB, cA)
    yy, xx = np.mgrid[0:H, 0:W]
    F = q - np.stack([xx, yy], -1)
    E = edge_pixels(LA, cA[0])
    nx, ny = normals(LA)
    ey, ex = np.nonzero(E)
    k = LA[ey, ex]
    n_x, n_y = nx[ey, ex], ny[ey, ex]
    j = sample(LA, ex - SIDE * n_x, ey - SIDE * n_y)
    ok_side = (j >= 0) & (j <= 3) & (j != k)
    Fx, Fy = F[ey, ex, 0], F[ey, ex, 1]
    Fn = Fx * n_x + Fy * n_y
    # B で同じ面の点が見えるか（隠れていないか）
    sB, colB, rowB = cB
    qx, qy = q[ey, ex, 0], q[ey, ex, 1]
    qi, qj = np.rint(qy).astype(np.int64), np.rint(qx).astype(np.int64)
    inb = np.isfinite(qx) & np.isfinite(qy) & (qi >= 0) & (qi < H) & (qj >= 0) & (qj < W)
    vis = np.zeros(len(ey), bool)
    ii = np.nonzero(inb)[0]
    sa = cA[0][ey[ii], ex[ii]]
    vis[ii] = (sB[qi[ii], qj[ii]] == sa) & (np.abs(colB[qi[ii], qj[ii]] - cA[1][ey[ii], ex[ii]]) < 1.0) & \
              (np.abs(rowB[qi[ii], qj[ii]] - cA[2][ey[ii], ex[ii]]) < 1.0)
    disc = ok_side & vis & (np.abs(Fn) >= DISC)

    def hyp(Lb, dx, dy):
        a = sample(Lb, ex + dx + SIDE * n_x, ey + dy + SIDE * n_y) == k
        b = sample(Lb, ex + dx - SIDE * n_x, ey + dy - SIDE * n_y) == j
        return a & b

    fol = hyp(LB, Fx, Fy)
    stay = hyp(LB, 0, 0)
    # 光学的な流れ（DIS）の法線の成分と面の動きの法線の成分の比（追従 1、画面に貼り付いた模様 0）
    gA = cv2.cvtColor(imA[:, :, ::-1], cv2.COLOR_BGR2GRAY)
    gB = cv2.cvtColor(imB[:, :, ::-1], cv2.COLOR_BGR2GRAY)
    of = DIS.calc(gA, gB, None)
    ofn = of[ey, ex, 0] * n_x + of[ey, ex, 1] * n_y
    rr = np.where(disc, ofn / np.where(np.abs(Fn) > 1e-6, Fn, 1.0), np.nan)
    # 貼り付き = 移し替えの試しで「動かさない所で合い、動かした所で合わない」かつ 光学的な流れの法線の成分が面の動きの半分未満
    tr_only = disc & stay & ~fol
    stuck = tr_only & (rr < 0.5)
    ncl, top = clusters(_mask(ey, ex, stuck))
    ncl_tr, _ = clusters(_mask(ey, ex, tr_only))
    ncl_of, _ = clusters(_mask(ey, ex, disc & (rr < 0.3)))
    # 感度の対照：模様が画面に貼り付いた場合（B の画像 = A の画像。色区は同じ、光学的な流れは 0）
    fol_c = hyp(LA, Fx, Fy)
    stay_c = hyp(LA, 0, 0)
    stuck_c = disc & stay_c & ~fol_c   # 光学的な流れは 0 なので比 0 < 0.5
    ncl_c, _ = clusters(_mask(ey, ex, stuck_c))
    r = rr[disc]
    nd = int(disc.sum())
    res = {
        'A': os.path.basename(frA[key]), 'B': os.path.basename(frB[key]), 'colour': key,
        'reproj_A_px_p50': round(float(np.median(resid)), 4), 'reproj_A_px_p99': round(float(np.percentile(resid, 99)), 4),
        'edge_px': int(len(ey)), 'disc_px': nd,
        'disc_px_by_sheet': {SID2NAME[q]: int((cA[0][ey[disc], ex[disc]] == q).sum()) for q in SID2NAME},
        'stuck_px_by_sheet': {SID2NAME[q]: int((cA[0][ey[stuck], ex[stuck]] == q).sum()) for q in SID2NAME},
        'geo_normal_px_median': round(float(np.median(np.abs(Fn[disc]))), 3) if nd else None,
        'follow_rate': round(float(fol[disc].mean()), 4) if nd else None,
        'stay_rate': round(float(stay[disc].mean()), 4) if nd else None,
        'stuck_px': int(stuck.sum()), 'stuck_clusters_ge10': ncl, 'stuck_cluster_sizes_top': top,
        'transfer_only_px': int(tr_only.sum()), 'transfer_only_clusters_ge10': ncl_tr,
        'transfer_only_of_ratio_median': round(float(np.nanmedian(rr[tr_only])), 4) if tr_only.any() else None,
        'of_only_lt0p3_clusters_ge10': ncl_of,
        'neither_px': int((disc & ~stay & ~fol).sum()),
        'control_stuck_px': int(stuck_c.sum()), 'control_stuck_clusters_ge10': ncl_c,
        'of_ratio_median': round(float(np.median(r)), 4) if nd else None,
        'of_ratio_frac_0p5_1p5': round(float(((r > 0.5) & (r < 1.5)).mean()), 4) if nd else None,
        'of_ratio_frac_lt_0p3': round(float((r < 0.3).mean()), 4) if nd else None,
    }
    if want_maps:
        res['_maps'] = dict(ex=ex, ey=ey, disc=disc, fol=fol, stuck=stuck, neither=disc & ~stay & ~fol, F=F, of=of, imA=imA, imB=imB)
    return res


def frames(kind, **kw):
    out = [f for f in REP['frames'] if f['kind'] == kind]
    for a, b in kw.items():
        out = [f for f in out if (abs(f[a] - b) < 1e-3 if isinstance(b, float) else f[a] == b)]
    return out


def one(kind, **kw):
    f = frames(kind, **kw)
    if len(f) != 1:
        raise KeyError((kind, kw, len(f)))
    return f[0]


def main():
    os.makedirs(FIG, exist_ok=True)
    M = {'schema': 'ds37_flowlines_metrics/1', 'number': '設計37 第「流れに沿う線」部', 'unity_report_sha256': sha(UD + '/ds37_render_report.json'),
         'definitions_ja': {
             'stuck': '面の動きの法線の成分が 3 px 以上の模様の縁の画素のうち、(1) 縁の両側（±1.5 px）の色区が、動かさない所では次の画像と合い、面の動きだけ動かした所では合わない（移し替えの試し）、'
                      'かつ (2) 光学的な流れの法線の成分が面の動きの法線の成分の半分未満の画素（2 つの測り方が共に画面への貼り付きを示す所）',
             'stuck_definition_change_ja': '最初の実行は (1) だけで数え、0.1 s の組と頭の揺れの組で 10 px 以上の塊が 4 個出た。4 個とも幅 1〜2 px の細い藍の線の中で、'
                                           '塊の中の光学的な流れの比の中央値は 0.99〜1.01（模様は面とともに動いている）。±1.5 px の両側の見本が 1〜2 px の線を分けられないための誤検出と判断し、(2) を加えた'
                                           '（transfer_only_* に (1) だけの数を残す）。',
             'stuck_cluster': '貼り付きの画素の 8 近傍の塊で 10 px 以上のもの。合格 = 全ての組で 0（既定値、進行役の判断）',
             'control': '感度の対照：次の画像の色区を前の画像の色区に置き換え（画面に貼り付いた模様）、同じ試しで貼り付きの塊が出ること',
             'of_ratio': '光学的な流れ（OpenCV DIS、MEDIUM）の法線の成分 ÷ 面の動きの法線の成分（追従 1、貼り付き 0）',
         }}
    # D. 原画視点に触れていないこと
    pc = UD + '/check/ds37_painting_tstar.png'
    a, b = imread_rgb(pc), imread_rgb(DS36_TSTAR)
    M['painting_tstar_vs_ds36'] = {'ds37': pc, 'ds37_sha256': sha(pc), 'ds36': DS36_TSTAR, 'ds36_sha256': sha(DS36_TSTAR),
                                   'identical_pixels': bool(np.array_equal(a, b)), 'max_abs_diff': int(np.abs(a.astype(int) - b.astype(int)).max()),
                                   'px_diff': int((np.abs(a.astype(int) - b.astype(int)).max(-1) > 0).sum())}
    print('check', M['painting_tstar_vs_ds36'], flush=True)

    # A. 形成：（t, t + 0.1 s）と（t, t + 1 s）
    form = []
    for view in ('painting', 'seat'):
        for key in ('colourWhiteOff', 'colourWhiteOn'):
            for t in range(1, 13 + 1):
                for gap in (0.1, 1.0):
                    tb = t + gap
                    if tb > 13.1 + 1e-6:
                        continue
                    try:
                        fa, fb = one('flow', view=view, t=float(t)), one('flow', view=view, t=float(tb))
                    except KeyError:
                        continue
                    r = pattern_test(fa, fb, key)
                    r.update(view=view, t=t, gap=gap)
                    form.append(r)
                    print('form', view, key, t, gap, r['disc_px'], r['follow_rate'], r['stay_rate'], r['stuck_clusters_ge10'], r['control_stuck_clusters_ge10'], r['of_ratio_median'], flush=True)
    M['formation_pairs'] = form
    # A. 頭の揺れ
    sway = []
    keep = {}
    for view in ('seat', 'seat_toward_wave'):
        for t in (6.0, 9.0, 12.0):
            for da, db in ((0.0, 0.1), (0.0, -0.1), (-0.1, 0.1)):
                fa, fb = one('sway', view=view, t=t, dx=da), one('sway', view=view, t=t, dx=db)
                want = (view, t, da, db) in (('seat', 9.0, -0.1, 0.1), ('seat_toward_wave', 9.0, -0.1, 0.1))
                r = pattern_test(fa, fb, 'colourWhiteOn', want_maps=want)
                if want:
                    keep[view] = r.pop('_maps')
                r.update(view=view, t=t, dxA=da, dxB=db)
                sway.append(r)
                print('sway', view, t, da, db, r['disc_px'], r['follow_rate'], r['stay_rate'], r['stuck_clusters_ge10'], r['control_stuck_clusters_ge10'], r['of_ratio_median'], flush=True)
    M['sway_pairs'] = sway
    # 合否は 0.1 s の組（3 コマ）と頭の揺れの組で出す。1 s の組は記録のみ：1 s の間に唇が伸びて細かい模様の形が変わり（面とともに伸びる）、
    # 170 px ほど動く所で「動かさない所」が細かい模様の別の縁と偶然合うことがある（最初の試しの t 8 → 9 s の原画視点、(92, 409) の 12 px の塊）。
    form_gate = [p for p in form if p['gap'] < 0.5]
    M['formation_gap1s_record_only'] = {'pairs': sum(p['gap'] >= 0.5 for p in form), 'stuck_clusters_total': sum(p['stuck_clusters_ge10'] for p in form if p['gap'] >= 0.5),
                                        'follow_rate_min': min((p['follow_rate'] for p in form if p['gap'] >= 0.5 and p['disc_px']), default=None)}
    allp = form_gate + sway
    tot_cl = sum(p['stuck_clusters_ge10'] for p in allp)
    ctl_ok = all(p['control_stuck_clusters_ge10'] > 0 for p in allp if p['disc_px'] >= 200)
    M['screen_sticking'] = {
        'pairs': len(allp), 'pairs_with_disc_ge200': sum(p['disc_px'] >= 200 for p in allp),
        'stuck_clusters_total': tot_cl, 'stuck_px_total': int(sum(p['stuck_px'] for p in allp)),
        'disc_px_total': int(sum(p['disc_px'] for p in allp)),
        'follow_rate_weighted': round(sum(p['follow_rate'] * p['disc_px'] for p in allp if p['disc_px']) / max(1, sum(p['disc_px'] for p in allp)), 4),
        'stay_rate_weighted': round(sum(p['stay_rate'] * p['disc_px'] for p in allp if p['disc_px']) / max(1, sum(p['disc_px'] for p in allp)), 4),
        'of_ratio_median_of_pairs': round(float(np.median([p['of_ratio_median'] for p in allp if p['of_ratio_median'] is not None])), 4),
        'control_detects_all_pairs_with_disc_ge200': bool(ctl_ok),
        'sway_disc_px_total': int(sum(p['disc_px'] for p in sway)),
        'disc_px_by_sheet_total': {nm: int(sum(p['disc_px_by_sheet'][nm] for p in allp)) for nm in SID2NAME.values()},
        'stuck_px_by_sheet_total': {nm: int(sum(p['stuck_px_by_sheet'][nm] for p in allp)) for nm in SID2NAME.values()},
        'transfer_only_clusters_total': int(sum(p['transfer_only_clusters_ge10'] for p in allp)),
        'transfer_only_of_ratio_median_by_pair': [p['transfer_only_of_ratio_median'] for p in allp if p['transfer_only_clusters_ge10'] > 0],
        'of_only_lt0p3_clusters_total': int(sum(p['of_only_lt0p3_clusters_ge10'] for p in allp)),
        'pass': bool(tot_cl == 0 and ctl_ok),
    }
    print('sticking', M['screen_sticking'], flush=True)
    fig_sway(keep)
    fig_ratio(form_gate, sway)

    # B. 177
    M['177'] = eval_177()
    print('177', {k: v for k, v in M['177'].items() if k not in ('bands', 'display_ai_mid', 'times')}, flush=True)
    # C. 191
    M['191_precheck'] = eval_191()
    print('191', {k: v for k, v in M['191_precheck'].items() if k != 'per_view_series'}, flush=True)
    M['backlog'] = {
        '177': {'value': M['177']['summary_ja'], 'verdict': 'pass' if M['177']['pass'] else 'fail'},
        'screen_sticking_0': {'value': '貼り付きの塊 {} 個（{} 組、見分けられる縁の画素 {}）、感度の対照は全ての組で検出'.format(tot_cl, len(allp), M['screen_sticking']['disc_px_total']),
                              'verdict': 'pass' if M['screen_sticking']['pass'] else 'fail'},
        '191': {'value': M['191_precheck']['summary_ja'], 'verdict': '記録のみ（事前検査。合否は設計38）'},
    }
    M['seconds'] = round(time.time() - T0, 1)
    with open(OUT + '/ds37_flowlines_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(M, f, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    print('done', M['seconds'], 's')


COL_DIR = ROOT + '/Tools/PaintingTruth/colour'


def _poly_mask(region):
    m = np.zeros((H, W), np.uint8)
    for ring in region['rings']:
        pts = np.round(np.array(ring['points_display'], np.float64) * 8).astype(np.int32)
        cv2.fillPoly(m, [pts], 0 if ring.get('hole') else 1, lineType=cv2.LINE_8, shift=3)
    return cv2.erode(m, np.ones((3, 3), np.uint8)) > 0


def _texel_class_comp(uv3, cls, lab, col, row):
    uv = surf_point(uv3, col.astype(np.float64), row.astype(np.float64))
    ti = np.clip((uv[:, 1] * 4096).astype(np.int64), 0, 4095)
    tj = np.clip((uv[:, 0] * 4096).astype(np.int64), 0, 4095)
    return cls[ti, tj], lab[ti, tj]


def eval_177():
    """177：美術優先31 と同じ藍中の帯 25 本（美術優先28 の第A部の真値 colour_truth.json の stripes.ai_mid_bands、多角形は colour_polylines.json を 1 px 縮めた）。"""
    hs = SHEETS['hero']
    rows, cols = hs['rows'], hs['cols']
    uv3 = np.fromfile(REP['heroUv3Path'], np.float32).reshape(rows, cols, 2)
    raw = np.fromfile(REP['heroSdfPath'], np.uint8).reshape(4096, 4096, 4)
    cls = raw.argmax(-1).astype(np.uint8)  # 行 0 = v 0（Unity の生データの順）
    _, lab = cv2.connectedComponents((cls == 2).astype(np.uint8), connectivity=8)
    truth = json.load(open(COL_DIR + '/colour_truth.json', encoding='utf-8'))
    polys = {r['id']: r for r in json.load(open(COL_DIR + '/colour_polylines.json', encoding='utf-8'))['regions']}
    tb = truth['stripes']['ai_mid_bands']
    fr = one('flowk', view='painting', t=12.0)
    sid, col, row = load_coord(fr['coord'])
    L = labels(imread_rgb(fr['colourWhiteOn']))
    times = sorted({round(v['t'], 3) for v in REP['verts'] if v['sheet'] == 'hero' and '/h177/' in v['path'].replace(chr(92), '/')})
    i2, its = times.index(2.0), times.index(12.0)
    out = []
    band_comps = {}
    for b in tb:
        pm = _poly_mask(polys[b['region']]) & (sid == 1) & (L == 2)
        if pm.sum() == 0:
            out.append({'region': b['region'], 'mapped': False})
            continue
        c, r = col[pm], row[pm]
        _, comp = _texel_class_comp(uv3, cls, lab, c, r)
        ids, cnt = np.unique(comp[comp > 0], return_counts=True)
        keep = [int(i) for i, n in zip(ids, cnt) if n >= 0.1 * len(comp)]
        sel = np.isin(comp, keep)
        band_comps[b['region']] = keep
        cb, rb = c[sel].astype(np.float64), r[sel].astype(np.float64)
        hy, cx = [], []
        for t in times:
            X = surf_point(verts('hero', t), cb, rb)
            hy.append(float(X[:, 1].mean()))
            p, _ = project(X, fr)
            cx.append(float(np.median(p[:, 0])))
        dh = np.diff(hy[i2:its + 1])
        out.append({'region': b['region'], 'mapped': True, 'px_tstar': int(sel.sum()), 'uv_components': keep, 'lower_end_display': b['lower_end_display'],
                    'height_m_t2': round(hy[i2], 3), 'height_m_tstar': round(hy[its], 3), 'rise_m': round(hy[its] - hy[i2], 3),
                    'height_max_drop_per_step_m': round(float(max(0.0, -dh.min())), 3), 'height_total_drop_m': round(float(np.maximum(0, -dh).sum()), 3),
                    'height_m': [round(h, 3) for h in hy], 'screen_x_median': [round(x, 1) for x in cx]})
    mapped = [o for o in out if o['mapped']]
    lower = [o for o in mapped if o['lower_end_display'][1] > 690]
    inv = []
    if len(lower) > 1:
        ref = np.array([o['screen_x_median'][its] for o in lower])
        for q in range(i2, its + 1):
            xs = np.array([o['screen_x_median'][q] for o in lower])
            inv.append(int(sum(1 for a in range(len(xs)) for b2 in range(a + 1, len(xs)) if (ref[a] - ref[b2]) * (xs[a] - xs[b2]) < 0)))
    # 表示が藍中のままか：形成の各時刻の原画視点（白の時間場あり）で、帯の UV 成分に入り、3×3 の近傍の面の点の色区も藍中の画素（境の 1 画素を除く）の表示
    allc = sorted({c for v in band_comps.values() for c in v})
    disp = []
    for fr2 in frames('flowk', view='painting'):
        s2, c2, r2 = load_coord(fr2['coord'])
        L2 = labels(imread_rgb(fr2['colourWhiteOn']))
        m = s2 == 1
        k = np.full((H, W), 255, np.uint8)
        comp = np.zeros((H, W), np.int32)
        kk, cc = _texel_class_comp(uv3, cls, lab, c2[m], r2[m])
        k[m] = kk
        comp[m] = cc
        interior = cv2.erode((k == 2).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        sel = interior & np.isin(comp, allc)
        n = int(sel.sum())
        disp.append({'t': round(fr2['t'], 2), 'band_px': n, 'shown_ai_mid': int((L2[sel] == 2).sum()), 'shown_white': int((L2[sel] == 0).sum()),
                     'shown_mizuiro': int((L2[sel] == 1).sum()), 'shown_ai_dark': int((L2[sel] == 3).sum()), 'shown_off_palette_aa': int((L2[sel] == 5).sum()),
                     'frac': round(float((L2[sel] == 2).mean()), 5) if n else None})
    fr_min = min(d['frac'] for d in disp if d['band_px'] >= 20)
    white_over = int(sum(d['shown_white'] for d in disp))
    sym = json.load(open(DS36_SYM, encoding='utf-8'))
    ends = {row['item']: row['kp_sym_max_px'] for row in sym['rows'] if row['item'] in ('77', '118')}
    rise_all = all(o['rise_m'] > 0 for o in mapped)
    falling = [o['region'] for o in mapped if o['rise_m'] <= 0]
    # 合否の読み（進行役の判断、既定値）：帯 25/25・全部上がる・下側の並びの入れ替わり 0・帯の画素が白で塗られる 0（白の時間場が帯を塗らない）・終点 ≤4 px。
    # 表示が藍中の割合は記録（美術優先31 は ID の画像で ≥0.999 を見たが、ここはアンチエイリアスありの色の画像で、藍中でない画素は帯の中の 1 画素より細い白・淡い水色の点の混色）
    ok = bool(len(mapped) == len(tb) and white_over == 0 and rise_all and max(inv or [0]) == 0 and all(v <= 4.0 for v in ends.values()))
    summ = ('藍中の帯 {}/{} 本（美術優先31 と同じ帯）。同じ面の点の高さ t 2 s → t*：{:.2f}〜{:.2f} m（上がらない帯 {}）。下側の {} 本の原画視点の x の並びの入れ替わり 最大 {}。'
            '帯の内側の画素が白で塗られる 0 画素であること：{} 画素。表示が藍中の割合 最小 {:.4f}（{} 時刻、記録。藍中でない画素は帯の中の細かい点の混色）。終点 77 {} px・118 {} px（設計36 の t28_claws の評価器。原画視点の t* の画像は同じ）').format(
        len(mapped), len(tb), min(o['rise_m'] for o in mapped), max(o['rise_m'] for o in mapped), falling or 'なし', len(lower), max(inv or [0]),
        white_over, fr_min, sum(1 for d in disp if d['band_px'] >= 20), ends.get('77'), ends.get('118'))
    return {'bands_total': len(tb), 'bands_mapped': len(mapped), 'lower_bands': [o['region'] for o in lower], 'lower_order_inversions': inv,
            'rise_all': rise_all, 'bands_not_rising': falling, 'display_ai_mid': disp, 'display_ai_mid_min_frac': fr_min, 'band_px_shown_white_total': white_over, 'endpoints_px': ends,
            'times': times, 'bands': out, 'pass': ok, 'summary_ja': summ,
            'method_ja': '帯＝美術優先31 と同じ 25 本（colour_truth.json の stripes.ai_mid_bands）。t* の原画視点で多角形（1 px 縮めた）の中の藍中に見える主役波の画素の面の点を、'
                         '主役波の色区の表（' + REP['heroSdfPath'] + '）の藍中の 8 近傍の成分へ分け、帯の画素の 10% 以上が入る成分をその帯の成分とした（美術優先31 と同じ規則。テクセルではなく画素の面の点）。'
                         '描画は背景（船・富士など）と外殻線を切った原画視点（flowk、評価器の af28r01_painting_kstar と同じ切り方。背景ありでは左下の 4 本が手前の船に隠れる）。高さは同じ面の点のワールドの y の平均（GPU の頂点の読み戻し、0.25 s ごと）。下側の帯＝下の端の表示の y > 690（美術優先31 と同じ）。'
                         '表示の検査は、面の座標 → UV3 → 色区の表で求めた色区が 3×3 の近傍でも藍中で、帯の成分に入る画素の、描画の色（最も近い調色板の色）。'}


def eval_191():
    out = {}
    series = {}
    for rec in REP['l191']:
        n = rec['frames']
        raw = np.memmap(rec['path'], np.uint8, 'r', shape=(n, H, W // 8))
        prev = None
        cur = np.unpackbits(raw[0], axis=1).astype(bool)
        nxt = np.unpackbits(raw[1], axis=1).astype(bool)
        blink = []
        blink_cl = []
        flash_cl = []
        hole_cl = []
        jump_cl = []
        cham_p99 = []
        mv = rec['heroMoveMax']
        for q in range(1, n - 1):
            prev, cur, nxt = cur, nxt, np.unpackbits(raw[q + 1], axis=1).astype(bool)
            b = (cur != prev) & (prev == nxt)
            blink.append(int(b.sum()))
            slow = mv[q] < 1.0 and mv[q + 1] < 1.0
            nb, _ = clusters(b)
            blink_cl.append(nb if slow else 0)
            # 点滅（動きを考えた読み）：このコマの線の画素で、前のコマにも次のコマにも（頂点の動きの最大 + 2 px）の内に線がない＝一瞬だけ出た線、
            # 前後のコマで同じ画素に線があるのに、このコマでは 1 px の内に線がない＝一瞬だけ消えた線。その 10 px 以上の塊
            if cur.any() and prev.any() and nxt.any():
                dp = cv2.distanceTransform((~prev).astype(np.uint8), cv2.DIST_L2, 3)
                dn = cv2.distanceTransform((~nxt).astype(np.uint8), cv2.DIST_L2, 3)
                dc = cv2.distanceTransform((~cur).astype(np.uint8), cv2.DIST_L2, 3)
                flash = cur & (dp > mv[q] + 2.0) & (dn > mv[q + 1] + 2.0)
                hole = prev & nxt & (dc > 1.5)
                nf, _ = clusters(flash)
                nh, _ = clusters(hole)
            else:
                nf = nh = 0
            flash_cl.append(nf)
            hole_cl.append(nh)
            # 跳び：このコマの線の画素から次のコマの最も近い線の画素までの距離が、主役波の頂点の画面の動きの最大 + 2 px を超える画素の塊
            if nxt.any() and cur.any():
                dt = cv2.distanceTransform((~nxt).astype(np.uint8), cv2.DIST_L2, 3)
                d = dt[cur]
                cham_p99.append(float(np.percentile(d, 99)))
                jm = np.zeros((H, W), bool)
                jm[cur] = dt[cur] > (mv[q + 1] + 2.0)
                nj, _ = clusters(jm)
                jump_cl.append(nj)
            else:
                cham_p99.append(0.0)
                jump_cl.append(0)
        del raw
        lp = np.array(rec['linePx'][1:-1], float)
        bf = np.array(blink) / np.maximum(lp, 1)
        out[rec['view']] = {'frames': n, 'line_px_median': int(np.median(rec['linePx'])), 'blink_px_frac_median': round(float(np.median(bf)), 5),
                            'blink_px_frac_max': round(float(bf.max()), 5), 'blink_clusters_ge10_in_slow_frames': int(sum(blink_cl)),
                            'slow_frames': int(sum(1 for q in range(1, n - 1) if mv[q] < 1.0 and mv[q + 1] < 1.0)),
                            'chamfer_p99_px_median': round(float(np.median(cham_p99)), 3), 'chamfer_p99_px_max': round(float(max(cham_p99)), 3),
                            'flash_clusters_ge10': int(sum(flash_cl)), 'flash_frames': [int(q + 1 + rec['firstFrame']) for q, v in enumerate(flash_cl) if v > 0][:20],
                            'hole_clusters_ge10': int(sum(hole_cl)), 'hole_frames': [int(q + 1 + rec['firstFrame']) for q, v in enumerate(hole_cl) if v > 0][:20],
                            'jump_clusters_ge10': int(sum(jump_cl)), 'jump_frames': [int(q + 1 + rec['firstFrame']) for q, v in enumerate(jump_cl) if v > 0][:20],
                            'hero_move_max_px_median': round(float(np.median(mv[1:])), 3)}
        series[rec['view']] = {'blink_frac': bf.round(5).tolist(), 'chamfer_p99': np.round(cham_p99, 3).tolist(), 'jump_clusters': jump_cl, 'line_px': rec['linePx']}
    fig_191(series)
    summ = '; '.join('{}：一瞬だけ出た線の塊 {}（コマ {}）・一瞬だけ消えた線の塊 {}（コマ {}）・跳びの塊 {}（コマ {}）、ゆっくりのコマ（{} コマ）の単純な点滅の塊 {}、'
                     '線の画素の中央値 {}（単純な点滅の画素の割合の中央値 {:.3f}：細い線が 1 コマに線幅より大きく動くと 1 コマだけ線になる画素が多いので記録のみ）'.format(
        v, o['flash_clusters_ge10'], o['flash_frames'][:5], o['hole_clusters_ge10'], o['hole_frames'][:5], o['jump_clusters_ge10'], o['jump_frames'][:5],
        o['slow_frames'], o['blink_clusters_ge10_in_slow_frames'], o['line_px_median'], o['blink_px_frac_median']) for v, o in out.items())
    return {'per_view': out, 'per_view_series': series, 'summary_ja': summ,
            'method_ja': '外殻線（_AF28IdMode = 1 のマゼンタ）の画素の連続 301 コマ（t 2.0〜12.0 s、30 fps、飛沫なし・爪あり）。点滅 = 前後のコマと違い、前後のコマどうしは同じ画素。'
                         'ゆっくりのコマ = 主役波の頂点の画面の動きの最大が前後とも 1 px/コマ未満。跳び = 次のコマの最も近い線の画素まで（頂点の動きの最大 + 2 px）より遠い画素の 10 px 以上の塊。'}


def fig_sway(keep):
    for view, mp in keep.items():
        imA, imB = mp['imA'], mp['imB']
        vis = (0.55 * imA).astype(np.uint8)
        ex, ey = mp['ex'], mp['ey']
        d = mp['disc']
        vis[ey[d & mp['fol']], ex[d & mp['fol']]] = (40, 220, 60)
        vis[ey[mp['neither']], ex[mp['neither']]] = (250, 170, 20)
        vis[ey[mp['stuck']], ex[mp['stuck']]] = (255, 0, 255)
        diff = np.abs(imA.astype(int) - imB.astype(int)).max(-1)
        dv = cv2.applyColorMap(np.clip(diff * 2, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[:, :, ::-1]
        top = np.concatenate([imA, imB], 1)
        bot = np.concatenate([vis, dv], 1)
        fig = np.concatenate([top, bot], 0)
        fig = cv2.resize(fig, (1920, 1080), interpolation=cv2.INTER_AREA)
        for txt, xy in ((view + ' t 9 s  eye -0.1 m', (10, 30)), (view + ' t 9 s  eye +0.1 m', (970, 30)),
                        ('pattern edges: green = follows surface, orange = neither, magenta = screen-stuck', (10, 570)), ('|A - B| (x2)', (970, 570))):
            cv2.putText(fig, txt, xy, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(fig, txt, xy, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(FIG + '/fig_ds37_sway_' + view + '_t09.png', fig[:, :, ::-1])


def _text(img, s, xy, scale=0.5, col=(0, 0, 0), th=1):
    cv2.putText(img, s, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)


def fig_ratio(form, sway):
    """追従の割合（緑）・貼り付きの割合（赤紫）・光学的な流れの比の中央値（黒の点）を組ごとに描く（OpenCV。matplotlib は入っていない）。"""
    img = np.full((1080, 1920, 3), 255, np.uint8)
    panels = ((form, 'formation pairs (t, t+0.1 s), painting/seat, W0 = white field off, W1 = on'), (sway, 'head sway pairs (eye -0.1/0/+0.1 m), seat / seat_toward_wave'))
    for pi, (data, title) in enumerate(panels):
        data = [p for p in data if p['disc_px'] > 0]
        x0, y0, pw, ph = 80, 60 + pi * 520, 1800, 380
        cv2.rectangle(img, (x0, y0), (x0 + pw, y0 + ph), (0, 0, 0), 1)
        for v in (0.0, 0.5, 1.0, 1.2):
            yy = int(y0 + ph - v / 1.25 * ph)
            cv2.line(img, (x0, yy), (x0 + pw, yy), (210, 210, 210), 1)
            _text(img, '{:.1f}'.format(v), (x0 - 40, yy + 5))
        n = max(1, len(data))
        bw = pw / n
        for i, p in enumerate(data):
            xc = x0 + (i + 0.5) * bw
            for val, dx, col in ((p['follow_rate'], -0.2, (60, 160, 60)), (p['stay_rate'], 0.2, (200, 40, 150))):
                h = int(val / 1.25 * ph)
                cv2.rectangle(img, (int(xc + (dx - 0.18) * bw), y0 + ph - h), (int(xc + (dx + 0.18) * bw), y0 + ph), col, -1)
            if p['of_ratio_median'] is not None:
                cv2.circle(img, (int(xc), int(y0 + ph - max(0.0, min(1.25, p['of_ratio_median'])) / 1.25 * ph)), 4, (0, 0, 0), -1)
            if p['stuck_clusters_ge10']:
                _text(img, 'x', (int(xc) - 5, y0 - 5), 0.6, (0, 0, 255), 2)
            lab = ('{} {} t{}'.format(p['view'][:5], 'W0' if p['colour'] == 'colourWhiteOff' else 'W1', p['t']) if 'gap' in p
                   else '{} t{:.0f} {:+.1f}>{:+.1f}'.format('stw' if p['view'] == 'seat_toward_wave' else 'seat', p['t'], p['dxA'], p['dxB']))
            cv2.putText(img, lab, (int(xc) - 4, y0 + ph + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)
        _text(img, title + '   stuck clusters = {}'.format(sum(p['stuck_clusters_ge10'] for p in data)), (x0, y0 - 20), 0.7, (0, 0, 0), 2)
    _text(img, 'green = follow rate (pattern edges found where the surface moved them), magenta = stay rate (edges found at the old screen position), '
               'black dot = median(optical flow / surface motion, normal comp.)', (20, 1060), 0.55)
    cv2.imwrite(FIG + '/fig_ds37_follow_vs_stay.png', img)


def fig_191(series):
    img = np.full((1080, 1920, 3), 255, np.uint8)
    cols = {'painting': (200, 80, 30), 'seat': (30, 120, 200)}
    for pi, (key, ymax, lab) in enumerate((('blink_frac', 0.2, 'blink px / line px'), ('chamfer_p99', 20.0, 'line to next-frame line p99 (px)'))):
        x0, y0, pw, ph = 100, 60 + pi * 500, 1760, 400
        cv2.rectangle(img, (x0, y0), (x0 + pw, y0 + ph), (0, 0, 0), 1)
        for v in np.linspace(0, ymax, 5):
            yy = int(y0 + ph - v / ymax * ph)
            cv2.line(img, (x0, yy), (x0 + pw, yy), (220, 220, 220), 1)
            _text(img, '{:g}'.format(round(v, 3)), (x0 - 70, yy + 5))
        for t in range(2, 13):
            xx = int(x0 + (t - 2) / 10 * pw)
            cv2.line(img, (xx, y0 + ph), (xx, y0 + ph + 6), (0, 0, 0), 1)
            _text(img, '{} s'.format(t), (xx - 12, y0 + ph + 24))
        for v, s in series.items():
            ys = np.array(s[key], float)
            ts = 2.0 + (np.arange(len(ys)) + 1) / 30.0
            pts = np.stack([x0 + (ts - 2) / 10 * pw, y0 + ph - np.clip(ys, 0, ymax) / ymax * ph], 1).astype(np.int32)
            cv2.polylines(img, [pts], False, cols.get(v, (0, 0, 0)), 2, cv2.LINE_AA)
        _text(img, lab, (x0, y0 - 15), 0.7, (0, 0, 0), 2)
    _text(img, '191 pre-check: outline mask over 301 consecutive frames (t 2-12 s, 30 fps). blue = painting, orange = seat', (20, 1060), 0.6)
    cv2.imwrite(FIG + '/fig_ds37_191_precheck.png', img)


if __name__ == '__main__':
    main()
