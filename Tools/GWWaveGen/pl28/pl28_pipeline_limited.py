# -*- coding: utf-8 -*-
"""仕上げ28：設計28修正01 試行F の一式（ds28r01f_pipeline.py）を、同時に走らせる検査の数を絞って回す包み。

ds28r01f_pipeline.py は検査（関門 5 組・重なり・目標の検査器・走査・P20 …）を全部同時に起動する。仕上げ28 の実行の時、この機械の
確保の上限（commit、約 67.8 GB。ほかのアプリで約 61 GB が使われていた）の残りが約 6.5 GB しかなく、生成の 14 プロセスで MemoryError
になった。この包みは、同じプロセスの中だけで ds28r01d_pipeline.run_parallel を「同時に N 個まで」の版に差し替えてから
ds28r01f_pipeline.main を呼ぶ（命令・引数・出力は元のまま。ファイルは変えない）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_pipeline_limited.py --max-jobs 2 -- <ds28r01f_pipeline.py の引数>
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01f"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01d"))
import ds28r01d_pipeline as PD  # noqa: E402
import ds28r01f_pipeline as FP  # noqa: E402

MAX_JOBS = 2


def run_limited(jobs, log_dir):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    pending = list(jobs)
    running = []
    bad = []
    while pending or running:
        while pending and len(running) < MAX_JOBS:
            name, cmd = pending.pop(0)
            lf = open(os.path.join(log_dir, name + ".log"), "w", encoding="utf-8")
            running.append((name, subprocess.Popen(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, env=env), lf, time.time()))
        time.sleep(2.0)
        still = []
        for name, p, lf, t0 in running:
            rc = p.poll()
            if rc is None:
                still.append((name, p, lf, t0))
                continue
            lf.close()
            print("%-28s rc %d  %.0f s" % (name, rc, time.time() - t0), flush=True)
            if rc != 0:
                bad.append(name)
        running = still
    return bad


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--" not in argv:
        raise SystemExit("使い方：--max-jobs N -- <ds28r01f_pipeline.py の引数>")
    k = argv.index("--")
    own, rest = argv[:k], argv[k + 1:]
    if "--max-jobs" in own:
        MAX_JOBS = int(own[own.index("--max-jobs") + 1])
    PD.run_parallel = run_limited
    FP.PD.run_parallel = run_limited
    sys.argv = [os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01f", "ds28r01f_pipeline.py")] + rest
    print("同時に走らせる検査の数：%d" % MAX_JOBS, flush=True)
    FP.main()
