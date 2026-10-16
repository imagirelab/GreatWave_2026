using System;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.FLIP3D
{
    // FLIP3D：DA3 の面の記録のクリップ（GW45CLP1）と manifest.json を読み、コマごとの Mesh を作る（2026-10-16、進行役）。
    // 形は Tools/GWWaveGen/flip45/g45_export_unity.py・flip3d/f3d_export.py の説明と同じ（little endian）。
    //   クリップの頭 64 バイト："GW45CLP1"、uint32 版、uint32 コマの数 n、float64 fps（面の記録の数/s。DA3 は 8）、float64 最初の時刻、int32 最初のコマ。
    //   目次 n × 16 バイト：uint64 位置、uint32 長さ、uint32 予備。
    //   1 コマ（GW45SRF1）：頭 96 バイト（float64 t、int32 コマ、uint32 nv、uint32 nt、float32×3 箱の下、float32×3 箱の上、float32 静かな水面のずれ）、
    //   位置 uint16×3×nv（箱の中を 0〜65535）、法線 uint16×2×nv（8 方向の写像）、v float16×3×nv（使わない）、添字 uint32×3×nt。
    // 読み解きは量子化を戻すだけで、形は変えない（平滑・補間・ずらしをしない）。横の写しは FLIP3DPlayer が z → −z の変換で描く。
    [Serializable]
    public class FLIP3DManifest
    {
        public string format; public int version; public string clip_file; public long clip_bytes; public string clip_sha256;
        public int frames; public double record_fps, sim_fps; public int record_step_frames;
        public double t_first, t_last; public int frame_first, frame_last;
        public double loop_seconds, loop_start_s, loop_end_s;
        public int vert_max, tri_max; public float still_offset_m;
        public int breaker_k, print_record_frame, print_record_index, print_bestframes_frame;
        public double print_record_t, print_bestframes_t, print_score3;
        public float print_crest_x, print_crest_eta;
        public double seam_mesh_median_m, seam_mesh_p95_m, seam_mesh_max_m, seam_eta_rms_break_m, step_mesh_p95_median_m;
        public string bed_file; public int bed_nx, bed_nz; public float bed_x0, bed_z0, bed_dx;
        public float tank_x0, tank_x1, tank_half_width;
        public float seat_x, seat_z, seat_eye_m;
        public double heave_fps; public float[] heave; public float heave_seam_jump_m;
    }

    public sealed class FLIP3DClip
    {
        public FLIP3DManifest Manifest { get; private set; }
        public Mesh[] Meshes { get; private set; }
        public double[] Times { get; private set; }
        public int[] SimFrames { get; private set; }
        public Mesh BedMesh { get; private set; }
        public double LoadSeconds { get; private set; }
        public long ClipBytes { get; private set; }

        public static FLIP3DClip Load(string dir)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var c = new FLIP3DClip();
            string mp = Path.Combine(dir, "manifest.json");
            c.Manifest = JsonUtility.FromJson<FLIP3DManifest>(File.ReadAllText(mp, Encoding.UTF8));
            byte[] all = File.ReadAllBytes(Path.Combine(dir, c.Manifest.clip_file));
            c.ClipBytes = all.LongLength;
            if (Encoding.ASCII.GetString(all, 0, 8) != "GW45CLP1") throw new InvalidDataException("GW45CLP1 でない");
            int n = (int)BitConverter.ToUInt32(all, 12);
            double fps = BitConverter.ToDouble(all, 16);
            if (n != c.Manifest.frames || Math.Abs(fps - c.Manifest.record_fps) > 1e-9) throw new InvalidDataException("manifest とクリップの頭が違う");
            c.Meshes = new Mesh[n];
            c.Times = new double[n];
            c.SimFrames = new int[n];
            for (int i = 0; i < n; i++)
            {
                long o = BitConverter.ToInt64(all, 64 + 16 * i);
                c.Meshes[i] = DecodeFrame(all, (int)o, out c.Times[i], out c.SimFrames[i]);
                c.Meshes[i].name = "FLIP3D_DA3_f" + c.SimFrames[i].ToString("D5");
            }
            c.BedMesh = BuildBed(dir, c.Manifest);
            c.LoadSeconds = sw.Elapsed.TotalSeconds;
            return c;
        }

        // 1 コマを配列に読み解く（Mesh を作る時と、確かめの書き出しで同じ関数を使う）
        public static void DecodeArrays(byte[] b, int o, out Vector3[] pos, out Vector3[] nrm, out int[] idx, out double t, out int frame, out Vector3 lo, out Vector3 hi)
        {
            if (Encoding.ASCII.GetString(b, o, 8) != "GW45SRF1") throw new InvalidDataException("GW45SRF1 でない");
            int hb = (int)BitConverter.ToUInt32(b, o + 12);
            t = BitConverter.ToDouble(b, o + 16);
            frame = BitConverter.ToInt32(b, o + 24);
            int nv = (int)BitConverter.ToUInt32(b, o + 28), nt = (int)BitConverter.ToUInt32(b, o + 32);
            lo = new Vector3(BitConverter.ToSingle(b, o + 36), BitConverter.ToSingle(b, o + 40), BitConverter.ToSingle(b, o + 44));
            hi = new Vector3(BitConverter.ToSingle(b, o + 48), BitConverter.ToSingle(b, o + 52), BitConverter.ToSingle(b, o + 56));
            var span = (hi - lo) / 65535f;
            pos = new Vector3[nv];
            nrm = new Vector3[nv];
            int p = o + hb;
            for (int k = 0; k < nv; k++, p += 6)
                pos[k] = new Vector3(lo.x + BitConverter.ToUInt16(b, p) * span.x, lo.y + BitConverter.ToUInt16(b, p + 2) * span.y, lo.z + BitConverter.ToUInt16(b, p + 4) * span.z);
            for (int k = 0; k < nv; k++, p += 4)
                nrm[k] = OctDecode(BitConverter.ToUInt16(b, p), BitConverter.ToUInt16(b, p + 2));
            p += 6 * nv;                                  // 速さ v（使わない）
            idx = new int[3 * nt];
            Buffer.BlockCopy(b, p, idx, 0, 12 * nt);
            // 座標は計画の（右手の）x・上・横をそのまま Unity の（左手の）x・y・z に置くので、見かけの回りが逆になる。
            // 三角形の 2 番目と 3 番目を入れ替えて、Unity の表（時計回り）にそろえる（点の位置と法線はそのまま）
            for (int k = 0; k < idx.Length; k += 3) { int tmp = idx[k + 1]; idx[k + 1] = idx[k + 2]; idx[k + 2] = tmp; }
        }

        static Mesh DecodeFrame(byte[] b, int o, out double t, out int frame)
        {
            DecodeArrays(b, o, out var pos, out var nrm, out var idx, out t, out frame, out var lo, out var hi);
            var m = new Mesh { indexFormat = IndexFormat.UInt32 };
            m.vertices = pos;
            m.normals = nrm;
            m.SetTriangles(idx, 0, false);
            m.bounds = new Bounds((lo + hi) * 0.5f, hi - lo);
            m.UploadMeshData(true);                       // GPU に置いたまま、主メモリーの写しを捨てる
            return m;
        }

        // g45_export_unity.oct_decode と同じ式
        static Vector3 OctDecode(ushort a, ushort c)
        {
            float x = a / 65535f * 2f - 1f, y = c / 65535f * 2f - 1f;
            float z = 1f - Mathf.Abs(x) - Mathf.Abs(y);
            float t = Mathf.Max(-z, 0f);
            x = x >= 0 ? x - t : x + t;
            y = y >= 0 ? y - t : y + t;
            return new Vector3(x, y, z).normalized;
        }

        // 海底：DA3 の cfg の海底（g49_common.bed_z）を f3d_export.py が 1 m の格子で書いた物。全幅（横 −85〜85 m）
        static Mesh BuildBed(string dir, FLIP3DManifest mf)
        {
            string p = Path.Combine(dir, mf.bed_file);
            if (!File.Exists(p)) return null;
            byte[] raw = File.ReadAllBytes(p);
            int nx = mf.bed_nx, nz = mf.bed_nz;
            var h = new float[nx * nz];
            Buffer.BlockCopy(raw, 0, h, 0, 4 * nx * nz);
            var v = new Vector3[nx * nz];
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < nx; i++)
                    v[j * nx + i] = new Vector3(mf.bed_x0 + i * mf.bed_dx, h[j * nx + i], mf.bed_z0 + j * mf.bed_dx);
            var tri = new int[(nx - 1) * (nz - 1) * 6];
            int q = 0;
            for (int j = 0; j < nz - 1; j++)
                for (int i = 0; i < nx - 1; i++)
                {
                    int a = j * nx + i, b2 = a + 1, c = a + nx, d = c + 1;
                    tri[q++] = a; tri[q++] = c; tri[q++] = b2;
                    tri[q++] = b2; tri[q++] = c; tri[q++] = d;
                }
            var m = new Mesh { indexFormat = IndexFormat.UInt32, name = "FLIP3D_DA3_bed" };
            m.vertices = v;
            m.SetTriangles(tri, 0, true);
            m.RecalculateNormals();
            m.UploadMeshData(true);
            return m;
        }
    }
}
