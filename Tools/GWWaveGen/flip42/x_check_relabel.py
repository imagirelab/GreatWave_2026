# -*- coding: utf-8 -*-
"""FLIP42：_v2（印の字だけを直した版）が、元の版と字のほかで同じかを、符号化の前のコマで確かめる。2026-10-10。
- 動画 2 本：描く関数（g_preview.side・g_video.main）を元の字と新しい字で 2 回ずつ走らせ、選んだコマ（約 40）の
  符号化の前の画素を比べる。違う画素の外接の四角を出す（字の所だけなら、四角は印の字の位置に収まる）。
  コマを選ぶため Data のコマの一覧だけを間引く（各コマの描き方・番号・時刻は全部描く時と同じ）。
- 断面の並び：preview/R2_first_strip.png と preview/R2_first_strip_v2.png を画素で比べる。
出力：<FLIP42>/preview/relabel_check.json
使い方：py -3.10 -B x_check_relabel.py <FLIP42 のフォルダー>
"""
import sys, os, json
import numpy as np
from PIL import Image

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_preview as G
import g_video as V
import g_relabel_v2 as RL

OLD_G = dict(G.LAB); OLD_V = dict(V.LAB)


class Cap:
    """V.encode の代わり。符号化せず、書かれたコマの画素を持つ。"""
    def __init__(self):
        self.frames = []
        self.stdin = self

    def write(self, b):
        self.frames.append(np.frombuffer(b, np.uint8).reshape(V.H, V.W, 3).copy())

    def close(self):
        pass

    def wait(self):
        pass


def sample(frames, extra_t):
    fr = [int(f) for f in frames]
    keep = set(fr[::max(1, len(fr) // 30)]) | {fr[0], fr[-1]}
    for t in extra_t:
        f = int(round(t * 24)) + 1
        keep |= {f - 1, f, f + 1}
    return np.array(sorted(f for f in fr if f in keep))


def patch(cls, extra_t):
    class Sub(cls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.D = dict(self.D)
            self.D["frames"] = sample(self.D["frames"], extra_t)
    return Sub


def run_capture(fn, lab_g, lab_v):
    G.LAB.clear(); G.LAB.update(lab_g); V.LAB.clear(); V.LAB.update(lab_v)
    caps = []
    def enc(path, fps):
        c = Cap(); caps.append((os.path.basename(path), c)); return c
    old_enc = V.encode
    V.encode = enc
    try:
        fn()
    finally:
        V.encode = old_enc
    return caps


def diff_boxes(a, b):
    d = np.any(a != b, axis=2)
    n = int(d.sum())
    if n == 0:
        return dict(n_px=0, box=None)
    ys, xs = np.nonzero(d)
    # 行の帯ごとに分けて外接の四角（字の行が離れているので）
    rows = np.unique(ys)
    bands, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r > prev + 6:
            bands.append((start, prev)); start = r
        prev = r
    bands.append((start, prev))
    out = []
    for y0, y1 in bands:
        m = (ys >= y0) & (ys <= y1)
        out.append([int(xs[m].min()), int(y0), int(xs[m].max()), int(y1)])
    return dict(n_px=n, boxes=out)


def compare(name, caps_old, caps_new):
    res = []
    for (fo, co), (fn_, cn) in zip(caps_old, caps_new):
        assert fo == fn_ and len(co.frames) == len(cn.frames), (fo, len(co.frames), len(cn.frames))
        per = [diff_boxes(a, b) for a, b in zip(co.frames, cn.frames)]
        allbox = None
        for p in per:
            for bx in p.get("boxes") or []:
                allbox = bx if allbox is None else [min(allbox[0], bx[0]), min(allbox[1], bx[1]), max(allbox[2], bx[2]), max(allbox[3], bx[3])]
        bands = sorted({tuple(bx[1::2]) for p in per for bx in (p.get("boxes") or [])})
        res.append(dict(stream=fo, frames_compared=len(per), frames_with_diff=sum(1 for p in per if p["n_px"]),
                        max_px_changed=max(p["n_px"] for p in per), union_box_x0y0x1y1=allbox,
                        row_bands_y=[list(b) for b in bands][:20]))
    return dict(video=name, streams=res)


if __name__ == "__main__":
    base = sys.argv[1]
    sd = json.load(open(os.path.join(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs", "R3", "shape.json"), encoding="utf8"))
    ev = [sd["onset"]["t"], sd["touchdown"]["t"], 157.04, 159.3, 171.5]
    out = {"schema": "GreatWave.FLIP42.relabel_check/1", "date": "2026-10-10",
           "note_ja": "元の字と新しい字で同じ関数を走らせ、符号化の前のコマの画素を比べた。box は違う画素の外接の四角（画素、左上が 0）。"
                      "字のほかが同じなら、違いは印の字の行（場所の印は窓の上の端、時刻の印は下の時間の帯）にだけ出る",
           "labels_old": {"g_preview": OLD_G, "g_video": OLD_V}, "labels_new": {"g_preview": RL.NEW_G, "g_video": RL.NEW_V}}
    G.Data2 = patch(G.Data2, ev)
    side = lambda: G.side("R3", "unused.mp4", None, "")
    o = run_capture(side, OLD_G, OLD_V); n = run_capture(side, RL.NEW_G, RL.NEW_V)
    out["side"] = compare("R2_first_side", o, n)
    del o, n
    V.Data = patch(V.Data, ev)
    def crest():
        sys.argv = ["g_video.py", "R3", os.path.join(base, "R2", "video_v2"), "--label=" + RL.CREST_LABEL, "--only=crest"]
        V.main()
    o = run_capture(crest, OLD_G, OLD_V); n = run_capture(crest, RL.NEW_G, RL.NEW_V)
    out["crest"] = compare("R3_crest / R2_side_finest", o, n)
    del o, n
    a = np.asarray(Image.open(os.path.join(base, "preview", "R2_first_strip.png")).convert("RGB"))
    b = np.asarray(Image.open(os.path.join(base, "preview", "R2_first_strip_v2.png")).convert("RGB"))
    out["strip"] = dict(same_size=a.shape == b.shape, **(diff_boxes(a, b) if a.shape == b.shape else {}))
    G.LAB.clear(); G.LAB.update(OLD_G); V.LAB.clear(); V.LAB.update(OLD_V)
    p = os.path.join(base, "preview", "relabel_check.json")
    json.dump(out, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
