using System;
using System.IO;
using System.Security.Cryptography;
using GreatWave.ArtFirst;
using UnityEngine;

namespace GreatWave.Design27
{
    // 設計27：単発砕波（形成から t* まで）の DS27 keypose を GPU で再生する。美術優先30 の AF30KeyposeWave と AF31WhiteField を写して、
    // 次を変えた（美術優先の番号のファイルは変えない）：
    //  1) 時刻は物理の時刻 τ（t* = 0）。採取は ApplyTau で τ を直接与える。GWClock から τ(t) の表（DS27TimeWarp）で読む経路は
    //     driveFromClock で残す（単発の再生は設計30）。
    //  2) 節点 knot_tau は不等間隔でよい。補間は節点の間の 3 次 Hermite（傾きは中心差分、端は片側。AF30KeyposeWave.Weights と同じ式）。
    //  3) keypose は波の枠の局所座標。ワールド = O(τ) + 局所。O(τ) は密な標本（240 Hz 以上）の線形補間を CPU で求め、大域の値で渡す。
    //  4) 法線のファイルはない。外殻線の頂点シェーダーが、補間した位置から K* の格子の 6 つの三角形の面の法線の和を求める
    //     （美術優先30 の vertex_normals と同じ定義）。
    //  5) GPU の容量を減らすため、RGBA16 の A（常に 65535）を捨て、頂点ごとに 16 bit × 3（6 バイト）を StructuredBuffer<uint> に詰める
    //     （Texture2DArray の RGBA64 の 3/4）。値は同じ UNORM の 16 bit（位置 = bbox_min + q/65535 × bbox_size）。
    //  6) T_white は τ の秒（+1e9 = t* までに白にならない）。StructuredBuffer<float> で渡す。
    // パッケージの書式は Tools/GWWaveGen/ds27/ds27_player_ref.py の冒頭（numpy の参照の実装）と同じ。
    // メッシュ（固定位相の格子、添字・UV・UV2）は同じ GameObject の AF26KStarMesh が K* の .gwb から読み、UV3 は AF28NprWave が付ける。
    // 頂点バッファは K* のまま変えない（位置はシェーダーがバッファから読む）。外接箱は、局所の外接箱と枠の原点の動く範囲の和にする。
    [RequireComponent(typeof(AF26KStarMesh))]
    [DefaultExecutionOrder(100)]
    public class DS27KeyposePlayer : MonoBehaviour
    {
        [Tooltip("DS27 パッケージのフォルダー（Unity プロジェクトからの相対パスか絶対パス。既定は Git 対象外の /Unity/Build/Design/27/art_on）")]
        public string packageDir = "Build/Design/27/art_on";
        [Tooltip("読み込むときに位置と T_white の SHA-256 を JSON の値と照合する")]
        public bool verifySha256 = true;
        [Tooltip("白の時間場を使う（切ると終態の色：終態の白が最初から見える）")]
        public bool whiteEnabled = true;
        [Header("GWClock からの再生（設計30 で使う。設計27 の採取は ApplyTau で τ を直接与える）")]
        public bool driveFromClock = false;
        [Tooltip("時刻を読む時計（空なら GWClock.Active）")]
        public GWClock clock;
        [Tooltip("τ(t) の表（Unity プロジェクトからの相対パスか絶対パス）")]
        public string timewarpPath = "../Tools/GWWaveGen/ds27/timewarp_default.json";

        public const int Rows = 240, Cols = 400;
        public const double NeverWhite = 1.0e8;   // これ以上の T_white は「t* までに白にならない」（約束は +1e9）

        public class Meta
        {
            public int layers, rows, cols, preWhiteIndex = 2;
            public double[] bboxMin, bboxSize, knotTau, frameTau;
            public double[][] frameOrigin;
            public string posSha256, twhiteFile, twhiteSha256, dir, jsonSha256;
            public bool hasPreWhiteIndex;
        }

        Meta meta;
        GraphicsBuffer posBuf, whiteBuf;
        DS27TimeWarp warp;
        MaterialPropertyBlock block;

