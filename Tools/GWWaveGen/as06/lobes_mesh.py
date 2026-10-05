# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：主役波 K*′ AS06L（② ③ を陰関数の塊にした形）の t* の、材質 AS05 Flat Smooth が読む頂点の属性つきの静止のメッシュを作る。
as05/fx5_B_mesh.py（変えない）の写しで、白の印 whiteSD の決め方だけを塊の形に合わせて替えた。約束は Unity/Build/Polish/sample04/mat/README.md。

白の印（m、+ が白）の作り：
  1. 作り直していない行（c ≥ −8 と、塊の無い行）：見本05 B10 の白の印（fix1/B/mesh/white_mask_as05b_f32.bin）の符号。T6（Q33 の切り出し）の直しを含む。
  2. 作り直した行：見本04 AS04F の白の印の符号から始め、背の頂の白（列 ≤ col_back_white）だけを残し、その先を藍にしてから、
     塊ごとに「縁の頂の帯」を白にする：塊の面（塊の距離が体・ほかの塊の距離より小さく 0.6 m 以内）のうち、
     溝の点の a − back_m より前、かつ唇の下の先（utip）の高さ − drop_m より上の頂点。その下の凹み・下の面・蹴込みは藍
     （原画の ② ③ の白い房が、それぞれ自分の藍の面の上に載るように。T5 の白い粒は作らない）。
     塊の重み f が f_min より小さい端の行と、c < c_min_white（S9：左の白は低い・最も左の白は c −23.4 m より右）は白にしない。
  3. 低い行（頂 < 0.22 H0）は白にしない（見本04 と同じ）。
原画のカメラの投影は使わない（G1）。行・列・断面の座標だけで決める。
使い方：py -3.10 -B Tools/GWWaveGen/as06/lobes_mesh.py <根> <候補の名前（例 kstarAS06L_a45）>
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as03")
import shape_mesh as M  # noqa: E402
import surf_common as SC  # noqa: E402
import surf_relief as R  # noqa: E402

sys.path.insert(0, REPO + "/Tools/GWWaveGen/as06")

WM_04F = REPO + "/Unity/Build/Polish/sample04/fix1/shape/mesh/white_mask_as04f_f32.bin"
WM_05B = REPO + "/Unity/Build/Polish/sample05/fix1/B/mesh/white_mask_as05b_f32.bin"
ROWS_04F = REPO + "/Unity/Build/Polish/sample04/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"
RULE = {"col_back_white": 112, "back_m": float(os.environ.get("AS06L_BACK_M", "0.4")), "drop_m": float(os.environ.get("AS06L_DROP_M", "0.15")),
        "f_min": float(os.environ.get("AS06L_WHITE_FMIN", "0.6")), "label_d_m": 0.6, "c_min_white": -23.2,
        "mode": os.environ.get("AS06L_WHITE_MODE", "crest"), "back_crest_m": float(os.environ.get("AS06L_BACK_CREST_M", "1.5"))}


