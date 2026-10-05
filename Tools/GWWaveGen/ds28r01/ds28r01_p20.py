# -*- coding: utf-8 -*-
"""設計28修正01：P20（美術の誘導の大きさ、記録）の足し。設計28修正01 で足した ds_rise_overlap の大きさを、入れた版（設計28修正01 の art_on）と
その誘導だけを切った版（＝設計28 の入れた版 art_on。ds_rise_overlap を切ると設計28 と同じ動きになる）の頂点の差で測る。
切った版（art_off）が設計28 の切った版（物理だけ、art_off_phys）と同じバイトかも確かめる。

どちらのパッケージも ds27_gates.Package（量子化した keypose の Hermite）で読むので、差には量子化（最大 約 1.2 mm）が入る。
使い方（リポジトリの根で。約 1 分）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_p20.py [--out Unity/Build/Design/28R01/p20/ds28r01_p20.json]
生成器を直接呼ぶ測り方（1 つ 約 4〜6 分）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_p20.py --direct rise_off|no_water_override|no_tower_override
  （出力 Unity/Build/Design/28R01/p20/ds28r01_p20_direct_<variant>.json。修正01 の既定とその版の差、量子化なし）
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402

REPO = DG.REPO
B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
BR = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
TAUS = [-12.0, -10.0, -8.0, -6.0, -5.0, -4.5, -4.2, -4.0, -3.6, -3.4, -3.2, -3.0, -2.8, -2.6, -2.4, -2.2, -2.0, -1.8, -1.6, -1.4,
        -1.2, -1.0, -0.8, -0.6, -0.4, -0.2, 0.0]
f = DG.fnum


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BR, "p20", "ds28r01_p20.json"))
    a = ap.parse_args()
    ks = DG.KStar()
    on = DG.Package(os.path.join(BR, "art_on"), ks)
    ref = DG.Package(os.path.join(B28, "art_on"), ks)
    mr, pr = ks.main_row, ks.peak_row
    rows = []
    for tau in TAUS:
        X1 = on.local(tau)
        X0 = ref.local(tau)
        dd = np.linalg.norm(X1 - X0, axis=-1)
        i = np.unravel_index(int(dd.argmax()), dd.shape)
        A1, Y1, _ = ks.section(X1 + ks.O)
        A0, Y0, _ = ks.section(X0 + ks.O)
        r1 = DG.row_metrics(A1, Y1, ks.crest_hi, ks.j_E)
        r0 = DG.row_metrics(A0, Y0, ks.crest_hi, ks.j_E)
        big = dd > 0.05
        rows.append(dict(tau=f(tau, 3), rms_m=f(float(np.sqrt((dd ** 2).mean())), 4), max_m=f(float(dd.max()), 3),
                         max_at=dict(row=int(i[0]), col=int(i[1]), c_m=f(ks.c[i[0]], 2)), vertices_over_5cm=int(big.sum()),
                         crest_H_diff_m={"main": f(float(r1["H"][mr] - r0["H"][mr]), 3), "peak": f(float(r1["H"][pr] - r0["H"][pr]), 3)},
                         Lo_over_H={"main": [f(float(r0["Lo"][mr] / r0["H"][mr]), 3), f(float(r1["Lo"][mr] / r1["H"][mr]), 3)],
                                    "peak": [f(float(r0["Lo"][pr] / r0["H"][pr]), 3), f(float(r1["Lo"][pr] / r1["H"][pr]), 3)]}))
    k = max(rows, key=lambda r: r["max_m"])
    first = next((r["tau"] for r in rows if r["max_m"] > 0.005), None)
    # 切った版が設計28 の切った版（物理だけ）と同じか
    jo = json.load(open(os.path.join(BR, "art_off", "ds27_keypose.json"), encoding="utf-8"))
    jr = json.load(open(os.path.join(B28, "art_off_phys", "ds27_keypose.json"), encoding="utf-8"))
    same_off = dict(pos_sha256_28r01=jo["pos_sha256"], pos_sha256_28=jr["pos_sha256"], same_pos=jo["pos_sha256"] == jr["pos_sha256"],
                    twhite_same=jo["twhite_sha256"] == jr["twhite_sha256"])
    jn = json.load(open(os.path.join(BR, "art_on", "ds27_keypose.json"), encoding="utf-8"))
    jd = json.load(open(os.path.join(B28, "art_on", "ds27_keypose.json"), encoding="utf-8"))
    rep = dict(schema="GreatWave.DS28R01.p20/1", number="設計28修正01", tool=DG.rel(os.path.abspath(__file__)),
               guidance=dict(ds_rise_overlap=dict(
                   kind_ja="頂の高さの時刻の表（噴流の始まりで 0.73H*、t* まで 0.105〜0.12 H*/s で上がり続ける）と、それに合わせた唇の打ち出しの解き直し",
                   on_ja="設計28修正01 の入れた版（art_on）", off_ja="設計28 の入れた版（art_on）＝ds_rise_overlap だけを切った動き",
                   max_m=k["max_m"], max_tau=k["tau"], max_at=k["max_at"], rms_max_m=max(r["rms_m"] for r in rows), first_tau_over_5mm=first,
                   at_tstar=dict(rms_m=rows[-1]["rms_m"], max_m=rows[-1]["max_m"]), per_tau=rows,
                   twhite_same=jn["twhite_sha256"] == jd["twhite_sha256"])),
               art_off_equals_ds28_art_off_phys=same_off,
               note_ja="差は量子化した keypose どうし（量子化の最大 約 1.2 mm を含む）。t* ではどちらも K*（差は量子化だけ）。")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1)
    print("[ds28r01_p20] ds_rise_overlap 最大 %.2f m（τ %s、行 %d）、RMS の最大 %.2f m、t* %.4f m；切った版 = 設計28 の物理だけ：%s → %s" % (
        k["max_m"], k["tau"], k["max_at"]["row"], rep["guidance"]["ds_rise_overlap"]["rms_max_m"], rows[-1]["max_m"], same_off["same_pos"], a.out))



# ---------------------------------------------------------------- 生成器を直接呼ぶ測り方（誘導を 1 つだけ切る）
DIRECT_VARIANTS = {
    "rise_off": "ds_rise_overlap を切る（＝設計28 の入れた版の動き。下の 2 つの上書きも一緒に消える）",
    "no_water_override": "ds_approach_kstar の水の釣り合いの上書き（band_frac 0.15）だけを消す（設計28 の 0.06）",
    "no_tower_override": "ds_tower_peak の時刻の上書き（−0.1 s）だけを消す（設計28 の表）",
}


def direct(variant, out):
    """設計28修正01 の入れた版（既定）と、variant の版の頂点の差（波の枠の局所座標、生成器を直接。量子化なし）。"""
    import copy as _copy
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    sys.path.insert(0, HERE)
    import ds28r01_model as MR
    R = json.load(open(MR.PARAMS_R01, encoding="utf-8"))
    kw = {}
    if variant == "rise_off":
        kw = dict(rise_overlap=False)
    else:
        R2 = _copy.deepcopy(R)
        if variant == "no_water_override":
            R2["approach"].pop("water_overrides", None)
        elif variant == "no_tower_override":
            R2.pop("tower_overrides", None)
        else:
            raise SystemExit("知らない variant")
        tmp = os.path.join(os.path.dirname(os.path.abspath(out)), "params_%s.json" % variant)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        json.dump(R2, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        kw = dict(r01_path=tmp)
    g1 = MR.Generator("art_on")
    g0 = MR.Generator("art_on", **kw)
    K = g1.K
    rows = []
    for tau in TAUS:
        X1 = g1.local(tau)
        X0 = g0.local(tau)
        dd = np.linalg.norm(X1 - X0, axis=-1)
        i = np.unravel_index(int(dd.argmax()), dd.shape)
        _, y1 = g1.crest(tau)[:2]
        _, y0 = g0.crest(tau)[:2]
        rows.append(dict(tau=f(tau, 3), rms_m=f(float(np.sqrt((dd ** 2).mean())), 4), max_m=f(float(dd.max()), 3),
                         max_at=dict(row=int(i[0]), col=int(i[1]), c_m=f(K.c[i[0]], 2)), vertices_over_5cm=int((dd > 0.05).sum()),
                         crest_y_diff_m={"main": f(float(y1[K.main_row] - y0[K.main_row]), 3), "peak": f(float(y1[192] - y0[192]), 3)}))
    k = max(rows, key=lambda r: r["max_m"])
    first = next((r["tau"] for r in rows if r["max_m"] > 0.005), None)
    T1, T0 = g1.twhite(), g0.twhite()
    ch = np.abs(T1.astype(np.float64) - T0.astype(np.float64)) > 1e-6
    rep = dict(variant=variant, kind_ja=DIRECT_VARIANTS[variant], variant_generator=g0.variant, max_m=k["max_m"], max_tau=k["tau"], max_at=k["max_at"],
               rms_max_m=max(r["rms_m"] for r in rows), first_tau_over_5mm=first, at_tstar=dict(rms_m=rows[-1]["rms_m"], max_m=rows[-1]["max_m"]),
               twhite_changed_vertices=int(ch.sum()), per_tau=rows, note_ja="生成器を直接呼んだ差（量子化・Hermite を含まない）。入れた版は設計28修正01 の既定（art_on）")
    with open(out, "w", encoding="utf-8", newline="\n") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1)
    print("[ds28r01_p20 direct] %s：最大 %.3f m（τ %s、行 %d 列 %d）、RMS の最大 %.3f m、t* %.4f m → %s" % (
        variant, k["max_m"], k["tau"], k["max_at"]["row"], k["max_at"]["col"], rep["rms_max_m"], rows[-1]["max_m"], out))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        v = sys.argv[2]
        direct(v, sys.argv[3] if len(sys.argv) > 3 else os.path.join(BR, "p20", "ds28r01_p20_direct_%s.json" % v))
    else:
        main()
