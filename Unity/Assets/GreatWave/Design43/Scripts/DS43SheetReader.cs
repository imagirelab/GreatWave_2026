using System;
using System.Collections.Generic;
using System.IO;
using GreatWave.Design27;
using GreatWave.Design29;
using UnityEngine;

namespace GreatWave.Design43
{
    // 設計43：DS27 形式のシート（主役波と設計30 の周りの海）を CPU で読み、鉛直の線との交わりの高さを返す（船用水面データの中身）。
    //   ・復号は GPU（DS27KeyposeCore.cginc、精度の層つき）と同じ式：位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size。
    //   ・時刻は DS27KeyposePlayer.Weights（不等間隔の節点の 3 次 Hermite の 4 層と重み）と、枠の原点 O(τ)（密な表の線形補間。DS30SheetPlayer.OriginAt と同じ）。
    //   ・描く四角だけを使う：主役波は本体の列 colMin〜colMax の間（DS30SheetPlayer の colMin・colMax と同じ）、far は最後の行（すその鉛直の四角）を除く。
    //   ・層は必要な時だけファイルから読み、復号した層を少数だけ手元に置く。空間の索引は関心の範囲（船のまわり）の三角形だけの一様格子。
    public class DS43SheetReader
    {
        public readonly string Name;
        public readonly DS27KeyposePlayer.Meta Meta;
        public readonly int Rows, Cols, C0, C1, R1;   // 四角：行 0..R1-1、列 C0..C1-1
        readonly string posPath, loPath;
        readonly bool hasLo;
        readonly int n;
        readonly Dictionary<int, float[]> cache = new Dictionary<int, float[]>();
        readonly LinkedList<int> order = new LinkedList<int>();
        const int CacheMax = 10;
        readonly int[] idx = new int[4];
        readonly float[] w = new float[4];
        public float[] X;                      // 世界の頂点（行 × 列 × 3）
        public double BuiltTau = double.NaN;
        public Vector3 BuiltOrigin;
        // 索引
        Rect roi; float cell; int gx, gz;
        List<int>[] grid;
        public int IndexedTriangles { get; private set; }
        public long LayerReads { get; private set; }

        public DS43SheetReader(string name, string packageDir, int colMin, int colMax, bool dropLastRowQuads)
        {
            Name = name;
            Meta = DS29KeyposePlayer.ReadMeta(packageDir);
            Rows = Meta.rows; Cols = Meta.cols; n = Rows * Cols;
            C0 = colMin >= 0 ? colMin : 0;
            C1 = colMax >= 0 ? colMax : Cols - 1;
            R1 = Rows - 1 - (dropLastRowQuads ? 1 : 0);
            posPath = Path.Combine(Meta.dir, "ds27_pos_rgba16.bin");
            loPath = Path.Combine(Meta.dir, "ds27_pos_lo_rgba8.bin");
            hasLo = File.Exists(loPath);
            if (!File.Exists(posPath)) throw new FileNotFoundException("DS43SheetReader：位置のファイルがありません", posPath);
            X = new float[n * 3];
        }

        float[] Layer(int i)
        {
            if (cache.TryGetValue(i, out var got)) { order.Remove(i); order.AddLast(i); return got; }
            var hi = new byte[n * 8];
            using (var fs = new FileStream(posPath, FileMode.Open, FileAccess.Read, FileShare.Read)) { fs.Seek((long)i * n * 8, SeekOrigin.Begin); ReadFully(fs, hi); }
            byte[] lo = null;
            if (hasLo)
            {
                lo = new byte[n * 4];
                using (var fl = new FileStream(loPath, FileMode.Open, FileAccess.Read, FileShare.Read)) { fl.Seek((long)i * n * 4, SeekOrigin.Begin); ReadFully(fl, lo); }
            }
            var L = new float[n * 3];
            double[] bm = Meta.bboxMin, bs = Meta.bboxSize;
            for (int v = 0; v < n; v++)
                for (int a = 0; a < 3; a++)
                {
                    double q = hi[8 * v + 2 * a] | (hi[8 * v + 2 * a + 1] << 8);
                    double f = lo != null ? lo[4 * v + a] / 255.0 - 0.5 : 128.0 / 255.0 - 0.5;
                    L[3 * v + a] = (float)(bm[a] + (q + f) / 65535.0 * bs[a]);
                }
            cache[i] = L; order.AddLast(i); LayerReads++;
            while (cache.Count > CacheMax) { int old = order.First.Value; order.RemoveFirst(); cache.Remove(old); }
            return L;
        }

        public Vector3 OriginAt(double tau)
        {
            var ft = Meta.frameTau; var fo = Meta.frameOrigin; int m = ft.Length;
            double[] o;
            if (tau <= ft[0]) o = fo[0];
            else if (tau >= ft[m - 1]) o = fo[m - 1];
            else
            {
                int i = Array.BinarySearch(ft, tau);
                if (i >= 0) o = fo[i];
                else
                {
                    i = ~i - 1;
                    double s = (tau - ft[i]) / (ft[i + 1] - ft[i]);
                    o = new[] { fo[i][0] + s * (fo[i + 1][0] - fo[i][0]), fo[i][1] + s * (fo[i + 1][1] - fo[i][1]), fo[i][2] + s * (fo[i + 1][2] - fo[i][2]) };
                }
            }
            return new Vector3((float)o[0], (float)o[1], (float)o[2]);
        }

