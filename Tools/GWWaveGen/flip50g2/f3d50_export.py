# -*- coding: utf-8 -*-
"""FLIP50 (option D) surface records -> clips for the FLIP3D Unity player (py -3.10 -B, numpy + scipy). 2026-10-17 written new (Claude).

Why a new file: flip3d/f3d_export.py is DA3-specific (bed from the DA3 cfg via g49_common, tank 442 x 85 m, breakers from DA3's
pana/best_frames.json, --long only for every-frame records). FLIP50 runs differ in all four: tank Lx 412 m, half width W 140 m with the
surface recorded only to y 95 m (crop_z1; the 95-140 m side band is a relaxation band), the D19B (+ DG1 groove) bed, their own
pana/best_frames.json, and records every 3rd frame (8 records/s) from 44 s. No file of flip3d, flip45-flip50 or flip50g is edited:
this imports f3d_common (the GW45SRF1 reader through g45_export_unity, read only), g50_common (bed functions, read only) and, only when
the run's cfg carries bed.groove (DG1), g50g_common.patch_modules() (in-memory bed patch, never a file edit). Run folders are read only.
Writes only Unity/Build/FLIP3D/<name>/ (outside Git).

  long  one continuous clip (no loop, no seam), GW45LIST1: Unity streams the run's own surf/s_FFFFF.gw45s files (no copy)
        py -3.10 -B f3d50_export.py long --run DM1A_D19B_T12_th80_dp0p5 [--from-s 44 --to-s 92] [--play S0,S1] [--print-k K] [--name N]
  loop  one wave-period window (T of the run cfg: 12 s = 288 frames for DM1A / DG1, 10 s = 240 for DF1A), GW45CLP1 (one file; the player keeps it all on the GPU; key [4] can switch to it)
        py -3.10 -B f3d50_export.py loop --run DM1A_D19B_T12_th80_dp0p5 [--k K] [--name N]
  both: [--seat X,Z] (default 300,-35 = the DA3 clips' seat) [--eye M] [--half-width W] (default cfg parms crop_z1 = 95 m) [--dry]

Playback rule (unchanged player): record floor(phase x record_fps); record_fps = 24 / record step (8 for every-3rd-frame records, 24 for an
every-frame re-record). No shape between records is made (no interpolation, smoothing or blending).
Loop window rule (written before measuring; the FLIP3D section 1 rule with its AM-L1 addition, and the floor-free surface distance of
AM-24a): L = one wave period T of the run (288 frames for T 12 s). For each judged breaker k of the run (pana/best_frames.json) the window start tau runs over the record frames
with tau <= window_first(k) and tau + L - 1 >= window_last(k) (onset .. touchdown + 0.5 s inside) and tau + L a record frame. Seam = the
symmetric nearest-point distance between the surface at tau and at tau + L (vertices against vertices + triangle centroids, inside the
break box x 190-335 m, lateral 0-95 m). Per breaker the tau with the smallest seam p95; then among breakers whose best p95 <= 1.05 x the
smallest, the smallest score3 (closest to the print). The print record = the record frame nearest best_frames' frame (ties: earlier).
Reported with it: hf delta-eta RMS of the seam (same box) and the median p95 of the ordinary one-record steps inside the window.
Tags: 【測定】 measured records, 【計算】 numbers derived here, 【選び】 chosen (seat, half width, box, rule).
"""
import os, sys, json, struct, hashlib, time

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in (REPO + "/Tools/GWWaveGen/flip3d", REPO + "/Tools/GWWaveGen/flip50", REPO + "/Tools/GWWaveGen/flip50g"):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                  # noqa: E402
import f3d_common as C              # noqa: E402  reader only (GW45SRF1, hf/r4 blocks); never edited
import g50_common as GC50           # noqa: E402  bed functions, read only

B50 = GC50.B50
OUT = C.OUT                          # Unity/Build/FLIP3D
FPS = 24.0
SEAT = (300.0, -35.0)                # 【選び】 the DA3 clips' seat (comparison in the same player); Unity z < 0 = mirrored side, lateral 35 m
EYE = 1.5                            # 【選び】 as f3d_export
FOOT = (4.0, 1.5)                    # 【選び】 as f3d_export (heave = hf mean over x +-4 m, lateral +-1.5 m)
L_LOOP_DEFAULT = 288                 # 12 s; a run uses one wave period T of its cfg (dir.T / sf.T): 288 for T 12 s, 240 for T 10 s
BOX_X, BOX_Y = (190.0, 335.0), (0.0, 95.0)   # 【選び】 = FLIP50 r4 box (break target 240 +- 25 m .. P1 limit 330 m + touchdown), interior y


