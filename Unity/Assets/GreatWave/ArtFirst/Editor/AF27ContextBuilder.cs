using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号27「空のドーム・船・富士の配置」。
    // Dump：M1 の仮形状（船・富士・前景のうねり・斜面）の FBX を保存しない空のシーンへ置き、
    //       配置用の親を単位行列にしたときの頂点・三角形を書き出す（numpy で配置を当てはめるため）。
    // 配置の当てはめは Tools/GWContext/af27_fit.py、シーンの組み立てと描画は AF27ContextScene.cs が行う。
    public static class AF27ContextBuilder
    {
        public const string OutRoot = "Build/ArtFirst/27";
        public const string ArtDir = "Assets/GreatWave/Art/M1/";
        public const string SlopesFbx = "Assets/GreatWave/Art/M1_Revision01/revision_slopes.fbx";

        public static readonly string[] Groups = { "boat_blockout", "fuji_blockout", "foam_static", "revision_slopes" };

        public static string FbxPath(string group) => group == "revision_slopes" ? SlopesFbx : ArtDir + group + ".fbx";

        public static void Dump()
        {
            string dir = OutRoot + "/dump";
            Directory.CreateDirectory(dir);
            var hashesBefore = Groups.ToDictionary(g => g, g => Sha(FbxPath(g)));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var report = new DumpReport { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O") };
            var groups = new List<DumpGroup>();
            foreach (var g in Groups)
            {
                var asset = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath(g));
                if (asset == null) throw new InvalidOperationException("FBX がありません: " + FbxPath(g));
                // M1 の Model() と同じく、配置用の親（単位行列）の下に FBX を置く。斜面は親なしで置かれていたので、
                // FBX の既定の根の変換も記録する（numpy 側で M1 の配置を再現するため）。
                var root = new GameObject("dump_" + g);
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(asset);
                var instDefault = new TRS { position = inst.transform.localPosition, rotation = inst.transform.localRotation, scale = inst.transform.localScale };
                inst.transform.SetParent(root.transform, false);
                var dg = new DumpGroup { group = g, fbx = FbxPath(g), fbxSha256 = hashesBefore[g], fbxRootDefault = instDefault };
                var meshes = new List<DumpMesh>();
                using (var fs = new FileStream(Path.Combine(dir, g + ".bin"), FileMode.Create))
                using (var bw = new BinaryWriter(fs))
                {
                    foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var mesh = mf.sharedMesh;
                        var r = mf.GetComponent<Renderer>();
                        var m = mf.transform.localToWorldMatrix; // 親が単位行列なので根からの行列
                        var dm = new DumpMesh
                        {
                            name = mf.name, path = PathOf(mf.transform, root.transform), active = mf.gameObject.activeInHierarchy,
                            vertexCount = mesh.vertexCount, subMeshCount = mesh.subMeshCount, byteOffset = fs.Position,
                            materials = r == null ? new string[0] : r.sharedMaterials.Select(x => x == null ? "" : x.name).ToArray(),
                            indexCounts = Enumerable.Range(0, mesh.subMeshCount).Select(i => (int)mesh.GetIndexCount(i)).ToArray(),
                        };
                        foreach (var v in mesh.vertices)
                        {
                            var w = m.MultiplyPoint3x4(v);
                            bw.Write(w.x); bw.Write(w.y); bw.Write(w.z);
                        }
                        for (int s = 0; s < mesh.subMeshCount; s++)
                            foreach (var i in mesh.GetTriangles(s)) bw.Write(i);
                        meshes.Add(dm);
                    }
                }
                dg.meshes = meshes.ToArray();
                // 甲板の測り方（M1RevisionBuilder と同じ：根の局所 (0,10,-2) から下向き）と富士の頂点（根の局所 (0,8,0)）の確認用
                groups.Add(dg);
            }
            report.groups = groups.ToArray();
            report.fbxUnchanged = Groups.All(g => Sha(FbxPath(g)) == hashesBefore[g]);
            File.WriteAllText(Path.Combine(dir, "dump.json"), JsonUtility.ToJson(report, true));
            if (!report.fbxUnchanged) throw new InvalidOperationException("FBX が変わりました。");
            Debug.Log("AF27_DUMP_DONE groups=" + groups.Count);
        }

        public static string PathOf(Transform t, Transform stop) => t == stop || t.parent == null ? t.name : PathOf(t.parent, stop) + "/" + t.name;

        public static string Sha(string path)
        {
            using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] public class TRS { public Vector3 position; public Quaternion rotation; public Vector3 scale; }
        [Serializable] class DumpMesh { public string name, path; public bool active; public int vertexCount, subMeshCount; public long byteOffset; public string[] materials; public int[] indexCounts; }
        [Serializable] class DumpGroup { public string group, fbx, fbxSha256; public TRS fbxRootDefault; public DumpMesh[] meshes; }
        [Serializable] class DumpReport { public string unity, utc; public bool fbxUnchanged; public DumpGroup[] groups; }
    }
}
