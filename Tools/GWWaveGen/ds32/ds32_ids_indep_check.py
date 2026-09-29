# -*- coding: utf-8 -*-
"""設計32：ID の履歴の独立の検査（生成器 ds32_ids.py と別の組み立て）。

- 主役波の位置は ds31_white.Pkg（設計31 の numpy の Hermite。生成器は ds30_checks.Pkg と ds27_player_ref の重み）で、ワールド = 局所 + O(τ)。
- τ(t) は時間曲線の表をこの検査で読み直して np.interp。
- 根元：一覧の (行, 列) の双線形を、この検査の中の式で求め、履歴のファイルの根元と比べる（30 Hz の全コマ）。
- 先端：|先端 − 根元| = g·|局所のずれ|（剛体の長さ）を全コマで確かめる（座標系の作り方に依らない）。
- 瞬間移動：根元の 30 Hz の動きが、そのコマのシート（本体の列）の頂点の動きの最大 + 1 mm を超えない（双線形の点は頂点の凸結合なので超えられない）。
  先端・群：履歴のファイルから前後のコマに対する突出（4 倍 + 5 cm）を数え直す。
- 点滅：見える（履歴の 8 番目の値）が τ ≥ τ_b（一覧の tau_birth と、この検査の τ(t)）と一致し、1 → 0 の変化がない。
- t* の再投影：truthlib.project_world（生成器は af27common.Cam）で、根元・先端を一覧の表示の画素と比べる。
- 群：どの爪も 1 つの爪の群に、どの飛沫の粒も 1 つの飛沫の群に入り、白の帯の群の頂点は重ならない。
出力：Unity/Build/Design/32/list+ids/ds32_ids_indep_check.json
"""
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
import ds31_white as W31  # noqa: E402
import truthlib as T  # noqa: E402

OUT = REPO + "/Unity/Build/Design/32/list+ids"