        public Meta PackageMeta => meta;
        public GraphicsBuffer PositionBuffer => posBuf;
        public GraphicsBuffer WhiteBuffer => whiteBuf;
        public int[] Slices { get; } = new int[4];
        public float[] WeightsNow { get; } = new float[4];
        public double AppliedTau { get; private set; } = double.NaN;
        public Vector3 AppliedOrigin { get; private set; }
        public long PositionGpuBytes => posBuf == null ? 0 : (long)posBuf.count * posBuf.stride;
        public long WhiteGpuBytes => whiteBuf == null ? 0 : (long)whiteBuf.count * whiteBuf.stride;
        public long AlphaNot65535 { get; private set; }
        public double WhiteFiniteMin { get; private set; } = double.NaN;
        public double WhiteFiniteMax { get; private set; } = double.NaN;
        public int WhiteNeverCount { get; private set; }
        public double FrameMinRateHz { get; private set; }
        public int ClampedKnotCount { get; private set; }
        public int ClampedFrameCount { get; private set; }
        public Bounds WorldBounds { get; private set; }
        public float LoadSeconds { get; private set; }

        public static readonly int PosId = Shader.PropertyToID("_DS27Pos"), WhiteId = Shader.PropertyToID("_DS27White"),
            BBoxMinId = Shader.PropertyToID("_DS27BBoxMin"), BBoxSizeId = Shader.PropertyToID("_DS27BBoxSize"),
            SlicesId = Shader.PropertyToID("_DS27Slices"), WeightsId = Shader.PropertyToID("_DS27Weights"),
            OriginId = Shader.PropertyToID("_DS27Origin"), GridId = Shader.PropertyToID("_DS27Grid"),
            TauId = Shader.PropertyToID("_DS27Tau"), EnabledId = Shader.PropertyToID("_DS27Enabled"),
            WhiteEnabledId = Shader.PropertyToID("_DS27WhiteEnabled"), DebugId = Shader.PropertyToID("_DS27DebugMode");

        // 設計29修正01：精度の層（パッケージの ds27_pos_lo_rgba8.bin、拡張 pos_lo_rgba8/1）を読むシェーダーの変種の大域キーワードと、そのバッファの名前
        // （DS27KeyposeCore.cginc）。この再生器（設計27）は精度の層を読まない（16 bit だけで、設計27・28 と同じ）。読むのは設計29 の DS29KeyposePlayer。
        // 同じ処理の中で DS29KeyposePlayer がキーワードを入れた後でも元の変種で描くよう、この再生器は大域の値を渡すたびにキーワードを切る。
        public const string PosLoKeyword = "DS27_POS_LO";
        public static readonly int PosLoId = Shader.PropertyToID("_DS27PosLo");

        public string FullDir => Path.GetFullPath(packageDir);

        public static Meta ReadMeta(string dir)
        {
            var jp = Path.Combine(Path.GetFullPath(dir), "ds27_keypose.json");
            var text = File.ReadAllText(jp);
            var r = DS27Json.AsObj(DS27Json.Parse(text), "ds27_keypose.json");
            var m = new Meta
            {
                dir = Path.GetFullPath(dir),
                layers = (int)DS27Json.Num(r, "layers"), rows = (int)DS27Json.Num(r, "rows"), cols = (int)DS27Json.Num(r, "cols"),
                bboxMin = DS27Json.Nums(DS27Json.Get(r, "bbox_min"), "bbox_min"), bboxSize = DS27Json.Nums(DS27Json.Get(r, "bbox_size"), "bbox_size"),
                knotTau = DS27Json.Nums(DS27Json.Get(r, "knot_tau"), "knot_tau"),
                posSha256 = DS27Json.Text(r, "pos_sha256"), twhiteFile = DS27Json.Text(r, "twhite_file"), twhiteSha256 = DS27Json.Text(r, "twhite_sha256"),
                jsonSha256 = Sha256(File.ReadAllBytes(jp))
            };
            var fr = DS27Json.AsObj(DS27Json.Get(r, "frame"), "frame");
            m.frameTau = DS27Json.Nums(DS27Json.Get(fr, "tau"), "frame.tau");
            m.frameOrigin = DS27Json.Nums2(DS27Json.Get(fr, "origin"), "frame.origin");
            if (DS27Json.Has(r, "pre_white_index")) { m.preWhiteIndex = (int)DS27Json.Num(r, "pre_white_index"); m.hasPreWhiteIndex = true; }
            if (m.rows != Rows || m.cols != Cols) throw new InvalidDataException("DS27 の格子は 240 行 × 400 列のはずです: " + m.rows + " × " + m.cols);
            if (m.layers < 1 || m.knotTau.Length != m.layers) throw new InvalidDataException("knot_tau の長さが層の数と合いません。");
            for (int i = 1; i < m.layers; i++) if (!(m.knotTau[i] > m.knotTau[i - 1])) throw new InvalidDataException("knot_tau が狭義単調増加でありません。");
            if (m.knotTau[m.layers - 1] != 0.0) throw new InvalidDataException("knot_tau の最後は 0.0（t*）のはずです: " + m.knotTau[m.layers - 1]);
            if (m.bboxMin.Length != 3 || m.bboxSize.Length != 3) throw new InvalidDataException("bbox_min と bbox_size は 3 成分のはずです。");
            if (m.frameTau.Length < 2 || m.frameOrigin.Length != m.frameTau.Length) throw new InvalidDataException("frame の tau と origin の長さが合いません。");
            for (int i = 0; i < m.frameOrigin.Length; i++)
            {
                if (m.frameOrigin[i].Length != 3) throw new InvalidDataException("frame.origin の要素は 3 成分のはずです。");
                if (i > 0 && !(m.frameTau[i] > m.frameTau[i - 1])) throw new InvalidDataException("frame.tau が狭義単調増加でありません。");
            }
            return m;
        }

