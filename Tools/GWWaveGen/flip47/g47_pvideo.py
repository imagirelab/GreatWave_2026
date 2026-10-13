# -*- coding: utf-8 -*-
"""FLIP47：周期の波の計算の動画（py -3.10 -B）。2026-10-13 周期の波の実験の役（Claude）が書いた。g47_video.py（動画の役）を読み込んで使い、
変えない。足すのは「全部の時間を通して、左下の拡大の窓が崩れる波を次々に追う」動画だけ（g47_video の run は 1 つの崩れ k だけを追う）。
  1 コマごとに「いま追う崩れ」を決める：着水の follow_post s 後（既定 1.0 s）までは k 番目、その後は k + 1 番目（窓は次の波の頂へ飛ぶ）。
  拡大の窓・右下の重ね・数の表・原画の輪郭・時刻の帯の印は、その時に追う崩れの物（g47_video の RunVideo の描き方そのまま）。
  崩れの見つけ方・原画に最も近いコマ（score3 の最小）・測り方は g47_video.Run と同じ。
使い方：
  py -3.10 -B g47_pvideo.py all <run_id か置き場所> [--t0=<s>] [--t1=<s>] [--speed=4] [--name=..] [--label=..] [--follow_post=1.0] [--hold=0]
     → Unity/Build/FLIP47/videos/<name>.mp4 と .json（既定の名前 <run_id>_all_x<speed>）。
     既定は記録の全部を 4 倍の速さ（スローと止めなし）。--speed=1 --slow=0.25 で崩れごとに 0.25 倍のスロー、--hold=1 で各崩れの最も近いコマで 1 s 止める。
     追うのは来た波の崩れ（g47_periodic_ana.find_events の選び方）だけ。時刻の帯の印「k」は来た波の順（g47_video の k とは違う）。
  py -3.10 -B g47_pvideo.py montage <run> 5,6,7,8,9,10 [--slow=0.25 ...]   来た波の崩れ k を 2×3 に並べる（着水にそろえる。g47_video の Montage）
  py -3.10 -B g47_pvideo.py clip <run> <k> [--pre=6 --post=3 --name=..]   来た波の崩れ k の短い動画（0.25 倍のスロー、原画に最も近いコマで止める）
"""
import os, sys, json, math, time
sys.dont_write_bytecode = True
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g47_video as GV          # noqa: E402
import g47_common as GCM        # noqa: E402


