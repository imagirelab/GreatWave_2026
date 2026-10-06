# -*- coding: utf-8 -*-
"""P1 の 1 本の計算の解析：巻くか（巻き波の判定）、いつ・どこで、頂の高さ、断面の形の値（原画の読みと同じ定義）。
py -3.10（numpy・scipy・cv2）。使い方: py -3.10 p1_analyze.py <run_dir> [--quiet]

断面の粒子（snap_XXXX.npz、|z|<1.05 m の薄い切り口）を 0.25 m の升目に落として水の形を作る。
narrow band なので水面から 4〜6 m より深い所には粒子がない。升目の空いた所のうち、上の空気とつながらず、
窓の左右か下の端に触れる大きな空き（＝深い所の水）は水として埋める。窓の中に閉じた空き（上の空気とつながらず、
窓の端に触れない、1 m² 以上）は「閉じた空洞」の候補として残す。1 m² 未満の空きは粒子のすき間として埋める。

海底より下の升目は水と同じに扱う（浅い坂で、水面の帯と海底に沿った粒子の帯の間のすき間を深い所の水として埋めるため）。
窓は断面の粒子を書き出した x の範囲の中に限る。

判定（指示の定義）：
- B = 頂の水の速さ u / 頂の進む速さ c。u は頂の近く（|x-xc|<2 m、y>yc-1.5 m）の粒子の水平の流速の最大。
  c は前の面の半分の高さ（0.5 Hc）の点の x の時間の変化（±0.5 秒の直線の当てはめ）。B > 0.85 を砕けの始まりとする（Barthelemy ら 2018 の目安）。
  砕けの始まりは B > 0.85 が 2 枚（1/6 秒）続いた最初のコマ。
- 前の面が垂直を過ぎた：頂の近くの窓で、上から水→空気（2 升以上）→水の列が 4 列以上ある（張り出し）コマが、3 枚（0.25 秒）続いた最初のコマ。
- 空洞が閉じた・ほぼ閉じた：張り出しの後で、閉じた空き（上の空気とつながらない 1 m² 以上。重心が頂の 5 m 後ろより前、0.15 Hc より上）ができた、
  またはかぶりが 0.15 Hc 以上に育ってから唇の先の下の空気の高さが 0.1 Hc 未満になった。
巻き波 = 3 つとも満たす。
形の値（原画と同じ定義。Hc＝頂の高さ）：唇の届き＝唇の先 x − 頂 x、落ち＝頂 y − 唇の先 y、
かぶり＝唇の先 x − 内側の壁 x（覆われた空気の一番後ろ）、空洞の幅/高さ＝かぶり / (唇の先 y − 0.2 Hc)、
前の面：内側の壁の点から、前の面の 0.2 Hc の高さの点までの弦の角度と、弦からの凹み、背：頂から 0.75 Hc まで下がる横の長さと傾き。
出力：<run_dir>/analysis.json
"""
import sys, os, json, glob, math
import numpy as np
import cv2
from scipy import ndimage as ndi

DX = 0.25
YMIN, YMAX = -20.0, 34.0


def set_dx(P):
    """升目の大きさ：粒子の間隔の 0.7 倍（0.35 m の粒子で 0.25 m）。粒子が粗いと升目が空きすぎるため。"""
    global DX
    DX = max(0.175, round(0.7 * float(P.get("dp", 0.35)) / 0.025) * 0.025)


def load_snaps(rd):
    fs = sorted(glob.glob(os.path.join(rd, "snap_*.npz")))
    return fs


def raster(x, y, x0, x1):
    nx = int(round((x1 - x0) / DX)); ny = int(round((YMAX - YMIN) / DX))
    ix = ((x - x0) / DX).astype(np.int64); iy = ((y - YMIN) / DX).astype(np.int64)
    m = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    cnt = np.zeros((ny, nx), np.int32)
    np.add.at(cnt, (iy[m], ix[m]), 1)
    return cnt


