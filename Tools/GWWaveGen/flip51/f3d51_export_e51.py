# -*- coding: utf-8 -*-
"""FLIP51 (plan E) runs -> long clips for the FLIP3D Unity player, carrying the e51 period summits (py -3.10 -B, numpy + scipy).
2026-10-17 written new (Claude) for the user's question about X2 seen from the print view.

Why: flip50g2/f3d50_export.py reads the judged breakers from pana/best_frames.json of the run it exports. A FLIP51 E run has no pana/ (it is
read by x51_ana.py: e51/screen_E05.json and judge_E05.json, one summit per wave period n). This wrapper runs the UNCHANGED f3d50_export.py
'long' with one difference: the per-period summits of e51 are given to it in place of best_frames.json (Run.bf, in memory only):
  k = the e51 period n, frame = the e51 summit frame (screen_E05.json periods[].f, the scan summit = the highest centre peak of that period;
  the most converged instant is the e51 red instant n6, frame 983), t, x_c / eta_c = the summit (e51 x_pk, Hc), window_frames = the e51
  period window t_n +- 3.5 s, score3 / ruler hood, lip = the centre-section print ruler AT the summit frame from --section (x2_section.json,
  the g49 best-frame call: r2_mask -> STUDY52 measure_mask -> g47_video.score3). f3d50_export.py snaps each frame to the nearest surface
  record (every 3rd frame here; ties to the earlier record) and keeps frame_bestframes / record_offset_frames; --print-k picks the print
  record (default 6 = the red instant n6 -> record 982 for X2).
  judge_E05.json uses g50-event instants for n8 / n9 (frames 1270 / 1592 in X2) instead of the scan summits; they are written to the manifest
  (e51_judge_instants) but not used as breakers (the clip marks the summits).
  NOTE: these are wave SUMMITS of the period (focused peaks), not breakers; the player's on-screen label still says '崩れ k' for them
  (FLIP3DPlayer is not edited); breakers_source / e51_note_ja say what they are.
Camera: --cams <cameras JSON> --view print|front writes cam_print_pos / cam_print_look_at / cam_print_fov_v from that JSON's 'print' or
  'front' block (the FLIP3D player then uses them for its Print mode; cam_* support added 2026-10-17). The seat is not chosen for these
  clips (f3d50_export.py default seat 300,-35; only its heave is written).
--water-double-sided: water_double_sided true (display only, as flip50g2/f3d50_export_src.py; the records are not changed).
No file of flip3d, flip50, flip50g, flip50g2 or flip51 is edited; the run folder is read only; writes only Unity/Build/FLIP3D/<name>/.

  py -3.10 -B f3d51_export_e51.py long --run <FLIP51 run dir or id> --section <x2_section.json> --cams <cameras_X2.json> --view print|front
        [--from-s 35 --to-s 75] [--print-k 6] [--water-double-sided] [--name N] [--dry]
Tags: 【測定】 records, e51 numbers; 【計算】 record snapping, heave, ruler; 【選び】 cameras (from the cameras JSON), seat (default), half width.
"""
import os, sys, json, time

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip50g2")
import f3d50_export as E          # noqa: E402  unchanged (its own imports: f3d_common, g50_common read only)

TOOL = "Tools/GWWaveGen/flip51/f3d51_export_e51.py"
B51 = REPO + "/Unity/Build/FLIP51"


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def drop(a, k, n=2):
    if k in a:
        i = a.index(k)
        del a[i:i + n]


def run_dir51(name):
    if "/" in name or "\\" in name:
        return name.replace("\\", "/").rstrip("/")
    p = B51 + "/runs/" + name
    if not os.path.isdir(p):
        raise SystemExit("run folder %s not found under %s/runs" % (name, B51))
    return p


