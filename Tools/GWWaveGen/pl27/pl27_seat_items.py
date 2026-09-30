# -*- coding: utf-8 -*-
"""仕上げ27：バックログ 80・106・107・108・111（船上から見た形成）を、採用の動き（28修正01 の F_final、ds27 の包み）で測って記録する。

測り方は美術優先30 の記録（Tools/GWWaveGen/af30_evidence.py の座席の項目。Docs/Evidence/ArtFirst/30/metrics.json）と同じ定義を、
ds27 の包み（関門の検査器 ds27_gates.py の Package・KStar で読む。16 bit の Hermite）と K*′ R4 の目印の列（meta の profile.index）へ当てた：
  目：座席 v1（Tools/GWContext/seat_v1.json の eye_world。右船の唇の下、甲板の 1.2 m 上）。固定（美術優先30・設計27 と同じ）。
      体験の場面では座席の船が動くので、設計47 の走り main（Editor の Play、HMD Camera の位置の記録 ds47_frames.csv）の目でも 80・108 を測る（記録のみ）。
  時刻：体験の時刻 t 0〜14 s、30 Hz。τ(t) は 28修正01 の timewarp_F_final.json（t* = 12 s、12〜14 s は保持）。
  行の組：座席の c（c_seat = (eye − O)·e）から、中央 ±5 m・近く ±3 m・左 −25〜−5 m・右 +5〜+15 m（美術優先30 と同じ）。
  唇：巻きの行（検査器の curled）の列 j_top〜j_corner。唇先の列 j_tip。内壁：列 j_corner〜j_facebot。水面は y > 0.3 m。
判定：美術優先30 の式（geom_ok は連続性の検査一式がすべて合格）と、項目の言葉だけの読みの両方を書く。連続性の検査一式は
関門の検査器の P13 の出力（--gates-json）を写す。107 は、面の反転を項目の範囲（座席の近くの行の内壁）でも数える。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_seat_items.py --package Unity/Build/Design/28R01F/F_final/art_on \
      --kstar Unity/Build/Design/28R01F/kstar_F_final --timewarp Unity/Build/Design/28R01F/F_final/timewarp_F_final.json \
      --gates-json Unity/Build/Design/28R01F/F_final/gates/default_ds27.json --out Unity/Build/Polish/27/seat_items/seat_items_F_final.json
"""
import argparse
import csv
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GW, "..", ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_gates as DG  # noqa: E402
import ds28r01d_gates as DGW  # noqa: E402

SEAT = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
DS47_CSV = os.path.join(REPO, "Unity", "Build", "Design", "47", "flow", "unity", "main", "ds47_frames.csv")


