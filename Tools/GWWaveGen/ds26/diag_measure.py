# -*- coding: utf-8 -*-
"""美術優先30/31 の形成の動きの診断（読み取り専用）。

再生される 16 ビットの keypose（af30_pos_rgba16.bin）を、Unity の AF30KeyposeWave と同じ
非一様 Catmull-Rom（af30_formation.cr_weights をそのまま使う）で補間し、K* の断面座標
（a = 進行方向 t、y = 上、c = 波峰線方向 e。原点 section_origin_world）で測る。
使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds26/diag_measure.py
入力：Unity/Build/ArtFirst/26修正01/kstar/・30/keypose/・31/white/（Git 対象外）、af30_rig.json、Docs/Evidence/ArtFirst/31/metrics.json。
出力：Unity/Build/Design/26/diag/diag_measure.json・diag_sections.npz（Git 対象外。-B で __pycache__ も作らない）。
"""
import json
import math
import os
import struct
import sys
import time

import numpy as np

import ds26_paths as DP  # noqa: E402
REPO = DP.REPO
OUT = DP.outdir(DP.OUT_DIAG)
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
import af30_formation as F30  # noqa: E402  （cr_weights・Rig・KStar を読むだけ）

G = 9.81
t0_clock = time.time()
KDIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
KPDIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30", "keypose")
rig = json.load(open(os.path.join(REPO, "Tools", "GWWaveGen", "af30_rig.json"), encoding="utf-8"))
ks = F30.KStar(KDIR, rig["inputs"]["kstar_gwb_sha256"])
kp = json.load(open(os.path.join(KPDIR, "af30_keypose.json"), encoding="utf-8"))
nu, nv, nk = kp["nu"], kp["nv"], kp["layers"]
times = np.array(kp["key_times_s"], np.float64)
lo = np.array(kp["bbox_min"]); size = np.array(kp["bbox_size"])
raw = np.fromfile(os.path.join(KPDIR, "af30_pos_rgba16.bin"), "<u2").reshape(nk, nv, nu, 4)
Xk = lo + raw[..., :3].astype(np.float64) / 65535.0 * size          # (nk, nv, nu, 3) world m
del raw
O, te, ec = ks.O, ks.t, ks.e
D = Xk - O
Ak = (D @ te).astype(np.float64)                                     # (nk, nv, nu)
Ck = (D @ ec).astype(np.float64)
Yk = Xk[..., 1].copy()
del D
# 断面の面の中だけで動くか（c が行の値のまま）
c_dev = float(np.abs(Ck - ks.c[None, :, None]).max())
del Ck
pc = rig["profile_columns"]
jB, jT, jP, jK, jF, jE = (pc[k] for k in ("j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"))
mr = ks.main_row


def play(t, arr):
    idx, w = F30.cr_weights(times, t)
    out = None
    for q in range(4):
        if w[q] != 0.0:
            out = w[q] * arr[idx[q]] if out is None else out + w[q] * arr[idx[q]]
    return out


# K* の事実
AK, YK = ks.A, ks.Y
Hrow = YK.max(1)
crest_col_K = YK.argmax(1)
kfacts = {
    "units": "m（Unity ワールド、左手系、Y 上）。時間 s",
    "vertices": int(nu * nv), "grid": [nu, nv], "triangles": int(len(ks.tris)),
    "e_crest_world": ks.e.tolist(), "t_travel_world": ks.t.tolist(), "section_origin_world": ks.O.tolist(),
    "main_row": mr, "main_row_c_m": float(ks.c[mr]),
    "main_row_crest_m": float(Hrow[mr]), "peak_crest_m": float(Hrow.max()), "peak_row_c_m": float(ks.c[Hrow.argmax()]),
    "main_row_back_foot_a_m": float(AK[mr, jB]), "main_row_front_foot_a_m": float(AK[mr, jE]),
    "main_row_crest_a_m": float(AK[mr, crest_col_K[mr]]), "main_row_tip_a_y_m": [float(AK[mr, jP]), float(YK[mr, jP])],
    "row_c_range_m": [float(ks.c.min()), float(ks.c.max())],
    "rows_with_crest_gt_3m": int((Hrow > 3).sum()),
    "c_range_crest_gt_half_peak_m": [float(ks.c[Hrow > 0.5 * Hrow.max()].min()), float(ks.c[Hrow > 0.5 * Hrow.max()].max())],
    "min_y_m": float(YK.min()),
}
# 0.3H の内壁から唇先までの張り出し（主断面）
seg = YK[mr, jK:jE + 1]; aa = AK[mr, jK:jE + 1]
i03 = np.nonzero(seg <= 0.3 * Hrow[mr])[0][0]
kfacts["main_row_overhang_m"] = float(AK[mr, jP] - aa[i03])
# 断面の面積（海面より上）
def row_area(A, Y):
    # 折れ線（後ろの海 → 前の海）と y=0 で閉じた多角形の面積（上が正）
    s = A[..., :-1] * Y[..., 1:] - A[..., 1:] * Y[..., :-1]
    return -0.5 * s.sum(-1)


