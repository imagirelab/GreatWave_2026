# -*- coding: utf-8 -*-
"""設計29修正01（手渡し (a) の記録の読み）：t* の色区の項目を「輪郭の両側を除く」読みでも測る。

美術優先28修正01 の評価器（af28r01_evaluate.py、番号28 の af28_evaluate.ClassBoundary）は、空との境（主役波の輪郭。78〜132・72 の対象）を
色区の境界の項目から除くのに、真値の点は「真値の空から 2 px 以内」、描画の点は「描画の空から 2 px 以内」だけを除く。
K* では輪郭の差が 1.4〜1.8 px だったので、この片側の除き方で足りた。K*′ は輪郭の差が 2.7〜3.8 px（設計28修正01 で採った関門）なので、
**描画の空が原画の色区へ食い込んだ所**で、真値の点（真値の空からは 2 px より遠い）が描画の輪郭の外に落ち、色区の境界の値に輪郭の差が入る。
ここでは、同じ評価器を同じプロセスの中だけで次のように変えて走らせる（元のファイルは変えない。**記録の読みで、評価器の判定ではない**）：
  - ClassBoundary：真値の点も描画の点も、「真値の空または描画の空から 2 px 以内」なら除く（輪郭の両側を除く。除く幅 2 px は同じ）。
  - 267・266 の原画視点の平塗り：真値の色区を 3 px 縮めた範囲から、さらに描画の空から 2 px 以内を除いた範囲で測る（描画の空は輪郭の差）。
同じ読みを、美術優先28修正01 の描画（K* ＋ K* の焼き込み）にも当てて、同じ読み同士で比べる（±0.5 px）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_tstar_sym.py
入力：Unity/Build/Design/29R01/unity/f_final_kp/t28（ds29r01_tstar_eval.py が並べたもの）、Unity/Build/ArtFirst/28修正01（読むだけ。写しで測る）
出力（Git 対象外）：Unity/Build/Design/29R01/unity/tstar_sym/{kp,base28}/evidence/metrics.json と tstar_sym.json
"""
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
COLOUR = os.path.join(REPO, "Tools", "PaintingTruth", "colour")
sys.path.insert(0, COLOUR)
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
import truthlib as T  # noqa: E402
import colour_truth as CT  # noqa: E402
import af28_evaluate as E  # noqa: E402
import af28r01_evaluate as R  # noqa: E402
import cv2  # noqa: E402

OUT = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity", "tstar_sym")
KP_T28 = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity", "f_final_kp", "t28")
B28 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01")
EX = None
ITEMS = ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]


def patch_classboundary():
    orig = E.ClassBoundary.__init__

    def init(self, k, cov_t, cov_r, sigma, dsky_t, dsky_r, ex):
        orig(self, k, cov_t, cov_r, sigma, dsky_t, dsky_r, ex)
        self.tp_sky = self.tp_sky | (E.sample(dsky_r, self.tp) <= ex)
        self.rp_sky = self.rp_sky | (E.sample(dsky_t, self.rp) <= ex)
    E.ClassBoundary.__init__ = init


def stage_base28(dst):
    """美術優先28修正01 の描画を写して測る（評価器は build の下へ eval23_* を書くので、元のフォルダーでは走らせない）。"""
    os.makedirs(dst, exist_ok=True)
    rd = os.path.join(dst, "render")
    if os.path.exists(rd):
        shutil.rmtree(rd)
    shutil.copytree(os.path.join(B28, "render"), rd)
    for sub in ("bake", "bake_input"):
        d = os.path.join(dst, sub)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(os.path.join(B28, sub)):
            s, t = os.path.join(B28, sub, f), os.path.join(d, f)
            if not os.path.exists(t):
                try:
                    os.link(s, t)
                except OSError:
                    shutil.copy2(s, t)
    for f in ("af28r01_render_report.json", "af28r01_build_report.json"):
        shutil.copy2(os.path.join(B28, f), os.path.join(dst, f))


def stage_kp(dst):
    os.makedirs(dst, exist_ok=True)
    for sub in ("render", "bake", "bake_input"):
        d = os.path.join(dst, sub)
        if os.path.exists(d):
            shutil.rmtree(d)
        if sub == "render":
            shutil.copytree(os.path.join(KP_T28, sub), d)
        else:
            os.makedirs(d)
            for f in os.listdir(os.path.join(KP_T28, sub)):
                try:
                    os.link(os.path.join(KP_T28, sub, f), os.path.join(d, f))
                except OSError:
                    shutil.copy2(os.path.join(KP_T28, sub, f), os.path.join(d, f))
    for f in ("af28r01_render_report.json", "af28r01_build_report.json"):
        shutil.copy2(os.path.join(KP_T28, f), os.path.join(dst, f))