def ab(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def drop_max(x):
    f = np.nan_to_num(np.asarray(x, float), nan=-90.0)
    return float(np.max(np.maximum(f[:-1] - f[1:], 0.0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--timewarp", required=True)
    ap.add_argument("--gates-json", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    kd = DGW.patch_kstar(ab(a.kstar))
    ks = DG.KStar(kd)
    pk = DG.Package(ab(a.package), ks)
    meta_p = [os.path.join(ab(a.kstar), f) for f in os.listdir(ab(a.kstar)) if f.endswith("_meta.json")][0]
    pi = json.load(open(meta_p, encoding="utf-8"))["profile"]["index"]
    jT, jP, jK, jF = int(pi["j_top"]), int(pi["j_tip"]), int(pi["j_corner"]), int(pi["j_facebot"])
    tw = json.load(open(ab(a.timewarp), encoding="utf-8"))
    tw_t, tw_tau = np.array(tw["t"], float), np.array(tw["tau"], float)
    GJ = json.load(open(ab(a.gates_json), encoding="utf-8"))
    P13 = GJ["gates"]["P13"]["detail"]
    seat = json.load(open(SEAT, encoding="utf-8"))
    eye = np.array(seat["seat"]["eye_world"], float)
    nv, nu = ks.nv, ks.nu
    c_seat = float((eye - ks.O) @ ks.e)
    near_rows = np.nonzero(np.abs(ks.c - c_seat) <= 3.0)[0]
    face_rows = np.nonzero(np.abs(ks.c - c_seat) <= 5.0)[0]
    left_rows = np.nonzero((ks.c < c_seat - 5.0) & (ks.c >= c_seat - 25.0))[0]
    right_rows = np.nonzero((ks.c > c_seat + 5.0) & (ks.c <= c_seat + 15.0))[0]
    lip_rows = ks.curled_idx
    lipm = np.zeros((nv, nu), bool)
    lipm[np.ix_(lip_rows, np.arange(jT, jK + 1))] = True
    # 内壁の三角形（座席の近くの行、列 jK..jF）
    trm = np.zeros((nv - 1, nu - 1), bool)
    fr0, fr1 = int(face_rows.min()), int(face_rows.max())
    trm[fr0:fr1, jK:jF] = True
    hz = 30.0
    ts = np.arange(0, int(round(14.0 * hz)) + 1) / hz
    its = int(round(12.0 * hz))
    S = {k: [] for k in ("tau", "lip_elev_max", "lip_hdist_min", "near_tip_elev", "centre_elev_max", "left_elev_max", "right_elev_max",
                         "face_normal_up_deg", "face_normal_to_seat", "tip_dir_deg", "zenith70", "lip_within5m", "face_flips_region")}
    prev_fn = None
    face_turn_max = 0.0
    tip_prev = None
    tip_jump_max = 0.0
    tipl_prev = None
    tipl_jump_max = 0.0
    sign = None
    prev_tn = None
    X_by_t = {}
    for t in ts:
        tau = float(np.interp(t, tw_t, tw_tau))
        X = pk.world(tau)
        A, Y, C = ks.section(X)
        d = X - eye
        hd = np.hypot(d[..., 0], d[..., 2])
        el = np.degrees(np.arctan2(d[..., 1], hd))
        above = Y > 0.3
        lm = lipm & above
        S["tau"].append(tau)
        S["lip_elev_max"].append(float(el[lm].max()) if lm.any() else float("nan"))
        high = lm & (d[..., 1] > 3.0)
        S["lip_hdist_min"].append(float(hd[high].min()) if high.any() else float("nan"))
        S["lip_within5m"].append(int((high & (hd <= 5.0)).sum()))
        S["zenith70"].append(int((above & (el >= 70.0)).sum()))
        S["near_tip_elev"].append(float(el[near_rows, jP].max()))
        for key, rows_ in (("centre_elev_max", face_rows), ("left_elev_max", left_rows), ("right_elev_max", right_rows)):
            m_ = above[rows_]
            S[key].append(float(el[rows_][m_].max()) if m_.any() else float("nan"))
        tn = DG.tri_normals(X)                                      # (nv-1, nu-1, 2, 3)
        if sign is None:
            s_ = tn[..., 1].sum()
            sign = 1.0 if s_ >= 0 else -1.0                         # 最初のコマ（平らな海）で上向きになる向き
        tn = tn * sign
        fn = tn[trm].reshape(-1, 3).sum(0)
        fn /= np.linalg.norm(fn)
        cen = X[fr0:fr1 + 1, jK:jF + 1].reshape(-1, 3).mean(0)
        to_seat = eye - cen
        to_seat[1] = 0
        to_seat /= np.linalg.norm(to_seat)
        S["face_normal_up_deg"].append(float(np.degrees(np.arccos(np.clip(fn[1], -1, 1)))))
        S["face_normal_to_seat"].append(float(fn @ to_seat))
        if prev_fn is not None:
            face_turn_max = max(face_turn_max, float(np.degrees(np.arccos(np.clip(fn @ prev_fn, -1, 1)))))
        prev_fn = fn
        # 項目の範囲の面の反転（前のコマの法線と向きが逆、面積 > 0）
        nl = np.linalg.norm(tn, axis=-1)
        if prev_tn is not None:
            pl_ = np.linalg.norm(prev_tn, axis=-1)
            bad = (nl > 1e-10) & (pl_ > 1e-10) & ((tn * prev_tn).sum(-1) <= 0) & trm[..., None]
            S["face_flips_region"].append(int(bad.sum()))
        else:
            S["face_flips_region"].append(0)
        prev_tn = tn
        v = np.stack([A[near_rows, jP] - A[near_rows, jP - 8], Y[near_rows, jP] - Y[near_rows, jP - 8]], -1)
        S["tip_dir_deg"].append(float(np.median(np.degrees(np.arctan2(v[:, 1], v[:, 0])))))
        tp = X[near_rows, jP]
        if tip_prev is not None:
            tip_jump_max = max(tip_jump_max, float(np.linalg.norm(tp - tip_prev, axis=-1).max()))
        tip_prev = tp
        tpl = tp - pk.origin(tau)[0]                                # 波の枠（局所。約 20 m/s の進みを除く）
        if tipl_prev is not None:
            tipl_jump_max = max(tipl_jump_max, float(np.linalg.norm(tpl - tipl_prev, axis=-1).max()))
        tipl_prev = tpl
        if abs(t - round(t)) < 1e-9:
            X_by_t[int(round(t))] = None
    S = {k: np.array(v, float) for k, v in S.items()}
    lip_f = np.nan_to_num(S["lip_elev_max"], nan=-90.0)
    cen_f = np.nan_to_num(S["centre_elev_max"], nan=-90.0)
    tip = S["tip_dir_deg"]
    tipdir_step = float(np.max(np.abs(np.diff(tip))))
    # ---- 体験の場面の目（設計47 の走り main の HMD Camera。記録のみ）
    mov = None
    if os.path.isfile(DS47_CSV):
        rows = list(csv.DictReader(open(DS47_CSV, encoding="utf-8")))
        wv = np.array([float(r["wave"]) for r in rows])
        ho = np.array([r["handed_over"] == "1" for r in rows])
        cam = np.array([[float(r["cam_x"]), float(r["cam_y"]), float(r["cam_z"])] for r in rows])
        tauc = np.array([float(r["tau"]) for r in rows])
        ok = ho & (wv > 0.0)
        idx = np.nonzero(ok)[0]
        mv = {k: [] for k in ("t", "tau", "centre_elev_max", "lip_elev_max", "cam_y", "cam_c")}
        for t in ts[1:]:
            j = idx[np.argmin(np.abs(wv[idx] - t))]
            if abs(wv[j] - t) > 1.0 / 60:
                continue
            e2 = cam[j]
            X = pk.world(float(tauc[j]))
            A, Y, C = ks.section(X)
            d = X - e2
            el = np.degrees(np.arctan2(d[..., 1], np.hypot(d[..., 0], d[..., 2])))
            above = Y > 0.3
            cs = float((e2 - ks.O) @ ks.e)
            fr = np.nonzero(np.abs(ks.c - cs) <= 5.0)[0]
            m_ = above[fr]
            lm = lipm & above
            mv["t"].append(float(wv[j]))
            mv["tau"].append(float(tauc[j]))
            mv["centre_elev_max"].append(float(el[fr][m_].max()) if m_.any() else float("nan"))
            mv["lip_elev_max"].append(float(el[lm].max()) if lm.any() else float("nan"))
            mv["cam_y"].append(float(e2[1]))
            mv["cam_c"].append(cs)
        M = {k: np.array(v) for k, v in mv.items()}
        mov = dict(source=DG.rel(DS47_CSV), source_sha256=DG.sha256_file(DS47_CSV), frames=int(len(M["t"])),
                   eye_ja="設計47 の走り main（Editor の Play、仮想のキーボードの操船）の HMD Camera の位置。座席の船が導入から形成へ動き、t* で原画の置き方へ着く",
                   centre_elev_deg={("t%d" % k): round(float(np.interp(k, M["t"], M["centre_elev_max"])), 2) for k in (1, 4, 6, 8, 9, 10, 11, 12)},
                   centre_max_drop_deg_per_frame=round(drop_max(M["centre_elev_max"]), 3),
                   lip_elev_deg={("t%d" % k): round(float(np.interp(k, M["t"], np.nan_to_num(M["lip_elev_max"], nan=-90))), 2) for k in (2, 8, 10, 12)},
                   lip_max_drop_deg_per_frame=round(drop_max(M["lip_elev_max"]), 3),
                   cam_y_range_m=[round(float(M["cam_y"].min()), 3), round(float(M["cam_y"].max()), 3)],
                   cam_c_range_m=[round(float(M["cam_c"].min()), 2), round(float(M["cam_c"].max()), 2)])
    # ---- 連続性の検査一式（関門の検査器の P13 から写す）
    def pv(k):
        return P13[k]["value"], bool(P13[k]["pass"])
    cont = {k: dict(value=P13[k]["value"], pass_=bool(P13[k]["pass"]), threshold=P13[k]["threshold"]) for k in P13 if isinstance(P13[k], dict) and "value" in P13[k]}
    geom_ok = all(v["pass_"] for v in cont.values())
    common = dict(index_constant_ja="全コマで同じ 96,000 頂点・同じ三角形（包みの約束。Unity の再生も同じ格子）",
                  continuity_P13=cont, continuity_all_pass=geom_ok,
                  continuity_failed=[k for k, v in cont.items() if not v["pass_"]])
    step_ok = pv("(1) 波の枠の 1 コマの変位（30 Hz）_m")[1]
    missing_ok = pv("(5a) 唇・管の三角形の面積の最小_m2")[1] and pv("(6) 法線が有限（唇・管の頂点の 1 環の面積の最小 > 0）_m2")[1]
    tear_ok = pv("(5d) 辺の長さの K* に対する比（行の間、縦と斜め）")[1]
    selfx_ok = pv("(5f) 自己交差（巻きの行の断面と、隣り合う巻きの行の間の中央の面）")[1]
    h2 = int(2 * hz)
    items = {}
    ok80_words = bool(step_ok and missing_ok and drop_max(S["centre_elev_max"]) < 1.0 and cen_f[its] > cen_f[h2] + 20)
    items["80"] = dict(name_ja="船上の正面中央で、波の上側を上昇前から上昇後まで続けて見られる（形の切替・欠落 0）",
                       value=dict(common, centre_band_elev_deg={("t%d" % k): round(float(cen_f[int(k * hz)]), 2) for k in (0, 2, 4, 6, 8, 9, 10, 11)} | {"tstar": round(float(cen_f[its]), 2)},
                                  centre_band_max_drop_deg_per_frame=round(drop_max(S["centre_elev_max"]), 3),
                                  moving_eye_record=mov),
                       verdict_af30_formula="合格" if (geom_ok and drop_max(S["centre_elev_max"]) < 1.0 and cen_f[its] > cen_f[h2] + 20) else "不合格",
                       verdict_item_words="合格" if ok80_words else "不合格",
                       reading_ja="項目の言葉の読み：形の切替（添字は同じ）・欠落（(5a)・(6)）・位置跳び（(1)）が 0 で、中央の帯の仰角が 1 コマで 1° 以上下がらず、"
                                  "t = 2 s から t* までに 20° 以上上がる。美術優先30 の式は、これに連続性の検査一式がすべて合格を足す")
    items["106"] = dict(name_ja="船上の正面中央から左右まで、水面が同じ一面として上へ移る（裂け・位置跳び 0）",
                        value=dict(common, left_elev_tstar=round(float(S["left_elev_max"][its]), 2), right_elev_tstar=round(float(S["right_elev_max"][its]), 2),
                                   centre_elev_tstar=round(float(cen_f[its]), 2),
                                   left_max_drop_deg_per_frame=round(drop_max(S["left_elev_max"]), 3), right_max_drop_deg_per_frame=round(drop_max(S["right_elev_max"]), 3),
                                   rows_ja="左 = 手前の肩の行（c が座席 −25〜−5 m）、中央 = 座席 ±5 m、右 = 奥の行（座席 +5〜+15 m）の水面の最大仰角"),
                        verdict_af30_formula="合格" if geom_ok else "不合格",
                        verdict_item_words="合格" if (step_ok and tear_ok and selfx_ok) else "不合格",
                        reading_ja="項目の言葉の読み：裂け（(5d) 行の間の伸び・(5f) 自己交差）と位置跳び（(1)）が 0")
    flips_region = int(S["face_flips_region"].sum())
    ok107 = bool(S["face_normal_up_deg"][0] < 1.0 and S["face_normal_to_seat"][its] > 0.3 and face_turn_max < 5.0)
    items["107"] = dict(name_ja="船側の水面が上向きから船向きへ連続して変わる（面の反転・位置跳び 0）",
                        value=dict(common, face_normal_up_deg={"t0": round(float(S["face_normal_up_deg"][0]), 2), "t8": round(float(S["face_normal_up_deg"][int(8 * hz)]), 2),
                                                               "tstar": round(float(S["face_normal_up_deg"][its]), 2)},
                                   face_normal_dot_to_seat_tstar=round(float(S["face_normal_to_seat"][its]), 3), face_normal_turn_max_deg_per_frame=round(face_turn_max, 3),
                                   face_flips_in_item_region_30hz=flips_region,
                                   t0_note_ja="t 0 の法線の傾き（上から）は、海のうねり（Hs 5 m）と搬送波で水面が傾く分。美術優先30 の『< 1°』は平らな海の rig の読み",
                                   face_flips_whole_mesh_P13_5g=P13["(5g) 面の反転（30 Hz、向きの決まった最後のコマと比べる）"]["value"],
                                   region_ja="座席の近くの行（c が座席 ±5 m）の内壁（列 j_corner〜j_facebot）。P13 の (5g) の 130 は奥の端の行 227〜234（c +12.8〜+14）で、この範囲の外"),
                        verdict_af30_formula="合格" if (geom_ok and ok107) else "不合格",
                        verdict_item_words="合格" if (ok107 and flips_region == 0 and step_ok) else "不合格",
                        reading_ja="項目の言葉の読み：項目の範囲の面の反転 0・位置跳び 0 で、平均の法線が上向き（t 0 で 1° 未満）から座席の方へ（t* で座席の向きとの内積 > 0.3）1 コマ 5° 未満の回りで変わる")
    lip_el = S["lip_elev_max"]
    lip_drop = drop_max(lip_el)
    ok108_elev = bool(np.nanmax(lip_el) >= 60.0 and lip_drop < 1.0 and lip_f[h2] < 20.0)
    ok108_over = bool(S["lip_within5m"].max() > 0 or S["zenith70"].max() > 0)
    items["108"] = dict(name_ja="船上から、前方の水面が船側へ延びて座席の上に入る過程を見られる",
                        value=dict(lip_elev_max_deg={("t%d" % k): round(float(lip_f[int(k * hz)]), 2) for k in (2, 6, 8, 10)} | {"tstar": round(float(lip_f[its]), 2),
                                                                                                                                 "max": round(float(np.nanmax(lip_el)), 2)},
                                   lip_elev_max_drop_deg_per_frame=round(lip_drop, 3),
                                   near_rows_tip_elev_deg_tstar=round(float(S["near_tip_elev"][its]), 2),
                                   lip_horizontal_min_m_tstar=round(float(S["lip_hdist_min"][its]), 3),
                                   lip_points_within_5m_horizontal_max=int(S["lip_within5m"].max()),
                                   water_points_elev_ge_70deg_max=int(S["zenith70"].max()),
                                   lip_elev_max_over_all_frames_at_s=round(float(ts[int(np.nanargmax(lip_el))]), 4),
                                   frames_before_tstar_above_tstar=int((lip_f[:its] > lip_f[its] + 1e-9).sum()),
                                   moving_eye_record=mov),
                        verdict_elevation_reading="合格" if ok108_elev else "不合格",
                        verdict_overhead_reading="合格" if ok108_over else "不合格",
                        reading_ja="(1) 仰角の読み（美術優先30 が置いた読み）：同じ水面（唇）の仰角が前方（t = 2 s で 20° 未満）から 60° 以上へ途切れずに"
                                   "（1 コマで 1° 以上下がらない）上がる。(2) 真上の読み：座席から水平 5 m 以内・仰角 70° 以上に水面が来る。"
                                   "どちらを判定に使うかは美術優先30 から保留（利用者の選択待ち）。仕上げ27 の判断（Q24）は記録に書く")
    ok111 = bool(tip[its] < -20 and tipdir_step < 3.0 and tip_jump_max < 0.6)
    ok111_local = bool(tip[its] < -20 and tipdir_step < 3.0 and tipl_jump_max < 0.6)
    items["111"] = dict(name_ja="座席の上へ延びた水面の先が、下向きに曲がる過程を見られる（位置跳び・欠落 0）",
                        value=dict(common, tip_dir_deg={("t%d" % k): round(float(tip[int(k * hz)]), 2) for k in (6, 8, 9, 10, 11)} | {"tstar": round(float(tip[its]), 2), "max": round(float(tip.max()), 2)},
                                   tip_dir_step_max_deg_per_frame=round(tipdir_step, 3), tip_jump_max_m_per_frame=round(tip_jump_max, 4),
                                   tip_jump_max_m_per_frame_wave_frame=round(tipl_jump_max, 4),
                                   tip_jump_note_ja="地面（世界）の 1 コマの移動は、波の約 20 m/s の進み（1/30 s で約 0.67 m）を含む。美術優先30 の 0.6 m の目安は、その場で育つ rig の値。"
                                                    "波の枠（局所）の移動も書く",
                                   tstar_vs_kstar_ok=bool(GJ["gates"]["Painting"]["pass"]), P4=GJ["gates"]["P4"]["value"], P16=GJ["gates"]["P16"]["value"],
                                   rows_ja="座席の近くの行（c が座席 ±3 m）の唇先の向き（唇の上面の最後の 8 列（j_tip−8〜j_tip）、断面の中の水平からの角の中央値。負が下向き）"),
                        verdict_af30_formula="合格" if (ok111 and geom_ok) else "不合格",
                        verdict_item_words="合格" if (ok111 and step_ok and missing_ok) else "不合格",
                        verdict_item_words_wave_frame="合格" if (ok111_local and step_ok and missing_ok) else "不合格",
                        reading_ja="項目の言葉の読み：t* の唇先の向きが −20° より下向き、1 コマの向きの変化 < 3°、唇先の 1 コマの移動 < 0.6 m、位置跳び・欠落 0。"
                                   "美術優先30 の式は、これに連続性の検査一式と t* = K* を足す")
    rep = dict(schema="GreatWave.pl27.seat_items/1", package=DG.rel(ab(a.package)), pos_sha256=pk.pos_sha, kstar=DG.rel(kd),
               timewarp=dict(path=DG.rel(ab(a.timewarp)), sha256=DG.sha256_file(ab(a.timewarp))),
               gates_json=dict(path=DG.rel(ab(a.gates_json)), sha256=DG.sha256_file(ab(a.gates_json))),
               seat=dict(path=DG.rel(SEAT), sha256=DG.sha256_file(SEAT), eye_world=eye.tolist(), c_seat_m=round(c_seat, 3)),
               landmarks=dict(j_top=jT, j_tip=jP, j_corner=jK, j_facebot=jF),
               rows=dict(near=[int(near_rows.min()), int(near_rows.max())], face=[fr0, fr1], left=[int(left_rows.min()), int(left_rows.max())],
                         right=[int(right_rows.min()), int(right_rows.max())] if len(right_rows) else None, lip_rows=int(len(lip_rows))),
               hz=hz, evidence_kind_ja="包み（16 bit の Hermite）を numpy で読んだ幾何の測定。描画ではない。座席は固定の座席 v1（体験の場面の動く目は記録のみ）",
               items=items, runtime_s=round(time.time() - t0, 1))
    os.makedirs(os.path.dirname(ab(a.out)), exist_ok=True)
    with open(ab(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    np.savez_compressed(os.path.splitext(ab(a.out))[0] + "_series.npz", t=ts, **{k: v for k, v in S.items()})
    for k, v in items.items():
        print(k, {kk: vv for kk, vv in v.items() if kk.startswith("verdict")})
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
