# -*- coding: utf-8 -*-
"""FLIP52HS hs_hero_n3: the N3 hero clip - the EXISTING surface records of a hero re-record with ONLY their drawn shading normals recomputed,
played in the Unity FLIP3D player exactly like that hero (same clip timing, seat, print pose, move, capture settings), checked, captioned and
compared before / after (py -3.10 -B; numpy, scipy, PIL, ffmpeg; Unity batch only in `unity`). 2026-10-18 written new (Claude subagent).

Why (user 2026-10-18 ~16:35): "我留意到目前视频的网格非常明显 是不是精度不够的原因？ 如果是的话我希望提升一下精度再给我看看，我觉得现在的大型和动态
也许能达到导师的标准". The Unity comparison of this workflow (Unity/Build/FLIP52B/hires/unity_cmp/, hs_unity_compare.py + hs_unity_sheet.py)
ranked B N3 first: shape change exactly 0, the smoothest picture in every view (band detail -17 to -30 % at f2112, -9 to -22 % at f2149,
dark specks 0) [measured]; it does NOT remove the polygonal crest outline (0.6 m segments) [measured]. The true surfacing fix (Houdini
0.25 m voxels, a re-record from checkpoint 1152) is a later, separate step and is NOT done here.

N3 (= hs_mesh_smooth variant "N3", byte for byte the records judged in Unity): positions unchanged; area-weighted vertex normals from the
record's triangles (oriented like the stored Houdini normals), seam normals lateral 0, then 3 passes of one-ring normal averaging
(N <- normalize(N + one-ring mean); on the symmetry seam the mirror-symmetric ring); written like g52b_run.write_surface /
hs_mesh_smooth.write_srf (|lateral| < 1e-4 -> normal lateral 0, the same oct encoding). Only the normal block of a GW45SRF1 record changes:
this tool SPLICES the new normal block into the record's own bytes, so header, positions, velocities and triangles are byte-identical by
construction, and `apply` / `verify` check it on every record. The FLIP particles, the physics records (hf / r2 / r3 / volcorr / ckpt) and the
hero's own surf files are never opened for writing (they are not even read, except the surf records). SURFACING (DRAWING) CHANGED, PHYSICS
UNCHANGED - every manifest, caption, sheet and status line says so.

Heroes (--hero): E = DFG-2B-E, the user-accepted hero (Unity/Build/FLIP3D/clip_DFGB2Er_f1153_3001_r24_seatA_ds, h52b_hero.py design: seat A,
move f2149); V = DFG-2B-V, the valid twin (clip_DFGBVr_f1153_3001_r24_seat<A|B>_ds made by auto_heroV.py, h52b3_hero.py design: move f2156).
The hero tool module of that hero is imported UNCHANGED; its Hero object is re-pointed in memory to the N3 outputs (clip / capture / json
paths, short name <short>N3, one more honesty line) and its capture_args / cmd_capcheck / caption lines are used as they are, so the N3
captures are made "the same way" as the hero's. For V the module's write guard (E_PROTECTED) is narrowed in memory to the accepted DFG-2B-E
hero's own places (hero/, runs/, clip_DFGB2Er_, capture_DFGB2Er_, video FLIP3D_DFGB2Er_) because every N3 output lives under
Unity/Build/FLIP52B/hires/; this tool's own guard refuses any write outside --root.
Outputs (all new, never overwritten unless --force on a file this tool wrote), root Unity/Build/FLIP52B/hires/hero_N3/:
  <run_id>/surf/s_FFFFF.gw45s       the N3 records (same names, same sizes as the hero's), <run_id>/n3_apply.json, n3_verify.json
  clip_<short>N3_f<a>_<b>_r24_seat<S>_ds/   GW45LIST1 manifest that STREAMS the N3 records + bed.f32 (copied) + n3_clip.json
  capture_<short>N3_..._ds/{cseat,cprint,cmove}/   Unity frames (1920x1080, 24 fps, the hero's -f3d* arguments with the N3 clip)
  video/FLIP3D_<short>N3_..._{cseat,cprint,cmove}.mp4 (+ _sheet.jpg), FLIP3D_<short>N3_..._before_after*.jpg
  json/*.json                       unity / capcheck / schedule / video / sheet reports;  _unity_backup/<stamp>/  pre-batch scene + materials
  (f3d_unity.ps1 writes its log to its fixed folder Unity/Build/FLIP3D/logs/unity_<hero2b|heroV>_<short>N3_seat<S>.log, a new name.)

  py -3.10 -B hs_hero_n3.py plan      --hero E|V [--seat auto|A|B]        read only: inputs, outputs, Unity arguments, disk / memory, estimate
  py -3.10 -B hs_hero_n3.py selftest  --hero E|V [--seat ..]              read only: N3 bytes vs the judged test records, splice identity,
                                                                           schedule comparator, caption patch + title widths, manifest dry build
  py -3.10 -B hs_hero_n3.py apply     --hero E|V [--from F] [--to F] [--prio idle|below] [--root R]   N3 records (resumable, idempotent)
  py -3.10 -B hs_hero_n3.py verify    --hero E|V [--root R]               every N3 record vs its source: non-normal bytes identical, sizes, sha
  py -3.10 -B hs_hero_n3.py clip      --hero E|V [--dry] [--force]        the N3 clip folder (needs verify ok)
  py -3.10 -B hs_hero_n3.py unity     --hero E|V [--dry]                  free commit >= 8 GB, backup, f3d_unity.ps1, restore (pre-batch state)
  py -3.10 -B hs_hero_n3.py capcheck  --hero E|V                          the hero module's capcheck on the N3 capture + same schedule as the hero
  py -3.10 -B hs_hero_n3.py video     --hero E|V [--dry] [--force]        captioned mp4s (the hero's captions + one N3 honesty line)
  py -3.10 -B hs_hero_n3.py sheet     --hero E|V [--n3-cap DIR] [--no-measures]   before / after sheets (overview, 1:1, 1:1 contrast x2) + measures
Every command prints one JSON object as its last stdout line (the launcher reads it). Tags: [measured] records / captures, [computed]
derived, [chosen] rules.
"""
import os, sys
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "2"
import json, math, time, struct, hashlib, shutil, subprocess, ctypes, csv, glob, importlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                                    # noqa: E402
import hs_mesh_smooth as M                            # noqa: E402  (read_srf / topo / orient_sign / awn / smooth_normals / oct_encode, unchanged)

REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
TOOL = "Tools/GWWaveGen/flip52hs/hs_hero_n3.py"
B52B = REPO + "/Unity/Build/FLIP52B"
B52B3 = REPO + "/Unity/Build/FLIP52B3"
HIRES = B52B + "/hires"
ROOT_DEF = HIRES + "/hero_N3"
OUT3D = REPO + "/Unity/Build/FLIP3D"
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
UNITY_METHOD = "GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture"
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]
COMMIT_MIN_GB = 8.0                                   # [chosen] the project rule before any Unity batch
JOBS = "cseat,cprint,cmove"                           # [chosen] the task: cseat / cprint / cmove (the hero also had cstills)
N_AVG = 3                                             # N3: 3 one-ring normal averages (hs_mesh_smooth VARIANTS["N3"])
SEAM_WRITE = 1e-4                                     # hs_mesh_smooth.write_srf / g52b_run.write_surface seam rule
VIS_EMIN = -1.0                                       # [chosen] vertices with elevation >= -1 m: the visible side (below: the hidden under-water sheet)
TEST_N3 = HIRES + "/test_smooth/N3"                   # the N3 records judged in Unity (hs_mesh_smooth test, DFGB2Er frames)
HEROES = {
    "E": dict(name="DFG-2B-E", modpath=TOOLS + "/flip52bh", mod="h52b_hero",
              cfg=B52B + "/hero/cfg/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long.json",
              clip=OUT3D + "/clip_DFGB2Er_f1153_3001_r24_seat%s_ds", cap=OUT3D + "/capture_DFGB2Er_f1153_3001_r24_seat%s_ds",
              log_prefix="hero2b", judge_attr="JUDGE52B", seat_default="A",
              run_text_ja=("%s（表示の法線 N3）：DFG-2B-E（多くの周波数の組、a² の和 = DM1A）を 48 s の途中保存から同じ物理で計算し直し、"
                           "面を毎コマ、粒子 0.5 m")),
    "V": dict(name="DFG-2B-V", modpath=TOOLS + "/flip52b3h", mod="h52b3_hero",
              cfg=B52B3 + "/hero/cfg/DFGBVr_D19B_xf272p25_in5c0p6_tp3_dp0p5_c1152_t125_long.json",
              clip=OUT3D + "/clip_DFGBVr_f1153_3001_r24_seat%s_ds", cap=OUT3D + "/capture_DFGBVr_f1153_3001_r24_seat%s_ds",
              log_prefix="heroV", judge_attr="JUDGEV", seat_default=None,
              run_text_ja=("%s（表示の法線 N3）：DFG-2B-V（入口 n5 の位相の較正と横の帯 3 %% の弱め、a² の和 = DM1A）を 48 s の途中保存から"
                           "同じ物理で計算し直し、面を毎コマ、粒子 0.5 m。主役の候補")),
}
E_PROTECTED_NARROW = (B52B + "/hero/", B52B + "/runs/", OUT3D + "/clip_DFGB2Er_", OUT3D + "/capture_DFGB2Er_", OUT3D + "/video/FLIP3D_DFGB2Er_")
N3_EN = ("SURFACING (DRAWING) CHANGED, PHYSICS UNCHANGED: only the shading normals of the existing surface records were recomputed (N3: "
         "area-weighted vertex normals + %d one-ring averages); vertex positions, triangles and velocities are byte-identical to %s's records "
         "(shape change 0); particles and physics records untouched; the polygonal crest outline (0.6 m segments) remains")
N3_JA = ("表示の法線だけ N3 に変えた（面積で重み付けした法線を 1 リングで %d 回平均）。点の位置・三角形・粒子・物理は %s の記録と同じ"
         "（形の差 0）。頂の輪郭の 0.6 m の折れは残る")
SCHED_COLS = ("i", "s", "phase", "record", "sim_t", "frozen", "blend", "cx", "cy", "cz", "fov", "wanted", "sim_frame", "cut", "ended")
HEAD = struct.Struct("<8sIIdiIIffffffff")


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def emit(o):
    print(json.dumps(M.clean(o), ensure_ascii=False, default=str), flush=True)


def set_priority(kind):
    try:
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00000040 if kind != "below" else 0x00004000)   # IDLE / BELOW_NORMAL
        return "idle (IDLE_PRIORITY_CLASS)" if kind != "below" else "below normal (BELOW_NORMAL_PRIORITY_CLASS)"
    except Exception as e:
        return "not set: %r" % e


class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def commit_free_gb():
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9, m.ullTotalPageFile / 1e9


def disk_free_gb(p):
    return shutil.disk_usage(os.path.splitdrive(p)[0] + "/").free / 1e9


