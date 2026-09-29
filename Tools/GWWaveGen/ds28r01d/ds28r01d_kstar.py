# -*- coding: utf-8 -*-
"""設計28修正01 試行D：K*（t* の姿）をファイルの場所で受け取る読み込みと、足の焼き直し（台座を取って前の谷へ流す。試し）。

README
======
生成器（ds28r01d_model.py）は K* を「フォルダー」で受け取る。フォルダーには次の 3 つがあればよい（名前の頭は自由、1 つずつ）：
  *.gwb        GWW0 書式（先頭 32 バイト 'GWW0' + int32 版, nu, nv, フレーム数, float32 fps, int32 t* フレーム, int32 三角形数、
               UV・UV2（N×2 float32 ずつ）、三角形（M×3 int32）、頂点（N×3 float32、Unity ワールド m））
  *_rows.npz   A（進む向き t の座標）・Y（高さ）・c（波峰線の向き e の行の位置）。(nv, nu)・(nv,)
  *_meta.json  frame{e_crest, t_travel, section_origin_world}・rows{main_row}・profile{index{j_B, j_corner, j_E, ...}}
               （目印の列。無ければ設計27 の既定 18・314・394）
SHA-256 は読み込む時に測って記録する（決まった値との照合はしない。26修正01 の K* のときは設計27 の記録の値と一致する）。

前の谷と背後の谷（Q16 の点2）は、K* の中の「平らな縁」（前は列 j_E より先、後ろは列 j_B より手前）の y < 0 の部分として受け取る：
  split_trough：T* = min(Y, 0)（縁の列だけ）、土台 Y_base = Y − T*（縁は y = 0）。生成器は土台を K* として動かし、
  谷 T* を時間の係数 s_r(τ)（t* で 1）で掛けて足す（near_trough）。t* では土台 + T* = K* そのもの。
  新しい K*′（別の作業が作る）は、はじめから谷へ流れ込む形で来る。その場合もこの分け方で動く（j_E は meta の目印）。

foot_rebake（今の K* の試し。名前の付いた美術の誘導 ds_kstar_foot_rebake）：
  26修正01 の K* は、前の足が高さ約 3 m の鉛直の台座（列 379〜387、Δa ≈ 0.01 m）で、前の谷が無い（Q16 の点2、TR1）。
  列 j_s（既定 370、どの行でも約 0.2H の高さ。下の列は台座と平らな縁）より下を作り直す：
    前面：P_s（K* の列 j_s）から、その点の K* の接線の傾きで出て、谷の底（深さ D_r = d_frac·H_r、a_b = a_s + k_b·H_r + b_0、傾き 0）へ
          3 次 Hermite（途中で急になってから底へなだらかに入る S 字）。y = 0 を切る点を新しい足（列 j_E_new にちょうど置く）。
    前の谷：底 a_b から、シートの前の端（K* の列 399 の a）まで y = −D_r·(1 − S5(u²))（u は 0〜1、S5 は smootherstep。
          底は平らに長く、端で値・傾き 0）。
    背後の谷：列 0〜j_B（後ろの平らな縁）に y = −D_b·(1 − |2u − 1|³)²（D_b = back_frac·D_r、両端で値・傾き 0）。
    座席の船（seat_v1）の平面の足跡（竜骨の線 ± 半幅 + 余白）の所だけ、谷の深さを cap_depth_m まで浅くする（ds_trough_seat_cap。
          重みは足跡からの距離の smoothstep）。
  列 j_s+1〜399 は新しい曲線の上に弧長で配り直す（最初の間隔は K* の列 j_s の間隔、先へ行くほど広く）。UV は変えない（色の焼き付けの
  UV は古い足のまま。試しなので記録だけ）。
使い方：py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_kstar.py --rebake --src Unity/Build/ArtFirst/26修正01/kstar
          --out Unity/Build/Design/28R01D/kstar_foot
"""
import argparse
import copy
import glob
import hashlib
import json
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_KSTAR = "Unity/Build/ArtFirst/26修正01/kstar"
DEFAULT_LANDMARKS = dict(j_B=18, j_corner=314, j_E=394)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")
    except ValueError:
        return p.replace("\\", "/")


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smootherstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x ** 3 * (x * (6 * x - 15) + 10)


# ---------------------------------------------------------------- 読み込み
def find_files(kdir):
    kdir = absrepo(kdir)
    out = {}
    for key, pat in (("gwb", "*.gwb"), ("rows", "*_rows.npz"), ("meta", "*_meta.json")):
        c = sorted(glob.glob(os.path.join(kdir, pat)))
        if len(c) != 1:
            raise SystemExit("[ds28r01d_kstar] %s に %s がちょうど 1 つ要ります（%d 個）" % (rel(kdir), pat, len(c)))
        out[key] = c[0]
    return out


