# -*- coding: utf-8 -*-
"""仕上げ35（数量と負荷）の記録：負荷の計測器と通しの走りの数え直し（作る部の pl35_perf_summary.py・pl35_formation.py と別の読み）、性能の表の図、
metrics.json・run.json、証拠の写し（Docs/Evidence/Polish/35）。

数え直しの読み（作る部と変える所）：
  ・最大密度の区間：フレームの間隔を FrameTimingManager の開始時刻の差ではなく、Unity の unscaledDeltaTime（PL35PerfProbe の dt）で数える（先頭 8 件を除く）。
  ・形成の全区間：設計50 の frames.csv の udt ではなく、実時間の列 real の差で数える（形成で時計が動いているコマが続く所）。
両方の読みの値を metrics.json の recount に書く。HMD の実機ではない（PS VR2 は未導入）。RTX 3080・i7-12700K の PC の代理（対象 PC の RTX3060 ではない）。
使い方：py -3.10 -B Tools/GWWaveGen/pl35/pl35_record.py
"""
import csv
import hashlib
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/35"
EV = REPO + "/Docs/Evidence/Polish/35"
RUNS = B + "/runs"
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"
PERF_TAGS = ["f1_fast1", "f1_legacy1", "f1_fast2", "f1_legacy2"]
AUTO_TAGS = ["auto_pl33r01_1", "auto_pl35_1", "auto_pl33r01_2", "auto_pl35_2", "auto_ds50_1"]
AFTER, BEFORE = ["f1_fast1", "f1_fast2"], ["f1_legacy1", "f1_legacy2"]
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl35")
import pl35_perf_summary as PS  # noqa: E402
import pl35_formation as PF  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def jd(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)


def r(v, n=3):
    return None if v is None else round(float(v), n)


def probe(tag):
    return jl(os.path.join(RUNS, tag, "pl35perf_%s.json" % tag))


def recount_cond(c):
    dt = np.array(c.get("dt") or [], dtype=np.float64)[8:] * 1000.0
    if len(dt) == 0:
        return None
    return {"fps_mean_dt": r(1000.0 / dt.mean(), 1), "p95_ms_dt": r(np.percentile(dt, 95)), "max_ms_dt": r(dt.max()), "over_33_3_frac_dt": r((dt > 33.3).mean(), 4)}


def recount_formation(tag):
    rows = list(csv.DictReader(open(os.path.join(RUNS, tag, "frames.csv"), encoding="utf-8")))
    real = np.array([float(x["real"]) for x in rows])
    keep = np.array([x["phase"] == "Formation" and x["clockRunning"] == "1" and x["flowPaused"] == "0" for x in rows])
    iv = np.diff(real) * 1000.0
    sel = keep[1:] & keep[:-1]
    v = iv[sel]
    return {"intervals": int(sel.sum()), "fps_mean_real": r(1000.0 / v.mean(), 1), "p95_ms_real": r(np.percentile(v, 95)), "over_33_3_frac_real": r((v > 33.3).mean(), 4)}


def font(s, b=False):
    return ImageFont.truetype(FONT_B if b else FONT_R, s)


def cv(S, tags, key, k, mode):
    v = [S[t]["conditions"][key].get(k) for t in tags if S[t]["conditions"].get(key) and S[t]["conditions"][key].get(k) is not None]
    if not v:
        return None
    return min(v) if mode == "min" else max(v)


