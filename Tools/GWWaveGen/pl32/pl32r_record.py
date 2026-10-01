# -*- coding: utf-8 -*-
"""仕上げ32 記録の部：群の最終の metrics.json・run.json と、提出の一覧 commit_list.txt を書き、記録の部の確かめをする。

新しい計算・描画はしない。数は作る部の metrics_build.json、修正の回 1・2 の metrics_fix01.json と、
Docs/Evidence/Polish/32 の数の JSON から読み直す（どれも Git 対象外の出力から作られたもの）。
確かめ：証拠の PNG がどれも 1920×1080、MP4 が 5 MB 以下、PL32 の場面と材質の guid の行き先、
提出の一覧の全部のファイルがあり Unity/Build を含まないこと、禁止の場所・個人のパスの文字列、
採用のデータの SHA-256 が修正の回 1 の run_fix01.json と同じこと。
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32r_record.py
"""
import glob
import hashlib
import json
import os
import re
import subprocess

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/32"
E = REPO + "/Docs/Evidence/Polish/32"
P32 = REPO + "/Unity/Assets/GreatWave/Polish32"
RECORD = REPO + "/Docs/Progress/Polish_32_ja.md"
COMMIT_LIST = B + "/commit_list.txt"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


# ---------------------------------------------------------------- 提出の一覧
def commit_files():
    tools = sorted(p for p in glob.glob(REPO + "/Tools/GWWaveGen/pl32/*") if os.path.isfile(p)
                   and os.path.splitext(p)[1] in (".py", ".ps1", ".json", ".txt"))
    unity = [REPO + "/Unity/Assets/GreatWave/Polish32.meta"]
    for root, dirs, files in os.walk(P32):
        dirs.sort()
        for f in sorted(files):
            unity.append(os.path.join(root, f))
    docs = [RECORD] + sorted(p for p in glob.glob(E + "/*") if os.path.isfile(p))
    return [rel(p) for p in tools + sorted(unity) + docs]


def check_commit_list(files):
    out = {"files": len(files), "missing": [], "under_build": [], "meta_missing": [], "untracked_outside_list": []}
    for f in files:
        if not os.path.exists(REPO + "/" + f):
            out["missing"].append(f)
        if f.startswith("Unity/Build/"):
            out["under_build"].append(f)
        if f.startswith("Unity/Assets/") and not f.endswith(".meta") and f + ".meta" not in files:
            out["meta_missing"].append(f)
    # Polish32 の下のフォルダーの .meta
    for root, dirs, _ in os.walk(P32):
        for d in dirs:
            m = rel(os.path.join(root, d)) + ".meta"
            if m not in files:
                out["meta_missing"].append(m)
    # この群の場所で、一覧にない未追跡のファイル（__pycache__ は .gitignore）
    st = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=all", "--",
                         "Tools/GWWaveGen/pl32", "Unity/Assets/GreatWave/Polish32", "Unity/Assets/GreatWave/Polish32.meta",
                         "Docs/Evidence/Polish/32", "Docs/Progress"], capture_output=True, text=True, encoding="utf-8").stdout
    for ln in st.splitlines():
        p = ln[3:].strip().strip('"')
        if p and p not in files and not p.startswith("Docs/Progress/README"):
            out["untracked_outside_list"].append(ln)
    out["pass_"] = not (out["missing"] or out["under_build"] or out["meta_missing"])
    return out


# ---------------------------------------------------------------- 場面の guid
BUILTIN = {"0000000000000000e000000000000000": "組み込み（unity default resources）",
           "0000000000000000f000000000000000": "組み込み（unity_builtin_extra）",
           "0000000000000000d000000000000000": "組み込み（unity editor resources）"}


def meta_guids(base):
    out = {}
    for root, dirs, files in os.walk(base):
        for f in files:
            if not f.endswith(".meta"):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    for _ in range(4):
                        ln = fh.readline()
                        if ln.startswith("guid:"):
                            out.setdefault(ln.split(":", 1)[1].strip(), rel(p[:-5]))
                            break
            except OSError:
                pass
    return out


