"""終幕フレームの形状検査 S1–S8（旧仕様の第5節）。無画面で単独実行できる。

  blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/test_shape.py -- --object <name>
          [--blend <path>] [--build-script <py> [--build-func f] [--build-arg k=v ...]]
          [--contour <base_contour.json>] [--final-frame N] [--res-scale s] [--H m] [--out-dir d]
直接起動では --python-exit-code 1 が必須。指定しないと、インポート中の例外で Blender が終了コード0を返す。
main() 内の例外は common_test.guarded_main が捕捉し、判定 ERROR と終了コード2を記録する。

CAM_print から見たシルエットをサブピクセル精度でラスタライズし、輪郭を基準JSONと比較する。
閾値の出典は tests/thresholds.json のみ。両段階の結果を毎回報告する。
出力：results/<YYYYMMDD_HHMMSS>_shape/ に metrics.json、summary.md、原画重ね合わせ、
局所拡大、偏差と弧長の図、S8・S4の図を保存する。

判定に入れず、報告だけに使う値：S7の各方向と符号付き偏差、S5の波頂→先端方向、
Wの断面幅・張り出し・空洞深度・面積、各輪郭自身の波高で規格化した形状量、
S7の波頭下面と波腹、原画の波頂平坦部、S8の頂点窓角など。
T系は有効性を説明する値で、JSON接合点と検出点の差が画面高0.2％を超えると INVALID にする。
非有限頂点、欠落三角形、脱離成分、静水面への到達、S7対象外の割合も毎回報告する。

2026-09-20から、S3は静水面基準とモデル自身の谷基準を同じ閾値で併記・判定した。
これは当時の暫定解釈で、利用者確認待ちだった。
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common_test as ct  # noqa: E402
from common_test import bootstrap, draw, imgio, paths, plot, pm, silhouette, log  # noqa: E402

TEST_NAME = "shape"
SEGS = ("back", "head", "inner_arc")
SIGNED_LABEL = "報告専用：符号付き法線偏差。正はモデルが目標浪体の外側（閾値なし）"
DARKGREEN = (0, 95, 30)
VERTEX_WINDOW_LABEL = ("報告専用：S8の1標本間隔に相当する閉区間で折線自身の頂点の転角を測る。除外区間なし。"
                       "正式基準輪郭自身が19°なので15°で判定しない")


# ------------------------------------------------------------------------------------ per-sample deviation
def deviation_samples(model_pts, poly, mm, P):
    """pm.s7_deviation と同じ標本間隔・余白・in_S7 の扱いで、標本ごとの偏差を返す。
    失敗箇所の特定と描画に使う。判定値は引き続き pm.s7_deviation から取り、呼出側で照合する。"""
    Cm, Cb = pm.Curve(model_pts), pm.Curve(poly["pts_H"])
    b_idx = Cb.index_map
    b_seg, b_flag = poly["seg_id"][b_idx], poly["in_S7"][b_idx]
    sp = float(pm.pct_h_to_H(P["s7_sample_spacing_pct_h"]))
    margin = float(pm.pct_h_to_H(P["s7_segment_margin_pct_h"]))
    i_cb = int(np.searchsorted(b_idx, poly["crest_index"]))
    i_tb = int(np.searchsorted(b_idx, poly["tip_index"]))
    b_rng = {"back": (0.0, Cb.s[i_cb]), "head": (Cb.s[i_cb], Cb.s[i_tb]), "inner_arc": (Cb.s[i_tb], Cb.length)}
    edge_ok = b_flag[:-1] & b_flag[1:]
    out = {"_model_curve": Cm, "_base_curve": Cb}
    for k, nm in enumerate(poly["names"]):
        m_rng = mm["segments_s"].get(nm)
        if m_rng is None:
            out[nm] = None
            continue
        s0, s1 = float(max(0.0, m_rng[0])), float(min(Cm.length, m_rng[1]))
        n = max(2, int(np.ceil((s1 - s0) / sp)) + 1)
        ss = np.linspace(s0, s1, n)
        mp = Cm.at(ss)
        lo, hi = max(0.0, b_rng[nm][0] - margin), min(Cb.length, b_rng[nm][1] + margin)
        ia, ib = max(0, Cb.index_at(lo) - 1), Cb.index_at(hi)
        d, e = pm.point_polyline_distance(mp, Cb.pts[ia:ib + 1])
        counted = edge_ok[np.clip(ia + e, 0, len(edge_ok) - 1)]
        sel = (b_seg == k) & b_flag
        bp, bs = Cb.pts[sel], Cb.s[sel]
        if bp.shape[0] > 1:
            keep = np.concatenate([[True], np.diff(np.floor(bs / sp)) > 0])
            bp, bs = bp[keep], bs[keep]
        lo_m, hi_m = max(0.0, m_rng[0] - margin), min(Cm.length, m_rng[1] + margin)
        d2 = pm.point_polyline_distance(bp, Cm.slice_pts(lo_m, hi_m))[0] if bp.shape[0] else np.zeros(0)
        out[nm] = {"model_to_base": {"s_H": ss, "pts_H": mp, "dev_pct_h": pm.H_to_pct_h(d), "counted": counted},
                   "base_to_model": {"s_H": bs, "pts_H": bp, "dev_pct_h": pm.H_to_pct_h(d2),
                                     "counted": np.ones(bp.shape[0], bool)},
                   "model_s_range_H": [s0, s1], "base_s_range_H": [float(b_rng[nm][0]), float(b_rng[nm][1])]}
    return out


def _stretches(F, side, limit, seg, max_n):
    """一方向の失敗区間を、弧長範囲・最大偏差・座標の辞書リストで返す。"""
    dev, cnt = side["dev_pct_h"], side["counted"]
    out = []
    for i0, i1 in ct.ranges_above(dev, limit, cnt):
        j = i0 + int(np.argmax(dev[i0:i1 + 1]))
        w = ct.where_point(F, side["pts_H"][j], segment=seg, s_H=side["s_H"][j])
        w.update({"s_range_pct_h": [float(pm.H_to_pct_h(side["s_H"][i0])), float(pm.H_to_pct_h(side["s_H"][i1]))],
                  "max_dev_pct_h": float(dev[j]),
                  "px_range": [[float(v) for v in F.H_to_px(*side["pts_H"][i0])], [float(v) for v in F.H_to_px(*side["pts_H"][i1])]]})
        out.append(w)
    out.sort(key=lambda r: -r["max_dev_pct_h"])
    return out[:max_n], len(out)


# ------------------------------------------------------------------------------------ 報告専用の補助関数
def armpit_of(C, s_tip, s_deep, min_sagitta_H):
    """報告専用。頭部先端と空洞最深点を結ぶ弦から、胴体側へ最も離れた内側弧の点を脇とする。
    先端から最深点へ進むと胴体側は右、空洞側は左。脇で頭部下面と腹を分ける。
    弧長・座標・矢高の辞書を返し、明瞭な角がなければ None。"""
    if s_tip is None or s_deep is None or s_deep <= s_tip:
        return None
    n = max(8, int((s_deep - s_tip) / float(pm.pct_h_to_H(0.1))) + 1)
    ss = np.linspace(s_tip, s_deep, n)
    q = C.at(ss)
    d = q[-1] - q[0]
    L = float(np.hypot(d[0], d[1]))
    if L <= 0.0:
        return None
    r = q - q[0]
    right = -(d[0] * r[:, 1] - d[1] * r[:, 0]) / L
    k = int(np.argmax(right))
    if right[k] < min_sagitta_H:
        return None
    return {"s": float(ss[k]), "H": [float(q[k, 0]), float(q[k, 1])], "sagitta_pct_h": float(pm.H_to_pct_h(right[k]))}


def height_on_plumb(C, s_lo, s_hi, x0=0.0):
    """報告専用。弧長 s_lo..s_hi の輪郭が X=x0 の鉛直線と交わる最大 Z。交わらなければ None。"""
    sel = (C.s >= s_lo) & (C.s <= s_hi)
    x, z = C.pts[sel, 0] - float(x0), C.pts[sel, 1]
    if x.size < 2:
        return None
    k = np.nonzero((x[:-1] <= 0.0) != (x[1:] <= 0.0))[0]
    zs = [float(z[i] + (0.0 - x[i]) / (x[i + 1] - x[i]) * (z[i + 1] - z[i])) for i in k if x[i + 1] != x[i]]
    zs += [float(v) for v in z[x == 0.0]]
    return max(zs) if zs else None


def in_s7_shares(poly, s7):
    """各区間で S7 から除外される割合を返す。
    目標側は in_S7=false の端点を持つ基準輪郭の辺の弧長比、モデル側は最近接区間が除外域にある標本の比。"""
    Cb = pm.Curve(poly["pts_H"])
    idx = Cb.index_map
    seg, flag = poly["seg_id"][idx], poly["in_S7"][idx]
    ds = np.diff(Cb.s)
    out = {}
    for k, nm in enumerate(poly["names"]):
        e_seg = (seg[:-1] == k) & (seg[1:] == k)
        tot = float(ds[e_seg].sum())
        tgt = None if tot <= 0 else 100.0 * float(ds[e_seg & ~(flag[:-1] & flag[1:])].sum()) / tot
        mdl = None
        r = (s7 or {}).get(nm)
        if r:
            n_ok, n_skip = int(r["model_to_base"].get("n") or 0), int(r["model_to_base"].get("n_skipped_not_in_S7") or 0)
            mdl = None if (n_ok + n_skip) == 0 else 100.0 * n_skip / float(n_ok + n_skip)
        out[nm] = {"target_pct": tgt, "model_pct": mdl}
    return out


def _part_stats(side, lo, hi):
    """弧長 [lo, hi] に含まれ、S7 の一方向で計数した標本の平均・p95・件数。"""
    sel = side["counted"] & (side["s_H"] >= lo) & (side["s_H"] <= hi)
    if not sel.any():
        return {"n": 0, "mean": None, "p95": None}
    d = side["dev_pct_h"][sel]
    return {"n": int(sel.sum()), "mean": float(d.mean()), "p95": float(np.percentile(d, 95))}


# ------------------------------------------------------------------------------------ 検査本体
def judge_profile(F, S, pts_H, bc, poly=None, bm=None, P=None):
    """H 単位の順序付き輪郭一本を基準輪郭と比較し、S1～S8 を検査する。
    モデルのシルエットと selfcheck_tests.py の解析的な折線に共用する。検査値・注記・測定資料の辞書を返す。"""
    P = P or pm.get_params()
    poly = poly or pm.base_contour_polyline(bc)
    bm = bm or pm.measure_base_contour(bc, P)
    m = pm.measure_profile(pts_H, P)
    pc = pm.position_checks(m, bc, bm, frame_obj=F)
    s7 = pm.s7_deviation(pts_H, poly, m, P)
    lmk = m["landmarks"]
    checks, notes = [], []
    if not m["overhanging"]:
        notes.append("測定した輪郭に張り出しがない。CAM_print から波頭先端と内側の弧を識別できず、S2・S5・S6・S7の波頭／内側の弧を測れない")

    def W(key, seg=None):
        lm = lmk.get(key)
        return None if lm is None else ct.where_point(F, lm["H"], segment=seg, s_H=lm["s"])

    # ---- S1
    v = pc["S1"]["vs_spec"]
    tgt = {"H": pc["S1"]["target_spec_H"], "left_top_pct": [38.2, 8.7]}
    checks.append(ct.make_check("S1", "dx_pct_h", v["dx_pct_h"], target=tgt, difference=v["dx_pct_h"], where=W("crest", "back|head")))
    checks.append(ct.make_check("S1", "dz_pct_h", v["dz_pct_h"], target=tgt, difference=v["dz_pct_h"], where=W("crest", "back|head")))
    if pc["S1"].get("vs_base"):
        vb = pc["S1"]["vs_base"]
        for k in ("dx_pct_h", "dz_pct_h"):
            checks.append(ct.make_check("S1", k, vb[k], sub="vs_base_contour", target={"H": bm["landmarks"]["crest"]["H"]},
                                        difference=vb[k], info_only=True, note="参考値：基準輪郭の波頂を目標とする"))
    checks.append(ct.report_value("S1", "crest_plateau_width_pct_h", lmk["crest_plateau"]["width_pct_h"], "% of image height",
                                  note="モデルの最大高さから %.2g %% 以内にある連続区間の幅" % lmk["crest_plateau"]["tol_pct_h"]))
    # S1 の補助値（報告専用）。原画の波頂は数 % 幅の平坦部なので、最高点の X は不安定。
    # モデルの波頂が原画の平坦部の X 範囲内にあるか、仕様第4節の鉛直線 X=0 上で輪郭がどの高さかを示す。
    Cm0 = pm.Curve(pts_H)
    plat, plat_src = None, None
    jl = ((bc.get("landmarks") or {}).get("crest") or {}).get("plateau_x_px")
    if jl and len(jl) == 2:
        plat = sorted(float(F.px_to_H(float(v), 0.0)[0]) for v in jl)
        plat_src = "基準輪郭JSONの landmarks.crest.plateau_x_px = %s px" % [round(float(v), 1) for v in jl]
    else:
        try:
            cpl = pm.measure_profile(poly["pts_H"], P)["landmarks"]["crest_plateau"]
            plat = [float(cpl["x_min_H"]), float(cpl["x_max_H"])]
            plat_src = "基準輪郭の折線から検出した平坦部（頂点高さとの差が画面高の %.2g %% 以内）" % cpl["tol_pct_h"]
        except Exception as exc:                                   # report-only: never let it break the judged checks
            plat_src = "取得できない（%s: %s）" % (type(exc).__name__, exc)
    xc = float(lmk["crest"]["H"][0])
    inside = None if plat is None else bool(plat[0] <= xc <= plat[1])
    outside = None if plat is None else float(pm.H_to_pct_h(max(plat[0] - xc, xc - plat[1], 0.0)))
    checks.append(ct.report_value("S1", "crest_inside_painted_plateau", inside, "bool", target={"plateau_x_range_H": plat},
                                  note="報告専用：モデル波頂のX座標 %.4f H が原画の平坦部 %s に含まれるか。出典：%s" % (xc, plat, plat_src)))
    checks.append(ct.report_value("S1", "crest_outside_plateau_pct_h", outside, "% of image height",
                                  note="報告専用：モデル波頂と原画の平坦部の水平距離。内部なら0"))
    s_top_end = lmk["head_tip"]["s"] if m["overhanging"] else lmk["trough_end"]["s"]
    z0 = height_on_plumb(Cm0, 0.0, s_top_end, 0.0)
    h0 = None if z0 is None else float(pm.H_to_pct_h(z0 - float(P["z_still_H"])))
    checks.append(ct.report_value("S1", "height_on_x0_plumb_pct_h", h0, "% of image height", target=float(F.height_pct),
                                  difference=None if h0 is None else h0 - float(F.height_pct),
                                  note="報告専用：X＝0の鉛直線上にある輪郭上面の静水面からの高さ。目標 %.1f はS3の高さ。"
                                       "波頂自体は X＝%.4f H、Z＝%.4f H" % (F.height_pct, xc, lmk["crest"]["H"][1])))
    # ---- S2
    v = pc["S2"]["vs_spec"]
    tgt = {"H": pc["S2"]["target_spec_H"], "left_top_pct": [39.5, 46.3]}
    checks.append(ct.make_check("S2", "dist_pct_h", None if v is None else v["dist_pct_h"], target=tgt,
                                difference=None if v is None else {"dx_pct_h": v["dx_pct_h"], "dz_pct_h": v["dz_pct_h"]},
                                where=W("inner_deepest", "inner_arc")))
    if pc["S2"].get("vs_base"):
        vb = pc["S2"]["vs_base"]
        checks.append(ct.make_check("S2", "dist_pct_h", vb["dist_pct_h"], sub="vs_base_contour",
                                    target={"H": bm["landmarks"]["inner_deepest"]["H"]},
                                    difference={"dx_pct_h": vb["dx_pct_h"], "dz_pct_h": vb["dz_pct_h"]}, info_only=True,
                                    note="参考値：基準輪郭の最深点を目標とする"))
    # ---- S3
    checks.append(ct.make_check("S3", "height_err_pct_h", pc["S3"]["height_err_pct_h"], target=66.0,
                                difference=pc["S3"]["height_err_pct_h"], where=W("crest"),
                                note="Z＝0（画角の定義）からの波頂高さは画面高の %.3f %%。モデル自身の谷水位"
                                     "（内側の弧の最深点以後にある輪郭の最低点）からの高さは %s。S3.from_model_trough として判定"
                                     % (pc["S3"]["height_pct_h"], ct._fmt(pc["S3"]["height_from_measured_trough_pct_h"]))))
    s3m = pc["S3_from_model_trough"]
    checks.append(ct.make_check("S3", "height_err_pct_h", s3m["height_err_pct_h"], sub="from_model_trough", target=66.0,
                                difference=s3m["height_err_pct_h"], where=W("trough_lowest"),
                                label="暫定解釈・利用者確認待ち：モデル自身の谷水位から波頂までの高さ",
                                note="S3と同じ閾値で判定し、悪い側を採る。波頂Zから、内側の弧の最深点と右端の間の最低Zを引いた値＝画面高の %s %%。"
                                     "モデルの谷水位はZ＝0より %s %% 上。静水面へ到達したか（許容差 %s %%）：%s"
                                     % (ct._fmt(s3m["height_pct_h"]), ct._fmt(s3m["trough_level_above_still_pct_h"]),
                                        ct._fmt(s3m["reached_still_water_tol_pct_h"]), s3m["reached_still_water"])))
    # ---- S4
    s4, s4b = m["S4"], bm["S4"]
    spec4 = paths.load_thresholds()["S4"]["target"]
    for k in ("left_end_deg", "mid_max_deg", "before_crest_deg"):
        w = None
        if k == "mid_max_deg" and s4.get("mid_max_at"):
            w = ct.where_point(F, s4["mid_max_at"]["H"], segment="back", s_H=s4["mid_max_at"]["s"])
        checks.append(ct.make_check("S4", k, s4.get(k), target={"spec_about_deg": spec4[k], "base_contour_deg": s4b.get(k)},
                                    difference=None if s4.get(k) is None else
                                    {"vs_spec_deg": s4[k] - spec4[k], "vs_base_contour_deg": None if s4b.get(k) is None else s4[k] - s4b[k]},
                                    where=w))
    for k in ("mid_is_steepest", "flattens_towards_crest", "top_is_round_no_corner"):
        note = None
        if k == "flattens_towards_crest":
            note = "最急点以後の傾きの最大再増加：%s°（許容 %s°）" % (
                ct._fmt(s4.get("max_slope_increase_after_steepest_deg")), P["s4_monotone_tol_deg"])
        if k == "top_is_round_no_corner":
            note = "波頂から %s %% 以内のS8最大転角：%s°" % (P["s4_crest_zone_pct_h"], ct._fmt(s4.get("crest_max_turn_deg")))
        if k == "mid_is_steepest" and s4.get("mid_max_at"):
            note = "最急点は背の弧長の %.0f %% にある" % (100.0 * s4["mid_max_at"]["frac_of_back"])
        checks.append(ct.make_check("S4", k, s4.get(k), target=1, note=note,
                                    where=None if not s4.get("mid_max_at") else
                                    ct.where_point(F, s4["mid_max_at"]["H"], segment="back", s_H=s4["mid_max_at"]["s"])))
    # ---- S5
    s5 = pc.get("S5")
    tip_t = {"H": bm["landmarks"]["head_tip"]["H"] if bm["landmarks"].get("head_tip") else None, "phi_deg": bm["phi_deg"]}
    checks.append(ct.make_check("S5", "pos_pct_h", None if not s5 else s5["pos_pct_h"], target=tip_t,
                                difference=None if not s5 else {"dx_pct_h": s5["dx_pct_h"], "dz_pct_h": s5["dz_pct_h"]},
                                where=W("head_tip", "head|inner_arc")))
    checks.append(ct.make_check("S5", "dir_deg", None if not s5 else s5["dir_deg"], target=tip_t,
                                difference=None if not s5 else s5["dir_deg"], where=W("head_tip", "head|inner_arc"),
                                note=None if not s5 else "φ：モデル %s°、基準輪郭 %s°。φは先端前の上面の弦方向で、S5とM4に共通して使う"
                                                         % (ct._fmt(s5["model_phi_deg"]), ct._fmt(s5["base_phi_deg"]))))
    checks.append(ct.report_value("S5", "crest_to_tip_dir_diff_deg", None if not s5 else s5.get("crest_to_tip_diff_deg"), "deg",
                                  target={"base_contour_deg": bm.get("crest_to_tip_deg")},
                                  note="報告専用：波頂→先端の直線方向。モデル %s°、基準輪郭 %s°。S5の判定にはφを使う"
                                       % (ct._fmt(m.get("crest_to_tip_deg")), ct._fmt(bm.get("crest_to_tip_deg")))))
    if m.get("head_lobes"):
        hl = m["head_lobes"]
        checks.append(ct.report_value("S5", "model_head_lobes", hl["n_lobes"], "count",
                                      note="モデルの波頂から最深点までに、Xが画面高の %s %% 以上右から左へ戻る回数（1なら単一の先端）。"
                                           "旧規則による先端は現行先端から画面高の %s %% 離れる"
                                           % (ct._fmt(hl["lobe_reversal_pct_h"]), ct._fmt(hl["onset_to_tip_pct_h"]))))
    # ---- S6
    s6 = pc.get("S6")
    checks.append(ct.make_check("S6", "body_rightmost_left_pct", None if not s6 else s6["body_rightmost_left_pct"], target=59.2,
                                difference=None if not s6 else s6["body_rightmost_left_pct"] - 59.2, where=W("body_rightmost", "head"),
                                note=None if not s6 else "爪先までの余裕：画面高の %.3f %%" % s6["margin_pct_h"]))
    # ---- S7
    dv = deviation_samples(pts_H, poly, m, P)
    lim = {t: {k: paths.threshold("S7", k, t) for k in ("mean_dev_pct_h", "p95_dev_pct_h")} for t in ct.TIERS}
    consistency = {}
    for seg in SEGS:
        r = s7.get(seg)
        if r is None:
            for k in ("mean_dev_pct_h", "p95_dev_pct_h"):
                checks.append(ct.make_check("S7", k, None, sub=seg, note="測定輪郭にこの区間が存在しない"))
            continue
        worse = "model_to_base" if (r["model_to_base"]["p95_pct_h"] or 0) >= (r["base_to_model"]["p95_pct_h"] or 0) else "base_to_model"
        side = dv[seg][worse]
        cnt = side["counted"]
        if cnt.any():
            consistency[seg] = {"lib_mean": r[worse]["mean_pct_h"], "local_mean": float(side["dev_pct_h"][cnt].mean()),
                                "lib_p95": r[worse]["p95_pct_h"], "local_p95": float(np.percentile(side["dev_pct_h"][cnt], 95))}
        wp = r.get("worst_point")
        for k in ("mean_dev_pct_h", "p95_dev_pct_h"):
            where = None if not wp else ct.where_point(F, wp["H"], segment=seg, worst_dev_pct_h=wp["dev_pct_h"], direction=wp["direction"])
            if where is not None and r[k] is not None and r[k] > min(lim[t][k] for t in ct.TIERS):
                lst, n_all = _stretches(F, side, lim["spec"][k], seg, int(S["s7_report_max_ranges"]))
                where.update({"direction_listed": worse, "limit_pct_h": lim["spec"][k], "n_ranges": n_all, "ranges": lst,
                              "s_reference": "%s輪郭の始点（画面左端）からの弧長。単位は画面高の百分率"
                                             % ("モデル" if worse == "model_to_base" else "基準")})
            checks.append(ct.make_check("S7", k, r[k], sub=seg, target=0.0, where=where,
                                        note="双方向の悪い側を判定：モデル→基準 %s／基準→モデル %s。モデル側の%d標本は最近接の基準区間が in_S7=false のため除外"
                                             % (ct._fmt(r["model_to_base"][k.replace("_dev", "")]), ct._fmt(r["base_to_model"][k.replace("_dev", "")]),
                                                r["model_to_base"].get("n_skipped_not_in_S7", 0))))
        # 旧定義表に沿い、最近接距離を双方向それぞれで報告する。判定には使わない。
        for direction in ("model_to_base", "base_to_model"):
            for k in ("mean_dev_pct_h", "p95_dev_pct_h"):
                checks.append(ct.make_check("S7", k, r[direction][k.replace("_dev", "")], sub="%s.%s" % (seg, direction), target=0.0,
                                            info_only=True, note="一方向のみの参考値。標本数%d。判定には双方向の悪い側を使う"
                                                                 % r[direction]["n"]))
        # 報告専用：符号付き法線偏差。正値はモデルが目標浪体の外側にあることを示す。
        # 幅広かつ低い胴体は符号なし偏差だけでは方向が分からないため、ずれの向きを記録する。
        mb = r["model_to_base"]
        checks.append(ct.report_value("S7", "signed_mean_dev_pct_h", r.get("signed_mean_dev_pct_h"), "% of image height", sub=seg, target=0.0,
                                      label=SIGNED_LABEL,
                                      note="%s。モデル→基準標本：中央値 %s、5％点 %s、95％点 %s、目標浪体の外側にある割合 %s、符号なし平均 %s"
                                           % (SIGNED_LABEL, ct._fmt(mb.get("signed_median_pct_h")), ct._fmt(mb.get("signed_p05_pct_h")), ct._fmt(mb.get("signed_p95_pct_h")),
                                              ct._fmt(mb.get("frac_model_outside")), ct._fmt(mb.get("mean_pct_h")))))
        for q in ("signed_p05_pct_h", "signed_p95_pct_h"):
            checks.append(ct.report_value("S7", q, mb.get(q), "% of image height", sub=seg, label=SIGNED_LABEL, note=SIGNED_LABEL))
    # 報告専用：内側の弧を脇で頭部下面（先端～脇）と波腹（脇～波谷）に分ける。
    split = {"definition": "腋部＝先端と最深点を結ぶ直線から浪体側へ最も離れた内側の弧の点。"
                           "波頭下面＝先端から腋部、波腹＝腋部から内側の弧の終点。標本と in_S7 の扱いは S7.inner_arc と同じ",
             "model_armpit": None, "base_armpit": None, "parts": {}}
    if m["overhanging"] and dv.get("inner_arc") and bm["landmarks"].get("head_tip") and bm["landmarks"].get("inner_deepest"):
        min_sag = float(pm.pct_h_to_H(S["armpit_min_sagitta_pct_h"]))
        am = armpit_of(dv["_model_curve"], lmk["head_tip"]["s"], lmk["inner_deepest"]["s"], min_sag)
        ab = armpit_of(dv["_base_curve"], bm["landmarks"]["head_tip"]["s"], bm["landmarks"]["inner_deepest"]["s"], min_sag)
        split["model_armpit"], split["base_armpit"] = am, ab
        if am and ab:
            ia = dv["inner_arc"]
            for part, (lo_m, hi_m), (lo_b, hi_b) in (("underside", (-np.inf, am["s"]), (-np.inf, ab["s"])), ("belly", (am["s"], np.inf), (ab["s"], np.inf))):
                a, b = _part_stats(ia["model_to_base"], lo_m, hi_m), _part_stats(ia["base_to_model"], lo_b, hi_b)
                split["parts"][part] = {"model_to_base": a, "base_to_model": b}
                for k, key in (("mean_dev_pct_h", "mean"), ("p95_dev_pct_h", "p95")):
                    vals = [v[key] for v in (a, b) if v[key] is not None]
                    checks.append(ct.make_check("S7", k, max(vals) if vals else None, sub=part, target=0.0, info_only=True,
                                                where=ct.where_point(F, am["H"], segment="inner_arc (%s)" % part, s_H=am["s"]),
                                                label="報告専用：内側の弧の部分（%s）" % part,
                                                note="報告専用で判定しない。仕様の対象は内側の弧全体。モデル→基準 %s（標本%d）と基準→モデル %s（標本%d）の悪い側。"
                                                     "腋部で分割し、モデル (%.4f, %.4f) H、基準輪郭 (%.4f, %.4f) H"
                                                     % (ct._fmt(a[key]), a["n"], ct._fmt(b[key]), b["n"], am["H"][0], am["H"][1], ab["H"][0], ab["H"][1])))
    if not split["parts"]:
        checks.append(ct.report_value("S7", "underside_belly_split", None, None,
                                      note="報告専用：張り出しがないか、腋部の深さが画面高の %s %% 未満のため、下面と波腹に分けられない"
                                           % ct._fmt(S["armpit_min_sagitta_pct_h"])))
    # ---- S8
    s8 = m["S8"]
    Cm = dv["_model_curve"]
    s_tip = lmk["head_tip"]["s"] if m["overhanging"] else None
    s8full = pm.s8_smoothness(Cm, lmk["crest"]["s"], s_tip, lmk["trough_end"]["s"], P)
    js, jd = np.asarray(s8full["_junction_s"]), np.abs(np.asarray(s8full["_junction_diff"]))
    judged = np.ones(js.size, bool) if s_tip is None else (np.abs(js - s_tip) > float(pm.pct_h_to_H(P["s8_tip_exclusion_pct_h"])))
    where8 = None
    if s8.get("max_at"):
        where8 = ct.where_point(F, s8["max_at"]["H"], segment=s8["max_at"]["segment"], s_H=s8["max_at"]["s"])
        lim8 = paths.threshold("S8", "max_tangent_diff_deg", "spec")
        order = np.argsort(js)
        rr = ct.ranges_above(jd[order], lim8, judged[order])
        if rr:
            lst = []
            for i0, i1 in rr:
                idx = order[i0:i1 + 1]
                j = idx[int(np.argmax(jd[idx]))]
                w = ct.where_point(F, Cm.at(js[j]), s_H=js[j])
                w.update({"s_range_pct_h": [float(pm.H_to_pct_h(js[idx].min())), float(pm.H_to_pct_h(js[idx].max()))], "max_turn_deg": float(jd[j])})
                lst.append(w)
            lst.sort(key=lambda r: -r["max_turn_deg"])
            where8.update({"n_ranges": len(lst), "ranges": lst[:int(S["s7_report_max_ranges"])], "limit_deg": lim8})
    checks.append(ct.make_check("S8", "max_tangent_diff_deg", s8["max_tangent_diff_deg"], target=0.0, where=where8,
                                note="区間別：%s。先端の転角 %s°。先端除外なしの最大値 %s°"
                                     % (ct.jsonable(s8["per_segment"]), ct._fmt(s8["tip_turn_deg"]), ct._fmt(s8["max_unexcluded_deg"]))))
    checks.append(ct.make_check("S8", "sample_spacing_pct_h", s8["spacing_pct_h"], target=1.0, note="検査設定（params.json の S8_sample_spacing_pct）"))
    checks.append(ct.report_value("S8", "tip_turn_deg", s8["tip_turn_deg"], "deg", note="波頭先端をまたぐ総転角。暫定解釈として別途報告し、利用者確認待ち"))
    checks.append(ct.report_value("S8", "max_unexcluded_deg", s8["max_unexcluded_deg"], "deg",
                                  note="波頭先端の周辺を除外しない場合のS8最大値。2026-09-20から先端上の接合点も含む。"
                                       "その接合点を除くと %s°" % ct._fmt(s8.get("max_unexcluded_without_tip_junction_deg"))))
    checks.append(ct.report_value("S8", "tip_junction_deg", s8.get("tip_junction_deg"), "deg", target={"base_contour_deg": bm["S8"].get("tip_junction_deg")},
                                  note="報告専用：波頭先端上の接合点における符号付き接線角差。尖りはここに現れ、判定用S8には現れない"))
    vw, vwb = s8.get("vertex_window_turn") or {}, bm["S8"].get("vertex_window_turn") or {}
    where_v = None
    if vw.get("max_at"):
        where_v = ct.where_point(F, vw["max_at"]["H"], segment=vw["max_at"].get("segment"), s_H=vw["max_at"].get("s"))
    checks.append(ct.report_value("S8", "max_vertex_window_turn_deg", s8.get("max_vertex_window_turn_deg"), "deg", where=where_v,
                                  target={"base_contour_deg": bm["S8"].get("max_vertex_window_turn_deg")},
                                  difference=None if (s8.get("max_vertex_window_turn_deg") is None or bm["S8"].get("max_vertex_window_turn_deg") is None)
                                  else s8["max_vertex_window_turn_deg"] - bm["S8"]["max_vertex_window_turn_deg"],
                                  label=VERTEX_WINDOW_LABEL,
                                  note="%s。モデルの区間別 %s、先端除外区間外 %s、先端をまたぐ値 %s。基準輪郭の区間別 %s。モデルの短い窓：%s"
                                       % (VERTEX_WINDOW_LABEL, ct.jsonable(vw.get("per_segment")), ct._fmt(vw.get("max_outside_tip_exclusion_deg")), ct._fmt(vw.get("across_tip_deg")),
                                          ct.jsonable(vwb.get("per_segment")),
                                          ["%s %%: %s deg" % (ct._fmt(w.get("window_pct_h")), ct._fmt(w.get("max_deg"))) for w in (vw.get("short_windows") or [])])))
    for seg8, v8 in sorted((vw.get("per_segment") or {}).items()):
        checks.append(ct.report_value("S8", "vertex_window_turn_deg", v8, "deg", sub=seg8, target={"base_contour_deg": (vwb.get("per_segment") or {}).get(seg8)},
                                      label=VERTEX_WINDOW_LABEL, note=VERTEX_WINDOW_LABEL))
    # ---- W: report-only size metrics (NO thresholds; pending user decision)
    w_rows = pm.compare_width_metrics(m["W"], bm["W"])
    for r in w_rows:
        if r["model"] is None and r["target"] is None:
            continue
        sub, name = r["name"].split(".", 1) if "." in r["name"] else (None, r["name"])
        where = None
        if r["level_H"] is not None:
            sec = m["W"]["sections"][sub]
            if sec.get("x_front_H") is not None:
                where = ct.where_point(F, [sec["x_front_H"], r["level_H"]], segment="section Z = %.2f H" % r["level_H"])
        checks.append(ct.report_value("W", name, r["model"], r["unit"], sub=sub, target=r["target"], where=where,
                                      difference={"abs": r["diff"], "pct_of_target": r["diff_pct_of_target"], "abs_pct_h": r["diff_pct_h"]},
                                      label=pm.WIDTH_LABEL,
                                      note=("%s。" % pm.WIDTH_LABEL) + ("モデルと基準輪郭を比較" if r["comparable"] else "比較不能")
                                           + ("" if not r["note"] else "; " + r["note"])))
    # ---- W.own_h: report-only shape descriptors relative to each contour's OWN crest height (NO thresholds)
    shape_rows = pm.compare_shape_descriptors(m["shape"], bm["shape"])
    for r in shape_rows:
        if r["model"] is None and r["target"] is None:
            continue
        checks.append(ct.report_value("W", r["name"], r["model"], r["unit"], sub="own_h", target=r["target"],
                                      difference={"abs": r["diff"], "pct_of_target": r["diff_pct_of_target"]}, label=pm.SHAPE_LABEL,
                                      note=("%s。" % pm.SHAPE_LABEL) + ("モデルと基準輪郭を比較" if r["comparable"] else "比較不能")
                                           + ("" if not r["note"] else "; " + r["note"])))
    # ---- T: how much of every segment is excluded from S7 (in_S7 = false)?  always reported; above the limit -> INVALID
    validity_fail = []
    shares = in_s7_shares(poly, s7)
    lim_share = float(S["in_s7_false_max_share_pct"])
    for seg in SEGS:
        sh = shares.get(seg) or {}
        for key, nm in (("target_pct", "in_s7_false_share_pct"), ("model_pct", "model_samples_not_counted_share_pct")):
            checks.append(ct.report_value("T", nm, sh.get(key), "% of the segment", sub=seg, target={"validity_limit_le": lim_share},
                                          note=("基準輪郭：in_S7=false の区間の弧長。遮蔽補完のためS7に算入しない" if key == "target_pct" else
                                                "モデル：最近接の基準区間が in_S7=false なのでS7に算入しない標本")
                                               + "。%s %% を超えると INVALID（tests/thresholds.json の interpretations.test_settings.in_s7_false_max_share_pct）" % ct._fmt(lim_share)))
            if sh.get(key) is not None and sh[key] > lim_share:
                validity_fail.append("区間 '%s' の%sの %.1f %% が in_S7=false によりS7から除外された（上限 %s %%）。この区間のS7判定は対象範囲が足りない"
                                     % (seg, "基準輪郭" if key == "target_pct" else "モデル標本", sh[key], ct._fmt(lim_share)))
    # ---- T: does the front face come down to the still water?  (S3 from Z = 0 measures to a level the model must reach)
    checks.append(ct.report_value("T", "reached_still_water", m.get("reached_still_water"), "bool",
                                  note="内側の弧の最深点以後の輪郭最低点は Z＝0 より画面高の %s %% 上（許容差 %s %%）"
                                       % (ct._fmt(m.get("trough_level_above_still_pct_h")), ct._fmt(m.get("reached_still_water_tol_pct_h")))))
    if m.get("reached_still_water") is False:
        validity_fail.append("前面が静水面へ届かない。波前方の輪郭最低点は Z＝0 より画面高の %s %% 上"
                             "（許容差 %s %%）。この場合、Z＝0基準のS3はモデルが到達しない水位からの高さ。S3.from_model_trough = %s"
                             % (ct._fmt(m.get("trough_level_above_still_pct_h")), ct._fmt(m.get("reached_still_water_tol_pct_h")),
                                ct._fmt(pc["S3_from_model_trough"]["height_err_pct_h"])))
    # ---- T: is the TARGET segmented like the model?  (json joints vs the library's detection on the same polyline)
    sc = bm.get("segmentation_check")
    if sc:
        for key, nm in (("crest", "seg_crest_dist_pct_h"), ("head_tip", "seg_head_tip_dist_pct_h"), ("inner_deepest", "seg_deepest_dist_pct_h")):
            it = sc["items"][key]
            checks.append(ct.report_value("T", nm, it["dist_pct_h"], "% of image height", target={"json_H": it["json_H"], "detected_H": it["detected_H"]},
                                          where=None if it["detected_H"] is None else ct.where_point(F, it["detected_H"]),
                                          note="基準輪郭：JSON接合点に基づく地標と同じ折線で検出した地標の距離（先端規則 '%s'）。"
                                               "%s %% を超えると INVALID" % (sc["tip_rule"], ct._fmt(sc["tol_pct_h"]))))
        checks.append(ct.report_value("T", "base_head_lobes", sc["detected_head_lobes"]["n_lobes"], "count",
                                      note="基準輪郭の波頂から最深点までに、Xが画面高の %s %% 以上右から左へ戻る回数（1なら単一の先端）"
                                           % ct._fmt(sc["detected_head_lobes"]["lobe_reversal_pct_h"])))
    return {"checks": checks, "notes": notes, "m": m, "bm": bm, "poly": poly, "pc": pc, "s7": s7, "dv": dv,
            "s8pack": (js, jd, judged, s_tip), "consistency": consistency, "P": P, "w_rows": w_rows, "segmentation_check": sc,
            "shape_rows": shape_rows, "s7_split": split, "in_s7_shares": shares, "validity_fail": validity_fail}


def segmentation_validity(sc):
    """基準輪郭の分段整合性から (ok, note) を返す。検査未実施は有効として扱う。"""
    if not sc or sc.get("consistent"):
        return True, None
    parts = []
    for key, it in sc["items"].items():
        parts.append("%s %s" % (key, "n/a" if it["dist_pct_h"] is None else "%.3f %%" % it["dist_pct_h"]))
    return False, ("目標とモデルの分段が一致しない。基準輪郭のJSON接合点と同じ折線上でライブラリが検出した地標の差が画面高の %s %% を超える"
                   "（%s、基準輪郭の張り出し：JSON %s／検出 %s、検出した波頭の瓣数 %d）。"
                   "モデルは常に検出値で分段されるため、S5とS7では異なる区間を比較してしまう。この実行は FAIL ではなく INVALID。"
                   "JSON接合点を pm.detect_landmarks(polyline) の位置に置くか、波頭を単一の先端にする。"
                   % (ct._fmt(sc["tol_pct_h"]), ", ".join(parts), sc["json_overhanging"], sc["detected_overhanging"],
                      sc["detected_head_lobes"]["n_lobes"]))


def target_self_check(F, S, bc, P=None):
    """基準輪郭を自身と比較する。右端まで静水面を延長し、モデル側の分段は他のモデルと同様に検出する。"""
    poly = pm.base_contour_polyline(bc)
    pts = poly["pts_H"]
    if pts[-1, 0] < F.x_right - 1e-6:
        pts = np.concatenate([pts, [[F.x_right, min(0.0, float(pts[-1, 1]))]]])
    J0 = judge_profile(F, S, pts, bc, poly=poly, P=P)
    by_id = {c["id"]: {"measured": c["measured"], "spec": c["tiers"]["spec"]["status"],
                       "user_relaxed_5pct": c["tiers"]["user_relaxed_5pct"]["status"]} for c in J0["checks"] if not c["info_only"]}
    bad = lambda t: sorted(k for k, v in by_id.items() if v[t] in ("FAIL", "NOT_MEASURABLE"))  # noqa: E731
    return {"by_id": by_id, "failed_spec": bad("spec"), "failed_relaxed": bad("user_relaxed_5pct"),
            "n_x_reversals_after_crest": _count_reversals(poly, P or pm.get_params())}


def _count_reversals(poly, P):
    """基準輪郭の波頂以後でXが右から左へ戻る回数を数える。単一の先端なら1。"""
    return pm.count_x_reversals(poly["pts_H"][poly["crest_index"]:, 0], float(pm.pct_h_to_H(P["tip_min_reversal_pct_h"])))


def run(ctx, contour_path=None, run_dir=None):
    """ctx.objs の終幕フレームで S1–S8 を測定し、結果を辞書と出力先に保存する。"""
    F, S = ctx.F, ctx.settings
    run_dir = run_dir or ctx.run_dir
    contour_path = contour_path or ctx.contour_path
    scale = float(ctx.args.res_scale) if getattr(ctx.args, "res_scale", None) else float(S["shape_res_scale"])
    sw = ct.StopWatch()
    bc = pm.load_base_contour(paths.require_file(contour_path))
    P = pm.get_params()

    ctx.scene.frame_set(int(ctx.final_frame))
    rect = silhouette.ViewRect.from_cam_print(H=ctx.H, scale=scale)
    validity_notes = []
    try:
        prof, mask, info = silhouette.profile_of_objects(ctx.objs, rect=rect, water_z=ctx.water_z, exact=True)
    except silhouette.ProfileError as exc:
        result = {"schema": ct.RESULT_SCHEMA, "test": TEST_NAME, "run_dir": run_dir, "context": ctx.describe(),
                  "checks": [], "summary": ct.summarize([], False, ["輪郭を取得できない: %s" % exc], expected=ct.EXPECTED_IDS[TEST_NAME], audit=ctx.audit()),
                  "outputs": {}}
        ct.write_result(run_dir, result)
        log("[shape] 有効性：輪郭を取得できない: %s" % exc)
        return result
    t_sil = sw.lap()
    # ---- validity of the silhouette (a failed item makes the whole test FAIL: numbers are not trustworthy)
    valid = True
    if not prof["complete"]:
        valid = False
        validity_notes.append("輪郭が不完全：境界の追跡が画面の %s 側で終了した" % prof["end_border"])
    if prof["holes"]["hole_area_px"] > 0:
        valid = False
        validity_notes.append("シルエットに未充填の穴が%d個ある。合計%d px、充填後シルエットの %.2f %%（CAM_print から見て薄片が閉じていない）。最大穴の範囲 %s"
                              % (prof["holes"]["n_holes"], prof["holes"]["hole_area_px"], 100.0 * prof["holes"]["hole_area_frac"],
                                 prof["holes"].get("largest_hole_bbox")))
    if prof.get("n_cracks_without_exact_data"):
        validity_notes.append("正確な交点データがない境界の隙間が%d箇所（精度は±0.5 px）" % prof["n_cracks_without_exact_data"])
    if info.get("mesh_area_px") == 0:
        valid = False
        validity_notes.append("CAM_print から見た静水面より上の被覆面積が0 pxで、輪郭は水体のみ。"
                              "開いた薄片を真横から見ると投影面積がない（docs/measurement_definitions.md 第1.1節）")
    # ---- 2026-09-20: geometry the measurement layer had to drop must never pass silently
    n_nf, n_dt = int(info.get("n_nonfinite_vertices") or 0), int(info.get("n_dropped_triangles") or 0)
    if n_nf or n_dt:
        valid = False
        validity_notes.append("有限でない幾何：フレーム%dで NaN／無限大の座標を持つ頂点が%d個、シルエットから除かれた三角形が%d面ある"
                              "（最初の頂点番号 %s）。測定値はこれらの三角形を除いた網目の値である"
                              % (ctx.final_frame, n_nf, n_dt, (info.get("mesh") or {}).get("nonfinite_vertex_indices") or info.get("nonfinite_vertex_indices")))
    comp = prof["components"]
    islands = [c for c in (comp.get("removed") or []) if c.get("kind") == "island"]
    if int(comp.get("n_removed_islands") or 0) > 0:
        valid = False
        desc = "; ".join("%d px、範囲 X %.3f..%.3f H、Z %.3f..%.3f H（原画像素 x %.0f..%.0f、y %.0f..%.0f）"
                         % ((c["area_px"], c["bbox_H"][0], c["bbox_H"][2], c["bbox_H"][1], c["bbox_H"][3])
                            + (F.H_to_px(c["bbox_H"][0], 0.0)[0], F.H_to_px(c["bbox_H"][2], 0.0)[0], F.H_to_px(0.0, c["bbox_H"][3])[1], F.H_to_px(0.0, c["bbox_H"][1])[1]))
                         for c in islands[:5])
        validity_notes.append("離れたシルエット成分：主成分につながらない%d個、合計%d pxが輪郭追跡前に除かれた"
                              "（この解像度での微小片上限 %.4g px）：%s。輪郭とS値はこれらを除いた場面を示す。"
                              "空洞や波の前方に立つ物体は三次元形状の欠陥（旧仕様第5節の注2）"
                              % (comp["n_removed_islands"], comp.get("removed_islands_area_px", 0), comp.get("speck_max_area_px") or float("nan"), desc))
    J = judge_profile(F, S, prof["H"], bc, P=P)
    checks, m, bm, poly, pc, s7, dv, consistency = J["checks"], J["m"], J["bm"], J["poly"], J["pc"], J["s7"], J["dv"], J["consistency"]
    validity_notes += J["notes"]
    rec_u, note_u = ct.untested_objects_report(ctx)
    checks.append(rec_u)
    if note_u:
        validity_notes.append(note_u)
    if paths.norm(contour_path) != paths.norm(paths.BASE_CONTOUR_JSON):
        validity_notes.append("注意（判定に影響しない）：正式な target/base_contour.json ではなく %s と比較した" % paths.norm(contour_path))
    if J["validity_fail"]:
        valid = False
        validity_notes += J["validity_fail"]
    for nm_, v_, unit_, note_ in (("n_nonfinite_vertices", n_nf, "count", "評価網目の NaN／無限大の座標を持つ頂点。0より大きければ INVALID"),
                                  ("n_dropped_triangles", n_dt, "count", "有限でない頂点のためシルエットから除かれた三角形。0より大きければ INVALID"),
                                  ("n_removed_islands", int(comp.get("n_removed_islands") or 0), "count",
                                   "微小片の上限（この解像度で %s px）を超えるのに除かれたシルエット成分。合計 %s px。0より大きければ INVALID"
                                   % (ct._fmt(comp.get("speck_max_area_px")), comp.get("removed_islands_area_px"))),
                                  ("n_removed_specks", int(comp.get("n_removed_specks") or 0), "count",
                                   "微小片の上限未満で除かれた成分。合計 %s px（ラスタの細片。報告のみ）" % comp.get("removed_specks_area_px"))):
        checks.append(ct.report_value("T", nm_, v_, unit_, note=note_))
    # ---- target and model must be segmented the same way (json joints of the base contour vs the library's detection)
    seg_ok, seg_note = segmentation_validity(J["segmentation_check"])
    if not seg_ok:
        valid = False
        validity_notes.append(seg_note)
    # ---- 目標輪郭の自己検査。基準輪郭の完全な複製も失敗する検査では、モデルの失敗から形状の差を論じられない。
    # target/base_contour.json で 2026-09-20 に確認した。
    target_self = target_self_check(F, S, bc, P)
    for c in checks:
        ts = target_self["by_id"].get(c["id"])
        if ts is not None:
            c["target_self_check"] = ts
    if target_self["failed_spec"]:
        validity_notes.append("基準輪郭自身が次の検査に合格しない：%s。幾何学的に同じモデルでも失敗する。"
                              "モデルは検出点、基準輪郭はJSON接合点で分段されるか、基準輪郭自身がS8で滑らかでない。"
                              "各検査の target_self_check を参照" % ", ".join(target_self["failed_spec"]))
    t_measure = sw.lap()

    # ---- outputs
    outputs = save_images(ctx, run_dir, prof, mask, rect, m, bm, bc, poly, dv, s7, J["s8pack"], P, J["w_rows"], J["shape_rows"], J["s7_split"])
    t_img = sw.lap()
    audit = ctx.audit(effective={"shape_res_scale": (scale, "--res-scale" if getattr(ctx.args, "res_scale", None) else None)}, measure_params=P)
    summary = ct.summarize(checks, valid, validity_notes, expected=ct.EXPECTED_IDS[TEST_NAME], audit=audit)
    result = {
        "schema": ct.RESULT_SCHEMA, "test": TEST_NAME, "run_dir": run_dir, "context": ctx.describe(),
        "frame": int(ctx.final_frame), "mask": {"resolution": [rect.width_px, rect.height_px], "scale": scale, "exact": True,
                                                  "n_triangles": info.get("n_triangles"), "mesh_area_px": info.get("mesh_area_px"), "holes": prof["holes"], "components": prof["components"],
                                                  "complete": prof["complete"], "end_border": prof["end_border"]},
        "summary": summary, "checks": checks,
        "settings_audit": audit,
        "interpretation_notes": {k: ct.INTERPRETATION_NOTES[k] for k in ("tiers", "verdicts", "validity", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "segmentation", "W",
                                                                         "report_only_shape")},
        "S8_note": ct.INTERPRETATION_NOTES["S8"],
        "measurements": {"model": {k: m[k] for k in m if k not in ("params",)}, "base_contour": {k: bm[k] for k in bm if k not in ("params",)},
                         "position_checks": pc, "S7": s7, "S7_local_vs_library": consistency, "measure_params": m["params"],
                         "W_compare": {"label": pm.WIDTH_LABEL, "rows": J["w_rows"]},
                         "shape_compare": {"label": pm.SHAPE_LABEL, "rows": J["shape_rows"]},
                         "S7_underside_belly": J["s7_split"], "in_S7_false_shares_pct": J["in_s7_shares"],
                         "geometry_dropped": {"n_nonfinite_vertices": n_nf, "n_dropped_triangles": n_dt, "per_object": (info.get("mesh") or {}).get("objects")},
                         "target_segmentation_check": J["segmentation_check"]},
        "target_self_check": {k: target_self[k] for k in ("failed_spec", "failed_relaxed", "n_x_reversals_after_crest")},
        "outputs": outputs, "seconds": {"silhouette": t_sil, "measure": t_measure, "images": t_img},
    }
    ct.write_result(run_dir, result)
    ct.log_checks(checks, "test_shape frame %d (%dx%d px)" % (ctx.final_frame, rect.width_px, rect.height_px))
    log_width_table(J["w_rows"])
    for ln in shape_table_lines(J["shape_rows"], s7):
        log("[shape] " + ln)
    for n in validity_notes:
        log("[shape] validity: " + n)
    return result


def width_table_lines(rows):
    """報告専用の寸法指標を ASCII 表にする。overlay_widths_1600.png にも描画する。"""
    L = ["W: %s (no thresholds)" % pm.WIDTH_LABEL,
         "%-24s %10s %10s %10s %9s %9s  %s" % ("quantity", "model", "base", "diff", "diff %", "diff %h", "")]
    for r in rows:
        if r["model"] is None and r["target"] is None:
            continue
        f = lambda v, nd=4: "n/a" if v is None else ("%." + str(nd) + "f") % v  # noqa: E731
        L.append("%-24s %10s %10s %10s %9s %9s  %s" % (r["name"], f(r["model"]), f(r["target"]), f(r["diff"]),
                                                      "n/a" if r["diff_pct_of_target"] is None else "%+.2f" % r["diff_pct_of_target"],
                                                      "n/a" if r["diff_pct_h"] is None else "%+.2f" % r["diff_pct_h"],
                                                      "" if r["comparable"] else "(not comparable)"))
    return L


def shape_table_lines(shape_rows, s7):
    """自分自身の高さを基準とした形状指標と、符号付き S7 偏差の ASCII 表を作る。"""
    L = ["W.own_h: %s" % pm.SHAPE_LABEL,
         "%-30s %10s %10s %9s  %s" % ("quantity (length / own h)", "model", "base", "diff %", "")]
    f = lambda v, nd=4: "n/a" if v is None else ("%." + str(nd) + "f") % v  # noqa: E731
    for r in shape_rows or []:
        if r["model"] is None and r["target"] is None:
            continue
        L.append("%-30s %10s %10s %9s  %s" % (r["name"], f(r["model"]), f(r["target"]),
                                             "n/a" if r["diff_pct_of_target"] is None else "%+.2f" % r["diff_pct_of_target"],
                                             "" if r["comparable"] else "(not comparable: back outside the frame / section kind differs)"))
    # オーバーレイは draw.py の ASCII 専用フォントを使うため、描画ラベルは英数字にする。
    L.append("S7 signed deviation (positive = outside):")
    for seg in SEGS:
        r = (s7 or {}).get(seg)
        if not r:
            continue
        mb = r["model_to_base"]
        L.append("  %-10s signed mean %7s   p05 %7s   p95 %7s   (unsigned mean %s, p95 %s) %% of image height"
                 % (seg, "n/a" if r.get("signed_mean_dev_pct_h") is None else "%+.3f" % r["signed_mean_dev_pct_h"],
                    "n/a" if mb.get("signed_p05_pct_h") is None else "%+.3f" % mb["signed_p05_pct_h"],
                    "n/a" if mb.get("signed_p95_pct_h") is None else "%+.3f" % mb["signed_p95_pct_h"], f(r.get("mean_dev_pct_h"), 3), f(r.get("p95_dev_pct_h"), 3)))
    return L


def log_width_table(rows):
    for ln in width_table_lines(rows):
        log("[shape] " + ln)


# ------------------------------------------------------------------------------------ 画像
def shape_overlay_items(F, m, bm, split=None):
    """報告専用の自己高さ断面と、内側弧を分ける脇の線・印を描く。
    モデルは紫、基準輪郭は濃緑の破線で、絶対高さの線から上下にずらす。"""
    pls, mks = [], []
    z_still = float((m.get("params") or {}).get("z_still_H", 0.0))
    for d, col, dy, dash in ((m, "purple", -5.0, None), (bm, DARKGREEN, 14.0, (4, 5))):
        for tag, sec in ((d.get("shape") or {}).get("sections") or {}).items():
            if not sec.get("measurable"):
                continue
            y = float(F.H_to_px(0.0, sec["level_H"])[1]) + dy
            xs = [float(F.H_to_px(v, 0.0)[0]) for v in (sec["x_back_H"], sec["x_front_H"])]
            pls.append({"px": np.array([[xs[0], y], [xs[1], y]]), "color": col, "width": 1.5, "dash": dash})
    _ = z_still
    for a, col, lab in (((split or {}).get("model_armpit"), "purple", "armpit"), ((split or {}).get("base_armpit"), DARKGREEN, None)):
        if a:
            mks.append({"px": F.H_to_px(*a["H"]), "kind": "x", "color": col, "size": 8, "label": lab, "offset": (14, 6)})
    return pls, mks


def width_overlay_items(F, m, bm, w_rows):
    """報告専用の断面幅の線・印を原画ピクセル座標で作る。
    モデルは紺、基準輪郭は 8 px 下の緑破線。x_back／x_inner／x_front に目盛を置く。"""
    pls, mks = [], []
    rel = {r["name"]: r for r in (w_rows or [])}
    for tag, sec in m["W"]["sections"].items():
        bsec = bm["W"]["sections"].get(tag)
        y = float(F.H_to_px(0.0, sec["level_H"])[1])
        for d, col, dy, dash in ((sec, "navy", 0.0, None), (bsec, "green", 8.0, (10, 6))):
            if not d or not d["measurable"]:
                continue
            xs = [float(F.H_to_px(v, 0.0)[0]) for v in (d["x_back_H"], d["x_front_H"])]
            pls.append({"px": np.array([[xs[0], y + dy], [xs[1], y + dy]]), "color": col, "width": 2.0, "dash": dash})
            for v in (d["x_back_H"], d["x_inner_H"], d["x_front_H"]):
                if v is not None:
                    xv = float(F.H_to_px(v, 0.0)[0])
                    pls.append({"px": np.array([[xv, y + dy - 12.0], [xv, y + dy + 12.0]]), "color": col, "width": 2.0})
        if sec["measurable"]:
            r = rel.get("%s.width_full_H" % tag)
            txt = "W%s model %.3f" % (tag[1:], sec["width_full_H"])
            if r and r["target"] is not None:
                txt += " base %.3f H" % r["target"]
                if r["diff_pct_of_target"] is not None:
                    txt += " (%+.1f%%)" % r["diff_pct_of_target"]
            if sec["back_clipped_at_frame_edge"]:
                txt += " [from frame edge]"
            mks.append({"px": [float(F.H_to_px(sec["x_front_H"], 0.0)[0]), y], "kind": "o", "color": "navy", "size": 4,
                        "label": txt, "offset": (14, 6)})        # below the line: the landmark labels sit above their points
    return pls, mks


def save_images(ctx, run_dir, prof, mask, rect, m, bm, bc, poly, dv, s7, s8pack, P, w_rows=None, shape_rows=None, split=None):
    F = ctx.F
    out = {}
    use_painting = ctx.background == "painting" or (ctx.background == "auto" and (bc.get("image") or {}).get("path"))
    if use_painting:
        base = imgio.load_painting_rgb().copy()
    else:
        base = draw.canvas(F.height_px, F.width_px, "white")
    full_mask = ct.upsample_mask(mask, F.width_px, F.height_px)
    draw.overlay_mask(base, full_mask, "blue", 0.22 if use_painting else 0.30)
    model_px = F.pts_H_to_px(prof["H"])
    base_px = F.pts_H_to_px(poly["pts_H"])
    flag = poly["in_S7"]
    base_counted = np.where(flag[:, None], base_px, np.nan)
    base_excl = np.where((~flag | ~np.roll(flag, 1) | ~np.roll(flag, -1))[:, None], base_px, np.nan)
    pls = [{"px": base_counted, "color": "lime", "width": 3.0}, {"px": base_excl, "color": "yellow", "width": 3.0, "dash": (10, 7)}]
    for name in ("back", "head", "inner_arc", "trough_run"):
        rng = m["segments"].get(name)
        if rng is None and name == "head" and m["segments"].get("front"):
            rng, name = m["segments"]["front"], "head"
        if rng is not None and rng[1] > rng[0]:
            pls.append({"px": model_px[rng[0]:rng[1] + 1], "color": ct.SEG_COLORS[name], "width": 2.0})
    mks = []
    for key, lab in (("crest", "crest"), ("head_tip", "tip"), ("inner_deepest", "deepest")):
        if bm["landmarks"].get(key):
            mks.append({"px": F.H_to_px(*bm["landmarks"][key]["H"]), "kind": "O", "color": "green", "size": 11})
        if m["landmarks"].get(key):
            mks.append({"px": F.H_to_px(*m["landmarks"][key]["H"]), "kind": "+", "color": "red", "label": lab, "size": 12})
    # 微小領域の上限を超えて除外されたシルエット成分（INVALID）を赤枠で示す。
    for comp_ in (prof.get("components") or {}).get("removed") or []:
        if comp_.get("kind") != "island":
            continue
        bx0, bz0, bx1, bz1 = comp_["bbox_H"]
        pls.append({"px": np.array([F.H_to_px(a, b) for a, b in ((bx0, bz0), (bx1, bz0), (bx1, bz1), (bx0, bz1), (bx0, bz0))], dtype=np.float64),
                    "color": "red", "width": 3.0})
        mks.append({"px": F.H_to_px(bx1, bz1), "kind": "x", "color": "red", "size": 7, "offset": (10, -8),
                    "label": "DETACHED %d px: removed before tracing -> INVALID" % comp_["area_px"]})
    from gw import frame as gw_frame
    for key, lab in (("S1_crest", "S1 spec"), ("S2_inner_arc_deepest", "S2 spec"), ("S6_claw_rightmost", "S6 bound")):
        mks.append({"px": F.pct_to_px(*gw_frame.SPEC_LANDMARKS_PCT[key]), "kind": "x", "color": "blue", "label": lab, "size": 9, "offset": (12, 16)})
    legend = [("model contour: back red / head orange / inner arc magenta", "red"),
              ("base contour: lime (counted in S7), yellow dashes (in_S7 = false)", "green"),
              ("+ model landmark   O base-contour landmark   x spec value", "blue")]
    ttl = "test_shape frame %d: %s" % (ctx.final_frame, ",".join(o.name for o in ctx.objs))
    sc = 1600.0 / F.width_px
    wpls, wmks = width_overlay_items(F, m, bm, w_rows)
    legend_w = legend + [("section widths at Z = 0.25 / 0.5 / 0.75 H: navy = model, green dashes = base contour (REPORT ONLY)", "navy")]
    # 全体画像には断面線のみ描く。数値は特徴点ラベルと重なるため overlay_widths_1600.png へ分ける。
    img = ct.draw_view(base, (0, 0, F.width_px, F.height_px), sc, pls + wpls, mks, ttl,
                       legend + [("REPORT ONLY section widths at Z = 0.25 / 0.5 / 0.75 H: navy = model, green dashes = base; numbers: overlay_widths_1600.png", "navy")])
    out["overlay_full"] = imgio.save_png(os.path.join(run_dir, "overlay_full_1600.png"), img)
    # ---- dedicated picture of the report-only size metrics: contours + sections + the table
    if w_rows:
        spls, smks = shape_overlay_items(F, m, bm, split)
        imgw = ct.draw_view(base, (0, 0, F.width_px, F.height_px), sc, pls + wpls + spls, wmks + smks,
                            "report-only size metrics (no thresholds; pending user decision)",
                            legend_w[-1:] + [("sections at 0.25 / 0.5 / 0.75 of each contour's OWN crest height: purple = model, dark-green dashes = base (REPORT ONLY)", "purple")])
        lines = width_table_lines(w_rows)
        lines.append("area = between the contour [left frame edge .. trough end] and Z = 0 (H^2); widths in H; diff %h = % of image height")
        lines.append("")
        lines += shape_table_lines(shape_rows, s7)
        panel = draw.canvas(22 * len(lines) + 12, imgw.shape[1], "white")
        for k, ln in enumerate(lines):
            draw.text(panel, 8, 6 + 22 * k, ln, "black", 2)
        out["overlay_widths"] = imgio.save_png(os.path.join(run_dir, "overlay_widths_1600.png"), draw.vstack([imgw, panel], gap=0))

    def box_around(points, half=(330, 240)):
        p = np.asarray([q for q in points if q is not None], dtype=np.float64)
        c = p.mean(axis=0)
        hw = max(half[0], 0.5 * (p[:, 0].max() - p[:, 0].min()) + 120)
        hh = max(half[1], 0.5 * (p[:, 1].max() - p[:, 1].min()) + 90)
        return (int(c[0] - hw), int(c[1] - hh), int(c[0] + hw), int(c[1] + hh)), min(2.0, 1500.0 / (2 * hw))

    def lm_px(d, key):
        return None if not d["landmarks"].get(key) else np.array(F.H_to_px(*d["landmarks"][key]["H"]), dtype=np.float64)

    crops = [("crop_crest", [lm_px(m, "crest"), lm_px(bm, "crest")]),
             ("crop_head_tip", [lm_px(m, "head_tip"), lm_px(bm, "head_tip")]),
             ("crop_inner_deepest", [lm_px(m, "inner_deepest"), lm_px(bm, "inner_deepest")]),
             ("crop_left_end", [model_px[0], base_px[0]]),
             ("crop_trough", [lm_px(m, "trough_end"), base_px[-1]])]
    if m["S4"].get("mid_max_at"):
        crops.append(("crop_back_steepest", [np.array(F.H_to_px(*m["S4"]["mid_max_at"]["H"]), dtype=np.float64)]))
    worst = [(s7[s]["worst_point"]["dev_pct_h"], s7[s]["worst_point"]["H"], s) for s in SEGS if s7.get(s) and s7[s].get("worst_point")]
    if worst:
        w = max(worst)
        crops.append(("crop_worst_S7_%s" % w[2], [np.array(F.H_to_px(*w[1]), dtype=np.float64)]))
    for name, pts in crops:
        if all(p is None for p in pts):
            continue
        box, scz = box_around(pts)
        imgc = ct.draw_view(base, box, scz, pls, mks, "%s  (x%.2g)" % (name, scz), None)
        out[name] = imgio.save_png(os.path.join(run_dir, name + ".png"), imgc)
    # 頭部領域を一つの視点で示す。
    hp = [p for p in (lm_px(m, "crest"), lm_px(m, "head_tip"), lm_px(m, "inner_deepest"), lm_px(bm, "head_tip")) if p is not None]
    if len(hp) >= 2:
        box, scz = box_around(hp, half=(200, 150))
        out["crop_head_region"] = imgio.save_png(os.path.join(run_dir, "crop_head_region.png"),
                                                 ct.draw_view(base, box, scz, pls, mks, "head region (x%.2g)" % scz, legend))

    # ---- deviation vs arc length
    lim_s = {k: paths.threshold("S7", k, "spec") for k in ("mean_dev_pct_h", "p95_dev_pct_h")}
    lim_r = paths.threshold("S7", "p95_dev_pct_h", "user_relaxed_5pct")
    plots = []
    for direction, xlabel in (("model_to_base", "arc length along the MODEL contour from the left frame edge [% of image height]"),
                              ("base_to_model", "arc length along the BASE contour from the left frame edge [% of image height]")):
        series, spans = [], []
        for seg in SEGS:
            if not dv.get(seg):
                continue
            sd = dv[seg][direction]
            x = pm.H_to_pct_h(sd["s_H"])
            y = np.where(sd["counted"], sd["dev_pct_h"], np.nan)
            series.append({"label": seg, "x": x, "y": y, "color": ct.SEG_COLORS[seg], "width": 2})
            if (~sd["counted"]).any():
                series.append({"label": seg + " (not counted)", "x": x, "y": np.where(sd["counted"], np.nan, sd["dev_pct_h"]), "color": "gray", "width": 1})
            if x.size:
                spans.append({"x0": float(x.min()), "x1": float(x.max()), "label": seg, "color": ct.SEG_COLORS[seg], "alpha": 0.07})
        ymax = max([float(np.nanmax(s["y"])) for s in series if np.isfinite(s["y"]).any()] + [lim_s["p95_dev_pct_h"] * 1.3])
        plots.append({"series": series, "title": "S7 deviation, %s" % direction.replace("_", " "), "xlabel": xlabel,
                      "ylabel": "% of img height", "size": (1500, 420), "spans": spans, "ylim": (0.0, ymax * 1.08),
                      "hlines": [{"y": lim_s["mean_dev_pct_h"], "label": "spec mean limit", "color": "orange"},
                                 {"y": lim_s["p95_dev_pct_h"], "label": "spec p95 limit", "color": "red"}]
                                + ([{"y": lim_r, "label": "relaxed 5 %", "color": "purple"}] if ymax > 0.8 * lim_r else [])})
    out["plot_S7_deviation"] = imgio.save_png(os.path.join(run_dir, "plot_S7_deviation.png"),
                                              plot.multi_plot(plots, title="S7: deviation vs arc length (frame %d)" % ctx.final_frame))
    # ---- S8 turn per junction
    js, jd, judged, s_tip = s8pack
    if js.size:
        o = np.argsort(js)
        x = pm.H_to_pct_h(js[o])
        ser = [{"label": "judged", "x": x, "y": np.where(judged[o], jd[o], np.nan), "color": "blue", "marker": "o", "marker_size": 2, "line": False},
               {"label": "tip zone (not judged)", "x": x, "y": np.where(judged[o], np.nan, jd[o]), "color": "gray", "marker": "x", "marker_size": 3, "line": False}]
        lim8 = paths.threshold("S8", "max_tangent_diff_deg", "spec")
        vl = [{"x": float(pm.H_to_pct_h(m["landmarks"]["crest"]["s"])), "label": "crest", "color": "red"}]
        if s_tip is not None:
            vl.append({"x": float(pm.H_to_pct_h(s_tip)), "label": "head tip", "color": "green"})
        ymax = max(float(jd.max()), lim8) * 1.1
        img8 = plot.line_plot(ser, title="S8: tangent change between neighbouring samples (spacing %.3g %%, %d phases)" % (P["s8_spacing_pct_h"], P["s8_n_phases"]),
                              xlabel="arc length along the MODEL contour [% of image height]", ylabel="deg", size=(1500, 440),
                              ylim=(0.0, ymax), hlines=[{"y": lim8, "label": "limit %g deg" % lim8, "color": "red"}], vlines=vl)
        out["plot_S8_turn"] = imgio.save_png(os.path.join(run_dir, "plot_S8_turn.png"), img8)
    # ---- S4 slope curve of the back
    ser = []
    for lab, d, col in (("model", m, "red"), ("base contour", bm, "green")):
        sc4 = d["S4"].get("slope_curve")
        if sc4:
            x = pm.H_to_pct_h(np.asarray(sc4["s_H"]) - d["landmarks"]["crest"]["s"])
            ser.append({"label": lab, "x": x, "y": sc4["deg"], "color": col})
    if ser:
        img4 = plot.line_plot(ser, title="S4: slope of the back (chord over %.3g %% of image height)" % P["s4_tangent_window_pct_h"],
                              xlabel="arc length relative to the crest [% of image height]", ylabel="deg", size=(1500, 440),
                              hlines=[{"y": 25.0, "label": "spec ~25 (left end)"}, {"y": 47.0, "label": "spec ~47 (max)"}, {"y": 8.0, "label": "spec ~8 (before crest)"}])
        out["plot_S4_back_slope"] = imgio.save_png(os.path.join(run_dir, "plot_S4_back_slope.png"), img4)
    return out


def main():
    ap = argparse.ArgumentParser(description="great_wave shape test S1-S8 (final frame)")
    ct.add_common_args(ap)
    args = bootstrap.parse_args(ap)

    def body(run_dir):
        ctx = ct.setup_context(args, TEST_NAME, run_dir=run_dir)
        result = run(ctx)
        log("[shape] results: %s" % result["run_dir"])
        return result

    ct.guarded_main(TEST_NAME, args, body)


if __name__ == "__main__":
    main()
