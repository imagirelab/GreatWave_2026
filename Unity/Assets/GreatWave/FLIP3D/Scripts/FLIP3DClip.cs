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
    // 2026-10-16 追記（続けて再生する長い記録）：manifest の形がもう 1 つ増えた。
    //   "GW45LIST1"：クリップのファイルを作らず、計算の記録のフォルダーの面の記録 surf/s_FFFFF.gw45s をそのまま読む（4 GB の写しを作らない）。
    //   どのファイルを何番目に見せるかは source_frames、長さと SHA-256 は source_bytes・source_sha256（f3d_export.py --long が書く）。
    //   読み解きの関数（DecodeInto）は、前の全部を GPU に置く読み方・続けて読む読み方（FLIP3DStream）・確かめの書き出しで同じ物を使う。
    [Serializable]
    public class FLIP3DBreaker
    {
        public int k, frame, win_first, win_last;
        public double t, score3;
        public float hood, lip;
    }

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
        // 2026-10-16 追記（続けて再生する長い記録。前の manifest にない項目は空のまま＝12 s の繰り返しの窓）
        public string clip_kind;                       // 空・"loop"：繰り返しの窓、"continuous"：続けて 1 回、"synthetic_test"：試験用の合成の列（本番ではない）
        public string source_run;
        public int[] source_frames; public long[] source_bytes; public string[] source_sha256;
        public string stream_dir, stream_dir_rel, stream_pattern;
        public double play_from_s, play_to_s;          // 既定の再生の範囲（計算の時刻 s）。0 と 0 なら全部
        public FLIP3DBreaker[] breakers;               // 範囲の中の崩れと、score3 で原画に最も近い瞬間（DA3 の pana/best_frames.json）
        public string breakers_source;
        // 2026-10-17 追記（FLIP50 の D の水槽のカメラ。flip50g2/f3d50_export_src.py --cams が書く）。前の manifest にない項目は空のまま＝場面の値を使う
        public float[] cam_seat_look_at, cam_print_pos, cam_print_look_at;
        public float cam_seat_fov_v, cam_print_fov_v;
        // 2026-10-17 追記（Claude）：水を両面で描く（表示だけ。flip50g2/f3d50_export_src.py --water-double-sided が書く）。記録の面の穴から空が見えるのを、
        // 穴の向こうの水の裏の面で塞ぐ（FLIP3DPlayer.ApplyWaterSides）。前の manifest にない項目は false＝前と同じ片面
        public bool water_double_sided;

        public bool IsContinuousKind => clip_kind == "continuous" || clip_kind == "synthetic_test";

        public static FLIP3DManifest Read(string dir)
        {
            return JsonUtility.FromJson<FLIP3DManifest>(File.ReadAllText(Path.Combine(dir, "manifest.json"), Encoding.UTF8));
        }
    }

    // 1 コマの頭（読み解かずに分かる数）
    public struct FLIP3DRecordHeader
    {
        public double t; public int frame, nv, nt, headBytes; public Vector3 lo, hi;
    }

    // 記録の置き場所の目次：GW45CLP1（1 つのファイルの中の位置と長さ）と GW45LIST1（記録 1 つが 1 つのファイル）を同じ形で引く
    public sealed class FLIP3DRecordIndex
    {
        public string Format { get; private set; }
        public int Count { get; private set; }
        public string[] Files { get; private set; }     // GW45CLP1 は 1 つ、GW45LIST1 は記録の数だけ
        public long[] Offsets { get; private set; }
        public int[] Lengths { get; private set; }
        public int MaxLength { get; private set; }
        public long TotalBytes { get; private set; }
        public string Where { get; private set; }

        public static FLIP3DRecordIndex Open(string dir, FLIP3DManifest mf)
        {
            var x = new FLIP3DRecordIndex { Format = mf.format };
            if (mf.format == "GW45CLP1")
            {
                string cp = Path.Combine(dir, mf.clip_file);
                using (var fs = new FileStream(cp, FileMode.Open, FileAccess.Read, FileShare.Read, 4096))
                {
                    var head = new byte[64];
                    ReadFully(fs, head, 64);
                    if (Encoding.ASCII.GetString(head, 0, 8) != "GW45CLP1") throw new InvalidDataException("GW45CLP1 でない");
                    int n = (int)BitConverter.ToUInt32(head, 12);
                    double fps = BitConverter.ToDouble(head, 16);
                    if (n != mf.frames || Math.Abs(fps - mf.record_fps) > 1e-9) throw new InvalidDataException("manifest とクリップの頭が違う");
                    var idx = new byte[16 * n];
                    ReadFully(fs, idx, idx.Length);
                    x.Count = n; x.Files = new[] { cp }; x.Offsets = new long[n]; x.Lengths = new int[n];
                    for (int i = 0; i < n; i++) { x.Offsets[i] = BitConverter.ToInt64(idx, 16 * i); x.Lengths[i] = (int)BitConverter.ToUInt32(idx, 16 * i + 8); }
                    x.TotalBytes = fs.Length;
                }
                x.Where = cp;
            }
            else if (mf.format == "GW45LIST1")
            {
                string sd = null;
                if (!string.IsNullOrEmpty(mf.stream_dir_rel)) { var p = Path.GetFullPath(Path.Combine(dir, mf.stream_dir_rel)); if (Directory.Exists(p)) sd = p; }
                if (sd == null && !string.IsNullOrEmpty(mf.stream_dir) && Directory.Exists(mf.stream_dir)) sd = mf.stream_dir;
                if (sd == null) throw new DirectoryNotFoundException("面の記録のフォルダーがない：" + mf.stream_dir_rel + " / " + mf.stream_dir);
                int n = mf.frames;
                if (mf.source_frames == null || mf.source_frames.Length != n || mf.source_bytes == null || mf.source_bytes.Length != n)
                    throw new InvalidDataException("GW45LIST1 の source_frames・source_bytes の数が frames と違う");
                x.Count = n; x.Files = new string[n]; x.Offsets = new long[n]; x.Lengths = new int[n];
                string pat = string.IsNullOrEmpty(mf.stream_pattern) ? "s_{0:D5}.gw45s" : mf.stream_pattern;
                long tot = 0;
                for (int i = 0; i < n; i++)
                {
                    x.Files[i] = Path.Combine(sd, string.Format(System.Globalization.CultureInfo.InvariantCulture, pat, mf.source_frames[i]));
                    x.Lengths[i] = (int)mf.source_bytes[i];
                    tot += mf.source_bytes[i];
                }
                x.TotalBytes = tot;
                x.Where = sd;
            }
            else throw new InvalidDataException("知らない形：" + mf.format);
            int mx = 0; foreach (var l in x.Lengths) mx = Math.Max(mx, l);
            x.MaxLength = mx;
            return x;
        }

        static void ReadFully(Stream s, byte[] b, int n)
        {
            int got = 0;
            while (got < n) { int r = s.Read(b, got, n - got); if (r <= 0) throw new EndOfStreamException(); got += r; }
        }

        // 1 つの読み手（スレッドごとに 1 つ）。GW45CLP1 はファイルを開いたままにする。GW45LIST1 は記録ごとに開いて閉じる
        public sealed class Reader : IDisposable
        {
            readonly FLIP3DRecordIndex x;
            FileStream single;
            public Reader(FLIP3DRecordIndex x) { this.x = x; }

            // 記録 i のバイトを buf の頭に読む（buf が小さければ大きくする）。返り値は長さ
            public int Read(int i, ref byte[] buf)
            {
                int len = x.Lengths[i];
                if (buf == null || buf.Length < len) buf = new byte[Math.Max(len, x.MaxLength)];
                if (x.Files.Length == 1 && x.Format == "GW45CLP1")
                {
                    if (single == null) single = new FileStream(x.Files[0], FileMode.Open, FileAccess.Read, FileShare.Read, 4096, FileOptions.RandomAccess);
                    single.Seek(x.Offsets[i], SeekOrigin.Begin);
                    ReadFully(single, buf, len);
                }
                else
                {
                    // 2026-10-16 確かめで直した：計算（g49_run.py）は同じ名前のファイルを open("wb") でそのまま書く（途中保存から続けると重なりのコマを書き直す）。
                    // FileShare.Read だと、こちらが開いている 1 ms の間に計算が書こうとすると計算の側が止まるので、書き・消しを妨げない ReadWrite | Delete で開く
                    // （書きかけを読んだ時は、下の長さと FLIP3DStream のコマの番号・-f3dsha の SHA-256 で分かる）
                    using (var fs = new FileStream(x.Files[i], FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete, 1, FileOptions.SequentialScan))
                    {
                        if (fs.Length != len) throw new InvalidDataException("面の記録の長さが manifest と違う：" + x.Files[i] + " " + fs.Length + " != " + len);
                        ReadFully(fs, buf, len);
                    }
                }
                return len;
            }

            public void Dispose() { single?.Dispose(); single = null; }
        }
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

        // 全部の記録を読み解いて GPU に置く（12 s の窓の 96・288 コマ用。前と同じ読み方。長い記録は FLIP3DStream で続けて読む）
        public static FLIP3DClip Load(string dir)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var c = new FLIP3DClip();
            c.Manifest = FLIP3DManifest.Read(dir);
            var x = FLIP3DRecordIndex.Open(dir, c.Manifest);
            c.ClipBytes = x.TotalBytes;
            int n = x.Count;
            c.Meshes = new Mesh[n];
            c.Times = new double[n];
            c.SimFrames = new int[n];
            byte[] buf = null;
            ushort[] scratch = null;
            using (var rd = new FLIP3DRecordIndex.Reader(x))
            {
                for (int i = 0; i < n; i++)
                {
                    rd.Read(i, ref buf);
                    c.Meshes[i] = DecodeFrame(buf, 0, ref scratch, out c.Times[i], out c.SimFrames[i]);
                    c.Meshes[i].name = "FLIP3D_DA3_f" + c.SimFrames[i].ToString("D5");
                }
            }
            c.BedMesh = BuildBed(dir, c.Manifest);
            c.LoadSeconds = sw.Elapsed.TotalSeconds;
            return c;
        }

        public static FLIP3DRecordHeader ReadHeader(byte[] b, int o)
        {
            if (b[o] != (byte)'G' || Encoding.ASCII.GetString(b, o, 8) != "GW45SRF1") throw new InvalidDataException("GW45SRF1 でない");
            var h = new FLIP3DRecordHeader
            {
                headBytes = (int)BitConverter.ToUInt32(b, o + 12),
                t = BitConverter.ToDouble(b, o + 16),
                frame = BitConverter.ToInt32(b, o + 24),
                nv = (int)BitConverter.ToUInt32(b, o + 28),
                nt = (int)BitConverter.ToUInt32(b, o + 32),
                lo = new Vector3(BitConverter.ToSingle(b, o + 36), BitConverter.ToSingle(b, o + 40), BitConverter.ToSingle(b, o + 44)),
                hi = new Vector3(BitConverter.ToSingle(b, o + 48), BitConverter.ToSingle(b, o + 52), BitConverter.ToSingle(b, o + 56)),
            };
            return h;
        }

        // 1 コマを読み解き、渡した配列（大きさは nv・nv・3 nt 以上）の頭に書く。Mesh を作る時・続けて読む時（別のスレッド）・確かめの書き出しで同じ関数。
        // Unity の API は使わない（Vector3 の計算だけ）ので、主スレッドの外で呼んでよい。scratch は uint16 の読み場所（なければ作る）
        public static FLIP3DRecordHeader DecodeInto(byte[] b, int o, Vector3[] pos, Vector3[] nrm, int[] idx, ref ushort[] scratch)
        {
            var h = ReadHeader(b, o);
            int nv = h.nv, nt = h.nt;
            if (pos.Length < nv || nrm.Length < nv || idx.Length < 3 * nt) throw new ArgumentException("配列が小さい");
            if (scratch == null || scratch.Length < 3 * nv) scratch = new ushort[Math.Max(3 * nv, 4096)];
            var lo = h.lo;
            var span = (h.hi - h.lo) / 65535f;
            int p = o + h.headBytes;
            Buffer.BlockCopy(b, p, scratch, 0, 6 * nv);
            for (int k = 0, q = 0; k < nv; k++, q += 3)
                pos[k] = new Vector3(lo.x + scratch[q] * span.x, lo.y + scratch[q + 1] * span.y, lo.z + scratch[q + 2] * span.z);
            p += 6 * nv;
            Buffer.BlockCopy(b, p, scratch, 0, 4 * nv);
            for (int k = 0, q = 0; k < nv; k++, q += 2)
                nrm[k] = OctDecode(scratch[q], scratch[q + 1]);
            p += 4 * nv;
            p += 6 * nv;                                  // 速さ v（使わない）
            Buffer.BlockCopy(b, p, idx, 0, 12 * nt);
            // 座標は計画の（右手の）x・上・横をそのまま Unity の（左手の）x・y・z に置くので、見かけの回りが逆になる。
            // 三角形の 2 番目と 3 番目を入れ替えて、Unity の表（時計回り）にそろえる（点の位置と法線はそのまま）
            for (int k = 0, m = 3 * nt; k < m; k += 3) { int tmp = idx[k + 1]; idx[k + 1] = idx[k + 2]; idx[k + 2] = tmp; }
            return h;
        }

        // 1 コマを配列に読み解く（大きさちょうどの配列を作って DecodeInto を呼ぶ。確かめの書き出しで使う）
        public static void DecodeArrays(byte[] b, int o, out Vector3[] pos, out Vector3[] nrm, out int[] idx, out double t, out int frame, out Vector3 lo, out Vector3 hi)
        {
            var h0 = ReadHeader(b, o);
            pos = new Vector3[h0.nv];
            nrm = new Vector3[h0.nv];
            idx = new int[3 * h0.nt];
            ushort[] scratch = null;
            var h = DecodeInto(b, o, pos, nrm, idx, ref scratch);
            t = h.t; frame = h.frame; lo = h.lo; hi = h.hi;
        }

        static Mesh DecodeFrame(byte[] b, int o, ref ushort[] scratch, out double t, out int frame)
        {
            var h0 = ReadHeader(b, o);
            var pos = new Vector3[h0.nv];
            var nrm = new Vector3[h0.nv];
            var idx = new int[3 * h0.nt];
            var h = DecodeInto(b, o, pos, nrm, idx, ref scratch);
            t = h.t; frame = h.frame;
            var m = new Mesh { indexFormat = IndexFormat.UInt32 };
            m.vertices = pos;
            m.normals = nrm;
            m.SetTriangles(idx, 0, false);
            m.bounds = new Bounds((h.lo + h.hi) * 0.5f, h.hi - h.lo);
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
        public static Mesh BuildBed(string dir, FLIP3DManifest mf)
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
