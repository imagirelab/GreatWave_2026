# -*- coding: utf-8 -*-
"""RT48（計画 §5 の手順 3・4）：R3e の計算し直しが終わった後に、順に走らせる（r_chain.py --after が起動する。手で走らせてもよい）。
  1. C1 (b)（r_c1.py b）。外れたら止める（計画：細かい元を使わず、粗い元で続ける）。
  2. 粒子から作った細かい面（r_surface.py、優先度「通常より下」、作業 3 つ）。
  3. C2（r_c2.py）。外れても 4 まで進める（横からの絵で並べるため。動画と報告には使わないと目次に書く）。
  4. 細かい元の焼き（r_bake.py fine）と C3・C4・K。
  5. 目次 data/manifest.json を作り直す（r_index.py）。
  6. data/record_ja.md の「結果」に、この道具が書いたと分かる形で数を書き足す（判定の文は進行役が後で書く）。
py -3.10 r_after.py <run_dir>
記録：Unity/Build/RT48/data/after_log.txt"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json, time, subprocess

T = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("RT48_DATA", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/data")   # 試しの時だけ環境変数で替える
PY = sys.executable
BELOW_NORMAL = 0x00004000
LOG = os.path.join(DATA, "after_log.txt")


def log(*a):
    s = time.strftime("%Y-%m-%d %H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(s, flush=True)
    open(LOG, "a", encoding="utf8").write(s + "\n")


def run(args, name):
    log("start", name, " ".join(args))
    with open(os.path.join(DATA, "after_%s.txt" % name), "w", encoding="utf8", errors="ignore") as fh:
        rc = subprocess.run([PY] + args, stdout=fh, stderr=subprocess.STDOUT, creationflags=BELOW_NORMAL).returncode
    log("end", name, "exit", rc)
    return rc


def jl(p):
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def r(v, nd=3):
    """数を短く書く（None はそのまま）"""
    if v is None:
        return "なし"
    if isinstance(v, float):
        return ("%%.%df" % nd) % v
    return str(v)


def append_record(lines):
    p = os.path.join(DATA, "record_ja.md")
    with open(p, "a", encoding="utf8") as fh:
        fh.write("\n" + "\n".join(lines) + "\n")


def main():
    rd = sys.argv[1]
    fine = os.path.join(rd, "fine")
    lines = ["### %s r_after.py が書いた数（計算し直しの後。判定の言葉は進行役が確かめて別に書く）" % time.strftime("%Y-%m-%d %H:%M"), ""]
    rc = run([os.path.join(T, "r_c1.py"), "b", rd], "c1b")
    c1b = jl(os.path.join(DATA, "c1b.json"))
    if c1b:
        for k, v in c1b["kinds"].items():
            lines.append("- C1 (b) %s：比べたコマ %d、比べた数 %d、違った数 %d、R3e に足りないコマ %d【測った：c1b.json】" % (
                k, v["n_frames"], v["comparisons"], v["n_bad"], len(v["missing_in_rerun"])))
    lines.append("- C1 (b) の合否（道具の判定）：%s" % ("入った" if rc == 0 else "外れた"))
    if rc != 0:
        lines.append("- 計画のとおり、細かい元は作らずに止めた。")
        append_record(lines)
        run([os.path.join(T, "r_index.py")], "index")
        return 3
    TF = os.environ.get("RT48_TEST_FRAMES")      # 試しの時だけ（例 "3319,3738,3739"）
    TR = os.environ.get("RT48_TEST_RANGE")       # 試しの時だけ（例 "3738-3750"）
    rc = run([os.path.join(T, "r_surface.py"), rd, "--workers", "3"] + (["--frames", TF] if TF else []), "surface")
    if rc != 0:
        lines.append("- r_surface.py が止まった（exit %d、after_surface.txt）。" % rc)
        append_record(lines)
        return 4
    meta = jl(os.path.join(fine, "meta.json"))
    lines.append("- 細かい面：静かな水面のずれ %.4f m（3319 コマ目の差の中央値 %.4f m、列 %d）、粒子の半径 %s、列の全部を計算した列の数の合計 %d、"
                 "帯の端の食い違いの列の合計 %d、sec の外で交わりが 1 回でない列（直す前 %d・直した後 %d）、時間 %.0f s【測った：fine/meta.json】" % (
                     meta["still_offset_m"], meta["still_offset_note"]["median_fine_minus_solver"], meta["still_offset_note"]["n_cols"],
                     meta["radius_values"], meta["totals"]["cols_full_sum"], meta["totals"]["cols_edge_mismatch_sum"],
                     meta["totals"]["cols_multi_outside_sec_sum"], meta["totals"]["cols_multi_outside_sec_after_sum"], meta["seconds"]))
    rc2 = run([os.path.join(T, "r_c2.py"), fine, rd] + (["--frames", TF] if TF else []), "c2")
    c2 = jl(os.path.join(DATA, "c2.json"))
    if c2:
        lines.append("- C2 (a)：p99 %.3f m・最大 %.3f m（n %d）→ %s" % (c2["a"]["p99"], c2["a"]["max"], c2["a"]["n"], "入った" if c2["a"]["ok"] else "外れた"))
        b = c2["b"]
        lines.append("- C2 (b)：巻き始め %s コマ・%s m・η_c %s m（R3 3714・508.3・9.56）→ %s" % (r(b["onset_frame"]), r(b["onset_x_rel"], 2), r(b["eta_c"], 2), "入った" if b["ok"] else "外れた"))
        lines.append("- C2 (c)：細かい→解く %.3f m、解く→細かい %.3f m（除いた小さな水 細かい %d・解く %d）→ %s" % (
            c2["c"]["max_fine_to_solver"], c2["c"]["max_solver_to_fine"], c2["c"]["small_water_dropped"]["fine"], c2["c"]["small_water_dropped"]["solver"],
            "入った" if c2["c"]["ok"] else "外れた"))
        lines.append("- C2 (d)：最初の接触 %s コマ（R3 3745）→ %s" % (c2["d"]["first_contact_frame"], "入った" if c2["d"]["ok"] else "外れた"))
        e = c2["e"]
        lines.append("- C2 (e)：唇の最大 %s コマ、届く距離 %s m・厚み %s m（3.65・1.06 ± 0.5）→ %s" % (r(e["frame"]), r(e["reach"], 2), r(e["thick"], 2), "入った" if e["ok"] else "外れた"))
        # 焼きのために巻き始めのコマを細かい面の meta に入れる
        meta["onset_frame"] = b["onset_frame"]
        json.dump(meta, open(os.path.join(fine, "meta.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    rc3 = run([os.path.join(T, "r_bake.py"), "fine", fine] + (["--f0", TR.split("-")[0], "--f1", TR.split("-")[1]] if TR else []), "bake_fine")
    sm = jl(os.path.join(DATA, "fine", "summary.json"))
    if sm:
        lines.append("- 細かい元の焼き：K %s、補間する組 %d / %d、C3 最大 %.4f m（%s）、C4 外れ %d / %d（最大の最大 %.3f m・最大の p99 %.3f m）、観測した次数 %s、交わりで止めた組 %d" % (
            sm["K"], sm["n_interp"], sm["n_pairs"], sm["C3"]["max"], "入った" if sm["C3"]["ok"] else "外れた", sm["C4"]["n_fail"], sm["C4"]["n"],
            sm["C4"]["max_of_max"] or 0, sm["C4"]["max_of_p99"] or 0, r(sm["C4"]["p_observed"], 2), sm["self_x"]))
        for k, v in sm["boat"].items():
            lines.append("- 座席 %s m：かぶさった水が船体に入るコマ %s、終わり %s コマ（%.3f s）。粗い元では座席 556 m が 3772・574 m が 3797（細かい元で早く出たら終わりを早める。計画 §1.2）" % (k, r(v["overturned_on_hull_frame"]), v["clip_end_frame"], v["clip_end_t"]))
    run([os.path.join(T, "r_index.py")], "index")
    append_record(lines)
    log("after done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
