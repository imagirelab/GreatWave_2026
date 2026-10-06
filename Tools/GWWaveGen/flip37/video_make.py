# -*- coding: utf-8 -*-
"""段階 Video の道具の本体：毎コマの水面の網目 → Blender の粘土の図（二つの固定カメラ）→ 重ね・点数・時刻の帯・R9 の比べ・
t* で 2 秒止める三枚の図 → ffmpeg（30 MB 以下、実時間と最後の 3 秒の 0.5 倍）、ほかに回り台 12 方位の一枚。py -3.10

使い方:
  py -3.10 video_make.py all <config.json>        # 全部（下の順に実行）
  py -3.10 video_make.py plan|render|scores|compose|encode|turntable <config.json>
  py -3.10 video_make.py twin <誘導ありの config.json> <誘導なしの双子の config.json>   # 左右に並べた動画（置き方は誘導ありの t*）
出力（config の out_dir、既定は Unity/Build/FLIP37/video_tools/<config の名前>/）:
  plan.json（網目の時刻・置き方・カメラ）、render/<鍵>/（粘土の図。カメラ・解像度・切り取りの鍵）、scores_<鍵>.json、
  frames_rt/・frames_slow/（JPEG のコマ）、hold.png、frame_tstar.png、turntable.png、<name>_rt/_slow/_both.mp4、encode.json、timings.json
粘土の図と点数は鍵が同じなら前の物を使う（続きから）。設定を変えると plan.json は作り直され、カメラが変われば別の鍵のフォルダーに描く。
コマ（frames_*）と動画は毎回作り直す。計算の出力（網目）は読むだけ。
"""
import os, sys, json, math, subprocess, time, shutil, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import video_common as V  # noqa: E402
import p2_common as C  # noqa: E402

FW, FH = 1920, 1080
COL = {"jet_start": (200, 40, 40), "t_star": (0, 0, 0), "switch": (130, 60, 170), "tube_closed": (30, 110, 160)}
MARK_JA = {"jet_start": "噴き出しの始まり", "t_star": "選んだ瞬間 t*", "switch": "P2→P3 の切り替え", "tube_closed": "管が閉じる"}
MARK_ORDER = ("jet_start", "switch", "tube_closed", "t_star")


