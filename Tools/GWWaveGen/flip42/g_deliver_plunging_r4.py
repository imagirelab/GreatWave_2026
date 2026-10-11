# -*- coding: utf-8 -*-
"""FLIP42：報告 Docs/Progress/FLIP_Plunging_ja.md に R4（R4d、粒子 0.1767578125 m）を足した時の証拠の追加。2026-10-11。
- 10/10 に g_deliver_plunging.py で作った Docs/Evidence/FLIPPlunging/ に、R4 の動画・断面の並び・図（fp_10〜fp_15）と、
  R4・R4fix の記録、独立の確かめ check/R4、A3' の出し直し a3fix の写しを足す（バイトはそのまま）。
  flip42/record_ja.md の写しは 10/11 の版に替える（10/10 17:45 の写しの SHA-256 は run.json の replaced_copies に残す）。
- metrics.json：g_deliver_plunging.metrics()（10/10 の項目）を作り直した上で、R4 の値と判定を足し、A3' を符号を直した値にする
  （10/10 の値は old_sign_20261010 として残す）。
- run.json：今の run.json を読み、写し・R3d と R4d の起動と時間・使った計算の記録の SHA-256・道具の SHA-256（x_r4fix_*.py も入れる）・
  直した道具・改めの記録を足す。10/10 の項目は消さない。
- 10/11 13 時台：2 回目の独立の確かめ check/R4b の写しを flip42/check/R4b/ に足し、metrics.json に直し（apply_r4b）を入れ、run.json に改めの記録を足した。
g_deliver_plunging.py は 10/10 の証拠を作った時のまま残す。走らせ直すと 10/10 の写し・metrics.json・run.json に戻るので、
10/11 から後は走らせない（走らせた時は、続けてこの道具を走らせる）。
新しい流体の計算はしない。Houdini は起動しない。git の操作とダウンロードはしない。何も消さない。
使い方：py -3.10 -B Tools/GWWaveGen/flip42/g_deliver_plunging_r4.py（何度走らせても同じ形になる）
"""
import sys, os, json, glob, hashlib, shutil, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g_deliver_plunging as D0

REPO, F42, OUT, TOOLS = D0.REPO, D0.F42, D0.OUT, D0.TOOLS
rel, sha, fileinfo, J = D0.rel, D0.sha, D0.fileinfo, D0.J
MAX_FILE = 20 * 1024 * 1024
TC, LC = 9.507500301523587, 135.46329754326246
T_OB, X_OB = 159.30, 584.5

FIGS_R4 = [
    ("fp_10_side_R4.mp4", "R4/R4_first_side.mp4",
     "R4（R4d、粒子 0.1767578125 m）を横から。fp_1 と同じ形：上の段は造波板から 300〜750 m、下の段は巻き始めの頂 512 m の周り。"
     "114.5 s から巻き始めの 1.5 Tc 前までは実時間、そこから半分の速さ（巻く所は 0:55〜1:04）。縦横同じ縮尺、赤い縦棒＝10 m、点線＝静かな水面。"
     "印は「D&K の表の着水の値（計算の条件の表）」と「唇が前の面に付いた時（記録の着水）」。見出しの粒子は 3 桁に丸めて「0.177 m」"),
    ("fp_11_crest_R4_half.mp4", "R4/R4_side_finest.mp4",
     "R4 の頂の周り（±1 波長と ±0.4 波長の拡大）、138.2 s から、半分の速さ（巻く所は 0:33〜0:44）。fp_2 と同じ形。video/R4d_crest_half.mp4 と同じ物"),
    ("fp_12_strip_R4.png", "R4/R4_first_strip.png",
     "R4 の断面の並び（巻き始めにそろえた −0.3〜+0.3 Tc と、唇が前の面に付いた時）。数字は η_c と H（前の谷まで）。fp_3 と同じ形"),
    ("fp_13_c_strip_R3_R4.png", "R4/figs/c_strip_R3_R4d.png",
     "R3（上）と R4（下）の断面の並び（同じく巻き始めにそろえた時刻）"),
    ("fp_14_c_overlay_R2_R3_R4.png", "R4/figs/c_overlay.png",
     "巻き始めにそろえた時刻の断面の線を R2・R3・R4 で重ねた図（x は各計算の巻き始めの点から）。「着水」は記録の決まり（唇が前の面に付いて空気を囲んだ時）"),
    ("fp_15_c_series_R2_R3_R4.png", "R4/figs/c_series.png",
     "巻き始めからの時刻で見た η_c・H・前の面の最大の傾き・頂の位置（R2・R3・R4）"),
]
CHECK4 = ["check/R4/" + os.path.basename(p) for p in sorted(glob.glob(F42 + "/check/R4/*")) if os.path.isfile(p)] + \
         ["check/R4/frames/" + os.path.basename(p) for p in sorted(glob.glob(F42 + "/check/R4/frames/*.png"))]