        public void EnsureLoaded()
        {
            if (meta != null && posBuf != null) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var m = ReadMeta(packageDir);
            var km = GetComponent<AF26KStarMesh>();
            var mesh = km.EnsureLoaded();
            int n = m.rows * m.cols;
            if (mesh.vertexCount != n || km.nu != m.cols || km.nv != m.rows)
                throw new InvalidDataException("DS27 の格子と K* のメッシュが合いません: " + mesh.vertexCount);

            // 位置：層ごとに読み、A を捨てて 16 bit × 3 を uint に 2 つずつ詰める（頂点 v・成分 k の 16 bit の番号 = (層 × N + v) × 3 + k）
            string pp = Path.Combine(m.dir, "ds27_pos_rgba16.bin");
            long layerBytes = (long)n * 8;
            var fi = new FileInfo(pp);
            if (fi.Length != layerBytes * m.layers) throw new InvalidDataException("ds27_pos_rgba16.bin の大きさが層 × 行 × 列 × 8 と合いません: " + fi.Length);
            int wordsPerLayer = n * 3 / 2;
            ReleaseBuffers();
            posBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, wordsPerLayer * m.layers, 4) { name = "DS27 keypose 位置（16 bit × 3）" };
            var raw = new byte[layerBytes];
            var us = new ushort[n * 4];
            var packedUs = new ushort[n * 3];
            var packed = new uint[wordsPerLayer];
            long alphaBad = 0;
            using (var sha = SHA256.Create())
            using (var fs = new FileStream(pp, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
            {
                for (int l = 0; l < m.layers; l++)
                {
                    int got = 0;
                    while (got < raw.Length)
                    {
                        int k = fs.Read(raw, got, raw.Length - got);
                        if (k <= 0) throw new EndOfStreamException("ds27_pos_rgba16.bin が途中で終わっています。");
                        got += k;
                    }
                    if (verifySha256) sha.TransformBlock(raw, 0, raw.Length, null, 0);
                    Buffer.BlockCopy(raw, 0, us, 0, raw.Length);
                    for (int v = 0; v < n; v++)
                    {
                        packedUs[3 * v] = us[4 * v];
                        packedUs[3 * v + 1] = us[4 * v + 1];
                        packedUs[3 * v + 2] = us[4 * v + 2];
                        if (us[4 * v + 3] != 65535) alphaBad++;
                    }
                    Buffer.BlockCopy(packedUs, 0, packed, 0, packedUs.Length * 2);
                    posBuf.SetData(packed, 0, l * wordsPerLayer, wordsPerLayer);
                }
                if (verifySha256)
                {
                    sha.TransformFinalBlock(new byte[0], 0, 0);
                    var h = BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
                    if (h != m.posSha256) { ReleaseBuffers(); throw new InvalidDataException("ds27_pos_rgba16.bin の SHA-256 が JSON と違います: " + h); }
                }
            }
            AlphaNot65535 = alphaBad;

            // T_white（τ の秒、R32F、行 × 列）
            var tb = File.ReadAllBytes(Path.Combine(m.dir, m.twhiteFile));
            if (tb.Length != n * 4) { ReleaseBuffers(); throw new InvalidDataException("T_white の大きさが行 × 列 × 4 と合いません: " + tb.Length); }
            if (verifySha256)
            {
                var h = Sha256(tb);
                if (h != m.twhiteSha256) { ReleaseBuffers(); throw new InvalidDataException("T_white の SHA-256 が JSON と違います: " + h); }
            }
            var tw = new float[n];
            Buffer.BlockCopy(tb, 0, tw, 0, tb.Length);
            double lo = double.MaxValue, hi = double.MinValue;
            int never = 0;
            foreach (var x in tw)
            {
                if (x >= NeverWhite) { never++; continue; }
                lo = Math.Min(lo, x); hi = Math.Max(hi, x);
            }
            WhiteFiniteMin = never == n ? double.NaN : lo;
            WhiteFiniteMax = never == n ? double.NaN : hi;
            WhiteNeverCount = never;
            whiteBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n, 4) { name = "DS27 T_white（τ）" };
            whiteBuf.SetData(tw);

            double maxDt = 0;
            for (int i = 1; i < m.frameTau.Length; i++) maxDt = Math.Max(maxDt, m.frameTau[i] - m.frameTau[i - 1]);
            FrameMinRateHz = 1.0 / maxDt;

            // 外接箱：局所の外接箱 ＋ 枠の原点の動く範囲 ＋ 外殻線の押し出し（最大 0.3 m）の余白
            var bmin = new Vector3((float)m.bboxMin[0], (float)m.bboxMin[1], (float)m.bboxMin[2]);
            var bsz = new Vector3((float)m.bboxSize[0], (float)m.bboxSize[1], (float)m.bboxSize[2]);
            Vector3 omin = Vector3.positiveInfinity, omax = Vector3.negativeInfinity;
            foreach (var o in m.frameOrigin)
            {
                var v3 = new Vector3((float)o[0], (float)o[1], (float)o[2]);
                omin = Vector3.Min(omin, v3); omax = Vector3.Max(omax, v3);
            }
            var wb = new Bounds();
            wb.SetMinMax(bmin + omin - Vector3.one * 0.5f, bmin + bsz + omax + Vector3.one * 0.5f);
            mesh.bounds = wb;
            WorldBounds = wb;

            meta = m;
            Shader.SetGlobalBuffer(PosId, posBuf);
            Shader.SetGlobalBuffer(WhiteId, whiteBuf);
            Shader.DisableKeyword(PosLoKeyword);
            Shader.SetGlobalVector(BBoxMinId, bmin);
            Shader.SetGlobalVector(BBoxSizeId, bsz);
            Shader.SetGlobalVector(GridId, new Vector4(m.cols, m.rows, n, 0));
            Shader.SetGlobalFloat(EnabledId, 1f);
            Shader.SetGlobalFloat(WhiteEnabledId, whiteEnabled ? 1f : 0f);
            Shader.SetGlobalFloat(DebugId, 0f);
            ApplyPreWhite();
            LoadSeconds = (float)sw.Elapsed.TotalSeconds;
            ApplyTau(0.0);
        }

