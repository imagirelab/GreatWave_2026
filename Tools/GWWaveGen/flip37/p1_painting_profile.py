# -*- coding: utf-8 -*-
"""P1：原画の大波を「断面」として読み、頂の高さを 20 m にそろえた輪郭と、比べる値を出す（py -3.10、numpy・PIL）。

読み方（記録に書くこと）：
- 原画の輪郭は、リポジトリの真値 Tools/PaintingTruth/targets/main_wave_outline_envelope.json（表示 1920×1080 の画素。
  区間 78→130→131→132 が外側の輪郭で、132 の終わりが唇の先、72 が唇の先から内側の壁を通って前の面の下（y=735）までの内側の輪郭）。
  envelope 版（爪の指を閉じてなだらかにした版）を使う。爪の指（claws 版）は唇の細部なので断面の比べには使わない。
- 原画カメラ PaintingCam v1（位置 (0,3,-62)、注視点 (-2.5,9.7,4.0)、縦の画角 26°、Unity の座標）で、各画素の光線を縦の平面へ当てる。
  読み A（主）：横から見た断面。カメラの水平の向きに垂直な縦の平面（波が画面の右へ進むと読む。描かれた横の長さをそのまま使う）。
  読み B（参考）：見本06 の立体の読みでの進む向き T=(0.733,0,-0.680)（画面に対して約 43° 手前へ進む）を含む縦の平面（R9 の主の断面 c=-0.8）。
  どちらも、平面までの距離（=倍率）を、頂の高さが静かな水面 y=0 から 20 m になるように決める（頂の高さ 20 m は指示の値）。
  静かな水面 y=0 は、カメラの高さ 3 m から決まる（平面までの距離とともに画面の中の位置が変わる）。
- 読み B では、外側の輪郭の左の部分（78・130・131）は峰に沿う高さの変化（S4「背は一つの山」）を斜めから見たもので、
  断面の背ではない。背の傾きは読み A だけで出す。
出力：Unity/Build/FLIP37/P1/painting/painting_section.json と painting_section.png
"""
import json, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = r"G:/Unity/GreatWave_2026_Fresh"
OUTD = REPO + "/Unity/Build/FLIP37/P1/painting"
os.makedirs(OUTD, exist_ok=True)
SRC = REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
HC = 20.0
CAM_POS = np.array([0.0, 3.0, -62.0]); CAM_TGT = np.array([-2.5, 9.7, 4.0]); VFOV = 26.0; WD, HD = 1920, 1080
UP = np.array([0.0, 1.0, 0.0])
T_SEC = np.array([0.7333652004044829, 0.0, -0.6798348938056156])  # kh_common.T（見本06 の断面の進む向き）
E_SEC = np.array([0.6798348938056157, 0.0, 0.733365200404483])
O_SEC = np.array([-7.227685896240013, 0.0, -2.7131699203121187])


