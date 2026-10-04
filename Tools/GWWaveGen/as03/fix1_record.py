# -*- coding: utf-8 -*-
"""美術の見本03 修正の回 1：実行の記録（Build/Polish/sample03/fix01/fix1_run.json）。コマンド・決めたことと理由・直した所と直せなかった所・
入力と出力の SHA-256 を書く（読み取りのみ。Unity・シェーダー・見本01/02 のファイルは変えていない）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/fix1_record.py
"""
import glob
import hashlib
import json
import os
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
S3 = REPO + "/Unity/Build/Polish/sample03"
FIX = S3 + "/fix01"
TA = REPO + "/Tools/GWWaveGen/as03"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    rc, rb = jl(S3 + "/rules_check.json"), jl(S3 + "/rules_check_before_fix.json")
    t4, t4b = rc["rules"]["T4"], rb["rules"]["T4"]
    rep = {}
    for v in ("V1", "V2", "V3", "V1_ids", "V3_ids", "V1_cmp"):
        p = FIX + "/render/%s/as03asm_render_report.json" % v
        r = jl(p)
        rep[v] = {"report": rel(p), "sha256": sha(p), "protectedUnchanged": r.get("protectedUnchanged"), "secondsTotal": r.get("secondsTotal"),
                  "as03Crown": r.get("as03Crown"), "as03Params": rel(r["as03Params"]) if r.get("as03Params") else None, "as03ParamsSha256": r.get("as03ParamsSha256")}
    parts = {}
    for m in ("OUT", "IN"):
        for f in sorted(glob.glob(FIX + "/crown/%s/*" % m)):
            parts[rel(f)] = sha(f)
    tools = {rel(p): sha(p) for p in sorted(glob.glob(TA + "/fix1_*"))}
    sheets = {rel(p): sha(p) for p in sorted(glob.glob(FIX + "/sheets/*.png"))}
    res = {
        "schema": "GreatWave.AS03.fix1_run/1",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_local_ja": "2026-10-04 11:08〜12:05 ごろ（時間枠 3 時間のうち約 1 時間）",
        "noteJa": ("美術の見本03 修正の回 1（Q31「现在整个贴图的感觉也还是不对，特别是当前的海浪浪尖的那一部分」）。rules_check.json で落ちた T4（冠が原画視点のほかの"
                   "どの視点でも枠の 0.5% より多く見える）と、批評の必ず直す所（順位 1〜8）のうち入るだけを直し、3 つの変種のすべての視点を描き直し、規則を測り直した。"
                   "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止だけ。美術が届いたかは利用者が決める（Q29・Q30）。"
                   "目で見た良し悪しは道具で、閉じる条件にしない。"),
        "commands_ja": [
            "py -3.10 -B Tools/GWWaveGen/as03/fix1_crown.py --mode OUT   # 泡の皮（kind 5）と唇の縁から垂れる滴（kind 3）。B1 の冠はそのまま",
            "py -3.10 -B Tools/GWWaveGen/as03/fix1_crown.py --mode IN    # V3：原画の空に出る皮をなめらかに沈め、空に出る滴を外す",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V1 OUT sculpt views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V2 OUT flat views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V3 IN sculpt views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V1_ids OUT sculpt views,crest,tt,ids",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V3_ids IN sculpt views,crest,tt,ids",
            "bash Tools/GWWaveGen/as03/fix1_render.sh V1_cmp OUT sculpt cmp -as03Cmp \"front:30:15:72:34;right45:-15:28:72:34;left45:75:28:72:34;back:210:18:72:34;top:30:85:95:40\"",
            "RB=…/sample03/fix01/render LG=…/sample03/fix01/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh V3 V1 V2",
            "cp rules_check.json rules_check_before_fix.json   # 前の結果を残す（SHA-256 は下）",
            "py -3.10 -B Tools/GWWaveGen/as03/fix1_rules.py    # rules_check.json を上書き（asm_rules.py をそのまま使い、描画の場所を fix01 へ。滴の検査と批評の測りの記録を足す）",
            "py -3.10 -B Tools/GWWaveGen/as03/fix1_sheets.py all   # 並べ図（fix01/sheets）と利用者だけの比べの図（user_only/sculpture_vs_V1_fix01.png）",
            "py -3.10 -B Tools/GWWaveGen/as03/fix1_record.py"],
        "fixed_ja": {
            "T4（規則）": "冠が見える割合の最小：V1 %.2f%% → %.2f%%、V2 %.2f%% → %.2f%%、V3 %.2f%% → %.2f%%（基準 0.5%% より多い）。T4 は 3 つとも 不合 → 合。" % (
                100 * t4b["crown_visibility"]["V1"]["min"]["frac"], 100 * t4["crown_visibility"]["V1"]["min"]["frac"],
                100 * t4b["crown_visibility"]["V2"]["min"]["frac"], 100 * t4["crown_visibility"]["V2"]["min"]["frac"],
                100 * t4b["crown_visibility"]["V3"]["min"]["frac"], 100 * t4["crown_visibility"]["V3"]["min"]["frac"]),
            "必ず直す所 1（頂が滑らかな白い面で、冠が白の上の白）": "前の白の地を、泡の瘤の皮で覆った（指の背の列を互い違いに重ね、間は谷。瘤 0.75〜1.1 m おき）。滑らかな白い地は前から見えなくなった（見える白のうち冠の割合 0.09〜0.16 → 0.85〜0.97、V1）。",
            "必ず直す所 2（指が寝て見える）": "一部だけ。泡の皮の指の背は頂から唇の先へ前・下へ流れる。B1 の寝た手は皮に半ば埋もれる。B1 の手そのもの（根元の向き）は変えていない。",
            "必ず直す所 3（垂れる縁が無い）": "唇の縁に立体の滴を垂らした（OUT 42・IN 19 本、間隔の中央値 0.93・0.81 m、長さ 0.96・0.83 m、幅 0.38・0.37 m。彫刻の写真の読み 0.8 m・0.6〜1.45 m・0.30〜0.48 m）。滴は泡の指の列の先に置いた。白の舌は皮が覆い、盛り上がった釉の流れになった。",
            "必ず直す所 4（白が灰色・稜が平らな縞）": "材質の値だけで：環境の空・海の照り返し・補いの光を明るく、回り込みを広く。白の明るさの中央値：波頭 90° 151 → 209、座席 136 → 182（彫刻の白の中 214〜218）。藍の艶と映り込みの空を強く。",
            "必ず直す所 5（とげ・穴・z の争い）": "穴（白の中の暗い冠の塊）は 0 になった（皮が覆った）。とげ（B1 の冠の役の利用者の爪 48 本の鋭い先）は残る（下の not_fixed）。",
            "必ず直す所 6（背・横から冠が弱い）": "頂の線に泡の瘤 11 個（高さ 0.65〜1.40 m、中央値 0.91 m）を置き、背の輪郭に出した（彫刻の背の写真：太く短い指 約 10 本）。冠の見える割合の最小は 1.2〜1.5%。",
            "必ず直す所 7（溝の青が明るい）": "溝のコバルトの青を (66,102,158) → (51,84,135)（S1 の光の当たるコバルト (59,92,145) へ）。",
            "必ず直す所 8（V2 の冠が空に溶ける）": "FLAT の冠の色の黄みを抜いた（_MeshTint・_MeshMizuiro）。冠と空の色の差 ΔE76 の中央値 8.7 → 20.0（原画視点）。"},
        "not_fixed_ja": [
            "とげ（必ず直す所 5 の一部）：B1 の冠の役の利用者の爪 48 本は鋭い鉤のまま。C2（利用者の模型の水準：鋭い先）と、Q29・S1（波頭と唇は太く丸い指）が食い違う。"
            "C3（100 本を原画の位置へ戻す）の数に入るので外せない。批評の勧め（C2 は面の内・近い海の 35 本だけに当てる）にするかは進行役が決めて記録する。",
            "寝た指（必ず直す所 2）：B1 の手の根元の向き（法線との角 70°）は変えていない。手を作り直すと T4 の数（S1 の範囲）と G2（V3）の測り直しが要り、1 回の修正に入らなかった。",
            "背の注ぎ釉の波紋（批評の 11、必ず直す所の外）、光る主役波と平らな海の差・裾の境のぼけ（批評の 10、見本の範囲の外）、面の内の爪が屑に見える（批評の 12）は手を付けていない。",
            "座席から見た面は、溝の青を暗くしても、まだ等間隔の縞に読める（稜の形は B2 の彫りのまま）。"],
        "decisions_ja": [
            "泡の皮・滴は B1 の冠とは別のメッシュ（fix01/crown/<OUT|IN>/fix1_foam・fix1_drips）にし、描画の道具の -as03Crown に並べて渡した（冠の画の色・材質は同じ）。理由：B1 の冠・手・利用者の爪（T4 の数・C3）を変えずに足せる。",
            "泡の皮は面の座標 (u, w) の瘤の場で、彫りの面の頂点を法線の向きへ持ち上げた（彫りの面そのものは変えていない）。理由：G1・S4・T1（彫りの面の測り）を変えない。2 秒で作れる。最初の格子の並べ方は松かさ・うろこに、長い鎖は等間隔の縞に見えたので、3〜6 個の短い指を互い違いに重ねた。",
            "頂の線の泡の瘤と滴は T4 の「指の先・手」の数に入れない（泡の皮の一部・垂れる縁）。代わりに T4 に滴の下位の検査（間隔・長さ・幅）を足した（批評の提案：数を頂の線と唇の縁の線に分ける）。範囲は批評が彫刻の正面の写真から読んだ数（±25%）で、進行役が変えてよい。",
            "V3（IN）の皮は、原画の空（2 px より内）に出て主役波に隠れない頂点の印を面の上で約 1 m にならし、なめらかに沈めた。最初の、外れた頂点と周り 3 輪だけを沈める版は、原画視点で皮の崖が暗い斑に見えた。G2 は V3 で 2.741・3.553・3.442・3.629・3.532 px（4 以下）。",
            "頂の線の瘤は鎖の頭の 22%（11 個）。32%（26 個）では背の輪郭に等間隔の突起の列（背びれ）に読めた。",
            "材質はシェーダーのコードを変えず、値の表（fix1_sculpt_params.txt・fix1_flat_params.txt）だけを替えた。理由：G1 のシェーダーの SHA-256 の確かめをそのまま通す。"],
        "rules": {"before": {"path": rel(S3 + "/rules_check_before_fix.json"), "sha256": sha(S3 + "/rules_check_before_fix.json"), "verdicts": rb["summary"]["verdicts"]},
                  "after": {"path": rel(S3 + "/rules_check.json"), "sha256": sha(S3 + "/rules_check.json"), "verdicts": rc["summary"]["verdicts"],
                            "by_variant": rc["summary"]["by_variant"]}},
        "renders": rep,
        "crown_parts_sha256": parts,
        "tools_sha256": tools,
        "sheets_sha256": sheets,
        "user_only": {"sheet": rel(S3 + "/user_only/sculpture_vs_V1_fix01.png"), "sha256": sha(S3 + "/user_only/sculpture_vs_V1_fix01.png"),
                      "note_ja": "写真は組み立ての一時の写し（user_only/ref_asm）をそのまま使った。新しい写真の写しは作っていない。リポジトリ・Docs へ入れない。"},
        "kept_unchanged_ja": "Unity のシーン・材質・スクリプト・シェーダー（AS03 の 3 つ、AS03AsmRender.cs）、見本01・02、B1 の冠（crown/OUT・IN）、B2 の彫りの面、白の印は変えていない。"
                             "描画のたびに守るファイルの SHA-256 が同じ（protectedUnchanged=True）。参照モデルの OBJ は読んでいない。git の add・commit・push はしていない。",
    }
    out = FIX + "/fix1_run.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("FIX1_RECORD_DONE", out, sha(out))


if __name__ == "__main__":
    main()
