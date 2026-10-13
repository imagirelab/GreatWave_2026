# -*- coding: utf-8 -*-
"""FLIP47：周期の波の実験の cfg（g47_run.py・g47_chain.py に渡す json）を書く（py -3.10 -B。numpy だけ）。
2026-10-13 周期の波の実験の役（Claude）が書いた。元の値は periodic_design.json の runs・smoke（設計の役が凍結した物）をそのまま使い、
次だけを足す・変える（理由を cfg の pcfg_changes_ja に書く）：
  hip       ：Houdini/FLIP47/g47_tank_periodic.hiplc（g47_build_tank.py --periodic で作った場面。g47_tank.hiplc は変えない）
  sec       ：断面の記録を箱の全部（x0〜x1）・t 0 から（設計は x 520〜800 m・t 20 s から）。利用者の決まり「領域の全部の断面の動画」のため。
              粒子 0.25 m で 1 コマ 0.3 MB の桁（海底の組の記録 31 MB / 120 コマから）、190 s で 2 GB の桁【推定】。
  ana_xref  ：0（読みと動画の x を計画の座標のままにする。cfg の parms に x_p があると g47_analyze は x − x_p にするため）
  case・wave：動画と表の言葉（海底・波）
  sf_check  ：入口の帯の中の点（x 200・300・400・425 m × y −17・−9.5・−2 m）の格子の流速と帯の目標を、5 s ごとに並べる
煙の試し SM0（設計にない。タスクの「帯を入れた静かな水で流れがないこと」）：SM1 と同じ水槽（平ら 19 m、粒子 0.5 m）で、sf_on 1 のまま
  組の包絡を 0（set_P 1e9・set_up・set_flat・set_down 0）にして、帯の目標を流速 0 にする 30 s。
relax_w（2026-10-13 SM0 の後に変えた）：設計の relax_w 1（鉛直の流速も寄せる）は、SM0（帯の目標 0 の静かな水）で上流の壁に水を集めた
  （壁の水面 4 s で +0.63 m、14 s で +1.51 m。帯のない SA は +0.11〜0.12 m で止まる）【測った】。Houdini の FLIP Solver の説明（nodes.zip
  dop/flipsolver.txt）は、Volume Velocity の入力の解き手は「流速の場を作った後、発散を 0 にする前」に入ると書く【文献】。鉛直の流速を目標へ
  寄せると、重力が足した下向きの流速を圧力を解く前に消すので、帯の中の静水圧が足りず水を吸い込む【推定】。そこで SM0 だけ設計のまま
  relax_w 1 で残し（記録）、ほかは relax_w 0（水平だけ寄せる。FLIP44 で ±5 % を出したやり方）にする。SM0b は relax_w 0 の静かな水。
使い方：py -3.10 -B g47_pcfg.py [SM0|SM0b|SM1|SM2|P1|P2|P3|R4a|all]   → smoke/ready/<run_id>.json・runs/ready/<run_id>.json
      py -3.10 -B g47_pcfg.py <key> [--H=<m>] [--partsep=1] [--name=<run_id>] [--t_end=<s>]
        --H：流れ関数の波を 19 m・同じ周期で波高 H に解き直す（N 40。設計の SM1 の決まり「H_target × (H_target/H_測った)、0.9 H_max 以下」で 1 回だけ）
        --partsep：FLIP Solver の Apply Particle Separation（既定 0＝前と同じ）。SM1b で水が 45 s で +2.0 m 増えたので使わない
        --beach=1：斜面をそのまま浜（静かな水面の上 14 m）まで延ばす（浅い平ら・岩棚と吸う帯なし。P1b の後に足した）
        --volmode=1：帯の平均の水面を保つ形（帯の中だけに目標の発散。SM2b の後に足した）
        --volcorr=1：水の体積の直し（場面の volcorr_on。目標の発散で体積を V0 へ戻す。g47_tanklib.BODIES_VC）と、その記録（volcorr_diag）
"""
import os, sys, json, copy
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC

