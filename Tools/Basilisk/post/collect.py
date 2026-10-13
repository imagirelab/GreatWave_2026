# -*- coding: utf-8 -*-
"""報告の証拠をまとめる：results.json（全部の算例の量）、top3.json、図、比べの動画、run.json（版・命令・SHA-256）、動画の写し。

使い方：python3 collect.py
置き場（環境変数）：GW_BIN（組み立てた gw_shoal）、GW_RUNS（計算の書き出し）、GW_ANA（gwcase の測った結果）、
GW_VIDEOS（算例ごとの動画。make_videos.py case で作る）、GW_EVID（出力。既定は Docs/Evidence/Basilisk）
比べの動画は COMPARE の組で、GW_VIDEOS にない時だけ作る。
"""
import os, sys, json, glob, shutil, hashlib, subprocess, platform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EVID = os.environ.get("GW_EVID", os.path.join(REPO, "Docs", "Evidence", "Basilisk"))
BIN = os.environ.get("GW_BIN", "/opt/gw/bin")
RUNS = os.environ.get("GW_RUNS", "/opt/gw/runs")
ANA = os.environ.get("GW_ANA", "/opt/gw/ana")
VIDEOS = os.environ.get("GW_VIDEOS", "/opt/gw/videos")
CASES = json.load(open(os.path.join(HERE, "..", "cases.json"), encoding="utf8"))
TOP3 = ["C04_L11", "C08_L11", "C03_L11"]
# 比べの動画の組（着水の時刻をそろえる）
COMPARE = {
    "compare_A": ["A_L10", "A_L11", "A_L12"],
    "compare_B": ["B_S1_L11", "B_S2_L11", "B_S5_L11", "C04_L11"],
    "compare_C": ["C04_L10", "C08_L10", "C03_L10", "C07_L10", "C12_L10", "C17_L10"],
}
# 組み立ての命令（README と同じ）
QCC = {
    "gw_shoal_t": "qcc -O2 -Wall -disable-dimensions -DTENSION=1 gw_shoal.c -o $GW_BIN/gw_shoal_t -lm",
    "gw_shoal_n": "qcc -O2 -Wall -disable-dimensions -DTENSION=0 gw_shoal.c -o $GW_BIN/gw_shoal_n -lm",
    "gw_shoal_t_mpi": "CC99='mpicc -std=c99 -D_GNU_SOURCE=1' qcc -O2 -disable-dimensions -D_MPI=1 -DTENSION=1 gw_shoal.c -o $GW_BIN/gw_shoal_t_mpi -lm",
    "gw_shoal_n_mpi": "CC99='mpicc -std=c99 -D_GNU_SOURCE=1' qcc -O2 -disable-dimensions -D_MPI=1 -DTENSION=0 gw_shoal.c -o $GW_BIN/gw_shoal_n_mpi -lm",
}


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
    import figures
    figures.EVID = EVID
    figures.fig_A_levels()
    figures.fig_score3(figures.bc_names(done), "fig_BC_score3.png", "B・C の score3（score3 最小のコマ）。格子の段は算例の名前の末尾（L10 = 10 段）")
    for lv in ("L11", "L12"):
        names = [n for n in ("B_S1_" + lv, "B_S2_" + lv, "B_S5_" + lv) if n in done]
        if names:
            figures.fig_shapes(names, "fig_B_shapes_%s.png" % lv,
                               "B（重力だけに近い条件、%s 段）。橙の線は原画の輪郭（縦÷1.3、頂の高さと位置を合わせた）" % lv[1:])
    figures.fig_shapes([n for n in TOP3 if n in done], "fig_top3.png", "C の上位 3 つを 11 段で解き直した結果。橙の線は原画の輪郭")
    # 比べの動画
    import make_videos
    for k, names in COMPARE.items():
        out = os.path.join(VIDEOS, k + ".mp4")
        if not os.path.exists(out) and all(n in done for n in names):
            make_videos.compare(out, names)
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
        rs = os.path.join(rd, "restarts.txt")
        runs[n] = dict(command=" ".join(RC.command(n, "$GW_BIN", "$GW_RUNS")), done=open(dn).read().strip() if os.path.exists(dn) else None,
                       restarted_at=open(rs).read().split() if os.path.exists(rs) else [],
                       n_win_frames=len(glob.glob(os.path.join(rd, "win_*.bin"))),
                       log_sha256=sha(os.path.join(rd, "log.txt")) if os.path.exists(os.path.join(rd, "log.txt")) else None)
    head = ver("git -C %s rev-parse HEAD" % REPO)
    out = dict(
        note_ja="雲の計算機（claude.ai/code）での Basilisk の計算の記録。書き出しそのものはリポジトリに入れていない",
        binary_note_ja=("全部の算例を、今の gw_shoal.c（途中の保存の event を含む）から組み立てた版で計算した。"
                        "途中の保存の event（Δt̃ 0.5 ごと）は時間の刻みを変えるので、それを入れる前の版の結果とは完全には同じにならない"
                        "（S2 の 10 段で score3 0.38 と 0.33）。前の版の結果は使っていない"),
        git_head_when_collected=head,
        machine=dict(cpu=ver("lscpu | grep 'Model name'"), cores=os.cpu_count(), os=platform.platform()),
        tools=dict(basilisk_tarball="https://basilisk.fr/basilisk/basilisk.tar.gz（2026-10-12 取得。日々変わる tarball で、同じ物はもう取れない見込み）",
                   basilisk_tarball_sha256="de851a91712aa83b0592e1e1ae8f7d7e2ffe1ade0266433434700f8c313fbed4",
                   author_setup="https://basilisk.fr/sandbox/ffeddersen/shoal_RE0_BO4000.c",
                   author_setup_sha256="e09a4e6bfd5fb83031f49839e0edf66775fa0c3bf5fb0896eb8b180500840ebd",
                   gcc=ver("gcc --version"), mpicc=ver("mpicc --version"), ffmpeg=ver("ffmpeg -version"), python=sys.version.split()[0],
                   numpy=ver("python3 -c 'import numpy; print(numpy.__version__)'"), scipy=ver("python3 -c 'import scipy; print(scipy.__version__)'"),
                   skimage=ver("python3 -c 'import skimage; print(skimage.__version__)'"), matplotlib=ver("python3 -c 'import matplotlib; print(matplotlib.__version__)'")),
        build=dict(commands=QCC, binaries_sha256={os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(BIN, "gw_shoal_*")))}),
        inputs={p: sha(os.path.join(REPO, p)) for p in ["Tools/Basilisk/gw_shoal.c", "Tools/Basilisk/cases.json", "Tools/Basilisk/run_cases.py",
                                                         "Tools/GWWaveGen/ruler/s52_shape.py", "Tools/GWWaveGen/ruler/s52_common.py",
                                                         "Tools/GWWaveGen/ruler/shape_measures.json",
                                                         "Tools/PaintingTruth/targets/main_wave_outline_envelope.json"]
                + ["Tools/Basilisk/post/" + os.path.basename(f) for f in sorted(glob.glob(os.path.join(HERE, "*.py")))]},
        compare_videos={k + ".mp4": dict(cases=v, command="python3 make_videos.py compare %s.mp4 %s" % (k, " ".join(v))) for k, v in COMPARE.items()},
        runs=runs,
        outputs={os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(EVID, "*"))) if os.path.basename(p) != "run.json"})
    json.dump(out, open(os.path.join(EVID, "run.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("算例", len(done), "動画", len(vids))


if __name__ == "__main__":
    main()
