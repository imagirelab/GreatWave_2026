# -*- coding: utf-8 -*-
"""FLIP3D：続けて読む再生の、記録のファイルをディスク（G:）から読む速さを、OS のファイルの写し（キャッシュ）を通さずに測る（py -3.10 -B、Windows だけ）。
2026-10-16 進行役（Claude）のサブエージェントが新しく書いた。読むだけ（書かない）。
  CreateFileW(FILE_FLAG_NO_BUFFERING) で記録のファイルを 1 つずつ、プレイヤーと同じ順（manifest の source_frames）に丸ごと読み、
  1 つの時間（ms）と全体の MB/s を書く。プレイヤー（FLIP3DStream）の readMs は OS の写しを通る（温かいかは分からない）ので、こちらがディスクの下限の目安。
  同じファイルを 2 回目に読む時もディスクから読む（NO_BUFFERING は写しを使わない）。
使い方：py -3.10 -B f3d_diskread.py <クリップのフォルダー名（Unity/Build/FLIP3D の下）> [--max N] [--rate 24] [--out <json>]
  --rate R：1 s に R 個の速さに合わせて読む（実時間の再生と同じ間隔。待つ間はディスクが空く）。なければ続けて読む（速さの上限）。
"""
import os, sys, json, time, ctypes
import ctypes.wintypes as W

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402

GENERIC_READ = 0x80000000
FILE_SHARE_READ, FILE_SHARE_WRITE = 1, 2
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x2000, 0x8000, 0x04
INVALID = ctypes.c_void_p(-1).value

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = W.HANDLE
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
k32.ReadFile.argtypes = [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
k32.CloseHandle.argtypes = [W.HANDLE]
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, W.DWORD, W.DWORD]
k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, W.DWORD]


def read_unbuffered(path, buf, cap):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None)
    if h == INVALID or h is None:
        raise OSError(ctypes.get_last_error(), "CreateFileW " + path)
    try:
        size = os.path.getsize(path)
        want = (size + 4095) // 4096 * 4096
        if want > cap:
            raise ValueError("buffer small")
        got = W.DWORD(0)
        total = 0
        while total < size:
            n = min(want - total, 8 << 20)
            if not k32.ReadFile(h, ctypes.c_void_p(buf + total), n, ctypes.byref(got), None):
                raise OSError(ctypes.get_last_error(), "ReadFile " + path)
            if got.value == 0:
                break
            total += got.value
        return min(total, size)
    finally:
        k32.CloseHandle(h)


def pct(a, q):
    a = sorted(a)
    return a[int(q * (len(a) - 1))] if a else None


def main():
    a = sys.argv[1:]
    clip = a[0]
    mx = int(a[a.index("--max") + 1]) if "--max" in a else 0
    rate = float(a[a.index("--rate") + 1]) if "--rate" in a else 0.0
    cdir = C.OUT + "/" + clip
    man = json.load(open(cdir + "/manifest.json", encoding="utf8"))
    if man["format"] != "GW45LIST1":
        raise SystemExit("GW45LIST1 の manifest だけ（記録のファイルを読む）")
    sd = os.path.normpath(os.path.join(cdir, man["stream_dir_rel"])) if man.get("stream_dir_rel") else man["stream_dir"]
    frames = man["source_frames"][: mx or None]
    cap = (max(man["source_bytes"]) + 4095) // 4096 * 4096 + 4096
    buf = k32.VirtualAlloc(None, cap, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    ms, nb = [], 0
    late = 0
    t0 = time.perf_counter()
    try:
        for i, f in enumerate(frames):
            if rate > 0:
                due = t0 + i / rate
                while True:
                    d = due - time.perf_counter()
                    if d <= 0:
                        break
                    time.sleep(min(d, 0.002))
            s = time.perf_counter()
            n = read_unbuffered(os.path.join(sd, "s_%05d.gw45s" % f), buf, cap)
            e = time.perf_counter()
            if rate > 0 and e > t0 + (i + 1) / rate:
                late += 1
            ms.append((e - s) * 1000.0)
            nb += n
    finally:
        k32.VirtualFree(ctypes.c_void_p(buf), 0, MEM_RELEASE)
    T = time.perf_counter() - t0
    busy = sum(ms) / 1000.0
    res = dict(clip=clip, where=sd, records=len(frames), bytes=nb, seconds=round(T, 3), rate=rate or None,
               MBps_wall=round(nb / 1e6 / T, 1), MBps_while_reading=round(nb / 1e6 / max(busy, 1e-9), 1),
               ms_p50=round(pct(ms, 0.5), 3), ms_p95=round(pct(ms, 0.95), 3), ms_p99=round(pct(ms, 0.99), 3), ms_max=round(max(ms), 3),
               late_vs_rate=(late if rate > 0 else None), hython_running=bool(os.popen('tasklist /FI "IMAGENAME eq hython.exe" /NH').read().count("hython")),
               note_ja="FILE_FLAG_NO_BUFFERING（OS の写しを通さない）。1 つずつ順に丸ごと読む。late_vs_rate は 1/rate s の枠を越えた数")
    out = a[a.index("--out") + 1] if "--out" in a else None
    if out:
        C.write_json(out, res)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
