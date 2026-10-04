# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデル（他者の展示作品のスキャン。Q5・Q18〜Q20。参考にとどめ写し取らない）から、
波頭の冠・面の彫り・大きさの比を「数だけ」測る。生成器はこのファイルも OBJ も読まない（F13-1）。
形・頂点・断面・画像はリポジトリにも成果物にも書かない（数だけの JSON。確かめの一時の図はキャッシュのフォルダーに置き、delete で消す）。

参照モデル G:/research/model/wave_repair_zbrush2.obj を読み取りのみで開き、SHA-256 を照合してから、作業計画 9.4 の整列
（解B、Docs/Evidence/ArtFirst/26/reference/align_B_upright.json）で Unity の世界へ置き、さらに主役波の断面の座標
（kh_common.sec：a = 進行方向 T、y = 高さ、c = 波峰線 E）へ移した一時キャッシュ（Git 対象外の
Unity/Build/Polish/sample03/study/_objcache_s1/）を作る。測り終えたらキャッシュを消し、消したファイルの SHA-256 を記録する。

使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/as03/s1_obj.py cache
    py -3.10 -B Tools/GWWaveGen/as03/s1_obj.py overview
    py -3.10 -B Tools/GWWaveGen/as03/s1_obj.py delete
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
SRC = r"G:\research\model\wave_repair_zbrush2.obj"
SRC_SHA = "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40"
ALIGN = REPO + "/Docs/Evidence/ArtFirst/26/reference/align_B_upright.json"
STUDY = REPO + "/Unity/Build/Polish/sample03/study"
CACHE_DIR = STUDY + "/_objcache_s1"
CACHE = CACHE_DIR + "/ref_sec_tmp.npz"
LOG = STUDY + "/s1_objcache_log.json"
OUT = STUDY + "/s1_obj_numbers.json"

# 主役波の断面の座標（Tools/GWWaveGen/kstar_h/kh_common.py と同じ値）
E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def load_log():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding="utf-8"))
    return {"source": os.path.basename(SRC), "source_sha256": SRC_SHA, "events": []}


def save_log(d):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def sec(P):
    Q = P - O
    return np.stack([Q @ T, Q[:, 1], Q @ E], -1)


def cmd_cache():
    t0 = time.time()
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    if h != SRC_SHA:
        raise SystemExit("参照モデルの SHA-256 が違うので使わない: " + h)
    lines = raw.split(b"\n")
    del raw
    V = np.array([l.split()[1:4] for l in lines if l.startswith(b"v ")], dtype=np.float64)
    tris, quads = [], []
    for l in lines:
        if not l.startswith(b"f "):
            continue
        p = [int(x.split(b"/")[0]) - 1 for x in l.split()[1:]]
        if len(p) == 3:
            tris.append(p)
        elif len(p) == 4:
            quads.append(p)
        else:
            for j in range(1, len(p) - 1):
                tris.append([p[0], p[j], p[j + 1]])
    del lines
    Q = np.array(quads, np.int64).reshape(-1, 4)
    Tt = np.array(tris, np.int64).reshape(-1, 3)
    F = np.vstack([Tt, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
    M4 = np.array(json.load(open(ALIGN, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    Vs = sec(Vu)
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(CACHE, V=Vs.astype(np.float32), F=F)
    d = load_log()
    d["events"].append({"event": "cache_created", "file": os.path.relpath(CACHE, REPO).replace("\\", "/"), "sha256": sha256_file(CACHE),
                        "bytes": os.path.getsize(CACHE), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "seconds": round(time.time() - t0, 1), "source_sha256_checked": h, "n_v": int(len(V)), "n_f_tri": int(len(F)),
                        "align": os.path.relpath(ALIGN, REPO).replace("\\", "/"), "align_sha256": sha256_file(ALIGN),
                        "frame": "kh_common.sec (a = T, y, c = E)"})
    save_log(d)
    print("cache", CACHE, len(V), len(F), "%.1fs" % (time.time() - t0))


def cmd_delete():
    d = load_log()
    if os.path.isdir(CACHE_DIR):
        for nm in sorted(os.listdir(CACHE_DIR)):
            fp = os.path.join(CACHE_DIR, nm)
            if os.path.isfile(fp):
                s = sha256_file(fp)
                os.remove(fp)
                d["events"].append({"event": "cache_deleted", "file": os.path.relpath(fp, REPO).replace("\\", "/"), "sha256": s,
                                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    left = os.listdir(CACHE_DIR) if os.path.isdir(CACHE_DIR) else []
    if os.path.isdir(CACHE_DIR) and not left:
        os.rmdir(CACHE_DIR)
    d["cache_dir_exists_after_delete"] = os.path.isdir(CACHE_DIR)
    save_log(d)
    print("deleted; left:", left)


def load():
    z = np.load(CACHE)
    return z["V"].astype(np.float64), z["F"]


def cmd_overview():
    V, F = load()
    print("bbox a", V[:, 0].min(), V[:, 0].max(), " y", V[:, 1].min(), V[:, 1].max(), " c", V[:, 2].min(), V[:, 2].max())
    # c ごとに、最も高い点（頂）と、その a
    cb = np.arange(np.floor(V[:, 2].min()), np.ceil(V[:, 2].max()) + 0.5, 0.5)
    idx = np.digitize(V[:, 2], cb)
    for k in range(1, len(cb)):
        s = idx == k
        if s.sum() < 10:
            continue
        P = V[s]
        j = np.argmax(P[:, 1])
        hi = P[P[:, 1] > P[j, 1] - 0.5]
        print("c %6.1f  n %6d  ymax %6.2f at a %6.2f   a-range at top0.5m %6.2f..%6.2f   a-range all %6.2f..%6.2f" % (
            cb[k - 1], s.sum(), P[j, 1], P[j, 0], hi[:, 0].min(), hi[:, 0].max(), P[:, 0].min(), P[:, 0].max()))


if __name__ == "__main__":
    {"cache": cmd_cache, "delete": cmd_delete, "overview": cmd_overview}[sys.argv[1]]()
