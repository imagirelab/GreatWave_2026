# -*- coding: utf-8 -*-
"""cases.json の算例を組み立て済みの gw_shoal で走らせる（同時に走らせる数を決められる）。

使い方：
  python3 run_cases.py --bin 組み立てた物の置き場 --runs 書き出し先 --jobs 3 A_L10 B_S2_L11 ...
  python3 run_cases.py --print A_L12          # 走らせる命令だけ表示
  python3 run_cases.py --mpi 4 B_S2_L12       # MPI で 1 本を 4 プロセス
  python3 run_cases.py --fresh A_L10          # 前の書き出し（途中の保存を含む）を消して初めから

同じ名前で走らせ直すと、途中の保存（restart）があれば続きから回る。初めから回す時は --fresh を付ける。

書き出し先には、算例の名前のフォルダー（win_*.bin・full_*.bin・log.txt）と、
名前.out・名前.err・名前.done（終わりの記録：exit= と wall=）ができる。
"""
import os, sys, json, argparse, subprocess, time, shlex
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = json.load(open(os.path.join(HERE, "cases.json"), encoding="utf8"))


def command(name, bindir, runs, mpi=0):
    c = CASES[name]
    b = c["binary"] + ("_mpi" if mpi else "")
    args = ["level=%d" % c["level"], "x0=%.10g" % c["x0"], "xl=%.10g" % c["xl"], "lbox=%.10g" % c["lbox"],
            "a0=%g" % c["a0"], "re=%g" % c["re"], "bo=%g" % c["bo"], "tend=%g" % c["tend"],
            "bathy=" + ",".join("%.10g:%.10g" % (x, d) for x, d in c["bathy"])] + c.get("extra", []) + \
           ["out=" + os.path.join(runs, name)]
    cmd = [os.path.join(bindir, b)] + args
    if mpi:
        cmd = ["mpirun", "--allow-run-as-root", "-np", str(mpi)] + cmd
    return cmd


def run_one(name, bindir, runs, mpi=0, fresh=False):
    done = os.path.join(runs, name + ".done")
    if fresh:
        import shutil
        shutil.rmtree(os.path.join(runs, name), ignore_errors=True)
        for ext in (".done", ".out", ".err"):
            if os.path.exists(os.path.join(runs, name + ext)):
                os.remove(os.path.join(runs, name + ext))
    if os.path.exists(done) and "exit=0" in open(done).read():
        return name, "既に終わっている"
    cmd = command(name, bindir, runs, mpi)
    t0 = time.time()
    with open(os.path.join(runs, name + ".out"), "w") as o, open(os.path.join(runs, name + ".err"), "w") as e:
        r = subprocess.call(cmd, stdout=o, stderr=e)
    with open(done if r == 0 else os.path.join(runs, name + ".fail"), "a") as fp:
        fp.write("exit=%d wall=%d\n" % (r, time.time() - t0))
    return name, r


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="cases.json の算例を走らせる")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--bin", default=os.environ.get("GW_BIN", "/opt/gw/bin"))
    ap.add_argument("--runs", default=os.environ.get("GW_RUNS", "/opt/gw/runs"))
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--mpi", type=int, default=0)
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="前の書き出しを消して初めから回す")
    a = ap.parse_args()
    if a.print:
        for n in a.names:
            print(" ".join(shlex.quote(x) for x in command(n, a.bin, a.runs, a.mpi)))
        sys.exit(0)
    os.makedirs(a.runs, exist_ok=True)
    with ThreadPoolExecutor(a.jobs) as ex:
        for n, r in ex.map(lambda n: run_one(n, a.bin, a.runs, a.mpi, a.fresh), a.names):
            print(n, r, flush=True)
