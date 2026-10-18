# -*- coding: utf-8 -*-
"""FLIP52HS hs_unity_compare: the surfacing / smoothing variants of the water surface seen in UNITY from the same cameras
(py -3.10 -B; numpy, scipy, PIL). 2026-10-18 written new (Claude subagent).

Why (user 2026-10-18 ~16:35): "the grid of the water surface is very visible in the video; if it is a precision problem, raise the precision
and show it again; the big shape and the motion may already meet the supervisor's standard". The two earlier steps of this workflow made
(A) Houdini re-surfacings of the SAME particles on a crop (hs_surface_test.py: Unity/Build/FLIP52B/hires/test_f2112/<variant>/) and
(B) exporter-side smoothings of the hero's own records (hs_mesh_smooth.py: Unity/Build/FLIP52B/hires/test_smooth/<variant>/). This tool
puts them into the Unity FLIP3D player and captures every variant with the SAME cameras, then makes one comparison sheet.

Records (all GW45SRF1; the FLIP particles and every existing record are only READ):
  hero       the hero record as is (Unity/Build/FLIP52B/hero/runs/DFGB2Er_.../surf/s_FFFFF.gw45s), bytes copied, only the header frame
             number patched to the test clip's own record number (the player checks it).
  A crops    the Houdini crop variant covers x 200-300 m, lateral <= 40 m (triangle centroid rule of hs_surface_test.py). It is COMPOSITED:
             the hero's triangles whose centroid is outside the box shrunk by OVERLAP_M (1.5 m) + all the variant's triangles. Outside the box
             every A row shows the hero mesh unchanged; in a 1.5 m band inside the box edge both meshes overlap (the meshes are not stitched;
             without the overlap the gap showed the bed through a crack). The box edge is not the variant's own property.
  A + N3     the a0_v050_dse crop with its normals recomputed (area-weighted) and averaged 3 times over the one-ring (positions unchanged),
             then composited the same way (the combination of the two fixes; made here).
  B          the full-frame smoothed records of hs_mesh_smooth.py (N3, T2, T2S1wN2), bytes copied, header frame patched.
Clips (new folders; GW45LIST1 manifests that stream the test records, the hero clip's bed / seat / heave of the real frame):
  Unity/Build/FLIP3D/clip_hires_test_views        every record, the hero's seat A camera (cseat) and print camera (cprint)
  Unity/Build/FLIP3D/clip_hires_test_close_fFFFF  the records of frame FFFF, close-up cameras: cprint = the print camera position with half the
             field of view (11.75 deg) aimed at that frame's crest face; cseat = the seat A eye with half the field of view (27.5 deg) aimed at
             the centre of the lower half of the seat frame (the near water) -> 2x close-ups (twice the pixels per degree)
Unity: FLIP3DBatch.BuildSceneAndCapture through flip3d/f3d_unity.ps1 (unchanged), one batch at a time, free commit >= 8 GB before each,
  the tracked scene / material files backed up and restored to their pre-batch working-tree state. Captures under
  Unity/Build/FLIP52B/hires/unity_cmp/cap_<clip>/.
Tags: [measured] files / captures / earlier json; [computed] derived; [chosen] cameras, rows.

usage:
  py -3.10 -B hs_unity_compare.py build            records + clips (+ crest / camera json)
  py -3.10 -B hs_unity_compare.py unity [--only views|close_f2112|close_f2149] [--dry]
  py -3.10 -B hs_unity_compare.py check            capture frames.csv: shown record per frame, camera; b0_base vs hero pixel difference
  py -3.10 -B hs_unity_compare.py sheet            comparison sheets (rows = variants, columns = views) with deviation / cost
"""
import os, sys
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "2"
import json, math, time, struct, shutil, hashlib, subprocess, ctypes, csv

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                                    # noqa: E402
import hs_mesh_smooth as M                            # noqa: E402  (read_srf / write_srf / topo / awn / smooth_normals / crest_x)

REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOL = "Tools/GWWaveGen/flip52hs/hs_unity_compare.py"
B52B = REPO + "/Unity/Build/FLIP52B"
HIRES = B52B + "/hires"
OUT = HIRES + "/unity_cmp"
OUT3D = REPO + "/Unity/Build/FLIP3D"
HERO_RUN = B52B + "/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long"
HERO_CLIP = OUT3D + "/clip_DFGB2Er_f1153_3001_r24_seatA_ds"
TEST_A = HIRES + "/test_f2112"
TEST_B = HIRES + "/test_smooth"
UNITY_PS1 = REPO + "/Tools/GWWaveGen/flip3d/f3d_unity.ps1"
UNITY_METHOD = "GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture"
TRACKED = ["Unity/Assets/GreatWave/FLIP3D/Scenes/FLIP3D_Playback.unity"] + [
    "Unity/Assets/GreatWave/FLIP3D/Materials/FLIP3D_%s.mat" % m for m in ("Bed", "Sea", "Sky", "Water")]
COMMIT_MIN_GB = 8.0
FPS = 24.0
FAKE0 = 9001                                          # [chosen] the test clips' own record numbers (header frame patched; never a sim frame)
BOX = dict(x0=200.0, x1=300.0, z1=40.0)               # hs_surface_test.CROP (triangle centroid rule)
OVERLAP_M = 1.5                                       # [chosen] the hero mesh is kept 1.5 m into the box under the variant: no crack (gap) at the box edge