        // 白の前の色区（パッケージに pre_white_index があればその値、なければマテリアルの値のまま）を、同じ GameObject と子の Renderer へ
        // MaterialPropertyBlock で渡す（AF28NprWave が同じ block に _SdfTex を入れているので、読み足して書き戻す）。
        void ApplyPreWhite()
        {
            if (meta == null || !meta.hasPreWhiteIndex) return;
            var r = GetComponent<Renderer>();
            if (r == null) return;
            if (block == null) block = new MaterialPropertyBlock();
            r.GetPropertyBlock(block);
            block.SetFloat("_PreWhiteClass", meta.preWhiteIndex);
            r.SetPropertyBlock(block);
        }

        /// <summary>τ の補間に使う 4 つの層と重み（AF30KeyposeWave.Weights・ds27_player_ref.hermite_weights と同じ式）。範囲の外は端の層。</summary>
        public static bool Weights(double[] tk, double t, int[] idx, float[] w)
        {
            int n = tk.Length;
            if (n == 1 || t <= tk[0]) { idx[0] = idx[1] = idx[2] = idx[3] = 0; w[0] = 0; w[1] = 1; w[2] = 0; w[3] = 0; return n > 1 && t < tk[0]; }
            if (t >= tk[n - 1]) { idx[0] = idx[1] = idx[2] = idx[3] = n - 1; w[0] = 0; w[1] = 1; w[2] = 0; w[3] = 0; return t > tk[n - 1]; }
            int i1 = Array.BinarySearch(tk, t);
            if (i1 < 0) i1 = ~i1 - 1;
            if (i1 > n - 2) i1 = n - 2;
            int i2 = i1 + 1, i0 = Math.Max(i1 - 1, 0), i3 = Math.Min(i2 + 1, n - 1);
            double t1 = tk[i1], t2 = tk[i2], D = t2 - t1, s = (t - t1) / D;
            double h00 = 2 * s * s * s - 3 * s * s + 1, h10 = s * s * s - 2 * s * s + s, h01 = -2 * s * s * s + 3 * s * s, h11 = s * s * s - s * s;
            double w0 = 0, w1 = h00, w2 = h01, w3 = 0;
            if (i0 == i1) { w2 += h10; w1 -= h10; }
            else { double f = h10 * D / (t2 - tk[i0]); w2 += f; w0 -= f; }
            if (i3 == i2) { w2 += h11; w1 -= h11; }
            else { double f = h11 * D / (tk[i3] - t1); w3 += f; w1 -= f; }
            idx[0] = i0; idx[1] = i1; idx[2] = i2; idx[3] = i3;
            w[0] = (float)w0; w[1] = (float)w1; w[2] = (float)w2; w[3] = (float)w3;
            return false;
        }

