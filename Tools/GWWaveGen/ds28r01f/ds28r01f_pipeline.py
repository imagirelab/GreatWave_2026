# -*- coding: utf-8 -*-
"""設計28修正01 試行F：K*′ のフォルダーを 1 つ渡すと、生成から検査まで全部を行う 1 つの命令。

  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_pipeline.py --kstar <K*′ のフォルダー> --tag F_R3
      [--root Unity/Build/Design/28R01F] [--no-copy] [--skip-generate] [--workers 14] [--check-workers 12]

1. K*′ の 3 つのファイル（*.gwb・*_rows.npz・*_meta.json）を <根>/kstar_<tag>/ へ写す（別の作業がフォルダーを動かしても壊れないように。
   SHA-256 を <根>/kstar_<tag>/_copied_from.json に記録。--no-copy で写さない）。
2. 生成：ds28r01f_generate.py（パッケージ <根>/<tag>/art_on/、F の層の P20 <根>/<tag>/art_on/p20_f_layers.json）。
3. 時間曲線（ds28r01f_warp.py）：<根>/<tag>/timewarp_<tag>.json（E の P10H を、この K*′ の主断面の前面が鉛直になる時刻へずらす。Unity の再生器の -WarpFile）
   検査を並べて（ds28r01d_pipeline.run_parallel。画面の時刻はこの時間曲線で）：
   関門（設計27・28 の検査器、試行D の包みで K*′ を渡す）：<根>/<tag>/gates/{default（16 bit）,default_fine（精度の層）,default_fine_stop13,alt,default_q13}.json
   Q13 の重なりの独立の検査器：<根>/<tag>/overlap/overlap_default.json
   目標の検査器（試行E の検査器を K*′ の行で。ds28r01f_review.py）：<根>/review/review_<tag>.json
   走査（M1〜M3。ds28r01f_scan.py）：<根>/<tag>/scan.json
   E から受け継いだ名前の付いた値の P20（ds28r01e_p20.py、この K*′ で）：<根>/<tag>/p20_e/*.json（--skip-p20-e で省く）
   ds_back_width_retarget の P20（ds28r01f_p20.py、生成と同じ条件）：<根>/<tag>/art_on/p20_back_width_retarget.json
   （F_final の後）ds_anchor_retarget・ds_far_hook_early の P20：<根>/<tag>/art_on/p20_{anchor_retarget,far_hook_early}.json
4. 比べの表（ds28r01f_table.py）：<根>/table_E_F.{json,md}（あるタグを全部並べる）
ログは <根>/logs/<tag>_*.log。時間は <根>/<tag>/pipeline_timing.json。

［仕上げ27（2026-09-30）］生成器の既定に 2 つの数値の条件（num_balance_swell_calm・num_sea_sample_range）が入った。採用の F_final を
作り直すときは --off balance_swell_calm,sea_sample_range を付ける（付けないと仕上げ27 の F_p27 と同じ中身を F_final の名前で作る）。
［仕上げ27 の修正 1 回目］生成の前に、<根>/<tag>/art_on/ に既にある包みの生成の記録と比べ、記録では入っていない（または名前が無い）
F の名前が今の既定と --off で入るなら止める（ds28r01f_pkglog.rebuild_conflicts。採用の包みを新しい既定で上書きしないため）。
新しい既定で作るなら別の --tag にする。
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "ds28r01d")))
import ds28r01d_pipeline as PD  # noqa: E402


def check_rebuild(root_dir, tag, off):
    """［仕上げ27 の修正 1 回目］<root_dir>/<tag>/art_on/ に既にある包みを、記録と違う F の名前の入り切りで上書きしないかを確かめる。
    戻り：(止める名前の list, 記録では入っていたのに --off で切る名前の list)。包みが無ければ ([], [])。"""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import ds28r01f_pkglog as PL
    old = PL.load_result(os.path.join(root_dir, tag, "art_on"))
    if old is None:
        return [], []
    fon = old.get("f_on") or {}
    return PL.rebuild_conflicts(old, off), [n for n in off if fon.get(n, False)]

PY = ["py", "-3.10", "-B"]                        # 生成と走査は自分で電力の抑制を切る
PYL = PY + ["Tools/GWWaveGen/ds28r01f/ds28r01f_proc.py"]   # 関門・検査器は起動器で電力の抑制を切ってから走らせる（ds28r01f_proc.py）
WARP = None                                       # F の時間曲線（main の中で <根>/<tag>/timewarp_<tag>.json）
T = "Tools/GWWaveGen"
WARP_E = "%s/ds28r01e/timewarp_default_E.json" % T   # E の時間曲線（記録。F は <根>/<tag>/timewarp_<tag>.json）
WARP_ALT = "%s/ds27/timewarp_alt.json" % T


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy_kstar(src, dst):
    srcA = src if os.path.isabs(src) else os.path.join(REPO, src)
    os.makedirs(dst, exist_ok=True)
    rec = dict(source=os.path.relpath(srcA, REPO).replace("\\", "/"), files={})
    for pat in ("*.gwb", "*_rows.npz", "*_meta.json"):
        c = sorted(glob.glob(os.path.join(srcA, pat)))
        if len(c) != 1:
            raise SystemExit("[ds28r01f_pipeline] %s に %s がちょうど 1 つ要ります（%d 個）" % (src, pat, len(c)))
        d = os.path.join(dst, os.path.basename(c[0]))
        if not os.path.isfile(d) or sha(d) != sha(c[0]):
            shutil.copy2(c[0], d)
        rec["files"][os.path.basename(c[0])] = sha(d)
    for old in glob.glob(os.path.join(dst, "*")):
        if os.path.isfile(old) and os.path.basename(old) not in rec["files"] and not old.endswith("_copied_from.json"):
            raise SystemExit("[ds28r01f_pipeline] %s に余分なファイルがあります：%s" % (dst, old))
    rec["copied_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(dst, "_copied_from.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def main():
    global WARP
    ap = argparse.ArgumentParser()
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--root", default="Unity/Build/Design/28R01F")
    ap.add_argument("--no-copy", action="store_true")
    ap.add_argument("--skip-generate", action="store_true")
    ap.add_argument("--skip-checks", action="store_true")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--check-workers", type=int, default=12)
    ap.add_argument("--skip-p20-e", action="store_true", help="E から受け継いだ値の P20（生成器を 2 つずつ作る、約 10 分）を省く")
    ap.add_argument("--off", default="", help="生成器へそのまま渡す切る名前（, 区切り。仕上げ27：F_final の再現は balance_swell_calm,sea_sample_range）")
    a = ap.parse_args()
    t_all = time.time()
    root = a.root.replace("\\", "/")
    B = os.path.join(REPO, root)
    logd = os.path.join(B, "logs")
    os.makedirs(logd, exist_ok=True)
    tag = a.tag
    timing = {}
    if not a.skip_generate:
        bad_on, now_off = check_rebuild(B, tag, [s for s in a.off.split(",") if s])
        if bad_on:
            raise SystemExit("[ds28r01f_pipeline] %s/%s/art_on の包みの生成の記録では入っていない（または名前が無い）F の名前 %s が、今の既定で入ります。"
                             "この包みを作り直すなら --off %s を付けてください（F_final は --off balance_swell_calm,sea_sample_range）。"
                             "新しい既定で作るなら別の --tag にしてください（仕上げ27）"
                             % (root, tag, ",".join(bad_on), ",".join(sorted(set(bad_on) | set(s for s in a.off.split(",") if s)))))
        if now_off:
            print("注意：%s/%s/art_on の包みの記録で入っていた %s を --off で切って上書きします" % (root, tag, ",".join(now_off)), flush=True)
    if a.no_copy:
        kdir = a.kstar
    else:
        kdir = "%s/kstar_%s" % (root, tag)
        rec = copy_kstar(a.kstar, os.path.join(REPO, kdir))
        print("K*′ を写した：%s → %s %s" % (rec["source"], kdir, {k: v[:12] for k, v in rec["files"].items()}), flush=True)
    pk = "%s/%s/art_on" % (root, tag)
    if not a.skip_generate:
        t0 = time.time()
        cmd = PY + ["%s/ds28r01f/ds28r01f_generate.py" % T, "--kstar", kdir, "--name", "%s/art_on" % tag, "--out", root]
        if a.workers:
            cmd += ["--workers", str(a.workers)]
        if a.off:
            cmd += ["--off", a.off]
        bad = PD.run_parallel([("%s_generate" % tag, cmd)], logd)
        timing["generate_s"] = round(time.time() - t0, 1)
        if bad:
            raise SystemExit("生成に失敗：%s（%s）" % (bad, os.path.join(logd, "%s_generate.log" % tag)))
    # 時間曲線（ds_timewarp_f）：E の P10H の速さの節点を、この K*′ の主断面の前面が鉛直になる時刻へずらす（ds28r01f_warp.py）
    warp = "%s/%s/timewarp_%s.json" % (root, tag, tag)
    if not a.skip_checks or not os.path.isfile(os.path.join(REPO, warp)):
        t0 = time.time()
        bad = PD.run_parallel([("%s_warp" % tag, PYL + ["%s/ds28r01f/ds28r01f_warp.py" % T, "--package", pk, "--kstar", kdir, "--out", warp])], logd)
        timing["warp_s"] = round(time.time() - t0, 1)
        if bad:
            raise SystemExit("時間曲線に失敗：%s" % bad)
    WARP = warp
    if not a.skip_checks:
        t0 = time.time()
        sea = pk + "/ds27_sea.npz"
        for sub in ("gates", "overlap"):
            os.makedirs(os.path.join(B, tag, sub), exist_ok=True)
        jobs = []
        g = PYL + ["%s/ds28r01d/ds28r01d_gates.py" % T, "--kstar", kdir, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("%s_gates_default" % tag, g + ["--timewarp", WARP, "--out", "%s/%s/gates/default.json" % (root, tag), "--table", "design26"]))
        jobs.append(("%s_gates_alt" % tag, g + ["--timewarp", WARP_ALT, "--out", "%s/%s/gates/alt.json" % (root, tag), "--table", "design26"]))
        jobs.append(("%s_gates_default_q13" % tag, g + ["--timewarp", WARP, "--out", "%s/%s/gates/default_q13.json" % (root, tag), "--table", "q13"]))
        gf = PYL + ["%s/ds28r01e/ds28r01e_gates.py" % T, "--kstar", kdir, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("%s_gates_default_fine" % tag, gf + ["--timewarp", WARP, "--out", "%s/%s/gates/default_fine.json" % (root, tag), "--table", "design26"]))
        gs = PYL + ["%s/ds28r01e/ds28r01e_gates.py" % T, "--stop-max", "1.3", "--kstar", kdir, "--tool", "gates", "--", "--package", pk, "--sea", sea]
        jobs.append(("%s_gates_default_fine_stop13" % tag, gs + ["--timewarp", WARP, "--out", "%s/%s/gates/default_fine_stop13.json" % (root, tag),
                                                                 "--table", "design26"]))
        jobs.append(("%s_overlap" % tag, PYL + ["%s/ds28r01d/ds28r01d_gates.py" % T, "--kstar", kdir, "--tool", "overlap", "--",
                                              "--package", pk, "--tw-default", WARP, "--tw-alt", WARP_ALT,
                                              "--out", "%s/%s/overlap/overlap_default.json" % (root, tag),
                                              "--label", "設計28修正01 試行F %s 既定（art_on）" % tag]))
        jobs.append(("%s_review" % tag, PYL + ["%s/ds28r01f/ds28r01f_review.py" % T, "--kstar", kdir, "--tags", tag,
                                             "--tag-spec", "%s=%s|%s|%s|%s" % (tag, pk, WARP, kdir, "-3.85"),
                                             "--out", "%s/review/review_%s.json" % (root, tag)]))
        jobs.append(("%s_scan" % tag, PY + ["%s/ds28r01f/ds28r01f_scan.py" % T, "--package", pk, "--kstar", kdir, "--warp", WARP,
                                           "--out", "%s/%s/scan.json" % (root, tag), "--label", "試行F %s" % tag, "--workers", str(a.check_workers)]))
        jobs.append(("%s_p20_width" % tag, PY + ["%s/ds28r01f/ds28r01f_p20.py" % T, "--package", pk, "--workers", "6"]))
        # F_final で足した当て直し（ds_anchor_retarget・ds_far_hook_early）の P20（入れていない版のパッケージでは測らない）
        glog = os.path.join(REPO, pk, "ds28r01f_generate_log.json")
        fon = (json.load(open(glog, encoding="utf-8")).get("result") or {}).get("f_on", {}) if os.path.isfile(glog) else {}
        for nm in ("anchor_retarget", "far_hook_early"):
            if fon.get(nm):
                jobs.append(("%s_p20_%s" % (tag, nm), PY + ["%s/ds28r01f/ds28r01f_p20.py" % T, "--package", pk, "--workers", "3", "--name", nm]))
        if not a.skip_p20_e:
            # E から受け継いだ名前の付いた値の大きさ（P20）を、この K*′ で（試行E の ds28r01e_p20.py、E の生成器で切った版との差）
            os.makedirs(os.path.join(B, tag, "p20_e"), exist_ok=True)
            for nm in ("lean_with_height", "tower_peak_off", "curl_lead", "back_hold_water"):
                jobs.append(("%s_p20e_%s" % (tag, nm), PYL + ["%s/ds28r01e/ds28r01e_p20.py" % T, "--name", nm, "--kstar", kdir,
                                                            "--out", "%s/%s/p20_e/%s.json" % (root, tag, nm)]))
        bad = PD.run_parallel(jobs, logd)
        timing["checks_s"] = round(time.time() - t0, 1)
        if bad:
            print("検査の失敗：%s（ログ %s）" % (bad, logd), flush=True)
    t0 = time.time()
    PD.run_parallel([("table", PY + ["%s/ds28r01f/ds28r01f_table.py" % T, "--root", root])], logd)
    timing["table_s"] = round(time.time() - t0, 1)
    timing["total_s"] = round(time.time() - t_all, 1)
    os.makedirs(os.path.join(B, tag), exist_ok=True)
    with open(os.path.join(B, tag, "pipeline_timing.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(tag=tag, kstar=kdir, timing=timing, command="py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_pipeline.py " + " ".join(sys.argv[1:])),
                  f, ensure_ascii=False, indent=1)
    print("DONE %s %s" % (tag, timing), flush=True)


if __name__ == "__main__":
    main()
