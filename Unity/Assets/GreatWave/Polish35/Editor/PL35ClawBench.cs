using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using GreatWave.Design34;
using GreatWave.Design38;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Polish35.EditorTools
{
    // 仕上げ35 修正の回 1 の下調べ（Editor の batchmode。記録）：爪の層の毎コマの仕事（DS34ClawPlayer.ApplyT と DS38ClawOutline.Sync）を部分ごとに測り、
    // 縁の線の法線を Unity の RecalculateNormals の代わりに C# の並列の計算で作る案の速さと、RecalculateNormals との向きの差を測る。
    // 場面とファイルは変えない（一時の GameObject を作って消す）。出力：-pl35Out の pl35_claw_bench.json。
    public static class PL35ClawBench
    {
        static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return def;
        }

        [Serializable] public class Row { public string nameJa; public double msMean, msMin, msMax; public int n; }
        [Serializable] public class Report
        {
            public string utc, unity, layout; public int vertices, triangles, claws; public double t;
            public Row[] rows; public string[] compareJa; public double[] angleDegMaxA, angleDegP999A, angleDegMaxB, angleDegP999B; public int[] zeroLenUnity, zeroLenOurs;
        }

        static Row Time(string name, int n, Action a)
        {
            a();   // 一度目（JIT）は数えない
            var l = new List<double>();
            for (int i = 0; i < n; i++) { var sw = Stopwatch.StartNew(); a(); l.Add(sw.Elapsed.TotalMilliseconds); }
            l.Sort();
            double s = 0; foreach (var x in l) s += x;
            return new Row { nameJa = name, msMean = s / l.Count, msMin = l[0], msMax = l[l.Count - 1], n = n };
        }

        public static void Run()
        {
            string layout = Arg("-pl35Claws", "Build/Polish/33r01/fix01/claws/ds33_claw_layout.json");
            double t = double.Parse(Arg("-pl35T", "11.5123"), System.Globalization.CultureInfo.InvariantCulture);
            var go = new GameObject("PL35 bench claws");
            try
            {
                go.AddComponent<MeshFilter>(); go.AddComponent<MeshRenderer>();
                var cp = go.AddComponent<DS34ClawPlayer>();
                cp.layoutPath = layout; cp.verifySha256 = false;
                cp.Load();
                var ol = go.AddComponent<DS38ClawOutline>();
                ol.claws = cp; ol.Attach();
                cp.ApplyT(t); ol.Sync();
                var rows = new List<Row>();
                rows.Add(Time("DS34ClawPlayer.ApplyT（格子の間、補間）", 20, () => cp.ApplyT(t)));
                rows.Add(Time("DS38ClawOutline.Sync（全部）", 20, () => ol.Sync()));
                var lineMesh = ol.Line.GetComponent<MeshFilter>().sharedMesh;
                Vector3[] cur = null;
                rows.Add(Time("DS34ClawPlayer.Current（配列の写し）", 20, () => cur = cp.Current));
                rows.Add(Time("線のメッシュ SetVertices", 20, () => lineMesh.SetVertices(cur)));
                rows.Add(Time("線のメッシュ RecalculateNormals", 20, () => lineMesh.RecalculateNormals()));
                rows.Add(Time("爪のメッシュ SetVertices（ApplyT の中の分）", 20, () => go.GetComponent<MeshFilter>().sharedMesh.SetVertices(cur)));

                // C# の並列の法線（面の法線 → 頂点ごとに隣の面を足す）
                int V = lineMesh.vertexCount;
                var tris = lineMesh.triangles;
                int T = tris.Length / 3;
                var cnt = new int[V + 1];
                for (int i = 0; i < tris.Length; i++) cnt[tris[i] + 1]++;
                for (int v = 0; v < V; v++) cnt[v + 1] += cnt[v];
                var adj = new int[tris.Length];
                var fill = (int[])cnt.Clone();
                for (int f = 0; f < T; f++) for (int k = 0; k < 3; k++) adj[fill[tris[3 * f + k]]++] = f;
                var face = new Vector3[T];
                var ours = new Vector3[V];
                var unity = lineMesh.normals;
                var pos = cur;
                int chunks = Environment.ProcessorCount * 4;
                Action<bool> calc = normFace =>
                {
                    System.Threading.Tasks.Parallel.For(0, chunks, c =>
                    {
                        int a = (int)((long)T * c / chunks), b = (int)((long)T * (c + 1) / chunks);
                        for (int f = a; f < b; f++)
                        {
                            var p0 = pos[tris[3 * f]]; var p1 = pos[tris[3 * f + 1]]; var p2 = pos[tris[3 * f + 2]];
                            var n = Vector3.Cross(p1 - p0, p2 - p0);
                            if (normFace) { float m = n.magnitude; n = m > 0f ? n / m : Vector3.zero; }
                            face[f] = n;
                        }
                    });
                    System.Threading.Tasks.Parallel.For(0, chunks, c =>
                    {
                        int a = (int)((long)V * c / chunks), b = (int)((long)V * (c + 1) / chunks);
                        for (int v = a; v < b; v++)
                        {
                            Vector3 s = Vector3.zero;
                            for (int j = cnt[v]; j < cnt[v + 1]; j++) s += face[adj[j]];
                            float m = s.magnitude;
                            ours[v] = m > 0f ? s / m : Vector3.zero;
                        }
                    });
                };
                rows.Add(Time("C# の並列の法線（面積の重み）", 20, () => calc(false)));
                rows.Add(Time("C# の並列の法線（面の単位法線）", 20, () => calc(true)));
                rows.Add(Time("線のメッシュ SetNormals", 20, () => lineMesh.SetNormals(ours)));

                // 向きの差（いくつかの時刻）
                var ts = new[] { 7.0123, 9.0, 10.5, 11.5123, 12.0 };
                var maxA = new double[ts.Length]; var p999A = new double[ts.Length]; var maxB = new double[ts.Length]; var p999B = new double[ts.Length];
                var zU = new int[ts.Length]; var zO = new int[ts.Length];
                for (int i = 0; i < ts.Length; i++)
                {
                    cp.ApplyT(ts[i]); ol.Sync();
                    pos = cp.Current;
                    unity = lineMesh.normals;
                    for (int pass = 0; pass < 2; pass++)
                    {
                        calc(pass == 1);
                        var ang = new List<double>();
                        int zu = 0, zo = 0;
                        for (int v = 0; v < V; v++)
                        {
                            bool a0 = unity[v].sqrMagnitude < 0.5f, b0 = ours[v].sqrMagnitude < 0.5f;
                            if (a0) zu++; if (b0) zo++;
                            if (a0 || b0) continue;
                            ang.Add(Vector3.Angle(unity[v], ours[v]));
                        }
                        ang.Sort();
                        double mx = ang.Count > 0 ? ang[ang.Count - 1] : 0, p = ang.Count > 0 ? ang[(int)(0.999 * (ang.Count - 1))] : 0;
                        if (pass == 0) { maxA[i] = mx; p999A[i] = p; zU[i] = zu; zO[i] = zo; } else { maxB[i] = mx; p999B[i] = p; }
                    }
                }
                var rep = new Report { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, layout = layout, vertices = V, triangles = T, claws = cp.ClawCount, t = t,
                    rows = rows.ToArray(), angleDegMaxA = maxA, angleDegP999A = p999A, angleDegMaxB = maxB, angleDegP999B = p999B, zeroLenUnity = zU, zeroLenOurs = zO,
                    compareJa = new[] { "A＝面積の重み（外積の和）、B＝面の単位法線の和。時刻 " + string.Join(",", ts) + " s で RecalculateNormals との角度（度）。長さ 0 の法線（潰した爪）は数えない" } };
                var od = Arg("-pl35Out", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/35/bench");
                Directory.CreateDirectory(od);
                File.WriteAllText(Path.Combine(od, "pl35_claw_bench.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
                foreach (var r in rows) UnityEngine.Debug.Log("PL35_BENCH " + r.nameJa + " mean=" + r.msMean.ToString("F3") + " min=" + r.msMin.ToString("F3") + " max=" + r.msMax.ToString("F3"));
                UnityEngine.Debug.Log("PL35_BENCH_DONE V=" + V + " T=" + T + " maxA=" + string.Join(",", maxA) + " maxB=" + string.Join(",", maxB) + " p999A=" + string.Join(",", p999A) + " p999B=" + string.Join(",", p999B) + " zeroU=" + string.Join(",", zU) + " zeroO=" + string.Join(",", zO));
                ol.Release(); cp.Release();
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}
