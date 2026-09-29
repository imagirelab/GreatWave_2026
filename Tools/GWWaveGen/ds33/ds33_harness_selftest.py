# -*- coding: utf-8 -*-
"""設計33 の測定器（ds33_harness.py）の自己試験。爪の部の出力ではなく、設計32 の ID の仮の成長から作った試験用の帯で、
測定器が (1) 正しい爪を合格にし、(2) わざと入れた欠陥を見つけるかを確かめる（numpy。作品には入れない）。

試験用の帯（作品の爪ではない）：設計32 の ds32_ids.json の結び付けた爪ごとに、根元＝そのコマのシートの (行, 列) の三角形の面の点、
中心線＝ds32 の centerline_local_offsets_m（根元の局所の座標系）× 仮の成長 g(τ)（ds32 と同じ smoothstep）、幅は根元 0.12 m から先端 0 へ。
面の法線の側へ 0.03·u m 浮かせる（u は中心線の弧長の比。根元は面の上）。見えるのは g > 0 のコマ。

入れる欠陥（「欠陥あり」の組）：
  slip：1 本の根元の列を 0.004 升／コマずつずらす（137 で見つかるはず）
  lag：1 本の根元を前のコマの面で置く（105 か 137 で見つかるはず）
  lift：1 本の根元を法線の向きへ 3 mm 浮かせる（105）
  gap：1 本を成長の途中の 1 コマだけ消す（139）
  drop：1 本の成長を途中の 1 コマだけ半分にする（139b の面積の減りと頂点の突出）
  budget：1 本の頂点を 700 にする（頂点の数）
  flip：1 本の先端の向きを逆にする（原画視点の対応の旗）
  omit：1 本を出さない（本数と対応）
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds33_harness as HN  # noqa: E402

NSEG = 12


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class Ribbons:
    def __init__(self, ctx, defects=False):
        self.ctx = ctx
        b = [c for c in ctx.ids32["claws"] if c.get("bound")]
        self.ids = [c["id"] for c in b]
        self.n_frames = HN.NFR
        self.rc = np.array([c["sheet_rc"] for c in b], float)
        def res12(o):
            o = np.asarray(o, float)
            t = np.linspace(0, len(o) - 1, NSEG)
            return np.stack([np.interp(t, np.arange(len(o)), o[:, j]) for j in range(3)], -1)
        self.off = np.array([res12(c["centerline_local_offsets_m"]) for c in b], float)      # K × 12 × 3
        self.taub = np.array([c["tau_birth"] for c in b], float)
        self.root_rc = self.rc.copy()
        K = len(b)
        self.K = K
        self.defects = {}
        if defects:
            pick = lambda cid: self.ids.index(cid)  # noqa: E731
            names = ["slip", "lag", "lift", "gap", "drop", "budget", "flip", "omit"]
            # 途中・船側・上側から散らして選ぶ（ID は結び付けた爪の並びの中の決まった番号）
            chosen = [self.ids[i] for i in (5, 20, 40, 60, 80, 100, 120, 140)]
            for nm, cid in zip(names, chosen):
                self.defects[nm] = pick(cid)
        self.u = np.linspace(0, 1, NSEG)
        self.width = 0.12 * (1 - self.u)

    def g(self, f):
        tau = self.ctx.taus[f]
        return np.where(tau >= self.taub, smoothstep((tau - self.taub) / (0.0 - self.taub)), 0.0)

    def frame(self, f):
        ctx, K = self.ctx, self.K
        X = ctx.X(f)
        rc = self.rc.copy()
        g = self.g(f)
        if "slip" in self.defects:
            k = self.defects["slip"]
            rc[k, 1] += 0.004 * max(0, f - 200)
        root = HN.tri_interp(X, rc[:, 0], rc[:, 1])
        Fm = HN.local_frame(X, rc[:, 0], rc[:, 1])
        if "lag" in self.defects and f > 0:
            k = self.defects["lag"]
            Xp = ctx.X(f - 1)
            root[k] = HN.tri_interp(Xp, rc[k, 0], rc[k, 1])
        if "lift" in self.defects:
            k = self.defects["lift"]
            root[k] = root[k] + 0.003 * Fm[k, 2]
        if "drop" in self.defects and f == 330:
            g = g.copy(); g[self.defects["drop"]] *= 0.5
        off = self.off.copy()
        if "flip" in self.defects:
            k = self.defects["flip"]
            off[k, :, :2] *= -1
        cl = root[:, None, :] + g[:, None, None] * np.einsum("kij,kni->knj", Fm, off)      # K × 12 × 3（Fm は行が基底）
        cl = cl + (0.03 * self.u)[None, :, None] * Fm[:, None, 2, :]
        tng = np.gradient(cl, axis=1)
        side = np.cross(Fm[:, None, 2, :], tng)
        side = side / np.maximum(np.linalg.norm(side, axis=-1, keepdims=True), 1e-12)
        wv = (self.width[None, :, None] * np.maximum(g, 1e-3)[:, None, None]) * 0.5
        left = cl + wv * side; right = cl - wv * side
        Vk = np.stack([left, right], 2).reshape(K, NSEG * 2, 3)                              # K × 24 × 3
        Tq = []
        for i in range(NSEG - 1):
            a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
            Tq += [[a, b, c], [c, b, d]]
        Tq = np.array(Tq)
        V = [Vk.reshape(-1, 3)]
        T = [(Tq[None] + (np.arange(K) * NSEG * 2)[:, None, None]).reshape(-1, 3)]
        cid = [np.repeat(np.arange(K), NSEG * 2)]
        nv = K * NSEG * 2
        if "budget" in self.defects:
            k = self.defects["budget"]
            extra = 700 - NSEG * 2
            ev = np.repeat(Vk[k, :1], extra, 0) + 1e-6 * np.arange(extra)[:, None]
            V.append(ev); cid.append(np.full(extra, k))
            nv += extra
        V = np.concatenate(V); T = np.concatenate(T); cid = np.concatenate(cid)
        vis = g > 0
        if "gap" in self.defects and f == 340:
            vis = vis.copy(); vis[self.defects["gap"]] = False
        if "omit" in self.defects:
            k = self.defects["omit"]
            T = T[cid[T[:, 0]] != k]
            cid = np.where(cid == k, -1, cid)          # 三角形を持たない頂点（描かない）
            vis = vis.copy(); vis[k] = False
        return dict(V=V, T=T, cid=cid, root=root, visible=vis)


def main(out_root):
    os.makedirs(out_root, exist_ok=True)
    out = os.path.join(out_root, "selftest")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    ctx = HN.Context()
    res = {}
    clean = HN.evaluate(Ribbons(ctx, False), out, tag="_selftest_clean", ctx=ctx)
    bad_p = Ribbons(ctx, True)
    bad = HN.evaluate(bad_p, out, tag="_selftest_defects", ctx=ctx)
    idx = {k: bad_p.ids[v] for k, v in bad_p.defects.items()}
    tr = bad["tracks"]; pa = bad["painting"]
    flagged = {d["id"]: d["flags"] for d in pa["flagged"]}
    found = {
        "slip": idx["slip"] in tr["slip_over"],
        "lag": idx["lag"] in tr["slip_over"] or idx["lag"] in tr["root_dist_over"],
        "lift": idx["lift"] in tr["root_dist_over"],
        "gap": idx["gap"] in tr["claws_with_gaps"],
        "drop": idx["drop"] in tr["claws_with_drops"],
        "drop_as_vertex_pulse": idx["drop"] in tr["vertex_spikes"],
        "budget": idx["budget"] in tr["over_budget"],
        "flip": idx["flip"] in flagged,
        "omit": idx["omit"] in tr["missing_vs_ds32_bound"] and idx["omit"] in pa["missing_vs_ds32_bound"],
    }
    false_pos = sorted(set(tr["slip_over"] + tr["root_dist_over"] + tr["claws_with_gaps"] + tr["claws_with_drops"] + tr["over_budget"]
                           + list(tr["vertex_spikes"])) - set(idx.values()))
    cv = clean["verdicts"]
    res = dict(schema="GreatWave.DS33.harness_selftest/1",
               note_ja="試験用の帯（設計32 の仮の成長から作った、作品の爪ではないもの）で、測定器が正しい帯を合格にし、入れた欠陥を見つけるかを確かめた。",
               clean=dict(verdicts={k: v.get("verdict") for k, v in cv.items()}, root_dist_tri_max_m=clean["tracks"]["root_dist_tri_max_m"],
                          root_dist_bilinear_max_m=clean["tracks"]["root_dist_bilinear_max_m"], slip_max_m=clean["tracks"]["slip_max_m"],
                          painting_flagged=clean["painting"]["flagged"][:40], n_flagged=len(clean["painting"]["flagged"]),
                          root_err_px=clean["painting"]["root_err_px"], tip_err_px=clean["painting"]["tip_err_px"],
                          angle_err_deg=clean["painting"]["angle_err_deg"],
                          outline=dict(sheet=clean["outline"]["sheet_only_same_method"], with_ribbons=clean["outline"]["with_claws"])),
               defects=dict(injected=idx, found=found, all_found=all(found.values()), other_claws_flagged_tracks=false_pos,
                            painting_flags_of_injected={k: flagged.get(v) for k, v in idx.items()}),
               elapsed_s=round(time.time() - t0, 1))
    HN.jdump(os.path.join(out, "harness_selftest.json"), res)
    print(json.dumps(res["defects"], ensure_ascii=False, indent=1))
    print("clean verdicts", json.dumps(res["clean"]["verdicts"], ensure_ascii=False))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HN.OUT_DEFAULT)
