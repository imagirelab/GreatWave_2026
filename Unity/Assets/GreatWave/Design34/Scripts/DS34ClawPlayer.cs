using System;
using System.IO;
using System.Security.Cryptography;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design34
{
    // 設計34：爪の層。設計33 の爪の帯（148 本、GreatWave.DS33.claw_layout/1）を 1 つの結合メッシュにし、コマの表の頂点を差し替えて再生する。
    //   ・ds33_claw_frames_f32.bin：float32、コマ × 頂点 × 3（ワールドの m）。コマ k は体験の時刻 t = k/hz（hz = 30、設計31・32 と同じ時計、同じ τ(t)）。
    //   ・ds33_claw_tris_i32.bin：int32、三角形 × 3。ds33_claw_tri_attr_u16.bin：uint16、三角形 × 2（爪の番号、面の種類 0 上面・1 縁の側面と下面・2 根元の白の円）。
    //   ・部分メッシュ 0 = 白（面の種類 0 と 2）、1 = 淡い水色（面の種類 1）。見えないコマの爪は根元の点に潰してある（面積 0 で描かれない）。
    // 時刻：採取（DS34Render）は ApplyT(t) を DS30SinglePlayback.Seek と同じ t で呼ぶ。Play モードでは GWClock の秒（DS30SinglePlayback が書く）を読む。
    //   t がコマの格子の上（|t·hz − k| < 1e-4）ならコマ k をそのまま使う（主役波・飛沫と同じコマ番号）。格子の間は隣の 2 コマを線形に補う（Play モードの 90 Hz など）。
    //   t* = 12 s の後は、表の最後のコマ（t 14 s、t* の姿のまま）まで同じ規則、それより後は最後のコマ。
    [DefaultExecutionOrder(60)]   // DS30SinglePlayback（50）が時計を書いた後に読む
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class DS34ClawPlayer : MonoBehaviour
    {
        [Tooltip("設計33 の爪の並び（ds33_claw_layout.json。Unity プロジェクトからの相対パスか絶対パス）")]
        public string layoutPath = "Build/Design/33/claws/ds33_claw_layout.json";
        public GWClock clock;
        public bool verifySha256 = true;
        [Tooltip("白（上面と根元の白の円）。主役波の DS27 NPR White の _White と同じ")]
        public Color white = new Color(0.97255f, 0.95294f, 0.87451f, 1f);
        [Tooltip("淡い水色（縁の側面と下面）。主役波の DS27 NPR White の _Mizuiro と同じ")]
        public Color mizuiro = new Color(0.77647f, 0.84314f, 0.79608f, 1f);
        [Tooltip("Play モードで GWClock を読んで頂点を差し替える")]
        public bool followClockInPlayMode = true;

        public const string ShaderName = "GreatWave/Design34/DS34 Claw Unlit";
        public int Frames { get; private set; }
        public float Hz { get; private set; }
        public int VertexCount { get; private set; }
        public int TriangleCount { get; private set; }
        public int ClawCount { get; private set; }
        public string[] ClawIds { get; private set; }
        public int[] VertOffset { get; private set; }
        public int[] VertCount { get; private set; }
        public string FramesSha256 { get; private set; } = "";
        public string TrisSha256 { get; private set; } = "";
        public string AttrSha256 { get; private set; } = "";
        public bool Loaded => mesh != null;
        public double AppliedT { get; private set; } = double.NaN;
        /// <summary>今の頂点がどのコマから来たか（格子の上ならその番号、間なら小数の位置）。</summary>
        public double AppliedFrame { get; private set; } = double.NaN;
        public bool AppliedOnGrid { get; private set; }
        public int WhiteTriangles { get; private set; }
        public int MizuiroTriangles { get; private set; }
        public float LoadSeconds { get; private set; }

        float[] frames;     // コマ × 頂点 × 3
        Vector3[] now;
        Mesh mesh;
        Material matWhite, matMizuiro;

        public void Load()
        {
            if (mesh != null) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var lp = Path.GetFullPath(layoutPath);
            var jo = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(lp)), "claw_layout");
            if (DS27Json.Text(jo, "schema") != "GreatWave.DS33.claw_layout/1") throw new InvalidDataException("爪の並びの書式ではありません: " + lp);
            Frames = (int)DS27Json.Num(jo, "frames");
            Hz = (float)DS27Json.Num(jo, "hz");
            VertexCount = (int)DS27Json.Num(jo, "vertices");
            TriangleCount = (int)DS27Json.Num(jo, "triangles");
            var fl = DS27Json.AsObj(DS27Json.Get(jo, "files"), "files");
            string dir = Path.GetDirectoryName(lp);
            Func<string, string> fileOf = k => Path.Combine(dir, DS27Json.Text(DS27Json.AsObj(DS27Json.Get(fl, k), k), "file"));
            Func<string, string> shaOf = k => DS27Json.Text(DS27Json.AsObj(DS27Json.Get(fl, k), k), "sha256");
            var cl = DS27Json.Get(jo, "claws") as System.Collections.IList;
            if (cl == null) throw new InvalidDataException("claws がありません");
            ClawCount = cl.Count;
            ClawIds = new string[ClawCount]; VertOffset = new int[ClawCount]; VertCount = new int[ClawCount];
            for (int i = 0; i < ClawCount; i++)
            {
                var c = DS27Json.AsObj(cl[i], "claw");
                ClawIds[i] = DS27Json.Text(c, "id");
                VertOffset[i] = (int)DS27Json.Num(c, "vert_offset");
                VertCount[i] = (int)DS27Json.Num(c, "vert_count");
            }

            // 頂点のコマの表
            var fb = File.ReadAllBytes(fileOf("frames"));
            if (fb.LongLength != (long)Frames * VertexCount * 12) throw new InvalidDataException("コマの表の大きさが合いません: " + fb.LongLength);
            FramesSha256 = Sha(fb);
            if (verifySha256 && FramesSha256 != shaOf("frames")) throw new InvalidDataException("コマの表の SHA-256 が並びと違います");
            frames = new float[(long)Frames * VertexCount * 3];
            Buffer.BlockCopy(fb, 0, frames, 0, fb.Length);
            fb = null;
            // 三角形と面の種類
            var tb = File.ReadAllBytes(fileOf("tris"));
            var ab = File.ReadAllBytes(fileOf("tri_attr"));
            TrisSha256 = Sha(tb); AttrSha256 = Sha(ab);
            if (verifySha256 && (TrisSha256 != shaOf("tris") || AttrSha256 != shaOf("tri_attr"))) throw new InvalidDataException("三角形か面の種類の SHA-256 が並びと違います");
            if (tb.Length != TriangleCount * 12 || ab.Length != TriangleCount * 4) throw new InvalidDataException("三角形の数が合いません");
            var tris = new int[TriangleCount * 3];
            Buffer.BlockCopy(tb, 0, tris, 0, tb.Length);
            var attr = new ushort[TriangleCount * 2];
            Buffer.BlockCopy(ab, 0, attr, 0, ab.Length);
            var w = new System.Collections.Generic.List<int>();
            var m = new System.Collections.Generic.List<int>();
            for (int t = 0; t < TriangleCount; t++)
            {
                var dst = attr[2 * t + 1] == 1 ? m : w;
                dst.Add(tris[3 * t]); dst.Add(tris[3 * t + 1]); dst.Add(tris[3 * t + 2]);
            }
            WhiteTriangles = w.Count / 3; MizuiroTriangles = m.Count / 3;

            now = new Vector3[VertexCount];
            mesh = new Mesh { name = "DS34 爪の結合メッシュ", hideFlags = HideFlags.DontSave };
            mesh.indexFormat = VertexCount > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            mesh.MarkDynamic();
            FillFrame(0, 0, 0f);
            mesh.SetVertices(now);
            mesh.subMeshCount = 2;
            mesh.SetTriangles(w, 0, false);
            mesh.SetTriangles(m, 1, false);
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            GetComponent<MeshFilter>().sharedMesh = mesh;

            var sh = Shader.Find(ShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            matWhite = new Material(sh) { name = "DS34 爪 白", hideFlags = HideFlags.DontSave, enableInstancing = true };
            matWhite.SetColor("_Colour", white); matWhite.SetFloat("_IdClass", 0f);
            matMizuiro = new Material(sh) { name = "DS34 爪 淡い水色", hideFlags = HideFlags.DontSave, enableInstancing = true };
            matMizuiro.SetColor("_Colour", mizuiro); matMizuiro.SetFloat("_IdClass", 1f);
            var r = GetComponent<MeshRenderer>();
            r.sharedMaterials = new[] { matWhite, matMizuiro };
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            r.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
            AppliedT = 0.0; AppliedFrame = 0.0; AppliedOnGrid = true;
            LoadSeconds = (float)sw.Elapsed.TotalSeconds;
        }

        void FillFrame(int k0, int k1, float s)
        {
            long a = (long)k0 * VertexCount * 3, b = (long)k1 * VertexCount * 3;
            if (k0 == k1 || s <= 0f)
                for (int i = 0; i < VertexCount; i++) now[i] = new Vector3(frames[a + 3 * i], frames[a + 3 * i + 1], frames[a + 3 * i + 2]);
            else
                for (int i = 0; i < VertexCount; i++)
                {
                    long p = a + 3 * i, q = b + 3 * i;
                    now[i] = new Vector3(frames[p] + s * (frames[q] - frames[p]), frames[p + 1] + s * (frames[q + 1] - frames[p + 1]), frames[p + 2] + s * (frames[q + 2] - frames[p + 2]));
                }
        }

        /// <summary>コマの番号 k の位置（t = k/hz）。</summary>
        public static int FrameOf(double t, float hz, int frames) => (int)Math.Max(0, Math.Min(frames - 1, Math.Round(t * hz)));

        /// <summary>体験の時刻 t の爪の頂点を結合メッシュへ入れる。</summary>
        public void ApplyT(double t)
        {
            if (mesh == null) Load();
            double x = Math.Max(0.0, Math.Min(t * Hz, Frames - 1));
            int kr = (int)Math.Round(x);
            if (Math.Abs(x - kr) < 1e-4)
            {
                FillFrame(kr, kr, 0f);
                AppliedFrame = kr; AppliedOnGrid = true;
            }
            else
            {
                int k0 = (int)Math.Floor(x), k1 = Math.Min(k0 + 1, Frames - 1);
                FillFrame(k0, k1, (float)(x - k0));
                AppliedFrame = x; AppliedOnGrid = false;
            }
            mesh.SetVertices(now);
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            AppliedT = t;
        }

        /// <summary>検査用：コマ k の頂点 i（ワールドの m）。</summary>
        public Vector3 FrameVertex(int k, int i)
        {
            long a = ((long)k * VertexCount + i) * 3;
            return new Vector3(frames[a], frames[a + 1], frames[a + 2]);
        }

        /// <summary>今メッシュに入っている頂点の写し。</summary>
        public Vector3[] Current => (Vector3[])now.Clone();

        void Start()
        {
            if (Application.isPlaying) Load();
        }

        void Update()
        {
            if (!Application.isPlaying || !followClockInPlayMode || mesh == null) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c != null) ApplyT(c.Seconds);
        }

        void OnDestroy() { Release(); }

        public void Release()
        {
            if (matWhite != null) { if (Application.isPlaying) Destroy(matWhite); else DestroyImmediate(matWhite); matWhite = null; }
            if (matMizuiro != null) { if (Application.isPlaying) Destroy(matMizuiro); else DestroyImmediate(matMizuiro); matMizuiro = null; }
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); mesh = null; }
            frames = null; now = null;
        }

        static string Sha(byte[] b)
        {
            using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }
    }
}