def cam():
    f = CAM_TGT - CAM_POS; f /= np.linalg.norm(f)
    r = np.cross(UP, f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return r, u, f


def rays(px):
    r, u, f = cam()
    t = math.tan(math.radians(VFOV) / 2); asp = WD / HD
    vx = (px[:, 0] + 0.5) / WD; vy = 1.0 - (px[:, 1] + 0.5) / HD
    cx = (2 * vx - 1) * t * asp; cy = (2 * vy - 1) * t
    return cx[:, None] * r + cy[:, None] * u + f


def plane_hit(d, n, p0):
    s = ((p0 - CAM_POS) @ n) / (d @ n)
    return CAM_POS + s[:, None] * d


def read_A(px):
    """横から見た断面：法線 = カメラの水平の向き。距離 D は後で頂 20 m に合わせる。戻り：(D=1 の時の) 横 h・高さ y の関数。"""
    r, u, f = cam()
    fh = np.array([f[0], 0, f[2]]); fh /= np.linalg.norm(fh)
    rh = np.cross(UP, fh); rh /= np.linalg.norm(rh)
    d = rays(px)
    q = d / (d @ fh)[:, None]   # D=1 の平面上の点 - CAM_POS
    return q @ rh, q[:, 1]      # 横、縦（D をかけるとメートル。縦は CAM_POS.y を足す）


def read_B(px, c):
    d = rays(px)
    P = plane_hit(d, E_SEC, O_SEC + c * E_SEC)
    Q = P - O_SEC
    return Q @ T_SEC, P[:, 1]


def main():
    src = json.load(open(SRC, encoding="utf8"))
    segs = {s["id"]: np.array(s["points_display"], float) for s in src["segments"]}
    outer = np.concatenate([segs["78"], segs["130"][1:], segs["131"][1:], segs["132"][1:]])
    inner = segs["72"]
    allpx = np.concatenate([outer, inner[1:]])
    n_outer = len(outer)
    res = {"source": "Tools/PaintingTruth/targets/main_wave_outline_envelope.json",
           "source_sha256": __import__("hashlib").sha256(open(SRC, "rb").read()).hexdigest(),
           "reference_image": src["reference_path"], "reference_sha256": src["reference_sha256"],
           "painting_cam": src["painting_cam"], "crest_height_m": HC, "readings": {}}
    for name in ("A_side", "B_sample06_plane"):
        if name == "A_side":
            hx, hy = read_A(allpx)
            ic = int(np.argmax(-allpx[:n_outer, 1]))   # 画面で一番上の点＝頂
            D = (HC - CAM_POS[1]) / hy[ic]
            X = hx * D; Y = CAM_POS[1] + hy * D
            note = "平面までの距離 D = %.2f m（カメラから水平に）" % D
            extra = {"plane_distance_m": round(float(D), 3)}
        else:
            X, Y = read_B(allpx, -0.8)
            ic = int(np.argmax(-allpx[:n_outer, 1]))
            s = HC / Y[ic]
            X = X * s; Y = Y * s
            note = "R9 の主の断面 c=-0.8 の平面に当てた後、頂を 20 m にそろえる倍率 %.4f をかけた" % s
            extra = {"scale_to_20m": round(float(s), 4)}
        X = X - X[ic]   # 頂を横 0 に
        ox, oy = X[:n_outer], Y[:n_outer]
        ix, iy = X[n_outer - 1:], Y[n_outer - 1:]   # 内側（唇の先から）
        tip = np.array([ox[-1], oy[-1]])
        crest = np.array([ox[ic], oy[ic]])
        iw = int(np.argmin(ix))                  # 内側の壁の一番後ろ
        wall = np.array([ix[iw], iy[iw]])
        foot = np.array([ix[-1], iy[-1]])        # 前の面の下の端（手前の小波に隠れる所）
        # 前の面：内側の壁から下の端まで。弦からのふくらみ（正＝凹：面が弦より後ろ＝波の側へ入る）
        fx, fy = ix[iw:], iy[iw:]
        ch = foot - wall; chn = ch / np.linalg.norm(ch); nrm = np.array([-chn[1], chn[0]])  # 弦の左手の法線
        sag = (np.stack([fx, fy], -1) - wall) @ nrm
        # 弦の向きは右下がり。左手の法線は (−dy, dx) 系で、上・右を向く。凹（後ろ＝左上へ入る）は負になる向きなので符号を合わせる
        concave = float(-sag.min()) if (-sag).max() > 0 else 0.0
        face_angle = math.degrees(math.atan2(wall[1] - foot[1], foot[0] - wall[0]))
        # 前の面の傾き（中ほど 25–75 % の高さ）
        # 背（読み A だけ）：頂より後ろの外側の輪郭で 0.25 Hc と 0.75 Hc を通る所
        back = {}
        if name == "A_side":
            bx, by = ox[:ic + 1], oy[:ic + 1]
            def xat(level):
                k = np.where((by[:-1] < level) & (by[1:] >= level))[0]
                if len(k) == 0:
                    return None
                k = k[-1]; w = (level - by[k]) / (by[k + 1] - by[k])
                return float(bx[k] + w * (bx[k + 1] - bx[k]))
            x25, x75 = xat(0.25 * HC), xat(0.75 * HC)
            back = {"x_at_0.25Hc": x25, "x_at_0.75Hc": x75,
                    "back_slope_deg_25_75": (math.degrees(math.atan2(0.5 * HC, x75 - x25)) if (x25 is not None and x75 is not None) else None),
                    "outline_left_end": [float(ox[0]), float(oy[0])],
                    "note_ja": "左の端（区間 78 の始まり）は y=%.1f m で、画面の左の端で切れている（背の足元は見えない）" % oy[0]}
        reach = float(tip[0] - crest[0]); drop = float(crest[1] - tip[1])
        overhang = float(tip[0] - wall[0])
        tube_h = float(tip[1] - foot[1])
        m = {
            "note_ja": note, **extra,
            "crest": crest.round(3).tolist(), "lip_tip": tip.round(3).tolist(), "inner_wall": wall.round(3).tolist(),
            "face_foot": foot.round(3).tolist(),
            "lip_reach_m": round(reach, 3), "lip_drop_m": round(drop, 3),
            "reach_over_Hc": round(reach / HC, 3), "drop_over_Hc": round(drop / HC, 3),
            "tip_height_over_Hc": round(float(tip[1]) / HC, 3),
            "overhang_m": round(overhang, 3), "overhang_over_Hc": round(overhang / HC, 3),
            "wall_behind_crest_m": round(float(crest[0] - wall[0]), 3),
            "tube_width_m": round(overhang, 3), "tube_height_tip_to_foot_m": round(tube_h, 3),
            "tube_aspect_w_over_h": round(overhang / tube_h, 3) if tube_h > 0 else None,
            "front_face_chord_angle_deg": round(face_angle, 2),
            "front_face_concavity_m": round(concave, 3), "front_face_concavity_over_Hc": round(concave / HC, 3),
            "foot_height_m": round(float(foot[1]), 3),
            "back": back,
        }
        res["readings"][name] = m
        res["readings"][name]["_outline_outer_xy"] = np.stack([ox, oy], -1).round(3).tolist()
        res["readings"][name]["_outline_inner_xy"] = np.stack([ix, iy], -1).round(3).tolist()
    json.dump(res, open(OUTD + "/painting_section.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 図
    img = Image.new("RGB", (1600, 900), (255, 255, 255)); dr = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 20); fs = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 15)
    except Exception:
        fnt = fs = ImageFont.load_default()
    for k, (name, col) in enumerate((("A_side", (20, 60, 160)), ("B_sample06_plane", (200, 80, 20)))):
        m = res["readings"][name]
        x0 = 40 + k * 780; y0 = 60; sc = 9.0
        def P(x, y):
            return (x0 + 480 + x * sc, y0 + 560 - y * sc)
        dr.text((x0, 20), {"A_side": "読み A（横から見た断面、主）", "B_sample06_plane": "読み B（見本06 の進む向きの平面、参考）"}[name], fill=(0, 0, 0), font=fnt)
        dr.line([P(-50, 0), P(30, 0)], fill=(150, 150, 150), width=1)
        dr.text(P(-50, 0.8), "静かな水面 y=0", fill=(120, 120, 120), font=fs)
        for yy in range(0, 25, 5):
            dr.line([P(-50, yy), P(-49, yy)], fill=(0, 0, 0)); dr.text((P(-50, yy)[0] - 30, P(-50, yy)[1] - 8), "%d" % yy, fill=(0, 0, 0), font=fs)
        o = m["_outline_outer_xy"]; i = m["_outline_inner_xy"]
        dr.line([P(*q) for q in o], fill=col, width=3)
        dr.line([P(*q) for q in i], fill=col, width=3)
        for lab, key in (("頂", "crest"), ("唇の先", "lip_tip"), ("内側の壁", "inner_wall"), ("前の面の下", "face_foot")):
            q = P(*m[key]); dr.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], outline=(0, 0, 0), width=2)
            dr.text((q[0] + 6, q[1] - 22), lab, fill=(0, 0, 0), font=fs)
        txt = ["唇の届き %.1f m（%.2f Hc）・落ち %.1f m（%.2f Hc）" % (m["lip_reach_m"], m["reach_over_Hc"], m["lip_drop_m"], m["drop_over_Hc"]),
               "唇のかぶり（内側の壁→唇の先）%.1f m（%.2f Hc）" % (m["overhang_m"], m["overhang_over_Hc"]),
               "空洞の幅/高さ %.2f（高さ＝唇の先→前の面の下）" % (m["tube_aspect_w_over_h"] or float('nan')),
               "前の面の弦の角度 %.0f°・凹み %.1f m" % (m["front_face_chord_angle_deg"], m["front_face_concavity_m"])]
        if m["back"]:
            b = m["back"]
            txt.append("背：0.75 Hc の所は頂の %.1f m 後ろ。0.25 Hc は %s" % (-(b["x_at_0.75Hc"] or 0), ("頂の %.1f m 後ろ・傾き %.0f°" % (-b["x_at_0.25Hc"], b["back_slope_deg_25_75"])) if b["x_at_0.25Hc"] is not None else "画面の左で切れて届かない（左の端の高さ %.1f m）" % b["outline_left_end"][1]))
        for j, tx in enumerate(txt):
            dr.text((x0, 650 + j * 26), tx, fill=(0, 0, 0), font=fs)
    img.save(OUTD + "/painting_section.png")
    for name in res["readings"]:
        mm = {k: v for k, v in res["readings"][name].items() if not k.startswith("_")}
        print(name, json.dumps(mm, ensure_ascii=False))


if __name__ == "__main__":
    main()