DESIGN = GC.B47 + "/periodic_design.json"
HIP_P = "Houdini/FLIP47/g47_tank_periodic.hiplc"
KEYS = {"SM1": ("smoke", "SM1_flat_sf14_dp0p5"), "SM2": ("smoke", "SM2_P1_dp0p5"), "P1": ("runs", "P1_S2_sf14"), "P2": ("runs", "P2_S5_sf14"),
        "P3": ("runs", "P3_S2_sets14"), "R4a": ("runs", "R4a_slab_sf14")}
BED_JA = {"P1": "S2：勾配 1:10 で水深 1.9 m の浅い平らへ（x 570〜741 m）", "P2": "S5：勾配 1:7 で水深 3.8 m の岩棚へ",
          "P3": "S2：勾配 1:10 で水深 1.9 m の浅い平らへ（x 570〜741 m）", "SM2": "S2：勾配 1:10 で水深 1.9 m の浅い平らへ",
          "SM1": "平ら 19 m（跳ね返りを測る）", "SM0": "平ら 19 m", "SM0b": "平ら 19 m", "R4a": "1:10 で 19 → 13 m、1:1 の段で 3.8 m の岩棚へ"}


def sf_text(sf, sets=None):
    s = "流れ関数の%s T %g s・H %g m（水深 %g m の平らで。平均の質量の流れ 0）" % ("波の組" if sets else "規則波", float(sf["T"]), float(sf["H"]), float(sf["h"]))
    if sets:
        s += "、組：%g s ごとに上り %g s・満ち %g s・下り %g s" % (sets["P"], sets["up"], sets["flat"], sets["down"])
    return s


BEACH_TOP = 14.0      # 浜の上の端（静かな水面の上 m）。流れ関数の波 H 12 m の打ち上げ（ξ0 0.55 で R/H0 0.8〜1 の桁）より高く


def beach_bed(bed, top=BEACH_TOP):
    """設計の海底の最初の斜面（斜面の足 x_toe から下る所）の勾配のまま、静かな水面の上 top m まで延ばした浜（その先は平ら）。
    崩れる所（水深 9〜13 m）とその前は設計と同じ。浅い平ら・岩棚と吸う帯を除く（周期の波で閉じた池になるため。record_ja.md）。"""
    b = [[float(x), float(d)] for x, d in bed]
    for (x0, d0), (x1, d1) in zip(b[:-1], b[1:]):
        if d1 < d0 - 1e-9 and x1 > x0:
            sl = (d0 - d1) / (x1 - x0)
            xc = x0 + (d0 + top) / sl
            return [[0.0, d0], [x0, d0], [xc, -top], [max(1130.0, xc + 10.0), -top]], sl, x0
    raise ValueError("斜面がない")


