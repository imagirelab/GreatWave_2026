# -*- coding: utf-8 -*-
"""美術の見本02 修正の回 1：C2（利用者の模型の水準）と C3（原画視点の IoU ≥ 0.85）が両立しない爪の確かめ。
as02_claws100.py --fix01 の選び方（280 通り）より広く、肋の組み方のならし PAIR_SIG 3 × ガウスの倍率 8 × スプラインの倍率 6 × 長い波を戻すならし 4
× 幅の倍率 8 ＝ 4,608 通りの 2 次元の形を作り、
  ・2 次元の水準の検査（輪郭のでこぼこ ≤ claw_mid + 2 ＝ 10、背骨の曲率の跳び ≤ 模型）を通る中で、利用者のマスクとの IoU（枠の外も数える）の最大
  ・でこぼこを 12 まで許した時の IoU の最大
を書く。2 次元の IoU は原画視点の IoU とほぼ同じ（厚みの向きを射線へ寄せた時、差 0.002 以内）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_conflict_search.py <claw001,...> <out.json>
"""
import itertools
import json
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_claws100 as A  # noqa: E402


def main():
    ids = sys.argv[1].split(",")
    out = sys.argv[2]
    std = json.load(open(A.STD, encoding="utf-8"))
    lim_l = std["models"]["claw_mid"]["outline_lumps_hysteresis"] + 2
    lim_j = max(std["models"]["claw_mid"]["spine_curvature_x_wmax"]["jump_p95"], std["models"]["claw_low"]["spine_curvature_x_wmax"]["jump_p95"])
    users, _, _ = A.load_user()
    A.P.update(PAIR_SIG=0.6, CLIP_CROP=1)
    res = {"tool": "Tools/GWWaveGen/as02/as02_fix01_conflict_search.py", "limits": {"outline_lumps": lim_l, "spine_jump_p95": lim_j}, "claws": {}}
    grid = dict(PAIR_SIG=(0.4, 0.6, 1.0), GAUSS_K=(1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0), SPLINE_K=(1.0, 1.25, 1.5, 1.75, 2.0, 2.5),
                SHRINK_COMP=(0.0, 2.0, 3.0, 5.0), width_scale=(0.97, 1.0, 1.02, 1.04, 1.06, 1.08, 1.1, 1.13))
    res["grid"] = grid
    for c in users:
        if c["uid"] not in ids:
            continue
        rows = []
        for ps, g, sk, bp in itertools.product(grid["PAIR_SIG"], grid["GAUSS_K"], grid["SPLINE_K"], grid["SHRINK_COMP"]):
            save = dict(A.P)
            A.P.update(PAIR_SIG=ps, GAUSS_K=g, SPLINE_K=sk, SHRINK_COMP=bp)
            try:
                sh0 = A.shape2d(c, std)
            except Exception:  # noqa: BLE001
                A.P.clear(); A.P.update(save)
                continue
            A.P.clear(); A.P.update(save)
            for f in grid["width_scale"]:
                sh = A.clip_crop(A.scale_width(sh0, f))
                rows.append(dict(iou2d=round(A.iou_mask2d(sh), 4), lumps=A.outline_lumps(sh["poly"], sh["w_mid"] / 0.75), jump=round(A.spine_jump_p95(sh), 3),
                                 PAIR_SIG=ps, GAUSS_K=g, SPLINE_K=sk, SHRINK_COMP=bp, width_scale=f))
        ok = [r for r in rows if r["lumps"] <= lim_l and r["jump"] <= lim_j]
        l12 = [r for r in rows if r["lumps"] <= 12 and r["jump"] <= lim_j]
        res["claws"][c["uid"]] = {"tried": len(rows), "best_c2_pass": max(ok, key=lambda r: r["iou2d"]) if ok else None,
                                  "best_lumps_le_12": max(l12, key=lambda r: r["iou2d"]) if l12 else None,
                                  "best_any": max(rows, key=lambda r: r["iou2d"])}
        print(c["uid"], json.dumps(res["claws"][c["uid"]], ensure_ascii=False), flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