class AllRunVideo(GV.RunVideo):
    def __init__(self, run, opt):
        self.r = run
        self.opt = opt
        evs = run.events()
        self.evs = evs
        self.slow = float(opt.get("slow", 1.0))
        self.speed = float(opt.get("speed", 4.0))
        self.hold_s = float(opt.get("hold", 0.0))
        self.post = float(opt.get("overturn_post", 0.5))
        self.follow_post = float(opt.get("follow_post", 1.0))
        t_first, t_last = run.tf[run.frames[0]], run.tf[run.frames[-1]]
        t0 = float(opt.get("t0", t_first)); t1 = float(opt.get("t1", t_last))
        self.fr = [f for f in run.frames if t0 - 1e-9 <= run.tf[f] <= t1 + 1e-9]
        self.ta, self.tb = run.tf[self.fr[0]], run.tf[self.fr[-1]]
        # 崩れごとの窓の位置と測り（窓の中の崩れだけ）
        self.cams = {}
        # 来た波の崩れ（g47_periodic_ana.find_events と同じ選び方）だけを追う。浅い所の巻き直しは追わない
        prim_k = set(primary_kall(run.rd, float(opt.get("primary_x", 570.0))))
        use = [e for e in evs if e["k"] in prim_k and e.get("td_t", e["on_t"] + 2.0) + self.follow_post >= self.ta and e["on_t"] - 8.0 <= self.tb]
        self.secondary = [e for e in evs if e["k"] not in prim_k]
        for e in use:
            self.cams[e["k"]] = dict(run.make_camera(e))
            run.prep(e, pre=1.0, post=self.post)
        self.use = use
        allp = [e for e in evs if e["k"] in prim_k]
        self.kp = {id(e): i + 1 for i, e in enumerate(allp)}
        if not use:                      # 崩れがない計算（煙の試し）：いちばん高い山の筋を追う（g47_video と同じ）
            if not run.tracks:           # 山もない（静かな水）：拡大の窓を --zoom_x（既定 上流の壁 + 40 m）に止める
                xz = float(opt.get("zoom_x", run.x_range()[0] + 40.0))
                run.tracks = [dict(id=0, f=list(run.frames), t=[run.tf[f] for f in run.frames], x=[xz] * len(run.frames),
                                   eta=[1.0] * len(run.frames), th=[None] * len(run.frames))]
            run.make_camera(None)
        # 1 コマごとに追う崩れ
        self.active = {}
        for f in self.fr:
            t = run.tf[f]
            a = next((e for e in use if t <= e.get("td_t", e["on_t"] + 2.0) + self.follow_post), use[-1] if use else None)
            self.active[f] = a
        self.ev = use[0] if use else None
        self.k = self.ev["k"] if self.ev else 1
        self._set(self.ev)
        self._layout_all()

    def _set(self, e):
        r = self.r
        self.ev = e
        if e is None:
            self.best_f = None; self.ov_t = None; self.slow_t = None
            return
        self.k = getattr(self, "kp", {}).get(id(e), e["k"])
        r._cam = self.cams[e["k"]]; r._cam_ev = e
        self.best_f = e.get("best_f")
        self.ov_t = (e["on_t"], e.get("td_t", e["on_t"] + 2.0) + self.post)
        self.slow_t = ((e["on_t"] - float(self.opt.get("slow_pre", 1.0)), e.get("td_t", e["on_t"] + 2.0) + float(self.opt.get("slow_post", 0.5)))
                       if abs(self.slow - 1.0) > 1e-9 else None)

    def _layout_all(self):
        """g47_video の _layout を、追う崩れのすべてで同じ拡大の縦の範囲になるように（最も高い頂と最も深い海底で）。"""
        keep = self.ev
        z1s, z0s = [], []
        for e in self.use or [None]:
            self._set(e) if e is not None else None
            self._layout()
            z1s.append(self.z1); z0s.append(self.z0)
        self._set(keep)
        self._layout()
        self.z1 = max(z1s); self.z0 = min(z0s)
        ph_max = float(self.bottom - 22 - self.zy)
        self.zoom_w = float(min(80.0, max(40.0, 1100.0 * (self.z1 - self.z0) / ph_max))) if self.opt.get("zoom_w", "auto") in (None, "auto") else float(self.opt["zoom_w"])
        self.zs = min(1100.0 / self.zoom_w, ph_max / (self.z1 - self.z0))

    def render(self, f, state):
        self._set(self.active.get(f))
        im = GV.Image.new("RGB", (GV.W, GV.H), GV.BG); dr = GV.ImageDraw.Draw(im)
        self.header(dr, f)
        GV.banner(dr, 1510, 70, state, self.slow, self.speed, self.hold_s)
        self.draw_top(im, dr, f)
        self.draw_zoom(im, dr, f)
        self.draw_overlay(im, dr, f)
        marks = []
        for i, e in enumerate(self.use):
            kp = self.kp.get(id(e), i + 1)
            marks.append((e["on_t"], "k%d" % kp if e is not self.ev else "巻き始め k%d" % kp, GV.RED))
            if e is self.ev:
                if e.get("td_t") is not None:
                    marks.append((e["td_t"], "着水", GV.PURP))
                if e.get("best_f") is not None:
                    marks.append((self.r.tf[e["best_f"]], "最も近い", GV.GREEN))
        GV.timebar(dr, 40, GV.W - 40, GV.H - 44, self.ta, self.tb, self.r.tf[f], marks, self.slow_t, head="t ")
        return im

    def schedule(self):
        out, acc, emitted = [], 0.0, 0
        for f in self.fr:
            t = self.r.tf[f]
            e = self.active.get(f)
            sl = False
            if e is not None and abs(self.slow - 1.0) > 1e-9:
                sl = e["on_t"] - float(self.opt.get("slow_pre", 1.0)) - 1e-9 <= t <= e.get("td_t", e["on_t"] + 2.0) + float(self.opt.get("slow_post", 0.5)) + 1e-9
            sp = self.speed * (self.slow if sl else 1.0)
            acc += 1.0 / sp
            n = int(math.floor(acc + 1e-9)) - emitted
            emitted += n
            if n > 0:
                out.append((f, n, "slow" if sl else "real"))
            if e is not None and f == e.get("best_f") and self.hold_s > 0:
                out.append((f, int(round(self.hold_s * GV.FPS)), "hold"))
        return out


