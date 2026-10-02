# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 1：爪の並び（仕上げ33 採用）から、立つ指の材料を作る（numpy）。

出力（Git 対象外、Unity/Build/Polish/33r01/houdini/prep/）：
  fingers_tstar.json   Houdini の Python SOP が読む t* の指ごとの材料（Houdini の座標 = Unity の z を反転）：
                       面の上の中心線 22 点、原画のカメラへの向き、半幅、t* の弧長の割合、立ち上がりの高さ H、種類、根元の円の法線、
                       頂の帯（根元の白の円の上の薄い帯）の粒、VDB の格子の大きさ・閉じの半径・減らした後の点の数の目安。
  frames_spines.npz    全部のコマ（421）の面の上の中心線・上の向き・半幅・根元の円（Unity の座標、float32）。deform が使う。
  prep_report.json     選んだ爪・落とした爪・数・SHA-256。
参照モデルの OBJ は読まない（F13-1）。原画カメラからの投影の色は使わない（Q28）。
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import houdini_common as H  # noqa: E402


def main():
    t0 = time.time()
    out = H.OUT + "/prep"
    os.makedirs(out, exist_ok=True)
    L, F = H.load_layout()
    items = H.select_items(L)
    C, UP, HW, RC = H.spines_frame(F, H.K_STAR, items)
    A = H.arclen(C)
    keep = A >= H.PRM["a_min"]
    dropped = [it["id"] for it, k in zip(items, keep) if not k]
    items = [it for it, k in zip(items, keep) if k]
    C, UP, HW, RC, A = C[keep], UP[keep], HW[keep], RC[keep], A[keep]
    n = len(items)
    kind = np.array([{"C": 0, "S": 1, "K": 2}[it["id"][0]] for it in items])
    U = H.arc_u(C)
    Q = H.proj_ratio(F, H.K_STAR, items, C)          # 原画視点の幅に合わせる比（pl33r01h_paint_width）
    HW = HW * Q
    prm = H.PRM
    Hh = np.clip(prm["h_rel"] * A + prm["h_add"], prm["h_min"], prm["h_max"]) * (kind != 2)
    nc = H.circle_normal(RC)
    Lr = H.CAM_U[None, :] - C[:, 0]
    Lr = Lr / np.linalg.norm(Lr, axis=1, keepdims=True)
    s_cam = np.sign((nc * Lr).sum(1)); s_cam[s_cam == 0] = 1
    s_up = np.sign((nc * UP[:, 0]).sum(1)); s_up[s_up == 0] = 1
    sgn = np.where(kind == 2, s_up, s_cam)
    ramps = {"curl": [np.interp(x, [k[0] for k in H.CURL_KEYS], [k[1] for k in H.CURL_KEYS]) for x in np.linspace(0, 1, 512)],
             "taper": [np.interp(x, [k[0] for k in H.TAPER_KEYS], [k[1] for k in H.TAPER_KEYS]) for x in np.linspace(0, 1, 512)]}
    P, R, NO = H.stand2(C, UP, HW, RC, U, Hh, kind, sgn, A, A, ramps)
    # 格子・閉じ・点の数の目安（既定のランプで見積もる。Houdini の側の最終の形はランプで決まる）
    rmed = np.array([np.median(R[i][R[i] > 0]) if (R[i] > 0).any() else 0.03 for i in range(n)])
    vox = np.clip(prm["vox_rel"] * rmed, prm["vox_min"], prm["vox_max"])
    kclose = np.clip(prm["close_rel"] * R[:, 1], prm["close_min"], prm["close_max"])
    len3 = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
    padr = np.clip(prm["pad_rel"] * HW[:, 1], prm["pad_min"], prm["pad_max"])
    circ_r = np.linalg.norm(RC[:, 1:] - RC[:, :1], axis=2).mean(1)
    ell = np.where(kind == 2, 1.0, prm["ell_k"])
    area = 2 * np.pi * np.maximum(rmed, 0.02) * len3 * (1 + ell) / 2 + np.pi * (circ_r + padr) ** 2
    npts = np.clip((area / prm["area_per_pt"]).astype(int), prm["npts_min"], prm["npts_max"])
    fingers = []
    for i, it in enumerate(items):
        # 頂の帯の粒：根元の円の中心・円 8・その中点 8・根元の点。面から外へ半径 + 隙間だけ（面の向こうへ出ない）
        # 帯は根元のまわりの小さな台に限る（根元の円の向きのまま、半径を根元の半幅の 1.6 倍までに縮める。pl33r01h_crest_band）
        dirs = RC[i, 1:] - RC[i, :1]
        dl = np.linalg.norm(dirs, axis=1, keepdims=True)
        rr = np.minimum(dl, 1.6 * max(HW[i, 1], 0.02))
        ring = RC[i, :1] + dirs / np.maximum(dl, 1e-9) * rr
        pts = np.vstack([RC[i, :1], ring, 0.5 * (RC[i, :1] + ring), C[i, :1]])
        pad = pts + NO[i][None] * (padr[i] + prm["pad_gap"])
        tipprev_u = float(U[i, -2])
        fingers.append({
            "id": it["id"], "fid": i, "kind": int(kind[i]), "type": it.get("type", ""),
            "C": H.u2h(C[i]).round(6).tolist(), "U": U[i].round(6).tolist(), "HW": HW[i].round(6).tolist(),
            "NO": H.u2h(NO[i][None])[0].round(6).tolist(), "H": float(Hh[i]),
            "tip_prev": [float(HW[i, -2]), tipprev_u],
            "pad": H.u2h(pad).round(6).tolist(), "padr": float(padr[i]),
            "vox": float(vox[i]), "kclose": float(kclose[i]), "npts": int(npts[i]), "A": float(A[i]), "ell": float(ell[i]),
        })
    meta = {"cam_h": H.u2h(H.CAM_U[None])[0].tolist(), "prm": prm, "curl_keys": H.CURL_KEYS, "taper_keys": H.TAPER_KEYS,
            "frame": H.K_STAR, "src": H.SRC_CLAWS, "note_ja": "Houdini の座標（Unity の z を反転）。C は面の上の中心線、U は t* の弧長の割合。"}
    jp = out + "/fingers_tstar.json"
    json.dump({"meta": meta, "fingers": fingers}, open(jp, "w", encoding="utf-8"))
    # 全部のコマ
    nf = L["frames"]
    CF = np.zeros((nf, n, H.NPT, 3), np.float32); UF = np.zeros_like(CF); WF = np.zeros((nf, n, H.NPT), np.float32)
    RF = np.zeros((nf, n, 9, 3), np.float32)
    for f in range(nf):
        c, u, w, rc = H.spines_frame(F, f, items)
        CF[f], UF[f], WF[f], RF[f] = c, u, w * Q, rc
    npz = out + "/frames_spines.npz"
    np.savez(npz, C=CF, UP=UF, HW=WF, RC=RF, U_star=U.astype(np.float32), H=Hh.astype(np.float32), kind=kind.astype(np.int32),
             sgn=sgn.astype(np.float32), A_star=A.astype(np.float32), ids=np.array([it["id"] for it in items]))
    rep = {"items": n, "by_kind": {k: int((kind == v).sum()) for k, v in (("C", 0), ("S", 1), ("K", 2))}, "dropped_collapsed_tstar": dropped,
           "A_star_pct": np.percentile(A, [0, 10, 50, 90, 100]).round(3).tolist(),
           "H_pct_CS": np.percentile(Hh[kind != 2], [0, 10, 50, 90, 100]).round(3).tolist(),
           "len3d_pct": np.percentile(len3, [0, 10, 50, 90, 100]).round(3).tolist(),
           "rmed_pct": np.percentile(rmed, [0, 10, 50, 90, 100]).round(3).tolist(),
           "paint_width_ratio_pct_CS": np.percentile(Q[kind != 2][:, 1:-1], [0, 10, 50, 90, 100]).round(3).tolist(),
           "npts_sum_estimate": int(npts.sum()),
           "src_layout_sha256": H.sha256(H.SRC_CLAWS + "/ds33_claw_layout.json"), "src_frames_sha256": L["files"]["frames"]["sha256"],
           "fingers_json_sha256": H.sha256(jp), "seconds": round(time.time() - t0, 1)}
    json.dump(rep, open(out + "/prep_report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
