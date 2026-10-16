# -*- coding: utf-8 -*-
"""FLIP49：計算 1 本（g49_chain.py）を子として起動し、走る間の主メモリーと約束の量（commit）を見張って記録する（py -3.10、numpy も要らない）。
2026-10-16 新しく書いた（PROBE025：粒子 0.25 m の主メモリー・時間の短い試し。probe, not a result）。
  - 2 s ごとに：主メモリーの空き・約束の量の上限と余り（GlobalMemoryStatusEx）、子の chain の下の hython.exe の作業セット・私用の約束の量
    （PrivateUsage）・その最大（GetProcessMemoryInfo）を <記録>/memwatch.csv に書く。
  - 約束の量の余りが --kill_commit_gb（既定 2.0 GB）より少ないか、主メモリーの空きが --kill_avail_gb（既定 1.5 GB）より少なければ、
    子の chain の下の hython だけを止め（TerminateProcess）、<記録>/STOP（chain が次の起動をしない）と STOPPED_MEMWATCH.txt を書く。
    この PC はページファイルが 1 GB（C:）で、約束の量が上限に届くと hython だけでなくほかのアプリも落ちうるため。
  - <記録>/log_c*.txt に新しく出た行に時刻を付けて <記録>/memwatch_logts.txt に写す（24 コマごとの行の間の時間 = 記録を含む全部の時間）。
使い方：py -3.10 g49_memwatch.py <cfg.json> [--kill_commit_gb=2.0] [--kill_avail_gb=1.5] [--poll=2]
"""
import sys, os, json, time, glob, subprocess, ctypes
from ctypes import wintypes

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g49_common as GC     # noqa: E402

k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


class MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class PMCX(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
k32.OpenProcess.restype = ctypes.c_void_p
k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PE32)]
k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PE32)]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
GB = float(2 ** 30)


def sysmem():
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    k32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / GB, m.ullAvailPageFile / GB, m.ullTotalPageFile / GB, m.ullTotalPhys / GB


def procs():
    """[(pid, ppid, exe)]"""
    out = []
    h = k32.CreateToolhelp32Snapshot(0x2, 0)
    if not h or h == ctypes.c_void_p(-1).value:
        return out
    e = PE32(); e.dwSize = ctypes.sizeof(PE32)
    ok = k32.Process32FirstW(h, ctypes.byref(e))
    while ok:
        out.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile.lower()))
        ok = k32.Process32NextW(h, ctypes.byref(e))
    k32.CloseHandle(h)
    return out


def descendants(root, pl):
    kids = {root}
    grew = True
    while grew:
        grew = False
        for pid, ppid, _ in pl:
            if ppid in kids and pid not in kids:
                kids.add(pid); grew = True
    return kids


