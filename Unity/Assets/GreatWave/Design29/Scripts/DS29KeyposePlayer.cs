using System;
using System.IO;
using System.Security.Cryptography;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using UnityEngine;

namespace GreatWave.Design29
{
    // 設計29：表示用サーフェス（密度を変えた格子）の keypose を GPU で再生する。設計27 の DS27KeyposePlayer の写しで、次だけを変えた
    // （設計27 のファイルは変えない。シェーダーは設計27 の DS27_NPR_White・DS27_Outline_Keypose をそのまま使い、同じ大域の値の名前へ渡す）：
    //  1) 格子の行 × 列はパッケージの ds27_keypose.json の rows・cols から読む（設計27 は 240 × 400 に固定して、ほかを拒んでいた）。
    //     シェーダーの法線（DS27Normal）は大域の _DS27Grid（列の数、行の数、頂点の数）から格子を読むので、そのまま使える。
    //  2) メッシュ（固定位相の格子、添字・UV・UV2）は同じ GameObject の AF26KStarMesh が読む。meshFromPackage のとき、
    //     パッケージの tstar/kstar_a45.gwb（表示の格子の t* の面。作り手 ds29_build.py が書く）を読む。
    //  3) 焼き込み用 UV（UV3、TEXCOORD2）は、パッケージに ds29_uv3_f32.bin（頂点ごとに float32 × 2、添字 = 行 × 列の数 + 列）があればそれを使う。
    //     無ければ 28修正01 の列ごと・行ごとの表（AF28NprWave.ApplyWarp と同じ）。表示の格子は列の並びが K* と違うので表は使えない。
    //  4) 色区テクスチャ（28修正01 の焼き込み、4096² RGBA32 線形）も自分で読み、_SdfTex を MaterialPropertyBlock で渡す
    //     （AF28NprWave.EnsureLoaded は列ごと・行ごとの表を必ず当てるので、表示の格子では使わない）。
    // 位置・T_white・補間（不等間隔の節点の 3 次 Hermite）・枠の原点 O(τ) の約束は設計27 と同じ（ds27_player_ref.py の冒頭）。
    // 読み込みは 2 段：LoadSurface（メッシュ・UV3・色区テクスチャ）→ LoadKeypose（位置と T_white の GPU バッファ）。GPU の容量を分けて測るため。
    // 設計29修正01：パッケージに精度の層（ds27_keypose.json の extensions に "pos_lo_rgba8/1"、ファイル ds27_pos_lo_rgba8.bin。
    //   設計28修正01 の試行E 以後の生成器 ds28r01e_generate.py の export_lo が書く）があり、readPosLo のとき、それも GPU だけの
    //   StructuredBuffer<uint>（頂点ごとに RGBA8 の 4 バイトをファイルのまま、層 × 頂点）へ読み、大域キーワード DS27_POS_LO を入れて
    //   位置 = bbox_min + (q16 + lo/255 − 0.5)/65535 × bbox_size で描く（刻み約 7 µm。16 bit だけでは約 1.7 mm）。
    //   精度の層のないパッケージ（設計27・28・29）と readPosLo = false では、キーワードを切り、設計29 とまったく同じに描く（後方互換）。
    //   どちらのバッファも CPU に写しを残さない（読み取り不可。設計29 §Q10 の (1)）。
    [RequireComponent(typeof(AF26KStarMesh))]
    [DefaultExecutionOrder(100)]
    public class DS29KeyposePlayer : MonoBehaviour
    {
        [Tooltip("パッケージのフォルダー（Unity プロジェクトからの相対パスか絶対パス。Git 対象外の /Unity/Build/Design/29/…）")]
        public string packageDir = "Build/Design/29/r01/full_240x400";
        [Tooltip("メッシュをパッケージの tstar/kstar_a45.gwb から読む（切ると AF26KStarMesh.dataPath のまま。設計28 の K* の格子の比較用）")]
        public bool meshFromPackage = true;
        [Tooltip("UV3 の頂点ごとのファイル（パッケージの中）。無ければ warpPath の列ごと・行ごとの表を使う")]
        public string uv3File = "ds29_uv3_f32.bin";
        [Tooltip("28修正01 の列ごと・行ごとの UV3 の表（K* の格子のときだけ使う）")]
        public string warpPath = "Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json";
        [Tooltip("28修正01 の色区の符号付き距離（4096² RGBA32 線形の生データ）")]
        public string sdfPath = "Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin";
        public int sdfSize = 4096;
        [Tooltip("外殻線 v0 の描画（子の MeshRenderer）。同じメッシュを渡す")]
        public MeshRenderer outline;
        public bool verifySha256 = true;
        public bool whiteEnabled = true;
        [Header("GWClock からの再生（設計30 で使う）")]
        public bool driveFromClock = false;
        public GWClock clock;
        public string timewarpPath = "../Tools/GWWaveGen/ds27/timewarp_default.json";
        [Header("設計29修正01：精度の層")]
        [Tooltip("パッケージに精度の層（extensions の pos_lo_rgba8/1、ds27_pos_lo_rgba8.bin）があれば読む。切ると 16 bit だけ（設計29 と同じ）")]
        public bool readPosLo = true;