        /// <summary>時刻 τ の世界の頂点を作り、関心の範囲 region（xz）の三角形の索引を作り直す。</summary>
        public void Build(double tau, Rect region, float cellSize)
        {
            DS27KeyposePlayer.Weights(Meta.knotTau, tau, idx, w);
            var o = OriginAt(tau);
            Array.Clear(X, 0, X.Length);
            for (int k = 0; k < 4; k++)
            {
                float wk = w[k];
                if (wk == 0f) continue;
                var L = Layer(idx[k]);
                for (int j = 0; j < X.Length; j++) X[j] += wk * L[j];
            }
            for (int v = 0; v < n; v++) { X[3 * v] += o.x; X[3 * v + 1] += o.y; X[3 * v + 2] += o.z; }
            BuiltTau = tau; BuiltOrigin = o;
            // 索引
            if (grid == null || roi != region || cell != cellSize)
            {
                roi = region; cell = cellSize;
                gx = Math.Max(1, Mathf.CeilToInt(region.width / cellSize)); gz = Math.Max(1, Mathf.CeilToInt(region.height / cellSize));
                grid = new List<int>[gx * gz];
                for (int i = 0; i < grid.Length; i++) grid[i] = new List<int>(8);
            }
            else foreach (var l in grid) l.Clear();
            int cnt = 0;
            for (int r = 0; r < R1; r++)
                for (int c = C0; c < C1; c++)
                {
                    int a = r * Cols + c, b = a + Cols, cc = a + 1, d = b + 1;
                    for (int t = 0; t < 2; t++)
                    {
                        int p0 = t == 0 ? a : cc, p1 = b, p2 = t == 0 ? cc : d;
                        float x0 = Mathf.Min(X[3 * p0], Mathf.Min(X[3 * p1], X[3 * p2])), x1 = Mathf.Max(X[3 * p0], Mathf.Max(X[3 * p1], X[3 * p2]));
                        float z0 = Mathf.Min(X[3 * p0 + 2], Mathf.Min(X[3 * p1 + 2], X[3 * p2 + 2])), z1 = Mathf.Max(X[3 * p0 + 2], Mathf.Max(X[3 * p1 + 2], X[3 * p2 + 2]));
                        if (x1 < roi.xMin || x0 > roi.xMax || z1 < roi.yMin || z0 > roi.yMax) continue;
                        int i0 = Mathf.Clamp((int)Math.Floor((x0 - roi.xMin) / cell), 0, gx - 1), i1 = Mathf.Clamp((int)Math.Floor((x1 - roi.xMin) / cell), 0, gx - 1);
                        int j0 = Mathf.Clamp((int)Math.Floor((z0 - roi.yMin) / cell), 0, gz - 1), j1 = Mathf.Clamp((int)Math.Floor((z1 - roi.yMin) / cell), 0, gz - 1);
                        int id = ((r * Cols + c) << 1) | t;
                        for (int j = j0; j <= j1; j++) for (int i = i0; i <= i1; i++) grid[j * gx + i].Add(id);
                        cnt++;
                    }
                }
            IndexedTriangles = cnt;
        }

        /// <summary>点 (x, z) の鉛直の線と、索引にある三角形の交わりの高さを hits へ足す（重なりはそのまま。呼ぶ側でまとめる）。範囲の外は false。</summary>
        public bool Query(float x, float z, List<float> hits)
        {
            if (grid == null || x < roi.xMin || x > roi.xMax || z < roi.yMin || z > roi.yMax) return false;
            int i = Mathf.Clamp((int)Math.Floor((x - roi.xMin) / cell), 0, gx - 1), j = Mathf.Clamp((int)Math.Floor((z - roi.yMin) / cell), 0, gz - 1);
            foreach (int id in grid[j * gx + i])
            {
                int t = id & 1, q = id >> 1;
                int a = q, b = a + Cols, cc = a + 1, d = b + 1;
                int p0 = t == 0 ? a : cc, p1 = b, p2 = t == 0 ? cc : d;
                double ax = X[3 * p0], az = X[3 * p0 + 2];
                double e1x = X[3 * p1] - ax, e1z = X[3 * p1 + 2] - az, e2x = X[3 * p2] - ax, e2z = X[3 * p2 + 2] - az;
                double det = e1x * e2z - e1z * e2x;
                if (Math.Abs(det) < 1e-12) continue;
                double dx = x - ax, dz = z - az;
                double u = (dx * e2z - dz * e2x) / det, v = (e1x * dz - e1z * dx) / det;
                if (u < -1e-7 || v < -1e-7 || u + v > 1 + 1e-7) continue;
                double y = X[3 * p0 + 1] + u * (X[3 * p1 + 1] - X[3 * p0 + 1]) + v * (X[3 * p2 + 1] - X[3 * p0 + 1]);
                hits.Add((float)y);
            }
            return true;
        }

        static void ReadFully(Stream fs, byte[] raw)
        {
            int got = 0;
            while (got < raw.Length)
            {
                int k = fs.Read(raw, got, raw.Length - got);
                if (k <= 0) throw new EndOfStreamException("ファイルが途中で終わっています。");
                got += k;
            }
        }
    }
}
