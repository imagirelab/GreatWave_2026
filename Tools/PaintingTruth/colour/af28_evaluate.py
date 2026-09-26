# -*- coding: utf-8 -*-
"""番号28 第B部：投影ベイクと NPR shader v1 の評価、証拠の図、metrics.json・run.json。

使い方（リポジトリの根で実行。py -3.10、numpy・OpenCV・PIL だけ）:
    py -3.10 Tools/PaintingTruth/colour/af28_evaluate.py

入力：
    Unity/Build/ArtFirst/28/render/<key>/*.png   Unity の描画（AF28NprScene.Render）。色区 ID は 3840×2160・主役波だけ
    Unity/Build/ArtFirst/28/bake/*.json, *.bin    焼いたテクスチャと集計（AF28ProjectionBaker）
    Unity/Build/ArtFirst/28/partA/stage_a.npz     第A部の色区の地図（線を両側へ吸収した高解像度の地図 mw_region）
    Tools/PaintingTruth/colour/colour_truth.json・colour_polylines.json・colour_annotations.json（第A部の正解）
出力：
    Docs/Evidence/ArtFirst/28/28B_*.png、metrics.json、run.json
評価の約束：
    ・t* = 12.0 s の PaintingCam v1、表示フレーム 1920×1080。色区 ID（3840×2160）を 2×2 平均して色区ごとの被覆率にし、
      番号23 の評価器と同じく σ 1 px で平滑して 0.5 の等値線の点にする（採点列 157〜1762）。
    ・主役波以外（前景の波、船、右の海など。原画で主役波の外の画素）は、原画の色区の地図の値で置き換えて比べる
      （番号27・39 の範囲の遮蔽物を原画のものにした合成の評価）。空との境（主役波の輪郭）は描画のままにする。
    ・項目の境界：第A部の折れ線（colour_polylines.json）から表示 1.5 px 以内の真値の境界点を、その項目の対象とする。
      描画の境界点は、同じ色区の真値の境界点のうち最も近い点へ割り当てる（番号23 の評価器と同じラベル付き対称 Hausdorff）。
"""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PT))
sys.path.insert(0, PT)
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import colour_truth as CT  # noqa: E402  Frame・_pil_text・disk（第A部と同じ写像）

PARAMS_REL = "Tools/PaintingTruth/colour/af28_params.json"
CT_REL = "Tools/PaintingTruth/colour/colour_truth.json"
POLY_REL = "Tools/PaintingTruth/colour/colour_polylines.json"
ANN_REL = "Tools/PaintingTruth/colour/colour_annotations.json"
STAGE_REL = "Unity/Build/ArtFirst/28/partA/stage_a.npz"
BUILD_REL = "Unity/Build/ArtFirst/28"
EVID_REL = "Docs/Evidence/ArtFirst/28"
ENV_REL = "Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
SKY_ENV_REL = "Tools/PaintingTruth/targets/masks/sky_envelope_cov.png"
LW_REL = "Tools/PaintingTruth/targets/line_width_profile.json"
CLASSES = ["white", "mizuiro", "ai_mid", "ai_dark"]
CLS_VAL = {"out": 0, "white": 1, "mizuiro": 2, "ai_mid": 3, "ai_dark": 4, "sky": 9}
STACK = ["out", "white", "mizuiro", "ai_mid", "ai_dark", "sky"]
ID_RGB = {"sky": (255, 255, 255), "white": (255, 0, 0), "mizuiro": (0, 255, 0), "ai_mid": (0, 0, 255), "ai_dark": (255, 255, 0), "line": (255, 0, 255)}
PASS_PX = 4.0
W, H = 1920, 1080


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def r3(v):
    return None if v is None else (round(float(v), 3) if np.isscalar(v) else [round(float(x), 3) for x in v])


def jl(path):
    return json.load(open(path, encoding="utf-8"))


# ================================================================= 地図
def truth_maps(stage):
    z = np.load(stage, allow_pickle=True)
    reg = z["mw_region"]
    fr = CT.Frame(reg.shape[1], reg.shape[0])
    cov = {n: fr.hi_to_disp_cov(reg == CLS_VAL[n]) for n in STACK}
    lab = np.array([CLS_VAL[n] for n in STACK], np.uint8)[np.stack([cov[n] for n in STACK], -1).argmax(-1)]
    return z, fr, cov, lab


def render_maps(ids_path, cov_t):
    ids = T.imread_rgb(ids_path)
    f = ids.shape[0] // H
    if ids.shape[:2] != (H * f, W * f):
        raise SystemExit("ID 画像の大きさが違います: %s" % (ids.shape,))
    known = np.zeros(ids.shape[:2], bool)
    cov = {}
    for n in ["white", "mizuiro", "ai_mid", "ai_dark", "sky", "line"]:
        m = np.all(ids == np.array(ID_RGB[n], np.uint8)[None, None], -1)
        known |= m
        cov[n] = m.astype(np.float64).reshape(H, f, W, f).mean((1, 3)) if f > 1 else m.astype(np.float64)
    unknown = int((~known).sum())
    # 合成：原画で主役波の外（前景の波・船・右の海など）の割合 a だけ、原画の値に置き換える
    a = np.clip(cov_t["out"], 0, 1)
    comp = {n: (1 - a) * cov.get(n, np.zeros((H, W))) for n in STACK if n != "out"}
    comp["out"] = a
    # 描画の線（外殻線）は色区の評価では使わない（line の画素は描画の ID に入れていない前提。入っていれば数える）
    lab = np.array([CLS_VAL[n] for n in STACK], np.uint8)[np.stack([comp[n] for n in STACK], -1).argmax(-1)]
    return ids, cov, comp, lab, unknown


def iso_pts(cov, sigma):
    f = cv2.GaussianBlur(np.asarray(cov, np.float64), (0, 0), sigma) if sigma > 0 else cov
    p = T.iso_points(f, 0.5)
    return p[(p[:, 0] >= 157) & (p[:, 0] <= 1762)]


def resample_lines(lines, step=0.25):
    out = [T.resample_polyline(np.asarray(L, np.float64), step) for L in lines if len(L) >= 2]
    out += [np.asarray(L, np.float64) for L in lines if len(L) == 1]
    return np.vstack(out) if out else np.zeros((0, 2))


def dist_to(mask):
    """mask（True）までの距離（表示 px）。"""
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)


def sample(img, pts):
    q = np.clip(np.round(pts).astype(int), 0, [W - 1, H - 1])
    return img[q[:, 1], q[:, 0]]


class ClassBoundary:
    """色区 k の真値と描画の境界点、描画→真値の最近点（キャッシュ）。

    空との境（主役波の輪郭）は 78〜132・72（番号26）の対象なので、色区の境界の項目からは除く：
    真値は真値の空から ex px 以内の境界点を選ばず、描画は描画の空から ex px 以内の境界点を割り当てに数えない。
    """

    def __init__(self, k, cov_t, cov_r, sigma, dsky_t, dsky_r, ex):
        self.k = k
        self.tp = iso_pts(cov_t[k], sigma)
        self.rp = iso_pts(cov_r[k], sigma)
        self.d_rt, self.i_rt = T.nearest(self.rp, self.tp)
        self.tp_sky = sample(dsky_t, self.tp) <= ex
        self.rp_sky = sample(dsky_r, self.rp) <= ex

    def select(self, lines, dsel):
        Q = resample_lines(lines)
        if len(Q) == 0 or len(self.tp) == 0:
            return np.zeros(len(self.tp), bool)
        d, _ = T.nearest(self.tp, Q)
        return (d <= dsel) & ~self.tp_sky

    def hausdorff(self, sel):
        """番号23 の labelled_hausdorff と同じ式（描画→真値の最近点をキャッシュ）。"""
        Tp = self.tp[sel]
        out = {"n_truth": int(len(Tp)), "n_render_assigned": 0}
        if len(Tp) == 0:
            out["error"] = "真値点なし"
            return out, None
        if len(self.rp) == 0:
            out.update(max_px=float("inf"), error="描画側の境界なし")
            return out, None
        d_tr, _ = T.nearest(Tp, self.rp)
        assigned = sel[self.i_rt] & ~self.rp_sky
        d_rt = self.d_rt[assigned]
        both = np.concatenate([d_tr, d_rt])
        worst = Tp[int(np.argmax(d_tr))]
        if len(d_rt) and d_rt.max() > d_tr.max():
            worst = self.rp[assigned][int(np.argmax(d_rt))]
        out.update(n_render_assigned=int(assigned.sum()), max_px=round(float(both.max()), 3), p95_px=round(float(np.percentile(both, 95)), 3),
                   p50_px=round(float(np.percentile(both, 50)), 3), max_truth_to_render=round(float(d_tr.max()), 3),
                   max_render_to_truth=round(float(d_rt.max()), 3) if len(d_rt) else None, worst_display_xy=r3(worst))
        return out, assigned