def fig_perf(S, F, out):
    im = Image.new("RGB", (1920, 1080), (250, 248, 242))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 62], fill=(30, 36, 52))
    d.text((16, 8), "仕上げ35 最大密度の区間（t 11〜12 s の繰り返し）と形成の全区間のフレームの時間：Release のプレイヤー（RTX 3080・i7-12700K の代理。RTX3060・PS VR2 ではない）",
           font=font(21, True), fill=(255, 255, 255))
    d.text((16, 38), "前＝--pl35legacy（仕上げ33修正01 の爪の縁の線の道）、後＝修正の回 1（PL35ClawOutlineFast）。同じ exe を交互に 2 回ずつ。表の値は 2 回の悪い方（fps は小さい方、ms・回数は大きい方）。",
           font=font(15), fill=(220, 220, 220))
    cols = ["条件", "fps 平均", "間隔 p95 ms", "33.3 ms 超", "CPU 主 p50 ms", "GPU p95 ms", "爪の段 ms", "ごみ集め／8 s"]
    xs = [16, 520, 720, 920, 1110, 1310, 1510, 1700]
    y = 76
    for x, c in zip(xs, cols):
        d.text((x, y), c + ("" if c == "条件" else "（前→後）"), font=font(15, True), fill=(20, 30, 60))
    y += 30
    names = [("desk1080_painting", "1920×1080・原画視点"), ("desk1080_seat", "1920×1080・座席 v1"), ("exp_hmd", "体験の PC の画面（HMD Camera）"),
             ("proxy_stereo_hmd", "立体の代理（HMD Camera、2064×2208×2・4×MSAA）"), ("proxy_stereo_seat", "立体の代理（座席 v1）"),
             ("exp_hmd_no_boatwater", "体験の画面・船用水面データの作り直しを止める"), ("proxy_stereo_hmd_no_boatwater", "立体の代理・作り直しを止める"),
             ("exp_hmd_no_claws", "体験の画面・爪の段と爪を切る"), ("ps_static_all", "立体の代理・時刻を止める（描画だけ）")]
    for key, ja in names:
        def pair(k, mode, fmt):
            a, b = cv(S, BEFORE, key, k, mode), cv(S, AFTER, key, k, mode)
            return "%s → %s" % (fmt % a if a is not None else "—", fmt % b if b is not None else "—")

        def frac(tags):
            return max(S[t]["conditions"][key].get("over_33_3ms", 0) / max(1, S[t]["conditions"][key].get("n_intervals", 1)) for t in tags) * 100
        row = [ja, pair("fps_mean", "min", "%.1f"), pair("interval_p95_ms", "max", "%.2f"), "%.0f%% → %.0f%%" % (frac(BEFORE), frac(AFTER)),
               pair("cpuMain_p50_ms", "max", "%.2f"), pair("gpu_p95_ms", "max", "%.2f"), pair("msClaws_p50", "max", "%.2f"), pair("gc_gen0", "max", "%d")]
        for x, c in zip(xs, row):
            d.text((x, y), c, font=font(15), fill=(30, 30, 30))
        y += 30
    y += 8
    d.text((16, y), "形成の全区間（体験の通し＝設計50 の自動の試し --ds50auto main、1920×1080 の窓。時計が動いているコマだけ。形成の中の停止の試しの間は除く）",
           font=font(17, True), fill=(20, 30, 60))
    y += 30
    for rr in F["runs"]:
        lab = ("前（仕上げ33修正01 の exe）" if "pl33r01" in rr["run"] else "参考（設計50 の exe、仕上げの前）" if "ds50" in rr["run"] else "後（仕上げ35 の exe）") + " " + rr["run"]
        d.text((30, y), "%s：fps 平均 %.1f・間隔 p95 %.1f ms・p99 %.1f ms・33.3 ms 超 %.0f%%・CPU 主 p50 %.1f ms・GPU p95 %.2f ms" % (
            lab, rr["fps_mean"], rr["interval_p95_ms"], rr["interval_p99_ms"], rr["over_33_3ms_frac"] * 100, rr["cpuMain_p50_ms"], rr["gpu_p95_ms"]), font=font(15), fill=(30, 30, 30))
        y += 24
        d.text((60, y), "大波の時刻 0〜11 s の 1 s ごとの間隔の平均（ms）：" + "  ".join("%s:%.0f" % (k, v["interval_mean_ms"]) for k, v in rr["by_wave_s"].items()), font=font(13), fill=(70, 70, 70))
        y += 24
    y += 6
    st = S["f1_fast1"]["conditions"]
    g = lambda k: st[k]["gpu_p95_ms"]
    d.text((16, y), "描画の時間の切り分け（立体の代理、時刻 t 11.5 s で止める、GPU p95）：全部 %.2f ms ／ 海を切る %.2f（海の分 %.2f）／ 主役波を切る %.2f（%.2f）／ 爪を切る %.2f（%.2f）／ 飛沫を切る %.2f（%.2f）" % (
        g("ps_static_all"), g("ps_static_no_sea"), g("ps_static_all") - g("ps_static_no_sea"), g("ps_static_no_hero"), g("ps_static_all") - g("ps_static_no_hero"),
        g("ps_static_no_claws"), g("ps_static_all") - g("ps_static_no_claws"), g("ps_static_no_spray"), g("ps_static_all") - g("ps_static_no_spray")), font=font(15), fill=(30, 30, 30))
    y += 34
    bw = [S[t]["conditions"]["exp_hmd"].get("boatWater_rebuild_ms_mean") for t in PERF_TAGS]
    lines = ["・CPU の主スレッドの律速は、座席の船の段（seat_boat）の水の問い合わせが毎コマ起こす船用水面データの作り直し（DS43BoatWater、1 回 %.1f〜%.1f ms）。設計43 限界 11・段階9確認 F9-4 で仕上げ43 の項目。" % (min(bw), max(bw)),
             "・それを止めると、最大密度の区間は 1920×1080 で約 320 fps（間隔 p95 3.7〜3.9 ms）、立体の代理で約 300 fps（4.1〜4.2 ms）。その時の CPU 主スレッド約 3.0 ms のうち爪の段が約 2.4 ms（90 Hz の 11.1 ms の約 2 割）。",
             "・GPU：時刻を止めた立体の代理は p95 2.15 ms（8.9 ms の内）。CPU 律速の時の FrameTiming の GPU p95（11〜14 ms）は、止めた時・作り直しを止めた時（3.2〜3.4 ms）よりずっと大きく、CPU の待ちを含むとみる（記録）。",
             "・修正の回 1：爪の縁の線の写しから毎コマ 1.26 MB の配列の写しをなくした（線のメッシュの頂点・法線の差 0）。作り直しを止めた時のごみ集めは 8 秒に 106〜113 回 → 0 回、間隔の最大 6.5〜7.7 ms → 5.1〜5.7 ms（体験の画面と立体の代理）。"]
    for ln in lines:
        d.text((16, y), ln, font=font(15), fill=(80, 30, 30))
        y += 26
    im.save(out)
    return out


