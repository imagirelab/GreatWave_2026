# -*- coding: utf-8 -*-
"""FLIP50 re-record clips that carry the SOURCE run's judged breakers (py -3.10 -B, numpy + scipy). 2026-10-17 written new (Claude).

Why: a re-record (g50g2_cont.py rr, e.g. DM1Ar_..._c1728_t86p25) recomputes a window of a judged run from its checkpoint with the same
physics and writes the surface every frame, but it has no pana/ (it is not judged). f3d50_export.py reads pana/best_frames.json of the
run it exports, so the re-record gave 'long' clips with breakers [] / print k 0, and 'loop' found no breaker. This wrapper runs the
UNCHANGED f3d50_export.py functions with one difference: the judged breakers (best_frames.json) are read from the SOURCE run.
That is allowed only because the re-record is bit-identical to the source on every common record (restart_compare.json
all_bit_identical True: hf / r2 / r3 every frame, r4 / r5 on the common every-3rd frames, volcorr), so the source's judgement of
frames f is a judgement of the same water at frames f. The wrapper refuses otherwise. Frame numbers are the same in both runs.
No file of flip3d, flip50, flip50g or flip50g2 is edited; run folders are read only; writes only Unity/Build/FLIP3D/<name>/.

  long  py -3.10 -B f3d50_export_src.py long --run DM1Ar_D19B_T12_th80_dp0p5_c1728_t86p25 [--name N] [--cams <cameras json>] [f3d50_export.py long options]
  loop  py -3.10 -B f3d50_export_src.py loop --run DM1Ar_D19B_T12_th80_dp0p5_c1728_t86p25 [--tau F | --tau rule] [--k K] [--name N] [--cams <cameras json>]
        --tau: default = the re-record cfg case.loop_tau_frame (the tau the re-record was launched for; 1759 for DM1Ar, chosen by
        f3d50_export.py loop on the source's every-3rd records). 'rule' = let f3d50_export.py's seam rule choose on the every-frame records.
        Either way the rule's own free choice on the every-frame records is computed too and written to loop_ana.json (rule_free_every_frame).
  both: --src <source run> (default cfg restart.src_run), --cams <cameras json> (cam50_choose.py output: seat x/z/eye for the heave and
        the seat look / print pose written as manifest cam_* fields; the FLIP3D player uses them when present).

Manifest additions (only these; everything else is f3d50_export.py's): breakers_source (the source file), pana_source_{run,file,sha256},
restart_compare_{file,sha256,verdict}, wrapper, wrapper_args, unity_notes_ja (rewritten when cam_* are written), and with --cams:
cam_seat_look_at, cam_seat_fov_v, cam_print_pos, cam_print_look_at, cam_print_fov_v, cam_source_{file,sha256,run}, cam_note_ja.
Loop: loop_tau_source, loop_tau_rule_free_every_frame, breakers (the judged breakers inside the window, same form as the long clip's).
Tags: 【測定】 records / restart compare, 【計算】 numbers derived here, 【選び】 tau default, camera values (from the cameras JSON).
"""
import os, sys, json, io, inspect, contextlib, hashlib, time

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip50g2")
import f3d50_export as E          # noqa: E402  unchanged (its own imports: f3d_common, g50_common read only)

TOOL = "Tools/GWWaveGen/flip50g2/f3d50_export_src.py"
TAU_LINE = '        taus = [f for f in rec if f <= b["win_first"] and f + L_LOOP - 1 >= b["win_last"] and (f + L_LOOP) in rs]\n'
TAU_NEW = ('        taus = [f for f in rec if f <= b["win_first"] and f + L_LOOP - 1 >= b["win_last"] and (f + L_LOOP) in rs'
           ' and (FORCE_TAU is None or f == FORCE_TAU)]\n')


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def drop(a, k, n=2):
    if k in a:
        i = a.index(k)
        del a[i:i + n]


