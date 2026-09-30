# -*- coding: utf-8 -*-
"""設計44：Unity の記録から、動画（1920×1080、30 fps）・図・静止画・metrics.json・run.json を作る（numpy・OpenCV・ffmpeg。グラフも OpenCV で描く）。

動画：左上 = 追う視点（Unity の描画）、右上 = 真上の地図（Unity の描画に、範囲・帯・原画の位置・通った跡・固定の軌道を重ねる）、
      左下 = 横から見た全体（Unity の描画）、右下 = 時系列（速さ・向き・入力・範囲の距離）と今の時刻の線。
重ねた線と文字は記録の数値から描いたもので、Unity の描画ではない（動画の中に注記）。
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds44_model as M  # noqa: E402
import ds44_measure as DM  # noqa: E402


OUT = M.OUT
UNITY = os.path.join(OUT, "unity")
FRAMES = os.path.join(UNITY, "frames")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
REPO = M.REPO
W, H = 960, 540

LABEL_EN = {
    "前進（W）：加速": "forward (W): accelerate",
    "入力なし：抵抗で減速": "no input: drag slows the boat",
    "前進＋右旋回（W＋D）": "forward + turn right (W+D)",
    "停止（Space）": "stop (Space)",
    "入力なし": "no input",
    "左旋回（左スティック ←）": "turn left at rest (gamepad left stick <-)",
    "前進（R2）：範囲の縁へ": "forward (gamepad R2) toward the range edge",
    "入力なし：押し戻し": "no input: soft push-back",
    "減速・後進（L2）": "slow down / reverse (gamepad L2)",
    "前進＋右（左スティック ↗）": "forward + right (gamepad left stick /)",
}


DECISIONS_JA = [
    "D44-1（Q24、進行役の判断）：操船の範囲は painting frame（原点 = 原画の座席の船の根の xz、u = 原画の船首の向き、v = 右舷）の角を丸めた長方形 u −85〜−25 m・v ±25 m・角の半径 10 m。"
    "設計15 の候補範囲（M1 の世界の X 17〜31・Z −22〜−3 m、painting frame で u −24〜−10）は M1 の波のための座標なので、設計15 の規則（主役波の投影の外に船の半径＋余白、観賞の位置へ導く）を今の世界で当て直した。"
    "前の縁を −10 m でなく −25 m にしたのは、D26 の引き継ぎの道（15 s 以上で原画の位置へ速さ 0 で着く）の格子の試し（750 の状態）（ds44_grid.py、ds44_trajectory_grid.json）で、−10 m では 66 件が原画の位置の前へ 2 m を超えて出て最大 19.8 m、首振り 15°/s 超 16 件だったのに対し、−25 m では 10 件・最大 4.4 m、2 件だったから。"
    "t* の主役波の投影（y > 0.5 m、u ≥ +5.8 m）から 30.8 m 以上離れる。地図には設計15 の箱を灰色で参考に描いた（範囲には含めない）",
    "D44-2：形成（単発再生の t = 0）の始まりは引き継ぎが決める（s_f = s_h + T − 12 s、T は軌道の所要。最短 15 s）。t* でちょうど原画の位置に速さ 0 で着き、速さ・加速度・首振りの上限を守るため。引き継ぎの時刻（接近の終わり）は設計47 の出来事の表が決める。試験では s_h = 70 s",
    "D44-3：範囲の外の押し戻しは平行移動だけ（外向きの推力を弱め、内向きの加速度と外向きの速度の減衰）。船首を勝手に回さない（設計書 §7.3「HMDの頭を勝手に回さず」、快適性）",
    "D44-4：固定の軌道の間は、物理の段ごとに水平の位置と首の向きを軌道の値へ合わせる（高さ・横揺れ・縦揺れは浮力のまま）。run1 の速度の帰還だけの版は、形成の終わりに波が船を大きく傾けた所（傾き最大 64°）で t* のずれが 0.14 m・5.6°、保持の間に最大 0.27 m・15° になったため（修正 1 回目）",
    "D44-5：操船の数値（最高速 2.4 m/s、抵抗、首振り 10°/s など）は調整値で、資料の値ではない。軌道の上限（速さ 2.2 m/s、加速 0.3・減速 0.6 m/s²、首振り 10°/s）も同じ",
    "D44-6：入力の確かめは Input System の仮想のキーボードとゲームパッド（InputState.Change）で行い、実際の機器と同じ読み方（DS44Input.Read）で読んだ。手で押す確かめと PS VR2 の Sense は保留（利用者の手）",
    "D44-7：跳びの判定は 1 段（1/120 s）の変化が物理の上限の 1.5 倍（向き 0.125°、速さ 0.0125 m/s）を超えること。着いた時の目安（≤ 5 cm・≤ 0.5°・≤ 0.05 m/s）も進行役が決めた",
]

LIMITS_JA = [
    "軌道の首振りの速さは最大 14.0°/s（計画の上限 10°/s を、引き継ぎの時の首振りの差をなめらかに戻す分だけ越えた）。格子の試し（750 の状態）では p95 10.1°/s・最大 17.0°/s、10/750 件が原画の位置の前へ最大 4.4 m 出る。所要 T は中央値 39.7 s・最大 70.7 s（遠い所や逆向きで引き継ぐと、形成の前の固定の軌道が長い）。引き継ぎで加速度は 0.13 → 0.30 m/s² と段で変わる（速さは連続、加加速度は抑えていない）→ 仕上げ44",
    "導入と接近の水は単発再生の待機（t = 0 のコマ）で止まったうねり。接近でうねりを育てることと、引き継ぎの時刻は設計47",
    "船用水面データの関心の範囲は固定の長方形（x −31〜109、z −59〜25 m）。外は予備の y = 0（この試験では 0 回）。範囲を広げる時は作り直しの時間（1 回 約 22 ms）が増える",
    "形成の間、波が座席の船を持ち上げて大きく傾ける（傾き最大 67°、上下の加速度最大 11.5 m/s²、浮力点がすべて水の外の段 79）。設計43 の記録と同じ所。座席の目は全コマで水の上（余裕の最小 0.46 m）→ 設計45・仕上げ43",
    "Play モードの道（FixedUpdate＋ReadLive で今の機器を読む。DS44_Steer.unity は stepInFixedUpdate = 0 で保存）は回していない（batchmode の Editor で Step を外から 1/120 s で呼んだ）。"
    "プロジェクトの固定の時間刻みは 0.02 s（50 Hz、TimeManager 2822399/141120000）で、跳びのしきい値は 1/120 s の段で決めてある → Play モードの刻みでの確かめは設計47。"
    "実行順（DS42Buoyancy 0 → DS44BoatSteer 70）は正しい。手で押す確かめ・PS VR2 の Sense・HMD は保留",
    "ほかの 2 隻は設計43 と同じく自由に浮く。軌道は他の船や右の高い波を避ける計算をしていない（この試験の道は触れていない）",
    "形成の間、右舷の側に右の高い波（設計30 の周りの海の一部）が立ち、run2 の追う視点と横の視点をふさいだので、run3 で 2 つのカメラを左舷の側へ移した（物理の記録は run2 とバイトで同じ）",
    # 以下は検査（ck44）で見つかり、修正の回で記録にしたもの（受入の量は満たすので直さず仕上げへ送る）
    "引き継ぎの道は船の根の位置（rb.position）と重心の速度（rb.linearVelocity）から作っている（DS44BoatSteer.Handover）。軌道の間は根を重心の速度で動かし、ω×r（r 約 0.44 m）の分を落とすので、"
    "根の進む向きが引き継ぎの次の 1 段（s = 70.0167 s）で −37.37° → −38.65°（1.27°）跳ぶ（横の速度の段 約 0.033 m/s。座席の目では 30 fps の 1 コマ 0.0255 m/s、引き継ぎ前 0.006、操船の間の p99 0.036）。"
    "受入の量（首の向きと速さ）は連続（首の向きの段 0.0414°、速さの段 0.00125 m/s）。直し方の案：rb.GetPointVelocity(rb.position) を使うか、道を重心で作る → 仕上げ44",
    "引き継ぎの時、船は右へ 約 +5°/s で回っていたが、軌道の弧は左へ回る（−43°）。座席の目の進む向きの変わり方が 1 コマ +0.18° から −0.3° へ変わり、横の加速度が 約 0.13 m/s² 段で変わる"
    "（上の加速度の段 0.13 → 0.30 m/s² と同じ所。加加速度は抑えていない）→ 仕上げ44",
    "着いた状態（Arrived）は段の格子のため t* の 1 段（8.3 ms）前に始まる（s = 91.65 s で tPlay = 11.992 s）。速さはすでに 0 なので見た目の差はない → 仕上げ44",
]


def runs_record():
    r = {}
    for name in ("run1", "run2"):
        p = os.path.join(OUT, name, "ds44_unity_report.json")
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            r[name] = dict(utc=d["utc"], handoverPos=d["handoverPos"], arrivalPos=d["arrivalPos"], arrivalYawDeg=d["arrivalYawDeg"], arrivalSpeed=d["arrivalSpeed"])
    r["run1"] = dict(r.get("run1", {}), note_ja="最初の実行。操船・範囲・引き継ぎの受入は満たしたが、軌道を速度の帰還だけで追ったので、形成の終わりに t* のずれ 0.14 m・5.6°")
    r["run2"] = dict(r.get("run2", {}), note_ja="修正 1 回目（Q26 の 1 回）：軌道の間、段ごとに水平の位置と首の向きを合わせる（D44-4）。範囲の目印の柱を縁に沿って等間隔に。横の視点を足した")
    p2 = os.path.join(OUT, "run2", "ds44_steps.csv")
    p3 = os.path.join(UNITY, "ds44_steps.csv")
    same = os.path.exists(p2) and os.path.exists(p3) and sha256_file(p2) == sha256_file(p3)
    r["run3"] = dict(note_ja="カメラだけを動かした描き直し（追う視点と横の視点を左舷の側へ）。物理の記録 ds44_steps.csv は run2 とバイトで同じか", steps_csv_identical_to_run2=bool(same),
                     steps_csv_sha256=sha256_file(p3) if os.path.exists(p3) else None)
    r["report_fix"] = dict(
        note_ja="検査（ck44）の後の修正の回（Q26 の 1 回）。直したのは報告の図だけ：fig_ds44_steer.png の要約の文をグラフの下（y ≥ 840）へ移し、縦軸の名前を枠の上（題の左）へ移して目盛の数値と重ねない。"
                "範囲のグラフの線を枠の横の範囲で切った（前は s > 72 s の線が枠の右へはみ出ていた）。動画は crf 23 → 25 で 5 MB の目安の下へ。"
                "Unity と物理は回し直していない（ds44_steps.csv は run3 のまま、受入の数値は同じ）",
        steps_csv_sha256=sha256_file(p3) if os.path.exists(p3) else None)
    return r


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def project(cam, pts):
    """世界の点（N×3）→ 画素（N×2）と前にあるか。"""
    w2c = np.array(cam["w2c"], np.float64).reshape(4, 4)
    pr = np.array(cam["proj"], np.float64).reshape(4, 4)
    P = np.hstack([np.asarray(pts, np.float64), np.ones((len(pts), 1))])
    c = (pr @ w2c @ P.T).T
    wv = c[:, 3]
    ndc = c[:, :3] / wv[:, None]
    x = (ndc[:, 0] + 1) * 0.5 * W
    y = (1 - ndc[:, 1]) * 0.5 * H
    return np.stack([x, y], 1), wv > 1e-6


def outline_world(fr, R, inset=0.0, n=256):
    """範囲の縁（inset > 0 で内側へ）の世界の xz。"""
    r = max(R["cornerRadius"] - inset, 0.5)
    u0, u1, v0, v1 = R["uMin"] + inset, R["uMax"] - inset, R["vMin"] + inset, R["vMax"] - inset
    pts = []
    for cu, cv, a0 in [(u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180), (u1 - r, v0 + r, 270)]:
        for k in range(n // 4 + 1):
            a = math.radians(a0 + 90.0 * k / (n // 4))
            pts.append(fr.to_world(cu + r * math.cos(a), cv + r * math.sin(a)))
    pts.append(pts[0])
    return np.array(pts)


def phase_of(s, s_h, s_f, t_star):
    if s < s_h:
        return "STEERING (intro/approach)"
    if s < s_f:
        return "FIXED TRAJECTORY (lead before formation)"
    if s < t_star:
        return "FIXED TRAJECTORY + FORMATION t = %.2f s" % (s - s_f)
    return "ARRIVED, HOLD at t* (painting position)"


def put(img, txt, org, scale=0.55, color=(255, 255, 255), thick=1, bg=True):
    if bg:
        (tw, th), bl = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        cv2.rectangle(img, (org[0] - 3, org[1] - th - 4), (org[0] + tw + 3, org[1] + bl + 2), (20, 20, 20), -1)
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


class Panel:
    """OpenCV の簡単なグラフの枠。"""

    def __init__(self, img, x0, y0, w, h, xr, yr, title="", ylab=""):
        self.img, self.x0, self.y0, self.w, self.h, self.xr, self.yr = img, x0, y0, w, h, xr, yr
        cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (255, 255, 255), -1)
        if title:
            cv2.putText(img, title, (x0 + 4, y0 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
        if ylab:
            # 修正（検査の指摘）：縦軸の名前は枠の上（題の左）に置き、上の目盛の数値と重ねない
            (tw, _), _ = cv2.getTextSize(ylab, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
            cv2.putText(img, ylab, (max(x0 - 6 - tw, 0), y0 - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (60, 60, 60), 1, cv2.LINE_AA)

    def X(self, x):
        v = self.x0 + (np.asarray(x, np.float64) - self.xr[0]) / (self.xr[1] - self.xr[0]) * self.w
        return int(round(float(v))) if np.ndim(v) == 0 else np.round(v).astype(np.int32)

    def Y(self, y):
        v = self.y0 + self.h - (np.clip(np.asarray(y, np.float64), self.yr[0], self.yr[1]) - self.yr[0]) / (self.yr[1] - self.yr[0]) * self.h
        return int(round(float(v))) if np.ndim(v) == 0 else np.round(v).astype(np.int32)

    def span(self, a, b, color):
        cv2.rectangle(self.img, (self.X(max(a, self.xr[0])), self.y0), (self.X(min(b, self.xr[1])), self.y0 + self.h), color, -1)

    def vline(self, x, color=(90, 90, 90), dashed=True):
        X = self.X(x)
        for y in range(self.y0, self.y0 + self.h, 6 if dashed else self.h):
            cv2.line(self.img, (X, y), (X, min(y + (3 if dashed else self.h), self.y0 + self.h)), color, 1)

    def hline(self, y, color=(90, 90, 90), dashed=False):
        Y = self.Y(y)
        step = 6 if dashed else self.w
        for x in range(self.x0, self.x0 + self.w, step):
            cv2.line(self.img, (x, Y), (min(x + (3 if dashed else self.w), self.x0 + self.w), Y), color, 1)

    def line(self, x, y, color, thick=1, dots=False):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        m = ~np.isnan(y) & (x >= self.xr[0]) & (x <= self.xr[1])  # 修正：枠の外（横）へ線を出さない
        pts = np.stack([self.X(x[m]), self.Y(y[m])], 1).astype(np.int32)
        if dots:
            for q in pts:
                cv2.circle(self.img, (int(q[0]), int(q[1])), 2, color, -1, cv2.LINE_AA)
        cv2.polylines(self.img, [pts.reshape(-1, 1, 2)], False, color, thick, cv2.LINE_AA)

    def axes(self, xticks, yticks, fmt_x="%g", fmt_y="%g"):
        cv2.rectangle(self.img, (self.x0, self.y0), (self.x0 + self.w, self.y0 + self.h), (80, 80, 80), 1)
        for t in xticks:
            X = self.X(t)
            cv2.line(self.img, (X, self.y0 + self.h), (X, self.y0 + self.h + 3), (80, 80, 80), 1)
            cv2.putText(self.img, fmt_x % t, (X - 8, self.y0 + self.h + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (60, 60, 60), 1, cv2.LINE_AA)
        for t in yticks:
            Y = self.Y(t)
            cv2.line(self.img, (self.x0 - 3, Y), (self.x0, Y), (80, 80, 80), 1)
            cv2.putText(self.img, fmt_y % t, (max(self.x0 - 40, 0), Y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (60, 60, 60), 1, cv2.LINE_AA)


def phase_spans(pn, s_h, s_f, t_star, s_end):
    pn.span(0, s_h, (224, 240, 232))
    pn.span(s_h, s_f, (247, 230, 210))
    pn.span(s_f, t_star, (210, 230, 247))
    pn.span(t_star, s_end, (238, 238, 238))
    for x in (s_h, s_f, t_star):
        pn.vline(x)


def build_graph(ser, S, s_h, s_f, t_star, s_end, path, P):
    img = np.full((H, W, 3), 250, np.uint8)
    s = ser["s"]
    k = slice(None, None, 4)
    xt = list(range(0, int(s_end) + 1, 10))
    x0, w, h = 52, 890, 86
    ys = [24, 150, 276, 402]
    p0 = Panel(img, x0, ys[0], w, h, (0, s_end), (-1.5, 2.6), "speed (m/s): blue |v|, orange surge", "m/s")
    phase_spans(p0, s_h, s_f, t_star, s_end)
    p0.hline(0, (150, 150, 150))
    p0.line(s[k], ser["spd"][k], (156, 78, 31), 2)
    p0.line(s[k], ser["surge"][k], (32, 96, 208), 1)
    p0.axes(xt, [-1, 0, 1, 2])
    p1 = Panel(img, x0, ys[1], w, h, (0, s_end), (-130, -20), "heading psi (deg); dashed = painting heading", "deg")
    phase_spans(p1, s_h, s_f, t_star, s_end)
    p1.hline(P["painting"]["yawDeg"], (0, 136, 170), dashed=True)
    p1.line(s[k], ser["psi"][k], (42, 122, 42), 2)
    p1.axes(xt, [-120, -90, -60, -30])
    p2 = Panel(img, x0, ys[2], w, h, (0, s_end), (-1.15, 1.15), "inputs read from the virtual devices: blue throttle, red turn, black stop", "input")
    phase_spans(p2, s_h, s_f, t_star, s_end)
    p2.hline(0, (150, 150, 150))
    p2.line(s[k], S["thrIn"][k], (156, 78, 31), 2)
    p2.line(s[k], S["turnIn"][k], (48, 48, 176), 1)
    p2.line(s[k], S["stopIn"][k] * 0.9, (30, 30, 30), 1)
    p2.axes(xt, [-1, 0, 1])
    p3 = Panel(img, x0, ys[3], w, h, (0, s_end), (-30, 2), "distance to the range edge d (m, + = outside); orange dashes = push-back band", "m")
    phase_spans(p3, s_h, s_f, t_star, s_end)
    p3.hline(0, (16, 16, 192))
    p3.hline(-P["range"]["bandM"], (32, 144, 224), dashed=True)
    p3.line(s[k], ser["d"][k], (226, 43, 138), 2)
    p3.axes(xt, [-30, -20, -10, 0])
    cv2.putText(img, "s (s)   green: steering | blue: fixed trajectory lead | orange: formation t 0-12 s | grey: hold", (x0, H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (40, 40, 40), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)
    return float(p0.X(0)), float(p0.X(s_end))


def main():
    t_start = time.time()
    P = M.load_params()
    fr = M.Frame(P)
    res, S, F, rep = DM.measure(P)
    ser = res.pop("series")
    s_h, s_f, t_star = res["handover_s"], res["formation_start_s"], res["t_star_s"]
    s_end = F[-1]["s"]
    os.makedirs(OUT, exist_ok=True)
    # ---- 時系列の背景
    gpath = os.path.join(OUT, "graph_panel.png")
    gx0, gx1 = build_graph(ser, S, s_h, s_f, t_star, s_end, gpath, P)
    graph = cv2.imread(gpath)
    # ---- 地図に重ねるもの
    R = P["range"]
    edge = outline_world(fr, R)
    band = outline_world(fr, R, inset=R["bandM"])
    fs = np.array([f["s"] for f in F])
    seat = np.array([[b for b in f["boats"] if b["key"] == P["painting"]["key"]][0]["pos"] for f in F])
    rot = np.array([[b for b in f["boats"] if b["key"] == P["painting"]["key"]][0]["rot"] for f in F])
    heading = DM.heading_from_quat(rot[:, 0], rot[:, 1], rot[:, 2], rot[:, 3])
    trajP = np.stack([rep["trajPathX"], rep["trajPathZ"]], 1) if rep.get("trajPathX") else None
    si = np.searchsorted(S["s"], fs).clip(0, len(S["s"]) - 1)
    segs = P["test"]["segments"]

    def w3(xz, y=0.0):
        xz = np.asarray(xz)
        return np.stack([xz[:, 0], np.full(len(xz), y), xz[:, 1]], 1)

    def draw_map(img, n, cam, full=False):
        pe, _ = project(cam, w3(edge))
        pb, _ = project(cam, w3(band))
        cv2.polylines(img, [pe.astype(np.int32)], False, (40, 40, 220), 2, cv2.LINE_AA)
        for k in range(0, len(pb) - 1, 2):
            cv2.line(img, tuple(pb[k].astype(int)), tuple(pb[k + 1].astype(int)), (40, 150, 240), 1, cv2.LINE_AA)
        pp, _ = project(cam, w3(np.array([fr.o, fr.o + 8 * fr.f])))
        cv2.circle(img, tuple(pp[0].astype(int)), 7, (0, 220, 255), 2, cv2.LINE_AA)
        cv2.arrowedLine(img, tuple(pp[0].astype(int)), tuple(pp[1].astype(int)), (0, 220, 255), 2, cv2.LINE_AA, tipLength=0.3)
        put(img, "painting position (t*)", (int(pp[0][0]) + 10, int(pp[0][1]) + 5), 0.45, (0, 220, 255))
        m15 = [fr.to_world(u, v) for u, v in [(-24, -7), (-10, -7), (-10, 12), (-24, 12), (-24, -7)]]
        p15, _ = project(cam, w3(np.array(m15)))
        cv2.polylines(img, [p15.astype(np.int32)], False, (180, 180, 180), 1, cv2.LINE_AA)
        if trajP is not None and (full or fs[n] >= s_h):
            pt, _ = project(cam, w3(trajP))
            cv2.polylines(img, [pt.astype(np.int32)], False, (255, 230, 0), 1, cv2.LINE_AA)
        upto = len(fs) if full else n + 1
        tr, _ = project(cam, w3(seat[:upto, [0, 2]]))
        for k in range(1, upto):
            c = (255, 255, 255) if fs[k] < s_h else ((255, 200, 80) if fs[k] < s_f else (80, 170, 255))
            cv2.line(img, tuple(tr[k - 1].astype(int)), tuple(tr[k].astype(int)), c, 2, cv2.LINE_AA)
        if fs[min(n, len(fs) - 1)] >= s_h or full:
            ph, _ = project(cam, w3(np.array([[rep["handoverPos"][0], rep["handoverPos"][2]]])))
            cv2.drawMarker(img, tuple(ph[0].astype(int)), (255, 230, 0), cv2.MARKER_DIAMOND, 14, 2)
        nn = min(n, len(fs) - 1)
        hd = math.radians(heading[nn])
        pa, _ = project(cam, w3(np.array([seat[nn, [0, 2]], seat[nn, [0, 2]] + 9 * np.array([math.sin(hd), math.cos(hd)])])))
        cv2.arrowedLine(img, tuple(pa[0].astype(int)), tuple(pa[1].astype(int)), (60, 230, 60), 2, cv2.LINE_AA, tipLength=0.35)
        put(img, "top view (orthographic). red: range edge, orange dashes: push-back band, grey: design-15 box (M1), yellow: fixed trajectory, diamond: handover",
            (8, H - 10), 0.36, (230, 230, 230))

    # ---- 動画
    mp4 = os.path.join(OUT, "ds44_steer_30fps.mp4")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1920x1080", "-r", "30", "-i", "-",
           "-c:v", "libx264", "-crf", "25", "-preset", "medium", "-pix_fmt", "yuv420p", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    stills_idx = {}
    key_times = [8.0, 16.0, 24.0, 29.0, 36.0, 48.0, 56.0, 60.0, s_h + 0.0, s_h + 5.0, s_f + 6.0, t_star]
    for kt in key_times:
        stills_idx[int(np.argmin(np.abs(fs - kt)))] = kt
    stills = {}
    for n, f in enumerate(F):
        a = cv2.imread(os.path.join(FRAMES, "chase_%04d.jpg" % n))
        b = cv2.imread(os.path.join(FRAMES, "map_%04d.jpg" % n))
        c = cv2.imread(os.path.join(FRAMES, "side_%04d.jpg" % n))
        draw_map(b, n, f["camMap"])
        i = si[n]
        sN = f["s"]
        seg = int(S["seg"][i]) if not np.isnan(S["seg"][i]) else -1
        lab = LABEL_EN.get(segs[seg]["labelJa"], "") if (seg >= 0 and sN < s_h) else ""
        put(a, "s = %6.2f s   %s" % (sN, phase_of(sN, s_h, s_f, t_star)), (10, 24), 0.6, (255, 255, 255), 1)
        if sN < s_h:
            put(a, "script: %s" % lab, (10, 52), 0.55, (120, 255, 255))
            put(a, "input read (Unity Input System, virtual %s): throttle %+.2f  turn %+.2f  stop %d" % (S["src"][i] if S["src"][i] != "-" else "device", S["thrIn"][i], S["turnIn"][i], int(S["stopIn"][i])), (10, 80), 0.5)
        else:
            put(a, "fixed trajectory to the painting position (D26); input ignored", (10, 52), 0.55, (120, 255, 255))
        put(a, "speed %.2f m/s  surge %+.2f m/s  heading %.1f deg  yaw rate %+.1f deg/s" % (ser["spd"][i], ser["surge"][i], ser["psi"][i], ser["yawrate"][i]), (10, 108), 0.5)
        if sN < s_h:
            put(a, "distance to range edge d = %+.2f m   push-back %.2f m/s^2" % (ser["d"][i], S["pushA"][i] if not np.isnan(S["pushA"][i]) else 0.0), (10, 136), 0.5)
        else:
            put(a, "range push-back off (fixed trajectory leaves the steering range by design)", (10, 136), 0.5)
        put(a, "chase view (Unity PC batchmode render, not HMD). red posts = range edge (test scene only)", (8, H - 10), 0.4, (230, 230, 230))
        put(c, "side overview (fixed camera, Unity render). Wave formation starts at s = %.2f s, t* at s = %.2f s" % (s_f, t_star), (8, H - 10), 0.42, (230, 230, 230))
        g = graph.copy()
        x = int(round(gx0 + (gx1 - gx0) * sN / s_end))
        cv2.line(g, (x, 8), (x, H - 30), (0, 0, 200), 2)
        top = np.hstack([a, b])
        bot = np.hstack([c, g])
        img = np.vstack([top, bot])
        proc.stdin.write(img.tobytes())
        if n in stills_idx:
            stills[stills_idx[n]] = (a.copy(), b.copy())
    proc.stdin.close()
    proc.wait()
    # ---- 静止画（12 の時刻、追う視点と地図）
    cells = []
    for kt in key_times:
        a, b = stills[kt]
        cells.append(np.vstack([cv2.resize(a, (320, 180)), cv2.resize(b, (320, 180))]))
    rows = [np.hstack(cells[i:i + 6]) for i in (0, 6)]
    sheet = np.vstack(rows)
    canvas = np.full((1080, 1920, 3), 245, np.uint8)
    canvas[0:720, 0:1920] = sheet
    put(canvas, "DS44 key moments (top: chase view, bottom: map). s = " + ", ".join("%.1f" % k for k in key_times), (10, 760), 0.6, (0, 0, 0), 1, bg=False)
    for j, line in enumerate([
        "1-4: W accelerate / no input drag / W+D turn right / Space stop.   5-8: turn left at rest / R2 toward the edge, soft push-back / release / L2 reverse.",
        "9: handover to the fixed trajectory (s = %.2f s).  10: lead before formation.  11: formation t = 6 s.  12: t* (painting position)." % s_h,
        "PC batchmode render (not HMD). Overlays on the map are drawn from the logged numbers."]):
        put(canvas, line, (10, 800 + 30 * j), 0.55, (40, 40, 40), 1, bg=False)
    still_path = os.path.join(OUT, "stills_ds44_key_moments.png")
    cv2.imwrite(still_path, canvas)
    # ---- 図
    last = cv2.imread(os.path.join(FRAMES, "map_%04d.jpg" % (len(F) - 1)))
    first = cv2.imread(os.path.join(FRAMES, "map_%04d.jpg" % 0))
    base = cv2.addWeighted(first, 0.5, last, 0.5, 0)
    draw_map(base, len(F) - 1, F[-1]["camMap"], full=True)
    canvas = np.full((1080, 1920, 3), 250, np.uint8)
    bb = cv2.resize(base, (1100, 619))
    canvas[40:659, 10:1110] = bb
    cv2.putText(canvas, "Top view (Unity render, first and last frames blended) + logged path: white = steering, blue = fixed trajectory lead, orange = formation", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    s = ser["s"]
    pA = Panel(canvas, 1180, 60, 720, 200, (0, s_end), (-1.5, 2.8), "input -> acceleration and drag: speed (blue |v|, orange surge); numbers = script segments", "m/s")
    for j, g_ in enumerate(segs):
        pA.span(g_["s0"], g_["s1"], (246, 238, 230) if j % 2 else (232, 240, 246))
        cv2.putText(canvas, str(j + 1), (pA.X((g_["s0"] + g_["s1"]) / 2) - 4, pA.Y(2.6)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (20, 20, 20), 1, cv2.LINE_AA)
    for x_ in (s_h, s_f, t_star):
        pA.vline(x_)
    pA.hline(0, (150, 150, 150))
    pA.line(s[::4], ser["spd"][::4], (156, 78, 31), 2)
    pA.line(s[::4], ser["surge"][::4], (32, 96, 208), 1)
    pA.axes(list(range(0, int(s_end) + 1, 10)), [-1, 0, 1, 2])
    pB = Panel(canvas, 1180, 320, 720, 200, (0, s_h + 2), (-30, 2), "out-of-range: d (+ = outside). pushing outward: max d = %.2f m; release -> back %.2f m" % (res["out_of_range"]["d_max_push_segment"], res["out_of_range"]["inward_move_after_release_m"]), "d (m)")
    pB.span(segs[6]["s0"], segs[6]["s1"], (232, 240, 246))
    pB.hline(0, (16, 16, 192))
    pB.hline(-R["bandM"], (32, 144, 224), dashed=True)
    pB.line(s[::4], ser["d"][::4], (226, 43, 138), 2)
    pB.axes(list(range(0, int(s_h) + 3, 10)), [-30, -20, -10, 0])
    ih = res["handover_index"]
    win = slice(ih - 120, ih + 121)
    ps = ser["psi"][win]
    pC = Panel(canvas, 1180, 580, 330, 200, (s_h - 1, s_h + 1), (float(ps.min()) - 0.05, float(ps.max()) + 0.05), "heading at handover (every 1/120 s step)", "deg")
    pC.vline(s_h)
    pC.line(s[win], ps, (42, 122, 42), 1, dots=True)
    pC.axes([s_h - 1, s_h, s_h + 1], [round(float(ps.min()), 1), round(float(ps.max()), 1)], "%.0f", "%.1f")
    vs = ser["spd"][win]
    pD = Panel(canvas, 1570, 580, 330, 200, (s_h - 1, s_h + 1), (float(vs.min()) - 0.01, float(vs.max()) + 0.01), "speed at handover (every 1/120 s step)", "m/s")
    pD.vline(s_h)
    pD.line(s[win], vs, (156, 78, 31), 1, dots=True)
    pD.axes([s_h - 1, s_h, s_h + 1], [round(float(vs.min()), 2), round(float(vs.max()), 2)], "%.0f", "%.2f")
    jp = res["handover"]
    lines = [
        "Handover at s = %.2f s: heading step %.4f deg (prev %.4f, next %.4f); speed step %.5f m/s (prev %.5f, next %.5f)" % (
            s_h, jp["heading_step_deg"], jp["heading_step_prev_deg"], jp["heading_step_next_deg"], jp["speed_step"], jp["speed_step_prev"], jp["speed_step_next"]),
        "Jumps (> %.3f deg or > %.4f m/s per 1/120 s step): +-1 s window %d / %d; handover -> formation start %d / %d; formation (record) %d / %d" % (
            jp["threshold_heading_step_deg"], jp["threshold_speed_step"], jp["jumps_heading_window"], jp["jumps_speed_window"], jp["jumps_heading_lead"], jp["jumps_speed_lead"],
            jp["formation_record"]["heading_steps_over_threshold"], jp["formation_record"]["speed_steps_over_threshold"]),
        "Fixed trajectory: L = %.1f m, T = %.2f s, lead before formation = %.2f s, arc %.1f deg; arrival at t*: position error %.3f m, heading error %.2f deg, speed %.3f m/s" % (
            res["trajectory"]["L_m"], res["trajectory"]["T_s"], res["trajectory"]["lead_s"], res["trajectory"]["arc_deg"], res["arrival"]["pos_err_m"], res["arrival"]["yaw_err_deg"], res["arrival"]["speed"]),
        "Accelerate (W): 0 -> %.2f m/s in 10 s (onset %.2f s after the press). Drag (no input): measured / model deceleration = %.3f. Stop (Space): %.2f -> %.3f m/s in %.2f s." % (
            res["input_to_motion"]["accelerate"]["v_end"], res["input_to_motion"]["accelerate"]["onset_s_after_press"], res["input_to_motion"]["drag"]["ratio_measured_to_model"],
            res["input_to_motion"]["stop"]["surge_start"], res["input_to_motion"]["stop"]["surge_end"], res["input_to_motion"]["stop"]["time_to_below_0p05"]),
        "Unity 6000.4.3f1 PC batchmode (RTX 3080), not HMD. Inputs: Unity Input System virtual keyboard / gamepad (InputState.Change), read by DS44Input.Read. PS VR2 Sense: pending (not installed).",
    ]
    for j, t_ in enumerate(lines):
        # 修正（検査の指摘）：要約の文は全部のグラフ（下端 y = 780、目盛の数値 y ≈ 794）より下に置く
        cv2.putText(canvas, t_, (10, 840 + 30 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    fig_path = os.path.join(OUT, "fig_ds44_steer.png")
    cv2.imwrite(fig_path, canvas)
    # ---- metrics.json
    acc = res["input_to_motion"]
    rr = res["out_of_range"]
    arr = res["arrival"]
    mm = dict(
        schema="GreatWave.DS44.metrics/1", number="設計44", part="steer", created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        backlog={"82": "記録（操船の範囲と原画の位置へ導く引き継ぎ。計画 §2.4 設計44 の依存・バックログ。使える水準）",
                 "91": "航行から大波の出現への引継ぎ：向き（計画 §5 仕上げ44 の文言から。使える水準：跳び 0）",
                 "92": "航行から大波の出現への引継ぎ：速さ（同上。使える水準：跳び 0）"},
        min_acceptance_ja="入力から加速と抵抗が働く動画。範囲外の扱いが働く。引き継ぎで向きと速さの跳び 0（91・92 を使える水準で）（計画 §2.4 設計44）",
        min_acceptance=dict(
            input_to_motion=dict(video="ds44_steer_30fps.mp4", accelerate=acc["accelerate"], drag=acc["drag"], turn_right=acc["turn_right"], stop=acc["stop"],
                                 turn_left_at_rest=acc["turn_left_at_rest"], reverse=acc["reverse"], pass_=acc["pass_"]),
            out_of_range=rr,
            handover_jumps=jp,
            pass_=bool(acc["pass_"] and rr["pass_"] and jp["pass_"])),
        arrival=arr, tracking=res["tracking"], trajectory=res["trajectory"], trajectory_crosscheck=res["trajectory_crosscheck"], segments=res["segments"],
        record_only=dict(seat_eye=res["seat_eye"], heave_accel=res["heave_accel"], wet_zero_steps=res["wet_zero_steps"],
                         water=dict(fallbacks=rep["fallbacks"], rebuilds=rep["rebuilds"], rebuild_ms_mean=rep["rebuildMsMean"], region=rep["region"])),
        input_path=dict(path=rep["inputPath"], check_ja=rep["inputCheckJa"], ps_vr2_sense="保留（PS VR2 は未導入。SteamVR の OpenXR の XRController の thumbstick／primary2DAxis を読む道は書いたが確かめていない）"),
        painting_view_touched=False, protected_unchanged=rep["protectedUnchanged"], changed_files=rep["changedFiles"],
        runs=runs_record(),
        decisions_ja=DECISIONS_JA,
        limits_ja=LIMITS_JA,
    )
    DM_json = os.path.join(OUT, "metrics.json")
    with open(DM_json, "w", encoding="utf-8") as fo:
        json.dump(mm, fo, ensure_ascii=False, indent=1)
    # ---- run.json
    files_in = [os.path.join(REPO, p) for p in [
        "Unity/Assets/GreatWave/Design44/Data/ds44_steer.json", "Unity/Assets/GreatWave/Design44/Scripts/DS44SteerConfig.cs", "Unity/Assets/GreatWave/Design44/Scripts/DS44Trajectory.cs",
        "Unity/Assets/GreatWave/Design44/Scripts/DS44Input.cs", "Unity/Assets/GreatWave/Design44/Scripts/DS44BoatSteer.cs", "Unity/Assets/GreatWave/Design44/Editor/DS44SteerTest.cs",
        "Tools/GWWaveGen/ds44/ds44_model.py", "Tools/GWWaveGen/ds44/ds44_measure.py", "Tools/GWWaveGen/ds44/ds44_grid.py", "Tools/GWWaveGen/ds44/ds44_report.py", "Tools/GWWaveGen/ds44/run_ds44_unity.ps1",
        "Unity/Assets/GreatWave/Design43/Data/ds43_boats.json", "Unity/Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_mid.json"]]
    files_out = [os.path.join(OUT, p) for p in ["ds44_steer_30fps.mp4", "fig_ds44_steer.png", "stills_ds44_key_moments.png", "metrics.json", "graph_panel.png",
                                                "unity/ds44_unity_report.json", "unity/ds44_steps.csv", "unity/ds44_frames.jsonl", "ds44_trajectory_grid.json"]]
    run = dict(
        schema="GreatWave.DS44.run/1", number="設計44", part="steer",
        commands=["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds44/run_ds44_unity.ps1 -Method GreatWave.Design44.EditorTools.DS44SteerTest.Run -Log run3",
                  "py -3.10 Tools/GWWaveGen/ds44/ds44_grid.py", "py -3.10 Tools/GWWaveGen/ds44/ds44_report.py"],
        tools=dict(python="py -3.10（numpy %s・OpenCV %s）" % (np.__version__, cv2.__version__), unity="6000.4.3f1 batchmode（run_ds44_unity.ps1、unity.lock）", ffmpeg=FFMPEG),
        unity_report=dict((k, rep[k]) for k in ["utc", "device", "graphicsApi", "scene", "sceneSha256", "secondsTotal", "secondsLoop", "frames", "inputPath", "protectedUnchanged", "simulationModeBefore", "simulationModeAfter"]),
        inputs={os.path.relpath(p, REPO).replace("\\", "/"): sha256_file(p) for p in files_in if os.path.exists(p)},
        outputs={os.path.relpath(p, REPO).replace("\\", "/"): dict(sha256=sha256_file(p), bytes=os.path.getsize(p)) for p in files_out if os.path.exists(p)},
        frames_dir=dict(path="Unity/Build/Design/44/steer/unity/frames", files=len(os.listdir(FRAMES))),
        seconds_report=round(time.time() - t_start, 1),
    )
    with open(os.path.join(OUT, "run.json"), "w", encoding="utf-8") as fo:
        json.dump(run, fo, ensure_ascii=False, indent=1)
    print(json.dumps(dict(pass_=mm["min_acceptance"]["pass_"], acc=acc["pass_"], range=rr["pass_"], handover=jp["pass_"], arrival=arr, seconds=run["seconds_report"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
