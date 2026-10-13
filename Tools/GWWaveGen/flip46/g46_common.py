# -*- coding: utf-8 -*-
"""FLIP46：道具が共に使う物（numpy だけ。hython からも py -3.10 からも読む）。
2026-10-12 FLIP45 の g45_common.py（Tools/GWWaveGen/flip45、変えていない）を写して、FLIP46 の分だけ直した。
計画：Docs/Research/BigWave_Recipes_ja.md §5.2「E1b」（Guyenne & Grilli 2006 を実物の大きさで。h0 17 m、長さ × 17 m、時間 × √(h0/g) = 1.316 s）。

座標（FLIP45 と同じ決まり）：計画の x＝波の進む向き（x = 0 が上流の壁）、y＝横（y = 0 が対称の面）、z＝上（静かな水面 0、平らな海底 −17 m）。
Houdini の中は x はそのまま、上が y、横が z。全部を o = (ox, oy, oz) だけずらす（Houdini = 計画 + o。壁を格子の面に置くため。FLIP45 の読み方 R1）。
この道具の関数の引数は、断りのない限り計画の座標（x, y_lat, z_up）。

FLIP45 から変えた所：
  - 置き場所（flip46・Build/FLIP46・Houdini/FLIP46）
  - 定数（水深 17 m、尾根の形、孤立波 H0/h0 0.6、頂 x0 98.345 m）。入口の表・帯・利得の定数は持ち込まない
  - 箱：x 0〜323 m、横 0〜68 m、縦 −17〜+17 m（格子の倍数に切り上げ。粒子 1.0 m の煙の試しだけ x が 324 m になる）
  - 尾根の海底の式 bed_z（numpy）と、GN の孤立波の式 gn_solitary（煙の試しの代わりの npz と確かめのため）
"""
import os, json, math, hashlib, time, ctypes
from ctypes import wintypes

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip46"
B46 = REPO + "/Unity/Build/FLIP46"
HIP = REPO + "/Houdini/FLIP46/g46_tank.hiplc"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
SOL_DIR = B46 + "/solitary"
GN_PLACEHOLDER = SOL_DIR + "/gn_placeholder_a0p6.npz"     # g46_gn_npz.py が作る（Tanaka の解 g46_solitary.write_grid が出るまでの代わり）
SOL_TANAKA = SOL_DIR + "/tanaka_a0p6.npz"              # Tanaka（1986）の厳密な解の置き場所の約束（g46_solitary.write_grid が書く。あれば g46_cfg.py が使う）

G = 9.80665
H0 = 17.0                       # 水深 h0 (m)
TS = math.sqrt(H0 / G)          # 時間の単位 √(h0/g) = 1.3166 s
FPS = 24.0
A0 = 0.6                        # 孤立波 H0/h0
X0_CREST = 5.785 * H0           # 98.345 m
RIDGE_X0 = 5.225 * H0           # 88.825 m（尾根の始まり）
RIDGE_S = 15.0                  # 真ん中の断面の勾配 1:15
RIDGE_K = 0.25                  # sech²(k y') の k（主の場合）
LX_PLAN = 19.0 * H0             # 323 m
W_PLAN = 4.0 * H0               # 68 m
Z_BOTTOM = -H0                  # −17 m（平らな所の海底 = 箱の底）
H_BOX = 2.0 * H0                # 34 m（−17 m から +17 m）

# 使ってよい粒子（2 進で割り切れる物だけ。FLIP42 R4：割り切れない大きさは場の端がずれ、圧力 0・自由落下になった）
PLAN_DP = (0.5, 0.25, 0.1767578125)
SMOKE_ONLY_DP = (1.0,)


def is_binary_exact(v, bits=20):
    """v × 2^bits が整数なら 2 進で割り切れる（0.5・0.25・181/1024・1.0 など）。0.2 や 0.3 は拒む。"""
    s = float(v) * (1 << bits)
    return abs(s - round(s)) == 0.0 and float(v) > 0


def check_dp(dp, smoke=False):
    ok = set(PLAN_DP) | (set(SMOKE_ONLY_DP) if smoke else set())
    if float(dp) not in ok or not is_binary_exact(dp):
        raise ValueError("粒子 %r m は使わない（2 進で割り切れる %s m だけ%s）" % (
            dp, "・".join(repr(v) for v in PLAN_DP), "。煙の試しは 1.0 m も" if smoke else ""))
    return float(dp)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rup(v, q):
    """v を q の倍数に切り上げ（浮動小数の誤りを除いて）。"""
    n = math.ceil(v / q - 1e-9)
    return n * q, n


