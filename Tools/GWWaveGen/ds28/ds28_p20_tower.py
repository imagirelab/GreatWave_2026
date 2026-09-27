# -*- coding: utf-8 -*-
"""設計28：関門 P20（美術の誘導の大きさ、記録）に、ds28_model.py の外で名前を付けた誘導と、1 つだけでは切れない誘導の大きさを足す。

ds28_p20.py（ds28_model の 12 個）と同じ測り方（ds28_p20.measure と同じ τ の並び、頂点の差、波の枠の局所座標）で、
  (1) ds_crest_tower（行ごとの t* の頂の高さを K* から受け継ぐ。統合で名前を付けた）：入れた版と、これだけを切った版（物理の頂の高さ）
  (2) ds_undercut_kstar（噴流の始まりの前に前面を頂の下までえぐる量を K* から決める。レビュー対応で名前を付けた）：
      入れた版と、これだけを切った版（始まりの張り出し 0、K* の錨で頭打ちしない）。錨の始まりの位置 q_on と K* の錨 q* も記録する
  (3) 14 個すべて切った版（設計28 の切った版＝物理だけ。ds28_physoff の art_off の既定）と、レビューの前の切った版
      （13 個を切り、ds_undercut_kstar だけ入る。参考）
  (4) 入れた版から 1 つだけ切っても形が変わらない 2 個の大きさを、別の測り方で：
      ds_back_steep：(a) ds_body_narrow と一緒に切った差（入れた版 − 2 個）、(b) ds_body_narrow を切った版からさらに切った差、
                     (c) 物理だけの版に ds_back_steep だけを入れた差
      ds_farwall_hold：物理だけの版にこれだけを入れた差（入れた版では版の名前 art_on で峰の行が決まるので、切っても変わらない）
  (5) 名前のない、版の名前（art_on／art_off）で決まる違い：12 個の切り替えと ds_crest_tower・ds_undercut_kstar をすべて切った
      「art_on という名前の版」と、物理だけの版の差（唇の重み κ の決め方、唇先の列のならし、峰の行 c_pk、唇の白の最遅の時刻）
を測る。入れた版は ds28_physoff.Generator("art_on") で作り、ds28_model.Generator("art_on") と頂点まで同じことを確かめる。
判定はしない（記録）。生成器を直接呼ぶ（パッケージの量子化と Hermite を含まない）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28/ds28_p20_tower.py [--out Unity/Build/Design/28/p20/ds28_p20_tower.json]
1 回 約 10〜15 分。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds28_model as M8  # noqa: E402
import ds28_p20 as P20  # noqa: E402
import ds28_physoff as PO  # noqa: E402

REPO = M8.REPO


def fin(e):
    e["max_over_tau_m"] = max(r["max_m"] for r in e["per_tau"])
    e["rms_max_over_tau_m"] = max(r["rms_m"] for r in e["per_tau"])
    k = max(e["per_tau"], key=lambda r: r["max_m"])
    e["max_tau"] = k["tau"]
    e["max_at"] = k["max_at"]
    return e


def twhite_diff(g1, g2):
    T1 = g1.twhite().astype(np.float64)
    T2 = g2.twhite().astype(np.float64)
    fin_ = (T1 < 1e8) | (T2 < 1e8)
    d = np.abs(np.where(fin_, np.minimum(T1, 1e3) - np.minimum(T2, 1e3), 0.0))
    ch = d > 1e-6
    return dict(twhite_changed_vertices=int(ch.sum()), twhite_max_abs_diff_s=float(round(float(d.max()), 3)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Unity", "Build", "Design", "28", "p20", "ds28_p20_tower.json"))
    a = ap.parse_args()
    t0 = time.time()

    def log(s):
        print(s, flush=True)
    g_on = M8.Generator("art_on")
    g_on2 = PO.Generator("art_on")
    same = max(float(np.abs(g_on.local(t) - g_on2.local(t)).max()) for t in (-4.0, -2.4, -1.0, 0.0))
    log("  ds28_physoff の入れた版と ds28_model の入れた版の差の最大 %.3g m" % same)
    del g_on2
    K = g_on.K
    T = P20.TAUS
    names12 = list(g_on.sw.keys())
    out = dict(schema="GreatWave.DS28.p20_tower/2", number="設計28",
               ja="関門 P20 の追加（記録）。ds28_model.py の外（ds28_physoff.Generator の引数）で名前を付けた 2 個（ds_crest_tower・ds_undercut_kstar）、"
                  "14 個すべて切った設計28 の切った版（物理だけ）との差、入れた版から 1 つだけ切っても形が変わらない 2 個（ds_back_steep・ds_farwall_hold）の別の測り方、"
                  "名前のない版の名前で決まる違い。ds28_p20.py と同じ τ と同じ測り方（頂点の差、波の枠の局所座標、m）。",
               taus=T, art_on_same_as_ds28_model_max_m=float(round(same, 9)), guidance={}, separability={})
    # (1) ds_crest_tower
    g_tw = PO.Generator("art_on", crest_tower=False)
    out["guidance"]["ds_crest_tower"] = fin(dict(kind_ja="行ごとの t* の頂の高さを K* から受け継ぐ（塔。設計28 の統合で名前を付けた）",
                                                 per_tau=P20.measure(g_on, g_tw, K, T, "ds_crest_tower", log)))
    del g_tw
    # (2) ds_undercut_kstar
    g_uc = PO.Generator("art_on", undercut_kstar=False)
    e = fin(dict(kind_ja="噴流の始まりの前に前面を頂の下までえぐる量を K* から決める（レビュー対応で名前を付けた。ds28_model の anchor_q の σ < −2.4 の分岐）",
                 per_tau=P20.measure(g_on, g_uc, K, T, "ds_undercut_kstar", log)))
    hb = g_on.has_body
    H = g_on.H
    back = np.where(hb, np.maximum(g_uc.q_on - g_uc.qst, 0.0) * H, 0.0)
    rows_back = np.nonzero(back > 0.005)[0]
    mr = int(K.main_row)
    pr = int(np.argmin(np.abs(K.c - g_on.c_pk_on)))
    duc = (g_uc.q_on - g_on.q_on) * H
    e["anchor"] = dict(
        ja="錨（内壁の 0.3H 付近の点）の頂からの横の距離 / H。q_on_on：入れた版の噴流の始まりの位置（K* の張り出しで決めたえぐり、K* の錨で頭打ち）。"
           "q_on_off：切った版（始まりの張り出し 0）。qst：t* の K* の錨。undercut_m = (q_on_off − q_on_on)·H は、入れた版が始まりの前に余分にえぐる横の量。"
           "切った版では、始まりの後に錨が q_on_off から q* へ進むので、q_on_off > q* の行では錨が噴流の始まりの後に後ろへ戻る（anchor_back_after_onset_when_off）",
        main_row=dict(row=mr, q_on_on=round(float(g_on.q_on[mr]), 4), q_on_off=round(float(g_uc.q_on[mr]), 4), qst=round(float(g_on.qst[mr]), 4),
                      undercut_m=round(float(duc[mr]), 3)),
        peak_row=dict(row=pr, q_on_on=round(float(g_on.q_on[pr]), 4), q_on_off=round(float(g_uc.q_on[pr]), 4), qst=round(float(g_on.qst[pr]), 4),
                      undercut_m=round(float(duc[pr]), 3)),
        undercut_m_body_rows=dict(min=round(float(duc[hb].min()), 3), max=round(float(duc[hb].max()), 3), median=round(float(np.median(duc[hb])), 3)),
        anchor_back_after_onset_when_off=dict(rows=int(len(rows_back)), of_body_rows=int(hb.sum()), max_m=round(float(back.max()), 3),
                                              rows_c_m=[round(float(K.c[rows_back.min()]), 2), round(float(K.c[rows_back.max()]), 2)] if len(rows_back) else None))
    out["guidance"]["ds_undercut_kstar"] = e
    del g_uc
    # (3) すべて切った版
    g_all = PO.Generator("art_off")
    out["all_off_phys"] = dict(kind_ja="14 個すべて切った版（設計28 の切った版＝物理だけ。レビュー対応の後の定義）との差",
                               per_tau=P20.measure(g_on, g_all, K, T, "art_off_phys（14 個を切る）", log))
    g_all_r0 = PO.Generator("art_off", undercut_kstar=True)
    out["all_off_phys_review_r0"] = dict(kind_ja="参考：レビューの前の切った版（13 個を切り、ds_undercut_kstar だけ入る）との差",
                                         per_tau=P20.measure(g_on, g_all_r0, K, T, "art_off_phys（レビューの前）", log))
    out["physoff_undercut_effect"] = fin(dict(kind_ja="物理だけの版の中での ds_undercut_kstar の差（レビューの前の切った版 − 今の切った版）",
                                              per_tau=P20.measure(g_all_r0, g_all, K, T, "physoff の ds_undercut_kstar", log)))
    del g_all_r0
    # (4) 1 つだけでは切れない 2 個
    sep = out["separability"]
    g_bn = M8.Generator("art_on", switches={"ds_body_narrow": False})
    g_bnbs = M8.Generator("art_on", switches={"ds_body_narrow": False, "ds_back_steep": False})
    sep["ds_back_steep"] = dict(
        ja="ds_back_steep は ds27_model の sections で『ds_body_narrow または ds_back_steep』の分岐（K* の背面を使うか）にだけ効くので、"
           "入れた版から 1 つだけ切っても形が変わらない（ds28_p20.py の 0 は大きさではなく、分けられないこと）。",
        with_body_narrow=fin(dict(kind_ja="入れた版と、ds_body_narrow・ds_back_steep の 2 個を一緒に切った版の差（2 個の合計）",
                                  per_tau=P20.measure(g_on, g_bnbs, K, T, "body_narrow+back_steep", log))),
        after_body_narrow_off=fin(dict(kind_ja="ds_body_narrow を切った版から、さらに ds_back_steep を切った差（K* の背面 → 物理の交差波群の背面）",
                                       per_tau=P20.measure(g_bn, g_bnbs, K, T, "back_steep（body_narrow を切った後）", log))))
    del g_bn, g_bnbs
    g_bs1 = PO.Generator("art_off", switches={"ds_back_steep": True})
    sep["ds_back_steep"]["alone_from_physics_only"] = fin(dict(kind_ja="物理だけの版に ds_back_steep だけを入れた差",
                                                               per_tau=P20.measure(g_bs1, g_all, K, T, "back_steep だけ入れる", log)))
    del g_bs1
    g_fw1 = PO.Generator("art_off", switches={"ds_farwall_hold": True})
    sep["ds_farwall_hold"] = dict(
        ja="ds_farwall_hold は峰の行（砕波の広がりの起点 c_pk）だけに効き、ds27_model の _rows は『版が art_on または ds_farwall_hold』で c_pk = +3.85 m にするので、"
           "入れた版では切っても変わらない（奥の壁を t* まで砕かないのは、実際には版の名前で決まる唇の重み κ と白の時刻による。unnamed_version_keyed）。",
        alone_from_physics_only=fin(dict(kind_ja="物理だけの版に ds_farwall_hold だけを入れた差（峰の行 c_pk 0 → +3.85 m）",
                                         per_tau=P20.measure(g_fw1, g_all, K, T, "farwall_hold だけ入れる", log))),
        c_pk_m=dict(physics_only=float(g_all.c_pk), with_farwall_hold=float(g_fw1.c_pk)))
    sep["ds_farwall_hold"]["alone_from_physics_only"].update(twhite_diff(g_fw1, g_all))
    del g_fw1
    # (5) 名前のない、版の名前で決まる違い
    g_vk = PO.Generator("art_on", switches={k: False for k in names12}, crest_tower=False, undercut_kstar=False)
    ent = fin(dict(kind_ja="名前のない違い（版の名前 art_on／art_off で決まる）：14 個をすべて切った『art_on という名前の版』と物理だけの版の差",
                   per_tau=P20.measure(g_vk, g_all, K, T, "版の名前だけ", log)))
    ent.update(twhite_diff(g_vk, g_all))
    kap_on = np.asarray(g_vk.kappa, float)
    kap_off = np.asarray(g_all.kappa, float)
    ent["branches_ja"] = [
        "唇の重み κ：art_on は K* の巻き（張り出し）から行ごとに決めてならした値（奥の壁の外側で小さく、唇が弱い・遅い）、art_off は頂の高さの smoothstep（artoff_lip_weight_H_m）。ds27_model._rows",
        "唇先の列：art_off だけ波峰線方向にならす（boundary_row_smooth_m）。ds27_model._rows",
        "峰の行 c_pk（砕波の広がりの起点）：art_on は +3.85 m（設計26）、art_off は物理の頂なら c = 0（ds28_physoff）、K* の頂なら最も高い行。ds27_model._rows・ds28_physoff._rows",
        "唇の白の最遅の時刻（lip_latest_tau_s）：art_on だけ（色だけ）。ds27_model.twhite",
        "設計28 の κ < 1 の行の打ち出しの弱め方（lip_kappa）は κ に従うので、上の κ の違いを通して版の名前に依る",
    ]
    ent["kappa"] = dict(rows_kappa_lt1_art_on=int(((kap_on > 0) & (kap_on < 1)).sum()), rows_kappa_lt1_art_off=int(((kap_off > 0) & (kap_off < 1)).sum()),
                        rows_lip_art_on=int((kap_on > 0).sum()), rows_lip_art_off=int((kap_off > 0).sum()),
                        max_abs_diff=round(float(np.abs(kap_on - kap_off).max()), 3), c_pk_m=dict(art_on=float(g_vk.c_pk), art_off=float(g_all.c_pk)))
    out["unnamed_version_keyed"] = ent
    out["runtime_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("DONE %.0f s → %s" % (time.time() - t0, a.out))


if __name__ == "__main__":
    main()
