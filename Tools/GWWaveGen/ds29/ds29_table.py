# -*- coding: utf-8 -*-
"""設計29：密度ごとの点検の表（ds29_measure.py の出力 → Markdown と JSON）。

使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/ds29/ds29_table.py [--names src,half_120x200,full_240x400,double_480x800,...]
        [--measure Unity/Build/Design/29/measure] [--out Docs/Evidence/Design/29]
        [--packages Unity/Build/Design/29/r01]
出力：<out>/ds29_display_table.md・ds29_display_table.json（・ds29_packages.json：層・容量・SHA-256）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


ITEMS = [("(1)", "1 コマの変位 < 0.6 m"), ("(2)", "二階差分 ≤ 2g"), ("(3)", "最も低い点"), ("(4)", "頂の単調"), ("(5a)", "三角形の面積"),
         ("(5b)", "行の方向の辺 ≥ 5 mm"), ("(5c)", "行の方向の伸び 0.05〜4"), ("(5d)", "行の間の伸び 0.05〜4"), ("(5e)", "rim の継ぎ目 0.25〜4"),
         ("(5f)", "自己交差 0"), ("(5g)", "面の反転 0"), ("(6)", "法線が有限")]


def fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, list):
        return "〜".join(fmt(x, nd) for x in v)
    if isinstance(v, float):
        if abs(v) >= 100:
            return "%.0f" % v
        return ("%%.%dg" % nd) % v
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="src,half_120x200,full_240x400,double_480x800")
    ap.add_argument("--measure", default=os.path.join(REPO, "Unity", "Build", "Design", "29", "measure"))
    ap.add_argument("--out", default=os.path.join(REPO, "Docs", "Evidence", "Design", "29"))
    ap.add_argument("--packages", default="", help="パッケージの根（例 Unity/Build/Design/29/r01）。あれば ds29_packages.json に層・容量・SHA-256 を書く")
    a = ap.parse_args()
    names = [n for n in a.names.split(",") if n]
    R = {}
    for n in names:
        p = os.path.join(a.measure, n + ".json")
        if os.path.isfile(p):
            R[n] = json.load(open(p, encoding="utf-8"))
        else:
            print("なし：%s" % p, file=sys.stderr)
    names = [n for n in names if n in R]
    L = []
    L.append("| 項目 | " + " | ".join("%s（%d × %d）" % ("設計28 の源" if n == "src" else n, R[n]["rows"], R[n]["cols"]) for n in names) + " |")
    L.append("| --- |" + " --- |" * len(names))

    def row(label, f):
        L.append("| %s | %s |" % (label, " | ".join(f(R[n]) for n in names)))
    row("頂点・三角形", lambda r: "%d・%d" % (r["vertices"], r["triangles"]))
    row("層", lambda r: str(r["layers"]))
    for key, lab in ITEMS:
        def f(r, key=key):
            it = r["P13"]["items"][key]
            v = it["value"]
            s = fmt(v, 3)
            if key in ("(5a)", "(5b)", "(5c)", "(5d)", "(5e)"):
                s += "（違反 %d）" % it["at"].get("violations", 0)
            return ("**不合格** " if not it["pass_"] else "合格 ") + s
        row("P13 " + key + " " + lab, f)
    row("P13 の不合格の数", lambda r: "%d / %d" % (r["P13"]["n_fail"], r["P13"]["n_items"]))

    def film_f(tau, d, nm="exact"):
        def f(r):
            e = r["film"].get(tau)
            if not e:
                return "—"
            x = e[nm]["d_%.1fm" % d]
            return "%s m（0.3 m 未満 %d 行／%d）" % (fmt(x["min_m"]), x["rows_below_min"], x["rows"])
        return f
    for tau in ("0.0", "-0.5", "-1.333", "-2.25"):
        row("薄膜 τ %s、唇先から 1.0 m の厚みの最小" % tau, film_f(tau, 1.0))
    row("薄膜 t*、唇先から 0.5 m", film_f("0.0", 0.5))
    row("薄膜 t*、唇先から 2.0 m", film_f("0.0", 2.0))
    row("波頭の欠落：頂の高さ（正確な網、最大／RMS）", lambda r: "%s／%s m" % (fmt(r["crest_loss"]["exact_crest_height"]["max_m"]), fmt(r["crest_loss"]["exact_crest_height"]["rms_m"])))
    row("波頭の欠落：唇の前への届き（正確な網、最大／RMS）", lambda r: "%s／%s m" % (fmt(r["crest_loss"]["exact_lip_reach"]["max_m"]), fmt(r["crest_loss"]["exact_lip_reach"]["rms_m"])))
    row("波頭の欠落：頂の高さ（再生、最大／RMS）", lambda r: "%s／%s m" % (fmt(r["crest_loss"]["playback_crest_height"]["max_m"]), fmt(r["crest_loss"]["playback_crest_height"]["rms_m"])))
    row("波頭の欠落：唇の届き（再生、最大／RMS）", lambda r: "%s／%s m" % (fmt(r["crest_loss"]["playback_lip_reach"]["max_m"]), fmt(r["crest_loss"]["playback_lip_reach"]["rms_m"])))
    row("設計28 の動きとの面の差（弦、最大／RMS）", lambda r: ("%s／%s m（法線 %s／%s）" % (fmt(r["deviation_from_ds28_motion"]["chord_dist_max_m"]), fmt(r["deviation_from_ds28_motion"]["chord_dist_rms_m"]),
                                                                        fmt(r["deviation_from_ds28_motion"]["chord_normal_max_m"]), fmt(r["deviation_from_ds28_motion"]["chord_normal_rms_m"])))
        if r["deviation_from_ds28_motion"] else "0（源そのもの）")
    row("t* の K* との面の差（弦、最大／RMS）", lambda r: ("%s／%s m（法線 %s／%s）" % (fmt(r["tstar"]["vs_kstar_chord_dist_max_m"]), fmt(r["tstar"]["vs_kstar_chord_dist_rms_m"]),
                                                               fmt(r["tstar"]["vs_kstar_chord_normal_max_m"]), fmt(r["tstar"]["vs_kstar_chord_normal_rms_m"])))
        if "vs_kstar_chord_dist_max_m" in r["tstar"] else "頂点 %s m" % fmt(r["tstar"].get("package_last_layer_vs_kstar_max_m")))
    row("Hermite：30 Hz の全コマ（最大）", lambda r: "%s mm" % fmt(r["hermite"]["frames_30hz_max_m"] * 1000))
    row("Hermite：区間の中点（間隔が一様）", lambda r: "%s mm（%d 点）" % (fmt(r["hermite"]["uniform_interval_midpoints"]["max_m"] * 1000), r["hermite"]["uniform_interval_midpoints"]["n"]))
    row("Hermite：間隔が変わる区間（比 ≥ 1.5）", lambda r: "%s mm（%d 区間、τ %s）" % (fmt(r["hermite"]["nonuniform_intervals"]["max_m"] * 1000), r["hermite"]["nonuniform_intervals"]["n_intervals"],
                                                                        fmt(r["hermite"]["nonuniform_intervals"]["at_tau"])))
    row("GPU：位置のバッファ（読み取り不可）", lambda r: "%.1f MiB" % r["gpu"]["position_buffer_mib"])
    row("GPU：合計の見積もり（位置＋T_white＋網）", lambda r: "%.1f MiB（%s）" % (r["gpu"]["total_mib_estimate"], "≤ 512" if r["gpu"]["within_512"] else "**> 512**"))
    md = "\n".join(L) + "\n"
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "ds29_display_table.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    slim = {n: dict(rows=R[n]["rows"], cols=R[n]["cols"], vertices=R[n]["vertices"], layers=R[n]["layers"], P13=R[n]["P13"], film=R[n]["film"],
                    crest_loss=R[n]["crest_loss"], deviation_from_ds28_motion=R[n]["deviation_from_ds28_motion"], tstar=R[n]["tstar"],
                    hermite={k: v for k, v in R[n]["hermite"].items()}, gpu=R[n]["gpu"]) for n in names}
    with open(os.path.join(a.out, "ds29_display_table.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(slim, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if a.packages:
        root = os.path.abspath(a.packages)
        pk = {}
        for n in names:
            if n == "src":
                continue
            d = os.path.join(root, n)
            J = json.load(open(os.path.join(d, "ds27_keypose.json"), encoding="utf-8"))
            ds = J["display_surface"]
            pk[n] = dict(dir=os.path.relpath(d, REPO).replace("\\", "/"), rows=J["rows"], cols=J["cols"], layers=J["layers"],
                         knot_tau_range=[J["knot_tau"][0], J["knot_tau"][-1]], pos_sha256=J["pos_sha256"], pos_bytes=J["pos_bytes"],
                         twhite_sha256=J["twhite_sha256"], uv3_sha256=ds["uv3_sha256"], tstar_gwb_sha256=ds["tstar_mesh_sha256"],
                         keypose_json_sha256=_sha(os.path.join(d, "ds27_keypose.json")), gpu_estimate=J["gpu_estimate"],
                         quantization_max_err_m=J["quantization_max_err_m"], segments=ds["segments"], region=ds["region"])
        bl = os.path.join(root, "ds29_build_log.json")
        out = dict(packages=pk, build_log=os.path.relpath(bl, REPO).replace("\\", "/") if os.path.isfile(bl) else None)
        if os.path.isfile(bl):
            B = json.load(open(bl, encoding="utf-8"))
            out["build"] = dict(code_sha256=B["code_sha256"], source_repro_max_m=B["source_repro_max_m"], seconds_total=B["seconds_total"],
                                adaptive_rounds={k: v["adaptive_rounds"] for k, v in B["displays"].items()})
        with open(os.path.join(a.out, "ds29_packages.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write("\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
