"""基準輪郭の候補A・Bを判定して統合し、正式な target/base_contour.json を作る。

実行例（画面なし、約1分）:
    & "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/contour/build_base_contour.py
オプション（-ScriptArgs で '--' の後に渡す）:
    --params <json>   別のパラメーターファイル。既定値は隣の base_contour_params.json。
    --tag <name>      試行実行。すべて results/step1_prepare/contour_final/variant_<name>/ に出力し、
                      target/base_contour.json と target/base_contour_overlay.png には触れない。

入力: 原画、target/candidates/a/base_contour.json、target/candidates/b/base_contour.json、
      target/candidates/b/base_contour_alt_white_body_outline.json。
      候補ファイルはそれぞれ1コマンドで再生成できる。
出力: target/base_contour.json（形式 gw.base_contour.v1）、target/base_contour_overlay.png、
      results/step1_prepare/contour_final/（比較画像、判定用切出し、最終切出し、グラフ、
      metrics.json、左端の別の読み取り方による輪郭）。
同じパラメーターファイルと候補ファイルからはバイト単位で同じ JSON を得る。

処理内容
  1. 輪郭に沿って A と B を比較する。区間ごとの平均・95パーセンタイル・最大差、グラフ、
     差が0.5%を超える部分の一覧を作る。該当部分がパラメーター内の判定領域に含まれなければ終了コード1。
  2. 最終輪郭 = 基本候補 B + 判定に従い候補Aから差し込む部分 + 背面左端の選択した読み取り方
     + 名称を付け直した補完部分。特徴点と区間を求め、2 px で再標本化する。
  3. S1～S6、独自の S8、波頭の厚みを再測定し、独立した縁の確認と
     低域通過による S7 と S8 の関係の診断を行う。
  4. 重ね画像、切出し画像、グラフ、metrics.json を作る。
各区間の規約を保つ。back は左画面端→峰、head は峰→波頭の先端
（爪を除いた最も右の点）、inner_arc は先端→下面→内側の弧→谷の水位。
端点は共有し、in_S7=False は completed_* の点に限る。

各区間の 'source' フラグ。説明は JSON の 'source_flags' に書く。
  traced / claw_root_bridge / completed_occluded / completed_other は候補から引き継ぐ。
  offset_from_visible_edge は2026-09-20 の批判的検証後に追加したラベルで、形状は従来の
  'traced' を付けたファイルとビット単位で同じ。white_body_outline の読み取り方で構成した
  背面左端を表す。そこには墨の線がなく、見える白い波本体の縁を測定した墨線の幅だけ外側へずらす。
  in_S7=true のままとし、'pending_user_confirmation' / 'pending_stretches' に X 範囲を記録する。
  テストはその部分の S7 を別に報告できる。docs/records/step1_contour_flags.md を参照。
"""
import hashlib
import math
import os
import sys

import numpy as np

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gw import bootstrap, paths, frame, imgio, draw, plot          # noqa: E402
from contour import method_a_lib as LA                              # noqa: E402  （numpy のみを使う折れ線の補助関数）

log = bootstrap.log
HERE = os.path.dirname(os.path.abspath(__file__))
SEG_NAMES = ("back", "head", "inner_arc")
SEG_JP = {"back": "背", "head": "波頭", "inner_arc": "内側の弧"}
COMPLETED = ("completed_occluded", "completed_other")
OFFSET_FLAG = "offset_from_visible_edge"
ON_LINE_FLAGS = ("traced", OFFSET_FLAG)               # 実在または構成した輪郭上にあるとする点のフラグ。
PENDING_KEY = "pending_user_confirmation"
PENDING_STRETCHES_KEY = "pending_stretches"
PENDING_LEFT_END = "back_left_variant"
SOURCE_FLAG_TEXT = {
    "traced": "outer (sky-side) half-level edge of a DRAWN ink line of the painting, traced (sub-pixel)",
    OFFSET_FLAG: "CONSTRUCTED, not traced: no ink line is drawn there. Left end of the back in the white_body_outline reading "
                 "(below the fork of the back's outline): the VISIBLE white-body edge (white / dark-blue boundary) shifted outwards "
                 "by the ink-line width measured above the fork (provenance.build_info.left_end.outward_offset_px). in_S7 = true; "
                 "the stretch depends on the pending decision 'back_left_variant' (see pending_stretches)",
    "claw_root_bridge": "ball-smoothed; includes ink-width bumps, not every run is a claw root. The flag marks EVERY stretch where the "
                        "rolling ball (morphological opening from the body side, candidate B) moved the raw silhouette by more than "
                        "its tolerance (src/contour/method_b_core.py label_and_bridge); the stretch is replaced by the chord between "
                        "its two end points. in_S7 = true",
    "completed_occluded": "hidden behind the near wave, completed by extrapolation (in_S7 = false)",
    "completed_other": "visible sea patch without a drawn wave face, completed by extrapolation (in_S7 = false)",
}


# ====================================================================== 補助関数
def P(cfg, name):
    e = cfg[name]
    return e["value"] if isinstance(e, dict) and "value" in e else e


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def bilinear(a, x, y):
    """a[row, col] を連続画素座標で標本化する（画素 (i, j) の中心は (i + .5, j + .5)）。"""
    h, w = a.shape
    fx = np.clip(np.asarray(x, np.float64) - 0.5, 0.0, w - 1.001)
    fy = np.clip(np.asarray(y, np.float64) - 0.5, 0.0, h - 1.001)
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    tx, ty = fx - x0, fy - y0
    return ((1 - tx) * (1 - ty) * a[y0, x0] + tx * (1 - ty) * a[y0, x0 + 1]
            + (1 - tx) * ty * a[y0 + 1, x0] + tx * ty * a[y0 + 1, x0 + 1])


def resample_1px(pts, lab=None):
    s = LA.arclength(pts)
    n = max(1, int(round(s[-1])))
    t = np.linspace(0.0, s[-1], n + 1)
    out = np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], axis=1)
    if lab is None:
        return out
    idx = np.clip(np.searchsorted(s, t, side="left"), 0, len(s) - 1)
    prev = np.clip(idx - 1, 0, len(s) - 1)
    use_prev = np.abs(s[prev] - t) < np.abs(s[idx] - t)
    idx = np.where(use_prev, prev, idx)
    return out, np.asarray(lab)[idx]


def resample_exact(pts, lab, spacing):
    s = LA.arclength(pts)
    n = max(1, int(round(s[-1] / spacing)))
    t = np.linspace(0.0, s[-1], n + 1)
    out = np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], axis=1)
    out[0], out[-1] = pts[0], pts[-1]
    idx = np.clip(np.searchsorted(s, t, side="left"), 0, len(s) - 1)
    prev = np.clip(idx - 1, 0, len(s) - 1)
    idx = np.where(np.abs(s[prev] - t) < np.abs(s[idx] - t), prev, idx)
    return out, np.asarray(lab)[idx], s[-1] / n


def left_normals(pts, half=5):
    """画素座標（y は下向き）で進行方向の左、すなわち輪郭の空側を向く単位法線を返す。

    接線 (tx, ty) に対する法線は (ty, -tx)。接線は ±half 点を結ぶ弦から求める。
    """
    p = np.asarray(pts, np.float64)
    n = len(p)
    i0 = np.clip(np.arange(n) - half, 0, n - 1)
    i1 = np.clip(np.arange(n) + half, 0, n - 1)
    t = p[i1] - p[i0]
    ln = np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)
    t = t / ln[:, None]
    return np.stack([t[:, 1], -t[:, 0]], axis=1), t


def nearest_index(pts, q):
    d = np.hypot(pts[:, 0] - q[0], pts[:, 1] - q[1])
    return int(np.argmin(d))