# ====================================================================== context: the hero, its module, the re-pointed Hero object
class Ctx:
    def __init__(self, a, need_src=True):
        self.hero = (opt(a, "--hero", "E") or "E").upper()
        if self.hero not in HEROES:
            raise SystemExit("--hero must be E or V")
        self.spec = spec = HEROES[self.hero]
        self.root = os.path.abspath(opt(a, "--root", ROOT_DEF)).replace("\\", "/").rstrip("/")
        if not self.root.startswith(HIRES + "/"):
            raise SystemExit("refused: --root must be under %s" % rel(HIRES))
        if spec["modpath"] not in sys.path:
            sys.path.insert(0, spec["modpath"])
        self.mod = mod = importlib.import_module(spec["mod"])            # unchanged module; adds flip50g2 / flip3d to sys.path itself
        self.seat = self.resolve_seat(opt(a, "--seat", "auto"))
        self.src_clip = spec["clip"] % self.seat
        self.src_cap = spec["cap"] % self.seat
        self.src_man = jload(self.src_clip + "/manifest.json")
        if need_src and not self.src_man:
            raise SystemExit("no source clip manifest %s (for V: auto_heroV.py must have finished)" % rel(self.src_clip))
        H = mod.Hero(spec["cfg"], seat=self.seat)
        self.src_short = H.short                                          # DFGB2Er / DFGBVr
        self.rid = H.rid
        self.src_honesty = H.honesty()
        H.short = self.src_short + "N3"
        tag = "%s_f%d_%d_r24_seat%s_ds" % (H.short, H.f0, H.f1, self.seat)
        H.clip_name, H.cap_name = "clip_" + tag, "capture_" + tag
        H.clip, H.cap = self.root + "/" + H.clip_name, self.root + "/" + H.cap_name
        rid, root = self.rid, self.root
        H.hj = lambda name: root + "/json/%s_%sN3.json" % (name, rid)
        self.n3_en = N3_EN % (N_AVG, self.src_short)
        self.n3_ja = N3_JA % (N_AVG, self.src_short)
        base_honesty = H.honesty
        H.honesty = lambda: base_honesty() + [self.n3_en]                 # instance override: every honesty list of the module gets the N3 line
        self.H = H
        self.tag = tag
        self.surf_out = root + "/" + rid + "/surf"
        self.video_dir = root + "/video"
        self.unity_log = "%s_%s_seat%s" % (spec["log_prefix"], H.short, self.seat)   # = the name the module's cmd_capcheck reads
        mod.hero_from_args = lambda _a: H                                 # in memory: the module's commands act on the N3 Hero
        if self.hero == "V":
            mod.E_PROTECTED = E_PROTECTED_NARROW                          # in memory: still protects every DFG-2B-E hero place
        self.frames = [int(f) for f in (self.src_man or {}).get("source_frames") or []]
        self.src_stream = self.stream_dir(self.src_clip, self.src_man) if self.src_man else None

    def resolve_seat(self, s):
        s = (s or "auto").upper()
        if s in ("A", "B"):
            return s
        if self.spec["seat_default"]:
            return self.spec["seat_default"]
        found = [x for x in ("A", "B") if os.path.exists(self.spec["clip"] % x + "/manifest.json")]
        if len(found) == 1:
            return found[0]
        if not found:
            return "A"                                                    # nothing exported yet (the caller reports the missing clip)
        raise SystemExit("both seat A and seat B clips exist for %s: pass --seat" % self.spec["name"])

    @staticmethod
    def stream_dir(clip, man):
        r = man.get("stream_dir_rel")
        if r:
            p = os.path.abspath(os.path.join(clip, r)).replace("\\", "/")
            if os.path.isdir(p):
                return p
        return (man.get("stream_dir") or "").replace("\\", "/")

    def guard(self, p):
        q = os.path.abspath(p).replace("\\", "/")
        if not q.startswith(self.root + "/"):
            raise SystemExit("refused: %s is outside %s" % (q, rel(self.root)))
        for pre in E_PROTECTED_NARROW:
            if q.lower().startswith(pre.lower()):
                raise SystemExit("refused: %s is an accepted-hero place" % q)
        return q

    def jdump(self, o, p):
        self.guard(p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(M.clean(o), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        return p

    def src_record(self, f):
        return "%s/s_%05d.gw45s" % (self.src_stream, f)

    def out_record(self, f):
        return "%s/s_%05d.gw45s" % (self.surf_out, f)


# ====================================================================== N3 on one record (splice of the normal block)
def layout(b):
    magic, ver, hb, t, fr, nv, nt = HEAD.unpack_from(b, 0)[:7]
    if magic != b"GW45SRF1":
        raise ValueError("not GW45SRF1")
    o_n = hb + nv * 6
    o_e = o_n + nv * 4
    if hb + nv * 16 + nt * 12 != len(b):
        raise ValueError("GW45SRF1 size %d != %d" % (len(b), hb + nv * 16 + nt * 12))
    return dict(frame=int(fr), t=float(t), nv=int(nv), nt=int(nt), hb=int(hb), o_n=int(o_n), o_e=int(o_e))


def decode(b):
    """positions, stored normals, triangles of a GW45SRF1 record held in memory (= hs_mesh_smooth.read_srf, from bytes)."""
    magic, ver, hb, t, fr, nv, nt, x0, y0, z0, x1, y1, z1, off, rsv = HEAD.unpack_from(b, 0)
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(nv, 3); o += nv * 6
    n2 = np.frombuffer(b, np.uint16, nv * 2, o).reshape(nv, 2); o += nv * 4
    o += nv * 6
    tri = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3).astype(np.int64)
    lo = np.array([x0, y0, z0], np.float64); hi = np.array([x1, y1, z1], np.float64)
    return q.astype(np.float64) / 65535.0 * (hi - lo) + lo, M.oct_decode(n2), tri


def n3_bytes(b):
    """the record b with its normal block replaced by the N3 normals; (bytes, info). Everything else is b's own bytes."""
    L = layout(b)
    if L["nt"] == 0 or L["nv"] == 0:
        return bytes(b), dict(L, empty=True)
    P, Nst, tri = decode(b)
    T = M.topo(P, tri)
    s, agree = M.orient_sign(P, tri, Nst)
    N0 = M.awn(P, tri, s, T["seam"])                                  # area-weighted geometric normals (shape of the record)
    N = M.smooth_normals(N0, T, N_AVG)                                # = hs_mesh_smooth make_variant("N3")
    N = N.copy()
    N[np.abs(P[:, 2]) < SEAM_WRITE, 2] = 0.0                          # = write_srf
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    enc = M.oct_encode(N).tobytes()
    if len(enc) != L["o_e"] - L["o_n"]:
        raise ValueError("normal block size")
    out = b[:L["o_n"]] + enc + b[L["o_e"]:]
    a_geo = np.degrees(np.arccos(np.clip((N * N0).sum(1), -1, 1)))
    a_st = np.degrees(np.arccos(np.clip((N * Nst).sum(1), -1, 1)))
    off = HEAD.unpack_from(b, 0)[13]
    vis = (P[:, 1] - off) >= VIS_EMIN                                 # the visible side; below it the hidden under-water sheet (bed-hugging)
    q = lambda x: [float(np.percentile(x, 50)), float(np.percentile(x, 99)), float(x.max())] if len(x) else None
    info = dict(L, orient_sign=s, orient_agree=agree, n_seam_v=int(T["n_seam_v"]), n_nonmanifold_e=int(T["n_nonmanifold_e"]),
                n3_vs_geometric_deg=q(a_geo), n3_vs_geometric_visible_deg=q(a_geo[vis]), n3_vs_houdini_visible_deg=q(a_st[vis]),
                n3_vs_houdini_deg=q(a_st), n_visible_v=int(vis.sum()))
    return out, info


def same_outside_normals(a, b):
    La, Lb = layout(a), layout(b)
    return bool(len(a) == len(b) and La["o_n"] == Lb["o_n"] and a[:La["o_n"]] == b[:Lb["o_n"]] and a[La["o_e"]:] == b[Lb["o_e"]:])


def write_atomic(c, p, b):
    c.guard(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".part"
    with open(tmp, "wb") as fh:
        fh.write(b)
    os.replace(tmp, p)


# ====================================================================== plan / selftest (read only)
def cmd_plan(a):
    c = Ctx(a, need_src=False)
    H, m = c.H, c.src_man or {}
    miss = [f for f in c.frames if not os.path.exists(c.src_record(f))] if c.src_stream else None
    n_out = len(glob.glob(c.surf_out + "/s_*.gw45s"))
    free, total = commit_free_gb()
    o = dict(hero=c.hero, name=c.spec["name"], seat=c.seat, source_clip=rel(c.src_clip), source_clip_exists=bool(c.src_man),
             source_capture=rel(c.src_cap), source_capture_exists=os.path.exists(c.src_cap + "/cmove/frames.csv"),
             source_stream=rel(c.src_stream) if c.src_stream else None, frames=[c.frames[0], c.frames[-1], len(c.frames)] if c.frames else None,
             source_missing=(len(miss) if miss is not None else None), source_bytes_gb=(sum(m.get("source_bytes") or []) / 1e9),
             tri_max=m.get("tri_max"), vert_max=m.get("vert_max"),
             out_root=rel(c.root), out_surf=rel(c.surf_out), out_surf_existing=n_out, out_clip=rel(H.clip), out_capture=rel(H.cap),
             out_videos=[rel(c.video_dir + "/FLIP3D_%s_%s.mp4" % (c.tag, n)) for n in JOBS.split(",")],
             unity_extra=c.mod.capture_args(H, JOBS), unity_log=rel(OUT3D + "/logs/unity_%s.log" % c.unity_log),
             unity_log_exists=os.path.exists(OUT3D + "/logs/unity_%s.log" % c.unity_log),
             move=getattr(c.mod, "MOVE", None), print=getattr(c.mod, "PRINT", None), seat_design=H.seat,
             disk_free_gb=disk_free_gb(c.root), commit_free_gb=free, commit_limit_gb=total,
             estimate=dict(apply_s_per_frame=[0.10, 0.16], apply_min=[0.10 * len(c.frames) / 60, 0.16 * len(c.frames) / 60] if c.frames else None,
                           disk_gb=(sum(m.get("source_bytes") or []) / 1e9) + 0.6, unity_min="about 3-4 (the hero's four jobs took 195.6 s)",
                           tags="apply [computed] from hs_mesh_smooth timings (0.05-0.06 s N3 + read / write) [measured]; Unity [measured] hero batch"),
             honesty=c.H.honesty())
    emit(o)
    return 0


def cmd_selftest(a):
    """read only: (1) N3 bytes of the judged test frames == the records judged in Unity (E); (2) splice identity on every test frame;
    (3) the schedule comparator on the hero capture against itself; (4) the caption patch compiles and the titles fit; (5) a dry manifest."""
    c = Ctx(a)
    prio = set_priority("idle")
    res = dict(priority=prio)
    tf = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(TEST_N3 + "/s_*.gw45s")) if c.hero == "E" else []
    ids = {}
    for f in (tf or c.frames[:1] + c.frames[len(c.frames) // 2:len(c.frames) // 2 + 1]):
        src = c.src_record(f)
        b = open(src, "rb").read()
        t0 = time.perf_counter()
        nb, info = n3_bytes(b)
        dt = time.perf_counter() - t0
        r = dict(seconds=round(dt, 3), splice_identity=same_outside_normals(b, nb), normals_changed=bool(nb != b),
                 n3_vs_geometric_deg=info.get("n3_vs_geometric_deg"), n3_vs_geometric_visible_deg=info.get("n3_vs_geometric_visible_deg"),
                 orient_agree=info.get("orient_agree"))
        tp = TEST_N3 + "/s_%05d.gw45s" % f
        if c.hero == "E" and os.path.exists(tp):
            r["equals_judged_test_record"] = bool(open(tp, "rb").read() == nb)
        ids[f] = r
    res["records"] = ids
    res["records_ok"] = bool(ids and all(v["splice_identity"] and v["normals_changed"] and v.get("equals_judged_test_record", True) for v in ids.values()))
    if os.path.exists(c.src_cap + "/cseat/frames.csv"):
        sc = same_schedule(c.src_cap, c.src_cap)
        res["schedule_self"] = sc
        res["schedule_ok"] = all(v.get("identical") for v in sc.values())
    rc, vd = video_dry(c)
    res["video_dry"] = vd
    res["video_ok"] = bool(rc == 0 and all(w["fits"] for w in vd.get("title_widths", [])))
    man, why = build_manifest(c, dry=True)
    res["manifest_dry"] = why
    res["manifest_ok"] = bool(man and why.get("fields_ok"))
    res["unity_extra"] = c.mod.capture_args(c.H, JOBS)
    res["hero_vs_n3_extra_differ_only_in_paths"] = unity_args_compare(c)
    res["honesty_last"] = c.H.honesty()[-1]
    res["ok"] = bool(res["records_ok"] and res.get("schedule_ok", True) and res["video_ok"] and res["manifest_ok"]
                     and res["hero_vs_n3_extra_differ_only_in_paths"]["ok"])
    emit(res)
    return 0 if res["ok"] else 9


def unity_args_compare(c):
    """the N3 Unity arguments vs the hero's own (the module's capture_args on the unchanged Hero): only -f3ddata / -f3dout may differ."""
    H0 = c.mod.Hero(c.spec["cfg"], seat=c.seat)
    a0 = c.mod.capture_args(H0, JOBS).split(" ")
    a1 = c.mod.capture_args(c.H, JOBS).split(" ")
    diff = [(a0[i - 1], a0[i], a1[i]) for i in range(len(a0)) if i < len(a1) and a0[i] != a1[i]]
    ok = bool(len(a0) == len(a1) and all(k in ("-f3ddata", "-f3dout") for k, _, _ in diff))
    rec = None
    j = jload(B52B + "/hero/unity_seatA_%s.json" % c.rid) if c.hero == "E" else jload(B52B3 + "/hero/unity_seat%s_%s.json" % (c.seat, c.rid))
    if j and j.get("extra"):
        e0 = j["extra"].split(" ")
        hero_rec = [x for x in e0]
        rec = dict(hero_recorded_jobs=hero_rec[1] if len(hero_rec) > 1 else None,
                   same_as_recorded_except_jobs_paths=bool(len(e0) == len(a1) and all(
                       e0[i] == a1[i] or (i > 0 and e0[i - 1] in ("-f3dcap", "-f3ddata", "-f3dout")) for i in range(len(e0)))))
    return dict(ok=ok, differing=diff, recorded_hero_batch=rec)


# ====================================================================== apply / verify
def cmd_apply(a):
    c = Ctx(a)
    prio = set_priority(opt(a, "--prio", "idle"))
    f0, f1 = int(opt(a, "--from", "0")), int(opt(a, "--to", "999999"))
    shas = c.src_man.get("source_sha256") or []
    idx = {f: i for i, f in enumerate(c.frames)}
    todo = [f for f in c.frames if f0 <= f <= f1]
    if not todo:
        raise SystemExit("no frames in %d-%d" % (f0, f1))
    need = sum((c.src_man.get("source_bytes") or [0])[idx[f]] for f in todo) / 1e9 + 0.2
    if disk_free_gb(c.root) < need + 2.0:
        raise SystemExit("disk: %.1f GB free < %.1f GB needed + 2 GB" % (disk_free_gb(c.root), need))
    os.makedirs(c.surf_out, exist_ok=True)
    logp = c.root + "/" + c.rid + "/n3_apply.json"
    old = jload(logp) or {}
    recs = {int(k): v for k, v in (old.get("records") or {}).items()}
    t0 = time.time()
    n_w = n_same = n_bad_src = 0
    for k, f in enumerate(todo):
        src = c.src_record(f)
        b = open(src, "rb").read()
        src_ok = bool(idx[f] < len(shas) and sha_bytes(b) == shas[idx[f]])
        if not src_ok:
            n_bad_src += 1
            recs[f] = dict(frame=f, src_sha_matches_manifest=False)
            continue                                                  # never write N3 of a record the hero clip does not play
        ts = time.perf_counter()
        nb, info = n3_bytes(b)
        if not same_outside_normals(b, nb):
            raise SystemExit("splice identity failed at frame %d" % f)
        outp = c.out_record(f)
        if os.path.exists(outp) and os.path.getsize(outp) == len(nb) and open(outp, "rb").read() == nb:
            n_same += 1
        else:
            write_atomic(c, outp, nb)
            n_w += 1
        recs[f] = dict(frame=f, src_sha_matches_manifest=True, bytes=len(nb), sha256=sha_bytes(nb), nv=info["nv"], nt=info["nt"],
                       orient_agree=info.get("orient_agree"), n3_vs_geometric_deg=info.get("n3_vs_geometric_deg"),
                       n3_vs_geometric_visible_deg=info.get("n3_vs_geometric_visible_deg"), n3_vs_houdini_deg=info.get("n3_vs_houdini_deg"),
                       seconds=round(time.perf_counter() - ts, 3))
        if k % 200 == 0:
            print("apply %d/%d frame %d %.1f s" % (k + 1, len(todo), f, time.time() - t0), flush=True)
            c.jdump(dict(tool=TOOL + " apply", partial=True, records={str(kk): v for kk, v in sorted(recs.items())}), logp)
    el = time.time() - t0
    good = [v for v in recs.values() if v.get("src_sha_matches_manifest")]
    geo = np.array([v["n3_vs_geometric_deg"] for v in good if v.get("n3_vs_geometric_deg")]) if good else np.zeros((0, 3))
    gv = np.array([v["n3_vs_geometric_visible_deg"] for v in good if v.get("n3_vs_geometric_visible_deg")]) if good else np.zeros((0, 3))
    hou = np.array([v["n3_vs_houdini_deg"] for v in good if v.get("n3_vs_houdini_deg")]) if good else np.zeros((0, 3))
    summ = dict(n_frames_clip=len(c.frames), n_done_total=len(good), n_this_call=len(todo), written=n_w, already_identical=n_same,
                source_sha_mismatch=n_bad_src, seconds=round(el, 1), s_per_frame=round(el / max(len(todo), 1), 3), priority=prio,
                n3_vs_geometric_deg_median_p50=float(np.median(geo[:, 0])) if len(geo) else None,
                n3_vs_geometric_deg_max_p99=float(geo[:, 1].max()) if len(geo) else None,
                n3_vs_geometric_visible_deg_median_p50=float(np.median(gv[:, 0])) if len(gv) else None,
                n3_vs_geometric_visible_deg_median_p99=float(np.median(gv[:, 1])) if len(gv) else None,
                n3_vs_geometric_visible_deg_max_p99=float(gv[:, 1].max()) if len(gv) else None,
                n3_vs_houdini_deg_median_p50=float(np.median(hou[:, 0])) if len(hou) else None,
                orient_agree_min=float(min(v.get("orient_agree") or 1.0 for v in good)) if good else None)
    c.jdump(dict(tool=TOOL + " apply", time=time.strftime("%Y-%m-%d %H:%M:%S"), hero=c.spec["name"], source_clip=rel(c.src_clip),
                 source_stream=rel(c.src_stream), out=rel(c.surf_out), n3_rule=c.n3_en, summary=summ,
                 tags="angles [measured] on the records; seconds [measured]",
                 records={str(k): v for k, v in sorted(recs.items())}), logp)
    emit(dict(apply=summ, out=rel(c.surf_out), log=rel(logp)))
    return 0 if n_bad_src == 0 else 3


def cmd_verify(a):
    c = Ctx(a)
    shas = c.src_man.get("source_sha256") or []
    t0 = time.time()
    rows, bad, missing = [], [], []
    for i, f in enumerate(c.frames):
        outp = c.out_record(f)
        if not os.path.exists(outp):
            missing.append(f); continue
        b = open(c.src_record(f), "rb").read()
        n = open(outp, "rb").read()
        ok_src = bool(i < len(shas) and sha_bytes(b) == shas[i])
        same = same_outside_normals(b, n)
        Ln = layout(n)
        nrm = M.oct_decode(np.frombuffer(n, np.uint16, Ln["nv"] * 2, Ln["o_n"]).reshape(-1, 2)) if Ln["nv"] else np.zeros((0, 3))
        unit = bool(np.isfinite(nrm).all())
        changed = bool(n[Ln["o_n"]:Ln["o_e"]] != b[Ln["o_n"]:Ln["o_e"]])
        h = sha_bytes(n)
        rows.append(dict(frame=f, bytes=len(n), sha256=h, src_ok=ok_src, same_outside_normals=same, normals_finite=unit, normals_changed=changed,
                         header_frame=Ln["frame"]))
        if not (ok_src and same and unit and Ln["frame"] == f):
            bad.append(f)
    tf = {}
    if c.hero == "E":
        for p in sorted(glob.glob(TEST_N3 + "/s_*.gw45s")):
            f = int(os.path.basename(p)[2:7])
            if os.path.exists(c.out_record(f)):
                tf[f] = bool(open(p, "rb").read() == open(c.out_record(f), "rb").read())
    ok = bool(not bad and not missing and len(rows) == len(c.frames) and all(tf.values()))
    out = dict(tool=TOOL + " verify", time=time.strftime("%Y-%m-%d %H:%M:%S"), hero=c.spec["name"], ok=ok, n=len(rows), n_expected=len(c.frames),
               missing=missing[:50], n_missing=len(missing), bad=bad[:50], n_bad=len(bad),
               n_normals_unchanged=sum(1 for r in rows if not r["normals_changed"]),
               equals_judged_test_records=tf, seconds=round(time.time() - t0, 1),
               statement=("every N3 record's header, positions, velocities and triangles are byte-identical to the hero record the hero clip "
                          "plays (its sha256 = the hero manifest's); only the normal block differs [measured]; physics records not touched"),
               records=rows)
    c.jdump(out, c.root + "/" + c.rid + "/n3_verify.json")
    emit({k: out[k] for k in ("ok", "n", "n_expected", "n_missing", "n_bad", "n_normals_unchanged", "equals_judged_test_records", "seconds")})
    return 0 if ok else 4


# ====================================================================== the N3 clip
def build_manifest(c, dry=False):
    V = jload(c.root + "/" + c.rid + "/n3_verify.json") or {}
    vrec = {int(r["frame"]): r for r in V.get("records") or []}
    m = json.loads(json.dumps(c.src_man))
    why = dict(verify_ok=bool(V.get("ok")), n_verified=len(vrec))
    if not dry and not V.get("ok"):
        return None, dict(why, refused="n3_verify.json not ok: run apply + verify first")
    shas, sizes = [], []
    for i, f in enumerate(c.frames):
        r = vrec.get(f)
        if r is None:
            if not dry:
                return None, dict(why, refused="frame %d not verified" % f)
            shas.append(m["source_sha256"][i]); sizes.append(m["source_bytes"][i])      # dry: the hero's own entry as a stand-in
        else:
            shas.append(r["sha256"]); sizes.append(r["bytes"])
    stream_rel = os.path.relpath(c.surf_out, c.H.clip).replace("\\", "/")
    m.update(source_sha256=shas, source_bytes=sizes, source_list_sha256=hashlib.sha256("".join(shas).encode("ascii")).hexdigest(),
             clip_bytes=int(sum(sizes)), stream_dir=c.surf_out, stream_dir_rel=stream_rel, created=time.strftime("%Y-%m-%d %H:%M:%S"),
             tool=TOOL + " clip")
    m["surface_variant"] = dict(
        name="N3", what_en=c.n3_en, what_ja=c.n3_ja, hero=c.spec["name"], source_clip=rel(c.src_clip),
        source_manifest_sha256=sha(c.src_clip + "/manifest.json"), source_stream=rel(c.src_stream), physics_run=m.get("source_run"),
        positions_triangles_velocities_byte_identical=bool(V.get("ok")), n_records_verified=len(vrec),
        judged_in_unity="Unity/Build/FLIP52B/hires/unity_cmp (sheet_f2112_*, sheet_f2149_all_views.jpg): rank 1 of the comparison",
        does_not_fix="the polygonal crest outline (0.6 m segments) and the triangle layout remain [measured]", tool=TOOL)
    m["notes_en"] = list(m.get("notes_en") or []) + [c.n3_en]
    hero = m.get("hero")
    if isinstance(hero, dict) and isinstance(hero.get("vr_command_hint"), str):
        hero["vr_command_hint"] = hero["vr_command_hint"].replace(c.src_clip, c.H.clip)
        hero["surface_variant"] = "N3 (shading normals only; physics unchanged)"
    keep = ("frames", "frame_first", "frame_last", "vert_max", "tri_max", "vert_min", "tri_min", "heave", "source_frames", "breakers", "bed_sha256",
            "cam_print_pos", "cam_print_look_at", "cam_seat_look_at", "seat_x", "seat_z", "seat_eye_m", "print_record_frame", "record_fps")
    why["fields_unchanged"] = {k: bool(m.get(k) == c.src_man.get(k)) for k in keep}
    why["sizes_equal_hero"] = bool(sizes == list(c.src_man.get("source_bytes") or []))
    why["stream_dir_rel"] = stream_rel
    why["fields_ok"] = bool(all(why["fields_unchanged"].values()) and why["sizes_equal_hero"] and len(shas) == len(c.frames) == int(m["frames"]))
    return m, why


def cmd_clip(a):
    c = Ctx(a)
    dry = "--dry" in a
    man, why = build_manifest(c, dry=dry)
    if man is None:
        emit(dict(clip=None, **why)); return 4
    if dry:
        emit(dict(dry=True, clip=rel(c.H.clip), **why)); return 0 if why["fields_ok"] else 4
    if not why["fields_ok"]:
        emit(dict(clip=None, refused="manifest fields changed", **why)); return 4
    mp = c.guard(c.H.clip + "/manifest.json")
    if os.path.exists(mp) and "--force" not in a:
        old = jload(mp) or {}
        if old.get("source_list_sha256") == man["source_list_sha256"] and (old.get("surface_variant") or {}).get("name") == "N3":
            emit(dict(clip=rel(c.H.clip), already=True, **why)); return 0
        raise SystemExit("refused: %s exists (use --force for a clip this tool wrote)" % rel(mp))
    os.makedirs(c.H.clip, exist_ok=True)
    bed = c.guard(c.H.clip + "/bed.f32")
    shutil.copyfile(c.src_clip + "/bed.f32", bed)
    bed_ok = bool(sha(bed) == man.get("bed_sha256"))
    if not bed_ok:
        raise SystemExit("bed.f32 sha256 differs from the manifest")
    json.dump(man, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep = dict(tool=TOOL + " clip", time=time.strftime("%Y-%m-%d %H:%M:%S"), clip=rel(c.H.clip), source_clip=rel(c.src_clip), bed_ok=bed_ok,
               manifest_sha256=sha(mp), **why)
    c.jdump(rep, c.H.clip + "/n3_clip.json")
    emit(dict(clip=rel(c.H.clip), bed_ok=bed_ok, records=len(man["source_sha256"]), clip_gb=man["clip_bytes"] / 1e9, **why))
    return 0


# ====================================================================== Unity (the hero's arguments with the N3 clip; backup / restore)
def git_tracked_status():
    p = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-uno"], capture_output=True, text=True, encoding="utf8")
    return p.stdout


def cmd_unity(a):
    c = Ctx(a)
    H = c.H
    extra = c.mod.capture_args(H, JOBS)
    free, total = commit_free_gb()
    plan = dict(method=UNITY_METHOD, extra=extra, log=c.unity_log, commit_free_gb=round(free, 2), commit_limit_gb=round(total, 2),
                need_gb=COMMIT_MIN_GB, unity_lock_exists=os.path.exists(REPO + "/Unity/Build/unity.lock"), args_check=unity_args_compare(c))
    if " " in H.clip or " " in H.cap:
        raise SystemExit("f3d_unity.ps1 splits -Extra on spaces: the N3 paths must not contain spaces")
    if "--dry" in a:
        emit(dict(dry=plan)); return 0
    if not plan["args_check"]["ok"]:
        raise SystemExit("the N3 Unity arguments differ from the hero's in more than -f3ddata / -f3dout: %s" % plan["args_check"])
    if not os.path.exists(H.clip + "/manifest.json"):
        raise SystemExit("no clip %s: run `clip` first" % rel(H.clip))
    done = [j for j in JOBS.split(",") if os.path.exists(H.cap + "/" + j + "/frames.csv") and os.path.exists(H.cap + "/" + j + "/capture.json")]
    if len(done) == len(JOBS.split(",")) and "--force" not in a:
        emit(dict(rc=0, already=True, all_restored=True, git_status_same=True, lock_released=True, unity_line="(capture %s complete: not captured again; "
                  "--force captures again into it)" % rel(H.cap), settings_changed=None, backup=None))
        return 0
    if free < COMMIT_MIN_GB:
        emit(dict(unity="skipped: commit free %.2f GB < %.1f GB" % (free, COMMIT_MIN_GB), **plan)); return 5
    c.guard(H.cap + "/x")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = c.guard(c.root + "/_unity_backup/" + stamp)
    os.makedirs(bdir, exist_ok=True)
    before = {}
    for r in TRACKED:                                   # the PRE-BATCH working-tree state (not HEAD): restored byte for byte afterwards
        src = REPO + "/" + r
        dst = bdir + "/" + r.replace("/", "__")
        shutil.copyfile(src, dst)
        before[r] = sha(src)
        if sha(dst) != before[r]:
            raise SystemExit("backup copy differs: %s" % r)
    st0 = git_tracked_status()
    c.jdump(dict(files=before, git_status_uno=st0, date=time.strftime("%Y-%m-%d %H:%M:%S")), bdir + "/pre_batch.json")
    t0 = time.time()
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UNITY_PS1, "-Method", UNITY_METHOD, "-Log", c.unity_log, "-Extra", extra,
           "-TimeoutMinutes", "90", "-LockWaitMinutes", "40"]
    out, rc = "", -1
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    finally:
        restored = {}
        for rr in TRACKED:
            dst = REPO + "/" + rr
            if not os.path.exists(dst) or sha(dst) != before[rr]:
                shutil.copyfile(bdir + "/" + rr.replace("/", "__"), dst)
            restored[rr] = sha(dst) == before[rr]
    st1 = git_tracked_status()
    line = [l for l in out.splitlines() if l.startswith("FLIP3D_UNITY ")]
    res = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " unity", rc=rc, seconds=round(time.time() - t0, 1), unity_line=line[-1] if line else None,
               settings_changed=(line[-1].split("settings_changed=")[1].split(" ")[0] if line and "settings_changed=" in line[-1] else None),
               restored_pre_batch_state=restored, all_restored=all(restored.values()), git_status_same=st0 == st1, backup=rel(bdir), tail=out[-1500:],
               lock_released=not os.path.exists(REPO + "/Unity/Build/unity.lock"), **plan)
    c.jdump(res, H.hj("unity_seat%s" % c.seat))
    emit({k: res[k] for k in ("rc", "seconds", "unity_line", "settings_changed", "all_restored", "git_status_same", "backup", "lock_released")})
    return 0 if (rc == 0 and res["all_restored"]) else 6


# ====================================================================== capture checks
def frames_rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None


def same_schedule(cap_a, cap_b):
    """per job: every frames.csv column of the schedule / camera (not the timing columns) identical, row for row."""
    out = {}
    for job in JOBS.split(","):
        ra, rb = frames_rows(cap_a + "/" + job + "/frames.csv"), frames_rows(cap_b + "/" + job + "/frames.csv")
        if ra is None or rb is None:
            out[job] = dict(missing=[x for x, r in (("a", ra), ("b", rb)) if r is None], identical=False); continue
        diffs = [k for k in SCHED_COLS if [r.get(k) for r in ra] != [r.get(k) for r in rb]]
        first = None
        for i, (x, y) in enumerate(zip(ra, rb)):
            if any(x.get(k) != y.get(k) for k in SCHED_COLS):
                first = dict(row=i, a={k: x.get(k) for k in SCHED_COLS}, b={k: y.get(k) for k in SCHED_COLS}); break
        out[job] = dict(rows=[len(ra), len(rb)], identical=bool(not diffs and len(ra) == len(rb)), differing_columns=diffs, first_difference=first)
    return out


def cmd_capcheck(a):
    c = Ctx(a)
    H = c.H
    rc = c.mod.cmd_capcheck([c.spec["cfg"], "--seat", c.seat])           # the hero module's own check, on the N3 Hero (in memory)
    cc = jload(H.cap + "/hero_capcheck.json") or {}
    src_cc = jload(c.src_cap + "/hero_capcheck.json") or {}
    sc = same_schedule(c.src_cap, H.cap)
    keys = ("frames", "sim_frame_eq_first_plus_record", "skipped_records", "back_steps", "frozen_frames", "cam_col_clearance_min_m",
            "cam_nearest_vertex_min_m", "arrive", "leave_sim_t", "move_start_sim_t")
    same_num = {job: {k: bool((cc.get(job) or {}).get(k) == (src_cc.get(job) or {}).get(k)) for k in keys} for job in JOBS.split(",")}
    out = dict(tool=TOOL + " capcheck", time=time.strftime("%Y-%m-%d %H:%M:%S"), module_capcheck_rc=rc, n3_ok=cc.get("ok"), hero_ok=src_cc.get("ok"),
               same_schedule_as_hero=sc, schedule_identical=all(v.get("identical") for v in sc.values()),
               capcheck_numbers_equal_hero=same_num, capcheck_numbers_all_equal=all(all(v.values()) for v in same_num.values()),
               unity_log=cc.get("unity_log"), honesty=H.honesty())
    out["ok"] = bool(cc.get("ok") == src_cc.get("ok") and cc.get("ok") is not None and out["schedule_identical"]
                     and ((cc.get("unity_log") or {}).get("exceptions", 1) == 0))
    c.jdump(out, H.hj("schedule_capcheck_seat%s" % c.seat))
    emit({k: out[k] for k in ("ok", "n3_ok", "hero_ok", "schedule_identical", "capcheck_numbers_all_equal", "module_capcheck_rc")}
         | dict(stream=(cc.get("unity_log") or {}).get("stream")))
    return 0 if out["ok"] else 7


# ====================================================================== videos (the hero's caption patch + one N3 line)
def caption_setup(c):
    H, mod = c.H, c.mod
    import f3d50_video_loop as FL                                            # unchanged
    V, V5 = FL.V, FL.V5
    V5.RUN_TEXT = dict(V5.RUN_TEXT)
    V5.RUN_TEXT[c.src_short] = c.spec["run_text_ja"] % c.src_short             # keyed like V5.patched: the manifest run_id's short (unchanged)
    if c.hero == "E":
        base = [H.invalid_line() + " | " + mod.ENERGY_EN, H.physics_line() + " | " + mod.NOSHAPE_EN]   # = h52b_hero.cmd_video lines 4-5
    else:
        base = mod.caption_lines(H)                                                                     # = h52b3_hero.cmd_video lines 4-7
    L = list(base) + [c.n3_ja]
    cols = ["(255, 200, 140)"] * len(base) + ["(150, 255, 170)"]
    for i, l in enumerate(L):
        setattr(V, "HIRES_L%d" % (i + 1), l)                                    # in memory: copied into the exec namespace by V5.patched
    band_old = "        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))\n"
    band_new = "        dr.rectangle([0, 0, W, %d], fill=(0, 0, 0, 150))\n" % (112 + 28 * len(L) - 2)
    l3_old = "        dr.text((18, 74), line3, font=_fit(line3, 19, W - 36), fill=(225, 225, 225))\n"
    l3_new = l3_old + "".join("        dr.text((18, %d), HIRES_L%d, font=_fit(HIRES_L%d, 19, W - 36), fill=%s)\n" % (102 + 28 * i, i + 1, i + 1, cols[i])
                              for i in range(len(L)))
    FL.FIT_LINES = tuple(FL.FIT_LINES) + ((band_old, band_new), (l3_old, l3_new))   # each must occur exactly once (checked by FL)
    return FL, V, V5, L


def title_widths(c, FL, V, V5):
    """the fitted title of each job vs the frame width (W - 36 = 1884 px at 1920): the f3d_video title rule, with CNAMES of the play range."""
    out = []
    t0 = (c.H.f0 - 1) / 24.0
    t1 = c.H.f1 / 24.0
    for job in JOBS.split(","):
        title = "FLIP3D 試作（Unity で実時間に再生）" + V5.RUN_TEXT[c.src_short] + " — " + V.CNAMES[job] % (t0, t1 - 1.0 / 24.0)
        f = FL.fit(title, 26, 1920 - 36)
        w = f.getlength(title)
        out.append(dict(job=job, px=round(w, 1), font_px=f.size, fits=bool(w <= 1884)))
    for i in range(1, 12):
        l = getattr(V, "HIRES_L%d" % i, None)
        if l is None:
            break
        f = FL.fit(l, 19, 1920 - 36)
        out.append(dict(job="line%d" % (i + 3), px=round(f.getlength(l), 1), font_px=f.size, fits=bool(f.getlength(l) <= 1884)))
    return out


def video_dry(c):
    import inspect
    FL, V, V5, L = caption_setup(c)
    s = inspect.getsource(V.compose_cont)
    if s.count(FL.OLD_MOVE) != 1:
        return 8, dict(error="move caption not found once")
    s = s.replace(FL.OLD_MOVE, FL.NEW_MOVE)
    for old, new in FL.FIT_LINES:
        if s.count(old) != 1:
            return 8, dict(error="caption line not found exactly once: " + old[:60])
        s = s.replace(old, new)
    for old in (V5.OLD_TITLE, V5.OLD_LINE2, V5.OLD_LINE3):
        if s.count(old) != 1:
            return 8, dict(error="f3d50_video caption not found once: " + old[:40])
    compile(s, "patched compose_cont", "exec")
    return 0, dict(dry="caption patch compiles (every replacement found exactly once)", lines=L, title_widths=title_widths(c, FL, V, V5),
                   videos_would_be=[rel(c.video_dir + "/FLIP3D_%s_%s.mp4" % (c.tag, n)) for n in JOBS.split(",")])


def cmd_video(a):
    c = Ctx(a, need_src="--dry" not in a)
    H = c.H
    if "--dry" in a:
        rc, d = video_dry(c)
        emit(d); return rc
    names = [n for n in JOBS.split(",") if os.path.exists(H.cap + "/" + n + "/frames.csv")]
    if names != JOBS.split(","):
        raise SystemExit("capture incomplete: %s" % names)
    have = [n for n in names if os.path.exists(c.guard(c.video_dir + "/FLIP3D_%s_%s.mp4" % (c.tag, n)))]
    if have and "--force" not in a:
        if len(have) == len(names):
            emit(dict(videos=[(n, rel(c.video_dir + "/FLIP3D_%s_%s.mp4" % (c.tag, n)), None, os.path.getsize(c.video_dir + "/FLIP3D_%s_%s.mp4" % (c.tag, n)))
                              for n in names], already=True, title_widths_fit=None))
            return 0
        raise SystemExit("refused: some videos exist %s (use --force to make all three again)" % have)
    FL, V, V5, L = caption_setup(c)
    widths = title_widths(c, FL, V, V5)
    V.VID = c.guard(c.video_dir)                                              # in memory: compose_cont writes its mp4 / sheet / temp frames here
    os.makedirs(V.VID, exist_ok=True)
    capdir = os.path.relpath(H.cap, V.C.OUT).replace("\\", "/")              # compose_cont reads C.OUT + "/" + capdir
    fn = FL.compose_cont_exact(capdir, names)
    res = [fn(nm, capdir) for nm in names]
    r = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " video", videos=res, lines=L, title_widths=widths, capdir=capdir)
    c.jdump(r, H.hj("video_seat%s" % c.seat))
    emit(dict(videos=[(x["name"], rel(x["mp4"]), x["frames"], x["bytes"]) for x in res], title_widths_fit=all(w["fits"] for w in widths)))
    return 0


# ====================================================================== before / after sheets + image measures
def wrap_px(text, fnt, width):
    words, rows, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fnt.getlength(t) <= width or not cur:
            cur = t
        else:
            rows.append(cur); cur = w
    return rows + ([cur] if cur else [])


def index_rows(cap, job):
    out = {}
    for r in frames_rows(cap + "/" + job + "/frames.csv") or []:
        out.setdefault(int(r["sim_frame"]), r)
    return out


def cmd_sheet(a):
    c = Ctx(a)
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage as ndi
    import hs_unity_sheet as US                                                # the comparison step's measures (luma, water mask), unchanged
    H = c.H
    n3cap = (opt(a, "--n3-cap") or H.cap).replace("\\", "/")                  # --n3-cap: self-test on the hero capture against itself
    font = lambda s: ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", s)
    J = jload(getattr(c.mod, c.spec["judge_attr"])) or {}
    conv = {int(g["n"]): int(g["conv"]["f"]) for g in J.get("groups") or [] if (g.get("conv") or {}).get("f")}
    best = c.mod.pv53_best()
    frames = []
    for n in (1, 2, 3):
        frames += [conv.get(n), (best.get(n) or {}).get("frame")]
    frames = [f for f in frames if f]
    mvf = int(c.mod.MOVE["frame"])
    idx = {(w, job): index_rows(cap, job) for w, cap in (("hero", c.src_cap), ("n3", n3cap)) for job in ("cseat", "cprint")}
    for k, v in idx.items():
        if not v:
            raise SystemExit("no capture rows %s" % (k,))
    img = lambda w, job, f: Image.open((c.src_cap if w == "hero" else n3cap) + "/%s/frame_%05d.jpg" % (job, int(idx[(w, job)][f]["i"]))).convert("RGB")
    head = ["%s: hero (as accepted) vs N3 (shading normals only) - the same records, cameras and schedule" % c.spec["name"]] + H.honesty()
    os.makedirs(c.video_dir, exist_ok=True)
    outs = {}
    # ---- overview: 6 frames x (hero seat, N3 seat, hero print, N3 print)
    CW, CH = 640, 360
    COLS = max(1, len(frames))
    rows_h = []
    for i, l in enumerate(head):
        fnt = font(30 if i else 34)
        for j, piece in enumerate(wrap_px(l, fnt, CW * COLS - 40)):
            rows_h.append((("    " if j else "") + piece, fnt, (255, 255, 255) if i == 0 else ((150, 255, 170) if i == len(head) - 1 else (255, 200, 140))))
    TOP = 16 + 44 * len(rows_h)
    S = Image.new("RGB", (CW * COLS, TOP + 4 * CH), (0, 0, 0))
    dr = ImageDraw.Draw(S)
    for i, (l, fnt, col) in enumerate(rows_h):
        dr.text((14, 8 + 44 * i), l, font=fnt, fill=col)
    lab = (("hero", "cseat", "hero  seat %s" % c.seat), ("n3", "cseat", "N3  seat %s" % c.seat), ("hero", "cprint", "hero  print view"),
           ("n3", "cprint", "N3  print view"))
    for j, f in enumerate(frames):
        for m, (w, job, name) in enumerate(lab):
            x, y = j * CW, TOP + m * CH
            if f not in idx[(w, job)]:
                dr.text((x + 10, y + 10), "frame %d not captured" % f, font=font(18), fill=(255, 120, 120)); continue
            S.paste(img(w, job, f).resize((CW, CH), Image.LANCZOS), (x, y))
            dr.rectangle([x, y, x + CW, y + 28], fill=(0, 0, 0))
            dr.text((x + 6, y + 2), "%s  %.3f s (frame %d)%s" % (name, (f - 1) / 24.0, f, "  [move arrives]" if f == mvf else ""), font=font(19),
                    fill=(150, 255, 170) if w == "n3" else (255, 230, 120))
    p = c.guard(c.video_dir + "/FLIP3D_%s_before_after.jpg" % c.tag)
    S.save(p, quality=90)
    outs["overview"] = rel(p)
    # ---- 1:1 detail (and contrast x2) at the print instant (the move frame) and 1.5 s before it: the print view cropped around the wave's
    # highest water column (found on the hero picture, the same box for both) and the seat view's lower centre (the near water)
    def crest_box(f):
        A = np.asarray(img("hero", "cprint", f))
        m = US.water_mask(A)
        top = np.where(m.any(0), m.argmax(0), 10 ** 6)
        top[:40] = 10 ** 6; top[-40:] = 10 ** 6
        x = int(np.argmin(top)); y = int(top[x]) if top[x] < 10 ** 6 else 540
        x0 = min(max(x - 480, 0), 960); y0 = min(max(y - 200, 0), 540)
        return (x0, y0, x0 + 960, y0 + 540)
    dfr = [f for f in (mvf - 36, mvf) if f in idx[("hero", "cprint")] and f in idx[("n3", "cprint")]]
    rows = []
    for f in dfr:
        b = crest_box(f)
        rows += [(f, "cprint", b, "print view, 960x540 at 1:1 around the crest (box %d,%d)" % b[:2]),
                 (f, "cseat", (480, 540, 1440, 1080), "seat %s, lower centre 960x540 at 1:1 (the near water)" % c.seat)]
    for gain, suf in ((1.0, "detail_1to1"), (2.0, "detail_1to1_contrast2")):
        hl = ["%s  hero (left) vs N3 (right), 1:1 pixels%s" % (c.spec["name"], "" if gain == 1 else ", contrast x2 about each crop's mean")]
        hl += wrap_px(c.n3_en, font(20), 1890)
        HT = 10 + 28 * len(hl)
        D = Image.new("RGB", (1920, HT + len(rows) * (540 + 34)), (0, 0, 0))
        dd = ImageDraw.Draw(D)
        for i, l in enumerate(hl):
            dd.text((14, 6 + 28 * i), l, font=font(20), fill=(255, 255, 255) if i == 0 else (150, 255, 170))
        for r_i, (f, job, box, txt) in enumerate(rows):
            y = HT + r_i * (540 + 34)
            dd.text((14, y + 4), "%s  frame %d (%.3f s)" % (txt, f, (f - 1) / 24.0), font=font(20), fill=(255, 230, 120))
            for k, w in enumerate(("hero", "n3")):
                if f not in idx[(w, job)]:
                    continue
                cr = np.asarray(img(w, job, f).crop(box), np.float32)
                if gain != 1.0:
                    cr = np.clip((cr - cr.mean()) * gain + cr.mean(), 0, 255)
                D.paste(Image.fromarray(cr.astype(np.uint8)), (k * 960, y + 34))
        p = c.guard(c.video_dir + "/FLIP3D_%s_before_after_%s.jpg" % (c.tag, suf))
        D.save(p, quality=93)
        outs[suf] = rel(p)
    # ---- image measures [measured]: every 48th shared frame of cseat / cprint + the sheet frames; specks on the sheet frames only
    meas = {}
    for job in (("cseat", "cprint") if "--no-measures" not in a else ()):
        common = sorted(set(idx[("hero", job)]) & set(idx[("n3", job)]))
        pick = sorted(set(common[::48]) | (set(frames) & set(common)))
        per = []
        for f in pick:
            A = np.asarray(img("hero", job, f)); B = np.asarray(img("n3", job, f))
            m = US.water_mask(A) & US.water_mask(B)
            m = ndi.binary_erosion(m, iterations=8)
            if m.sum() < 1000:
                continue
            row = dict(frame=f, mask_px=int(m.sum()), mean_abs_diff_levels=float(np.abs(A.astype(np.float32) - B.astype(np.float32)).max(2)[m].mean()))
            for w, X in (("hero", A), ("n3", B)):
                Y = US.luma(X.astype(np.float32))
                g15 = ndi.gaussian_filter(Y, 1.5); g6 = ndi.gaussian_filter(Y, 6.0)
                row[w] = dict(fine=float(np.abs(Y - g15)[m].mean()), band=float(np.abs(g15 - g6)[m].mean()))
                if f in frames:
                    med = ndi.median_filter(Y, size=9)
                    row[w]["specks_per_mpx"] = float(((Y < med - 20.0) & m).sum() / m.sum() * 1e6)
            per.append(row)
        rb = np.array([r["n3"]["band"] / max(r["hero"]["band"], 1e-9) for r in per]) if per else np.zeros(0)
        rf = np.array([r["n3"]["fine"] / max(r["hero"]["fine"], 1e-9) for r in per]) if per else np.zeros(0)
        meas[job] = dict(n=len(per), band_ratio_n3_over_hero_median=float(np.median(rb)) if len(rb) else None,
                         band_ratio_min_max=[float(rb.min()), float(rb.max())] if len(rb) else None,
                         fine_ratio_n3_over_hero_median=float(np.median(rf)) if len(rf) else None,
                         mean_abs_diff_levels_median=float(np.median([r["mean_abs_diff_levels"] for r in per])) if per else None, frames=per)
    rep = dict(tool=TOOL + " sheet", time=time.strftime("%Y-%m-%d %H:%M:%S"), hero=c.spec["name"], n3_capture=rel(n3cap), hero_capture=rel(c.src_cap),
               sheets=outs, frames=frames, move_frame=mvf, measures=meas,
               rule=("hs_unity_sheet measures: water mask (hue < 205 deg, Y < 160) of BOTH pictures eroded 8 px; fine = mean |Y - G1.5|; band = mean "
                     "|G1.5 - G6| (2-8 px detail: facets / lumps); specks = darker than the 9x9 median by > 20 levels per Mpx; they count all detail, "
                     "not grid-ness alone [measured on the JPEG captures]"),
               honesty=H.honesty())
    rep["detail_frames"] = dfr
    rep["detail_boxes"] = [r[2] for r in rows]
    c.jdump(rep, H.hj("sheet_seat%s" % c.seat) if "--n3-cap" not in a else c.root + "/json/sheet_selftest.json")
    emit(dict(sheets=outs, detail_frames=dfr, measures={k: {kk: v[kk] for kk in ("n", "band_ratio_n3_over_hero_median", "fine_ratio_n3_over_hero_median",
                                                                                 "mean_abs_diff_levels_median")} for k, v in meas.items()}))
    return 0


CMDS = dict(plan=cmd_plan, selftest=cmd_selftest, apply=cmd_apply, verify=cmd_verify, clip=cmd_clip, unity=cmd_unity, capcheck=cmd_capcheck,
            video=cmd_video, sheet=cmd_sheet)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] not in CMDS:
        print(__doc__); sys.exit(1)
    if a[0] in ("plan", "verify", "clip", "capcheck", "video", "sheet"):
        set_priority("below")                                   # [chosen] reads / encodes below normal (ffmpeg inherits); apply sets idle itself
    sys.exit(CMDS[a[0]](a[1:]))
