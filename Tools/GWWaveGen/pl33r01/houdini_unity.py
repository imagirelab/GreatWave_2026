# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）：Unity の batchmode を 1 回動かす（run_pl33_unity.ps1 と同じ手順を Python で）。
Unity/Build/unity.lock を排他的に作ってから起動し、終わったら（失敗しても）消す。30 分を超えたら止める。同じプロジェクトの Unity は 1 つだけ。
ログは Unity/Build/Polish/33r01/houdini/logs/unity_<log>.log。Unity の TEMP・TMP は Unity/Build/Polish/33r01/houdini/tmp_env（C: の空きが少ない）。

usage: py -3.10 houdini_unity.py --method <Class.Method> --log <name> [--noquit] -- <Unity へ渡す引数 …>
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

ROOT = "G:/Unity/GreatWave_2026_Fresh"
PROJECT = ROOT + "/Unity"
LOCK = PROJECT + "/Build/unity.lock"
UNITY = "E:/6000.4.3f1/Editor/Unity.exe"
OUTD = PROJECT + "/Build/Polish/33r01/houdini"


def unity_running():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | ForEach-Object { $_.CommandLine }"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return False
    return "GreatWave_2026_Fresh\\Unity" in out or "GreatWave_2026_Fresh/Unity" in out


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        k = argv.index("--"); extra = argv[k + 1:]; argv = argv[:k]
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--noquit", action="store_true")
    ap.add_argument("--timeout-min", type=float, default=30.0)
    ap.add_argument("--wait-min", type=float, default=40.0)
    a = ap.parse_args(argv)
    if a.timeout_min > 30:
        raise SystemExit("1 回の計算は 30 分以内")
    logd = OUTD + "/logs"; os.makedirs(logd, exist_ok=True)
    tmpd = OUTD + "/tmp_env"; os.makedirs(tmpd, exist_ok=True)
    logf = logd + "/unity_" + a.log + ".log"
    t_end = time.time() + a.wait_min * 60
    got = False
    while not got:
        if not os.path.exists(LOCK) and not unity_running():
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ("PL33R01H " + a.log + " " + datetime.datetime.utcnow().isoformat() + "Z").encode("utf-8"))
                os.close(fd)
                got = True
                break
            except FileExistsError:
                pass
        if time.time() > t_end:
            raise SystemExit("unity.lock を取得できない（待ち時間の上限）")
        time.sleep(20)
    env = dict(os.environ); env["TEMP"] = tmpd.replace("/", "\\"); env["TMP"] = tmpd.replace("/", "\\")
    cmd = [UNITY, "-batchmode", "-projectPath", PROJECT.replace("/", "\\"), "-executeMethod", a.method, "-logFile", logf.replace("/", "\\")]
    if not a.noquit:
        cmd.append("-quit")
    cmd += extra
    t0 = time.time()
    code = -1
    try:
        p = subprocess.Popen(cmd, env=env)
        try:
            code = p.wait(timeout=a.timeout_min * 60)
        except subprocess.TimeoutExpired:
            p.kill(); code = -9
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass
    print("exit=%d seconds=%.1f log=%s" % (code, time.time() - t0, logf))
    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    main()
