using System;
using System.Collections.Generic;
using UnityEngine;

namespace GreatWave.Design44
{
    public struct DS44TrajSample
    {
        public Vector2 pos, vel;   // 世界の xz
        public double yawDeg, yawRateDegPs, s, speed;
    }

    // 設計44：固定の軌道（D26）。引き継ぎの時の位置・速度・向き・首振りの速さから、原画の座席の船の位置と向きへ速さ 0 で着く道と速さの表を作る。
    //   道：船の進む向きと原画の位置への方位の差 |α| が arcTriggerDeg を超える時は、円弧（半径 max(arcRadiusM, v0/yawRateMax × 1.15)、
    //       曲がりは max(arcEntryM, v0·arcEntryS) の長さで 0 から増やす）で目標の側へ回り、差が arcExitDeg 以下（または回しても差が縮まない・200°）で止める。
    //       その後 3 次 Bezier（腕 = max(bezierK·D, armMinM)。円弧のない時は始めの腕を v0·armTimeS 以上）で原画の位置と向きへ。
    //   速さ：道の曲がり κ から v ≤ min(vCap, yawRateMax/|κ|)、加速 aMax・減速 aDecMax の後ろ・前の走査（始め v0、終わり 0）。
    //       所要 T が formationS + leadMinS より短ければ vCap を二分法で下げる。形成は引き継ぎの T − formationS 秒後に始める（t* で着く）。
    //   向き：道の向き＋引き継ぎの時の差（横滑りの角 β0 と首振りの速さの差 c）を (β0 + c·t)·(1 − smoothstep(t/yawBlendS)) で 0 へ。
    // 同じ手順の numpy 版は Tools/GWWaveGen/ds44/ds44_model.py の Trajectory。
    public class DS44Trajectory
    {
        public readonly double[] S, X, Z, Psi, Kappa, V, Tt;
        public readonly double L, T, Lead, V0, VCap, Beta0, CRate, ArcDeg, ArcR, APlan0;
        readonly DS44TrajCfg tp;

        static double Wrap(double a) { a = (a + 180.0) % 360.0; if (a < 0) a += 360.0; return a - 180.0; }
        static double Deg(double r) => r * 180.0 / Math.PI;
        static double Rad(double d) => d * Math.PI / 180.0;