def water_mask(cnt):
    """粒子の升目 → 水の形（ny, nx）。行 0 が下。戻り：water（bool）、closed_air（閉じた空洞の候補 bool）"""
    w = cnt > 0
    w = ndi.binary_closing(w, structure=np.ones((3, 3)), iterations=1, border_value=0) | w
    air = ~w
    lab, n = ndi.label(air)
    ny, nx = w.shape
    top_labels = set(np.unique(lab[-1, :])) - {0}
    side_labels = (set(np.unique(lab[:, 0])) | set(np.unique(lab[:, -1])) | set(np.unique(lab[0, :]))) - {0}
    sizes = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    water = w.copy()
    closed = np.zeros_like(w)
    for L in range(1, n + 1):
        if L in top_labels:
            continue
        area = sizes[L - 1] * DX * DX
        if L in side_labels or area < 1.0:
            water[lab == L] = True      # 深い所の水、または粒子のすき間
        else:
            closed[lab == L] = True     # 閉じた空洞の候補
    return water, closed


def main_component(water):
    lab, n = ndi.label(water)
    if n == 0:
        return water
    sizes = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def column_runs(col):
    """列（下→上の bool）の水の区間 [(lo, hi), ...]（上から順）"""
    d = np.diff(np.r_[0, col.astype(np.int8), 0])
    st = np.where(d == 1)[0]; en = np.where(d == -1)[0] - 1
    return list(zip(st, en))[::-1]


