# -*- coding: utf-8 -*-
"""設計28（レビュー対応）：関門が見ない所を測って記録する（記録のみ。判定はしない）。

1. シートの上の本体の水（設計27 の記録 §2.5 の「本体の水」と同じ定義）：設計27 と設計28 の入れた版、設計28 の切った版（物理だけ）。
   定義は設計27 の ds27_review_measure.water と同じ：行ごとのシートの上の符号付きの断面積（ds27_gates.row_areas。y = 0 で閉じる、
   張り出しの下の空気は引かれる）× 行の間隔（K* の c の勾配）の和。τ −4.6〜0 s を 0.1 s おき（設計27 は −4.0 s から）。
   P17（行ごとの本体の列、前面が鉛直 → t*）より広い区間と範囲の値。
2. 唇のすべての列の弾道（引き継ぎ 3 の確かめを広げる）：設計28 の入れた版の唇の行すべて・唇の列すべてについて、打ち出しの補間の後
   （放出 + 補間の長さ + 0.02 s）から t* までを 240 Hz でパッケージから読み、2 次式の当てはめの加速度（地面の縦 ay・進行方向 a_h）を測る。
   窓が 0.25 s 未満の点は除く（ds28_evidence.lips_ballistic と同じ規則。あちらは唇先と上面の s 0.25・0.5 の 3 点だけ）。
   除いた行（峰の行の外側の κ の小さい行）の放出と補間の終わりの時刻も書く。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28/ds28_review_checks.py [--out Unity/Build/Design/28/gates/ds28_review_checks.json]
numpy だけ。1 回 約 3〜5 分。パッケージ・生成器は読むだけ。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402

REPO = DG.REPO
PKGS = [("ds27_art_on", "Unity/Build/Design/27/art_on"), ("ds28_art_on", "Unity/Build/Design/28/art_on"),
        ("ds28_art_off_phys", "Unity/Build/Design/28/art_off_phys")]


def volume(ks, pk):
    dc = np.gradient(ks.c)
    taus = np.round(np.arange(-4.6, 1e-9, 0.1), 4)
    vol, am, ap = [], [], []
    for tau in taus:
        A, Y, _ = ks.section(pk.world(float(tau)))
        an, _ = DG.row_areas(A, Y)
        vol.append(float((an * dc).sum()))
        am.append(float(an[ks.main_row]))
        ap.append(float(an[ks.peak_row]))
    vol = np.array(vol)
    kx = int(vol.argmax())
    kn = kx + int(vol[kx:].argmin())
    r1 = lambda v: round(float(v), 1)
    return dict(taus=[float(t) for t in taus], sheet_volume_m3=[r1(v) for v in vol], main_row_Anet_m2=[r1(v) for v in am], peak_row_Anet_m2=[r1(v) for v in ap],
                volume_max=dict(tau=round(float(taus[kx]), 2), m3=r1(vol[kx])), volume_min_after_max=dict(tau=round(float(taus[kn]), 2), m3=r1(vol[kn])),
                volume_tstar_m3=r1(vol[-1]), drop_frac=round(float(1 - vol[kn] / vol[kx]), 4), rise_last_frac=round(float(vol[-1] / vol[kn] - 1), 4))


def lips_all(ks, pk):
    import ds28_model as M8
    g = M8.Generator("art_on")
    fits = []
    skipped = {}
    for r in sorted(g.lip.keys()):
        L = g.lip[r]
        cols = np.asarray(L["cols"])
        Tc = np.asarray(L["Tc"], float)
        Tr = np.broadcast_to(np.asarray(L["Tr"], float), Tc.shape)
        t0 = -Tc + Tr + 0.02
        ok = -t0 >= 0.25
        if not ok.any():
            i = int(np.argmin(Tc))       # 唇先（最初に放たれる点）
            skipped[int(r)] = dict(c_m=round(float(ks.c[r]), 2), kappa=round(float(g.kappa[r]), 3), tip_release_tau=round(float(-Tc.max()), 3),
                                   latest_ramp_end_tau=round(float(t0.min() - 0.02), 3), longest_window_s=round(float(-t0.min()), 3))
            continue
        tmin = float(t0[ok].min())
        tq = np.linspace(tmin, 0.0, int(round(-tmin * 240)) + 1)
        W = pk.sub(tq, r * ks.nu + cols[ok].astype(int), 0)          # (nt, n, 3)
        H_ = (W - ks.O) @ ks.t
        for k, i in enumerate(np.nonzero(ok)[0]):
            m = tq >= t0[i] - 1e-9
            ay = float(2.0 * np.polyfit(tq[m], W[m, k, 1], 2)[0])
            ah = float(2.0 * np.polyfit(tq[m], H_[m, k], 2)[0])
            fits.append((int(r), int(cols[i]), ay, ah))
    fa = np.array([(f[2], f[3]) for f in fits])
    good = (np.abs(fa[:, 0] + 9.81) <= 0.5) & (np.abs(fa[:, 1]) <= 0.5)
    bad = [dict(row=f[0], col=f[1], ay=round(f[2], 2), a_h=round(f[3], 2)) for f, o in zip(fits, good) if not o]
    return dict(ja="設計28 の入れた版の唇の行すべて・唇の列すべて。打ち出しの補間の後（+0.02 s）から t* までの 2 次式の当てはめの加速度（地面、m/s²）。"
                   "窓が 0.25 s 未満の点は除く。skipped_rows は、どの点も窓が 0.25 s に届かない行（打ち出しの補間の終わりが t* の 0.25 s 前より後）",
                rows=len(set(f[0] for f in fits)), points=int(len(fits)), within_0p5=int(good.sum()),
                ay_range=[round(float(fa[:, 0].min()), 3), round(float(fa[:, 0].max()), 3)], a_h_abs_max=round(float(np.abs(fa[:, 1]).max()), 3),
                exceptions=bad[:30], n_exceptions=len(bad), skipped_rows=skipped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Unity", "Build", "Design", "28", "gates", "ds28_review_checks.json"))
    a = ap.parse_args()
    ks = DG.KStar()
    out = dict(schema="GreatWave.DS28.review_checks/1", number="設計28",
               volume=dict(ja="シートの上の本体の水（設計27 の記録 §2.5 の『本体の水』と同じ定義：行ごとの符号付きの断面積 × 行の間隔の和、窓ではない）。"
                              "最大の後の最小（drop_frac）と、最小から t* への戻り（rise_last_frac）。記録のみ", runs={}))
    for key, p in PKGS:
        pk = DG.Package(os.path.join(REPO, p), ks)
        R = volume(ks, pk)
        R.update(package=p, pos_sha256=pk.pos_sha)
        out["volume"]["runs"][key] = R
        print("%s: max %.0f m3 (tau %.1f) -> min %.0f m3 (tau %.1f, -%.1f%%) -> t* %.0f m3 (+%.1f%%)" % (
            key, R["volume_max"]["m3"], R["volume_max"]["tau"], R["volume_min_after_max"]["m3"], R["volume_min_after_max"]["tau"], 100 * R["drop_frac"],
            R["volume_tstar_m3"], 100 * R["rise_last_frac"]), flush=True)
    pk = DG.Package(os.path.join(REPO, "Unity/Build/Design/28/art_on"), ks)
    out["lips_all"] = lips_all(ks, pk)
    L = out["lips_all"]
    print("lips all: %d rows %d points, within 0.5: %d, ay %s, |a_h| max %s, skipped rows %s" % (L["rows"], L["points"], L["within_0p5"], L["ay_range"], L["a_h_abs_max"],
                                                                      sorted(L["skipped_rows"].keys())), flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