# 10/11 13 時台：この報告の版の 2 回目の独立の確かめ（check/R4b）。道具・出力・まとめ（check_ja.md）をそのまま写す
CHECK4B = ["check/R4b/" + os.path.basename(p) for p in sorted(glob.glob(F42 + "/check/R4b/*"))
           if os.path.isfile(p) and not p.endswith(".pyc")]
R4FIX_TESTS = ["R4fix/tests/" + os.path.basename(p) for p in sorted(glob.glob(F42 + "/R4fix/tests/*")) if os.path.isfile(p)]
MIRROR_R4 = [
    ("record_ja.md", "計算の記録（計画の読み方、計画から変えた所 1〜8、R4 の試し、解析の道具の直し 10/11）。10/11 の版"),
    ("R4/record_ja.md", "R4（R4d）の段の記録。冒頭に独立の確かめを受けた〔10/11 訂正〕"),
    ("R4/C_R3_vs_R4d.json", "(c) 細かさの比べ R3 と R4（計画の判定）"),
    ("R4/C_R2_vs_R4d.json", "(c) 参考 R2 と R4"),
    ("R4/visual_R2_R3_R4d.json", "見た目の量（R2・R3・R4、x_r4_visual.py）"),
    ("R4/cfg_R4d.json", "R4d の設定（最初の 2 回の起動）"),
    ("R4/cfg_R4d_b.json", "R4d の設定（途中保存の間隔の候補を足した後）"),
    ("R4fix/record_ja.md", "R4 が走らなかった原因（場の端の丸めのずれ）と直し（粒子 0.1767578125 m）、R3d の確かめ"),
    ("R4fix/C_R3_vs_R3d.json", "R3 と R3d の C1〜C4（差 0）"),
    ("R4fix/surfdiff.json", "R3 と R3d・R3m の巻き始めの前の水面の差"),
    ("R4fix/cfg_R4d.json", "R4d の設定（R4fix で用意した物）"),
    ("R4fix/cfg_R3d.json", "R3d の設定"),
] + [(p, "R4fix の短い試しの出力と道具") for p in R4FIX_TESTS] + \
    [(p, "R4（R4d）の独立の確かめ（自前の道具・出力・動画のコマ）") for p in CHECK4] + [
    ("a3fix/a3p_fix.json", "A3' を符号を直して出し直した値（R1b・R2・R3・R4d）と 10/9 の版の値（x_a3fix.py）"),
] + [(p, "R4 を足した報告の版の 2 回目の独立の確かめ R4b（自前の道具・出力・まとめ。10/11 13 時台）") for p in CHECK4B]
RUN_NOTE_R4 = {
    "R3d": "R3 の 138.2 s（3318 コマ目の途中保存）から、R4 の直しの決まり（格子を 2 進で割り切れる値に）を当てはめた設定で 158.3 s まで。R3 とビット単位で同じ",
    "R4d": "計画の R4 の粒子 0.177 m を 0.1767578125 m（格子 0.353515625 m）にしたもの。計画の R4 として走らせた。187.8 s まで",
}


def cpack(c):
    return dict(C1_dt_s=round(c["C1"]["dt"], 3), C1_dx_m=round(c["C1"]["dx"], 2), C2_H=round(c["C2"]["H"][2], 4), C2_eta_c=round(c["C2"]["eta_c"][2], 4),
                C3=round(c["C3"]["steep"][2], 4), C4_time=round(c["C4"]["jet_time"][2], 4), C4_dist=round(c["C4"]["jet_dist"][2], 4))


def r4(v, n=4):
    return round(float(v), n)