def shape_metrics(water, closed, x0, xc_guess, cnt_vx=None):
    """窓の中の水の形から、頂・唇・覆われた空気・前の面・背を測る。"""
    ny, nx = water.shape
    ys = YMIN + (np.arange(ny) + 0.5) * DX
    xs = x0 + (np.arange(nx) + 0.5) * DX
    body = main_component(water)
    # 一番上の水面（列ごと）
    has = body.any(axis=0)
    jtop = np.where(has, ny - 1 - np.argmax(body[::-1, :], axis=0), -1)
    ytop = np.where(has, ys[np.clip(jtop, 0, ny - 1)] + 0.5 * DX, np.nan)
    # 頂：xc_guess の近く（-10〜+30 m）で一番高い所
    win = (xs > xc_guess - 10) & (xs < xc_guess + 30) & np.isfinite(ytop)
    if not win.any():
        return None
    ic = np.where(win)[0][np.nanargmax(ytop[win])]
    yc = float(ytop[ic])
    # 頂の x：一番高い所から 0.25 m 以内でつながる列の中ほど（平らな頂で x が跳ばないように）
    lo = ic
    while lo - 1 >= 0 and np.isfinite(ytop[lo - 1]) and ytop[lo - 1] >= yc - 0.25:
        lo -= 1
    hi_ = ic
    while hi_ + 1 < nx and np.isfinite(ytop[hi_ + 1]) and ytop[hi_ + 1] >= yc - 0.25:
        hi_ += 1
    ic = (lo + hi_) // 2
    xc = float(xs[ic])
    out = {"crest": [xc, yc]}
    # 前の面の半分の高さの所（頂より前で一番上の水面が 0.5 Hc を切る最初の x）。頂の進む速さはこの点の動きから測る
    fr_ = np.where((xs > xc) & np.isfinite(ytop) & (ytop < 0.5 * yc))[0]
    out["x_front_half"] = float(xs[fr_[0]]) if len(fr_) else None
    # 張り出し：頂の後ろ 15 m から前 40 m の列で、上から水→空気(>=2升)→水
    over_cols = []
    tube_cells = []
    for i in range(max(0, ic - int(15 / DX)), min(nx, ic + int(40 / DX))):
        runs = column_runs(body[:, i])
        if len(runs) >= 2:
            (lo1, hi1), (lo2, hi2) = runs[0], runs[1]
            gap = lo1 - hi2 - 1
            if gap >= 2 and ys[lo1] > 0.0:
                over_cols.append((i, lo1, hi1, hi2, gap))
    out["n_over_cols"] = len(over_cols)
    out["overturned"] = len(over_cols) >= 4
    if out["overturned"]:
        # 唇の先：張り出しの列のうち一番前の列の、上の水の下の端
        itip = max(c[0] for c in over_cols)
        ctip = [c for c in over_cols if c[0] == itip][0]
        xtip = float(xs[itip]); ytip = float(ys[ctip[1]])
        # 唇の先の点は、一番前の列の水の上の水の区間の中ほど（先の太さの中心）
        ytip = float(0.5 * (ys[ctip[1]] + ys[ctip[2]]))
        gap_below_tip = float(ctip[4] * DX)
        # 覆われた空気（張り出しの列の、上の水と下の水の間）
        cov = np.zeros_like(body)
        for (i, lo1, hi1, hi2, gap) in over_cols:
            cov[hi2 + 1:lo1, i] = True
        # 覆われた空気の連なりのうち唇の先の下を含むもの
        lab, n = ndi.label(cov)
        Ltip = lab[min(ctip[3] + 1, ny - 1), itip]
        tube = (lab == Ltip) if Ltip > 0 else cov
        tj, ti = np.where(tube)
        iwall = int(ti.min())
        xwall = float(xs[iwall]); ywall = float(ys[int(np.median(tj[ti == iwall]))])
        area = float(tube.sum() * DX * DX)
        dist = cv2.distanceTransform((tube | closed).astype(np.uint8), cv2.DIST_L2, 5)
        r_in = float(dist.max() * DX)
        # 等価な楕円の長さ/幅
        if len(ti) > 5:
            cov2 = np.cov(np.stack([xs[ti], ys[tj]]))
            ev = np.sort(np.linalg.eigvalsh(cov2))
            lw = float(math.sqrt(ev[1] / max(ev[0], 1e-9)))
        else:
            lw = None
        out.update({"lip_tip": [xtip, ytip], "gap_below_tip_m": gap_below_tip,
                    "inner_wall": [xwall, ywall], "covered_air_area_m2": area, "tube_inscribed_r_m": r_in,
                    "covered_air_LW": lw,
                    "lip_reach_m": xtip - xc, "lip_drop_m": yc - ytip, "overhang_m": xtip - xwall})
        Hc = yc
        out["reach_over_Hc"] = (xtip - xc) / Hc
        out["drop_over_Hc"] = (yc - ytip) / Hc
        out["overhang_over_Hc"] = (xtip - xwall) / Hc
        out["tip_height_over_Hc"] = ytip / Hc
        th = ytip - 0.2 * Hc
        out["tube_aspect_w_over_h"] = (xtip - xwall) / th if th > 0.5 else None
        # 前の面：内側の壁の高さより下で、各行の body の一番前（頂より前、唇の下の空気より下）
        face = []
        for j in range(0, ny):
            yy = ys[j]
            if yy > ywall or yy < 0.2 * Hc - 0.01:
                continue
            row = body[j, iwall:min(nx, ic + int(40 / DX))]
            # 内側の壁から前へ、最初に水が切れる所
            k = np.argmax(~row) if (~row).any() else len(row)
            face.append((float(xs[iwall + k - 1]) if k > 0 else xwall, float(yy)))
        if len(face) >= 4:
            face = np.array(face)
            ff = face[np.argmin(np.abs(face[:, 1] - 0.2 * Hc))]
            wall = np.array([xwall, ywall])
            ch = ff - wall
            if np.linalg.norm(ch) > 0.5:
                chn = ch / np.linalg.norm(ch); nrm = np.array([-chn[1], chn[0]])
                sag = (face - wall) @ nrm
                out["front_face_chord_angle_deg"] = math.degrees(math.atan2(wall[1] - ff[1], ff[0] - wall[0]))
                out["front_face_concavity_m"] = float(max(0.0, -sag.min()))
                out["face_foot_02Hc"] = ff.tolist()
    # 背：頂より後ろで、一番上の水面が 0.75 Hc まで下がる所
    Hc = yc
    back = np.where((xs < xc) & np.isfinite(ytop))[0][::-1]
    x75 = None; x25 = None
    for i in back:
        if x75 is None and ytop[i] <= 0.75 * Hc:
            x75 = float(xs[i])
        if ytop[i] <= 0.25 * Hc:
            x25 = float(xs[i]); break
    out["back_dx_to_075Hc_m"] = (xc - x75) if x75 is not None else None
    out["back_slope_crest_to_075Hc_deg"] = math.degrees(math.atan2(0.25 * Hc, xc - x75)) if x75 is not None else None
    out["back_slope_25_75_deg"] = math.degrees(math.atan2(0.5 * Hc, x75 - x25)) if (x75 is not None and x25 is not None) else None
    # 前の谷（頂より前 60 m までの一番低い水面）
    fr = (xs > xc) & (xs < xc + 60) & np.isfinite(ytop)
    out["trough_ahead_m"] = float(np.nanmin(ytop[fr])) if fr.any() else None
    # 閉じた空洞：閉じた空きのうち、重心が頂より 5 m 前より前、高さ 0.15 Hc より上にあるものだけ（水の中の帯のすき間を数えない）
    labc, nc = ndi.label(closed)
    area_c = 0.0
    for L in range(1, nc + 1):
        jj, ii = np.where(labc == L)
        if xs[int(np.mean(ii))] > xc - 5.0 and ys[int(np.mean(jj))] > 0.15 * yc and abs(xs[int(np.mean(ii))] - xc) < 45:
            area_c += len(jj) * DX * DX
    out["closed_air_area_m2"] = float(area_c)
    return out


