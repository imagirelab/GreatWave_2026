# -*- coding: utf-8 -*-
"""設計30：参照モデル（Q5・Q18・Q20）の配置の数値だけを測る（記録のみ。生成器はこのファイルも OBJ も読まない。F13-1）。

参照モデル G:/research/model/wave_repair_zbrush2.obj（SHA-256 AB4124F9…3D40。他者の展示作品のスキャン。作者・所蔵は未確認、D18）を
読み取りのみで開き、SHA-256 を照合してから、作業計画 9.4 の整列（解B、Docs/Evidence/ArtFirst/26/reference/align_B_upright.json）で
Unity の世界へ置いた一時キャッシュ（Git 対象外の Unity/Build/Design/30/_objcache/）を作る。そこから次の数値だけを取り出す：
  - 大波の頂（最も高い点）の位置と、モデル自身の海面、波高 H_ref
  - 手前の小波（前景の富士形の小波）の頂の位置・高さ・裾の幅・斜面の角度
  - 大波の下の谷（前の谷）の底の位置・深さ・前の壁の傾き
  - 右側（波峰線の +c 側）の最も高い所（9.2 では右側の波はないとした。確かめる）
位置は主役波の波の枠の軸（t：進む向き、e：波峰線の向き。K*′ の frame と同じ）で、参照モデル自身の頂からの差 (Δa, Δc) と
H_ref との比にする。メッシュ・頂点・断面の線は出力しない（数値だけの JSON）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds30/ds30_refmeasure.py cache      一時キャッシュを作る（SHA-256 を記録）
    py -3.10 Tools/GWWaveGen/ds30/ds30_refmeasure.py measure    数値を測り Unity/Build/Design/30/ref/ds30_ref_layout.json へ書く
    py -3.10 Tools/GWWaveGen/ds30/ds30_refmeasure.py delete     一時キャッシュを消し、消したファイルの SHA-256 を記録する
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = r"G:\research\model\wave_repair_zbrush2.obj"
SRC_SHA = "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40"
ALIGN = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26", "reference", "align_B_upright.json")
CACHE_DIR = os.path.join(REPO, "Unity", "Build", "Design", "30", "_objcache")
CACHE = os.path.join(CACHE_DIR, "ref_world_tmp.npz")
OUT_DIR = os.path.join(REPO, "Unity", "Build", "Design", "30", "ref")
LOG = os.path.join(OUT_DIR, "ds30_ref_cache_log.json")
# 主役波の波の枠（K*′ の meta の frame。Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json）
E_CREST = np.array([0.6798348938056157, 0.0, 0.733365200404483])
T_TRAVEL = np.array([0.7333652004044829, 0.0, -0.6798348938056156])


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load_log():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding="utf-8"))
    return {"source": os.path.basename(SRC), "source_sha256": SRC_SHA, "events": []}


def save_log(d):
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def cmd_cache():
    t0 = time.time()
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    if h != SRC_SHA:
        raise SystemExit("参照モデルの SHA-256 が違うので使わない: " + h)
    lines = raw.split(b"\n")
    V = np.array([l.split()[1:4] for l in lines if l.startswith(b"v ")], dtype=np.float64)
    tris, quads = [], []
    for l in lines:
        if not l.startswith(b"f "):
            continue
        p = [int(x.split(b"/")[0]) - 1 for x in l.split()[1:]]
        if len(p) == 3:
            tris.append(p)
        elif len(p) == 4:
            quads.append(p)
        else:
            for j in range(1, len(p) - 1):
                tris.append([p[0], p[j], p[j + 1]])
    del raw, lines
    Q = np.array(quads, np.int64).reshape(-1, 4)
    T = np.array(tris, np.int64).reshape(-1, 3)
    F = np.vstack([T, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
    M4 = np.array(json.load(open(ALIGN, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(CACHE, V=Vu.astype(np.float32), F=F)
    d = load_log()
    d["events"].append({"event": "cache_created", "file": os.path.relpath(CACHE, REPO).replace("\\", "/"),
                        "sha256": sha256_file(CACHE), "bytes": os.path.getsize(CACHE),
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t0, 1),
                        "align": os.path.relpath(ALIGN, REPO).replace("\\", "/"), "align_sha256": sha256_file(ALIGN)})
    save_log(d)
    print("cache", CACHE, len(V), len(F), "%.1fs" % (time.time() - t0))


def cmd_delete():
    """一時キャッシュのフォルダーの中身（キャッシュと、そこから作った確認用の図・一時のスクリプト）を全部消し、各ファイルの SHA-256 を記録する。"""
    d = load_log()
    if os.path.isdir(CACHE_DIR):
        for nm in sorted(os.listdir(CACHE_DIR)):
            fp = os.path.join(CACHE_DIR, nm)
            if os.path.isfile(fp):
                s = sha256_file(fp)
                os.remove(fp)
                d["events"].append({"event": "cache_deleted", "file": os.path.relpath(fp, REPO).replace("\\", "/"), "sha256": s,
                                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    left = os.listdir(CACHE_DIR) if os.path.isdir(CACHE_DIR) else []
    if os.path.isdir(CACHE_DIR) and not left:
        os.rmdir(CACHE_DIR)
    d["cache_dir_exists_after_delete"] = os.path.isdir(CACHE_DIR)
    save_log(d)
    print("deleted; left:", left)


def local_max_2d(Z, r):
    from scipy.ndimage import maximum_filter
    m = maximum_filter(np.nan_to_num(Z, nan=-1e9), size=2 * r + 1)
    return np.isfinite(Z) & (Z >= m)


def cmd_measure():
    z = np.load(CACHE)
    V = z["V"].astype(np.float64)
    F = z["F"]
    P0, P1, P2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    N = np.cross(P1 - P0, P2 - P0)
    area2 = np.linalg.norm(N, axis=1)
    ok = area2 > 1e-12
    n = np.zeros_like(N)
    n[ok] = N[ok] / area2[ok, None]
    Cc = (P0 + P1 + P2) / 3.0
    up = n[:, 1] > 0.2
    flat = n[:, 1] > 0.95
    # モデル自身の海面：作業計画 9.4 の値（解B での上向き面の世界 y の中央値 1.198 m。af26_reference.py の SEA_REF_WORLD_Y）。
    # ほぼ水平な面は 3 つの高さに分かれ（台座の底 y −8〜−6.5、海面 0〜1.5、塊の上の平らな所 8.7〜12）、全体の中央値は海面を表さない
    y_sea = 1.1982310754126466
    it = int(np.argmax(V[:, 1]))
    top = V[it]
    H_ref = float(top[1] - y_sea)
    # 波の枠の軸での座標（参照モデル自身の頂が原点）
    def ac(P):
        d = P - top
        return d @ T_TRAVEL, d @ E_CREST
    a_all, c_all = ac(Cc)
    # 高さの地図（0.5 m の格子、上向きの面）：最も高い面（上面）と最も低い上向きの面（唇の下の水面）
    g = 0.5
    a0, a1 = np.floor(a_all.min()), np.ceil(a_all.max())
    c0, c1 = np.floor(c_all.min()), np.ceil(c_all.max())
    na, nc = int((a1 - a0) / g) + 1, int((c1 - c0) / g) + 1
    ia = np.clip(((a_all - a0) / g).astype(int), 0, na - 1)
    ic = np.clip(((c_all - c0) / g).astype(int), 0, nc - 1)
    ymax = np.full((na, nc), np.nan)
    ymin_up = np.full((na, nc), np.nan)
    sel = up
    key = ia[sel] * nc + ic[sel]
    yv = Cc[sel, 1]
    order = np.argsort(key)
    ks, ys = key[order], yv[order]
    uk, st = np.unique(ks, return_index=True)
    mx = np.maximum.reduceat(ys, st)
    mn = np.minimum.reduceat(ys, st)
    ymax.flat[uk] = mx
    ymin_up.flat[uk] = mn
    A = a0 + (np.arange(na) + 0.5) * g
    Cg = c0 + (np.arange(nc) + 0.5) * g
    AA, CC = np.meshgrid(A, Cg, indexing="ij")
    h = ymax - y_sea
    # 手前の小波：頂より前（Δa > 4 m）で、頂から横に ±25 m の中の、上面の局所の最大（半径 3 m）で高さ > 0.1 H
    lm = local_max_2d(h, 6) & (AA > 4.0) & (np.abs(CC) < 40) & (h > 0.1 * H_ref)
    cands = []
    for i, j in zip(*np.nonzero(lm)):
        cands.append(dict(da=float(AA[i, j]), dc=float(CC[i, j]), h=float(h[i, j]), h_over_H=float(h[i, j] / H_ref)))
    cands.sort(key=lambda d: -d["h"])
    # 谷：頂より前（0 < Δa < 0.9 H）、|Δc| < 0.5 H の、最も低い上向きの面（唇の下の水面）の最小
    hl = ymin_up - y_sea
    win = (AA > 0) & (AA < 0.9 * H_ref) & (np.abs(CC) < 0.5 * H_ref) & np.isfinite(hl)
    iw = np.argmin(np.where(win, hl, np.inf))
    ti, tj = np.unravel_index(iw, hl.shape)
    trough = dict(da=float(AA[ti, tj]), dc=float(CC[ti, tj]), depth=float(-hl[ti, tj]), depth_over_H=float(-hl[ti, tj] / H_ref))
    # 谷の底から前（+a）へ、上面が海面へ戻るまでの距離と、前の壁の平均の傾き（底の行 tj に沿って）
    row = hl[ti:, tj]
    rise = np.nan
    for k in range(1, len(row)):
        if np.isfinite(row[k]) and row[k] >= -0.05 * H_ref:
            rise = k * g
            break
    trough["front_wall_run_m"] = float(rise)
    trough["front_wall_run_over_H"] = float(rise / H_ref) if np.isfinite(rise) else None
    trough["front_wall_slope_deg"] = float(np.degrees(np.arctan2(trough["depth"], rise))) if np.isfinite(rise) else None
    # 谷の横の広がり：底の Δa で、深さが底の半分より深い Δc の範囲
    col = hl[ti, :]
    deep = np.isfinite(col) & (col < -0.5 * trough["depth"])
    trough["half_depth_dc_range"] = [float(Cg[deep].min()), float(Cg[deep].max())] if deep.any() else None
    # 右側（+c）：頂から Δc > +0.5 H の上面の最も高い所
    right = np.isfinite(h) & (CC > 0.5 * H_ref)
    ir = np.argmax(np.where(right, h, -np.inf))
    ri, rj = np.unravel_index(ir, h.shape)
    right_max = dict(da=float(AA[ri, rj]), dc=float(CC[ri, rj]), h=float(h[ri, rj]), h_over_H=float(h[ri, rj] / H_ref))
    # モデルの足跡（上面がある範囲）
    has = np.isfinite(h)
    extent = dict(da=[float(AA[has].min()), float(AA[has].max())], dc=[float(CC[has].min()), float(CC[has].max())])
    # 小波の形：最も高い候補の頂から ±方向の裾（高さが頂の 10% になる距離）と、両側の斜面の平均の角
    small = None
    if cands:
        s0 = cands[0]
        i0 = int(np.argmin(np.abs(A - s0["da"])))
        j0 = int(np.argmin(np.abs(Cg - s0["dc"])))
        prof = {}
        for nm, (di, dj) in {"+a": (1, 0), "-a": (-1, 0), "+c": (0, 1), "-c": (0, -1)}.items():
            k, hh = 0, s0["h"]
            while True:
                k += 1
                ii, jj = i0 + di * k, j0 + dj * k
                if not (0 <= ii < na and 0 <= jj < nc) or not np.isfinite(h[ii, jj]):
                    break
                if h[ii, jj] <= 0.1 * s0["h"]:
                    break
            dist = k * g
            prof[nm] = dict(foot_m=float(dist), slope_deg=float(np.degrees(np.arctan2(0.9 * s0["h"], dist))))
        small = dict(apex=s0, profile=prof)
    # 主役の大波の頂（参照）の世界の位置
    out = dict(
        schema="GreatWave.DS30.ref_layout/1",
        source=os.path.basename(SRC), source_sha256=SRC_SHA,
        credit_ja="他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。数値だけを借り、形は写さない。",
        align="解B（作業計画 9.4、align_B_upright.json）", align_sha256=sha256_file(ALIGN),
        axes_ja="Δa は主役波の進む向き t、Δc は波峰線の向き e（K*′ の frame と同じ軸）。原点は参照モデル自身の頂（最も高い点）。長さは m（解B の縮尺）。",
        ref_top_world=[float(v) for v in top], ref_sea_y_world=y_sea, H_ref_m=H_ref,
        small_wave=small, small_wave_candidates=cands[:6], trough=trough, right_side_max=right_max, footprint=extent,
        grid_m=g, faces_up=int(up.sum()),
        note_ja="高さの地図は上向きの面（法線 y > 0.2）の重心を 0.5 m の格子へ落とした最大（上面）と最小（唇の下の水面）。船の浮彫は同じ殻に溶け込んでいるので、局所の最大の候補に船が入りうる（候補の表で確かめる）。",
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "ds30_ref_layout.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 確認用の平面図（数値の確認だけ。Git 対象外の _objcache に置き、キャッシュと一緒に消す）
    try:
        import cv2
        img = np.nan_to_num(np.clip(h / H_ref, -0.4, 1.1), nan=-0.5)
        u8 = ((img + 0.5) / 1.6 * 255).astype(np.uint8)
        col_ = cv2.applyColorMap(u8, cv2.COLORMAP_JET)
        col_ = cv2.resize(col_[::-1], None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(os.path.join(CACHE_DIR, "plan_check_tmp.png"), col_)
    except Exception as ex:  # noqa: BLE001
        print("plan image skipped", ex)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    {"cache": cmd_cache, "measure": cmd_measure, "delete": cmd_delete}[cmd]()
