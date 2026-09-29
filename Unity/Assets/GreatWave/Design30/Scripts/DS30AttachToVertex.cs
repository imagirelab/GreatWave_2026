using System;
using System.Collections.Generic;
using System.IO;
using GreatWave.Design27;
using UnityEngine;

namespace GreatWave.Design30
{
    // 設計30：静止の仮置き（手前の小波の泡の線 M1_ForegroundFoam_Static など）を、シートの 1 つの頂点の動きに付けて動かす。
    // t* では元の位置（ずれ 0）。t* より前は、その頂点のワールドの位置の t* からの差（波の枠の進みと、育つ地形の誘導の高さ）だけ平行移動する。
    // 手前の小波が海から育つ間、泡の線が空中に浮かず、小波の頂とともに海の中から現れる。頂点は t* の位置が target に最も近いもの。
    public class DS30AttachToVertex : MonoBehaviour
    {
        public DS30SheetPlayer sheet;
        [Tooltip("t* のワールドの位置（この点に最も近い頂点に付ける）")]
        public Vector3 target;
        public List<Transform> followers = new List<Transform>();

        int layers, vertex = -1;
        double[] knot;
        float[][] pos;          // [層] 局所の xyz
        Vector3[] base0;
        Vector3 p0;
        readonly int[] sl = new int[4];
        readonly float[] w = new float[4];
        public int Vertex => vertex;
        public float TargetDistance { get; private set; }
        public Vector3 CurrentOffset { get; private set; }

        public void Load()
        {
            if (pos != null) return;
            sheet.EnsureLoaded();
            var m = sheet.PackageMeta;
            layers = m.layers; knot = m.knotTau;
            int n = m.rows * m.cols;
            bool lo = sheet.PosLoFromPackage;
            string lp = null;
            if (lo)
            {
                var jr = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(m.dir, "ds27_keypose.json"))), "ds27_keypose.json");
                lp = Path.Combine(m.dir, DS27Json.Text(jr, "pos_lo_file"));
            }
            using (var fs = new FileStream(Path.Combine(m.dir, "ds27_pos_rgba16.bin"), FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
            using (var fl = lo ? new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read) : null)
            {
                // t* の層で target に最も近い頂点
                var o0 = sheet.OriginAt(knot[layers - 1]);
                var hi = new byte[(long)n * 8];
                fs.Seek((long)(layers - 1) * n * 8, SeekOrigin.Begin);
                Read(fs, hi);
                float best = float.MaxValue;
                for (int v = 0; v < n; v++)
                {
                    var p = Decode(m, hi, v * 8, null, 0) + o0;
                    float d = (p - target).sqrMagnitude;
                    if (d < best) { best = d; vertex = v; }
                }
                TargetDistance = Mathf.Sqrt(best);
                pos = new float[layers][];
                var h8 = new byte[8]; var l4 = new byte[4];
                for (int l = 0; l < layers; l++)
                {
                    fs.Seek(((long)l * n + vertex) * 8, SeekOrigin.Begin); Read(fs, h8);
                    if (lo) { fl.Seek(((long)l * n + vertex) * 4, SeekOrigin.Begin); Read(fl, l4); }
                    var p = Decode(m, h8, 0, lo ? l4 : null, 0);
                    pos[l] = new[] { p.x, p.y, p.z };
                }
            }
            p0 = PosAt(knot[layers - 1]);
            base0 = new Vector3[followers.Count];
            for (int i = 0; i < followers.Count; i++) base0[i] = followers[i] != null ? followers[i].position : Vector3.zero;
        }

        static Vector3 Decode(DS27KeyposePlayer.Meta m, byte[] hi, int off, byte[] lo, int loOff)
        {
            var r = new double[3];
            for (int k = 0; k < 3; k++)
            {
                double q = BitConverter.ToUInt16(hi, off + 2 * k);
                double e = lo != null ? lo[loOff + k] / 255.0 - 0.5 : 0.0;
                r[k] = m.bboxMin[k] + (q + e) / 65535.0 * m.bboxSize[k];
            }
            return new Vector3((float)r[0], (float)r[1], (float)r[2]);
        }

        static void Read(Stream s, byte[] b)
        {
            int got = 0;
            while (got < b.Length) { int k = s.Read(b, got, b.Length - got); if (k <= 0) throw new EndOfStreamException(); got += k; }
        }

        Vector3 PosAt(double tau)
        {
            DS27KeyposePlayer.Weights(knot, tau, sl, w);
            float x = 0, y = 0, z = 0;
            for (int j = 0; j < 4; j++) { var a = pos[sl[j]]; x += w[j] * a[0]; y += w[j] * a[1]; z += w[j] * a[2]; }
            return new Vector3(x, y, z) + sheet.OriginAt(tau);
        }

        public void ApplyTau(double tau)
        {
            Load();
            CurrentOffset = PosAt(tau) - p0;
            for (int i = 0; i < followers.Count; i++) if (followers[i] != null) followers[i].position = base0[i] + CurrentOffset;
        }
    }
}
