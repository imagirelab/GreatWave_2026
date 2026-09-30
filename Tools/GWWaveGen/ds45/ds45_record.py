# -*- coding: utf-8 -*-
"""設計45 の記録の道具：作る部の出力の SHA-256 を照合し、乗客の記録から数え直し、証拠を写し、記録の metrics.json・run.json を書く。

- 照合：作る部の run.json の inputs（コード・表・場面・設計44 の記録）と outputs（図・動画・記録）の SHA-256 を読み直して比べる（違えば止まる）。
- 数え直し（作る部の ds45_report.py・ds45_codecheck.py を使わない）：unity/ds45_rider.csv（120 Hz、5 人の乗客と船の根）から、
  段の移り変わりと座席リセット、段を固定した乗客との一致、船の枠での目の位置（着座）、1 段の回転（四元数の差の角を atan2 で求める）、
  HMD Camera の世界の位置と RiderComfortRoot の差、30 Hz の上下の加速度（区間ごと）、t* の目のずれ。
  unity/ds45_heave30.csv（設計30 の座席の上下、30 Hz）から上下の加速度と船の枠での目の位置。
  場面 DS45_Comfort.unity の部品の旗（stepInLateUpdate・stepInFixedUpdate）と GUID の依存。
- 証拠：Docs/Evidence/Design/45/ へ写す（図・静止画は 1920 × 1080 の PNG、動画は 5 MB 以下、JSON）。
  4 段の並べの動画（作る部 11.8 MB）は 5 MB の目安を超えるので、ffmpeg で 1280 × 720 に縮めて写す（元の各コマは 640 × 360 の描画を 2 × 2 に並べたもの）。
コミットの一覧の点検は、禁止の場所の文字列を持つので、この道具に入れず Git 対象外の Unity/Build/Design/45/record/ds45_commit_scan.py で行う。
使い方：py -3.10 -B Tools/GWWaveGen/ds45/ds45_record.py
PC の batchmode の出力を読むだけで、Unity と HMD は使わない。git も使わない。
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B45 = os.path.join(REPO, "Unity", "Build", "Design", "45")
OUT = os.path.join(B45, "comfort")
UNITY = os.path.join(OUT, "unity")
REC = os.path.join(B45, "record")
EVD = os.path.join(REPO, "Docs", "Evidence", "Design", "45")
ASSETS = os.path.join(REPO, "Unity", "Assets")
SCENE = os.path.join(ASSETS, "GreatWave", "Design45", "Scenes", "DS45_Comfort.unity")
BASE_SCENE = os.path.join(ASSETS, "GreatWave", "Design44", "Scenes", "DS44_Steer.unity")
CFG = os.path.join(ASSETS, "GreatWave", "Design45", "Data", "ds45_comfort.json")
BOATS43 = os.path.join(ASSETS, "GreatWave", "Design43", "Data", "ds43_boats.json")
R44 = os.path.join(REPO, "Unity", "Build", "Design", "44", "steer", "unity", "ds44_unity_report.json")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
RIGS = ["main", "L0", "L1", "L2", "L3"]
LEV = ["L0", "L1", "L2", "L3"]
MB5 = 5 * 1000 * 1000


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(p, d):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def rel(p):
    return os.path.relpath(p, REPO).replace(os.sep, "/")


def hms(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def r4(x, n=4):
    return round(float(x), n)


def verify(run):
    rows, bad = [], []
    items = {k: v for k, v in run["inputs"].items()}
    items.update({rel(os.path.join(OUT, k)): v for k, v in run["outputs"].items()})
    for k, v in items.items():
        p = os.path.join(REPO, k)
        got = sha(p) if os.path.exists(p) else None
        rows.append(dict(path=k, expected=v, same=got == v))
        if got != v:
            bad.append(k)
    return rows, bad


# ---------------------------------------------------------------- 四元数（x, y, z, w）
def qconj(q):
    return q * np.array([-1.0, -1.0, -1.0, 1.0])


def qmul(a, b):
    ax, ay, az, aw = a.T
    bx, by, bz, bw = b.T
    return np.stack([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz], 1)


def qrot(q, v):
    u = q[..., :3]
    w = q[..., 3:4]
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def qangle(a, b):
    """a から b への回転の角（度）。atan2 で求めるので、単位の長さの誤差（float32）で 0 の回転に床が出ない。"""
    d = qmul(qconj(a), b)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    return np.degrees(2.0 * np.arctan2(np.linalg.norm(d[:, :3], axis=1), np.abs(d[:, 3])))


def qangle_acos(a, b):
    """作る部の ds45_report.py と同じ 2·acos(|a·b|)（比べるためだけ）。"""
    d = np.abs(np.sum(a * b, 1))
    return np.degrees(2.0 * np.arccos(np.clip(d, -1.0, 1.0)))


def rider_csv():
    with open(os.path.join(UNITY, "ds45_rider.csv"), encoding="utf-8") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        rows = list(rd)
    col = {k: i for i, k in enumerate(hdr)}
    cmd = [r[col["cmd"]] for r in rows]
    num = {k: np.array([float(r[i]) if r[i] not in ("", "null") else np.nan for r in rows]) for k, i in col.items() if k != "cmd"}
    return num, cmd


def stats(x):
    x = np.abs(np.asarray(x, np.float64))
    x = x[~np.isnan(x)]
    return dict(max=r4(x.max()), p95=r4(np.percentile(x, 95))) if len(x) else dict(max=None, p95=None)


def recount(cfg):
    r44 = load(R44)
    s_h, s_f = float(r44["handoverS"]), float(r44["formationStartS"])
    t_star = s_f + 12.0
    num, cmd = rider_csv()
    s = num["s"]
    N = len(s)
    be = np.stack([num["bex"], num["bey"], num["bez"]], 1)
    bq = np.stack([num["bqx"], num["bqy"], num["bqz"], num["bqw"]], 1)
    P = {r: np.stack([num[r + "_x"], num[r + "_y"], num[r + "_z"]], 1) for r in RIGS}
    Q = {r: np.stack([num[r + "_qx"], num[r + "_qy"], num[r + "_qz"], num[r + "_qw"]], 1) for r in RIGS}
    gun = float(cfg["seatEyeAboveGunwaleM"])
    secs = dict(steering=(0.0, s_h), approach=(s_h, s_f), formation=(s_f, t_star), hold=(t_star, s[-1] + 1e-6), all=(0.0, s[-1] + 1e-6))
    out = dict(rows=int(N), s_first=r4(s[0]), s_last=r4(s[-1]), handover_s=s_h, formation_start_s=r4(s_f), t_star_s=r4(t_star))

    # 1) 段の移り変わりと座席リセット（主の乗客）
    lvl = num["level"].astype(int)
    ch = np.nonzero(np.diff(lvl))[0] + 1
    out["level_changes"] = [dict(s=r4(s[i], 3), frm="L%d" % lvl[i - 1], to="L%d" % lvl[i]) for i in ch]
    rs = num["resets"].astype(int)
    rch = np.nonzero(np.diff(rs))[0] + 1
    out["resets"] = [dict(s=r4(s[i], 3), count=int(rs[i])) for i in rch]
    out["commands"] = [dict(s=r4(s[i], 3), cmd=c) for i, c in enumerate(cmd) if c]
    out["levels_visited"] = sorted(set("L%d" % v for v in lvl))

    # 2) 段を固定した乗客との一致（切り替えから blendS の後、次の切り替えまで。位置と傾き）
    blend = float(cfg["blendS"])
    edges = [0] + list(ch) + [N]
    same = []
    for a, b in zip(edges[:-1], edges[1:]):
        L = "L%d" % lvl[a]
        m = np.zeros(N, bool)
        m[a:b] = True
        if a > 0:
            m &= s >= s[a] + blend + 1e-6
        if not m.any():
            continue
        same.append(dict(level=L, s0=r4(s[a], 3), s1=r4(s[b - 1], 3), steps=int(m.sum()),
                         pos_max_diff_m=float(np.abs(P["main"][m] - P[L][m]).max()),
                         tilt_max_diff_deg=float(np.abs(num["main_tilt"][m] - num[L + "_tilt"][m]).max())))
    out["main_equals_fixed_level_after_blend"] = same

    # 3) 着座：船の枠で座席の目から測った目の位置（上向き・水平）と船縁の上端（座席の目の 0.149 m 下。設計41）
    bqi = qconj(bq)
    seat = {}
    for r in RIGS:
        e = qrot(bqi, P[r] - be)
        d = {}
        for k, (a, b) in secs.items():
            m = (s >= a) & (s < b)
            u = e[m, 1]
            d[k] = dict(up_min_m=r4(u.min()), up_max_m=r4(u.max()), horiz_max_m=r4(np.hypot(e[m, 0], e[m, 2]).max()),
                        below_gunwale_top_fraction=r4(np.mean(u < -gun)))
        seat[r] = d
    out["seated_boat_frame"] = seat

    # 4) 1 段（1/120 s）の回転：atan2 の角と、作る部の 2·acos の角（床の確かめ）
    rot = {}
    for r in RIGS:
        a1 = qangle(Q[r][:-1], Q[r][1:])
        a2 = qangle_acos(Q[r][:-1], Q[r][1:])
        rot[r] = dict(max_deg_atan2=r4(a1.max(), 5), p95_deg_atan2=r4(np.percentile(a1, 95), 5), max_deg_acos=r4(a2.max(), 5),
                      steps_over_0p01deg_atan2=int(np.sum(a1 > 0.01)))
    # 主の乗客：座席リセットの段の角と、それ以外の段の最大
    ra = np.concatenate([[0.0], qangle(Q["main"][:-1], Q["main"][1:])])
    reset_steps = [int(i) for i in rch]
    rot["main_reset_snaps_deg"] = [r4(ra[i], 3) for i in reset_steps]
    mm = np.ones(N, bool)
    mm[reset_steps] = False
    rot["main_max_deg_except_reset_steps"] = r4(ra[mm].max(), 5)
    wins = []
    for i in ch:
        m = (s >= s[i] - 0.1) & (s <= s[i] + blend + 0.25)
        m &= mm
        fixed = max(float(np.concatenate([[0.0], qangle(Q[L][:-1], Q[L][1:])])[m].max()) for L in ("L%d" % lvl[i - 1], "L%d" % lvl[i]))
        wins.append(dict(s=r4(s[i], 3), main_max_deg=r4(ra[m].max(), 5), fixed_levels_max_deg=r4(fixed, 5)))
    rot["switch_windows"] = wins
    out["rotation_per_step"] = rot

    # 5) HMD Camera の世界の位置 = RiderComfortRoot（HMD Camera の局所の姿勢が 0 のまま、XR Origin −1.2 と Camera Offset +1.2 で打ち消す）
    out["hmd_world_minus_root_max_m"] = {r: float(np.abs(np.stack([num[r + "_cx"], num[r + "_cy"], num[r + "_cz"]], 1) - P[r]).max()) for r in RIGS}

    # 6) 30 Hz の上下の加速度（各コマの終わりの段の位置の 2 階差分）
    fr = np.arange(3, N, 4)
    s30 = s[fr]
    acc, acch = {}, {}
    for k, p in [("boat", be)] + [(r, P[r]) for r in RIGS]:
        a3 = np.full((len(fr), 3), np.nan)
        a3[1:-1] = (p[fr][2:] - 2.0 * p[fr][1:-1] + p[fr][:-2]) * 900.0
        acc[k] = {sk: stats(a3[(s30 >= a0) & (s30 < b0), 1]) for sk, (a0, b0) in secs.items()}
        ah = np.hypot(a3[:, 0], a3[:, 2])
        acch[k] = {sk: stats(ah[(s30 >= a0) & (s30 < b0)]) for sk, (a0, b0) in secs.items()}
    out["acc_vert_30hz_mps2"] = acc
    out["acc_horiz_30hz_mps2"] = acch

    # 7) 向きと傾き
    yaw = {r: num[r + "_yaw"] for r in RIGS}
    st = s < s_h
    seat_yaw = num["boatYaw"] + float(cfg["seatYawOffsetDeg"])
    out["yaw"] = dict(
        boat_turn_during_steering_deg=r4(num["boatYaw"][st].max() - num["boatYaw"][st].min(), 3),
        L0_range_steering_deg=r4(np.ptp(yaw["L0"][st]), 5), L1_range_steering_deg=r4(np.ptp(yaw["L1"][st]), 5),
        L2_minus_seat_facing_max_abs_deg=r4(np.abs(yaw["L2"] - seat_yaw).max(), 5),
        L3_minus_seat_facing_max_abs_deg=r4(np.abs(yaw["L3"] - seat_yaw).max(), 5))
    out["tilt_max_deg"] = {r: r4(np.nanmax(num[r + "_tilt"]), 4) for r in RIGS}
    out["boat_tilt_max_deg"] = r4(np.nanmax(num["boatTilt"]), 3)

    # 8) t* の目のずれ（30 Hz のコマで t* に最も近いもの）と終わり
    i = int(fr[np.argmin(np.abs(s30 - t_star))])
    at = dict(s=r4(s[i], 4))
    for r in RIGS:
        e = qrot(bqi[i:i + 1], (P[r][i] - be[i])[None, :])[0]
        at[r] = dict(norm_m=r4(np.linalg.norm(P[r][i] - be[i])), boat_frame_m=[r4(v) for v in e],
                     yaw_minus_seat_facing_deg=r4(yaw[r][i] - seat_yaw[i], 3))
    out["at_tstar"] = at
    out["at_end_norm_m"] = {r: r4(np.linalg.norm(P[r][-1] - be[-1])) for r in RIGS}

    # 9) 設計30 の座席の上下（原画の姿勢のまま鉛直に動かす。30 Hz）
    with open(os.path.join(UNITY, "ds45_heave30.csv"), encoding="utf-8") as f:
        rd = csv.reader(f)
        h = next(rd)
        hv = np.array([[float(x) for x in rr] for rr in rd])
    H = {k: hv[:, j] for j, k in enumerate(h)}
    tt = H["t"]
    dt = np.diff(tt)
    mid = [b for b in load(BOATS43)["boats"] if b["key"] == "boat_mid"][0]
    q0 = np.array(mid["rootRot"], np.float64)[None, :]
    up0 = qrot(q0, np.array([[0.0, 1.0, 0.0]]))[0]
    hb = np.stack([H["bex"], H["bey"], H["bez"]], 1)

    def acc_h(y):
        a = np.full(len(y), np.nan)
        a[1:-1] = (y[2:] - 2.0 * y[1:-1] + y[:-2]) / (dt[1:] * dt[:-1])
        return a
    ab = acc_h(H["bey"])
    heave = dict(frames=int(len(tt)), dt_s=[r4(dt.min(), 6), r4(dt.max(), 6)], boat=dict(acc=stats(ab), range_y_m=r4(np.ptp(H["bey"]))),
                 boat_painting_pose_tilt_deg=r4(np.degrees(np.arccos(np.clip(up0[1], -1, 1))), 3))
    for L in LEV:
        p = np.stack([H[L + "_x"], H[L + "_y"], H[L + "_z"]], 1)
        a = acc_h(H[L + "_y"])
        e = qrot(np.repeat(qconj(q0), len(tt), 0), p - hb)
        heave[L] = dict(acc=stats(a), ratio_to_boat=r4(np.nanmax(np.abs(a)) / np.nanmax(np.abs(ab))),
                        up_min_m=r4(e[:, 1].min()), up_max_m=r4(e[:, 1].max()), below_gunwale_top_fraction=r4(np.mean(e[:, 1] < -gun)),
                        tilt_max_deg=r4(H[L + "_tilt"].max()))
    out["heave30"] = heave
    return out


def run2_seated(cfg):
    """修正の前（run2 の控え run2/ds45_rider_run2.csv）の着座：形成の間の船の枠の上向きの成分と、船縁の上端より下の割合。"""
    p = os.path.join(OUT, "run2", "ds45_rider_run2.csv")
    with open(p, encoding="utf-8") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        rows = list(rd)
    col = {k: i for i, k in enumerate(hdr)}

    def c(k):
        return np.array([float(r[col[k]]) for r in rows])
    r44 = load(R44)
    s_f = float(r44["formationStartS"])
    s = c("s")
    m = (s >= s_f) & (s < s_f + 12.0)
    be = np.stack([c("bex"), c("bey"), c("bez")], 1)
    bq = np.stack([c("bqx"), c("bqy"), c("bqz"), c("bqw")], 1)
    gun = float(cfg["seatEyeAboveGunwaleM"])
    out = dict(file=rel(p), sha256=sha(p))
    for r in RIGS:
        e = qrot(qconj(bq), np.stack([c(r + "_x"), c(r + "_y"), c(r + "_z")], 1) - be)
        u = e[m, 1]
        out[r] = dict(up_min_m=r4(u.min()), up_max_m=r4(u.max()), below_gunwale_top_fraction=r4(np.mean(u < -gun)),
                      above_0p3m_fraction=r4(np.mean(u > 0.3)))
    return out


def key_frames():
    """修正の前後の図の 2 つの時刻（s 86.6667・91.6667）で、目を船の枠で座席の目から測った値（run2 の控えと run3）。"""
    out = {}
    for tag, p in (("run2", os.path.join(OUT, "run2", "ds45_rider_run2.csv")), ("run3", os.path.join(UNITY, "ds45_rider.csv"))):
        with open(p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        s = np.array([float(r["s"]) for r in rows])
        d = {}
        for target in (86.6667, 91.6667):
            r = rows[int(np.argmin(np.abs(s - target)))]
            be = np.array([float(r["bex"]), float(r["bey"]), float(r["bez"])])
            bq = np.array([[float(r[k]) for k in ("bqx", "bqy", "bqz", "bqw")]])
            e = {L: [r4(v, 3) for v in qrot(qconj(bq), (np.array([float(r[L + "_x"]), float(r[L + "_y"]), float(r[L + "_z"])]) - be)[None, :])[0]] for L in LEV}
            d["s_%.4f" % float(r["s"])] = dict(boat_tilt_deg=r4(float(r["boatTilt"]), 2), eye_boat_frame_xyz_m=e)
        out[tag] = d
    return out


def scene_check():
    txt = open(SCENE, encoding="utf-8").read()
    base = open(BASE_SCENE, encoding="utf-8").read()
    gm = {}
    for dp, dn, fn in os.walk(ASSETS):
        for f in fn:
            if f.endswith(".meta"):
                p = os.path.join(dp, f)
                with open(p, encoding="utf-8", errors="replace") as fh:
                    g = re.search(r"^guid: ([0-9a-f]{32})", fh.read(), re.M)
                if g:
                    gm[g.group(1)] = rel(p[:-5])
    mine = set(re.findall(r"guid: ([0-9a-f]{32})", txt))
    bset = set(re.findall(r"guid: ([0-9a-f]{32})", base))
    return dict(path=rel(SCENE), sha256=sha(SCENE), bytes=os.path.getsize(SCENE),
                stepInLateUpdate=re.findall(r"stepInLateUpdate: (\d)", txt), readInput=re.findall(r"readInput: (\d)", txt),
                stepInFixedUpdate=re.findall(r"stepInFixedUpdate: (\d)", txt), startLevel=re.findall(r"startLevel: (-?\d)", txt),
                guids=len(mine), in_base_scene=len(mine & bset),
                not_in_base=[dict(guid=g, path=gm.get(g, "（Assets の外。Unity の組み込み・パッケージ）")) for g in sorted(mine - bset)])


def compare(rc, bm):
    """記録の数え直しと作る部の metrics.json の差（同じ量だけ）。"""
    d = {}
    bl = bm["run44Replay"]["byLevel"]
    for k in ["boat"] + RIGS:
        for sk, bk in (("steering", "steering_0_70"), ("formation", "formation_sf_tstar"), ("hold", "hold_tstar_end")):
            d["accVertMax_%s_%s" % (k, sk)] = abs(rc["acc_vert_30hz_mps2"][k][sk]["max"] - bl[k][bk]["accVert_mps2"]["max"])
            d["accHorizMax_%s_%s" % (k, sk)] = abs(rc["acc_horiz_30hz_mps2"][k][sk]["max"] - bl[k][bk]["accHoriz_mps2"]["max"])
    for r in RIGS:
        a = rc["seated_boat_frame"][r]["all"]
        b = bl[r]["all"]["eyeInBoatFrameUp_m"]
        d["seatUpMin_%s" % r] = abs(a["up_min_m"] - b["min"])
        d["seatUpMax_%s" % r] = abs(a["up_max_m"] - b["max"])
    h = bm["backlog85_heaveScale"]["heave30"]
    d["heave30_boat_max"] = abs(rc["heave30"]["boat"]["acc"]["max"] - h["boat"]["accVert_mps2"]["max"])
    for L in LEV:
        d["heave30_%s_max" % L] = abs(rc["heave30"][L]["acc"]["max"] - h[L]["accVert_mps2"]["max"])
    for r in RIGS:
        d["tstar_norm_%s" % r] = abs(rc["at_tstar"][r]["norm_m"] - bm["run44Replay"]["atTstar"][r]["eyeFromSeatEye_m"])
    return {k: round(float(v), 6) for k, v in d.items()}


def small_grid_mp4(src, dst):
    """4 段の並べの動画を 1280 × 720 に縮めて 5 MB の下へ（crf を上げて試す）。"""
    for crf in (26, 28, 30, 32, 34):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vf", "scale=1280:720:flags=area", "-c:v", "libx264", "-preset", "slow",
                        "-crf", str(crf), "-pix_fmt", "yuv420p", "-an", dst], check=True)
        if os.path.getsize(dst) <= 4.8 * 1000 * 1000:
            return dict(crf=crf, bytes=os.path.getsize(dst), size="1280x720")
    raise RuntimeError("縮めても 5 MB を超える")


def file_times():
    items = ["Unity/Build/Design/45", "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortConfig.cs",
             "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortSolver.cs", "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortInput.cs",
             "Unity/Assets/GreatWave/Design45/Scripts/DS45RiderComfort.cs", "Unity/Assets/GreatWave/Design45/Data/ds45_comfort.json",
             "Unity/Assets/GreatWave/Design45/Editor/DS45ComfortTest.cs", "Tools/GWWaveGen/ds45/run_ds45_unity.ps1",
             "Tools/GWWaveGen/ds45/ds45_codecheck.py", "Unity/Build/Design/45/comfort/logs/unity_ds45_run1.log",
             "Unity/Build/Design/45/comfort/run1", "Tools/GWWaveGen/ds45/ds45_report.py",
             "Unity/Build/Design/45/comfort/logs/unity_ds45_run2.log", "Unity/Build/Design/45/comfort/run2",
             "Unity/Build/Design/45/comfort/unity/frames", "Unity/Build/Design/45/comfort/logs/unity_ds45_run3.log",
             "Unity/Assets/GreatWave/Design45/Scenes/DS45_Comfort.unity", "Unity/Build/Design/45/comfort/codecheck.json",
             "Unity/Build/Design/45/comfort/metrics.json", "Unity/Build/Design/45/comfort/ds45_levels_grid_30fps.mp4",
             "Unity/Build/Design/45/comfort/run.json"]
    out = {}
    for p in items:
        a = os.path.join(REPO, p)
        if os.path.exists(a):
            st = os.stat(a)
            out[p] = dict(created=hms(st.st_ctime), modified=hms(st.st_mtime))
    return out


def main():
    t0 = time.time()
    os.makedirs(EVD, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    run_b = load(os.path.join(OUT, "run.json"))
    rows, bad = verify(run_b)
    if bad:
        print("SHA-256 が作る部の run.json と違う：", bad)
        sys.exit(1)
    met_b = load(os.path.join(OUT, "metrics.json"))
    cfg = load(CFG)
    rc = recount(cfg)
    rc["scene"] = scene_check()
    rc["run2_before_fix_seated_formation"] = run2_seated(cfg)
    rc["before_after_frames_boat_frame"] = key_frames()
    cmp_ = compare(rc, met_b)

    copies = {
        "fig_ds45_comfort.png": os.path.join(OUT, "fig_ds45_comfort.png"),
        "stills_ds45_levels.png": os.path.join(OUT, "stills_ds45_levels.png"),
        "fix_ds45_seated_before_after.png": os.path.join(OUT, "fix_ds45_seated_before_after.png"),
        "stereo_ds45_mock.png": os.path.join(OUT, "stereo_ds45_mock.png"),
        "ds45_main_switching_30fps.mp4": os.path.join(OUT, "ds45_main_switching_30fps.mp4"),
        "ds45_comfort_metrics.json": os.path.join(OUT, "metrics.json"),
        "ds45_comfort_run.json": os.path.join(OUT, "run.json"),
        "ds45_codecheck.json": os.path.join(OUT, "codecheck.json"),
        "ds45_unity_report.json": os.path.join(UNITY, "ds45_unity_report.json"),
    }
    for dst, src in copies.items():
        shutil.copyfile(src, os.path.join(EVD, dst))
    grid = small_grid_mp4(os.path.join(OUT, "ds45_levels_grid_30fps.mp4"), os.path.join(EVD, "ds45_levels_grid_30fps.mp4"))
    for f in ("fig_ds45_comfort.png", "stills_ds45_levels.png", "fix_ds45_seated_before_after.png", "stereo_ds45_mock.png"):
        assert cv2.imread(os.path.join(EVD, f)).shape[:2] == (1080, 1920), f
    for f in ("ds45_main_switching_30fps.mp4", "ds45_levels_grid_30fps.mp4"):
        assert os.path.getsize(os.path.join(EVD, f)) <= MB5, f

    dump(os.path.join(EVD, "ds45_record_recount.json"), dict(
        schema="GreatWave.DS45.record_recount/1", number="設計45",
        note_ja="記録の道具 ds45_record.py の数え直し。作る部の ds45_report.py・ds45_codecheck.py は使わず、unity/ds45_rider.csv・unity/ds45_heave30.csv・場面のファイルから数えた。"
                "1 段の回転は四元数の差の角を atan2 で求めた（作る部の 2·acos(|a·b|) は float32 の四元数の長さの誤差で、回っていない乗客にも 1 段 0.037° の床が出る）",
        recount=rc, diff_vs_builder_metrics=cmp_, grid_mp4_reencode=grid))

    gates = met_b["gates"]
    metrics = dict(
        schema="GreatWave.DS45.record_metrics/1", number="設計45", title_ja="乗客の揺れを一種類ずつ調整する",
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        evidence_kind_ja="PC の Unity 6000.4.3f1 batchmode（RTX 3080、Direct3D11）。船は設計44 の run3 の記録を入れただけ（物理は解いていない）。Input System の仮想の機器、numpy の測定、進行役の独立の検査。HMD 実機ではない。利用者は確かめていない",
        plan_ja="計画 §2.4 設計45：RiderComfortRoot に4段（水平維持 → 弱い上下動 → 旋回 → 傾斜）の設定。頭部の追跡は上書きしない（設計書 §7.3 の構造）。利用者の試遊記録（PS VR2、約1時間）",
        min_acceptance_ja="4段を切り替えられる。HMD Camera のローカル姿勢に手を入れていない（コードの検査）。H5・H7 の記録",
        acceptance=[dict(item=g["item"], result=g["result"]) for g in gates],
        acceptance_record=dict(
            switch_levels=dict(result="合格", level_changes=rc["level_changes"], resets=rc["resets"],
                               main_equals_fixed_level_after_blend_max_pos_m=max(x["pos_max_diff_m"] for x in rc["main_equals_fixed_level_after_blend"]),
                               rotation_per_step=rc["rotation_per_step"]),
            hmd_local_pose=dict(result="合格", runtime_writes=gates[1]["value"]["runtimeWrites"], hmd_checks=gates[1]["value"]["hmdChecks"],
                                hmd_local_pos_max_change=gates[1]["value"]["hmdLocalPosMaxAbsChange"], hmd_local_rot_max_deg=gates[1]["value"]["hmdLocalRotMaxAngleDeg"],
                                hmd_world_minus_root_max_m=rc["hmd_world_minus_root_max_m"]),
            h5=dict(result="保留", stand_in_ja="PC の代わり：4 段の並べの動画（頭を 30° 上げた試験だけのカメラ）、Mock の両目の静止画（±0.032 m、s 84・86.67・t*・93.6）"),
            h7=dict(result="保留（計算の検査は済み。実機は未検証）", recenter=gates[4]["value"]),
            playtest=dict(result="保留", note_ja="PS VR2 は未導入（利用者の手）")),
        seated_fix_gate=dict(result="合格（修正の回の確認。計画の最小の受入の外）", record=rc["seated_boat_frame"],
                             run2_before_fix_ja=gates[2]["value"]["run2BeforeFix"]["noteJa"],
                             run2_before_fix_record=rc["run2_before_fix_seated_formation"]),
        backlog85=dict(result="記録のみ", kV=met_b["backlog85_heaveScale"]["kV"], heave30=rc["heave30"], replay_acc_vert_30hz=rc["acc_vert_30hz_mps2"],
                       replay_acc_horiz_30hz=rc["acc_horiz_30hz_mps2"],
                       note_ja="修正の後（run3）の船の枠の頭打ちで、保持（t* の後 2 s、船が約 150°/s で回る）の L0 の水平の加速度の最大は 22.87 m/s²（船 14.80 の 1.54 倍。run1・run2 は 15.28）。記録の時に見つけた限界"),
        at_tstar=rc["at_tstar"],
        fix_rounds=dict(count=1,
                        builder_run2_ja="作る部の中の run2：run1（omegaV 2.5、速度の先回り 1、世界の上下で頭打ち 0.45 m）は設計30 の上下の L0 の最大を 5.97 → 5.66 m/s² しか下げなかったので、betaV を足し omegaV 1.0・betaV 0.5・頭打ち 0.6 m にした（2.36 m/s²）。作る部はこれを修正の回と書いたが、自分で決めた調整の範囲の中の直しで、検査の指摘への修正ではない",
                        fix01_ja="検査の後の run3（Q26 の修正 1 回）：run2 は形成の間に目が船の枠で −0.58〜+0.56 m 動き、形成の 54 %（L0）で船縁の上端より下へ沈んだ。頭打ちを船の枠の上 0.10・下 0.10・水平 0.25 m に移し、omegaV を 4.0 にした（D45-10）。目は全段で ±0.10 m、船縁の上端より下 0 %"),
        record_recount=dict(file="Docs/Evidence/Design/45/ds45_record_recount.json", diff_vs_builder_max=float(max(cmp_.values())), diff=cmp_),
        builder_sha256_verified=dict(files=len(rows), all_same=not bad),
        time=dict(box_ja="Q26 の日程で 2 時間（計画 §2.6 の［Q26］の表、10/3 の行。計画の時間枠は ≤0.5日＋利用者の試遊）", file_times=file_times(),
                  builder_report_ja="作る部の報告は「2 時間の内の約 27 分（12:11〜12:38 ごろ）」、修正の回はファイルの時刻で 12:47〜13:00",
                  unity_in_run_s=dict(run1=57.6, run2=59.3, run3=68.9), report_s=run_b["reportSeconds"]),
        hmd_ja="保留（PS VR2 の導入は利用者の手）。H5・H7・約 1 時間の試遊・PS VR2 の Sense・手で押す機器・Play モードの頭部追跡は確かめていない",
        painting_view_ja="原画視点の場面（DS39_Paper.unity）は開いていない。守るファイル 19 の SHA-256 は 3 回の実行の前後で同じ。計画 §2.0 の回帰は対象外",
        evidence=sorted(set(os.listdir(EVD) + ["metrics.json", "run.json"])),
    )
    dump(os.path.join(EVD, "metrics.json"), metrics)

    ev_sha = {rel(os.path.join(EVD, f)): sha(os.path.join(EVD, f)) for f in sorted(os.listdir(EVD)) if f != "run.json"}
    code = {}
    for root in (HERE, os.path.join(ASSETS, "GreatWave", "Design45")):
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d != "__pycache__"]
            for f in sorted(fn):
                code[rel(os.path.join(dp, f))] = sha(os.path.join(dp, f))
    code["Unity/Assets/GreatWave/Design45.meta"] = sha(os.path.join(ASSETS, "GreatWave", "Design45.meta"))
    run = dict(
        schema="GreatWave.DS45.record_run/1", number="設計45", created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        tools=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, unity="6000.4.3f1（batchmode。記録では使っていない）",
                   ffmpeg=FFMPEG + "（作る部の動画と、記録の 4 段の並べの縮めた写し）", input_system="com.unity.inputsystem（Unity/Packages/manifest.json）"),
        builder_commands=run_b["commands"],
        record_commands=["py -3.10 -B Tools/GWWaveGen/ds45/ds45_record.py",
                         "py -3.10 -B Unity/Build/Design/45/record/ds45_commit_scan.py（コミットの一覧の点検。Git 対象外）"],
        builder_inputs_sha256=run_b["inputs"], builder_outputs_sha256=run_b["outputs"],
        scene=dict(path=rc["scene"]["path"], sha256=rc["scene"]["sha256"], bytes=rc["scene"]["bytes"]),
        grid_mp4_reencode=grid, code_sha256=code, evidence_sha256=ev_sha,
        seconds=round(time.time() - t0, 1),
        note_ja="SHA-256 は作業の木のバイトの値。Unity のコマの JPG（5 × 2,811 枚と Mock の両目 32 枚）とログは Git 対象外で SHA-256 を取っていない")
    dump(os.path.join(EVD, "run.json"), run)
    print(json.dumps(dict(verified=len(rows), bad=bad, diff_max=max(cmp_.values()), grid=grid, seconds=run["seconds"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
