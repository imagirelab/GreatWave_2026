# -*- coding: utf-8 -*-
"""仕上げ33 記録の部：群の最終の metrics.json・run.json と、提出の一覧 Unity/Build/Polish/33/commit_list.txt を書き、記録の部の確かめをする。

新しい描画・計算はしない。値は Docs/Evidence/Polish/33 の JSON（作る部・修正の回 1・修正の回 2 の記録）から取る。
確かめ：PNG が 1920×1080、MP4 と提出のファイルが 5 MB 以下、場面の guid の行き先、Python の読み込みの行き先（Git の追跡済みか提出の一覧の中）、
Unity のファイルとフォルダーの .meta、提出の一覧に Unity/Build がないこと、禁止の場所と個人のパスの文字列（この道具を除く）。

使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33r_record.py [--no-import-check]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/33"
EV = REPO + "/Docs/Evidence/Polish/33"
ME = "Tools/GWWaveGen/pl33/pl33r_record.py"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def git_tracked():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
    return set(x for x in out.split("\n") if x)


def commit_files():
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl33/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/pl33/*.ps1"))
    unity = [REPO + "/Unity/Assets/GreatWave/Polish33.meta"]
    for root, dirs, files in os.walk(REPO + "/Unity/Assets/GreatWave/Polish33"):
        dirs.sort()
        for f in sorted(files):
            unity.append(os.path.join(root, f))
    record = [REPO + "/Docs/Progress/Polish_33_ja.md"]
    ev = sorted(glob.glob(EV + "/*"))
    return [rel(p) for p in code + unity + record + ev]


def check_meta(files):
    s = set(files)
    missing = []
    for f in files:
        if f.startswith("Unity/Assets/") and not f.endswith(".meta"):
            if f + ".meta" not in s:
                missing.append(f + ".meta")
            d = os.path.dirname(f)
            while d.startswith("Unity/Assets/GreatWave/Polish33"):
                if d + ".meta" not in s:
                    missing.append(d + ".meta")
                d = os.path.dirname(d)
    return sorted(set(missing))


def check_guids(tracked, files):
    guid2meta = {}
    for m in glob.glob(REPO + "/Unity/Assets/**/*.meta", recursive=True):
        try:
            g = re.search(r"^guid: ([0-9a-f]{32})", open(m, encoding="utf-8", errors="ignore").read(), re.M)
        except OSError:
            continue
        if g:
            guid2meta.setdefault(g.group(1), []).append(rel(m))
    pkg = {}
    for m in glob.glob(REPO + "/Unity/Library/PackageCache/**/*.meta", recursive=True):
        try:
            g = re.search(r"^guid: ([0-9a-f]{32})", open(m, encoding="utf-8", errors="ignore").read(), re.M)
        except OSError:
            continue
        if g:
            pkg[g.group(1)] = os.path.relpath(m, REPO + "/Unity/Library/PackageCache").replace("\\", "/").split("/")[0]
    s = set(files)
    out = {}
    for sc in sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33/Scenes/*.unity")):
        res = {"tracked_meta": 0, "this_group_meta": [], "package": [], "builtin": 0, "missing": []}
        for g in sorted(set(re.findall(r"guid: ([0-9a-f]{32})", open(sc, encoding="utf-8", errors="ignore").read()))):
            if g.startswith("0000000000000000"):
                res["builtin"] += 1
            elif g in guid2meta:
                ms = guid2meta[g]
                if any(m in tracked for m in ms):
                    res["tracked_meta"] += 1
                elif any(m in s for m in ms):
                    res["this_group_meta"] += ms
                else:
                    res["missing"].append(g)
            elif g in pkg:
                res["package"].append(pkg[g])
            else:
                res["missing"].append(g)
        out[rel(sc)] = res
    return out


def check_imports(tracked, files, dynamic):
    """pl33 の道具が読み込むリポジトリの中の .py が、追跡済みか提出の一覧の中かを確かめる。"""
    s = set(files)
    loaded = set()
    fails = []
    if dynamic:
        for f in sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl33/*.py")):
            m = os.path.splitext(os.path.basename(f))[0]
            code = ("import sys,json;sys.path.insert(0,%r);import %s;"
                    "print(json.dumps(sorted(set(getattr(v,'__file__','') or '' for v in list(sys.modules.values())))))") % (REPO + "/Tools/GWWaveGen/pl33", m)
            r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=600, cwd=REPO + "/Tools/GWWaveGen/pl33")
            if r.returncode:
                fails.append(m)
                continue
            for p in json.loads(r.stdout.strip().splitlines()[-1]):
                p2 = os.path.normpath(p).replace("\\", "/")
                if p2.lower().startswith(REPO.lower() + "/"):
                    loaded.add(rel(p2))
    not_ok = sorted(p for p in loaded if p not in tracked and p not in s)
    return {"dynamic": dynamic, "modules_in_repo": sorted(loaded), "tracked": sorted(p for p in loaded if p in tracked),
            "in_commit_list": sorted(p for p in loaded if p in s and p not in tracked), "neither": not_ok, "import_failures": fails}


FORBID = [
    ("旧試作の場所 Ukeyoe", re.compile(r"Ukeyoe(?!_Claw[\\/]+Docs[\\/]+Research[\\/]+Claw_Analysis[\\/]+README\.md)")),
    ("旧試作の場所 bigwave", re.compile(r"bigwave", re.I)),
    ("旧 GreatWave_2026", re.compile(r"GreatWave_2026(?!_Fresh)")),
    ("参照モデルのフォルダーのほかのファイル", re.compile(r"research[\\/]+model[\\/]+(?!wave_repair_zbrush2\.obj)")),
    ("reality scan のほかのフォルダー", re.compile(r"reality scan[\\/]+(?!北斋参考)")),
    ("個人のパス", re.compile(r"wang6|zhuoran|C:[\\/]+Users[\\/]+(?!…)[A-Za-z0-9]", re.I)),
]


def check_strings(files):
    hits = []
    for f in files:
        if f == ME or os.path.splitext(f)[1].lower() not in (".py", ".ps1", ".cs", ".shader", ".unity", ".meta", ".md", ".json", ".txt"):
            continue
        txt = open(REPO + "/" + f, encoding="utf-8-sig", errors="ignore").read()
        for name, rx in FORBID:
            for m in rx.finditer(txt):
                hits.append({"file": f, "kind": name, "text": txt[max(0, m.start() - 20):m.end() + 20]})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-import-check", action="store_true")
    a = ap.parse_args()

    mb = jl(EV + "/metrics_build.json")
    m1 = jl(EV + "/metrics_fix01.json")
    m2 = jl(EV + "/metrics_fix02.json")
    ms = jl(EV + "/pl33f2_measure.json")
    ms1 = jl(EV + "/pl33f_measure.json")
    chk = jl(EV + "/pl33_checks.json")
    tips = jl(EV + "/pl33f_tips_seat.json")
    ridge = jl(EV + "/pl33f2_ridge_img.json")
    rb = jl(EV + "/release_build_fix02.json")
    rb32 = jl(REPO + "/Docs/Evidence/Polish/32/release_build_fix01.json")
    pmr = jl(EV + "/playmode_release_fix02.json")
    pms = jl(EV + "/playmode_single_fix02.json")
    pl = jl(EV + "/pl33_players_fix02.json")
    rr = jl(EV + "/render_report_fix02.json")
    bu = jl(EV + "/pl33_bumps_fix02.json")["items"]
    bun = jl(EV + "/pl33_bumps_after_noclaws.json")["items"]
    clip = jl(EV + "/pl33f2_clip_report.json")["summary"]
    perf = jl(EV + "/pl33_perf.json")
    rh = ms["painting_tstar_rhythm"]
    V = ms["views"]
    geo = ms["geometry"]
    rg = ms["closed_rings"]
    K3 = ("before", "build", "fix")

    def trio(d):
        return {"before_pl32": d["before"], "fix01": d["build"], "after_fix02": d["fix"]}

    views = {}
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"):
        for t in ("t105", "t120"):
            k = "%s_%s" % (v, t)
            if k in V:
                views[k] = {kk: {"claw_px": V[k][x]["claw_px"], "over_indigo_px": V[k][x]["over_indigo_px"], "line_on_light_px": V[k][x]["line_on_light_px"]}
                            for kk, x in (("before_pl32", "before"), ("fix01", "build"), ("after_fix02", "fix"))}
    eye = {
        "painting": "t 9 s：頂の上に冠の爪の芽は出ない。t 10.5 s：牙の束・空へ出る鉤・b区域の下の細片はない。t*：頂と唇の爪が白い指・墨版の線・水色の膜で縁取られる（前より線と水色が多い）。頂の輪郭そのものは滑らかな塊のまま。b区域は 2〜3 本の束",
        "seat": "t 10.5 s・t*：前とほぼ同じ。面に沿う低い帯で、角の四角い板・藍の上の白い三日月はない。3D の白い指としては読めない（限界）",
        "seat_toward_wave": "t 10.5 s：白いつららの縁に爪の線。水色の小石・破片はない。t*：前とほぼ同じ",
        "side_left": "ドームの左上の 1 か所に冠の爪の房の列が面を下る形で見える。上の縁の大半は滑らか。中ほどの平らな白は主役波の材質（仕上げ29・31）",
        "side_right": "t 9 s から頂が爪で縁取られ、t 10.5 s・t* で頭の上と背に鉤の房が並ぶ",
        "back65": "t 9 s に稜の上に芽の列。t 10.5 s・t* で稜の左の頂（b区域の裏）と右の肩に房。房の間の稜は滑らか。面の中ほどに米粒はない",
        "top": "頂の付近に房の指の塊（稜の全長ではない）",
        "turntable": "t 10.5 s・t*：0〜150°・300〜330° は頂が縁取られる。180〜270° は稜の頂の付近だけで、右の肩は縁取られない。動画で飛び出し・点滅なし",
    }
    rows = [
        {"row": 1, "user_words": True, "text_ja": "［利用者の言葉］Q16・Q21 の b区域の爪が原画視点で房として読めない、帯の幅",
         "source_ja": "段階9確認 #2・#8、段階6確認 F6-1・F6-2・F6-3、設計33 限界4、設計36 限界8",
         "before": rh["bregion_before"], "after": rh["bregion_fix"], "painting": rh["bregion_painting"], "verdict": "一部",
         "note_ja": "2 回の修正の回（［利用者の言葉］の上限）を使った。5〜10 本の房と藍の窓は主役波の形・材質（仕上げ28・29・31）。10/29 以降へ"},
        {"row": 2, "text_ja": "原画視点で 3D の爪がほとんど読めない／座席では細かく乱れて房として読みにくい", "source_ja": "段階6確認 F6-1、段階7確認 §6 の9・§9",
         "before": {"claw_zone_mizuiro": rh["claw_zone_before"]["mizuiro"], "seat_t120_claw_px": V["seat_t120"]["before"]["claw_px"]},
         "after": {"claw_zone_mizuiro": rh["claw_zone_fix"]["mizuiro"], "seat_t120_claw_px": V["seat_t120"]["fix"]["claw_px"]},
         "painting": {"claw_zone_mizuiro": rh["claw_zone_painting"]["mizuiro"]}, "verdict": "一部",
         "note_ja": "座席から 3D の白い指は読めない（限界）。作る部の「直した（0.419／90,219）」は取り消した"},
        {"row": 3, "text_ja": "焼き込みの爪の模様と 3D の爪の二重、頂の模様が埋まる", "source_ja": "設計36 §7 の限界4、設計38 §7、段階7確認 §9",
         "verdict": "該当なし", "note_ja": "仕上げ29 で焼き込みをやめた"},
        {"row": 4, "text_ja": "132・72 の細部込みの爪のこぶを 4 px へ", "source_ja": "段階6確認 §4.1・§8、設計33 限界5・§7",
         "after": {k: {kk: bu[k][kk] for kk in ("max_px", "p95_px", "render_points_gt4", "render_points")} for k in ("132", "72")},
         "noclaws": {k: {kk: bun[k][kk] for kk in ("max_px", "p95_px", "render_points_gt4", "render_points")} for k in ("132", "72")},
         "rim_fill_try_not_adopted": m1["must_fix"]["6_9_132_72_detail"]["rim_try"], "verdict": "満たさない（限界）"},
        {"row": 5, "text_ja": "帯の断面の向きを輪の間とコマの間で続ける", "source_ja": "段階6確認 §8、設計33 §7、設計34 §7",
         "before": {"frame_flips_gt90": geo["before"]["section_orientation"]["frame_flips_gt90"], "ring_twists_gt60": geo["before"]["section_orientation"]["ring_twists_gt60"]},
         "after": {"frame_flips_gt90": geo["fix"]["section_orientation"]["frame_flips_gt90"], "ring_twists_gt60": geo["fix"]["section_orientation"]["ring_twists_gt60"]}, "verdict": "直した"},
        {"row": 6, "text_ja": "中心線の急な折れの所の幅", "source_ja": "段階6確認 §8", "before": geo["before"]["bends_tstar"], "after": geo["fix"]["bends_tstar"],
         "verdict": "一部", "note_ja": "45° を超える折れは仕上げ32 の一覧の中心線の形"},
        {"row": 7, "text_ja": "シートに一部が隠れる爪・根元の白の円の角ばり・根元が藍濃の 2 本（C163・C165）・200 の根元の白", "source_ja": "段階6確認 §8、設計36 §7",
         "claws_visible_fraction_lt_0p8": chk["claws_partly_hidden_by_sheet_tstar"], "verdict": "一部",
         "note_ja": "C163・C165 は仕上げ32 から帯にしていない（根元の白い角 0）。根元の円の角ばりは変えていない。根元の円は仕上げ32 の決まりで水色の版"},
        {"row": 8, "text_ja": "成長の時刻、V3 の爪が画面の外で伸び始める", "source_ja": "段階6確認 §8、設計35 §7", "done_ja": m1["must_fix"]["7_row8_growth"],
         "verdict": "直した（原画視点。V3 の比べの版は作り直していない）"},
        {"row": 9, "text_ja": "先端がシートから浮く", "source_ja": "設計32 §7", "tips_seat": tips,
         "seat_t120_over_indigo_px": [V["seat_t120"][k]["over_indigo_px"] for k in K3], "verdict": "一部",
         "note_ja": "原画のカメラへの射線の向きの低い浮き彫り（t* で 0.02〜0.22 m、中央値 0.08 m）は意図した形。作る部の座席の浮いた三日月は消えた"},
        {"row": 10, "text_ja": "空へ出る爪が唇の輪郭に作る白い欠け", "source_ja": "設計38 §7、段階7確認 §6 の10", "values": ms["lip_outline_white_notches_tstar"],
         "verdict": "限界として記録", "note_ja": "小さな切れ目 2 か所は爪の縁の線が根元で開く所（線の群、仕上げ38）"},
        {"row": 11, "text_ja": "爪が重なる所の線の精度", "source_ja": "設計38 §7",
         "closed_rings_all": {k: {t: rg["%s_%s_all" % (k, t)]["rings"] for t in ("t090", "t105", "t120")} for k in K3}, "verdict": "一部",
         "note_ja": "作る部より減ったが前より多い。重なる原画の爪どうしの線は変えていない"},
        {"row": 12, "text_ja": "動画の描画を短くする", "source_ja": "設計33 §7", "render_seconds_total": round(rr.get("secondsTotal", 0), 1),
         "verdict": "直した", "note_ja": "設計33 は numpy で約 40 分"},
    ]
    pen = geo["fix"]["penetration"]
    backlog = {
        "99": {"value": chk["99_C095_side_thickness_over_front_width"], "verdict": "満たす"},
        "100": {"value_ja": "帯は閉じた筒。輪郭の細部込みは 132 %.4f・72 p95 %.4f px" % (bu["132"]["max_px"], bu["72"]["p95_px"]), "verdict": "一部"},
        "101": {"value_ja": "原画の爪の芽は面に付いた短い帯。冠の爪も芽から伸びる", "verdict": "記録"},
        "103_104": {"value_ja": "原画の爪の t* の輪の中心と先の投影は仕上げ32 と同じ（差 %.1f px）。仕上げ32 の先端の最大 0.54 px" % ms["C_tstar_centre_tip_projection_shift_px"]["fix"]["max"], "verdict": "満たす"},
        "105": {"value_ja": "原画の爪の根元は仕上げ32 とバイトまで同じ。冠の爪の根元とシートの頂点の差 最大 %.1f µm" % (ms["crown_fix"]["root_to_sheet_vertex_max_m"] * 1e6), "verdict": "満たす"},
        "129": {"value": {k: geo["fix"]["motion"][k]["teleports_gt0p5m"] for k in ("C", "W", "K", "S")}, "verdict": "満たす"},
        "136": {"value": {"crown_born_before_root_white": ms["crown_fix"]["born_before_root_white"]}, "verdict": "満たす"},
        "137": {"value_ja": "冠の爪の根元はシートの頂点そのもの", "verdict": "満たす"},
        "138": {"value_ja": "向きは根元の座標系で持ち、そのコマの面で作り直す", "verdict": "満たす（作りの上で）"},
        "139": {"value": {"counts": geo["fix"]["counts"], "motion": geo["fix"]["motion"]}, "verdict": "満たす"},
        "140_141": {"value": {k: {"claw_px": V["seat_t120"][k]["claw_px"], "floating_comps": V["seat_t120"][k]["floating_comps"]} for k in K3}, "verdict": "記録"},
        "180": {"value": tips, "verdict": "記録"},
        "200_207_208": {"value_ja": "爪の上面の白は主役波の白と同じ値（ΔE00 0）。根元の円・側面・下面は水色の版（仕上げ32 の決まり）", "verdict": "上面は満たす。ほかは記録"},
        "204": {"value": {"frame_flips_gt90": geo["fix"]["section_orientation"]["frame_flips_gt90"], "ring_twists_gt60": geo["fix"]["section_orientation"]["ring_twists_gt60"],
                          "frames_width_outside_first_last_range": chk["204_frames_width_outside_first_last_range"]}, "verdict": "満たす"},
        "205_206": {"value": {"web_rings_below_5cm_t090_t105_t120": [pen["W_t090"]["rings_below_5cm"], pen["W_t105"]["rings_below_5cm"], pen["W_t120"]["rings_below_5cm"]]},
                    "verdict": "一部（面の下の膜の輪は 206 の違反として記録）"},
        "238": {"value_ja": "根元の線は仕上げ32 のとおり開き、膜には線を出さない", "verdict": "満たす"},
        "262": {"value": {k: [pen["%s_%s" % (k, t)]["rings_below_5cm"] for t in ("t090", "t105", "t120")] for k in ("C", "W", "K", "S")},
                "deepest_m": {k: pen["%s_t120" % k]["deepest_m"] for k in ("C", "W")}, "verdict": "満たさない（一部。前より少ない）"},
    }
    g = m2["gates_painting_view"]
    met = {
        "schema": "GreatWave.Polish33.metrics/1",
        "number": {"group": "仕上げ33", "design": "設計33 爪の造形", "backlog": "99〜101、103〜105、129、136〜141、180、200、204〜208、238、262", "time_box_days": 1.5,
                   "plan": "Docs/Design/Stage9_Plan_2026-09-26_ja.md §5.1・§5.2・§5.3 仕上げ33・§2.6"},
        "before_ja": "仕上げ32（ede11c8、修正の回 1 の状態）。描画 Unity/Build/Polish/32/fix01/r_fix01",
        "after_ja": "仕上げ33 修正の回 2（採用）。爪の並び Unity/Build/Polish/33/fix02/claws、描画 Unity/Build/Polish/33/fix02/r_fix02",
        "evidence_kind_ja": "Unity 6000.4.3f1 の PC オフスクリーン描画、Editor の Play モード、Release のプレイヤーを PC で動かした結果、numpy・OpenCV・scipy の計算。HMD 実機ではない。利用者は見ていない",
        "user_words": {
            "Q16_Q21_bregion": {"plan_row": 1, "values": {"painting": rh["bregion_painting"], "before_pl32": rh["bregion_before"], "fix01": rh["bregion_build"], "after_fix02": rh["bregion_fix"],
                                                           "build_r_after": ms1["painting_tstar_rhythm"]["bregion_build"]},
                                "closed_rings_t105_t120": {"before_pl32": [rg["before_t105_bregion"]["rings"], rg["before_t120_bregion"]["rings"]],
                                                           "after_fix02": [rg["fix_t105_bregion"]["rings"], rg["fix_t120_bregion"]["rings"]]},
                                "fix_rounds_used": 2, "verdict": "一部", "verdict_ja": "2〜3 本の指の束として読めるが、5〜10 本の房と藍の窓・水色の量には届かない。2 回の修正の回を使ったので 10/29 以降へ"},
            "Q28_3d_claws_every_view": {"source_ja": "制作手順 Q28、計画 §5.1 の審査の決まり", "projection_colour_used": False,
                                        "ridge_top_edge_fraction_img": {k: ridge[k] for k in ridge}, "ridge_ringed_fraction_tstar": ms["ridge_ringed_fraction_tstar"],
                                        "verdict": "一部", "verdict_ja": "側面・後ろ・真上・回り台で頂の房の列として読める。稜は房ごと、左の側面は 1 か所、座席からは 3D の白い指として読めない（限界）"},
        },
        "plan_5_3": rows,
        "plan_5_3_counts": {"直した": 3, "一部": 6, "満たさない（限界）": 1, "限界として記録": 1, "該当なし": 1},
        "backlog": backlog,
        "gates_painting_view": {"after_fix02": g, "fix01": m2["gates_fix01"], "before_pl32": m2["gates_before"], "cp1_26r01_reference": m2["cp1_26r01_reference"],
                                "verdict_ja": "形の関門 78・130・131・132 σ12・72 σ12 は爪あり・爪なしとも仕上げ32 と同じ値（後退なし）。評価器 23 の合否の数も 4 組とも同じ。CP1／26修正01 に対しては段階5確認 §6.3 以来の後退のまま"},
        "q28_views": {"claw_px_etc": views, "by_eye_ja": eye, "ridge_top_edge_fraction_img": ridge,
                      "painting_outside_hero_px": {t: {kk: ms["painting_outside_hero"][t][x]["claw_px_outside_hero"] for kk, x in (("before_pl32", "before"), ("fix01", "build"), ("after_fix02", "fix"))}
                                                   for t in ms["painting_outside_hero"]},
                      "sliver_over_indigo": m2["must_fix"]["1_bregion_sliver_into_indigo"],
                      "verdict_ja": "この群の範囲に、引き伸ばし・継ぎ目・溶けた爪・浮いた板・藍へ垂れる細片は見えない。平らな白は左の側面・後ろ 65° のドームの中ほど（主役波の材質と白の範囲）"},
        "painting_rhythm_tstar": {k: rh[k] for k in ("claw_zone_painting", "claw_zone_before", "claw_zone_build", "claw_zone_fix")},
        "geometry_after": geo["fix"],
        "clip_fix02": clip,
        "unity": {"playmode": {"release": {"end": pmr.get("end"), "sawApplied": pmr.get("sawApplied")}, "single": {"end": pms.get("end"), "sawApplied": pms.get("sawApplied")}},
                  "release_build": {"result": rb.get("buildResult"), "data_files": rb.get("dataFiles"), "build_errors": rb.get("buildErrorCount"),
                                    "data_bytes": rb.get("dataBytes"), "data_bytes_pl32": rb32.get("dataBytes"), "absolute_paths_left": rb.get("absolutePathsLeft"),
                                    "must_have_present": rb.get("mustHavePresent"), "bake_files_absent": rb.get("bakeFilesAbsent"), "exe_sha256": rb.get("exeSha256")},
                  "players_fix02": pl, "players_pl32_same_day": {"frames": [perf["pl32_1"]["frames"], perf["pl32_2"]["frames"]], "file": "pl33_perf.json（作る部と交互に動かした）"},
                  "perf_build_pairs": {k: {"frames": v.get("frames"), "Formation": v.get("Formation")} for k, v in perf.items()},
                  "claw_layer": {"entries": sum(geo["fix"]["counts"].values()), "counts": geo["fix"]["counts"], "vertices": 95547, "triangles": 183240},
                  "hmd": "未検証"},
        "limits_ja": [
            "座席・座席から波の方向から 3D の白い指は読めない（座席 t* の爪の画素 %d、前 %d）。原画視点の律動も一部（水色 %.3f、原画 %.3f）" % (
                V["seat_t120"]["fix"]["claw_px"], V["seat_t120"]["before"]["claw_px"], rh["claw_zone_fix"]["mizuiro"], rh["claw_zone_painting"]["mizuiro"]),
            "［利用者の言葉］Q16・Q21 の b区域の房は一部（2 回の修正の回の後。線の成分 %d、水色 %.3f）" % (rh["bregion_fix"]["components"], rh["bregion_fix"]["mizuiro"]),
            "132・72 の細部込みは 4 px に届かない（132 %.4f、72 p95 %.4f）" % (bu["132"]["max_px"], bu["72"]["p95_px"]),
            "稜の縁取りは房ごと（後ろ 65° %.2f、回り台 210° %.2f）。左の側面は 1 か所。右の肩は原画の輪郭そのもので冠の爪を置けない" % (
                ms["ridge_ringed_fraction_tstar"]["back65"]["fix"], ms["ridge_ringed_fraction_tstar"]["tt210"]["fix"]),
            "45° を超える中心線の折れ %d 本、縁の折れ返り %d 本" % (geo["fix"]["bends_tstar"]["claws_bend_gt45"], geo["fix"]["bends_tstar"]["claws_edge_foldback"]),
            "面に入る輪：t* で原画の爪 %d・膜 %d 輪" % (pen["C_t120"]["rings_below_5cm"], pen["W_t120"]["rings_below_5cm"]),
            "閉じた輪：原画視点 t* %d・t 10.5 s %d（前 %d・%d）" % (rg["fix_t120_all"]["rings"], rg["fix_t105_all"]["rings"], rg["before_t120_all"]["rings"], rg["before_t105_all"]["rings"]),
            "唇の輪郭の小さな切れ目 2 か所（線の群）",
            "冠の爪は原画にない立体の爪（進行役の解釈）。ドームの中ほどの平らな白は主役波の材質と白の範囲",
            "pl33f2_white_clip の検査の画像は爪なしの原画視点の描画から作る。主役波の材質・海・飛沫を変えたらやり直す",
            "鉤の内の膜は板に見えうる（206）",
            "根元の円の角ばり、200・207・208 の根元・側面・下面の白は仕上げ32 の決まりのまま。V3 の比べの版の成長の時刻は作り直していない",
            "重さ：データ %.2f GB（仕上げ32 %.2f GB）、プレイヤーのフレームは約 1〜3%% 少ない。90 Hz の判定は仕上げ35" % (rb["dataBytes"] / 1e9, rb32["dataBytes"] / 1e9),
            "HMD は未検証",
        ],
    }

    files = commit_files()
    tracked = git_tracked()
    pngs = {f: list(png_size(REPO + "/" + f)) for f in files if f.lower().endswith(".png")}
    mp4s = {f: os.path.getsize(REPO + "/" + f) for f in files if f.lower().endswith(".mp4")}
    big = {f: os.path.getsize(REPO + "/" + f) for f in files if os.path.getsize(REPO + "/" + f) > 5 * 1000 * 1000}
    rp = {
        "files_in_commit_list": len(files),
        "missing_files": [f for f in files if not os.path.exists(REPO + "/" + f)],
        "unity_build_in_list": [f for f in files if f.startswith("Unity/Build/")],
        "already_tracked_in_list": sorted(f for f in files if f in tracked),
        "png_not_1920x1080": {f: s for f, s in pngs.items() if s != [1920, 1080]},
        "png_count": len(pngs),
        "mp4_bytes": mp4s,
        "files_over_5MB": big,
        "unity_meta_missing": check_meta(files),
        "scene_guids": check_guids(tracked, files),
        "python_imports": check_imports(tracked, files, not a.no_import_check),
        "forbidden_or_personal_strings": check_strings(files),
        "excluded_from_string_check": ME,
    }
    met["record_phase"] = rp
    json.dump(met, open(EV + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    adopted = [B + "/fix02/claws/ds33_claw_layout.json", B + "/fix02/claws/ds33_claw_frames_f32.bin", B + "/fix02/claws/ds33_claw_tris_i32.bin",
               B + "/fix02/claws/ds33_claw_tri_attr_u16.bin", B + "/fix02/claws/pl33f2_web_scale.npy", B + "/fix02/claws/pl33f2_tuft_scale.npy",
               B + "/fix01/claws/ds33_claw_layout.json", B + "/fix01/claws/ds33_claw_frames_f32.bin", B + "/release/player/GreatWave50.exe"]
    inputs = [B + "/../32/fix01/claws/ds33_claw_frames_f32.bin", B + "/../32/fix01/claws/ds33_claw_layout.json", B + "/../32/white/hero_pkg/ds27_keypose.json",
              B + "/../32/white/hero_pkg/ds27_twhite_r32f.bin", B + "/../32/white/pl31_zone_vertex.npy", B + "/../28/G_p28rec/timewarp_G_p28rec.json",
              B + "/../32/fix01/list/ds32_claw_inventory.json"]
    arch = {}
    for d in ("archive_build", "archive_fix01", "archive_fix02"):
        p = B + "/record/" + d + "/archive_index.json"
        if os.path.exists(p):
            arch["Unity/Build/Polish/33/record/" + d] = sha(p)
    run = {
        "schema": "GreatWave.Polish33.run/1",
        "note_ja": "仕上げ33 の群の最終。作る部・修正の回 1・修正の回 2 のコマンドの全文は run_build.json・run_fix01.json・run_fix02.json。記録の部は新しい描画・計算をしていない。",
        "commands_record_ja": ["py -3.10 -B Tools/GWWaveGen/pl33/pl33r_record.py（metrics.json・run.json・Unity/Build/Polish/33/commit_list.txt と記録の部の確かめ）"],
        "commands_adopted_chain": [c for c in jl(EV + "/run_fix01.json")["commands"][:3]] + [c for c in jl(EV + "/run_fix02.json")["commands"]],
        "record_phase_changes_ja": ["Docs/Progress/Polish_33_ja.md を 1 つの記録にまとめた（前の版は Unity/Build/Polish/33/record/archive_fix02/Polish_33_ja_fix02.md）",
                                    "作る部の metrics.json・run.json を metrics_build.json・run_build.json に名前を替えた（中身はバイトまで同じ）",
                                    "pl33_record.py の出力の名前と、pl33f2_record.py が読み替えを書き足す先を metrics_build.json・run_build.json に替えた（替える前の写しは archive_fix02）",
                                    "pl33r_record.py を加えた"],
        "tools": {"unity": "6000.4.3f1", "python": "py -3.10（numpy・OpenCV・scipy・PIL）", "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe",
                  "houdini": "使っていない", "blender": "使っていない"},
        "inputs_sha256": {rel(os.path.normpath(p)): sha(p) for p in inputs if os.path.exists(p)},
        "adopted_outputs_sha256": {rel(p): sha(p) for p in adopted if os.path.exists(p)},
        "archives_index_sha256": arch,
        "commit_list_sha256": {f: sha(REPO + "/" + f) for f in files if f != "Docs/Evidence/Polish/33/run.json" and os.path.exists(REPO + "/" + f)},
        "reference_reads_ja": "作る部で、利用者の指示 Q16 の例外の写真のフォルダー G:/research/reality scan/北斋参考 の 3 枚（正面图.jpg・左45.jpg・背图.jpg）を画面で見ただけ。"
                              "画像・寸法・形・Exif はリポジトリと成果物に入れていない。修正の回 1・2 と記録の部では開いていない。参照モデルの OBJ、利用者の爪形分析、G:/research/Wave Simulation は開いていない。",
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
    }
    json.dump(run, open(EV + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(B + "/commit_list.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(files) + "\n")
    bad = (rp["missing_files"] or rp["unity_build_in_list"] or rp["png_not_1920x1080"] or rp["files_over_5MB"] or rp["unity_meta_missing"]
           or any(v["missing"] for v in rp["scene_guids"].values()) or rp["python_imports"]["neither"] or rp["python_imports"]["import_failures"]
           or rp["forbidden_or_personal_strings"])
    print("PL33R_RECORD_DONE files=%d png=%d mp4=%d problems=%s" % (len(files), len(pngs), len(mp4s), "YES" if bad else "none"))
    if bad:
        print(json.dumps({k: rp[k] for k in rp if k not in ("python_imports", "scene_guids", "mp4_bytes")}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
