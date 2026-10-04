using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using GreatWave.Design27;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtSample03
{
    // 美術の見本03（Q31）：静止のメッシュ（書式 GreatWave.AS03.static_mesh/1、Build/Polish/sample03/shared/README）を読み、
    // ワールドの座標のまま Mesh にして、同じ物の MeshRenderer に AS03 の材質を付ける。
    //   <名前>.json：vertices・triangles・channels（[名前, 成分の数] の並び）・bin・sha256
    //   <名前>.bin：channels の順に、チャンネルごとに N × 成分 の float32（平面の並び）、続いて M × 3 の uint32（三角形）
    //   チャンネル：position(3)・normal(3)・tangent(4)・uv3(4)・uv4(4)・uv5(4)・uv6(4)（uvK は TEXCOORDK）
    // 主役波の彫りの面（surf_relief.py）と、冠・指（B1）に使う。原画カメラの投影は使わない。オブジェクトの変換は単位のまま置く。
    [ExecuteAlways]
    public class AS03StaticMesh : MonoBehaviour
    {
        [Tooltip("静止のメッシュの .json（Unity プロジェクトからの相対パスか絶対パス）")] public string jsonPath = "";
        [Tooltip("AS03 の材質")] public Material material;
        [Tooltip("SHA-256 を照合する")] public bool verifySha256 = true;

        public Mesh LoadedMesh { get; private set; }
        public string Sha256Read { get; private set; } = "";
        public int Vertices { get; private set; }
        public int Triangles { get; private set; }
        public string[] Channels { get; private set; } = new string[0];

        public void Load()
        {
            var jp = Path.GetFullPath(jsonPath);
            var jo = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(jp)), "static_mesh");
            if (DS27Json.Text(jo, "schema") != "GreatWave.AS03.static_mesh/1") throw new InvalidDataException("静止のメッシュの書式ではありません: " + jp);
            int n = (int)DS27Json.Num(jo, "vertices");
            int m = (int)DS27Json.Num(jo, "triangles");
            var binPath = Path.Combine(Path.GetDirectoryName(jp), DS27Json.Text(jo, "bin"));
            var bytes = File.ReadAllBytes(binPath);
            using (var s = SHA256.Create()) Sha256Read = BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
            if (verifySha256 && DS27Json.Has(jo, "sha256") && DS27Json.Text(jo, "sha256") != Sha256Read) throw new InvalidDataException("静止のメッシュの SHA-256 が違います: " + binPath);
            var chl = DS27Json.Get(jo, "channels") as System.Collections.IList;
            if (chl == null) throw new InvalidDataException("channels がありません");
            var mesh = new Mesh { name = "AS03 " + Path.GetFileNameWithoutExtension(jp), hideFlags = HideFlags.DontSave, indexFormat = n > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
            long off = 0;
            var names = new List<string>();
            foreach (var o in chl)
            {
                var pair = o as System.Collections.IList;
                string name = (string)pair[0];
                int comps = Convert.ToInt32(pair[1]);
                names.Add(name + ":" + comps);
                var f = new float[n * comps];
                Buffer.BlockCopy(bytes, (int)off, f, 0, n * comps * 4);
                off += (long)n * comps * 4;
                if (name == "position" || name == "normal")
                {
                    var v = new Vector3[n];
                    for (int i = 0; i < n; i++) v[i] = new Vector3(f[3 * i], f[3 * i + 1], f[3 * i + 2]);
                    if (name == "position") mesh.vertices = v; else mesh.normals = v;
                }
                else
                {
                    var v = new Vector4[n];
                    for (int i = 0; i < n; i++) v[i] = new Vector4(f[4 * i], f[4 * i + 1], f[4 * i + 2], f[4 * i + 3]);
                    if (name == "tangent") mesh.tangents = v;
                    else if (name.StartsWith("uv")) mesh.SetUVs(int.Parse(name.Substring(2)), new List<Vector4>(v));
                    else throw new InvalidDataException("知らないチャンネル: " + name);
                }
            }
            if (off + (long)m * 12 != bytes.LongLength) throw new InvalidDataException("静止のメッシュの大きさが合いません: " + bytes.LongLength + " / " + (off + (long)m * 12));
            var tri = new int[m * 3];
            Buffer.BlockCopy(bytes, (int)off, tri, 0, m * 12);
            mesh.SetIndices(tri, MeshTopology.Triangles, 0, true);
            mesh.RecalculateBounds();
            var mf = GetComponent<MeshFilter>(); if (mf == null) mf = gameObject.AddComponent<MeshFilter>();          // Unity の偽の null があるので ?? は使わない
            var mr = GetComponent<MeshRenderer>(); if (mr == null) mr = gameObject.AddComponent<MeshRenderer>();
            mf.sharedMesh = mesh;
            if (material != null) mr.sharedMaterial = material;
            mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off; mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            LoadedMesh = mesh; Vertices = n; Triangles = m; Channels = names.ToArray();
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
        }

        public void Release()
        {
            if (LoadedMesh != null) { if (Application.isPlaying) Destroy(LoadedMesh); else DestroyImmediate(LoadedMesh); }
            LoadedMesh = null;
        }
    }
}