def analyze(rd, quiet=False):
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    P = run["parms"]
    set_dx(P)
    fs = load_snaps(rd)
    xc0 = float(P.get("xc0", 330.0)) if float(P.get("wave_mode", 0)) < 0.5 else float(P.get("xsol", 200.0))
    tl = []
    xc_prev = None
    for f in fs:
        d = np.load(f)
        x, y, vx = d["x"], d["y"], d["vx"]
        t = float(d["t"])
        if xc_prev is None:
            # 最初のコマ：断面の中で一番高い所の近く
            xc_prev = float(x[np.argmax(y)])
        # 窓は断面の粒子を書き出した x の範囲の中に限る（範囲の外の空の列が深い所の水を「空気」につなげないように）
        sxr = run.get("snap", {}).get("x", [-1e9, 1e9])
        x0 = max(xc_prev - 80.0, float(sxr[0]) + 0.5); x1 = min(xc_prev + 80.0, float(sxr[1]) - 0.5)
        cnt = raster(x, y, x0, x1)
        # 海底より下の升目は水と同じに扱う（浅い所で、水面の帯と海底の帯の間のすき間が海底を通って窓の下の端につながり、深い所の水として埋まるように）。
        # 岩棚の計算では海底は窓より下（y<-20）なので効かない。孤立波の坂の計算のため。
        xs_ = x0 + (np.arange(cnt.shape[1]) + 0.5) * DX
        ybed = np.minimum(-float(P["h0"]) + np.maximum(0.0, xs_ - float(P["xs0"])) / float(P["slope_n"]), -float(P["hr"]))
        ys_ = YMIN + (np.arange(cnt.shape[0]) + 0.5) * DX
        cnt[ys_[:, None] < ybed[None, :]] += 1
        water, closed = water_mask(cnt)
        m = shape_metrics(water, closed, x0, xc_prev)
        if m is None:
            continue
        xc, yc = m["crest"]
        near = (np.abs(x - xc) < 2.0) & (y > yc - 1.5)
        u = float(vx[near].max()) if near.any() else float("nan")
        m.update({"t": t, "frame": int(os.path.basename(f)[5:9]), "u_crest": u, "n_part": int(d["n"])})
        tl.append(m)
        xc_prev = xc
    # 頂の進む速さ
    # 頂の進む速さ c：前の面の半分の高さの点 x_front_half の動き（±0.5 秒の直線の当てはめ）。
    # 頂の一番高い点の x は、平らな頂の上で跳ぶので使わない（S05 で c が 12〜56 m/s と揺れた）。
    tt = np.array([q["t"] for q in tl]); yy = np.array([q["crest"][1] for q in tl])
    xx = np.array([q["x_front_half"] if q.get("x_front_half") is not None else np.nan for q in tl])
    for k, q in enumerate(tl):
        sel = (np.abs(tt - tt[k]) <= 0.51) & np.isfinite(xx)
        if sel.sum() >= 5:
            A = np.vstack([tt[sel], np.ones(sel.sum())]).T
            c = float(np.linalg.lstsq(A, xx[sel], rcond=None)[0][0])
        else:
            c = float("nan")
        q["c_crest"] = c
        q["B"] = q["u_crest"] / c if c and c > 1 else float("nan")
    # 出来事
    ev = {}
    def first(cond):
        for q in tl:
            if cond(q):
                return q
        return None
    # 砕けの始まり：B > 0.85 が 2 枚続けて（ノイズの 1 枚を数えない）
    qb = None
    for k in range(len(tl) - 1):
        if all(np.isfinite(tl[k + j]["B"]) and tl[k + j]["B"] > 0.85 for j in range(2)):
            qb = tl[k]; break
    # 前の面が垂直を過ぎた：張り出しが 3 枚続けて（0.25 秒）見えた最初のコマ（粒子の帯の小さな穴を数えない）
    qo = None
    for k in range(len(tl) - 2):
        if all(tl[k + j].get("overturned") for j in range(3)):
            qo = tl[k]; break
    t_ov = qo["t"] if qo else 1e9
    # 閉じた・ほぼ閉じた：張り出しがある間で
    # ほぼ閉じた：かぶりが 0.15 Hc 以上に育ってから、唇の先の下の空気の高さが 0.1 Hc 未満（張り出し始めの小さなすき間を数えない）
    qcl = first(lambda q: q["t"] >= t_ov and q.get("overturned") and (q.get("closed_air_area_m2", 0) >= 1.0 or
                (q.get("overhang_m", 0) >= 0.15 * q["crest"][1] and q.get("gap_below_tip_m", 99) < 0.1 * q["crest"][1])))
    ev["breaking_onset_B085"] = {"t": qb["t"], "x": qb["crest"][0], "crest_y": qb["crest"][1], "B": qb["B"]} if qb else None
    ev["face_past_vertical"] = {"t": qo["t"], "x": qo["crest"][0], "crest_y": qo["crest"][1]} if qo else None
    ev["tube_closed_or_nearly"] = {"t": qcl["t"], "x": qcl["crest"][0], "closed_area_m2": qcl.get("closed_air_area_m2"),
                                   "gap_below_tip_m": qcl.get("gap_below_tip_m")} if qcl else None
    pre = [q for q in tl if (qo is None or q["t"] <= qo["t"])]
    ev["crest_max_before_overturn_m"] = max(q["crest"][1] for q in pre) if pre else None
    # B の最大は、前の面が垂直を過ぎる時まで（その後は前の面の点が唇とともに跳ぶので c が測れない）
    tl_pre = [q for q in tl if (qo is None or q["t"] <= qo["t"])]
    ev["B_max"] = float(np.nanmax([q["B"] for q in tl_pre])) if tl_pre else None
    plunge = bool(qb and qo and qcl)
    # 原画の読み A との比べ：張り出しのあるコマで、届き・落ち・かぶり（/Hc）の差の 2 乗和が最小のコマ
    pt = json.load(open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1/painting/painting_section.json", encoding="utf8"))
    best = {}
    for rk in ("A_side", "B_sample06_plane"):
        R = pt["readings"][rk]
        cand = [q for q in tl if q["t"] >= t_ov and q.get("overturned") and q.get("tube_aspect_w_over_h") is not None]
        if qcl:
            cand = [q for q in cand if q["t"] <= qcl["t"] + 1.0]
        if not cand:
            best[rk] = None; continue
        def sc3(q):
            return ((q["reach_over_Hc"] - R["reach_over_Hc"]) ** 2 + (q["drop_over_Hc"] - R["drop_over_Hc"]) ** 2
                    + (q["overhang_over_Hc"] - R["overhang_over_Hc"]) ** 2)
        def sc(q):
            # 点数（小さいほど原画に近い）：唇の 3 つ（/Hc）＋前の面の弦の角度（差/60°）＋空洞の幅/高さ（差/2）
            # ＋背（読み A だけ：頂→0.75 Hc の横の長さ/Hc の差）。どれも 2 乗して足す。重みは同じ（案）。
            v = sc3(q)
            fa = q.get("front_face_chord_angle_deg")
            v += ((fa - R["front_face_chord_angle_deg"]) / 60.0) ** 2 if fa is not None else 0.25
            ta = q.get("tube_aspect_w_over_h")
            v += ((ta - R["tube_aspect_w_over_h"]) / 2.0) ** 2 if ta is not None else 0.25
            return v
        def scb(q):
            # 背の差（読み A だけ）。物理の波の背は原画より長くなる見込み（C_shape_keep の M6）なので、点数とは別に記録する
            if rk != "A_side":
                return None
            bd = q.get("back_dx_to_075Hc_m")
            return ((bd / q["crest"][1] - (-R["back"]["x_at_0.75Hc"]) / 20.0)) ** 2 if bd is not None else None
        qq = min(cand, key=sc)
        best[rk] = {"t": qq["t"], "frame": qq["frame"], "score": sc(qq), "score_lip3": sc3(qq), "score_back": scb(qq),
                    "score_run": sc(qq) + ((qq["crest"][1] - 20.0) / 20.0) ** 2,
                    "crest_m": qq["crest"][1], "since_overturn_s": qq["t"] - qo["t"] if qo else None,
                    "score_def_ja": "score＝唇の届き・落ち・かぶり（/Hc）の差、前の面の弦の角度の差/60°、空洞の幅/高さの差/2 の 2 乗和。score_run＝score＋（頂の高さ−20 m）/20 m の 2 乗（倍率をかけない頂の高さの近さ）。score_back＝背の頂→0.75Hc の横/Hc の差の 2 乗（別に記録）"}
    res = {"run_id": run["run_id"], "parms": {k: P[k] for k in ("T", "H", "slope_n", "hr", "h0", "xc0", "xhot", "wave_mode", "Hs", "xsol", "dp", "W") if k in P},
           "stopped": run.get("stopped"), "wall_total_s": run.get("wall_total_s"), "wall_per_frame_median_s": run.get("wall_per_frame_median_s"),
           "particles_max": run.get("particles_max"), "rss_peak_gb": run.get("rss_peak_gb"),
           "t_end": tt[-1] if len(tt) else None,
           "events": ev, "plunging": plunge, "best_frame_vs_painting": best,
           "timeline": tl}
    # 波の高さ：斜面の足元（xs0 - 20 m）の水面計で、頂が通る時の山と前後の谷（eta.npz から）
    try:
        E = np.load(os.path.join(rd, "eta.npz"))
        xg = float(P.get("xs0", 420.0)) - 20.0
        ig = int(np.argmin(np.abs(E["x"] - xg)))
        eg = E["eta"][:, ig]; tg = E["t"]
        kmax = int(np.nanargmax(eg))
        res["toe_gauge"] = {"x": float(E["x"][ig]), "crest_m": float(eg[kmax]), "t_crest": float(tg[kmax]),
                            "trough_before_m": float(np.nanmin(eg[:kmax + 1])), "trough_after_m": float(np.nanmin(eg[kmax:])),
                            "H_toe_m": float(eg[kmax] - min(np.nanmin(eg[:kmax + 1]), np.nanmin(eg[kmax:])))}
    except Exception as e:
        res["toe_gauge"] = {"error": str(e)}
    json.dump(res, open(os.path.join(rd, "analysis.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    if not quiet:
        s = {k: res[k] for k in ("run_id", "stopped", "plunging", "events", "best_frame_vs_painting", "toe_gauge", "t_end")}
        print(json.dumps(s, ensure_ascii=False, default=float, indent=1))
    return res


if __name__ == "__main__":
    analyze(sys.argv[1], quiet="--quiet" in sys.argv)
