# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S3：見本02（K*′ AS02C・fix01 の爪・見本 A の材質）の波頭まわりの数を測る（読み取りのみ）。

測るもの：
  1. 主役波の格子（400 列 × 240 行）の、波頭（j_top）〜唇の先（j_tip）の間の頂点の間隔（巻きの向き＝列、頂に並ぶ向き＝行）。
  2. 波頭の稜の線（各行の j_top の位置）と唇の先の線（j_tip）、波頭の回り台（crest orbit）の中心と半径。
  3. 爪 83 本の根元・先の位置を主役波の (行, 列) へ当て、波頭の縁（j_top〜j_tip の上の方）・面の内側・近い海に分ける。
読むのは自分たちの成果物だけ（参照モデルの OBJ・写真・利用者の画像は読まない）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/as03_s3_inventory.py <出力 json>
"""
import json
import struct
import sys

import numpy as np

B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/fix01"
GWB = B + "/back/final/cand/kstarAS02C_a45.gwb"
META = B + "/back/final/cand/kstarAS02C_a45_meta.json"
ROWS = B + "/back/final/cand/kstarAS02C_a45_rows.npz"
CL = B + "/assemble/claws/mesh"


def read_gwb(p):
    b = open(p, "rb").read()
    magic, ver, nu, nv, nfr, fps, ts, nt = struct.unpack("<4s4if2i", b[:32])
    n = nu * nv
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, nt * 3, o).reshape(nt, 3)
    o += nt * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(nv, nu, 3).astype(np.float64)
    return nu, nv, tris, X


def main():
    out = sys.argv[1]
    nu, nv, tris, X = read_gwb(GWB)
    meta = json.load(open(META, encoding="utf-8"))
    idx = meta["profile"]["index"]
    jB, jT, jTip, jC, jF, jE = idx["j_B"], idx["j_top"], idx["j_tip"], idx["j_corner"], idx["j_facebot"], idx["j_E"]
    fr = meta["frame"]
    H0 = fr["H0_m"]
    e = np.array(fr["e_crest"]); t = np.array(fr["t_travel"])
    c = np.array(meta["rows"]["c_m"])
    rz = np.load(ROWS)
    top = rz["top_argmax_col"]
    res = {"grid": {"cols_nu": nu, "rows_nv": nv, "vertices": nu * nv, "triangles": int(len(tris)),
                    "profile_index": idx, "H0_m": H0}}
    # 1. 間隔
    dcol = np.linalg.norm(np.diff(X, axis=1), axis=2)      # (nv, nu-1) 巻きの向き
    drow = np.linalg.norm(np.diff(X, axis=0), axis=2)      # (nv-1, nu) 頂に並ぶ向き
    hero = (c >= -19.0) & (c <= 15.0)
    hr = np.where(hero)[0]
    segs = {"back_jB_jtop": (jB, jT), "crest_jtop_jtop+20": (jT, jT + 20), "crest_to_lip_jtop_jtip": (jT, jTip),
            "lip_tube_jtip_jcorner": (jTip, jC), "face_jcorner_jfacebot": (jC, jF)}
    sp = {}
    for k, (a, b2) in segs.items():
        dc = dcol[hr][:, a:b2]
        dr = drow[hr[:-1]][:, a:b2 + 1]
        sp[k] = {"cols": b2 - a, "along_curl_m_p10_p50_p90": [round(float(np.percentile(dc, q)), 4) for q in (10, 50, 90)],
                 "across_m_p10_p50_p90": [round(float(np.percentile(dr, q)), 4) for q in (10, 50, 90)],
                 "arc_len_m_main_row": round(float(dcol[idx["main_row"], a:b2].sum()), 3)}
    res["spacing_hero_rows_c_-19_15"] = sp
    # 2. 稜と唇の先の線
    crest = X[np.arange(nv), np.clip(top, 0, nu - 1)]
    tip = X[:, jTip]
    hrows = [i for i in hr if crest[i, 1] > 0.6 * H0]
    res["crest_line"] = {"rows_above_0.6H0": len(hrows), "c_range_m": [float(c[hrows[0]]), float(c[hrows[-1]])],
                         "height_m_at_c": {str(round(float(c[i]), 1)): round(float(crest[i, 1]), 2) for i in hrows[:: max(1, len(hrows) // 12)]},
                         "top_col_range": [int(top[hrows].min()), int(top[hrows].max())]}
    # 波頭の領域：行は稜が 0.75 H0 より高い行、列は j_top−10〜j_tip
    rows_hi = [i for i in hr if crest[i, 1] > 0.75 * H0]
    P = X[rows_hi][:, max(0, jT - 10):jTip + 1].reshape(-1, 3)
    ctr = P.mean(0)
    rad = float(np.percentile(np.linalg.norm(P - ctr, axis=1), 95))
    ext = P.max(0) - P.min(0)
    res["crest_region"] = {"rows_crest_above_0.75H0": len(rows_hi), "c_range_m": [float(c[rows_hi[0]]), float(c[rows_hi[-1]])],
                           "cols": [max(0, jT - 10), jTip], "center_world": [round(float(v), 3) for v in ctr],
                           "radius_p95_m": round(rad, 3), "extent_xyz_m": [round(float(v), 2) for v in ext],
                           "extent_along_e_m": round(float((P @ e).max() - (P @ e).min()), 2),
                           "extent_along_t_m": round(float((P @ t).max() - (P @ t).min()), 2),
                           "extent_y_m": round(float(P[:, 1].max() - P[:, 1].min()), 2)}
    res["lip_tip_line"] = {"height_m_main_row": round(float(tip[idx["main_row"], 1]), 2),
                           "forward_of_crest_m_main_row": round(float((tip[idx["main_row"]] - crest[idx["main_row"]]) @ t), 2)}
    # 3. 爪
    lay = json.load(open(CL + "/ds33_claw_layout.json", encoding="utf-8"))
    V = np.fromfile(CL + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3).astype(np.float64)
    flat = X.reshape(-1, 3)
    # 主役波の頂点の近いものを探す（格子の近傍：KD 木を使わず、粗い格子で）
    from scipy.spatial import cKDTree
    kd = cKDTree(flat)
    cls = {"crest_rim": [], "face": [], "back": [], "sea_or_other": []}
    rec = []
    for cl in lay["claws"]:
        o0, n = cl["vert_offset"], cl["vert_count"]
        st = cl["stations"]
        root = V[o0]
        tipv = V[o0 + 1 + st * 8]
        dr, ir = kd.query(root)
        rr, cc = divmod(int(ir), nu)
        dt, it = kd.query(tipv)
        L = float(np.linalg.norm(tipv - root))
        # 波頭の縁：根元の列が j_top−12〜j_tip で、行が主役波の範囲、根元の高さ > 0.7 H0
        if not hero[rr] or dr > 2.0:
            k = "sea_or_other"
        elif cc < jT - 12:
            k = "back"
        elif cc <= jTip and root[1] > 0.7 * H0:
            k = "crest_rim"
        else:
            k = "face"
        cls[k].append(cl["id"])
        rec.append({"id": cl["id"], "user_id": cl.get("user_id"), "root_row": rr, "root_col": cc, "root_c_m": round(float(c[rr]), 2),
                    "root_h_m": round(float(root[1]), 2), "root_dist_m": round(float(dr), 3), "len_m": round(L, 3), "zone": k,
                    "verts": n, "stations": st})
    res["claws"] = {"count": len(lay["claws"]), "vertices": lay["vertices"], "triangles": lay["triangles"],
                    "zone_counts": {k: len(v) for k, v in cls.items()}, "zones": cls,
                    "len_m_p10_p50_p90": [round(float(np.percentile([r["len_m"] for r in rec], q)), 3) for q in (10, 50, 90)],
                    "per_claw": rec}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "claws"}, ensure_ascii=False, indent=1)[:4000])
    print("claws", json.dumps({k: res["claws"][k] for k in ("count", "vertices", "triangles", "zone_counts", "len_m_p10_p50_p90")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
