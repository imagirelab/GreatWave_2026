# -*- coding: utf-8 -*-
"""FLIP47：論文の図の波の形を、原画と同じ物差し（STUDY52 の measure_mask、Unity/Build/STUDY52/tools/s52_shape.py）で測る。
py -3.10 -B で走らせる（numpy・scipy・PIL）。読むだけ。書くのは Unity/Build/FLIP47/lit/ の中だけ。
2026-10-12 文献と走らせる組の案の役（Claude）が書いた。

測る図（どれも着水の直前、静かな水面 z = 0 から上の η_c で割った値）：
  1. Feddersen・Hanson・Mostert・Fincham 2024（JFM 1000 A48）の図 5（a：Re* 2400 岸へ吹く風、b：風なし、c：Re* −1800 沖へ吹く風）。
     図は線と塗りの絵（vector）。水（水色 0.39,0.82,0.85）と海底（茶 0.76,0.70,0.50）の塗りの多角形を、目盛りの線の位置で x/h0・z/h0 へ直し、
     0.002 h0 の升に塗って和をとる（重なりの境で細い筋が出るので XOR ではなく OR）。
     軸：x 38 h0 が 138.3 pt、43 h0 が 369.5 pt。z は各図の z = 0 の目盛り（568.4・442.4・316.5 pt）から 0.5 h0 ごとに 15.84 pt。
  2. Pick & Feddersen 2026（JFM 1040 A8）の図 5（4 つ：a 1/15・H0/h0 0.2、b 1/30・0.2、c 1/15・0.6、d 1/30・0.6）と図 6a（1/30・0.6 の崩れ始め）。
     図は画像（高い解像度の PDF の中の JPEG）。水（青）・海底（茶）・線（黒）を水とし、線の太さの半分（6 画素、図 6a は 5 画素）だけ削る。
     軸：図 5 は縦横同じ 1620.8 画素/h0（x の目盛り 0.4 h0 ごとに 648.3 画素、z の目盛り 0.5 h0 ごとに 811 画素で確かめた）、
     z = 0 は点線の中心（上の段 1304.5、下の段 3825 画素）。図 6a は x 1906 画素/h0、z 2575 画素/h0（縦が 1.35 倍。目盛りで確かめた）、z = 0 は 2068 画素。
入力：論文の PDF（出版社の公開の版。リポジトリには置かない）。既定はこの会話で読んだ時の置き場所。
  --f24 <Feddersen_etal2024JFM.pdf>  --pf <Pick&Feddersen 2026 の高い解像度の PDF（_hi.pdf）>
確かめ：測った η_c が論文の値と合うか（F24：Hb/h0 0.676・0.64・0.627、P&F：図 5d の H_I/h0 0.707、図 6a の H_b/h0 0.749）を json に書く。
"""
import os, sys, re, json, zlib, argparse
sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Unity/Build/STUDY52/tools")
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import s52_shape as S52

OUT = REPO + "/Unity/Build/FLIP47/lit"
TR = os.environ.get("GW_LIT_PDF_DIR", "") + "/"  # 論文の PDF を置いたローカルの置き場所（リポジトリに入れない）
DEF_F24 = TR + "webfetch-1791803482650-rj5ykn.pdf"
DEF_PF = TR + "webfetch-1791803925654-hdsem0.pdf"
KEEP = ["eta_c", "face_chord_deg_01_05", "front_x01_rel", "front_x05_rel", "steep45_frac", "steep60_frac", "gap_max", "gap_under_tip",
        "lip_thick_mid", "hood_area", "hood_height", "reach", "tip_z", "hood_low_z", "hood_wall_x_rel"]
Image.MAX_IMAGE_PIXELS = None


def pick(m):
    return {k: (float(m[k]) if isinstance(m.get(k), (int, float, np.floating, bool, np.bool_)) else None) for k in KEEP}


def pdf_objs(path):
    data = open(path, "rb").read()
    return {int(m.group(1)): m.group(2) for m in re.finditer(rb"(\d+) 0 obj(.*?)endobj", data, re.S)}


def stream(body, inflate=True):
    s = body.find(b"stream") + 6
    s += 2 if body[s:s + 2] == b"\r\n" else 1
    e = body.rfind(b"endstream")
    raw = body[s:e]
    return zlib.decompressobj().decompress(raw) if inflate else raw