cK = ks.c
dc = np.gradient(cK)  # 行の間隔（台形）
areaK = row_area(AK, YK)
kfacts["main_row_area_above_swl_m2"] = float(areaK[mr])
kfacts["volume_above_swl_m3"] = float((areaK * dc).sum())
kfacts["volume_below_swl_m3"] = 0.0
kfacts["footprint_main_row_m"] = float(AK[mr, jE] - AK[mr, jB])
kfacts["back_slope_mean_deg"] = float(math.degrees(math.atan2(Hrow[mr], AK[mr, crest_col_K[mr]] - AK[mr, jB])))
kfacts["keypose"] = {"layers": nk, "rate_hz": 15, "t_range_s": [float(times[0]), float(times[-1])],
                     "position_bytes": kp["position_bytes"], "normal_bytes": kp["normal_bytes"],
                     "bytes_per_layer": (kp["position_bytes"] + kp["normal_bytes"]) // nk,
                     "quantization_max_err_m": kp["quantization_max_err_m"]}
kfacts["section_plane_c_dev_max_m"] = c_dev

# ---------------------------------------------------------------- 60 Hz の全フレーム
HZ = 60.0
ts = np.arange(int(round(17.0 * HZ)) + 1) / HZ
nt = len(ts)
crest_y = np.zeros((nt, nv)); crest_a = np.zeros((nt, nv)); area = np.zeros((nt, nv))
tip = np.zeros((nt, nv, 2)); gtip = np.zeros((nt, nv, 2))
phi_max = np.full((nt, nv), np.nan); phi_half = np.full((nt, nv), np.nan)
overhang = np.zeros((nt, nv))
cent_a = np.zeros((nt, nv))
dist_rms = np.zeros(nt); dist_max = np.zeros(nt)
spd_mean = np.zeros(nt); spd_max = np.zeros(nt); spd_p95 = np.zeros(nt)
lip_arc = np.zeros((nt, nv))
ymin_t = np.zeros(nt)
main_sections = {}
keep_t = [round(v, 3) for v in np.arange(2.0, 12.01, 0.5)]
Ap = Yp = None
rows_ix = np.arange(nv)
for i, t in enumerate(ts):
    A = play(t, Ak); Y = play(t, Yk)
    ymin_t[i] = Y.min()
    cy = Y.max(1); cj = Y.argmax(1)
    crest_y[i] = cy; crest_a[i] = A[rows_ix, cj]
    area[i] = row_area(A, Y)
    # 面積の重心の a
    s = A[:, :-1] * Y[:, 1:] - A[:, 1:] * Y[:, :-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        cx = ((A[:, :-1] + A[:, 1:]) * s).sum(1) / (6.0 * (0.5 * s.sum(1)))
    cent_a[i] = np.where(np.abs(area[i]) > 1e-3, cx, np.nan)
    tip[i, :, 0] = A[:, jP]; tip[i, :, 1] = Y[:, jP]
    # 唇の弧長（頂の列 → 唇先の列）
    lip_arc[i] = np.hypot(np.diff(A[:, jT:jP + 1], axis=1), np.diff(Y[:, jT:jP + 1], axis=1)).sum(1)
    # 前面の角と張り出し（行ごと）
    for r in range(nv):
        H = cy[r]
        if H < 1.0:
            continue
        j0 = cj[r]
        a = A[r, j0:jE + 1]; y = Y[r, j0:jE + 1]
        da = np.diff(a); dy = np.diff(y); ym = 0.5 * (y[1:] + y[:-1])
        L = np.hypot(da, dy)
        ok = (L > 1e-3) & (dy < 0) & (ym > 0.15 * H) & (ym < 0.97 * H)
        if ok.any():
            ph = np.degrees(np.arctan2(-dy[ok], da[ok]))
            phi_max[i, r] = ph.max()
        # 0.5H を最後に下へ横切る所の角（前の足へ下る内壁）
        cross = np.nonzero((y[:-1] > 0.5 * H) & (y[1:] <= 0.5 * H))[0]
        if len(cross):
            k = cross[-1]
            phi_half[i, r] = math.degrees(math.atan2(-dy[k], da[k]))
            # 張り出し：0.3H を最後に下へ横切る点の a と、0.3H より上の前の部分の a の最大
            c3 = np.nonzero((y[:-1] > 0.3 * H) & (y[1:] <= 0.3 * H))[0]
            if len(c3):
                k3 = c3[-1]
                f = (y[k3] - 0.3 * H) / max(y[k3] - y[k3 + 1], 1e-12)
                a3 = a[k3] + f * (a[k3 + 1] - a[k3])
                above = y > 0.3 * H
                overhang[i, r] = a[above].max() - a3
        # 幾何の唇先：前の部分で 0.5H より上の点の a の最大
        above = y > 0.5 * H
        if above.any():
            k = np.argmax(np.where(above, a, -1e9))
            gtip[i, r] = (a[k], y[k])
    X = np.stack([A, Y], -1)
    if Ap is not None:
        v = np.hypot(A - Ap, Y - Yp) * HZ
        body = Y > 0.5
        spd_mean[i] = v[body].mean() if body.any() else 0.0
        spd_max[i] = v.max()
        spd_p95[i] = np.percentile(v[body], 95) if body.any() else 0.0
    Ap, Yp = A, Y
    d = np.hypot(A - AK, Y - YK)
    dist_rms[i] = math.sqrt((d ** 2).mean()); dist_max[i] = d.max()
    if round(t, 3) in keep_t:
        main_sections[round(t, 3)] = np.stack([A[[mr, 146, 120, 100, 185, 200]], Y[[mr, 146, 120, 100, 185, 200]]], -1)
    if i % 120 == 0:
        print("frame %d/%d t=%.2f (%.0f s)" % (i, nt, t, time.time() - t0_clock), flush=True)

# ---------------------------------------------------------------- 唇先・頂の運動学（240 Hz、中心差分）
HZ2 = 240.0
ts2 = np.arange(int(round(12.5 * HZ2)) + 1) / HZ2
cols = np.array([jT, 110, 130, 150, 170, 185, jP])
Ak_c = Ak[:, :, cols]; Yk_c = Yk[:, :, cols]
Ak_n = Ak[:, :, [jP - 1, jP + 1]]; Yk_n = Yk[:, :, [jP - 1, jP + 1]]
P = np.zeros((len(ts2), nv, len(cols), 2)); Pn = np.zeros((len(ts2), nv, 2, 2))
for i, t in enumerate(ts2):
    P[i, :, :, 0] = play(t, Ak_c); P[i, :, :, 1] = play(t, Yk_c)
    Pn[i, :, :, 0] = play(t, Ak_n); Pn[i, :, :, 1] = play(t, Yk_n)
V = np.gradient(P, 1.0 / HZ2, axis=0)
Acc = np.gradient(V, 1.0 / HZ2, axis=0)
# key の間隔（1/15 s）の箱で平滑した加速度（節点での二階微分の段をならす）
box = int(round(HZ2 / 15.0))
ker = np.ones(box) / box
Acc_s = np.apply_along_axis(lambda x: np.convolve(x, ker, mode="same"), 0, Acc[:, mr, :, :].reshape(len(ts2), -1)).reshape(len(ts2), len(cols), 2)
tan = Pn[:, :, 1, :] - Pn[:, :, 0, :]
tan /= np.maximum(np.linalg.norm(tan, axis=-1, keepdims=True), 1e-12)
vt = V[:, :, -1, :]
sp = np.linalg.norm(vt, axis=-1)
cosang = np.abs((vt * tan).sum(-1)) / np.maximum(sp, 1e-9)

# ---------------------------------------------------------------- 白（番号31）
m31 = json.load(open(os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "31", "metrics.json"), encoding="utf-8"))
wf = np.array(m31["items"]["uv"]["value"]["white_fraction"], np.float64)
wf_hz = float(m31["items"]["uv"]["value"]["hz"])
wf_t = np.arange(len(wf)) / wf_hz
tw = np.fromfile(os.path.join(REPO, "Unity", "Build", "ArtFirst", "31", "white", "af31_twhite_r32f.bin"), "<f4").reshape(nv, nu)
idser = m31["items"]["id_series"]["value"]


