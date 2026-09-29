# -*- coding: utf-8 -*-
"""Q20 final K*': one-shot evaluation of a rows npz (no reference-model data):
  * the official rubric (Unity/Build/Q20/rubric/tools/rubric_check.py, --gate) with a numpy-bool-safe recount,
  * painting-view sky difference against K* 26修正01 and against the painting (holes / spill), by component,
  * mesh hygiene: local 3-D self-intersections (V1.local_self_intersections, window 6), flipped quads, creases by c,
  * the second-crest S1 share (painted band rays that land on the near-shoulder tier).
usage: py -3.10 fin_eval.py rows.npz out_prefix [--fast]"""
import sys, os, json, math
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_check as RC

# 2026-09-29 設計28修正01 を閉じる時：Q16 の研究で作った原画の帯のマスク（band_foam_mask_painting.png）のフォルダーは、
# リポジトリの外の作業場所（<scratchpad>/q16/crest）にある。個人のパスを書かないため、環境変数 GW_Q16_CREST_DIR で渡す
# （計算は変えていない。変える前のこのファイルの SHA-256 は 6ef824a9…、Git 対象外の kh_eval_summary.json に残る）。
# 渡さないと、kh_eval.py の S1 は {"error": …} になる（リポジトリだけでは S1 を再現できない）。
# 注意：このファイルを単独で import すると、candA_common.RUBRIC_TOOLS（Git 対象外の Unity/Build/Q20/rubric/tools）から
# rubric_check を読む。採用の経路（kh_eval.py・kh_R4_quick.py）は、先にリポジトリの Tools/GWWaveGen/rubric を読み込んでおく。
SCRATCH_CREST = os.environ.get("GW_Q16_CREST_DIR", "")


def recount(R):
    nm = sum(1 for L in R["checks"].values() for x in L if x["pass_must"] is not None and not bool(x["pass_must"]))
    nt = sum(1 for L in R["checks"].values() for x in L if x["pass_target"] is not None and not bool(x["pass_target"]))
    n = sum(len(L) for L in R["checks"].values())
    return {"must_fail": nm, "target_miss": nt, "n_checks": n}


def coverage(fr, V1, c, A, Y):
    X = fr.world(c, A, Y); tris = V1.triangles(A.shape[1], A.shape[0])
    return V1.rasterize(fr.cam, X, tris) > 0.5


def sky_diff(fr, tgt, V1, G0, c, A, Y, out_png=None):
    cov = coverage(fr, V1, c, A, Y)
    Kz = np.load(C.KSTAR_ROWS)
    covk = coverage(fr, V1, Kz["c"].astype(float), Kz["A"].astype(float), Kz["Y"].astype(float))
    seacov, yh = G0.sea_horizon_cover(fr.cam, tgt.spec)
    sea = seacov > 0.5
    # the painting: wave where the (half-width compensated) sky sdf is negative
    Hh, Ww = cov.shape
    yy, xx = np.mgrid[0:Hh, 0:Ww]
    s = tgt.sample(np.stack([xx.ravel(), yy.ravel()], -1).astype(float), comp=True).reshape(Hh, Ww)
    inframe = (xx >= tgt.x0) & (xx <= tgt.x1)
    wave = (s < 0) & inframe & ~sea
    skyp = (s > 0) & inframe & ~sea
    res = {}
    def comps(m):
        n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        big = sorted([(int(st[i, 4]), int(st[i, 0]), int(st[i, 1]), int(st[i, 0] + st[i, 2]), int(st[i, 1] + st[i, 3])) for i in range(1, n)], reverse=True)[:5]
        return {"px": int(m.sum()), "components": n - 1, "largest_area_x0y0x1y1": big}
    res["vs_kstar_new_sky"] = comps(covk & ~cov & ~sea & inframe)
    res["vs_kstar_new_wave"] = comps(cov & ~covk & ~sea & inframe)
    res["vs_painting_holes_in_wave"] = comps(wave & ~cov)
    res["vs_painting_spill_into_sky"] = comps(skyp & cov)
    res["kstar_vs_painting_holes_in_wave"] = comps(wave & ~covk)
    res["kstar_vs_painting_spill_into_sky"] = comps(skyp & covk)
    if out_png:
        img = np.zeros(cov.shape + (3,), np.uint8)
        img[cov] = (90, 90, 90)
        img[wave & ~cov] = (0, 0, 255)       # hole (red)
        img[skyp & cov] = (255, 160, 0)      # spill (blue)
        img[covk & ~cov & ~sea & inframe & ~(wave & ~cov)] = (0, 200, 255)
        cv2.imwrite(out_png, img)
    return res


