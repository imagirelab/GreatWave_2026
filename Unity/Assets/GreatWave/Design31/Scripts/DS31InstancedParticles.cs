using System;
using System.IO;
using System.Security.Cryptography;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design31
{
    // 設計31：光を使わない不透明の小球の instancing（飛沫 v0 と、確認用の印）。
    // 粒子の枠の書式 GreatWave.DS31.particles/1（Tools/GWWaveGen/ds31/ds31_white.py・ds31_spray_convert.py が書く）：
    //   JSON（frames・hz・t0・count・file・sha256・colour）＋ float32 のコマ × 数 × 4（x, y, z, 半径。ワールドの m。半径 0 は描かない）。
    //   コマ k は体験の時刻 t = t0 + k/hz（t* = 12 s の後は t* の姿のまま）。
    // 時刻：採取（DS31Render）は ApplyT(t) を DS30SinglePlayback.Seek と同じ t で呼ぶ。Play モードでは GWClock の秒（DS30SinglePlayback が書く）を読む。
    // コマの間は線形に補間する（両方のコマで生きている粒子だけ。片方で半径 0 なら近い方のコマ）。
    // 描画：球の網（正二十面体の分割）1 つを、GraphicsBuffer（float4 × 数）を読むシェーダー DS31 Spray Unlit で 1 回の DrawMeshInstancedProcedural で描く。
    //   採取ではカメラの CommandBuffer（AddTo）、Play モードでは Graphics.DrawMeshInstancedProcedural。
    [DefaultExecutionOrder(60)]   // DS30SinglePlayback（50）が時計を書いた後に読む
    public class DS31InstancedParticles : MonoBehaviour
    {
        [Tooltip("粒子の枠の JSON（Unity プロジェクトからの相対パスか絶対パス）")]
        public string dataPath = "";
        [Tooltip("平塗りの色（空なら JSON の colour）")]
        public Color colour = new Color(0.97255f, 0.95294f, 0.87451f, 1f);
        public bool colourFromJson = true;
        [Tooltip("球の網の分割の段数（0 = 正二十面体 20 三角形、1 = 80、2 = 320）")]
        public int subdivisions = 1;
        public GWClock clock;
        public bool drawInPlayMode = true;
        public bool verifySha256 = true;

        public int Count { get; private set; }
        public int Frames { get; private set; }
        public float Hz { get; private set; }
        public float T0 { get; private set; }
        public int AliveNow { get; private set; }
        public int MaxAlive { get; private set; }
        public double AppliedT { get; private set; } = double.NaN;
        public string DataSha256 { get; private set; } = "";
        public int SphereTriangles => sphere == null ? 0 : sphere.triangles.Length / 3;
        public long GpuBytes => buf == null ? 0 : (long)buf.count * buf.stride;
        public bool Loaded => buf != null;

        Mesh sphere;
        Material mat;
        GraphicsBuffer buf;
        float[] data;      // frames × count × 4
        Vector4[] now;
        static readonly int PId = Shader.PropertyToID("_DS31P"), ColId = Shader.PropertyToID("_Colour");
        public const string ShaderName = "GreatWave/Design31/DS31 Spray Unlit";

        public void Load()
        {
            if (buf != null) return;
            var jp = Path.GetFullPath(dataPath);
            var jo = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(jp)), "particles");
            if (DS27Json.Text(jo, "schema") != "GreatWave.DS31.particles/1") throw new InvalidDataException("粒子の枠の書式ではありません: " + jp);
            Frames = (int)DS27Json.Num(jo, "frames");
            Count = (int)DS27Json.Num(jo, "count");
            Hz = (float)DS27Json.Num(jo, "hz");
            T0 = (float)DS27Json.Num(jo, "t0");
            var bp = Path.Combine(Path.GetDirectoryName(jp), DS27Json.Text(jo, "file"));
            var bytes = File.ReadAllBytes(bp);
            if (bytes.Length != (long)Frames * Count * 16) throw new InvalidDataException("粒子の枠の大きさが合いません: " + bytes.Length);
            using (var sh = SHA256.Create()) DataSha256 = BitConverter.ToString(sh.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
            if (verifySha256 && DS27Json.Has(jo, "sha256") && DS27Json.Text(jo, "sha256") != DataSha256) throw new InvalidDataException("粒子の枠の SHA-256 が JSON と違います: " + bp);
            data = new float[Frames * Count * 4];
            Buffer.BlockCopy(bytes, 0, data, 0, bytes.Length);
            if (colourFromJson && DS27Json.Has(jo, "colour"))
            {
                var c = DS27Json.Nums(DS27Json.Get(jo, "colour"), "colour");
                colour = new Color((float)c[0], (float)c[1], (float)c[2], 1f);
            }
            MaxAlive = 0;
            for (int k = 0; k < Frames; k++)
            {
                int a = 0;
                for (int i = 0; i < Count; i++) if (data[(k * Count + i) * 4 + 3] > 0f) a++;
                MaxAlive = Math.Max(MaxAlive, a);
            }
            sphere = IcoSphere(subdivisions);
            var shader = Shader.Find(ShaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            mat = new Material(shader) { name = "DS31 粒子 " + name, hideFlags = HideFlags.DontSave, enableInstancing = true };
            mat.SetColor(ColId, colour);
            buf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, Math.Max(Count, 1), 16);
            now = new Vector4[Math.Max(Count, 1)];
            mat.SetBuffer(PId, buf);
            ApplyT(0.0);
        }

        /// <summary>体験の時刻 t の粒子を GPU へ送る。</summary>
        public void ApplyT(double t)
        {
            if (buf == null) Load();
            double x = (t - T0) * Hz;
            x = Math.Max(0.0, Math.Min(x, Frames - 1));
            int k0 = (int)Math.Floor(x);
            int k1 = Math.Min(k0 + 1, Frames - 1);
            float s = (float)(x - k0);
            int alive = 0;
            for (int i = 0; i < Count; i++)
            {
                int a = (k0 * Count + i) * 4, b = (k1 * Count + i) * 4;
                float ra = data[a + 3], rb = data[b + 3];
                Vector4 v;
                if (s <= 1e-6f || k0 == k1) v = new Vector4(data[a], data[a + 1], data[a + 2], ra);
                else if (ra > 0f && rb > 0f)
                    v = new Vector4(data[a] + s * (data[b] - data[a]), data[a + 1] + s * (data[b + 1] - data[a + 1]), data[a + 2] + s * (data[b + 2] - data[a + 2]), ra + s * (rb - ra));
                else v = s < 0.5f ? new Vector4(data[a], data[a + 1], data[a + 2], ra) : new Vector4(data[b], data[b + 1], data[b + 2], rb);
                now[i] = v;
                if (v.w > 0f) alive++;
            }
            buf.SetData(now);
            AliveNow = alive;
            AppliedT = t;
        }

        /// <summary>今のコマの粒子（x, y, z, 半径）の写し。</summary>
        public Vector4[] Current => (Vector4[])now.Clone();

        public void AddTo(CommandBuffer cb)
        {
            if (buf == null) Load();
            if (Count > 0) cb.DrawMeshInstancedProcedural(sphere, 0, mat, 0, Count);
        }

        void Start()
        {
            if (Application.isPlaying) Load();
        }

        void Update()
        {
            if (!Application.isPlaying || !drawInPlayMode || buf == null) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c != null) ApplyT(c.Seconds);
            if (Count > 0)
                Graphics.DrawMeshInstancedProcedural(sphere, 0, mat, new Bounds(Vector3.zero, Vector3.one * 2000f), Count, null, ShadowCastingMode.Off, false, gameObject.layer);
        }

        void OnDestroy() { Release(); }

        public void Release()
        {
            buf?.Release(); buf = null;
            if (mat != null) { if (Application.isPlaying) Destroy(mat); else DestroyImmediate(mat); mat = null; }
            if (sphere != null) { if (Application.isPlaying) Destroy(sphere); else DestroyImmediate(sphere); sphere = null; }
        }

        // 単位の球（正二十面体を分割して球へ押し出す）
        public static Mesh IcoSphere(int sub)
        {
            float t = (1f + Mathf.Sqrt(5f)) / 2f;
            var v = new System.Collections.Generic.List<Vector3> {
                new Vector3(-1, t, 0), new Vector3(1, t, 0), new Vector3(-1, -t, 0), new Vector3(1, -t, 0),
                new Vector3(0, -1, t), new Vector3(0, 1, t), new Vector3(0, -1, -t), new Vector3(0, 1, -t),
                new Vector3(t, 0, -1), new Vector3(t, 0, 1), new Vector3(-t, 0, -1), new Vector3(-t, 0, 1) };
            for (int i = 0; i < v.Count; i++) v[i] = v[i].normalized;
            var f = new System.Collections.Generic.List<int> {
                0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11, 1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
                3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9, 4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1 };
            for (int s = 0; s < sub; s++)
            {
                var mid = new System.Collections.Generic.Dictionary<long, int>();
                Func<int, int, int> M = (a, b) =>
                {
                    long key = a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
                    if (mid.TryGetValue(key, out int r)) return r;
                    v.Add(((v[a] + v[b]) * 0.5f).normalized);
                    mid[key] = v.Count - 1;
                    return v.Count - 1;
                };
                var nf = new System.Collections.Generic.List<int>();
                for (int i = 0; i < f.Count; i += 3)
                {
                    int a = f[i], b = f[i + 1], c = f[i + 2];
                    int ab = M(a, b), bc = M(b, c), ca = M(c, a);
                    nf.AddRange(new[] { a, ab, ca, b, bc, ab, c, ca, bc, ab, bc, ca });
                }
                f = nf;
            }
            // Unity は時計回りが表。上の並びは反時計回り（外向き）なので裏返す
            for (int i = 0; i < f.Count; i += 3) { int tmp = f[i + 1]; f[i + 1] = f[i + 2]; f[i + 2] = tmp; }
            var m = new Mesh { name = "DS31 球 " + sub, hideFlags = HideFlags.DontSave };
            m.SetVertices(v);
            m.SetTriangles(f, 0);
            m.RecalculateBounds();
            m.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            return m;
        }
    }
}
