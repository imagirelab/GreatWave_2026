# -*- coding: utf-8 -*-
"""設計33（爪の部）：metrics.json（受入・記録のみ・限界）と run.json（コマンド・道具の版・入出力の SHA-256）をまとめる。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds33/ds33_claws_record.py
一度に回す順：ds33_claw_rig.py → ds33_claw_anim.py → ds33_claw_render.py → ds33_claws_indep_check.py → ds33_claws_record.py
"""
import collections
import os
import platform
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds33_common as U  # noqa: E402

OUT = U.OUT


def main():
    rig = U.jload(OUT + "/ds33_claw_rig.json")
    chk = U.jload(OUT + "/ds33_claw_checks.json")
    ind = U.jload(OUT + "/ds33_claws_indep_check.json")
    con = U.jload(OUT + "/ds33_contour_tstar.json")
    vis = U.jload(OUT + "/ds33_visibility_tstar.json")
    claws = rig["claws"]
    tc = collections.Counter(c["type"] for c in claws)
    rp = chk["reprojection_tstar_record_only"]
    r0, r1 = con["results"]["no_claws"], con["results"]["claws"]
    bq = [c for c in claws if c["b_region_q16"]]
    bgroups = collections.defaultdict(list)
    for c in bq:
        bgroups[c["group"]].append(c["id"])
    acc = {
        "overlay_position_orientation": dict(
            item="原画視点で一覧の爪の位置・向きの対応が見て取れる（重ね図）", verdict="pass（目視・進行役の判断。重ね図 fig_ds33_tstar_overlay.png と列ごとの 4 枚）",
            record_only_4px=dict(hausdorff_px_p50=rp["hausdorff_px"]["p50"], hausdorff_px_p95=rp["hausdorff_px"]["p95"], hausdorff_px_max=rp["hausdorff_px"]["max"],
                                 claws_le_4px=rp["hausdorff_px"]["le4"], claws=len(claws), note_ja="骨格の曲線（関節を通る Catmull-Rom）と一覧の中心線の対称 Hausdorff（表示の画素）。記録のみ")),
        "105": dict(item="根元から水面までの距離 ≤ 1 mm", value_m=chk["item105"]["max_m"], indep_m=ind["item105"]["max_m"],
                    verdict="pass" if chk["item105"]["pass_"] and ind["item105"]["pass_"] else "fail"),
        "137": dict(item="根元の滑り 0", value_m=chk["item137"]["max_m"], value_cells=chk["item137"]["max_param_cells"], indep_m=ind["item137"]["max_m"],
                    verdict="pass" if chk["item137"]["pass_"] and ind["item137"]["pass_"] else "fail",
                    note_ja="根元の (行, 列) は固定。読み直しの差は float32 の頂点の丸め（µm）"),
        "139": dict(item="成長の途中の欠落 0（使える水準）", generator=dict((k, chk["item139"][k]) for k in ("visibility_gaps", "never_visible", "decreasing_samples", "nan_frames", "zero_area_frames")),
                    indep=ind["item139"], verdict="pass" if chk["item139"]["pass_"] and ind["item139"]["pass_"] else "fail"),
        "vertices": dict(item="1 本あたり ≤ 600 頂点", per_claw_max=chk["vertices"]["per_claw_max"], per_type_instance_max=chk["vertices"]["per_type_instance_max"],
                         verdict="pass" if chk["vertices"]["pass_"] else "fail"),
    }
    design = dict(
        types=dict(defined=list(rig["types"].keys()), instances=dict(tc),
                   note_ja="T1 単爪・T2 主爪＋1支・T3 主爪＋2支・T4 細い指・T5 右側の鉤（型だけ）。一覧から T1・T2（支 8 本）・T4 が生成された。"
                           "T3 は一覧に、1 本の爪の領域から 2 本の支が出る爪がないので 0 本（型の試作の図にだけ出す）。T5 は右側の爪が主役波のシートに結び付いていないので生成しない"),
        claws=len(claws), rows=dict(collections.Counter(c["row"] for c in claws)),
        segments=rig["stats"]["segments"], joint_how=rig["stats"]["joint_how"], hanging=rig["stats"]["hanging"],
        skeleton_vs_user100=dict(list_ratio_median_3seg=rig["stats"]["list_ratio_median_3seg"], user100_ratio_median=rig["user100"]["ratio_median"],
                                 list_turn_abs_median_3seg_deg=rig["stats"]["list_turn_abs_median_3seg_deg"], user100_turn_median_deg=rig["user100"]["turn_median_deg"],
                                 note_ja="一覧（設計32）の中心線に当てはめた 3 段の骨格の長さ比と転折角（画面の 2 次元）は、利用者の 96 本の中央値に近い。短い 6 本だけ型の標準の骨格を使った"),
        band=dict(ring_vertices=8, stations={k: v["stations"] for k, v in rig["types"].items()}, thickness_ratio={k: v["thickness_ratio"] for k, v in rig["types"].items()},
                  note_ja="側面の厚み＝正面の幅 × 0.18〜0.25。根元が広く先端が閉じる（先端は 1 点）"),
        growth=dict(stage=rig["params"]["stage"], rule_ja="3 段の標準曲線（根元が白くなる → 伸びる → 最後に曲がる）。s = (τ − τ_start)/(0 − τ_start)。支は主爪が支の根元まで伸びてから",
                    order_indep=ind["growth_order"]),
        root_binding_ja="根元は設計32 の sheet_rc（シートの (行, 列)）に固定し、そのコマのシートの描画と同じ三角形の上の点に置く。関節と輪の座標系はコマごと（キーごと）に作り直す",
        web_join=dict(root_class=chk["web_join"]["root_class"], dist_to_white_vertex_m=chk["web_join"]["dist_to_white_vertex_m"],
                      note_ja="波頭の白い帯は設計31 の T_white で白くなるシートの色区（設計32 の約束）。爪は根元のその白の出現で生まれ、根元の白の円（シートに付く 8 点）でつながる"),
        b_region_q16=dict(claws=len(bq), groups=dict(bgroups), note_ja="b区域の爪の房（設計32 の群 GC32・GC33・GC34）と Q16 の浪尖の爪（b_region_q16 の 15 本、C172 は上側の列）を同じ型で生成した"),
        teleport=dict(count=chk["teleport"]["count"], tip_spikes_indep=ind["tip_spikes"]),
    )
    record_only = dict(
        contour_tstar=dict(method_ja=con["method_ja"],
                           no_claws=dict(lf_132_sigma12_max=r0["lf_132_sigma12_max"], lf_72_sigma24_p95=r0["lf_72_sigma24_p95"],
                                         raw_78=r0["raw"]["78_envelope"]["max_px"], raw_130=r0["raw"]["130_envelope"]["max_px"], raw_131=r0["raw"]["131_envelope"]["max_px"],
                                         raw_132_max=r0["raw"]["132_envelope"]["max_px"], raw_72_p95=r0["raw"]["72_envelope"]["p95_px"]),
                           claws=dict(lf_132_sigma12_max=r1["lf_132_sigma12_max"], lf_72_sigma24_p95=r1["lf_72_sigma24_p95"],
                                      raw_78=r1["raw"]["78_envelope"]["max_px"], raw_130=r1["raw"]["130_envelope"]["max_px"], raw_131=r1["raw"]["131_envelope"]["max_px"],
                                      raw_132_max=r1["raw"]["132_envelope"]["max_px"], raw_72_p95=r1["raw"]["72_envelope"]["p95_px"]),
                           unity_reference=con["reference"],
                           note_ja="爪なしの numpy の値は Unity（29修正01・設計30）の値と一致した（78・130・131・132 σ12・72 σ24・細部込みの 132・72）。"
                                   "爪ありで 78・130・131・132 σ12 は変わらず、72 σ24 p95 と細部込みの 132 最大・72 p95 が良くなった（後退なし）。Unity の原画視点の描画は変えていない（設計34 で入れる）"),
        visibility_tstar=dict(percentiles_0_5_10_25_50=vis["frac_percentiles_0_5_10_25_50"], under_0p5=vis["under_0p5"], under_0p8=vis["under_0p8"], lowest=vis["lowest"][:6]),
        arc_length_drop=dict(frames=chk["item139"]["arc_length_drop_over_1pct_frames_record_only"], ids=chk["item139"]["arc_length_drop_ids_record_only"]),
        reprojection_truthlib=ind["reprojection_tstar_truthlib"],
    )
    limits = [
        "T3（主爪＋2支）は一覧に当てはまる爪がなく 0 本。型の試作の図だけ。支の判定（根元が主爪の領域の中、主爪の中心線の 10〜95%）は仮",
        "T5（右側の鉤）は型の定義と試作の図だけ。右側の爪 25 本は主役波のシートに結び付いていない（設計32、ブラッシュアップの最後）",
        "唇から空へ出る爪（15 本）の一部は、原画視点 t* でシートに一部が隠れる（見える割合の最小 %.2f、0.8 未満 %d 本。記録のみ）" % (vis["frac_percentiles_0_5_10_25_50"][0], vis["under_0p8"]),
        "帯の幅は一覧の領域（D25 の仮の定義）の距離変換を型の先細りの 0.6〜1 倍に収めた。原画視点 t* の帯の見かけの幅は、領域の幅の中央値 0.72 倍（中心線の 1/3 の所、四分位 0.61〜0.95）・0.81 倍（1/2 の所）で、原画の指より細い。面の傾きの補正の下限 0.4 と根元の幅の上限（長さの 0.45 倍）による。爪ごとの輪郭の合わせは仕上げ32・33",
        "成長の時刻は根元の T_white（設計31）から t* まで（0.69〜2.68 s）。見え方の否決はまだない（計画の損切り：3 段の標準曲線に固定する形を、はじめから既定にした）",
        "崩壊での消失は作らない（Q11）。動画は成長 → 曲がり → t* の保持",
        "描画は numpy の z バッファの仮の NPR（Unity ではない）。Unity での 3 層の再生は設計34。HMD（PS VR2）は保留",
        "近くから見ると（fig_ds33_single_growth.png の C075 の t*）、面に沿う爪の帯の一部が手前の面のふくらみに隠れる所がある（原画視点では見える割合 0.94）。座席からの見え方は設計34 で確かめる",
        "132・72 の爪のこぶは、爪で細部込みの値が少し良くなっただけで、4 px にはまだ届かない（132 最大 %.2f px、72 p95 %.2f px）。仕上げ28・32・33" % (r1["raw"]["132_envelope"]["max_px"], r1["raw"]["72_envelope"]["p95_px"]),
    ]
    metrics = dict(schema="GreatWave.DS33.claws.metrics/1", number="設計33（爪の部）", evidence_kind_ja="numpy の生成器・検査・z バッファの描画（Unity の描画ではない。HMD 実機ではない）",
                   backlog=["95", "96", "97", "98", "101", "103", "104", "105", "122〜129", "136", "137", "138", "139", "200"],
                   acceptance=acc, design=design, record_only=record_only, limits_ja=limits,
                   all_acceptance_pass=all(v["verdict"].startswith("pass") for v in acc.values()))
    U.jdump(OUT + "/metrics.json", metrics)
    # run.json
    files = {}
    for root, _, fs in os.walk(OUT):
        for fn in sorted(fs):
            if fn.startswith("_") or fn in ("run.json",):
                continue
            p = os.path.join(root, fn).replace("\\", "/")
            files[U.rel(p)] = dict(sha256=U.sha(p), bytes=os.path.getsize(p))
    tools = {}
    for fn in sorted(os.listdir(os.path.dirname(os.path.abspath(__file__)))):
        if fn.endswith(".py") and (fn.startswith("ds33_claw") or fn == "ds33_common.py"):
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn).replace("\\", "/")
            tools[U.rel(p)] = U.sha(p)
    import cv2
    run = dict(schema="GreatWave.DS33.claws.run/1", number="設計33（爪の部）",
               commands=["py -3.10 -B Tools/GWWaveGen/ds33/ds33_claw_rig.py", "py -3.10 -B Tools/GWWaveGen/ds33/ds33_claw_anim.py",
                         "py -3.10 -B Tools/GWWaveGen/ds33/ds33_claw_render.py --parts still,rows,types,contour,single",
                         "py -3.10 -B Tools/GWWaveGen/ds33/ds33_claw_render.py --parts video",
                         "py -3.10 -B Tools/GWWaveGen/ds33/ds33_claws_indep_check.py", "py -3.10 -B Tools/GWWaveGen/ds33/ds33_claws_record.py"],
               tools=dict(python=platform.python_version(), numpy=np.__version__, opencv=cv2.__version__, ffmpeg=U.FFMPEG.split("/")[-3]),
               generators=tools,
               inputs=dict(rig["inputs"], hero_pkg=dict(path=U.rel(U.HERO), pos_sha256=U.K.Pkg(U.HERO).k["pos_sha256"]),
                           timewarp=dict(path=U.rel(U.WARP), sha256=U.sha(U.WARP)), colour_sdf=dict(path=U.rel(U.W31.SDF), sha256=U.sha(U.W31.SDF)),
                           colour_uvwarp=dict(path=U.rel(U.W31.UVW), sha256=U.sha(U.W31.UVW)), painting=dict(path=U.rel(U.PAINT), sha256=U.sha(U.PAINT)),
                           sea=dict(path=U.rel(U.SEA)), claw_readme_ja="爪形分析の README は数値（96 本の中央値と四分位）だけを写した。爪形分析のフォルダーの画像・マスクは読んでいない"),
               not_used_ja="参照モデル、利用者の解算、爪形分析のフォルダー（G:/research/爪形分析）、禁止の場所、Unity、git の操作",
               outputs=files)
    U.jdump(OUT + "/run.json", run)
    print("all_acceptance_pass", metrics["all_acceptance_pass"])
    for k, v in acc.items():
        print(k, v["verdict"])


if __name__ == "__main__":
    main()
