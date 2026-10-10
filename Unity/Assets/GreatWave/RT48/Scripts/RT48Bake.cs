using System;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48（Q48 の案 1）：焼いた断面の曲線（計画 §2.4）を読む。書き手は Tools/GWWaveGen/rt48/u_bakeio.py（形の説明もそこ）。
    //   meta.json：下の RT48BakeMeta（平らな配列だけ）。pairs.bin：float32 LE [組][A,B][点][x,y]。loops.bin：float32 LE [点][x,y]。
    //   x は x_origin_m（527.0 m）からの距離、y は静かな水面からの高さ。コマ f の時刻は (f − 1) / fps。
    [Serializable]
    public class RT48BakeMeta
    {
        public string schema, source_id, label_ja, caption1_ja, caption3_ja, created_utc, tool, note_ja;
        public bool is_synthetic, interp_verified;
        public double x_origin_m, fps;
        public int n_points, frame_first, frame_count, pair_count, k_frame;
        public int[] pair_interp, pair_reason, pair_lm_crest, pair_lm_lip;
        public double[] crest_x_m, x_range_m, taper_m;
        public double onset_s, onset_x_m, contact_s, contact_x_m, side_end_s;
        public double[] seat_x_m, seat_end_s;
        public int[] loop_frame_first, loop_frame_count, loop_kind, loop_point_first, loop_point_count;
        public string[] files_name, files_sha256;
        public long[] files_bytes;
    }

    public sealed class RT48Bake
    {
        public const string Schema = "GreatWave.RT48.bake/1";
        public string Dir { get; private set; }
        public RT48BakeMeta Meta { get; private set; }
        public float[] Pairs { get; private set; }      // [P][2][N][2]
        public float[] LoopPts { get; private set; }    // [M][2]
        public bool ShaChecked { get; private set; }
        public bool ShaOk { get; private set; }
        public string ShaNote { get; private set; } = "";
        public double LoadSeconds { get; private set; }

        public int N => Meta.n_points;
        public int P => Meta.pair_count;
        public int F => Meta.frame_count;
        public int OffsetA(int pair) => pair * 2 * N;          // float2 の添字
        public int OffsetB(int pair) => pair * 2 * N + N;
        public double FrameTime(int k) => (Meta.frame_first + k - 1) / Meta.fps;   // k は 0 始まりのコマの番号
        public double[] TaperStored => new[] { Meta.taper_m[0] - Meta.x_origin_m, Meta.taper_m[1] - Meta.x_origin_m, Meta.taper_m[2] - Meta.x_origin_m, Meta.taper_m[3] - Meta.x_origin_m };

        // meta.json（u_bakeio.py の形）か manifest.json（r_bake.py の形、Unity/Build/RT48/data/<元>/）の、どちらかと pairs.bin があるフォルダー
        public static bool IsBakeDir(string dir) => (File.Exists(Path.Combine(dir, "meta.json")) || File.Exists(Path.Combine(dir, "manifest.json"))) && File.Exists(Path.Combine(dir, "pairs.bin"));

        public string MetaFormat { get; private set; } = "";

        public static RT48Bake Load(string dir, bool verifySha)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var b = new RT48Bake { Dir = Path.GetFullPath(dir) };
            if (File.Exists(Path.Combine(dir, "meta.json")))
            {
                b.Meta = JsonUtility.FromJson<RT48BakeMeta>(File.ReadAllText(Path.Combine(dir, "meta.json"), System.Text.Encoding.UTF8));
                b.MetaFormat = "meta.json（u_bakeio.py）";
            }
            else
            {
                b.Meta = FromManifest(dir);
                b.MetaFormat = "manifest.json（r_bake.py）";
            }
            var m = b.Meta;
            if (m == null || m.schema != Schema) throw new InvalidDataException("RT48：meta.json の schema が違います：" + (m == null ? "null" : m.schema) + "（" + dir + "）");
            if (m.pair_count != m.frame_count - 1) throw new InvalidDataException("RT48：pair_count ≠ frame_count − 1");
            if (m.pair_interp == null || m.pair_interp.Length != m.pair_count) throw new InvalidDataException("RT48：pair_interp の長さが違います");
            if (m.taper_m == null || m.taper_m.Length != 4) throw new InvalidDataException("RT48：taper_m は 4 つの値");
            if (m.n_points < 4) throw new InvalidDataException("RT48：n_points が小さすぎます");
            var pairBytes = File.ReadAllBytes(Path.Combine(dir, "pairs.bin"));
            long expect = (long)m.pair_count * 2 * m.n_points * 2 * 4;
            if (pairBytes.LongLength != expect) throw new InvalidDataException("RT48：pairs.bin の大きさが違います：" + pairBytes.LongLength + " ≠ " + expect);
            var loopPath = Path.Combine(dir, "loops.bin");
            var loopBytes = File.Exists(loopPath) ? File.ReadAllBytes(loopPath) : new byte[0];
            if (!BitConverter.IsLittleEndian) throw new NotSupportedException("RT48：ビッグエンディアンの機械は扱いません");
            b.Pairs = new float[pairBytes.Length / 4];
            Buffer.BlockCopy(pairBytes, 0, b.Pairs, 0, pairBytes.Length);
            b.LoopPts = new float[loopBytes.Length / 4];
            Buffer.BlockCopy(loopBytes, 0, b.LoopPts, 0, loopBytes.Length);
            if (verifySha && m.files_name != null && m.files_sha256 != null)
            {
                b.ShaChecked = true; b.ShaOk = true;
                for (int i = 0; i < m.files_name.Length; i++)
                {
                    byte[] bytes = m.files_name[i] == "pairs.bin" ? pairBytes : m.files_name[i] == "loops.bin" ? loopBytes : null;
                    if (bytes == null) continue;
                    var h = Sha256(bytes);
                    bool ok = string.Equals(h, m.files_sha256[i], StringComparison.OrdinalIgnoreCase);
                    b.ShaOk &= ok;
                    b.ShaNote += m.files_name[i] + (ok ? " 一致 " : " 不一致 ") + h.Substring(0, 12) + "… ";
                }
            }
            b.LoadSeconds = sw.Elapsed.TotalSeconds;
            return b;
        }

        // r_bake.py の manifest.json（Unity/Build/RT48/data/<元>/）を、この読み手の形へ移す。親の data/manifest.json があれば字 1・3 をそこから取る。
        //   pairs[i].interp・reason（interp / after_K / C4_fail / self_x）・marks、playback.K、events.onset_t・first_contact_t、time、coords.origin_x_rel、
        //   x_fade.ranges_x_rel、boat[座席].seat_x_rel・clip_end_t、loops_index[コマ].loops = [始め, 数, 相（−1 水・+1 空気・0 決まらない）, 面積]、files。
        public static RT48BakeMeta FromManifest(string dir)
        {
            var m = RT48Json.O(RT48Json.Parse(File.ReadAllText(Path.Combine(dir, "manifest.json"), System.Text.Encoding.UTF8)));
            var r = new RT48BakeMeta { schema = Schema };
            r.source_id = RT48Json.S(RT48Json.Get(m, "source"));
            r.label_ja = RT48Json.S(RT48Json.Get(m, "label"));
            r.tool = RT48Json.S(RT48Json.Get(m, "tool"));
            r.created_utc = RT48Json.S(RT48Json.Get(m, "date"));
            r.note_ja = "manifest.json（" + RT48Json.S(RT48Json.Get(m, "format")) + "）から読んだ";
            r.is_synthetic = false;
            r.x_origin_m = RT48Json.D(RT48Json.Get(RT48Json.GetO(m, "coords"), "origin_x_rel"));
            var time = RT48Json.GetO(m, "time");
            r.fps = RT48Json.D(RT48Json.Get(time, "fps"));
            r.frame_first = RT48Json.I(RT48Json.Get(time, "first_frame"));
            r.frame_count = RT48Json.I(RT48Json.Get(time, "n_frames"));
            r.side_end_s = RT48Json.D(RT48Json.Get(time, "t_last"));
            r.n_points = RT48Json.I(RT48Json.Get(m, "n_points"));
            var pairs = RT48Json.A(RT48Json.Get(m, "pairs"));
            int P = pairs.Count;
            r.pair_count = P;
            r.pair_interp = new int[P]; r.pair_reason = new int[P]; r.pair_lm_crest = new int[P]; r.pair_lm_lip = new int[P];
            for (int p = 0; p < P; p++)
            {
                var q = RT48Json.O(pairs[p]);
                if (RT48Json.I(RT48Json.Get(q, "p")) != p || RT48Json.I(RT48Json.Get(q, "k")) != r.frame_first + p) throw new InvalidDataException("RT48：manifest の pairs の並びが違います（" + p + "）");
                bool ip = RT48Json.B(RT48Json.Get(q, "interp"));
                string why = RT48Json.S(RT48Json.Get(q, "reason"));
                r.pair_interp[p] = ip ? 1 : 0;
                r.pair_reason[p] = ip ? 0 : why == "after_K" ? 1 : why == "C4_fail" ? 2 : why.StartsWith("self") ? 3 : 4;
                var marks = RT48Json.Get(q, "marks") as System.Collections.Generic.List<object>;
                r.pair_lm_crest[p] = marks != null && marks.Count > 0 ? RT48Json.I(marks[0]) : -1;
                r.pair_lm_lip[p] = marks != null && marks.Count > 1 ? RT48Json.I(marks[1]) : -1;
            }
            r.k_frame = RT48Json.I(RT48Json.Get(RT48Json.GetO(m, "playback"), "K"));
            var ev = RT48Json.GetO(m, "events");
            r.onset_s = RT48Json.D(RT48Json.Get(ev, "onset_t"));
            r.contact_s = RT48Json.D(RT48Json.Get(ev, "first_contact_t"));
            var frames = RT48Json.A(RT48Json.Get(m, "frames"));
            r.crest_x_m = new double[frames.Count];
            for (int k = 0; k < frames.Count; k++) r.crest_x_m[k] = RT48Json.D(RT48Json.Get(RT48Json.O(frames[k]), "crest_x"));
            var fades = RT48Json.A(RT48Json.Get(RT48Json.GetO(m, "x_fade"), "ranges_x_rel"));
            var f0 = RT48Json.A(fades[0]); var f1 = RT48Json.A(fades[1]);
            r.taper_m = new[] { RT48Json.D(f0[0]), RT48Json.D(f0[1]), RT48Json.D(f1[0]), RT48Json.D(f1[1]) };
            r.x_range_m = new[] { r.taper_m[0], r.taper_m[3] };
            var boat = RT48Json.GetO(m, "boat");
            var seats = new System.Collections.Generic.List<double>(); var ends = new System.Collections.Generic.List<double>();
            if (boat != null)
                foreach (var kv in boat)
                {
                    var bo = kv.Value as System.Collections.Generic.Dictionary<string, object>;
                    if (bo == null || RT48Json.Get(bo, "clip_end_t") == null) continue;
                    seats.Add(RT48Json.D(RT48Json.Get(bo, "seat_x_rel"))); ends.Add(RT48Json.D(RT48Json.Get(bo, "clip_end_t")));
                }
            r.seat_x_m = seats.ToArray(); r.seat_end_s = ends.ToArray();
            var li = RT48Json.A(RT48Json.Get(m, "loops_index"));
            if (li.Count != r.frame_count) throw new InvalidDataException("RT48：loops_index の数がコマの数と違います");
            r.loop_frame_first = new int[r.frame_count]; r.loop_frame_count = new int[r.frame_count];
            var kinds = new System.Collections.Generic.List<int>(); var pf = new System.Collections.Generic.List<int>(); var pc = new System.Collections.Generic.List<int>();
            for (int k = 0; k < li.Count; k++)
            {
                var e = RT48Json.O(li[k]);
                if (RT48Json.I(RT48Json.Get(e, "frame")) != r.frame_first + k) throw new InvalidDataException("RT48：loops_index の並びが違います（" + k + "）");
                var ls = RT48Json.A(RT48Json.Get(e, "loops"));
                r.loop_frame_first[k] = kinds.Count; r.loop_frame_count[k] = ls.Count;
                foreach (var lo in ls)
                {
                    var a = RT48Json.A(lo);
                    pf.Add(RT48Json.I(a[0])); pc.Add(RT48Json.I(a[1]));
                    int phase = RT48Json.I(a[2]);
                    kinds.Add(phase < 0 ? 0 : phase > 0 ? 1 : 2);   // 0 水、1 空気、2 決まらない（描かない）
                }
            }
            r.loop_kind = kinds.ToArray(); r.loop_point_first = pf.ToArray(); r.loop_point_count = pc.ToArray();
            var files = RT48Json.GetO(m, "files");
            var fn = new System.Collections.Generic.List<string>(); var fs = new System.Collections.Generic.List<string>(); var fb = new System.Collections.Generic.List<long>();
            foreach (var key in new[] { "pairs", "loops" })
            {
                var fo = RT48Json.GetO(files, key);
                if (fo == null) continue;
                fn.Add(RT48Json.S(RT48Json.Get(fo, "name"))); fs.Add(RT48Json.S(RT48Json.Get(fo, "sha256"))); fb.Add((long)RT48Json.D(RT48Json.Get(fo, "bytes")));
            }
            r.files_name = fn.ToArray(); r.files_sha256 = fs.ToArray(); r.files_bytes = fb.ToArray();
            var checks = RT48Json.GetO(m, "checks");
            var c3 = RT48Json.GetO(checks, "C3"); var c4 = RT48Json.GetO(checks, "C4");
            r.interp_verified = c3 != null && c4 != null && RT48Json.B(RT48Json.Get(c3, "ok")) && RT48Json.I(RT48Json.Get(c4, "n_fail")) == 0;
            // 親の data/manifest.json（r_index.py）の字
            var full = Path.GetFullPath(dir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            var parent = Path.Combine(Path.GetDirectoryName(full), "manifest.json");
            if (File.Exists(parent))
            {
                try
                {
                    var pm = RT48Json.O(RT48Json.Parse(File.ReadAllText(parent, System.Text.Encoding.UTF8)));
                    var caps = RT48Json.GetO(pm, "captions");
                    r.caption1_ja = RT48Json.S(RT48Json.Get(caps, "1"));
                    var src = RT48Json.GetO(RT48Json.GetO(pm, "sources"), r.source_id);
                    r.caption3_ja = RT48Json.S(RT48Json.Get(src, "caption"));
                }
                catch (Exception e) { r.note_ja += "。親の manifest を読めない：" + e.Message; }
            }
            return r;
        }

        public static string Sha256(byte[] bytes)
        {
            using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }

        // ---------------------------------------------------------------- CPU（float64）の曲線
        // 組 pair の A と B を割合 alpha で混ぜた生の曲線（x 保存、y）。xy は 2N。
        public void FillBlended(int pair, double alpha, double[] xy)
        {
            int a = OffsetA(pair) * 2, bb = OffsetB(pair) * 2, n2 = N * 2;
            for (int i = 0; i < n2; i++)
            {
                double va = Pairs[a + i], vb = Pairs[bb + i];
                xy[i] = va + (vb - va) * alpha;
            }
        }

        // コマ k（0 始まり）の曲線：組 k の A、最後のコマは最後の組の B。
        public void FillFrame(int k, double[] xy)
        {
            int off = (k < F - 1 ? OffsetA(k) : OffsetB(P - 1)) * 2, n2 = N * 2;
            for (int i = 0; i < n2; i++) xy[i] = Pairs[off + i];
        }

        public int LoopCount(int k) => Meta.loop_frame_count != null && k >= 0 && k < Meta.loop_frame_count.Length ? Meta.loop_frame_count[k] : 0;
        public int LoopIndex(int k, int j) => Meta.loop_frame_first[k] + j;
    }

    // 表示の形（x の両端の下ろし）と、一番上の水面・船の上下と縦揺れ。式は u_bakeio.py と同じ。
    public static class RT48BoatMotion
    {
        public static readonly double[] HullDx = { -6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0 };

        public static double TaperWeight(double xs, double[] t)
        {
            if (xs <= t[0] || xs >= t[3]) return 0.0;
            if (xs > t[0] && xs < t[1]) return 0.5 - 0.5 * Math.Cos(Math.PI * (xs - t[0]) / (t[1] - t[0]));
            if (xs > t[2] && xs < t[3]) return 0.5 + 0.5 * Math.Cos(Math.PI * (xs - t[2]) / (t[3] - t[2]));
            return 1.0;
        }

        // 生の曲線 xy（2N）に重みを掛けた表示の y を disp へ（x はそのまま）。
        public static void ToDisplayed(double[] xy, int n, double[] taper, double[] disp)
        {
            for (int i = 0; i < n; i++) { double x = xy[2 * i]; disp[2 * i] = x; disp[2 * i + 1] = xy[2 * i + 1] * TaperWeight(x, taper); }
        }

        // 鉛直の線 x = xq と折れ線の交わりのうち最も高い y（端を含む。鉛直の線分は両端の高い方）。交わらなければ NaN。
        public static double TopSurface(double[] c, int n, double xq)
        {
            double best = double.NegativeInfinity; bool any = false;
            for (int i = 0; i < n - 1; i++)
            {
                double x0 = c[2 * i], x1 = c[2 * i + 2];
                double lo = x0 < x1 ? x0 : x1, hi = x0 < x1 ? x1 : x0;
                if (xq < lo || xq > hi) continue;
                double y0 = c[2 * i + 1], y1 = c[2 * i + 3], dx = x1 - x0, y;
                if (dx != 0) { double s = (xq - x0) / dx; y = y0 + s * (y1 - y0); }
                else y = y0 > y1 ? y0 : y1;
                if (!any || y > best) { best = y; any = true; }
            }
            return any ? best : double.NaN;
        }

        public struct Pose { public double heave, pitchDeg, slope; public bool ok; }

        public static Pose Fit(double[] ys)
        {
            double sum = 0; bool ok = true;
            for (int j = 0; j < ys.Length; j++) { sum += ys[j]; ok &= !double.IsNaN(ys[j]); }
            double h = sum / ys.Length, num = 0, den = 0;
            for (int j = 0; j < ys.Length; j++) { num += HullDx[j] * (ys[j] - h); den += HullDx[j] * HullDx[j]; }
            double slope = num / den;
            return new Pose { heave = h, slope = slope, pitchDeg = Math.Atan(slope) * 180.0 / Math.PI, ok = ok };
        }

        // 表示の曲線 disp（2N）と座席の x（保存の座標）から船の姿勢。ys は 9 点の高さの置き場。
        public static Pose FromDisplayed(double[] disp, int n, double seatXs, double[] ys)
        {
            for (int j = 0; j < HullDx.Length; j++) ys[j] = TopSurface(disp, n, seatXs + HullDx[j]);
            return Fit(ys);
        }
    }
}
