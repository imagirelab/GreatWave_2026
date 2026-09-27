# -*- coding: utf-8 -*-
"""設計28：関門 P20（美術の誘導の大きさの表）。名前の付いた美術の誘導 12 個のそれぞれについて、入れた版（art_on）と、その誘導だけを
切った版（誘導のない動き）の頂点の差（波の枠の局所座標、m）を τ ごとに測り、RMS・最大・最大の場所（行・列・c）・0.05 m を超える
行と列の範囲を表にする。色だけの誘導（ds_tube_white_early・ds_tip_white_line）は T_white の差（頂点の数・最大の差）を書く。
判定はしない（記録。P20 は「別に記録する」ための表）。生成器（ds28_model.Generator）を直接呼ぶ（パッケージの量子化と Hermite を含まない）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28/ds28_p20.py [--out Unity/Build/Design/28/p20/ds28_p20.json]
1 回 約 3〜5 分。
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

REPO = M8.REPO
TAUS = [-12.0, -10.0, -8.0, -6.0, -5.0, -4.5, -4.2, -4.0, -3.6, -3.4, -3.2, -3.0, -2.8, -2.6, -2.4, -2.2, -2.0, -1.8, -1.6, -1.4,
        -1.2, -1.0, -0.8, -0.6, -0.4, -0.2, 0.0]
COLOUR_ONLY = ("ds_tube_white_early", "ds_tip_white_line")
KIND_JA = {
    "ds_body_narrow": "本体の幅（K* の足跡へ狭める）", "ds_back_steep": "背面の急さ（K* の 72°）", "ds_tube_shape": "管の天井・内壁の形を K* へ移す",
    "ds_claws": "唇の縁の鉤・爪（唇の標的）", "ds_lip_target_kstar": "唇を t* に K* へ着くよう逆算", "ds_farwall_hold": "奥の壁を t* まで砕かない",
    "ds_tube_white_early": "管の中の白を着水の前に出す（色だけ）", "ds_swell_calm": "主役波のまわりのうねりを静める", "ds_sea_calm_painting": "t* の原画視点の周りの海を平らにする",
    "ds_approach_kstar": "内壁の錨を K* へ単調に進め、本体の水を保つ（設計28）", "ds_tower_peak": "段階 b の尖った塔（設計28）", "ds_tip_white_line": "段階 c の唇先の白い線（設計28、色だけ）",
}


def f(x, n=4):
    return None if x is None else float(round(float(x), n))


def measure(g_on, g_off, K, taus, name, log):
    rows = []
    for tau in taus:
        X1 = g_on.local(tau)
        X0 = g_off.local(tau)
        d = np.linalg.norm(X1 - X0, axis=-1)
        i = np.unravel_index(int(d.argmax()), d.shape)
        big = d > 0.05
        rr = np.nonzero(big.any(1))[0]
        cc = np.nonzero(big.any(0))[0]
        rows.append(dict(tau=f(tau, 3), rms_m=f(np.sqrt((d ** 2).mean()), 4), max_m=f(d.max(), 3), max_at=dict(row=int(i[0]), col=int(i[1]), c_m=f(K.c[i[0]], 2)),
                         vertices_over_5cm=int(big.sum()), rows_over_5cm=[int(rr.min()), int(rr.max())] if len(rr) else None,
                         cols_over_5cm=[int(cc.min()), int(cc.max())] if len(cc) else None))
    log("  %s：最大 %.2f m（τ %s）" % (name, max(r["max_m"] for r in rows), max(rows, key=lambda r: r["max_m"])["tau"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Unity", "Build", "Design", "28", "p20", "ds28_p20.json"))
    a = ap.parse_args()
    t0 = time.time()

    def log(s):
        print(s, flush=True)
    g_on = M8.Generator("art_on")
    K = g_on.K
    names = list(g_on.sw.keys())
    T_on = g_on.twhite().astype(np.float64)
    out = dict(schema="GreatWave.DS28.p20/1", number="設計28",
               ja="関門 P20：美術の誘導の大きさ（記録）。入れた版（art_on、12 個すべて入れる）と、その誘導だけを切った版の頂点の差（波の枠の局所座標、m）。"
                  "τ は物理の時刻。max_at は最大の頂点（行・列・波峰線の c）。rows/cols_over_5cm は差が 0.05 m を超える行と列の範囲。"
                  "色だけの誘導は形の差 0 で、T_white の差を書く。最後に、すべて切った版（art_off）との差を書く。生成器を直接呼ぶ（パッケージの量子化・Hermite を含まない）。",
               taus=TAUS, guidance={})
    for nm in names:
        g_off = M8.Generator("art_on", switches={nm: False})
        ent = dict(kind_ja=KIND_JA.get(nm, ""))
        if nm in COLOUR_ONLY:
            T_off = g_off.twhite().astype(np.float64)
            fin = (T_on < 1e8) | (T_off < 1e8)
            diff = np.abs(np.where(fin, np.minimum(T_on, 1e3) - np.minimum(T_off, 1e3), 0.0))
            ch = diff > 1e-6
            rr = np.nonzero(ch.any(1))[0]
            ent.update(colour_only=True, twhite_changed_vertices=int(ch.sum()), twhite_max_abs_diff_s=f(diff.max(), 3),
                       twhite_earliest_on=f(float(T_on[ch].min()) if ch.any() else None, 3), twhite_earliest_off=f(float(T_off[ch].min()) if ch.any() else None, 3),
                       rows=[int(rr.min()), int(rr.max())] if len(rr) else None,
                       note_ja="t* の白（最終の色区が白の頂点）の集合は変えない。変わるのは白が出る時刻だけ（T_white、τ の秒。+1e9 は 1e3 に丸めて比べる）")
            # 形は同じはず（確かめ）
            dmax = max(float(np.abs(g_on.local(t) - g_off.local(t)).max()) for t in (-2.4, -1.0, 0.0))
            ent["shape_max_diff_m"] = f(dmax, 6)
            log("  %s：色だけ、T_white が変わる頂点 %d、最大の差 %.3f s" % (nm, int(ch.sum()), diff.max()))
        else:
            ent["per_tau"] = measure(g_on, g_off, K, TAUS, nm, log)
            ent["max_over_tau_m"] = max(r["max_m"] for r in ent["per_tau"])
            ent["rms_max_over_tau_m"] = max(r["rms_m"] for r in ent["per_tau"])
        out["guidance"][nm] = ent
    g_all = M8.Generator("art_off")
    out["all_off"] = dict(kind_ja="12 個すべて切った版（art_off）との差", per_tau=measure(g_on, g_all, K, TAUS, "art_off", log))
    out["runtime_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("DONE %.0f s → %s" % (time.time() - t0, a.out))


if __name__ == "__main__":
    main()
