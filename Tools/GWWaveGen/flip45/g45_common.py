# -*- coding: utf-8 -*-
"""FLIP45：道具が共に使う物（numpy だけ。hython からも py -3.10 からも読む）。
2026-10-12 進行役が新しく書いた。計画：Unity/Build/FLIP45/plan/plan_ja.md（凍結版）。数：plan/plan_numbers.json（読むだけ）。

座標（計画の頭書き）：計画の x＝波の進む向き（造波板が x = 0）、y＝横（y = 0 が対称の面）、z＝上（静かな水面 0、海底 −20 m）。
Houdini の中は x はそのまま、上が y、横が z（FLIP44 と同じ）。この道具の関数の引数は、断りのない限り計画の座標（x, y_lat, z_up）。

入っている物：
  - 置き場所（道具・記録・場面・hython）
  - 定数（g = 9.80665、水深 20 m、Ω 0.8971 rad/s、周期 T、波数 K0、板の式 F0）
  - 2 進で割り切れる粒子の決まり（is_binary_exact。計画 §3：0.5・0.34375・0.25・0.1767578125 m。煙の試しだけ 1.0 m も使う）
  - 窓（layout）の箱：粒子ごとに、箱の長さを格子（粒子の 2 倍）の倍数に切り上げ、箱の底を −20 m ちょうどに置く（計画 §3）
  - 自分の処理の優先度を「通常より下」にし、Windows の電力の抑えを使わないよう頼む（FLIP42・44 と同じ設定）
"""
import os, json, math, hashlib, time, ctypes
from ctypes import wintypes

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen/flip45"
B45 = REPO + "/Unity/Build/FLIP45"
PLAN_DIR = B45 + "/plan"
PLAN_NUMBERS = PLAN_DIR + "/plan_numbers.json"
PLAN_FROZEN = PLAN_DIR + "/plan_frozen.json"
HIP = REPO + "/Houdini/FLIP45/g45_tank.hiplc"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
GAIN_FILE = B45 + "/gain/gain45.json"          # 入口の利得（煙の試し S2b・S2a から決めた物。決めた後は変えない。計画 §4.1）

G = 9.80665
D = 20.0
OM = 0.8971
T = 2 * math.pi / OM
FPS = 24.0
XF = 250.0
LH = 300.0
J = 60
Z_BOTTOM = -20.0
H_BOX = 36.0          # 箱の高さ（−20 m から +16 m。格子の倍数に切り上げる）
SIGMA_ABS = 2.37      # 吸う帯の速さ σ（1/s）。σ χ²（計画 §3.1）


def k_real(om, h=D):
    k = om * om / G
    for _ in range(80):
        f = G * k * math.tanh(k * h) - om * om
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


K0 = k_real(OM)
L0 = 2 * math.pi / K0
C0 = OM / K0
CG0 = C0 * 0.5 * (1 + 2 * K0 * D / math.sinh(2 * K0 * D))


def flap_F_real(k):
    kd = k * D
    return 4 * math.sinh(kd) * (1 - math.cosh(kd) + kd * math.sinh(kd)) / (kd * (math.sinh(2 * kd) + 2 * kd))


F0 = flap_F_real(K0)

# 使ってよい粒子（計画 §3）。SMOKE_ONLY は煙の試しだけ（格子 2 m も 2 進で割り切れる）
PLAN_DP = (0.5, 0.34375, 0.25, 0.1767578125)
SMOKE_ONLY_DP = (1.0,)


def is_binary_exact(v, bits=20):
    """v × 2^bits が整数なら 2 進で割り切れる（0.5・11/32・0.25・181/1024・1.0 など）。0.2 や 0.3 は拒む。"""
    s = float(v) * (1 << bits)
    return abs(s - round(s)) == 0.0 and float(v) > 0


def check_dp(dp, smoke=False):
    """計画の粒子でなければ（煙の試しは 1.0 m も）ValueError。"""
    ok = set(PLAN_DP) | (set(SMOKE_ONLY_DP) if smoke else set())
    if float(dp) not in ok or not is_binary_exact(dp):
        raise ValueError("粒子 %r m は使わない（計画 §3：2 進で割り切れる %s m だけ%s）" % (
            dp, "・".join(repr(v) for v in PLAN_DP), "。煙の試しは 1.0 m も" if smoke else ""))
    return float(dp)


