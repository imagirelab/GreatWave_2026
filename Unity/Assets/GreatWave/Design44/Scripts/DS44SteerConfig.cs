using System;
using UnityEngine;

namespace GreatWave.Design44
{
    // 設計44：操船の表（Assets/GreatWave/Design44/Data/ds44_steer.json）。numpy の Tools/GWWaveGen/ds44 も同じ表を読む。
    // 値はすべて調整値・推定（資料の値ではない）。座標は Unity の世界（m、Y 上）。首の向き ψ は +z から +x へ測る（度。上から見て時計回りが正、ds43_boats.json の yawDeg と同じ）。
    [Serializable] public class DS44Painting { public string key; public float x, z, yawDeg; public string source; }
    [Serializable] public class DS44RangeCfg { public float uMin, uMax, vMin, vMax, cornerRadius, bandM, pushAccel, pushDampPerS; public string noteJa; }
    [Serializable]
    public class DS44DynCfg
    {
        public float inputLagS, vMaxFwd, dragLinPerS, dragQuadPerM, reverseRatio, brakePerS, brakeAccelMax, latDragPerS;
        public float yawRateMaxDeg, yawAtRestRatio, yawRefSpeed, yawDampPerS, brakeYawDampPerS;
        public string noteJa;
    }
    [Serializable]
    public class DS44TrajCfg
    {
        public float leadMinS, formationS, dsM, vMax, aMax, aDecMax, yawRateMaxDeg, arcTriggerDeg, arcExitDeg, arcRadiusM, arcEntryM, arcEntryS;
        public float bezierK, armMinM, armTimeS, yawBlendS, tangentFromVelocityMinSpeed;
        public string noteJa;
    }
    [Serializable] public class DS44Segment { public float s0, s1; public string device, keys, labelJa; public float[] stick, trig; public int south; }
    [Serializable] public class DS44TestCfg { public float startU, startV, startYawOffsetDeg, settleS, handoverS, holdAfterStarS; public DS44Segment[] segments; public string noteJa; }
    [Serializable]
    public class DS44SteerConfig
    {
        public string schema, noteJa;
        public DS44Painting painting;
        public DS44RangeCfg range;
        public DS44DynCfg dyn;
        public DS44TrajCfg traj;
        public DS44TestCfg test;

        public static DS44SteerConfig Parse(string json)
        {
            var c = JsonUtility.FromJson<DS44SteerConfig>(json);
            if (c == null || c.painting == null || c.range == null || c.dyn == null || c.traj == null) throw new InvalidOperationException("DS44SteerConfig：表が読めません");
            return c;
        }
    }

    /// <summary>painting frame（原点 = 原画の座席の船の根の xz、u = 原画の船首の向き、v = 右舷）と世界の xz の行き来。</summary>
    public struct DS44Frame
    {
        public Vector2 o, f, s;
        public float yawDeg;

        public DS44Frame(DS44Painting p)
        {
            o = new Vector2(p.x, p.z);
            yawDeg = p.yawDeg;
            float r = p.yawDeg * Mathf.Deg2Rad;
            f = new Vector2(Mathf.Sin(r), Mathf.Cos(r));
            s = new Vector2(Mathf.Cos(r), -Mathf.Sin(r));
        }

        public Vector2 ToWorld(float u, float v) => o + u * f + v * s;
        public Vector2 ToUV(Vector2 xz) { var d = xz - o; return new Vector2(Vector2.Dot(d, f), Vector2.Dot(d, s)); }
    }

    /// <summary>操船の範囲：painting frame の角を丸めた長方形。符号付き距離 d（外が正）と押し戻しの強さ φ。</summary>
    public class DS44Range
    {
        public readonly DS44RangeCfg R;
        public readonly DS44Frame Fr;
        readonly Vector2 c, h;
        readonly float r;

        public DS44Range(DS44RangeCfg cfg, DS44Frame fr)
        {
            R = cfg; Fr = fr;
            c = new Vector2((cfg.uMin + cfg.uMax) * 0.5f, (cfg.vMin + cfg.vMax) * 0.5f);
            h = new Vector2((cfg.uMax - cfg.uMin) * 0.5f, (cfg.vMax - cfg.vMin) * 0.5f);
            r = cfg.cornerRadius;
        }

        public float SdfUV(Vector2 uv)
        {
            var q = new Vector2(Mathf.Abs(uv.x - c.x), Mathf.Abs(uv.y - c.y)) - (h - new Vector2(r, r));
            var qp = new Vector2(Mathf.Max(q.x, 0f), Mathf.Max(q.y, 0f));
            return qp.magnitude + Mathf.Min(Mathf.Max(q.x, q.y), 0f) - r;
        }

        public float Sdf(Vector2 xz) => SdfUV(Fr.ToUV(xz));

        /// <summary>外向きの単位の法線（世界の xz）。</summary>
        public Vector2 Grad(Vector2 xz, float e = 0.01f)
        {
            float gx = (Sdf(xz + new Vector2(e, 0f)) - Sdf(xz - new Vector2(e, 0f))) / (2f * e);
            float gz = (Sdf(xz + new Vector2(0f, e)) - Sdf(xz - new Vector2(0f, e))) / (2f * e);
            var g = new Vector2(gx, gz);
            float n = g.magnitude;
            return n > 1e-9f ? g / n : g;
        }

        public float Phi(float d)
        {
            float b = R.bandM;
            if (d <= 0f) { float x = Mathf.Clamp01((d + b) / b); return x * x * (3f - 2f * x); }
            return 1f + d / b;
        }
    }
}
