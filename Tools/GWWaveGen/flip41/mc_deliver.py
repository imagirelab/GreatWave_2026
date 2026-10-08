# -*- coding: utf-8 -*-
"""FLIP41 まとめ（10/9）：方法の確かめ（Q41）の証拠を Docs/Evidence/FLIPMethodCheck へまとめる（py -3.10、numpy は使わない）。
新しい流体計算・描画はしない。
- 図は Unity/Build/FLIP41/verify/figs（Git 対象外）から名前を変えて写す（中身は同じ。SHA-256 を copies.json に書く）。
- 計画（plan_ja.md、走らせる前に決めた判定の幅）・全計算の表・数の JSON は、中身を変えずに写す。
- 調べの 2 つ（基準の問題・風）は Docs/Research へ写し、リンクの相対パスと、個人の一時置き場のパス 1 か所だけを直す（直した所は copies.json）。
- metrics.json：verify/summary.json から、計算ごとの主な数と判定（決めた幅に入ったか）を写す。
- run.json：道具・場面・計算の記録（runs.jsonl）の SHA-256、起動の数と時間、キャッシュの数と大きさ（水面の記録 hf_c*.npz は SHA-256 も）。
使い方: py -3.10 -B mc_deliver.py
"""
import os, sys, re, json, glob, shutil, hashlib, datetime, platform, collections

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
B = ROOT + "/Unity/Build/FLIP41/"
V = B + "verify/"
EV = ROOT + "/Docs/Evidence/FLIPMethodCheck/"
RS = ROOT + "/Docs/Research/"
TOOLS = ROOT + "/Tools/GWWaveGen/flip41/"
SCENE = ROOT + "/Houdini/FLIP41/v_tank.hiplc"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


FIGS = [
    ("mc_1_B1_summary.png", "figs/B1_summary.png",
     "平らな底の規則波の全体：速さの誤差（左上）、同じ周期 7 s の速さと水深（右上、線＝線形の分散の式、点＝FLIP）、3 波長の高さの減り（左下）、造波の帯の出口の高さ（右下）。色＝粒子の大きさ（青 1 m・赤 0.5 m・橙 0.25 m・黒 0.125 m。黒は凡例にない）。塗りつぶしは振幅/格子 0.45 以上"),
    ("mc_2_old_setting_1m.png", "figs/snap_dp1.png",
     "今までの細かさ（粒子 1 m・格子 2 m、FLIP39 E と同じ）の水面と、線形の理論の波（点線）。周期 7 s・5 s の低い波は遅れて消え、高さ 2.97 m の波も 3 波長で 33 % 減る"),
    ("mc_3_h10_convergence.png", "figs/snap_h10_convergence.png",
     "周期 7 s・水深 10 m・高さ 1.0 m を粒子 0.5・0.25・0.125 m で。細かくすると理論の波（点線）に重なる（速さ −2.5 → −0.9 → −0.4 %、3 波長の減り 28 → 15 → 3 %）"),
    ("mc_4_B1_convergence.png", "figs/B1_convergence.png",
     "粒子の間隔だけを変えた時の速さの誤差と高さの減り（4 組）。赤い線は判定の幅"),
    ("mc_5_amplitude_vs_grid.png", "figs/B1_amplitude_vs_grid.png",
     "1 波長の窓ごとの速さの誤差と減りを、その場の振幅 ÷ 格子に対して描いた図。格子より低い波（0.15 未満）は 2〜4 割遅く、1 波長で 26〜88 % 減る"),
    ("mc_6_cause_isolation.png", "figs/B1_cause_isolation.png",
     "原因を分ける計算（周期 7 s・水深 25 m）：粒子の帯・時間の刻み・流速の受け渡しを一つずつ変えても、速さの誤差は大きくは変わらない"),
    ("mc_7_B2_T10_dp0.5.png", "figs/B2_B2_T10_h40-12_n20_dp0.5_relax_H1.5.png",
     "ゆるい斜面（水深 40 → 12 m、1:20）、周期 10 s、粒子 0.5 m：場所ごとの速さは線形の式から −2.3〜+1.3 %、斜面を上る時間は FLIP 44.29 s・線形 43.89 s（40 m のままなら 38.27 s）。高さは浅水係数（線）より大きく減った"),
    ("mc_8_T1_pressure_units.png", "figs/T1_pressure_units.png",
     "水面の圧力の場 surfacepressure の確かめ：静かな水に cos の圧力を与えた時の水面と式 −p/(ρg)。粒子 1 m では谷が始めの水面で止まり、粒子の帯を使わないと止まらない"),
    ("mc_9_T2_wind_growth.png", "figs/T2_wind_growth.png",
     "風の圧力（水面の斜面と同じ位相）で波が育つ速さ：FLIP（点と実線）と、入れた圧力の仕事の式（点線）。Miles 型 1.03、Jeffreys 型 0.90、接線の応力を足すと 0.68（記録だけ）"),
]

