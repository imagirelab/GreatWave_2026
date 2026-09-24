using System;

namespace GreatWave.Playback18
{
    // Unityを起動せず境界事例を検査できる、数値だけの配置計算。
    public static class Playback18VATLayout
    {
        [Serializable]
        public struct Diagnostics
        {
            public float rawX, rawY;
            public float activeX, activeY;
            public float deltaX, deltaY;
            public float tolerance;
            public float scaledMinZ, scaledNegativeMaxX;
            public float usedScaledMinZ, usedScaledNegativeMaxX;
        }

        public static Diagnostics Evaluate(float encodedMinZ, float encodedMaxX,
            int lookupWidth, int lookupHeight)
        {
            if (lookupWidth < 1 || lookupHeight < 1)
                throw new ArgumentOutOfRangeException("検索表の寸法が不正です。");
            if (float.IsNaN(encodedMinZ) || float.IsInfinity(encodedMinZ) ||
                float.IsNaN(encodedMaxX) || float.IsInfinity(encodedMaxX))
                throw new ArgumentException("符号化された境界値は有限値が必要です。");
            float scaledX = encodedMinZ * 10f;
            float scaledY = -encodedMaxX * 10f;
            float tolerance = Math.Min(2e-5f, .125f / Math.Max(lookupWidth, lookupHeight));
            float usedX = SnapIntegerBoundary(scaledX, tolerance);
            float usedY = SnapIntegerBoundary(scaledY, tolerance);
            float rawX = 1f - ((float)Math.Ceiling(scaledX) - scaledX);
            float rawY = 1f - (scaledY - (float)Math.Floor(scaledY));
            float activeX = 1f - ((float)Math.Ceiling(usedX) - usedX);
            float activeY = 1f - (usedY - (float)Math.Floor(usedY));
            return new Diagnostics
            {
                rawX = rawX, rawY = rawY, activeX = activeX, activeY = activeY,
                deltaX = activeX - rawX, deltaY = activeY - rawY,
                tolerance = tolerance, scaledMinZ = scaledX, scaledNegativeMaxX = scaledY,
                usedScaledMinZ = usedX, usedScaledNegativeMaxX = usedY
            };
        }

        // 不連続なceil/fracへ入る前に整数境界だけを補正する。
        // 許容差は最大2e-5、かつ検索表の1/8画素以下。一般的なclampではない。
        static float SnapIntegerBoundary(float value, float tolerance)
        {
            float nearest = (float)Math.Round(value);
            return Math.Abs(value - nearest) <= tolerance ? nearest : value;
        }
    }
}