def load_plan():
    return json.load(open(PLAN_NUMBERS, encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def frozen_ok():
    """凍結した 4 つのファイルの SHA-256 が plan_frozen.json と同じか。返り値 (ok, 違う物の一覧)。"""
    fr = json.load(open(PLAN_FROZEN, encoding="utf-8"))
    bad = []
    for e in fr["frozen"]:
        p = REPO + "/" + e["path"]
        if not os.path.exists(p) or sha256_file(p) != e["sha256"]:
            bad.append(e["path"])
    return (not bad), bad


def rup(v, q):
    """v を q の倍数に切り上げ（浮動小数の誤りを除いて）。"""
    n = math.ceil(v / q - 1e-9)
    return n * q, n


def box(layout, dp):
    """窓（plan_numbers の layouts の 1 つ、または同じ形の dict）と粒子から、箱の数（計画 §3）。
    x は layout["x"][0] から、横は 0 から、縦は −20 m から、どれも格子の倍数に切り上げる。帯の位置は計画の値のまま（m）。"""
    dp = float(dp)
    vox = 2.0 * dp
    x0, x1 = float(layout["x"][0]), float(layout["x"][1])
    Lx, nx = rup(x1 - x0, vox)
    W, nz = rup(float(layout["y"][1]) - float(layout["y"][0]), vox)
    Hz, ny = rup(H_BOX, vox)
    b = dict(dp=dp, vox=vox, x0=x0, x1=x0 + Lx, Lx=Lx, W=W, z_bottom=Z_BOTTOM, z_top=Z_BOTTOM + Hz, Hz=Hz,
             cells=[nx, nz, ny],
             inlet=[float(v) for v in layout["inlet"]], exit=[float(layout["exit"][0]), x0 + Lx],
             side=[float(layout["side"][0]), W], side_gen=float(layout["side_gen"]), side_sw=float(layout["side_sw"]))
    # Houdini の場の格子は、格子の中心が世界の原点からの格子の大きさの倍数に並び、閉じた壁は格子の面（中心から格子の半分）にある
    # 【測った：2026-10-12 煙の試しの確かめ probe_box、読み方 R1】。計画の壁（x0・横 0・底 −20 m）を格子の面に置くため、Houdini の中の座標を
    # 計画の座標から o = (ox, oy, oz) だけずらす（Houdini = 計画 + o）。どれも 0 以上・格子より小さく、2 進で割り切れる。
    b["ox"] = (0.5 * vox - x0) % vox
    b["oy"] = (0.5 * vox - Z_BOTTOM) % vox
    b["oz"] = (0.5 * vox) % vox
    for k in ("x0", "x1", "Lx", "W", "z_top", "Hz", "ox", "oy", "oz"):
        if not is_binary_exact(abs(b[k]) if b[k] != 0 else 1.0):
            raise ValueError("箱の %s = %r が 2 進で割り切れない" % (k, b[k]))
    return b


def frames_for(t0, t_end):
    """t0 から t_end（s）までのコマの数（コマ f の時刻は t0 + (f − 1)/24）。"""
    return int(round((t_end - t0) * FPS)) + 1


def t_of_frame(f, t0):
    return t0 + (f - 1) / FPS


# ------------------------------------------------------------------ 優先度と電力の抑え・主メモリー（Windows）
def unthrottle_self():
    """自分の処理の優先度を「通常より下」にし、実行速度の抑え（EcoQoS）を使わないよう頼む（g44_run.py と同じ設定）。"""
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
    """(今の主メモリー, 最大) GiB。"""
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
    """この処理が動いている間だけ Windows が眠らないように頼む（終わると元に戻る。電源の設定は変えない）。"""
    try:
        f = ctypes.windll.kernel32.SetThreadExecutionState
        f.argtypes = [ctypes.c_uint]; f.restype = ctypes.c_uint
        return bool(f(0x80000000 | 0x00000001))
    except Exception:
        return False


def free_gb(drive="G:/"):
    import shutil
    return shutil.disk_usage(drive).free / 1e9