def e51_breakers(rd, section_path):
    scr_p, jud_p = rd + "/e51/screen_E05.json", rd + "/e51/judge_E05.json"
    scr = json.load(open(scr_p, encoding="utf8"))
    jud = json.load(open(jud_p, encoding="utf8")) if os.path.exists(jud_p) else {}
    sec = json.load(open(section_path, encoding="utf8"))
    if os.path.basename(sec.get("run", "").rstrip("/")) != os.path.basename(rd):
        raise SystemExit("section JSON is for %s, not %s" % (sec.get("run"), rd))
    secp = {int(p["n"]): p for p in sec["periods"]}
    per = []
    for p in scr["periods"]:
        if not p.get("complete") or p.get("f") is None:
            continue
        n = int(p["n"])
        s = (secp.get(n) or {}).get("at_summit") or {}
        if int(s.get("frame", -1)) != int(p["f"]) or s.get("score3") is None:
            raise SystemExit("section JSON has no ruler at the e51 summit frame of n%d (%s)" % (n, p["f"]))
        w0, w1 = int(round(float(p["window"][0]) * 24.0)) + 1, int(round(float(p["window"][1]) * 24.0)) + 1
        per.append(dict(k=n, frame=int(p["f"]), t=float(p["t"]), x_c=float(p["x_pk"]), eta_c=float(p["Hc"]), score3=float(s["score3"]),
                        ruler=dict(hood=s.get("hood"), lip=s.get("lip"), chord=s.get("chord"), foot=s.get("foot"), back=s.get("back")),
                        window_frames=[w0, w1], src="e51 screen_E05.json period summit (scan)", e51_miss=p.get("miss")))
    jud_inst = []
    for p in jud.get("periods") or []:
        u = [q for q in jud.get("instants_used", []) if int(q["n"]) == int(p["n"])]
        jud_inst.append(dict(n=int(p["n"]), frame=int(p["f"]), t=float(p["t"]), x_pk=float(p["x_pk"]), Hc=float(p["Hc"]),
                             instant=(u[0].get("instant") if u else None)))
    prov = dict(e51_screen_file=rel(scr_p), e51_screen_sha256=E.sha(scr_p), e51_judge_file=rel(jud_p) if jud else None,
                e51_judge_sha256=E.sha(jud_p) if jud else None, e51_red_instant=scr.get("red_instant"), e51_judge_red_instant=jud.get("red_instant"),
                e51_judge_valid=jud.get("valid"), e51_judge_failed_gates=jud.get("failed_gates"), e51_judge_instants=jud_inst,
                e51_section_file=rel(section_path), e51_section_sha256=E.sha(section_path))
    return dict(per_breaker=per), prov


def install(bf):
    class RunE51(E.Run):
        def __init__(self, name):
            super().__init__(name)
            if self.bf is not None:
                raise SystemExit("the run has its own pana/best_frames.json: use f3d50_export.py directly")
            self.bf = bf
    E.Run = RunE51


def cam_fields(path, view, rd):
    cj = json.load(open(path, encoding="utf8"))
    if cj.get("run_id") != os.path.basename(rd):
        raise SystemExit("cameras JSON is for %s, not %s" % (cj.get("run_id"), os.path.basename(rd)))
    v = cj[view]["unity"]
    return dict(cam_print_pos=[float(q) for q in v["printPos"]], cam_print_look_at=[float(q) for q in v["printLookAt"]], cam_print_fov_v=float(v["printFovV"]),
                cam_view=view, cam_source_file=rel(path), cam_source_sha256=E.sha(path), cam_source_run=cj.get("run_id"),
                cam_note_ja=("Print モードの視点は %s の '%s'【選び】（位置 x %.2f・高さ %.2f・横 %.0f m、見る点 (%.2f, %.2f, %.0f)、縦の画角 %.2f°）。"
                             "FLIP3D のプレイヤーは cam_* があればそれを使う。座席は選んでいない（f3d50_export.py の既定 300,−35 のまま、船の上下だけ書く）"
                             % (rel(path), view, v["printPos"][0], v["printPos"][1], -v["printPos"][2], v["printLookAt"][0], v["printLookAt"][1],
                                v["printLookAt"][2], v["printFovV"])))