DATA = [
    ("plan_ja.md", V + "plan_ja.md",
     "走らせる前（2026-10-08 21:25、判定に使う最初の計算 21:26 の前）に書いた計画と判定の幅。中身は元と同じ。§8 は走らせた後に足した計算と理由（判定の幅は変えていない）。文中のパスは Unity/Build/FLIP41/ から見たもの"),
    ("summary_tables.md", V + "summary_tables.md", "全部の計算の値と判定の表（v_summary.py の出力。中身は元と同じ）"),
    ("summary.json", V + "summary.json", "同じ表の数（v_summary.py の出力）"),
    ("t2_summary.json", V + "t2_summary.json", "風の確かめ T2 の窓ごとの数（v_summary.py の出力）"),
    ("plan_numbers.json", V + "plan_numbers.json", "計画の理論の値（v_plan_numbers.py の出力）"),
    ("b_theory_numbers.json", B + "research/b_theory_numbers.json", "基準の問題の調べの理論の値（b_theory_numbers.py の出力）"),
    ("wind_estimates.json", B + "research/wind_estimates.json", "風の調べの数（wind_estimates.py の出力）"),
    ("mc_proposal_numbers.json", B + "report/mc_proposal_numbers.json", "報告 §6 の提案の数（mc_proposal_numbers.py の出力。式と測った値からの見積もり）"),
]

NOTE_COPY = "> 写し：元は `Unity/Build/FLIP41/research/{src}`（Git 対象外、2026-10-08）。直したのは、ほかの文書を指す名前とリンクの相対パス{extra}だけで、ほかは元のまま。文中の【計算】の JSON は [Docs/Evidence/FLIPMethodCheck](../Evidence/FLIPMethodCheck/) に写した。測った結果は [方法の確かめの報告](../Progress/FLIP_MethodCheck_ja.md)。\n"

# 個人の一時置き場のパス（C: の利用者のフォルダーの下の tool-results）。名前そのものはこの道具にも書かない
PERSONAL_RE = re.compile(r"`C:\\Users\\[^`]*?\\tool-results\\` の `webfetch-\*\.pdf`")

RESEARCH = [
    ("WaveTank_Benchmarks_ja.md", "benchmarks_ja.md", "と、読む道具の一時置き場のパス（個人のパス）1 か所",
     [("[wind_ja.md](wind_ja.md)", "[WindWaves_Kanagawa_ja.md](WindWaves_Kanagawa_ja.md)"),
      ("](../../../../Docs/Workflow/Production_Workflow_ja.md)", "](../Workflow/Production_Workflow_ja.md)"),
      (PERSONAL_RE, "会話の一時置き場（C: の利用者のフォルダーの下）の `webfetch-*.pdf`"),
      ("wind_ja.md", "WindWaves_Kanagawa_ja.md")]),
    ("WindWaves_Kanagawa_ja.md", "wind_ja.md", "",
     [("](../../../../Docs/Research/TallWave_Mechanisms_ja.md)", "](TallWave_Mechanisms_ja.md)"),
      ("](../../../../Docs/Workflow/Production_Workflow_ja.md)", "](../Workflow/Production_Workflow_ja.md)"),
      ("benchmarks_ja.md", "WaveTank_Benchmarks_ja.md")]),
]


