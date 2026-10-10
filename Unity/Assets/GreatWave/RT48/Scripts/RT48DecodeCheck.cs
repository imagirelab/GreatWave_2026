using System;
using System.Collections.Generic;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48：照合（計画 C5 の測り方）。RT48Decode.hlsl（描くシェーダーと同じファイル）を計算シェーダーで走らせて全部の点を読み戻し、
    // CPU の float64 の計算（同じ組・同じ割合・同じ下ろし）と比べる。
    //   位置の幅：max(0.0001 m, その点の座標の大きさでの float32 の刻みの 4 倍)、法線の角の差 ≤ 0.5°。
    // Editor（RT48SelfTest）とプレイヤー（-rt48decodecheck）の両方から使う。
    public static class RT48DecodeCheck
    {
        [Serializable]
        public class Case
        {
            public double t, alpha; public int frame, pair; public bool interp;
            public double maxPosErr, maxPosErrOverTol, maxNormDeg; public int worstIndex, failPos, failNorm; public bool pass;
        }

        [Serializable]
        public class Result
        {
            public string schema = "GreatWave.RT48.decodecheck/1";
            public string source, gpu, graphicsApi, unity, utc, noteJa;
            public bool isEditor, pass;
            public double seatX, maxPosErr, maxPosErrOverTol, maxNormDeg;
            public int points, cases;
            public Case[] results;
        }

        public static double Ulp32(double v)
        {
            double a = Math.Abs(v);
            if (a < 1.1754943508222875e-38) return 1.4e-45;
            return Math.Pow(2.0, Math.Floor(Math.Log(a, 2.0)) - 23.0);
        }

        public static Result Run(ComputeShader cs, RecordedSectionSource src, double seatX, IList<double> times)
        {
            int n = src.PointCount;
            int k = cs.FindKernel("Decode");
            var outBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n, 16);
            var gpu = new Vector4[n];
            var raw = new double[2 * n];
            var disp = new double[2 * n];
            double shift = src.XOriginM - seatX;
            var tp = src.TaperStored;
            var res = new Result
            {
                source = src.Id, gpu = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), unity = Application.unityVersion,
                utc = DateTime.UtcNow.ToString("O"), isEditor = Application.isEditor, seatX = seatX, points = n, pass = true,
                noteJa = "計算シェーダー RT48DecodeCheck.compute（RT48Decode.hlsl を読む）の出力を、CPU の float64 の同じ計算と比べた。位置の幅 max(0.0001 m, 4 ulp(float32))、法線 0.5°。"
            };
            var cases = new List<Case>();
            try
            {
                cs.SetBuffer(k, "_RT48Curves", src.CurveBuffer);
                cs.SetBuffer(k, "_RT48Out", outBuf);
                cs.SetInt("_RT48PointCount", n);
                cs.SetFloat("_RT48XShift", (float)shift);
                cs.SetVector("_RT48Taper", new Vector4((float)tp[0], (float)tp[1], (float)tp[2], (float)tp[3]));
                foreach (var t in times)
                {
                    var s = src.StateAt(t);
                    cs.SetInt("_RT48OffsetA", s.offsetA);
                    cs.SetInt("_RT48OffsetB", s.offsetB);
                    cs.SetFloat("_RT48Alpha", (float)s.alpha);
                    cs.Dispatch(k, (n + 63) / 64, 1, 1);
                    outBuf.GetData(gpu);
                    src.FillCurve(s, raw);
                    RT48BoatMotion.ToDisplayed(raw, n, tp, disp);
                    var c = new Case { t = t, alpha = s.alpha, frame = s.frame, pair = s.pair, interp = s.interpolating };
                    for (int i = 0; i < n; i++)
                    {
                        double X = disp[2 * i] + shift, Y = disp[2 * i + 1];
                        double tol = Math.Max(1e-4, 4.0 * Ulp32(Math.Max(Math.Abs(disp[2 * i]), Math.Abs(X))));
                        double e = Math.Max(Math.Abs(gpu[i].x - X), Math.Abs(gpu[i].y - Y));
                        if (e > c.maxPosErr) { c.maxPosErr = e; c.worstIndex = i; }
                        c.maxPosErrOverTol = Math.Max(c.maxPosErrOverTol, e / tol);
                        if (e > tol) c.failPos++;
                        int i0 = Math.Max(0, i - 1), i1 = Math.Min(n - 1, i + 1);
                        double tx = disp[2 * i1] - disp[2 * i0], ty = disp[2 * i1 + 1] - disp[2 * i0 + 1];
                        double L = Math.Sqrt(tx * tx + ty * ty);
                        if (L > 1e-12)
                        {
                            double nx = -ty / L, ny = tx / L;
                            double dot = Math.Max(-1.0, Math.Min(1.0, nx * gpu[i].z + ny * gpu[i].w));
                            double gl = Math.Sqrt((double)gpu[i].z * gpu[i].z + (double)gpu[i].w * gpu[i].w);
                            double ang = Math.Acos(Math.Max(-1.0, Math.Min(1.0, dot / Math.Max(gl, 1e-30)))) * 180.0 / Math.PI;
                            c.maxNormDeg = Math.Max(c.maxNormDeg, ang);
                            if (ang > 0.5) c.failNorm++;
                        }
                    }
                    c.pass = c.failPos == 0 && c.failNorm == 0;
                    res.pass &= c.pass;
                    res.maxPosErr = Math.Max(res.maxPosErr, c.maxPosErr);
                    res.maxPosErrOverTol = Math.Max(res.maxPosErrOverTol, c.maxPosErrOverTol);
                    res.maxNormDeg = Math.Max(res.maxNormDeg, c.maxNormDeg);
                    cases.Add(c);
                }
            }
            finally { outBuf.Release(); }
            res.results = cases.ToArray();
            res.cases = cases.Count;
            return res;
        }
    }
}
