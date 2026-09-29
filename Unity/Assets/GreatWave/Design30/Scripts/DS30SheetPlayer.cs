using System;
using System.IO;
using System.Security.Cryptography;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using GreatWave.Design29;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design30
{
    // 設計30：DS27 形式のシート（主役波と周りの海のシート）を 1 枚ずつ GPU で再生する。場面に何枚あっても同じ時計で一緒に描けるよう、
    // 設計29修正01 の DS29KeyposePlayer（大域の値で 1 枚だけを描く）の読み込みを写して、値の渡し方だけを変えた：
    //  1) keypose の値（_DS27Pos・_DS27White・_DS27PosLo・外接箱・格子・4 層と重み・枠の原点・τ・有効）は、大域ではなく
    //     レンダラーごとの MaterialPropertyBlock で渡す（面と外殻線の 2 つのレンダラー）。大域の値は読まれない（MaterialPropertyBlock が優先）。
    //  2) 精度の層のキーワード DS27_POS_LO は大域で入れたままにする（設計27 のシェーダーは multi_compile の大域のキーワード）。
    //     精度の層を持つシート（主役波 F_final）は自分の層を、持たないシートは「16 bit の丸めの残り 0」に近い一様な値 128/255 の層を渡す
    //     （復号の差は 16 bit の刻みの 0.5/255 = 0.00196 倍。周りの海の外接箱 1 km でも 0.03 mm）。キーワードを切り替えないので、
    //     1 回の描画の中で主役波と周りの海の変種が混ざらない。
    //  3) メッシュ：meshGwb（主役波は K*′ の .gwb）→ パッケージの tstar/kstar_a45.gwb → 行 × 列の格子を自分で張る（周りの海）の順。
    //     三角形は DS27Normal と同じ（四角 (r, c) ごとに (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)）。
    //  4) 色：sdfPath があれば設計28修正01／設計29修正01 の色区テクスチャと UV3（パッケージの頂点ごとの UV3 か列ごと・行ごとの表）、
    //     なければ flatClass（0 白、1 淡い水色、2 藍中、3 藍濃）の平塗り。
    // 補間（不等間隔の節点の 3 次 Hermite）・枠の原点 O(τ)・T_white の約束は設計27 と同じ（DS27KeyposePlayer.Weights、DS29KeyposePlayer.ReadMeta）。
    // 位置のバッファは CPU に写しを残さない（読み取り不可）。PC のオフスクリーン描画と Play モードで使う。HMD 実機は未検証。
    [DefaultExecutionOrder(100)]
    public class DS30SheetPlayer : MonoBehaviour
    {
        [Tooltip("シートの名前（報告の欄）")]
        public string sheetName = "hero";
        [Tooltip("DS27 形式のパッケージのフォルダー（Unity プロジェクトからの相対パスか絶対パス。Git 対象外の Build/）")]
        public string packageDir = "Build/Design/28R01F/F_final/art_on";
        [Tooltip("メッシュの .gwb（主役波は K*′）。空ならパッケージの tstar/kstar_a45.gwb、それも無ければ行 × 列の格子を張る")]
        public string meshGwb = "";
        [Tooltip("パッケージの頂点ごとの UV3（float32 × 2）。無ければ warpPath の表")]
        public string uv3File = "ds29_uv3_f32.bin";
        [Tooltip("列ごと・行ごとの UV3 の表（K* の格子のときだけ）")]
        public string warpPath = "";
        [Tooltip("色区の符号付き距離（4096² RGBA32 線形の生データ）。空なら flatClass の平塗り")]
        public string sdfPath = "";
        public int sdfSize = 4096;
        [Tooltip("平塗りの色区（sdfPath が空のとき）。0 白、1 淡い水色、2 藍中、3 藍濃")]
        public int flatClass = 3;
        [Tooltip("精度の層（pos_lo_rgba8/1）があれば読む")]
        public bool readPosLo = true;
        public bool whiteEnabled = true;
        public bool verifySha256 = true;
        [Tooltip("外殻線の子レンダラー（無ければ描かない）")]
        public MeshRenderer outline;
        [Tooltip("周りの海の仮の色（設計30 第B部。色と線は設計36・38・仕上げ30 で置き換える）：t* の高さ（ワールドの y）がこの値以上の頂点を白、未満を flatClass で塗る。NaN で使わない（全部 flatClass）")]
        public float whiteAboveTStarY = float.NaN;
        [Tooltip("白の前の色区（負ならパッケージの pre_white_index。周りの海は 3 = 藍濃）。whiteAboveTStarY を使い whiteEnabled のとき、白の頂点は" +
                 "その高さが閾値を最後に超えた節点の τ から白になる（それまでは白の前の色で塗る。育つ地形の誘導が白く浮き出る）")]
        public int preWhiteClass = -1;
        [Tooltip("描く列の範囲（頂点の列、両端を含む）。負なら全部。設計30 の主役波は本体の列 18〜394 だけを描き、外の平らな余白は周りの海の接続帯が置き換える")]
        public int colMin = -1, colMax = -1;
        [Tooltip("設計30修正1：列の範囲を使うとき、外殻線だけをさらに両端から何列内側まで描くか（0 で面と同じ範囲）。主役波の本体の境の輪（列 colMin・colMax）の" +
                 "法線は描かない余白の列から求まり、押し出した外殻線が継ぎ目に沿った灰色の線として海の上に見えたので、輪に触れる外殻線の三角形を描かない")]
        public int outlineColInset = 0;

        public const string PosLoExtension = "pos_lo_rgba8/1";

        DS27KeyposePlayer.Meta meta;
        GraphicsBuffer posBuf, whiteBuf, posLoBuf;
        Texture2D sdfTex;
        Mesh mesh, ownMesh, lineMesh;
        int[] fullTris, windowTris, lineWindowTris;
        bool[] tstarWhite;
        MaterialPropertyBlock block, lineBlock;
        MeshRenderer surface;

        public DS27KeyposePlayer.Meta PackageMeta => meta;
        public Mesh SurfaceMesh => mesh;
        public MeshRenderer Surface => surface != null ? surface : (surface = GetComponent<MeshRenderer>());
        public int[] Slices { get; } = new int[4];
        public float[] WeightsNow { get; } = new float[4];
        public double AppliedTau { get; private set; } = double.NaN;
        public Vector3 AppliedOrigin { get; private set; }
        public long PositionGpuBytes => posBuf == null ? 0 : (long)posBuf.count * posBuf.stride;
        public long WhiteGpuBytes => whiteBuf == null ? 0 : (long)whiteBuf.count * whiteBuf.stride;
        public long PosLoGpuBytes => posLoBuf == null ? 0 : (long)posLoBuf.count * posLoBuf.stride;
        public bool PosLoInPackage { get; private set; }
        public bool PosLoFromPackage { get; private set; }
        public string PosLoSha256 { get; private set; } = "";
        public long AlphaNot65535 { get; private set; }
        public long PosLoAlphaNot255 { get; private set; }
        public int WhiteNeverCount { get; private set; }
        public string MeshSource { get; private set; } = "";
        public string MeshSha256 { get; private set; } = "";
        public string Uv3Source { get; private set; } = "";
        public Bounds WorldBounds { get; private set; }
        public float LoadSeconds { get; private set; }
        public bool Loaded => posBuf != null;
        public int WhiteClassVertexCount { get; private set; }
        public bool ClassFileUsed { get; private set; }
        public bool WhiteFromHeight { get; private set; }
        public bool WhiteFromPackage { get; private set; }
        public int ClassFileAgree { get; private set; }
        public bool ColumnWindowOn { get; private set; }
        public int FullTriangleCount => fullTris == null ? 0 : fullTris.Length / 3;
        public int WindowTriangleCount => windowTris == null ? 0 : windowTris.Length / 3;
        public int OutlineWindowTriangleCount => lineWindowTris != null ? lineWindowTris.Length / 3 : WindowTriangleCount;

        static readonly int SdfTexId = Shader.PropertyToID("_SdfTex"), PreWhiteId = Shader.PropertyToID("_PreWhiteClass"), FlatId = Shader.PropertyToID("_FlatClass");

        public void EnsureLoaded()
        {
            if (posBuf != null) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            meta = DS29KeyposePlayer.ReadMeta(packageDir);
            LoadMesh();
            LoadBuffers();
            SetupBlocks();
            LoadSeconds = (float)sw.Elapsed.TotalSeconds;
            ApplyTau(meta.knotTau[meta.layers - 1]);
        }

        void LoadMesh()
        {
            var m = meta;
            int n = m.rows * m.cols;
            string gwb = meshGwb;
            if (string.IsNullOrEmpty(gwb))
            {
                var pg = Path.Combine(m.dir, "tstar", "kstar_a45.gwb");
                if (File.Exists(pg)) gwb = pg;
            }
            if (!string.IsNullOrEmpty(gwb))
            {
                var km = GetComponent<AF26KStarMesh>();
                if (km == null) km = gameObject.AddComponent<AF26KStarMesh>();
                km.dataPath = gwb;
                mesh = km.EnsureLoaded();
                if (mesh.vertexCount != n || km.nu != m.cols || km.nv != m.rows)
                    throw new InvalidDataException(sheetName + "：パッケージの格子とメッシュが合いません: " + m.rows + " × " + m.cols + " / " + km.nv + " × " + km.nu);
                MeshSource = "gwb " + km.FullDataPath;
                MeshSha256 = FileSha256(km.FullDataPath);
            }
            else
            {
                // 行 × 列の格子（DS27Normal と同じ三角形）。頂点の位置は描画に使わない（シェーダーがバッファから読む）ので 0。
                var verts = new Vector3[n];
                var uv = new Vector2[n];
                for (int r = 0; r < m.rows; r++)
                    for (int c = 0; c < m.cols; c++) uv[r * m.cols + c] = new Vector2(c / (float)(m.cols - 1), r / (float)(m.rows - 1));
                var tris = new int[(m.rows - 1) * (m.cols - 1) * 6];
                int k = 0;
                for (int r = 0; r + 1 < m.rows; r++)
                    for (int c = 0; c + 1 < m.cols; c++)
                    {
                        int v = r * m.cols + c;
                        tris[k++] = v; tris[k++] = v + m.cols; tris[k++] = v + 1;
                        tris[k++] = v + 1; tris[k++] = v + m.cols; tris[k++] = v + m.cols + 1;
                    }
                ownMesh = new Mesh { name = "DS30 シートの格子 " + sheetName, indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
                ownMesh.vertices = verts;
                ownMesh.uv = uv;
                ownMesh.SetTriangles(tris, 0, false);
                mesh = ownMesh;
                var mf = GetComponent<MeshFilter>();
                if (mf == null) mf = gameObject.AddComponent<MeshFilter>();
                mf.sharedMesh = mesh;
                MeshSource = "行 × 列の格子（" + m.rows + " × " + m.cols + "、DS27Normal と同じ三角形）";
            }

            // UV3（色区のときだけ意味がある）
            var up = string.IsNullOrEmpty(uv3File) ? "" : Path.Combine(m.dir, uv3File);
            if (!float.IsNaN(whiteAboveTStarY))
            {
                // 2 色：t* の層（最後の層、精度の層つき）の高さで白か flatClass か。2 × 1 の色区テクスチャの左の画素 = flatClass、右 = 白。
                // 双線形の読みで、境は UV3.x = 0.5 の所（シェーダーのアンチエイリアスのまま）。
                var ty = TStarWorldY(m, n);
                var uv3 = new Vector2[n];
                tstarWhite = new bool[n];
                int nw = 0;
                // UV3.x = 0.5 + 0.25·(y − 閾値)/0.5 m（0.25〜0.75 に切る）。三角形の中は高さの線形補間と同じなので、2 色の境は t* の高さ = 閾値の
                // 等高線（三角形ごとの直線がつながった線）になり、頂点ごとに色を決めたときのぎざぎざが出ない
                // 第A部の色区の手がかり（パッケージの class_file、uint8：0 = 海、1 = 白）があれば、頂点の側はそれに従わせる（境の形は等高線のまま）
                byte[] cls = null;
                var jr0 = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(m.dir, "ds27_keypose.json"))), "ds27_keypose.json");
                if (DS27Json.Has(jr0, "class_file"))
                {
                    var cp = Path.Combine(m.dir, DS27Json.Text(jr0, "class_file"));
                    if (File.Exists(cp)) { cls = File.ReadAllBytes(cp); if (cls.Length != n) cls = null; }
                }
                int agree = 0;
                for (int i = 0; i < n; i++)
                {
                    float u = Mathf.Clamp(0.5f + 0.25f * (ty[i] - whiteAboveTStarY) / 0.5f, 0.25f, 0.75f);
                    if (cls != null)
                    {
                        if ((cls[i] != 0) == (ty[i] >= whiteAboveTStarY)) agree++;
                        u = cls[i] != 0 ? Mathf.Max(u, 0.51f) : Mathf.Min(u, 0.49f);
                    }
                    if (u > 0.5f) nw++;
                    uv3[i] = new Vector2(u, 0.5f);
                    tstarWhite[i] = u > 0.5f;
                }
                ClassFileUsed = cls != null; ClassFileAgree = agree;
                mesh.SetUVs(2, uv3);
                WhiteClassVertexCount = nw;
                sdfTex = new Texture2D(2, 1, TextureFormat.RGBA32, false, true)
                {
                    name = "DS30 周りの海の 2 色 " + sheetName, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 0, hideFlags = HideFlags.DontSave
                };
                var px = new Color32[2];
                px[0] = new Color32(flatClass == 0 ? (byte)255 : (byte)0, flatClass == 1 ? (byte)255 : (byte)0, flatClass == 2 ? (byte)255 : (byte)0, flatClass == 3 ? (byte)255 : (byte)0);
                px[1] = new Color32(255, 0, 0, 0);
                sdfTex.SetPixels32(px);
                sdfTex.Apply(false, false);
                Uv3Source = "t* の高さ ≥ " + whiteAboveTStarY.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) + " m の等高線で白（" + nw + " 頂点）、ほかは色区 " + flatClass +
                            (cls != null ? "。頂点の側は第A部の class_file に従う（等高線の読みと一致 " + agree + "/" + n + "）" : "");
            }
            else if (!string.IsNullOrEmpty(up) && File.Exists(up))
            {
                var b = File.ReadAllBytes(up);
                if (b.Length != n * 8) throw new InvalidDataException(sheetName + "：UV3 のファイルの大きさが頂点 × 8 と合いません: " + b.Length);
                var f = new float[n * 2];
                Buffer.BlockCopy(b, 0, f, 0, b.Length);
                var uv3 = new Vector2[n];
                for (int i = 0; i < n; i++) uv3[i] = new Vector2(f[2 * i], f[2 * i + 1]);
                mesh.SetUVs(2, uv3);
                Uv3Source = "パッケージの頂点ごとの UV3（" + uv3File + "、" + Sha256(b) + "）";
            }
            else if (!string.IsNullOrEmpty(warpPath))
            {
                var wp = Path.GetFullPath(warpPath);
                var w = JsonUtility.FromJson<AF28NprWave.Warp>(File.ReadAllText(wp));
                AF28NprWave.ApplyWarp(mesh, m.cols, m.rows, w.uWarp, w.vWarp);
                Uv3Source = "列ごと・行ごとの表（" + warpPath + "、" + FileSha256(wp) + "）";
            }
            else
            {
                mesh.SetUVs(2, new Vector2[n]);
                Uv3Source = "なし（平塗り）";
            }
            if (outline != null)
            {
                var of = outline.GetComponent<MeshFilter>();
                if (of != null) of.sharedMesh = mesh;
            }
            // 列の範囲（面と外殻線は同じメッシュ）
            fullTris = mesh.GetTriangles(0);
            if (colMin >= 0 && colMax >= colMin)
            {
                var keep = new System.Collections.Generic.List<int>(fullTris.Length);
                for (int t = 0; t < fullTris.Length; t += 3)
                {
                    int c0 = fullTris[t] % m.cols, c1 = fullTris[t + 1] % m.cols, c2 = fullTris[t + 2] % m.cols;
                    if (c0 < colMin || c1 < colMin || c2 < colMin || c0 > colMax || c1 > colMax || c2 > colMax) continue;
                    keep.Add(fullTris[t]); keep.Add(fullTris[t + 1]); keep.Add(fullTris[t + 2]);
                }
                windowTris = keep.ToArray();
                // 設計30修正1：外殻線は別のメッシュ（頂点は同じ、三角形だけ outlineColInset 列だけ内側）
                if (outline != null && outlineColInset > 0)
                {
                    int lo = colMin + outlineColInset, hi = colMax - outlineColInset;
                    var lk = new System.Collections.Generic.List<int>(windowTris.Length);
                    for (int t = 0; t < windowTris.Length; t += 3)
                    {
                        int c0 = windowTris[t] % m.cols, c1 = windowTris[t + 1] % m.cols, c2 = windowTris[t + 2] % m.cols;
                        if (c0 < lo || c1 < lo || c2 < lo || c0 > hi || c1 > hi || c2 > hi) continue;
                        lk.Add(windowTris[t]); lk.Add(windowTris[t + 1]); lk.Add(windowTris[t + 2]);
                    }
                    lineWindowTris = lk.ToArray();
                    lineMesh = Instantiate(mesh);
                    lineMesh.name = mesh.name + "（外殻線）";
                    lineMesh.hideFlags = HideFlags.DontSave;
                    var of = outline.GetComponent<MeshFilter>();
                    if (of != null) of.sharedMesh = lineMesh;
                }
                UseColumnWindow(true);
            }
            if (!string.IsNullOrEmpty(sdfPath) && sdfTex == null)
            {
                var sb = File.ReadAllBytes(Path.GetFullPath(sdfPath));
                if (sb.Length != sdfSize * sdfSize * 4) throw new InvalidDataException(sheetName + "：色区テクスチャの容量が違います: " + sb.Length);
                sdfTex = new Texture2D(sdfSize, sdfSize, TextureFormat.RGBA32, false, true)
                {
                    name = "DS30 色区の符号付き距離 " + Path.GetFileNameWithoutExtension(sdfPath),
                    wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 0, hideFlags = HideFlags.DontSave
                };
                sdfTex.LoadRawTextureData(sb);
                sdfTex.Apply(false, true);
            }
        }

        /// <summary>最後の層（t*、τ = 0）の頂点のワールドの y（精度の層があれば読む）。</summary>
        float[] TStarWorldY(DS27KeyposePlayer.Meta m, int n)
        {
            var hi = new byte[(long)n * 8];
            using (var fs = new FileStream(Path.Combine(m.dir, "ds27_pos_rgba16.bin"), FileMode.Open, FileAccess.Read, FileShare.Read))
            { fs.Seek((long)(m.layers - 1) * n * 8, SeekOrigin.Begin); ReadFully(fs, hi); }
            byte[] lo = null;
            var jr = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(m.dir, "ds27_keypose.json"))), "ds27_keypose.json");
            if (DS27Json.Has(jr, "pos_lo_file"))
            {
                var lp = Path.Combine(m.dir, DS27Json.Text(jr, "pos_lo_file"));
                if (File.Exists(lp)) { lo = new byte[(long)n * 4]; using (var fl = new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read)) { fl.Seek((long)(m.layers - 1) * n * 4, SeekOrigin.Begin); ReadFully(fl, lo); } }
            }
            double oy = OriginAt(m.knotTau[m.layers - 1]).y;
            var y = new float[n];
            for (int v = 0; v < n; v++)
            {
                double q = BitConverter.ToUInt16(hi, v * 8 + 2);
                double off = lo != null ? lo[v * 4 + 1] / 255.0 - 0.5 : 0.0;
                y[v] = (float)(m.bboxMin[1] + (q + off) / 65535.0 * m.bboxSize[1] + oy);
            }
            return y;
        }

        /// <summary>列の範囲だけを描くか、全部を描くか（外接箱は変えない）。</summary>
        public void UseColumnWindow(bool on)
        {
            if (mesh == null || fullTris == null) return;
            bool w = on && windowTris != null;
            var b = mesh.bounds;
            mesh.SetTriangles(w ? windowTris : fullTris, 0, false);
            mesh.bounds = b;
            if (lineMesh != null)
            {
                var lb = lineMesh.bounds;
                lineMesh.SetTriangles(w && lineWindowTris != null ? lineWindowTris : fullTris, 0, false);
                lineMesh.bounds = lb;
            }
            ColumnWindowOn = w;
        }

        void LoadBuffers()
        {
            var m = meta;
            int n = m.rows * m.cols;
            string pp = Path.Combine(m.dir, "ds27_pos_rgba16.bin");
            long layerBytes = (long)n * 8;
            var fi = new FileInfo(pp);
            if (fi.Length != layerBytes * m.layers) throw new InvalidDataException(sheetName + "：ds27_pos_rgba16.bin の大きさが層 × 行 × 列 × 8 と合いません: " + fi.Length);
            ReleaseBuffers();
            // 16 bit × 3 を層をまたいで切れ目なく uint に詰める（シェーダーの番号 i = (層 × N + 頂点) × 3 + 成分 と同じ並び）。
            // 頂点の数が奇数（遠い海 19 × 247 など）だと層の境が uint の途中になるので、全体を 1 本の列として詰め、最後に 1 語の余白を足す。
            long totalUs = (long)m.layers * n * 3;
            int posWords = (int)((totalUs + 1) / 2) + 1;
            posBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, posWords, 4) { name = "DS30 " + sheetName + " 位置（16 bit × 3）" };
            var raw = new byte[layerBytes];
            var us = new ushort[n * 4];
            // 1 回に SetData する塊：偶数個の 16 bit の値（uint の境に合わせる）
            var pend = new System.Collections.Generic.List<ushort>(n * 3 + 2);
            bool heightWhite = tstarWhite != null && whiteEnabled;
            int[] lastBelow = null;
            if (heightWhite) { lastBelow = new int[n]; for (int v = 0; v < n; v++) lastBelow[v] = -1; }
            double sy = m.bboxSize[1] / 65535.0, by = m.bboxMin[1];
            var chunk = new uint[(n * 3 + 2) / 2 + 1];
            int wordAt = 0;
            long alphaBad = 0;
            using (var sha = SHA256.Create())
            using (var fs = new FileStream(pp, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
            {
                for (int l = 0; l < m.layers; l++)
                {
                    ReadFully(fs, raw);
                    if (verifySha256) sha.TransformBlock(raw, 0, raw.Length, null, 0);
                    Buffer.BlockCopy(raw, 0, us, 0, raw.Length);
                    if (heightWhite)
                    {
                        double oy = OriginAt(m.knotTau[l]).y;
                        for (int v = 0; v < n; v++) if (by + us[4 * v + 1] * sy + oy < whiteAboveTStarY) lastBelow[v] = l;
                    }
                    for (int v = 0; v < n; v++)
                    {
                        pend.Add(us[4 * v]); pend.Add(us[4 * v + 1]); pend.Add(us[4 * v + 2]);
                        if (us[4 * v + 3] != 65535) alphaBad++;
                    }
                    bool last = l == m.layers - 1;
                    int take = last ? pend.Count : pend.Count & ~1;   // 最後の層のほかは偶数個だけ書き、余りは次の層へ持ち越す
                    int nw = (take + 1) / 2;
                    for (int w = 0; w < nw; w++)
                    {
                        uint lo16 = pend[2 * w];
                        uint hi16 = 2 * w + 1 < take ? pend[2 * w + 1] : 0u;
                        chunk[w] = lo16 | (hi16 << 16);
                    }
                    posBuf.SetData(chunk, 0, wordAt, nw);
                    wordAt += nw;
                    pend.RemoveRange(0, take);
                }
                posBuf.SetData(new uint[] { 0u }, 0, wordAt, 1);
                if (verifySha256)
                {
                    sha.TransformFinalBlock(new byte[0], 0, 0);
                    var h = Hex(sha.Hash);
                    if (h != m.posSha256) { ReleaseBuffers(); throw new InvalidDataException(sheetName + "：ds27_pos_rgba16.bin の SHA-256 が JSON と違います: " + h); }
                }
            }
            AlphaNot65535 = alphaBad;

            var tw = new float[n];
            var tp = Path.Combine(m.dir, m.twhiteFile ?? "");
            if (!string.IsNullOrEmpty(m.twhiteFile) && File.Exists(tp))
            {
                var tb = File.ReadAllBytes(tp);
                if (tb.Length != n * 4) { ReleaseBuffers(); throw new InvalidDataException(sheetName + "：T_white の大きさが行 × 列 × 4 と合いません: " + tb.Length); }
                if (verifySha256 && !string.IsNullOrEmpty(m.twhiteSha256) && Sha256(tb) != m.twhiteSha256) { ReleaseBuffers(); throw new InvalidDataException(sheetName + "：T_white の SHA-256 が JSON と違います。"); }
                Buffer.BlockCopy(tb, 0, tw, 0, tb.Length);
            }
            else for (int i = 0; i < n; i++) tw[i] = 1.0e9f;
            bool fileHasWhite = false;
            foreach (var x in tw) if (x < DS27KeyposePlayer.NeverWhite) { fileHasWhite = true; break; }
            if (heightWhite && !fileHasWhite)
            {
                // パッケージの T_white がすべて +1e9 のとき：白の頂点（t* の色区が白）は、高さが閾値を最後に超えた節点の τ から白。ほかは t* までに白にならない
                for (int v = 0; v < n; v++)
                    tw[v] = tstarWhite[v] ? (float)m.knotTau[Math.Min(lastBelow[v] + 1, m.layers - 1)] : 1.0e9f;
                WhiteFromHeight = true;
            }
            else if (fileHasWhite && tstarWhite != null)
            {
                // パッケージの T_white（第A部 v1：高い所ほど早く白）をそのまま使う。t* の色区が白でない頂点は白にならない（念のため +1e9）
                for (int v = 0; v < n; v++) if (!tstarWhite[v]) tw[v] = 1.0e9f;
                WhiteFromPackage = true;
            }
            int never = 0;
            foreach (var x in tw) if (x >= DS27KeyposePlayer.NeverWhite) never++;
            WhiteNeverCount = never;
            whiteBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n, 4) { name = "DS30 " + sheetName + " T_white" };
            whiteBuf.SetData(tw);

            // 精度の層（無ければ 128/255 の一様な層）
            PosLoInPackage = false; PosLoFromPackage = false; PosLoSha256 = ""; PosLoAlphaNot255 = 0;
            var jr = DS27Json.AsObj(DS27Json.Parse(System.Text.Encoding.UTF8.GetString(File.ReadAllBytes(Path.Combine(m.dir, "ds27_keypose.json")))), "ds27_keypose.json");
            if (DS27Json.Has(jr, "extensions") && DS27Json.Get(jr, "extensions") is System.Collections.Generic.List<object> el)
                foreach (var e in el) if (e is string es && es == PosLoExtension) PosLoInPackage = true;
            posLoBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n * m.layers, 4) { name = "DS30 " + sheetName + " 精度の層（RGBA8）" };
            if (PosLoInPackage && readPosLo)
            {
                string lp = Path.Combine(m.dir, DS27Json.Text(jr, "pos_lo_file"));
                string want = DS27Json.Text(jr, "pos_lo_sha256");
                var lfi = new FileInfo(lp);
                if (!lfi.Exists || lfi.Length != (long)n * 4 * m.layers) { ReleaseBuffers(); throw new InvalidDataException(sheetName + "：精度の層の大きさが層 × 行 × 列 × 4 と合いません: " + lp); }
                var lraw = new byte[(long)n * 4];
                var words = new uint[n];
                long bad = 0;
                using (var sha = SHA256.Create())
                using (var fs = new FileStream(lp, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
                {
                    for (int l = 0; l < m.layers; l++)
                    {
                        ReadFully(fs, lraw);
                        sha.TransformBlock(lraw, 0, lraw.Length, null, 0);
                        for (int v = 0; v < n; v++) if (lraw[4 * v + 3] != 255) bad++;
                        Buffer.BlockCopy(lraw, 0, words, 0, lraw.Length);
                        posLoBuf.SetData(words, 0, l * n, n);
                    }
                    sha.TransformFinalBlock(new byte[0], 0, 0);
                    PosLoSha256 = Hex(sha.Hash);
                }
                PosLoAlphaNot255 = bad;
                if (verifySha256 && PosLoSha256 != want) { ReleaseBuffers(); throw new InvalidDataException(sheetName + "：精度の層の SHA-256 が JSON と違います: " + PosLoSha256); }
                PosLoFromPackage = true;
            }
            else
            {
                var words = new uint[n];
                uint mid = 0xFF808080u;   // R = G = B = 128、A = 255
                for (int v = 0; v < n; v++) words[v] = mid;
                for (int l = 0; l < m.layers; l++) posLoBuf.SetData(words, 0, l * n, n);
            }

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
            // シェーダーはワールドの位置を直接描く（オブジェクトの変換を使わない）。カリングの外接箱はオブジェクトの変換で写るので、逆に写しておく
            var inv = transform.worldToLocalMatrix;
            var lb = new Bounds(inv.MultiplyPoint3x4(wb.center), Vector3.zero);
            foreach (var cx in new[] { wb.min.x, wb.max.x }) foreach (var cy in new[] { wb.min.y, wb.max.y }) foreach (var cz in new[] { wb.min.z, wb.max.z })
                lb.Encapsulate(inv.MultiplyPoint3x4(new Vector3(cx, cy, cz)));
            mesh.bounds = lb;
            if (lineMesh != null) lineMesh.bounds = lb;
            WorldBounds = wb;
        }

        void SetupBlocks()
        {
            Shader.EnableKeyword(DS27KeyposePlayer.PosLoKeyword);
            if (block == null) block = new MaterialPropertyBlock();
            if (lineBlock == null) lineBlock = new MaterialPropertyBlock();
            var r = Surface;
            if (r != null)
            {
                r.GetPropertyBlock(block);
                if (sdfTex != null) { block.SetTexture(SdfTexId, sdfTex); block.SetFloat(FlatId, -1f); }
                else block.SetFloat(FlatId, flatClass);
                block.SetFloat(PreWhiteId, preWhiteClass >= 0 ? preWhiteClass : (meta.hasPreWhiteIndex ? meta.preWhiteIndex : 2));
                r.SetPropertyBlock(block);
            }
            if (outline != null) { outline.GetPropertyBlock(lineBlock); outline.SetPropertyBlock(lineBlock); }
        }

        void Fill(MaterialPropertyBlock b, Vector3 o, double tau)
        {
            var m = meta;
            b.SetBuffer(DS27KeyposePlayer.PosId, posBuf);
            b.SetBuffer(DS27KeyposePlayer.WhiteId, whiteBuf);
            b.SetBuffer(DS27KeyposePlayer.PosLoId, posLoBuf);
            b.SetVector(DS27KeyposePlayer.BBoxMinId, new Vector4((float)m.bboxMin[0], (float)m.bboxMin[1], (float)m.bboxMin[2], 0));
            b.SetVector(DS27KeyposePlayer.BBoxSizeId, new Vector4((float)m.bboxSize[0], (float)m.bboxSize[1], (float)m.bboxSize[2], 0));
            b.SetVector(DS27KeyposePlayer.GridId, new Vector4(m.cols, m.rows, m.rows * m.cols, 0));
            b.SetVector(DS27KeyposePlayer.SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            b.SetVector(DS27KeyposePlayer.WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            b.SetVector(DS27KeyposePlayer.OriginId, new Vector4(o.x, o.y, o.z, 0));
            b.SetFloat(DS27KeyposePlayer.TauId, (float)tau);
            b.SetFloat(DS27KeyposePlayer.EnabledId, 1f);
            b.SetFloat(DS27KeyposePlayer.WhiteEnabledId, whiteEnabled ? 1f : 0f);
        }

        public Vector3 OriginAt(double tau)
        {
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

        /// <summary>物理の時刻 τ（t* = 0）の 4 層と重み・枠の原点・τ を、このシートのレンダラーだけへ渡す。</summary>
        public void ApplyTau(double tau)
        {
            if (posBuf == null) EnsureLoaded();
            DS27KeyposePlayer.Weights(meta.knotTau, tau, Slices, WeightsNow);
            var o = OriginAt(tau);
            var r = Surface;
            if (r != null) { r.GetPropertyBlock(block); Fill(block, o, tau); r.SetPropertyBlock(block); }
            if (outline != null) { outline.GetPropertyBlock(lineBlock); Fill(lineBlock, o, tau); outline.SetPropertyBlock(lineBlock); }
            AppliedTau = tau;
            AppliedOrigin = o;
        }

        /// <summary>検査用：面の色区を一時的に平塗りにする（k = 0〜3）。負で元へ戻す。</summary>
        public void SetDebugFlatClass(int k)
        {
            var r = Surface;
            if (r == null || block == null) return;
            r.GetPropertyBlock(block);
            block.SetFloat(FlatId, k >= 0 ? k : (sdfTex != null ? -1f : flatClass));
            r.SetPropertyBlock(block);
        }

        /// <summary>検査用のコンピュートシェーダー（設計27 の DS27KeyposeCapture）へ同じ値を渡す（精度の層のキーワードは常に入れる）。</summary>
        public void BindCompute(ComputeShader cs, int kernel)
        {
            cs.EnableKeyword(DS27KeyposePlayer.PosLoKeyword);
            cs.SetBuffer(kernel, DS27KeyposePlayer.PosLoId, posLoBuf);
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

        static void ReadFully(Stream fs, byte[] raw)
        {
            int got = 0;
            while (got < raw.Length)
            {
                int k = fs.Read(raw, got, raw.Length - got);
                if (k <= 0) throw new EndOfStreamException("ファイルが途中で終わっています。");
                got += k;
            }
        }

        static string Hex(byte[] h) => BitConverter.ToString(h).Replace("-", "").ToLowerInvariant();
        static string Sha256(byte[] b) { using (var s = SHA256.Create()) return Hex(s.ComputeHash(b)); }
        static string FileSha256(string p) { using (var s = SHA256.Create()) using (var f = File.OpenRead(p)) return Hex(s.ComputeHash(f)); }

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
            if (ownMesh != null) { if (Application.isPlaying) Destroy(ownMesh); else DestroyImmediate(ownMesh); ownMesh = null; }
            if (lineMesh != null) { if (Application.isPlaying) Destroy(lineMesh); else DestroyImmediate(lineMesh); lineMesh = null; }
            lineWindowTris = null;
            mesh = null;
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void OnDestroy()
        {
            Release();
            meta = null;
        }
    }
}