def font(sz, bold=False):
    for p in (("C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


F12, F14, F16, F18, F22 = font(13), font(15), font(17), font(19), font(23, True)


def env_g(out):
    e = dict(os.environ)
    tmp = os.path.join(out, "_tmp"); os.makedirs(tmp, exist_ok=True)
    e["TEMP"] = e["TMP"] = tmp   # C: は空きが少ないので、Blender・ffmpeg の一時ファイルも G: へ
    return e


# ================================================================ plan

def plan(cfg):
    out = cfg["out_dir"]; os.makedirs(out, exist_ok=True)
    pp = os.path.join(out, "plan.json")
    cur = json.loads(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")}))
    if os.path.isfile(pp):
        old = json.load(open(pp, encoding="utf8"))
        if json.dumps(old.get("cfg"), sort_keys=True, ensure_ascii=False) == json.dumps(cur, sort_keys=True, ensure_ascii=False):
            return old
        print("設定が変わったので plan.json を作り直す")
    tl = V.timeline(cfg)
    if not tl:
        raise SystemExit("網目がない：segments の mesh_dir・t0・t1 を確かめる")
    marks = resolve_marks(cfg, tl)
    cfg["marks"] = marks
    pl = V.resolve_placement(cfg, tl)
    cams = V.main_cams(cfg, pl)
    t_lo = cfg.get("t_start", tl[0][0]); t_hi = cfg.get("t_end", marks["t_star"])
    r9 = None
    if cfg["r9"]:
        # R9（見本06 の採用の形）の網目は読むだけ。SHA-256 を確かめて記録する
        meta = json.load(open(V.R9_MESH, encoding="utf8"))
        h = hashlib.sha256(open(os.path.join(os.path.dirname(V.R9_MESH), meta["bin"]), "rb").read()).hexdigest()
        r9 = {"json": V.R9_MESH, "bin_sha256": h, "matches_record": h == V.R9_SHA == meta["sha256"]}
        if not r9["matches_record"]:
            print("注意：R9 の網目の SHA-256 が記録と違う", h)
    tl_show = [(t, pth, si) for t, pth, si in tl if t_lo - 1.0 <= t <= t_hi + 1e-6]
    p = {"name": cfg.get("name", os.path.basename(out)), "label": cfg["label"], "r9": r9, "segments": cfg["segments"], "marks": marks,
         "t_lo": t_lo, "t_hi": t_hi, "timeline": [list(q) for q in tl_show],
         "outer": V.outer_map(cfg, tl_show), "seg_dp": [V.seg_dp(s) for s in cfg["segments"]],
         "placement": pl, "cams": cams, "tt_cams": V.tt_cams(pl, cfg["tt"]), "cfg": cur}
    json.dump(p, open(pp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return p


def resolve_marks(cfg, tl):
    """印の時刻。数を書けばそのまま。"analysis" と書くと区間の run_dir の analysis.json から読む（後ろの区間を優先）：
    jet_start = P2 の解析の t_first_overturn_any_section（どこかの切り口で前の面が垂直を過ぎた最初の時刻）、
                P1 の解析なら events.face_past_vertical.t
    t_star    = analysis.json の best の t（P2）／best_frame_vs_painting.A_side の t（P1）
    switch    = "segments" と書くと 2 番目の区間の t0
    t_star がなければ最後の網目の時刻。読めなかった印は None（帯に「なし」と出る）と、marks_note に理由を書く。"""
    marks = dict(cfg["marks"])
    notes = {}
    ans = []
    for s in cfg["segments"][::-1]:
        ap = os.path.join(s.get("run_dir", ""), "analysis.json")
        if s.get("run_dir") and os.path.isfile(ap):
            ans.append(json.load(open(ap, encoding="utf8")))
    for k in ("jet_start", "t_star"):
        if marks.get(k) != "analysis":
            continue
        v = None
        for a in ans:
            if k == "jet_start":
                v = a.get("t_first_overturn_any_section") or ((a.get("events") or {}).get("face_past_vertical") or {}).get("t")
            else:
                v = (a.get("best") or {}).get("t") or ((a.get("best_frame_vs_painting") or {}).get("A_side") or {}).get("t")
            if v is not None:
                break
        marks[k] = v
        notes[k] = "analysis.json から" if v is not None else "analysis.json に値がない（巻いていない等）"
    if marks.get("switch") == "segments":
        marks["switch"] = cfg["segments"][1]["t0"] if len(cfg["segments"]) > 1 else None
    if marks.get("t_star") is None:
        marks["t_star"] = tl[-1][0]; notes["t_star"] = "印がないので最後の網目の時刻"
    marks["_note"] = notes
    return marks


def score_key(p):
    """点数の鍵（置き方と網目の一覧が同じなら前の点数を使う）"""
    pl = p["placement"]
    return hashlib.md5(json.dumps([pl["anchor"], pl["psi_deg"], pl["scale"], p["marks"]["t_star"], [q[1] for q in p["timeline"]]]
                                  + ([sorted((k, v["mesh"], v["hole"]) for k, v in p["outer"].items())] if p.get("outer") else [])).encode()).hexdigest()[:8]


def fresh_frames(fd, n):
    """コマのフォルダーを用意する。前の回の余ったコマ（番号 n 以上）は 1 枚ずつ消す（ffmpeg が続きの番号を読まないように）。"""
    os.makedirs(fd, exist_ok=True)
    for f in os.listdir(fd):
        if f.endswith(".jpg") and f[:-4].isdigit() and int(f[:-4]) >= n:
            os.remove(os.path.join(fd, f))


def rkey(cams, res, crop):
    """描画の鍵（カメラ・解像度・切り取りが変わると別のフォルダーに描く。古い図を間違って使わないため）"""
    return hashlib.md5(json.dumps([cams, res, crop], sort_keys=True).encode()).hexdigest()[:8]


def rdir(cfg, p):
    crop = cfg.get("crop_main") if not cfg.get("two_sided") else [cfg.get("crop_main"), "two_sided"]
    return os.path.join(cfg["out_dir"], "render", rkey(p["cams"], cfg["render_res"], crop))


def fid(path):
    return os.path.splitext(os.path.basename(path))[0].replace("mesh_", "f") + "_" + hashlib.md5(path.encode()).hexdigest()[:6]


def fkey(p, path):
    """描いた図の名前。外の海（P2 の網目）を足すコマは、その網目と抜く範囲も鍵に入れる。"""
    o = (p.get("outer") or {}).get(path)
    if not o:
        return fid(path)
    return fid(path) + "_o" + hashlib.md5(json.dumps([o["mesh"], o["hole"], (p.get("cfg") or {}).get("outer_tint")]).encode()).hexdigest()[:5]


def extra_of(p, path):
    """Blender の item に渡す外の海：[{"mesh": .., "hole": "auto" か [x0, x1, z0, z1]}]"""
    o = (p.get("outer") or {}).get(path)
    return [{"mesh": o["mesh"], "hole": o["hole"]}] if o else []


def r9_dir(cams, res):
    h = hashlib.md5(json.dumps([cams, res], sort_keys=True).encode()).hexdigest()[:10]
    return os.path.join(V.TOOLS_OUT, "_r9_cache", h)


# ================================================================ render

def run_blender(job, out, tag, timer):
    jp = os.path.join(out, "job_%s.json" % tag)
    json.dump(job, open(jp, "w", encoding="utf8"))
    lp = os.path.join(out, "blender_%s.log" % tag)
    with timer("blender_" + tag), open(lp, "w", encoding="utf8") as lf:
        r = subprocess.run([V.BLENDER, "-b", "--factory-startup", "-P", os.path.join(HERE, "video_render_bl.py"), "--", jp],
                           stdout=lf, stderr=subprocess.STDOUT, env=env_g(out), timeout=3600)
    tail = open(lp, encoding="utf8", errors="replace").read()[-400:]
    if r.returncode != 0 or "VIDEO_BL DONE" not in tail:
        raise SystemExit("Blender の失敗（%s）：%s" % (lp, tail))
    print(tail.strip().splitlines()[-1])


def render(cfg, p, timer):
    out = cfg["out_dir"]; res = cfg["render_res"]
    pl = p["placement"]
    xf = {"T": pl["T"], "E": pl["E"], "O": pl["O"], "s": pl["scale"], "anchor": pl["anchor"]}
    items = []
    for t, path, si in p["timeline"]:
        f = fkey(p, path)
        items.append({"mesh": path, "extra": extra_of(p, path), "xf": xf, "cams": p["cams"], "crop": cfg.get("crop_main"),
                      "out": {c["name"]: os.path.join(rdir(cfg, p), c["name"], f + ".png").replace("\\", "/") for c in p["cams"]}})
    # R9（見本06 の主役波と左の小波。Unity の座標のまま）。カメラが同じなら前の図を使う
    if cfg["r9"]:
        rd = r9_dir(p["cams"], res)
        items.append({"static": V.R9_MESH, "xf": None, "cams": p["cams"],
                      "out": {c["name"]: os.path.join(rd, c["name"] + ".png").replace("\\", "/") for c in p["cams"]}})
    run_blender({"res": res, "near_clip": cfg["near_clip"], "outer_tint": cfg["outer_tint"], "items": items,
                 "two_sided": bool(cfg.get("two_sided"))}, out, "main", timer)


# ================================================================ scores

def scores(cfg, p, timer):
    out = cfg["out_dir"]
    pk = score_key(p)
    sp = os.path.join(out, "scores_%s.json" % pk)
    mp = os.path.join(out, "mask_tstar_%s.png" % pk)
    pl = p["placement"]
    ts = p["marks"]["t_star"]
    tstar_path = V.mesh_at([tuple(q) for q in p["timeline"]], ts)[1]
    # 外の海を足すときは鍵に入れる（足す前の点数を使わないように）
    if os.path.isfile(sp):
        if not os.path.isfile(mp):
            P, tri = V.load_frame(tstar_path, (p.get("outer") or {}).get(tstar_path))
            Image.fromarray((V.score_mesh(P, tri, pl)[1] * 255).astype(np.uint8)).save(mp)
        return json.load(open(sp, encoding="utf8"))
    res = {}
    with timer("scores"):
        for t, path, si in p["timeline"]:
            P, tri = V.load_frame(path, (p.get("outer") or {}).get(path))
            s, m = V.score_mesh(P, tri, pl)
            s["t"] = t; s["seg"] = si
            res[path] = s
            if path == tstar_path:
                Image.fromarray(V.overlap_image(m)).save(os.path.join(out, "overlap_tstar_%s.png" % pk))
                Image.fromarray((m * 255).astype(np.uint8)).save(mp)
    json.dump(res, open(sp, "w", encoding="utf8"), ensure_ascii=False, indent=0)
    return res


# ================================================================ compose

def painting_display(w, h):
    _, _, src = C.painting_outline()
    fr = src["frame"]
    img = Image.open(V.REF).convert("RGB")
    img = img.resize((int(round(img.width * fr["scale"])), int(round(img.height * fr["scale"]))), Image.LANCZOS)
    cv = Image.new("RGB", (FW, FH), (0, 0, 0)); cv.paste(img, (int(round(fr["offset_x"])), 0))
    return cv.resize((w, h), Image.LANCZOS)


def draw_outline(im, w, h, width=2):
    outer, inner, _ = C.painting_outline()
    dr = ImageDraw.Draw(im)
    k = w / FW
    for pl in (outer, inner):
        dr.line([((x + 0.5) * k - 0.5, (y + 0.5) * k - 0.5) for x, y in pl], fill=(25, 70, 220), width=width)
    x0, x1, y0, y1 = C.WIN
    dr.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], outline=(150, 150, 150))
    return im


def fit_text(dr, text, room, fonts=None):
    """見出しの文字を幅 room に収める：大きい字 → 小さい字 → 末尾を「…」で切る。戻り (文字, 字)。"""
    fonts = fonts or (F22, F18)
    for f in fonts:
        if dr.textlength(text, font=f) <= room:
            return text, f
    f = fonts[-1]
    while len(text) > 4 and dr.textlength(text + "…", font=f) > room:
        text = text[:-1]
    return text + "…", f


def guide_state(seg, t):
    """誘導の札（見出しに出す）。誘導のない区間は None。"""
    if not seg.get("guided"):
        return None
    gw = seg.get("guide_window")
    if not gw:
        return "【誘導あり】"
    if t < gw[0] - 1e-6:
        return "【誘導あり・力はまだ 0（%.2f s から）】" % gw[0]
    if t <= gw[1] + 1e-6:
        return "【誘導あり・力 on】"
    return "【誘導あり・力は %.2f s から 0】" % gw[1]


def tag(dr, xy, text, f=F14, fg=(0, 0, 0), bg=(255, 255, 255, 200)):
    x, y = xy
    bb = dr.textbbox((x, y), text, font=f)
    dr.rectangle([bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3], fill=bg[:3])
    dr.text((x, y), text, font=f, fill=fg)


class Composer:
    def __init__(self, cfg, p, sc):
        self.cfg, self.p, self.sc = cfg, p, sc
        self.out = cfg["out_dir"]
        self.tl = [tuple(q) for q in p["timeline"]]
        self.r9 = {}
        if cfg["r9"]:
            rd = r9_dir(p["cams"], cfg["render_res"])
            for c in p["cams"]:
                self.r9[c["name"]] = Image.open(os.path.join(rd, c["name"] + ".png")).convert("RGB")
        self.cache = {}
        self.ser = sorted(((v["t"], v) for v in sc.values()), key=lambda q: q[0])

    def panel(self, path, cam, w, h, outline=False):
        key = (path, cam, w, h, outline)
        if key not in self.cache:
            if len(self.cache) > 12:
                self.cache.clear()
            im = Image.open(os.path.join(rdir(self.cfg, self.p), cam, fkey(self.p, path) + ".png")).convert("RGB")
            if im.size != (w, h):
                im = im.resize((w, h), Image.LANCZOS)
            if outline:
                draw_outline(im, w, h)
            self.cache[key] = im
        return self.cache[key].copy()

    # -------- 時刻の帯
    def time_bar(self, dr, x0, y0, w, t, mode):
        p = self.p
        lo, hi = p["t_lo"], p["t_hi"]
        X = lambda tt: x0 + (tt - lo) / max(hi - lo, 1e-6) * w
        # 区間（計算の出どころ）
        cols = [(200, 200, 200), (150, 190, 235), (200, 225, 170)]
        for i, s in enumerate(p["segments"]):
            a = max(lo, s.get("t0", lo)); b = min(hi, s.get("t1", hi))
            if b <= a:
                continue
            dr.rectangle([X(a), y0, X(b), y0 + 22], fill=cols[i % 3])
        seg_labels = []
        for i, s in enumerate(p["segments"]):
            a = max(lo, s.get("t0", lo)); b = min(hi, s.get("t1", hi))
            if b > a:
                seg_labels.append((X(a) + 4, y0 + 2, s.get("label", "区間 %d" % (i + 1)), cols[i % 3]))
        guide_labels = []
        # 誘導のある区間は斜線（設定の segments[i]["guided"] = true）。"guide_window": [入, 切] があれば、力がかかる時刻だけに斜線
        for i, s in enumerate(p["segments"]):
            if not s.get("guided"):
                continue
            a = max(lo, s.get("t0", lo)); b = min(hi, s.get("t1", hi))
            gw = s.get("guide_window")
            if gw:
                a = max(a, gw[0]); b = min(b, gw[1])
            if b <= a:
                continue
            xx = X(a)
            while xx < X(b):
                dr.line([xx, y0 + 22, min(xx + 10, X(b)), y0], fill=(200, 60, 60))
                xx += 8
            if gw:
                dr.line([X(b), y0, X(b), y0 + 22], fill=(200, 60, 60), width=2)
                gt = "誘導の力 %.2f〜%.2f s（斜線）→" % (gw[0], gw[1])
                gx = X(b) - 6 - dr.textlength(gt, font=F12)
                seg_end = max([x + dr.textlength(t_, font=F12) for x, _, t_, _ in seg_labels if x <= gx] or [x0])
                if gx < seg_end + 10:      # 斜線の中に入らなければ、斜線の右へ
                    gt = "← 誘導の力 %.2f〜%.2f s（斜線）" % (gw[0], gw[1]); gx = X(b) + 6
                guide_labels.append((gx, y0 + 2, gt))
        # 区間の名前と誘導の札は斜線の上に書く（読めるように）
        for x, y, txt, bgc in seg_labels:
            tag(dr, (x, y), txt, F12, bg=bgc)
        for x, y, txt in guide_labels:
            tag(dr, (x, y), txt, F12, fg=(170, 40, 40), bg=(250, 235, 235))
        # 0.5 倍の動画では、遅くした範囲を帯の下に示す
        if mode == "slow":
            a, b = slow_range(self.cfg, p)
            dr.rectangle([X(a), y0 + 24, X(b), y0 + 30], fill=(235, 170, 90))
        dr.rectangle([x0, y0, x0 + w, y0 + 22], outline=(80, 80, 80))
        # 網目のある時刻
        for tt, _, _ in self.tl:
            if lo <= tt <= hi:
                dr.line([X(tt), y0 + 22, X(tt), y0 + 27], fill=(90, 90, 90))
        # 目盛り
        for s_ in range(int(math.ceil(lo)), int(math.floor(hi)) + 1):
            dr.line([X(s_), y0 + 22, X(s_), y0 + 34], fill=(0, 0, 0))
            dr.text((X(s_) - 8, y0 + 35), "%d s" % s_, font=F12, fill=(0, 0, 0))
        # 印（文字が重なるときは上へずらす）
        placed = []
        for name in MARK_ORDER:
            tm = p["marks"].get(name)
            if tm is None or not (lo - 1e-6 <= tm <= hi + 1e-6):
                continue
            c = COL[name]
            dr.line([X(tm), y0 - 10, X(tm), y0 + 34], fill=c, width=3 if name == "t_star" else 2)
            dr.polygon([(X(tm) - 6, y0 - 16), (X(tm) + 6, y0 - 16), (X(tm), y0 - 6)], fill=c)
            txt = "%s %.2f s" % (MARK_JA[name], tm)
            bb = dr.textbbox((0, 0), txt, font=F14)
            tw = bb[2] - bb[0]
            tx = X(tm) + 8 if X(tm) + 8 + tw < x0 + w + 50 else X(tm) - 8 - tw
            ty = y0 - 34
            while any(not (tx + tw < a0 or tx > a1) and ty == yy for a0, a1, yy in placed):
                ty -= 19
            placed.append((tx, tx + tw, ty))
            dr.text((tx, ty), txt, font=F14, fill=c)
        # 今の時刻
        cx = X(min(max(t, lo), hi))
        dr.polygon([(cx - 9, y0 + 58), (cx + 9, y0 + 58), (cx, y0 + 40)], fill=(235, 120, 30))
        dr.line([cx, y0, cx, y0 + 22], fill=(235, 120, 30), width=3)
        # 印の凡例（ない印は「なし」）
        lg = "　".join("%s：%s" % (MARK_JA[n], ("%.2f s" % p["marks"][n]) if p["marks"].get(n) is not None else "なし")
                      for n in ("jet_start", "t_star", "switch", "tube_closed") if n != "tube_closed" or n in p["marks"])
        dr.text((x0, y0 + 64), "計算の時刻の帯（細い目盛り＝網目のある時刻）。" + lg, font=F14, fill=(40, 40, 40))

    # -------- 点数の線
    def score_graph(self, dr, x0, y0, w, h, t):
        p = self.p
        lo, hi = p["t_lo"], p["t_hi"]
        X = lambda tt: x0 + (tt - lo) / max(hi - lo, 1e-6) * w
        dr.rectangle([x0, y0, x0 + w, y0 + h], outline=(120, 120, 120), fill=(252, 252, 250))
        for v in (0.25, 0.5, 0.75):
            dr.line([x0, y0 + h - v * h, x0 + w, y0 + h - v * h], fill=(225, 225, 225))
        pts_i = [(X(tt), y0 + h - v["iou"] * h) for tt, v in self.ser if lo <= tt <= hi]
        pts_d = [(X(tt), y0 + h - min(v["mean_px"], 300) / 300 * h) for tt, v in self.ser if lo <= tt <= hi and v.get("mean_px") is not None]
        if len(pts_i) > 1:
            dr.line(pts_i, fill=(40, 150, 70), width=2)
        if len(pts_d) > 1:
            dr.line(pts_d, fill=(220, 110, 30), width=2)
        tm = p["marks"].get("t_star")
        if tm is not None and lo <= tm <= hi:
            dr.line([X(tm), y0, X(tm), y0 + h], fill=(0, 0, 0))
        cx = X(min(max(t, lo), hi))
        dr.line([cx, y0, cx, y0 + h], fill=(235, 120, 30), width=2)
        dr.text((x0 + 4, y0 + 2), "緑＝IoU（0〜1）　橙＝輪郭の平均距離（0〜300 px）", font=F12, fill=(60, 60, 60))

    def header(self, dr, t, path, mode):
        p = self.p
        si = [q for q in self.tl if q[1] == path][0][2]
        seg = p["segments"][si]
        dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
        dp = (p.get("seg_dp") or [None] * (si + 1))[si]
        sl = seg.get("label", "区間 %d" % (si + 1)) + ("・粒子 %.2g m" % dp if dp else "")
        if (p.get("outer") or {}).get(path):
            sl += "＋外の海 P2"
        right = "t = %.2f s　コマ %s（%s）　%s" % (t, os.path.basename(path)[5:9], sl, mode)
        bb = dr.textbbox((0, 0), right, font=F18)
        dr.text((FW - 14 - (bb[2] - bb[0]), 11), right, font=F18, fill=(255, 220, 160))
        x_right = FW - 14 - (bb[2] - bb[0])
        g = guide_state(seg, t)
        if g:
            bb2 = dr.textbbox((0, 0), g, font=F18)
            x = x_right - 12 - (bb2[2] - bb2[0])
            dr.rectangle([x - 4, 6, x + (bb2[2] - bb2[0]) + 4, 38], fill=(190, 40, 40) if "力 on" in g else (120, 60, 60))
            dr.text((x, 11), g, font=F18, fill=(255, 255, 255))
            x_right = x - 4
        # 左の名前とラベル：右の文字に重なるなら小さい字にし、それでも重なれば末尾を「…」で切る（全文は plan.json の label）
        left, f = fit_text(dr, "%s　%s" % (p["name"], p["label"]), x_right - 12 - 16)
        dr.text((12, 8 if f is F22 else 11), left, font=f, fill=(255, 255, 255))

    def gap_note(self, t):
        """t の網目がない（前の網目を保っている）ときの注意。網目の間が 0.2 s を超えるときだけ。"""
        t_ = V.mesh_at(self.tl, t)[0]
        return ("注意：%.2f s の網目がない（%.2f s の網目を見せている）" % (t, t_)) if t - t_ > 0.2 else None

    def numbers(self, dr, x0, y0, path, t):
        s = self.sc[path]
        pl = self.p["placement"]
        lines = [
            "原画視点のシルエット（置き方は t* のまま固定）：IoU %.3f　輪郭の平均距離 %s px（1920 表示）" % (
                s["iou"], "%.0f" % s["mean_px"] if s.get("mean_px") is not None else "—"),
            "網目の最高 %.1f m（計算の座標）　置き方 ψ=%d°・倍率 %.2f（%s）" % (s["crest_y"], pl["psi_deg"], pl["scale"], pl["source"]),
            "点数は記録だけ（合否に使わない）。投影での合わせ・時間の伸縮・形の引き寄せはしていない。",
        ]
        o = (self.p.get("outer") or {}).get(path)
        if o:
            lines.append("主役の範囲の外は粗い計算 P2 の水面（網目 %s、時刻の差 %+.3f s）。境目は少し重ねて描く" % (os.path.basename(o["mesh"])[5:9], o["dt"]))
        if s.get("camera_wet"):
            lines.append("注意：このコマは原画カメラの真下の水面がカメラの高さに近い（カメラが水の中に入る）")
        g = self.gap_note(t)
        if g:
            lines.append(g)
        for i, l in enumerate(lines):
            dr.text((x0, y0 + i * 22), l, font=F14, fill=(150, 30, 30) if l.startswith("注意") else (20, 20, 20))

    def frame(self, t, mode, bar_mode="rt"):
        t_, path, si = V.mesh_at(self.tl, t)
        im = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(im)
        self.header(dr, t, path, mode)
        a = self.panel(path, "painting", 960, 540, outline=True)
        b = self.panel(path, "leftfront", 960, 540)
        im.paste(a, (0, 44)); im.paste(b, (960, 44))
        tag(dr, (10, 52), "原画カメラ（PaintingCam v1）・青＝原画の大波の輪郭（重ねただけ）", F14)
        lf = self.cfg["leftfront"]
        tag(dr, (970, 52), ("左前の斜め（固定。見本06 の回り台の %.0f°・%.0f m・高さ %.0f m）" % (lf["az_deg"], lf["dist"], lf["height"]))
            if "az_deg" in lf else "左前の斜め（固定）", F14)
        dr.line([960, 44, 960, 584], fill=(255, 255, 255), width=2)
        if self.cfg.get("r9_in_frames", True) and self.r9:
            # R9（1 回目・2 回目の配置。r9_in_frames: false なら毎コマには出さず、t* の後の比べの一枚だけにする）
            for j, c in enumerate(("painting", "leftfront")):
                r = self.r9[c].resize((480, 270), Image.LANCZOS)
                if c == "painting":
                    draw_outline(r, 480, 270, 1)
                im.paste(r, (j * 480, 584))
            tag(dr, (6, 590), "比べ：見本06 R9（同じカメラ・動かない。目標ではない）", F12)
        else:
            self.info_block(dr, 20, 600, path, t)
        # 点数
        self.score_graph(dr, 980, 600, 920, 130, t)
        self.numbers(dr, 980, 740, path, t)
        # 時刻の帯
        self.time_bar(dr, 60, 900, 1800, t, bar_mode)
        return im

    def phys_tag(self, dr, xy, path, t, f=None):
        """【物理だけ・誘導なし】／誘導の札を大きく出す。"""
        si = [q for q in self.tl if q[1] == path][0][2]
        g = guide_state(self.p["segments"][si], t)
        tag(dr, xy, g if g else "【" + self.cfg.get("physics_label", "物理だけ・誘導なし") + "】", f or F22, fg=(255, 255, 255),
            bg=((190, 40, 40) if "力 on" in g else (120, 60, 60)) if g else (40, 110, 60))

    def info_block(self, dr, x0, y0, path, t):
        """毎コマの左下：物理だけの札、コマ・時刻、粒子の間隔、出どころ。"""
        si = [q for q in self.tl if q[1] == path][0][2]
        seg = self.p["segments"][si]
        dp = (self.p.get("seg_dp") or [None] * (si + 1))[si]
        fr = os.path.basename(path)[5:9]
        self.phys_tag(dr, (x0 + 4, y0 + 4), path, t)
        dr.text((x0, y0 + 50), "t = %.2f s　コマ %s（24 コマ/秒、計算の時刻）" % (t, fr), font=F22, fill=(0, 0, 0))
        lines = ["粒子の間隔 %s　%s" % (("%.2g m" % dp) if dp else "—", seg.get("label", ""))]
        if seg.get("note"):
            lines.append(seg["note"])
        o = (self.p.get("outer") or {}).get(path)
        if o:
            lines.append(self.cfg.get("outer_note", "主役の範囲の外の海：粗い計算 P2 の水面（粒子 1 m）"))
        lines.append("粘土の見た目だけ（材質・爪・白・しぶきなし）。カメラは二つとも固定。")
        for i, l in enumerate(lines):
            dr.text((x0, y0 + 92 + i * 24), l, font=F16, fill=(30, 30, 30))

    def silhouette_panel(self, w, h):
        """③ 流体のシルエット（t* の置き方・原画カメラ）に原画の輪郭を細い線で重ねた図。"""
        mp = os.path.join(self.out, "mask_tstar_%s.png" % score_key(self.p))
        win = C.window_mask(V.SC)
        img = np.full(win.shape + (3,), 252, np.uint8)
        img[~win] = (232, 232, 232)
        if os.path.isfile(mp):
            m = np.array(Image.open(mp).convert("L")) > 127
            img[m & win] = (125, 140, 160)
            img[m & ~win] = (170, 178, 188)
        im = Image.fromarray(img).resize((w, h), Image.LANCZOS)
        return draw_outline(im, w, h, 1)

    def hold(self, t):
        t_, path, si = V.mesh_at(self.tl, t)
        im = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(im)
        self.header(dr, t, path, "t* で止める（%.0f 秒）" % self.cfg["hold_s"])
        s = self.sc[path]
        W3, H3 = 640, 360
        y = 86
        im.paste(painting_display(W3, H3), (0, y))
        im.paste(self.panel(path, "painting", W3, H3), (640, y))
        im.paste(self.silhouette_panel(W3, H3), (1280, y))
        for x, txt in ((0, "① 原画"), (640, "② 流体の粘土・原画カメラ"), (1280, "③ 流体のシルエット（灰）と原画の輪郭（青の線）")):
            tag(dr, (x + 8, y + 6), txt, F16)
        tag(dr, (1288, y + H3 - 64), "IoU %.3f" % s["iou"], F22, bg=(255, 255, 255))
        tag(dr, (1288, y + H3 - 32), "輪郭の平均距離 %s px（1920 表示）" % ("%.0f" % s["mean_px"] if s.get("mean_px") is not None else "—"), F16)
        dr.line([640, y, 640, y + H3], fill=(255, 255, 255), width=2); dr.line([1280, y, 1280, y + H3], fill=(255, 255, 255), width=2)
        dr.text((10, 50), "選んだ瞬間 t* = %.2f s（コマ %s）。いちばん原画に近い瞬間（z=0 の断面を原画の読み A と比べた点数が最小）" % (
            self.p["marks"]["t_star"], os.path.basename(path)[5:9]), font=F18, fill=(0, 0, 0))
        self.phys_tag(dr, (1500, 50), path, t, F16)
        # 下の段（参考）：左前の斜め・z=0 の断面と原画
        y2 = 470
        im.paste(self.panel(path, "leftfront", W3, H3), (0, y2))
        tag(dr, (8, y2 + 6), "参考：流体・左前の斜め（固定）", F14)
        sec = self.cfg.get("hold_section_img")
        if sec and os.path.isfile(sec):
            si_ = Image.open(sec).convert("RGB")
            box = self.cfg.get("hold_section_crop") or [0, 0, si_.width, si_.height]
            si_ = si_.crop(box)
            k = min(W3 / si_.width, H3 / si_.height)
            si_ = si_.resize((int(si_.width * k), int(si_.height * k)), Image.LANCZOS)
            bgp = Image.new("RGB", (W3, H3), (255, 255, 255)); bgp.paste(si_, ((W3 - si_.width) // 2, (H3 - si_.height) // 2))
            im.paste(bgp, (640, y2))
            tag(dr, (648, y2 + 6), "参考：z=0 の断面（橙＝流体、青＝原画の読み A、頂を 20 m にそろえた）", F12)
        x3 = 1300
        lines = self.cfg.get("hold_notes") or []
        for i, l in enumerate(lines):
            dr.text((x3, y2 + 4 + i * 24), l, font=F16, fill=(20, 20, 20))
        self.numbers(dr, 20, 845, path, t)
        self.time_bar(dr, 60, 960, 1800, t, "hold")
        return im

    def tt_frame(self, k):
        """回り台の k 番目の方位（t* の流体の粘土。大きく一枚＋12 方位の小さな一覧）。"""
        p = self.p
        ts = p["marks"]["t_star"]
        t_, path, si = V.mesh_at(self.tl, ts)
        im = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(im)
        self.header(dr, ts, path, "t* の回り台 %d/12" % (k + 1))
        td = tt_dir(self.cfg, p, path)
        c = p["tt_cams"][k]
        big = Image.open(os.path.join(td, c["name"] + ".png")).convert("RGB").resize((1440, 810), Image.LANCZOS)
        im.paste(big, (0, 50))
        tag(dr, (10, 58), "回り台 %s°（t* = %.2f s、粘土・流体だけ。方位は見本06 の回り台の決め方、0° が原画の側）" % (c["name"][2:].lstrip("0") or "0", ts), F18)
        self.phys_tag(dr, (10, 96), path, ts, F16)
        for j, cj in enumerate(p["tt_cams"]):
            th = Image.open(os.path.join(td, cj["name"] + ".png")).convert("RGB").resize((224, 126), Image.LANCZOS)
            xx = 1450 + (j % 2) * 232; yy = 52 + (j // 2) * 140
            im.paste(th, (xx, yy))
            if j == k:
                dr.rectangle([xx - 3, yy - 3, xx + 226, yy + 128], outline=(235, 120, 30), width=4)
            dr.text((xx + 4, yy + 2), "%s°" % (cj["name"][2:].lstrip("0") or "0"), font=F12, fill=(0, 0, 0))
        self.time_bar(dr, 60, 920, 1800, ts, "hold")
        return im

    def r9_frame(self):
        """見本06 R9 と流体を同じカメラで並べる一枚（情報。R9 は目標ではない）。"""
        p = self.p
        ts = p["marks"]["t_star"]
        t_, path, si = V.mesh_at(self.tl, ts)
        im = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(im)
        self.header(dr, ts, path, "情報：見本06 R9 と流体")
        W2, H2 = 672, 378
        for row, cam in enumerate(("painting", "leftfront")):
            y = 56 + row * (H2 + 12)
            r = self.r9[cam].resize((W2, H2), Image.LANCZOS)
            f = self.panel(path, cam, W2, H2)
            im.paste(r, (250, y)); im.paste(f, (950, y))
            dr.text((12, y + 150), "原画カメラ" if cam == "painting" else "左前の斜め", font=F22, fill=(0, 0, 0))
            dr.text((12, y + 184), "（同じカメラ）", font=F16, fill=(60, 60, 60))
            tag(dr, (258, y + 6), "見本06 R9（今の作品の形。目標ではない）", F14)
            tag(dr, (958, y + 6), "流体 t* = %.2f s（物理だけ）" % ts, F14)
        dr.text((250, 832), "情報としての比べ。R9 は今の作品の形で、新しい形の目標ではない（先生の指示 Q37：流体の計算を基にした形へ変える）。",
                font=F16, fill=(60, 60, 60))
        self.time_bar(dr, 60, 920, 1800, ts, "hold")
        return im


def slow_range(cfg, p):
    """0.5 倍の範囲。slow_range "tstar"（既定）＝t* の前 slow_last_s 秒、"end"＝見せる範囲の最後の slow_last_s 秒（t* を含めば t* で止める）。"""
    ts = p["marks"]["t_star"]; lo, hi = p["t_lo"], p["t_hi"]
    if cfg.get("slow_range", "tstar") == "end":
        return max(lo, hi - cfg["slow_last_s"]), hi
    return max(lo, ts - cfg["slow_last_s"]), ts


def schedule(cfg, p):
    """コマの予定。("f", t)＝動き、("h", t*)＝止める三枚、("tt", k)＝回り台の k 番目の方位、("r9", t*)＝R9 と流体の比べ。
    rt_extras（例 ["turntable", "r9panel"]）を書くと、実時間の版で t* で止めた後に回り台（1 方位 tt_hold_s 秒）と R9 の比べ（r9panel_s 秒）を入れる。"""
    fps = cfg["fps"]
    ts = p["marks"]["t_star"]; lo, hi = p["t_lo"], p["t_hi"]
    rt = []
    n = int(math.floor((min(ts, hi) - lo) * fps + 1e-6))
    rt += [("f", lo + k / fps) for k in range(n + 1)]
    rt += [("h", ts)] * int(round(cfg["hold_s"] * fps))
    for ex in cfg.get("rt_extras") or []:
        if ex == "turntable":
            for k in range(12):
                rt += [("tt", k)] * int(round(cfg.get("tt_hold_s", 0.5) * fps))
        elif ex == "r9panel" and cfg["r9"]:
            rt += [("r9", ts)] * int(round(cfg.get("r9panel_s", 2.0) * fps))
    if hi > ts + 1e-6:
        m = int(math.floor((hi - ts) * fps + 1e-6))
        rt += [("f", ts + k / fps) for k in range(1, m + 1)]
    sl = []
    a, b = slow_range(cfg, p)
    dt = cfg["slow_factor"] / fps
    n = int(math.floor((b - a) / dt + 1e-6))
    held = False
    for k in range(n + 1):
        t = a + k * dt
        if not held and t >= ts - 1e-6:
            sl += [("h", ts)] * int(round(cfg["hold_s"] * fps)); held = True
        sl.append(("f", t))
    if not held:
        sl += [("h", ts)] * int(round(cfg["hold_s"] * fps))
    return {"rt": rt, "slow": sl}


def compose(cfg, p, sc, timer):
    out = cfg["out_dir"]
    cp = Composer(cfg, p, sc)
    sch = schedule(cfg, p)
    hold_img = None
    extra = {}
    sa, sb = slow_range(cfg, p)
    with timer("compose"):
        for kind, seq in sch.items():
            fd = os.path.join(out, "frames_" + kind)
            fresh_frames(fd, len(seq))
            for i, (k, t) in enumerate(seq):
                if k == "h":
                    if hold_img is None:
                        hold_img = cp.hold(t)
                        hold_img.save(os.path.join(out, "hold.png"))
                    im = hold_img
                elif k in ("tt", "r9"):
                    if (k, t) not in extra:
                        extra[(k, t)] = cp.tt_frame(t) if k == "tt" else cp.r9_frame()
                    im = extra[(k, t)]
                else:
                    mode = "実時間" if kind == "rt" else "%.1f 倍（%.2f〜%.2f s）" % (cfg["slow_factor"], sa, sb)
                    im = cp.frame(t, mode, "slow" if kind == "slow" else "rt")
                im.save(os.path.join(fd, "%05d.jpg" % i), quality=93)
        # 静止画：t* の主の配置
        cp.frame(p["marks"]["t_star"], "t*").save(os.path.join(out, "frame_tstar.png"))
        if cfg["r9"]:
            cp.r9_frame().save(os.path.join(out, "r9_compare.png"))
    return sch


# ================================================================ encode

def probe_mb(path):
    return os.path.getsize(path) / 1e6


def encode(cfg, p, timer):
    """rt（実時間＋t* で 2 秒止める）・slow（t* の前 3 秒を 0.5 倍＋止める）・both（rt の後に slow）の 3 本。
    どれも H.264（yuv420p、限られた色の範囲）、24 fps。上限（max_mb）を超えたら、上限の 92% に入る平均の速さで 2 回の符号化。"""
    out = cfg["out_dir"]; name = p["name"]
    res = {}
    fr = str(cfg["fps"])
    venc = ["-c:v", "libx264", "-preset", "medium", "-threads", str(cfg["threads"]), "-movflags", "+faststart"]
    vf = "scale=in_range=pc:out_range=tv,format=yuv420p"
    for kind in ("rt", "slow", "both"):
        if kind == "both":
            n = sum(len(os.listdir(os.path.join(out, "frames_" + k))) for k in ("rt", "slow"))
            inp = ["-framerate", fr, "-i", os.path.join(out, "frames_rt", "%05d.jpg"), "-framerate", fr, "-i", os.path.join(out, "frames_slow", "%05d.jpg")]
            filt = ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0," + vf + "[v]", "-map", "[v]"]
        else:
            fd = os.path.join(out, "frames_" + kind)
            n = len(os.listdir(fd))
            inp = ["-framerate", fr, "-i", os.path.join(fd, "%05d.jpg")]
            filt = ["-vf", vf]
        dur = n / cfg["fps"]
        mp = os.path.join(out, "%s_%s.mp4" % (name, kind))
        base = [V.FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + inp + filt + venc
        with timer("encode_" + kind):
            subprocess.run(base + ["-crf", "20", mp], check=True, env=env_g(out), cwd=out)
            mb = probe_mb(mp); how = "crf20"
            if mb > cfg["max_mb"]:
                kbps = int(cfg["max_mb"] * 0.92 * 8e3 / dur)
                pl = os.path.join(out, "_tmp", "x264pass")
                subprocess.run(base + ["-b:v", "%dk" % kbps, "-pass", "1", "-passlogfile", pl, "-an", "-f", "mp4", os.devnull],
                               check=True, env=env_g(out), cwd=out)
                subprocess.run(base + ["-b:v", "%dk" % kbps, "-pass", "2", "-passlogfile", pl, mp], check=True, env=env_g(out), cwd=out)
                mb = probe_mb(mp); how = "2pass %d kbps" % kbps
        res[kind] = {"path": mp.replace("\\", "/"), "frames": n, "seconds": round(dur, 2), "MB": round(mb, 2), "how": how,
                     "within_cap": mb <= cfg["max_mb"]}
        print(kind, res[kind])
    json.dump(res, open(os.path.join(out, "encode.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return res


# ================================================================ turntable

def tt_dir(cfg, p, path):
    res = cfg.get("tt_res", [640, 360])
    extra = [x for x in ([cfg["tt"].get("drop_below_y")] if cfg["tt"].get("drop_below_y") is not None else []) + (["two_sided"] if cfg.get("two_sided") else [])]
    k = rkey(p["tt_cams"], res, cfg["tt"].get("crop")) if not extra else rkey(p["tt_cams"], res, [cfg["tt"].get("crop")] + extra)
    return os.path.join(cfg["out_dir"], "turntable", k + "_" + fkey(p, path))


def turntable(cfg, p, timer):
    out = cfg["out_dir"]
    sp = os.path.join(out, "turntable_R9.png" if cfg.get("tt_res") else "turntable.png")
    pl = p["placement"]
    ts = p["marks"]["t_star"]
    t_, path, si = V.mesh_at([tuple(q) for q in p["timeline"]], cfg.get("turntable_t", ts))
    xf = {"T": pl["T"], "E": pl["E"], "O": pl["O"], "s": pl["scale"], "anchor": pl["anchor"]}
    res = cfg.get("tt_res", [640, 360])
    td = tt_dir(cfg, p, path)
    items = [{"mesh": path, "extra": extra_of(p, path), "xf": xf, "cams": p["tt_cams"], "crop": cfg["tt"].get("crop"),
              "drop_below_y": cfg["tt"].get("drop_below_y"), "out": {c["name"]: os.path.join(td, c["name"] + ".png").replace("\\", "/") for c in p["tt_cams"]}}]
    rd = r9_dir(p["tt_cams"], res)
    if cfg["r9"]:
        items.append({"static": V.R9_MESH, "xf": None, "cams": p["tt_cams"],
                      "out": {c["name"]: os.path.join(rd, c["name"] + ".png").replace("\\", "/") for c in p["tt_cams"]}})
    run_blender({"res": res, "near_clip": cfg["near_clip"], "outer_tint": cfg["outer_tint"], "items": items,
                 "two_sided": bool(cfg.get("two_sided"))}, out, "turntable", timer)
    tw, th = 320, 180
    rows = 4 if cfg["r9"] else 2
    sheet = Image.new("RGB", (6 * tw, 50 + rows * (th + 4)), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    dr.text((8, 6), "%s：回り台 12 方位（向きは見本06 の回り台と同じ。頂のまわりの箱だけ）t = %.2f s。%s" % (p["name"], t_, "1・3 段＝流体、2・4 段＝見本06 R9（比べ、目標ではない）" if cfg["r9"] else "流体"),
            font=F16, fill=(0, 0, 0))
    dr.text((8, 28), p["label"] + "。置き方 ψ=%d°・倍率 %.2f。方位は見本06 の回り台の決め方（0° が原画の側）" % (pl["psi_deg"], pl["scale"]), font=F12, fill=(60, 60, 60))
    for k, c in enumerate(p["tt_cams"]):
        col = k % 6; half = k // 6
        y = 50 + (half * (2 if cfg["r9"] else 1)) * (th + 4)
        im = Image.open(os.path.join(td, c["name"] + ".png")).convert("RGB").resize((tw, th), Image.LANCZOS)
        sheet.paste(im, (col * tw, y))
        tag(dr, (col * tw + 4, y + 4), "%s°" % c["name"][2:].lstrip("0").rjust(1, "0"), F12)
        if cfg["r9"]:
            im = Image.open(os.path.join(rd, c["name"] + ".png")).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (col * tw, y + th + 4))
            tag(dr, (col * tw + 4, y + th + 8), "R9 %s°" % c["name"][2:].lstrip("0").rjust(1, "0"), F12)
    sheet.save(sp)
    if cfg.get("tt_res"):
        # 1920×1080 の一枚（流体だけ、4×3）
        sh = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(sh)
        dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
        dr.text((12, 9), "%s：t* = %.2f s の流体の波を回り台の 12 方位から（粘土・流体だけ）" % (p["name"], t_), font=F22, fill=(255, 255, 255))
        dr.text((12, 52), "%s。方位は見本06 の回り台の決め方（0° が原画の側、270° が左）。頂の足元の %.0f m 上を中心に半径 %.0f m・目の高さ %.0f m。"
                "%s主役の範囲 P3（粒子 0.25 m、粘土色）、外の海は P2（灰青）。" % (
                    cfg.get("physics_label", p["label"]), cfg["tt"]["center_up"], cfg["tt"]["dist"], cfg["tt"]["height"],
                    ("頂のまわりの箱（計算の座標で頂から x %.0f〜%.0f m、z %.0f〜%.0f m）だけ描く。" % (
                        cfg["tt"]["crop"]["x"][0], cfg["tt"]["crop"]["x"][1], cfg["tt"]["crop"]["z"][0], cfg["tt"]["crop"]["z"][1]))
                    if cfg["tt"].get("crop") else "水面は切らずに全部描く。"),
                font=F14, fill=(40, 40, 40))
        W4, H4 = 476, 268
        for k, c in enumerate(p["tt_cams"]):
            col, row = k % 4, k // 4
            x = 4 + col * (W4 + 4); y = 80 + row * (H4 + 64)
            im = Image.open(os.path.join(td, c["name"] + ".png")).convert("RGB").resize((W4, H4), Image.LANCZOS)
            sh.paste(im, (x, y))
            tag(dr, (x + 6, y + 6), "%s°" % (c["name"][2:].lstrip("0") or "0"), F16)
        dr.text((12, FH - 30), "置き方 ψ=%d°・倍率 %.2f（%s）。形の良し悪しを決めるのは利用者。" % (pl["psi_deg"], pl["scale"], pl["source"]),
                font=F14, fill=(60, 60, 60))
        sh.save(os.path.join(out, "turntable.png"))


# ================================================================ 静止画（動き全体のコマの帯、ほかの瞬間の候補）

def strip_sheet(cfg, p, sc):
    """動き全体のコマの帯（1920×1080）：時刻 strip_times の 12 枚 × 2 つの固定カメラ。"""
    cp = Composer(cfg, p, sc)
    ts_ = cfg.get("strip_times") or list(np.linspace(p["t_lo"], p["t_hi"], 12))
    sh = Image.new("RGB", (FW, FH), (244, 243, 239))
    dr = ImageDraw.Draw(sh)
    dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
    dr.text((12, 9), "%s：動き全体のコマの帯（伝わる → 立ち上がる → 巻く）。上＝原画カメラ（青＝原画の輪郭）、下＝左前の斜め" % p["name"],
            font=F22, fill=(255, 255, 255))
    W6, H6 = 318, 179
    names = {v: MARK_JA[k] for k, v in p["marks"].items() if k in MARK_JA and v is not None}
    for blk in range(2):
        for j in range(6):
            k = blk * 6 + j
            if k >= len(ts_):
                break
            t = ts_[k]
            t_, path, si = V.mesh_at(cp.tl, t)
            x = 2 + j * (W6 + 2); y = 56 + blk * (2 * H6 + 92)
            sh.paste(cp.panel(path, "painting", W6, H6, outline=True), (x, y + 26))
            sh.paste(cp.panel(path, "leftfront", W6, H6), (x, y + 28 + H6))
            seg = p["segments"][si]
            lab = "t = %.2f s（コマ %s）" % (t, os.path.basename(path)[5:9])
            dr.text((x + 2, y + 2), lab, font=F16, fill=(0, 0, 0))
            nm = [v for kk, v in names.items() if abs(kk - t) < 0.03]
            sub = ("P3 0.25 m" if si > 0 else "P2 1 m") + ("・" + nm[0] if nm else "")
            tag(dr, (x + 4, y + 30), sub, F12, bg=(255, 235, 200) if nm else (255, 255, 255))
            if (sc.get(path) or {}).get("camera_wet"):
                tag(dr, (x + 4, y + 54), "原画カメラが水の中（%.2f s〜）" % min(v["t"] for v in sc.values() if v.get("camera_wet")), F12,
                    fg=(150, 20, 20), bg=(255, 230, 230))
    dr.text((12, FH - 56), "P2 1 m＝P3 の始まり（%.2f s）より前は粗い計算 P2 R18 の水面だけ。P3 0.25 m＝主役の範囲は細かい計算 P3、その外の海（灰青）は P2 の水面。" % (
        p["marks"].get("switch") or 0), font=F14, fill=(40, 40, 40))
    dr.text((12, FH - 32), "%s。粘土の見た目だけ。カメラは固定（置き方は t* のもの）。" % cfg.get("physics_label", p["label"]), font=F14, fill=(40, 40, 40))
    sh.save(os.path.join(cfg["out_dir"], "strip.png"))


def section_thumb(sec_dir, frame, w, h):
    """z=0 の断面の小さな図：流体の水の形の縁（橙）と粒子（薄い青）、原画の読み A の線（青）。頂を横 0・高さ 20 m にそろえる（p1_figs.compare と同じ）。"""
    import p1_figs as PF
    an = json.load(open(os.path.join(sec_dir, "analysis.json"), encoding="utf8"))
    q = [q for q in an["timeline"] if q["frame"] == frame]
    im = Image.new("RGB", (w, h), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    if not q:
        dr.text((8, 8), "断面なし（コマ %d）" % frame, font=F14, fill=(120, 0, 0))
        return im
    q = q[0]
    cs, d = PF.contour_of(sec_dir, frame, q["crest"][0])
    xc, yc = q["crest"]
    s = 20.0 / yc
    RA = json.load(open(PF.PT, encoding="utf8"))["readings"]["A_side"]
    sc_ = h / 32.0; ox, oy = w * 0.62, h - 6 * sc_
    Pp = lambda x, y: (ox + x * sc_, oy - y * sc_)
    dr.line([Pp(-60, 0), Pp(30, 0)], fill=(170, 170, 170))
    arr = np.array(im)
    m = np.abs(d["x"] - xc) < 60
    px = (ox + (d["x"][m] - xc) * s * sc_).astype(int); py = (oy - d["y"][m] * s * sc_).astype(int)
    k = (px >= 0) & (px < w) & (py >= 0) & (py < h)
    arr[py[k], px[k]] = (205, 220, 238)
    im = Image.fromarray(arr); dr = ImageDraw.Draw(im)
    for c in cs:
        ok = (np.abs(c[:, 0] - xc) < 60) & (c[:, 1] > PF.A.YMIN + 1.0)
        seg = []
        for (u, v), o in zip(c, ok):
            if o:
                seg.append(Pp((u - xc) * s, v * s))
            elif len(seg) > 2:
                dr.line(seg, fill=(230, 120, 20), width=2); seg = []
            else:
                seg = []
        if len(seg) > 2:
            dr.line(seg, fill=(230, 120, 20), width=2)
    for key in ("_outline_outer_xy", "_outline_inner_xy"):
        dr.line([Pp(*pp) for pp in RA[key]], fill=(20, 50, 170), width=2)
    dr.text((4, 2), "z=0 の断面（橙＝流体・青＝原画 読み A、頂を 20 m にそろえた）", font=F12, fill=(60, 60, 60))
    return im


def candidates_sheet(cfg, p, sc):
    """選んだ瞬間 t* とほかの候補 3 つ（利用者が別の瞬間を選べるように）。cfg["candidates"]：[{"t":, "label":, "lines": [..]}]"""
    cands = cfg.get("candidates") or []
    if not cands:
        return
    cp = Composer(cfg, p, sc)
    sh = Image.new("RGB", (FW, FH), (244, 243, 239))
    dr = ImageDraw.Draw(sh)
    dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
    dr.text((12, 9), "%s：いちばん原画に近い瞬間 t* とほかの候補 3 つ（別の瞬間を選ぶための一覧）" % p["name"], font=F22, fill=(255, 255, 255))
    W4, H4 = 476, 268
    for j, c in enumerate(cands[:4]):
        t_, path, si = V.mesh_at(cp.tl, c["t"])
        x = 4 + j * (W4 + 4)
        dr.text((x + 4, 54), c.get("label", "t = %.2f s" % c["t"]), font=F18, fill=(0, 0, 0) if j else (160, 30, 30))
        sh.paste(cp.panel(path, "painting", W4, H4, outline=True), (x, 84))
        sh.paste(cp.panel(path, "leftfront", W4, H4), (x, 84 + H4 + 4))
        y_txt = 84 + 2 * H4 + 14
        if cfg.get("candidates_section_dir"):
            try:
                st = section_thumb(cfg["candidates_section_dir"], int(os.path.basename(path)[5:9]), W4, 200)
                sh.paste(st, (x, 84 + 2 * H4 + 8)); y_txt += 206
            except Exception as e:
                print("section_thumb", repr(e))
        s = sc.get(path) or {}
        lines = list(c.get("lines") or [])
        if s:
            lines.append("原画カメラ（t* の置き方のまま）：IoU %.3f・輪郭 %s px" % (s["iou"], "%.0f" % s["mean_px"] if s.get("mean_px") is not None else "—"))
        for i, l in enumerate(lines):
            dr.text((x + 4, y_txt + i * 22), l, font=F14, fill=(20, 20, 20))
    for i, l in enumerate(cfg.get("candidates_notes") or []):
        dr.text((12, FH - 30 - 24 * (len(cfg.get("candidates_notes")) - 1 - i)), l, font=F14, fill=(60, 60, 60))
    sh.save(os.path.join(cfg["out_dir"], "candidates.png"))



# ================================================================ twin（誘導ありと誘導なしの双子を並べる）

def numbers_compact(cp, dr, x0, y0, path, t):
    s = cp.sc[path]
    lines = ["IoU %.3f　輪郭の平均距離 %s px" % (s["iou"], "%.0f" % s["mean_px"] if s.get("mean_px") is not None else "—"),
             "網目の最高 %.1f m　網目 %s" % (s["crest_y"], os.path.basename(path)[5:9])]
    if s.get("camera_wet"):
        lines.append("注意：原画カメラが水の中に入るコマ")
    t_ = V.mesh_at(cp.tl, t)[0]
    if t - t_ > 0.2:
        lines.append("注意：この時刻の網目がない（%.2f s を保つ）" % t_)
    for i, l in enumerate(lines):
        dr.text((x0, y0 + i * 22), l, font=F14, fill=(150, 30, 30) if l.startswith("注意") else (20, 20, 20))


def twin(cfg_g, cfg_u, timer):
    """左＝誘導あり（cfg_g）、右＝誘導なしの双子（cfg_u）。置き方とカメラは誘導ありの t* のものを両方に使う（同じ水槽の座標なので同じ変換）。
    出力は cfg_g の out_dir の twin_<双子の名前>/。"""
    p_g = plan(cfg_g)
    cfg_g["marks"] = p_g["marks"]
    pl = p_g["placement"]
    cfg_u["placement"] = {"anchor": pl["anchor"], "psi_deg": pl["psi_deg"], "scale": pl["scale"],
                          "source": "双子：%s の置き方" % p_g["name"]}
    cfg_u["marks"] = dict(p_g["marks"], **cfg_u.get("marks", {}))
    cfg_u.setdefault("t_start", p_g["t_lo"]); cfg_u.setdefault("t_end", p_g["t_hi"])
    # 双子の描画は誘導ありの out_dir の下へ（双子だけで作った plan.json の置き方と混ざらないように）
    cfg_u["out_dir"] = os.path.join(cfg_g["out_dir"], "twin_" + cfg_u.get("name", "u"), "u")
    p_u = plan(cfg_u)
    cfg_u["marks"] = p_u["marks"]
    for c, p in ((cfg_g, p_g), (cfg_u, p_u)):
        if not all(os.path.isfile(os.path.join(rdir(c, p), cam["name"], fkey(p, q[1]) + ".png")) for q in p["timeline"] for cam in p["cams"]):
            render(c, p, timer)
    sg, su = scores(cfg_g, p_g, timer), scores(cfg_u, p_u, timer)
    cg, cu = Composer(cfg_g, p_g, sg), Composer(cfg_u, p_u, su)
    td = os.path.dirname(cfg_u["out_dir"])
    os.makedirs(td, exist_ok=True)
    sch = schedule(cfg_g, p_g)

    def frame(t, mode, bar_mode):
        im = Image.new("RGB", (FW, FH), (244, 243, 239))
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
        rt = "t = %.2f s　%s" % (t, mode)
        bb = dr.textbbox((0, 0), rt, font=F18)
        dr.text((FW - 14 - (bb[2] - bb[0]), 11), rt, font=F18, fill=(255, 220, 160))
        hl, hf = fit_text(dr, "双子の比べ　左：%s　右：%s" % (p_g["label"], p_u["label"]), FW - 14 - (bb[2] - bb[0]) - 40, (F18, F16))
        dr.text((12, 11), hl, font=hf, fill=(255, 255, 255))
        for j, (cp, p) in enumerate(((cg, p_g), (cu, p_u))):
            path = V.mesh_at(cp.tl, t)[1]
            x = 960 * j
            if mode.startswith("t*"):
                path = V.mesh_at(cp.tl, p_g["marks"]["t_star"])[1]
            im.paste(cp.panel(path, "painting", 960, 540, outline=True), (x, 44))
            im.paste(cp.panel(path, "leftfront", 480, 270), (x, 588))
            tag(dr, (x + 10, 52), ("左：" if j == 0 else "右：") + p["label"] + "・原画カメラ", F14,
                bg=(255, 225, 225) if j == 0 else (255, 255, 255))
            tag(dr, (x + 6, 594), "左前の斜め", F12)
            tq = p_g["marks"]["t_star"] if mode.startswith("t*") else t
            si_ = [q for q in cp.tl if q[1] == path][0][2]
            g = guide_state(p["segments"][si_], tq)
            tag(dr, (x + 10, 80), g if g else "【物理だけ・誘導なし】", F16, fg=(255, 255, 255),
                bg=((190, 40, 40) if "力 on" in g else (120, 60, 60)) if g else (40, 110, 60))
            numbers_compact(cp, dr, x + 495, 600, path, tq)
        dr.line([960, 44, 960, 860], fill=(255, 255, 255), width=3)
        dr.text((495, 700), "置き方は左の t* のもの（ψ=%d°・倍率 %.2f）を" % (pl["psi_deg"], pl["scale"]), font=F12, fill=(60, 60, 60))
        dr.text((495, 718), "両方に使う。点数は記録だけ（合否に使わない）。", font=F12, fill=(60, 60, 60))
        cg.time_bar(dr, 60, 900, 1800, t, bar_mode)
        return im

    with timer("twin_compose"):
        hold = None
        for kind, seq in sch.items():
            fd = os.path.join(td, "frames_" + kind)
            fresh_frames(fd, len(seq))
            for i, (k, t) in enumerate(seq):
                if k == "h":
                    if hold is None:
                        hold = frame(t, "t* で止める（%.0f 秒）" % cfg_g["hold_s"], "rt")
                        hold.save(os.path.join(td, "twin_hold.png"))
                    im = hold
                else:
                    im = frame(t, "実時間" if kind == "rt" else "%.1f 倍" % cfg_g["slow_factor"], "slow" if kind == "slow" else "rt")
                im.save(os.path.join(fd, "%05d.jpg" % i), quality=93)
    c2 = dict(cfg_g); c2["out_dir"] = td
    return encode(c2, {"name": "twin_" + p_g["name"] + "__" + p_u["name"]}, timer)

# ================================================================ main

def main():
    cmd, cp_ = sys.argv[1], sys.argv[2]
    cfg = V.load_cfg(cp_)
    timer = V.Timer()
    if cmd == "twin":
        t0 = time.time()
        r = twin(cfg, V.load_cfg(sys.argv[3]), timer)
        tm = dict(timer.t); tm["total_s"] = round(time.time() - t0, 1); tm["cmd"] = "twin"
        print("timings", tm)
        return
    tp = os.path.join(cfg["out_dir"], "timings.json")
    t0 = time.time()
    with timer("plan"):
        p = plan(cfg)
    cfg["marks"] = p["marks"]
    if cmd in ("all", "render"):
        render(cfg, p, timer)
    sc = None
    if cmd in ("all", "scores", "compose", "sheets"):
        sc = scores(cfg, p, timer)
    tt_first = "turntable" in (cfg.get("rt_extras") or [])
    if cmd in ("all", "turntable") and cfg["turntable"] and tt_first:
        turntable(cfg, p, timer)      # 実時間の版に回り台を入れるときは、合成の前に描く
    if cmd in ("all", "compose"):
        compose(cfg, p, sc, timer)
    if cmd in ("all", "encode"):
        encode(cfg, p, timer)
    if cmd in ("all", "turntable") and cfg["turntable"] and not tt_first:
        turntable(cfg, p, timer)
    if cmd in ("all", "sheets", "compose"):
        with timer("sheets"):
            strip_sheet(cfg, p, sc)
            candidates_sheet(cfg, p, sc)
    tm = dict(timer.t); tm["total_s"] = round(time.time() - t0, 1); tm["cmd"] = cmd
    tm["meshes"] = len(p["timeline"])
    old = json.load(open(tp, encoding="utf8")) if os.path.isfile(tp) else []
    old.append(tm)
    json.dump(old, open(tp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("timings", tm)


if __name__ == "__main__":
    main()
