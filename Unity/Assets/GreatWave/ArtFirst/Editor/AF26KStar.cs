using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号26「主役波の終態 K*」。M1 Revision01 の構図シーンを別名 AF26_KStar.unity で複製し（番号24 と同じ手順）、
    // 旧い静止波・斜面・白帯・爪を新シーンだけで非表示にして、gw_wavegen v1 の K*（立体解釈 30°／45°／60°）を 3 つ置く。
    // 解釈ごとに 1 つだけ表示して、PaintingCam v1（1920×1080）・評価器用 ID 画像（3840×2160）・船上座席・側面・背面・真上から
    // Camera.Render → RenderTexture → PNG で描く（PC のオフスクリーン描画。HMD 実機ではない）。
    public static class AF26KStar
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF26_KStar.unity";
        const string MaterialDir = "Assets/GreatWave/ArtFirst/Materials";
        const string OutRoot = "Build/ArtFirst/26";
        const string LayoutJson = "../Docs/Evidence/M1/Revision01/15_revision_layout.json";
        const int W = 1920, H = 1080;
        static readonly string[] Keys = { "a30", "a45", "a60" };

        // PaintingCam v1（Tools/PaintingTruth/painting_truth.json と同じ値）
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62);
        static readonly Vector3 PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        // 船上座席（15_revision_layout.json の eyeWorld）と側面は番号24 と同じ
        static readonly Vector3 BoatTarget = new Vector3(-7, 5, 3);
        const float BoatFov = 80;
        static readonly Vector3 SidePosition = new Vector3(53, 22, -2);
        static readonly Vector3 SideTarget = new Vector3(-1, 7, 0);
        const float SideFov = 60;
        // 背面（波の後ろ、左奥の上から）と真上（平面図）は番号26 で加えた。3 解釈で同じ機位にする。
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60);
        static readonly Vector3 BackTarget = new Vector3(-5, 8, -3);
        const float BackFov = 50;
        static readonly Vector3 TopPosition = new Vector3(-5, 120, -10);
        static readonly Vector3 TopTarget = new Vector3(-5, 0, -9.9f);
        const float TopFov = 60;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);   // 番号23 調色板 v0.2「空上」
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Color IdBoatLeft = new Color(1, 0, 0), IdBoatMid = new Color(0, 1, 0), IdBoatFg = new Color(1, 1, 0);

        public static void BuildAndRender() { Build(); Render(); }

        public static void Build()
        {
            string source = GreatWave.Editor.M1RevisionBuilder.ScenePath;
            string sourceHashBefore = Sha(source);
            var scene = EditorSceneManager.OpenScene(source, OpenSceneMode.Single);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("新シーンを保存できません。");
            scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

            var hidden = new List<string>();
            HideRoot("M1 main wave - static geometry", hidden);
            HideRoot("M1 Revision01 static supporting slopes", hidden);
            HideRoot("M1 Revision01 provisional region overlay", hidden);
            var foam = GameObject.Find("M1 static foam and foreground swell");
            if (foam == null) throw new InvalidOperationException("旧い白波の親が見つかりません。");
            foreach (var t in foam.GetComponentsInChildren<Transform>(true))
            {
                if (t.name.StartsWith("M1_Foam_FrontRibbon") || t.name.StartsWith("M1_Foam_Claw"))
                {
                    if (t.gameObject.activeSelf) { t.gameObject.SetActive(false); hidden.Add(PathOf(t)); }
                }
            }

            Directory.CreateDirectory(MaterialDir);
            var clay = MaterialAsset("AF26_Clay", "GreatWave/ArtFirst/AF26 Clay");
            var seaFlat = MaterialAsset("AF26_SeaFlat", "GreatWave/ArtFirst/AF26 Clay");
            seaFlat.SetFloat("_SeaOnly", 1);
            EditorUtility.SetDirty(seaFlat);
            var sea = GameObject.Find("M1 flat reference sea");
            if (sea == null) throw new InvalidOperationException("参照海面が見つかりません。");
            sea.GetComponent<Renderer>().sharedMaterial = seaFlat;

            foreach (var k in Keys)
            {
                string name = "AF26 K* " + k;
                var old = GameObject.Find(name);
                if (old != null) UnityEngine.Object.DestroyImmediate(old);
                var wave = new GameObject(name);
                wave.AddComponent<MeshFilter>();
                var r = wave.AddComponent<MeshRenderer>();
                r.sharedMaterial = clay;
                r.shadowCastingMode = ShadowCastingMode.Off;
                r.receiveShadows = false;
                var km = wave.AddComponent<AF26KStarMesh>();
                km.dataPath = OutRoot + "/kstar/kstar_" + k + ".gwb";
                wave.SetActive(k == "a45");   // 既定は 45°（作業計画 D6 の既定値）
            }

            var layout = JsonUtility.FromJson<Layout>(File.ReadAllText(LayoutJson));
            MakeCamera("AF26 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            MakeCamera("AF26 船上座席カメラ", layout.eyeWorld, BoatTarget, BoatFov);
            MakeCamera("AF26 側面カメラ", SidePosition, SideTarget, SideFov);
            MakeCamera("AF26 背面カメラ", BackPosition, BackTarget, BackFov);
            MakeCamera("AF26 真上カメラ", TopPosition, TopTarget, TopFov);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("新シーンを保存できません。");
            AssetDatabase.SaveAssets();
            string sourceHashAfter = Sha(source);
            var report = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), sourceScene = source, scene = ScenePath,
                sourceSceneSha256Before = sourceHashBefore, sourceSceneSha256After = sourceHashAfter,
                sourceSceneUnchanged = sourceHashBefore == sourceHashAfter, hiddenObjects = hidden.ToArray(),
                eyeWorld = layout.eyeWorld, sceneSha256 = Sha(ScenePath)
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af26_build_report.json", JsonUtility.ToJson(report, true));
            if (!report.sourceSceneUnchanged) throw new InvalidOperationException("元の M1 Revision01 シーンが変わりました。");
            UnityEngine.Debug.Log("AF26_BUILD_DONE hidden=" + hidden.Count);
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var waves = Keys.Select(k => FindInactive("AF26 K* " + k)).ToArray();
            var cams = new Dictionary<string, Camera>
            {
                { "painting", FindCamera("AF26 PaintingCam v1") }, { "boat", FindCamera("AF26 船上座席カメラ") },
                { "side", FindCamera("AF26 側面カメラ") }, { "back", FindCamera("AF26 背面カメラ") }, { "top", FindCamera("AF26 真上カメラ") }
            };
            var msaa = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var resolve = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            msaa.Create(); resolve.Create();
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            var report = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), startedUtc = DateTime.UtcNow.ToString("O"), width = W, height = H, msaa = 8,
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture（MSAA 8x → 解決）→ ReadPixels → PNG。ID 画像は 3840×2160・MSAA なし。PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            var items = new List<RenderItem>();
            for (int i = 0; i < Keys.Length; i++)
            {
                for (int j = 0; j < waves.Length; j++) waves[j].SetActive(j == i);
                var km = waves[i].GetComponent<AF26KStarMesh>();
                var mesh = km.EnsureLoaded();
                string dir = OutRoot + "/render/" + Keys[i];
                Directory.CreateDirectory(dir);
                var it = new RenderItem { key = Keys[i], gwb = km.FullDataPath, gwbSha256 = ShaAbs(km.FullDataPath), vertexCount = mesh.vertexCount, indexCount = (int)mesh.GetIndexCount(0) };
                foreach (var kv in cams) Capture(kv.Value, msaa, resolve, tex, dir + "/26_" + Keys[i] + "_" + kv.Key + ".png");
                it.idDistinctColors = RenderIds(cams["painting"], dir + "/26_" + Keys[i] + "_painting_ids.png");
                items.Add(it);
            }
            for (int j = 0; j < waves.Length; j++) waves[j].SetActive(Keys[j] == "a45");
            File.WriteAllText(OutRoot + "/render/idmap.json", "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n \"note_ja\": \"番号26 の ID 画像（3840×2160、MSAA なし）。空＝カメラの背景、3 隻はそれぞれの色、ほかは全て other（K*・参照海面・前景の旧うねり・富士）。\"\n}\n");
            report.items = items.ToArray();
            report.finishedUtc = DateTime.UtcNow.ToString("O");
            report.totalSeconds = (float)total.Elapsed.TotalSeconds;
            report.passed = items.Count == Keys.Length && items.All(x => x.vertexCount > 0);
            File.WriteAllText(OutRoot + "/af26_render_report.json", JsonUtility.ToJson(report, true));
            UnityEngine.Object.DestroyImmediate(tex); msaa.Release(); resolve.Release();
            UnityEngine.Object.DestroyImmediate(msaa); UnityEngine.Object.DestroyImmediate(resolve);
            UnityEngine.Debug.Log("AF26_RENDER_DONE items=" + items.Count + " seconds=" + report.totalSeconds);
            if (!report.passed) throw new InvalidOperationException("描画の検査が不合格です。");
        }

        static int RenderIds(Camera camera, string pngPath)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("ID シェーダーがありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Color c) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetColor("_IdColor", c); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var boats = new Dictionary<string, Color> { { "M1 left boat", IdBoatLeft }, { "M1 middle boat", IdBoatMid }, { "M1 foreground boat", IdBoatFg } };
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                string key = "other"; Color c = IdOther;
                foreach (var b in boats) { var root = GameObject.Find(b.Key); if (root != null && r.transform.IsChildOf(root.transform)) { key = b.Key; c = b.Value; } }
                saved.Add((r, r.sharedMaterials));
                var m = Mat(key, c);
                r.sharedMaterials = Enumerable.Repeat(m, Math.Max(1, r.sharedMaterials.Length)).ToArray();
            }
            var clear = camera.clearFlags; var bg = camera.backgroundColor;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = IdSky;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
            rt.Create();
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, true);
            var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            camera.allowHDR = false; camera.allowMSAA = false;
            camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(pngPath, tex.EncodeToPNG());
            var px = tex.GetPixels32(); var colors = new HashSet<int>();
            foreach (var p in px) colors.Add((p.r << 16) | (p.g << 8) | p.b);
            camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg;
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            return colors.Count;
        }

        static void Capture(Camera camera, RenderTexture msaa, RenderTexture resolve, Texture2D tex, string path)
        {
            var prev = camera.targetTexture;
            camera.aspect = (float)W / H;
            camera.targetTexture = msaa;
            camera.Render();
            Graphics.Blit(msaa, resolve);
            RenderTexture.active = resolve;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            camera.targetTexture = prev;
            File.WriteAllBytes(path, tex.EncodeToPNG());
        }

        static Camera MakeCamera(string name, Vector3 position, Vector3 target, float fov)
        {
            var old = GameObject.Find(name);
            if (old != null) UnityEngine.Object.DestroyImmediate(old);
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = SkyTop;
            cam.orthographic = false;
            cam.fieldOfView = fov;
            cam.nearClipPlane = .1f;
            cam.farClipPlane = 900;
            cam.aspect = (float)W / H;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            go.transform.position = position;
            go.transform.LookAt(target, Vector3.up);
            return cam;
        }

        static Camera FindCamera(string name)
        {
            var go = GameObject.Find(name);
            if (go == null) throw new InvalidOperationException("カメラがありません: " + name);
            return go.GetComponent<Camera>();
        }

        static GameObject FindInactive(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("K* がありません: " + name);
            return go;
        }

        static Material MaterialAsset(string name, string shaderName)
        {
            var shader = Shader.Find(shaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + shaderName);
            string path = MaterialDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(shader); AssetDatabase.CreateAsset(m, path); }
            m.shader = shader;
            EditorUtility.SetDirty(m);
            return m;
        }

        static void HideRoot(string name, List<string> hidden)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("非表示にする対象がありません: " + name);
            hidden.Add(go.activeSelf ? name : name + "（元から非表示）");
            go.SetActive(false);
        }

        static string PathOf(Transform t) => t.parent == null ? t.name : PathOf(t.parent) + "/" + t.name;

        static string Sha(string path) => ShaAbs(path);

        static string ShaAbs(string path)
        {
            using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] class Layout { public Vector3 eyeWorld; }
        [Serializable] class BuildReport
        {
            public string unity, utc, sourceScene, scene, sourceSceneSha256Before, sourceSceneSha256After, sceneSha256;
            public bool sourceSceneUnchanged;
            public string[] hiddenObjects;
            public Vector3 eyeWorld;
        }
        [Serializable] class RenderItem
        {
            public string key, gwb, gwbSha256;
            public int vertexCount, indexCount, idDistinctColors;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, startedUtc, finishedUtc, renderMethod;
            public int width, height, msaa;
            public float totalSeconds;
            public bool passed;
            public RenderItem[] items;
        }
    }
}