def read_gwb(path):
    b = open(path, "rb").read()
    if b[:4] != b"GWW0":
        raise SystemExit("[ds28r01d_kstar] GWW0 ではありません：%s" % rel(path))
    ver, nu, nv, nfr = struct.unpack("<4i", b[4:20])
    ntri = struct.unpack("<i", b[28:32])[0]
    n = nu * nv
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy()
    o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy()
    o += n * 8
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy()
    o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3 * nfr, o).reshape(nfr, nv, nu, 3).copy()
    return dict(header=b[:32], nu=nu, nv=nv, nfr=nfr, ntri=ntri, uv=uv, uv2=uv2, tris=tris, X=X, tail=b[o + n * 12 * nfr:])


def write_gwb(path, g, X):
    X = np.asarray(X, np.float32).reshape(1, g["nv"], g["nu"], 3)
    hdr = bytearray(g["header"])
    hdr[16:20] = struct.pack("<i", 1)       # フレーム数 1
    with open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(g["uv"].astype(np.float32).tobytes())
        f.write(g["uv2"].astype(np.float32).tobytes())
        f.write(g["tris"].astype(np.int32).tobytes())
        f.write(X.tobytes())


def landmarks_from_meta(meta):
    idx = ((meta or {}).get("profile") or {}).get("index") or {}
    lm = dict(DEFAULT_LANDMARKS)
    for k in ("j_B", "j_corner", "j_E"):
        if k in idx:
            lm[k] = int(idx[k])
    src = "meta.profile.index" if all(k in idx for k in ("j_B", "j_corner", "j_E")) else "既定（設計27）と meta の混ぜ"
    return lm, src


def load(kdir):
    f = find_files(kdir)
    meta = json.load(open(f["meta"], encoding="utf-8"))
    z = np.load(f["rows"])
    lm, lm_src = landmarks_from_meta(meta)
    return dict(dir=rel(absrepo(kdir)), files={k: rel(v) for k, v in f.items()}, paths=f,
                sha={k: sha256_file(v) for k, v in f.items()}, meta=meta,
                A=z["A"].astype(np.float64), Y=z["Y"].astype(np.float64), c=z["c"].astype(np.float64),
                landmarks=lm, landmarks_source=lm_src)


def split_trough(A, Y, jB, jE):
    """平らな縁の y < 0（谷）と土台。戻り (Y_base, T)。T は縁の列だけ 0 でない。"""
    T = np.zeros_like(Y)
    T[:, jE:] = np.minimum(Y[:, jE:], 0.0)
    T[:, :jB + 1] = np.minimum(Y[:, :jB + 1], 0.0)
    return Y - T, T


def world_from_section(meta, c, A, Y):
    fr = meta["frame"]
    O = np.array(fr["section_origin_world"], np.float64)
    e = np.array(fr["e_crest"], np.float64)
    t = np.array(fr["t_travel"], np.float64)
    up = np.array([0.0, 1.0, 0.0])
    return O[None, None] + c[:, None, None] * e[None, None] + A[..., None] * t[None, None] + Y[..., None] * up[None, None]


# ---------------------------------------------------------------- 座席の船の足跡（断面の座標）
def seat_footprint(meta, seat_json):
    S = json.load(open(absrepo(seat_json), encoding="utf-8"))
    wc = S["water_contact"]
    fr = meta["frame"]
    O = np.array(fr["section_origin_world"], np.float64)
    e = np.array(fr["e_crest"], np.float64)
    t = np.array(fr["t_travel"], np.float64)
    p = np.array(wc["p_ref"], np.float64) - O
    ax = np.array(wc["axis_h"], np.float64)
    a0, c0 = float(p @ t), float(p @ e)
    da, dc = float(ax @ t), float(ax @ e)
    s0, s1 = float(wc["s_min"]), float(wc["s_max"])
    keel = lambda s: float(wc["y0"]) + float(wc["slope_dy_ds"]) * s        # noqa: E731
    return dict(a0=a0, c0=c0, da=da, dc=dc, s0=s0, s1=s1, draft=float(wc["draft_m"]),
                end_a=[a0 + da * s0, a0 + da * s1], end_c=[c0 + dc * s0, c0 + dc * s1],
                waterline_y=[keel(s0) + float(wc["draft_m"]), keel(s1) + float(wc["draft_m"])], keel=keel, sha=sha256_file(absrepo(seat_json)))


