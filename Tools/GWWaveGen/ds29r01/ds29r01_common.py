# -*- coding: utf-8 -*-
"""設計29修正01：設計29 の検査器（ds29_qa.py・ds29_review_checks.py）を、ファイルを変えずに、
(1) 精度の層（ds27_pos_lo_rgba8.bin、設計28修正01 の試行E で足した後方互換の追加）つきの復号と、
(2) 別の K*（設計28修正01 の K*′ = Unity/Build/Design/28R01F/kstar_final など）で走らせるための差し替え。

差し替え（同じプロセスの中だけ。元のファイルは変えない）
  - ds27_gates の KSTAR_DIR・KStar の既定の引数・SHA256 の表：設計28修正01 の包み ds28r01d_gates.patch_kstar と同じ（K* のフォルダーを渡す）。
    ds29_qa の巻きの行・唇の列・断面の面は、この K* から作られる。
  - ds29_qa.PackageSurface：ds27_keypose.json の extensions に "pos_lo_rgba8/1" があり、decode="fine" なら、層の位置を
    位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size で復号する（ds28r01e_generate.py の export_lo の約束。刻み ≈ 6.9 µm）。
    decode="hi" は設計27〜29 の再生器と同じ 16 bit だけの読み（刻み ≈ 1.7 mm）。どちらも float32 に丸めて持つ（GPU の読みに合わせる。元の検査器と同じ）。
    量子化の半径 q_max（(5b)〜(5d) の許し）は、fine では 16 bit の 1/255 にする。
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for sub in ("ds29", "ds27", "ds28", "ds28r01", "ds28r01d"):
    p = os.path.abspath(os.path.join(HERE, "..", sub))
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_KSTAR = "Unity/Build/Design/28R01F/kstar_final"
DEFAULT_PACKAGE = "Unity/Build/Design/28R01F/F_final/art_on"
OUT_ROOT = os.path.join(REPO, "Unity", "Build", "Design", "29R01")
LO_EXT = "pos_lo_rgba8/1"

STATE = dict(decode="fine", kstar=None)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def setup(kstar=DEFAULT_KSTAR, decode="fine"):
    """K* と復号の差し替えを入れる。戻り値：ds29_qa のモジュール。"""
    if decode not in ("fine", "hi"):
        raise SystemExit("decode は fine か hi")
    STATE["decode"] = decode
    import ds28r01d_gates as DGW
    kdir = kstar if os.path.isabs(kstar) else os.path.join(REPO, kstar)
    STATE["kstar"] = DGW.patch_kstar(kdir)
    STATE["kstar_src"] = rel(kdir)
    import ds29_qa as Q
    if getattr(Q.PackageSurface, "_ds29r01_patched", False):
        return Q
    orig_init = Q.PackageSurface.__init__
    orig_info = Q.PackageSurface.info

    def init(self, d, label=None):
        orig_init(self, d, label)
        J = self.meta
        self.decode = STATE["decode"]
        self.raw_lo = None
        self.q_max_hi = self.q_max
        has_lo = LO_EXT in (J.get("extensions") or [])
        self.has_lo = has_lo
        if self.decode == "fine":
            if not has_lo:
                raise SystemExit("[ds29r01] 精度の層がありません（extensions に %s がない）：%s" % (LO_EXT, d))
            p = os.path.join(self.dir, J["pos_lo_file"])
            size = os.path.getsize(p)
            want = self.L * self.nv * 4
            if size != want:
                raise SystemExit("[ds29r01] 精度の層の大きさが層 × 行 × 列 × 4 と違います：%d ≠ %d" % (size, want))
            self.pos_lo_path = p
            self.pos_lo_sha = sha256_file(p)
            self.checks.append(dict(item_ja="pos_lo_sha256 がファイルと一致", ok=self.pos_lo_sha == J.get("pos_lo_sha256"),
                                    detail=self.pos_lo_sha[:12]))
            self.checks.append(dict(item_ja="精度の層 = 層 × 行 × 列 × 4 バイト", ok=True, detail="%d バイト" % size))
            self.raw_lo = np.memmap(p, dtype=np.uint8, mode="r", shape=(self.L, self.nv, 4))
            self.q_max = self.q_max_hi / 255.0
        self._cache = {}

    def layer(self, l):
        l = int(l)
        v = self._cache.get(l)
        if v is None:
            if len(self._cache) >= 8:
                self._cache.pop(next(iter(self._cache)))
            q = np.asarray(self.raw[l, :, :3], dtype=np.float64)
            if self.raw_lo is not None:
                q = q + np.asarray(self.raw_lo[l, :, :3], dtype=np.float64) / 255.0 - 0.5
            v = (self.lo + q / 65535.0 * self.sz).astype(np.float32).astype(np.float64)
            self._cache[l] = v
        return v

    def info(self):
        out = orig_info(self)
        out["decode"] = self.decode
        out["decode_ja"] = ("16 bit ＋ 精度の層（位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size）" if self.raw_lo is not None
                            else "16 bit だけ（設計27〜29 の再生器の読み）")
        if self.raw_lo is not None:
            out["pos_lo_sha256"] = self.pos_lo_sha
            out["pos_lo_bytes"] = int(os.path.getsize(self.pos_lo_path))
        out["quantization_max_m"] = float(self.q_max)
        out["quantization_max_hi_m"] = float(self.q_max_hi)
        out["kstar_dir"] = STATE.get("kstar_src")
        return out

    Q.PackageSurface.__init__ = init
    Q.PackageSurface.layer = layer
    Q.PackageSurface.info = info
    Q.PackageSurface._ds29r01_patched = True
    return Q


def jdump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
