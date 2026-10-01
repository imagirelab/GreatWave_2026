# -*- coding: utf-8 -*-
"""仕上げ30：Docs/Evidence/Polish/30/metrics.json（計画 §5.3 の各行・閉じる目安・バックログ項目 → 値 → 判定）を書く。
数は metrics_measured.json（pl30_record.py が既にある出力から集めたもの）から読む。判定の言葉はこの道具に書いた（修正の回 1 の後の作る側の判定。進行役の自己評審の前）。
修正01：自己評審の must-fix 12 件ごとの行（fix01_must_fix）を足し、各行の値を修正01 の採用（fix01/r10・sea）に替えた（作る部の値は build_round）。
修正02：自己評審の修正の回 2 の must-fix 7 件ごとの行（fix02_must_fix）を足し、各行の値を修正02 の採用（fix02/r_final・sea）に替えた。
       fix01_must_fix は修正01 の時点の記録（その後の値は fix02_must_fix と各行）。fix01_must_fix の 5 の「全節点 0.86」は 5 節点おき＋t* の値で、全 251 節点の読みは fix02_must_fix の 7。
記録の部（修正02 の後）：must-fix の前後の図を縦横の比を保って作り直し（pl30_sheets.tile_fit）、全解像度の画像で 7 視点＋回り台を見直した読みを record_stage_review に書き、
       Q18 ③（右の高い波）の判定を「一部」に改めた（回り台 60〜120° の房が四角い歯、方位 90° の縦の帯と白い縦の棒、後ろ 65° の縦縞の斑）。数は変えていない。

使い方：py -3.10 -B Tools/GWWaveGen/pl30/pl30_metrics.py
"""
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
E = os.path.join(REPO, "Docs", "Evidence", "Polish", "30")


