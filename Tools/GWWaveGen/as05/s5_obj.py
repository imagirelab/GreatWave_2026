# -*- coding: utf-8 -*-
"""美術の見本05 の調べ（Q33）：参照モデル（他者の展示作品のスキャン。参考にとどめ写し取らない）の左の大きな形から、
三つの層の「数だけ」を測る。生成器はこのファイルも OBJ も読まない。形・頂点・断面・画像はリポジトリにも成果物にも書かない。

測る物（大きな形だけ）：
  1. 上から見た高さの場 h(a, c) の峰と、峰ごとの突出（自分より高い所へ行く道の最も高い鞍まで）、鞍の場所、峰の前後（a）の位置。
  2. c ごとの頂の高さ H(c) と、頂の a（主の頂の線がどこを通るか）。
  3. 峰のある c の断面で、前の縁（高さ 0.2 H 以上で a が最大の点）と、その下の面の引っ込み（前の縁から 0.1〜0.3 H 下の a の最小）。
参照モデル G:/research/model/wave_repair_zbrush2.obj を読み取りのみで開き、SHA-256 を照合し、整列 B（align_B_upright.json）で
主役波の断面の座標へ移す。**ファイルへのキャッシュは書かない**（メモリの中だけで測り、終わったら捨てる）。照合と実行の記録は
Unity/Build/Polish/sample05/study/s5_obj_log.json。出力：Unity/Build/Polish/sample05/study/s5_obj_numbers.json（数だけ。Git 対象外のまま）。
使い方：py -3.10 -B Tools/GWWaveGen/as05/s5_obj.py
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_common as S  # noqa: E402

SRC = r"G:\research\model\wave_repair_zbrush2.obj"
SRC_SHA = "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40"
ALIGN = S.REPO + "/Docs/Evidence/ArtFirst/26/reference/align_B_upright.json"
LOG = S.OUT + "/s5_obj_log.json"
OUTJ = S.OUT + "/s5_obj_numbers.json"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_obj_vertices():
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    if h != SRC_SHA:
        raise SystemExit("参照モデルの SHA-256 が違うので使わない: " + h)
    V = []
    for l in raw.split(b"\n"):
        if l.startswith(b"v "):
            V.append(l.split()[1:4])
    del raw
    V = np.array(V, dtype=np.float64)
    M4 = np.array(json.load(open(ALIGN, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    return Vu, h, len(V)


def sections(Q, cvals, H):
    out = []
    for c0 in cvals:
        m = np.abs(Q[:, 2] - c0) < 0.35
        q = Q[m]
        if len(q) < 50:
            continue
        top = q[np.argmax(q[:, 1])]
        hi = q[q[:, 1] >= 0.2 * H]
        fe = hi[np.argmax(hi[:, 0])] if len(hi) else None
        rec = {"c": S.rnd(c0, 2), "crest_y_over_H": S.rnd(top[1] / H), "crest_a": S.rnd(top[0], 2)}
        if fe is not None:
            rec.update({"front_edge_a": S.rnd(fe[0], 2), "front_edge_y_over_H": S.rnd(fe[1] / H)})
            for lo, hi_ in ((0.1, 0.2), (0.2, 0.3)):
                band = q[(q[:, 1] <= fe[1] - lo * H) & (q[:, 1] >= fe[1] - hi_ * H) & (q[:, 0] > fe[0] - 15)]
                # 外の面（前の縁の下で、手前を向く面）の前の端：高さの帯ごとの a の最大の最小
                if len(band):
                    yb = np.round(band[:, 1] / 0.25)
                    amax = [band[yb == k, 0].max() for k in np.unique(yb)]
                    rec["recess_%.1f_%.1fH_below_front" % (lo, hi_)] = S.rnd(fe[0] - min(amax), 2)
        out.append(rec)
    return out


def main():
    t0 = time.time()
    log = {"source": os.path.basename(SRC), "source_sha256_expected": SRC_SHA, "events": []}
    Vu, h, nv = load_obj_vertices()
    log["events"].append({"event": "read_in_memory", "utc": now(), "source_sha256_checked": h, "n_vertices": nv,
                          "cache_written": False, "align": os.path.relpath(ALIGN, S.REPO).replace("\\", "/"), "align_sha256": S.sha(ALIGN)})
    Q = S.K.sec(Vu)
    del Vu
    Q = Q[Q[:, 1] > 0.3]           # 台・海面のすぐ上は除く
    H = float(Q[:, 1].max())
    hgt, g = S.heightfield(Q)
    pk = S.crest_layers(hgt, g, grow_px=60.0, rad_m=1.5, hmin=0.15 * H)
    # c ごとの頂
    cb = np.arange(-20.0, 16.01, 1.0)
    prof = []
    for c0 in cb:
        m = np.abs(Q[:, 2] - c0) < 0.5
        if m.sum() < 20:
            continue
        j = np.argmax(Q[m, 1])
        prof.append({"c": S.rnd(c0, 1), "H_over_Href": S.rnd(Q[m, 1][j] / H), "crest_a": S.rnd(Q[m, 0][j], 2)})
    secs = sections(Q, [-16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4], H)
    res = {"note_ja": "参照モデル（他者の展示作品のスキャン）の大きな形の数だけ。整列 B は大まかで、原画の画素の区域の位置は 50〜130 原画画素ずれる"
                      "（見本04 の調べ S-4）。区域の判定は ±60 画素まで広げた。リポジトリへ入れない。",
           "H_ref_m": S.rnd(H, 2), "heightfield_grid": g, "peaks": pk, "crest_profile": prof, "sections": secs,
           "seconds": round(time.time() - t0, 1)}
    S.jdump(OUTJ, res)
    del Q
    log["events"].append({"event": "numbers_written_memory_released", "utc": now(), "output": os.path.relpath(OUTJ, S.REPO).replace("\\", "/")})
    S.jdump(LOG, log)
    print(json.dumps({k: v for k, v in res.items() if k in ("H_ref_m", "seconds")}, ensure_ascii=False))
    for p in pk[:14]:
        print(json.dumps(p, ensure_ascii=False))
    for r in prof:
        print(r)
    for r in secs:
        print(r)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