def runs_of(mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def in_bbox(p, bb, margin=0.0):
    return (bb[0] - margin <= p[0] <= bb[2] + margin) and (bb[1] - margin <= p[1] <= bb[3] + margin)


def stats_pct(d_px, F):
    d = np.asarray(d_px, np.float64)
    if d.size == 0:
        return {"n": 0, "mean": None, "p95": None, "max": None}
    v = F.px_to_pct_h(d)
    return {"n": int(d.size), "mean": float(v.mean()), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


# ====================================================================== 候補
def load_candidate(path):
    j = paths.read_json(path)
    pts, src, seg = [], [], []
    by = {s["name"]: s for s in j["segments"]}
    for k, nm in enumerate(SEG_NAMES):
        p = np.asarray(by[nm]["points_px"], np.float64)
        s = list(by[nm]["source"])
        if k:
            p, s = p[1:], s[1:]
        pts.append(p)
        src += s
        seg += [nm] * len(p)
    pts = np.concatenate(pts)
    n_back = len(by["back"]["points_px"])
    n_head = len(by["head"]["points_px"])
    return {"json": j, "pts": pts, "src": np.array(src), "seg": np.array(seg),
            "i_crest": n_back - 1, "i_tip": n_back - 1 + n_head - 1,
            "back_pts": np.asarray(by["back"]["points_px"], np.float64)}


def compare_candidates(A, B, F, cfg):
    """輪郭に沿った距離、区間別統計値、しきい値を超える連続部分を求める。"""
    dA = LA.point_to_polyline_dist(A["pts"], B["pts"])
    dB = LA.point_to_polyline_dist(B["pts"], A["pts"])
    out = {"per_segment": {}, "stretches": []}
    for nm in SEG_NAMES:
        e = {}
        for tag, d, C in (("A_to_B", dA, A), ("B_to_A", dB, B)):
            m = C["seg"] == nm
            comp = np.isin(C["src"], COMPLETED)
            e[tag + "_visible"] = stats_pct(d[m & ~comp], F)
            if (m & comp).any():
                e[tag + "_completed"] = stats_pct(d[m & comp], F)
        out["per_segment"][nm] = e
    thr = float(F.pct_h_to_px(P(cfg, "judge_threshold_pct_h")))
    gap = P(cfg, "judge_run_merge_gap_px")
    found = []
    for tag, d, C in (("A", dA, A), ("B", dB, B)):
        s = LA.arclength(C["pts"])
        rr = runs_of(d > thr)
        merged = []
        for (i, j) in rr:
            if merged and s[i] - s[merged[-1][1]] < gap:
                merged[-1] = (merged[-1][0], j)
            else:
                merged.append((i, j))
        for (i, j) in merged:
            q = C["pts"][i:j + 1]
            found.append({"on": tag, "i0": int(i), "i1": int(j), "segment": str(C["seg"][(i + j) // 2]),
                          "from_px": [float(q[0, 0]), float(q[0, 1])], "to_px": [float(q[-1, 0]), float(q[-1, 1])],
                          "bbox_px": [float(q[:, 0].min()), float(q[:, 1].min()), float(q[:, 0].max()), float(q[:, 1].max())],
                          "centre_px": [float(q[:, 0].mean()), float(q[:, 1].mean())],
                          "length_px": float(s[j] - s[i]), "max_dist_px": float(d[i:j + 1].max()),
                          "max_dist_pct_h": float(F.px_to_pct_h(d[i:j + 1].max())),
                          "labels": sorted(set(C["src"][i:j + 1].tolist()))})
    verdicts = P(cfg, "verdicts")
    unjudged = []
    for st in found:
        hit = [v["id"] for v in verdicts if in_bbox(st["centre_px"], v["bbox_px"], 15.0)]
        st["verdict_ids"] = hit
        if not hit:
            unjudged.append(st)
    out["stretches"] = found
    out["unjudged"] = unjudged
    out["dA"], out["dB"] = dA, dB
    return out


# ====================================================================== 原画上の縁の測定
class EdgeProbe:
    """候補A・Bの実装から独立に、輪郭の法線に沿う半値境界の位置を測る。"""

    def __init__(self, rgb):
        a = rgb.astype(np.float32)
        self.luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
        self.rb = a[..., 0] - a[..., 2]
        self.us = np.arange(-18.0, 10.0 + 1e-9, 0.25)

    def profiles(self, pts, nrm, field):
        xs = pts[:, 0:1] + self.us[None, :] * nrm[:, 0:1]
        ys = pts[:, 1:2] + self.us[None, :] * nrm[:, 1:2]
        return bilinear(field, xs, ys)

    def _sel(self, lo, hi):
        return (self.us >= lo) & (self.us <= hi)

    @staticmethod
    def _cross(us, prof, k0, step, level, rising):
        """k0 から step（+1 または -1）方向へ進み、`level` を初めて横切る位置。"""
        k = k0
        n = len(us)
        while 0 <= k + step < n:
            a, b = prof[k], prof[k + step]
            if (rising and a <= level < b) or ((not rising) and a >= level > b):
                t = (level - a) / (b - a) if b != a else 0.0
                return us[k] + t * (us[k + step] - us[k])
            k += step
        return np.nan

    def outer_inner(self, pts, nrm, min_contrast=40.0):
        """空と墨、墨と本体の半値境界の位置を輪郭点からの符号付き距離で返す。

        返却値は (u_outer, u_inner, field_used)。単位は画素、正は空側。
        コントラストが低い場所の値は NaN とする。
        """
        n = len(pts)
        u_out = np.full(n, np.nan)
        u_in = np.full(n, np.nan)
        used = np.zeros(n, np.int8)
        prof_l = self.profiles(pts, nrm, self.luma)
        prof_c = self.profiles(pts, nrm, self.rb) * 2.0
        s_sky, s_ink, s_body = self._sel(3.0, 7.0), self._sel(-6.0, 1.5), self._sel(-17.0, -11.0)
        idx_ink = np.nonzero(s_ink)[0]
        k_start = int(np.nonzero(self.us >= 3.0)[0][0])
        for i in range(n):
            for code, prof in ((1, prof_l[i]), (2, prof_c[i])):
                sky = float(np.median(prof[s_sky]))
                k_min = int(idx_ink[np.argmin(prof[idx_ink])])
                ink = float(prof[k_min])
                if sky - ink < min_contrast:
                    continue
                u_out[i] = self._cross(self.us, prof, k_start, -1, 0.5 * (sky + ink), rising=False)
                body = float(np.median(prof[s_body]))
                if body - ink >= min_contrast:
                    u_in[i] = self._cross(self.us, prof, k_min, -1, 0.5 * (body + ink), rising=True)
                used[i] = code
                break
        return u_out, u_in, used

    def inner_only(self, pts, nrm, w, min_contrast=40.0):
        """外側へ w ずらした輪郭に対する、見える本体縁の位置を返す。

        本体と暗い部分の半値境界までの距離（画素、正は空側）。期待値は -w。
        """
        prof_l = self.profiles(pts, nrm, self.luma)
        s_dark = np.nonzero(self._sel(-w - 0.5, -w + 4.0))[0]
        s_body = self._sel(-w - 13.0, -w - 7.0)
        out = np.full(len(pts), np.nan)
        for i in range(len(pts)):
            prof = prof_l[i]
            k_min = int(s_dark[np.argmin(prof[s_dark])])
            dark = float(prof[k_min])
            body = float(np.median(prof[s_body]))
            if body - dark < min_contrast:
                continue
            out[i] = self._cross(self.us, prof, k_min, -1, 0.5 * (body + dark), rising=True)
        return out


def q_stats(v):
    v = np.asarray(v, np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "median": float(np.median(v)), "mean": float(v.mean()),
            "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))}


def measure_s6(rgb, cfg, probe):
    x0, y0, x1, y1 = [int(v) for v in P(cfg, "s6_window_px")]
    ink = probe.rb[y0:y1, x0:x1] < P(cfg, "ink_rb_max")
    cnt = ink.sum(axis=0)
    cols = np.nonzero(cnt >= 3)[0]
    if cols.size == 0:
        return None
    c = int(cols[-1])
    rows = np.nonzero(ink[:, c])[0]
    y = y0 + float(rows.mean()) + 0.5
    # 画素未満の補間: 同じ行の右側にある墨と空の半値境界。
    xs = np.arange(x0 + c - 4 + 0.5, x0 + c + 10 + 0.5, 0.25)
    prof = bilinear(probe.luma, xs, np.full_like(xs, y))
    ink_l = float(prof[:24].min())
    sky_l = float(np.median(prof[-16:]))
    k = int(np.argmin(prof[:24]))
    xc = EdgeProbe._cross(xs, prof, k, +1, 0.5 * (ink_l + sky_l), rising=True)
    return {"px": [float(xc) if np.isfinite(xc) else float(x0 + c + 1), y],
            "pixel_level_px": [float(x0 + c + 1), y], "subpixel_ok": bool(np.isfinite(xc)),
            "how": "right-most column with >= 3 ink pixels (R-B < %g) inside the window %s; y = mean row of the ink "
                   "pixels of that column; x refined to the luma half level between ink and sky along that row"
                   % (P(cfg, "ink_rb_max"), [x0, y0, x1, y1])}


def measure_sea_top(probe, cfg):
    c0, c1 = [int(v) for v in P(cfg, "s3_sea_columns_px")]
    thr = P(cfg, "ink_rb_max")
    ys = []
    for c in range(c0, c1 + 1):
        col = probe.rb[1750:2050, c] < thr
        run = 0
        for k, v in enumerate(col):
            run = run + 1 if v else 0
            if run >= 6:
                ys.append(1750 + k - 5)
                break
    ys = np.array(ys, np.float64)
    return {"columns_px": [c0, c1], "n_columns": int(ys.size), "median_y_px": float(np.median(ys)),
            "min_y_px": float(ys.min()), "max_y_px": float(ys.max())}


# ====================================================================== 最終輪郭の構築
def splice_other(base_pts, base_lab, base_org, other, bbox, base_name, other_name, tol=1.5):
    """bbox 内で `other` と異なる基準輪郭の部分を、`other` の対応部分に置き換える。"""
    d = LA.point_to_polyline_dist(base_pts, other["pts"])
    inside = np.array([in_bbox(p, bbox, 0.0) for p in base_pts])
    bad = np.nonzero(inside & (d > tol))[0]
    if bad.size == 0:
        return base_pts, base_lab, base_org, None
    i0, i1 = int(bad[0]), int(bad[-1])
    while i0 > 0 and not np.all(d[max(0, i0 - 5):i0] < tol):
        i0 -= 1
    while i1 < len(d) - 1 and not np.all(d[i1 + 1:i1 + 6] < tol):
        i1 += 1
    i0, i1 = max(0, i0 - 3), min(len(d) - 1, i1 + 3)
    j0 = nearest_index(other["pts"], base_pts[i0])
    j1 = nearest_index(other["pts"], base_pts[i1])
    if j1 <= j0:
        raise RuntimeError("splice: candidates do not re-join in order inside %s" % (bbox,))
    mid_p = other["pts"][j0 + 1:j1]
    mid_l = other["src"][j0 + 1:j1]
    pts = np.vstack([base_pts[:i0 + 1], mid_p, base_pts[i1:]])
    lab = np.concatenate([base_lab[:i0 + 1], mid_l, base_lab[i1:]])
    org = np.concatenate([base_org[:i0 + 1], np.array([other_name] * len(mid_p), dtype=object), base_org[i1:]])
    info = {"from_px": base_pts[i0].tolist(), "to_px": base_pts[i1].tolist(), "n_points_inserted": int(len(mid_p))}
    return pts, lab, org, info


def white_body_left_end(pts, lab, org, cands, probe, cfg):
    """背面の左端を白い本体の輪郭に置き換える。

    B_alt の内縁を、測定した墨線の幅だけ外側にずらす。
    新しい (pts, lab, org, info) を返す。
    """
    alt_back = cands["B_alt"]["back_pts"]
    s_alt = LA.arclength(alt_back)
    d = LA.point_to_polyline_dist(alt_back, pts)
    cand = np.nonzero((s_alt > 100.0) & (d < P(cfg, "alt_join_dist_px")))[0]
    if cand.size == 0:
        raise RuntimeError("white-body trace never joins the main back")
    j = int(cand[0])
    inner = alt_back[:j + 1]
    # ---- 分岐点より上で墨線の幅を測る。
    m0 = nearest_index(pts, inner[-1])
    s_main = LA.arclength(pts)
    a, b = P(cfg, "line_width_measure_stretch_px")
    sel = np.nonzero((s_main >= s_main[m0] + a) & (s_main <= s_main[m0] + b))[0]
    nrm, _ = left_normals(pts)
    u_out, u_in, _ = probe.outer_inner(pts[sel], nrm[sel])
    width = u_out - u_in
    ok = np.isfinite(width)
    w_med = float(np.median(width[ok]))
    info = {"join_px_inner_edge": inner[-1].tolist(), "inner_edge_points_used": int(len(inner)),
            "line_width_px": {"median": w_med, "p05": float(np.percentile(width[ok], 5)),
                              "p95": float(np.percentile(width[ok], 95)), "n": int(ok.sum()),
                              "stretch_from_px": pts[sel[0]].tolist(), "stretch_to_px": pts[sel[-1]].tolist()},
            "outer_edge_offset_of_base_on_that_stretch_px": q_stats(u_out)}
    w = w_med if P(cfg, "white_body_outward_offset") == "measured_line_width" else 0.0
    info["outward_offset_px"] = w
    n_in, _ = left_normals(inner)
    off = inner + w * n_in
    # ---- 左枠 x = 0 まで切り詰めるか延長する。
    if off[0, 0] < 0.0:
        k = int(np.nonzero(off[:, 0] >= 0.0)[0][0])
        t = (0.0 - off[k - 1, 0]) / (off[k, 0] - off[k - 1, 0])
        first = off[k - 1] + t * (off[k] - off[k - 1])
        off = np.vstack([[0.0, first[1]], off[k:]])
    elif off[0, 0] > 0.0:
        tdir = off[1] - off[0]
        t = off[0, 0] / tdir[0]
        off = np.vstack([[0.0, off[0, 1] - t * tdir[1]], off])
    # ---- 主となる背面との継ぎ目（前進方向で分岐点より上）。
    m1 = nearest_index(pts, off[-1])
    tdir = off[-1] - off[-6]
    tdir = tdir / max(np.hypot(*tdir), 1e-9)
    while m1 < len(pts) - 1 and float(np.dot(pts[m1] - off[-1], tdir)) < 1.0:
        m1 += 1
    info["seam"] = {"offset_curve_end_px": off[-1].tolist(), "main_back_start_px": pts[m1].tolist(),
                    "along_step_px": float(np.dot(pts[m1] - off[-1], tdir)),
                    "normal_step_px": float(abs(np.dot(pts[m1] - off[-1], np.array([tdir[1], -tdir[0]]))))}
    new_pts = np.vstack([off, pts[m1:]])
    # ラベルのみ変更（2026-09-20）: ずらした曲線は追跡ではなく構成したものなので、
    # 'traced' の代わりに OFFSET_FLAG を使う。形状は変更しない。
    new_lab = np.concatenate([np.array([OFFSET_FLAG] * len(off), dtype=object), lab[m1:]])
    new_org = np.concatenate([np.array(["B_alt_inner_edge+offset"] * len(off), dtype=object), org[m1:]])
    # ---- 継ぎ目を局所的に平滑化する。
    sig = P(cfg, "seam_smooth_sigma_px")
    hw = P(cfg, "seam_smooth_halfwidth_px")
    s = LA.arclength(new_pts)
    s_seam = s[len(off) - 1]
    lo, hi = s_seam - 2 * hw, s_seam + 2 * hw
    k0, k1 = int(np.searchsorted(s, lo)), int(np.searchsorted(s, hi))
    sub = new_pts[k0:k1 + 1]
    sub1 = resample_1px(sub)
    sm = LA.gaussian_smooth(sub1, sig, 1.0)
    s1 = LA.arclength(sub1)
    ss = s[k0:k1 + 1] - s[k0]
    smx = np.stack([np.interp(ss, s1, sm[:, 0]), np.interp(ss, s1, sm[:, 1])], axis=1)
    dist = np.abs(s[k0:k1 + 1] - s_seam)
    wgt = np.where(dist <= hw, 1.0, 0.5 * (1 + np.cos(np.pi * np.clip((dist - hw) / hw, 0, 1))))[:, None]
    moved = wgt * smx + (1 - wgt) * sub
    info["seam"]["max_shift_by_smoothing_px"] = float(np.hypot(*(moved - sub).T).max())
    new_pts[k0:k1 + 1] = moved
    new_org[k0:k1 + 1] = np.where(dist <= hw, "seam_smoothed", new_org[k0:k1 + 1])
    new_pts[0, 0] = 0.0
    info["left_frame_edge_px"] = new_pts[0].tolist()
    info["n_points_left_end"] = int(len(off))
    return new_pts, new_lab, new_org, info


def relabel_completion(pts, lab, probe, cfg):
    comp = np.nonzero(np.isin(lab, COMPLETED))[0]
    if comp.size == 0:
        return lab, None
    k = 3
    rb = probe.rb
    vals = []
    for p in pts[comp]:
        x, y = int(p[0]), int(p[1])
        vals.append(float(rb[max(0, y - k):y + k + 1, max(0, x - k):x + k + 1].mean()))
    sea = np.array(vals) < P(cfg, "completed_other_sea_rb_max")
    first = None
    for i in range(len(sea)):
        if sea[i] and sea[i:].mean() >= 0.95:
            first = i
            break
    lab = lab.copy()
    lab[comp] = "completed_occluded"
    info = {"n_completed": int(comp.size), "first_sea_point_px": None}
    if first is not None:
        lab[comp[first:]] = "completed_other"
        info["first_sea_point_px"] = pts[comp[first]].tolist()
        info["n_completed_other"] = int(comp.size - first)
    return lab, info


def build_contour(variant, cands, probe, cfg, F):
    base_name = P(cfg, "base_candidate")
    other_name = "A" if base_name == "B" else "B"
    base, other = cands[base_name], cands[other_name]
    pts = base["pts"].copy()
    lab = base["src"].astype(object).copy()
    org = np.array([base_name] * len(pts), dtype=object)
    info = {"base_candidate": base_name, "variant": variant, "splices": []}
    for v in P(cfg, "verdicts"):
        if v["use"] == other_name:
            pts, lab, org, si = splice_other(pts, lab, org, other, v["bbox_px"], base_name, other_name)
            info["splices"].append({"verdict": v["id"], "result": si})
    if variant == "white_body_outline":
        if base_name != "B":
            raise RuntimeError("the white-body left end is defined relative to candidate B")
        pts, lab, org, li = white_body_left_end(pts, lab, org, cands, probe, cfg)
        info["left_end"] = li
    elif variant != "sky_silhouette":
        raise ValueError("unknown back_left_variant %r" % variant)
    lab, ci = relabel_completion(pts, lab, probe, cfg)
    info["completion"] = ci

    # ---- 1 px 間隔の写しで特徴点を求める。
    p1, l1 = resample_1px(pts, lab)
    _, o1 = resample_1px(pts, org)
    sig = float(F.pct_h_to_px(P(cfg, "landmark_sigma_pct_h")))
    sm = LA.gaussian_smooth(p1, sig, 1.0)
    vis = ~np.isin(l1, COMPLETED)
    i_vis_end = int(np.nonzero(vis)[0][-1])
    i_c = int(np.argmin(sm[:i_vis_end + 1, 1]))
    i_top = int(np.argmin(p1[:i_vis_end + 1, 1]))
    i_t = i_c + int(np.argmax(p1[i_c:i_vis_end + 1, 0]))
    i_d = i_t + int(np.argmin(sm[i_t:i_vis_end + 1, 0]))
    i_dstrict = i_t + int(np.argmin(p1[i_t:i_vis_end + 1, 0]))
    tol = P(cfg, "plateau_tol_px")
    top_run = np.nonzero(p1[:i_t, 1] <= p1[i_top, 1] + tol)[0]
    deep_run = i_t + np.nonzero(p1[i_t:i_vis_end + 1, 0] <= p1[i_dstrict, 0] + tol)[0]
    lm = {"i_crest": i_c, "i_tip": i_t, "i_deep": i_d, "i_vis_end": i_vis_end,
          "crest_strict_px": p1[i_top].tolist(),
          "crest_plateau_x_px": [float(p1[top_run, 0].min()), float(p1[top_run, 0].max())],
          "deep_strict_px": p1[i_dstrict].tolist(),
          "deep_run_y_px": [float(p1[deep_run, 1].min()), float(p1[deep_run, 1].max())]}

    # ---- 2 px 間隔の区間。
    sp = P(cfg, "sample_spacing_px")
    segs = {}
    for nm, (a, b) in (("back", (0, i_c)), ("head", (i_c, i_t)), ("inner_arc", (i_t, len(p1) - 1))):
        q, ql, actual = resample_exact(p1[a:b + 1], l1[a:b + 1], sp)
        _, qo, _ = resample_exact(p1[a:b + 1], o1[a:b + 1], sp)
        q = np.round(q, 3)
        segs[nm] = {"pts": q, "lab": ql, "org": qo, "actual_spacing_px": float(actual),
                    "length_px": float(LA.arclength(p1[a:b + 1])[-1])}
    segs["head"]["pts"][0] = segs["back"]["pts"][-1]
    segs["inner_arc"]["pts"][0] = segs["head"]["pts"][-1]
    return {"variant": variant, "segs": segs, "p1": p1, "l1": l1, "o1": o1, "lm": lm, "info": info,
            "crest_px": segs["back"]["pts"][-1].copy(), "tip_px": segs["head"]["pts"][-1].copy(),
            "deep_px": np.round(p1[i_d], 3)}


def pending_left_end(back_pts, back_lab, x_range_px, F, from_label):
    """保留中の判断 'back_left_variant' に依存する背面部分の JSON 項目を作る。

    back_pts / back_lab は出力先ファイルの 'back' 区間。x_range_px は
    white_body_outline の解釈で構成した部分（offset_from_visible_edge）の [x0, x1]。
    ラベルとメタデータのみを扱う。
    """
    x = np.asarray(back_pts, np.float64)[:, 0]
    sel = np.nonzero((x >= x_range_px[0]) & (x <= x_range_px[1]))[0]
    lab = np.asarray(back_lab, dtype=object)
    blk = {"segment": "back",
           "x_range_px": [round(float(x_range_px[0]), 3), round(float(x_range_px[1]), 3)],
           "x_range_H": [round(float(F.px_to_H(v, 0.0)[0]), 6) for v in x_range_px],
           "selector": "points of segment 'back' with x_range_px[0] <= x_px <= x_range_px[1] (same as x_range_H on points_H[:, 0])",
           "index_range": ([int(sel[0]), int(sel[-1])] if sel.size else None),
           "n_points": int(sel.size),
           "index_range_is_contiguous": bool(sel.size == 0 or np.all(np.diff(sel) == 1)),
           "flag_counts": {k: int((lab[sel] == k).sum()) for k in sorted(set(lab[sel].tolist()))},
           "in_S7": True,
           "x_range_taken_from": from_label,
           "what": "left end of the back below the fork of the back's outline at about (337, 894) px. white_body_outline reading: NO ink line "
                   "is drawn there, the line is CONSTRUCTED (flag offset_from_visible_edge = visible white-body edge shifted outwards by "
                   "the measured ink-line width); sky_silhouette reading: the traced top edge of the dark-blue band. The two readings "
                   "differ by up to 7.1 % of image height on this stretch (judge's measurement, base_contour_params.json "
                   "back_left_variant). The stretch stays in_S7 = true; tests should report S7 "
                   "for it SEPARATELY until the user has confirmed the reading (docs/base_contour_report.md section 2 and 12)."}
    return blk


def full_polyline(C):
    pts = [C["segs"]["back"]["pts"], C["segs"]["head"]["pts"][1:], C["segs"]["inner_arc"]["pts"][1:]]
    lab = [C["segs"]["back"]["lab"], C["segs"]["head"]["lab"][1:], C["segs"]["inner_arc"]["lab"][1:]]
    seg = [["back"] * len(pts[0]), ["head"] * len(pts[1]), ["inner_arc"] * len(pts[2])]
    return np.vstack(pts), np.concatenate(lab), np.concatenate([np.array(s) for s in seg])


# ====================================================================== 輪郭上の測定
def poly_principal_axis(poly_px):
    """画素座標（y は下向き）の閉じた多角形から面積モーメントで主軸を求める。

    角度は度数で、0 は +X、正は上向き。
    """
    x = poly_px[:, 0].astype(np.float64)
    y = -poly_px[:, 1].astype(np.float64)               # Z を上向きに変換。
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    c = x * y1 - x1 * y
    A = 0.5 * c.sum()
    cx = ((x + x1) * c).sum() / (6 * A)
    cy = ((y + y1) * c).sum() / (6 * A)
    Ixx = ((y * y + y * y1 + y1 * y1) * c).sum() / 12.0
    Iyy = ((x * x + x * x1 + x1 * x1) * c).sum() / 12.0
    Ixy = ((x * y1 + 2 * x * y + 2 * x1 * y1 + x1 * y) * c).sum() / 24.0
    mxx = Iyy / A - cx * cx
    myy = Ixx / A - cy * cy
    mxy = Ixy / A - cx * cy
    ang = 0.5 * math.degrees(math.atan2(2 * mxy, mxx - myy))
    ev = np.linalg.eigvalsh(np.array([[mxx, mxy], [mxy, myy]]))
    return {"deg": float(ang), "area_px2": float(abs(A)), "centroid_px": [float(cx), float(-cy)],
            "elongation": float(math.sqrt(ev[1] / ev[0])) if ev[0] > 0 else None}


def own_s8(pts, spacing_px, n_phase=4):
    s = LA.arclength(pts)
    best = {"max_deg": 0.0, "n": 0, "n_ge_15": 0, "at_px": None, "all_s": [], "all_deg": [], "all_px": []}
    for ph in range(n_phase):
        t = np.arange(spacing_px * ph / n_phase, s[-1] + 1e-9, spacing_px)
        if len(t) < 3:
            continue
        q = LA.interp_at(pts, s, t)
        ang = np.degrees(np.arctan2(-np.diff(q[:, 1]), np.diff(q[:, 0])))
        d = np.abs(LA.angle_diff_deg(ang[1:], ang[:-1]))
        if ph == 0:
            best["n"] = int(d.size)
            best["n_ge_15"] = int((d >= 15.0).sum())
            best["all_s"], best["all_deg"], best["all_px"] = t[1:-1], d, q[1:-1]
        k = int(np.argmax(d))
        if d[k] > best["max_deg"]:
            best["max_deg"] = float(d[k])
            best["at_px"] = q[1 + k].tolist()
    return best


def slope_profile(back_pts, sigma_px):
    p1 = resample_1px(back_pts)
    sm = LA.gaussian_smooth(p1, sigma_px, 1.0)
    ang = LA.tangent_angles(sm)
    return p1, ang


def measure_contour(full, lab, seg, i_c, i_t, F, cfg, deep_sigma_px):
    """候補A・Bと最終輪郭を同じ定義で再測定する。"""
    out = {}
    pts = full
    s = LA.arclength(pts)
    vis = ~np.isin(lab, COMPLETED)
    i_end = int(np.nonzero(vis)[0][-1])
    Hpx = float(F.px_per_H)
    # S1
    c = pts[i_c]
    cp = F.px_to_pct(c[0], c[1])
    spec = F.pct_to_px(38.2, 8.7)
    tol = P(cfg, "plateau_tol_px")
    top = float(pts[:i_t, 1].min())
    run = np.nonzero(pts[:i_t, 1] <= top + tol)[0]
    out["S1"] = {"px": c.tolist(), "pct": [float(cp[0]), float(cp[1])],
                 "dx_pct_h": float(F.px_to_pct_h(c[0] - spec[0])), "dy_pct_h": float(F.px_to_pct_h(c[1] - spec[1])),
                 "plateau_x_px": [float(pts[run, 0].min()), float(pts[run, 0].max())],
                 "plateau_width_pct_h": float(F.px_to_pct_h(pts[run, 0].max() - pts[run, 0].min())),
                 "plateau_centre_left_pct": float((pts[run, 0].min() + pts[run, 0].max()) / 2 / F.width_px * 100)}
    # S2
    p1 = resample_1px(pts[i_t:i_end + 1])
    sm = LA.gaussian_smooth(p1, deep_sigma_px, 1.0)
    kd = int(np.argmin(sm[:, 0]))
    dp = p1[kd]
    dpc = F.px_to_pct(dp[0], dp[1])
    spec2 = F.pct_to_px(39.5, 46.3)
    runx = np.nonzero(p1[:, 0] <= p1[:, 0].min() + tol)[0]
    out["S2"] = {"px": dp.tolist(), "pct": [float(dpc[0]), float(dpc[1])],
                 "dx_pct_h": float(F.px_to_pct_h(dp[0] - spec2[0])), "dy_pct_h": float(F.px_to_pct_h(dp[1] - spec2[1])),
                 "dist_pct_h": float(F.px_to_pct_h(np.hypot(dp[0] - spec2[0], dp[1] - spec2[1]))),
                 "y_range_within_tol_of_leftmost_pct": [float(p1[runx, 1].min() / F.height_px * 100),
                                                        float(p1[runx, 1].max() / F.height_px * 100)]}
    # S4（独自の定義、gw.profile_metrics に対応）: 最初の 5% の弦、2% の弦の最大値、
    # 峰より 8～3% 手前の弦を使う。
    back = pts[:i_c + 1]
    sb = LA.arclength(back)
    h1 = float(F.pct_h_to_px(1.0))

    def chord(a, b):
        q = LA.interp_at(back, sb, np.array([a, b]))
        return float(np.degrees(np.arctan2(-(q[1, 1] - q[0, 1]), q[1, 0] - q[0, 0])))
    tt = np.arange(h1, sb[-1] - h1, 0.25 * h1)
    sl = np.array([chord(t - h1, t + h1) for t in tt])
    k = int(np.argmax(sl))
    qk = LA.interp_at(back, sb, np.array([tt[k]]))[0]
    after = sl[k:]
    rise = float((after - np.minimum.accumulate(after)).max())
    fine_p, fine_a = slope_profile(back, float(F.pct_h_to_px(0.5)))
    coarse_p, coarse_a = slope_profile(back, float(F.pct_h_to_px(3.0)))

    def at_x(pp, aa, x):
        i = int(np.argmin(np.abs(pp[:, 0] - x)))
        return float(aa[i])
    out["S4"] = {"left_end_deg_chord_first_5pct": chord(0.0, 5 * h1),
                 "left_end_deg_chord_first_2pct": chord(0.0, 2 * h1),
                 "mid_max_deg_2pct_chord": float(sl[k]), "mid_max_at_px": qk.tolist(),
                 "mid_max_at_pct": [float(qk[0] / F.width_px * 100), float(qk[1] / F.height_px * 100)],
                 "before_crest_deg_chord_8_to_3pct": chord(sb[-1] - 8 * h1, sb[-1] - 3 * h1),
                 "before_crest_deg_chord_5_to_1pct": chord(sb[-1] - 5 * h1, sb[-1] - 1 * h1),
                 "max_slope_increase_after_steepest_deg": rise,
                 "mid_max_deg_coarse_sigma_3pct": float(coarse_a.max()),
                 "slope_table_coarse_sigma_3pct_deg": {str(x): at_x(coarse_p, coarse_a, x) for x in
                                                        (0, 50, 100, 150, 200, 250, 300, 350, 400, 500, 600, 800, 1000, 1200, 1300, 1400)},
                 "slope_table_fine_sigma_0p5pct_deg": {str(x): at_x(fine_p, fine_a, x) for x in
                                                       (0, 50, 100, 150, 200, 250, 300, 350, 400, 500, 600, 800, 1000, 1200, 1300, 1400)},
                 "_curves": {"fine": (fine_p, fine_a), "coarse": (coarse_p, coarse_a)}}
    # S5
    tip = pts[i_t]
    tpc = F.px_to_pct(tip[0], tip[1])
    tH = F.px_to_H(tip[0], tip[1])
    i_deep_full = i_t + nearest_index(pts[i_t:i_end + 1], dp)
    x_d = dp[0]
    k_cross = i_c + int(np.nonzero(pts[i_c:i_t + 1, 0] >= x_d)[0][0])
    a, b = pts[k_cross - 1], pts[k_cross]
    t = (x_d - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0.0
    top_cross = a + t * (b - a)
    poly = np.vstack([top_cross, pts[k_cross:i_deep_full + 1], [x_d, dp[1]]])
    pa = poly_principal_axis(poly)
    s_t = s[i_t]

    def at(sv):
        return LA.interp_at(pts, s, np.array([sv]))[0]

    def chord_full(a_s, b_s):
        q0, q1 = at(a_s), at(b_s)
        return float(np.degrees(np.arctan2(-(q1[1] - q0[1]), q1[0] - q0[0])))
    alt = {"crest_to_tip": float(np.degrees(np.arctan2(-(tip[1] - c[1]), tip[0] - c[0]))),
           "top_side_chord_2_to_8pctH_before_tip (gw.profile_metrics phi)": chord_full(s_t - 0.08 * Hpx, s_t - 0.02 * Hpx),
           "top_side_chord_last_5pctH": chord_full(s_t - 0.05 * Hpx, s_t),
           "top_side_chord_last_10pctH": chord_full(s_t - 0.10 * Hpx, s_t),
           "top_side_chord_last_20pctH": chord_full(s_t - 0.20 * Hpx, s_t)}
    s6 = F.pct_to_px(59.2, 33.0)
    out["S5"] = {"px": tip.tolist(), "pct": [float(tpc[0]), float(tpc[1])], "H": [float(tH[0]), float(tH[1])],
                 "direction_deg": pa["deg"], "overhang_area_H2": pa["area_px2"] / Hpx ** 2,
                 "overhang_centroid_px": pa["centroid_px"], "overhang_elongation": pa["elongation"],
                 "direction_alternatives_deg": alt,
                 "relative_to_S6_spec_point_pct_h": {"dx": float(F.px_to_pct_h(tip[0] - s6[0])), "dy": float(F.px_to_pct_h(tip[1] - s6[1]))},
                 "overhang_of_body_pct_H": float((tip[0] - c[0]) / Hpx * 100), "_poly": poly}
    # 厚さ。
    th = {}
    under = pts[i_t:i_deep_full + 1]
    for q in (5, 10, 20):
        dlen = q / 100.0 * Hpx
        pa_, pb_ = at(s_t - dlen), at(s_t + dlen)
        th["%d_pct_H" % q] = {"top_px": pa_.tolist(), "under_px": pb_.tolist(),
                              "pair_distance_pct_H": float(np.hypot(*(pa_ - pb_)) / Hpx * 100),
                              "shortest_top_to_underside_pct_H": float(LA.point_to_polyline_dist(pa_[None], under)[0] / Hpx * 100)}
    out["head_thickness"] = th
    # 独自の S8 と先端の旋回角。
    sp = float(F.pct_h_to_px(P(cfg, "own_s8_spacing_pct_h")))
    s8 = {}
    for nm in SEG_NAMES:
        m = np.nonzero((seg == nm) & vis)[0]
        lo, hi = m[0], m[-1]
        if nm != "back":
            lo = max(0, lo - 1)
        r = own_s8(pts[lo:hi + 1], sp)
        s8[nm] = r
    out["S8_own"] = s8
    turn = {}
    for wq in (2.0, 5.0):
        wpx = float(F.pct_h_to_px(wq))
        d0 = chord_full(s_t - wpx - sp, s_t - wpx)
        d1 = chord_full(s_t + wpx, s_t + wpx + sp)
        turn["window_pm_%gpct_h" % wq] = float((d0 - d1) % 360.0)
    out["tip_turn_clockwise_deg"] = turn
    # 長さとフラグ。
    ln = {}
    for nm in SEG_NAMES:
        m = np.nonzero(seg == nm)[0]
        lo, hi = (m[0] if nm == "back" else m[0] - 1), m[-1]
        L = float(s[hi] - s[lo])
        l_seg = lab[m]
        ln[nm] = {"n_points": int(m.size + (0 if nm == "back" else 1)), "length_px": L,
                  "length_pct_h": float(F.px_to_pct_h(L)), "length_H": L / Hpx,
                  "counts": {k2: int((l_seg == k2).sum()) for k2 in sorted(set(l_seg.tolist()))},
                  "share_in_S7_false": float(np.isin(l_seg, COMPLETED).mean())}
    out["segments"] = ln
    out["_deep_index_full"] = i_deep_full
    return out


def lowpass_diagnostic(full, lab, seg, i_c, i_t, F, cfg):
    vis = ~np.isin(lab, COMPLETED)
    i_end = int(np.nonzero(vis)[0][-1])
    base = full[:i_end + 1]
    p1 = resample_1px(base)
    s1 = LA.arclength(p1)
    s_full = LA.arclength(base)
    sp = float(F.pct_h_to_px(1.0))
    rows, curves = [], {}
    for sg in P(cfg, "lowpass_sigmas_pct_h"):
        sm = LA.gaussian_smooth(p1, float(F.pct_h_to_px(sg)), 1.0)
        row = {"sigma_pct_h": sg}
        # 平滑化した曲線について各区間の独自 S8 を測る（区間の境界は基準特徴点の弧長）。
        lim = {"back": (0.0, s_full[i_c]), "head": (s_full[i_c], s_full[i_t]), "inner_arc": (s_full[i_t], s_full[i_end])}
        for nm in SEG_NAMES:
            a, b = lim[nm]
            ka, kb = int(round(a)), int(round(b))
            r = own_s8(sm[ka:kb + 1], sp)
            d = LA.point_to_polyline_dist(base[(seg[:i_end + 1] == nm)], sm)
            st = stats_pct(d, F)
            row[nm] = {"own_s8_max_deg": r["max_deg"], "n_ge_15": r["n_ge_15"], "n": r["n"],
                       "dev_mean_pct_h": st["mean"], "dev_p95_pct_h": st["p95"], "dev_max_pct_h": st["max"]}
        k_tip = int(np.argmax(sm[int(s_full[i_c]):int(s_full[i_end]) + 1, 0])) + int(s_full[i_c])
        row["tip_shift_pct_h"] = [float(F.px_to_pct_h(sm[k_tip, 0] - full[i_t, 0])), float(F.px_to_pct_h(sm[k_tip, 1] - full[i_t, 1]))]
        rows.append(row)
        curves[sg] = sm
    return rows, curves


# ====================================================================== 描画
COL = {"back": "red", "head": "magenta", "inner_arc": "lime", "claw_root_bridge": "orange",
       "completed_occluded": "cyan", "completed_other": "blue"}


def offset_dash(width):
    """構成した区間（offset_from_visible_edge）を示す短い破線パターン。

    区間の色を使い、どの線幅でも読み取れる長さにする。
    """
    return (max(5.0, 3.0 * width), max(4.0, 2.5 * width))


def draw_final(img, tf, C, width=2.0, alt_back=None):
    if alt_back is not None:
        draw.polyline(img, tf(alt_back), "purple", max(1.0, width * 0.75), dash=(8, 6))
    for nm in SEG_NAMES:
        sg = C["segs"][nm]
        pts, lab = sg["pts"], sg["lab"]
        i = 0
        while i < len(pts):
            j = i
            while j + 1 < len(pts) and lab[j + 1] == lab[i]:
                j += 1
            k = min(j + 1, len(pts) - 1)
            l_ = lab[i]
            if l_ == "traced":
                draw.polyline(img, tf(pts[i:k + 1]), COL[nm], width)
            elif l_ == OFFSET_FLAG:                                     # constructed stretch: segment colour, short dashes
                draw.polyline(img, tf(pts[i:k + 1]), COL[nm], width, dash=offset_dash(width))
            elif l_ == "claw_root_bridge":
                draw.polyline(img, tf(pts[i:k + 1]), COL["claw_root_bridge"], width)
            else:
                draw.polyline(img, tf(pts[i:k + 1]), COL[l_], width, dash=(10, 6))
            i = j + 1


def draw_landmarks(img, tf, C, F, scale=1, labels=True):
    z0 = F.pct_to_px(0, 74.7)[1]
    for name, pct in (("S1 spec", (38.2, 8.7)), ("S2 spec", (39.5, 46.3)), ("S6 spec", (59.2, 33.0))):
        p = tf(np.array(F.pct_to_px(*pct), np.float64))
        if labels:
            draw.label_point(img, p, name, "navy", scale=scale, offset=(10, 10), kind="x", size=5 + 2 * scale)
        else:
            draw.marker(img, p, "x", 5 + 2 * scale, "navy", 2, outline="white")
    for name, p in (("crest", C["crest_px"]), ("head tip", C["tip_px"]), ("inner deepest", C["deep_px"])):
        q = tf(np.asarray(p, np.float64))
        if labels:
            draw.label_point(img, q, name, "black", scale=scale, offset=(10, -14), kind="O", size=4 + 2 * scale)
        else:
            draw.marker(img, q, "O", 4 + 2 * scale, "black", 2, outline="white")
    return z0


def legend(img, x, y, scale=2, extra=None):
    items = [("back (traced)", COL["back"]), ("back: offset_from_visible_edge (constructed, short dashes)", COL["back"], offset_dash(3.0)),
             ("head (traced)", COL["head"]), ("inner_arc (traced)", COL["inner_arc"]),
             ("claw_root_bridge (ball-smoothed)", COL["claw_root_bridge"]), ("completed_occluded (dashed)", COL["completed_occluded"]),
             ("completed_other (dashed)", COL["completed_other"])] + (extra or [])
    w = max(draw.text_size(it[0], scale)[0] for it in items) + 60
    h = 11 * scale * len(items) + 10
    draw.rect(img, x, y, x + w, y + h, "white", fill=True, alpha=0.85)
    for k, it in enumerate(items):
        t, c = it[0], it[1]
        yy = y + 6 + k * 11 * scale
        draw.line(img, (x + 6, yy + 4 * scale), (x + 40, yy + 4 * scale), c, 3, dash=(it[2] if len(it) > 2 else None))
        draw.text(img, x + 48, yy, t, "black", scale=scale)


def save_crop(path, rgb, C, F, box, scale, title, alt_back=None, extra_lines=None, landmarks=True, width=1.6):
    x0, y0, x1, y1 = box
    v = draw.View(rgb, x0, y0, x1, y1, scale=scale, method="bilinear")
    if extra_lines:
        for pts, col, wd, dash in extra_lines:
            draw.polyline(v.img, v.to_view(pts), col, wd, dash=dash)
    if C is not None:
        draw_final(v.img, v.to_view, C, width=width, alt_back=alt_back)
        if landmarks:
            draw_landmarks(v.img, v.to_view, C, F, scale=2)
    draw.text(v.img, 4, 4, "%s  x %d..%d  y %d..%d  zoom %g" % (title, x0, x1, y0, y1, scale), "black", scale=2, bg="white")
    imgio.save_png(path, v.img)
    return v.img.shape


# ====================================================================== 主処理
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(HERE, "base_contour_params.json"))
    ap.add_argument("--tag", default="")
    args = bootstrap.parse_args(ap)
    cfg = paths.read_json(args.params)
    F = frame.get_frame()
    official = not args.tag
    out_dir = paths.ensure_dir(os.path.join(paths.STEP1_DIR, "contour_final") if official else
                               os.path.join(paths.STEP1_DIR, "contour_final", "variant_" + args.tag))
    # 正式な出力先は2026-09-20の大形状の判断で変更した。この処理は指先規模の参照輪郭を作る。
    # target/base_contour.json と target/base_contour_overlay.png は現在
    # src/contour/build_large_form.py が作るため、ここでは書き込まない。
    json_path = os.path.join(paths.TARGET_DIR, "base_contour_finger_scale.json") if official else os.path.join(out_dir, "base_contour.json")
    overlay_path = os.path.join(out_dir, "base_contour_finger_scale_overlay.png") if official else os.path.join(out_dir, "base_contour_overlay.png")
    log("BUILD params =", paths.norm(args.params), "| official =", official)

    # ---------------------------------------------------------------- 入力
    rgb = imgio.load_painting_rgb()
    probe = EdgeProbe(rgb)
    cands, hashes, warn = {}, {}, []
    for k, rel in P(cfg, "candidate_files").items():
        pth = paths.require_file(os.path.join(paths.PROJECT_ROOT, rel))
        cands[k] = load_candidate(pth)
        hashes[k] = sha256_of(pth)
        exp = P(cfg, "candidate_sha256_expected").get(k, "")
        if exp and not hashes[k].startswith(exp.upper()):
            warn.append("candidate %s hash %s... differs from the judged one (%s...)" % (k, hashes[k][:8], exp))
            log("BUILD WARNING", warn[-1])
    A, B = cands["A"], cands["B"]

    # ---------------------------------------------------------------- 1. 比較
    cmp_ = compare_candidates(A, B, F, cfg)
    for nm in SEG_NAMES:
        e = cmp_["per_segment"][nm]
        log("CMP %-9s A->B visible mean %.3f p95 %.3f max %.3f | B->A mean %.3f p95 %.3f max %.3f  [%% of image height]" % (
            nm, e["A_to_B_visible"]["mean"], e["A_to_B_visible"]["p95"], e["A_to_B_visible"]["max"],
            e["B_to_A_visible"]["mean"], e["B_to_A_visible"]["p95"], e["B_to_A_visible"]["max"]))
    for st in cmp_["stretches"]:
        log("CMP stretch on %s %-9s (%.0f,%.0f)->(%.0f,%.0f) len %.0f px max %.2f %% verdict %s" % (
            st["on"], st["segment"], st["from_px"][0], st["from_px"][1], st["to_px"][0], st["to_px"][1],
            st["length_px"], st["max_dist_pct_h"], ",".join(st["verdict_ids"]) or "NONE"))

    # ---------------------------------------------------------------- 2. 最終輪郭と別の読み取り方
    variant = P(cfg, "back_left_variant")
    other_variant = [v for v in cfg["back_left_variant"]["allowed"] if v != variant][0]
    C = build_contour(variant, cands, probe, cfg, F)
    C_other = build_contour(other_variant, cands, probe, cfg, F)
    # 構成した左端（フラグ OFFSET_FLAG）の X 範囲は、保留中の back_left_variant の判断に依存する。
    # white_body_outline 輪郭上で測定し、両方の読み取り方に記録する（ラベルとメタデータのみ）。
    pending_x = None
    _pend = cfg.get(PENDING_KEY)                          # parameter file entry; older parameter files do not have it -> still pending
    pending_list = [str(v) for v in (_pend["value"] if isinstance(_pend, dict) and "value" in _pend else [PENDING_LEFT_END])]
    for Cx_ in (C, C_other):
        bk = Cx_["segs"]["back"]
        m_off = np.asarray(bk["lab"], dtype=object) == OFFSET_FLAG
        if m_off.any():
            pending_x = [float(bk["pts"][m_off, 0].min()), float(bk["pts"][m_off, 0].max())]
            log("FLAGS %s: %d back points flagged %s, x %.3f .. %.3f px, last one at index %d (%.3f, %.3f)" % (
                Cx_["variant"], int(m_off.sum()), OFFSET_FLAG, pending_x[0], pending_x[1], int(np.nonzero(m_off)[0][-1]),
                bk["pts"][np.nonzero(m_off)[0][-1], 0], bk["pts"][np.nonzero(m_off)[0][-1], 1]))
    full, lab, seg = full_polyline(C)
    n_back = len(C["segs"]["back"]["pts"])
    n_head = len(C["segs"]["head"]["pts"])
    i_c, i_t = n_back - 1, n_back + n_head - 2
    log("FINAL variant %s | crest (%.1f, %.1f) tip (%.1f, %.1f) deepest (%.1f, %.1f)" % (
        variant, C["crest_px"][0], C["crest_px"][1], C["tip_px"][0], C["tip_px"][1], C["deep_px"][0], C["deep_px"][1]))
    if "left_end" in C["info"]:
        li = C["info"]["left_end"]
        log("FINAL left end: line width median %.2f px (p05 %.2f p95 %.2f n %d), offset %.2f px, frame edge y %.1f, seam normal step %.2f px" % (
            li["line_width_px"]["median"], li["line_width_px"]["p05"], li["line_width_px"]["p95"], li["line_width_px"]["n"],
            li["outward_offset_px"], li["left_frame_edge_px"][1], li["seam"]["normal_step_px"]))

    # ---------------------------------------------------------------- 3. 測定
    sig_px = float(F.pct_h_to_px(P(cfg, "landmark_sigma_pct_h")))
    M = {"final": measure_contour(full, lab, seg, i_c, i_t, F, cfg, sig_px)}
    fo, lo_, so = full_polyline(C_other)
    nbo, nho = len(C_other["segs"]["back"]["pts"]), len(C_other["segs"]["head"]["pts"])
    M["final_other_reading"] = measure_contour(fo, lo_, so, nbo - 1, nbo + nho - 2, F, cfg, sig_px)
    for k in ("A", "B"):
        cd = cands[k]
        # 峰はすべて同じ定義で求める（平滑化した写しの y の最小値）。
        p1 = resample_1px(cd["pts"][:cd["i_tip"] + 1])
        smc = LA.gaussian_smooth(p1, sig_px, 1.0)
        c_pt = p1[int(np.argmin(smc[:, 1]))]
        ic = nearest_index(cd["pts"][:cd["i_tip"] + 1], c_pt)
        M[k] = measure_contour(cd["pts"], cd["src"], cd["seg"], ic, cd["i_tip"], F, cfg, sig_px)
    s6 = measure_s6(rgb, cfg, probe)
    sea = measure_sea_top(probe, cfg)
    crest_y = M["final"]["S1"]["px"][1]
    s3 = {"spec": {"trough_top_pct": 74.7, "height_pct_h": 66.0},
          "visible_sea_top_edge": sea,
          "visible_sea_top_edge_top_pct": sea["median_y_px"] / F.height_px * 100,
          "height_pct_h_if_that_edge_were_the_trough": (sea["median_y_px"] - crest_y) / F.height_px * 100,
          "height_pct_h_with_frame_Z0": (F.pct_to_px(0, 74.7)[1] - crest_y) / F.height_px * 100}
    s3["diff_pct_h_if_that_edge_were_the_trough"] = s3["height_pct_h_if_that_edge_were_the_trough"] - 66.0
    s3["diff_pct_h_with_frame_Z0"] = s3["height_pct_h_with_frame_Z0"] - 66.0
    s6spec = F.pct_to_px(59.2, 33.0)
    s6m = None
    if s6:
        cpx = M["final"]["S1"]["px"]
        s6m = dict(s6)
        s6m["pct"] = [s6["px"][0] / F.width_px * 100, s6["px"][1] / F.height_px * 100]
        s6m["dx_pct_h"] = float(F.px_to_pct_h(s6["px"][0] - s6spec[0]))
        s6m["dy_pct_h"] = float(F.px_to_pct_h(s6["px"][1] - s6spec[1]))
        s6m["overhang_pct_H_from_final_crest"] = (s6["px"][0] - cpx[0]) / F.px_per_H * 100
        s6m["direction_from_final_crest_deg"] = float(np.degrees(np.arctan2(-(s6["px"][1] - cpx[1]), s6["px"][0] - cpx[0])))
        s6m["final_head_tip_is_left_of_it_by_pct_h"] = float(F.px_to_pct_h(s6["px"][0] - C["tip_px"][0]))

    # 独立した縁の検査。traced の点を3点おきに調べる。構成した左端 OFFSET_FLAG も
    # ラベル変更前と同じ3点おきの選択に含め、見える本体の縁と照合する（下の m_left）。
    nrm, _ = left_normals(full)
    edge = {}
    for nm in SEG_NAMES:
        m = np.nonzero((seg == nm) & np.isin(lab, ON_LINE_FLAGS))[0][::3]
        if "left_end" in C["info"] and nm == "back":
            n_left = C["info"]["left_end"]["n_points_left_end"]                # candidate points are 2 px apart too
            m_left = m[m < n_left - 25]
            m = m[m >= n_left + 25]
            w = C["info"]["left_end"]["outward_offset_px"]
            ui = probe.inner_only(full[m_left], nrm[m_left], w)
            edge["back_left_end_visible_body_edge_minus_expected"] = q_stats(ui + w)
        uo, _, used = probe.outer_inner(full[m], nrm[m])
        edge[nm] = dict(q_stats(uo), n_tried=int(m.size), n_luma=int((used == 1).sum()), n_rb=int((used == 2).sum()))
    for k in ("A", "B"):
        cd = cands[k]
        nk, _ = left_normals(cd["pts"])
        for nm in SEG_NAMES:
            m = np.nonzero((cd["seg"] == nm) & (cd["src"] == "traced"))[0][::3]
            uo, _, _ = probe.outer_inner(cd["pts"][m], nk[m])
            edge["%s_%s" % (k, nm)] = q_stats(uo)
    for nm in SEG_NAMES:
        e = edge[nm]
        log("EDGE final %-9s n %d median %+.2f p05 %+.2f p95 %+.2f px (+ = true edge further out)" % (nm, e["n"], e["median"], e["p05"], e["p95"]))
    if "back_left_end_visible_body_edge_minus_expected" in edge:
        e = edge["back_left_end_visible_body_edge_minus_expected"]
        log("EDGE final left end (visible body edge vs expected) n %d median %+.2f p05 %+.2f p95 %+.2f px" % (e["n"], e["median"], e["p05"], e["p95"]))

    # 最終輪郭と候補間の距離。
    dist_final = {}
    for k in ("A", "B"):
        d = LA.point_to_polyline_dist(full, cands[k]["pts"])
        dist_final[k] = {nm: stats_pct(d[(seg == nm) & ~np.isin(lab, COMPLETED)], F) for nm in SEG_NAMES}
        dist_final[k]["_d"] = d
    lp_rows, lp_curves = lowpass_diagnostic(full, lab, seg, i_c, i_t, F, cfg)

    # テスト担当側の測定ライブラリで互換性を検査する。失敗は報告するが処理は続ける。
    lib = {"ok": False}
    # JSON を書き込んだ後に埋める。

    # ---------------------------------------------------------------- 4. JSON
    def seg_json(Cx, nm):
        sg = Cx["segs"][nm]
        ptsH = np.round(F.pts_px_to_H(sg["pts"]), 6)
        org_runs = []
        i = 0
        while i < len(sg["org"]):
            j = i
            while j + 1 < len(sg["org"]) and sg["org"][j + 1] == sg["org"][i]:
                j += 1
            org_runs.append({"from_index": i, "to_index": j, "origin": str(sg["org"][i])})
            i = j + 1
        return {"name": nm, "jp": SEG_JP[nm], "points_px": [[float(a), float(b)] for a, b in sg["pts"]],
                "points_H": [[float(a), float(b)] for a, b in ptsH], "source": [str(v) for v in sg["lab"]],
                "in_S7": [bool(v not in COMPLETED) for v in sg["lab"]],
                "actual_spacing_px": round(sg["actual_spacing_px"], 6), "origin_runs": org_runs}

    def lm_json(p):
        h = F.px_to_H(p[0], p[1])
        pc = F.px_to_pct(p[0], p[1])
        return {"px": [float(p[0]), float(p[1])], "H": [round(float(h[0]), 6), round(float(h[1]), 6)],
                "pct": [round(float(pc[0]), 3), round(float(pc[1]), 3)]}

    def strip(d):
        if isinstance(d, dict):
            return {k: strip(v) for k, v in d.items() if not k.startswith("_")}
        if isinstance(d, (list, tuple)):
            return [strip(v) for v in d]
        if isinstance(d, np.ndarray):
            return d.tolist()
        if isinstance(d, (np.floating, np.integer)):
            return d.item()
        return d

    def contour_json(Cx, Mx, is_official_variant):
        m = Mx
        z0 = float(F.pct_to_px(0, 74.7)[1])
        spec4 = {"left_end": 25.0, "mid_max": 47.0, "before_crest": 8.0}
        exceed = []
        if abs(m["S1"]["dx_pct_h"]) > 1 or abs(m["S1"]["dy_pct_h"]) > 1:
            exceed.append("S1")
        if m["S2"]["dist_pct_h"] > 1:
            exceed.append("S2")
        exceed.append("S3 (visible sea top edge 1.6 % above the spec trough level; NOT a reliable trough measurement)")
        if s6m and (abs(s6m["dx_pct_h"]) > 1 or abs(s6m["dy_pct_h"]) > 1):
            exceed.append("S6")
        flags_present = sorted(set(str(v) for nm in SEG_NAMES for v in Cx["segs"][nm]["lab"]))
        pend_txt = ", pending user confirmation" if PENDING_LEFT_END in pending_list else ""
        if Cx["variant"] == "white_body_outline":
            left_text = ("below the fork of the back's outline at (337, 894) NO ink line is drawn: there the line is CONSTRUCTED = the visible "
                         "white-body edge shifted outwards by the measured ink-line width (white_body_outline reading, flag "
                         "offset_from_visible_edge%s)" % pend_txt)
        else:
            left_text = ("left of the fork of the back's outline at (337, 894) the upper branch (top edge of the dark-blue band) is followed "
                         "(sky_silhouette reading, traced%s)" % pend_txt)
        J = {
            "schema": "gw.base_contour.v1",
            "official": bool(is_official_variant),
            "built_by": "src/contour/build_base_contour.py (judge / merge of candidates A and B)",
            "variant": {"back_left_variant": Cx["variant"], "note": "NEEDS USER CONFIRMATION - see docs/base_contour_report.md section 1"},
            PENDING_KEY: list(pending_list),
            PENDING_STRETCHES_KEY: ({PENDING_LEFT_END: pending_left_end(Cx["segs"]["back"]["pts"], Cx["segs"]["back"]["lab"], pending_x, F,
                                                                        "flag %s of the white_body_outline contour built in the same run" % OFFSET_FLAG)}
                                    if (pending_x and PENDING_LEFT_END in pending_list) else {}),
            "image": {"path": paths.painting_path(), "width": F.width_px, "height": F.height_px},
            "frame": {"crest_left_pct": F.crest_left_pct, "crest_top_pct": F.crest_top_pct, "height_pct": F.height_pct,
                      "frame_h_H": round(F.frame_h, 6), "frame_w_H": round(F.frame_w, 6),
                      "x_left_H": round(F.x_left, 6), "z_top_H": round(F.z_top, 6)},
            "order": "left frame edge -> crest -> head tip -> inner arc -> trough",
            "sample_spacing_px": P(cfg, "sample_spacing_px"),
            "contour_definition": "outer (sky-side) edge of the ink outline of the great wave at the half level between sky and ink; "
                                  "claws and spray removed at finger scale (rolling ball R = 40 px from the body side), every stretch the "
                                  "ball changed is bridged by the chord between its two end points (flag claw_root_bridge = ball-smoothed; "
                                  "not every run is a claw root, see source_flags); " + left_text + "; hidden part completed by a tangent-continuous "
                                  "parabola to Z = 0 (in_S7 = false)",
            "source_flags": {k: SOURCE_FLAG_TEXT[k] for k in SOURCE_FLAG_TEXT if k in flags_present},
            "segments": [seg_json(Cx, nm) for nm in SEG_NAMES],
            "landmarks": {
                "crest": dict(lm_json(Cx["crest_px"]), definition="highest point of the base contour: argmin(y) of a copy smoothed with sigma = %g %% of image height (flat top, see remeasure.S1)" % P(cfg, "landmark_sigma_pct_h"),
                              strict_highest_px=Cx["lm"]["crest_strict_px"], plateau_x_px=Cx["lm"]["crest_plateau_x_px"]),
                "head_tip": dict(lm_json(Cx["tip_px"]), direction_deg=round(m["S5"]["direction_deg"], 2),
                                 direction_definition="principal axis (largest second moment of area, exact polygon moments) of the OVERHANG = area enclosed by the base contour on the boat side of the plumb line through the inner-arc deepest point (top side -> head tip -> underside -> inner arc down to the deepest point, closed by that plumb line); 0 deg = +X, negative = pointing below the horizontal. Same definition as both candidates (A: -46.2, B: -45.8). Local definitions are unstable on the blunt, lobed head: see direction_alternatives_deg; the test library's phi (top-side chord 2..8 % H before the tip) is one of them.",
                                 direction_alternatives_deg={k: round(v, 2) for k, v in m["S5"]["direction_alternatives_deg"].items()}),
                "inner_deepest": dict(lm_json(Cx["deep_px"]), definition="left-most point of the visible inner arc: argmin(x) of the smoothed copy (near-vertical run, see remeasure.S2)",
                                      strict_leftmost_px=Cx["lm"]["deep_strict_px"], run_y_px=Cx["lm"]["deep_run_y_px"]),
                "trough_level": {"y_px": round(z0, 3), "top_pct": 74.7,
                                 "note": "Z = 0 of the frame definition (crest_top_pct + height_pct). NOT measurable in the painting: the trough under the head is hidden by the near wave; the top edge of the visible sea patch right of the near wave was measured at %.2f %% from the top (candidate B estimates the lower end of that patch at about 76.7 %%), so 74.7 %% lies inside the patch but on no drawn feature" % s3["visible_sea_top_edge_top_pct"]},
                "claw_rightmost": (dict(lm_json(s6m["px"]), how=s6m["how"]) if s6m else None),
                "inner_arc_visible_end": lm_json(Cx["p1"][Cx["lm"]["i_vis_end"]]),
                "completion_end": lm_json(Cx["segs"]["inner_arc"]["pts"][-1]),
            },
            "remeasure": {
                "S1": {"spec_pct": [38.2, 8.7], "measured_pct": [round(v, 3) for v in m["S1"]["pct"]], "measured_px": m["S1"]["px"],
                       "diff_pct_h": {"dx": round(m["S1"]["dx_pct_h"], 3), "dy_down_positive": round(m["S1"]["dy_pct_h"], 3)},
                       "plateau_x_px": m["S1"]["plateau_x_px"], "plateau_width_pct_h": round(m["S1"]["plateau_width_pct_h"], 3),
                       "plateau_centre_left_pct": round(m["S1"]["plateau_centre_left_pct"], 3),
                       "how": "argmin(y) of the base contour smoothed with sigma 0.5 % of image height; plateau = contour within 2 px of the top row"},
                "S2": {"spec_pct": [39.5, 46.3], "measured_pct": [round(v, 3) for v in m["S2"]["pct"]], "measured_px": m["S2"]["px"],
                       "diff_pct_h": {"dx": round(m["S2"]["dx_pct_h"], 3), "dy_down_positive": round(m["S2"]["dy_pct_h"], 3), "dist": round(m["S2"]["dist_pct_h"], 3)},
                       "y_range_within_2px_of_leftmost_pct": [round(v, 3) for v in m["S2"]["y_range_within_tol_of_leftmost_pct"]],
                       "how": "argmin(x) of the smoothed visible inner arc (sky / belly boundary, outer edge of its ink line)"},
                "S3": dict(strip(s3), reliable=False,
                           how="The trough is hidden; only the top edge of the visible dark sea patch can be measured (first run of >= 6 px with R-B < -8 below y = 1750 in every column of s3_sea_columns_px). The frame keeps Z = 0 at 74.7 %."),
                "S4": {"spec_deg": spec4,
                       "measured_deg": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in strip(m["S4"]).items()},
                       "diff_deg": {"left_end(chord first 5 %)": round(m["S4"]["left_end_deg_chord_first_5pct"] - 25.0, 2),
                                    "mid_max(2 % chord)": round(m["S4"]["mid_max_deg_2pct_chord"] - 47.0, 2),
                                    "before_crest(chord 8..3 %)": round(m["S4"]["before_crest_deg_chord_8_to_3pct"] - 8.0, 2)},
                       "how": "chord directions on the back segment (arclength windows in % of image height), same windows as gw.profile_metrics; angles cannot be expressed in % of image height"},
                "S5": strip({k: v for k, v in m["S5"].items()}),
                "S6": (strip(s6m) if s6m else None),
                "items_differing_from_spec_by_more_than_1pct_of_image_height": exceed,
            },
            "head_thickness_claws_removed": strip(m["head_thickness"]),
            "own_S8": {nm: {"max_deg": round(m["S8_own"][nm]["max_deg"], 2), "n_samples": m["S8_own"][nm]["n"],
                            "n_ge_15_deg": m["S8_own"][nm]["n_ge_15"], "max_at_px": m["S8_own"][nm]["at_px"]} for nm in SEG_NAMES},
            "tip_turn_clockwise_deg": strip(m["tip_turn_clockwise_deg"]),
            "segment_summary": strip(m["segments"]),
            "doubt_zones": P(cfg, "doubt_zones"),
            "provenance": {"candidate_sha256": hashes, "params_file": paths.norm(args.params),
                           "build_info": strip(Cx["info"]), "warnings": warn},
        }
        return J

    J = contour_json(C, M["final"], True)
    paths.write_json(json_path, J)
    J_other = contour_json(C_other, M["final_other_reading"], False)
    other_path = os.path.join(out_dir, "base_contour_alt_%s.json" % other_variant)
    paths.write_json(other_path, J_other)
    log("WROTE", paths.norm(json_path), "sha256", sha256_of(json_path)[:16])
    log("WROTE", paths.norm(other_path))

    # 測定ライブラリとの互換性。
    try:
        from gw import profile_metrics as PM
        bc = PM.load_base_contour(json_path)
        mm = PM.measure_base_contour(bc)
        lib = {"ok": True, "phi_deg": mm.get("phi_deg"), "theta": mm.get("theta"), "o_H": mm.get("o"), "h_H": mm.get("h"),
               "S4": {k: v for k, v in mm["S4"].items() if k != "slope_curve"}, "S8": mm["S8"],
               "landmarks_H": {k: (v["H"] if isinstance(v, dict) and "H" in v else None) for k, v in mm["landmarks"].items()},
               "notes": mm.get("notes")}
        log("LIB measure_base_contour ok: phi %.1f  S8 judged max %.1f (unexcluded %.1f)  S4 left %.1f mid %.1f before-crest %.1f" % (
            mm["phi_deg"], mm["S8"]["max_tangent_diff_deg"], mm["S8"]["max_unexcluded_deg"],
            mm["S4"]["left_end_deg"], mm["S4"]["mid_max_deg"], mm["S4"]["before_crest_deg"]))
    except Exception as ex:                                        # shared code of another agent: report, do not fail
        lib = {"ok": False, "error": repr(ex)}
        log("LIB measure_base_contour FAILED:", repr(ex))

    # テストライブラリ独自の定義で S7 と S8 の両立性を調べる。仮のモデル輪郭として、
    # 補完部分を含む基準輪郭に sigma の低域通過を適用する。先端領域を除いて S8 を、
    # 基準輪郭に対して S7 を判定する。
    lib_lowpass = []
    try:
        from gw import profile_metrics as PM
        bc = PM.load_base_contour(json_path)
        pf1 = resample_1px(full)
        for sgm in P(cfg, "lowpass_sigmas_pct_h"):
            smf = LA.gaussian_smooth(pf1, float(F.pct_h_to_px(sgm)), 1.0)
            smH = F.pts_px_to_H(smf[::2])
            mm_ = PM.measure_profile(smH)
            s7_ = PM.s7_deviation(smH, bc, model_metrics=mm_)
            row = {"sigma_pct_h": sgm, "S8_judged_max_deg": mm_["S8"]["max_tangent_diff_deg"],
                   "S8_per_segment_deg": mm_["S8"]["per_segment"], "S8_max_unexcluded_deg": mm_["S8"]["max_unexcluded_deg"],
                   "S8_judged_max_at_px": ([float(v) for v in F.H_to_px(*mm_["S8"]["max_at"]["H"])] if mm_["S8"].get("max_at") else None),
                   "S8_judged_max_in_segment": (mm_["S8"]["max_at"]["segment"] if mm_["S8"].get("max_at") else None),
                   "tip_turn_deg": mm_["S8"]["tip_turn_deg"], "phi_deg": mm_.get("phi_deg"),
                   "head_tip_H": (mm_["landmarks"]["head_tip"] or {}).get("H"),
                   "S7": {nm: ({"mean": s7_[nm]["mean_dev_pct_h"], "p95": s7_[nm]["p95_dev_pct_h"]} if s7_.get(nm) else None) for nm in SEG_NAMES}}
            tipH = row["head_tip_H"]
            if tipH:
                tp = F.H_to_px(tipH[0], tipH[1])
                row["S5_pos_dist_pct_h"] = float(F.px_to_pct_h(np.hypot(float(tp[0]) - C["tip_px"][0], float(tp[1]) - C["tip_px"][1])))
            lib_lowpass.append(row)
            log("LIBLOWPASS sigma %.1f %%: S8 judged %.1f deg %s | S7 mean/p95 " % (sgm, row["S8_judged_max_deg"], {k: round(v, 1) for k, v in row["S8_per_segment_deg"].items()})
                + " ".join("%s %.2f/%.2f" % (nm, row["S7"][nm]["mean"], row["S7"][nm]["p95"]) for nm in SEG_NAMES if row["S7"][nm])
                + " | tip shift %.2f %% phi %.1f | S8 max at %s" % (row.get("S5_pos_dist_pct_h", float("nan")), row["phi_deg"] if row["phi_deg"] is not None else float("nan"),
                                                                 [round(v) for v in row["S8_judged_max_at_px"]] if row["S8_judged_max_at_px"] else None))
    except Exception as ex:
        lib_lowpass = [{"error": repr(ex)}]
        log("LIBLOWPASS FAILED:", repr(ex))

    # ---------------------------------------------------------------- 5. 画像
    alt_back = C_other["segs"]["back"]["pts"][:260]
    pA, pB = A["pts"], B["pts"]
    sA = LA.arclength(pA)
    # 5a 比較の重ね画像と距離グラフ。
    box = (0, 0, 2700, 2100)
    v = draw.View(rgb, *box, scale=1600.0 / 2700.0)
    draw.polyline(v.img, v.to_view(pA), "red", 2.0)
    draw.polyline(v.img, v.to_view(pB), (0, 170, 0), 1.2)
    for vd in P(cfg, "verdicts"):
        bb = vd["bbox_px"]
        q0, q1 = v.to_view(np.array([bb[0], bb[1]], float)), v.to_view(np.array([bb[2], bb[3]], float))
        draw.rect(v.img, q0[0], q0[1], q1[0], q1[1], "blue", 2)
        draw.text(v.img, q1[0] + 3, q0[1], vd["id"].split("_")[0], "blue", scale=2, bg="white")
    draw.text(v.img, 4, 4, "candidate A = red (wide), candidate B = green (thin), blue boxes = stretches differing > 0.5 % (verdict ids)", "black", scale=2, bg="white")
    imgio.save_png(os.path.join(out_dir, "compare_ab_1600.png"), v.img)
    spans, acc = [], 0.0
    for nm, colr in (("back", "red"), ("head", "magenta"), ("inner_arc", "lime")):
        m = np.nonzero(A["seg"] == nm)[0]
        spans.append({"x0": float(F.px_to_pct_h(sA[m[0]])), "x1": float(F.px_to_pct_h(sA[m[-1]])), "label": nm, "color": colr, "alpha": 0.10})
    sBn = LA.arclength(pB)
    # 最近接の A 点を使い、B を A の弧長軸に対応付ける。
    idxB = np.array([nearest_index(pA, q) for q in pB[::2]])
    pl = plot.line_plot([{"label": "A -> B", "x": F.px_to_pct_h(sA), "y": F.px_to_pct_h(cmp_["dA"]), "color": "red"},
                         {"label": "B -> A", "x": F.px_to_pct_h(sA[idxB]), "y": F.px_to_pct_h(cmp_["dB"][::2]), "color": "green", "line": False, "marker": "o", "marker_size": 1}],
                        title="distance between candidate A and candidate B along the contour", xlabel="arclength of A from the left frame edge [% of image height]",
                        ylabel="distance [% of image height]", size=(1600, 560), ylim=(0, 4.0), spans=spans,
                        hlines=[{"y": 0.5, "label": "0.5 judge threshold", "color": "blue"}])
    imgio.save_png(os.path.join(out_dir, "compare_ab_distance_plot.png"), pl)
    # 5b 判定用の切出し画像。
    for vd in P(cfg, "verdicts"):
        bb = vd["bbox_px"]
        mx = 60 if (bb[2] - bb[0]) < 300 else 40
        cx0, cy0, cx1, cy1 = max(0, bb[0] - mx), max(0, bb[1] - mx), bb[2] + mx, bb[3] + mx
        sc = min(8.0, 1500.0 / (cx1 - cx0))
        fullC = full
        save_crop(os.path.join(out_dir, "judge_%s.png" % vd["id"]), rgb, None, F, (cx0, cy0, cx1, cy1), sc,
                  "%s use=%s | yellow halo = FINAL, red = A, green = B" % (vd["id"], vd["use"]),
                  extra_lines=[(fullC, "yellow", 6.0, None), (pA, "red", 1.6, None), (pB, (0, 170, 0), 1.6, None)])
    # 5c 最終輪郭の重ね画像。
    ov = rgb.copy()
    draw_final(ov, lambda q: q, C, width=4.0, alt_back=alt_back)
    z0 = draw_landmarks(ov, lambda q: q, C, F, scale=3)
    draw.hline(ov, z0, "orange", 2.0, dash=(16, 10))
    draw.text(ov, 10, z0 + 6, "Z = 0 (74.7 % from top, frame definition - not measurable in the painting)", "orange", scale=3, bg="white")
    imgio.save_png(os.path.join(out_dir, "overlay_full_res.png"), ov)
    sc = 1600.0 / F.width_px
    v = draw.View(rgb, 0, 0, F.width_px, F.height_px, scale=sc)
    draw_final(v.img, v.to_view, C, width=2.2, alt_back=alt_back)
    draw_landmarks(v.img, v.to_view, C, F, scale=1)
    zz = v.to_view(np.array([0.0, z0]))[1]
    draw.hline(v.img, zz, "orange", 1.5, dash=(10, 6))
    draw.text(v.img, 6, zz + 4, "Z = 0 (74.7 %)", "orange", scale=1, bg="white")
    legend(v.img, 1150, 8, scale=1, extra=[("other reading of the left end (dashed)", "purple")])
    draw.text(v.img, 6, 6, "base contour (official) - back_left_variant = %s" % variant, "black", scale=2, bg="white")
    imgio.save_png(overlay_path, v.img)
    v = draw.View(rgb, 0, 0, 2700, 2100, scale=1600.0 / 2700.0)
    draw_final(v.img, v.to_view, C, width=2.5, alt_back=alt_back)
    draw_landmarks(v.img, v.to_view, C, F, scale=2)
    zz = v.to_view(np.array([0.0, z0]))[1]
    draw.hline(v.img, zz, "orange", 1.5, dash=(10, 6))
    legend(v.img, 8, 30, scale=2, extra=[("other reading of the left end (dashed)", "purple")])
    imgio.save_png(os.path.join(out_dir, "overlay_wave_1600.png"), v.img)
    for dz in P(cfg, "doubt_zones"):
        bb = dz["bbox_px"]
        q0, q1 = v.to_view(np.array([bb[0], bb[1]], float)), v.to_view(np.array([bb[2], bb[3]], float))
        draw.rect(v.img, q0[0], q0[1], q1[0], q1[1], "blue", 2)
        draw.text(v.img, q0[0] + 2, q0[1] - 20, dz["id"].split("_")[0], "blue", scale=2, bg="white")
    imgio.save_png(os.path.join(out_dir, "overlay_doubt_zones_1600.png"), v.img)
    # 5d 最終輪郭の切出し画像。
    crops = [("crop_01_back_left_end", (0, 780, 520, 1120), 3.0), ("crop_02_back_fork_zoom", (270, 830, 430, 950), 8.0),
             ("crop_03_back_mid", (450, 330, 1150, 830), 2.2), ("crop_04_crest", (1250, 150, 1750, 400), 3.0),
             ("crop_05_head_top_hook_claws", (1760, 340, 1960, 640), 5.0), ("crop_06_head_step_thin_line", (1850, 560, 2110, 700), 5.5),
             ("crop_07_pocket_lobe3_lobe4", (2030, 620, 2190, 800), 8.0), ("crop_08_head_tip", (2090, 720, 2320, 900), 6.0),
             ("crop_09_right_flank", (2030, 780, 2300, 1120), 4.5), ("crop_10_underside_right", (1850, 850, 2250, 1150), 4.0),
             ("crop_11_underside_left_armpit", (1500, 830, 1900, 1100), 4.0), ("crop_12_inner_deepest", (1430, 1080, 1630, 1360), 5.0),
             ("crop_13_inner_arc_mid", (1480, 1300, 1900, 1780), 3.0), ("crop_14_inner_arc_meets_near_wave", (1740, 1680, 1900, 1800), 8.0),
             ("crop_15_completion_trough", (1750, 1700, 2350, 2000), 2.6), ("crop_16_cloud_side_of_head", (2050, 500, 2500, 1000), 3.0)]
    for name, bx, scl in crops:
        save_crop(os.path.join(out_dir, name + ".png"), rgb, C, F, bx, scl, name, alt_back=alt_back,
                  extra_lines=[(np.array([[bx[0], z0], [bx[2], z0]]), "orange", 1.5, (10, 6))])
    # 5e グラフ。
    ser = []
    for key, colr in (("final", "red"), ("final_other_reading", "purple")):
        fp, fa = M[key]["S4"]["_curves"]["fine"]
        cp_, ca = M[key]["S4"]["_curves"]["coarse"]
        ser.append({"label": "%s fine (sigma 0.5 %%)" % key, "x": fp[:, 0], "y": fa, "color": colr, "width": 1})
        ser.append({"label": "%s coarse (sigma 3 %%)" % key, "x": cp_[:, 0], "y": ca, "color": colr, "width": 3})
    pl = plot.line_plot(ser, title="S4: slope of the back (final = %s, other = %s)" % (variant, other_variant), xlabel="x [px]", ylabel="slope [deg]",
                        size=(1600, 600), ylim=(-30, 60), hlines=[{"y": 25, "label": "spec 25"}, {"y": 47, "label": "spec 47"}, {"y": 8, "label": "spec 8"}])
    imgio.save_png(os.path.join(out_dir, "plot_S4_back_slope.png"), pl)
    ser, acc = [], 0.0
    s_full = LA.arclength(full)
    for nm, colr in (("back", "red"), ("head", "magenta"), ("inner_arc", "green")):
        r = M["final"]["S8_own"][nm]
        m = np.nonzero(seg == nm)[0]
        off = s_full[m[0]] if nm == "back" else s_full[m[0] - 1]
        ser.append({"label": nm, "x": F.px_to_pct_h(np.asarray(r["all_s"]) + off), "y": r["all_deg"], "color": colr, "marker": "o", "marker_size": 2})
    pl = plot.line_plot(ser, title="own S8 of the base contour: tangent change between neighbouring 1 % samples (phase 0)",
                        xlabel="arclength [% of image height]", ylabel="deg", size=(1600, 520), hlines=[{"y": 15, "label": "S8 limit 15"}])
    imgio.save_png(os.path.join(out_dir, "plot_S8_own.png"), pl)
    sg = [r["sigma_pct_h"] for r in lp_rows]
    pl1 = plot.line_plot([{"label": "%s own S8 max" % nm, "x": sg, "y": [r[nm]["own_s8_max_deg"] for r in lp_rows], "marker": "o"} for nm in SEG_NAMES],
                         title="low-pass diagnostic: own S8 of the low-passed contour", xlabel="sigma [% of image height]", ylabel="deg",
                         size=(1100, 460), hlines=[{"y": 15, "label": "15"}])
    pl2 = plot.line_plot([{"label": "%s p95 dev" % nm, "x": sg, "y": [r[nm]["dev_p95_pct_h"] for r in lp_rows], "marker": "o"} for nm in SEG_NAMES]
                         + [{"label": "%s mean dev" % nm, "x": sg, "y": [r[nm]["dev_mean_pct_h"] for r in lp_rows], "dash": (6, 4)} for nm in SEG_NAMES],
                         title="low-pass diagnostic: distance base contour -> low-passed contour", xlabel="sigma [% of image height]",
                         ylabel="% of image height", size=(1100, 460), hlines=[{"y": 2, "label": "S7 p95 limit 2"}, {"y": 1, "label": "S7 mean limit 1"}])
    imgio.save_png(os.path.join(out_dir, "plot_lowpass_diagnostic.png"), draw.vstack([pl1, pl2]))
    extra = [(lp_curves[s_], c_, 2.0, None) for s_, c_ in ((2.0, "blue"), (4.0, "black")) if s_ in lp_curves]
    save_crop(os.path.join(out_dir, "diagnostic_lowpass_head.png"), rgb, C, F, (1400, 150, 2400, 1150), 1.5,
              "low-pass of the base contour: blue sigma 2 %, black sigma 4 % of image height (diagnostic only)", extra_lines=extra, landmarks=False)
    ov2 = draw.View(rgb, 1400, 150, 2400, 1150, scale=1.5)
    draw.fill_polygon(ov2.img, ov2.to_view(M["final"]["S5"]["_poly"]), "yellow", alpha=0.25)
    draw_final(ov2.img, ov2.to_view, C, width=2.0)
    cen = np.array(M["final"]["S5"]["overhang_centroid_px"])
    ang = math.radians(M["final"]["S5"]["direction_deg"])
    dv = np.array([math.cos(ang), -math.sin(ang)]) * 450.0
    draw.line(ov2.img, ov2.to_view(cen - dv), ov2.to_view(cen + dv), "black", 2.0, dash=(10, 6))
    draw.text(ov2.img, 4, 4, "S5 direction: principal axis of the overhang area (yellow) = %.1f deg" % M["final"]["S5"]["direction_deg"], "black", scale=2, bg="white")
    for q in (5, 10, 20):
        t_ = M["final"]["head_thickness"]["%d_pct_H" % q]
        draw.line(ov2.img, ov2.to_view(np.array(t_["top_px"])), ov2.to_view(np.array(t_["under_px"])), "blue", 1.5)
    imgio.save_png(os.path.join(out_dir, "diagnostic_S5_direction_and_thickness.png"), ov2.img)

    # ---------------------------------------------------------------- 6. metrics.json
    metrics = {
        "params_file": paths.norm(args.params), "candidate_sha256": hashes, "warnings": warn,
        "back_left_variant": variant,
        "compare_A_B": {"per_segment_pct_h": cmp_["per_segment"], "stretches_over_threshold": cmp_["stretches"],
                        "unjudged": cmp_["unjudged"]},
        "final_vs_candidates_pct_h": {k: {nm: dist_final[k][nm] for nm in SEG_NAMES} for k in dist_final},
        "build_info": strip(C["info"]), "build_info_other_reading": strip(C_other["info"]),
        "remeasure_same_definitions": {k: strip({kk: vv for kk, vv in M[k].items()}) for k in M},
        "S3": strip(s3), "S6": strip(s6m) if s6m else None,
        "candidate_reported_remeasure": {"A": A["json"].get("remeasure"), "B": B["json"].get("remeasure")},
        "edge_check_px": edge,
        "lowpass_diagnostic": lp_rows,
        "test_library_on_final_json": lib,
        "lowpass_diagnostic_with_test_library": lib_lowpass,
        "output_sha256": {"base_contour.json": sha256_of(json_path), "alt": sha256_of(other_path)},
    }
    for k in metrics["remeasure_same_definitions"]:
        for nm in SEG_NAMES:
            r = metrics["remeasure_same_definitions"][k]["S8_own"][nm]
            for kk in ("all_s", "all_deg", "all_px"):
                r.pop(kk, None)
    paths.write_json(os.path.join(out_dir, "metrics.json"), metrics)

    # コンソールの要約。
    m = M["final"]
    log("S1 final %.2f / %.2f  dx %+.2f dy %+.2f | plateau x %.0f..%.0f (%.2f %%)" % (m["S1"]["pct"][0], m["S1"]["pct"][1], m["S1"]["dx_pct_h"], m["S1"]["dy_pct_h"],
        m["S1"]["plateau_x_px"][0], m["S1"]["plateau_x_px"][1], m["S1"]["plateau_width_pct_h"]))
    log("S2 final %.2f / %.2f  dx %+.2f dy %+.2f dist %.2f" % (m["S2"]["pct"][0], m["S2"]["pct"][1], m["S2"]["dx_pct_h"], m["S2"]["dy_pct_h"], m["S2"]["dist_pct_h"]))
    log("S3 sea top edge %.2f %% -> height %.2f %% (diff %+.2f); with frame Z0: %.2f %%" % (s3["visible_sea_top_edge_top_pct"], s3["height_pct_h_if_that_edge_were_the_trough"],
        s3["diff_pct_h_if_that_edge_were_the_trough"], s3["height_pct_h_with_frame_Z0"]))
    for k in ("final", "final_other_reading", "A", "B"):
        q = M[k]["S4"]
        log("S4 %-20s left(5%%) %+.1f left(2%%) %+.1f mid max %.1f at (%.0f, %.0f) before crest(8..3) %.1f rise %.1f" % (k, q["left_end_deg_chord_first_5pct"],
            q["left_end_deg_chord_first_2pct"], q["mid_max_deg_2pct_chord"], q["mid_max_at_px"][0], q["mid_max_at_px"][1], q["before_crest_deg_chord_8_to_3pct"], q["max_slope_increase_after_steepest_deg"]))
    log("S5 final tip %.2f / %.2f  H (%.4f, %.4f) dir %.1f deg; alternatives %s" % (m["S5"]["pct"][0], m["S5"]["pct"][1], m["S5"]["H"][0], m["S5"]["H"][1], m["S5"]["direction_deg"],
        {k: round(v, 1) for k, v in m["S5"]["direction_alternatives_deg"].items()}))
    if s6m:
        log("S6 measured %.2f / %.2f dx %+.2f dy %+.2f ; overhang %.1f %% H dir %.1f deg; tip is %.2f %% left of it" % (s6m["pct"][0], s6m["pct"][1], s6m["dx_pct_h"], s6m["dy_pct_h"],
            s6m["overhang_pct_H_from_final_crest"], s6m["direction_from_final_crest_deg"], s6m["final_head_tip_is_left_of_it_by_pct_h"]))
    for q in (5, 10, 20):
        t_ = m["head_thickness"]["%d_pct_H" % q]
        log("THICK %2d %% H behind tip: pair %.1f %% H, shortest %.1f %% H" % (q, t_["pair_distance_pct_H"], t_["shortest_top_to_underside_pct_H"]))
    for nm in SEG_NAMES:
        r, g = m["S8_own"][nm], m["segments"][nm]
        log("SEG %-9s n %d len %.0f px (%.1f %%) in_S7=false %.1f %% | own S8 max %.1f deg (%d of %d >= 15) at %s | %s" % (nm, g["n_points"], g["length_px"], g["length_pct_h"],
            100 * g["share_in_S7_false"], r["max_deg"], r["n_ge_15"], r["n"], [round(v) for v in r["at_px"]], g["counts"]))
    log("TIP turn", m["tip_turn_clockwise_deg"])
    for k in ("A", "B"):
        log("DIST final->%s  " % k + "  ".join("%s mean %.3f p95 %.3f max %.3f" % (nm, dist_final[k][nm]["mean"], dist_final[k][nm]["p95"], dist_final[k][nm]["max"]) for nm in SEG_NAMES))
    for r in lp_rows:
        log("LOWPASS sigma %.1f %%: " % r["sigma_pct_h"] + " | ".join("%s S8 %.0f dev mean %.2f p95 %.2f max %.2f" % (nm, r[nm]["own_s8_max_deg"], r[nm]["dev_mean_pct_h"], r[nm]["dev_p95_pct_h"], r[nm]["dev_max_pct_h"]) for nm in SEG_NAMES))

    ok = not cmp_["unjudged"]
    bootstrap.finish(ok, "base contour written" if ok else "%d A-B stretch(es) > threshold without a verdict - look at them and add verdicts" % len(cmp_["unjudged"]))


if __name__ == "__main__":
    main()