def box(dp, Lx=LX_PLAN, W=W_PLAN, x0=0.0, floor_pad=0, side_pad=0):
    """粒子から箱の数。x は x0 から、横は 0 から、縦は −17 m から、どれも格子（粒子の 2 倍）の倍数に切り上げる。
    ずらし o は FLIP45 と同じ式（壁を格子の面に置く）。floor_pad：箱の底を −17 m より何格子下げるか（場面の CTRL の floor_pad）。"""
    dp = float(dp)
    vox = 2.0 * dp
    Lx_, nx = rup(float(Lx), vox)
    W_, nz = rup(float(W), vox)
    Hz, ny = rup(H_BOX, vox)
    b = dict(dp=dp, vox=vox, x0=float(x0), x1=float(x0) + Lx_, Lx=Lx_, W=W_, z_bottom=Z_BOTTOM, z_top=Z_BOTTOM + Hz, Hz=Hz,
             floor_pad=int(floor_pad), z_floor=Z_BOTTOM - int(floor_pad) * vox,
             cells=[nx, nz + int(side_pad), ny + int(floor_pad)], side_pad=int(side_pad), y_side_low=-int(side_pad) * vox)
    b["ox"] = (0.5 * vox - float(x0)) % vox
    b["oy"] = (0.5 * vox - Z_BOTTOM) % vox
    b["oz"] = (0.5 * vox) % vox
    for k in ("x1", "Lx", "W", "z_top", "Hz", "ox", "oy", "oz"):
        if not is_binary_exact(abs(b[k]) if b[k] != 0 else 1.0):
            raise ValueError("箱の %s = %r が 2 進で割り切れない" % (k, b[k]))
    return b


def frames_for(t0, t_end):
    return int(round((t_end - t0) * FPS)) + 1


def t_of_frame(f, t0=0.0):
    return t0 + (f - 1) / FPS


# ------------------------------------------------------------------ 尾根と孤立波（numpy）
def bed_z(x, y_lat=0.0, k=RIDGE_K, x_toe=RIDGE_X0, s=RIDGE_S, h0=H0, on=True):
    """海底の高さ（静かな水面 0、上向き）。x < x_toe は −h0。x ≥ x_toe は −h0 h'(x', y')、
    h' = 1 − (x' − 5.225) sech²(k y') / 15（BigWave_Recipes_ja.md §5.2）。"""
    import numpy as np
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    if not on:
        return np.full(np.broadcast(x, y).shape, -h0)
    sh = 1.0 / np.cosh(k * y / h0)
    dep = h0 - np.maximum(x - x_toe, 0.0) * sh * sh / s
    return -dep


def gn_solitary(x, z, a0=A0 * H0, h0=H0, x0=X0_CREST, t=0.0, g=G):
    """Green–Naghdi の孤立波（BigWave_Recipes_ja.md §5.1 の式 (2.4)(2.5)）。x・z は配列（z は静かな水面 0、上向き）。
    返り値 eta(x)、u(z, x)、w(z, x)、C。u は深さによらない、w は (z + h0) に比例。水面より上の値は NaN（使う側が埋める）。"""
    import numpy as np
    x = np.asarray(x, dtype=np.float64); z = np.asarray(z, dtype=np.float64)
    C = math.sqrt(g * h0 * (1.0 + a0 / h0))
    kap = math.sqrt(3.0 * (a0 / h0) / (4.0 * (1.0 + a0 / h0))) / h0
    xi = x - x0 - C * t
    sech2 = 1.0 / np.cosh(kap * xi) ** 2
    eta = a0 * sech2
    etax = -2.0 * a0 * kap * sech2 * np.tanh(kap * xi)
    u1 = C * eta / (h0 + eta)
    U = np.broadcast_to(u1[None, :], (len(z), len(x))).copy()
    Wv = -C * h0 * (z[:, None] + h0) * etax[None, :] / (h0 + eta[None, :]) ** 2
    above = z[:, None] > eta[None, :]
    U[above] = np.nan; Wv[above] = np.nan
    return eta, U, Wv, C


# ------------------------------------------------------------------ 優先度と電力の抑え・主メモリー（Windows）（FLIP45 と同じ）
def unthrottle_self():
    """自分の処理の優先度を「通常より下」にし、実行速度の抑え（EcoQoS）を使わないよう頼む。"""
    try:
        k = ctypes.WinDLL("kernel32", use_last_error=True)

        class PPTS(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.GetPriorityClass.argtypes = [wintypes.HANDLE]
        h = k.GetCurrentProcess()
        s = PPTS(1, 0x1, 0x0)
        r1 = bool(k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s)))
        r2 = bool(k.SetPriorityClass(h, 0x4000))
        return dict(pid=os.getpid(), power_throttling_off=r1, below_normal=r2, priority_class=hex(k.GetPriorityClass(h)),
                    time=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        return dict(pid=os.getpid(), error=repr(e)[:200])


def rss_gb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
    f = ctypes.windll.psapi.GetProcessMemoryInfo
    f.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    f(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**30, c.PeakWorkingSetSize / 2**30


def hython_running():
    """ほかの hython が動いているか（重い計算は一度に一つ）。"""
    import subprocess
    out = subprocess.run(["tasklist", "/fi", "imagename eq hython.exe", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         encoding="mbcs", errors="ignore").stdout.lower()
    return "hython.exe" in out


def wait_no_hython(poll=10, log=None):
    t0 = time.time()
    n = 0
    while hython_running():
        if log and n % 30 == 0:
            log("waiting: another hython is running (%.0f s)" % (time.time() - t0))
        n += 1
        time.sleep(poll)
    return time.time() - t0


def keep_awake():
    try:
        f = ctypes.windll.kernel32.SetThreadExecutionState
        f.argtypes = [ctypes.c_uint]; f.restype = ctypes.c_uint
        return bool(f(0x80000000 | 0x00000001))
    except Exception:
        return False


def free_gb(drive="G:/"):
    import shutil
    return shutil.disk_usage(drive).free / 1e9
