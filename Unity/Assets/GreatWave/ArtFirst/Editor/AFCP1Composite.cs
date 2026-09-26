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
    // 完成点 CP1 の合成シーン AF_CP1.unity。
    // 番号27 のプレハブ（空のドーム・海・3隻・富士・前景と斜面の仮置き）に、番号26 の K*（30°／45°／60°）を
    // 番号28 の NPR shader v1（色区テクスチャ）と外殻線 v0 で置く。27・28・26 のファイルは読むだけで変えない（前後の SHA-256 を記録する）。
    // 描画は Camera.Render → RenderTexture → PNG（PC のオフスクリーン描画。HMD 実機ではない）。
    public static class AFCP1Composite
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF_CP1.unity";
        const string OutRoot = "Build/ArtFirst/CP1";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab";
        const string NprMatPath = "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat";
        const string OutlineMatPath = "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat";
        const string LayoutPath = "../Tools/GWContext/context_layout.json";
        const string KStarDir = "Build/ArtFirst/26/kstar";
        const string BakeDir = "Build/ArtFirst/28/bake";
        static readonly string[] Keys = { "a30", "a45", "a60" };
        const int W = 1920, H = 1080;

        // PaintingCam v1（Tools/PaintingTruth/painting_truth.json と同じ値）
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        // 側面：番号26・28 の右側 (53,22,−2) は番号27 の右の斜面の仮置き（高さ約 19 m）の裏になるので、番号27 と同じ左側から主役波を見る
        static readonly Vector3 SidePosition = new Vector3(-90, 30, -14), SideTarget = new Vector3(-5, 8, -3);
        const float SideFov = 45;
        // 背面：番号26・28 と同じ
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60), BackTarget = new Vector3(-5, 8, -3);
        const float BackFov = 50;
        // 俯瞰：番号27 と同じ（右手前の上から、3隻・主役波・仮置きをまとめて見る）
        static readonly Vector3 OverviewPosition = new Vector3(40, 28, -70), OverviewTarget = new Vector3(0, 3, -12);
        const float OverviewFov = 55;
        // 座席の候補 (a)（右船）から見る注視点：主役波の中ほど
        static readonly Vector3 CandidateTarget = new Vector3(-5, 12, -2);
        // 評価器の ID 色（番号27 と同じ）
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Dictionary<string, Color> IdBoats = new Dictionary<string, Color> {
            { "boat_left", new Color(1, 0, 0) }, { "boat_mid", new Color(0, 1, 0) }, { "boat_fg", new Color(1, 1, 0) } };

        static string[] ProtectedFiles => new[] {
            ContextPrefab, "Assets/GreatWave/ArtFirst/Prefabs/AF27_SkyDome.prefab", NprMatPath, OutlineMatPath,
            "Assets/GreatWave/ArtFirst/Materials/AF28_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_ai_dark.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_white.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_boat_ochre.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_fuji_snow.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_fuji_slope.mat", "Assets/GreatWave/ArtFirst/Textures/AF27_SkyThetaT.asset",
            "Assets/GreatWave/ArtFirst/Textures/AF27_SkyGradient.asset", "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs",
            "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader", "Assets/GreatWave/ArtFirst/Shaders/AF27SkyDome.shader",
            "Assets/GreatWave/ArtFirst/Shaders/AF27Flat.shader", "Assets/GreatWave/Scenes/Tests/AF27_Context.unity",
            "Assets/GreatWave/Scenes/Tests/AF28_NPR.unity", "Assets/GreatWave/Scenes/Tests/AF26_KStar.unity" };

        public static void BuildAndRender() { Build(); Render(); }

        // ------------------------------------------------------------------ 組み立て
        public static void Build()
        {
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            var L = JsonUtility.FromJson<Layout>(File.ReadAllText(LayoutPath)).unity;
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false;
            RenderSettings.skybox = null;

            // 番号27 の背景一式（プレハブのまま置く。プレハブは変えない）
            var ctxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ContextPrefab);
            if (ctxAsset == null) throw new InvalidOperationException("番号27 のプレハブがありません: " + ContextPrefab);
            var ctx = (GameObject)PrefabUtility.InstantiatePrefab(ctxAsset);
            ctx.name = "CP1 背景（番号27：空・船・富士・海・仮置き）";

            // 番号26 の K* 3 案に番号28 の NPR v1 と外殻線 v0 を付ける（マテリアルは番号28 のものを参照するだけ）
            var npr = AssetDatabase.LoadAssetAtPath<Material>(NprMatPath);
            var outline = AssetDatabase.LoadAssetAtPath<Material>(OutlineMatPath);
            if (npr == null || outline == null) throw new InvalidOperationException("番号28 のマテリアルがありません。");
            foreach (var k in Keys)
            {
                var wave = new GameObject("CP1 K* " + k);
                wave.AddComponent<MeshFilter>();
                var r = wave.AddComponent<MeshRenderer>();
                r.sharedMaterial = npr;
                r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
                r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
                var km = wave.AddComponent<AF26KStarMesh>();
                km.dataPath = KStarDir + "/kstar_" + k + ".gwb";
                var line = new GameObject("CP1 外殻線 v0（番号28）");
                line.transform.SetParent(wave.transform, false);
                line.AddComponent<MeshFilter>();
                var lr = line.AddComponent<MeshRenderer>();
                lr.sharedMaterial = outline;
                lr.shadowCastingMode = ShadowCastingMode.Off; lr.receiveShadows = false;
                lr.lightProbeUsage = LightProbeUsage.Off; lr.reflectionProbeUsage = ReflectionProbeUsage.Off;
                var nw = wave.AddComponent<AF28NprWave>();
                nw.sdfPath = BakeDir + "/af28_uvsdf_" + k + ".bin";
                nw.warpPath = BakeDir + "/af28_uvwarp_" + k + ".json";
                nw.size = 4096;
                nw.outline = lr;
                wave.SetActive(k == "a45");   // 既定は 45°（作業計画 D6 の既定値・利用者未回答）
            }

            var cams = new GameObject("CP1 カメラ");
            MakeCamera(cams, "CP1 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            // 座席：番号27 の置き直した手前の船の座席（context_layout.json の eyeNumpy。Unity との差 0.05 mm）
            MakeCamera(cams, "CP1 船上座席カメラ", V(L.seat.eyeNumpy), V(L.seat.target), L.seat.fov);
            MakeCamera(cams, "CP1 側面カメラ", SidePosition, SideTarget, SideFov);
            MakeCamera(cams, "CP1 背面カメラ", BackPosition, BackTarget, BackFov);
            MakeCamera(cams, "CP1 俯瞰カメラ", OverviewPosition, OverviewTarget, OverviewFov);
            // D7 の判断材料：座席の候補 (a)「唇の下の船」＝右船（boat_mid）。番号27 と同じ測り方（船の局所 (0,10,−2) から船の局所の下向きに甲板を測り、1.2 m 上）。
            // 座席は決めていない（利用者の D7 待ち）。注視点は主役波の中ほど。
            var midRoot = GameObject.Find("AF27 船 boat_mid");
            if (midRoot == null) throw new InvalidOperationException("右船がありません。");
            var deck = midRoot.GetComponentsInChildren<MeshFilter>().Single(f => f.name == "Boat_Deck_Planks");
            var col = deck.gameObject.AddComponent<MeshCollider>(); col.sharedMesh = deck.sharedMesh; Physics.SyncTransforms();
            var probe = midRoot.transform.TransformPoint(V(L.seat.probeLocal));
            bool hitDeck = col.Raycast(new Ray(probe, -midRoot.transform.up), out RaycastHit hit, 100);
            UnityEngine.Object.DestroyImmediate(col);
            if (!hitDeck) throw new InvalidOperationException("右船の甲板を測れません。");
            var midEye = hit.point + Vector3.up * L.seat.eyeAboveDeck;
            MakeCamera(cams, "CP1 座席候補 右船カメラ", midEye, CandidateTarget, L.seat.fov);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = Sha(ScenePath),
                seatEye = V(L.seat.eyeNumpy), seatTarget = V(L.seat.target), seatFov = L.seat.fov, candidateRightBoatEye = midEye, candidateTarget = CandidateTarget,
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(),
                changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/cp1_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("番号26・27・28 の資産が変わりました: " + string.Join(", ", rep.changedFiles));
            UnityEngine.Debug.Log("CP1_BUILD_DONE");
        }

        // ------------------------------------------------------------------ 描画
        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var waves = Keys.Select(k => FindRoot("CP1 K* " + k)).ToArray();
            var cams = new Dictionary<string, Camera> {
                { "painting", FindCamera("CP1 PaintingCam v1") }, { "seat", FindCamera("CP1 船上座席カメラ") },
                { "side", FindCamera("CP1 側面カメラ") }, { "back", FindCamera("CP1 背面カメラ") }, { "overview", FindCamera("CP1 俯瞰カメラ") },
                { "seatmid", FindCamera("CP1 座席候補 右船カメラ") } };
            var rep = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), startedUtc = DateTime.UtcNow.ToString("O"),
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture → ReadPixels → PNG。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし、3840×2160）。PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            var items = new List<RenderItem>();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            try
            {
                for (int i = 0; i < waves.Length; i++)
                {
                    string key = Keys[i];
                    foreach (var w in waves) w.SetActive(w == waves[i]);
                    var nw = waves[i].GetComponent<AF28NprWave>();
                    var mesh = nw.EnsureLoaded();
                    string dir = OutRoot + "/render/" + key;
                    Directory.CreateDirectory(dir);
                    var files = new List<string>();
                    nw.outline.enabled = true;
                    foreach (var v in new[] { "painting", "seat", "side", "back", "overview", "seatmid" })
                        files.Add(Capture(cams[v], dir + "/cp1_" + key + "_" + v + ".png"));
                    // 確認図：主役波・海・空だけ（番号27 の船・富士・仮置きを一時的に隠す。場面の見え方ではない）
                    var ctx = FindRoot("CP1 背景（番号27：空・船・富士・海・仮置き）").transform;
                    var hide = new List<GameObject>();
                    foreach (Transform ch in ctx)
                        if (ch.gameObject.activeSelf && ch.name != "AF27 空のドーム" && ch.name != "AF27 参照海面") { ch.gameObject.SetActive(false); hide.Add(ch.gameObject); }
                    try
                    {
                        foreach (var v in new[] { "seat", "side", "back" })
                            files.Add(Capture(cams[v], dir + "/cp1_" + key + "_" + v + "_waveonly.png"));
                    }
                    finally { foreach (var g in hide) g.SetActive(true); }
                    // 評価器用の ID（外殻線なし＝番号26 と同じ判定の条件、外殻線あり＝記録）
                    nw.outline.enabled = false;
                    files.Add(RenderIds(cams["painting"], dir + "/cp1_" + key + "_painting_ids.png"));
                    nw.outline.enabled = true;
                    files.Add(RenderIds(cams["painting"], dir + "/cp1_" + key + "_painting_ids_line.png"));
                    items.Add(new RenderItem
                    {
                        key = key, vertexCount = mesh.vertexCount, gwb = waves[i].GetComponent<AF26KStarMesh>().FullDataPath,
                        gwbSha256 = Sha(waves[i].GetComponent<AF26KStarMesh>().FullDataPath), sdf = nw.FullSdfPath, sdfSha256 = Sha(nw.FullSdfPath),
                        files = files.ToArray(), filesSha256 = files.Select(Sha).ToArray()
                    });
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                foreach (var w in waves) w.SetActive(w.name == "CP1 K* a45");
            }
            File.WriteAllText(OutRoot + "/render/idmap.json",
                "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n" +
                " \"note_ja\": \"CP1 の ID 画像（3840×2160、MSAA なし）。空＝番号27 の空のドーム（とカメラの背景）、3隻はそれぞれの色、ほかは全て other（K*・参照海面・富士・前景のうねりと斜面の仮置きは (0,0,0)、_ids_line.png の外殻線は (255,0,255)）。_ids.png は外殻線なし、_ids_line.png は外殻線あり。\"\n}\n");
            var cam = cams["painting"]; cam.aspect = (float)W / H;
            rep.paintingCamPosition = cam.transform.position; rep.paintingCamEuler = cam.transform.rotation.eulerAngles; rep.paintingCamFov = cam.fieldOfView;
            rep.seatEye = cams["seat"].transform.position; rep.seatEuler = cams["seat"].transform.rotation.eulerAngles; rep.seatFov = cams["seat"].fieldOfView;
            rep.items = items.ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]);
            rep.finishedUtc = DateTime.UtcNow.ToString("O");
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = items.Count == Keys.Length && items.All(x => x.vertexCount == 80000) && rep.protectedUnchanged;
            File.WriteAllText(OutRoot + "/cp1_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("CP1_RENDER_DONE items=" + items.Count + " seconds=" + rep.totalSeconds);
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

        // 番号27 の RenderIds と同じ規則（AF24 ID Flat で塗り分け、MSAA なし、3840×2160）
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
                // 外殻線は押し出しを頂点シェーダーで行うので、材質を替えずに番号28 の ID 表示（大域の _AF28IdMode = 1 で (1, 0, 1)）で描く。
                // (1, 0, 1) は空・3隻のどの ID 色とも違うので、評価器では other になる。
                if (r.sharedMaterial != null && r.sharedMaterial.shader != null && r.sharedMaterial.shader.name == "GreatWave/ArtFirst/AF28 Outline v0") continue;
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
            Shader.SetGlobalFloat("_AF28IdMode", 1);
            camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
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
            cam.enabled = false; // Camera.Render でだけ使う
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Color.black;
            cam.fieldOfView = fov; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
            cam.allowHDR = false; cam.allowMSAA = true;
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

        static GameObject FindRoot(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("見つかりません: " + name);
            return go;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);

        [Serializable] class Layout { public UnityJ unity; }
        [Serializable] class UnityJ { public SeatJ seat; }
        [Serializable] class SeatJ { public string boatKey; public float[] eyeNumpy, target, probeLocal; public float fov, eyeAboveDeck; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256; public Vector3 seatEye, seatTarget, candidateRightBoatEye, candidateTarget; public float seatFov;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class RenderItem { public string key, gwb, gwbSha256, sdf, sdfSha256; public int vertexCount; public string[] files, filesSha256; }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, startedUtc, finishedUtc, renderMethod;
            public float totalSeconds, paintingCamFov, seatFov; public bool passed, protectedUnchanged;
            public Vector3 paintingCamPosition, paintingCamEuler, seatEye, seatEuler;
            public RenderItem[] items;
        }
    }
}