def make(key, H=None, partsep=None, name=None, t_end=None, volcorr=None, volmode=None, beach=None):
    D = json.load(open(DESIGN, encoding="utf8"))
    if key in ("SM0", "SM0b"):
        c = copy.deepcopy(D["smoke"]["SM1_flat_sf14_dp0p5"])
        c["run_id"] = "SM0_still_band_dp0p5" if key == "SM0" else "SM0b_still_band_u_dp0p5"
        c["t_end_s"] = 30.0
        c["f_end"] = GC.frames_for(30.0)
        c["parms"].update(set_P=1e9, set_up=0.0, set_flat=0.0, set_down=0.0)
        c["purpose_ja"] = "帯（sf_on 1）と吸う帯を入れたまま、帯の目標を 0（組の包絡 0）にした静かな水 30 s。帯が流れや水面の上下を作らないか"
        c.pop("cost_estimate", None)
        wave_ja = "波なし（帯の目標の流速 0。帯と吸う帯は入れたまま）"
    else:
        grp, rid = KEYS[key]
        c = copy.deepcopy(D[grp][rid])
        wave_ja = sf_text(c["sf"], c.get("sets"))
    for k in [k for k, v in list(c.items()) if isinstance(v, str) and "<" in v]:
        c.pop(k)
    b = c["box"]
    c["hip"] = HIP_P
    c["sec"] = dict(x0=b["x0"], x1=b["x1"], t0=0.0, block=120, allz=True)
    c["ana_xref"] = 0.0
    c["wave_kind"] = c.pop("wave", None)
    c["wave"] = dict(name_ja=wave_ja)
    c["case"] = dict(name="FLIP47_periodic_%s" % key,
                     name_ja="周期の波 %s（%s。%s）" % (key, BED_JA.get(key, ""), "粒子 %g m" % float(c["parms"]["dp"])))
    f_end = int(c["f_end"])
    c["sf_check"] = dict(frames=[2] + list(range(121, f_end + 1, 120)), x=[200.0, 300.0, 400.0, 425.0], y=[-17.0, -9.5, -2.0])
    c.setdefault("leak_every", 24)
    c.setdefault("level_guard_m", 1.0)
    c.setdefault("disk_stop_free_gb", 25.0)
    c.setdefault("wait_hython_max_s", 1800)
    c["pcfg_changes_ja"] = ["hip を周期の波の場面に", "sec を箱の全部・t 0 から・4 層（設計：x 520〜800・t 20 s）。動画で領域の全部を見せるため",
                            "ana_xref 0（x は計画の座標）", "case・wave の言葉", "sf_check（入口の帯の目標と格子の流速）"]
    c["design_source"] = "periodic_design.json（%s）" % ("smoke.SM1_flat_sf14_dp0p5 を写した SM0" if key.startswith("SM0") else ".".join(KEYS[key]))
    if key != "SM0":
        c["parms"]["relax_w"] = 0.0
        c["pcfg_changes_ja"].append("relax_w 0（水平だけ寄せる）。設計は 1。SM0 で 1 が上流の壁に水を集めたため（この道具の頭の説明）")
    c["out_root"] = "smoke" if key.startswith("SM") else "runs"
    if H is not None:
        import g47_sfwave as SFW
        sv = SFW.solve(float(c["sf"]["h"]), float(c["sf"]["T"]), float(H), N=int(c["sf"]["N"]))
        if not sv["ok"]:
            raise SystemExit("流れ関数の解が解けない H %g: %s" % (H, sv["msg"]))
        Hmax = SFW.highest_H(float(c["sf"]["h"]), float(c["sf"]["T"]))
        if float(H) > 0.9 * Hmax + 1e-9:
            raise SystemExit("H %g m は 0.9 H_max（%.3f m）を越える" % (H, 0.9 * Hmax))
        tb = SFW.table(sv)
        old = c["sf"]
        c["sf"] = dict({k: v for k, v in old.items() if k not in tb}, **tb)
        c["sf"]["H_design"] = float(old["H"])
        c["sf"]["resolve_note_ja"] = "SM1（粒子 0.5 m）で波高が目標の −9 %% だったので、設計の決まりで H を %.3f m（0.9 H_max %.3f m 以下）に解き直した" % (float(H), 0.9 * Hmax)
        c["wave"]["name_ja"] = sf_text(c["sf"], c.get("sets")) + "（設計 H %g m から解き直し）" % float(old["H"])
        c["pcfg_changes_ja"].append("流れ関数の波を H %.3f m に解き直した（設計 %g m）" % (float(H), float(old["H"])))
    if volcorr:
        c["parms"].update(volcorr_on=1.0, vol_tau=4.0, vol_dmax=0.002, vol_tcap=1.5)
        c["volcorr_diag"] = True
        c["pcfg_changes_ja"].append("水の体積の直し volcorr_on 1（τ 4 s、上限 0.002 /s、V0 は 1.5 s まで）。SM1 で FLIP の水が 120 s で箱の平均 −0.28 m 減ったため")
    if volmode == 1:
        P_ = c["parms"]
        P_.update(volcorr_on=1.0, vol_mode=1.0, vol_x0=float(P_["x0"]) + float(P_["wall_taper_m"]) + 10.0, vol_x1=float(P_["xg_end"]) - 12.0,
                  vol_tau=10.0, vol_ti=30.0, vol_avg_s=float(c["sf"]["T"]), vol_dmax=0.006, vol_tcap=1.5)
        c["pcfg_changes_ja"].append("帯の平均の水面を保つ（vol_mode 1、x %.0f〜%.0f m だけに目標の発散、τ 10 s・積分 30 s・動く平均 %g s・上限 0.006 /s）。"
                                    "SM2b で浅い平らに水が運び上げられ、閉じた水槽の沖の平均の水面が −1.2 m 下がって崩れる所が沖へ動いたため"
                                    % (P_["vol_x0"], P_["vol_x1"], float(c["sf"]["T"])))
    if beach:
        nb, sl, xt = beach_bed(c["bed"])
        c["bed_design"] = c["bed"]
        c["bed"] = nb
        c["parms"].update(abs_on=0.0, xa0=1e9)
        c["case"]["name_ja"] = c["case"]["name_ja"].replace(BED_JA.get(key, "@@"), "勾配 1:%.3g をそのまま浜（静かな水面の上 %.0f m）まで延ばした" % (1.0 / sl, BEACH_TOP))
        c["bed_name_ja"] = "斜面の足 x %.0f m から勾配 1:%.3g のまま浜へ（静かな水面の線 x %.1f m、上の端 +%.0f m を x %.1f m）。浅い平ら・岩棚と吸う帯なし" % (
            xt, 1.0 / sl, xt + 19.0 / sl, BEACH_TOP, nb[2][0])
        c["pcfg_changes_ja"].append("海底を浜にした（%s）。周期の波では浅い平らが閉じた池になり（P1b で時間の平均 +5〜+6.5 m で増え続けた）、崩れる所と計算の速さを変えたため。"
                                    "崩れる所（x 640〜665 m、水深 9〜12 m）とその沖の海底は設計と同じ" % c["bed_name_ja"])
    if partsep is not None:
        c["solver"]["partsep"] = int(partsep)
        c["pcfg_changes_ja"].append("FLIP Solver の Apply Particle Separation %d（既定 0）" % int(partsep))
    if t_end is not None:
        c["t_end_s"] = float(t_end); c["f_end"] = GC.frames_for(float(t_end))
        c["sf_check"]["frames"] = [f for f in c["sf_check"]["frames"] if f <= c["f_end"]]
        if "pstats_frames" in c:
            c["pstats_frames"] = [f for f in c["pstats_frames"] if f <= c["f_end"]] + [c["f_end"]]
    if name:
        c["run_id"] = name
        c["case"]["name"] = "FLIP47_periodic_%s" % name
    if key.startswith("SM"):      # 煙の試しも途中保存する（1 起動 29 分を越えても続けられるように。設計は ckpt_on 0）
        c.update(ckpt_on=1, ckpt_every=240, ckpt_list=[480, 240, 120])
        c["pcfg_changes_ja"].append("煙の試しも途中保存（ckpt_on 1、240 コマごと）")
    return c


