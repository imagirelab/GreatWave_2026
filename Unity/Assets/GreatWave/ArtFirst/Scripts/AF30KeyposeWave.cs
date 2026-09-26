using System;
using System.IO;
using UnityEngine;

namespace GreatWave.ArtFirst
{
    // 番号30：形成の keypose を GPU で再生する（番号24 の CPU のメッシュ更新 AF24WavePlayer に代わるもの）。
    // keypose（Tools/GWWaveGen/af30_formation.py が Build/ArtFirst/30/keypose/ に書く）を 2 つの Texture2DArray にして大域の値で渡し、
    // 時刻（GWClock）から補間に使う 4 層と Catmull-Rom の重みを CPU で決めて、頂点シェーダー（AF30Keypose.cginc）に渡す。
    // メッシュ（固定位相の格子、添字・UV・UV2）は同じ GameObject の AF26KStarMesh が K* の .gwb から読み、UV3 は AF28NprWave が付ける。
    // 頂点バッファは K* のまま変えない（位置はシェーダーが keypose から読む）。外接箱だけを全 key の外接箱にする（視錐台の判定のため）。
    [RequireComponent(typeof(AF26KStarMesh))]
    [DefaultExecutionOrder(100)]
    public class AF30KeyposeWave : MonoBehaviour
    {
        [Tooltip("keypose のフォルダー（Unity プロジェクトからの相対パス、Git 対象外の /Unity/Build/ の下）")]
        public string keyposeDir = "Build/ArtFirst/30/keypose";
        [Tooltip("時刻を読む時計（空なら GWClock.Active）")]
        public GWClock clock;

        [Serializable]
        public class Meta
        {
            public int nu, nv, layers, t_star_layer;
            public float t_star_s, end_s;
            public float[] key_times_s, bbox_min, bbox_size;
            public string position_file, normal_file, position_sha256, normal_sha256, index_sha256, kstar_gwb_sha256, rig_sha256;
            public long position_bytes, normal_bytes;
        }

        Meta meta;
        Texture2DArray posTex, nrmTex;
        double[] times;
        public Meta KeyMeta => meta;
        public Texture2DArray PositionTexture => posTex;
        public Texture2DArray NormalTexture => nrmTex;
        public int[] Slices { get; } = new int[4];
        public float[] WeightsNow { get; } = new float[4];
        public float AppliedSeconds { get; private set; } = float.NaN;

        public static readonly int PosTexId = Shader.PropertyToID("_AF30PosTex"), NrmTexId = Shader.PropertyToID("_AF30NrmTex"),
            BBoxMinId = Shader.PropertyToID("_AF30BBoxMin"), BBoxSizeId = Shader.PropertyToID("_AF30BBoxSize"),
            SlicesId = Shader.PropertyToID("_AF30Slices"), WeightsId = Shader.PropertyToID("_AF30Weights"),
            GridNUId = Shader.PropertyToID("_AF30GridNU"), EnabledId = Shader.PropertyToID("_AF30Enabled");

        public string FullDir => Path.GetFullPath(keyposeDir);

        public void EnsureLoaded()
        {
            if (meta != null) return;
            var m = JsonUtility.FromJson<Meta>(File.ReadAllText(Path.Combine(FullDir, "af30_keypose.json")));
            if (m == null || m.layers < 2 || m.key_times_s == null || m.key_times_s.Length != m.layers)
                throw new InvalidDataException("af30_keypose.json を読めません。");
            var km = GetComponent<AF26KStarMesh>();
            var mesh = km.EnsureLoaded();
            if (mesh.vertexCount != m.nu * m.nv || km.nu != m.nu || km.nv != m.nv)
                throw new InvalidDataException("keypose の格子と K* のメッシュが合いません: " + mesh.vertexCount);
            if (!SystemInfo.SupportsTextureFormat(TextureFormat.RGBA64) || !SystemInfo.SupportsTextureFormat(TextureFormat.RG32))
                throw new NotSupportedException("RGBA64 / RG32 のテクスチャが使えません。");
            posTex = LoadArray(Path.Combine(FullDir, m.position_file), m, TextureFormat.RGBA64, 8, "AF30 keypose 位置 RGBA16");
            nrmTex = LoadArray(Path.Combine(FullDir, m.normal_file), m, TextureFormat.RG32, 4, "AF30 keypose 法線 RG16");
            times = Array.ConvertAll(m.key_times_s, v => (double)v);
            var lo = new Vector3(m.bbox_min[0], m.bbox_min[1], m.bbox_min[2]);
            var sz = new Vector3(m.bbox_size[0], m.bbox_size[1], m.bbox_size[2]);
            mesh.bounds = new Bounds(lo + 0.5f * sz, sz);
            meta = m;
            Shader.SetGlobalTexture(PosTexId, posTex);
            Shader.SetGlobalTexture(NrmTexId, nrmTex);
            Shader.SetGlobalVector(BBoxMinId, lo);
            Shader.SetGlobalVector(BBoxSizeId, sz);
            Shader.SetGlobalFloat(GridNUId, m.nu);
            Shader.SetGlobalFloat(EnabledId, 1f);
        }