# ================================================================= 77：下側の帯状の範囲の中の縞（真値と描画に同じ手順）
def strip_mask(run, inside, strip):
    m = np.zeros((H, W), np.uint8)
    cv2.polylines(m, [np.round(np.asarray(run) * 8).astype(np.int32)], False, 1, 1, cv2.LINE_8, shift=3)
    d = dist_to(m > 0)
    return (d >= strip[0]) & (d <= strip[1]) & inside


def strip_components(lab, strip, run, cls, min_area):
    """帯状の範囲の中の色区 cls の連結成分と、下側の折れ線に沿った弧長の範囲 [s_from, s_to]（1 px おきの点の番号）。"""
    Pr = T.resample_polyline(np.asarray(run, np.float64), 1.0)
    m = (strip & (lab == cls)).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for c in range(1, n):
        if st[c, cv2.CC_STAT_AREA] < min_area:
            continue
        ys, xs = np.nonzero(cc == c)
        _, idx = T.nearest(np.stack([xs, ys], 1).astype(np.float64), Pr)
        out.append({"s_from": int(idx.min()), "s_to": int(idx.max()), "area": int(st[c, cv2.CC_STAT_AREA])})
    return sorted(out, key=lambda r: (r["s_from"], r["s_to"]))


def match_components(ct_, cr_, min_overlap=0.5):
    """真値と描画の成分を、下側に沿った弧長の範囲の重なり（短い方の長さの min_overlap 以上）で順に 1 対 1 に対応させる。
    位置の精度は境界の距離（lower_ends）で別に判定する。"""
    used = set()
    pairs, miss = [], []
    for a in ct_:
        best = None
        for j, b in enumerate(cr_):
            if j in used:
                continue
            ov = min(a["s_to"], b["s_to"]) - max(a["s_from"], b["s_from"]) + 1
            short = min(a["s_to"] - a["s_from"], b["s_to"] - b["s_from"]) + 1
            f = ov / max(short, 1)
            if f >= min_overlap and (best is None or f > best[1]):
                best = (j, f)
        if best is not None:
            used.add(best[0])
            b = cr_[best[0]]
            pairs.append((a, b, max(abs(a["s_from"] - b["s_from"]), abs(a["s_to"] - b["s_to"]))))
        else:
            miss.append(a)
    extra = [b for j, b in enumerate(cr_) if j not in used]
    order_ok = all(pairs[i][1]["s_from"] <= pairs[i + 1][1]["s_from"] for i in range(len(pairs) - 1))
    return pairs, miss, extra, order_ok


# ================================================================= 77：下側に沿った並び（記録。表示 px。真値と描画に同じ手順）
def lower_sequence(lab, run, strip, min_run=6):
    P = T.resample_polyline(np.asarray(run, np.float64), 1.0)
    tan = np.gradient(P, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1)
    # 内向き（主浪の色区の側）を決める：両側 6 px の色区の数
    def cls_at(Q):
        q = np.clip(np.round(Q).astype(int), 0, [W - 1, H - 1])
        return lab[q[:, 1], q[:, 0]]
    inside = np.isin(cls_at(P + 6 * nrm), [1, 2, 3, 4]).sum() >= np.isin(cls_at(P - 6 * nrm), [1, 2, 3, 4]).sum()
    if not inside:
        nrm = -nrm
    kinds = []
    for i in range(len(P)):
        ds = np.arange(strip[0], strip[1] + 1e-9, 1.0)
        c = cls_at(P[i][None] + ds[:, None] * nrm[i][None])
        nb = int((c == 3).sum()); nd = int((c == 4).sum()); nf = int(np.isin(c, [1, 2]).sum())
        if nb + nd + nf == 0:
            kinds.append("none")
        else:
            kinds.append(["band", "dark", "foam"][int(np.argmax([nb, nd, nf]))])
    # 連長（短い区間は前の区間へ吸収）
    runs = []
    for i, k in enumerate(kinds):
        if runs and runs[-1][0] == k:
            runs[-1][2] = i
        else:
            runs.append([k, i, i])
    changed = True
    while changed:
        changed = False
        for j in range(len(runs)):
            if runs[j][2] - runs[j][1] + 1 < min_run and len(runs) > 1:
                t = j - 1 if j > 0 else j + 1
                runs[t][1] = min(runs[t][1], runs[j][1]); runs[t][2] = max(runs[t][2], runs[j][2])
                del runs[j]
                changed = True
                break
        m = []
        for r_ in runs:
            if m and m[-1][0] == r_[0]:
                m[-1][2] = r_[2]
            else:
                m.append(r_)
        runs = m
    seq = [{"kind": k, "s_from": a, "s_to": b} for k, a, b in runs]
    n_band = sum(1 for s in seq if s["kind"] == "band")
    n_dark_between = sum(1 for j, s in enumerate(seq) if s["kind"] == "dark" and 0 < j < len(seq) - 1)
    return seq, n_band, n_dark_between, P, nrm


def compare_sequences(st, sr):
    ks_t = [s["kind"] for s in st]
    ks_r = [s["kind"] for s in sr]
    same = ks_t == ks_r
    dmax = None
    if same:
        dmax = max(max(abs(a["s_from"] - b["s_from"]), abs(a["s_to"] - b["s_to"])) for a, b in zip(st[1:], sr[1:])) if len(st) > 1 else 0.0
    return same, dmax


