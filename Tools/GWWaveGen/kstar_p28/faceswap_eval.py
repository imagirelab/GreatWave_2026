# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：候補を R4 と並べて評価する（py -3.10）。

1. kstar_h/kh_eval.py（関門：定義どおりの読み・σ12・σ24、評価基準 F01〜F13、Q21 の検査、評審の膨らみ j_bulge6、網の衛生、
   粘土の 9 視点＋利用者の失敗の視点、ターンテーブル）を、出力と参照モデルの一時キャッシュの置き場所をこの回のフォルダーに替えて走らせる
   （kh_common.OUT_ROOT / TMP を差し替える。キャッシュは F13 と量感の数値のためだけに作り、最後に消して SHA-256 を記録する）。
2. 追加の検査 faceswap_extra.json：左の外輪郭を描く点（FACE-SWAP の確かめ）、背のくびれ（kh_R4_notch）、背と管の壁の厚み、
   頂の ±2 m の弦の角（t* の頂と手前の尾が弧か）、三角形どうしの自己交差（Blender BVH、kh_R1_selfx_bl.py）。
usage: py -3.10 faceswap_eval.py <out_dir> R4=<rows.npz> FS1=<rows.npz> [--no-render]
"""
import os
import sys
import json
import subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import faceswap_common as F  # noqa: E402
import faceswap_wall as FW  # noqa: E402
KC = F.KC


def extra(out, items):
    import kh_R4_notch as NT
    res = {}
    gw = {}
    for lab, p in items:
        z = np.load(p)
        c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
        wt = FW.summary(c, A, Y)
        bands = {}
        for lo, hi in ((-30, -16), (-16, -6), (-6, 3), (3, 8), (8, 15.1)):
            v = [x for x in wt if lo <= x[0] < hi]
            if v:
                k = min(v, key=lambda t: t[1])
                bands["c%g..%g" % (lo, hi)] = {"min_m": round(k[1], 3), "at_c": round(k[0], 2), "min_over_H": round(k[1] / max(k[3], 1e-6), 3)}
        ch = F.chord_table(c, A, Y, c_lo=-45, c_hi=15)
        tail = [x for x in ch if -39.8 <= x[0] <= -26.6]
        main = [x for x in ch if -24.0 <= x[0] <= 12.0]
        res[lab] = {
            "outline_generators_78_130_131": F.outline_generators(c, A, Y, n_per=9),
            "outline_generator_shift_vs_R4": F.generator_shift(c, A, Y, n_per=9),
            "back_notch_kh_R4_notch": NT.all_notches(c, A, Y),
            "wall_thickness_back_to_tube_m": bands,
            "apex_chord_pm2m_deg": {"near_tail_c-39.8..-26.6_min": min(x[2] for x in tail) if tail else None,
                                    "near_tail_rows_below_110": sum(1 for x in tail if x[2] < 110),
                                    "main_c-24..+12_min": min(x[2] for x in main) if main else None,
                                    "main_rows_below_110": sum(1 for x in main if x[2] < 110),
                                    "main_rows_below_125": sum(1 for x in main if x[2] < 125),
                                    "table_every_4th": ch[::4]},
            "row_max_col_not_90pm5_rows_Hgt1": int(sum(1 for r in range(len(c)) if Y[r].max() > 1 and abs(int(np.argmax(Y[r, :200])) - 90) > 5)),
        }
        # GWW0 for the Blender BVH
        g = os.path.join(out, "_%s_bvh.gwb" % lab)
        uvk, _ = KC.kstar_uv()
        KC.write_gwb(g, A.shape[1], A.shape[0], uvk.reshape(-1, 2), uvk.reshape(-1, 2), KC.triangles(A.shape[1], A.shape[0]), KC.world(c, A, Y))
        gw[lab] = g
    bj = os.path.join(out, "selfx_bvh.json")
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
           os.path.join(KC.HERE, "kh_R1_selfx_bl.py"), "--", bj] + ["%s=%s" % (k, v) for k, v in gw.items()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if r.returncode == 0 and os.path.isfile(bj):
        sx = json.load(open(bj))
        for lab in sx:
            res[lab]["selfx_bvh"] = {k: v for k, v in sx[lab].items() if k in ("pairs_all", "pairs_resolvable_alt5mm", "pairs_distant",
                                                                               "vertices_involved", "n_rows_involved", "distant_samples")}
    else:
        for lab in gw:
            res[lab]["selfx_bvh"] = {"error": (r.stdout[-500:] + r.stderr[-500:])}
    for g in gw.values():
        if os.path.isfile(g):
            os.remove(g)
    json.dump(res, open(os.path.join(out, "faceswap_extra.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return res


def main():
    out = os.path.abspath(sys.argv[1])
    items = [a.split("=", 1) for a in sys.argv[2:] if "=" in a]
    os.makedirs(out, exist_ok=True)
    # 1. kh_eval（出力とキャッシュの置き場所をこの回のフォルダーへ）
    KC.OUT_ROOT = out
    KC.TMP = os.path.join(out, "_tmp")
    import kh_eval as KE
    args = ["kh_eval.py", "--out", out]
    if "--no-render" not in sys.argv:
        args += ["--turntable"]
    args += ["%s=%s" % (l, p) for l, p in items]
    sys.argv = args
    KE.main()
    # 2. 追加の検査
    res = extra(out, items)
    for lab in res:
        print(lab, json.dumps({k: v for k, v in res[lab].items() if k in ("back_notch_kh_R4_notch", "wall_thickness_back_to_tube_m",
                                                                         "row_max_col_not_90pm5_rows_Hgt1")}, ensure_ascii=False)[:1500])
        print(lab, "chord", {k: v for k, v in res[lab]["apex_chord_pm2m_deg"].items() if k != "table_every_4th"}, "selfx", res[lab].get("selfx_bvh"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