def guid_check(files):
    srcs = [P32 + "/Scenes/PL32_Release.unity", P32 + "/Scenes/PL32_SinglePlayback.unity", P32 + "/Materials/PL32_Claw_Shade.mat"]
    refs = {}
    for s in srcs:
        for g in re.findall(r"guid: ([0-9a-f]{32})", open(s, encoding="utf-8", errors="replace").read()):
            refs.setdefault(g, set()).add(os.path.basename(s))
    tracked = set(subprocess.run(["git", "-C", REPO, "ls-files", "Unity/Assets"], capture_output=True, text=True,
                                 encoding="utf-8").stdout.split("\n"))
    assets = meta_guids(REPO + "/Unity/Assets")
    pk = {}
    for base in (REPO + "/Unity/Library/PackageCache", REPO + "/Unity/Packages"):
        if os.path.isdir(base):
            pk.update(meta_guids(base))
    fs = set(files)
    cls = {"tracked_meta": [], "this_group_meta": [], "package": [], "builtin": [], "untracked_not_listed": [], "unresolved": []}
    for g in sorted(refs):
        if g in BUILTIN:
            cls["builtin"].append([g, BUILTIN[g]])
        elif g in assets:
            a = assets[g]
            if a + ".meta" in tracked:
                cls["tracked_meta"].append([g, a])
            elif a + ".meta" in fs:
                cls["this_group_meta"].append([g, a])
            else:
                cls["untracked_not_listed"].append([g, a])
        elif g in pk:
            cls["package"].append([g, pk[g]])
        else:
            cls["unresolved"].append([g, sorted(refs[g])])
    summ = {k: len(v) for k, v in cls.items()}
    return {"sources": [rel(s) for s in srcs], "guids": len(refs), "counts": summ,
            "this_group_meta": cls["this_group_meta"], "package": cls["package"], "builtin": cls["builtin"],
            "untracked_not_listed": cls["untracked_not_listed"], "unresolved": cls["unresolved"],
            "pass_": not (cls["untracked_not_listed"] or cls["unresolved"])}


# ---------------------------------------------------------------- 文字列の検査
FORBID = [("旧試作 bigwave", r"Unity[/\\]+bigwave"), ("旧 GreatWave_2026", r"GreatWave_2026(?!_Fresh)"),
          ("Ukeyoe（README の例外の 1 ファイルを除く）", r"Unity[/\\]+Ukeyoe(?!_Claw[/\\]+Docs[/\\]+Research[/\\]+Claw_Analysis[/\\]+README\.md)"),
          ("research/model（例外の OBJ を除く）", r"research[/\\]+model(?![/\\]+wave_repair_zbrush2\.obj)"),
          ("reality scan（北斋参考を除く）", r"reality scan(?![/\\]+北斋参考)"),
          ("個人のパス C:/Users", r"[Cc]:[/\\]+Users[/\\]+")]
TEXT_EXT = (".md", ".json", ".py", ".ps1", ".txt", ".cs", ".shader", ".unity", ".mat", ".meta")


def string_check(files):
    hits = []
    for f in files:
        # この道具は検査の式そのものを持つので数えない。この道具が書く metrics.json・run.json は、書く前の中身を main で別に調べる
        if not f.endswith(TEXT_EXT) or f.endswith("/pl32r_record.py") or f in ("Docs/Evidence/Polish/32/metrics.json", "Docs/Evidence/Polish/32/run.json"):
            continue
        s = open(REPO + "/" + f, encoding="utf-8", errors="replace").read()
        for name, pat in FORBID:
            for m in re.finditer(pat, s):
                a = max(0, m.start() - 50)
                hits.append({"file": f, "kind": name, "context": s[a:m.end() + 50].replace("\n", " ")})
    return hits


def text_hits(s):
    """文字列 s の中の禁止の場所・個人のパスの文字列の数。"""
    return sum(len(re.findall(pat, s)) for _, pat in FORBID)


# ---------------------------------------------------------------- 証拠の大きさ
def media_check():
    from PIL import Image
    pngs, bad = [], []
    for p in sorted(glob.glob(E + "/*.png")):
        w, h = Image.open(p).size
        pngs.append([os.path.basename(p), w, h])
        if (w, h) != (1920, 1080):
            bad.append(os.path.basename(p))
    mp4 = [[os.path.basename(p), os.path.getsize(p)] for p in sorted(glob.glob(E + "/*.mp4"))]
    return {"png": len(pngs), "png_not_1920x1080": bad, "mp4": mp4, "mp4_max_bytes": max(s for _, s in mp4),
            "mp4_over_5MB": [n for n, s in mp4 if s > 5 * 1024 * 1024], "pass_": not bad and all(s <= 5 * 1024 * 1024 for _, s in mp4)}


def sheets_same_tiles():
    """記録の部で見出しだけ描き直した前後の図が、修正の回 1 の図と絵の所（y 62〜880）で画素まで同じか。"""
    import numpy as np
    from PIL import Image
    A = B + "/record/archive/evidence_media_fix01"
    out = []
    for p in sorted(glob.glob(E + "/fig_pl32_ba_*.png")):
        q = A + "/" + os.path.basename(p)
        if not os.path.exists(q):
            continue
        a = np.asarray(Image.open(q).convert("RGB"))
        b = np.asarray(Image.open(p).convert("RGB"))
        out.append([os.path.basename(p), int(np.any(a[62:880] != b[62:880], axis=2).sum())])
    return {"sheets": len(out), "tile_diff_px": out, "pass_": all(d == 0 for _, d in out)}


