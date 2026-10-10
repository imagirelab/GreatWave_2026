# -*- coding: utf-8 -*-
"""FLIP42：報告（Docs/Progress/FLIP_Plunging_ja.md）の証拠 Docs/Evidence/FLIPPlunging/ を作る。2026-10-10。
- 図・動画（印の字を直した _v2）・凍結した計画と見直し・計算の記録・独立の確かめを写す（バイトはそのまま）。
- metrics.json：判定の項目 → 値 → 結果（入った／外れた／判定できない／記録のみ）。値は ana.json・shape.json・C_*.json・
  N1N2.json・独立の確かめの JSON から読む。
- run.json：道具・場面・計算（起動の数と時間）・写したファイルと、使った計算の記録（一番上の水面の高さ・断面の水面の場・
  解析の JSON）の SHA-256。途中保存（ckpt）は解析と動画に使っていないので、数と大きさだけ書く。
新しい流体の計算はしない。Houdini は起動しない。git の操作とダウンロードはしない。何も消さない。
使い方：py -3.10 -B Tools/GWWaveGen/flip42/g_deliver_plunging.py（作業フォルダーはどこでもよい）
2026-10-10 18 時台の直し（報告の見直しを受けて）：R3b の手で止めた 11 回目と R4 の 1 回目を起動の数と時間に足した。
record_ja.md の写しは 17:45 の版のまま残す（その後に R4 の診断などが元の記録へ書き足したため。下の SNAPSHOT_KEEP）。
R4 の診断の計算（R3d・R4d）が runs.jsonl に行を足していくので、報告に使った計算だけを数え、runs.jsonl は最初の 62 行の SHA-256 で残す。
flip42/README_ja.md（写しの案内、手で書いた）の SHA-256 も残す。
"""
import sys, os, json, glob, hashlib, shutil, platform, datetime
import numpy, scipy, PIL

REPO = r"G:/Unity/GreatWave_2026_Fresh"
F42 = REPO + "/Unity/Build/FLIP42"
OUT = REPO + "/Docs/Evidence/FLIPPlunging"
TOOLS = REPO + "/Tools/GWWaveGen/flip42"
SCENE = REPO + "/Houdini/FLIP42/g_tank.hiplc"
MAX_VIDEO = 20 * 1024 * 1024
# R4 の原因の診断（別に走っている、結果は 10/12 の見込み）の途中の道具。この報告には使っていないので、道具の一覧に入れない
EXCLUDE_PREFIX = "x_r4fix_"
# 報告に使った計算（runs.jsonl の run_id）。R4 の診断の R3d・R4d などは数えない
RUN_IDS = ["smoke_dp0.5", "smoke2_dp0.5", "R1", "R1b", "R3", "R3b", "R5p", "R2", "R3m", "R4"]
JSONL_ROWS = 62   # 報告に使った runs.jsonl の行（2026-10-10 16:19 までの全部の行）
# 写しを作った後に元が書き足されたもの：写しは作った時の版のまま残し、写しと元の SHA-256 を両方書く
SNAPSHOT_KEEP = {"record_ja.md": "2026-10-10 17:45 の版。その後、17:55〜17:58 に R4 の診断が「計画から変えた所」6 と「R4 の試し」への注を、"
                                 "18:12 に進行役が「計画の読み方」8 についての追記を、元の記録に書き足した。報告は診断の途中の結果を使わないので、写しは 17:45 の版のまま"}
GUIDE = "flip42/README_ja.md"


def rel(p):
    p = p.replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO) else p


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fileinfo(p):
    st = os.stat(p)
    return dict(path=rel(p), bytes=st.st_size, sha256=sha(p),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))


def J(p):
    return json.load(open(p, encoding="utf8"))