def write(key, **kw):
    c = make(key, **kw)
    p = GC.B47 + "/%s/ready/%s.json" % (c["out_root"], c["run_id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return p, c


if __name__ == "__main__":
    opts = {a[2:].split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
    kw = {}
    if "H" in opts: kw["H"] = float(opts["H"])
    if "partsep" in opts: kw["partsep"] = int(opts["partsep"])
    if "name" in opts: kw["name"] = opts["name"]
    if "t_end" in opts: kw["t_end"] = float(opts["t_end"])
    if "volcorr" in opts: kw["volcorr"] = int(opts["volcorr"])
    if "volmode" in opts: kw["volmode"] = int(opts["volmode"])
    if "beach" in opts: kw["beach"] = int(opts["beach"])
    ks = [a for a in sys.argv[1:] if not a.startswith("--")] or ["all"]
    if ks == ["all"]:
        ks = ["SM0", "SM0b", "SM1", "SM2", "P1", "P2", "P3", "R4a"]
    for k in ks:
        p, c = write(k, **kw)
        b = c["box"]; P = c["parms"]
        print(p, "f_end", c["f_end"], "dp", P["dp"], "box", b["x0"], b["x1"], b["y_floor"], b["y_top"], "Lz", b["Lz"], "o", b["ox"], b["oy"], b["oz"],
              "relax", P["relax_on"], P["xg_end"], "abs", P["abs_on"], P["xa0"], "sf_on", P["sf_on"], "relax_w", P["relax_w"], "set_P", P["set_P"],
              "ramp", P["ramp_s"], "solver", c["solver"])
