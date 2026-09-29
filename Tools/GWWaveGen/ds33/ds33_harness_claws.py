# -*- coding: utf-8 -*-
"""設計33：爪の部の出力（Unity/Build/Design/33/claws/、書式 GreatWave.DS33.claw_layout/1）を測定器（ds33_harness.py）で測る包み。

読むもの（読むだけ。SHA-256 を harness_run*.json に記録する）：
  ds33_claw_layout.json（爪ごとの ID・頂点の範囲・輪の数・型）、ds33_claw_frames_f32.bin（コマ × 頂点 × 3、ワールドの m）、
  ds33_claw_tris_i32.bin（三角形 × 3）、ds33_claw_tri_attr_u16.bin（三角形 × 2：爪の番号・面の種類）、
  ds33_claw_skel_f32.bin（コマ × 爪 × 36。見える＝欄 34）、ds33_claw_checks.json（爪の部の自己検査。値を並べて比べるだけ）。
爪ごとの頂点の並び（layout の vertex_order_ja）：根元の点 1、輪 stations × 8、先端 1、根元の白の円の中心 1、円 8。
  → root＝根元の点、tip＝先端の点、visible＝骨格の見える、root_vertices（記録）＝最初の輪の 8 頂点。
  根元の白の円は爪の頂点として数える（頂点の数・被覆に入る）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds33/ds33_harness_claws.py [--claws Unity/Build/Design/33/claws] [--out Unity/Build/Design/33/harness/claws_run] [--tag ""]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds33_harness as HN  # noqa: E402

CLAWS = HN.REPO + "/Unity/Build/Design/33/claws"
OUT = HN.OUT_DEFAULT + "/claws_run"
SKEL_W = 36
SKEL_VIS = 34


class ClawLayoutProvider:
    def __init__(self, d):
        self.dir = d
        self.path = os.path.join(d, "ds33_claw_layout.json")
        L = json.load(open(self.path, encoding="utf-8"))
        self.L = L
        cl = sorted(L["claws"], key=lambda c: c["index"])
        self.ids = [c["id"] for c in cl]
        K = len(cl)
        self.n_frames = int(L["frames"])
        N, M = int(L["vertices"]), int(L["triangles"])
        f = L["files"]
        self.files = {}

        def fp(key):
            p = os.path.join(d, f[key]["file"])
            self.files[key] = p
            return p
        self.pos = np.memmap(fp("frames"), "<f4", "r", shape=(self.n_frames, N, 3))
        self.T = np.fromfile(fp("tris"), "<i4").reshape(M, 3).astype(np.int64)
        attr = np.fromfile(fp("tri_attr"), "<u2").reshape(M, 2)
        self.tri_claw = attr[:, 0].astype(np.int64)
        self.tri_kind = attr[:, 1].astype(np.int64)
        skel_key = "skel" if "skel" in f else None
        if skel_key is None:
            p = os.path.join(d, "ds33_claw_skel_f32.bin")
            self.files["skel"] = p
        else:
            p = fp(skel_key)
        self.skel = np.memmap(p, "<f4", "r", shape=(self.n_frames, K, SKEL_W))
        cid = np.full(N, -1, np.int64)
        self.root_idx = np.zeros(K, np.int64)
        self.tip_idx = np.zeros(K, np.int64)
        self.root_vertices = []
        for k, c in enumerate(cl):
            o, n, st = int(c["vert_offset"]), int(c["vert_count"]), int(c["stations"])
            cid[o:o + n] = k
            self.root_idx[k] = o
            self.tip_idx[k] = o + 1 + st * 8
            self.root_vertices.append(np.arange(o + 1, o + 1 + 8))
        self.cid = cid
        # 三角形の爪の番号と、頂点の爪の番号が合うか（測定器は T[:,0] の頂点の爪で三角形を数える）
        self.tri_claw_mismatch = int((cid[self.T[:, 0]] != self.tri_claw).sum())
        self.root_rc = None
        self.meta = cl

    def frame(self, f):
        V = np.asarray(self.pos[f], np.float64)
        return dict(V=V, T=self.T, cid=self.cid, root=V[self.root_idx], tip=V[self.tip_idx],
                    visible=np.asarray(self.skel[f, :, SKEL_VIS]) > 0.5)


def compare_self_checks(d, res):
    p = os.path.join(d, "ds33_claw_checks.json")
    if not os.path.isfile(p):
        return None
    c = json.load(open(p, encoding="utf-8"))
    tr = res["tracks"]
    out = dict(claws_checks=p, claws_checks_sha256=HN.sha(p))

    def g(*ks):
        v = c
        for k in ks:
            if not isinstance(v, dict) or k not in v:
                return None
            v = v[k]
        return v
    out["105"] = dict(claws_part=g("item105", "max_m") or g("items", "105", "max_m"), harness=tr["root_dist_tri_max_m"])
    out["137"] = dict(claws_part=g("item137", "max_m") or g("items", "137", "max_m"), harness=tr["slip_max_m"])
    out["vertices"] = dict(claws_part=g("vertices", "per_claw_max"), harness=tr["vertices_max"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claws", default=CLAWS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tag", default="")
    ap.add_argument("--unity-ids", default=None)
    a = ap.parse_args()
    d = a.claws if os.path.isabs(a.claws) else os.path.join(HN.REPO, a.claws)
    out = a.out if os.path.isabs(a.out) else os.path.join(HN.REPO, a.out)
    prov = ClawLayoutProvider(d)
    print("claws %d, vertices %d, triangles %d, tri/vertex claw mismatch %d" % (len(prov.ids), len(prov.cid), len(prov.T), prov.tri_claw_mismatch), flush=True)
    res = HN.evaluate(prov, out, a.tag, a.unity_ids)
    cmp_ = compare_self_checks(d, res)
    res["claws_part_self_checks_vs_harness"] = cmp_
    res["adapter"] = dict(kind="ClawLayoutProvider", tri_claw_mismatch=prov.tri_claw_mismatch,
                          types={t: sum(1 for c in prov.meta if c.get("type") == t) for t in sorted(set(c.get("type") for c in prov.meta))})
    HN.jdump(os.path.join(out, "harness_metrics%s.json" % a.tag), res)
    v = res["verdicts"]
    print(json.dumps({k: v[k].get("verdict") for k in v}, ensure_ascii=False))
    print(json.dumps(cmp_, ensure_ascii=False))


if __name__ == "__main__":
    main()