def metrics():
    m = D0.metrics()
    a4 = J(F42 + "/runs/R4d/ana.json")
    fx = J(F42 + "/a3fix/a3p_fix.json")
    cv = J(F42 + "/check/R4/check_R4_conv.json")
    ge = J(F42 + "/check/R4/check_R4_geom.json")
    c34 = J(F42 + "/R4/C_R3_vs_R4d.json"); c24 = J(F42 + "/R4/C_R2_vs_R4d.json")
    m["date"] = "2026-10-11"
    m["note_ja"] += "。10/11：R4（R4d、粒子 0.1767578125 m）の値と判定を足し、A3' を符号を直した値にした（g_deliver_plunging_r4.py）"
    it = {x["id"]: x for x in m["items"]}
    # A1
    a = it["A1"]
    a["value"] = dict(R3=a["value"], R4=dict(bands=[dict(components=b["components"], amp_ratio=r4(b["amp_ratio"]), phase_rad=r4(b["phase_rad"]))
                                                   for b in a4["A1"]["subbands"]], S=r4(a4["A1"]["S_measured"])))
    a["name_ja"] = "帯の出口（造波板から 33.9 m）の 3 帯域の振幅の比・位相と測った S（R3・R4）"
    a["verdict_ja"] = "外れた（成分 22〜32：R3 振幅 0.945、R4 振幅 0.949・位相 +0.115 rad）"
    a["source"] = "runs/R3/ana.json・runs/R4d/ana.json A1"
    # A2'
    a = it["A2p"]
    a["value"]["R4"] = dict(speed_err=r4(a4["A2p"]["speed_err_wmean"]), amp_change=r4(a4["A2p"]["amp_change_wmean"]))
    a["source"] += "。R4 は runs/R4d/ana.json A2p"
    # A3'
    a = it["A3p"]
    keys = ("dx_focus_over_Lc", "dt_focus_over_Tc", "crest_ratio", "H_ratio")
    short = dict(dx_focus_over_Lc="dx_over_Lc", dt_focus_over_Tc="dt_over_Tc", crest_ratio="crest_ratio", H_ratio="H_ratio")
    def pk(d):
        return {short[k]: round(d[k], 4) for k in keys}
    a["name_ja"] = "集まり：測った速さと減りを入れた線形の焦点の模型（R3・R4 で判定。R1b・R2 は記録）"
    a["value"] = dict(R3=pk(fx["runs"]["R3"]["fixed"]), R4=pk(fx["runs"]["R4d"]["fixed"]),
                      R1b_record=pk(fx["runs"]["R1b"]["fixed"]), R2_record=pk(fx["runs"]["R2"]["fixed"]),
                      R4_shift_smaller_than_R3=fx["R4_smaller_than_R3"],
                      old_sign_20261010={r: pk(fx["runs"][k]["old_sign"]) for r, k in (("R1b", "R1b"), ("R2", "R2"), ("R3", "R3"), ("R4", "R4d"))},
                      note_ja="10/10 の値（old_sign_20261010）は解析の道具 g_analyze.py が測った位相と速さの誤差を逆の符号で入れていた値。"
                              "10/11 11:35 に道具を直し、残した記録から出し直した（Unity/Build/FLIP42/record_ja.md「解析の道具の直し」）")
    a["tolerance_ja"] = "場所 ±0.1 Lc・時刻 ±0.1 Tc・頂と H の比 0.95 以上、R4 のずれが R3 より小さいこと"
    a["verdict_ja"] = ("外れた（R3 +0.15 Lc・+0.11 Tc・頂 0.873、R4 +0.24 Lc・+0.19 Tc・頂 0.875。R4 のずれも R3 より大きい）。"
                       "直した向き（焦点が先・遅く）は、計算が線形の焦点より手前・早く崩れたことの説明にならない")
    a["source"] = "Unity/Build/FLIP42/a3fix/a3p_fix.json（写し flip42/a3fix/a3p_fix.json）、check/R4/check_ja.md 見つけた所 1"
    # B1
    a = it["B1"]
    a["value"]["R4"] = r4(a4["B1"]["loss_exit_to_m10"])
    a["tolerance_ja"] = "5 % 以内（R3・R4 で判定）"
    a["verdict_ja"] = "外れた（R3 7.1 %、R4 6.0 %）"
    # C：R3 と R4
    a = it["C_res_R3_R4"]
    a["value"] = cpack(c34)
    a["verdict_ja"] = ("入った。C3 は幅の端まで 1.3 % 分で、近い読み方（弦の長さ・巻き始めのコマ）では −10.2〜−11.3 % になる。"
                       "前の面の険しさと巻き始めの場所は R2→R3→R4 でまだ同じ向きに動いている（C_trend）。唇・空気は C1〜C4 の外で落ち着かない")
    a["name_ja"] = "細かさ：R3 と R4（R4d、粒子 0.1767578125 m。比の基準は R4）"
    a["source"] = "Unity/Build/FLIP42/R4/C_R3_vs_R4d.json（写し flip42/R4/）、check/R4/check_ja.md 見つけた所 2・3、check_R4_onset_sens.json"
    new = []
    for x in m["items"]:
        new.append(x)
        if x["id"] == "C_res_R3_R4":
            new.append(dict(id="C_res_R2_R4", name_ja="参考：R2 と R4", value=cpack(c24), tolerance_ja=x["tolerance_ja"],
                            verdict_ja="記録のみ（C1 だけ入る）", source="Unity/Build/FLIP42/R4/C_R2_vs_R4d.json"))
            tr = {}
            for k, nm in (("onset_t", "巻き始めの時刻 s"), ("onset_x", "巻き始めの場所 m"), ("eta_c", "η_c m"), ("steep", "前の面の険しさ"),
                          ("jet_dist", "噴流の距離 m"), ("H_front_rule", "H（前の谷まで）m"), ("air_max", "最大の空気 m²")):
                q = cv[k]
                tr[k] = dict(name_ja=nm, R2=round(q["R2"], 4), R3=round(q["R3"], 4), R4=round(q["R4"], 4),
                             p=None if q.get("p") is None else round(q["p"], 2), extrap=None if "extrap" not in q or q.get("p") is None or k == "air_max" else round(q["extrap"], 4),
                             note_ja=q.get("note", "") if k != "air_max" else "近づいていない")
            new.append(dict(id="C_trend", name_ja="細かさの並び R2（0.35 m）→ R3（0.25 m）→ R4（0.177 m）と 3 点の外挿（目安）", value=tr,
                            tolerance_ja="—", verdict_ja="記録のみ。η_c と噴流の距離は落ち着いた。前の面の険しさと巻き始めの場所はまだ同じ向きに動く。"
                                                       "H（前の谷まで）は頂から 30 m 先の谷が深くなるので近づかない。空気は近づかない",
                            source="check/R4/check_R4_conv.json"))
    m["items"] = new
    it = {x["id"]: x for x in m["items"]}
    # D1〜D3
    it["D1"]["value"] = it["D1"]["value"] + "。R4 も同じ順（156.13 s に前の面の静かな水面から 4.1〜7.2 m の所で 3.3 m² の空気を囲んだ）"
    d2 = ge["D2_R4d"]
    it["D2"]["value"] = dict(R3=it["D2"]["value"], R4=dict(x=round(d2["x"], 1), t=154.875))
    it["D2"]["source"] += "、check/R4/check_R4_geom.json D2_R4d"
    d3 = ge["D3_R4d"]
    v3 = it["D3"]["value"]
    it["D3"]["name_ja"] = "着水の時刻と場所（計画どおり R4 で判定。記録の決まりでは唇の先が前の面に付いて空気を囲んだ時）"
    it["D3"]["value"] = dict(R4=dict(t=round(d3["t"], 3), x=round(d3["x"], 1), dt_s=round(d3["dt"], 2), dt_over_Tc=round(d3["dt_Tc"], 3),
                                     dx_m=round(d3["dx"], 1), dx_over_Lc=round(d3["dx_Lc"], 3), air_m2=3.27, air_height_above_still_m=[4.05, 7.21],
                                     alt_second_jet=dict(t=156.917, x=549.9, dt_over_Tc=-0.251, dx_over_Lc=-0.255)),
                             R3_reference=v3 if "R4" not in v3 else v3.get("R3_reference"))
    it["D3"]["verdict_ja"] = "外れた（R4 で判定、−0.33 Tc・−0.38 Lc）。比べた出来事も同じではない（噴流の先は静かな水面の高さに届いていない）"
    it["D3"]["source"] = "check/R4/check_R4_geom.json D3_R4d、check/R2/check_R2_geom.json R3.events.touch_air（参考）"
    # R4
    it["R4"]["name_ja"] = "粒子 0.177 m（計画の R4）と 0.1767578125 m（R4d）"
    it["R4"]["value"] = ("計画の 0.177 m は、格子 0.354 m が 2 進の小数で割り切れず、場の箱の端が丸めで 3 × 10⁻⁵ m ずれて圧力が 0 になり、水が自由落下した。"
                         "粒子を 0.1767578125 m（0.14 % 小さい）にした R4d は 4,508 コマ（187.8 s）まで走った（15.2 時間、起動 32 回、水面の見張りは働かなかった）。"
                         "直しの決まりを 0.25 m に当てはめた R3d は R3 とビット単位で同じ")
    it["R4"]["verdict_ja"] = "R4d を計画の R4 として判定に使った。0.14 % 小さくした効きは確かめていない（0.177 m は走らない）"
    it["R4"]["source"] = "Unity/Build/FLIP42/R4fix/record_ja.md・R4/record_ja.md（写し flip42/R4fix/・flip42/R4/）、check/R4/check_ja.md §6、runs/R4d"
    # 見た目（R4）
    m["items"].append(dict(id="V_R4", name_ja="見た目：R4 の巻き始めの高さ・唇・空気",
                           value=dict(eta_c=9.58, eta_c_max_mid_node=9.61, H_front=10.98, front_trough=-1.40, front_trough_dist=30.0,
                                      H_rear=13.86, rear_trough=-4.28, rear_trough_dist=67.5, steep_h60=1.89,
                                      lip_before_first_contact=[3.87, 1.12], lip_plus_0p2Tc=[3.77, 0.62], second_jet_before_low_air=[6.85, 0.58],
                                      first_air=dict(t=156.125, area=3.27), low_air_ge4=dict(t=157.25, area=16.87), largest_air=dict(t=157.79, area=22.82),
                                      jet_tip_lowest_above_still_m=[1.0, 1.27],
                                      next_crest=dict(t=179.917, x=727.9, steep=0.254, lip=1.35)),
                           tolerance_ja="記録", verdict_ja="記録のみ（唇・空気は計算ごとに変わる）",
                           source="check/R4/check_ja.md §2（自前の読み方）、R4/record_ja.md §7（記録の読み方）。噴流の先の最も低い所は記録 1.0 m・確かめ 1.27 m"))
    apply_r4b(m)
    return m