def main(a):
    t0 = time.time()
    args = list(a)
    a = a[1:]
    rd = run_dir51(opt(a, "--run"))
    a[a.index("--run") + 1] = rd
    sec = opt(a, "--section"); drop(a, "--section")
    if not sec:
        raise SystemExit("--section <x2_section.json> is required (score3 at the e51 summits)")
    bf, prov = e51_breakers(rd, sec)
    install(bf)
    extra = {}
    cams, view = opt(a, "--cams"), opt(a, "--view", "print")
    drop(a, "--cams"); drop(a, "--view")
    if cams:
        extra.update(cam_fields(cams, view, rd))
    if "--water-double-sided" in a:
        drop(a, "--water-double-sided", 1)
        extra.update(water_double_sided=True, water_double_sided_ja=(
            "表示だけ（f3d50_export_src.py と同じ印）：FLIP3D のプレイヤーは水を両面で描く。面の記録の穴から見える水の裏の面を、法線を裏返して表と同じ式で塗る。"
            "記録・計算・形は変えない"))
    if "--print-k" not in a:
        a += ["--print-k", "6"]
    short = "X2" if "S51X2" in os.path.basename(rd) else os.path.basename(rd).split("_")[0]
    if "--name" not in a:
        a += ["--name", "clip_%s_f841_1801_r8_%s%s" % (short, view, "_ds" if extra.get("water_double_sided") else "")]
    name = opt(a, "--name")
    if "--dry" in a:
        E.main_long(a)
        return
    E.main_long(a)
    out = E.OUT + "/" + name
    mp = out + "/manifest.json"
    man = json.load(open(mp, encoding="utf8"))
    W, crop = man["sim_half_width"], man["surface_crop_y"]
    man.update(prov)
    man.update(extra)
    man["breakers_source"] = ("%s の周期ごとの頂（k = 周期 n。崩れではなく、その周期で真ん中に最も高く集まった頂。score3 は %s の真ん中の断面の物差しの値）。"
                              "記録は 3 コマおきなので最も近い記録のコマに寄せた（frame_bestframes と record_offset_frames）" % (prov["e51_screen_file"], prov["e51_section_file"]))
    man["e51_note_ja"] = ("この計算に pana/best_frames.json はない（FLIP51 の E は x51_ana.py の e51 で読む）。%s が e51 の周期の頂を f3d50_export.py に"
                          "best_frames の代わりに渡した（メモリの中だけ）。最も集まった瞬間は e51 の赤い瞬間 n6 のコマ 983（記録は最も近い 982）。"
                          "judge_E05.json は n8・n9 に g50 の崩れの瞬間（コマ 1270・1592）を使うが、ここでは頂（scan）を使った（e51_judge_instants に両方）" % TOOL)
    man["half_width_ja"] = ("面の記録は横 0〜%.1f m（cfg の crop_z1 = %.0f m まで。%.0f〜%.0f m は向きのある海を入れる横の帯で、記録しない）。"
                            "tank_half_width は %.0f m。そこは壁ではないので -f3dtiles 0 で見る（外は計算にない平らな海）" % (crop + 2.5, crop, crop, W, man["tank_half_width"]))
    man["unity_notes_ja"] = ("Print モードの視点は manifest の cam_*（cam_view = %s、cam_note_ja）。座席は選んでいない。FLIP3DXR の crestAlign"
                             "（print_crest_x − 278.5 m で x をずらす）は VR の道で働くので、VR では -f3dnocrestalign を付ける。プレイヤーの画面の字は頂を「崩れ k」と書く"
                             % extra.get("cam_view", "-"))
    man["wrapper"] = TOOL
    man["wrapper_args"] = args
    json.dump(man, open(mp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    cp = out + "/check.json"
    ck = json.load(open(cp, encoding="utf8"))
    ck["e51"] = prov
    ck["wrapper"] = TOOL
    json.dump(ck, open(cp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(out=out, print_record_frame=man.get("print_record_frame"), print_record_index=man.get("print_record_index"),
                          breakers=[(b["k"], b["frame"], b["frame_bestframes"]) for b in man.get("breakers") or []], frames=[man["frame_first"], man["frame_last"]],
                          records=man["frames"], view=extra.get("cam_view"), cam=[extra.get("cam_print_pos"), extra.get("cam_print_look_at"), extra.get("cam_print_fov_v")],
                          double_sided=bool(extra.get("water_double_sided")), seconds=round(time.time() - t0, 1)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] != "long" or "--run" not in a:
        print(__doc__); sys.exit(1)
    main(a)
