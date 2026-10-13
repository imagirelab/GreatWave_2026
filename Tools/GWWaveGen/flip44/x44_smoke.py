# -*- coding: utf-8 -*-
"""FLIP44 煙の試し（計画 plan_ja.md §6、record_ja.md の「計画の読み方」と「計画から変えた所」1）を、名前の順に 1 本ずつ走らせる。
py -3.10 x44_smoke.py S1 S4i S4ii S2f S2 S2b S4b S4bc S8 [S4i@v2 ...]（「名前@版」は run_id「名前_版」で走らせ直す）
各試しは Unity/Build/FLIP44/smoke/<名前>/ に、cfg.json・log_cXXXX.txt と g44_run.py の記録を残す。判定は x44_smoke_check.py。
重い計算は一度に一つ（ほかの hython が動いていたら待つ）。g44_run.py が起動の始めに優先度を「通常より下」にし、電力の抑えを外す。
"""
import sys, os, json, subprocess, time, shutil
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_cfg as C

BASE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
SM = BASE + "/smoke"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
RUN = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44/g44_run.py"
TMP = BASE + "/tmp_houdini"
BEDX = [300.0, 320.0, 350.0, 400.0, 450.0, 470.0, 500.0, 530.0, 560.0, 600.0, 650.0, 700.0]


def spec(name):
    if name == "S1":
        c = C.make("S1", 0.5, prog="PR1", reef=0, f_end=240, ckpt_every=120, sec_t0=0.0, out_root="smoke",
                   note="S1：新しい場面が FLIP42 R1b と同じ計算をするか（礁なし・R3 の入口を表で・粒子 0.5 m・帯なし・240 コマ）")
        c["fieldbox_frames"] = [2]
        return [c]
    if name in ("S4i", "S4ii"):
        c = C.make(name, 0.5, prog="PR1", reef=0, f_end=168, ckpt_every=48, sec_t0=0.0, out_root="smoke",
                   wind=(dict(wind_on=1.0, wind_mode=1.0, wind_q=0.0, wind_t0=0.0, wind_tramp=1.0) if name == "S4ii" else None),
                   note="S4：S1 の 120 コマ目の途中保存から 48 コマ。%s" % ("(ii) 風の道具あり・q 0" if name == "S4ii" else "(i) 風の道具なし"))
        c["f_start"] = 121; c["f_first"] = 121
        c["from_ckpt"] = dict(run="S1", frame=120)
        return [c]
    if name == "S2f":
        c = C.make("S2f", 0.34375, prog="PR1", reef=0, amp_gain=0.0, f_end=120, ckpt_every=120, sec_t0=1e9, out_root="smoke",
                   note="S2f：礁なし・入口の振幅 0・粒子 0.34375 m・120 コマ（S2 の比べの元）")
        c["pstats_frames"] = [1, 2, 60, 120]; c["fieldbox_frames"] = [2]
        return [c]
    if name == "S2":
        c1 = C.make("S2", 0.34375, prog="PR1", reef=1, amp_gain=0.0, f_end=60, ckpt_every=60, sec_t0=1e9, out_root="smoke",
                    note="S2：礁あり・入口の振幅 0・粒子 0.34375 m。120 コマを 2 回の起動に分ける（1 回目 1〜60）")
        c1["pstats_frames"] = [1, 2, 60]; c1["fieldbox_frames"] = [2]; c1["bedcheck"] = dict(frame=2, x_rel=BEDX)
        c2 = dict(json.loads(json.dumps(c1)), f_start=61, f_end=120, note="S2：2 回目の起動（61〜120、60 コマ目の途中保存から）")
        c2["pstats_frames"] = [61, 120]; c2["fieldbox_frames"] = []; c2.pop("bedcheck")
        return [c1, c2]
    if name == "S2b":
        c = C.make("S2b", 0.25, prog="PR1", reef=1, amp_gain=0.0, f_end=24, ckpt_every=240, sec_t0=1e9, out_root="smoke",
                   note="S2b：礁あり・入口の振幅 0・粒子 0.25 m・24 コマ")
        c["ckpt_on"] = 0
        c["pstats_frames"] = [1, 2, 24]; c["fieldbox_frames"] = [2]
        return [c]
    if name in ("S4b", "S4bc"):
        c = C.make(name, 0.5, prog="PR1", reef=0, amp_gain=0.0, relax_g=0.0, Lx=160.0, xa0_rel=1e6, f_end=(492 if name == "S4b" else 24),
                   minsub=(1 if name == "S4b" else 3), sec_t0=1e9, out_root="smoke",
                   wind=dict(wind_on=1.0, wind_mode=3.0, wt_p0=2000.0, wt_lam=40.0, wt_ramp=10.0),
                   note="%s：水面の圧力の試しの形 p = 2,000 cos(2πx/40) Pa（10 s で上げる）を本番と同じ繋ぎで。水槽 160 m・粒子 0.5 m%s" % (
                       name, "" if name == "S4b" else "・最小の小刻み 3（呼ばれた回数の試し）"))
        c["ckpt_on"] = 0
        c["fieldbox_frames"] = [2]
        return [c]
    if name == "S8":
        c = C.make("S8", 0.5, prog="RPreef", reef=1, reef_shift=-300.0, Lx=600.0, xa0_rel=400.0, f_end=1152, ckpt_every=576, sec_t0=0.0,
                   sec_x_rel=[0.0, 400.0], out_root="smoke",
                   note="S8：礁の上を波が数周期通っても止まらないか。水槽 600 m・礁を 300 m 寄せた・繰り返しの入口・粒子 0.5 m・48 s")
        c["fieldbox_frames"] = [2]
        return [c]
    if name == "S8b":
        c = spec("S8")[0]
        c["f_start"] = 1153; c["f_end"] = 1632
        c["fieldbox_frames"] = []
        c["note"] = "S8 の続き（1,152 コマ目の途中保存から 1,632 コマ目＝68 s まで。record_ja.md の計画から変えた所 5）"
        return [c]
    if name == "S9b":
        c = spec("S9")[0]
        c["run_id"] = "S9b"
        c["f_start"] = 1153; c["f_first"] = 1153; c["f_end"] = 1200
        c["from_ckpt"] = dict(run="S8", frame=1152)
        c["parms"]["wind_t0"] = 48.0
        c["stop_touchdown"]["t_from"] = 48.0
        c["note"] = "S9b：S9 を S8 の 1,152 コマ目（47.96 s）の途中保存から 48 コマでやり直す。風は 48.0 s から 1 s で上げる（record_ja.md の計画から変えた所 5）"
        return [c]
    if name == "S1b":
        c = C.make("S1b", 0.25, prog="PR1", reef=0, f_end=120, ckpt_every=240, sec_t0=1e9, out_root="smoke",
                   note="S1b：S1 と同じ比べを粒子 0.25 m・120 コマで FLIP42 R3 と行う（記録だけ。費用の見込みの比のため）")
        c["ckpt_on"] = 0
        return [c]
    if name == "S9":
        q = 0.5 * 1.2 * (45.0 + 12.0) ** 2
        xp = C.plan()["tank"]["x_p"]
        c = C.make("S9", 0.5, prog="RPreef", reef=1, reef_shift=-300.0, Lx=600.0, xa0_rel=400.0, f_end=624, ckpt_every=48, sec_t0=0.0,
                   sec_x_rel=[0.0, 400.0], out_root="smoke",
                   wind=dict(wind_on=1.0, wind_mode=1.0, wind_q=q, wind_t0=24.0, wind_tramp=1.0, wind_t1=1e9, wind_x0=xp, wind_x1=xp + 400.0),
                   note="S9：はがれた流れの形（S）の風の圧力（U10 45 m/s、q %.1f Pa）を DOP で書く試し。S8 の 576 コマ目の途中保存から 48 コマ" % q)
        c["f_start"] = 577; c["f_first"] = 577
        c["from_ckpt"] = dict(run="S8", frame=576)
        c["record_psec"] = True
        c["stop_touchdown"] = dict(after_s=0.5, t_from=24.0, Lc=C.plan()["tank"]["Lc"], still_offset_m=0.0)
        return [c]
    raise SystemExit("unknown " + name)