def run_dir(name):
    if "/" in name or "\\" in name:
        return name.replace("\\", "/").rstrip("/")
    for sub in ("runs", "smoke"):
        p = B50 + "/" + sub + "/" + name
        if os.path.isdir(p):
            return p
    raise SystemExit("run folder %s not found under %s/runs" % (name, B50))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def head(b):
    magic, ver, hb, t, fr, nv, nt = struct.unpack_from("<8sIIdiII", b, 0)
    if magic != b"GW45SRF1":
        raise ValueError("not GW45SRF1")
    return dict(t=t, frame=fr, nv=nv, nt=nt, still_offset=struct.unpack_from("<f", b, 60)[0])


class Run:
    def __init__(self, name):
        self.rd = run_dir(name)
        self.id = os.path.basename(self.rd)
        self.cfg = json.load(open(self.rd + "/cfg.json", encoding="utf8"))
        self.groove = bool((self.cfg.get("bed") or {}).get("groove"))
        if self.groove:
            import g50g_common as GG          # in-memory bed patch only (the DG1 tools' own rule); no file is edited
            GG.patch_modules()
        self.spec = GC50.bed_spec(self.cfg)
        P = self.cfg["parms"]
        self.Lx, self.W = float(P["Lx"]), float(P["W"])
        self.crop_y = float(P.get("crop_z1", self.W))
        self.surf = C.surf_frames(self.rd)
        bfp = self.rd + "/pana/best_frames.json"
        self.bf = json.load(open(bfp, encoding="utf8")) if os.path.exists(bfp) else None
        self._hf = None
        self._cache = {}

    @property
    def hf(self):
        if self._hf is None:
            self._hf = C.Rec("hf", self.rd)
        return self._hf

    def records(self, f_lo, f_hi):
        fr = [f for f in self.surf if f_lo <= f <= f_hi]
        if len(fr) < 2:
            raise SystemExit("fewer than 2 surface records in frames %d-%d of %s" % (f_lo, f_hi, self.rd))
        d = np.diff(fr)
        if not np.all(d == d[0]):
            gaps = [(int(a), int(b)) for a, b in zip(fr[:-1], fr[1:]) if b - a != d[0]][:10]
            raise SystemExit("records are not evenly spaced (step %d; gaps %s): pick a range without gaps" % (d[0], gaps))
        return fr, int(d[0])

    def breakers(self, rec):
        """judged breakers of the run (best_frames per_breaker) with the print frame snapped to the nearest record frame (ties: earlier)."""
        out = []
        rs = np.array(rec)
        for b in (self.bf or {}).get("per_breaker", []):
            w0, w1 = [int(v) for v in b["window_frames"]]
            if not (rec[0] <= b["frame"] <= rec[-1]):
                continue
            i = int(np.argmin(np.abs(rs - b["frame"]) * 2 + (rs > b["frame"])))      # nearest, ties to the earlier record
            ru = b.get("ruler") or {}
            out.append(dict(k=int(b["k"]), frame=int(rs[i]), t=C.t_of(int(rs[i])), score3=float(b["score3"]), win_first=w0, win_last=w1,
                            hood=float(ru.get("hood") or 0.0), lip=float(ru.get("lip") or 0.0), frame_bestframes=int(b["frame"]),
                            t_bestframes=float(b["t"]), record_offset_frames=int(rs[i]) - int(b["frame"]), xc_bestframes=float(b.get("x_c") or b.get("xc") or 0.0),
                            eta_c_bestframes=float(b.get("eta_c") or 0.0)))
        return out

    def bed(self, half):
        bx = np.arange(0.0, self.Lx + 1e-9, 1.0)
        bz = np.arange(-half, half + 1e-9, 1.0)
        X, Z = np.meshgrid(bx, bz)
        B = np.asarray(GC50.bed_z(X, np.abs(Z), **self.spec), dtype=np.float32)
        return bx, bz, B

    def heave(self, f_from, n, seat):
        xs, zs = C.axes_hf(self.hf.meta)
        ix = (xs >= seat[0] - FOOT[0]) & (xs <= seat[0] + FOOT[0])
        iz = (zs >= abs(seat[1]) - FOOT[1]) & (zs <= abs(seat[1]) + FOOT[1])
        miss = [f for f in range(f_from, f_from + n) if f not in self.hf.where]
        if miss:
            raise SystemExit("hf misses %d frames (first %s)" % (len(miss), miss[:5]))
        return np.array([float(np.nanmean(self.hf.get(f)[iz][:, ix])) for f in range(f_from, f_from + n)])

    # ---- seam metrics (loop) ----
    def box_pts(self, f):
        if f in self._cache:
            return self._cache[f]
        if len(self._cache) > 24:
            self._cache.pop(next(iter(self._cache)))
        d = C.read_surf(f, self.rd)
        P, T = d["P"], d["tri"]
        inb = (P[:, 0] >= BOX_X[0]) & (P[:, 0] <= BOX_X[1]) & (P[:, 2] >= BOX_Y[0]) & (P[:, 2] <= BOX_Y[1])
        tk = inb[T].all(axis=1)
        cen = P[T[tk]].mean(axis=1)
        from scipy.spatial import cKDTree
        v = P[inb].astype(np.float64)
        dense = np.vstack([v, cen])
        self._cache[f] = (v, cKDTree(dense))
        return self._cache[f]

    def mesh_nn(self, f, g):
        va, ta = self.box_pts(f)
        vb, tb = self.box_pts(g)
        da, _ = tb.query(va)
        db, _ = ta.query(vb)
        d = np.concatenate([da, db])
        return dict(median=float(np.median(d)), p95=float(np.percentile(d, 95)), max=float(d.max()), n=int(len(d)))

    def eta_rms(self, f, g):
        xs, zs = C.axes_hf(self.hf.meta)
        m = ((xs >= BOX_X[0]) & (xs <= BOX_X[1]))[None, :] & ((zs >= BOX_Y[0]) & (zs <= BOX_Y[1]))[:, None]
        d = (self.hf.get(g) - self.hf.get(f))[m]
        d = d[np.isfinite(d)]
        return float(np.sqrt(np.mean(d * d))) if len(d) else float("nan")