# ---------------------------------------------------------------- まとめ
def first_time(mask_t, tt):
    idx = np.nonzero(mask_t)[0]
    return float(tt[idx[0]]) if len(idx) else None


res = {"kstar": kfacts}
H_final = crest_y[-1]
big = H_final > 3.0
# 行ごとの時刻：頂が最終の 50%・90% に届く、前面の最大角が 60°・90°・120° を超える
t50 = np.array([first_time(crest_y[:, r] >= 0.5 * H_final[r], ts) if big[r] else np.nan for r in range(nv)], float)
t90 = np.array([first_time(crest_y[:, r] >= 0.9 * H_final[r], ts) if big[r] else np.nan for r in range(nv)], float)
tv = {}
for ang in (45, 60, 90, 120):
    tv[ang] = np.array([first_time(np.nan_to_num(phi_max[:, r], nan=0) >= ang, ts) if big[r] else np.nan for r in range(nv)], float)
curl = np.zeros(nv, bool)
for r in range(nv):
    curl[r] = big[r] and overhang[-1, r] >= 0.2 * H_final[r]
res["rows"] = {"c_m": cK.tolist(), "H_final_m": H_final.tolist(), "t50": t50.tolist(), "t90": t90.tolist(),
               "t_phi45": tv[45].tolist(), "t_phi60": tv[60].tolist(), "t_phi90": tv[90].tolist(), "t_phi120": tv[120].tolist(),
               "curl_rows": curl.tolist(), "overhang_final_m": overhang[-1].tolist()}


