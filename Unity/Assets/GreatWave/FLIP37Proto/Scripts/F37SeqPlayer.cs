using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.FLIP37Proto
{
    // FLIP37 組み込みの準備（独立の試作。先生の指示 Q37 の「巻き込みが生じる波が作れるようになったら作品へ組み込む」の下準備）。
    // 流体の水面を変換した並び（Tools/GWWaveGen/flip37/integ_convert.py の index.json、schema GreatWave.F37.seq/1）を再生する。
    // 作品の場面・材質・部品は使わない・変えない。材質は AS05 のシェーダー（変えない）を、この試作の新しい材質の資産で使う（_AS03Src = 1 の静止のメッシュの道）。
    //   .bin：position3・normal3・uv3〜uv6（各 4）の平面の float32、続いて uint32 の三角形（書式 GreatWave.AS03.static_mesh/1 の .bin と同じ並び）。
    // method = sheet（topology fixed。240 行 × 400 列で頂点の番号がコマの間で同じ意味）：コマの間を補間する（位置は Catmull-Rom、法線・属性は線形）。
    // method = frames（topology variable。コマごとの流体の網目）：番号がコマごとに違うので補間できない。その時刻の直前のコマを出す（段々）。
    // seaOnly：frames の網目から主役波の範囲（F が −1 でない頂点＝変換が主役波の網目の近くと決めた頂点、だけでできた三角形）を除き、周りの海として出す（sheet と一緒に使う）。
    [ExecuteAlways]
    public class F37SeqPlayer : MonoBehaviour
    {
        [Tooltip("index.json の絶対パス")] public string indexPath = "";
        public Material material;
        [Tooltip("計算の時刻（秒）")] public float dataTime;
        [Tooltip("sheet のときコマの間を補間する")] public bool interpolate = true;
        [Tooltip("frames の網目から主役波の範囲を除いて周りの海として出す")] public bool seaOnly;
        [Tooltip("全体を下げる（m）。周りの海を主役波の面の少し下に置くため")] public float yOffset;

        [Serializable] public class FrameRec { public float t; public string bin; public int vertices; public int triangles; }
        [Serializable] public class IndexRec { public string schema; public string seq; public string method; public string topology; public float rate_hz; public FrameRec[] frames; }

        class Frame { public Vector3[] p, n; public Vector4[] a, b, c, d; public int[] tri; }

        IndexRec idx;
        string dir;
        Mesh mesh;
        int shownFrame = -1;
        bool trisSet;
        readonly Dictionary<int, Frame> cache = new Dictionary<int, Frame>();
        readonly List<int> lru = new List<int>();
        Vector3[] wp; Vector3[] wn; List<Vector4> wa, wb, wc, wd;

        public IndexRec Index => idx;
        public bool Loaded => idx != null;
        public float T0 => idx.frames[0].t;
        public float T1 => idx.frames[idx.frames.Length - 1].t;
        public double LastSetMs { get; private set; }
        public int LastVertices { get; private set; }

        public void Load()
        {
            idx = JsonUtility.FromJson<IndexRec>(File.ReadAllText(indexPath));
            if (idx == null || idx.schema != "GreatWave.F37.seq/1") throw new InvalidDataException("F37 の並びの書式ではありません: " + indexPath);
            dir = Path.GetDirectoryName(indexPath);
            mesh = new Mesh { name = "F37 " + idx.seq + " " + idx.method + (seaOnly ? " sea" : ""), hideFlags = HideFlags.DontSave, indexFormat = IndexFormat.UInt32 };
            mesh.MarkDynamic();
            var mf = GetComponent<MeshFilter>(); if (mf == null) mf = gameObject.AddComponent<MeshFilter>();
            var mr = GetComponent<MeshRenderer>(); if (mr == null) mr = gameObject.AddComponent<MeshRenderer>();
            mf.sharedMesh = mesh;
            if (material != null) mr.sharedMaterial = material;
            mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off; mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            transform.SetPositionAndRotation(new Vector3(0, -yOffset, 0), Quaternion.identity);
            transform.localScale = Vector3.one;
            cache.Clear(); lru.Clear(); shownFrame = -1; trisSet = false;
        }

        Frame Get(int k)
        {
            if (cache.TryGetValue(k, out var f)) { lru.Remove(k); lru.Add(k); return f; }
            var fr = idx.frames[k];
            var bytes = File.ReadAllBytes(Path.Combine(dir, fr.bin));
            int n = fr.vertices, m = fr.triangles;
            long need = (long)n * 22 * 4 + (long)m * 12;
            if (bytes.LongLength != need) throw new InvalidDataException("大きさが合いません: " + fr.bin + " " + bytes.LongLength + " / " + need);
            var fl = new float[n * 22];
            Buffer.BlockCopy(bytes, 0, fl, 0, n * 22 * 4);
            f = new Frame { p = new Vector3[n], n = new Vector3[n], a = new Vector4[n], b = new Vector4[n], c = new Vector4[n], d = new Vector4[n], tri = new int[m * 3] };
            int o = 0;
            for (int i = 0; i < n; i++) f.p[i] = new Vector3(fl[o + 3 * i], fl[o + 3 * i + 1], fl[o + 3 * i + 2]);
            o += 3 * n;
            for (int i = 0; i < n; i++) f.n[i] = new Vector3(fl[o + 3 * i], fl[o + 3 * i + 1], fl[o + 3 * i + 2]);
            o += 3 * n;
            foreach (var arr in new[] { f.a, f.b, f.c, f.d })
            {
                for (int i = 0; i < n; i++) arr[i] = new Vector4(fl[o + 4 * i], fl[o + 4 * i + 1], fl[o + 4 * i + 2], fl[o + 4 * i + 3]);
                o += 4 * n;
            }
            Buffer.BlockCopy(bytes, n * 22 * 4, f.tri, 0, m * 12);
            if (seaOnly)
            {
                // 主役波の範囲（F ≠ −1）の頂点だけでできた三角形を除く
                var keep = new List<int>(f.tri.Length);
                for (int t = 0; t < m; t++)
                {
                    int i0 = f.tri[3 * t], i1 = f.tri[3 * t + 1], i2 = f.tri[3 * t + 2];
                    if (Hero(f.a[i0]) && Hero(f.a[i1]) && Hero(f.a[i2])) continue;
                    keep.Add(i0); keep.Add(i1); keep.Add(i2);
                }
                f.tri = keep.ToArray();
                for (int i = 0; i < n; i++) { var v = f.a[i]; v.x = -1f; f.a[i] = v; var w = f.c[i]; w.z = -5f; f.c[i] = w; }
            }
            cache[k] = f; lru.Add(k);
            while (lru.Count > 6) { cache.Remove(lru[0]); lru.RemoveAt(0); }
            return f;
        }

        static bool Hero(Vector4 a) => Mathf.Abs(a.x + 1f) > 1e-4f;

        public void SetTime(float t)
        {
            if (idx == null) Load();
            var sw = System.Diagnostics.Stopwatch.StartNew();
            dataTime = t;
            var fr = idx.frames;
            int nfr = fr.Length;
            int k = 0;
            while (k + 1 < nfr && fr[k + 1].t <= t) k++;
            bool fixedTopo = idx.topology == "fixed";
            if (!fixedTopo || !interpolate || nfr < 2)
            {
                if (k != shownFrame)
                {
                    var f = Get(k);
                    mesh.Clear();
                    mesh.vertices = f.p; mesh.normals = f.n;
                    mesh.SetUVs(3, f.a); mesh.SetUVs(4, f.b); mesh.SetUVs(5, f.c); mesh.SetUVs(6, f.d);
                    mesh.SetIndices(f.tri, MeshTopology.Triangles, 0, true);
                    shownFrame = k;
                    LastVertices = f.p.Length;
                }
            }
            else
            {
                int k1 = Mathf.Min(k + 1, nfr - 1);
                float u = k1 == k ? 0f : Mathf.Clamp01((t - fr[k].t) / (fr[k1].t - fr[k].t));
                var f0 = Get(Mathf.Max(k - 1, 0)); var f1 = Get(k); var f2 = Get(k1); var f3 = Get(Mathf.Min(k + 2, nfr - 1));
                int n = f1.p.Length;
                if (wp == null || wp.Length != n)
                {
                    wp = new Vector3[n]; wn = new Vector3[n];
                    wa = new List<Vector4>(new Vector4[n]); wb = new List<Vector4>(new Vector4[n]); wc = new List<Vector4>(new Vector4[n]); wd = new List<Vector4>(new Vector4[n]);
                    trisSet = false;
                }
                float u2 = u * u, u3 = u2 * u;
                // Catmull-Rom（一様の間隔）
                float c0 = -0.5f * u3 + u2 - 0.5f * u, c1 = 1.5f * u3 - 2.5f * u2 + 1f, c2 = -1.5f * u3 + 2f * u2 + 0.5f * u, c3 = 0.5f * u3 - 0.5f * u2;
                for (int i = 0; i < n; i++)
                {
                    wp[i] = c0 * f0.p[i] + c1 * f1.p[i] + c2 * f2.p[i] + c3 * f3.p[i];
                    wn[i] = Vector3.Normalize(Vector3.Lerp(f1.n[i], f2.n[i], u));
                    wa[i] = Vector4.Lerp(f1.a[i], f2.a[i], u); wb[i] = Vector4.Lerp(f1.b[i], f2.b[i], u);
                    wc[i] = Vector4.Lerp(f1.c[i], f2.c[i], u);
                    var dd = Vector4.Lerp(f1.d[i], f2.d[i], u); dd.w = u < 0.5f ? f1.d[i].w : f2.d[i].w; wd[i] = dd;   // whiteOn は 0/1 のまま
                }
                if (!trisSet) { mesh.Clear(); mesh.vertices = wp; mesh.SetIndices(f1.tri, MeshTopology.Triangles, 0, false); trisSet = true; }
                else mesh.vertices = wp;
                mesh.normals = wn;
                mesh.SetUVs(3, wa); mesh.SetUVs(4, wb); mesh.SetUVs(5, wc); mesh.SetUVs(6, wd);
                mesh.RecalculateBounds();
                shownFrame = -1;
                LastVertices = n;
            }
            LastSetMs = sw.Elapsed.TotalMilliseconds;
        }

        void OnDestroy()
        {
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); }
        }
    }
}
