# -*- coding: utf-8 -*-
"""報告の証拠をまとめる：results.json（全部の算例の量）、top3.json、図、run.json（版・命令・SHA-256）、動画の写し。

使い方：python3 collect.py  （GW_RUNS・GW_ANA・GW_VIDEOS で置き場を変えられる）
出力：Docs/Evidence/Basilisk/
"""
import os, sys, json, glob, shutil, hashlib, subprocess, platform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EVID = os.path.join(REPO, "Docs", "Evidence", "Basilisk")
RUNS = os.environ.get("GW_RUNS", "/opt/gw/runs")
ANA = os.environ.get("GW_ANA", "/opt/gw/ana")
VIDEOS = os.environ.get("GW_VIDEOS", "/opt/gw/videos")
CASES = json.load(open(os.path.join(HERE, "..", "cases.json"), encoding="utf8"))
TOP3 = ["C04_L11", "C08_L11", "C03_L11"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ver(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip().splitlines()[0]
    except Exception:
        return None


def main():
    os.makedirs(EVID, exist_ok=True)
    done = [n for n in CASES if os.path.exists(os.path.join(ANA, n + ".json"))]
    # 数の表
    import gwtable
    gwtable.main(os.path.join(EVID, "results.json"), [os.path.join(ANA, n + ".json") for n in done])
    json.dump(dict(note_ja="C の 10 段の score3 の上位 3 つを 11 段で解き直した算例", fine=[n for n in TOP3 if n in done]),
              open(os.path.join(EVID, "top3.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 図
    os.environ["GW_EVID"] = EVID
    import figures
    figures.EVID = EVID
    figures.fig_A_levels()
    names = [n for n in done if (n.startswith("B_S") and "x15" not in n and "S1p" not in n) or n.startswith("C")]
    figures.fig_score3(names, "fig_BC_score3.png", "B・C の score3（score3 最小のコマ）。格子の段は算例の名前の末尾（L10 = 10 段）")
    lv = "L12" if all(n in done for n in ("B_S1_L12", "B_S2_L12", "B_S5_L12")) else "L11"
    figures.fig_shapes(["B_S1_" + lv, "B_S2_" + lv, "B_S5_" + lv], "fig_B_shapes.png",
                       "B：S1・S2・S5（重力だけに近い条件、%s）。橙の線は原画の輪郭（縦÷1.3、頂の高さと位置を合わせた）" % lv.replace("L", "") + " 段")
    figures.fig_shapes([n for n in TOP3 if n in done], "fig_top3.png", "C の上位 3 つを 11 段で解き直した結果。橙の線は原画の輪郭")
    # 動画の写し
    vids = sorted(glob.glob(os.path.join(VIDEOS, "*.mp4")))
    for v in vids:
        shutil.copy2(v, os.path.join(EVID, os.path.basename(v)))
    # run.json
    sys.path.insert(0, os.path.join(HERE, ".."))
    import run_cases as RC
    runs = {}
    for n in done:
        rd = os.path.join(RUNS, n)
        dn = os.path.join(RUNS, n + ".done")
        runs[n] = dict(command=" ".join(RC.command(n, os.environ.get("GW_BIN", "/opt/gw/bin"), RUNS)), done=open(dn).read().strip() if os.path.exists(dn) else None,
                       restarted=os.path.exists(os.path.join(rd, "restarts.txt")),
                       n_win_frames=len(glob.glob(os.path.join(rd, "win_*.bin"))),
                       log_sha256=sha(os.path.join(rd, "log.txt")) if os.path.exists(os.path.join(rd, "log.txt")) else None)
    out = dict(
        note_ja="雲の計算機（claude.ai/code）での Basilisk の計算の記録。書き出しそのものはリポジトリに入れていない",
        binary_note_ja=("前半の算例（A_L9〜A_L11、B_S1_L10、B_S2_L10、B_S5_L10、B_S2_L11、C01〜C11 など）は、gw_shoal.c の log の体積の直し（dv の二重の cs）・"
                        "途中の保存・引数の確かめを入れる前の版で計算した。計算そのもの（流れ・格子・書き出し）は同じ"
                        "（独立の点検で、今の版で A_L10 を解き直し、最初のコマの書き出しが同じことを確かめた）。"
                        "B_S2_L10 は tS2_L10_inv（tend=20）の写し。覆いかぶさりの後 3 で止まるので tend の違いは結果に入らない"),
        machine=dict(cpu=ver("lscpu | grep 'Model name'"), cores=os.cpu_count(), os=platform.platform()),
        tools=dict(basilisk_tarball="https://basilisk.fr/basilisk/basilisk.tar.gz（2026-10-12 取得）",
                   basilisk_tarball_sha256="de851a91712aa83b0592e1e1ae8f7d7e2ffe1ade0266433434700f8c313fbed4",
                   author_setup="https://basilisk.fr/sandbox/ffeddersen/shoal_RE0_BO4000.c",
                   author_setup_sha256="e09a4e6bfd5fb83031f49839e0edf66775fa0c3bf5fb0896eb8b180500840ebd",
                   gcc=ver("gcc --version"), mpicc=ver("mpicc --version"), ffmpeg=ver("ffmpeg -version"), python=sys.version.split()[0],
                   numpy=ver("python3 -c 'import numpy; print(numpy.__version__)'"), scipy=ver("python3 -c 'import scipy; print(scipy.__version__)'"),
                   skimage=ver("python3 -c 'import skimage; print(skimage.__version__)'"), matplotlib=ver("python3 -c 'import matplotlib; print(matplotlib.__version__)'")),
        inputs={p: sha(os.path.join(REPO, p)) for p in ("Tools/Basilisk/gw_shoal.c", "Tools/Basilisk/cases.json",
                                                         "Tools/GWWaveGen/ruler/s52_shape.py", "Tools/GWWaveGen/ruler/shape_measures.json",
                                                         "Tools/PaintingTruth/targets/main_wave_outline_envelope.json")},
        runs=runs,
        outputs={os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(EVID, "*"))) if os.path.basename(p) != "run.json"})
    json.dump(out, open(os.path.join(EVID, "run.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("算例", len(done), "動画", len(vids))


if __name__ == "__main__":
    main()
