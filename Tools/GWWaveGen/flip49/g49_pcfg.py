# -*- coding: utf-8 -*-
"""FLIP49：周期の波の計算（PER49）の設定（cfg.json）を書き、走らせる前の確かめ（numpy だけ、1 分以内）と、計画の凍結をする（py -3.10 -B）。
2026-10-15 新しく書いた（周期の波の計画を実装する役）。flip45〜48 のファイルは読むだけ（g48_common・u3_beds・g47_sfwave）。
計画（凍らせた物）：Unity/Build/FLIP49/plan/plan_frozen.json（＋ .sha256）。同じバイトの写しを Unity/Build/FLIP48/plan/plan_P_frozen.json にも置く
（タスクの文がその置き場所を書いたため。本体は FLIP49 の物）。

  py -3.10 -B g49_pcfg.py check              numpy の確かめ（plan/precheck.json）：既存の海底が R0・R1・R2b・R3・R4・C3 の cfg と 1 bit も違わない（assert）、
                                              PG12s が u3_beds.depth と 1e-9 m で同じ、勾配の数値の差、等深線のまっすぐさ、流れ関数の波の値、粒子の数、
                                              Iribarren の数・横の揺れの向き・静振の周期、時間の見込み
  py -3.10 -B g49_pcfg.py freeze             plan/plan_frozen.json（＋ .sha256）と写しを書く（あれば書かない）。下見の json 3 つを plan/ に写す
        --force=1 [--reason=…]：FLIP49 の計算の記録が無い間だけ凍らせ直す。決まりが同じなら理由は要らない。design・honesty を直す時だけ
                                 --reason が要る（refrozen_changes に残す）。criteria・decision_rules・runs は変えられない
  py -3.10 -B g49_pcfg.py cfg S0a|S0b|S1|S2|S3|D0|D1|D3|all [--in_gain=1.06] [--stage=A|B|C] [--from=<D0 の記録>] [--run=<D1 の記録>]
                                              設定を runs/ready/（3D）・strips/ready/（板）に書く。走らせる前の確かめ（precheck）を cfg に入れ、
                                              ok でなければ書かずに止める（g49_chain.py も precheck.ok と build_check と凍らせた計画の SHA-256 を見る）
        --H=6.5|8.5：S1・S2・S3・D0・D1 の波高を変える（S1 の後の決まり (2) の H 6.5 m、決まり (c) の前の S1 型の板の H 8.5 m）
        --band=120：S0b・S1・S2・S3・D0・D1 の入口の帯を 120 m に（S0b の後の決まり。波高計は 128・146・160 m、窓は 130〜285 m）
  py -3.10 -B g49_pcfg.py cfg D2 --rule=a|b|c|d|e|f [--e=b18|hr12] [--stage=B|C]   決まり D2 の 1 つだけ変えた D1
  py -3.10 -B g49_pcfg.py cfg Z0 [--dub=0]    2 段目（組）の板の試し（du_b 無しだけ。du_b は Design 3 の式が要るので未実装）
  py -3.10 -B g49_pcfg.py cfg SMOKE           3D の煙の試し（T0 の一部、判定しない。2026-10-15 足した）：粒子 1.0 m・PG12s・半幅 85 m・0〜8 s を smoke/ready/ に。
                                              場面・帯の DOP の wrangle・水の量の直しのファイル・記録・sf_check・途中保存からの続き（wall_limit 80 s で
                                              起動を 2 回以上に分ける）だけを見る。in_gain は仮の 1.0（S0b の前に走らせてよいように）
  2026-10-15 方案 A（PER49-A、海底 SC37 = FLIP48 C3 の海底を +37.25 m、箱 442 × 85 m・底 −25 m、出口の帯 362〜442 m）を足した：
  py -3.10 -B g49_pcfg.py cfg SMOKE_A|DA1|DA3 [--run=<DA1 の記録>]   方案 A の設定（layout A。cfg の analysis に読みの窓）。DA1 は時間の見込みの上が
                                              2.5 h を越えれば重い記録を 1 コマおき（R4・R5 の every 2）にする。DA2 は下の 2026-10-16 の行（AM-A3）
        DA1 --heavy=cont（既定、2026-10-15 AM-A2）：重い記録を 47 s〜終わりの 1 つの窓で 3 コマごと（下見の巻き始めに縛らない）。
        DA1 --heavy=screen：前の決まり（下見の巻き始め ± [−3, +4] s の窓、時間の見込みが 2.5 h を越えれば 1 コマおき）
  2026-10-16 DA2 を足した（plan/amendments.jsonl AM-A3）：
  py -3.10 -B g49_pcfg.py cfg DA2 [--change=chy40]   DA1 から海底の 1 つだけ（溝の壁の真ん中 ch_y0 55 → 40 m）を変えた主の粗い 3D。波・入口・箱・出口の帯・
                                              92 s・重い記録（47〜92 s を 3 コマごと）・段 C は DA1 と同じ。in_gain は plan/in_gain.json（同じ波なので入口の板は要らない）。
                                              粒子が +5.1 % なので 1 本の時間の上限だけ 3.0 h（AM-A3。判定の閾ではない）。--change=T16 は書かない（AM-A3 で選ばなかった）
  2026-10-16 DA3 を足した（plan/amendments.jsonl AM-A5）：
  py -3.10 -B g49_pcfg.py cfg DA3 [--change=chy30]   DA2 から海底の 1 つだけ（溝の壁の真ん中 ch_y0 40 → 30 m）を変えた主の粗い 3D（方案 A の続き 2 本の 2 本目）。
                                              波・入口・箱・出口の帯・92 s・重い記録・段 C・1 本の上限 3.0 h は DA2 と同じ。時間の見込みは DA2 の測った時間から。
                                              --change=T16 は書かない（AM-A5：T16 は巻く幅を広げ P4b を失う見込み。理由は AM-A5 の t16_resolution）
  py -3.10 -B g49_pcfg.py cfg DA3c --run=<方案 A の記録>   PERIODIC が通った時の +48 s の続き（140 s）。AM-A5 で前の名前 DA3 から DA3c に改めた。
                                              `cfg DA3 --run=…` は前の書き方として残し、前と 1 byte も違わない cfg を出す（queue_id も前の 'DA3'）
  2026-10-16 PROBE025 を足した（probe, not a result。細かい粒子の本番は指導教員の返事の後のまま：Q57・Q64）：
  py -3.10 -B g49_pcfg.py cfg PROBE025 [--W=24] [--t_end=4] [--wall=1740]   粒子 0.25 m（格子 0.5 m、2 進で割り切れる）の主メモリー・時間の短い試し。
                                              DA3 と同じ海底・波・段 C・箱の長さ 442 m・底 −25 m で、半幅だけ W（既定 24 m）に狭める（その時の約束の量の
                                              余りで落ちない大きさ）。probe/ready/ に書く（runs/ に混ぜない）。重い記録（R4・R5）は 2.02〜4 s を毎コマ、
                                              途中保存は 24 コマごと。判定しない。ほかの設定の出す cfg は 1 byte も変えない
  2026-10-16 DA3r を足した（FLIP3D の再生のための記録し直し。判定しない。ほかの設定の出す cfg は 1 byte も変えない）：
  py -3.10 -B g49_pcfg.py cfg DA3r [--ckpt=1824] [--t_end=90] [--wall=1700]   DA3 の途中保存 v.1824（75.958 s）から DA3 と同じ設定のまま
                                              t_end（89.5〜92 s）まで、新しい置き場所 runs/DA3r_…/ で計算し直し、面（R5）と R4 を毎コマ書く。
                                              走らせる前に g49_restart.py seed <cfg>（途中保存と水の量の直しの状態を写す。DA3 の置き場所は読むだけ）、
                                              後に g49_restart.py compare <cfg>（DA3 の 3 コマおきの記録と同じコマで比べる）
  py -3.10 -B g49_pcfg.py freezeA [--force=1 --reason=…]   plan/plan_A_frozen.json（＋ .sha256）を書く（g49_planA.py。あれば書かない）
  check は方案 A の確かめ（T0A：C3 をずらした海底と 1 bit 同じ・u3 と同じ・勾配・形・箱と粒子の数・in_gain・SMOKE_A と DA1 の precheck）も行う
  py -3.10 -B g49_pcfg.py gain <S0b の記録>    S0b の門（plan_frozen.json の strip_gates.S0b）を当てはめ、通れば plan/in_gain.json を書く。
                                              外れなら次の手（in_gain を 7.5/H にして 1 回走らせ直す・帯 120 m・止める）を画面に出す
in_gain：S0b で一度だけ決める（plan/in_gain.json）。S1・D0・D1・S2・S3・D2・D3 はそれが無ければ precheck が ok にならない（--in_gain で与えた時は
  「与えた値」と書き、ok にしない＝走らせない。数を見るためだけ）。
数の印：【測定】前の FLIP の記録、【計算】この道具や下見の計算、【文献】、【推測】、【選び】。
"""
import os, sys, json, math, time, glob, shutil, copy

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                 # noqa: E402
import g49_common as GC            # noqa: E402

G48 = GC.G48
PLAN_REL = "Unity/Build/FLIP49/plan/plan_frozen.json"
DOC = "Unity/Build/FLIP49/plan/plan_frozen.json（design・criteria・decision_rules・honesty）"
COEF_LO, COEF_HI = 0.486, 0.575            # s / (百万粒子・コマ)、FLIP48 R4・C3・R1・R2b【測定から計算】
GROWTH_LO, GROWTH_HI = 1.16, 1.25          # 粒子の増え：1 波 1.15〜1.16【測定】、周期の波 1.25【推測】
R5_S_PER_FRAME = 1.8                       # 重い記録（R5 の面）1 コマの秒（FLIP48 の 3D、粒子 0.5 m）【測定】
LIMIT_3D_H = 2.5                           # 粗い 3D 1 本の上限（時間）【選び：H の 30 分を周期の波で置き換えた】
EXPECT_PARTICLES = {("3d", 0.5): 3633016, ("3d", 1.0): 449666, ("axis", 0.5): 214224, ("flat", 0.5): 293760}   # 【計算】g49_common.count_particles
EXPECT_PARTICLES_A = {0.5: 4981609, 1.0: 625205}   # 方案 A（SC37、箱 442 × 85 m・底 −25 m。粒子 1.0 m は半幅 86 m）【計算】設計の数と同じ
GROWTH_HI_A = 1.30                         # 方案 A の粒子の増えの上：D0（周期の波、粒子 1.0 m）の 1.30【測定】。粒子 0.5 m の周期の波は測っていない
T_END_A = 92.0                             # 判定する崩れ 4 つ（下見の巻き始め 50.5・62.1・74.1・85.8 s）の後まで【選び】
T_END_A3 = 140.0                           # DA3（続き）：+48 s = 4 T【選び】
ONSET_SCREEN_A = [50.5, 62.1, 74.1, 85.8]  # 下見（U3、η/h ≥ 1 の時刻）【計算、下見だけ】。D0 では FLIP の巻き始めが下見と 1 s 以内だった【測定】
PLAN_A_REL = "Unity/Build/FLIP49/plan/plan_A_frozen.json"
T_END_MAIN = 102.0
T_END_D3 = 150.0
ONSET_GUESS = [37.0 + 12.0 * k for k in range(10)]   # 下見の段の上の巻き始めの見込み（s）【計算、下見】。FLIP は 1〜2 s ずれうる
HEAVY_WIN = (-3.0, 4.0)                    # 重い記録の窓 [t_on − 3, t_on + 4]
HEAVY_WIN_GUESS = (-4.0, 4.0)              # D0 の巻き始めが 4 つより少ない時：37 + 12k ± 4 s
# 方案 A DA1 の重い記録の既定（2026-10-15 AM-A2）：下見の巻き始め ± [−3, +4] s の窓（1 コマおき）の代わりに、47 s〜終わりを続けて 3 コマごと（R4・R5 とも）。
# 理由：方案 A の海底は 1:10 の緩い軸で、崩れる所が下見（U3、η/h ≥ 1）より岸寄り（FLIP48 R4・C3 の 326〜353 m）になれば巻き始めが 5〜8 s 遅れ、
# 窓が崩れを外す（P2・P3 の幅と 3D の面が読めない）。続けて記録すれば外さない。R5 のコマ数は窓の 337 → 361（+24、約 +0.01 h）【計算】。
# 47 s = 判定の下限 45 s と最初の下見の巻き始め 50.5 s − 3 s（窓の設計と同じ前の余裕）の間。3 コマ ≤ w_at・mesh_exists の ±1〜2 コマ。
# 前の窓に戻すのは `cfg DA1 --heavy=screen`
HEAVY_CONT_A = dict(t0=47.0, every=3)
# 方案 A DA2（2026-10-16、plan/amendments.jsonl AM-A3）：SC37 から溝の壁の真ん中 ch_y0 だけを 55 → 40 m に（ほかの海底の数は SC37 と同じ）【選び】。
# 理由（diag_DA1）：DA1 の巻いた幅 2.7〜3.5 Hc は巻き始めの頂の横の形 c(y) が広いこと（半分の超えの全幅 F 49〜69 m）で決まる【測定】。
# 下見（U3、DA1 に合わせた倍率）で F −26〜−35 %、c0/c_side と c0/c(4Hc) は下がらない【計算】。T16 H7.0 は c0/c_side 1.16〜1.29 の見込みで止める決まりに当たる【推測】
SPEC_A2_CHANGE = dict(ch_y0=40.0)
EXPECT_PARTICLES_A2 = {0.5: 5238087, 1.0: 656570}   # SC37 ch_y0 40（箱 442 × 85 m・底 −25 m。粒子 1.0 m は半幅 86 m）【計算】g49_common.count_particles。+5.15 %、水 +32,060 m³
LIMIT_3D_H_A2 = 3.0                         # DA2 の 1 本の上限（時間）：DA1 の測った 2.35 h × 粒子 1.0515 ≈ 2.47 h が 2.5 h に近いので（AM-A3）【選び】
DA1_RUN_A = "DA1_SC37_T12H7p5_dp0p5"        # DA2 の時間の見込みに測った値を使う元の記録（runs/<これ>）
# 方案 A DA3（2026-10-16、plan/amendments.jsonl AM-A5）：DA2 の海底から溝の壁の真ん中 ch_y0 だけを 40 → 30 m に（ほかの海底の数は SC37・DA2 と同じ）【選び】。
# 理由（diag_DA2）：DA1 → DA2（ch_y0 55 → 40）で最も巻いたコマの幅 ÷ Hc の中央値が 3.05 → 2.60、巻き始めの F が −22 %【測定】。同じ向きの次の段は
# 下見 × DA1・DA2 の 2 本で合わせた倍率で中央値 2.29（倍率を弱めない時 2.12）、c0/c_side 1.75〜2.14、c0/c(4Hc) 1.26〜1.37【推測】。
# DA2 からの海底の変わりは x 266 m で |y| 20 m まで +0.10 m 以下、|y| 27 m（4 Hc）で +2.6 m【計算】。ch_y0 25 は 4 Hc の内に溝の壁が入る（|y| 25 m で +7.3 m）ので選ばない
SPEC_A3_CHANGE = dict(ch_y0=30.0)
EXPECT_PARTICLES_A3 = {0.5: 5439373, 1.0: 682249}   # SC37 ch_y0 30（箱 442 × 85 m・底 −25 m。粒子 1.0 m は半幅 86 m）【計算】g49_common.count_particles。DA2 の 1.0384 倍
LIMIT_3D_H_A3 = 3.0                         # DA3 の 1 本の上限（時間）：DA2 と同じ（DA2 の測った 2.32 h × 粒子 1.038 ≈ 2.4 h）【選び】
DA2_RUN_A = "DA2_SC37y40_T12H7p5_dp0p5"     # DA3 の時間の見込みに測った値を使う元の記録（runs/<これ>）
# PROBE025（2026-10-16、probe, not a result）：粒子 0.25 m の主メモリー・時間の短い試し。DA3 の海底・波・段 C のまま半幅だけ狭める。
# 理由：この PC は主メモリー 63.8 GB・ページファイル 1 GB（C:、上限 4 GB）で約束の量の上限 64.8 GB。試しを決めた時、ほかのアプリが 45.3 GB を
# 約束していて余りは約 19 GB【測定】。半幅 85 m の粒子 0.25 m は初め 43.7 M 粒子【計算】で、DA3 の 1 粒子あたり（7.13 GB ÷ 6.28 M）なら 50 GB 近く
# 【推測】になり、余りを越えて hython やほかのアプリが落ちうる。半幅 24 m は 8.39 M 粒子【計算】で見込み約 11 GB【推測】。
DA3_RUN_A = "DA3_SC37y30_T12H7p5_dp0p5"     # PROBE025 の見込みの元（runs/<これ>）
PROBE_DP = 0.25                             # 粒子（格子 0.5 m）。2 進で割り切れる（GC.check_dp の計画の粒子）
PROBE_W = 24.0                              # 既定の半幅（m）【選び】
PROBE_T_END = 4.0                           # 既定の終わり（s）【選び】：起動 1 回 ≤ 29 分に収まる短さ
PROBE_T_END_MAX = 6.0                       # これより長い PROBE025 は書かない（probe の決まり）
PROBE_HEAVY = (2.0 + 0.5 / 24.0, 4.0)       # 重い記録の窓（s）。2 s までは軽い記録だけ（解く時間と記録の時間を分けて測る）
EXPECT_PARTICLES_PROBE = {24.0: 8393829, 16.0: 5319010, 32.0: 12188808, 85.0: 43732762}   # DA3 の海底・粒子 0.25 m・箱 442 m・底 −25 m【計算】count_particles
DA3_RSS_PEAK_GB = 7.13                      # DA3（粒子 0.5 m）の起動ごとの最大 RSS の最大【測定】runs/DA3…/chain.log
DA3_PARTICLES_MAX = 6280606                 # その時の粒子の最大【測定】
# DA3r（2026-10-16、FLIP3D の再生のための記録し直し）：DA3 の途中保存から、新しい記録の置き場所で、同じ設定のまま面（R5）と R4 を毎コマ書く。
# 理由：DA3 の面は 3 コマおき（8 個/s）で、Unity の再生が段になる（Docs/Progress/FLIP3D_Playback_ja.md §5・§6）。形は作らない（物理だけ）。
# DA3 の記録の置き場所には書かない（途中保存と水の量の直しの状態は g49_restart.py seed が新しい置き場所へ写す）。ほかの設定の出す cfg は 1 byte も変えない
DA3R_CKPT = 1824                            # 既定の途中保存（75.958 s）：繰り返しの窓の始め 77.25 s（コマ 1855）以前で最も遅い物【測定：DA3 の ckpt/】
DA3R_LOOP_S = (77.25, 89.25)                # FLIP3D の繰り返しの窓（FLIP3D_Playback_ja.md §1、f3d_loop_ana の選び）
DA3R_T_END = 90.0                           # 既定の終わり（s）：窓の終わり 89.25 s ＋ 0.75 s（窓を 1 コマ単位で選び直す余り）【選び】
DA3R_T_END_MIN = 89.5                       # これより短くは書かない（1 周期 ＋ 余り）
DA3R_T_END_MAX = 92.0                       # DA3 の面の記録が続けてある終わり（同じコマで比べられる所）
DA3R_MAX_H = 1.0                            # 1 本の上限（時間）【選び】。見込みは DA3 の測った 1 コマの時間 ＋ 面を毎コマ（下の da3r_cost）
DA3R_CKPT_EVERY = 24                        # 途中保存の間隔（コマ）：2 回目の起動で計算し直すコマを少なくする【選び】
DA3R_FULL_T_END_MAX = 140.0                 # --full（2026-10-16、利用者「50〜135 秒を毎コマ記録し、繰り返さずに続けて再生」）：DA3 の続き（DA3c）の終わり 140 s まで
DA3R_FULL_MAX_H = 6.0                       # --full の 1 本の上限（時間）【選び】：約 2,100 コマ × 約 6.4 s ＋ 起動の重なり
DA3R_FULL_CKPT_EVERY = 48                   # --full の途中保存の間隔（コマ）：置き場所を抑える（1 個約 0.2 GB）【選び】
DA3R_PHYS_KEYS = ("kind", "layout", "stage", "parms", "sf", "wave", "drift", "solver", "box", "bed", "gauges", "level_regions", "level_box",
                  "level_guard_m", "sf_check", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "analysis")   # DA3 と 1 つも違えない物
