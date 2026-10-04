# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4：④ の別の波を確かめるための「仮の主役波」（下げた左側の代わり。形を作る側の本物ではない）。

調べ S の計画 (b) の試算の頂の高さ H_after_b（s4_plan.json の H_profile）を使い、主役波 K*′ AS02C の行ごとに、
断面の高さ y を k(c) = H_after_b / H_now 倍にする（左の白を楔の下の縁まで下げ、c −18 → −26 m で海へ下ろす）。
k が 0 に近い行は海より少し下（最大 0.15 m）へ沈め、海と重ならないようにする。a・c は変えない。
出力（Git 対象外）：Unity/Build/Polish/sample04/wave4/standin/
  standin_rows.npz（A・Y・c。別の波の地面と交わりの検査に使う）、hero_standin.json/.bin（AS04 の静止のメッシュ。mat の hero_smooth_as02c を同じ式で下げた物。
  u・w などの属性は元のまま＝下げた所では弧長が少しずれる。海へ下ろした尾 k < 0.5 の白の印だけ藍にする）。
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_standin.py
"""
import json

import numpy as np

import w4_common as W

OUTD = W.OUT + "/standin"
SINK = 0.15


def kfun():
    P = json.load(open(W.PLAN, encoding="utf-8"))["H_profile"]
    c = np.array(P["c"], float)
    hn = np.array(P["H_now"], float)
    hb = np.array(P["H_after_b"], float)
    k = np.where(hn > 0.05, np.clip(hb / np.maximum(hn, 1e-6), 0, 1), np.where(hb > 0, 1.0, 0.0))
    return c, k


def main():
    c_k, k_k = kfun()
    c, A, Y = W.load_rows(W.HERO_ROWS_AS02C)
    k = np.interp(c, c_k, k_k)
    Y2 = Y * k[:, None] - SINK * (1 - k)[:, None] * (Y > -1)
    np.savez_compressed(OUTD + "/standin_rows.npz", c=c, A=A, Y=Y2, k=k)
    ch, tri, j = W.read_static(W.HERO_MESH_AS02C)
    P = ch["position"].astype(np.float64)
    q = W.K.sec(P)
    kv = np.interp(q[:, 2], c_k, k_k)
    q[:, 1] = q[:, 1] * kv - SINK * (1 - kv)
    P2 = W.K.world(np.zeros(1), q[:, 0][None], q[:, 1][None])[0] + q[:, 2][:, None] * W.K.E
    n = ch["normal"].astype(np.float64)
    # y を k 倍した面の法線：逆転置 → (nx·k, ny, nz·k)
    n2 = np.stack([n[:, 0] * kv, n[:, 1], n[:, 2] * kv], -1)
    n2 /= np.maximum(np.linalg.norm(n2, axis=1, keepdims=True), 1e-12)
    # 海の高さへ下ろした尾（k < 0.5）の白の印は藍にする（白い尾が海の上に平らに残らないように。仮の主役波だけの処置）
    uv5 = ch["uv5"].copy()
    uv5[:, 2] = np.where(kv < 0.5, np.minimum(uv5[:, 2], -2.0), uv5[:, 2])
    ch["uv5"] = uv5
    ch["position"] = P2.astype(np.float32)
    ch["normal"] = n2.astype(np.float32)
    h = W.write_static(OUTD + "/hero_standin.json", ch, tri,
                       {"note_ja": "仮の主役波（見本04 W4 の確かめ用。計画 (b) の H_after_b で y を行ごとに縮めた AS02C。形を作る側の本物ではない）",
                        "source": W.HERO_MESH_AS02C, "source_sha256": j["sha256"]})
    rep = {"schema": "GreatWave.AS04.w4_standin/1", "rows": OUTD + "/standin_rows.npz", "rows_sha256": W.sha(OUTD + "/standin_rows.npz"),
           "mesh": OUTD + "/hero_standin.json", "mesh_bin_sha256": h, "source_rows": W.HERO_ROWS_AS02C, "source_rows_sha256": W.sha(W.HERO_ROWS_AS02C),
           "plan": W.PLAN, "plan_sha256": W.sha(W.PLAN), "sink_m": SINK,
           "k_by_c": {"%.1f" % cc: W.rnd(float(np.interp(cc, c_k, k_k))) for cc in (-30, -26, -24, -22, -20, -18, -17, -16, -15, -14, -13, -12, -10)},
           "crest_after_m": {"%.1f" % cc: W.rnd(float(np.interp(cc, c, Y2[:, 18:200].max(1)))) for cc in (-26, -22, -18, -17, -15, -13, -12, -10, -8)}}
    W.jdump(OUTD + "/standin_report.json", rep)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    import os
    os.makedirs(OUTD, exist_ok=True)
    main()
