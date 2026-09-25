using System;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst
{
    // 編号24：gw_wavegen v0 が書いた全フレームの頂点位置（.gwb）を読み、固定位相のメッシュを CPU で更新する。
    // v0 の仮再生で、keypose テクスチャと SPI シェーダーによる再生（CP1 前に接続）とは別物。
    public class AF24WavePlayer : MonoBehaviour
    {
        [Tooltip("Unity プロジェクトからの相対パス（Git 対象外の /Unity/Build/ の下）")]
        public string dataPath = "Build/ArtFirst/24/wave/wave_v0.gwb";
        [Tooltip("再生時に 0〜17 s を繰り返す")]
        public bool playInPlayMode = true;

        [NonSerialized] public int nu, nv, frameCount, tStarFrame, triangleCount;
        [NonSerialized] public float fps;
        public int CurrentFrame { get; private set; } = -1;
        public Mesh Mesh => mesh;

        Mesh mesh;
        FileStream stream;
        long framesOffset;
        byte[] buffer;
        float[] floats;
        Vector3[] vertices;

        public string FullDataPath => Path.GetFullPath(dataPath);

        public Mesh EnsureLoaded()
        {
            if (mesh != null) return mesh;
            stream = new FileStream(FullDataPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            var reader = new BinaryReader(stream);
            var magic = new string(reader.ReadChars(4));
            if (magic != "GWW0") throw new InvalidDataException("gw_wavegen の .gwb ではありません: " + magic);
            int version = reader.ReadInt32();
            if (version != 1) throw new InvalidDataException("未対応の .gwb 版: " + version);
            nu = reader.ReadInt32(); nv = reader.ReadInt32(); frameCount = reader.ReadInt32();
            fps = reader.ReadSingle(); tStarFrame = reader.ReadInt32(); triangleCount = reader.ReadInt32();
            int n = nu * nv;
            var uv = ReadVector2(reader, n);
            var uv2 = ReadVector2(reader, n);
            var tris = new int[triangleCount * 3];
            var tb = reader.ReadBytes(tris.Length * 4);
            Buffer.BlockCopy(tb, 0, tris, 0, tb.Length);
            framesOffset = stream.Position;
            if (stream.Length != framesOffset + (long)frameCount * n * 12)
                throw new InvalidDataException("フレーム数と容量が一致しません。");
            buffer = new byte[n * 12];
            floats = new float[n * 3];
            vertices = new Vector3[n];
            mesh = new Mesh { name = "AF24 主役波 v0（固定位相）", indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
            mesh.MarkDynamic();
            ReadFrame(0);
            mesh.vertices = vertices;
            mesh.uv = uv;
            mesh.uv2 = uv2;
            mesh.SetTriangles(tris, 0, true);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            CurrentFrame = 0;
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

        void ReadFrame(int frame)
        {
            int n = nu * nv;
            stream.Position = framesOffset + (long)frame * n * 12;
            int read = 0;
            while (read < buffer.Length)
            {
                int r = stream.Read(buffer, read, buffer.Length - read);
                if (r <= 0) throw new EndOfStreamException("フレームを読み切れません: " + frame);
                read += r;
            }
            Buffer.BlockCopy(buffer, 0, floats, 0, buffer.Length);
            for (int i = 0; i < n; i++) vertices[i] = new Vector3(floats[3 * i], floats[3 * i + 1], floats[3 * i + 2]);
        }

        /// <summary>フレーム番号（30 Hz、0 始まり）の頂点位置へ更新する。頂点数・添字は変えない。</summary>
        public void SetFrame(int frame)
        {
            EnsureLoaded();
            frame = Mathf.Clamp(frame, 0, frameCount - 1);
            if (frame == CurrentFrame) return;
            ReadFrame(frame);
            mesh.vertices = vertices;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            CurrentFrame = frame;
        }

        public void SetTime(float seconds) => SetFrame(Mathf.RoundToInt(seconds * fps));

        public Vector3[] CurrentVertices => vertices;

        void Update()
        {
            if (!Application.isPlaying || !playInPlayMode) return;
            EnsureLoaded();
            SetTime(Time.time % (frameCount / fps));
        }

        void OnDestroy()
        {
            stream?.Dispose();
            stream = null;
            if (mesh != null)
            {
                if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh);
            }
        }
    }
}