def data_same_as_fix01():
    rf = J(E + "/run_fix01.json")
    out, bad = 0, []
    for k, v in rf["data_sha256"].items():
        p = REPO + "/" + k if not os.path.isabs(k) else k
        if os.path.exists(p):
            out += 1
            if sha(p) != v:
                bad.append(k)
        else:
            bad.append(k + "（ない）")
    return {"checked": out, "changed_or_missing": bad, "pass_": not bad}


# ---------------------------------------------------------------- metrics
def build_metrics(chk):
    mb = J(E + "/metrics_build.json")
    mf = J(E + "/metrics_fix01.json")
    mfx = mf["must_fix"]
    g = mf["painting_gates"]
    tb = mfx["4_bregion_tufts_user_words"]
    m95 = mfx["5_6_C095_95_97"]
    reps = mfx["7_reps_123_126"]
    out13 = mfx["13_outline_144_145_261"]
    rows_f = out13["rows"]["fix01"]
    iou_f = mf["list"]["iou"]
    iou_b = mb["plan_rows"]["1_print_study_base_colour_iou"]["iou"]
    plan_rows = {
        "1 ［利用者の言葉］Q8 摺りの工程の調べ → 爪の基礎色と IoU（D25）": dict(
            source_ja="計画 §5.3 仕上げ32 の 1 行目（第0.3節、元の行、設計32 §7）",
            result_ja="大英博物館の Korenberg の論文（111 枚の刷りの比較）・Heritage Science の Vermeulen ほか（2020）の要旨・百科事典の二次の出典を読んだ。"
                      "白の版はなく、爪の白は摺らない紙の地、陰は水色の版、形は墨版（藍を多く含む青）の線。原画の爪の領域の画素は紙の地 73.8%・水色の版 24.5%・墨版の線の縁 1.7%・藍中 0.0%・藍濃 0.0%。"
                      "基礎色を紙の地の白、陰を水色の版 (203, 215, 206) にし、仕上げ29 の下面の藍中の段をやめた（PL32_Claw_Shade.mat）。D25＝墨版の線で区切った紙の地と水色の版の画素",
            claw_pixels_by_print_layer=mb["plan_rows"]["1_print_study_base_colour_iou"]["claw_pixels_by_print_layer"],
            iou={"rule_ja": iou_f["rule_ja"], "final": iou_f["pl32"], "build": iou_b.get("pl32"), "ds32_same_truth": iou_f["ds32_same_truth"]},
            verdict="満たす（調べと決め直し。読み方と決定は進行役、利用者は未確認。Vermeulen の本文と The Met の解説は読めていない）"),
        "2 ［利用者の言葉］Q16・Q21 b区域の浪尖の爪が原画視点で房として読めない": dict(
            source_ja="計画 §5.3 仕上げ32 の 2 行目（段階9確認 #2・#8、段階6確認 F6-3）",
            result_ja="b区域の爪を原画から数え直して 63 本を加え（一覧の b区域 77 本）、根元が立体の材質の白の範囲に乗る 57 本を帯にした。縁の線を根元で開き、付け根に水色の版の雲を付け、帯の幅を領域へ合わせた。"
                      "藍の窓（房と房の間の藍）と 3 つの房の形は主役波の形と材質（仕上げ28・29 の限界）で、この群では変えていない",
            dark_line_components={"painting": tb["lines"]["painting"]["components"], "before_pl31": tb["lines"]["before"]["components"],
                                  "build": tb["lines"]["build"]["components"], "final": tb["lines"]["fix01"]["components"]},
            dark_line_px={"painting": tb["lines"]["painting"]["dark_line_px"], "before_pl31": tb["lines"]["before"]["dark_line_px"],
                          "build": tb["lines"]["build"]["dark_line_px"], "final": tb["lines"]["fix01"]["dark_line_px"]},
            mizuiro_on_white={"painting": tb["mizuiro"]["painting"], "before_pl31": tb["mizuiro"]["before"], "build": tb["mizuiro"]["build"], "final": tb["mizuiro"]["fix01"]},
            closed_rings=mfx["3_rice_grains_t105"]["closed_rings"],
            bregion_claws={"list": 77, "banded_final": tb["bregion_claws_built"], "before_pl31": 15},
            verdict="一部（爪は根元が泡の胴へ開いた鉤と水色の雲で読めるが、原画の房（藍の窓で区切られ、5〜10 本の指が同じ向きに巻く）としては読めない。"
                    "作る部の判定「満たす」は修正の回 1 で取り下げた。［利用者の言葉］の 2 回目の作り直しは行っていない。爪の帯の読みやすさは仕上げ33、藍の窓と房の形は 10/29 の後の一覧へ）"),
        "3 仕上げ28 の形でシートへの結び付けと履歴を作り直す（ds32_ids → ds33_claw_rig → ds33_claw_anim → 設計34 の描画）": dict(
            source_ja="計画 §5.3 仕上げ32 の 3 行目（段階6確認 §8 の仕上げ28、設計32 §7）",
            ids=mf["claws"]["ids"], banded=mf["claws"]["built"], dropped_white_root=mf["claws"]["dropped_white_root"],
            item105_max_m=mf["claws"]["item105_max_m"], item137_max_m=mf["claws"]["item137_max_m"], item139_pass=mf["claws"]["item139_pass"],
            band_teleport={"build": mfx["10_motion"]["teleport"]["build"], "final": mfx["10_motion"]["teleport"]["fix01"]},
            rel_move_max_m={"before_pl31": mfx["10_motion"]["judge_motion"]["prev_design33_pl31"]["rel_move_max_m"],
                            "build": mfx["10_motion"]["judge_motion"]["build"]["rel_move_max_m"], "final": mfx["10_motion"]["judge_motion"]["fix01"]["rel_move_max_m"]},
            growth_jumps={"build": mfx["10_motion"]["judge_motion"]["build"]["growth_jump_count"], "final": mfx["10_motion"]["judge_motion"]["fix01"]["growth_jump_count"]},
            depth=mf["claws"]["depth"], b136=mf["claws"]["b136"], b136_zone_rooted=mf["claws"]["b136_zone_rooted"], b102=mf["claws"]["b102"],
            over_indigo_seat=mfx["1_seat_claws_left_edge"]["over_indigo_seat_spot"], over_indigo_stw=mfx["2_stw_upper_left"]["over_indigo_stw_spot"],
            verdict="満たす（223 本の ID で瞬間移動・点滅・129 が 0、帯の瞬間移動 0・成長の跳び 0、105 1.3 µm・137 2.0 µm・139 合格。作る部で座席・座席から波の方向に出た藍の上の白い棒は修正の回 1 で消えた）"),
        "4 ③ 爪ごとに領域の多角形と中心線を原画の輪郭線へ合わせる（帯の幅 F6-2 は仕上げ33）": dict(
            source_ja="計画 §5.3 仕上げ32 の 4 行目（段階6確認 F6-2・§8、設計33 §7）",
            region_rule_ja="測地の競り合い（中心線を種に、紙の地と水色の版の画素を、指の白の半幅の 2.2 倍まで広がる。爪どうしは画素を分け合わない）。中心線は領域の真ん中の最短路に結び直した（209 本、ずれの中央値 1.6 px・最大 7.4 px）",
            outline_le4={"final": [out13["fix01"]["le4"], out13["fix01"]["claws"]], "build": [out13["build"]["le4"], out13["build"]["claws"]], "before_pl31": [51, 148]},
            width_ratio_p50_final={k: v["width_ratio_p50"] for k, v in rows_f.items()},
            verdict="満たす（使える水準。帯の投影の幅を領域へ合わせた pl32f_width_fit は計画では仕上げ33 の行だが、審査の 95・123〜126 の指摘に要るので投影の幅だけこの群で行った。断面・折れ・こぶは仕上げ33）"),
        "5 領域の重なり 40 組・とげ・他の爪の領域の中の根元 15": dict(
            source_ja="計画 §5.3 仕上げ32 の 5 行目（設計32 §7、段階6確認 §8）",
            overlap_pairs_over5={"ds32": 40, "final": mf["list"]["overlap_pairs_over5"], "independent": mf["independent"]["overlap"]["pairs_over_5px"]},
            roots_inside_other={"ds32": 15, "final_builder": len(mf["list"]["roots_inside_other"]), "independent": mf["independent"]["roots_inside_other"]},
            spikes_removed_px=mb["plan_rows"]["4_fit_regions_centerlines"]["spikes_removed_px"],
            verdict="満たす（重なり 40 → 0、とげ 1,334 画素を落とした。他の爪の領域の中の根元は 15 → 作り手の検査 0・独立の検査 1：C235 の根元が修正の回 1 で加えた利用者の爪 C245（帯にしない）の領域の中。帯どうしの重なりではない）"),
        "6 C066・C112・C113・C109、根元の先で指が続く疑い、上側の列の根元（口の規則）": dict(
            source_ja="計画 §5.3 仕上げ32 の 6 行目（段階6確認 §8）",
            named=mb["plan_rows"]["5_named_short_claws"]["lengths"],
            upper_mouth_rule={"applied": mb["plan_rows"]["6_upper_row_mouth"]["changed"], "excluded": ["C042"], "eye_checked": 15},
            root_continuation={"ds32": 8, "build": len(mfx["8_root_continuation"]["build"]), "final": len(mfx["8_root_continuation"]["final"]),
                               "final_ids": sorted(mfx["8_root_continuation"]["final"]), "extended": 13},
            verdict="満たす・決めた（C066・C113・C109 は長さを保つ、C112 は消す、C174 は C002 に統合。上側 47 本に口の規則（C042 は当てない）。根元の先の疑い 8 → 作る部 18 → 11：13 本を溝に沿って延ばし、残る 11 本は目で見て判定）"),
        "7 利用者の 100 本の位置合わせ、対応なし 29 本（範囲の外の 9・手前の波の 11）、C174 と C002": dict(
            source_ja="計画 §5.3 仕上げ32 の 7 行目（段階6確認 §8、設計32 §7）",
            summary_ja=mfx["9_user100_branch"]["verdict"],
            list_counts=mf["list"]["counts"],
            verdict="決めた（位置合わせが不確か 7 → 4。加えた 15：主浪の左下 4（根元が立体の材質の藍の所なので帯にしない）・手前の波 11（一覧だけ。手前の波に爪の層がない）、"
                    "まとめた 3、既存の爪に対応 7、加えない 6。C174 は C002 に統合）"),
        "8 支の判定の規則（T3 0 本）、代表の形、船側中央の爪と代表10形（D8 第一候補 C095）": dict(
            source_ja="計画 §5.3 仕上げ32 の 8 行目（設計33 §7、段階6確認 §8、第7.2節 D8）",
            branch_rule_ja="利用者の爪形分析の README §4.2（支は主爪の第 2 の折れ点から出る）に合わせ、支の根元が主爪の中心線の 35〜97% の所で、主爪の幅 × 0.6 ＋ 10 px 以内、主爪の 0.9 倍より短い（pl32f_branch_rule）",
            types_final={"T1": 160, "T4": 17, "T2": 2, "T3": 1, "branches": 4, "T3_claw": "C092（支 C093・C089）"},
            reps=reps["fix01"], c095=m95["fix01"],
            verdict="決めた（T3 1 本。代表10形は美術優先29 の R1〜R10 のまま、D8 の船側中央の爪は C095 のままで 95・97・98 を満たす。代表10形の輪郭 ≤4 px は 5／10）"),
    }
    sb = rows_f
    backlog = {
        "95〜98 船側中央の爪 C095（立体の帯の投影）": {"before_pl31": m95["prev"], "build": m95["build"], "final": m95["fix01"],
                                                "verdict": "95・97・98 を満たす（作る部の後退を修正の回 1 で直した）。輪郭 ≤4 px は満たさない（5.86・5.27 px）。96 は文言が手元にないので数えない"},
        "95〜98 一覧の原画の爪 C095": {"value": mb["backlog_values"]["b95_98_centre_C095"]["painting_inventory"], "verdict": "95・97・98 を満たす"},
        "122・127・128 各列の根元と先端 ≤4 px": {"final_rows": {k: {"claws": v["claws"], "root_le4": v["root_le4"], "tip_le4": v["tip_le4"],
                                                                    "root_max": v["root_max"], "tip_max": v["tip_max"]} for k, v in sb.items()},
                                           "root_max_px": max(v["root_max"] for v in sb.values()), "tip_max_px": max(v["tip_max"] for v in sb.values()),
                                           "verdict": "満たす（帯にした 184 本とも。列と項目番号の対応は文言が手元にないので全部の列で数えた）"},
        "123〜126 代表10形": {"final": reps["fix01"], "build": reps["build"],
                           "verdict": "長短の順序（Spearman 1.00）・先端の向き（差 最大 3.5°）・幅（領域の 0.71〜1.14 倍）は満たす。左右の輪郭 ≤4 px は 5／10（R1・R4・R6・R7・R10）で一部"},
        "144・145・261 ほかの爪ごとの ≤4 px（記録のみ）": {"final": out13["fix01"], "build": out13["build"], "before_pl31": {"claws": 148, "le4": 51, "p50": 5.0, "p90": 9.61},
                                                 "verdict": "記録のみ（96／184 本）"},
    }
    gates = {
        "final": g["fix01"], "build": g["build"], "prev_pl31": g["prev_pl31"], "cp1": g["cp1"], "r2601": g["r2601"],
        "verdict_ja": "後退なし。78 2.741・130 3.5815・131 3.4419・132 σ12 3.5576（爪あり・なし）は仕上げ31 と同じ。72 σ12 p95 は爪なし 3.8507（同じ）・爪あり 3.5757（仕上げ31 3.5698 より +0.006 px、関門 ≤ 4 px の内）。"
                      "記録のみの定義の読みの 132（爪あり）5.3771 px（仕上げ31 5.2998 px より +0.077 px）。CP1／26修正01 に対しては段階5確認 §6.3 以来の後退のまま（この群で増えも減りもしない）"}
    # 色区の項目 73〜270（新しい読み：仕上げ29 で色が立体の材質になったので 28修正01 の投影の値と比べると全部が不合格。記録のみ）
    regs = {"prev_pl31": J(REPO + "/Docs/Evidence/Polish/31/pl28u_regress_after.json"), "build": J(E + "/pl28u_regress_after.json"),
            "final": J(E + "/pl28u_regress_fix01.json")}
    colour = {}
    for st in ("t28_white", "t28_claws"):
        colour[st] = {}
        for it in ("73", "77", "79", "118", "120", "133", "134", "175", "263", "270"):
            colour[st][it] = {k: [r["sets"][st]["strict"]["colour_items"][it]["max_now_px"], r["sets"][st]["strict"]["colour_items"][it]["verdict"]]
                              for k, r in regs.items()}
        colour[st]["265_dE00"] = {k: r["sets"][st]["strict"]["colour_265_267"]["265_dE00"] for k, r in regs.items()}
        colour[st]["267_bands_ge_20px"] = {k: r["sets"][st]["strict"]["colour_265_267"]["267_bands_ge_20px"] for k, r in regs.items()}
    colour["note_ja"] = ("爪なし（t28_white）は ID の画像が仕上げ31 と SHA-256 まで同じで、全部の値が同じ。爪あり（t28_claws）で動いたのは 134（41.48 → 作る部 41.46 → 24.54 px）と "
                         "267 の 20 px 以上の帯（原画視点 114 → 作る部 107 → 141。爪の帯が色の帯として数えられる）だけ。どれも記録のみ（新しい読み）")
    views = {
        "painting": "t 6 s は前と同じ。t 9 s：頂の白の上の爪の芽は小さな c の弧（前の唇の上の早い白い塊と芽はない）。t 10.5 s：伸びる途中の爪は c・u の弧で、閉じた輪は b区域で 1（作る部 4）。"
                    "t*：頂・唇・b区域の爪は根元が開いた鉤で、付け根に水色の版の雲。b区域の白い背に爪が並ぶ（前はほとんど線がない）が、房には読めない。引き伸ばし・継ぎ目・溶けた爪はない",
        "seat": "t 6・9・10.5 s は前とほぼ同じ。t*：作る部の左端の藍の上の白い棒・くねった白はない。頂の縁の爪の線は前と同じに並ぶ。b区域の稜を越える帯の細い線が残る（限界）",
        "seat_toward_wave": "t 9 s：頂の白が小さい（前の唇の先の白い塊がない）。t*：作る部の左上の白い斜めの棒と鉤はない。管の内側からは爪がほとんど見えない（前と同じ）",
        "side_left": "唇の縁の爪の画素が少し変わるだけ。浮いた爪・跳ぶ爪はない",
        "side_right": "ほとんど変わらない。浮いた爪・跳ぶ爪はない",
        "back65": "ほとんど変わらない（爪は波の手前の面にあり見えない）",
        "top": "唇の縁の小さな変化だけ。傷はない",
        "turntable": "0〜60°：頂と b区域の爪の付け根に水色の雲、b区域に爪の帯。90〜330°：爪はほとんど見えない（前と同じ。仕上げ29 の限界 1、造形は仕上げ33）",
        "verdict_ja": "この群の範囲（爪の一覧・結び付け・成長の始まり・爪の色と縁の線）に、色面の引き伸ばし・継ぎ目・平らな面・溶けた爪は 7 視点＋回り台・4 時刻で見えない（記録の部の目視で 11 枚の図を見直した。絵の所は再評審が見た修正の回 1 の図と画素まで同じ）"}
    unity = {"playmode_single": mf["unity"]["playmode_single"], "playmode_release": mf["unity"]["playmode_release"], "release": mf["unity"]["release"],
             "release_scene_sha256": J(E + "/release_build_fix01.json")["sceneSha256"], "exe_sha256": J(E + "/release_build_fix01.json")["exeSha256"],
             "player_runs": {k: {kk: v[kk] for kk in ("frames", "seconds", "pass_", "errors", "exceptions")} for k, v in mfx["11_performance"]["runs"].items()},
             "note_ja": "Release のプレイヤーは PC で仕上げ31 と交互に 2 組（fix_p3・fix_p4 と pl31_p3・pl31_p4）。作る部は build_main。HMD ではない"}
    limits = [
        "b区域の房は一部：藍の窓と 3 つの房の形は主役波の形（仕上げ28 の限界）と材質（仕上げ29）。爪の帯の読みやすさは仕上げ33 の同じ［利用者の言葉］の行、藍の窓は 10/29 の後",
        "帯にしない 29 本（根元が立体の材質の白の範囲の外。原画では白い泡、材質では藍）：b区域と主浪の間・b区域の下・主浪の左下の利用者の 4 本。白の範囲（仕上げ29・31）を広げれば帯にできる",
        "座席から b区域の稜を後ろから見ると、稜を越える帯が細い線として残る（帯の持ち上げと厚みの分）",
        "代表10形の輪郭 ≤4 px は 5／10、爪ごとは 96／184。C095 の輪郭は 5.86・5.27 px（帯の断面と曲がり。仕上げ33）",
        "72 σ12 p95（爪あり）は仕上げ31 より +0.006 px（関門の内）、定義の読みの 132（爪あり）は +0.077 px（記録のみ。爪のこぶは仕上げ33）",
        "根元の先で指が続く疑い 11 本（目視の判定つき。C210・C233 は目では続くが延ばしていない）",
        "位置合わせが不確かな利用者の爪 4 本（claw031・047・049・089）と claw035・043、つなげない手前の波の claw073・074",
        "側面・後ろ・真上・回り台 90〜330° では爪がほとんど見えない（爪の大きさ・厚み・数は仕上げ33）",
        "帯の持ち上げ（原画のカメラの向きへ 8.5 cm ＋ 厚みの 1/4）、縁の線の根元の開き、水色の雲は HMD で未検証",
        "PL32ClawDriver は時刻が変わらない時だけ差し替えを止める。形成の間は毎コマ差し替える（90 Hz の予算の判定は仕上げ35）",
        "b区域の候補の目視は 1 回。真値を覆う割合 0.51（右上の空へ出る細い指、帯の下の窓の間の指など、一覧にない指がある）",
        "調べの限界：Vermeulen の本文と The Met の解説は読めていない。「色の版は墨版の線の内側に収まる」は一般の浮世絵の手順で、この作品で確かめたものではない。122・127・128 と列の対応と 96 の文言はリポジトリの外のバックログ",
        "前後の動画は原画視点・座席・座席から波の方向・左の側面・回り台の 5 本。右の側面・後ろ 65°・真上は静止画だけ（描画の段 -pl29VideoViews に入っていない）",
    ]
    return mb, mf, dict(
        schema="GreatWave.Polish32.metrics/2", group="仕上げ32（設計32 白波群と ID・爪の一覧）", date="2026-10-02",
        state_ja="作る部（02:11〜03:55）→ 自己評審（評審 2 件）→ 修正の回 1（04:20〜06:05、審査の 12 の指摘）→ 再評審 → 修正の回 2（06:18〜06:21、記録の文の誤り 1 件だけ、作り直しなし）→ 記録の部（06:21〜）。"
                 "計画 §5.3 の 8 行のうち 6 行を満たし、2 行は決めて記録した。［利用者の言葉］2 項目：Q8 は満たす、Q16・Q21 は一部。進行役の再評審の前。HMD 実機ではない。利用者は見ていない",
        before_ja=mb["before_ja"] + "（前の描画 r_before）",
        after_ja="後＝採用の状態：作る部の一覧・ID・白（hero_pkg、T_white 9f7ab0b6…）に、修正の回 1 の一覧の直し（fix01/list）・帯（fix01/claws、帯 184 本）・Unity の部品（PL32ClawLook・PL32ClawDriver・PL32 Claw Outline）を加えたもの。描画 fix01/r_fix01",
        user_words=[
            {"item_ja": "Q8「建议去调查北斋的这幅画的印刷流程以及历史，根据印刷流程去确定爪的基础色」→ ① 摺りの工程と歴史の調査 ② 爪の基礎色と IoU の定義（D25）を決め直す",
             "source_ja": "計画 §5.3 仕上げ32 の 1 行目（第0.3節、元の行、設計32 §7）", "verdict": "満たす（読み方と決定は進行役、利用者は未確認）"},
            {"item_ja": "Q16・Q21 の b区域の浪尖の爪（15 本）が、原画視点で房として読めない",
             "source_ja": "計画 §5.3 仕上げ32 の 2 行目（段階9確認 #2・#8、段階6確認 F6-3）",
             "verdict": "一部（作る部の「満たす」は修正の回 1 で取り下げ。2 回目の作り直しはしていない。仕上げ33 と 10/29 の後の一覧へ）"}],
        backlog=mb["backlog"], time_box_days=1.5,
        plan_rows=plan_rows, backlog_values=backlog, painting_gates=gates,
        evaluator23={"final": mf["evaluator23"]["fix01"], "build": mf["evaluator23"]["build"],
                     "prev_pl31": mf["evaluator23"].get("prev_pl31", {c: v["prev_pl31"] for c, v in mb["evaluator23"].items() if isinstance(v, dict) and "prev_pl31" in v}),
                     "verdict_ja": "合否の数は 4 組とも仕上げ31 と同じ（線なし 合格 4・不合格 5、線あり 合格 2・不合格 7）"},
        colour_items_new_reading=colour,
        views_q28=views, unity=unity, limits_ja=limits,
        fix_rounds={"round1": "審査の 12 の指摘（metrics_fix01.json の must_fix）。8 を直し、3 は一部（b区域の房、代表10形の輪郭、72 σ12 の爪あり）、1 は記録のみ（144・145・261）",
                    "round2": "metrics_fix01.json の指摘 12 の判定の文が数と食い違っていたのを直した（記録だけ）",
                    "record_phase_corrections_ja": ["修正の回 1 の記録の表で、修正01 の 122・127・128 の先端の最大を 2.10 px と書いていた（作る部の値の写し）。正しくは 0.54 px（pl32f_measure_claws.json の after の行の tip_max の最大）。最終の記録はこの値にした"]},
        sub_metrics={"build": "metrics_build.json（作る部、03:52。記録の部で metrics.json から名前を替えた）", "fix01": "metrics_fix01.json（修正の回 1・2）"},
        record_phase=chk)