DA3R_RUNTIME_MODULES = ("flip49/g49_common.py", "flip49/g49_tanklib.py", "flip49/g49_run.py", "flip49/g49_build_tank.py", "flip49/g49_chain.py",
                        "flip48/g48_common.py", "flip47/g47_sfwave.py")   # 計算に効く道具（g49_pcfg は cfg を書くだけ）


# ====================================================================== 凍らせる計画（g49_pcfg.py freeze）
def frozen_plan():
    tg48 = json.load(open(GC.REPO + "/Unity/Build/FLIP48/plan/plan_frozen.json", encoding="utf8"))["targets"]
    s_, sfT = GC.sf_solve()
    P = dict(
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_pcfg.py freeze", canonical_path=PLAN_REL,
        copies=["Unity/Build/FLIP48/plan/plan_P_frozen.json"],
        supervisor_Q52="一つの波ができればよいわけではなく、大波が定期的に現れるような状態が作れる方法を検討してください。",
        user_20261015_ja="老师说过他想要的是周期性的能产生这种大浪的办法；大浪的收束效果不太明显；视频要在大浪最像原画的时候用红框框出来（利用者 2026-10-15）",
        reading_ja="Q52 の我々の読み（宣言）：規則的なうねりを固定した海底に入れ、毎回の波が同じ所で大きな細い巻き波になる（12 s ごと）。"
                   "「静かな波の間に大きな組が来る」の意味なら 2 段目（組）が答え。どちらかは指導教員への問いとして残す",
        campaign="PER49",
        design=dict(
            forcing=dict(kind="regular unidirectional straight-crested Fenton stream-function wave, zero mean mass flux (u2 = 0)",
                         source="g47_sfwave.solve(17, 12, 7.5, N=40)（読むだけ）", T_s=12.0, H_m=7.5, h0_m=17.0,
                         values_computed=dict(L_m=sfT["L"], c_mps=sfT["c"], eta_crest_m=sfT["eta_crest"], eta_trough_m=sfT["eta_trough"],
                                              u1_mean_current_mps=sfT["u1_mean_current"], ursell=sfT["ursell"], H_over_Hmax=sfT["H_over_Hmax"]),
                         inlet_band=dict(x_m=[0.0, GC.IN_X1], weight="w = (exp(chi^3.5)-1)/(e-1), chi = (100-x)/100, per substep 1-(1-w)^(dt/dt0), dt0 1/24 s",
                                         E="in_gain x walltaper(20 m) x rampT(half-cosine 24 s) x setenv(=1)",
                                         relaxed="vel.x toward E*u_SF at Y = max(min(y, eta)+h, 0); vel.z (lateral) toward 0; vertical velocity and eta NEVER relaxed",
                                         x_p_m=GC.X_P, in_gain="calibrated once in S0b (plan/in_gain.json)"),
                         frozen_wave_changes=dict(H_6p5="if the break moves onto the 1:10 approach (rule b / S1 pre-rule)", H_8p5="if P1 fails (rule c)"),
                         stage2_sets=dict(P_s=84.0, up_s=12.0, flat_s=36.0, down_s=12.0, lull_s=24.0, envelope="retarded time t - (x - x_p)/cg (set_cg)",
                                          du_b="bound long-wave term: NOT implemented in this step (needs the Design 3 formula)", trigger="see stage2_trigger")),
            bed=dict(name="PG12s", spec=GC.bed_record(GC.PG12S), u3_name="PGs_ledge10_s40 with h_L 12, x_toe 180.25, xb1 200, xb2 230",
                     parts=dict(FOCUS="tapered sech^2 spur, 1:10 from 17 m to 12 m (x 180.25-230.25)", BREAK="1:2.5 ledge 12 m -> 1.7 m (x 230.25-255.9), flat across |y| <= 12 m",
                                DRAIN="20 m reef flat (x 256-276), 1:2 down to a 6 m lagoon open sideways to the 17 m flanks"),
                     honesty="design choice resembling a slab-reef front, not a measured site"),
            domain=dict(Lx_m=GC.LX, W_m=GC.W_MAIN, symmetry="half tank: symmetry plane y = 0 and wall y = 85 (= a row of identical reefs 170 m apart)",
                        z_m=[-17.0, 17.0], particle_m=0.5, veltransfer="flip", layout_m=dict(inlet_band=[0, 100], free_flat=[100, 180.25], focus=[180.25, 230.25],
                                                                                              ledge=[230.25, 255.9], reef_flat=[256, 276], lagoon_from=285, exit_band=[290, 360]),
                        t_end_s=T_END_MAIN, ramp_s=24.0, gauges=dict(x_m=list(GC.GAUGE_X), y_m=list(GC.GAUGE_Y))),
            absorber_and_drift_fix=dict(exit=dict(x_m=[GC.EX_X0, GC.LX], w="1 - exp(-%g chi^2 dt) on vel.x and vel.z toward 0" % GC.EX_SIGMA,
                                                  sigma_theory=GC.EX_SIGMA_THEORY),
                                        stage_A=dict(window_m=list(GC.VOL_X), formula="d = clamp((V0 - V)/(V_win0*tau), +-0.004/s), tau 4 s, V0/V_win0 = mean over 1.0-1.5 s",
                                                     V="end-of-frame surface SDF, above-bed cells, weight clamp(0.5 - sdf/vox, 0, 1)"),
                                        stage_B=dict(trigger="band-core period-mean drift > 0.3 m under A", region_m=list(GC.HOLD_X),
                                                     formula="I += (L_ref - mean_T(L_band))*dt/(h0*T*Ti), Ti 300 s, d_band = clamp(I, +-0.004/s); integral only, frozen while clipped"),
                                        stage_C=dict(trigger="A and B both fail", probe_m=list(GC.PROBE_C), formula="du_abs = -sqrt(g/h0)*(mean_T(eta at x 100-110) - reading at 1.0-1.5 s), added to the inlet target u x walltaper; volume correction off"))),
        criteria=dict(
            source="P1-P5 and H thresholds copied unchanged from Unity/Build/FLIP48/plan/plan_frozen.json (targets); none loosened",
            targets48=tg48,
            definitions=dict(judged_breaker="centre (y 0.5 m) onset at t >= %g s" % GC.T_JUDGE, window_k="[t_on,k - T/2, t_on,k + T/2]",
                             Hc_k="centre crest above the still level at onset (ana.json onset.eta_c)"),
            per_breaker=dict(
                P1=dict(x_max_m=GC.X_P1_MAX, x_rule="5 m upstream of the exit band (x_exit - 5)", time_rule="inside its own window k",
                        text="the y 0.5 m row reaches a vertical tangent inside window k at x <= 285 m (frozen 330 m tightened; 17.5 s replaced by the window)"),
                P2=dict(width_over_hc_max=tg48["P2"]["width_over_hc_max"]),
                P3=dict(width_over_hc_max_overturn=tg48["P3"]["width_over_hc_max_overturn"], width_over_hc_touchdown=tg48["P3"]["width_over_hc_touchdown"], report="atan(c/v)"),
                P4a=dict(side_band_m=list(GC.SIDE_BAND), x_side_max_m=GC.X_P1_MAX, ratio_min=tg48["P4a"]["ratio_min"], ratio_clear=tg48["P4a"]["ratio_clear"],
                         text="c(0) / mean crest of |y| 70-84 m (x <= 285 m) >= 1.5; >= 2.0 ('clearly focused') reported separately as the aim"),
                P4b=dict(ratio_4hc_min=tg48["P4b"]["ratio_4hc_min"], text="c(0)/c(|y| = 4 Hc) >= 1.3 and no row at |y| >= 4 Hc curls before centre touchdown"),
                P5=dict(chord_min_deg=tg48["P5"]["chord_min_deg"], chord_good_deg=tg48["P5"]["chord_good_deg"], lip_min=tg48["P5"]["lip_min"],
                        hood_min=tg48["P5"]["hood_min"], print=tg48["P5"]["print"], report="per-k values and medians, never best frames only")),
            periodicity=dict(
                PER1="at least 3 consecutive judged breakers each meet P1-P4",
                PER2=dict(onset_x_within_m=10.0, text="their onset x within +-10 m of their median"),
                PER3=dict(Hc_cv_max=0.10, Hc_cv_good=0.05, interval_s=[11.4, 12.6], phase_std_over_T_max=0.05),
                PER4=dict(trend_x_m_max=10.0, trend_Hc_rel_max=0.10, max_dev_from_first_m=10.0, text="|linear trend x (n-1)|; checked over D1 and again over D3"),
                PER5=dict(H_inlet_rel=0.05, H_inlet_x_m=[110.0, 160.0], band_core_change_m_max=0.3, free_flat_abs_mean_m_max=0.3,
                          report_only=["reef_flat", "lagoon", "side"])),
            health=dict(bed_leak_frac_max=tg48["H"]["bed_leak_frac_max"], volume_drift_max=tg48["H"]["volume_drift_max"],
                        still_offset_max_m=tg48["H"]["still_offset_max_m"], mp4=True, wall_max_h_per_coarse_3d_run=LIMIT_3D_H,
                        wall_rule="the 30-min-per-run rule of FLIP48 H is replaced by <= 2.5 h per coarse 3D run, launched as chunks of <= 29 min",
                        init_check="not applicable: still-water start (no solitary initial state); the inlet target is checked by sf_check (reported only)",
                        volume_report="raw and corrected volume and the share of frames at the dmax cap (stage C: P-mean interior volume x 110-285)"),
            strip_gates=dict(S0a=dict(band_core_change_max_m=0.05, spurious_u_max_mps=0.05, volume_change_max=0.001, still_offset_max_m=0.1),
                             S0b=dict(H_rel=0.05, c_rel=0.02, H_cv_max_at_128=0.03, Kr_max=0.1, band_drift_max_m_6T=0.1, gain_rescales_max=1),
                             S1=dict(band_core_period_mean_change_max_m=0.3, volume_change_max=0.01),
                             D1_start="only after S0a, S0b and S1 pass (or the drift stage is escalated) and D0 has run the whole pipeline"),
            best_frame_rule=dict(window="for each judged k: frames from centre onset to touchdown + 0.5 s (no touchdown: onset + 2.5 s)",
                                 score="score3 = sum of the print-band misses of face chord (0.1-0.5 eta_c), front foot (0.1 eta_c) and hood area (g47_video.score3, "
                                       "the same formula as the earlier GitHub videos), on the centre section r2 measured with STUDY52 measure_mask",
                                 order=["score3 (g47_video formula on this tool's centre-section measures)", "minimum of the 5 ana scores (score5)", "steepest frame"],
                                 tie="smaller chord miss, then higher hood", overall="minimum score3 over judged k", representative="breaker with the median score3",
                                 output="<run>/pana/best_frames.json (for the video tool g48_video2.py, which this tool does not edit)"),
            deliverables="per 3D run: an mp4 that draws a red box around the crest at the most print-like moment of each breaker (hold 1 s, 0.25x around it, print outline), "
                         "a top view of eta with centre and side crest heights and their ratio, a cross-section of eta along the crest line versus y at onset, "
                         "breaker number k and the periodicity table; per-k table, RESULT_ja.md with tagged numbers, run json",
            verdict_wording=dict(full="P1-P5 on every judged breaker plus PER1-PER5",
                                 periodic_narrow_peak="PER1-PER5 with P1-P4 on >= 3 consecutive breakers: 'breakers k = a..b repeated within the frozen bands'",
                                 never="'steady state' (only 4-9 waves can be judged; lab regular-wave breaking needs 10-100 waves to settle [literature, re-read before quoting])",
                                 partial="anything less, breaker by breaker", self_assessment="all scores are AI self-assessment; the user judges print-likeness")),
        runs=[dict(id="T0", what="code and build checks only"), dict(id="S0a", what="still axis strip, bands on, target 0, stage A, 30 s"),
              dict(id="S0b", what="flat strip inlet calibration, 100 s, at most one gain rerun"), dict(id="S1", what="PG12s axis strip, 120 s (2D reference)"),
              dict(id="D0", what="3D dp 1.0 plumbing and preview, 102 s, never judged, mp4 to the user labelled coarse preview"),
              dict(id="D1", what="main coarse periodic 3D run, dp 0.5, 102 s, heavy records in per-wave windows"),
              dict(id="S2/S3", what="drift-cause A/B strips (no correction / FLIP47 mode 0)"), dict(id="D3", what="+48 s continuation to 150 s if PER1-PER4 pass"),
              dict(id="D2", what="single-change rerun by the D2 rule, at most two"), dict(id="Z0/Z1", what="stage 2 (sets), conditional")],
        decision_rules=dict(
            after_T0="any check fails: fix the code; no simulation until all pass",
            after_S0a="band-core change >= 0.05 m or spurious |u| >= 0.05 m/s: bug hunt; no further runs until it passes",
            after_S0b=["H off by more than 5 %: in_gain = 7.5/H_meas and rerun once", "still off, or c off > 2 %, or Kr > 0.1: lengthen the band to 120 m once and rerun",
                       "still failing: stop and report the inlet as failed"],
            after_S1=["(1) band-core drift > 0.3 m: S1 with stage B (+12 min); if still failing, stage C; if all fail, go on with the smallest-drift variant and report PER5 failed",
                      "(2) the 2D wave breaks on the 1:10 approach (onset x < 225 m) in >= 2 of periods 3-8: switch to H 6.5 m before D0",
                      "(3) otherwise D0 unchanged; 2D shape recorded only"],
            after_D0=["pipeline/record/analysis/mp4 failure: fix and rerun D0",
                      "health failure (bed leak, |dV| >= 1 %, lateral asymmetry growth > 20 %/period, reef set-up > 3 m, breaking at x < 180 m): diagnose before D1; forcing cause: stop and report",
                      "otherwise set the D1 heavy-record windows from the D0 onsets and start D1 (never judged on P1-P5, never used to change the design)"],
            after_D1=["PER1-PER4 pass: D3 first; then if P5 fails on >= 2 breakers, D2 rule (e)",
                      "otherwise D2, first match: (a) PER5 fails -> next drift stage (B, then C), strip first; (b) onset x < 230 m on >= 2 judged breakers -> H 6.5 m; "
                      "(c) P1 fails on >= 2 -> H 8.5 m after one S1-type strip; (d) P4a < 1.5 or P4b fails on >= 2 -> R4's 25 m side channel (zb -25; says it lowers the side reference); "
                      "(e) P1-P4 pass but chord < 55 deg on >= 2: side share >= 70 % (C3A budget) -> b_end 18 m, else reef top h_r 1.2 m; "
                      "(f) every breaker passes P1-P4 but PER2-PER4 fail with band drift <= 0.3 m -> unshifted Lx 400 layout"],
            after_D2=["moved the way the rule says: keep, re-evaluate (at most two D2 runs, then report)", "moved the wrong way: revert, negative result, no further tuning of that knob"],
            after_D3=["new breakers within the bands: 'breakers k = a..b repeated to 150 s' and cut a seamless 12 s loop", "drift/Hc growth after 100 s: report as FLIP47-like late drift; S2/S3 if not done; then rule (a) or (f)"],
            after_S2S3="confirmed (S3 band core falls 1-3 m and break moves offshore while S1 holds) or refuted (S3 within 0.3 m and 5 m of S1); does not change a passing D-run",
            stage2_trigger=["(i) the supervisor or the user says 'periodic' means big waves separated by calmer ones",
                            "(ii) after D1 and any D2, P4a < 2.0 on most judged breakers (focusing not clearly visible)",
                            "then Z0 and Z1 (50 min); the 4-5 h dp 0.5 set campaign only after the user sees Z1"],
            global_rules=["one change per run", "never loosen a frozen threshold after seeing results", "rule (e) without effect on P5: report P5 as the open problem"]),
        honesty=dict(
            chosen=["regular swell instead of sets as the first answer to Q52", "T 12 s and H 7.5 m", "PG12s geometry", "40 m shift and Lx 360 x W 85 half tank",
                    "band lengths (inlet 100 m, exit 70 m)", "dp 0.5, t_end 102 s, judged cutoff t >= 45 s", "drift-fix stages and gate values",
                    "P1 x limit 285 m", "best-frame rule, D2 rule order, stage-2 trigger", "x_p 80 m (same phase reference as the U3 screening)",
                    "PER thresholds (+-10 m, CV 10 %, T +- 5 %, 0.3 m) are chosen tolerances"],
            computed=["SF wave properties", "mode cutoff, Iribarren numbers, seiche periods, particle counts, run-time estimates",
                      "exit sponge sigma %g/s: optimum of the Perić & Abdel-Maksoud 2018 1D theory (the FLIP45 r45 function) for T 12 s, h 17 m, 70 m band "
                      "(CR 0.046; the FLIP45 value 2.37 gives 0.166 here)" % GC.EX_SIGMA,
                      "screening results (depth-averaged model without overturning; predictions to be tested, not FLIP results)"],
            measured=["FLIP47 2D periodic repetition, its late band drop and drift", "relax_w 1 water pull", "FLIP45 sponge reflection", "FLIP48 solver rates, R4/C3 P-results, C3A side-feed share"],
            guesses=["FLIP47 drift cause (tested by S2/S3)", "periodic particle growth 1.25, record overhead", "ledge reflection Kr 0.1-0.3", "lateral-mode build-up", "2D break depth from Goda's index"],
            not_predicted="P2, P3 and P5 (the print-like shape)",
            literature_to_reread="Battjes 1974, Goda 2010, Mead & Black 2001, Haller & Dalrymple 2001, Longuet-Higgins & Stewart, Van Dongeren & Svendsen 1997 (used from abstracts/secondary sources/memory)"),
        screening=dict(files=list(GC.SCREEN_JSON), copied_to="Unity/Build/FLIP49/plan/screening/", tag="computed, screening only (U3 depth-averaged Boussinesq/NSW, no overturning)"),
        implementation=dict(
            tools=["Tools/GWWaveGen/flip49/" + n for n in ("g49_common.py", "g49_tanklib.py", "g49_build_tank.py", "x49_build.py", "g49_run.py", "g49_chain.py",
                                                         "g49_pcfg.py", "g49_periodic_ana.py")],
            module_sha256_16=GC.module_shas(), hip="Houdini/FLIP49/g49_tank.hiplc", build_check="Unity/Build/FLIP49/_logs/build_check.json",
            build_check_at_freeze=_build_check_summary(), read_only=["flip45-flip48 files", "g48_tank.hiplc", "g48_video2.py (not edited)"],
            notes=["dp 1.0 boxes round the half width up to the 2 m grid: D0 runs at W 86 m (455,606 particles), dp 0.5 at W 85 m (3,633,016) [computed]",
                   "axis-strip Merian seiche 2*integral(dx/sqrt(g d)) = %.1f s, flat 17 m = %.1f s [computed]; the stage-B integral time 300 s is %.2f x the axis value "
                   "(the design said >= 4 x 56-66 s); kept as chosen" % (_seiche_axis(), 2 * GC.LX / math.sqrt(GC.G * GC.H0), 300.0 / _seiche_axis()),
                   "stage B uses tau_B = T in I += e*dt/(h0*tau_B*Ti) (the design gave only 'integral only, Ti 300 s') [chosen]",
                   "stage C reads 'eta_bar_T - 0' as the one-T mean minus the same probe's reading at 1.0-1.5 s (removes the particle-surface offset) [chosen]",
                   "stage 2 (sets): the retarded-time envelope (set_cg) is implemented in VEX; the bound long-wave term du_b is NOT implemented",
                   "the DOP wrangles (relax_zones, vc_div) call the same VEX functions that the build-time SOP probes checked; they are first executed in S0a"]),
    )
    return P