def mesh_hygiene(c, A, Y, V1, win=6):
    nv, nu = A.shape
    X = C.world(c, A, Y)
    bad = V1.local_self_intersections(X, win=win)
    rows = sorted(set(r for r, j in bad))
    V = X.reshape(-1, 3); tris = V1.triangles(nu, nv)
    fn = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
    area = 0.5 * np.linalg.norm(fn, axis=1)
    un = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-15)[:, None]
    flip = ((un[0::2] * un[1::2]).sum(1) < -0.866).reshape(nv - 1, nu - 1)
    fr_, fj = np.nonzero(flip)
    # quad normals and creases
    d1 = X[1:, 1:] - X[:-1, :-1]; d2 = X[:-1, 1:] - X[1:, :-1]
    n = np.cross(d1, d2); qa = np.linalg.norm(n, axis=-1); n = n / np.maximum(qa, 1e-15)[..., None]
    ym = np.maximum.reduce([Y[:-1, :-1], Y[1:, :-1], Y[:-1, 1:], Y[1:, 1:]])
    ok = (qa > 1e-6) & (ym > 0.3)
    vr = np.degrees(np.arccos(np.clip((n[:-1] * n[1:]).sum(-1), -1, 1)))
    okr = ok[:-1] & ok[1:]
    cr, cj = np.nonzero(okr & (vr > 30))
    hist = {}
    for lo, hi in [(-60, -20), (-20, -12), (-12, -5), (-5, -1), (-1, 0.001), (0.001, 3), (3, 6), (6, 9), (9, 20)]:
        hist["%g..%g" % (lo, hi)] = int(((c[cr + 1] >= lo) & (c[cr + 1] < hi)).sum())
    return {"local_selfx_vertices_win%d" % win: len(bad), "local_selfx_rows": rows[:60],
            "flipped_quads_gt150": int(flip.sum()), "flipped_rows": sorted(set(int(r) for r in fr_))[:60],
            "cross_row_gt30_all": int((okr & (vr > 30)).sum()), "cross_row_gt60_all": int((okr & (vr > 60)).sum()),
            "cross_row_gt120_all": int((okr & (vr > 120)).sum()), "cross_row_gt30_by_c": hist,
            "min_tri_area_m2": float(area.min()), "degenerate_lt_1e-6": int((area < 1e-6).sum()),
            "nan": int((~np.isfinite(X)).sum()), "min_row_gap_m": float(np.diff(c).min())}


def zbuf_ids(P, tris, W=1920, H=1080):
    pts = [P[:, :3]]; ids = [np.arange(len(P))]
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        pts.append(0.5 * (P[tris[:, i]] + P[tris[:, j]])); ids.append(tris[:, i])
    pts.append((P[tris[:, 0]] + P[tris[:, 1]] + P[tris[:, 2]]) / 3.0); ids.append(tris[:, 0])
    Q = np.vstack(pts); I = np.concatenate(ids)
    ok = (Q[:, 2] > 1) & (Q[:, 0] >= 0) & (Q[:, 0] < W) & (Q[:, 1] >= 0) & (Q[:, 1] < H)
    Q, I = Q[ok], I[ok]
    pix = np.clip(np.round(Q[:, 1]).astype(int), 0, H - 1) * W + np.clip(np.round(Q[:, 0]).astype(int), 0, W - 1)
    order = np.lexsort((Q[:, 2], pix))
    pix, Qz, I = pix[order], Q[order, 2], I[order]
    first = np.r_[True, pix[1:] != pix[:-1]]
    zb = np.full(W * H, np.inf); ib = np.full(W * H, -1)
    zb[pix[first]] = Qz[first]; ib[pix[first]] = I[first]
    zb = zb.reshape(H, W); ib = ib.reshape(H, W)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sh_z = np.roll(np.roll(zb, dy, 0), dx, 1); sh_i = np.roll(np.roll(ib, dy, 0), dx, 1)
            hole = ~np.isfinite(zb) & np.isfinite(sh_z)
            zb = np.where(hole, sh_z, zb); ib = np.where(hole, sh_i, ib)
    return zb, ib