# rows [chosen]: (key, frame, kind, source, label, note)
ROWS = [
    ("hero", 2112, "copy", HERO_RUN + "/surf/s_%05d.gw45s", "hero (now)", "the hero record as played (0.5 m voxels, adaptivity 0.005)"),
    ("b0_base", 2112, "comp", TEST_A + "/b0_base/s_%05d.gw45s", "A b0_base (check)", "Houdini re-surface with the hero settings (must equal the hero)"),
    ("a0_adapt0", 2112, "comp", TEST_A + "/a0_adapt0/s_%05d.gw45s", "A adapt0", "0.5 m voxels, adaptivity 0"),
    ("v050", 2112, "comp", TEST_A + "/v050/s_%05d.gw45s", "A v050", "0.25 m voxels, adaptivity 0.005"),
    ("v050_dseg", 2112, "comp", TEST_A + "/v050_dseg/s_%05d.gw45s", "A v050_dseg", "0.25 m voxels, adapt 0.005, dilate 2 / mean-curv 2 / erode 2 / gauss 2"),
    ("a0_v050_dse", 2112, "comp", TEST_A + "/a0_v050_dse/s_%05d.gw45s", "A a0_v050_dse", "0.25 m voxels, adapt 0, dilate 2 / mean-curv 2 / erode 2"),
    ("a0_v050_dseg", 2112, "comp", TEST_A + "/a0_v050_dseg/s_%05d.gw45s", "A a0_v050_dseg", "0.25 m voxels, adapt 0, dse + gauss 2"),
    ("a0_v050_dse_N3", 2112, "compN3", TEST_A + "/a0_v050_dse/s_%05d.gw45s", "A a0_v050_dse + N3", "a0_v050_dse + area-weighted normals + 3 one-ring normal averages"),
    ("N3", 2112, "copy", TEST_B + "/N3/s_%05d.gw45s", "B N3", "hero mesh, normals recomputed + 3 averages (positions unchanged)"),
    ("T2S1wN2", 2112, "copy", TEST_B + "/T2S1wN2/s_%05d.gw45s", "B T2S1wN2", "hero mesh, Taubin 2 + 1-level subdivision x 180-320 / lat <= 60 + 2 normal averages"),
    ("hero", 2149, "copy", HERO_RUN + "/surf/s_%05d.gw45s", "hero (now)", "the hero record as played"),
    ("N3", 2149, "copy", TEST_B + "/N3/s_%05d.gw45s", "B N3", "normals recomputed + 3 averages"),
    ("T2", 2149, "copy", TEST_B + "/T2/s_%05d.gw45s", "B T2", "Taubin 2 pairs + area-weighted normals"),
    ("T2S1wN2", 2149, "copy", TEST_B + "/T2S1wN2/s_%05d.gw45s", "B T2S1wN2", "Taubin 2 + wide subdivision + 2 normal averages"),
]
FRAMES = (2112, 2149)


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(M.clean(o), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def guard_out(p):
    p = os.path.abspath(p).replace("\\", "/")
    ok = p.startswith(HIRES + "/") or p.startswith(OUT3D + "/clip_hires_test_")
    if not ok:
        raise SystemExit("refused: writes only under %s or %s/clip_hires_test_* (got %s)" % (rel(HIRES), rel(OUT3D), p))
    return p


# ====================================================================== records
def patch_copy(src, dst, fake):
    b = bytearray(open(src, "rb").read())
    if bytes(b[:8]) != b"GW45SRF1":
        raise SystemExit("not GW45SRF1: " + src)
    struct.pack_into("<i", b, 24, int(fake))                       # header: magic 8, ver 4, hb 4, t 8 -> frame int32 at byte 24
    open(guard_out(dst), "wb").write(bytes(b))


def composite(hero_path, var_path, dst, fake, n3=False):
    H = M.read_srf(hero_path)
    V = M.read_srf(var_path)
    if H["frame"] != V["frame"] or abs(H["off"] - V["off"]) > 1e-6:
        raise SystemExit("frame / offset mismatch %s %s" % (hero_path, var_path))
    c = H["P"][H["tri"]].mean(1)
    m = OVERLAP_M
    inbox = (c[:, 0] >= BOX["x0"] + m) & (c[:, 0] <= BOX["x1"] - m) & (c[:, 2] <= BOX["z1"] - m)
    cv = V["P"][V["tri"]].mean(1)
    v_out = ~((cv[:, 0] >= BOX["x0"] - 1e-3) & (cv[:, 0] <= BOX["x1"] + 1e-3) & (cv[:, 2] <= BOX["z1"] + 1e-3))
    ht = H["tri"][~inbox]
    hu = np.unique(ht)
    hmap = -np.ones(len(H["P"]), np.int64); hmap[hu] = np.arange(len(hu))
    VN = V["N"]
    info = dict(hero_tri_total=len(H["tri"]), hero_tri_in_box_dropped=int(inbox.sum()), var_tri=len(V["tri"]), var_tri_outside_box=int(v_out.sum()))
    if n3:
        T = M.topo(V["P"], V["tri"])
        s, frac = M.orient_sign(V["P"], V["tri"], V["N"])
        N0 = M.awn(V["P"], V["tri"], s, T["seam"])
        VN = M.smooth_normals(N0, T, 3)
        ang = np.degrees(np.arccos(np.clip((VN * V["N"]).sum(1), -1, 1)))
        info["n3"] = dict(orient_sign=s, orient_agree=frac, drawn_vs_stored_normal_deg_p50_p99_max=[float(np.percentile(ang, 50)), float(np.percentile(ang, 99)), float(ang.max())])
    P = np.vstack([H["P"][hu], V["P"]])
    N = np.vstack([H["N"][hu], VN])
    v = np.vstack([np.asarray(H["v"], np.float16)[hu], np.asarray(V["v"], np.float16)])
    tri = np.vstack([hmap[ht], V["tri"] + len(hu)])
    d = dict(t=H["t"], frame=int(fake), off=H["off"])
    M.write_srf(guard_out(dst), d, P, N, v, tri, force=True)
    rb = M.readback(dst, P, tri)
    info.update(nv=len(P), nt=len(tri), readback=rb)
    return info


def crest_info(frame):
    d = M.read_srf(HERO_RUN + "/surf/s_%05d.gw45s" % frame)
    xc, ec = M.crest_x(d["P"], d["tri"], d["off"])
    return dict(frame=frame, x_c=xc, eta_c=ec, off=d["off"], rule="hs_mesh_smooth.crest_x: highest point of the lateral 0.5 m section in x 230-300 m [measured]")


def cams(H, crest):
    """[chosen] close-up cameras (Unity x, y, z; z = -lateral: the seat and the print camera look at the mirrored half)."""
    seat_base = np.array([H["seat_x"], H["still_offset_m"] + H["seat_eye_m"], H["seat_z"]])
    look = np.array(H["cam_seat_look_at"], float)
    d = look - seat_base
    hd = math.hypot(d[0], d[2])
    pitch = math.degrees(math.atan2(d[1], hd))
    fov = float(H["cam_seat_fov_v"])
    p2 = pitch - fov / 4.0                                         # centre of the lower half of the seat frame
    az = np.array([d[0] / hd, 0.0, d[2] / hd])
    tgt = seat_base + 30.0 * (math.cos(math.radians(p2)) * az + np.array([0.0, math.sin(math.radians(p2)), 0.0]))
    near = dict(seat_look_at=[float(x) for x in tgt], seat_fov_v=fov / 2.0, seat_pitch_deg=p2, hero_seat_pitch_deg=pitch,
                rule="seat A eye (heave of the frame), same azimuth, pitched down by a quarter of the seat FOV, FOV / 2 = the lower-centre quarter of the seat frame at 2x")
    pp = list(H["cam_print_pos"])
    ce = [crest["x_c"] + 1.5, crest["off"] + crest["eta_c"] - 2.0, 0.0]
    close = dict(print_pos=pp, print_look_at=ce, print_fov_v=float(H["cam_print_fov_v"]) / 2.0,
                 rule="the print camera position, FOV / 2, aimed at (x_c + 1.5 m, crest - 2 m, centreline): the crest, lip and face of frame %d at 2x" % crest["frame"])
    return near, close


def manifest_for(H, recs, name, cam):
    m = dict(H)
    n = len(recs)
    for k in ("breakers", "hero", "notes_en", "breakers_source"):
        m.pop(k, None)
    m.update(format="GW45LIST1", clip_kind="continuous", clip_file="", clip_sha256="", frames=n, t_first=0.0, t_last=(n - 1) / FPS,
             frame_first=FAKE0, frame_last=FAKE0 + n - 1, loop_seconds=n / FPS, loop_start_s=0.0, loop_end_s=n / FPS, play_from_s=0.0,
             play_to_s=n / FPS, record_fps=FPS, sim_fps=FPS, record_step_frames=1,
             source_frames=[r["fake"] for r in recs], source_bytes=[r["bytes"] for r in recs], source_sha256=[r["sha256"] for r in recs],
             clip_bytes=int(sum(r["bytes"] for r in recs)), vert_max=int(max(r["nv"] for r in recs)), tri_max=int(max(r["nt"] for r in recs)),
             vert_min=int(min(r["nv"] for r in recs)), tri_min=int(min(r["nt"] for r in recs)),
             stream_dir=OUT + "/surf", stream_dir_rel=os.path.relpath(OUT + "/surf", OUT3D + "/" + name).replace("\\", "/"),
             stream_pattern="s_{0:D5}.gw45s", repeat=1, heave_fps=FPS, heave=[r["heave"] for r in recs],
             heave_min_m=float(min(r["heave"] for r in recs)), heave_max_m=float(max(r["heave"] for r in recs)),
             print_record_frame=FAKE0, print_record_index=0, print_record_t=0.0, breakers=[],
             source_run=rel(HERO_RUN), run_id="hires_test", created=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL,
             test_records=[dict((k, r[k]) for k in ("fake", "key", "frame", "label", "kind", "source")) for r in recs],
             test_note_en=("TEST CLIP (not the hero): one record per surfacing / smoothing variant of the SAME FLIP particles; the record numbers "
                           "%d.. are this clip's own; heave = the hero heave of each record's real frame; physics unchanged" % FAKE0))
    m.update(cam)
    return m


def cmd_build(a):
    H = jload(HERO_CLIP + "/manifest.json")
    os.makedirs(OUT + "/surf", exist_ok=True)
    recs = []
    for i, (key, f, kind, src, label, note) in enumerate(ROWS):
        fake = FAKE0 + i
        dst = OUT + "/surf/s_%05d.gw45s" % fake
        srcp = src % f
        t0 = time.time()
        info = {}
        if kind == "copy":
            patch_copy(srcp, dst, fake)
            d = M.read_srf(dst)
            info = dict(nv=len(d["P"]), nt=len(d["tri"]))
        else:
            info = composite(HERO_RUN + "/surf/s_%05d.gw45s" % f, srcp, dst, fake, n3=(kind == "compN3"))
        hv = float(H["heave"][f - int(H["frame_first"])])
        r = dict(fake=fake, key=key, frame=f, kind=kind, source=rel(srcp), label=label, note=note, path=rel(dst), bytes=os.path.getsize(dst),
                 sha256=sha(dst), nv=info["nv"], nt=info["nt"], heave=hv, info=info, seconds=round(time.time() - t0, 2))
        recs.append(r)
        print("rec", fake, key, f, kind, r["nv"], r["nt"], r["bytes"], r["seconds"], flush=True)
    crest = {f: crest_info(f) for f in FRAMES}
    clips = {}
    name = "clip_hires_test_views"
    cam = dict(cam_seat_look_at=H["cam_seat_look_at"], cam_seat_fov_v=H["cam_seat_fov_v"], cam_print_pos=H["cam_print_pos"],
               cam_print_look_at=H["cam_print_look_at"], cam_print_fov_v=H["cam_print_fov_v"],
               cam_note_ja="主役 DFGB2Er の座席 A・原画の視点と同じ（manifest の cam_* を写した）", cam_source_file=rel(HERO_CLIP + "/manifest.json"))
    clips[name] = (recs, cam)
    camj = {}
    for f in FRAMES:
        near, close = cams(H, crest[f])
        camj[f] = dict(near_water=near, crest_close=close, crest=crest[f])
        name = "clip_hires_test_close_f%d" % f
        cam = dict(cam_seat_look_at=near["seat_look_at"], cam_seat_fov_v=near["seat_fov_v"], cam_print_pos=close["print_pos"],
                   cam_print_look_at=close["print_look_at"], cam_print_fov_v=close["print_fov_v"],
                   cam_note_ja="2 倍の寄り：cseat = 座席 A の目から座席の画の下半分の中央（近くの水）、cprint = 原画の視点の位置から f%d の頂の前の面" % f)
        clips[name] = ([r for r in recs if r["frame"] == f], cam)
    out = {}
    for name, (rr, cam) in clips.items():
        cd = guard_out(OUT3D + "/" + name)
        os.makedirs(cd, exist_ok=True)
        shutil.copyfile(HERO_CLIP + "/bed.f32", cd + "/bed.f32")
        man = manifest_for(H, rr, name, cam)
        json.dump(man, open(cd + "/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out[name] = dict(dir=rel(cd), records=[r["fake"] for r in rr], vert_max=man["vert_max"], tri_max=man["tri_max"], bytes=man["clip_bytes"])
    rep = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " build", box=BOX, records=recs, crest=crest, cameras=camj, clips=out,
               tags="[measured] files; [chosen] rows, cameras, record numbers")
    jdump(rep, OUT + "/build.json")
    print(json.dumps(dict(clips=out, crest=crest), default=float, indent=1))
    return 0


# ====================================================================== Unity
class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def commit_free_gb():
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9, m.ullTotalPageFile / 1e9


def unity_one(name):
    clip = OUT3D + "/" + name
    cap = guard_out(OUT + "/cap_" + name.replace("clip_", ""))
    extra = ("-f3dcap cseat,cprint -f3dsize 1920x1080 -f3dfps 24 -f3dtiles 0 -f3dsha -f3ddata %s -f3dmoves none -f3dout %s" % (clip, cap))
    free, total = commit_free_gb()
    plan = dict(clip=rel(clip), extra=extra, commit_free_gb=round(free, 2), need_gb=COMMIT_MIN_GB)
    if free < COMMIT_MIN_GB:
        return dict(skipped="commit free %.2f GB < %.1f GB" % (free, COMMIT_MIN_GB), **plan)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = OUT + "/_unity_backup/" + stamp
    os.makedirs(bdir, exist_ok=True)
    before = {}
    for r in TRACKED:
        src = REPO + "/" + r
        dst = bdir + "/" + r.replace("/", "__")
        shutil.copyfile(src, dst)
        before[r] = sha(src)
        assert sha(dst) == before[r]
    t0 = time.time()
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UNITY_PS1, "-Method", UNITY_METHOD, "-Log", "hires_" + name,
           "-Extra", extra, "-TimeoutMinutes", "20", "-LockWaitMinutes", "30"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    finally:
        restored = {}
        for rr in TRACKED:
            dst = REPO + "/" + rr
            shutil.copyfile(bdir + "/" + rr.replace("/", "__"), dst)
            restored[rr] = sha(dst) == before[rr]
    line = [l for l in out.splitlines() if l.startswith("FLIP3D_UNITY ")]
    return dict(rc=rc, seconds=round(time.time() - t0, 1), unity_line=line[-1] if line else None, all_restored=all(restored.values()),
                backup=rel(bdir), tail=out[-800:], **plan)


def cmd_unity(a):
    only = opt(a, "--only")
    names = ["clip_hires_test_views"] + ["clip_hires_test_close_f%d" % f for f in FRAMES]
    if only:
        names = [n for n in names if n.endswith(only)]
    res = {}
    for n in names:
        if "--dry" in a:
            res[n] = dict(dry=True, free=commit_free_gb()[0]); continue
        res[n] = unity_one(n)
        print(json.dumps({n: {k: res[n].get(k) for k in ("rc", "seconds", "unity_line", "all_restored", "skipped", "commit_free_gb")}}), flush=True)
        if res[n].get("skipped") or res[n].get("rc") != 0 or not res[n].get("all_restored"):
            break
    old = jload(OUT + "/unity.json") or {}
    old.update(res)
    jdump(old, OUT + "/unity.json")
    return 0


# ====================================================================== checks
def frames_csv(capdir, job):
    p = capdir + "/" + job + "/frames.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    return rows


def cmd_check(a):
    from PIL import Image
    B = jload(OUT + "/build.json")
    res = {}
    for name in ["clip_hires_test_views"] + ["clip_hires_test_close_f%d" % f for f in FRAMES]:
        cd = OUT + "/cap_" + name.replace("clip_", "")
        man = jload(OUT3D + "/" + name + "/manifest.json")
        recs = man["test_records"]
        r = {}
        for job in ("cseat", "cprint"):
            rows = frames_csv(cd, job)
            shown = [int(x["record"]) for x in rows]
            r[job] = dict(frames=len(rows), shown_records=shown, ok=shown == list(range(len(recs))),
                          cam=[[float(x["cx"]), float(x["cy"]), float(x["cz"]), float(x["fov"])] for x in rows])
        res[name] = r
    # b0_base vs hero pixel difference (same frame 2112, same camera): the composite check
    diffs = {}
    for name in ["clip_hires_test_views", "clip_hires_test_close_f2112"]:
        cd = OUT + "/cap_" + name.replace("clip_", "")
        man = jload(OUT3D + "/" + name + "/manifest.json")
        idx = {(t["key"], t["frame"]): i for i, t in enumerate(man["test_records"])}
        for job in ("cseat", "cprint"):
            a0 = np.asarray(Image.open(cd + "/%s/frame_%05d.jpg" % (job, idx[("hero", 2112)])), np.float32)
            b0 = np.asarray(Image.open(cd + "/%s/frame_%05d.jpg" % (job, idx[("b0_base", 2112)])), np.float32)
            dd = np.abs(a0 - b0).max(2)
            diffs["%s/%s" % (name, job)] = dict(mean=float(dd.mean()), p99=float(np.percentile(dd, 99)), p999=float(np.percentile(dd, 99.9)), max=float(dd.max()),
                                               share_gt8=float((dd > 8).mean()))
    out = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " check", records=res, hero_vs_b0_base_pixels=diffs,
               tags="[measured] frames.csv and capture pixels (8-bit levels, max over RGB)")
    jdump(out, OUT + "/check.json")
    print(json.dumps(dict((k, {j: v[j]["ok"] for j in v}) for k, v in res.items()), indent=1))
    print(json.dumps(diffs, indent=1))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    M.low_priority()
    if not a:
        print(__doc__); sys.exit(1)
    c = a[0]
    if c == "build":
        sys.exit(cmd_build(a[1:]))
    if c == "unity":
        sys.exit(cmd_unity(a[1:]))
    if c == "check":
        sys.exit(cmd_check(a[1:]))
    if c == "sheet":
        import hs_unity_sheet as S
        sys.exit(S.main(a[1:]))
    print(__doc__); sys.exit(1)