# ================================================================= 134：白い帯の幅（真値と描画に同じ手順）
def band_widths(lab, seg132, stop_sky, big_min_area, step=2.0, maxd=320.0):
    P = T.resample_polyline(np.asarray(seg132, np.float64), step)
    blue = np.isin(lab, [3, 4]).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(blue, 8)
    big = np.zeros(n, bool)
    big[1:] = st[1:, cv2.CC_STAT_AREA] >= big_min_area
    bigm = big[cc]
    tan = np.gradient(P, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1)
    q = np.clip(np.round(P + 8 * nrm).astype(int), 0, [W - 1, H - 1])
    if (lab[q[:, 1], q[:, 0]] == 9).mean() > 0.5:
        nrm = -nrm
    wid = []
    for i in range(len(P)):
        entered = False
        wv = maxd
        for d in np.arange(0.0, maxd, 0.5):
            x, y = P[i] + d * nrm[i]
            xi, yi = int(round(x)), int(round(y))
            if not (0 <= xi < W and 0 <= yi < H):
                wv = d; break
            if not entered:
                if lab[yi, xi] != 9:
                    entered = True
                continue
            if bigm[yi, xi] or stop_sky[yi, xi]:
                wv = d; break
        wid.append(wv)
    wid = np.array(wid)
    k = 31
    sm = np.convolve(np.pad(wid, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    n_ = len(sm)
    a, b = n_ // 3, 2 * n_ // 3
    i1 = int(np.argmin(sm[:a])); i2 = a + int(np.argmax(sm[a:b])) if b > a else a; i3 = b + int(np.argmin(sm[b:]))
    order = [{"kind": "narrow", "i": i1, "arc_fraction": round(i1 / max(n_ - 1, 1), 3), "at": r3(P[i1]), "width": round(float(sm[i1]), 2)},
             {"kind": "wide", "i": i2, "arc_fraction": round(i2 / max(n_ - 1, 1), 3), "at": r3(P[i2]), "width": round(float(sm[i2]), 2)},
             {"kind": "narrow", "i": i3, "arc_fraction": round(i3 / max(n_ - 1, 1), 3), "at": r3(P[i3]), "width": round(float(sm[i3]), 2)}]
    ok = sm[i1] < sm[i2] and sm[i3] < sm[i2]
    return wid, sm, order, ok, P


# ================================================================= 色の統計
def lab_img(path):
    return T.srgb8_to_lab(T.imread_rgb(path))


def region_stats(lab, mask, target_lab):
    v = lab[mask]
    if len(v) < 20:
        return None
    med = np.median(v, 0)
    de_med = T.ciede2000(v, np.broadcast_to(med, v.shape))
    de_tgt = T.ciede2000(med, np.asarray(target_lab, np.float64))
    dev = np.zeros(mask.shape, np.uint8)
    dev[mask] = (de_med > 1.0).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(dev, 8)
    bands = int((st[1:, cv2.CC_STAT_AREA] >= 20).sum()) if n > 1 else 0
    return {"n_px": int(len(v)), "lab_median": r3(med), "dE00_median_to_palette": round(float(de_tgt), 3),
            "dE00_to_median_std": round(float(np.std(de_med)), 4), "dE00_to_median_p99": round(float(np.percentile(de_med, 99)), 4),
            "dE00_to_median_max": round(float(de_med.max()), 3), "n_px_dev_gt_1": int((de_med > 1.0).sum()), "bands_ge_20px": bands}


# ================================================================= 図
def quant_save(path, img, reserved=((0, 255, 255), (60, 230, 60), (255, 220, 0), (255, 40, 40), (255, 255, 255), (0, 0, 0))):
    T.save_png_reserved(path, img, list(reserved))


def dimmed(img, f=0.45):
    o = (img.astype(np.float32) * f).astype(np.uint8)
    o[:, :157] //= 4
    o[:, 1763:] //= 4
    return o


def put(img, items, size=18):
    return CT._pil_text(img, items, size)


def main():
    t0 = time.time()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    P = jl(os.path.join(REPO, PARAMS_REL))
    E = P["eval"]
    ct = jl(os.path.join(REPO, CT_REL))
    poly = jl(os.path.join(REPO, POLY_REL))
    ann = jl(os.path.join(REPO, ANN_REL))
    spec = T.load_spec()
    sigma = float(spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
    build = os.path.join(REPO, BUILD_REL)
    evid = os.path.join(REPO, EVID_REL)
    os.makedirs(evid, exist_ok=True)
    stage = os.path.join(REPO, STAGE_REL)
    z, fr, cov_t, lab_t = truth_maps(stage)
    regs = list(z["regs"])
    comp_id = z["comp_id"]
    lab_of = {r["id"]: i + 1 for i, r in enumerate(regs)}
    feats = poly["features"]
    painting_disp = CT.Frame(fr.W, fr.H).disp_image(T.imread_rgb(T.repo_abs(spec["reference"]["path"])))
    disp_lab_paint = T.srgb8_to_lab(painting_disp)
    pal = jl(os.path.join(build, "bake_input", "af28_bake_input_record.json"))["palette"]
    render_rep = jl(os.path.join(build, "af28_render_report.json"))
    keys = P["keys"]
    pk = P["preferred_key"]

    # ---- 項目の対象（真値の折れ線）
    bad_nb = {"sky", "outside", "99", "-1"}
    def fl(kind, item=None, cond=lambda f: True):
        return [f["points_display"] for f in feats if f["kind"] == kind and (item is None or item in f.get("items", [])) and cond(f)]
    white_items = {it: fl("white_part", it, lambda f: str(f.get("neighbour")) not in bad_nb) for it in (79, 133, 134)}
    inner_lines = fl("inner_face_boundary", None, lambda f: str(f.get("neighbour")) not in bad_nb)
    main_bands = sorted({b for m in ct["stripes"]["main_stripes_118"] for b in m["bands"]})
    lines118 = fl("stripe_edge", None, lambda f: f.get("stripe") in main_bands)
    lower_run = np.asarray(ct["stripes"]["lower_side"]["run_display"], np.float64)
    sl_edges = fl("stripe_edge", None, lambda f: str(f.get("stripe", "")).startswith("SL"))
    lines120 = fl("boundary_120")
    lines270 = fl("boundary_270_ai_mid")
    lines270m = fl("boundary_270_mizuiro")
    r175 = [r for r in poly["regions"] if r.get("in_white_range_175")]
    lower_end = np.asarray(ct["inner_face"]["lower_end_display"], np.float64)
    upper_end = np.asarray(ct["inner_face"]["upper_end_display"], np.float64)
    a001 = fr.hi_to_disp_cov(comp_id == lab_of["A001"]) >= 0.5
    w001 = fr.hi_to_disp_cov(comp_id == lab_of["W001"]) >= 0.5
    zone_mask = {}
    for zk in ("79", "133"):
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, [np.round(np.array(ann["white_item_zones_display"][zk]["points"]) * 8).astype(np.int32)], 1, shift=3)
        zone_mask[zk] = m > 0
    env = jl(os.path.join(REPO, ENV_REL))
    seg = {s["id"]: np.asarray(s["points_display"], np.float64) for s in env["segments"]}
    env_sky = T.load_cov_png(os.path.join(REPO, SKY_ENV_REL)) >= 0.5

    per_key = {}
    detail_pk = None
    for key in keys:
        rdir = os.path.join(build, "render", key)
        ids_path = os.path.join(rdir, "28_%s_class_ids.png" % key)
        ids, cov_raw, cov_r, lab_r, unknown = render_maps(ids_path, cov_t)
        dsky_t = dist_to(cov_t["sky"] >= 0.5)
        dsky_r = dist_to(cov_r["sky"] >= 0.5)
        CB = {k: ClassBoundary(k, cov_t, cov_r, sigma, dsky_t, dsky_r, E["silhouette_exclude_px"]) for k in CLASSES}
        items = {}
        assigned_viz = []

        def judge(name, k, lines, extra_sel=None):
            sel = CB[k].select(lines, E["item_select_px"])
            if extra_sel is not None:
                sel &= extra_sel(CB[k].tp)
            res, asg = CB[k].hausdorff(sel)
            res["class"] = k
            res["verdict_boundary"] = "pass" if res.get("max_px", np.inf) <= PASS_PX else "fail"
            assigned_viz.append((k, sel, asg, name))
            return res

        # 79・133・134（白の内側の境界）
        items["79"] = {"boundary": judge("79", "white", white_items[79])}
        items["133"] = {"boundary": judge("133", "white", white_items[133])}
        # 133 の連続：描画の白の連結成分のうち、W001 の左側（79 の区域）と上側（133 の区域）の両方を 50% 以上覆うもの
        wm = (lab_r == 1).astype(np.uint8)
        n, cc, st, _ = cv2.connectedComponentsWithStats(wm, 8)
        L = w001 & zone_mask["79"]; U = w001 & zone_mask["133"]
        best = None
        for c in range(1, n):
            fl_ = float((cc[L] == c).mean()) if L.any() else 0.0
            fu_ = float((cc[U] == c).mean()) if U.any() else 0.0
            if best is None or min(fl_, fu_) > min(best[1], best[2]):
                best = (c, fl_, fu_)
        items["133"]["continuity"] = {"left_cover": round(best[1], 4), "upper_cover": round(best[2], 4),
                                      "pass": bool(best[1] >= 0.5 and best[2] >= 0.5),
                                      "ja": "描画の白の連結成分（8 近傍）のうち最も両方を覆うものが、W001 の左側（79 の区域）と上側（133 の区域）の画素をそれぞれ何割覆うか"}
        items["134"] = {"boundary": judge("134", "white", white_items[134])}
        wt, smt, ordt, okt, P132 = band_widths(lab_t, seg["132"], env_sky, E["band_blue_min_area_display_px2"])
        wr, smr, ordr, okr, _ = band_widths(lab_r, seg["132"], lab_r == 9, E["band_blue_min_area_display_px2"])
        dfrac = max(abs(a["arc_fraction"] - b["arc_fraction"]) for a, b in zip(ordt, ordr))
        corr = float(np.corrcoef(smt, smr)[0, 1]) if np.std(smt) > 0 and np.std(smr) > 0 else None
        items["134"]["width_order"] = {"truth": ordt, "render": ordr, "truth_order_ok": bool(okt), "render_order_ok": bool(okr),
                                       "max_arc_fraction_shift": round(dfrac, 3), "median_abs_width_diff_px": round(float(np.median(np.abs(smt - smr))), 2),
                                       "corr_smoothed": r3(corr), "pass": bool(okt and okr and dfrac <= 0.1),
                                       "partA_order": ct["white"]["band_134"]["wide_narrow_order_from_crest"],
                                       "ja": "132（包絡版）の外輪郭から内向きに、藍の胴（面積 ≥1500 表示 px² の藍中・藍濃）か唇の下の空に当たるまでの幅（2 px おき、31 点の移動平均）。真値と描画に同じ手順を使い、狭→広→狭の順と位置（弧長の割合の差 ≤0.1）を比べる"}
        # 73・263・120（内側の藍中の帯）
        items["73"] = {"boundary": judge("73", "ai_mid", inner_lines)}
        lower_zone = lambda tp: tp[:, 1] >= lower_end[1] - 60
        items["263"] = {"boundary_lower": judge("263", "ai_mid", inner_lines, lower_zone)}
        am = (lab_r == 3).astype(np.uint8)
        n, cc, st, _ = cv2.connectedComponentsWithStats(am, 8)
        cov_a = [(c, float((cc[a001] == c).mean())) for c in range(1, n)]
        cbest = max(cov_a, key=lambda x: x[1]) if cov_a else (0, 0.0)
        ys, xs = np.nonzero(cc == cbest[0])
        if len(ys):
            pts = np.stack([xs, ys], 1).astype(np.float64)
            low = pts[np.argmax(pts[:, 1])]
            d_low = float(np.linalg.norm(pts - lower_end, axis=1).min())
            d_up = float(np.linalg.norm(pts - upper_end, axis=1).min())
        else:
            low, d_low, d_up = None, np.inf, np.inf
        items["263"]["continuity"] = {"component_cover_of_A001": round(cbest[1], 4), "render_lowest_point": r3(low),
                                      "dist_truth_lower_end_px": round(d_low, 3), "dist_truth_upper_end_px": round(d_up, 3),
                                      "pass": bool(cbest[1] >= 0.9 and d_low <= PASS_PX and d_up <= PASS_PX),
                                      "ja": "描画の藍中の連結成分のうち内側の帯 A001 を最も覆うもの（覆う割合 ≥0.9）が、真値の上端（唇の下）と下端（前景の小波の縁）の両方から 4 px 以内に届くか"}
        items["120"] = {"boundary": judge("120", "ai_mid", lines120)}
        # 118（主要な縞の両側の境界）
        items["118"] = {"boundary": judge("118", "ai_mid", lines118), "main_stripes": [m["id"] + ":" + "+".join(m["bands"]) for m in ct["stripes"]["main_stripes_118"]]}
        # 77（下側から始まる帯の下端と、下側に沿った並び）
        near_lower = lambda tp: T.nearest(tp, T.resample_polyline(lower_run, 0.5))[0] <= E["lower_end_zone_px"]
        items["77"] = {"lower_ends": judge("77", "ai_mid", sl_edges, near_lower)}
        seq_t, nb_t, nd_t, Ps, Ns = lower_sequence(lab_t, lower_run, E["lower_side_strip_px"])
        seq_r, nb_r, nd_r, _, _ = lower_sequence(lab_r, lower_run, E["lower_side_strip_px"])
        same, dmax = compare_sequences(seq_t, seq_r)
        strip = strip_mask(lower_run, np.isin(lab_t, [1, 2, 3, 4]), E["lower_side_strip_px"])
        strip &= (dsky_t > E["silhouette_exclude_px"]) & (dsky_r > E["silhouette_exclude_px"])
        comp77 = {}
        ok77 = True
        for nm, cl in (("band_ai_mid", 3), ("dark_ai_dark", 4)):
            ct_ = strip_components(lab_t, strip, lower_run, cl, E["strip_min_area_px"])
            cr_ = strip_components(lab_r, strip, lower_run, cl, E["strip_min_area_px"])
            pairs, miss, extra, order_ok = match_components(ct_, cr_)
            comp77[nm] = {"truth_n": len(ct_), "render_n": len(cr_), "matched": len(pairs), "order_preserved": bool(order_ok),
                          "missing_in_render": miss, "extra_in_render": extra,
                          "max_end_shift_along_side_px": max([p_[2] for p_ in pairs]) if pairs else None,
                          "truth_s_ranges": [[a["s_from"], a["s_to"]] for a in ct_]}
            if cl == 3:
                ok77 &= (len(miss) == 0 and len(extra) == 0 and order_ok)
        items["77"]["strip_components"] = {**comp77, "pass": bool(ok77),
                                           "ja": "下側（第A部の lower_side の折れ線）から内側 3〜12 px の帯状の範囲（真値・描画の空から 2 px 以内を除く）で、藍中（下側から始まる帯）と藍濃（その間の縞）の連結成分（面積 ≥%d px²）を真値と描画で求め、下側に沿った弧長の範囲の重なりで順に 1 対 1 に対応させた。判定は藍中の帯の本数と並び順（過不足 0、順序が同じ）。藍濃は記録。位置の精度は lower_ends（境界 ≤4 px）で判定する" % int(E["strip_min_area_px"])}
        items["77"]["sequence_record"] = {"truth_n_band_runs": nb_t, "truth_n_dark_between": nd_t, "render_n_band_runs": nb_r, "render_n_dark_between": nd_r,
                                   "same_kinds_in_order": bool(same), "max_run_edge_shift_px": dmax,
                                   "truth_kinds": "".join({"band": "B", "dark": "D", "foam": "F", "none": "-"}[s["kind"]] for s in seq_t),
                                   "render_kinds": "".join({"band": "B", "dark": "D", "foam": "F", "none": "-"}[s["kind"]] for s in seq_r),
                                   "partA_counts": {"n_lower_side_bands": ct["log"]["stripes"]["n_lower_side_bands"],
                                                    "n_dark_stripes_lower_side": ct["log"]["stripes"]["n_dark_stripes_lower_side"]},
                                   "same_within_4px": bool(same and dmax is not None and dmax <= PASS_PX),
                                   "ja": "記録のみ：下側に沿って 1 px おきに、内側 3〜12 px の画素の多数決（B 藍中の帯、D 藍濃、F 泡＝白・淡い水色）をとり、6 px 未満の区間を前へ吸収した並び。多数決が拮抗する所では 1 画素の差で種類が入れ替わるので、判定には上の strip_components を使う"}
        # 270（白と藍中の境。別案の白と淡い水色の境は記録）
        items["270"] = {"boundary": judge("270", "white", lines270)}
        items["270"]["record_mizuiro_reading"] = judge("270m", "white", lines270m)
        items["270"]["order_ja"] = "境界の全点が 4 px 以内なら、振れ幅が 4 px を超える曲がりの順序は保たれる（曲がりの順序は境界の距離で代える）"
        # 175（白い範囲の中の色区が全部残るか、その境界）
        ret = []
        by_cls = {k: [] for k in ("mizuiro", "ai_mid", "ai_dark")}
        for r in r175:
            m = np.zeros((H, W), np.uint8)
            for ring in r["rings"]:
                pts = np.round(np.asarray(ring["points_display"]) * 8).astype(np.int32)
                cv2.fillPoly(m, [pts], 0 if ring["hole"] else 1, shift=3)
            q = m > 0
            if not q.any():
                c = np.round(np.asarray(r["centroid_display"])).astype(int)
                q[c[1], c[0]] = True
            frac = float((lab_r[q] == CLS_VAL[r["class"]]).mean())
            qi = q & (dsky_t > E["silhouette_exclude_px"])
            frac_i = float((lab_r[qi] == CLS_VAL[r["class"]]).mean()) if qi.any() else None
            same_i = int((lab_r[qi] == CLS_VAL[r["class"]]).sum())
            ret.append((r["id"], r["class"], frac, float(r["area_display_px2"]), frac_i, int(q.sum()), int(qi.sum()),
                        r3(r["centroid_display"]), round(float(dsky_t[q].min()), 2), same_i))
            by_cls[r["class"]] += [ring["points_display"] for ring in r["rings"]]
        kept = [x for x in ret if x[2] >= E["retain_min_fraction"]]
        lost = [x for x in ret if x[2] < E["retain_min_fraction"]]
        # 残る＝真値の空から 2 px より内側の多角形の画素のうち、描画が同じ色区の画素が 3 px 以上ある（形は境界 ≤4 px で別に判定）
        kept_i = [x for x in ret if x[6] == 0 or x[9] >= E["retain_min_px"]]
        lost_i = [x for x in ret if x[6] > 0 and x[9] < E["retain_min_px"]]
        b175 = {k: judge("175_" + k, k, by_cls[k]) for k in by_cls if by_cls[k]}
        mx175 = max(v.get("max_px", 0) for v in b175.values())
        lost_ids = {x[0] for x in ret if x[6] > 0 and x[9] < E["retain_min_px"]} | {x[0] for x in ret if x[6] == 0 and x[9] == 0 and x[2] == 0}
        by_cls_x = {k: [] for k in by_cls}
        for r in r175:
            if r["id"] not in lost_ids:
                by_cls_x[r["class"]] += [ring["points_display"] for ring in r["rings"]]
        b175x = {k: CB[k].hausdorff(CB[k].select(by_cls_x[k], E["item_select_px"]))[0] for k in by_cls_x if by_cls_x[k]}
        def lost_rec(xs):
            return [{"id": x[0], "class": x[1], "fraction_all": round(x[2], 3), "fraction_interior": None if x[4] is None else round(x[4], 3),
                     "same_class_px_interior": x[9], "area_display_px2": x[3], "n_px": x[5], "n_px_interior": x[6], "centroid_display": x[7],
                     "min_dist_to_truth_sky_px": x[8]} for x in xs]
        items["175"] = {"regions_total": len(ret), "regions_retained": len(kept_i), "regions_retained_all_pixels": len(kept),
                        "lost": lost_rec(lost_i), "lost_all_pixels_rule": lost_rec(lost),
                        "retain_rule_ja": "色区の多角形（第A部）の画素のうち、真値の空から 2 px より内側の画素に、描画の同じ色区の画素が 3 px 以上あれば『残る』とする（形は境界 ≤4 px で判定。空との境の 2 px は輪郭の項目の対象）。全画素に対する割合 ≥0.5 で数えた値も記録（regions_retained_all_pixels）",
                        "boundary_by_class": b175, "boundary_max_px": round(mx175, 3),
                        "record_excluding_lost_regions": {"excluded": sorted(lost_ids), "boundary_by_class": b175x,
                                                          "boundary_max_px": round(max(v.get("max_px", 0) for v in b175x.values()), 3),
                                                          "ja": "記録のみ：残らなかった色区（輪郭に接する）を除いた境界"},
                        "verdict_boundary": "pass" if mx175 <= PASS_PX else "fail"}
        per_key[key] = {"ids": rel(ids_path), "ids_sha256": sha256(ids_path), "unknown_id_px": unknown, "items": items}
        if key == pk:
            detail_pk = (CB, assigned_viz, cov_r, lab_r, seq_t, seq_r, Ps, Ns, (wt, smt, ordt, wr, smr, ordr, P132))

    # ---- 項目ごとの判定（45°）
    it = per_key[pk]["items"]
    verdict = {}
    def v_of(ok):
        return "pass" if ok else "fail"
    verdict["73"] = v_of(it["73"]["boundary"]["verdict_boundary"] == "pass")
    verdict["77"] = v_of(it["77"]["lower_ends"]["verdict_boundary"] == "pass" and it["77"]["strip_components"]["pass"])
    verdict["79"] = v_of(it["79"]["boundary"]["verdict_boundary"] == "pass")
    verdict["118"] = v_of(it["118"]["boundary"]["verdict_boundary"] == "pass")
    verdict["120"] = v_of(it["120"]["boundary"]["verdict_boundary"] == "pass")
    verdict["133"] = v_of(it["133"]["boundary"]["verdict_boundary"] == "pass" and it["133"]["continuity"]["pass"])
    verdict["134"] = v_of(it["134"]["boundary"]["verdict_boundary"] == "pass" and it["134"]["width_order"]["pass"])
    verdict["175"] = v_of(it["175"]["verdict_boundary"] == "pass" and it["175"]["regions_retained"] == it["175"]["regions_total"])
    verdict["263"] = v_of(it["263"]["boundary_lower"]["verdict_boundary"] == "pass" and it["263"]["continuity"]["pass"])
    verdict["270"] = v_of(it["270"]["boundary"]["verdict_boundary"] == "pass")

    # ---- 265・266・267（色）
    rdir = os.path.join(build, "render", pk)
    lab_pk = lab_img(os.path.join(rdir, "28_%s_painting_kstar.png" % pk))
    lab_bk = lab_img(os.path.join(rdir, "28_%s_boat_kstar.png" % pk))
    ids_b = T.imread_rgb(os.path.join(rdir, "28_%s_boat_class_ids.png" % pk))
    er = int(E["colour_erode_px"])
    target265 = np.asarray(ct["item_targets"]["265"]["lab"], np.float64)
    m265 = cv2.erode(a001.astype(np.uint8), CT.disk(er)) > 0
    med265 = np.median(lab_pk[m265], 0)
    de265 = float(T.ciede2000(med265, target265))
    col = {"265": {"target_lab_inner_face": r3(target265), "render_lab_median": r3(med265), "n_px": int(m265.sum()), "dE00": round(de265, 3),
                   "verdict": v_of(de265 <= 5.0), "ja": "内側の帯 A001 を 3 px 縮めた範囲で、主役波だけの原画視点の描画の Lab 中央値と、原画の内側の帯の中央値（第A部）の ΔE00"}}
    views = {}
    for k in CLASSES:
        mt = cv2.erode(((lab_t == CLS_VAL[k])).astype(np.uint8), CT.disk(er)) > 0
        mb = cv2.erode(np.all(ids_b == np.array(ID_RGB[k], np.uint8), -1).astype(np.uint8), CT.disk(er)) > 0
        sp = region_stats(lab_pk, mt, pal[k]["lab"])
        sb = region_stats(lab_bk, mb, pal[k]["lab"])
        cross = round(float(T.ciede2000(np.asarray(sp["lab_median"]), np.asarray(sb["lab_median"]))), 3) if sp and sb else None
        views[k] = {"painting_view": sp, "boat_view": sb, "dE00_boat_vs_painting_median": cross}
    def flat_ok(k):
        v = views[k]
        return (v["painting_view"] and v["boat_view"] and v["painting_view"]["dE00_to_median_std"] < 1.0 and v["boat_view"]["dE00_to_median_std"] < 1.0
                and v["painting_view"]["bands_ge_20px"] == 0 and v["boat_view"]["bands_ge_20px"] == 0 and v["dE00_boat_vs_painting_median"] <= 5.0)
    col["266"] = {"class_default": "ai_mid", "views": {"ai_mid": views["ai_mid"], "mizuiro_record": views["mizuiro"]}, "verdict": v_of(flat_ok("ai_mid")),
                  "ja": "『水色』は第A部の既定（藍中、既定値・利用者未回答）。原画視点（真値の色区を 3 px 縮めた範囲）と船上座席（描画の色区 ID を 3 px 縮めた範囲）で、各画素の色と範囲の中央値の ΔE00 の標準偏差 <1、1 ΔE00 を超える画素が 20 px 以上まとまった帯 0、2 視点の中央値の差 ≤5。淡い水色は記録"}
    col["267"] = {"class": "white", "views": {"white": views["white"]}, "verdict": v_of(flat_ok("white")),
                  "ja": "白について 266 と同じ手順（原画にない灰色の帯＝1 ΔE00 を超える 20 px 以上のまとまり 0）"}
    col["palette_all_classes_record"] = views

    # ---- 空のテクセル（ベイクの集計）
    bake = {k: jl(os.path.join(build, "bake", "af28_bake_%s.json" % k)) for k in keys}
    empty = {k: {"emptyAfterFill": bake[k]["emptyAfterFill"], "notRasterised": bake[k]["notRasterised"], "noPositiveClass": bake[k]["noPositiveClass"]} for k in keys}
    verdict_empty = v_of(all(e["emptyAfterFill"] == 0 and e["notRasterised"] == 0 for e in empty.values()))

    # ---- 142・143（外殻線の位置の事前検査、記録のみ）
    line = line_precheck(os.path.join(rdir, "28_%s_line_ids.png" % pk), seg, cov_t)

    # ---- 輪郭の照合（番号23 の評価器を ID モードで。番号26 の値の再現の確認、記録のみ）
    sil = {}
    for key in keys:
        sil[key] = run_evaluator(os.path.join(build, "render", key), key, "class_ids")
    sil_line = run_evaluator(os.path.join(build, "render", pk), pk, "line_ids")

    # ---- 図
    figs = make_figures(evid, build, pk, keys, painting_disp, detail_pk, per_key, verdict, col, line, lab_t, ct)

    # ---- metrics.json
    status = gate_status_safe()
    items_out = {}
    names = {"73": "内側の水色（藍中）の色区の境界", "77": "下側から始まる縞の本数・並び順と下側端", "79": "左側の白の境界", "118": "主要な縞の両側の境界",
             "120": "唇の白と内側の水色の境", "133": "左側から上側へ続く白と上側の境界", "134": "白帯の両側の境界と幅の広狭", "175": "白の中の藍・水色の色区が全部残る",
             "263": "内側から下方へ続く水色", "270": "白と水色の境"}
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        items_out[k_] = {"name_ja": names[k_], "criterion": "境界 ≤4 px（表示 px、最大）" + ("＋並び" if k_ == "77" else "＋連続" if k_ in ("133", "263") else "＋広狭の順" if k_ == "134" else "＋全部残る" if k_ == "175" else ""),
                         "value": it[k_], "verdict": verdict[k_]}
    items_out["265"] = {"name_ja": "内側の水色の表示色", "criterion": "ΔE00 ≤5（領域の中央値）", "value": col["265"], "verdict": col["265"]["verdict"]}
    items_out["266"] = {"name_ja": "水色の平塗り（照明の帯 0）", "criterion": "領域内の ΔE00 の標準偏差 <1、帯 0、2 視点の差 ≤5", "value": col["266"], "verdict": col["266"]["verdict"]}
    items_out["267"] = {"name_ja": "白の平塗り（灰色の帯 0）", "criterion": "同上", "value": col["267"], "verdict": col["267"]["verdict"]}
    items_out["uv_no_empty_texels"] = {"name_ja": "UV テクスチャに空のテクセルがない", "criterion": "外挿の後に未設定 0、UV で描かれないテクセル 0", "value": empty, "verdict": verdict_empty}
    items_out["142"] = {"name_ja": "左側の外周線（事前検査）", "criterion": "記録のみ（正式な判定は番号36）", "value": line["142"], "verdict": "record-only"}
    items_out["143"] = {"name_ja": "上側から船側の端までの外周線（事前検査）", "criterion": "記録のみ（正式な判定は番号36）", "value": line["143"], "verdict": "record-only"}
    items_out["178"] = {"name_ja": "縞の枝分かれ", "criterion": "計画の損切りどおり記録のみ（延期）", "value": {"partA_branch_candidates": len(ct["stripes"]["branches_178"])}, "verdict": "record-only"}
    others = {k: {kk: {"boundary_max_px": item_max(vv), "boundary_verdict": "pass" if item_max(vv) <= PASS_PX else "fail"}
                   for kk, vv in per_key[k]["items"].items()} for k in keys if k != pk}
    M = {
        "schema": "GreatWave.AF28.metrics/1", "number": "28", "part": "B",
        "t_star_s": spec["timeline"]["t_star_s"], "camera": spec["painting_cam"]["id"], "frame": [W, H],
        "preferred_key": pk, "preferred_ja": P["preferred_ja"],
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC のオフスクリーン描画（RTX 3080、Direct3D11、Linear 色空間）と、その画像の numpy・OpenCV の測定。HMD 実機の結果ではない。",
        "evaluator": {"method_ja": __doc__.split("評価の約束：")[1].strip(), "truth": "番号28 第A部の色区の正解 v0（colour_truth.json）と番号23 の真値 v0.2",
                      "gate23": {"all_pass": status.get("all_pass"), "truth_unchanged_since_gate": status.get("truth_unchanged_since_gate")},
                      "provisional": not bool(status.get("all_pass")),
                      "structural_note_ja": "t* の原画視点の境界と色は、投影ベイクにより構造上ほぼ一致する（テクセルは自分の投影先の原画の値を持つ）。これは完成を意味しない。船上・側面・背面の見え方と、形成の途中の配色は別に確かめる（作業計画 31 の注意、R11）。"},
        "items": items_out,
        "record_other_interpretations": others,
        "silhouette_crosscheck_evaluator23": {"class_ids": sil, "with_outline_shell": sil_line,
                                               "ja": "番号23 の評価器（ID モード、包絡版）に、この番号の色区 ID 画像（空＝白）を通した値。主役波の形は番号26 の K* のままなので、78〜72 は番号26 と同じ値になるはず（確認用）。外殻線ありは、外周の外縁の位置（142・143 の参考）"},
        "bake": {k: {kk: bake[k][kk] for kk in ("direct", "innerDark", "uFill", "uFillBlue", "vFill", "sea", "leftoverU", "leftoverV", "leftoverDefault", "emptyAfterFill",
                                               "noPositiveClass", "onScreen", "visible", "classCountsDirect", "classCountsAll", "depthRowsFlipped", "uvRowsFlipped",
                                               "depthCheckMatchNormal", "depthCheckMatchFlipped", "outSdfSha256")} for k in keys},
        "palette_srgb8": {k: pal[k]["srgb8"] for k in CLASSES},
        "shader_v1": {
            "unlit_palette_linear_check": {k: {"painting_view_dE00_median_to_palette": (views[k]["painting_view"] or {}).get("dE00_median_to_palette"),
                                               "boat_view_dE00_median_to_palette": (views[k]["boat_view"] or {}).get("dE00_median_to_palette")} for k in CLASSES},
            "unlit_palette_ja": "調色板（第A部の色区の中央値の Lab）と、描画の色区の中央値の ΔE00。0.2 前後は Lab → 8bit sRGB の丸めの分（af28_bake_input_record.json の dE00_rounding と同じ）。Linear 色空間で Color を渡し、sRGB の描画先に書いた値が 8bit で一致したことを示す",
            "id_mode": {k: {"unknown_id_px": per_key[k]["unknown_id_px"]} for k in keys},
            "id_mode_ja": "ID 表示（大域 _AF28IdMode = 1）で描いた色区 ID 画像に、決めた 6 色以外の画素が何 px あったか（0 が期待値）",
            "spi_compile": spi_summary(os.path.join(build, "af28_spi_compile.json")),
            "aa_ja": "上位 2 つの色区の距離の差を fwidth で 1 画素幅に混ぜるアンチエイリアス。原画視点の色の画像（MSAA 8x）で使い、ID 画像では使わない",
        },
        "summary_verdicts": {**verdict, "265": col["265"]["verdict"], "266": col["266"]["verdict"], "267": col["267"]["verdict"], "uv_no_empty_texels": verdict_empty},
        "figures": figs,
    }
    T.save_json(os.path.join(evid, "metrics.json"), M)

    # ---- run.json
    ins = [PARAMS_REL, CT_REL, POLY_REL, ANN_REL, ENV_REL, SKY_ENV_REL, LW_REL, "Tools/PaintingTruth/painting_truth.json",
           "Tools/PaintingTruth/colour/af28_bake_input.py", "Tools/PaintingTruth/colour/af28_evaluate.py", "Tools/PaintingTruth/colour/run_af28.ps1",
           "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/evaluate.py",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF28ProjectionBaker.cs", "Unity/Assets/GreatWave/ArtFirst/Editor/AF28NprScene.cs",
           "Unity/Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_Bake.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader"]
    build_files = []
    for d, _, fs in os.walk(build):
        if os.sep + "partA" in d:
            continue
        for f_ in fs:
            build_files.append(os.path.join(d, f_))
    run = {
        "schema": "GreatWave.AF28.run/1", "number": "28", "part": "B", "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/PaintingTruth/colour/run_af28.ps1",
                     "py -3.10 Tools/PaintingTruth/colour/af28_bake_input.py",
                     "E:/6000.4.3f1/Editor/Unity.exe -batchmode -projectPath G:/Unity/GreatWave_2026_Fresh/Unity -executeMethod GreatWave.ArtFirst.EditorTools.AF28NprScene.BakeBuildAndRender -logFile Unity/Build/ArtFirst/28/unity_af28.log -quit",
                     "py -3.10 Tools/PaintingTruth/colour/af28_evaluate.py"],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": __import__("PIL").__version__, "unity": render_rep.get("unity"), "device": render_rep.get("device"),
                  "graphics_api": render_rep.get("graphicsApi"), "color_space": render_rep.get("colorSpace"), "os": platform.platform()},
        "unity_lock_ja": "Unity は Unity/Build/unity.lock を作ってから 1 プロセスだけ動かし、終わったら消した（run_af28.ps1）。",
        "inputs_sha256": {r_: sha256(os.path.join(REPO, r_)) for r_ in ins if os.path.exists(os.path.join(REPO, r_))},
        "stage_a_sha256": sha256(stage),
        "kstar_gwb_sha256": {k: bake[k]["gwbSha256"] for k in keys},
        "outputs_sha256": {rel(os.path.join(evid, f_)): sha256(os.path.join(evid, f_)) for f_ in sorted(os.listdir(evid))
                           if f_.startswith("28B_") or f_ == "metrics.json"},
        "not_committed_sha256": {rel(p_): sha256(p_) for p_ in sorted(build_files) if not p_.endswith(".log")},
        "not_committed_ja": "Unity/Build/ArtFirst/28/ は Git 対象外（/Unity/Build/）。焼いたテクスチャ（各 64 MB）・原画側の入力（80 MB）・描画・ID 画像・ベイクの集計。同じコマンドで作り直せる。",
        "elapsed_evaluate_s": round(time.time() - t0, 1),
        "bake_seconds": {k: round(float(bake[k]["secondsTotal"]), 2) for k in keys},
        "render_seconds": render_rep.get("totalSeconds"),
    }
    T.save_json(os.path.join(evid, "run.json"), run)
    print("AF28_EVALUATE_DONE", {k: v for k, v in M["summary_verdicts"].items()}, round(time.time() - t0, 1), "s")
    return 0