# ------------------------------------------------------------------ Feddersen ら 2024 図 5（線と塗りの絵）
def f24_paths(objs, content_obj=609):
    d = stream(objs[content_obj])
    tok = re.compile(rb"\((?:\x5c.|[^\x5c)])*\)|\[|\]|<<|>>|<[0-9A-Fa-f\s]*>|/[^\s/\[\]()<>]+|[-+]?\d*\.?\d+|[A-Za-z'\"*]+[0-9]*\*?")
    ops, st = [], []
    for m in tok.finditer(d):
        t = m.group(0)
        if re.fullmatch(rb"[-+]?\d*\.?\d+", t):
            st.append(float(t))
        elif t[:1] in (b"/", b"(", b"<") or t in (b"[", b"]"):
            st.append(t)
        else:
            ops.append((t.decode("latin-1"), st)); st = []
    ctm = np.eye(3); gs = []; fill = (0, 0, 0); cur = []; path = []; out = []

    def tr(x, y):
        p = np.array([x, y, 1.0]) @ ctm
        return (float(p[0]), float(p[1]))
    for op, a in ops:
        if op == "q":
            gs.append((ctm.copy(), fill))
        elif op == "Q":
            ctm, fill = gs.pop()
        elif op == "cm":
            ctm = np.array([[a[-6], a[-5], 0], [a[-4], a[-3], 0], [a[-2], a[-1], 1.0]]) @ ctm
        elif op == "rg":
            fill = tuple(a[-3:])
        elif op == "g":
            fill = (a[-1],) * 3
        elif op in ("sc", "scn"):
            n = [v for v in a if isinstance(v, float)]
            if len(n) == 3:
                fill = tuple(n)
        elif op == "m":
            if cur: path.append(cur)
            cur = [tr(*a[-2:])]
        elif op in ("l", "c", "v", "y"):
            cur.append(tr(*a[-2:]))
        elif op == "h":
            if cur: cur.append(cur[0])
        elif op == "re":
            x, y, w, h = a[-4:]
            if cur: path.append(cur)
            cur = [tr(x, y), tr(x + w, y), tr(x + w, y + h), tr(x, y + h), tr(x, y)]
        elif op in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"):
            if cur: path.append(cur)
            if op in ("f", "F", "f*"):
                for p in path:
                    out.append((tuple(round(c, 2) for c in fill), p))
            path = []; cur = []
    return out


def f24_measure(pdf):
    objs = pdf_objs(pdf)
    paths = f24_paths(objs)
    AQUA, BROWN = (0.39, 0.82, 0.85), (0.76, 0.7, 0.5)
    X0, X1 = 138.3, 369.5
    sx = (X1 - X0) / 5.0; sz = 15.84 / 0.5; FINE = 0.002
    panels = {"F24_fig5a_Re2400_t19.13": (568.4, 0.676), "F24_fig5b_Re0_t19.96": (442.4, 0.64), "F24_fig5c_Re-1800_t20.22": (316.5, 0.627)}
    res = {}
    for name, (y0, hb) in panels.items():
        sel = [(c, p) for c, p in paths if c in (AQUA, BROWN) and min(q[1] for q in p) >= y0 - 34 and max(q[1] for q in p) <= y0 + 60 and len(p) >= 3]
        xs = np.arange(38.0, 43.0, FINE) + 0.5 * FINE
        zs = np.arange(-1.0, 1.4, FINE) + 0.5 * FINE
        acc = np.zeros((len(zs), len(xs)), bool)
        for c, p in sel:
            img = Image.new("L", (len(xs), len(zs)), 0)
            ImageDraw.Draw(img).polygon([((38.0 + (px - X0) / sx - 38.0) / FINE, (1.4 - (py - y0) / sz) / FINE) for px, py in p], fill=1)
            acc |= np.asarray(img)[::-1].astype(bool)
        Image.fromarray((acc[::-1] * 255).astype(np.uint8)).save(OUT + "/%s.png" % name)
        m = pick(S52.measure_mask(acc, xs, zs))
        m.update(paper_Hb_over_h0=hb, eta_c_over_h0=m["eta_c"], units="x/h0, z/h0")
        res[name] = m
    return res


