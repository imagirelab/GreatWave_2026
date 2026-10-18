# -*- coding: utf-8 -*-
"""DFG-2B-E hero PREVIEW from the existing 8/s surface records (py -3.10 -B; numpy, PIL, ffmpeg, Unity batch). 2026-10-18 written new
(Claude subagent, Q85: the user chose DFG-2B over DM1A, "DFG-2B 的效果更好").

What it is: the hero design (seat A, one visible seat -> print-view move to group 2's most print-like instant, frame 2149 = 89.5 s) played
in the unchanged FLIP3D Unity player from the judged run's OWN surf records, which exist only every 3rd frame (8 records/s) inside
55-69 / 83-97 / 111-125 s. It is a PREVIEW, not the hero: the hero needs the every-frame re-record (24/s) from checkpoint v.1152.
How 8/s records are shown at 24 fps (unchanged player rule): record = floor((t - t_first) x 8 + 1e-6), so every record is held for exactly
3 output frames; no shape is made between records (no interpolation, smoothing or blending). The camera (heave from hf at 24/s, the move
S-curve, FOV) is evaluated every output frame, so the camera moves smoothly while the water steps every 0.125 s.

Run (read only): Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5. DFG-2B-E is formally INVALID by two marginal gates (G2f inlet
5.6 s component phase 0.514 rad > 0.35; G6 group 1 peak 58.958 s, 0.042 s before 59.0 s). Energy (Q84): spectral sum a^2 = DM1A's
1.336 m^2, in-tank power 0.23 x DM1A. Every manifest, caption and sheet written here says so.
No existing tool file is edited: f3d50_export.main_long is imported unchanged and its manifest is patched afterwards (the pv53 make_clip
precedent); FLIP3DBatch.BuildSceneAndCapture runs unchanged through flip3d/f3d_unity.ps1 (unity.lock, one Unity at a time).
Writes only: Unity/Build/FLIP3D/clip_DFGB2E_*_preview/ (GW45LIST1 manifest that streams the run's surf files, no copy),
Unity/Build/FLIP3D/capture_DFGB2E_*_preview/ (Unity frames), Unity/Build/FLIP52B/hero/preview/ (checks, videos, still sheet, the
pre-batch backup of the tracked FLIP3D scene / materials). All of Unity/Build is git-ignored.
Unity batch safety: free commit memory >= 8 GB before the batch (GlobalMemoryStatusEx), the 5 tracked FLIP3D files that BuildScene
re-saves (FLIP3D_Playback.unity + 4 .mat) are copied before and restored byte-for-byte after (the pre-batch working-tree state, not
HEAD); ProjectSettings hashes are compared by f3d_unity.ps1.
Tags: 【測定】 measured records / captures, 【計算】 derived here, 【選び】 chosen (seat, poses, windows, move seconds).
usage:
  py -3.10 -B p52bh_preview.py export move|seat1          (writes the clip, patches the manifest)
  py -3.10 -B p52bh_preview.py unity move|seat1           (memory check, backup, Unity capture, restore)
  py -3.10 -B p52bh_preview.py check move|seat1           (capture log / record mapping / clearance / brightness checks -> json)
  py -3.10 -B p52bh_preview.py video move|seat1           (captioned mp4 per capture job)
  py -3.10 -B p52bh_preview.py sheet                      (still sheet: seat x4, move, group 1 seat, print views, section vs print)
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys, json, time, csv, io, shutil, hashlib, subprocess, contextlib, ctypes, math, re

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
for _p in (TOOLS + "/flip50g2", TOOLS + "/flip3d"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                       # noqa: E402

TOOL = "Tools/GWWaveGen/flip52bh/p52bh_preview.py"
RUN = REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5"
OUT3D = REPO + "/Unity/Build/FLIP3D"
HERO = REPO + "/Unity/Build/FLIP52B/hero/preview"
PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5"
UNITY_PS1 = TOOLS + "/flip3d/f3d_unity.ps1"
FPS = 24.0

SEAT = dict(x=284.0, z=-20.0, eye=1.5, look=[263.74, 6.04, 1.67], fov_v=55.0)          # 【選び】 seat A (dfgb2e_seats_finals rank 1; FOV 55 = DM1A hero precedent)
PRINT = dict(pos=[270.3725239459851, 4.000681399583817, -71.37486248981337],              # 【計算】 group 2's own pv53 option-D pose (scaled by Hc 6.814 / 7.160)
             look=[265.99486571327657, 5.475761891039959, 0.0], fov_v=23.5)
GROUPS = {   # 【測定】 pv53_DFGB2E...json periods: best frame, score3 and ruler at the best frame; window_frames = the pv53 scan windows
    1: dict(k=1, best=1470, score3=0.557, lip=0.2509505703421988, hood=0.05366565947173731, x_c=262.4500000000143, eta_c=6.575000000000264, win=[1380, 1488]),
    2: dict(k=2, best=2149, score3=0.770, lip=0.3117870722433379, hood=0.07587213925314587, x_c=265.50000000001387, eta_c=6.575000000000264, win=[2067, 2175]),
    3: dict(k=3, best=2824, score3=0.752, lip=0.30888030888030077, hood=0.09397593953580018, x_c=267.2000000000138, eta_c=6.4750000000002625, win=[2734, 2842]),
}
JOBS = {   # 【選び】 the preview design
    "move": dict(name="clip_DFGB2E_f1993_2329_r8_seatA_preview", cap="capture_DFGB2E_f1993_2329_r8_seatA_preview", from_s=82.9999, to_s=97.0001,
                 group=2, jobs="cseat,cprint,cmove", moves="-f3dmoves f2149 -f3dmovesec 4 -f3dhold 2 -f3dstay 4 -f3dback 3.5"),
    "seat1": dict(name="clip_DFGB2E_f1321_1657_r8_seatA_preview", cap="capture_DFGB2E_f1321_1657_r8_seatA_preview", from_s=54.9999, to_s=69.0001,
                  group=1, jobs="cseat", moves="-f3dmoves none"),
}
INVALID_EN = ("DFG-2B-E (DFGB2E_D19B_xf272p25_dp0p5), formally INVALID: G2f inlet 5.6 s phase 0.514 rad > 0.35, "
              "G6 group 1 peak 58.958 s, 0.042 s before 59.0 s")
ENERGY_EN = "energy: sum a^2 = DM1A's 1.336 m^2, in-tank power 0.23 x DM1A"
PREVIEW_EN = "PREVIEW, 8/s records (each record held 3 frames at 24 fps; no shapes between records)"
PHYS_EN = "physics only, 0.5 m Houdini FLIP; the judged run's own surf records (not re-recorded)"
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]
COMMIT_MIN_GB = 8.0


def t_of(f):
    return (f - 1) / FPS


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf8") as fh:
        return json.load(fh)


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf8") as fh:
        json.dump(o, fh, ensure_ascii=False, indent=1, default=float)


# ====================================================================== export + manifest patch
def export(key):
    J = JOBS[key]
    import f3d50_export as FX                      # unchanged
    args = ["--run", RUN, "--from-s", "%.4f" % J["from_s"], "--to-s", "%.4f" % J["to_s"], "--seat", "%g,%g" % (SEAT["x"], SEAT["z"]),
            "--eye", "%g" % SEAT["eye"], "--name", J["name"]]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        FX.main_long(args)
    out = OUT3D + "/" + J["name"]
    mp = out + "/manifest.json"
    man = jload(mp)
    sf = man["source_frames"]
    g = GROUPS[J["group"]]
    rs = np.array(sf)
    i = int(np.argmin(np.abs(rs - g["best"]) * 2 + (rs > g["best"])))      # nearest record, ties earlier (pv53 / f3d50_export rule)
    pr = int(rs[i])
    sc_pr = score3_at(J["group"], pr)
    brk = [dict(k=g["k"], frame=pr, t=t_of(pr), score3=g["score3"], win_first=g["win"][0], win_last=g["win"][1], hood=g["hood"], lip=g["lip"],
                frame_bestframes=g["best"], t_bestframes=t_of(g["best"]), record_offset_frames=pr - g["best"], xc_bestframes=g["x_c"],
                eta_c_bestframes=g["eta_c"], score3_at_record=sc_pr)]
    still = float(man["still_offset_m"])
    man.update(
        breaker_k=g["k"], print_record_frame=pr, print_record_t=t_of(pr), print_record_index=sf.index(pr), print_bestframes_frame=g["best"],
        print_bestframes_t=t_of(g["best"]), print_score3=g["score3"], print_crest_x=g["x_c"], print_crest_eta=still + g["eta_c"],
        breakers=brk,
        breakers_source=("pv53 most print-like instant of group %d (Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json: "
                         "score3 minimum on r2 every frame; window_frames = the pv53 scan window, not a cue)" % g["k"]),
        seat_x=SEAT["x"], seat_z=SEAT["z"], seat_eye_m=SEAT["eye"],
        cam_seat_look_at=SEAT["look"], cam_seat_fov_v=SEAT["fov_v"],
        cam_print_pos=PRINT["pos"], cam_print_look_at=PRINT["look"], cam_print_fov_v=PRINT["fov_v"],
        cam_source_file="Unity/Build/FLIP52B/hero/seats/dfgb2e_seats_finals.json (seat A) + pv53 group 2 option-D pose",
        cam_source_run="DFGB2E_D19B_xf272p25_dp0p5 (seat A rank 1; print pose = group 2's own pv53 pose, used for every group)",
        cam_note_ja=("座席 A（x 284・横 20 m・目は揺れの上 1.5 m、正面から 44〜52°、唇まで 26〜29 m）【選び】。原画の視点はグループ 2 の pv53 option-D の構図"
                     "（cameras_DM1A.json の構図を Hc 6.814 / 7.160 で縮めた物）を全部のグループに使う【計算】"),
        water_double_sided=True, water_double_sided_ja="表示だけ：水を両面で描く（DM1Ar seatA_ds・pv53 と同じ。記録・形は変えない）",
        half_width_ja=("面の記録は横 0〜97.5 m（cfg の crop_z1 = 95 m まで。95〜140 m は計算の中の横の帯で、記録しない。壁ではない）。tank_half_width は 95 m "
                       "【選び】。-f3dtiles 0 で見る（95 m の外は計算にない平らな海）。f3d50_export の書く『y = 140 m は壁、-f3dtiles 1』は DFG には誤りなので上書きした"),
        unity_notes_ja=("座席・原画の視点は manifest の cam_* から読む（ApplyManifestPoses）。FLIP3DExperience に -f3dmoves を渡さないとグループ 3 を選ぶので、"
                        "f2149 を明示する。VR（FLIP3DXR）では -f3dnocrestalign を渡す（渡さないと crestAlign が視点を約 −13 m ずらす）"),
        notes_en=[PREVIEW_EN, INVALID_EN, ENERGY_EN, PHYS_EN],
        notes_ja=["試写：8 個/s の記録（各記録を 24 fps の 3 フレーム見せる。記録の間の形は作らない）。本番は途中保存 v.1152 からの毎コマの記録し直し",
                  "DFG-2B-E は形式上は無効（G2f：入口の 5.6 s 成分の位相 0.514 rad > 0.35、G6：グループ 1 の頂 58.958 s が 59.0 s より 0.042 s 早い）",
                  "エネルギー：スペクトルの a² の和は DM1A と同じ 1.336 m²、水槽の中の力は DM1A の 0.23 倍"],
        preview=dict(tool=TOOL, key=key, group=J["group"], print_record=pr, score3_best_frame=g["score3"], score3_at_record=sc_pr,
                     record_rule="record = floor((t - t_first) x record_fps + 1e-6), held 3 output frames at 24 fps; no shapes between records",
                     date=time.strftime("%Y-%m-%d %H:%M:%S")))
    jdump(man, mp)
    res = dict(clip=out, records=len(sf), frames=[sf[0], sf[-1]], t=[man["t_first"], man["t_last"]], play=[man["play_from_s"], man["play_to_s"]],
               record_fps=man["record_fps"], bytes=man["clip_bytes"], print_record=pr, print_index=sf.index(pr), score3_at_record=sc_pr,
               heave=[man["heave_min_m"], man["heave_max_m"]], heave_n=len(man["heave"]), still=still, exporter_stdout=buf.getvalue()[-600:])
    print(json.dumps({k: v for k, v in res.items() if k != "exporter_stdout"}, ensure_ascii=False, indent=1))
    return res


def score3_at(group, frame):
    try:
        S = jload(PV53 + "/pv53_DFGB2E_D19B_xf272p25_dp0p5.json")["series"][str(group)]
        for r in S:
            if int(r["frame"]) == int(frame):
                return r["score3"]
    except Exception:
        pass
    return None


# ====================================================================== Unity batch
def commit_free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2 ** 30, m.ullTotalPageFile / 2 ** 30


def git_tracked_status():
    p = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-uno"], capture_output=True, text=True, encoding="utf8")
    return p.stdout


def unity(key):
    J = JOBS[key]
    free, lim = commit_free_gb()
    print("commit free %.2f GB of %.2f GB" % (free, lim), flush=True)
    if free < COMMIT_MIN_GB:
        raise SystemExit("free commit %.2f GB < %.1f GB: not starting Unity" % (free, COMMIT_MIN_GB))
    if os.path.exists(REPO + "/Unity/Build/unity.lock"):
        raise SystemExit("unity.lock exists: another Unity batch is running")
    bdir = HERO + "/_unity_backup/" + key + "_" + time.strftime("%Y%m%d_%H%M%S")
    os.makedirs(bdir, exist_ok=True)
    pre = {}
    for rp in TRACKED:
        src = REPO + "/" + rp
        dst = bdir + "/" + os.path.basename(rp)
        shutil.copy2(src, dst)
        pre[rp] = sha(src)
        if sha(dst) != pre[rp]:
            raise SystemExit("backup copy differs: " + rp)
    st0 = git_tracked_status()
    jdump(dict(files=pre, git_status_uno=st0, date=time.strftime("%Y-%m-%d %H:%M:%S")), bdir + "/pre_batch.json")
    clip = OUT3D + "/" + J["name"]
    cap = OUT3D + "/" + J["cap"]
    extra = "-f3dcap %s -f3ddata %s -f3dout %s -f3dsize 1920x1080 -f3dfps 24 -f3dtiles 0 %s" % (J["jobs"], clip, cap, J["moves"])
    log_name = "p52bh_" + J["cap"]
    ps = "& '%s' -Method 'GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture' -Log '%s' -Extra '%s' -LockWaitMinutes 2 -TimeoutMinutes 30" % (
        UNITY_PS1, log_name, extra)
    t0 = time.time()
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    finally:
        restored = {}
        for rp in TRACKED:
            src = bdir + "/" + os.path.basename(rp)
            dst = REPO + "/" + rp
            if not os.path.exists(dst) or sha(dst) != pre[rp]:
                shutil.copy2(src, dst)
                restored[rp] = "restored"
            else:
                restored[rp] = "unchanged"
        ok = all(sha(REPO + "/" + rp) == pre[rp] for rp in TRACKED)
    st1 = git_tracked_status()
    res = dict(key=key, rc=rc, seconds=round(time.time() - t0, 1), tail=out.strip().splitlines()[-3:] if out.strip() else [], extra=extra,
               log=OUT3D + "/logs/unity_" + log_name + ".log", backup=bdir, restore=restored, restored_equal_pre_batch=ok,
               git_status_same=st0 == st1, git_status_after=st1, commit_free_before_gb=round(free, 2), commit_free_after_gb=round(commit_free_gb()[0], 2),
               lock_released=not os.path.exists(REPO + "/Unity/Build/unity.lock"))
    jdump(res, HERO + "/unity_" + key + ".json")
    print(json.dumps({k: v for k, v in res.items() if k != "git_status_after"}, ensure_ascii=False, indent=1))
    return res


# ====================================================================== checks
def rows_of(capdir, job):
    p = capdir + "/" + job + "/frames.csv"
    with open(p, encoding="utf8") as fh:
        return list(csv.DictReader(fh))


class Surf:
    def __init__(self):
        import f3d_common as C
        self.C = C
        self.cache = {}

    def get(self, f):
        if f not in self.cache:
            if len(self.cache) > 8:
                self.cache.pop(next(iter(self.cache)))
            d = self.C.read_surf(f, RUN)
            self.cache[f] = np.asarray(d["P"], np.float64)
        return self.cache[f]


def col_max(P, x, lat, r):
    m = (np.abs(P[:, 0] - x) <= r) & (np.abs(P[:, 2] - lat) <= r)
    if not m.any():
        return None
    return float(P[m, 1].max())


def foot_max(P, x, lat, fx=4.0, fz=1.5):
    m = (np.abs(P[:, 0] - x) <= fx) & (np.abs(P[:, 2] - lat) <= fz)
    if not m.any():
        return None
    return float(P[m, 1].max())


def hf_at(e, xs, zs, x, lat):
    ix = (x - xs[0]) / (xs[1] - xs[0]); iz = (lat - zs[0]) / (zs[1] - zs[0])
    i0, k0 = int(math.floor(ix)), int(math.floor(iz))
    if i0 < 0 or k0 < 0 or i0 + 1 >= len(xs) or k0 + 1 >= len(zs):
        return None
    a, b = ix - i0, iz - k0
    v = (e[k0, i0] * (1 - a) * (1 - b) + e[k0, i0 + 1] * a * (1 - b) + e[k0 + 1, i0] * (1 - a) * b + e[k0 + 1, i0 + 1] * a * b)
    return float(v) if np.isfinite(v) else None


def hf_near_max(e, xs, zs, x, lat, half=2.0):
    sx = (xs >= x - half) & (xs <= x + half); sz = (zs >= lat - half) & (zs <= lat + half)
    v = e[np.ix_(sz, sx)]
    v = v[np.isfinite(v)]
    return float(v.max()) if len(v) else None


def check(key):
    import f3d_common as C
    J = JOBS[key]
    capdir = OUT3D + "/" + J["cap"]
    man = jload(OUT3D + "/" + J["name"] + "/manifest.json")
    sf = man["source_frames"]
    step = int(man["record_step_frames"])
    t0 = float(man["t_first"])
    still = float(man["still_offset_m"])
    log = open(OUT3D + "/logs/unity_p52bh_" + J["cap"] + ".log", encoding="utf8", errors="replace").read()
    lines = [ln for ln in log.splitlines() if ln.startswith(("FLIP3D_CSEQ", "FLIP3D_POSES", "FLIP3D_INIT", "FLIP3D_WATER", "FLIP3D_STREAM_STATS", "FLIP3D_MOVES", "FLIP3D_CAPTURE"))]
    hf = C.Rec("hf", RUN)
    xs, zs = C.axes_hf(hf.meta)
    S = Surf()
    out = dict(key=key, clip=J["name"], capture=J["cap"], log_lines=lines, jobs={})
    pr_i = int(man["print_record_index"])
    for job in J["jobs"].split(","):
        rows = rows_of(capdir, job)
        n = len(rows)
        rec = np.array([int(r["record"]) for r in rows]); frz = np.array([int(r["frozen"]) for r in rows])
        sfr = np.array([int(r["sim_frame"]) for r in rows]); st = np.array([float(r["sim_t"]) for r in rows])
        s = np.array([float(r["s"]) for r in rows]); bl = np.array([float(r["blend"]) for r in rows])
        cam = np.array([[float(r["cx"]), float(r["cy"]), float(r["cz"])] for r in rows]); fov = np.array([float(r["fov"]) for r in rows])
        # record mapping: experience time minus the holds already passed -> clock c; expected record = floor(c x fps + 1e-6)
        held = np.cumsum(np.r_[0, frz[:-1]]) / FPS                     # seconds of frozen clock before frame i
        c = s - held
        exp = np.floor(c * float(man["record_fps"]) + 1e-6).astype(int)
        exp_hold = exp.copy()
        mism = [int(i) for i in np.where((rec != exp) & (frz == 0))[0]]
        runs, cur, cnt = [], rec[0], 0
        for r_ in rec:
            if r_ == cur:
                cnt += 1
            else:
                runs.append((int(cur), cnt)); cur, cnt = r_, 1
        runs.append((int(cur), cnt))
        seq_ok = all(b == a + 1 for (a, _), (b, _) in zip(runs[:-1], runs[1:]))
        counts = {}
        for r_, k_ in runs:
            counts.setdefault(k_, []).append(r_)
        frame_ok = bool(np.all(sfr == np.array([sf[r_] for r_ in rec])))
        # clearance on every output frame: camera y minus the shown record's surface (column r 1 m and boat footprint 4 x 1.5 m),
        # and minus hf at the shown record frame and at the 24/s frame of the true clock time
        cm, fm, hs, ht, hn, c5, d3 = [], [], [], [], [], [], []
        for i in range(n):
            x, y, z = cam[i]; lat = abs(z)
            P = S.get(int(sfr[i]))
            v = col_max(P, x, lat, 1.0); cm.append(None if v is None else y - v)
            v = col_max(P, x, lat, 0.5); c5.append(None if v is None else y - v)      # the seat search's definition (+-0.5 m column)
            m3 = (np.abs(P[:, 0] - x) <= 3.0) & (np.abs(P[:, 2] - lat) <= 3.0)
            d3.append(float(np.sqrt(((P[m3] - np.array([x, y, lat])) ** 2).sum(axis=1)).min()) if m3.any() else None)   # near clip 0.3 m
            if bl[i] <= 0.0:
                v = foot_max(P, x, lat); fm.append(None if v is None else y - v)
            e = hf.get(int(sfr[i])); v = hf_at(e, xs, zs, x, lat); hs.append(None if v is None else y - v)
            ftrue = int(round(t0 * FPS + c[i] * FPS)) + 1 if not frz[i] else int(sfr[i])
            if ftrue in hf.where:
                e2 = hf.get(ftrue); v = hf_at(e2, xs, zs, x, lat); ht.append(None if v is None else y - v)
                v = hf_near_max(e2, xs, zs, x, lat); hn.append(None if v is None else y - v)

        def mn(a):
            a = [v for v in a if v is not None]
            return (round(float(min(a)), 3), int(len(a))) if a else (None, 0)
        cmin = mn(cm)
        cidx = int(np.nanargmin([v if v is not None else np.nan for v in cm])) if cmin[1] else None
        worst = {}
        for nm_, arr_ in (("col05", c5), ("hf_true", ht), ("near3d", d3)):
            vv = [v if v is not None else np.nan for v in arr_]
            if len(vv) and np.isfinite(vv).any():
                k_ = int(np.nanargmin(vv))
                worst[nm_] = dict(i=k_, s=float(s[k_]), sim_t=float(st[k_]), sim_frame=int(sfr[k_]), blend=float(bl[k_]), value=round(float(vv[k_]), 3),
                                  cam=[round(float(q), 2) for q in cam[k_]])
        below1 = [int(i) for i, v in enumerate(c5) if v is not None and v < 1.0]
        # brightness of every frame (white-out check): mean luminance, largest frame-to-frame change
        from PIL import Image
        lum = []
        for i in range(0, n):
            im = Image.open(capdir + "/" + job + "/frame_%05d.jpg" % i).convert("L").resize((96, 54))
            lum.append(float(np.asarray(im, np.float32).mean()))
        lum = np.array(lum)
        J2 = dict(frames=n, seconds=n / FPS, records_shown=len(runs), first_record=int(rec[0]), last_record=int(rec[-1]),
                  sequential_records=seq_ok, hold_counts={str(k): (v if len(v) <= 6 else [v[0], "...", v[-1], "n=%d" % len(v)]) for k, v in counts.items()},
                  record_mismatch_unfrozen=mism[:10], n_record_mismatch_unfrozen=len(mism), sim_frame_equals_source_frames=frame_ok,
                  frozen_frames=int(frz.sum()), frozen_records=sorted(set(int(r_) for r_ in rec[frz == 1])),
                  print_record_index=pr_i, print_record_frames_shown=int((rec == pr_i).sum()),
                  cam_y=[round(float(cam[:, 1].min()), 3), round(float(cam[:, 1].max()), 3)], fov=[float(fov.min()), float(fov.max())],
                  clear_mesh_col1m_min=cmin, clear_mesh_col1m_min_at=(dict(i=cidx, sim_frame=int(sfr[cidx]), s=float(s[cidx]), blend=float(bl[cidx]),
                                                                            cam=[round(float(v), 2) for v in cam[cidx]]) if cidx is not None else None),
                  clear_mesh_col05m_min=mn(c5), mesh_vertex_nearest_3d_min=mn(d3),
                  clear_mesh_boat_footprint_min_on_seat=mn(fm), clear_hf_shown_record_min=mn(hs), clear_hf_true_time_min=mn(ht),
                  clear_hf_true_time_near2m_min=mn(hn),
                  worst=worst, n_frames_col05_below_1m=len(below1), frames_col05_below_1m=(below1[:3] + ["..."] + below1[-3:]) if len(below1) > 6 else below1,
                  lum_mean=[round(float(lum.min()), 1), round(float(lum.max()), 1)], lum_max_step=round(float(np.abs(np.diff(lum)).max()), 2),
                  lum_max_step_at=int(np.argmax(np.abs(np.diff(lum)))) + 1)
        if job == "cmove":
            mv = np.where((bl > 0) & (bl < 1))[0]
            arr = np.where(bl >= 1)[0]
            J2.update(move_frames=[int(mv[0]), int(mv[-1])] if len(mv) else None, blend_first_1=int(arr[0]) if len(arr) else None,
                      blend_last_1=int(arr[-1]) if len(arr) else None,
                      blend_first_1_record=int(rec[arr[0]]) if len(arr) else None, blend_first_1_sim_frame=int(sfr[arr[0]]) if len(arr) else None,
                      move_start_sim_t=float(st[mv[0]]) if len(mv) else None,
                      on_seat_end_s=float(s[mv[0] - 1]) if len(mv) else None,
                      back_on_seat_from_s=float(s[np.where((bl <= 0) & (np.arange(n) > (arr[-1] if len(arr) else 0)))[0][0]]) if len(arr) and (bl[arr[-1]:] <= 0).any() else None,
                      move_speed_max_mps=round(float(np.max(np.linalg.norm(np.diff(cam, axis=0), axis=1)) * FPS), 2),
                      move_path_m=round(float(np.sum(np.linalg.norm(np.diff(cam[mv[0] - 1:arr[0] + 1], axis=0), axis=1))), 2) if len(mv) and len(arr) else None)
        out["jobs"][job] = J2
    out["heave_m"] = [man["heave_min_m"], man["heave_max_m"]]
    hv = np.array(man["heave"]); out["heave_max_rate_mps"] = round(float(np.abs(np.diff(hv)).max() * FPS), 3)
    out["still_offset_m"] = still
    out["tags"] = "capture rows, records, hf 【測定】; clearances, mapping, brightness 【計算】"
    jdump(out, HERO + "/check_" + key + ".json")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
    return out


# ====================================================================== projection (print framing) and video
def project(cam, look, fov_v, P, W=1920, H=1080):
    """normalised screen coords (-1..1 = half-widths) of point P for a camera at cam looking at look (Unity, y up, no roll)."""
    cam, look, P = np.array(cam, float), np.array(look, float), np.array(P, float)
    f = look - cam; f /= np.linalg.norm(f)
    r = np.cross(np.array([0, 1.0, 0]), f); r /= np.linalg.norm(r)       # Unity left-handed: right = up x forward
    u = np.cross(f, r)
    d = P - cam
    zc = d @ f
    th = math.tan(math.radians(fov_v) / 2)
    return float((d @ r) / zc / (th * W / H)), float((d @ u) / zc / th)


def video(key):
    import f3d_video as V
    from PIL import Image, ImageDraw
    J = JOBS[key]
    capdir = OUT3D + "/" + J["cap"]
    man = jload(OUT3D + "/" + J["name"] + "/manifest.json")
    g = GROUPS[J["group"]]
    os.makedirs(HERO, exist_ok=True)
    res = []
    names = {"cseat": "boat seat A (x 284, lateral 20 m, eye 1.5 m above the heave) / 座席 A",
             "cprint": "print view (group 2 pv53 option-D pose) / 原画の視点",
             "cmove": "seat A -> print view, visible move arriving at frame %d (%.3f s), no white-out / 座席→原画の視点" % (man["print_record_frame"], man["print_record_t"])}
    fonts = {}

    def fit(text, size, width):
        s_ = size
        while True:
            f_ = fonts.get(s_) or fonts.setdefault(s_, V.F(s_))
            if s_ <= 12 or f_.getlength(text) <= width:
                return f_
            s_ -= 1
    for job in J["jobs"].split(","):
        rows = rows_of(capdir, job)
        cap = jload(capdir + "/" + job + "/capture.json")
        tmp = HERO + "/_frames_" + key + "_" + job
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        title = PREVIEW_EN + " | " + names[job]
        l2 = INVALID_EN + " | " + ENERGY_EN
        l3 = ("%s. Records %d-%d (%.3f-%.3f s), %d records at %g/s streamed from the run's surf folder; seat and print poses from the manifest%s"
              % (PHYS_EN, man["frame_first"], man["frame_last"], man["t_first"], man["t_last"], man["frames"], man["record_fps"],
                 ("; move %s" % (re.search(r"schedule=(\S+)", " ".join(open(OUT3D + "/logs/unity_p52bh_" + J["cap"] + ".log", encoding="utf8", errors="replace").read().splitlines()[-4000:])) or [None, ""])[1]
                                 if job == "cmove" else "")))
        for i, r in enumerate(rows):
            im = Image.open(capdir + "/" + job + "/frame_%05d.jpg" % i).convert("RGBA")
            W, H = im.size
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
            dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150)); dr.rectangle([0, H - 52, W, H], fill=(0, 0, 0, 150))
            im = Image.alpha_composite(im, ov); dr = ImageDraw.Draw(im)
            dr.text((18, 8), title, font=fit(title, 26, W - 36), fill=(255, 255, 255))
            dr.text((18, 46), l2, font=fit(l2, 19, W - 36), fill=(255, 225, 150))
            dr.text((18, 74), l3, font=fit(l3, 19, W - 36), fill=(225, 225, 225))
            rec, sfr, frz, bl = int(r["record"]), int(r["sim_frame"]), int(r["frozen"]), float(r["blend"])
            stt = "sim t %.3f s (frame %d, record %d/%d, record held 3 output frames)" % (float(r["sim_t"]), sfr, rec + 1, man["frames"])
            if job == "cmove":
                stt += " | camera: " + ("seat" if bl <= 0 else ("print view" if bl >= 1 else "moving %.0f %%" % (bl * 100)))
            if rec == man["print_record_index"]:
                stt += " | * group %d most print-like instant (pv53 score3 %.3f at frame %d%s)" % (
                    g["k"], g["score3"], g["best"], "" if man["print_record_frame"] == g["best"] else ", shown = nearest record %d" % man["print_record_frame"])
            if frz:
                stt += " | HOLD (playback clock stopped)"
            dr.text((18, H - 40), stt, font=fit(stt, 22, W - 36), fill=(255, 255, 255))
            im.convert("RGB").save(tmp + "/f_%05d.jpg" % i, quality=92)
        mp4 = HERO + "/DFGB2E_preview_%s_%s.mp4" % (key, job)
        subprocess.run([V.C.FFMPEG, "-y", "-loglevel", "error", "-threads", "2", "-framerate", "24", "-i", tmp + "/f_%05d.jpg", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", mp4], check=True)
        keep = HERO + "/_cap_" + key + "_" + job
        shutil.rmtree(keep, ignore_errors=True)
        os.rename(tmp, keep)                     # captioned frames kept for the sheet / inspection (Unity/Build, git-ignored)
        res.append(dict(job=job, mp4=mp4, frames=len(rows), seconds=len(rows) / FPS, bytes=os.path.getsize(mp4), mode=cap.get("mode")))
    jdump(res, HERO + "/video_" + key + ".json")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return res


# ====================================================================== still sheet
def frame_at(capdir, job, sim_frame=None, sim_t=None, first_hold=True):
    rows = rows_of(capdir, job)
    if sim_frame is not None:
        hit = [r for r in rows if int(r["sim_frame"]) == int(sim_frame)]
    else:
        best = min(abs(float(r["sim_t"]) - sim_t) for r in rows)
        hit = [r for r in rows if abs(float(r["sim_t"]) - sim_t) <= best + 1e-9]
    r = hit[0]
    return capdir + "/" + job + "/frame_%05d.jpg" % int(r["i"]), r


def sheet():
    from PIL import Image, ImageDraw, ImageFont
    import f3d_video as V
    capM = OUT3D + "/" + JOBS["move"]["cap"]
    cap1 = OUT3D + "/" + JOBS["seat1"]["cap"]
    W, H = 640, 360
    pan = []
    for f in (2065, 2104, 2149, 2185):
        p, r = frame_at(capM, "cseat", sim_frame=f)
        pan.append((p, "seat A, group 2, t %.3f s (frame %d)%s" % (float(r["sim_t"]), int(r["sim_frame"]), " = most print-like (score3 0.770)" if f == 2149 else
                                                                  (" near the converged crest peak (87.58 s)" if f == 2104 else (" 1.5 s later: the broken crest runs toward the seat" if f == 2185 else " rising")))))
    rows = rows_of(capM, "cmove")
    mid = min(rows, key=lambda r: abs(float(r["blend"]) - 0.5))
    pan.append((capM + "/cmove/frame_%05d.jpg" % int(mid["i"]), "move seat -> print view, %.0f %% (t %.3f s), no white-out" % (float(mid["blend"]) * 100, float(mid["sim_t"]))))
    p, r = frame_at(cap1, "cseat", sim_frame=1471)
    pan.append((p, "seat A, group 1 curl, t %.3f s (record 1471; best frame 1470 score3 0.557)" % float(r["sim_t"])))
    p, r = frame_at(capM, "cprint", sim_frame=2149)
    pan.append((p, "print view, this preview, frame 2149 (89.500 s), 1920x1080"))
    pan.append((PV53 + "/DFGB2E_D19B_xf272p25_dp0p5_converged_printview_f2149.jpg", "pv53 print view still, frame 2149 (same pose, 1280x720)"))
    pan.append((None, "centre section r2 at frame 2149 vs print outline (black), pv53 draw_section"))
    S = Image.new("RGB", (3 * W + 4 * 12, 3 * (H + 30) + 150), (247, 247, 244))
    dr = ImageDraw.Draw(S)
    F = lambda s: V.F(s)
    dr.text((12, 8), PREVIEW_EN, font=F(22), fill=(160, 20, 20))
    dr.text((12, 40), INVALID_EN, font=F(16), fill=(20, 20, 20))
    dr.text((12, 62), ENERGY_EN + " | " + PHYS_EN, font=F(16), fill=(20, 20, 20))
    dr.text((12, 84), "seat A (284, -20), eye 1.5 m, look (263.74, 6.04, 1.67), FOV 55; print pose (270.373, 4.001, -71.375) -> (265.995, 5.476, 0), FOV 23.5",
            font=F(15), fill=(80, 80, 80))
    rep = PV53 + "/pv53_DFGB2E_D19B_xf272p25_dp0p5.png"
    y0 = 150
    for j, (p, lab) in enumerate(pan):
        x = 12 + (j % 3) * (W + 12); y = y0 + (j // 3) * (H + 30)
        dr.text((x, y), lab, font=F(14), fill=(20, 20, 20))
        if p is None:
            src = section_crop(rep)
        else:
            src = Image.open(p).convert("RGB")
        if src is not None:
            sc = min(W / src.width, H / src.height)
            src = src.resize((max(1, int(src.width * sc)), max(1, int(src.height * sc))), Image.LANCZOS)
            S.paste(src, (x + (W - src.width) // 2, y + 22 + (H - src.height) // 2))
    out = HERO + "/DFGB2E_preview_sheet.jpg"
    S.save(out, quality=92)
    print(out)
    return out


def section_png(group=2):
    """the centre section r2 (y 0.5 m) at the group's pv53 best frame with the print outline, drawn by pv53.draw_section (imported,
    unchanged; the pv53 report itself shows group 1 only)."""
    out = HERO + "/section_g%d_f%d.png" % (group, GROUPS[group]["best"])
    if os.path.exists(out):
        return out
    sys.path.insert(0, TOOLS + "/flip53")
    import pv53 as PV                           # unchanged
    from PIL import Image
    R = PV.PVRun(RUN)
    J = jload(PV53 + "/pv53_DFGB2E_D19B_xf272p25_dp0p5.json")
    best = dict(J["periods"][group - 1]["best"])
    im = Image.new("RGB", (900, 380), PV.BG)
    PV.draw_section(im, R, best, (10, 34, 870, 330), PV.reference())
    im.save(out)
    return out


def section_crop(rep):
    from PIL import Image
    try:
        return Image.open(section_png(2)).convert("RGB")
    except Exception as ex:
        print("section not drawn: %r" % ex)
        return None


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    cmd = a[0]
    if cmd == "export":
        export(a[1])
    elif cmd == "unity":
        unity(a[1])
    elif cmd == "check":
        check(a[1])
    elif cmd == "video":
        video(a[1])
    elif cmd == "sheet":
        sheet()
    elif cmd == "section":
        print(section_png(int(a[1]) if len(a) > 1 else 2))
    else:
        print(__doc__); sys.exit(1)