def make_all(ref, opt, log=print):
    GCM.unthrottle_self()
    out = GV.guard_out(opt.get("out") or GV.VID)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    run = GV.Run(ref, opt.get("layer", "sdf"), log=log)
    rv = AllRunVideo(run, opt)
    name = opt.get("name") or "%s_all_x%g" % (run.rid, rv.speed)
    sch = rv.schedule()
    path = os.path.join(out, name + ".mp4")
    wr = GV.Writer(path)
    for f, n, st in sch:
        wr.put(rv.render(f, st), n)
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip47/g47_pvideo.py all", opt=opt, run=run.rid, rd=run.rd,
                still_offset_m=run.cx.off, still_offset_src=run.cx.off_src,
                events=[dict(k=v["k"], onset_frame=v["on_f"], onset_t=v["on_t"], onset_x=v["on_x"], touchdown_frame=v.get("td_f"), touchdown_t=v.get("td_t"),
                             touchdown_src=v.get("td_src"), best_frame=v.get("best_f"), best_src=v.get("best_src")) for v in run.evs],
                followed_k=[e["k"] for e in rv.use], window_s=[rv.ta, rv.tb], speed=rv.speed, slow=rv.slow, hold_s=rv.hold_s, follow_post_s=rv.follow_post,
                zoom=dict(w_m=rv.zoom_w, z0=rv.z0, z1=rv.z1), out_frames_written=wr.n, ffprobe=pb, elapsed_s=round(time.time() - t0, 1),
                ok=bool(pb.get("ok") and pb.get("frames") == wr.n))
    GV.jdump(info, os.path.join(out, name + ".json"))
    log("wrote %s  コマ %d（ffprobe %s）、%.1f s、作るのに %.0f s、ok %s" % (path, wr.n, pb.get("frames"), pb.get("duration_s", 0), time.time() - t0, info["ok"]))
    return info


def primary_kall(rd, primary_x=570.0):
    """来た波の崩れの g47_video の番号（全部の崩れの順）の並び（g47_periodic_ana.find_events の選び方）。"""
    import g47_periodic_ana as PA
    out, _a, _r, _s = PA.find_events(rd, primary_x=primary_x)
    return [d["k_all"] for d in out]


def primary_map(ref, primary_x=570.0):
    """来た波の崩れの番号 k → g47_video の k（全部の崩れの順）。"""
    rd = GV.resolve_run(ref)
    ks = primary_kall(rd, primary_x)
    return {i + 1: k for i, k in enumerate(ks)}, os.path.basename(rd)