# ------------------------------------------------------------------ Pick & Feddersen 2026 図 5・6a（画像）
def pf_images(pdf):
    objs = pdf_objs(pdf)
    ims = {}
    for k, b in objs.items():
        h = b[:400]
        if b"/Subtype /Image" in h and b"/DCTDecode" in h:
            w = int(re.search(rb"/Width (\d+)", h).group(1)); hh = int(re.search(rb"/Height (\d+)", h).group(1))
            ims[(w, hh)] = stream(b, inflate=False)
    return ims


def water_mask(A, half):
    r, g, b = A[..., 0], A[..., 1], A[..., 2]
    M = (b > r + 50) | ((r > b + 20) & (r > 100)) | ((r < 80) & (g < 80) & (b < 80))
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1]
    M = ndimage.binary_erosion(M, structure=(xx * xx + yy * yy) <= half * half)
    M = ndimage.binary_opening(M, structure=np.ones((3, 3), bool))
    lab, n = ndimage.label(M)
    bot = lab[-1][lab[-1] > 0]
    if len(bot):
        M = lab == np.bincount(bot).argmax()
    return M


def pf_one(A, z0_row, px_x, px_z, name, half=6):
    M = water_mask(A, half)
    H, W = M.shape
    X = (np.arange(W) + 0.5) / px_x
    Z = (z0_row - (H - 1 - np.arange(H))) / px_z
    Image.fromarray((M * 255).astype(np.uint8)).resize((W // 4, H // 4)).save(OUT + "/%s.png" % name)
    m = pick(S52.measure_mask(M[::-1], X, Z))
    m.update(eta_c_over_h0=m["eta_c"], units="x/h0, z/h0")
    return m


def pf_measure(pdf):
    import io
    ims = pf_images(pdf)
    res = {}
    A = np.asarray(Image.open(io.BytesIO(ims[(5101, 4645)])).convert("RGB")).astype(int)
    pxh = 648.3 / 0.4
    panels = {"PF_fig5a_s1-15_H0.2_impact_on_flat": (11, 2116, 17, 2280, 1304.5, None),
              "PF_fig5b_s1-30_H0.2": (11, 2116, 2826, 5090, 1304.5, None),
              "PF_fig5c_s1-15_H0.6": (2531, 4637, 17, 2280, 3825.0, None),
              "PF_fig5d_s1-30_H0.6": (2531, 4637, 2826, 5090, 3825.0, 0.707)}
    for name, (r0, r1, c0, c1, zr, hi) in panels.items():
        m = pf_one(A[r0:r1, c0:c1], zr - r0, pxh, pxh, name)
        if hi:
            m["paper_HI_over_h0"] = hi
        res[name] = m
    B = np.asarray(Image.open(io.BytesIO(ims[(5296, 5020)])).convert("RGB")).astype(int)
    m = pf_one(B[13:2325, 15:5279], 2068 - 13, 953.0 / 0.5, 515.0 / 0.2, "PF_fig6a_s1-30_H0.6_break_onset", half=5)
    m["paper_Hb_over_h0"] = 0.749
    res["PF_fig6a_s1-30_H0.6_break_onset"] = m
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f24", default=DEF_F24)
    ap.add_argument("--pf", default=DEF_PF)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    res = dict(note_ja="論文の図の形を STUDY52 の measure_mask で測った値。長さ・高さは η_c（静かな水面から頂）で割った値、角は度。"
                       "eta_c_over_h0 は η_c ÷ h0。図の線の太さ・画素で ±0.01 h0 ほどの誤差がある。g47_lit_ruler.py",
               inputs=dict(f24=os.path.basename(a.f24), pf=os.path.basename(a.pf)))
    res.update(f24_measure(a.f24))
    res.update(pf_measure(a.pf))
    json.dump(res, open(OUT + "/lit_ruler.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for k, v in res.items():
        if isinstance(v, dict) and "eta_c" in v:
            print(k, {kk: round(vv, 3) for kk, vv in v.items() if isinstance(vv, float) and kk in
                      ("eta_c", "face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area", "reach", "tip_z")})


if __name__ == "__main__":
    main()