        /// <summary>波の枠の原点 O(τ)（密な標本の線形補間。範囲の外は端の標本）。clamped は範囲の外だったか。</summary>
        public Vector3 OriginAt(double tau, out bool clamped)
        {
            EnsureLoaded();
            var ft = meta.frameTau;
            var fo = meta.frameOrigin;
            int n = ft.Length;
            clamped = tau < ft[0] || tau > ft[n - 1];
            double[] o;
            if (tau <= ft[0]) o = fo[0];
            else if (tau >= ft[n - 1]) o = fo[n - 1];
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

        public Vector3 OriginAt(double tau) => OriginAt(tau, out _);

        /// <summary>物理の時刻 τ（秒、t* = 0）の keypose と枠の原点と白の時刻をシェーダーへ渡す（大域の値）。</summary>
        public void ApplyTau(double tau)
        {
            EnsureLoaded();
            if (Weights(meta.knotTau, tau, Slices, WeightsNow)) ClampedKnotCount++;
            var o = OriginAt(tau, out bool fc);
            if (fc) ClampedFrameCount++;
            Shader.SetGlobalVector(SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            Shader.SetGlobalVector(WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            Shader.SetGlobalVector(OriginId, new Vector4(o.x, o.y, o.z, 0));
            Shader.SetGlobalFloat(TauId, (float)tau);
            Shader.SetGlobalFloat(EnabledId, 1f);
            Shader.SetGlobalFloat(WhiteEnabledId, whiteEnabled ? 1f : 0f);
            Shader.DisableKeyword(PosLoKeyword);
            AppliedTau = tau;
            AppliedOrigin = o;
        }

        /// <summary>コンピュートシェーダー（DS27KeyposeCapture）へ同じ値を渡す。</summary>
        public void BindCompute(ComputeShader cs, int kernel)
        {
            EnsureLoaded();
            cs.DisableKeyword(PosLoKeyword);
            cs.SetBuffer(kernel, PosId, posBuf);
            cs.SetVector(BBoxMinId, new Vector4((float)meta.bboxMin[0], (float)meta.bboxMin[1], (float)meta.bboxMin[2], 0));
            cs.SetVector(BBoxSizeId, new Vector4((float)meta.bboxSize[0], (float)meta.bboxSize[1], (float)meta.bboxSize[2], 0));
            cs.SetVector(GridId, new Vector4(meta.cols, meta.rows, meta.rows * meta.cols, 0));
            cs.SetVector(SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            cs.SetVector(WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            cs.SetVector(OriginId, new Vector4(AppliedOrigin.x, AppliedOrigin.y, AppliedOrigin.z, 0));
            cs.SetFloat(TauId, (float)AppliedTau);
            cs.SetFloat(EnabledId, 1f);
        }

        /// <summary>パッケージを替える（採取で版を切り替えるとき）。</summary>
        public void Reload(string dir)
        {
            ReleaseBuffers();
            meta = null;
            packageDir = dir;
            EnsureLoaded();
        }

        static string Sha256(byte[] b)
        {
            using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }

        void ReleaseBuffers()
        {
            posBuf?.Release(); posBuf = null;
            whiteBuf?.Release(); whiteBuf = null;
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void LateUpdate()
        {
            if (!Application.isPlaying || !driveFromClock) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c == null) return;
            if (warp == null) warp = DS27TimeWarp.Load(timewarpPath);
            ApplyTau(warp.TauAt(c.Seconds));
        }

        void OnDisable()
        {
            if (!Application.isPlaying) return;
            Shader.SetGlobalFloat(EnabledId, 0f);
        }

        void OnDestroy()
        {
            Shader.SetGlobalFloat(EnabledId, 0f);
            ReleaseBuffers();
            meta = null;
        }
    }
}