        public DS44Trajectory(DS44SteerConfig cfg, Vector2 p0, Vector2 vel0, double yaw0Deg, double r0DegPs, DS44Frame fr)
        {
            tp = cfg.traj;
            double p0x = p0.x, p0z = p0.y, p1x = fr.o.x, p1z = fr.o.y, h1x = fr.f.x, h1z = fr.f.y;
            double sp = Math.Sqrt((double)vel0.x * vel0.x + (double)vel0.y * vel0.y);
            double f0x = Math.Sin(Rad(yaw0Deg)), f0z = Math.Cos(Rad(yaw0Deg));
            double h0x, h0z, v0;
            if (sp >= tp.tangentFromVelocityMinSpeed) { h0x = vel0.x / sp; h0z = vel0.y / sp; v0 = sp; }
            else { h0x = f0x; h0z = f0z; v0 = Math.Max(0.0, vel0.x * f0x + vel0.y * f0z); }
            V0 = v0;
            double ds = tp.dsM;
            var px = new List<double> { p0x }; var pz = new List<double> { p0z };
            double hd = Deg(Math.Atan2(h0x, h0z));
            double alpha = Wrap(hd - Deg(Math.Atan2(p1x - p0x, p1z - p0z)));
            ArcDeg = 0.0; ArcR = 0.0;
            if (Math.Abs(alpha) > tp.arcTriggerDeg)
            {
                double rmax = Rad(tp.yawRateMaxDeg);
                double R = Math.Max(tp.arcRadiusM, v0 / rmax * 1.15);
                double Lc = Math.Max(tp.arcEntryM, v0 * tp.arcEntryS);
                double sgn = alpha > 0 ? -1.0 : 1.0;
                double x = p0x, z = p0z, h = hd, turned = 0.0, sArc = 0.0, errPrev = 1e9;
                ArcR = R;
                while (true)
                {
                    sArc += ds;
                    double k = Math.Min(sArc / Lc, 1.0) / R;
                    double dh = Deg(k * ds) * sgn;
                    h += dh; turned += dh;
                    x += ds * Math.Sin(Rad(h)); z += ds * Math.Cos(Rad(h));
                    px.Add(x); pz.Add(z);
                    double err = Math.Abs(Wrap(h - Deg(Math.Atan2(p1x - x, p1z - z))));
                    if (err <= tp.arcExitDeg || (sArc > Lc && Math.Abs(turned) > 90.0 && err > errPrev + 1e-9) || Math.Abs(turned) >= 200.0) break;
                    errPrev = err;
                }
                ArcDeg = turned;
                hd = h;
            }
            double pax = px[px.Count - 1], paz = pz[pz.Count - 1];
            double hax = Math.Sin(Rad(hd)), haz = Math.Cos(Rad(hd));
            double D = Math.Sqrt((p1x - pax) * (p1x - pax) + (p1z - paz) * (p1z - paz));
            double arm1 = Math.Max(tp.bezierK * D, tp.armMinM);
            double arm0 = ArcDeg == 0.0 ? Math.Max(arm1, v0 * tp.armTimeS) : arm1;
            double c0x = pax, c0z = paz, c1x = pax + arm0 * hax, c1z = paz + arm0 * haz, c2x = p1x - arm1 * h1x, c2z = p1z - arm1 * h1z, c3x = p1x, c3z = p1z;
            const int NB = 4097;
            var bx = new double[NB]; var bz = new double[NB]; var sb = new double[NB];
            for (int i = 0; i < NB; i++)
            {
                double q = i / (double)(NB - 1), a = 1 - q;
                bx[i] = a * a * a * c0x + 3 * a * a * q * c1x + 3 * a * q * q * c2x + q * q * q * c3x;
                bz[i] = a * a * a * c0z + 3 * a * a * q * c1z + 3 * a * q * q * c2z + q * q * q * c3z;
                sb[i] = i == 0 ? 0 : sb[i - 1] + Math.Sqrt((bx[i] - bx[i - 1]) * (bx[i] - bx[i - 1]) + (bz[i] - bz[i - 1]) * (bz[i] - bz[i - 1]));
            }
            int nb = Math.Max(2, (int)Math.Ceiling(sb[NB - 1] / ds));
            for (int j = 1; j <= nb; j++)
            {
                double s = sb[NB - 1] * j / nb;
                px.Add(Interp(s, sb, bx)); pz.Add(Interp(s, sb, bz));
            }
            int n = px.Count;
            X = px.ToArray(); Z = pz.ToArray();
            S = new double[n];
            for (int i = 1; i < n; i++) S[i] = S[i - 1] + Math.Sqrt((X[i] - X[i - 1]) * (X[i] - X[i - 1]) + (Z[i] - Z[i - 1]) * (Z[i] - Z[i - 1]));
            L = S[n - 1];
            // 向き（区間の向きを順に巻き戻し、点は隣の区間の平均。始めは h0、終わりは原画の向き）
            var seg = new double[n - 1];
            for (int i = 0; i < n - 1; i++)
            {
                double a = Deg(Math.Atan2(X[i + 1] - X[i], Z[i + 1] - Z[i]));
                seg[i] = i == 0 ? a : seg[i - 1] + Wrap(a - seg[i - 1]);
            }
            Psi = new double[n];
            double h0deg = Deg(Math.Atan2(h0x, h0z));
            Psi[0] = seg[0] + Wrap(h0deg - seg[0]);
            for (int i = 1; i < n - 1; i++) Psi[i] = 0.5 * (seg[i - 1] + seg[i]);
            Psi[n - 1] = Psi[n - 2] + Wrap(fr.yawDeg - Psi[n - 2]);
            Kappa = new double[n];
            for (int i = 0; i < n; i++)
            {
                int a = Math.Max(i - 1, 0), b = Math.Min(i + 1, n - 1);
                Kappa[i] = Rad(Psi[b] - Psi[a]) / Math.Max(S[b] - S[a], 1e-9);
            }
            // 速さの表
            double vcap = tp.vMax;
            double[] v, t;
            Plan(vcap, v0, out v, out t);
            double Treq = tp.formationS + tp.leadMinS;
            if (t[n - 1] < Treq)
            {
                double lo = 0.02, hi = vcap;
                for (int it = 0; it < 40; it++)
                {
                    double mid = 0.5 * (lo + hi);
                    Plan(mid, v0, out v, out t);
                    if (t[n - 1] < Treq) hi = mid; else lo = mid;
                }
                Plan(lo, v0, out v, out t);
                vcap = lo;
            }
            VCap = vcap; V = v; Tt = t;
            T = t[n - 1];
            Lead = T - tp.formationS;
            Beta0 = Wrap(yaw0Deg - Psi[0]);
            CRate = r0DegPs - Deg(Kappa[0]) * v0;
            APlan0 = (v[1] * v[1] - v[0] * v[0]) / (2 * Math.Max(S[1] - S[0], 1e-9));
        }