def main():
    M = json.load(open(os.path.join(E, "metrics_measured.json"), encoding="utf-8"))
    G = json.load(open(os.path.join(E, "gpu_sea_fix02_runs.json"), encoding="utf-8"))
    G1 = json.load(open(os.path.join(E, "gpu_sea_fix01_runs.json"), encoding="utf-8"))
    F2 = M["fix02"]; W2 = json.load(open(os.path.join(E, "pl30_fix02_white_px.json"), encoding="utf-8"))["boxes"]
    sa = F2["fix02_checks"]["after"]["seam_all"]; sa1 = F2["fix02_checks"]["fix01"]["seam_all"]
    wg = F2["fix02_checks"]["after"]["white"]["frames"]; fj = F2["fuji_all_frames"]
    seam = M["seam"]["after"]; bp = M["boat_patch"]["after"]; ka = M["band_kink"]["after"]; kb = M["band_kink"]["before"]
    fu = M["fuji"]; lines = M["f7_2_lines_seat_270_300"]; st = M["s5_3_stair_seat_f280"]; sid = M["sea_id_fractions"]; hv = M["heave"]
    vj = M["s5_1_pop"]["video_jumps"]
    F = M["fix01"]; fa = F["checks_after"]["fix01_checks"]; fr = F["checks_build_round"]["fix01_checks"]; frp = F["checks_build_round"]["pl30_checks"]
    tr = F["trough_share"]["views"]
    gpu = {c: dict(before_median_ms=round(v["before_median"], 3), after_median_ms=round(v["after_median"], 3), before_ms=v["before_ms"], after_ms=v["after_ms"],
                   fix01_after_median_ms=v.get("fix01_after_median")) for c, v in G["runs"].items()}
    gpu1 = {c: dict(before_median_ms=round(v["before_median"], 3), after_median_ms=round(v["after_median"], 3)) for c, v in G1["runs"].items()}

    def wbox(prefix):
        return [dict(item=b["item"], fix01=b.get("fix01"), fix02=b.get("fix02")) for b in W2 if b["item"].startswith(prefix)]
    ev_a = M["evaluator23"]["after"]; ev_r7 = M["evaluator23"]["build_round_after_r7"]; ev_p = M["evaluator23"]["previous_group"]

    def item(ev, c, k, tgt):
        for x in ev[c]["items"].get(k, []):
            if x[0] == tgt:
                return x
        return None

    def attr_jump(d):
        out = {}
        for s in ("near", "far"):
            a = d["attr"][s]
            ku = "ridge_or_small_u_col" if "ridge_or_small_u_col" in a else "ridge_u_col"
            kq = "ridge_or_small_q_col" if "ridge_or_small_q_col" in a else "ridge_q_col"
            out[s] = dict(u_col_pairs_over100m=a[ku]["n_over_all"], q_col_max_visible_m=a[kq]["max_visible"], sea_along_col_max_m=a["sea_along"]["col_max"])
        return out

    must_fix = [
        dict(item="1 面の座標の継ぎ目（u の +1000 m、q の最大 285 m の跳び。左の側面・右の側面・真上の点線、回り台の段の帯・藍の四角・白の縦の切れ）",
             value=dict(build_round=attr_jump(fr), after=attr_jump(fa),
                        note_ja="作る部：近い稜を頂点ごとに選び、肩の稜の弧長に +1000 m。修正01：稜の系は右の高い波の a − a_crest(c) の連続な場と、両端を直線で延ばした肩の稜への距離を、t* の高さの差 ±3 m で混ぜる。"
                                "頂点の間の値の勾配（|Δ値|／|Δ位置|）の最大：q 158 → 11 m/m、u 4,246 → 9.6、頂の高さ 52.7 → 7.9（作る部 → 修正01、近い海の列と行）。小波は楕円の座標（角度は断片の中）。海の溝は輪を一周して閉じる沿う座標 along。"),
             verdict="満たす（図 fig_pl30_fix01_a の 1・2・3 列。点線・段の帯・藍の四角・白の縦の切れは見えない）"),
        dict(item="2 Q16 谷（［利用者の言葉］）：座席から波の方向・座席の低い視点の t* で谷の縁を読めるように。t 9 s の淡い水色の斑",
             value=dict(trough_share_tstar=tr, method_ja="生成器に谷の縁のうねり pl30_trough_rim（主役波の t* の谷の深さに応じ、継ぎ目に垂直に 2.6 m の所を頂とする高さ 0.75 m のうねり）を足し、"
                        "材質で頂の内（継ぎ目〜頂）と頂の外の唇の帯 0.9 m を藍中の地に藍濃の溝、頂に藍の線と泡の点。段は τ −0.8 → −0.05 s に頂から谷の底へ広がる。今の深さの段（斑の元）はやめた。"),
             verdict="一部（座席から波の方向の t* で段は画面の 10.0%（海の画素の 77%）。t 9 s の斑はない。座席の低い視点の t* では、近い海が座席の船の船体の陰で見えない（見える海は左奥の船のうねりだけ）ので段も見えない）"),
        dict(item="3 右の高い波：座席から波の方向 t 10.5 s の平らな藍の壁と空に近いクリーム色の三角",
             value="壁は座席の船の支えの当て布（船の竜骨の線に沿う 33° の面）を目の近くで見たもの。当て布の中も右の高い波の溝（稜に平行）を描き、溝の周期が画面で大きい所に 2 段の細い溝（主の 1/3・1/9、海は 1/4・1/16）を足した。背の白は閾値 0.94（頂だけ）",
             verdict="満たす（図 fig_pl30_fix01_a の 4 列。クリーム色の三角はない）"),
        dict(item="4 右の高い波と肩の稜の白（Q18 ③［利用者の言葉］）：櫛・ジッパーの歯、雪山と氷柱",
             value="白の閾値 前 0.70 → 0.80・背 0.80 → 0.94。房は 2 層（周期 3.1 m・4.9 m、置く割合 80%・55%）、長さの揺れ・まとまり（波長 23 m）・長い房 18% を 1.6 倍、指は先の尖った錐で伸びるほど 3.0 m 横へ曲がり、先を 2〜4 本の小さな爪に割る。縁の小さな舌は周期 0.93 m で 60% だけ。白の縁の低い揺れ ±0.035。",
             verdict="一部（櫛の歯の揃いは消え、回り台 90° の段の帯・藍の四角も消えた。目の前の右の高い波は、近い回り台の視点では白い頂がまだ画面の上を大きく占める）"),
        dict(item="5 船の支え（目標 竜骨の外で稜・溝 ≤ 0.1 m、法線の内積 ≥ 0.9）",
             value=dict(builder_metric=dict(ridge_m=bp["max_ridge_outside_keel_m"], groove_m=bp["max_groove_outside_keel_m"],
                                            build_round=dict(ridge_m=frp["boat_patch"]["max_ridge_outside_keel_m"], groove_m=frp["boat_patch"]["max_groove_outside_keel_m"])),
                        keel_cross_profiles=dict(after={k: fa["boat"][k] for k in ("max_drop_1m_outside_m", "max_groove_m", "max_ridge_m")},
                                                 build_round={k: fr["boat"][k] for k in ("max_drop_1m_outside_m", "max_groove_m", "max_ridge_m")}),
                        normal_dot=dict(tstar_min=seam["normal_dot_tstar_min_excl_cone"], all_knots_min=seam["normal_dot_min_excl_cone"], below09_tstar=seam["normal_dot_below09_tstar"],
                                        build_round=dict(tstar_min=frp["seam"]["normal_dot_tstar_min_excl_cone"], all_knots_min=frp["seam"]["normal_dot_min_excl_cone"],
                                                         below09_tstar=frp["seam"]["normal_dot_below09_tstar"])),
                        keel_water_minus_keel_m=bp["keel_water_minus_keel_m"]),
             verdict="満たさない（改善：稜 0.17 → 0.11 m、溝 −0.54 → −0.33 m、法線の最小 0.82 → 0.88（全節点 0.82 → 0.86、0.9 未満 18 → 3 頂点）。竜骨の断面の 1 m の落差 1.7 m は船首の外の側で残る。"
                     "竜骨は大波の前の足（y 0）から 1〜3.5 m、船尾 −1.4 m・船首 5.2 m で、足の側の立ち上がりと溝は船の置き方（仕上げ41）か主役波の前の足（仕上げ28）を変えないと直らない）"),
        dict(item="6 帯の傾き ≤ 45°",
             value=dict(triangles=dict(after_tstar=fa["tilt"]["tstar"], build_round_tstar=fr["tilt"]["tstar"], after_band_only_all_knots=fa["tilt"]["band_only"],
                                       build_round_band_only_all_knots=fr["tilt"]["band_only"]),
                        quads=dict(after={k: v for k, v in fa["tilt"]["quad"].items() if k != "per_knot_max"}, build_round={k: v for k, v in fr["tilt"]["quad"].items() if k != "per_knot_max"}),
                        column_reading=dict(after_max=ka["max_slope_deg"], after_at=ka["max_slope_at"], build_round=frp["kink"]["max_slope_deg"])),
             verdict="一部（帯の式だけの所（地形の誘導 < 0.3 m・船の支えの外）の t* の三角形：最大 52.7° → 40.2°、45° を超える数 7 → 0。四角の読み：t* の 45° を超える四角 456 → 75（全部が錐の点の扇の行 0〜5）、"
                     "形成の途中の最大 86.7° → 73.9°（τ −11 s の右の錐の点の隣の後ろの列。作る部も同じ所 75°）。地形の誘導の面（右の高い波・小波の面、船の支えの当て布）は 45° を超える）"),
        dict(item="7 Q16 谷の縁（［利用者の言葉］）：藍中 1.9% は溝の色で満たしていた", value="2 と同じ（段の画素を材質の印 _PL29Diag = 7 で数え、溝の色と分けた）", verdict="2 と同じ"),
        dict(item="8 Q16 稜の連続（［利用者の言葉］）：右の側面・真上で大波の右の端と肩の稜の間が空き、低い鞍だけでつながる",
             value="肩の稜の頂の白い泡の線（_CrestFoam：頂の t* の高さ 1.2〜4.5 m の肩の稜で、今の高さの比 0.86 より上を白）で、低い鞍でも白を大波の右の端の近くから右の高い波の頂まで続けた。"
                   "肩の稜の上り口の頂の高さは谷の続きを含めた値にした（含めないと白が切れた）。前と背の閾値の混ぜは二つの稜のそれぞれの前の側の量の大きい方（合流で白が切れない）。線分が稜の系を 2 度横切る所にも行を集めた（近い海 64 行）",
             verdict="一部（右の側面・真上で白い稜は大波の右の端の近くから右の高い波の頂まで一続き。ただし形は大波の右の端の錐の点（海面の高さ）から上る鞍のまま。上り口を高くする案は原画視点 t 9.5〜9.75 s に富士の雪の 13% を隠したので切った）"),
        dict(item="9 回り台 90° の t* の段の帯（モアレ）と藍の四角", value="1 と同じ（面の座標の跳び）", verdict="満たす"),
        dict(item="10 作る部が限界とした傷：座席から波の方向 t 10.5 s のクリーム色の三角と平らな暗い面、t 9 s の谷の斑、左の側面の細い白い角",
             value="三角：背の閾値 0.94。暗い面：3 と同じ。斑：2 と同じ（今の深さの段をやめた）。白い角：閾値 0.80 と縁の揺れで、左の側面 t* の右の高い波は頂の白の塊になった",
             verdict="満たす（図 fig_pl30_fix01_a・b）"),
        dict(item="11 原画視点 t* の手前の船（boat_fg）の船底を海が隠す（評価器 213 boat_ochre 0.13 → 16.99）",
             value=dict(cause_ja="肩の稜と右の高い波の滑らかな max の足し分 (k − |x − y|)²/4k が、両方が 0 の所でも 0.25 m を足し、格子の全部で海が 0.25 m 上がっていた",
                        boat_fg_sea_height_m=fa["fg"], boat_fg_sea_height_build_round_m=fr["fg"],
                        e213_boat_ochre=dict(after=item(ev_a, "noline", "213", "boat_ochre"), build_round=item(ev_r7, "noline", "213", "boat_ochre"), polish29=item(ev_p, "noline", "213", "boat_ochre")),
                        e75_boat_fg=dict(after=item(ev_a, "noline", "75", "boat_fg"), build_round=item(ev_r7, "noline", "75", "boat_fg"), polish29=item(ev_p, "noline", "75", "boat_fg"))),
             verdict="満たす（足し分を両方が低い所で 0 へ。213 boat_ochre 16.99 → 0.133（仕上げ29 と同じ）を 4 組とも。手前の船の所の海は 0.25 → 0.00 m）"),
        dict(item="12 記録の数：右の高い波の立ち上がりの速さ、+0.5 ms の GPU",
             value=dict(rise=fa["rise"], gpu=gpu1, gpu_note_ja=G1["build_round_claim_ja"]),
             verdict="直した（立ち上がりは t 10〜11.5 s の平均 6.1 m/s・最大 8.8 m/s（t 10.33 s）。作る部の記録の「約 5 m/s」は誤り。GPU は前後 3 回ずつの中央値で書いた）"),
    ]
    must_fix2 = [
        dict(item="1 ［Q18 ③・Q28］形成の途中の偽の白（平らな白い刃と筋）：原画視点 t 6 s（x 250〜420・y 735〜775）・t 9 s（x 700〜940・y 815〜835）、回り台 t 6 s の方位 0〜90°",
             value=dict(cause_ja="材質の白の判定 hrel = y/max(hR, 0.5) が、t* で頂でない頂点（主役波の形成で帯が持ち上がった所。修正01 の海の near 列 681〜710・行 19〜39 など）でも発火した。"
                                 "t* の高さの比 hf ≥ 0.7 の門だけでは、t 6 s に hf ≥ 0.7 の頂点の白も残る（稜の系はまだ g_r = 0.12 しか育っていない）",
                        method_ja="今の高さの比を「その系の今の育ち g(τ) × t* の高さの比 hf ＋ 0.1」で上から抑える（g は生成器の growth_right_knots・growth_knots を τ の表 _GrowR・_GrowS に入れて材質が読む）。"
                                  "t* では g = 1 で「hf ≥ 閾値 − 房 − 0.1」の t* の頂の門になる。頂の泡の線も同じ比を使う",
                        numpy_white_vertices=wg, unity_white_px=wbox("1 ")),
             verdict="満たす（原画視点 t 6 s の白い刃 928 → 0 画素、t 9 s の白い筋 104 → 0 画素。回り台 t 6 s の方位 0〜90° に平らな刃はない（残る白は手前の小波の頂と主役波の頂）。numpy の写しで t 6〜9 s の稜の系の白の頂点 980〜99 → 0）"),
        dict(item="2 ［Q18 ②］手前の小波の頂の三日月（原画視点 t* x 700〜760・y 625〜690、真上の白の中の輪）と、回り台 t 6 s の触手",
             value=dict(method_ja="楕円の座標の極（頂）から 1.2〜2.0 m の内は白の中の淡い水色（房の陰・流れの線・泡の粒・陰の帯）を描かない。"
                                  "房の長さを今の小波の白い頂の高さ（(g − 0.62)/(1 − 0.62)、g は小波の今の育ち）に比例させる（t 6 s は g = 0.78 で 0.42 倍、t* で 1 倍）",
                        unity_white_px_tt_t6=wbox("1 回り台")),
             verdict="満たす（原画視点 t* の頂の三日月と真上の輪は消えた。回り台 t 6 s の小波は小さな白い頂と短い房で、長い触手はない）"),
        dict(item="3 ［Q18 ③］近い視点の右の高い波の白（回り台の方位 60〜120° の t* と t 10.5 s の、氷柱の垂れた大きなクリーム色のドーム）",
             value=dict(method_ja="背の側の白の幅を高さの比 0.94 だけで決めず、稜からの距離 q で上限：背の側は稜から 0.5 m、前の側は 0.8 m を越えると閾値を 1 m あたり 0.6 上げる"
                                  "（硬い q の切りは q の 0 が本当の頂とずれる所で房の先だけが離れて残ったので、閾値の坂にした）。前の側の外では房をその分だけ伸ばし、房は前の側からだけ垂らす（背の房 0.22 倍 → 0）。"
                                  "肩の稜の重みのある所は坂を掛けず、細い線にする（合流で白が切れないように）",
                        unity_white_px=wbox("3 "), fuji_snow="原画視点の富士の雪は t 5〜12 s の 211 コマの全部で 2,260 画素（材質だけの変更で、右の高い波の形は同じ）"),
             verdict="満たす（指摘のドームはなくなった。回り台 t* の下半分の白：方位 60° 212,265 → 約 8.6 万、90° 360,805 → 約 13 万、120° 278,079 → 約 15 万画素。白い頂は稜に沿う帯になり、房は前の側から垂れる。"
                     "記録の部の読み（全解像度の画像と、縦横の比を保って作り直した図 fig_pl30_fix02_b）：房は先の平らな四角い歯（城壁のような凹凸）に見え、爪の指としては読めない。"
                     "方位 90° に、肩の稜が右の高い波の手前の面を下りる所の白い縦の棒（幅約 60 画素）と、溝が縦に変わる帯がある。修正02 の記録の「短く丸い指」「細い白い筋」は、横に最大 3.7 倍縮んだ前の図での読みだった。"
                     "このため［利用者の言葉］Q18 ③ の判定は一部（record_stage_review）。後の群へ）"),
        dict(item="4 ［Q28・原画視点］t* の水平線の白い楔（x 1005〜1350・y 765〜830）",
             value=dict(cause_ja="修正01 の肩の稜の頂の泡の線（_CrestFoam）と、肩の稜の普通の白（頂の t* の高さ 2〜3.5 m）が、原画視点の 73〜78 m 先で幅 3〜4 m の帯になった",
                        method_ja="肩の稜の白と頂の泡の線を、|q| < 0.35 m（と頂のすぐ近く）の細い線にし、線の幅が画面で 1.2 画素より細い所（遠く見える所）は低い鞍（頂 < 4.5 m）だけ切る",
                        unity_white_px=wbox("4 ")),
             verdict="満たす（楔の所の白 3,798 → 46 画素（残りは泡の点）。右の側面と真上で白い稜は大波の右の端の近くから右の高い波の頂まで一続き、真上の Y の合流もつながる）"),
        dict(item="5 ［Q16 稜の連続］低い鞍を高くする案（上り口 0・1.6 → 2.2・2.8 m）に pl30_right_lag と同じ形の育ちの遅れを付けて、もう一度だけ試す",
             value=dict(method_ja="足し分（高くした上り口と元の肩の稜の差）だけを別の育ちの遅れ pl30_shoulder_lag（τ −0.75 s まで 0、−0.5 s で 0.35、−0.25 s で 0.8、t* で 1 の PCHIP × g(τ)）で足す",
                        fuji_all_frames=dict(frames=fj.get("fix02_frames"), min_snow=fj.get("fix02_min_snow"), frames_not_2260=fj.get("fix02_frames_not_2260"),
                                             fix01_min_snow=min((r["snow"] for r in fj.get("fix01", [])), default=None)),
                        growth_shoulder_knots_tail=(F2["generate"].get("growth_shoulder_knots") or [])[-12:]),
             verdict="採った（原画視点 t 5〜12 s の 1/30 s おきの 211 コマの全部で富士の雪が 2,260 画素。numpy の見当でも雪の見える割合はどのコマも 1.0）"),
        dict(item="6 ［Q16 谷の縁］真上で谷の縁の段の帯の左の端が真っ直ぐに切れる（x ≈ 718、y 620〜665）",
             value=dict(cause_ja="材質が谷の縁の重み tw を 0.5 で切っていた（帯の幅は一定）", method_ja="帯の幅（頂の内と唇の帯）を tw 0.15〜0.85 で 0 から全部へ細らせる",
                        trough_share=F2["trough_share"]),
             verdict="満たす（真上の帯の左の端は細って終わる。座席から波の方向の t* の段は画面の 10.0% のまま。座席の低い視点は仕上げ36 の限界のまま）"),
        dict(item="7 記録を直す（手前の尾の刃・S5-3 の稜線の段 0・継ぎ目の法線の全 251 節点の値）",
             value=dict(tail_blade_ja="群の指示の「手前の尾の刃」は、左の側面 t* の主役波の印の画像で主役波の中にある（右下へ伸びる主役波の尾）。主役波の形（仕上げ28 の採用）なので範囲の外（図 fig_pl30_fix02_tail.png）",
                        s5_3_ja="稜線の段 0 は、座席 v1 のコマ 280 の測る所（x 1787〜1912・y 435〜604）の空でない画素が 0 という読み（前は 10,004 画素・段 19）。右の高い波が育ちの遅れで座席の視点のその所に入らなくなったためで、"
                                "稜線そのものは原画視点・右の側面で目で見て確かめた（階段なし）",
                        seam_normals_all_knots=dict(fix01_sea=dict(vertex=dict(min=sa1["vertex"]["min"], at_tau=sa1["vertex"]["at_tau"], every5=sa1["vertex"]["min_every5"]),
                                                                   face_this_reading=dict(min=sa1["face"]["min"], at_tau=sa1["face"]["at_tau"]),
                                                                   face_reviewer_reading=dict(min=0.769, at_tau=-11.25)),
                                                    fix02_sea=dict(vertex=dict(min=sa["vertex"]["min"], at_tau=sa["vertex"]["at_tau"], tstar=sa["vertex"]["tstar_min"]),
                                                                   face_this_reading=dict(min=sa["face"]["min"], at_tau=sa["face"]["at_tau"], tstar=sa["face"]["tstar_min"])),
                                                    note_ja="修正01 の記録の「全節点 0.86」（0.858）は 5 節点おき＋t* の値。全 251 節点の頂点の読みは 0.856（τ −4.25）。面の読みは自己評審の読みで 0.769（τ −11.25）。"
                                                            "この群の面の読み（継ぎ目の辺の両側の三角形、主役波は内へ 1 つ・near は行 1）では 0.846（τ −10.0）で、自己評審の 0.769 の三角形の取り方は再現できなかった（両方を書く）")),
             verdict="直した"),
    ]
    rows = [
        dict(row="［利用者の言葉］Q16「浪前方缺少自然的凹陷」① 谷の縁の段と海の色の連続", value=dict(trough_share_tstar=tr, sea_ai_mid_frac_after=dict(
            seat_toward_wave_t12=sid["after"]["seat_toward_wave_t120"]["ai_mid_frac"], seat_low_t12=sid["after"]["seat_low_t120"]["ai_mid_frac"]),
            palette="海の限定色は主役波の材質 PL29_Ukiyoe_Hero.mat から写す（藍濃の 1 段の差なし）",
            note_ja="修正01：谷の縁のうねり pl30_trough_rim と、頂の内・唇の帯の段（藍中の地に藍濃の溝、頂の線と泡の点）。t* の谷の大部分は主役波のシートの中（主役波の材質）。座席の低い視点の t* は近い海が座席の船の船体の陰で見えない"),
             verdict="一部（座席から波の方向は段が読める。座席の低い視点では海が見えない。修正02 で真上の帯の端を細らせた）"),
        dict(row="［利用者の言葉］Q18 二次設計 ② 手前の小波（富士形の小波）", value="白の頂（今の高さ ÷ 頂の高さ > 0.62）、一周 24 本の爪の房（角度は断片の中で求め、頂の後ろの切れ目なし）、縁の泡の舌 40 本、縁の外の泡の白い点、胴は頂を中心にした藍中の溝。足は藍の溝で鋸歯なし。"
                                                                  "修正02：頂の三日月（極に集まった淡い水色）を消し、房の長さを今の白い頂の高さに比例させた（形成の途中の触手なし）",
             verdict="満たす"),
        dict(row="［利用者の言葉］Q16「把右侧的浪和大浪连在一起」③ 波頭の稜の連続・S5-2・S5-3", value=dict(
            shoulder_ridge="大波の右の端から 60° の交差の稜 pl30_shoulder_ridge で右の高い波の頂へ。修正02：上り口を 0・1.6 → 2.2・2.8 m に高くし、足し分だけ育ちを遅らせた（pl30_shoulder_lag）。白は細い線で一続き",
            fuji_snow_min_px_t5_10=fu["min_snow_t5_10"], fuji_snow_px_tstar=fu["snow_px_tstar"], stair_seat_f280=st,
            ridge_rows="近い海 64 行（稜の山の所と、地形の誘導の高さ 0.5〜3.5 m を超える所の全部に行を集める）"),
             verdict="満たす（富士を隠さない（t 5〜12 s の全部のコマ）・稜線の段なし・白い稜の一続き・上り口を高くした鞍。大波の右の端の錐の点そのもの（海面の高さ）は主役波の形で仕上げ28 のまま）"),
        dict(row="① S5-1 コマ 184→185 の色面の跳び", value=dict(frames_180_190=M["s5_1_pop"]["frames_180_190"], video_jump_ratio_f185=dict(
            before={k: v.get("f185_ratio") for k, v in vj["before"].items()}, after={k: v.get("f185_ratio") for k, v in vj["after"].items()})), verdict="満たす"),
        dict(row="① 前の継ぎ目の船の支えの稜・溝（目標 法線の内積 ≥ 0.9、竜骨の外で稜・溝 ≤ 0.1 m）", value="fix01_must_fix の 5", verdict="満たさない（改善。fix01_must_fix の 5）"),
        dict(row="① near の帯の溝と動きの折れ（目標 ≤ 0.05 m／コマ²、45° 以下）", value=dict(max_d2_after=ka["max_d2_m_per_frame2"], max_d2_before=kb["max_d2_m_per_frame2"],
            frames_over_005_after=ka["frames_over_005"], slope="fix01_must_fix の 6"),
             verdict="一部（二階差分は満たす 0.199 → 0.038。傾きは帯の式だけの所の t* で 40°、錐の点の扇と地形の誘導の面で 45° を超える）"),
        dict(row="① near と far の T 字", value=dict(far_cols=M["adopted"]["sea_package"]["far_cols"], near_far_max_diff_m=seam["near_far_T_max_diff_m"], curtain="幕を切った"), verdict="満たす"),
        dict(row="① 継ぎ目（G_p28rec の境の輪）", value=dict(before_gap_m=M["seam"]["before"]["ring0_max_diff_m"], after_gap_m=seam["ring0_max_diff_m"]), verdict="満たす"),
        dict(row="① 海の段を今の高さで決める", value="白・泡の点は今の頂点の高さで決める。谷の縁の段は t* の形の面の座標と、谷が深くなる最後の時間の τ（−0.8 → −0.05 s）で決め、今の深さの段（t 9 s の斑の元）はやめた", verdict="満たす"),
        dict(row="① 主役波と海の藍濃の 1 段の差", value="海の材質の限定色を主役波の材質から写す", verdict="満たす"),
        dict(row="① far の線がない", value="遠い海に外殻線と波峰線に平行な溝", verdict="満たす"),
        dict(row="① far の網の折れ目の加速度（設計43 の限界 4・5）", value="far は 1,231 列。船が far を読む加速度は測り直していない（仕上げ43）", verdict="一部"),
        dict(row="① near のつなぎの帯の水の急な減速（設計43 の限界 3）", value=dict(keel_water_accel=hv), verdict="一部（竜骨の下の水の 30 Hz の二階差分の最大 167.5 → 81.9 m/s²。仕上げ43）"),
        dict(row="① 仮置き M1_Revision_LeftSupport の置き換え", value="左奥の船のうねり pl30_left_swell（面の座標を 20 個の並びにした。稜の系の溝、白にはしない）", verdict="満たす"),
        dict(row="② 写真の錐状の副峰（Q12、優先度は低い）", value="作業しない（記録のみ）", verdict="記録のみ"),
        dict(row="③ near の格子と稜線の段・線の点滅（F7-2）", value=dict(lines=lines["after"]["one_frame_drops"], lines_before=lines["before"]["one_frame_drops"]),
             verdict="満たす（座席 v1 のコマ 270〜300 の 1 コマだけの線の消え 18 → 5）"),
        dict(row="③ 右の高い波の尖りの扇（原画視点と、側面・背面の細長い尖り）", value="fix01_must_fix の 4・10、fix02_must_fix の 3、record_stage_review",
             verdict="一部（原画視点の扇と左の側面の細い白い角は消え、近い視点の白い頂は稜に沿う帯になった。記録の部の読み：回り台 60〜120° の t* の房は四角い歯で爪として読めず、"
                     "方位 90° に白い縦の棒と縦の溝の帯。後の群へ）"),
        dict(row="③ 座席から波の方向の near の大きな平らな面と縦の硬い色の段（F7-4）", value=dict(seat_toward_wave_t105=dict(before=sid["before"]["seat_toward_wave_t105"], after=sid["after"]["seat_toward_wave_t105"])),
             verdict="満たす（fix01_must_fix の 3）"),
        dict(row="③ 右の高い波の輪の間隔", value="近い海 64 行。稜の山の所と地形の誘導の全部に行を集める", verdict="満たす"),
        dict(row="終わったら 71・76・213 を仕上げ40 で判定する", value="仕上げ40 へ（71・76 は不合格のまま値も同じ。213 boat_ochre は仕上げ29 の値へ戻った）", verdict="送る"),
        dict(row="Q28 の審査の規則（7 視点＋回り台、t 6・9・10.5・12 s）", value="面の座標の継ぎ目の点線・段の帯・藍の四角・平らな板・斑・形成の途中の偽の白・水平線の白い楔はない（修正02）。"
                                                                          "記録の部の読みで残るもの：回り台 60〜120° の t* の右の高い波の房が四角い歯、方位 90° の t*（と 120° の左の端、t 10.5 s の方位 90° の下）に縦の溝の帯と白い縦の棒、"
                                                                          "後ろ 65° の t 10.5・12 s の主役波の右の端の横に縦縞の四角い斑、原画視点 t* の右の高い波の白の帯の左の端が真っ直ぐに切れる",
             verdict="一部（海の側に継ぎ目に近い縦の帯と、爪として読めない四角い歯が残る。主役波の爪は仕上げ32・33）"),
    ]
    closing = [
        dict(criterion="①の数値の目標（設計30 §7）", verdict="一部（T 字・継ぎ目・二階差分は満たす。船の支えの稜・溝・法線と帯の傾きは改善したが満たさない）"),
        dict(criterion="原画視点 t ≈ 5〜10 s で右の波が富士を隠さない", verdict="満たす（雪 2,260／2,260 px を全部のコマで）"),
        dict(criterion="コマ 184→185 の跳びがない", verdict="満たす"),
        dict(criterion="座席から波の方向と座席の低い視点の t* で谷の縁の段が見える（near の藍中が 1.9% より増える）",
             verdict="一部（座席から波の方向：段の画素が画面の 10.0%。座席の低い視点：近い海が座席の船の船体の陰で見えない）"),
        dict(criterion="② 手前の小波に白の縁の模様があり、足が鋸歯でない", verdict="満たす"),
        dict(criterion="③ 波頭の稜が大波の肩から続き、座席 v1 のコマ 280 の稜線の階段がない", verdict="満たす（修正02：上り口を 2.2・2.8 m に高くした鞍（育ちの遅れ pl30_shoulder_lag で富士の雪を隠さない）。白い稜は細い線で一続き。階段なし（測る所に右の高い波が入らない読み。目でも確かめた））"),
    ]
    out = dict(
        schema="GreatWave.Polish30.metrics/1", number="仕上げ30（設計30 周りの海）", backlog_items=M["backlog_items"], made_local=M["made_local"],
        state_ja="閉じる目安 6 つのうち 4 つを満たす（一部 2）。作る部 1 回・修正の回 1 回・［利用者の言葉］の 2 回目の後、自己評審の修正の回 1（must-fix 12 件）と修正の回 2（must-fix 7 件：満たす 5・採った 1・直した 1）。HMD 実機の結果ではない。",
        evidence_kind_ja=M["evidence_kind_ja"], adopted=M["adopted"], fix01_must_fix=must_fix, fix02_must_fix=must_fix2, rows_plan_5_3=rows, closing_criteria_plan_5_3=closing, closing_criteria_met="4/6（一部 2）",
        user_words_open=True,
        user_words_open_ja="Q16 の谷（座席の低い視点では近い海が座席の船の船体の陰で見えない。仕上げ36 の限界）は一部。Q18 ③ 右の高い波は一部（記録の部の読み：房が四角い歯、方位 90° の縦の帯と白い縦の棒）。"
                           "Q16 の稜の連続と Q18 ② 小波は満たす",
        user_words=[
            dict(words="Q16「浪前方缺少自然的凹陷」", item="① 谷の縁の段と海の色の連続", verdict="一部",
                 note_ja="座席から波の方向の t* で段の画素は画面の 10.0%。座席の低い視点の t* は近い海が座席の船の船体の陰で見えない（0%）"),
            dict(words="Q18「大浪前面的小山丘似的小浪和右边高的浪…二次设计」", item="② 手前の小波", verdict="満たす", note_ja="白い頂・爪の房・泡、足は溝。頂の三日月と形成の途中の触手なし"),
            dict(words="同（Q18）", item="③ 右の高い波", verdict="一部",
                 note_ja="作る側（修正02）は満たすとした。記録の部で全解像度の画像と縦横の比を保った図で見直すと、回り台 60〜120° の t* の房は先の平らな四角い歯で爪として読めず、"
                         "方位 90° に白い縦の棒と縦の溝の帯（継ぎ目に近い見え方）があるので一部とした"),
            dict(words="Q16「把右侧的浪和大浪连在一起」", item="③ 波頭の稜の連続・S5-2・S5-3", verdict="満たす",
                 note_ja="上り口を 2.2・2.8 m に高くした鞍、白い稜は細い線で一続き、富士の雪は t 5〜12 s の 211 コマの全部で 2,260 画素、コマ 280 の稜線の階段なし（測る所が空の読みと目で見た稜線）"),
        ],
        record_stage_review=dict(
            when="2026-10-01 22:15〜（修正02 の後、進行役の再評審の前）",
            figures_ja="must-fix の前後の図（fig_pl30_fix01_a・b・trough、fig_pl30_fix02_a・b・c・tail）は、切り抜きを枠の比へ引き伸ばしていた（横に 1.2〜3.7 倍縮む）。"
                       "pl30_sheets.tile_fit で縦横の比を保って作り直した。fig_pl30_fix02_b の回り台 t* の 2 枚は、右の高い波の房の所を枠に近い比で切り抜き直した（方位 90° は x 1000〜1520、120° は x 0〜560）。"
                       "数（pl30_fix01_trough_share.json・pl30_fix02_*.json）は作り直しても同じ。視点ごとの前後の図・回り台の図・動画・fig_pl30_items は元から比を保っていたので変えていない。"
                       "下の読みの切り抜きは fig_pl30_record_review.png（修正02 の採用 fix02/r_final、全解像度、比を保つ）",
            readings_ja=[
                "回り台 t* の方位 60〜120°：右の高い波の白い帯の下の房は、先の平らな四角い歯（城壁のような凹凸）に見え、爪の指としては読めない",
                "回り台 t* の方位 90°：肩の稜が右の高い波の手前の面を下りる所に、白い縦の棒（x 1260〜1320・y 700〜910）と先の尖った白い筋、溝の向きが縦に変わる帯（x 1190〜1490、縁が真っ直ぐ）。"
                "方位 120° の左の端（x 0〜150）と、t 10.5 s の方位 90° の下（x 1230〜1460・y 900〜1080）にも同じ縦の帯",
                "後ろ 65° の t 10.5・12 s：主役波の右の端の横の海（x 640〜720・y 560〜760）に、縦の細かい縞の四角い斑",
                "真上の t*：二つの稜の間（V の内）に細かい縞と、二つの溝の系が薄く重なって交わる所",
                "原画視点 t*：右の高い波の白の帯の左の端が真っ直ぐに切れる（修正02 の記録のとおり）。水平線の白い楔はない（白の画素 46）",
                "左の側面・座席・座席から波の方向：修正02 の記録のとおり（継ぎ目の点線・板・斑・平らな壁は見えない）",
            ],
            verdict_change_ja="［利用者の言葉］Q18 ③ を満たす → 一部、計画 §5.3 の行「③ 右の高い波の尖りの扇」と Q28 の行を満たす → 一部。閉じる目安（6 つ）の判定は変わらない（4 つ満たす・一部 2）",
        ),
        backlog={
            "88": dict(value="主役波の境の輪と near の行 0 の隔たり 7.6 µm、near と far 0.046 mm、幕なし。目で見て穴・継ぎ目なし（7 視点＋回り台）", verdict="記録（交接の前・中・後は段階9）"),
            "93": dict(value="far は半径 650 m、全部の列（1,231）、外殻線つき", verdict="記録"),
            "153〜156・158・160・167〜171・182〜190・202・228・231・233・235・236・239・242・245・248・251〜255・257〜260・264": dict(value="計画 §5.3 の各行（rows_plan_5_3）で数えた", verdict="rows_plan_5_3 のとおり"),
        },
        painting_view_gates=M["painting_view_gates"], evaluator23_counts=dict(after={k: v["counts"] for k, v in ev_a.items()}, fix01_r10={k: v["counts"] for k, v in M["evaluator23"]["fix01_r10"].items()},
                                                                           build_round={k: v["counts"] for k, v in ev_r7.items()},
                                                                           previous_group={k: v["counts"] for k, v in ev_p.items()}),
        gpu_sea_surfaces_ms=gpu, gpu_sea_surfaces_ms_fix01=gpu1, gpu_note_ja=G["method_ja"],
        limits_ja=[
            "船の支え：竜骨の外の稜 0.11 m・溝 −0.33 m、継ぎ目の法線の最小 t* 0.88（0.9 未満 3 頂点）・全 251 節点の頂点の読み 0.865（τ −1.875、修正01 の海は 0.856・τ −4.25）・面の読み 0.855（この群の読み。自己評審の読みでは修正01 の海で 0.769・τ −11.25）、竜骨の断面の船首の外の 1 m の落差 1.7 m。竜骨が大波の前の足（y 0）から 1〜3.5 m・船尾 −1.4 m〜船首 5.2 m にあるため。仕上げ41・43。",
            "帯の傾き：帯の式だけの所の t* は 40° 以下。錐の点の扇の行 0〜5（継ぎ目から 1.5 m の内）の四角 75 個と、形成の途中の右の錐の点の隣（τ −11 s で 74°、作る部も同じ）、地形の誘導の面（右の高い波・小波・船の支え）は 45° を超える。",
            "谷の縁の段：座席の低い視点の t* では、近い海が座席の船の船体の陰で見えない。谷そのもの（底 −2〜−5.4 m）は主役波のシートの中で、谷の底の段と線は仕上げ36（主役波の材質）。",
            "稜の連続：修正02 で上り口を 2.2・2.8 m に高くした（足し分の育ちの遅れ pl30_shoulder_lag は名前の付いた美術の誘導）。大波の右の端の錐の点そのもの（海面の高さ）は主役波の形（仕上げ28）のまま。",
            "右の高い波の白（Q18 ③、一部）：修正02 で稜に沿う帯にした。房（前の側から）は回り台 60〜120° の t* で先の平らな四角い歯に見え、爪の指として読めない（記録の部の読み）。"
            "原画視点 t* の右の高い波の白の帯の左の端が真っ直ぐに切れる（肩の稜の重みの所で細い線へ替わり、遠いので線が細い）。爪の形は仕上げ32・33 の後に主役波の爪の読みと揃える。",
            "肩の稜が右の高い波の手前の面を下りる所（回り台 t* の方位 90°・120° の左の端、t 10.5 s の方位 90° の下）：白い縦の棒（幅約 60 画素）と、溝の向きが縦に変わる帯（縁が真っ直ぐ）。"
            "後ろ 65° の t 10.5・12 s にも主役波の右の端の横に縦縞の四角い斑。継ぎ目に近い見え方（Q28）で、記録の部で見つけた。原因（肩の稜の重みと q の勾配の最大 11 m/m の所か、錐の点の扇か）は調べていない。",
            "手前の小波の房の長さは今の白い頂の高さに比例（t 6 s で 0.42 倍）。小波そのものの育ちは主役波の頂の高さの比 g(τ) のまま。",
            "右の高い波の育ちの遅れ pl30_right_lag は名前の付いた美術の誘導。t 10〜11.5 s の平均 6.1 m/s、最大 8.8 m/s（t 10.33 s）で立ち上がる。",
            "面の座標は連続だが、右の高い波と肩の稜の合流の所で q の勾配が最大 11 m/m（溝が詰まる。画面で細かくなる所は消える）。",
            "竜骨の下の水の加速度 81.9 m/s²（前 167.5）。far の網の加速度は船で測り直していない（仕上げ43）。",
            "海の面の GPU（壁時計の見当、前後 3 回ずつの中央値。gpu_sea_surfaces_ms）：修正02 の材質は修正01 の材質に育ちの表の読みと q の坂・細い線の計算を足した。1 回ごとの揺れは ±0.1〜0.2 ms。HMD 実機は未検証（仕上げ35）。",
            "Release に設計36 の海の色の表（使わない）が写る（DS36SeaPalette の欄が残る）。",
            "評価器の色区の 267（記録のみ）：座席の低い視点の 20 画素以上の帯 2（仕上げ29）→ 3（作る部）→ 4（修正01）→ 2（修正02）。",
        ],
    )
    with open(os.path.join(E, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("written metrics.json", len(rows), "rows", len(must_fix), "must-fix")


if __name__ == "__main__":
    main()
