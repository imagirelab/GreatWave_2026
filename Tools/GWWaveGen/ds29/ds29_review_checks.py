# -*- coding: utf-8 -*-
"""設計29 のレビュー対応：採用した原版（設計28 の網）と r02 の網の追加の検査と、描画の傷の密度による違いの確かめ。

レビューの指摘（1〜3）を、記録に書く前に自分で測り直すためのもの。どれも読むだけ（パッケージ・Unity の出力・設計28 の描画）。

  mesh     30 Hz の通し（τ −12〜0 s、361 コマ）で、
             (a) 頂点を 1 つだけ共有する面の組の貫通：片方の面の「共有する頂点の向かいの辺」がもう片方の面の内を通るか
                 （2 つの三角形が 1 頂点を共有して貫通するなら、交わりの線分は共有の頂点から出て、どちらかの向かいの辺で終わる。
                 BVH の検査（ds29_blender_qa.py）は頂点を共有する組を最初に除くので、ここだけで測る）。
                 判定の数は両方の面の最小の高さ ≥ 5 mm の組（BVH の検査と同じ足切り）。_all に全部。
             (b) 折れ返り：隣の面（辺を共有する面）との単位法線の内積 < 0 の隣が 2 つ以上ある面（両方の面が最小の高さ ≥ 5 mm）。
                 指定した面（既定：行 185・列 239・三角形 1）は、各コマの 3 つの隣との内積・長さ（最長の辺）・幅（最小の高さ）を書く。
             --exact で、原版で (a) が出たコマを設計28 の生成器の正確な網（量子化の前、float64）でも測る。
  blender  BVH の 3 次元の自己交差（頂点を共有しない組、両方の面 ≥ 5 mm）を 361 コマ全部で測る（ds29_review_blender.py）。
  temporal t* の前（f295〜f360）の画像の時間の変わり方（コマの差の順、60 px の区画の二階差分）を 4 組で比べる（網に依る飛びがあるか）。
  folds_region  管の天井（行 178〜192・列 200〜300）の τ −1.5〜−0.2 s の折れ（隣 2 つ以上と逆向き）を、内積のしきい値 0・−0.5・−0.8 で数える。
  exact_local  見つかった交差の周り（行 ±6・列 ±14）の頂点を共有しない面の組を総当たりで、包みと設計28 の生成器の正確な網の両方で測る。
  render   原版の 24 枚の静止画と 3 本の動画が設計28 の描画と同じか、描画の傷の場所（唇の端・前面の足・原画視点の左端）の
           密度ごとの画素の差（動画の全コマ）、唇の端の 1:1 の切り出しの並べ図。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py mesh --package src_d28=Unity/Build/Design/28/art_on --package full_r02=Unity/Build/Design/29/r02/full_240x400 --package half_r02=Unity/Build/Design/29/r02/half_120x200 --exact src_d28 --out Unity/Build/Design/29/review
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py blender --package src_d28=Unity/Build/Design/28/art_on … --out Unity/Build/Design/29/review
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py exact_local --package src_d28=Unity/Build/Design/28/art_on --site 54,348@-10.433333,-10.4,-10.366667,-10.333333 --site 60,150@-0.566667,-0.533333,-0.5 --out Unity/Build/Design/29/review
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py folds_region --package src_d28=Unity/Build/Design/28/art_on --package full_r02=Unity/Build/Design/29/r02/full_240x400 --out Unity/Build/Design/29/review
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py temporal --out Unity/Build/Design/29/review
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py render --out Unity/Build/Design/29/review --fig Docs/Evidence/Design/29/fig_ds29_lipend_crops.png
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py crops_zh --fig <試写のフォルダー>/唇部末端_1比1对比.png（試写の中国語の図）
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_review_checks.py summary --out Unity/Build/Design/29/review --evidence Docs/Evidence/Design/29/ds29_review_checks.json
numpy・Pillow。Blender 5.2.2 ヘッドレス、ffmpeg は ds29_record.py と同じ。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import ds29_qa as Q  # noqa: E402  包みの読み込みと Hermite（独立の検査器のもの）

B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
B29 = os.path.join(REPO, "Unity", "Build", "Design", "29")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
RES_ALT = 0.005
HZ = 30


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)


def taus30():
    return [round(-12.0 + k / HZ, 6) for k in range(12 * HZ + 1)]


# ---------------------------------------------------------------- 位相の準備
def one_vertex_pairs(F, nv):
    """頂点をちょうど 1 つ共有する面の組 (f, g) と共有の頂点 v。"""
    nf = len(F)
    vv = F.reshape(-1)
    vf = np.repeat(np.arange(nf), 3)
    o = np.argsort(vv, kind="stable")
    vv, vf = vv[o], vf[o]
    cnt = np.bincount(vv, minlength=nv)
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    pos = np.arange(len(vv)) - start[vv]
    D = int(cnt.max())
    M = -np.ones((nv, D), np.int64)
    M[vv, pos] = vf
    P, S = [], []
    for i in range(D):
        for j in range(i + 1, D):
            ok = (M[:, i] >= 0) & (M[:, j] >= 0)
            P.append(np.stack([M[ok, i], M[ok, j]], 1))
            S.append(np.nonzero(ok)[0])
    P = np.concatenate(P)
    S = np.concatenate(S)
    Fa, Fb = F[P[:, 0]], F[P[:, 1]]
    ns = np.zeros(len(P), np.int64)
    for i in range(3):
        for j in range(3):
            ns += Fa[:, i] == Fb[:, j]
    k = ns == 1
    P, S = P[k], S[k]

    def opp(Fx, v):
        m = Fx != v[:, None]
        idx = np.argsort(~m, axis=1, kind="stable")[:, :2]
        return np.take_along_axis(Fx, idx, 1)
    return P, S, opp(F[P[:, 0]], S), opp(F[P[:, 1]], S)


def edge_neighbours(F):
    """辺を共有する面の組 (fa, fb)。"""
    nf = len(F)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(nf), 3)
    E = np.sort(E, 1)
    key = E[:, 0] * (int(E.max()) + 1) + E[:, 1]
    o = np.argsort(key, kind="stable")
    key, fid = key[o], fid[o]
    same = key[1:] == key[:-1]
    return np.stack([fid[:-1][same], fid[1:][same]], 1)


def seg_tri(P0, P1, A, B, C, eps=1e-7):
    """線分 P0→P1 が三角形 ABC の内を（端と辺を除いて）通るか。戻り値：当たり、線分の端の面からの距離の小さい方（貫通の深さ）。"""
    d = P1 - P0
    e1, e2 = B - A, C - A
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-15
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = P0 - A
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    w = np.einsum("ij,ij->i", d, q) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u > eps) & (w > eps) & (u + w < 1 - eps) & (t > eps) & (t < 1 - eps)
    n = np.cross(e1, e2)
    nl = np.linalg.norm(n, axis=1)
    n = n / np.maximum(nl, 1e-300)[:, None]
    d0 = np.abs(np.einsum("ij,ij->i", P0 - A, n))
    d1 = np.abs(np.einsum("ij,ij->i", P1 - A, n))
    return hit, np.minimum(d0, d1)


def face_geom(X, F):
    a, b, c = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    n = np.cross(b - a, c - a)
    nl = np.linalg.norm(n, axis=1)
    L = np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)], 1)
    emax = L.max(1)
    alt = nl / np.maximum(emax, 1e-15)
    un = n / np.maximum(nl, 1e-300)[:, None]
    return un, alt, emax


def shared_vertex_hits(X, F, P, S, oa, ob, resolv):
    """頂点を 1 つ共有する組の貫通。f の向かいの辺が g を通る、または g の向かいの辺が f を通る。"""
    A = X[S]
    ga, gb = F[P[:, 1]], F[P[:, 0]]
    # g の三角形を共有の頂点 A から張る（残りの 2 頂点 = ob）
    h1, d1 = seg_tri(X[oa[:, 0]], X[oa[:, 1]], A, X[ob[:, 0]], X[ob[:, 1]])
    h2, d2 = seg_tri(X[ob[:, 0]], X[ob[:, 1]], A, X[oa[:, 0]], X[oa[:, 1]])
    del ga, gb
    hit = h1 | h2
    depth = np.where(h1 & h2, np.maximum(d1, d2), np.where(h1, d1, d2))
    rs = resolv[P[:, 0]] & resolv[P[:, 1]]
    return hit, hit & rs, depth


def fold_faces(un, resolv, EN, nf):
    """隣との単位法線の内積 < 0 の隣が 2 つ以上ある面（両方の面が最小の高さ ≥ 5 mm の隣だけ数える）。"""
    dot = np.einsum("ij,ij->i", un[EN[:, 0]], un[EN[:, 1]])
    ok = resolv[EN[:, 0]] & resolv[EN[:, 1]] & (dot < 0)
    c = np.bincount(EN[ok, 0], minlength=nf) + np.bincount(EN[ok, 1], minlength=nf)
    return np.nonzero(c >= 2)[0], dot


# ---------------------------------------------------------------- mesh
def run_mesh(a):
    os.makedirs(a.out, exist_ok=True)
    T = taus30()
    res = {}
    for spec in a.package:
        name, d = spec.split("=", 1)
        t0 = time.time()
        surf = Q.PackageSurface(os.path.join(REPO, d), label=name)
        F = surf.F
        nf = len(F)
        P, S, oa, ob = one_vertex_pairs(F, surf.nv)
        EN = edge_neighbours(F)
        fr_, fc_, fk_ = [int(x) for x in a.face.split(",")]
        track = None
        if surf.grid and fr_ < surf.rows - 1 and fc_ < surf.cols - 1:
            track = (fr_ * (surf.cols - 1) + fc_) * 2 + fk_
            tn = EN[(EN[:, 0] == track) | (EN[:, 1] == track)]
            tn = np.where(tn[:, 0] == track, tn[:, 1], tn[:, 0])
        frames, sv_frames, fold_frames, track_rows = [], [], [], []
        fold_runs = {}
        for k, tau in enumerate(T):
            X = surf.world(tau)
            un, alt, emax = face_geom(X, F)
            resolv = alt >= RES_ALT
            hit, hitr, depth = shared_vertex_hits(X, F, P, S, oa, ob, resolv)
            ff, dot = fold_faces(un, resolv, EN, nf)
            rec = dict(tau=tau, sv_all=int(hit.sum()), sv=int(hitr.sum()), fold_faces=int(len(ff)))
            if hitr.any():
                ii = np.nonzero(hitr)[0]
                rec["sv_pairs"] = [dict(faces=[int(P[i, 0]), int(P[i, 1])], rc=[Q.face_rc(surf, int(P[i, 0])), Q.face_rc(surf, int(P[i, 1]))],
                                        vertex_rc=Q.vert_rc(surf, int(S[i])), depth_mm=round(float(depth[i]) * 1000, 2),
                                        alt_mm=[round(float(alt[P[i, 0]]) * 1000, 1), round(float(alt[P[i, 1]]) * 1000, 1)],
                                        world=[round(float(v), 3) for v in X[S[i]]]) for i in ii[:12]]
                sv_frames.append(k)
            if len(ff):
                rec["fold_faces_rc"] = [Q.face_rc(surf, int(f)) for f in ff[:12]]
                fold_frames.append(k)
            cur = set(int(f) for f in ff)
            for f in cur:
                fold_runs.setdefault(f, []).append(k)
            if track is not None:
                dd = [round(float(np.dot(un[track], un[n])), 3) for n in tn]
                track_rows.append(dict(tau=tau, dots=dd, length_m=round(float(emax[track]), 3), width_mm=round(float(alt[track]) * 1000, 1),
                                       folded=int(sum(1 for x in dd if x < 0) >= 2)))
            frames.append(rec)
        # 折れ返りの続く長さ（連続したコマ）
        runs = []
        for f, ks in fold_runs.items():
            ks = sorted(ks)
            s = ks[0]
            for i in range(1, len(ks) + 1):
                if i == len(ks) or ks[i] != ks[i - 1] + 1:
                    runs.append((ks[i - 1] - s + 1, f, s, ks[i - 1]))
                    if i < len(ks):
                        s = ks[i]
        runs.sort(reverse=True)
        out = dict(label=name, package=rel(surf.dir), rows=surf.rows, cols=surf.cols, faces=nf, one_vertex_pairs=int(len(P)),
                   edge_pairs=int(len(EN)), frames_n=len(T), tau_range=[T[0], T[-1]], res_alt_m=RES_ALT,
                   shared_vertex=dict(frames_with_hits=len(sv_frames), taus=[T[k] for k in sv_frames],
                                      pairs_total=int(sum(fr["sv"] for fr in frames)),
                                      all_incl_slivers_frames=int(sum(1 for fr in frames if fr["sv_all"])),
                                      all_incl_slivers_pairs=int(sum(fr["sv_all"] for fr in frames)),
                                      max_depth_mm=max([p["depth_mm"] for fr in frames for p in fr.get("sv_pairs", [])], default=0.0),
                                      detail=[fr for fr in frames if fr["sv"]]),
                   folds=dict(frames_with_folds=len(fold_frames), fold_face_frames=int(sum(fr["fold_faces"] for fr in frames)),
                              longest_runs=[dict(frames=r[0], face=r[1], rc=Q.face_rc(surf, r[1]), tau=[T[r[2]], T[r[3]]]) for r in runs[:10]],
                              runs_ge3=int(sum(1 for r in runs if r[0] >= 3)),
                              transient_note_ja="transient = t* の前に終わる折れ返り（t* の網＝K* の折れ目に続くものを除く）",
                              transient_runs_ge3=int(sum(1 for r in runs if r[0] >= 3 and r[3] < len(T) - 1)),
                              transient_longest=[dict(frames=r[0], face=r[1], rc=Q.face_rc(surf, r[1]), tau=[T[r[2]], T[r[3]]])
                                                 for r in runs if r[3] < len(T) - 1][:12],
                              faces_folded_at_tstar=int(frames[-1]["fold_faces"]),
                              per_frame=[[fr["tau"], fr["fold_faces"]] for fr in frames if fr["fold_faces"]]),
                   runtime_s=round(time.time() - t0, 1))
        if track is not None:
            tr = [r for r in track_rows if a.track_from <= r["tau"] <= a.track_to]
            fl = [r for r in track_rows if r["folded"]]
            out["tracked_face"] = dict(rc=[fr_, fc_, fk_], face=int(track), neighbours=[int(x) for x in tn], rows=tr,
                                       folded_frames=len(fl), folded_tau=[fl[0]["tau"], fl[-1]["tau"]] if fl else None,
                                       folded_length_m=[min(r["length_m"] for r in fl), max(r["length_m"] for r in fl)] if fl else None,
                                       folded_width_mm=[min(r["width_mm"] for r in fl), max(r["width_mm"] for r in fl)] if fl else None,
                                       folded_dots_min=[min(min(r["dots"]) for r in fl), max(min(r["dots"]) for r in fl)] if fl else None)
            # 座席 v1 の目からの距離と、面の幅が見込む角度（射線の間隔 0.64° と比べる）
            seat = json.load(open(Q.SEAT_JSON, encoding="utf-8"))
            eye = np.array(seat["seat"]["eye_world"], float)
            if fl:
                X = surf.world(fl[len(fl) // 2]["tau"])
                c = X[F[track]].mean(0)
                dist = float(np.linalg.norm(c - eye))
                out["tracked_face"]["seat_distance_m"] = round(dist, 2)
                out["tracked_face"]["width_angle_deg_at_mid"] = round(float(np.degrees(fl[len(fl) // 2]["width_mm"] / 1000 / dist)), 4)
        # 正確な網（量子化の前）で、(a) が出たコマを測り直す
        if a.exact and name in a.exact and sv_frames:
            sys.path.insert(0, os.path.join(HERE, "..", "ds28"))
            sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
            import ds28_model as M8
            g = M8.Generator("art_on", log=None)
            ex = []
            for k in sv_frames:
                Xe = np.asarray(g.world(float(T[k])), np.float64).reshape(-1, 3)
                un, alt, emax = face_geom(Xe, F)
                resolv = alt >= RES_ALT
                hit, hitr, depth = shared_vertex_hits(Xe, F, P, S, oa, ob, resolv)
                ex.append(dict(tau=T[k], sv_all=int(hit.sum()), sv=int(hitr.sum()),
                               quant_diff_max_mm=round(float(np.abs(Xe - surf.world(T[k])).max()) * 1000, 3)))
            out["shared_vertex"]["exact_generator"] = ex
        jdump(os.path.join(a.out, "mesh_%s.json" % name), out)
        print("DS29REV mesh %s sv_frames=%d sv_pairs=%d folds_frames=%d runs_ge3=%d %.0fs" % (
            name, len(sv_frames), out["shared_vertex"]["pairs_total"], len(fold_frames), out["folds"]["runs_ge3"], time.time() - t0), flush=True)
        res[name] = out
    return res


# ---------------------------------------------------------------- blender（361 コマの BVH）
def run_blender(a):
    os.makedirs(a.out, exist_ok=True)
    T = taus30()
    for spec in a.package:
        name, d = spec.split("=", 1)
        surf = Q.PackageSurface(os.path.join(REPO, d), label=name)
        V = np.stack([surf.world(t).astype(np.float32) for t in T])
        npz = os.path.join(a.out, "bvh_%s_in.npz" % name)
        np.savez(npz, V=V, F=surf.F.astype(np.int32), taus=np.array(T), res_alt=np.array(RES_ALT))
        del V
        outj = os.path.join(a.out, "bvh_%s.json" % name)
        t0 = time.time()
        p = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                            os.path.join(HERE, "ds29_review_blender.py"), "--", npz, outj], capture_output=True, text=True, encoding="utf-8", errors="replace")
        with open(os.path.join(a.out, "bvh_%s.log" % name), "w", encoding="utf-8", newline="\n") as f:
            f.write(p.stdout + "\n---- stderr ----\n" + p.stderr)
        try:
            os.remove(npz)
        except OSError:
            pass
        if p.returncode != 0:
            raise SystemExit("Blender が失敗しました：%s" % name)
        B = json.load(open(outj, encoding="utf-8"))
        B["package"] = rel(surf.dir)
        B["runtime_s"] = round(time.time() - t0, 1)
        jdump(outj, B)
        print("DS29REV bvh %s frames=%d with_selfx=%d pairs=%d %.0fs" % (name, B["frames_n"], B["frames_with_selfx"], B["pairs_total"], time.time() - t0), flush=True)


# ---------------------------------------------------------------- render
SETS = [("src_d28", "原版（設計28 の網）", os.path.join(B29, "unity", "src_d28")),
        ("half_r02", "軽量版 120 × 200・r02", os.path.join(B29, "unity", "half_120x200_r02")),
        ("full_r02", "張り直し 240 × 400・r02", os.path.join(B29, "unity", "full_240x400_r02")),
        ("double_r01", "約 2 倍 480 × 800・r01", os.path.join(B29, "unity", "double_480x800"))]
# 描画の傷を見る所（1920 × 1080 の画素、x0, y0, x1, y1）
REGIONS = {"seat_toward_wave": {"lip_end": (940, 0, 1200, 560), "face_foot": (0, 330, 1300, 420)},
           "painting": {"left_edge": (0, 200, 400, 800)}}
CROP_TAUS = [-1.333, -1.0, -0.6, -0.3, 0.0]


def video_frames(mp4, idx=None, crop=None):
    """mp4 を RGB で読む（idx があればその番号のコマだけ、crop = (x0, y0, x1, y1) があればその領域だけ）。"""
    cmd = [FFMPEG, "-v", "error", "-i", mp4]
    vf = []
    if idx is not None:
        vf.append("select='%s'" % "+".join("eq(n\\,%d)" % i for i in idx))
    w, h = 1920, 1080
    if crop is not None:
        x0, y0, x1, y1 = crop
        w, h = x1 - x0, y1 - y0
        vf.append("crop=%d:%d:%d:%d" % (w, h, x0, y0))
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if idx is not None:
        cmd += ["-vsync", "0"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def warp_frame_taus(n):
    w = json.load(open(os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json"), encoding="utf-8"))
    return np.interp(np.arange(n) / 30.0, np.array(w["t"]), np.array(w["tau"]))


SETS_ZH = {"src_d28": "原版（设计28 的网格）", "half_r02": "轻量版 120×200·r02", "full_r02": "重新布网 240×400·r02", "double_r01": "约2倍 480×800·r01"}


def make_crops(fig, zh=False):
    """唇の端の 1:1 の切り出しの並べ図。行 = 4 組、列 = τ（座席から波の方向）＋座席 v1 の t*。"""
    from PIL import Image, ImageDraw, ImageFont
    fidx = []
    tw = warp_frame_taus(421)
    for t in CROP_TAUS:
        fidx.append(int(np.argmin(np.abs(tw[:361] - t))) if t < 0 else 360)
    crops = {}
    for key, ja, d in SETS:
        fr = video_frames(os.path.join(d, "video", "ds29_seat_toward_wave_30fps.mp4"), fidx, crop=(940, 0, 1200, 560))
        crops[key] = [fr[i] for i in range(len(fidx))]
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc" if zh else "C:/Windows/Fonts/YuGothM.ttc", 20)
    cw, chh, lw, th = 260, 560, 250, 34
    seat_w, seat_h = 480, 420
    W = lw + cw * len(fidx) + 12 + seat_w
    H = th + chh * len(SETS)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    for j, t in enumerate(CROP_TAUS):
        dr.text((lw + cw * j + 6, 6), "τ %+.3f s（f%d）" % (tw[fidx[j]], fidx[j]), fill=(0, 0, 0), font=font)
    dr.text((lw + cw * len(fidx) + 18, 6), ("座位 v1 原画瞬间（x 700–1180, y 520–940）" if zh else "座席 v1 の t*（x 700–1180, y 520–940）"), fill=(0, 0, 0), font=font)
    for i, (key, ja, d) in enumerate(SETS):
        y = th + chh * i
        dr.text((6, y + 8), SETS_ZH[key] if zh else ja, fill=(0, 0, 0), font=font)
        for j in range(len(fidx)):
            img.paste(Image.fromarray(crops[key][j]), (lw + cw * j, y))
        s = Image.open(os.path.join(d, "stills", "ds29_seat_tstar_tau+0.000.png")).convert("RGB").crop((700, 520, 1180, 940))
        img.paste(s, (lw + cw * len(fidx) + 12, y + (chh - seat_h) // 2))
    dr.text((6, H - 60), ("1:1（未缩小）。左 5 列：从座位看来浪方向的唇部末端" if zh else "1:1（縮小なし）"), fill=(80, 80, 80), font=font)
    os.makedirs(os.path.dirname(fig), exist_ok=True)
    img.save(fig, optimize=False)
    return dict(fig=rel(fig) if fig.startswith(REPO) else os.path.basename(fig), frames=fidx, taus=[round(float(tw[i]), 3) for i in fidx],
                seat_toward_wave_crop=[940, 0, 1200, 560], seat_v1_tstar_crop=[700, 520, 1180, 940])


def run_render(a):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(a.out, exist_ok=True)
    out = {}
    # 1) 原版の静止画 24 枚と動画 3 本が設計28 の描画と同じか
    st = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left"):
        for s_, tau in (("a", "-4.433"), ("b", "-3.500"), ("c", "-2.933"), ("d", "-2.250"), ("apex", "-1.333"), ("tstar", "+0.000")):
            p29 = os.path.join(B29, "unity", "src_d28", "stills", "ds29_%s_%s_tau%s.png" % (v, s_, tau))
            d28 = "art_on_default" if v == "seat_toward_wave" else "art_on_default_stages"
            p28 = os.path.join(B28, d28, "stills", "ds27_%s_%s_tau%s.png" % (v, s_, tau))
            A_ = np.asarray(Image.open(p29).convert("RGB"), np.int16)
            B_ = np.asarray(Image.open(p28).convert("RGB"), np.int16)
            st.append(dict(view=v, stage=s_, ds29=rel(p29), ds28=rel(p28), differing_pixels=int((np.abs(A_ - B_).max(2) > 0).sum()) if A_.shape == B_.shape else None))
    vids = []
    for v in ("painting", "seat_toward_wave", "side_left"):
        p29 = os.path.join(B29, "unity", "src_d28", "video", "ds29_%s_30fps.mp4" % v)
        p28 = os.path.join(B28, "art_on_default", "video", "ds27_%s_30fps.mp4" % v)
        vids.append(dict(view=v, ds29=rel(p29), ds28=rel(p28), sha256_ds29=sha(p29), sha256_ds28=sha(p28), same=sha(p29) == sha(p28)))
    out["original_vs_ds28"] = dict(stills=st, stills_identical=int(sum(1 for x in st if x["differing_pixels"] == 0)), stills_n=len(st), videos=vids)
    # 2) 傷の場所の密度ごとの画素の差（原版との、全コマ）。「違う画素」= RGB のどれかが 24/255 を超えて違う画素（mp4 の圧縮の揺れを除く）
    reg = {}
    for v, regions in REGIONS.items():
        for rn, (x0, y0, x1, y1) in regions.items():
            ref = video_frames(os.path.join(SETS[0][2], "video", "ds29_%s_30fps.mp4" % v), crop=(x0, y0, x1, y1))
            taus = warp_frame_taus(len(ref))
            for key, ja, d in SETS[1:]:
                oth = video_frames(os.path.join(d, "video", "ds29_%s_30fps.mp4" % v), crop=(x0, y0, x1, y1))
                n = min(len(ref), len(oth))
                fr = []
                for i in range(n):
                    dd = np.abs(ref[i].astype(np.int16) - oth[i].astype(np.int16)).max(2) > 24
                    fr.append(float(dd.mean()))
                fr = np.array(fr)
                act = taus[:n] >= -4.433
                reg.setdefault(v, {}).setdefault(rn, {})[key] = dict(region=[x0, y0, x1, y1], frames=n, peak=round(float(fr.max()), 4),
                                                                     peak_tau=round(float(taus[int(fr.argmax())]), 3),
                                                                     mean_from_a=round(float(fr[act].mean()), 4))
    out["artefact_regions_vs_original"] = dict(threshold_ja="RGB のどれかが 24/255 を超えて違う画素の割合（領域の画素に対する）。mp4 どうしの比較",
                                               values=reg)
    # 3) 唇の端の 1:1 の切り出し（座席から波の方向の動画、x 940–1200・y 0–560）と、座席 v1 の t* の静止画（x 700–1180・y 520–940）
    out["lipend_crops"] = make_crops(a.fig, zh=False)
    jdump(os.path.join(a.out, "render_checks.json"), out)
    print("DS29REV render stills_identical=%d/%d videos_same=%d" % (out["original_vs_ds28"]["stills_identical"], len(st), sum(x["same"] for x in vids)), flush=True)


# ---------------------------------------------------------------- exact_local
def tri_tri(X, F, A, B):
    """面の組 (A, B) の三角形どうしの交差（どちらかの辺がもう片方の面の内を通る）。頂点を共有しない組に使う。"""
    hit = np.zeros(len(A), bool)
    for f, g in ((A, B), (B, A)):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            h, _ = seg_tri(X[F[f, i]], X[F[f, j]], X[F[g, 0]], X[F[g, 1]], X[F[g, 2]], eps=1e-9)
            hit |= h
    return hit


def run_exact_local(a):
    """原版（格子）で見つかった交差の周り（行 ±6・列 ±14）の、頂点を共有しない面の組を総当たりで、
    包み（16 ビットの量子化）と設計28 の生成器の正確な網（float64）の両方で測る。BVH の 361 コマの結果の出どころの確かめ。"""
    sys.path.insert(0, os.path.join(HERE, "..", "ds28"))
    sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
    import ds28_model as M8
    name, d = a.package[0].split("=", 1)
    surf = Q.PackageSurface(os.path.join(REPO, d), label=name)
    F = surf.F
    g = M8.Generator("art_on", log=None)
    out = dict(label=name, package=rel(surf.dir), res_alt_m=RES_ALT, cases=[])
    for spec in a.site:
        rc, taus = spec.split("@")
        r0, c0 = [int(x) for x in rc.split(",")]
        sel = []
        for r in range(max(0, r0 - 6), min(surf.rows - 1, r0 + 6)):
            for c in range(max(0, c0 - 14), min(surf.cols - 1, c0 + 14)):
                q = r * (surf.cols - 1) + c
                sel += [2 * q, 2 * q + 1]
        sel = np.array(sel)
        I, J = np.meshgrid(np.arange(len(sel)), np.arange(len(sel)), indexing="ij")
        m = I < J
        A, B = sel[I[m]], sel[J[m]]
        Fa, Fb = F[A], F[B]
        share = np.zeros(len(A), bool)
        for i in range(3):
            for j in range(3):
                share |= Fa[:, i] == Fb[:, j]
        A, B = A[~share], B[~share]
        for t in [float(x) for x in taus.split(",")]:
            Xq = surf.world(t)
            Xe = np.asarray(g.world(t), np.float64).reshape(-1, 3)
            rq = face_geom(Xq, F)[1] >= RES_ALT
            re_ = face_geom(Xe, F)[1] >= RES_ALT
            hq = tri_tri(Xq, F, A, B)
            he = tri_tri(Xe, F, A, B)
            kq = hq & rq[A] & rq[B]
            ke = he & re_[A] & re_[B]
            out["cases"].append(dict(site_rc=[r0, c0], tau=t, pairs_tested=int(len(A)), quantized_all=int(hq.sum()), quantized=int(kq.sum()),
                                     quantized_pairs_rc=[[Q.face_rc(surf, int(x)), Q.face_rc(surf, int(y))] for x, y in zip(A[kq], B[kq])],
                                     exact_all=int(he.sum()), exact=int(ke.sum())))
    jdump(os.path.join(a.out, "exact_local_%s.json" % name), out)
    print("DS29REV exact_local %s cases=%d quantized=%d exact=%d" % (name, len(out["cases"]), sum(c["quantized"] for c in out["cases"]),
                                                                    sum(c["exact"] for c in out["cases"])), flush=True)


# ---------------------------------------------------------------- folds_region
def run_folds_region(a):
    """管の天井（行 178〜192・列 200〜300、格子の番号）の τ −1.5〜−0.2 s（30 Hz）で、隣 2 つ以上と単位法線の内積が
    しきい値（0・−0.5・−0.8）より小さい面（両方の面が最小の高さ ≥ 5 mm）を数える。行 185 の折れと同じ種類の折れが
    ほかの面にもあるかを、原版と張り直しで比べる（網の番号は同じ行、列は網ごとに違う点）。"""
    out = {}
    for spec in a.package:
        name, d = spec.split("=", 1)
        surf = Q.PackageSurface(os.path.join(REPO, d), label=name)
        F = surf.F
        nf = len(F)
        EN = edge_neighbours(F)
        rows = (np.arange(nf) // 2) // (surf.cols - 1)
        cols = (np.arange(nf) // 2) % (surf.cols - 1)
        reg = (rows >= 178) & (rows <= 192) & (cols >= 200) & (cols <= 300)
        T = [t for t in taus30() if -1.5 - 1e-9 <= t <= -0.2 + 1e-9]
        res = {}
        acc = {thr: [0, 0, set()] for thr in (0.0, -0.5, -0.8)}
        for t in T:
            un, alt, emax = face_geom(surf.world(t), F)
            rv = alt >= RES_ALT
            dot = np.einsum("ij,ij->i", un[EN[:, 0]], un[EN[:, 1]])
            for thr in acc:
                ok = rv[EN[:, 0]] & rv[EN[:, 1]] & (dot < thr)
                c = np.bincount(EN[ok, 0], minlength=nf) + np.bincount(EN[ok, 1], minlength=nf)
                ff = np.nonzero((c >= 2) & reg)[0]
                if len(ff):
                    acc[thr][0] += 1
                    acc[thr][1] += int(len(ff))
                    acc[thr][2] |= set(int(f) for f in ff)
        for thr, (fr, tot, faces) in acc.items():
            res["dot_lt_%g" % thr] = dict(frames=fr, face_frames=tot, faces=len(faces),
                                          faces_rc=[Q.face_rc(surf, f) for f in sorted(faces)][:40])
        out[name] = dict(package=rel(surf.dir), rows=[178, 192], cols=[200, 300], tau=[T[0], T[-1]], frames_n=len(T), values=res)
        print("DS29REV folds_region %s %s" % (name, {k: (v["frames"], v["face_frames"], v["faces"]) for k, v in res.items()}), flush=True)
    jdump(os.path.join(a.out, "folds_region.json"), out)


# ---------------------------------------------------------------- temporal
def run_temporal(a):
    """t* の前（f295〜f360、τ −0.93〜0 s）の画像の時間の変わり方を 4 組で比べる。
    (1) コマの差の平均（全画面、|f[i] − f[i−1]|）の大きいコマの順、(2) 60 × 60 px の区画ごとの二階差分 |f[i+1] − 2f[i] + f[i−1]| の
    最大を原版と各組で比べ、原版だけに出る区画（原版の値が 20 以上で、比べる組の 2 倍を超える）を数える（行 185 の折れなどの網に依る飛びの確かめ）。"""
    views = ["painting", "seat_toward_wave", "side_left"]
    f0, f1 = 295, 360
    tw = warp_frame_taus(421)
    out = dict(frames=[f0, f1], tau=[round(float(tw[f0]), 3), round(float(tw[f1]), 3)], tile_px=60,
               note_ja="mp4 どうしの比較（0〜255 の RGB の平均）。原版だけの区画 = 原版の区画の二階差分の最大 ≥ 20 かつ比べる組の 2 倍を超える", views={})
    for v in views:
        curves, tiles = {}, {}
        for key, ja, d in SETS:
            idx = list(range(f0, f1 + 1))
            fr = video_frames(os.path.join(d, "video", "ds29_%s_30fps.mp4" % v), idx).astype(np.float32)
            dif = np.abs(fr[1:] - fr[:-1]).mean(axis=(1, 2, 3))
            curves[key] = dif
            sd = np.abs(fr[2:] - 2 * fr[1:-1] + fr[:-2]).mean(3)
            H, W = sd.shape[1] // 60 * 60, sd.shape[2] // 60 * 60
            t_ = sd[:, :H, :W].reshape(sd.shape[0], H // 60, 60, W // 60, 60).mean((2, 4))
            tiles[key] = t_.max(0)
            del fr, sd
        ref = curves["src_d28"]
        top = [int(f0 + 1 + i) for i in np.argsort(ref)[::-1][:6]]
        vv = dict(top_frames_original=top, top_tau_original=[round(float(tw[i]), 3) for i in top], sets={})
        for key, ja, d in SETS[1:]:
            c = curves[key]
            only = (tiles["src_d28"] >= 20) & (tiles["src_d28"] > 2 * tiles[key])
            vv["sets"][key] = dict(top_frames=[int(f0 + 1 + i) for i in np.argsort(c)[::-1][:6]],
                                   curve_corr_with_original=round(float(np.corrcoef(ref, c)[0, 1]), 4),
                                   curve_max_abs_diff=round(float(np.abs(ref - c).max()), 3),
                                   tiles_only_in_original=int(only.sum()),
                                   tiles_only_in_original_xy=[[int(q) * 60, int(r) * 60] for r, q in zip(*np.nonzero(only))][:10],
                                   tile_max_original=round(float(tiles["src_d28"].max()), 2), tile_max_set=round(float(tiles[key].max()), 2))
        out["views"][v] = vv
        print("DS29REV temporal %s top=%s %s" % (v, top, {k: (x["curve_corr_with_original"], x["tiles_only_in_original"]) for k, x in vv["sets"].items()}), flush=True)
    jdump(os.path.join(a.out, "temporal.json"), out)


# ---------------------------------------------------------------- summary
def run_summary(a):
    S = dict(schema="GreatWave.DS29.review_checks/1", number="設計29（レビュー対応）", script="Tools/GWWaveGen/ds29/ds29_review_checks.py")
    for fn in sorted(os.listdir(a.out)):
        p = os.path.join(a.out, fn)
        if fn.endswith(".json") and (fn.startswith("mesh_") or fn.startswith("bvh_") or fn.startswith("exact_local_") or fn in ("render_checks.json", "folds_region.json", "temporal.json")):
            J = json.load(open(p, encoding="utf-8"))
            if fn.startswith("mesh_"):
                J["shared_vertex"]["detail"] = J["shared_vertex"]["detail"][:12]
                if "tracked_face" in J:
                    J["tracked_face"]["rows"] = [r for r in J["tracked_face"]["rows"]]
            if fn.startswith("bvh_"):
                J["frames"] = [f for f in J["frames"] if f["self_intersections"]]
            S[fn[:-5]] = J
            S.setdefault("sources", []).append(dict(path=rel(p), sha256=sha(p)))
    jdump(a.evidence, S)
    print("DS29REV summary", rel(a.evidence))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mesh", "blender", "exact_local", "folds_region", "temporal", "render", "crops_zh", "summary"])
    ap.add_argument("--site", action="append", default=[], help="exact_local：行,列@τ,τ,…")
    ap.add_argument("--package", action="append", default=[])
    ap.add_argument("--exact", action="append", default=[])
    ap.add_argument("--face", default="185,239,1")
    ap.add_argument("--track-from", type=float, default=-1.2)
    ap.add_argument("--track-to", type=float, default=-0.2)
    ap.add_argument("--out", default=os.path.join(B29, "review"))
    ap.add_argument("--fig", default=os.path.join(REPO, "Docs", "Evidence", "Design", "29", "fig_ds29_lipend_crops.png"))
    ap.add_argument("--evidence", default=os.path.join(REPO, "Docs", "Evidence", "Design", "29", "ds29_review_checks.json"))
    a = ap.parse_args()
    a.out = os.path.join(REPO, a.out) if not os.path.isabs(a.out) else a.out
    a.fig = os.path.join(REPO, a.fig) if not os.path.isabs(a.fig) else a.fig
    a.evidence = os.path.join(REPO, a.evidence) if not os.path.isabs(a.evidence) else a.evidence
    if a.cmd == "crops_zh":
        make_crops(a.fig, zh=True)
        return
    {"mesh": run_mesh, "blender": run_blender, "exact_local": run_exact_local, "folds_region": run_folds_region, "temporal": run_temporal, "render": run_render, "summary": run_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