def hython_running():
    return "hython" in subprocess.run(["tasklist"], capture_output=True, text=True, encoding="mbcs", errors="ignore").stdout.lower()


def run_one(c):
    rd = os.path.join(SM, c["run_id"])
    os.makedirs(os.path.join(rd, "ckpt"), exist_ok=True)
    fc = c.get("from_ckpt")
    if fc:
        src = os.path.join(SM, fc["run"], "ckpt", "v.%04d.sim" % fc["frame"])
        dst = os.path.join(rd, "ckpt", "v.%04d.sim" % fc["frame"])
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    p = os.path.join(rd, "cfg_c%04d.json" % c["f_start"])
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    if c["f_start"] == c.get("f_first", 1):
        json.dump(c, open(os.path.join(rd, "cfg.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    while hython_running():
        time.sleep(5)
    env = dict(os.environ, HOUDINI_TEMP_DIR=TMP, TEMP=TMP, TMP=TMP)
    os.makedirs(TMP, exist_ok=True)
    t0 = time.time()
    with open(os.path.join(rd, "log_c%04d.txt" % c["f_start"]), "w", encoding="utf8", errors="ignore") as lg:
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n"); lg.flush()
        subprocess.run([HY, RUN, p], stdout=lg, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
        lg.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    print(time.strftime("%H:%M:%S"), c["run_id"], c["f_start"], "-", c["f_end"], "%.1f s" % (time.time() - t0), flush=True)


def spec_v(name):
    """「名前@版」なら、同じ試しを run_id「名前_版」で走らせる（場面を直した後の走らせ直し。前の記録は消さずに残す）。"""
    if "@" not in name:
        return spec(name)
    base, ver = name.split("@", 1)
    out = []
    for c in spec(base):
        c = json.loads(json.dumps(c))
        c["run_id"] = "%s_%s" % (c["run_id"], ver)
        c["note"] = c.get("note", "") + "（%s：場面を直した後の走らせ直し）" % ver
        out.append(c)
    return out


if __name__ == "__main__":
    for nm in sys.argv[1:]:
        for c in spec_v(nm):
            run_one(c)
    print("all done", time.strftime("%H:%M:%S"))
