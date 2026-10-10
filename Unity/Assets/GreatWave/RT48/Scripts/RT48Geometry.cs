using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.RT48
{
    // RT48 の形を作る（計画 §3.2）。座標：X ＝ x − 座席の x、Y ＝ 静かな水面からの高さ、Z ＝ 頂の向き。1 単位 1 m。
    //   ・掃いた面：点の番号 i（曲線に沿って N）× 頂の向きの線 j（Z = 0、±250、±1000、±5000、±20000 m）の格子。
    //     位置は頂点のシェーダー（RT48Decode.hlsl）が作る。メッシュは uv = (i, j)、位置 = (0, 0, Z_j) だけを持つ。
    //     三角形の表は空気の側（曲線の左の法線 (−t.y, t.x) の向き）。
    //   ・まわりの海：Y = 0 の平らな面（半径 25 km の四角）。波の面のある四角（x 100〜925 m、|Z| ≤ 20 km）に穴。
    //   ・離れた水：閉じた線を同じ ±20 km に掃いた管（CPU、コマが変わる時だけ作り直す）。
    public static class RT48Geometry
    {
        public static readonly float[] SweepZ = { -20000f, -5000f, -1000f, -250f, 0f, 250f, 1000f, 5000f, 20000f };
        public const float SeaHalfM = 25000f;

        public static Mesh BuildSweep(int n)
        {
            int nz = SweepZ.Length;
            var verts = new Vector3[n * nz];
            var uvs = new Vector2[n * nz];
            var nrm = new Vector3[n * nz];
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < n; i++)
                {
                    int v = j * n + i;
                    verts[v] = new Vector3(0f, 0f, SweepZ[j]);
                    uvs[v] = new Vector2(i, j);
                    nrm[v] = Vector3.up;
                }
            var tris = new int[(n - 1) * (nz - 1) * 6];
            int t = 0;
            for (int j = 0; j < nz - 1; j++)
                for (int i = 0; i < n - 1; i++)
                {
                    int a = j * n + i, b = (j + 1) * n + i, c = j * n + i + 1, d = (j + 1) * n + i + 1;
                    // (i,j),(i,j+1),(i+1,j) と (i+1,j),(i,j+1),(i+1,j+1)：表の法線 cross(b−a, c−a) が曲線の左の法線の向き
                    tris[t++] = a; tris[t++] = b; tris[t++] = c;
                    tris[t++] = c; tris[t++] = b; tris[t++] = d;
                }
            var m = new Mesh { name = "RT48 掃いた面 " + n + "×" + nz, indexFormat = IndexFormat.UInt32 };
            m.SetVertices(verts);
            m.SetUVs(0, uvs);
            m.SetNormals(nrm);
            m.SetTriangles(tris, 0, false);
            m.bounds = new Bounds(Vector3.zero, new Vector3(4000f, 400f, 2f * SweepZ[nz - 1] + 200f));
            return m;
        }

        // 穴（X が xa〜xb、|Z| ≤ zHole）の空いた四角の海。
        public static Mesh BuildSea(float xa, float xb, float zHole, float half = SeaHalfM)
        {
            var verts = new List<Vector3>();
            var tris = new List<int>();
            void Quad(float x0, float x1, float z0, float z1)
            {
                if (x1 <= x0 || z1 <= z0) return;
                int b = verts.Count;
                verts.Add(new Vector3(x0, 0, z0)); verts.Add(new Vector3(x0, 0, z1)); verts.Add(new Vector3(x1, 0, z0)); verts.Add(new Vector3(x1, 0, z1));
                // (x0,z0),(x0,z1),(x1,z0)：表が上
                tris.Add(b); tris.Add(b + 1); tris.Add(b + 2);
                tris.Add(b + 2); tris.Add(b + 1); tris.Add(b + 3);
            }
            Quad(-half, xa, -half, half);
            Quad(xb, half, -half, half);
            Quad(xa, xb, zHole, half);
            Quad(xa, xb, -half, -zHole);
            var m = new Mesh { name = "RT48 まわりの海" };
            m.SetVertices(verts);
            m.SetTriangles(tris, 0);
            var n = new Vector3[verts.Count];
            for (int i = 0; i < n.Length; i++) n[i] = Vector3.up;
            m.SetNormals(n);
            m.bounds = new Bounds(Vector3.zero, new Vector3(2 * half, 10f, 2 * half));
            return m;
        }

        // 閉じた線（水）を ±20 km に掃いた管。pts は保存の座標の float2、xShift で X へ、taper で y を下ろす。
        public static void BuildLoops(Mesh mesh, float[] pts, List<RT48Loop> loops, double xShift, double[] taper,
                                      List<Vector3> v, List<Vector3> nr, List<int> tri, List<Vector2> work)
        {
            v.Clear(); nr.Clear(); tri.Clear();
            int nz = SweepZ.Length;
            foreach (var L in loops)
            {
                if (L.kind != 0 || L.count < 3) continue;   // 囲まれた空気は外から見えないので描かない（計画 §2.4）
                work.Clear();
                double area2 = 0;
                for (int k = 0; k < L.count; k++)
                {
                    double x = pts[2 * (L.first + k)], y = pts[2 * (L.first + k) + 1];
                    work.Add(new Vector2((float)(x + xShift), (float)(y * RT48BoatMotion.TaperWeight(x, taper))));
                }
                for (int k = 0; k < work.Count; k++) { var p = work[k]; var q = work[(k + 1) % work.Count]; area2 += (double)p.x * q.y - (double)q.x * p.y; }
                if (area2 > 0) work.Reverse();   // 時計回りにそろえる：左の法線が外（空気）を向く
                int n = work.Count, b = v.Count;
                for (int j = 0; j < nz; j++)
                    for (int k = 0; k < n; k++)
                    {
                        var p0 = work[(k - 1 + n) % n]; var p1 = work[(k + 1) % n];
                        var tg = p1 - p0;
                        var nn = new Vector3(-tg.y, tg.x, 0f).normalized;
                        v.Add(new Vector3(work[k].x, work[k].y, SweepZ[j]));
                        nr.Add(nn);
                    }
                for (int j = 0; j < nz - 1; j++)
                    for (int k = 0; k < n; k++)
                    {
                        int k1 = (k + 1) % n;
                        int a = b + j * n + k, bb = b + (j + 1) * n + k, c = b + j * n + k1, d = b + (j + 1) * n + k1;
                        tri.Add(a); tri.Add(bb); tri.Add(c);
                        tri.Add(c); tri.Add(bb); tri.Add(d);
                    }
            }
            mesh.Clear();
            mesh.indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            mesh.SetVertices(v);
            mesh.SetNormals(nr);
            mesh.SetTriangles(tri, 0, false);
            mesh.bounds = new Bounds(Vector3.zero, new Vector3(4000f, 400f, 2f * SweepZ[nz - 1] + 200f));
        }

        // 簡単な船（水線の長さ 12 m、幅 2 m、船首は −X）。原点は水線の真ん中。
        public static Mesh BuildBoat()
        {
            float L = 6f, B = 1f, top = 0.45f, bottom = -0.45f, bow = -6.8f;
            // 断面の 5 つの x（船尾 → 船首の手前）と、船首の 1 点
            float[] xs = { L, 3f, 0f, -3f, -L + 0.8f };
            float[] half = { 0.85f * B, B, B, B, 0.75f * B };
            var verts = new List<Vector3>();
            var tris = new List<int>();
            // 各断面：上左、上右、下右、下左
            foreach (var (x, i) in Enumerate(xs))
            {
                float h = half[i];
                verts.Add(new Vector3(x, top, -h)); verts.Add(new Vector3(x, top, h));
                verts.Add(new Vector3(x, bottom, 0.6f * h)); verts.Add(new Vector3(x, bottom, -0.6f * h));
            }
            int bowTop = verts.Count; verts.Add(new Vector3(bow, top + 0.15f, 0f));
            int bowBot = verts.Count; verts.Add(new Vector3(bow + 0.6f, bottom + 0.1f, 0f));
            int ns = xs.Length;
            for (int s = 0; s < ns - 1; s++)
            {
                int a = s * 4, b = (s + 1) * 4;
                for (int e = 0; e < 4; e++)
                {
                    int e1 = (e + 1) % 4;
                    AddQuad(tris, a + e, a + e1, b + e1, b + e);
                }
            }
            // 船尾の板
            AddQuad(tris, 0, 3, 2, 1);
            // 船首：最後の断面と船首の 2 点
            int l = (ns - 1) * 4;
            tris.AddRange(new[] { l + 0, l + 1, bowTop });      // 甲板
            tris.AddRange(new[] { l + 1, l + 2, bowBot, l + 1, bowBot, bowTop });
            tris.AddRange(new[] { l + 3, l + 0, bowTop, l + 3, bowTop, bowBot });
            tris.AddRange(new[] { l + 2, l + 3, bowBot });
            var m = new Mesh { name = "RT48 船（簡単な形）" };
            m.SetVertices(verts);
            m.SetTriangles(tris, 0);
            // 外を向いているかを、真ん中からの向きで確かめて、内を向く三角形は裏返す
            var c = Vector3.zero; foreach (var p in verts) c += p; c /= verts.Count;
            for (int t = 0; t < tris.Count; t += 3)
            {
                var p0 = verts[tris[t]]; var p1 = verts[tris[t + 1]]; var p2 = verts[tris[t + 2]];
                var nrm = Vector3.Cross(p1 - p0, p2 - p0);
                if (Vector3.Dot(nrm, (p0 + p1 + p2) / 3f - c) < 0) { int tmp = tris[t + 1]; tris[t + 1] = tris[t + 2]; tris[t + 2] = tmp; }
            }
            // 平らな面の陰にするため、三角形ごとに点を分ける
            var fv = new List<Vector3>(tris.Count);
            var ft = new List<int>(tris.Count);
            for (int t = 0; t < tris.Count; t++) { fv.Add(verts[tris[t]]); ft.Add(t); }
            m.Clear();
            m.SetVertices(fv);
            m.SetTriangles(ft, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        static void AddQuad(List<int> t, int a, int b, int c, int d) { t.Add(a); t.Add(b); t.Add(c); t.Add(a); t.Add(c); t.Add(d); }

        static IEnumerable<(float, int)> Enumerate(float[] xs) { for (int i = 0; i < xs.Length; i++) yield return (xs[i], i); }
    }
}