def item_max(v):
    b = v.get("boundary") or v.get("boundary_lower") or v.get("lower_ends")
    return float(b["max_px"]) if b and "max_px" in b else float(v.get("boundary_max_px", np.inf))


def spi_summary(path):
    if not os.path.exists(path):
        return {"error": "af28_spi_compile.json がない"}
    d = jl(path)
    return {"all_success": d.get("allSuccess"), "n_variants": len(d.get("items", [])),
            "failed": [x for x in d.get("items", []) if not x.get("success")], "keyword_sets": sorted({x["keywords"] for x in d.get("items", [])}),
            "note_ja": d.get("noteJa")}


def gate_status_safe():
    try:
        import evaluate as EV
        return EV.gate_status()
    except Exception as e:  # noqa: BLE001
        return {"all_pass": False, "error": str(e)}


def run_evaluator(rdir, key, kind):
    """番号23 の評価器（ID モード）に通す。idmap は空＝白（255,255,255）だけを渡す。"""
    out = os.path.join(rdir, "eval23_" + kind)
    os.makedirs(out, exist_ok=True)
    idm = os.path.join(out, "idmap_sky.json")
    T.save_json(idm, {"classes": {"sky": [255, 255, 255]}, "note_ja": "番号28 の ID 画像の空（白）だけ。船は描いていない。"})
    render = os.path.join(rdir, "28_%s_painting.png" % key)
    ids = os.path.join(rdir, "28_%s_%s.png" % (key, kind))
    cmd = [sys.executable, os.path.join(PT, "evaluate.py"), "--render", render, "--ids", ids, "--idmap", idm, "--out-dir", out, "--name", "af28_" + kind]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return {"error": r.stderr[-800:]}
    m = jl(os.path.join(out, "metrics.json"))
    out = {}
    for s_ in ("78", "130", "131", "132", "72", "71"):
        if s_ in m["items"]:
            ms = m["items"][s_].get("measures", [{}])[0]
            out[s_] = {"max_px": ms.get("value_max_px"), "p95_px": ms.get("p95_px"), "iou": ms.get("iou"), "verdict": m["items"][s_].get("verdict")}
    return out