def copy_research(copies):
    for dst, src, extra, reps in RESEARCH:
        sp = B + "research/" + src
        txt = open(sp, encoding="utf-8").read()
        done = []
        for a, b in reps:
            if isinstance(a, re.Pattern):
                txt, n = a.subn(b, txt)
                done.append(dict(old="（C: の利用者のフォルダーの下の、読む道具の一時置き場のパス）", new=b, count=n))
                continue
            n = txt.count(a)
            if n:
                txt = txt.replace(a, b)
            done.append(dict(old=a, new=b, count=n))
        lines = txt.split("\n")
        lines.insert(1, "\n" + NOTE_COPY.format(src=src, extra=extra).rstrip("\n"))
        txt = "\n".join(lines)
        if re.search(r"C:\\Users|C:/Users", txt):
            raise SystemExit("個人のパスが残っている: " + dst)
        dp = RS + dst
        with open(dp, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        copies.append(dict(name=rel(dp), src=rel(sp), src_sha256=sha(sp), bytes=os.path.getsize(dp), sha256=sha(dp),
                           note_ja="調べの写し。先頭に写しの注を 1 行足し、次の置き換えだけをした", replacements=done))


def metrics():
    s = json.load(open(V + "summary.json", encoding="utf-8"))
    keep = ("run_id", "T", "h", "kh", "dp", "wm", "H", "HL", "a_vox", "L_vox", "c_err", "c_spread", "decay_3L",
            "a_exit_ratio", "dphase_exit", "R", "band_vox", "minsub", "vt", "nb", "wall_s", "ok_c", "ok_decay", "ok_exit")

    def pick(r):
        return {k: (round(r[k], 4) if isinstance(r.get(k), float) else r.get(k)) for k in keep if k in r}
    out = {
        "schema": "GreatWave.FLIPMethodCheck.metrics/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note_ja": "FLIP41 の方法の確かめ（Q41）の主な数と判定。ok_* は plan_ja.md §5 の幅（走らせる前に進行役が決めた幅。利用者・指導教員の確認はまだ）に入ったか。c_err は線形の分散の式 ω² = g k tanh(kh) の速さとの差（比 − 1）、decay_3L は測る区間 3 波長での高さの減り、a_vox・L_vox は振幅・波長 ÷ 格子。値は verify/summary.json から写した",
        "criteria_ja": {
            "B1_speed": "|c/c線形 − 1| ≤ 1 %", "B1_decay": "3 波長で ≤ 5 %", "B1_exit": "帯の出口 高さ ±5 %・位相 ±0.1 rad",
            "B1_gci": "使う粒子の大きさで速さの GCI ≤ 1 %", "W_piston": "Biésel の式の高さ ±5 %",
            "B2": "場所ごとの速さ ±2 %、斜面を上る時間 ±0.5 s、浅水係数 ±3 %",
            "T1": "cos の圧力への答え ±10 %、一様な圧力で揺れが静かな水の 2 倍以内", "T2": "圧力の仕事の式との比 ±25 %、Miles 型は Plant の幅の中"},
        "headline_ja": [
            "粒子 1 m（今までの設定）：速さ −31〜+2.4 %、3 波長の減り 33〜82 %。決めた幅に入らない",
            "周期 7 s を水深 25・10・5 m で（粒子 0.25 m 以下）：速さ −0.46・−0.45（0.125 m）・−1.7 %。25・10 m は 1 % の幅に入った",
            "水深 10 m の組の収束：次数 2.0、GCI 0.17 %（0.125 m）・0.69 %（0.25 m）。水深 25 m の組は振動して GCI 1.7〜5.1 %",
            "斜面 1:20（粒子 0.5 m、周期 10 s）：斜面を上る時間 +0.40 s（水深の効果 5.6 s）。高さ（浅水係数）は確かめられなかった",
            "風の圧力：圧力の仕事の式との比 1.03（Miles 型）・0.90（Jeffreys 型）",
        ],
        "B1": [pick(r) for r in s["B1"] + s["AMP"]],
        "W_piston": [pick(r) for r in s["W"]],
        "cause_isolation": [pick(r) for r in s["ISO"]],
        "B2": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in s["B2"]],
        "T1": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in s["T1"]],
        "T2": [{k: (round(v, 6) if isinstance(v, float) else ([round(x, 6) for x in v] if isinstance(v, list) else v)) for k, v in r.items()} for r in s["T2"]],
        "convergence": s["convergence"],
    }
    p = EV + "metrics.json"
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return p


