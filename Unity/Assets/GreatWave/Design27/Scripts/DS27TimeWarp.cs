using System;
using System.IO;

namespace GreatWave.Design27
{
    // 設計27：世界全体の時間曲線 τ(t)（設計26 §3.2、D31）の表を読む。表は {"t": [...], "tau": [...]}（t = 0〜14 s、240 Hz 以上）で、
    // 間は線形に補間し、表の外は端の値のまま。既定（timewarp_default.json）と代案（timewarp_alt.json）は設計27 の生成器が
    // Tools/GWWaveGen/ds27/ に書く。採取（DS27Formation）は各コマの t からこの表で τ を決めて DS27KeyposePlayer.ApplyTau に渡す。
    // 単発の再生（GWClock の時刻から τ を読む経路）は設計30 で使う。
    public class DS27TimeWarp
    {
        public double[] T { get; private set; }
        public double[] Tau { get; private set; }
        public string Path { get; private set; }
        public double MinRateHz { get; private set; }

        public static DS27TimeWarp Load(string path)
        {
            var full = System.IO.Path.GetFullPath(path);
            var root = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(full)), "時間曲線の表");
            var t = DS27Json.Nums(DS27Json.Get(root, "t"), "t");
            var tau = DS27Json.Nums(DS27Json.Get(root, "tau"), "tau");
            if (t.Length != tau.Length || t.Length < 2) throw new InvalidDataException("時間曲線の表の t と tau の長さが合いません: " + path);
            double maxDt = 0;
            for (int i = 1; i < t.Length; i++)
            {
                if (!(t[i] > t[i - 1])) throw new InvalidDataException("時間曲線の表の t が単調増加でありません: " + path);
                maxDt = Math.Max(maxDt, t[i] - t[i - 1]);
            }
            return new DS27TimeWarp { T = t, Tau = tau, Path = full, MinRateHz = 1.0 / maxDt };
        }

        /// <summary>体験の時刻 t（秒）→ 物理の時刻 τ（秒、t* = 0）。</summary>
        public double TauAt(double t)
        {
            int n = T.Length;
            if (t <= T[0]) return Tau[0];
            if (t >= T[n - 1]) return Tau[n - 1];
            int i = Array.BinarySearch(T, t);
            if (i >= 0) return Tau[i];
            i = ~i - 1;
            double s = (t - T[i]) / (T[i + 1] - T[i]);
            return Tau[i] + s * (Tau[i + 1] - Tau[i]);
        }

        public double TauMin { get { double m = double.MaxValue; foreach (var v in Tau) m = Math.Min(m, v); return m; } }
        public double TauMax { get { double m = double.MinValue; foreach (var v in Tau) m = Math.Max(m, v); return m; } }
    }
}
