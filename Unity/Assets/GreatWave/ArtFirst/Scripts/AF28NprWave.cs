using System;
using System.IO;
using UnityEngine;

namespace GreatWave.ArtFirst
{
    // 番号28：主役波（K*）に NPR シェーダー v1 の色区テクスチャをつなぐ。
    // 色区テクスチャは AF28ProjectionBaker（計画の GWProjectionBaker）が焼いた符号付き距離（4096²、RGBA32 の生データ、線形、
    // 下の行 = v′ 0 から）で、Git 対象外の /Unity/Build/ に置く。シーンには保存せず、読み込んで MaterialPropertyBlock で渡す。
    // テクスチャの座標は焼き込み用の UV（UV3）。UV0 を列ごと・行ごとに単調に引き伸ばした (u′, v′) で、固定位相の格子の添字（行 × nu + 列）
    // だけで決まる。表（列ごとの u′、行ごとの v′）はベイクのときに af28_uvwarp_<key>.json へ書いたものを読む。
    // メッシュは同じ GameObject の AF26KStarMesh（番号26）が読む。外殻線 v0 の子（outline）にも同じメッシュを渡す。
    [RequireComponent(typeof(AF26KStarMesh))]
    public class AF28NprWave : MonoBehaviour
    {
        [Tooltip("Unity プロジェクトからの相対パス（Git 対象外の /Unity/Build/ の下）")]
        public string sdfPath = "Build/ArtFirst/28/bake/af28_uvsdf_a45.bin";
        [Tooltip("焼き込み用 UV（UV3）の表。Unity プロジェクトからの相対パス")]
        public string warpPath = "Build/ArtFirst/28/bake/af28_uvwarp_a45.json";
        public int size = 4096;
        [Tooltip("外殻線 v0 の描画（子の MeshRenderer）")]
        public MeshRenderer outline;

        [Serializable] public class Warp { public string key; public int nu, nv; public float[] uWarp, vWarp; }

        Texture2D tex;
        MaterialPropertyBlock block;
        public Texture2D SdfTexture => tex;
        public string FullSdfPath => Path.GetFullPath(sdfPath);

        // UV3（TEXCOORD2）を格子の添字から付ける。u′ は列だけ、v′ は行だけで決まる。
        public static void ApplyWarp(Mesh mesh, int nu, int nv, float[] uWarp, float[] vWarp)
        {
            if (uWarp == null || vWarp == null || uWarp.Length != nu || vWarp.Length != nv || mesh.vertexCount != nu * nv)
                throw new InvalidDataException("焼き込み用 UV の表の大きさが格子と合いません。");
            var uv3 = new Vector2[nu * nv];
            for (int r = 0; r < nv; r++)
                for (int c = 0; c < nu; c++) uv3[r * nu + c] = new Vector2(uWarp[c], vWarp[r]);
            mesh.SetUVs(2, uv3);
        }

        public Mesh EnsureLoaded()
        {
            var km = GetComponent<AF26KStarMesh>();
            var mesh = km.EnsureLoaded();
            var warp = JsonUtility.FromJson<Warp>(File.ReadAllText(Path.GetFullPath(warpPath)));
            ApplyWarp(mesh, km.nu, km.nv, warp.uWarp, warp.vWarp);
            if (outline != null)
            {
                var f = outline.GetComponent<MeshFilter>();
                if (f != null) f.sharedMesh = mesh;
            }
            if (tex == null)
            {
                var bytes = File.ReadAllBytes(FullSdfPath);
                if (bytes.Length != size * size * 4) throw new InvalidDataException("色区テクスチャの容量が違います: " + bytes.Length);
                tex = new Texture2D(size, size, TextureFormat.RGBA32, false, true)
                {
                    name = "AF28 色区の符号付き距離 " + Path.GetFileNameWithoutExtension(sdfPath),
                    wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 0, hideFlags = HideFlags.DontSave
                };
                tex.LoadRawTextureData(bytes);
                tex.Apply(false, true);
            }
            if (block == null) block = new MaterialPropertyBlock();
            var r = GetComponent<Renderer>();
            r.GetPropertyBlock(block);
            block.SetTexture("_SdfTex", tex);
            r.SetPropertyBlock(block);
            return mesh;
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void OnDestroy()
        {
            if (tex != null)
            {
                if (Application.isPlaying) Destroy(tex); else DestroyImmediate(tex);
            }
        }
    }
}