        void Plan(double vcap, double v0, out double[] vf, out double[] t)
        {
            int n = S.Length;
            double rmax = Rad(tp.yawRateMaxDeg);
            var vb = new double[n];
            vb[n - 1] = 0.0;
            for (int i = n - 2; i >= 0; i--)
            {
                double vl = Math.Min(vcap, rmax / Math.Max(Math.Abs(Kappa[i]), 1e-9));
                vb[i] = Math.Min(vl, Math.Sqrt(vb[i + 1] * vb[i + 1] + 2 * tp.aMax * (S[i + 1] - S[i])));
            }
            vf = new double[n];
            vf[0] = v0;
            for (int i = 0; i < n - 1; i++)
            {
                double h = S[i + 1] - S[i];
                double up = Math.Sqrt(vf[i] * vf[i] + 2 * tp.aMax * h);
                double dn = Math.Sqrt(Math.Max(vf[i] * vf[i] - 2 * tp.aDecMax * h, 0.0));
                vf[i + 1] = Math.Max(Math.Min(vb[i + 1], up), dn);
            }
            vf[n - 1] = 0.0;
            t = new double[n];
            for (int i = 1; i < n; i++) t[i] = t[i - 1] + 2 * (S[i] - S[i - 1]) / Math.Max(vf[i - 1] + vf[i], 1e-6);
        }

        static double Interp(double x, double[] xs, double[] ys)
        {
            int n = xs.Length;
            if (x <= xs[0]) return ys[0];
            if (x >= xs[n - 1]) return ys[n - 1];
            int i = Array.BinarySearch(xs, x);
            if (i >= 0) return ys[i];
            i = ~i - 1;
            double d = xs[i + 1] - xs[i];
            double f = d > 0 ? (x - xs[i]) / d : 0;
            return ys[i] + f * (ys[i + 1] - ys[i]);
        }

        double Blend(double t, out double rate)
        {
            double Tb = tp.yawBlendS;
            double x = Math.Min(Math.Max(t / Tb, 0.0), 1.0);
            double g = 1.0 - x * x * (3 - 2 * x);
            double gd = (t > 0 && t < Tb) ? -6.0 * x * (1 - x) / Tb : 0.0;
            rate = CRate * g + (Beta0 + CRate * t) * gd;
            return (Beta0 + CRate * t) * g;
        }

        /// <summary>引き継ぎからの時間 t（秒）の目標。t ≥ T では原画の位置・向きに止まる。</summary>
        public DS44TrajSample Eval(double t)
        {
            double tt = Math.Min(Math.Max(t, 0.0), T);
            double s = Interp(tt, Tt, S);
            double sp = t < T ? Interp(tt, Tt, V) : 0.0;
            double psiP = Interp(s, S, Psi);
            double br;
            double b = Blend(tt, out br);
            var o = new DS44TrajSample();
            o.pos = new Vector2((float)Interp(s, S, X), (float)Interp(s, S, Z));
            o.vel = new Vector2((float)(Math.Sin(Rad(psiP)) * sp), (float)(Math.Cos(Rad(psiP)) * sp));
            o.yawDeg = psiP + b;
            o.yawRateDegPs = t < T ? Deg(Interp(s, S, Kappa)) * sp + br : 0.0;
            o.s = s; o.speed = sp;
            return o;
        }
    }
}