        static Texture2DArray LoadArray(string path, Meta m, TextureFormat fmt, int bytesPerTexel, string name)
        {
            var bytes = File.ReadAllBytes(path);
            long layerBytes = (long)m.nu * m.nv * bytesPerTexel;
            if (bytes.LongLength != layerBytes * m.layers) throw new InvalidDataException("keypose の容量が違います: " + path + " " + bytes.LongLength);
            var tex = new Texture2DArray(m.nu, m.nv, m.layers, fmt, false, true)
            {
                name = name, filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, anisoLevel = 0, hideFlags = HideFlags.DontSave
            };
            for (int l = 0; l < m.layers; l++) tex.SetPixelData(bytes, 0, l, (int)(layerBytes * l));
            tex.Apply(false, true);
            return tex;
        }

        /// <summary>時刻 t の補間に使う 4 つの層と重み（af30_formation.py の cr_weights と同じ式）。</summary>
        public static void Weights(double[] tk, double t, int[] idx, float[] w)
        {
            int n = tk.Length;
            if (t <= tk[0]) { idx[0] = idx[1] = idx[2] = idx[3] = 0; w[0] = 0; w[1] = 1; w[2] = 0; w[3] = 0; return; }
            if (t >= tk[n - 1]) { idx[0] = idx[1] = idx[2] = idx[3] = n - 1; w[0] = 0; w[1] = 1; w[2] = 0; w[3] = 0; return; }
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
        }

        /// <summary>時刻 t（秒）の keypose をシェーダーへ渡す（大域の値）。</summary>
        public void ApplyTime(float t)
        {
            EnsureLoaded();
            Weights(times, t, Slices, WeightsNow);
            Shader.SetGlobalVector(SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            Shader.SetGlobalVector(WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            Shader.SetGlobalFloat(EnabledId, 1f);
            AppliedSeconds = t;
        }

        /// <summary>コンピュートシェーダー（AF30KeyposeCapture）へ同じ値を渡す。</summary>
        public void BindCompute(ComputeShader cs, int kernel)
        {
            EnsureLoaded();
            cs.SetTexture(kernel, PosTexId, posTex);
            cs.SetTexture(kernel, NrmTexId, nrmTex);
            cs.SetVector(BBoxMinId, new Vector4(meta.bbox_min[0], meta.bbox_min[1], meta.bbox_min[2], 0));
            cs.SetVector(BBoxSizeId, new Vector4(meta.bbox_size[0], meta.bbox_size[1], meta.bbox_size[2], 0));
            cs.SetVector(SlicesId, new Vector4(Slices[0], Slices[1], Slices[2], Slices[3]));
            cs.SetVector(WeightsId, new Vector4(WeightsNow[0], WeightsNow[1], WeightsNow[2], WeightsNow[3]));
            cs.SetFloat(GridNUId, meta.nu);
            cs.SetFloat(EnabledId, 1f);
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c != null) ApplyTime(c.Seconds);
        }

        void OnDestroy()
        {
            Shader.SetGlobalFloat(EnabledId, 0f);
            foreach (var t in new Texture[] { posTex, nrmTex })
            {
                if (t == null) continue;
                if (Application.isPlaying) Destroy(t); else DestroyImmediate(t);
            }
        }
    }
}
