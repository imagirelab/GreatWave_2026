using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design43;
using GreatWave.Design46;
using UnityEditor;
using UnityEngine;

namespace GreatWave.Design46.EditorTools
{
    // 設計46：形のハッシュ（Editor と Play の両方の検査で使う）。どれも「今、描かれる／読まれる」データそのものから取る。
    //   sheet_*：各シート（hero・near・far）の頂点を GPU で読み戻す（頂点シェーダーと同じ関数の DS27KeyposeCapture。描いた面そのもの）。xyz の float32 の SHA-256。
    //   white  ：主役波の白の頂点の旗（T_white ≤ 材質へ渡した τ。DS27 NPR White の頂点の比べと同じ float）。T_white は GPU のバッファから読む。
    //   claws  ：爪の結合メッシュの今の頂点。spray_*：飛沫の今の (x, y, z, 半径)。
    //   boat   ：船用水面データの格子（2 m おき 28 × 26 点）の交わりの数と高さ。
    //   events ：通過した出来事の id。
    public sealed class DS46Probe : IDisposable
    {
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        readonly ComputeShader cs;
        readonly int kern;
        readonly List<DS30SheetPlayer> sheets;
        readonly ComputeBuffer[] bufs;
        readonly Vector4[][] outv;
        readonly int[] cnt;
        readonly DS46ClockBus bus;
        float[] heroTWhite;
        readonly List<Vector3> grid = new List<Vector3>();

        public DS46Probe(DS46ClockBus bus)
        {
            this.bus = bus;
            cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
            if (cs == null) throw new InvalidOperationException("DS27KeyposeCapture.compute がありません。");
            kern = cs.FindKernel("DS27Capture");
            sheets = bus.playback.sheets.Where(s => s != null).ToList();
            bufs = new ComputeBuffer[sheets.Count]; outv = new Vector4[sheets.Count][]; cnt = new int[sheets.Count];
            for (int s = 0; s < sheets.Count; s++)
            {
                cnt[s] = sheets[s].PackageMeta.rows * sheets[s].PackageMeta.cols;
                bufs[s] = new ComputeBuffer(cnt[s] * 2, 16); outv[s] = new Vector4[cnt[s] * 2];
            }
            for (float x = -31f; x <= 23.0f + 1e-3f; x += 2f) for (float z = -48f; z <= 2.0f + 1e-3f; z += 2f) grid.Add(new Vector3(x, 0f, z));
        }

        public int GridCount => grid.Count;
        public IList<DS30SheetPlayer> Sheets => sheets;

        public float[] SheetXyz(int s)
        {
            sheets[s].BindCompute(cs, kern);
            cs.SetBuffer(kern, "_DS27Out", bufs[s]);
            cs.SetInt("_DS27Count", cnt[s]);
            cs.Dispatch(kern, (cnt[s] + 63) / 64, 1, 1);
            bufs[s].GetData(outv[s]);
            var f = new float[cnt[s] * 3];
            for (int i = 0; i < cnt[s]; i++) { var p = outv[s][2 * i]; f[3 * i] = p.x; f[3 * i + 1] = p.y; f[3 * i + 2] = p.z; }
            return f;
        }

        public string SheetHash(int s) => Sha(SheetXyz(s));

        public int HeroIndex => sheets.FindIndex(s => s.sheetName == "hero");

        public byte[] WhiteFlags(out int whiteCount)
        {
            var hero = sheets[HeroIndex];
            if (heroTWhite == null)
            {
                var fi = typeof(DS30SheetPlayer).GetField("whiteBuf", BindingFlags.NonPublic | BindingFlags.Instance);
                var gb = fi?.GetValue(hero) as GraphicsBuffer;
                if (gb == null) throw new InvalidOperationException("主役波の T_white のバッファがありません。");
                heroTWhite = new float[gb.count];
                gb.GetData(heroTWhite);
            }
            float tau = (float)hero.AppliedTau;
            if (bus.layers != null && !bus.layers.whiteBand) tau = DS34LayerSet.WhiteOffTau;
            var b = new byte[heroTWhite.Length];
            whiteCount = 0;
            for (int i = 0; i < b.Length; i++) if (heroTWhite[i] <= tau) { b[i] = 1; whiteCount++; }
            return b;
        }

        public float[] ClawXyz()
        {
            var v = bus.claws.Current;
            var f = new float[v.Length * 3];
            for (int i = 0; i < v.Length; i++) { f[3 * i] = v[i].x; f[3 * i + 1] = v[i].y; f[3 * i + 2] = v[i].z; }
            return f;
        }

        public float[] SprayXyzr()
        {
            var l = new List<float>();
            foreach (var s in bus.sprays) { if (s == null) continue; foreach (var p in s.Current) { l.Add(p.x); l.Add(p.y); l.Add(p.z); l.Add(p.w); } }
            return l.ToArray();
        }

        public float[] BoatGrid()
        {
            var hits = new List<float>(16);
            var f = new List<float>(grid.Count * 3);
            foreach (var p in grid)
            {
                int k = bus.boatWater.Hits(p, hits);
                f.Add(k); f.Add(k > 0 ? hits[0] : float.NaN); f.Add(k > 1 ? hits[k - 1] : float.NaN);
            }
            return f.ToArray();
        }

        /// <summary>今の形のハッシュ一式（キー → SHA-256）。</summary>
        public SortedDictionary<string, string> All(bool sheetsAll = true)
        {
            var d = new SortedDictionary<string, string>();
            for (int s = 0; s < sheets.Count; s++) if (sheetsAll || s == HeroIndex) d["sheet_" + sheets[s].sheetName] = SheetHash(s);
            d["white"] = Sha(WhiteFlags(out _));
            if (bus.claws != null) d["claws"] = Sha(ClawXyz());
            if (bus.sprays.Count > 0) d["spray"] = Sha(SprayXyzr());
            if (bus.boatWater != null) d["boat"] = Sha(BoatGrid());
            if (bus.events != null) d["events"] = Sha(Encoding.UTF8.GetBytes(bus.events.PassedAt(bus.clock.ExperienceSeconds)));
            return d;
        }

        public static string Sha(float[] f) { var b = new byte[f.Length * 4]; Buffer.BlockCopy(f, 0, b, 0, b.Length); return Sha(b); }
        public static string Sha(byte[] b) { using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant(); }

        public static float MaxAbsDiff(float[] a, float[] b)
        {
            if (a.Length != b.Length) return float.PositiveInfinity;
            float m = 0f;
            for (int i = 0; i < a.Length; i++) { float d = Math.Abs(a[i] - b[i]); if (float.IsNaN(d)) { if (!(float.IsNaN(a[i]) && float.IsNaN(b[i]))) return float.PositiveInfinity; } else if (d > m) m = d; }
            return m;
        }

        public static string J(SortedDictionary<string, string> d) => "{" + string.Join(",", d.Select(kv => "\"" + kv.Key + "\":\"" + kv.Value + "\"")) + "}";
        public static string F(double x) => double.IsNaN(x) ? "null" : x.ToString("R", CultureInfo.InvariantCulture);

        public void Dispose()
        {
            if (bufs != null) foreach (var b in bufs) b?.Release();
        }
    }
}