def flat_painting(rdir, ex):
    """266・267 の原画視点：真値の色区を 3 px 縮め、描画の空から ex px 以内を除いた範囲の平塗り。"""
    stage = os.path.join(REPO, R.STAGE_REL)
    z, fr, cov_t, lab_t = E.truth_maps(stage)
    ids, cov_raw, cov_r, lab_r, unknown = E.render_maps(os.path.join(rdir, "af28r01_class_ids.png"), cov_t)
    dsky_r = E.dist_to(cov_r["sky"] >= 0.5)
    lab_pk = E.lab_img(os.path.join(rdir, "af28r01_painting_kstar.png"))
    pal = T.load_json(os.path.join(rdir, "..", "bake_input", "af28_bake_input_record.json"))["palette"]
    out = {}
    for k in ("white", "mizuiro", "ai_mid", "ai_dark"):
        mt0 = cv2.erode((lab_t == E.CLS_VAL[k]).astype(np.uint8), CT.disk(3)) > 0
        mt = mt0 & (dsky_r > ex)
        out[k] = {"strict": E.region_stats(lab_pk, mt0, pal[k]["lab"]), "sym": E.region_stats(lab_pk, mt, pal[k]["lab"]),
                  "px_removed_near_render_sky": int((mt0 & ~(dsky_r > ex)).sum())}
    return out


def run_eval(build, tag, kstar_dir):
    P = T.load_json(os.path.join(COLOUR, "af28r01_params.json"))
    rel = os.path.relpath(build, REPO).replace("\\", "/")
    P["build_dir"] = rel
    P["evidence_dir"] = rel + "/evidence"
    P["kstar_dir"] = kstar_dir
    P["note_ja"] = "設計29修正01 の輪郭の両側を除く読み（記録）の一時の params（Git 対象外）。" + tag
    pp = os.path.join(build, "sym_params.json")
    T.save_json(pp, P)
    R.PARAMS_REL = rel + "/sym_params.json"
    R.main()
    return T.load_json(os.path.join(build, "evidence", "metrics.json"))


def flatten(v, path=""):
    out = {}
    if isinstance(v, dict):
        if "max_px" in v and isinstance(v["max_px"], (int, float)):
            out[path or "."] = v["max_px"]
        for k, x in v.items():
            if isinstance(x, dict):
                out.update(flatten(x, (path + "/" if path else "") + k))
    return out


def main():
    global EX
    P = T.load_json(os.path.join(COLOUR, "af28r01_params.json"))
    EX = float(P["eval"]["silhouette_exclude_px"])
    patch_classboundary()
    kp = os.path.join(OUT, "kp")
    b28 = os.path.join(OUT, "base28")
    stage_kp(kp)
    stage_base28(b28)
    m_kp = run_eval(kp, "K*′ ＋ K*′ の焼き込み（設計29修正01 の F_final の t*）", "Unity/Build/Design/29R01/bake_kp/kstar")
    m_28 = run_eval(b28, "K* ＋ K* の焼き込み（美術優先28修正01 の描画の写し）", "Unity/Build/ArtFirst/26修正01/kstar")
    rows = []
    worst = 0.0
    for k in ITEMS:
        a = flatten(m_kp["items"][k]["value"])
        b = flatten(m_28["items"][k]["value"])
        for p in sorted(set(a) & set(b)):
            d = a[p] - b[p]
            if k == "175" and "lost" in p:
                continue
            worst = max(worst, abs(d))
            rows.append({"item": k, "measure": p, "kp_sym_max_px": round(a[p], 4), "r28_sym_max_px": round(b[p], 4), "diff_px": round(d, 4),
                         "kp_verdict_sym": m_kp["items"][k]["verdict"], "r28_verdict_sym": m_28["items"][k]["verdict"]})
    flat = {"kp": flat_painting(os.path.join(kp, "render"), EX), "base28": flat_painting(os.path.join(b28, "render"), EX)}
    res = {"schema": "GreatWave.DS29R01.tstar_sym/1", "number": "設計29修正01", "method_ja": __doc__.strip(), "silhouette_exclude_px": EX,
           "rows": rows, "worst_abs_diff_px": round(worst, 4), "criterion_px": 0.5, "pass": worst <= 0.5,
           "verdicts_kp_sym": m_kp["summary_verdicts"], "verdicts_28_sym": m_28["summary_verdicts"],
           "flat_painting_view_266_267": flat}
    T.save_json(os.path.join(OUT, "tstar_sym.json"), res)
    over = [r for r in rows if abs(r["diff_px"]) > 0.5]
    print("DS29R01_TSTAR_SYM worst=%.4f pass=%s over=%s" % (worst, worst <= 0.5, [(r["item"], r["measure"], r["diff_px"]) for r in over]))
    for k in ("white", "mizuiro", "ai_mid", "ai_dark"):
        s = flat["kp"][k]["sym"]
        print(k, "kp sym bands", s and s["bands_ge_20px"], "std", s and s["dE00_to_median_std"], "| strict bands", flat["kp"][k]["strict"]["bands_ge_20px"],
              "| base28 sym bands", flat["base28"][k]["sym"]["bands_ge_20px"], "removed", flat["kp"][k]["px_removed_near_render_sky"])


if __name__ == "__main__":
    main()