def main():
    files = commit_files()
    open(COMMIT_LIST, "w", encoding="utf-8", newline="\n").write("\n".join(files) + "\n")
    chk = {"date": "2026-10-02", "commit_list": check_commit_list(files), "media": media_check(), "sheets_retitled_same_tiles": sheets_same_tiles(),
           "scene_guids": guid_check(files), "strings": string_check(files), "adopted_data_same_as_fix01": data_same_as_fix01()}
    mb, mf, metrics = build_metrics(chk)
    chk["strings_in_metrics_json_before_write"] = text_hits(json.dumps(metrics, ensure_ascii=False))
    json.dump(metrics, open(E + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rb, rf = J(E + "/run_build.json"), J(E + "/run_fix01.json")
    fsha = {f: sha(REPO + "/" + f) for f in files if f not in ("Docs/Evidence/Polish/32/run.json",)}
    arch = B + "/record/archive"
    rj = dict(
        schema="GreatWave.Polish32.run/2",
        tools=rf["tools"],
        commands_record_ja=[
            "set PYTHONIOENCODING=utf-8, PYTHONUTF8=1、TMP・TEMP を G: の Unity/Build/Polish/32/record に（C: の空きが 8 MB しかないため）",
            "記録の部の前の Polish_32_ja.md（作る部）・Polish_32_修正01_ja.md・metrics.json・run.json・前後の図と動画を Unity/Build/Polish/32/record/archive へ写した（SHA-256 は archive/sha256_before_record.txt）",
            "Docs/Evidence/Polish/32 の metrics.json → metrics_build.json、run.json → run_build.json（中身は同じ。pl32_record.py の出力の名前も替えた）",
            "Docs/Progress/Polish_32_修正01_ja.md を Unity/Build/Polish/32/record/archive へ移した（記録は Polish_32_ja.md の 1 つにまとめた）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_sheets.py --before <B>/r_before --after <B>/fix01/r_fix01 --out Docs/Evidence/Polish/32 --final   # 見出しだけ「仕上げ32」に（絵は修正の回 1 と同じ）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32r_record.py   # metrics.json・run.json・commit_list.txt と記録の部の確かめ"],
        commands_build=rb["commands"], commands_fix01=rf["commands"], common_ja=rb.get("common_ja"),
        files_sha256=fsha,
        data_sha256=rf["data_sha256"],
        read_only_user_files_sha256=rf.get("read_only_user_files_sha256"),
        read_only_note_ja=rf.get("read_only_note_ja"),
        references_ja=rb.get("references_ja"),
        sub_runs={"run_build.json": sha(E + "/run_build.json"), "run_fix01.json": sha(E + "/run_fix01.json")},
        archive_sha256={rel(p): sha(p) for p in sorted(glob.glob(arch + "/*")) if os.path.isfile(p)},
        prohibited_paths_ja="AGENTS.md の禁止の場所は開いていない。参照モデル・参照の彫刻の写真・G:/research/Wave Simulation は開いていない。"
                            "爪形分析は修正の回 1 で Q8 の例外として読み取りだけ（9 本の切り抜き・マスクと構造点の表、メモリの中だけ）。ds33_claw_rig.py・pl32f_claw_rig.py は Q8 の例外の README 1 ファイルの数を読む")
    rj["strings_in_run_json_before_write"] = text_hits(json.dumps(rj, ensure_ascii=False))
    json.dump(rj, open(E + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    s = {k: (v.get("pass_") if isinstance(v, dict) else (len(v) if isinstance(v, list) else v)) for k, v in chk.items() if k != "date"}
    s["strings_in_run_json_before_write"] = rj["strings_in_run_json_before_write"]
    print(json.dumps(s, ensure_ascii=False))
    print("files", len(files), "metrics", os.path.getsize(E + "/metrics.json"), "run", os.path.getsize(E + "/run.json"))


if __name__ == "__main__":
    main()
