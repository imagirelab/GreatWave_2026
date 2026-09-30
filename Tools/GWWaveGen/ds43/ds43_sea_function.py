# -*- coding: utf-8 -*-
"""設計43：設計30 の海の式（sea_function.json）に、far の半径方向の弱めと読み方の約束を書き足した版を作り、シートの頂点と照合する。

設計30 の限界 7（far の半径 380〜600 m の弱めが sea_function.json の式にない。約 400 m より外で式と最大 3.4 m 違う）を閉じる。
  η(x, z, τ) = w_far(r)·[κ_c·A_c·Σ_car + κ_s·Σ_swell] + g(τ)·F(a, c)
  w_far(r) = 1 − smoothstep((r − 380)/(600 − 380))、r = |(a, c) − (a_c0, c_c0)|（波の枠とともに動く競技場の中心 (a_c0, c_c0) = (−2.5, −2.5) m から）。
  地形の誘導 g·F には掛けない（ds30_generate.py と同じ）。far の最後の輪（半径 650 m）は y = 0、その下は −8 m のすそ。
照合：節点の層（Hermite を使わない）の頂点の高さと、式の値の差。near は行 0 からの実際の距離 s ≥ 10 m の頂点（接続帯の外）で外周の行を除く、far は行 1〜16。
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_sea_function.py
"""
import os
import time

import numpy as np

import ds43_common as C

SRC = os.path.join(C.REPO, "Unity", "Build", "Design", "30", "sea", "sea_function.json")
DST = os.path.join(C.OUT, "sea_function_ds43.json")