# ---------------------------------------------------------------- 写すもの
FIGS = [
    ("fp_1_side_R3_v2.mp4", "preview/R2_first_side_v2.mp4",
     "R3（粒子 0.25 m）を横から。上の段は造波板から 300〜750 m（群が集まり、険しくなる所）、下の段は巻き始めの頂の周り 460〜568 m。"
     "114.5 s から巻き始めの 1.5 Tc 前までは実時間、そこから半分の速さ。縦横同じ縮尺、赤い縦棒＝10 m、点線＝静かな水面。"
     "印の字だけを直した版（元は preview/R2_first_side.mp4。「実験の着水」→「D&K の表の着水の値（計算の条件の表）」、"
     "R3 の「着水」→「唇が前の面に付いた時（記録の着水）」）"),
    ("fp_2_crest_R3_half_v2.mp4", "R2/R2_side_finest_v2.mp4",
     "R3 の頂の周り（巻き始めの頂 507 m の ±1 波長と ±0.4 波長の拡大）、138.2 s から、半分の速さ。印の字だけを直した版"
     "（元は R2/R2_side_finest.mp4。「D&K の着水」→「D&K の表の着水の値（計算の条件の表）」、R3 の「着水」→「唇が前の面に付いた時（記録の着水）」）"),
    ("fp_3_strip_R3_v2.png", "preview/R2_first_strip_v2.png",
     "R3 の断面の並び（巻き始めにそろえた −0.3〜+0.3 Tc と最初の接触）。数字は η_c と H（前の谷まで）。8 枚目の題だけを"
     "「着水」→「唇が前の面に付いた時・記録の「着水」」に直した版（元は preview/R2_first_strip.png）"),
    ("fp_4_xt_R3.png", "R2/figs/xt_R3.png",
     "R3 の水面の高さの時間と場所の図（群が集まる様子）。緑の点「D&K の着水」は D&K の表 3.1（計算の条件の表）の t_ob・x_ob を 70 倍した値"),
    ("fp_5_gauges_R2_R3.png", "R2/figs/gauges.png",
     "測る点の水面の時系列（R2・R3）と、造波板の位置の目標を線形で進めた値（灰）。位置は造波板から"),
    ("fp_6_spectra_A1_A2.png", "R2/figs/spectra.png",
     "A1（帯の出口の線形に対する振幅の比と位相）と A2'（帯の出口 → −15 の点の速さの誤差と振幅の変化）。赤い横線は A1 の幅"),
    ("fp_7_crestmax_R2_R3.png", "R2/figs/crestmax.png",
     "各場所の最大の頂 η_c（60 s から終わりまで）と線形の重ね合わせ。上の端の「実験で崩れた範囲」と「D&K の着水」の字は重なっている。"
     "「D&K の着水」は D&K の表（計算の条件の表）の x_ob"),
    ("fp_8_c_overlay.png", "R2/figs/c_overlay.png",
     "巻き始めにそろえた時刻の断面の線を重ねた図（R2・R3・R5'・R3m）。「着水」は記録の決まり（唇が前の面に付いて空気を囲んだ時）"),
    ("fp_9_c_strip_R2_R3_R5p.png", "R2/figs/c_strip_R2_R3_R5p.png",
     "R2・R3・R5' の断面の並び（同じ時刻の位置で上下に）。「着水」は記録の決まり（唇が前の面に付いて空気を囲んだ時）"),
]
MIRROR = [  # Docs/Evidence/FLIPPlunging/flip42/ の下に、FLIP42 の中の相対の位置のまま写す
    ("plan/plan_ja.md", "凍結した計画（2026-10-09 13:18）。SHA-256 は plan_frozen.json と同じ"),
    ("plan/plan_numbers.json", "凍結した計画の数"),
    ("plan/plan_frozen.json", "凍結の記録（SHA-256）"),
    ("plan/review_ja.md", "走らせる前の見直し"),
    ("plan/review_numbers.json", "見直しの数"),
    ("record_ja.md", "計算の記録（計画の読み方、計画から変えた所 1〜5、R4 の試し）。10/10 17:45 の写し（SNAPSHOT_KEEP）"),
    ("R1/record_ja.md", "R1・R1b（粒子 0.5 m）の段の記録"),
    ("R1/N1N2.json", "粒子の帯の判定 N1・N2"),
    ("R2/record_ja.md", "R3・R3b・R5'・R2・R3m・R4 の段の記録（§3・§4 の「235 m」「343 m」は帯の出口の測る点からの距離）"),
    ("R2/C_R3_vs_R5p.json", "(c) 時間の刻みの比べ"),
    ("R2/C_R2_vs_R3.json", "(c) 細かさの比べ（条件つき）"),
    ("R2/C_R3_vs_R3m.json", "圧力の前処理の効き"),
    ("check/R1/check_ja.md", "R1・R1b の独立の確かめ"),
    ("check/R1/check_R1.json", "同じ、出力"),
    ("check/R1/check_R1.py", "同じ、確かめの道具（解析の道具を使わない自前の計算）"),
    ("check/R2/check_ja.md", "R2 の段の独立の確かめ（唇と 2 つ目の噴流が落ち着かないこと、D3 の出来事の違い、H の谷の選び方など 11 点）"),
    ("check/R2/check_R2_load.json", "同じ、記録の範囲・重なり・静かな水面"),
    ("check/R2/check_R2_geom.json", "同じ、巻き始め・着水・巻き始めにそろえた量"),
    ("check/R2/check_R2_rows.json", "同じ、全コマの量"),
    ("check/R2/check_R2_more.json", "同じ、最大の頂・測る点・群の次の頂・小刻み"),
    ("check/R2/check_R2_spec.json", "同じ、A1・S・B1"),
    ("check/R2/check_R2_extra.json", "同じ、後ろの谷・A2'・R3b・唇の最大・空気"),
    ("check/R2/check_R2_geom.py", "同じ、確かめの道具"),
    ("check/R2/check_R2_more.py", "同じ、確かめの道具"),
    ("check/R2/check_R2_spec.py", "同じ、確かめの道具"),
    ("check/R2/check_R2_extra.py", "同じ、確かめの道具"),
    ("preview/relabel_check.json", "印の字の直しの確かめ（元の字と新しい字で描いた符号化の前のコマの画素の比べ）"),
]

