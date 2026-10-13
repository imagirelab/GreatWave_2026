# -*- coding: utf-8 -*-
"""FLIP47：道具が共に使う物（numpy だけ。hython からも py -3.10 からも読む）。
2026-10-12 FLIP46 の g46_common.py（Tools/GWWaveGen/flip46、変えていない）を写して、2D の板の水槽に直した。
計画：Docs/Research/BigWave_Recipes_ja.md §5.1「E1a」（Feddersen・Hanson・Mostert・Fincham 2024、JFM 1000 A48 を h0 19 m の実物の大きさで）。

座標（計画の座標）：x＝波の進む向き、y＝上（静かな水面 0、平らな所の海底 −h0）、z＝板の厚さ（真ん中が 0、±Lz/2 が滑る壁）。
Houdini の中は全部を o = (ox, oy, oz) だけずらして置く（Houdini = 計画 + o）。FLIP45 の読み方 R1 と同じ理由：Houdini の FLIP の場の格子は、
中心が世界の原点から格子の大きさの倍数に並び、閉じた壁は端の格子の面にある。計画の壁（x0・x1、箱の底、板の両面）を格子の面に置くため。
  ox = (vox/2 − x0) mod vox、oy = (vox/2 − y_floor) mod vox、oz = vox/2（板は z −2 vox〜+2 vox、格子 4 個）。
海底：折れ線（x, 水深）の点の並び（cfg の bed。水深は静かな水面から下へ正）。両端の外は端の水深で平ら。斜面・棚・段・2 段の海底を作れる。
  箱の底（閉じた壁）は、いちばん深い所より floor_pad 格子下（既定 2。FLIP44・46 と同じく海底を全部 SDF で）。
"""
import os, json, math, hashlib, time, ctypes, subprocess
from ctypes import wintypes

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip47"
B47 = REPO + "/Unity/Build/FLIP47"
HIP = REPO + "/Houdini/FLIP47/g47_tank.hiplc"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
SOL_DIR = B47 + "/solitary"
TOOLS46 = REPO + "/Tools/GWWaveGen/flip46"          # 厳密な孤立波 g46_solitary.py（読むだけ。変えない）

G = 9.80665
FPS = 24.0

# ------------------------------------------------------------------ E1a（Feddersen ら 2024 を h0 19 m に）
H0 = 19.0                         # 水深 h0 (m)
TS = math.sqrt(H0 / G)            # 時間の単位 √(h0/g) = 1.392 s
A_OVER_H = 0.6                    # 孤立波 a0/h0
X0_CREST = 15.0 * H0              # 285 m（全部の領域）
SLOPE = 0.0693                    # 勾配
X_TOE = 30.0 * H0                 # 570 m（斜面の足）
H_SHELF = 0.371 * H0              # 7.049 m（棚の水深）
X_TOP = X_TOE + (H0 - H_SHELF) / SLOPE     # 742.45 m（棚の始め。論文 39.08 h0 = 742.5 m）
X_END_FULL = 1130.0               # 全部の領域の終わり（壁）。棚は 742.45〜1130 m（20.4 h0）
SHORT_X = (20.0 * H0, 47.0 * H0)  # 短い領域 380〜893 m
X0_CREST_SHORT = 25.0 * H0        # 475 m
BED_E1A = [[0.0, H0], [X_TOE, H0], [X_TOP, H_SHELF], [X_END_FULL, H_SHELF]]

# 使ってよい粒子（2 進で割り切れる物だけ。FLIP42 R4・FLIP46：割り切れない大きさは場の端がずれ、圧力 0・自由落下になった）
PLAN_DP = (0.5, 0.25, 0.125, 0.0625)


def is_binary_exact(v, bits=20):
    s = float(v) * (1 << bits)
    return abs(s - round(s)) == 0.0 and float(v) > 0


def check_dp(dp):
    if float(dp) not in PLAN_DP or not is_binary_exact(dp):
        raise ValueError("粒子 %r m は使わない（2 進で割り切れる %s m だけ）" % (dp, "・".join(repr(v) for v in PLAN_DP)))
    return float(dp)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rup(v, q):
    n = math.ceil(v / q - 1e-9)
    return n * q, n


# ------------------------------------------------------------------ 海底（折れ線）
def bed_points(bed):
    """cfg の bed（[[x, 水深], ...]、x は増える順）を確かめて返す。"""
    pts = [[float(a), float(b)] for a, b in bed]
    if len(pts) < 1:
        raise ValueError("海底の点がない")
    for i in range(len(pts) - 1):
        if not pts[i + 1][0] >= pts[i][0]:
            raise ValueError("海底の点の x が増える順でない: %r" % (pts,))
    return pts


def bed_string(bed):
    """CTRL の bed_prof（「x0 d0 x1 d1 ...」、repr の桁で 64 ビットのまま）。"""
    return " ".join("%r %r" % (float(a), float(b)) for a, b in bed_points(bed))