def footprint_dist(fp, A, C):
    """点 (a, c) から竜骨の線分（平面）までの距離と、線分の上の s。"""
    va, vc = A - fp["a0"], C - fp["c0"]
    s = np.clip(va * fp["da"] + vc * fp["dc"], fp["s0"], fp["s1"])
    return np.hypot(va - s * fp["da"], vc - s * fp["dc"]), s


# ---------------------------------------------------------------- 足の焼き直し（今の K* の試し）
def hermite(y0, m0, y1, m1, h, u):
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    return h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1


def row_foot_curve(a_s, y_s, m_s, H, a_edge, prm):
    """1 行の新しい前面と前の谷 y(a)（a ∈ [a_s, a_edge]）を細かい点列で返す。戻り (a, y, 情報)。"""
    D = float(prm["depth_over_H"]) * H
    kb = float(prm["bottom_ahead_over_H"])
    a_b = min(a_s + kb * H + float(prm.get("bottom_ahead_extra_m", 0.0)), a_s + 0.6 * (a_edge - a_s))
    a1 = np.linspace(a_s, a_b, 400)
    y1 = hermite(y_s, m_s, -D, 0.0, a_b - a_s, (a1 - a_s) / max(a_b - a_s, 1e-9))
    a2 = np.linspace(a_b, a_edge, 600)[1:]
    # 谷の先の端：底から trough_length_over_H·H（シートの前の端まで）。小さい行（手前・奥の端）で谷の面積が本体の断面積に比べて
    # 大きくなりすぎないように（修正1：幅が H によらずシートの端までだった初回は、H 3.5 m の行 60 で窓の水の釣り合い P3 が 3.49）
    a_end = min(a_edge, a_b + float(prm.get("trough_length_over_H", 1e9)) * H)
    u = np.clip((a2 - a_b) / max(a_end - a_b, 1e-9), 0.0, 1.0)
    y2 = -D * (1.0 - smootherstep(u ** float(prm["flat_bottom_power"])))
    a = np.concatenate([a1, a2])
    y = np.concatenate([y1, y2])
    return a, y, dict(D=D, a_b=a_b)


def distribute(P, n, ds0):
    """点列 P（(m, 2)）の上に n 個の点を置く（最初の点は P[0] から ds0 ほど、先へ行くほど広く）。戻り (n, 2)。"""
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    S = s[-1]
    x = np.arange(1, n + 1) / n
    # f(x) = (1 − w) x + w x²、f(1/n)·S = ds0
    w = np.clip((1.0 / n - ds0 / S) / (1.0 / n - 1.0 / n ** 2), 0.0, 0.95)
    f = (1 - w) * x + w * x * x
    q = f * S
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], 1)