def _build_check_summary():
    p = GC.B49 + "/_logs/build_check.json"
    if not os.path.exists(p):
        return None
    c = json.load(open(p, encoding="utf8"))
    return dict(all_ok=c.get("all_ok"), hip_sha256=c.get("hip_sha256"), date=c.get("date"),
                sf_probe={k: c.get("sf_probe", {}).get(k) for k in ("u_max_abs_over_c", "w_max_abs_over_c", "eta_max_abs_over_H")},
                bed_vex_numpy_max_m=max(float((c.get(k) or {}).get("bed_max_abs_dz_m") or 0.0) for k in ("axis_strip_PG12s", "flat_strip", "PG12s_3d", "R4_g48_path")))


def _seiche_axis():
    return seiche_axis(GC.pg_axis())


def freeze(force=False, reason=None):
    """reason：FLIP49 の計算の記録が無い間だけ、design・honesty の変わりを理由つきで許す（criteria・decision_rules・runs は決して変えない）。"""
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    p = GC.PLAN_FROZEN
    if os.path.exists(p) and not force:
        return p, "exists（変えない）"
    scr = GC.PLAN_DIR + "/screening"
    os.makedirs(scr, exist_ok=True)
    copied = {}
    for nm in GC.SCREEN_JSON:
        src = os.path.join(GC.SCRATCH_U4, nm)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(scr, nm))
            copied[nm] = GC.sha256_file(os.path.join(scr, nm))[:16]
        else:
            copied[nm] = None
    d = frozen_plan()
    d["screening"]["copied_sha256_16"] = copied
    if os.path.exists(p) and force:
        # 凍らせ直し（走らせる前だけ）：決まり（criteria・decision_rules・design・honesty）が前と同じことを確かめ、違えば止める
        old = json.load(open(p, encoding="utf8"))
        same = {k: json.dumps(old.get(k), sort_keys=True, ensure_ascii=False) == json.dumps(d.get(k), sort_keys=True, ensure_ascii=False)
                for k in ("criteria", "decision_rules", "design", "honesty", "runs", "supervisor_Q52", "reading_ja")}
        changed = [k for k, v in same.items() if not v]
        if changed and (not reason or any(k not in ("design", "honesty") for k in changed)):
            raise SystemExit("凍らせ直しで決まりが変わる（%s）。走らせた後なら決して変えない。走らせる前の design・honesty の直しだけ --reason=… で許す" % changed)
        if glob.glob(os.path.join(GC.B49, "runs", "*", "run_c*.json")) + glob.glob(os.path.join(GC.B49, "strips", "*", "run_c*.json")):
            raise SystemExit("FLIP49 の計算の記録があるので凍らせ直さない")
        hist = list(old.get("refrozen_history") or [])
        hist.append(dict(frozen_at=old.get("frozen_at"), sha256=GC.sha256_file(p), refrozen_ja=old.get("refrozen_ja"), changes=old.get("refrozen_changes")))
        d["refrozen_history"] = hist
        if changed:
            d["refrozen_ja"] = "前の凍結 %s（SHA-256 %s…）を、FLIP の計算を始める前に凍らせ直した。変えた所：%s（理由は refrozen_changes）。criteria・decision_rules・runs は同じ" % (
                old.get("frozen_at"), GC.sha256_file(p)[:16], ", ".join(changed))
            d["refrozen_changes"] = dict(keys=changed, reason=reason)
        else:
            d["refrozen_ja"] = "前の凍結 %s（SHA-256 %s…）を、FLIP の計算を始める前に凍らせ直した。決まりは同じ（%s を比べた）。変わったのは道具の SHA-256（implementation）と時刻だけ" % (
                old.get("frozen_at"), GC.sha256_file(p)[:16], ", ".join(same))
    s = json.dumps(d, indent=1, ensure_ascii=False)
    open(p, "w", encoding="utf8", newline="\n").write(s)
    h = GC.sha256_file(p)
    open(p + ".sha256", "w", newline="\n").write(h + "  plan_frozen.json\n")
    cp = GC.PLAN_COPY48
    if not os.path.exists(cp) or force:
        shutil.copy2(p, cp)
        open(cp + ".sha256", "w", newline="\n").write(h + "  plan_P_frozen.json\n")
    return p, "new %s" % h[:16]


# ====================================================================== 設定
def sf_table(H=GC.H_WAVE, T=GC.T_WAVE):
    _, tb = GC.sf_solve(GC.H0, T, H, GC.SF_N)
    return tb


def read_gain():
    p = GC.PLAN_DIR + "/in_gain.json"
    if os.path.exists(p):
        g = json.load(open(p, encoding="utf8"))
        return float(g["in_gain"]), "plan/in_gain.json（%s）" % g.get("source_run")
    return None, None


def parms_for(dp, W, spec, zb=GC.Z_BOTTOM, Lx=GC.LX, smoke=False, layout=None):
    """layout（GC.LAYOUTS の dict）を与えれば出口の帯・水の量の窓をその並びに（方案 A）。無ければ PG12s の数（前と同じ）。"""
    GC.check_dp(dp, smoke=smoke)
    xa0_ = float(layout["ex_x0"]) if layout else GC.EX_X0
    vx_ = tuple(layout["vol_x"]) if layout else GC.VOL_X
    b = GC.box48(dp, Lx=Lx, W=W, zb=zb, floor_pad=2)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=b["W"],
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=1.0, sf_on=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=GC.RAMP_S, wall_taper_m=GC.WALL_TAPER, in_gain=1.0,
             x_p=GC.X_P, xg_end=GC.IN_X1, xa0=xa0_, abs_sigma=GC.EX_SIGMA, abs_pow=GC.EX_POW,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=0.0,
             volcorr_on=1.0, vol_x0=vx_[0], vol_x1=vx_[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(spec))
    return p, b


def drift_parms(stage):
    """段 A・B・C の CTRL と cfg の drift。"""
    if stage == "A":
        return dict(volcorr_on=1.0, hold_on=0.0, duabs_on=0.0), dict(stage="A", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP,
                                                                    V_measure=GC.VOL_MEASURE)
    if stage == "B":
        return dict(volcorr_on=1.0, hold_on=1.0, duabs_on=0.0), dict(stage="B", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP,
                                                                    hold_ti_s=GC.HOLD_TI, hold_tau_s=GC.T_WAVE, hold_dmax=GC.VOL_DMAX,
                                                                    V_measure=GC.VOL_MEASURE)
    if stage == "C":
        return dict(volcorr_on=0.0, hold_on=0.0, duabs_on=1.0), dict(stage="C", tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE)   # V は記録だけ（柱の読み）
    if stage == "none":       # S2（直しはしないが、V は柱の読みで記録する）
        return dict(volcorr_on=0.0, hold_on=0.0, duabs_on=0.0), dict(stage="none", V_measure=GC.VOL_MEASURE)
    if stage == "mode0":      # S3：FLIP47 mode 0（帯を含む水の全部に同じ発散。上限 0.002 /s は FLIP47 の値）
        return dict(volcorr_on=1.0, hold_on=0.0, duabs_on=0.0, vol_x0=0.0, vol_x1=GC.LX), dict(stage="mode0", tau_s=4.0, dmax=0.002, tcap_s=GC.VOL_TCAP,
                                                                                                    V_measure="sdf")   # FLIP47 の写しは元の読みのまま
    raise SystemExit("段は A・B・C・none・mode0")


def windows_from(onsets, win=HEAVY_WIN, t_end=T_END_MAIN, t_min=GC.T_JUDGE - 3.0):
    w = []
    for t in sorted(onsets):
        a, b = t + win[0], t + win[1]
        if b < t_min or a > t_end:
            continue
        w.append([round(max(a, 0.0), 4), round(min(b, t_end), 4)])
    return w


def d0_onsets(d0_dir):
    """D0 の periodic_ana.json の巻き始め（全部の来た波の崩れ）。"""
    p = os.path.join(d0_dir, "pana", "periodic_ana.json")
    if not os.path.exists(p):
        return None, "D0 の解析 %s がない" % p
    d = json.load(open(p, encoding="utf8"))
    ons = [float(e["on_t"]) for e in (d.get("events_found") or [])]
    return ons, p


def make(run_id, kind, dp, W, spec, t_end, stage="A", in_gain=None, H=GC.H_WAVE, windows=None, out_root=None, note="", case_extra=None,
         records=None, zb=GC.Z_BOTTOM, Lx=GC.LX, extra_parms=None, f_start=1, layout=None):
    """1 本の設定。kind：still_strip・flat_strip・axis_strip・3d・smoke。layout："A" なら方案 A の並び（箱・出口の帯・窓・平均の水面の所・
    R4 の x の窓・P1 の上限・頂を探す窓。cfg に layout を書き、g49_periodic_ana.py もそれで読む）。無ければ PG12s の並び（前と同じ cfg）。"""
    LY = GC.LAYOUTS[layout] if layout else None
    if LY:
        zb = float(LY["zb"]); Lx = float(LY["Lx"])
    p, b = parms_for(dp, W, spec, zb=zb, Lx=Lx, smoke=(kind in ("3d", "smoke") and dp == 1.0), layout=LY)
    dpm, drift = drift_parms(stage)
    p.update(dpm)
    if kind == "still_strip":
        p.update(sf_on=0.0)               # 帯は入れたまま、目標 0
    sf = sf_table(H) if kind != "still_strip" else None
    g_used, g_src = (None, None)
    if kind == "smoke":
        g_used, g_src = 1.0, "煙の試しの仮の 1.0（S0b の前。判定しない）"
    elif kind in ("axis_strip", "3d"):
        g_file, g_fsrc = read_gain()
        if in_gain is not None:
            g_used, g_src = float(in_gain), "与えた値（--in_gain）"
        elif g_file is not None:
            g_used, g_src = g_file, g_fsrc
    elif kind == "flat_strip":
        g_used, g_src = (float(in_gain), "与えた値（S0b の 2 回目：7.5/H_meas）") if in_gain is not None else (1.0, "1.0（S0b の 1 回目）")
    if g_used is not None:
        p["in_gain"] = g_used
    if extra_parms:
        p.update(extra_parms)
    vox = b["vox"]
    f_end = GC.frames_for(0.0, t_end)
    r4x = list(LY["r4_x"]) if LY else [180.0, 300.0]
    rec = records or dict(r2=True, r3_z=b["W"] - 0.5 * vox, block=120, r4_block=24, preg_every=24,
                          r4=dict(x=r4x, z1=b["W"], y0=-10.0, y1=16.0, clip_vox=6.0, t0=0.0),
                          r5=dict(t0=0.0, every=1), windows=windows)
    three_d = kind in ("3d", "smoke")
    c = dict(
        run_id=run_id, out_root=out_root or ("runs" if three_d else "strips"), stage="FLIP49", kind=kind,
        case=dict(name="FLIP49_%s_%s" % (kind, GC.bed_kind(spec)), plan_frozen=PLAN_REL, plan=DOC, campaign="PER49", **(case_extra or {})),
        f_start=f_start, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(spec, b),
        sf=sf, wave=dict(kind="stream-function regular wave" if sf else "none (band target 0)", T_s=GC.T_WAVE, H_m=float(H) if sf else 0.0,
                         in_gain=p.get("in_gain"), in_gain_source=g_src, x_p=GC.X_P, ramp_s=GC.RAMP_S, tags=dict(T="選び", H="選び", sf="計算（g47_sfwave）",
                                                                                                             in_gain="測定（S0b）" if g_src and "plan/in_gain" in g_src else "選び／未決")),
        drift=drift, solver=dict(veltransfer="flip", donarrowband=0), records=rec,
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in (LY["level_regions"] if LY else GC.LEVEL_REGIONS)],
        sf_check=dict(every=120, x=[10.0, 40.0, 70.0, 95.0], y=[-15.0, -8.0, -2.0], zl=[0.5 * vox] + ([0.5 * b["W"]] if three_d else [])),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0,
        max_hours=(LIMIT_3D_H if (three_d and dp == 0.5) else (0.75 if three_d else 0.5)), level_box=[0.0, b["Lx"], 0.0, b["W"]],
        n1_x=list(LY["vol_x"] if LY else GC.VOL_X), n1_window=[0.5, 1.5], shore_x=float(GC.edge_x(spec)) if (spec.get("on", True) and GC.is_new(spec)) else 256.0,
        fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)], note=note)
    if LY:
        c["layout"] = LY["name"]
        c["case"].update(plan_frozen=PLAN_A_REL, plan="Unity/Build/FLIP49/plan/plan_A_frozen.json（design・criteria・decision_rules・honesty）",
                         campaign="PER49-A", P1_x_max_m=float(LY["p1_x_max"]))
        c["analysis"] = dict(layout=LY["name"], p1_x_max_m=float(LY["p1_x_max"]), crest_x_min_m=float(LY["crest_x_min"]), crest_window=LY["crest_window"],
                             side_band_m=list(LY["side_band"]), vol_x_m=list(LY["vol_x"]), report_levels=list(LY["report_levels"]),
                             setup_region=LY["setup_region"], plan_frozen=PLAN_A_REL)
    c["precheck"] = precheck(c)
    return c


def precheck(c):
    """走らせる前の確かめ。3D（粒子 0.5 m）は時間の見込み（大きい方）が 2.5 時間を越えれば ok でない。"""
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="計算（numpy、場面と同じ決まり）", wall="計算（FLIP48 の測定の係数から）"))
    ck = out["checks"]
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), float(P["dp"]), zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V))
    key = ("3d" if c["kind"] in ("3d", "smoke") else ("flat" if not spec.get("on", True) else "axis"), float(P["dp"]))
    LY = GC.LAYOUTS.get(c.get("layout")) if c.get("layout") else None
    if LY and LY["name"] == "A":
        out.update(precheck_A(c, P, spec, n))
        ck.update(out.pop("checks_A"))
    elif key in EXPECT_PARTICLES and GC.is_new(spec) and abs(spec.get("x_toe", 0) - 180.25) < 1e-9 and float(P["Lx"]) == GC.LX \
            and (spec.get("ch_h") or 0) == 0 and abs(spec["shelf_h"] - 1.7) < 1e-9 and (spec.get("b_end") or 0) in (0.0, 12.0):
        ck["particles_as_designed"] = bool(abs(n / EXPECT_PARTICLES[key] - 1.0) < 0.02)
    sf = c.get("sf")
    if sf:
        ck["sf_depth_is_h0_17"] = bool(abs(float(sf["h"]) - float(P["h0"])) < 1e-9 and abs(float(sf["h"]) - 17.0) < 1e-9)
        ck["sf_terms"] = bool(len(sf["E"]) == len(sf["B"]) + 1 and len(sf["B"]) == GC.SF_N)
        ck["sf_below_0p9_Hmax"] = bool(float(sf["H_over_Hmax"]) <= 0.9)
    gx_ = [float(v) for v in (c.get("gauges") or {}).get("x", GC.GAUGE_X)]
    ck["band_layout"] = bool(float(P["xg_end"]) < min(gx_) and (float(P["vol_x0"]) >= float(P["xg_end"]) or float(P["vol_x1"]) >= float(P["Lx"]) - 1e-9)
                             and (float(P["vol_x1"]) <= float(P["xa0"]) or float(P["vol_x0"]) <= 0.0) and max(gx_) <= float(P["vol_x1"]))
    ck["exit_after_lagoon_start"] = bool(float(P["xa0"]) >= 285.0 or not GC.is_new(spec))
    ck["bed_above_box_floor"] = bool(c["bed"].get("max_depth_m", 17.0) <= -float(P["zb"]) + 1e-6)
    ck["in_gain_set"] = bool(c["kind"] in ("still_strip", "flat_strip", "smoke") or "plan/in_gain.json" in str((c.get("wave") or {}).get("in_gain_source")))
    if c["kind"] == "3d" and float(P["dp"]) == 0.5:
        f_from = int(c.get("f_resume_est", c.get("f_start", 1)))          # 続き（D3）は前の計算の終わりの次のコマから
        nf = int(c["f_end"]) - f_from + 1
        heavy = heavy_frames(c, f_from)
        g_hi = GROWTH_HI_A if (LY and LY["name"] == "A") else GROWTH_HI
        out["growth_hi"] = g_hi
        lo = COEF_LO * n * GROWTH_LO / 1e6 * nf / 3600.0
        hi = COEF_HI * n * g_hi / 1e6 * nf / 3600.0
        rec_h = heavy * R5_S_PER_FRAME / 3600.0
        wl_ = float(c.get("wall_limit_s", 1740))
        lim_ = float(c.get("limit_h_run", LIMIT_3D_H))   # DA2 だけ 3.0 h（AM-A3）。無ければ前と同じ 2.5 h・同じ鍵の名前
        out.update(frames=nf, heavy_frames=heavy, solve_h_lo=lo, solve_h_hi=hi, records_h=rec_h, total_h_lo=lo + rec_h, total_h_hi=hi + rec_h,
                   limit_h=lim_, fallbacks="heavy records every 2nd frame, then t_end 90 s",
                   launches_est="%d-%d launches of <= %d min" % (math.ceil((lo + rec_h) * 3600 / wl_), math.ceil((hi + rec_h) * 3600 / wl_), round(wl_ / 60)))
        ck["wall_le_2p5h" if lim_ == LIMIT_3D_H else "wall_le_%sh" % GC.tag(lim_)] = bool(hi + rec_h <= lim_)
        if lim_ != LIMIT_3D_H:
            ck["max_hours_le_limit"] = bool(float(c.get("max_hours", 1e9)) <= lim_ + 1e-9)
        ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in (c["records"].get("windows") or [])))
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "外れ：" + ", ".join(k for k, v in ck.items() if not v)
    return out


def heavy_frames(c, f_from):
    """重い記録（R4・R5）を書くコマの数（窓の中、every コマごと。R4 と R5 の every が違えば多い方の数）。窓が無ければ全部のコマ。"""
    rec = c["records"]
    ev = max(1, min(int((rec.get("r4") or {}).get("every", 1)), int((rec.get("r5") or {}).get("every", 1))))
    wins = rec.get("windows") or []
    n = 0
    for f in range(f_from, int(c["f_end"]) + 1):
        t = (f - 1) / 24.0
        if (not wins or any(a - 1e-9 <= t <= b + 1e-9 for a, b in wins)) and (f - 1) % ev == 0:
            n += 1
    return n


