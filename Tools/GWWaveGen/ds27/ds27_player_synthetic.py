# -*- coding: utf-8 -*-
"""設計27：Unity の DS27 keypose 再生（DS27KeyposePlayer）を試すための合成パッケージと時間曲線を作る（試験用。作品の波ではない）。

生成器（設計27 の本体）の出力がまだない段階で、再生側を約束（ds27_player_ref.py の冒頭）どおりに試すためのもの。
- 形：K*（26修正01 の kstar_a45.gwb）を波の枠の局所座標にし（局所 = K* − O0、O0 = K* の断面の原点）、節点ごとに
  高さを s(τ) = 0.25 + 0.75·exp(τ/2.5) 倍し、進行方向へ 0.8 m·sin(0.12 c + 0.9 τ)·(1 − exp(τ/2.5)) だけ揺らす
  （c は波峰線方向の位置）。τ = 0 で s = 1・揺れ 0 なので、最後の層は K* そのもの（量子化の差だけ）。
- 節点：τ = −12.0, −9.0, −6.5, −4.2, −3.0, −2.1, −1.3, −0.6, 0.0（9 層、不等間隔。代案の時間曲線の τ(0) = −12 s まで覆う）。
- 波の枠の原点：O(τ) = O0 + X(τ)·t（t は K* の進行方向）。速さは 20 m/s、τ −2.4〜−1.6 s で 16 m/s へ滑らかに落とす。240 Hz。
- T_white：美術優先31 の T_white（体験の秒、t* = 12 s）を τ = T − 12 へずらしたもの（試験用）。
  --never を付けた版（art_off）は、管の天井と内壁の列（K* の j_corner 314〜j_facebot 379）を +1e9（t* まで白にならない）にする。
- 時間曲線（試験用の写し）：既定（設計26 §3.2、tw_gate.py の 'new'：r0 0.5、減速 1 s、止める 0.4 s、最初の唇先の頂点 τ −1.432 s）と
  代案（実時間のまま t* で瞬間に止める：τ = min(t − 12, 0)）。t = 0〜14 s を 240 Hz（本番の表は生成器が Tools/GWWaveGen/ds27/ に書く）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds27/ds27_player_synthetic.py --out <フォルダー>
出力：<out>/art_on/（ds27_pos_rgba16.bin・ds27_keypose.json・ds27_twhite_r32f.bin）、<out>/art_off/（同じ位置、T_white だけ違う）、
      <out>/timewarp_default.json・timewarp_alt.json。numpy だけを使う。
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ds27_player_ref import REPO, read_kstar, sha256_file, save_json, load_json  # noqa: E402

KSTAR_META = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45_meta.json")
AF31_TW = os.path.join(REPO, "Unity", "Build", "ArtFirst", "31", "white", "af31_twhite_r32f.bin")
AF31_TW_SHA256 = "8a18f2e08a23e139e5cee071ae2a8a9311b06ae095acec6c82c5120c275ea73d"
KNOTS = [-12.0, -9.0, -6.5, -4.2, -3.0, -2.1, -1.3, -0.6, 0.0]
T_STAR = 12.0
T_END = 14.0
HZ = 240


def S(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def Sd(x):
    return np.where((x > 0) & (x < 1), 6.0 * x * (1.0 - x), 0.0)


def timewarp(kind, tau_ap=-1.432, r0=0.5, d1=1.0, tf=0.4):
    """t（0〜14 s）→ τ。設計26 §3.2 の既定（tw_gate.py の build('new')）と代案（実時間＋t* で瞬間に止める）。"""
    DT = 1e-4
    t = np.arange(0.0, T_END + DT / 2, DT)
    if kind == "default":
        Lc = (abs(tau_ap) - r0 * tf / 2) / r0
        t_ap = T_STAR - tf - Lc
        t1 = t_ap - d1
        r = np.ones_like(t)
        m = (t >= t1) & (t < t_ap)
        r[m] = 1 - (1 - r0) * S((t[m] - t1) / d1)
        m = (t >= t_ap) & (t < T_STAR - tf)
        r[m] = r0
        m = (t >= T_STAR - tf) & (t < T_STAR)
        r[m] = r0 * (1 - S((t[m] - (T_STAR - tf)) / tf))
        r[t >= T_STAR] = 0.0
        seg = {"ramp_start_t": t1, "apex_t": t_ap, "freeze_ramp_start_t": T_STAR - tf, "r0": r0, "hold_s": [T_STAR, T_END]}
    elif kind == "alt":
        r = np.where(t < T_STAR, 1.0, 0.0)
        seg = {"real_time_until_t": T_STAR, "instant_freeze_at_t": T_STAR, "hold_s": [T_STAR, T_END]}
    else:
        raise ValueError(kind)
    tau = np.concatenate([[0.0], np.cumsum((r[1:] + r[:-1]) / 2 * DT)])
    tau -= tau[int(round(T_STAR / DT))]
    ts = np.round(np.arange(0, int(round(T_END * HZ)) + 1) / HZ, 9)
    taus = np.interp(ts, t, tau) if kind == "default" else np.minimum(ts - T_STAR, 0.0)   # 代案は式のまま（台形の積分の丸めを入れない）
    taus[ts >= T_STAR] = 0.0
    return {"schema": "GreatWave.DS27.timewarp/1", "kind": kind, "synthetic_test_copy": True,
            "note_ja": "再生側の試験用の写し（ds27_player_synthetic.py）。本番の表は設計27 の生成器が Tools/GWWaveGen/ds27/timewarp_%s.json に書く。" % kind,
            "t_star_s": T_STAR, "rate_hz": HZ, "segments": seg, "t": ts.tolist(), "tau": [float(x) for x in taus]}


def frame_origin(O0, tvec):
    ftau = np.round(np.arange(int(round(-12.5 * HZ)), 1) / HZ, 9)
    DT = 1e-4
    tt = np.arange(-12.5, 0.0 + DT / 2, DT)
    c = 20.0 - 4.0 * S((tt + 2.4) / 0.8)
    X = np.concatenate([[0.0], np.cumsum((c[1:] + c[:-1]) / 2 * DT)])
    X -= X[-1]
    Xs = np.interp(ftau, tt, X)
    org = O0[None, :] + Xs[:, None] * tvec[None, :]
    return ftau, org


def write_version(out, name, Lq, lo, size, knots, ftau, forg, tw, extra):
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    pp = os.path.join(d, "ds27_pos_rgba16.bin")
    Lq.tofile(pp)
    tp = os.path.join(d, "ds27_twhite_r32f.bin")
    tw.astype("<f4").tofile(tp)
    meta = {"schema": "GreatWave.DS27.keypose/1", "synthetic_test_package": True,
            "note_ja": "Unity の DS27KeyposePlayer の試験用の合成パッケージ（ds27_player_synthetic.py）。作品の波ではない。",
            "layers": int(Lq.shape[0]), "rows": int(Lq.shape[1]), "cols": int(Lq.shape[2]),
            "bbox_min": [float(v) for v in lo], "bbox_size": [float(v) for v in size], "knot_tau": [float(v) for v in knots],
            "frame": {"tau": [float(v) for v in ftau], "origin": [[float(a), float(b), float(c)] for a, b, c in forg]},
            "pos_sha256": sha256_file(pp), "twhite_file": "ds27_twhite_r32f.bin", "twhite_sha256": sha256_file(tp),
            "pre_white_index": 2}
    meta.update(extra)
    save_json(os.path.join(d, "ds27_keypose.json"), meta)
    return d, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    nu, nv, tris, X = read_kstar()
    km = load_json(KSTAR_META)["frame"]
    O0 = np.asarray(km["section_origin_world"], np.float64)
    tv = np.asarray(km["t_travel"], np.float64)
    ev = np.asarray(km["e_crest"], np.float64)
    L0 = X - O0[None, :]
    a = L0 @ tv
    y = L0[:, 1].copy()
    c = L0 @ ev
    layers = []
    for tau in KNOTS:
        g = np.exp(tau / 2.5)
        s = 0.25 + 0.75 * g
        wob = 0.8 * np.sin(0.12 * c + 0.9 * tau) * (1.0 - g)
        Lk = (a + wob)[:, None] * tv[None, :] + (y * s)[:, None] * np.array([0.0, 1.0, 0.0])[None, :] + c[:, None] * ev[None, :]
        layers.append(Lk)
    Ls = np.stack(layers)                        # (層, N, 3)
    last_vs_kstar = float(np.abs(Ls[-1] - L0).max())
    lo = Ls.reshape(-1, 3).min(0) - 0.01
    hi = Ls.reshape(-1, 3).max(0) + 0.01
    size = hi - lo
    q = np.clip(np.round((Ls - lo) / size * 65535.0), 0, 65535).astype("<u2")
    Lq = np.concatenate([q, np.full(q.shape[:-1] + (1,), 65535, "<u2")], -1).reshape(len(KNOTS), nv, nu, 4)
    deq = lo + q.astype(np.float64) / 65535.0 * size
    qerr = float(np.linalg.norm(deq - Ls, axis=-1).max())
    ftau, forg = frame_origin(O0, tv)
    if sha256_file(AF31_TW) != AF31_TW_SHA256:
        raise SystemExit("美術優先31 の T_white の SHA-256 が違います。")
    tw31 = np.fromfile(AF31_TW, "<f4").astype(np.float64)
    tw_on = (tw31 - T_STAR).astype(np.float32)
    tw_off = tw_on.copy().reshape(nv, nu)
    tw_off[:, 314:380] = 1.0e9
    tw_off = tw_off.reshape(-1)
    common = {"kstar_gwb_sha256": hashlib.sha256(open(os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb"), "rb").read()).hexdigest(),
              "quantization_max_err_m": qerr, "last_layer_vs_kstar_local_max_m": last_vs_kstar,
              "origin_at_tstar": [float(v) for v in forg[-1]], "twhite_source_ja": "美術優先31 の T_white（SHA-256 %s…）− 12 s" % AF31_TW_SHA256[:12]}
    d_on, m_on = write_version(out, "art_on", Lq, lo, size, KNOTS, ftau, forg, tw_on, dict(common, version="art_on"))
    d_off, m_off = write_version(out, "art_off", Lq, lo, size, KNOTS, ftau, forg, tw_off,
                                 dict(common, version="art_off", never_columns_ja="列 314〜379（管の天井・内壁）の T_white を +1e9（試験用）"))
    for kind in ("default", "alt"):
        save_json(os.path.join(out, "timewarp_%s.json" % kind), timewarp(kind))
    tw_d = load_json(os.path.join(out, "timewarp_default.json"))
    print("DS27_SYNTH layers=%d quant_err=%.5f m last_vs_kstar=%.2e m origin_samples=%d tau(t=0) default=%.4f alt=%.4f -> %s" % (
        len(KNOTS), qerr, last_vs_kstar, len(ftau), tw_d["tau"][0], load_json(os.path.join(out, "timewarp_alt.json"))["tau"][0], out))


if __name__ == "__main__":
    main()
