using System;
using System.IO;
using GreatWave.Design27;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design30
{
    // 設計30：near と far の継ぎ目（far の行 0。near の外周の 5 点おきと同じ位置で、その間の near の点は線形補間＝T 字の継ぎ目）の下に、
    // 鉛直の幕（継ぎ目の 1 cm 上から 1 m 下まで）を張る。T 字の継ぎ目は数値の上では隙間 0 でも、ラスタライズでは長い辺と短い辺の間に
    // 1 画素より細い割れ目が出て、その奥の空が見える（Editor の穴の検査で 1 コマ最大 1〜2 画素、水平線の近く）。幕は割れ目を通る視線を
    // すぐ下で受け止め、同じ藍濃で塗る。海の面より上に出るのは 1 cm だけ（150 m 先で 1 画素の約 1/6）。
    // far のパッケージの行 0 だけを CPU で復号し、同じ τ・同じ Hermite の重み・同じ枠の原点で毎コマ動かす（DS30FlatSeaRing と同じ読み方）。
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class DS30SeamCurtain : MonoBehaviour
    {
        public DS30SheetPlayer sheet;
        [Tooltip("幕を張る行（far の行 0 = near との継ぎ目）")]
        public int row = 0;
        public float above = 0.01f, below = 1.0f;

        int cols, layers;
        double[] knot;
        float[][] rowPos;
        Mesh mesh;
        Vector3[] verts;
        readonly int[] sl = new int[4];
        readonly float[] w = new float[4];
        public double AppliedTau { get; private set; } = double.NaN;

        public void Load()
        {
            if (rowPos != null) return;
            sheet.EnsureLoaded();
            var m = sheet.PackageMeta;
            cols = m.cols; layers = m.layers; knot = m.knotTau;
            int n = m.rows * m.cols;
            bool lo = sheet.PosLoFromPackage;
            string lp = null;
            if (lo)
            {
                var jr = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(m.dir, "ds27_keypose.json"))), "ds27_keypose.json");
                lp = Path.Combine(m.dir, DS27Json.Text(jr, "pos_lo_file"));
            }
            var hi = new byte[cols * 8];
            var lob = new byte[cols * 4];
            rowPos = new float[layers][];
            using (var fs = new FileStream(Path.Combine(m.dir, "ds27_pos_rgba16.bin"), FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var fl = lo ? new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read) : null)
            {
                for (int l = 0; l < layers; l++)
                {
                    fs.Seek(((long)l * n + (long)row * cols) * 8, SeekOrigin.Begin);
                    Read(fs, hi);
                    if (lo) { fl.Seek(((long)l * n + (long)row * cols) * 4, SeekOrigin.Begin); Read(fl, lob); }
                    var a = new float[cols * 3];
                    for (int c = 0; c < cols; c++)
                        for (int k = 0; k < 3; k++)
                        {
                            double q = BitConverter.ToUInt16(hi, c * 8 + 2 * k);
                            double off = lo ? lob[c * 4 + k] / 255.0 - 0.5 : 0.0;
                            a[3 * c + k] = (float)(m.bboxMin[k] + (q + off) / 65535.0 * m.bboxSize[k]);
                        }
                    rowPos[l] = a;
                }
            }
            mesh = new Mesh { name = "DS30 継ぎ目の幕", indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
            verts = new Vector3[cols * 2];
            var tris = new int[(cols - 1) * 6];
            for (int c = 0; c + 1 < cols; c++)
            {
                int t = c * 6;
                tris[t] = 2 * c; tris[t + 1] = 2 * c + 1; tris[t + 2] = 2 * c + 2;
                tris[t + 3] = 2 * c + 2; tris[t + 4] = 2 * c + 1; tris[t + 5] = 2 * c + 3;
            }
            mesh.vertices = verts;
            mesh.SetTriangles(tris, 0, false);
            mesh.bounds = sheet.WorldBounds;
            GetComponent<MeshFilter>().sharedMesh = mesh;
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
        }

        static void Read(Stream s, byte[] b)
        {
            int got = 0;
            while (got < b.Length) { int k = s.Read(b, got, b.Length - got); if (k <= 0) throw new EndOfStreamException(); got += k; }
        }

        public void ApplyTau(double tau)
        {
            Load();
            DS27KeyposePlayer.Weights(knot, tau, sl, w);
            var o = sheet.OriginAt(tau);
            for (int c = 0; c < cols; c++)
            {
                float x = 0, y = 0, z = 0;
                for (int j = 0; j < 4; j++)
                {
                    var a = rowPos[sl[j]];
                    x += w[j] * a[3 * c]; y += w[j] * a[3 * c + 1]; z += w[j] * a[3 * c + 2];
                }
                verts[2 * c] = new Vector3(x + o.x, y + o.y + above, z + o.z);
                verts[2 * c + 1] = new Vector3(x + o.x, y + o.y - below, z + o.z);
            }
            mesh.vertices = verts;
            AppliedTau = tau;
        }

        void OnDestroy()
        {
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); }
        }
    }
}