def precheck_A(c, P, spec, n):
    """方案 A（SC37）の走らせる前の確かめ（PG12s に特有の確かめの代わり）。返り値 dict(checks_A=…, A=…)。"""
    LY = GC.LAYOUTS["A"]
    ck = {}
    info = {}
    dp = float(P["dp"])
    a2 = is_spec_A2(spec)                     # DA2 の海底（SC37 の ch_y0 だけ 40 m、AM-A3）。DA1・SMOKE_A は偽（前と同じ確かめ・同じ鍵）
    a3 = is_spec_A3(spec)                     # DA3 の海底（SC37 の ch_y0 だけ 30 m、AM-A5）。DA1・DA2・SMOKE_A は偽（前と同じ確かめ・同じ鍵）
    if dp in EXPECT_PARTICLES_A and float(P["W"]) in (85.0, 86.0) and not a2 and not a3:
        ck["A_particles_as_designed"] = bool(n == EXPECT_PARTICLES_A[dp])
    if a2 and dp in EXPECT_PARTICLES_A2 and float(P["W"]) in (85.0, 86.0):
        ck["A2_particles_as_computed"] = bool(n == EXPECT_PARTICLES_A2[dp])
    if a3 and dp in EXPECT_PARTICLES_A3 and float(P["W"]) in (85.0, 86.0):
        ck["A3_particles_as_computed"] = bool(n == EXPECT_PARTICLES_A3[dp])
    ck["A_box"] = bool(float(P["Lx"]) == LY["Lx"] and float(P["zb"]) == LY["zb"] and float(P["floor_pad"]) == 2.0)
    if a2:
        o2, k2 = checks_A2(spec)
        ck.update(k2)
        info["A2"] = o2
        info["A2"]["particles"] = dict(model=int(n), SC37_dp0p5=EXPECT_PARTICLES_A[0.5], ratio_vs_SC37=(n / EXPECT_PARTICLES_A[dp]) if dp in EXPECT_PARTICLES_A else None)
        if c["kind"] == "3d" and dp == 0.5:
            # DA3c（AM-A5、+48 s の続き）だけ、計算するコマ（f_resume_est〜f_end）で見込む。ほか（DA2・前の書き方 DA3 --run）は前と同じ f_end
            nf_a2 = nf_cost(c) if (c.get("case") or {}).get("queue_id") == "DA3c" else int(c["f_end"])
            info["A2"]["cost_from_DA1"] = cost_from_run(DA1_RUN_A, n, float(c.get("limit_h_run", LIMIT_3D_H)), nf_a2)
            cm = info["A2"]["cost_from_DA1"]
            if cm.get("est_hi_h") is not None:
                ck["A2_measured_est_hi_le_limit"] = bool(cm["est_hi_h"] <= cm["limit_h"])
    elif a3:
        o3, k3 = checks_A3(spec)
        ck.update(k3)
        info["A3"] = o3
        info["A3"]["particles"] = dict(model=int(n), SC37_dp0p5=EXPECT_PARTICLES_A[0.5], DA2_dp0p5=EXPECT_PARTICLES_A2[0.5],
                                       ratio_vs_SC37=(n / EXPECT_PARTICLES_A[dp]) if dp in EXPECT_PARTICLES_A else None,
                                       ratio_vs_DA2=(n / EXPECT_PARTICLES_A2[dp]) if dp in EXPECT_PARTICLES_A2 else None)
        if c["kind"] == "3d" and dp == 0.5:
            info["A3"]["cost_from_DA2"] = cost_from_run(DA2_RUN_A, n, float(c.get("limit_h_run", LIMIT_3D_H)), nf_cost(c), src="DA2")
            info["A3"]["cost_from_DA2"]["frames_costed"] = nf_cost(c)
            cm = info["A3"]["cost_from_DA2"]
            if cm.get("est_hi_h") is not None:
                ck["A3_measured_est_hi_le_limit"] = bool(cm["est_hi_h"] <= cm["limit_h"])
    else:
        ck["A_bed_is_SC37"] = bool(all((spec.get(k) == v) if not isinstance(v, float) else abs(float(spec.get(k)) - v) < 1e-12 for k, v in GC.SPEC_A.items())
                                   and GC.is_spur_drop(spec))
    xa0 = float(P["xa0"]); Lx = float(P["Lx"])
    drop_end = spec["x_back"] + (spec["h_lag"] - spec["shelf_h"]) * spec["s_back"]
    info.update(exit_band_m=[xa0, Lx], exit_len_m=Lx - xa0, drop_end_x_m=drop_end, sigma=float(P["abs_sigma"]), theory=GC.EX_THEORY_A)
    ck["A_exit_band_80m_sigma"] = bool(abs((Lx - xa0) - GC.EX_THEORY_A["band_m"]) < 1e-9 and abs(float(P["abs_sigma"]) - GC.EX_THEORY_A["sigma"]) < 1e-12)
    ck["A_exit_after_drop"] = bool(xa0 >= drop_end - 1e-9)
    ck["A_vol_window"] = bool(abs(float(P["vol_x0"]) - LY["vol_x"][0]) < 1e-9 and abs(float(P["vol_x1"]) - LY["vol_x"][1]) < 1e-9
                              and float(P["vol_x1"]) <= xa0 - 5.0 + 1e-9)
    an = c.get("analysis") or {}
    ck["A_P1_limit"] = bool(abs(float((c.get("case") or {}).get("P1_x_max_m", -1)) - (xa0 - 5.0)) < 1e-9 and abs(float(an.get("p1_x_max_m", -1)) - (xa0 - 5.0)) < 1e-9)
    r4 = (c["records"].get("r4") or {})
    edge = GC.edge_x(spec)
    info.update(edge_x_axis_m=edge, r4_x=r4.get("x"), r4_every=r4.get("every", 1), r5_every=(c["records"].get("r5") or {}).get("every", 1))
    ck["A_r4_window"] = bool(r4 and float(r4["x"][0]) <= 230.0 and float(r4["x"][1]) >= edge and float(r4["x"][1]) <= xa0)
    gx = [float(v) for v in (c.get("gauges") or {}).get("x", GC.GAUGE_X)]
    ck["A_gauges_before_toe"] = bool(max(gx) < spec["x_toe"] and min(gx) > float(P["xg_end"]))
    regs = c.get("level_regions") or []
    names = [r[0] for r in regs]
    ck["A_level_regions"] = bool(all(0.0 <= r[1] < r[2] <= Lx for r in regs)
                                 and all(nm in names for nm in ("band_core", "probe_c", "flat", "reef_top", "lagoon", "side", "axis_front")))
    ck["A_layout_named"] = bool(c.get("layout") == "A" and an.get("plan_frozen") == PLAN_A_REL)
    if c["kind"] == "3d":
        ck["A_plan_frozen_named"] = bool((c.get("case") or {}).get("plan_frozen") == PLAN_A_REL)
    return dict(checks_A=ck, A=info)


def spec_A2():
    """DA2 の海底（AM-A3）：SC37 の ch_y0 だけを 40 m に。"""
    sp = dict(GC.SPEC_A)
    sp.update(SPEC_A2_CHANGE)
    return sp


def is_spec_A2(spec):
    """spec が DA2 の海底（SC37 と ch_y0 以外は同じ、ch_y0 = 40 m）か。"""
    ref = spec_A2()
    return bool(GC.is_spur_drop(spec) and all((spec.get(k) == v) if not isinstance(v, float) else
                                               (spec.get(k) is not None and abs(float(spec.get(k)) - v) < 1e-12) for k, v in ref.items()))


def checks_A2(spec):
    """DA2 の海底の numpy の確かめ（数秒）。返り値 (記録, ok)。
    (1) 溝が始まる前（x < ch_x0）で SC37 と 1 bit も違わない (2) どこでも SC37 より浅くならない（違いは溝の項だけ）
    (3) 下見（u3_beds.depth、diag_DA1/d4_u3_screen.py の A_T12H7p5_chy40 と同じ名前）と同じ (4) 軸の縁・最も深い所は SC37 と同じ。"""
    sp0 = GC.SPEC_A
    o, ok = {}, {}
    xs = np.arange(0.0, 442.0, 0.25); ys = np.arange(-90.0, 90.0001, 0.25)
    X, Y = np.meshgrid(xs, ys)
    z0 = GC.bed_z(X, Y, **sp0); z2 = GC.bed_z(X, Y, **spec)
    up = xs < float(spec["ch_x0"])
    deeper = z0 - z2
    ok["A2_bed_equals_SC37_before_channels"] = bool(np.array_equal(z0[:, up], z2[:, up]))
    ok["A2_bed_never_shallower_than_SC37"] = bool(deeper.min() >= -1e-12)
    o["deeper_than_SC37_max_m_by_abs_y"] = {str(v): float(deeper[np.abs(ys) <= v].max()) for v in (10, 20, 25, 27, 30, 33, 35, 40, 85)}
    o["depth_m_x266"] = {str(v): [float(-GC.bed_z(266.0, float(v), **sp0)), float(-GC.bed_z(266.0, float(v), **spec))] for v in (0, 20, 30, 35, 40, 45, 50, 55, 60)}
    U3 = GC.u3_depth_fn()
    Xg, Yg = np.meshgrid(np.arange(-10.0, 442.0001, 0.25), np.arange(-90.0, 90.0001, 0.5))
    u3s = dict(GC.SPEC_A_U3); u3s.update(SPEC_A2_CHANGE)
    dU = float(np.abs(-GC.bed_z(Xg, Yg, **spec) - U3(Xg, Yg, u3s)).max())
    o["vs_u3"] = dict(max_abs_m=dU, u3_spec=u3s, grid="x -10..442 step 0.25, y -90..90 step 0.5", screen="Unity/Build/FLIP49/diag_DA1/u3/u3_A_T12H7p5_chy40.json")
    ok["A2_bed_vs_u3_lt_1e-9"] = bool(dU < 1e-9)
    e0, e2 = GC.edge_x(sp0), GC.edge_x(spec)
    o.update(edge_x_axis_m=[e0, e2], max_depth_m=[float(-z0.min()), float(-z2.min())], change=dict(SPEC_A2_CHANGE), from_ch_y0=float(sp0["ch_y0"]))
    ok["A2_edge_and_max_depth_as_SC37"] = bool(e0 == e2 and abs(float(z0.min()) - float(z2.min())) < 1e-3)   # 最も深い所はどちらも溝の 25 m（tanh の裾で 1e-7 m 違う）
    o["tags"] = dict(all="計算（numpy）")
    return o, ok


def nf_cost(c):
    """この cfg で計算するコマの数（新しい計算は f_end。続き DA3c は f_resume_est〜f_end）。DA3・DA3c の測った時間からの見込みに使う（AM-A5）"""
    return int(c["f_end"]) - int(c.get("f_resume_est", c.get("f_start", 1))) + 1


def spec_A3():
    """DA3 の海底（AM-A5）：SC37 の ch_y0 だけを 30 m に（DA2 から ch_y0 40 → 30 m の 1 つだけ）。"""
    sp = dict(GC.SPEC_A)
    sp.update(SPEC_A3_CHANGE)
    return sp


def is_spec_A3(spec):
    """spec が DA3 の海底（SC37 と ch_y0 以外は同じ、ch_y0 = 30 m）か。"""
    ref = spec_A3()
    return bool(GC.is_spur_drop(spec) and all((spec.get(k) == v) if not isinstance(v, float) else
                                               (spec.get(k) is not None and abs(float(spec.get(k)) - v) < 1e-12) for k, v in ref.items()))


def checks_A3(spec):
    """DA3 の海底の numpy の確かめ（数秒、AM-A5）。返り値 (記録, ok)。
    (1) 溝が始まる前（x < ch_x0）で SC37・DA2 と 1 bit も違わない (2) どこでも DA2 より浅くならない（違いは溝の項だけ）、DA2 と本当に違う
    (3) 下見（u3_beds.depth、diag_DA2/c1_u3_screen.py の B_y30 と同じ名前）と同じ (4) 軸の縁・最も深い所は SC37・DA2 と同じ。
    DA2 からの変わり（|y| ごとの最大と x 266 m の水深）を記録する（4 Hc ≈ 27 m の内でどれだけ変えたか）。"""
    sp0 = GC.SPEC_A; sp2 = spec_A2()
    o, ok = {}, {}
    xs = np.arange(0.0, 442.0, 0.25); ys = np.arange(-90.0, 90.0001, 0.25)
    X, Y = np.meshgrid(xs, ys)
    z0 = GC.bed_z(X, Y, **sp0); z2 = GC.bed_z(X, Y, **sp2); z3 = GC.bed_z(X, Y, **spec)
    up = xs < float(spec["ch_x0"])
    d2 = z2 - z3
    ok["A3_bed_equals_SC37_and_DA2_before_channels"] = bool(np.array_equal(z0[:, up], z3[:, up]) and np.array_equal(z2[:, up], z3[:, up]))
    ok["A3_bed_never_shallower_than_DA2"] = bool(d2.min() >= -1e-12 and (z0 - z3).min() >= -1e-12)
    ok["A3_bed_differs_from_DA2"] = bool(d2.max() > 1.0)          # ch_y0 が本当に効いている（DA2 のままなら偽）
    o["deeper_than_DA2_max_m_by_abs_y"] = {str(v): float(d2[np.abs(ys) <= v].max()) for v in (10, 15, 20, 22, 25, 27, 30, 33, 35, 40, 85)}
    o["depth_m_x266_SC37_DA2_DA3"] = {str(v): [float(-GC.bed_z(266.0, float(v), **s_)) for s_ in (sp0, sp2, spec)]
                                      for v in (0, 10, 15, 20, 22, 25, 27, 30, 33, 35, 40, 45, 55, 60)}
    U3 = GC.u3_depth_fn()
    Xg, Yg = np.meshgrid(np.arange(-10.0, 442.0001, 0.25), np.arange(-90.0, 90.0001, 0.5))
    u3s = dict(GC.SPEC_A_U3); u3s.update(SPEC_A3_CHANGE)
    dU = float(np.abs(-GC.bed_z(Xg, Yg, **spec) - U3(Xg, Yg, u3s)).max())
    o["vs_u3"] = dict(max_abs_m=dU, u3_spec=u3s, grid="x -10..442 step 0.25, y -90..90 step 0.5", screen="Unity/Build/FLIP49/diag_DA2/u3/u3_B_y30.json")
    ok["A3_bed_vs_u3_lt_1e-9"] = bool(dU < 1e-9)
    e0, e2, e3 = GC.edge_x(sp0), GC.edge_x(sp2), GC.edge_x(spec)
    o.update(edge_x_axis_m=[e0, e2, e3], max_depth_m=[float(-z0.min()), float(-z2.min()), float(-z3.min())], change=dict(SPEC_A3_CHANGE),
             from_ch_y0_DA2=float(sp2["ch_y0"]), from_ch_y0_SC37=float(sp0["ch_y0"]))
    ok["A3_edge_and_max_depth_as_SC37"] = bool(e0 == e2 == e3 and abs(float(z0.min()) - float(z3.min())) < 1e-3)
    o["tags"] = dict(all="計算（numpy）")
    return o, ok


def cost_from_run(run_id, n_new, limit_h, f_end_new, src="DA1"):
    """方案 A の測った記録（DA1。DA3 は DA2：src）の時間から、粒子の数に比例させた見込み（DA2・DA3 の precheck に書く。測った値 × 比）。
    est = 元の chain の経過 × n_new/n_元 × コマ数の比。est_hi = est ＋ 起動のし直しで重ねるコマが毎回いちばん大きい途中保存の間隔（96 コマ）だった時の差。
    鍵の頭は src（DA2 の cfg は前と同じ 'DA1_…'）。n_元 は元の記録の場面の粒子（VEX）の数"""
    rd = os.path.join(GC.B49, "runs", run_id)
    o = dict(run=run_id, limit_h=limit_h, tag="測定（%s の chain.log と periodic_ana.json）× 計算（粒子の比）" % src)
    try:
        lines = open(os.path.join(rd, "chain.log"), encoding="utf8", errors="ignore").read().splitlines()
        pa = json.load(open(os.path.join(rd, "pana", "periodic_ana.json"), encoding="utf8"))
        c0 = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    except Exception as e:
        o["missing"] = repr(e)[:200]
        return o
    chunks, elapsed = [], None
    for ln in lines:
        w = ln.split()
        if " chunk " in ln and "done to" in ln:
            i = w.index("chunk"); j = w.index("to")
            chunks.append((int(w[i + 1]), int(w[j + 1]), float(w[w.index("wall") + 1])))
        if "chain end" in ln and "elapsed_h" in ln:
            elapsed = float(w[w.index("elapsed_h") + 1])
    if not chunks or elapsed is None:
        o["missing"] = "chain.log に起動の行か chain end が無い"
        return o
    nf1 = int(c0["f_end"]); n1 = int(((pa.get("health") or {}).get("particles") or {}).get("first") or 0)
    computed = sum(d - f0 + 1 for f0, d, _ in chunks)
    redo = computed - nf1
    wall = sum(wv for _, _, wv in chunks)
    s_per = wall / max(computed, 1)
    sp_max = max(int(v) for v in c0.get("ckpt_list", [96]))
    worst_redo = (len(chunks) - 1) * sp_max
    ratio = n_new / max(n1, 1)
    est = elapsed * ratio * (f_end_new / nf1)
    est_hi = est + max(0, worst_redo - redo) * s_per * ratio / 3600.0
    meas = dict(elapsed_h=elapsed, launches=len(chunks), frames=nf1, frames_computed=computed, frames_redone=redo,
                s_per_frame_mean=s_per, particles_first=n1, growth=((pa.get("health") or {}).get("particles") or {}).get("growth"))
    o.update({"%s_%s" % (src, k): v for k, v in meas.items()})
    o.update(particle_ratio=ratio, est_h=est, est_hi_h=est_hi, worst_redo_frames=worst_redo)
    return o


def write(c):
    p = os.path.join(GC.B49, c["out_root"], "ready", c["run_id"] + ".json").replace("\\", "/")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return p


def apply_band(c, xg):
    """決まり（S0b の後）：入口の帯を xg（120 m）に 1 回だけ延ばす。波高計 128・146・160 m（18 m の組）、平らの所 130〜160 m、段 C の所 120〜130 m、
    段 A の窓 130〜285 m、段 B の所 20〜(xg − 5) m、静かな水面のずれ 130〜285 m。precheck を作り直す。"""
    xg = float(xg)
    P = c["parms"]
    P.update(xg_end=xg, vol_x0=xg + 10.0, hold_x1=xg - 5.0)
    c["gauges"] = dict(x=[xg + 8.0, xg + 26.0, 160.0] if xg + 26.0 < 160.0 else [xg + 8.0, xg + 26.0, xg + 44.0], y=list(GC.GAUGE_Y))
    lr = []
    for r in GC.LEVEL_REGIONS:
        r = list(r)
        if r[0] == "band_core":
            r[2] = xg - 5.0
        elif r[0] == "probe_c":
            r[1], r[2] = xg, xg + 10.0
        elif r[0] in ("flat", "asym_centre", "asym_side"):
            r[1] = xg + 10.0
        elif r[0] == "window":
            r[1] = xg + 10.0
        lr.append(r)
    c["level_regions"] = lr
    c["n1_x"] = [xg + 10.0, GC.VOL_X[1]]
    c["sf_check"]["x"] = [10.0, 0.35 * xg, 0.7 * xg, xg - 5.0]
    c["run_id"] += "_band%s" % GC.tag(xg)
    c["note"] += "｜入口の帯を %g m に延ばした（S0b の後の決まり、1 回だけ）。波高計 %s m" % (xg, c["gauges"]["x"])
    c["case"]["band_m"] = xg
    c["precheck"] = precheck(c)
    return c


