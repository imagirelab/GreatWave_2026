# -*- coding: utf-8 -*-
"""仕上げ27：設計27 の座席の静止画 3 枚（噴流の始まり・段階 d・t*）の代替（seat_form の仰角 30° の視点、設計27 の動き）を、
体験の場面（設計50 の DS50_Release、Release のプレイヤーの PC の画面）の座席 v1 の画に置き換える。

座席 v1：Tools/GWContext/seat_v1.json の目（右船の唇の下）。体験の場面では、この目が座席の船（設計41〜45）に乗り、正面は座席 v1 の
再センタリングの向き（設計45 D45-6）。画は設計50 の最終の記録の走り capture5（Time.captureDeltaTime = 1/30 s、毎フレームの JPG、
1920×1080。Release の exe。記録は Unity/Build/Design/50/release/runs/capture5/）から、目標の時刻に一番近い、走っている（止めていない）
フレームを選び、PNG に写す（拡大・縮小なし。JPG の圧縮はそのまま）。新しく描いてはいない。

目標の時刻（設計27 の最小の受入の 3 枚と同じ出来事を、採用の動き F_final で）：
  噴流の始まり：峰で最も高い巻きの行（K*′ の行 160）の前面が鉛直になる τ（関門の検査器の onset_tau_by_row。F_final の default_ds27.json）
  段階 d：同じ行の P15 の d の τ
  t*：τ = 0
τ → 体験の時刻 t は 28修正01 の τ(t)（timewarp_F_final.json。体験の場面の GWClock が読む表と同じことを DS47 の記録で確かめた）。

比べの図：1 段目 設計27 の座席 v1（固定の見上げ。波が入らない）、2 段目 設計27 の代替（seat_form）、3 段目 仕上げ27（体験の場面の座席 v1）。
設計27 の 2 つの段は設計27 の動き（採用の経路にない）の、設計27 の噴流の始まり（峰の行 τ −2.62 s。P7）・段階 d（τ −1.967 s）・t* の画。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl27/pl27_seat_stills.py
"""
import csv
import hashlib
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CAP = os.path.join(REPO, "Unity", "Build", "Design", "50", "release", "runs", "capture5")
TW_F = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "timewarp_F_final.json")
GATES_F = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "gates", "default_ds27.json")
TW_27 = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json")
B27 = os.path.join(REPO, "Unity", "Build", "Design", "27")
OUT = os.path.join(REPO, "Docs", "Evidence", "Polish", "27")
FONT = "C:/Windows/Fonts/YuGothM.ttc"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def tau_to_t(tw, tau):
    t = np.array(tw["t"], float)
    ta = np.array(tw["tau"], float)
    if tau >= 0.0:
        return 12.0
    return float(np.interp(tau, ta, t))


