# -*- coding: utf-8 -*-
"""設計44：操船の模型（numpy）。C# の DS44BoatSteer・DS44Trajectory と同じ式を別に書いたもの。

- 範囲：painting frame（原点 = 原画の座席の船の根の xz、u = 原画の船首の向き、v = 右舷）の角を丸めた長方形の符号付き距離 d（外が正）。
- 水平の 3 自由度の模型（x, z, ψ）：推力・抵抗・首振り・停止・押し戻し（ds44_steer.json の dyn・range）。浮力・上下・横揺れは含めない。
  試験の入力の筋書き（test.segments）を前もって流し、筋書きの時刻と範囲の縁への届き方を確かめる（計画用。Unity の結果の代わりにはしない）。
- 固定の軌道：3 次 Bezier の道＋5 次の時間の式 s(t)、T の探索、向きのなめらかなつなぎ（traj）。Unity の記録の数え直しにも使う。
座標：Unity の世界（m、Y 上）。ψ は +z から +x へ測る首の向き（度、yawDeg と同じ。上から見て時計回りが正）。
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARAMS = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design44", "Data", "ds44_steer.json")
OUT = os.path.join(REPO, "Unity", "Build", "Design", "44", "steer")


def load_params(path=PARAMS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


class Frame:
    """painting frame ⇔ 世界（xz）。"""

    def __init__(self, P):
        p = P["painting"]
        self.o = np.array([p["x"], p["z"]], np.float64)
        self.yaw = float(p["yawDeg"])
        r = math.radians(self.yaw)
        self.f = np.array([math.sin(r), math.cos(r)])      # 船首（x, z）
        self.s = np.array([math.cos(r), -math.sin(r)])     # 右舷（x, z）

    def to_world(self, u, v):
        return self.o + u * self.f + v * self.s

    def to_uv(self, xz):
        d = np.asarray(xz, np.float64) - self.o
        return float(d @ self.f), float(d @ self.s)


class Range:
    def __init__(self, P, frame):
        R = P["range"]
        self.R = R
        self.fr = frame
        self.c = np.array([(R["uMin"] + R["uMax"]) / 2, (R["vMin"] + R["vMax"]) / 2])
        self.h = np.array([(R["uMax"] - R["uMin"]) / 2, (R["vMax"] - R["vMin"]) / 2])
        self.r = R["cornerRadius"]

    def sdf_uv(self, u, v):
        q = np.abs(np.array([u, v]) - self.c) - (self.h - self.r)
        return float(np.linalg.norm(np.maximum(q, 0.0)) + min(max(q[0], q[1]), 0.0) - self.r)

    def sdf(self, xz):
        u, v = self.fr.to_uv(xz)
        return self.sdf_uv(u, v)

    def grad(self, xz, e=0.01):
        x = np.asarray(xz, np.float64)
        gx = (self.sdf(x + [e, 0]) - self.sdf(x - [e, 0])) / (2 * e)
        gz = (self.sdf(x + [0, e]) - self.sdf(x - [0, e])) / (2 * e)
        g = np.array([gx, gz])
        n = np.linalg.norm(g)
        return g / n if n > 1e-9 else g

    def phi(self, d):
        b = self.R["bandM"]
        if d <= 0:
            return smoothstep((d + b) / b)
        return 1.0 + d / b

    def outline_uv(self, n=256):
        """縁の点（u, v）を一周。"""
        pts = []
        u0, u1 = self.c[0] - self.h[0], self.c[0] + self.h[0]
        v0, v1 = self.c[1] - self.h[1], self.c[1] + self.h[1]
        r = self.r
        corners = [(u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180), (u1 - r, v0 + r, 270)]
        for cu, cv, a0 in corners:
            for k in range(n // 4 + 1):
                a = math.radians(a0 + 90.0 * k / (n // 4))
                pts.append((cu + r * math.cos(a), cv + r * math.sin(a)))
        pts.append(pts[0])
        return np.array(pts)


# ---------------------------------------------------------------- 固定の軌道
class Trajectory:
    """引き継ぎの状態 → 原画の位置・向きへ速さ 0 で着く道と速さの表（C# の DS44Trajectory と同じ手順）。

    道：向きの差 |α|（船の進む向きと、原画の位置への方位の差）が arcTriggerDeg より大きい時は、半径 arcRadiusM の円弧で
    目標の側へ回り、方位の差が arcExitDeg 以下になった所から 3 次 Bezier（腕 = max(bezierK·D, armMinM)）で原画の位置と向きへ。
    速さ：道の曲がり κ から v ≤ min(vCap, yawRateMax/|κ|)、加速 aMax・減速 aDecMax の前後の走査（始め v0、終わり 0）。
    所要 T が formationS + leadMinS より短い時は vCap を二分法で下げて T を延ばす。
    """

    def __init__(self, P, p0, vel0, yaw0_deg, r0_degps, a0_along, frame):
        tp = P["traj"]
        self.tp = tp
        self.p0 = np.asarray(p0, np.float64)
        self.p1 = frame.o.copy()
        h1 = frame.f.copy()
        sp = float(np.linalg.norm(vel0))
        f0 = np.array([math.sin(math.radians(yaw0_deg)), math.cos(math.radians(yaw0_deg))])
        if sp >= tp["tangentFromVelocityMinSpeed"]:
            h0 = np.asarray(vel0, np.float64) / sp
            v0 = sp
        else:
            h0 = f0
            v0 = max(0.0, float(np.dot(vel0, f0)))
        self.v0 = v0
        ds = tp["dsM"]
        pts = [self.p0.copy()]
        hd = math.degrees(math.atan2(h0[0], h0[1]))
        # 円弧
        to = self.p1 - self.p0
        alpha = wrap_deg(hd - math.degrees(math.atan2(to[0], to[1])))
        self.arc_deg = 0.0
        if abs(alpha) > tp["arcTriggerDeg"]:
            rmax = math.radians(tp["yawRateMaxDeg"])
            R = max(tp["arcRadiusM"], v0 / rmax * 1.15)
            Lc = max(tp["arcEntryM"], v0 * tp["arcEntryS"])
            sgn = -1.0 if alpha > 0 else 1.0          # 目標の側へ回る（alpha > 0 なら ψ を減らす）
            p = self.p0.copy()
            h = hd
            turned = 0.0
            s_arc = 0.0
            self.arc_R = R
            err_prev = 1e9
            while True:
                s_arc += ds
                k = min(s_arc / Lc, 1.0) / R            # 曲がりを 0 から 1/R へ増やす（首振りの速さが跳ばない）
                dh = math.degrees(k * ds) * sgn
                h += dh
                turned += dh
                p = p + ds * np.array([math.sin(math.radians(h)), math.cos(math.radians(h))])
                pts.append(p.copy())
                to = self.p1 - p
                err = abs(wrap_deg(h - math.degrees(math.atan2(to[0], to[1]))))
                if err <= tp["arcExitDeg"] or (s_arc > Lc and abs(turned) > 90.0 and err > err_prev + 1e-9) or abs(turned) >= 200.0:
                    break                               # 向きが合った／目標が回る円の内側で差が縮まなくなった／半周
                err_prev = err
            self.arc_deg = turned
            hd = h
        pa = pts[-1]
        ha = np.array([math.sin(math.radians(hd)), math.cos(math.radians(hd))])
        D = float(np.linalg.norm(self.p1 - pa))
        arm1 = max(tp["bezierK"] * D, tp["armMinM"])
        arm0 = max(arm1, v0 * tp["armTimeS"]) if self.arc_deg == 0 else arm1
        C = np.array([pa, pa + arm0 * ha, self.p1 - arm1 * h1, self.p1])
        q = np.linspace(0, 1, 4097)[:, None]
        B = (1 - q) ** 3 * C[0] + 3 * (1 - q) ** 2 * q * C[1] + 3 * (1 - q) * q ** 2 * C[2] + q ** 3 * C[3]
        seg = np.linalg.norm(np.diff(B, axis=0), axis=1)
        Sb = np.concatenate([[0], np.cumsum(seg)])
        nb = max(2, int(math.ceil(Sb[-1] / ds)))
        sb = np.linspace(0, Sb[-1], nb + 1)[1:]
        Bx = np.interp(sb, Sb, B[:, 0])
        Bz = np.interp(sb, Sb, B[:, 1])
        pts.extend(np.stack([Bx, Bz], 1))
        X = np.array(pts)
        seg = np.linalg.norm(np.diff(X, axis=0), axis=1)
        self.S = np.concatenate([[0], np.cumsum(seg)])
        self.X = X
        self.L = float(self.S[-1])
        d = np.diff(X, axis=0)
        psi_seg = np.degrees(np.unwrap(np.arctan2(d[:, 0], d[:, 1])))
        psi = np.concatenate([[psi_seg[0]], (psi_seg[:-1] + psi_seg[1:]) / 2, [psi_seg[-1]]])
        # 始めと終わりの向きを正確に
        psi[0] = hd if self.arc_deg == 0 else math.degrees(math.atan2(h0[0], h0[1]))
        psi = psi[0] + np.degrees(np.unwrap(np.radians(psi - psi[0])))
        psi[-1] = psi[-2] + wrap_deg(frame.yaw - psi[-2])
        self.psi = psi
        self.kappa = np.gradient(np.radians(psi), self.S)                 # rad/m
        # 速さの表
        self.T = None
        rmax = math.radians(tp["yawRateMaxDeg"])
        def plan(vcap):
            vl = np.minimum(vcap, rmax / np.maximum(np.abs(self.kappa), 1e-9))
            n = len(self.S)
            vb = np.empty(n)
            vb[-1] = 0.0
            for i in range(n - 2, -1, -1):
                h = self.S[i + 1] - self.S[i]
                vb[i] = min(vl[i], math.sqrt(vb[i + 1] ** 2 + 2 * tp["aMax"] * h))
            vf = np.empty(n)
            vf[0] = v0
            for i in range(n - 1):
                h = self.S[i + 1] - self.S[i]
                up = math.sqrt(vf[i] ** 2 + 2 * tp["aMax"] * h)
                dn = math.sqrt(max(vf[i] ** 2 - 2 * tp["aDecMax"] * h, 0.0))
                vf[i + 1] = max(min(vb[i + 1], up), dn)
            vf[-1] = 0.0
            dt = 2 * np.diff(self.S) / np.maximum(vf[:-1] + vf[1:], 1e-6)
            t = np.concatenate([[0], np.cumsum(dt)])
            return vf, t
        vcap = tp["vMax"]
        v, t = plan(vcap)
        Treq = tp["formationS"] + tp["leadMinS"]
        if t[-1] < Treq:
            lo, hi = 0.02, vcap
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                v, t = plan(mid)
                if t[-1] < Treq:
                    hi = mid
                else:
                    lo = mid
            v, t = plan(lo)
            vcap = lo
        self.vcap = vcap
        self.v = v
        self.t = t
        self.T = float(t[-1])
        self.lead = self.T - tp["formationS"]
        # 向きのつなぎ（横滑りの角と首振りの速さの差を yawBlendS でなめらかに 0 へ）
        self.beta0 = wrap_deg(yaw0_deg - self.psi[0])
        self.c_rate = r0_degps - math.degrees(self.kappa[0]) * v0
        self.a_plan0 = float((v[1] ** 2 - v[0] ** 2) / (2 * max(self.S[1] - self.S[0], 1e-9)))

    def blend(self, t):
        Tb = self.tp["yawBlendS"]
        x = min(max(t / Tb, 0.0), 1.0)
        g = 1.0 - x * x * (3 - 2 * x)
        return (self.beta0 + self.c_rate * t) * g

    def eval(self, t):
        """(位置 xz, 速度 xz, 向き ψ 度, 首振り 度/s, 弧長 s, 速さ)"""
        tt = min(max(t, 0.0), self.T)
        s = float(np.interp(tt, self.t, self.S))
        sp = float(np.interp(tt, self.t, self.v)) if t < self.T else 0.0
        pos = np.array([np.interp(s, self.S, self.X[:, 0]), np.interp(s, self.S, self.X[:, 1])])
        psi_p = float(np.interp(s, self.S, self.psi))
        tan = np.array([math.sin(math.radians(psi_p)), math.cos(math.radians(psi_p))])
        e = 1e-3
        yaw = psi_p + self.blend(tt)
        yaw_rate = math.degrees(float(np.interp(s, self.S, self.kappa))) * sp + (self.blend(tt + e) - self.blend(max(tt - e, 0))) / (tt + e - max(tt - e, 0))
        if t >= self.T:
            yaw_rate = 0.0
        return pos, tan * sp, yaw, yaw_rate, s, sp


# ---------------------------------------------------------------- 水平の模型（計画用）
class Planar:
    def __init__(self, P, mass, inertia_y, frame, rng):
        self.P = P
        self.m = mass
        self.I = inertia_y
        self.fr = frame
        self.rng = rng
        d = P["dyn"]
        self.a_fwd = d["dragLinPerS"] * d["vMaxFwd"] + d["dragQuadPerM"] * d["vMaxFwd"] ** 2
        self.th = 0.0
        self.tu = 0.0

    def forces(self, pos, vel, yaw_deg, w_degps, thr_in, turn_in, stop, dt):
        d = self.P["dyn"]
        k = dt / max(d["inputLagS"], 1e-6)
        self.th += (thr_in - self.th) * min(k, 1.0)
        self.tu += (turn_in - self.tu) * min(k, 1.0)
        r = math.radians(yaw_deg)
        f = np.array([math.sin(r), math.cos(r)])
        s = np.array([math.cos(r), -math.sin(r)])
        u = float(vel @ f)
        v = float(vel @ s)
        F = np.zeros(2)
        N = 0.0
        w = math.radians(w_degps)
        if stop:
            ab = -d["brakePerS"] * u
            ab = max(-d["brakeAccelMax"], min(d["brakeAccelMax"], ab))
            thrust = f * ab * self.m
            N += -self.I * d["brakeYawDampPerS"] * w
            self.th = 0.0
        else:
            a = self.a_fwd * self.th * (1.0 if self.th >= 0 else d["reverseRatio"])
            thrust = f * a * self.m
        # 範囲
        dd = self.rng.sdf(pos)
        phi = self.rng.phi(dd)
        n_in = -self.rng.grad(pos)
        if phi > 0:
            out = float(thrust @ n_in)
            if out < 0:
                thrust = thrust - n_in * out * min(phi, 1.0)
        F += thrust
        F += -self.m * (d["dragLinPerS"] * u + d["dragQuadPerM"] * u * abs(u)) * f
        F += -self.m * d["latDragPerS"] * v * s
        Rg = self.P["range"]
        push = np.zeros(2)
        if phi > 0:
            push += self.m * Rg["pushAccel"] * phi * n_in
            vo = float(vel @ n_in)
            if vo < 0:
                push += -self.m * Rg["pushDampPerS"] * phi * vo * n_in
        F += push
        ramp = d["yawAtRestRatio"] + (1 - d["yawAtRestRatio"]) * min(abs(u) / d["yawRefSpeed"], 1.0)
        N += self.I * d["yawDampPerS"] * math.radians(d["yawRateMaxDeg"]) * self.tu * ramp * (0 if stop else 1)
        N += -self.I * d["yawDampPerS"] * w
        return F, N, dict(u=u, v=v, d=dd, phi=phi, push=float(np.linalg.norm(push)) / self.m, th=self.th, tu=self.tu)


def script_input(P, s):
    """筋書きの入力（キーボード・ゲームパッドを DS44Input と同じ規則で読む）。"""
    thr = turn = 0.0
    stop = False
    label = ""
    for g in P["test"]["segments"]:
        if g["s0"] <= s < g["s1"]:
            label = g["labelJa"]
            keys = g["keys"].split()
            thr += (1.0 if "W" in keys else 0.0) - (1.0 if "S" in keys else 0.0)
            turn += (1.0 if "D" in keys else 0.0) - (1.0 if "A" in keys else 0.0)
            stop = stop or ("Space" in keys) or bool(g["south"])
            sx, sy = g["stick"]
            thr += sy + g["trig"][0] - g["trig"][1]
            turn += sx
    return max(-1.0, min(1.0, thr)), max(-1.0, min(1.0, turn)), stop, label


def simulate_plan(P, mass=2083.236782268851, inertia_y=15006.771484102012, dt=1.0 / 120.0):
    fr = Frame(P)
    rng = Range(P, fr)
    pl = Planar(P, mass, inertia_y, fr, rng)
    T = P["test"]
    pos = fr.to_world(T["startU"], T["startV"])
    yaw = fr.yaw + T["startYawOffsetDeg"]
    vel = np.zeros(2)
    w = 0.0
    rows = []
    n = int(round(T["handoverS"] / dt))
    for i in range(n):
        s = i * dt
        thr, turn, stop, lab = script_input(P, s)
        F, N, info = pl.forces(pos, vel, yaw, w, thr, turn, stop, dt)
        vel = vel + F / mass * dt
        w = w + math.degrees(N / inertia_y * dt)
        pos = pos + vel * dt
        yaw = yaw + w * dt
        uu, vv = fr.to_uv(pos)
        rows.append([s, pos[0], pos[1], yaw, vel[0], vel[1], w, info["u"], info["d"], info["phi"], info["push"], thr, turn, float(stop), uu, vv])
    return np.array(rows), pos, vel, yaw, w


if __name__ == "__main__":
    import sys
    P = load_params()
    R, pos, vel, yaw, w = simulate_plan(P)
    for s in [2, 6, 12, 16, 20, 26, 31, 33, 38, 45, 50, 53, 58, 62, 69.99]:
        i = min(int(s * 120), len(R) - 1)
        r = R[i]
        print("s=%5.1f u=%6.1f v=%6.1f yaw=%7.1f surge=%5.2f yawrate=%5.1f d=%6.2f phi=%4.2f push=%4.2f" % (r[0], r[14], r[15], r[3], r[7], r[6], r[8], r[9], r[10]))
    print("max d", R[:, 8].max(), "max phi", R[:, 9].max(), "max push", R[:, 10].max(), "max surge", R[:, 7].max())
    fr = Frame(P)
    acc = 0.0
    tr = Trajectory(P, pos, vel, yaw, w, acc, fr)
    print("arc", tr.arc_deg, "vcap", tr.vcap)
    print("handover pos", pos, "uv", fr.to_uv(pos), "yaw", yaw, "speed", np.linalg.norm(vel), "L", tr.L, "T", tr.T, "lead", tr.lead, )
    ts = np.linspace(0, tr.T, 400)
    ev = [tr.eval(t) for t in ts]
    print("max speed", max(e[5] for e in ev), "max yaw rate", max(abs(e[3]) for e in ev), "end", ev[-1][0], ev[-1][2])