def source_pana(rr_dir, src_name=None):
    """the source run's best_frames.json, after checking the re-record is bit-identical to it (refuses otherwise)."""
    cfg = json.load(open(rr_dir + "/cfg.json", encoding="utf8"))
    rs = cfg.get("restart") or {}
    src = E.run_dir(src_name or rs.get("src_run") or "")
    rcp = rr_dir + "/restart_compare.json"
    if not os.path.exists(rcp):
        raise SystemExit("no restart_compare.json in %s: cannot borrow the source's judgement" % rr_dir)
    rc = json.load(open(rcp, encoding="utf8"))
    norm = lambda p: os.path.normcase(os.path.abspath(p))
    bad = []
    if rc.get("all_bit_identical") is not True:
        bad.append("all_bit_identical is not True")
    if norm(rc.get("src", "")) != norm(src):
        bad.append("restart_compare src %s != source %s" % (rc.get("src"), src))
    if norm(rc.get("dst", "")) != norm(rr_dir):
        bad.append("restart_compare dst %s != re-record %s" % (rc.get("dst"), rr_dir))
    r5 = rc.get("r5") or {}
    if not r5.get("n_common") or r5.get("n_bytes_equal") != r5.get("n_common"):
        bad.append("surface records r5 not all byte-equal (%s/%s)" % (r5.get("n_bytes_equal"), r5.get("n_common")))
    hf = ((rc.get("hf") or {}).get("eta") or {})
    if not hf.get("n_frames") or hf.get("n_bit_equal") != hf.get("n_frames"):
        bad.append("hf not all bit-equal")
    if rs.get("src_run") and os.path.basename(src) != rs.get("src_run"):
        bad.append("cfg restart.src_run %s != source %s" % (rs.get("src_run"), os.path.basename(src)))
    bfp = src + "/pana/best_frames.json"
    if not os.path.exists(bfp):
        bad.append("source has no pana/best_frames.json")
    if bad:
        raise SystemExit("refused (source judgement not borrowable): " + "; ".join(bad))
    bf = json.load(open(bfp, encoding="utf8"))
    verdict = dict(all_bit_identical=True, time=rc.get("time"), tool=rc.get("tool"), src=rel(rc["src"]), dst=rel(rc["dst"]), frames=rc.get("frames"),
                   restart_ckpt=rc.get("restart_ckpt"), r5_bytes_equal=[r5.get("n_bytes_equal"), r5.get("n_common")],
                   hf_bit_equal=[hf.get("n_bit_equal"), hf.get("n_frames")],
                   r2_bit_equal=[((rc.get("r2") or {}).get("sdf") or {}).get("n_bit_equal"), ((rc.get("r2") or {}).get("sdf") or {}).get("n_frames")],
                   r3_bit_equal=[((rc.get("r3") or {}).get("sdf") or {}).get("n_bit_equal"), ((rc.get("r3") or {}).get("sdf") or {}).get("n_frames")],
                   r4_bit_equal=[((rc.get("r4") or {}).get("sdf") or {}).get("n_bit_equal"), ((rc.get("r4") or {}).get("sdf") or {}).get("n_frames")],
                   volcorr_equal=[(rc.get("volcorr") or {}).get("n_equal"), (rc.get("volcorr") or {}).get("n_common")])
    prov = dict(pana_source_run=os.path.basename(src), pana_source_file=rel(bfp), pana_source_sha256=E.sha(bfp),
                restart_compare_file=rel(rcp), restart_compare_sha256=E.sha(rcp), restart_compare_verdict=verdict)
    return cfg, src, bf, prov


def install(bf):
    """f3d50_export.Run with the source's best_frames (the only change)."""
    class RunSrc(E.Run):
        def __init__(self, name):
            super().__init__(name)
            if self.bf is not None:
                raise SystemExit("the re-record has its own pana/best_frames.json: use f3d50_export.py directly")
            self.bf = bf
    E.Run = RunSrc
    return RunSrc


def cams_fields(path, src):
    cj = json.load(open(path, encoding="utf8"))
    if cj.get("run_id") != os.path.basename(src):
        raise SystemExit("cameras JSON is for %s, not the source %s" % (cj.get("run_id"), os.path.basename(src)))
    su, pu = cj["seat"]["unity"], cj["print"]["unity"]
    seat = (float(su["manifest"]["seat_x"]), float(su["manifest"]["seat_z"]), float(su["manifest"]["seat_eye_m"]))
    f = dict(cam_seat_look_at=[float(v) for v in su["seatLookAt"]], cam_seat_fov_v=float(su["seatFovV"]),
             cam_print_pos=[float(v) for v in pu["printPos"]], cam_print_look_at=[float(v) for v in pu["printLookAt"]], cam_print_fov_v=float(pu["printFovV"]),
             cam_source_file=rel(path), cam_source_sha256=E.sha(path), cam_source_run=cj.get("run_id"),
             cam_note_ja=("座席（seat_x・seat_z・seat_eye_m と heave）と、座席の見る点・画角・原画の視点の位置・見る点・画角は %s の値【選び】"
                          "（座席 x %.0f・横 %.0f m、原画の視点 x %.1f・高さ %.1f・横 %.0f m・縦の画角 %.1f°）。FLIP3D のプレイヤーは cam_* があればそれを使う"
                          "（2026-10-17 追記。ない前のクリップは場面の値のまま）" % (rel(path), seat[0], -seat[1], pu["printPos"][0], pu["printPos"][1], -pu["printPos"][2], pu["printFovV"])))
    return seat, f