def apply_r4b(m):
    """10/11 13 時台：2 回目の独立の確かめ check/R4b（check_ja.md）を受けた直し。値は check/R4b の出力から読む（計算はしない）。"""
    d = F42 + "/check/R4b/"
    var = J(d + "b_a3var.json"); geo = J(d + "b_geom.json"); tip = J(d + "b_tipscan.json"); sens = J(d + "b_sens.json"); misc = J(d + "b_misc.json")
    it = {x["id"]: x for x in m["items"]}
    m["note_ja"] += "。10/11 13 時台：2 回目の独立の確かめ check/R4b を受けて、言い方と読み方の幅を直した（判定は変わらない）"
    # A3'：比は入れ方で動く。確かな外れは場所と時刻
    a = it["A3p"]
    a["value"]["input_variants_check_R4b"] = {
        r: {k: dict(dx_over_Lc=round(v["dx_Lc"], 4), dt_over_Tc=round(v["dt_Tc"], 4), crest_ratio=round(v["crest_ratio"], 4), H_ratio=round(v["H_ratio_075Lc"], 4))
            for k, v in var[rk].items() if k != "speed_only_old_sign"}
        for r, rk in (("R3", "R3"), ("R4", "R4d"))}
    a["value"]["input_variants_note_ja"] = ("A2p_const_amp は計画 §5 の A3' の文のまま（A2' の速さと振幅の変化を定数で入れる）。A2p_dist_amp は振幅の変化を距離で伸ばす。"
                                            "speed_only は速さだけ。解析の道具の値（R3・R4）は帯の出口の |R| と距離で伸ばす振幅の変化を入れたもの")
    a["verdict_ja"] += ("。〔R4b〕頂と H の比は測った振幅の入れ方で 0.87〜1.0 と動き、計画の文のままの入れ方では 0.95 の境目（R4 0.950・0.953）。"
                        "どの入れ方でも外れるのは場所と時刻のずれ（R3 +0.15〜+0.185 Lc、R4 +0.22〜+0.265 Lc）")
    a["source"] += "、check/R4b/b_a3var.json（入れ方の感度）"
    # C：まだ動く量に巻き始めの時刻を足す
    c = it["C_res_R3_R4"]
    c["verdict_ja"] = ("入った（R3 と R4 の差が幅の中）。C3 は幅の端まで 1.3 % 分で、近い読み方（弦の長さ・巻き始めのコマ）では −10.2〜−11.3 % になる。"
                       "R2→R3→R4 で落ち着いたのは η_c と噴流の距離。巻き始めの時刻・場所と前の面の険しさはまだ同じ向きに動き、H（前の谷まで）は近づかず、"
                       "C4 の時間は向きが変わった（C_trend、check/R4b の見つけた所 1・2）。唇・空気は C1〜C4 の外で落ち着かない")
    c["source"] += "、check/R4b/check_ja.md"
    t = it["C_trend"]
    t["verdict_ja"] = ("記録のみ。η_c と噴流の距離は落ち着いた。巻き始めの時刻・場所と前の面の険しさはまだ同じ向きに動く。"
                       "H（前の谷まで）は頂から 30 m 先の谷が深くなるので近づかない。C4 の時間は 0.83 → 1.29 → 1.25 s で向きが変わった。空気は近づかない")
    g2, g3, g4 = geo["R2"], geo["R3"], geo["R4d"]
    t["value"]["jet_time"] = dict(name_ja="C4 の時間 s", R2=round(g2["c4_time"], 4), R3=round(g3["c4_time"], 4), R4=round(g4["c4_time"], 4), p=None, extrap=None,
                                  note_ja="向きが変わった（check/R4b/b_geom.json）")
    t["value"]["offset_from_linear_focus"] = dict(name_ja="巻き始めの線形の焦点（592.2 m・171.515 s）からの手前・早さ",
                                                  R2=dict(m=round(592.2 - g2["onset_x"], 1), Tc=round((171.515 - g2["onset_t"]) / TC, 3)),
                                                  R3=dict(m=round(592.2 - g3["onset_x"], 1), Tc=round((171.515 - g3["onset_t"]) / TC, 3)),
                                                  R4=dict(m=round(592.2 - g4["onset_x"], 1), Tc=round((171.515 - g4["onset_t"]) / TC, 3)),
                                                  extrap_ja="68 m・1.71 Tc（3 点の外挿、check/R4b の見つけた所 1）")
    t["source"] += "、check/R4b/b_geom.json"
    # D3：細かさで少し縮むが外挿でも外。R3 の 2 つ目の噴流の場所
    d3 = it["D3"]
    d3["value"]["trend_check_R4b"] = {r: dict(dt_s=round(g["touch_t"] - T_OB, 2), dx_m=round(g["touch_x"] - X_OB, 1),
                                              dt_over_Tc=round((g["touch_t"] - T_OB) / TC, 3), dx_over_Lc=round((g["touch_x"] - X_OB) / LC, 3))
                                      for r, g in (("R2", g2), ("R3", g3), ("R4", g4))}
    d3["value"]["trend_extrap_ja"] = "3 点の外挿 −3.15 s（−0.33 Tc）・−48.5 m（−0.36 Lc）で幅 ±0.25 の外（check/R4b の見つけた所 3）"
    r3 = d3["value"].get("R3_reference") or {}
    if "alt_second_jet" in r3:
        r3["alt_second_jet"] = dict(t=157.083, x=548.45, dt_s=round(157.083 - T_OB, 2), dx_m=round(548.45 - X_OB, 2),
                                    dt_over_Tc=round((157.083 - T_OB) / TC, 3), dx_over_Lc=round((548.45 - X_OB) / LC, 3),
                                    note_ja="10/11 の版の 548.9 m は R2 の段の記録の値。157.083 s に囲んだ空気の前の端は 548.45 m（check/R4b の見つけた所 6）")
    d3["verdict_ja"] = ("外れた（R4 で判定、−0.33 Tc・−0.38 Lc）。細かくすると差は少し縮む（R2 −0.53 Lc → R3 −0.42 → R4 −0.38）が、3 点の外挿でも幅の外。"
                        "比べた出来事も同じではない（噴流の先は静かな水面の高さに届いていない）。着水どうしで D&K の表の値より 0.33〜0.35 Tc 早い")
    d3["source"] += "、check/R4b/b_geom.json"
    # 見た目：読み方で違う値の幅
    v = it["V_R4"]["value"]
    v["readings_ja"] = "値は check/R4 の自前の読み方。読み方で違う値は *_readings に、記録（R4/record_ja.md §7）・check/R4・check/R4b の値を並べた"
    v["lip_plus_0p2Tc_readings"] = dict(record=[3.9, 0.6], check_R4=[3.77, 0.62], check_R4b=[round(g4["aligned"]["2"]["reach"], 2), round(g4["aligned"]["2"]["thick"], 2)])
    v["steep_h60_readings"] = dict(record=1.89, check_R4b=round(g4["h60"], 2), R3_record=1.66, R3_check_R4b=round(g3["h60"], 2))
    v["crest_area_readings_m2_per_m"] = dict(record=184, check_R4b=round(g4["crest_area"], 1), R3_record=178, R3_check_R4b=round(g3["crest_area"], 1))
    v["next_crest_lip_readings"] = dict(record=1.4, check_R4=1.35, check_R4b=round(sens["R4d"]["next_crest"]["lip_max_2s"], 2))
    v["R3_jet_tip_lowest_readings"] = dict(check_R2=1.6, record=1.8, check_R4=1.85, check_R4b=round(tip["R3"]["lowest"][0][0], 2))
    v["jet_tip_lowest_above_still_m"] = [round(tip["R4d"]["lowest"][0][0], 2), 1.27]
    m["storage_runs_dir_20261011"] = dict(bytes=misc["runs_dir"]["bytes"], GB=round(misc["runs_dir"]["GB"], 1), GiB=round(misc["runs_dir"]["GiB"], 1),
                                          note_ja="Unity/Build/FLIP42/runs/ 全体（R3d・R4d を含む）。10/11 13:18 に check/R4b が測った（報告の 10/11 11 時台の版は約 258 GB と書いた）")