# 元の字のまま `g_relabel_v2.py orig` で描き直した物が、利用者に出した物とバイト単位で同じだったこと（2026-10-10 17:38、一時置き場で確かめた）
REPRO_ORIG = ["preview/R2_first_side.mp4", "preview/R2_first_strip.png", "R2/R2_side_finest.mp4", "R2/video/R3_crest.mp4"]
RUNS = ["R1", "R1b", "R2", "R3", "R3b", "R3m", "R4", "R5p"]
RUN_NOTE = {
    "smoke_dp0.5": "道具の試し（粒子 0.5 m、200 コマ、起動の区切りと再開）。場面の前の版",
    "smoke2_dp0.5": "道具の試し（小刻みの数え方の直しの確かめ、30 コマ）",
    "R1": "粒子 0.5 m・粒子の帯 4 m。下見と帯の判定。巻かなかった",
    "R1b": "粒子 0.5 m・帯なし。帯の判定（N2 が外れ、以後は帯なし）",
    "R3": "粒子 0.25 m・帯なし。評価の主な計算。154.7 s に巻き始め。21〜04 時は別のプログラムで遅くなった",
    "R3b": "R3 の帯を 2 Lc に（A1 の 1 回目の直し）。直らなかった。11 回目の起動（09:25:51〜09:47:26、3082 コマ目から）を 3360 コマ目（140 s）で手で止めた。"
           "その起動は runs.jsonl に行がない（launches・hours・frames は runs.jsonl の 10 行の値。記録で終わったコマは 3360：runs/R3b/chain.log・log_c3082.txt）",
    "R5p": "R3 の 138.2 s から CFL 半分・最小小刻み 2（時間の刻み）。158.8 s で止めた",
    "R2": "粒子 0.35 m・帯なし（細かさの並び、条件つき）",
    "R3m": "R3 の 138.2 s から圧力の前処理だけ多重格子。158.3 s まで",
    "R4": "粒子 0.177 m・前処理は多重格子。12 コマで水が自由落下し、見張りで止まった。前の不完全コレスキーの起動（15:14:52〜15:15:08）は記録を書く前に止まった（runs.jsonl に行がない）",
}


