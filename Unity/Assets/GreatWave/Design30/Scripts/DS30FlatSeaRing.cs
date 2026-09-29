using System;
using System.Collections.Generic;
using System.IO;
using GreatWave.Design27;
using GreatWave.Design29;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design30
{
    // 設計30：周りの海の外の平らな海（美術優先27 の「AF27 参照海面」の上面、y = −0.07、x −500〜500・z −400〜600 の四角）を、
    // 遠い海のシート（far）の足跡の中では描かない輪にしたもの（第A部の約束 README_interface.txt の 3 の推奨）。
    // 内側の縁 = far の最後の行（垂直のすその下の縁）の水平の位置。far のパッケージの最後の行だけを CPU で復号し、
    // 同じ τ・同じ Hermite の重み（DS27KeyposePlayer.Weights）・同じ枠の原点で毎コマ動かす。外側の縁 = 四角（隅も含める）。
    // 高さは四角と同じ上面の y。far のすそ（y = 0 → −8 m）が内側の縁で平らな面を貫くので、継ぎ目に穴は開かない。
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class DS30FlatSeaRing : MonoBehaviour
    {
        public DS30SheetPlayer far;
        [Tooltip("平らな海の上面の高さ（m）")]
        public float surfaceY = -0.07f;
        [Tooltip("四角の範囲（x の最小・最大、z の最小・最大）")]
        public Vector4 square = new Vector4(-500f, 500f, -400f, 600f);

        int cols, layers;
        double[] knot;
        float[][] lastRow;    // [層][列 × 3] 局所の位置
        Mesh mesh;
        readonly int[] sl = new int[4];
        readonly float[] w = new float[4];
        public double AppliedTau { get; private set; } = double.NaN;
        public float InnerRadiusMin { get; private set; }
        public float InnerRadiusMax { get; private set; }

        public void Load()
        {
            if (lastRow != null) return;
            far.EnsureLoaded();
            var m = far.PackageMeta;
            cols = m.cols; layers = m.layers; knot = m.knotTau;
            int n = m.rows * m.cols, r = m.rows - 1;
            lastRow = new float[layers][];
            bool lo = far.PosLoFromPackage;
            string lp = null;
            if (lo)
            {
                var jr = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(m.dir, "ds27_keypose.json"))), "ds27_keypose.json");
                lp = Path.Combine(m.dir, DS27Json.Text(jr, "pos_lo_file"));
            }
            var hi = new byte[cols * 8];
            var lob = new byte[cols * 4];
            using (var fs = new FileStream(Path.Combine(m.dir, "ds27_pos_rgba16.bin"), FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var fl = lo ? new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read) : null)
            {
                for (int l = 0; l < layers; l++)
                {
                    fs.Seek(((long)l * n + (long)r * cols) * 8, SeekOrigin.Begin);
                    Read(fs, hi);
                    if (lo) { fl.Seek(((long)l * n + (long)r * cols) * 4, SeekOrigin.Begin); Read(fl, lob); }
                    var a = new float[cols * 3];
                    for (int c = 0; c < cols; c++)
                        for (int k = 0; k < 3; k++)
                        {
                            double q = BitConverter.ToUInt16(hi, c * 8 + 2 * k);
                            double off = lo ? lob[c * 4 + k] / 255.0 - 0.5 : 0.0;
                            a[3 * c + k] = (float)(m.bboxMin[k] + (q + off) / 65535.0 * m.bboxSize[k]);
                        }
                    lastRow[l] = a;
                }
            }
            mesh = new Mesh { name = "DS30 平らな海の輪", indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
            GetComponent<MeshFilter>().sharedMesh = mesh;
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
        }

        static void Read(Stream s, byte[] b)
        {
            int got = 0;
            while (got < b.Length) { int k = s.Read(b, got, b.Length - got); if (k <= 0) throw new EndOfStreamException(); got += k; }
        }

        /// <summary>τ のときの内側の縁（ワールド、列の順）。</summary>
        public Vector3[] InnerAt(double tau)
        {
            Load();
            DS27KeyposePlayer.Weights(knot, tau, sl, w);
            var o = far.OriginAt(tau);
            var p = new Vector3[cols];
            for (int c = 0; c < cols; c++)
            {
                float x = 0, y = 0, z = 0;
                for (int j = 0; j < 4; j++)
                {
                    var a = lastRow[sl[j]];
                    x += w[j] * a[3 * c]; y += w[j] * a[3 * c + 1]; z += w[j] * a[3 * c + 2];
                }
                p[c] = new Vector3(x + o.x, y + o.y, z + o.z);
            }
            return p;
        }

        public void ApplyTau(double tau)
        {
            var inner = InnerAt(tau);
            int m = inner.Length;
            // 閉じた輪（最後の列が最初の列の写し）なら最後を落とす
            if (m > 2 && (inner[m - 1] - inner[0]).sqrMagnitude < 1e-6f) m--;
            var ctr = Vector3.zero;
            for (int i = 0; i < m; i++) ctr += inner[i];
            ctr /= m;
            float rmin = float.MaxValue, rmax = 0;
            var verts = new List<Vector3>(m * 2 + 8);
            var tris = new List<int>(m * 9);
            for (int i = 0; i < m; i++)
            {
                var d = new Vector2(inner[i].x - ctr.x, inner[i].z - ctr.z);
                rmin = Mathf.Min(rmin, d.magnitude); rmax = Mathf.Max(rmax, d.magnitude);
                verts.Add(new Vector3(inner[i].x, surfaceY, inner[i].z));
            }
            // 外側：中心から内側の頂点の向きへ伸ばした線と四角の交点
            var outerAng = new float[m];
            for (int i = 0; i < m; i++)
            {
                var d = new Vector2(inner[i].x - ctr.x, inner[i].z - ctr.z).normalized;
                verts.Add(SquareHit(ctr, d));
                outerAng[i] = Mathf.Atan2(d.y, d.x);
            }
            var corners = new[] { new Vector2(square.y, square.w), new Vector2(square.x, square.w), new Vector2(square.x, square.z), new Vector2(square.y, square.z) };
            var cornerIdx = new int[4];
            var cornerAng = new float[4];
            for (int k = 0; k < 4; k++)
            {
                cornerIdx[k] = verts.Count;
                verts.Add(new Vector3(corners[k].x, surfaceY, corners[k].y));
                cornerAng[k] = Mathf.Atan2(corners[k].y - ctr.z, corners[k].x - ctr.x);
            }
            for (int i = 0; i < m; i++)
            {
                int j = (i + 1) % m;
                int ii = i, ij = j, oi = m + i, oj = m + j;
                // この区間（角度 outerAng[i] → outerAng[j]、向きは列の進む向き）にある四角の隅
                int corner = -1;
                float a0 = outerAng[i], a1 = outerAng[j];
                float span = DeltaAng(a0, a1);
                for (int k = 0; k < 4; k++)
                {
                    float dk = DeltaAng(a0, cornerAng[k]);
                    if (Mathf.Abs(span) > 1e-6f && Mathf.Sign(dk) == Mathf.Sign(span) && Mathf.Abs(dk) < Mathf.Abs(span)) corner = cornerIdx[k];
                }
                if (corner < 0)
                {
                    tris.Add(ii); tris.Add(oi); tris.Add(oj);
                    tris.Add(ii); tris.Add(oj); tris.Add(ij);
                }
                else
                {
                    tris.Add(ii); tris.Add(oi); tris.Add(corner);
                    tris.Add(ii); tris.Add(corner); tris.Add(oj);
                    tris.Add(ii); tris.Add(oj); tris.Add(ij);
                }
            }
            mesh.Clear();
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0, true);
            mesh.RecalculateNormals();
            InnerRadiusMin = rmin; InnerRadiusMax = rmax;
            AppliedTau = tau;
        }

        static float DeltaAng(float a, float b)
        {
            float d = b - a;
            while (d > Mathf.PI) d -= 2 * Mathf.PI;
            while (d < -Mathf.PI) d += 2 * Mathf.PI;
            return d;
        }

        Vector3 SquareHit(Vector3 c, Vector2 d)
        {
            float best = float.MaxValue;
            if (Mathf.Abs(d.x) > 1e-9f) { best = Mathf.Min(best, Pos((square.x - c.x) / d.x)); best = Mathf.Min(best, Pos((square.y - c.x) / d.x)); }
            if (Mathf.Abs(d.y) > 1e-9f) { best = Mathf.Min(best, Pos((square.z - c.z) / d.y)); best = Mathf.Min(best, Pos((square.w - c.z) / d.y)); }
            return new Vector3(c.x + d.x * best, surfaceY, c.z + d.y * best);
        }

        static float Pos(float t) => t > 0 ? t : float.MaxValue;

        void OnDestroy()
        {
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); }
        }
    }
}
