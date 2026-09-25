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
    // 編号24「最初の画面：主役波 v0」。M1 Revision01 の構図シーンを別名で複製し、旧い静止波と斜面の仮形状を
    // 新シーンだけで非表示にして gw_wavegen v0 の水面シートを置く。PaintingCam v1・船上座席・側面から
    // Camera.Render → RenderTexture → PNG で描く（PC のオフスクリーン描画。HMD 実機ではない）。
    public static class AF24FirstLight
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF24_FirstLight.unity";
        const string MaterialDir = "Assets/GreatWave/ArtFirst/Materials";
        const string OutRoot = "Build/ArtFirst/24";
        const string LayoutJson = "../Docs/Evidence/M1/Revision01/15_revision_layout.json";
        const int W = 1920, H = 1080;

        // PaintingCam v1（Tools/PaintingTruth/painting_truth.json と同じ値）
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62);
        static readonly Vector3 PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        // 船上座席（15_revision_layout.json の eyeWorld）の注視点と画角は M1 Revision01 の視点1と同じ
        static readonly Vector3 BoatTarget = new Vector3(-7, 5, 3);
        const float BoatFov = 80;
        // 側面は M1 Revision01 の視点2と同じ
        static readonly Vector3 SidePosition = new Vector3(53, 22, -2);
        static readonly Vector3 SideTarget = new Vector3(-1, 7, 0);
        const float SideFov = 60;
        // 空は編号23の調色板「空上」（8bit sRGB）
        static readonly Color32 SkyTop = new Color32(248, 231, 195, 255);
        // 評価器の ID 色（成分は 0 か 255 だけ）
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Color IdBoatLeft = new Color(1, 0, 0), IdBoatMid = new Color(0, 1, 0), IdBoatFg = new Color(1, 1, 0);

        public static void BuildAndRender() { Build(); Render(); }

        public static void Build()
        {
            string source = GreatWave.Editor.M1RevisionBuilder.ScenePath;
            string sourceHashBefore = Sha(source);
            var scene = EditorSceneManager.OpenScene(source, OpenSceneMode.Single);
            // 別名で保存し、以後の変更は新シーンだけに入る（元の M1 Revision01 シーンは書き換えない）。
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
            var palette = MaterialAsset("AF24_Palette", "GreatWave/ArtFirst/AF24 Palette v0");
            var seaFlat = MaterialAsset("AF24_SeaFlat", "GreatWave/ArtFirst/AF24 Palette v0");
            seaFlat.SetFloat("_SeaOnly", 1);
            EditorUtility.SetDirty(seaFlat);
            var sea = GameObject.Find("M1 flat reference sea");
            if (sea == null) throw new InvalidOperationException("参照海面が見つかりません。");
            // 新シーンの参照海面だけ、波の平らな部分と同じ藍濃の無光照にする（M1_Sea.mat 自体は変えない）。
            sea.GetComponent<Renderer>().sharedMaterial = seaFlat;

            var old = GameObject.Find("AF24 主役波 v0");
            if (old != null) UnityEngine.Object.DestroyImmediate(old);
            var wave = new GameObject("AF24 主役波 v0");
            wave.AddComponent<MeshFilter>();
            var renderer = wave.AddComponent<MeshRenderer>();
            renderer.sharedMaterial = palette;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            var player = wave.AddComponent<AF24WavePlayer>();
            player.dataPath = OutRoot + "/wave/wave_v0.gwb";

            var layout = JsonUtility.FromJson<Layout>(File.ReadAllText(LayoutJson));
            MakeCamera("AF24 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            MakeCamera("AF24 船上座席カメラ", layout.eyeWorld, BoatTarget, BoatFov);
            MakeCamera("AF24 側面カメラ", SidePosition, SideTarget, SideFov);

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
            File.WriteAllText(OutRoot + "/af24_build_report.json", JsonUtility.ToJson(report, true));
            if (!report.sourceSceneUnchanged) throw new InvalidOperationException("元の M1 Revision01 シーンが変わりました。");
            UnityEngine.Debug.Log("AF24_BUILD_DONE hidden=" + hidden.Count);
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var player = UnityEngine.Object.FindAnyObjectByType<AF24WavePlayer>();
            if (player == null) throw new InvalidOperationException("AF24WavePlayer がありません。");
            var mesh = player.EnsureLoaded();
            // 形成率はマテリアル資産を書き換えず、MaterialPropertyBlock で渡す。
            var waveRenderer = player.GetComponent<MeshRenderer>();
            var block = new MaterialPropertyBlock();
            var painting = FindCamera("AF24 PaintingCam v1");
            var boat = FindCamera("AF24 船上座席カメラ");
            var side = FindCamera("AF24 側面カメラ");
            string framesP = OutRoot + "/frames_painting", framesB = OutRoot + "/frames_boat";
            foreach (var d in new[] { framesP, framesB }) { if (Directory.Exists(d)) Directory.Delete(d, true); Directory.CreateDirectory(d); }

            var msaa = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var resolve = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            msaa.Create(); resolve.Create();
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            var report = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), startedUtc = DateTime.UtcNow.ToString("O"),
                width = W, height = H, msaa = 8, frames = player.frameCount, fps = player.fps, tStarFrame = player.tStarFrame,
                nu = player.nu, nv = player.nv, dataPath = player.FullDataPath,
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture（MSAA 8x → 解決）→ ReadPixels → PNG。PC のオフスクリーン描画で、HMD 実機ではない。",
                meshUpdate = "CPU（AF24WavePlayer.SetFrame：Mesh.vertices の差し替え＋RecalculateNormals）"
            };
            int expectedVerts = player.nu * player.nv;
            int expectedIdx = player.triangleCount * 3;
            report.minVertexCount = int.MaxValue; report.minIndexCount = int.MaxValue;
            var loop = Stopwatch.StartNew();
            for (int f = 0; f < player.frameCount; f++)
            {
                player.SetFrame(f);
                block.SetFloat("_Progress", Progress(f / player.fps)); waveRenderer.SetPropertyBlock(block);
                int vc = mesh.vertexCount, ic = (int)mesh.GetIndexCount(0);
                report.minVertexCount = Math.Min(report.minVertexCount, vc); report.maxVertexCount = Math.Max(report.maxVertexCount, vc);
                report.minIndexCount = Math.Min(report.minIndexCount, ic); report.maxIndexCount = Math.Max(report.maxIndexCount, ic);
                foreach (var v in player.CurrentVertices) if (!(IsFinite(v.x) && IsFinite(v.y) && IsFinite(v.z))) report.nonFiniteVertices++;
                Capture(painting, msaa, resolve, tex, Path.Combine(framesP, "f_" + f.ToString("D4") + ".png"));
                Capture(boat, msaa, resolve, tex, Path.Combine(framesB, "f_" + f.ToString("D4") + ".png"));
                report.renderedFrames++;
            }
            report.frameLoopSeconds = (float)loop.Elapsed.TotalSeconds;
            // t* の静止画（側面）と、評価器の ID 画像（3840×2160、MSAA なし）
            player.SetFrame(player.tStarFrame);
            block.SetFloat("_Progress", 1); waveRenderer.SetPropertyBlock(block);
            Capture(side, msaa, resolve, tex, OutRoot + "/24_side_tstar.png");
            Capture(painting, msaa, resolve, tex, OutRoot + "/24_painting_tstar_direct.png");
            Capture(boat, msaa, resolve, tex, OutRoot + "/24_boat_tstar_direct.png");
            RenderIds(painting, OutRoot + "/24_painting_tstar_ids.png", OutRoot + "/24_idmap.json", report);
            report.vertexCountConstant = report.minVertexCount == expectedVerts && report.maxVertexCount == expectedVerts;
            report.indexCountConstant = report.minIndexCount == expectedIdx && report.maxIndexCount == expectedIdx;
            report.finishedUtc = DateTime.UtcNow.ToString("O");
            report.totalSeconds = (float)total.Elapsed.TotalSeconds;
            report.passed = report.renderedFrames == player.frameCount && report.vertexCountConstant && report.indexCountConstant && report.nonFiniteVertices == 0;
            File.WriteAllText(OutRoot + "/af24_render_report.json", JsonUtility.ToJson(report, true));
            UnityEngine.Object.DestroyImmediate(tex); msaa.Release(); resolve.Release();
            UnityEngine.Object.DestroyImmediate(msaa); UnityEngine.Object.DestroyImmediate(resolve);
            UnityEngine.Debug.Log("AF24_RENDER_DONE frames=" + report.renderedFrames + " passed=" + report.passed + " seconds=" + report.totalSeconds);
            if (!report.passed) throw new InvalidOperationException("描画の検査が不合格です。");
        }

        // 形成率 P_body(t) = smootherstep((t - 2) / 10)。Tools/GWWaveGen/params_v0.json の timeline と同じ。
        static float Progress(float t)
        {
            float x = Mathf.Clamp01((t - 2f) / 10f);
            return x * x * x * (x * (x * 6f - 15f) + 10f);
        }

        static void RenderIds(Camera camera, string pngPath, string idmapPath, RenderReport report)
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
            // 使われた色の数（ID 画像に混色がないことの確認）
            var px = tex.GetPixels32(); var colors = new HashSet<int>();
            foreach (var p in px) colors.Add((p.r << 16) | (p.g << 8) | p.b);
            report.idDistinctColors = colors.Count;
            camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg;
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            File.WriteAllText(idmapPath, "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n \"note_ja\": \"編号24 の ID 画像（3840×2160、MSAA なし）。空＝カメラの背景、ほかは全て other（主役波・参照海面・前景の旧うねり・富士）。\"\n}\n");
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
            cam.enabled = false; // Camera.Render でだけ使う
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
            // 非アクティブで保存された根も探す（GameObject.Find は非アクティブを見つけない）。
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("非表示にする対象がありません: " + name);
            hidden.Add(go.activeSelf ? name : name + "（元から非表示）");
            go.SetActive(false);
        }

        static string PathOf(Transform t) => t.parent == null ? t.name : PathOf(t.parent) + "/" + t.name;
        static bool IsFinite(float f) => !float.IsNaN(f) && !float.IsInfinity(f);

        static string Sha(string path)
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
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, startedUtc, finishedUtc, renderMethod, meshUpdate, dataPath;
            public int width, height, msaa, frames, tStarFrame, nu, nv, renderedFrames, minVertexCount, maxVertexCount, minIndexCount, maxIndexCount, nonFiniteVertices, idDistinctColors;
            public float fps, frameLoopSeconds, totalSeconds;
            public bool vertexCountConstant, indexCountConstant, passed;
        }
    }
}