def main():
    t0 = time.time()
    sf = C.SeaFunction()
    hero, near, far = C.load_sheets()
    P = sf.P
    G = P["grid"]
    zeta = np.array(near.k["ring_zeta"])
    ring_s = np.array(G["near_ring_s_m"])
    band_rows = [r for r in range(near.R - 1) if ring_s[r] >= P["band"]["carrier_blend_m"]]
    knots = list(range(0, far.L, 10)) + [far.L - 1]
    res = dict(far_with_taper=[], far_without_taper=[], near_outside_band=[])
    for i in knots:
        tau = float(far.knots[i])
        O = far.origin(tau)
        Xf = far.layer(i) + O[None, None, :]
        rows = slice(1, far.R - 2)
        xf, yf, zf = Xf[rows, :-1, 0], Xf[rows, :-1, 1], Xf[rows, :-1, 2]
        # 式（節点 i の A_c をそのまま使う：生成器と同じ knot=i）
        Oa = sf.hero.origin(tau)
        a = (xf - Oa[0]) * sf.hero.t[0] + (zf - Oa[2]) * sf.hero.t[2]
        c = (xf - Oa[0]) * sf.hero.e[0] + (zf - Oa[2]) * sf.hero.e[2]
        base = sf.sea.eta(xf, zf, tau, knot=i)
        w, r = sf.taper(xf, zf, tau)
        F = sf.feat.growth_knots[i] * sf.feat.shape(a, c)["total"]
        res["far_with_taper"].append(float(np.abs(w * base + F - yf).max()))
        res["far_without_taper"].append(float(np.abs(base + F - yf).max()))
        Xn = near.layer(i) + O[None, None, :]
        s_act = np.hypot(Xn[:, :-1, 0] - Xn[0:1, :-1, 0], Xn[:, :-1, 2] - Xn[0:1, :-1, 2])
        msk = (s_act >= P["band"]["carrier_blend_m"])
        msk[-1] = False                                   # 外周の行（5 点おきの間は線形補間）は除く
        xn, yn, zn = Xn[:, :-1, 0][msk], Xn[:, :-1, 1][msk], Xn[:, :-1, 2][msk]
        a = (xn - Oa[0]) * sf.hero.t[0] + (zn - Oa[2]) * sf.hero.t[2]
        c = (xn - Oa[0]) * sf.hero.e[0] + (zn - Oa[2]) * sf.hero.e[2]
        yn_f = sf.sea.eta(xn, zn, tau, knot=i) + sf.feat.growth_knots[i] * sf.feat.shape(a, c)["total"]
        res["near_outside_band"].append(float(np.abs(yn_f - yn).max()))
    d = C.load_json(SRC)
    d["schema"] = "GreatWave.DS43.sea_function/1"
    d["number"] = "設計43（設計30 の sea_function.json に書き足した版）"
    d["based_on"] = dict(file="Unity/Build/Design/30/sea/sea_function.json", sha256=C.sha256_file(SRC))
    d["formula_ja"] = ("η(x, z, τ) = w_far(r)·[κ_c(τ)·A_c(c, τ)·Σ_car amp·cos(kx·(x − Ox) + kz·(z − Oz) − ω·τ + φ) + κ_s(τ)·Σ_swell（同じ形）] + g(τ)·F(a, c)。"
                       "設計30 の式に w_far を足した（設計43）。w_far は地形の誘導 g·F には掛けない。ほかの記号は設計30 の formula_ja と同じ。")
    d["far_taper"] = dict(
        on=True, start_m=float(G["far_taper_start_m"]), end_m=float(G["far_taper_end_m"]),
        center_ac_m=[float(v) for v in sf.cen_ac],
        center_source_ja="競技場（near の外周：前 a +105、後 a −110、右 c +125、左 c −130 m）の中心 ((105 − 110)/2, (125 − 130)/2) = (−2.5, −2.5)。波の枠とともに動く（a・c は O(τ) からの局所の軸）",
        shape_ja="w_far(r) = 1 − smoothstep((r − 380)/(600 − 380))、smoothstep(x) = x²(3 − 2x)（0〜1 に切る）。r = √((a − a_c0)² + (c − c_c0)²)",
        applies_to_ja="搬送波とうねりの和（周りの海）だけ。地形の誘導 g·F には掛けない。far のシートでは行 1〜16 がこの式、行 0 は near の外周の写し、行 17（半径 650 m）は y = 0、行 18 は −8 m のすそ",
        source=dict(file="Tools/GWWaveGen/ds30/ds30_generate.py", params="Tools/GWWaveGen/ds30/ds30_params.json（grid.far_taper_start_m・far_taper_end_m）"))
    d["reading_rule_ds43_ja"] = ("船用水面データ（設計43 の DS43BoatWater）は、この式ではなく、表示と同じ標本（主役波の本体の列 18〜394・near・far のシートを同じ τ で復号し、"
                                 "鉛直の線の最も低い交わり＝下側の一価の面）を読む。この式は周りの海の定義で、シートの頂点はこの式の値（接続帯の外）。"
                                 "far の表示は粗い網（輪の間隔 数 m〜数十 m）なので、網の間では式と最大 17 cm 違う（設計43 の前の確かめ）。流速・シートの外の予備に使う")
    d["verification_ds43"] = dict(
        knots_checked=[int(k) for k in knots],
        far_rows_1_16_absmax_m_with_taper=max(res["far_with_taper"]),
        far_rows_1_16_absmax_m_without_taper=max(res["far_without_taper"]),
        near_rows_outside_band_absmax_m=max(res["near_outside_band"]),
        near_rule_ja="near は、行 0（主役波の輪）からの実際の水平距離 s ≥ 10 m の頂点（接続帯の外）。外周の行は除く",
        note_ja="節点の層の頂点（16 bit + 精度の層）とこの式の差。弱めを入れると far の頂点と量子化の大きさで合い、入れないと設計30 の独立の検査の値（約 400 m より外で最大 3.4 m）と同じ大きさで違う")
    d["reference_impl_ds43"] = "Tools/GWWaveGen/ds43/ds43_common.py（SeaFunction.eta）"
    C.save_json(DST, d)
    import json
    print(json.dumps(d["verification_ds43"], ensure_ascii=False, indent=1), round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