def common_manifest(R, rec, step, seat, eye, half, out, bp, bx, bz, heave):
    still = head(open(C.surf_path(rec[0], R.rd), "rb").read())["still_offset"]
    f50 = "/FLIP50/" in R.rd
    hw = (("面の記録は横 0〜%.1f m（cfg の crop_z1 = %.0f m まで。%.0f〜%.0f m は横の帯＝向きのある海を入れる緩和の帯で、記録しない）。"
           "tank_half_width は %.0f m にした【選び】。並べる（-f3dtiles 1 以上）と %.0f m を壁として写すことになるが、そこは壁ではないので、"
           "FLIP50 のクリップは -f3dtiles 0 で見る（外は計算にない平らな海）" % (R.crop_y + 2.5, R.crop_y, R.crop_y, R.W, half, half)) if f50 else
          ("面の記録は横 0〜%.0f m（y = %.0f m は壁。壁で写して並べてよい：-f3dtiles 1 は DA3 のクリップと同じ）" % (R.W, R.W)))
    un = ("プレイヤーの原画の視点（printPos 284,4,−45 → 279,5.5,0）と座席の向き（274,3,0）は DA3 の頂 x 278.5 m に合わせた場面の値のまま"
          "（manifest からは読まない）。FLIP50 の頂は x 約 266〜272 m なので、原画の視点では頂が左へ約 7〜13 m ずれて映る。画面の字も DA3 と書く"
          "（-f3dnolabel で消す）。直すのは Unity の作業を始めてよい時（場面の値を manifest の print_crest_x からずらす小さな変更）") if f50 else          "DA3 の記録。視点は前のクリップと同じ場面の値"
    return dict(
        record_fps=FPS / step, sim_fps=FPS, record_step_frames=step, still_offset_m=float(still),
        bed_file="bed.f32", bed_nx=len(bx), bed_nz=len(bz), bed_x0=float(bx[0]), bed_z0=float(bz[0]), bed_dx=1.0, bed_sha256=sha(bp),
        bed_formula=(R.cfg.get("bed") or {}).get("formula"), bed_groove=(R.cfg.get("bed") or {}).get("groove"),
        tank_x0=0.0, tank_x1=R.Lx, tank_half_width=half, sim_half_width=R.W, surface_crop_y=R.crop_y,
        seat_x=seat[0], seat_z=seat[1], seat_eye_m=eye, seat_foot_x=FOOT[0], seat_foot_z=FOOT[1],
        heave_fps=FPS, heave=[round(float(v), 4) for v in heave], heave_min_m=float(np.min(heave)), heave_max_m=float(np.max(heave)),
        heave_source=R.rd.replace(REPO + "/", "") + " hf",
        source_run=R.rd.replace(REPO + "/", ""), run_id=R.id,
        coords_ja="計画の座標（x 前・上・横）をそのまま Unity の x・y・z に置く。横を −z に写した物をもう一度描く（計算の対称の面 y = 0 の仮定）",
        half_width_ja=hw, unity_notes_ja=un,
        created=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50g2/f3d50_export.py")


def write_bed(R, out, half):
    bx, bz, B = R.bed(half)
    bp = out + "/bed.f32"
    B.tofile(bp)
    return bx, bz, bp


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def main_long(a):
    t0 = time.time()
    R = Run(opt(a, "--run"))
    fs, ts = float(opt(a, "--from-s", "0")), float(opt(a, "--to-s", "1e9"))
    rec, step = R.records(int(round(fs * FPS)) + 1, int(round(ts * FPS)) + 1)
    seat = tuple(float(v) for v in opt(a, "--seat", "%g,%g" % SEAT).split(","))
    eye = float(opt(a, "--eye", EYE))
    half = float(opt(a, "--half-width", R.crop_y))
    short = R.id.split("_")[0]
    name = opt(a, "--name", "clip_%s_f%d_%d_r%d" % (short, rec[0], rec[-1], round(FPS / step)))
    out = OUT + "/" + name
    play = opt(a, "--play", "%g,%g" % (C.t_of(rec[0]), C.t_of(rec[-1]) + step / FPS))
    p0, p1 = [float(v) for v in play.split(",")]
    brk = R.breakers(rec)
    bin_ = [b for b in brk if p0 <= b["t"] < p1]
    pk = opt(a, "--print-k")
    pb = [b for b in bin_ if b["k"] == int(pk)] if pk else sorted(bin_, key=lambda b: (b["score3"], b["k"]))[:1]
    plan = dict(run=R.rd, records=len(rec), step=step, record_fps=FPS / step, frames=[rec[0], rec[-1]], t=[C.t_of(rec[0]), C.t_of(rec[-1])],
                play=[p0, p1], breakers=[(b["k"], b["frame"], b["frame_bestframes"], round(b["score3"], 3)) for b in brk],
                print_k=pb[0]["k"] if pb else None, out=out, groove=R.groove, half_width=half, seat=seat)
    if "--dry" in a:
        print(json.dumps(plan, ensure_ascii=False, indent=1)); return
    os.makedirs(out, exist_ok=True)
    info, bad = {}, []
    for f in rec:
        b = open(C.surf_path(f, R.rd), "rb").read()
        h = head(b)
        if h["frame"] != f or abs(h["t"] - C.t_of(f)) > 1e-6:
            bad.append(dict(frame=f, head_frame=h["frame"], head_t=h["t"]))
        info[f] = dict(bytes=len(b), sha=hashlib.sha256(b).hexdigest(), **h)
    if bad:
        raise SystemExit("record head frame/time differs from the file name: %s" % bad[:5])
    chk = [C.E45.check_frame(C.surf_path(f, R.rd))[0] for f in rec[::48]]
    bx, bz, bp = write_bed(R, out, half)
    n_hv = len(rec) * step + 1                     # 24 Hz to one record step past the last record, cut at the last hf frame
    while n_hv > 2 and (rec[0] + n_hv - 1) not in R.hf.where:
        n_hv -= 1
    heave = R.heave(rec[0], n_hv, seat)
    pr = dict(breaker_k=0, print_record_frame=0, print_record_t=0.0, print_record_index=0, print_bestframes_frame=0, print_bestframes_t=0.0,
              print_score3=0.0, print_crest_x=0.0, print_crest_eta=0.0)
    if pb:
        b = pb[0]
        e = R.hf.get(b["frame"])
        xs, _ = C.axes_hf(R.hf.meta)
        i = int(np.nanargmax(e[0]))
        pr = dict(breaker_k=b["k"], print_record_frame=b["frame"], print_record_t=C.t_of(b["frame"]), print_record_index=rec.index(b["frame"]),
                  print_bestframes_frame=b["frame_bestframes"], print_bestframes_t=b["t_bestframes"], print_score3=b["score3"],
                  print_crest_x=float(xs[i]), print_crest_eta=float(e[0, i]))
    sd = R.rd + "/surf"
    n = len(rec)
    man = dict(format="GW45LIST1", version=1, clip_kind="continuous", clip_file="", clip_bytes=int(sum(info[f]["bytes"] for f in rec)), clip_sha256="",
               frames=n, t_first=info[rec[0]]["t"], t_last=info[rec[-1]]["t"], frame_first=rec[0], frame_last=rec[-1],
               loop_seconds=n * step / FPS, loop_start_s=info[rec[0]]["t"], loop_end_s=info[rec[0]]["t"] + n * step / FPS, play_from_s=p0, play_to_s=p1,
               vert_max=int(max(info[f]["nv"] for f in rec)), tri_max=int(max(info[f]["nt"] for f in rec)),
               vert_min=int(min(info[f]["nv"] for f in rec)), tri_min=int(min(info[f]["nt"] for f in rec)),
               source_frames=rec, source_bytes=[info[f]["bytes"] for f in rec], source_sha256=[info[f]["sha"] for f in rec],
               source_list_sha256=hashlib.sha256("".join(info[f]["sha"] for f in rec).encode("ascii")).hexdigest(),
               stream_dir=sd, stream_dir_rel=os.path.relpath(sd, out).replace("\\", "/"), stream_pattern="s_{0:D5}.gw45s", repeat=1,
               breakers=bin_, breakers_source=R.rd.replace(REPO + "/", "") + "/pana/best_frames.json（この計算の判定 score3。記録が 3 コマおきの時は最も近い記録のコマに寄せた：frame_bestframes と record_offset_frames）",
               **pr)
    man.update(common_manifest(R, rec, step, seat, eye, half, out, bp, bx, bz, heave))
    man["playback_ja"] = ("面の記録は %g 個/s（計算の %s）。Unity は記録の範囲を続けて 1 回（繰り返さない・継ぎ目なし）、実時間の時計で、その時刻以前の最後の記録を見せる。"
                          "コマの間の形は作らない。記録のファイルをそのまま続けて読む（GW45LIST1）" % (FPS / step, "毎コマ" if step == 1 else "%d コマおき" % step))
    json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    ck = dict(records=n, step=step, head_frame_and_t_match_name=True, frames_check_every_48=chk, bytes_total=man["clip_bytes"], breakers_all=brk,
              breakers_in_play=[(b["k"], b["frame"]) for b in bin_], print=pr, play=[p0, p1], heave=dict(min=man["heave_min_m"], max=man["heave_max_m"], n=len(heave)),
              groove=R.groove, seconds=round(time.time() - t0, 1), tags="records 【測定】; snapping, heave, bed 【計算】; seat, half width 【選び】")
    json.dump(ck, open(out + "/check.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(out=out, records=n, record_fps=FPS / step, t=[man["t_first"], man["t_last"]], play=[p0, p1], bytes=man["clip_bytes"],
                          vert_max=man["vert_max"], tri_max=man["tri_max"], print=pr, breakers=[(b["k"], b["frame"], b["frame_bestframes"]) for b in bin_],
                          heave=[man["heave_min_m"], man["heave_max_m"]], seconds=ck["seconds"]), ensure_ascii=False, indent=1))


