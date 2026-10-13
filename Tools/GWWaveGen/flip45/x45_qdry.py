# -*- coding: utf-8 -*-
"""FLIP45：並べて走らせる道具 g45_queue.py の道を --dry-run で確かめる（py -3.10。hython も表も作らない。数十秒）。
2026-10-12 12:55 に書いた（別の者の確かめ check_ja.md の F2・F7 の直しの確かめ）。
V1 の後の道は、置き場所ごとに V1 の結果（QUEUE_STATE.json の V1_done・V1_gate）を仮に置いてから打つ（本当の V1 の結果ではない）。
置き場所：Unity/Build/FLIP45/qdry/<日時>/<試しの名前>/（毎回新しい。前の物は消さない）。結果：Unity/Build/FLIP45/qdry/<日時>/qdry_result.json
使い方：py -3.10 x45_qdry.py
"""
import sys, os, json, time, subprocess, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

Q = GC.TOOLS + "/g45_queue.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
STAMP = time.strftime("%Y%m%d_%H%M%S")
BASE = "qdry/" + STAMP
os.makedirs(os.path.join(GC.B45, BASE), exist_ok=True)

GATE_PASS = dict(a=True, b=True, d=True, pre=False, n3_min=0.97, n3_max=1.06, focus_eta=5.6, stops=[None], tBP=47.9, v3_needed=False,
                 v3_why_ja="（仮に置いた値）")