def main():
    t0 = time.time()
    ids = json.load(open(OUT + "/ds32_ids.json", encoding="utf-8"))
    inv = json.load(open(OUT + "/ds32_claw_inventory.json", encoding="utf-8"))
    NFR = ids["clock"]["frames"]
    bound = [c for c in ids["claws"] if c.get("bound")]
    nb = len(bound)
    H = np.fromfile(OUT + "/" + ids["claw_hist"]["file"], "<f4").reshape(NFR, nb, 8).astype(np.float64)
    pkg = W31.Pkg(REPO + "/" + ids["sheet"]["package"])
    R, C = pkg.R, pkg.C
    w = json.load(open(REPO + "/" + ids["clock"]["timewarp"], encoding="utf-8"))
    taus = np.interp(np.arange(NFR) / float(ids["clock"]["hz"]), np.array(w["t"]), np.array(w["tau"]))
    rc = np.array([c["sheet_rc"] for c in bound], np.float64)
    r0 = np.clip(np.floor(rc[:, 0]).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(rc[:, 1]).astype(int), 0, C - 2)
    fr, fc = rc[:, 0] - r0, rc[:, 1] - c0
    i00, i10, i01, i11 = r0 * C + c0, (r0 + 1) * C + c0, r0 * C + c0 + 1, (r0 + 1) * C + c0 + 1
    b0, b1 = ids["sheet"]["body_cols"]
    body = (np.arange(R)[:, None] * C + np.arange(b0, b1 + 1)[None, :]).ravel()
    root_err = np.zeros(NFR)
    root_move = np.zeros(NFR)
    sheet_move = np.zeros(NFR)
    Pprev = None
    for f, tau in enumerate(taus):
        Pl = pkg.eval(float(tau))
        O = pkg.origin(float(tau))[0]
        Pw = Pl + O
        root = (Pw[i00] * ((1 - fr) * (1 - fc))[:, None] + Pw[i10] * (fr * (1 - fc))[:, None] + Pw[i01] * ((1 - fr) * fc)[:, None]
                + Pw[i11] * (fr * fc)[:, None])
        root_err[f] = float(np.abs(root - H[f, :, 0:3]).max())
        Pb = Pw[body]
        if Pprev is not None:
            sheet_move[f] = float(np.linalg.norm(Pb - Pprev, axis=1).max())
            root_move[f] = float(np.linalg.norm(H[f, :, 0:3] - H[f - 1, :, 0:3], axis=1).max())
        Pprev = Pb
    over_sheet = int((root_move > sheet_move + 1e-3).sum())
    # 先端の剛体の長さ
    offs = np.array([np.linalg.norm(c["tip_local_offset_m"]) for c in bound])
    Ltip = np.linalg.norm(H[:, :, 3:6] - H[:, :, 0:3], axis=-1)
    len_err = float(np.abs(Ltip - H[:, :, 6] * offs[None, :]).max())
    # 突出（先端）
    d = np.linalg.norm(H[1:, :, 3:6] - H[:-1, :, 3:6], axis=-1)
    vis = H[:, :, 7] > 0.5
    both = vis[1:] & vis[:-1]
    dn = np.zeros_like(d)
    dn[1:-1] = np.maximum(d[:-2], d[2:]); dn[0] = d[1]; dn[-1] = d[-2]
    tip_spikes = int((both & (d > 4 * dn + 0.05)).sum())
    # 群（履歴のファイルの重み付きの重心は記録のみなので、ここでは爪の群の共通の根元の重心を数え直す）
    groups = ids["groups"]
    pos = {c["id"]: i for i, c in enumerate(bound)}
    grp_spikes = 0
    grp_max = 0.0
    for g in groups:
        if g["kind"] != "claw":
            continue
        ii = [pos[m] for m in g["members"]]
        dd = np.zeros(NFR)
        for f in range(1, NFR):
            com = vis[f, ii] & vis[f - 1, ii]
            if com.any():
                a = np.array(ii)[com]
                dd[f] = np.linalg.norm(H[f, a, 0:3].mean(0) - H[f - 1, a, 0:3].mean(0))
        grp_max = max(grp_max, float(dd.max()))
        grp_spikes += int((dd[1:] > sheet_move[1:] * 1.5 + 0.02).sum())
    # 点滅と誕生
    taub = np.array([c["tau_birth"] for c in bound])
    vis_expect = taus[:, None] >= taub[None, :]
    vis_mismatch = int((vis_expect != vis).sum())
    off_transitions = int(((vis[:-1]) & (~vis[1:])).sum())
    # t* の再投影（truthlib）
    spec = T.load_spec()
    byid = {c["id"]: c for c in inv["claws"]}
    fl = NFR - 1
    xr, yr, _, _, _ = T.project_world(spec, H[fl, :, 0:3])
    xt, yt, _, _, _ = T.project_world(spec, H[fl, :, 3:6])
    er = np.hypot(xr - np.array([byid[c["id"]]["root_display"][0] for c in bound]), yr - np.array([byid[c["id"]]["root_display"][1] for c in bound]))
    et = np.hypot(xt - np.array([byid[c["id"]]["tip_display"][0] for c in bound]), yt - np.array([byid[c["id"]]["tip_display"][1] for c in bound]))
    # 群の所属
    claw_in = {}
    for g in groups:
        if g["kind"] == "claw":
            for m in g["members"]:
                claw_in[m] = claw_in.get(m, 0) + 1
    spray_in = {}
    for g in groups:
        if g["kind"] == "spray":
            for m in g["members"]:
                spray_in[m] = spray_in.get(m, 0) + 1
    arr = np.fromfile(OUT + "/ds32_band_members_i32.bin", np.int32)
    k, seen, dup = 0, set(), 0
    while k < len(arr):
        n = int(arr[k]); v = arr[k + 1:k + 1 + n]
        dup += len(seen.intersection(v.tolist())); seen.update(v.tolist()); k += 1 + n
    stab = json.load(open(REPO + "/Unity/Build/Design/31/spray/ds31_spray_table.json", encoding="utf-8"))["particles"]
    res = {
        "schema": "GreatWave.DS32.ids_indep_check/1",
        "method_ja": __doc__,
        "root_vs_indep_eval_max_m": round(float(root_err.max()), 6),
        "root_move_over_sheet_max_frames": over_sheet,
        "root_move_max_m": round(float(root_move.max()), 4), "sheet_vertex_move_max_m": round(float(sheet_move.max()), 4),
        "tip_rigid_length_err_max_m": round(len_err, 6),
        "tip_spike_count": tip_spikes,
        "claw_group_common_move_max_m": round(grp_max, 4), "claw_group_over_rule_a": grp_spikes,
        "visible_vs_birth_mismatch": vis_mismatch, "visible_off_transitions": off_transitions,
        "reproj_truthlib_root_max_px": round(float(er.max()), 3), "reproj_truthlib_tip_max_px": round(float(et.max()), 3),
        "claws_in_exactly_one_group": sum(1 for c in bound if claw_in.get(c["id"], 0) == 1), "claws_bound": nb,
        "spray_in_exactly_one_group": sum(1 for p in stab if spray_in.get(p["dot_id"], 0) == 1), "spray_total": len(stab),
        "band_vertex_duplicates": dup,
        "elapsed_s": round(time.time() - t0, 1),
    }
    res["pass"] = bool(res["root_vs_indep_eval_max_m"] < 2e-3 and over_sheet == 0 and len_err < 1e-3 and tip_spikes == 0 and grp_spikes == 0
                       and vis_mismatch == 0 and off_transitions == 0 and res["reproj_truthlib_root_max_px"] < 1.0 and res["reproj_truthlib_tip_max_px"] < 1.0
                       and res["claws_in_exactly_one_group"] == nb and res["spray_in_exactly_one_group"] == len(stab) and dup == 0)
    with open(OUT + "/ds32_ids_indep_check.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "method_ja"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