def finish(out, prov, extra, args):
    mp = out + "/manifest.json"
    man = json.load(open(mp, encoding="utf8"))
    man["breakers_source"] = (prov["pana_source_file"] + "（元の計算 %s の判定 score3。記録し直しは元とビット単位で同じなので同じ判定を使う："
                              "%s の all_bit_identical True）" % (prov["pana_source_run"], prov["restart_compare_file"]))
    man.update(prov)
    man.update(extra)
    if "cam_print_pos" in man:
        man["unity_notes_ja"] = ("座席・原画の視点の値は manifest の cam_* を使う（プレイヤーの 2026-10-17 追記。cam_note_ja）。"
                                 "FLIP3DXR の crestAlign（print_crest_x − 278.5 m で x をずらす）は cam_* のある時も働くので、VR・体験の道では -f3dnocrestalign を付ける")
    man["wrapper"] = TOOL
    man["wrapper_args"] = args
    json.dump(man, open(mp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    cp = out + "/check.json"
    ck = json.load(open(cp, encoding="utf8"))
    ck["source_judgement"] = prov
    ck["wrapper"] = TOOL
    json.dump(ck, open(cp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return man


def patched_main_loop(force_tau):
    src = inspect.getsource(E.main_loop)
    if src.count(TAU_LINE) != 1:
        raise SystemExit("tau line not found exactly once in f3d50_export.main_loop")
    ns = dict(E.__dict__)
    ns["FORCE_TAU"] = force_tau
    exec(compile(src.replace(TAU_LINE, TAU_NEW), E.__file__ + " [main_loop, forced tau by flip50g2/f3d50_export_src.py]", "exec"), ns)
    return ns["main_loop"]


def main(a):
    t0 = time.time()
    kind = a[0]
    args = list(a)
    a = a[1:]
    rr = E.run_dir(opt(a, "--run"))
    cfg, src, bf, prov = source_pana(rr, opt(a, "--src"))
    drop(a, "--src")
    install(bf)
    extra = {}
    cams = opt(a, "--cams")
    if cams:
        seat, extra = cams_fields(cams, src)
        drop(a, "--cams")
        if "--seat" not in a:
            a += ["--seat", "%g,%g" % (seat[0], seat[1])]
        if "--eye" not in a:
            a += ["--eye", "%g" % seat[2]]
    short = os.path.basename(rr).split("_")[0]
    if kind == "long":
        if "--name" not in a:
            rec, step = E.Run(rr).records(1, 10 ** 7)
            a += ["--name", "clip_%s_f%d_%d_r%d_srcpana" % (short, rec[0], rec[-1], round(E.FPS / step))]
        name = opt(a, "--name")
        E.main_long(a)
        man = finish(E.OUT + "/" + name, prov, extra, args)
    else:
        tau_arg = opt(a, "--tau", "cfg")
        drop(a, "--tau")
        # the rule's free choice on the every-frame records (information; dry, writes nothing)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            patched_main_loop(None)(a + ["--dry"])
        txt = buf.getvalue()
        free = json.loads(txt[txt.index("{"):])
        progress = [ln for ln in txt.splitlines() if ln.startswith("k")]
        print("rule (every-frame records, free):", " | ".join(progress), flush=True)
        if tau_arg == "rule":
            tau, tsrc = None, "f3d50_export.py の継ぎ目の決まりを毎コマの記録で（自由に選ばせた）"
        else:
            tau = int(cfg["case"]["loop_tau_frame"]) if tau_arg == "cfg" else int(tau_arg)
            tsrc = (("記録し直しの cfg case.loop_tau_frame = %d（g50g2_cont.py rr --tau。元 %s の 3 コマおきの記録で f3d50_export.py loop が選んだ τ。"
                     "記録し直しの終わりはこの τ + 1 周期を含むように決めた）" % (tau, os.path.basename(src))) if tau_arg == "cfg" else "--tau %d（手で与えた）" % tau)
        name = opt(a, "--name")
        if not name:
            name = "clip_%s_k%s_r24" % (short, opt(a, "--k", "%d" % free["k"]))
            a += ["--name", name]
        patched_main_loop(tau)(a)
        out = E.OUT + "/" + name
        m0 = json.load(open(out + "/manifest.json", encoding="utf8"))
        # f3d50_export.py loop writes only the chosen breaker (breaker_k / print_*); the window's judged breakers are added in the long-clip form
        extra = dict(extra, loop_tau_source=tsrc, loop_tau_rule_free_every_frame=free["tau_frame"], breakers=E.Run(rr).breakers(m0["source_frames"]))
        man = finish(out, prov, extra, args)
        la = json.load(open(out + "/loop_ana.json", encoding="utf8"))
        la["rule_free_every_frame"] = dict(chosen=free, progress=progress)
        la["tau_used"] = dict(tau_frame=man["frame_first"], source=tsrc)
        la["source_judgement"] = prov
        json.dump(la, open(out + "/loop_ana.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    ok = bool(man.get("breakers") or man.get("breaker_k"))
    print(json.dumps(dict(out=E.OUT + "/" + name, breaker_k=man.get("breaker_k"), print_record_frame=man.get("print_record_frame"),
                          print_record_index=man.get("print_record_index"), breakers=[(b["k"], b["frame"]) for b in (man.get("breakers") or [])],
                          frames=[man["frame_first"], man["frame_last"]], records=man["frames"], seat=[man["seat_x"], man["seat_z"]],
                          cams=bool(extra.get("cam_print_pos")), pana=prov["pana_source_file"], carries_judgement=ok,
                          seconds=round(time.time() - t0, 1)), ensure_ascii=False, indent=1))
    if not ok:
        raise SystemExit("export carries no judged breaker")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] not in ("long", "loop") or "--run" not in a:
        print(__doc__); sys.exit(1)
    main(a)