def metrics():
    a3 = J(F42 + "/runs/R3/ana.json"); a2 = J(F42 + "/runs/R2/ana.json"); a1b = J(F42 + "/runs/R1b/ana.json")
    s3 = J(F42 + "/runs/R3/shape.json")
    c5 = J(F42 + "/R2/C_R3_vs_R5p.json"); c2 = J(F42 + "/R2/C_R2_vs_R3.json"); cm = J(F42 + "/R2/C_R3_vs_R3m.json")
    nn = J(F42 + "/R1/N1N2.json")
    ex = J(F42 + "/check/R2/check_R2_extra.json"); mo = J(F42 + "/check/R2/check_R2_more.json")
    ge = J(F42 + "/check/R2/check_R2_geom.json")
    sb = a3["A1"]["subbands"]
    Tc, Lc = 9.507500301523587, 135.46329754326246
    t_ob, x_ob = 159.30, 584.5
    on, tou = s3["onset"], s3["touchdown"]
    m = {"schema": "GreatWave.FLIPPlunging.metrics/1", "date": "2026-10-10",
         "note_ja": "判定の幅は凍結した計画 Unity/Build/FLIP42/plan/plan_ja.md §5（写しは flip42/plan/plan_ja.md）。結果は進行役が決めた幅に対してで、"
                    "指導教員の確認は受けていない。位置は造波板から（m）、時刻は計算の始めから（s）。Tc 9.51 s・Lc 135.5 m",
         "items": []}
    it = m["items"]
    def add(k, name, value, tol, verdict, src):
        it.append(dict(id=k, name_ja=name, value=value, tolerance_ja=tol, verdict_ja=verdict, source=src))
    add("A1", "帯の出口（造波板から 33.9 m）の 3 帯域の振幅の比・位相と測った S（R3）",
        dict(bands=[dict(components=b["components"], amp_ratio=round(b["amp_ratio"], 4), phase_rad=round(b["phase_rad"], 4)) for b in sb],
             S=round(a3["A1"]["S_measured"], 4)),
        "各帯域で振幅 ±5 %・位相 ±0.1 rad、S 0.334〜0.370", "外れた（成分 22〜32 の振幅 0.945）", "runs/R3/ana.json A1")
    add("A1_fix1", "A1 の 1 回目の直し（帯 2 Lc の R3b、0〜139 s）の成分 22〜32",
        dict(R3b=round(ex["A1_0_139s"]["R3b"][2]["amp"], 4), R3_same_window=round(ex["A1_0_139s"]["R3"][2]["amp"], 4)),
        "同じ", "直らなかった", "check/R2/check_R2_extra.json A1_0_139s")
    add("A2p", "伝わり：帯の出口 → kc(x−x_b)=−15（造波板から 268.8 m、間 235 m）の速さの誤差（+ が遅い）と振幅の変化",
        {r: dict(speed_err=round(ex["A2"][r]["speed_err"], 4), amp_change=round(ex["A2"][r]["amp_change"], 4)) for r in ("R1b", "R2", "R3")},
        "記録", "記録のみ", "check/R2/check_R2_extra.json A2（runs/*/ana.json A2p と同じ）")
    p = a3["A3p_model"]
    add("A3p", "集まり：測った速さと減りを入れた線形の焦点の模型（R3）",
        dict(dx_over_Lc=round(p["dx_focus_over_Lc"], 3), dt_over_Tc=round(p["dt_focus_over_Tc"], 3),
             crest_ratio=round(p["crest_ratio"], 3), H_ratio=round(p["H_ratio"], 3)),
        "場所 ±0.1 Lc・時刻 ±0.1 Tc・頂と H の比 0.95 以上", "外れた", "runs/R3/ana.json A3p_model")
    add("B1", "計算の減り：エネルギーの流れの帯の出口 → −10 の点（造波板から 376.6 m）の減り（成分の帯域の中）",
        dict(R1b=round(a1b["B1"]["loss_exit_to_m10"], 4), R2=round(a2["B1"]["loss_exit_to_m10"], 4), R3=round(a3["B1"]["loss_exit_to_m10"], 4)),
        "5 % 以内（R3 で判定）", "外れた（R3 7.1 %）", "runs/*/ana.json B1")
    b, nb = nn["N2"]["band"], nn["N2"]["noband"]
    add("N1N2", "粒子の帯（粒子 0.5 m、帯 4 m の R1 と帯なしの R1b）",
        dict(N1_diff_m=[round(g["diff"], 3) for g in nn["N1"]], N1_tol_m=[round(g["tol"], 3) for g in nn["N1"]], N1_ok=nn["N1_ok"],
             N2_rel_diff=dict(H=round((b["H"] - nb["H"]) / nb["H"], 4), eta_c=round((b["eta_c"] - nb["eta_c"]) / nb["eta_c"], 4),
                              steep=round((b["steep"] - nb["steep"]) / nb["steep"], 4)), N2_ok=nn["N2_ok"], decision_ja=nn.get("decision_ja")),
        "N1 その点の線形の波高の 5 %、N2 H・η_c ±5 %・険しさ ±10 %",
        "N2 が外れた → 決まりどおり R3 から先は帯なし", "R1/N1N2.json")
    def cpack(c):
        return dict(C1_dt_s=round(c["C1"]["dt"], 3), C1_dx_m=round(c["C1"]["dx"], 2), C2_H=round(c["C2"]["H"][2], 4), C2_eta_c=round(c["C2"]["eta_c"][2], 4),
                    C3=round(c["C3"]["steep"][2], 4), C4_time=round(c["C4"]["jet_time"][2], 4), C4_dist=round(c["C4"]["jet_dist"][2], 4))
    tol_c = "C1 ±0.1 Tc（0.95 s）・±0.1 Lc（13.5 m）、C2 ±5 %、C3・C4 ±10 %（比の基準は細かい方・刻みの小さい方）"
    add("C_time", "時間の刻み：R3 と R5'（138.2 s から CFL 半分・最小小刻み 2）", cpack(c5), tol_c,
        "入った（唇・2 つ目の噴流・空気は C1〜C4 に入っておらず、落ち着かない）", "R2/C_R3_vs_R5p.json")
    add("C_res_R3_R4", "細かさ：R3 と R4（粒子 0.177 m）", None, tol_c, "判定できない（R4 が走らなかった）", "Unity/Build/FLIP42/runs/R4/chain.log")
    add("C_res_R2_R3", "細かさ（条件つき）：R2（粒子 0.35 m）と R3", cpack(c2), tol_c, "C1・C2 は入り、C3・C4 は外れた", "R2/C_R2_vs_R3.json")
    add("C_precond", "記録：R3 と R3m（圧力の前処理だけ多重格子）", cpack(cm), tol_c, "記録のみ（C1〜C4 は 2 % 以内）", "R2/C_R3_vs_R3m.json")
    add("D1", "崩れ方", "前の面が鉛直を越え、唇が前の面に付いて空気を囲んだ（R2・R3・R5'・R3m のどれでも）",
        "前へ巻く（噴流の先が前の水面へ落ち、空気を囲む）", "入った", "runs/*/shape.json、check/R2/check_ja.md §2・§3")
    add("D2", "巻き始めの場所（前の面が初めて鉛直になった点）", dict(x=round(ge["R3"]["events"]["onset"]["vertical_x"], 1), t=round(on["t"], 3)),
        "484〜592 m（R&M の観測 kc(x−x_b)=−5〜0）", "入った", "check/R2/check_R2_geom.json R3.events.onset")
    ta = ge["R3"]["events"]["touch_air"]
    add("D3", "着水の時刻と場所（R3。記録の決まりでは唇の先が前の面に付いて空気を囲んだ時）",
        dict(t=round(ta["t"], 3), x=round(ta["x"], 1), dt_s=round(ta["t"] - t_ob, 2), dt_over_Tc=round((ta["t"] - t_ob) / Tc, 3),
             dx_m=round(ta["x"] - x_ob, 1), dx_over_Lc=round((ta["x"] - x_ob) / Lc, 3),
             air_m2=round(ta["area"], 2), air_height_above_still_m=[round(ta["y_bot"], 2), round(ta["y_top"], 2)],
             alt_second_jet=dict(t=157.1, x=548.9, dt_s=-2.2, dx_m=-35.6)),
        "D&K の表 3.1（計算の条件の表）の 159.3 s・584.5 m から ±0.25 Tc（2.4 s）・±0.25 Lc（34 m）",
        "外れた。比べた出来事も同じではない（噴流の先は静かな水面の高さに届いていない）", "check/R2/check_R2_geom.json R3.events.touch_air、check/R2/check_ja.md 見つけた所 2")
    rr = ex["rear"]["R3"]
    lp = ex["lip"]
    add("V_height", "見た目：巻き始めの高さ（R3）",
        dict(eta_c=round(on["eta_c"], 2), H_front=round(on["H"], 2), front_trough=round(rr["front_trough"], 2), front_trough_dist=rr["front_dist"],
             H_rear=round(rr["H_rear"], 2), rear_trough=round(rr["rear_trough"], 2), rear_trough_dist=rr["dist_behind"],
             H_rear_R2=round(ex["rear"]["R2"]["H_rear"], 2), max_H_section_whole_run=round(mo["R3"]["max_H_section"]["H"], 2)),
        "記録", "記録のみ", "runs/R3/shape.json onset、check/R2/check_R2_extra.json rear、check_R2_more.json")
    oo = ge["R3"]["events"]["onset"]
    add("V_front", "見た目：60° より立った前の面の高さ（巻き始め、R3）",
        dict(record=round(on["steep_h60"], 2), check_forward_only=round(oo["h60_forward_only"], 2), check_all=round(oo["h60_all"], 2)),
        "記録", "記録のみ", "runs/R3/shape.json onset、check/R2/check_R2_geom.json")
    add("V_lip", "見た目：唇と 2 つ目の噴流（届く距離・厚み、m）",
        {r: dict(before_first_contact=[round(lp[r]["windows"]["154.5-156.0"]["reach"], 2), round(lp[r]["windows"]["154.5-156.0"]["thick"], 2)],
                 second_jet_157_158=[round(lp[r]["windows"]["157.0-158.3"]["reach"], 2), round(lp[r]["windows"]["157.0-158.3"]["thick"], 2)])
         for r in ("R3", "R5p", "R3m", "R2")},
        "記録", "記録のみ（2 つ目の噴流は計算ごとに変わり、再現しない。R2 では 2 つ目の噴流は出ない）", "check/R2/check_R2_extra.json lip")
    add("V_air", "見た目：囲んだ空気（m²）",
        {r: dict(first_ge4=(None if lp[r]["first_air_ge4"] is None else dict(t=round(lp[r]["first_air_ge4"]["t"], 3), area=round(lp[r]["first_air_ge4"]["area"], 2))),
                 largest_to_158_3=round(lp[r]["largest_air"]["area"], 2)) for r in ("R3", "R5p", "R3m", "R2")},
        "記録", "記録のみ（計算ごとに変わる）", "check/R2/check_R2_extra.json lip")
    add("R4", "粒子 0.177 m", "12 コマで水面が 1.06 m 下がり、水面の見張りで止まった（自由落下）。数コマの試しでは、粒子 0.21・0.20・0.18・0.177 m は、"
        "試した水槽（x の格子 2,606〜3,403 個）・上の空気の高さ・格子と海底の合わせ方・前処理によらず落ちた",
        "—", "走らなかった。細かさの比べ（R3 と R4）は判定できない。原因は別の作業で調べている（まとめは 10/12 の見込み）。その途中の記録（10/10 17:55、"
        "Unity/Build/FLIP42/R4fix/record_ja.md）は格子の大きさの丸めによる場のずれと読んでいるが、独立の確かめはまだで、この報告では使っていない",
        "Unity/Build/FLIP42/record_ja.md の R4 の試し（写しは flip42/record_ja.md）、runs/R4/chain.log")
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    copies = []
    for name, src, note in FIGS:
        s = F42 + "/" + src; d = OUT + "/" + name
        if name.endswith(".mp4") and os.path.getsize(s) > MAX_VIDEO:
            raise SystemExit("video over 20 MB: " + src)
        shutil.copyfile(s, d)
        copies.append(dict(name=rel(d), src=rel(s), bytes=os.path.getsize(d), sha256=sha(d), same_as_src=sha(d) == sha(s), note_ja=note))
    for src, note in MIRROR:
        s = F42 + "/" + src; d = OUT + "/flip42/" + src
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if src in SNAPSHOT_KEEP and os.path.exists(d):
            copies.append(dict(name=rel(d), src=rel(s), bytes=os.path.getsize(d), sha256=sha(d), same_as_src=sha(d) == sha(s), note_ja=note,
                               snapshot_ja=SNAPSHOT_KEEP[src], src_now=fileinfo(s)))
            continue
        shutil.copyfile(s, d)
        copies.append(dict(name=rel(d), src=rel(s), bytes=os.path.getsize(d), sha256=sha(d), same_as_src=sha(d) == sha(s), note_ja=note))
    mp = OUT + "/metrics.json"
    json.dump(metrics(), open(mp, "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=1)

    # 計算（runs.jsonl）
    lines = open(F42 + "/runs/runs.jsonl", "rb").read().split(b"\n")
    head = b"\n".join(lines[:JSONL_ROWS]) + b"\n"
    rows = [json.loads(l) for l in lines[:JSONL_ROWS] if l.strip()]
    assert len(rows) == JSONL_ROWS and all(r["run_id"] in RUN_IDS for r in rows), "runs.jsonl の最初の行が報告の計算と合わない"
    runs = {}
    for r in rows:
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
        q["note_ja"] = RUN_NOTE.get(k, "")
    tot = dict(launches=sum(q["launches"] for q in runs.values()), hours=round(sum(q["hours"] for q in runs.values()), 2))
    runs["R3b"]["frames_done_by_log"] = 3360
    # runs.jsonl に行のない起動（時刻は chain.log と起動の記録のファイルから）
    unrec = [dict(run="R3b", start="2026-10-10 09:25:51", end="2026-10-10 09:47:26", hours=round((21 * 60 + 35) / 3600.0, 3),
                  frames=[3082, 3360], why_ja="進行役が手で止めた（A1 が直らなかった）。log_c3082.txt・hf_c3082.npz は残っている"),
             dict(run="R4", start="2026-10-10 15:14:52", end="2026-10-10 15:15:08", hours=round(16 / 3600.0, 3),
                  frames=[1, 1], why_ja="前処理が不完全コレスキーの起動。2 コマ目で水面の場が作られず、起動の記録を書く前に止まった（runs/R4/log_c0001_failed_IC.txt）")]
    tot_all = dict(launches=tot["launches"] + len(unrec), hours=round(tot["hours"] + sum(u["hours"] for u in unrec), 2),
                   note_ja="runs.jsonl の行の起動に、行のない起動（unrecorded_launches）を足した数。R4 の数コマの試し 11 通りは含まない")

    # 使った計算の記録（解析と動画の入力）
    cache = []
    for r in RUNS:
        for p in sorted(glob.glob(F42 + "/runs/" + r + "/hf_c*.npz") + glob.glob(F42 + "/runs/" + r + "/sec_c*.npz")
                        + [F42 + "/runs/" + r + "/" + n for n in ("ana.json", "shape.json", "cfg.json", "run.json", "chain.log")
                           if os.path.exists(F42 + "/runs/" + r + "/" + n)]):
            cache.append(fileinfo(p))
    cache.append(dict(path=rel(F42 + "/runs/runs.jsonl"), first_lines=JSONL_ROWS, bytes_first_lines=len(head),
                      sha256_first_lines=hashlib.sha256(head).hexdigest(),
                      note_ja="R4 の診断の計算が後ろに行を足していくので、報告に使った最初の 62 行の SHA-256 を残す"))
    ckpt = {}
    for r in RUNS:
        fs = [p for p in glob.glob(F42 + "/runs/" + r + "/ckpt/**", recursive=True) if os.path.isfile(p)]
        ckpt[r] = dict(files=len(fs), bytes=sum(os.path.getsize(p) for p in fs))
    r4dbg = [fileinfo(p) for p in sorted(glob.glob(F42 + "/tmp_houdini/r4dbg/*")) if os.path.isfile(p)]

    tools = {rel(p): sha(p) for p in sorted(glob.glob(TOOLS + "/*.py")) if not os.path.basename(p).startswith(EXCLUDE_PREFIX)}
    run = {
        "schema": "GreatWave.FLIPPlunging.deliver_run/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note_ja": "Docs/Evidence/FLIPPlunging を作った記録。この段で新しい流体の計算はしていない（動画と断面の並びは印の字だけを直して描き直した）。"
                   "git の操作とダウンロードはしていない。何も消していない。パスはリポジトリからの相対",
        "report": "Docs/Progress/FLIP_Plunging_ja.md",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/flip42/g_relabel_v2.py orig <一時置き場>   # 元の字で描き直し、利用者に出した物とバイト単位で同じかを確かめた",
            "py -3.10 -B Tools/GWWaveGen/flip42/g_relabel_v2.py v2 Unity/Build/FLIP42   # 印の字だけを直した _v2",
            "py -3.10 -B Tools/GWWaveGen/flip42/x_check_relabel.py Unity/Build/FLIP42   # 符号化の前のコマで、違いが字の所だけかを確かめた",
            "py -3.10 -B Tools/GWWaveGen/flip42/g_deliver_plunging.py   # この証拠",
        ],
        "upstream_commands_ja": {
            "計画": "py -3.10 Tools/GWWaveGen/flip42/p_plan_numbers.py → Unity/Build/FLIP42/plan/plan_numbers.json、plan_ja.md（走らせる前に書いて凍結した）",
            "場面": "hython Tools/GWWaveGen/flip42/g_build_tank.py → Houdini/FLIP42/g_tank.hiplc（計算ごとには変えない。CTRL の値だけを変える）",
            "計算": "py -3.10 g_cfg.py → py -3.10 g_chain.py（R1・R1b）／g_chain2.py（R3 から）。30 分以下の起動に区切り途中保存から続ける。起動は g_run.py",
            "解析": "py -3.10 g_analyze.py <計算> → runs/<計算>/ana.json、py -3.10 g_shape.py <計算>（R5'・R3m は --parent=R3）→ shape.json、g_shape.py --compare → R2/C_*.json、g_compare.py R1 R1b → R1/N1N2.json",
            "図と動画": "py -3.10 g_figs.py・g_figs2.py → R1/figs・R2/figs、py -3.10 g_video.py・g_preview.py → R1/video・R2/video・preview",
            "独立の確かめ": "py -3.10 check/R1/check_R1.py、check/R2/check_R2_geom.py → check_R2_more.py → check_R2_spec.py → check_R2_extra.py（解析の道具を使わない）",
        },
        "versions": {
            "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__, "pillow": PIL.__version__,
            "houdini": "Houdini 22.0.466 hython（画面なし。runs.jsonl の全行で 22.0.466。方法の確かめ FLIP41 は 22.0.459）",
            "ffmpeg": "ffmpeg 2024-12-19-git-494c961379-full_build（libx264、crf 20、yuv420p）",
            "font": "Yu Gothic（YuGothM.ttc・YuGothB.ttc）",
        },
        "scene": dict(fileinfo(SCENE), runs_with_this_sha=[k for k, q in runs.items() if sha(SCENE) in q["hip_sha256"]],
                      note_ja="道具の試し smoke_dp0.5 の 5 回の起動だけ前の版（小刻みの数え方を直す前）。キャッシュは含まない"),
        "tools": tools,
        "tools_excluded_ja": "Tools/GWWaveGen/flip42/x_r4fix_*.py：R4 の原因の診断（別に走っている）の途中の道具。この報告にも証拠にも使っていない。診断の結果と一緒に扱う",
        "tools_changed_after_runs_ja": "g_cfg.py（10/10 15:16）と g_run.py（10/10 15:19）は、R1・R1b・R3・R3b・R5'・R2 を走らせた後に R4 のために足した"
                                       "（解き方の設定を cfg から渡して FLIP Solver に入れる所と、水面の場が作られない時に記録を残して止まる所）。"
                                       "R3m と R4 はこの版で走った。前の版のファイルは残していない。各計算で実際に使った解き方の設定は、起動ごとに Houdini から読み戻して "
                                       "runs.jsonl の solver_parms に残してある",
        "runs": runs,
        "runs_total": tot,
        "runs_total_with_unrecorded": tot_all,
        "unrecorded_launches": unrec,
        "runs_not_in_jsonl_ja": [
            "R3b の 11 回目の起動（2026-10-10 09:25:51〜09:47:26、3082 → 3360 コマ）：進行役が手で止めた（runs/R3b/chain.log の最後の行、0.36 h）",
            "R4 の最初の起動（2026-10-10 15:15、前処理は不完全コレスキー）：2 コマ目に止まり、起動の記録が残らなかった（runs/R4/chain.log「no run record for chunk 1 (crash?)」、0.005 h）",
            "R4 の数コマの試し 11 通り（15:16〜16:42。tools x_try_r4.py・x_debug_r4.py。出力は tmp_houdini/r4dbg/、下の r4dbg_outputs）",
        ],
        "relabel": {
            "why_ja": "独立の確かめ（check/R2/check_ja.md の見つけた所 2）：D&K の t_ob・x_ob は表 3.1「Input parameters for the simulated cases」の値で、"
                      "測った値とは書かれていない。R3 の最初の「着水」は唇の先が前の面（静かな水面から 5〜7 m）に付いた時で、噴流の先は静かな水面に届いていない",
            "changed_strings": {
                "preview/R2_first_side.mp4 → _v2": {"場所の印": ["実験の着水 584.5 m（D&K）", "D&K の表の着水の値 584.5 m（計算の条件の表）"],
                                                     "時間の帯": ["実験の着水", "D&K の表の着水の値（計算の条件の表）"],
                                                     "時間の帯（R3）": ["着水", "唇が前の面に付いた時（記録の着水）"]},
                "R2/R2_side_finest.mp4 → _v2": {"場所の印": ["D&K の着水 584.5 m", "D&K の表の着水の値 584.5 m（計算の条件の表）"],
                                                 "時間の帯": ["D&K の着水の時刻", "D&K の表の着水の値（計算の条件の表）"],
                                                 "時間の帯（R3）": ["着水", "唇が前の面に付いた時（記録の着水）"]},
                "preview/R2_first_strip.png → _v2": {"8 枚目の題": ["着水", "唇が前の面に付いた時・記録の「着水」"],
                                                      "note_ja": "この図には D&K の印はない"},
            },
            "unchanged_ja": "描き方・窓・時刻・コマ・数・符号化の設定は同じ（g_preview.py・g_video.py の字の辞書 LAB だけを差し替えた）",
            "reproduction_ja": "元の字のまま描き直した 4 つ（下の reproduced_byte_identical）は、利用者に出した物と SHA-256 が同じだった（2026-10-10 17:38）。"
                               "道具と記録は、出した時と同じ物を描く",
            "reproduced_byte_identical": [fileinfo(F42 + "/" + p) for p in REPRO_ORIG],
            "v2_files": [fileinfo(F42 + "/" + p) for p in ("preview/R2_first_side_v2.mp4", "preview/R2_first_strip_v2.png",
                                                          "R2/R2_side_finest_v2.mp4", "R2/video_v2/R3_crest.mp4", "R2/video_v2/R3_crest_half.mp4")],
            "pixel_check": "flip42/preview/relabel_check.json",
        },
        "copies": copies,
        "cache_used": cache,
        "cache_used_note_ja": "解析・図・動画・独立の確かめが読んだ計算の記録（一番上の水面の高さ hf_c*.npz、板の真ん中の断面の水面の場 sec_c*.npz、解析の JSON、設定と起動の記録）。"
                              "どれも Unity/Build/FLIP42/runs/ の下（リポジトリの外）",
        "checkpoints_not_hashed": ckpt,
        "checkpoints_note_ja": "途中保存は計算を続けるためだけに使い、解析と動画には使っていないので SHA-256 は取らない。消していない",
        "r4dbg_outputs": r4dbg,
        "metrics": dict(fileinfo(mp)),
        "guide": dict(fileinfo(OUT + "/" + GUIDE), note_ja="写しの案内（手で書いた。写しの時点と、写しに残る退けた言い方）"),
        "revisions_ja": ["2026-10-10 17:47 最初の版",
                         "2026-10-10 18 時台：報告の見直しを受けて、R3b・R4 の行のない起動、g_cfg.py・g_run.py の変更、record_ja.md の写しの時点、"
                         "runs.jsonl の扱い、R4 の書き方を直した。動画・図・写しの中身は変えていない"],
    }
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=1)
    print("copies", len(copies), "cache", len(cache), "runs", tot)


if __name__ == "__main__":
    main()