def preset(name, opt):
    cs = _preset(name, opt)
    if opt.get("band") and name in ("S0b", "S1", "S2", "S3", "D0", "D1"):
        cs = [apply_band(c, float(opt["band"])) for c in cs]
    return cs


def _preset(name, opt):
    stage = opt.get("stage", "A")
    g = float(opt["in_gain"]) if opt.get("in_gain") else None
    Hw = float(opt.get("H", GC.H_WAVE))
    hx = "" if abs(Hw - GC.H_WAVE) < 1e-9 else "_H%s" % GC.tag(Hw)
    AX = GC.pg_axis(); FL = GC.flat_spec()
    sx = ("" if stage == "A" else "_st%s" % stage) + hx
    if name == "S0a":
        vx = "_vcol" if (stage in ("A", "B", "none") and GC.VOL_MEASURE == "column") else ""   # 2026-10-15：虫を直した後の S0a は別の名前（前の記録と混ぜない）
        return [make("S0a_still_axis_bands0" + sx + vx, "still_strip", 0.5, GC.W_STRIP, AX, 30.0, stage=stage, case_extra=dict(queue_id="S0a"),
                     records=dict(r2=True, r3_z=None, block=120, preg_every=24, r4=None, r5=None, windows=None),
                     note="FLIP49 S0a：静かな水の軸の板（PG12s の真ん中の断面、半幅 6 m、粒子 0.5 m）。両方の帯を入れ目標 0、段 A。30 s。帯が流れや水面の上下を作らないか")]
    if name == "S0b":
        rid = "S0b_flat_sf12_H7p5" + ("_g%s" % GC.tag(g) if g is not None else "") + sx
        return [make(rid, "flat_strip", 0.5, GC.W_STRIP, FL, 100.0, stage=stage, in_gain=g, case_extra=dict(queue_id="S0b"),
                     records=dict(r2=True, r3_z=None, block=120, preg_every=24, r4=None, r5=None, windows=None),
                     note="FLIP49 S0b：入口の確かめ（平ら 17 m の板、半幅 6 m、粒子 0.5 m）。流れ関数の波 T 12 s・H 7.5 m、in_gain %s、出口の帯 290〜360 m、段 A、100 s"
                          % (g if g is not None else 1.0))]
    if name in ("S1", "S2", "S3"):
        st = {"S1": stage, "S2": "none", "S3": "mode0"}[name]
        rid = {"S1": "S1_axis_PG12s" + sx, "S2": "S2_axis_PG12s_novc", "S3": "S3_axis_PG12s_mode0"}[name]
        rid = rid + hx if name != "S1" else rid
        return [make(rid, "axis_strip", 0.5, GC.W_STRIP, AX, 120.0, stage=st, in_gain=g, H=Hw, case_extra=dict(queue_id=name),
                     records=dict(r2=True, r3_z=None, block=120, preg_every=24, r4=dict(x=[180.0, 300.0], z1=GC.W_STRIP, y0=-10.0, y1=16.0, clip_vox=6.0, t0=24.0),
                                  r5=dict(t0=24.0, every=2), windows=None),
                     note="FLIP49 %s：PG12s の軸の板（横に一様、半幅 6 m、粒子 0.5 m）、流れ関数の波 T 12 s・H 7.5 m、%s、120 s。2D の基準（集まりのない Hc・弦・唇・覆い）"
                          % (name, {"A": "段 A", "B": "段 B", "C": "段 C", "none": "水の量の直しなし（S2）", "mode0": "FLIP47 mode 0（帯を含む水の全部に同じ直し、S3）"}[st]))]
    if name == "D0":
        return [make("D0_PG12s_dp1p0" + sx, "3d", 1.0, GC.W_MAIN, GC.PG12S, T_END_MAIN, stage=stage, in_gain=g, H=Hw, case_extra=dict(queue_id="D0", judged=False),
                     note="FLIP49 D0：3D の下見（粒子 1.0 m、0.45 M）。PG12s・半幅 85 m、流れ関数の波 T 12 s・H 7.5 m、102 s。重い記録も毎コマ。P1〜P5 で判定しない"
                          "（礁の上 1.7 m は 1.7 格子）。巻き始めの時刻が D1 の重い記録の窓を決める")]
    if name in ("D1", "D2"):
        ons, src = (d0_onsets(opt["from"]) if opt.get("from") else (None, "D0 の記録を --from で与えていない"))
        if ons and len([t for t in ons if t >= GC.T_JUDGE - 3.0]) >= 4:
            win = windows_from(ons); wsrc = "D0 の巻き始め（%s）± [−3, +4] s" % src
        else:
            win = windows_from(ONSET_GUESS, HEAVY_WIN_GUESS); wsrc = "下見の見込み 37 + 12k s ± 4 s（%s）" % src
        if name == "D1":
            return [make("D1_PG12s_dp0p5" + sx, "3d", 0.5, GC.W_MAIN, GC.PG12S, T_END_MAIN, stage=stage, in_gain=g, H=Hw, windows=win,
                         case_extra=dict(queue_id="D1", windows_source=wsrc),
                         note="FLIP49 D1：主の粗い周期の 3D（粒子 0.5 m、3.63 M）。PG12s、半幅 85 m、流れ関数の波 T 12 s・H 7.5 m、入口の帯 0〜100 m、出口の帯 290〜360 m、"
                              "%s、102 s。重い記録は崩れごとの窓（%s）" % ({"A": "段 A", "B": "段 B", "C": "段 C"}[stage], wsrc))]
        return [d2(opt, win, wsrc)]
    if name == "D3":
        rd = opt.get("run")
        if not rd or not os.path.exists(os.path.join(rd, "cfg.json")):
            raise SystemExit("D3 は続ける計算の記録を --run で与える（cfg.json がある所）")
        c0 = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        c = copy.deepcopy(c0)
        for k_ in ("hip_sha256", "module_shas_at_chain_start", "precheck"):
            c.pop(k_, None)
        ons, src = d0_onsets(rd)
        last = max([t for t in (ons or [])] or [ONSET_GUESS[5]])
        extra = [last + 12.0 * k for k in range(1, 6)]
        c["f_resume_est"] = int(c0["f_end"]) + 1
        c["f_end"] = GC.frames_for(0.0, T_END_D3); c["t_end_s"] = T_END_D3
        c["records"]["windows"] = (c["records"].get("windows") or []) + windows_from(extra, t_end=T_END_D3, t_min=0.0)
        c["case"]["queue_id"] = "D3"; c["case"]["continuation_of"] = c0["run_id"]
        c["note"] = c0.get("note", "") + "｜D3：同じ設定のまま最後の途中保存から 150 s まで（+48 s = 4 T）。窓を足した（%s の最後の巻き始め %.1f s + 12k s）" % (src, last)
        c["pstats_frames"] = sorted(set(c.get("pstats_frames", []) + [c["f_end"]]))
        c["precheck"] = precheck(c)
        return [c]
    if name == "SMOKE":
        c = make("SMOKE49_PG12s_dp1p0", "smoke", 1.0, GC.W_MAIN, GC.PG12S, 8.0, stage=stage, H=Hw, out_root="smoke",
                 case_extra=dict(queue_id="T0_smoke", judged=False),
                 note="FLIP49 煙の試し（T0 の一部、判定しない）：3D・粒子 1.0 m・PG12s・半幅 85 m（箱は 2 m の格子に丸めて 86 m）・0〜8 s。"
                      "場面・帯の DOP の wrangle・水の量の直しのファイル・記録・sf_check・途中保存からの続き（wall_limit 80 s で起動を 2 回以上に分ける）を"
                      "確かめるだけ。in_gain は仮の 1.0（S0b の前）。8 s では入口の半余弦は E 0.25 までしか上がらない")
        c.update(wall_limit_s=80, max_hours=0.25, ckpt_every=48, ckpt_list=[48, 24, 12])
        c["sf_check"]["every"] = 48
        c["pstats_frames"] = [1, 2, int(c["f_end"])]
        c["precheck"] = precheck(c)
        return [c]
    if name in ("SMOKE_A", "DA1", "DA2", "DA3", "DA3c"):
        return preset_A(name, opt)
    if name == "Z0":
        if int(opt.get("dub", 0)):
            raise SystemExit("du_b（組の下の束縛された長い波）は未実装（Design 3 の式が要る）。Z0 は du_b 無しだけ書ける")
        set_ = dict(set_P=1e9, set_up=12.0, set_flat=36.0, set_down=12.0, set_cg=0.0)
        return [make("Z0_flat_set1_nodub", "flat_strip", 0.5, GC.W_STRIP, FL, 120.0, stage=stage, in_gain=g, extra_parms=set_,
                     case_extra=dict(queue_id="Z0", stage2=True),
                     records=dict(r2=True, r3_z=None, block=120, preg_every=24, r4=None, r5=None, windows=None),
                     note="FLIP49 Z0（2 段目、引き金の後だけ）：平らな板、組 1 つ（上り 12 s・満ち 36 s・下り 12 s）の後 60 s の静けさ、du_b 無し")]
    if name == "PROBE025":
        return [preset_probe025(opt)]
    if name == "DA3r":
        return [preset_DA3r(opt)]
    raise SystemExit("cfg は S0a・S0b・S1・S2・S3・D0・D1・D2・D3・Z0・SMOKE・SMOKE_A・DA1・DA2・DA3・DA3c・PROBE025・DA3r")


def preset_A(name, opt):
    """方案 A（PER49-A、plan_A_frozen.json）の設定。SMOKE_A：3D の煙の試し（粒子 1.0 m、0〜8 s、起動 2 回）。DA1：主の粗い周期の 3D
    （粒子 0.5 m、T 12 s・H 7.5 m、段 C、92 s、重い記録は下見の巻き始め ± [−3, +4] s）。DA2：DA1 から 1 つだけ変えた続き（2026-10-16 AM-A3：溝の壁の真ん中 ch_y0 55 → 40 m。前の予定 T16 H7.0 は書かない）。
    DA3（2026-10-16 AM-A5）：DA2 から 1 つだけ変えた続きの 2 本目（溝の壁の真ん中 ch_y0 40 → 30 m）。--run がある時は前の名前の続き（下の DA3c と同じ）。
    DA3c（AM-A5 で改めた名前）：PERIODIC が通った時の +48 s の続き（140 s）。"""
    stage = opt.get("stage", "C")
    sp = dict(GC.SPEC_A)
    if name == "SMOKE_A":
        c = make("SMOKE49A_SC37_dp1p0", "smoke", 1.0, GC.W_MAIN, sp, 8.0, stage=stage, out_root="smoke", layout="A",
                 case_extra=dict(queue_id="SMOKE_A", judged=False),
                 note="FLIP49 方案 A の煙の試し（判定しない）：3D・粒子 1.0 m・SC37（FLIP48 C3 の海底を +37.25 m、礁の上 20 m の先 1:2 で 6 m）・"
                      "箱 442 × 86 m（2 m の格子に丸め）・底 −25 m・出口の帯 362〜442 m・段 C・0〜8 s。FLIP で初めて通す道（pg_reef の道で溝＋礁湖への下り、"
                      "FLIP49 の水槽で底 −25 m の箱、Lx 442、80 m の出口の帯、新しい所と窓、途中保存からの続き。wall_limit 80 s で起動を 2 回以上に分ける）"
                      "を確かめるだけ。in_gain は仮の 1.0（plan/in_gain.json も 1.0）")
        c.update(wall_limit_s=80, max_hours=0.25, ckpt_every=48, ckpt_list=[48, 24, 12])
        c["sf_check"]["every"] = 48
        c["pstats_frames"] = [1, 2, int(c["f_end"])]
        c["records"]["windows"] = [[2.0, 8.0]]          # 重い記録（R4・R5）の窓の道も通す（短い）
        c["records"]["r4"]["every"] = 2                  # DA1 の逃げ道（重い記録を 1 コマおき）と同じ道を通す
        c["records"]["r5"]["every"] = 2
        c["precheck"] = precheck(c)
        return [c]
    if name == "DA1":
        g = float(opt["in_gain"]) if opt.get("in_gain") else None
        heavy = opt.get("heavy", "cont")
        if heavy not in ("cont", "screen"):
            raise SystemExit("--heavy は cont（既定：47 s〜終わりを 3 コマごと、AM-A2）か screen（下見の巻き始め ± [−3, +4] s の窓）")
        if heavy == "cont":
            win = [[HEAVY_CONT_A["t0"], T_END_A]]
            wsrc = ("続けて %g〜%g s を %d コマごと（R4・R5、AM-A2）。下見（U3）の巻き始め %s s に縛らない：1:10 の緩い軸では FLIP の崩れる所が下見より岸寄りに"
                    "なりうる（FLIP48 R4・C3 は x 326〜353 m）" % (HEAVY_CONT_A["t0"], T_END_A, HEAVY_CONT_A["every"], ONSET_SCREEN_A))
        else:
            win = windows_from(ONSET_SCREEN_A, HEAVY_WIN, t_end=T_END_A)
            wsrc = "下見（U3）の巻き始め %s s ± [−3, +4] s（D0 では FLIP の巻き始めが下見と 1 s 以内）" % ONSET_SCREEN_A
        c = make("DA1_SC37_T12H7p5_dp0p5" + ("" if stage == "C" else "_st%s" % stage), "3d", 0.5, GC.W_MAIN, sp, T_END_A, stage=stage, in_gain=g,
                 windows=win, layout="A", case_extra=dict(queue_id="DA1", windows_source=wsrc, heavy_rule=heavy),
                 note="FLIP49 方案 A DA1：主の粗い周期の 3D（粒子 0.5 m、4.98 M）。SC37、半幅 85 m、箱 442 m・底 −25 m、流れ関数の波 T 12 s・H 7.5 m、"
                      "入口の帯 0〜100 m、出口の帯 362〜442 m（80 m、σ 1.41）、段 %s、%g s。重い記録は %s" % (stage, T_END_A, wsrc))
        if heavy == "cont":
            c["records"]["r4"]["every"] = HEAVY_CONT_A["every"]
            c["records"]["r5"]["every"] = HEAVY_CONT_A["every"]
            c["case"]["amendment"] = "AM-A2 (Unity/Build/FLIP49/plan/amendments.jsonl)"
            c["precheck"] = precheck(c)
            return [c]
        c["records"]["r4"]["every"] = 1
        c["records"]["r5"]["every"] = 1
        c["precheck"] = precheck(c)
        if not c["precheck"]["checks"].get("wall_le_2p5h"):
            hi1 = c["precheck"].get("total_h_hi")
            c["records"]["r4"]["every"] = 2
            c["records"]["r5"]["every"] = 2
            c["note"] += "｜時間の見込みの上 %.2f h が 2.5 h を越えたので、FLIP49 の逃げ道（重い記録を 1 コマおき：R4・R5 の every 2）を当てた" % hi1
            c["case"]["fallback"] = dict(rule="heavy records every 2nd frame (FLIP49 fallback, plan_A_frozen.json design)", total_h_hi_before=hi1)
            c["precheck"] = precheck(c)
        return [c]
    if name == "DA2":
        ch = opt.get("change", "chy40")
        if ch == "T16":
            raise SystemExit("DA2 = T16 H7.0 は書かない（2026-10-16 AM-A3 で ch_y0 40 m を選んだ。T16 は下見で c0/c_side 1.16〜1.29 の見込み = 止める決まり）。"
                             "書くには先に T 16 s の S0b 型の入口の板と、120 m 以上の出口の帯（箱を延ばす並び、σ を選び直す）が要る")
        if ch != "chy40":
            raise SystemExit("DA2 の --change は chy40（既定、AM-A3：溝の壁の真ん中 ch_y0 55 → 40 m）だけ")
        g = float(opt["in_gain"]) if opt.get("in_gain") else None
        sp2 = spec_A2()
        win = [[HEAVY_CONT_A["t0"], T_END_A]]
        wsrc = ("続けて %g〜%g s を %d コマごと（R4・R5、AM-A2 と同じ。DA1 の巻き始め 51.0・62.7・75.0・87.0 s【測定】を全部含む）"
                % (HEAVY_CONT_A["t0"], T_END_A, HEAVY_CONT_A["every"]))
        what = "海底の溝の壁の真ん中 ch_y0 55 → 40 m（ほかは DA1 と同じ：T 12 s・H 7.5 m・in_gain・箱 442 m・出口の帯 362〜442 m・92 s・粒子 0.5 m・段 C）"
        c = make("DA2_SC37y40_T12H7p5_dp0p5" + ("" if stage == "C" else "_st%s" % stage), "3d", 0.5, GC.W_MAIN, sp2, T_END_A, stage=stage, in_gain=g,
                 windows=win, layout="A",
                 case_extra=dict(queue_id="DA2", windows_source=wsrc, heavy_rule="cont", da2_change=what, da2_parent_run=DA1_RUN_A,
                                 da2_why="AM-A3 (Unity/Build/FLIP49/plan/amendments.jsonl); diagnosis Unity/Build/FLIP49/diag_DA1/d6_predict.json",
                                 amendment="AM-A2 (records) + AM-A3 (DA2 change, wall limit 3.0 h) (Unity/Build/FLIP49/plan/amendments.jsonl)"),
                 note="FLIP49 方案 A DA2（AM-A3）：DA1 から 1 つだけ変えた主の粗い周期の 3D（粒子 0.5 m、5.24 M）。%s。重い記録は %s。"
                      "1 本の時間の上限は 3.0 h（粒子 +5.1 %%、AM-A3）、1 回の起動は 29 分以内（DA1 と同じ）" % (what, wsrc))
        c["records"]["r4"]["every"] = HEAVY_CONT_A["every"]
        c["records"]["r5"]["every"] = HEAVY_CONT_A["every"]
        c["limit_h_run"] = LIMIT_3D_H_A2
        c["max_hours"] = LIMIT_3D_H_A2
        c["precheck"] = precheck(c)
        return [c]
    if name == "DA3" and not opt.get("run"):
        # 2026-10-16 AM-A5：DA3 = DA2 から海底の 1 つだけ（溝の壁の真ん中 ch_y0 40 → 30 m）。方案 A の続き 2 本の 2 本目（limits）
        ch = opt.get("change", "chy30")
        if ch == "T16":
            raise SystemExit("DA3 = T16 H7.0 は書かない（2026-10-16 AM-A5 の t16_resolution：下見 × DA1・DA2 の倍率で最も巻いたコマの幅の中央値 2.77 Hc"
                             "（DA2 2.60）・P4b 0/4・P(PERIODIC) 0.02、倍率を弱めない時は c0/c_side 0.96〜1.17 で止める決まりに当たる。"
                             "T 16 s の入口の板・120 m 以上の出口の帯・約 3.2 h も要る）")
        if ch != "chy30":
            raise SystemExit("DA3 の --change は chy30（既定、AM-A5：溝の壁の真ん中 ch_y0 40 → 30 m）だけ。+48 s の続きは cfg DA3c --run=<記録>")
        g = float(opt["in_gain"]) if opt.get("in_gain") else None
        sp3 = spec_A3()
        win = [[HEAVY_CONT_A["t0"], T_END_A]]
        wsrc = ("続けて %g〜%g s を %d コマごと（R4・R5、AM-A2 と同じ。DA2 の巻き始め 50.8・62.4・75.0・86.8 s【測定】を全部含む）"
                % (HEAVY_CONT_A["t0"], T_END_A, HEAVY_CONT_A["every"]))
        what = ("海底の溝の壁の真ん中 ch_y0 40 → 30 m（ほかは DA2 と同じ：ch_w 4・ch_h 25・ch_x0 187.25・ch_lx 40・先細り k 0.35 → 1.0、"
                "T 12 s・H 7.5 m・in_gain・入口の帯・波高計・箱 442 × 85 m・底 −25 m・出口の帯 362〜442 m・92 s・粒子 0.5 m・段 C）")
        c = make("DA3_SC37y30_T12H7p5_dp0p5" + ("" if stage == "C" else "_st%s" % stage), "3d", 0.5, GC.W_MAIN, sp3, T_END_A, stage=stage, in_gain=g,
                 windows=win, layout="A",
                 case_extra=dict(queue_id="DA3", windows_source=wsrc, heavy_rule="cont", da3_change=what, da3_parent_run=DA2_RUN_A,
                                 da3_why=("AM-A5 (Unity/Build/FLIP49/plan/amendments.jsonl); diagnosis Unity/Build/FLIP49/diag_DA2/ "
                                          "(c3_table.json B_y30, b2_recal.json, a1_DA2.json)"),
                                 follow_up="2nd and last of at most 2 follow-up runs in option A (plan_A_frozen.json limits)",
                                 amendment=("AM-A2 (records) + AM-A3 (wall limit 3.0 h, kept for DA3) + AM-A5 (DA3 change; the +48 s continuation renamed DA3c) "
                                            "(Unity/Build/FLIP49/plan/amendments.jsonl)")),
                 note="FLIP49 方案 A DA3（AM-A5）：DA2 から 1 つだけ変えた主の粗い周期の 3D（粒子 0.5 m、5.44 M、方案 A の続き 2 本の 2 本目）。%s。重い記録は %s。"
                      "1 本の時間の上限は 3.0 h（DA2 と同じ）、1 回の起動は 29 分以内（DA1・DA2 と同じ）" % (what, wsrc))
        c["records"]["r4"]["every"] = HEAVY_CONT_A["every"]
        c["records"]["r5"]["every"] = HEAVY_CONT_A["every"]
        c["limit_h_run"] = LIMIT_3D_H_A3
        c["max_hours"] = LIMIT_3D_H_A3
        c["precheck"] = precheck(c)
        return [c]
    if name in ("DA3", "DA3c"):
        # +48 s の続き。AM-A5 で名前を DA3c に改めた。`DA3 --run=…` は前の書き方で、前と 1 byte も違わない cfg を出す（queue_id 'DA3'）
        qid = name
        rd = opt.get("run")
        if not rd or not os.path.exists(os.path.join(rd, "cfg.json")):
            raise SystemExit("DA3 は続ける DA1 の記録を --run で与える（cfg.json がある所）" if qid == "DA3" else
                             "DA3c は続ける方案 A の記録（DA1・DA2・DA3）を --run で与える（cfg.json がある所）")
        c0 = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        if c0.get("layout") != "A":
            raise SystemExit("%s は方案 A の記録（cfg の layout A）だけ" % qid)
        c = copy.deepcopy(c0)
        for k_ in ("hip_sha256", "module_shas_at_chain_start", "precheck"):
            c.pop(k_, None)
        ons, src = d0_onsets(rd)
        last = max([t for t in (ons or [])] or [ONSET_SCREEN_A[-1]])
        extra = [last + 12.0 * k for k in range(1, 5)]
        c["f_resume_est"] = int(c0["f_end"]) + 1
        c["f_end"] = GC.frames_for(0.0, T_END_A3); c["t_end_s"] = T_END_A3
        c["records"]["windows"] = (c["records"].get("windows") or []) + windows_from(extra, t_end=T_END_A3, t_min=0.0)
        c["case"]["queue_id"] = qid; c["case"]["continuation_of"] = c0["run_id"]
        if qid == "DA3c":
            c["case"]["renamed_from"] = "DA3 (plan_A_frozen.json runs; renamed by AM-A5 because DA3 now names the ch_y0 30 run)"
        c["note"] = c0.get("note", "") + "｜%s：同じ設定のまま最後の途中保存から %g s まで（+48 s = 4 T、指導教員の長い動画の頼み Q66）。窓を足した（%s の最後の巻き始め %.1f s + 12k s）" % (
            qid, T_END_A3, src, last)
        c["pstats_frames"] = sorted(set(c.get("pstats_frames", []) + [c["f_end"]]))
        c["precheck"] = precheck(c)
        return [c]
    raise SystemExit("方案 A の cfg は SMOKE_A・DA1・DA2・DA3・DA3c")


