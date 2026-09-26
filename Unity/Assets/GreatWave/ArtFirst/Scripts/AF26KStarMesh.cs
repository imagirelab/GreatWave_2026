using System;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst
{
    // 番号26：gw_wavegen v1 が書いた K*（主役波の終態、1 フレームの GWW0 形式 .gwb）を読み、固定位相のメッシュにする。
    // 書式は番号24 の wave_v0.gwb と同じ（Tools/GWWaveGen/gw_wavegen_v1.py の write_gwb）。メッシュはシーンに保存しない。
    public class AF26KStarMesh : MonoBehaviour
    {
        [Tooltip("Unity プロジェクトからの相対パス（Git 対象外の /Unity/Build/ の下）")]
        public string dataPath = "Build/ArtFirst/26/kstar/kstar_a45.gwb";

        [NonSerialized] public int nu, nv, triangleCount;
        public Mesh Mesh => mesh;
        Mesh mesh;

        public string FullDataPath => Path.GetFullPath(dataPath);

        public Mesh EnsureLoaded()
        {
            if (mesh != null) return mesh;
            using (var stream = new FileStream(FullDataPath, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var reader = new BinaryReader(stream))
            {
                var magic = new string(reader.ReadChars(4));
                if (magic != "GWW0") throw new InvalidDataException("gw_wavegen の .gwb ではありません: " + magic);
                int version = reader.ReadInt32();
                if (version != 1) throw new InvalidDataException("未対応の .gwb 版: " + version);
                nu = reader.ReadInt32(); nv = reader.ReadInt32();
                int frames = reader.ReadInt32();
                reader.ReadSingle(); reader.ReadInt32();
                triangleCount = reader.ReadInt32();
                if (frames != 1) throw new InvalidDataException("K* の .gwb は 1 フレームのはずです: " + frames);
                int n = nu * nv;
                var uv = ReadVector2(reader, n);
                var uv2 = ReadVector2(reader, n);
                var tris = new int[triangleCount * 3];
                var tb = reader.ReadBytes(tris.Length * 4);
                Buffer.BlockCopy(tb, 0, tris, 0, tb.Length);
                var vb = reader.ReadBytes(n * 12);
                if (vb.Length != n * 12 || stream.Position != stream.Length) throw new InvalidDataException("容量が一致しません。");
                var f = new float[n * 3];
                Buffer.BlockCopy(vb, 0, f, 0, vb.Length);
                var vertices = new Vector3[n];
                for (int i = 0; i < n; i++) vertices[i] = new Vector3(f[3 * i], f[3 * i + 1], f[3 * i + 2]);
                mesh = new Mesh { name = "AF26 K* " + Path.GetFileNameWithoutExtension(dataPath), indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
                mesh.vertices = vertices;
                mesh.uv = uv;
                mesh.uv2 = uv2;
                mesh.SetTriangles(tris, 0, true);
                mesh.RecalculateNormals();
                mesh.RecalculateBounds();
            }
            var filter = GetComponent<MeshFilter>();
            if (filter != null) filter.sharedMesh = mesh;
            return mesh;
        }

        static Vector2[] ReadVector2(BinaryReader reader, int n)
        {
            var b = reader.ReadBytes(n * 8);
            var f = new float[n * 2];
            Buffer.BlockCopy(b, 0, f, 0, b.Length);
            var v = new Vector2[n];
            for (int i = 0; i < n; i++) v[i] = new Vector2(f[2 * i], f[2 * i + 1]);
            return v;
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void OnDestroy()
        {
            if (mesh != null)
            {
                if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh);
            }
        }
    }
}