def runs_from_jsonl(rows, ids):
    runs = {}
    for r in rows:
        if r["run_id"] not in ids:
            continue
        q = runs.setdefault(r["run_id"], dict(launches=0, hours=0.0, first=r["date"], frames=[r["f_start"], r.get("f_end_done")],
                                               dp=r["parms"]["dp"], narrowband=r["solver"].get("donarrowband"),
                                               cfl=r["parms"].get("cfl"), minsub=r["parms"].get("minsub"),
                                               mg_preconditioner=r["solver_parms"].get("usemgpreconditioner", 0),
                                               hip_sha256=set(), houdini=set()))
        q["launches"] += 1; q["hours"] += (r.get("wall_launch_s") or 0) / 3600.0
        q["frames"][1] = r.get("f_end_done"); q["last"] = r["date"]; q["stopped_last"] = r.get("stopped")
        q["particles_max"] = max(q.get("particles_max", 0), r.get("particles_max") or 0)
        q["hip_sha256"].add(r["hip_sha256"]); q["houdini"].add(r["houdini"])
    for k, q in runs.items():
        q["hours"] = round(q["hours"], 3); q["hip_sha256"] = sorted(q["hip_sha256"]); q["houdini"] = sorted(q["houdini"])
        q["note_ja"] = RUN_NOTE_R4.get(k, "")
    return runs


