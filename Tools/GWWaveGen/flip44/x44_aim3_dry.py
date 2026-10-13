# -*- coding: utf-8 -*-
"""FLIP44：下見 3 本目の入口（凍結した p_plan_numbers.py --aim3 と同じ計算）を、試しの置き場所へ書く（py -3.10。g44_queue.py の --dry-run 用。確かめ G3）。
凍結した道具は書き換えない：ファイルを読み、SHA-256 が plan/plan_frozen.json と同じことを確かめ、出力のフォルダー（OUTDIR の 1 行）だけを
替えた写しを、この処理の中で走らせる。plan/ には何も書かない。
py -3.10 x44_aim3_dry.py <狙い x m> <出力のフォルダー>   → <出力のフォルダー>/pr3_aim<x>.json
"""
import sys, os, json, hashlib

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
SRC = ROOT + "/Tools/GWWaveGen/flip44/p_plan_numbers.py"
FROZEN = ROOT + "/Unity/Build/FLIP44/plan/plan_frozen.json"
LINE = 'OUTDIR = ROOT + "/Unity/Build/FLIP44/plan"'


def main():
    x, outdir = sys.argv[1], sys.argv[2]
    outdir = os.path.abspath(outdir).replace("\\", "/")
    plan_dir = (ROOT + "/Unity/Build/FLIP44/plan").lower()
    if outdir.lower().rstrip("/") == plan_dir:
        print("出力のフォルダーが凍結した計画の plan/ になっている。dry-run の写しは plan/ に書かない", file=sys.stderr); sys.exit(2)
    raw = open(SRC, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    fz = {f["path"]: f["sha256"] for f in json.load(open(FROZEN, encoding="utf-8"))["frozen"]}
    if fz.get("Tools/GWWaveGen/flip44/p_plan_numbers.py") != sha:
        print("p_plan_numbers.py の SHA-256 が凍結の記録と違う（%s）。走らせない" % sha, file=sys.stderr); sys.exit(2)
    src = raw.decode("utf-8")
    if src.count(LINE) != 1:
        print("OUTDIR の行が 1 つでない。走らせない", file=sys.stderr); sys.exit(2)
    os.makedirs(outdir, exist_ok=True)
    code = compile(src.replace(LINE, "OUTDIR = %r" % outdir), SRC, "exec")
    sys.argv = [SRC, "--aim3", x]
    g = {"__name__": "__main__", "__file__": SRC}
    exec(code, g)
    p = os.path.join(outdir, "pr3_aim%.0f.json" % float(x))
    if not os.path.exists(p):
        print("書いたはずの %s がない" % p, file=sys.stderr); sys.exit(2)
    print("dry-run の写し：凍結した道具と同じ計算（SHA-256 %s…）で %s を書いた" % (sha[:12], p))


if __name__ == "__main__":
    main()
