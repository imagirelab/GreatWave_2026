# -*- coding: utf-8 -*-
"""美術の見本02（Q30）を利用者へ渡す時の記録：Docs/Evidence/ArtSample02/ の metrics.json・run.json・rules_check.json を書く。
数は Git 対象外の Build/Polish/sample02/ の各部の記録（爪の部 claws/、背の部 back/final/、組み立て assemble/、修正の回 1 fix01/）から読むだけ。
利用者のマスク・画像、参照モデル、彫刻の写真は読まない（数と出典のパス・SHA-256 だけを書く）。
使い方（リポジトリの根で、as02_deliver.py の後）：py -3.10 -B Tools/GWWaveGen/as02/as02_deliver_record.py <開始の時刻 YYYY-MM-DDTHH:MM>
"""
import glob
import hashlib
import json
import os
import platform
import shutil
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
S2 = REPO + "/Unity/Build/Polish/sample02"
FIX = S2 + "/fix01"
EV = REPO + "/Docs/Evidence/ArtSample02"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def J(p):
    return json.load(open(p, encoding="utf-8"))


def stat(v):
    v = np.asarray(v, float)
    return dict(n=int(len(v)), p10=round(float(np.percentile(v, 10)), 4), p50=round(float(np.percentile(v, 50)), 4),
                p90=round(float(np.percentile(v, 90)), 4), min=round(float(v.min()), 4), max=round(float(v.max()), 4))


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else ""
    os.makedirs(EV, exist_ok=True)
    rc_src = S2 + "/rules_check.json"
    shutil.copyfile(rc_src, EV + "/rules_check.json")
    rc = J(rc_src)
    rc_prev = J(S2 + "/rules_check_AS02B_A.json")
    fm = J(FIX + "/metrics.json")
    am = J(S2 + "/assemble/metrics.json")
    cm = J(S2 + "/claws/metrics.json")
    bm = J(S2 + "/back/final/metrics.json")
    rep = J(FIX + "/assemble/claws/mesh/as02_claws_report.json")
    sheets = J(S2 + "/deliver/deliver_sheets.json")
    placed = [c for c in rep["claws"] if c.get("placed")]
    dups = [dict(user_id=c["user_id"], duplicate_of=c.get("duplicate_of"), why_ja=c.get("why_not_ja")) for c in rep["claws"] if not c.get("placed")]
    per = []
    for c in placed:
        per.append(dict(user_id=c["user_id"], iou_painting=c["iou_painting"], iou_face=c["iou_face"],
                        iou_painting_s8=c.get("iou_painting_s8"), iou_face_600px=c.get("iou_face_600px"),
                        length_3d_m=c["length_3d_m"], width_max_m=c.get("width_max_m"), thick_max_m=c.get("thick_max_m"),
                        root_dir_vs_normal_deg=c["root_dir_vs_normal_deg"], alpha_deg=c.get("alpha_deg"), beta_deg=c.get("beta_deg"),
                        stretch=c.get("stretch"), stations=c.get("stations"), n_ortho=c.get("fix01_n_ortho"),
                        standard_pass=not [f for f in (c.get("standard_fails_ja") or []) if not f.startswith("面から見た")],
                        area_mask_disp_px=c.get("area_mask_px"), visible_fraction=c.get("visible_fraction")))
    A = cm["variant_A_paint"]["summary"]
    B = cm["variant_B_ref"]["summary"]
    metrics = dict(
        schema="GreatWave.ArtSample02.metrics/1",
        created_local=time.strftime("%Y-%m-%dT%H:%M"),
        note_ja="美術の見本02（Q30-1・Q30-2）。主役波 K*′ AS02C（P28R2rec の見えない背を一つの山に直した形）を t* = 12 s の静止で、"
                "利用者が爪形分析で切り出した 100 本の爪を 3D に戻して 83 本を置き（17 本は同じ爪の 2 回目の切り抜き）、面の色は見本 A を中立の地にした。"
                "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。美術が届いたかは利用者が決める（Q29・Q30）。",
        rules=dict(source=rel(rc_src), sha256=sha(rc_src), verdicts=rc["summary"]["verdicts"], all_pass=rc["summary"]["all_pass"],
                   verdicts_first_assembly_AS02B_A=rc_prev["summary"]["verdicts"] if "summary" in rc_prev else None,
                   C3_fail_claws=rc["rules"]["C3"]["iou_painting_below_085"],
                   C3_fail_at_old_resolution=rc["rules"]["C3"]["iou_painting_s8_below_085"],
                   C3_conflict_search=rc["rules"]["C3"]["conflict_search"],
                   delivery_decision_ja="C3 が 2 本（83 本中）で通らないまま渡す。要求書の「通らない見本は出さない」の例外として進行役の判断で出す"
                                        "（理由：2 本は C2〈利用者の模型の水準〉と C3〈マスクとの重なり 0.85〉が両立しない手描きの S 字の縁で、"
                                        "4,608 通りの形を試した最大が 0.834・0.840。C2 を先にした。利用者の判定〈Q30〉を待つ方が先に進む。記録 ArtSample_02_ja.md §6）"),
        back_S4=dict(peaks_c_by_level=fm["S4"]["peaks_c_by_level"], middle_zone_c=[-6.0, 6.0],
                     bulge_over_chord_dip_m=fm["S4"]["bulge_over_chord_dip_m"], back_contour_dip_m=fm["S4"]["back_contour_dip_m"],
                     silhouette_dip_px=fm["S4"]["silhouette_dip_px"], far_volume_c_gt_0_m3=fm["S4"]["far_volume_c_gt_0_m3"],
                     tolerance_m=0.10, strict_zero_dip=False, painting_view_unchanged=fm["S4"]["painting_view_unchanged"],
                     moved_vertices_gt_1mm=fm["S4"]["moved_vertices_gt_1mm"], max_move_m=fm["S4"]["max_move_m"],
                     rubric_must_fail=dict(P28R2rec=bm["rubric"]["summary_base"]["must_fail"], AS02B=bm["rubric"]["summary_cand"]["must_fail"],
                                           AS02C=fm["S4"]["rubric_summary_AS02B_to_AS02C"][1]["must_fail"], n_checks=55),
                     limits_AS02B_ja=bm["limits_ja"]),
        claws=dict(
            users=100, placed=len(placed), duplicates_dropped=dups,
            on_hero_and_near_sea_ja="主役波 73・近い海 10（爪の部の README_interface）",
            C2=fm["C2"], C3=fm["C3"], C4_record=fm["C4_record"],
            iou_painting=stat([c["iou_painting"] for c in placed]), iou_face=stat([c["iou_face"] for c in placed]),
            length_3d_m=stat([c["length_3d_m"] for c in placed]), root_dir_vs_normal_deg=stat([c["root_dir_vs_normal_deg"] for c in placed]),
            layout=fm["claws_layout"],
            user_claw_standard=dict(source="Unity/Build/Polish/sample02/claws/user_claw_standard.json（claw_mid・claw_low を読み取りのみで測った数）",
                                    values=cm["user_claw_standard"]),
            reference_model_placement_r07=dict(source="Unity/Build/Polish/sample02/claws/ref/as02_ref_claw_placement_r0.7.json（参照モデルの数だけ。一時キャッシュは消した）",
                                               values=cm["reference_model_placement"].get("_r0.7")),
            placement_variants=dict(
                note_ja="案 A（原画の射線の上で奥行きだけ動かす）を見本にした。案 B（作り直した爪を根元の周りに回し、根元の向きを参照モデルの p50 24° へ起こす）は前の形（修正の回 1 の前の爪、背 P28R2rec）での比べ",
                A=dict(iou_painting=A["iou_painting"], iou_face=A["iou_face"]),
                B=dict(iou_painting=B["iou_painting"], iou_face=B["iou_face"], gate_132_s12_px=14.4),
                visible_claw_px_per_view=cm["visible_claw_pixels_per_view"]),
            per_claw=per),
        painting_view=dict(gates=rc["rules"]["G2"]["gates"], eval23=rc["rules"]["G2"]["eval23"], note_ja=rc["rules"]["G2"]["note_ja"]),
        no_projection=dict(code_pass=rc["rules"]["G1"]["code_pass"], surface_param=rc["rules"]["G1"]["surface_param"]),
        views_now_vs_previous=fm["views"],
        hero_package=dict(AS02B=am["hero_package"], note_ja="hero_pkg_AS02C は t* の層だけを替えた包み。τ < 0 の層は G_p28rec のままなので、見本は t* の静止だけに使える"),
        material_attr_pin=fm["attr_pin"],
        evidence_sheets=sheets,
    )
    json.dump(metrics, open(EV + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as02/*"))
    subruns = [S2 + "/claws/run.json", S2 + "/claws/metrics.json", S2 + "/claws/ref/as02_ref_cache_log.json", S2 + "/back/final/run.json",
               S2 + "/back/final/metrics.json", S2 + "/assemble/run.json", S2 + "/assemble/metrics.json", FIX + "/run.json", FIX + "/metrics.json",
               S2 + "/rules_check_AS02B_A.json", S2 + "/rules_check.json", FIX + "/assemble/claws/mesh/as02_claws_report.json",
               FIX + "/assemble/claws/mesh/ds33_claw_layout.json", FIX + "/back/final/cand/kstarAS02C_a45.gwb", FIX + "/back/final/cand/back_design.json",
               FIX + "/back/final/measure.json", FIX + "/claws/conflict_search.json", S2 + "/deliver/deliver_sheets.json"]
    refl = J(S2 + "/claws/ref/as02_ref_cache_log.json")
    run = dict(
        schema="GreatWave.ArtSample02.run/1",
        deliver_start_local=start, deliver_end_local=time.strftime("%Y-%m-%dT%H:%M"),
        sample_span_local_ja="2026-10-04 1:21 頃〜4:01（背の部 1:21〜2:25、爪の部〜2:28、組み立て 2:30〜2:48、修正の回 1 2:49〜4:01）、渡す準備 %s〜" % start,
        python=platform.python_version(), numpy=np.__version__,
        unity="6000.4.3f1（batchmode、AS01SampleRender。新しい C# は無い）", blender="Blender 5.2.2（Workbench の粘土）", houdini="使っていない",
        commands=["py -3.10 -B Tools/GWWaveGen/as02/as02_deliver.py（爪の近くの図を描き、背の図を描き直し、図 6 枚を Docs/Evidence/ArtSample02 へ）",
                  "py -3.10 -B Tools/GWWaveGen/as02/as02_deliver_record.py %s" % start,
                  "各部のコマンドは下の sub_records の run.json にある"],
        reference_model=dict(file="G:/research/model/wave_repair_zbrush2.obj", sha256=refl["source_sha256"],
                             use_ja="爪の部だけが置き方の数を測るために一時キャッシュで読み、測った後に消した（cache_log）。生成器は OBJ を読まない（F13-1）。背の部・組み立て・修正の回 1・渡す準備は読んでいない",
                             cache_log=rel(S2 + "/claws/ref/as02_ref_cache_log.json"),
                             cache_deleted=all(e["event"] != "cache_created" or any(d["event"] == "cache_deleted" and d["file"] == e["file"] for d in refl["events"]) for e in refl["events"]),
                             cache_dir_exists_now=os.path.exists(S2 + "/_objcache")),
        sculpture_photos_ja="爪の部が 8 枚を作業の一時フォルダー（リポジトリの外）で縮めて見ただけで、消した。写真も写真から作った画像もリポジトリに入れていない",
        user_files=dict(
            claw_analysis="G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3/clawNNN/{fill_mask.png, centerline_raw.csv}、final_100_claw_structural_points_v2/final_points_long.csv（読み取りのみ。D14・D23）",
            claw_analysis_sha256_ja="マスク・中心線の SHA-256 は Build/Design/32/list+ids/ds32_user100_registration.json の user_files_sha256、構造点 39474fff9dbd20f42436a0990d47bd0ec56d41b90e3d53e33d04484aae75c539",
            claw_models=J(S2 + "/claws/run.json")["inputs"]["user_claw_models"],
            in_repo_ja="マスク・画像・模型のファイルはリポジトリへ写していない。図 as02_1・as02_2 には、マスクの縁を我々が線（緑）で描いたものだけがある。マスクの塗りと claw_mid の描画が入った一覧（s1_claw_gallery）は Git 対象外の Build だけ"),
        painting_image=dict(path="Docs/References/Met_JP1847_DP130155.jpg", sha256=sha(REPO + "/Docs/References/Met_JP1847_DP130155.jpg")),
        sub_records={rel(p): sha(p) for p in subruns if os.path.exists(p)},
        tools_sha256={rel(p): sha(p) for p in tools if os.path.isfile(p)},
        evidence_sha256={rel(p): sha(p) for p in sorted(glob.glob(EV + "/*")) if not p.endswith("run.json")},
        incidents_ja=[
            "修正の回 1 で、Blender の粘土の描画を相対の出力の場所で回し、静止画 17 枚が C:\\Unity\\Build\\Polish\\sample02\\fix01\\back\\final\\renders に書かれた。"
            "回 1 で G: の fix01/back/final/renders へ移した。渡す準備で、残っていた空のフォルダー（C:\\Unity\\Build\\Polish 以下、10/4 3:31 にこの回が作ったもの、ファイル 0）を rmdir で片付けた。C:\\Unity\\Build\\ArtFirst（前からある）は触っていない",
            "渡す準備で、背の図（as02_fix01_back_chart.py）の説明の「見本02（水色）」が線の本当の色（緑の点線）と違っていたので、文だけ直して描き直した（数は同じ measure.json）"],
        git="add・commit・push はしていない（コミットは進行役。一覧は Unity/Build/Polish/sample02/commit_list.txt）",
    )
    json.dump(run, open(EV + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", EV + "/metrics.json", os.path.getsize(EV + "/metrics.json"))
    print("wrote", EV + "/run.json", os.path.getsize(EV + "/run.json"))
    print("cache_deleted", run["reference_model"]["cache_deleted"], "cache_dir_exists_now", run["reference_model"]["cache_dir_exists_now"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