def main():
    os.makedirs(EV, exist_ok=True)
    S = {}
    for t in PERF_TAGS + ["f0_perf2"]:
        dd = probe(t)
        S[t] = {"conditions": {c["name"]: PS.cond_stats(c) for c in dd["conditions"]}, "legacy": dd.get("legacy"), "fastOutlineActive": dd.get("fastOutlineActive"),
                "selfCheckT": dd.get("selfCheckT"), "selfCheckMaxVertexDiff": dd.get("selfCheckMaxVertexDiff"), "selfCheckMaxNormalDiff": dd.get("selfCheckMaxNormalDiff"),
                "device": dd["device"], "cpu": dd["cpu"], "graphicsApi": dd["graphicsApi"], "isDebugBuild": dd["isDebugBuild"], "screen": [dd["screenWidth"], dd["screenHeight"]],
                "clawVertices": dd["clawVertices"], "clawTriangles": dd["clawTriangles"], "clawItems": dd["clawItems"], "spray": [dd["sprayCount0"], dd["sprayCount1"]],
                "reachRealS": dd["reachRealS"], "waveStartS": dd["waveStartS"], "handoverS": dd["handoverS"], "stagesAfter": dd["stagesAfter"],
                "recount_dt": {c["name"]: recount_cond(c) for c in dd["conditions"]}}
    F = {"runs": [PF.one(os.path.join(RUNS, t)) for t in AUTO_TAGS]}
    jd(B + "/measure/formation_all.json", {"rule_ja": PF.__doc__.strip().split("\n\n")[1], "runs": F["runs"]})
    FR = {t: recount_formation(t) for t in AUTO_TAGS}
    fig = fig_perf(S, F, EV + "/fig_pl35_perf_table.png")
    copies = {}

    def cp(src, dst):
        shutil.copy2(src, os.path.join(EV, dst))
        copies[dst] = sha(os.path.join(EV, dst))
    for f in sorted(os.listdir(B + "/evidence")):
        if f.endswith(".png") or f.endswith(".json"):
            cp(os.path.join(B + "/evidence", f), f)
    for f in ("pl35_ds35_2x2_painting_30fps.mp4", "pl35_ds35_2x2_seat_30fps.mp4", "pl35_caption_fix.json"):
        cp(os.path.join(B + "/caption", f), f)
    cp(B + "/caption/frame_painting_t065.png", "fig_pl35_ds35_2x2_painting_t065.png")
    cp(B + "/caption/frame_seat_t090.png", "fig_pl35_ds35_2x2_seat_t090.png")
    for src, dst in ((B + "/release/unity/pl35_build.json", "release_build.json"), (B + "/setup/pl35_setup_fix1.json", "setup.json"), (B + "/bench/pl35_claw_bench.json", "pl35_claw_bench.json"),
                     (B + "/r_after/pl28u_regress.json", "pl28u_regress.json"), (B + "/r_after/pl33_render_report.json", "render_report.json"), (B + "/measure/formation_all.json", "pl35_formation.json")):
        cp(src, dst)
    jd(EV + "/pl35_perf.json", {"rule_ja": PS.__doc__.strip().split("\n\n")[1], "runs": S})
    copies["pl35_perf.json"] = sha(EV + "/pl35_perf.json")
    ev23 = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        m = jl(B + "/eval23/off_%s/metrics.json" % c)
        it = m["items"] if isinstance(m["items"], list) else list(m["items"].values())
        cnt = {}
        for x in it:
            s = str(x.get("status") or x.get("verdict") or x.get("result"))
            cnt[s] = cnt.get(s, 0) + 1
        ev23[c] = cnt
    diffs = jl(B + "/evidence/pl35_sheet_diffs.json")["stats"]
    ed = [v for k, v in diffs.items() if v and (k.startswith("views") or k.startswith("tt"))]
    cap = jl(B + "/caption/pl35_caption_fix.json")
    bench = jl(B + "/bench/pl35_claw_bench.json")
    build = jl(B + "/release/unity/pl35_build.json")
    desk = ["desk1080_painting", "desk1080_seat", "exp_hmd"]
    fps_after = [S[t]["conditions"][k]["fps_mean"] for t in AFTER for k in desk]
    p95_after = [S[t]["conditions"][k]["interval_p95_ms"] for t in AFTER for k in desk]
    hero_mib = sum(f["bytes"] for f in build["data"] if "hero_pkg" in f["rel"]) / 2 ** 20
    sea_mib = sum(f["bytes"] for f in build["data"] if "Polish/30/sea" in f["rel"]) / 2 ** 20
    claws_mib = sum(f["bytes"] for f in build["data"] if "33r01/fix01/claws" in f["rel"]) / 2 ** 20
    fa = [x for x in F["runs"] if "pl35" in x["run"]]
    met = {
        "schema": "GreatWave.Polish35.metrics/1", "group": "仕上げ35（設計35 数量と負荷）", "date": "2026-10-02",
        "evidence_kind_ja": "Release（Development でない）の Windows プレイヤーを PC（RTX 3080・i7-12700K、Direct3D11、1920×1080 の窓、垂直同期なし）で動かした実測と、Unity 6000.4.3f1 の PC オフスクリーン描画。HMD 実機ではない（PS VR2 は未導入）。対象 PC の RTX3060 ではない（借りていない）＝代理測定。",
        "items": [
            {"plan_line": "RTX3060 を借りられれば同じプレイヤーで実測、借りられなければ代理のまま「代理測定」と明記。81・112・199 の本判定", "user_words": False,
             "result_ja": "RTX3060 は借りていないので代理測定（RTX 3080）。設計35 の DS35Perf.exe は設計34 の古い場面（爪 148 本・飛沫 186 個・DS27 の材質）を描くので、体験の場面の写し PL35_Release.unity に計測器 PL35PerfProbe を置いて測り直した。81・112・199 は代理で不合格（記録）。本判定（RTX3060・PS VR2）は保留。"},
            {"plan_line": "2×2 の動画の説明の「最初の爪 3.6 s」の直し（F6-4）", "user_words": False,
             "result_ja": "説明を「データの最初の爪（根元から伸び始めるコマ）」と「この視点の画面で V1 と違って見え始める時刻」に分けた 2×2 の動画を作り直した（原画視点 V3 6.8 s・V2 8.9 s、座席 V3 8.9 s・V2 9.4 s）。設計35 の証拠は書き換えていない。",
             "values": cap["views"]}],
        "backlog": {
            "b81": {"criterion_ja": "1920×1080 で平均 ≥ 30 fps・95% のフレーム ≤ 33.3 ms（RTX3080 で代理測定）",
                    "value_ja": "最大密度の区間 t 11〜12 s（後、原画視点・座席 v1・体験の画面 × 2 回）：平均 %.1f〜%.1f fps、間隔 p95 %.2f〜%.2f ms" % (min(fps_after), max(fps_after), min(p95_after), max(p95_after)),
                    "verdict_ja": "代理で不合格（95% ≤ 33.3 ms を満たさず、平均は 30 fps の前後）。原因は船用水面データの作り直し（仕上げ43）。本判定（RTX3060）は保留"},
            "b112": {"criterion_ja": "同上（設計35 と同じ読み）", "value_ja": "同上", "verdict_ja": "同上"},
            "b199": {"criterion_ja": "波・爪・線・飛沫・船が同時に映る形成の全区間で平均 ≥ 30 fps・95% ≤ 33.3 ms（3080 で代理測定）。VR 代理の GPU p95 ≤ 8.9 ms",
                     "value_ja": "形成の全区間（後 2 回）：平均 %.1f・%.1f fps、間隔 p95 %.1f・%.1f ms。立体の代理の GPU p95：時刻を止めて %.2f ms、作り直しを止めて %.2f〜%.2f ms、CPU 律速のまま %.2f〜%.2f ms" % (
                         fa[0]["fps_mean"], fa[1]["fps_mean"], fa[0]["interval_p95_ms"], fa[1]["interval_p95_ms"], S["f1_fast1"]["conditions"]["ps_static_all"]["gpu_p95_ms"],
                         cv(S, AFTER, "proxy_stereo_hmd_no_boatwater", "gpu_p95_ms", "min"), cv(S, AFTER, "proxy_stereo_hmd_no_boatwater", "gpu_p95_ms", "max"),
                         cv(S, AFTER, "proxy_stereo_hmd", "gpu_p95_ms", "min"), cv(S, AFTER, "proxy_stereo_hmd", "gpu_p95_ms", "max")),
                     "verdict_ja": "フレームの時間は代理で不合格（CPU 律速、船用水面データの作り直し）。GPU の描画の仕事は 8.9 ms の内（CPU 律速の時の FrameTiming の GPU p95 は CPU の待ちを含むとみて記録）。PS VR2 の実機は保留"},
            "acceptance_81_112_other": {
                "keypose_le_512MiB_ja": "主役波の keypose（hero_pkg）%.1f MiB ≤ 512 MiB。周りの海の keypose %.1f MiB、爪の並び %.1f MiB（コマの表 504.5 MiB）は別に持つ" % (hero_mib, sea_mib, claws_mib),
                "mock_line_diff_ja": "「Mock の両眼の線の画素の差 <10%」は Mock では測っていない。2 カメラの代理の左右の眼の暗い画素（輝度 < 60）の数の差は 0.4〜1.8%（参考。線の ID の数ではない）"}},
        "fix_round_1": {
            "what_ja": "PL35ClawOutlineFast：共通時計の爪の段を同じ規則（仕上げ32 の PL32ClawDriver の飛ばし）の段で置き換え、縁の線の頂点を DS34ClawPlayer の今の配列から写さずに入れる（DS34ClawPlayer.Current の 1.26 MB の写しをなくす）。法線は今までと同じ RecalculateNormals。--pl35legacy で前の道",
            "selfcheck_t": S["f1_fast1"]["selfCheckT"], "selfcheck_max_vertex_diff": [S[t]["selfCheckMaxVertexDiff"] for t in AFTER], "selfcheck_max_normal_diff": [S[t]["selfCheckMaxNormalDiff"] for t in AFTER],
            "gc_per_8s_no_boatwater_before": [S[t]["conditions"]["exp_hmd_no_boatwater"]["gc_gen0"] for t in BEFORE],
            "gc_per_8s_no_boatwater_after": [S[t]["conditions"]["exp_hmd_no_boatwater"]["gc_gen0"] for t in AFTER],
            "claws_stage_ms_p50_no_boatwater_before": [S[t]["conditions"]["exp_hmd_no_boatwater"]["msClaws_p50"] for t in BEFORE],
            "claws_stage_ms_p50_no_boatwater_after": [S[t]["conditions"]["exp_hmd_no_boatwater"]["msClaws_p50"] for t in AFTER],
            "interval_max_ms_no_boatwater_before": [S[t]["conditions"]["exp_hmd_no_boatwater"]["interval_max_ms"] for t in BEFORE],
            "interval_max_ms_no_boatwater_after": [S[t]["conditions"]["exp_hmd_no_boatwater"]["interval_max_ms"] for t in AFTER],
            "verdict_ja": "ごみ集めとフレームの揺れは減ったが、81・112・199 の判定は変わらない（律速は船用水面データの作り直し）"},
        "attribution": {
            "boat_water_rebuild_ms_mean": [S[t]["conditions"]["exp_hmd"].get("boatWater_rebuild_ms_mean") for t in PERF_TAGS],
            "stage_ms_p50_exp_hmd_after": {k: S["f1_fast1"]["conditions"]["exp_hmd"].get(k) for k in ("msSeek_p50", "msWater_p50", "msBoatWater_p50", "msWhite_p50", "msClaws_p50", "msSpray_p50")},
            "gpu_static_stereo_p95": {k: S["f1_fast1"]["conditions"][k]["gpu_p95_ms"] for k in ("ps_static_all", "ps_static_no_sea", "ps_static_no_hero", "ps_static_no_claws", "ps_static_no_spray")},
            "note_ja": "座席の船の段（seat_boat）の水の問い合わせ（HeightAt → Sync）が作り直しを起こすので、boat_water の段の時間は 0.001 ms で、作り直しの時間は DS43BoatWater.RebuildMsTotal から読んだ"},
        "claw_bench_editor": bench["rows"],
        "data_mib": {"claws": round(claws_mib, 1), "sea": round(sea_mib, 1), "hero_pkg": round(hero_mib, 1), "total": round(build["dataBytes"] / 2 ** 20, 1), "mono_heap_mb_player": 1200},
        "regression": {
            "editor_views_tt_images": len(ed), "editor_changed_pixels_total": sum(v["changed_gt0"] for v in ed), "full_renders_byte_identical": True, "videos_byte_identical": True,
            "evaluator23": ev23,
            "gates_ja": "78 2.741・130 3.5815・131 3.4419・132 σ12 3.5789（爪なし 3.5576）・72 σ12 p95 3.9059（爪なし 3.8507）。仕上げ33修正01 と同じ値（描画が画素まで同じ）。CP1 は 2.772・1.968・1.814・1.326・1.558、26修正01 は 1.641・1.953・1.798・1.574・1.723",
            "player_painting_view_changed_pixels": diffs.get("player/desk1080_painting")},
        "recount": {"probe_dt": {t: S[t]["recount_dt"] for t in PERF_TAGS}, "formation_real": FR},
        "copies_sha256": copies,
    }
    jd(EV + "/metrics.json", met)
    files = ["Unity/Assets/GreatWave/Polish35/Scripts/PL35PerfProbe.cs", "Unity/Assets/GreatWave/Polish35/Scripts/PL35ClawOutlineFast.cs", "Unity/Assets/GreatWave/Polish35/Editor/PL35Setup.cs",
             "Unity/Assets/GreatWave/Polish35/Editor/PL35ReleaseBuild.cs", "Unity/Assets/GreatWave/Polish35/Editor/PL35ClawBench.cs", "Unity/Assets/GreatWave/Polish35/Scenes/PL35_Release.unity",
             "Unity/Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity", "Tools/GWWaveGen/pl35/pl35_run_unity.ps1", "Tools/GWWaveGen/pl35/pl35_run_player.ps1", "Tools/GWWaveGen/pl35/pl35_run_render.sh",
             "Tools/GWWaveGen/pl35/pl35_perf_summary.py", "Tools/GWWaveGen/pl35/pl35_formation.py", "Tools/GWWaveGen/pl35/pl35_caption_fix.py", "Tools/GWWaveGen/pl35/pl35_sheets.py", "Tools/GWWaveGen/pl35/pl35_record.py"]
    runs = {}
    for t in PERF_TAGS + AUTO_TAGS + ["f0_perf1", "f0_perf2"]:
        lj = os.path.join(RUNS, t, "launch.json")
        if os.path.exists(lj):
            l = jl(lj)
            runs[t] = {k: l.get(k) for k in ("mode", "exe", "exeSha256", "args", "utcStart", "seconds", "exitCode")}
    run = {"schema": "GreatWave.Polish35.run/1",
           "tools": {"unity": "6000.4.3f1", "python": "3.10", "numpy": np.__version__, "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build", "gpu": S["f1_fast1"]["device"], "cpu": S["f1_fast1"]["cpu"]},
           "code_sha256": {f: sha(os.path.join(REPO, f)) for f in files if os.path.exists(os.path.join(REPO, f))},
           "release_exe": {"path": build["playerPath"], "sha256": build["exeSha256"], "scene": build["scene"], "sceneSha256": build["sceneSha256"], "dataBytes": build["dataBytes"], "dataFiles": build["dataFiles"]},
           "claw_files": [{"rel": f["rel"], "bytes": f["bytes"], "sha256": f["sha256"]} for f in build["data"] if "33r01/fix01/claws" in f["rel"]],
           "player_runs": runs,
           "commands_ja": [
               "powershell -File Tools/GWWaveGen/pl35/pl35_run_unity.ps1 -Method GreatWave.Polish35.EditorTools.PL35Setup.BuildScenes -Log setup_fix1 -Extra \"-pl35fix 1\"",
               "powershell -File Tools/GWWaveGen/pl35/pl35_run_unity.ps1 -Method GreatWave.Polish35.EditorTools.PL35ReleaseBuild.BuildAll -Log release_build_fix1",
               "powershell -File Tools/GWWaveGen/pl35/pl35_run_player.ps1 -Tag f1_fast1 -Mode perf（f1_legacy1 は -Extra --pl35legacy。f1_fast2・f1_legacy2 と交互）",
               "powershell -File Tools/GWWaveGen/pl35/pl35_run_player.ps1 -Tag auto_pl35_1 -Mode auto（auto_pl33r01_* は -Exe Unity/Build/Polish/33r01/release/player/GreatWave50.exe。交互）",
               "powershell -File Tools/GWWaveGen/pl35/pl35_run_unity.ps1 -Method GreatWave.Polish35.EditorTools.PL35ClawBench.Run -Log bench1",
               "bash Tools/GWWaveGen/pl35/pl35_run_render.sh r_after views,tt,t28,full,video",
               "py -3.10 -B Tools/PaintingTruth/evaluate.py（4 組、出力 Unity/Build/Polish/35/eval23）・py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/35/r_after --kstar rec",
               "py -3.10 -B Tools/GWWaveGen/pl35/pl35_sheets.py ／ pl35_caption_fix.py ／ pl35_record.py"]}
    jd(EV + "/run.json", run)
    print("fig", fig)
    print(json.dumps(met["backlog"], ensure_ascii=False, indent=1))
    print("recount formation", FR)
    print("recount dt fast1", {k: v for k, v in S["f1_fast1"]["recount_dt"].items() if k in ("exp_hmd", "desk1080_painting", "exp_hmd_no_boatwater")})


if __name__ == "__main__":
    main()