        public const string PosLoExtension = "pos_lo_rgba8/1";

        DS27KeyposePlayer.Meta meta;
        GraphicsBuffer posBuf, whiteBuf, posLoBuf;
        Texture2D sdfTex;
        Mesh mesh;
        DS27TimeWarp warp;
        MaterialPropertyBlock block;

        public DS27KeyposePlayer.Meta PackageMeta => meta;
        public Mesh SurfaceMesh => mesh;
        public int[] Slices { get; } = new int[4];
        public float[] WeightsNow { get; } = new float[4];
        public double AppliedTau { get; private set; } = double.NaN;
        public Vector3 AppliedOrigin { get; private set; }
        public long PositionGpuBytes => posBuf == null ? 0 : (long)posBuf.count * posBuf.stride;
        public long WhiteGpuBytes => whiteBuf == null ? 0 : (long)whiteBuf.count * whiteBuf.stride;
        public long PosLoGpuBytes => posLoBuf == null ? 0 : (long)posLoBuf.count * posLoBuf.stride;
        /// <summary>精度の層を読んで使っているか（キーワード DS27_POS_LO を入れて描く）。</summary>
        public bool PosLoUsed => posLoBuf != null;
        /// <summary>パッケージの json に精度の層の拡張があったか（readPosLo に関わらず）。</summary>
        public bool PosLoInPackage { get; private set; }
        public string PosLoFile { get; private set; } = "";
        public string PosLoSha256 { get; private set; } = "";
        public long PosLoAlphaNot255 { get; private set; }
        public long AlphaNot65535 { get; private set; }
        public int WhiteNeverCount { get; private set; }
        public string MeshPath { get; private set; } = "";
        public string Uv3Source { get; private set; } = "";
        public string Uv3Sha256 { get; private set; } = "";
        public Bounds WorldBounds { get; private set; }
        public float SurfaceLoadSeconds { get; private set; }
        public float KeyposeLoadSeconds { get; private set; }

        public string FullDir => Path.GetFullPath(packageDir);