def main_loop(a):
    t0 = time.time()
    R = Run(opt(a, "--run"))
    rec, step = R.records(1, 10 ** 7)
    rs = set(rec)
    seat = tuple(float(v) for v in opt(a, "--seat", "%g,%g" % SEAT).split(","))
    eye = float(opt(a, "--eye", EYE))
    half = float(opt(a, "--half-width", R.crop_y))
    brk = R.breakers(rec)
    T = float((R.cfg.get("dir") or R.cfg.get("sf") or {}).get("T", 12.0))
    L_LOOP = int(round(T * FPS))
    kk = opt(a, "--k")
    rows, cand = [], []
    for b in brk:
        if kk and b["k"] != int(kk):
            continue
        taus = [f for f in rec if f <= b["win_first"] and f + L_LOOP - 1 >= b["win_last"] and (f + L_LOOP) in rs]
        if not taus:
            continue
        rr = []
        for f in taus:
            m = R.mesh_nn(f + L_LOOP, f)
            rr.append(dict(k=b["k"], tau_frame=f, tau_s=C.t_of(f), seam_nn=m, seam_eta_rms=R.eta_rms(f, f + L_LOOP)))
        rows += rr
        best = min(rr, key=lambda r: r["seam_nn"]["p95"])
        cand.append(dict(b, n_tau=len(rr), tau_range=[rr[0]["tau_frame"], rr[-1]["tau_frame"]], best=best))
        print("k%d: %d tau, best tau %d (%.3f s) seam p95 %.3f m, eta rms %.3f m (%.0f s)" % (b["k"], len(rr), best["tau_frame"], best["tau_s"],
              best["seam_nn"]["p95"], best["seam_eta_rms"], time.time() - t0), flush=True)
    if not cand:
        raise SystemExit("no breaker whose onset .. touchdown + 0.5 s fits a one-period window with a record one period later")
    p95min = min(c["best"]["seam_nn"]["p95"] for c in cand)
    near = [c for c in cand if c["best"]["seam_nn"]["p95"] <= 1.05 * p95min]
    ch = min(near, key=lambda c: (c["score3"], c["best"]["seam_nn"]["p95"]))
    tau = ch["best"]["tau_frame"]
    win = list(range(tau, tau + L_LOOP, step))
    steps = [R.mesh_nn(win[i + 1], win[i])["p95"] for i in range(0, len(win) - 1, 2)]
    steps_eta = [R.eta_rms(win[i], win[i + 1]) for i in range(0, len(win) - 1, 2)]
    jump = R.mesh_nn(win[0], win[-1])          # what the viewer sees at the seam: last record -> first record
    short = R.id.split("_")[0]
    name = opt(a, "--name", "clip_%s_k%d_r%d" % (short, ch["k"], round(FPS / step)))
    out = OUT + "/" + name
    res = dict(run=R.rd, T_s=T, rule=__doc__.split("Loop window rule")[1].split("Tags:")[0].strip(), L_frames=L_LOOP, record_step_frames=step,
               candidates=[dict((k_, v) for k_, v in c.items() if k_ != "best") | dict(best=c["best"]) for c in cand],
               chosen=dict(k=ch["k"], tau_frame=tau, tau_s=C.t_of(tau), end_frame=tau + L_LOOP, n_records=len(win), print_record_frame=ch["frame"],
                           print_frame_bestframes=ch["frame_bestframes"], score3=ch["score3"], seam_nn=ch["best"]["seam_nn"], seam_eta_rms=ch["best"]["seam_eta_rms"],
                           jump_nn=jump, jump_eta_rms=R.eta_rms(win[-1], win[0]),
                           step_nn_p95_median=float(np.median(steps)), step_nn_p95_max=float(np.max(steps)), step_eta_rms_median=float(np.median(steps_eta))),
               seam_rows=rows, seconds=round(time.time() - t0, 1), tags="seam numbers 【測定】 (records) / 【計算】; box and rule 【選び】")
    if "--dry" in a:
        print(json.dumps(res["chosen"], ensure_ascii=False, indent=1)); return
    os.makedirs(out, exist_ok=True)
    blobs = [open(C.surf_path(f, R.rd), "rb").read() for f in win]
    heads = [head(b) for b in blobs]
    n = len(blobs)
    fps = FPS / step
    hd = struct.pack("<8sIIddi", b"GW45CLP1", 1, n, fps, heads[0]["t"], heads[0]["frame"])
    hd += b"\0" * (64 - len(hd))
    pos = 64 + n * 16
    idx = b""
    for b in blobs:
        idx += struct.pack("<QII", pos, len(b), 0)
        pos += len(b)
    cp = out + "/clip.gw45c"
    with open(cp, "wb") as fh:
        fh.write(hd); fh.write(idx)
        for b in blobs:
            fh.write(b)
    data = open(cp, "rb").read()
    ok = all(data[struct.unpack_from("<QII", data, 64 + 16 * i)[0]:][:len(b)] == b for i, b in enumerate(blobs))
    del data
    bx, bz, bp = write_bed(R, out, half)
    heave = R.heave(tau, L_LOOP + 1, seat)
    e = R.hf.get(ch["frame"])
    xs, _ = C.axes_hf(R.hf.meta)
    i = int(np.nanargmax(e[0]))
    c4 = res["chosen"]
    man = dict(format="GW45CLP1", version=1, clip_kind="loop", clip_file="clip.gw45c", clip_bytes=os.path.getsize(cp), clip_sha256=sha(cp),
               frames=n, t_first=heads[0]["t"], t_last=heads[-1]["t"], frame_first=heads[0]["frame"], frame_last=heads[-1]["frame"],
               loop_seconds=L_LOOP / FPS, loop_start_s=C.t_of(tau), loop_end_s=C.t_of(tau + L_LOOP),
               vert_max=int(max(h["nv"] for h in heads)), tri_max=int(max(h["nt"] for h in heads)), vert_min=int(min(h["nv"] for h in heads)), tri_min=int(min(h["nt"] for h in heads)),
               source_frames=win, source_sha256=[hashlib.sha256(b).hexdigest() for b in blobs],
               breaker_k=ch["k"], print_record_frame=ch["frame"], print_record_t=C.t_of(ch["frame"]), print_record_index=win.index(ch["frame"]),
               print_bestframes_frame=ch["frame_bestframes"], print_bestframes_t=ch["t_bestframes"], print_score3=ch["score3"],
               print_crest_x=float(xs[i]), print_crest_eta=float(e[0, i]),
               seam_mesh_median_m=c4["seam_nn"]["median"], seam_mesh_p95_m=c4["seam_nn"]["p95"], seam_mesh_max_m=c4["seam_nn"]["max"],
               seam_eta_rms_break_m=c4["seam_eta_rms"], step_mesh_p95_median_m=c4["step_nn_p95_median"],
               jump_nn_median_m=c4["jump_nn"]["median"], jump_nn_p95_m=c4["jump_nn"]["p95"], jump_nn_max_m=c4["jump_nn"]["max"], jump_eta_rms_break_m=c4["jump_eta_rms"],
               heave_seam_jump_m=float(heave[L_LOOP] - heave[0]), seam_metric_ja="面どうしの最も近い点の距離（点と三角形の重心、x 190〜335 m・横 0〜95 m）")
    man.update(common_manifest(R, win, step, seat, eye, half, out, bp, bx, bz, heave))
    man["playback_ja"] = ("面の記録は %g 個/s。1 周期の窓 %.3f〜%.3f s を繰り返す（継ぎ目がある：τ と τ + 1 周期の違い p95 %.2f m、ふつうの 1 歩の p95 の中央値 %.2f m）。"
                          "コマの間の形は作らない" % (fps, C.t_of(tau), C.t_of(tau + L_LOOP), c4["seam_nn"]["p95"], c4["step_nn_p95_median"]))
    json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(res, open(out + "/loop_ana.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    json.dump(dict(clip_roundtrip_bytes_equal=bool(ok), frames=[C.E45.check_frame(C.surf_path(f, R.rd))[0] for f in win[::24]], seconds=round(time.time() - t0, 1)),
              open(out + "/check.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(out=out, chosen=c4, roundtrip=ok, heave=[man["heave_min_m"], man["heave_max_m"]], heave_seam=man["heave_seam_jump_m"],
                          seconds=round(time.time() - t0, 1)), ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] not in ("long", "loop") or "--run" not in a:
        print(__doc__); sys.exit(1)
    (main_long if a[0] == "long" else main_loop)(a[1:])
