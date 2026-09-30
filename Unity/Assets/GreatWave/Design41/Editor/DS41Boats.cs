using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design36;
using GreatWave.Design37;
using GreatWave.Design38;
using GreatWave.Design39;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design41.EditorTools
{
    // 設計41：仮船（M1 の blockout）を、資料に基づく押送船の Blender モデル（ds41_oshiokuri.fbx）へ置き換える。
    //   ImportCheck.  設計07 の検査：FBX を保存しない空の場面の原点に置き、部品ごとのワールドの頂点の範囲を Blender の値（(x, y, z) → (−x, z, −y)）と比べる。
    //                 尺度（先端間 10、幅）・軸（船首 +Z、上 +Y）・左右（右舷の櫓 3 本が +X、左舷の 4 本が −X、三重積の符号）・船殻の法線の向き。
    //   BuildScene.   プレハブ DS41_Oshiokuri.prefab（表示の部品は美術優先27 の平塗りの材質、衝突形状は MeshCollider（convex）で描かない、浮力用の船体は描かない）を作り、
    //                 設計39 の場面 DS39_Paper.unity を開いて（保存しない）、3 隻の根「AF27 船 boat_*」の子（blockout）をプレハブに替え、
    //                 根の Transform（位置・回転・縮尺）は変えずに、新しい場面 DS41_Boats.unity として別に保存する。原画視点の両端の投影は変わらない。
    //   Render.       DS41_Boats.unity で t*（12 s）を描く（設計40 の DS40Render と同じ描き方）：t28 の組（回帰の評価器の入力）、原画視点の色画像と
    //                 評価器23 の ID 画像（船 3 隻は別の色）、座席 v1 などの視点、船の近くの一時のカメラ（置き換えの前＝blockout を一時に置いた描画と後）。
    // PC オフスクリーン描画（batchmode）。HMD 実機ではない。
    public static class DS41Boats
    {
        const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        public const string Scene41 = "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity";
        const string FbxPath = "Assets/GreatWave/Design41/Models/ds41_oshiokuri.fbx";
        const string PrefabPath = "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab";
        const string BlockoutFbx = "Assets/GreatWave/Art/M1/boat_blockout.fbx";
        const string MatOchre = "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_boat_ochre.mat";
        const string MatAiDark = "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_ai_dark.mat";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/41/model/unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム", FujiName = "AF27 富士";
        static readonly string[] BoatKeys = { "boat_left", "boat_mid", "boat_fg" };
        const int W = 1920, H = 1080;
        const float TStar = 12f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60), BackTarget = new Vector3(-5, 8, -3);
        static readonly Vector4 IdSkyV = new Vector4(0, 1, 1, 1), IdOtherV = new Vector4(0, 0, 0, 1);
        static readonly Dictionary<string, Vector4> IdBoats = new Dictionary<string, Vector4> {
            { "boat_left", new Vector4(0.4f, 0, 0, 1) }, { "boat_mid", new Vector4(0, 0.4f, 0, 1) }, { "boat_fg", new Vector4(0.4f, 0.4f, 0, 1) } };
        static readonly Dictionary<string, string> MatMap = new Dictionary<string, string> {
            { "GW_Boat_Wood", MatOchre }, { "GW_Boat_Plank", MatOchre }, { "GW_Boat_Edge", MatAiDark }, { "GW_Boat_Oar", MatAiDark } };

        static string[] Protected => new[] {
            Scene39, "Assets/GreatWave/Design39/Scenes/DS39_Perf.unity", "Assets/GreatWave/Design40/Editor/DS40Render.cs",
            "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab", "Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab", BlockoutFbx,
            MatOchre, MatAiDark, "Assets/GreatWave/ArtFirst/Shaders/AF27Flat.shader", "Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
            "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design39/Scripts/DS39PaperLayers.cs", "Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity",
            "Build/Design/30/sea/boat_support.json", "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/33/claws/ds33_claw_frames_f32.bin" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        // ------------------------------------------------------------------ 設計07 の検査
        [Serializable] class ExpObj { public string name; public float[] min, max; public int vertices; }
        [Serializable] class Expect
        {
            public string blenderReportSha256; public ExpObj[] objects; public float[] bowTip, sternTip, stationZ, stationBottom, stationSheer;
            public float tipToTip, halfBeam; public string starboardPrefix, portPrefix; public int starboardCount, portCount;
        }
        [Serializable] class ObjCheck { public string name; public Vector3 min, max, expMin, expMax, localPosition, localEuler, localScale; public float maxAbsDiff; public int unityVertices, blenderVertices; }
        [Serializable] class CheckReport
        {
            public string unity, utc, fbx, fbxSha256, expectSha256, noteJa;
            public string importerJa;
            public ObjCheck[] objects;
            public float boundsMaxAbsDiff, bowTipNearest, sternTipNearest, tipToTip, beam, triple;
            public Vector3 bowTipMeasured, sternTipMeasured, forward, up, right;
            public int starboardOarsPlusX, starboardOarsMinusX, portOarsPlusX, portOarsMinusX;
            public int hullTrianglesChecked, hullTrianglesOutward;
            public float hullOutwardFraction;
            public bool rootIdentity, scalePass, axisPass, mirrorPass, normalsPass, pass;
        }

        public static void ImportCheck()
        {
            AssetDatabase.Refresh();
            var imp = (ModelImporter)AssetImporter.GetAtPath(FbxPath);
            var ex = JsonUtility.FromJson<Expect>(File.ReadAllText(OutRoot + "/ds41_unity_expect.json"));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            go.transform.position = Vector3.zero; go.transform.rotation = Quaternion.identity; go.transform.localScale = Vector3.one;
            var rep = new CheckReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), fbx = FbxPath, fbxSha256 = Sha(FbxPath),
                expectSha256 = Sha(OutRoot + "/ds41_unity_expect.json"),
                importerJa = string.Format(CultureInfo.InvariantCulture, "globalScale={0} useFileScale={1} useFileUnits={2} bakeAxisConversion={3} fileScale={4}",
                    imp.globalScale, imp.useFileScale, imp.useFileUnits, imp.bakeAxisConversion, imp.fileScale),
                rootIdentity = true
            };
            var list = new List<ObjCheck>();
            var all = new List<Vector3>();
            var cents = new Dictionary<string, Vector3>();
            float worst = 0;
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                var e = ex.objects.FirstOrDefault(o => o.name == mf.name);
                var vs = mf.sharedMesh.vertices.Select(v => mf.transform.TransformPoint(v)).ToArray();
                var mn = new Vector3(vs.Min(v => v.x), vs.Min(v => v.y), vs.Min(v => v.z));
                var mx = new Vector3(vs.Max(v => v.x), vs.Max(v => v.y), vs.Max(v => v.z));
                var oc = new ObjCheck { name = mf.name, min = mn, max = mx, unityVertices = vs.Length, localPosition = mf.transform.localPosition,
                    localEuler = mf.transform.localEulerAngles, localScale = mf.transform.localScale };
                if (e != null)
                {
                    oc.expMin = new Vector3(e.min[0], e.min[1], e.min[2]); oc.expMax = new Vector3(e.max[0], e.max[1], e.max[2]);
                    oc.blenderVertices = e.vertices;
                    oc.maxAbsDiff = Mathf.Max(MaxAbs(mn - oc.expMin), MaxAbs(mx - oc.expMax));
                    worst = Mathf.Max(worst, oc.maxAbsDiff);
                }
                else oc.maxAbsDiff = float.NaN;
                list.Add(oc);
                cents[mf.name] = (mn + mx) * 0.5f;
                if (!mf.name.StartsWith("Boat41_Col_") && mf.name != "Boat41_Buoyancy") all.AddRange(vs);
            }
            rep.objects = list.ToArray();
            rep.boundsMaxAbsDiff = worst;
            var bow = new Vector3(ex.bowTip[0], ex.bowTip[1], ex.bowTip[2]);
            var stern = new Vector3(ex.sternTip[0], ex.sternTip[1], ex.sternTip[2]);
            rep.bowTipMeasured = all.OrderBy(v => (v - bow).sqrMagnitude).First();
            rep.sternTipMeasured = all.OrderBy(v => (v - stern).sqrMagnitude).First();
            rep.bowTipNearest = (rep.bowTipMeasured - bow).magnitude;
            rep.sternTipNearest = (rep.sternTipMeasured - stern).magnitude;
            rep.tipToTip = (rep.bowTipMeasured - rep.sternTipMeasured).magnitude;
            var hullR = go.GetComponentsInChildren<MeshFilter>(true).First(m => m.name == "Boat41_Hull");
            var hv = hullR.sharedMesh.vertices.Select(v => hullR.transform.TransformPoint(v)).ToArray();
            rep.beam = hv.Max(v => v.x) - hv.Min(v => v.x);
            // 軸：船首 +Z、上 +Y（船殻の舷の上縁の中ほど − 船底）、右：右舷の櫓の中心 − 左舷の櫓の中心
            rep.forward = (rep.bowTipMeasured - rep.sternTipMeasured).normalized;
            // 上：両端の先端の中点 − 船体中央の船底の最も低い点（船首の向きの成分を除く）
            var mid = hv.Where(v => Mathf.Abs(v.z) < 1f).ToArray(); float ymin = mid.Min(v => v.y);
            var low = mid.Where(v => v.y < ymin + 1e-3f).ToArray();
            var keel = low.Aggregate(Vector3.zero, (p, q) => p + q) / low.Length;   // 航の下面の中央（左右の平均）
            var upv = (rep.bowTipMeasured + rep.sternTipMeasured) * 0.5f - keel;
            rep.up = (upv - Vector3.Dot(upv, rep.forward) * rep.forward).normalized;
            var sb = cents.Where(kv => kv.Key.StartsWith(ex.starboardPrefix)).Select(kv => kv.Value).ToList();
            var pt = cents.Where(kv => kv.Key.StartsWith(ex.portPrefix)).Select(kv => kv.Value).ToList();
            rep.starboardOarsPlusX = sb.Count(c => c.x > 0); rep.starboardOarsMinusX = sb.Count(c => c.x < 0);
            rep.portOarsPlusX = pt.Count(c => c.x > 0); rep.portOarsMinusX = pt.Count(c => c.x < 0);
            var sbc = sb.Aggregate(Vector3.zero, (a, b) => a + b) / Math.Max(1, sb.Count);
            var ptc = pt.Aggregate(Vector3.zero, (a, b) => a + b) / Math.Max(1, pt.Count);
            rep.right = new Vector3(sbc.x - ptc.x, 0, 0).normalized;
            rep.triple = Vector3.Dot(Vector3.Cross(rep.up, rep.forward), rep.right);
            // 船殻の法線：面の中心から、その断面の中心線（x = 0、高さ 船底 + 0.85 × (舷 − 船底)）へ向かう向きの逆を向くか
            var mesh = hullR.sharedMesh; var tri = mesh.triangles; var nrm = mesh.normals;
            int chk = 0, outw = 0;
            for (int i = 0; i < tri.Length; i += 3)
            {
                var c = (hv[tri[i]] + hv[tri[i + 1]] + hv[tri[i + 2]]) / 3f;
                if (Mathf.Abs(c.z) > 4.2f) continue;
                var n = hullR.transform.TransformDirection(nrm[tri[i]] + nrm[tri[i + 1]] + nrm[tri[i + 2]]).normalized;
                int k = 0; float best = float.MaxValue;
                for (int s = 0; s < ex.stationZ.Length; s++) { float d = Mathf.Abs(ex.stationZ[s] - c.z); if (d < best) { best = d; k = s; } }
                float zc = ex.stationBottom[k] + 0.85f * (ex.stationSheer[k] - ex.stationBottom[k]);
                var r = new Vector3(c.x, c.y - zc, 0);
                if (r.magnitude < 1e-5f) continue;
                chk++; if (Vector3.Dot(n, r) > 0) outw++;
            }
            rep.hullTrianglesChecked = chk; rep.hullTrianglesOutward = outw; rep.hullOutwardFraction = chk > 0 ? (float)outw / chk : 0;
            rep.scalePass = Mathf.Abs(rep.tipToTip - ex.tipToTip) < 1e-3f && Mathf.Abs(rep.beam - 2 * ex.halfBeam) < 2e-3f && worst < 1e-3f;
            rep.axisPass = Vector3.Dot(rep.forward, Vector3.forward) > 0.999f && Vector3.Dot(rep.up, Vector3.up) > 0.999f && rep.bowTipNearest < 1e-3f && rep.sternTipNearest < 1e-3f;
            rep.mirrorPass = rep.starboardOarsPlusX == ex.starboardCount && rep.portOarsMinusX == ex.portCount && rep.starboardOarsMinusX == 0 && rep.portOarsPlusX == 0 && rep.triple > 0.999f;
            rep.normalsPass = rep.hullOutwardFraction > 0.98f;
            rep.pass = rep.scalePass && rep.axisPass && rep.mirrorPass && rep.normalsPass;
            rep.noteJa = "子の localEuler の x が 270.02° と出るのは、四元数 (−0.7071068, 0, 0, 0.7071067) を ZXY のオイラー角へ直すときの特異点の近くの丸めで、頂点の範囲の差（最大 boundsMaxAbsDiff）が回転の誤差のないことを示す。" +
                         "FBX を保存しない空の場面の原点（位置 0・回転 0・縮尺 1）に置き、部品ごとの MeshFilter のワールドの頂点を測った。期待値は Blender の頂点の範囲を (x, y, z) → (−x, z, −y) で写したもの（設計07 の実測の対応）。" +
                         "三重積は Unity の Vector3.Cross(上, 船首) と右（右舷の櫓の中心 − 左舷の櫓の中心）の内積で、+1 なら左右の反転なし。";
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/ds41_import_check.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS41_IMPORT_CHECK pass=" + rep.pass + " scale=" + rep.scalePass + " axis=" + rep.axisPass + " mirror=" + rep.mirrorPass + " normals=" + rep.normalsPass +
                                  " worst=" + worst.ToString("0.000000", CultureInfo.InvariantCulture) + " triple=" + rep.triple.ToString("0.0000", CultureInfo.InvariantCulture));
            if (!rep.pass) EditorApplication.Exit(3);
        }

        static float MaxAbs(Vector3 v) => Mathf.Max(Mathf.Abs(v.x), Mathf.Max(Mathf.Abs(v.y), Mathf.Abs(v.z)));

        // ------------------------------------------------------------------ プレハブと場面
        [Serializable] class BoatRec { public string key; public Vector3 position, scale; public Quaternion rotation; public string[] removedChildren; public string placed; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene39, scene39Sha256Before, scene39Sha256After, scene41, scene41Sha256, prefab, prefabSha256, fbxSha256, noteJa;
            public BoatRec[] boats; public string[] prefabParts; public bool protectedUnchanged; public string[] changedFiles;
        }

        static GameObject MakePrefab(List<string> parts)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PrefabPath));
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.name = "DS41 押送船";
            var mats = MatMap.ToDictionary(kv => kv.Key, kv => AssetDatabase.LoadAssetAtPath<Material>(kv.Value));
            foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                if (mf.name.StartsWith("Boat41_Col_"))
                {
                    if (mr != null) UnityEngine.Object.DestroyImmediate(mr);
                    var mc = mf.gameObject.AddComponent<MeshCollider>();
                    mc.sharedMesh = mf.sharedMesh; mc.convex = true;
                    parts.Add(mf.name + "：衝突形状（MeshCollider convex、描画なし）");
                    continue;
                }
                if (mf.name == "Boat41_Buoyancy")
                {
                    if (mr != null) UnityEngine.Object.DestroyImmediate(mr);
                    parts.Add(mf.name + "：浮力用の船体（MeshFilter だけ、描画なし）");
                    continue;
                }
                mr.sharedMaterials = mr.sharedMaterials.Select(m =>
                {
                    if (m == null || !mats.ContainsKey(m.name)) throw new InvalidOperationException("材質の対応がありません: " + (m == null ? "null" : m.name) + " @ " + mf.name);
                    return mats[m.name];
                }).ToArray();
                mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
                parts.Add(mf.name + "：表示（" + string.Join("・", mr.sharedMaterials.Select(m => m.name)) + "）");
            }
            var pf = PrefabUtility.SaveAsPrefabAsset(inst, PrefabPath);
            UnityEngine.Object.DestroyImmediate(inst);
            return pf;
        }

        public static void BuildScene()
        {
            var before = Protected.ToDictionary(p => p, Sha);
            AssetDatabase.Refresh();
            var parts = new List<string>();
            var prefab = MakePrefab(parts);
            var s39Before = Sha(Scene39);
            var scene = EditorSceneManager.OpenScene(Scene39, OpenSceneMode.Single);
            var recs = new List<BoatRec>();
            foreach (var key in BoatKeys)
            {
                var root = GameObject.Find("AF27 船 " + key);
                if (root == null) throw new InvalidOperationException("船の根がありません: " + key);
                var kids = root.transform.Cast<Transform>().ToList();
                var rec = new BoatRec { key = key, position = root.transform.position, rotation = root.transform.rotation, scale = root.transform.lossyScale,
                    removedChildren = kids.Select(k => k.name).ToArray() };
                foreach (var k in kids) UnityEngine.Object.DestroyImmediate(k.gameObject);
                var p = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
                p.transform.localPosition = Vector3.zero; p.transform.localRotation = Quaternion.identity; p.transform.localScale = Vector3.one;
                p.name = "DS41 押送船（" + key + "）";
                rec.placed = p.name;
                // 船尾の梯子状の枠は原画の右船（boat_mid）だけに見える（絵の読み P8）。ほかの 2 隻では切る
                var frame = p.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "Boat41_SternFrame");
                if (frame != null && key != "boat_mid") { frame.gameObject.SetActive(false); rec.placed += "（船尾の枠は切）"; }
                recs.Add(rec);
            }
            Directory.CreateDirectory(Path.GetDirectoryName(Scene41));
            if (!EditorSceneManager.SaveScene(scene, Scene41, true)) throw new InvalidOperationException("場面を保存できません");
            // 設計39 の場面は開いたまま保存しない（捨てる）
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.Refresh();
            var after = Protected.ToDictionary(p => p, Sha);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene39 = Scene39, scene39Sha256Before = s39Before, scene39Sha256After = Sha(Scene39),
                scene41 = Scene41, scene41Sha256 = Sha(Scene41), prefab = PrefabPath, prefabSha256 = Sha(PrefabPath), fbxSha256 = Sha(FbxPath), boats = recs.ToArray(),
                prefabParts = parts.ToArray(), protectedUnchanged = Protected.All(p => before[p] == after[p]), changedFiles = Protected.Where(p => before[p] != after[p]).ToArray(),
                noteJa = "設計39 の場面を開き、3 隻の根の子（blockout）を消してプレハブを根の原点に置き、別の場面として保存した（saveAsCopy）。根の Transform は変えていない。設計39 の場面は保存していない。"
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/ds41_build_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS41_BUILD_DONE protectedUnchanged=" + rep.protectedUnchanged + " scene39Same=" + (rep.scene39Sha256Before == rep.scene39Sha256After));
            if (!rep.protectedUnchanged) EditorApplication.Exit(4);
        }

        // ------------------------------------------------------------------ 描画（設計40 の DS40Render と同じ組み方）
        class Ctx
        {
            public GameObject ctx;
            public DS30SinglePlayback play;
            public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS38ClawOutline clawLine;
            public List<DS38SheetOutline> lineComps = new List<DS38SheetOutline>();
            public DS34LayerSet layers;
            public DS31InstancedParticles spray, dense;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
            public DS38LineGlobals globals;
            public DS39PaperLayers paper;
            public List<GameObject> temp = new List<GameObject>();
        }

        [Serializable] class ImgRec { public string view, cond, path, sha256; public float t; }
        [Serializable] class CamRec { public string view; public Vector3 position, euler; public float fov, near, far; public float[] worldToCamera, projection; }
        [Serializable] class BoatPose { public string key; public Vector3 position, lossyScale; public Quaternion rotation; public float[] localToWorld; public int renderers; public Vector3 boundsMin, boundsMax; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, noteJa, idLegendJa;
            public string[] t28Files; public ImgRec[] images; public CamRec[] cameras; public BoatPose[] boats;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles; public float secondsTotal;
        }

        static Ctx Open()
        {
            EditorSceneManager.OpenScene(Scene41, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.sheets = c.play.sheets.Where(s => s != null).ToList();
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            c.cams["seat_toward_wave"] = camRoot.Find("DS30 seat_toward_wave").GetComponent<Camera>();
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            var parts = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).ToList();
            c.spray = parts.First(p => p.name == "DS31 spray");
            c.dense = parts.First(p => p.name == "DS39 spray dense");
            c.pal = c.claws.GetComponent<DS36ClawPalette>();
            c.seaPal = roots.Select(g => g.GetComponentInChildren<DS36SeaPalette>(true)).First(x => x != null);
            c.clawLine = c.claws.GetComponent<DS38ClawOutline>();
            c.globals = c.play.GetComponent<DS38LineGlobals>();
            foreach (var s in c.sheets) { var so = s.GetComponent<DS38SheetOutline>(); if (so != null) c.lineComps.Add(so); }
            c.paper = roots.Select(g => g.GetComponentInChildren<DS39PaperLayers>(true)).First(x => x != null);
            // 一時のカメラ（背面：CP1 と同じ。船の近く：この番号の確認用）
            TempCam(c, "back", BackPosition, BackTarget, 50);
            return c;
        }

        static void TempCam(Ctx c, string key, Vector3 pos, Vector3 target, float fov)
        {
            var go = new GameObject("DS41 一時カメラ " + key) { hideFlags = HideFlags.DontSave };
            var cam = go.AddComponent<Camera>();
            cam.CopyFrom(c.cams["painting"]);
            cam.enabled = false;
            go.transform.position = pos; go.transform.LookAt(target, Vector3.up);
            cam.fieldOfView = fov; cam.nearClipPlane = 0.05f;
            c.cams[key] = cam; c.temp.Add(go);
        }

        static void Prepare(Ctx c)
        {
            foreach (var so in c.lineComps) so.Attach();
            c.clawLine.Attach();
            c.globals.Apply();
            c.play.Prepare();
            c.spray.Load(); c.claws.Load(); c.dense.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            foreach (var so in c.lineComps) so.BindMask();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS38LineCoordMode", 0);
            Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);
            Shader.SetGlobalFloat("_DS39Gain", 0);
            c.paper.Build();
        }

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t); c.dense.ApplyT(t); c.claws.ApplyT(t);
            c.layers.whiteBand = white; c.layers.clawsOn = claws; c.layers.sprayOn = spray;
            c.layers.ApplyToggles();
            c.clawLine.Sync();
            c.paper.Apply();
        }

        static void SetLines(Ctx c, bool on)
        {
            foreach (var s in c.sheets) if (s.outline != null) s.outline.enabled = on;
            if (c.clawLine.Line != null) c.clawLine.Line.enabled = on && c.clawR.enabled;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds41Out") ?? OutRoot;
            var skip = new HashSet<string>((Arg(a, "-ds41Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = Scene41, sceneSha256 = Sha(Scene41),
                idLegendJa = "full/ids_*.png（3840×2160、線形、MSAA なし）：空 (0,255,255)、船は AF24 ID Flat に 0.4 を渡し線形の描画先で boat_left (34,0,0)・boat_mid (0,34,0)・boat_fg (34,34,0)（設計40 と同じ）。" +
                             "keypose のシート・爪は _AF28IdMode の色区 ID、線 (255,0,255)、CPU のメッシュの other (0,0,0)。飛沫は入れない。"
            };
            var c = Open();
            var imgs = new List<ImgRec>();
            try
            {
                Prepare(c);
                Set(c, false, false, false);
                Seek(c, TStar, true, true, false);
                // 船の近くの一時のカメラ（t* の船の位置から決める）
                foreach (var key in BoatKeys)
                {
                    var b = BoundsOf(GameObject.Find("AF27 船 " + key));
                    Vector3 off = key == "boat_left" ? new Vector3(7, 4.5f, -9) : key == "boat_mid" ? new Vector3(-9, 4, -9) : new Vector3(-7, 4, -8);
                    TempCam(c, "close_" + key, b.center + off, b.center, 45);
                }
                if (!skip.Contains("t28"))
                {
                    var f = new List<string>();
                    Seek(c, TStar, true, false, false);
                    f.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, true, true, false);
                    f.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                    rep.t28Files = f.ToArray();
                }
                if (!skip.Contains("full"))
                {
                    foreach (var (cond, on) in new[] { ("off", false), ("all", true) })
                    {
                        Set(c, on, on, on);
                        Seek(c, TStar, true, true, true);
                        var p = od + "/full/painting_t120_" + cond + ".png";
                        CaptureWithSpray(c, "painting", p, on);
                        imgs.Add(Rec("painting", cond, p, TStar));
                    }
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, false);
                    var p1 = od + "/full/ids_noline.png"; RenderIdsFull(c, c.cams["painting"], p1, false); imgs.Add(Rec("painting", "ids_noline", p1, TStar));
                    var p2 = od + "/full/ids_line.png"; RenderIdsFull(c, c.cams["painting"], p2, true); imgs.Add(Rec("painting", "ids_line", p2, TStar));
                    SetLines(c, true);
                }
                if (!skip.Contains("views"))
                {
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, true);
                    foreach (var view in new[] { "seat", "seat_low", "seat_toward_wave", "side_left", "back", "close_boat_mid", "close_boat_fg", "close_boat_left" })
                    {
                        var p = od + "/views/" + view + "_t120_off.png";
                        CaptureWithSpray(c, view, p, false);
                        imgs.Add(Rec(view, "off", p, TStar));
                    }
                    // 置き換えの前（blockout を一時に置いた描画）：同じカメラで比べる。場面は保存しない
                    var blk = AssetDatabase.LoadAssetAtPath<GameObject>(BlockoutFbx);
                    var ochre = AssetDatabase.LoadAssetAtPath<Material>(MatOchre); var ai = AssetDatabase.LoadAssetAtPath<Material>(MatAiDark);
                    var tmp = new List<GameObject>(); var hidden = new List<GameObject>();
                    try
                    {
                        foreach (var key in BoatKeys)
                        {
                            var root = GameObject.Find("AF27 船 " + key).transform;
                            foreach (Transform ch in root) if (ch.gameObject.activeSelf) { ch.gameObject.SetActive(false); hidden.Add(ch.gameObject); }
                            var g = (GameObject)UnityEngine.Object.Instantiate(blk, root);
                            g.hideFlags = HideFlags.DontSave; g.transform.localPosition = Vector3.zero; g.transform.localRotation = Quaternion.identity; g.transform.localScale = Vector3.one;
                            foreach (var r in g.GetComponentsInChildren<Renderer>(true))
                                r.sharedMaterials = r.sharedMaterials.Select(m => m != null && m.name.StartsWith("GW_Boat_Edge") ? ai : ochre).ToArray();
                            tmp.Add(g);
                        }
                        foreach (var view in new[] { "painting", "seat", "close_boat_mid", "close_boat_fg", "close_boat_left" })
                        {
                            var p = od + "/views/" + view + "_t120_off_blockout.png";
                            CaptureWithSpray(c, view, p, false);
                            imgs.Add(Rec(view, "off_blockout", p, TStar));
                        }
                    }
                    finally
                    {
                        foreach (var g in tmp) UnityEngine.Object.DestroyImmediate(g);
                        foreach (var g in hidden) g.SetActive(true);
                    }
                }
                var cams = new List<CamRec>();
                foreach (var kv in c.cams)
                {
                    var cam = kv.Value; float asp = cam.aspect; cam.aspect = (float)W / H;
                    cams.Add(new CamRec { view = kv.Key, position = cam.transform.position, euler = cam.transform.rotation.eulerAngles, fov = cam.fieldOfView,
                        near = cam.nearClipPlane, far = cam.farClipPlane, worldToCamera = M(cam.worldToCameraMatrix), projection = M(cam.projectionMatrix) });
                    cam.aspect = asp;
                }
                rep.cameras = cams.ToArray();
                Seek(c, TStar, true, true, false);
                rep.boats = BoatKeys.Select(k =>
                {
                    var g = GameObject.Find("AF27 船 " + k); var b = BoundsOf(g);
                    return new BoatPose { key = k, position = g.transform.position, rotation = g.transform.rotation, lossyScale = g.transform.lossyScale,
                        localToWorld = M(g.transform.localToWorldMatrix), renderers = g.GetComponentsInChildren<Renderer>(false).Count(r => r.enabled), boundsMin = b.min, boundsMax = b.max };
                }).ToArray();
            }
            finally
            {
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.paper.Teardown();
                foreach (var so in c.lineComps) so.ReleaseMask();
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                foreach (var g in c.temp) if (g != null) UnityEngine.Object.DestroyImmediate(g);
            }
            rep.images = imgs.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render、DS41_Boats.unity を開くだけで保存しない）。HMD 実機ではない。" +
                         "_blockout の画像は、同じ場面で新しい船を一時に隠し、M1 の blockout を同じ根に一時に置いて描いた置き換えの前の比べ。";
            File.WriteAllText(od + "/ds41_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS41_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static Bounds BoundsOf(GameObject g)
        {
            var rs = g.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled).ToArray();
            var b = rs[0].bounds; foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds);
            return b;
        }

        static float[] M(Matrix4x4 m) { var r = new float[16]; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) r[i * 4 + j] = m[i, j]; return r; }
        static ImgRec Rec(string view, string cond, string path, float t) => new ImgRec { view = view, cond = cond, path = path, t = t, sha256 = Sha(path) };
        static void Set(Ctx c, bool paper, bool mura, bool spray) => c.paper.Set(paper, mura, spray);

        static List<string> RenderT28(Ctx c, string d28)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            try
            {
                SetLines(c, true);
                foreach (var v in new[] { "painting", "seat", "seat_low" }) f.Add(Capture(c.cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                c.ctx.SetActive(false);
                SetLines(c, false);
                f.Add(Capture(c.cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png"));
                f.Add(Capture(c.cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png"));
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png"));
                f.Add(Capture(c.cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png"));
                SetLines(c, true);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png"));
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.ctx.SetActive(true);
                SetLines(c, true);
            }
            return f;
        }

        static void CaptureWithSpray(Ctx c, string view, string path, bool dense)
        {
            var cam = c.cams[view];
            var cb = new CommandBuffer { name = "DS41 飛沫" };
            c.spray.AddTo(cb);
            if (dense) c.dense.AddTo(cb);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            try { Capture(cam, W, H, true, path); }
            finally { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
        }

        static bool KeepMaterial(Shader sh)
        {
            if (sh == null) return false;
            string n = sh.name;
            return n.Contains("Keypose") || n.StartsWith("GreatWave/Design27/") || n.StartsWith("GreatWave/Design34/") || n.StartsWith("GreatWave/Design36/DS36 Claw")
                || n.StartsWith("GreatWave/Design38/") || n.StartsWith("GreatWave/Design31/");
        }

        static void RenderIdsFull(Ctx c, Camera camera, string pngPath, bool lines)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Vector4 v) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetVector("_IdColor", v); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find(SkyDomeName);
            var boatRoots = IdBoats.Keys.ToDictionary(k => k, k => GameObject.Find("AF27 船 " + k));
            SetLines(c, lines);
            try
            {
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
                {
                    if (!r.enabled) continue;
                    var sh = r.sharedMaterial != null ? r.sharedMaterial.shader : null;
                    string key = null; Vector4 col = IdOtherV;
                    if (r.gameObject == dome) { key = "sky"; col = IdSkyV; }
                    foreach (var b in IdBoats) if (r.transform.IsChildOf(boatRoots[b.Key].transform)) { key = b.Key; col = b.Value; }
                    if (key == null && KeepMaterial(sh)) continue;
                    if (key == null) key = "other";
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = Enumerable.Repeat(Mat(key, col), Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                var clear = camera.clearFlags; var bg = camera.backgroundColor;
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 1, 1, 1);
                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false, true);
                var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA; float asp = camera.aspect;
                camera.allowHDR = false; camera.allowMSAA = false;
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
                camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = asp;
                camera.clearFlags = clear; camera.backgroundColor = bg;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            }
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = colour ? (Color)SkyTop : Color.white;
            camera.allowHDR = false; camera.allowMSAA = colour;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = colour ? 8 : 1 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h; camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