def run_record(copies):
    L = [json.loads(l) for l in open(V + "runs.jsonl", encoding="utf-8") if l.strip()]
    good = set(os.listdir(V + "runs"))
    launches = [r for r in L if r["run_id"] in good and not str(r.get("stopped") or "").startswith("free_fall")]
    other = [dict(run_id=r["run_id"], date=r["date"], wall_s=r["wall_launch_s"], stopped=r.get("stopped"))
             for r in L if r not in launches]
    per = collections.OrderedDict()
    for r in launches:
        d = per.setdefault(r["run_id"], dict(launches=0, wall_s=0.0, particles_max=0, rss_peak_gb=0.0))
        d["launches"] += 1
        d["wall_s"] = round(d["wall_s"] + r["wall_launch_s"], 1)
        d["particles_max"] = max(d["particles_max"], r.get("particles_max") or 0)
        d["rss_peak_gb"] = max(d["rss_peak_gb"], r.get("rss_peak_gb") or 0.0)
    # キャッシュ
    hf, ck_n, ck_b = [], 0, 0
    for rd in sorted(glob.glob(V + "runs/*/")):
        for p in sorted(glob.glob(rd + "hf_c*.npz")):
            hf.append(dict(path=rel(p), bytes=os.path.getsize(p), sha256=sha(p)))
        for p in glob.glob(rd + "ckpt/**/*", recursive=True):
            if os.path.isfile(p):
                ck_n += 1; ck_b += os.path.getsize(p)
    tools = {rel(p): sha(p) for p in sorted(glob.glob(TOOLS + "*.py"))}
    scene_sha = sha(SCENE)
    run = {
        "schema": "GreatWave.FLIPMethodCheck.deliver_run/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note_ja": "Docs/Evidence/FLIPMethodCheck を作った記録。この段で新しい流体計算・描画はしていない（図は確かめの時に v_figs.py で描いたものの写し）。git の操作とダウンロードはしていない",
        "commands": ["py -3.10 -B Tools/GWWaveGen/flip41/mc_proposal_numbers.py", "py -3.10 -B Tools/GWWaveGen/flip41/mc_deliver.py"],
        "upstream_commands_ja": {
            "調べ": "py -3.10 b_theory_numbers.py → research/b_theory_numbers.json、py -3.10 wind_estimates.py → research/wind_estimates.json",
            "場面": "hython Tools/GWWaveGen/flip41/v_build_tank.py → Houdini/FLIP41/v_tank.hiplc（計算ごとには変えない。CTRL の値だけを変える）",
            "計画": "py -3.10 v_plan_numbers.py → verify/plan_numbers.json、verify/plan_ja.md（走らせる前に書いた）",
            "計算": "py -3.10 v_cfg.py <組> の JSON → py -3.10 v_chain.py <JSON>（30 分ごとに区切り途中保存から続ける）。列は py -3.10 v_queue.py verify/queue1.txt〜queue5.txt（記録 verify/queue_log.txt・runs.jsonl）",
            "解析": "py -3.10 v_analyze.py <計算の名前> → runs/<名前>/ana.json、py -3.10 v_summary.py → summary_tables.md・summary.json・t2_summary.json、py -3.10 v_figs.py all → figs/",
        },
        "versions": {"python": platform.python_version(), "houdini": "Houdini Indie 22.0.459 hython（画面なし。runs.jsonl の全行で 22.0.459）",
                     "unity": "使っていない（作品の場面は開いていない）"},
        "scene": {"path": rel(SCENE), "bytes": os.path.getsize(SCENE), "sha256": scene_sha,
                  "same_as_all_runs": all(r["hip_sha256"] == scene_sha for r in L),
                  "note_ja": "キャッシュは含まない。Houdini が自動で書く作者の印と既定の道具のパスを含む（FLIP37・FLIP39 の場面と同じ）"},
        "tools": tools,
        "runs": {"period": [L[0]["date"], L[-1]["date"]], "n_runs": len(per), "n_launches": len(launches),
                 "wall_h": round(sum(r["wall_launch_s"] for r in launches) / 3600, 2),
                 "max_launch_min": round(max(r["wall_launch_s"] for r in launches) / 60, 1),
                 "per_run": per, "other_launches_ja": "道具の試し 3 本（smoke_*）、帯なしの 1 回目（水が落ちて 13 コマで見張りが止めた）、時間のため止めた帯なしの B2（81 秒ぶん）",
                 "other_launches": other,
                 "runs_jsonl": dict(path=rel(V + "runs.jsonl"), sha256=sha(V + "runs.jsonl"), lines=len(L))},
        "caches": {"surface_records_hf": dict(count=len(hf), bytes=sum(x["bytes"] for x in hf), files=hf),
                   "checkpoints": dict(count=ck_n, bytes=ck_b, note_ja="途中保存。解析には使わない。消すかは利用者が決める（SHA-256 は取っていない）")},
        "evidence": [dict(name=c["name"], sha256=c["sha256"]) for c in copies],
    }
    p = EV + "run.json"
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    return p, run