def second_crest_S1(fr, tgt, V1, A, Y, c):
    """share of the painted second-crest band (Q16 user region, foam mask) whose painting-camera rays first hit the
    near-shoulder second tier (rows c -16.5..-3 at heights 7..12.8 m)."""
    band = np.asarray(Image.open(os.path.join(SCRATCH_CREST, "band_foam_mask_painting.png"))) > 128
    ys, xs = np.nonzero(band[::4, ::4]); ys *= 4; xs *= 4
    D = tgt.fm.ref_to_disp(np.stack([xs, ys], -1).astype(float))
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    zb, ib = zbuf_ids(P, V1.triangles(nu, nv))
    xi = np.clip(np.round(D[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(D[:, 1]).astype(int), 0, 1079)
    vid = ib[yi, xi]; hit = vid >= 0
    r = vid[hit] // nu; j = vid[hit] % nu
    yv = Y[r, j]
    tier = (c[r] >= -16.5) & (c[r] <= -3.0) & (yv >= 7.0) & (yv <= 12.8)
    return {"band_pixels_sampled": int(len(D)), "rays_hitting_the_sheet": int(hit.sum()),
            "share_on_second_tier": float(tier.mean()) if hit.any() else 0.0,
            "hit_c_range_m": [float(c[r].min()), float(c[r].max())] if hit.any() else None,
            "hit_y_p10_p90_m": [float(np.percentile(yv, 10)), float(np.percentile(yv, 90))] if hit.any() else None,
            "hit_c_p10_p90_m": [float(np.percentile(c[r], 10)), float(np.percentile(c[r], 90))] if hit.any() else None}


def landmark_stats(A, Y, c):
    H = Y.max(1); out = {}
    body = np.nonzero(H >= 2.0)[0]
    top = np.array([int(np.argmax(Y[r, :200])) for r in body])
    out["top_col_argmax_range"] = [int(top.min()), int(top.max())]
    out["rows_top_not_at_90_pm5"] = int((np.abs(top - 90) > 5).sum())
    out["top_col_jumps_gt5"] = int((np.abs(np.diff(top)) > 5).sum())
    return out


def evaluate(rows, prefix, fast=False):
    V1, tgt, fr = C.painting_frame()
    import gw_wavegen as G0
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    R = RC.check(rows, gate=True, ref_cache=None)
    R["summary_recount"] = recount(R)
    out = {"rows": rows, "rubric_summary_recount": R["summary_recount"], "rubric_summary_tool": R["summary"]}
    json.dump(R, open(prefix + "_rubric.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(prefix + "_rubric_table.md", "w", encoding="utf-8").write(RC.to_table(R) + "\n")
    out["gate"] = {k: (round(v["max_px"], 2), round(v["p95_px"], 2)) for k, v in R["gate_raw"].items()}
    out["sky"] = sky_diff(fr, tgt, V1, G0, c, A, Y, prefix + "_skydiff.png")
    if not fast:
        out["mesh"] = mesh_hygiene(c, A, Y, V1)
    out["S1"] = second_crest_S1(fr, tgt, V1, A, Y, c)
    out["landmarks"] = landmark_stats(A, Y, c)
    json.dump(out, open(prefix + "_eval.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return out, R


def brief(out, R):
    lines = []
    lines.append("MUST FAIL %d / %d (tool said %d)" % (out["rubric_summary_recount"]["must_fail"], out["rubric_summary_recount"]["n_checks"], out["rubric_summary_tool"]["must_fail"]))
    lines.append("gate " + json.dumps(out["gate"]))
    for fid in sorted(R["checks"]):
        for x in R["checks"][fid]:
            v = x["value"]
            vs = ("[%.2f,%.2f]" % tuple(v)) if isinstance(v, list) else (("%.2f" % v) if isinstance(v, float) else str(v))
            pm = x["pass_must"]
            flag = "  " if pm is None or bool(pm) else "XX"
            lines.append("%s %s %s = %s (must %s)" % (flag, fid, x["name"][:38], vs, x["must"]))
    s = out["sky"]
    lines.append("sky: new_sky_vs_K* %d px, new_wave_vs_K* %d, holes_vs_painting %d (K* %d), spill %d (K* %d)" % (
        s["vs_kstar_new_sky"]["px"], s["vs_kstar_new_wave"]["px"], s["vs_painting_holes_in_wave"]["px"], s["kstar_vs_painting_holes_in_wave"]["px"],
        s["vs_painting_spill_into_sky"]["px"], s["kstar_vs_painting_spill_into_sky"]["px"]))
    lines.append("holes largest: %s" % (s["vs_painting_holes_in_wave"]["largest_area_x0y0x1y1"][:3],))
    if "mesh" in out:
        m = out["mesh"]
        lines.append("mesh: selfx %d rows %s; flips %d rows %s; creases>30 %d >60 %d >120 %d by c %s" % (
            m["local_selfx_vertices_win6"], m["local_selfx_rows"][:12], m["flipped_quads_gt150"], m["flipped_rows"][:12],
            m["cross_row_gt30_all"], m["cross_row_gt60_all"], m["cross_row_gt120_all"], m["cross_row_gt30_by_c"]))
    lines.append("S1 %s" % json.dumps(out["S1"]))
    lines.append("landmarks %s" % json.dumps(out["landmarks"]))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out, R = evaluate(sys.argv[1], sys.argv[2], fast="--fast" in sys.argv)
    txt = brief(out, R)
    open(sys.argv[2] + "_brief.txt", "w", encoding="utf-8").write(txt)
    print(txt)