def main():
    SH = sys.argv[1] if os.path.isabs(sys.argv[1]) else REPO + "/" + sys.argv[1]
    CAND = SH + "/cand/" + sys.argv[2]
    NAME = "hero_smooth_as06l"
    nr, nc = 240, 400
    import ds33_common as U  # noqa: F401
    SC.HERO_PKG = SH + "/hero_pkg_AS06L"
    Pb = SC.load_hero_world()
    sd_src = np.fromfile(WM_05B, np.float32).astype(np.float64).reshape(nr, nc)
    sd_04f = np.fromfile(WM_04F, np.float32).astype(np.float64).reshape(nr, nc)
    z = np.load(CAND + "_rows.npz"); c = z["c"].astype(np.float64); A = z["A"].astype(np.float64); Y = z["Y"].astype(np.float64)
    z0 = np.load(ROWS_04F); A0 = z0["A"]; Y0 = z0["Y"]
    log = json.load(open(CAND + "_build_log.json", encoding="utf-8"))["log"]
    fz = np.load(CAND + "_fields.npz")
    fb, f2, f3 = fz["base"].astype(np.float64), fz["r2"].astype(np.float64), fz["r3"].astype(np.float64)
    rows_log = {r["row"]: r for r in log["rows"]}
    white = sd_src > 0
    changed = (np.abs(A - A0).max(1) + np.abs(Y - Y0).max(1)) > 1e-4
    per_row = []
    for i in np.nonzero(changed)[0]:
        w = sd_04f[i] > 0
        w[RULE["col_back_white"] + 1:] = False
        r = rows_log.get(int(i), {})
        info = []
        for key, fk, fo in (("r2", f2, f3), ("r3", f3, f2)):
            if key not in r or r[key]["f"] < RULE["f_min"] or c[i] < RULE["c_min_white"]:
                continue
            P = np.array(r[key]["P"], float)
            groove, rim, nose, utip = P[2], P[3], P[4], P[5]
            dom = np.isfinite(fk[i]) & (fk[i] < np.nan_to_num(fb[i], nan=9.0)) & (fk[i] < np.nan_to_num(fo[i], nan=9.0)) & (fk[i] < RULE["label_d_m"])
            if RULE["mode"] == "crest":
                # 縁の頂の帯：縁の頂から後ろへ back_crest_m、前は唇の前の面の上の半分（鼻と唇の下の先の中ほど）まで
                band = dom & (A[i] >= rim[0] - RULE["back_crest_m"]) & (Y[i] >= 0.5 * (nose[1] + utip[1]))
            else:
                band = dom & (A[i] >= groove[0] - RULE["back_m"]) & (Y[i] >= utip[1] - RULE["drop_m"])
            band[:RULE["col_back_white"] + 1] = False
            w |= band
            info.append([key, int(band.sum())])
        white[i] = w
        per_row.append([round(float(c[i]), 2), info])
    t6_rows = []
    sd_sign = np.where(white, np.maximum(np.abs(sd_src), 0.01), -np.maximum(np.abs(sd_src), 0.01))
    sd_new = M.resigned_distance(Pb, sd_sign)
    Hrow = Pb[:, 18:201, 1].max(1)
    cap = (Hrow - M.LOW_H0 * M.H0) * M.LOW_K
    sd_new = np.minimum(sd_new, cap[:, None])
    MO = os.environ.get("AS06L_MESH_OUT", SH)          # 材質の試し（白の範囲の変種）を別の置き場へ書く時
    os.makedirs(MO + "/mesh", exist_ok=True)
    wm = MO + "/mesh/white_mask_as06l_f32.bin"
    sd_new.astype(np.float32).tofile(wm)
    wrep = {"source_mask_unchanged_rows": WM_05B, "source_sha256": SC.sha(WM_05B), "source_mask_changed_rows": WM_04F, "source04f_sha256": SC.sha(WM_04F),
            "out": wm, "out_sha256": SC.sha(wm), "rule": RULE,
            "changed_rows": int(changed.sum()), "step_rows_rim_col": per_row, "t6_rows_cut": t6_rows,
            "white_vertices_source_new": [int((sd_src > 0).sum()), int((sd_new > 0).sum())],
            "note_ja": "作り直した行は背の頂の白と、塊ごとの縁の頂の帯だけ白（凹み・下の面・蹴込みは藍）。作り直していない行は B10 の白（T6 の直しを含む）。境からの距離を AS06L の面の上で測り直した。"}
    SC.GWB = CAND + ".gwb"
    SC.META = CAND + "_meta.json"
    SC.ROWS = CAND + "_rows.npz"
    SC.ATTR = SH + "/attr/a/s01a_hero_attr_v2_f32.bin"
    SC.OUT = MO
    R.S = SC
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat", "--white-mask", wm, "--c-range=" + os.environ.get("AS06L_C_RANGE", "-24.4,18")]   # ③ の左の端（c −23.6 m まで）を静止のメッシュに入れる
    R.main()
    rp = MO + "/mesh/" + NAME + "_report.json"
    rep = json.load(open(rp, encoding="utf-8"))
    rep["as06l_white_mask"] = wrep
    rep["as06l_inputs"] = {"hero_pkg": SC.HERO_PKG, "gwb": SC.GWB, "meta": SC.META, "rows": SC.ROWS, "attr": SC.ATTR}
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps({k: v for k, v in wrep.items() if k not in ("step_rows_rim_col", "t6_rows_cut")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