def pmem(pid):
    h = k32.OpenProcess(0x1000 | 0x0010, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
    if not h:
        return None
    c = PMCX(); c.cb = ctypes.sizeof(PMCX)
    ok = psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    k32.CloseHandle(h)
    if not ok:
        return None
    return c.WorkingSetSize / GB, c.PrivateUsage / GB, c.PeakWorkingSetSize / GB, c.PeakPagefileUsage / GB


def kill(pid):
    h = k32.OpenProcess(0x0001, False, pid)               # PROCESS_TERMINATE
    if not h:
        return False
    ok = bool(k32.TerminateProcess(h, 99))
    k32.CloseHandle(h)
    return ok


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {a[2:].split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    cfgp = os.path.abspath(pos[0])
    cfg = json.load(open(cfgp, encoding="utf8"))
    rd = os.path.join(GC.B49, cfg.get("out_root", "runs"), cfg["run_id"])
    os.makedirs(rd, exist_ok=True)
    kc = float(opt.get("kill_commit_gb", 2.0)); ka = float(opt.get("kill_avail_gb", 1.5)); poll = float(opt.get("poll", 2.0))
    csvp = os.path.join(rd, "memwatch.csv"); tsp = os.path.join(rd, "memwatch_logts.txt")
    new = not os.path.exists(csvp)
    fc = open(csvp, "a", encoding="utf8")
    if new:
        fc.write("time,elapsed_s,avail_phys_gb,commit_avail_gb,commit_limit_gb,hython_pid,ws_gb,private_gb,peak_ws_gb,peak_private_gb\n")
    a0, c0, cl, tp = sysmem()
    fc.write("# start %s cfg %s total_phys_gb %.2f commit_limit_gb %.2f avail_phys_gb %.2f commit_avail_gb %.2f kill_commit_gb %.1f kill_avail_gb %.1f\n"
             % (time.strftime("%Y-%m-%d %H:%M:%S"), cfgp, tp, cl, a0, c0, kc, ka)); fc.flush()
    T0 = time.time()
    child = subprocess.Popen([sys.executable, "-B", os.path.join(HERE, "g49_chain.py"), cfgp], stdin=subprocess.DEVNULL)
    seen = {lp: os.path.getsize(lp) for lp in glob.glob(os.path.join(rd, "log_c*.txt"))}   # 前の起動の行は写さない（続きの時）
    peak = dict(private_gb=0.0, ws_gb=0.0, min_commit_avail_gb=c0, min_avail_phys_gb=a0)
    killed = None
    while True:
        rc = child.poll()
        av, ca, cl, _ = sysmem()
        pl = procs()
        mine = descendants(child.pid, pl)
        hy = [p for p, pp, ex in pl if p in mine and ex == "hython.exe"]
        row = None
        for pid in hy:
            m = pmem(pid)
            if m:
                row = (pid,) + m
                peak["private_gb"] = max(peak["private_gb"], m[1], m[3]); peak["ws_gb"] = max(peak["ws_gb"], m[0], m[2])
        peak["min_commit_avail_gb"] = min(peak["min_commit_avail_gb"], ca); peak["min_avail_phys_gb"] = min(peak["min_avail_phys_gb"], av)
        fc.write("%s,%.1f,%.3f,%.3f,%.3f,%s\n" % (time.strftime("%H:%M:%S"), time.time() - T0, av, ca, cl,
                                                ",".join("%.3f" % v if isinstance(v, float) else str(v) for v in row) if row else ",,,,"))
        fc.flush()
        if hy and (ca < kc or av < ka) and killed is None:
            open(os.path.join(rd, "STOP"), "w").write("memwatch\n")
            for pid in hy:
                kill(pid)
            killed = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), commit_avail_gb=ca, avail_phys_gb=av, pids=hy)
            open(os.path.join(rd, "STOPPED_MEMWATCH.txt"), "w", encoding="utf8").write(
                "%s 約束の量の余り %.2f GB（止める線 %.1f）か主メモリーの空き %.2f GB（止める線 %.1f）が足りないので hython %s を止めた（probe の見張り）\n"
                % (killed["time"], ca, kc, av, ka, hy))
        for lp in sorted(glob.glob(os.path.join(rd, "log_c*.txt"))):
            try:
                with open(lp, "r", encoding="utf8", errors="ignore") as fh:
                    fh.seek(seen.get(lp, 0)); txt = fh.read(); seen[lp] = fh.tell()
            except OSError:
                continue
            if txt:
                with open(tsp, "a", encoding="utf8") as ft:
                    for ln in txt.splitlines():
                        if ln.strip():
                            ft.write("%s %.1f %s | %s\n" % (time.strftime("%H:%M:%S"), time.time() - T0, os.path.basename(lp), ln))
        if rc is not None:
            break
        time.sleep(poll)
    summ = dict(end=time.strftime("%Y-%m-%d %H:%M:%S"), elapsed_s=round(time.time() - T0, 1), chain_rc=child.returncode, killed=killed,
                start=dict(avail_phys_gb=a0, commit_avail_gb=c0, commit_limit_gb=cl, total_phys_gb=tp), **peak,
                tags=dict(all="測定（GlobalMemoryStatusEx・GetProcessMemoryInfo、2 s ごと）"), label="probe, not a result")
    with open(os.path.join(rd, "memwatch_summary.jsonl"), "a", encoding="utf8") as fs:
        fs.write(json.dumps(summ, ensure_ascii=False) + "\n")
    fc.write("# end %s\n" % json.dumps(summ, ensure_ascii=False)); fc.close()
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