def main():
    os.makedirs(EV, exist_ok=True)
    copies = []
    for name, src, note in FIGS:
        sp = V + src
        dp = EV + name
        shutil.copyfile(sp, dp)
        copies.append(dict(name=rel(dp), src=rel(sp), bytes=os.path.getsize(dp), sha256=sha(dp), note_ja=note))
    for name, sp, note in DATA:
        dp = EV + name
        shutil.copyfile(sp, dp)
        copies.append(dict(name=rel(dp), src=rel(sp), bytes=os.path.getsize(dp), sha256=sha(dp), note_ja=note))
    copy_research(copies)
    mp = metrics()
    copies.append(dict(name=rel(mp), src="verify/summary.json から mc_deliver.py で作った", bytes=os.path.getsize(mp), sha256=sha(mp),
                       note_ja="主な数と判定"))
    for c in copies:
        if c.get("src_sha256") is None and not c["src"].startswith("verify/") and os.path.exists(ROOT + "/" + c["src"]):
            c["same_as_src"] = sha(ROOT + "/" + c["src"]) == c["sha256"]
    with open(EV + "copies.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(copies, f, ensure_ascii=False, indent=1)
    rp, run = run_record(copies)
    print("evidence files:", len(copies))
    print("runs:", run["runs"]["n_runs"], "launches:", run["runs"]["n_launches"], "wall_h:", run["runs"]["wall_h"],
          "max_launch_min:", run["runs"]["max_launch_min"], "scene same:", run["scene"]["same_as_all_runs"])
    print("hf:", run["caches"]["surface_records_hf"]["count"], round(run["caches"]["surface_records_hf"]["bytes"] / 1e9, 2), "GB;",
          "ckpt:", run["caches"]["checkpoints"]["count"], round(run["caches"]["checkpoints"]["bytes"] / 1e9, 2), "GB")


if __name__ == "__main__":
    main()
