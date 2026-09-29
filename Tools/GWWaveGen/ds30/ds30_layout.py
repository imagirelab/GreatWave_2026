# -*- coding: utf-8 -*-
"""設計30：配置の記録（参照モデルの配置の数値 → 一次設計 → 二次設計、わざと変えた所）と、t* の平面図。

参照モデル（他者の展示作品のスキャン、作者・所蔵は未確認 D18）の OBJ は読まない。読むのは ds30_refmeasure.py が測った数値だけの
Unity/Build/Design/30/ref/ds30_ref_layout.json（頂点・網・断面の線は入っていない）。形は写さない（Q19・Q20）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds30/ds30_layout.py [--sea Unity/Build/Design/30/sea] [--out Unity/Build/Design/30/layout]
出力：<out>/ds30_layout_record.json・ds30_layout_plan_tstar.png（numpy の図。参照モデルの形は描かない、数値の印だけ）
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds30_sea as S  # noqa: E402
import ds30_checks as K  # noqa: E402

REPO = S.REPO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Design/30/sea")
    ap.add_argument("--out", default="Unity/Build/Design/30/layout")
    args = ap.parse_args()
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    sd = os.path.join(REPO, args.sea)
    P = S.load_json(S.PARAMS)
    refp = os.path.join(REPO, "Unity", "Build", "Design", "30", "ref", "ds30_ref_layout.json")
    ref = S.load_json(refp)
    hero_s = S.Hero()
    hero = K.Pkg(hero_s.dir)
    near = K.Pkg(os.path.join(sd, "near")); far = K.Pkg(os.path.join(sd, "far"))
    feat = S.Features(hero_s)
    log = S.load_json(os.path.join(sd, "ds30_generate_log.json"))
    feat.set_growth(log["hero_hmax_knots"])
    t_ax, e_ax, O = hero_s.t, hero_s.e, hero_s.focus
    # 主役波の t* の頂（最も高い点）
    Xh = hero.layer(hero.L - 1) + hero.origin(0.0)
    jb, je = P["hero"]["body_cols"]
    body = Xh[:, jb:je + 1]
    k = np.unravel_index(np.argmax(body[..., 1]), body.shape[:2])
    top = body[k]
    H_hero = float(top[1])
    top_a, top_c = float((top - O) @ t_ax), float((top - O) @ e_ax)
    H_ref = ref["H_ref_m"]
    sc = H_hero / H_ref
    # 主役波の谷（本体の中）の最も深い所（t*、頂より前）
    A = (Xh - O) @ t_ax; Cc = (Xh - O) @ e_ax
    front = (A > top_a) & (Xh[..., 1] < 0)
    kt = np.argmin(np.where(front, Xh[..., 1], np.inf))
    tr = np.unravel_index(kt, Xh.shape[:2])
    trough_hero = dict(a=float(A[tr]), c=float(Cc[tr]), depth=float(-Xh[tr][1]), depth_over_H=float(-Xh[tr][1] / H_hero))

    def first(dv):
        return dict(a=top_a + dv["da"] * sc, c=top_c + dv["dc"] * sc)
    sw = ref["small_wave"]["apex"]
    f_small = dict(**first(sw), h=sw["h_over_H"] * H_hero, h_over_H=sw["h_over_H"])
    tref = ref["trough"]
    f_trough = dict(**first(tref), depth=tref["depth_over_H"] * H_hero, depth_over_H=tref["depth_over_H"],
                    half_depth_c=[top_c + v * sc for v in tref["half_depth_dc_range"]])
    rref = ref["right_side_max"]
    f_right = dict(**first(rref), h=rref["h_over_H"] * H_hero, h_over_H=rref["h_over_H"])
    R = P["features"]["ds30_right_wave"]
    ci = int(np.argmax(R["crest_h"]))
    s_right_peak = dict(c=R["crest_c"][ci], a=float(np.interp(R["crest_c"][ci], R["crest_a_c"], R["crest_a"])), h=R["crest_h"][ci],
                        h_over_H=R["crest_h"][ci] / H_hero)
    sm = feat.small
    s_small = dict(a=sm["a"], c=sm["c"], h=sm["h"], h_over_H=sm["h"] / H_hero)
    T = P["features"]["ds30_trough_continue"]
    ti = int(np.argmax(T["depth_m"]))
    s_trough_cont = dict(c=T["c"][ti], a=float(np.interp(T["c"][ti], T["a_c"], T["a"])), depth=T["depth_m"][ti])
    rec = dict(
        schema="GreatWave.DS30.layout_record/1", number="設計30",
        reference=dict(source=ref["source"], source_sha256=ref["source_sha256"], credit_ja=ref["credit_ja"], align=ref["align"],
                       numbers_file="Unity/Build/Design/30/ref/ds30_ref_layout.json（数値だけ。Git 対象外）",
                       numbers_file_sha256=S.sha256_file(refp), H_ref_m=H_ref, sea_y_world=ref["ref_sea_y_world"],
                       small_wave=ref["small_wave"], trough=ref["trough"], right_side_max=ref["right_side_max"], footprint=ref["footprint"],
                       reading_ja="参照モデルは直径約 30 m の球の彫刻（台座の上）で、大波の前は深さ 0.43 H の椀状の谷、その前の縁に高さ 0.11 H の小さな富士形の小波。"
                                  "右側に別の高い波はない（大波の右の部分が 0.71 H のまま球の切断面 Δc +16 m まで続く。作業計画 9.2 と同じ）。"),
        hero=dict(H_m=H_hero, top_a=top_a, top_c=top_c, trough_in_sheet=trough_hero, scale_hero_over_ref=sc),
        first_design=dict(
            note_ja="参照モデルの配置の数値を、主役波の頂を原点に H の比（%.3f）で置いたもの（数値の記録。パッケージは作らない）。" % sc,
            small_wave=f_small, trough=f_trough, right_side=f_right),
        second_design=dict(
            note_ja="一面の海に置くための二次設計（パッケージ Unity/Build/Design/30/sea）。",
            small_wave=s_small, right_wave_peak=s_right_peak, trough_in_sheet=trough_hero, trough_continue_deepest=s_trough_cont,
            params=P["features"]),
        differences=[
            dict(id="D30-1", item="手前の小波の位置", first=f_small, second=s_small,
                 why_ja="原画視点の像を仮置き（M1_ForegroundSwell_Static）の頂と同じ射線に固定し、主役波の本体の前の縁から 5 m 前（a 15.0）に置いた。"
                        "一次設計の点（a %.1f・c %.1f）は本体の前の縁（c −10 で a ≈ 11）から 2 m しかなく、裾が本体の中に入る。" % (f_small["a"], f_small["c"])),
            dict(id="D30-2", item="手前の小波の高さ", first=f_small["h"], second=s_small["h"],
                 why_ja="参照モデルの 0.11 H（%.1f m）では原画の小波の頂の高さに届かない。原画視点の射線が決める %.2f m（%.2f H）にした。" % (f_small["h"], s_small["h"], s_small["h_over_H"])),
            dict(id="D30-3", item="手前の小波の形", why_ja="参照モデルの小波は後ろが緩く（裾 8.5 m）前が急（2 m）。二次設計は後ろを短く（4.2 m、主役波の谷の前の壁からそのまま立ち上がる）、"
                                                   "前 7.6 m・横 7.2 m、斜面はわずかに凹（1 − r の 1.38 乗）。原画視点で仮置きの輪郭に合わせるため（第 7 節の表）。"),
            dict(id="D30-4", item="大波の下の谷の深さ", first=f_trough["depth"], second=trough_hero["depth"],
                 why_ja="参照モデルの谷は球の彫刻の中に掘った椀（0.43 H）。一面の海では主役波のシートの谷（設計28修正01、%.2f H）のままにし、深くしない。" % trough_hero["depth_over_H"]),
            dict(id="D30-5", item="谷の続き", why_ja="参照モデルでは谷が球の縁で切れる。二次設計では本体の右の端（c +15）の先へ、大波の右の端と右の高い波の背の間の浅い谷"
                                                 "（深さ最大 %.1f m、c %.0f）として続け、c +46 で海へ戻す。左は主役波の谷が浅いので続けない。" % (s_trough_cont["depth"], s_trough_cont["c"])),
            dict(id="D30-6", item="右の高い波", first=f_right, second=s_right_peak,
                 why_ja="参照モデルには右側の別の波がない（大波の右の部分が 0.71 H で切れる）。二次設計は、同じ波群の波峰線が大波の右の端から前へ曲がる所として、"
                        "頂 %.1f m（%.2f H、c %.1f・a %.1f）の右の高い波を作り、谷の続きと座席の船の通る肩（c −3〜+6、高さ ≤ 5.3 m）で大波と一続きの面にした。"
                        "像の高さは仮置きの右の斜面（各 c の最も高い所）に合わせた。" % (s_right_peak["h"], s_right_peak["h_over_H"], s_right_peak["c"], s_right_peak["a"])),
            dict(id="D30-7", item="周りの海", why_ja="参照モデルは台座の上の球で、周りの海がない。二次設計は主役波と同じ交差うねりと搬送波の式で半径 650 m まで広げ、"
                                                 "ds_swell_calm・ds_sea_calm_painting で最後の数秒に静める。"),
            dict(id="D30-8", item="座席の船の支え", why_ja="参照モデルの船は浮彫で殻に溶け込んでいる。二次設計は t* で竜骨 + 喫水の水面（船の支えの誘導）にし、それより前は目の点の下の水面で鉛直に上下させる。"),
        ])
    S.save_json(os.path.join(out, "ds30_layout_record.json"), rec)
    # 平面図（t*、a を縦、c を横。主役波の本体・near・far の高さ）
    g = 0.5
    a0, a1, c0, c1 = -60.0, 70.0, -75.0, 85.0
    na, nc = int((a1 - a0) / g), int((c1 - c0) / g)
    Hm = np.full((na, nc), np.nan)
    pts = []
    for pk, Xl, rng in ((near, near.layer(near.L - 1), None), (far, far.layer(far.L - 1)[:-1], None), (hero, hero.layer(hero.L - 1)[:, jb:je + 1], None)):
        V = Xl.reshape(-1, 3)
        pts.append(V)
    # 三角形を平面へ塗る（遠い海 → near → 主役波の本体の順。高さは三角形の平均）
    def fill(Hmap, Xl, Tt):
        V = Xl.reshape(-1, 3)
        tri = V[Tt]
        pa = (tri @ t_ax - a0) / g; pc = (tri @ e_ax - c0) / g
        hv = tri[..., 1].mean(1)
        order = np.argsort(hv)
        for q in order:
            poly = np.stack([pc[q], pa[q]], 1)
            if poly[:, 0].max() < 0 or poly[:, 0].min() > nc or poly[:, 1].max() < 0 or poly[:, 1].min() > na:
                continue
            cv2.fillConvexPoly(Hmap, np.round(poly * 4).astype(np.int32), float(hv[q]), lineType=cv2.LINE_8, shift=2)
    Hm = np.full((na, nc), np.nan, np.float32)
    Xf = far.layer(far.L - 1)[:-1]
    fill(Hm, Xf, K.grid_tris(Xf.shape[0], Xf.shape[1]))
    Xn = near.layer(near.L - 1)
    fill(Hm, Xn, K.grid_tris(near.R, near.C))
    Hb = np.full((na, nc), np.nan, np.float32)
    Xb = hero.layer(hero.L - 1)
    fill(Hb, Xb, K.grid_tris(hero.R, hero.C, jb, je))
    x = np.clip((np.nan_to_num(Hm, nan=0) + 6) / 26.0, 0, 1)
    img = cv2.applyColorMap((x * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
    xb = np.clip((np.nan_to_num(Hb, nan=0) + 6) / 26.0, 0, 1)
    ib = cv2.applyColorMap((xb * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    img[np.isfinite(Hb)] = (0.55 * ib[np.isfinite(Hb)] + 0.45 * 255).astype(np.uint8)
    img = img[::-1]   # 上が +a（前）
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)

    def px(a, c):
        return (int(round((c - c0) / g * 3)), int(round((a1 - a) / g * 3)))
    for v in range(-70, 90, 10):
        cv2.line(img, px(a1, v), px(a0, v), (90, 90, 90), 1)
    for v in range(-60, 71, 10):
        cv2.line(img, px(v, c0), px(v, c1), (90, 90, 90), 1)
    for nm, d, col in (("1st small", f_small, (255, 255, 255)), ("1st trough", f_trough, (255, 255, 255)), ("1st right", f_right, (255, 255, 255)),
                       ("2nd small", s_small, (0, 0, 255)), ("2nd right peak", s_right_peak, (0, 0, 255)), ("2nd trough cont.", s_trough_cont, (0, 0, 255))):
        p = px(d["a"], d["c"])
        cv2.drawMarker(img, p, col, cv2.MARKER_TILTED_CROSS if nm.startswith("1st") else cv2.MARKER_DIAMOND, 18, 3)
        cv2.putText(img, nm, (p[0] + 10, p[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    kl = feat.keel
    for j in range(len(kl["a"]) - 1):
        cv2.line(img, px(kl["a"][j], kl["c"][j]), px(kl["a"][j + 1], kl["c"][j + 1]), (0, 200, 255), 3)
    seat = S.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    ey = np.array(seat["seat"]["eye_world"])
    cv2.circle(img, px(float((ey - O) @ t_ax), float((ey - O) @ e_ax)), 7, (0, 255, 255), 2)
    cv2.putText(img, "seat eye", px(float((ey - O) @ t_ax) - 2, float((ey - O) @ e_ax) + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(img, "ds30 t* plan (a up = travel t, c right = crest e; 10 m grid). hero body = pale; sea height -6..20 m (viridis). numpy, not Unity",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(out, "ds30_layout_plan_tstar.png"), img)
    print(json.dumps(dict(first=rec["first_design"], second={k: v for k, v in rec["second_design"].items() if k != "params"}), ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