def foot_rebake(src, out, prm, seat_json="Tools/GWContext/seat_v1.json", log=print):
    K = load(src)
    A0, Y0, c = K["A"], K["Y"], K["c"]
    nv, nu = A0.shape
    lm = K["landmarks"]
    jB, jE_old = lm["j_B"], lm["j_E"]
    j_s = int(prm["start_col"])
    jE_new = int(prm["foot_col"])
    A, Y = A0.copy(), Y0.copy()
    H = Y0.max(1)
    fp = seat_footprint(K["meta"], seat_json)
    cap = prm["seat_cap"]
    rows_info = {}
    n_face = jE_new - j_s          # 列 j_s+1..jE_new（前面、最後が y = 0）
    n_trough = (nu - 1) - jE_new   # 列 jE_new+1..nu-1（前の谷）
    for r in range(nv):
        if H[r] < float(prm["min_H_m"]):
            # ほとんど平らな行（H < min_H、両端の海）：足より先の列の y ≥ 0 の残り（≤ 1 mm）を 0 にする（土台の縁は y = 0 の約束）
            Y[r, jE_new:] = np.minimum(Y[r, jE_new:], 0.0)
            continue
        a_s, y_s = A0[r, j_s], Y0[r, j_s]
        k0 = j_s - int(prm["tangent_cols"])
        m_s = (Y0[r, j_s] - Y0[r, k0]) / max(A0[r, j_s] - A0[r, k0], 1e-6)
        m_s = min(m_s, -0.05)
        a_edge = A0[r, nu - 1]
        a, y, inf = row_foot_curve(a_s, y_s, m_s, H[r], a_edge, prm)
        # 座席の船の足跡：谷の深さを cap まで浅くする（y < 0 の部分だけ、重みは足跡からの距離）
        if cap.get("on"):
            d, _ = footprint_dist(fp, a, np.full_like(a, c[r]))
            wcap = 1.0 - smoothstep((d - float(cap["half_width_m"]) - float(cap["margin_m"])) / float(cap["falloff_m"]))
            neg = y < 0
            Dr = max(inf["D"], 1e-9)
            k_ = 1.0 - wcap * max(0.0, 1.0 - float(cap["depth_m"]) / Dr)
            y = np.where(neg, y * k_, y)
        # 前面（y ≥ 0）と谷（y ≤ 0）に分け、足（y = 0 を切る点）をちょうど列 jE_new に置く
        iz = int(np.nonzero(y <= 0.0)[0][0])
        f = y[iz - 1] / (y[iz - 1] - y[iz])
        a0 = a[iz - 1] + f * (a[iz] - a[iz - 1])
        face = np.concatenate([np.stack([a[:iz], y[:iz]], 1), [[a0, 0.0]]])
        trough = np.concatenate([[[a0, 0.0]], np.stack([a[iz:], y[iz:]], 1)])
        ds0 = float(np.hypot(A0[r, j_s] - A0[r, j_s - 1], Y0[r, j_s] - Y0[r, j_s - 1]))
        Pf = distribute(face, n_face, max(ds0, 0.05))
        Pf[-1] = [a0, 0.0]
        Pt = distribute(trough, n_trough, max(float(np.hypot(*(Pf[-1] - Pf[-2]))), 0.05))
        Pt[-1] = [a_edge, 0.0]
        A[r, j_s + 1:jE_new + 1] = Pf[:, 0]
        Y[r, j_s + 1:jE_new + 1] = Pf[:, 1]
        A[r, jE_new + 1:] = Pt[:, 0]
        Y[r, jE_new + 1:] = np.minimum(Pt[:, 1], 0.0)
        Y[r, jE_new] = 0.0
        # 背後の谷（列 0..jB）
        Db = float(prm["back_depth_over_front"]) * inf["D"]
        ab = A0[r, :jB + 1]
        Wb = min(ab[-1] - ab[0], float(prm.get("back_width_over_H", 1e9)) * H[r])
        u = (ab - (ab[-1] - Wb)) / max(Wb, 1e-9)
        yb = np.where((u >= 0.0) & (u <= 1.0), -Db * (1.0 - np.abs(2 * np.clip(u, 0, 1) - 1) ** 3) ** 2, 0.0)
        if cap.get("on"):
            d, _ = footprint_dist(fp, ab, np.full_like(ab, c[r]))
            wcap = 1.0 - smoothstep((d - float(cap["half_width_m"]) - float(cap["margin_m"])) / float(cap["falloff_m"]))
            yb = yb * (1.0 - wcap * max(0.0, 1.0 - float(cap["depth_m"]) / max(Db, 1e-9)))
        Y[r, :jB + 1] = yb
        Y[r, jB] = 0.0
        yt = Y[r, jE_new:]
        at = A[r, jE_new:]
        kmin = int(np.argmin(yt))
        half = yt <= 0.5 * yt[kmin]
        body_area = float(np.sum(np.diff(A0[r, jB:j_s + 1]) * 0.5 * (Y0[r, jB:j_s] + Y0[r, jB + 1:j_s + 1])))
        tr_area = float(-np.sum(np.diff(at) * 0.5 * (yt[:-1] + yt[1:]))) + float(-np.sum(np.diff(A0[r, :jB + 1]) * 0.5 * (Y[r, :jB] + Y[r, 1:jB + 1])))
        rows_info[r] = dict(H=float(H[r]), D_front=float(-yt[kmin]), trough_over_body_area=tr_area / max(abs(body_area), 1e-9), D_over_H=float(-yt[kmin] / H[r]), a_foot=float(a0),
                            bottom_ahead_of_foot_m=float(at[kmin] - a0), width_zero_to_edge_m=float(a_edge - a0),
                            width_half_depth_m=float(at[half].max() - at[half].min()) if half.sum() >= 2 else 0.0,
                            D_back=float(-Y[r, :jB + 1].min()), face_slope_start=float(m_s))
    Ybase, T = split_trough(A, Y, jB, jE_new)
    # 書き出し
    os.makedirs(absrepo(out), exist_ok=True)
    g = read_gwb(K["paths"]["gwb"])
    X = world_from_section(K["meta"], c, A, Y)
    base = os.path.splitext(os.path.basename(K["paths"]["gwb"]))[0]
    pg = os.path.join(absrepo(out), base + ".gwb")
    write_gwb(pg, g, X)
    z = dict(np.load(K["paths"]["rows"]))
    z["A"], z["Y"] = A, Y
    pr = os.path.join(absrepo(out), base + "_rows.npz")
    np.savez(pr, **z)
    meta = copy.deepcopy(K["meta"])
    meta["number"] = "設計28修正01 試行D（今の K* の足の焼き直し・試し）"
    meta["key"] = str(meta.get("key", "a45")) + "_foot"
    meta["files"] = dict(gwb=os.path.basename(pg), gwb_sha256=sha256_file(pg), gwb_bytes=os.path.getsize(pg),
                         rows=os.path.basename(pr), rows_sha256=sha256_file(pr), note_ja="obj は書かない（gwb と同じ頂点）")
    meta["profile"]["index"]["j_E"] = jE_new
    meta["profile"]["index"]["j_E_before_rebake"] = jE_old
    meta["profile"]["index"]["j_rebake_start"] = j_s
    rs = sorted(rows_info)
    body = [r for r in rs if rows_info[r]["H"] >= 0.5 * float(H.max())]
    meta["ds28r01d_foot_rebake"] = dict(
        name="ds_kstar_foot_rebake", kind_ja="美術の誘導（K* の立体解釈の修正。今の K* の試し）", params=prm, source=K["dir"],
        source_sha256=K["sha"], seat_json=rel(absrepo(seat_json)), seat_json_sha256=fp["sha"],
        seat_footprint_section=dict(end_a=fp["end_a"], end_c=fp["end_c"], waterline_y_at_ends=fp["waterline_y"]),
        rows_changed=len(rs), max_vertex_move_m=float(np.sqrt((A - A0) ** 2 + (Y - Y0) ** 2).max()),
        body_rows_H_ge_half_peak=dict(n=len(body), D_over_H=[min(rows_info[r]["D_over_H"] for r in body), max(rows_info[r]["D_over_H"] for r in body)],
                                      bottom_ahead_of_foot_m=[min(rows_info[r]["bottom_ahead_of_foot_m"] for r in body),
                                                              max(rows_info[r]["bottom_ahead_of_foot_m"] for r in body)],
                                      width_half_depth_m=[min(rows_info[r]["width_half_depth_m"] for r in body), max(rows_info[r]["width_half_depth_m"] for r in body)],
                                      width_zero_to_edge_m=[min(rows_info[r]["width_zero_to_edge_m"] for r in body),
                                                            max(rows_info[r]["width_zero_to_edge_m"] for r in body)],
                                      trough_over_body_area=[min(rows_info[r]["trough_over_body_area"] for r in body),
                                                             max(rows_info[r]["trough_over_body_area"] for r in body)]),
        all_rows_H_ge_1m_trough_over_body_area=[min(rows_info[r]["trough_over_body_area"] for r in rs if rows_info[r]["H"] >= 1.0),
                                                 max(rows_info[r]["trough_over_body_area"] for r in rs if rows_info[r]["H"] >= 1.0)],
        rows_sample={str(r): rows_info[r] for r in (60, 80, 100, 130, 159, 176, 192, 214, 225) if r in rows_info},
        trough_split_ja="生成器は split_trough（縁の列の min(Y, 0)）で谷を分け、土台を K* として動かす")
    pm = os.path.join(absrepo(out), base + "_meta.json")
    with open(pm, "w", encoding="utf-8", newline="\n") as fo:
        json.dump(meta, fo, ensure_ascii=False, indent=1)
    log("foot_rebake → %s  j_E %d → %d  行 %d  最大の移動 %.2f m" % (rel(absrepo(out)), jE_old, jE_new, len(rs), meta["ds28r01d_foot_rebake"]["max_vertex_move_m"]))
    return meta["ds28r01d_foot_rebake"], A, Y, Ybase, T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebake", action="store_true")
    ap.add_argument("--src", default=DEFAULT_KSTAR)
    ap.add_argument("--out", default="Unity/Build/Design/28R01D/kstar_foot")
    ap.add_argument("--params", default=os.path.join(HERE, "ds28r01d_params.json"))
    a = ap.parse_args()
    if a.rebake:
        prm = json.load(open(a.params, encoding="utf-8"))["kstar_foot_rebake"]
        rec, *_ = foot_rebake(a.src, a.out, prm)
        print(json.dumps(rec["body_rows_H_ge_half_peak"], ensure_ascii=False))
        print(json.dumps(rec["rows_sample"], ensure_ascii=False))
    else:
        K = load(a.src)
        print(json.dumps(dict(dir=K["dir"], files=K["files"], sha=K["sha"], landmarks=K["landmarks"], src=K["landmarks_source"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