def line_precheck(line_ids_path, seg, cov_t):
    """外殻線の ID 画像（3840×2160）から、外周（78・130・131・132）に沿った線の位置と幅を測る（記録のみ）。"""
    ids = T.imread_rgb(line_ids_path)
    f = ids.shape[0] // H
    line = np.all(ids == np.array(ID_RGB["line"], np.uint8), -1).astype(np.float64).reshape(H, f, W, f).mean((1, 3))
    sky = np.all(ids == np.array(ID_RGB["sky"], np.uint8), -1).astype(np.float64).reshape(H, f, W, f).mean((1, 3))
    lw = jl(os.path.join(REPO, LW_REL))
    s = 1080.0 / 2594.0
    wmed = {sg["id"]: float(np.nanmedian(np.where(np.asarray(sg["reason"]) == 0, np.asarray(sg["width_ref_px"], np.float64), np.nan))) * s for sg in lw["segments"]}
    out = {}
    for item, segs in (("142", ["78", "130"]), ("143", ["131", "132"])):
        dc, wr, present, outer = [], [], [], []
        for sid in segs:
            Pp = T.resample_polyline(seg[sid], 1.0)
            tan = np.gradient(Pp, axis=0)
            tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
            nrm = np.stack([-tan[:, 1], tan[:, 0]], 1)
            q = np.clip(np.round(Pp + 4 * nrm).astype(int), 0, [W - 1, H - 1])
            if (cov_t["sky"][q[:, 1], q[:, 0]] > 0.5).mean() > 0.5:
                nrm = -nrm   # 水側へ
            ds = np.arange(-8.0, 8.0001, 0.25)
            for p_, n_ in zip(Pp, nrm):
                Q = p_[None] + ds[:, None] * n_[None]
                x = np.clip(Q[:, 0], 0, W - 1.001); y = np.clip(Q[:, 1], 0, H - 1.001)
                x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
                def bil(img):
                    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
                lv = bil(line) >= 0.5
                sv = bil(sky) >= 0.5
                if lv.any():
                    idx = np.nonzero(lv)[0]
                    # 真値の外縁に最も近い線の塊
                    groups = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
                    g = min(groups, key=lambda g_: np.abs(ds[g_]).min())
                    a, b = ds[g[0]], ds[g[-1]]
                    centre = 0.5 * (a + b)
                    truth_centre = 0.5 * wmed[sid]
                    dc.append(abs(centre - truth_centre)); wr.append(b - a + 0.25); present.append(1)
                else:
                    present.append(0)
                # 描画の外縁（空の終わり）
                if sv.any() and (~sv).any():
                    first_non_sky = ds[np.argmax(~sv)] if sv[0] else None
                    if first_non_sky is not None:
                        outer.append(abs(first_non_sky))
        dc = np.asarray(dc); wr = np.asarray(wr)
        out[item] = {"segments": segs, "n_points": len(present), "line_present_fraction": round(float(np.mean(present)), 4),
                     "centre_offset_max_px": r3(dc.max()) if len(dc) else None, "centre_offset_p95_px": r3(np.percentile(dc, 95)) if len(dc) else None,
                     "render_line_width_median_px": r3(np.median(wr)) if len(wr) else None, "render_line_width_p10_p90_px": r3(np.percentile(wr, [10, 90])) if len(wr) else None,
                     "truth_line_width_median_px": {sid: round(wmed[sid], 3) for sid in segs},
                     "outer_edge_offset_p95_px": r3(np.percentile(outer, 95)) if outer else None,
                     "ja": "真値の外輪郭（線の外縁、包絡版）の点から水側への法線上（−8〜+8 px、0.25 px おき）で、外殻線の ID の塊の中心と幅を測った。真値の線の中心＝外縁から線幅（区間の中央値）の半分だけ水側。記録のみ"}
    return out