def seed(root, gate=None, extra=None, v1_dir=False):
    rd = os.path.join(GC.B45, root)
    os.makedirs(rd, exist_ok=True)
    s = {}
    if gate is not None:
        s.update(V1_done="2026-10-12 00:00:00（x45_qdry の仮の値）", V1_gate=gate)
    if extra:
        s.update(extra)
    json.dump(s, open(os.path.join(rd, "QUEUE_STATE.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if v1_dir:
        os.makedirs(os.path.join(rd, "V1"), exist_ok=True)
        open(os.path.join(rd, "V1", "SEED.txt"), "w", encoding="utf8").write("x45_qdry の仮の V1 の置き場所\n")
        open(os.path.join(rd, "V1_RESULT_ja.md"), "w", encoding="utf8").write("# 仮の V1 の結果（x45_qdry）\n")


def run(name, args, root=None, expect_rc=None, expect_text=(), expect_files=(), expect_absent=(), seed_kw=None):
    root = root or (BASE + "/" + name)
    if seed_kw is not None:
        seed(root, **seed_kw)
    rd = os.path.join(GC.B45, root)
    cmdl = [sys.executable, Q] + args + ["--root", root]
    p = subprocess.run(cmdl, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    txt = p.stdout + p.stderr
    for fn in ("QUEUE_STOP.txt", "QUEUE_PAUSE.txt"):
        fp = os.path.join(rd, fn)
        if os.path.exists(fp):
            txt += "\n" + open(fp, encoding="utf8").read()
    ok = True; why = []
    if expect_rc is not None and p.returncode != expect_rc:
        ok = False; why.append("rc %s（期待 %s）" % (p.returncode, expect_rc))
    for t in expect_text:
        if t not in txt:
            ok = False; why.append("文がない：%s" % t)
    for f in expect_files:
        if not glob.glob(os.path.join(rd, f)):
            ok = False; why.append("ファイルがない：%s" % f)
    for f in expect_absent:
        if glob.glob(os.path.join(rd, f)):
            ok = False; why.append("あってはいけないファイルがある：%s" % f)
    last = [l for l in txt.splitlines() if ("STOP" in l or "PAUSE" in l or "stage" in l or "queue end" in l or "rerun" in l)]
    res = dict(name=name, args=args, root=root, rc=p.returncode, ok=ok, why=why, lines=last[-12:])
    print(("OK  " if ok else "NG  ") + name, p.returncode, "|", (last[-1] if last else txt.strip()[-200:])[:300])
    return res


R = []
AG = ["--agreed", "x45_qdry dry-run only", "--dry-run"]
# 1. 旗なし
R.append(run("T01_noflag", [], expect_rc=2))
# 2. 下見（新しい置き場所）：V1 の設定を書いて止まる。設定は ready/V1.json と置き場所の 1 行だけ違う（下で比べる）
R.append(run("T02_preview", ["--preview", "--dry-run"], expect_rc=3, expect_text=["dry-run：V1 の設定を書いた"], expect_files=["V1/cfg_queue.json"]))
# 3. V1 の前の --confirm v1 は受けない（F7）
R.append(run("T03_confirm_before_v1", ["--preview", "--confirm", "v1", "--dry-run"], expect_rc=2, expect_text=["--confirm v1 は受けない"],
             expect_absent=["V1/cfg_queue.json"]))
# 4. 合意の道で V1 がない
R.append(run("T04_agreed_no_v1", AG, expect_rc=2, expect_text=["V1 がまだ終わっていない"], expect_absent=["M1_L1", "M1_L2"]))
# 5. 合意の道、関門は入った、--confirm v1 なし → 止まって確かめを待つ（M1 を始めない）
R.append(run("T05_agreed_no_confirm", AG, expect_rc=3, expect_text=["--confirm v1）がないので"], expect_absent=["M1_L1", "M1_L2"],
             seed_kw=dict(gate=dict(GATE_PASS))))
# 6. 合意の道、関門は入った、--confirm v1 あり → M1_L1（並び B）を書いて M1 の後で止まる
r6 = BASE + "/T06_agreed_confirm"
R.append(run("T06_agreed_confirm", AG + ["--confirm", "v1"], root=r6, expect_rc=3, expect_text=["stage M1_L1", "M1 が終わった"],
             expect_files=["M1_L1/cfg_queue.json", "SEQ_DECISION.json"], seed_kw=dict(gate=dict(GATE_PASS))))
# 6b. 同じ置き場所で --confirm m1 → 残りの並び B（M1f なし）
R.append(run("T06b_agreed_confirm_m1", AG + ["--confirm", "m1"], root=r6, expect_rc=0,
             expect_text=["stage M1h_L1", "stage V1h", "stage V4", "stage RPT05", "stage X60_L1x", "stage M1c_L1", "stage F40_L1", "stage X45_L1w", "queue end"],
             expect_absent=["M1f_L2"]))
# 7. 関門 (b) が外れた：--confirm v1 は受けるが、M1 を始めず、帯を直して V1 を走らせ直すと書いて止まる（F2）
GB = dict(GATE_PASS, b=False, n3_min=0.861, n3_max=0.947)
R.append(run("T07_agreed_gate_b_fail", AG + ["--confirm", "v1"], expect_rc=2,
             expect_text=["関門 (b)", "帯の作り（VEX、表、壁のなだらかさ、利得の入れ方）", "--rerun-v1"], expect_absent=["M1_L1", "M1_L2"],
             seed_kw=dict(gate=dict(GB))))
# 7b. 関門 (b) が外れた、--confirm v1 なし（前の check の T6 と同じ形）：やはり M1 を始めない
R.append(run("T07b_agreed_gate_b_fail_noconfirm", AG, expect_rc=2, expect_text=["関門 (b)"], expect_absent=["M1_L1", "M1_L2"],
             seed_kw=dict(gate=dict(GB))))
# 8. 関門 (b) が外れた：下見の道（V2・V1h・V4）も始めない
R.append(run("T08_preview_gate_b_fail", ["--preview", "--confirm", "v1", "--user-ok-05", "x45_qdry", "--dry-run"], expect_rc=2,
             expect_text=["関門 (b)"], expect_absent=["V1h", "V4", "V2"], seed_kw=dict(gate=dict(GB))))
# 9. 関門 (b) が外れた後の走らせ直し：前の V1 を V1_try1_* へ移し（消さない）、V1 の設定を書き直して止まる
r9 = BASE + "/T09_rerun_v1"
R.append(run("T09_rerun_v1", ["--preview", "--rerun-v1", "x45_qdry：帯の作りを直したつもりの試し", "--dry-run"], root=r9, expect_rc=3,
             expect_text=["rerun V1", "dry-run：V1 の設定を書いた"], expect_files=["V1_try1_*/SEED.txt", "V1_try1_*_RESULT_ja.md", "V1_RERUN_LOG.txt",
                                                                             "V1/cfg_queue.json"],
             seed_kw=dict(gate=dict(GB), extra=dict(confirmed=dict(v1=dict(at="x", of_V1_done="2026-10-12 00:00:00（x45_qdry の仮の値）"))), v1_dir=True)))
# 9b. 走らせ直しの後、前の確かめは使えない：合意の道は V1 がないので止まる
R.append(run("T09b_after_rerun_agreed", AG + ["--confirm", "v1"], root=r9, expect_rc=2, expect_text=["--confirm v1 は受けない"],
             expect_absent=["M1_L1"]))
# 10. 関門が全部入った時の --rerun-v1 は受けない
R.append(run("T10_rerun_refused", ["--preview", "--rerun-v1", "x", "--dry-run"], expect_rc=2, expect_text=["--rerun-v1 は受けない"],
             seed_kw=dict(gate=dict(GATE_PASS), v1_dir=True), expect_files=["V1/SEED.txt"]))
# 11. 関門 (d) が外れた
R.append(run("T11_agreed_gate_d_fail", AG + ["--confirm", "v1"], expect_rc=2, expect_text=["関門 (d)"], expect_absent=["M1_L1"],
             seed_kw=dict(gate=dict(GATE_PASS, d=False, focus_eta=4.7))))
# 12. 関門 (a) が外れた
R.append(run("T12_agreed_gate_a_fail", AG + ["--confirm", "v1"], expect_rc=2, expect_text=["関門 (a)"], expect_absent=["M1_L1"],
             seed_kw=dict(gate=dict(GATE_PASS, a=False, stops=["free_fall at frame 900"]))))
# 13. V1 の巻き始めの時刻が ±5 % の外：M1 の前に V3（立ち上げ tanh_s）
R.append(run("T13_agreed_v3", AG + ["--confirm", "v1"], expect_rc=3, expect_text=["stage V3", "ramp tanh_s", "stage M1_L1"],
             expect_files=["V3/cfg_queue.json", "M1_L1/cfg_queue.json"], seed_kw=dict(gate=dict(GATE_PASS, tBP=53.2, v3_needed=True))))
# 14. V1 が §6.8 の前提を満たした：合意の道の最初に V2 → 止まる → --confirm v2 → M1（check の F6）
r14 = BASE + "/T14_agreed_v2"
R.append(run("T14_agreed_v2", AG + ["--confirm", "v1"], root=r14, expect_rc=3, expect_text=["stage V2", "V2 が終わった"],
             expect_files=["V2/cfg_queue.json", "SEQ_DECISION.json"], expect_absent=["M1_L1", "M1_L2"], seed_kw=dict(gate=dict(GATE_PASS, pre=True))))
R.append(run("T14b_agreed_without_confirm_v2", AG, root=r14, expect_rc=3, expect_text=["V2 の結果（runs/SEQ_DECISION.json）を人が見た確かめがまだ"],
             expect_absent=["M1_L1", "M1_L2"]))
R.append(run("T14c_agreed_confirm_v2", AG + ["--confirm", "v2"], root=r14, expect_rc=3, expect_text=["stage M1_L1"], expect_files=["M1_L1/cfg_queue.json"]))
# 15. 古い形の確かめ（文字だけ。どの V1 か分からない）は使えない
R.append(run("T15_stale_confirm", AG, expect_rc=3, expect_text=["--confirm v1）がないので"], expect_absent=["M1_L1"],
             seed_kw=dict(gate=dict(GATE_PASS), extra=dict(confirmed=dict(v1="2026-10-12 12:00:00")))))
# 16. 下見の道：関門は入った、確かめあり、利用者の許しなし → 許しを待つ
R.append(run("T16_preview_need_user_ok", ["--preview", "--confirm", "v1", "--dry-run"], expect_rc=3, expect_text=["利用者の許しが要る"],
             seed_kw=dict(gate=dict(GATE_PASS))))
# 17. 凍結の違い・利得の記録なし（モジュールの値だけ差し替える。ファイルは変えない）
for nm, mode in (("T17_frozen_mismatch", "frozen"), ("T18_no_gain", "gain")):
    root = BASE + "/" + nm
    code = ("import sys, runpy; sys.path.insert(0, %r); import g45_common as GC\n" % GC.TOOLS +
            ("GC.frozen_ok = lambda: (False, ['plan/plan_ja.md（x45_qdry の差し替え）'])\n" if mode == "frozen"
             else "GC.GAIN_FILE = GC.B45 + '/gain/__no_such_gain_file__.json'\n") +
            "sys.argv = [%r, '--preview', '--dry-run', '--root', %r]\nrunpy.run_path(%r, run_name='__main__')\n" % (Q, root, Q))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    txt = p.stdout + p.stderr
    want = "凍結した計画" if mode == "frozen" else "入口の利得の記録"
    ok = p.returncode == 2 and want in txt and not os.path.exists(os.path.join(GC.B45, root, "V1"))
    print(("OK  " if ok else "NG  ") + nm, p.returncode)
    R.append(dict(name=nm, rc=p.returncode, ok=ok, why=[] if ok else ["rc か文が違う"], lines=[l for l in txt.splitlines() if "STOP" in l][-3:]))

# T02 の V1 の設定と ready/V1.json の比べ（置き場所の 1 行だけ違うはず）
cmp = {}
try:
    a = json.load(open(os.path.join(GC.B45, BASE, "T02_preview", "V1", "cfg_queue.json"), encoding="utf8"))
    b = json.load(open(os.path.join(GC.B45, "runs", "ready", "V1.json"), encoding="utf8"))
    cmp["diff_keys"] = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    cmp["ok"] = cmp["diff_keys"] == ["out_root"]
except Exception as e:
    cmp = dict(error=repr(e), ok=False)
print(("OK  " if cmp.get("ok") else "NG  ") + "T02 の V1 の設定と ready/V1.json の違い", cmp.get("diff_keys"))
out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), base=BASE, all_ok=bool(all(r["ok"] for r in R) and cmp.get("ok")), results=R, v1_cfg_vs_ready=cmp)
json.dump(out, open(os.path.join(GC.B45, BASE, "qdry_result.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("all_ok", out["all_ok"], "->", BASE + "/qdry_result.json")
sys.exit(0 if out["all_ok"] else 1)