def main():
    os.makedirs(OUT, exist_ok=True)
    twf = json.load(open(TW_F, encoding="utf-8"))
    G = json.load(open(GATES_F, encoding="utf-8"))
    pr = int(G["kstar"]["peak_row"])
    onset = float(G["onset_tau_by_row"][str(pr)])
    p15 = G["gates"]["P15"]["detail"]
    d_tau = None
    for k, v in p15.items():
        if isinstance(v, dict) and v.get("row") == pr and isinstance(v.get("tau"), dict):
            d_tau = v["tau"].get("d")
    if d_tau is None:
        d_tau = -1.983           # default_ds27.md の P15：峰で最も高い巻きの行 d −1.983
    targets = [("onset", "噴流の始まり", onset), ("d", "段階 d", float(d_tau)), ("tstar", "t*", 0.0)]
    rows = list(csv.DictReader(open(os.path.join(CAP, "frames_capture.csv"), encoding="utf-8")))
    wave = np.array([float(r["wave"]) for r in rows])
    running = np.array([(r["flowPaused"] == "0") and (r["shell"] == "Running") for r in rows])
    rec = dict(schema="GreatWave.pl27.seat_stills/1", source=dict(run=rel(CAP), csv_sha256=sha(os.path.join(CAP, "frames_capture.csv")),
                                                                  launch_json_sha256=sha(os.path.join(CAP, "launch.json"))),
               timewarp=dict(path=rel(TW_F), sha256=sha(TW_F)), gates=dict(path=rel(GATES_F), sha256=sha(GATES_F), peak_row=pr),
               evidence_kind_ja="Release のプレイヤー（設計50 の DS50_Release、PC の画面）の毎フレームの JPG（1/30 s）を PNG に写したもの。HMD の中の見え方ではない",
               stills=[])
    t_all = np.array([tau_to_t(twf, tv) for _, _, tv in targets])
    for (key, name, tv), tt in zip(targets, t_all):
        cand = np.where(running & (wave >= 0.0))[0]
        i = int(cand[np.argmin(np.abs(wave[cand] - tt))])
        fr = int(rows[i]["frame"])
        src = os.path.join(CAP, "frames", "f_%06d.jpg" % fr)
        tw_t = np.array(twf["t"], float)
        tw_tau = np.array(twf["tau"], float)
        tau_at = float(np.interp(wave[i], tw_t, tw_tau))
        im = Image.open(src).convert("RGB")
        assert im.size == (1920, 1080)
        dst = os.path.join(OUT, "seat_v1_exp_%s.png" % key)
        im.save(dst, optimize=True)
        rec["stills"].append(dict(key=key, name_ja=name, target_tau=round(tv, 4), target_t=round(float(tt), 4), frame=fr, frame_wave_t=round(float(wave[i]), 4),
                                  frame_tau=round(tau_at, 4), phase=rows[i]["phase"], exp_s=float(rows[i]["exp"]),
                                  source_jpg=rel(src), source_jpg_sha256=sha(src), png=rel(dst), png_sha256=sha(dst), png_bytes=os.path.getsize(dst)))
    # ---- 比べの図
    tw27 = json.load(open(TW_27, encoding="utf-8"))
    t27 = [("噴流の始まり", -2.62), ("段階 d", -1.967), ("t*", 0.0)]
    seat27 = {"噴流の始まり": None, "段階 d": os.path.join(B27, "art_on_default_stages", "stills", "ds27_seat_d_tau-1.967.png"),
              "t*": os.path.join(B27, "art_on_default_stages", "stills", "ds27_seat_tstar_tau+0.000.png")}
    # 設計27 の座席 v1 の噴流の始まり（τ −2.62）の静止画はないので、段階 c（τ −2.5）の静止画（段階 a〜d と同じ画像）で見せる
    seat27["噴流の始まり"] = os.path.join(B27, "art_on_default_stages", "stills", "ds27_seat_c_tau-2.500.png")
    W, H = 1920, 1080
    cw, ch = 528, 297
    sheet = Image.new("RGB", (W, H), (245, 241, 230))
    dr = ImageDraw.Draw(sheet)
    f1 = ImageFont.truetype(FONT, 26)
    f2 = ImageFont.truetype(FONT, 20)
    dr.text((24, 10), "仕上げ27：座席の静止画 3 枚を、代替から体験の場面の座席 v1 へ置き換えた（左から 噴流の始まり・段階 d・t*）", fill=(20, 30, 60), font=f1)
    gx = (W - 3 * cw) // 4
    x0 = [gx, 2 * gx + cw, 3 * gx + 2 * cw]
    y0 = [100, 100 + ch + 34, 100 + 2 * (ch + 34)]
    labels = ["設計27 の座席 v1（固定の見上げ。設計27 の動き。波が画面に入らない）",
              "設計27 の代替：座席の目から仰角 30°（seat_form、設計27 の動き）",
              "仕上げ27：体験の場面の座席 v1（DS50_Release の capture5、F_final）"]
    srcs = []
    for c, (nm, tv) in enumerate(t27):
        k27 = int(round(tau_to_t(tw27, tv) * 30))
        p_sf = os.path.join(B27, "art_on_default", "frames", "seat_form", "f_%04d.png" % k27)
        p_st = seat27[nm]
        p_ex = rec["stills"][c]["png"]
        for rrow, (p, cap) in enumerate(((p_st, "τ %.3f s" % (-2.5 if nm == "噴流の始まり" else tv)),
                                         (p_sf, "τ %.3f s（コマ %d）" % (tv, k27)),
                                         (os.path.join(REPO, p_ex), "τ %.3f s・t %.3f s（コマ %d）" % (rec["stills"][c]["frame_tau"], rec["stills"][c]["frame_wave_t"], rec["stills"][c]["frame"])))):
            im = Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS)
            sheet.paste(im, (x0[c], y0[rrow]))
            dr.rectangle([x0[c], y0[rrow] + ch - 30, x0[c] + cw, y0[rrow] + ch], fill=(20, 30, 60))
            dr.text((x0[c] + 8, y0[rrow] + ch - 28), "%s　%s" % (nm, cap), fill=(255, 255, 255), font=f2)
            srcs.append(dict(row=rrow, col=c, path=rel(p) if os.path.isabs(p) else p, sha256=sha(p if os.path.isabs(p) else os.path.join(REPO, p))))
    for rrow in range(3):
        dr.text((x0[0], y0[rrow] - 28), labels[rrow], fill=(20, 30, 60), font=f2)
    figp = os.path.join(OUT, "fig_pl27_seat_stills.png")
    sheet.save(figp, optimize=True)
    rec["figure"] = dict(path=rel(figp), sha256=sha(figp), sources=srcs,
                         note_ja="1・2 段目は設計27 の動き（採用の経路にない）。1 段目の噴流の始まりの列は、設計27 の座席 v1 に τ −2.62 s の静止画がないので段階 c（τ −2.5 s）の静止画"
                                 "（段階 a〜d の 4 枚は同じ画像）。3 段目は F_final の τ で選んだ Release のプレイヤーのコマ")
    with open(os.path.join(OUT, "seat_stills.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    for s in rec["stills"]:
        print(s["key"], s["target_tau"], s["target_t"], "→ frame", s["frame"], "t", s["frame_wave_t"], "τ", s["frame_tau"], s["png_bytes"])
    print("図", rel(figp))


if __name__ == "__main__":
    main()