def spread(x, m):
    v = x[m & np.isfinite(x)]
    return {"n": int(len(v)), "min": float(v.min()), "max": float(v.max()), "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95)), "std": float(v.std())} if len(v) else None


res["row_sync"] = {"t50": spread(t50, big), "t90": spread(t90, big), "t_phi90_curl": spread(tv[90], curl), "t_phi60_big": spread(tv[60], big),
                   "t_phi90_all_big": spread(tv[90], big), "curl_rows": int(curl.sum()), "big_rows": int(big.sum()),
                   "crest_arc_of_big_rows_m": float(np.abs(np.diff(cK[big])).sum())}
# 主断面の時系列
ms = {}
ms["t"] = ts.tolist()
ms["crest_y"] = crest_y[:, mr].tolist(); ms["crest_a"] = crest_a[:, mr].tolist(); ms["area"] = area[:, mr].tolist()
ms["centroid_a"] = cent_a[:, mr].tolist(); ms["tip_a"] = tip[:, mr, 0].tolist(); ms["tip_y"] = tip[:, mr, 1].tolist()
ms["gtip_a"] = gtip[:, mr, 0].tolist(); ms["gtip_y"] = gtip[:, mr, 1].tolist()
ms["phi_max"] = np.nan_to_num(phi_max[:, mr], nan=-1).tolist(); ms["phi_half"] = np.nan_to_num(phi_half[:, mr], nan=-1).tolist()
ms["overhang"] = overhang[:, mr].tolist(); ms["lip_arc"] = lip_arc[:, mr].tolist()
res["main_series"] = ms
vol = (area * dc[None, :]).sum(1)
res["global_series"] = {"t": ts.tolist(), "volume_above_swl_m3": vol.tolist(), "ymin": ymin_t.tolist(),
                        "peak_crest_m": crest_y.max(1).tolist(), "dist_rms_to_kstar_m": dist_rms.tolist(), "dist_max_to_kstar_m": dist_max.tolist(),
                        "speed_mean_body_mps": spd_mean.tolist(), "speed_p95_body_mps": spd_p95.tolist(), "speed_max_mps": spd_max.tolist()}
res["kinematics_240hz_main_row"] = {
    "t": ts2.tolist(), "cols": cols.tolist(),
    "tip_v": V[:, mr, -1, :].tolist(), "tip_acc_box": Acc_s[:, -1, :].tolist(), "crest_col_v": V[:, mr, 0, :].tolist(),
    "cos_v_tangent_tip": cosang[:, mr].tolist(), "col_speed": np.linalg.norm(V[:, mr, :, :], axis=-1).tolist(),
    "col_acc_box": Acc_s.tolist(),
}
res["white"] = {"t": wf_t.tolist(), "fraction": wf.tolist(),
                "twhite_main_row": tw[mr].tolist(),
                "id_painting": [[d_["t"], d_.get("white_shown_px", 0), d_.get("white_final_px", 0)] for d_ in idser["painting"]]}
res["checks"] = {"c_dev_max_m": c_dev}
# 断面（主断面など 6 行）
np.savez_compressed(os.path.join(OUT, "diag_sections.npz"), **{("t%05.2f" % k): v for k, v in main_sections.items()},
                    AK=AK[[mr, 146, 120, 100, 185, 200]], YK=YK[[mr, 146, 120, 100, 185, 200]],
                    tip_all=tip, gtip_all=gtip, crest_y=crest_y, crest_a=crest_a, phi_max=phi_max, overhang=overhang, area=area,
                    ts=ts, cK=cK, P240=P[:, mr], ts240=ts2)
with open(os.path.join(OUT, "diag_measure.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False)
print("DONE %.0f s" % (time.time() - t0_clock))
