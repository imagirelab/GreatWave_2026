# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）組み立て：背を直した候補 K*′ AS02B を Unity の主役波の包み（DS27 keypose）へ入れる。

見本は t*（τ = 0）の静止なので、仕上げ32 の hero_pkg（G_p28rec の写し。最後の層 τ = 0 は K*′ P28R2rec そのもの、量子化の差だけ）の
**最後の層（t_star_layer）だけ**を AS02B の .gwb の位置（ワールド − O(0)）に置き換える。ほかの層・T_white・時間曲線は同じ
（動きの作り直しはしていない。τ ∈ (−0.025, 0) の 1 区間だけ、前の層から AS02B の t* へつなぐ補間になる）。
符号化は keypose の pos_format_ja・pos_lo_format_ja のとおり（16 bit ＋ 精度の層 8 bit）。bbox は変えない（AS02B が収まることを確かめる）。
読むのは自分たちの成果物だけ（参照モデルの OBJ・利用者の画像は読まない）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src <hero_pkg> --gwb <AS02B .gwb> --out <新しい hero_pkg>
"""
import argparse
import hashlib
import json
import os
import shutil
import struct

import numpy as np


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def read_gwb_pos(p):
    b = open(p, "rb").read()
    magic, ver, nu, nv, nfr, fps, ts, nt = struct.unpack("<4s4if2i", b[:32])
    n = nu * nv
    o = 32 + n * 16 + nt * 12
    return np.frombuffer(b, np.float32, n * 3, o).reshape(nv, nu, 3).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--gwb", required=True)
    ap.add_argument("--rows", default="")
    ap.add_argument("--meta", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    k = json.load(open(os.path.join(a.src, "ds27_keypose.json"), encoding="utf-8"))
    L, R, C = k["layers"], k["rows"], k["cols"]
    li = int(k["t_star_layer"])
    if abs(float(k["knot_tau"][li])) > 1e-9:
        raise ValueError("t_star_layer の τ が 0 でない")
    bmin = np.array(k["bbox_min"], float)
    bsz = np.array(k["bbox_size"], float)
    O0 = np.array(k["frame"]["origin"][int(np.argmin(np.abs(np.array(k["frame"]["tau"]))))], float)
    X = read_gwb_pos(a.gwb)
    if X.shape != (R, C, 3):
        raise ValueError("格子が違う %r" % (X.shape,))
    u = (X - O0 - bmin) / bsz * 65535.0
    if u.min() < 0 or u.max() > 65535:
        raise ValueError("bbox の外: %r %r" % (u.min(), u.max()))
    q16 = np.clip(np.round(u), 0, 65535)
    e = u - q16
    lo = np.clip(np.round((e + 0.5) * 255.0), 0, 255)
    os.makedirs(a.out, exist_ok=True)
    # 位置の 2 つのファイル：前の包みを写し、最後の層だけ書き換える
    stats = {}
    for name, key, dt, val in (("pos", "pos_file", np.uint16, q16), ("pos_lo", "pos_lo_file", np.uint8, lo)):
        src = os.path.join(a.src, k[key])
        dst = os.path.join(a.out, k[key])
        shutil.copyfile(src, dst)
        mm = np.memmap(dst, dt, "r+", shape=(L, R, C, 4))
        old = np.array(mm[li, ..., :3])
        mm[li, ..., :3] = val.astype(dt)
        mm.flush()
        stats[name] = int((old != val.astype(dt)).any(-1).sum())
        del mm
    # 復号して確かめる
    hi = np.memmap(os.path.join(a.out, k["pos_file"]), np.uint16, "r", shape=(L, R, C, 4))
    lw = np.memmap(os.path.join(a.out, k["pos_lo_file"]), np.uint8, "r", shape=(L, R, C, 4))
    P = bmin + (hi[li, ..., :3].astype(np.float64) + lw[li, ..., :3] / 255.0 - 0.5) / 65535.0 * bsz
    err = float(np.abs(P + O0 - X).max())
    shutil.copyfile(os.path.join(a.src, k["twhite_file"]), os.path.join(a.out, k["twhite_file"]))
    k2 = dict(k)
    k2["number"] = "美術の見本02（Q30-2）組み立て：仕上げ32 の hero_pkg の最後の層（τ = 0）だけを K*′ AS02B（背を一つの山にした候補）に置き換えた写し。" \
                   "ほかの層・T_white・時間曲線は仕上げ32 のまま（動きは作り直していない。見本は t* の静止）。元の number：" + str(k["number"])
    k2["pos_sha256"] = sha256(os.path.join(a.out, k["pos_file"]))
    k2["pos_lo_sha256"] = sha256(os.path.join(a.out, k["pos_lo_file"]))
    k2["tstar"] = dict(k["tstar"], note_ja="最後の層（τ = 0）は K*′ AS02B（Unity/Build/Polish/sample02/back/final/cand）そのもの（量子化の差だけ）。")
    ks = dict(k.get("kstar", {}))
    ks["dir"] = os.path.dirname(a.gwb).replace("\\", "/")
    ks["sha256"] = {"gwb": sha256(a.gwb)}
    if a.rows:
        ks["sha256"]["rows"] = sha256(a.rows)
    if a.meta:
        ks["sha256"]["meta"] = sha256(a.meta)
    k2["kstar"] = ks
    k2["as02_assemble"] = {"src_pkg": a.src.replace("\\", "/"), "src_keypose_sha256": sha256(os.path.join(a.src, "ds27_keypose.json")),
                           "replaced_layer": li, "texels_changed": stats, "max_decode_err_m": err,
                           "note_ja": "τ < 0 の層は G_p28rec（P28R2rec の形成）のまま。%s の背の変化へは τ −0.025 → 0 の 1 区間でつながるので、動きとしては使えない（見本は t* の静止だけ）。" % os.path.basename(a.gwb)}
    with open(os.path.join(a.out, "ds27_keypose.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(k2, f, ensure_ascii=False, indent=None)
    print(json.dumps(k2["as02_assemble"], ensure_ascii=False))
    print("AS02_ASM_PKG_DONE", a.out)


if __name__ == "__main__":
    main()
