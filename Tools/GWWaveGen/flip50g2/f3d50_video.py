# -*- coding: utf-8 -*-
"""FLIP3D videos of FLIP50 clips (py -3.10 -B; PIL + ffmpeg). 2026-10-17 written new (Claude).
flip3d/f3d_video.py compose_cont() writes DA3r captions ("DA3r ... 24 個/s ...") into every frame. This runs the UNCHANGED function in memory
with three exact, counted caption replacements taken from the clip's manifest (run id, record rate, what the record is), the flip50g
precedent (no file of flip3d is edited). The picture (Unity's rendering) is not changed; only the text bands differ.
  py -3.10 -B f3d50_video.py --cap <capture folder under Unity/Build/FLIP3D> [--crf 20] cseat cprint cmove
"""
import os, sys, json, inspect

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip3d")
import f3d_video as V        # noqa: E402  unchanged

RUN_TEXT = {   # 【選び】 short Japanese descriptions (numbers from the run cfgs / README item 11)
    "DM1A": "DM1A：向きを集めた周期のうねり T 12 s（±80°、30 成分）を横にまっすぐな 1:10 の斜面で崩す、粒子 0.5 m",
    "DF1A": "DF1A：向きを集めた周期のうねり T 10 s（±80°、30 成分）を横にまっすぐな 1:10 の斜面で崩す、粒子 0.5 m",
    "DG1": "DG1：DM1A の海底に崩れる所の両わきの浅い溝（深さ 3 m の型）を足した物、粒子 0.5 m",
    "DG1r": "DG1r：DG1 を途中保存から同じ物理で計算し直し、面を毎コマ書いた物、粒子 0.5 m",
    "DM1Ar": "DM1Ar：DM1A を途中保存から同じ物理で計算し直し、面を毎コマ書いた物、粒子 0.5 m",
}
OLD_TITLE = '"FLIP3D 試作（Unity で実時間に再生）DA3r：周期のうねり T 12 s・H 7.5 m、粒子 0.5 m — "'
OLD_LINE2 = '"面の記録は 24 個/s（計算の毎コマ。DA3 を途中保存から同じ物理で計算し直した DA3r）を 1 フレームずつ実時間で見せる。%.2f〜%.2f s を続けて 1 回（繰り返さない・継ぎ目なし）。"'
OLD_LINE3 = '"計算にない物：外の平らな海・霧・空・水の色。★ は DA3 の判定（score3）で原画に最も近い瞬間（崩れごと）。全幅と並びは計算の対称の面・壁の仮定で写した"'


def patched(capdir, names):
    d0 = V.C.OUT + "/" + capdir + "/" + names[0]
    cap = json.load(open(d0 + "/capture.json", encoding="utf8"))
    man = json.load(open(cap["dataDir"] + "/manifest.json", encoding="utf8"))
    short = (man.get("run_id") or os.path.basename(man.get("source_run", "")) or "?").split("_")[0]
    step = int(man.get("record_step_frames") or 1)
    rate = "%g 個/s（計算の%s）" % (man["record_fps"], "毎コマ" if step == 1 else "%d コマおき。各記録を %d フレーム見せる" % (step, step))
    title = "FLIP3D 試作（Unity で実時間に再生）" + RUN_TEXT.get(short, short) + " — "
    line2 = "面の記録は " + rate + "。%.2f〜%.2f s を続けて 1 回（繰り返さない・継ぎ目なし）。"
    line3 = ("計算にない物：外の平らな海（横 %.0f m の外）・霧・空・水の色。★ は %s の判定（score3）で原画に最も近い瞬間（崩れごと、最も近い記録）。"
             "横は計算の対称の面 y = 0 で写した" % (float(man.get("tank_half_width") or 0), short))
    src = inspect.getsource(V.compose_cont)
    for old, new in ((OLD_TITLE, repr(title)), (OLD_LINE2, repr(line2)), (OLD_LINE3, repr(line3))):
        n = src.count(old)
        if n != 1:
            raise SystemExit("caption text not found exactly once in f3d_video.compose_cont (%d): %s" % (n, old[:40]))
        src = src.replace(old, new)
    ns = dict(V.__dict__)
    exec(compile(src, V.__file__ + " [compose_cont, FLIP50 captions by flip50g2/f3d50_video.py]", "exec"), ns)
    return ns["compose_cont"]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if "--crf" in a:
        V.CRF = a[a.index("--crf") + 1]; del a[a.index("--crf"):a.index("--crf") + 2]
    if "--cap" not in a:
        print(__doc__); sys.exit(1)
    capdir = a[a.index("--cap") + 1]; del a[a.index("--cap"):a.index("--cap") + 2]
    names = a or ["cseat", "cprint", "cmove"]
    os.makedirs(V.VID, exist_ok=True)
    fn = patched(capdir, names)
    print(json.dumps([fn(nm, capdir) for nm in names], ensure_ascii=False, indent=1))
