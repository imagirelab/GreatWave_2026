using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号26修正01「唇を波峰方向へ延ばし、波峰全体を巻かせる（45°）」。
    // 番号27修正01 のプレハブ AF27R01_Context.prefab（背景一式、右船の置き直し、右船の水面、座席 v1 の目印）を置いて完全に展開し、
    // gw_wavegen v2 の K*（Build/ArtFirst/26修正01/kstar/kstar_a45.gwb）と、比較用に CP1 の K* 45°（番号26、Build/ArtFirst/26/kstar/kstar_a45.gwb）を
    // 番号26 の確認用クレイ（AF26_Clay.mat を参照するだけ）で置く。色は仮で、原画の色ではない（色の焼き直しは 28修正01）。
    // 機位は af26r01_views.py が書いた Build/ArtFirst/26修正01/af26r01_views.json から読む（座席 v1 からの見上げ・左右・管の中など）。
    // 描画は Camera.Render → RenderTexture → PNG（PC のオフスクリーン描画。HMD 実機ではない）。
    // 番号26・27・27修正01・28・CP1 のプレハブ・マテリアル・シェーダー・スクリプト・シーンは読むだけで変えない（前後の SHA-256 を記録する）。
    public static class AF26R01KStar
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF26R01_KStar.unity";
        const string OutRoot = "Build/ArtFirst/26修正01";
        const string ViewsJson = OutRoot + "/af26r01_views.json";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab";
        const string ClayMatPath = "Assets/GreatWave/ArtFirst/Materials/AF26_Clay.mat";
        const string NewGwb = OutRoot + "/kstar/kstar_a45.gwb";
        const string OldGwb = "Build/ArtFirst/26/kstar/kstar_a45.gwb";
        const string RootName = "AF26R01 背景（番号27修正01 のプレハブ）";
        const string NewName = "AF26R01 K* a45（26修正01、gw_wavegen v2）";
        const string OldName = "AF26R01 比較用 K* a45（番号26・CP1）";
        const string CamRoot = "AF26R01 カメラ";
        const int W = 1920, H = 1080;
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Dictionary<string, Color> IdBoats = new Dictionary<string, Color> {
            { "boat_left", new Color(1, 0, 0) }, { "boat_mid", new Color(0, 1, 0) }, { "boat_fg", new Color(1, 1, 0) } };

        static string[] ProtectedFiles => new[] {
            ContextPrefab, "Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab", "Assets/GreatWave/ArtFirst/Prefabs/AF27_SkyDome.prefab",
            ClayMatPath, "Assets/GreatWave/ArtFirst/Materials/AF26_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat", "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat",
            "Assets/GreatWave/ArtFirst/Meshes/AF27R01_RightSlope.asset",
            "Assets/GreatWave/ArtFirst/Shaders/AF26Clay.shader", "Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Editor/AF26KStar.cs", "Assets/GreatWave/ArtFirst/Editor/AF27R01Seat.cs",
            "Assets/GreatWave/Scenes/Tests/AF26_KStar.unity", "Assets/GreatWave/Scenes/Tests/AF27R01_Seat.unity", "Assets/GreatWave/Scenes/Tests/AF_CP1.unity" };

        public static void BuildAndRender() { Build(); Render(); }

        // ------------------------------------------------------------------ 組み立て
        public static void Build()
        {
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            var views = LoadViews();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false; RenderSettings.skybox = null;
            var ctxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ContextPrefab);
            if (ctxAsset == null) throw new InvalidOperationException("番号27修正01 のプレハブがありません: " + ContextPrefab);
            var ctx = (GameObject)PrefabUtility.InstantiatePrefab(ctxAsset);
            PrefabUtility.UnpackPrefabInstance(ctx, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            ctx.name = RootName;
            var clay = AssetDatabase.LoadAssetAtPath<Material>(ClayMatPath);
            if (clay == null) throw new InvalidOperationException("番号26 のクレイがありません: " + ClayMatPath);
            MakeWave(NewName, NewGwb, clay, true);
            MakeWave(OldName, OldGwb, clay, false);
            var cams = new GameObject(CamRoot);
            foreach (var v in views.views) MakeCamera(cams, "AF26R01 " + v.key, V(v.eye), V(v.target), v.fov);
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            AssetDatabase.SaveAssets();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = Sha(ScenePath),
                views = views.views.Length, protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(), changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af26r01_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("保護したファイルが変わりました: " + string.Join(", ", rep.changedFiles));
            UnityEngine.Debug.Log("AF26R01_BUILD_DONE views=" + views.views.Length);
        }

        static void MakeWave(string name, string gwb, Material clay, bool active)
        {
            var go = new GameObject(name);
            go.AddComponent<MeshFilter>();
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = clay;
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            go.AddComponent<AF26KStarMesh>().dataPath = gwb;
            go.SetActive(active);
        }

        // ------------------------------------------------------------------ 描画
        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            var views = LoadViews();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var waveNew = FindRoot(NewName); var waveOld = FindRoot(OldName);
            var meshNew = waveNew.GetComponent<AF26KStarMesh>().EnsureLoaded();
            waveOld.SetActive(true); var meshOld = waveOld.GetComponent<AF26KStarMesh>().EnsureLoaded(); waveOld.SetActive(false);
            string dir = OutRoot + "/render";
            Directory.CreateDirectory(dir);
            var files = new List<string>();
            var ctx = FindRoot(RootName).transform;
            // 形を読みやすくするため、描画の間だけ番号26 のクレイを複製したマテリアル（保存しない）を使い、光を機位ごとにカメラの後ろ上から当てる
            var rNew = waveNew.GetComponent<MeshRenderer>(); var rOld = waveOld.GetComponent<MeshRenderer>();
            var clayAsset = rNew.sharedMaterial;
            var clayRun = new Material(clayAsset) { hideFlags = HideFlags.DontSave, name = "AF26R01 クレイ（描画の間だけ）" };
            clayRun.SetFloat("_Ambient", 0.42f);
            rNew.sharedMaterial = clayRun; rOld.sharedMaterial = clayRun;
            foreach (var v in views.views)
            {
                var cam = FindCamera("AF26R01 " + v.key);
                var ld = (-cam.transform.forward + Vector3.up * 0.8f + cam.transform.right * 0.35f).normalized;
                clayRun.SetVector("_LightDir", new Vector4(ld.x, ld.y, ld.z, 0));
                foreach (var variant in v.variants)
                {
                    bool isNew = variant.StartsWith("r01");
                    waveNew.SetActive(isNew); waveOld.SetActive(!isNew);
                    bool waveOnly = variant.EndsWith("_waveonly");
                    var hidden = new List<Renderer>();
                    if (waveOnly)
                    {
                        // 主役波・空のドーム・参照海面だけを表示する確認図（場面の見え方ではない）
                        foreach (var r in ctx.GetComponentsInChildren<Renderer>(false))
                        {
                            if (!r.enabled || r.name == "AF27 空のドーム" || r.name == "AF27 参照海面") continue;
                            r.enabled = false; hidden.Add(r);
                        }
                    }
                    try { files.Add(Capture(cam, dir + "/af26r01_" + v.key + "_" + variant + ".png")); }
                    finally { foreach (var r in hidden) r.enabled = true; }
                }
            }
            rNew.sharedMaterial = clayAsset; rOld.sharedMaterial = clayAsset;
            UnityEngine.Object.DestroyImmediate(clayRun);
            waveNew.SetActive(true); waveOld.SetActive(false);
            var painting = FindCamera("AF26R01 painting");
            files.Add(RenderIds(painting, dir + "/af26r01_painting_ids.png"));
            waveNew.SetActive(false); waveOld.SetActive(true);
            files.Add(RenderIds(painting, dir + "/af26r01_painting_ids_cp1k.png"));
            waveNew.SetActive(true); waveOld.SetActive(false);
            File.WriteAllText(dir + "/idmap.json",
                "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n" +
                " \"note_ja\": \"番号26修正01 の ID 画像（3840×2160、MSAA なし）。番号27修正01・CP1 と同じ規則：空＝番号27 の空のドーム（とカメラの背景）、3隻はそれぞれの色、ほかは全て other（K*・参照海面・富士・前景のうねりと斜面の仮置き・右船の水面）。外殻線はない。_cp1k は比較用に K* だけ番号26（CP1）の 45° に替えたもの。\"\n}\n");
            var camRecs = views.views.Select(v => { var c = FindCamera("AF26R01 " + v.key); return new CamRec { name = v.key, position = c.transform.position, forward = c.transform.forward, fov = c.fieldOfView }; }).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            var rep = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(),
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture → ReadPixels → PNG。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし、3840×2160）。PC のオフスクリーン描画で、HMD 実機ではない。主役波は番号26 の確認用クレイ（仮の色）。",
                newGwb = Path.GetFullPath(NewGwb), newGwbSha256 = Sha(NewGwb), newVertexCount = meshNew.vertexCount, newIndexCount = (int)meshNew.GetIndexCount(0),
                oldGwb = Path.GetFullPath(OldGwb), oldGwbSha256 = Sha(OldGwb), oldVertexCount = meshOld.vertexCount,
                cameras = camRecs, files = files.ToArray(), filesSha256 = files.Select(Sha).ToArray(),
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]), totalSeconds = (float)total.Elapsed.TotalSeconds
            };
            rep.passed = rep.protectedUnchanged && meshNew.vertexCount > 0 && meshOld.vertexCount == 80000;
            File.WriteAllText(OutRoot + "/af26r01_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF26R01_RENDER_DONE files=" + files.Count + " seconds=" + rep.totalSeconds);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です。");
        }

        static string Capture(Camera camera, string path)
        {
            var prev = camera.targetTexture;
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            camera.aspect = (float)W / H;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        // 番号27修正01（AF27R01Seat.RenderIds）と同じ規則：AF24 ID Flat で塗り分け、MSAA なし、3840×2160
        static string RenderIds(Camera camera, string pngPath)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Color c) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetColor("_IdColor", c); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find("AF27 空のドーム");
            if (dome == null) throw new InvalidOperationException("空のドームがありません。");
            var boatRoots = IdBoats.Keys.ToDictionary(k => k, k => GameObject.Find("AF27 船 " + k));
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                if (!r.enabled) continue;
                string key = "other"; Color c = IdOther;
                if (r.gameObject == dome) { key = "sky"; c = IdSky; }
                foreach (var b in IdBoats) { var root = boatRoots[b.Key]; if (root != null && r.transform.IsChildOf(root.transform)) { key = b.Key; c = b.Value; } }
                saved.Add((r, r.sharedMaterials));
                r.sharedMaterials = Enumerable.Repeat(Mat(key, c), Math.Max(1, r.sharedMaterials.Length)).ToArray();
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
            camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg;
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            return pngPath;
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 position, Vector3 target, float fov)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color32(249, 232, 196, 255);
            cam.fieldOfView = fov; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
            cam.allowHDR = false; cam.allowMSAA = true;
            go.transform.position = position;
            go.transform.LookAt(target, Vector3.up);
            return cam;
        }

        static Camera FindCamera(string name)
        {
            var root = GameObject.Find(CamRoot);
            var t = root == null ? null : root.transform.Find(name);
            if (t == null) throw new InvalidOperationException("カメラがありません: " + name);
            return t.GetComponent<Camera>();
        }

        static GameObject FindRoot(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("見つかりません: " + name);
            return go;
        }

        static ViewsFile LoadViews()
        {
            if (!File.Exists(ViewsJson)) throw new InvalidOperationException("機位の JSON がありません: " + ViewsJson);
            var v = JsonUtility.FromJson<ViewsFile>(File.ReadAllText(ViewsJson));
            if (v == null || v.views == null || v.views.Length == 0) throw new InvalidOperationException("機位が空です。");
            return v;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);

        [Serializable] class ViewJ { public string key; public float[] eye, target; public float fov; public string[] variants; }
        [Serializable] class ViewsFile { public ViewJ[] views; }
        [Serializable] class CamRec { public string name; public Vector3 position, forward; public float fov; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256; public int views;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, renderMethod, newGwb, newGwbSha256, oldGwb, oldGwbSha256;
            public int newVertexCount, newIndexCount, oldVertexCount; public CamRec[] cameras;
            public string[] files, filesSha256; public bool protectedUnchanged, passed; public float totalSeconds;
        }
    }
}