def make_pmontage(ref, ks, opt, log=print):
    """同じ計算の来た波の崩れ k（来た波の順）を 2×3 に並べる（g47_video の Montage を使い、札だけ来た波の k に直す）。"""
    GCM.unthrottle_self()
    mp, rid = primary_map(ref, float(opt.get("primary_x", 570.0)))
    refs = ["%s@%d" % (ref, mp[k]) for k in ks]
    out = GV.guard_out(opt.get("out") or GV.VID)
    t0 = time.time()
    mt = GV.Montage(refs, opt, log=log)
    for r, k in zip(mt.runs, ks):
        r.label = "%s・来た波の k %d" % (rid, k)
    name = opt.get("name") or "%s_montage_k%s" % (rid, "-".join(str(k) for k in ks))
    path = os.path.join(out, name + ".mp4")
    wr = GV.Writer(path)
    for k, n, st in mt.schedule():
        wr.put(mt.render(k if k is not None else 0, st), n)
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip47/g47_pvideo.py montage", opt=opt, run=rid,
                k_primary=list(ks), k_all=[mp[k] for k in ks],
                panels=[dict(k=k, onset_frame=r.ev["on_f"], onset_t=r.ev["on_t"], touchdown_frame=r.ev.get("td_f"), touchdown_t=r.ev.get("td_t"),
                             best_frame=r.ev.get("best_f"), best_src=r.ev.get("best_src")) for r, k in zip(mt.runs, ks)],
                tau=[mt.tau0, mt.tau1], slow=mt.slow, out_frames_written=wr.n, ffprobe=pb, elapsed_s=round(time.time() - t0, 1),
                ok=bool(pb.get("ok") and pb.get("frames") == wr.n))
    GV.jdump(info, os.path.join(out, name + ".json"))
    log("wrote %s  コマ %d（ffprobe %s）、%.1f s、作るのに %.0f s、ok %s" % (path, wr.n, pb.get("frames"), pb.get("duration_s", 0), time.time() - t0, info["ok"]))
    return info


def make_pclip(ref, k, opt, log=print):
    """来た波の崩れ k（来た波の順）の短い動画（g47_video run --k=<全部の順> --around=1。札に来た波の k を書く）。"""
    mp, rid = primary_map(ref, float(opt.get("primary_x", 570.0)))
    o = dict(opt, k=str(mp[k]), around="1")
    o.setdefault("pre", "6"); o.setdefault("post", "3")
    o.setdefault("name", "%s_k%d_slow" % (rid, k))
    o["label"] = ("来た波の崩れ k %d" % k) + ("　" + opt["label"] if opt.get("label") else "")
    # g47_video.make_run_video と同じ流れ。拡大の窓の札の k だけ来た波の順にする（g47_video の k は全部の崩れの順）
    GCM.unthrottle_self()
    out = GV.guard_out(o.get("out") or GV.VID)
    t0 = time.time()
    run = GV.Run(ref, o.get("layer", "sdf"), log=log)
    rv = GV.RunVideo(run, o)
    e = rv.ev
    rv.k = k
    path = os.path.join(out, o["name"] + ".mp4")
    wr = GV.Writer(path)
    for f, n, st in rv.schedule():
        wr.put(rv.render(f, st), n)
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip47/g47_pvideo.py clip", opt=o, run=run.rid, k_primary=k,
                k_all=mp[k], onset_frame=e["on_f"], onset_t=e["on_t"], touchdown_frame=e.get("td_f"), touchdown_t=e.get("td_t"), touchdown_src=e.get("td_src"),
                best_frame=e.get("best_f"), best_src=e.get("best_src"), window_s=[rv.ta, rv.tb], slow=rv.slow, slow_t=rv.slow_t, hold_s=rv.hold_s,
                still_offset_m=run.cx.off, checks=run.checks, out_frames_written=wr.n, ffprobe=pb, elapsed_s=round(time.time() - t0, 1),
                ok=bool(pb.get("ok") and pb.get("frames") == wr.n))
    GV.jdump(info, os.path.join(out, o["name"] + ".json"))
    log("wrote %s  コマ %d（ffprobe %s）、%.1f s、作るのに %.0f s、ok %s" % (path, wr.n, pb.get("frames"), pb.get("duration_s", 0), time.time() - t0, info["ok"]))
    return info


if __name__ == "__main__":
    opt, pos = GV.parse(sys.argv[1:])
    if len(pos) >= 2 and pos[0] == "all":
        make_all(pos[1], opt)
    elif len(pos) >= 3 and pos[0] == "montage":
        make_pmontage(pos[1], [int(v) for v in pos[2].split(",")], opt)
    elif len(pos) >= 3 and pos[0] == "clip":
        make_pclip(pos[1], int(pos[2]), opt)
    else:
        print(__doc__); sys.exit(1)