def parse_bed_string(s):
    v = [float(t) for t in str(s).split()]
    return [[v[2 * i], v[2 * i + 1]] for i in range(len(v) // 2)]


def bed_y(x, bed):
    """海底の高さ（計画の y、上向き。静かな水面 0）。両端の外は端の水深で平ら。"""
    import numpy as np
    p = bed_points(bed)
    bx = np.array([a for a, _ in p]); bd = np.array([b for _, b in p])
    return -np.interp(np.asarray(x, dtype=np.float64), bx, bd)


def max_depth(bed):
    return max(b for _, b in bed_points(bed))


# ------------------------------------------------------------------ 箱
def box(dp, x0, x1, bed, floor_pad=2, y_top=None, nz_cells=4):
    """粒子から箱の数（計画の座標）。x は x0 から格子の倍数に切り上げ、縦はいちばん深い所の下 floor_pad 格子から y_top（既定 h0 の
    いちばん深い水深と同じ高さ）まで、板の厚さは格子 nz_cells 個。ずらし o は FLIP45・46 と同じ式。"""
    dp = float(dp)
    vox = 2.0 * dp
    Lx, nx = rup(float(x1) - float(x0), vox)
    hmax = max_depth(bed)
    y_floor = -hmax - int(floor_pad) * vox
    yt = hmax if y_top is None else float(y_top)
    Hy, ny = rup(yt - y_floor, vox)
    Lz = nz_cells * vox
    b = dict(dp=dp, vox=vox, x0=float(x0), x1=float(x0) + Lx, Lx=Lx, y_floor=y_floor, y_top=y_floor + Hy, Hy=Hy, Lz=Lz,
             floor_pad=int(floor_pad), hmax=hmax, cells=[nx, ny, int(nz_cells)])
    b["ox"] = (0.5 * vox - float(x0)) % vox
    b["oy"] = (0.5 * vox - y_floor) % vox
    b["oz"] = (0.5 * vox) % vox
    for k in ("x0", "x1", "Lx", "y_floor", "y_top", "Hy", "Lz", "ox", "oy", "oz"):
        if not is_binary_exact(abs(b[k]) if b[k] != 0 else 1.0):
            raise ValueError("箱の %s = %r が 2 進で割り切れない" % (k, b[k]))
    return b


def frames_for(t_end, t0=0.0):
    return int(round((t_end - t0) * FPS)) + 1


def t_of_frame(f, t0=0.0):
    return t0 + (f - 1) / FPS


# ------------------------------------------------------------------ GN の孤立波（BigWave_Recipes_ja.md §5.1 の式 (2.4)(2.5)）
def gn_params(a0, h0, g=G):
    C = math.sqrt(g * h0 * (1.0 + a0 / h0))
    kap = math.sqrt(3.0 * (a0 / h0) / (4.0 * (1.0 + a0 / h0))) / h0
    return C, kap


def gn_solitary(x, z, a0, h0, x0, t=0.0, g=G):
    """η0 = a0 sech²(κ (x − x0 − C t))、u = C η/(h0 + η)（深さによらない）、w = −C h0 (z + h0) ∂η/∂x / (h0 + η)²。
    x・z は配列（z は静かな水面 0、上向き）。返り値 eta[nx]、u[nz, nx]、w[nz, nx]、C。水面より上は NaN。"""
    import numpy as np
    x = np.asarray(x, dtype=np.float64); z = np.asarray(z, dtype=np.float64)
    C, kap = gn_params(a0, h0, g)
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


def gn_point(x, z, a0, h0, x0, t=0.0, g=G):
    """1 点の (eta, u, w)。水面より上でも式の値（確かめの表のため）。"""
    C, kap = gn_params(a0, h0, g)
    xi = x - x0 - C * t
    s2 = 1.0 / math.cosh(kap * xi) ** 2
    eta = a0 * s2
    etax = -2.0 * a0 * kap * s2 * math.tanh(kap * xi)
    return eta, C * eta / (h0 + eta), -C * h0 * (z + h0) * etax / (h0 + eta) ** 2


def travel_estimate(bed, x_from, x_to, a0, h0=H0, g=G, dx=0.5):
    """頂の走る時間の目安：c = √(g (h + a))、a は Green の式 a0 (h0/h)^¼（勾配の上の振幅の増え。上の目安）。"""
    import numpy as np
    xs = np.arange(float(x_from), float(x_to), dx)
    h = -bed_y(xs, bed)
    a = a0 * (h0 / h) ** 0.25
    return float(np.sum(dx / np.sqrt(g * (h + a))))


# ------------------------------------------------------------------ 優先度と電力の抑え・主メモリー・hython の見張り（Windows。FLIP46 と同じ）
def unthrottle_self():
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
    out = subprocess.run(["tasklist", "/fi", "imagename eq hython.exe", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         encoding="mbcs", errors="ignore").stdout.lower()
    return "hython.exe" in out


def wait_no_hython(poll=60, max_wait_s=1800, log=None):
    """ほかの hython が動いていれば、poll 秒ごとに見て待つ（重い計算は一度に一つ）。max_wait_s を越えたら None を返す（始めない）。
    返り値：待った秒（始めてよい時）か None。"""
    t0 = time.time()
    n = 0
    while hython_running():
        if time.time() - t0 > max_wait_s:
            if log:
                log("gave up: another hython still running after %.0f s" % (time.time() - t0))
            return None
        if log and n % 5 == 0:
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

# ------------------------------------------------------------------ 速度の受け渡し（2026-10-13 板の層の差を調べる役）
# APIC（前からの既定）は 2D の板の −z の壁の側へ偽の横流れを作り、噴流と空洞の形が板の層で 2 倍違う（S2 で Ao/Hb² 0.13〜0.29）。
# FLIP（Velocity Smoothing 0.1 = Houdini の既定）にすると層の差は消える（0.30〜0.32）。新しい cfg はこちらを勧める。前の既定は変えない。
VELTRANSFER_RECOMMENDED = "flip"


def solver_for(veltransfer):
    """cfg の solver に足す物。apic は前のまま（足す物なし）。flip は Velocity Smoothing の既定 0.1 を書いて固定する。"""
    if veltransfer == "apic":
        return dict(veltransfer="apic")
    if veltransfer == "flip":
        return dict(veltransfer="flip", smoothing=0.1)
    raise ValueError("veltransfer は apic か flip")