def commit_now_gb():
    """Windows の約束の量（commit）の上限と余り、主メモリーの空き（GB）。読めなければ None（ほかの OS など）。"""
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return None
        return dict(total_phys_gb=m.ullTotalPhys / 2**30, avail_phys_gb=m.ullAvailPhys / 2**30, commit_limit_gb=m.ullTotalPageFile / 2**30,
                    commit_avail_gb=m.ullAvailPageFile / 2**30, time=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def preset_probe025(opt):
    """PROBE025（2026-10-16、probe, not a result）：粒子 0.25 m の主メモリー・時間の短い試し。DA3（海底 SC37 ch_y0 30 m・T 12 s・H 7.5 m・段 C・
    in_gain・入口の帯・出口の帯・箱 442 m・底 −25 m）と同じで、半幅だけ W（既定 24 m）に狭め、終わりを t_end（既定 4 s、6 s まで）にする。
    重い記録（R4・R5）は PROBE_HEAVY の窓で毎コマ（本番の 3 コマごとの 1 コマの時間を測るため）。途中保存は 24 コマごと（大きさと書く時間を測る）。
    置き場所は Build/FLIP49/probe/（runs に混ぜない）。判定しない。細かい粒子の本番は指導教員の返事の後（Q57・Q64）。"""
    W = float(opt.get("W", PROBE_W))
    t_end = float(opt.get("t_end", PROBE_T_END))
    wl = float(opt.get("wall", 1740))
    if t_end > PROBE_T_END_MAX + 1e-9:
        raise SystemExit("PROBE025 の t_end は %g s まで（probe の決まり。長い計算は指導教員の返事の後）" % PROBE_T_END_MAX)
    sp3 = spec_A3()
    win = [[round(PROBE_HEAVY[0], 6), PROBE_HEAVY[1]]]
    c = make("PROBE025_DA3_W%s_dp0p25" % GC.tag(W), "3d", PROBE_DP, W, sp3, t_end, stage="C", windows=win, layout="A", out_root="probe",
             case_extra=dict(queue_id="PROBE025", judged=False, label="probe, not a result", parent=DA3_RUN_A,
                             probe_change="particle 0.5 -> 0.25 m (grid 1.0 -> 0.5 m); half width 85 -> %g m; t_end 92 -> %g s; heavy records every frame in %s s"
                                          % (W, t_end, win[0]),
                             probe_why=("memory/time probe for a 0.25 m run (Q57: formal fine runs wait for the supervisor). Width cut so the probe fits "
                                        "the commit headroom of this PC (commit limit 64.8 GB = RAM 63.8 GB + 1 GB page file)")),
             note="FLIP49 PROBE025（probe, not a result）：粒子 0.25 m（格子 0.5 m）の主メモリー・時間の短い試し。DA3 と同じ海底（SC37、溝の壁の真ん中 ch_y0 30 m）・"
                  "流れ関数の波 T 12 s・H 7.5 m・段 C・入口の帯 0〜100 m・出口の帯 362〜442 m・箱 442 m・底 −25 m で、半幅だけ %g m（DA3 は 85 m）、0〜%g s。"
                  "重い記録は %s s を毎コマ。判定しない。波の形の結果ではない" % (W, t_end, win[0]))
    c["records"]["r4"]["every"] = 1
    c["records"]["r5"]["every"] = 1
    c.update(wall_limit_s=min(wl, 1740.0), max_hours=0.5, ckpt_every=24, ckpt_list=[24, 12, 6])
    c["sf_check"]["every"] = 48
    c["pstats_frames"] = [1, 2, int(c["f_end"])]
    c["precheck"] = precheck(c)
    pc = c["precheck"]
    P = c["parms"]
    n = int(pc["particles_model"])
    ck = pc["checks"]
    ck["PROBE_dp_0p25_grid_0p5_binary_exact"] = bool(float(P["dp"]) == PROBE_DP and GC.is_binary_exact(float(P["dp"]))
                                                    and float(P["dp"]) * float(P["gridscale"]) == 0.5)
    ck["PROBE_short"] = bool(c["t_end_s"] <= PROBE_T_END_MAX + 1e-9 and int(c["f_end"]) <= GC.frames_for(0.0, PROBE_T_END_MAX))
    ck["PROBE_one_launch_le_29min"] = bool(float(c["wall_limit_s"]) <= 1740.0 and float(c["max_hours"]) <= 0.5)
    ck["PROBE_not_judged_own_folder"] = bool(c["out_root"] == "probe" and c["case"].get("judged") is False)
    ck["PROBE_bed_is_DA3"] = bool(is_spec_A3(GC.bed_spec(c)))
    if W in EXPECT_PARTICLES_PROBE:
        ck["PROBE_particles_as_computed"] = bool(n == EXPECT_PARTICLES_PROBE[W])
    # 主メモリーの見込み（DA3 の 1 粒子あたりの最大 RSS × 粒子の増え 1.155【測定、DA3 の 5.44 → 6.28 M】）と、書く時の約束の量の余り
    gr = DA3_PARTICLES_MAX / float(EXPECT_PARTICLES_A3[0.5])
    rss_est = DA3_RSS_PEAK_GB / DA3_PARTICLES_MAX * n * gr
    rule = "DA3 peak RSS %.2f GB / %d particles x model particles x growth %.3f [inferred]" % (DA3_RSS_PEAK_GB, DA3_PARTICLES_MAX, gr)
    if opt.get("rss_from"):
        # 前の PROBE025 の測った約束の量（memwatch）の最大と、準 2D の板（S0a：0.23 M 粒子・4.7 GB）を結ぶ 1 次で見込む【推測】
        rf = opt["rss_from"]
        m0 = json.loads(open(os.path.join(rf, "memwatch_summary.jsonl"), encoding="utf8").readline())
        r0 = json.load(open(os.path.join(rf, "run_c00001.json"), encoding="utf8"))
        p0, n0 = float(m0["private_gb"]), float(r0["particles_max"])
        slope = (p0 - 4.7) / ((n0 - 0.23e6) / 1e6)
        rss_est = p0 + slope * (n - n0) / 1e6
        rule = ("measured probe %s: private %.2f GB at %d particles; line through the 0.5 m strip S0a (0.23 M, 4.7 GB): %.3f GB per M particles [inferred]"
                % (os.path.basename(rf.rstrip("/\\")), p0, n0, slope))
    mem = commit_now_gb()
    pc["probe"] = dict(label="probe, not a result", particles_model=n, particles_full_width_dp0p25=EXPECT_PARTICLES_PROBE[85.0],
                       rss_est_gb=rss_est, rss_est_rule=rule, memory_at_write=mem, heavy_window_s=win[0],
                       tags=dict(particles="計算", rss_est="推測（DA3 の測定から比例）", memory_at_write="測定（GlobalMemoryStatusEx）"))
    if mem:
        ck["PROBE_rss_est_plus_3GB_le_commit_avail"] = bool(rss_est + 3.0 <= mem["commit_avail_gb"])
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "外れ：" + ", ".join(k for k, v in ck.items() if not v)
    return c


def da3r_still_offset(rd0, f_from):
    """DA3 の続きの起動が使った静かな水面のずれ（g49_run.py が run_c*.json から引き継ぐ値と同じ物。面の記録の頭に書く値）。返り値 (値, 出どころ)。"""
    best = None
    for p in sorted(glob.glob(os.path.join(rd0, "run_c*.json"))):
        r = json.load(open(p, encoding="utf8"))
        so = (r.get("still_offset") or {})
        if so.get("value") is not None and int(r.get("f_start") or 0) <= f_from:
            best = (float(so["value"]), "%s (%s)" % (os.path.basename(p), so.get("source")))
    return best if best else (None, "DA3 の run_c*.json に still_offset がない")


def da3r_cost(rd0, f_from, f_end, wall_limit, sp, launch_extra_s=2.0):
    """DA3 の測った 1 コマの時間（r6 の wall、同じコマが 2 つの起動にあれば後の物）＋ 面の書き出し（DA3 の surf_s の中央値）を毎コマ
    ＋ 1 コマのほかの手間（起動の全部の時間 − 解く時間 − 面の時間）で、起動の区切りを g49_chain.py と g49_run.py の決まりどおりに数える
    （起動は wall_limit を越えたコマの後で止まる。次の起動は sp の倍数の最後の途中保存の次のコマから）。【測定 × 計算】"""
    sim, surf, other = {}, [], []
    for p in sorted(glob.glob(os.path.join(rd0, "r6_c*.npz"))):
        c_ = int(os.path.basename(p)[4:9])
        rp = os.path.join(rd0, "run_c%05d.json" % c_)
        if not os.path.exists(rp):
            continue
        r = json.load(open(rp, encoding="utf8"))
        d = np.load(p)
        fr, w, s = d["frames"], d["wall"], d["surf_s"]
        if not ((fr >= f_from) & (fr <= f_end)).any():
            continue
        for f_, w_ in zip(fr, w):
            sim[int(f_)] = float(w_)
        surf += [float(v) for v in s if v > 0]
        other.append((float(r["wall_total_s"]) - float(w.sum()) - float(s.sum())) / max(len(fr), 1))
    need = list(range(f_from, f_end + 1))
    if not surf or any(f_ not in sim for f_ in need):
        return dict(missing="DA3 の r6 に %d〜%d コマの時間がない" % (f_from, f_end))
    s_surf = float(np.median(surf)); s_other = float(np.mean(other))
    cost = {f_: sim[f_] + s_surf + s_other for f_ in need}
    launches, f0 = [], f_from
    for _ in range(20):
        t, f_ = launch_extra_s, f0
        while f_ <= f_end:
            t += cost[f_]
            if t > wall_limit:
                break
            f_ += 1
        done = min(f_, f_end)
        launches.append(dict(f_start=f0, f_done=done, est_s=round(t, 1)))
        if done >= f_end:
            break
        ck = (done // sp) * sp
        if ck + 1 <= f0:
            return dict(missing="途中保存の間隔 %d では起動 1 回で次の途中保存に届かない" % sp, launches=launches)
        f0 = ck + 1
    tot = sum(L_["est_s"] for L_ in launches)
    return dict(s_per_frame_mean=float(np.mean(list(cost.values()))), s_sim_mean=float(np.mean([sim[f_] for f_ in need])), s_surf=s_surf, s_other=s_other,
                launch_extra_s=launch_extra_s, launches=launches, n_launches=len(launches), total_h=tot / 3600.0,
                frames_redone=sum(L_["f_done"] - L_["f_start"] + 1 for L_ in launches) - len(need),
                tag="測定（DA3 の r6_c*.npz・run_c*.json）× 計算（起動の区切り）")


def preset_DA3r(opt):
    """DA3r（2026-10-16）：DA3 の途中保存 v.<ckpt>.sim（既定 1824 = 75.958 s）から、DA3 と同じ設定（DA3R_PHYS_KEYS が 1 つも違わない）のまま、
    新しい記録の置き場所 runs/<run_id>/ で t_end（既定 90 s、89.5〜92 s）まで計算し直し、面（R5）と R4 を毎コマ書く（hf・r2・r3 は前から毎コマ）。
    走らせる前に `py -3.10 -B g49_restart.py seed <cfg>` が途中保存と水の量の直しの状態（volcorr）を写す。DA3 の置き場所には書かない。
    走った後に `g49_restart.py compare <cfg>` が DA3 の 3 コマおきの記録と同じコマで比べる（同じに戻るかの確かめ）。
    --ckpt=<コマ>：別の途中保存（窓の始め以前の物だけ ok）。--t_end=<s>：終わり。--wall=<s>：1 回の起動の上限（既定 1700 s、1740 s まで）。"""
    rd0 = os.path.join(GC.B49, "runs", DA3_RUN_A)
    full = bool(opt.get("full"))
    t_end = float(opt.get("t_end", DA3R_T_END))
    t_max = DA3R_FULL_T_END_MAX if full else DA3R_T_END_MAX
    if not (DA3R_T_END_MIN - 1e-9 <= t_end <= t_max + 1e-9):
        raise SystemExit("DA3r の t_end は %g〜%g s（1 周期 ＋ 余り、DA3 の面の記録が続けてある所まで。--full は DA3 の続きの終わりまで）" % (DA3R_T_END_MIN, t_max))
    k = int(opt.get("ckpt", DA3R_CKPT))
    ck_every = DA3R_FULL_CKPT_EVERY if full else DA3R_CKPT_EVERY
    max_h = DA3R_FULL_MAX_H if full else DA3R_MAX_H
    wl = float(opt.get("wall", 1700.0))
    c0 = json.load(open(os.path.join(rd0, "cfg.json"), encoding="utf8"))
    c = copy.deepcopy(c0)
    for k_ in ("hip_sha256", "module_shas_at_chain_start", "precheck", "f_resume_est"):
        c.pop(k_, None)
    f_from = k + 1
    f_end = int(GC.frames_for(0.0, t_end))
    t_from = (f_from - 1) / 24.0
    rid = "DA3r_SC37y30_T12H7p5_dp0p5_c%04d_t%s" % (k, GC.tag(t_end)) + ("_full" if full else "")
    off, off_src = da3r_still_offset(rd0, f_from)
    ck_src = os.path.join(rd0, "ckpt", "v.%04d.sim" % k).replace("\\", "/")
    c.update(run_id=rid, out_root="runs", f_start=f_from, f_first=f_from, f_end=f_end, t_end_s=t_end, still_offset_m=off,
             ckpt_on=1, ckpt_every=ck_every, ckpt_list=[ck_every, ck_every // 2], wall_limit_s=min(wl, 1740.0),
             max_hours=max_h, limit_h_run=max_h, pstats_frames=[f_from, f_end])
    c["records"]["r4"]["every"] = 1
    c["records"]["r5"]["every"] = 1
    c["records"]["windows"] = [[t_from, t_end]]
    case = c["case"]
    for k_ in ("continuation_of", "renamed_from", "windows_source", "heavy_rule", "follow_up"):
        case.pop(k_, None)
    case.update(queue_id="DA3r", judged=False, label="re-record of DA3 for playback: same physics, every-frame surface records",
                restart_of=DA3_RUN_A, restart_ckpt_frame=k, windows_source="every frame %d-%d (R4, R5; hf, r2, r3 as DA3)" % (f_from, f_end),
                why="DA3 R5 exists only every 3rd frame (8 records/s), so the FLIP3D loop playback steps (Docs/Progress/FLIP3D_Playback_ja.md 5, 6)")
    c["restart"] = dict(src_run=DA3_RUN_A, src_dir=rd0.replace("\\", "/"), ckpt_frame=k, ckpt_t_s=(k - 1) / 24.0, ckpt_file=ck_src,
                        ckpt_bytes=os.path.getsize(ck_src) if os.path.exists(ck_src) else None, loop_window_s=list(DA3R_LOOP_S),
                        still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip49/g49_restart.py seed <cfg>: copies v.%04d.sim, volcorr/ref.json, volcorr/state.jsonl rows f <= %d, "
                             "volcorr/vd_%05d.txt and vd_%05d.txt into the new run folder (DA3 folder is read only)" % (k, k, k, k + 1),
                        compare="py -3.10 -B Tools/GWWaveGen/flip49/g49_restart.py compare <cfg>")
    c["note"] = ("FLIP49 DA3r（2026-10-16、FLIP3D の再生のための記録し直し、判定しない）：DA3 の途中保存 v.%04d（%.3f s）から、DA3 と同じ設定のまま "
                 "%.3f〜%g s（コマ %d〜%d）を計算し直し、面（R5）と R4 を毎コマ書く（DA3 は 3 コマおき）。新しい置き場所 runs/%s。形は変えない（物理だけ）。"
                 "1 回の起動は %.0f s 以内、途中保存は %d コマごと" % (k, (k - 1) / 24.0, t_from, t_end, f_from, f_end, rid, c["wall_limit_s"], DA3R_CKPT_EVERY))
    pc = precheck(c)
    ck = pc["checks"]
    others = [os.path.getsize(p) for p in glob.glob(os.path.join(rd0, "ckpt", "v.*.sim"))]
    ck["DA3r_ckpt_exists_full_size"] = bool(os.path.exists(ck_src) and others and os.path.getsize(ck_src) >= 0.5 * float(np.median(others)))
    f_loop = int(GC.frames_for(0.0, DA3R_LOOP_S[0]))
    ck["DA3r_ckpt_le_loop_start"] = bool(k <= f_loop - 1)
    if full:                          # --full：繰り返しの窓ではなく、判定した崩れ k2〜k9（巻き始め 50.79〜134.42 s）の全部を毎コマ
        case.update(label="re-record of DA3 for continuous playback (no loop): same physics, every-frame surface records",
                    why="user 2026-10-16: re-record 50-135 s (8 breakers) every frame and play continuously in Unity without looping (no seam)")
    launch_cfgs = sorted(glob.glob(os.path.join(rd0, "cfg_c*.json")))
    same = []
    for p in [os.path.join(rd0, "cfg.json")] + launch_cfgs:
        q = json.load(open(p, encoding="utf8"))
        same.append(all(q.get(kk) == c.get(kk) for kk in DA3R_PHYS_KEYS))
    ck["DA3r_physics_same_as_DA3_all_launches"] = bool(same and all(same))
    hip_now = GC.sha256_file(GC.HIP)
    ck["DA3r_hip_same_as_DA3"] = bool(hip_now == c0.get("hip_sha256"))
    m_now, m_da3 = GC.module_shas(), (c0.get("module_shas_at_chain_start") or {})
    ck["DA3r_runtime_modules_same_as_DA3"] = bool(all(m_now.get(kk) == m_da3.get(kk) and m_now.get(kk) for kk in DA3R_RUNTIME_MODULES))
    out_dir = os.path.abspath(os.path.join(GC.B49, c["out_root"], rid)).replace("\\", "/").lower()
    ck["DA3r_new_folder_not_DA3"] = bool(rid != DA3_RUN_A and out_dir != os.path.abspath(rd0).replace("\\", "/").lower())
    ck["DA3r_records_every_frame"] = bool(int(c["records"]["r5"]["every"]) == 1 and int(c["records"]["r4"]["every"]) == 1
                                          and heavy_frames(c, f_from) == f_end - f_from + 1)
    ck["DA3r_t_end_covers_loop"] = bool(t_end >= DA3R_T_END_MIN - 1e-9 and t_end >= DA3R_LOOP_S[1] + 0.25 - 1e-9)
    ck["DA3r_one_launch_le_29min"] = bool(float(c["wall_limit_s"]) <= 1740.0)
    ck["DA3r_still_offset_from_DA3"] = bool(off is not None)
    vdir = os.path.join(rd0, "volcorr")
    rows = set()
    if os.path.exists(os.path.join(vdir, "state.jsonl")):
        for ln in open(os.path.join(vdir, "state.jsonl"), encoding="utf8"):
            try:
                rows.add(int(json.loads(ln)["f"]))
            except Exception:
                pass
    nT = int(round(GC.T_WAVE * 24))
    ck["DA3r_volcorr_state_ready"] = bool(os.path.exists(os.path.join(vdir, "ref.json")) and os.path.exists(os.path.join(vdir, "vd_%05d.txt" % f_from))
                                          and all(f_ in rows for f_ in range(k - nT + 1, k + 1)))
    est = da3r_cost(rd0, f_from, f_end, float(c["wall_limit_s"]), ck_every)
    pc["DA3r"] = dict(cost_measured=est, hip_sha256=hip_now, runtime_modules=list(DA3R_RUNTIME_MODULES), physics_keys=list(DA3R_PHYS_KEYS),
                      launch_cfgs_compared=[os.path.basename(p) for p in launch_cfgs], loop_frames=[f_loop, int(GC.frames_for(0.0, DA3R_LOOP_S[1]))],
                      tags=dict(cost_measured="測定 × 計算", physics="DA3 の cfg と同じ（確かめ）"))
    ck["DA3r_measured_est_le_max_hours"] = bool(est.get("total_h") is not None and est["total_h"] <= max_h)
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "外れ：" + ", ".join(kk for kk, v in ck.items() if not v)
    c["precheck"] = pc
    return c


def d2(opt, win, wsrc):
    r = opt.get("rule")
    sp = dict(GC.PG12S); H = GC.H_WAVE; stage = opt.get("stage", "A"); zb = GC.Z_BOTTOM; Lx = GC.LX; ex = {}
    what = ""
    if r == "a":
        stage = opt.get("stage") or "B"
        if stage not in ("B", "C"):
            raise SystemExit("決まり (a) は次の段 B か C（--stage）")
        what = "段 %s（帯の水面を保つ）" % stage
    elif r == "b":
        H = 6.5; what = "H 6.5 m（頂 ≈ 4.4 m）"
    elif r == "c":
        H = 8.5; what = "H 8.5 m（頂 ≈ 6.05 m）。先に S1 型の板を 1 本"
    elif r == "d":
        sp.update(ch_h=25.0, ch_y0=55.0, ch_w=4.0, ch_x0=150.0, ch_lx=40.0); zb = G48.ZB_DEEP
        what = "R4 の横の深い溝 25 m（箱の底 −25 m）。横の基準を下げることを書く"
    elif r == "e":
        e = opt.get("e")
        if e == "b18":
            sp.update(b_end=18.0); what = "頂の平ら b_end 18 m（等深線が ±2 Hc までまっすぐ）"
        elif e == "hr12":
            sp.update(shelf_h=1.2); what = "礁の上の水深 h_r 1.2 m"
        else:
            raise SystemExit("決まり (e) は --e=b18（横から来る水の割合 ≥ 70 %）か --e=hr12")
    elif r == "f":
        sp.update(x_toe=220.25, xb1=240.0, xb2=270.0, xk1=240.0, xk2=296.0, x_back=316.0); Lx = 400.0
        ex = dict(xa0=330.0, vol_x1=325.0, crop_x1=400.0)
        what = "ずらさない Lx 400 m の形（縁 x 296 m、出口の帯 330〜400 m、P1 の上限 325 m）"
    else:
        raise SystemExit("D2 の決まりは a〜f")
    rid = "D2%s_PG12s_dp0p5" % r + ("_%s" % opt.get("e") if r == "e" else "") + ("_st%s" % stage if stage != "A" else "")
    c = make(rid, "3d", 0.5, GC.W_MAIN, sp, T_END_MAIN, stage=stage, in_gain=(float(opt["in_gain"]) if opt.get("in_gain") else None), H=H,
             windows=win, zb=zb, Lx=Lx, extra_parms=ex, case_extra=dict(queue_id="D2" + r, d2_rule=r, d2_change=what, windows_source=wsrc,
                                                                        P1_x_max_m=(325.0 if r == "f" else GC.X_P1_MAX)),
             note="FLIP49 D2 決まり (%s)：D1 から 1 つだけ変えた：%s" % (r, what))
    if r == "f":
        c["records"]["r4"]["x"] = [220.0, 340.0]
        c["precheck"] = precheck(c)
    return c


# ====================================================================== S0b の門 → in_gain
def gain(run_dir):
    p = os.path.join(run_dir, "pana", "inlet.json")
    if not os.path.exists(p):
        raise SystemExit("S0b の入口の読み %s がない（先に py -3.10 -B g49_periodic_ana.py inlet %s）" % (p, run_dir))
    a = json.load(open(p, encoding="utf8"))
    plan = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))
    gt = plan["criteria"]["strip_gates"]["S0b"]
    cfg = json.load(open(os.path.join(run_dir, "cfg.json"), encoding="utf8"))
    g_used = float(cfg["parms"]["in_gain"])
    Hm = a.get("H_mean_m"); cm = a.get("c_mps"); cv = a.get("H_cv_x128"); kr = a.get("Kr"); dr = a.get("band_core_drift_6T_m")
    J = dict(H=bool(Hm is not None and abs(Hm / GC.H_WAVE - 1) <= gt["H_rel"]), c=bool(cm is not None and abs(cm / a["c_target_mps"] - 1) <= gt["c_rel"]),
             cv=bool(cv is not None and cv <= gt["H_cv_max_at_128"]), Kr=bool(kr is not None and kr <= gt["Kr_max"]),
             drift=bool(dr is not None and abs(dr) <= gt["band_drift_max_m_6T"]))
    out = dict(run=os.path.basename(run_dir.rstrip("/\\")), in_gain_used=g_used, H_mean_m=Hm, c_mps=cm, H_cv_x128=cv, Kr=kr, band_core_drift_6T_m=dr, judge=J)
    if all(J.values()):
        g = dict(in_gain=g_used, source_run=out["run"], date=time.strftime("%Y-%m-%d %H:%M:%S"), gate=J, values=out, tag="測定（S0b の門を通った）")
        json.dump(g, open(GC.PLAN_DIR + "/in_gain.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
        out["next"] = "plan/in_gain.json を書いた（in_gain %.4f）。S1 へ" % g_used
    elif not J["H"] and abs(g_used - 1.0) < 1e-12:
        out["next"] = "H が 5 %% より外れ：py -3.10 -B g49_pcfg.py cfg S0b --in_gain=%.4f（7.5/H_meas × 1.0、1 回だけ）" % (GC.H_WAVE / Hm)
    elif not (J["c"] and J["Kr"]) or not J["H"]:
        out["next"] = "まだ外れ（c・Kr・H）：帯を 120 m に 1 回だけ延ばす（決まり。xg_end 120、平らは 60 m）。それでも外れなら入口を失敗として報告"
    else:
        out["next"] = "H・c・Kr は通ったが CV か帯の水面が外れ：段の決まり（S1 の後の (1)）で扱う。報告に書く"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ====================================================================== 確かめ（numpy）
def checks():
    t_start = time.time()
    out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="g49_pcfg.py check")
    ok = {}
    # (1) 既存の海底が 1 bit も違わない（R0・R1・R2b・R3・R4・C3 の cfg）
    rng = np.random.default_rng(4901)
    X = np.concatenate([rng.uniform(-20.0, 420.0, 300000), np.arange(0.0, 360.0001, 0.25)])
    Y = np.concatenate([rng.uniform(-100.0, 120.0, 300000), np.zeros(1441)])
    ex = {}
    for rid in ("R0_strip_RS_A0p3", "R1_RS_k0p35_A0p3_W85", "R2b_RS_k0p5_A0p3_W85", "R3_TSC_k0p35_A0p3_b0p12_W85", "R4_TSC_k0p35_A0p3_b0p18_W85",
                "C3_TSC_k0p35_A0p35_b0p18_W85"):
        p = os.path.join(G48.B48, "runs", rid, "cfg.json")
        if not os.path.exists(p):
            ex[rid] = dict(missing=p); continue
        cfg = json.load(open(p, encoding="utf8"))
        r = {}
        for src, s49, s48 in (("cfg_bed", GC.bed_spec(cfg), G48.bed_spec(cfg)), ("cfg_parms_ctrl", GC.bed_spec(parms=cfg["parms"]), G48.bed_spec(parms=cfg["parms"]))):
            z0 = G48.bed_z(X, Y, **s48); z1 = GC.bed_z(X, Y, **s49)
            g0 = G48.bed_grad(X, Y, **s48); g1 = GC.bed_grad(X, Y, **s49)
            r[src] = dict(bit_equal=bool(np.array_equal(z0, z1) and np.array_equal(g0[0], g1[0]) and np.array_equal(g0[1], g1[1])),
                          is_new=GC.is_new(s49), kind=GC.bed_kind(s49))
            assert r[src]["bit_equal"] and not r[src]["is_new"], "既存の海底 %s（%s）が g48 と 1 bit 違う" % (rid, src)
        ex[rid] = r
    out["existing_beds_bit_exact"] = ex
    ok["existing_beds_bit_exact"] = bool(ex and not any("missing" in v for v in ex.values()))
    # (2) PG12s と U3
    U3 = GC.u3_depth_fn()
    Xg, Yg = np.meshgrid(np.arange(-10.0, 400.0001, 0.1), np.arange(-90.0, 90.0001, 0.25))
    dmax = float(np.abs(-GC.bed_z(Xg, Yg, **GC.PG12S) - U3(Xg, Yg, GC.PG12S_U3)).max())
    out["pg12s_vs_u3"] = dict(max_abs_m=dmax, grid="x -10..400 step 0.1, y -90..90 step 0.25")
    ok["pg12s_vs_u3_lt_1e-9"] = dmax < 1e-9
    # (3) 勾配（数値の差。折れの近くを除く）：PG12s・軸の板・溝つき（決まり d）・b_end 18・h_r 1.2（決まり e）・ずらさない形（決まり f）
    grads = {}
    h = 1e-5
    variants = dict(PG12s=GC.PG12S, axis=GC.pg_axis(), rule_d=dict(GC.PG12S, ch_h=25.0), rule_e_b18=dict(GC.PG12S, b_end=18.0),
                    rule_e_hr12=dict(GC.PG12S, shelf_h=1.2), rule_f=dict(GC.PG12S, x_toe=220.25, xb1=240.0, xb2=270.0, xk1=240.0, xk2=296.0, x_back=316.0))
    for nm, sp in variants.items():
        Xr = rng.uniform(150, 390, 40000); Yr = rng.uniform(-88, 88, 40000)
        gx, gy = GC.bed_grad(Xr, Yr, **sp)
        ngx = (GC.bed_z(Xr + h, Yr, **sp) - GC.bed_z(Xr - h, Yr, **sp)) / (2 * h); ngy = (GC.bed_z(Xr, Yr + h, **sp) - GC.bed_z(Xr, Yr - h, **sp)) / (2 * h)
        err = np.maximum(np.abs(gx - ngx), np.abs(gy - ngy))
        grads[nm] = dict(max=float(err.max()), n_gt_1em5=int((err > 1e-5).sum()), n=len(Xr), even_in_y=float(np.abs(GC.bed_z(Xr, Yr, **sp) - GC.bed_z(Xr, -Yr, **sp)).max()))
    out["bed_grad_fd"] = grads
    ok["bed_grad_fd"] = all(v["n_gt_1em5"] <= 2 and v["even_in_y"] < 1e-12 for v in grads.values())
    # (4) 崩す所の形（|y| = 1.5 Hc、Hc 9.6 m の等深線のずれ）を下見の json と比べる
    xs = np.arange(150.0, 400.0, 0.05)
    geo = {}
    for dd in (3.0, 6.0, 8.0, 10.0):
        def xd(yy):
            d = -GC.bed_z(xs, np.full_like(xs, yy), **GC.PG12S)
            i = np.where(d <= dd)[0]
            return float(xs[i[0]]) if len(i) else float("nan")
        geo["dx_d%gm_y1.5Hc" % dd] = xd(1.5 * 9.6) - xd(0.0)
        geo["x_d%gm_axis" % dd] = xd(0.0)
    geo["x_edge"] = GC.edge_x(GC.PG12S); geo["x_foot_12m"] = GC.foot_x(GC.PG12S)
    scr = os.path.join(GC.SCRATCH_U4, GC.SCREEN_JSON[0])
    if not os.path.exists(scr):
        scr = os.path.join(GC.PLAN_DIR, "screening", GC.SCREEN_JSON[0])
    if os.path.exists(scr):
        sj = json.load(open(scr, encoding="utf8"))
        geo["screening_geom"] = {k: sj["geom"].get(k) for k in ("x_edge", "dx_d3m_y1.5Hc", "dx_d6m_y1.5Hc", "dx_d8m_y1.5Hc", "dx_d10m_y1.5Hc")}
        geo["screening_bed_matches"] = bool(all(abs(float(sj["bed"][k]) - float(GC.PG12S_U3[k])) < 1e-12 for k in GC.PG12S_U3 if k in sj["bed"]))
        geo["match_screening"] = bool(abs(geo["x_edge"] - sj["geom"]["x_edge"]) < 0.06 and all(abs(geo["dx_d%gm_y1.5Hc" % dd] - sj["geom"]["dx_d%gm_y1.5Hc" % dd]) < 0.06 for dd in (3.0, 6.0, 8.0, 10.0)))
        ok["contours_match_screening"] = bool(geo["match_screening"] and geo["screening_bed_matches"])
    out["break_geometry"] = geo
    # (5) 流れ関数の波と、その numpy の目標（VEX の写し）が g47_sfwave と同じか
    s_, sfT = GC.sf_solve()
    SFW = GC.sfwave_mod()
    xq = np.linspace(0, 300, 41); tq = np.linspace(0, 12, 7)
    XX, TT = np.meshgrid(xq, tq)
    e1 = GC.sf_target(XX, -5.0, TT, sfT, dict(x_p=GC.X_P), E=1.0)[3]
    e2 = SFW.eta(s_, (XX - GC.X_P).ravel(), TT.ravel()).reshape(XX.shape)
    yq = np.minimum(-5.0, e2)
    u1_, w1_ = GC.sf_vel(GC.sf_from_table(sfT), (XX - GC.X_P).ravel(), yq.ravel(), TT.ravel())
    u2_, w2_ = SFW.vel(s_, (XX - GC.X_P).ravel(), yq.ravel(), TT.ravel())
    vel_copy_diff = float(max(np.abs(u1_ - u2_).max(), np.abs(w1_ - w2_).max()))
    bc = SFW._bc_residuals(s_)
    out["sf"] = dict(L=sfT["L"], c=sfT["c"], eta_crest=sfT["eta_crest"], eta_trough=sfT["eta_trough"], u1=sfT["u1_mean_current"], ursell=sfT["ursell"],
                     H_over_Hmax=sfT["H_over_Hmax"], residual_max=sfT["residual_max"], bc_residuals=bc, target_eta_vs_g47_max=float(np.abs(e1 - e2).max()), sf_vel_copy_vs_g47_max=vel_copy_diff,
                     design=dict(L=148.6, c=12.39, eta_crest=5.17, eta_trough=-2.33, u1=-0.29, ursell=34, H_over_Hmax=0.64))
    ok["sf_values_match_design"] = bool(abs(sfT["L"] - 148.6) < 0.05 and abs(sfT["c"] - 12.39) < 0.01 and abs(sfT["eta_crest"] - 5.17) < 0.01
                                        and abs(sfT["eta_trough"] + 2.33) < 0.01 and abs(sfT["u1_mean_current"] + 0.29) < 0.01 and np.abs(e1 - e2).max() < 1e-12
                                        and vel_copy_diff < 1e-12)
    # (6) 物の数：Iribarren・横の揺れの向き・静振の周期（Merian）
    L0 = GC.G * GC.T_WAVE ** 2 / (2 * math.pi)
    k_lin = SFW.k_lin(GC.T_WAVE, GC.H0); L_lin = 2 * math.pi / k_lin
    out["numbers"] = dict(L0_deep_m=L0, iribarren_1_10=0.1 / math.sqrt(GC.H_WAVE / L0), iribarren_1_2p5=0.4 / math.sqrt(GC.H_WAVE / L0),
                          L_lin_T12_m=L_lin, L_lin_T14_m=2 * math.pi / SFW.k_lin(14.0, GC.H0),
                          mode1_angle_deg_lin=math.degrees(math.asin(min(1.0, L_lin / (2 * GC.W_MAIN)))),
                          mode1_angle_deg_sf=math.degrees(math.asin(min(1.0, sfT["L"] / (2 * GC.W_MAIN)))),
                          T14_at_W85_cutoff=bool(abs(2 * math.pi / SFW.k_lin(14.0, GC.H0) - 2 * GC.W_MAIN) / (2 * GC.W_MAIN) < 0.01),
                          seiche_T1_flat17_s=2 * GC.LX / math.sqrt(GC.G * GC.H0),
                          seiche_T1_axis_s=seiche_axis(GC.pg_axis()),
                          tags="計算")
    # (7) 粒子の数
    pc = {}
    for nm, sp, W, dp in (("3d_dp0p5", GC.PG12S, GC.W_MAIN, 0.5), ("3d_dp1p0", GC.PG12S, GC.W_MAIN, 1.0), ("axis_dp0p5", GC.pg_axis(), GC.W_STRIP, 0.5),
                          ("flat_dp0p5", GC.flat_spec(), GC.W_STRIP, 0.5)):
        n, V = GC.count_particles(sp, GC.LX, W, dp)
        pc[nm] = dict(particles=n, water_m3=V)
    out["particles"] = pc
    ok["particles_as_designed"] = bool(abs(pc["3d_dp0p5"]["particles"] / 3.63e6 - 1) < 0.01 and abs(pc["3d_dp1p0"]["particles"] / 0.45e6 - 1) < 0.01
                                       and abs(pc["axis_dp0p5"]["particles"] / 0.214e6 - 1) < 0.01 and abs(pc["flat_dp0p5"]["particles"] / 0.294e6 - 1) < 0.01)
    # (8) 設定を書かずに作って、走らせる前の確かめの数（in_gain が無いので S1 以降の ok は偽でよい）
    cf = {}
    for nm in ("S0a", "S0b", "S1", "D0", "D1"):
        try:
            c = preset(nm, {})[0]
            cf[nm] = dict(run_id=c["run_id"], precheck=c["precheck"], f_end=c["f_end"], windows=c["records"].get("windows"))
        except SystemExit as e:
            cf[nm] = dict(error=str(e))
    out["cfg_dry"] = cf
    ok["cfg_S0a_S0b_precheck_ok"] = bool(cf["S0a"].get("precheck", {}).get("ok") and cf["S0b"].get("precheck", {}).get("ok"))
    d1 = (cf["D1"].get("precheck") or {})
    ok["D1_wall_le_2p5h"] = bool(d1.get("checks", {}).get("wall_le_2p5h"))
    ok["D1_particles_as_designed"] = bool(d1.get("checks", {}).get("particles_as_designed"))
    # (A) 方案 A（2026-10-15 足した）
    out["A"], okA = checks_A(rng)
    ok.update(okA)
    # (9) 凍らせた計画
    if os.path.exists(GC.PLAN_FROZEN):
        h_ = GC.sha256_file(GC.PLAN_FROZEN)
        rec = open(GC.PLAN_FROZEN + ".sha256").read().split()[0] if os.path.exists(GC.PLAN_FROZEN + ".sha256") else None
        cp = GC.PLAN_COPY48
        out["plan_frozen"] = dict(path=GC.PLAN_FROZEN, sha256=h_, sha256_file=rec, copy=cp, copy_identical=bool(os.path.exists(cp) and GC.sha256_file(cp) == h_))
        ok["plan_frozen_sha"] = bool(rec == h_ and out["plan_frozen"]["copy_identical"])
    if os.path.exists(PLAN_A):
        hA = GC.sha256_file(PLAN_A)
        recA = open(PLAN_A + ".sha256").read().split()[0] if os.path.exists(PLAN_A + ".sha256") else None
        out["plan_A_frozen"] = dict(path=PLAN_A, sha256=hA, sha256_file=recA)
        ok["plan_A_frozen_sha"] = bool(recA == hA)
    out["ok"] = ok
    out["all_ok"] = bool(all(ok.values()))
    out["elapsed_s"] = round(time.time() - t_start, 1)
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    json.dump(out, open(GC.PLAN_DIR + "/precheck.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    return out


PLAN_A = GC.REPO + "/" + PLAN_A_REL


def checks_A(rng):
    """方案 A の numpy の確かめ（T0A）。返り値 (記録 dict, ok dict)。"""
    o, ok = {}, {}
    sp = GC.SPEC_A
    # (A1) x < x_back で FLIP48 C3 の海底を +37.25 m ずらした物と 1 bit も違わない（高さ）。勾配は式の道が違うので差の最大を書く
    c3 = os.path.join(G48.B48, "runs", GC.C3_RUN48, "cfg.json")
    if os.path.exists(c3):
        s48 = G48.bed_spec(json.load(open(c3, encoding="utf8")))
        X = np.concatenate([rng.uniform(-20.0, sp["x_back"] - 1e-6, 300000), np.arange(0.0, sp["x_back"], 0.25)])
        Y = np.concatenate([rng.uniform(-100.0, 100.0, 300000), np.zeros(len(np.arange(0.0, sp["x_back"], 0.25)))])
        zA = GC.bed_z(X, Y, **sp); zC = G48.bed_z(X - GC.DX_A, Y, **s48)
        gA = GC.bed_grad(X, Y, **sp); gC = G48.bed_grad(X - GC.DX_A, Y, **s48)
        Xg, Yg = np.meshgrid(np.arange(0.0, sp["x_back"], 0.25), np.arange(-90.0, 90.0001, 0.25))
        zAg = GC.bed_z(Xg, Yg, **sp); zCg = G48.bed_z(Xg - GC.DX_A, Yg, **s48)
        o["vs_C3_shifted"] = dict(c3_cfg=c3, c3_spec=s48, n_random=300000, grid="x 0..353.25 step 0.25, y -90..90 step 0.25",
                                  z_bit_equal_random=bool(np.array_equal(zA, zC)), z_bit_equal_grid=bool(np.array_equal(zAg, zCg)),
                                  z_max_abs_m=float(max(np.abs(zA - zC).max(), np.abs(zAg - zCg).max())),
                                  grad_max_abs=float(max(np.abs(gA[0] - gC[0]).max(), np.abs(gA[1] - gC[1]).max())),
                                  note="heights compared bit for bit; gradients go through the g49 'new' formula (|y| and sech^2 of k|y|) and differ by rounding only")
        ok["A_bed_equals_C3_shifted"] = bool(o["vs_C3_shifted"]["z_bit_equal_random"] and o["vs_C3_shifted"]["z_bit_equal_grid"] and o["vs_C3_shifted"]["grad_max_abs"] < 1e-12)
    else:
        o["vs_C3_shifted"] = dict(missing=c3)
        ok["A_bed_equals_C3_shifted"] = False
    # (A2) 下見の海底（u3_beds.depth、screen_A/sa_run.py の BED_A）と同じ
    U3 = GC.u3_depth_fn()
    Xg, Yg = np.meshgrid(np.arange(-10.0, 442.0001, 0.1), np.arange(-90.0, 90.0001, 0.25))
    dA = float(np.abs(-GC.bed_z(Xg, Yg, **sp) - U3(Xg, Yg, GC.SPEC_A_U3)).max())
    o["vs_u3"] = dict(max_abs_m=dA, grid="x -10..442 step 0.1, y -90..90 step 0.25", u3_spec=GC.SPEC_A_U3)
    ok["A_bed_vs_u3_lt_1e-9"] = dA < 1e-9
    # (A3) 勾配の数値の差・y について偶
    h = 1e-5
    Xr = rng.uniform(150, 440, 40000); Yr = rng.uniform(-88, 88, 40000)
    gx, gy = GC.bed_grad(Xr, Yr, **sp)
    ngx = (GC.bed_z(Xr + h, Yr, **sp) - GC.bed_z(Xr - h, Yr, **sp)) / (2 * h); ngy = (GC.bed_z(Xr, Yr + h, **sp) - GC.bed_z(Xr, Yr - h, **sp)) / (2 * h)
    err = np.maximum(np.abs(gx - ngx), np.abs(gy - ngy))
    o["grad_fd"] = dict(max=float(err.max()), n_gt_1em5=int((err > 1e-5).sum()), n=len(Xr), even_in_y=float(np.abs(GC.bed_z(Xr, Yr, **sp) - GC.bed_z(Xr, -Yr, **sp)).max()))
    ok["A_bed_grad_fd"] = bool(o["grad_fd"]["n_gt_1em5"] <= 2 and o["grad_fd"]["even_in_y"] < 1e-12)
    # (A4) 形：軸の縁・舌の半幅・x 340 m の水深・後ろの下りの終わり
    def half_width(x):
        ys = np.arange(0.0, 60.0, 0.01)
        d = -GC.bed_z(np.full_like(ys, x), ys, **sp)
        i = np.where(d > sp["shelf_h"] + 1e-9)[0]
        return float(ys[i[0]]) if len(i) else float("nan")
    o["geometry"] = dict(edge_x_axis_m=GC.edge_x(sp), tongue_half_width_m={"333.25": half_width(333.25), "343": half_width(343.0), "353": half_width(353.0)},
                         depth_x340_m={str(y): float(-GC.bed_z(340.0, float(y), **sp)) for y in (0, 10, 20, 30, 55, 60, 70)},
                         drop_end_x_m=sp["x_back"] + (sp["h_lag"] - sp["shelf_h"]) * sp["s_back"], kind=GC.bed_kind(sp), formula=GC.bed_formula(sp),
                         design=dict(edge=332.8, half_width_353=6.0, depth_x340={"10": 5.5, "20": 11.9, "30": 15.2, "55": 21.0}))
    g_ = o["geometry"]
    ok["A_geometry_as_designed"] = bool(abs(g_["edge_x_axis_m"] - 332.8) < 0.06 and abs(g_["tongue_half_width_m"]["353"] - 6.0) < 0.1
                                        and all(abs(g_["depth_x340_m"][k] - v) < 0.06 for k, v in g_["design"]["depth_x340"].items()))
    # (A5) 箱・粒子の数
    LY = GC.LAYOUTS["A"]
    b05 = GC.box48(0.5, Lx=LY["Lx"], W=GC.W_MAIN, zb=LY["zb"], floor_pad=2); b10 = GC.box48(1.0, Lx=LY["Lx"], W=GC.W_MAIN, zb=LY["zb"], floor_pad=2)
    n05, V05 = GC.count_particles(sp, b05["Lx"], b05["W"], 0.5, zb=LY["zb"]); n10, V10 = GC.count_particles(sp, b10["Lx"], b10["W"], 1.0, zb=LY["zb"])
    o["box_particles"] = dict(box_dp0p5=b05, box_dp1p0=b10, particles_dp0p5=n05, water_m3_dp0p5=V05, particles_dp1p0=n10, water_m3_dp1p0=V10,
                              design=dict(particles_dp0p5=4981609, particles_dp1p0=625205, cells_dp0p5=[442, 85, 44]))
    ok["A_box_cells"] = bool(b05["cells"] == [442, 85, 44] and b10["W"] == 86.0)
    ok["A_particles_as_designed"] = bool(n05 == EXPECT_PARTICLES_A[0.5] and n10 == EXPECT_PARTICLES_A[1.0])
    # (A6) 帯・波・入口の利得
    g_file, g_src = read_gain()
    o["inlet"] = dict(in_gain=g_file, source=g_src, exit_theory=GC.EX_THEORY_A, layout={k: (list(v) if isinstance(v, tuple) else v) for k, v in LY.items() if k != "level_regions"},
                      level_regions=[list(r) for r in LY["level_regions"]])
    ok["A_in_gain_present"] = bool(g_file is not None)
    # (A7) 設定を書かずに作って、走らせる前の確かめ
    cf = {}
    for nm in ("SMOKE_A", "DA1"):
        try:
            c = preset(nm, {})[0]
            cf[nm] = dict(run_id=c["run_id"], precheck=c["precheck"], f_end=c["f_end"], windows=c["records"].get("windows"),
                          r4=c["records"].get("r4"), r5=c["records"].get("r5"), fallback=(c.get("case") or {}).get("fallback"))
        except SystemExit as e:
            cf[nm] = dict(error=str(e))
    o["cfg_dry"] = cf
    ok["A_cfg_SMOKE_A_precheck_ok"] = bool((cf["SMOKE_A"].get("precheck") or {}).get("ok"))
    ok["A_cfg_DA1_precheck_ok"] = bool((cf["DA1"].get("precheck") or {}).get("ok"))
    return o, ok


def seiche_axis(spec, Lx=GC.LX):
    """閉じた水槽の 1 次の静振の周期 T1 = 2 ∫ dx/√(g d(x))（軸の断面、Merian の長い波の近似）。"""
    xs = np.arange(0.0, Lx, 0.1) + 0.05
    d = -GC.bed_z(xs, 0.0, **spec)
    return float(2.0 * np.sum(0.1 / np.sqrt(GC.G * d)))


def summary(o):
    L = ["all_ok %s  %s" % (o["all_ok"], o["ok"])]
    L.append("existing beds: %s" % {k: {kk: vv.get("bit_equal") for kk, vv in v.items()} if "missing" not in v else "missing" for k, v in o["existing_beds_bit_exact"].items()})
    L.append("PG12s vs u3_beds.depth: %.3e m" % o["pg12s_vs_u3"]["max_abs_m"])
    L.append("bed grad FD: %s" % {k: (round(v["max"], 9), v["n_gt_1em5"]) for k, v in o["bed_grad_fd"].items()})
    g = o["break_geometry"]
    L.append("break geometry: edge %.2f foot %.2f; dx at 1.5 Hc: 10/8/6/3 m = %.2f/%.2f/%.2f/%.2f; screening %s" % (
        g["x_edge"], g["x_foot_12m"], g["dx_d10m_y1.5Hc"], g["dx_d8m_y1.5Hc"], g["dx_d6m_y1.5Hc"], g["dx_d3m_y1.5Hc"], g.get("screening_geom")))
    s = o["sf"]
    L.append("SF: L %.3f c %.4f crest %.4f trough %.4f u1 %.4f Ur %.1f H/Hmax %.3f residual %.1e bc %s target-vs-g47 %.1e" % (
        s["L"], s["c"], s["eta_crest"], s["eta_trough"], s["u1"], s["ursell"], s["H_over_Hmax"], s["residual_max"], s["bc_residuals"], s["target_eta_vs_g47_max"]))
    L.append("numbers: %s" % {k: (round(v, 3) if isinstance(v, float) else v) for k, v in o["numbers"].items()})
    L.append("particles: %s" % {k: v["particles"] for k, v in o["particles"].items()})
    for k, v in o["cfg_dry"].items():
        pc = v.get("precheck") or {}
        L.append("  cfg %s: %s ok %s reason %s %s" % (k, v.get("run_id"), pc.get("ok"), pc.get("reason"),
                                                    {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in pc.items() if kk in ("solve_h_lo", "solve_h_hi", "records_h", "total_h_hi", "heavy_frames")}))
    if o.get("plan_frozen"):
        L.append("plan_frozen: %s" % o["plan_frozen"])
    A = o.get("A") or {}
    if A:
        v = A.get("vs_C3_shifted") or {}
        L.append("A: bed vs C3+37.25 z bit equal %s/%s (max %.1e) grad max %.1e; vs u3 %.1e; grad FD %s; geometry %s" % (
            v.get("z_bit_equal_random"), v.get("z_bit_equal_grid"), v.get("z_max_abs_m") or 0.0, v.get("grad_max_abs") or 0.0,
            A["vs_u3"]["max_abs_m"], (round(A["grad_fd"]["max"], 9), A["grad_fd"]["n_gt_1em5"]),
            {k: A["geometry"][k] for k in ("edge_x_axis_m", "tongue_half_width_m", "depth_x340_m", "drop_end_x_m")}))
        bp = A["box_particles"]
        L.append("A: cells %s, particles dp0.5 %d dp1.0 %d (W %g), in_gain %s" % (bp["box_dp0p5"]["cells"], bp["particles_dp0p5"], bp["particles_dp1p0"], bp["box_dp1p0"]["W"], A["inlet"]["in_gain"]))
        for k, v in A["cfg_dry"].items():
            pc = v.get("precheck") or {}
            L.append("  A cfg %s: %s ok %s reason %s %s" % (k, v.get("run_id"), pc.get("ok"), pc.get("reason"),
                                                          {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in pc.items()
                                                           if kk in ("solve_h_lo", "solve_h_hi", "records_h", "total_h_lo", "total_h_hi", "heavy_frames", "launches_est")}))
    if o.get("plan_A_frozen"):
        L.append("plan_A_frozen: %s" % o["plan_A_frozen"])
    return "\n".join(L)


def parse(argv):
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    return pos, opt


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = parse(sys.argv[1:])
    if not pos:
        print(__doc__); sys.exit(1)
    if pos[0] == "check":
        o = checks()
        print(summary(o))
    elif pos[0] == "freeze":
        print(freeze(force=bool(int(opt.get("force", "0"))), reason=opt.get("reason")))
    elif pos[0] == "freezeA":
        import g49_planA as PA_
        print(PA_.freeze_A(force=bool(int(opt.get("force", "0"))), reason=opt.get("reason")))
    elif pos[0] == "gain":
        gain(os.path.abspath(pos[1]))
    elif pos[0] == "cfg":
        names = pos[1:] or ["all"]
        if names == ["all"]:
            names = ["S0a", "S0b", "S1", "D0", "D1", "S2", "S3"]
        for nm in names:
            for c in preset(nm, opt):
                if not c["precheck"]["ok"]:
                    print("NOT WRITTEN", c["run_id"], c["precheck"]["reason"])
                    continue
                print("written", write(c), "f_end", c["f_end"], "particles", c["precheck"]["particles_model"],
                      {k: round(v, 3) for k, v in c["precheck"].items() if k in ("solve_h_hi", "total_h_hi")})
    else:
        print(__doc__); sys.exit(1)