        /// <summary>DS27 の ReadMeta と同じ読み方で、格子の大きさの固定だけを外したもの。</summary>
        public static DS27KeyposePlayer.Meta ReadMeta(string dir)
        {
            var jp = Path.Combine(Path.GetFullPath(dir), "ds27_keypose.json");
            var bytes = File.ReadAllBytes(jp);
            var r = DS27Json.AsObj(DS27Json.Parse(System.Text.Encoding.UTF8.GetString(bytes)), "ds27_keypose.json");
            var m = new DS27KeyposePlayer.Meta
            {
                dir = Path.GetFullPath(dir),
                layers = (int)DS27Json.Num(r, "layers"), rows = (int)DS27Json.Num(r, "rows"), cols = (int)DS27Json.Num(r, "cols"),
                bboxMin = DS27Json.Nums(DS27Json.Get(r, "bbox_min"), "bbox_min"), bboxSize = DS27Json.Nums(DS27Json.Get(r, "bbox_size"), "bbox_size"),
                knotTau = DS27Json.Nums(DS27Json.Get(r, "knot_tau"), "knot_tau"),
                posSha256 = DS27Json.Text(r, "pos_sha256"), twhiteFile = DS27Json.Text(r, "twhite_file"), twhiteSha256 = DS27Json.Text(r, "twhite_sha256"),
                jsonSha256 = Sha256(bytes)
            };
            var fr = DS27Json.AsObj(DS27Json.Get(r, "frame"), "frame");
            m.frameTau = DS27Json.Nums(DS27Json.Get(fr, "tau"), "frame.tau");
            m.frameOrigin = DS27Json.Nums2(DS27Json.Get(fr, "origin"), "frame.origin");
            if (DS27Json.Has(r, "pre_white_index")) { m.preWhiteIndex = (int)DS27Json.Num(r, "pre_white_index"); m.hasPreWhiteIndex = true; }
            if (m.rows < 2 || m.cols < 2) throw new InvalidDataException("格子の行・列が 2 未満です: " + m.rows + " × " + m.cols);
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
            LoadSurface();
            LoadKeypose();
        }

        /// <summary>メッシュ（表示の格子の t* の面）、UV3、色区テクスチャ。GPU の位置のバッファはまだ作らない。</summary>
        public Mesh LoadSurface()
        {
            if (mesh != null) return mesh;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var m = meta ?? ReadMeta(packageDir);
            meta = m;
            var km = GetComponent<AF26KStarMesh>();
            if (meshFromPackage)
            {
                var gwb = Path.Combine(m.dir, "tstar", "kstar_a45.gwb");
                if (!File.Exists(gwb)) throw new FileNotFoundException("パッケージに tstar/kstar_a45.gwb がありません。", gwb);
                if (km.Mesh != null && Path.GetFullPath(km.dataPath) != Path.GetFullPath(gwb))
                    throw new InvalidOperationException("AF26KStarMesh は別の .gwb を読み込み済みです: " + km.dataPath);
                km.dataPath = gwb;
            }
            var ms = km.EnsureLoaded();
            MeshPath = km.FullDataPath;
            int n = m.rows * m.cols;
            if (ms.vertexCount != n || km.nu != m.cols || km.nv != m.rows)
                throw new InvalidDataException("パッケージの格子とメッシュが合いません: " + m.rows + " × " + m.cols + " / " + km.nv + " × " + km.nu);

            // UV3
            var up = Path.Combine(m.dir, uv3File);
            if (!string.IsNullOrEmpty(uv3File) && File.Exists(up))
            {
                var b = File.ReadAllBytes(up);
                if (b.Length != n * 8) throw new InvalidDataException("UV3 のファイルの大きさが頂点 × 8 と合いません: " + b.Length);
                var f = new float[n * 2];
                Buffer.BlockCopy(b, 0, f, 0, b.Length);
                var uv3 = new Vector2[n];
                for (int i = 0; i < n; i++) uv3[i] = new Vector2(f[2 * i], f[2 * i + 1]);
                ms.SetUVs(2, uv3);
                Uv3Source = "パッケージの頂点ごとの UV3（" + uv3File + "）";
                Uv3Sha256 = Sha256(b);
            }
            else
            {
                var wp = Path.GetFullPath(warpPath);
                var w = JsonUtility.FromJson<AF28NprWave.Warp>(File.ReadAllText(wp));
                AF28NprWave.ApplyWarp(ms, km.nu, km.nv, w.uWarp, w.vWarp);
                Uv3Source = "28修正01 の列ごと・行ごとの表（" + warpPath + "）";
                Uv3Sha256 = Sha256(File.ReadAllBytes(wp));
            }
            if (outline != null)
            {
                var of = outline.GetComponent<MeshFilter>();
                if (of != null) of.sharedMesh = ms;
            }

            // 色区テクスチャ
            if (sdfTex == null)
            {
                var sb = File.ReadAllBytes(Path.GetFullPath(sdfPath));
                if (sb.Length != sdfSize * sdfSize * 4) throw new InvalidDataException("色区テクスチャの容量が違います: " + sb.Length);
                sdfTex = new Texture2D(sdfSize, sdfSize, TextureFormat.RGBA32, false, true)
                {
                    name = "DS29 色区の符号付き距離 " + Path.GetFileNameWithoutExtension(sdfPath),
                    wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 0, hideFlags = HideFlags.DontSave
                };
                sdfTex.LoadRawTextureData(sb);
                sdfTex.Apply(false, true);
            }
            var r = GetComponent<Renderer>();
            if (r != null)
            {
                if (block == null) block = new MaterialPropertyBlock();
                r.GetPropertyBlock(block);
                block.SetTexture("_SdfTex", sdfTex);
                if (m.hasPreWhiteIndex) block.SetFloat("_PreWhiteClass", m.preWhiteIndex);
                r.SetPropertyBlock(block);
            }
            mesh = ms;
            SurfaceLoadSeconds = (float)sw.Elapsed.TotalSeconds;
            return ms;
        }