def make_figures(evid, build, pk, keys, paint, detail, per_key, verdict, col, line, lab_t, ct):
    CB, assigned_viz, cov_r, lab_r, seq_t, seq_r, Ps, Ns, bw = detail
    rdir = os.path.join(build, "render", pk)
    figs = []
    rgb = T.imread_rgb(os.path.join(rdir, "28_%s_painting.png" % pk))
    # 1 描画（そのまま）
    p = os.path.join(evid, "28B_%s_painting.png" % pk)
    cv2.imwrite(p, rgb[..., ::-1], [cv2.IMWRITE_PNG_COMPRESSION, 9])
    figs.append(rel(p))
    # 2 原画 50% 重ね
    ov = (0.5 * rgb.astype(np.float32) + 0.5 * paint.astype(np.float32)).astype(np.uint8)
    ov = put(ov, [(170, 1040, "番号28 NPR v1（45°、t*、PaintingCam v1）と原画の 50% 重ね（確認用の図。測定には使わない）", (255, 255, 255))], 20)
    p = os.path.join(evid, "28B_%s_overlay50.png" % pk)
    quant_save(p, ov)
    figs.append(rel(p))
    # 3 境界の偏差図
    img = dimmed(paint, 0.4)
    for k, sel, asg, name in assigned_viz:
        cb = CB[k]
        tp = cb.tp[sel]
        for q in tp[::2]:
            img[int(round(q[1])) % H, int(round(q[0])) % W] = (0, 255, 255)
        if asg is None:
            continue
        rp = cb.rp[asg]
        dd = cb.d_rt[asg]
        c = np.where(dd[:, None] <= 2.0, np.array([[60, 230, 60]]), np.where(dd[:, None] <= 4.0, np.array([[255, 220, 0]]), np.array([[255, 40, 40]])))
        xi = np.clip(np.round(rp[:, 0]).astype(int), 0, W - 1); yi = np.clip(np.round(rp[:, 1]).astype(int), 0, H - 1)
        img[yi, xi] = c
    it = per_key[pk]["items"]
    rows = []
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        v = it[k_]
        b = v.get("boundary") or v.get("boundary_lower") or v.get("lower_ends")
        mx = item_max(v)
        p95 = b.get("p95_px") if b else None
        rows.append("%s: 最大 %.2f px%s  %s" % (k_, mx, (" / p95 %.2f" % p95) if p95 is not None else "", "合格" if verdict[k_] == "pass" else "不合格"))
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        v = it[k_]
        cand = [v.get("boundary"), v.get("boundary_lower"), v.get("lower_ends")] + list(v.get("boundary_by_class", {}).values())
        for b in cand:
            if b and b.get("max_px", 0) > PASS_PX and b.get("worst_display_xy"):
                w_ = b["worst_display_xy"]
                cv2.circle(img, (int(round(w_[0])), int(round(w_[1]))), 12, (255, 40, 40), 2, cv2.LINE_AA)
    items_txt = [(1400, 60 + 26 * i, r_, (255, 255, 255)) for i, r_ in enumerate(rows)]
    img = put(img, [(170, 1010, "色区の境界（45°、t*）：シアン＝真値の項目の境界、描画の境界点 緑 ≤2 px・黄 ≤4 px・赤 >4 px、赤丸＝4 px を超えた所", (255, 255, 255)),
                    (170, 1040, "主役波の外（前景の波・船など）は原画の値で置き換えた合成の評価。空との境 2 px 以内は輪郭の項目（78〜132・72）の対象として除いた。表示 px", (255, 255, 255))] + items_txt, 19)
    p = os.path.join(evid, "28B_%s_boundaries.png" % pk)
    quant_save(p, img)
    figs.append(rel(p))
    # 4 船上・側面・背面 と UV の焼き込み
    def rd(name, s=(960, 540)):
        return cv2.resize(T.imread_rgb(os.path.join(rdir, name)), s, interpolation=cv2.INTER_AREA)
    uv = uv_preview(build, pk, ct)
    top = np.concatenate([rd("28_%s_boat.png" % pk), rd("28_%s_side.png" % pk)], 1)
    bot = np.concatenate([rd("28_%s_back.png" % pk), uv], 1)
    v4 = np.concatenate([top, bot], 0)
    v4 = put(v4, [(12, 10, "船上座席（t*、縦画角 80°）", (0, 0, 0)), (972, 10, "側面", (0, 0, 0)), (12, 550, "背面", (0, 0, 0)),
                  (972, 550, "UV の焼き込み（45°）：左＝色区、右＝埋め方", (255, 255, 255))], 20)
    p = os.path.join(evid, "28B_%s_views.png" % pk)
    quant_save(p, v4)
    figs.append(rel(p))
    # 5 3 つの立体解釈（原画視点・船上）
    tiles = []
    for key in keys:
        d = os.path.join(build, "render", key)
        a = cv2.resize(T.imread_rgb(os.path.join(d, "28_%s_painting.png" % key)), (640, 360), interpolation=cv2.INTER_AREA)
        b = cv2.resize(T.imread_rgb(os.path.join(d, "28_%s_boat.png" % key)), (640, 360), interpolation=cv2.INTER_AREA)
        tiles.append(np.concatenate([a, b], 0))
    order = sorted(range(len(keys)), key=lambda i: int(keys[i][1:]))
    fig = np.concatenate([tiles[i] for i in order], 1)
    fig = np.concatenate([fig, np.full((1080 - 720, 1920, 3), 30, np.uint8)], 0)
    txt = [(12 + 640 * j, 8, "%s°（原画視点）" % keys[i][1:], (0, 0, 0)) for j, i in enumerate(order)]
    txt += [(12 + 640 * j, 368, "%s°（船上座席）" % keys[i][1:], (0, 0, 0)) for j, i in enumerate(order)]
    y0 = 740
    for j, i in enumerate(order):
        key = keys[i]
        its = per_key[key]["items"]
        mx = [item_max(its[k_]) for k_ in ["73", "77", "79", "118", "120", "133", "134", "263", "270"]]
        txt.append((12 + 640 * j, y0, "%s°：175 以外の 9 項目の境界の最大 %.2f px" % (key[1:], max(mx)), (255, 255, 255)))
        txt.append((12 + 640 * j, y0 + 30, "175：境界の最大 %.2f px、残った色区 %d / %d" % (item_max(its["175"]), its["175"]["regions_retained"], its["175"]["regions_total"]), (255, 255, 255)))
    txt.append((12, 1040, "判定は 45°（既定値・利用者未回答）。30°・60° は記録のみ。PC のオフスクリーン描画", (200, 200, 200)))
    fig = put(fig, txt, 20)
    p = os.path.join(evid, "28B_interpretations.png")
    quant_save(p, fig)
    figs.append(rel(p))
    # 6 拡大（描画と原画）：唇、下側の縞、左の白と泡、外周の線
    crops = [("唇の下と内側の帯（120・73）", (800, 270, 1040, 490)), ("下側の縞（77・118）", (380, 560, 620, 780)),
             ("白の中の色区（175・79）", (200, 380, 440, 600)), ("外周の線（142・143）", (600, 70, 840, 290))]
    tiles = []
    for name, (x0, y0_, x1, y1) in crops:
        a = cv2.resize(rgb[y0_:y1, x0:x1], (480, 440), interpolation=cv2.INTER_NEAREST)
        b = cv2.resize(paint[y0_:y1, x0:x1], (480, 440), interpolation=cv2.INTER_NEAREST)
        tiles.append((name, a, b))
    rows_ = []
    for i in range(0, 4, 2):
        r_ = np.concatenate([tiles[i][1], tiles[i][2], tiles[i + 1][1], tiles[i + 1][2]], 1)
        rows_.append(r_)
    cl = np.concatenate(rows_ + [np.full((1080 - 880, 1920, 3), 30, np.uint8)], 0)
    txt = []
    for i, (name, _, _) in enumerate(tiles):
        x = 960 * (i % 2); y = 440 * (i // 2)
        txt.append((x + 8, y + 6, name + "：左 描画（外殻線あり）／右 原画（2 倍）", (255, 255, 255)))
    lp = line
    txt.append((12, 890, "外殻線 v0（中心眼から世界幅で計算、記録のみ）：142 線の中心のずれ 最大 %s px・p95 %s px、線幅の中央値 %s px（原画 %s）" % (
        lp["142"]["centre_offset_max_px"], lp["142"]["centre_offset_p95_px"], lp["142"]["render_line_width_median_px"],
        "・".join("%.2f" % v for v in lp["142"]["truth_line_width_median_px"].values())), (255, 255, 255)))
    txt.append((12, 920, "143 線の中心のずれ 最大 %s px・p95 %s px、線幅の中央値 %s px、線がある割合 %s" % (
        lp["143"]["centre_offset_max_px"], lp["143"]["centre_offset_p95_px"], lp["143"]["render_line_width_median_px"], lp["143"]["line_present_fraction"]), (255, 255, 255)))
    txt.append((12, 956, "描画には内側の藍の線（泡・爪・縞の縁の線）がない。色区の地図では線を両側の色へ吸収した。色区の境界線と爪の縁の線は番号36", (255, 255, 255)))
    txt.append((12, 992, "265 内側の帯の色 ΔE00 %.2f（目標 ≤5）。266 藍中・267 白：領域内の ΔE00 の標準偏差 原画視点 %.3f・%.3f／船上 %.3f・%.3f" % (
        col["265"]["dE00"], col["266"]["views"]["ai_mid"]["painting_view"]["dE00_to_median_std"], col["267"]["views"]["white"]["painting_view"]["dE00_to_median_std"],
        col["266"]["views"]["ai_mid"]["boat_view"]["dE00_to_median_std"], col["267"]["views"]["white"]["boat_view"]["dE00_to_median_std"]), (255, 255, 255)))
    cl = put(cl, txt, 19)
    p = os.path.join(evid, "28B_%s_closeups.png" % pk)
    quant_save(p, cl)
    figs.append(rel(p))
    return figs


def uv_preview(build, key, ct):
    """UV3 の焼き込み（4096²）を 960×540 の図へ：左 480×480 に色区、右 480×480 に埋め方。"""
    N = 4096
    sdf = np.fromfile(os.path.join(build, "bake", "af28_uvsdf_%s.bin" % key), np.uint8).reshape(N, N, 4)
    cat = np.fromfile(os.path.join(build, "bake", "af28_uvcat_%s.bin" % key), np.uint8).reshape(N, N)
    cls = sdf.argmax(-1)
    pal = np.array([[248, 243, 223], [198, 215, 203], [44, 105, 147], [35, 64, 97]], np.uint8)
    img = pal[cls][::-1]            # 行 0 が v=0（下）なので上下を返して表示
    cc = np.array([[0, 0, 0], [240, 240, 240], [20, 20, 120], [230, 150, 40], [60, 170, 90], [40, 60, 80], [200, 60, 200], [200, 60, 200], [255, 0, 0],
                   [120, 190, 230]], np.uint8)
    cimg = cc[cat][::-1]
    a = cv2.resize(img, (420, 420), interpolation=cv2.INTER_AREA)
    b = cv2.resize(cimg, (420, 420), interpolation=cv2.INTER_NEAREST)
    out = np.full((540, 960, 3), 30, np.uint8)
    out[40:460, 20:440] = a
    out[40:460, 500:920] = b
    out = put(out, [(20, 464, "左：色区（白・淡い水色・藍中・藍濃）　右：埋め方", (220, 220, 220)),
                    (20, 486, "白 直接　紺 内側の藍濃　橙 u 方向（色）　水 u 方向（藍だけ）", (220, 220, 220)),
                    (20, 506, "緑 v 方向（縞）　灰 海面　紫 残り", (220, 220, 220)),
                    (20, 522, "焼き込み用 UV（UV3）：横 u′（後ろの海→頂→唇→内壁→前の海）、縦 v′（下が手前）", (180, 180, 180))], 14)
    return out


if __name__ == "__main__":
    sys.exit(main())
