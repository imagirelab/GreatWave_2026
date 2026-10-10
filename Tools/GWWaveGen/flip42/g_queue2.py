# -*- coding: utf-8 -*-
"""FLIP42 R2 の段：重い計算を一つずつ順に流す（計画 §7.4 の順：R3 → R5' → R2 → R4）。
py -3.10 g_queue2.py <step> [<step> ...]
  step：wait:<run_id>（その計算の chain.log に "chain end" が出るまで待つ）
        copy:<from_run>:<frame>:<to_run>（from の途中保存 v.<frame>.sim を to の ckpt へ写す。元は消さない）
        chain:<run_id>（runs/<run_id>/cfg_in.json で g_chain2.py を走らせ、chain.log に書く）
止める：runs/QUEUE_STOP を置くと、次の step に入らない（今の chain は runs/<run_id>/STOP で止める）。
記録：runs/queue2_log.txt"""
import sys, os, time, shutil, subprocess

R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
CH = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/g_chain2.py"
LOG = os.path.join(R, "queue2_log.txt")


def log(*a):
    s = time.strftime("%Y-%m-%d %H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(s, flush=True)
    open(LOG, "a", encoding="utf8").write(s + "\n")


for st in sys.argv[1:]:
    if os.path.exists(os.path.join(R, "QUEUE_STOP")):
        log("QUEUE_STOP found; stop before", st); break
    kind, *a = st.split(":")
    log("start", st)
    if kind == "wait":
        p = os.path.join(R, a[0], "chain.log")
        while True:
            if os.path.exists(p) and "chain end" in open(p, encoding="utf8", errors="ignore").read():
                break
            time.sleep(30)
    elif kind == "copy":
        src = os.path.join(R, a[0], "ckpt", "v.%04d.sim" % int(a[1]))
        dd = os.path.join(R, a[2], "ckpt"); os.makedirs(dd, exist_ok=True)
        if not os.path.exists(src):
            log("missing checkpoint", src); break
        shutil.copy2(src, os.path.join(dd, os.path.basename(src)))
    elif kind == "chain":
        with open(os.path.join(R, a[0], "chain.log"), "a", encoding="utf8") as fh:
            rc = subprocess.run([sys.executable, CH, os.path.join(R, a[0], "cfg_in.json")], stdout=fh, stderr=subprocess.STDOUT).returncode
        log("chain", a[0], "returncode", rc)
    log("done", st)
log("queue end")