        /// <summary>位置（16 bit × 3 を uint に詰めた StructuredBuffer、GPU だけ）と T_white の GPU バッファ。設計27 と同じ詰め方。</summary>
        public void LoadKeypose()
        {
            if (posBuf != null) return;
            var ms = LoadSurface();
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var m = meta;
            int n = m.rows * m.cols;
            if ((n * 3) % 2 != 0) throw new InvalidDataException("頂点の数が奇数だと 16 bit × 3 を uint に詰められません: " + n);
            string pp = Path.Combine(m.dir, "ds27_pos_rgba16.bin");
            long layerBytes = (long)n * 8;
            var fi = new FileInfo(pp);
            if (fi.Length != layerBytes * m.layers) throw new InvalidDataException("ds27_pos_rgba16.bin の大きさが層 × 行 × 列 × 8 と合いません: " + fi.Length);
            int wordsPerLayer = n * 3 / 2;
            ReleaseBuffers();
            posBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, wordsPerLayer * m.layers, 4) { name = "DS29 keypose 位置（16 bit × 3）" };
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

            var tb = File.ReadAllBytes(Path.Combine(m.dir, m.twhiteFile));
            if (tb.Length != n * 4) { ReleaseBuffers(); throw new InvalidDataException("T_white の大きさが行 × 列 × 4 と合いません: " + tb.Length); }
            if (verifySha256 && Sha256(tb) != m.twhiteSha256) { ReleaseBuffers(); throw new InvalidDataException("T_white の SHA-256 が JSON と違います。"); }
            var tw = new float[n];
            Buffer.BlockCopy(tb, 0, tw, 0, tb.Length);
            int never = 0;
            foreach (var x in tw) if (x >= DS27KeyposePlayer.NeverWhite) never++;
            WhiteNeverCount = never;
            whiteBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n, 4) { name = "DS29 T_white（τ）" };
            whiteBuf.SetData(tw);
            LoadPosLo(m, n);

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
            ms.bounds = wb;
            WorldBounds = wb;
            BindGlobals();
            KeyposeLoadSeconds = (float)sw.Elapsed.TotalSeconds;
            ApplyTau(0.0);
        }

        /// <summary>設計29修正01：精度の層（RGBA8、層 × 頂点 × 4 バイト）を、ファイルのバイトのまま GPU だけのバッファへ読む。無ければ何もしない。</summary>
        void LoadPosLo(DS27KeyposePlayer.Meta m, int n)
        {
            PosLoInPackage = false; PosLoFile = ""; PosLoSha256 = ""; PosLoAlphaNot255 = 0;
            var jp = Path.Combine(m.dir, "ds27_keypose.json");
            var r = DS27Json.AsObj(DS27Json.Parse(System.Text.Encoding.UTF8.GetString(File.ReadAllBytes(jp))), "ds27_keypose.json");
            bool ext = false;
            if (DS27Json.Has(r, "extensions") && DS27Json.Get(r, "extensions") is System.Collections.Generic.List<object> el)
                foreach (var e in el) if (e is string es && es == PosLoExtension) ext = true;
            if (!ext) return;
            PosLoInPackage = true;
            string file = DS27Json.Text(r, "pos_lo_file");
            string want = DS27Json.Text(r, "pos_lo_sha256");
            PosLoFile = file;
            if (!readPosLo) return;
            string lp = Path.Combine(m.dir, file);
            long layerBytes = (long)n * 4;
            var fi = new FileInfo(lp);
            if (!fi.Exists) throw new FileNotFoundException("精度の層のファイルがありません（json には pos_lo_rgba8/1 がある）。", lp);
            if (fi.Length != layerBytes * m.layers) throw new InvalidDataException("精度の層の大きさが層 × 行 × 列 × 4 と合いません: " + fi.Length);
            posLoBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n * m.layers, 4) { name = "DS29 keypose 精度の層（RGBA8）" };
            var raw = new byte[layerBytes];
            var words = new uint[n];
            long alphaBad = 0;
            using (var sha = SHA256.Create())
            using (var fs = new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
            {
                for (int l = 0; l < m.layers; l++)
                {
                    int got = 0;
                    while (got < raw.Length)
                    {
                        int k = fs.Read(raw, got, raw.Length - got);
                        if (k <= 0) throw new EndOfStreamException("精度の層のファイルが途中で終わっています。");
                        got += k;
                    }
                    sha.TransformBlock(raw, 0, raw.Length, null, 0);
                    for (int v = 0; v < n; v++) if (raw[4 * v + 3] != 255) alphaBad++;
                    Buffer.BlockCopy(raw, 0, words, 0, raw.Length);
                    posLoBuf.SetData(words, 0, l * n, n);
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                PosLoSha256 = BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
            }
            PosLoAlphaNot255 = alphaBad;
            if (verifySha256 && PosLoSha256 != want) { ReleaseBuffers(); throw new InvalidDataException("精度の層の SHA-256 が JSON と違います: " + PosLoSha256); }
        }

        /// <summary>精度の層のキーワードとバッファを大域へ（無ければキーワードを切る＝設計29 と同じ変種）。</summary>
        void BindPosLoGlobal()
        {
            if (posLoBuf != null)
            {
                Shader.SetGlobalBuffer(DS27KeyposePlayer.PosLoId, posLoBuf);
                Shader.EnableKeyword(DS27KeyposePlayer.PosLoKeyword);
            }
            else Shader.DisableKeyword(DS27KeyposePlayer.PosLoKeyword);
        }

        /// <summary>シェーダーの大域の値（設計27 と同じ名前）をこのパッケージへ向ける。場面に主役波が複数あるときは、描く直前に呼ぶ。</summary>
        public void BindGlobals()
        {
            var m = meta;
            Shader.SetGlobalBuffer(DS27KeyposePlayer.PosId, posBuf);
            Shader.SetGlobalBuffer(DS27KeyposePlayer.WhiteId, whiteBuf);
            BindPosLoGlobal();
            Shader.SetGlobalVector(DS27KeyposePlayer.BBoxMinId, new Vector4((float)m.bboxMin[0], (float)m.bboxMin[1], (float)m.bboxMin[2], 0));
            Shader.SetGlobalVector(DS27KeyposePlayer.BBoxSizeId, new Vector4((float)m.bboxSize[0], (float)m.bboxSize[1], (float)m.bboxSize[2], 0));
            Shader.SetGlobalVector(DS27KeyposePlayer.GridId, new Vector4(m.cols, m.rows, m.rows * m.cols, 0));
            Shader.SetGlobalFloat(DS27KeyposePlayer.EnabledId, 1f);
            Shader.SetGlobalFloat(DS27KeyposePlayer.WhiteEnabledId, whiteEnabled ? 1f : 0f);
            Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0f);
        }

        public Vector3 OriginAt(double tau)
        {
            LoadKeypose();
            var ft = meta.frameTau;
            var fo = meta.frameOrigin;
            int n = ft.Length;
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

        /// <summary>物理の時刻 τ（t* = 0）の 4 層と重み・枠の原点・τ をシェーダーへ渡す（設計27 と同じ式）。</summary>
        public void ApplyTau(double tau)
        {
            LoadKeypose();
            DS27KeyposePlayer.Weights(meta.knotTau, tau, Slices, WeightsNow);
            var o = OriginAt(tau);
            Shader.SetGlobalVector(DS27KeyposePlayer.SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            Shader.SetGlobalVector(DS27KeyposePlayer.WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            Shader.SetGlobalVector(DS27KeyposePlayer.OriginId, new Vector4(o.x, o.y, o.z, 0));
            Shader.SetGlobalFloat(DS27KeyposePlayer.TauId, (float)tau);
            Shader.SetGlobalFloat(DS27KeyposePlayer.EnabledId, 1f);
            Shader.SetGlobalFloat(DS27KeyposePlayer.WhiteEnabledId, whiteEnabled ? 1f : 0f);
            BindPosLoGlobal();
            AppliedTau = tau;
            AppliedOrigin = o;
        }

        /// <summary>コンピュートシェーダー（設計27 の DS27KeyposeCapture）へ同じ値を渡す。</summary>
        public void BindCompute(ComputeShader cs, int kernel)
        {
            LoadKeypose();
            if (posLoBuf != null)
            {
                cs.EnableKeyword(DS27KeyposePlayer.PosLoKeyword);
                cs.SetBuffer(kernel, DS27KeyposePlayer.PosLoId, posLoBuf);
            }
            else cs.DisableKeyword(DS27KeyposePlayer.PosLoKeyword);
            cs.SetBuffer(kernel, DS27KeyposePlayer.PosId, posBuf);
            cs.SetVector(DS27KeyposePlayer.BBoxMinId, new Vector4((float)meta.bboxMin[0], (float)meta.bboxMin[1], (float)meta.bboxMin[2], 0));
            cs.SetVector(DS27KeyposePlayer.BBoxSizeId, new Vector4((float)meta.bboxSize[0], (float)meta.bboxSize[1], (float)meta.bboxSize[2], 0));
            cs.SetVector(DS27KeyposePlayer.GridId, new Vector4(meta.cols, meta.rows, meta.rows * meta.cols, 0));
            cs.SetVector(DS27KeyposePlayer.SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            cs.SetVector(DS27KeyposePlayer.WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            cs.SetVector(DS27KeyposePlayer.OriginId, new Vector4(AppliedOrigin.x, AppliedOrigin.y, AppliedOrigin.z, 0));
            cs.SetFloat(DS27KeyposePlayer.TauId, (float)AppliedTau);
            cs.SetFloat(DS27KeyposePlayer.EnabledId, 1f);
        }

        static string Sha256(byte[] b)
        {
            using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }

        void ReleaseBuffers()
        {
            posBuf?.Release(); posBuf = null;
            whiteBuf?.Release(); whiteBuf = null;
            posLoBuf?.Release(); posLoBuf = null;
        }

        public void Release()
        {
            ReleaseBuffers();
            if (sdfTex != null) { if (Application.isPlaying) Destroy(sdfTex); else DestroyImmediate(sdfTex); sdfTex = null; }
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

        void OnDestroy()
        {
            Shader.SetGlobalFloat(DS27KeyposePlayer.EnabledId, 0f);
            Shader.DisableKeyword(DS27KeyposePlayer.PosLoKeyword);
            Release();
            meta = null;
        }
    }
}