def main():
    rj = OUT + "/run.json"
    run = J(rj)
    # ---- 写し
    for name, src, note in FIGS_R4:
        if os.path.getsize(F42 + "/" + src) > MAX_FILE:
            raise SystemExit("over 20 MB: " + src)
    old_rec = [c for c in run["copies"] if c["name"] == rel(OUT + "/flip42/record_ja.md")]
    newnames = set()
    adds = []
    for name, src, note in FIGS_R4:
        s = F42 + "/" + src; d = OUT + "/" + name
        shutil.copyfile(s, d)
        adds.append(dict(name=rel(d), src=rel(s), bytes=os.path.getsize(d), sha256=sha(d), same_as_src=sha(d) == sha(s), note_ja=note, added="2026-10-11"))
    for src, note in MIRROR_R4:
        s = F42 + "/" + src; d = OUT + "/flip42/" + src
        if os.path.getsize(s) > MAX_FILE:
            raise SystemExit("over 20 MB: " + src)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(s, d)
        adds.append(dict(name=rel(d), src=rel(s), bytes=os.path.getsize(d), sha256=sha(d), same_as_src=sha(d) == sha(s), note_ja=note, added="2026-10-11"))
    for c in adds:
        newnames.add(c["name"])
    if old_rec and old_rec[0].get("snapshot_ja"):
        o = old_rec[0]
        run["replaced_copies"] = [dict(name=o["name"], bytes=o["bytes"], sha256=o["sha256"], snapshot_ja=o["snapshot_ja"],
                                       replaced_ja="2026-10-11：報告が R4fix と R4 の結果を使うようになったので、写しを 10/11 の版（R4 の段・解析の道具の直しを含む）に替えた")]
    run["copies"] = [c for c in run["copies"] if c["name"] not in newnames] + adds

    # ---- metrics
    mp = OUT + "/metrics.json"
    json.dump(metrics(), open(mp, "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=1)

    # ---- 計算（runs.jsonl の全部の行）
    raw = open(F42 + "/runs/runs.jsonl", "rb").read()
    lines = raw.split(b"\n")
    rows = [json.loads(l) for l in lines if l.strip()]
    assert all(r["run_id"] in D0.RUN_IDS + ["R3d", "R4d"] for r in rows), "runs.jsonl に報告にない計算の行がある"
    nrows = len(rows)
    newruns = runs_from_jsonl(rows[D0.JSONL_ROWS:], {"R3d", "R4d"})
    for k, q in newruns.items():
        run["runs"][k] = q
    tot = dict(launches=sum(q["launches"] for q in run["runs"].values()), hours=round(sum(q["hours"] for q in run["runs"].values()), 2))
    run["runs_total_20261011"] = dict(tot, note_ja="runs.jsonl の %d 行（10/10 の 62 行に R3d 4 行・R4d 32 行を足した）" % nrows)
    run["runs_total_with_unrecorded_20261011"] = dict(launches=tot["launches"] + len(run["unrecorded_launches"]),
                                                     hours=round(tot["hours"] + sum(u["hours"] for u in run["unrecorded_launches"]), 2),
                                                     note_ja="行のない起動 2 回を足した数。R4 の数コマの試し 11 通りと R4fix の短い試し 23 本は含まない")
    run["runs_not_in_jsonl_ja"] = [s for s in run["runs_not_in_jsonl_ja"] if not s.startswith("R4fix")] + [
        "R4fix の短い試し 23 本（2026-10-10 17:25〜19:33。tools x_r4fix_still.py ほか。出力は Unity/Build/FLIP42/R4fix/tests/、写しは flip42/R4fix/tests/）"]
    run["scene"]["runs_with_this_sha"] = [k for k, q in run["runs"].items() if run["scene"]["sha256"] in q["hip_sha256"]]

    # ---- 使った計算の記録
    done = {c.get("path") for c in run["cache_used"]}
    for r in ("R3d", "R4d"):
        for p in sorted(glob.glob(F42 + "/runs/" + r + "/hf_c*.npz") + glob.glob(F42 + "/runs/" + r + "/sec_c*.npz")
                        + [F42 + "/runs/" + r + "/" + n for n in ("ana.json", "shape.json", "cfg.json", "run.json", "chain.log") if os.path.exists(F42 + "/runs/" + r + "/" + n)]):
            if rel(p) not in done:
                run["cache_used"].append(fileinfo(p))
    for n in ("R4d_chain_stdout.txt", "R4d_chain_stdout_b.txt"):
        p = F42 + "/runs/" + n
        if os.path.exists(p) and rel(p) not in done:
            run["cache_used"].append(fileinfo(p))
    run["cache_used"] = [c for c in run["cache_used"] if not (c.get("path") == rel(F42 + "/runs/runs.jsonl") and c.get("first_lines") == nrows)]
    run["cache_used"].append(dict(path=rel(F42 + "/runs/runs.jsonl"), first_lines=nrows, bytes_first_lines=len(raw), sha256_first_lines=hashlib.sha256(raw).hexdigest(),
                                  note_ja="10/11：R3d・R4d の行を足した全部の行（%d 行）の SHA-256。10/10 の 62 行の SHA-256 は上の行" % nrows))
    for r in ("R3d", "R4d"):
        fs = [p for p in glob.glob(F42 + "/runs/" + r + "/ckpt/**", recursive=True) if os.path.isfile(p)]
        run["checkpoints_not_hashed"][r] = dict(files=len(fs), bytes=sum(os.path.getsize(p) for p in fs))

    # ---- 道具
    if "tools_20261010" not in run:
        run["tools_20261010"] = run["tools"]   # 10/10 の提出の時の道具の SHA-256（比べの元）
    old_tools = run["tools_20261010"]
    run["tools"] = {rel(p): sha(p) for p in sorted(glob.glob(TOOLS + "/*.py"))}
    run["tools_changed_20261011"] = {k: dict(before=old_tools.get(k), now=v) for k, v in run["tools"].items() if old_tools.get(k) != v}
    run["tools_excluded_ja"] = ("10/10 は x_r4fix_*.py（R4 の原因の診断の途中の道具）を入れなかった。10/11 から報告が R4fix の直しを使うので入れた。"
                                "除いている道具はない")
    note = ("g_analyze.py（10/11 11:35）：A3' の位相の符号を直した（10/9 の版は a3p_model_old_sign として同じファイルに残した。直す前の SHA-256 は "
            "0a1eedfeb826c469ed48801a2555a9b2e9b2641b6c0632fb49fda6ded1d22ca2）。R1b・R2・R3・R4d の ana.json は直す前の版で作ったもので、書き換えていない。"
            "直した A3' は x_a3fix.py → Unity/Build/FLIP42/a3fix/a3p_fix.json。x_r4_visual.py・x_r4_media.py・x_a3fix.py・g_deliver_plunging_r4.py は 10/10 の後に足した")
    if note not in run["tools_changed_after_runs_ja"]:
        run["tools_changed_after_runs_ja"] = run["tools_changed_after_runs_ja"].split("。10/11：")[0] + "。10/11：" + note

    # ---- そのほか
    run["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if "10/11" not in run["note_ja"]:
        run["note_ja"] += "。10/11：R4（R4d）の証拠を g_deliver_plunging_r4.py で足した（新しい流体の計算はしていない）"
    for c in ("py -3.10 -B Tools/GWWaveGen/flip42/x_a3fix.py   # A3' を符号を直して R1b・R2・R3・R4d の記録から出し直す → Unity/Build/FLIP42/a3fix/a3p_fix.json",
              "py -3.10 -B Tools/GWWaveGen/flip42/g_deliver_plunging_r4.py   # R4 の証拠の追加（10/11）"):
        if c not in run["commands"]:
            run["commands"].append(c)
    run["upstream_commands_ja"]["R4（R4d）"] = ("R4fix：x_r4fix_*.py の短い試し → R4fix/cfg_R4d.json。計算：py -3.10 g_chain2.py（R4/cfg_R4d.json・cfg_R4d_b.json、R3d は R4fix/cfg_R3d.json）。"
                                              "解析：g_analyze.py R4d・g_shape.py R4d・g_shape.py --compare R4d R3（R2）→ R4/C_*.json、x_r4_visual.py → R4/visual_R2_R3_R4d.json、"
                                              "x_a3fix.py → a3fix/a3p_fix.json。動画と図：x_r4_media.py（g_video.py・g_preview.py・g_figs.py・g_figs2.py の字の印だけを差し替え）。"
                                              "独立の確かめ：check/R4/check_R4_geom.py → check_R4_spec.py → check_R4_onset_sens.py → check_R4_conv.py → check_R4_misc.py（解析の道具を使わない）")
    run["versions"]["houdini"] = "Houdini 22.0.466 hython（画面なし。runs.jsonl の全行（R3d・R4d を含む）で 22.0.466。方法の確かめ FLIP41 は 22.0.459）"
    run["metrics"] = dict(fileinfo(mp))
    run["guide"] = dict(fileinfo(OUT + "/" + D0.GUIDE), note_ja=run["guide"].get("note_ja", ""))
    rev = ("2026-10-11 11 時台：R4（R4d）を足した（動画 2 本・断面の並び 2 枚・図 2 枚、R4・R4fix の記録、独立の確かめ check/R4、A3' の出し直し a3fix の写し）。"
           "flip42/record_ja.md の写しを 10/11 の版に替えた。metrics.json に R4 を足し A3' を直した値にした。道具に x_r4fix_*.py を入れた")
    if rev not in run["revisions_ja"]:
        run["revisions_ja"].append(rev)
    rev_b = ("2026-10-11 13 時台：この版の 2 回目の独立の確かめ check/R4b を受けて、報告の言い方と読み方の幅を直した（まだ動く量に巻き始めの時刻、"
             "§5 の「C1〜C4 まで落ち着いた」、D3 の差が細かさで少し縮むこと、A3' の比が入れ方で 0.95 の境目まで動くこと、着水どうしの比べ、R3 の 2 つ目の噴流 548.5 m、"
             "runs/ 259 GB（241 GiB）など）。check/R4b の写しを flip42/check/R4b/ に足し、metrics.json に直しを入れた。判定は変わらない。新しい計算はしていない")
    if rev_b not in run["revisions_ja"]:
        run["revisions_ja"].append(rev_b)
    run["storage_runs_dir_20261011"] = J(OUT + "/metrics.json")["storage_runs_dir_20261011"]
    if "check/R4b" not in run["upstream_commands_ja"]["R4（R4d）"]:
        run["upstream_commands_ja"]["R4（R4d）"] += ("。2 回目の独立の確かめ：check/R4b/b_spec.py → b_a3var.py → b_geom.py → b_sens.py → b_misc.py → b_tipscan.py"
                                                   "（解析の道具と check/R4 の道具を使わない）。まとめ check/R4b/check_ja.md")
    json.dump(run, open(rj, "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=1)
    print("copies added", len(adds), "runs", run["runs_total_20261011"], run["runs_total_with_unrecorded_20261011"],
          "ckpt R3d/R4d", run["checkpoints_not_hashed"]["R3d"], run["checkpoints_not_hashed"]["R4d"],
          "tools changed", list(run["tools_changed_20261011"].keys()))


if __name__ == "__main__":
    main()
